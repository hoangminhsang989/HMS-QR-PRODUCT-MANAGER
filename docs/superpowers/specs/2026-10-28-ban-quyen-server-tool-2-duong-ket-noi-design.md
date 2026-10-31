# Thiết kế: Bản quyền ở Server Tool + 2 đường kết nối cho Desktop/Mobile + Web tách riêng

Ngày: 2026-10-28
Repo: `D:\PHAN MEM QUAN LY QR` (HMS-QR) và `D:\HE-THONG-KEY-BAN-QUYEN` (máy chủ bản quyền)

> Ghi chú về đường dẫn (2026-10-31): repo HMS-QR khi thiết kế này được viết nằm ở
> `E:\QR`. Ổ `E:` đó không còn tồn tại trên máy này — repo đã được chuyển sang
> `D:\PHAN MEM QUAN LY QR`. Mọi chỗ bên dưới vẫn giữ nguyên đường dẫn cũ trong
> bảng hiện trạng, vì đó là những gì đã được kiểm tra thật vào ngày 2026-10-28;
> chỉ có dòng tiêu đề và các hướng dẫn thao tác là trỏ đến vị trí hiện tại.
> Repo máy chủ bản quyền vẫn ở `D:\HE-THONG-KEY-BAN-QUYEN`, không đổi.

Sơ đồ duyệt: `.archify/02-DE-XUAT/DE-XUAT-ban-quyen-server-tool.html`

## 1. Intent và lý do

LO muốn phần mềm HMS QR được bảo vệ bản quyền ngay từ **máy chủ xưởng**, và người
dùng cuối có 2 đường kết nối để khỏi phụ thuộc một đường duy nhất:

- Máy xưởng mua key → nhập key **một lần duy nhất trên Server Tool** → server chạy.
- Người dùng cuối dùng **Desktop** hoặc **Mobile**, mỗi loại có **2 đường**:
  mạng LAN (nhanh, không đi vòng) và web (qua trung gian trên VPS, dùng link theo
  tài khoản).
- Giao diện web **tách làm 2 bản riêng** để tránh tải chậng và khỏi "đi vòng".
- Khách hàng nhận key có **tiền tố riêng theo tài khoản** để nhìn vào key là biết
  của ai, và server hết hạn vẫn được **dùng thêm 15 ngày** chờ gia hạn.

Động lực kinh doanh: hiện bản quyền chỉ nằm ở desktop qua 3 biến env phải copy tay
từng máy; máy xưởng có thể chạy server mà không cần key hợp lệ.

## 2. Hiện trạng (đã kiểm tra trong code)

### Repo máy chủ bản quyền — `D:\HE-THONG-KEY-BAN-QUYEN`

| Thứ | Trạng thái |
|---|---|
| Nền tảng | FastAPI + SQLite, deploy VPS Plesk/Caddy (`deploy/`) |
| Web | Portal khách tự phục vụ + trang admin + thanh toán payOS |
| API client | `POST /api/activate`, `POST /api/verify` (`routers/public.py`) |
| API offline | `POST /admin-api/api/offline/generate` (`routers/admin.py:509`) |
| Chuỗi key | `HMS-XXXXX-XXXXX-XXXXX-XXXXX`, 4 nhóm × 5 ký tự, bảng 31 ký tự (~99 bit) |
| Lưu key | Bảng key của máy chủ bản quyền giữ `key_hash` (SHA-256); plaintext chỉ tồn tại lúc mint |
| SDK | `packages/hms_license`: `create_request_file`, `import_license_file`, `check_at_launch`, `ACTIVATE_PATH=/api/activate` |
| Kho key | Thiết kế vault (`HMS_KEY_VAULT_KEY`, AES-256-GCM) đã có spec 2026-10-27 |

### Repo HMS-QR — `E:\QR`

| Thứ | Trạng thái |
|---|---|
| Desktop | PySide6; **đã có** cổng bản quyền qua 3 biến env `HMS_QR_LICENSE_SERVER_URL` / `_PUBLIC_KEY_PEM` / `_FILE_KEY` (`apps/desktop/license_gate.py`) |
| Server Tool | PySide6, sở hữu vòng đời API (uvicorn 0.0.0.0:8010); **chưa có** bản quyền |
| Server | FastAPI `apps/server/app.py`; auth token HMAC-SHA256 8 giờ; vai trò ADMIN/EDITOR/VIEWER (`packages/application/server_auth.py`) |
| Dữ liệu | SQL Engine `packages/sqlengine` (snapshot.json + journal.log), migration head 7 |
| Mobile | **Một** trang `web/index.html` duy nhất, host tĩnh chung (Vercel) |
| Desktop | chỉ có đường LAN (kết nối server local) |

## 3. Goals / Non-goals / Anti-goals

### Goals

- G1 — Server Tool là **chỗ duy nhất** nhập key và kích hoạt (online + offline).
- G2 — Máy xưởng **không copy 3 biến env**: tool lấy cấu hình từ web, admin đổi
  được trên trang admin.
- G3 — Desktop **và** Mobile đều có **2 đường**: LAN và web (link).
- G4 — Web tách **2 bản HTML riêng**: Web LAN (cùng cổng 8010, do server phục vụ)
  và Web VPS (do trung gian phục vụ).
- G5 — Link **chỉ là đường kết nối**; sau khi lấy được đường vẫn phải đăng nhập
  tài khoản server có phân quyền, y như đường LAN.
- G6 — Tiền tố **tự sinh theo tài khoản**, kèm chuỗi **mã hoá**.
- G7 — Server hết hạn → **ân hạn 15 ngày** rồi mới dừng API.
- G8 — **Server local cấp phép** sử dụng cho Desktop (Desktop không tự gọi máy chủ
  bản quyền).

### Non-goals

- Không đổi giao diện admin hiện có, trừ: thêm mục cấu hình kết nối, hiển thị
  tiền tố theo tài khoản.
- Không đổi format chuỗi key (vẫn ~99 bit) — chỉ **thêm tiền tố** vào đầu.
- Không làm app mobile native — vẫn là web.
- Không đổi cơ chế đăng nhập / phân quyền hiện có của server.

### Anti-goals (thất bại dù kỹ thuật chạy)

- Link bị hiểu nhầm là "đăng nhập" / link cấp quyền dùng.
- Desktop tự gọi máy chủ bản quyền (phải qua server local).
- Web LAN phải đi vòng qua VPS (chậm, phụ thuộc internet).
- Mất internet là server chết ngay (phải ân hạn).
- Key lộ plaintext trong CSDL máy chủ bản quyền.

## 4. Thiết kế

### 4.1 Server Tool làm chủ bản quyền (repo HMS-QR)

- Cổng bản quyền nằm **trong Server Tool**, chạy **trước khi API bật**:
  - chưa có key → màn hình kích hoạt (nhập key / nộp file .lic);
  - hết hạn hoặc bị thu hồi → khoá, không bật API;
  - còn hạn → bật API như cũ.
- **Kích hoạt online**: tool gọi máy chủ bản quyền qua HTTPS (`/api/activate`,
  `/api/verify`).
- **Kích hoạt offline**: tool tạo file `.req` (AES-256-GCM) → mang ra ngoài
  (USB/email) → nộp trên web (khách tự nộp ở portal, hoặc admin nộp ở
  `/offline/generate`) → nhận về `license.dat` → nhập vào tool. Về sau tool tự
  kiểm chữ ký + HWID + hạn dùng, không cần mạng.
- **Cấu hình lấy từ web**: tool gọi endpoint cấu hình trên máy chủ bản quyền
  (URL server, public key, file key, tên product, thời gian ân hạn). Admin đặt
  được trên trang admin. Tool cache cấu hình đã lấy để dùng khi mất mạng.
- **Tool đóng thì API vẫn chạy** (autostart/production_launcher) → chính
  HMS QR Server tự kiểm tra bản quyền định kỳ (task nền); quá 15 ngày ân hạn thì
  từ chối phục vụ.

### 4.2 Server local cấp phép cho Desktop (repo HMS-QR)

- Desktop đăng nhập vào server local **như cũ** (tài khoản + phân quyền
  ADMIN/EDITOR/VIEWER).
- Phiên làm việc / response đăng nhập mang **trạng thái bản quyền của server**
  (hợp lệ / đang ân hạn / hết hạn).
- Desktop **chỉ hỏi server local**, không tự gọi máy chủ bản quyền.
- **Bỏ** 3 biến env `HMS_QR_LICENSE_*` ở desktop.

### 4.3 Hai đường kết nối cho Desktop + Mobile

- **ĐƯỜNG LAN**: thiết bị vào thẳng HMS QR Server `:8010` (cùng mạng). Mobile mở
  **Web LAN** do chính server phục vụ, cùng cổng 8010; API gọi trực tiếp.
- **ĐƯỜNG WEB**: dùng **link theo tài khoản** → **trung gian trên VPS** →
  HMS QR Server.
  - Link do **tool tạo**: operator đăng nhập bằng tài khoản + mật khẩu người mua
    tool, tool đăng ký với trung gian và nhận link mã hoá riêng cho tài khoản đó.
  - Link **gắn với tài khoản**: đổi tài khoản thì link đổi theo.
  - Link **chỉ là đường kết nối** — không cấp quyền. Sau khi có đường, người dùng
    vẫn đăng nhập tài khoản server có phân quyền.
  - Trung gian vừa phục vụ trang **Web VPS**, vừa chuyển tiếp API vào server.
- **Trung gian đặt CÙNG VPS** với máy chủ bản quyền.

### 4.4 Web tách 2 bản riêng (repo HMS-QR)

- **Web LAN**: bản HTML riêng, do HMS QR Server phục vụ (cùng cổng 8010), dành
  cho thiết bị cùng WiFi.
- **Web VPS**: bản HTML riêng, do trung gian phục vụ, dành cho thiết bị ngoài mạng.
- Cả hai gọi **cùng một bộ API**, chỉ khác điểm vào.
- Hai bản tách riêng để tránh tải chậm và khỏi đi vòng (LAN không phải qua VPS).

### 4.5 Tiền tố theo tài khoản (repo máy chủ bản quyền)

- Mỗi tài khoản khách có một **tiền tố tự sinh** (ví dụ `KH01`) kèm **chuỗi mã
  hoá** — không đoán ra được từ tên khách.
- Key phát ra mang tiền tố của khách: `KH01-XXXXX-XXXXX` (giữ entropy ~99 bit).
- Trang admin hiển thị / cho sao chép tiền tố của từng tài khoản.
- Tiền tố lưu cùng tài khoản; dùng cho mọi key mint qua mọi leg (webhook, poller,
  nút khách, nút admin).

### 4.6 Ân hạn 15 ngày

- Server hết hạn → cho dùng **thêm 15 ngày** chờ gia hạn.
- Trong 15 ngày: server vẫn chạy, nhưng báo trạng thái "đang ân hạn" cho desktop
  và mobile.
- Quá 15 ngày: server **từ chối phục vụ** (API trả lỗi bản quyền), desktop và
  mobile báo "bản quyền hết hạn — liên hệ quản trị".

## 5. Đã quyết (em chốt để builder khỏi đoán)

Builder đã kiểm tra bản thiết kế và đặt 9 câu. Sáu câu em chốt như sau — anh chỉ
cần xem lại, không cần trả lời:

- **D1 — Cấu hình lấy từ web phải đăng nhập.** Endpoint cấu hình **không công
  khai** vì nó chứa file key (bí mật). Tool đăng nhập bằng tài khoản khách → giữ
  **session token** (DPAPI), **không lưu mật khẩu**; hết session thì đăng nhập lại.
  URL máy chủ mặc định đi kèm tool (admin đổi được) — hết được vấn đề "phải biết URL
  trước khi lấy cấu hình".
- **D2 — Ân hạn 15 ngày tính ở phía HMS-QR, KHÔNG sửa SDK dùng chung.**
  `GRACE_DAYS = 5` trong `packages/hms_license` để nguyên (HMS-CAM đang dùng).
  Tool và server HMS-QR tự tính cửa sổ 15 ngày từ `expires_at` (số ngày ân hạn để
  trong cấu hình, admin đổi được).
- **D3 — Trung gian là một phần của app máy chủ bản quyền** (cùng VPS, cùng CSDL,
  dùng lại bảng `users`/`sessions`). Tool đăng nhập tài khoản khách rồi gọi đăng ký
  link; **đổi tài khoản thì link cũ bị thu hồi ngay**.
- **D4 — Server giữ bản quyền, không phải tool.** Tool ghi license + cấu hình vào
  thư mục dữ liệu production (`D:/HMS-QR-PROD/...`); **một bản duy nhất** là bản
  có hiệu lực. Server kiểm **cục bộ** (chữ ký + hạn dùng) mỗi vòng, và **gọi thêm
  `/api/verify` khi có mạng** để bắt thu hồi. Gia hạn: tool kích hoạt lại → ghi đè
  file → server nhận ngay (watch file), **không cần khởi động lại**.
- **D5 — "Từ chối phục vụ" không phải tắt hết.** Khi quá ân hạn: trang HTML
  (`/`, `/admin`, `/tracking/mobile`, Web LAN), `/health/readiness/*` và endpoint
  trạng thái bản quyền **vẫn trả lời** (để người dùng đọc "bản quyền hết hạn" và
  tool vẫn kích hoạt lại được); các API dữ liệu (`/api/v1/*`, `/stage2`, `/tracking`
  API, `/files`, `/ws/live`) trả lỗi bản quyền.
- **D6 — Một key / nhiều máy qua `max_devices`.** Key gắn HWID như SDK hiện làm.
  Tool có nút **"Giải phóng máy này"** (gọi `/api/admin/activations/{id}/reset` sẵn
  có) để đổi máy. `max_devices` mặc định do lô key quyết.
- **D7 — Vercel bỏ hẳn; server tự mở kênh ngược ra trung gian.** LO chốt
  2026-10-28: *"Vercel không cần giữ nữa"*. Web VPS (do trung gian phục vụ) thay
  chỗ trang mobile duy nhất trên Vercel. Vì máy xưởng không có IP public, **server
  chủ động gọi ra VPS**: một kênh ngược (websocket) từ HMS QR Server tới trung gian,
  có xác thực 2 chiều, heartbeat và tự nối lại. `CHAY_WEB.bat`, `tunnel_url.py` và
  `/api/v1/tunnel-status` **giữ lại cho chạy thử/dev ở cổng 8000** — đường mobile
  thật không còn phụ thuộc chúng.
- **D8 — Gia hạn trực tiếp trên web, VẪN KEY ĐÓ.** LO chốt 2026-10-28. Khi cần
  gia hạn: khách (hoặc LO thay mặt) gia hạn **trên web** → **key cũ tiếp tục dùng,
  chỉ đổi ngày hết hạn** — không cấp key mới.
  - **Máy kích hoạt ONLINE:** server đã gọi `/api/verify` định kỳ nên **tự nhận hạn
    mới**, không cần làm gì thêm.
  - **Máy kích hoạt OFFLINE:** khách **tải file bản quyền mới** (`.lic` đã chỉnh
    thời hạn) từ web rồi nhập vào Server Tool — dùng đúng luồng offline sẵn có
    (`create_request_file` → `/offline/generate` → `import_license_file`).
  - Phía web chỉ cần thêm hành động **"gia hạn"** (kéo dài `expires_at` của
    key/lô — `renew_batch` đã có ở `repo.py:139`); thanh toán gia hạn dùng lại
    payOS nếu khách tự làm, hoặc LO bấm tay ở trang admin.
- **D9 — Không tồn kho key; mọi key đều mang tiền tố chủ.** LO chốt 2026-10-28:
  *"Khi nào cần key tôi tự tạo trong trang admin; khách tự tạo key / mua hàng thì
  không liên quan, nên không cần tồn kho key."**
  - Form tạo key của admin **thêm ô chọn tài khoản khách** → key lúc nào cũng mang
    tiền tố đúng chủ. (Non-goal "trang admin chỉ đổi 2 chỗ" được nới lên **3 chỗ**:
    cấu hình kết nối, hiển thị tiền tố, ô chọn tài khoản khi tạo key.)
  - Khách tự mua / tự tạo key thì luôn biết tài khoản nên tiền tố lấy từ tài khoản
    đó — không có luồng "key chưa định danh".
- **D10 — Máy xưởng cũ: LO kích hoạt tay lúc phát bản, không làm cửa sổ miễn.**
  *(Em chốt thay LO — anh phản đồ thì em sửa.)* Bản phát hành là offline, anh tự
  quyết khi nào cài lên máy khách, nên không cần cờ "miễn kiểm tra tới ngày X":
  anh mang key tới và kích hoạt trên Server Tool như một bước trong quy trình cài.
  Nhờ D8, từ giờ mọi lần gia hạn đều tự lo được trên web, khỏi phải mang tay nữa.

## 6. Rủi ro đã biết

- **Mất khoá mã hoá tiền tố / khoá vault** → không tra ngược được key đã bán. Phải
  sao lưu env trên VPS (script backup đã copy file env).
- **Trung gian là điểm chết**: nếu VPS chết, đường web chết nhưng đường LAN vẫn
  chạy — thiết kế phải giữ điều này (đường LAN không phụ thuộc trung gian).
- **Link bị chia sẻ**: link chỉ là đường kết nối nên chia sẻ link không cho quyền
  dùng — nhưng vẫn nên giới hạn tốc độ và ghi log.
- **Desktop bỏ env gate**: nếu server local bị tắt giả (license giả), desktop vẫn
  tin server. Chấp nhận được vì server là thứ đang giữ bản quyền.
- **15 ngày ân hạn bị lạm dụng**: khách cố tình không gia hạn. Cần trang admin
  cảnh báo đơn đang ân hạn.

## 7. Chờ LO quyết

*(Trống — LO đã trả lời hết. Vercel bỏ (D7), câu 1 chốt thành D8+D9+D10.)*

### Câu 1 — Máy xưởng cũ nâng cấp lên bản mới thì có bị tắt máy không?

**Tình hình:** Hôm nay server ở máy xưởng chạy **không cần key** (bản quyền chỉ nằm
ở desktop). Sau thay đổi này, server sẽ **từ chối chạy** nếu chưa nhập key.

**Ví dụ cụ thể:** Anh có 10 máy xưởng đang chạy cho 10 khách. Anh phát bản mới.

- **Phương án A — có cửa sổ chuyển tiếp:** bản mới có cài đặt "miễn kiểm tra tới
  ngày …" (ví dụ 31/12/2026). Cả 10 máy vẫn chạy bình thường sau khi cài bản mới.
  Anh có 2 tháng để bán key, mang tới từng máy kích hoạt. Sau 31/12, máy nào chưa
  có key mới bị chặn.
- **Phương án B — không có cửa sổ:** ngay khi cài bản mới, máy nào chưa nhập key thì
  server tắt luôn. Anh (hoặc người bán) phải có key sẵn trong tay và kích hoạt
  từng máy ngay lúc cài.

**Đoán sai thì sao:** chọn B mà anh chưa bán được key → khách báo "máy tắt đứng
đơ", anh phải chạy theo từng máy. Chọn A mà anh không đẩy nhanh việc bán key →
hết ngày miễn thì khách lại tắt máy đùng một cái.

### Câu 2 — Key tạo theo lô (nhập kho) có mang tiền tố khách hàng không?

**Tình hình:** Ở trang admin, anh có thể tạo key **theo lô** — ví dụ tạo 100 key
một lúc để nhập kho bán dần. Form tạo key này **hiện không hỏi "key này của khách
nào"**. Nhưng yêu cầu mới nói mỗi key mang **tiền tố của khách** (ví dụ
`KH01-XXXXX`) để nhìn vào key là biết của ai.

**Ví dụ cụ thể:**

- **Phương án A — thêm ô chọn khách:** form tạo key thêm một ô chọn tài khoản. Mỗi
  lần tạo key đều phải chọn khách → mọi key đều mang tiền tố đúng khách. Giá trị:
  khách gửi key lên hỗ trợ, anh biết ngay của ai. Chi phí: trang admin đổi thêm
  một chỗ nữa (tao đã thoả thuận chỉ đổi 2 chỗ: cấu hình kết nối + hiển thị tiền
  tố), và anh **không thể tạo key "nhập kho" không định danh** nữa.
- **Phương án B — key lô không có tiền tố:** key tạo theo lô (chưa bán cho ai)
  không mang tiền tố; chỉ key phát cho khách cụ thể (qua mua hàng / tài khoản) mới
  có. Giá trị: anh vẫn tạo key nhập kho bán dần như cũ. Chi phí: nếu khách mua một
  key kho và gửi lên hỗ trợ, anh **không tra ra được của ai** từ chuỗi key.

**Đoán sai thì sao:** chọn A mà anh định tạo key kho bán đại trà → khó chịu ngay
lúc tạo. Chọn B mà anh trông chờ tra cứu khách từ key → lúc khót vấn đề hỗ trợ anh
phải tra tay trong CSDL.

## 8. Việc cần làm (tóm tắt cho builder)

### Repo máy chủ bản quyền

1. Tiền tố tự sinh theo tài khoản + chuỗi mã hoá; lưu vào bảng tài khoản; dùng khi
   mint key (mọi leg).
2. Trung gian trên VPS: nhận đăng ký từ tool, cấp link theo tài khoản, phục vụ
   Web VPS, chuyển tiếp API vào server xưởng.
3. Endpoint cấu hình cho tool (URL server, public key, file key, product, ân hạn).
4. Trang admin: mục cấu hình kết nối + hiển thị tiền tố theo tài khoản.

### Repo HMS-QR

5. Server Tool: cổng bản quyền (kích hoạt online/offline, lấy cấu hình từ web,
   ân hạn 15 ngày, khoá khi hết hạn).
6. Server: task nền kiểm tra bản quyền; trạng thái bản quyền trong response
   đăng nhập (cấp phép cho desktop); từ chối phục vụ khi quá ân hạn.
7. Desktop: bỏ 3 biến env gate; thêm đường web (dùng link lấy đường kết nối rồi
   đăng nhập như LAN).
8. Mobile: tách Web LAN (server phục vụ, cổng 8010) và Web VPS (trung gian phục
   vụ); cả hai đăng nhập tài khoản server có phân quyền.
