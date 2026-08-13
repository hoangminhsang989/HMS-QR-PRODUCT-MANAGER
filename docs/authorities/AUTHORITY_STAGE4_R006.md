HMS QR PRODUCT MANAGER
STAGE 4 — QC + NG RETURN + PACKING + DELIVERY STATUS
MEGA AUTHORITY R006

==================================================
TIẾN ĐỘ PHẦN MỀM
==================================================

Previous verdict:

PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005A_INTEGRATED

Repository:

F:\PHAN-MEM-QUAN-LY-QR

Accepted branch:

main

Accepted HEAD:

fd2148a4c89ecde4c399addc41858c63106c452d

Accepted tree:

ef85816744cfc56e002802c851d2266a489f3cd0

Expected working tree:

CLEAN

Current Stage:

Stage 4

WP:

QC
+
NG RETURN
+
PACKING
+
DELIVERY STATUS

Revision:

R006

Target candidate verdict:

PASS_STAGE4_QC_PACKING_DELIVERY_R006

KHUYẾN NGHỊ CODEX:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

==================================================
1. BUSINESS OBJECTIVE
==================================================

Mở rộng Tracking Item hiện tại để hỗ trợ chuỗi:

Gia công/report
        ↓
QC
        ↓
PASS / THIẾU HÀNG / NG
        ↓
nếu NG → TRẢ LẠI NC CHỜ XỬ LÝ
        ↓
QC lại nếu cần
        ↓
ĐÓNG GÓI
        ↓
GIAO HÀNG

Không tạo Routing engine.

Không biến QC thành Production Run routing step.

Tracking Item vẫn là anchor nghiệp vụ chính cho QR và trạng thái thực tế.

==================================================
2. USER-DEFINED QC ACTIONS
==================================================

Web/mobile QC phải hỗ trợ tối thiểu các action người dùng đã yêu cầu:

ĐÃ KIỂM TRA

THIẾU HÀNG

NG TRẢ LẠI NC CHỜ XỬ LÝ

ĐÃ ĐÓNG GÓI

ĐÃ GIAO HÀNG

và:

BÁO CÁO BẰNG NỘI DUNG

Không hard-code toàn business engine vào text label UI.

Dùng semantic event/status codes nội bộ,
nhưng UI hiển thị tiếng Việt đúng yêu cầu.

==================================================
3. EVENT MODEL — KHÔNG GHI ĐÈ
==================================================

Không chỉ lưu một field current_status rồi overwrite mất lịch sử.

Mỗi thao tác QC/packing/delivery phải tạo event/history.

Concept:

QC_CHECKED

SHORTAGE_REPORTED

QC_NG_RETURNED_TO_MACHINING

PACKED

DELIVERED

GENERAL_REPORT

Mỗi event tối thiểu:

event UUID
tracking_item_id
event_type
quantity
notes/content
actor_user_id
actor_display_name_snapshot
server_timestamp
client_timestamp optional
device/client id optional
revision
supersedes_event_id optional

==================================================
4. CURRENT STATUS PROJECTION
==================================================

Tracking Item có thể giữ derived/current status để list/filter nhanh.

Nhưng source history phải là event/audit.

Ví dụ:

event history:
PHAY LẦN 1
PHAY LẦN 2
ĐÃ XONG
QC_CHECKED
PACKED

current status:
PACKED

Không xóa event cũ khi status thay đổi.

==================================================
5. QC — ĐÃ KIỂM TRA
==================================================

Khi bấm:

ĐÃ KIỂM TRA

hiển thị quantity.

Có thể prefill quantity từ tracking item,
nhưng người dùng sửa được.

Tối thiểu lưu:

checked_quantity
notes optional
actor
timestamp

Không tự coi toàn bộ quantity PASS nếu quantity báo kiểm tra chỉ là một phần.

==================================================
6. THIẾU HÀNG
==================================================

Action:

THIẾU HÀNG

Cho nhập tối thiểu:

quantity thiếu
nội dung/ghi chú

Ví dụ:

Tracking Item:
20 pcs

thực tế:
18 pcs

shortage:
2 pcs

Không silently thay đổi ordered quantity/product master quantity.

Shortage là event nghiệp vụ riêng.

==================================================
7. NG TRẢ LẠI NC CHỜ XỬ LÝ
==================================================

Action:

NG TRẢ LẠI NC CHỜ XỬ LÝ

"NC" trong UI có thể giữ theo yêu cầu người dùng,
nhưng code semantic nên rõ nghĩa.

Tối thiểu nhập:

NG quantity
nội dung lỗi
machining type liên quan optional
attempt/report liên quan optional

Event phải đặt Tracking Item vào trạng thái tương đương:

REWORK / NG_WAITING_MACHINING

Không xóa lịch sử QC cũ.

==================================================
8. NG → GIA CÔNG LẠI
==================================================

Sau NG, người làm gia công vẫn dùng chính QR hiện tại.

Không tạo QR mới chỉ vì NG/rework.

User quét lại:

thấy trạng thái NG / chờ xử lý

và vẫn có thể:

chọn loại gia công
Lần N
ĐÃ XONG

theo cơ chế Stage 3 hiện tại.

Sau đó QC có thể tạo event kiểm tra mới.

==================================================
9. MULTIPLE QC CYCLES
==================================================

Phải hỗ trợ:

Gia công
→ QC NG
→ Gia công lại
→ QC NG lần 2
→ Gia công lại
→ QC PASS

Không được assume chỉ có một QC event cho Tracking Item.

==================================================
10. PACKING
==================================================

Action:

ĐÃ ĐÓNG GÓI

Tối thiểu:

packed_quantity
notes optional
actor
timestamp

Không được cho packed_quantity âm hoặc 0.

Cần policy rõ cho partial packing.

Ví dụ:

Tracking quantity:
20

Packing event:
10

event sau:
10

Tổng packed quantity:
20

Không nhất thiết bắt buộc đóng gói một lần.

==================================================
11. DELIVERY
==================================================

Action:

ĐÃ GIAO HÀNG

Tối thiểu:

delivered_quantity
delivery timestamp/date
notes optional
actor

Có thể prefill ngày hiện tại nhưng server timestamp vẫn authority.

Phải hỗ trợ partial delivery.

Ví dụ:

20 pcs

Delivered:
10
rồi
10

Không dùng một boolean delivered đơn giản làm source of truth.

==================================================
12. PACK / DELIVERY QUANTITY INVARIANTS
==================================================

Tối thiểu review/test:

packed_quantity > 0

delivered_quantity > 0

aggregate packed <= relevant available quantity

aggregate delivered <= aggregate packed

hoặc nếu business cho phép giao không cần packing,
phải document policy rõ.

Ưu tiên trong R006:

DELIVERY REQUIRES PACKED QUANTITY

để tránh giao số lượng chưa từng đóng gói.

Không silently allow over-delivery.

==================================================
13. QC QUANTITY SEMANTICS
==================================================

Không dùng một field quantity duy nhất cho:

ordered
processed
checked
NG
packed
delivered

Giữ tách semantics.

Tracking Item quantity:
target/order occurrence quantity

Events:
checked_quantity
shortage_quantity
ng_quantity
packed_quantity
delivered_quantity

==================================================
14. GENERAL REPORT
==================================================

Có nút:

BÁO CÁO

hoặc:

NỘI DUNG BÁO CÁO

Cho nhập free-text report.

Tạo event:

GENERAL_REPORT

Không thay đổi current workflow status trừ khi business rule yêu cầu.

Ví dụ báo:

"Chờ vật liệu"
"Chờ khách xác nhận"
"Đang xử lý lại bề mặt"

Lịch sử phải giữ.

==================================================
15. REPORT EDITING / REVISION
==================================================

Giống Stage 3:

người dùng được sửa báo cáo đã gửi,
nhưng KHÔNG destructive update.

Tạo revision mới.

Ví dụ:

R1:
NG qty=3

R2:
NG qty=2
reason="Nhập nhầm số lượng"

Giữ R1 trong audit history.

==================================================
16. WEB ROLE / MODE
==================================================

Sau scan QR, web cần cho phép người dùng vào ít nhất hai nhóm thao tác:

GIA CÔNG

QC / TRẠNG THÁI

Không bắt buộc hệ thống auth role production trong R006.

Có thể UI dạng tab/segment:

[ GIA CÔNG ]
[ QC / GIAO HÀNG ]

User vẫn giữ identity hiện tại.

==================================================
17. QC MOBILE UI
==================================================

Sau scan, section QC có nút:

ĐÃ KIỂM TRA

THIẾU HÀNG

NG TRẢ LẠI NC CHỜ XỬ LÝ

ĐÃ ĐÓNG GÓI

ĐÃ GIAO HÀNG

BÁO CÁO

Không hiển thị tất cả thành nút khổng lồ chiếm hết màn hình.

Mobile-first, dễ bấm.

==================================================
18. ACTION DIALOG
==================================================

Sau chọn action:

hiện form ngắn phù hợp.

Ví dụ:

NG TRẢ LẠI NC CHỜ XỬ LÝ

Số lượng NG:
[ 2 ]

Nội dung:
[ Sai kích thước lỗ Ø10 ]

[ GỬI BÁO CÁO ]

Không bắt user nhập trường không liên quan.

==================================================
19. MOBILE HISTORY
==================================================

History trên web phải phân biệt trực quan:

Gia công
QC
NG
Đóng gói
Giao hàng
Báo cáo

Hiển thị tối thiểu:

time
user
action
quantity
notes summary

Cho mở chi tiết.

==================================================
20. CURRENT PRODUCT CARD
==================================================

Sau QR scan vẫn phải hiện:

Tên sản phẩm
Khách hàng
Mã sản phẩm
Mã theo dõi riêng
Ngày giao hàng
Số lượng
Trạng thái

Không được regress Stage 3.

==================================================
21. DESKTOP — STATUS OVERVIEW
==================================================

Desktop Tracking Item list mở rộng:

QC status
NG/rework status
packed quantity
delivered quantity
current status

Có màu semantic.

Không lưu màu vào DB.

==================================================
22. DESKTOP — HISTORY
==================================================

Có khả năng mở lịch sử một Tracking Item:

Gia công
QC
Packing
Delivery
Report revisions

Ưu tiên timeline/table gọn.

==================================================
23. DESKTOP — QC MANAGEMENT
==================================================

Desktop cũng được phép tạo:

Đã kiểm tra
Thiếu hàng
NG
Đã đóng gói
Đã giao hàng
Báo cáo

Không bắt buộc chỉ web mới được thao tác.

Tất cả vẫn đi application service/API/business layer,
không bypass audit.

==================================================
24. SEARCH / FILTER
==================================================

Desktop/API thêm filter hữu ích:

WAITING_QC
QC_CHECKED / PASS-equivalent
QC_NG
REWORK
PACKED
PARTIALLY_DELIVERED
DELIVERED
SHORTAGE

Không overbuild workflow engine.

==================================================
25. TRACKING STATUS SEMANTICS
==================================================

Review Stage 3 tracking status.

Mở rộng semantic status nếu cần:

NEW
IN_PROCESS
WAITING_QC
QC_CHECKED
QC_NG
REWORK
PACKING
PACKED
PARTIALLY_DELIVERED
DELIVERED
HOLD

Không nhất thiết dùng đúng toàn bộ nếu model tốt hơn,
nhưng phải map rõ.

==================================================
26. ĐÃ KIỂM TRA VS QC PASS
==================================================

User yêu cầu label:

ĐÃ KIỂM TRA

Không tự đổi wording UI thành:

QC PASS

nếu chưa có yêu cầu.

Internally có thể coi đây là checked/accepted state theo policy R006,
nhưng UI phải giữ đúng ngôn ngữ dễ hiểu.

Nếu cần phân biệt CHECKED và PASS về sau:
document extension point.

==================================================
27. DELIVERY DATE VS DELIVERY EVENT
==================================================

Phân biệt:

planned delivery date

và:

actual delivered event/time.

Đổi planned delivery date:
không phải giao hàng.

Đã giao hàng:
event thực tế.

Không overwrite hai concept.

==================================================
28. QR REMAINS UNCHANGED
==================================================

QC/NG/Packing/Delivery:

KHÔNG thay QR.

QR payload vẫn đúng 4 field:

product_name
customer_name
product_code
tracking_code

Không thêm trạng thái QC vào QR.

==================================================
29. PRINTED LABEL
==================================================

R006 không cần QR payload change.

Có thể bổ sung current visible status vào label template nếu phù hợp,
nhưng không bắt buộc.

Không nhét status vào QR.

==================================================
30. API
==================================================

Tạo API surface versioned phù hợp.

Concept:

POST /tracking/api/v1/tracking-items/{id}/qc-events

POST /tracking/api/v1/tracking-items/{id}/packing-events

POST /tracking/api/v1/tracking-items/{id}/delivery-events

POST /tracking/api/v1/tracking-items/{id}/reports

GET /tracking/api/v1/tracking-items/{id}/history

POST /.../{event_id}/revisions

Endpoint naming có thể khác nếu architecture hiện tại tốt hơn.

Không duplicate business rules trong routes.

==================================================
31. APPLICATION SERVICES
==================================================

Tạo/tách service phù hợp:

QcService
PackingService
DeliveryService
TrackingHistoryService

hoặc bounded service tương đương.

Không tạo God Service chứa toàn app.

==================================================
32. IDEMPOTENCY
==================================================

Các write event từ mobile phải hỗ trợ request UUID/idempotency giống process reports.

Double tap:

ĐÃ GIAO HÀNG

không được tạo 2 delivery events nếu cùng request ID.

Tương tự QC/NG/Packing.

==================================================
33. TRANSACTIONALITY
==================================================

Event create + status projection/update phải atomic.

Không để:

delivery event đã tạo
nhưng current status chưa update

hoặc ngược lại.

Inject failure test phù hợp.

==================================================
34. SERVER TIME
==================================================

Server timestamp authority.

UTC storage.

UI hiển thị:

Asia/Ho_Chi_Minh.

==================================================
35. USER IDENTITY
==================================================

Dùng Operator/User foundation Stage 3.

Không dùng raw display name làm only identity.

History phải có:

actor_user_id
actor_display_name_snapshot

==================================================
36. DATABASE
==================================================

Mở rộng SQLAlchemy/Alembic.

Ưu tiên event table architecture dùng chung nếu maintainable,
hoặc bounded tables nếu rõ semantics hơn.

Không nhồi mọi loại event vào JSON blob không schema nếu không cần.

Codex đánh giá tradeoff.

==================================================
37. SQLITE TEST
==================================================

Automated integration vẫn dùng SQLite trong TEST ROOT.

Giữ:

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED

Không cài production PostgreSQL trong R006.

==================================================
38. ALEMBIC
==================================================

Fresh migration smoke:

existing Stage3 schema
→ upgrade Stage4
→ data preserved
→ new tables/fields available.

Test fresh DB và upgrade-path DB nếu phù hợp.

Không được phá:

Product
Customer
PO
Production Run
Tracking Item
QR
Process Reports.

==================================================
39. QC TEST MATRIX
==================================================

Bắt buộc:

QC checked
partial checked
multiple QC cycles
shortage
NG
NG → machining report → QC again
invalid quantities
revision
idempotency

==================================================
40. PACKING TEST MATRIX
==================================================

Bắt buộc:

pack full
pack partial
multiple packing events
zero/negative reject
over-pack reject
idempotent retry

==================================================
41. DELIVERY TEST MATRIX
==================================================

Bắt buộc:

deliver partial
deliver remaining
over-delivery reject
delivery before enough packing reject
idempotent retry
actual delivery time
planned delivery date remains separate

==================================================
42. STATUS PROJECTION TEST
==================================================

Ví dụ test:

tracking item
→ process report
→ QC NG
→ rework report
→ QC checked
→ packed
→ partial delivery
→ delivered

Current status phải đúng ở từng bước.

History không mất event.

==================================================
43. REPORT REVISION TEST
==================================================

Create NG report/event.

Revise quantity/content.

Old revision remains available.

Current effective revision correct.

Audit chain correct.

==================================================
44. MOBILE WEB TEST
==================================================

Fresh browser/component tests:

scan existing QR

switch to QC section

ĐÃ KIỂM TRA

THIẾU HÀNG

NG TRẢ LẠI NC CHỜ XỬ LÝ

ĐÃ ĐÓNG GÓI

ĐÃ GIAO HÀNG

BÁO CÁO

forms

history refresh

No horizontal overflow.

No own-code console errors.

==================================================
45. STAGE 3 REGRESSION
==================================================

Bắt buộc giữ:

QR exact four-field payload
same QR after delivery-date change
new order → new tracking/QR
TẠO PHÔI
user preference
attempt expansion
ĐÃ XONG
process report
idempotency
revision

PASS.

==================================================
46. STAGE 0–2 REGRESSION
==================================================

Product
Excel lifecycle
Customer
PO
Delivery Schedule
Production Run
Alembic

must remain PASS.

==================================================
47. TEST ISOLATION
==================================================

Production root:

F:\PHAN-MEM-QUAN-LY-QR

Test root:

F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST

Run:

python scripts/check_test_isolation.py

Required:

TEST_ISOLATION_PASS

NO_RUNTIME_ARTIFACTS_IN_PRODUCTION

==================================================
48. NAS
==================================================

Do not write test artifacts to:

\\192.168.1.58\data-pm-qr

Keep:

NAS_WRITE_PIPELINE_NOT_YET_EXECUTED

==================================================
49. WEB HOSTING
==================================================

Do not deploy production hosting in R006.

But preserve web architecture so later deployment target can be:

GitHub private repository
→ Cloudflare Pages Free
→ Web/PWA

Do not put production business data in repository/Pages.

Keep:

PRODUCTION_WEB_HOSTING_NOT_YET_DEPLOYED

==================================================
50. CAMERA
==================================================

Do not claim real iPhone/Android camera PASS.

Keep:

MOBILE_CAMERA_REAL_DEVICE_PASS_NOT_YET_EXECUTED

==================================================
51. EXCEL
==================================================

Do not regress generic export.

Stage 4 may extend export fields:

QC status
NG quantity
packed quantity
delivered quantity
actual delivery status

No need exact legacy template fidelity yet.

Keep:

TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE

==================================================
52. STATIC REVIEW
==================================================

After implementation:

git diff --check

Review full diff.

Report:

DIFF_REVIEW_FILE_COUNT=
UNRELATED_CHANGE_COUNT=

Expected:

UNRELATED_CHANGE_COUNT=0

==================================================
53. BRANCH
==================================================

Create:

stage4-qc-packing-delivery

Do not implement directly on main.

==================================================
54. DOCUMENTATION
==================================================

Create:

docs/authorities/AUTHORITY_STAGE4_R006.md

docs/checkpoints/CHECKPOINT_STAGE4_R006.md

Update:

PROJECT_STATE.md
DATA_MODEL.md
ARCHITECTURE.md
DECISIONS.md
README.md if necessary

==================================================
55. ADR
==================================================

Record major decision:

QC/PACKING/DELIVERY ARE EVENT-BASED TRACKING WORKFLOWS

not routing steps.

Also document quantity semantics.

==================================================
56. CANDIDATE PASS
==================================================

R006 PASS when end-to-end works:

QR scan
→ Product info
→ QC checked / shortage / NG
→ rework possible
→ packing
→ delivery
→ history
→ Desktop current state

with:

audit
revisions
idempotency
quantity invariants
migration
regression
isolation

==================================================
57. CANDIDATE ONLY
==================================================

If R006 passes:

PASS_STAGE4_QC_PACKING_DELIVERY_R006

Do NOT merge main yet.

Independent review/integration gate required.

==================================================
58. BLOCK / REJECT
==================================================

Own-code defect:

REJECT_STAGE4_QC_PACKING_DELIVERY_R006_<REASON>

External prerequisite:

BLOCKED_STAGE4_QC_PACKING_DELIVERY_R006_<REASON>

Do not hide defects behind BLOCKED.

==================================================
59. NEXT ROADMAP — DO NOT IMPLEMENT EARLY
==================================================

After Stage 4 integration, likely next major stages:

A.
NAS FILE/IMAGE STORAGE PIPELINE
+
Product attachments
+
backup foundations

B.
Exact legacy Excel template import/export fidelity

C.
PostgreSQL + Machine A deployment

D.
Cloudflare Pages Free web deployment
+
secure connection to Machine A

E.
Real iPhone / Android camera acceptance

F.
Production security/authentication/hardening

Do not begin these inside R006.

==================================================
60. CHAT POLICY
==================================================

If R006 completes and current Codex context is still healthy:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

If context has become genuinely large after Stage 3 + Stage 4:
create proper checkpoint/handoff and then recommend new chat.

Do not switch mechanically.

==================================================
61. FINAL REPORT
==================================================

Start with:

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

baseline HEAD/tree
branch
candidate HEAD/tree
changed paths
QC status
shortage status
NG/rework status
packing status
delivery status
quantity invariants
history/revisions
idempotency
API
desktop
mobile web
SQLAlchemy/Alembic
Excel regression
Stage3 regression
full regression
isolation
warnings
known gaps
next exact action

==================================================
62. EXECUTE
==================================================

PRECHECK_STAGE4_R006

→ create branch
→ save authority
→ domain/event model
→ migration
→ application/API
→ mobile QC UI
→ desktop integration
→ focused tests
→ complete regression
→ isolation
→ checkpoint
→ candidate commit(s)
→ final report

Target:

PASS_STAGE4_QC_PACKING_DELIVERY_R006