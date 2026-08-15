"""Test-only deterministic PostgreSQL concurrency instrumentation.

This module never changes transaction semantics or commits on behalf of product
code.  It observes the real connection used by a repository operation, records
its PostgreSQL backend PID, and gates two workers immediately before their
decisive SQL statement.
"""

from __future__ import annotations

from concurrent.futures import Future, ThreadPoolExecutor
from dataclasses import dataclass
from threading import Barrier, BrokenBarrierError, Event, Lock, get_ident
from time import monotonic
from typing import Callable

from sqlalchemy import event


TIMEOUT_SECONDS = 8.0


@dataclass(frozen=True, slots=True)
class WorkerOutcome:
    label: str
    value: object | None
    error: BaseException | None
    completed_at: float


class DecisiveSqlWindow:
    """Synchronize two real DB connections at one matched SQL operation."""

    def __init__(
        self,
        engine,
        predicate: Callable[[str], bool],
        *,
        hold_first_result: bool = False,
    ) -> None:
        self.engine = engine
        self.predicate = predicate
        self.hold_first_result = hold_first_result
        self.all_entered = Event()
        self.first_result_held = Event()
        self.release_first_result = Event()
        self._barrier = Barrier(2, action=self.all_entered.set, timeout=TIMEOUT_SECONDS)
        self._mutex = Lock()
        self._entered_threads: set[int] = set()
        self.backend_pids: dict[int, int] = {}
        self.entered_at: dict[int, float] = {}
        self.holder_backend_pid: int | None = None

    def __enter__(self) -> "DecisiveSqlWindow":
        event.listen(self.engine, "before_cursor_execute", self._before_cursor_execute)
        if self.hold_first_result:
            event.listen(self.engine, "after_cursor_execute", self._after_cursor_execute)
        return self

    def __exit__(self, *_exc) -> None:
        self.release_first_result.set()
        try:
            self._barrier.abort()
        except Exception:
            pass
        event.remove(self.engine, "before_cursor_execute", self._before_cursor_execute)
        if self.hold_first_result:
            event.remove(self.engine, "after_cursor_execute", self._after_cursor_execute)

    def _before_cursor_execute(
        self, connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        if not self.predicate(statement):
            return
        thread_id = get_ident()
        with self._mutex:
            if thread_id in self._entered_threads:
                return
            self._entered_threads.add(thread_id)

        driver_connection = connection.connection.driver_connection
        with driver_connection.cursor() as cursor:
            cursor.execute("SELECT pg_backend_pid()")
            backend_pid = int(cursor.fetchone()[0])
            cursor.execute("SET LOCAL lock_timeout = '5s'")
        with self._mutex:
            self.backend_pids[thread_id] = backend_pid
            self.entered_at[thread_id] = monotonic()
        try:
            self._barrier.wait(timeout=TIMEOUT_SECONDS)
        except BrokenBarrierError as exc:
            raise AssertionError("decisive SQL overlap barrier was not reached twice") from exc

    def _after_cursor_execute(
        self, _connection, _cursor, statement, _parameters, _context, _executemany
    ) -> None:
        if not self.predicate(statement):
            return
        thread_id = get_ident()
        backend_pid = self.backend_pids.get(thread_id)
        should_hold = False
        with self._mutex:
            if self.holder_backend_pid is None and backend_pid is not None:
                self.holder_backend_pid = backend_pid
                should_hold = True
        if should_hold:
            self.first_result_held.set()
            if not self.release_first_result.wait(TIMEOUT_SECONDS):
                raise AssertionError("row-lock holder release gate timed out")

    def assert_distinct_backends(self) -> None:
        assert self.all_entered.is_set(), "both decisive SQL windows were not entered"
        assert len(self.backend_pids) == 2
        assert len(set(self.backend_pids.values())) == 2

    def assert_overlap_before_completion(self, outcomes: tuple[WorkerOutcome, WorkerOutcome]) -> None:
        self.assert_distinct_backends()
        assert max(self.entered_at.values()) <= min(outcome.completed_at for outcome in outcomes)


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

    executor = ThreadPoolExecutor(max_workers=2, thread_name_prefix="r010r2a1")
    futures = (
        executor.submit(invoke, "A", worker_a),
        executor.submit(invoke, "B", worker_b),
    )
    try:
        assert window.all_entered.wait(TIMEOUT_SECONDS), "workers did not reach decisive SQL window"
        if while_first_result_held is not None:
            assert window.first_result_held.wait(TIMEOUT_SECONDS), "row lock was not acquired"
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
