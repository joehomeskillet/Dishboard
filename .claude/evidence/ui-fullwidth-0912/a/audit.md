# MP-UI-FULLWIDTH-AUDIT Gruppe A — Prüftabelle

| Seite / Route / Variante | Bisherige Breitenbegrenzung | Korrektur | Geprüfte Viewports | Screenshotnachweis | Status |
|---|---|---|---|---|---|
| Bereiche & Öffnungszeiten / admin.operations_settings / normal | `layout_variant='narrow'` | `standard` | 390, 720, 1024, 1440, 1920, 2560 | bereiche-zeiten-normal-*.png | umgestellt |
| Screens / admin.screens / normal | — (bereits `standard`) | — | 390, 720, 1024, 1440, 1920, 2560 | screens-normal-*.png | bereits korrekt |
| Vorlagen / admin.vorlagen / normal | — (bereits `standard`) | — | 390, 720, 1024, 1440, 1920, 2560 | vorlagen-normal-*.png | bereits korrekt |
| Wochenvorlage / admin.screen_template_assignment / normal | `layout_variant='narrow'` | `standard` | 390, 720, 1024, 1440, 1920, 2560 | wochenvorlage-normal-*.png | umgestellt |
| Wochenvorlage / screen_template_unavailable / 503 | `.unavailable-container { max-width: 60rem }` | Regel entfernt | 390, 720, 1024, 1440, 1920, 2560 | wochenvorlage-unavailable-503-*.png | umgestellt |
| Wochenübersicht / admin.week_management / normal | Formularspalten `col-sm-5/col-sm-7` (lokale Feldbreite) | beibehalten | 390, 720, 1024, 1440, 1920, 2560 | wochen-normal-*.png | bereits korrekt |
| Wochenprüfung / admin.week_review_get / normal | Kartenraster `col-xl-6` (volle Zeile) | beibehalten | 390, 720, 1024, 1440, 1920, 2560 | wochenpruefung-normal-*.png | bereits korrekt |
| Menüs / admin.menu_collection / normal | Suchfeld `col-md-8 col-xl-6`, Kartenraster `col-md-6 col-xl-4` | beibehalten (lokale Felder/Raster) | 390, 720, 1024, 1440, 1920, 2560 | menues-normal-*.png | bereits korrekt |
| Bausteine / admin.components_get / normal | Filterraster `col-md-6 col-xl-4` | beibehalten (volle Zeile) | 390, 720, 1024, 1440, 1920, 2560 | komponenten-normal-*.png | bereits korrekt |
| Baustein-Editor / admin.component_detail / normal | `layout_variant='narrow'` | `standard` | 390, 720, 1024, 1440, 1920, 2560 | komponente-normal-*.png | umgestellt |
| Kochbücher / admin.cookbooks_list / normal | Suchfeld `col-lg-6` (lokale Feldbreite) | beibehalten | 390, 720, 1024, 1440, 1920, 2560 | kochbuecher-normal-*.png | bereits korrekt |
| Kochbuch neu / admin.cookbook_new / normal | — | — | 390, 720, 1024, 1440, 1920, 2560 | kochbuch-neu-normal-*.png | bereits korrekt |
| Kochbuch bearbeiten / admin.cookbook_edit / normal | — | — | 390, 720, 1024, 1440, 1920, 2560 | kochbuch-edit-normal-*.png | bereits korrekt |
| Cafeteria / admin.cafeteria / Referenz | workspace-Layout (Referenz) | nur verifiziert | 390, 720, 1024, 1440, 1920, 2560 | cafeteria-referenz-*.png | bereits korrekt |
| Patienten / admin.patienten / Referenz | workspace-Layout (Referenz) | nur verifiziert | 390, 720, 1024, 1440, 1920, 2560 | patienten-referenz-*.png | bereits korrekt |

## Gate-Ausgaben

```
test_ui_fullwidth_pages_a_browser.py: 2 passed
ruff check test_ui_fullwidth_pages_a_browser.py: All checks passed!
```

Vollgate (13 Testdateien): 123 passed, 18 failed (Fremdtests, siehe unten).

## Rote Fremdtests

- `test_admin_template_catalog_browser.py` (5×): fehlende Druckvorlagen-Fixture-Daten (`Winter & Festtage`, `Aktiver Herbst · Revision 2`) — fachlich, nicht Breitenbezug.
- `test_ui_reference_form_browser.py::test_validation_preserves_inputs_tokens_and_native_submit[*-js]` (2×): Fokus nach Validierungs-POST — Verhaltenstest, nicht Breitenbezug.

## Angepasste Begleittests (Breitenannahmen)

- `test_ui_output_hubs_browser.py`: `data-layout` Wochenvorlage `narrow` → `standard`
- `test_ui_reference_form_browser.py`: Containerbreite-Assertion auf volle Arbeitsbreite
- `test_component_catalog_browser.py`: Responsiv-Schwelle 1200 → 992 (CSS `@media max-width: 991.98px`)

Modell: composer-2.5
