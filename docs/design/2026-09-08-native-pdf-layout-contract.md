# TPL-002: Native weekly PDF layout contract

Status: adopted compatibility contract, 2026-09-08. Implements the reader slice of
`2026-09-05-screens-vorlagen-verwaltung.md` §5. Renderer and editor are subsequent
work packages; this slice does not complete TPL-002 or enable configurable output.

Use existing Tabler controls and fpdf2. No arbitrary canvas, coordinates, template
paths, HTML, CSS, expressions, URLs or dependency additions. Configurations bind
existing data; they never store menu values, declarations, prices or photos.

## Revision shape

The existing eight appearance properties remain unchanged. Only explicit new
layout revisions add `layout`. Historical revisions receive no defaults or new
keys. Cafeteria retains portrait A4; patients retain landscape A4 without prices.

```json
{
  "version": 1,
  "grid": "days_rows",
  "header": ["logo", "title", "date_range", "week_number", "header_note"],
  "footer": ["service_notes", "footer_note"],
  "menu_fields": ["title", "components", "image", "origins", "allergens", "labels", "prices"],
  "photo": "none",
  "alignment": "left",
  "day_label_width": "standard",
  "row_spacing": "standard",
  "legend_position": "bottom"
}
```

Patient `menu_fields` contains precisely the same bindings except `prices`.
Header/footer/menu arrays are exact permutations: each mandatory binding once,
no omissions, duplicates or extensions. Empty source fields naturally contribute
no content. `header_note` and `footer_note` use the existing validated text fields.
The legend remains mandatory when menu data requires it.

| Property | Allowed values |
| --- | --- |
| version | Integer 1; booleans and floating-point values rejected |
| grid | days_rows, days_columns |
| photo | none, small, medium |
| alignment | left, center |
| day_label_width | compact, standard, wide |
| row_spacing | compact, standard, roomy |
| legend_position | top, bottom |

All object keys and list lengths are bounded before traversal. Image binding uses
existing local assets only in the future renderer. Grid changes preserve all
actual days, services and menu slots, including configured cafeteria weekends.
The renderer must map geometry choices to bounded constants, maintain 8.5 pt
minimum, all declarations and both cafeteria amounts, and reject actual-week
overflow before emitting a PDF. Preview, activation and download share rendering.

## Compatibility and staged delivery

Document versions 1, 2 and 3 are readable. Versions 1/2 may contain only legacy
eight-key configurations. Version 3 can mix legacy and layout revisions. A new
layout save changes the envelope to 3, without changing old revisions. Archive,
copy, restore and later legacy saves never downgrade 3. Legacy v1 archive fields
continue to normalize only in memory until a successful write commits v2.

No SQL migration: existing JSON setting key and CAS/actor/row-lock contract stay.
Strict old readers cannot read v3. Before exposing layout writes, deploy and gate
a compatible fallback reader. Existing editor forms remain unchanged in this
slice. Valid new layouts may be saved through the store for compatibility tests,
but preview, download and activation explicitly reject them until the renderer
supports their complete contract. They must never silently use legacy geometry.

Acceptance includes strict profile validation at read/save/render boundaries,
immutable historical structures, original default PDF SHA-256 bytes, v3 lifecycle
with rollback on unsupported activation, and unchanged existing archive/CAS tests.
