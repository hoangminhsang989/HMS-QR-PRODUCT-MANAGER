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

## Provisioner thư mục sản xuất sau Recovery-A

Module duy nhất được duy trì là `packages.deployment.provisioning`, chạy bằng:

```text
python -m packages.deployment.provisioning --target-root <ROOT> --service-account <ACCOUNT>
```

Mặc định lệnh chỉ dry-run và xuất một JSON có trạng thái tổng thể, role còn
thiếu/đã đúng, collision, reparse, kiểm tra security, partial state và số
mutation. Chỉ authority sản xuất riêng trong tương lai mới được thêm `--apply`.
Stage implementation/offline qualification không được chạy vào
`D:\HMS-QR-PROD`, không UAC và không mutation Machine A.

Tranche đầu tối thiểu chỉ gồm:

- `releases`: release immutable, service chỉ read/execute;
- `runtime`: Python runtime cô lập, service chỉ read/execute;
- `staging`: vùng stage do SYSTEM/Administrators quản lý, service không có ACE.

`data`, `ingest`, `logs`, `backups`, `secrets`, `rollback` được hỗ trợ bởi cùng
role catalog nhưng hoãn đến tranche có consumer tương ứng. Không tạo top-level
`temp`; temp phải là workspace có phạm vi và lifecycle rõ ràng.

Provisioner kiểm tra root đã tồn tại, không phải reparse, owner/DACL root khớp
precondition được review. Nó không tự take ownership, không sửa DACL root và
không xóa collision. Directory mới nhận protected DACL ngay trong
`CreateDirectoryW`; SYSTEM và BUILTIN\Administrators giữ recovery access, còn
service nhận quyền theo từng role. Nếu một role thành công rồi role sau lỗi,
state hợp lệ đã tạo được giữ nguyên; sửa nguyên nhân rồi chạy lại để hội tụ.

Chuỗi `WP2H-C-R1`/R1A/R1B/R1C/R1D/R1E/R1F và kiến trúc executor/finalizer theo
micro-revision đã nghỉ hẳn. Không chạy hoặc dùng byte R1E làm future authority.
