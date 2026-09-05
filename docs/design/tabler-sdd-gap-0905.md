# Tabler-SDD Gap-Audit (2026-09-05)

Basis: SDD `docs/superpowers/tabler-sdd-user-2026-09-05.md` (verbindlich) gegen Code-Stand `a3a351a`
(Branch `docs/fable-sdd-audit-0905`). Live-Prod ist `e0d5470` ohne Tabler. Die Tabler-Erstintegration
aus dem Fable-Worktree `admin-tablet-fable-0905` (Stand `d3a9e9c`, dort noch ohne Tabler-Dateien) wurde
als `7e1dc73`/`e9088a3` übernommen; `6a27e3f` isolierte danach die Shell-Styles von den Legacy-Wochen.
Zielgerät laut Nutzer: Samsung Galaxy XCover (Compact, Android); exaktes Modell, OS- und Browserversion
sind offen und werden vor T11 dokumentiert. Nur Dokumentation, kein Produktcode geändert.

## 1. SDD-Vorschläge auf bestehende Struktur abgebildet

| SDD-Vorschlag (7.4 / 14 / 15) | Ist im Repository (`reference_scaffold/cafeteria/…`) | Entscheid |
|---|---|---|
| `static/vendor/tabler/<version>/…` | `static/vendor/tabler/tabler.min.css`, `static/vendor/tabler-icons/tabler-icons.svg`, Provenienz in `static/vendor/README.md` | Flacher Pfad bleibt; Version steht im README und wird durch Kopierskript reproduziert |
| `static/css/dishboard-admin.css` | `static/admin-tabler.css` (Marken-Tokens, Shell, Touch) | Datei bleibt, wird erweitert |
| `static/js/dishboard-admin.js`, `…-menu-editor.js` | `static/admin.js` (Dirty-Tracking, Zeilen, Fehlerfokus, Modus-Sync) | Eine Datei bleibt; kein Split |
| `templates/admin/base_tabler.html` | fehlt; `templates/base.html` lädt Tabler nur bedingt hinter `app.css` | Neu anlegen (WP-D) |
| `partials/sidebar.html`, `partials/page_header.html` | `admin/_workflow_sidebar.html`, Makro `page_header` in `admin/_macros.html` | Bestehende Dateien bleiben |
| `macros/forms.html`, `macros/status.html` | nur `icon`, `page_header`, `profile_tabs`, `pagination` in `_macros.html` | Feld-/Status-Makros in `_macros.html` ergänzen (WP-E) |
| `weekly_plan.html` | `admin/cafeteria.html`, `admin/patienten.html` (Endpoints `admin.cafeteria`, `admin.patienten`) | Namen bleiben |
| `menu_editor.html`, `components_list.html`, `component_editor.html` | `admin/menu_editor.html`, `admin/components.html`, `admin/component_editor.html` | Namen bleiben |
| Entitäten `menu_revision`, `publication`, `review` (Kap. 14) | `cafeteria.publication_revisions`, `row_version` je Item, Review-Token (`workflow_review.py`) | Kein neues SQL; vorhandene Modelle gelten |
| Preise «numerisch, zwei Dezimalstellen» (14.2) | Formular `internal_chf`/`external_chf`, Speicherung als Integer-Rappen (`test_cafeteria_menu_persists_rappen_from_chf`) | Rappen-Integer bleibt; nur Anzeige in CHF |
| Rollenmatrix Kap. 4 | Capabilities `draft.read/write`, `preview.read`, `publication.publish`, `csv.*` (`@require_capability`) | Rollen und Bedeutung unverändert |
| `ADMIN_UI_THEME` legacy/tabler (19.3) | kein solcher Schalter in `config.py` | Rückweg = Release `e0d5470` mit vollständigen Assets (WP-N) |

Routen (Blueprint `admin`, Prefix `/admin`, `workflow_routes.py`): `/`, `/cafeteria`, `/patienten`,
`/<family>/menu` GET+POST, `/<family>/menu/review` POST, `/<family>/header`, `/<family>/service`,
`/<family>/komponenten[/<public_id>[/archive|/unarchive]]`, `/<family>/copy`, `/<family>/preview`,
`/<family>/publish` POST; `/<family>/menues` (`menu_collection_routes.py`), `/<family>/wochen`
(`week_management_routes.py`), `/<family>/preview/print` (`print_routes.py`), `/import-preview`
(`routes.py`). Alle schreibenden Aktionen sind POST mit `_csrf` (scoped, `_validate_scoped_csrf`).

## 2. Evidenztabelle T01–T12

Status: `erfüllt` / `teilweise` / `offen`. Regressionsdateien liegen unter `reference_scaffold/tests/`.

| WP | Status | Ist-Dateien / Endpoint | Formular-Vertrag / Regressionsdatei | Abweichung zur SDD | Kleinste Korrektur |
|---|---|---|---|---|---|
| T01 | teilweise | `docs/design/admin-tabler-contract.md` (Markup-Vertrag) | – | Keine Zuordnung Datei → Änderung → Funktion → Test; Zielgerät unbestätigt | Dieses Dokument (Kap. 1, 2, 4) schliesst T01; Gerätedaten nachtragen |
| T02 | teilweise | `static/vendor/README.md` (core 1.5.0, icons 3.46.0, Tarball- und Datei-SHA256, Lizenzen) | `test_admin_tabler_browser.py` (genau ein `tabler.min.css`-Link) | Kein Paketmanager und keine Lockdatei im Repo; `tabler.min.js` nicht vendored; Reproduktion nur als Prosa | `tools/vendor_tabler.py` mit gepinnter URL+SHA256 als Lock-Ersatz; JS mitkopieren (WP-B) |
| T03 | teilweise | Flask `static`-Endpoint, `base.html:12-15` lädt CSS nur bei `admin-body` | `test_tabler_styles_do_not_load_on_public_or_login_pages` | Kein Build-Schritt, kein JS; Ladereihenfolge `app.css` vor Tabler statt Tabler → Admin-CSS | Kopierskript (WP-B) + Ladereihenfolge in `base_tabler.html` (WP-D) |
| T04 | offen | `_workflow_sidebar.html` (`navbar-expand-lg`, kein Toggler), `admin-tabler.css:33-46` (992 px), `cafeteria.html:12-36`/`patienten.html` mit eigener Legacy-Sidebar | `test_admin_shell_ui.py` (Sidebar/Main-Geometrie, Schwelle 1000 px), `test_legacy_week_sidebar_keeps_content_beside_it` | Kein `base_tabler.html`; Umschaltpunkt 992 statt 1200; unter dem Punkt horizontale Leiste statt Klapp-Navigation mit Button «Menü»; Wochen-Übersichten nutzen die Partial nicht | WP-D |
| T05 | teilweise | `admin-tabler.css` (Tokens `--tblr-*` aus `--sh-*`, 44 px, Fokusring), `_macros.html` | `test_admin_templates_use_no_hardcoded_hex`, `test_css_rgba_colors_outside_root_use_design_tokens` | 44 px statt 48 px; keine Feld-/Check-/Status-Makros; keine Referenzseite mit Feldfehlern | WP-E (Makros) + 48 px in WP-D |
| T06 | offen | `cafeteria.html` (165 Z.), `patienten.html` (190 Z.): `admin-week-shell`, `status-pill`, `.btn primary`, `data-sticky` | POST `/header` (`row_version`), `/service`, `/publish` (exakte Keys), `/copy`; `test_admin_overview_forms.py`, `test_admin_week_routes.py`, `test_admin_workflow_routes.py::test_publish_*`, `test_rendered_ui.py::test_admin_overview_*`, `test_admin_patient_overview_has_no_cost_vocabulary` | Kein Tabler-Markup, keine Tageskarten `card`, keine Publikations-Modal-Zusammenfassung (nur `data-confirm`) | WP-J |
| T07 | offen | `menu_editor.html:36-68`: Hidden `week, day, meal, option, row_version`; Felder `title, description, note, internal_chf, external_chf` | `test_menu_post_error_rerenders_editor_with_values`, `test_menu_editor_prefills_saved_item_and_masters`, `test_menu_editor_patient_has_no_cost_fields`, `test_patient_menu_rejects_price_fields_without_write` | Legacy-Markup (`admin-dish`, `label`+`input` ohne `form-control`); Prüfpanel nicht neben Grunddaten ab 1200 px | WP-G |
| T08 | offen | `menu_editor.html:70-181`: `component_public_id/component_text`, `allergen_mode/allergen_code/allergen_presence`, `origin_mode/origin_ingredient/origin_country_code`, `label_mode/label_code`; Review-Form `component_version`; `admin.js` (`data-add-row`, `formdata`, Modus-Sync) | `test_admin_review_checkboxes_rehydrate_canonical_checked_status`, `test_review_token_is_single_use_and_server_resolved`, `test_admin_workflow_review_db.py`, `test_admin_shell_ui.py` | Keine Akkordeons, kein Auto-Öffnen bei Fehler; Herkunft als Freitext-ISO-Code (SDD 12.3: Länderauswahl) | WP-H; Länderauswahl als `select.form-select` mit gleichem `name` |
| T09 | offen | `components.html` (136 Z., `details`-Formular), `component_editor.html` (119 Z.); Endpoints `komponenten*` | `test_component_create_update_archive_unarchive_exact_forms`, `test_component_detail_uses_public_id_and_masks_unknown`, `test_admin_components_list_marks_archived_and_usage`, `test_component_catalog_browser.py` | Keine Tabelle ≥1200 px / Karten darunter; kein Tabler-Formular; Filter «nur Cafeteria», «nur verwendete» in SDD 11.2, im Repo nicht nachgewiesen (Folgeauftrag) | WP-I |
| T10 | teilweise | migriert: `menu_collection.html`, `week_management.html` (Tabler-Klassen, Makros); offen: `copy.html`, `import_preview.html`; `preview.html` ohne `admin-body`, eigene `admin-preview.css` | `test_menu_collection*.py`, `test_week_management*.py`, `test_admin_copy_ui.py`, `test_admin_csv_preview_ui.py`, `test_admin_draft_preview.py` | Migrierte Seiten erben noch `base.html` mit `app.css`; Kopieren und CSV-Import Legacy | WP-F, WP-K; Vorschau bleibt eigene Fläche (Entscheid) |
| T11 | teilweise | `test_admin_tabler_browser.py` (768, 800, 1024, 1280, 390; 44 px), Screenshots `design/screenshots/admin-tabler/2026-09-05/` | – | Breiten 360, 820, 1199, 1200 fehlen; 48 px nicht geprüft; TAB-04/05/06 fehlen; kein Nachweis auf echtem XCover | WP-M; Gerätedaten vom Nutzer |
| T12 | offen | kein `ADMIN_UI_THEME`; Live `e0d5470` | `test_tabler_styles_do_not_load_on_public_or_login_pages` | Kein Laufzeit-Umschalter | WP-N: Rückweg über Release-Tag, im CHANGELOG dokumentieren |

## 3. Verbindliche Vorgaben für alle Folge-WPs

- Alle Admin-Seiten (`admin/*.html` mit `admin-body`, ausser `preview.html`) erben künftig von
  `templates/admin/base_tabler.html`. Blöcke: `title`, `page_header`, `content`, `page_styles`, `page_scripts`.
- `base_tabler.html` lädt `static/tokens.css` (Token-Block aus `app.css:1-107`, ausgelagert), dann
  `vendor/tabler/tabler.min.css`, dann `admin-tabler.css`; danach `vendor/tabler/tabler.min.js` und
  `admin.js` je mit `defer`. Migrierte Seiten laden `app.css` nicht mehr. `base.html` bleibt für
  Public, Signage, Login und `preview.html` unverändert; `test_tabler_styles_do_not_load_on_public_or_login_pages` bleibt grün.
- Sidebar: `navbar-expand-xl`, ab 1200 px fest links; darunter `button.navbar-toggler` mit sichtbarem
  Text «Menü», `data-bs-toggle="collapse"`, `data-bs-target="#sidebar-menu"`, `aria-expanded`.
  Alle 992-px-Regeln in `admin-tabler.css` werden auf 1200/1199.98 gesetzt.
- Touch: `.btn`, `.form-control`, `.form-select`, `.nav-link`, `.page-link`, `.form-check`, klickbare
  Tabellen-/Listenzeilen mindestens 48 px hoch; Testschwellen von 44 auf 48 anheben
  (`test_admin_tabler_browser.py`, `test_admin_shell_ui.py:96-113`).
- Prüfbreiten: 360, 768, 820, 1024, 1199, 1200, 1280. Kein horizontales Scrollen der Seite.
- Unverändert: Flask-Endpoints, Hidden-IDs (`week, day, meal, option, row_version, component_version`),
  `_csrf`, Feldnamen, Capability-Bedeutung, Rappen-Integer, Public liest nur `published_snapshot`.

## 4. Backend-Prüfung Kapitel 13 (nur mit Evidenz)

- Revisionen: `cafeteria.publication_revisions` mit `revision_number` (`workflow_publication.py:35-60`);
  `publish` flasht die Revisions-ID (`test_publish_prg_flashes_revision_in_live_region`). Erfüllt.
- Prüfung an Version gebunden: Review-Token aus `item_row_version` und `component_row_version`, einmalig
  und serverseitig aufgelöst (`workflow_review.py:289-341`, `test_review_token_is_single_use_and_server_resolved`). Erfüllt.
- Publizierter Stand bleibt: Teil- und Vollspeicherungen erhalten `workflow_state`; `schema.sql:512-522`
  verhindert Herabstufen einer publizierten Woche mit aktiver Revision; `test_admin_workflow_db.py:330-381`
  bearbeitet den Entwurf und prüft, dass `active_snapshot` die erste Publikation bleibt. Kein Gap.
- Öffentliche Ausgabe: `public/routes.py` liefert nur `published_snapshot`; Query-Parameter werden
  abgelehnt (`test_public_endpoints_reject_every_query_parameter`). Erfüllt. Admin-Vorschau zeigt
  authentifiziert den letzten gespeicherten Stand (`test_preview_is_last_saved_without_publication_fallback`); gültig.
- Verifizierte Lücken (Backend-Audit 2026-09-05, getrenntes Backend-WP, kein UI-Scope):
  1. Die Prüfung hängt an `menu_item.row_version` plus Komponenten-Hash, nicht an einer Wochenrevision.
     Header- und Service-Speicherungen (`workflow_partial_store.py:226`, `:270`) erhöhen nur ihre Zeilen
     und entwerten die Item-Prüfung nicht; `publish` (`workflow.py:529`) prüft die eingereichte
     Wochenversion und danach (`:537`) nur die Item-Prüfung. Ein gültiger Header-/Service-Edit ist damit
     ohne neue Prüfung der geänderten Einheit publizierbar (Verstoss gegen SDD 13.2 und 20.2).
  2. `review_component` (`workflow_review.py:307-359`) speichert den geprüften Status, schreibt aber
     kein dauerhaftes Audit-Ereignis mit Prüfer und geprüfter Revision, obwohl `audit_events` existiert
     (SDD 17 «Audit-Ereignisse enthalten Benutzer, Zeitpunkt, Objekt, Aktion und Revision»).
  Kein literales Feld «aktuell geprüfte Version»; die Semantik der bestehenden Tokens bleibt bis WP-O
  unverändert. Templates zeigen weiterhin nur den serverseitig gelieferten Status.

## 5. Geordnete Micro-WPs (Dateibesitz, je ein Worktree)

| WP | Deckt | Besitzt ausschliesslich | Gate |
|---|---|---|---|
| WP-A | T01 | `docs/design/tabler-sdd-gap-0905.md` | erledigt mit diesem Commit |
| WP-B | T02, T03 | `tools/vendor_tabler.py`, `static/vendor/README.md`, `static/vendor/tabler/tabler.min.js` | Skript idempotent, Hashes im README, `test_admin_tabler_browser.py` |
| WP-C | 7.5 | `static/tokens.css` (neu), `static/app.css` (nur Token-Block entfernen), `templates/base.html` (Link ergänzen) | `test_rendered_ui.py`, `test_ui_contracts.py`, Public-Screens unverändert |
| WP-D | T04, T05-Teil | `templates/admin/base_tabler.html` (neu), `templates/admin/_workflow_sidebar.html`, `static/admin-tabler.css` | Toggler bei 1199 sichtbar, Sidebar bei 1200 fest; 48 px; TAB-04 |
| WP-E | T05 | `templates/admin/_macros.html`, `docs/design/admin-tabler-contract.md` | Makros `field`, `check`, `status_badge`; Vertrag auf 48 px und 1200 px angepasst |
| WP-F | T10-Teil | `templates/admin/menu_collection.html`, `templates/admin/week_management.html` | `extends "admin/base_tabler.html"`; `test_menu_collection*`, `test_week_management*` |
| WP-G | T07 | `templates/admin/menu_editor.html` (Zeilen 1-68, Aktionsleiste) | Editor-Tests aus T07; Feldnamen und Hidden-IDs diffgleich |
| WP-H | T08 | `templates/admin/menu_editor.html` (Zeilen 69-181), `static/admin.js` | Akkordeon öffnet bei Fehler (TAB-05), Zeilen mit eindeutigen IDs (TAB-06), Review-Tests |
| WP-I | T09 | `templates/admin/components.html`, `templates/admin/component_editor.html` | Tabelle ≥1200 / Karten <1200, Katalog-Tests, `test_admin_shell_ui.py` |
| WP-J | T06 | `templates/admin/cafeteria.html`, `templates/admin/patienten.html` | Tageskarten, Publikations-Modal mit Zusammenfassung, Overview-/Publish-Tests; Legacy-Sidebar-Test ersetzen |
| WP-K | T10-Rest | `templates/admin/copy.html`, `templates/admin/import_preview.html` | `test_admin_copy_ui.py`, `test_admin_csv_preview_ui.py`, `test_admin_csv_import.py` |
| WP-L | 7.5 Abschluss | `templates/base.html` (Admin-Bedingung entfernen), `static/admin-tabler.css` (Legacy-Neutralisierung entfernen) | Kein Tabler auf Public; kein `app.css` im Admin |
| WP-M | T11 | `reference_scaffold/tests/test_admin_tabler_browser.py`, `design/screenshots/admin-tabler/<datum>/` | Matrix 360–1280, TAB-01…08; echtes XCover-Protokoll mit Modell/Browser |
| WP-N | T12 | `CHANGELOG.md`, `docs/design/admin-tabler-contract.md` (Abschnitt Rückweg) | Rückweg = Release `e0d5470`; TAB-09 als Deploy-Probe |
| WP-O | SDD 13.2, 17, 20.2 (Backend, 19.2) | `workflow_partial_store.py`, `workflow.py`, `workflow_review.py`, `database/migrations/0013_*.sql` falls nötig, `tests/test_admin_workflow_db.py`, `tests/test_admin_workflow_review_db.py` | Header-/Service-Änderung macht die Woche prüfpflichtig oder `publish` prüft deren Version; Review schreibt `audit_events` mit Prüfer und Revision; alte Publikation bleibt (Test 330-381 grün) |

Reihenfolge: A → B → C → D → E → F → G → H → I → J → K → L → M → N. WP-G/H, WP-I und WP-K sind nach
WP-F untereinander parallelisierbar (disjunkte Dateien). WP-J zuletzt vor Cleanup, weil es die
Legacy-Wochen-Shell ablöst, die `6a27e3f` gerade abgesichert hat. WP-O läuft unabhängig von der
UI-Reihe in einem eigenen Worktree und ist vor der Produktionsfreigabe (SDD 19.2) zu schliessen;
kein UI-WP ändert Prüf- oder Publikationsregeln stillschweigend.

## 6. Nicht-Ziele dieses Audits

Keine Änderung an Public-, Signage-, Druck- oder Login-Templates; keine SQL-Migration aus UI-WPs (nur
WP-O darf eine anlegen); keine neuen Rollen; keine Rezept-/Nährwertlogik; kein Laufzeit-Theme-Schalter; keine Bewertung der Komponenten-Filter
aus SDD 11.2 ohne Repo-Nachweis.
