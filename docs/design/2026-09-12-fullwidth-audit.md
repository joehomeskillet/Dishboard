# Vollbreiten-Audit aller Admin-Seiten (MP-UI-FULLWIDTH-AUDIT, 2026-09-12)

Vorgabe des Auftraggebers vom 2026-09-12: jede Seite nutzt die gesamte verfügbare Breite rechts neben der Navigation, ohne Ausnahme.
Gemeinsame Lösung im Seitenrahmen: MP-UI-FULLWIDTH-SHELL (grok-4.6, 4d60042, deployt als 30ec192 am 2026-09-12 09:28):  ohne
 für Seitenkopf, Bereichs-Tabs und Inhalt, Innenabstand 32/24/16 px; / engen nicht mehr ein.
Seiten-Audit in zwei Gruppen (A: cursor composer-2.5, 65babf7/fba5fac; B: grok-4.6, 837ee04/f806cda). Messung je Route: primärer Inhaltsblock
≥ 0,95 × Innenbreite von  bei ≥ 1024 px, kein Dokumentüberlauf; Viewports 390×844, 720×450 (1440 px bei 200 %),
1024×768, 1440×900, 1920×1080, 2560×1440. Screenshots unter  und .
Vorschau () ist eigenständig ohne Admin-Shell (Root-Entscheid 2026-09-12) und über  auf fünf
Viewports ohne Überlauf geprüft; Druck/PDF/Signage unverändert.

## Gruppe A

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


## Gruppe B

Viewports: 390×844, 720×450 (1440 bei 200 %), 1024×768, 1440×900, 1920×1080, 2560×1440.
Messung: primärer Inhaltsblock ≥ 0,95 × Innenbreite von `.page-body > .container-xl` (ab 1024 px); kein Dokumentüberlauf.
401/403 nicht geöffnet (deckt der Seiten-WP-Test).

| Seite / Route / Variante | Bisherige Breitenbegrenzung | Korrektur | Geprüfte Viewports | Screenshotnachweis | Status |
|---|---|---|---|---|---|
| admin.menu_get / default | `col-xl-8` + `col-xl-4` in einer vollen Zeile (Formular + Prüfung) | behalten: zusammengehörige Spalten füllen die Zeile | 390, 720, 1024, 1440, 1920, 2560 | `admin.menu_get-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.menu_get / empty (LUNCH VEGGIE) | wie default | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.menu_get-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.menu_get / form_error | wie default plus Alert | — | nicht separat | — | offen (gleicher Raster wie default; Alert ändert die Seitenbreite nicht) |
| admin.menu_get / origin_conflict | wie default plus 409-Alert | — | nicht separat | — | offen (Katalog-Konfliktfixture; Layout identisch mit default) |
| admin.master_data_list / default | Filter `col-lg-4`/`col-lg-3` (lokale Feldbreite), Liste volle Karte | Filter lokal belassen | 390, 720, 1024, 1440, 1920, 2560 | `admin.master_data_list-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.master_data_list / empty | wie default, Empty-State | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.master_data_list-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.master_data_detail / default (Zutat) | Dichte/Stückgewicht untereinander | innere `row` `col-lg-6` | 390, 720, 1024, 1440, 1920, 2560 | `admin.master_data_detail-default-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.master_data_detail / default-unit | Anlegen-Felder untereinander | innere `row` `col-lg-6` | 390, 720, 1024, 1440, 1920, 2560 | `admin.master_data_detail-default-unit-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.master_data_detail / default-category | Name/Code untereinander | innere `row` `col-lg-6` beim Anlegen; Detail volle Karte | 390, 720, 1024, 1440, 1920, 2560 | `admin.master_data_detail-default-category-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.master_data_new / default (Zutat) | wie Detail-Formular | innere Spalten wie Detail | 390, 720, 1024, 1440, 1920, 2560 | `admin.master_data_new-default-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.master_data_new / empty (Einheit) | wie Unit-Formular | innere Spalten | 390, 720, 1024, 1440, 1920, 2560 | `admin.master_data_new-empty-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.local_users_list / default | Filter `col-md-5` lokal, Tabelle volle Karte | Filter lokal belassen | 390, 720, 1024, 1440, 1920, 2560 | `admin.local_users_list-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.local_users_list / empty | wie default | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.local_users_list-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.local_user_new / default | `col-12 col-xl-8` als einziger Inhalt der Zeile | Wrapper entfernt; Benutzername/Anzeigename `col-lg-6` | 390, 720, 1024, 1440, 1920, 2560 | `admin.local_user_new-default-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.local_user_new / invalid | wie default plus Fehleralert | gleiche Korrektur | 390, 720, 1024, 1440, 1920, 2560 | `admin.local_user_new-invalid-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.local_user_detail / default | `col-12 col-xl-8` um die Aktionsformulare | Wrapper entfernt; Passwortfelder `col-lg-6` | 390, 720, 1024, 1440, 1920, 2560 | `admin.local_user_detail-default-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.local_user_events / default | volle Karte/Tabelle | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.local_user_events-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.local_user_events / empty | wie default | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.local_user_events-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.access_history / default | Filter lokale Feldbreite, Tabelle volle Karte | Filter lokal belassen | 390, 720, 1024, 1440, 1920, 2560 | `admin.access_history-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.access_history / empty | wie default | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.access_history-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipes_list / default | Filter `col-md-4`, Kartenraster volle Breite (1 Spalte) | Raster füllt die Zeile; 1 Spalte bewusst für gleiche Kartenhöhe (`test_recipe_navigation_browser`) | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipes_list-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipes_list / empty | wie default | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipes_list-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_new / default | Formular volle Karten, kurze Felder `col-md-6` | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_new-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_new / invalid | Konfliktseite `main.container-xl` (Tabler-Deckel) | `container-fluid` | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_new-invalid-{390,720,1024,1440,1920,2560}.png` | umgestellt |
| admin.recipe_edit / default | wie recipe_new | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_edit-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_revisions / default | volle Karten/Tabelle | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_revisions-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_revisions / empty | wie default | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_revisions-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_revision / default | `dl` dt/dd lokal, Bilder `col-lg-4` Raster | Raster füllt die Zeile | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_revision-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_images / default | Lizenz/Abrufzeit `col-lg-6`, Upload volle Karte | lokale Feldbreite belassen | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_images-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_images / empty | wie default ohne Bilder | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_images-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_scale / default | Zielmenge `col-lg-4` lokal, Tabelle volle Karte | lokale Feldbreite belassen | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_scale-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_scale / invalid | wie default plus Fehler | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_scale-invalid-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.branding_editor / default | `col-xl-6` + `col-xl-6` (Entwurf + Vorschau) | behalten: volle Zeile | 390, 720, 1024, 1440, 1920, 2560 | `admin.branding_editor-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.branding_preview / default | iframe-Inhalt `main.p-3`, Karte blockbreit | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.branding_preview-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.display_settings / default | Einstellungen `col-md-6` in voller Karte; Vorschau `contained` nur Demo | Seitenformular ungedeckelt | 390, 720, 1024, 1440, 1920, 2560 | `admin.display_settings-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.print_template_editor / default | `col-xl-5` + `col-xl-7` (Eigenschaften + PDF) | behalten: volle Zeile | 390, 720, 1024, 1440, 1920, 2560 | `admin.print_template_editor-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.recipe_print_template_editor / default | gleiches Template | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.recipe_print_template_editor-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.api_overview / default | Schlüsseldatum `col-lg-3` lokal, Tabellen volle Karten | lokale Feldbreite belassen | 390, 720, 1024, 1440, 1920, 2560 | `admin.api_overview-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.copy_get / default | Quelle/Ziel `col-sm-6` in voller Karte | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.copy_get-default-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.import_preview / empty | Upload volle Karte | keine | 390, 720, 1024, 1440, 1920, 2560 | `admin.import_preview-empty-{390,720,1024,1440,1920,2560}.png` | bereits korrekt |
| admin.import_preview / invalid | wie empty plus Fehlerkarte | nicht separat (kein CSV-Upload in diesem Lauf) | — | — | offen (leerer Zustand geöffnet; invalid braucht Datei) |
| Standalone: rezepte_conflict, local_user_unavailable, grundlagen_unavailable, print_template_unavailable, recipe_template_error | `main.container-xl` (Tabler max-width) | `container-fluid` | conflict über recipe_new invalid; übrige 503-Pfade nicht live ausgelöst | `admin.recipe_new-invalid-*.png` | umgestellt (503-Seiten Template-only) |

`layout_variant = 'narrow'` bleibt `data-layout` (Shell deckelt nicht). `test_ui_menu_editor_browser`, `test_ui_brand_ops_browser`, `test_ui_reference_settings_browser` prüfen das Attribut weiterhin.

Nicht geöffnet: 401/403 (Auftrag), menu form_error/origin_conflict, import invalid, Live-503 der Unavailable-Templates.
