# R011 triển khai HMS QR trên Machine A (bản nháp WP1A)

Tài liệu này là hướng dẫn chuẩn bị, không phải giấy phép thao tác sản xuất.
WP1A chỉ tạo artifact, schema, kế hoạch và bộ kiểm thử trên máy phát triển.
Không kết nối Machine A, không cài PostgreSQL, không đăng ký Windows Service,
không sửa firewall/registry/tài khoản/DPAPI/TLS và không ghi NAS.

## Quy trình được ủy quyền ở WP1A

1. Xác nhận Git HEAD/tree đúng baseline và worktree sạch.
2. Dựng release immutable bên ngoài repository; kiểm tra manifest, Git identity,
   SHA-256, kích thước và Alembic head.
3. Đọc inventory trong WP1B bằng collector read-only sau khi có ủy quyền riêng.
   Collector ghi rõ `UNKNOWN`, `ACCESS_DENIED`, `NOT_PRESENT` và không thu thập
   secret, password, connection string hoặc private key.
4. Reconcile deployment plan với inventory; preflight phải fail-closed.
5. Chạy dry-run để xem mutation manifest. Dry-run luôn có executed=false và
   machine mutation count bằng 0.

## Hướng dẫn inventory read-only cho WP1B (chưa được ủy quyền)

Collector đọc thông tin OS/phần cứng/volume, adapter và listener, firewall,
service, dấu hiệu PostgreSQL/Python/HMS, timezone/time service, trạng thái bảo
mật, certificate metadata và dấu hiệu pending reboot. Collector chỉ xuất JSON
ra stdout; không có tham số máy đích, remoting hay live-execute.

Collector không đọc giá trị secret, Credential Manager, connection string,
DPAPI plaintext, database password, browser/NAS credential hoặc certificate
private-key bytes. `HasPrivateKey` chỉ là metadata boolean. Trường hợp cần quyền
admin chỉ mở rộng khả năng đọc; operator không được sửa trạng thái máy để làm
inventory “PASS”. `UNKNOWN`, `ACCESS_DENIED`, `UNSUPPORTED` và `NOT_PRESENT` là
các kết quả khác nhau và phải được giữ nguyên trong evidence.

## Quy trình sản xuất dự kiến (chưa được thực hiện)

Sau khi có artifact, inventory, kế hoạch và quyền riêng cho từng work package:

- Xác minh release trước khi staging; giữ release trước đó trong
  `ROLLBACK_RELEASE_ROOT`.
- Dựng các root tượng trưng thành root vật lý được phê duyệt; không đặt dữ liệu
  bền vững trong release immutable.
- Cấu hình service wrapper với runtime, identity, config và log path đã được
  inventory/review phê duyệt. Restart phải có backoff hữu hạn và trạng thái lỗi
  cần operator xử lý.
- PostgreSQL phải là major 17, local-only, role ứng dụng least-privilege và
  Alembic là authority. Không tự động downgrade database khi rollback ứng dụng.
- TLS/firewall chỉ được thực hiện trong work package được ủy quyền; private key
  chỉ được tham chiếu qua secret store.
- Health/readiness phải chứng minh process, database và local storage; archive có
  thể OFFLINE theo chính sách local-first.

Các thao tác start/stop/restart sau này phải đi qua wrapper đã được WP1C chốt,
ghi pre/post-state, tuân stop timeout và restart backoff hữu hạn. Nếu vượt rapid
failure threshold, service giữ trạng thái lỗi thấy được để operator xử lý; không
restart vô hạn. Log nằm ngoài release tại `APP_LOG_ROOT`, có rotation/retention
và sanitizer. Secret rotation phải quiesce/reload, probe kết nối, rồi mới thu hồi
phiên bản cũ; evidence chỉ ghi reference/version, không ghi giá trị.

## Nâng cấp, rollback, gỡ bỏ

Update là stage → verify → preflight → activate → readiness → retain previous.
Rollback chỉ đổi application release khi schema tương thích; phục hồi database
là hành động operator riêng có backup/evidence. Gỡ bỏ mặc định chỉ xóa release
immutable và giữ `APP_DATA_ROOT`, `APP_LOG_ROOT`, `LOCAL_INGEST_ROOT`,
`SECRET_STORE`, `POSTGRESQL_DATA_ROOT`.

## Evidence và secret

Evidence phải chứa authority, baseline, release identity, inventory hash,
pre/post-state, planned/executed mutations, service/database/network state,
verification, rollback events và verdict. Dùng sanitizer dùng chung; không ghi
password, token, URL có credential, DPAPI plaintext hay private key.

`WP1B_MACHINE_A_READ_AUTHORIZED=NO` và `MACHINE_A_MUTATION_AUTHORIZED=NO` vẫn
được giữ nguyên sau WP1A.
