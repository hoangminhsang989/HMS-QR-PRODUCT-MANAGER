# Web app mobile — HMS QR

Giao diện mobile (PWA) của HMS QR. Một thư mục tĩnh thuần, **không build step**:
Vercel phục vụ đúng như máy chủ LAN phục vụ, từ cùng một trang nguồn.

```
web/
  index.html        toàn bộ app: HTML + CSS + JS inline — TRANG NGUỒN
  lan.html          bản LAN: index trừ màn hình nhập địa chỉ máy chủ
  vps.html          bản VPS: byte-identical với index.html
  manifest.json     PWA manifest (start_url "/" — Vercel phục vụ web/ ở gốc domain)
  sw.js             service worker, chỉ cache tài nguyên cục bộ
  vercel.json       cache header + security header cho Vercel
  static/           jsqr.min.js (quét QR), icon, favicon
```

Hai bản `lan.html` và `vps.html` **không sửa bằng tay**. Chúng do
`scripts/build_mobile_web.py` sinh ra từ `index.html`:

```
python -m scripts.build_mobile_web          # sinh lại cả hai
python -m scripts.build_mobile_web --check  # chỉ kiểm tra, không ghi
```

`tests/stage6/test_mobile_web_builds.py` sinh lại vào thư mục tạm và đòi
byte-identical, nên khác biệt sẽ thành test failure chứ không ship đi.

## Vì sao lại tách ra đây

Trước đây trang mobile nằm trong `apps/mobile/web.py` dưới dạng một chuỗi Python,
với `const api = '/tracking'` viết cứng — nghĩa là nó chỉ chạy được same-origin,
tức là chỉ khi điện thoại mở trực tiếp từ máy chủ xưởng.

Giờ `web/index.html` là **trang nguồn**. `apps/mobile/web.py` chỉ đọc và trả về
byte của từng tệp khi có request, không dịch newline.

## Ba route, ba bản build

| Route | Tệp | Địa chỉ máy chủ |
|---|---|---|
| `/tracking/mobile` | `index.html` | trang nguồn |
| `/tracking/mobile/vps` | `vps.html` | nhập tay — điện thoại ngoài LAN |
| `/tracking/mobile/lan` | `lan.html` | cố định `location.origin` |

Chúng là ba tệp riêng chứ không phải một trang kèm cờ hiệu, để hai bản không thể
trôi lẫn vào nhau: điện thoại trong xưởng **không bao giờ được hiện** màn hình
nhập địa chỉ máy chủ — màn hình đó chỉ có nghĩa ngoài LAN. Chính vì vậy
`lan.html` cố tình **không** byte-identical với `index.html`.

## Địa chỉ máy chủ resolve lúc chạy

`index.html` tự tìm địa chỉ máy chủ theo thứ tự:

1. `localStorage['hms-server-origin']` — đã lưu từ màn KẾT NỐI MÁY CHỦ
2. `location.origin` — khi trang được chính máy chủ HMS QR serve (path bắt đầu `/tracking/`)
3. rỗng — bắt buộc mở màn KẾT NỐI MÁY CHỦ

Nhờ vậy đổi URL Cloudflare quick tunnel **không cần redeploy Vercel**: mở app →
bấm ô MÁY CHỦ → dán URL mới → Lưu.

## Bật cross-origin trên máy chủ

Mặc định máy chủ **không** cho cross-origin — bản chỉ dùng LAN giữ nguyên nguyên
trạng same-origin. Để frontend Vercel gọi được, đặt biến môi trường trước khi
khởi động server:

```bat
set HMS_QR_CORS_ORIGINS=https://ten-app.vercel.app
```

Nhiều origin thì phân cách bằng dấu phẩy **hoặc xuống dòng** — cả hai đều được.
`CHAY_WEB.bat` đọc danh sách từ `D:\HMS-QR-DATA\cors-origins.txt`, mỗi origin
một dòng. Không bao giờ dùng `*`.

## Đăng nhập

Trang mobile giờ đăng nhập bằng tài khoản server có sẵn (`/admin-api/api/v1/auth/login`),
nhận token ký và gửi kèm `Authorization: Bearer …` cho mọi request. Token sống 8
giờ; hết hạn thì app tự mở lại màn đăng nhập.

Route `/tracking/mobile` **không** yêu cầu auth — chính trang đó chứa form đăng
nhập, chặn nó thì không còn cách nào đăng nhập.

## Deploy lên Vercel

1. Push repo lên GitHub (đã có sẵn remote).
2. Vercel → Add New Project → import repo này.
3. **Root Directory: `web`** — đây là bước dễ sai nhất; để trống sẽ deploy nhầm
   thư mục gốc của repo Python.
4. Framework Preset: **Other**. Không có build command, không có output directory.
5. Deploy. Mỗi lần push `main` sau đó Vercel tự deploy lại.

## Domain production

**`https://hms-qr-product-manager-web.vercel.app`**

Project Vercel tên là **`hms-qr-product-manager-web`** (có hậu tố `-web`), không
phải `hms-qr-product-manager`. Project cũ đó là rác - mọi alias đều trả 404
`DEPLOYMENT_NOT_FOUND`, bản deploy duy nhất còn lại cũ hơn mọi commit trong repo,
và GitHub commit-status trỏ vào `hms-qr-product-manager-web`. Nên xóa đi.

Domain này phải được ghi vào `D:\HMS-QR-DATA\cors-origins.txt` trên máy chạy
server, nếu không trình duyệt sẽ chặn mọi request từ trang production.

## Truy vết ai cấp phát QR

Khi thợ chọn một chi tiết chưa có mã, trang gửi kèm header `X-Actor` chứa tên
tài khoản đang đăng nhập. Server ghi tên đó vào bảng `tracking_audit_events`,
và lịch sử của chi tiết (`GET /tracking/api/v1/tracking-items/{id}/history`)
sẽ hiện dòng `QR_ISSUED` kèm tên người cấp phát.

Nếu không gửi header, server ghi chuỗi `"development-user"` — một cái tên
không trả lời được câu hỏi ai đã làm. Header này không thuộc nhóm
CORS-safelisted nên trình duyệt phải preflight; `allow_headers` của middleware
đã bao gồm `X-Actor`.

## HTTPS là bắt buộc

Trang production chạy HTTPS, và trình duyệt không cho phép một trang HTTPS gọi
một origin HTTP. Vì vậy **server HMS QR phải được phơi ra ngoài qua HTTPS**.
`CHAY_WEB.bat` làm đúng điều này: server chạy HTTP nội bộ, TLS được kết thúc tại
Cloudflare tunnel. Một server LAN thuần HTTP sẽ không hoạt động.

Đã kiểm chứng toàn bộ hành trình thật trên domain production (16/16): mở trang,
trỏ origin tunnel, đăng nhập, chọn chi tiết, cấp phát QR, quét lại payload.

## Chạy cục bộ

Không cần gì đặc biệt — mở `web/index.html` bằng Live Server, hoặc để chính máy
chủ HMS QR serve tại `http://<ip>:8010/tracking/mobile`.

## Tem cửa không khớp
Server tính `qr_identity_consistent` cho mỗi lần quét: payload QR còn khớp với
item nó trả về không. Tem in trước khi thông tin chi tiết bị sửa vẫn resolve
được, vì scan trả item bằng `tracking_code`. Khi không khớp, page hiện cảnh báo
trong thẻ sản phẩm; pick chi tiết khác xóa nó, vì payload của pick do server tạo.
## Trạng thái "đang gia công" chỉ còn một cách viết
Trước đây một chi tiết có thể mang trạng thái `IN_PROCESS` hoặc
`IN_PRODUCTION` tùy nơi ghi vào: import Excel xuất ghi `IN_PRODUCTION`, còn
đường tính trạng thái tự động ghi `IN_PROCESS`. Vì thế mọi chỗ đọc đều phải cộng
cả hai lại — portal cộng, báo cáo Excel cộng, và trang web phân nhánh trên cả
hai. Giờ chỉ còn `IN_PROCESS` được ghi. `IN_PRODUCTION` vẫn nằm trong
`TrackingStatus` vì dòng đã lưu trước đây vẫn còn mang chữ đó, và
`BEING_MACHINED` là chỗ duy nhất biết hai cách viết là một trạng thái.
## Ai là người thực hiện
Mỗi ghi nhận trong luồng tracking đều ghi operator được chọn trong danh
sách, không phải tài khoản đăng nhập — trên máy dùng chung, một lần đăng
nhập nhiều thợ tự chọn tên mình. Header `X-Actor` ưu tiên operator đó; chỉ
khi chưa chọn ai nó mới fallback về tài khoản đăng nhập.
## Khi có lỗi
Picker và cấp phát QR đều nói rõ bước nào thất bại, không đổ lỗi cho bước
khác. Catalog không tải được và cấp phát QR không được là hai thông báo
riêng; nếu chúng im lặng, lần quét tiếp theo sẽ báo "không tìm thấy mã QR"
dù thất bại ở bước ghi.
Hai nút NGƯỜI DÙNG và CÔNG ĐOẠN trước đây cũng im lặng: bấm vào không mở
được danh sách thì không có picker cũng không có thông báo. Bây giờ chúng nói
rõ nguyên nhân, và picker vẫn bị ẩn khi không tải được dữ liệu.
Ô nhập mã QR có ghi "Dán mã QR hoặc nhập tay", nên gõ tay là đường thường
dùng nhất. Trước đây một mã nhập sai và một mã không tồn tại đều báo "không
tìm thấy dữ liệu cho mã QR này" — chỉ trong trường hợp thứ hai mới đúng.
Bây giờ trang đọc thông báo của máy chủ, nên mã nhập sai sẽ nói đúng mã đó sai
gì.
Cả hai ô số lượng (sự kiện và báo cáo gia công) đều được điền sẵn từ chi
tiết, nhưng vẫn xoá trắng được, và đều gửi lên dạng chuỗi. Một ô trống bị
server từ chối bằng 422 không nói rõ trường nào. Bây giờ hai chỗ đều kiểm tra
trước khi gửi, và đều tự báo "Vui lòng nhập số lượng lớn hơn 0" thay vì để
