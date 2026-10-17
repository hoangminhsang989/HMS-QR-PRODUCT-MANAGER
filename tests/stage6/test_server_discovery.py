from unittest.mock import Mock

import pytest

from packages.application.server_discovery import load_saved_server_url, resolve_server_url, save_server_url
from apps.desktop.__main__ import desktop_credentials, desktop_server_url


def test_saved_server_url_round_trip(tmp_path):
    path = tmp_path / "desktop" / "server.json"
    save_server_url("http://192.168.1.10:8010/", path)
    assert load_saved_server_url(path) == "http://192.168.1.10:8010"


def test_desktop_uses_ready_saved_server_without_broadcast(tmp_path):
    path = tmp_path / "server.json"
    save_server_url("http://192.168.1.10:8010", path)
    discover = Mock()
    assert resolve_server_url(saved_path=path, discover=discover, ready=lambda _url: True) == "http://192.168.1.10:8010"
    discover.assert_not_called()


def test_desktop_discovers_and_persists_when_saved_server_is_offline(tmp_path):
    path = tmp_path / "server.json"
    save_server_url("http://192.168.1.9:8010", path)
    assert resolve_server_url(saved_path=path, discover=lambda: "http://192.168.1.10:8010", ready=lambda url: url.endswith(".10:8010")) == "http://192.168.1.10:8010"
    assert load_saved_server_url(path) == "http://192.168.1.10:8010"


def test_desktop_rejects_unready_explicit_server(tmp_path):
    with pytest.raises(RuntimeError, match="chưa sẵn sàng"):
        resolve_server_url(configured_url="http://192.168.1.10:8010", saved_path=tmp_path / "server.json", ready=lambda _url: False)


def test_desktop_uses_launcher_credentials_without_opening_dialog():
    dialog = Mock()
    assert desktop_credentials(username="admin", password="admin", dialog_factory=lambda: dialog) == ("admin", "admin")
    dialog.exec.assert_not_called()


def test_desktop_collects_credentials_from_native_dialog_when_missing():
    dialog = Mock()
    dialog.exec.return_value = 1
    dialog.username.text.return_value = "editor"
    dialog.password.text.return_value = "editor-password"
    assert desktop_credentials(dialog_factory=lambda: dialog) == ("editor", "editor-password")


def test_desktop_login_details_returns_remember_choice_without_saving(tmp_path):
    from apps.desktop.__main__ import desktop_login_details

    dialog = Mock()
    dialog.exec.return_value = 1
    dialog.username.text.return_value = "editor"
    dialog.password.text.return_value = "editor-password"
    dialog.remember_credentials.isChecked.return_value = True
    assert desktop_login_details(dialog_factory=lambda: dialog, load_credentials=lambda: None,
                                 credential_path=tmp_path / "credentials.json") == (
        "editor", "editor-password", True)
    dialog.remember_credentials.isChecked.assert_called_once()


def test_saved_credentials_prepopulate_login_dialog_and_unchecked_clears_them():
    from apps.desktop.__main__ import desktop_login_details

    dialog = Mock()
    dialog.exec.return_value = 1
    dialog.username.text.return_value = "editor"
    dialog.password.text.return_value = "new-password"
    dialog.remember_credentials.isChecked.return_value = False
    assert desktop_login_details(dialog_factory=lambda: dialog, load_credentials=lambda: ("editor", "old-password")) == (
        "editor", "new-password", False)
    dialog.username.setText.assert_called_once_with("editor")
    dialog.password.setText.assert_called_once_with("old-password")


def test_desktop_credential_store_never_writes_plaintext_password(tmp_path, monkeypatch):
    from apps.desktop import credentials

    monkeypatch.setattr(credentials, "_crypt", lambda value, *, unprotect: b"protected-blob" if not unprotect else b"secret-password")
    path = tmp_path / "credentials.json"
    credentials.save_credentials("editor", "secret-password", path)
    contents = path.read_text(encoding="utf-8")
    assert "secret-password" not in contents
    assert credentials.load_credentials(path) == ("editor", "secret-password")
    credentials.delete_credentials(path)
    assert not path.exists()


def test_desktop_keeps_automatic_server_resolution_when_available():
    dialog = Mock()
    assert desktop_server_url(resolver=lambda **_kwargs: "http://192.168.1.10:8010", dialog_factory=lambda: dialog) == "http://192.168.1.10:8010"
    dialog.exec.assert_not_called()


def test_desktop_offers_server_selection_after_automatic_discovery_failure():
    dialog = Mock()
    dialog.exec.return_value = 1
    dialog.server_url.text.return_value = "http://192.168.1.10:8010/"
    assert desktop_server_url(resolver=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")), dialog_factory=lambda: dialog) == "http://192.168.1.10:8010"


def test_desktop_does_not_hide_invalid_explicit_server_in_selection_dialog():
    with pytest.raises(RuntimeError, match="offline"):
        desktop_server_url(configured_url="http://192.168.1.10:8010", resolver=lambda **_kwargs: (_ for _ in ()).throw(RuntimeError("offline")))
