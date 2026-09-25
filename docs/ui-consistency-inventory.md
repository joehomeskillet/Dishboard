# UI-Konsistenzinventar — Migrationsliste P4/P5

Statische Quellenzählung aller Templates; Laufzeitzweige und dynamische Labels
brauchen Browserprüfung. Öffentliche/Signage-Einträge erteilen keine Migrationsfreigabe.
Nullzeilen bleiben erhalten, damit jede Quelle erfasst ist.

Kategorien: literale Buttons, lange Labels (>2 Wörter oder >18 Zeichen), alte Labels,
abweichende Icons, lokale Listen/Tabellen, lokale Filter/Suchformulare.
`list_typography_overrides` zählt font-size, font-weight und color in Listen-/Tabellenregeln
von admin-*.css, cookbook-admin.css und recipe-*.css, einschliesslich zentralem admin-tabler.css.
Diese Quellenzählung unterscheidet bewusst nicht zwischen wirksamen und überstimmten Regeln.

Aktualisieren: `rtk python3 tools/ui_consistency_inventory.py --update-baseline`.
Bestehende Obergrenzen dürfen nur sinken; neue Dateien starten bei null.

## P5a-Fixup: ganzzahlige Zeilenhöhen (2026-09-26)

`/admin/{cafeteria,patienten}/komponenten`, Admin mit Daten, 390×844 und
1440×1100: gemeinsame Listenrollen (M66/R47) erhalten 20-px-Zeilenhöhen.
Mobile Titel-/Statuslabel-Zeilen werden ebenfalls ganzzahlig; Aktionsunterkante
nach nativem Scrollen 844,09375 → 844 px. Desktop-Katalogzeile bleibt 56,5 px.
Gate: `1 failed, 52 passed in 306.30s (0:05:06)`; Shell, Master-Tokens und
Katalog bestehen. Globaler Typografienachweis offen: Messtest sucht bei Benutzer
die bereits durch `list_row()` ersetzte `.admin-users-row`. Keine Baselineänderung.
OCR ungeprüft: Provider HTTP 402. Screenshots/Messmatrix: `/tmp/pytest-of-root/pytest-2310/`.

| Quelle | literal_buttons | long_labels | legacy_labels | wrong_icons | local_lists | local_filters | list_typography_overrides |
|---|---:|---:|---:|---:|---:|---:|---:|
| _brand_logo.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| _food_symbols.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| _menu_image.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| _menu_metadata.html | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| admin/_area_tabs.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_country_select.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_course_editor.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_course_line.html | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_course_recipe_search.html | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| admin/_local_user_forms.html | 0 | 0 | 1 | 0 | 0 | 0 | 0 |
| admin/_macros.html | 1 | 0 | 0 | 0 | 2 | 0 | 0 |
| admin/_recipe_document.html | 2 | 1 | 0 | 0 | 5 | 0 | 0 |
| admin/_recipe_template_selection.html | 10 | 6 | 0 | 0 | 1 | 3 | 0 |
| admin/_rezepte_fields.html | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_service_courses.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_week_controls.html | 6 | 2 | 0 | 0 | 2 | 0 | 0 |
| admin/_week_menu_card.html | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| admin/_week_service.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_week_settings.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_workflow_sidebar.html | 1 | 0 | 0 | 0 | 1 | 0 | 0 |
| admin/access_history.html | 3 | 1 | 0 | 1 | 1 | 1 | 0 |
| admin/api.html | 4 | 1 | 0 | 0 | 3 | 0 | 0 |
| admin/base_tabler.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/bestellung.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/bestellung_korb.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/branding_editor.html | 3 | 2 | 1 | 0 | 1 | 0 | 0 |
| admin/branding_preview.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/cafeteria.html | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/component_editor.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/components.html | 0 | 0 | 2 | 0 | 2 | 1 | 0 |
| admin/copy.html | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| admin/display_settings.html | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| admin/einkaufsliste.html | 0 | 0 | 0 | 0 | 1 | 2 | 0 |
| admin/einkaufslisten.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/gerichtvorlage_einplanen.html | 5 | 2 | 0 | 0 | 0 | 0 | 0 |
| admin/gerichtvorlagen.html | 7 | 2 | 0 | 0 | 1 | 0 | 0 |
| admin/grundlagen.html | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| admin/grundlagen_food.html | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| admin/grundlagen_location_conflict.html | 1 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/grundlagen_unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/grundlagen_unit.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/grundlagen_vocabulary.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/import_preview.html | 2 | 2 | 0 | 0 | 1 | 0 | 0 |
| admin/kalkulation.html | 0 | 0 | 0 | 0 | 1 | 0 | 0 |
| admin/kochbuch_editor.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/kochbuecher.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/kuechenkalender.html | 3 | 0 | 0 | 0 | 2 | 1 | 0 |
| admin/kuechenkalender_anlass.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/lager.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/local_user_create.html | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/local_user_editor.html | 5 | 4 | 0 | 1 | 0 | 0 | 0 |
| admin/local_user_events.html | 2 | 1 | 0 | 0 | 1 | 0 | 0 |
| admin/local_user_unavailable.html | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/local_users.html | 2 | 0 | 1 | 0 | 1 | 1 | 0 |
| admin/menu_collection.html | 5 | 0 | 0 | 2 | 1 | 0 | 0 |
| admin/menu_editor.html | 15 | 4 | 0 | 1 | 3 | 1 | 0 |
| admin/operations.html | 1 | 0 | 0 | 0 | 4 | 0 | 0 |
| admin/patienten.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/preview.html | 3 | 3 | 0 | 0 | 1 | 0 | 0 |
| admin/print_template_editor.html | 19 | 11 | 0 | 0 | 1 | 1 | 0 |
| admin/print_template_unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/recipe_template_error.html | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/rezepte.html | 4 | 2 | 0 | 0 | 1 | 1 | 0 |
| admin/rezepte_ansicht.html | 4 | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/rezepte_conflict.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/rezepte_editor.html | 9 | 2 | 0 | 0 | 0 | 0 | 0 |
| admin/rezepte_images.html | 2 | 1 | 0 | 0 | 1 | 0 | 0 |
| admin/rezepte_import.html | 4 | 3 | 0 | 0 | 2 | 0 | 0 |
| admin/rezepte_revision.html | 3 | 0 | 0 | 0 | 1 | 0 | 0 |
| admin/rezepte_revisionen.html | 2 | 1 | 0 | 0 | 3 | 0 | 0 |
| admin/rezepte_scale.html | 2 | 0 | 0 | 0 | 1 | 0 | 0 |
| admin/screen_template_assignment.html | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/screen_template_unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/screens.html | 1 | 0 | 1 | 0 | 0 | 0 | 0 |
| admin/vorlagen.html | 17 | 11 | 0 | 0 | 2 | 1 | 0 |
| admin/week_management.html | 0 | 0 | 0 | 0 | 0 | 1 | 0 |
| admin/week_review.html | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| api/docs.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| auth/error.html | 1 | 1 | 0 | 0 | 0 | 0 | 0 |
| auth/local_login.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| base.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| public/base_public.html | 1 | 1 | 0 | 0 | 1 | 0 | 0 |
| public/cafeteria_today.html | 2 | 1 | 1 | 0 | 1 | 0 | 0 |
| public/cafeteria_week.html | 2 | 0 | 1 | 0 | 0 | 0 | 0 |
| public/legend.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| public/patient_today.html | 2 | 1 | 1 | 0 | 0 | 0 | 0 |
| public/patient_week.html | 2 | 0 | 1 | 0 | 0 | 0 | 0 |
| public/print_cafeteria_week.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| public/print_patient_week.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| public/unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/base_signage.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/cafeteria_closed.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/cafeteria_day.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/cafeteria_week.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/patient_day.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/patient_week.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| ui/_semantic.html | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-bestellung.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-branding.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-components.css | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| static/admin-einkaufslisten.css | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| static/admin-gerichtvorlagen.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-grundlagen.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-kalkulation.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-kitchen-calendar.css | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| static/admin-lager.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-menu-collection.css | 0 | 0 | 0 | 0 | 0 | 0 | 1 |
| static/admin-menu-editor.css | 0 | 0 | 0 | 0 | 0 | 0 | 2 |
| static/admin-nav.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-preview.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-screens.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-settings-benutzer.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-settings-bereiche.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-settings-darstellung.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-settings-import.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-settings-schnittstellen.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-tabler.css | 0 | 0 | 0 | 0 | 0 | 0 | 21 |
| static/admin-vorlagen-druck.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-vorschau-bildschirme.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-week-tabler.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-wochenplan-kern.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-wochenuebersicht.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/cookbook-admin.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/recipe-admin.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/recipe-document.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | 167 | 74 | 11 | 5 | 52 | 17 | 28 |
