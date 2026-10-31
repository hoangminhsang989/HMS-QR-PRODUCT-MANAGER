"""The desktop licence gate: decision table, orchestration, screens, enforcement.

The gate is deliberately split from Qt (``license_gate``) so most of these tests
need no display at all. The dialog tests take a ``QApplication`` the same way
``tests/stage1/test_desktop.py`` does.

The last test is the one that matters: an active gate whose client reports a
locked status must stop the launch before the app contacts a server or builds a
window. Commit ``ce9f3eb`` removed an earlier licence system because nothing
ever consumed it; these assertions are what stops that happening again.
"""

from __future__ import annotations

from pathlib import Path

import pytest
from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
from cryptography.hazmat.primitives.serialization import Encoding, PublicFormat

from apps.desktop import __main__ as desktop_main
from apps.desktop.license_dialogs import (
    ActivationDialog,
    GraceBanner,
    LockScreen,
    QtLicenseUi,
)
from apps.desktop.license_gate import (
    ACTIVE_ENV,
    FILE_KEY_ENV,
    PRODUCT,
    PUBLIC_KEY_ENV,
    SERVER_URL_ENV,
    VIETNAMESE_REASONS,
    DesktopLicenseGate,
    build_client,
    decide_action,
    gate_is_active,
)

SOURCE_ROOT = Path(__file__).resolve().parents[1]


@pytest.fixture(scope="session")
def qapp():
    from PySide6.QtWidgets import QApplication

    return QApplication.instance() or QApplication([])


@pytest.fixture()
def public_pem() -> bytes:
    key = Ed25519PrivateKey.generate()
    return key.public_key().public_bytes(
        encoding=Encoding.PEM, format=PublicFormat.SubjectPublicKeyInfo
    )


def active_env(public_pem: bytes, **overrides: str) -> dict[str, str]:
    env = {
        SERVER_URL_ENV: "http://127.0.0.1:9000",
        PUBLIC_KEY_ENV: public_pem.decode("utf-8"),
        FILE_KEY_ENV: "11" * 32,
    }
    env.update(overrides)
    return env


class FakeClient:
    """Answers a scripted sequence of launch statuses and nothing else."""

    def __init__(self, *statuses: str, grace_days: int | None = None) -> None:
        self._statuses = list(statuses)
        self.grace_days = grace_days
        self.checks = 0
        self.grace_reads = 0

    def check_at_launch(self, online_timeout: float = 2.0) -> str:
        self.checks += 1
        if self._statuses:
            return self._statuses.pop(0)
        return "ok"

    def grace_days_left(self) -> int | None:
        self.grace_reads += 1
        return self.grace_days


class ExplodingClient:
    def check_at_launch(self, online_timeout: float = 2.0) -> str:
        raise RuntimeError("the licence file could not be read")

    def grace_days_left(self) -> int | None:
        raise RuntimeError("the licence file could not be read")


class FakeUi:
    """Records what the gate asked for, and answers as scripted."""

    def __init__(self, *, activation: bool = False, lock: bool = False) -> None:
        self.activation_result = activation
        self.lock_result = lock
        self.calls: list[object] = []

    def activation(self) -> bool:
        self.calls.append("activation")
        return self.activation_result

    def lock(self, reason: str) -> bool:
        self.calls.append(("lock", reason))
        return self.lock_result

    def banner(self, grace_days: int | None) -> None:
        self.calls.append(("banner", grace_days))


class ScriptedClient:
    """``activate``/``import_license_file`` answer whatever the test scripts."""

    def __init__(self, *online_outcomes: str) -> None:
        self.online_outcomes = list(online_outcomes)
        self.import_outcomes: list[str] = []
        self.activated_keys: list[str] = []

    def activate(self, key: str) -> str:
        self.activated_keys.append(key)
        return self.online_outcomes.pop(0) if self.online_outcomes else "ok"

    def create_request_file(self, path: str) -> None:
        Path(path).write_text("request", encoding="utf-8")

    def import_license_file(self, path: str) -> str:
        return self.import_outcomes.pop(0) if self.import_outcomes else "ok"


# -- gate_is_active ----------------------------------------------------------


@pytest.mark.parametrize(
    "missing",
    [None, SERVER_URL_ENV, PUBLIC_KEY_ENV, FILE_KEY_ENV],
)
def test_the_gate_is_active_only_with_all_three_variables(public_pem, missing):
    env = active_env(public_pem)
    if missing is not None:
        env[missing] = ""
    assert gate_is_active(env) is (missing is None)


def test_a_blank_variable_is_not_a_variable(public_pem):
    env = active_env(public_pem)
    env[SERVER_URL_ENV] = "   "
    assert gate_is_active(env) is False


def test_the_gate_reads_the_process_environment_by_default(monkeypatch, public_pem):
    for name in ACTIVE_ENV:
        monkeypatch.delenv(name, raising=False)
    assert gate_is_active() is False
    monkeypatch.setenv(SERVER_URL_ENV, "http://127.0.0.1:9000")
    monkeypatch.setenv(PUBLIC_KEY_ENV, public_pem.decode("utf-8"))
    monkeypatch.setenv(FILE_KEY_ENV, "22" * 32)
    assert gate_is_active() is True


# -- decide_action -----------------------------------------------------------


@pytest.mark.parametrize(
    ("status", "expected"),
    [
        ("ok", "allow"),
        ("offline-ok", "allow"),
        ("server-error", "allow"),
        ("grace", "warn"),
        ("expired", "lock"),
        ("revoked", "lock"),
        ("no-license", "activate"),
        ("hwid-mismatch", "activate"),
        ("hwid-error", "activate"),
        ("a-status-nobody-has-heard-of", "activate"),
    ],
)
def test_decide_action_maps_every_documented_status(status, expected):
    assert decide_action(status, 3) == expected


def test_the_decision_never_depends_on_the_grace_count():
    for days in (None, 0, 1, 5, 99):
        assert decide_action("expired", days) == "lock"
        assert decide_action("ok", days) == "allow"


def test_every_lock_status_has_a_vietnamese_reason():
    assert set(VIETNAMESE_REASONS) == {"expired", "revoked"}
    assert all(reason.strip() for reason in VIETNAMESE_REASONS.values())


# -- build_client ------------------------------------------------------------


def test_the_client_is_built_for_this_product(public_pem):
    client = build_client(active_env(public_pem))
    assert client.product == PRODUCT
    assert client.server_url == "http://127.0.0.1:9000"


def test_the_public_key_is_accepted_as_a_path_or_as_pem_text(public_pem, tmp_path):
    key_file = tmp_path / "server-public.pem"
    key_file.write_bytes(public_pem)

    from_path = build_client(active_env(public_pem, **{PUBLIC_KEY_ENV: str(key_file)}))
    from_text = build_client(active_env(public_pem))

    assert from_path.public_pem == from_text.public_pem == public_pem.strip()


def test_the_file_key_is_decoded_from_hex(public_pem):
    client = build_client(active_env(public_pem, **{FILE_KEY_ENV: "ab" * 32}))
    assert client.file_key == b"\xab" * 32


def test_a_non_hex_file_key_is_rejected_with_the_variable_named(public_pem):
    with pytest.raises(ValueError, match=FILE_KEY_ENV):
        build_client(active_env(public_pem, **{FILE_KEY_ENV: "not-hex-at-all"}))


def test_a_short_file_key_is_rejected(public_pem):
    with pytest.raises(ValueError, match="32 bytes"):
        build_client(active_env(public_pem, **{FILE_KEY_ENV: "ab" * 16}))


def test_no_client_is_built_when_the_gate_is_off(public_pem):
    env = active_env(public_pem)
    env.pop(SERVER_URL_ENV)
    assert build_client(env) is None
    assert build_client({}) is None


def test_the_vendored_sdk_is_reachable_under_both_names_as_one_module():
    """The SDK's files import each other as ``hms_license``.

    They are vendored byte-for-byte, so the name is bound instead of rewritten.
    If that binding ever regresses, ``packages.hms_license`` would import a
    second, separate copy of every module.
    """
    import sys

    from apps.desktop.license_gate import _vendored_sdk

    module = _vendored_sdk()
    assert sys.modules["hms_license"] is module
    assert sys.modules["packages.hms_license"] is module
    assert module.LicenseClient.__module__ == "hms_license.client"
    assert (
        sys.modules["hms_license.client"]
        is sys.modules["packages.hms_license.client"]
    )


# -- gate orchestration ------------------------------------------------------


def test_an_ok_licence_starts_the_app_and_touches_no_screen():
    ui = FakeUi()
    assert DesktopLicenseGate(FakeClient("ok")).startup_check(ui=ui) is True
    assert ui.calls == []


def test_a_grace_licence_warns_and_still_starts_the_app():
    ui = FakeUi()
    gate = DesktopLicenseGate(FakeClient("grace", grace_days=3))

    assert gate.startup_check(ui=ui) is True
    assert ui.calls == [("banner", 3)]


def test_an_expired_licence_locks_the_app():
    ui = FakeUi()
    assert DesktopLicenseGate(FakeClient("expired")).startup_check(ui=ui) is False
    assert ui.calls == [("lock", VIETNAMESE_REASONS["expired"])]


def test_a_revoked_licence_locks_the_app():
    ui = FakeUi()
    assert DesktopLicenseGate(FakeClient("revoked")).startup_check(ui=ui) is False
    assert ui.calls == [("lock", VIETNAMESE_REASONS["revoked"])]


def test_a_missing_licence_asks_for_activation():
    ui = FakeUi()
    assert DesktopLicenseGate(FakeClient("no-license")).startup_check(ui=ui) is False
    assert ui.calls == ["activation"]


def test_a_licence_that_activates_on_the_second_check_starts_the_app():
    ui = FakeUi(activation=True)
    gate = DesktopLicenseGate(FakeClient("no-license", "ok"))

    assert gate.startup_check(ui=ui) is True
    assert ui.calls == ["activation"]


def test_an_activation_that_does_not_survive_the_recheck_refuses_the_start():
    ui = FakeUi(activation=True)
    gate = DesktopLicenseGate(FakeClient("no-license", "no-license"))

    assert gate.startup_check(ui=ui) is False
    assert ui.calls == ["activation"]


def test_a_lock_screen_that_reactivates_starts_the_app():
    ui = FakeUi(lock=True)
    assert DesktopLicenseGate(FakeClient("revoked")).startup_check(ui=ui) is True
    assert ui.calls == [("lock", VIETNAMESE_REASONS["revoked"])]


def test_the_grace_count_is_only_read_when_a_banner_will_show_it():
    client = FakeClient("ok", grace_days=4)
    DesktopLicenseGate(client).startup_check(ui=FakeUi())
    assert client.grace_reads == 0

    client = FakeClient("grace", grace_days=4)
    DesktopLicenseGate(client).startup_check(ui=FakeUi())
    assert client.grace_reads == 1


def test_a_client_that_blows_up_refuses_the_start_instead_of_crashing():
    assert DesktopLicenseGate(ExplodingClient()).startup_check(ui=FakeUi()) is False


def test_a_ui_that_blows_up_refuses_the_start_instead_of_crashing():
    class ExplodingUi:
        def activation(self):
            raise RuntimeError("no display")

        def lock(self, reason):
            raise RuntimeError("no display")

        def banner(self, grace_days):
            raise RuntimeError("no display")

    assert DesktopLicenseGate(FakeClient("expired")).startup_check(ui=ExplodingUi()) is False


# -- activation dialog -------------------------------------------------------


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        ("invalid_key", "Mã kích hoạt không đúng. Kiểm tra lại ký tự đã nhập."),
        ("devices_exceeded", "Mã kích hoạt đã dùng hết số máy cho phép."),
        ("key_revoked", "Mã kích hoạt đã bị thu hồi."),
        ("product_mismatch", "Mã kích hoạt thuộc phần mềm khác, không dùng được cho phần mềm này."),
        ("key_expired", "Mã kích hoạt đã hết hạn."),
        ("network_error", "Không kết nối được Máy chủ bản quyền. Kiểm tra mạng rồi thử lại."),
        ("rate_limited", "Không kích hoạt được. Thử lại hoặc liên hệ nhà cung cấp."),
    ],
)
def test_every_online_outcome_has_a_vietnamese_message_and_only_ok_accepts(qapp, outcome, message):
    dialog = ActivationDialog(ScriptedClient(outcome))
    dialog.key_field.setText("KEY-1234")
    dialog._activate_online()

    assert dialog.result() != ActivationDialog.DialogCode.Accepted
    assert dialog.status.text() == message


def test_an_ok_outcome_accepts_the_dialog(qapp):
    dialog = ActivationDialog(ScriptedClient("ok"))
    dialog.key_field.setText("KEY-1234")
    dialog._activate_online()

    assert dialog.result() == ActivationDialog.DialogCode.Accepted
    assert dialog.status.text() == ""


def test_an_empty_key_is_refused_before_the_server_is_asked(qapp):
    client = ScriptedClient("ok")
    dialog = ActivationDialog(client)
    dialog._activate_online()

    assert client.activated_keys == []
    assert dialog.result() != ActivationDialog.DialogCode.Accepted
    assert dialog.status.text() == "Nhập mã kích hoạt trước."


@pytest.mark.parametrize(
    ("outcome", "message"),
    [
        ("hwid-mismatch", "File license này thuộc về máy khác."),
        ("invalid-file", "File license không đọc được hoặc không đúng."),
    ],
)
def test_every_import_outcome_has_a_vietnamese_message(qapp, tmp_path, outcome, message, monkeypatch):
    client = ScriptedClient("ok")
    client.import_outcomes = [outcome]
    dialog = ActivationDialog(client)
    monkeypatch.setattr(dialog, "_ask_request_path", lambda: str(tmp_path / "a.req"))
    monkeypatch.setattr(dialog, "_confirm_request_created", lambda path: None)
    monkeypatch.setattr(dialog, "_ask_license_path", lambda: str(tmp_path / "a.lic"))

    dialog._activate_offline()

    assert dialog.result() != ActivationDialog.DialogCode.Accepted
    assert dialog.status.text() == message
    assert (tmp_path / "a.req").read_text(encoding="utf-8") == "request"


def test_a_usable_imported_file_accepts_the_dialog(qapp, tmp_path, monkeypatch):
    dialog = ActivationDialog(ScriptedClient("ok"))
    monkeypatch.setattr(dialog, "_ask_request_path", lambda: str(tmp_path / "a.req"))
    monkeypatch.setattr(dialog, "_confirm_request_created", lambda path: None)
    monkeypatch.setattr(dialog, "_ask_license_path", lambda: str(tmp_path / "a.lic"))

    dialog._activate_offline()

    assert dialog.result() == ActivationDialog.DialogCode.Accepted


def test_cancelling_the_request_picker_stops_the_offline_flow(qapp, tmp_path, monkeypatch):
    client = ScriptedClient("ok")
    dialog = ActivationDialog(client)
    monkeypatch.setattr(dialog, "_ask_request_path", lambda: "")
    asked: list[str] = []
    monkeypatch.setattr(dialog, "_ask_license_path", lambda: asked.append("asked") or "")

    dialog._activate_offline()

    assert asked == []
    assert dialog.result() != ActivationDialog.DialogCode.Accepted


# -- lock screen -------------------------------------------------------------


def test_the_lock_screen_survives_reject_and_close(qapp):
    screen = LockScreen(VIETNAMESE_REASONS["revoked"], FakeUi())

    screen.reject()
    assert screen.result() == 0
    assert screen.reactivated is False
    assert screen.quit_requested is False

    from PySide6.QtGui import QCloseEvent

    event = QCloseEvent()
    screen.closeEvent(event)
    assert event.isAccepted() is False


def test_the_quit_button_records_the_choice_without_reactivating(qapp):
    screen = LockScreen(VIETNAMESE_REASONS["expired"], FakeUi(activation=True))
    screen.quit_button.click()

    assert screen.quit_requested is True
    assert screen.reactivated is False


def test_the_reactivate_button_reports_a_successful_activation(qapp):
    screen = LockScreen(VIETNAMESE_REASONS["revoked"], FakeUi(activation=True))
    screen.reactivate_button.click()

    assert screen.reactivated is True
    assert screen.quit_requested is False


def test_the_reactivate_button_stays_shut_when_activation_fails(qapp):
    screen = LockScreen(VIETNAMESE_REASONS["revoked"], FakeUi(activation=False))
    screen.reactivate_button.click()

    assert screen.reactivated is False
    assert screen.result() == 0


def test_the_lock_screen_has_no_close_button(qapp):
    screen = LockScreen(VIETNAMESE_REASONS["revoked"], FakeUi())
    from PySide6.QtCore import Qt

    assert screen.windowFlags() & Qt.WindowType.WindowCloseButtonHint == Qt.WindowType(0)


# -- grace banner ------------------------------------------------------------


@pytest.mark.parametrize(
    ("days", "text"),
    [
        (0, "Bản quyền đã hết hạn. Gia hạn ngay để tránh bị khóa."),
        (1, "Bản quyền đã hết hạn, còn 1 ngày."),
        (3, "Bản quyền đã hết hạn, còn 3 ngày."),
        (None, "Bản quyền đã hết hạn. Hãy gia hạn để tránh bị khóa."),
    ],
)
def test_the_grace_banner_renders_zero_one_and_many_days(qapp, days, text):
    from PySide6.QtCore import Qt

    banner = GraceBanner(days)

    assert banner.text() == text
    assert banner.windowModality() == Qt.WindowModality.NonModal


# -- QtLicenseUi -------------------------------------------------------------


def test_the_ui_reports_a_missing_client_instead_of_raising(qapp):
    reported: list[str] = []
    ui = QtLicenseUi(None, error_view=lambda *args: reported.append(args[-1]))

    assert ui.activation() is False
    assert ui.lock("reason") is False
    assert reported == [
        "Hệ thống bản quyền chưa được cài đặt. Liên hệ nhà cung cấp.",
        "Hệ thống bản quyền chưa được cài đặt. Liên hệ nhà cung cấp.",
    ]


def test_the_ui_reuses_one_banner(qapp):
    ui = QtLicenseUi(ScriptedClient("ok"))
    ui.banner(3)
    first = ui._banner
    ui.banner(1)

    assert ui._banner is first
    assert first.text() == "Bản quyền đã hết hạn, còn 1 ngày."


# -- enforcement -------------------------------------------------------------


def test_a_locked_licence_never_reaches_the_main_window(qapp, monkeypatch, public_pem):
    reached: list[object] = []
    monkeypatch.setattr(desktop_main, "desktop_server_url", lambda **kwargs: reached.append("server"))
    monkeypatch.setattr(desktop_main, "run", lambda *args, **kwargs: reached.append("run"))
    monkeypatch.setattr(desktop_main, "build_client", lambda env: FakeClient("revoked"))
    ui = FakeUi(lock=False)

    allowed = desktop_main._license_gate_allows_start(
        active_env(public_pem), ui_factory=lambda client: ui
    )

    assert allowed is False
    assert ui.calls == [("lock", VIETNAMESE_REASONS["revoked"])]
    assert reached == []
    assert [widget for widget in qapp.topLevelWidgets() if widget.isVisible()] == []


def test_a_refused_launch_builds_no_window_and_calls_nothing(qapp, monkeypatch, public_pem):
    reached: list[object] = []
    monkeypatch.setattr(desktop_main, "build_client", lambda env: FakeClient("revoked"))
    monkeypatch.setattr(desktop_main, "run", lambda *a, **k: reached.append("run"))
    monkeypatch.setattr(
        desktop_main, "desktop_server_url", lambda **k: reached.append("server")
    )
    monkeypatch.setattr(
        desktop_main, "ProductApiClient", lambda *a, **k: reached.append("client")
    )
    ui = FakeUi(lock=False)

    assert desktop_main._license_gate_allows_start(
        active_env(public_pem), ui_factory=lambda client: ui
    ) is False
    assert ui.calls == [("lock", VIETNAMESE_REASONS["revoked"])]
    assert reached == []
    assert [widget for widget in qapp.topLevelWidgets() if widget.isVisible()] == []


def test_a_running_licence_is_allowed_through(qapp, monkeypatch, public_pem):
    monkeypatch.setattr(desktop_main, "build_client", lambda env: FakeClient("ok"))
    ui = FakeUi()

    assert desktop_main._license_gate_allows_start(
        active_env(public_pem), ui_factory=lambda client: ui
    ) is True
    assert ui.calls == []


def test_the_gate_runs_before_the_app_contacts_a_server():
    source = (SOURCE_ROOT / "apps" / "desktop" / "__main__.py").read_text(encoding="utf-8")
    gate = source.index("if not _license_gate_allows_start():")
    server = source.index("desktop_server_url(configured_url=")
    assert gate < server, "the licence gate must run before the server is contacted"
