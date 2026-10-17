from pathlib import Path

import pytest
from fastapi import HTTPException

import apps.server.app as server_app


def test_factory_excel_path_accepts_only_files_below_configured_root(tmp_path, monkeypatch):
    root = tmp_path / "factory"
    root.mkdir()
    monkeypatch.setattr(server_app, "FACTORY_EXCEL_ROOT", str(root))

    assert server_app.factory_excel_path("orders.xlsx") == root / "orders.xlsx"
    with pytest.raises(HTTPException) as traversal:
        server_app.factory_excel_path("../outside.xlsx")
    assert traversal.value.status_code == 400
    with pytest.raises(HTTPException):
        server_app.factory_excel_path(str(tmp_path / "outside.xlsx"))
