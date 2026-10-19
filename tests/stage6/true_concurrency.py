"""Test-only deterministic concurrency instrumentation for the SQL engine.

The engine has exactly one writer per process: every write transaction holds a
single re-entrant lock for its whole duration, so two overlapping operations
are arbitrated by that lock rather than by database row locks.  This module
gates two workers at their decisive SQL statement so a test can prove the
operations really did overlap and then assert the engine's arbitration produced
exactly one winner.

The gate works by briefly releasing the write lock while a worker sits at the
barrier, which lets the second worker enter its own transaction and reach the
same statement.  On the way back in the worker refreshes its rollback snapshot,
so the interleaving the gate creates is a real one rather than a stale-snapshot
artifact.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier, BrokenBarrierError, Event, Lock, get_ident
from time import monotonic
from typing import Callable

from packages.sqlengine.database import Database, Transaction


TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True, slots=True)
class WorkerOutcome:
    label: str
    value: object | None
    error: BaseException | None
    completed_at: float


class DecisiveSqlWindow:
    """Synchronize two workers at one matched SQL operation."""

    def __init__(
        self,
        database: Database,
        predicate: Callable[[str], bool],
        *,
        hold_first_result: bool = False,
    ) -> None:
        self.database = database
        self.predicate = predicate
        self.hold_first_result = hold_first_result
        self.all_entered = Event()
        self.first_result_held = Event()
        self.release_first_result = Event()
        self._barrier = Barrier(2, action=self.all_entered.set, timeout=TIMEOUT_SECONDS)
        self._mutex = Lock()
        self._entered_threads: set[int] = set()
        self._original_execute = None
        self._original_database_execute = None
        self.entered_at: dict[int, float] = {}
        self.holder_thread: int | None = None
        self.matched_statements: list[str] = []

    def __enter__(self) -> "DecisiveSqlWindow":
        self._original_execute = Transaction.execute
        self._original_database_execute = Database.execute
        window = self

        def guarded_database_execute(database, sql, parameters=None):
            # No lock is held here yet, so both workers can meet at the barrier
            # before either one opens its transaction.
            if window.predicate(sql):
                window._enter(None, sql)
                if window.hold_first_result:
                    window._maybe_hold()
            return window._original_database_execute(database, sql, parameters)

        def guarded_execute(transaction, sql, parameters=None):
            if window.predicate(sql):
                window._enter(transaction, sql)
                if window.hold_first_result:
                    window._maybe_hold()
            return window._original_execute(transaction, sql, parameters)

        Database.execute = guarded_database_execute
        Transaction.execute = guarded_execute
        return self

    def __exit__(self, *_exc) -> None:
        self.release_first_result.set()
        try:
            self._barrier.abort()
        except Exception:
            pass
        Transaction.execute = self._original_execute
        Database.execute = self._original_database_execute
        self._original_execute = None
        self._original_database_execute = None

    def _enter(self, transaction: Transaction | None, sql: str) -> None:
        thread_id = get_ident()
        with self._mutex:
            if thread_id in self._entered_threads:
                return
            self._entered_threads.add(thread_id)
            self.matched_statements.append(sql)
            self.entered_at[thread_id] = monotonic()

        if transaction is None:
            try:
                self._barrier.wait(timeout=TIMEOUT_SECONDS)
            except BrokenBarrierError as exc:
                raise AssertionError("decisive SQL overlap barrier was not reached twice") from exc
            return

        database = transaction.database
        held = database._write_lock
        # Let the second worker into its own transaction so both genuinely sit
        # at the same statement, then take the lock back and resynchronize the
        # rollback snapshot with whatever the other worker committed.
        held.release()
        try:
            self._barrier.wait(timeout=TIMEOUT_SECONDS)
        except BrokenBarrierError as exc:
            raise AssertionError("decisive SQL overlap barrier was not reached twice") from exc
        finally:
            held.acquire()
        transaction._saved_rows = database.schema.clone_rows()
        transaction._saved_tables = _snapshot_tables(database.schema)

    def _maybe_hold(self) -> None:
        thread_id = get_ident()
        should_hold = False
        with self._mutex:
            if self.holder_thread is None:
                self.holder_thread = thread_id
                should_hold = True
        if should_hold:
            self.first_result_held.set()
            if not self.release_first_result.wait(TIMEOUT_SECONDS):
                raise AssertionError("first-result release gate timed out")

    def assert_distinct_workers(self) -> None:
        assert self.all_entered.is_set(), "both decisive SQL windows were not entered"
        assert len(self._entered_threads) == 2

    def assert_overlap_before_completion(self, outcomes: tuple[WorkerOutcome, WorkerOutcome]) -> None:
        self.assert_distinct_workers()
        assert max(self.entered_at.values()) <= min(outcome.completed_at for outcome in outcomes)


def _snapshot_tables(schema):
    from packages.sqlengine.database import _snapshot_tables as snapshot

    return snapshot(schema)


def run_worker_pair(
    window: DecisiveSqlWindow,
    worker_a: Callable[[], object],
    worker_b: Callable[[], object],
    *,
    while_first_result_held: Callable[[tuple[Future, Future]], None] | None = None,
) -> tuple[WorkerOutcome, WorkerOutcome]:
    """Run two bounded workers and preserve their values/errors as evidence."""

    def invoke(label: str, worker: Callable[[], object]) -> WorkerOutcome:
        try:
            return WorkerOutcome(label, worker(), None, monotonic())
        except BaseException as exc:  # test evidence must preserve exact product error
            return WorkerOutcome(label, None, exc, monotonic())

    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="engine-concurrency")
    futures = (
        executor.submit(invoke, "A", worker_a),
        executor.submit(invoke, "B", worker_b),
    )
    try:
        assert window.all_entered.wait(TIMEOUT_SECONDS), "workers did not reach decisive SQL window"
        if while_first_result_held is not None:
            assert window.first_result_held.wait(TIMEOUT_SECONDS), "first result was not held"
            while_first_result_held(futures)
            window.release_first_result.set()
        outcomes = (
            futures[0].result(timeout=TIMEOUT_SECONDS),
            futures[1].result(timeout=TIMEOUT_SECONDS),
        )
        window.assert_overlap_before_completion(outcomes)
        return outcomes
    finally:
        window.release_first_result.set()
        try:
            window._barrier.abort()
        except Exception:
            pass
        # Do not add an unbounded implicit thread join after the explicitly
        # bounded Future/Barrier/Event waits above. Normal success reaches this
        # point with both futures complete; timeout paths release every gate
        # and return control without masking the bounded diagnostic.
        executor.shutdown(wait=False, cancel_futures=True)


__all__ = [
    "DecisiveSqlWindow",
    "TIMEOUT_SECONDS",
    "WorkerOutcome",
    "run_worker_pair",
]
