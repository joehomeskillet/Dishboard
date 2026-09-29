# UI-Konsistenzinventar — Migrationsliste P4/P5

## Abschlussstand Icon-first-Migration (H18, korrigiert durch H18b)

Quellenstand: 2026-09-29, Dokumentkorrektur auf `21bfc4cb`. Die unten genannten
`reports/`- und `audit/`-Pfade liegen unter
`/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18/.claude/state/claude-session-2026-09-29/`.
Testpfade sind relativ zu `reference_scaffold/`. Die Tabelle nennt tatsächlich
ausgeführte Tests aus den jeweiligen Reports, keine neuen H18b-Produktläufe und
keine pauschale Freigabe: rote Zwischenläufe, Reviewblocker und Grenzen bleiben
in den Quellen erhalten. `<family>` steht für `cafeteria` oder `patienten`.

### Migrierte Ansichten (Route, Muster, tatsächliche Tests)

| Ansicht / Route | Muster, Rolle und Zustand | Tatsächliche Tests / Quelle |
|---|---|---|
| Bausteine: `/admin/<family>/komponenten` | DEC-2/D3: Namen als Text; Editor-Einstieg über Bearbeiten-Icon, archivierte Einträge über Öffnen. Beide Profile, vorhandene Rollen, JS/No-JS. | `tests/test_component_catalog_browser.py`, `tests/test_icon_pilot_density_browser.py`; `reports/D3-report.md`, Abschnitt „Änderung und Abdeckung“. |
| Zutaten: `/admin/grundlagen` und `/admin/grundlagen/<kind>/<public_id>` | DEC-2/D3: Namen als Text, Symbolaktion als Zugang; ohne Schreibrecht Öffnen, Statusaktionen nur mit Recht. Fünf Stammdatenarten, aktiv/archiviert. | `tests/test_master_data_browser.py`; `reports/D3-report.md`, Abschnitt „Änderung und Abdeckung“. |
| Menüsammlung: `/admin/<family>/menues` | DEC-2/D3: Textnamen und Bearbeiten-/Öffnen-Aktion, Liste und vorhandene Kartenansicht; Admin/Editor/Publisher, aktiv/archiviert. | `tests/test_menu_collection_browser.py`; `reports/D3-report.md`. Folgeanpassungen: `tests/test_ui_korrektur_menus_browser.py`, `reports/R10-report.md`. |
| Gerichtvorlagen: `/admin/gerichtvorlagen` | D4: wirksame Titelsuche, Archivfilter, Zurücksetzen und Paginierung mit erhaltenem `q`; Enter mit/ohne JS. | `tests/test_dish_template_browser.py`, `tests/test_dish_template_routes.py`, `tests/test_recipe_link_reads_db.py`; `reports/D4-report.md`, Abschnitte „Gerichtvorlagen-Browser komplett“ und „Routen-/Store-Regressionen“. |
| Kochbücher: `/admin/kochbuecher` | D5: normale aktive Liste ohne redundantes Aktiv-Badge/Strich; bei `archived=1` Aktiv und Archiviert unterscheidbar. D13b: Bearbeiten für aktive schreibbare Bücher, sonst Öffnen; Leseansicht bei Bedarf im Überlauf. | `tests/test_cookbooks_browser.py`, `tests/test_ui_korrektur_cookbooks_browser.py`, `tests/test_cookbook_routes.py`; `reports/D5-report.md`, `reports/D13-report.md`, Abschnitt „D13b — Korrigierter Auftrag“. |
| Kochbuch-Leseansicht: `/admin/kochbuecher/<cookbook_id>/ansicht` | D13b/DEC-1: GET mit `draft.read`, geordnete Rezeptansichtslinks; Bearbeiten nur mit Recht. Writer/Reader/Archiv, JS/No-JS, Desktop/mobile fine/coarse. | `tests/test_icon_cookbook_view_browser.py`, `tests/test_ui_route_inventory.py`; `reports/D13-report.md`, Abschnitte „Endgültige Änderung“ und „Ergebnisübersicht“. |
| Wochenplan: `/admin/cafeteria`, `/admin/patienten` | D7: Publish-Controls nur mit `publication.publish`, serverseitige Sperren bleiben erhalten (D6). D19: Titel/Kontext → gebündelte Prüfhinweise → weitere Hinweise/Raster. M45/M64: 36 px fine / mindestens 44 px coarse. | `tests/test_icon_publish_controls_role_browser.py`, `tests/test_icon_publish_guards_browser.py`, `tests/test_week_check_header_browser.py`, `tests/test_ui_korrektur_week_browser.py`; `reports/D6-report.md`, `reports/D7-report.md`, `reports/D19-report.md`. |
| Rezepte: `/admin/rezepte` | D14: tatsächlich leere Zellen gestapelter Tabellen ohne Pseudolabel und Platzbedarf; gemischte Zustände bleiben sichtbar, Desktop-Tabelle bleibt erhalten. 390/1440 px, fine/coarse. | `tests/test_icon_stack_empty_labels_browser.py`, `tests/test_recipe_density_browser.py`, `tests/test_ui_korrektur_recipes_browser.py`; `reports/D14-report.md`, Abschnitt „Änderung und Abnahme“. |
| Rezepteditor: `/admin/rezepte/neu`, `/admin/rezepte/<recipe_id>` | D15: Ausbeuteeinheit bei 360/390 px nicht abgeschnitten; bestehendes Desktop-Grid erhalten. | `tests/test_icon_recipe_editor_browser.py`, `tests/test_recipe_browser.py`; `reports/D15-report.md`. |
| Menüeditor: `/admin/<family>/menu` | D8/D16: ungespeicherte Änderungen geschützt; Abbrechen aus Sammlung übernimmt gültige Suche/Seite. Wochenlink/Breadcrumb bleiben bei der Woche; nach POST bzw. 400/409-Rerender Wochen-Fallback. Beide Profile, JS/No-JS. | `tests/test_icon_menu_unsaved_changes_browser.py`, `tests/test_menu_collection_browser.py`, `tests/test_admin_menu_editor_browser.py`; `reports/D8-report.md`, `reports/D16-report.md`, Abschnitt „Vertrag und Umfang“. Formularvergleich: `reports/R9-report.md`. |
| Einkaufslisten: `/admin/einkaufslisten` | D17: datensatzbezogener Überlaufname in allen vier Zustands-/Rechtezweigen. | `tests/test_shopping_list_browser.py`, `tests/test_ui_list_family_browser.py`; `reports/D17-report.md`, Abschnitte „Änderungen und Dateibesitz“ / „Testresultat“. |
| Bildschirme: `/admin/screens` | D17: Überlaufname mit Bereich und Kanal. | `tests/test_screen_template_browser.py`, `tests/test_ui_korrektur_screens_browser.py`; `reports/D17-report.md`. |
| Rezeptstände: `/admin/rezepte/<recipe_id>/revisionen` | D17: Überlaufname mit lesbarer Standnummer. | `tests/test_recipe_revision_routes.py`, `tests/test_ui_list_family_browser.py`; `reports/D17-report.md`. |
| Vorlagen: `/admin/vorlagen` | D17: Überlaufname mit tatsächlichem Vorlagen-/Bereichsnamen; Hauptaktion plus Überlauf. | `tests/test_admin_template_catalog_browser.py`, `tests/test_ui_korrektur_vorlagen_browser.py`; `reports/D17-report.md`. |
| Wochenverwaltung: `/admin/<family>/wochen` | D17: Überlaufname „Woche ab …“ mit Datensatzbezug. | `tests/test_week_management_browser.py`, `tests/test_admin_week_tabler_browser.py`; `reports/D17-report.md`. |
| Bestätigungen: `/admin/einkaufslisten`, `/admin/einkaufslisten/<public_id>`, `/admin/gerichtvorlagen/<public_id>` | R3: `admin.js` beachtet `data-confirm` am Submitter; Löschen/Archivieren ausführen oder abbrechen, native Formulardaten/CSRF/CAS erhalten. | `tests/test_icon_confirm_submitter_browser.py`, `tests/test_shopping_list_browser.py`, `tests/test_dish_template_browser.py`; `reports/R3-report.md`, Abschnitte „Ergebnis und Blocker“ / „Roh-Ausgaben der Browsergates“. |

Routenabgleich: `reference_scaffold/cafeteria/admin/` mit `workflow_routes.py`,
`master_data_routes.py`, `menu_collection_routes.py`, `dish_template_routes.py`,
`cookbook_routes.py` (registrierte GET-Regeln), `recipe_routes.py`,
`recipe_revision_routes.py`, `shopping_list_routes.py`, `output_routes.py` und
`week_management_routes.py`.

### Bekannte Ausnahmen

- **Kalender** bleibt Planungsansicht nach Spec §4.3/§14. Tagestitel plus Planen
  bleiben erhalten; UI-23/24-Dichteziele normaler Listen gelten hier nicht.
  Quelle: `reports/D17-report.md`, Abschnitt „Änderungen und Dateibesitz“.
- **Swagger UI (`/api/v1/docs`)** ist eine Fremdkomponente ausserhalb der
  Icon-first-Adminoberfläche. Unbenannte Buttons bleiben als bekannte A11y-Lücke
  dokumentiert. Quelle: `audit/D10b/classification.md`, Zeile „Fremdkomponente“.
- **Fragmentrouten `/admin/<family>/header` und `/admin/<family>/service`**
  liefern per GET Formularzustand (CSRF-Hidden und Datenspans), keine eigene
  Nutzeransicht; deshalb kein `h1`. Quelle: `workflow_routes.py`, `header_get`
  und `service_get`; `audit/D10b/classification.md`, Zeilen „kein View“.

### Offene Punkte und Grenzen der Abnahme

- **Gesamtabnahme offen.** `audit/closure-matrix.json` (`generated_at` 12:25,
  Basis `8e56bf7`, Abschnitte `criteria`/`overall`) führt 2 PASS, 25 PARTIAL und
  1 OPEN. Das ist ein früherer Stand: spätere Nachweise, darunter D9b, D10b,
  D16 und D18, ergänzen einzelne Kriterien; eine neu konsolidierte Freigabe ist
  daraus nicht ableitbar.
- **Interaktionsbreite offen:** Tastatur über alle Ansichten (UI-07),
  Tooltip/Escape je Ansicht/Rolle/Locale (UI-08), Touch über weitere Ansichten
  (UI-09), Abbruchpfade Rezept/Kochbuch/Vorwochenkopie (UI-15), weitere
  Leer-/Fehler-/Langtextzustände (UI-20), echter 200-%-Zoom weiterer Ansichten
  (UI-22) sowie Navigation über alle Ansichten (UI-27). Quelle:
  `audit/closure-matrix.json`, jeweilige `criteria`-Einträge. Spätere Teilbelege
  ersetzen keine vollständige Abnahme; D13b nennt Zoom/Kontrast seiner neuen
  Leseansicht ausdrücklich als nicht belegt (`reports/D13-report.md`, „Sichtnachweis und Grenzen“).
- **Restvarianten offen:** kein vollständiger Consumer-Nachweis für weitere
  lokale Varianten, kein pauschaler Löschauftrag. Quelle:
  `audit/closure-matrix.json`, `criteria.UI-26`.
- **Messbasis ergänzt, Abnahme begrenzt:** `audit/D10b/classification.md` belegt
  402 Captures in vier Pflichtviewports, keinen horizontalen Überlauf und nach
  Klassifizierung keine Adminview-Verstösse aus diesem Lauf. Das ersetzt keine
  Interaktions-/Accessibility-Abnahme; `reports/D10b-report.md` begrenzt die
  Namensmessung auf aria-label/aria-labelledby/Text und bewertet keine semantische
  Qualität/Lokalisierung. Die alten fehlenden Tablet-Zellen aus D10 sind damit
  kein aktueller Restpunkt.
- **UI-28 teilbelegt:** `audit/D18/pairs.md` liefert sieben vergleichbare Paare
  (`42c85fef` → `24100fee`, Admin, Standardfilter, 100 % Zoom, gleicher Seed).
  Pilotlisten enthalten je einen Datensatz; grosse Listen, weitere Rollen,
  Touch, geöffnete Menüs und 200-%-Zoom wurden nicht verglichen. Der frühere
  Matrixeintrag „kein Paar“ ist durch diese Teilbelege überholt.
- **Review-/Gate-Abnahme bleibt gesondert:** mehrere D-Reports melden fehlenden
  OCR-Nachweis. `reports/D19-report.md`, „Vorbestehendes Pflicht-Gate“, dokumentiert
  16 identische Basisfehler in `tests/test_admin_week_ui.py`. `reports/R11-report.md`,
  „Runs so far“, ist noch `IN_PROGRESS`; ein R12-Abschlussreport liegt beim
  H18b-Quellenabgleich nicht vor. Aktueller Abschluss dieser beiden Folgepakete
  daher offen; keine Behauptung eines neuen Produktfehlers.

---

## Historische Reports (vor H18-Abschluss)

## Kalender: Heute, Fokus und nativer Überlauf — 2026-09-28, 15:02 CEST

Zwei ergänzte UI19-Fälle prüfen JS mit Fine-Pointer bei1440/390px. Sechs echte
DB-Titel am belegten Tag erzeugen +3 Überlauf. Heute ist fest2026-09-02;
Tastaturfokus auf3.September ist davon getrennt. Die bestehende API besitzt
keinen ausgewählten Tag: Fokus wird ausdrücklich nicht als Auswahl gewertet.
Monat und Profil bleiben unabhängige Zustände. Desktop zeigt den gedämpften
31.August; Mobil prüft dessen echte Vormonatsnavigation und Heute-Rückkehr,
weil die mobile Liste absichtlich nur Tage innerhalb des Monats zeigt.

Native Tastaturbedienung öffnet den Überlauf und folgt einem Eintrag per GET
zum Patientenmenü; Pfad/Query/200 und keine POSTs werden geprüft. Zwei erste
Läufe scheiterten allein am Vergleich des whitespacebehafteten rohen href
mit der normalisierten Browser-URL. Ein anderer Autor korrigierte nur diese
Oracle auf a.href; sämtliche Pfad-/Query-/Zustandsprüfungen bleiben erhalten.
Autor:2 bestanden in12.05s, komplette Datei11 in50.61s. Root:11 bestanden
in53.42s. Root sah eigene Desktop-Heute/Fokus- und mobile Überlaufaufnahme;
Review `/tmp/wp-629944221b32.md` ist CLEAN im genannten Umfang.

Eine bestehende Testdatei übernommen, Bestand jetzt54; ursprünglicher
341-Zeilen-Präfix exakt erhalten. Alle54 Quellhashes und19 geschützte
Git-Metadaten nach Übernahme geprüft. Kombinierter Root-Lauf:2 bestanden
in12.33s, Outer-/Gate-Exit0. Belege `/tmp/calendar-state-{full,combined}-root-0928.{log,xml}`,
Receipt `/tmp/wp-6e63b3f0fab4-receipt.json`. Keine Produktänderung,
kein Touch-/NoJS-/Zoom- oder globaler UI19-Abnahmeanspruch, kein Commit/Deploy.

## Lokalisierte primäre Rezeptaktionen — 2026-09-28, 14:47 CEST

Die Rezeptliste übergibt den Rezepttitel nun mit dem vorhandenen object-
Vertrag an Bearbeiten/Öffnen. Zwei hart codierte deutsche Namensüberschreibungen
entfallen; Rollen-/Aktivbedingungen, Icons und native Ziel-URLs bleiben gleich.
Damit heißen die Hauptaktionen bei EN Edit/Open, bei DE bearbeiten/öffnen.
Dies lokalisiert ausdrücklich noch nicht die geöffneten Mehr-Menütexte.

Zwölf neue Fälle (DE/EN × aktiver Writer/Reader/archivierter Writer ×
JS1440fine oder NoJS390coarse) belegten vor dem Fix zweimal10FAIL/2PASS allein
an den falschen Namen. Eine vorherige ungültige Titel-Fixture wurde separat
durch einen anderen Autor korrigiert; deren12 Fehler waren kein Produkt-RED.
Autor12 bestanden in53.19s, unveränderte Navigation7 in60.05s.

Der Review fand mehrere Tooltips in einer Autorenaufnahme. Ein anderer Autor
ergänzte vor dem Screenshot die atomare exakte Einzeltooltip-/Textprüfung
sowie rohe Tooltipwerte vor/nach Aufnahme. Alle vorhandenen Namen-, Rollen-,
SVG-,36/44px-,GET-,NoPOST- und Datenprüfungen bleiben erhalten. Root12 bestanden
in56.78s;24 Zustände aus12 eindeutigen Fällen haben stabile Tooltip-/Pointer-
Werte. JS-Hauptaktionen zeigen je genau den passenden Tooltip, NoJS keinen.
Root und Reviewer sahen das korrigierte EN-Archivbild und das mobile NoJS-Ziel.
Review `/tmp/wp-63691746f338.md` CLEAN im beschriebenen Umfang.

Zwei Dateien übernommen, Bestand jetzt53; alle53 Quellhashes und19 geschützte
Git-Metadaten nach Übernahme geprüft. Root wiederholte die zwölf Fälle auf dem
gemeinsamen Stand:12 bestanden in54.39s, Outer-/Gate-Exit0, keine Fehler/Skips.
Receipt `/tmp/wp-878fa72fe89f-receipt.json`, Belege
`/tmp/recipe-locale-{settled,combined}-root-0928.{log,xml}`. Keine Änderungen
an Backend/Berechtigungen, kein Commit oder Deploy. Neue Tests untracked,
daher außerhalb des nur getrackte Dateien erfassenden Paketmanifests.

## Echter Menüeditorzoom mit stabilen Aufnahmen — 2026-09-28, 14:34 CEST

Vier neue Fälle prüfen beide Profile mit und ohne JavaScript bei echtem200%-
Chromium-Browserzoom. Set/GetDefaultZoom2 und App-CDPzoom2 werden bestätigt,
Root/Body CSSzoom1 und transformnone sowie720px innen/1440px außen/DPR2 geprüft.
Die unbeschnittene CDP-Viewportaufnahme verändert Geometrie/Scroll/Pointer nicht;
36 eindeutige Messzustände belegen diese Gleichheit. Dies ist Fine-Pointer-
Abdeckung, keine Touch- oder künstliche DPR-Zoombehauptung.

Jeder Fall durchläuft tatsächlichen400 mit erhaltenen Formularwerten,
Speichern303, Speichern-und-zurück303 und sauberes Abbrechen ohne POST.
Mehrfachfelder, CSRF/CAS, gespeicherte Versionen und native Tab-/Enter-
Bedienbarkeit bleiben streng geprüft. Kein neuer Dirty-Abbruch-/409-/EN-
Nachweis; die bisherigen720px-Reflowtests bleiben davon getrennt gültig.

Autor4 bestanden in34.52s, unabhängig Root4 in37.74s. Der Bildreview fand
überlagerte Tooltips in einer Aufnahme. Ein anderer Autor ergänzte Pointer-
Abstand und atomare exakte Tooltiptext-/Anzahlprüfung nach Tastaturfokus.
Ein zwischenzeitlicher getrennter Count-/Textcheck zeigte einen Assertion-
Übergang (1FAIL/3PASS, identischer Retry4PASS), keinen bewiesenen Produktfehler.
Finale vier Fälle bestanden in36.39s, Outer-/Gate-Exit0, ohne Fehler/Skips;
alle JS-Footeraufnahmen enthalten genau den Zieltooltip, NoJS keine Tooltips.
Root und Reviewer sahen das korrigierte Footerbild, außerdem NoJS400.

Review `/tmp/wp-fc796f792d70.md` CLEAN im Vierfallumfang; Capturekorrektur
`/tmp/wp-2eb64dc57741.md`, finale Belege
`/tmp/menu-native-zoom-atomic-root-0928.{log,xml}`. Neue Testdatei übernommen,
Quellbestand jetzt51 mit geprüften SHA-Werten;19 Git-Metadaten unverändert.
Receipt `/tmp/wp-2ee561fba01d-receipt.json`. Der Vierfalllauf gegen den
gemeinsamen Stand bestand in38.11s, Outer-/Gate-Exit0, ohne Fehler/Skips:
`/tmp/menu-native-zoom-combined-root-0928.{log,xml}`. Kein neuer Produktcode/Deploy.
Die neue Datei ist untracked und deshalb nicht im getrackten Paketmanifest.

## Eingereichte Kurswerte bei Konflikten — 2026-09-28, 14:17 CEST

Das passende Gängeformular erhält nach fehlgeschlagenem Speichern die
eingereichten IDs, Versionen, Zustände und Rezeptauswahlen zurück. Leere Werte
und Version0 bleiben erhalten; andere Tage, Mahlzeiten und Formulararten
verwenden weiterhin ihren gespeicherten Stand. Fehlt eine eingereichte Auswahl
in den tatsächlich angebotenen und gebundenen Rezepten, hält eine escaped,
neutrale Option „Eingereichte Auswahl“ ihren Wert. Sie behauptet weder einen
Rezepttitel noch eine gültige oder autorisierte Bindung; Serverprüfungen bleiben.

Ein echter409 verlor zuvor zweimal genau die Dessertauswahl außerhalb der
50 Treffer bei ansonsten27 gleichen Formularfeldern. Nach der Korrektur
bestanden Autor13 HTML und13 Browser. Root wiederholte beide vollständigen
Dateien unabhängig:26 bestanden in440.27s, Outer-/Gate-Exit0, keine Fehler/Skips.
Sechs native Abläufe decken Cafeteria Mittag und Patienten Mittag/Abend,
jeweils JS1440/fine und NoJS390/coarse, vier303 und einen409, vollständige
28-Feld-Nutzdaten, CSRF/CAS, echte Speicherung und unveränderte Nachbarn ab.
Der neue echte Outside-Page-Konflikt ist Cafeteria/JS/Dessert; alle sechs
Selects, Escaping, Empty/0 und Zielisolation ergänzend per SSR geprüft.
Dies erweitert den Nachweis nicht pauschal auf echte400-/Inactive-Ausnahmen.

NoJS aktiviert denselben Link per Fokus und Enter, mit sichtbarem Fokus,
Viewportprüfung und44px-Controls. Das ist keine Tap-/Scroll-API-Abnahme;
die frühere detached-element-Diagnose bleibt ohne bewiesene Produktursache.
Root sah zwei eigene Desktop-/NoJS-Aufnahmen, der Reviewer zwei Autorbilder.
Review `/tmp/wp-a84a74f6bb6c.md` CLEAN im beschriebenen Umfang.

Drei Quelldateien gezielt übernommen, Bestand jetzt50; alle50 Quellhashes
und19 Git-Metadaten nach Übernahme geprüft. Receipt
`/tmp/wp-1e4afa25a9e0-receipt.json`, unabhängiges Gate
`/tmp/course-retention-full-root-0928.{log,xml}`. Die sechs neuen Browserfälle
bestanden zusätzlich im gemeinsamen50-Dateien-Stand in301.08s, Outer-/Gate-
Exit0, ohne Fehler/Skips: `/tmp/course-retention-combined-root-0928.{log,xml}`.
Keine Änderung an Backend, Datenbank oder Berechtigungen. Kein neuer Commit
oder Deploy; der14:07-Stundenzug war mangels neuer Commits erneut NOOP.

## Herkunftsaktionen und Tooltip-Lebenszyklus — 2026-09-28, 14:03 CEST

Der Menüeditor zeigt pro Herkunftszeile nur die gemeinsame Mehr-Aktion.
Löschen samt Folgehinweis steht im geöffneten nativen Überlaufmenü (§5.4).
Automatische Herkunft bleibt gesperrt; die Löschung wird weiterhin erst mit
dem nativen Speichern persistiert. Ohne JavaScript bleibt der vorhandene
Weg über zwei leere Herkunftsfelder und Speichern erhalten. Der type=button-
Löschknopf erhält dadurch keine neue No-JS-Funktion.

Beim Entfernen einer Zeile entsorgt admin.js deren registrierte Tooltip-
Instanzen vor row.remove() und entfernt genau diese Controls aus dem Set.
Dies behebt den zweimal über fünf Sekunden nachgewiesenen doppelten Tooltip
nach Klonen und Entfernen. Das Leeren der letzten Zeile bleibt unverändert.
Die Tastaturaufnahme setzt vor dem Fokuszyklus den Mauszeiger ausserhalb
der Controls; exakte Fokus-, Namens- und Tooltip-Eindeutigkeit bleibt geprüft.

Unabhängig bestanden auf den anschließend übernommenen identischen Quellen
56 Tests in196.20s: Admin20, Escape16, Readonly8, echtes CSP4 und Herkunft8.
Outer-/Gate-Exit0, keine Fehler oder Skips. Autorprüfung49 Ausführungen grün;
der einzelne Regressionstest ist zusätzlich in dessen Admin20 enthalten.
Root sah zwei eigene Herkunftsbilder, Peer die Vorher-/Nachheraufnahmen.
Die acht Readonly-PNGs entstanden in einem zuvor nicht vorhandenen Verzeichnis;
keine fremden Baselines wurden ersetzt. Dies ist keine appweite Sichtabnahme.

Gemeinsamer Quellstand jetzt47 Dateien mit geprüften SHA-Werten;19 Git-
Metadaten unverändert. Receipt `/tmp/wp-2ac1ebf9419e-receipt.json`, Root-Gate
`/tmp/tooltip-origin-full-root-0928.{log,xml}`, unabhängige Reviews
`/tmp/wp-e44f11e0ba99.md` und `/tmp/wp-c6d15f4f4bdf.md` CLEAN im belegten Umfang.
Kursfehlerkorrekturen und echter Menüeditorzoom bleiben separat und offen.
Neue Tests sind teils untracked; das Paketmanifest erfasst nur getrackte
Dateien. Kein neuer Commit/Deploy: Git-Metadaten sind hier schreibgeschützt.

## Native Ladeanzeige und einheitliche Speicheraktionen — 2026-09-28, 13:00 CEST

Die Wochenprüfung aktiviert jetzt mit einem `data-loading`-Attribut die
vorhandene gemeinsame Ladefunktion. Vier echte native Abläufe (Patienten390
coarse/Cafeteria1440 fine, jeweils303 und veralteter Stand409) scheiterten
zuvor zweimal ausschliesslich an der fehlenden Ladeanzeige. Nach dem Opt-in
bestanden unabhängig Root4 in12.03s, bestehende Wochenprüfung24 in59.09s
und nach Übernahme in den gemeinsamen Quellstand neue4 in12.06s.
Alle Exits0, keine Fehler/Skips; unabhängiger Review CLEAN.
CSRF/week/context_version, externer Submit, Prüfbeleg/Audit sowie die Trennung
von Menüprüfung und Veröffentlichung bleiben nachgewiesen erhalten.

Der Test beobachtet submit/MutationObserver/beforeunload passiv und nimmt
während des echten serverseitig gehaltenen POSTs ein Bild auf. Die strenge
Spinnerbegrenzung stammt aus aufgelöstem CSSOM am beforeunload-Snapshot,
nicht aus einer während der Navigation blockierenden CDP-DOM-Abfrage.
Kein BFCache-Nachweis; Konflikterholung über frischen GET. Kein unmittelbarer
DOM-Pointerread nach dem Busybild. Dies schliesst die konkrete Wochenprüfung,
keine pauschale appweite UI20-Abnahme. Belege `/tmp/wp-0c6e30a8df95.md`
und `/tmp/wp-week-loading-review-root-0928.md`; Root sah zwei eigene
Pendingbilder, Peer alle14 Aufnahmen.

Im Menüeditor wurde genau die lokale48px-Mindesthöhe der Primäraktion
entfernt. Speichern, Speichern und Rückkehr sowie Abbrechen nutzen die
gemeinsame36px-fine/44px-coarse-Geometrie. Autor21 bestanden in70.99s,
unabhängig Root21 in70.07s. Zwei überholte Primärhöhen-Assertions wurden
auf exakte Quadrate umgestellt. Die separate alte96px-Footerannahme
scheiterte zweimal; ein anderer Autor ersetzte sie durch tatsächliche
Begrenzung in beiden Achsen und gegenseitige Nichtüberlappung bei wrap.
Sticky-/Scroll-/Tastatur-/Formularprüfungen bleiben erhalten. Root volle20
bestanden in92.13s; unabhängiger Review CLEAN. Zwei eigene Root-Bilder
und vier Vorher-/Nachherpaare beim Autor wurden angesehen.

Gemeinsamer Quellstand damals46 Dateien mit geprüften SHA-Werten;19
Git-Metadaten unverändert. Die gemeinsame Menüprüfung41 bestand in163.79s
mit Exit0, ohne Fehler oder Skips. Vier Inventarprüfungen bestanden in0.83s.
Aktuelle Receipts `/tmp/wp-0c6e30a8df95-receipt.json` und
`/tmp/wp-bf8d5cbbfeef-receipt.json`. Neue Tests sind teils untracked und
damit nicht Teil des nur getrackte Dateien erfassenden Paketmanifests.
Kein Commit/Deploy; damals blieben Herkunft-Remove/Sicherheitskontext,
vollständige Gängematrix und echter Menüeditorzoom eigene offene Grenzen.

## Kontextnamen der Wochenaktionen geprüft — 2026-09-28, 12:25 CEST

Leere Wochen-Slots verwenden jetzt den lokalisierten Anlegen-Namen, belegte
Slots den Bearbeiten-Namen. Beide behalten Tag, Datum, Mahlzeit, Menüoption
und Gericht im zugänglichen Namen und Tooltip. Die Symbolaktion nutzt den
bestehenden `actions.*.object`-Vertrag; Ziel-URL, native GET-Navigation und
Formulare bleiben erhalten. Deutsch/Englisch, beide Profile, JS/No-JS,
390px mit echtem Touch und 1440px sind in den bestehenden20 Fällen geprüft.

Der erste Autor verwendete eine falsche Testgrammatik. Ein anderer Agent
korrigierte genau zwei Solltextzeilen: anschließend20 bestanden in77.60s,
unabhängig Root20 in82.03s. Nach gezielter Übernahme beider Dateien in den
gemeinsamen Quellstand nochmals20 bestanden in78.70s; sämtliche Exitcodes0,
keine Fehler oder Skips. Zwei eigene Root-Aufnahmen und acht Peer-Aufnahmen
wurden angesehen. Belege: `/tmp/dishboard-week-slot-{oracle-peer,oracle-root,combined-root}-0928.{log,xml}`,
Bericht `/tmp/wp-918bf8e58c72.md`, Quellreceipt gleicher WP mit Suffix `-receipt.json`.
Der gemeinsame Bestand bleibt43 Dateien; zwei Identitäten wurden ersetzt.
Git-Metadaten unverändert, kein neuer Commit oder Deploy.

Zusätzlicher Inventarlauf auf dem vorherigen43-Dateien-Stand:10 Tests bestanden
in137.44s,204 neue Aufnahmen mit geprüften Bild-Hashes und ohne aufgezeichneten
horizontalen Überlauf. Dies ist keine Sichtabnahme sämtlicher204 Bilder.
Nur sechs Aufnahmen nennen ihre Rolle ausdrücklich. Historische Commit-/Grok-
Metadaten des Originalmanifests sind keine aktuelle Ausführungszuordnung.
Getrennte Quellen-/Ausführungsbelege: `/tmp/wp-capture-provenance-root-0928.{json,md}`.
Der spätere Namensfix ist durch diesen älteren Aufnahmesatz nicht abgedeckt.

UI20 bleibt offen: Der echte Lade-Test blockiert beim Anhalten der Navigation
im Testaufbau. Produktverhalten ist dadurch noch nicht als fehlerhaft bewiesen.
Unabhängige Testreparatur läuft; keine globale Ladefunktion wurde geändert.

## Drei Statuspakete gemeinsam geprüft — 2026-09-28, 11:47 CEST

Die drei P2-Statusgruppen des mobilen Reviews sind jetzt im gemeinsamen
Integrationsquellstand enthalten: 43 Dateien mit exakt geprüften SHA-Werten.
Sechs gezielte Dateideltas, elf Original-/Quellsicherungen und sämtliche
19 Git-Metadaten sind geprüft. Kein neuer Commit oder Deploy.
Auf genau diesem Stand bestanden unabhängig67 Fälle: ganze Wochenprüfung24
in60.18s, Skalierung/Bildbrowser/Route/Unit39 in84.22s und neue Importzustände4
in20.99s. Alle Outer-/GATE-Exits0, keine Fehler/internen Fehler/Skips.
Belege: `/tmp/dishboard-status-combined-{week,scale,import}-0928.{log,xml}`.
Die ursprünglichen26 Importbrowserfälle wurden im Autorenstand geprüft,
auf dem gemeinsamen Stand hier nur die vier neuen vollständigen Abläufe.
Die folgenden Einzelpaketprüfungen bleiben zusätzliche Belege:

- Wochenprüfung, beide Profile, Admin, ungeprüft/geprüft, JS/No-JS,
  390px mit echtem Touch und 1440px: redundante Kopfkarte entfernt,
  normale Bestätigungsaktion nur Symbol; Audittext, Zeitpunkt, Akteur und
  Trennung von Menüprüfung/Veröffentlichung erhalten. Autor neue8/volle24;
  unabhängig Root volle24 bestanden in60.10s.
- Rezeptskalierung, Admin, Entwurf/feste Revision, gültige/ungültige Zielmenge,
  JS/No-JS, 390/1440px mit feinem Zeiger: beide redundanten Kopfkarten entfernt.
  Original/Ziel, Nur-Lesen, native GETs und Datenbestand unverändert.
  Autor neue4/Bildbrowser12/Route+Unit23; Root neue4+Bildbrowser12 in67.20s.
- Rezeptimport, Admin, Entwurf/signiert/geändert/übernommen/verworfen,
  JS/No-JS, 390px Touch/1440px: doppelte Stapel-/Signaturkarten entfernt;
  unabhängige Aussagen im Ergebnisabsatz, erste Vorschau und Fehlerkontext
  erhalten. Autor neue4/volle30; Root neue4 in23.85s. Root korrigierte zuvor
  ausschließlich die MultiDict-Testvorbereitung und sechs alte Statusselektoren.

Alle genannten Gates ohne Fehler/interne Fehler/Skips, beide Exit-Ebenen0.
Root sichtete sechs eigene aktuelle Aufnahmen. Belege und genaue Grenzen:
`/tmp/wp-e7ca1496efdc.md`; Einzelpakete `wp-59ef37538fcb`, `wp-b66addecf5f0`,
`wp-de71c7e7ecdd`. Der neue Skalierungstest belegt keinen Coarse-Pointer.
Kein neuer 41-Seitenlauf oder vollständiger UI01–28-Nachweis behauptet.
Die erste übergrosse Patchübertragung scheiterte zweimal ohne Dateimutation.
Getrennte vollständige Dateisicherungen und der kompakte30450-Byte-Patch sind
anschliessend nativ angewendet und vollständig SHA-geprüft worden. Receipt:
`/tmp/wp-e7ca1496efdc-receipt.json`; kein Reapply. Git bleibt schreibgeschützt.
Stundenläufe09:07/10:07/11:07 waren NOOP; live weiterhin
`4ded0a7a16` seit08:20:45CEST, frisch11:32 healthy/Login200 geprüft.

## Kandidaten und offene Nachweise — 2026-09-28, 10:55 CEST

Die 39 geprüften Quelldateien sind jetzt gemeinsam im Integrations-Worktree
vorbereitet. Nach dem ersten 36-Datei-Stand ergänzte Root acht gezielte Deltas:
fünf aktualisierte Identitäten und drei zusätzliche Pfade. Sechs Screen-Dateien
und sämtliche 19 geprüften Git-Metadaten blieben unverändert. SHA-Prüfung aller
39 Dateien: ohne Abweichung. Das ist kein abgeschlossener Git-Merge oder Deploy.
Speichern/Rückkehr besteht unabhängig 332 Tests: Browser21, Semantik258,
Menü32, vollständige Admin-UX19 und NoJS-Konflikt2. Neuer sekundärer Submit ist
symbolbasiert mit lokalisiertem Namen; FormData, CSRF, CAS, Rückkehr und
implizites Enter auf dem Hauptsubmit bleiben geprüft. Vorhandener Hauptsubmit
bleibt 48px hoch; die 36/44px-Aussage betrifft nur den geänderten Zweitsubmit.
Auf dem gemeinsamen 39-Datei-Stand bestanden zusätzlich zehn Freigabefälle
in60.79s: neuer vollständiger Korrektur-/Prüfpfad4 plus bestehende Publikation6.
Speichern, Prüfen und Veröffentlichen bleiben getrennt. Gesamtbeleg:
`/tmp/dishboard-source-cohort-root-0928.md` und dort benannte Rohlogs/JUnits.
Der gemeinsame Listenfamilienlauf bestand mit 6 Tests in 26.64s: 41 Ansichten,
1440×900 und 390×844, keine gemessenen Abweichungscodes. Belege:
`/tmp/dishboard-cohort-list-root-0928.xml` und `.log`; neue Aufnahmen, Messdaten
und Bericht unter `/tmp/dishboard-cohort-list-root-evidence-0928`.
Alle 85 ursprünglichen Bild-/Bericht-/Baselinepfade sind bytegenau wiederhergestellt.
Abgedeckt sind Admin, JavaScript und feiner Zeiger; weitere Rollen, Touch,
vollständige Seiten und Zustandskombinationen bleiben gesonderte Nachweise.
Desktopkontaktblatt und mobile Operations/API/Screen-Ansichten wurden von Root
gesichtet; zusätzlich wurden alle 41 mobilen Originale unabhängig einzeln
betrachtet. Das Mess-PASS ersetzt die verbleibenden visuellen Befunde nicht.
Finaler Review: `/tmp/wp-4d6ec1c04f50.md`, SHA-256
`2682cc7caea86dfbb6b9e30e285d3864f26674d0d49ac643bc273d41b5909044`.
Drei P2-Gruppen betreffen wiederholte Statuskarten in Importdetail,
Wochenprüfung und Rezeptskalierung. Formularabschnittstitel bleiben gemäß §5.4
lesbar; ihre Texte sind keine bestätigten Buttonverstöße. Ein offener Tooltip
begrenzt die Vorlagenaufnahme, ohne einen dauerhaften Produktfehler zu beweisen.
Live-Prüfung um 10:35 erneut gesund/Login200, kein ALERT; letzter Deploy 08:20:45.
Die folgenden älteren Kandidatenangaben bleiben als Einzelpaket-Nachweise erhalten.

Live bleibt der unten belegte Stand `4ded0a7a16ccd9e975e5263e3b99486b3e4326a8`
seit 08:20 CEST mit 2776 bestandenen Zugtests. Die folgenden Arbeitsstände sind
separat erhalten und noch nicht integriert; Git-Metadaten bleiben schreibgeschützt.
Eine weitere unabhängige Prüfung gegen den vollständigen erwarteten SHA bestand:
`/tmp/dishboard-live-0920-root-0928.log`, Exit 0, healthy/Login 200, kein ALERT.
Die Kandidaten sind damit nicht live und nicht vollständig nach UI-01–28 abgenommen.
Der autonome 09:07-Zug bestätigte einen NOOP: Kandidat und Basis sind beide 4ded,
keine zusätzlichen Commits gegenüber GitHub. Beleg:
`/var/tmp/dishboard-release-train/20260928T070700Z-ZAp2L0/train.log`.
Letztes Deployment bleibt 08:20:45 CEST. Auch der 10:07-Zug war ein NOOP:
`/var/tmp/dishboard-release-train/20260928T080700Z-L5MCiM/train.log`.
Die erneute erwarteter-SHA-Prüfung um 10:08 bestätigte healthy/Login 200,
kein ALERT, keine zusätzlichen Commits (`/tmp/dishboard-live-1008-root-0928.log`).
Alle Worker-Testprozesse waren vor dem Zug beendet.
Die abschließende Integrationsliste `/tmp/wp-e8fc5210a82b.md` und `.json`
enthält 36 eindeutige finale Quelldateien: sechs bereits im begonnenen
Screen-Merge, 30 noch einzuspielen. Root verglich alle 72 Kandidat-/Zielstände
per SHA ohne Abweichung. Reihenfolge und Abhängigkeiten sind vorbereitet;
das ist kein gemeinsamer Release-Test oder Deploymentnachweis.
Die erneute Live-Prüfung um 09:47
bestand mit healthy/Login 200 (`/tmp/dishboard-live-0947-root-0928.log`).
HEAD und github/main des Integration-Worktrees sind direkt als derselbe volle
4ded-SHA geprüft; die main-relative Commitzahl des älteren Statusskripts ist
kein Nachweis zusätzlicher auslieferbarer Commits.

- Menüeditor, `wp-003d5880a2e5`: doppelte Tag-Infokarte entfernt; Datum,
  Mahlzeit, Menüoption, Profil und Warnung bei fehlenden Allergenangaben bleiben.
  Unabhängig bestanden Editor32 (104.41s), SaveBack5 (16.43s) und NoJS-Konflikt2
  (7.44s), jeweils GATE-/Prozess-Exit 0, keine Fehler oder Skips. Belege:
  `/tmp/dishboard-menu-day-root-0928.xml/.log`,
  `/tmp/dishboard-menu-day-saveback-root-0928.xml/.log` und
  `/tmp/dishboard-menu-day-conflict-root-0928.xml/.log`.
  Eigene Cafeteria-/Patientenbilder bei 390px und dichter Patientenfall bei
  1440px gesichtet. Zweidateien-Patch und Bericht `/tmp/wp-003d5880a2e5.*`.
  Weitere sichtbare Aktionstexte werden getrennt geprüft; kein Nachweis einer
  vollständig konformen Menüeditorseite, kein neuer Coarse- oder Zoomnachweis.
- Die aktuelle Matrix `/tmp/wp-f2fb60af27f7.md` ordnet UI-01–28 vorhandenen
  Belegen und Lücken zu. Zusammenhängende aktuelle 41-Seiten-/82-Bilder-Abnahme
  auf einem ausgelieferten SHA fehlt. UI-13, UI-20 und UI-26 bleiben offen.
  UI-23-Pilot ist bereits grün (207/212.30px); neun Kalenderfälle prüfen `+n`.
  Teilweise deutsche API-Aktionsnamen im englischen Kontext sind konkret offen.
- Operations-Hinweise: Notice-Paket
  `wp-321045080150` plus unabhängiger Reviewfix `wp-e13edb89b088` bestanden
  gezielte acht Fälle (38.21s), unabhängig 22 Fälle (85.08s) und final bei Root
  22 Fälle (87.05s), jeweils Prozess/GATE 0, keine Fehler/Skips. Vorherige Root-
  Prüfungen der 27 Routen und elf gemeinsamen Fehlerfälle bleiben separat belegt.
  Eigene Mobilbilder zeigten doppelte Feldlabels; zwei reproduzierende Läufe
  scheiterten genau daran. Ein enger Selektor korrigiert die bestehende lokale
  CSS-Regel. Aktuelle Bilder zeigen Beschriftungen einmal; Hinweisfeld, Werte,
  Fokus und 36/44px-Kontrollen bleiben erhalten. Finaler Drei-Dateien-Patch:
  `/tmp/wp-321045080150-reviewed.patch`; Root-Bericht `/tmp/wp-e13edb89b088.md`.
- API, `wp-a9b5ab01773d`: lokalisierte Widerrufnamen, Konsequenz und lesbare
  Bestätigung sowie kontextbezogene Detailsnamen. Vier Sprachschlüssel sind
  ausdrücklich in der weiterhin strikten Allowlist erfasst. Root bestand acht
  DE/EN-JS/NoJS-Touch/Feinzeigerfälle (33.01s) und zehn bestehende API-Fälle
  (22.50s); tatsächlicher POST 303, CSRF, Abbruch ohne POST und wörtliche
  Metazeichen im Namen belegt. Eigene EN-Bilder bei 390/1440px gesichtet.
  Die ganze Seite wird damit nicht als englisch übersetzt bezeichnet.
  Zwei alte Image-Upload-Textassertionen scheiterten zunächst zweimal bei sonst
  250 bestandenen Fällen. Separater unabhängiger Testfix `wp-2172c788bdd7`
  prüft stattdessen leeren Sichttext, exakten lokalisierten Namen/Tooltip und
  das Uploadsymbol. Ganze Semantikdatei danach bei Autor 252/252 (22.93s),
  unabhängig bei Root 252/252 (24.96s), jeweils Prozess/GATE 0 ohne Skips.
  Root-Beleg `/tmp/dishboard-api-image-semantics-root-0928.xml/.log`;
  keine Known-red-Erweiterung. API-Sieben-Dateien-Patch und separater
  Ein-Dateien-Testfix bleiben getrennt erhalten und müssen zusammen mit dem
  bereits geprüften Imagecalm-Stand integriert werden.

- Importvorschau, `wp-6095a60d482d`: `Vorschau speichern` nutzt nach Entfernen
  eines `show_text=true` das vorhandene Augensymbol. Zugänglicher Name und Tooltip,
  native Multipart-/CSRF-/Annotationsfelder, POST 303, Entwurf/Offen und lesbarer
  Sicherheitsdialog bleiben erhalten. Der eingefrorene Autorstand bestand alle
  24 bestehenden Fälle in 87.59s, GATE-/Prozess-Exit 0; Vorher/Nachher-Bilder bei
  1440/390px wurden gesichtet. Das belegt native Abläufe, Feinzeiger, Tastatur und
  den vorhandenen echten Browserzoom, keinen Coarse-Pointer. Belege:
  `/tmp/import-preview-icon-0928-after.xml/.log`, Bericht
  `/tmp/wp-6095a60d482d.md`. Zehn ursprüngliche Bilder wurden wiederhergestellt
  und per SHA geprüft. Child `wp-319877b9d6ac` ergänzte den exakten
  Vierdateien-Abgleich mit Shared-Stand 4ded und zwei zusätzliche Coarse-Fälle;
  die 24 bestehenden Fälle bleiben erhalten. Sein erster kombinierter Autorlauf
  ergab 43 bestandene und zwei fehlgeschlagene Fälle in 176.09s: Die beiden neuen
  Fälle erwarten nach erfolgreichem nativem POST 303 eine nicht gefundene
  Überschrift `Importstapel`. Der identische Retry endete mit denselben zwei
  Fehlern und 43 bestandenen Fällen in 177.10s; die ursprünglichen zehn Bilder
  wurden wiederhergestellt und ihre SHAs geprüft. Root korrigierte anschließend
  genau die Erwartung auf `name=f'Importstapel · {state}.json'`, weiterhin exakt
  (`wp-3f9f779a05d0`); unabhängige Peerprüfung ohne Befund. Root bestätigte
  anschließend zwei fokussierte Fälle in 8.22s und den vollständigen Lauf mit
  45 Fällen in 177.01s, jeweils GATE-/Prozess-Exit 0 und ohne Fehler oder Skips.
  Beide nativen Multipart-POSTs erzeugen nur Entwürfe; vorhandene Rezepte bleiben
  unverändert. 390px mit echtem Coarse-Pointer und maxTouchPoints=1 behält
  44×44px vor und nach Viewport-Aufnahmen, mit und ohne JavaScript.
  Root sichtete eigene JS-Initial-/Entwurfs- und No-JS-Entwurfsbilder. Die
  ursprünglichen 24 Fälle bleiben als 23.985 Bytes bytegleich erhalten.
  Belege: `/tmp/dishboard-import-{coarse,current}-reviewed-root-0928.xml/.log`;
  finaler Zweidateienpatch `/tmp/dishboard-import-preview-final-0928.patch`.
  Alle zehn Originalbilder sind erneut SHA-geprüft restauriert; neue Aufnahmen
  liegen separat unter `/tmp/dishboard-import-root-final-evidence-0928`.
- Wochenplan, Shared-Abgleich `wp-508d8009e174`: Autor 39 Fälle in 128.76s,
  unabhängig Root 39 in 132.11s, jeweils GATE-/Prozess-Exit 0 und ohne Fehler,
  interne Fehler oder Skips. Die Kombination umfasst elf Fehlerindikator-,
  20 Wochenkontext- und acht bestehende Formular-Rerender-Fälle. Alle vier
  übernommenen Dateien sind bytegleich zum Shared-Stand; SHA-Liste und
  abgegrenzter Abhängigkeitspatch stehen in `/tmp/wp-508d8009e174.md`.
  Root-Belege: `/tmp/dishboard-week-shared-root-0928.xml/.log`; 48 neue Bilder
  unter `/tmp/dishboard-week-shared-root-evidence-0928`, ursprüngliche 48
  wiederhergestellt und geprüft. Root sichtete `cafeteria-service-True-390x844`
  und `patienten-service-False-390x844`: Werte und Fehlermeldungen bleiben,
  mit JS ist der Fehlerindikator sichtbar. Dies ist eine Verbraucherprüfung,
  keine Abnahme sämtlicher Admin-Seiten. Der ursprüngliche Week-Dreidateienstand
  und seine Belege bleiben erhalten.
- Operations-Kopf/Detailaktion, `wp-3d847506cb68`: eingefrorener Kandidat im
  isolierten Worktree `menu-metadata-calm-0928`. Autor: acht neue Fälle in
  21.02s, sechs bestehende in 29.54s und 27 Routenfälle in 97.45s. Root bestätigte
  anschließend 52 kombinierte Fälle in 175.59s, GATE-/Prozess-Exit 0
  (elf Shared-, 14 Browser-, 27 Routenfälle):
  `/tmp/dishboard-operations-current-root-0928.xml/.log`. Root sichtete eigene
  390px-DE-No-JS-, 390px-EN-JS-geöffnet- und 1440px-DE-JS-Bilder. Acht JSON-Belege
  mit je zehn Zuständen prüfen echte 44px-Coarse-/36px-Fine-Kontrollen vor und
  nach Aufnahmen. Warnzahlen 5/14, Zeitzone und FormData bleiben erhalten;
  die redundante Bereichskarte entfällt. Drei Produktzeilen in zwei Dateien,
  keine CSS-Korrektur; ursprüngliche sechs Lifecycle-Fälle bytegleich. Dieser geprüfte
  Kandidat bleibt uncommitted und ist noch nicht live.
- Kochbucheditor, `wp-e5cfe2e726e8`, isolierter Print-Worktree: redundante
  Statuskarte entfernt, normaler Reaktivierungs-GET als Symbol. Aktiv-/Archivbadge,
  Rezeptzahl, Schreibschutz und lesbare Sicherheitsbestätigung bleiben erhalten.
  Root bestätigte zwölf UI-Fälle in 60.65s, zwölf bestehende Browserfälle in
  49.60s und 29 Routenfälle in 40.30s, jeweils ohne Fehler/Skips und Exit 0.
  Native Archivierungs-/Reaktivierungs-POSTs behalten genaue CSRF-, Kontext-,
  Versions- und Aktionsfelder; GET-Öffner erzeugen keine POSTs.
  Eigene 390px-No-JS-Archiv-, 390px-JS-Bestätigungs- und 1440px-JS-Archivbilder
  gesichtet. Diese neuen Fälle nutzen Tastatur/Feinzeiger, keinen Coarse-Pointer.
  Belege: `/tmp/dishboard-cookbook-{calm,existing,routes}-root-0928.xml/.log`.
  40 neue feste PNGs und vier JSONs liegen unter
  `/tmp/dishboard-cookbook-root-fixed-0928`; die ursprüngliche Abwesenheit ihres
  Worktree-Verzeichnisses ist wiederhergestellt. Alle fünf vorherigen Print-/
  Shared-Dateien sind SHA-identisch. Zweidateienpatch:
  `/tmp/dishboard-cookbook-own-e5cfe2e726e8.patch`, Root-Reverse-Prüfung Exit 0.
- Verbleibender statischer P2-Befund: Der Menüeditor wiederholt den bereits
  im Kontext genannten Tag. Paket `wp-003d5880a2e5` ist vorbereitet, noch nicht
  gestartet. Generische Mehr-Optionen-Öffner in Operations sind separat zu prüfen.
  Drucklinks der Vorschau gelten allein durch den bisherigen Quellbefund nicht
  als Regelverstoß. Der Auditbericht `/tmp/wp-b9fec9627d39.md` bleibt ein
  historischer Quellbefund und kein Browser- oder Gesamtabnahmenachweis.

## Release bestätigt — 2026-09-28, 08:21 CEST

Live ist `4ded0a7a16ccd9e975e5263e3b99486b3e4326a8` seit 08:20 CEST:
healthy, Login 200, identisch mit `github/main`. Zug 08:07 bestand 2776 Tests
ohne Fehler, interne Fehler oder Skips (A2016/B150/C599/D11), `NEW_FAILURES=0`
und alle vier Gate-Exits 0. Automatischer Push, Deployment und Abschluss waren
erfolgreich. Die neue Readiness-Prüfung wartete bei exakt dieser Revision auf
`health=starting`, danach lief die normale Liveprüfung erfolgreich. Damit ist
der zuvor offene unbeaufsichtigte Ablauf dieses Fixes tatsächlich belegt.

Root wiederholte die erwartete Revisionsprüfung unabhängig mit Exit 0:
`/tmp/dishboard-live-0821-root-0928.log`. Zugbelege:
`/var/tmp/dishboard-release-train/20260928T060702Z-FBbc6w`.
`last_success` enthält diese Revision, kein ALERT liegt vor und der temporäre
Release-Worktree wurde entfernt. Fehlerindikator und Readiness-Fix sind live;
die nachfolgenden Screen-/Bild-/Print-/Wochenkandidaten weiterhin nicht.

## Isolierte Verbraucherprüfung — 2026-09-28, 08:19 CEST

Die folgenden Nachweise gehören zu uncommitteten Kandidaten in separaten
Worktrees und sind keine Live-Abnahme:

- `/admin/rezepte/<id>/bilder`, Schreibrecht und archivierter Lesestand,
  JS/No-JS, 390/1440, DE/EN: Upload nur als Symbol; Entwurf/Archivstatus in
  der Kopfzeile erhalten, redundante Statuskarte entfernt. Root bestätigte
  acht erweiterte Fälle (47.87s) und zwölf bestehende Bildabläufe (48.73s),
  jeweils ohne Fehler/Skips; eigene mobile Upload-/Archivbilder gesichtet.
- Druckvorlageneditor aller drei Profile: Root bestätigte 31 bestehende
  Archivfälle (142.43s) und 29 Routenfälle (68.46s). Statische Antworten bleiben
  streng geprüft; einzig der zuvor erfolgreich geladene SVG-Sprite darf mit
  passenden ETag-Validatoren 304 liefern. Sichtbare Spriteglyphen werden auch
  ohne JavaScript geprüft; das Fehlericon nach ungültiger Bestätigung zusätzlich
  mit JavaScript. Fachliche Archiv-/CSRF-/CAS-Verträge
  bleiben erhalten. Die ergänzte Gesamtsuite bestand anschließend mit 36 Fällen
  (158.02s): ursprüngliche 30 plus sechs echte Touch-Fälle bei 390px für drei
  Profile mit/ohne JS. 36 Zustandsmessungen vor/nach Viewport-Aufnahmen liefern
  537 Symbolkontrollen mit exakt 44×44px und unverändertem Coarse-Pointer.
  Ungespeicherte Werte, FormData und CSRF-/Versionsfelder bleiben erhalten;
  zusätzliche POSTs finden nicht statt. Root sichtete eigene Profilbilder.
  Diese Touch-Aufnahmen belegen keine PDF-Darstellung ohne JavaScript.
- `/admin/cafeteria` und `/admin/patienten`, Admin mit aktiven und archivierten
  Menüvorlagen: 20 Root-Fälle bestanden in 74.07s. Der Symbolöffner nennt
  Tag/Datum/Mahlzeit/Option/Titel und nutzt übersetzte Aktionsgrammatik.
  Geöffnete Vorlagenlinks stehen in eigener Zeile ohne Textkompression;
  36/44px gelten vor und nach dem Öffnen. 16 Kontextläufe mit 348 Messpunkten
  behalten ihre Pointer-/Touch-Konfiguration. Eigene Desktop- und mobile
  JS-/No-JS-Bilder gesichtet. Zusätzlich bestanden 16 unveränderte Layout- und
  Erreichbarkeitsfälle (71.91s) sowie zehn Vorlagenbindungsfälle (35.52s),
  einschließlich archivierter Bezüge und nativer Konflikt-/Speicherabläufe.

JUnits liegen unter `/tmp/dishboard-image-{calm,existing-calm}-root-0928.xml`,
`/tmp/dishboard-print-{archive-validated,routes-restarted}-root-0928.xml` und
`/tmp/dishboard-print-coarse-final-root-0928.xml` sowie
`/tmp/dishboard-week-context-final-root-0928.xml` sowie
`/tmp/dishboard-week-existing-{layout,binding}-root-0928.xml`. Git-Metadaten bleiben
schreibgeschützt. Der abgeschlossene 08:07-Zug prüfte ausschließlich `4ded0a7a`;
diese drei Verbraucherpakete sind darin nicht enthalten.

## Bildschirm-Kandidat, noch nicht committed — 2026-09-28, 07:58 CEST

Screen-Kette `0e05edfa`, `4b7d63be`, `74048d60` liegt als geprüfter
Merge-Entwurf im Integrationsarbeitsbaum. Native logische Tabellenzeilen zeigen
Titel und Aktionen vor der aufklappbaren Vorschau; vier `tbody`-Gruppen tragen
je einen 1-px-Trenner und eindeutige Headerbezüge. Tatsächliche Vorlagenzuordnung
und gemischte Vorgabe-/Aktivzustände bleiben sichtbar; doppelte Statuskarten
und redundanter normaler Signage-Kontext entfallen.

Root prüfte den kombinierten Stand mit den aktuellen Tooltip-/Fehlerkorrekturen:
34 Fälle bestanden in 224.17s sowie die gesamte bestehende Screen-Suite mit
21 Fällen in 109.42s, jeweils GATE-/Prozess-Exit 0. Der neue Kontexttest prüft
jetzt ausdrücklich Escape1: Tooltip zu, Menü offen, Itemfokus; Escape2: Menü zu,
Summaryfokus ohne Ersatztooltip. Diese acht zusätzlichen Testzeilen beheben
eine veraltete Erwartung, die zweimal 12 Fehler/22 Passes erzeugte
(257.96/264.95s); Produktcode blieb dabei unverändert. Separater Peerreview CLEAN.
JUnits `/tmp/dishboard-screen-escape-reviewed-root-0928.xml` und
`/tmp/dishboard-screen-existing-current-root-0928.xml`.

Vorher bestanden auf Paketbasis bereits 34 Kontext-, sechs Listenfamilien-,
13 Preview- und 20 Vorlagenfälle. Die Contentbox-Messung berücksichtigt reale
Zeilenpadding-/Borderwerte; 1-px-Toleranz und 220-px-Mindestvorschau bleiben.
Root sichtete eigene mobile gemischte Zustände und echten 200-%-Browserzoom:
CDP zoom 2, CSS-Viewport 720×406.5, native PNG 1440×813. Vorhandene acht
ungetrackte Screen-Bilder wurden vor dem 21er in
`/tmp/dishboard-screen-consumer-originals-0754-0928` gesichert; keine Baseline
blind ersetzt oder als Gateerfolg verwendet.

Seit dem Sitzungswechsel sind Git-Metadaten schreibgeschützt. Deshalb bleibt
dieser Merge uncommitted; der Stundenzug kann nur HEAD `4ded0a7a` übernehmen.
Manifest und Templatequellhashes werden auch für den reviewbaren Arbeitsbaum
nachgeführt. Dies ist keine neue Live-Abnahme. Weitere Bild-/Druck-/Wochenpakete
bleiben in ihren isolierten Worktrees; die vollständige UI-01–28-Abnahme ist offen.

## Fehleranzeige an Symbolöffnern 2026-09-28, 07:28 CEST

`wp-3ba9cd7236a8`, `ca314632`: ungültige native Felder erhalten am
Symbol-Summary ein lokalisiertes Fehlericon statt überlaufendem sichtbarem
Fehlertext. Die bestehende Semantikregistrierung liefert Icon und Übersetzung;
ein eigenes eindeutiges Beschreibungsziel ergänzt vorhandene Hilfs-/Tooltip-IDs.
Bei gültigen Feldern verschwindet ausschließlich diese eigene Beschreibung.
Text-Summaries und native Fokus-/Validierungs-/Submitverträge bleiben erhalten.

Root prüfte 11 neue Fälle (24.38s), 16 unveränderte Tooltipfälle (18.50s)
und 30 Fälle im tatsächlichen Druckeditor aller drei Profile (132.54s).
Alle GATE-/Prozess-Exits 0. JS/No-JS, 390/1440, tatsächlicher Coarse-Pointer,
DE/EN/Fallback, Serverfehler und Beschreibung bei Hover sind berücksichtigt.
Eigenes mobiles Archivbestätigungsbild zeigt das rote Fehlericon innerhalb
des 36-px-Öffners; der vorherige vertikale Textüberlauf ist behoben.
JUnits `/var/tmp/dishboard-icon-error-root-0928.xml`,
`/var/tmp/dishboard-icon-error-tooltip-root-0928.xml` und
`/var/tmp/dishboard-print-error-root-0928.xml`. Die gemeinsamen drei Produktdateien
im Verbraucher sind SHA-identisch mit dem geprüften Error-Worktree.
OCR weiterhin ohne Ergebnis; neuer Worktree zweimal nicht indexiert,
Quellreview berücksichtigt den appweiten gemeinsamen Radius.
Diese Integration nimmt weder den noch isolierten Druckeditor noch die
gesamte UI-Matrix ab. Der 07:20-Livestand enthält diese Fehlerkorrektur noch nicht.

## Release und Bereitschaft 2026-09-28, 07:23 CEST

Live ist `d7a5eb63324324a007b8a5f3c7c380e534c97e59` seit 07:20 CEST:
healthy, Login 200, identisch mit `github/main`; erwartete Revision unabhängig
geprüft, Statuskommando Exit 0. Zug 07:07 bestand 2781 Tests ohne Fehler oder
Skips (A2016/B150/C599/D16), `NEW_FAILURES=0`. Push/Deploy liefen automatisch.
Die sofortige Liveprüfung sah erneut `health=starting` und endete mit Exit 1.
Nachprüfung und archivierter Originalalarm:
`/var/tmp/dishboard-release-train/20260928T050701Z-2nyGFw/recovery.md`.

Bereitschaftsfix `wp-7120ae692932`, `86036a44`: maximal 60 Sekunden auf
Docker-Health warten, ausschließlich bei passender Kandidatenrevision und
Zustand `starting`. Falsche Revision, ungesunder/fehlender Status oder
Inspect-Fehler bleiben Fehler; Deployment wird nicht wiederholt. Danach läuft
die unveränderte exakte Liveprüfung einmal. Autor und Root prüften unabhängig
alle 15 Readiness-/Status-Unitfälle (Root 7.356s, Exit 0), Bash/Ruff/Diff grün.
Integration erfolgt erst nach bestätigtem MainPID 0 des 07:07-Zuges, da dessen
ExecStart direkt dieses Integrationsskript verwendet. Unbeaufsichtigter Erfolg
mit dieser Korrektur muss im nächsten Zug noch nachgewiesen werden.

Einzelpakete weiter isoliert: gemeinsamer Fehlerindikator mit Root11,
Tooltip16 und echtem Druckeditor30 grün; eigenes mobiles Bestätigungsbild zeigt
das Fehlericon innerhalb des Öffners. Druckeditor-Altgates laufen noch.
Screen34 ist nach unabhängig geprüfter Contentbox-Messkorrektur grün
(228.23s); unveränderte 1-px-Toleranz, Mindestbreite und Formularverträge.
Listenfamilien-Ratchet läuft. Import/Bilder8 und vorhandener Importbrowser24
sind grün; weitere Bild-/Routengates stehen aus. Keine appweite UI-Abnahme.

## Release und Tooltip-Nachweis 2026-09-28, 06:53 CEST

Der wiederaufgenommene Zug prüfte `9873b033` vollständig: 4386 Fälle,
keine Fehler, acht Skips, alle 60 JUnit-Dateien terminal. Push/Deployment sind
angelaufen; eine neue Live-Abnahme steht noch aus. Log:
`/var/tmp/dishboard-release-train/20260928T040754Z-quWLVT`.
Der geplante Start 06:07 war zuvor am Manifest eines Zwischenstands gescheitert.
Integrationen werden deshalb ab jetzt ohne Zwischencommit zusammengeführt und
erst mit aktualisierten Hashes und geprüftem Manifest gemeinsam committed.

`40623846` korrigiert Escape an semantischen Öffnern: zuerst den eigenen Tooltip
schließen, danach den eigenen Bereich; Rückgabefokus erzeugt keinen Ersatztooltip.
Fremde Hover-Hilfe blockiert keine native oder Tabler-Modal-Abbrechhandlung.
Neuer Hover sowie bewusstes Wiederöffnen per Enter/Leertaste geben die Hilfe
wieder frei. Namen, ursprüngliche Beschreibungen, FormData, Dateiidentität und
native Aktionen bleiben erhalten. Root bestätigte den finalen Stand separat:
16 neue Browserfälle (`18.54s`), acht unveränderte Readonly-/Archiv-Rezeptfälle
mit JS/No-JS bei 390/1440 px (`26.98s`) und vier echte Menü-CSP-Fälle (`11.40s`).
Alle GATE-/Prozess-Exits 0. JUnits:
`/var/tmp/dishboard-tooltip-{reviewfix,readonly-reviewfix,csp-reviewfix}-root-0928.xml`.
Root sichtete eigene Escape-Aufnahmen. Die zusätzlich bestandenen 55 Shared-
Pattern- und 42 Semantikfälle stammen vor der letzten fünfzeiligen Tastaturkorrektur.
Diese behebt eine im unabhängigen Review zweimal beobachtete Regression
(`4 failed, 4 passed`); der alte Rezepttest blieb unverändert. Unterschiedliche
Autoren lieferten Produkt, Reviewkorrektur und Root-Abnahme. OCR bleibt ohne
Ergebnis, der neue Worktree ohne GitNexus-Index; Quellradius ausdrücklich appweit.

Druckvorlagen bleiben isoliert: Root 30 Browser- und 17 Archiv-Serverfälle grün,
echter App-Zoom 2× in allen sechs Profil-/JS-Kombinationen gemessen. Die eigene
Bildkontrolle zeigt jedoch einen vertikal überlaufenden Fehlertext am Symbol-
Summary nach ungültiger Archivbestätigung. WP `wp-3ba9cd7236a8` korrigiert diesen
gemeinsamen Fehlerindikator; fünf alte Browserdateien und umfassende Routen-Gates
bleiben offen. Bildschirm-Reihenfolge, Importdetails und der ursprüngliche
vollständige Bildschirm-Retry laufen separat und sind hier nicht abgenommen.

## Release- und Diagnosezustand 2026-09-28, 06:05 CEST

Zug 05:07 auf `1424adecc` ist vollständig beendet: 4382 Tests, 16 Fehler,
davon vier bereits bekannte Typografiefehler und `NEW_FAILURES=12`, acht Skips.
Kein Push/Deploy. Alle 56 isolierten Browserdateien liefen durch.
Log: `/var/tmp/dishboard-release-train/20260928T030700Z-9NRdt3`.
Liveprüfung 05:39: `c8c2e3c`, healthy, Login 200, gleich `github/main`;
zweimal Exit 1 wegen 186 Minuten Deploy-Alter. Der sporadische Rezept-Anlegefall
bestand diesmal mit allen zwölf Rezepteditorfällen; seine Ursache bleibt offen.

Separat geprüft und zur Integration freigegeben: semantische Wochen-Summaries
erben 36/44 px statt alter 44/48-px-Übersteuerungen. Text-Summaries behalten ihre
Mindesthöhen. Root: 19 Adminfälle, acht echte Fine/Coarse-Fälle beider Profile,
acht Fälle mit echten Browserassets; unabhängiger Peer: komplette 69 Renderfälle.
Die Messung erfasst jetzt auch sichtbare Öffner geschlossener Details und prüft
deren nichtleere Soll-/Ist-Anzahl. Root sichtete eigene Desktop-/Mobilaufnahmen.

Rezeptfilter: Worker und Root jeweils zwei komplette Fälle mit fünf Viewports,
JS/No-JS und unveränderten Formular-/Layoutprüfungen; Root `2 passed in 91.58s`.
Referenzliste: Worker zehn, Root `10 passed in 223.82s`; vier native Zoomfälle
mit App-CDP-Zoom 2, CSS-Zoom 1, DPR 2, 1440×813-PNG und unveränderter Geometrie.
320-/390-px-Reflow bleibt separat, keine gelockerte Overflowgrenze.
Rezeptmenüs: Root sieben Navigations-, 228 Semantik- und 23 Ansicht-/Druckfälle
grün; sichtbare kurze Labels nur im geöffneten Überlauf. Zusätzliche Menüprüfung
schließt ihren fokussierten Tooltip explizit mit Escape vor dem nächsten Klick.
Dies behebt nicht den separat reproduzierten Import-Escape-Konflikt.
JUnits: `/var/tmp/dishboard-{week-summary,week-summary-geometry,week-summary-live,
recipe-filter,reference-native,recipe-menu,recipe-menu-semantics,recipe-menu-view}-root-0928.xml`.
OCR bleibt wegen beobachtetem HTTP 402 ohne Ergebnis; neue Worktrees sind nicht
GitNexus-indexiert. Quellreview und echte Diffs ergänzen diese offenen Toolgrenzen.
Die folgenden älteren Abschnitte bleiben historische Nachweise; keine Live-Abnahme.

Zug 04:07 auf `b47c957d` ist vollständig beendet: `NEW_FAILURES=19`,
`verdict=1`, kein Push/Deploy. 18 Fehler betreffen später integrierte Korrekturen;
ein weiterer Rezeptfall liest nach Anlegen eine leere Zutatenzeilen-ID.
Sein isolierter Originalfall bestand; Ursache und Synchronisation bleiben in Prüfung.
Alle 55 isolierten Browserdateien wurden ausgeführt. Log:
`/var/tmp/dishboard-release-train/20260928T020700Z-Nz1M6U`.
Live `c8c2e3c` bleibt healthy, Login 200 und gleich `github/main`.
Statusprüfung zweimal Exit 1: seit 142 Minuten kein Deploy; Warnung bleibt bestehen.

Die Referenzlistenprüfung scheitert auch im identischen Retry an vier
CSS-Zoom-Überläufen (`4 failed, 6 passed in 249.99s`). Keine Grenzlockerung;
die Testanpassung bleibt isoliert. Importdetails zeigen zusätzlich einen
reproduzierten Escape-Konflikt: ein Hover-Tooltip wird versteckt und durch
Fokusübergabe beim Schließen des Details erneut geöffnet. Root-Cause-Diagnose
vorhanden, Shared-JS noch unverändert; die neue Importprüfung bleibt rot.

## Strikte Kontextübersetzungen 2026-09-28

`ca65fd60` ergänzt genau `recipe.import.row_details`,
`print_template.reactivate.label` und `print_template.reactivate.aria` in DE/EN.
Der Locale-Validator erhält dieselbe feste Allowlist; unbekannte, fehlende
oder leere Nachrichten bleiben Fehler. Parameter werden auch bei als sicher
markiertem Eingabetext escaped. Registry und vorhandene Icons bleiben gleich.
Die appweite Aufrufwirkung (GitNexus HIGH, 63 Symbole) wurde vor Änderung gemeldet.

Unabhängige Root-Prüfung: `228 passed in 26.82s` für Semantik-/Localeverträge;
`6 passed in 2.48s` für echten Appstart und öffentliche Profil-/Ausgabeverträge.
Jeweils `GATE_EXIT=0`, äußerer Exit 0; Ruff ohne Befund.
JUnits `/var/tmp/dishboard-context-messages-root-0928.xml` und
`/var/tmp/dishboard-context-appstart-root-0928.xml`.
Das ist eine geprüfte Voraussetzung, keine Abnahme der folgenden Import-/Druckoberflächen.

## Pilot-Listenköpfe und native Rezeptfilter 2026-09-28

`wp-ef3412676030`, `9191178b`: Baustein-Suche und Trefferzahl teilen eine
Desktopzeile; mobile Kategorie/Verwendung stehen kompakt neben ihren Labels.
Rezepte verwenden den gemeinsamen Filterbaustein und keine redundante Statuskarte.
Felder `text/q/ingredient/tag/archived`, Pagination, Rollen und native GET-Aktionen
bleiben erhalten. Makroparameter `search_id` und `search_emphasis` sind optional
und stehen am Ende; 20 alte/neue DE/EN-Ausgaben wurden vom Worker bytegleich geprüft.

Eigene Gates, alle mit `GATE_EXIT=0` und äußerem Exit 0:

- Dichte: `38 passed in 155.63s`, 48 reale Ansichten mit gleichen zehn Datensätzen.
- Native Filter: `8 passed in 59.14s`, einschließlich Tastatur, JS/No-JS, Nur-Lesen,
  Archivfilter, DE/EN-Namen, Paging/Reset und unverändertem DB-Snapshot.
- Vorhandene Nur-Lesen-Fälle: `2 passed in 10.42s`.
- HTTP-Suche und Bausteinfilter: `14 passed in 27.94s`.

Erste Desktop-Datenzeile: Bausteine 243 → 207 px, Rezepte 285.80 → 212.30 px;
jeweils zehn vollständig sichtbare Datensätze. Mobile Bausteinzeile 309 → 253 px;
Grenze 260 px unverändert. Null Zeilen-, Zell- oder Textüberläufe in der Matrix.
JUnits: `/var/tmp/dishboard-pilot-{headers,filters,readonly,http}-root-0928.xml`.
Desktop und mobile Filteraufnahme selbst gesichtet. Der bekannte fehlende Text
im geöffneten Rezept-Aktionsmenü bleibt ein eigenes §5.4-Korrekturpaket.
Der im gescrollten Fullpagebild sichtbare Skiplink ist ein offener Aufnahme-/Fokusbefund,
kein bewiesener neuer Produktfehler. Integriert, noch nicht live.

## Wochen-Symbolgrößen und Release-Testverträge 2026-09-28

`wp-5348075ecbdb`, `64ccc7aa`: beide Wochenübersichten verwenden für
Symbolaktionen wieder 36 px mit feinem und 44 px mit grobem Zeiger.
Navigation und Formularfelder behalten ihre bisherigen Mindestgrößen.
Patienten-Tageshöhe 321 → 285 px; bestehende Grenze 300 px unverändert.
Eigene Desktopaufnahme und unveränderte Dichtefälle beider Profile geprüft.

Worker-Vollgate mit `-p no:randomly -p no:cacheprovider`:
`33 passed in 125.19s (0:02:05)`, `GATE_EXIT=0`, äußerer Exit 0.
JUnit `/var/tmp/release-regression-0928-week-release-order.xml`.
Zwei frühere Vollaufrufe mit aktivem Randomly scheiterten ausschließlich an
der Reihenfolge der Playwright-Kontexte; beide Nachweise sind aufbewahrt.
Unabhängige Root-Gates: 8 Geometrie-, 2 Dichte-, 9 Katalog-, 5 Speicher-/Rückkehr-,
4 Menü- und 7 Rezeptnavigationstests, jeweils Exit 0. JUnits unter
`/var/tmp/dishboard-{week-geometry,week-density,catalog-regression,saveback,menus-regression,recipe-navigation}-root-0928.xml`.
Die Testanpassungen bewahren native Tastaturbedienung, Formularwerte, Rollen,
PDF-Ziele und Mutationsverbote. Kein Skip, kein gelockerter Dichtewert.
Integriert nach Quellreview, noch nicht live; Zug 04:07 prüft den älteren SHA `b47c957d`.

Offen bleiben CSS-Zoom-Überlauf der Referenzliste und konkrete §5.4-Labels
in geöffneten Aktionen-/Bestätigungsbereichen. Der sichtbare fachliche
Bestätigungskontext allein beweist keine korrekte Beschriftung des finalen Buttons.

## Rezept-Rücknavigation 2026-09-28

`wp-73b651824160`, `bafda787`: der lesbare Link «Zur Liste» im Rezepteditor
verwendet wieder die bestehende 48-px-Navigationshöhe. Eine gezielte Regel in
`recipe-admin.css` betrifft nur den direkten Toolbar-Link; Symbolaktionen
behalten 36/44 px. Korrektur durch einen anderen Autor, keine Testgrenze gesenkt.
Eigener unveränderter Shelllauf in isoliertem Review-Worktree:
`7 passed in 128.29s`, Exit 0, inklusive JS/No-JS, niedriger Fensterhöhe und
echtem 200-%-Browserzoom. Eigene Mobilaufnahme gesichtet. JUnit:
`/var/tmp/dishboard-nav-root-0928.xml`. Integriert, noch nicht live.

## Native Detailaktionen 2026-09-28

`wp-2b4ee926bca9` mit unabhängigem Reparaturpaket `wp-08363347d3d3`
(`e9c0cdff` + `028c983e`): Baustein-Editor beider Profile sowie Rezeptentwurf
und gespeicherte Rezeptrevision verwenden gemeinsame Symbol-Summaries für
weitere Aktionen, Originalmengen und Herkunft. Fachinhalte und ausdrückliche
Archivbestätigung bleiben lesbar. Native Details, ungespeicherte Formwerte,
Admin/reduzierte Editor-Rechte und unveränderliche Revisionsinhalte bleiben erhalten.

Eigene Prüfung: `test_icon_component_recipe_details_browser.py` meldet
`1 passed in 18.75s`, Exit 0; 32 Bildschirmmessungen, vier Druckmessungen,
DE/EN/Pseudo-Locale, Tastatur/Tooltip/Escape, JS/No-JS, 1440/390 und echter
200-%-Browserzoom. Drucktexte zuvor in 36-px-Flächen vertikal umgebrochen;
jetzt passen Originalmengen/Herkunft in 172/119 px, jeweils eine 24-px-Textzeile.
Desktop-/Mobilbilder gesichtet. Separater eigener Vertragslauf:
`259 passed in 30.94s`, Exit 0, einschliesslich 48 nativer PDF-Fälle.
JUnit: `/var/tmp/dishboard-detail-root-0928.xml` und
`/var/tmp/dishboard-detail-contracts-root-0928.xml`.
Integration ist kein Live-Nachweis; Release-Zug 03:07 stoppte mit 21 neuen
Fehlern in anderen Prüfungen. Produktion bleibt auf `c8c2e3c`.

## Pilot-Reflow 2026-09-28

`b8438235` korrigiert einen im Zehn-Datensätze-Pilot sichtbaren Mobilfehler:
Die zweizeilige 64-px-Regel war spezifischer als die mobile Auto-Höhe.
Sichtbare Zellen liefen bis y=655 über das Zeilenende y=411 in Folgezeilen.
Eine zusätzliche Selektorzeile in der bestehenden mobilen Regel stellt die
automatische Höhe wieder her; Desktop bleibt unverändert.
Unabhängig: `36 passed in 146.19s (0:02:26)`, `GATE_EXIT=0`; beide
Bausteinprofile und Rezepte, Admin/Editor, JS/No-JS, 1440/390 und echter
Browserzoom 200 %. Harte Prüfungen erfassen sichtbare Zell-/Textgrenzen,
Folgezeilen, Schriftgrößen 14/13 px, Filter und native Formularverträge.
JUnit `/var/tmp/dishboard-pilot-density-root-0928.xml`; eigene Mobil-/Desktopbilder
im gleichnamigen Verzeichnis gesichtet. Nach Integration: 41-Seiten-Listenprüfung
`6 passed in 18.09s`, `GATE_EXIT=0`,
JUnit `/var/tmp/dishboard-list-mobile-fix-root-0928.xml`.

UI-24: Desktop zeigt zehn vollständige Datensätze. Bausteine haben natürliche
zweizeilige Namen; Rezepte führen Ausbeute in separater Spalte, weshalb dieser
Teil nicht als zweizeiliger Rezeptnachweis gilt. UI-23 bleibt offen: erster
Bausteindatensatz 243 px, Rezeptdatensatz 285.8 px ab Main. Diese Richtziel-
Abweichung wird erfasst und nicht als bestandene Kopfverdichtung ausgegeben.
Noch kein Deploy dieses Pakets behauptet.

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
weiter eine Lokalisierungslücke. Diese Welle ist als `c8c2e3c` seit 02:32 CEST
live (exakte Revision, gesund, Login HTTP 200); keine authentifizierte
Produktions-Sichtprüfung behauptet.

Listenfamilienmessung `75453eee`: 41 Seiten/82 Blöcke, Kopfvergleich nur für
vorhandene Köpfe; Links mit gleicher Typografie gelten nicht mehr als abweichend.
Hintergrund/Höhe bleiben Messwerte. REPORT-Modus darf keine neue Abweichung in
die Baseline übernehmen. Eigener Zweitlauf `4 passed in 18.46s`, `GATE_EXIT=0`.
Nachmessung `4c8cac50`: native verschachtelte Summaries zählen als Einträge;
leere, verborgene und inerte Menüs bleiben erkannt. Vier alte API-Codes entfernt,
keine Baseline erhöht. Eigener Zweitlauf `6 passed in 19.50s`, `GATE_EXIT=0`,
JUnit `/var/tmp/dishboard-list-native-root-0928.xml`. Die manuelle Sichtsektion
des Vergleichsberichts bleibt beim Regenerieren unverändert erhalten.
Weitere konkrete
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
Gestaltungsabnahme: Anlegen-Disclosures und andere Reststellen werden weiter
klassifiziert; Vorlagenstatus ist im folgenden Paket verdichtet.

Vorlagen `8624fe48`: `/admin/vorlagen`, Admin/Editor, beide Profile und Rezept,
aktive Revision mit neuerem Entwurf, JS/No-JS und 390/1440 px. Vier Statuskarten
und doppelte aktive Vorlage entfernt; aktive Revision und neuer Entwurf bleiben
unterscheidbar, gespeicherte und veröffentlichte Druckziele bleiben getrennt.
Gleiche Fixture: erste Desktopzeile 517.19→189.80 CSS px ab Main; mobile erste
Zeile 985.89→354 px. Vorhandener nativer `:target`-Tabwechsel bleibt erhalten.
Eigener Lauf `1 passed in 151.70s (0:02:31)`, `GATE_EXIT=0`; JUnit und gesichtete
Desktop-/Mobilbilder `/var/tmp/dishboard-template-calm-root-0928*`.
Auf integrierter Basis bestehende Output-Matrix inklusive echtem Zoom,
Leer-/Fehler-/Konfliktzuständen: `16 passed in 77.99s (0:01:17)`, `GATE_EXIT=0`,
JUnit `/var/tmp/dishboard-template-output-root-0928.xml`.

Wochenwarnungen `6ef6fb40`: `/admin/cafeteria` und `/admin/patienten`, Mittag/Abend,
fehlende/gemischte/vollständige Angaben, 390/1440 px. Wiederholte Warnplaketten
werden lesbare Sekundärtexte; Kopfsumme, Eintragslinks und Veröffentlichungssperre
bleiben unverändert. Fehlend bleibt ausdrücklich ungleich allergenfrei, gespeicherte
Angaben bleiben ungeprüft. Unabhängige Matrix: `12 passed in 39.21s`; bestehende
Prüf-/Formularfälle a04–a07: `10 passed, 27 deselected in 32.39s`, beide
`GATE_EXIT=0`. JUnit `/var/tmp/dishboard-week-warnings-root-0928.xml` und
`/var/tmp/dishboard-week-safety-root-0928.xml`. Vorher/Nachher visuell geprüft.
Bereits vorher sichtbare überlappende Gangnamen und abgeschnittene Bildhinweise
sind durch das folgende separate Paket korrigiert.

Rezepteditor `24be3ef8`, `/admin/rezepte/<id>/bearbeiten`: gemeinsame native
Symbol-Summaries, lesbare Sicherheitsbestätigung, unveränderte POST- und
Fokusverträge. Eigene getrennte Läufe: neue Matrix `12 passed in 50.03s`,
Semantik/Makros `250 passed in 71.26s`, vorhandener Editor `12 passed in 57.62s`,
Dichte `21 passed in 93.08s`, Suche `7 passed in 24.23s`; alle `GATE_EXIT=0`.
JUnit `/var/tmp/dishboard-editor-{icons,shared,existing,density,search}-root-0928.xml`.
Die Dichtefälle beweisen noch nicht das Pilotkriterium von acht sichtbaren
Datensätzen bei mindestens zehn angelegten Einträgen.

Wochen-Reflow `1825cdd7`: lange Suppen-/Dessertnamen erhalten eigene Grid-Zeilen
und Wortumbruch; fehlendes Menübild bleibt vollständiger Sekundärtext.
Eigene Matrix `20 passed in 66.73s (0:01:06)`, `GATE_EXIT=0`, beide Profile,
JS/No-JS, 1440/1024/768/390 px und echter Browserzoom 200 %.
JUnit `/var/tmp/dishboard-week-reflow-root-0928.xml`, Bilder im gleichnamigen
Verzeichnis; Patient Desktop und Cafeteria Mobil unabhängig gesichtet.
Veröffentlichungssperre und native Formularfelder bleiben geprüft.

Release-Messwerkzeug `69e87ddd`: `show_text=` wird nicht mehr als `text=` gelesen.
Sechs unabhängige Unitfälle bestanden; echte entfernte Labels und gesperrte
Testdateien bleiben erkannt. Editorvergleich fällt dadurch von acht vermeintlich
entfernten Texten auf die zwei tatsächlich entfernten Labels zurück.
Diese Pakete sowie Vorlagenverdichtung und Listen-Nachmessung sind integriert,
aber noch nicht deployed. Gemeinsame API-/Rezepteditor-Browsermatrix auf
integrierter Basis: `16 passed in 67.18s (0:01:07)`, `GATE_EXIT=0`,
JUnit `/var/tmp/dishboard-icon-combined-root-0928.xml`.

Native Auswahl-/Detailaktionen `72862c47`: Rezeptvorlagen-Auswahl, Menü-Sammlung
(beide Profile, Admin/Publisher, Liste/Karten) und Bildschirm-Fehlerseite.
Gemeinsame Symbol-Summaries bewahren ausgewählte Rezeptstände, Hinweise und
ungespeicherte Formularfelder. Der DB-freie 503-Fallback lädt bestehende lokale
Tooltip-Assets; erneuter GET nach fehlgeschlagenem POST bleibt möglich, private
Fehlerdetails und DB-abhängige Context-Processor bleiben ausgeschlossen.
Eigener Lauf `16 passed in 53.28s`, `GATE_EXIT=0`, JS/No-JS, 390/1440 px.
JUnit `/var/tmp/dishboard-native-root-0928.xml`; eigene Bilder im gleichnamigen
Verzeichnis für Fehlerseite, gewählten Rezeptstand und Menüdetails gesichtet.
Noch offen im übergeordneten Druckvorlageneditor: redundante Statuskarten und
Klassifikation seiner übrigen beschrifteten Disclosures. Keine volle Editor-
oder appweite Gestaltungsabnahme aus diesem Paket abgeleitet.

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
