# HMS QR Server Tool Popup Design

## Intent

Make the Server Tool straightforward to use by presenting only server operation controls on the main window and moving advanced functions into dedicated popup windows.

## User-approved behavior

- The main window shows Server status, the Start/Stop Server control, and a checkbox labeled “Khởi động Server cùng Windows”.
- The checkbox is enabled by default and remains enabled unless the user turns it off.
- The checkbox choice is stored per current Windows user.
- When enabled, a Windows logon scheduled task starts the API in the background after sign-in. Opening the management UI remains a separate manual action.
- The main window offers buttons that open separate popup windows for: “Mạng & cài đặt”, “Dữ liệu & sao lưu”, “Tài khoản”, and “Nhật ký & kiểm tra”.

## Goals

- Reduce the visible complexity of the main Server Tool window.
- Preserve all existing management actions and make them reachable from the appropriate popup.
- Replace the one-way autostart button with a default-on, persistent checkbox that enables and disables the existing current-user logon task.
- Keep the API lifecycle controls in the main window.

## Non-goals

- Do not start the API merely by opening the management UI.
- Do not stop PostgreSQL when stopping the API.
- Do not change production paths, credentials, firewall rules, or API behavior.
- Do not change the desktop shortcut behavior.

## Constraints

- Build on the existing PySide6 Server Tool implementation in `apps/server/tool.py`.
- Reuse the existing `current_user_autostart_command` task definition and production launcher.
- Autostart must contain no HMS QR secret values.
- Preserve existing Server Tool actions, state updates, and operational guards.
- The checkbox default is enabled when no saved preference exists; a saved disabled choice must remain disabled on subsequent launches.

## Proposed structure

- Main window: title/connection overview, Server status, Start/Stop controls, and autostart checkbox.
- Popup “Mạng & cài đặt”: LAN listener/readiness, firewall, network profile/static IP, PostgreSQL installation, and production setup controls.
- Popup “Dữ liệu & sao lưu”: data/backup roots, backup/restore, storage checks and inventories, and folder shortcuts.
- Popup “Tài khoản”: administrator login, LAN account creation, registered-account table and account management.
- Popup “Nhật ký & kiểm tra”: operational refresh/diagnostics, copy/clear log, and detailed output.

## Testable acceptance criteria

1. New configuration defaults autostart to enabled; saved false remains false after reload.
2. Checking the control creates/enables the current-user ONLOGON task; unchecking removes/disables that task.
3. The checkbox is connected to the background API launcher and the task contains no credentials.
4. The main window exposes Start/Stop, status, autostart and four popup launch buttons.
5. Each popup exposes its assigned existing controls; no existing Server Tool action is lost.
6. Existing API start/stop ownership and PostgreSQL independence behavior remain unchanged.
7. Existing Server Tool tests and new focused regressions pass.

## Implementation calls left to the builder

- Store the boolean preference alongside the existing Server Tool settings, using backward-compatible settings loading.
- Use non-modal top-level dialogs/windows parented to the main window so users can access other popups without closing one.
- Represent the autostart task as a single create/delete current-user scheduled task; report task operation failures in the UI rather than silently changing the checkbox state.
