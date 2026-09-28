# Icon-first UI-Audit (WP1a, Runde 2)

Vollständiges Ansichteninventar gemäss Spezifikation §12.1 und Abnahme UI-01. Runde 1 deckte neun Kernansichten ab. Diese Runde erfasst jede administrative HTML-Route aus `docs/superpowers/backlog-0909/ui-route-matrix.json` und jedes Template unter `reference_scaffold/cafeteria/templates/admin/`.

Stand der Zählung: 2026-09-26, Worktree `docs/icon-first-inventory-0926`. Kein Produktcode geändert. Keine Live-Abnahme, kein Browserlauf.

## Fortsetzung 2026-09-28: Abnahme noch offen

Die folgenden Abschnitte bleiben das historische Quelleninventar. Ihre offenen
Zeilen werden nicht allein durch Release 18 oder einen bestandenen Listenvergleich
zu einer appweiten Abnahme. Aktuelle Produktionsrevision ist
`c8c2e3c11149b41523a50a34dcba64cdc60230a6`, seit 02:32 CEST gesund,
Login HTTP 200 und `github/main` exakt gleich. Der Timer bleibt bei `*:07` aktiv.
Die Fahrt 02:07 schloss mit `NEW_FAILURES=0` ab (3137 Tests, 13 bekannte Fehler),
scheiterte dann beim Push am fehlenden systemd-Login-Kontext. Derselbe geprüfte
SHA wurde manuell gepusht und deployed. Dienst-Drop-in setzt jetzt `User=root`
und `SetLoginEnvironment=yes`; separater systemd-Push-Dry-Run bestand. Beleg:
`/var/tmp/dishboard-release-train/20260928T000700Z-lbkljO/recovery.md`.
Die nächste vollständig unbeaufsichtigte Fahrt steht noch aus.

Governance-Abgleich `wp-8db997a09cea`: AGENTS.md, CLAUDE.md und zentrales
UI-Manifest nennen jetzt ausdrücklich den Vorrang der Icon-first-Spezifikation
vor historischen Text-/48-px-/Statuskartenregeln. Unabhängiger Quellenreview:
ACCEPT; identische Projektregeln, Manifestprüfung und `git diff --check` grün.
Keine Produktänderung oder zusätzliche Browserabnahme durch dieses Dokumentpaket.

Statusanzeige `wp-e0e6302c8073`, `25f09eea`: mehrere explizite bzw. lokale
Integrationslinien werden wieder angezeigt. Nur aktive zusätzlich entdeckte
Linien beeinflussen die Überfälligkeitswarnung; die konfigurierte Zug-Linie
behält ihre bisherige Altersprüfung. Exakter Live-SHA, Health/Login und
120-Minuten-Grenze bleiben erhalten. Eigener isolierter Lauf:
`rtk python3 -m unittest discover -s tools/release -p test_deploy_status.py -v`,
`Ran 10 tests in 6.371s`, `OK`, Exit 0. Stub-PATH, kein Dienst-/DB-/Browserzugriff.
Quellreview bestätigt zitierte Argumente, keine Shell-Auswertung von Branchwerten
und unveränderten Einzelzweig-Aufruf im Release-Zug. Lauf 03:07 bleibt auf
`dab6fda61c407883f7026c3bf7b1eed76c1b7a25` festgehalten; diese späteren Änderungen
gehören erst zur nächsten Fahrt.

Integriert nach eigener Diffprüfung und erneutem Gate: API-Symbolaktionen
(`wp-cb8f25515d05`, `6a656cd7`/`45d12e76`), Listenhülle
(`wp-edf89d346095`, `e169a69d`) und faire Listenmessung
(`wp-ae3225c63108`, `75453eee`) sowie kompakte Wochenwarnungen
(`wp-229caefe57d9`, `6ef6fb40`). Danach integriert: Rezepteditor
(`wp-811ff239d8e4`, `24be3ef8`), Wochen-Reflow (`wp-f1ea058b4ab3`, `1825cdd7`)
und präzise Label-Schlüsselworterkennung (`wp-da3257c1d042`, `69e87ddd`).
Vorlagenverdichtung (`wp-1491fd9d623a`, `8624fe48`) und native Listenmessung
(`wp-14feb78d051f`, `4c8cac50`) sind ebenfalls unabhängig geprüft integriert.
Native Rezeptauswahl-/Menüdetails-/Fehleraktionen (`wp-dcf177dec7ad`, `72862c47`)
sind ebenfalls unabhängig geprüft integriert. Weitere Detailaktionen und die
Pilot-Dichtemessung bleiben isolierte Pakete.
Je ein Worktree, Testpool und Dateibesitzer; Prüfung und
Manifestpflege vor Aufnahme in `integrate/icon-first-r18`. Paketverträge lokal
unter `/var/tmp/dishboard-*-0928*.json`. Die nach `c8c2e3c` integrierten Pakete
sind noch nicht live.

Eigene neue Prüfungen auf R18, Pool `worker-test-api-int2`, über
`rtk bash tools/release/gate.sh <pool> <worktree> -q <datei>`:

- `tests/test_ui_semantic_macros_browser.py`: `42 passed in 52.56s`, `GATE_EXIT=0`.
  Gemeinsame Makros, drei Sprachen, Tastatur und No-JS-Reflow; keine vollständige
  Prüfung ihrer Verwendungen auf Produktseiten.
- `tests/test_ui_fullwidth_shell_browser.py`: `7 passed in 130.86s (0:02:10)`,
  `GATE_EXIT=0`. Arbeitsbreite für sechs Routen, JS/No-JS, Desktop und schmal,
  echter Browserzoom 2 mit CSS-Zoom 1; Fokus und Speichern bei geringer Höhe.
  JUnit: `/var/tmp/dishboard-wp6-shell-0928.xml`.
- `tools/build_manifest.py --verify`: `Paketliste und SHA-256-Manifest: OK`.
- `tests/test_menu_collection_browser.py`: `18 passed in 73.95s (0:01:13)`,
  `GATE_EXIT=0`; JUnit `/var/tmp/dishboard-wp6-menu-0928.xml`.
- Audit-Commit `75453eee`, eigener zweiter Testlauf auf demselben Pool:
  `tests/test_ui_list_family_browser.py`: `4 passed in 18.46s`, `GATE_EXIT=0`.
  JUnit `/var/tmp/dishboard-list-audit-root-0928.xml`; `test_delta` meldet
  Tests 3→4, Assertions 15→25, Skips 0→0, `flagged=0`.
- API: `tests/test_ui_semantics.py` und `tests/test_admin_api_key_policy.py`:
  `206 passed in 34.96s`; `tests/test_icon_api_browser.py`:
  `4 passed in 16.04s`; beide `GATE_EXIT=0`.
- Listenhülle: `tests/test_list_shell_browser.py`: `1 passed in 15.62s`;
  `tests/test_admin_shared_patterns_browser.py`: `55 passed in 76.10s (0:01:16)`;
  beide `GATE_EXIT=0`. Eigene Desktop-/Mobilscreenshots gesichtet.
  JUnit `/var/tmp/dishboard-list-shell-root-0928.xml` und
  `/var/tmp/dishboard-list-shell-shared-root-0928.xml`. Änderungen betreffen
  gemeinsame Listenrahmen, Bestellung und Vorlagen, keine Formularverträge.

Der Browser-MCP startete zweimal mit `Chromium sandboxing failed!` nicht.
Die vorgenannten Projektbrowserläufe funktionieren unabhängig davon. Eine
authentifizierte Produktions-Sichtprüfung ist damit nicht nachgewiesen.
OCR scheiterte aktuell mit HTTP 402 bei SambaNova; kein erfolgreiches OCR-Review
und kein automatischer Anbieterwechsel.

| Kriterium | Aktueller Beleg und verbleibende Prüfung |
|---|---|
| UI-01 | Historisches Routen-/Templateinventar vorhanden. 41 Listen decken Editor-, Fehler- und dynamische Zustände nicht vollständig ab. Abgleich offen. |
| UI-02 | Neuer Listenvergleich integriert: 41 Seiten, 82 Blöcke inklusive Bildschirmvorlagen. Abschliessender Vergleich nach Produktkorrekturen offen. |
| UI-03 | Gemeinsame Makros geprüft. Native Summary- und dynamische Editoraktionen noch migrieren und auf Seiten prüfen. |
| UI-04 | API-Schlüssel normalisiert und mit JS/No-JS geprüft. Rezepteditor, Druckvorlagen-Auswahl und Bildschirm-Fehlerseite haben konkrete Restkandidaten. Keine appweite Freigabe. |
| UI-05 | Normale Listen bisher ohne gemeldete Überschreitung. Editor-Unterlisten und Dialogzustände separat prüfen. |
| UI-06 | Makronamen in DE/EN/Pseudo geprüft; Kontextnamen auf allen Produktseiten und reduzierten Rollen offen. |
| UI-07 | Makrotastatur und Shell-Fokus bestanden; Dialogrückkehr und Produktaktionen appweit offen. |
| UI-08 | Menü-Sammlung mit Tooltip-/Tastaturtests bestanden. Weitere Produktseiten und neue Summary-Verwendungen bleiben zu prüfen. |
| UI-09 | Touch-Tests vorhanden; neue aktuelle Nachweise für alle gemeinsamen Aktionsvarianten und Seiten fehlen noch. |
| UI-10 | Makrofilter/Formattribute geprüft; Suche per Enter, Reset und erhaltene Filter auf Produktseiten offen. |
| UI-11 | Gemischte/aktive/archivierte Filter und Normalzustände appweit offen. |
| UI-12 | Makroprüfung unterscheidet fehlend/ungeprüft. Allergen-, Herkunfts- und Lagerzustände im Produkt separat nachweisen. |
| UI-13 | Freigabesperren unverändert als harter Vertrag. Aktuelles negatives Veröffentlichungsgate offen. |
| UI-14 | Registry-Vertrag vorhanden; konkrete Speichern-/Prüfen-/Veröffentlichen-Abläufe weiter prüfen. |
| UI-15 | API-POST und Bestätigung im Paket; übrige destruktive/duplizierende Aktionen samt Abbruch und Rollen offen. |
| UI-16 | Bestehende Rollen-Gates weiterverwenden. Ein Admin-Screenshot beweist keine Nur-Lesen-Abnahme. |
| UI-17 | Beide Profile/Mahlzeiten/Gänge und bestehende Zuordnungen aktuell funktional prüfen. |
| UI-18 | Shelltest belegt erreichbares Speichern/Feldfokus; Detailrückkehr und ungespeicherte Änderungen appweit offen. |
| UI-19 | Kalender-Überlauf inklusive exakter verborgener Anzahl und Randtage aktuell prüfen. |
| UI-20 | Lange Texte und Shell-Reflow geprüft; Leer-/Lade-/Fehlerzustände über alle Module offen. |
| UI-21 | Shellmatrix 1440/1024/768/390 und weitere Breiten bestanden; Seitenmatrix samt geöffneten Zuständen noch offen. |
| UI-22 | Echter 200-%-Zoom für Woche, Rezeptansicht und Editor bestanden; restliche Referenztypen offen. |
| UI-23 | Vorlagen nach Korrektur 189.80 px ab Main. Pilotlisten noch darüber: Bausteine 243 px, Rezepte 285.8 px; Kopfverdichtung bleibt offen. |
| UI-24 | Zehn vollständige Desktopdatensätze in beiden Bausteinprofilen und Rezepten nachgewiesen; Bausteine natürlich zweizeilig. Rezepte verwenden separate Ertragsspalte, kein Zweizeilen-Rezeptnachweis. |
| UI-25 | Wochenwarnungen und Vorlagen-Hub verdichtet. Druckvorlageneditor sowie Bereichs-/Zeitmeldungen bleiben offen. |
| UI-26 | Erst nach Migration belegbar tote Overrides entfernen; keine vorsorgliche globale Stilbereinigung. |
| UI-27 | Shellnavigation im Zoom geprüft; aktive Parent-/Child-Zustände, Touch und reduzierte Rollen weiter prüfen. |
| UI-28 | Neue lokale Screenshots vorhanden. Vergleichbare Vorher/Nachher-Belege für beide Piloten, Woche und schmale Ansicht noch zusammenführen. |

Zusätzliche konkrete Quellbefunde, vor Änderung im Browser bestätigen:
`rezepte_editor.html` und `_rezepte_fields.html` enthalten beschriftete
Überlauf-/Detailaktionen; `_recipe_template_selection.html` eigene Such- und
Revisions-Summary-Buttons; `screen_template_unavailable.html` einen beschrifteten
Wiederholen-Link. Im echten Zoom-Screenshot des Rezepteditors ist «Mehr» sichtbar.
Diese Ansichten fehlen teilweise im 41-Seiten-Listenvergleich.

Neue lokale Sichtbelege aus dem Audit-Worktree bestätigen ausserdem: Patienten-
Wochenplan wiederholt die Allergen-/Zeitwarnungen trotz Kopfsumme; Vorlagen zeigen
vier Statuskarten sowie mehrfach «Standard/Aktiv» und dieselbe Druckerklärung.
Die Kalender-Markierung für heute ist ein semantischer Inset-Rahmen, kein
dekorativer Schatten pro Datensatz. Bei Trennlinien müssen innere Zeilen und
beide Seiten einer benachbarten Kante gemessen werden; ein einzelner letzter
Datensatz benötigt keinen künstlichen Trenner darunter.

## 0. Zählmethode

Wegwerfskript, nicht im Repo: `/tmp/claude-0/-nvmetank1-projects-menuplan/2f4bbcec-0188-43ba-9334-2cbe2fa40c97/scratchpad/wp1a/count_admin_views.py`. Es liest die Routenmatrix und den Quelltext der Admin-Templates. Jinja- und HTML-Kommentare werden vor dem Zählen entfernt. Gezählt wird der Quelltext, nicht das gerenderte DOM.

| Kürzel | Definition |
|---|---|
| ib | Aufrufe `icon_button(`; davon `text=` und literales `icon_only=true` |
| class=btn | Vorkommen von `class="btn` oder `class='btn` (trifft auch `btn-primary`) |
| button | Tags `<button` |
| row_actions | Aufrufe `row_actions(` |
| label | Aufrufe `label(`, nicht `icon_label(` und nicht der Alias `ui_label(` |
| status_badge_sem | Aufrufe `status_badge_sem(` |
| badge | Token `badge` ausserhalb von Bezeichnern wie `status_badge_sem` |
| filter_bar_sem | Aufrufe `filter_bar_sem(` |
| suchform | `<form>`, das `role="search"`, `type="search"`, `admin-filter-bar` oder eine Klasse mit `filter` enthält |
| details | Tags `<details` |
| card-zeilen | `{% for %}`-Schleifen, deren direkter Rumpf das Token `card` enthält |
| zeilenaktionen max | Obergrenze des Skripts je Schleife, nachdem verschachtelte Schleifen entfernt wurden. Kein Ersatz für die sichtbare Zeile. Werte über 2 sind in §6 gegen die Quelle geprüft. |

Grenze der Zählung: `label as ui_label` zählt nicht als `label(`. `components.html` und `_week_menu_card.html` rufen das Makro so auf. `form_footer(...)` in `_macros.html` rendert «Abbrechen» und «Speichern», ohne dass die aufrufende Datei selbst `<button` enthält (`kuechenkalender_anlass.html:45`).

**Ansicht:** Admin-Route mit `visual: true` und `classification: html`, die ein Template rendert. 60 solche Matrix-Einträge, davon eine ohne Template.

**Liste:** Ansicht, die im normalen Zustand eine wiederholte Datensatzliste, ein Kalender-/Wochenraster oder eine Editor-Unterliste zeigt. Die Skriptmarke «Template enthält Tabelle, `list_row`, Karte oder Kalender» trifft 42 Routen. §6 zieht sieben Fehlzuordnungen ab und nimmt drei Rezepteditor-Routen dazu, deren Zeilen nur über das Makro `row_actions` in `_rezepte_fields.html` laufen.

## 1. Korrekturen an Runde 1

Die Zeilenangaben aus Runde 1 stimmen überwiegend. Diese Zuordnungen waren falsch oder unvollständig:

1. **Zutaten sind nicht `grundlagen_food.html`.** Die Liste ist `grundlagen.html` über `admin.master_data_list` (`GET /admin/grundlagen`, Art Zutaten und dieselben anderen Stammdatenarten). `grundlagen_food.html:1` erweitert diese Liste und ersetzt Kopf und Inhalt. Das ist die Detail- und Neuanlage der Zutat (`admin.master_data_detail`, `admin.master_data_new`), einschliesslich der Preistabelle ab Zeile 88. Der Befund «zwei Filter, Containerüberschrift, schon teilweise Iconbuttons» steht in `grundlagen.html:50-74`, nicht im Detailformular. `grundlagen_food.html:147` bleibt der Prüfknopf des Detailformulars.

2. **Rezepte sind eine Kartenliste, keine Tabelle.** `rezepte.html:26-44` rendert je Treffer `<article class="card recipe-card">`. Sichtbar sind zwei Aktionen: Bearbeiten oder Öffnen (`:33`) plus Überlauf (`:34`). Drucken, History und Öffnen im Schreibfall liegen im `<details>`. Die Skriptobergrenze 3 zählt zusätzlich den Leerzustand im `for`/`else` (`:47`).

3. **Menü-Editor zeigt nicht vier Zeilenaktionen.** `menu_editor.html:175-181`: sichtbar sind Bearbeiten und das Überlaufmenü. «Nach oben», «Nach unten» und «Löschen» liegen im `<details class="admin-compact-actions">`. Der Fertig-Knopf `:237` trägt `hidden`. Die Listenprobleme aus §2 (hohe Zeile, Bearbeiten-Button) gehören zur Sammlung `menu_collection.html:85` und zur Kartenvariante `:96-120`.

4. **Der Vorlagen-Link der Wochenkarte ist zugeklappt.** `_week_menu_card.html:13-16` steht in `<details class="admin-week-template">`. Dauerhaft sichtbar ist der Bearbeiten-/Hinzufügen-Link `:77`.

5. **Wochenverwaltung und Rezeptliste überschreiten zwei sichtbare Zeilenaktionen nicht.** `week_management.html:97-108`: Öffnen plus Überlauf `week-more`. Vorschau und Kopieren sind darin. Das Skript zählte sie mit, weil die Klasse nicht `admin-compact-actions` heisst.

6. **Tageszellen sind keine einzelne Aktionszeile.** `patienten.html` und `cafeteria.html` legen Suppe, Dessert, Menükarte und Speichern nebeneinander in die Tagesiteration. Je Zeile bleibt eine Aktion (`_course_line.html` ein Zweig, `_week_menu_card.html:77` ein Link). Die Skriptobergrenze 7 addiert diese Zeilen.

7. **Neun Bildschirmvorlagen der Matrix fehlen als Admin-Dateien.** `admin.screen_template_preview` rendert `public/cafeteria_week.html` oder `public/patient_week.html` (`reference_scaffold/cafeteria/admin/screen_template_routes.py:129`). Die Matrix nennt `admin/cafeteria_week.html` und `admin/patient_week.html`. Diese Pfade gibt es unter `templates/admin/` nicht.

Unverändert richtige Runde-1-Stellen: `_course_line.html:22` und `:26`, `_week_controls.html:65` (daneben der Rohknopf `:63`, wenn die Beschriftung länger als 18 Zeichen ist), `kuechenkalender.html:49` und `:114-116`, `components.html:140`, `component_editor.html:33-34`, `gerichtvorlagen.html:43` und `:89`, `lager.html:41` und `:43`.

## 2. Pflichtreferenzen (§2), zuständige Templates

Pflichtreferenz ist die Ansicht aus den Referenzbildern. Editoren derselben Familie sind im Inventar, in der Spalte aber «nein».

| Ansicht | Route | Zuständiges Template | Beleg |
|---|---|---|---|
| Patienten-Wochenplan | `admin.patienten` | `patienten.html` plus Wochenpartials | Karte je Tag `patienten.html:57`. Gangzeile `_course_line.html:22` (`text=` «planen») und `:26` (roher Icon-Link Bearbeiten, anderer Zweig). Menükarte `_week_menu_card.html:77`. Kopf `_week_controls.html:63-65`. |
| Wochenübersicht | `admin.cafeteria` | `cafeteria.html` plus dieselben Partials | Dieselbe Karten- und Gangstruktur. Vorlagenlink nur in `_week_menu_card.html:13-16`. |
| Küchenkalender | `admin.kitchen_calendar` | `kuechenkalender.html` | Planen `kuechenkalender.html:49` (`text='Planen'`). Bereichsfilter als `<a class="btn">` `:114-116`. |
| Menüs | `admin.menu_collection` | `menu_collection.html` | Tabelle und Kartenreiter. Bearbeiten mit sichtbarem Text `:85` und `:120`. Hinweis-Details nur bei Beschreibung oder Notiz `:71`, `:110`. |
| Bausteine | `admin.components_get` | `components.html` | Eine Zeilenaktion `row_actions` `:140`, ohne `icon_only`, also mit Standardtext des Makros. Filter ist ein eigenes Suchformular, nicht `filter_bar_sem`. Status über `ui_label(` (Alias von `label`). |
| Zutaten | `admin.master_data_list` | `grundlagen.html` | Suchfeld plus Filter-`<details>` plus Submit `:50-64`. Zusätzliche Kartenüberschrift `:66`. Zeilenaktion `icon_only=true` `:73`. Leere Liste `:76-78`. |
| Rezepte | `admin.recipes_list` | `rezepte.html` | Karte je Zeile `:27`. Badge als rohes `badge` `:31`, nicht `status_badge_sem`. Aktionen `:33-34`. |
| Gerichtvorlagen | `admin.dish_templates_list` | `gerichtvorlagen.html` | `filter_bar_sem` `:63`. Zeile `row_actions` mit `text='Einplanen'` `:89`. Dieselbe Datei ist ab `:59` im Zweig `editing` auch Neu- und Bearbeiten-Formular. |
| Lager | `admin.inventory_home` | `lager.html` | Warnbadge je Zeile ohne Bestand `:41`. Öffnen `:43` ohne `icon_only`, daher mit Standardtext. |

`grundlagen_food.html:147` bestätigt oder hebt die Allergenprüfung der einzelnen Zutat auf. Das ist die Folgeansicht, nicht die Liste aus §2.

## 3. Summen

| Schnitt | Zahl | Bedeutung |
|---|---|---|
| Ansichten gesamt | 59 | 60 Admin-HTML-Routen mit `visual: true`, ohne `admin.order_basket_csv` (Matrix: html/visual, Templates leer, an anderer Stelle `blocked_classified_download`) |
| davon Listen | 38 | 42 Skripttreffer, minus 7 Fehlzuordnungen, plus 3 Rezepteditor-Routen |
| davon mit mehr als 2 sichtbaren Zeilenaktionen | 2 | `admin.shopping_list_detail`, `admin.vorlagen` |
| davon mit Text-Aktionsbuttons | 2 | beide Listen aus der vorigen Zeile |

Parallel, nicht als Teilmenge der Zwei: 58 der 59 Ansichten haben mindestens einen Text-Aktionsbutton in der Datei, in einem Include oder über `form_footer`. Ausnahme ist `admin.branding_preview` (reine Markenfläche, keine Aktion). Alle 38 Listen haben Text-Aktionsbuttons. `icon_button` zeigt ohne literales `icon_only=true` den übersetzten Namen oder `text=`.

Die sieben Abzüge von den 42 Skripttreffern:

- `admin.dish_template_edit` und `admin.dish_template_new`: die Tabelle steht in `{% if not editing %}` (`gerichtvorlagen.html:59`).
- `admin.master_data_new`: die Preistabelle steht in `{% if row %}` (`grundlagen_food.html:80`).
- `admin.cookbook_new`: die Zuordnungstabelle steht in `{% if book %}` (`kochbuch_editor.html:80`).
- `admin.recipe_view`: Erfolgspfad `rezepte_ansicht.html`. `rezepte_scale.html` nur bei Eingabefehler (`recipe_revision_routes.py:51-55`).
- `admin.recipe_revision`: Standard `rezepte_revision.html`. Skalierung nur mit `mode=scale` (`recipe_revision_routes.py:127`).
- `admin.screen_template_preview`: öffentliche Woche, siehe §1 Punkt 7.

Die drei Ergänzungen: `admin.recipe_edit`, `admin.recipe_new`, `admin.recipe_status`. Dieselbe Datei `rezepte_editor.html` ruft je Zutaten-, Schritt- und Bildzeile `row_actions` aus `_rezepte_fields.html:17` auf. Sichtbar ist die Summary «Aktionen», der Rest liegt im `<details>`.

## 4. Abdeckungstabelle

Status durchgehend `offen`. Pflicht «ja» nur für die neun Referenzansichten. «zeilenaktionen max» ist die ungeprüfte Schleifenobergrenze aus §0.

| Route | Template(s) | Listentyp | Zahlen | Pflichtreferenz | Status |
|---|---|---|---|---|---|
| `GET /admin/<any(cafeteria, patienten):family>/copy`<br>`admin.copy_get`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/copy.html` | copy.html: Formular | copy.html: ib 2 (text= 1, icon-only 1) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/<any(cafeteria, patienten):family>/komponenten`<br>`admin.components_get`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/components.html` | components.html: Tabelle | components.html: ib 2 (text= 0, icon-only 0) · class=btn 3 · button 1 · row_actions 1 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 1 · details 3 · card-zeilen 0 · zeilenaktionen max 1 | ja (Bausteine) | offen |
| `GET /admin/<any(cafeteria, patienten):family>/komponenten/<public_id>`<br>`admin.component_detail`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/component_editor.html` | component_editor.html: Formular | component_editor.html: ib 0 (text= 0, icon-only 0) · class=btn 3 · button 2 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 2 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/<any(cafeteria, patienten):family>/menu`<br>`admin.menu_get`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/menu_editor.html` | menu_editor.html: Liste + Formular | menu_editor.html: ib 8 (text= 4, icon-only 0) · class=btn 12 · button 8 · row_actions 0 · label 1 · status_badge_sem 0 · badge 4 · filter_bar_sem 0 · suchform 1 · details 4 · card-zeilen 0 · zeilenaktionen max 3 | nein | offen |
| `GET /admin/<any(cafeteria, patienten):family>/menues`<br>`admin.menu_collection`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/menu_collection.html` | menu_collection.html: Tabelle + Kartenliste | menu_collection.html: ib 2 (text= 0, icon-only 0) · class=btn 6 · button 2 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 1 · suchform 0 · details 2 · card-zeilen 1 · zeilenaktionen max 2 | ja (Menüs) | offen |
| `GET /admin/<any(cafeteria, patienten):family>/preview`<br>`admin.preview`<br>Zustände: default, access_denied_401, access_denied_403 | `admin/preview.html` | preview.html: Sonstiges | preview.html: ib 0 (text= 0, icon-only 0) · class=btn 3 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/<any(cafeteria, patienten):family>/wochen`<br>`admin.week_management`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/week_management.html` | week_management.html: Tabelle | week_management.html: ib 1 (text= 0, icon-only 0) · class=btn 9 · button 1 · row_actions 0 · label 2 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 2 · card-zeilen 0 · zeilenaktionen max 3 | nein | offen |
| `GET /admin/<any(cafeteria, patienten):family>/wochen/pruefung`<br>`admin.week_review_get`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/week_review.html` | week_review.html: Liste | week_review.html: ib 1 (text= 0, icon-only 1) · class=btn 1 · button 1 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/api`<br>`admin.api_overview`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/api.html` | api.html: Tabelle | api.html: ib 5 (text= 3, icon-only 0) · class=btn 7 · button 2 · row_actions 0 · label 4 · status_badge_sem 2 · badge 0 · filter_bar_sem 0 · suchform 0 · details 5 · card-zeilen 0 · zeilenaktionen max 2 | nein | offen |
| `GET /admin/benutzer`<br>`admin.local_users_list`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/local_user_unavailable.html`<br>`admin/local_users.html` | local_user_unavailable.html: Zustand<br>local_users.html: Liste | local_user_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>local_users.html: ib 6 (text= 2, icon-only 1) · class=btn 2 · button 1 · row_actions 1 · label 2 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 1 · details 1 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET /admin/benutzer/<uuid:public_id>`<br>`admin.local_user_detail`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/local_user_editor.html`<br>`admin/local_user_unavailable.html` | local_user_editor.html: Formular<br>local_user_unavailable.html: Zustand | local_user_editor.html: ib 6 (text= 5, icon-only 0) · class=btn 4 · button 1 · row_actions 0 · label 3 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 4 · card-zeilen 0 · zeilenaktionen max 0<br>local_user_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/benutzer/neu`<br>`admin.local_user_new`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/local_user_create.html`<br>`admin/local_user_unavailable.html` | local_user_create.html: Sonstiges<br>local_user_unavailable.html: Zustand | local_user_create.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>local_user_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/benutzer/protokoll`<br>`admin.local_user_events`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/local_user_events.html`<br>`admin/local_user_unavailable.html` | local_user_events.html: Tabelle<br>local_user_unavailable.html: Zustand | local_user_events.html: ib 2 (text= 1, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>local_user_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/benutzer/zugriffsverlauf`<br>`admin.access_history`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/access_history.html` | access_history.html: Tabelle | access_history.html: ib 3 (text= 1, icon-only 1) · class=btn 3 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 1 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET,POST /admin/bereiche-zeiten`<br>`admin.operations_settings`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/operations.html` | operations.html: Tabelle + Kartenliste | operations.html: ib 4 (text= 1, icon-only 0) · class=btn 5 · button 5 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 8 · card-zeilen 2 · zeilenaktionen max 1 | nein | offen |
| `GET /admin/bestellung`<br>`admin.order_home`<br>Zustände: default, empty, invalid, access_denied_401, access_denied_403 | `admin/bestellung.html` | bestellung.html: Liste | bestellung.html: ib 1 (text= 0, icon-only 0) · class=btn 7 · button 3 · row_actions 0 · label 0 · status_badge_sem 2 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET /admin/bestellung/korb/<public_id>`<br>`admin.order_basket`<br>Zustände: default, empty, invalid, access_denied_401, access_denied_403 | `admin/bestellung_korb.html` | bestellung_korb.html: Tabelle | bestellung_korb.html: ib 0 (text= 0, icon-only 0) · class=btn 4 · button 2 · row_actions 0 · label 0 · status_badge_sem 1 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/bestellung/korb/<public_id>/csv`<br>`admin.order_basket_csv`<br>Zustände: default, empty, invalid, access_denied_401, access_denied_403 | — | — | — | nein | offen |
| `GET /admin/cafeteria`<br>`admin.cafeteria`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/cafeteria.html` | cafeteria.html: Kalender/Raster | cafeteria.html: ib 1 (text= 1, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 1 · zeilenaktionen max 0 | ja (Wochenübersicht) | offen |
| `GET,POST /admin/design/darstellung`<br>`admin.display_settings`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/display_settings.html` | display_settings.html: Formular | display_settings.html: ib 3 (text= 0, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET,POST /admin/design/marke`<br>`admin.branding_editor`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/branding_editor.html` | branding_editor.html: Formular | branding_editor.html: ib 4 (text= 1, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 4 · status_badge_sem 2 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/design/marke/vorschau/<int:revision>`<br>`admin.branding_preview`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/branding_preview.html` | branding_preview.html: Sonstiges | branding_preview.html: ib 0 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/einkaufslisten`<br>`admin.shopping_lists_index`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/einkaufslisten.html` | einkaufslisten.html: Liste | einkaufslisten.html: ib 3 (text= 1, icon-only 0) · class=btn 5 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 2 | nein | offen |
| `GET /admin/einkaufslisten/<public_id>`<br>`admin.shopping_list_detail`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/einkaufsliste.html` | einkaufsliste.html: Tabelle | einkaufsliste.html: ib 7 (text= 6, icon-only 0) · class=btn 6 · button 4 · row_actions 0 · label 6 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 1 · details 0 · card-zeilen 0 · zeilenaktionen max 3 | nein | offen |
| `GET /admin/gerichtvorlagen`<br>`admin.dish_templates_list`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/gerichtvorlagen.html` | gerichtvorlagen.html: Tabelle | gerichtvorlagen.html: ib 9 (text= 5, icon-only 0) · class=btn 4 · button 2 · row_actions 1 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 1 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 1 | ja (Gerichtvorlagen) | offen |
| `GET /admin/gerichtvorlagen/<public_id>`<br>`admin.dish_template_edit`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/gerichtvorlagen.html` | gerichtvorlagen.html: Tabelle | gerichtvorlagen.html: ib 9 (text= 5, icon-only 0) · class=btn 4 · button 2 · row_actions 1 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 1 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET /admin/gerichtvorlagen/<public_id>/einplanen`<br>`admin.dish_template_plan`<br>Zustände: default, access_denied_401, access_denied_403, invalid, source_conflict_409, legacy_without_active_revision_409 | `admin/gerichtvorlage_einplanen.html` | gerichtvorlage_einplanen.html: Formular | gerichtvorlage_einplanen.html: ib 7 (text= 4, icon-only 1) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/gerichtvorlagen/neu`<br>`admin.dish_template_new`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/gerichtvorlagen.html` | gerichtvorlagen.html: Tabelle | gerichtvorlagen.html: ib 9 (text= 5, icon-only 0) · class=btn 4 · button 2 · row_actions 1 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 1 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET /admin/grundlagen`<br>`admin.master_data_list`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/grundlagen.html`<br>`admin/grundlagen_unavailable.html` | grundlagen.html: Liste<br>grundlagen_unavailable.html: Zustand | grundlagen.html: ib 4 (text= 1, icon-only 1) · class=btn 4 · button 2 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 1 · details 1 · card-zeilen 0 · zeilenaktionen max 2<br>grundlagen_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | ja (Zutaten) | offen |
| `GET /admin/grundlagen/<kind>/<public_id>`<br>`admin.master_data_detail`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/grundlagen_food.html`<br>`admin/grundlagen_location_conflict.html`<br>`admin/grundlagen_unavailable.html`<br>`admin/grundlagen_unit.html`<br>`admin/grundlagen_vocabulary.html` | grundlagen_food.html: Tabelle<br>grundlagen_location_conflict.html: Zustand<br>grundlagen_unavailable.html: Zustand<br>grundlagen_unit.html: Formular<br>grundlagen_vocabulary.html: Formular | grundlagen_food.html: ib 7 (text= 5, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 1 · details 7 · card-zeilen 0 · zeilenaktionen max 0<br>grundlagen_location_conflict.html: ib 1 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>grundlagen_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>grundlagen_unit.html: ib 1 (text= 0, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0<br>grundlagen_vocabulary.html: ib 0 (text= 0, icon-only 0) · class=btn 2 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET,POST /admin/grundlagen/<kind>/neu`<br>`admin.master_data_new`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/grundlagen_food.html`<br>`admin/grundlagen_location_conflict.html`<br>`admin/grundlagen_unavailable.html`<br>`admin/grundlagen_unit.html`<br>`admin/grundlagen_vocabulary.html` | grundlagen_food.html: Tabelle<br>grundlagen_location_conflict.html: Zustand<br>grundlagen_unavailable.html: Zustand<br>grundlagen_unit.html: Formular<br>grundlagen_vocabulary.html: Formular | grundlagen_food.html: ib 7 (text= 5, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 1 · details 7 · card-zeilen 0 · zeilenaktionen max 0<br>grundlagen_location_conflict.html: ib 1 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>grundlagen_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>grundlagen_unit.html: ib 1 (text= 0, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0<br>grundlagen_vocabulary.html: ib 0 (text= 0, icon-only 0) · class=btn 2 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET,POST /admin/import-preview`<br>`admin.import_preview`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/import_preview.html` | import_preview.html: Formular | import_preview.html: ib 3 (text= 2, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/kalkulation`<br>`admin.cost_home`<br>Zustände: default, empty, invalid, access_denied_401, access_denied_403 | `admin/kalkulation.html` | kalkulation.html: Tabelle | kalkulation.html: ib 3 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 2 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `POST /admin/kalkulation/vorschau`<br>`admin.cost_preview`<br>Zustände: default, empty, invalid, access_denied_401, access_denied_403 | `admin/kalkulation.html` | kalkulation.html: Tabelle | kalkulation.html: ib 3 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 2 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/kochbuecher`<br>`admin.cookbooks_list`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/kochbuecher.html` | kochbuecher.html: Liste | kochbuecher.html: ib 2 (text= 0, icon-only 0) · class=btn 2 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 1 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET,POST /admin/kochbuecher/<cookbook_id>`<br>`admin.cookbook_edit`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/kochbuch_editor.html` | kochbuch_editor.html: Tabelle + Formular | kochbuch_editor.html: ib 3 (text= 3, icon-only 0) · class=btn 7 · button 2 · row_actions 0 · label 0 · status_badge_sem 0 · badge 1 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET,POST /admin/kochbuecher/<cookbook_id>/status`<br>`admin.cookbook_status`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/kochbuch_editor.html` | kochbuch_editor.html: Tabelle + Formular | kochbuch_editor.html: ib 3 (text= 3, icon-only 0) · class=btn 7 · button 2 · row_actions 0 · label 0 · status_badge_sem 0 · badge 1 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET,POST /admin/kochbuecher/neu`<br>`admin.cookbook_new`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/kochbuch_editor.html` | kochbuch_editor.html: Tabelle + Formular | kochbuch_editor.html: ib 3 (text= 3, icon-only 0) · class=btn 7 · button 2 · row_actions 0 · label 0 · status_badge_sem 0 · badge 1 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET /admin/kuechenkalender`<br>`admin.kitchen_calendar`<br>Zustände: default, access_denied_401 | `admin/kuechenkalender.html` | kuechenkalender.html: Kalender/Raster | kuechenkalender.html: ib 6 (text= 4, icon-only 2) · class=btn 4 · button 1 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | ja (Küchenkalender) | offen |
| `GET /admin/kuechenkalender/anlass`<br>`admin.kitchen_event_new`<br>Zustände: default, access_denied_401 | `admin/kuechenkalender_anlass.html` | kuechenkalender_anlass.html: Formular | kuechenkalender_anlass.html: ib 0 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/kuechenkalender/anlass/<public_id>`<br>`admin.kitchen_event_edit`<br>Zustände: default, access_denied_401 | `admin/kuechenkalender_anlass.html` | kuechenkalender_anlass.html: Formular | kuechenkalender_anlass.html: ib 0 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/lager`<br>`admin.inventory_home`<br>Zustände: default, empty, invalid, access_denied_401, access_denied_403 | `admin/lager.html` | lager.html: Tabelle | lager.html: ib 2 (text= 0, icon-only 0) · class=btn 3 · button 2 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 1 | ja (Lager) | offen |
| `GET /admin/patienten`<br>`admin.patienten`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/patienten.html` | patienten.html: Kalender/Raster | patienten.html: ib 0 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 1 · zeilenaktionen max 0 | ja (Patienten-Wochenplan) | offen |
| `GET /admin/rezepte`<br>`admin.recipes_list`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/rezepte.html` | rezepte.html: Kartenliste | rezepte.html: ib 0 (text= 0, icon-only 0) · class=btn 12 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 1 · filter_bar_sem 0 · suchform 1 · details 2 · card-zeilen 1 · zeilenaktionen max 3 | ja (Rezepte) | offen |
| `GET,POST /admin/rezepte/<recipe_id>`<br>`admin.recipe_edit`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/rezepte_conflict.html`<br>`admin/rezepte_editor.html` | rezepte_conflict.html: Zustand<br>rezepte_editor.html: Formular | rezepte_conflict.html: ib 0 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>rezepte_editor.html: ib 0 (text= 0, icon-only 0) · class=btn 15 · button 4 · row_actions 3 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 5 · card-zeilen 0 · zeilenaktionen max 2 | nein | offen |
| `GET,POST /admin/rezepte/<recipe_id>/status`<br>`admin.recipe_status`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/rezepte_conflict.html`<br>`admin/rezepte_editor.html` | rezepte_conflict.html: Zustand<br>rezepte_editor.html: Formular | rezepte_conflict.html: ib 0 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>rezepte_editor.html: ib 0 (text= 0, icon-only 0) · class=btn 15 · button 4 · row_actions 3 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 5 · card-zeilen 0 · zeilenaktionen max 2 | nein | offen |
| `GET /admin/rezepte/<uuid:recipe_id>/ansicht`<br>`admin.recipe_view`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/rezepte_ansicht.html`<br>`admin/rezepte_scale.html` | rezepte_ansicht.html: Sonstiges<br>rezepte_scale.html: Tabelle | rezepte_ansicht.html: ib 0 (text= 0, icon-only 0) · class=btn 6 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0<br>rezepte_scale.html: ib 0 (text= 0, icon-only 0) · class=btn 3 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET,POST /admin/rezepte/<uuid:recipe_id>/bilder`<br>`admin.recipe_images`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/rezepte_images.html` | rezepte_images.html: Tabelle | rezepte_images.html: ib 0 (text= 0, icon-only 0) · class=btn 4 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET /admin/rezepte/<uuid:recipe_id>/revisionen`<br>`admin.recipe_revisions`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/rezepte_revisionen.html` | rezepte_revisionen.html: Tabelle | rezepte_revisionen.html: ib 0 (text= 0, icon-only 0) · class=btn 4 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 2 | nein | offen |
| `GET /admin/rezepte/<uuid:recipe_id>/revisionen/<uuid:revision_id>`<br>`admin.recipe_revision`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/rezepte_revision.html`<br>`admin/rezepte_scale.html` | rezepte_revision.html: Sonstiges<br>rezepte_scale.html: Tabelle | rezepte_revision.html: ib 0 (text= 0, icon-only 0) · class=btn 3 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>rezepte_scale.html: ib 0 (text= 0, icon-only 0) · class=btn 3 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/rezepte/<uuid:recipe_id>/skalierung`<br>`admin.recipe_scale`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable | `admin/rezepte_scale.html` | rezepte_scale.html: Tabelle | rezepte_scale.html: ib 0 (text= 0, icon-only 0) · class=btn 3 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/rezepte/import`<br>`admin.recipe_import_list`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/rezepte_import.html` | rezepte_import.html: Tabelle | rezepte_import.html: ib 0 (text= 0, icon-only 0) · class=btn 11 · button 5 · row_actions 0 · label 0 · status_badge_sem 0 · badge 2 · filter_bar_sem 0 · suchform 0 · details 4 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET /admin/rezepte/import/<batch_id>`<br>`admin.recipe_import_detail`<br>Zustände: default, access_denied_401, access_denied_403, empty_or_unavailable, invalid, conflict_if_versioned | `admin/rezepte_import.html` | rezepte_import.html: Tabelle | rezepte_import.html: ib 0 (text= 0, icon-only 0) · class=btn 11 · button 5 · row_actions 0 · label 0 · status_badge_sem 0 · badge 2 · filter_bar_sem 0 · suchform 0 · details 4 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| `GET,POST /admin/rezepte/neu`<br>`admin.recipe_new`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/rezepte_conflict.html`<br>`admin/rezepte_editor.html` | rezepte_conflict.html: Zustand<br>rezepte_editor.html: Formular | rezepte_conflict.html: ib 0 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>rezepte_editor.html: ib 0 (text= 0, icon-only 0) · class=btn 15 · button 4 · row_actions 3 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 5 · card-zeilen 0 · zeilenaktionen max 2 | nein | offen |
| `GET /admin/screens`<br>`admin.screens`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/screens.html` | screens.html: Kartenliste | screens.html: ib 0 (text= 0, icon-only 0) · class=btn 6 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 1 · filter_bar_sem 0 · suchform 0 · details 2 · card-zeilen 1 · zeilenaktionen max 2 | nein | offen |
| `GET,POST /admin/screens/<any(cafeteria,patienten):family>/wochenvorlage`<br>`admin.screen_template_assignment`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/screen_template_assignment.html`<br>`admin/screen_template_unavailable.html` | screen_template_assignment.html: Kartenliste<br>screen_template_unavailable.html: Zustand | screen_template_assignment.html: ib 1 (text= 0, icon-only 0) · class=btn 3 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 1 · zeilenaktionen max 1<br>screen_template_unavailable.html: ib 0 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/vorlagen`<br>`admin.vorlagen`<br>Zustände: default, access_denied_401, access_denied_403 | `admin/vorlagen.html` | vorlagen.html: Kartenliste | vorlagen.html: ib 0 (text= 0, icon-only 0) · class=btn 28 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 6 · filter_bar_sem 0 · suchform 1 · details 3 · card-zeilen 2 · zeilenaktionen max 5 | nein | offen |
| `GET,POST /admin/vorlagen/<any(cafeteria, patienten):family>`<br>`admin.print_template_editor`<br>Zustände: default, access_denied_401, access_denied_403 | `admin/print_template_editor.html`<br>`admin/print_template_unavailable.html` | print_template_editor.html: Formular<br>print_template_unavailable.html: Zustand | print_template_editor.html: ib 0 (text= 0, icon-only 0) · class=btn 26 · button 7 · row_actions 0 · label 0 · status_badge_sem 0 · badge 1 · filter_bar_sem 0 · suchform 0 · details 8 · card-zeilen 0 · zeilenaktionen max 2<br>print_template_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET,POST /admin/vorlagen/rezepte`<br>`admin.recipe_print_template_editor`<br>Zustände: default, access_denied_401, access_denied_403 | `admin/print_template_editor.html`<br>`admin/print_template_unavailable.html`<br>`admin/recipe_template_error.html` | print_template_editor.html: Formular<br>print_template_unavailable.html: Zustand<br>recipe_template_error.html: Zustand | print_template_editor.html: ib 0 (text= 0, icon-only 0) · class=btn 26 · button 7 · row_actions 0 · label 0 · status_badge_sem 0 · badge 1 · filter_bar_sem 0 · suchform 0 · details 8 · card-zeilen 0 · zeilenaktionen max 2<br>print_template_unavailable.html: ib 1 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0<br>recipe_template_error.html: ib 0 (text= 0, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| `GET /admin/vorlagen/screens/<any(cafeteria,patienten):family>/<template_id>`<br>`admin.screen_template_preview`<br>Zustände: default, access_denied_401, access_denied_403, invalid, conflict_if_versioned | `admin/screen_template_assignment.html`<br>`admin/cafeteria_week.html`<br>`admin/patient_week.html` | screen_template_assignment.html: Kartenliste<br>cafeteria_week.html: fehlt auf Platte<br>patient_week.html: fehlt auf Platte | screen_template_assignment.html: ib 1 (text= 0, icon-only 0) · class=btn 3 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 1 · zeilenaktionen max 1 | nein | offen |


### 4.1 Partials und Gerüst

Keine eigene Route. Zahlen am Dateiquell, ohne Expandieren der Includes. `_macros.html`, `base_tabler.html`, `_workflow_sidebar.html` und `_area_tabs.html` (Import aus `base_tabler.html:20`) sind Gerüst und gehören in die gemeinsame Basis, nicht in ein Seitenpaket.

| Route | Template(s) | Listentyp | Zahlen | Pflichtreferenz | Status |
|---|---|---|---|---|---|
| Partial<br>eingebunden von: kein include, nur extends/Makro | `admin/_area_tabs.html` | Partial | ib 0 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: kein include, nur extends/Makro | `admin/_country_select.html` | Partial | ib 0 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `cafeteria.html`, `patienten.html` | `admin/_course_editor.html` | Formular | ib 0 (text= 0, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 3 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `cafeteria.html`, `patienten.html` | `admin/_course_line.html` | Partial | ib 1 (text= 1, icon-only 0) · class=btn 1 · button 0 · row_actions 0 · label 2 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `_course_editor.html` | `admin/_course_recipe_search.html` | Formular | ib 2 (text= 0, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 1 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: kein include, nur extends/Makro | `admin/_local_user_forms.html` | Formular | ib 0 (text= 0, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: kein include, nur extends/Makro | `admin/_macros.html` | Gerüst | ib 0 (text= 0, icon-only 0) · class=btn 13 · button 5 · row_actions 0 · label 2 · status_badge_sem 0 · badge 2 · filter_bar_sem 0 · suchform 1 · details 5 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| Partial<br>eingebunden von: `rezepte_revision.html` | `admin/_recipe_document.html` | Partial | ib 0 (text= 0, icon-only 0) · class=btn 2 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 2 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `print_template_editor.html` | `admin/_recipe_template_selection.html` | Formular | ib 0 (text= 0, icon-only 0) · class=btn 10 · button 4 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 3 · card-zeilen 0 · zeilenaktionen max 1 | nein | offen |
| Partial<br>eingebunden von: kein include, nur extends/Makro | `admin/_rezepte_fields.html` | Partial | ib 0 (text= 0, icon-only 0) · class=btn 2 · button 1 · row_actions 1 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `preview.html` | `admin/_service_courses.html` | Partial | ib 0 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 1 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `cafeteria.html`, `patienten.html` | `admin/_week_controls.html` | Formular | ib 9 (text= 7, icon-only 0) · class=btn 8 · button 4 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 3 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `cafeteria.html`, `patienten.html` | `admin/_week_menu_card.html` | Partial | ib 0 (text= 0, icon-only 0) · class=btn 2 · button 0 · row_actions 0 · label 0 · status_badge_sem 1 · badge 2 · filter_bar_sem 0 · suchform 0 · details 2 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `cafeteria.html`, `patienten.html` | `admin/_week_service.html` | Formular | ib 0 (text= 0, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 1 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `cafeteria.html`, `patienten.html` | `admin/_week_settings.html` | Formular | ib 0 (text= 0, icon-only 0) · class=btn 1 · button 1 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: `base_tabler.html`, `operations.html` | `admin/_workflow_sidebar.html` | Gerüst | ib 0 (text= 0, icon-only 0) · class=btn 0 · button 5 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 1 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |
| Partial<br>eingebunden von: kein include, nur extends/Makro | `admin/base_tabler.html` | Gerüst | ib 0 (text= 0, icon-only 0) · class=btn 0 · button 0 · row_actions 0 · label 0 · status_badge_sem 0 · badge 0 · filter_bar_sem 0 · suchform 0 · details 0 · card-zeilen 0 · zeilenaktionen max 0 | nein | offen |


### 4.2 Admin-Routen ohne eigene Ansicht

59 Einträge: Redirect, POST, Download, Fragment. Sie sind keine Icon-first-Ansicht. `admin.header_get` und `admin.service_get` sind HTML-Fragmente. `admin.dashboard` leitet nur um.

- `POST /admin/api/keys` `admin.api_key_create` redirect
- `POST /admin/api/keys/<public_id>/revoke` `admin.api_key_revoke` redirect
- `GET /admin/design/marke/vorschau/<int:revision>.css` `admin.branding_preview_css` download
- `GET /admin/design/marke/logo/<sha256>.png` `admin.branding_preview_logo` download
- `POST /admin/<any(cafeteria, patienten):family>/komponenten/<public_id>/archive` `admin.component_archive` post_only
- `POST /admin/<any(cafeteria, patienten):family>/komponenten/<public_id>/unarchive` `admin.component_unarchive` post_only
- `POST /admin/<any(cafeteria, patienten):family>/komponenten/<public_id>` `admin.component_update` redirect
- `POST /admin/<any(cafeteria, patienten):family>/komponenten` `admin.components_create` redirect
- `POST /admin/kochbuecher/<cookbook_id>/rezepte` `admin.cookbook_recipes` redirect
- `POST /admin/<any(cafeteria, patienten):family>/copy` `admin.copy_post` redirect
- `GET /admin/` `admin.dashboard` redirect
- `POST /admin/gerichtvorlagen/neu` `admin.dish_template_create` post_only
- `POST /admin/gerichtvorlagen/<public_id>/einplanen` `admin.dish_template_plan_post` post_only
- `POST /admin/gerichtvorlagen/<public_id>` `admin.dish_template_save` post_only
- `GET /admin/export/<profile_code>.csv` `admin.export_csv` download
- `GET /admin/<any(cafeteria, patienten):family>/header` `admin.header_get` html_fragment
- `POST /admin/<any(cafeteria, patienten):family>/header` `admin.header_post` redirect
- `POST /admin/import` `admin.import_csv` redirect
- `POST /admin/benutzer/<uuid:public_id>/<action>` `admin.local_user_change` redirect
- `POST /admin/benutzer` `admin.local_user_create` redirect
- `POST /admin/grundlagen/<kind>/<public_id>/<purpose>` `admin.master_data_change` redirect
- `POST /admin/<any(cafeteria, patienten):family>/menu` `admin.menu_post` redirect
- `POST /admin/<any(cafeteria, patienten):family>/menu/review` `admin.menu_review` redirect
- `GET /admin/vorlagen/<any(cafeteria, patienten):family>/vorschau.pdf` `admin.print_template_preview` download
- `GET /admin/<any(cafeteria, patienten):family>/preview/print` `admin.print_week` download
- `POST /admin/<any(cafeteria, patienten):family>/publish` `admin.publish` redirect
- `GET /admin/rezepte/<uuid:recipe_id>/bilder/<sha256>` `admin.recipe_asset` download
- `POST /admin/rezepte/formular` `admin.recipe_form_rows` post_only
- `POST /admin/rezepte/<uuid:recipe_id>/revisionen` `admin.recipe_freeze` redirect
- `POST /admin/rezepte/import/<batch_id>/commit` `admin.recipe_import_commit` post_only
- `POST /admin/rezepte/import` `admin.recipe_import_create` post_only
- `POST /admin/rezepte/import/<batch_id>` `admin.recipe_import_save` post_only
- `GET /admin/vorlagen/rezepte/vorschau.pdf` `admin.recipe_print_template_preview` download
- `GET /admin/rezepte/<uuid:recipe_id>/revisionen/<uuid:revision_id>/druck.pdf` `admin.recipe_revision_pdf` download
- `POST /admin/<any(cafeteria, patienten):family>/wochenvorgaben` `admin.schedule_defaults` post_only
- `GET /admin/<any(cafeteria, patienten):family>/service` `admin.service_get` html_fragment
- `POST /admin/<any(cafeteria, patienten):family>/service` `admin.service_post` redirect
- `POST /admin/<any(cafeteria, patienten):family>/wochen` `admin.week_create` redirect
- `POST /admin/<any(cafeteria, patienten):family>/wochen/pruefung` `admin.week_review_post` redirect
- `POST /admin/einkaufslisten` `admin.shopping_lists_create` post_only
- `GET /admin/einkaufslisten/<public_id>/druck.pdf` `admin.shopping_list_pdf` download
- `POST /admin/einkaufslisten/<public_id>/berechnen` `admin.shopping_list_compute` post_only
- `POST /admin/einkaufslisten/<public_id>/archivieren` `admin.shopping_list_archive` post_only
- `POST /admin/einkaufslisten/<public_id>/zeilen` `admin.shopping_list_line_toggle` post_only
- `POST /admin/einkaufslisten/<public_id>/positionen` `admin.shopping_list_manual_create` post_only
- `POST /admin/einkaufslisten/<public_id>/positionen/<item_public_id>` `admin.shopping_list_manual_update` post_only
- `POST /admin/kuechenkalender/anlass` `admin.kitchen_event_create` form
- `POST /admin/kuechenkalender/anlass/<public_id>` `admin.kitchen_event_save` form
- `POST /admin/grundlagen/zutaten/<public_id>/preis` `admin.food_price_save` form
- `POST /admin/kalkulation/beleg` `admin.cost_confirm` redirect
- `POST /admin/<any(cafeteria, patienten):family>/courses` `admin.courses_post` redirect
- `POST /admin/lager/zaehlung` `admin.inventory_count` redirect
- `POST /admin/lager/bewegung` `admin.inventory_move` redirect
- `POST /admin/lager/umbuchung` `admin.inventory_transfer` redirect
- `POST /admin/bestellung/artikel` `admin.order_article_create` redirect
- `POST /admin/bestellung/korb` `admin.order_basket_create` redirect
- `POST /admin/bestellung/korb/<public_id>/bedarf` `admin.order_basket_from_demand` redirect
- `POST /admin/bestellung/korb/<public_id>` `admin.order_basket_save` redirect
- `POST /admin/bestellung/lieferanten` `admin.order_supplier_create` redirect


### 4.3 Ausgenommen §0

Öffentlicher Menüplan, Druck und Digital Signage. 14 Routen. Die Admin-Vorschau `admin.preview` und der Admin-Druckeditor bleiben im Inventar. `admin.print_week` und die PDF-Downloads stehen in §4.2, weil sie Dateien ausliefern und keine Verwaltungsseite sind.

- `GET /cafeteria/heute/` `public.cafeteria_today` blueprint=public class=html templates=public/cafeteria_today.html, public/unavailable.html
- `GET /cafeteria/wochenangebot/` `public.cafeteria_week` blueprint=public class=html templates=admin/screen_template_unavailable.html, public/cafeteria_week.html, public/unavailable.html
- `GET /cafeteria/wochenangebot/ohne-bilder/` `public.cafeteria_week_without_images` blueprint=public class=html templates=admin/screen_template_unavailable.html, public/cafeteria_week.html, public/unavailable.html
- `GET /cafeteria/legende/` `public.legend` blueprint=public class=html templates=public/legend.html
- `GET /patienten/heute/` `public.patient_today` blueprint=public class=html templates=public/patient_today.html, public/unavailable.html
- `GET /patienten/wochenplan/` `public.patient_week` blueprint=public class=html templates=admin/screen_template_unavailable.html, public/patient_week.html, public/unavailable.html
- `GET /patienten/wochenplan/ohne-bilder/` `public.patient_week_without_images` blueprint=public class=html templates=admin/screen_template_unavailable.html, public/patient_week.html, public/unavailable.html
- `GET /druck/cafeteria/woche` `public.print_cafeteria_week` blueprint=public class=html templates=public/print_cafeteria_week.html, public/unavailable.html
- `GET /druck/patienten/woche` `public.print_patient_week` blueprint=public class=html templates=public/print_patient_week.html, public/unavailable.html
- `GET /` `public.root` blueprint=public class=redirect templates=
- `GET /signage/cafeteria/tag` `signage.cafeteria_day` blueprint=signage class=html templates=signage/cafeteria_closed.html, signage/cafeteria_day.html, signage/unavailable.html
- `GET /signage/cafeteria/woche` `signage.cafeteria_week` blueprint=signage class=html templates=signage/cafeteria_week.html, signage/unavailable.html
- `GET /signage/patienten/tag` `signage.patient_day` blueprint=signage class=html templates=signage/patient_day.html, signage/unavailable.html
- `GET /signage/patienten/woche` `signage.patient_week` blueprint=signage class=html templates=signage/patient_week.html, signage/unavailable.html


### 4.4 Übrige Matrix-Routen

Keine Verwaltungsansicht und nicht §0: Anmeldung, API-Dokument, JSON, FHIR, Health, statische Branding-Dateien. `api_docs.docs` und `auth.local_login` / `auth.login` / `auth.callback` sind html und visuell, aber keine Dishboard-Verwaltungsliste.

- `GET /api/v1/published/cafeteria` `api.cafeteria` blueprint=api class=json visual=False
- `GET /api/v1/published/patienten` `api.patienten` blueprint=api class=json visual=False
- `GET /api/v1/docs` `api_docs.docs` blueprint=api_docs class=html visual=True
- `GET /api/v1/openapi.json` `api_docs.openapi_json` blueprint=api_docs class=json visual=False
- `GET /api/v1/keys/me` `api_v1.key_identity` blueprint=api_v1 class=json visual=False
- `GET /api/v1/published/<any(cafeteria, patienten):channel>` `api_v1.published_channel` blueprint=api_v1 class=json visual=False
- `GET /api/v1/published/<any(cafeteria, patienten):channel>/days/<date>` `api_v1.published_days` blueprint=api_v1 class=json visual=False
- `GET /api/v1/published/<any(cafeteria, patienten):channel>/today` `api_v1.published_today` blueprint=api_v1 class=json visual=False
- `GET /api/v1/status` `api_v1.status` blueprint=api_v1 class=json visual=False
- `GET /api/v1/weeks/<any(cafeteria, patienten):channel>` `api_v1.weeks` blueprint=api_v1 class=json visual=False
- `GET /api/v1/weeks/<any(cafeteria, patienten):channel>/<date>/preview` `api_v1.weeks_preview` blueprint=api_v1 class=json visual=False
- `GET /auth/callback` `auth.callback` blueprint=auth class=html visual=True
- `GET,POST /auth/frontchannel-logout` `auth.frontchannel_logout` blueprint=auth class=empty_response visual=False
- `GET,POST /auth/local` `auth.local_login` blueprint=auth class=html visual=True
- `GET /auth/login` `auth.login` blueprint=auth class=html visual=True
- `POST /auth/logout` `auth.logout` blueprint=auth class=redirect visual=False
- `GET /branding/logos/<sha256>.png` `branding.logo` blueprint=branding class=download visual=False
- `GET /branding/revisions/<int:revision>.css` `branding.stylesheet` blueprint=branding class=download visual=False
- `GET /fhir/Composition/<id>/$document` `fhir.document_composition` blueprint=fhir class=json visual=False
- `GET /fhir/metadata` `fhir.metadata` blueprint=fhir class=json visual=False
- `GET /fhir/Composition/<id>` `fhir.read_composition` blueprint=fhir class=json visual=False
- `GET /fhir/NutritionProduct/<id>` `fhir.read_nutrition_product` blueprint=fhir class=json visual=False
- `GET /fhir/Composition` `fhir.search_composition` blueprint=fhir class=json visual=False
- `GET /fhir/NutritionProduct` `fhir.search_nutrition_product` blueprint=fhir class=json visual=False
- `GET /health/live` `health.live` blueprint=health class=json visual=False
- `GET /health/ready` `health.ready` blueprint=health class=json visual=False
- `GET /static/<path:filename>` `static` blueprint= class=static visual=False


## 5. Weitere Zustände

Die Matrix führt an den Routen `default`, `empty` / `empty_or_unavailable`, `invalid`, `access_denied_401`, `access_denied_403`, `conflict_if_versioned` und einzelne Fachzustände (`source_conflict_409`, `legacy_without_active_revision_409`). Eigene Templates dafür:

- Leer: `empty_state(...)` in den Listen, unter anderem `grundlagen.html:76`, `rezepte.html:46-47`, `components.html:147-149`, `week_management.html:117`.
- Nicht verfügbar: `grundlagen_unavailable.html`, `local_user_unavailable.html`, `print_template_unavailable.html`, `screen_template_unavailable.html`.
- Konflikt: `grundlagen_location_conflict.html`, `rezepte_conflict.html`.
- Fehler: `recipe_template_error.html`.
- Archiv: Filter «Archivierte einschliessen» und Badges in `grundlagen.html`, `components.html`, `gerichtvorlagen.html`, `rezepte.html`, `kochbuch_editor.html`.
- Nur lesen: Zweige `can_write` / `can_mutate` ausgeblendet, zum Beispiel `grundlagen.html:73` (Öffnen statt Bearbeiten), `lager` ohne Buchungsformular, `local_user_create.html:8` mit Status Nur-Lesen.
- Dialoge: Veröffentlichungsdialog über `data-bs-target="#week-publish-modal"` in `_week_controls.html:63-65`. Bestätigen-vor-Löschen über `data-confirm` (API-Schlüssel `api.html:56`, manuelle Einkaufsposition `einkaufsliste.html:251`).
- Suche: `filter_bar_sem` in `gerichtvorlagen.html:63` und `kochbuecher.html`. Eigene Suchformulare in `components.html`, `grundlagen.html:50`, `rezepte.html:14`, `grundlagen_food.html:25`, `_course_recipe_search.html`.

`admin.recipe_view` listet in der Matrix zusätzlich `rezepte_scale.html`. Gerendert wird im Erfolg `rezepte_ansicht.html` (`recipe_routes.py:183`).

## 6. Sichtbare Zeilenaktionen über 2

Geprüft wurden alle Schleifen, deren Skriptobergrenze über 2 lag.

| Route | Sichtbar je Datensatzzeile | Befund |
|---|---|---|
| `admin.shopping_list_detail` | 3 | `einkaufsliste.html:245-251`: Speichern, Abhaken oder Wieder öffnen, Löschen. Alle drei ausserhalb von `<details>`. |
| `admin.vorlagen` | bis 4 | `vorlagen.html:97-103`: Editor, PDF-Prüfung und, wenn ein neuerer Entwurf neben der aktiven Version liegt, zwei weitere Links. Ohne diesen Zustand sind es zwei. |
| `admin.menu_get` | 2 | Überlauf und `hidden`, siehe §1. Herkunftszeile `:285` hat nur Löschen. |
| `admin.recipes_list` | 2 | Überlauf plus ein primärer Link. |
| `admin.week_management` | 2 | Öffnen plus `week-more`. |
| `admin.patienten`, `admin.cafeteria` | 1 je Gang- oder Kartenzeile | Summe der Tageszelle, nicht eine Zeile. |
| `admin.recipe_edit` | 1 | `_rezepte_fields.html:18-22` im `<details>`. |
| `admin.screens` | 2 | Öffnen plus Überlauf `:29-39`. |
| `admin.print_template_editor` | 2 | Versionszeile `:198-199`: Öffnen und Wiederherstellen. |

## 7. Fachliche Schutzstellen (§8.4)

Diese Texte bleiben. Zeilen gegen den aktuellen Quelltext geprüft:

- Allergenangaben nicht erfasst: `_week_menu_card.html:37`, `menu_editor.html:19` und `:389`.
- Allergenprüfung offen: `_week_menu_card.html:39`. Gebündelt im Wochenkopf `_week_controls.html:51`.
- Kein Bestand erfasst: `lager.html:41`.
- Entwurf / nicht gespeichert: `rezepte_editor.html:28`, `_week_service.html:38`.
- Zutat: fehlende Angabe ist nicht «frei von» (`grundlagen_food.html:135`). Leere Preisliste ist nicht 0 (`grundlagen_food.html:101`).

## 8. Mikropakete WP3–WP5

Höchstens drei Templates je Paket. Dateien überschneiden sich nicht. Gemeinsame Makros und das Gerüst (`_macros.html`, `base_tabler.html`, `_workflow_sidebar.html`, `_area_tabs.html`, `_country_select.html`) gehören zur Basis vor WP3 und werden hier nicht ein zweites Mal vergeben. `_country_select.html` importieren Bausteine und der Menü-Editor. `_local_user_forms.html` importieren Liste, Editor und Neuanlage. Diese eine Partial-Datei liegt im ersten Benutzerpaket. Die Seitenpakete danach ändern sie nicht.

Pilot zuerst, Bausteine und Rezepte.

| Paket | Templates |
|---|---|
| WP3-1 | `components.html`, `component_editor.html` |
| WP3-2 | `rezepte.html` |
| WP3-3 | `rezepte_editor.html`, `_rezepte_fields.html`, `rezepte_conflict.html` |
| WP4-1 | `grundlagen.html`, `grundlagen_food.html`, `grundlagen_unit.html` |
| WP4-2 | `grundlagen_vocabulary.html`, `grundlagen_location_conflict.html`, `grundlagen_unavailable.html` |
| WP4-3 | `gerichtvorlagen.html`, `gerichtvorlage_einplanen.html` |
| WP4-4 | `menu_collection.html`, `menu_editor.html` |
| WP4-5 | `lager.html` |
| WP4-6 | `kochbuecher.html`, `kochbuch_editor.html` |
| WP4-7 | `einkaufslisten.html`, `einkaufsliste.html` |
| WP4-8 | `bestellung.html`, `bestellung_korb.html` |
| WP4-9 | `kalkulation.html` |
| WP4-10 | `_local_user_forms.html`, `local_user_unavailable.html` |
| WP4-11 | `local_users.html` |
| WP4-12 | `local_user_editor.html`, `local_user_create.html` |
| WP4-13 | `local_user_events.html`, `access_history.html` |
| WP4-14 | `api.html` |
| WP4-15 | `screens.html`, `screen_template_assignment.html`, `screen_template_unavailable.html` |
| WP4-16 | `vorlagen.html` |
| WP4-17 | `print_template_editor.html`, `print_template_unavailable.html`, `_recipe_template_selection.html` |
| WP4-18 | `recipe_template_error.html` |
| WP4-19 | `rezepte_ansicht.html`, `rezepte_revision.html`, `_recipe_document.html` |
| WP4-20 | `rezepte_revisionen.html`, `rezepte_scale.html`, `rezepte_images.html` |
| WP4-21 | `rezepte_import.html` |
| WP4-22 | `branding_editor.html`, `branding_preview.html` |
| WP4-23 | `display_settings.html`, `operations.html` |
| WP4-24 | `copy.html`, `import_preview.html` |
| WP5-1 | `_week_controls.html`, `_week_settings.html`, `_week_menu_card.html` |
| WP5-2 | `_course_line.html`, `_course_editor.html`, `_course_recipe_search.html` |
| WP5-3 | `_week_service.html`, `_service_courses.html` |
| WP5-4 | `patienten.html` |
| WP5-5 | `cafeteria.html` |
| WP5-6 | `kuechenkalender.html`, `kuechenkalender_anlass.html` |
| WP5-7 | `week_management.html`, `week_review.html` |
| WP5-8 | `preview.html` |

WP5-1 bis WP5-3 vor den Seiten `patienten.html` und `cafeteria.html`, sonst bearbeiten zwei Pakete dieselben Partials. `_service_courses.html` hängt an `preview.html` und am Wochenraster. Es liegt nur in WP5-3.

## 9. Offene Punkte

- Keine gerenderte Prüfung. Alias `ui_label(` und Makro `form_footer` sind in den Dateizahlen nicht als `label(` oder `<button` enthalten. Die Summen in §3 berücksichtigen `form_footer` für die beiden Anlass-Routen ausdrücklich.
- `zeilenaktionen max` in der Tabelle ist die Schleifenobergrenze, nicht die sichtbare Zeile. Massgeblich ist §6.
- Screen-Vorlagenvorschau: Matrix-Pfade und Quell-Renderpfad stimmen nicht überein (§1 Punkt 7).
