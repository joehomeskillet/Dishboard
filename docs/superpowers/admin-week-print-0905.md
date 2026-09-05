# Saved-week PDF

The selected saved admin week opens as a real server-generated PDF using
`fpdf2==2.8.8`. It replaces the previous HTML/browser-print implementation.
The browser PDF viewer provides printing and downloading without a browser
pagination or CSS dependency. Tabler governs the admin UI, not the PDF.

## Contract

GET `/admin/<family>/preview/print?week=YYYY-MM-DD` requires `preview.read`,
rejects profile overrides and invalid/non-Monday weeks, reads only the scoped
saved draft, returns 404 if missing and 503 for an invalid active location.
The response is `application/pdf`, `Content-Disposition: inline` with a dated
filename, and `Cache-Control: no-store`. No database mutation, live fallback,
publication or unpersisted form values are involved.

- Cafeteria: exactly one A4 portrait page, Monday–Friday, two menu columns.
- Patients: exactly one A4 landscape page, Monday–Sunday, four columns:
  lunch menu 1, lunch vegetarian, dinner menu 1, dinner vegetarian (28 menus).
- Titles, components, descriptions, notes, labels, origins, allergen names and
  presence are retained. Missing declarations and pending review stay explicit.
  Closed services retain their notice; missing slots remain explicitly empty.
- Patients contain no generated prices or cafeteria heading. Cafeteria shared
  prices appear in the footer; differing prices appear with each saved menu.
  There is no fixed reference price or unverified origin/inclusion claim.

## Layout and fit policy

The renderer measures the exact wrapped lines before drawing. Each day's row
height covers its tallest cell. There are no automatic page breaks, clipping,
line limits or text truncation. Every accepted output is one complete page.
Patient text uses 9pt or 8.5pt; the dense patient layout joins components and
declarations into a continuous paragraph after the bold title. Cafeteria body
uses 12/11/10pt and details 10/9/8.5pt, choosing the largest fitting pair.
The footer note is 10pt for cafeteria and 8.5pt for patients.

The realistic fixture contains all 38 current menu titles/components and the
complete proposed recipe notes from `allergen-proposals-0905.md`. Those notes
are unreviewed proposals, not confirmed allergen declarations. The fixture
does not write them to any database. Both complete profiles fit one page.

Unbounded text beyond the physical capacity of one readable A4 page returns
HTTP 422 with a request to shorten descriptions/notes, preserve required
declarations, save, and reopen. Unsupported font glyphs also return an
actionable 422 instead of silently disappearing. This is intentionally not
an overflow-to-a-second-page mode.

## Reference and assets

Reference: https://www.suedhang.ch/wp-content/uploads/2025/01/Aktuelles_Wochenangebot_Cafeteria_Klinik_Suedhang.pdf
Retrieved 2026-09-05; SHA-256
`b9c0a608410f3db6e732ffbf8392dc063b3a253c0bdeee55523de0e1a0c6108e`.

Original header/photo and logo JPEGs are extracted from that supplied document.
The cafeteria table starts at x=21pt/y=203pt, width approximately 553pt, with
a 31pt blue header. Footer starts at y=756pt. Row heights adapt to the saved
declarations. Colour constants are named print tokens sampled from the PDF.

The source Calibri subsets omit glyphs required by the application. The complete
Carlito Regular/Bold fonts supply metric-compatible typography; this is not a
claim of pixel-identical Calibri. The bundled WOFF files came from the existing
Apache Guacamole distribution, `webapps/ROOT/fonts/carlito/`. TTF files were
converted from those WOFFs with FontTools (remove the WOFF flavor, save SFNT),
with no glyph-subsetting. Original SIL OFL 1.1 license remains at
`reference_scaffold/cafeteria/static/fonts/Carlito-LICENSE.txt`.

| Asset | SHA-256 |
| --- | --- |
| weekly-print-header.jpg | b7161679fbfe3a9a31d751962f54b67f6e4244899c0d546d63b6f61e061ff426 |
| weekly-print-logo.jpg | 5a12cfef7ab902476d8de24f7d18809ae93c8bf48292aee9a6e0591c41428a93 |
| weekly-print-carlito.woff | 550cd5fa32077c2db8c5ccd50edecd5f6fc344e4fd919601b76e57828bc18548 |
| weekly-print-carlito-bold.woff | 6292892e0f09dd80ccc510280831d1ecffe512b95558be1699ca5d4154889657 |

## Evidence

`design/screenshots/weekly-print/2026-09-05/` contains four new actual fpdf2
PDFs (`*-normal-server.pdf`, `*-notes-server.pdf`) and PNG renders of both
note-dense PDFs made with `pdftoppm`. All four PDFs have exactly one page.
The previous Chromium two-page patient/dense artifacts are superseded and removed.

Pure PDF tests use pypdf for page count, text retention and minimum font size;
Poppler word bounding boxes verify page bounds and pairwise non-overlap. Tests
also cover all 28 unique patient menu sentinels, declarations, empty slots,
variable prices and explicit overflow/glyph errors.

Initial integrated gate on the server-PDF implementation:

```text
.......................                                                  [100%]
23 passed in 17.61s
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/admin-print-0905/reference_scaffold
```

After the final footer geometry and glyph guard, pure PDF gate:

```text
..........                                                               [100%]
10 passed in 2.99s
```

Ruff: `All checks passed!`
Scoped mypy: `Success: no issues found in 2 source files`.
Final route/PDF gate, including before/after draft equality on successful PDFs
and HTTP 422:

```text
..............                                                           [100%]
14 passed in 6.70s
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/admin-print-0905/reference_scaffold
```

The lane report records the OCR result. Full application
suite, production deployment, live PDF retrieval and cross-vendor review are
orchestrator gates; they are not claimed by this work package.
