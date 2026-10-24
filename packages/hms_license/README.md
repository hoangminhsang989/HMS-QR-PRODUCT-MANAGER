# hms_license — SDK bản quyền (vendored)

Six files in this folder are the client SDK for the HMS licence system, copied
byte-for-byte from the `feat/license-key-system` branch of the licence-key
repository. They are the source of truth: do not edit them here.

What each file does:

| File | Vai trò |
| --- | --- |
| `__init__.py` | Xuất các API công khai của SDK. |
| `crypto.py` | Ed25519 ký/kiểm tra, AES-256-GCM mã hóa file. |
| `license.py` | Payload, chữ ký và chính sách trạng thái (`ok`/`grace`/`expired`/`revoked`). |
| `files.py` | Định dạng file yêu cầu và file license mã hóa. |
| `hwid.py` | Dấu vân tay máy (CPU, ổ đĩa, mainboard, MAC). |
| `client.py` | `LicenseClient`: kích hoạt online, kiểm tra lúc khởi động, luồng offline. |

Cách dùng trong HMS QR: `apps/desktop/license_gate.py` nạp SDK này. Sáu file
trên import lẫn nhau bằng tên `hms_license`, nên `license_gate._vendored_sdk()`
đăng ký một module object dưới cả hai tên `hms_license` và
`packages.hms_license`. Nhờ đó sáu file giữ nguyên byte gốc.

Cách vendored lại: copy đúng sáu file `.py` trên từ nhánh
`feat/license-key-system` của repo licence-key vào thư mục này, không sửa gì,
rồi chạy `python -m pytest tests/test_desktop_license_gate.py -q`.
