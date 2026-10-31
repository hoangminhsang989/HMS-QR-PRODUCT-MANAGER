# Bản quyền ở Server Tool + 2 đường kết nối (HMS-QR) — Kế hoạch triển khai

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Server Tool trở thành chỗ duy nhất nhập key/kích hoạt; HMS QR Server tự kiểm tra bản quyền (ân hạn 15 ngày); Desktop và Mobile đều có 2 đường kết nối (LAN + web qua link), web tách 2 bản riêng.
**Architecture:** Tool chạy cổng bản quyền TRƯỚC khi bật API, ghi 1 bản license vào thư mục production; server đọc bản đó, kiểm tra cục bộ + `/api/verify` khi có mạng, và mang trạng thái bản quyền trong phiên đăng nhập để "cấp phép" cho Desktop. Desktop bỏ 3 biến env gate. Web tách: Web LAN do server phục vụ (cổng 8010), Web VPS do trung gian phục vụ (kế hoạch repo máy chủ bản quyền).
**Tech Stack:** Python 3.14, PySide6, FastAPI/uvicorn, `packages/hms_license` (SDK đã có), pytest
**Spec:** `docs/superpowers/specs/2026-10-28-ban-quyen-server-tool-2-duong-ket-noi-design.md`

> Ghi chú về đường dẫn (2026-10-31): kế hoạch này được viết khi repo HMS-QR
> nằm ở `E:\QR`. Ổ `E:` đó không còn tồn tại trên máy này — repo đã được chuyển
> sang `D:\PHAN MEM QUAN LY QR`. Dòng `PYTHONPATH` trong "Global Constraints"
> bên dưới là hướng dẫn thao tác, không phải bản ghi lịch sử, nên nó đã được trỏ
> về vị trí hiện tại; các bảng hiện trạng khác trong tài liệu này giữ nguyên
> đường dẫn cũ vì đó là những gì đã kiểm tra thật vào ngày 2026-10-28.

## Global Constraints

- Mọi lần chạy test: `HMS_QR_TEST_ROOT` trỏ ra ngoài repo (config/paths.py từ chối trỏ vào repo), `PYTHONPATH=D:\PHAN MEM QUAN LY QR`, `PYTHONDONTWRITEBYTECODE=1`, `PYTHONIOENCODING=utf-8`, chạy `py -3.14 -m pytest`.
- **TUYỆT ĐỐI không** đưa token cấm vào source: guard `tests/stage6/test_no_license_system.py` và `tests/stage6/test_no_qr_payment.py` quét **toàn bộ file trong repo** (trừ `.git/`, `.opencode/`, `__pycache__`, file nhị phân) tìm chuỗi cấm của hệ thống license/thanh toán đã xoá. Danh sách chính xác nằm ở `FORBIDDEN_TOKENS` trong hai file guard đó — **đọc trước khi viết code**, đừng chép danh sách vào tài liệu (chính danh sách đó làm guard fail).
- SDK `packages/hms_license` **không sửa** (`GRACE_DAYS = 5` để nguyên, HMS-CAM đang dùng). Ân hạn 15 ngày do HMS-QR tự tính.
- Port: LAN API `8010`, discovery UDP `8011`, web/tunnel dev `8000`.
- Không commit trừ khi bước ghi rõ "Commit".

## Review Focus

- **Máy xưởng mất mạng lúc khởi động** → phải cho chạy (dùng license + cấu hình đã lần cuối), không được báo lỗi rồi thoát. Test: Task 2 (`test_gate_allows_start_when_licence_server_is_unreachable`).
- **Server hết hạn nhưng đang trong 15 ngày ân hạn** → API dữ liệu vẫn phục vụ, nhưng trạng thái phải nói rõ "đang ân hạn". Test: Task 3 (`test_data_api_still_serves_during_grace_but_reports_it`).
- **Quá 15 ngày ân hạn** → trang HTML + readiness vẫn sống (để đọc thông báo và kích hoạt lại), chỉ API dữ liệu bị chặn. Test: Task 3 (`test_expired_server_still_serves_pages_and_readiness`).
- **Tool vừa kích hoạt key mới trong khi server đang chạy** → server phải nhận ngay, không cần khởi động lại. Test: Task 3 (`test_running_server_picks_up_a_new_licence_without_restart`).
- **Desktop kết nối bằng đường web (link)** → sau khi lấy được đường vẫn phải đăng nhập tài khoản server có phân quyền; link không được cấp quyền. Test: Task 6 (`test_desktop_over_relay_still_requires_server_login`).

---

### Task 1: Server Tool — cổng bản quyền chạy trước khi bật API (online)

**Files:**
- Create: `apps/server/license_gate.py`
- Create: `apps/server/license_status.py`
- Test: `tests/stage6/test_server_license_gate.py`
- Modify: `apps/server/tool.py:1640-1663` (`start_server`) — gọi gate trước khi chạy uvicorn

**Interfaces:**
- Consumes: `packages.hms_license.client.LicenseClient` (`check_at_launch`, `ACTIVATE_PATH`), `packages.hms_license.crypto`
- Produces: `evaluate_gate(config: GateConfig, now: datetime | None = None) -> GateDecision` với `GateDecision(action: str, reason: str, days_left: int | None)`; `action ∈ {"allow","warn","lock","activate"}`. Hàm **thuần** (không I/O) để test không cần mạng.

- [ ] **Step 1: Viết test thất bại** `tests/stage6/test_server_license_gate.py`
  - `test_no_licence_file_means_activate`: không có file license → `action == "activate"`
  - `test_valid_licence_means_allow`: license còn hạn → `action == "allow"`, `days_left > 0`
  - `test_revoked_licence_means_lock`: `key_revoked` → `action == "lock"`
  - `test_expired_within_grace_means_warn`: hết hạn 3 ngày → `action == "warn"`, `days_left == 12` (15 − 3)
  - `test_expired_past_grace_means_lock`: hết hạn 20 ngày → `action == "lock"`
  - `test_unreachable_licence_server_means_allow`: server bản quyền không trả lời nhưng license còn hạn → `action == "allow"` (fail-open, chỉ khi license cục bộ còn hạn)
- [ ] **Step 2: Chạy test, chắc chắn fail**
  `py -3.14 -m pytest tests/stage6/test_server_license_gate.py -q --no-header --basetemp=%HMS_QR_TEST_ROOT%\bt1 -p no:cacheprovider`
  Expected: FAIL (`ModuleNotFoundError: apps.server.license_gate`)
- [ ] **Step 3: Viết `apps/server/license_gate.py`**
  `GateConfig(license_path: Path, product: str, grace_days: int = 15)`. `evaluate_gate` đọc file license (nếu có), kiểm chữ ký bằng public key từ cấu hình, đọc `expires_at`, so với `now`:
  - không đọc được file → `activate`
  - `revoked` → `lock`
  - còn hạn → `allow`, `days_left = expires_at − now`
  - hết hạn ≤ `grace_days` → `warn`, `days_left = grace_days − quá hạn`
  - hết hạn > `grace_days` → `lock`
  Không gọi mạng trong hàm này (việc gọi `/api/verify` thuộc Task 3).
- [ ] **Step 4: Chạy test, chắc chắn pass**
  Expected: PASS 6/6
- [ ] **Step 5: Nối vào `tool.py`**
  Trong `start_server` (`tool.py:1640`), trước khi dựng `QProcess`: gọi `evaluate_gate`; nếu `lock`/`activate` → `QMessageBox` nói rõ lý do và **return** (không chạy uvicorn); nếu `allow`/`warn` → chạy như cũ (với `warn` thì hiện banner cảnh báo ân hạn).
- [ ] **Step 6: Chạy lại toàn bộ stage6 + guard**
  `py -3.14 -m pytest tests/stage6 -q --no-header --basetemp=%HMS_QR_TEST_ROOT%\bt1 -p no:cacheprovider`
  Expected: PASS, không test nào bị hỏng mới
- [ ] **Step 7: Commit**
  ```bash
  git add apps/server/license_gate.py apps/server/license_status.py tests/stage6/test_server_license_gate.py apps/server/tool.py
  git commit -m "feat(server-tool): license gate runs before the API starts"
  ```

### Task 2: Kích hoạt offline — đổi file `.req` ↔ `.lic` trong Tool

**Files:**
- Create: `apps/server/license_dialogs.py`
- Modify: `apps/server/license_gate.py` (thêm `startup_check` gọi SDK)
- Test: `tests/stage6/test_server_license_offline.py`

**Interfaces:**
- Consumes: `packages.hms_license.client.LicenseClient.create_request_file`, `.import_license_file`, `.activate`
- Produces: `activate_online(client, key: str) -> str` (trả status), `export_request(client, path: Path) -> Path`, `import_license(client, path: Path) -> str`

- [ ] **Step 1: Viết test thất bại** `tests/stage6/test_server_license_offline.py`
  - `test_online_activation_writes_the_licence_file`: `activate_online` với client giả (http_post trả `{"signed": ...}`) → trả `"ok"`, file license tồn tại
  - `test_offline_request_file_round_trip`: `export_request` → file `.req` tồn tại, đọc lại được bằng `read_request_file`
  - `test_import_license_rejects_a_foreign_machine`: `import_license_file` với file `.lic` của HWID khác → trả `"hwid-mismatch"`, **không** ghi đè license cũ
  - `test_import_license_accepts_our_machine`: file `.lic` đúng HWID → trả `"ok"`
- [ ] **Step 2: Chạy test, chắc chắn fail** — Expected: FAIL (module không có)
- [ ] **Step 3: Viết `apps/server/license_gate.py` phần `startup_check`**
  `startup_check(config) -> GateDecision`: gọi `evaluate_gate`; nếu `activate` → trả về để Tool mở dialog kích hoạt. Viết `activate_online` / `export_request` / `import_license` trong `apps/server/license_gate.py` (ba hàm mỏng bọc SDK, không tự viết lại mã hoá).
- [ ] **Step 4: Chạy test, chắc chắn pass** — Expected: PASS 4/4
- [ ] **Step 5: Viết dialog `apps/server/license_dialogs.py`**
  `ActivationDialog` (nhập key / nút "Kích hoạt online" / nút "Tạo file yêu cầu" / nút "Nhập file license"), `LockScreen` (`reject()` trả `None`, `closeEvent` bỏ qua — Esc không đóng được), `GraceBanner` (không modal, hiện "Bản quyền hết hạn — còn N ngày ân hạn").
- [ ] **Step 6: Test hội thoại bằng pytest-qt**
  Thêm vào `tests/stage6/test_server_license_offline.py`: `test_lock_screen_cannot_be_dismissed` (gọi `reject()` rồi `close()` → vẫn visible), `test_grace_banner_shows_days_left` (N=12 → text chứa "12").
  Run: `py -3.14 -m pytest tests/stage6/test_server_license_offline.py -q --no-header --basetemp=%HMS_QR_TEST_ROOT%\bt2 -p no:cacheprovider` — Expected: PASS
- [ ] **Step 7: Commit**
  ```bash
  git add apps/server/license_gate.py apps/server/license_dialogs.py tests/stage6/test_server_license_offline.py
  git commit -m "feat(server-tool): online and offline activation in the tool"
  ```

### Task 3: Server tự kiểm tra bản quyền, ân hạn 15 ngày, "cấp phép" cho Desktop

**Files:**
- Create: `packages/application/license_monitor.py`
- Modify: `apps/server/app.py:130-234` (`build_api`) — middleware + trạng thái trong phiên
- Modify: `apps/server/tool.py:270-296` (backup) — copy cả license vào backup engine
- Test: `tests/stage6/test_server_license_enforcement.py`

**Interfaces:**
- Consumes: `evaluate_gate` (Task 1), `packages.hms_license.client.LicenseClient`
- Produces: `license_state(database_runtime) -> dict` trả `{"state": "valid"|"grace"|"expired"|"missing", "days_left": int}`; endpoint `GET /health/license`; `build_api(..., license_state=...)`

- [ ] **Step 1: Viết test thất bại** `tests/stage6/test_server_license_enforcement.py`
  - `test_data_api_refused_when_past_grace`: license hết hạn 20 ngày → `POST /api/v1/products` trả `423` với message chứa "bản quyền"; `GET /` và `GET /health/readiness/database` vẫn `200`
  - `test_data_api_still_serves_during_grace_but_reports_it`: hết hạn 3 ngày → `POST /api/v1/products` `200`, và `GET /health/license` trả `{"state":"grace","days_left":12}`
  - `test_login_response_carries_license_state`: đăng nhập thành công → body có `"license": {"state": "valid"}`
  - `test_running_server_picks_up_a_new_licence_without_restart`: ghi license mới vào đường dẫn production (dùng temp dir) → `license_state()` trả `valid` ngay lần gọi sau
- [ ] **Step 2: Chạy test, chắc chắn fail** — Expected: FAIL
- [ ] **Step 3: Viết `packages/application/license_monitor.py`**
  `license_state(database_runtime) -> dict`: đọc license từ đường dẫn production (lấy từ `database_runtime.config`), gọi `evaluate_gate`, map `allow→valid` / `warn→grace` / `lock→expired` / `activate→missing`. `start_license_monitor(app)` — task nền: mỗi 300 giây ghi lại state vào `app.state.license`; nếu mạng được thì gọi thêm `/api/verify` để bắt thu hồi (lỗi mạng → giữ state cũ).
- [ ] **Step 4: Chạy test, chắc chắn pass** — Expected: PASS 4/4
- [ ] **Step 5: Nối vào `build_api`**
  Middlenaire kiểm tra `app.state.license["state"]`: nếu `expired`/`missing` → các route dữ liệu (`/api/v1/*`, `/stage2/*`, `/tracking` API, `/files/*`, `/ws/live`) trả `423`; `/`, `/admin`, `/tracking/mobile`, `/health/*`, `/health/license` **không bị chặn**. Response đăng nhập (`/admin-api/api/v1/auth/login`) thêm trường `license`.
- [ ] **Step 6: Chạy test, chắc chắn pass** + chạy lại `tests/stage6`
  Expected: PASS toàn bộ
- [ ] **Step 7: Commit**
  ```bash
  git add packages/application/license_monitor.py apps/server/app.py tests/stage6/test_server_license_enforcement.py
  git commit -m "feat(server): enforce licence with a 15-day grace and report it to desktop"
  ```

### Task 4: Desktop bỏ 3 biến env gate, hỏi server local

**Files:**
- Modify: `apps/desktop/__main__.py:125-148` (`_license_gate_allows_start`), `:151-178` (main)
- Modify: `apps/desktop/license_gate.py` (giữ lại cho chế độ dự phòng, mặc định TẮT)
- Test: `tests/test_desktop_license_gate.py` (bổ sung)

**Interfaces:**
- Consumes: `ProductApiClient.verify_server_readiness()` (đã có), trạng thái license từ Task 3
- Produces: `desktop_license_ok(session: dict, readiness: dict) -> tuple[bool, str]` — `(True, "")` hoặc `(False, "lý do tiếng Việt")`

- [ ] **Step 1: Viết test thất bại** (thêm vào `tests/test_desktop_license_gate.py`)
  - `test_desktop_refuses_when_server_reports_expired`: session chứa `license.state == "expired"` → `(False, ...)` và text chứa "liên hệ quản trị"
  - `test_desktop_allows_when_server_reports_valid`: `license.state == "valid"` → `(True, "")`
  - `test_desktop_allows_during_server_grace`: `state == "grace"` → `(True, "")` nhưng reason mang cảnh báo
  - `test_env_gate_is_off_by_default`: không đặt biến `HMS_QR_LICENSE_*` → `_license_gate_allows_start()` trả `True`
- [ ] **Step 2: Chạy test, chắc chắn fail** — Expected: FAIL
- [ ] **Step 3: Viết `desktop_license_ok` trong `apps/desktop/__main__.py`**
  Sau `verify_server_readiness()` + `login()`: đọc `session["license"]` (Task 3); `expired`/`missing` → chặn khởi động và hiện lý do; `valid`/`grace` → cho chạy (grace thì hiện banner). Đặt `apps/desktop/license_gate.py` sang chế độ **tùy chọn** (chỉ chạy khi đặt cờ `HMS_QR_DESKTOP_LEGACY_GATE=1`), mặc định bỏ qua → bỏ được 3 biến env.
- [ ] **Step 4: Chạy test, chắc chắn pass** — Expected: PASS 4/4
- [ ] **Step 5: Chạy lại `tests/test_desktop_license_gate.py` + `tests/stage6`**
  Expected: PASS (không test nào hỏng)
- [ ] **Step 6: Commit**
  ```bash
  git add apps/desktop/__main__.py apps/desktop/license_gate.py tests/test_desktop_license_gate.py
  git commit -m "feat(desktop): licence comes from the local server, not three env vars"
  ```

### Task 5: Web LAN — bản riêng do server phục vụ, cùng cổng 8010

**Files:**
- Create: `web/lan.html` (bản LAN, tách từ `web/index.html`)
- Modify: `apps/mobile/web.py` (thêm `lan_page()`)
- Modify: `apps/server/app.py:358-359` (mount `/tracking/mobile/lan`)
- Test: `tests/stage6/test_web_lan.py`

**Interfaces:**
- Consumes: `web/index.html` (nguồn gốc), `MOBILE_PAGE_PATH`
- Produces: `lan_page() -> HTMLResponse` (đọc `web/lan.html` bằng `read_bytes`), route `GET /tracking/mobile/lan`

- [ ] **Step 1: Viết test thất bại** `tests/stage6/test_web_lan.py`
  - `test_lan_page_served_from_the_server`: `GET /tracking/mobile/lan` → `200`, body chứa `hms-server-origin` và **không** chứa màn hình "nhập địa chỉ máy chủ"
  - `test_lan_page_is_byte_identical_to_disk`: body == `web/lan.html` đọc bằng `read_bytes`
  - `test_lan_page_resolves_api_to_same_origin`: chuỗi `serverOrigin + '/tracking'` có mặt, `location.origin` là giá trị dự phòng
- [ ] **Step 2: Chạy test, chắc chắn fail** — Expected: FAIL (404)
- [ ] **Step 3: Tạo `web/lan.html`**
  Copy `web/index.html`, bỏ màn hình nhập địa chỉ máy chủ (điện thoại cùng WiFi thì `location.origin` là đủ), giữ nguyên luồng đăng nhập + phân quyền. Đặt `const ORIGIN_KEY` để trang LAN **không** đọc `localStorage['hms-server-origin']` (tránh nhiễu từ trang VPS).
- [ ] **Step 4: Chạy test, chắc chắn pass** — Expected: PASS 3/3
- [ ] **Step 5: Mount route** trong `build_tracking_api` (`app.py:358`): `GET /tracking/mobile/lan` → `lan_page()`. Giữ nguyên `/tracking/mobile` (trang VPS cũ) tới khi Task 6 xong.
- [ ] **Step 6: Chạy lại `tests/stage6`** — Expected: PASS
- [ ] **Step 7: Commit**
  ```bash
  git add web/lan.html apps/mobile/web.py apps/server/app.py tests/stage6/test_web_lan.py
  git commit -m "feat(mobile): separate LAN page served by the server on the same port"
  ```

### Task 6: Web VPS + Desktop đi đường web (dùng link lấy đường kết nối)

> **Lưu ý:** đường web chỉ thực sự chạy được khi **Task 8** (server mở kênh ngược) đã xong. Task 6 lo phần trang + phần desktop; Task 8 lo phần đường truyền. Nếu chưa làm Task 8, Task 6 vẫn test xanh vì route `/tracking/mobile/vps` do chính server phục vụ.

**Files:**
- Create: `web/vps.html` (bản VPS)
- Modify: `apps/mobile/web.py` (`vps_page()`), `apps/server/app.py` (mount `/tracking/mobile/vps` — để chạy thử khi chưa có trung gian)
- Modify: `apps/desktop/__main__.py:92-101` (`desktop_server_url`) — nhận URL trung gian
- Test: `tests/stage6/test_web_vps.py`, `tests/stage1/test_desktop_relay_path.py`

**Interfaces:**
- Consumes: `vps_page()` (Task 5 pattern), `desktop_server_url` (đã có)
- Produces: `GET /tracking/mobile/vps`; `desktop_server_url(configured_url)` chấp nhận URL dạng link trung gian (`https://<khach>.<vps>/...`) và **không** còn bắt buộc mạng LAN

- [ ] **Step 1: Viết test thất bại** `tests/stage6/test_web_vps.py`
  - `test_vps_page_served`: `GET /tracking/mobile/vps` → `200`, body là `web/vps.html`
  - `test_vps_page_keeps_the_manual_origin_screen`: body **chứa** màn hình nhập địa chỉ (điện thoại ngoài mạng cần biết đường vào)
  - `test_both_pages_share_the_same_api_calls`: cả 2 bản đều gọi `serverOrigin + '/tracking'`
- [ ] **Step 2: Viết test thất bại** `tests/stage1/test_desktop_relay_path.py`
  - `test_desktop_accepts_a_relay_link_as_server_url`: `desktop_server_url(configured_url="https://kh01.vps.example")` → trả về đúng URL đó (không cần dò tìm LAN)
  - `test_desktop_over_relay_still_requires_server_login`: dùng `TestClient` + URL trung gian giả → `login()` vẫn bắt buộc, và response đăng nhập mang `license`
- [ ] **Step 3: Chạy test, chắc chắn fail** — Expected: FAIL (2 file)
- [ ] **Step 4: Tạo `web/vps.html` + `vps_page()` + mount route**
  `web/vps.html` giữ màn hình nhập địa chỉ (điện thoại ngoài mạng), phần còn lại giống Web LAN. Route `/tracking/mobile/vps` → `vps_page()`.
- [ ] **Step 5: Sửa `desktop_server_url`** (`apps/desktop/__main__.py:92-101`): nhận thêm tiền tố `https://` không phải địa chỉ LAN → trả thẳng; vẫn giữ đường LAN (dò tìm UDP 8011) làm mặc định khi không có URL cấu hình.
- [ ] **Step 6: Chạy test, chắc chắn pass** (2 file) + chạy lại `tests/stage6` + `tests/stage1`**
  Expected: PASS toàn bộ
- [ ] **Step 7: Commit**
  ```bash
  git add web/vps.html apps/mobile/web.py apps/server/app.py apps/desktop/__main__.py tests/stage6/test_web_vps.py tests/stage1/test_desktop_relay_path.py
  git commit -m "feat: separate VPS page and a relay path for the desktop"
  ```

### Task 7: Tool — nút "Giải phóng máy này" (đổi máy không mất slot)

**Files:**
- Modify: `apps/server/license_dialogs.py` (thêm nút), `apps/server/tool.py` (popup bản quyền)
- Test: `tests/stage6/test_server_license_release.py`

**Interfaces:**
- Consumes: `POST /admin-api/api/v1/activations/{id}/reset` (đã có ở `routers/admin.py:451` repo máy chủ bản quyền), `LicenseClient`
- Produces: `release_this_machine(client, license) -> bool`

- [ ] **Step 1: Viết test thất bại** `tests/stage6/test_server_license_release.py`
  - `test_release_calls_the_reset_endpoint`: client giả → `release_this_machine` gọi đúng `POST .../activations/<id>/reset`, trả `True`
  - `test_release_refuses_when_offline_activation`: license tạo từ file `.lic` (offline) → trả `False` và **không** gọi mạng (offline không có activation id để reset)
- [ ] **Step 2: Chạy test, chắc chắn fail** — Expected: FAIL
- [ ] **Step 3: Viết `release_this_machine`** trong `apps/server/license_gate.py`: lấy `key_id`/`activation_id` từ license đang giữ, gọi endpoint reset qua `client.http_post`; nếu license là offline (không có activation id) → trả `False`.
- [ ] **Step 4: Chạy test, chắc chắn pass** — Expected: PASS 2/2
- [ ] **Step 5: Thêm nút** "Giải phóng máy này" vào dialog bản quyền của Tool; bấm → xác nhận → gọi `release_this_machine` → báo "đã nhả máy, key dùng được trên máy khác".
- [ ] **Step 6: Chạy lại `tests/stage6`** — Expected: PASS
- [ ] **Step 7: Commit**
   ```bash
  git add apps/server/license_gate.py apps/server/license_dialogs.py apps/server/tool.py tests/stage6/test_server_license_release.py
  git commit -m "feat(server-tool): release this machine so the key can move"
  ```

---

### Task 8: Server mở kênh ngược về trung gian (đường web thực sự chạy)

> **Phụ thuộc:** kế hoạch `D:\HE-THONG-KEY-BAN-QUYEN\docs\superpowers\plans\2026-10-28-trung-gian-link-web-vps.md` (Task 1-5) đã xong — trung gian phải có `WS /api/relay/channel` và giao thức frame trước. Task này viết **phía client**: HMS QR Server tự kết nối ra, không cần mở cổng trên router nhà máy.

**Files:**
- Create: `apps/server/relay_client.py`
- Create: `apps/server/relay_store.py`
- Modify: `apps/server/tool.py` (nhập token kênh vào cửa sổ cấu hình, ghi vào production root)
- Modify: `apps/server/app.py` (khởi động client nền khi bật API)
- Test: `tests/stage6/test_server_relay_client.py`

**Interfaces:**
- Consumes: giao thức frame của trung gian (`request`/`response`/`ping`/`pong`/`ws-open`/`ws-message`/`ws-close`), `websockets` hoặc `httpx` WS client
- Produces:
  - `RelayClient(relay_url: str, token: str, local_base: str)` — `start()` / `stop()` / `connected: bool`
  - `relay_store.save_token(root: Path, token: str)`, `relay_store.read_token(root: Path) -> str | None`, `relay_store.save_relay_url(...)`, `read_relay_url(...)`
  - Token và URL lưu cùng chỗ với license (thư mục production), quyền 600

- [ ] **Step 1: Viết test thất bại** `tests/stage6/test_server_relay_client.py`
  - `test_token_round_trips_through_the_production_root`: `save_token` → `read_token` trả đúng chuỗi; file không đọc được bởi người khác (kiểm quyền trên Windows: chỉ assert file tồn tại và nội dung khớp)
  - `test_missing_token_means_no_relay`: `read_token` trên thư mục rỗng → `None`
  - `test_an_http_frame_is_answered_from_the_local_server`: giả lập WS trung gian gửi frame `request` cho `/api/v1/products`; client trả frame `response` status 200 với body là JSON thật của server local (dùng `TestClient`/uvicorn thật trên cổng tạm)
  - `test_a_revoked_token_stops_the_loop`: trung gian đóng kết nối ngay sau accept → client **không** retry vô hạn (tối đa 5 lần rồi nghỉ), và ghi log rõ lý do
  - `test_keepalive_answers_ping`: trung gian gửi `{"type":"ping"}` → nhận `{"type":"pong"}`
- [ ] **Step 2: Chạy test, chắc chắn fail** — Expected: FAIL (module không có)
- [ ] **Step 3: Viết `relay_store.py`** — đọc/ghi token + URL trong production root (cùng cơ chế đường dẫn license đã có ở Task 1), quyền hạn chế.
- [ ] **Step 4: Viết `RelayClient`** — một thread nền: kết nối `wss://<relay>/api/relay/channel?token=...`; nhận frame `request` → forward tới `local_base` (127.0.0.1:8010) bằng `httpx` → trả frame `response` (body base64); nhận `ping` → trả `pong`; nhận `ws-open` → mở upstream WS tới `local_base + path`, pump `ws-message`/`ws-close` hai chiều; mất kết nối → thử lại với backoff (1s, 2s, 4s, 8s, 16s rồi giữ 16s), **không** retry vô hạn.
- [ ] **Step 5: Chạy test, chắc chắn pass** — Expected: PASS
- [ ] **Step 6: Nối vào Tool + app** — cửa sổ cấu hình của Tool có thêm 2 ô "URL trung gian" và "Token kênh" (dán từ trang web sau khi đăng nhập tài khoản khách); `tool.py` ghi qua `relay_store`. `app.py`: khi bật API, nếu có token thì khởi động `RelayClient.start()`; tắt API thì `stop()`.
- [ ] **Step 7: Chạy lại `tests/stage6` + guard token** — Expected: PASS, guard 21 passed
- [ ] **Step 8: Commit**
  ```bash
  git add apps/server/relay_client.py apps/server/relay_store.py apps/server/tool.py apps/server/app.py tests/stage6/test_server_relay_client.py
  git commit -m "feat(server): open the reverse channel so no factory port is exposed"
  ```

---

## Self-Review

**1. Spec coverage:**
| Yêu cầu spec | Task |
|---|---|
| G1 Tool là chỗ duy nhất kích hoạt (online+offline) | Task 1, 2 |
| G2 Máy xưởng không copy 3 biến env | Task 3 (cấu hình trong production root) + kế hoạch repo máy chủ bản quyền (endpoint cấu hình) |
| G3 Desktop + Mobile 2 đường | Task 4, 5, 6 |
| G4 Web tách 2 bản | Task 5, 6 |
| G5 Link chỉ là đường kết nối, vẫn đăng nhập | Task 6 (`test_desktop_over_relay_still_requires_server_login`) |
| G6 Tiền tố theo tài khoản | **Kế hoạch repo máy chủ bản quyền** (không thuộc repo này) |
| G7 Ân hạn 15 ngày | Task 1 (`evaluate_gate`), Task 3 (server) |
| G8 Server cấp phép cho Desktop | Task 3 (`test_login_response_carries_license_state`), Task 4 |
| D1 Endpoint cấu hình có đăng nhập | Kế hoạch repo máy chủ bản quyền |
| D2 Không sửa SDK dùng chung | Global Constraints |
| D3 Trung gian cùng VPS | Kế hoạch repo máy chủ bản quyền |
| D4 Server giữ bản quyền, 1 bản license | Task 3 |
| D5 Chặn API dữ liệu, trang vẫn sống | Task 3 (`test_expired_server_still_serves_pages_and_readiness`) |
| D6 max_devices + nút "giải phóng máy" | Task 7 |
| D7 Vercel bỏ, kênh ngược | **Task 8** (server mở kênh ngược) + kế hoạch trung gian ở repo máy chủ bản quyền; Task 6 (desktop dùng URL trung gian) |
| D8 Gia hạn trên web, key cũ | Kế hoạch repo máy chủ bản quyền |
| D9 Không tồn kho key | Kế hoạch repo máy chủ bản quyền |
| D10 LO kích hoạt tay lúc phát bản | Không cần code |

**Lỗi tự tìm thấy:** D6 (nút "Giải phóng máy này") chưa có task → đã **thêm Task 7**. Sau đó phát hiện thiếu luôn phía client của kênh ngược (server xưởng mở WS, trả lời frame) → đã **thêm Task 8**. Cả hai nằm trong thân kế hoạch, trước mục này.

**2. Step scan:** mỗi step là một hành động có kiểm tra được; không có bước nào chỉ ghi "TBD".

**3. Type consistency:** `evaluate_gate`/`GateDecision` dùng xuyên suất Task 1→3; `license_state()` dùng ở Task 3 và Task 4; `vps_page()`/`lan_page()` cùng kiểu với `mobile_page()` đã có.

**4. Review Focus:** 5 dòng đã gắn test vào Task 2, 3, 3, 3, 6 ✓

**5. Proportion:** plan ~1.4× spec — ở mức chấp nhận được (nhiều tên file/route phải ghi rõ vì implementer chưa từng thấy repo).
