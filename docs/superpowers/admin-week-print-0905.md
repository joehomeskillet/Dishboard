# Saved-week print

Purpose: print the selected saved admin week using the supplied Südhang cafeteria
sheet as the visual reference. Primary action: print or save as PDF.

The A4 portrait sheet preserves the reference photo, three-column day/menu grid,
blue headings, logo and footer. Existing brand blue and dedicated reference
colour tokens reproduce the PDF drawing colours. Complete Carlito Regular and
Bold, already bundled locally with Apache Guacamole, provide Calibri-compatible
metrics. Their original SIL OFL 1.1 license is bundled beside the fonts.
Patient sheets use a patient heading and one section per meal, with no prices.

GET `/admin/<family>/preview/print?week=YYYY-MM-DD` requires `preview.read`,
rejects profile overrides and invalid/non-Monday weeks, uses only the scoped
saved draft, returns 404 if missing, 503 for invalid active location, and no-store.
No database mutation or publication occurs. Labels, origins, allergen presence
and unchecked/missing declarations remain explicit. Empty slots stay empty.
Prices come from saved menus; shared prices appear in the footer, differing
prices beside the relevant menu. No unverified origin or inclusion claim is added.

Normal cafeteria content fits one A4 page. Long content may add pages; no hidden
overflow, line clamp or truncation. Browser printing waits for fonts and images.
Tests cover auth, scope, saved-source isolation, metadata, closed/empty slots,
dynamic prices and real Chromium PDF geometry/page count/content retention.
Screen controls retain 44px touch targets on 768×1024, 800×1280, 1024×768 and
1280×800 tablets in addition to phone width. Printed A4 geometry is unchanged.

Reference: https://www.suedhang.ch/wp-content/uploads/2025/01/Aktuelles_Wochenangebot_Cafeteria_Klinik_Suedhang.pdf
Retrieved 2026-09-05; SHA-256
`b9c0a608410f3db6e732ffbf8392dc063b3a253c0bdeee55523de0e1a0c6108e`.
Header and logo JPEGs are embedded image assets extracted from this reference.
No reference menu text, prices or blanket Swiss-origin statement is copied.

Typography limit: the source PDF embeds Calibri subsets with `fsType=8`, but
their glyph data omits characters needed by new labels (including uppercase A).
Browser validation exposed blank glyphs. Those subsets are not shipped. No
complete Calibri font was available in local font directories or project/host
assets; Carlito preserves line metrics but is not a pixel-identical typeface.

Asset checksums:

| Asset | SHA-256 |
| --- | --- |
| weekly-print-header.jpg | b7161679fbfe3a9a31d751962f54b67f6e4244899c0d546d63b6f61e061ff426 |
| weekly-print-logo.jpg | 5a12cfef7ab902476d8de24f7d18809ae93c8bf48292aee9a6e0591c41428a93 |
| weekly-print-carlito.woff | 550cd5fa32077c2db8c5ccd50edecd5f6fc344e4fd919601b76e57828bc18548 |
| weekly-print-carlito-bold.woff | 6292892e0f09dd80ccc510280831d1ecffe512b95558be1699ca5d4154889657 |

Carlito source: existing Apache Guacamole distribution,
`webapps/ROOT/fonts/carlito/`; files copied unchanged. Copyright 2010–2013,
tyPoland Lukasz Dziedzic. License: `static/fonts/Carlito-LICENSE.txt`.

## Verification, 2026-09-05

Isolated PostgreSQL plus real Chromium:
`test_admin_week_print.py`, `test_admin_draft_preview.py`,
`test_admin_preview_ui.py`: **16 passed in 18.06s**, `GATE_EXIT=0`.
Ruff passed; scoped mypy reported no issues; `node --check week-print.js` passed.

Committed fixture proofs: `design/screenshots/weekly-print/2026-09-05/`.
The PDFs are actual Chromium output; PNGs were rendered from those PDFs.

| Fixture | Pages | Verified text |
| --- | --- | --- |
| cafeteria-normal.pdf | 1 | All 10 menus and missing-allergen notices |
| patienten-normal.pdf | 2 | All 28 menus and missing-allergen notices; both meals |
| cafeteria-dense.pdf | 2 | All 10 unique end markers, including Friday vegetarian |

Every PDF page measures 594.95996 × 841.91998 pt (Chromium A4 rounding).
No data clipping, row-height truncation or hidden content is used. Repeated table
headings remain visible on overflow pages. PDF text extraction confirms complete
new-label/date glyphs after rejecting the incomplete Calibri subsets.
The normal cafeteria and second patient page were visually inspected after
matching the reference's measured 12pt body, 15pt headings, 10pt notes and 17pt date.
OCR first-pass service was unavailable in this wave after actual provider HTTP429;
this is not an OCR pass. Root performs independent diff review and re-gating.
