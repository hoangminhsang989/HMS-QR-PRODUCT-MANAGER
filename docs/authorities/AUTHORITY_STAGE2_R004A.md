HMS QR PRODUCT MANAGER
STAGE 2 — CUSTOMER + PO + PRODUCTION RUN
R004A — INDEPENDENT REVIEW + WARNING AUDIT + INTEGRATION GATE

==================================================
TIẾN ĐỘ PHẦN MỀM
==================================================

Previous candidate verdict:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004

Candidate branch:

stage2-customer-po-production-run

Candidate HEAD:

b4cc1c12145aaecaaa05af6640cda08c5781131d

Candidate tree:

580ae68d1ff94503b12239bb829006f75ee3badc

Main expected baseline:

bc9e8f0aecd2a2fd1644937365d6b088794ef77c

Main expected tree:

2b823a55b6f464161a265f3bff61bbbae73638d7

Expected working tree:
clean

Target final verdict:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004A_INTEGRATED

KHUYẾN NGHỊ CODEX:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

==================================================
1. PURPOSE
==================================================

Authority này là:

INDEPENDENT REVIEW
+
WARNING AUDIT
+
INTEGRATION GATE

Không triển khai Stage 3.

Không thêm Routing.
Không thêm Operation.
Không thêm QR.
Không thêm Mobile.
Không thêm QC.

Mục tiêu:

1. Review fresh toàn Stage 2 candidate.
2. Tái chạy test độc lập.
3. Audit 3 warning hiện có.
4. Phân biệt warning vô hại với defect thật.
5. Chỉ sửa warning nếu xác nhận là candidate defect/config defect và bounded.
6. Freeze candidate mới nếu có remediation.
7. Fresh review lại sau remediation.
8. Chỉ integrate main khi toàn gate PASS.
9. Post-integration regression.
10. Đóng Stage 2.

==================================================
2. ROOT POLICY
==================================================

Production:

F:\PHAN-MEM-QUAN-LY-QR

Test/temp/runtime duy nhất:

F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST

NAS:

\\192.168.1.58\data-pm-qr

Không ghi test lên NAS.

Không tạo runtime artifact trong production root.

==================================================
3. PRECHECK
==================================================

Xác nhận chính xác:

repo
branch
candidate HEAD/tree
main HEAD/tree
working tree
test root

Expected:

Candidate:
b4cc1c12145aaecaaa05af6640cda08c5781131d

Main:
bc9e8f0aecd2a2fd1644937365d6b088794ef77c

Nếu drift không giải thích được:

BLOCK.

==================================================
4. FULL DIFF REVIEW
==================================================

Review toàn diff:

main baseline

bc9e8f0aecd2a2fd1644937365d6b088794ef77c

→

candidate

b4cc1c12145aaecaaa05af6640cda08c5781131d

Kiểm tra ít nhất:

Customer domain
Customer code generator
PurchaseOrder
PurchaseOrderLine
DeliveryScheduleEntry
ProductionRun
Quantity invariants
SQLAlchemy models
Repository/service layer
Alembic
API
Desktop UI
Excel export
Configuration
Tests
Documentation

Báo:

DIFF_REVIEW_FILE_COUNT=
UNRELATED_CHANGE_COUNT=

Expected:

UNRELATED_CHANGE_COUNT=0

==================================================
5. DOMAIN RELATIONSHIP REVIEW
==================================================

Xác minh:

Customer 1:N PO

PO 1:N PO Line

Product 1:N PO Line

PO Line 1:N Delivery Schedule

PO Line 1:N Production Run

Production Run N:1 Product

Không duplicate master Product data không cần thiết.

Không dùng Product.quantity làm ordered/manufacturing/delivery quantity chung.

==================================================
6. QUANTITY INVARIANT REVIEW
==================================================

Fresh test và code review:

ordered_quantity > 0

planned_quantity > 0

completed_quantity >= 0

completed_quantity <= planned_quantity

aggregate Delivery Schedule planned quantity
không vượt PO Line ordered quantity

aggregate Production Run planned quantity
không vượt PO Line ordered quantity

Kiểm tra update path, không chỉ create path.

Đặc biệt thử:

- tạo 2 run vừa đủ quantity;
- update một run làm tổng vượt;
- tạo nhiều delivery entry;
- update entry khiến tổng vượt.

Nếu update path bỏ lọt aggregate validation:

REJECT.

==================================================
7. FOREIGN KEY / OWNERSHIP REVIEW
==================================================

Test sai quan hệ:

- PO dùng customer không tồn tại
- PO Line dùng product không tồn tại
- PO Line gắn sai PO
- Production Run product không khớp PO Line product
- Delivery Schedule gắn PO Line không tồn tại

Không chỉ dựa vào UI validation.

Server/application layer phải bảo vệ invariant.

==================================================
8. BUSINESS IDENTIFIER REVIEW
==================================================

Review:

customer_code
po_number
run_code

Phải:

- unique;
- error rõ;
- generator/service tách biệt;
- không phụ thuộc UI;
- không silently overwrite.

Concurrency production chưa cần PASS.

Giữ gap nếu chưa test PostgreSQL concurrency.

==================================================
9. SQLALCHEMY REVIEW
==================================================

Kiểm tra:

- session lifecycle
- transaction behavior
- rollback khi validation/repository failure
- relationships
- foreign keys
- uniqueness constraints
- Decimal handling
- timezone handling

Không để session/resource mở sau request/test.

Nếu có resource lifecycle tương tự Excel Stage 1:
phải sửa trước integration.

==================================================
10. ALEMBIC REVIEW
==================================================

Fresh migration smoke trong TEST ROOT:

fresh DB
→ alembic upgrade head
→ schema inspect
→ repository smoke

Không dùng production DB.

Status đúng:

ALEMBIC_SQLITE_MIGRATION_SMOKE_PASS

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED

==================================================
11. WARNING AUDIT — BẮT BUỘC
==================================================

Hiện candidate báo 3 warning classes:

A.
Starlette/httpx deprecation

B.
Pydantic Decimal serializer warning cho completed quantity mặc định

C.
Alembic path_separator deprecation

Mỗi warning phải được phân loại:

DEPENDENCY_EXTERNAL_NON_BLOCKING

hoặc

CANDIDATE_CONFIGURATION_DEFECT

hoặc

CANDIDATE_SERIALIZATION_DEFECT

hoặc classification chính xác tương đương.

Không bỏ qua warning chỉ vì test xanh.

==================================================
12. PYDANTIC DECIMAL WARNING
==================================================

Ưu tiên audit kỹ warning này.

Kiểm tra:

- model field type
- default type
- response serialization
- request parsing
- DB round-trip
- JSON output

Nếu field khai báo Decimal nhưng default là float/int/string không đúng contract:

sửa thành typed Decimal default phù hợp.

Không suppress warning.

Không filter warning để test xanh.

Thêm regression chứng minh:

- create Production Run default completed quantity;
- response JSON đúng;
- DB persisted value đúng;
- no Pydantic serializer warning từ own code.

Nếu warning là candidate defect:
bắt buộc remediate trước integration.

==================================================
13. ALEMBIC PATH_SEPARATOR WARNING
==================================================

Audit config Alembic.

Nếu deprecated local config của project:

sửa theo supported configuration hiện tại.

Không suppress warning.

Chạy migration smoke lại.

Nếu warning do own config:
phải loại bỏ.

==================================================
14. STARLETTE / HTTPX WARNING
==================================================

Xác định warning đến từ:

third-party compatibility/deprecation

hay own invocation.

Nếu hoàn toàn external và không có safe bounded fix cần thiết:

giữ:

STARLETTE_HTTPX_DEPRECATION_EXTERNAL_NON_BLOCKING

Không upgrade/downgrade dependency rộng chỉ để làm mất warning.

Không thay dependency production tùy tiện.

==================================================
15. API REVIEW — CUSTOMER
==================================================

Fresh tests:

POST customer
GET list
GET one
PATCH
duplicate code
404
search
active filter
pagination

==================================================
16. API REVIEW — PO
==================================================

Fresh:

create PO
duplicate po_number
read
list
update
invalid customer
status validation

PO Line:

create
multiple lines
invalid quantity
wrong product
wrong PO
duplicate line number

==================================================
17. API REVIEW — DELIVERY SCHEDULE
==================================================

Fresh:

single entry
multiple entries
update
over-allocation create
over-allocation update
invalid date/quantity
status validation

==================================================
18. API REVIEW — PRODUCTION RUN
==================================================

Fresh:

create
multiple runs
read/list
filter
planned quantity
completed quantity
over-allocation create
over-allocation update
invalid PO Line/Product relation
status validation

==================================================
19. DESKTOP REVIEW
==================================================

Fresh offscreen smoke:

KHÁCH HÀNG

ĐƠN HÀNG / PO

LỊCH SẢN XUẤT

Kiểm tra:

- create/edit flows
- master/detail relations
- status display
- quantity validation
- delivery schedule editor
- production run editor

Không cần pixel-perfect review trong authority này.

==================================================
20. EXCEL REVIEW
==================================================

Fresh export test:

Customer
PO number
Product
Ordered quantity
Delivery schedule
Production Run status

Nếu multiple delivery entries:

xác nhận export không mất entry.

Workbook phải đóng resource đúng.

Generated workbook:

TEST ROOT only.

Stage 1 Excel lifecycle tests phải tiếp tục PASS.

==================================================
21. STAGE 1 REGRESSION
==================================================

Bắt buộc chạy toàn Stage 1 regression.

Không được tái phát:

EXCEL_PREVIEW_LEAVES_WORKBOOK_OPEN

==================================================
22. FULL REGRESSION
==================================================

Chạy toàn suite fresh.

Báo:

passed
failed
skipped
warnings
duration

Không lấy số 16 passed từ R004 làm evidence mới.

==================================================
23. ISOLATION
==================================================

Cuối test:

python scripts/check_test_isolation.py

Expected:

TEST_ISOLATION_PASS

và:

NO_RUNTIME_ARTIFACTS_IN_PRODUCTION

==================================================
24. STATIC
==================================================

git diff --check

PASS required.

Review untracked files.

Không bỏ qua dirty working tree.

==================================================
25. REVIEW VERDICT BEFORE ANY FIX
==================================================

Nếu fresh review candidate không phát hiện defect:

APPROVE_STAGE2_R004A_INTEGRATION

Nếu warning audit phát hiện bounded defect:

không merge.

Remediate trên candidate branch.

Sau đó tạo new candidate identity và rerun fresh gate.

Nếu functional defect:

REJECT_STAGE2_R004A_<REASON>

==================================================
26. REMEDIATION POLICY
==================================================

Nếu cần fix:

chỉ sửa defect đã review xác nhận.

Allowed bounded scope:

- Decimal serialization/default
- Alembic deprecated config
- resource lifecycle
- Stage2 invariant bug
- directly related tests

Không refactor lan rộng.

Commit message rõ nghĩa.

Record:

REMEDIATED_HEAD=
REMEDIATED_TREE=

==================================================
27. FRESH REVIEW AFTER REMEDIATION
==================================================

Sau remediation:

working tree clean.

Rerun:

full Stage 2 review
Stage 1 regression
Stage 2 tests
migration smoke
desktop smoke
Excel
isolation
git diff --check

Không dùng pre-remediation results.

Chỉ sau đó:

APPROVE_STAGE2_R004A_INTEGRATION

==================================================
28. INTEGRATION
==================================================

Chỉ khi APPROVE.

Checkout main.

Expected HEAD:

bc9e8f0aecd2a2fd1644937365d6b088794ef77c

Expected clean.

Nếu main drift:

STOP.

Ưu tiên fast-forward only nếu graph cho phép.

Không squash.
Không rebase.
Không force.
Không push remote.

==================================================
29. POST-INTEGRATION TEST
==================================================

Sau main integration chạy fresh:

- Stage1 regression
- Stage2 regression
- migration smoke
- Excel lifecycle/export
- desktop smoke
- isolation

Record:

MAIN_HEAD=
MAIN_TREE=

Working tree:
CLEAN

==================================================
30. CHECKPOINT
==================================================

Tạo:

docs/checkpoints/CHECKPOINT_STAGE2_R004A_INTEGRATION.md

Ghi:

candidate identity
review findings
warning classifications
remediation nếu có
remediated identity
fresh test matrix
integration method
main HEAD/tree
post-integration evidence
known gaps
next action

==================================================
31. PROJECT STATE
==================================================

Nếu PASS:

Current verdict:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004A_INTEGRATED

Stage 2 progress:

100%

Next exact action:

STAGE3_ROUTING_OPERATIONS_QR_ISSUANCE_R005

Known gaps giữ chính xác:

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED

TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE

NAS_WRITE_PIPELINE_NOT_YET_EXECUTED

MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED

MOBILE_QR_NOT_YET_IMPLEMENTED

QC_WORKFLOW_NOT_YET_IMPLEMENTED

==================================================
32. FINAL VERDICT
==================================================

Target:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004A_INTEGRATED

Không gọi PASS nếu:

- aggregate update validation fail
- relation validation fail
- own-code Decimal warning chưa xử lý
- Alembic own config warning chưa xử lý
- regression fail
- isolation fail
- main chưa integration

==================================================
33. FINAL REPORT
==================================================

Bắt đầu:

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

candidate HEAD/tree
reviewed file count
unrelated change count
quantity invariant review
relationship review
warning audit classifications
remediation nếu có
remediated HEAD/tree
Customer tests
PO tests
Delivery tests
Production Run tests
SQLAlchemy status
Alembic status
API status
Desktop status
Excel status
Stage1 regression
full regression
isolation
integration method
main HEAD/tree
working tree
known gaps
next exact action

==================================================
34. CHAT POLICY
==================================================

Nếu R004A PASS:

Ưu tiên:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

Stage 3 vẫn liên quan trực tiếp đến Production Run.

Chỉ đổi chat nếu context thật sự đã trở nên nặng sau review này.

==================================================
35. START
==================================================

Thực hiện ngay.

Không triển khai Stage 3 trước.

Mục tiêu:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004A_INTEGRATED