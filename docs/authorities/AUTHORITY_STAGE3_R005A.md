HMS QR PRODUCT MANAGER
STAGE 3 — R005A
QR PAYLOAD REQUIREMENT REMEDIATION
+ PROCESS CATALOG CORRECTION
+ LABEL FOUNDATION
+ FRESH INDEPENDENT REVIEW
+ INTEGRATION GATE

==================================================
TIẾN ĐỘ PHẦN MỀM
==================================================

Input candidate verdict:

PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005

Candidate branch:

stage3-tracking-qr-process-reporting

Candidate HEAD:

21b36128431cd202e202d0644363719547e14efc

Candidate tree:

63f4944da2a1549e5a51f425ba446b7294d71e8e

Accepted main baseline:

2aed6e945543d2d190bf932a30330032608f95e2

Main tree:

f956fc07e4f5503b7624c808ff18b22e305255ae

Current external review verdict:

REJECT_STAGE3_R005_REQUIREMENT_DRIFT_QR_PAYLOAD_AND_PROCESS_CATALOG

Target:

PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005A_INTEGRATED

KHUYẾN NGHỊ CODEX:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

==================================================
1. IMPORTANT — USER REQUIREMENT OVERRIDES R005
==================================================

R005 authority contained an obsolete QR assumption.

Current user requirement is authoritative.

QR PAYLOAD MUST CONTAIN EXACTLY THESE FOUR BUSINESS VALUES:

1. Tên sản phẩm
2. Khách hàng
3. Mã sản phẩm
4. Mã theo dõi riêng

QR MUST NOT contain:

- ngày giao hàng
- số lượng
- vật liệu
- size
- trạng thái
- PO
- internal order code
- process status
- machining type
- report data
- database UUID
- opaque-only resolver token

Do not preserve the obsolete requirement:

HMSQR:v1:<opaque-public-id>

as the sole QR payload.

==================================================
2. QR PAYLOAD CONTRACT
==================================================

Use a deterministic structured payload containing exactly four fields.

Conceptual example only:

{
  "product_name": "...",
  "customer_name": "...",
  "product_code": "...",
  "tracking_code": "..."
}

Field names/serialization may be normalized, but there must be exactly four
business information fields in the QR.

No delivery date.

No quantity.

No PO.

No extra hidden business value.

If technical serialization metadata would violate the "only four values"
requirement, do not embed it.

Document the exact canonical payload format.

==================================================
3. SERVER RESOLUTION
==================================================

After QR scan:

1. Decode the four fields.
2. Use tracking_code as the authoritative lookup key.
3. Query server.
4. Display current/live server data.

The embedded Product/Customer/Product Code values may be used for:

- human-readable offline identification;
- consistency checking;
- diagnostics.

But server data resolved by tracking_code is authoritative for mutable fields.

==================================================
4. DELIVERY DATE RULE — MUST REMAIN TRUE
==================================================

Delivery date is NOT in QR.

Therefore:

change delivery date
25/08 → 30/08

must keep:

tracking_code unchanged
QR payload bytes unchanged
printed QR pattern unchanged

Scan same QR afterwards:

server returns current delivery date = 30/08.

Regression test this explicitly.

==================================================
5. NEW ORDER RULE
==================================================

If user chooses:

TẠO ĐƠN MỚI

create:

new order identity
new tracking item
new tracking_code
new QR

Because tracking_code changes,
QR payload necessarily changes.

Product Master may remain the same.

==================================================
6. QR PUBLIC ID REVIEW
==================================================

R005 introduced qr_public_id.

Review whether it still has useful internal meaning.

It MAY remain internally if required for:

- QR issuance records
- print history
- audit
- internal lifecycle

BUT:

it must NOT be the only data encoded in the QR.

It must not replace tracking_code as scan lookup identity.

Do not retain unnecessary architecture merely because R005 implemented it.

If qr_public_id/reissue semantics are now redundant,
simplify safely and document the migration.

Do not break Tracking Item identity.

==================================================
7. SCAN RESPONSE
==================================================

After server lookup, mobile/web must display at least:

Tên sản phẩm
Khách hàng
Mã sản phẩm
Mã theo dõi riêng
Ngày giao hàng hiện tại
Số lượng
Trạng thái

PO/order may also be displayed from server.

Remember:

displayed server data != QR payload.

==================================================
8. MACHINING TYPE CATALOG DEFECT
==================================================

Current R005 seed/catalog omitted:

TẠO PHÔI

Correct baseline catalog to include at least:

TẠO PHÔI
TIỆN
PHAY
CẮT DÂY

Optional/current additional types may remain:

MÀI
NHIỆT LUYỆN
KHÁC

Catalog remains configurable.

Do not turn this into Routing.

==================================================
9. USER PREFERENCE REMAINS
==================================================

Machining type selection stays saved by USER.

Example:

User A → PHAY

close web
open again

User A → PHAY restored.

There must still be:

ĐỔI LOẠI GIA CÔNG

Changing user must load that user's own preference.

==================================================
10. ATTEMPT EXPANSION REMAINS
==================================================

Attempt expansion remains keyed by:

tracking_item_id + machining_type_id

Example:

ITEM-A + PHAY → 9
ITEM-A + TIỆN → 3
ITEM-B + PHAY → 3

Do not convert it to user-global state.

==================================================
11. LABEL PRINTING — SEPARATE FROM QR PAYLOAD
==================================================

CRITICAL:

QR PAYLOAD
and
VISIBLE PRINTED LABEL TEXT

are separate concepts.

QR itself contains only the four specified values.

The printed label may show additional current information outside the QR.

Baseline label fields:

Tên sản phẩm
Khách hàng
Mã sản phẩm
Mã theo dõi riêng

Vật liệu
Số lượng
Kích thước / Size
Xử lý bề mặt
Ngày giao hàng
PO / mã đơn

Optional:

Ghi chú ngắn

==================================================
12. LABEL BEHAVIOR WHEN DELIVERY DATE CHANGES
==================================================

Changing delivery date:

QR does not change.

If user wants paper label to display the new delivery date:

reprint label.

Reprinted label:

same QR payload
same tracking code
updated visible delivery-date text.

==================================================
13. LABEL TEMPLATE FOUNDATION
==================================================

Do not build a huge final label designer.

Create clean template/service architecture so later we can have:

TEM NHỎ
TEM TIÊU CHUẨN
TEM ĐẦY ĐỦ

Fields should be configurable where practical.

QR generation logic must not be coupled to visible label formatting.

Concept:

QrPayloadService
LabelDataService
LabelTemplateRenderer
Print/ExportService

Names may differ.

==================================================
14. TEST — EXACT QR CONTENT
==================================================

Add regression proving decoded QR payload contains exactly:

product name
customer name
product code
tracking code

Assert absence of:

delivery date
quantity
material
size
surface treatment
PO
status
internal UUID

Do not only compare generated image existence.

Actually decode/inspect canonical QR payload in test.

==================================================
15. TEST — CHANGE DELIVERY DATE
==================================================

Create Tracking Item.

Generate QR payload P1.

Change delivery date.

Generate/read QR payload P2.

Required:

P1 == P2

tracking_code unchanged.

Then scan/resolve server:

delivery date == new date.

==================================================
16. TEST — NEW ORDER
==================================================

Original:

tracking code A
QR payload A

Create as new order.

New:

tracking code B
QR payload B

Required:

A != B

Product Master may be same.

==================================================
17. TEST — PRINT LABEL
==================================================

Label test must prove:

QR component decodes to only four required fields.

Visible label data separately contains:

material
quantity
size
surface treatment
delivery date
order/PO

Generated test assets:

TEST ROOT ONLY.

==================================================
18. TEST — TẠO PHÔI
==================================================

Machining catalog must include:

TẠO PHÔI

Test:

user selects TẠO PHÔI
preference saved
reload
TẠO PHÔI restored

Attempt state:

tracking item + TẠO PHÔI

must remain independent from PHAY/TIỆN.

==================================================
19. FRESH R005 REVIEW
==================================================

After remediation, rerun fresh independent-style Stage 3 review.

Review all important areas:

Tracking Item
identity semantics
change delivery date
new-order transaction
QR payload
QR decode
scan resolution
operator
user preference
machining catalog
attempt display
ĐÃ XONG
process reports
idempotency
report revision
desktop
mobile web
SQLAlchemy
Alembic
label foundation
Stage 0–2 regression
test isolation

Do not use R005 old results as substitute.

==================================================
20. MOBILE REVIEW
==================================================

At mobile viewport, confirm:

user visible
machining type visible
ĐỔI LOẠI GIA CÔNG
Product name
Customer
Product code
Tracking code
Delivery date
Quantity
Status
LẦN 1
LẦN 2
LẦN 3
+ THÊM LẦN
ĐÃ XONG

No horizontal overflow.

Camera real-device remains a separate future gate.

==================================================
21. FULL TEST MATRIX
==================================================

Run fresh:

Stage 0 regression
Stage 1 regression
Stage 2 regression
Stage 3 focused tests
QR payload tests
QR delivery-date stability
new-order identity
label tests
user preference
attempt state
ĐÃ XONG
idempotency
revision history
desktop smoke
mobile/browser smoke
Alembic migration smoke

Then:

python scripts/check_test_isolation.py

Required:

TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION

Run:

git diff --check

PASS required.

==================================================
22. WARNING POLICY
==================================================

Existing:

STARLETTE_HTTPX_DEPRECATION_EXTERNAL_NON_BLOCKING

may remain if unchanged.

Any new own-code warning must be audited.

==================================================
23. REMEDIATED CANDIDATE
==================================================

Commit only bounded Stage 3 remediation.

Record:

REMEDIATED_HEAD=
REMEDIATED_TREE=

Working tree clean.

Report:

R005A_CHANGED_PATH_COUNT=
R005A_UNRELATED_CHANGE_COUNT=

Expected:

R005A_UNRELATED_CHANGE_COUNT=0

==================================================
24. INTEGRATION GATE
==================================================

If fresh candidate review finds another real candidate defect:

REJECT_STAGE3_R005A_<REASON>

Do not merge.

If external blocker:

BLOCKED_STAGE3_R005A_<REASON>

Do not merge.

Only when fully approved:

APPROVE_STAGE3_R005A_INTEGRATION

then integrate to main.

==================================================
25. MAIN INTEGRATION
==================================================

Before integration verify main remains exactly:

HEAD:
2aed6e945543d2d190bf932a30330032608f95e2

Tree:
f956fc07e4f5503b7624c808ff18b22e305255ae

Working tree clean.

If drift:

STOP.

Prefer fast-forward only.

No squash.
No rebase.
No force.
No remote push in this authority.

==================================================
26. POST-INTEGRATION
==================================================

After integration rerun fresh critical suite including:

QR exact payload
change-date same QR
new-order new QR
TẠO PHÔI
user preference
attempt state
ĐÃ XONG
process reports
full regression
Alembic smoke
test isolation

Record:

MAIN_HEAD=
MAIN_TREE=

Working tree must be CLEAN.

==================================================
27. CHECKPOINT
==================================================

Create:

docs/checkpoints/CHECKPOINT_STAGE3_R005A_INTEGRATION.md

Record:

R005 rejected candidate identity
requirement drift
remediation
QR payload contract
label/QR separation
TẠO PHÔI correction
tests
remediated candidate
integration method
main HEAD/tree
known gaps
next action

==================================================
28. PROJECT STATE
==================================================

If successful:

PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005A_INTEGRATED

Stage 3:
100%

Known gaps:

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
NAS_WRITE_PIPELINE_NOT_YET_EXECUTED
MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED
QC_WORKFLOW_NOT_YET_IMPLEMENTED
PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED

Do not relabel these PASS.

==================================================
29. NEXT ACTION
==================================================

If Stage 3 closes successfully, next major business stage should be:

QC
+
NG RETURN
+
PACKING
+
DELIVERY STATUS

Do not implement it inside R005A.

==================================================
30. CHAT POLICY
==================================================

Continue current Codex chat if context remains healthy.

Do not change chat merely because Stage 3 closes.

==================================================
31. EXECUTE NOW
==================================================

Start from existing Stage 3 candidate.

Do not rebuild Stage 3 from scratch.

Do not merge obsolete R005 candidate.

Target:

PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005A_INTEGRATED