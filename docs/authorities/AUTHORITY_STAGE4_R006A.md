HMS QR PRODUCT MANAGER
STAGE 4 — QC + NG RETURN + PACKING + DELIVERY
R006A — INDEPENDENT REVIEW + INTEGRATION GATE

==================================================
TIẾN ĐỘ PHẦN MỀM
==================================================

Input candidate verdict:

PASS_STAGE4_QC_PACKING_DELIVERY_R006

Candidate branch:

stage4-qc-packing-delivery

Candidate HEAD:

c37587f06144ba4176e7df830a0e2a8af67927b7

Candidate tree:

c98c4132b52b910ff75e354b818c02be257036fe

Accepted main baseline:

fd2148a4c89ecde4c399addc41858c63106c452d

Accepted main tree:

ef85816744cfc56e002802c851d2266a489f3cd0

Expected main working tree:

CLEAN

Target:

PASS_STAGE4_QC_PACKING_DELIVERY_R006A_INTEGRATED

KHUYẾN NGHỊ CODEX:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

==================================================
1. PURPOSE
==================================================

Authority này chỉ thực hiện:

INDEPENDENT REVIEW
+
BOUNDED REMEDIATION NẾU CẦN
+
INTEGRATION GATE
+
POST-INTEGRATION VERIFICATION

Không triển khai Stage tiếp theo.

Không NAS production write.
Không PostgreSQL production.
Không Cloudflare deployment.
Không real iPhone/Android camera acceptance.
Không exact legacy Excel template.

==================================================
2. PRECHECK
==================================================

Xác nhận:

Repository:
F:\PHAN-MEM-QUAN-LY-QR

Candidate branch:
stage4-qc-packing-delivery

Candidate HEAD:
c37587f06144ba4176e7df830a0e2a8af67927b7

Candidate tree:
c98c4132b52b910ff75e354b818c02be257036fe

Main HEAD:
fd2148a4c89ecde4c399addc41858c63106c452d

Main tree:
ef85816744cfc56e002802c851d2266a489f3cd0

Working tree:
clean

Nếu identity drift không giải thích được:

BLOCK.

Không discard user changes.

==================================================
3. ROOT / TEST ISOLATION
==================================================

Production:

F:\PHAN-MEM-QUAN-LY-QR

Test root duy nhất:

F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST

NAS:

\\192.168.1.58\data-pm-qr

Không ghi test lên NAS.

Không tạo runtime artifacts trong production root.

==================================================
4. FULL DIFF REVIEW
==================================================

Review toàn diff:

main baseline

fd2148a4c89ecde4c399addc41858c63106c452d

→ candidate

c37587f06144ba4176e7df830a0e2a8af67927b7

Review tối thiểu:

- Stage4 domain/event model
- tracking_workflow_events
- application services
- status projection
- quantity calculations
- revision model
- idempotency
- API
- Desktop
- Mobile web
- Alembic migration
- tests
- docs

Báo:

DIFF_REVIEW_FILE_COUNT=
UNRELATED_CHANGE_COUNT=

Expected:

UNRELATED_CHANGE_COUNT=0

==================================================
5. EVENT SOURCE-OF-TRUTH REVIEW
==================================================

Xác minh:

QC_CHECKED
SHORTAGE_REPORTED
QC_NG_RETURNED_TO_MACHINING
PACKED
DELIVERED
GENERAL_REPORT

được lưu dạng event/history.

Tracking Item current status chỉ là projection.

Không được có business path chỉ update current status mà không tạo event.

Không được xóa event cũ khi revision.

==================================================
6. REVISION — CRITICAL REVIEW AREA
==================================================

Đây là gate quan trọng nhất R006A.

Fresh test tất cả quantity-bearing event revision.

Ví dụ:

SHORTAGE:
R1 shortage=4
R2 correction shortage=2

Effective shortage phải là 2,
không phải 6,
không phải 4.

PACKING:
R1 packed=10
R2 correction packed=8

Effective packed contribution phải là 8.

DELIVERY:
R1 delivered=6
R2 correction delivered=4

Effective delivered contribution phải là 4.

QC/NG tương tự nếu projection hoặc summary dùng quantity.

Superseded revision không được tiếp tục cộng vào aggregate.

==================================================
7. REVISION MUST REVALIDATE DOWNSTREAM INVARIANTS
==================================================

Test các trường hợp sửa báo cáo làm vi phạm dữ liệu downstream.

Ví dụ:

Tracking quantity = 20

Packed = 20
Delivered = 20

Sau đó revise PACKED từ 20 → 15.

Kết quả không được tạo state:

delivered 20 > packed 15.

Policy phải fail correction hoặc xử lý transactionally theo business rule rõ.

Ưu tiên:

REJECT INVALID REVISION

không tự sửa delivery lịch sử.

Tương tự:

shortage revise tăng lên
→ available-to-pack giảm
→ nếu packed hiện có vượt available mới
→ revision phải bị từ chối.

==================================================
8. SHORTAGE SEMANTICS
==================================================

Fresh test:

Tracking qty = 20
shortage 2
available-to-pack = 18

Revision shortage 2 → 1:
available = 19

Revision shortage 2 → 5:
available = 15

Nếu packed hiện tại = 18:
revision shortage → 5 phải fail.

Không silently tạo invalid aggregate state.

==================================================
9. MULTIPLE SHORTAGE EVENTS
==================================================

Review semantics khi có nhiều shortage events.

Xác định rõ:

- shortage events là additive;
- hay mỗi event đại diện snapshot/correction chain.

Nếu nhiều independent shortage events được phép:
effective shortage = sum current active revisions.

Không double-count superseded revisions.

Document chính xác.

==================================================
10. NG / REWORK REVIEW
==================================================

Test:

process report
→ QC NG
→ status QC_NG

new machining report same QR
→ REWORK

QC checked after rework
→ appropriate checked status

Second NG cycle
→ still supported.

Không tạo QR mới.

Không reset report/attempt history.

==================================================
11. GENERAL REPORT
==================================================

GENERAL_REPORT:

- phải có history
- idempotency
- revisions nếu supported
- KHÔNG thay đổi workflow status

Fresh regression bắt buộc.

==================================================
12. PACKING AGGREGATE
==================================================

Fresh tests:

full packing
partial packing
multiple events
revision of packing event
over-pack create
over-pack revision
zero
negative

Formula phải dựa trên active/current revisions only.

==================================================
13. DELIVERY AGGREGATE
==================================================

Fresh:

partial delivery
multiple delivery events
revision of delivery event
over-delivery create
over-delivery revision

Required:

effective delivered <= effective packed

planned delivery date không bị thay bởi actual delivery event.

==================================================
14. IDEMPOTENCY
==================================================

Fresh tests mỗi class:

QC
SHORTAGE
NG
PACKED
DELIVERED
GENERAL_REPORT

Same request UUID + same semantic request:

one event.

Same request UUID reused for:

different item
different event type
different payload incompatible

must fail closed.

Revision request IDs cũng phải có policy rõ nếu revision endpoint supports idempotency.

==================================================
15. TRANSACTION ROLLBACK
==================================================

Inject failures at appropriate points.

Required atomicity:

event append
+
supersession state
+
projection update

must commit or rollback together.

No half-applied revision.

No event without projection update.

No projection update without event.

==================================================
16. STATUS PROJECTION REVIEW
==================================================

Fresh sequence:

Tracking Item
→ machining
→ WAITING_QC
→ QC NG
→ REWORK
→ QC CHECKED
→ PACKING
→ PACKED
→ PARTIALLY_DELIVERED
→ DELIVERED

Review exact transition result after each operation.

Also test:

GENERAL_REPORT does not disturb projection.

==================================================
17. API STRUCTURED ERRORS
==================================================

Fresh test:

invalid quantity
not-found tracking item
not-found operator
invalid revision
over-pack
over-delivery
invalid shortage correction
idempotency conflict

No raw SQLAlchemy/traceback error returned as normal client response.

==================================================
18. DESKTOP REVIEW
==================================================

Fresh offscreen/controller smoke:

Tracking Item table
QC summary
NG summary
packed
delivered
current status
history

Actions:

ĐÃ KIỂM TRA
THIẾU HÀNG
NG
ĐÃ ĐÓNG GÓI
ĐÃ GIAO HÀNG
BÁO CÁO

Must create real application events.

No placeholder-only buttons.

==================================================
19. MOBILE WEB REVIEW
==================================================

Fresh mobile viewport review around 390x844.

Confirm:

GIA CÔNG
QC / GIAO HÀNG

QC controls:

ĐÃ KIỂM TRA
THIẾU HÀNG
NG TRẢ LẠI NC CHỜ XỬ LÝ
ĐÃ ĐÓNG GÓI
ĐÃ GIAO HÀNG
BÁO CÁO

Product card still shows:

Tên sản phẩm
Khách hàng
Mã sản phẩm
Mã theo dõi riêng
Ngày giao
Số lượng
Trạng thái

No horizontal overflow.

No own-code console errors/warnings.

==================================================
20. STAGE 3 NON-REGRESSION
==================================================

Required PASS:

QR payload exactly four fields

product_name
customer_name
product_code
tracking_code

Delivery date change:
same QR.

New order:
new tracking code + new QR.

TẠO PHÔI exists.

User machining preference persists.

Attempt expansion:
tracking item + machining type.

ĐÃ XONG remains separate completion event.

Process report revision/idempotency remains PASS.

==================================================
21. STAGE 0–2 REGRESSION
==================================================

Required PASS:

Product Master
Excel lifecycle
Customer
PO
PO Line
Delivery Schedule
Production Run
quantity invariants
SQLAlchemy/Alembic

==================================================
22. ALEMBIC REVIEW
==================================================

Test:

fresh DB → head

and:

Stage3 DB
→ Stage4 upgrade

Then repository/service smoke.

Existing data preserved.

Report:

ALEMBIC_SQLITE_MIGRATION_SMOKE_PASS

Do not claim PostgreSQL PASS.

==================================================
23. WARNING AUDIT
==================================================

Current known warning:

STARLETTE_HTTPX_DEPRECATION_EXTERNAL_NON_BLOCKING

May remain if unchanged and still external.

Any new own-code warning:

must be classified and remediated before approval.

==================================================
24. FULL REGRESSION
==================================================

Run fresh full suite.

Report exact:

passed
failed
skipped
warnings
duration

Do not reuse R006 numbers as fresh evidence.

==================================================
25. ISOLATION
==================================================

Run:

python scripts/check_test_isolation.py

Required:

TEST_ISOLATION_PASS

NO_RUNTIME_ARTIFACTS_IN_PRODUCTION

Also verify no test artifacts on NAS.

==================================================
26. STATIC
==================================================

Run:

git diff --check

Review:

tracked
untracked
dirty state

PASS required.

==================================================
27. PRE-INTEGRATION VERDICT
==================================================

If real candidate defect found:

REJECT_STAGE4_R006A_<REASON>

Do not merge.

If bounded candidate defect found:

remediate only related scope,
add regression,
freeze new candidate,
rerun fresh full review.

If external blocker:

BLOCKED_STAGE4_R006A_<REASON>

Only when fresh review passes:

APPROVE_STAGE4_R006A_INTEGRATION

==================================================
28. REMEDIATION POLICY
==================================================

Allowed bounded remediation examples:

- aggregate/revision calculation bug
- invalid downstream-invariant revision
- projection bug
- idempotency conflict bug
- transaction rollback bug
- API error mapping
- directly related tests

Do not refactor unrelated Stage 0–3 architecture.

Record:

REMEDIATED_HEAD=
REMEDIATED_TREE=

==================================================
29. INTEGRATION
==================================================

Only after APPROVE.

Checkout main.

Before FF expected:

HEAD:
fd2148a4c89ecde4c399addc41858c63106c452d

Tree:
ef85816744cfc56e002802c851d2266a489f3cd0

Working tree:
clean

If main drift:
STOP.

Fast-forward only if possible.

No squash.
No rebase.
No force.
No remote push.

==================================================
30. POST-INTEGRATION FRESH VERIFICATION
==================================================

After integration run fresh critical suite:

Stage4 revisions/aggregates
packing
delivery
NG/rework
idempotency
Stage3 QR/process
Alembic
Desktop
Mobile smoke
full regression
test isolation

Record:

MAIN_HEAD=
MAIN_TREE=
MAIN_WORKING_TREE=CLEAN

==================================================
31. CHECKPOINT
==================================================

Create:

docs/checkpoints/CHECKPOINT_STAGE4_R006A_INTEGRATION.md

Include:

input candidate identity
review findings
revision/aggregate audit
remediation if any
fresh tests
approval
integration method
final main HEAD/tree
known gaps
next exact action

==================================================
32. PROJECT STATE
==================================================

If PASS:

Current verdict:

PASS_STAGE4_QC_PACKING_DELIVERY_R006A_INTEGRATED

Stage 4:

100%

Known gaps remain:

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED

TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE

NAS_WRITE_PIPELINE_NOT_YET_EXECUTED

MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED

MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED

PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED

==================================================
33. NEXT EXACT ACTION
==================================================

Do NOT start next stage in R006A.

After Stage4 integrated, recommended next development mega-WP:

NAS STORAGE
+
PRODUCT IMAGES / ATTACHMENTS
+
BACKUP FOUNDATION
+
EXACT EXCEL TEMPLATE PREPARATION

Production PostgreSQL/Machine A remains later because Machine A is not currently available.

==================================================
34. CHAT POLICY
==================================================

After Stage4 review, evaluate context honestly.

If current chat still manageable:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

If Stage3 + Stage4 logs have now made context genuinely heavy:

create full checkpoint + HANDOFF
then:

TẠO CHAT CODEX MỚI

Do not switch mechanically.

==================================================
35. FINAL REPORT FORMAT
==================================================

TIẾN ĐỘ PHẦN MỀM

Stage:
WP:
Revision:
Stage progress:
Overall progress:
Verdict:
Blocker:

KHUYẾN NGHỊ CODEX

Then report:

candidate identity
diff review
revision aggregate review
shortage semantics
NG/rework
packing
delivery
idempotency
transactionality
API
Desktop
Mobile
Alembic
Stage3 regression
full regression
isolation
warnings
remediation identity if applicable
integration method
final main HEAD/tree
known gaps
next exact action

==================================================
36. EXECUTE NOW
==================================================

Start fresh independent review of:

c37587f06144ba4176e7df830a0e2a8af67927b7

Do not implement the next stage.

Target:

PASS_STAGE4_QC_PACKING_DELIVERY_R006A_INTEGRATED