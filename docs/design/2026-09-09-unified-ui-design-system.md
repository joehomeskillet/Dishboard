<!-- Verbindlicher Nutzerauftrag vom 9. September 2026, konsolidiert mit dem Dichteauftrag vom 13. September 2026. Fachliche, Sicherheits- und Architekturverträge bleiben erhalten. -->

# Verbindliches UI-Manifest: gemeinsame Flask-/Tabler-Gestaltung und kompakte Arbeitsflächen

**Einsatz:** Gemeinsamer Arbeitsvertrag für alle beauftragten Coding-Tools im bestehenden Repository.

**Geltungsbereich:** Die gesamte Anwendung, alle vorhandenen Tools, Module, Verwaltungsseiten und gemeinsam verwendeten UI-Komponenten. Keine Bindung an eine bestimmte Fachdomäne, Beispielseite oder Route.

**Technische Basis:** Flask, Jinja2, Tabler, das zur installierten Tabler-Version gehörende Bootstrap und Tabler Icons.

**Ziel:** Gemeinsame, überprüfbare Gestaltung aller bestehenden und künftigen Oberflächen: volle interne Arbeitsbreite, kompakte Inhalte und sichere unmittelbare Bedienung. Der Rezepteditor ist die erste Referenz, keine Begrenzung der Migration.

Dieses Dokument ist eigenständig verwendbar. Die beiden älteren Entwürfe zum UI-Design und zur seitenbezogenen Migration werden für diese UI-Aufgabe durch diesen konsolidierten Standard ersetzt. Bestehende Sicherheits-, Architektur- und Repository-Vorgaben bleiben gültig. Bei einem Konflikt mit einem freigegebenen Corporate Design oder Projektvertrag: Konflikt benennen, nicht stillschweigend überschreiben.

---

## Auftraggeber-Entscheid 2026-09-20

Gemäss Auftraggeber-Entscheid im Handoff (`docs/design/uiux-handoff-2026-09-20/`) werden folgende Regeln und Strukturen ersetzt bzw. präzisiert:
* **M01 Seitenrahmen/Tabs/Statuslage:** Horizontale Haupt-Untermenüs entfallen; stattdessen eingerückte Kontextnavigation in der Sidebar (nur bei aktivem Oberpunkt). Neue Seitenstruktur: Titel + ein Satz Kontext → rechts höchstens EINE primäre globale Aktion → Statusbar über volle Inhaltsbreite → Filter/Suche nur wenn nötig → Hauptinhalt → Sekundäres/Technisches.
* **R07:** Das Statusbar-Designsystem rückt als globale Komponente zentral unter den Titel. Die frühere Angabe «3–5 Slots» ist am 2026-09-20 durch **1–5 echte Slots** ersetzt.
* **R08:** Hauptaktion standardmässig oben rechts im Seitenkopf. Bei langen Editoren ist eine kompakte sticky Aktionsleiste zulässig.
* **A17 (Testmatrix) & Mobile:** Pflichtbreiten 360, 768, 1024, 1440 px. Sidebar darf mobil zu Drawer werden.
* **Begrifflichkeiten:** Der Navigationspunkt «Grundlagen» heisst neu «Zutaten». Der Seitentitel entspricht stets dem Navigationspunkt. Bestehende URLs und Endpoints bleiben unverändert.

**Ausdrücklich unverändert bleiben:**
* 200-%-Browserzoom-Test und sichtbarer Fokus (2px Outline mit Abstand).
* Mindesthöhen der Bedienelemente (hier gilt der strengere Wert von **48px** basierend auf Test `test_rendered_ui.py` gegenüber den Token-Variablen).
* Fehlende Angaben dürfen niemals als «allergenfrei» dargestellt werden.
* Ohne-JS-Bedienbarkeit und Erhalt der `<noscript>`-Redundanz.
* Erhalt bestehender CSRF- und Backend-Sicherheitsgrenzen.
* Verbindliche Token-Pflicht für alle Styles.
* Signage und öffentliche Seiten sind nicht Teil dieser Umsetzungs-Welle.

## Auftraggeber-Ergänzung 2026-09-20: Vereinfachung und kompakte Formulare

Ergänzung zu den Auftraggeber-Prompts «Kompakte Formulare» und «Globale UI-Vereinfachung» (`docs/design/uiux-handoff-2026-09-20/07_ERGAENZUNGEN/`). Beispielbilder sind Denkweise und Komposition, keine Datenquelle und kein Funktionsumfang.

### Grundprinzip

> «Zeige nur, was im aktuellen Kontext gebraucht wird.»

Komplexität darf im Datenmodell und Backend existieren; sie darf nicht ungefiltert und dauerhaft im UI landen. Funktionalität, Validierung und Speichersemantik bleiben unverändert.

### Entscheidungsregel

Wenn zwei Varianten fachlich gleichwertig sind, verwende diejenige, die:

1. weniger Erklärung benötigt,
2. weniger permanente UI-Elemente zeigt,
3. weniger Klicks im häufigsten Workflow benötigt,
4. weniger Platz verbraucht,
5. bereits an anderer Stelle als gemeinsames Pattern eingesetzt werden kann.

### Informationshierarchie

Priorität absteigend:

1. aktuelle Aufgabe,
2. für die Entscheidung notwendige Informationen,
3. Status und Warnungen,
4. Primäraktion,
5. optionale Details,
6. technische und administrative Informationen.

Stufen 5 und 6 standardmässig einklappen oder zurückhaltend darstellen, sofern sie nicht unmittelbar benötigt werden.

### Platzverbrauch

Vertikalen Platz als knappe Ressource behandeln. «Kompakt ist nicht gequetscht»: Mindesthöhen der Bedienelemente (**48 px**), sichtbarer Fokus, Lesbarkeit und 200-%-Zoom bleiben verbindlich. Keine riesigen Karten für wenige Informationen, keine dauerhaft sichtbaren Detailfelder für nicht ausgewählte Optionen, keine künstlich gestreckten Einzelfelder über die volle Breite ohne Grund.

### Prüffragen je Seite

Vor jeder Vereinfachung kurz prüfen:

- Kann Feld, Text, Button, Status oder Abschnitt entfallen?
- Kann etwas erst bei Bedarf eingeblendet werden?
- Werden dieselben Informationen mehrfach gezeigt?
- Sind Formulare unnötig lang oder breit?
- Gibt es dauerhaft sichtbare Detailfelder für nicht ausgewählte Optionen?
- Sind Aktionen über mehrere Stellen verteilt?
- Gibt es zu viele gleichwertig wirkende Buttons?
- Kann ein sinnvoller Standard einen Arbeitsschritt einsparen?
- Lassen sich Listen, Filter und Aktionen kompakter darstellen?
- Ist Tabelle statt vieler grosser Karten sinnvoller – oder umgekehrt?
- Sind Überschriften, Hilfetexte oder technische Angaben für den Normalfall nötig?
- Werden interne IDs, Revisionen oder technische Zustände unnötig prominent gezeigt?
- Gibt es grosse Leerflächen oder gestreckte Eingabefelder?
- Ist sofort erkennbar: Wo bin ich? Was ist der Zustand? Was ist die nächste Handlung?
- Ist die gleiche Funktion in anderen Modulen anders aufgebaut?

### Vorgehen

Phase 1 — UI-Audit → Phase 2 — gemeinsame Komponenten → Phase 3 — Module → Phase 4 — Detailseiten und Sonderzustände → Phase 5 — Regression. Keine vorhandene Fachfunktion entfernen; Backend-Verträge, Datenmodell, Validierung und Berechtigungen erhalten.

### Beispielbilder: übernommen / nicht übernommen

| Im Beispielbild | Entscheidung | Grund |
|---|---|---|
| Horizontale Modul-Tabs über der Liste und alle Module flach in der Sidebar | nicht übernehmen | SDD «nicht verhandelbar»: keine horizontale Modul-Untermenüleiste; Unterpunkte nur eingerückt in der Sidebar bei aktivem Oberpunkt |
| Globale Suche mit Tastenkürzel, Benachrichtigungsglocke, Hilfe, Datumsnavigation in einer Kopfleiste | nicht Teil der Welle | neue Fachfunktionen; Handoff verlangt «keine neue Businesslogik» |
| «Löschen» im Formularfuss | nur wo die Funktion heute existiert (sonst Archivieren/Reaktivieren) | keine neue Fachfunktion |
| Schritt-Assistent, Timer/Bild je Zubereitungsschritt, Raster-Ansicht, Duplizieren | nur wo heute vorhanden | keine neue Fachfunktion |
| «Alle als ‹nicht enthalten› setzen» und stiller Standardwert | nur mit unveränderter Speichersemantik | «Nicht ausgewählt» oder «ungeprüft» darf nie als «allergenfrei» gespeichert oder angezeigt werden; Prüfstatus wird durch die Oberfläche nicht verändert |
| Beispielwerte (Gerichte, Daten, Lieferanten, Bestände) | keine Datenquelle | Mockup-Inhalte |
| Eine Filterzeile, eine Zeile pro Datensatz, Status-Badges, Zeilenaktionen, Auswahl-Chips mit Detail nach Auswahl, «Weitere Optionen» eingeklappt, einheitlicher Formularfuss, 2–3 Spalten gross / 1 Spalte mobil | übernehmen | verbindliche Muster M21–M25 |

## Auftraggeber-Design-System v2 (2026-09-20)

Verbindliche Ergänzung aus `docs/design/design-system-v2-2026-09-20/` (SDD v2, Manifest v2, Update-Prompt, Review-Checkliste). **Vorrangregel:** Dieses Paket geht dem ersten Handoff (`docs/design/uiux-handoff-2026-09-20/`) vor. Referenzpriorität gemäss SDD v2 §19: akzeptierte Einstellungs-Screens definieren die Designsprache; generierte Mockups liefern Interaktionsprinzipien, keine pixelgenaue Vorlage; Ist-Screens belegen Fachlichkeit und Anti-Patterns. Bei Konflikt: Fachfunktion des Ist-Systems erhalten.

**Leitsatz (Manifest v2):** «So wenig UI wie möglich, so viel Information wie nötig.» Jede Ansicht folgt der Seitenhierarchie **Kontext → Status → Aufgabe → Primäraktion → Details**.

### Navigation

Drei Hauptpunkte mit Kontext-Unterpunkten in der linken Sidebar (nur sichtbar beim aktiven Hauptpunkt; keine horizontale Doppel-Navigation):

| Hauptpunkt | Unterpunkte |
|---|---|
| **Wochenplan** | Cafeteria · Patienten · Wochenübersicht · Küchenkalender |
| **Menüs & Bausteine** | Menüs · Bausteine · Zutaten · Rezepte · Kochbücher · Gerichtvorlagen · Einkaufslisten · Bestellung · Lager · Kalkulation |
| **Einstellungen** | Bereiche & Öffnungszeiten · Erscheinungsbild · Darstellung · Daten importieren · Schnittstellen · Benutzer & Zugriff |

Editor-interne Tabs oder Stepper sind zulässig, wenn sie echte Bearbeitungsschritte darstellen und keine globale Navigation duplizieren. Der bisherige Unterpunkt «Wochenverwaltung» heisst neu **«Wochenübersicht»**; URL und Endpoint bleiben unverändert.

### Statusleiste

Eigene wiederverwendbare Komponente unter dem Seitenkopf. Nur entscheidungsrelevante Angaben (z. B. Prüfstand, offene Kartenprüfungen, fehlende Allergenangaben, Veröffentlichungsstatus, Zeitraum/KW). **Statuschips dürfen direkt filtern oder navigieren** — als Link mit sichtbarem Text, nicht nur als Farbindikator. Keine Dekoration ohne Informations- oder Aktionswert.

### Bilder

In operativen Planungs- und Listenansichten nur **kleine Thumbnails** mit festem Seitenverhältnis und Lazy Loading. Grosse Bilder nur in Vorschau oder Detail, wenn visuell relevant. Keine bildschirmfüllenden Food-Fotos in der Arbeitsplanung.

### Verbotene Anti-Patterns (Manifest v2 §14)

1. horizontale Subnavigation zusätzlich zur Sidebar;
2. mehrere gleich starke Primärbuttons;
3. permanent sichtbare Sonderoptionen;
4. Status nur durch Farbe;
5. technische IDs als Hauptinformation;
6. grosse leere Karten;
7. Fullscreen-Food-Fotos in operativen Planungslisten;
8. unterschiedliche Filter-/Speicherlogik pro Modul;
9. Icons ohne Text, wenn Bedeutung nicht offensichtlich;
10. Hilfetexte, die dieselbe Information ständig wiederholen.

### Definition of Done (Manifest v2 §15)

Jede UI-Änderung ist konsistent mit bestehenden Komponenten, platzsparender als vorher, Keyboard- und Responsive-tauglich, Status und Aktionen eindeutig. Der **häufigste Workflow darf nicht länger** werden. Es existiert ein **Vorher/Nachher-Screenshot** für Review.

### Reihenfolge der Umsetzung (Update-Prompt)

1. Shell und kontextuelle Navigation
2. Statusbar, Toolbar, Filter und Actions
3. Wochenplan vollständig (Cafeteria, Patienten, Wochenübersicht, Küchenkalender, Tagesansicht)
4. Menüeditor inkl. Allergene
5. Menüs & Bausteine vollständig
6. Einstellungen ohne Verschlechterung
7. Responsive, A11y und Regression

### Abweichungen und Präzisierungen gegenüber v2

| Thema | Entscheidung |
|---|---|
| Touch-Ziele | **48 px** für zentrale Bedienelemente bleiben verbindlich (strenger als «ca. 44 px» in SDD v2 §13; erfüllt die v2-Vorgabe). |
| Allergen-Detail | Inline-Detail direkt an der gewählten Option (M21): Formulare senden Allergen und Präsenz als indexgepaarte Wiederholfelder; das Detailfeld wird deaktiviert statt versteckt und bleibt im selben Container. |
| Referenzbilder v2 | Die Ordner `accepted-settings/`, `current-modules/`, `current-weekplan/` und `generated-mockups/` fehlten in der Lieferung; bis zur Nachlieferung gilt für den Wochenplan der Text des SDD v2 §5–§6 als Zielmodell (M26–M30). |

## 1. Dein Auftrag

Migriere das bestehende Frontend auf das hier festgelegte Designsystem. Setze die Änderungen im Repository um; liefere nicht lediglich Vorschläge oder ein weiteres Konzept.

Arbeite von gemeinsamen Grundlagen zu den einzelnen Seitentypen: Design-Tokens, Tabler-Anbindung, Layout, Navigation, Komponenten und danach sämtliche betroffenen Tools und Routen. Eine Referenzseite dient der Entwicklung und Prüfung des Standards, nicht als Begrenzung des Auftrags.

**Gleiche Gestaltung bedeutet gemeinsame Komponenten und Regeln. Es bedeutet nicht, jede Seite in dasselbe Formular-plus-Tabelle-Layout zu zwingen.**

Erhalte Geschäftslogik, Daten, Berechtigungen und bestehende Bedienabläufe. Erfinde keine Funktionen, Datenspalten, Pflichtfelder, Zeichenlimits, Menüpunkte oder Statuswerte. Verändere keine API-Verträge und führe keine Datenbankmigration als Nebenprodukt der Gestaltung durch.

Die Farben in diesem Dokument sind die vorgeschlagene gemeinsame Anwendungspalette. Sie sind kein Nachweis einer offiziell freigegebenen Corporate-Design-Farbdefinition.

Die Nutzerentscheidung vom 13. September ersetzt frühere Breiten-, Dichte- und Navigationsvorgaben an ihrer jeweiligen Stelle in diesem Manifest. Alle internen Arbeitsseiten nutzen die volle verfügbare Breite. Nur kurze einzelne Felder oder sinnvoll begrenzte Lesetexte dürfen lokal schmal bleiben, niemals der gesamte Seiten- oder Formulararbeitsbereich. Das Manifest ist die einzige zentrale Quelle; kein paralleles Designsystem und keine separate Stilwelt pro Seite.

**Entscheidungsreihenfolge:** Korrekte Daten und sichere Bedienung → unveränderter Unterbau → verständliche Aufgabenführung → volle Arbeitsbreite und kompakte Inhalte → konsistente Gestaltung.

Versteckte Warnungen, verlorene Werte und eine breite Hülle mit weiterhin riesigen Zutatenblöcken erfüllen den Auftrag nicht. Bestehende Freigaben und Dateiverantwortlichkeiten erhalten; ein konkreter Werkzeug- oder Fachblocker stoppt nur den betroffenen Teil. Unabhängige zulässige Arbeit weiterführen.

### 1.1 Verbindliche Regeln R01–R10

| ID | Regel | Konkrete Umsetzung |
|---|---|---|
| R01 | Volle Arbeitsbreite | Hauptbereich rechts der Navigation vollständig nutzen; keine schmalen inneren Gesamtwrapper und kein `100vw` über die Sidebar hinweg. |
| R02 | Inhalt statt Verwaltungswand | Nach kompaktem Kopf und notwendiger Orientierung kommt die eigentliche Arbeit. Keine lange Strecke aus Hinweisen, Einrichtung und doppelten Aktionen davor. |
| R03 | Kompakte wiederholte Objekte | Eine Arbeitszeile pro Zutat, Schritt, Baustein oder Zuordnung. Zusatzfelder nur bei Bedarf; nicht eine hohe offene Card je Objekt. *(präzisiert am 2026-09-20: siehe Auftraggeber-Ergänzung / Muster M21, M23)* |
| R04 | Häufige Änderungen unmittelbar | Menge und Einheit direkt in der Zutatenübersicht ändern. Eine einfache Änderung darf keine zusätzliche Klickstrecke benötigen. |
| R05 | Verständliche Symbole | Tabler-Icon plus kurzer sichtbarer Text für Navigation und Hauptaktionen. Gleiche Bedeutung überall gleich darstellen. |
| R06 | Sichere Detailbereiche | Auf-/Zuklappen speichert und verwirft nichts. Neue oder fehlerhafte Einträge passend öffnen. Gefüllte Zusatzangaben im Kurztext erkennbar lassen. *(präzisiert am 2026-09-20: siehe Auftraggeber-Ergänzung / Muster M21, M25)* |
| R07 | Wahrheitsgetreue Zustände | Gespeichert, geprüft und veröffentlicht unterscheiden. Fehlende Angaben nicht durch einen allgemeinen grünen Haken verdecken. *(Ersetzt am 2026-09-20 durch: Statusbar als globales Designsystem mit 1–5 echten Slots zentral unter dem Titel; die frühere Angabe 3–5 ist damit abgelöst. Warnungen immer mit Text, Farbe nie alleiniger Träger. Keine erfundenen Daten.)* |
| R08 | Erreichbare Aktionen | Eine hervorgehobene Speicherhandlung je Formular, erreichbar ohne Scrollreise. Seltene Aktionen in einem beschrifteten Menü. *(Ersetzt am 2026-09-20 durch: Primäraktion standardmässig oben rechts im Seitenkopf. Bei langen Editoren ist eine kompakte sticky Aktionsleiste das zulässige Mittel.)* *(präzisiert am 2026-09-20: siehe Auftraggeber-Ergänzung / Muster M24)* |
| R09 | Ruhige Gestaltung | Bestehende Farben, Schriften und Tokens behalten. Weniger verschachtelte Rahmen, klare Kanten, keine Schmuckkarten oder dekorativen Kennzahlen. |
| R10 | Vollständiger Nachweis | Jede Seite prüfen. Ein Screenshot, HTTP 200, erfolgreicher Build oder Breitenwert ersetzt weder Interaktion noch Gesamtaudit. |

## 2. Konkrete Stellungnahme zum bisherigen Stand

### 2.1 Am gezeigten Ist-Interface erkennbar

Diese Befunde stammen aus der gezeigten Oberfläche. Ob dieselben Probleme auf weiteren Seiten bestehen, musst du im Repository und Browser prüfen.

| Befund | Was daran nicht stimmt | Verbindliche Korrektur |
|---|---|---|
| Grosse freie Randflächen bei gleichzeitig kleinen Texten und Bedienelementen | Der verfügbare Platz hilft der Lesbarkeit nicht. Innen ist die Oberfläche dicht, aussen bleibt viel Fläche leer. | Gesamten Hauptbereich und seine inneren Arbeitscontainer nutzen; kompakte Zeilen statt hoher Wiederholungs-Cards. Lesbare Schrift und mindestens 44px Bedienhöhe erhalten. |
| Seitenüberschrift kaum dominanter als ein Card-Titel | Seite, Bereich und einzelne Aufgabe haben zu wenig unterschiedliche Gewichtung. | Eindeutige H1, kurze hilfreiche Beschreibung und einheitlicher Seitenkopf. |
| Lange, praktisch ungegliederte Sidebar | Alltagsaufgaben, Stammdaten und Systemeinstellungen erscheinen nahezu gleichrangig. | Vorhandene Einträge nach tatsächlichen Aufgaben gruppieren, aktive Position eindeutig zeigen und Berechtigungen erhalten. |
| Ähnlich klingende Navigationsbegriffe ohne Erklärung | Der Unterschied zwischen benachbarten Funktionen ist für neue Benutzer nicht sofort klar. | Aufgaben und Zielseiten prüfen; verständliche Benennung oder kurze Erklärung verwenden. Nicht blind Funktionen zusammenlegen. |
| Formularfelder nutzen nur einen Teil der grossen Card | Kartenbreite und innere Feldaufteilung wirken nicht aufeinander abgestimmt. | Inhalt sinnvoll an ein gemeinsames Grid binden. Kurze Felder nicht endlos dehnen, längere Felder erhalten den nötigen Raum. |
| Feldhinweis „optional“ weit entfernt vom Label | Information und zugehöriges Feld sind visuell voneinander getrennt. | „Optional“ beim Label oder im direkt zugeordneten Hilfetext anzeigen. |
| Kleine Tabellenüberschriften und unauffällige Statusanzeigen | Die Lesbarkeit der eigentlichen Daten erhält zu wenig Gewicht. | Gut lesbare Tabellenbeschriftungen, klarer Abstand und ausreichend kontrastierende Status-Badges. |
| Mehrere ähnlich gewichtete Zeilenaktionen | Wichtigkeit und Nutzungshäufigkeit werden nicht unterschieden. | Häufige Aktionen beschriftet sichtbar lassen; seltene Aktionen nur bei Bedarf in ein funktionierendes Menü verschieben. |
| Pagination mit Vor-/Zurück-Steuerung bei nur einer Seite | Sichtbare Bedienung erzeugt keine zusätzliche Funktion. | Bei einer Seite nur die Anzahl anzeigen; Seitensteuerung erst bei mehreren Seiten. |

**Nicht als Fehler behaupten:** Eine fehlende Suche bei zwei Datensätzen ist kein grundsätzliches UX-Problem. Ein Screenshot belegt weder defekte Funktionen noch fehlende Barrierefreiheitstests oder eine bestimmte CSS-Ursache. Behaupte solche Dinge erst nach Prüfung.

### 2.2 Fehler und Lücken in den bisherigen Prompt-Entwürfen

| Bisherige Vorgabe | Warum sie nicht genügt | Neue Entscheidung |
|---|---|---|
| Eine konkrete Fachseite bestimmt die gesamte Migration. | Andere Tools und Seitentypen können unbearbeitet bleiben. | Vollständiges UI-Inventar und Nachweis pro vorhandener Route. |
| „Modern“, „ruhig“, „hochwertig“ ohne prüfbare Umsetzung. | Der Agent muss wichtige Entscheidungen jedes Mal neu interpretieren. | Feste Tokens, Komponentenverträge, Layoutvarianten und visuelle Referenzen. |
| Wertebereiche wie 240–260 px oder 32–36 px. | Mehrere unterschiedliche Ergebnisse erfüllen denselben Prompt. | Zentrale Standardwerte und responsive Zuordnung; Arbeitszeilen typischerweise 56–72px, bei Inhalt, Fehlern oder Zoom wachsend. |
| „Tabler-Standardschrift“, obwohl das Mockup Serifentitel zeigt. | Textvorgabe und visuelles Ziel widersprechen sich. | Feste Schriftfamilien für Bedientext und Überschriften; siehe Typografie. |
| Nur eigene CSS-Variablen definieren. | Das beweist nicht, dass Tabler-Komponenten diese tatsächlich verwenden. | Tokens an die installierte Tabler-Version anbinden und berechnete Browser-Styles prüfen. [S1, S2] |
| Helle Status- und Hilfstextfarben. | Einige konkret vorgeschlagene Kombinationen sind für kleine Schrift zu kontrastarm. | Dunklere Textfarben, getrennte Status-Texttokens und Kontrastprüfung. [S3] |
| Suche, Benachrichtigungen und Änderungsmetadaten als feste Mockup-Elemente. | Aus einer Illustration wird sonst unbeabsichtigt eine neue Funktionsanforderung. | Nur tatsächlich vorhandene Funktionen und Daten darstellen. |
| „Responsive prüfen“, aber ohne benannte Werkzeuge oder Belege. | Es bleibt unklar, ob wirklich im Browser geprüft wurde. | Playwright beziehungsweise vorhandene Browser-Werkzeuge, dokumentierte Viewports, Screenshots und Teststatus. [S4] |
| „Alles gleich“ ohne Abgrenzung der Ansichten. | Login, Formulare, Kalender und Digital Signage könnten unpassend gleichgeschaltet werden. | Gemeinsame Designsprache, aber passende Layoutvarianten. |

Konkrete Nachrechnung der alten Farbwerte, jeweils als voll deckender Text auf dem genannten Hintergrund: `#238636` auf `#EAF8ED` ergibt rund **4,22:1**, `#B26A00` auf `#FFF4D6` rund **3,87:1**, `#9CA3AF` auf Weiss rund **2,54:1**. Für normalen Text ist nach WCAG 2.2 AA grundsätzlich mindestens **4,5:1** erforderlich. Die neuen Tokens korrigieren diese Kombinationen. Das ist eine Bewertung der früher vorgeschlagenen Werte, keine Kontrastmessung der laufenden Anwendung. [S3]

## 3. Geltungsbereich: Alle vorhandenen Tools und Seitentypen

Erstelle eine vollständige Bestandsaufnahme aus Routen, Blueprints, Templates, Navigation, Dialogen und erreichbaren UI-Zuständen. Beschränke dich nicht auf Links in der Sidebar: Auch Bearbeitungsseiten, Unterseiten und rollenabhängige Ansichten zählen.

| Vorhandener Seitentyp / Tool | Designauftrag |
|---|---|
| Dashboard und Übersichtsseiten | Verständliche Hierarchie, echte Kennzahlen und konsistente Karten. Keine zusätzlichen Statistik-Kacheln als Dekoration. |
| Listen, Suche und Stammdatenverwaltung | Einheitlicher Seitenkopf, Tabellen, Filter, Aktionen, Status, leere Zustände und Pagination. |
| Anlegen, Bearbeiten und Detailansichten | Einheitliche Labels, Feldgruppen, Validierung, Aktionsleiste und Darstellung von Metadaten. |
| Einstellungen und Konfiguration | Thematische Gruppen, verständliche Erklärungen, konsistente Speichern-/Abbrechen-Logik. |
| Benutzer, Rollen und Zugriffe | Dasselbe Design; Rollenmodell und serverseitige Autorisierung unverändert. |
| Import, Export und Schnittstellenverwaltung | Einheitliche Dateiauswahl, Resultate und Fehlermeldungen; Fortschritt nur bei vorhandener technischer Grundlage. |
| Kalender, Planung, Kanban und ähnliche Fachwerkzeuge | Gemeinsame Farben, Schrift, Navigation und Bedienelemente; das fachlich notwendige Arbeitslayout erhalten. |
| Medien, Vorlagen und Inhaltsverwaltung | Gemeinsame Karten, Vorschauen, Auswahlzustände und Aktionen. |
| Modals, Dropdowns, Tabs und Bestätigungen | Auch diese Oberflächen migrieren, nicht nur vollständige HTML-Seiten. |
| Login, Zugriff verweigert und Fehlerseiten | Gemeinsame Marken- und Formgestaltung; kein erzwungener Admin-Seitenrahmen vor der Anmeldung. |
| Öffentliche Ansichten, Druck, Kiosk und Digital Signage | Gemeinsame Tokens nur dort übernehmen, wo passend. Keine Sidebar, keine Admin-Aktionen, keine pauschale Desktop-Schriftgrösse übertragen. Als eigene Layoutvarianten erfassen und gegen unbeabsichtigte Änderungen prüfen. |

Diese Tabelle ist eine Prüfliste, kein Auftrag, fehlende Module neu zu entwickeln. Verwende die echten Modulnamen und Routen des jeweiligen Projekts.

## 4. Technologien und Werkzeuge: explizit und mit klaren Grenzen

### 4.1 Laufzeit und Implementierung

| Technologie | Vorgabe |
|---|---|
| Flask | Bestehende Anwendung, Blueprints, Endpoints, Request-Verarbeitung und Sessions weiterverwenden. |
| Jinja2 | Vorhandene Template-Vererbung, Partials und Macros nutzen; wiederkehrende UI nicht kopieren. |
| Tabler / `@tabler/core` | Verbindliche Komponentenbasis. Installierte Version aus Projekt und Assets ermitteln, nicht automatisch aktualisieren. |
| Bootstrap | Nur die vorhandene, zur Tabler-Integration passende Basis nutzen. Kein zweites Bootstrap-CSS oder zweiter JS-Bundle. |
| Tabler Icons | Ein einziges konsistentes Icon-System. Bestehende SVG-/Sprite-Einbindung weiterverwenden. Keine Emojis als UI-Icons. |
| CSS / vorhandenes Sass | Zentrale Tokens und Komponenten-Styles. Vorhandenen Build verwenden, keinen neuen Build nur für die Neugestaltung einführen. |
| JavaScript | Vorhandene Skripte und Bootstrap-/Tabler-Interaktionen wiederverwenden. Neue kleine Interaktionen ohne neue Laufzeitbibliothek. |
| Vorhandene Bibliotheken | Zum Beispiel HTMX oder Alpine nur weiterverwenden, wenn schon Teil der Anwendung. Nicht neu einführen. |
| Nicht zulässig | React, Vue, Svelte, Tailwind, neue UI-Kits, Frameworkwechsel oder eine neue SPA als Nebenprodukt. |

### 4.2 Arbeits- und Prüfwerkzeuge des Coding Agents

| Werkzeug | Konkreter Einsatz | Grenze / Fallback |
|---|---|---|
| Codex oder Claude Code | Repository lesen, begrenzte Änderungen implementieren, Tests ausführen und Befunde dokumentieren. | Nur tatsächlich verfügbare Werkzeuge verwenden. |
| Git | Arbeitszustand vorab prüfen, Diffs lesen, fremde Änderungen erhalten, eigene Änderungen nachvollziehbar halten. | Kein `reset --hard`, kein automatischer Push, kein Deployment ohne Auftrag. |
| Shell / Terminal | Bestehende Start-, Build- und Testbefehle ausführen; Versionen und Assets ermitteln. | Bestehende Projektumgebung verwenden. Keine produktiven Daten verändern. |
| ripgrep (`rg`) | Templates, Inline-Styles, Farbwerte, Klassen, Duplikate und JS-Selektoren suchen. | Falls nicht vorhanden: `git grep`, vorhandene Dateisuche oder PowerShell `Select-String`. |
| Playwright | Echte Seiten öffnen, Navigation und Formulare bedienen, Viewports prüfen und Screenshots erstellen. | Vorhandene Integration nutzen. Fehlende Browser-/Testumgebung ausdrücklich als Blocker melden. |
| Playwright Test | Wenn im Projekt vorhanden: Screenshot-Vergleiche mit freigegebenen Referenzen, zum Beispiel `toHaveScreenshot()`. [S4] | Diese Assertion gehört zum Playwright-Test-Runner; nicht eine identische Python-API erfinden. |
| Browser-DevTools / vorhandenes Chrome-DevTools-MCP | Berechnete CSS-Werte, Box-Modell, Netzwerk, Konsole, Fokus und überlaufende Elemente untersuchen. | Kein MCP als vorhanden voraussetzen. Vorhandene gleichwertige Browser-Werkzeuge sind ausreichend. |
| axe-core / `@axe-core/playwright` | Automatisierte Accessibility-Prüfung, wenn verfügbar. [S5] | Nur Prüfwerkzeug, keine neue Produktionsabhängigkeit. Ersetzt keine manuelle Tastaturprüfung. |
| Flask-Testclient und bestehendes pytest/unittest | GET-/POST-Verhalten, Weiterleitungen, Berechtigungen und Regressionen prüfen. [S6] | Vorhandenes Testframework behalten. Kein Wechsel allein wegen dieses Prompts. |
| Vorhandene Linter und Formatter | Bestehende Qualitätsprüfungen für Python, Templates, CSS und JavaScript ausführen. | Nicht das ganze Repository unnötig neu formatieren. |

Nicht verfügbare Werkzeuge zuerst durch vorhandene gleichwertige Mittel ersetzen. Neue reine Entwicklungsabhängigkeiten nur nach den Repository-Regeln beziehungsweise mit nötiger Freigabe installieren. Fehlende Tests nicht als bestanden deklarieren und Sicherheitsmechanismen nicht deaktivieren, um Tests zu erleichtern.

## 5. Feste visuelle Basis

Die Stilrichtung bleibt: dunkle Petrol-Sidebar, warmer heller Hintergrund, weisse Inhaltsflächen, Burgunder als Handlungsakzent und zurückhaltende Trennlinien.

### 5.1 Zentrale Farb-Tokens

Definiere diese Werte einmal in einer gemeinsamen Token-Datei oder der entsprechenden vorhandenen zentralen Struktur. Die Namen sind der gemeinsame Vertrag; keine zweite parallele Palette anlegen.

```css
:root {
  --app-bg: #F6F4F1;
  --app-surface: #FFFFFF;
  --app-surface-soft: #FAF9F7;

  --app-sidebar: #173C3F;
  --app-sidebar-hover: #214A4D;
  --app-sidebar-active: #31585B;
  --app-sidebar-text: #C7D8D9;
  --app-sidebar-label: #9AB7BA;
  --app-sidebar-indicator: #F3A6C0;

  --app-primary: #A3164D;
  --app-primary-rgb: 163, 22, 77;
  --app-primary-hover: #8E123F;
  --app-primary-active: #7C1037;
  --app-primary-soft: #F7E8EE;
  --app-on-primary: #FFFFFF;

  --app-text: #1F2937;
  --app-text-muted: #596273;
  --app-border: #E5E7EB;
  --app-border-soft: #EFECE8;
  --app-control-border: #808B99;
  --app-focus: #A3164D;

  --app-success: #2FB344;
  --app-success-text: #166534;
  --app-success-soft: #EAF8ED;
  --app-warning: #F59F00;
  --app-warning-text: #854D0E;
  --app-warning-soft: #FFF4D6;
  --app-danger: #D63939;
  --app-danger-text: #B42318;
  --app-danger-soft: #FCEAEA;
  --app-info: #4299E1;
  --app-info-text: #175CD3;
  --app-info-soft: #EAF4FC;
  --app-neutral-text: #475467;
  --app-neutral-soft: #EEF0F2;
}
```

Burgunder bezeichnet die wichtigste Handlung, Auswahl oder einen Link, nicht eine beliebige grosse Hintergrundfläche. Für kleine Statustexte immer `*-text` auf `*-soft` verwenden, nicht die hellere Akzentfarbe. Destruktive Buttons verwenden einen geprüften dunklen Rotton, beispielsweise `--app-danger-text` mit Weiss.

Die helle Sidebar-Akzentlinie bleibt als optionaler Token verfügbar: Dunkles Burgunder hebt sich gegen Petrol schlecht ab. Aktive Navigation primär durch sanft getönten Hintergrund, Schriftgewicht und `aria-current` kennzeichnen; höchstens eine feine Akzentlinie ohne Layoutsprung ergänzen. Keine auffällige pinke Kontur plus Unterstreichung. Tastaturfokus bleibt davon getrennt deutlich sichtbar.

Helle Card-Rahmen sind dekorative Trennlinien. Wo eine Umrandung nötig ist, um ein Eingabefeld oder Bedienelement zu erkennen, `--app-control-border` und die tatsächliche Hintergrundfarbe auf ausreichenden Kontrast prüfen. [S7]

### 5.2 Typografie, Masse und Abstände

| Element | Fester Standard |
|---|---|
| Schrift für Fliesstext, Navigation, Tabellen, Formulare und Buttons | `Arial, Helvetica, sans-serif` |
| Schrift für H1 und Card-Überschriften | `Georgia, "Times New Roman", serif` |
| Fliesstext / Eingabefelder | `1rem`, Zeilenhöhe `1.5` |
| H1 ab Desktop-Breakpoint | `2.125rem`, Gewicht `700`, Zeilenhöhe `1.2` |
| H1 unter Desktop-Breakpoint | `1.75rem`, Gewicht `700`, Zeilenhöhe `1.2` |
| Card-Überschrift | `1.25rem`, Gewicht `700`, Zeilenhöhe `1.3` |
| Navigation / Tabellen / Labels | `0.875rem`; Labels Gewicht `600` |
| Hilfetext / sekundäre Metadaten | `0.8125rem`; wichtige Handlungsinformationen nicht kleiner setzen |
| Sidebar | `248px` breit auf Desktop |
| Topbar, nur bei tatsächlicher Funktion | `64px` Mindesthöhe, darf bei Zoom/Inhalten wachsen; keine leere zusätzliche Leiste |
| Arbeitsbreite | Volle verfügbare Breite neben der Sidebar, keine Obergrenze oder schmale innere Gesamtspalte; auch für Formulare |
| Inhaltspadding | Desktop `32px`, Tablet `24px`, Smartphone `16px` |
| Card-Radius | `12px` |
| Button-/Feld-/Nav-Radius | `8px` |
| Status-Badge-Radius | `999px` |
| Standard-Interaktionshöhe | mindestens `44px`; unterstützende Iconbuttons mindestens `44 × 44px` Trefferfläche, Iconzeichnung etwa `20px`; mehrzeilige Labels dürfen wachsen |
| Kompakte Arbeits-/Tabellenzeile | typischerweise `56–72px`, bei Umbruch, Fehlern oder Zoom wachsend; keine fixe Maximalhöhe |
| Card-Innenabstand | `24px`, auf Smartphone `16px` |
| Abstand zwischen Hauptblöcken | `24px` |
| Formular-Grid-Abstand | `24px` |
| Erlaubte allgemeine Abstandsskala | `4 / 8 / 12 / 16 / 24 / 32 / 40 / 48px` |
| Schatten | `0 1px 2px rgba(0, 0, 0, 0.025)` |

Die Serifentitel greifen die visuelle Richtung des Mockups ausdrücklich auf. Die Schriftwahl bleibt nicht mehr der jeweiligen Tabler-Standardkonfiguration überlassen. Keine pro Seite abweichende Schrift, keine nachträglich eingeführte Condensed-Schrift und kein unkontrollierter externer Font-Aufruf.

Die `rem`-Werte gehen vom unveränderten Browser-Standard aus. Keine erzwungene 16px-Root-Grösse, keine Zoom-Sperre und keine Schriftverkleinerung, um Probleme zu kaschieren. Fontstacks garantieren ohne identische installierte Fonts keine pixelgleichen Ergebnisse über Betriebssysteme hinweg; dokumentiere deshalb den tatsächlich verwendeten Font der Referenzumgebung. Eine spätere freigegebene selbst gehostete Markenschrift wird zentral und mit neuen geprüften Referenzen eingeführt.

Lege wiederkehrende Masswerte und kompakte Varianten zentral als Tokens an. Keine leicht unterschiedlichen Radien oder Paddings über einzelne Templates verteilen. Freiraum zwischen Gruppen bleibt sinnvoll; künstlich aufgeblähte Container und abgeschnittene Pflichtinformationen nicht.

Kurze Felder nebeneinander: Menge/Einheit, Preis/Zielgruppe, Dauer/Zeiteinheit. Ein Zahlenwert benötigt nicht eine komplette Bildschirmzeile. Textareas beginnen mit angemessener Höhe und bleiben vergrösserbar; lange Texte nicht in winzige Scrollschlitze pressen. Formulare bleiben ungefähr 1rem, wichtige Labels mindestens 0,875rem. Dies sind Projektziele, kein behaupteter Konformitätsnachweis.

### 5.3 Gemeinsame Symbolsprache

Nutze das vorhandene zentrale `icon`-Makro und die tatsächlich verfügbaren Tabler-Sprite-IDs. Keine neue Iconbibliothek und keine Emojis als Bedienelemente. Ein fehlendes Symbol darf nicht unbemerkt leer bleiben.

| ASCII-Kürzel in den Skizzen | In der Anwendung | Sichtbarer Text, beispielsweise |
|---|---|---|
| `[S]` | Speicher-Symbol | Rezept speichern |
| `[+]` | Plus | Zutat hinzufügen |
| `[E]` | Stift | Bearbeiten |
| `[>]` / `[v]` | Chevron geschlossen/offen | Details / Details schliessen |
| `[...]` | Menü-/Drei-Punkte-Symbol | Aktionen / Weitere Aktionen |
| `[^]` / `[v]` | Auf-/Ab-Pfeil im Sortierkontext | Nach oben / Nach unten |
| `[X]` | Kontextgerechtes Entfernen-Symbol | Aus Rezept entfernen |
| `[?]` | Lupe, nicht ein Fragezeichen | Suchen |
| `[O]` | Auge | Vorschau |
| `[P]` | Drucker | PDF öffnen / Drucken |
| `[<]` | Pfeil nach links | Zur Rezeptliste |
| `[!]` | Warnsymbol | Konkrete fehlende oder ungeklärte Angabe |
| `[OK]` | Haken | Nur den tatsächlich bestätigten Zustand benennen |

**Die ASCII-Kürzel werden nicht als Buchstaben in die Anwendung übernommen.** Sie veranschaulichen Icon plus Text. Produkttexte verwenden korrekte Umlaute und Schweizer Schreibweise; `ae/oe/ue` kommen nur in den ASCII-Skizzen zum Einsatz.

Hauptaktionen auch auf dem Smartphone beschriften. Ein Tooltipp oder zugänglicher Name allein ersetzt für unerfahrene Benutzer keinen sichtbaren Text. Unterstützende reine Iconbuttons nur in eindeutigem Kontext; Fokus, Name und Trefferfläche prüfen. Dekorative Icons neben Text nicht nochmals vorlesen lassen. Status nie nur durch Farbe darstellen.

**Auftraggeber-Präzisierung vom 13. September 2026:** Mehr verständliche Symbole und weniger wiederholte Wörter machen die Oberfläche ruhiger. Vorhandene Tabler-Symbole gezielt auch bei kurzen Labels und unterstützenden Hinweisen einsetzen; gleichartige Texte nicht in jeder Zeile ausschreiben. Hauptaktionen und Navigation behalten kurze sichtbare Labels. Eindeutige Nebenaktionen dürfen im klaren Zeilenkontext als Symbolbutton erscheinen, mit zugänglichem Namen und verständlichem Tooltip; notwendige Warnungen und Formfeldbezeichnungen bleiben verständlich. Beispielsweise genügt in einer bereits nummerierten History-Zeile «Ansehen» mit Auge statt eines erneut ausgeschriebenen Standtitels. Keine zusätzlichen dekorativen Symbole ohne Informationswert. Diese Präzisierung gilt bei der Prüfung laufender und folgender UI-Pakete.

## 6. Tabler tatsächlich anbinden, nicht nur umfärben

Untersuche zuerst die installierte Tabler-/Bootstrap-Version und die ausgelieferten CSS-Dateien. Dokumentation neuerer Versionen ist keine Aufforderung zum Upgrade.

Eigene `--app-*`-Variablen müssen an die tatsächlich verwendeten Theme- und Komponentenvariablen angeschlossen werden. Tabler dokumentiert beispielsweise `--tblr-primary`; Bootstrap-Komponenten können eigene lokale Variablen besitzen. Deshalb ist ein Eintrag in `:root` allein kein Nachweis, dass Buttons, Checkboxen, Tabs und Pagination richtig aussehen. [S1, S2]

Prüfe insbesondere Primärfarbe und RGB-Varianten, Body-Hintergrund, Schriftfamilien, Linkfarben sowie Normal-, Hover-, Active-, Focus-, Disabled- und Invalid-Zustände. `--app-primary-rgb` steht hier für RGB-Kanäle und wird nicht aus einem Hex-String zusammengesetzt.

Nutze den bestehenden Sass-Build, falls dieser bereits die Theme-Erstellung übernimmt. Sonst verwende schlanke, korrekt nach den Herstellerstyles geladene zentrale Overrides. Bearbeite keine minifizierten Vendor-Dateien und löse Konflikte nicht durch eine wachsende Sammlung von `!important`.

Prüfe berechnete Styles im Browser. Verhindere unbeabsichtigte Auswirkungen auf Druck, öffentliche Seiten, Signage und eingebundene Drittkomponenten durch passende Layout-/Bereichsselektoren. Entferne alte Überschreibungen erst nach Prüfung ihrer bisherigen Nutzung.

## 7. Gemeinsamer Seitenrahmen und Navigation

Alle regulären internen Tools verwenden denselben Seitenrahmen: Sidebar, bei benötigten Funktionen Topbar, Seitenkopf und Hauptinhalt. Topbar-Inhalte nicht erfinden; ohne zusätzliche Funktion keine leere Zierleiste erzeugen. Die gewählte Anwendungslösung wird zentral umgesetzt, nicht pro Tool neu entschieden.

Der Hauptbereich braucht `min-width: 0`. Seine Breite wird aus dem verfügbaren Bereich neben der Sidebar berechnet; kein `100vw` über die Sidebar hinweg. Die frühere Vorgabe «Kopf, Bereichsnavigation und Hauptinhalt teilen dieselben äusseren Kanten» ist am 2026-09-20 ersetzt durch: Seitenkopf, Statusbar und Hauptinhalt teilen dieselben äusseren Kanten; eine horizontale Bereichsnavigation existiert nicht mehr. Auch innere Gesamtcontainer und Formulare nutzen die volle Arbeitsbreite. Nur einzelne kurze Felder und Lesetexte lokal begrenzen; breite Hauptarbeit mit schmalerem Prüfkontext ist ein gemeinsames Layoutmuster, keine schmale Gesamtspalte.

Die Sidebar erhält das vorhandene Original-Logo und den Produktnamen. Kein Logo nachzeichnen, keinen Claim ergänzen. Die vier fachlichen Haupteinstiege bleiben **Wochenplan**, **Menüs & Bausteine**, **Vorschau & Bildschirme** und **Einstellungen**, entsprechend vorhandenen Rechten. Unterfunktionen im Bereich zeigen, nicht erneut als 14 gleichrangige Sidebarlinks.

Navigationseinträge: mindestens 44px hoch, Icon 20px plus sichtbarer Text, Abstand 12px, Radius 8px. Gruppentitel: 12px, Gewicht 600, dezente Grossschreibung. Aktiver Eintrag: sanft getönte Fläche, kontrastgeprüfte Schrift, etwas stärkeres Schriftgewicht; eine feine Akzentlinie ist optional. Keine auffällige pinke Kontur plus Unterstreichung. Fokus ist ein eigener deutlich sichtbarer Zustand.

Der Navigationsbereich scrollt bei Platzmangel, der Logout bleibt erreichbar. Profilfunktionen an einem klaren Ort bündeln, nicht mehrfach dieselbe Benutzerinformation in Sidebar und Topbar wiederholen. Rollenabhängige Sichtbarkeit erhalten; sie ersetzt keine serverseitige Autorisierung.

Seitenkopf: logisch korrekter Breadcrumb, genau eine H1, gegebenenfalls ein kurzer wirklich hilfreicher Satz und die wichtigsten Seitenaktionen. Danach folgt die Kernarbeit vor optionaler Verwaltung. Kein erfundener Breadcrumb-Zielpfad, kein dekorativer Eyebrow und kein Fülltext wie „Hier können Sie die Verwaltung verwalten“. Eine Bereichsauswahl pro Kontext: globale Navigation, Bereichslinks und lokale Abschnittslinks erfüllen verschiedene Aufgaben; keine doppelten Cafeteria-/Patientenreihen.

## 8. Komponentenregeln für alle Tools

| Komponente | Verbindliche Regel |
|---|---|
| Cards | Weisse Fläche, 12px Radius, dezenter Rand und minimaler Schatten nur bei inhaltlich nötiger Gruppierung. Wiederholte Zutaten, Schritte, Bausteine und Zuordnungen als kompakte Arbeitszeilen, keine hohe offene Card je Objekt oder Schmuckkarte. Keine Card in Card ohne fachlichen Grund. |
| Bereichs- und Abschnittsnavigation | Eine Auswahl je Kontext, zurückhaltende aktive Kennzeichnung aus zentralen Tokens. Echte Seitenwechsel als Links; lokale Rezeptlinks führen zu sichtbaren Abschnitten statt Zutaten hinter Tab-Inhalten zu verbergen. Dynamische Tabs nur für passende vorhandene Aufgaben mit Tastatur-/ARIA-Semantik; keine doppelte Auswahl oder vorgeschriebene Kombination von Kontur und Unterlinie. |
| Buttons | Eine hervorgehobene Speicherhandlung je bestehendem Formular, ohne Scrollreise erreichbar. Hauptaktionen mit Icon und sichtbarem kurzem Text auch mobil. Nebenaktionen neutral; mindestens 44px Bedienhöhe. Keine universelle Primäraktion auf Leseseiten oder globale Speicherung unabhängiger Formulare erzwingen. |
| Formularfelder | Sichtbares Label, tatsächlicher Pflichtstatus, sinnvoller Datentyp, 44px Mindesthöhe und verständlicher Hilfetext. Kurze Felder gemeinsam gruppieren; Menge/Einheit direkt in der Zutatenzeile bearbeiten. Genau ein massgebliches Feld je Wert. Placeholder ersetzt kein Label. |
| Validierung | Bestehende native und serverseitige Regeln erhalten. Fehlerzusammenfassung mit sichtbarem Feld verknüpfen, betroffenen geschlossenen Bereich öffnen/erschliessen, Fokus sinnvoll setzen; `aria-invalid`/`aria-describedby` passend setzen. Werte und Fehlermarker nach erneutem Schliessen erhalten. |
| Textareas | Sinnvolle Mindesthöhe und vertikale Vergrösserung erlauben. Zeichenlimit und Zähler nur aus echten bestehenden Vorgaben ableiten. |
| Tabellen | Semantische Tabelle, Header in normaler Schreibweise, ausreichend Padding, dezente Zeilentrennung. Daten und Aktionen nicht abschneiden oder unter 14px verkleinern. |
| Status-Badges | 13px Text, 4px/10px Padding, Pill-Form, dunkle Status-Textfarbe auf heller Statusfläche. Reale Backend-Zustände mit Text zuordnen: gespeichert, geprüft, aktiviert und veröffentlicht unterscheiden; alter Prüfstand bestätigt keine neuen Eingaben. Fehlend ist weder null noch allergenfrei. |
| Zeilenaktionen | Häufige Aktionen beschriftet sichtbar; seltene in ein echtes Dropdown. Keine versteckten Nur-Hover-Aktionen. Kein leeres Dreipunktmenü. |
| Suche und Filter | Suche und höchstens zwei häufige vorhandene Filter standardmässig; zusätzliche Filter bei Bedarf, aktive Auswahl und Reset bleiben erkennbar. Bestehende Suchparameter kombinierbar erhalten; bei serverseitiger Pagination nicht nur die sichtbare Seite als Gesamtbestand filtern. |
| Pagination | In den Listenabschluss integrieren. Gesamtzahl und Seitengrösse aus echten Daten. Keine Seitennavigation bei nur einer Seite. |
| Leere Zustände | „Noch keine Daten“, „kein Suchtreffer“, „Laden fehlgeschlagen“ und „keine Berechtigung“ unterscheiden. Keine erfundene Nullzählung; nur vorhandene erlaubte Folgeaktionen, keine Pagination ohne Daten. |
| Erfolg und Fehler | Gemeinsame Flash-/Alert-Komponente, verständliche Texte, Feldfehler zusätzlich lokal. Wichtige Informationen nicht nach kurzer Zeit automatisch entfernen. |
| Modals | Nur für passende kurze Aufgaben. Aussagekräftiger Titel, korrekter Fokus, Tastaturbedienung, Rückkehr zum Auslöser. Lange Formulare nicht in kleine Modals pressen. |
| Destruktive Aktionen | Bestehende Bestätigungen und Schutzmassnahmen erhalten. Objekt und Konsequenz benennen. Keine zusätzlichen riskanten Aktionen erfinden. |
| Ladezustände | Nur dort anzeigen, wo tatsächlich geladen wird. Keine künstlichen Wartezeiten oder erfundenen Fortschrittsprozente. |

Ein statisches Anlegeformular braucht nicht automatisch einen „Abbrechen“-Button. Ein Dashboard braucht nicht automatisch eine Suche. Eine Datentabelle braucht nicht automatisch eine Spalte „Letzte Änderung“. Das Mockup ist keine Datenquelle.

Sprache: Bestehende Anrede und Anwendungssprache konsistent halten. Für deutschsprachige Schweizer Anwendungen Schweizer Rechtschreibung verwenden. Sichtbare Datumsformate können lokalisiert werden; maschinelle Feldwerte und erwartete Backend-Formate unverändert lassen. Keine technischen Interna oder vertraulichen Informationen in Endbenutzer-Fehlermeldungen.

### 8.1 Interaktions- und Formularinvarianten

Die Skizzen sind nicht allein durch CSS abzuhaken. Folgende Verhaltensregeln gelten bei jeder Umsetzung:

| Situation | Verpflichtendes Verhalten |
|---|---|
| Detailbereich öffnen/schliessen | Keine Speicherung, kein Reset, keine verlorenen Werte. Auslöser benennt Zustand; Tastaturbedienung möglich. |
| Gefüllte Zusatzfelder schliessen | Bedeutung bleibt in kurzer Zusammenfassung erkennbar; Quellenrohwerte müssen nicht ständig sichtbar sein. |
| Neue Zutat oder neuer Schritt | Betroffenes neues Objekt öffnen und Fokus sinnvoll setzen; bestehende Eingaben und Reihenfolge erhalten. |
| Menge direkt ändern | Kein zusätzlicher Detaildialog nötig; genau ein massgebliches Eingabefeld im Formular. |
| Reihenfolge ändern | Vorhandenen Strukturweg nutzen; beim betroffenen Objekt bleiben; keine alleinige Drag-and-drop-Bedienung. |
| Entfernen | Lokalen und globalen Geltungsbereich unterscheiden; bestehende Schutzregeln erhalten, keine ungefragte neue Löschfunktion. |
| Intern navigieren mit Änderungen | Sichere Rückfrage mit „Weiter bearbeiten“ und „Änderungen verwerfen“, soweit darstellungsseitig möglich. Keine neue ungefragte Speicherung. |
| Speichern bestätigt | Erst nach erfolgreicher Antwort den tatsächlichen Speicherzustand anzeigen. Nur betroffenen Formularbereich als gespeichert kennzeichnen. |
| Speicherantwort unklar | Unsicherheit benennen; aktuellen Stand prüfen, bevor erneut geschrieben wird. Keine automatische Wiederholung nicht nachweislich sicher wiederholbarer Aktionen. |
| Ungespeicherte Änderungen prüfen | Nicht als vom alten Prüfergebnis bestätigt darstellen. Speichern, Prüfen, Aktivieren und Veröffentlichen getrennt halten. |
| Inhalt nicht erfasst | Nicht als null, vollständig, allergenfrei oder geprüft ausgeben. Quelle und Prüfstand nicht aus Titel oder Bild ableiten. |
| Session oder Berechtigung fehlt | Bestehenden Schutzweg nutzen, kein falscher Erfolg und keine Sicherheitsabschwächung. |
| 200 % Zoom / Smartphone | Umordnen statt schrumpfen; Fokus und Aktionsleiste verdecken nichts; Hauptaktionen bleiben beschriftet. |

**Keine doppelte Formularimplementierung:** Eine kompakte Zeile und ihr Detailbereich gehören zu denselben vorhandenen Feldern. Keine konkurrierenden `name`-Attribute, IDs oder versteckten Kopien mit veralteten Werten. Kein Entfernen aus dem DOM, wenn dadurch vorhandene Werte nicht mehr übermittelt werden. `readonly` und `disabled` sind nicht austauschbar.

**Fehler gehen vor Kompaktheit:** Ein geöffneter Pflichtfehler darf mehr Raum benötigen. Eine Warnung zur ungeprüften Rezeptquelle bleibt in der Übersicht; Rohwerte wie Quellen-IDs können nachgeordnet sein. Nicht jede fehlende optionale Notiz mit einer Warnung versehen.

**Keine zusätzliche Pflichtklickstrecke:** Menüs, Dropdowns und Details reduzieren seltene Bedienung. Häufige Schritte wie Mengenänderung, Öffnen des gewünschten Eintrags oder Speichern dürfen dadurch nicht umständlicher werden. Vergleiche Aufgabenaufwand, nicht nur Screenshot-Höhe.

### 8.2 Verbindliche Strukturreferenzen M01–M20

Die Mockups sind **verbindliche Struktur- und Interaktionsmuster**, keine pixelgenauen Screenshots und kein Nachweis einer bereits funktionierenden Anwendung. Breite Rahmen zeigen die gesamte verfügbare Arbeitsfläche, nicht eine feste Zeichen- oder Pixelbreite. Die Darstellungen sind absichtlich ohne zusätzliche Bilder verständlich. Im Rezepteditor sind „Rezept“, „Zutaten“ und „Zubereitung“ lokale Sprunglinks zu sichtbaren Abschnitten, keine Pflicht für versteckte Tab-Inhalte. So bleibt die Zutatenübersicht unmittelbar nutzbar.

Alle Datensätze, Mengen, Zeiträume, Zählungen und Statusbeispiele sind synthetisch. Keine Rezeptanweisung oder fachliche Freigabe daraus ableiten. Kein neues Feature, Filterfeld, Statuswert, Berechtigungsmodell oder Backendverhalten allein aus einer Skizze einbauen. Angezeigte Zahlen aus echten Daten berechnen bzw. nur vorhandene Werte nutzen; sonst die entsprechende Information weglassen oder als nicht verfügbar benennen.

Die Skizzen zeigen verschiedenartige Seitentypen und Zustände, nicht 20 neu zu bauende Seiten. Ordne jede tatsächliche Seite einem Muster zu und dokumentiere notwendige fachliche Unterschiede. Jede Skizze wird zusammen mit ihren anschliessenden Verhaltensregeln umgesetzt. Erklärende Anmerkungen innerhalb der Rahmen, beispielsweise „Weitere Treffer folgen“, sind Kommentare zum Layout, keine zusätzlich zu erzeugenden Hilfetextblöcke. Sichtbare Labels und Aktionen sind dagegen bewusst vorgegeben.



**Mockup-Verzeichnis**

| ID | Strukturreferenz |
|---|---|
| M01 | Gemeinsamer Seitenrahmen für alle internen Arbeitsseiten |
| M02 | Rezepteditor: kompakter Ausgangszustand |
| M03 | Rezeptzutat: nur die benötigten Details öffnen |
| M04 | Zubereitung: Kurzfassung und gezielte Bearbeitung |
| M05 | Zeilenaktionen: kompakt, beschriftet und kontextbezogen |
| M06 | Rezepteditor auf dem Smartphone |
| M07 | Menüübersicht: Text und Handlung vor Bildern |
| M08 | Bausteinliste mit gezielt erweiterten Filtern |
| M09 | Wochenübersicht: auswählen zuerst, anlegen bei Bedarf |
| M10 | Cafeteriaplan: Arbeitsraster statt Verwaltungsblöcke |
| M11 | Patientenplan: kompakte Tagesgruppen mit Mittag und Abend |
| M12 | Menüeditor: breite Hauptarbeit, schmalerer Prüfkontext |
| M13 | Baustein bearbeiten: eindeutige Allergenfelder |
| M14 | Drucken und Vorschau: Arbeitsauftrag von Layoutverwaltung trennen |
| M15 | Einstellungen: kompakte Zusammenfassung, Bearbeitung bei Bedarf |
| M16 | Erscheinungsbild: gespeicherten Entwurf eindeutig kennzeichnen |
| M17 | Datenimport: Aufgabe und Fehler, nicht technische Rohdaten |
| M18 | Benutzer und ähnliche Verwaltungslisten |
| M19 | Fehler in einem zuvor geschlossenen Detailbereich |
| M20 | Leere Daten, keine Treffer und Ladefehler unterscheiden |

#### M01 — Gemeinsamer Seitenrahmen für alle internen Arbeitsseiten

*(Ersetzt am 2026-09-20 durch: Eingerückte Sidebar, Statusbar unter dem Titel, keine horizontalen Tabs)*
Desktop; Sidebar links, gesamte verbleibende Breite rechts. Der Marker `>` steht nur für die dezente aktive Auswahl. Unterpunkte erscheinen eingerückt NUR bei aktivem Oberpunkt.

```text
+----------------------+  +---------------------------------------------------------------------------------+
| SUEDHANG             |  | SEITENTITEL / aktuelles Objekt                            [Hauptaktion]         |
| Menueplanung         |  | Kurzer Kontext nur, wenn er bei dieser Aufgabe hilft.                           |
+----------------------+  +---------------------------------------------------------------------------------+
|   Wochenplan         |  | [STATUSBAR: 1-5 echte Felder | Neutral/Erfolg/Warnung/Fehler]                  |
| > Menues & Bausteine |  +---------------------------------------------------------------------------------+
|     Menues           |  | Suche / Filter: nur wenn noetig, unter der Statusbar                            |
|     Bausteine        |  +---------------------------------------------------------------------------------+
|     Zutaten          |  | ARBEITSINHALT: Liste, Formular, Wochenplan oder Editor                          |
|     ...              |  |                                                                                 |
|   Vorschau &         |  | Die Flaeche reicht bis zum gemeinsamen rechten Seitenrand.                      |
|   Bildschirme        |  | Keine zusaetzliche schmale zentrierte Gesamtspalte.                             |
|   Einstellungen      |  |                                                                                 |
|                      |  | Kurze Felder nebeneinander. Lange Inhalte erhalten mehr Raum.                   |
|                      |  | Keine leeren Karten, um freie Flaeche kuenstlich zu fuellen.                    |
|                      |  |                                                                                 |
|                      |  | Details am betroffenen Objekt oeffnen, nicht alles dauerhaft.                   |
|                      |  |                                                                                 |
|                      |  +---------------------------------------------------------------------------------+
|                      |  | [Sekundaeres / Technisches nachrangig bzw. einklappbar]                         |
| Konto                |  |                                                                                 |
| Abmelden             |  |                                                                                 |
+----------------------+  +---------------------------------------------------------------------------------+
```

**Pflicht:** Kopf, Bereichsnavigation und Hauptinhalt nutzen dieselben äusseren Kanten. Eine zusätzliche Topbar nur für tatsächliche Funktionen, nie als leere Zierfläche. Der Bereichstitel darf ohne Karte stehen.

**WP1-Shell-Vertrag, umgesetzt am 2026-09-20:** Der frühere Pflichtsatz «Kopf, Bereichsnavigation und Hauptinhalt» ist ersetzt durch «Seitenkopf, Statusbar und Hauptinhalt». `base_tabler.html` ruft `render_tabs()` nicht mehr auf. `.admin-statusbar` stellt 1–5 Slots als responsive Grid ohne horizontales Dokument-Scrolling dar. Jeder Slot verwendet `.admin-statusbar-item` plus genau eine Variante `--neutral`, `--success`, `--warning` oder `--danger`; Varianten bilden ausschliesslich auf die bestehenden `--app-*-text`-/`--app-*-soft`-Tokens ab. `.admin-nav-subitems` liefert Einrückung, Trennlinie und mindestens 48 px hohe Unterpunkte. Die 34 zentralen `--app-*`-Farbtokens bleiben unverändert. Nachweis: `test_ui_fullwidth_shell_browser.py`, `test_admin_display_browser.py`, `test_ui_master_tokens_browser.py`.

**WP2-Navigationsvertrag, umgesetzt am 2026-09-20:** `_area_tabs.html` bleibt das einzige serverseitige Navigationsmodell und ordnet Routen ausschliesslich über explizite Endpoint-Mengen zu; präfixbasierte Zuordnung ist unzulässig. Das Modell exportiert `area_nav.areas`, `area_nav.selected.area`, `area_nav.selected.item` und `area_nav.href`. `_workflow_sidebar.html` rendert daraus vier `.admin-nav-area`-Oberpunkte und nur unter dem aktiven Oberpunkt eine eingerückte `.admin-nav-subitems`-Liste. Der aktive Unterpunkt trägt `aria-current="page"`; Desktop, Offcanvas und No-JS verwenden dasselbe Makro und dieselben Capability-Prädikate. «Menüs & Bausteine» enthält Menüs, Bausteine, Zutaten, Rezepte, Kochbücher, Gerichtvorlagen, Einkaufslisten, Bestellung, Lager und Kalkulation. «Einstellungen» enthält Bereiche & Öffnungszeiten, Erscheinungsbild, Darstellung, Daten importieren, Schnittstellen und Benutzer & Zugriff. «Zutaten» behält die bestehenden Grundlagen-Endpunkte und URLs. Nachweis: `test_admin_shell_ui.py`, `test_ui_master_shell_browser.py`, `test_recipe_navigation_browser.py`, `test_calendar_nav.py`, `test_branding_header_browser.py`.

**WP3-Statusbar-Makrovertrag, umgesetzt am 2026-09-20:** `page_header(title, description=none, breadcrumbs=none, actions=none, pretitle=none, status_items=[])` bleibt für alle bisherigen Aufrufe kompatibel. Jeder Eintrag ist ein Mapping mit `label`, `value`, optional `detail` und optional `variant`; zugelassen sind `neutral`, `success`, `warning` und `danger`, unbekannte Varianten fallen auf `neutral` zurück. Das Makro rendert höchstens fünf nichtleere, beschriftete Werte als semantische Liste `dl.admin-statusbar` mit `dt.admin-statusbar-label` und `dd.admin-statusbar-value`. `0` ist ein echter Wert; `none`, leere Zeichenketten und unbeschriftete Werte werden weggelassen. Varianten nutzen `.admin-statusbar-item--neutral|success|warning|danger`; sichtbare Labels und Werte tragen die Bedeutung, nie Farbe allein. Nachweis: `test_ui_master_components_browser.py` und `test_admin_statusbar_browser.py`, inklusive Browser-Reflow bei 360 px ohne horizontalen Dokument-Overflow.

**Responsive:** Unterhalb der bestehenden Sidebar-Schwelle wird die Navigation über „Menü“ geöffnet (als Drawer/kompakte Navigation zulässig). Ohne JavaScript bleibt die Mobilnavigation in einem nativen, standardmässig geschlossenen `details.admin-nojs-nav` mit 48 px hoher, fokussierbarer Summary «Menü»; Links und Unterpunkte werden erst nach dem Öffnen angezeigt. Sie darf das Formular nicht auf eine schmale Restfläche drücken. Für Login und öffentliche Ausgaben dieses Muster nicht blind erzwingen.

#### M02 — Rezepteditor: kompakter Ausgangszustand

Desktop; vier Beispielzutaten, zwei Schritte. Der Seitenkopf enthält ein eindeutiges Objekt, nicht mehrfach denselben Titel.

```text
+----------------------------------------------------------------------------------------------------------+
| REZEPT BEARBEITEN / Apfelmus                                         [<] Zur Rezeptliste                 |
| Entwurf  |  Beispielzustand: noch keine neuen Aenderungen                                                |
| [Rezept]  [Zutaten (4)]  [Zubereitung (2)]  [Weitere Angaben]                                            |
| [!] KI-Vorschlag: Rezept, Ausbeute und Allergene noch nicht fachlich geprueft.                           |
+----------------------------------------------------------------------------------------------------------+
| Name         [Apfelmus                                                                               ]   |
| Beschreibung [Optional                                                                               ]   |
| Ausbeute [1600] [Gramm v]     Vorbereitung [    ] Min.      Kochzeit [    ] Min.                         |
+----------------------------------------------------------------------------------------------------------+
| ZUTATEN                                                                         [+] Zutat hinzufuegen    |
| Zutat                    Menge          Einheit             Zusatzangaben / Aktionen                     |
| Aepfel                   [1800       ]  [Gramm        v]     [>] Details   [...] Aktionen                |
| Wasser                   [100        ]  [Milliliter   v]     [>] Details   [...] Aktionen                |
| Zucker                   [60         ]  [Gramm        v]     [>] Details   [...] Aktionen                |
| Zimt                     [           ]  [Auswaehlen   v]     [>] Details   [...] Aktionen                |
+----------------------------------------------------------------------------------------------------------+
| ZUBEREITUNG                                                                   [+] Schritt hinzufuegen    |
| 1  Aepfel vorbereiten ...                                   [E] Bearbeiten  [...] Aktionen               |
| 2  Fertige Menge messen und Angaben pruefen ...              [E] Bearbeiten  [...] Aktionen              |
+----------------------------------------------------------------------------------------------------------+
| [>] Kennzeichnungen und Bilder  |  [>] Quelle und technische Angaben                                     |
+----------------------------------------------------------------------------------------------------------+
| Speichern uebernimmt die Eingaben.                               [Abbrechen]  [S] Rezept speichern       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Mengen und Einheiten sind unmittelbar bearbeitbar. Nicht erst jede Zutat öffnen. Ausbeute, Vorbereitung und Kochzeit stehen bei ausreichendem Platz in einer gemeinsamen Feldgruppe. Namen und Angaben dürfen umbrechen.

**Keine Scheinlösung:** Nicht die gesamte Zutatenliste hinter einem Akkordeon verstecken. Nicht alle Zutaten gleichzeitig in grossen Detailkarten darstellen. Die Warnung bleibt sichtbar, auch wenn technische Quellenangaben geschlossen sind. Der Standardzustand darf bei echten Pflichtfehlern automatisch grösser werden.

#### M03 — Rezeptzutat: nur die benötigten Details öffnen

Dieselbe Liste wie M02; die erste Zutat ist geöffnet. Andere Zutaten bleiben direkt erreichbar.

```text
+----------------------------------------------------------------------------------------------------------+
| ZUTATEN                                                                         [+] Zutat hinzufuegen    |
| Aepfel         [1800] [Gramm v]                         [v] Details schliessen  [...] Aktionen           |
+----------------------------------------------------------------------------------------------------------+
|   Zutat aus Liste       [Aepfel                                                                     v]   |
|   Bezeichnung im Rezept [Aepfel                                                                      ]   |
|   Gruppe                [Optional                         ]                                              |
|   Notiz                 [Optional                                                                  ]     |
|   [>] Quelle und technische Angaben dieser Zutat                                                         |
|   Diese Angaben werden zusammen mit dem Rezept gespeichert.                                              |
+----------------------------------------------------------------------------------------------------------+
| Wasser         [100 ] [Milliliter v]                    [>] Details            [...] Aktionen            |
| Zucker         [60  ] [Gramm v]                         [>] Details            [...] Aktionen            |
| Zimt           [    ] [Auswaehlen v]                    [>] Details            [...] Aktionen            |
+----------------------------------------------------------------------------------------------------------+
| Aenderungen noch nicht gespeichert                               [Abbrechen]  [S] Rezept speichern       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Die beiden Werte „Zutat aus Liste“ und „Bezeichnung im Rezept“ behalten ihre tatsächliche unterschiedliche Bedeutung. Nicht als Entweder-oder behandeln, solange der Bestand beide benötigt. Menge und Einheit werden nicht als zweite gleichnamige Eingaben im Detailbereich dupliziert.

**Interaktion:** Schliessen behält alle Eingaben. Mehrere Details dürfen zum Vergleichen offen bleiben. Eine gefüllte Notiz oder Gruppe wird nach dem Schliessen als kurze Zusatzinformation erkennbar. Neue und fehlerhafte Zeilen öffnen sich passend; keine eigenständige Speicherung durch „Details schliessen“.

#### M04 — Zubereitung: Kurzfassung und gezielte Bearbeitung

Ein Schritt ist geöffnet. Vollständige Anleitung, Zeit und Bildzuordnung bleiben erhalten.

```text
+----------------------------------------------------------------------------------------------------------+
| ZUBEREITUNG                                                                   [+] Schritt hinzufuegen    |
| 1  Aepfel vorbereiten ...                                  [E] Bearbeiten   [...] Aktionen               |
| 2  Fertige Menge messen ...                         [v] Bearbeitung schliessen   [...] Aktionen          |
+----------------------------------------------------------------------------------------------------------+
|   Anleitung                                                                                              |
|   [Fertige Ausbeute in der angegebenen Einheit messen. Vorschlagsmenge vor Kuechenfreigabe pruefen.   ]  |
|   [                                                                                                 ]    |
|   Dauer [    ] Minuten            Bild zum Schritt [Kein Bild ausgewaehlt                          v]    |
|   Bildzuordnung und Dauer sind nur dann Pflicht, wenn der bestehende Vertrag dies verlangt.              |
+----------------------------------------------------------------------------------------------------------+
| Aenderungen noch nicht gespeichert                               [Abbrechen]  [S] Rezept speichern       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Die Kurzfassung unterstützt Orientierung; die komplette Anleitung bleibt im Editor sichtbar und vergrösserbar. Keine Zeichen abschneiden und als vollständige Anweisung ausgeben. Eine fehlende Dauer bedeutet nicht automatisch null Minuten.

**Speichern:** Die Zeile ist Teil desselben Rezeptformulars. Keine zweite unabhängige Schritt-Speicherung einführen. Eine Bildreferenz bleibt auch erhalten, wenn ihre Detailsteuerung geschlossen oder ein Bildname derzeit nicht auflösbar ist.

#### M05 — Zeilenaktionen: kompakt, beschriftet und kontextbezogen

Geöffnetes Aktionsmenü einer Zutat. Nur im Bestand vorhandene Operationen anbieten.

```text
+----------------------------------------------------------------------------------------------------------+
| Wasser             [100] [Milliliter v]                  [>] Details    [...] Aktionen                   |
|                                                                          +--------------------------+    |
|                                                                          | [+] Davor einfuegen      |    |
|                                                                          | [^] Nach oben            |    |
|                                                                          | [v] Nach unten           |    |
|                                                                          | [X] Aus Rezept entfernen |    |
|                                                                          +--------------------------+    |
| Aktionen betreffen diese Rezeptzeile, nicht die Zutat im zentralen Katalog.                              |
| Reihenfolge und Eingaben bleiben beim bestehenden Formularweg erhalten.                                  |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Kurze sichtbare Wörter; zugängliche Namen bei Bedarf um den Kontext ergänzen, beispielsweise „Wasser nach oben verschieben“. Pfeile passen zur vertikalen Reihenfolge. Am Anfang/Ende unmögliche Bewegungen korrekt deaktivieren oder weglassen. Keine erfundene Funktion „danach einfügen“, wenn der bestehende Weg sie nicht unterstützt.

**Vertrag:** Die zuvor untersuchten Rezeptaktionen verwendeten eigene Submit-/`formaction`-Wege. Aktuellen Stand prüfen und vorhandene `formnovalidate`-Semantik für Strukturaktionen erhalten. Nicht durch neue pauschale Validierungsumgehungen oder eine zweite clientseitige Sortierlogik ersetzen. Nach der Aktion zum betroffenen Objekt zurückkehren.

#### M06 — Rezepteditor auf dem Smartphone

Schmaler Viewport: Name, Menge, Einheit und beschriftete Aktionen bleiben nutzbar. Keine verkleinerte Desktoptabelle.

```text
+------------------------------------------+
| [Menue]             [<] Rezeptliste      |
| Apfelmus bearbeiten                      |
| [!] KI-Entwurf, noch ungeprueft.         |
| [Rezept] [Zutaten] [Zubereitung]         |
+------------------------------------------+
| ZUTATEN (4)                              |
| Aepfel                                   |
| Menge           Einheit                  |
| [1800        ]  [Gramm       v]          |
| [>] Details     [...] Aktionen           |
+------------------------------------------+
| Wasser                                   |
| Menge           Einheit                  |
| [100         ]  [Milliliter  v]          |
| [>] Details     [...] Aktionen           |
+------------------------------------------+
| Zucker                                   |
| Menge           Einheit                  |
| [60          ]  [Gramm       v]          |
| [>] Details     [...] Aktionen           |
+------------------------------------------+
| Weitere Zutaten folgen im Fluss.         |
| [+] Zutat hinzufuegen                    |
+------------------------------------------+
| Aenderungen nicht gespeichert            |
| [S] Rezept speichern                     |
| [Abbrechen]                              |
+------------------------------------------+
```

**Pflicht:** Umordnen statt schrumpfen. Keine horizontal scrollende Gesamtdokumentseite. Abschnittslinks dürfen umbrechen; keine abgeschnittene Tabreihe. Menge und Einheit bleiben sichtbar zugeordnet, auch ohne Tabellenkopf.

**Mobile Leiste:** Bei eingeblendeter Tastatur oder geringer Höhe darf die Speicherleiste in den Dokumentfluss wechseln. Sie verdeckt weder Felder noch Fehler oder Fokus. Die Skizze verspricht nicht, vier Zutaten samt kompletter Rezeptbasis auf 390 × 844 gleichzeitig zu zeigen.

#### M07 — Menüübersicht: Text und Handlung vor Bildern

Geplante Menüeinträge aus verschiedenen Wochen; kein neu erfundener Rezeptkatalog.

```text
+----------------------------------------------------------------------------------------------------------+
| MENUES & BAUSTEINE / Gespeicherte Menues                                                                 |
| [Menues] [Bausteine] [Zutaten] [Rezepte] [Kochbuecher] [Weitere vorhandene Bereiche]                     |
| [Cafeteria] [Patienten]                                                                                  |
| Menue oder Baustein suchen [                                                 ]  [?] Suchen               |
| Ansicht [Liste] [Karten]                                                                                 |
+----------------------------------------------------------------------------------------------------------+
| 11.09.2026 / Mittag / Menue 1                                                                            |
| Gebratenes Zanderfilet  |  Salzkartoffeln, Rahmspinat                    [E] Im Wochenplan oeffnen       |
| Gespeicherter Pruefstand: Geprueft*  |  [!] Allergenangaben nicht erfasst   [>] Hinweise                 |
+----------------------------------------------------------------------------------------------------------+
| 11.09.2026 / Mittag / Vegetarisch                                                                        |
| Falafel-Teller  |  Hummus, Ofengemuese                                 [E] Im Wochenplan oeffnen         |
| Gespeicherter Pruefstand: Geprueft*  |  [!] Allergenangaben nicht erfasst   [>] Hinweise                 |
+----------------------------------------------------------------------------------------------------------+
| * Den belegten Geltungsbereich der bestehenden Pruefung eindeutig beschriften.                           |
| Weitere Treffer folgen kompakt. Seitennavigation nur bei tatsaechlich mehreren Seiten.                   |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Öffnen führt zum tatsächlichen geplanten Eintrag, nicht unbeabsichtigt zu einem globalen Rezept. Sichtbarer Zeitraum, Menüart und relevante Warnung bleiben am Objekt. Lange interne Hinweise sind erreichbar, aber nicht der Hauptinhalt jeder Karte.

**Status:** „Geprüft“ darf nur den verifizierten bestehenden Prüfumfang wiedergeben. Der Stern ist ein Hinweis an den Agenten, keine dauerhaft nötige Fussnotenlösung im Produkt. Bedeutung am Code klären; keine Statusdaten ändern. Vorhandene Bilder nicht löschen, aber aus der Standardübersicht zurücknehmen. KI-Kennzeichnung in bestehenden Bildansichten erhalten.

#### M08 — Bausteinliste mit gezielt erweiterten Filtern

Liste mit wenigen Standardfiltern; zusätzliche Filter sind ausdrücklich geöffnet.

```text
+----------------------------------------------------------------------------------------------------------+
| BAUSTEINE                                                                    [+] Baustein hinzufuegen    |
| Suche [                                                   ]   [?] Suchen                                 |
| Kategorie [Alle v]     Status [Aktiv v]     [v] Weitere Filter                                           |
+----------------------------------------------------------------------------------------------------------+
| Allergen [Milch v]     Praesenz [Enthaelt v]     Herkunft [Alle Laender v]                               |
| [Filter anwenden]     [Filter zuruecksetzen]                                                             |
+----------------------------------------------------------------------------------------------------------+
| Aktive Filter: Aktiv | enthaelt Milch. Zusatzfilter bleiben auch eingeklappt erkennbar.                  |
| Name                 Kategorie       Angaben                         Verwendung          Aktion          |
| Kartoffelstock       Beilage         Enthaelt Milch                  2 Menues             [E] Bearbeiten |
| Weitere passende Treffer folgen; keine erfundene Gesamtzahl.                                             |
+----------------------------------------------------------------------------------------------------------+
| Eingeklappte Zusatzfilter duerfen nicht zu einer unerklaerlichen leeren Liste fuehren.                   |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Suche und höchstens zwei häufige Filter in der Standardansicht. Weitere vorhandene Filter bleiben erreichbar; aktuelle Auswahl und Reset sichtbar. Nutze echte Ländernamen, sofern die bestehende Zuordnung verfügbar ist, nicht ausschliesslich Flaggen oder Codes.

**Funktion:** Bestehende Suchparameter und deren Kombination erhalten. Kein Browserfilter nur über die aktuelle Seite einer serverseitig paginierten Liste. In einer leeren Ergebnismenge unterscheiden, ob Filter, Datenbestand, Rechte oder ein Ladefehler die Ursache sind; siehe M20.

#### M09 — Wochenübersicht: auswählen zuerst, anlegen bei Bedarf

Normalansicht mit geschlossenem Erstellformular. Dieses Muster gilt analog für Listen mit selten genutzter Anlagefunktion.

```text
+----------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Wochenuebersicht                                                 [+] Neue Woche anlegen     |
| Bereich [Cafeteria v]                                                                                    |
+----------------------------------------------------------------------------------------------------------+
| Zeitraum                           Kalenderwoche     Vorhandener Stand          Aktion                   |
| 7.-13. September 2026              KW 37             Veroeffentlicht           [E] Woche oeffnen         |
|                                                                                [...] Aktionen            |
| 31. August-6. September 2026        KW 36             Noch zu pruefen           [E] Woche oeffnen        |
|                                                                                [...] Aktionen            |
+----------------------------------------------------------------------------------------------------------+
| Die Anlage wird erst ueber den Button oben geoeffnet; keine zweite staendige Buttonreihe.                |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Nur einen sichtbaren Einstieg „Neue Woche anlegen“ im Seitenkopf platzieren. Bei Bedarf den bestehenden Formularbereich unterhalb der Werkzeugleiste öffnen: Wochenbeginn, Zusatzname, Hinweis und vorhandene Anlageaktion. Die letzte Zeile der Skizze ist eine Anmerkung, kein zusätzlicher Produkttext. Bei Formularfehlern bleibt der Bereich mit Eingaben offen.

**Semantik:** ISO-Woche und tatsächliche Cafeteria-Ausgabetage unterscheiden. Datumsbereich aus dem geplanten Zeitraum; Freititel ist keine verlässliche Datumsquelle. Kopieraktionen erklären Quelle, Ziel und tatsächliche Überschreibwirkung anhand des Bestands. Keine Zusicherungen erfinden.

#### M10 — Cafeteriaplan: Arbeitsraster statt Verwaltungsblöcke

Breiter Desktop mit ausreichender realer Spaltenbreite; fünf Tage und die zwei vorhandenen Menüarten.

```text
+----------------------------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Cafeteria  |  7.-11. September 2026  |  KW 37                                                                 |
| [Cafeteria] [Patienten] [Wochenuebersicht]                                                                                 |
| [<] Vorherige Woche   [Woche auswaehlen]   [>] Naechste Woche                                                              |
| Veroeffentlichungsstand: [vorhandener Stand]    Pruefung: [vorhandener Befund]                                             |
| [O] Vorschau   [...] Weitere Aktionen                        [!] Offene Angaben pruefen                                    |
+----------------------------------------------------------------------------------------------------------------------------+
+------------------------+------------------------+------------------------+------------------------+------------------------+
| Montag 7.9.            | Dienstag 8.9.          | Mittwoch 9.9.          | Donnerstag 10.9.       | Freitag 11.9.          |
+------------------------+------------------------+------------------------+------------------------+------------------------+
| MENUE 1                | MENUE 1                | MENUE 1                | MENUE 1                | MENUE 1                |
| Pouletbrust an         | Hackbraten             | Rindsgeschnetzeltes    | Schweinsragout         | Gebratenes             |
| Kraeutersauce          | an Rosmarinjus         |                        | Tessiner Art           | Zanderfilet            |
| Kartoffelstock         | Kartoffelgratin        | Nudeln                 | Polenta, Bohnen        | Salzkartoffeln         |
| [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   |
| Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  |
| Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     |
| [>] Hinweise           | [>] Hinweise           | [>] Hinweise           | [>] Hinweise           | [>] Hinweise           |
| [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         |
+------------------------+------------------------+------------------------+------------------------+------------------------+
| VEGETARISCH            | VEGETARISCH            | VEGETARISCH            | VEGETARISCH            | VEGETARISCH            |
| Spinat-Ricotta-        | Gemuese-Curry          | Risotto                | Gemuesegratin          | Falafel-Teller         |
| Ravioli                |                        |                        |                        |                        |
| Tomatensauce           | Reis                   | Gemuese                | Salat                  | Hummus, Gemuese        |
| [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   |
| Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  |
| Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     |
| [>] Hinweise           | [>] Hinweise           | [>] Hinweise           | [>] Hinweise           | [>] Hinweise           |
| [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         |
+------------------------+------------------------+------------------------+------------------------+------------------------+
+----------------------------------------------------------------------------------------------------------------------------+
| Alle Preise sind Beispieldaten. Beide Zielgruppen bleiben bei jedem Menue eindeutig zugeordnet.                            |
| [>] Wochenangaben aendern  |  Tages-/Ausgabeangaben am jeweiligen Tag gezielt oeffnen.                                     |
+----------------------------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Gerichte unmittelbar unter der kompakten Wochensteuerung. Konkrete vorhandene Warnungen und beide Cafeteriapreise sichtbar halten. Nur die ausführlichen Zusatzhinweise liegen hinter „Hinweise“. Keine zusätzlichen Menüarten aus früheren Bildern übernehmen.

**Responsive:** Wenn fünf ausreichend lesbare Spalten nicht passen, in chronologische Tagesabschnitte wechseln. Nicht Schrift verkleinern oder vollständige Namen abschneiden. Beide Preise müssen dem richtigen Menü und der richtigen Zielgruppe zugeordnet bleiben; fehlende Werte nicht raten.

#### M11 — Patientenplan: kompakte Tagesgruppen mit Mittag und Abend

Patienten bleiben ein Sieben-Tage-Plan. Darstellung der Mahlzeiten nebeneinander nur bei genügend Platz.

```text
+----------------------------------------------------------------------------------------------------------+
| PATIENTENPLAN / 7.-13. September 2026 / KW 37                                                            |
| [Cafeteria] [Patienten] [Wochenuebersicht]                                                               |
| Veroeffentlicht  |  [!] Allergenangaben fehlen. Gespeicherten Pruefstand separat erklaeren.              |
| [O] Vorschau  [...] Weitere Aktionen                        [!] Offene Angaben pruefen                   |
+----------------------------------------------------------------------------------------------------------+
| MONTAG, 7. SEPTEMBER                                                                                     |
| MITTAG                                              ABEND                                                |
| Geoeffnet | Zeiten nicht erfasst                     Geoeffnet | Zeiten nicht erfasst                    |
| [E] Ausgabeangaben aendern                           [E] Ausgabeangaben aendern                          |
|                                                                                                          |
| Menue 1: Pouletgeschnetzeltes                        Menue 1: Schinken-Kaese-Toast                       |
| Reis, Zucchetti                                     Tomatensalat                                         |
| [!] Allergene nicht erfasst                         [!] Allergene nicht erfasst                          |
| [E] Bearbeiten  [>] Hinweise                         [E] Bearbeiten  [>] Hinweise                        |
|                                                                                                          |
| Vegetarisch: Gemuesegeschnetzeltes                   Vegetarisch: Gemuese-Toast                          |
| Reis, Zucchetti                                     Tomatensalat                                         |
| [!] Allergene nicht erfasst                         [!] Allergene nicht erfasst                          |
| [E] Bearbeiten  [>] Hinweise                         [E] Bearbeiten  [>] Hinweise                        |
+----------------------------------------------------------------------------------------------------------+
| DIENSTAG bis SONNTAG folgen mit demselben Tagesmuster.                                                   |
| Alle 7 Tage x 2 Mahlzeiten x 2 vorhandenen Menuearten bleiben erreichbar. Keine Preise.                  |
| [>] Wochenangaben aendern                                                                                |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Die nächsten Tage folgen tatsächlich als Tagesgruppen; die Zusammenfassungszeile ist nur eine Verkürzung der Zeichnung. Weder Wochenende noch Abendangebot weglassen. Gefüllte Hinweise kurz erkennbar machen. Standardmässig nicht die grossen Zeit-/Betriebsformulare vor jedes Menü stellen.

#### M11b — Gemeinsame Gänge (Suppe, Dessert)

Suppe und Dessert sind eigenständige Planungszuweisungen pro Datum, Profil und Mahlzeit, nicht Beilagen eines Hauptgerichts. In der Wochenansicht steht die gemeinsame Suppe vor den Hauptmenüs, das gemeinsame Dessert danach; einmal je Ausgabe, nicht als zusätzliche grosse Menükarte. Menüabweichungen werden gezielt geöffnet und an der betroffenen Variante bezeichnet. „Noch nicht geplant“ und „nicht angeboten“ bleiben unterscheidbar. Fehlende Allergene werden nie zu einer positiven Aussage umgedeutet; „nicht angeboten“ trägt keine Kennzeichnung. Die globale Infoleiste zählt gemeinsame Gänge einmal, nicht je Menüvariante. Der Küchenkalender zeigt Gänge kompakt unter der Ausgabe, nicht als weitere Hauptgerichte.

**Admin-Woche:** Der Gang-Editor ist standardmässig zugeklappt, Bedienelemente sind mindestens 48 px hoch. Die Tab-Reihenfolge Veröffentlichen → Vorschau → Prüfen bleibt. Menükarten-Bilder behalten ihr Format (die 64–96-px-Regel gilt nur für Gang-Vorschaubilder).

**Signage und öffentliche Seiten:** Signage-Gänge stehen im vorhandenen Kopfband der Mahlzeit (Patienten-Tag `header.meal-label`, Patienten-Woche `.meal-name`, Cafeteria-Tag `.signage-kicker`), nie als zusätzliche Zeile/Karte; Schrift mindestens 18 px bei 1920 px Breite, skalierend. Bei langen Gangtiteln bleiben Allergen-/Label-Symbole immer vollständig sichtbar (`flex-shrink: 0`), der Titel wird sichtbar mit Ellipse gekürzt. Auf Wochenboards tragen Gänge nur Symbole ohne Allergen-Langtext (wie reguläre Optionen dort). Öffentliche Seiten zeigen eine kompakte Gangzeile mit Token-Abständen, Allergen-/Label-Kennzeichnung über dasselbe Makro wie reguläre Optionen; das Höhenbudget der Patientenwoche bleibt gewahrt.

**Status und Wirkung:** Eine Veröffentlichung sagt nichts über fehlende Angaben oder ungespeicherte Änderungen aus. Den vorhandenen Prüfstand separat erklären. „Ausgabeangaben ändern“ öffnet ausschliesslich das bestehende Formular und dessen eigene Speicheraktion. Kein globales „Alles speichern“, wenn es keine gemeinsame Transaktion gibt.

##### Modul Gänge (Suppe/Dessert) im Wochenplan (2026-09-20)

Nicht geplante Gänge erhalten eine kompakte «Suppe planen»-/«Dessert planen»-Aktion; bestehende Gänge eine beschriftete Aktion «Bearbeiten». Ziele sind die vorhandenen Gangfelder im atomaren Ausgabeformular. Statuswerte `unplanned`, `planned`, `not_offered` und `inherit` bleiben unverändert. Die Rezeptauswahl liegt in einem nativen Detailbereich, offen bei vorhandener Auswahl oder Formularfehler. Suche und Abweichungen stehen nachrangig; «Weitere Optionen» öffnet bei Abweichungen oder Fehlern automatisch. Keine Auswahl wird beim Einklappen deaktiviert, zurückgesetzt oder ausgelassen. Ein Formularfuss enthält genau eine Aktion «Speichern».

Die vorhandene globale Gangwarnung bleibt Aufgabe der Wochenplan-Statusbar (WP21): `course_issues.affected_assignments` und `course_issues.missing_allergens`, Ziel `#course-issues`. Kein zweiter Seitenkopf im wiederholten Partial. Rezept-Suchfelder erhalten pro Ausgabe eindeutige IDs. CSP, No-JS-Bedienbarkeit, 48-px-Ziele und alle POST-/CAS-Felder bleiben erhalten. Public-/Signage-Ausgaben bleiben unverändert. Nachweise: `test_course_browser.py`, `test_course_week_html.py`, `test_course_html_captures.py`.

#### M12 — Menüeditor: breite Hauptarbeit, schmalerer Prüfkontext

Volle Seitenbreite mit gemeinsamem Zwei-Spalten-Layout. Auf schmalen Geräten stehen die Bereiche untereinander.

```text
+-------------------------------------------------------------------+   +----------------------------------+
| MENUE BEARBEITEN / Dienstag 8. September                          |   | PRUEFUNG                         |
| Patienten / Mittag / Menue 1                                      |   | Zuletzt gespeicherter Stand      |
+-------------------------------------------------------------------+   +----------------------------------+
| Titel [Hackbraten an Rosmarinjus                               ]  |   | [!] Allergene nicht erfasst      |
| Beschreibung [Optional                                       ]    |   | [!] Herkunft nicht erfasst       |
+-------------------------------------------------------------------+   | Kennzeichnungen: nicht erfasst   |
| BAUSTEINE                           [+] Baustein hinzufuegen      |   |                                  |
| Kartoffelgratin              [E] Aendern  [...] Aktionen          |   | Neue Eingaben zuerst speichern.  |
| Broccoli                    [E] Aendern  [...] Aktionen           |   |                                  |
+-------------------------------------------------------------------+   | [Pruefung oeffnen]               |
| [>] Ausfuehrlicher Pruefhinweis vorhanden                         |   +----------------------------------+
| [E] Allergene bearbeiten   [E] Herkunft bearbeiten                |   | Bestaetigung nur nach dem        |
| Vorhandene Felder unten oder am Zielabschnitt bearbeiten.         |   | vorhandenen Pruefablauf.         |
+-------------------------------------------------------------------+   | Keine neue Freigabelogik.        |
| Nicht gespeichert                  [S] Menue speichern            |   +----------------------------------+
+-------------------------------------------------------------------+
```

**Pflicht:** Hauptformular deutlich breiter als der Prüfkontext; auf Desktop beispielsweise ungefähr zwei Drittel zu einem Drittel, an reale Inhalte angepasst. Keine schmale gesamte Mittelsäule. Prüfzusammenfassung enthält direkte Links zu bestehenden Feldern, soweit möglich, nicht nur passive Meldungen.

**Geltungsbereich:** Diese Skizze zeigt Patienten, deshalb ohne Preisfelder. In der Cafeteria bleiben beide vorhandenen Preisgruppen als kompakte Feldgruppe erhalten. Menübausteine dürfen die bestehende klare Auswahlart Katalog/Freitext erhalten; Rezeptzutaten aus M03 sind fachlich etwas anderes. Eine existierende seitliche Bearbeitung verwendet dasselbe Formularmuster; keine neue Panel-API bauen.

#### M13 — Baustein bearbeiten: eindeutige Allergenfelder

Editormuster für einen zentralen Baustein. Beispielwerte sind Eingaben, keine fachliche Deklaration.

```text
+----------------------------------------------------------------------------------------------------------+
| BAUSTEIN BEARBEITEN / Kartoffelstock                                       [<] Zur Bausteinliste         |
| Wird in 2 Menues verwendet  |  Aktiv                                                                     |
+----------------------------------------------------------------------------------------------------------+
| Name [Kartoffelstock                     ]  Kategorie [Beilage v]  Herkunft [Nicht erfasst v]            |
| Kennzeichnungen: [ ] Vegan   [ ] Vegetarisch   [ ] Glutenfrei   [ ] Laktosefrei                          |
+----------------------------------------------------------------------------------------------------------+
| ALLERGENE                                                                                                |
| [x] Milch                     Praesenz [Enthaelt      v]                                                 |
| [x] Glutenhaltiges Getreide    Praesenz [Kann enthalten v]                                               |
| [ ] Eier                      Nicht ausgewaehlt                                                          |
| [ ] Fisch                     Nicht ausgewaehlt                                                          |
| [>] Weitere Allergene anzeigen                                                                           |
| [!] Nicht ausgewaehlt bedeutet nicht: allergenfrei bestaetigt.                                           |
+----------------------------------------------------------------------------------------------------------+
| [>] Verwendung und Wirkung zentraler Aenderungen                                                         |
| [...] Weitere Aktionen, einschliesslich vorhandener Archivierung                                         |
+----------------------------------------------------------------------------------------------------------+
| Aenderungen noch nicht gespeichert                            [Abbrechen]  [S] Baustein speichern        |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Keine scheinbar aktive „enthält“-Auswahl neben einem nicht gewählten Allergen. Nicht gewählte zusätzliche Allergene bleiben erreichbar; ausgewählte oder fehlerhafte Angaben dürfen nicht verdeckt werden. Kennzeichnungen nicht automatisch aus Namen oder Allergenfeldern ableiten.

**Vertrag:** Vor dem Deaktivieren oder Ausblenden von Controls die POST-Semantik prüfen. Nur eine Darstellung ändern, keine Werte verlieren oder hidden/disabled-Verhalten neu erfinden. Der Verwendungszähler ist nur bei belegten Daten zulässig. Die Wirkung zentraler Änderungen auf bestehende Menüs anhand des Codes erklären; nicht als garantiert unveränderliche Vergangenheit ausgeben.

#### M14 — Drucken und Vorschau: Arbeitsauftrag von Layoutverwaltung trennen

Beispiel mit bewusst unterschiedlichen Zeiträumen für gewählte gespeicherte Woche und veröffentlichten Stand.

```text
+----------------------------------------------------------------------------------------------------------+
| VORSCHAU & BILDSCHIRME / Wochenplan drucken                                                              |
| [Wochenplan drucken] [Bildschirme] [Drucklayouts] [Weitere vorhandene Ausgaben]                          |
+----------------------------------------------------------------------------------------------------------+
| Bereich [Cafeteria v]      Gespeicherte Woche [7.-13. September 2026 / KW 37 v]                          |
| Gewaehlter Stand: gespeicherte Woche 37, nicht automatisch der veroeffentlichte Plan.                    |
| [P] PDF der gewaehlten Woche oeffnen                                                                     |
+----------------------------------------------------------------------------------------------------------+
| [v] Aktuell veroeffentlichten Plan drucken                                                               |
|     Beispiel: anderer Stand, 31. August-6. September 2026 / KW 36.                                       |
|     [P] Veroeffentlichten Plan drucken                                                                   |
+----------------------------------------------------------------------------------------------------------+
| [>] Drucklayout aendern       [>] Fruehere Versionen       [>] Inhalte bearbeiten                        |
| Rezeptdruck bleibt ein eigener bestehender Unterbereich.                                                 |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Die prominenteste Aktion öffnet genau die gewählte gespeicherte Woche. Der veröffentlichte Plan ist eine andere vorhandene Aktion mit eigenem Datenstand; Datum nur nennen, wenn bekannt. Vorhandene Wochenauswahlmechanik weiterverwenden, keinen neuen universellen Pickervertrag erfinden.

**Layoutverwaltung:** Für normales Drucken keine Versionsverwaltung durchlaufen. Entwurf ansehen und aktivieren bleiben getrennt. Keine neue PDF-Engine oder Vorschau-API. Patienten- und Cafeteriaausgaben behalten ihre eigene Preis- und Mahlzeitenlogik.

#### M15 — Einstellungen: kompakte Zusammenfassung, Bearbeitung bei Bedarf

Generisches Muster für vorhandene Einstellungen; keine neuen Einstelloptionen daraus ableiten.

```text
+----------------------------------------------------------------------------------------------------------+
| EINSTELLUNGEN                                                                                            |
| [Bereiche & Zeiten] [Erscheinungsbild] [Datenimport] [Benutzer] [Schnittstellen]                         |
+----------------------------------------------------------------------------------------------------------+
| BEREICHE UND AUSGABEZEITEN                                                                               |
| Cafeteria / Mittag         Vorhandener Zustand und vorhandene Zeiten              [E] Bearbeiten         |
| Patienten / Mittag         Vorhandener Zustand und vorhandene Zeiten              [E] Bearbeiten         |
| Patienten / Abend          Vorhandener Zustand und vorhandene Zeiten              [E] Bearbeiten         |
+----------------------------------------------------------------------------------------------------------+
| Patienten / Abend bearbeiten                                       [v] Bearbeitung schliessen            |
| Betrieb [Offen v]     Beginn [--:--]    Ende [--:--]                                                     |
| Hinweis [                                                                                           ]    |
| [!] Leere Zeiten bleiben leere Zeiten; keine erfundenen Standardwerte.                                   |
| [Abbrechen]                                                        [S] Ausgabeangaben speichern          |
+----------------------------------------------------------------------------------------------------------+
| Weitere Einstellungen folgen als kurze Zusammenfassung statt staendig offener Formularwand.              |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Bestehende Einstellbereiche gruppiert zeigen. Ein Zustand kann „Nicht erfasst“ sein; keine scheinbar konfigurierten Werte aus dem Beispiel übernehmen. Gefährliche oder weitreichende Einstellungen mit konkreter Wirkung erklären.

**Speichern:** Pro bestehendem Einstellformular eine passende Speicherhandlung; nicht unabhängige Endpoints in eine neue globale Transaktion zusammenlegen. Ein geöffneter Bereich mit Fehler bleibt offen. Sensible Schnittstellenwerte oder Schlüssel nicht in Zusammenfassungen und Screenshots offenlegen.

#### M16 — Erscheinungsbild: gespeicherten Entwurf eindeutig kennzeichnen

Einstellungen links, dazugehörige Vorschau rechts. Keine nur behauptete Live-Aktualisierung.

```text
+-------------------------------------------------------------------+   +----------------------------------+
| ERSCHEINUNGSBILD / Entwurf bearbeiten                             |   | VORSCHAU                         |
+-------------------------------------------------------------------+   | Gespeicherter Entwurf            |
| Name [Suedhang Standard - Entwurf                              ]  |   +----------------------------------+
| Logo [Vorhandenes Logo v]      [Datei auswaehlen]                 |   | Original-Logo                    |
| Primaerfarbe [Farbwert]       Hintergrund [Farbwert]              |   | Menue mit realistischem Namen    |
| Schrift [Vorhandene Auswahl v]                                    |   | Vorhandene Beispielinhalte       |
+-------------------------------------------------------------------+   |                                  |
| [S] Entwurf speichern und Vorschau anzeigen                       |   | Noch nicht aktiviert.            |
|                                                                   |   | [Entwurf aktivieren]             |
| [>] Fruehere Versionen                                            |   | Nur vorhandene Aktivierung.      |
| [>] Technische Farbwerte und weitere Angaben                      |   +----------------------------------+
+-------------------------------------------------------------------+
```

**Pflicht:** „Vorschau“ benennt den tatsächlich dargestellten Stand. Ein sichtbarer Hinweis bei ungespeicherten Änderungen erklärt, dass die gespeicherte Vorschau diese noch nicht enthält. Die aktive Version darf nicht als ungespeicherter Entwurf erscheinen.

**Nicht neu erfinden:** Kein zusätzlicher Designer, Farbservice oder Schriftabruf. Bestehende Upload-, Entwurfs-, Aktivierungs- und Versionsregeln erhalten. Aktives Marken-CSS und Admin-CSS dürfen sich nicht durch ungeprüfte Vererbung gegenseitig verändern.

#### M17 — Datenimport: Aufgabe und Fehler, nicht technische Rohdaten

Strukturmuster für den bestehenden Importablauf. Vorschau und Import nur in der tatsächlich vorhandenen Reihenfolge.

```text
+----------------------------------------------------------------------------------------------------------+
| EINSTELLUNGEN / Daten importieren                                                                        |
| Bereich [Vorhandene Bereichsauswahl v]      Datei [Datei auswaehlen]  beispiel.csv                       |
| [O] Datei pruefen / vorhandene Vorschau oeffnen                                                          |
+----------------------------------------------------------------------------------------------------------+
| PRUEFERGEBNIS DER AUSGEWAEHLTEN DATEI                                                                    |
| [!] Zeile 4: Eine vorhandene Pflichtangabe fehlt.                                                        |
| [>] Betroffene Zeile und konkrete Korrektur anzeigen                                                     |
| Weitere echte Befunde kompakt als Liste; keine erfundene Fortschrittsanzeige.                            |
+----------------------------------------------------------------------------------------------------------+
| [>] Dateiformat und Erklaerungen                                                                         |
| [>] Technische Details                                                                                   |
| Importaktion nur entsprechend den bestehenden Serverregeln anbieten.                                     |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Genau eine klare Dateiauswahl und eindeutiger Bezug zwischen Ergebnis und geprüfter Datei. Keine alten Prüfungsergebnisse nach Dateiaustausch als aktuell darstellen. Bestehende Importhindernisse verständlich erklären.

**Schutz:** Keine neue automatische Importfunktion, kein Wegklicken fachlicher Fehler und kein neuer Fortschrittsdienst. Rohdaten, Tokens oder interne Fehlerdetails nicht in normale Meldungen kopieren. Produktionsimporte sind keine zulässigen UI-Tests.

#### M18 — Benutzer und ähnliche Verwaltungslisten

Kompakte Verwaltung mit klarer Objektaktion; ausschliesslich vorhandene und erlaubte Daten zeigen.

```text
+----------------------------------------------------------------------------------------------------------+
| EINSTELLUNGEN / Benutzer und Zugriff                                        [+] Benutzer anlegen         |
| Suche [                                                        ]  [?] Suchen                             |
| Weitere vorhandene Filter bei Bedarf. Keine Anzeige vertraulicher Zugangsdaten.                          |
+----------------------------------------------------------------------------------------------------------+
| Name                    Konto                   Status             Aktion                                |
| Kueche Beispiel         kueche.beispiel          Aktiv              [E] Benutzer oeffnen                 |
| Testkonto               test.beispiel           Deaktiviert        [E] Benutzer oeffnen                  |
+----------------------------------------------------------------------------------------------------------+
| Auf der Detailseite: Rollen, Status und berechtigte Aktionen zusammenhaengend anzeigen.                  |
| Passwort- und Rechteaktionen nicht als namenlose Icons in jede Tabellenzeile quetschen.                  |
| Leere Liste: kurzer Hinweis und nur erlaubte Anlageaktion. Keine leere Grosskarte.                       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Dieselben Listen- und Filtermuster wie in anderen Modulen. Zugriffsstatus nicht allein durch Farbe; Aktionen dem konkreten Konto zuordnen. Rollenabhängige Sichtbarkeit ist nur Darstellung, kein Ersatz für serverseitige Autorisierung.

**Kritische Vorgänge:** Passwort, Deaktivierung und Rechteänderung behalten ihre vorhandenen separaten Schutz- und Bestätigungswege. Keine neue Rollenlogik, keine Teständerungen an echten Konten. Tabellenzeilen dürfen bei langen Namen wachsen.

#### M19 — Fehler in einem zuvor geschlossenen Detailbereich

Beispiel eines tatsächlichen Validierungsfehlers, nicht eine neue fachliche Mengenregel.

```text
+----------------------------------------------------------------------------------------------------------+
| REZEPT BEARBEITEN / Apfelmus                                                                             |
| [!] Speichern nicht erfolgreich. Bitte korrigiere den markierten Eintrag.                                |
| [Zum Fehler: Zutatenbezeichnung bei Zeile 2]                                                             |
+----------------------------------------------------------------------------------------------------------+
| Aepfel       [1800] [Gramm v]                                      [>] Details  [...] Aktionen           |
| ZEILE 2      [100 ] [Milliliter v]                    [!] Fehler    [v] Details schliessen               |
+----------------------------------------------------------------------------------------------------------+
|   Bezeichnung im Rezept [                                                                         ]      |
|   [!] Bitte die Bezeichnung ergaenzen. Diese Meldung stammt aus der bestehenden Validierung.             |
|   Zutat aus Liste [Wasser                                                                         v]     |
|   Andere Eingaben bleiben erhalten.                                                                      |
+----------------------------------------------------------------------------------------------------------+
| Zucker       [60  ] [Gramm v]                                      [>] Details  [...] Aktionen           |
+----------------------------------------------------------------------------------------------------------+
| Nicht gespeichert                                                [Abbrechen]  [S] Rezept speichern       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Fehlerzusammenfassung und lokaler Fehler führen zum sichtbaren Feld. Der zuständige Abschnitt öffnet sich automatisch; sein Fehler bleibt auch beim erneuten Schliessen erkennbar. Keine verlorenen Mengen, Reihenfolgen oder Referenzen.

**Native Validierung:** Auch ein erforderliches Feld in geschlossenen Details muss erreichbar werden. Nicht `required` entfernen, pauschal `novalidate` setzen oder Validierung aufblähen. Vorhandene Sonderbehandlung von Strukturaktionen bleibt davon getrennt.

**Unklare Netzwerkantwort:** Diese ist ein anderer Zustand als eine bestätigte Validierungsablehnung. Dann „Abschluss konnte nicht bestätigt werden“ anzeigen; weder behaupten, nichts sei gespeichert worden, noch die Schreibaktion blind wiederholen.

#### M20 — Leere Daten, keine Treffer und Ladefehler unterscheiden

Drei alternative Zustände desselben Listenmusters; nicht gleichzeitig auf der Seite darstellen.

```text
+----------------------------------------------------------------------------------------------------------+
| A / NOCH KEINE DATEN                                                                                     |
| Noch keine Bausteine angelegt.                                  [+] Baustein hinzufuegen                 |
| Keine Pagination. Kurzer Leerzustand statt einer bildschirmhohen Karte.                                  |
+----------------------------------------------------------------------------------------------------------+
| B / FILTER OHNE TREFFER                                                                                  |
| Keine Bausteine passen zu diesen Filtern.                       [Filter zuruecksetzen]                   |
| Aktiv: Kategorie Gemuese | enthaelt Milch. Auswahl bleibt sichtbar.                                      |
+----------------------------------------------------------------------------------------------------------+
| C / LADEN FEHLGESCHLAGEN                                                                                 |
| [!] Bausteine konnten nicht geladen werden.                    [Erneut laden]                            |
| Nicht als leere Datenbank oder null Treffer ausgeben.                                                    |
+----------------------------------------------------------------------------------------------------------+
| Fehlende Berechtigung ist ein weiterer eigener Zustand, kein leerer Bestand.                             |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Jeweils nur passende, tatsächlich vorhandene und berechtigte Folgeaktionen. Fehler dürfen nicht nach wenigen Sekunden verschwinden. Keine erfundene Nullzählung, wenn die Abfrage fehlgeschlagen ist.

**Übertragung:** Dieses Muster gilt für Menüs, Rezepte, Kochbücher, Vorlagen, Medien und Benutzerlisten genauso. Die fachliche Benennung und erlaubte Anlagehandlung anpassen; keine Funktionsattrappen hinzufügen.

#### M21 — Auswahl mit Detail nach Auswahl

Generisches Muster für wiederholte Optionen mit optionalem Detail; Beispiel Allergene. Desktop mit 2–4 Spalten, mobil eine Spalte.

```text
+----------------------------------------------------------------------------------------------------------+
| ALLERGENE                                                                                                |
| Eingabe: ( ) Manuell  ( ) Automatisch                                                                    |
+----------------------------------------------------------------------------------------------------------+
| [v] Gluten          [ ] Krebstiere        [v] Eier            [ ] Fisch                                  |
| [ ] Erdnuesse       [v] Milch             [ ] Schalenfruechte  [ ] Sellerie                              |
| [ ] Senf            [ ] Sesam             [ ] Sulfite          [ ] Lupinen                                |
| [ ] Soja            [ ] Weichtiere                                                                       |
| 3 von 14 ausgewaehlt                                                                                     |
+----------------------------------------------------------------------------------------------------------+
| Details (optional)  [v]  Nur fuer ausgewaehlte Allergene                                                 |
|   Gluten    Praesenz [Enthaelt      v]                                                                   |
|   Eier      Praesenz [Enthaelt      v]                                                                   |
|   Milch     Praesenz [Enthaelt      v]                                                                   |
| [!] Nicht ausgewaehlt bedeutet nicht: allergenfrei bestaetigt.                                           |
+----------------------------------------------------------------------------------------------------------+
|                                                      [Abbrechen]  [S] Speichern                          |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Auswahl als echte Formularelemente (Checkbox, Select o.ä.) mit Icon und Text. Ausgewählt = Rahmen + Haken + Text, nie nur Farbe. Detailfeld erscheint nur für ausgewählte Optionen; Zähler «n ausgewählt». Ohne JavaScript dürfen Detailfelder sichtbar bleiben; Bedienung muss möglich sein. Keine lange zweispaltige Wiederholungsliste mit dauerhaft sichtbarem Detail je Zeile.

**Sicherheitsregel:** Feldnamen, gesendete Werte, Standardwerte und Prüfstatus bleiben unverändert; «nicht ausgewählt» oder «ungeprüft» wird nie als «allergenfrei» gespeichert oder dargestellt; eine Sammelaktion wie «alle als nicht enthalten setzen» nur, wenn der Wert im Datenmodell heute existiert, und sie verändert den Prüfstatus nicht.

**Responsive:** 2–4 Spalten ab Tablet/Desktop; eine Spalte auf schmalen Displays. Chips umbrechen statt horizontal scrollen.

**Technischer Vertrag (2026-09-20):** `option_detail_group(options, submitted=none, errors=none, id='allergen', label='Allergene', code_name='allergen_code', detail_name='allergen_presence', manual=true, field_prefix=none, choices=none, mode='allergen')` ergänzt `_macros.html`; Optionen liefern `code` und `name` bzw. `display_name`, generische Optionen optional `icon`. `submitted` ist ein MultiDict oder ein Mapping mit Listen der wiederholten Werte. `.admin-option-group[data-option-group][data-option-mode][data-option-manual]` enthält `.admin-option-grid` mit einer Spalte mobil, zwei ab 768 px und drei ab 1440 px. Je `.admin-option-row[data-option-detail]` stehen Checkbox `[data-option-check]`, Icon/Text und Select `[data-option-presence]` inline; Allergene behalten zusätzlich `.allergen-row`. Index-Paarungs-Regel: **deaktivieren, nie nur verstecken; gleicher Container, gleiche Reihenfolge**. Für Wiederholfelder bleiben `allergen_code`/`allergen_presence`, Werte `contains|may_contain`, Standard `contains` sowie `field-error`, `is-invalid`, `aria-invalid` und `aria-describedby="err-allergen-presence"` erhalten; Checkbox und Detail sind bei nicht manuellem Modus deaktiviert, das Detail zusätzlich bei fehlender Auswahl. CSS blendet deaktivierte Details aus. Ohne JS bleiben vorausgewählte Paare bearbeitbar und korrekt sendbar; neue Checkboxauswahl aktiviert kein Select, die bisherige serverseitige Ablehnung unterschiedlicher Listenlängen bleibt bestehen. `field_prefix='allergen_'` verwendet dagegen ausdrücklich gesendete Einzelfelder `allergen_<CODE>` mit `absent|contains|may_contain`: ohne JS native Selects; mit JS unbenannte Checkboxen, deaktivierte Selects und je ein nur bei Abwahl aktiver `[data-option-absent]`-Hiddenwert. Kein Prüfstatus wird verändert. `[data-option-count][aria-live="polite"]` zählt die Auswahl (ohne JS Renderstand); der Hinweis «Nicht ausgewählt bedeutet nicht: allergenfrei bestätigt.» bleibt sichtbar. Nachweis: `test_admin_shared_patterns_browser.py` mit unsortierter DOM-/Klickreihenfolge, FormData-Submit, Moduswechsel, generischen Namen, explizitem `absent`, No-JS-POST und vier Viewports; bestehende Modul-Allergentests bleiben unverändert.

#### M22 — Eine Filterzeile

Gemeinsame Filterleiste für alle Listenmodule; dieselbe Reihenfolge überall.

```text
+----------------------------------------------------------------------------------------------------------+
| MENUES                                                                               [+] Menue anlegen     |
+----------------------------------------------------------------------------------------------------------+
| Suche [                                    ]  Kategorie [Alle v]  Status [Alle v]  [Weitere Filter v]  |
|                                                                                    [Filter zuruecksetzen] |
+----------------------------------------------------------------------------------------------------------+
| 8 von 8 Menues                                                                                           |
| Name / Unterzeile              Kategorie    Status        Kennzeichnungen              Aktion            |
| Apfelmus / Mittag 12.09.       Dessert      Aktiv         [GF] [V]                     [E] Bearbeiten   |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Suche zuerst. Höchstens 2–3 häufige Filter sichtbar; weitere unter «Weitere Filter». «Filter zurücksetzen» nur bei aktivem Filter. Gleiche Reihenfolge in Menüs, Bausteinen, Zutaten, Rezepten und allen übrigen Modulen.

**Responsive:** Filterzeile umbrechen; Suche bleibt erkennbar an erster Position. Keine zweite parallele Filterleiste.

**Technischer Vertrag (2026-09-20):** `filter_bar(action, search_name='q', search_value='', filters=none, more_filters=none, active=false, reset_url=none, id='filters')` rendert `form.admin-filter-bar[method=get][role=search][data-dirty-tracking=off]`. Das beschriftete Suchfeld steht zuerst; `filters` und `more_filters` sind in Jinja erfasste Markup-Slots mit unveränderten Parameternamen. Aufrufer übergeben höchstens drei häufige Filter in `.admin-filter-slots`; zusätzliche stehen in `details.admin-filter-more` mit Summary «Weitere Filter». Der Reset-Link erscheint nur bei `active` und übergebener URL. Native GET-Übermittlung und Details funktionieren ohne JS; keine neuen JS-Hooks. Nachweis: `test_admin_shared_patterns_browser.py` prüft GET-Parameter, bedingten Reset, Semantik, Fokus, 48-px-Ziele und Reflow bei 360/768/1024/1440 px.

#### M23 — Eine Zeile pro Datensatz

Kompakte Listenzeile mit klarer Hierarchie und einer sichtbaren Zeilenaktion.

```text
+----------------------------------------------------------------------------------------------------------+
| Kartoffelstock / Beilage, in 2 Menues verwendet    [Aktiv]  [GF] [V] [+2]           [E] Bearbeiten [...] |
| Apfelmus / Mittag 12.09., Cafeteria                [Entwurf] [GF] [V]               [E] Bearbeiten [...] |
+----------------------------------------------------------------------------------------------------------+
| [...] Weitere Aktionen  ->  Duplizieren (nur wenn vorhanden) | Archivieren | ...                       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Name plus einzeilige Unterzeile. Status als Badge. Kennzeichnungs-Icons mit Text oder `aria-label`. Genau eine sichtbare Zeilenaktion («Bearbeiten» oder «Ansehen») plus beschriftetes «Weitere Aktionen»-Menü für seltene Aktionen. Überlauf bei Kennzeichnungen als «+n», nicht als Badge-Wolke.

**Responsive:** Zeile darf bei Bedarf wachsen; Aktionen bleiben erreichbar. Keine drei gleichwertigen Icon-Buttons ohne Beschriftung.

**Technischer Vertrag (2026-09-20):** `list_row(name, subtitle, state, action, markings=none, overflow=0, more_actions=none)` rendert `.admin-list-row` mit `.admin-list-name`, einzeiliger `.admin-list-subtitle` (vollständiger Text im DOM und `title`), bestehendem `status_badge(state)` und `.admin-list-markings`. Der Aufrufer begrenzt den Kennzeichnungs-Slot; `overflow` ergänzt ein beschriftetes «+n». `action` verwendet das bestehende `actions`-Mapping (Link oder Button samt Formularattributen); genau diese Aktion steht offen in `.admin-list-actions`. Ein übergebener `more_actions`-Slot erscheint in `details.admin-compact-actions` mit «Weitere Aktionen». Keine neuen `data-`-Hooks, native Links/Buttons/Details bleiben ohne JS bedienbar. Nachweis: `test_admin_shared_patterns_browser.py` für eine sichtbare Aktion, Status, Überlauf, Tastatur, 48-px-Ziele und vier Breiten.

#### M24 — Formularfuss

Einheitliche Aktionsleiste am Ende jedes Formulars und Editors.

```text
+----------------------------------------------------------------------------------------------------------+
| ... Formularinhalt ...                                                                                   |
+----------------------------------------------------------------------------------------------------------+
| [Loeschen]                                              [Abbrechen]  [S] Speichern                       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Links destruktive oder seltene Aktion (nur wo vorhanden: Archivieren, Löschen). Rechts «Abbrechen» und genau eine Primäraktion «Speichern». Bei langen Editoren kompakte Sticky-Leiste gemäss R08; sie verdeckt weder Feld noch Fehler noch Fokus.

**Responsive:** Sticky-Leiste darf bei mobiler Tastatur in den Dokumentfluss wechseln. Primäraktion bleibt beschriftet.

**Technischer Vertrag (2026-09-20):** `form_footer(primary, cancel_url, rare=none, sticky=false, form_id=none)` rendert `.admin-form-footer`, links den optionalen Jinja-Slot `.admin-form-rare`, rechts `.admin-form-main` mit «Abbrechen» vor genau einer über `actions(primary=...)` gerenderten Speicheraktion. `primary` übernimmt dessen vorhandenen Mapping-Vertrag einschliesslich `name`, `value`, `formaction` und weiterer Formularattribute; Slots dürfen keine zusätzliche Primäraktion enthalten. `sticky` setzt `data-sticky`, optional `data-sticky-form`. Der vorhandene Viewport-Guard setzt `data-sticky-ready`/`.is-static`; erst nach Initialisierung und ab 700 px Höhe wird der Fuss sticky. Kleine Visual Viewports, mobile Tastatur, überhohe Leisten sowie fokussierte Eingabefelder oder Fehler im Formular lassen ihn im Dokumentfluss. Ohne JS bleibt er statisch. Nachweis: `test_admin_shared_patterns_browser.py` prüft genau eine `.btn-primary`, Submit, Fokus und geringe Höhe mit/ohne JS; bestehende Komponenten-Gates sichern `actions` ab.

#### M25 — Weitere Optionen

Seltene oder technische Angaben in nativem `<details>`; Kurztext zeigt vorhandenen Inhalt.

```text
+----------------------------------------------------------------------------------------------------------+
| Name [Kartoffelstock                     ]  Kategorie [Beilage v]                                        |
| [>] Weitere Optionen  —  Quelle erfasst, 1 technische Angabe                                           |
+----------------------------------------------------------------------------------------------------------+
| [v] Weitere Optionen  —  Quelle erfasst, 1 technische Angabe                                           |
|   Quelle [Manuell v]                                                                                     |
|   Interne Notiz [Optional                                                                        ]       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Natives `<details>`/`<summary>` verwenden. Öffnet sich automatisch bei Fehler oder gefülltem Inhalt (siehe R06). Kurztext im Summary zeigt, dass Inhalte vorhanden sind. Auf-/Zuklappen speichert und verwirft nichts.

**Responsive:** Summary bleibt vollständig lesbar; Inhalt folgt dem gemeinsamen Formular-Grid.

**Technischer Vertrag (2026-09-20):** `{% call disclosure_section(title='Weitere Optionen', id=none, open=false, has_content=false, has_error=false) %}…{% endcall %}` rendert `details.admin-compact-details.admin-disclosure` und `.admin-compact-detail-body`. `open`, `has_content` oder `has_error` öffnen serverseitig; `has_content` ergänzt «enthält Angaben» im Summary. Keine neuen `data-`-Attribute oder JavaScript-Abhängigkeit; native Tastaturbedienung erhält Formularwerte. Nachweis: `test_admin_shared_patterns_browser.py` für explizites Öffnen, Fehler/Inhalt, leeren geschlossenen Zustand, Fokus und responsive Zielgrössen mit und ohne JS.

#### M26 — Wochenplan Cafeteria — kompakte Wochenplanung

Kompakte Wochenplanung statt riesiger Einzelkarten; Zielmodell SDD v2 §5.1.

```text
+----------------------------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Cafeteria                                                                                                     |
| [<] Vorherige KW   [7.–11. September 2026 / KW 37]   [>] Naechste KW   [Heute]   [Filter]   [Suche........]  [+] Menue   |
| [Pruefung offen]  [3 ohne Allergenangaben]  [Veroeffentlicht]                                                              |
+----------------------------------------------------------------------------------------------------------------------------+
| MONTAG 7.9. — Geoeffnet                                                                                                    |
| +------------------+  +------------------+  +------------------+  +------------------+                                       |
| | Suppe            |  | Menue 1          |  | Vegetarisch      |  | Dessert          |                                       |
| | [img] Tomatensuppe|  | [img] Pouletbrust|  | [img] Risotto    |  | [img] Apfelmus   |                                       |
| | Kartoffel, Brot  |  | Kartoffelstock   |  | Gemuese          |  |                  |                                       |
| | [Entwurf] [!] Allergene fehlen | [Entwurf] [!] Allergene fehlen | [+] Dessert planen |                                       |
| | [E] Bearbeiten   |  | [E] Bearbeiten   |  | [E] Bearbeiten   |  |                  |                                       |
| +------------------+  +------------------+  +------------------+  +------------------+                                       |
| DIENSTAG bis FREITAG folgen mit demselben Tagesmuster.                                                                     |
+----------------------------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Toolbar mit Zeitraum/KW, Vor/Zurück, Heute, Filter, Suche und genau einer Primäraktion. Je Tag eine kompakte Gruppe mit den konfigurierten Slots (Suppe, Menü 1, Vegetarisch, Dessert …): Gerichtname, wichtigste Komponenten, Status-Badge, Allergenwarnung mit Text, kleines Thumbnail, «Bearbeiten». Nicht geplante Slots als kompakte Add-Aktion («+ Suppe planen»). Keine bildschirmfüllenden Food-Fotos. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Bei unzureichender Spaltenbreite in chronologische Tagesabschnitte wechseln (siehe M10). Thumbnails und Badges bleiben lesbar; keine Schriftverkleinerung.

#### M27 — Wochenplan Patienten — Raster

Klare Rasterstruktur statt verstreuter Karten; Zielmodell SDD v2 §5.2.

```text
+----------------------------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Patienten                                                                                                     |
| [<] Vorherige KW   [7.–13. September 2026 / KW 37]   [>] Naechste KW   [Heute]   [Filter]   [Suche........]              |
| [Pruefung offen]  [5 ohne Allergenangaben]                                                                                 |
+----------------------------------------------------------------------------------------------------------------------------+
| Tag          | MITTAG                                              | ABEND                                                |
|--------------+-----------------------------------------------------+------------------------------------------------------|
| Montag 7.9.  | Menue 1: Pouletgeschnetzeltes, Reis                 | Menue 1: Schinken-Kaese-Toast                        |
|              | [!] Allergene fehlen  [E] Bearbeiten                | [!] Allergene fehlen  [E] Bearbeiten                 |
|              | Vegetarisch: Gemuesegeschnetzeltes                  | [+] Dessert planen                                   |
|              | [E] Bearbeiten                                      |                                                      |
| Dienstag …   | (gleiches Raster)                                   |                                                      |
| … Sonntag    | Alle 7 Tage x Mittag/Abend x vorhandene Menuearten  |                                                      |
+----------------------------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Zeile = Tag; Spaltengruppe = Mittag/Abend; darin kompakte Slots mit Gerichtname, Komponenten, Status-Badge, Allergenwarnung mit Text und «Bearbeiten». Nicht geplante Positionen als Add-Aktion («+ Suppe planen», «+ Dessert planen»), nicht als wiederholter Fliesstext. Tagesdetail bei Bedarf öffnen. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Sieben Tage und beide Mahlzeiten bleiben erreichbar; bei schmalem Viewport Tagesgruppen untereinander statt unleserlichem Raster. Keine Preise.

#### M28 — Wochenübersicht — Tabelle

Kompakte Verwaltungsliste; Zielmodell SDD v2 §5.3.

```text
+----------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Wochenuebersicht                                                 [+] Neue Woche anlegen     |
+----------------------------------------------------------------------------------------------------------+
| KW/Zeitraum              | Titel              | Bereich    | Status        | Offene Punkte | Aktionen   |
| 7.–13. September / KW 37| Herbstwoche        | Cafeteria  | Veroeffentlicht| 2            | [O] Oeffnen [...] |
| 31. Aug.–6. Sep. / KW 36| —                  | Patienten  | Zu pruefen    | 5            | [O] Oeffnen [...] |
+----------------------------------------------------------------------------------------------------------+
| [...] Weitere Aktionen  ->  Kopieren | Vorschau | Archivieren (nur wenn vorhanden)                        |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Spalten KW/Zeitraum · Titel · Bereich · Status · offene Punkte · Aktionen. «Öffnen» ist die primäre Zeilenaktion; Kopieren, Vorschau und Archivieren im beschrifteten Overflow. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Tabelle darf in priorisierte Listen wechseln; «Öffnen» bleibt sichtbar beschriftet.

#### M29 — Küchenkalender — Monat

Monatskalender zur Orientierung; Zielmodell SDD v2 §5.4.

```text
+----------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Kuechenkalender                                                                             |
| [<] Vorheriger Monat   September 2026   [>] Naechster Monat   [Heute]   Filter: [Beide|Cafeteria|Patienten] |
+----------------------------------------------------------------------------------------------------------+
| Mo    Di    Mi    Do    Fr    Sa    So                                                                   |
|  7     8     9    10    11    12    13                                                                 |
| Poulet Hack- Rind- Schwei- Zander  —     —                                                             |
| [C]   [C]   [C]   [C]   [C]                                                                              |
| Suppe Suppe Suppe Suppe Suppe                                                                            |
| +2    +1                                                                                                 |
| 14    15    ...                                                                                          |
| (Heute: 9.9. dezent markiert, nicht dominant)                                                            |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Kurze Gerichtnamen, Bereichs-/Mahlzeit-Label, Filter «Beide | Cafeteria | Patienten». Bei Überfüllung «+ n weitere». Heute klar markieren, aber nicht dominant. Klick öffnet Tagesdetail. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Kalenderzellen dürfen umbrechen; Filter und «Heute» bleiben erreichbar.

#### M30 — Tagesansicht

Operativer Arbeitsplatz für einen einzelnen Tag; Zielmodell SDD v2 §6.

```text
+----------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Tagesansicht                                                                                |
| [<] Vorheriger Tag   Dienstag, 8. September 2026   [>] Naechster Tag   [Heute]   [...] Tag kopieren     |
+----------------------------------------------------------------------------------------------------------+
| MITTAG                                                                                                   |
| +---------------------------+  +---------------------------+  +---------------------------+              |
| | [img] Menue 1             |  | [img] Vegetarisch         |  | [+] Suppe planen          |              |
| | Pouletbrust an Kraeutersauce| | Gemuese-Curry, Reis       |  |                           |              |
| | Kartoffelstock            |  | [Entwurf] [!] Allergene   |  |                           |              |
| | [Entwurf] [!] Allergene   |  | [E] Bearbeiten  [...]     |  |                           |              |
| | [E] Bearbeiten  [...]     |  |                           |  |                           |              |
| +---------------------------+  +---------------------------+  +---------------------------+              |
| ABEND                                                                                                    |
| (gleiches Kartenmuster)                                                                                  |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Datum mit Vor/Zurück und Heute; Gruppen Mittag/Abend. Karten mit kleinem Bild, Gerichtname, Typ, Komponenten, Allergene, Status, «Bearbeiten» und Overflow. Nicht geplante Slots als kompakte Add-Karten. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Meal-Gruppen untereinander; Add-Karten und Primäraktionen bleiben tastaturbedienbar.

##### Modul Wochenplan-Kern: Cafeteria-Woche, Patienten-Raster, gemeinsame Wochen-Partials (2026-09-20)

M10/M11 und die frühere Bildgrössenregel in M11b sind für die operative Wochenansicht
ersetzt am 2026-09-20 durch M26/M27: kompakte Tagesgruppen, Menü-Thumbnails mit maximal
96 px Kantenlänge, festem Seitenverhältnis und Lazy Loading. Mittag und Abend stehen
auf breiten Arbeitsflächen nebeneinander; Gang-Editoren gehören zur jeweiligen Mahlzeit.
Lange Inhalte dürfen wachsen, Warntexte und beide Cafeteriapreise bleiben lesbar.

Die gemeinsame Wochensteuerung verwendet `page_header(..., status_items=...)`:
KW/Zeitraum, tatsächlicher Wochenstatus, Kartenprüfungen, fehlende/offene
Allergenangaben und vorhandene Gangprobleme. Keine technischen Revisionen oder IDs.
Gangprobleme behalten das Ziel `#course-issues`; das derzeitige gemeinsame Makro
unterstützt keine Linkwerte, daher steht der native Warnlink in der Werkzeugleiste.
Die wichtigste Wochenaktion steht im Kopf; Vorschau und Wochenprüfung bleiben
sekundär, seltene Aktionen im nativen «Weitere Aktionen»-Bereich.

Alle Formularnamen, Werte, CSRF-/CAS-Felder und Gang-Partials bleiben unverändert.
Die gesperrten Gang-Partials liefern eigene Primärbuttons innerhalb eingeklappter
Formulare; deren Umstellung auf neutrale Buttons benötigt den Integrationsowner.
Keine Suche, Filter, Tageskopie oder Schnellerfassung aus dem Mockup hinzuerfinden.

Die Cafeteria ordnet gemeinsame Gänge neben den beiden Menüoptionen an; im
Patientenraster stehen die Gänge unter der jeweiligen Mahlzeit. Alle Allergen-
und Prüfhinweise bleiben als Text sichtbar. Gangprobleme lassen sich am nativen
Ziel `#course-issues` aufklappen. Ohne JavaScript erlaubt eine native Bestätigung
die Veröffentlichung über dasselbe Formular mit unveränderten CSRF-/CAS-Feldern.
Kopieren zeigt Quelle und Ziel einmal in der Statusbar. Browser-Messungen prüfen
360/768/1024/1440 px, Thumbnailgrösse, Tageshöhe, Mahlzeitenausrichtung und Tastatur.

## 9. Wiederverwendung statt Seitensonderlösungen

Nutze vorhandene Strukturen. Fehlen gemeinsame Bausteine, lege sie in der passenden bestehenden Projektstruktur an. Geeignete Verträge sind:

| Baustein | Gemeinsame Verantwortung |
|---|---|
| Seitenrahmen / Basis-Template | Assets, Sidebar, Topbar, Hauptbereich, globale Meldungen |
| Seitenkopf | Titel, optionale Beschreibung, Breadcrumbs und Aktionen |
| Formular-Macros | Label, Feld, Hilfetext, Pflichtstatus und Fehlerzuordnung |
| Status-Macro | Feste Zuordnung echter Statuswerte zu Text und Farbvariante |
| Empty State | Titel, hilfreiche Erklärung, optionale erlaubte Aktion |
| Pagination | Wahrer Datenumfang, Seitenlinks, deaktivierte Zustände |
| Aktionsleiste | Eine Speicherhandlung je vorhandenem Formular; Status und Reichweite eindeutig, ohne verdeckte Felder oder Fokus |
| Arbeitszeile und Detailbereich | Eine Darstellung derselben Formularfelder; Kurztext, offene Fehler, Fokus und erhaltene Werte |
| Zeilenaktionsmenü | Beschriftete seltene vorhandene Aktionen; ursprüngliche Struktur-/Submit-Semantik und Rückkehr zum Objekt |
| Icon-Macro | Vorhandene Sprite-IDs, konsistente sichtbare Texte und zugängliche Namen; fehlende Icons erkennbar prüfen |

Jinja ist Teil der bestehenden Flask-Template-Struktur; verwende die vorhandene Vererbung und Escape-Regeln. Kein pauschales `safe`, um Darstellungsprobleme zu umgehen. [S8]

Keine parallelen Varianten wie `modern-card`, `better-table` oder `new-form-v2`. Keine universelle Mega-Komponente mit Dutzenden fachlichen Schaltern. Fachseiten dürfen unterschiedliche Inhalte haben; dieselbe Komponente darf nicht pro Seite anders aussehen.

## 10. Responsive Verhalten und Barrierefreiheit

Verwende die installierten Bootstrap-/Tabler-Breakpoints. Dieser Standard setzt die unveränderte Standardaufteilung voraus: ab 992px Desktop-Sidebar, 768–991px Tablet, darunter Smartphone. Bei nachgewiesen angepassten Projekt-Breakpoints zuerst eine zentrale Zuordnung festlegen und dokumentieren, keine zweiten konkurrierenden Breakpoints einführen.

Unterhalb des Desktop-Breakpoints: Sidebar über die vorhandene Collapse-/Offcanvas-Lösung öffnen; „Menü“, Fokus und Schliessen bleiben erreichbar. Sie darf Formulare nicht auf eine schmale Restfläche drücken. Feldgruppen auf kleinen Geräten sinnvoll umordnen: kurze Mengen-/Einheitenfelder dürfen bei ausreichendem Platz nebeneinander bleiben, umfangreiche Bereiche stehen untereinander. Abschnittslinks und Aktionsgruppen umbrechen lassen; Hauptaktionen bleiben sichtbar beschriftet.

Keine horizontale Gesamtdokument-Scrollleiste bei 390px oder im Reflow bei 320 CSS-Pixeln. Zutatenzeilen mobil umordnen statt eine Desktoptabelle zu schrumpfen. Cafeteriaraster bei unzureichender realer Spaltenbreite in chronologische Tagesabschnitte überführen; Patienten behalten sieben Tage, Mittag/Abend und vorhandene Menüarten. Andere fachlich notwendige breite Tabellen dürfen lokal, erkennbar und tastaturbedienbar scrollen; Ausnahmen begründen, wichtige Inhalte nicht abschneiden. Sticky-Speicherleisten verdecken weder Feld noch Fehler oder Fokus und dürfen bei mobiler Tastatur oder geringer Höhe in den Dokumentfluss wechseln.

Ziel ist WCAG 2.2 AA für betroffene Oberflächen: normaler Text mindestens 4,5:1, grosser Text mindestens 3:1; zur Erkennung notwendige nicht-textliche UI-Informationen grundsätzlich mindestens 3:1 zu benachbarten Farben. Prüfe Ausnahmen und Zustände sachgerecht, nicht nur ausgewählte Standardfarben. [S3, S7]

Als zusätzlicher **Projektstandard** gelten mindestens 44px für wesentliche Bedienelemente. Das ist bewusst grosszügiger als das 24px-Mindestmass des WCAG-2.2-AA-Kriteriums 2.5.8, das eigene Ausnahmen kennt. Behaupte nicht, WCAG AA verlange pauschal 44px. [S9]

Sichtbarer Fokus: auf hellen Flächen mindestens 2px Burgunder-Outline mit Abstand, in der Sidebar eine ausreichend kontrastierende helle Variante. Fokus nicht entfernen. Reihenfolge, Labels, Tastaturbedienung, 200%-Zoom und reduzierte Bewegung prüfen. Automatisierte axe-Prüfungen decken nicht alle Barrierefreiheitsanforderungen ab. [S5]

## 11. Migrationsablauf mit überprüfbaren Ergebnissen

### Phase A – Bestand und Befunde

Lies Repository-Anweisungen, relevante SDDs und bestehende Designentscheidungen. Prüfe den Git-Zustand und die tatsächlichen Versionen. Ermittle alle UI-Routen, Templates und Komponenten sowie Start- und Testbefehle.

Erweitere das vorhandene UI-Inventar mit echtem Modul, Route und sinnvollem Parameterbeispiel, Rolle/Zustand, Template, Kernaufgabe, M01–M20-/R01–R10-Zuordnung, vorhandenen Tests und tatsächlichem Nachweisstatus. Routen, Navigation, Template-/Komponentenverwendungen und Browserprüfungen abgleichen; nicht nur Indexseiten. Repräsentative Datenklassen sowie getrennte Rechte-/Fehlerzustände festlegen. Vor Änderungen Screenshots mit synthetischen Daten erfassen; produktive Personen-, Patienten- und Zugangsdaten gehören nicht in Testartefakte. Alte Audits und historische Commits bleiben historische Belege.

Formuliere Befunde konkret nach diesem Muster:

> **Problem → Beleg → Auswirkung → konkrete Korrektur → betroffene Komponenten/Seiten.**

Keine pauschalen Urteile wie „alles veraltet“ und keine unbewiesenen Aussagen über CSS oder Funktionsfehler.

**Historische Einstiegspunkte im aktuellen Stand verifizieren:**

| Einstieg | Zweck der Prüfung |
|---|---|
| `reference_scaffold/cafeteria/templates/admin/base_tabler.html` | Gemeinsamer Seitenrahmen, Navigation, Breite, Vererbung |
| `reference_scaffold/cafeteria/templates/admin/_macros.html` | Bestehende Icons und gemeinsame UI-Bausteine |
| `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html` | Zutaten-, Schritt-, Quellen- und Speicheranordnung |
| `reference_scaffold/cafeteria/templates/admin/_rezepte_fields.html` | Felder und Zeilenaktionen; Verträge nicht versehentlich verändern |
| `reference_scaffold/cafeteria/admin/recipe_routes.py` | Tatsächliche Daten- und Formularsemantik verstehen |
| `docs/design/2026-09-12-fullwidth-audit.md` | Historische Breitenbefunde, kein Nachweis aktueller vertikaler Effizienz |

#### Konkrete Prüfung von Platz und Aufgabenaufwand

| Prüffrage | Erwartete Untersuchung |
|---|---|
| Ist nur der äussere Rahmen breit? | Gesamte Containerhierarchie und echte Kerninhalte messen. |
| Wie weit liegt das erste fachliche Objekt unter dem Seitenbeginn? | Davorstehende Verwaltung, Duplikate und dekorative Karten identifizieren. |
| Wie viele Alltagsangaben sind ohne Zusatzklick bearbeitbar? | Menge/Einheit und typische Felder praktisch bedienen. |
| Wird pro Datensatz ein fast bildschirmhoher Block wiederholt? | Gemeinsames Zeilen-/Detailmuster anwenden; keine Einzelseiten-Ausnahme. |
| Sind leere optionale Felder oder technische IDs ständig offen? | Sinnvoll zusammenfassen und gezielt öffnen; Warnungen erhalten. |
| Sind Tabs, Meldungen, Kopfzeilen oder Aktionen doppelt? | Einen eindeutigen Platz und tatsächlichen Geltungsbereich festlegen. |
| Erzeugen kompakte Menüs mehr Arbeit? | Klickzahl und Scrollweg derselben Aufgabe vorher/nachher vergleichen. |
| Ist Bedienung ohne Vorkenntnis möglich? | Sichtbare Wörter, Kontext und ungefährliche Rückwege prüfen. |
| Gibt es fremde Seiteneffekte? | Gemeinsame CSS-/Macro-Verwendung sowie öffentliche Ausgabe regressionsprüfen. |

#### Messbare Dichteziele

Vergleiche identische Daten, Browserbedingungen und Viewports. Erfasse äussere/innere Breite, Gesamtseitenhöhe im normalen Ausgangszustand, Position des ersten Kerninhalts, direkt nutzbare Zeilen, Klicks/Scrollweg für eine Hauptaufgabe und verbleibende Fehler.

Für normale Listen und Editoren ist erster Kerninhalt innerhalb von ungefähr 280 CSS-Pixeln ab Viewportoberkante ein Prüf-Richtwert. Notwendige Warnungen oder mehrzeilige Titel dürfen ihn überschreiten; begründe dies, statt Pflichtinformationen zu verstecken.

Beim einfachen Rezept mit vier Zutaten und zwei Schritten sollen bei 1440 × 900 in der Standardansicht alle vier kompakten Zutatenzeilen und der Beginn der Zubereitung ohne Verwaltungs-Scrollreise sichtbar sein. Prüfe zusätzlich mindestens ein längeres Rezept mit 20 Zutaten und 10 Schritten. Es darf scrollen; eine offene Grosscard pro Eintrag bleibt unzulässig.

Für nachweislich überlange Wiederholungsformulare kann eine ungefähr halbierte Ausgangsseitenhöhe als Vergleichsziel dienen, nicht als allgemeine Schrumpfpflicht. Bereits kompakte Seiten nicht künstlich verändern. Keine verkleinerte Schrift, versteckte Zutatenliste, neuen Pflichtklicks oder abgeschnittenen Texte als Erfolg zählen.

### Phase B – Gemeinsame Grundlage

Implementiere Tokens, Tabler-Anbindung, Typografie, Seitenrahmen, Navigation und zentrale Komponenten. Prüfe deren Auswirkungen über die inventarisierten Layoutvarianten. Führe kein pauschales globales CSS ein, das Spezialansichten beschädigt.

Lege eine tatsächliche Komponentenübersicht im Entwicklungs-/Testkontext an, sofern noch keine existiert: Buttons und Zustände, Formfelder, Tabs, Cards, Badges, Alerts, Tabelle und Dialog. Verwende echte Komponenten, nicht separat nachgebaute Demo-HTML. Keine ungeschützte Produktions-Demoroute.

### Phase C – Referenz pro Seitentyp

Der Rezepteditor ist die erste Referenz: M02–M06 und M19 inklusive Inline-Mengen, Strukturaktionen, Detail-, Mobil- und Fehlerzuständen. Danach je eine vorhandene repräsentative Listen-, Formular-, Detail- und Einstellungsseite sowie besondere Facharbeitsflächen anhand M01–M20 migrieren. Fehlende Seitentypen oder Fachfunktionen nicht aus Skizzen neu erfinden.

Prüfe die Referenzen im Browser, korrigiere die gemeinsamen Komponenten und halte das resultierende Design fest. Ein generiertes Bild ist stilistische Orientierung, keine pixelgenaue Browser-Baseline und kein funktionaler Vertrag.

### Phase D – Alle Tools und Routen migrieren

Arbeite die vollständige Bestandsaufnahme ab. Übertrage die geprüften Bausteine auf jedes vorhandene Tool, einschliesslich Unterseiten, Modals, Rollenvarianten, Leer- und Fehlerzuständen.

Der Abschluss einer Referenzseite ist nicht der Abschluss der Migration. Bei globaler CSS-Wirkung jede betroffene Route mindestens überprüfen, statt aus einer einzigen schönen Seite auf den Rest zu schliessen.

### Phase E – Regression und Absicherung

Prüfe bestehende Kernabläufe mit realistischen Testdaten: Anzeigen, Anlegen, Bearbeiten, erlaubte Folgeaktionen, Validierung, Redirects, Tabs und Rollen. Besonders Feldnamen, Form-Methoden, Action-URLs, IDs, JS-Hooks, CSRF und das unterschiedliche Submit-Verhalten von `disabled`/`readonly` erhalten.

Nutze die vorhandenen Flask-Tests für serverseitiges Verhalten und Browser-Tests für echte Interaktion. Ein erfolgreicher Template-Render ersetzt keinen Browser-Test. Unverändertes Backend nicht pauschal behaupten, sondern den Diff prüfen.

### Kleine Pakete und laufende Integration

Arbeit in das vorhandene Backlog übernehmen; bestehende Pakete zuordnen und korrekte erledigte Arbeit erhalten. Gemeinsame Templates, Makros, Iconmapping und Styles haben einen Integrationsowner. Die folgende Aufgabenfolge wird vorhandenen MP-/WP-IDs zugeordnet; sie erzeugt keine zweite Paket- oder Leaseverwaltung.

| Paket | Inhalt | Pflichtnachweis |
|---|---|---|
| UI-00 | Aktuellen Stand, Regeln, vorhandene Tests, Inventar und konkrete Befunde erfassen | Tatsächliche Dateien, Rollen, Formularverträge und Baseline |
| UI-01 | Manifest konsolidieren, M01–M20 passend integrieren, Agentenverweise aktualisieren | Eine gültige Quelle ohne konkurrierende Breiten- und Formularkonzepte |
| UI-02 | Gemeinsame kompakte Arbeitszeile, Detailbereich, Aktionsmenü und Symbolverwendung | Tastatur, native/serverseitige Fehler, unveränderter Formularweg |
| UI-03 | Rezepteditor inklusive Mobil-, Detail- und Fehlerzuständen umsetzen | M02–M06 und M19 mit tatsächlichem Speichern und Strukturaktionen |
| UI-04 | Übrige Editoren, Bausteine, Stammdaten und Formulare nachziehen | Vollständige Zuordnung nach Inventar, nicht nur bekannte Screenshots |
| UI-05 | Listen, Wochenübersicht und Planungsflächen verdichten | M07–M12, vollständige Patienten-/Cafeteriasemantik |
| UI-06 | Ausgabehubs, Einstellungen, Design, Import und Benutzer prüfen/umbauen | M14–M18/M20 ohne Ausgabe-, Import- oder Rechteänderungen |
| UI-07 | Gesamtregression und Vergleichsbelege | Jede tatsächliche Seite mit Status, Vorher/Nachher und Tests |
| UI-08 | Zukunftsregeln in vorhandene Inventar-, Browser- und Reviewprüfungen integrieren | Neue UI-Routen können nicht still am Inventar vorbeigehen |
| UI-09 | Nutzertest und verbleibende Abnahme dokumentieren | Ergebnisse oder ausdrücklicher Status „noch ausstehend“ |

Jedes Paket nennt Ziel, R-/M-/A-IDs, tatsächliche Dateien und Besitzer, Abhängigkeiten, konkrete Tests und Risiken. Grosse Seitenpakete weiter aufteilen; nach stabiler gemeinsamer Basis nur unabhängige und dateidisjunkte Seiten parallel bearbeiten. Keine gestarteten Worker ohne tatsächlichen Ausführungsbeleg behaupten. Kleine Änderungen fortlaufend integrieren und prüfen; gemeinsame Ursachen zentral korrigieren und alle betroffenen Verwendungstypen regressionsprüfen. Manifeständerung oder Rezepteditor allein schliessen die Migration nicht ab.

## 12. Reproduzierbarkeit, Abnahmetests und visuelle Regression

Prüfe mindestens diese Viewports:

| Viewport | Zweck |
|---|---|
| 1440 × 900 | Regulärer Desktop |
| 1024 × 768 | Kleiner Desktop / Grenzfall mit Sidebar |
| 768 × 1024 | Tablet mit eingeklappter Navigation |
| 390 × 844 | Smartphone |
| 1920 × 1080 | Breitenprüfung der gemeinsamen Layoutvarianten |
| 2560 × 1440 | Grosse Arbeitsfläche: innere Breite und Dichte prüfen |

Jede interne UI-Seite mindestens bei 1440 × 900 und 390 × 844 öffnen, visuell prüfen und eine passende Kernaufgabe ausführen. Repräsentative Seitentypen und gemeinsame Komponenten zusätzlich in allen sechs Viewports prüfen. Dazu echter **200-%-Browserzoom**, **Reflow bei 320 CSS-Pixeln**, Tastatur und reduzierte Bewegung. Falls echte Zoomsteuerung fehlt, einen ersatzweisen Reflowtest ausdrücklich als solchen führen, niemals als ausgeführten Zoomtest. Fehlende Rollen, Fixtures oder Browserwerkzeuge ergeben „blockiert“ oder „nicht ausgeführt“. Signage behält zusätzlich seine fachlichen 1920 × 1080-/3840 × 2160-Ausgabeprüfungen; Admin-Vollbreite gilt nicht innerhalb eines A4-Druckbogens. Alle tatsächlich geprüften Kombinationen im Inventar festhalten.

Stabile Referenzbedingungen festlegen: Browser und Version, Betriebssystem beziehungsweise Container, tatsächlich geladene Fonts, Viewport, Gerätepixelfaktor, Sprache, Zeitzone, Benutzerrolle, Testdaten und eingefrorene relevante Uhrzeit. Animationen für visuelle Tests kontrollieren, nicht wahllos im Produkt entfernen. Auf Font- und Inhaltsbereitschaft warten, nicht allein mit festen Sleep-Zeiten arbeiten.

Playwright Test kann Screenshots erzeugen und gegen Referenzen vergleichen. Rendering kann sich zwischen Umgebungen unterscheiden; Referenzen und Vergleichsläufe müssen deshalb in kontrollierten vergleichbaren Umgebungen entstehen. [S4]

Freigegebene Baselines versionieren. Der Agent darf vorgeschlagene erste Referenzen erstellen, aber sie nicht selbst als vom Auftraggeber freigegeben ausgeben. Fehlschlagende Screenshots nie blind aktualisieren, um eine Prüfung grün zu machen. Dynamische Daten nur begründet maskieren; keine eigentlichen Layoutfehler wegmaskieren.

**Ein Prompt allein ist keine Garantie für identische Oberflächen. Verbindlich wird der Standard durch gemeinsame implementierte Komponenten, zentrale Tokens und geprüfte visuelle Referenzen.**

### 12.1 Abnahmekriterien A01–A24

Nutze die vorhandenen Testmittel. Neue reine Entwicklungsabhängigkeiten nur im Rahmen der Projektregeln; keine zusätzliche Produktionsbibliothek für diese UI-Aufgabe. Tests dürfen echte Layoutprobleme nicht durch blind aktualisierte Screenshots als neue Baseline akzeptieren.

| ID | Test | Bestehen bedeutet |
|---|---|---|
| A01 | Vollständiges UI-Inventar | Alle tatsächlich vorhandenen internen Seiten, Unteransichten und relevanten Rollen-/Zustandsklassen sind nachvollziehbar erfasst. |
| A02 | Volle Breite | Äussere und innere Gesamtcontainer nutzen den Arbeitsbereich ohne künstliche Mittelsäule und ohne Dokumentüberlauf. |
| A03 | Aufgabenbeginn | Kernarbeit steht vor optionaler Verwaltung; doppelte Bereichsauswahl und gleichlautende Prüfaktionen sind beseitigt. |
| A04 | Rezeptbasis 4/2 | Kurze Basisfelder, vier direkt bedienbare Zutaten und Beginn der Zubereitung erfüllen das beschriebene Desktopziel. |
| A05 | Langes Rezept 20/10 | Liste bleibt kompakt; notwendiges Scrollen statt riesiger Vollformulare; Angaben vollständig zugänglich. |
| A06 | Inline-Mengenänderung | Genau ein massgebliches Feld je Wert; ohne Detaildialog ändern und korrekt speichern. |
| A07 | Detailzustand | Öffnen, Schliessen und lokale Navigation verlieren oder speichern keine Eingaben. |
| A08 | Strukturaktion | Hinzufügen, Verschieben und Entfernen erhalten Reihenfolge, Zuordnungen, signierte Kontexte und bestehende Speichersemantik. |
| A09 | Fehler in geschlossenen Bereichen | Native und serverseitige Fehler öffnen bzw. erschliessen den richtigen Bereich, setzen sinnvollen Fokus und erhalten Werte. |
| A10 | Unverändertes Speichern | Daten, Referenzen, readonly/disabled-Bedeutungen und nicht auflösbare bestehende Zuordnungen überstehen den Roundtrip. |
| A11 | Gespeichert versus geprüft | Keine Bestätigung neuer ungespeicherter Werte durch alten Prüfstand; fehlende Allergene nicht als allergenfrei darstellen. |
| A12 | Unklare Schreibantwort | Kein falscher Erfolg und keine blinde Wiederholung; vorhandenen aktuellen Stand nachvollziehbar prüfen. |
| A13 | Patientenumfang | Alle sieben Tage, Mittag/Abend und bestehenden Menüarten erreichbar; keine Preise. |
| A14 | Cafeteriaumfang | Fünf reguläre Tage, vorhandene Menüarten und beide Preisgruppen korrekt; Ausnahmen aus bestehender Konfiguration erhalten. |
| A15 | Druckdatenstand | Absichtlich unterschiedliche gewählte/veröffentlichte Wochen ergeben korrekt beschriftete und tatsächlich passende Ausgaben. |
| A16 | Symbole und Texte | Vorhandene Icons geladen; gleiche Handlung gleich; Hauptaktionen auf Desktop und Mobil sichtbar beschriftet. |
| A17 | Bedienbarkeit | Maus, Tastatur, Touch, Trefferflächen, Fokus, Smartphone und echte Zoom-/Reflowprüfungen korrekt. *(Ersetzt am 2026-09-20 durch: Pflichtbreiten 360, 768, 1024, 1440 px in der Testmatrix. Sidebar darf mobil zu Drawer werden.)* |
| A18 | Sticky-Leisten | Kein Feld, Fehler oder Fokus verdeckt; eingeblendete mobile Tastatur und geringe Höhe berücksichtigt. |
| A19 | Suche und Leerzustände | Gesamte bestehende Suchsemantik erhalten; Datenleerstand, Filtertrefferlosigkeit, Fehler und Rechte unterscheiden. |
| A20 | Bestehende Sicherheitsgrenzen | CSRF, Formularkontext, Rollen, Versionierung, Session- und Serverprüfungen unverändert wirksam. |
| A21 | Technischer Diff | Keine ungefragten Framework-, Datenmodell-, Vertrags-, Fachlogik- oder Betriebsänderungen. |
| A22 | Öffentliche Nebenwirkungen | Website, Login, Druck/PDF und Signage nicht durch Admin-Styles beschädigt oder mit Admininhalten vermischt. |
| A23 | Vergleichbare Belege | Gleiche Daten/Viewports, echte Screenshots und nachvollziehbare Aufgabenmessung; Baselines nicht blind ersetzt. |
| A24 | Zukunftsgate | Neue/geänderte UI-Routen und gemeinsame Komponenten sind mit passenden Inventar-, Funktions- und Browserprüfungen verbunden. |
| A25 | Auswahl mit Detail nach Auswahl | Kein dauerhaft sichtbares Detailfeld bei nicht ausgewählter Option; Feldnamen, Werte, Standardwerte und Prüfstatus unverändert; «nicht ausgewählt» nie als «allergenfrei» (M21). |
| A26 | Eine Primäraktion je Kontext | Pro Formular genau eine hervorgehobene Speicherhandlung; destruktive Aktionen links, seltene im «Weitere Aktionen»-Menü (M24, R08). |
| A27 | Einheitliche Listenstruktur | Dieselbe Filterzeile und Zeilenaufbau in allen Modulen; Suche zuerst, «Filter zurücksetzen» nur bei Aktivität (M22, M23). |
| A28 | Wochenplan Desktop-Dichte | Wochenplan-Ansichten bei 1440 px ohne grosse Leerflächen und ohne bildschirmfüllende Food-Fotos (M26–M30, SDD v2 §5). |
| A29 | Nicht geplante Slots | Leere Planungspositionen als kompakte Add-Aktion («+ Suppe planen»), nicht als Fliesstext oder grosse Leerkarten. |
| A30 | Statuschips mit Handlung | Statuschips mit sichtbarem Text; optional als Link zum Filtern oder Navigieren, nicht nur als Farbindikator. |
| A31 | Review-Checkliste v2 | `docs/design/design-system-v2-2026-09-20/06_QA/UI_REVIEW_CHECKLIST_V2.md` je UI-Paket vollständig abgehakt. |

### 12.2 Nutzertest mit mindestens drei tatsächlichen Personen

Mindestens drei technisch unerfahrene Personen testen repräsentative Kernaufgaben ohne navigierende Hilfestellung: Menge ändern, Zutat hinzufügen und verschieben, Schritt bearbeiten, fehlende Angaben finden und bewusst speichern. Dazu je eine Aufgabe aus Planung, Verwaltung und Ausgabe.

Dokumentiere Suchwege, Fehlklicks, Rückfragen und kritische Missverständnisse. Als Projektziel sollen mindestens zwei von drei Personen jede Kernaufgabe ohne Wegbeschreibung abschliessen. Verwechslungen wie globales Löschen statt lokalem Entfernen, Prüfen statt Speichern oder falscher Druckzeitraum verhindern die Nutzerabnahme unabhängig von einer guten Durchschnittsquote.

Fehlen Testpersonen, bleibt dieser Nachweis offen. Ein Agententest oder automatisierter Kontrastcheck ersetzt weder reale Benutzer noch eine vollständige Zugänglichkeitsprüfung.

## 13. Dauerhafte Regeln für alle Coding-Tools

Dieses Manifest bleibt unter `docs/design/2026-09-09-unified-ui-design-system.md` die einzige ausführliche Quelle. AGENTS.md und CLAUDE.md enthalten denselben kurzen Leseauftrag; bestehende und bereichsspezifische Regeln bleiben erhalten. [S10, S11]

> Vor jeder Frontend-Änderung das zentrale UI-Manifest vollständig lesen und passende R-/M-/A-Regeln verwenden. Volle interne Arbeitsbreite, kompakte Wiederholungszeilen, direkt bedienbare häufige Felder und beschriftete Icons gelten für jede neue und geänderte Seite. Details, Fehler, Formulardaten und Speicherzustände sicher behandeln. Route, Rolle/Zustand, Muster und tatsächliche Tests im vorhandenen UI-Inventar nachführen. Keine Fertigmeldung ohne Funktions- und Sichtnachweise; fehlende Prüfungen nennen.

Ein Dateiname allein belegt nicht, dass der Inhalt gelesen wurde. Startdateien kurz halten und die ausführliche Spezifikation an diesem einzigen Ort pflegen.

Keine parallele Prüfarchitektur: bestehende Routeninventar-, Formular- und Browserprüfungen um vertikale Effizienz, Detail-/Fehlerverhalten, Beschriftungen und Vertragsroundtrips erweitern. Statische Suche ersetzt keine Bedienprüfung. Neue Routen brauchen eine bewusste Inventarzuordnung; jede globale Komponentenänderung löst Regression ihrer betroffenen Verwendungstypen aus.

Frühere Freigaben bei konkreten Änderungen revalidieren, nicht pauschal entwerten oder als aktuelle eigene Tests ausgeben. Bestandsabweichungen bleiben offen, bis sie behoben oder ausdrücklich fachlich begründet sind. Gestaltungsausnahmen nennen Ursache, Umfang und Entscheidung; „war vorher auch so“ genügt nicht. Baselines nicht ungeprüft ersetzen.

## 14. Sicherheits- und Änderungsgrenzen

Keine Änderungen an Authentifizierung, Autorisierung, Session-Handling, Secrets, CSRF oder Datenverträgen als Abkürzung für UI-Arbeit. Keine zusätzlichen öffentlichen Schnittstellen und keine unkontrollierten externen Fonts, CDNs oder Telemetrie integrieren.

Flask, Jinja, Tabler, Iconeinbindung, Datenhaltung und Fachlogik bleiben bestehen. Keine neue Produktionsabhängigkeit, Datenmigration, Speicher-/Vorschau-API, Freigabe- oder Allergenlogik und kein ungefragter Build-/Deploymentumbau. Standardbereich sind bestehende Templates/Partials, projektbezogene Styles, kleine Interaktionen im vorhandenen Assetweg, Tests und Dokumentation. Unvermeidbare darstellungsbezogene Python-Änderungen nach bestehenden Regeln separat begründen. Keine Rezept-, Klinik- oder Formulardaten ungefragt in Local Storage, neue Offline-Speicher oder externe Telemetrie schreiben.

Vor jedem Formular den bestehenden Vertrag sichern: URL, HTTP-Methode, Feldnamen, Indizes, IDs, CSRF, signierter Kontext, Versions-/Konfliktprüfung, `readonly`/`disabled`, `formaction`, `formnovalidate`, Fehlerantwort, Redirect und tatsächlicher Speicherzeitpunkt. Eine optisch lokale Aktion darf nicht unbemerkt eine persistente globale Änderung werden. Strukturaktionen behalten ihre gesonderte Semantik; kein pauschales `novalidate` und keine zweite clientseitige Sortierlogik.

Keine produktiven Lösch-, Import-, Benachrichtigungs- oder Versandaktionen durch Tests auslösen. Vorhandene autorisierte Entwicklungs-/Testumgebung und synthetische Daten verwenden. Sicherheitslücken oder notwendige fachliche Erweiterungen getrennt benennen; Sicherheitsprüfungen nicht verstecken oder stillschweigend aus dem Scope entfernen.

Keine fremden Änderungen überschreiben, keine grossflächigen Rewrites und keine unautorisierten Pushes oder Deployments. In kleinen logisch prüfbaren Änderungen arbeiten. Ohne funktionsfähige Browser-Testumgebung darf Code vorbereitet werden, aber die visuelle Abnahme bleibt offen.

## 15. Lieferumfang und Definition of Done

Liefere die tatsächlichen Implementierungsänderungen, ein konsolidiertes Designsystem, konkrete Befunde, das vollständige UI-Inventar, Testbelege und Vorher-/Nachher-Screenshots. Nutze die vorhandene Dokumentations- und Teststruktur; neue Parallelordner sind kein Qualitätsmerkmal.

Die Abdeckungstabelle enthält mindestens:

| Tool / Modul | Seite / Route / Rolle / Zustand | R-/M-/A-Muster | Befund und Ursache | Geänderte Dateien | Vorher/Nachher | Test / Viewport | Status / Restpunkt |
|---|---|---|---|---|---|---|---|

Teststatus eindeutig verwenden: **bestanden**, **fehlgeschlagen**, **nicht ausgeführt**, **blockiert** oder **nicht anwendbar mit Begründung**. Zusätzlich **implementiert**, **technisch geprüft**, **visuell geprüft** und **durch Benutzer abgenommen** unterscheiden. Ein geerbtes Basis-Template, HTTP 200, Build, Screenshot oder Breitenwert beweist weder vollständige Interaktion noch das Gesamtaudit.

Vorher-/Nachher-Belege unter denselben Bedingungen speichern. Zu HTML-Prototypen die tatsächlichen HTML-/CSS-/JS-Quellen ablegen; Prototypen und generierte Bilder sind kein Implementierungsnachweis. Anwendungsscreenshots eindeutig kennzeichnen. Bereinigte HTML-Belege enthalten keine Zugangsdaten, Sessionwerte, CSRF-Tokens oder personenbezogenen Patientendaten. Die Übergabe nennt pro Paket Anforderungen, tatsächliche Dateien, erhaltene Formularverträge, ausgeführte Tests, Screenshotbelege und Restentscheidungen.

Eine reine Manifestkonsolidierung erfüllt nur den Dokumentteil UI-01. Produktimplementierung, Inventar, Browser-/Formularprüfungen und der reale Drei-Personen-Nutzertest brauchen jeweils eigene Belege; dieses Dokument behauptet keinen bestandenen Produkttest.

Die Gesamtmigration ist erst abgeschlossen, wenn alle vorhandenen betroffenen Tools und Routen inventarisiert, migriert und entsprechend der Testmatrix geprüft sind; das Design zentral umgesetzt ist; wesentliche Abläufe weiterhin funktionieren; keine unerklärten alten Admin-Stile verbleiben; keine Attrappen oder erfundenen Daten hinzugekommen sind; und verbleibende Einschränkungen nicht verschwiegen werden.

Verwende für den Abschlussbericht:

```text
## Konkrete Ausgangsprobleme
Befund, Beleg und Auswirkung.

## Umgesetzte gemeinsame Änderungen
Tokens, Tabler-Anbindung, Layout und Komponenten.

## Abdeckung aller Tools und Seiten
Tatsächliche Namen/Routen mit Status und Restpunkten.

## Tests und Screenshots
Werkzeug, Befehl bzw. Testname, Umgebung, Ergebnis und Belegpfad.

## Änderungen ausserhalb des Frontends
Nur tatsächlich erfolgte Änderungen; sonst nach Diff-Prüfung „keine“.

## Offene Punkte / Blocker
Auswirkung und fehlende Voraussetzung. Nicht ausgeführte Prüfungen nennen.
```

## 16. Ausführungsauftrag

Beginne jetzt mit Repository- und UI-Inventar, konkreten Befunden und dem Start der vorhandenen Testumgebung. Implementiere danach die gemeinsamen Grundlagen, prüfe Referenzen pro Seitentyp und migriere sämtliche vorhandenen Tools und UI-Routen.

**Nicht nur eine Seite modernisieren. Nicht nur Farben austauschen. Nicht nur eine Liste von Empfehlungen liefern. Einen gemeinsamen, getesteten Designstandard im bestehenden Flask-/Tabler-Projekt umsetzen und die vollständige Abdeckung nachweisen.**

---

## Technische Quellen

Die Quellen erläutern Werkzeuge und technische Prüfanforderungen. Die konkrete Palette, Typografie und Layoutmasse oben sind eigenständige Projektentscheidungen. Für die Implementierung die tatsächlich installierten Versionen berücksichtigen.

- **[S1] Tabler: Customize Tabler.** Theme-Anpassung und Primärfarbe. `https://docs.tabler.io/ui/getting-started/customize`
- **[S2] Bootstrap: CSS variables / Buttons.** Globale und komponentenbezogene Variablen. `https://getbootstrap.com/docs/5.3/customize/css-variables/` und `https://getbootstrap.com/docs/5.3/components/buttons/`
- **[S3] W3C: Understanding SC 1.4.3, Contrast (Minimum).** Kontrastberechnung und Schwellenwerte. `https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html`
- **[S4] Playwright: Visual comparisons.** Screenshot-Vergleiche und Umgebungsabhängigkeit. `https://playwright.dev/docs/test-snapshots`
- **[S5] Playwright: Accessibility testing.** axe-Integration und Grenzen automatisierter Prüfungen. `https://playwright.dev/docs/accessibility-testing`
- **[S6] Flask: Testing Flask Applications.** Testclient und Testaufbau. `https://flask.palletsprojects.com/en/stable/testing/`
- **[S7] W3C: Understanding SC 1.4.11, Non-text Contrast.** Kontrast notwendiger UI-Informationen. `https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html`
- **[S8] Flask: Templates.** Jinja-Einbindung und Escaping. `https://flask.palletsprojects.com/en/stable/templating/`
- **[S9] W3C: Understanding SC 2.5.8, Target Size (Minimum).** Mindestzielgrössen und Ausnahmen. `https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html`
- **[S10] OpenAI: Custom instructions with AGENTS.md.** Projektanweisungen für Codex. `https://developers.openai.com/codex/guides/agents-md/`
- **[S11] Anthropic: How Claude remembers your project.** Projektanweisungen über CLAUDE.md. `https://code.claude.com/docs/en/memory`
