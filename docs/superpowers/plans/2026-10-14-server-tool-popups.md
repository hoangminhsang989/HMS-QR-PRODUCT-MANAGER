# HMS QR Server Tool Popup Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Simplify the Server Tool main window, expose existing administration in four dedicated popup windows, and provide a default-on per-user checkbox for background API startup at Windows logon.

**Architecture:** Keep behavior and UI in the existing `apps/server/tool.py`, adding reusable popup containers and a backward-compatible autostart preference to settings. Implement one current-user scheduled-task create/delete interface and bind the main-window checkbox to it, persisting only successful changes. Add focused tests in the existing Server Tool test module before implementation.

**Tech Stack:** Python 3.14, PySide6, Windows Task Scheduler (`schtasks.exe`), pytest.

**Spec:** `docs/superpowers/specs/2026-10-14-server-tool-popup-design.md`

## Global Constraints

- Do not start the API merely by opening the management UI.
- Do not stop PostgreSQL when stopping the API.
- Do not change production paths, credentials, firewall rules, or API behavior.
- Do not change the desktop shortcut behavior.
- Autostart defaults to enabled only when no saved preference exists; saved false remains false.
- Scheduled task contains no HMS QR secrets and launches the production API launcher after current-user logon.
- Preserve all existing Server Tool actions and operational guards.

## Review Focus

- Existing settings files without an autostart key: retain other settings and default true; test old-format load.
- Saved false preference: remain false after load and UI construction; test persistence.
- Task Scheduler create/delete failure: do not falsely persist an applied checkbox state; test error handling without invoking Windows.
- Popup ownership/lifetime: non-modal windows stay available while parent remains open; test each launch wiring or popup construction.
- Existing actions and state observers: must remain connected after reparenting controls; run the Server Tool regression suite and inspect resulting popup widget membership.

---

### Task 1: Add testable autostart preference and task toggling

**Files:**
- Modify: `apps/server/tool.py:58-73,271-275`
- Test: `tests/stage6/test_server_tool.py`

**Interfaces:**
- Produce `set_current_user_autostart(enabled: bool, source_root: Path | None = None) -> None`; enable uses `current_user_autostart_command`, disable invokes `schtasks.exe /Delete /TN <AUTO_START_TASK_NAME> /F`.
- Extend settings with boolean key `start_server_with_windows`, default `True`; preserve existing `load_tool_settings` keys and update `save_tool_settings` compatibly.

- [ ] Write tests: old JSON settings load with autostart true; saved false round-trips; task create/delete commands are selected by enabled state; subprocess failure raises a user-displayable exception.
- [ ] Run `python -m pytest tests/stage6/test_server_tool.py -q -k "autostart or tool_settings"` and confirm the new cases fail.
- [ ] Implement backward-compatible setting load/save and task toggle helper; check subprocess return code and raise on failure.
- [ ] Re-run the focused tests and confirm they pass.

### Task 2: Build main window and four non-modal popup sections

**Files:**
- Modify: `apps/server/tool.py:19-25,580-986`
- Test: `tests/stage6/test_server_tool.py`

**Interfaces:**
- Main window adds `start_with_windows_checkbox` and four popup-launch buttons; retain `start_button`, `stop_button`, status labels, and underlying action widgets.
- Add an internal popup-opening method that retains window references and shows non-modal parented windows.

- [ ] Add focused Qt tests asserting main-window controls and four popup launch actions are present, and that each popup contains its intended existing controls.
- [ ] Run the focused UI tests and verify they fail against the current monolithic UI.
- [ ] Move existing LAN/setup, data/backup, account, and activity widget groups into dedicated top-level non-modal windows; keep Server lifecycle/status on main window.
- [ ] Connect checkbox state to task helper and settings; when task operation fails, restore previous checked state and show an error.
- [ ] Connect all moved controls to existing slots, preserving object references, state refreshes, and log behavior.
- [ ] Run focused UI tests and confirm all groups and signals work.

### Task 3: Regression verification and project records

**Files:**
- Modify: `.opencode/tasks.md`
- Modify: `.opencode/edit-log.md`
- Test: `tests/stage6/test_server_tool.py`

- [ ] Run `python -m pytest tests/stage6/test_server_tool.py -q`.
- [ ] Run `git diff --check` and inspect the UI changes for lost actions or duplicate API lifecycle controls.
- [ ] Update `.opencode/edit-log.md` with verified changes and test output; update `.opencode/tasks.md` with the completed objective and any unresolved external acceptance.
