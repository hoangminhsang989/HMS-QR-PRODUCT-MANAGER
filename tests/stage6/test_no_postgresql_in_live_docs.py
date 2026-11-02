"""Live documentation must not send an operator to install PostgreSQL.

ADR-015 dropped PostgreSQL on 2026-10-18: packages/sqlengine is SQLite-only,
nothing imports psycopg, and requirements.txt forbids it by name. The
deployment docs were never reconciled with that. `docs/DEPLOYMENT_TOPOLOGY.md`
still drew `QR Server --> PostgreSQL` as its diagram, and
`docs/POSTGRESQL_LAN_DEPLOYMENT.md` carried a "superseded by ADR-015" banner
over 106 lines that still told the operator to create a database, a role, and a
`postgresql+psycopg` URL.

The banner is the trap. It reads like the problem was handled, so nobody reads
the 106 lines under it - which is exactly why they survived two weeks after the
decision they contradict. A guard that only checks the file was deleted does
not catch that; this one checks what the remaining live docs actually say.
"""
from __future__ import annotations

from pathlib import Path
import re

import pytest

SOURCE_ROOT = Path(__file__).resolve().parents[2]

# Documentation an operator is expected to follow today. Historical records
# under docs/checkpoints/, docs/handoffs/, docs/authorities/, ADRs in
# docs/DECISIONS.md, PROJECT_STATE.md and .opencode/ are deliberately absent:
# they record what was true when they were written, and rewriting them would
# destroy the audit trail rather than clean it up.
LIVE_DOCS = (
    "README.md",
    "docs/DEPLOYMENT_TOPOLOGY.md",
    "docs/R011_MACHINE_A_DEPLOYMENT_OPERATOR_RUNBOOK.md",
    "docs/ARCHITECTURE.md",
    "docs/DATA_MODEL.md",
    "docs/SECURITY.md",
    "docs/TEST_POLICY.md",
    "docs/MACHINE_2_DESKTOP.md",
    "docs/DESKTOP_UPGRADE_BACKLOG.md",
    "docs/LICENSE_GATE.md",
    "web/README.md",
)

DEAD_PATTERNS = (
    # A URL form the validator now rejects outright.
    r"postgresql\+psycopg://",
    # Instructions to install or run a database server.
    r"(?i)install\s+postgresql",
    r"(?i)run\s+postgresql",
    r"(?i)postgresql\s+on\s+the\s+server\s+only",
    r"(?i)create\s+a\s+postgresql\s+database",
)


@pytest.mark.parametrize("relative", LIVE_DOCS, ids=lambda rel: rel)
def test_no_live_doc_instructs_an_operator_to_use_postgresql(relative: str):
    path = SOURCE_ROOT / relative
    assert path.is_file(), f"{relative} is missing"
    text = path.read_text(encoding="utf-8", errors="replace")
    for pattern in DEAD_PATTERNS:
        match = re.search(pattern, text)
        assert match is None, (
            f"{relative} still tells an operator to use PostgreSQL "
            f"(matched {pattern!r} at offset {match.start()}). ADR-015 removed "
            "PostgreSQL from the runtime; packages/sqlengine is SQLite-only and "
            "psycopg is absent from requirements.txt."
        )


def test_the_deleted_postgresql_runbook_is_gone():
    """The file itself, not just its contents.

    Its name was the instruction: an operator who saw it linked from README
    followed it. Deleting the file is what stops that, so the guard asserts the
    deletion rather than trusting the content check above.
    """

    assert not (SOURCE_ROOT / "docs" / "POSTGRESQL_LAN_DEPLOYMENT.md").exists(), (
        "docs/POSTGRESQL_LAN_DEPLOYMENT.md is back. PostgreSQL is gone from the "
        "runtime (ADR-015); do not re-add a runbook for installing it."
    )
    readme = (SOURCE_ROOT / "README.md").read_text(encoding="utf-8")
    assert "POSTGRESQL_LAN_DEPLOYMENT" not in readme, (
        "README.md links to the deleted PostgreSQL runbook"
    )


def test_the_deployment_topology_diagram_shows_the_embedded_engine():
    """The diagram is the first thing anyone reads; it must name the real path.

    Only the diagram block is checked, not the whole file: the prose underneath
    is allowed to name PostgreSQL in order to explain that it is gone, which is
    the opposite of instructing anyone to use it.
    """

    text = (SOURCE_ROOT / "docs" / "DEPLOYMENT_TOPOLOGY.md").read_text(encoding="utf-8")
    diagram = re.search(r"```text\n(.*?)```", text, re.S)
    assert diagram is not None, "docs/DEPLOYMENT_TOPOLOGY.md has no ```text diagram"
    assert "PostgreSQL" not in diagram.group(1), (
        "the topology diagram still draws PostgreSQL as the datastore"
    )
    assert "sqlengine" in diagram.group(1).lower() or "sqlite" in diagram.group(1).lower(), (
        "the topology diagram does not show the embedded SQL engine"
    )


# Deployment symbols removed from packages/deployment in the same tranche. A
# live doc that still names one is sending an operator to configure something
# the code no longer has, which is the failure this whole file exists to stop.
REMOVED_SYMBOLS = (
    "PostgreSQLPlan",
    "POSTGRESQL_DATA_ROOT",
    "postgresql_existing_decision",
    "postgresql_local_only",
)


def test_no_live_doc_names_a_removed_deployment_symbol():
    """The runbook listed `POSTGRESQL_DATA_ROOT` among the roots an operator
    must preserve - after that root had been deleted from ``layout.py``.

    The instruction-level patterns above did not catch it: nothing in that line
    says "install PostgreSQL" or carries a psycopg URL. It just names a symbol
    that no longer exists, which is a quieter way to be wrong and the one this
    test is for.
    """

    offenders = []
    for relative in LIVE_DOCS:
        path = SOURCE_ROOT / relative
        if not path.is_file():
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        for symbol in REMOVED_SYMBOLS:
            if symbol in text:
                offenders.append(f"{relative} names {symbol}")
    assert not offenders, (
        "these live docs reference deployment symbols that were removed from "
        "packages/deployment:\n  " + "\n  ".join(offenders)
    )


def test_removed_symbols_are_absent_from_the_code():
    """The other half: the symbols really are gone, so the doc check is honest.

    This file is excluded from the search. A guard that names a symbol in order
    to look for it always matches itself - my first version asserted on its own
    ``assert "import" not in line`` and failed, which is the same class of
    mistake as a guard that reads only one of two copies.
    """

    import subprocess

    self_path = Path(__file__).resolve()
    for symbol in REMOVED_SYMBOLS:
        result = subprocess.run(
            ["git", "grep", "-n", symbol, "--", "*.py"],
            cwd=SOURCE_ROOT, capture_output=True, text=True, timeout=120,
        )
        for line in result.stdout.splitlines():
            location = line.split(":", 1)[0]
            if (SOURCE_ROOT / location).resolve() == self_path:
                continue
            # A docstring explaining that the symbol used to exist is allowed;
            # an import or a constructor call is not.
            assert "import" not in line and "PostgreSQLPlan(" not in line, (
                f"{symbol} is still used in code: {line}"
            )
