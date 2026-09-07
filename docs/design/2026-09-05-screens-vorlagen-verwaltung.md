# Dishboard: Screens, Vorlagen und Verwaltung

Status: **Entwurf und Backlog, keine Implementierungs- oder Geräteabnahme.** Stand: 5./6. September 2026. Repositorybasis der Bestandsaufnahme: `b97644ba5c86754051362c089d66109d66556279`, Schema 16. Der [Backlog](../BACKLOG.md) trennt laufende kleine Änderungen von geplanten Erweiterungen. Ergänzt um Tandoor als Rezept-/Planungsreferenz und Rezeptdruck.

**Verbindlicher Nutzerentscheid: Alles im Admin bleibt Tabler.** Formulare, Felder, Buttons, Dialoge, Navigation und Editor-Bedienelemente verwenden Tabler. Eine Tabler-Shell um eine fremde Oberfläche genügt nicht. Tandoor und Pauli dienen als Funktionsvorbilder; ihre Oberflächen und insbesondere Vue/Vuetify ersetzen den Dishboard-Admin nicht. Das gilt auch für alle nachfolgenden Prototypen und Erweiterungen.

## 1. Auftrag und Gestaltungsziel

Küchenadministration soll Wochenpläne, Inhalte und deren Darstellung an einem Ort pflegen. Bestehende Editoren, Flask/Jinja, PostgreSQL und Tabler weiterverwenden. Keine zweite Pflege derselben Menüs oder Zutaten. Gestaltung ruhig, kompakt und sachlich; vorhandenes Südhang-Theme und Tabler-Komponenten bestimmen das Erscheinungsbild. Eine unmittelbare Vorschau ist das zentrale Gestaltungselement.

Admin bleibt für kleine Samsung-Geräte bedienbar: 48-px-Aktionen, sichtbare Beschriftungen, 16-px-Eingabetext, keine horizontale Gesamtseitenbewegung. TV-Ausgabe erhält eigene Mindestschriftgrössen und feste getestete Raster. Kompakter Admin bedeutet keine kleinere Schrift auf öffentlichen Bildschirmen.

## 2. Navigation und Zuständigkeit

| Adminpunkt | Inhalt und Hauptaktion |
|---|---|
| Wochenpläne / Wochenverwaltung | Bestehende Tages-/Wochenzuordnungen, prüfen, veröffentlichen und drucken. |
| Menüs | Vorhandene Menüs suchen und bearbeiten; Karten und kompakte Liste. |
| Komponenten | Vorhandene Zutaten/Komponenten pflegen und Verwendung sehen. |
| **Grundlagen & Lager** | Zentraler Stammdaten-Einstieg nach Tandoors Datenbankbereich: Zutaten/Lebensmittel, Einheiten, Kategorien, Tags sowie Lagerorte/Bestände; bestehende Komponentenpflege einbinden. |
| Rezepte & Kochbücher | Geplante wiederverwendbare Rezepte, Sammlungen, Suche und Tags; von konkreten Wochenmenüs unterscheiden. |
| Einkauf | Geplante Einkaufslisten aus Rezepten und Wochenplänen; Mengen prüfen, abhaken und drucken. |
| **Screens** | Gemeinsamer Einstieg für Web- und Signage-Ausgaben beider Bereiche; Ziel öffnen, Vorlage zuordnen, Vorschau. |
| **Vorlagen** | Druck-, Screen- und Menüvorlagen verwalten; Zutaten/Komponenten und Menüs über ihre vorhandenen Editoren bearbeiten. |
| **Design & Marke** | Logo, Farben, Typografie; Unterbereich Darstellung mit globaler Admin-Dichte. |
| **Bereiche & Zeiten** | Anzeigenamen, Öffnungs-/Essenszeiten, Wochenregeln und Ausnahmen. |
| **Benutzer & Zugriff** | Benutzer, Rollen, Microsoft Entra ID und Zugriffsprotokoll. |
| CSV-Import / Abmelden | Bestehende Funktionen behalten. |

Die vier aktuellen Signage-Links werden durch einen Einstieg **Screens** ersetzt. Bestehende öffentliche URLs bleiben gültig. Unter Vorlagen öffnen Fachinhalte dieselben kanonischen Editoren wie unter Menüs/Komponenten; ein Menü ist kein dupliziertes Druckobjekt. Falls wiederverwendbare Menüvorlagen zusätzliche Speicherfunktionen benötigen, diese als eigenen Fachauftrag ausweisen. Keine verdeckte Umdeutung vorhandener Wochenmenüs.

## 3. Belegte vorhandene Bausteine

| Bereich | Vorhanden | Änderung / Grenze |
|---|---|---|
| Admin | `templates/admin/base_tabler.html`, `_workflow_sidebar.html`, Core 1.5.0, Icons 3.46.0 | Neue Seiten verwenden denselben Rahmen, dieselben Rollen und CSRF-Verträge. |
| Öffentliche Ansichten | `public/routes.py`, `signage/routes.py`, `templates/public/`, `templates/signage/`; gemeinsames `base.html`, `tokens.css`, `app.css` | Web- und TV-Seitenrahmen gezielt auf ausgewählte Bausteine migrieren; keine automatische Übernahme des Adminrasters. |
| Veröffentlichte Menüs | `db.py:active_snapshot`, aktive Publikationen, validierte Snapshots | Screen-/Vorlagenkonfiguration referenziert freigegebene Daten; kein Entwurf über öffentliche Parameter. |
| PDF | fpdf2 2.8.8; bestehende Admin-Druckrouten, je eine A4-Seite für Cafeteria/Patienten | Editor-Auswahl und Renderer-Vertrag noch offen; vorhandenen Renderer nicht stillschweigend ersetzen. |
| Einstellungen | Generische JSONB-Tabelle `settings` | Für validierte Darstellung prüfen; nicht als Secret- oder unkontrollierter Auth-Konfigurationsspeicher verwenden. |
| Anzeigenamen | `offer_profiles.display_name`, `meal_periods.display_name` | Harte Beschriftungen zuordnen; Seed darf gepflegte Namen nicht überschreiben. Technische Profile bleiben `patient`/`staff_guest`. |
| Service | `menu_services` mit Datum, Mahlzeit, offen/geschlossen/Feiertag/Betriebsferien und Hinweis | Uhrzeiten/Wochendefaults fehlen; neue datierte Werte durch bestehende Prüfung/Publikation führen. |
| Kompaktansicht | `static/admin.js` speichert `admin-dense` pro Browser | Globaler Serverwert ersetzt lokalen Schalter. `data-state` wird auch im CSV-Import verwendet und darf nicht für Dichte überschrieben werden. |
| Identität | Lokale Konto-/Passwortfunktionen, Rollen, MSAL mit einer statischen Entra-Konfiguration | Web-Verwaltung, letzte-Admin-Schutz und revisionierte Aktivierung fehlen. Bestehende Sicherheitsgrenzen erhalten. |

## 4. Bestehende Frameworks und Editoren

Recherche über Primärquellen am 5. September 2026; Sterne sind eine Momentaufnahme, keine Qualitätsabnahme.

**Gate für jeden Fremdeditor:** Vor Auswahl und Aktivierung müssen sämtliche Formulare, Buttons, Dialoge, Navigation, Werkzeugleisten und Eigenschaftsfelder als Tabler-Bedienelemente nachgewiesen sein. Nur Rahmen, Farben oder ein eingebettetes Fremd-UI erfüllen diesen Vertrag nicht. GrapesJS, Puck, Craft.js, Webstudio, pdfme und ReportBro sind daran gebunden; ohne diesen Nachweis keine Freigabe. Die Vorschaufläche ist vom Bedien-UI zu unterscheiden. Vorhandene Bibliotheken weiterverwenden, aber keinen fremden Admin als Ersatz einführen.

| Kandidat | Befund | Entscheidung |
|---|---|---|
| [Tabler](https://github.com/tabler/tabler) / [Bootstrap](https://github.com/twbs/bootstrap) | MIT; rund 41'629 / 174'724 Sterne, Tabler bereits vorhanden | Für öffentliche UI wiederverwenden. Separate Web-/TV-Layouts; kein zusätzliches Bootstrap-Kernbundle auf Tabler-Seiten. |
| [GrapesJS Core](https://github.com/GrapesJS/grapesjs) | BSD-3-Clause, 26'193 Sterne, 0.23.6; vorhandener visueller HTML/CSS-Editor, Blöcke, Assets, Undo und Geräteansichten | Bedingt bevorzugter Kandidat für Screen-Vorlagen mit Flask; vollständiges Tabler-Gate erforderlich. Nur Core; keine unbestellte kostenpflichtige Studio-SDK-Abhängigkeit. |
| [Puck](https://github.com/puckeditor/puck) | MIT, 13'265 Sterne, 0.23.0; kontrollierte React-Komponenten und fertiger Editor | Alternative bei bestandenem Tabler-Gate und besser belegter Samsung-Bedienung. Benötigt React-Build und Renderintegration; Jinja-Kompatibilität entsteht nicht automatisch. |
| [Craft.js](https://github.com/prevwong/craft.js) | MIT, 8'738 Sterne; Baukasten zum Bau eines Editors | Nicht bevorzugt: zu viel eigener Editoraufwand für diesen Auftrag. |
| [Webstudio](https://github.com/webstudio-is/webstudio) | AGPL-3.0-or-later, 8'906 Sterne; vollständiger Builder | Derzeit keine bevorzugte Einbettung; eigene Betriebs-/Exportanforderungen. |

[Tabler-Browseranforderungen](https://docs.tabler.io/ui/getting-started/browser-support) gegen tatsächliches Samsung und TV-WebView prüfen: Core 1.5.0 verlangt unter anderem moderne Chromium-Versionen. Ein Geräte-Vorschaurahmen im Editor belegt keine Touch-Bedienung. Vor endgültiger Editorbindung: Block hinzufügen/verschieben, Eigenschaften ändern, Logo hochladen, speichern, rotieren und Bildschirmtastatur auf Zielgerät prüfen. Kein Hardware-Nachweis liegt vor.

GrapesJS speichert [Projekt-JSON](https://grapesjs.com/docs/modules/Storage.html); HTML/CSS-Export allein ist kein vollständiger bearbeitbarer Projektstand. [Asset Manager](https://grapesjs.com/docs/modules/Assets.html) ersetzt keine serverseitige Uploadprüfung. Puck bietet einen [React-Renderer](https://puckeditor.com/docs/api-reference/components/render); dessen Einbindung wäre ein eigenes Paket.

Ein **PDF-Druckeditor** ist zusätzlich beauftragt. Cursor mit dem ausdrücklich gewünschten Modell Grok 4.6 wurde zweimal gestartet; beide Prozesse endeten mit Exit 0, lieferten wegen abgelehnter Werkzeugzugriffe aber keinen Vergleich. Kein positives Cursor-Rechercheergebnis behaupten. Separate Codex-Primärprüfung empfiehlt [pdfme](https://github.com/pdfme/pdfme) als Prototyp-Kandidaten: MIT, 4'804 Sterne, Version 6.0.0; visueller JSON-Designer mit eigenem Browser-/Node-Generator. Keine native fpdf2-Anbindung. [Tabellen](https://pdfme.com/docs/tables) unterstützen automatische Seitenumbrüche; Einseitigkeit bleibt Dishboard-Gate.

[ReportBro](https://github.com/jobsta/reportbro-designer) ist eine Python-nähere Alternative, aber mit AGPL-/kommerziellem Lizenzmodell und einer [Abhängigkeit auf `reportbro-fpdf2`](https://github.com/jobsta/reportbro-lib/blob/master/pyproject.toml). Kein direkter Zusatz zum vorhandenen `fpdf2==2.8.8`. Für pdfme den passenden Generator für Vorschau und Download gemeinsam erproben; keinen universellen eigenen JSON-zu-fpdf2-Konverter erfinden. Bestehende fpdf2-Ausgabe während der Erprobung erhalten. Auswahl muss echte Seitengrössen, dynamische Menüblöcke, Tabellen, Symbole und lesbare Einseitigkeit prüfen; eine HTML-Screen-Vorschau genügt nicht. Kein Kandidat ist installiert oder auf Samsung abgenommen.

## 5. Vorlagen und visuelle Druckbearbeitung

Vorlagenübersicht mit Kategorien **Druck**, **Screens**, **Menüvorlagen**, **Zutaten & Komponenten**. Druck umfasst Wochenpläne, Rezepte und Einkaufslisten. Zuletzt genannte Kategorie verweist auf vorhandene Stammdatenpflege; Menülinks führen zum vorhandenen Editor mit erhaltenem Wochen-/Tageskontext. Rezeptvorlagen verknüpfen später den kanonischen Rezepteditor.

Vorlagenaktionen: neu aus bestehender Vorlage, bearbeiten, duplizieren, Vorschau mit gewählter Woche, speichern, aktivieren, vorherige Version wiederherstellen, archivieren. Archivierbarkeit und aktive Verwendung werden angezeigt. Eine aktive Vorlage kann nicht ersatzlos verschwinden.

Editierbare Gestaltung:

- Logo, Farben und erlaubte Schriften aus Design & Marke, mit optionalem Vorlagen-Override.
- Kopf-/Fussbereich, Titel, Datum/Kalenderwoche, Hinweise, Abstände, Spalten und Zeilenaufteilung.
- Menüblöcke, Komponenten, Menübilder, Herkunftsflaggen, Allergene/Labels und automatische Legende.
- Bereichsbezogene Preisfelder nur dort, wo der vorhandene Fachvertrag Preise erlaubt.

Die Datenfelder binden an Menüs und Zeiten; das Design dupliziert keine Menüinhalte. Menütexte und Zutaten sind über verknüpfte Fachformulare editierbar. Pflichtangaben und Patiententrennung werden serverseitig validiert, auch bei manipuliertem Vorlagen-JSON.

Startvorlagen: **Cafeteria Woche – A4 hoch**, fünf Tage und zehn Menüs; **Patienten Woche – A4 quer**, sieben Tage und Mittag/Abend mit 28 Menüslots, ohne Preise. Südhang-Referenz bleibt visueller Ausgangspunkt; neue Symbole/Labels ersetzen die vereinbarten Textmarkierungen. Bearbeitung darf Raster verändern, die freigegebene Wochenvorlage muss weiterhin vollständig auf eine Seite passen. Andere Formate wären gesonderte Vorlagentypen.

Vor Aktivierung und Download erfolgt die Prüfung am tatsächlichen PDF: Seitenzahl, Vollständigkeit, Mindestschrift, Text-/Icongrenzen, Legenden, Glyphen und Patientenpreisfreiheit. Überlauf liefert einen verständlichen Hinweis mit betroffenen Blöcken; kein Abschneiden, keine automatische unlesbare Verkleinerung. Vorschau und endgültiger Download verwenden denselben Renderingvertrag.

Vorlagen besitzen Entwurf, validierte Revision und aktive Revision. Datenpublikation und Designaktivierung sind getrennte Transaktionen. Bereits erzeugte Drucke bleiben nachvollziehbar über Datenrevision plus Vorlagen-/Brandingrevision; technische Referenzen gehören in Metadaten/Audit, nicht sichtbar auf die Ausgabe. Alte Datenpublikationen werden durch Vorlagen- oder Zutatenänderungen nicht umgeschrieben.

## 6. Symbole, Flaggen und automatische Legenden

Recherchierte Auswahl: [Erudus/erudus-icons](https://github.com/Erudus/erudus-icons) (MIT, 24 Sterne, vollständiges Fachset) und [lipis/flag-icons](https://github.com/lipis/flag-icons) (MIT, 12'367 Sterne, Version 7.5.0). Erudus-Commit `7e25e14a09b1aa0af4f85dc69ebfb03ff99480b7` enthält die 14 neutralen Dateien für Gluten, Krebstiere, Eier, Fisch, Erdnüsse, Soja, Milch, Schalenfrüchte, Sellerie, Senf, Sesam, Sulfite, Lupinen und Weichtiere. Keine automatische Verwendung von `free-from-*`-Grafiken.

Tabler bleibt für Bedienelemente; es ist kein vollständiges Allergenset. Insbesondere ist Tablers `nut` eine Schraubenmutter und kein Schalenfruchtensymbol.

Gemeinsames Manifest: bestehender fachlicher Code → deutscher Name, lokales SVG, Textfallback, Quelle, Version, Lizenz und SHA-256. Vorhandene Codes nicht umbenennen. Länderflagge stets mit zuordenbarem Ländernamen/Kürzel; `CH` ist portabler Fallback. Keine Schrift-/Emoji-Abhängigkeit.

Legende aus tatsächlich dargestellten Codes und Ländern ableiten, dedupliziert und stabil sortiert. Beim paginierten Screen je sichtbarer Seite, beim Wochen-PDF aus dessen gesamtem Druckinhalt. Allergenstatus sprachlich unterscheiden: enthält, kann enthalten, nicht erfasst. Farbe dient als Ergänzung. Leere Daten erzeugen keine Frei-von-Aussage und keine erfundene Herkunft.

[fpdf2 2.8.8 unterstützt SVG](https://github.com/py-pdf/fpdf2/blob/2.8.8/docs/SVG.md) mit dokumentierten Grenzen. Ausgewählte Dateien tatsächlich rendern; falls erforderlich beim Build deterministisch in PNG umwandeln, keine zusätzliche Laufzeitkonvertierung. Visuelle Prüfung kleiner Symbole in Farbe, Schwarzweiss, PDF und auf Samsung bleibt offen.

## 7. Design, Darstellung und Betriebsangaben

Design & Marke validiert zentrale Logo-/Farb-/Schriftwerte; Vorschau vor Aktivierung, Wiederherstellung vorheriger Revision. Kein beliebiges CSS/JavaScript im Einstellungsformular. Uploads begrenzen, Inhalt prüfen, externe Referenzen entfernen/ablehnen und über kontrollierte Assets ausliefern. Bestehende CSP `script-src 'self'; style-src 'self'` nicht global aufweichen; Editor/Canvas isoliert integrieren.

Globale Admin-Dichte serverseitig aus `admin_density = compact|comfortable`, Standard `compact`. In `base_tabler.html` als eigenes `data-density` ausgeben; ohne JavaScript korrekt, kein Layoutflackern. Alte `admin-dense`-LocalStorage-Werte und Seitenschalter entfallen. Fachzustände wie CSV `data-state` unverändert lassen. Kompakte Kartenabstände sind erlaubt, versteckte Pflicht-Hinweise oder verkleinerte Touch-Ziele nicht.

Bereiche & Zeiten unterscheidet bearbeitbare Anzeigenamen von technischen Profilen. Umbenennen zu «Schüler» ist keine neue Berechtigung und kein dritter unabhängiger Datenbereich. Wiederkehrende Wochenzeiten dienen als Vorgabe für neue datierte Services; bestehende Wochen ändern sich erst über bewusste Bearbeitung und erneute Prüfung/Publikation. Zeitzone Europe/Zurich, Ausnahmen und Schliessungen explizit anzeigen. Harte aktuelle Essenszeiten in `patient_today.html`/`patient_day.html` gezielt ersetzen.

## 8. Benutzer und Microsoft Entra ID

Vorhandene Rollen `Cafeteria.Editor`, `Cafeteria.Publisher`, `Cafeteria.Admin` erhalten. Kontoaktionen nutzen die vorhandene getrennte Auth-Issuer-Berechtigung; das normale App-DB-Konto erhält keine pauschalen Identitäts-Schreibrechte. Benutzer-/Rollenänderung invalidiert Berechtigungen über den vorhandenen Mechanismus. Akteur stammt aus aktueller Sitzung, nie aus frei übermitteltem Formularfeld.

Vor Web-Freigabe: Schutz des letzten aktiven lokalen Admins und des letzten funktionsfähigen Anmeldewegs, auch bei parallelen Anfragen; eindeutige Bestätigung, CSRF und Audit. Bestehende Passwörter nicht verändern. Konto-Wiederaktivierung, Rollenwechsel und Entra-Sperren benötigen gezielte Backendverträge; vorhandene CLI-Funktionen decken nicht automatisch jede Aktion ab.

Entra: zunächst eine aktive Verbindung, mehrere Entwürfe. Tenant/Client/Callback validieren; vollständiger Anmeldetest bindet an exakte Entwurfsrevision. Aktivierung atomar, Fehler lässt alte Verbindung aktiv. Bereits gestartete Login-Flows behalten ihre ursprüngliche Konfigurationsrevision. Tenant/Object-ID bleibt Identitätsschlüssel; keine automatische Kontenzusammenführung per E-Mail.

Secrets nur maskiert beziehungsweise schreibend handhaben; zunächst genehmigte serverseitige Secret-Referenzen. Echte Web-Secret-Eingabe benötigt geschützten Store/Broker, keine allgemeinen Settings, beliebigen Dateipfade oder Host-Env-Schreibzugriffe. Keine Tokens, Passwörter oder ungefilterten Providerfehler in Audit/UI/Reports.

## 9. Kleine Arbeitspakete und Gates

| Paket | Dateiverantwortung / Ergebnis | Gate / Abhängigkeit |
|---|---|---|
| N01 | Gemeinsame Sidebar plus neue Screens-/Vorlagen-Hubs und deren Routen; vorhandene Editoren verlinken | Auth, alle Ziele beider Bereiche, mobile Navigation, keine neuen öffentlichen Entwurfswege. |
| D01 | Validierte globale Dichte, `base_tabler.html`, `admin.js`, zugehörige CSS und Tests | Zwei Browser gleicher Serverwert, JS aus, alte lokale Werte ignoriert, CSV-Zustände und 48-px-Ziele erhalten. Schemaweg vorher klären. |
| I01 | Lokale Symbolassets, Manifest, Lizenz-/Buildnachweis | Alle 14 Gruppen, gültige ISO-Zuordnung, Hash-/Fallbackprüfung; kein neuer Allergenstandard. |
| I02 | Gemeinsame Legendenableitung und Verbraucher in Admin/Public/Signage/PDF | Nur sichtbare Codes, unbekannt bleibt unbekannt, gleiche Zuordnung, Wochen-PDF jeweils genau eine Seite; Rezept-/Einkaufsdruck darf lesbar mehrseitig sein. Patienten ohne Preise; nach I01. |
| E01 | Screen- und Druckeditor mit Beispieldaten separat erproben | Bestehende Bibliothek, vollständige Tabler-Bedienelemente jedes Fremdeditors statt blosser Shell, reproduzierbarer Build, Touch-/Keyboard-Probe, CSP, echte PDF-Seitenprüfung. Keine Produktivaktivierung durch Prototyp. |
| E02 | Revisionierter Vorlagenstore, validierte Blöcke und aktive Zuordnung | Konflikterkennung, Rollen/CSRF, Rückweg, keine frei ausführbaren Vorlagen; nach E01 und abgestimmtem Schema. |
| E03 | Editor in Vorlagen einbinden; Vorschau/Validierung/Aktivierung | Vollständiges Tabler-Gate für Editor-Formulare, Buttons, Dialoge und Navigation; tatsächliche Woche, alle Pflichtinfos, identischer Vorschau-/Downloadrenderer; nach E02/I02. |
| B01 | Brandingstore, Upload und Design-&-Marke-Formulare samt Verbraucher | Assetprüfung, Kontrast, Rückweg, gemeinsame Tokens, unveränderte Datenpublikation. |
| O01 | Anzeigenamen/Zeiten, Seedvertrag, datierte Services und Ausgabe | Keine Seed-Überschreibung, Feiertage/Zeiten, Snapshotbestand erhalten, erneute Prüfung bei Änderungen. |
| A01 | Benutzer-/Rollenliste und Kontoaktionen mit SQL-Schutz | Auth-/DB-Tests, letzte-Admin-Rennen, keine Secrets/Hashes, bestehende Rollengrenzen. |
| A02 | Entra-Entwurf, Secret-Referenz, Test und Aktivierung | Callback bei Konfigurationswechsel, falscher Tenant, Redaktion sensibler Fehler, misslungene Aktivierung, lokaler Rückweg. |
| Q01 | Unabhängige Funktions-, Tablet-, TV- und Druckabnahme | Alle Admin-Bedienelemente Tabler; Web 360/768/820/1024/1280; TV 1920×1080 und Patientenwoche 3840×2160; tatsächliches Samsung. Wochen-PDF jeweils genau eine Seite; Rezept-/Einkaufsdruck mit lesbaren Seitenumbrüchen. |

Parallel möglich: I01, E01 und vorbereitender A01-Audit. Gemeinsame Sidebar, Settings-Verträge, Publikationsverträge und Testdatenbanken jeweils genau einer Lane zuordnen. Kleine fertige UI-Pakete nach unabhängigen Gates regulär deployen, nicht auf Abschluss aller Erweiterungen warten.

**Migrationskoordination:** API-001 reserviert `0014_v16_to_v17.sql`. Keine konkurrierende 0014 anlegen und keine neue Migration mit unerfüllter v17-Voraussetzung ausliefern. Vor erster neuen Schemaänderung Reihenfolge/Reservierung mit API-Koordination ausdrücklich festlegen. API bleibt Backlog; dieser Entwurf startet keine API-Lanes.

**Offene Nachweise:** exaktes Samsung-/TV-Browsermodell, endgültige Druckeditor-/Renderer-Auswahl, Touch-Eignung, kleine Drucksymbole, neue Speicher-/Aktivierungsverträge. Recherche und bestehende CLI-Funktionen sind kein Nachweis bereits implementierter Adminseiten.

## 10. Rezepte, Kochbücher und Einkauf nach Tandoor

Nutzerauftrag: von [Tandoor Recipes](https://github.com/TandoorRecipes/recipes) Funktionsabläufe und geeignete vorhandene Bausteine übernehmen. Rezeptverwaltung, Kochbücher, Planung, Einkaufslisten, KI-Hilfen, Importe, Volltext/Trigram und Tags sind als Referenzfunktionen im Projekt beschrieben. Dies ist ein Folgeauftrag im Backlog, keine Migration Dishboards auf Tandoor.

Tandoor ist eine eigene Anwendung mit Django und Vue; kein direkt einsetzbares Flask-/Tabler-Plugin. Vor Codeübernahme konkrete Module, Verträge und Abhängigkeiten zuordnen. Der [Lizenztext](https://github.com/TandoorRecipes/recipes/blob/develop/LICENSE.md) nennt AGPL v3 mit Commons Clause. Bei Wiederverwendung Herkunft/Version/Lizenz und erforderliche Hinweise erhalten; der Nutzerwunsch nach einem Lernprojekt ändert diesen Nachweis nicht. Es wurde kein Tandoor-Code übernommen.

Die angegebene [Demo](https://app.tandoor.dev/) zeigt bei unangemeldetem Zugriff die Loginseite; interaktive Rezept-/Planungsfunktionen sind noch nicht abgenommen. Keine Registrierung oder fremde Zugangsdaten verwenden, um einen Demo-Nachweis zu behaupten. Dokumentation und öffentlich zugängliche Beispiele als solche kennzeichnen.

### Fachliche Zuordnung

| Nutzerwunsch | Dishboard-Ziel und Abnahme |
|---|---|
| Rezepte und Kochbücher | Rezept mit Portionen, Zutaten/Mengen/Einheiten, Bildern, geordneten Schritten, Quelle und Revision; Kochbücher referenzieren dieselben Rezepte. Wochenmenüs binden eine definierte Rezeptrevision, ohne publizierte Pläne nachträglich zu ändern. |
| KI-Bilderkennung und Strukturierung | Fotos, Dokumente und Text in bearbeitbaren Entwurf überführen; Schritte ordnen, Zutaten zuordnen, Metadaten vorschlagen. Nutzer sieht Quelle, erkannte Werte und Unsicherheit vor Übernahme. Vorhandene Menübilderzeugung ist eine eigene Funktion. |
| Nährwerte | Werte mit Quelle, Bezugsmenge und Berechnungs-/Schätzstatus speichern. KI-Ausgabe ist kein bestätigter Nährwert und keine automatische Allergen- oder Kostformfreigabe. Nicht vorhandene Daten bleiben unbekannt. |
| Planen | Rezepte und Portionszahlen in vorhandene Tages-/Wochenplanung aufnehmen, keine konkurrierende zweite Wochenplan-Datenquelle. Unveröffentlichte Einkaufsvorbereitung bleibt im Admin. |
| Einkaufslisten | Aus Plan oder gewählten Rezepten ableiten, kompatible Einheiten umrechnen und gleiche Zutaten zusammenfassen; unvereinbare Einheiten getrennt zeigen. Manuelle Positionen und Abhakstatus, skalierte Portionen, nachvollziehbare Herkunft der Menge. |
| Sammlungsimport | Andere Rezeptmanager, Excel/XLSX, CSV, JSON und Pauli Kitchen Solution über konkrete Exportadapter; Vorschau, Mapping, Mengen-/Einheitenprüfung, Dublettenentscheidung, zeilenbezogene Fehler und transaktionale Übernahme. |
| Webseitenimport | Schema.org Recipe in JSON-LD/Microdata über bestehende Parser übernehmen; Quelle und Importzeit erhalten, vor Speicherung korrigierbar. Dokument-/Antwortgrössen, Dateitypen und ausgehende Ziele begrenzen. Kein Ausführen von Makros oder importierten Skripten. |
| Suche | Vorhandenes PostgreSQL nutzen: gewichtete Volltextsuche plus Trigram-Ähnlichkeit und fachliche Filter. Relevanz, Tippfehler, Umlaute, grössere Sammlungen und Profilberechtigungen prüfen; keine pauschale neue Suchmaschine. |
| Tags in Serie | Tags anlegen, suchen, filtern und gesammelt zuweisen. Vor Anwendung konkrete Trefferzahl/Objekte bestätigen, Berechtigung serverseitig erneut prüfen, keine unsichtbar veränderte Treffermenge. |
| Grundlagen und Lager | [Tandoors Datenbankbereich](https://app.tandoor.dev/database) als UX-Referenz prüfen. Ein gemeinsamer Einstieg für Zutaten/Lebensmittel, Komponenten, Einheiten, Kategorien und Tags; Lagerorte und Bestände als Dishboard-Ziel. Vorhandene Stammdaten erhalten, kompatible Mengen/Einheiten und bewusste Bestandskorrekturen prüfen. Rezeptplanung verändert nicht ungefragt den tatsächlichen Bestand; Einkaufslisten zeigen nachvollziehbar Bedarf und vorhandene Mengen. |
| Rezept-/Einkaufsdruck | Aus kanonischen Daten erzeugen; Layout unter Vorlagen mit Logo, Zutaten, Portionen, Schritten, Bildern und automatischen Legenden bearbeitbar. Lange Rezepte dürfen lesbar mehrseitig sein; Wochenpläne bleiben je eine Seite. |

Tandoors [Importdokumentation](https://docs.tandoor.dev/features/import_export/) und [KI-Dokumentation](https://docs.tandoor.dev/features/ai/) dienen als Ausgangspunkt für Adapter-/Workflowauswahl. Excel und Pauli sind explizite Dishboard-Ziele; ein vollständiger passender Tandoor-Adapter ist noch nicht nachgewiesen. «JSON» allein beschreibt kein Importschema. Für Pauli vor Implementierung Exportversion und repräsentative berechtigte Beispieldatei klären. Beliebige proprietäre Formate nicht als bereits kompatibel ausgeben.

Quellprüfung von Tandoor `develop` auf `e160ceecaee0b269924be600a6d01ecb0bd55e30`: Die [Import-Registry](https://github.com/TandoorRecipes/recipes/blob/e160ceecaee0b269924be600a6d01ecb0bd55e30/vue3/src/utils/integration_utils.ts) enthält formatspezifische Adapter, keinen nachgewiesenen generischen Excel-/CSV-/Pauli-Rezeptimport. Der [URL-Importer](https://github.com/TandoorRecipes/recipes/blob/e160ceecaee0b269924be600a6d01ecb0bd55e30/cookbook/helper/recipe_url_import.py) verwendet die separat MIT-lizenzierte Bibliothek [recipe-scrapers](https://github.com/hhursev/recipe-scrapers), einen geeigneten unabhängigen Prüfungskandidaten. Keine Installation erfolgt.

Die [Modelle](https://github.com/TandoorRecipes/recipes/blob/e160ceecaee0b269924be600a6d01ecb0bd55e30/cookbook/models.py) belegen `InventoryLocation`, `InventoryEntry` und `InventoryLog` mit Mengen, Einheiten, Ablaufdatum und Zu-/Ab-/Umbuchungen. Das ist ein Quellbefund, keine getestete Demo. `/database` wurde im Browser geöffnet und landete auf `/accounts/login/?next=/database`. Tandoors [PDF-Dokumentation](https://docs.tandoor.dev/features/import_export/#pdf) verweist auf Browserdruck; [Templating](https://docs.tandoor.dev/features/templating/) meint Zutatenreferenzen in Schritten, keinen visuellen Druckeditor.

### Folgepakete

R01 ordnet Rezept-/Zutaten-/Menümodelle und Revisionen zu. R02 ergänzt Rezepteditor, Kochbücher und Tags. R03 implementiert zunächst CSV/JSON mit Vorschau; XLSX, Quellmanager und Pauli folgen als getrennte Adapter mit realen Beispielen. R04 integriert einen geprüften Schema.org-Importer. R05 liefert Volltext/Trigram und Batch-Tags. R06 verbindet Portionen, Wochenplanung und Einkauf. R07 ergänzt KI-Vorschläge mit Übernahmeprüfung. R08 bindet Rezept-/Einkaufsdruck an den gemeinsamen Vorlageneditor. R09 ergänzt Grundlagen & Lager mit kontrollierten Bestandsänderungen und Verbindung zum Einkauf; tatsächliche Tandoor-Funktionen zuvor separat zuordnen.

Alle Pakete benötigen abgegrenzte Dateiverantwortung und bestehende Rollen-/Publikationsregression. Schemafolge mit API-Reservierung koordinieren. Kein Rezeptimport publiziert automatisch ein Menü; keine KI-Aktion bestätigt Allergene automatisch. Pro Paket unabhängige Gates und regulärer kleiner Deploy.

## 11. Kalkulation, Warenwirtschaft und Gastro-Übersetzer

Ergänzender Nutzerauftrag nach Pauli's Kitchen Solution/Optisoft. Alle folgenden Funktionen sind Backlog, kein aktueller Dishboard-Bestand.

| Bereich | Ziel / überprüfbare Abnahme |
|---|---|
| Rezeptdatenbank | Eigene und berechtigt importierte Sammlungen mit Quellen, Versionen und Dublettenprüfung. Die Herstellerangabe von über 4'400 PKS-Rezepten, davon laut Optisoft 1'655 Pauli-Rezepte, ist keine zugesagte Dishboard-Liefermenge. |
| Warenaufwand | Mengen, Preise mit Gültigkeitsdatum, Einheitenumrechnung, Ausbeute/Verlust und Portionszahl nachvollziehbar berechnen; fehlender Preis bleibt fehlend, nicht null. Referenzrechnungen und Rundung als Fachtests. |
| Menüpreise | Konfigurierbare Kalkulationsvorgaben und Preisvorschläge mit sichtbaren Annahmen. Vorhandene Preisfelder bewusst übernehmen; keine automatische Preisänderung veröffentlichter Pläne und keine Preise in Patientenausgaben. |
| Allergene/Nährwerte | Strukturierte Produkt-/Lieferantendaten mit Quelle, Aktualität, Bezugsmenge und Prüfstatus. Berechnung aus Rezepten nur bei belastbaren Mengen/Einheiten/Daten; KI-Schätzungen bleiben gekennzeichnet. |
| Inventur | Zählen, Korrekturen, Zu-/Abgänge und Umbuchungen mit Akteur/Zeit/Einheit; zeitgleiche Buchungen korrekt behandeln. Lager mit Einkaufsbedarf verbinden, Planänderung nicht automatisch als Verbrauch buchen. |
| Bestellung | Bedarf und Lieferantenzuordnung in Warenkorb/Bestellvorschlag überführen, Mengen und Preise vor Absenden prüfen. Übertragung nur über eingerichtete Schnittstelle/Export; Doppelversand verhindern, Ergebnis nachvollziehbar. Verbindliches Absenden braucht ausdrückliche Bestätigung. |
| Gastro-Übersetzer | Deutsch, Französisch, Englisch, Italienisch, Spanisch; Begriffe, Synonyme und Kontext. Berechtigte Glossare/geeignete Quellen verwenden, Fachübersetzung überprüfbar. Herstellerumfang von rund 50'000 Begriffen ist eine Referenz, kein automatisch übernommener Wörterbuchbestand. |

Primärquellen, geprüft am 5. September 2026: [Optisoft Produkte](https://optisoft.ch/preise-und-produkte/), [Optisoft](https://optisoft.ch/), [Lightspeed-Integration](https://www.lightspeedhq.de/integrationen/paulis-kitchen-solution/), [Pauli-Verlag](https://pauliph.com/). Pauli-Verlagskatalog und gesamter PKS-Bestand sind getrennte Angebote. Die aktuelle Produktseite nennt Lieferantenimport, Excel-Vorlage für Lieferantendaten, PKS-Serverzugang und Fremdprogrammexport; das belegt keinen generischen Excel-Rezeptimport.

[Fremdprogrammexport, Juni 2021](https://optisoft.ch/wp-content/uploads/2021/06/Export-Fremdprogramme.pdf) beschreibt Rezepte/Gerichte/Menüs samt Zutaten, Nährwerten und Allergenen. [Produktübersicht, Juni 2023](https://optisoft.ch/wp-content/uploads/2023/06/230616_Produktuebersicht-und-Preise.pdf) beschreibt Warenkorbbefüllung, Mengenübernahme, Lager und Inventur. Eine automatische Warenkorbbefüllung ist kein Nachweis unbeaufsichtigt ausgelöster verbindlicher Bestellungen. Öffentliche aktuelle API-Endpunkt-/Auth-/Formatdokumentation für Dishboard ist noch nicht belegt; Anbieteranschluss vor Umsetzung konkretisieren.

Arbeitspakete: K01 Preis-/Einheiten-/Kalkulationsvertrag, K02 Produktdatenadapter und Rezeptberechnung, K03 Inventur/Bestandsbuchungen, K04 Warenkorb/Bestelladapter, K05 Fachglossar und Übersetzungseditor. K01/K02 hängen an R01 und berechtigten Produktdaten; K03/K04 an Grundlagen & Lager und Lieferantenverträgen. Kein externer Bestellversand im Recherche-/Backlogauftrag.

## 12. Open Food Facts — OFF-001

Nutzerauftrag: [Open Food Facts](https://world.openfoodfacts.org/) durch den tatsächlichen AGY-Agenten evaluieren. **Status: tatsächliche AGY-Bewertung (ein Aufruf, Exit 0) und unabhängige Quellenkorrektur abgeschlossen; positiv für Barcode-Importvorschläge. Integration und Schweizer Abdeckungsmessung bleiben offen.** Die korrigierte Bewertung ist kein bereits implementierter Anschluss; keine ungeprüften API-Limits übernehmen.

Prüfumfang: Barcode/EAN und eindeutige Produktzuordnung; Produkte und Zutaten; Allergene getrennt von Spuren; Nährwerte mit Bezugsmenge; Herkunft und Bilder. API und bestehende SDKs anhand offizieller Quellen beurteilen, Schweizer Produktabdeckung und Datenqualität mit einer dokumentierten Stichprobe prüfen. Daten- und Bildlizenzen sowie Quellen-/Versionsnachweise getrennt klären. Kein vollständiger oder kostenlos übernehmbarer Datenbestand wird zugesagt.

Unabhängig korrigierte Lizenzzuordnung: Daten ODbL, Inhalte DbCL, Bilder CC BY-SA 3.0; [offizielle Lizenzangaben](https://openfoodfacts.github.io/openfoodfacts-server/api/tutorials/license-be-on-the-legal-side/). Frühere abweichende Feld-/Lizenzangaben aus der AGY-Erstantwort nicht als Implementierungsvertrag verwenden.

Ein möglicher Anschluss erzeugt ausschließlich prüfbare Importvorschläge mit Quelle und Abrufzeit. Fehlende Angaben bleiben unbekannt; weder Barcode noch Bild beweisen Herkunft oder Allergenfreiheit. Abweichungen zu bestehenden Zutaten-/Produktdaten anzeigen. Bestätigte Daten niemals automatisch überschreiben; Übernahme einzelner Felder braucht eine bewusste manuelle Freigabe. Formulare, Vergleichsansicht und Dialoge unterliegen dem vollständigen Tabler-Gate.

Vor Adapterfreigabe noch erforderlich: dokumentierte Schweizer Beispieldaten, endgültige Feldzuordnung, bekannte Lücken und ein konkreter Anschlussvertrag auf Basis der geprüften Quellen. Danach ein getrenntes Adapterpaket vergeben. Diese externe Datenquellenprüfung nimmt die zurückgestellte Dishboard-API-001 nicht wieder auf; Schemaänderungen weiterhin mit der reservierten Migration abstimmen.

## 13. Erster Screen-Katalog-/Zuordnungsslice — Plan vom 7. September 2026

**Planbasis `783fab33520e15c956df431f62ad75c9940e2285`, Schema 21; keine Implementierungsabnahme.** Dieser Nachtrag konkretisiert SCR-001/TPL-001, ersetzt keine Restanforderung der Abschnitte 5/9. Die Bestandsaufnahme oben ist historisch. Aktuell gelten generische responsive Breiten und das [Tabler-/Symbolmanifest](2026-09-07-admin-tabler-icon-manifest.md), keine Tablet-first-Priorität. Laufzeitkorrektur auf akzeptierter Basis `55709d9`/Schema 22: S1 benötigt den separat reservierten Writer `0020_v22_to_v23.sql`/Schema 23; R1s Migration `0019` und der Rezepteditor bleiben getrennte Aufträge.

### 13.1 Bestand und kleinster sichtbarer Nutzen

Ziel: Unter **Screens** die Darstellung eines Web-Wochenplans bewusst wählen und die aktive Auswahl sofort erkennen. Ruhige, kompakte Tabler-Karten, volle Beschriftungen und eine echte veröffentlichte Vorschau sind die Gestaltung. Alle Karten bleiben gleich gross; 48-px-Aktionen und vollständige Inhalte bestimmen die responsive Aufteilung.

Quellwurzel der folgenden Produktpfade ist `reference_scaffold/cafeteria/`:

| Tatsächliche Quelle an der Planbasis | Befund / Folge |
|---|---|
| `admin/output_routes.py:13–47`, `templates/admin/screens.html` | `admin.screens` ist lesend; vier Bereich/Kanal-Karten enthalten zehn Vorschauziele: acht kanonische Tag/Woche-Ziele und zwei feste bildlose Web-Wochenvarianten. |
| `public/routes.py:95–120`, `templates/public/cafeteria_week.html`, `templates/public/patient_week.html` | Zwei echte kompatible Wochenvarianten existieren bereits über `show_menu_images`. Keine Übertragung eines Webrasters in einen TV-Rahmen nötig. |
| `signage/routes.py:55–82`, `static/signage.js` | TV hat je Profil/Zeitraum nur ein Layout; Polling vergleicht Menürevision, Datum und Brandingrevision. Ein einzelner Auswahlwert wäre kein Zuordnungseditor. |
| `admin/output_routes.py:26–47`, `templates/admin/vorlagen.html` | Bestehender revisionierter PDF-Katalog mit V2-Archivstatus muss vollständig erhalten bleiben. Sein Wochenfilter gilt für PDF/Fachpflege, nicht für öffentliche Screen-Daten. |
| `print_templates.py:118–164`, `database/schema.sql:354–376` relativ zur Repositorywurzel | Settings erlaubt bounded JSONB, eindeutige Schlüssel auch bei NULL-Scope und Akteur/Zeit; `audit_events` erlaubt eine separate atomare Änderungsspur. Bestehender IAM-Sperrhelper ist verfügbar. |

**Lieferumfang S1:** Zwei zuweisbare Ziele: `public.cafeteria_week` und `public.patient_week`. Je Ziel genau zwei unveränderliche Katalogeinträge, „Wochenplan mit Bildern“ und „Wochenplan ohne Bilder“, beide Rendererrevision 1. Technische IDs sind feste Allowlistwerte, keine Templatepfade aus Eingaben. Ein Katalogeintrag enthält Profil, Kanal `web`, Zeitraum `week`, ID, Rendererrevision und `show_menu_images`; Kompatibilität ist Gleichheit aller drei Zielmerkmale. Keine fachlichen Daten kopieren.

Die beiden bestehenden `*_week_without_images`-URLs bleiben ausdrücklich bildlos und unverändert erreichbar, unabhängig von der aktiven Auswahl. Die kanonischen Wochen-URLs liefern bei fehlender Konfiguration weiterhin Bilder. Tages-/TV-Ziele bleiben im Katalog als bestehende feste Ausgaben sichtbar, ohne nutzlosen Ein-Option-Speicherknopf. Es entstehen keine neuen TV-Layouts, PDF-Vorlagen oder freien Editoren.

### 13.2 Vollständiger Speicher-/Schreibvertrag mit begrenztem Schema-23-Writer

Neue eigene Schlüssel `screen_assignment.v1.staff_guest.web.week` und `screen_assignment.v1.patient.web.week` in `cafeteria.settings`, jeweils `location_id=NULL, profile_id=NULL`, analog zum globalen PDF-Vorlagenstore. Dies ist ausdrücklich eine globale Darstellung je bestehendem Bereich; keine Standortauswahl und keine Gerätezuweisung. Der technische Profilanteil wird nur aus der erlaubten Route aufgelöst.

Dokument mit exakt `schema_version=1, version, template_id, renderer_revision=1`. Strikte Typen: bool ist keine Integer-Version; `version` 0 bis `2**63-2`; bekannte, zielkompatible IDs und Revisionen; unbekannte Schlüssel/Versionen oder beschädigte Daten führen kontrolliert zu 503. Maximal zwei neue Settingszeilen, keine benutzererzeugten Vorlagen, keine unbeschränkte Revisionsliste. Fehlende Zeile ist ein virtueller Bilderstandard mit Version 0; **kein GET initialisiert oder repariert Settings**.

Ein Writer führt nach Formprüfung genau eine Transaktion aus: `lock_operations_actor(original_actor, original_authz_version)` (bestehende Rollen-vor-Actor-Sperre und 5-s-Timeout erhalten), fehlende Standardzeile per konfliktfestem Insert, Settingszeile `FOR UPDATE`, strikte Validierung und Vergleich der originalen Dokumentversion. Danach genau ein UPDATE und ein INSERT in `audit_events` mit Akteur, Profil, Ziel, alter/neuer ID und Revision, alter/neuer Dokumentversion; kein Token/HTML/Secret im Audit. Fehler rollen auch den ersten Insert zurück. Gleiches aktives Ziel ist als Zustandsaktion 409, ohne Version/Audit; Versionsgrenze ebenfalls 409. Zwei konkurrierende Erstschreiber oder veraltete Formulare dürfen nicht beide gewinnen.

Die ursprüngliche Annahme eines App-INSERT-Rechts auf Audit ist durch zwei reale Runtime-Läufe widerlegt: Audit ist für die App nur lesbar, auch Sequenzrechte fehlen. **Kein breiter Auditgrant.** Migration `0020_v22_to_v23.sql` liefert ausschließlich `activate_screen_assignment_v23(p_actor bigint,p_authz bigint,p_profile text,p_expected_version bigint,p_template_id text,p_renderer_revision integer) RETURNS jsonb` als festen SECURITY-DEFINER-Writer mit sicherem search_path; App erhält nur EXECUTE auf diese neue Funktion. Er validiert sämtliche Parameter und gespeicherten Dokumente selbst, nutzt den unveränderten IAM-Sperrhelper und schreibt genau ein Audit `screen_assignment.activate` mit `actor_authz_version, profile, target, before, after`. Rückgabe ist das exakte neue Dokument. SQLSTATE `P2001` → 400, `P2004` → 503, `55000` → 409; kanonische Auth-/Isolations-/Timeoutfehler bleiben unverändert. `display_settings.py` ist kein CAS-/Audit-Muster und wird nicht erweitert.

### 13.3 Routen, Formkontext und Fehler

Lesen bleibt `draft.read`; Schreiben ist `settings.write` mit aktueller, in der Transaktion erneut geprüfter Adminrolle. Keine zusätzliche Rolle. Neuer GET/POST `/admin/screens/<any(cafeteria,patienten):family>/wochenvorlage`: GET zeigt die zwei Varianten und die aktive Auswahl, POST akzeptiert exakt `_csrf, _form_context, version, template_id, renderer_revision, action=activate`, jeweils einmal. Keine Queryparameter, keine frei eingegebenen Rücksprung- oder Renderpfade.

Signierter Formkontext nach vorhandenem Muster `admin/master_data_forms.py:44–94`, mit eigenem Salt: ursprünglicher Actor/Authz-Version, globaler Scope, Ziel, Dokumentversion, CSRF. Kontext und ursprüngliche CAS bleiben auf 400/409 erhalten; Nutzerwahl wird escaped wieder angezeigt, niemals still neu signiert oder auf eine frische Version gehoben. Actorwechsel/erneuerte Identität nach Formularöffnung ist 401, aktueller fehlender Zugriff 403, ungültige Felder/Signatur 400, unbekannte Route/Vorlage 404, inkompatible bekannte Variante 400, CAS-/Same-state-Konflikt 409. Erfolg genau ein POST → 303 auf dieselbe kanonische Adminroute, `no-store`.

CSRF wird an der Basis `783fab3` routenlokal geprüft; es gibt keinen globalen CSRF-Before-Request-Hook. Vorhandene CSRF-Utilities im neuen POST-Pfad und Originalkontext gemeinsam testen. Fehlerfokus und klare „Neu laden“-Verknüpfung ohne fremde URL; Wechsel zur aktuellen Fassung nur per bewusstem GET. Äusserer SQLAlchemy-/Settingsfehler inklusive IAM-Sperrtimeout wird 503 mit fester verständlicher Meldung, ohne erneuten DB-Zugriff oder DB-abhängigen Kontextprozessor. Dafür kleine eigene Fehleransicht; keine rohen Exceptions, keine Rekursion und kein automatischer Schreibretry.

### 13.4 Vorschau und öffentliche Übernahme

Unter `/admin/vorlagen` ergänzt ein eigener Abschnitt „Screen-Vorlagen“ die vier echten Web-Wochenvarianten mit kompatiblem Ziel, Aktivstatus, Vorschau und Link zur Zuordnung. Bestehende PDF-Karten, Revisionen, Archive, Wochenfilter und Fachlinks unverändert. Unter `/admin/screens` bleiben alle zehn bisherigen Vorschauen/Öffnen-Links erhalten; die kanonischen Web-Wochentabs benennen jetzt die aktive Variante korrekt statt Bilder still vorauszusetzen.

Explizite Vorschau per neuem GET `/admin/vorlagen/screens/<any(cafeteria,patienten):family>/<template_id>`, `draft.read`, keine Queryparameter, nur Registryauflösung und derselbe veröffentlichte Kontext/Renderer. Keine Wochenentwürfe, Fixtures oder historischen Adminmenüs in öffentliche Frames. Fehlende aktuelle Publikation bleibt HTML-404/`no-store`, kein leeres Erfolgsbild und kein heimliches Publizieren. Unverändert gelten Europe/Zurich, OPS-Ausnahmen/Wochenenden, Snapshot-`area_name`, patientenpreisfreie Texte und vollständige Metadaten/Legenden.

Nur die beiden kanonischen Web-Wochenfunktionen lesen ihre aktive Zuordnung und setzen den vorhandenen `show_menu_images`-Wert. Nicht die gemeinsame `published_response`-Funktion mit globaler Settingsabhängigkeit belasten: GitNexus meldet dort **CRITICAL, sechs direkte Verbraucher/sechs Flows**, einschliesslich Tages- und Druckausgaben. Vor Produktedits Impact neu prüfen. Eigene `X-Screen-Template-Revision` auf betroffenen Antworten bezeichnet Renderer-ID/Revision plus Zuordnungsversion; Menürevision bleibt unverändert.

S1 übernimmt Änderungen beim nächsten GET bzw. bewussten Neuladen; der vorhandene Webrahmen `templates/public/base_public.html` besitzt keinen Poller. Keine neue Reloadschleife und keine behauptete Live-Aktualisierung offener Browser. Bei Settingsausfall/beschädigtem Dokument 503/`no-store`, nicht still Bilderstandard oder anders zugeordneten Inhalt ausliefern. Vorhandener Snapshot-Ausfallvertrag bleibt separat, kein neuer unbegrenzter Konfigurationscache.

**Späterer TV-Slice hat ein hartes Zusatzgate:** mindestens zwei vollständig gemessene kompatible TV-Layouts, eigenes Zuordnungsrevisionssignal im DOM und Pollvergleich auch bei gleicher Menü-/Brandingrevision und gleichem Datum. Bestehende 60-s-Polls, 15-s-Requesttimeout, keine Überlappung, 30-s-Seitenrotation, 5-min-/Mitternachtsablauf, 404/410-Rücknahme und maximal ein bestehender Darstellungswechselpfad erhalten. Kein URL-/Redirect-/Vorlagen-Fallbackring. S1 ändert `static/signage.js` nicht.

### 13.5 Startfähige Ownership und Abnahme

**Die S1-Python-/UI-Lane besitzt Store + sämtliche Verbraucher zusammen**, neue Pythonmodule jeweils unter 400 LOC; keine zusätzliche Framework-/Repository-Schicht. Die getrennte SQL-Lane besitzt exklusiv Migration `0020`, identischen Fresh-Schema-Writer, Funktionsrechte, Schema-23-Versionspins und echte Writer-/Upgrade-/Grant-Regressionen. Beide Lanes verwenden die feste API aus §13.2; keine direkten App-Auditwrites:

| Eigentum relativ zur Quellwurzel | Aufgabe |
|---|---|
| Neu `screen_templates.py` | Feste Registry, Kompatibilität, strikter Dokumentparser, virtueller Default und Aufruf des festen SQL-CAS-/Audit-Writers. Bei tatsächlicher Grössenüberschreitung Registry/Validierung in `screen_template_config.py` trennen, nicht vorsorglich. |
| Neu `admin/screen_template_routes.py`, optional `admin/screen_template_forms.py` nur bei >400 LOC | GET/POST, ursprünglicher Formkontext, Vorschau, DB-freie Fehlerhülle. |
| `admin/output_routes.py`, `admin/__init__.py`, `templates/admin/screens.html`, `templates/admin/vorlagen.html`; neu `templates/admin/screen_template_assignment.html`, `templates/admin/screen_template_unavailable.html` | Beide Hubs, Registrierung und vollständige Bedienung. Bestehende Hubregistrierung in `admin/workflow_routes.py:860` erhalten; keine Doppelregistrierung. |
| `public/routes.py` nur Wochenfunktionen; `static/admin-screens.css` nur bei notwendiger vorhandener Rasteranpassung | Kanonische Rendereranbindung und gleiche Kartengrössen. Kein globales CSS/JS, keine Inlinewerte, kein Vendor-/Symbolasset-Umbau. |
| `templates/admin/_workflow_sidebar.html` nur falls für aktive Unterseiten nötig | Beide bestehenden Sidebarzweige behalten Screens/Vorlagen; keine neuen Hauptpunkte und keine verlorene Registrierung. |

Reale PG-Tests neu `reference_scaffold/tests/test_screen_template_store.py`, `test_screen_template_routes.py`; Browser neu `test_screen_template_browser.py`. Eigentum umfasst notwendige Ergänzungen in bestehenden `test_admin_output_hubs.py`, `test_admin_screens_preview_browser.py`, `test_admin_template_catalog_browser.py`, `test_public_week_no_images.py`, `test_public_contracts.py`. Keine Assertion für alte Links/Varianten entfernen.

- PG: fehlende Zeilen/GET ohne Mutation; zwei Erstschreiber und stale CAS; ein Audit mit tatsächlichem Vorher/Nachher; Same-state ohne Mutation; Profile/Kompatibilität strikt; Originalactor, Rollenwiderruf und 5-s-Sperrtimeout; unbekannte JSON-Version/ID und DB-Ausfall ohne Defaults/ReRead; Runtime-Apprechte, keine Schemareset-Abkürzung.
- Browser bei 390/820/1440 px, JS an/aus: alle zehn alten Ziele erreichbar; beide Profile und beide Wahlen; beschriftete Tabler-Auswahl, 48-px-Ziele, Tastatur/Fokus, keine horizontale Seite, gleiche Karten. Auswahl/Vorschau-GET speichert nichts; Aktivierung genau einmal/303; 400/409 behalten Auswahl/Token/CAS. Bildlose explizite URL bleibt bildlos, kanonischer GET wechselt tatsächlich, alle Menüs/Metadaten erhalten. Echte veröffentlichte und unveröffentlichte Wochen; fehlende Livedaten separat als nicht verfügbar ausweisen.
- Breite Regression: Public Tages-/Wochen-/Druck-, OPS-, Branding-/Food-Legenden- und sämtliche Signage-Engine/Expiry-Geometriefälle unverändert, insbesondere Legacy-Patientenrotation versus OPS-Layout. Erst Testpool exklusiv von Root zuweisen lassen; echte PG-/Browserwrapper, `PYTHONDONTWRITEBYTECODE=1`, keine SQLite-Ersatzabnahme.
- Root wiederholt fokussierte Tests und vollständiges Paket; Ruff, normaler Mypy mit Baselinevergleich, Node nur bei tatsächlich geändertem JS. Private Screenshots, erlaubte lokale Assets, keine CSP-Aufweichung. OCR ist in dieser Sitzung nach zweimal 429 nicht verfügbar, kein weiterer unveränderter Aufruf und kein CLEAN.

**Releasegrenze:** S1 ist nur nutzbarer Web-Wochenkatalog plus zwei globale aktive Zuordnungen. Frei gestaltbare/revisionierte Screenvorlagen, TV-Auswahl, Geräte-/Standortgruppen, Zeitpläne/Playlists, Uploads, Menüvorlagen und kompletter SCR/TPL-Auftrag bleiben offen. Ein altes App-Image ignoriert neue Zuordnungskeys: keine semantische Rückfallfreigabe daraus ableiten; kompatibler Reader/Renderer oder Forward-Fix muss geprüft sein. Kein JSON-Downgrade/Restore zur Umgehung. Bestehende V2-PDF-Fallbackgrenze bleibt unverändert.
