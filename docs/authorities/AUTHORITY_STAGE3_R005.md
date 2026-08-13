HMS QR PRODUCT MANAGER
STAGE 3 — ORDER TRACKING ITEM + QR + MOBILE PROCESS REPORTING
MEGA AUTHORITY R005

==================================================
TIẾN ĐỘ PHẦN MỀM
==================================================

Previous verdict:

PASS_STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004A_INTEGRATED

Repository:

F:\PHAN-MEM-QUAN-LY-QR

Current branch:

main

Accepted HEAD:

2aed6e945543d2d190bf932a30330032608f95e2

Accepted tree:

f956fc07e4f5503b7624c808ff18b22e305255ae

Expected working tree:

CLEAN

Current Stage:

Stage 3

WP:

Order Tracking Identity
+
QR Issuance
+
Mobile/Web Scan
+
Dynamic Machining Report

Revision:

R005

Target:

PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005

KHUYẾN NGHỊ CODEX:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

==================================================
1. IMPORTANT SCOPE CHANGE
==================================================

KHÔNG triển khai Routing engine.

KHÔNG yêu cầu Production Run phải định nghĩa trước chuỗi:

Tạo phôi
→ Tiện
→ Phay
→ Cắt dây
→ ...

Người dùng đã thay đổi yêu cầu.

Process reporting trên web/mobile phải đơn giản và động.

Production Run vẫn được giữ vì đã có ích cho quản lý kế hoạch sản xuất,
nhưng KHÔNG dùng nó làm source bắt buộc của routing.

==================================================
2. LUỒNG NGHIỆP VỤ MỤC TIÊU
==================================================

PC:

Customer
→ PO / Đơn
→ Product
→ Tracking Item
→ QR

Mobile/Web:

Quét QR
→ resolve Tracking Item
→ hiện Product
→ hiện Customer
→ hiện mã SP
→ hiện mã tracking riêng
→ hiện số đơn
→ hiện ngày giao
→ hiện số lượng
→ hiện trạng thái
→ lấy loại gia công ưu tiên của USER
→ báo Lần 1/2/3/... hoặc ĐÃ XONG
→ gửi
→ Server ghi event/audit
→ Desktop cập nhật

==================================================
3. ROOT POLICY — GIỮ NGUYÊN
==================================================

Production:

F:\PHAN-MEM-QUAN-LY-QR

Test/temp/runtime duy nhất:

F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST

NAS production:

\\192.168.1.58\data-pm-qr

Không ghi test lên NAS.

Không tạo:

SQLite test
QR test
PNG QR
screenshots
logs
mobile artifacts
pytest temp
Excel outputs

trong production root.

==================================================
4. BRANCH
==================================================

Từ accepted main tạo:

stage3-tracking-qr-process-reporting

Không implement trực tiếp trên main.

Preflight:

git status --short
git rev-parse HEAD
git rev-parse HEAD^{tree}

Nếu main drift hoặc dirty không giải thích được:

BLOCK.

==================================================
5. BA LỚP IDENTITY — PHẢI TÁCH RÕ
==================================================

Không được nhầm ba khái niệm sau.

A. PRODUCT MASTER ID

Ví dụ:

SP-2026-000125

Đây là mã loại sản phẩm/master.

Ổn định.

Không thay đổi chỉ vì tạo đơn mới.

----------------------------------

B. ORDER / PO IDENTITY

Ví dụ:

ORD-2026-000087

hoặc PO number của khách hàng.

Đây là đơn/lần đặt hàng.

----------------------------------

C. TRACKING ITEM ID

Mỗi sản phẩm xuất hiện trong một đơn/lần giao cần một mã theo dõi riêng.

Ví dụ:

ITEM-2026-000458

Đây là identity dùng để:

- check;
- tạo QR;
- báo cáo gia công;
- audit;
- theo dõi ngày giao;
- tra cứu lịch sử.

Không dùng Product Master code làm tracking identity.

==================================================
6. TRACKING ITEM ENTITY
==================================================

Tạo entity phù hợp, tên có thể là:

OrderTrackingItem

hoặc tên architecture tốt hơn.

Tối thiểu:

internal UUID

tracking_code

purchase_order_id

purchase_order_line_id

product_id

customer_id hoặc derivable customer relation

quantity

unit

delivery_date

status

qr_public_id

created_at
updated_at

created_by
updated_by

Không copy toàn bộ Product master fields không cần thiết.

==================================================
7. TRACKING CODE
==================================================

Tracking code phải unique.

Baseline:

ITEM-YYYY-NNNNNN

Generator/service riêng.

Không hard-code format trong UI.

Tracking code:

- không đổi khi chỉ thay ngày giao;
- không đổi khi di chuyển bản ghi;
- không đổi khi sửa ghi chú/trạng thái;
- không đổi khi thay đổi vị trí hiển thị.

==================================================
8. QUY TẮC THAY ĐỔI NGÀY GIAO
==================================================

Đây là business rule bắt buộc.

Ví dụ Tracking Item:

ITEM-2026-000458

Delivery:
25/08/2026

User chuyển sang:

30/08/2026

Nếu đây chỉ là:

ĐỔI NGÀY GIAO HÀNG

thì:

tracking_code giữ nguyên

qr_public_id giữ nguyên

QR giữ nguyên

order identity giữ nguyên

chỉ delivery_date thay đổi.

Audit phải ghi:

old date
new date
user
server timestamp
reason nếu có

==================================================
9. COPY SẢN PHẨM SANG NGÀY KHÁC
==================================================

Khi người dùng copy một sản phẩm/bản ghi sang một ngày giao khác:

KHÔNG được mặc định clone hoặc move.

UI phải hỏi rõ:

BẠN MUỐN:

[ ĐỔI NGÀY GIAO HÀNG ]

hay

[ TẠO ĐƠN MỚI ]

==================================================
10. OPTION — ĐỔI NGÀY GIAO HÀNG
==================================================

Nếu chọn:

ĐỔI NGÀY GIAO HÀNG

thì:

- giữ Product Master;
- giữ Tracking Item;
- giữ tracking_code;
- giữ QR;
- giữ order identity;
- chỉ cập nhật delivery date;
- ghi audit.

Không sinh mã mới.

==================================================
11. OPTION — TẠO ĐƠN MỚI
==================================================

Nếu chọn:

TẠO ĐƠN MỚI

phải tạo identity mới.

Tối thiểu:

new order/order occurrence
new tracking item
new tracking_code
new qr_public_id
new QR

Không reuse QR cũ.

Product Master vẫn có thể là cùng:

SP-2026-000125

Ví dụ:

OLD:

SP-2026-000125
ORD-2026-000087
ITEM-2026-000458

NEW:

SP-2026-000125
ORD-2026-000088
ITEM-2026-000459

==================================================
12. ORDER NUMBER SEMANTICS
==================================================

Stage 2 hiện có PO number.

Codex phải review xem có cần thêm:

internal_order_code

để đáp ứng yêu cầu:

“TẠO ĐƠN MỚI → MÃ ĐƠN HÀNG MỚI”

Nếu PO number là customer-provided identifier:

không nên tự động sửa customer PO number.

Có thể tách:

customer_po_number

và:

internal_order_code

nếu architecture cần.

Không phá semantics Stage 2.

Ghi ADR nếu tách hai identity này.

==================================================
13. QR CONTENT
==================================================

Không encode trực tiếp:

customer
product
delivery date
quantity

vào QR.

QR chỉ chứa opaque/versioned reference.

Ví dụ concept:

HMSQR:v1:<opaque-public-id>

Server resolve:

QR
→ Tracking Item
→ dữ liệu hiện tại

Lợi ích bắt buộc:

đổi ngày giao
→ QR vẫn giữ nguyên
→ khi scan sẽ thấy ngày mới.

==================================================
14. QR SECURITY
==================================================

QR public identifier:

- không dùng sequential DB integer;
- không lộ internal database ID trực tiếp;
- khó đoán hợp lý;
- unique;
- versionable.

Có thể dùng secure random/UUID phù hợp.

QR token không chứa credential.

==================================================
15. QR ISSUANCE
==================================================

Tracking Item mới phải có capability:

ISSUE QR

Tạo:

qr_public_id

và QR image/render/export.

QR image test:

TEST ROOT only.

Không lưu QR test lên NAS.

Production QR storage strategy có thể để Stage NAS sau.

==================================================
16. QR REISSUE
==================================================

R005 cần chuẩn bị policy:

- xem lại QR hiện tại;
- in lại cùng QR;
- reissue QR mới nếu QR cũ cần revoke.

Reprint không đồng nghĩa reissue.

Reprint:

same qr_public_id.

Reissue:

new qr_public_id
old QR becomes revoked/inactive
audit required.

R005 có thể implement tối thiểu nếu scope cho phép.

==================================================
17. SCAN RESOLUTION API
==================================================

Tạo endpoint versioned phù hợp, ví dụ:

GET /api/v1/scan/{qr_public_id}

hoặc contract tốt hơn.

Response tối thiểu:

tracking_code
product_code
part_name
customer
order code/PO
delivery_date
quantity
unit
tracking status
qr status

Không trả dữ liệu không cần thiết.

==================================================
18. MOBILE / WEB — USER IDENTITY FOUNDATION
==================================================

User mở web lần đầu:

nhập tên.

Tạo/lấy Operator/User profile.

Tối thiểu:

user UUID
display name
active
created_at
updated_at

Không cần full password/auth production R005.

Nhưng không chỉ dùng display name làm internal identity.

==================================================
19. NHỚ USER TRÊN THIẾT BỊ
==================================================

Sau khi user đã chọn/nhập một lần:

web nhớ user trên thiết bị.

Tên luôn hiện ở góc trên.

Có nút:

ĐỔI NGƯỜI DÙNG

hoặc:

SỬA TÊN

phù hợp.

Không bắt nhập lại sau mỗi scan.

Local storage có thể dùng để cache selected user identity.

Server vẫn lưu User profile.

==================================================
20. MACHINING TYPE
==================================================

Không dùng Routing.

Tạo configurable Process/Machining Type catalog.

Baseline:

TẠO PHÔI
TIỆN
PHAY
CẮT DÂY

Có thể thêm sau:

MÀI
NHIỆT LUYỆN
KHÁC

Không hard-code business core nếu tránh được.

Có active/order/display name.

Desktop/admin foundation cho phép thêm/sửa loại sau này hoặc ít nhất service/configurable data model.

==================================================
21. LOẠI GIA CÔNG ĐƯỢC NHỚ THEO USER
==================================================

Nếu User A chọn:

PHAY

thì Server lưu preference:

User A → PHAY

Khi:

- đóng web;
- mở web lại;
- scan QR khác;
- dùng session khác;

phải ưu tiên khôi phục PHAY cho User A.

Có nút rõ:

ĐỔI LOẠI GIA CÔNG

Không bắt người dùng chọn lại mỗi lần.

==================================================
22. USER PREFERENCE — SERVER SOURCE OF TRUTH
==================================================

Machining type preference:

lưu server-side theo USER.

Local cache:

chỉ để tăng tốc/fallback.

Không dùng local storage làm source duy nhất.

Khi đổi user:

phải load preference của user mới.

Không để preference user cũ rò sang user mới.

==================================================
23. ATTEMPT BUTTONS — DEFAULT
==================================================

Sau scan và chọn machining type:

mặc định hiển thị:

[ LẦN 1 ]
[ LẦN 2 ]
[ LẦN 3 ]

và:

[ + THÊM LẦN ]

Không mặc định hiện 20–30 nút.

==================================================
24. DYNAMIC ATTEMPT EXPANSION
==================================================

Khi bấm:

+ THÊM LẦN

hiện tiếp một nhóm hợp lý, ví dụ:

LẦN 4
LẦN 5
LẦN 6

Bấm thêm:

LẦN 7
LẦN 8
LẦN 9

v.v.

Không hard-code max = 6 hoặc 9.

Có bounded safety max/config nếu cần để tránh abuse,
nhưng UX phải cho phép mở rộng khi công việc thật cần.

==================================================
25. CỰC KỲ QUAN TRỌNG — ATTEMPT EXPANSION KEY
==================================================

Số lần đã xổ KHÔNG lưu theo user.

Không global.

Không áp sang mã hàng khác.

Phải lưu theo ít nhất:

TRACKING ITEM
+
MACHINING TYPE

Ví dụ:

ITEM-458 + PHAY → max visible = 9

ITEM-458 + TIỆN → max visible = 3

ITEM-459 + PHAY → max visible = 3

Do đó:

scan ITEM-458 + PHAY
→ hiện tới Lần 9

scan ITEM-459 + PHAY
→ chỉ Lần 1–3

scan ITEM-458 + TIỆN
→ chỉ Lần 1–3

==================================================
26. WHY TRACKING ITEM INSTEAD OF PRODUCT MASTER
==================================================

Không lưu max attempt chỉ theo Product Master.

Cùng một Product Master có thể xuất hiện ở nhiều đơn/lần giao khác nhau.

Các đơn này phải có tiến trình báo cáo độc lập.

Ưu tiên key:

tracking_item_id + machining_type_id

không phải:

product_master_id only.

==================================================
27. ATTEMPT EXPANSION PERSISTENCE
==================================================

Server lưu:

tracking_item_id
machining_type_id
max_visible_attempt

updated_at
updated_by optional

Đóng web mở lại:

khôi phục đúng.

Đổi điện thoại:

khôi phục đúng.

User khác scan cùng Tracking Item:

cũng thấy đúng số lần đã mở của Tracking Item + machining type đó.

==================================================
28. PROCESS REPORT EVENT
==================================================

Khi user bấm một Lần:

tạo immutable-ish report event.

Tối thiểu:

event UUID
tracking_item_id
machining_type_id
attempt_number
quantity
notes
actor_user_id
actor_display_name_snapshot
server_timestamp
client_timestamp optional
device/client identifier optional
revision
status

Không chỉ cập nhật một field "current attempt".

Phải giữ history.

==================================================
29. ATTEMPT NUMBER
==================================================

attempt_number là:

1
2
3
...

Không phải Routing step.

Không mang nghĩa bắt buộc phải làm tuần tự.

R005 không nên block user chỉ vì chưa có Lần 1 mà bấm Lần 2,
trừ khi user yêu cầu business rule khác sau này.

History phải cho biết những lần nào đã được báo.

==================================================
30. ĐÃ XONG — NÚT RIÊNG
==================================================

Ngoài các Lần phải có nút nổi bật:

ĐÃ XONG

Đây KHÔNG phải “Lần cuối”.

Đây là một completion action riêng.

Dùng khi:

người dùng đã hoàn thiện các công đoạn gia công sẵn rồi
và không cần báo từng lần nữa.

==================================================
31. ĐÃ XONG EVENT
==================================================

Khi bấm ĐÃ XONG:

ghi event riêng, ví dụ:

PROCESS_COMPLETED

Tối thiểu:

tracking item
machining type
quantity
notes optional
actor
server timestamp

Không giả tạo attempt_number nếu không cần.

==================================================
32. ĐÃ XONG KHÔNG XÓA HISTORY
==================================================

Nếu đã có:

Lần 1
Lần 2

rồi bấm:

ĐÃ XONG

history vẫn phải giữ:

Lần 1
Lần 2
Đã xong

Không collapse/xóa các báo cáo cũ.

==================================================
33. QUANTITY
==================================================

Sau khi chọn:

Lần N

hoặc:

ĐÃ XONG

hiển thị quantity input.

Có thể prefill hợp lý từ Tracking Item quantity,
nhưng user phải sửa được nếu báo cáo chỉ cho một phần.

Validation:

quantity > 0

Không vượt tracking item/order quantity nếu policy hiện tại không cho.

Nếu báo partial nhiều lần:

không tự cộng thành completed manufacturing quantity trừ khi semantics được chốt.

R005 chủ yếu ghi report event.

==================================================
34. NOTES
==================================================

Có input:

GHI CHÚ / NỘI DUNG BÁO CÁO

không bắt buộc trong normal path.

Có thể bắt buộc ở một số error/status trong Stage sau.

==================================================
35. REPORT SUBMISSION
==================================================

Khi gửi:

client tạo idempotency/request UUID.

Server chống duplicate do:

- double tap;
- timeout;
- retry;
- mạng chập chờn.

Cùng request UUID:

không được tạo 2 report events.

==================================================
36. REPORT EDITING
==================================================

Báo cáo đã gửi phải có:

SỬA BÁO CÁO

Nhưng KHÔNG update destructive.

Tạo revision mới.

Ví dụ:

Report R1
qty=10

Report R2
supersedes=R1
qty=12
reason="Nhập nhầm"

History vẫn xem được R1.

==================================================
37. SCAN UI — THÔNG TIN PHẢI HIỆN
==================================================

Sau scan QR:

hiển thị rõ tối thiểu:

TÊN SẢN PHẨM

KHÁCH HÀNG

MÃ SẢN PHẨM

MÃ THEO DÕI

MÃ ĐƠN / PO

NGÀY GIAO HÀNG

SỐ LƯỢNG

TRẠNG THÁI

Đây là requirement bắt buộc.

==================================================
38. DELIVERY DATE LIVE RESOLUTION
==================================================

Ngày giao không encode chết trong QR.

Scan phải resolve live từ server.

Do đó:

Tracking Item QR tạo ngày 20/08

sau đổi delivery date từ 25/08 → 30/08

scan cùng QR

phải hiện:

30/08

Không cần in QR mới.

==================================================
39. DESKTOP — TRACKING ITEM UI
==================================================

Bổ sung trên PC:

- tracking code;
- QR status;
- ngày giao;
- Product;
- Customer;
- Order;
- quantity;
- process-report summary.

Cho phép:

TẠO QR
XEM QR
IN/XUẤT QR

Không cần final label designer R005.

==================================================
40. DESKTOP — MOVE/COPY INTERACTION
==================================================

Khi thao tác copy/move một Tracking Item sang ngày khác:

hiển thị modal:

BẠN MUỐN:

[ ĐỔI NGÀY GIAO HÀNG ]

[ TẠO ĐƠN MỚI ]

[ HỦY ]

Không dùng ambiguous drag-copy behavior.

==================================================
41. NEW ORDER FLOW
==================================================

Nếu TẠO ĐƠN MỚI:

phải tạo atomically.

Không được tạo nửa chừng:

new order tạo rồi
tracking item fail
QR fail

mà để orphan data.

Dùng transaction phù hợp.

==================================================
42. CHANGE DATE FLOW
==================================================

Nếu ĐỔI NGÀY:

transaction đơn giản:

update delivery date
audit event

Không tạo new QR.

Regression bắt buộc kiểm tra QR public id không đổi.

==================================================
43. API — TRACKING ITEM
==================================================

Tạo endpoints phù hợp cho:

create tracking item

get/list/search

update allowed metadata

change delivery date

copy/new-order action

QR issue/get

Naming cuối có thể do Codex chọn,
nhưng phải REST/API contract rõ.

==================================================
44. API — USER PREFERENCE
==================================================

Có contract cho:

get current machining preference

set machining preference

Không cần full authentication.

R005 dev identity contract phải được document.

==================================================
45. API — ATTEMPT DISPLAY STATE
==================================================

Có contract để:

get max_visible_attempt

expand max_visible_attempt

theo:

tracking_item + machining_type

Server phải validate monotonic expansion phù hợp.

Không để client tùy tiện giảm rồi làm mất UI state nếu không có reset policy.

==================================================
46. API — REPORT
==================================================

Tạo:

submit attempt report

submit completed report

list report history

revise report

Có idempotency.

Structured errors.

==================================================
47. WEB/MOBILE
==================================================

R005 phải tạo first usable mobile web vertical slice.

Dùng responsive mobile-first UI.

Ưu tiên PWA-ready architecture.

Không bắt buộc native iOS/Android app.

==================================================
48. QR SCANNER
==================================================

Web phải có capability camera QR scan nếu môi trường test hỗ trợ.

Do browser camera thường yêu cầu HTTPS/secure context:

architecture phải document requirement.

Automated tests có thể mock scan payload.

Không cần public production hosting trong R005.

==================================================
49. MANUAL QR FALLBACK
==================================================

Nên có development/manual fallback:

nhập/paste QR code

để test desktop browser nếu camera unavailable.

Không làm fallback này thành UX chính production nếu không cần.

==================================================
50. WEB USER HEADER
==================================================

Góc trên luôn hiện:

NGƯỜI DÙNG: <tên>

Có control:

ĐỔI NGƯỜI DÙNG

và/hoặc sửa tên theo policy.

==================================================
51. WEB PROCESS HEADER
==================================================

Hiển thị:

LOẠI GIA CÔNG: PHAY

Có:

ĐỔI LOẠI GIA CÔNG

Nếu user đã có preference:
không popup bắt chọn lại.

==================================================
52. WEB ATTEMPT UI
==================================================

Sau scan:

LẦN 1
LẦN 2
LẦN 3

+ THÊM LẦN

và:

ĐÃ XONG

Thiết kế nút dễ bấm trên điện thoại,
nhưng không quá lớn/chiếm toàn màn hình.

==================================================
53. REPORT HISTORY ON WEB
==================================================

Có section gọn:

LỊCH SỬ GẦN ĐÂY

Hiển thị:

thời gian
user
loại gia công
Lần / Đã xong
quantity

Có thể mở xem chi tiết.

==================================================
54. STATUS COLORS
==================================================

Web và Desktop có thể dùng màu semantic.

Nhưng status vẫn là dữ liệu semantic,
không lưu màu vào business data.

==================================================
55. AUDIT
==================================================

Các action quan trọng:

tracking item create
delivery date change
new order clone
QR issue
QR reissue
process report
report revision
user preference change

phải có audit metadata phù hợp.

==================================================
56. TIME
==================================================

Server timestamp authority.

UTC storage.

UI:

Asia/Ho_Chi_Minh.

Không dựa vào client clock cho ordering authority.

==================================================
57. DATABASE / MIGRATION
==================================================

Mở rộng SQLAlchemy/Alembic cho:

Tracking Item

QR identity

User/operator profile

User preference

Machining type

Attempt display state

Process report event/revision

SQLite automated integration vẫn ở TEST ROOT.

Giữ:

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED

==================================================
58. TEST — TRACKING IDENTITY
==================================================

Bắt buộc:

unique tracking code

same Product on different order → different tracking code

same Product copied as NEW ORDER → new tracking code

change date → same tracking code

change date → same qr_public_id

new order → new qr_public_id

==================================================
59. TEST — SCAN DATA
==================================================

QR resolve phải trả đúng:

Product name
Customer
Product code
Tracking code
Order/PO
Delivery date
Quantity
Status

Sau change date:

same QR
→ new delivery date visible.

==================================================
60. TEST — USER PREFERENCE
==================================================

User A:
PHAY

User B:
TIỆN

Restart/reload simulated.

User A → PHAY

User B → TIỆN

Không cross-user leakage.

==================================================
61. TEST — ATTEMPT EXPANSION
==================================================

ITEM-A + PHAY:
expand to 9.

ITEM-B + PHAY:
must remain default 3.

ITEM-A + TIỆN:
must remain default 3.

Reload:

ITEM-A + PHAY:
still 9.

==================================================
62. TEST — COMPLETED ACTION
==================================================

ĐÃ XONG:

creates completion event.

Không yêu cầu attempt sequence.

Không xóa attempt history cũ.

User/time/quantity preserved.

==================================================
63. TEST — IDEMPOTENCY
==================================================

Submit same request UUID twice:

exactly one business report event.

Response phải predictable.

==================================================
64. TEST — REVISION
==================================================

Create report.

Revise report.

Old revision remains readable.

New revision is effective current version.

Audit links:

supersedes / revision chain.

==================================================
65. TEST — TRANSACTIONAL NEW ORDER
==================================================

Tạo đơn mới từ copy:

new order
new tracking item
new QR

phải atomic.

Inject failure phù hợp:

không orphan order/tracking/QR.

==================================================
66. TEST — DESKTOP
==================================================

Offscreen smoke:

Tracking Item list

QR action

Change date dialog

Copy/new order dialog

Tracking fields display

==================================================
67. TEST — MOBILE WEB
==================================================

Automated/component/browser tests phù hợp cho:

user restore

machining preference restore

scan resolution

attempt buttons default 1–3

expand

per-item/per-process restore

ĐÃ XONG

report submit

edit/revision path

==================================================
68. CAMERA TESTING
==================================================

Không cần automation dùng camera thật nếu môi trường không phù hợp.

Có thể test scan payload integration bằng mock.

Camera real-device verification sẽ có gate riêng sau.

Không tuyên bố:

IPHONE_CAMERA_PASS

ANDROID_CAMERA_PASS

nếu chưa test thiết bị thật.

==================================================
69. QR IMAGE TEST
==================================================

Generated QR test images:

F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\...

Không commit QR binaries.

Verify generated code decodes về đúng opaque payload nếu library/tool cho phép.

==================================================
70. STAGE 1 + STAGE 2 REGRESSION
==================================================

Bắt buộc full regression giữ:

Product Master

Excel lifecycle

Customer

PO

PO Line

Delivery Schedule

Production Run

quantity invariants

migrations

PASS.

==================================================
71. WARNING POLICY
==================================================

Starlette/httpx warning hiện được classified external non-blocking.

Không làm dependency churn chỉ để xóa warning.

Nếu R005 tạo warning mới từ own code:

audit và fix trước candidate PASS.

==================================================
72. TEST ISOLATION
==================================================

Cuối authority:

python scripts/check_test_isolation.py

Expected:

TEST_ISOLATION_PASS

NO_RUNTIME_ARTIFACTS_IN_PRODUCTION

==================================================
73. DIFF REVIEW
==================================================

Review:

main baseline

2aed6e945543d2d190bf932a30330032608f95e2

→ candidate

Báo:

DIFF_REVIEW_FILE_COUNT=
UNRELATED_CHANGE_COUNT=

Expected:

UNRELATED_CHANGE_COUNT=0

==================================================
74. DOCUMENTATION
==================================================

Update:

PROJECT_STATE.md
ARCHITECTURE.md
DATA_MODEL.md
DECISIONS.md
README.md nếu cần

Tạo:

docs/authorities/AUTHORITY_STAGE3_R005.md

docs/checkpoints/CHECKPOINT_STAGE3_R005.md

==================================================
75. ADR — IDENTITY
==================================================

Bắt buộc ghi architectural decision rõ về:

Product Master Identity
vs
Order Identity
vs
Tracking Item Identity
vs
QR Public Identity

Và semantics:

change delivery date preserves tracking/QR

new order creates new tracking/QR.

==================================================
76. ADR — PROCESS REPORTING
==================================================

Ghi decision:

NO ROUTING ENGINE REQUIRED FOR MOBILE REPORTING

Machining type:
user preference

Attempt expansion:
tracking item + machining type

Report:
event/revision model.

==================================================
77. EXCEL
==================================================

Không cần exact template fidelity trong R005.

Nhưng export sau này phải có khả năng thêm:

tracking code
QR reference
current delivery date
process status

Không phá generic Excel services hiện tại.

==================================================
78. KNOWN GAP — LEGACY TEMPLATE
==================================================

Giữ:

TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE

Nếu workbook người dùng chưa được đặt vào DEV TEST ROOT.

Không block Stage 3.

==================================================
79. NAS
==================================================

Không triển khai production NAS write pipeline trong R005 trừ khi thực sự cần cho source-independent QR assets.

Ưu tiên giữ QR asset test local TEST ROOT.

Known gap:

NAS_WRITE_PIPELINE_NOT_YET_EXECUTED

==================================================
80. MACHINE A
==================================================

Không production deploy.

Máy hiện tại vẫn là DEV WORKSTATION.

Giữ:

MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED

==================================================
81. CANDIDATE PASS CRITERIA
==================================================

R005 PASS khi vertical slice chứng minh được:

Desktop
→ create/order tracking item
→ issue QR

Web
→ select/restore user
→ scan QR
→ show Product/Customer/Tracking/Delivery

Web
→ restore user machining preference

Web
→ default Lần 1–3
→ expand per tracking item + machining type

Web
→ submit Lần N
hoặc
→ ĐÃ XONG

Server
→ persistence
→ audit/history

Desktop/API
→ thấy report state/history

==================================================
82. CANDIDATE VERDICT
==================================================

Nếu đạt:

PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005

Không merge main trong R005.

Cần independent review/integration gate sau.

Nếu defect:

REJECT_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005_<REASON>

Nếu external blocker:

BLOCKED_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005_<REASON>

==================================================
83. NEXT STAGE — KHÔNG IMPLEMENT TRƯỚC
==================================================

Sau Stage 3 candidate/review:

Stage tiếp theo dự kiến:

QC
+
NG RETURN
+
PACKING
+
DELIVERY STATUS
+
REPORTING

Sau nữa:

NAS production storage
PostgreSQL/Machine A
production deployment
real iPhone/Android verification.

==================================================
84. CHAT POLICY
==================================================

Không đổi chat cơ học.

Nếu R005 hoàn thành mà context vẫn kiểm soát được:

TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI

Nếu R005 thực sự rất lớn và log/context nặng:

tạo checkpoint/handoff,
sau đó mới đề nghị chat mới.

==================================================
85. FINAL REPORT
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

Báo:

baseline HEAD/tree
branch
candidate HEAD/tree

tracking identity status
order identity status
QR status
QR scan resolution
delivery-date preservation
new-order clone identity
user profile
user machining preference
attempt expansion persistence
ĐÃ XONG
report history/revisions
idempotency
desktop
mobile web
SQLAlchemy/Alembic
QR tests
full regression
test isolation
known gaps
next action

==================================================
86. START
==================================================

Thực hiện:

PRECHECK_STAGE3_R005

→ create branch
→ save authority
→ implement identity model
→ QR
→ user preferences
→ process reports
→ web/mobile vertical slice
→ desktop integration
→ focused tests
→ full regression
→ isolation
→ checkpoint
→ candidate commit(s)
→ final report

Mục tiêu:

PASS_STAGE3_TRACKING_QR_PROCESS_REPORTING_R005