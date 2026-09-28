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

## Release 18 R1: Rezeptaktionen und Regressionen (2026-09-27)

### Fortsetzung 2026-09-28: API-Schlüssel und Listenmessung

`/admin/api`, Admin, aktive/abgelaufene/widerrufene Schlüssel, 390 und 1440 px,
JS/No-JS: Widerrufsauslöser und Überlauf nutzen `icon_summary` aus dem gemeinsamen
Renderer. Das native `summary` enthält keinen verschachtelten Button. Der
Bestätigungsschritt bleibt beschriftet; Details im geöffneten Überlauf sowie
Formular-/Abschnittslabels bleiben lesbar. Formattribute, CSRF, Feldnamen und
Rechte bleiben unverändert. Paket `6a656cd7`/`45d12e76`, unabhängiges Review ACCEPT.
Eigener Zweitlauf: `206 passed in 34.96s` (Semantik und Schlüsselpolicy) sowie
`4 passed in 16.04s` (reale API-Browserfälle); beide `GATE_EXIT=0`.
JUnit: `/var/tmp/dishboard-icon-api-root-0928.xml` und
`/var/tmp/dishboard-icon-api-root-browser-0928.xml`. Stabile Screenshotbelege unter
`/var/tmp/icon-api-0928-browser-stable/`, Mobilbestätigung auch unabhängig gesichtet.
OCR aktuell HTTP 402, kein OCR-PASS. Bestehende deutsche API-Spezialtexte sind
weiter eine Lokalisierungslücke. Noch kein Deploy dieser Änderungen behauptet.

Listenfamilienmessung `75453eee`: 41 Seiten/82 Blöcke, Kopfvergleich nur für
vorhandene Köpfe; Links mit gleicher Typografie gelten nicht mehr als abweichend.
Hintergrund/Höhe bleiben Messwerte. REPORT-Modus darf keine neue Abweichung in
die Baseline übernehmen. Eigener Zweitlauf `4 passed in 18.46s`, `GATE_EXIT=0`.
Natives Details-Summary im API-Überlauf wird vom alten Leer-Menü-Zähler noch
fälschlich als leer bewertet; kein fehlender Produktzugang. Weitere konkrete
Restpunkte und UI-01 bis UI-28: `docs/design/2026-09-26-icon-first-audit.md`.

Listenhülle `e169a69d`: `/admin/bestellung` und `/admin/vorlagen`, Admin, 390/1440 px.
Gemeinsame Außenkante und 1-px-Zwischentrenner; Bildschirmvorlagen richten Aktionen
rechts aus. Der Bestell-Override hatte jede umschlossene Zeile als letzte Zeile
behandelt. Verschachtelte Karten bleiben rahmenlos; der Kalender behält die
Heute-Markierung. Native Formulare und Fachlogik sind unverändert.
Unabhängig: `test_list_shell_browser.py`: `1 passed in 15.62s` und
`test_admin_shared_patterns_browser.py`: `55 passed in 76.10s (0:01:16)`,
jeweils `GATE_EXIT=0`. Eigene Screenshots:
`/var/tmp/dishboard-list-shell-root-0928/`. Keine Behauptung appweiter
Gestaltungsabnahme: Vorlagenstatus und Anlegen-Disclosures sind noch zu verdichten.

Wochenwarnungen `6ef6fb40`: `/admin/cafeteria` und `/admin/patienten`, Mittag/Abend,
fehlende/gemischte/vollständige Angaben, 390/1440 px. Wiederholte Warnplaketten
werden lesbare Sekundärtexte; Kopfsumme, Eintragslinks und Veröffentlichungssperre
bleiben unverändert. Fehlend bleibt ausdrücklich ungleich allergenfrei, gespeicherte
Angaben bleiben ungeprüft. Unabhängige Matrix: `12 passed in 39.21s`; bestehende
Prüf-/Formularfälle a04–a07: `10 passed, 27 deselected in 32.39s`, beide
`GATE_EXIT=0`. JUnit `/var/tmp/dishboard-week-warnings-root-0928.xml` und
`/var/tmp/dishboard-week-safety-root-0928.xml`. Vorher/Nachher visuell geprüft.
Bereits vorher sichtbar und separat zu beheben: überlappende lange Gangnamen
bei Patienten sowie abgeschnittene Bildfehlermeldungen bei Cafeteria.

`/admin/rezepte`, Editor, Ansicht, Revisionen und Rezeptdruckvorlagen: Admin,
Nur-Lesen und archiviert, JS/No-JS, 320/390/768/1024/1440/1920/2560 px sowie
echter 200-%-Browserzoom. R44/M64: Symbolaktionen mit zugänglichen Namen;
Dichteprüfung zusätzlich mit echtem grobem Zeiger (44 px) und feinem Zeiger
(36 px). Formularwerte, Feldfokus, Warnungen und unveränderliche Stände bleiben
geprüft. DB-freie Fehlerseiten registrieren in der Testfixture dieselben
Template-Helfer wie die Anwendung; Context-Processor bleiben verboten.

Gemeinsamer Tooltip-Controller: In horizontalen `.btn-list`-/`.admin-row-actions`-
Gruppen nur oben/unten ausweichen, damit der Drucktooltip die benachbarte
Mengenaktion nicht verdeckt. Menüeinträge behalten ihre bisherigen Platzierungen.
Hover, Wechsel in den Tooltip, Escape, Fokus, freie Klickfläche und sichtbare
Seitenbreite werden auf echten Rezeptrevisionen geprüft. Screenshots bei 390 und
1440 px visuell geprüft; keine Formular-/Template- oder Baselineänderung.

R1-Dateigates: Dichte `21 passed in 118.12s (0:01:58)`, Fehlerfokus
`14 passed in 6.30s`, Ansicht/Druck `23 passed in 192.44s (0:03:12)`;
zusätzliche Tooltip-Breitenmessung `2 passed in 14.77s`.
Zusatzgate Tabler: `2 failed, 9 passed in 92.25s (0:01:32)`; zwei vorbestehende
Wochen-Selektoren erwarten das in `62888f0c` entfernte `<details>` statt Collapse
(Wrapper seit `a191cea9`). Als T mit Grund in `tools/release/known_red.txt`
erfasst. Keine offenen Produktfehler aus R1; keine Deploy-/Releasefreigabe.

## Release 18 Gruppe V: Bildschirmzeilen und Aktionsmenüs (2026-09-27)

`/admin/screens`, Admin, veröffentlichte Pläne, JS/No-JS, 320–1440 px:
Zeilen wachsen mit Vorschau und Inhalt; mobile Schalter bleiben anklickbar.
Geschlossene gemeinsame Aktionsmenüs beanspruchen keinen Inhaltsplatz.
R44/M64 (36/44-px-Symbolaktionen), R47/M66 (Inhalt ohne Abschneiden).
Pool `worker-test-ps5`, jede Datei in eigenem pytest-Prozess:
Bildschirmvorschauen `13 passed in 114.52s (0:01:54)`;
Logo-/Karten-Geometrie `12 passed in 64.69s (0:01:04)`;
Ausgabehubs mit Tastatur und Wochenwahl `21 passed in 96.99s (0:01:36)`.
`/admin/vorlagen/rezepte`, Admin, Rezept und gespeicherter Stand, JS/No-JS:
Tooltips bleiben über/unter dem Auslöser und blockieren nach Browser-Zurück
keinen benachbarten Kopfbutton. Rezeptvorlagen-Browser: `5 passed in 31.00s`.
Branding-Korrekturen: `9 passed in 36.50s`; Vorlagen-Korrekturen einschliesslich
nativer Requests, Fehlerzustände und Zoom: `29 passed in 92.03s (0:01:32)`.
Keine Formular- oder Screenshot-Baselineänderung.

## Release 17: Formularlabels und Symbolaktionen (2026-09-27)

`/admin/{cafeteria,patienten}/menu`, Admin, befüllt und Feldfehler:
Herkunft und Allergen-Präsenz haben sichtbare, klickbare Formularlabels.
Geklonte Zeilen übernehmen keine flüchtigen Tooltip-IDs. Beschreibung/Hinweis
bleiben im erreichbaren nativen Detailabschnitt. Menüeditor: `20 passed in 115.03s (0:01:55)`.
`/admin/rezepte`, Admin, lange Titel, JS/No-JS, 390/820/1440 px:
feste Spaltenanteile verhindern Höhenänderungen anderer Zeilen beim Öffnen
eines Aktionsmenüs. Navigation: `7 passed in 66.58s (0:01:06)`.
Symbolaktionen: 36 px bei feinem Zeiger, 44 px bei echter Touch-Emulation;
zugängliche Namen geprüft. Tabler: `11 passed in 44.04s`.
Formular-, Navigations- und Fachtexte bleiben sichtbar. Keine Baseline angehoben.

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
| static/admin-tabler.css | 0 | 0 | 0 | 0 | 0 | 0 | 17 |
| static/admin-vorlagen-druck.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-vorschau-bildschirme.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-week-tabler.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-wochenplan-kern.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/admin-wochenuebersicht.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/cookbook-admin.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/recipe-admin.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| static/recipe-document.css | 0 | 0 | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | 167 | 74 | 11 | 5 | 52 | 17 | 24 |
