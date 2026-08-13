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

## Test workspace

All test/runtime artifacts belong in:

`F:\PHAN-MEM-QUAN-LY-QR-FILE-CHAY-TEST`

The production tree must remain source/documentation only.
