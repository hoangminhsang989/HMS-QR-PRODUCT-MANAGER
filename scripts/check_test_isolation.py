"""Fail if known runtime/test artifacts appear in the production tree."""

from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
FORBIDDEN_NAMES = {
    ".pytest_cache", "__pycache__", ".coverage", "coverage.xml", "htmlcov", "tmp", "temp",
    "screenshots", "playwright", "test-output", "test.db", "test.sqlite3",
}


def find_violations() -> list[Path]:
    violations: list[Path] = []
    for path in ROOT.rglob("*"):
        if any(part in FORBIDDEN_NAMES for part in path.parts) or path.suffix == ".pyc":
            violations.append(path)
    return violations


if __name__ == "__main__":
    found = find_violations()
    if found:
        for path in found:
            print(path)
        raise SystemExit(1)
    print("TEST_ISOLATION_PASS")
