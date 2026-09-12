# MP-UI-FULLWIDTH-AUDIT Gruppe B — Prüftabelle

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
