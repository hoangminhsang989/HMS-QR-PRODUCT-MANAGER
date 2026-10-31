from __future__ import annotations
from pathlib import Path
from unittest.mock import Mock
import pytest
from apps.desktop.__main__ import desktop_server_url


def test_desktop_accepts_a_relay_link_as_server_url():
    """A relay link is a connection path, not a LAN address.

    The factory machine has no public IP, so the desktop reaches it through the
    relay hostname. Requiring LAN discovery first would make that URL unusable.
    """
    dialog = Mock()
    assert desktop_server_url(
        configured_url="https://kh01.vps.example",
        resolver=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")),
        dialog_factory=lambda: dialog,
    ) == "https://kh01.vps.example"
    dialog.exec.assert_not_called()


def test_desktop_over_relay_still_requires_server_login():
    """The link carries no authority: the account login is unchanged.

    A relay URL that skipped the login would hand the whole server to whoever
    held the link. The desktop must still collect credentials and the server
    must still refuse an unauthenticated request.
    """
    from fastapi.testclient import TestClient
    import apps.server.app as app_module

    with TestClient(app_module.app) as client:
        assert client.post(
            "/admin-api/api/v1/auth/login",
            json={"username": "no-such-account", "password": "wrong"},
        ).status_code == 401
        assert client.get("/tracking/api/v1/operators").status_code == 401
