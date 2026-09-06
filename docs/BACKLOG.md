# Backlog

## Aktueller Stand — Deployment vom 6. September 2026, 11:14:04 Uhr Schweiz

**Produktiv ist `0acd992` seit 11:14:04 Uhr**, Image `sha256:110bbc6ce858cc881b825d0b2b78c282c727ca804fc0ccbafb983e881aaa7e30`, Schema **18**, Container frisch als `healthy` bestätigt, externe Readiness HTTP 200. Vollständige unabhängige Paketprüfung: **3877 Tests bestanden, 15 ausdrücklich optionale Compose-/Restore-Skips, keine Fehler oder Fehlschläge**, `PACKAGE_GATE_EXIT=0`. Frisch nach diesem Neustart: **386 Screens-Checks und 194 API-/Admin-/PDF-Checks bestanden**, insgesamt 38 neue Screenshots; beide Einseiten-Wochen-PDFs erneut heruntergeladen. Backup vor Deployment mit Hash und TOC geprüft, kein Restore-Drill behauptet. [Aktueller Releasebeleg](/nvmetank1/projects/rag-stack/.claude/reports/wp-8b57137108b3.md).

**Neu live:** zusätzliche bildlose Web-Wochenpläne für Cafeteria und Patienten mit eigenem Vorschau-Tab und Link in Screens, insgesamt vier Karten/zehn Vorschauen; UI-003 verbessert sichtbare Editorlabels, Kontext der Bearbeiten-Links und Fehlerfokus. Bildlose Signage-Wochen gab es bereits. Zentraler Branding-Editor, sichere Logo-/Farb-/Schriftpflege und gemeinsame Menü-Legenden bleiben seit `cc6c8ce` produktiv; dessen [früherer Releasebeleg](/nvmetank1/projects/rag-stack/.claude/reports/wp-6102b5a04b76.md) bleibt historischer Nachweis.

**IAM-001 in Abnahme, noch nicht ausgeliefert:** Kern, Konten-/Ereignisleser und vollständige Tabler-Verwaltungsoberfläche sind mit Guard-/Ausfallkorrekturen integriert. Unabhängiger Root-Gate über 17 vollständige Module: **284 bestanden, 59 Warnungen in 216.40 Sekunden**, `GATE_EXIT=0` (`/tmp/dishboard-root-iam-integrated-gate-0906.log`). Ruff über Datenbank-, Tool- und Anwendungscode bestanden. Mypy nach Testfix `374e9da` unabhängig bestanden: `Success: no issues found in 15 source files`. Schema-19-Migration und Baseline-Gleichheit ebenfalls unabhängig auf echtem PostgreSQL bestätigt. Die vollständige gemeinsame Release-/Paketabnahme bleibt offen. **Schema 19 ist nicht produktiv und IAM noch nicht deploybereit.** Vollständiges Login-/Logout-Zugriffsprotokoll bleibt ein gesonderter offener Umfang.

Die neue Branding-Browserprüfung erreichte 798 Checks/40 Screenshots, blieb aber wegen 21 Befunden FAIL. Unabhängige öffentliche Diagnose: 19 Geometrie-Fehlalarme bei vollständig sichtbarem Text mit `overflow:visible`; eine echte Höhenabweichung in der mobilen Patienten-HTML-Druckansicht (390 px), ohne abgeschnittenen Inhalt; ein früherer Logo-Status-/MIME-Befund noch ungeklärt, bei frischer Diagnose nicht reproduziert. Diese Grenzen bleiben offen. Fachliche Küchenbestätigung, physischer Yodeck-Player und externer Design-Validator sind weiterhin separate Abnahmen.

Alle **35 Backlog-IDs** bleiben mit ihrem vollständigen Umfang erhalten. Die grossen Rezept-, Stammdaten-, Nährwert-, Kalkulations-, Lager-, Bestell- und freien Editorpakete sind weiterhin offen. Ältere «lokal vorbereitet»-Angaben unten werden durch diesen Stand ersetzt, nicht als weitere Lieferung gezählt.

**Gruppierter Bestand, keine Abschlussquote:** Die folgenden Gruppen enthalten jede Tabellen-ID genau einmal. «Produktive Funktionen» umfasst ausdrücklich Teilfunktionen und offene Abnahmefälle; es bedeutet nicht, dass 14 vollständige Backlogaufträge erledigt sind.

| Gruppe | Anzahl | IDs / verbleibende Grenze |
|---|---:|---|
| Produktive Funktionen | 14 | UI-001, UI-002, UI-003, CAT-001, DSP-001, BRD-001, API-001, ICO-001, ICO-002, SCR-001, SCR-002, TPL-001, TPL-002, TPL-003. Die jeweilige Releaseprüfung ist abgeschlossen; TPL-001/002 und SCR-001 haben erst Teilfunktionen. Offene Daten-, Druck-, Branding- und Playerabnahmen stehen weiterhin in den Einzelzeilen. |
| Implementiert, in Abnahme | 1 | IAM-001: A/B/C und Guard-/Ausfallkorrekturen integriert; Typprüfung und Schema-Gate unabhängig bestanden, gemeinsame Releaseabnahme offen, kein Schema-19-Deploy. |
| Grössere Umsetzung offen | 18 | OPS-001, BAS-001, REC-001–REC-007, NUT-001, OFF-001, CALC-001, INV-001, ORD-001, IAM-002, PKS-001, TRN-001, SCR-003. Vorhandene Referenzanalysen und Stammdaten ersetzen diese Funktionen nicht. |
| Fortlaufende Abnahme | 2 | QA-001 und DATA-001; technische Lieferungen ersetzen weder physische Player- noch fachliche Küchenbestätigung. |

## Historischer Deploy-Nachtrag — 6. September 2026, 04:55:35 Uhr Schweiz

Dieser Abschnitt beschreibt den damaligen Schema-17-Deploy; aktueller Release und Schema 18 stehen oben.

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
| BRD-001 | **Design & Marke** | Seit `cc6c8ce` produktiv: Darstellungseinstellungen sowie zentrale Logo-, Farb- und Schriftpflege mit sicherem Upload, Vorschau, Entwürfen, Aktivierung und Wiederherstellung. Admin/Web/Signage übernehmen die aktive Marke; Druckvorlagen können sie ausdrücklich erben. Vollständige Paketprüfung grün; verbleibende Browser-/Druckkarten-/Player-Abnahme siehe aktuellen Stand. |
| TPL-002 | **Visueller PDF-Druckvorlageneditor** | Erster Tabler-Eigenschaftseditor auf fpdf2 seit `118a644` produktiv: speichern, kopieren, echte PDF-Vorschau, aktivieren und frühere Revision als neuen Entwurf übernehmen. Logos, Farben, Schrift, Ränder, Zellenabstände und Kopf-/Fusszusatz; aktive Marke seit `cc6c8ce` als ausdrückliche Auswahl. Offen: freie Druckgestaltung mit Spalten, Bildern, Symbolen, Legenden und Datenfeldern. Offizieller pdfme-Designer erfüllt nach geprüfter Analyse die vollständige Tabler-Oberfläche nicht; Generator separat prüfbar, keine Editor-Technologiefreigabe. |
| API-001 | REST-API v1, MCP, FHIR R5 und API-Schlüssel | Seit `118a644` um 04:55 Uhr produktiv, einschliesslich Migration 16→17. Unabhängige vollständige Suite 3695 bestanden/15 Opt-in-Skips, Paketprüfung und Live-Abnahme durchgeführt. Nach Branding-Deployment aktuelle API-/FHIR-/Admin-Verträge erneut im erfolgreichen 194-Checks-Lauf geprüft. Historische Gatefehler und Korrekturen stehen im Releasebeleg; externe Clientanbindungen bleiben getrennte Betriebsaufgaben. |
| ICO-001 | Allergen-Symbole und Herkunftsflaggen in Admin, Web, Signage und PDF | Gemeinsame Symbole und sämtliche Web-/Signage-/PDF-Verbraucher seit `cc6c8ce` produktiv. Erudus für 14 Allergengruppen, flag-icons für Länder; lokal gepinnte SVGs, Lizenzen und gemeinsame Zuordnung. Echte Browser-/PDF-Regressionsnachweise vorhanden; fachliche Druck- und physische Yodeck-Abnahme bleiben offen. |
| ICO-002 | Automatische Legenden | Seit `cc6c8ce` in Admin, Web, Signage und PDF produktiv. Nur tatsächlich dargestellte Allergene, Labels und Länder, dedupliziert und stabil sortiert; seitenbezogen auch bei Patientenrotation. «Enthält», «Kann enthalten» und «Nicht erfasst» bleiben getrennt; keine Frei-von-Aussage aus fehlenden Daten. Datenbestätigung bleibt DATA-001. |
| SCR-002 | Bestehendes Framework für öffentliche Seiten und Bildschirme | PS1–PS5 und alle vier öffentlichen Tabler-Seiten seit `118a644` produktiv: Hero-Food, Duo-Board, Wochenraster/Patientenrotation, Fotos/Fallback, Uhr, Rücknahmebehandlung, Ausfallpuffer höchstens fünf Minuten und Mitternachtssperre. Seit `0acd992` zusätzlich die beiden bildlosen Web-Wochenpläne live; vollständiges Paket und frische 386 Screens-Checks bestanden. Tatsächlicher Yodeck-Player bleibt QA-001. |
| SCR-001 | Ein gemeinsamer Adminpunkt **Screens** | Einstieg und echte Vorschauen produktiv: seit `0acd992` vier Karten und zehn Ansichten inklusive beider bildlosen Web-Wochenvarianten mit eigenen Tabs/Links; Signage-Direktlinks aus Sidebar entfernt. Vollständige Vorlagenverwaltung, kompatibler Vorlagenkatalog und aktive Zuordnungen bleiben offen. |
| TPL-001 | Neuer Adminpunkt **Vorlagen** | Navigation, Fachkatalog-Verknüpfungen und erste Wochen-PDF-Eigenschaftseditoren produktiv. Vollständige Bearbeitungsübersicht für Druckvorlagen, Screen-Vorlagen, Menüvorlagen sowie Zutaten/Komponenten und Menüs bleibt offen. Bestehende Fachkataloge und Editoren verknüpfen, keine doppelten Datenbestände. |

### 2. Verlässliche Betriebsgrundlage und Wochenpläne

UI-003 liefert die Referenzentscheidungen vor weiterem Admin-Polish; laufende Lieferungen warten darauf nicht. Kontrollierte Wochen-PDFs und der vorgezogene Vorlageneditor werden gemeinsam auf Einseitigkeit, Lesbarkeit und Überlauf geprüft. Zeiten und lokale Benutzerverwaltung sind unabhängige Pakete; ihre späteren Änderungen werden in den Ausgaben erneut geprüft.

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| UI-003 | **MiseOS (Corral) als UI-/UX-Referenz auf Tabler übertragen** | [MiseOS-Referenz auf Corral](https://corral.dk/posts/final-thoughts/) geprüft; erste Adaption seit `0acd992` produktiv: sichtbare Komponenten-/Herkunfts-/Allergenlabels, stabile Formularbezüge, eindeutige Bearbeiten-Aktionen und korrekter Fehlerfokus. Unabhängige Vergleichs-/Formulargates, vollständiges Paket und frische Live-Abnahme bestanden. Gesamter Admin bleibt Tabler, mit kompaktem Standard und Touch-Zielen. Weiteren Referenzumfang zu Typografie, Abständen, Aktionsgrössen und Hierarchie anhand konkreter offener Bedienprobleme abnehmen; die erste Adaption ist keine pauschale Fertigmeldung sämtlichen Admin-Polishs. |
| TPL-003 | Zwei kontrollierte Wochen-Druckvorlagen | Produktiv und nach `cc6c8ce` erneut mit echten Downloads geprüft: Cafeteria eine A4-Seite hoch, Patienten ganze Woche auf einer A4-Seite quer ohne Preise. Referenzlayout und Labels erhalten; Überlauf vor Aktivierung/Druck verweigern, kein Abschneiden oder unlesbares Verkleinern. Fachliche Druckabnahme bleibt offen. Die separate mobile HTML-Druckkartenabweichung ist oben dokumentiert. |
| OPS-001 | **Bereiche & Zeiten** | Anzeigenamen wie Mitarbeitende, Patienten oder Schüler; Cafeteria-Öffnungszeiten und Patienten-Essenszeiten, Wochentage, Schliessungen und datierte Ausnahmen. Anzeigenamen ändern keine technischen Profil- oder Berechtigungsschlüssel. Zusätzliche unabhängige Bereiche sind eine eigene Modellerweiterung. |
| IAM-001 | **Benutzer & Zugriff** | Kern, Kontenliste/-detail, Kontoereignisse und vollständige Tabler-Verwaltung einschliesslich Guard-/Ausfallkorrekturen integriert: Anlegen, Rollen ersetzen, Passwort zurücksetzen, Deaktivieren/Reaktivieren, originale Actor-/Zielversionen, letzter lokaler Admin, atomarer Audit und Sessionwiderruf. Root-17-Modul-Gate: 284 bestanden, 59 Warnungen, `GATE_EXIT=0`; Mypy nach Testfix `374e9da` und Schema-19-Gate unabhängig bestanden. Gemeinsame Release-/Paketabnahme offen, nicht deploybereit, keine Schema-19-Produktion. Vollständiger Login-/Logout-Zugriffsverlauf bleibt gesondert offen. |

### 3. Stammdaten, Rezepte und geprüfte Datenimporte

BAS-001 legt wiederverwendbare Zutaten, Einheiten und Kategorien für REC-001 fest; vorhandene Bestände bleiben nutzbar. Danach Suche und Importwege auf denselben Rezeptvertrag aufbauen. Produktdaten und Open Food Facts können parallel als manuell freizugebender Importkanal folgen. Format- und Lizenzprüfung für Pauli früh in REC-004 klären; der spätere PKS-Anschluss blockiert andere Importe nicht. Bestandsbuchungen folgen in Phase 5.

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| BAS-001 | **Grundlagen & Lager** nach Tandoors Datenbankbereich | Zentrale Pflege von Zutaten/Lebensmitteln, Komponenten, Einheiten, Kategorien und Tags; Lagerorte und Bestände mit Rezepten und Einkaufslisten verbinden. Vorhandene Stammdaten wiederverwenden. Tandoors tatsächliche Lagerfunktionen gesondert prüfen; keine ungeprüfte Eins-zu-eins-Kompatibilität behaupten. |
| REC-001 | Rezeptverwaltung nach Vorbild **Tandoor** | Wiederverwendbare Rezepte mit Bildern, Zutaten/Mengen/Einheiten, Portionen, geordneten Schritten und Quellen; mit vorhandenen Menüs/Komponenten verbinden. Kochbücher und Sammlungen. **HugeRTE** ist auf Nutzerwunsch Prüfkandidat für den künftigen Rezepteditor; vollständige Tabler-Bedienoberfläche, CSP und Eignung prüfen. Keine Technologiefreigabe oder Dependency-Installation erfolgt. |
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

**Gemeinsame Lieferregel:** Jede Veröffentlichung braucht die zum geänderten Umfang passenden unabhängigen Gates und Live-Nachweise. Schemaänderungen mit dem aktuellen Schemastand und gemeinsamen Deploys abstimmen: Produktion bleibt in dieser Lieferung auf Schema 18; IAM-Migration 18→19 wird getrennt abgenommen. Funktionsumfang und Abnahmebedingungen der einzelnen IDs bleiben auch bei paralleler Ausführung verbindlich.

## REC-001 bis REC-007 — Tandoor als Referenz

Auf Nutzerwunsch neu aufgenommen am 5. September 2026. [Tandoor-Repository](https://github.com/TandoorRecipes/recipes) als Funktions-, UX- und Wiederverwendungsreferenz untersuchen; passende vorhandene Bausteine bevorzugen. Übernommene Dateien mit Ursprung, Version und Lizenz dokumentieren. Der geprüfte Lizenztext enthält AGPL v3 plus Commons Clause; Hobby-Nutzung ersetzt nicht die Lizenzbedingungen. [Lizenz](https://github.com/TandoorRecipes/recipes/blob/develop/LICENSE.md)

Die angegebene [Demo](https://app.tandoor.dev/) leitet bei der Prüfung auf eine Anmeldeseite weiter. Funktionen hinter der Anmeldung sind damit **noch nicht interaktiv geprüft**. README/Primärdokumentation wurden gelesen. Dishboard-Erweiterungen wie Pauli-/Excel-Adapter und visueller PDF-Vorlageneditor nicht als bereits von Tandoor bereitgestellt ausgeben. Architektur- und Abnahmeregeln stehen im [Entwurf, Abschnitt 10](design/2026-09-05-screens-vorlagen-verwaltung.md#10-rezepte-kochbücher-und-einkauf-nach-tandoor).

## PKS-001 bis TRN-001 — Kalkulation, Warenwirtschaft und Fachwissen

Auf Nutzerwunsch neu aufgenommen. [Optisoft Produkte](https://optisoft.ch/preise-und-produkte/) belegt Rezeptbestand, Produktdaten und Kalkulation; [Lightspeed](https://www.lightspeedhq.de/integrationen/paulis-kitchen-solution/) nennt zusätzlich den Gastroübersetzer und fünf Sprachen. Der [Pauli-Verlag](https://pauliph.com/) beschreibt seinen eigenen Rezeptkatalog; ihn nicht mit dem gesamten PKS-Bestand gleichsetzen.

[Exportbeschreibung, Juni 2021](https://optisoft.ch/wp-content/uploads/2021/06/Export-Fremdprogramme.pdf) und [Produktübersicht, Juni 2023](https://optisoft.ch/wp-content/uploads/2023/06/230616_Produktuebersicht-und-Preise.pdf) nennen Export-/Serverzugang, Warenkorb, Lager und Inventur. Historische Herstellerunterlagen sind kein Nachweis einer heute offen dokumentierten allgemeinen API. Konkreten Anschluss mit aktuellem Anbieterformat und berechtigten Daten prüfen. Weitere Ausarbeitung im [Entwurf, Abschnitt 11](design/2026-09-05-screens-vorlagen-verwaltung.md#11-kalkulation-warenwirtschaft-und-gastro-übersetzer).

## API-001 — REST-API v1, MCP, FHIR R5 und API-Schlüssel

**Historischer Status vor dem API-Deploy um 04:55 Uhr:** Seit Nutzerentscheid vom 06.09.2026, 01:55 Uhr übernimmt Codex allein. Übergabestand war `37d00b7`; damaliger Kandidat war `69ef540`. Backup-Fix `05b7985` ist mit 58 Tests und unabhängigem Teilgate über elf Tests geprüft. Gate 4 ist historisch fehlgeschlagen; Blueprint-Gate 5 auf `d70460c` ist mit `3417 passed, 15 skipped in 945.28s` abgeschlossen, Log `/tmp/menuplan-api-bootstrap-integration-full-5-0906.log`. Root-Gate 6 auf `8316790` endete mit `3592 passed, 1 failed, 31 errors, 15 skipped in 1153.23s`; die Testvertragskorrektur `d8fd9d3` ist als `69ef540` integriert. Der vollständige Wiederholungslauf über 3710 Tests ist mit **3695 bestanden, 15 Opt-in-Skips und viermal `GATE_EXIT=0`** abgeschlossen, Logs `/tmp/dishboard-release-shard-{0,1,2,3}-0906.log`. Die Skips sind **14 Restore-Drills und ein Compose-Test**, kein gemeinsamer Restore-Block. Damals blieb Produktion `1bff82e` auf Schema 16; der API-Deploy `118a644` und der aktuelle Schema-18-Release `0acd992` sind inzwischen oben belegt.

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
