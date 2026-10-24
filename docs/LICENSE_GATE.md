# Cổng bản quyền HMS QR Desktop

Phần mềm HMS QR Desktop chỉ mở được khi máy đó có bản quyền hợp lệ. Cổng
bản quyền (licence gate) chạy **trước tiên**, ngay sau khi tạo `QApplication`
và **trước khi** kết nối Server hoặc mở cửa sổ chính.

Trước đây (commit `ce9f3eb`) hệ thống bản quyền cũ đã bị xóa vì *không có ai
gọi* nó — trông có vẻ được áp dụng nhưng không có gì chặn cả. Cổng bản quyền
này được kiểm chứng bằng test: trạng thái bị khóa thì `run()` không bao giờ
được gọi.

## Bật áp dụng

Cổng chỉ hoạt động khi cả ba biến môi trường sau đều có giá trị:

| Biến | Nội dung |
| --- | --- |
| `HMS_QR_LICENSE_SERVER_URL` | URL máy chủ bản quyền, ví dụ `http://192.168.2.10:9000` |
| `HMS_QR_LICENSE_PUBLIC_KEY_PEM` | Khóa công khai Ed25519 của máy chủ. Chấp nhận **đường dẫn tới file PEM** hoặc **nội dung PEM** |
| `HMS_QR_LICENSE_FILE_KEY` | Khóa mã hóa file offline, dạng hex 64 ký tự (32 byte) |

Thiếu một trong ba biến thì cổng bản quyền không hoạt động — phần mềm chạy như
trước, không khóa ai cả.

## Trạng thái và hành động

| Trạng thái từ máy chủ | Ứng xử |
| --- | --- |
| `ok`, `offline-ok`, `server-error` | Cho chạy. `offline-ok`/`server-error` nghĩa là máy chủ không trả lời được nhưng license trên máy vẫn tốt — không khóa khách vì mất mạng |
| `grace` | Hiện banner "còn N ngày" (không chặn) rồi cho chạy |
| `expired`, `revoked` | Hiện màn hình khóa, không cho chạy |
| `no-license`, `hwid-mismatch`, `hwid-error`, bất kỳ trạng thái lạ nào | Mở cửa sổ kích hoạt |

Thời gian ân hạn là **5 ngày** sau khi hết hạn (`hms_license.license.GRACE_DAYS`).

## Hai đường kích hoạt

1. **Online** — nhập mã kích hoạt, phần mềm gọi máy chủ và tự lưu license.
2. **Offline** — cho máy không có mạng:
   - Bấm "Kích hoạt offline" → chọn nơi lưu **file yêu cầu** (`.req`).
   - Gửi file đó cho nhà cung cấp, nhận về **file license** (`.lic`).
   - Bấm lại "Kích hoạt offline" → chọn file license vừa nhận.

Cả hai đường đều chỉ thành công khi license ký đúng, đúng máy này và đúng
sản phẩm `HMS-QR`.

## Màn hình khóa

Khi bản quyền hết hạn hoặc bị thu hồi, màn hình khóa hiện lý do bằng tiếng
Việt với hai nút: "Kích hoạt lại" và "Thoát". Phím Esc và nút đóng cửa sổ
**không tắt được** màn hình này — chỉ có kích hoạt thành công hoặc bấm "Thoát".

## Vendored lại SDK

Sáu file trong `packages/hms_license/` là bản sao nguyên byte từ nhánh
`feat/license-key-system` của repo licence-key. Khi SDK đổi, copy đúng sáu file
`.py` đó vào thư mục trên, không sửa nội dung, rồi chạy:

```
python -m pytest tests/test_desktop_license_gate.py -q
```

## Kiểm thử

```
python -m pytest tests/test_desktop_license_gate.py -q
python -m pytest tests/stage1/test_desktop.py tests/stage1/test_product_api_client.py -q
```
