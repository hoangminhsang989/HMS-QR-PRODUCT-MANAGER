from apps.desktop.app import create_app as create_desktop_app
from apps.server.app import create_app as create_server_app
from config.paths import validate_paths


def test_server_and_desktop_imports():
    assert create_server_app()["status"] == "foundation"
    assert create_desktop_app()["status"] == "foundation"


def test_canonical_paths_exist():
    assert validate_paths()
