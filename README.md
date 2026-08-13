# HMS QR Product Manager

Foundation repository for the HMS QR Product Manager: a QR server on Machine A,
desktop clients, and a mobile web/PWA client.

Stage 0 establishes architecture, test isolation, and traceable project state.
Business workflows are intentionally deferred until the foundation gate passes.

Stage 1 adds the first Product Master vertical slice on branch
`stage1-product-master`: validated Product domain, SQLite DEV/test repository,
versioned API, Vietnamese PySide6 desktop window, and generic Excel
preview/confirm/import/export. PostgreSQL production integration and exact
legacy workbook fidelity are intentionally pending.

Development entry points:

```text
python -m apps.desktop
uvicorn apps.server.app:app --reload
```

Stage 2 adds the Customer → PO → PO Line → Delivery Schedule / Production Run
vertical slice with SQLAlchemy/Alembic architecture, generic order export, and
compact desktop navigation tabs. QR issuance, mobile scan, QC, NAS writes, and
Machine A deployment remain outside R004.

Stage 3 adds Order Tracking Items, opaque QR issuance/live scan resolution,
operator and machining preferences, dynamic attempt reporting, report revision
history, a compact desktop tracking window, and a responsive mobile-first web
page at `/tracking/mobile`. Real camera verification still requires HTTPS and
physical iPhone/Android testing.

## Test workspace

All test/runtime artifacts belong in:

`F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`

The production tree must remain source/documentation only.
