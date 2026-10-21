# Web app mobile — HMS QR

Giao diện mobile (PWA) của HMS QR. Một thư mục tĩnh thuần, **không build step**:
Vercel phục vụ đúng như máy chủ LAN phục vụ, cùng một tệp `index.html`.

```
web/
  index.html        toàn bộ app: HTML + CSS + JS inline
  manifest.json     PWA manifest (start_url "/" — Vercel phục vụ web/ ở gốc domain)
  sw.js             service worker, chỉ cache tài nguyên cục bộ
  vercel.json       cache header + security header cho Vercel
  static/           jsqr.min.js (quét QR), icon, favicon
```

## Vì sao lại tách ra đây

Trước đây trang mobile nằm trong `apps/mobile/web.py` dưới dạng một chuỗi Python,
với `const api = '/tracking'` viết cứng — nghĩa là nó chỉ chạy được same-origin,
tức là chỉ khi điện thoại mở trực tiếp từ máy chủ xưởng.

Giờ `web/index.html` là **nguồn duy nhất**. `apps/mobile/web.py` chỉ đọc và trả
về tệp đó, nên bản chạy trên LAN và bản chạy trên Vercel là byte-identical.

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

## Tem cu khong khop

Server tinh `qr_identity_consistent` cho moi lan quet: payload QR con khớp với
item no tra ve khong. Tem in trước khi thông tin chi tiết bị sửa van resolve
duợc, vi scan tra item bằng `tracking_code`. Khi không khớp, page hiện canh bao
trong the san pham; pick chi tiet khac xoa no, vi payload của pick do server tao.

## Ai la nguoi thuc hien

Moi ghi nhan trong luong tracking deu ghi operator duoc chon trong danh
sach, khong phai tai khoan dang nhap — tren may dung chung, mot lan dang
nhap nhieu tho tu chon ten minh. Header `X-Actor` uu tien operator do; chi
khi chua chon ai no moi fallback ve tai khoan dang nhap.

## Khi co loi

Picker va cap phat QR deu noi ro buoc nao that bai, khong do loi cho buoc
khac. Catalog khong tai duoc va cap phat QR khong duoc la hai thong bao
rieng; neu chung im lang, lan quet tiep theo se bao "khong tim thay ma QR"
du that bai o buoc ghi.

Hai nut NGUOI DUNG va CONG DOAN truoc day cung im lang: bam vao khong mo
duoc danh sach thi khong co picker cung khong co thong bao. Bay chung noi
ro nguyen nhan, va picker van bi an khi khong tai duoc du lieu.

O nhap ma QR co ghi "Dán mã QR hoặc nhập tay", nen go tay la duong thuong
dung nhat. Truoc day mot ma nhap sai va mot ma khong ton tai deu bao "khong
tim thay du lieu cho ma QR nay" - chi trong truong hợp thu hai moi dung.
Bay trang doc thong bao cua may chu, nen ma nhap sai se noi dung ma do sai
gi.

Ca hai o so luong (su kien va bao cao gia cong) deu duoc dien san tu chi
tiet, nhung van xoa trang duoc, va deu gui len dang chuoi. Mot o trong bi
server tu choi bang 422 khong noi ro truong nao. Bay hai cho deu kiem tra
truoc khi gui, va deu tu bao "Vui long nhap so luong lon hon 0" thay vi de
operator nhan mot thong bao chung.

Viet lai o chung: mot ham doc thong bao loi cua server, mot ham doc o so
luong. Truoc day moi cho tu viet lai mot ban, do cung la ly do loi xuat hien
hai lan. Bay ghi them mot cho ghi moi la khong the quen duoc nua.

Nut "xem them lan" truoc day tang so lan hien thi TRUOC khi gui len server va
khong xem ket qua. Neu server tu choi (mo rong phai tang dan), trang van hien
them ba nut ma server khong co, va operator khong biet gi. Bay gio chi tang
khi server dong y, va thong bao loi lay nguyen loi do cua server.

May chu tra loi loi trong hai dang: `_error()` boc thanh
`{error:{message}}`, con `HTTPException` va kiem tra du lieu cua FastAPI tra
ve `{detail:...}`. Trang doc ca hai, nen mot truong bi tu choi se hien dung
nguyen nhan tu may chu thay vi bi thay bang "Khong the ghi su kien".
