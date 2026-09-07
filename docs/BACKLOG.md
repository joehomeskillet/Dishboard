# Backlog

## Aktueller Stand — Live-Checkpoint vom 7. September 2026, 05:16 Uhr Schweiz

Die Uhrzeit bezeichnet den belegten Admin-Live-Checkpoint. Der Gate-Nachtrag unten dokumentiert die später bestätigten Laufzustände 64757 und 89103 ohne zusätzliche Zeitbehauptung.

**Produktiv bleibt `3d35cbb` seit 07.09.2026, 04:18:43 CEST, mit Schema 20.** Die unabhängige vollständige Paketprüfung bestand mit **4472 Tests und 15 ausdrücklich aktivierbaren Opt-in-Skips**. OPS-001 ist ausgeliefert; frühere Lane-Unterbrechungen sind kein aktueller Lieferstatus.

**Frische lesende Live-Nachweise:** Der OPS-Beleg `ops-live-branding-3d35cbb-root-0907/proof.json` enthält **56 bestandene Checks für beide Viewports**. Die datierte Admin-Probe `admin-live-week-3d35cbb-root-0907/proof.json`, erfasst am `2026-09-07T03:16:09.722335+00:00`, bestand mit **738 Checks und 36 Screenshots**, ohne Fehler oder nicht verfügbare Prüfungen. Beide Familien und beide Viewports verwenden ausdrücklich die gespeicherte Woche **2026-08-31**. Operatorquelle `450894babda514e63602b2e40c8ae123263c38cc`: unabhängig 167 Tests bestanden nach getrennten Läufen mit 149 und 78 bestandenen Tests. Die datierte Druckprüfung derselben Woche bestand für beide Familien: 10 Cafeteria-/28 Patientenfotos, jeweils eine PDF-Seite und gleiche Karten. Fachliche Druckabnahme bleibt offen.

**Vorbereitet, nicht deployed:** `5b746b35d261ed8b552724b3b273e71fd393973c` enthält geprüfte Menü-Iconaktionen und deklarierte VEG/VGN-Angaben für UI-003/ICO-001/002. Kombinierte 121 Tests und Roots unabhängige Imageprüfung bestanden. Das vollständige Releasegate 6043 endete mit Exit 143, ohne JUnit oder Abschlussausgabe; die Ursache ist unbelegt. Root sicherte die Evidenz mit `cp -a` unter `symbols-fullgate-0907-hvz04M/evidence-first` und bestätigte anhand der Prozess-Arbeitsverzeichnisse, dass im eingefrorenen Export keine Prozesse verblieben. Der exakt identische Wiederholungslauf 89103 läuft; kein vollständiges PASS. Image `menuplan-symbols-0907:5b746b3-u022` wurde anhand von 677 Dateien ohne Abweichungen oder Extras, 247 AST-Prüfungen, Revision-Label, Benutzer, pip und Schema-20-Hashes unabhängig bestätigt (Build-WP `wp-1b31436a1455`). Das ist keine Produktivabnahme.

**Public und nächste Grundlage:** Aktuelles Public-404 mit `no_published_menu` ist bei fehlender aktueller Publikation vertraglich erwartet. Die Leerseite verwendet noch die alte Basis; der separate Tabler-Fix `de80b7e` bestand nach 1959 Worker-Tests auch Rootgate 64757 mit **1959 passed in 65.04s**. Root las den vollständigen Zwei-Dateien-Diff; Ruff bestand. Normales Mypy meldet byte-identisch dieselben 64 Fehler in 14 Basisdateien, kein Mypy-PASS. Der Fix ist noch nicht integriert oder deployed. BAS-001/B2 wird aktiv in `bas-b2-ma-astra` umgesetzt; Schema 21 ist reserviert, nicht produktiv. B1 ist bereits Bestandteil von `3d35cbb`. Die früheren IAM-, Branding- und Playerbelege unten gelten nur für ihren damaligen Stand; offene fachliche und physische Abnahmen bleiben erhalten.

## Historischer Releasebeleg — 6. September 2026, 20:38:51 Uhr Schweiz

Die folgenden Release-, Sicherungs- und Liveangaben beschreiben Schema 19. Der damalige Fallback ist kein Rückweg für die aktuelle Schema-20-Produktion; deren geprüfter Betriebscheckpoint wird von Root separat geführt.

**Produktiv ist `3690e04585af6b5c16917872cf6e4b50601b22c9` seit 20:38:51 Uhr CEST**, Image `sha256:6fca168acd508b2a66b58399f2beb1f87c979252f20aa55dc7897d1ba79bc828`, Containerstart `2026-09-06T18:38:51.931697209Z`, `healthy`, öffentlicher HTTP-Status 200. Schema **19**: Migration, Runtime und Auth-Issuer jeweils `ready=true`; Registry-Prüfsumme `e195aac3c6b53fb08f733723cd8ef12e6e40fb7abdc5fe58bf1f88585015c6c1` bestätigt. Vollständige unabhängige Paketprüfung: **4001 Tests bestanden, 15 Opt-in-Skips**, 4016 Tests insgesamt in 1603.990 Sekunden, `PACKAGE_GATE_EXIT=0`. Die 14 Restore-Opt-ins bestanden danach separat in 122.97 Sekunden. Die korrigierte Compose-Probe bestand mit vier Fehler-/Cleanup-Fällen zusammen mit dem Branding-Operator unabhängig **67 Tests in 21.87 Sekunden**. Sie prüft Containererzeugung ohne Pull/Build, die konkrete Missing-Image-Ursache und eigene Ressourcenbereinigung; keine gestarteten Dienste oder Netzkonnektivität. [Aktueller Releasebeleg](/nvmetank1/projects/rag-stack/.claude/reports/wp-ee18982cddf0.md).

**Neu live:** lokale Benutzerverwaltung (IAM-001) und gleiche Menükarten in beiden HTML-Wochen-Druckprofilen, auch mobil. Die bildlosen Web-Wochenpläne, vier Screens-Karten/zehn Vorschauen und UI-003 bleiben seit `0acd992` produktiv; zentrale Markenpflege und gemeinsame Menü-Legenden seit `cc6c8ce`. Diese früheren Lieferungen werden nicht erneut gezählt.

**Frische Live-Abnahme nach diesem Deploy:** [IAM](/tmp/dishboard-iam-readonly-live-after-deploy-0906/proof.json) 208 Checks/12 PNG, [Screens](/tmp/dishboard-screen-variants-live-iam-0906/proof.json) 386 Checks/20 PNG und [API/Admin/PDF](/tmp/dishboard-iam-api-admin-live-0906/proof.json) 194 Checks/18 PNG: insgesamt **788 bestandene Checks und 50 Screenshots**, alle drei Belege `passed`, keine fehlgeschlagenen Checks. Der Screens-Beleg weist separat **acht abgebrochene Bildabrufe** (`cancelled_image_requests`) aus. IAM wurde lesend geprüft; **kein produktiver IAM-Schreibtest**. Der vollständige Login-/Logout-Zugriffsverlauf bleibt gesondert offen.

Die frühere Branding-Browserprüfung mit 798 Checks/40 Screenshots blieb wegen 21 Befunden FAIL. Die echte mobile HTML-Druckkartenabweichung ist produktiv behoben; MIME- und Geometrie-Fehlalarme wurden im Operator korrigiert. Root hat den Geometriefix unabhängig mit **87 Tests**, Ruff und Mypy geprüft. Zwei frische vollständige Live-Durchläufe liefern nun jeweils **798 bestandene Checks, 40 Screenshots und null Fehler** ([erster Beleg](/tmp/dishboard-root-branding-overflow-live-first-0906/proof.json), [Wiederholung](/tmp/dishboard-root-branding-overflow-live-0906/proof.json)). Beide melden trotzdem korrekt `incomplete`: individuelle öffentliche/Vorschau-Logos werden von den aktuellen Revisionen nicht verwendet; geschlossene oder leere Zustände sind nur abgedeckt, soweit sie live vorkamen. **Keine uneingeschränkte Branding-Gesamtabnahme.** Diese Varianten, fachliche Küchenbestätigung, physischer Yodeck-Player und externer Design-Validator bleiben separate Abnahmen.

**Rückweg und Sicherungen:** Schema-19-kompatibler UI-off-Fallback `ff4fbc9`, Image `sha256:511618f522077e730fb721b7c5181c6bdb27d4bdbb853cc8855e89ffa09b2da9`, vorbereitet und unabhängig mit 177 Tests, 495 gleichen Dateihashes, 229 AST-Prüfungen und pip-Prüfung bestätigt; er ist nicht der laufende Release. Root prüfte Hash und TOC beider Sicherungen: vor Schema 19 `cafeteria-20260906T183716Z.cEcJmn.dump`, SHA-256 `45a901c49cd5bdc8199552dfcf040c1e81a299f581569f876dd156d1a0ffd9eb`; danach `cafeteria-20260906T183935Z.BnjLhD.dump`, SHA-256 `c972ca061bc4b9610162c41d3bdb659a0645c76b2e8e593f0ee21ccbf2d105d5`. Die separaten Restore-Tests oben sind kein behaupteter Wiederherstellungstest dieser beiden Produktionssicherungen.

Der vorbereitete Fallback gilt ausschliesslich für einen nachgewiesenen UI-Fehler nach erfolgreicher Schema-19-Migration. Schema-/Kernfehler erfordern einen geprüften Forward-Fix auf Schema 19; ein altes Schema-18-Image oder ein älterer Datenbankdump ist kein gewöhnlicher Anwendungsrollback.

Alle **35 Backlog-IDs** bleiben mit ihrem vollständigen Umfang erhalten. Die grossen Rezept-, Stammdaten-, Nährwert-, Kalkulations-, Lager-, Bestell- und freien Editorpakete sind weiterhin offen. Ältere «lokal vorbereitet»-Angaben unten werden durch diesen Stand ersetzt, nicht als weitere Lieferung gezählt.

## Bestand und operative Reihenfolge — 7. September 2026

**Operative Reihenfolge:** OPS ist produktiv. Das vorbereitete Symbolrelease durchläuft sein vollständiges Releasegate; der Public-Leerseiten-Fix und BAS/B2 werden unabhängig weiter geprüft beziehungsweise umgesetzt. Danach bleiben offene Screens-/Vorlagen-/Branding-Funktionen, Grundlagen und Rezeptverwaltung, Suche/Importe/Produktdaten, Rezeptplanung/Einkauf/Druck/KI, Kalkulation/Lager/Bestellungen und weitere Anbindungen. Die Phasen unten erhalten alle Detailaufträge; Qualitäts- und Fachabnahmen begleiten jede Lieferung.

**Gruppierter Bestand, keine Abschlussquote:** Die folgenden Gruppen enthalten jede Tabellen-ID genau einmal. «Produktive Funktionen» umfasst ausdrücklich Teilfunktionen und offene Abnahmefälle; es bedeutet nicht, dass 16 vollständige Backlogaufträge erledigt sind. BAS-001 bleibt trotz ausgeliefertem B1 wegen des aktiven B2-Pakets in der Umsetzungsgruppe.

| Gruppe | Anzahl | IDs / verbleibende Grenze |
|---|---:|---|
| Produktive Funktionen | 16 | UI-001, UI-002, UI-003, CAT-001, DSP-001, BRD-001, API-001, ICO-001, ICO-002, SCR-001, SCR-002, TPL-001, TPL-002, TPL-003, IAM-001, OPS-001. TPL-001/002 und SCR-001 haben erst Teilfunktionen; der vollständige IAM-Zugriffsverlauf bleibt offen. Offene Daten-, Druck-, Branding- und Playerabnahmen stehen weiterhin in den Einzelzeilen. |
| Aktive Umsetzung | 1 | BAS-001: B1 ist produktiv, B2 wird aktiv umgesetzt. Voraussetzung OPS-Schema 20 erfüllt; Schema 21 reserviert, noch nicht ausgeliefert. Keine vollständige BAS-Fertigmeldung. |
| Weitere grössere Umsetzung offen | 16 | REC-001–REC-007, NUT-001, OFF-001, CALC-001, INV-001, ORD-001, IAM-002, PKS-001, TRN-001, SCR-003. Vorhandene Referenzanalysen und Stammdaten ersetzen diese Funktionen nicht. |
| Fortlaufende Abnahme | 2 | QA-001 und DATA-001; technische Lieferungen ersetzen weder physische Player- noch fachliche Küchenbestätigung. |

## Historischer Deploy-Nachtrag — 6. September 2026, 04:55:35 Uhr Schweiz

Dieser Abschnitt beschreibt den damaligen Schema-17-Deploy; aktueller Release und Schema 20 stehen oben.

**Release `118a644` ist produktiv**, Image `sha256:afe5305a73128fb92cbbf3f325ea441aacc8b9a6acc38d28487c301eb9779c41`, Container `healthy`, Schema 17. Migration: 32 Tabellen, `ready=true`; Runtime: 30 sichtbare Tabellen, `ready=true`. API, die vier öffentlichen Tabler-Seiten, vier globale Darstellungsoptionen und der erste Wochen-PDF-Eigenschaftseditor sind jetzt live. Nachweise: **3695 Tests bestanden, 15 Opt-in-Skips**, vollständige Paketprüfung `PACKAGE_GATE_EXIT=0`, **272 Live-Checks bestanden**, 44 Screenshots sowie vier zusätzliche Rotationsscreenshots in FHD/4K mit allen 28 Patientenmenüs. [Vollständiger Root-Beleg](/nvmetank1/projects/rag-stack/.claude/reports/wp-bd5539046da6.md).

Die früheren Angaben «lokal vorbereitet», «noch nicht deployed» und Produktion `1bff82e` sind für diesen Lieferumfang historisch und durch diesen Nachtrag abgelöst. Live-Restbefunde: impliziter Favicon-Abruf HTTP 404, physische Yodeck-Abnahme und externer Design-Validator. Der rohe Rotations-Gesamtstatus bleibt wegen des Favicon-404 `passed:false`; Rotation und Layout bestanden. **Alle 35 Backlog-IDs und ihr vollständiger Restumfang bleiben erhalten**; der erste Eigenschaftseditor und die Darstellungsauswahl erfüllen die umfassenden Vorlagen-/Markenaufträge nicht.

**Historischer Vor-Deploy-Stand:** **6. September 2026**, vorbereitete Lieferung `69ef540`. Nutzerauftrag: gesamten Backlog umsetzen. [Ausführungsplan und laufende Pakete](superpowers/backlog-execution-0906.md). «Lokal vorbereitet» bezeichnete implementierte Änderungen mit Teilnachweisen, ohne Produktivabnahme. Damals bestätigte Produktion: `1bff82e`, Schema 16; die neue API-/Public-/Admin-Lieferung war noch nicht deployed. Die Tabler-Basis war bereits produktiv; [Nachweise und verbleibende Abnahme](design/tabler-integration-evidence-0905.md) sind separat dokumentiert.

**Verbindlicher Nutzerentscheid: Alles im Admin bleibt Tabler.** Das gilt für Formulare, Felder, Buttons, Dialoge, Navigation und sämtliche Fremdeditoren. Eine Tabler-Shell um eine fremde Bedienoberfläche genügt nicht. Tandoor und Pauli sind Funktionsvorbilder, kein Vue-/Vuetify-Ersatz für den Admin. GrapesJS, pdfme und andere Editor-Kandidaten dürfen erst nach nachgewiesener vollständiger Tabler-Bedienoberfläche freigegeben werden.

## Zuletzt ausgeliefert

| ID | Auftrag | Status / Abnahme |
|---|---|---|
| UI-001 | Menüs: umschaltbare kompakte Listenansicht wie bei Komponenten, für beide Bereiche | Produktiv mit `6828138` seit 06.09.2026, 00:06 Uhr Schweiz. Vorhandene Filter und Editorlinks erhalten, aktueller Prüfstatus, keine Patientenpreise; Live-Prüfung bei 390 und 1440 px. |
| UI-002 | Öffentliche Seiten und Signage von technischen Angaben bereinigen | Produktiv mit `6828138`. Kanal, Revision, Auflösung und «Publizierter Datenstand» aus sichtbaren Ausgaben entfernt. Fachliche Inhalte, interne Header, Statuscodes und Veröffentlichungsschutz erhalten. |

Gemeinsamer Nachweis für UI-001/UI-002: 284 unabhängige lokale Regressionstests bestanden; Live-Prüfung mit 130 Checks und 20 Screenshots ohne Fehler.

**Historischer Produktivstand `1bff82e` seit 06.09., 03:09:55 Uhr Schweiz:** Screens zeigt vier Vorschaukarten mit acht echten eingebetteten Ansichten; die vier Signage-Direktlinks sind aus der Seitennavigation entfernt. Die Admin-Wochenansichten erfüllen die Kartengrössenprüfung für zehn Cafeteria- und 28 Patientenkarten. CSP-Korrektur um 03:16:31 Uhr. Live-Beleg: `/tmp/dishboard-live-hubs-cards-proof-0906/proof.json`, 78 bestandene Checks und zwölf Screenshots bei 390/820/1440 px. Dieser Beleg umfasst den damaligen Stand, nicht die nachfolgend vorbereiteten Editoren oder Public-Screen-Layouts.

## Fortlaufende Abnahme — bei jeder betroffenen Lieferung

CAT-001/DSP-001 sind bereits produktiv; ihre offenen Datenfälle werden mit der nächsten passenden Abnahme geschlossen. QA-001 begleitet jede betroffene Veröffentlichung, DATA-001 jede Übernahme oder Änderung fachlicher Angaben. Diese Prüfungen sind keine einmalige Schlussphase und blockieren unabhängige Entwicklung nicht.

| ID | Auftrag | Status / verbleibende Abnahme |
|---|---|---|
| CAT-001 | Fehlende Filter auf `/admin/cafeteria/komponenten` | In der produktiven Version `0ebea64`: kombinierbare Filter für Kategorie, Verwendung in Menüs, Allergene, Labels, Herkunft und aktiv/archiviert, mit Suche, Zurücksetzen und Trefferzahl; Gültigkeit/Bereich gemäss Tabler-SDD. Positive Label-Filter mit passenden aktiven Echtdaten und kombinierte Treffer sind noch abzunehmen. |
| DSP-001 | Globale **Darstellung**: kompakte Adminansicht als Standard | In der produktiven Version `0ebea64`: zentrale Einstellung unter Design & Marke für Benutzer und Geräte, ohne seitenspezifische Schalter oder Browser-Persistierung. Touch-Flächen, Pflicht-Hinweise und Fehlermeldungen bleiben Teil der Abnahme; gemeinsamer Schlussnachweis noch unvollständig. |
| QA-001 | Generische responsive und Yodeck-Abnahme | Nutzerkorrektur: generisch statt bestimmtem Samsung-Modell. Tablet/Telefon/Desktop nach CSS-Breiten; vier Signage-Routen bei 1920×1080 und 3840×2160, vier Public-Routen bei 390×844 und 1440×1100 im echten Browser prüfen. Lesbarkeit, Hoch-/Querformat, Bild-Fallback, Touchziele ≥ 48 px, a11y, CSP, Patientenpreisfreiheit sowie Revision, Datumswechsel, Rücknahme und begrenztes Ausfallverhalten prüfen. Yodeck auf Raspberry Pi 4B separat abnehmen: FHD als gemeinsames Ziel, 4K bei passender Hardware. Browsernachweise ersetzen keine tatsächliche Playerabnahme. |
| DATA-001 | Fachliche Bestätigung der Rezept-/Allergenangaben | Vorhandene Vorschläge durch Küche prüfen. Unbekannte Angaben bleiben unbekannt; fachliche Bestätigung wird nicht aus KI-Vorschlägen abgeleitet. |

Schlussnachweis für CAT-001/DSP-001 `/tmp/dishboard-settings-filters-live-final-0906/proof.json`: **`incomplete`**, 1'090 Checks, 0 Fehler, 6 mangels passender aktiver Echtdaten nicht verfügbare positive Label-Filter-Prüfungen. Dieser Beleg ist kein vollständiges Abnahme-PASS; fehlende Datenfälle bleiben offen.

## Lieferreihenfolge und Abhängigkeiten

Die folgenden Phasen geben die Priorität vor. Innerhalb einer Phase steht der nächste nutzbare Schritt oben; ausdrücklich unabhängige Pakete dürfen parallel oder früher starten, sobald ihre eigenen Voraussetzungen erfüllt sind. Es gibt keine Sperre, bis sämtliche Aufgaben einer früheren Phase abgeschlossen sind.

**Aktuelle Nutzerpriorität:** Gleichartige Menükarten müssen pro Ansicht und Bildschirmbreite durchgehend gleich hoch und breit sein, mit vollständig lesbaren Pflichtangaben. Die vier Signage-Direktlinks entfallen in der Seitennavigation; Screens bleibt der zentrale Einstieg und erhält echte Vorschauen in den Karten. Ein bedienbarer Vorlageneditor sowie zusätzliche wirksame Darstellungseinstellungen werden vorgezogen. Diese Korrekturen laufen parallel zur bereits begonnenen API-/Public-Screens-Lieferung.

Gemeinsamer Entwurf mit Dateizuordnung und Arbeitspaketen: [Screens, Vorlagen und Verwaltung](design/2026-09-05-screens-vorlagen-verwaltung.md).

**Historischer, geprüft vorbereiteter Zwischenstand `69ef540`:** API mit Schema 17, vier globale Darstellungsoptionen, erster PDF-Eigenschaftseditor, PS1–PS5, gemeinsame öffentliche Karten und begrenzter Ausfallpuffer sind lokal integriert. Der vollständige unabhängige Lauf ist abgeschlossen: **3695 bestanden, 15 Opt-in-Skips**, alle 3710 gesammelten Tests auf vier isolierten Pools abgedeckt. Ergebnisse und offene Abnahmen stehen im Ausführungsplan. Das ist keine vollständige Abnahme von BRD-001, SCR-001, TPL-001/002 oder ICO-001/002 und kein Produktivnachweis.

**Aktuelle Zuständigkeit seit 06.09.2026, 01:55 Uhr:** Nutzerentscheid und `KOORDINATION-API-CODEX-2026-09-05.md` (§ÜBERGABE, Nachtrag 02:00) übertragen API-001 und sämtliche Public-Screens-Pakete WP-1 bis WP-5 an Codex als alleinigen Orchestrator, zusätzlich zu Symbolbasis, Admin-Backlog, unabhängigen Gates, Integration und Deployments. Die frühere Claude-Zuständigkeit von 01:40 Uhr ist damit abgelöst; Claude führt diese Pakete nicht weiter. Vorhandene Worktrees und Ergebnisse werden übernommen.

**AGY-Anforderungen für SCR-002, ICO-001/002 und QA-001:** Hero-Food, Duo-Board und Wochenraster; Menüfotos mit Fallback, Live-Uhr, mobile Tabler-Karten und Wochentag-Pills. Flackerfreies Polling muss auch Datumswechsel bei gleicher Revision und zurückgezogene Veröffentlichungen (404/410) behandeln. Die vorgeschlagene unbegrenzte Offline-Anzeige wird nicht übernommen: gültige Daten, begrenztes Ausfallverhalten und Rücknahme müssen geprüft sein. Bestehende URLs, Query-Schutz, CSP und vollständige Patientenpreisfreiheit bleiben verbindlich.

### 1. Laufende Lieferungen abschliessen

API und Public Screens laufen unabhängig weiter. Symbolbasis und Screen-Layouts können parallel geprüft werden; gemeinsame Ausgaben und Legenden werden vor der jeweiligen Veröffentlichung zusammen abgenommen. Navigationsgrundlagen liefern bereits Nutzen, vollständige Verwaltung bleibt Teil der offenen Pakete.

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| BRD-001 | **Design & Marke** | Seit `cc6c8ce` produktiv: Darstellungseinstellungen sowie zentrale Logo-, Farb- und Schriftpflege mit sicherem Upload, Vorschau, Entwürfen, Aktivierung und Wiederherstellung. Admin/Web/Signage übernehmen die aktive Marke; Druckvorlagen können sie ausdrücklich erben. Vollständige Paketprüfung grün; verbleibende Browser-/Druck-/Player-Abnahme siehe aktuellen Stand. |
| TPL-002 | **Visueller PDF-Druckvorlageneditor** | Erster Tabler-Eigenschaftseditor auf fpdf2 seit `118a644` produktiv: speichern, kopieren, echte PDF-Vorschau, aktivieren und frühere Revision als neuen Entwurf übernehmen. Logos, Farben, Schrift, Ränder, Zellenabstände und Kopf-/Fusszusatz; aktive Marke seit `cc6c8ce` als ausdrückliche Auswahl. Offen: freie Druckgestaltung mit Spalten, Bildern, Symbolen, Legenden und Datenfeldern. Offizieller pdfme-Designer erfüllt nach geprüfter Analyse die vollständige Tabler-Oberfläche nicht; Generator separat prüfbar, keine Editor-Technologiefreigabe. |
| API-001 | REST-API v1, MCP, FHIR R5 und API-Schlüssel | Seit `118a644` um 04:55 Uhr produktiv, einschliesslich Migration 16→17. Unabhängige vollständige Suite 3695 bestanden/15 Opt-in-Skips, Paketprüfung und Live-Abnahme durchgeführt. Nach Branding-Deployment aktuelle API-/FHIR-/Admin-Verträge erneut im erfolgreichen 194-Checks-Lauf geprüft. Historische Gatefehler und Korrekturen stehen im Releasebeleg; externe Clientanbindungen bleiben getrennte Betriebsaufgaben. |
| ICO-001 | Allergen-Symbole und Herkunftsflaggen in Admin, Web, Signage und PDF | Gemeinsame Symbole und sämtliche Web-/Signage-/PDF-Verbraucher seit `cc6c8ce` produktiv. Erudus für 14 Allergengruppen, flag-icons für Länder; lokal gepinnte SVGs, Lizenzen und gemeinsame Zuordnung. Echte Browser-/PDF-Regressionsnachweise vorhanden; fachliche Druck- und physische Yodeck-Abnahme bleiben offen. |
| ICO-002 | Automatische Legenden | Seit `cc6c8ce` in Admin, Web, Signage und PDF produktiv. Nur tatsächlich dargestellte Allergene, Labels und Länder, dedupliziert und stabil sortiert; seitenbezogen auch bei Patientenrotation. «Enthält», «Kann enthalten» und «Nicht erfasst» bleiben getrennt; keine Frei-von-Aussage aus fehlenden Daten. Datenbestätigung bleibt DATA-001. |
| SCR-002 | Bestehendes Framework für öffentliche Seiten und Bildschirme | PS1–PS5 und alle vier öffentlichen Tabler-Seiten seit `118a644` produktiv: Hero-Food, Duo-Board, Wochenraster/Patientenrotation, Fotos/Fallback, Uhr, Rücknahmebehandlung, Ausfallpuffer höchstens fünf Minuten und Mitternachtssperre. Seit `0acd992` zusätzlich die beiden bildlosen Web-Wochenpläne live; vollständiges Paket und frische 386 Screens-Checks bestanden. Tatsächlicher Yodeck-Player bleibt QA-001. |
| SCR-001 | Ein gemeinsamer Adminpunkt **Screens** | Einstieg und echte Vorschauen produktiv: seit `0acd992` vier Karten und zehn Ansichten inklusive beider bildlosen Web-Wochenvarianten mit eigenen Tabs/Links; Signage-Direktlinks aus Sidebar entfernt. Vollständige Vorlagenverwaltung, kompatibler Vorlagenkatalog und aktive Zuordnungen bleiben offen. |
| TPL-001 | Neuer Adminpunkt **Vorlagen** | Navigation, Fachkatalog-Verknüpfungen und erste Wochen-PDF-Eigenschaftseditoren produktiv. Vollständige Bearbeitungsübersicht für Druckvorlagen, Screen-Vorlagen, Menüvorlagen sowie Zutaten/Komponenten und Menüs bleibt offen. Bestehende Fachkataloge und Editoren verknüpfen, keine doppelten Datenbestände. |

### 2. Verlässliche Betriebsgrundlage und Wochenpläne

UI-003 liefert die Referenzentscheidungen vor weiterem Admin-Polish; laufende Lieferungen warten darauf nicht. Kontrollierte Wochen-PDFs und der vorgezogene Vorlageneditor werden gemeinsam auf Einseitigkeit, Lesbarkeit und Überlauf geprüft. Zeiten und lokale Benutzerverwaltung sind unabhängige Pakete; ihre späteren Änderungen werden in den Ausgaben erneut geprüft.

**Weitere Admin-UI-Arbeit:** Das geprüfte [Tabler- und Symbolmanifest von Astra](design/2026-09-07-admin-tabler-icon-manifest.md) konkretisiert UI-003 und ICO-001/002: einheitliche Tabler-Komponenten, mehr eindeutige Symbole sowie Erklärungen bei Hover, Tastaturfokus und Antippen. Gemeint ist das **Tabler-Framework**, keine Tablet-Priorisierung. Menü-Iconaktionen und deklarierte VEG/VGN sind im geprüften Kandidaten `5b746b35` umgesetzt; Releasegate und Produktivabnahme stehen noch aus. Der vollständige Sollvertrag ist dadurch nicht pauschal erfüllt.

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| UI-003 | **MiseOS (Corral) als UI-/UX-Referenz auf Tabler übertragen** | [MiseOS-Referenz auf Corral](https://corral.dk/posts/final-thoughts/) geprüft; erste Adaption seit `0acd992` produktiv: sichtbare Komponenten-/Herkunfts-/Allergenlabels, stabile Formularbezüge, eindeutige Bearbeiten-Aktionen und korrekter Fehlerfokus. Unabhängige Vergleichs-/Formulargates, vollständiges Paket und frische Live-Abnahme bestanden. Gesamter Admin bleibt Tabler, mit kompaktem Standard und Touch-Zielen. Weiteren Referenzumfang zu Typografie, Abständen, Aktionsgrössen und Hierarchie anhand konkreter offener Bedienprobleme abnehmen; die erste Adaption ist keine pauschale Fertigmeldung sämtlichen Admin-Polishs. |
| TPL-003 | Zwei kontrollierte Wochen-Druckvorlagen | Produktiv und nach `3d35cbb` für Woche 2026-08-31 mit echten Downloads geprüft: 10 Cafeteria-/28 Patientenfotos, jeweils eine PDF-Seite und gleiche Karten. Cafeteria A4 hoch, Patienten ganze Woche A4 quer ohne Preise. Referenzlayout und Labels erhalten; Überlauf vor Aktivierung/Druck verweigern, kein Abschneiden oder unlesbares Verkleinern. Beide HTML-Druckprofile haben seit `3690e04` auch mobil gleich grosse Menükarten. Fachliche Druckabnahme bleibt offen. |
| OPS-001 | **Bereiche & Zeiten** | Seit `3d35cbb` mit Schema 20 produktiv; vollständige Paketprüfung und frische lesende OPS-/datierte Admin-Liveprüfung bestanden, siehe aktuellen Stand. Anzeigenamen wie Mitarbeitende, Patienten oder Schüler; Cafeteria-Öffnungszeiten und Patienten-Essenszeiten, Wochentage, Schliessungen und datierte Ausnahmen. Anzeigenamen ändern keine technischen Profil- oder Berechtigungsschlüssel. Zusätzliche unabhängige Bereiche sind eine eigene Modellerweiterung. |
| IAM-001 | **Benutzer & Zugriff** | Seit `3690e04` mit Schema 19 produktiv: Kontenliste/-detail, Kontoereignisse und vollständige Tabler-Verwaltung einschliesslich Guard-/Ausfallkorrekturen; Anlegen, Rollen ersetzen, Passwort zurücksetzen, Deaktivieren/Reaktivieren, originale Actor-/Zielversionen, letzter lokaler Admin, atomarer Audit und Sessionwiderruf. Unabhängige Kern-/UI-/Typ-/Schema-Gates und vollständige Paketprüfung bestanden; frische lesende Live-Abnahme mit 208 Checks/12 PNG. Kein produktiver IAM-Schreibtest. Vollständiger Login-/Logout-Zugriffsverlauf bleibt gesondert offen. |

### 3. Stammdaten, Rezepte und geprüfte Datenimporte

BAS-001 legt wiederverwendbare Zutaten, Einheiten und Kategorien für REC-001 fest; vorhandene Bestände bleiben nutzbar. Danach Suche und Importwege auf denselben Rezeptvertrag aufbauen. Produktdaten und Open Food Facts können parallel als manuell freizugebender Importkanal folgen. Format- und Lizenzprüfung für Pauli früh in REC-004 klären; der spätere PKS-Anschluss blockiert andere Importe nicht. Bestandsbuchungen folgen in Phase 5.

**Begonnen, im aktuellen Code-Stand enthalten:** B1 `e0fb93e` (ursprünglich `c7873fa`) liefert reine Mengen-/Einheitenlogik und Tests.
Root hat den vollständigen 433-Zeilen-Diff gelesen und selbst **101 passed in 1.26s**, Ruff PASS
und Mypy PASS für zwei Dateien bestätigt ([JUnit](/tmp/dishboard-root-quantities-b1-0906.xml)).
B1 ist mit `3d35cbb` produktiv; Produktion verwendet Schema 20.
[Gemeinsamer Vertrag](design/2026-09-06-bas-rec-data-contract.md) und
[Arbeitspakete](superpowers/bas-rec-work-packages-0906.md) trennen B1 von B2, das nach erfüllter OPS-Schema-20-Voraussetzung
aktiv umgesetzt wird. Schema 21 ist für B2 reserviert, nicht produktiv. BAS-001/REC-001 und ihr vollständiger Restumfang bleiben offen.

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| BAS-001 | **Grundlagen & Lager** nach Tandoors Datenbankbereich | Zentrale Pflege von Zutaten/Lebensmitteln, Komponenten, Einheiten, Kategorien und Tags; Lagerorte und Bestände mit Rezepten und Einkaufslisten verbinden. Vorhandene Stammdaten wiederverwenden. Tandoors tatsächliche Lagerfunktionen gesondert prüfen; keine ungeprüfte Eins-zu-eins-Kompatibilität behaupten. |
| REC-001 | Rezeptverwaltung nach Vorbild **Tandoor** | Wiederverwendbare Rezepte mit Bildern, Zutaten/Mengen/Einheiten, Portionen, geordneten Schritten und Quellen; mit vorhandenen Menüs/Komponenten verbinden. Kochbücher und Sammlungen. **HugeRTE 1.0.13** auf Nutzerwunsch lokal browsergeprüft: Richtext funktioniert, eine Style-CSP-Verletzung bleibt; Silver erfüllt keine vollständige Tabler-Bedienoberfläche. [Beleg und Primärquellen](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md). Vollständige CSP-/Tabler-Integration und Produktabnahme offen; keine Technologiefreigabe oder Produktdependency-Installation. |
| REC-006 | Anpassbare Suche und Tags | PostgreSQL-Volltext und Trigram-Ähnlichkeit, Filter für Rezept-/Zutaten-/Tagdaten, speicherbare Suche; Tags erstellen/suchen und gesammelt auf bestätigte Filtertreffer anwenden. |
| REC-005 | Rezepte von Webseiten importieren | Schema.org-Rezepte aus JSON-LD und Microdata übernehmen, Quelle erhalten, Vorschau und Korrektur vor Speicherung. Bestehende Parser prüfen; keine Zusage für jede Website. |
| REC-004 | Flexible Sammlungsimporte | Andere Rezeptmanager, Excel/XLSX, CSV, JSON und **Pauli Kitchen Solution** berücksichtigen; Dateivorschau, Feldzuordnung, Dubletten und Fehlerprotokoll. Konkrete Pauli-Exportversion/Formate anhand echter Beispieldaten klären; Unterstützung nicht vorab behaupten. |
| NUT-001 | Produktdaten für Allergene und Nährwerte | Strukturierte, quellenbezogene Produkt-/Lieferantendaten importieren und pflegen; Rezept-/Portionsbezug, Aktualisierungen und fehlende Angaben klar behandeln. KI-Schätzwerte getrennt von bestätigten Quelldaten. |
| OFF-001 | **Open Food Facts durch AGY evaluieren** | Tatsächliche AGY-Bewertung und unabhängige Quellenkorrektur abgeschlossen: positiv für Barcode-Importvorschläge. Integration und Schweizer Abdeckungsmessung offen. Barcode/EAN, Produkte/Zutaten, Allergene und Spuren getrennt, Nährwerte, Herkunft, Bilder sowie API/SDK berücksichtigen. Nur Importvorschläge mit manueller Freigabe; bestätigte Daten niemals automatisch überschreiben. Lizenzzuordnung im Entwurf §12; keine ungeprüften API-Limits übernehmen. |

### 4. Rezepte im Alltag nutzen

Planung und Einkaufslisten bauen auf Rezepten, Portionen und Einheiten auf. Rezeptdruck nutzt die vorhandene Vorlagen-/Druckbasis; der umfassende visuelle PDF-Editor ist keine Voraussetzung für nutzbare Ausdrucke. KI ergänzt die bestätigten Daten und Abläufe, sie blockiert weder manuelle Rezeptpflege noch Planung.

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| REC-003 | Rezeptplanung und Einkaufslisten | Rezepte mit Portionszahlen in bestehende Tages-/Wochenplanung aufnehmen; Einkaufszettel aus Plan oder Rezeptauswahl, Mengen/Einheiten sinnvoll zusammenführen, ergänzen und abhaken. Einkaufslisten druckbar. |
| REC-007 | **Rezepte drucken und Drucklayout bearbeiten** | Rezept- und Einkaufslisten-PDFs unter Vorlagen, mit editierbarem Layout, Logo, Zutaten, Portionen, Schritten, Bildern und Legenden. Sinnvolle Seitenumbrüche für lange Rezepte; Einseitenpflicht gilt weiterhin für Wochenpläne. |
| REC-002 | KI-Hilfen für Rezepte | Bilder/Dokumente erkennen, Rezeptschritte strukturieren und sortieren, Zutaten zuordnen, Nährwerte und weitere Metadaten vorschlagen. Quellen und Schätzstatus anzeigen; menschliche Prüfung vor Übernahme. |

### 5. Kosten, Warenfluss und Bestellvorbereitung

Kalkulation und Inventur können auf gemeinsamen Mengen-/Einheitendaten parallel entstehen. Verlässliche Einkaufspreise, Bestände und Bedarf aus Phase 4 werden für Bestellvorschläge zusammengeführt. Bestellungen bleiben ausdrücklich freizugebende Aktionen.

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| CALC-001 | Warenaufwand und Menüpreiskalkulation | Einkaufspreise, Mengen, Portionen, Ausbeute/Verlust und Einheiten nachvollziehbar in Rezept-/Menükosten überführen; Kalkulationsvorgaben und Preisvorschläge. Bestehende Patientenansichten bleiben ohne Preise. |
| INV-001 | Warenwirtschaft und Inventur | Zugänge, Abgänge, Umbuchungen, Zählung und Korrekturen mit Lagerorten, Einheiten und Verlauf; Einkaufs-/Planungsdaten anbinden. Tatsächliche Bestände nicht allein durch Planänderung abbuchen. |
| ORD-001 | Automatisierte Bestellvorbereitung | Bedarf aus Menüplanung/Produktion/Bestand ableiten, Lieferantenwarenkörbe und Bestellvorschläge erstellen; genehmigte Exporte/Schnittstellen nutzen. Verbindliches Absenden als ausdrücklich bestätigte Aktion; unbeaufsichtigte Bestellung ist nicht als bereits vorhandene Funktion belegt. |

### 6. Optionale Anbindungen und freier Screen-Editor

Entra setzt einen funktionierenden lokalen Admin und Rückweg voraus, blockiert lokale Benutzerverwaltung jedoch nicht; bei betrieblichem Bedarf kann IAM-002 nach IAM-001 vorgezogen werden. Pauli und Übersetzung folgen geklärten Nutzungsrechten und Importverträgen. Der freie Screen-Editor baut auf bewährten Layouts, Datenfeldern und Veröffentlichungsregeln auf; Tabler-Nachweis bleibt Voraussetzung der Technologiefreigabe. Der PDF-Vorlageneditor ist auf Nutzerwunsch in Phase 1 vorgezogen.

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| IAM-002 | Microsoft-Entra-ID-Verbindungen konfigurieren | Verbindungsentwurf, Test, Aktivierung und Rückweg; geschützte Secret-Verwaltung. Bestehende Anmeldung während Einrichtung erhalten. Mehrere Entwürfe, zunächst eine aktive Verbindung. |
| PKS-001 | Umfangreiche Rezeptdatenbank / Pauli-Anbindung | Eigene und importberechtigte Rezeptbestände aufnehmen. Anbieterangabe: über 4'400 PKS-Rezepte, davon laut Optisoft 1'655 Pauli-Rezepte. Dieser Bestand ist nicht automatisch in Dishboard enthalten. Export-/Servermodul und Nutzungsumfang klären. |
| TRN-001 | Gastro-Übersetzer | Fachbegriffe und Rezept-/Menütexte für Deutsch, Französisch, Englisch, Italienisch und Spanisch. Quellen, Synonyme und Fachprüfung; Anbieterumfang von rund 50'000 Begriffen als Referenz, keine ungeprüfte Übernahme eines geschützten Wörterbuchbestands. |
| SCR-003 | Visueller Screen-Editor aus bestehendem GitHub-Projekt | Layout, Logo, Farben und erlaubte Inhaltsblöcke bearbeiten; GrapesJS Core als bedingter Kandidat, Puck als Alternative. Vollständige Tabler-Bedienoberfläche und generische responsive Touch-Bedienung vor Technologiefreigabe prüfen; eine Tabler-Shell allein genügt nicht. |

**Gemeinsame Lieferregel:** Jede Veröffentlichung braucht die zum geänderten Umfang passenden unabhängigen Gates und Live-Nachweise. Schemaänderungen mit dem aktuellen Schemastand und gemeinsamen Deploys abstimmen: Produktion läuft auf Schema 20; Schema 21 ist reserviert und wird separat koordiniert und abgenommen. Funktionsumfang und Abnahmebedingungen der einzelnen IDs bleiben auch bei paralleler Ausführung verbindlich.

## REC-001 bis REC-007 — Tandoor als Referenz

Auf Nutzerwunsch neu aufgenommen am 5. September 2026. [Tandoor-Repository](https://github.com/TandoorRecipes/recipes) als Funktions-, UX- und Wiederverwendungsreferenz untersuchen; passende vorhandene Bausteine bevorzugen. Übernommene Dateien mit Ursprung, Version und Lizenz dokumentieren. Der geprüfte Lizenztext enthält AGPL v3 plus Commons Clause; Hobby-Nutzung ersetzt nicht die Lizenzbedingungen. [Lizenz](https://github.com/TandoorRecipes/recipes/blob/develop/LICENSE.md)

Die angegebene [Demo](https://app.tandoor.dev/) leitet bei der Prüfung auf eine Anmeldeseite weiter. Funktionen hinter der Anmeldung sind damit **noch nicht interaktiv geprüft**. README/Primärdokumentation wurden gelesen. Dishboard-Erweiterungen wie Pauli-/Excel-Adapter und visueller PDF-Vorlageneditor nicht als bereits von Tandoor bereitgestellt ausgeben. Architektur- und Abnahmeregeln stehen im [Entwurf, Abschnitt 10](design/2026-09-05-screens-vorlagen-verwaltung.md#10-rezepte-kochbücher-und-einkauf-nach-tandoor).

## PKS-001 bis TRN-001 — Kalkulation, Warenwirtschaft und Fachwissen

Auf Nutzerwunsch neu aufgenommen. [Optisoft Produkte](https://optisoft.ch/preise-und-produkte/) belegt Rezeptbestand, Produktdaten und Kalkulation; [Lightspeed](https://www.lightspeedhq.de/integrationen/paulis-kitchen-solution/) nennt zusätzlich den Gastroübersetzer und fünf Sprachen. Der [Pauli-Verlag](https://pauliph.com/) beschreibt seinen eigenen Rezeptkatalog; ihn nicht mit dem gesamten PKS-Bestand gleichsetzen.

[Exportbeschreibung, Juni 2021](https://optisoft.ch/wp-content/uploads/2021/06/Export-Fremdprogramme.pdf) und [Produktübersicht, Juni 2023](https://optisoft.ch/wp-content/uploads/2023/06/230616_Produktuebersicht-und-Preise.pdf) nennen Export-/Serverzugang, Warenkorb, Lager und Inventur. Historische Herstellerunterlagen sind kein Nachweis einer heute offen dokumentierten allgemeinen API. Konkreten Anschluss mit aktuellem Anbieterformat und berechtigten Daten prüfen. Weitere Ausarbeitung im [Entwurf, Abschnitt 11](design/2026-09-05-screens-vorlagen-verwaltung.md#11-kalkulation-warenwirtschaft-und-gastro-übersetzer).

## API-001 — REST-API v1, MCP, FHIR R5 und API-Schlüssel

**Historischer Status vor dem API-Deploy um 04:55 Uhr:** Seit Nutzerentscheid vom 06.09.2026, 01:55 Uhr übernimmt Codex allein. Übergabestand war `37d00b7`; damaliger Kandidat war `69ef540`. Backup-Fix `05b7985` ist mit 58 Tests und unabhängigem Teilgate über elf Tests geprüft. Gate 4 ist historisch fehlgeschlagen; Blueprint-Gate 5 auf `d70460c` ist mit `3417 passed, 15 skipped in 945.28s` abgeschlossen, Log `/tmp/menuplan-api-bootstrap-integration-full-5-0906.log`. Root-Gate 6 auf `8316790` endete mit `3592 passed, 1 failed, 31 errors, 15 skipped in 1153.23s`; die Testvertragskorrektur `d8fd9d3` ist als `69ef540` integriert. Der vollständige Wiederholungslauf über 3710 Tests ist mit **3695 bestanden, 15 Opt-in-Skips und viermal `GATE_EXIT=0`** abgeschlossen, Logs `/tmp/dishboard-release-shard-{0,1,2,3}-0906.log`. Die Skips waren **14 Restore-Drills und ein Compose-Test**, kein gemeinsamer Restore-Block. Damals blieb Produktion `1bff82e` auf Schema 16. Der spätere Schema-19-Release `3690e04` und die danach separat bestandenen 14 Restore-Opt-ins sind oben historisch belegt; aktuell produktiv ist `3d35cbb` auf Schema 20.

**Historischer Recovery-Nachweis:** `5a5f98b` (A1: sachfremden TRUNCATE entfernt), `6bc1cc7` (D: Schema-17-Testannahme); damaliges D-Gate `153 passed in 80.18s (0:01:20)`, `GATE_EXIT=0`. Dieser Teilnachweis ersetzt das aktuelle Integrationsgate nicht.

**Umfang:** Dokumentierte REST-API v1 mit OpenAPI 3.1 und lokalem Swagger UI, FHIR-R5-Leseschnittstelle, MCP-Server sowie API-Schlüssel mit Admin-Verwaltung unter `/admin/api`.

**Quellen und vorhandene Planung:**

- Übergabe: `/nvmetank1/projects/menuplan/UEBERGABE-CODEX-API-2026-09-05.md` (insbesondere §4 und §6); dortige Lane-Stände bei Wiederaufnahme neu prüfen.
- Koordination: `/nvmetank1/projects/menuplan/KOORDINATION-API-CODEX-2026-09-05.md`, massgeblich §ÜBERGABE 01:55 und Nachtrag 02:00 für Übernahme, laufendes Gate, Migration und Restarbeiten.
- Spec: `docs/superpowers/specs/2026-09-05-dishboard-api-mcp-fhir-design.md`, Branch `docs/api-mcp-fhir-spec-0905`, Commit `5e4750f`.
- Briefs und Logs: `.claude/state/api-mcp-fhir-0905/`.

**Historischer Liefer- und Prüfablauf der API-Welle:** Dieser Ablauf führte zum bereits belegten Deploy `118a644`; er ist kein aktuell offener Migrationsauftrag. Neue Lieferungen benötigen ihre eigenen aktuellen Gates.

1. Die vier Test-Shards auf `69ef540` sind erfolgreich ausgewertet; Verteilung und vollständige Abdeckung stehen in `/tmp/dishboard-release-shards-0906.json`. Die 14 Restore-/der eine Compose-Opt-in-Skip bleiben gesondert offen. Alte Läufe 3–6 nicht als laufend wiederaufnehmen. Fehlende DB-Umgebung, Fehler oder ungeprüfte Skips sind kein grüner Nachweis; Testpools exklusiv zuordnen.
2. Codex übernimmt die integrierten Wellen, prüft Abschlusslogs und vollständigen Diff, führt offene Ruff-, Schema-, Swagger-Asset- und Offline-Paketprüfungen aus, aktualisiert API-Dokumentation und Manifest. Schema/Schlüssel-Store, REST, FHIR, MCP, Swagger, Admin-Verwaltung und schlüsselgeschützte Endpunkte bleiben Bestandteil der Abnahme.
3. Unabhängige Reviews und Gates gegen den endgültigen Integrationsstand abschliessen. Externe OCR-Läufe sind nach 429/Timeout beziehungsweise null abgeschlossenen Modell-Tokens nicht verfügbar und dürfen nicht als CLEAN gelten. Native Browser-/PDF-Belege ersetzen weder einen ausgeführten Gemini-Design-Validator noch die physische Yodeck-Abnahme. **Den alten `gate.sh`-Aufruf nicht blind ausführen:** Er verweist auf eine gelöschte Datenbank. Aktuelle Wrapper und exklusiv zugeordnete Testdatenbanken verwenden; Swagger-Artefakte offline verifizieren.
4. Erst nach erfolgreichen unabhängigen Gates integriert Codex die Lieferung und deployt nach bestehendem Runbook: Backup, kontrollierte Migration **16→17**, danach Smokes für `/api/v1/status`, `/api/v1/docs`, `/fhir/metadata` und authentifiziert `/admin/api`. Schlüssel ausschliesslich über die Admin-Verwaltung erzeugen; Klartext nicht in Chat oder Logs übernehmen. Fremde Änderungen und Worktrees erhalten.
