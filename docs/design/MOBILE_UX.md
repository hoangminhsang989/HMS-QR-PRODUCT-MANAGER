# Mobile UX

Factory-floor flow is scan → product card → action → submit → confirmation. The default is a soft light industrial surface with clear separators and dark text. Current user and machining preference remain visible without repeated prompts: `web/index.html` stores `hms-user` and `hms-process` in `localStorage` and restores them on load. Product/QR fields are clearly separated from live server fields.

## Actions

Of the 6 workflow actions named here, 6 sit in the QC mode and none in the machining mode: QC, shortage, NG/rework, packing, delivery and report — `QC_CHECKED`, `SHORTAGE_REPORTED`, `QC_NG_RETURNED_TO_MACHINING`, `PACKED`, `DELIVERED` and `GENERAL_REPORT`.

The machining mode carries two actions of its own, which this list does not cover: add-attempt (`expandAttempts`) and mark-stage-complete (`submitCompleted`).

## Forms

Each form requests only quantity and relevant notes. The QC form carries `#workflow-qty` and `#workflow-notes`; the machining form carries `#qty` and `#notes`. Neither has any other input.
