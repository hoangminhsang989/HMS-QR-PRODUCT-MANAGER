# R011 triển khai HMS QR trên Machine A — trạng thái sau D2

Tài liệu này là hướng dẫn vận hành có ranh giới authority, không phải giấy phép
thao tác sản xuất. WP1A và R011 D2 đã được delivery tới canonical/remote `main`
ở commit `b492719343405ee7fdb224f2e1001ef96ded4ebb`, tree
`6036d8d51cd04c1e928f4a94ee37e39bdf5560b2`. Gate kế tiếp chỉ được chọn, chưa
được chạy. Không kết nối Machine A, không chạy production, không cài
PostgreSQL, không đăng ký Windows Service, không sửa firewall/registry/tài
khoản/DPAPI/TLS và không ghi NAS theo authority reconciliation hiện tại.

## Chuỗi source-side đã delivered

1. Xác nhận Git HEAD/tree đúng baseline và worktree sạch.
2. Dựng release immutable bên ngoài repository; kiểm tra manifest, Git identity,
   SHA-256, kích thước và Alembic head.
3. Đọc inventory bằng collector read-only chỉ sau khi có authority Gate C riêng.
   Collector ghi rõ `UNKNOWN`, `ACCESS_DENIED`, `NOT_PRESENT` và không thu thập
   secret, password, connection string hoặc private key.
4. Reconcile deployment plan với inventory; preflight phải fail-closed.
5. Chạy dry-run để xem mutation manifest. Dry-run luôn có executed=false và
   machine mutation count bằng 0.

Các mục trên mô tả capability và thứ tự; chúng không tự cấp quyền thực thi.
R011 D2 đã đóng Gate A (canonical Git identity) và Gate B (exact deployment
artifact/tooling identity). Không được dùng trạng thái delivered đó để suy diễn
quyền Machine A.

## Gate C kế tiếp đã chọn (chưa được ủy quyền)

```text
GATE_NAME=R011_GATE_C_MACHINE_A_READ_ONLY_CURRENT_STATE_INVENTORY_AND_D2_PREFLIGHT
PURPOSE=Refresh and reconcile current Machine A facts and the four preserved foundation mutations before any D2 production execution or further mutation.
READ_ONLY_OR_MUTATING=READ_ONLY
MACHINE_A_REQUIRED=YES
NETWORK_REQUIRED=NO
UAC_REQUIRED=NO
PRODUCTION_ROOT_READ_REQUIRED=YES_METADATA_ONLY
PRODUCTION_ROOT_MUTATION_REQUIRED=NO
```

Prerequisite tối thiểu: canonical/origin `main` đúng `b492719...`, tree
`6036d8d...`; closure index SHA-256 đúng `107e7fc...`; Stage-0, payload,
runtime và bundle đúng code-owned identity; Recovery-A snapshot và cumulative
mutation count `4`; host/root/service-account name và SID đúng frozen authority;
collector secret-free; evidence root mới bên ngoài repo. Không remoting, không
production write và không tự động hóa authentication.

Gate chỉ PASS khi collector chạy local trên Machine A dưới standard token; Git,
artifact và tooling identity khớp; OS/host/volume/time/listener/service/
PostgreSQL/runtime/firewall/root/account metadata được ghi trung thực; root
final-path/reparse metadata và account name/SID/state khớp; bốn historical
mutations được reconcile; không che giấu state bất ngờ; `ACCESS_DENIED`,
`UNKNOWN`, `NOT_PRESENT`, `UNSUPPORTED` vẫn phân biệt; field bắt buộc unresolved
hoặc contradictory phải block readiness; UAC và mutation đều bằng `0`; output
được sanitize và hash-index.

Gate fail-closed khi identity drift, child/ACL/account/service/state bất ngờ,
field bắt buộc unavailable hoặc contradictory, secret exposure, write/UAC/
remoting attempt, hoặc evidence mismatch. Gate này chưa được thực thi.

## Hướng dẫn inventory read-only cho Gate C

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

`GATE_C_MACHINE_A_READ_AUTHORIZED=NO` và `MACHINE_A_MUTATION_AUTHORIZED=NO` vẫn
được giữ nguyên cho đến khi có fresh authority riêng.

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
