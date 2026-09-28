# UI-Konsistenzinventar — Migrationsliste P4/P5

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
