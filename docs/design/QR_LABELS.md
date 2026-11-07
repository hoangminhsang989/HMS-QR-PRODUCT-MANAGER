# QR label foundation

The encoded QR object is always the four-field contract documented in `DESIGN.md`: `product_name`, `customer_name`, `product_code`, `tracking_code`. That is enforced rather than merely intended — `packages/qr/payload.py` refuses to decode anything that is not exactly those four fields in that order. Everything below is presentation only.

## Variants

Of the 3 variants named here, 1 is defined: `TEM TIÊU CHUẨN`, the default `LabelTemplate.name` in `packages/labels/service.py`. No caller passes a template of its own, so it is the only one that can be produced.

NOT YET ADOPTED (2): `TEM NHÃN`, `TEM ĐÓNG ĐỒ`. `LabelTemplate` takes a name and a field list, so the type supports them; neither is defined anywhere.

## Printed fields

Of the 6 fields named here, 5 render: `material`, `quantity`, `size`, `delivery_date`, `notes`.

`PO` does not render. `LabelData` carries both `order_code` and `customer_po_number`, and `LabelTemplateRenderer.LABELS` holds a Vietnamese label for each — but `LabelTemplate.visible_fields` lists neither, so the data is loaded and the label exists and neither reaches the page.

No drag/drop designer is introduced in R007.
