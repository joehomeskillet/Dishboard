# Backlog

Stand: **5./6. September 2026**. Diese Übersicht führt die offenen Nutzerwünsche zusammen. «In Arbeit» bedeutet weder gemergt noch produktiv. Die Tabler-Integration selbst ist bereits produktiv; [Nachweise und verbleibende Abnahme](design/tabler-integration-evidence-0905.md) sind separat dokumentiert.

**Verbindlicher Nutzerentscheid: Alles im Admin bleibt Tabler.** Das gilt für Formulare, Felder, Buttons, Dialoge, Navigation und sämtliche Fremdeditoren. Eine Tabler-Shell um eine fremde Bedienoberfläche genügt nicht. Tandoor und Pauli sind Funktionsvorbilder, kein Vue-/Vuetify-Ersatz für den Admin. GrapesJS, pdfme und andere Editor-Kandidaten dürfen erst nach nachgewiesener vollständiger Tabler-Bedienoberfläche freigegeben werden.

## Aktuelle Umsetzung

| ID | Auftrag | Status / Abnahme |
|---|---|---|
| UI-001 | Menüs: umschaltbare kompakte Listenansicht wie bei Komponenten, für beide Bereiche | In Arbeit; vorhandene Filter und Editorlinks erhalten, aktueller Prüfstatus, keine Patientenpreise; Browserprüfung bei 390 und 1440 px. |
| UI-002 | Öffentliche Seiten und Signage von technischen Angaben bereinigen | In Arbeit; Kanal, Revision, Auflösung und «Publizierter Datenstand» aus sichtbaren Ausgaben entfernen. Menüdaten, fachliche Hinweise, interne Header, Statuscodes und Veröffentlichungsschutz erhalten. |

## Geplante Erweiterungen

Gemeinsamer Entwurf mit Dateizuordnung und Arbeitspaketen: [Screens, Vorlagen und Verwaltung](design/2026-09-05-screens-vorlagen-verwaltung.md).

| ID | Auftrag | Umfang / noch offen |
|---|---|---|
| SCR-001 | Ein gemeinsamer Adminpunkt **Screens** | Öffentliche Ansichten und die vier vorhandenen Signage-Ziele für Cafeteria und Patienten zusammenführen; Links und aktive Zuordnung zentral verwalten. |
| SCR-002 | Bestehendes Framework für öffentliche Seiten und Bildschirme | Tabler/Bootstrap wiederverwenden; eigene lesbare Web- und TV-Layouts. Zielbrowser prüfen, keine zweite Bootstrap-Laufzeit laden. |
| SCR-003 | Visueller Screen-Editor aus bestehendem GitHub-Projekt | Layout, Logo, Farben und erlaubte Inhaltsblöcke bearbeiten; GrapesJS Core als bedingter Kandidat, Puck als Alternative. Vollständige Tabler-Bedienoberfläche und Touch-Bedienung auf Samsung vor Technologiefreigabe prüfen; eine Tabler-Shell allein genügt nicht. |
| TPL-001 | Neuer Adminpunkt **Vorlagen** | Zentrale Bearbeitungsübersicht für Druckvorlagen, Screen-Vorlagen, Menüvorlagen sowie Zutaten/Komponenten und Menüs. Bestehende Fachkataloge und Editoren verknüpfen, keine doppelten Datenbestände. |
| TPL-002 | **Visueller PDF-Druckvorlageneditor** | Gesamte Druckgestaltung bearbeiten: Logo, Farben, Schrift, Abstände, Spalten, Kopf/Fuss, Bilder, Symbole, Legenden und Datenfelder. pdfme als bedingter Prototyp-Kandidat: vollständige Tabler-Bedienoberfläche erforderlich, noch keine Rendererentscheidung. Vorlagen speichern, kopieren, Vorschau, aktivieren und zurücksetzen. Cursor/Grok-4.6-Versuche blieben durch Werkzeugfreigaben unvollständig; separate Codex-Recherche liegt vor. |
| TPL-003 | Zwei kontrollierte Wochen-Druckvorlagen | Cafeteria: eine A4-Seite hoch; Patienten: eine A4-Seite quer mit der ganzen Woche, ohne Preise. Referenzlayout Südhang und neue Labels erhalten; Überlauf vor Aktivierung/Druck erkennen. Kein Abschneiden und kein unlesbares automatisches Verkleinern. |
| BRD-001 | **Design & Marke** | Logo, Farbpalette und Typografie zentral pflegen; Vorschau für Admin, Web, Screen und Druck, mit sicherem Upload und rücksetzbarer Aktivierung. |
| DSP-001 | Globale **Darstellung**: kompakte Adminansicht als Standard | Zentral unter Design & Marke setzen; für alle Benutzer und Geräte. Seitenspezifische Schalter und Browser-Persistierung entfernen. Touch-Flächen, Pflicht-Hinweise und Fehlermeldungen erhalten. |
| OPS-001 | **Bereiche & Zeiten** | Anzeigenamen wie Mitarbeitende, Patienten oder Schüler; Cafeteria-Öffnungszeiten und Patienten-Essenszeiten, Wochentage, Schliessungen und datierte Ausnahmen. Anzeigenamen ändern keine technischen Profil- oder Berechtigungsschlüssel. Zusätzliche unabhängige Bereiche sind eine eigene Modellerweiterung. |
| IAM-001 | **Benutzer & Zugriff** | Benutzerverwaltung mit bestehenden Rollen und lokalen Konten; deaktivieren, Rollen/Passwort verwalten, Zugriffsprotokoll. Letzten funktionsfähigen lokalen Admin vor Aussperren schützen. |
| IAM-002 | Microsoft-Entra-ID-Verbindungen konfigurieren | Verbindungsentwurf, Test, Aktivierung und Rückweg; geschützte Secret-Verwaltung. Bestehende Anmeldung während Einrichtung erhalten. Mehrere Entwürfe, zunächst eine aktive Verbindung. |
| ICO-001 | Allergen-Symbole und Herkunftsflaggen in Admin, Web, Signage und PDF | Erudus für 14 Allergengruppen, flag-icons für Länder als recherchierte Auswahl; lokale, gepinnte SVGs, Lizenzen und gemeinsame Code-Zuordnung. Erkennbarkeit im Druck und auf Samsung noch prüfen. |
| ICO-002 | Automatische Legenden | Nur tatsächlich dargestellte Allergene, Labels und Länder, dedupliziert und stabil sortiert. «Enthält», «Kann enthalten» und «Nicht erfasst» unterscheiden; keine Frei-von-Aussage aus fehlenden Daten. |
| QA-001 | Echte Samsung-Geräteabnahme | Exaktes XCover-/Tabletmodell, Android und Browser noch unbekannt; Hoch-/Querformat, Bildschirmtastatur und Touch prüfen. Vorliegende Browser-Viewporttests ersetzen dies nicht. |
| CAT-001 | Fehlende Filter auf `/admin/cafeteria/komponenten` | Geplant: sichtbare kombinierbare Filterleiste für Kategorie, Verwendung in Menüs, Allergene, Labels, Herkunft und aktiv/archiviert; Zurücksetzen und Trefferzahl. Vorhandene Suche/Filter prüfen und gezielt ergänzen, Gültigkeit/Bereich aus dem Tabler-SDD abgrenzen; auf Tablets mit Tabler bedienbar. Noch keine Implementierung behauptet. |
| DATA-001 | Fachliche Bestätigung der Rezept-/Allergenangaben | Vorhandene Vorschläge durch Küche prüfen. Unbekannte Angaben bleiben unbekannt; fachliche Bestätigung wird nicht aus KI-Vorschlägen abgeleitet. |
| REC-001 | Rezeptverwaltung nach Vorbild **Tandoor** | Wiederverwendbare Rezepte mit Bildern, Zutaten/Mengen/Einheiten, Portionen, geordneten Schritten und Quellen; mit vorhandenen Menüs/Komponenten verbinden. Kochbücher und Sammlungen. |
| REC-002 | KI-Hilfen für Rezepte | Bilder/Dokumente erkennen, Rezeptschritte strukturieren und sortieren, Zutaten zuordnen, Nährwerte und weitere Metadaten vorschlagen. Quellen und Schätzstatus anzeigen; menschliche Prüfung vor Übernahme. |
| REC-003 | Rezeptplanung und Einkaufslisten | Rezepte mit Portionszahlen in bestehende Tages-/Wochenplanung aufnehmen; Einkaufszettel aus Plan oder Rezeptauswahl, Mengen/Einheiten sinnvoll zusammenführen, ergänzen und abhaken. Einkaufslisten druckbar. |
| REC-004 | Flexible Sammlungsimporte | Andere Rezeptmanager, Excel/XLSX, CSV, JSON und **Pauli Kitchen Solution** berücksichtigen; Dateivorschau, Feldzuordnung, Dubletten und Fehlerprotokoll. Konkrete Pauli-Exportversion/Formate anhand echter Beispieldaten klären; Unterstützung nicht vorab behaupten. |
| REC-005 | Rezepte von Webseiten importieren | Schema.org-Rezepte aus JSON-LD und Microdata übernehmen, Quelle erhalten, Vorschau und Korrektur vor Speicherung. Bestehende Parser prüfen; keine Zusage für jede Website. |
| REC-006 | Anpassbare Suche und Tags | PostgreSQL-Volltext und Trigram-Ähnlichkeit, Filter für Rezept-/Zutaten-/Tagdaten, speicherbare Suche; Tags erstellen/suchen und gesammelt auf bestätigte Filtertreffer anwenden. |
| REC-007 | **Rezepte drucken und Drucklayout bearbeiten** | Rezept- und Einkaufslisten-PDFs unter Vorlagen, mit editierbarem Layout, Logo, Zutaten, Portionen, Schritten, Bildern und Legenden. Sinnvolle Seitenumbrüche für lange Rezepte; Einseitenpflicht gilt weiterhin für Wochenpläne. |
| BAS-001 | **Grundlagen & Lager** nach Tandoors Datenbankbereich | Zentrale Pflege von Zutaten/Lebensmitteln, Komponenten, Einheiten, Kategorien und Tags; Lagerorte und Bestände mit Rezepten und Einkaufslisten verbinden. Vorhandene Stammdaten wiederverwenden. Tandoors tatsächliche Lagerfunktionen gesondert prüfen; keine ungeprüfte Eins-zu-eins-Kompatibilität behaupten. |
| PKS-001 | Umfangreiche Rezeptdatenbank / Pauli-Anbindung | Eigene und importberechtigte Rezeptbestände aufnehmen. Anbieterangabe: über 4'400 PKS-Rezepte, davon laut Optisoft 1'655 Pauli-Rezepte. Dieser Bestand ist nicht automatisch in Dishboard enthalten. Export-/Servermodul und Nutzungsumfang klären. |
| CALC-001 | Warenaufwand und Menüpreiskalkulation | Einkaufspreise, Mengen, Portionen, Ausbeute/Verlust und Einheiten nachvollziehbar in Rezept-/Menükosten überführen; Kalkulationsvorgaben und Preisvorschläge. Bestehende Patientenansichten bleiben ohne Preise. |
| NUT-001 | Produktdaten für Allergene und Nährwerte | Strukturierte, quellenbezogene Produkt-/Lieferantendaten importieren und pflegen; Rezept-/Portionsbezug, Aktualisierungen und fehlende Angaben klar behandeln. KI-Schätzwerte getrennt von bestätigten Quelldaten. |
| OFF-001 | **Open Food Facts durch AGY evaluieren** | Tatsächliche AGY-Bewertung und unabhängige Quellenkorrektur abgeschlossen: positiv für Barcode-Importvorschläge. Integration und Schweizer Abdeckungsmessung offen. Barcode/EAN, Produkte/Zutaten, Allergene und Spuren getrennt, Nährwerte, Herkunft, Bilder sowie API/SDK berücksichtigen. Nur Importvorschläge mit manueller Freigabe; bestätigte Daten niemals automatisch überschreiben. Lizenzzuordnung im Entwurf §12; keine ungeprüften API-Limits übernehmen. |
| INV-001 | Warenwirtschaft und Inventur | Zugänge, Abgänge, Umbuchungen, Zählung und Korrekturen mit Lagerorten, Einheiten und Verlauf; Einkaufs-/Planungsdaten anbinden. Tatsächliche Bestände nicht allein durch Planänderung abbuchen. |
| ORD-001 | Automatisierte Bestellvorbereitung | Bedarf aus Menüplanung/Produktion/Bestand ableiten, Lieferantenwarenkörbe und Bestellvorschläge erstellen; genehmigte Exporte/Schnittstellen nutzen. Verbindliches Absenden als ausdrücklich bestätigte Aktion; unbeaufsichtigte Bestellung ist nicht als bereits vorhandene Funktion belegt. |
| TRN-001 | Gastro-Übersetzer | Fachbegriffe und Rezept-/Menütexte für Deutsch, Französisch, Englisch, Italienisch und Spanisch. Quellen, Synonyme und Fachprüfung; Anbieterumfang von rund 50'000 Begriffen als Referenz, keine ungeprüfte Übernahme eines geschützten Wörterbuchbestands. |
| API-001 | REST-API v1, MCP, FHIR R5 und API-Schlüssel | Weiterhin zurückgestellt; bereits vorhandene Lanes erhalten. Ablauf unten. |

**Lieferfolge:** UI-001/UI-002 unabhängig fertigstellen und geprüft deployen; parallel Editor-Auswahl und Vorlagenentwurf konkretisieren. Danach Screens-/Vorlagen-Navigation, globale Darstellung und gemeinsame Symbolbasis; Branding, Bereiche/Zeiten und Benutzer/Entra in getrennten geprüften Paketen. API-001 wird durch diese Liste nicht automatisch wieder aufgenommen. Schemaänderungen vor Vergabe der nächsten Migration mit der reservierten API-Migration 16→17 abstimmen.

## REC-001 bis REC-007 — Tandoor als Referenz

Auf Nutzerwunsch neu aufgenommen am 5. September 2026. [Tandoor-Repository](https://github.com/TandoorRecipes/recipes) als Funktions-, UX- und Wiederverwendungsreferenz untersuchen; passende vorhandene Bausteine bevorzugen. Übernommene Dateien mit Ursprung, Version und Lizenz dokumentieren. Der geprüfte Lizenztext enthält AGPL v3 plus Commons Clause; Hobby-Nutzung ersetzt nicht die Lizenzbedingungen. [Lizenz](https://github.com/TandoorRecipes/recipes/blob/develop/LICENSE.md)

Die angegebene [Demo](https://app.tandoor.dev/) leitet bei der Prüfung auf eine Anmeldeseite weiter. Funktionen hinter der Anmeldung sind damit **noch nicht interaktiv geprüft**. README/Primärdokumentation wurden gelesen. Dishboard-Erweiterungen wie Pauli-/Excel-Adapter und visueller PDF-Vorlageneditor nicht als bereits von Tandoor bereitgestellt ausgeben. Architektur- und Abnahmeregeln stehen im [Entwurf, Abschnitt 10](design/2026-09-05-screens-vorlagen-verwaltung.md#10-rezepte-kochbücher-und-einkauf-nach-tandoor).

## PKS-001 bis TRN-001 — Kalkulation, Warenwirtschaft und Fachwissen

Auf Nutzerwunsch neu aufgenommen. [Optisoft Produkte](https://optisoft.ch/preise-und-produkte/) belegt Rezeptbestand, Produktdaten und Kalkulation; [Lightspeed](https://www.lightspeedhq.de/integrationen/paulis-kitchen-solution/) nennt zusätzlich den Gastroübersetzer und fünf Sprachen. Der [Pauli-Verlag](https://pauliph.com/) beschreibt seinen eigenen Rezeptkatalog; ihn nicht mit dem gesamten PKS-Bestand gleichsetzen.

[Exportbeschreibung, Juni 2021](https://optisoft.ch/wp-content/uploads/2021/06/Export-Fremdprogramme.pdf) und [Produktübersicht, Juni 2023](https://optisoft.ch/wp-content/uploads/2023/06/230616_Produktuebersicht-und-Preise.pdf) nennen Export-/Serverzugang, Warenkorb, Lager und Inventur. Historische Herstellerunterlagen sind kein Nachweis einer heute offen dokumentierten allgemeinen API. Konkreten Anschluss mit aktuellem Anbieterformat und berechtigten Daten prüfen. Weitere Ausarbeitung im [Entwurf, Abschnitt 11](design/2026-09-05-screens-vorlagen-verwaltung.md#11-kalkulation-warenwirtschaft-und-gastro-übersetzer).

## API-001 — REST-API v1, MCP, FHIR R5 und API-Schlüssel

**Status:** Auf Nutzerwunsch ins Backlog verschoben (2026-09-05). Der Produktionswechsel auf v16/Tabler ist erfolgt; API-001 bleibt zurückgestellt. Vorhandene API-Arbeiten erhalten, jetzt keine Lanes starten oder einsammeln.

**Umfang:** Dokumentierte REST-API v1 mit OpenAPI 3.1 und lokalem Swagger UI, FHIR-R5-Leseschnittstelle, MCP-Server sowie API-Schlüssel mit Admin-Verwaltung unter `/admin/api`.

**Quellen und vorhandene Planung:**

- Übergabe: `/nvmetank1/projects/menuplan/UEBERGABE-CODEX-API-2026-09-05.md` (insbesondere §4 und §6); dortige Lane-Stände bei Wiederaufnahme neu prüfen.
- Koordination: `/nvmetank1/projects/menuplan/KOORDINATION-API-CODEX-2026-09-05.md` für Dateigrenzen, Migration und Sidebar-Vertrag.
- Spec: `docs/superpowers/specs/2026-09-05-dishboard-api-mcp-fhir-design.md`, Branch `docs/api-mcp-fhir-spec-0905`, Commit `5e4750f`.
- Briefs und Logs: `.claude/state/api-mcp-fhir-0905/`.

**Reihenfolge bei Wiederaufnahme:**

1. Gemäß Übergabe §4 vorhandene Lanes sammeln: Abschlusslogs, Reports, Worktree-Status und Commits prüfen. Root wiederholt die jeweiligen Gates und Ruff selbst und committet erst danach. Fremde Änderungen und bestehende API-Worktrees erhalten; keine Quoten-Vorabprüfung oder Ausschlüsse anhand gespeicherter Quotenstände.
2. Welle 1 in `.claude/worktrees/api-integration-0905` auf Branch `integrate/api-mcp-fhir-0905` vervollständigen: Schema/Schlüssel-Store D, REST A1 und FHIR B integrieren; vorhandene Spec-, MCP-, Swagger- und Dokumentationsänderungen berücksichtigen.
3. Kombiniertes Gate aus §6 einschließlich Gesamtsuite, Ruff, Schema- und Swagger-Asset-Prüfung ausführen; anschließend Security-Review und unabhängiges Cross-Vendor-Review. **Der dort genannte alte `gate.sh`-Aufruf darf nicht blind ausgeführt werden:** Der bekannte alte Root-Wrapper verweist auf eine gelöschte Datenbank. Vorher gegen aktuell vorhandene Wrapper und eine tatsächlich verfügbare isolierte Testdatenbank prüfen. Fehlende DB-Umgebung beziehungsweise deswegen übersprungene DB-Tests sind kein grüner Nachweis.
4. Erst nach erfolgreicher Welle-1-Prüfung Welle 2 über `brief-e.md` und `brief-g.md` aufnehmen: Admin-Verwaltung und schlüsselgeschützte Endpunkte in eigenen Worktrees; Sidebar und Rendertests gemäß Spec ergänzen.
5. Rebase auf `main` erst nach dem v16/Tabler-Merge. Manifest aktualisieren, vollständige Offline-Paketprüfung ausführen und die Swagger-Verifikation aus Koordination §2.6 klären.
6. Deployment nach dem bestehenden Runbook vorbereiten: Backup, kontrollierte Migration **16→17**, danach Smokes für `/api/v1/status`, `/api/v1/docs`, `/fhir/metadata` und authentifiziert `/admin/api`. Schlüssel ausschließlich über die Admin-Verwaltung erzeugen; Klartext nicht in Chat oder Logs übernehmen.
