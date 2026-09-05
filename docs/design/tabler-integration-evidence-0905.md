# Tabler-Integration: Nachweise vom 5. September 2026

Releasebasis: `1a3004af42592d686947148df53b549350183bf3`. Massstab ist die [verbindliche SDD](../superpowers/tabler-sdd-user-2026-09-05.md), Kapitel 19–20. **Tabler ist seit 5. September 2026, 22:07 Uhr Schweizer Zeit produktiv; der Container läuft gesund.** Der vollständige authentifizierte Live-Nachweis besteht mit 42 Seiten und 847 Prüfungen, ohne Fehler oder nicht verfügbare Prüfungen. Lokale Browserprüfungen und dieser Go-live ersetzen keine vollständige Geräteabnahme.

## T01–T12

Testdateien liegen unter [`reference_scaffold/tests`](../../reference_scaffold/tests/), Admin-Templates unter [`templates/admin`](../../reference_scaffold/cafeteria/templates/admin/).

| WP | Aktueller Stand | Konkreter Nachweis / Restpunkt |
|---|---|---|
| T01 | Struktur erfasst; Gerät offen | [Markup-Vertrag](admin-tabler-contract.md) und [ursprünglicher Gap-Audit](tabler-sdd-gap-0905.md). Exaktes XCover-Modell, Android-/Browserversion und echte Bildschirmtastatur fehlen weiterhin. |
| T02 | Gepinnt und lokal vorhanden | [`tabler.lock.json`](../../reference_scaffold/cafeteria/static/vendor/tabler.lock.json): Core **1.5.0**, Icons **3.46.0**, Quellen-/Dateihashes; lokale CSS-, JS-, SVG- und Lizenzdateien. [`vendor_tabler.py`](../../tools/vendor_tabler.py) bietet Reproduktion und Offline-Prüfung. |
| T03 | Integriert; saubere Paketabnahme bestanden | [`base_tabler.html`](../../reference_scaffold/cafeteria/templates/admin/base_tabler.html) lädt lokale Assets. `test_week_overviews_extend_tabler_base_and_load_assets` und `test_tabler_styles_do_not_load_on_public_or_login_pages`. Der vollständige Validatorlauf aus `/tmp/dishboard-tabler-final` endet mit Exit 0; Vendorprüfung aller fünf Artefakte, Schema mit 13 Migrationsdateien sowie CSS- und Screenshotprüfungen sind bestanden. |
| T04 | Implementiert und im Browser geprüft | Eigene Tabler-Basis, gemeinsame Sidebar, mobile Klappnavigation, Umschaltung bei 1200 px. `test_admin_shell_ui.py`, `test_admin_tabler_browser.py`; Screenshots unten. |
| T05 | Implementiert und im Browser geprüft | [`_macros.html`](../../reference_scaffold/cafeteria/templates/admin/_macros.html), `tokens.css`, `admin-tabler.css`: Feldfehler, Statusdarstellung, Fokus und 48-px-Ziele. `test_shared_macros_expose_errors_labels_and_touch_targets`, Editor-Matrix und Kompaktansicht. |
| T06 | Implementiert; native Abläufe geprüft | `cafeteria.html`/`patienten.html`: zehn beziehungsweise 28 Menüslots, Tageskarten, Wochenprüfung und Publikationsdialog. `test_admin_week_tabler_browser.py`, `test_admin_overview_forms.py`: Header-/Service-POST führt per 303 zur gewählten vollständigen Woche; Dialog sendet den bestehenden exakten Vertrag. |
| T07 | Implementiert; Speichern/Rücksprung geprüft | `menu_editor.html`, `test_admin_menu_editor_browser.py`, `test_admin_menu_save_back_browser.py`, `test_admin_form_contracts.py`. Grunddaten, CHF-Anzeige/Rappen-Vertrag, Patient ohne Preise; `return_to=week` ist ein streng begrenzter POST-Querywert, Fehler bleiben im Editor. |
| T08 | Implementiert; dynamische Formulare geprüft | `test_dynamic_rows_have_unique_ids_labeled_controls_and_ordered_payload`, `test_field_error_opens_only_affected_accordion_and_summary_links_to_field`, `test_modes_and_accordion_state_survive_save_and_reload`. Länderauswahl behält ISO-Feldwerte; Auto-Labels erfordern bekannte Komponenten (`82b2191`). |
| T09 | Tabler/CRUD geprüft; Zusatzfilter offen | `components.html`/`component_editor.html`, `test_component_catalog_browser.py`, `test_component_catalog_routes.py`, `test_admin_form_contracts.py`: responsive Liste, Verwendung, Archivierung und Feldfehler mit erhaltenen Mehrfachwerten. Zusätzliche Filter «nur verwendete»/expliziter Gültigkeitsscope aus SDD 11.2 sind nicht belegt. |
| T10 | Alle vorgesehenen Admin-Seiten migriert | Wochenübersichten, Menüeditor, Komponentenliste/-editor, Menüs, Wochenverwaltung, Kopieren, CSV-Vorschau und Wochenprüfung erben direkt von `admin/base_tabler.html`. `preview.html` bleibt bewusst eine eigene Vorschau mit `base.html`. `test_menu_collection*`, `test_week_management*`, `test_admin_copy_ui.py`, `test_admin_csv_preview_ui.py`. |
| T11 | Browserabdeckung vorhanden; Hardwareabnahme offen | Matrix 360/768/820/1024/1199/1200/1280 in Wochen-/Editortests; Navigation, Fehlerfokus, dynamische Zeilen und Aktionsleiste geprüft. Der nach Dialogabbruch nur teilweise sichtbare Wochenfokus ist mit `14f4084` korrigiert; zehn Browserprüfungen bestehen. Eine simulierte Viewport-/Fokusprüfung ersetzt TAB-08 mit realer Android-Bildschirmtastatur und Rotation nicht. |
| T12 | Paketprüfung, Go-live und Live-Nachweis bestanden | Release `1a3004a`, gesund seit `2026-09-05T20:07:00Z`; Backup und Migration 15→16 geprüft. Ein v16-kompatibles Legacy-Image ist separat vorbereitet und durch Root geprüft. Authentifizierter Live-Lauf: 42 Seiten, 847 Prüfungen bestanden. PDF-/Bild-/Kartenprüfung und acht öffentliche HTTP-Prüfungen bestanden. Kein Laufzeit-Theme-Schalter vorhanden. |

## Unabhängige Root-Gates

Vom Orchestrator gemeldete, getrennte Läufe; keine Summierung über überlappende Tests. Gemeinsamer Aufruf: `worker-test_root-gate.sh <WT> -q tests/<Datei> … -p no:cacheprovider -rs --tb=short` auf isoliertem PostgreSQL 16.

| Stand | Ergebnis | Exakte Testdateien |
|---|---|---|
| `8add9ce` | **77 passed in 142.28s** | `test_admin_week_tabler_browser.py`, `test_admin_shell_ui.py`, `test_admin_ux_browser.py`, `test_week_review_browser.py` |
| `7468322` | **65 passed in 100.41s** | `test_admin_menu_save_back_browser.py`, `test_admin_menu_editor_browser.py`, `test_admin_form_contracts.py`, `test_admin_overview_forms.py`, `test_component_catalog_browser.py` |
| `82b2191` | **34 passed in 17.99s** | `test_workflow_review_receipts_db.py`, `test_workflow_review_migration_db.py`, `test_admin_workflow_review_db.py`, `test_week_review_routes.py`, `test_component_assignment_db.py` |

Der 65er-Lauf ersetzt den vorher gemeldeten positiven 63er-Formular-/Overview-Zwischenstand. Die abschliessende saubere Paketprüfung auf `/tmp/dishboard-tabler-final` ist mit **Exit 0** abgeschlossen: **2912 Tests bestanden**, alle Paketchecks einschliesslich Vendor, Schema, CSS und Screenshots bestanden. Das Abschlussprotokoll enthält keine einzelne Skip-Liste. Die 15 externen Drill-Skips sind nur für frühere identische Gesamtläufe belegt; sie werden weder als endgültige Skip-Zahl dieses Abschlusslaufs noch als ausgeführte Testabdeckung ausgegeben.

Der abschliessende Ruff-Lauf über **56 geänderte Python-Dateien** meldet `All checks passed!`. Die drei auf der Basis reproduzierten Mypy-Diagnosen bleiben unverändert: `rendering.py:32` (`int(object)`), `workflow_routes.py:211` (Listen-Rückgabetyp) und `:359` (`list(object)`) im damaligen Typprüfstand. Kein vollständig grünes Typgate wird behauptet. OCR war mit tatsächlich beobachteten 429-/Timeout-Fehlern nicht verfügbar; es liegt kein positiver OCR-Abschluss vor.

## Fable-Review und dauerhafte Belege

[Fable-Review v16](fable-review-v16-0905.md) bewertet die Prüf-/Audit-Kernlogik im bestehenden App-Vertrauensmodell als korrekt. H1 (fehlende Basis im isolierten Backend-Branch) und M1 (fehlender Link) sind im Integrationsstand statisch aufgelöst. Der dort noch offene Browsernachweis ist durch QA-Commit `29a1e64da508720a07626248bf7ffacf60b8baeb` und den 77er-Root-Lauf nachgereicht: [`test_week_review_browser.py`](../../reference_scaffold/tests/test_week_review_browser.py) verwendet echten Flask-Loader, Datenbank und Browser für beide Profile, explizite Bestätigung, veraltete Tokens sowie vollständig geschlossene Wochen. Der historische Reviewtext bleibt als zeitlicher Befund erhalten.

Versionierte Screenshot-Beispiele, jeweils lokale Testbelege:

- Basisnavigation bei 360 px: [Cafeteria-Menüs](../../design/screenshots/admin-tabler/sdd-base-2026-09-05/cafeteria-menues-360x800.png); Breakpointvergleich [1199 px](../../design/screenshots/admin-tabler/sdd-base-2026-09-05/cafeteria-menues-1199x800.png) / [1200 px](../../design/screenshots/admin-tabler/sdd-base-2026-09-05/cafeteria-menues-1200x800.png).
- Kopieren/CSV: [Patienten kopieren](../../design/screenshots/admin-tabler/sdd-copy-csv-2026-09-05/copy-patienten-360.png), [CSV-Feldfehler](../../design/screenshots/admin-tabler/sdd-copy-csv-2026-09-05/after-invalid-360.png).
- Wochenprüfung aus `29a1e64`: [Patienten offen](../../design/screenshots/admin-tabler/week-review-2026-09-05/patienten-360-open.png), [Patienten mit Beleg](../../design/screenshots/admin-tabler/week-review-2026-09-05/patienten-360-receipt.png), [geschlossene Cafeteria nur lesen](../../design/screenshots/admin-tabler/week-review-2026-09-05/cafeteria-360-read-only-closed.png).

## Produktionsstand und Rückweg

Die folgenden Freigabedaten wurden vom Orchestrator unabhängig geprüft:

| Nachweis | Ergebnis |
|---|---|
| Release | `1a3004af42592d686947148df53b549350183bf3` |
| Produktiv-Image | `sha256:5bac8d3f67f07b9f7f6c3049732b0a7d9966217c38df29b55e024b632f74916b` |
| Paketgleichheit | 642 versionierte Quelldateien stimmen mit dem Release-Artefakt überein. |
| Start/Health | Seit `2026-09-05T20:07:00Z` (22:07 Uhr Schweiz) läuft der Produktivcontainer; Health bestanden. |
| Backup | `cafeteria-20260905T200553Z.ALIEcP.dump`; SHA-256 `17c7a221c58d25869e3993c556976599993bcfaef9d28d7c22307e4e4f419073`; Hashprüfung und `pg_restore`-Inhaltsverzeichnis bestanden. |
| Migration | Version 15→16 auf PostgreSQL 18.6 bestanden; Readiness `true`. |
| Bestandserhalt | Acht vor/nach der Migration verglichene Bestandshashes sind identisch; Bestand: 38 Menüs, 37 Komponenten, zwei Publikationen. |
| Authentifizierter Live-Nachweis | **42 Seiten, 847 Prüfungen bestanden; null Fehler, null nicht verfügbare Prüfungen**, Status `passed` in `/nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/proof/tabler-live-1a3004a/admin-corrected/proof.json`. Einschliesslich Login, CSP, lokaler Assets, Navigation, CSRF und Patienten-Preisfreiheit. Prüfwerkzeugkorrektur `26ae0d5` (Quellcommit `ff8880a`), unabhängig durch Root geprüft: `62 passed in 22.58s`, `GATE_EXIT=0`, Ruff bestanden. Das Produktiv-Image blieb unverändert. Der anfängliche Stand 841/847 war ein nachgewiesener Regex-Fehlalarm: `chf` traf innerhalb von «Milchfreiheit»; kein Preis-Leak festgestellt. |
| PDFs, Bilder und Karten | Live HTTP 200 für beide PDFs, jeweils eine Seite (Cafeteria A4 hoch mit zehn Menütiteln, Patienten A4 quer mit 28 Menütiteln). Zehn beziehungsweise 28 unterschiedliche Menübilder geladen. Kartenhöhenspanne jeweils 1 px bei 360/390/768/800/1024/1280 px Breite. Ergebnis `passed` in `/nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/proof/tabler-live-1a3004a/pdf/proof.json`. |
| Öffentliche Routen | HTTP 200 für `/cafeteria/heute/`, `/cafeteria/wochenangebot/`, `/patienten/heute/`, `/patienten/wochenplan/`, `/signage/cafeteria/tag`, `/signage/cafeteria/woche`, `/signage/patienten/tag` und `/signage/patienten/woche`. Root hat zusätzlich Screenshots des Desktop-Editors und der mobilen Wochenübersicht visuell geprüft. |

Der vorbereitete Rückweg verwendet **v16-kompatiblen Backendcode mit Legacy-Oberfläche**: Branch `fix/legacy-ui-v16-return-0905`, Commit `9af55da`, Image `sha256:5b5af79ca5b3332e4ca62621bfa26474183c2b690005ac96da490650bbdd041e`. Root hat dafür vier Browserfälle in 11,90 Sekunden erfolgreich geprüft. Es gibt **keinen `ADMIN_UI_THEME`-Schalter**. Ein v15-Binary ist nach der Migration kein sicherer Backend-Rollback; ein Rückwechsel der Oberfläche ersetzt keine Datenbank-Restore-Entscheidung.

Offen bleiben die Zusatzfilter aus T09 sowie die Abnahme auf dem tatsächlichen Samsung XCover mit dokumentiertem Modell, Android- und Browserversion, Bildschirmtastatur und Rotation. Historische `checked`-Flags erhalten keine erfundenen Prüfbelege.
