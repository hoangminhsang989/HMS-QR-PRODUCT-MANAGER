# HMS QR PRODUCT MANAGER

# STAGE 1 — PRODUCT MASTER VERTICAL SLICE

# AUTHORITY R002

## 0. AUTHORITY STATUS

Authority:

`STAGE1_PRODUCT_MASTER_VERTICAL_SLICE_R002`

Bắt đầu từ baseline đã được xác nhận:

```text
Repository:
F:\PHAN-MEM-QUAN-LY-QR

Branch:
main

HEAD:
45496d92e059d751741b896d4213123e45c7fdc1

Tree:
85e5ce5def6427766f672e1fbcae4fd9633d5b2e

Working tree:
clean

Previous verdict:
PASS_STAGE0_FOUNDATION_R001
```

Next objective:

`PASS_STAGE1_PRODUCT_MASTER_R002`

Codex phải lưu nguyên authority này vào:

```text
F:\PHAN-MEM-QUAN-LY-QR\docs\authorities\AUTHORITY_STAGE1_R002.md
```

Authority cũ không được sửa sau khi đã thực thi.

---

# 1. ĐỌC TRƯỚC KHI IMPLEMENT

Đọc tối thiểu:

```text
F:\PHAN-MEM-QUAN-LY-QR\PROJECT_STATE.md

F:\PHAN-MEM-QUAN-LY-QR\docs\handoffs\
HANDOFF_STAGE0_TO_STAGE1.md

F:\PHAN-MEM-QUAN-LY-QR\docs\ARCHITECTURE.md

F:\PHAN-MEM-QUAN-LY-QR\docs\DATA_MODEL.md

F:\PHAN-MEM-QUAN-LY-QR\docs\DECISIONS.md

F:\PHAN-MEM-QUAN-LY-QR\docs\SECURITY.md

F:\PHAN-MEM-QUAN-LY-QR\docs\TEST_POLICY.md

F:\PHAN-MEM-QUAN-LY-QR\docs\DEPLOYMENT_TOPOLOGY.md
```

Không làm lại Stage 0.

Không hỏi lại thông tin đã tồn tại trong repository/handoff/authority.

---

# 2. PHẠM VI R002

R002 phải tạo **vertical slice Product Master đầu tiên có thể chạy được**.

Chuỗi mục tiêu:

```text
Desktop Product Master
        ↓
Create / Edit Product
        ↓
Application Service
        ↓
Repository / Persistence
        ↓
Server API
        ↓
List / Search / Filter
        ↓
Excel Export
```

Đồng thời:

```text
Excel
   ↓
Import parser
   ↓
Preview / Validation
   ↓
Product records
```

R002 KHÔNG triển khai:

* mobile QR scanning hoàn chỉnh;
* PO workflow hoàn chỉnh;
* Production Run hoàn chỉnh;
* QC workflow hoàn chỉnh;
* giao hàng hoàn chỉnh;
* toàn bộ MES;
* public Internet deployment;
* production Máy A;
* NAS production write pipeline hoàn chỉnh.

Nhưng architecture phải chuẩn bị extension point cho các Stage sau.

---

# 3. LUẬT THƯ MỤC — TUYỆT ĐỐI

## Production source

```text
F:\PHAN-MEM-QUAN-LY-QR
```

## Test / temporary / generated artifacts

```text
F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST
```

Đây là nơi DUY NHẤT được phép chứa runtime artifact được sinh ra để test.

Bao gồm:

* pytest temp;
* `.pytest_cache`;
* coverage;
* junit XML;
* database test;
* Excel test;
* Excel export test;
* image test;
* generated QR test;
* screenshots;
* logs;
* debug output;
* benchmark;
* temp;
* build test;
* packaged test;
* runtime fixtures;
* UI screenshots;
* API test artifacts.

Không được:

```text
test xong rồi cleanup
```

như một giải pháp cho việc framework ghi vào production root.

Phải cấu hình từ đầu để artifact không được tạo ở production root.

Sau test bắt buộc chứng minh:

```text
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION
```

---

# 4. ENVIRONMENT IDENTITY

Máy đang chạy Codex hiện tại là:

```text
DEV WORKSTATION
```

KHÔNG được gọi hoặc giả định đây là Máy A.

Máy A là future production server.

Hiện Máy A chưa có tại vị trí đang phát triển.

Architecture phải hỗ trợ ít nhất:

```text
DEV
STAGING
PROD
```

Business logic không được hard-code hostname/IP/môi trường cụ thể.

---

# 5. NAS

Production NAS share đã biết:

```text
\\192.168.1.58\data-pm-qr
```

Máy DEV hiện tại kết nối được NAS qua LAN.

Trong R002:

* có thể kiểm tra read-only nếu cần;
* KHÔNG tạo file test tùy tiện trên NAS;
* KHÔNG dùng NAS làm test root;
* KHÔNG lưu database test trên NAS;
* KHÔNG để Desktop Client truy cập NAS trực tiếp;
* KHÔNG hard-code literal UNC path trong business logic.

Phải chuẩn bị configuration/storage abstraction.

Ví dụ concept:

```text
StorageService
    |
    +-- LocalDevStorage
    +-- NasStorage
    +-- FutureOtherStorage
```

Client về sau phải đi:

```text
Desktop / Mobile
       ↓
Server
       ↓
Storage Service
       ↓
NAS
```

Không:

```text
Desktop / Mobile
       ↓
NAS trực tiếp
```

---

# 6. DATABASE

Mục tiêu production:

```text
PostgreSQL chạy trên Máy A
```

NAS không chứa live production database.

Stage 0 ghi nhận:

```text
psql
pg_isready
```

chưa có trong `PATH`.

Đây KHÔNG phải blocker của R002.

Không tự ý cài PostgreSQL Server chỉ để làm unit test.

R002 được phép dùng:

```text
SQLite
```

cho isolated automated tests, với điều kiện:

* database file test nằm TEST ROOT;
* data layer vẫn thiết kế PostgreSQL-compatible;
* không sử dụng SQLite-specific behavior làm business contract;
* không tuyên bố PostgreSQL integration PASS nếu chưa chạy PostgreSQL thật.

---

# 7. STACK

Baseline:

## Server

```text
Python
FastAPI
SQLAlchemy 2.x
Pydantic
Alembic architecture
PostgreSQL target
```

## Desktop

```text
Python
PySide6
```

## Excel

Ưu tiên:

```text
openpyxl
```

Nếu dependency chưa có:

đánh giá dependency rõ ràng trước khi cài.

Không cài package ngẫu nhiên khi standard library / dependency hiện có đã giải quyết được.

---

# 8. GIT WORKFLOW

Preflight trước implementation:

```text
git status --short
git rev-parse HEAD
git rev-parse HEAD^{tree}
```

Phải xác nhận baseline chính xác hoặc giải thích drift.

Từ `main`, tạo branch:

```text
stage1-product-master
```

Không implement Stage 1 trực tiếp trên `main`.

Nếu working tree có thay đổi không xác định:

BLOCK.

Không tự discard dữ liệu người dùng.

---

# 9. DOMAIN — PRODUCT MASTER

Tạo Product domain rõ ràng.

Một Product tối thiểu cần các field/business concepts:

```text
internal_id / UUID

product_code

company / customer

part_name

quantity

unit

material

requester
(người đặt)

surface_treatment

outsourced
(đặt ngoài)

size

notes

delivery_schedule

status

created_at
updated_at

created_by
updated_by
```

Có thể chuẩn hóa tên field internal bằng English.

UI hiển thị tiếng Việt.

---

# 10. PRODUCT IDENTIFIER

Không dùng autoincrement DB ID làm business code chính.

Internal identity:

```text
UUID
```

Business identity:

```text
product_code
```

Baseline format có thể là:

```text
SP-2026-000001
```

Nhưng generator phải tách thành service/config.

Không viết logic format rải rác trong UI/API/model.

Thiết kế để sau này:

* đổi prefix;
* đổi sequence;
* phân loại customer;
* phân loại năm;
* import legacy code;

không cần migration toàn hệ thống.

Phải có uniqueness validation.

Concurrency strategy phải được ít nhất document ngay từ R002, dù test concurrency production có thể sang Stage sau.

---

# 11. PRODUCT STATUS

Không lưu màu như business status.

Status semantic baseline:

```text
NEW

WAITING

IN_PROGRESS

WAITING_QC

QC_PASS

QC_NG

REWORK

PACKED

DELIVERED

HOLD

CANCELLED
```

UI mapping màu riêng.

Ví dụ:

```text
status → semantic
theme → color mapping
```

Không:

```text
status = "#00FF00"
```

---

# 12. PRODUCT EXTENSION POINTS

Product Master phải chuẩn bị quan hệ/extension point cho:

```text
Product Images
Attachments
Drawing
Drawing Revision
Customer
PO
Production Run
Routing
Operation
QR
QC
Delivery
Audit
```

Nhưng R002 không được nhét toàn bộ dữ liệu đó vào một bảng Product khổng lồ.

Không tạo God Model.

---

# 13. AUDIT FOUNDATION

Mọi create/update product phải có metadata.

Tối thiểu:

```text
created_at
updated_at
created_by
updated_by
```

Time authority:

```text
server timestamp
```

Storage:

```text
UTC
```

Display mặc định:

```text
Asia/Ho_Chi_Minh
UTC+07:00
```

Không dựa tuyệt đối vào clock client.

Data model phải mở đường cho immutable audit/event history ở Stage sau.

Không thiết kế CRUD kiểu về sau không thể biết ai đã sửa gì.

---

# 14. REPOSITORY / SERVICE LAYERS

Không gọi database trực tiếp từ UI.

Không nhúng SQL vào widget.

Tách tối thiểu concept:

```text
Domain
Repository
Application Service
API
Desktop Presentation
Excel Service
Storage Service
```

Ví dụ:

```text
ProductRepository
ProductService
ProductCodeService
ProductExcelImporter
ProductExcelExporter
```

Tên cuối có thể khác nếu có lý do hợp lý.

---

# 15. SERVER API

Tạo versioned API:

```text
POST
/api/v1/products

GET
/api/v1/products

GET
/api/v1/products/{identifier}

PATCH
/api/v1/products/{identifier}
```

`identifier` phải hỗ trợ strategy rõ ràng cho UUID/product_code hoặc endpoint phân biệt hợp lý.

Không thiết kế ambiguity khó kiểm soát.

List endpoint hỗ trợ tối thiểu:

```text
pagination
search
status filter
```

Search có thể tìm các field phù hợp như:

```text
product_code
part_name
company/customer
material
```

API cần:

* validation;
* structured error;
* duplicate code handling;
* not-found handling;
* bad request handling;
* stable response schema.

Không cần hard delete ở R002.

Nếu chưa có archive business rule thì defer delete.

---

# 16. DESKTOP PRODUCT MASTER — FIRST USABLE UI

Tạo màn hình Product Master đầu tiên.

Phong cách:

```text
Dark mode
Gọn
High-density
Phù hợp ứng dụng cơ khí/sản xuất
Không dùng control quá to
```

Các chức năng tối thiểu:

```text
Danh sách sản phẩm

Tạo sản phẩm

Sửa sản phẩm

Refresh

Tìm kiếm

Filter trạng thái

Sort cột phù hợp

Status color

Hiển thị các trường chính
```

UI phải phản hồi lỗi rõ ràng bằng tiếng Việt.

Không để exception Python thô cho người dùng.

---

# 17. EXCEL-LIKE TABLE FOUNDATION

Người dùng muốn phần mềm PC có trải nghiệm nhập dữ liệu giống Excel.

R002 KHÔNG cần xây spreadsheet engine hoàn chỉnh.

Nhưng kiến trúc table phải chuẩn bị cho:

```text
keyboard navigation
multi-cell selection
copy
paste
bulk edit
sort
filter
image
formula
undo/redo
```

Không khóa kiến trúc vào widget đơn giản khiến Stage sau phải viết lại toàn bộ.

---

# 18. FILE EXCEL THỰC TẾ CỦA NGƯỜI DÙNG

Người dùng đang sử dụng workbook:

```text
LIST HÀNG THÁNG -07.xlsx
```

Đây là reference cho:

```text
Thông tin sản phẩm
+
Lịch giao hàng
```

Các đặc tính đã được ChatGPT kiểm tra từ workbook thực:

```text
Sheet:
05-07

Used area khoảng:
A1:Q127
```

Workbook có:

* phần thông tin công ty ở phía trên;
* header bảng màu xanh;
* ngày/tháng nổi bật màu vàng;
* Picture;
* Company;
* Part Name;
* Quantity;
* Unit;
* Material;
* Người đặt;
* Surface treatment;
* Đặt ngoài;
* Size;
* Ghi chú;
* Lịch Vendor giao hàng;
* ảnh sản phẩm;
* một số cột giá/thành tiền ẩn;
* một số công thức Excel;
* row/column formatting.

Đây phải được coi là:

```text
REFERENCE_EXCEL_PRODUCT_DELIVERY_TEMPLATE_V1
```

---

# 19. VỊ TRÍ FILE EXCEL MẪU

Không giả định file Excel mẫu đã có trên DEV workstation.

Nếu người dùng sau này copy file vào máy để Codex test, file reference/test phải đặt dưới TEST ROOT, ví dụ:

```text
F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\
references\
LIST HÀNG THÁNG -07.xlsx
```

Không đặt workbook test/reference vào source production root.

Nếu file không tồn tại:

R002 KHÔNG BLOCK.

Phải triển khai:

```text
generic import/export foundation
+
template contract
```

và ghi gap:

```text
TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
```

Không được tuyên bố:

```text
EXACT_TEMPLATE_MATCH_PASS
```

khi chưa mở workbook thật trên DEV.

---

# 20. EXCEL IMPORT

R002 phải có architecture và implementation cơ bản cho:

```text
Excel
 ↓
Read workbook
 ↓
Detect/map columns
 ↓
Validate rows
 ↓
Preview
 ↓
Import
```

Tối thiểu hỗ trợ:

* field mapping;
* header normalization;
* empty row handling;
* type conversion;
* quantity validation;
* status mapping nếu có;
* date/delivery schedule parsing phù hợp;
* validation result;
* duplicate strategy;
* dry-run/preview.

Không silently bỏ dòng lỗi.

Phải có result kiểu:

```text
valid rows
invalid rows
warnings
errors
duplicates
```

Import thật chỉ chạy sau validation.

---

# 21. DUPLICATE IMPORT POLICY

Không đoán duplicate chỉ dựa trên tên sản phẩm.

Thiết kế duplicate policy theo thứ tự/business identifier phù hợp.

Ví dụ:

```text
product_code
```

nếu tồn tại.

Nếu Excel legacy chưa có product_code:

phải có strategy/documentation rõ ràng.

Có thể đưa dòng về:

```text
PENDING_USER_REVIEW
```

thay vì tự merge sai.

R002 không được silently overwrite record hiện có.

---

# 22. EXCEL EXPORT

R002 phải export Product Master cơ bản ra `.xlsx`.

Mọi file test export phải nằm TEST ROOT.

Architecture phải chuẩn bị cho:

```text
Generic Export

Template Export

Filtered Export

Monthly Export

Customer Export

Delivery Schedule Export
```

Export service không nằm trong UI class.

UI chỉ gọi service.

---

# 23. TEMPLATE FIDELITY TARGET

Long-term phải có khả năng xuất lại gần/đúng workbook mẫu người dùng đang sử dụng.

Cần chuẩn bị support cho:

```text
merged cells

font

alignment

borders

fills

number formats

row height

column width

hidden columns

formulas

images

header/company information

delivery schedule

month/date presentation
```

R002 không nhất thiết hoàn thiện pixel fidelity nếu workbook thật chưa có trên DEV.

Nhưng architecture không được phá khả năng đó.

---

# 24. EXCEL FORMULAS

Không cần tự viết một Excel calculation engine ở R002.

Nếu template có formula:

có thể preserve/write formula string phù hợp.

Lưu ý:

`openpyxl` không phải Excel calculation engine.

Không tuyên bố đã calculate mọi formula chỉ vì workbook chứa formula.

Nếu cần derived value trong app:

business-critical calculation phải có logic riêng trong application layer.

Không dùng Excel formula làm nguồn business truth duy nhất.

---

# 25. PRODUCT IMAGE FOUNDATION

Workbook có cột Picture.

Product Master phải chuẩn bị image metadata.

Không lưu binary image lớn trực tiếp vào Product record nếu không có lý do mạnh.

Thiết kế concept:

```text
ProductAttachment
ProductImage
StorageReference
```

R002 tối thiểu có thể hỗ trợ:

* reference metadata;
* placeholder/UI extension;
* Excel exporter architecture có hook để chèn ảnh.

NAS image pipeline hoàn chỉnh sang Stage sau.

---

# 26. CONFIGURATION

Tạo cấu hình rõ ràng theo environment.

Ví dụ concept:

```text
config/
    dev
    staging
    prod
```

Không commit:

* password;
* database secrets;
* NAS credential;
* API secret;
* production token.

Có `.env.example`/config template nếu phù hợp.

Production NAS path có thể xuất hiện trong production configuration/documentation, nhưng không nằm literal trong business logic.

---

# 27. NODE / NPM GHI NHẬN

Stage 0:

Node tồn tại tại dạng:

```text
C:\Program Files\nodejs\node.exe
```

`npm.ps1` bị PowerShell execution policy chặn.

R002 không yêu cầu Node frontend.

KHÔNG thay PowerShell execution policy hệ thống.

Nếu một thao tác thật sự cần npm, trước tiên đánh giá:

```text
npm.cmd
```

hoặc invocation bounded tương đương.

Không làm đây thành blocker nếu không cần Node.

---

# 28. TEST MATRIX — BẮT BUỘC

Tạo test đủ mạnh cho R002.

Tối thiểu:

## Domain

```text
Product validation
Required fields
Quantity validation
Status validation
UUID behavior
```

## Product code

```text
Valid format
Invalid format
Generation
Uniqueness behavior
```

## Repository

```text
Create
Read
Update
List
Search
Filter
Duplicate
```

## API

```text
POST product
GET list
GET one
PATCH
404
validation error
duplicate handling
pagination
search
filter
```

## Audit metadata

```text
created_at
updated_at
created_by
updated_by
UTC behavior
```

## Excel import

```text
valid workbook
invalid row
empty row
type conversion
duplicate strategy
preview mode
```

## Excel export

```text
xlsx created
expected headers
expected values
valid workbook open
```

## Desktop

```text
import smoke
model/view smoke
Product Master window smoke
create/edit form validation
```

Nếu UI test cần headless:

dùng bounded Qt offscreen approach phù hợp.

## Configuration

```text
DEV profile
STAGING profile
PROD profile schema
NAS path abstraction
```

## Isolation

```text
TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION
```

---

# 29. TEST DATABASE

Nếu dùng SQLite test:

file phải nằm ví dụ:

```text
F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\
db\
stage1_r002_test.sqlite
```

Không:

```text
F:\PHAN-MEM-QUAN-LY-QR\test.sqlite
```

Nếu in-memory SQLite đủ cho test cụ thể thì có thể dùng.

Nhưng test persistence/file behavior phải vẫn theo isolation policy.

---

# 30. TEST EXCEL

Generated workbook ví dụ:

```text
F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST\
excel\
stage1_r002_export.xlsx
```

Fixtures generated runtime cũng nằm TEST ROOT.

Chỉ source fixture nhỏ cần version-control mới được nằm tests source tree, và phải được justify.

Không commit binary Excel test output.

---

# 31. SOURCE QUALITY

Không tạo một file Python khổng lồ chứa:

```text
database
API
UI
Excel
business logic
```

Tách module theo responsibility.

Dùng type hints phù hợp.

Không over-engineer framework nội bộ.

Không duplicate model definitions không cần thiết.

API schema và domain model có thể khác layer nếu cần.

---

# 32. ERROR HANDLING

UI tiếng Việt.

Ví dụ:

```text
Không thể tạo sản phẩm: mã sản phẩm đã tồn tại.

Không thể nhập dòng 27: Quantity phải lớn hơn 0.

Không thể xuất Excel: thư mục đích không khả dụng.
```

Technical log có thể giữ traceback.

Không hiển thị raw stack trace làm UX bình thường.

---

# 33. SECURITY FOUNDATION

R002 chưa cần authentication hoàn chỉnh.

Nhưng không design endpoint theo assumption:

```text
mọi caller đều admin vĩnh viễn
```

Actor identity hiện có thể truyền qua development context/header/test fixture theo contract tạm thời.

Phải document đây là transitional architecture.

Không hard-code:

```text
admin
123456
```

trong source production.

---

# 34. USER DISPLAY

Người dùng mobile sau này sẽ nhập tên ngay từ đầu.

Desktop cũng cần concept actor/user.

R002 chỉ cần foundation.

Không xây full Identity subsystem.

Nhưng:

```text
created_by
updated_by
```

không được để architecture vô nghĩa.

---

# 35. DELIVERY SCHEDULE

Do workbook thực tế quản lý lịch giao hàng, Product Master phải có representation phù hợp.

Không bắt buộc nhét toàn bộ logistics workflow vào một string nếu data model cần cấu trúc hơn.

Codex phải đánh giá liệu:

```text
delivery_schedule
```

nên là:

* field đơn giản ban đầu;
* hoặc child entity/value object.

Nếu chọn field đơn giản trong R002:

document migration path sang structured delivery schedule.

Không overbuild Stage 1.

---

# 36. CURRENT QUANTITY SEMANTICS

Workbook có Quantity.

R002 phải phân biệt ít nhất trên documentation:

```text
ordered/product quantity
```

khác với future:

```text
processed quantity
QC quantity
NG quantity
packed quantity
delivered quantity
```

Không dùng một `quantity` duy nhất sau này cho mọi trạng thái sản xuất.

Stage 1 Product quantity có meaning rõ ràng.

---

# 37. UI STATUS COLORS

Product table phải có báo màu trạng thái.

Nhưng màu chỉ presentation mapping.

Ví dụ conceptual:

```text
NEW         → neutral
IN_PROGRESS → active
WAITING_QC  → attention
QC_PASS     → success
QC_NG       → error
PACKED      → packed
DELIVERED   → completed
```

Không cần cố định palette trước khi final UX review.

Dark mode phải dễ nhìn.

---

# 38. DESKTOP APP STARTUP

Desktop app phải có entry point rõ ràng.

Không yêu cầu user chạy module ngẫu nhiên.

Development launch có thể dạng:

```text
python -m ...
```

và được document.

Stage sau mới đóng gói `.exe`.

---

# 39. SERVER STARTUP

Server app phải có entry point rõ ràng.

Development startup được document.

Không yêu cầu production Windows Service trong R002.

Production service/deployment để Stage sau.

---

# 40. MIGRATIONS

Nếu SQLAlchemy schema được tạo:

chuẩn bị Alembic architecture.

Nếu PostgreSQL chưa tồn tại và Alembic migration chưa thể integration-test production:

vẫn có thể tạo initial migration hoặc migration framework, nhưng phải báo evidence chính xác.

Không tuyên bố migration production PASS khi chưa test PostgreSQL.

---

# 41. PRODUCT MASTER UX — MINIMUM ACCEPTANCE

R002 được xem là desktop usable khi có thể:

1. Mở Product Master.
2. Xem danh sách.
3. Tạo một Product hợp lệ.
4. Thấy Product xuất hiện.
5. Tìm Product.
6. Filter status.
7. Sửa Product.
8. Refresh vẫn còn dữ liệu.
9. Export Product ra Excel.
10. Lỗi validation được báo rõ.

Nếu persistence test dùng isolated development configuration, báo chính xác môi trường.

---

# 42. EXCEL IMPORT UX FOUNDATION

Nếu desktop UI cho import được triển khai trong R002:

flow ưu tiên:

```text
Chọn file
  ↓
Phân tích
  ↓
Preview
  ↓
Hiển thị lỗi/cảnh báo
  ↓
Người dùng xác nhận import
```

Không:

```text
chọn file → ghi DB ngay lập tức
```

Nếu UI import chưa đầy đủ nhưng service/tests đạt, ghi rõ gap.

Vertical slice PASS cần đủ usable theo acceptance đã chốt; không phóng đại.

---

# 43. EXCEL EXPORT UX FOUNDATION

Nút:

```text
Xuất Excel
```

có thể hỗ trợ tối thiểu:

* current result;
* hoặc toàn Product Master.

Future options:

```text
Tháng
Khách hàng
Status
Đã giao/chưa giao
PO
```

không cần hoàn thiện toàn bộ R002.

---

# 44. PERFORMANCE

Không cần benchmark cực lớn R002.

Nhưng table/repository không được viết kiểu chắc chắn O(N²) cho thao tác phổ biến nếu tránh được.

List API có pagination.

Desktop không assume toàn bộ database luôn nhỏ.

---

# 45. CHECKPOINT

Sau khi implementation và verification hoàn tất tạo:

```text
docs/checkpoints/CHECKPOINT_STAGE1_R002.md
```

Nội dung tối thiểu:

```text
Date
Stage
WP
Revision

Repository
Branch

Baseline HEAD
Baseline tree

Candidate HEAD
Candidate tree
Parent

Objective

Completed work

Changed paths

Tests executed

Exact results

Excel status

Desktop status

API status

Persistence status

Known gaps

Blockers/non-blockers

Decisions

Risks

Next exact action

Resume instruction
```

---

# 46. PROJECT STATE

Update:

```text
PROJECT_STATE.md
```

Ngắn gọn.

Không biến thành log hàng nghìn dòng.

Có:

```text
Current Stage
Current WP
Current Revision
Branch
HEAD
Last approved baseline
Current verdict

Stage progress
Overall progress

Active blockers
Latest completed work
Next exact action
Latest authority
Latest checkpoint
```

---

# 47. DECISION LOG

Nếu phát sinh architectural decision mới đáng kể, update:

```text
docs/DECISIONS.md
```

Ví dụ có thể cần:

```text
Excel import/export architecture
Product identifier strategy
Product quantity semantics
Delivery schedule representation
SQLite test portability
```

Không ghi từng implementation detail thành ADR.

---

# 48. DOCUMENTATION

Update nếu cần:

```text
README.md
ARCHITECTURE.md
DATA_MODEL.md
TEST_POLICY.md
SECURITY.md
PROJECT_STATE.md
DECISIONS.md
```

Không viết tài liệu dư thừa chỉ để tăng số file.

---

# 49. VERIFICATION ORDER

Trước khi verdict:

1. Focused domain tests.
2. Repository tests.
3. API tests.
4. Excel tests.
5. Desktop smoke.
6. Configuration tests.
7. Existing regression.
8. Test isolation guard.
9. `git diff --check`.
10. Review `git diff`.
11. Check `git status`.
12. Check generated artifact locations.

Không gọi PASS nếu evidence không đủ.

---

# 50. COMMIT STRATEGY

Không commit mỗi thay đổi nhỏ vô nghĩa.

Có thể dùng các commit có trách nhiệm rõ ràng, ví dụ:

```text
stage1: establish product master domain and persistence

stage1: add product API and desktop management slice

stage1: add Excel import export foundation

stage1: record product master checkpoint
```

Không bắt buộc đúng 4 commit.

Quan trọng là history dễ audit.

---

# 51. KHÔNG MERGE MAIN TRONG R002

R002 implementation ở branch:

```text
stage1-product-master
```

Sau khi local PASS:

không tự merge main nếu authority chưa yêu cầu integration review.

Stage tiếp theo/review authority sẽ quyết định merge.

---

# 52. PASS CRITERIA

Chỉ dùng verdict:

```text
PASS_STAGE1_PRODUCT_MASTER_R002
```

nếu tất cả điều cốt lõi đạt:

### Domain

PASS

### Persistence

PASS trong môi trường test được khai báo chính xác.

### API

Create/read/update/list/search/filter PASS.

### Desktop

Usable Product Master smoke PASS.

### Excel

Import foundation PASS.

Export foundation PASS.

### Isolation

PASS.

### Git

Candidate state explainable.

### Documentation

Updated.

### Checkpoint

Created.

Known future gaps được phép tồn tại nếu ngoài R002.

---

# 53. BLOCKED / REJECT

Nếu external prerequisite ngăn hoàn tất:

```text
BLOCKED_STAGE1_PRODUCT_MASTER_R002_<REASON>
```

Ví dụ:

```text
BLOCKED_STAGE1_PRODUCT_MASTER_R002_REQUIRED_DEPENDENCY_UNAVAILABLE
```

Nếu implementation/test phát hiện defect khiến candidate không đạt:

```text
REJECT_STAGE1_PRODUCT_MASTER_R002_<REASON>
```

Không dùng BLOCKED để che defect code.

Không dùng REJECT cho external prerequisite.

---

# 54. EXCEL TEMPLATE VERDICT RIÊNG

Nếu workbook thực tế chưa tồn tại trên máy DEV:

được phép Stage 1 PASS với:

```text
GENERIC_EXCEL_IMPORT_EXPORT_PASS

TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE
```

Miễn generic Excel architecture/tests đạt.

Không được ghi:

```text
REFERENCE_EXCEL_TEMPLATE_PASS
```

nếu chưa test file thật.

---

# 55. POSTGRESQL VERDICT RIÊNG

Nếu R002 dùng SQLite isolated:

có thể:

```text
SQLITE_TEST_PERSISTENCE_PASS

POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED
```

Điều này không tự động BLOCK R002.

Không ghi:

```text
POSTGRESQL_PASS
```

nếu PostgreSQL chưa chạy.

---

# 56. NAS VERDICT RIÊNG

R002 không cần ghi file production NAS.

Có thể xác nhận:

```text
NAS_CONFIGURATION_CONTRACT_PASS
```

và nếu thực hiện read-only accessibility check:

```text
NAS_READ_ONLY_PREFLIGHT_PASS
```

Không tự tạo evidence file trên NAS.

---

# 57. BÁO CÁO TIẾN ĐỘ — BẮT BUỘC

Báo cáo Codex cuối authority phải bắt đầu bằng:

```text
TIẾN ĐỘ PHẦN MỀM

Stage:
WP:
Revision:

Stage progress:
Overall progress:

Verdict:

Blocker:
```

Sau đó:

```text
KHUYẾN NGHỊ CODEX
```

---

# 58. NỘI DUNG BÁO CÁO CUỐI

Báo tối thiểu:

```text
Baseline HEAD/tree

Branch

Candidate HEAD/tree

Working tree

Changed paths

Implemented functionality

Product model status

Persistence status

API status

Desktop status

Excel import status

Excel export status

NAS abstraction status

PostgreSQL status

Test matrix

Exact pass/fail counts

Test isolation result

Known gaps

Risks

Next exact action
```

---

# 59. CHAT / TOKEN MANAGEMENT

KHÔNG tự đề nghị đổi chat chỉ vì vừa xong R002.

Checkpoint/handoff và đổi chat là hai việc khác nhau.

Ưu tiên:

```text
TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI
```

nếu:

* context còn gọn;
* reasoning vẫn ổn;
* chưa tích lũy quá nhiều log;
* Stage tiếp theo liên quan chặt đến Product Master.

Chỉ dùng:

```text
TẠO CHAT CODEX MỚI
```

khi:

* context đã dài rõ rệt;
* log/test/evidence quá nhiều;
* reasoning có dấu hiệu giảm;
* vừa hoàn tất một mega-WP lớn;
* chuẩn bị sang subsystem khác biệt đáng kể.

Không chuyển chat cơ học theo số Stage.

---

# 60. NEXT ROADMAP — KHÔNG IMPLEMENT TRƯỚC

Nếu R002 PASS, candidate roadmap dự kiến:

```text
Stage 1 continuation / Stage 2
Customer + PO + Production Run

sau đó

Routing + Operations

sau đó

QR issuance

sau đó

Mobile QR workflow

sau đó

QC / NG / rework

sau đó

Packing / Delivery
```

Nhưng không triển khai ngoài R002 trong authority này.

---

# 61. KHÔNG ĐƯỢC

Không được:

* tự suy diễn scope ngoài authority;
* sửa Stage 0;
* hard-code NAS vào business logic;
* ghi test lên NAS;
* tạo test artifacts trong production root;
* cài PostgreSQL production chỉ để test;
* thay PowerShell execution policy toàn máy;
* viết UI gọi SQL trực tiếp;
* tạo God Model;
* dùng màu làm status;
* hard delete Product không có policy;
* silently overwrite Excel duplicate;
* silently bỏ dòng Excel lỗi;
* tuyên bố template Excel exact-match khi chưa test;
* tuyên bố PostgreSQL PASS khi chưa chạy;
* merge `main` trước review;
* báo PASS nếu test isolation fail;
* xóa evidence để làm working tree đẹp;
* xóa dữ liệu không rõ nguồn gốc.

---

# 62. THỰC HIỆN NGAY

Bắt đầu bằng:

```text
PRECHECK_STAGE1_R002
```

Xác nhận:

```text
repo
branch
HEAD
tree
working tree
test root
required docs
Python/dependencies
```

Sau đó:

```text
create stage1-product-master branch
→ save authority
→ implement
→ focused test
→ vertical slice verification
→ regression
→ isolation verification
→ checkpoint
→ commits
→ final report
```

Không hỏi lại thông tin authority đã cung cấp.

Nếu có vấn đề kỹ thuật có thể giải quyết an toàn trong phạm vi authority:

tự xử lý và tiếp tục.

Chỉ dừng khi có blocker thực sự.

Mục tiêu:

```text
PASS_STAGE1_PRODUCT_MASTER_R002
```

hoặc verdict BLOCKED/REJECT có evidence chính xác.

Cuối báo cáo ghi chính xác một trong hai:

```text
TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI
```

hoặc:

```text
TẠO CHAT CODEX MỚI
```
