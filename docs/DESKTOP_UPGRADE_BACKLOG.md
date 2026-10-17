# Desktop Upgrade Backlog

## Existing Features

- Product Master: product list, search, status filter, create product, and concurrent LAN refresh protection.
- Excel-style worksheet: multi-row entry, formulas, filters, sort, find/replace, fill handle, formatting, dates, images, clipboard, undo/redo, zoom, and configurable cell sizes.
- Product identity: automatic product code, QR payload, high-resolution 50 x 30 mm label generation, preview, and clipboard copy.
- Product files: upload/view/download product images and attachments through the Server API, archive status, and retry controls.
- Tracking: delivery-date navigator, workflow actions, history, QR actions, and Excel copy.
- LAN access: UDP Server discovery, readiness validation, saved verified endpoint, API-only authentication, and role-based Server access.

## Upgrade Order

1. [DONE] Connection visibility: show verified Server URL, signed-in account/role, and a safe reconnect check in Desktop.
2. [DONE] Login screen: collect username/password in Desktop instead of requiring environment variables.
3. [DONE] Server selection: allow discover, retry, and explicit LAN URL selection without editing environment variables.
4. [DONE] Role-aware interface: clearly mark read-only actions for `VIEWER` and disable unavailable changes before submission.
5. [DONE] Product list productivity: visible search/filter list, result count, copy active results to Excel, and row-level file selection.
6. [DONE] Worksheet productivity: export selected worksheet rows and block partial saves with a row-by-row validation summary.
7. [DONE] Tracking integration: open tracking for the selected Product Master row using the authenticated API client.
8. [DONE] File workflow: show task status, prevent competing operations, refresh results, and sanitize unexpected failure details.
9. [DONE] Machine 2 release: API-only launcher, Desktop shortcut, version display, and first-run diagnostics guide.
10. [IN PROGRESS] Acceptance: physical Machine 2 discovery, login, product read/write by role, files, tracking, and disconnect recovery.
