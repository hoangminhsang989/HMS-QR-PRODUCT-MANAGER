from pathlib import Path


TEST_OUTPUT_ROOT = Path(r"F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST")


def require_test_output_path(path: str | Path) -> Path:
    target = Path(path).resolve()
    root = TEST_OUTPUT_ROOT.resolve()
    if target != root and root not in target.parents:
        raise ValueError(f"generated assets must stay under {root}")
    return target
