HMS QR PRODUCT MANAGER
STAGE 2 — CUSTOMER + PO + PRODUCTION RUN
MEGA AUTHORITY R004

==================================================
TIẾN ĐỘ PHẦN MỀM
==================================================

Previous Stage:
Stage 1 — Product Master

Previous verdict:
PASS_STAGE1_PRODUCT_MASTER_R003A_INTEGRATED

Current main:

Repository:
F:\PHAN-MEM-QUAN-LY-QR

Branch:
main

HEAD:
bc9e8f0aecd2a2fd1644937365d6b088794ef77c

Tree:
2b823a55b6f464161a265f3bff61bbbae73638d7

Expected working tree:
clean

Current Stage:
Stage 2

WP:
Customer + PO + Production Run vertical slice

Revision:
R004

Target verdict:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004

KHUYẾN NGHỊ CODEX:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

==================================================
1. PHẠM VI R004
==================================================

Xây vertical slice nghiệp vụ:

CUSTOMER
   ↓
PURCHASE ORDER / PO
   ↓
PO LINE
   ↓
PRODUCT
   ↓
PRODUCTION RUN
   ↓
DELIVERY SCHEDULE

Mục tiêu là từ Product Master hiện có tạo được dữ liệu đơn hàng sản xuất thực tế.

R004 phải cho phép ít nhất:

1. Tạo khách hàng.
2. Tạo PO cho khách hàng.
3. Thêm nhiều dòng sản phẩm vào PO.
4. Gán quantity/order data.
5. Tạo một hoặc nhiều Production Run từ PO line.
6. Theo dõi quantity planned/produced.
7. Tạo nhiều lịch giao hàng cho một PO line.
8. Hiển thị toàn bộ chuỗi trên Desktop.
9. Có API/service/persistence đầy đủ.
10. Export dữ liệu liên quan ra Excel generic.

R004 KHÔNG triển khai:

- QR issuance;
- mobile scan;
- công đoạn gia công chi tiết;
- QC workflow;
- packing workflow hoàn chỉnh;
- giao hàng transaction hoàn chỉnh;
- authentication production;
- NAS production write;
- Machine A deployment.

==================================================
2. ROOT POLICY
==================================================

Production source:

F:\PHAN-MEM-QUAN-LY-QR

Test/temp/runtime duy nhất:

F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST

Không được tạo runtime artifact trong production root.

Tất cả:

- SQLite DB
- Excel test
- logs
- screenshots
- pytest temp
- cache
- coverage
- migration test DB
- export test

phải nằm TEST ROOT.

Sau verification bắt buộc:

TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION

==================================================
3. BRANCH
==================================================

Từ main accepted baseline tạo:

stage2-customer-po-production-run

Không implement trực tiếp trên main.

Preflight:

git status --short
git rev-parse HEAD
git rev-parse HEAD^{tree}

Nếu baseline drift hoặc working tree dirty không giải thích được:

BLOCK.

==================================================
4. CUSTOMER DOMAIN
==================================================

Customer tối thiểu:

internal UUID
customer_code
name
short_name
address
tax_code
contact_name
phone
email
notes
active
created_at
updated_at
created_by
updated_by

Không bắt buộc mọi field phải required.

customer_code phải unique.

Không dùng integer DB ID làm business identity.

Ví dụ:

CUS-000001

Generator/policy phải tách service.

==================================================
5. PURCHASE ORDER
==================================================

PO tối thiểu:

internal UUID
po_number
customer_id
po_date
requested_delivery_date
status
notes
created_at
updated_at
created_by
updated_by

PO status semantic baseline:

DRAFT
CONFIRMED
IN_PRODUCTION
PARTIALLY_COMPLETED
COMPLETED
CANCELLED
HOLD

Không dùng màu làm status.

po_number là business identifier.

Cho phép PO number do người dùng nhập vì nhiều khách hàng đã có PO riêng.

Không tự overwrite nếu trùng.

==================================================
6. PO LINE
==================================================

PO phải có nhiều PO Line.

PO Line tối thiểu:

internal UUID
po_id
product_id
line_number
ordered_quantity
unit
unit_price optional
currency optional
customer_part_reference optional
notes

Quan trọng:

Product.quantity hiện tại không được coi là nguồn duy nhất cho quantity đơn hàng.

Phải bắt đầu tách rõ:

Product:
master/reference information

PO Line:
ordered quantity

Production Run:
planned/manufacturing quantity

Future QC:
checked/pass/ng quantity

Future Delivery:
delivered quantity

Không dùng một field quantity cho tất cả.

==================================================
7. DELIVERY SCHEDULE
==================================================

Workbook hiện tại có:

Lịch Vendor giao hàng

R004 phải chuyển concept này thành dữ liệu có cấu trúc.

Không chỉ lưu một chuỗi text nếu có thể tránh.

Tạo child entity/value object tương đương:

DeliveryScheduleEntry

Tối thiểu:

internal UUID
po_line_id
planned_date
planned_quantity
status
notes
created_at
updated_at

Status baseline:

PLANNED
CONFIRMED
PARTIAL
COMPLETED
CANCELLED

Một PO Line có thể có nhiều ngày giao.

Ví dụ:

PO Line:
100 pcs

Delivery:
30 pcs — 20/08
30 pcs — 25/08
40 pcs — 30/08

Validation:

Tổng planned quantity có thể:
- bằng ordered quantity;
- hoặc nhỏ hơn trong lúc đang lập lịch.

Nếu vượt ordered quantity:
warning/error policy phải rõ.

Không silently cho vượt nếu business rule không cho phép.

==================================================
8. PRODUCTION RUN
==================================================

Production Run là lần/lệnh sản xuất cụ thể.

Một PO Line có thể tạo nhiều Production Run.

Ví dụ:

PO line:
100 pcs

Run 1:
40 pcs

Run 2:
60 pcs

Production Run tối thiểu:

internal UUID
run_code
po_line_id
product_id
planned_quantity
completed_quantity
status
priority
planned_start
planned_finish
actual_start
actual_finish
notes
created_at
updated_at
created_by
updated_by

run_code business identifier.

Baseline ví dụ:

RUN-2026-000001

Generator tách service.

==================================================
9. PRODUCTION RUN STATUS
==================================================

Semantic status baseline:

PLANNED
RELEASED
IN_PROGRESS
ON_HOLD
WAITING_QC
COMPLETED
CANCELLED

R004 chưa triển khai routing/công đoạn thật.

Nhưng Production Run phải là anchor cho Stage QR tiếp theo.

Future relation:

Production Run
   ↓
Routing
   ↓
Operation
   ↓
QR
   ↓
Mobile report

==================================================
10. QUANTITY INVARIANTS
==================================================

Phải document và test rõ:

ordered_quantity > 0

planned_quantity > 0

completed_quantity >= 0

completed_quantity <= planned_quantity
trừ khi future policy cho over-production.

Tổng Production Run planned quantity của PO Line:

không được âm.

Nếu vượt ordered quantity:
phải có explicit policy.

Ưu tiên block vượt trong R004 nếu chưa có overproduction permission model.

Không silently accept.

==================================================
11. RELATIONSHIPS
==================================================

Baseline:

Customer
1 → N PurchaseOrder

PurchaseOrder
1 → N PurchaseOrderLine

Product
1 → N PurchaseOrderLine

PurchaseOrderLine
1 → N ProductionRun

PurchaseOrderLine
1 → N DeliveryScheduleEntry

ProductionRun
N → 1 Product

Không duplicate toàn bộ Product fields vào PO Line.

Nếu cần snapshot customer/product name cho historical display:
document strategy thay vì copy tùy tiện.

==================================================
12. PERSISTENCE NORMALIZATION
==================================================

Stage 1 hiện có SQLite DEV/test persistence.

R004 là thời điểm chuẩn hóa persistence trước khi domain mở rộng quá xa.

Ưu tiên đưa persistence sang:

SQLAlchemy 2.x

và chuẩn bị:

Alembic

Production target vẫn:

PostgreSQL trên Máy A

Automated R004 vẫn có thể chạy:

SQLite trong TEST ROOT.

Nếu Stage 1 repository hiện chưa SQLAlchemy:

migrate có kiểm soát Product persistence sang SQLAlchemy cùng Customer/PO/Run.

Phải giữ behavior/API Stage 1.

Không rewrite UI/business unnecessarily.

Không xóa dữ liệu người dùng production vì hiện chưa có production DB.

==================================================
13. ALEMBIC
==================================================

Thiết lập migration architecture.

Tạo initial/baseline schema migration phù hợp cho:

Product
Customer
PurchaseOrder
PurchaseOrderLine
ProductionRun
DeliveryScheduleEntry

Nếu SQLite migration smoke có thể chạy:

chạy trong TEST ROOT.

Không tuyên bố:

POSTGRESQL_MIGRATION_PASS

nếu chưa có PostgreSQL.

Status chính xác có thể là:

SQLALCHEMY_SQLITE_INTEGRATION_PASS

ALEMBIC_SQLITE_MIGRATION_SMOKE_PASS

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED

==================================================
14. API — CUSTOMER
==================================================

Versioned endpoints tối thiểu:

POST /api/v1/customers
GET  /api/v1/customers
GET  /api/v1/customers/{identifier}
PATCH /api/v1/customers/{identifier}

Hỗ trợ:

pagination
search
active filter

Structured errors.

==================================================
15. API — PO
==================================================

Tối thiểu:

POST /api/v1/purchase-orders
GET  /api/v1/purchase-orders
GET  /api/v1/purchase-orders/{identifier}
PATCH /api/v1/purchase-orders/{identifier}

PO line:

POST /api/v1/purchase-orders/{id}/lines

PATCH /api/v1/purchase-order-lines/{id}

GET /api/v1/purchase-orders/{id}/lines

Nếu endpoint naming khác tốt hơn:
được phép, nhưng phải nhất quán và document.

==================================================
16. API — DELIVERY SCHEDULE
==================================================

Tối thiểu:

POST delivery schedule entry
GET list by PO line
PATCH schedule entry

Không hard delete nếu chưa có policy.

Cancel/status transition tốt hơn hard delete.

==================================================
17. API — PRODUCTION RUN
==================================================

Tối thiểu:

POST /api/v1/production-runs
GET  /api/v1/production-runs
GET  /api/v1/production-runs/{identifier}
PATCH /api/v1/production-runs/{identifier}

Filters:

status
product
PO
customer
planned date range nếu hợp lý.

==================================================
18. APPLICATION SERVICE
==================================================

Không để API tự tính business rule.

Tách services như:

CustomerService
PurchaseOrderService
ProductionRunService
DeliveryScheduleService

Tên có thể thay đổi.

Business validations nằm application/domain layer.

==================================================
19. DESKTOP UI
==================================================

Mở rộng Desktop theo phong cách hiện tại:

dark mode
compact
high density
Vietnamese UI

Tạo tối thiểu các khu:

KHÁCH HÀNG

ĐƠN HÀNG / PO

LỆNH SẢN XUẤT

Có thể dùng tab/navigation hợp lý.

==================================================
20. CUSTOMER UI
==================================================

Tối thiểu:

list
search
create
edit
active/inactive

Không cần CRM đầy đủ.

==================================================
21. PO UI
==================================================

Master-detail ưu tiên:

PO list
   ↓
PO detail
   ↓
PO lines

Cho phép:

- chọn customer;
- nhập PO number;
- ngày PO;
- requested delivery date;
- thêm Product;
- ordered quantity;
- unit;
- notes;
- sửa line.

Validation rõ bằng tiếng Việt.

==================================================
22. DELIVERY SCHEDULE UI
==================================================

Từ PO line có thể mở lịch giao.

Cho phép:

- thêm ngày;
- quantity;
- trạng thái;
- note.

Hiển thị cảnh báo nếu tổng quantity lịch giao vượt ordered quantity.

Đây là nền để thay thế cột:

Lịch Vendor giao hàng

trong Excel hiện tại.

==================================================
23. PRODUCTION RUN UI
==================================================

Cho phép từ PO Line:

TẠO LỆNH SẢN XUẤT

Nhập:

planned quantity
priority
planned start
planned finish
notes

Hiển thị:

run code
product
PO
customer
quantity
status
timeline

==================================================
24. STATUS COLORS
==================================================

Desktop có thể báo màu semantic cho:

PO
Production Run
Delivery Schedule

Nhưng mapping màu vẫn ở presentation layer.

Không đưa màu vào database business state.

==================================================
25. EXCEL EXPORT EXTENSION
==================================================

Mở rộng generic Excel export để xuất được ít nhất:

Customer
PO number
Product code
Part name
Ordered quantity
Unit
Material
Requester
Surface treatment
Outsourced
Size
Notes
Delivery schedule summary
Production Run status

Không cần exact legacy workbook fidelity trong R004 nếu reference file chưa có trên DEV.

Giữ:

TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE

==================================================
26. DELIVERY SCHEDULE EXCEL REPRESENTATION
==================================================

Nếu một PO Line có nhiều DeliveryScheduleEntry:

generic export có thể:

- join thành formatted multi-line cell;
hoặc
- tạo separate delivery schedule sheet.

Codex đánh giá phương án maintainable hơn.

Không làm mất dữ liệu.

Không chỉ export schedule đầu tiên.

==================================================
27. EXCEL IMPORT
==================================================

Không bắt buộc import PO production đầy đủ từ legacy workbook nếu mapping chưa đủ chắc chắn.

Nhưng importer architecture phải mở rộng được.

Nếu legacy row không có PO number/product code rõ:

không tự suy diễn nguy hiểm.

Có thể giữ Product import hiện có và document:

LEGACY_PO_IMPORT_MAPPING_PENDING

Đây không phải blocker của R004 nếu PO CRUD vertical slice đạt.

==================================================
28. AUDIT
==================================================

Customer/PO/PO Line/Production Run/DeliverySchedule phải có:

created_at
updated_at
created_by
updated_by

UTC server authority.

Không cần full immutable event log ở R004 nhưng architecture phải tiếp tục tương thích.

==================================================
29. BUSINESS HISTORY
==================================================

Không hard delete PO đã có Production Run.

Không silently overwrite delivered/planned quantities.

Nếu delete chưa có policy:

không expose delete endpoint.

Use:

CANCELLED
inactive
archived

khi phù hợp.

==================================================
30. NAS
==================================================

Production NAS:

\\192.168.1.58\data-pm-qr

R004 vẫn:

KHÔNG ghi test lên NAS.

Business logic không hard-code UNC.

Storage abstraction Stage 1 phải tiếp tục giữ.

==================================================
31. MACHINE A
==================================================

Máy hiện tại là DEV WORKSTATION.

Không phải Máy A.

Không deploy production server trong R004.

Giữ:

MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED

==================================================
32. TEST MATRIX — CUSTOMER
==================================================

Tối thiểu:

customer create
customer update
duplicate customer_code
search
active filter
validation

==================================================
33. TEST MATRIX — PO
==================================================

Tối thiểu:

create PO
duplicate po_number policy
create PO line
multiple lines
invalid quantity
list/read/update
customer relation
product relation
status validation

==================================================
34. TEST MATRIX — DELIVERY
==================================================

Tối thiểu:

single schedule
multiple schedules
quantity totals
over-allocation behavior
update status
date validation

==================================================
35. TEST MATRIX — PRODUCTION RUN
==================================================

Tối thiểu:

create
multiple runs for one PO line
run code generation
planned quantity validation
completed quantity validation
over-allocation protection
search/filter
status

==================================================
36. TEST MATRIX — PERSISTENCE
==================================================

Fresh database in TEST ROOT.

Test:

Product compatibility
Customer relationships
PO relationships
Production Run relationships
Delivery Schedule relationships

Foreign-key behavior phải được test phù hợp.

==================================================
37. TEST MATRIX — MIGRATION
==================================================

Nếu SQLAlchemy/Alembic được triển khai:

fresh DB migration smoke

upgrade to head

schema presence

repository smoke

Không test DB trong production root.

==================================================
38. TEST MATRIX — API
==================================================

Fresh API tests cho:

Customer
PO
PO Line
Delivery Schedule
Production Run

Bao gồm:

happy path
404
validation
duplicate
filter/search
pagination nơi phù hợp

==================================================
39. TEST MATRIX — DESKTOP
==================================================

PySide6 offscreen/smoke:

Customer view
PO view
PO detail/lines
Delivery Schedule editor
Production Run view
validation

Không cần screenshot nếu không cần.

Nếu screenshot:
TEST ROOT only.

==================================================
40. STAGE 1 REGRESSION
==================================================

Bắt buộc giữ toàn bộ Stage 1 Product Master tests PASS.

Đặc biệt:

Excel lifecycle regression phải tiếp tục PASS.

Không được tái phát WinError 32.

==================================================
41. EXCEL REGRESSION
==================================================

Fresh:

generic import/export

workbook lifecycle

output open/read validation

generated files ở TEST ROOT.

==================================================
42. TEST ISOLATION
==================================================

Bắt buộc cuối authority:

python scripts/check_test_isolation.py

Expected:

TEST_ISOLATION_PASS

và:

NO_RUNTIME_ARTIFACTS_IN_PRODUCTION

==================================================
43. DIFF REVIEW
==================================================

Sau implementation review toàn diff:

main baseline
bc9e8f0aecd2a2fd1644937365d6b088794ef77c

→ R004 candidate

Báo:

DIFF_REVIEW_FILE_COUNT=
UNRELATED_CHANGE_COUNT=

Expected:

UNRELATED_CHANGE_COUNT=0

==================================================
44. GIT DIFF CHECK
==================================================

Chạy:

git diff --check

PASS required.

==================================================
45. PERFORMANCE
==================================================

List API phải có pagination.

Desktop không load relation theo cách gây N+1 nghiêm trọng nếu dễ tránh.

Không over-optimize premature.

==================================================
46. DOCUMENTATION
==================================================

Update phù hợp:

PROJECT_STATE.md
ARCHITECTURE.md
DATA_MODEL.md
DECISIONS.md
README.md nếu cần

Tạo:

docs/authorities/AUTHORITY_STAGE2_R004.md

docs/checkpoints/CHECKPOINT_STAGE2_R004.md

==================================================
47. ADR
==================================================

Ghi ADR nếu cần cho:

structured Delivery Schedule

PO/Production quantity semantics

SQLAlchemy/Alembic persistence normalization

Production Run anchor cho QR

Không ghi ADR cho chi tiết nhỏ.

==================================================
48. CHECKPOINT
==================================================

Checkpoint ghi tối thiểu:

baseline HEAD/tree
branch
candidate HEAD/tree
changed paths
data model
API status
desktop status
persistence status
migration status
Excel status
tests
known gaps
risks
next exact action

==================================================
49. ACCEPTANCE VERTICAL SLICE
==================================================

R004 PASS khi chứng minh được end-to-end:

Desktop
  ↓
Tạo Customer
  ↓
Tạo PO
  ↓
Thêm Product vào PO
  ↓
Ordered Quantity
  ↓
Delivery Schedule
  ↓
Tạo Production Run
  ↓
Persistence
  ↓
API/List/Search
  ↓
Excel Export

Và restart/reopen test persistence phù hợp vẫn đọc được dữ liệu.

==================================================
50. KNOWN GAPS KHÔNG ĐƯỢC PHÓNG ĐẠI
==================================================

Giữ chính xác nếu chưa thực hiện:

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED

TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE

NAS_WRITE_PIPELINE_NOT_YET_EXECUTED

MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED

MOBILE_QR_NOT_YET_IMPLEMENTED

QC_WORKFLOW_NOT_YET_IMPLEMENTED

==================================================
51. TARGET FOR NEXT STAGE
==================================================

Nếu R004 PASS, next exact action dự kiến:

STAGE3_ROUTING_OPERATIONS_QR_ISSUANCE_R005

Stage đó mới bắt đầu:

- công đoạn gia công;
- routing;
- Tạo phôi;
- Tiện lần 1/2/3;
- Phay lần 1/2/3;
- Cắt dây...
- QR issuance gắn Production Run.

Không implement các phần đó trước trong R004.

==================================================
52. CHAT POLICY
==================================================

Nếu R004 PASS nhưng context vẫn kiểm soát tốt:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

Không đổi chat chỉ vì số Stage tăng.

Nếu R004 sinh diff/test/log rất lớn và context bắt đầu nặng:
tạo checkpoint/handoff rồi mới đề nghị đổi.

==================================================
53. FINAL REPORT FORMAT
==================================================

Bắt đầu bằng:

TIẾN ĐỘ PHẦN MỀM

Stage:
WP:
Revision:

Stage progress:
Overall progress:

Verdict:

Blocker:

KHUYẾN NGHỊ CODEX

Sau đó báo:

baseline
branch
candidate HEAD/tree
changed paths
diff review count
unrelated change count
Customer status
PO status
PO Line status
Delivery Schedule status
Production Run status
SQLAlchemy status
Alembic status
API status
Desktop status
Excel status
full test matrix
Stage1 regression
test isolation
known gaps
next exact action

==================================================
54. MERGE POLICY
==================================================

R004 là implementation candidate.

KHÔNG merge main trong authority này nếu chưa có review/integration gate riêng.

Nếu local R004 PASS:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004

và giữ branch candidate để independent review tiếp theo.

==================================================
55. START
==================================================

Thực hiện ngay:

PRECHECK_STAGE2_R004
→ create branch
→ save authority
→ implement
→ focused verification
→ full regression
→ isolation
→ checkpoint
→ candidate commit(s)
→ final report

Không hỏi lại thông tin đã có.

Mục tiêu:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004