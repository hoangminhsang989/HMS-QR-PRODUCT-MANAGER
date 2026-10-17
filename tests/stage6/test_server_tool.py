import hashlib
import os
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path
from unittest.mock import Mock, patch

import pytest
from PySide6.QtWidgets import QMessageBox

import apps.server.tool as server_tool
from apps.server.tool import AUTO_START_TASK_NAME, MAX_ACTIVITY_LOG_LINES, POSTGRESQL_DATA_ROOT, POSTGRESQL_INSTALLER_SHA256, active_lan_network_status, backup_freshness, backup_integrity_details, backup_integrity_inventory, backup_inventory, backup_sqlite, check_sqlite_backup, create_production_secrets, current_user_autostart_command, current_user_autostart_exists, disk_space_status, external_hms_server_pid_command, firewall_private_status, generate_admin_password, lan_listener_status, lan_readiness_assessment, lan_readiness_checklist, latest_postgresql_backup, latest_sqlite_backup, load_server_secret, load_tool_settings, locations_are_saved, operational_readiness_report, postgresql_backup_inventory, postgresql_backup_path, postgresql_restore_command, postgresql_unattended_command, postgresql_unattended_options, production_database_file, production_database_mode, production_database_url, production_paths, production_postgresql_is_installed, production_setup_requirements, repair_private_lan_command, restore_sqlite_database, run_postgresql_offline_installer, save_autostart_preference, save_server_secret, save_tool_settings, set_current_user_autostart, verified_postgresql_offline_installer


def test_direct_module_launch_requests_admin_and_does_not_start_window_when_not_elevated(monkeypatch):
    launch = Mock(return_value=True)
    monkeypatch.setattr(server_tool, "is_running_as_admin", lambda: False)
    monkeypatch.setattr(server_tool, "request_admin_restart", launch)
    run = Mock()

    assert server_tool.start_with_admin(run) is False
    launch.assert_called_once_with()
    run.assert_not_called()


def test_direct_module_launch_runs_application_when_already_elevated(monkeypatch):
    monkeypatch.setattr(server_tool, "is_running_as_admin", lambda: True)
    launch = Mock()
    run = Mock()

    assert server_tool.start_with_admin(run) is True
    launch.assert_not_called()
    run.assert_called_once_with()


def test_server_tool_persists_separate_writable_data_and_backup_roots(tmp_path):
    settings = tmp_path / "settings.json"
    data_root = tmp_path / "runtime"
    backup_root = tmp_path / "backups"

    save_tool_settings(str(data_root), str(backup_root), settings)

    assert load_tool_settings(settings) == {
        "data_root": str(data_root.resolve()),
        "backup_root": str(backup_root.resolve()),
        "start_server_with_windows": True,
    }
    with pytest.raises(ValueError, match="tách biệt"):
        save_tool_settings(str(data_root), str(data_root), settings)


def test_tool_settings_default_windows_autostart_to_enabled_and_persist_opt_out(tmp_path):
    settings_path = tmp_path / "server-tool-settings.json"
    settings_path.write_text('{"data_root":"C:/data","backup_root":"C:/backups"}', encoding="utf-8")

    settings = load_tool_settings(settings_path)
    assert settings["start_server_with_windows"] is True

    save_tool_settings(
        settings["data_root"], settings["backup_root"], settings_path,
        start_server_with_windows=False,
    )

    assert load_tool_settings(settings_path)["start_server_with_windows"] is False


@pytest.mark.parametrize("enabled", [True, False])
def test_set_current_user_autostart_creates_or_deletes_logon_task(enabled, tmp_path):
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0)) as run:
        set_current_user_autostart(enabled, tmp_path)

    command = run.call_args.args[0]
    if enabled:
        assert command == current_user_autostart_command(tmp_path)
    else:
        assert command == ["schtasks.exe", "/Delete", "/TN", AUTO_START_TASK_NAME, "/F"]


def test_set_current_user_autostart_reports_task_scheduler_failure(tmp_path):
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=1, stderr="denied")):
        with pytest.raises(RuntimeError, match="tự khởi động"):
            set_current_user_autostart(True, tmp_path)


def test_server_tool_main_window_exposes_autostart_and_four_function_popups(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    settings_path = tmp_path / "settings.json"
    with patch("apps.server.tool.SETTINGS_PATH", settings_path), patch("apps.server.tool.ServerToolWindow.refresh_status"):
        window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)

    assert window.start_button.text() == "KHỞI ĐỘNG SERVER"
    assert window.stop_button.text() == "DỪNG SERVER CỦA TOOL"
    assert window.start_with_windows_checkbox.isChecked()
    assert window.start_with_windows_checkbox.window() is window
    assert not hasattr(window, "autostart_button")
    assert len(window.popup_buttons) == 4
    assert {popup.windowTitle() for popup in window._popups.values()} == {
        "Mạng & cài đặt", "Dữ liệu & sao lưu", "Tài khoản", "Nhật ký & kiểm tra",
    }
    for button, title in (
        (window.popup_buttons[0], "Mạng & cài đặt"),
        (window.popup_buttons[1], "Dữ liệu & sao lưu"),
        (window.popup_buttons[2], "Tài khoản"),
        (window.popup_buttons[3], "Nhật ký & kiểm tra"),
    ):
        button.click()
        assert window._popups[title].isVisible()
        window._popups[title].hide()
    assert window.firewall_button.window() is window._popups["Mạng & cài đặt"]
    assert window.backup_button.window() is window._popups["Dữ liệu & sao lưu"]
    assert window.login_button.window() is window._popups["Tài khoản"]
    assert window.details.window() is window._popups["Nhật ký & kiểm tra"]
    assert window.apply_ip_button.window() is window._popups["Mạng & cài đặt"]
    assert window.setup_production_button.window() is window._popups["Mạng & cài đặt"]
    assert window.restore_button.window() is window._popups["Dữ liệu & sao lưu"]
    assert window.check_space_button.window() is window._popups["Dữ liệu & sao lưu"]
    assert window.accounts_table.window() is window._popups["Tài khoản"]
    assert window.rename_account_button.window() is window._popups["Tài khoản"]
    assert window.copy_log_button.window() is window._popups["Nhật ký & kiểm tra"]
    assert window.refresh_button.window() is window._popups["Nhật ký & kiểm tra"]


def test_server_tool_autostart_checkbox_updates_task_and_saved_preference(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    settings_path = tmp_path / "settings.json"
    with patch("apps.server.tool.SETTINGS_PATH", settings_path), patch("apps.server.tool.ServerToolWindow.refresh_status"), patch("apps.server.tool.set_current_user_autostart") as set_task:
        window = ServerToolWindow()
        window._timer.stop()
        qtbot.addWidget(window)
        window.start_with_windows_checkbox.setChecked(False)
        assert not window.start_with_windows_checkbox.isChecked()
        set_task.assert_called_once_with(False)
        assert load_tool_settings(settings_path)["start_server_with_windows"] is False


def test_server_tool_autostart_failure_restores_checkbox_and_preference(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    settings_path = tmp_path / "settings.json"
    with patch("apps.server.tool.SETTINGS_PATH", settings_path), patch("apps.server.tool.ServerToolWindow.refresh_status"), patch("apps.server.tool.set_current_user_autostart", side_effect=RuntimeError("scheduler failed")), patch("apps.server.tool.QMessageBox.critical"):
        window = ServerToolWindow()
        window._timer.stop()
        qtbot.addWidget(window)
        window.start_with_windows_checkbox.blockSignals(True)
        window.start_with_windows_checkbox.setChecked(False)
        window.start_with_windows_checkbox.blockSignals(False)
        window.update_autostart_preference(False)
        assert window.start_with_windows_checkbox.isChecked()
        assert load_tool_settings(settings_path)["start_server_with_windows"] is True


def test_locations_are_saved_uses_normalized_paths(tmp_path):
    settings = {"data_root": str(tmp_path / "runtime"), "backup_root": str(tmp_path / "backups")}
    assert locations_are_saved(str(tmp_path / "runtime" / ".." / "runtime"), str(tmp_path / "backups"), settings)
    assert not locations_are_saved(str(tmp_path / "other"), str(tmp_path / "backups"), settings)


def test_production_paths_keep_machine_one_storage_and_backups_local(tmp_path):
    paths = production_paths(tmp_path / "HMS-QR-PROD")

    assert paths["storage"] == tmp_path / "HMS-QR-PROD" / "storage"
    assert paths["backups"] == tmp_path / "HMS-QR-PROD" / "backups"
    assert paths["logs"] == tmp_path / "HMS-QR-PROD" / "logs"


def test_production_storage_and_backups_are_valid_separate_tool_roots(tmp_path):
    paths = production_paths(tmp_path / "HMS-QR-PROD")

    save_tool_settings(str(paths["storage"]), str(paths["backups"]), tmp_path / "settings.json")


def test_postgresql_unattended_command_uses_local_paths_without_network():
    option_file = Path("C:/runtime/postgresql-install-options.conf")
    command = postgresql_unattended_command(Path("C:/release/postgresql.exe"), option_file)

    assert Path(command[0]) == Path("C:/release/postgresql.exe")
    assert command[1:] == ["--optionfile", str(option_file)]
    options = postgresql_unattended_options(data_root=POSTGRESQL_DATA_ROOT, superpassword="secret")
    assert "mode=unattended" in options
    assert f"datadir={POSTGRESQL_DATA_ROOT}" in options
    assert "serverport=5432" in options
    assert "secret" in options


def test_postgresql_installer_removes_temporary_secret_option_file(tmp_path):
    option_file = tmp_path / "postgresql-install-options.conf"
    installer = tmp_path / "postgresql.exe"
    with patch("apps.server.tool.restrict_option_file_to_current_user") as restrict, patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0)):
        result = run_postgresql_offline_installer(installer, option_file, "superpassword=secret\n")

    assert result.returncode == 0
    restrict.assert_called_once_with(option_file)
    assert not option_file.exists()


def test_provisioning_skips_postgresql_restart_when_already_local_only():
    from apps.server.tool import ServerToolWindow

    responses = iter((
        Mock(returncode=0),
        Mock(returncode=0, stdout="1\n"),
        Mock(returncode=0, stdout="127.0.0.1\n"),
    ))
    tool = ServerToolWindow.__new__(ServerToolWindow)
    with patch.object(Path, "is_file", return_value=True), patch("apps.server.tool.load_server_secret", return_value="secret"), patch("apps.server.tool.subprocess.run", side_effect=lambda *_args, **_kwargs: next(responses)) as run:
        tool._provision_production_database(Path("C:/PostgreSQL/bin/psql.exe"))

    assert not any(call.args[0][0] == "powershell" for call in run.call_args_list)


def test_production_setup_requires_bundled_python_and_wheels_only(tmp_path):
    source = tmp_path / "release"
    (source / "installer" / "python").mkdir(parents=True)
    (source / "installer" / "wheels").mkdir()
    (source / "installer" / "postgresql").mkdir()

    missing = production_setup_requirements(source)

    assert "Python offline installer" in missing
    assert "Python offline wheels" in missing
    assert missing == ["Python offline installer", "Python offline wheels"]


def test_production_database_url_defaults_to_standalone_sqlite(tmp_path):
    secrets = tmp_path / "server-tool-secrets.json"

    assert production_database_mode(secrets) == "standalone"
    assert production_database_file(tmp_path) == tmp_path / "database" / "hms_qr.sqlite"
    url = production_database_url(tmp_path, secrets)
    assert url == f"sqlite:///{(tmp_path / 'database' / 'hms_qr.sqlite').as_posix()}"


def test_production_database_url_uses_postgresql_only_when_mode_selected(tmp_path):
    secrets = tmp_path / "server-tool-secrets.json"
    save_server_secret("database_mode", "postgresql", secrets)
    save_server_secret("database_password", "app-secret", secrets)

    assert production_database_mode(secrets) == "postgresql"
    url = production_database_url(tmp_path, secrets)
    assert url.startswith("postgresql+psycopg://hms_qr_app:app-secret@127.0.0.1:5432/hms_qr")


def test_postgresql_backup_helpers_use_distinct_custom_dump_files(tmp_path):
    first = postgresql_backup_path(tmp_path, now=datetime(2026, 9, 20, 9, 30, 0, 1))
    second = postgresql_backup_path(tmp_path, now=datetime(2026, 9, 20, 9, 30, 0, 2))
    first.write_bytes(b"one")
    second.write_bytes(b"two")

    assert first.suffix == ".dump"
    assert first != second
    assert latest_postgresql_backup(tmp_path) == second
    assert postgresql_backup_inventory(tmp_path) == "2 file (0.0 MB)"


def test_postgresql_restore_and_autostart_commands_do_not_contain_secrets(tmp_path):
    restore = postgresql_restore_command(tmp_path / "hms_qr_verified.dump")
    autostart = current_user_autostart_command(tmp_path)
    assert "--clean" in restore and "--exit-on-error" in restore
    assert str(tmp_path / "hms_qr_verified.dump") in restore
    assert autostart[:3] == ["schtasks.exe", "/Create", "/TN"]
    assert AUTO_START_TASK_NAME in autostart
    assert "production_launcher" in " ".join(autostart)
    assert "password" not in " ".join(autostart).lower()


def test_server_tool_creates_readable_sqlite_backup(tmp_path):
    database = tmp_path / "runtime" / "hms_qr_test.sqlite"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample (name TEXT)")
        connection.execute("INSERT INTO sample VALUES ('verified')")

    backup = backup_sqlite(database, tmp_path / "backups")

    with sqlite3.connect(backup) as connection:
        assert connection.execute("SELECT name FROM sample").fetchone() == ("verified",)
    assert latest_sqlite_backup(tmp_path / "backups") == backup
    assert latest_sqlite_backup(tmp_path / "empty-backups") is None
    assert check_sqlite_backup(backup) == f"BACKUP HỢP LỆ: {backup.name}"
    with pytest.raises(ValueError, match="Không tìm thấy"):
        check_sqlite_backup(tmp_path / "missing.sqlite")


def test_rapid_sqlite_backups_do_not_overwrite_each_other(tmp_path):
    database = tmp_path / "runtime" / "hms_qr_test.sqlite"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE sample (name TEXT)")
    first = backup_sqlite(database, tmp_path / "backups")
    second = backup_sqlite(database, tmp_path / "backups")
    assert first != second
    assert first.is_file()
    assert second.is_file()


def test_restore_sqlite_database_keeps_safety_snapshot_and_replaces_runtime(tmp_path):
    database = tmp_path / "runtime" / "hms_qr_test.sqlite"
    database.parent.mkdir()
    connection = sqlite3.connect(database)
    try:
        connection.execute("CREATE TABLE sample (value TEXT)")
        connection.execute("INSERT INTO sample VALUES ('current')")
        connection.commit()
    finally:
        connection.close()
    backup_root = tmp_path / "backups"
    source_backup = backup_sqlite(database, backup_root)
    connection = sqlite3.connect(database)
    try:
        connection.execute("UPDATE sample SET value = 'changed'")
        connection.commit()
    finally:
        connection.close()

    safety = restore_sqlite_database(database, source_backup, backup_root)

    connection = sqlite3.connect(database)
    try:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("current",)
    finally:
        connection.close()
    connection = sqlite3.connect(safety)
    try:
        assert connection.execute("SELECT value FROM sample").fetchone() == ("changed",)
    finally:
        connection.close()


def test_restore_refuses_an_external_running_server(qtbot):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    with patch("apps.server.tool.production_postgresql_is_installed", return_value=False), patch.object(window, "_server_listening", return_value=True), patch("apps.server.tool.QMessageBox.warning") as warning:
        window.restore_database()
    assert warning.call_args.args[1] == "Không thể khôi phục"


def test_restore_uses_postgresql_workflow_when_production_postgresql_is_installed(qtbot):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    with patch("apps.server.tool.production_postgresql_is_installed", return_value=True), patch.object(window, "restore_postgresql_database") as restore:
        window.restore_database()
    restore.assert_called_once_with()


def test_backup_freshness_reports_missing_recent_and_stale_backups(tmp_path):
    backup = tmp_path / "hms_qr_20260919_220000.sqlite"
    backup.touch()
    now = datetime(2026, 9, 19, 23, 0, 0)
    os.utime(backup, (now.timestamp(), now.timestamp()))
    assert backup_freshness(None, now=now) == "CHƯA CÓ BACKUP"
    assert backup_freshness(backup, now=now) == "MỚI (0 giờ)"
    os.utime(backup, ((now - timedelta(hours=25)).timestamp(),) * 2)
    assert backup_freshness(backup, now=now) == "QUÁ 24 GIỜ (25 giờ)"


def test_backup_inventory_counts_only_hms_qr_snapshots(tmp_path):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    (backup_root / "hms_qr_one.sqlite").write_bytes(b"a" * 1024**2)
    (backup_root / "hms_qr_two.sqlite").write_bytes(b"b" * 512 * 1024)
    (backup_root / "other.sqlite").write_bytes(b"ignored")
    assert backup_inventory(backup_root) == "2 file (1.5 MB)"


def test_backup_integrity_inventory_reports_valid_and_invalid_snapshots(tmp_path):
    backup_root = tmp_path / "backups"
    backup_root.mkdir()
    valid_source = tmp_path / "source.sqlite"
    with sqlite3.connect(valid_source) as connection:
        connection.execute("CREATE TABLE sample (value TEXT)")
    backup_sqlite(valid_source, backup_root)
    (backup_root / "hms_qr_broken.sqlite").write_text("not a database", encoding="ascii")
    assert backup_integrity_inventory(backup_root) == "1 hợp lệ, 1 lỗi"
    assert backup_integrity_details(backup_root) == ("1 hợp lệ, 1 lỗi", ["hms_qr_broken.sqlite"])


def test_disk_space_status_classifies_free_space_without_writing(tmp_path):
    usage = Mock(free=10 * 1024**3)
    with patch("apps.server.tool.shutil.disk_usage", return_value=usage):
        assert disk_space_status(tmp_path) == "ĐỦ DUNG LƯỢNG (10.0 GB trống)"
    with patch("apps.server.tool.shutil.disk_usage", return_value=Mock(free=2 * 1024**3)):
        assert disk_space_status(tmp_path) == "SẮP ĐẦY (2.0 GB trống)"
    with patch("apps.server.tool.shutil.disk_usage", return_value=Mock(free=512 * 1024**2)):
        assert disk_space_status(tmp_path) == "GẦN HẾT (0.5 GB trống)"


def test_backup_creation_verifies_the_new_file(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    database = tmp_path / "runtime" / "hms_qr_test.sqlite"
    database.parent.mkdir()
    with sqlite3.connect(database) as connection:
        connection.execute("CREATE TABLE verified_backup (value TEXT)")
    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    window._settings = {"data_root": str(database.parent), "backup_root": str(tmp_path / "backups")}
    with patch("apps.server.tool.POSTGRESQL_INSTALL_ROOT", tmp_path / "no-postgresql"), patch("apps.server.tool.QMessageBox.information") as information:
        window.backup_database()
    assert "BACKUP HỢP LỆ" in window.details.toPlainText()
    assert window.overview_backup.text().endswith(".sqlite")
    assert information.call_args.args[1] == "Sao lưu đã xác minh"


def test_postgresql_backup_is_verified_before_success_is_reported(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    window._settings = {"data_root": str(tmp_path / "runtime"), "backup_root": str(tmp_path / "backups")}
    dump = tmp_path / "backups" / "hms_qr_20260920_094000_000001.dump"

    def run(command, **_kwargs):
        if "pg_dump.exe" in command[0]:
            dump.parent.mkdir()
            dump.write_bytes(b"postgresql dump")
        return Mock(returncode=0)

    with patch("apps.server.tool.POSTGRESQL_INSTALL_ROOT", tmp_path / "postgresql"), patch.object(Path, "is_file", return_value=True), patch("apps.server.tool.load_server_secret", return_value="secret"), patch("apps.server.tool.postgresql_backup_path", return_value=dump), patch("apps.server.tool.subprocess.run", side_effect=run), patch("apps.server.tool.QMessageBox.information") as information:
        window.backup_database()
    assert window.overview_backup.text() == dump.name
    assert information.call_args.args[1] == "Sao lưu đã xác minh"


def test_setup_progress_updates_visible_status(qtbot):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    window._set_setup_progress(3, "3/7 Đang cài PostgreSQL 17 offline...")

    assert window.setup_progress.value() == 3
    assert window.setup_progress.format() == "3/7 Đang cài PostgreSQL 17 offline..."
    assert window.status_label.text() == "3/7 Đang cài PostgreSQL 17 offline..."


def test_setup_failure_activity_does_not_expose_exception_message(qtbot):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    window._set_setup_progress(2, "2/7 Bảo vệ bí mật Server bằng Windows DPAPI...")
    window.append_activity(f"THIẾT LẬP LỖI Ở {window.setup_progress.value()}/7: RuntimeError")
    assert "2/7: RuntimeError" in window.details.toPlainText()
    assert "secret-value" not in window.details.toPlainText()


def test_server_tool_uses_compact_overview_layout(qtbot):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)

    assert window.width() == 1060
    assert window.accounts_table.height() == 92
    assert window.details.height() == 72


def test_server_tool_reports_private_firewall_rule_without_changing_it():
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0, stdout="ĐÃ MỞ PRIVATE\n")) as run:
        assert firewall_private_status() == "ĐÃ MỞ PRIVATE"
    assert "Get-NetFirewallRule" in run.call_args.args[0][3]
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=1, stdout="")):
        assert firewall_private_status() == "KHÔNG KIỂM TRA ĐƯỢC"


def test_lan_profile_diagnostic_and_repair_target_only_default_gateway_adapter():
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0, stdout="PUBLIC\n")) as run:
        assert active_lan_network_status() == "PUBLIC"
    assert "IPv4DefaultGateway" in run.call_args.args[0][3]
    command = repair_private_lan_command()
    assert "IPv4DefaultGateway" in command
    assert "Set-NetConnectionProfile" in command
    assert "NetworkCategory Private" in command
    assert "UDP -LocalPort 8011" in command
    assert "TCP -LocalPort 8010" in command


def test_external_server_restart_detection_targets_only_hms_qr_uvicorn_on_8010():
    command = external_hms_server_pid_command()
    assert "Name = 'python.exe'" in command
    assert "apps\\.server\\.app:app" in command
    assert "--port\\s+8010" in command


def test_postgresql_offline_installer_requires_the_verified_bundle(tmp_path, monkeypatch):
    installer = tmp_path / "postgresql.exe"
    installer.write_bytes(b"verified PostgreSQL fixture")
    monkeypatch.setattr("apps.server.tool.POSTGRESQL_INSTALLER_SHA256", hashlib.sha256(installer.read_bytes()).hexdigest())
    assert verified_postgresql_offline_installer(installer) == installer
    installer.write_bytes(b"altered")
    with pytest.raises(ValueError, match="checksum"):
        verified_postgresql_offline_installer(installer)
    with pytest.raises(ValueError, match="Không tìm thấy"):
        verified_postgresql_offline_installer(tmp_path / "missing.exe")


def test_server_secrets_use_dpapi_protected_storage_without_plaintext(tmp_path, monkeypatch):
    secrets_path = tmp_path / "server-tool-secrets.json"
    protected = "DPAPI-BLOB"
    with patch("apps.server.tool._dpapi", side_effect=[protected, "admin-password"]):
        save_server_secret("hms_qr_admin_password", "admin-password", secrets_path)
        assert load_server_secret("hms_qr_admin_password", secrets_path) == "admin-password"
    assert "admin-password" not in secrets_path.read_text(encoding="utf-8")
    assert "DPAPI-BLOB" in secrets_path.read_text(encoding="utf-8")
    assert generate_admin_password() == "admin"


def test_reveal_saved_admin_password_uses_production_secret_name(qtbot):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    with patch("apps.server.tool._is_windows_admin", return_value=True), patch("apps.server.tool.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes), patch("apps.server.tool.load_server_secret", return_value="saved-password") as load, patch("apps.server.tool.QMessageBox.information"):
        window.reveal_saved_admin_password()

    load.assert_called_once_with("admin_password")


def test_dpapi_script_loads_windows_security_assembly():
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0, stdout="DPAPI-BLOB")) as run:
        from apps.server.tool import _dpapi
        assert _dpapi("value", unprotect=False) == "DPAPI-BLOB"
    assert "Add-Type -AssemblyName System.Security" in run.call_args.args[0][3]


def test_production_secret_creation_is_idempotent_and_never_writes_plaintext(tmp_path):
    secrets_path = tmp_path / "server-tool-secrets.json"
    protected = iter(("mode-blob", "postgres-blob", "database-blob", "auth-blob", "admin-blob"))
    with patch("apps.server.tool._dpapi", side_effect=lambda value, **_kwargs: next(protected)):
        create_production_secrets(secrets_path)
    first = secrets_path.read_text(encoding="utf-8")
    with patch("apps.server.tool._dpapi") as dpapi:
        create_production_secrets(secrets_path)
    assert dpapi.call_count == 0
    assert set(__import__("json").loads(first)) == {"database_mode", "postgres_password", "database_password", "auth_secret", "admin_password"}
    assert "standalone" not in first


def test_server_tool_classifies_tcp_listener_for_lan_readiness():
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0, stdout="  TCP    0.0.0.0:8010           0.0.0.0:0              LISTENING       1234")):
        assert lan_listener_status() == "SẴN SÀNG LAN"
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0, stdout="  TCP    127.0.0.1:8010         0.0.0.0:0              LISTENING       1234")):
        assert lan_listener_status() == "CHỈ LOCALHOST"
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0, stdout="")):
        assert lan_listener_status() == "CHƯA LẮNG NGHE"


def test_operational_readiness_report_is_sanitized(tmp_path):
    settings = {"data_root": str(tmp_path / "runtime-secret"), "backup_root": str(tmp_path / "backups-secret")}
    with patch("apps.server.tool.lan_listener_status", return_value="SẴN SÀNG LAN"), patch("apps.server.tool.firewall_private_status", return_value="ĐÃ MỞ PRIVATE"), patch("apps.server.tool.ServerToolWindow._lan_address", return_value="http://192.168.1.50:8010"):
        report = operational_readiness_report(settings)
    assert "SẴN SÀNG LAN" in report
    assert "ĐÃ MỞ PRIVATE" in report
    assert "runtime-secret" not in report
    assert "backups-secret" not in report
    assert "password" not in report.casefold()
    assert "token" not in report.casefold()


def test_lan_readiness_assessment_lists_only_missing_conditions():
    assert lan_readiness_assessment(True, "SẴN SÀNG LAN", "ĐÃ MỞ PRIVATE") == "SẴN SÀNG LAN"
    assessment = lan_readiness_assessment(False, "CHỈ LOCALHOST", "CHƯA MỞ")
    assert "SERVER/DATABASE" in assessment
    assert "TCP 8010: CHỈ LOCALHOST" in assessment
    assert "FIREWALL: CHƯA MỞ" in assessment


def test_lan_readiness_checklist_gives_operator_specific_next_actions():
    checklist = lan_readiness_checklist(False, "CHỈ LOCALHOST", "CHƯA MỞ")
    assert checklist[0].startswith("CẦN XỬ LÝ Server/database")
    assert "bind 0.0.0.0" in checklist[1]
    assert "Administrator" in checklist[2]


def test_account_filters_hide_nonmatching_rows(qtbot):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    window.accounts_table.setRowCount(2)
    for row, values in enumerate((("admin", "ADMIN", "ĐANG HOẠT ĐỘNG", "id-admin"), ("editor", "EDITOR", "ĐÃ TẮT", "id-editor"))):
        for column, value in enumerate(values):
            window.accounts_table.setItem(row, column, __import__("PySide6.QtWidgets", fromlist=["QTableWidgetItem"]).QTableWidgetItem(value))
    window.account_role_filter.setCurrentText("EDITOR")
    assert window.accounts_table.isRowHidden(0)
    assert not window.accounts_table.isRowHidden(1)
    window.account_filter.setText("admin")
    assert window.accounts_table.isRowHidden(1)


def test_activity_history_is_timestamped_and_bounded(qtbot):
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    for index in range(MAX_ACTIVITY_LOG_LINES + 5):
        window.append_activity(f"event-{index}")
    lines = window.details.toPlainText().splitlines()
    assert len(lines) == MAX_ACTIVITY_LOG_LINES
    assert lines[0].endswith("event-5")
    assert lines[-1].endswith(f"event-{MAX_ACTIVITY_LOG_LINES + 4}")
    assert lines[-1].startswith("[")


def test_clearing_activity_log_only_clears_the_display(qtbot):
    from PySide6.QtWidgets import QMessageBox
    from apps.server.tool import ServerToolWindow

    window = ServerToolWindow()
    window._timer.stop()
    qtbot.addWidget(window)
    window.append_activity("before-clear")
    with patch("apps.server.tool.QMessageBox.question", return_value=QMessageBox.StandardButton.Yes):
        window.clear_activity_log()
    assert window.details.toPlainText() == ""
    assert window.status_label.text() == "Đã xóa nhật ký hiển thị trong Tool."


def test_current_user_autostart_exists_queries_task_scheduler():
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=0)) as run:
        assert current_user_autostart_exists() is True
    assert run.call_args.args[0][:3] == ["schtasks.exe", "/Query", "/TN"]
    assert AUTO_START_TASK_NAME in run.call_args.args[0]
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=1)):
        assert current_user_autostart_exists() is False


def test_set_current_user_autostart_disable_is_idempotent_when_task_missing(tmp_path):
    with patch("apps.server.tool.subprocess.run", return_value=Mock(returncode=1)) as run:
        set_current_user_autostart(False, tmp_path)
    assert run.call_count == 1
    assert run.call_args.args[0][:3] == ["schtasks.exe", "/Query", "/TN"]


def test_autostart_command_quotes_release_root_for_spaces(tmp_path):
    root = tmp_path / "HMS QR Release"
    command = current_user_autostart_command(root)
    task_run = command[command.index("/TR") + 1]
    assert f'cd /d "{root}"' in task_run


def test_tool_settings_fall_back_to_defaults_for_non_object_json(tmp_path):
    settings_path = tmp_path / "settings.json"
    settings_path.write_text("[]", encoding="utf-8")
    assert load_tool_settings(settings_path)["start_server_with_windows"] is True


def test_save_autostart_preference_preserves_roots_and_flag(tmp_path):
    settings_path = tmp_path / "settings.json"
    save_tool_settings(str(tmp_path / "data"), str(tmp_path / "backups"), settings_path, start_server_with_windows=True)
    save_autostart_preference(False, settings_path)
    settings = load_tool_settings(settings_path)
    assert settings["start_server_with_windows"] is False
    assert settings["data_root"] == str((tmp_path / "data").resolve())
    assert settings["backup_root"] == str((tmp_path / "backups").resolve())


def test_autostart_reconciliation_creates_missing_task_for_default_preference(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    settings_path = tmp_path / "settings.json"
    with patch("apps.server.tool.SETTINGS_PATH", settings_path), patch("apps.server.tool.ServerToolWindow.refresh_status"), patch("apps.server.tool.current_user_autostart_exists", return_value=False), patch("apps.server.tool.set_current_user_autostart") as set_task:
        window = ServerToolWindow()
        window._timer.stop()
        qtbot.addWidget(window)
        window._reconcile_autostart_task()
    set_task.assert_called_once_with(True)
    assert window.start_with_windows_checkbox.isChecked()


def test_autostart_reconciliation_deletes_task_when_preference_disabled(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    settings_path = tmp_path / "settings.json"
    save_tool_settings(str(tmp_path / "data"), str(tmp_path / "backups"), settings_path, start_server_with_windows=False)
    with patch("apps.server.tool.SETTINGS_PATH", settings_path), patch("apps.server.tool.ServerToolWindow.refresh_status"), patch("apps.server.tool.current_user_autostart_exists", return_value=True), patch("apps.server.tool.set_current_user_autostart") as set_task:
        window = ServerToolWindow()
        window._timer.stop()
        qtbot.addWidget(window)
        window._reconcile_autostart_task()
    set_task.assert_called_once_with(False)
    assert not window.start_with_windows_checkbox.isChecked()


def test_autostart_reconciliation_reports_failure_without_crashing(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    settings_path = tmp_path / "settings.json"
    with patch("apps.server.tool.SETTINGS_PATH", settings_path), patch("apps.server.tool.ServerToolWindow.refresh_status"), patch("apps.server.tool.current_user_autostart_exists", side_effect=RuntimeError("scheduler down")):
        window = ServerToolWindow()
        window._timer.stop()
        qtbot.addWidget(window)
        window._reconcile_autostart_task()
    assert window.start_with_windows_checkbox.isChecked()
    assert "Không đồng bộ được tác vụ" in window.details.toPlainText()


def test_server_tool_popups_are_non_modal_and_close_with_parent(qtbot, tmp_path):
    from PySide6.QtCore import Qt
    from apps.server.tool import ServerToolWindow

    settings_path = tmp_path / "settings.json"
    with patch("apps.server.tool.SETTINGS_PATH", settings_path), patch("apps.server.tool.ServerToolWindow.refresh_status"), patch("apps.server.tool.current_user_autostart_exists", return_value=True), patch("apps.server.tool.set_current_user_autostart"):
        window = ServerToolWindow()
        window._timer.stop()
        qtbot.addWidget(window)
        window.show()
        for popup in window._popups.values():
            assert popup.windowModality() == Qt.NonModal
            popup.show()
            assert popup.isVisible()
        window.close()
        assert not any(popup.isVisible() for popup in window._popups.values())


def test_server_tool_autostart_save_failure_rolls_back_task(qtbot, tmp_path):
    from apps.server.tool import ServerToolWindow

    settings_path = tmp_path / "settings.json"
    calls = []

    def fake_set_task(enabled, source_root=None):
        calls.append(enabled)

    with patch("apps.server.tool.SETTINGS_PATH", settings_path), patch("apps.server.tool.ServerToolWindow.refresh_status"), patch("apps.server.tool.set_current_user_autostart", side_effect=fake_set_task), patch("apps.server.tool.save_autostart_preference", side_effect=OSError("disk full")), patch("apps.server.tool.QMessageBox.critical"):
        window = ServerToolWindow()
        window._timer.stop()
        qtbot.addWidget(window)
        window.start_with_windows_checkbox.setChecked(False)
    assert calls == [False, True]
    assert window.start_with_windows_checkbox.isChecked()
    assert load_tool_settings(settings_path)["start_server_with_windows"] is True
