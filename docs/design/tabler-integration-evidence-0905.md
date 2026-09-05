# Tabler-Integration: Nachweise vom 5. September 2026

Dokumentbasis: Integrationscommit `746832214a006009069e1abfa7304afe0653d592`. Massstab ist die [verbindliche SDD](../superpowers/tabler-sdd-user-2026-09-05.md), Kapitel 19–20. **Tabler ist noch nicht produktiv ausgerollt.** Die folgenden Nachweise betreffen lokale Integration und isolierte Testdatenbanken; sie sind keine vollständige Produktiv- oder Geräteabnahme.

## T01–T12

Testdateien liegen unter [`reference_scaffold/tests`](../../reference_scaffold/tests/), Admin-Templates unter [`templates/admin`](../../reference_scaffold/cafeteria/templates/admin/).

| WP | Aktueller Stand | Konkreter Nachweis / Restpunkt |
|---|---|---|
| T01 | Struktur erfasst; Gerät offen | [Markup-Vertrag](admin-tabler-contract.md) und [ursprünglicher Gap-Audit](tabler-sdd-gap-0905.md). Exaktes XCover-Modell, Android-/Browserversion und echte Bildschirmtastatur fehlen weiterhin. |
| T02 | Gepinnt und lokal vorhanden | [`tabler.lock.json`](../../reference_scaffold/cafeteria/static/vendor/tabler.lock.json): Core **1.5.0**, Icons **3.46.0**, Quellen-/Dateihashes; lokale CSS-, JS-, SVG- und Lizenzdateien. [`vendor_tabler.py`](../../tools/vendor_tabler.py) bietet Reproduktion und Offline-Prüfung. |
| T03 | Lokal integriert; Paketabnahme offen | [`base_tabler.html`](../../reference_scaffold/cafeteria/templates/admin/base_tabler.html) lädt lokale Assets. `test_week_overviews_extend_tabler_base_and_load_assets` und `test_tabler_styles_do_not_load_on_public_or_login_pages`. Validator-Ergänzung `9669fb3` prüft Lockdateien sowie Definitionen in `tokens.css` und `app.css`; ihre sieben fokussierten Tests ersetzen keinen sauberen Paketlauf. |
| T04 | Implementiert und im Browser geprüft | Eigene Tabler-Basis, gemeinsame Sidebar, mobile Klappnavigation, Umschaltung bei 1200 px. `test_admin_shell_ui.py`, `test_admin_tabler_browser.py`; Screenshots unten. |
| T05 | Implementiert und im Browser geprüft | [`_macros.html`](../../reference_scaffold/cafeteria/templates/admin/_macros.html), `tokens.css`, `admin-tabler.css`: Feldfehler, Statusdarstellung, Fokus und 48-px-Ziele. `test_shared_macros_expose_errors_labels_and_touch_targets`, Editor-Matrix und Kompaktansicht. |
| T06 | Implementiert; native Abläufe geprüft | `cafeteria.html`/`patienten.html`: zehn beziehungsweise 28 Menüslots, Tageskarten, Wochenprüfung und Publikationsdialog. `test_admin_week_tabler_browser.py`, `test_admin_overview_forms.py`: Header-/Service-POST führt per 303 zur gewählten vollständigen Woche; Dialog sendet den bestehenden exakten Vertrag. |
| T07 | Implementiert; Speichern/Rücksprung geprüft | `menu_editor.html`, `test_admin_menu_editor_browser.py`, `test_admin_menu_save_back_browser.py`, `test_admin_form_contracts.py`. Grunddaten, CHF-Anzeige/Rappen-Vertrag, Patient ohne Preise; `return_to=week` ist ein streng begrenzter POST-Querywert, Fehler bleiben im Editor. |
| T08 | Implementiert; dynamische Formulare geprüft | `test_dynamic_rows_have_unique_ids_labeled_controls_and_ordered_payload`, `test_field_error_opens_only_affected_accordion_and_summary_links_to_field`, `test_modes_and_accordion_state_survive_save_and_reload`. Länderauswahl behält ISO-Feldwerte; Auto-Labels erfordern bekannte Komponenten (`82b2191`). |
| T09 | Tabler/CRUD geprüft; Zusatzfilter offen | `components.html`/`component_editor.html`, `test_component_catalog_browser.py`, `test_component_catalog_routes.py`, `test_admin_form_contracts.py`: responsive Liste, Verwendung, Archivierung und Feldfehler mit erhaltenen Mehrfachwerten. Zusätzliche Filter «nur verwendete»/expliziter Gültigkeitsscope aus SDD 11.2 sind nicht belegt. |
| T10 | Alle vorgesehenen Admin-Seiten migriert | Wochenübersichten, Menüeditor, Komponentenliste/-editor, Menüs, Wochenverwaltung, Kopieren, CSV-Vorschau und Wochenprüfung erben direkt von `admin/base_tabler.html`. `preview.html` bleibt bewusst eine eigene Vorschau mit `base.html`. `test_menu_collection*`, `test_week_management*`, `test_admin_copy_ui.py`, `test_admin_csv_preview_ui.py`. |
| T11 | Browserabdeckung vorhanden; Hardwareabnahme offen | Matrix 360/768/820/1024/1199/1200/1280 in Wochen-/Editortests; Navigation, Fehlerfokus, dynamische Zeilen und Aktionsleiste geprüft. Eine simulierte Viewport-/Fokusprüfung ersetzt TAB-08 mit realer Android-Bildschirmtastatur und Gerätewechsel nicht. |
| T12 | Offen | Vollständige saubere Paketprüfung, v16-kompatibler Rückweg, Produktionsumschaltung und anschliessender Live-Nachweis stehen aus. Kein Laufzeit-Theme-Schalter wird behauptet. |

## Unabhängige Root-Gates

Vom Orchestrator gemeldete, getrennte Läufe; keine Summierung über überlappende Tests. Gemeinsamer Aufruf: `worker-test_root-gate.sh <WT> -q tests/<Datei> … -p no:cacheprovider -rs --tb=short` auf isoliertem PostgreSQL 16.

| Stand | Ergebnis | Exakte Testdateien |
|---|---|---|
| `8add9ce` | **77 passed in 142.28s** | `test_admin_week_tabler_browser.py`, `test_admin_shell_ui.py`, `test_admin_ux_browser.py`, `test_week_review_browser.py` |
| `7468322` | **65 passed in 100.41s** | `test_admin_menu_save_back_browser.py`, `test_admin_menu_editor_browser.py`, `test_admin_form_contracts.py`, `test_admin_overview_forms.py`, `test_component_catalog_browser.py` |
| `82b2191` | **34 passed in 17.99s** | `test_workflow_review_receipts_db.py`, `test_workflow_review_migration_db.py`, `test_admin_workflow_review_db.py`, `test_week_review_routes.py`, `test_component_assignment_db.py` |

Der jüngste 65er-Lauf ersetzt den vorher gemeldeten positiven 63er-Formular-/Overview-Zwischenstand. Ruff über 44 geänderte Python-Dateien ist grün. Mypy über acht Laufzeitdateien meldet weiterhin drei auf der Basis reproduzierte Diagnosen: `rendering.py:32` (`int(object)`), `workflow_routes.py:211` (Listen-Rückgabetyp) und `:359` (`list(object)`). Kein vollständig grünes Typgate wird behauptet.

## Fable-Review und dauerhafte Belege

[Fable-Review v16](fable-review-v16-0905.md) bewertet die Prüf-/Audit-Kernlogik im bestehenden App-Vertrauensmodell als korrekt. H1 (fehlende Basis im isolierten Backend-Branch) und M1 (fehlender Link) sind im Integrationsstand statisch aufgelöst. Der dort noch offene Browsernachweis ist durch QA-Commit `29a1e64da508720a07626248bf7ffacf60b8baeb` und den 77er-Root-Lauf nachgereicht: [`test_week_review_browser.py`](../../reference_scaffold/tests/test_week_review_browser.py) verwendet echten Flask-Loader, Datenbank und Browser für beide Profile, explizite Bestätigung, veraltete Tokens sowie vollständig geschlossene Wochen. Der historische Reviewtext bleibt als zeitlicher Befund erhalten.

Versionierte Screenshot-Beispiele, jeweils lokale Testbelege:

- Basisnavigation bei 360 px: [Cafeteria-Menüs](../../design/screenshots/admin-tabler/sdd-base-2026-09-05/cafeteria-menues-360x800.png); Breakpointvergleich [1199 px](../../design/screenshots/admin-tabler/sdd-base-2026-09-05/cafeteria-menues-1199x800.png) / [1200 px](../../design/screenshots/admin-tabler/sdd-base-2026-09-05/cafeteria-menues-1200x800.png).
- Kopieren/CSV: [Patienten kopieren](../../design/screenshots/admin-tabler/sdd-copy-csv-2026-09-05/copy-patienten-360.png), [CSV-Feldfehler](../../design/screenshots/admin-tabler/sdd-copy-csv-2026-09-05/after-invalid-360.png).
- Wochenprüfung aus `29a1e64`: [Patienten offen](../../design/screenshots/admin-tabler/week-review-2026-09-05/patienten-360-open.png), [Patienten mit Beleg](../../design/screenshots/admin-tabler/week-review-2026-09-05/patienten-360-receipt.png), [geschlossene Cafeteria nur lesen](../../design/screenshots/admin-tabler/week-review-2026-09-05/cafeteria-360-read-only-closed.png).

## Vor Produktionsfreigabe

Sauberes Paket, vollständige Pflichtgates und kompatiblen Rückweg fertig prüfen; danach kontrolliert alte Anwendung stoppen, Migration v16 transaktional ausführen und v16 starten. **Ein v15-Binary ist nach der Migration kein sicherer Backend-Rollback.** Vorhandene Publikationssnapshotbytes und Benutzernotizen bleiben erhalten; historische `checked`-Flags erhalten keine erfundenen Prüfbelege. Root ergänzt hier nach dem Deploy Commit/Artefakt, Zeitpunkt, Health- und authentifizierten Live-Nachweis. Reale XCover-/Tablet- und Tastaturabnahme bleibt separat offen.
