"""Canonical production/test roots used by tooling."""

from pathlib import Path

PRODUCTION_ROOT = Path(r"F:\PHAN-MEM-QUAN-LY-QR")
TEST_ROOT = Path(r"F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST")


def validate_paths() -> bool:
    return PRODUCTION_ROOT.is_dir() and TEST_ROOT.is_dir() and PRODUCTION_ROOT != TEST_ROOT
