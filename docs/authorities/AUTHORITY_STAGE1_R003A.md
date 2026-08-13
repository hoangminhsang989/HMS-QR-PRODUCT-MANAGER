# HMS QR PRODUCT MANAGER

# STAGE 1 — PRODUCT MASTER

# R003A — EXCEL WORKBOOK LIFECYCLE REMEDIATION + FRESH INTEGRATION REVIEW

## TIẾN ĐỘ PHẦN MỀM

Stage:
Stage 1 — Product Master

WP:
Excel lifecycle remediation + fresh integration review

Revision:
R003A

Current rejected verdict:

`REJECT_STAGE1_PRODUCT_MASTER_R003_EXCEL_PREVIEW_LEAVES_WORKBOOK_OPEN`

Candidate branch:

`stage1-product-master`

Rejected candidate HEAD:

`fb6453e97f472d2a96ebc3e6f4f0a7e5dbc0dfa6`

Rejected candidate tree:

`7f1dff3a1d53314e32f46ac75a3b216edd6d6c76`

Main baseline:

`45496d92e059d751741b896d4213123e45c7fdc1`

Main MUST remain unchanged until fresh review passes.

## KHUYẾN NGHỊ CODEX

`TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI`

---

# 1. ROOT CAUSE ĐÃ ĐƯỢC INDEPENDENT REVIEW XÁC NHẬN

Defect:

`ProductExcelImporter.preview()` mở workbook bằng:

```python
load_workbook(path, read_only=True, data_only=False)
```

nhưng workbook không được đóng sau khi preview hoàn tất.

Observed consequence trên Windows:

```text
PermissionError: [WinError 32]
The process cannot access the file because it is being used by another process
```

Independent review reproduction:

* tạo workbook trong TEST ROOT;
* gọi preview;
* cleanup file ngay;
* cleanup fail vì workbook/file handle vẫn mở.

Đây là candidate defect.

Không phải external blocker.

---

# 2. PHẠM VI R003A

R003A chỉ được:

1. sửa lifecycle của workbook trong Excel importer;
2. audit các đường `load_workbook()` liên quan trong Stage 1 để phát hiện cùng class defect;
3. thêm regression tests;
4. chạy fresh verification toàn candidate;
5. nếu PASS, thực hiện lại integration review gate;
6. chỉ merge `main` sau fresh approval.

Không mở rộng:

* PO;
* Production Run;
* QR;
* mobile;
* QC;
* PostgreSQL production;
* NAS write pipeline;
* authentication.

---

# 3. PRE-EDIT GATE

Trước sửa:

Xác nhận:

```text
repo
branch
HEAD
tree
working tree
main baseline
```

Expected branch:

`stage1-product-master`

Expected rejected HEAD:

`fb6453e97f472d2a96ebc3e6f4f0a7e5dbc0dfa6`

Nếu HEAD đã drift:

record exact reason trước khi edit.

Không discard bất kỳ user changes nào.

---

# 4. REMEDIATION REQUIREMENT

Fix phải bảo đảm workbook được đóng trong **mọi đường thoát**, bao gồm:

* preview thành công;
* validation error;
* exception trong row parsing;
* exception trong header mapping;
* early return;
* duplicate/warning path.

Ưu tiên lifecycle có cấu trúc chắc chắn như:

```python
workbook = load_workbook(...)
try:
    ...
finally:
    workbook.close()
```

hoặc abstraction tương đương rõ ràng.

Không chỉ thêm `.close()` ở happy path.

Không dựa vào garbage collection/destructor.

Không dùng sleep/retry để che file lock.

---

# 5. AUDIT CÙNG CLASS DEFECT

Search toàn Stage 1 source cho:

```text
load_workbook(
Workbook(
open(
NamedTemporaryFile
TemporaryDirectory
```

Tập trung các resource có lifecycle phải đóng.

Không sửa linh tinh ngoài phạm vi.

Báo:

```text
RESOURCE_LIFECYCLE_AUDIT_PATH_COUNT=
ADDITIONAL_CONFIRMED_DEFECT_COUNT=
```

Nếu phát hiện defect cùng class thực sự:

được phép sửa trong R003A nếu nhỏ và liên quan trực tiếp lifecycle Excel.

Nếu phát hiện vấn đề lớn khác:

STOP và báo REJECT mới thay vì mở rộng scope âm thầm.

---

# 6. REGRESSION TEST BẮT BUỘC

Thêm test tái hiện chính xác defect Windows lifecycle.

Tối thiểu:

### Test A — preview rồi xóa ngay

```text
create workbook in TEST ROOT
→ ProductExcelImporter.preview()
→ immediately delete workbook
→ PASS
```

Không retry.

Không sleep.

### Test B — preview validation/error path

Tạo workbook khiến parser trả validation failure hoặc exception path phù hợp.

Sau preview/error handling:

```text
immediately delete workbook
→ PASS
```

Mục tiêu chứng minh workbook vẫn được đóng khi không đi happy path.

### Test C — repeated preview

```text
preview same workbook multiple times
→ no accumulated handle leak
→ delete immediately
```

### Test D — export/read lifecycle nếu liên quan

Nếu exporter hoặc verification code dùng `load_workbook`, kiểm tra nó cũng đóng resource.

---

# 7. TEST ARTIFACT POLICY

Tất cả workbook regression phải nằm dưới:

```text
F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST
```

Không tạo file Excel runtime trong:

```text
F:\PHAN-MEM-QUAN-LY-QR
```

Sau test:

```text
TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION
```

---

# 8. FOCUSED VERIFICATION

Sau fix chạy fresh:

1. Excel lifecycle regression tests.
2. Excel importer tests.
3. Excel exporter tests.
4. Domain/repository/API focused suite.
5. Desktop/config smoke.
6. Full regression.

Không dùng kết quả R002/R003 cũ làm evidence thay cho fresh execution.

---

# 9. EXACT FILE-LOCK PROOF

R003A phải có evidence trực tiếp rằng defect cũ đã hết.

Ví dụ:

```text
EXCEL_PREVIEW_FILE_RELEASE_TEST=PASS
EXCEL_PREVIEW_ERROR_PATH_RELEASE_TEST=PASS
EXCEL_REPEATED_PREVIEW_RELEASE_TEST=PASS
```

Nếu Windows cleanup vẫn fail dù chỉ một lần:

REJECT.

Không gọi flaky PASS bằng retry.

---

# 10. STATIC / DIFF REVIEW

Sau remediation:

```text
git diff --check
```

Review diff từ rejected candidate:

```text
fb6453e97f472d2a96ebc3e6f4f0a7e5dbc0dfa6
```

đến remediated candidate.

Expected scope:

* importer lifecycle fix;
* directly related tests;
* authority/checkpoint/state docs nếu cần.

Báo:

```text
R003A_CHANGED_PATH_COUNT=
R003A_UNRELATED_CHANGE_COUNT=
```

Expected:

`R003A_UNRELATED_CHANGE_COUNT=0`

---

# 11. COMMIT REMEDIATION

Nếu focused + regression PASS:

commit remediation với message rõ ràng, ví dụ:

```text
stage1: close Excel workbooks after product preview
```

Record:

```text
REMEDIATED_HEAD
REMEDIATED_TREE
```

Working tree phải sạch trước fresh review gate.

---

# 12. FRESH R003 REVIEW GATE

Sau remediation commit, không tự coi candidate approved.

Chạy lại fresh independent-style review trên toàn Stage 1 diff:

```text
main baseline
45496d92e059d751741b896d4213123e45c7fdc1

→ remediated candidate HEAD
```

Review lại tối thiểu:

* full diff;
* architecture boundaries;
* Product domain;
* Product code;
* repository;
* API;
* desktop;
* Excel import/export;
* config/storage abstraction;
* test isolation.

Báo:

```text
DIFF_REVIEW_FILE_COUNT=
UNRELATED_CHANGE_COUNT=
```

---

# 13. FRESH FULL TEST MATRIX

Sau remediation candidate frozen:

Chạy fresh:

### Product/domain/repository

PASS required.

### API

PASS required.

### Excel

PASS required, bao gồm lifecycle tests mới.

### Desktop

PASS required.

### Configuration

PASS required.

### Full regression

PASS required.

### Isolation

PASS required.

### git diff --check

PASS required.

Báo exact:

```text
passed
failed
skipped
warnings
duration
```

---

# 14. REVIEW VERDICT TRƯỚC MERGE

Nếu bất kỳ candidate defect mới nào được tái hiện:

```text
REJECT_STAGE1_PRODUCT_MASTER_R003A_<REASON>
```

Không merge.

Nếu external prerequisite thật:

```text
BLOCKED_STAGE1_PRODUCT_MASTER_R003A_<REASON>
```

Không merge.

Chỉ khi fresh review đạt:

```text
APPROVE_STAGE1_PRODUCT_MASTER_R003A_INTEGRATION
```

mới được integration.

---

# 15. INTEGRATE VÀO MAIN

Chỉ sau APPROVE.

Checkout:

```text
main
```

Xác nhận trước merge:

```text
HEAD == 45496d92e059d751741b896d4213123e45c7fdc1
working tree clean
```

Nếu main drift:

STOP.

Ưu tiên fast-forward nếu graph cho phép.

Không:

* force;
* squash;
* rebase history;
* push remote;

trừ khi authority khác cho phép.

---

# 16. POST-INTEGRATION VERIFICATION

Sau merge vào main chạy fresh tối thiểu:

* Excel lifecycle regression;
* Product focused suite;
* API;
* Excel import/export;
* Desktop smoke;
* full regression;
* isolation guard.

Xác nhận:

```text
MAIN_WORKING_TREE=CLEAN
TEST_ISOLATION_PASS
NO_RUNTIME_ARTIFACTS_IN_PRODUCTION
```

Record:

```text
MAIN_HEAD=
MAIN_TREE=
```

---

# 17. CHECKPOINT

Tạo:

```text
docs/checkpoints/CHECKPOINT_STAGE1_R003A_INTEGRATION.md
```

Ghi:

* rejected candidate identity;
* root cause;
* exact remediation;
* changed paths;
* lifecycle tests;
* fresh full review;
* approval verdict;
* integration method;
* main resulting HEAD/tree;
* post-integration tests;
* known gaps;
* next exact action.

---

# 18. PROJECT STATE

Nếu integration PASS:

Update:

```text
PROJECT_STATE.md
```

Current verdict:

```text
PASS_STAGE1_PRODUCT_MASTER_R003A_INTEGRATED
```

Stage 1:

```text
100%
```

Known gaps vẫn phải giữ chính xác:

```text
POSTGRESQL_PRODUCTION_INTEGRATION_NOT_YET_EXECUTED

TEMPLATE_FIDELITY_PENDING_REFERENCE_FILE

NAS_WRITE_PIPELINE_NOT_YET_EXECUTED

MACHINE_A_PRODUCTION_DEPLOYMENT_NOT_YET_EXECUTED
```

Next exact action:

```text
STAGE2_CUSTOMER_PO_PRODUCTION_RUN_R004
```

---

# 19. FINAL VERDICT

Mục tiêu tốt nhất:

```text
PASS_STAGE1_PRODUCT_MASTER_R003A_INTEGRATED
```

Không dùng lại `PASS_STAGE1_PRODUCT_MASTER_R002` làm final integration verdict.

---

# 20. FINAL REPORT FORMAT

Bắt đầu bằng:

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

Báo tối thiểu:

```text
Rejected candidate HEAD/tree

Root cause

Remediation paths

Resource lifecycle audit results

New regression tests

Remediated HEAD/tree

Fresh diff review count

Unrelated change count

Full test matrix

Excel lifecycle proof

Test isolation result

Integration method

Resulting main HEAD/tree

Working tree

Known gaps

Next exact action
```

---

# 21. CHAT POLICY

Nếu R003A PASS và context vẫn gọn:

```text
TIẾP TỤC TRONG CHAT CODEX HIỆN TẠI
```

Không tạo handoff/chat mới chỉ vì vừa xong integration.

Stage tiếp theo:

```text
CUSTOMER + PO + PRODUCTION RUN
```

liên quan trực tiếp Product Master và nên tiếp tục cùng context nếu còn ổn.

---

# 22. THỰC HIỆN NGAY

Bắt đầu từ rejected candidate hiện tại.

Không làm lại Stage 1 từ đầu.

Không sửa unrelated code.

Không merge main trước fresh approval.

Mục tiêu:

```text
PASS_STAGE1_PRODUCT_MASTER_R003A_INTEGRATED
```
