# Dishboard – Korrekturauftrag für Patientenplan und Menüeditor

Verbindlicher Auftrag des Auftraggebers vom 2026-09-12 (wörtlich übernommen). Ergänzt das Referenzpaket
`docs/design/screenshot-referenzen-0911/` und die Vollbreiten-Vorgabe (`docs/design/2026-09-12-fullwidth-audit.md`).

## Geltungsbereich (Ergänzung des Auftraggebers, 2026-09-12)

> «Die Kritik gilt für das ganze UI/UX, einfachere Bedienung — ohne Funktionseinbussen.»

Patientenplan und Menüeditor sind die Referenz-Umsetzung. Dieselben Grundsätze gelten für jede Bedienseite
der Anwendung: Wiederholungen entfernen, Hauptaufgabe zuerst zeigen, Verwaltungsangaben bei Bedarf öffnen,
eine hervorgehobene Hauptaktion, verständliche Wörter, Prüf-/Statusaussagen wahrheitsgetreu trennen.
Keine Funktion, kein Formularfeld, keine Route und kein Schreibweg fällt dabei weg; bedarfsgerecht
geöffnete Bereiche bleiben mit einem Klick erreichbar und übertragen weiterhin alle Werte.

## Auftrag

Überarbeite die bestehenden Ansichten weiter. Technisch unerfahrene Küchenmitarbeitende sollen zuerst die Menüs sehen, den richtigen Eintrag ändern und den gespeicherten Stand nachvollziehbar prüfen können. Verwaltungsfelder dürfen die eigentliche Planungsaufgabe nicht verdrängen.

Die zuletzt geforderte **volle verfügbare Arbeitsbreite auf allen Bedienseiten bleibt verbindlich**. Dieser Auftrag ist ausdrücklich keine Rückkehr zu schmalen Formularcontainern. Flask, Tabler und der bestehende technische Unterbau bleiben erhalten.

Implementiere die nachfolgend beschriebenen Darstellungsverbesserungen nach einer Bestandsaufnahme. Liefere nicht nur eine weitere Designanalyse. Eine ungeklärte Fachlogik blockiert den betroffenen Teil, nicht sämtliche unabhängigen Layoutarbeiten.

## 1. Prüfgrundlage und Beweisgrenzen

Grundlage sind drei vom Auftraggeber bereitgestellte Screenshots:

| Referenz | Sichtbarer Inhalt |
|---|---|
| S1 | Patientenplan am Seitenanfang: doppelte Bereichsauswahl, grosser Status-/Aktionsblock, weitere Wochenaktionen, Wochenformular und Beginn des ersten Tages. |
| S2 | Patientenplan weiter unten: Montag mit Mittag/Abend, zwei umfangreichen Ausgabeformularen und vier Menükarten. |
| S3 | Patienten-Menüeditor: Grunddaten und Bausteine links, Prüfung rechts, mehrere Aktionen am unteren Rand. |

Die Screenshots belegen Darstellung und sichtbare Texte. Sie belegen nicht, welche serverseitigen Prüfungen, Statusdefinitionen, Fehlerbehandlungen oder mobilen Layouts tatsächlich implementiert sind. Insbesondere sind eine fehlende fachliche Sperre, ein ungeschützter Navigationswechsel und ein Überdecken von Feldern durch die Aktionsleiste **Prüffragen**, keine bereits nachgewiesenen technischen Fehler.

Die vier Haupteinstiege und die breite Arbeitsfläche sind auf diesen Ansichten bereits vorhanden. Sie bleiben erhalten. Daraus folgt noch keine Abnahme aller übrigen Seiten.

## 2. Konkrete Befunde

| ID | Priorität | Beobachtung | Ziel |
|---|---|---|---|
| P01 | P1 | S1 zeigt Cafeteria/Patienten zweimal als Bereichsauswahl. | Ein einziger Bereichswechsel; Wochenübersicht sinnvoll darin erreichbar. |
| P02 | P1 | „Wochenangaben prüfen“ steht im Kopf und nochmals unter dem Statusblock. | Eine eindeutige Prüfaktion pro Wochenkontext. |
| P03 | P1 | Auf S1 ist trotz grossem Bildschirm noch kein Gericht sichtbar. | Menüs vor optionalen Verwaltungsangaben zeigen. |
| P04 | P1 | S2 beginnt jede Mahlzeit mit Betrieb, Hinweis, Beginn, Ende und eigener Speicherung. | Ausgabeinformationen zunächst kompakt lesen, nur bei Bedarf bearbeiten. |
| P05 | P0 | „Live“ und „Keine offenen Prüfungen“ stehen über Einträgen mit „Geprüft“, ungeprüften Rezepturhinweisen und nicht erfassten Allergenangaben. | Veröffentlichungsstand, vorhandene Prüfung und Datenvollständigkeit wahrheitsgetreu unterscheiden. |
| P06 | P1 | Lange Rezepturhinweise dominieren die Menükarten. | Fehlende Angaben kurz sichtbar machen, vollständige Hinweise gezielt öffnen. |
| P07 | P1 | S3 bietet Katalog und eigenen Text gleichzeitig an und erklärt lediglich, dass beides nicht gleichzeitig verwendet werden soll. | Die Eingabeart durch eindeutige Bedienung führen. |
| P08 | P1 | S3 wiederholt Bausteinbezeichnungen und verschachtelt jeden Baustein in einen grossen Formularblock. | Kompakte, verständliche Zeilen mit sichtbaren Änderungsaktionen. |
| P09 | P1 | Speicher- und Prüfhandlungen sind auf Fussleiste und rechte Spalte verteilt. | Einen eindeutigen Speicherweg hervorheben und Prüfhandlungen zusammenhängend anbieten. |
| P10 | P2 | Technische Begriffe, lange Hilfetexte und dicht aneinanderstehende Tages-/Statusangaben erschweren das Lesen. | Verständliche Wörter, klare Abstände und konsistente Hierarchie. |

P0 bezeichnet hier einen vor Abnahme zu klärenden Darstellungs-/Datenkonflikt. Es erlaubt keine eigenmächtige Änderung von Fachlogik oder gespeicherten Daten.

## 3. Patientenplan: Menüs zuerst

### 3.1 Ein kompakter Kopfbereich

Verwende genau diese Informationsreihenfolge:

1. **Patientenplan** mit verständlichem Datumsbereich, beispielsweise „7.–13. September 2026 · KW 37“.
2. **Eine** Bereichs-/Seitennavigation für Cafeteria, Patienten und die bestehende Wochenübersicht.
3. Tatsächlicher Veröffentlichungsstand und verständliche Zusammenfassung vorhandener Prüfangaben.
4. Eine zusammengehörige Wochensteuerung: Vorschau, nächste sinnvolle Hauptaktion und „Weitere Aktionen“.
5. Unmittelbar anschliessend die Tagesplanung.

Datumsbereich und Kalenderwoche stammen aus der tatsächlich gewählten Woche. Ein frei editierbarer Wochentitel ist kein Ersatz für die Datumsidentität. Eine Wochenauswahl oder Navigation zur Vor-/Folgewoche darf nur vorhandene Funktionen und Verträge nutzen.

Die obere Steuerung soll auf Desktop kompakt bleiben. Bei 1366 × 768 und 1920 × 1080 muss im regulären Ausgangszustand mindestens der erste tatsächliche Menüeintrag sichtbar sein, ohne zuerst durch Verwaltungsformulare zu scrollen. Keine starre Höhe einbauen, die Fehler, Warnungen oder lange Texte abschneidet. Die gesamte Woche muss nicht auf einen Bildschirm passen.

### 3.2 Wochenverwaltung nach Bedarf öffnen

Das Formular für Wochentitel und Hinweis wird unter **„Wochenangaben ändern“** bei Bedarf geöffnet. Bestehende Validierungsfehler öffnen den Bereich automatisch und bleiben mit den Eingaben sichtbar.

CSV-Export, Vorwoche kopieren und vorhandene Standardvorgaben werden unter **„Weitere Aktionen“** sinnvoll zusammengefasst. Ihre ursprünglichen URLs, Berechtigungen und fachlichen Wirkungen bleiben gleich. Kopieren benennt Quelle, Ziel und bekannte Auswirkungen. Keine unbestätigten Aussagen über Überschreiben oder mitkopierte Prüfstände.

Der Satz „Dieses Raster enthält ausschliesslich Speiseplandaten“ und der Begriff „Getrenntes Raster“ gehören nicht als dauerhafter grosser Hinweis vor die Planung. Ein kurzer Kontext „Montag–Sonntag · Mittag und Abend“ reicht dort. Falls eine Erklärung fachlich notwendig ist, bleibt sie gezielt erreichbar. Wichtige Warnungen werden davon nicht erfasst und dürfen nicht versteckt werden.

Getrennte vorhandene Speicherformulare bleiben getrennt. Kein neues „Alles speichern“ und keine automatische Änderung beim Öffnen der Seite.

### 3.3 Tagesblöcke erhalten, Verwaltungsfelder reduzieren

Die Patientenplanung bleibt vollständig: **sieben Tage, Mittag und Abend, zwei vorhandene Menüarten je Mahlzeit, keine Preise**.

Behalte die sinnvolle fachliche Gruppierung:

- Tagesüberschrift mit Datum und separat abgesetzter vorhandener Belegungsinformation;
- Mittag mit den beiden zugehörigen Menüeinträgen;
- Abend mit den beiden zugehörigen Menüeinträgen.

Auf ausreichend breiten Displays können Mittag und Abend nebeneinander stehen. Pro Mahlzeit stehen die beiden Menüarten nebeneinander, soweit die realen Namen und Bedienelemente lesbar bleiben. Auf kleineren Displays wird chronologisch umgebrochen. Keine sieben schmalen Tagesspalten erzwingen und keine Mahlzeit standardmässig unsichtbar machen.

Betrieb, Ausgabehinweis und Zeiten erscheinen zuerst als kurze Zusammenfassung. **„Ausgabeangaben ändern“** öffnet das bestehende Formular für genau diese Mahlzeit. Bei Fehlern bleibt dieses Formular offen.

Leere Zeitfelder sind nicht automatisch eine Schliessung. Zeige beispielsweise „Zeiten nicht eingetragen“, wenn tatsächlich keine Zeiten vorliegen. „Standardzeiten“ nur nennen, wenn sie nachweislich angewendet werden. Nicht eigenmächtig Zeiten ergänzen.

### 3.4 Menükarten als Übersicht

Zeige pro Karte in dieser Reihenfolge:

| Inhalt | Darstellung |
|---|---|
| Menüart | Eindeutig innerhalb der betreffenden Mahlzeit. |
| Menüname | Vollständig und gut lesbar. |
| Bausteine | Kurze Zusammenfassung; Namen dürfen umbrechen. |
| Fehlende wichtige Angaben | Direkt sichtbar, zum Beispiel „Allergenangaben nicht erfasst“. |
| Vorhandener Prüfstand | Mit wahrheitsgetreuem Geltungsbereich, nicht als pauschale Vollständigkeitsgarantie. |
| Handlung | Sichtbares „Menü bearbeiten“. |
| Lange Hinweise | „Prüfhinweis anzeigen“ mit tatsächlich vorhandenem vollständigem Inhalt. |

Ein eingeklappter Hinweis darf nicht den einzigen Nachweis einer fehlenden wichtigen Angabe enthalten. Die Warnung bleibt direkt auf der Karte. Keine internen Hinweise löschen, keine feste Kartenhöhe erzwingen und keine Schrift verkleinern, um identische Karten zu erhalten.

## 4. Prüfstand und Datenvollständigkeit klären

Untersuche im Bestand getrennt:

- die Bedeutung und Quelle von „Live“;
- die Berechnung oder Speicherung von „Keine offenen Prüfungen“;
- die Bedeutung und den Geltungsbereich von „Geprüft“;
- die Datenquelle der Allergenangaben;
- die Quelle und Aktualität des ungeprüften Rezepturhinweises.

Ein veralteter Freitext ist möglich, aber nicht bewiesen. Ein grünes Badge beweist umgekehrt keine vollständige Deklaration.

**Nicht erfasste Allergenangaben sind keine bestätigte Allergenfreiheit.** Titel, Bilder und vermutete Rezepturen dürfen nicht zu einer neuen automatischen Deklaration werden.

Stelle vorhandene Aussagen getrennt dar. Beispiel einer Struktur, keine neue Statusdefinition:

| Aussage | Voraussetzung |
|---|---|
| Veröffentlichungsstand: Veröffentlicht | Nur, wenn dies der nachgewiesenen Bedeutung des vorhandenen Zustands entspricht. |
| Gespeicherter Prüfstand: bestätigt | Nur mit der tatsächlich gespeicherten Prüfung und ihrem belegten Geltungsbereich. |
| Allergenangaben: nicht erfasst | Bei tatsächlich fehlenden Daten direkt sichtbar. |
| Rezepturhinweis vorhanden | Nur bei tatsächlich vorhandenem Hinweis; vollständig erreichbar. |

Keine Prüfung still zurücksetzen, keine fehlenden Angaben automatisch bestätigen und keine neue Veröffentlichungssperre nur im Browser einführen. Ein fachlicher Fehler im Bestand ist separat zu dokumentieren und zur Entscheidung vorzulegen.

Bei bereits veröffentlichten Plänen muss die vorhandene Veröffentlichungsaktion verständlich beschriftet werden: Sie kann beispielsweise eine erneute Veröffentlichung auslösen. Ob Änderungen vorliegen oder die Aktion überhaupt notwendig ist, darf die UI ohne vorhandene Daten nicht behaupten. „Live“ und ein undifferenziertes „Publizieren“ erklären diesen Zusammenhang nicht ausreichend.

## 5. Menüeditor vereinfachen

### 5.1 Breite behalten, Arbeit klarer ordnen

Die volle Arbeitsbreite bleibt erhalten. Die Hauptspalte enthält die Bearbeitung, die rechte Spalte den gespeicherten Prüfstand und die bestehenden Prüfhandlungen. Auf kleinen Bildschirmen wird daraus eine nachvollziehbare einspaltige Reihenfolge.

Die Menüidentität wird einmal eindeutig angezeigt: Datum, Mahlzeit und Menüart. Wiederholte Zeilen mit demselben Kontext sind nicht notwendig. Der Rückweg zur gewählten Woche bleibt sichtbar und berücksichtigt ungespeicherte Änderungen.

Sinnvolle Hauptreihenfolge:

1. Menüname und Bausteine;
2. vorhandene Beschreibung und Hinweise mit klar benanntem Anzeigezweck;
3. vorhandene Deklarationsfelder;
4. eine klare Speicheraktion.

Der Anzeigezweck des Hinweisfeldes muss am Bestand geprüft werden. Ein öffentlich ausgegebenes Feld darf nicht als „Interne Notiz“ beschriftet werden. Es werden keine neuen Felder erfunden. Bei anderen Zielbereichen bleiben deren vorhandene Preisfelder erhalten; im Patienteneditor erscheinen keine Preise.

### 5.2 Bausteine: Auswahl statt Warnsatz

Pro Baustein gibt es eine klare Eingabeart:

- **Aus Liste auswählen**;
- **Eigenen Text eingeben**, sofern dieser bestehende Weg vorhanden ist.

Nicht beide Eingabefelder gleichzeitig als gleichwertige Quellen präsentieren und den Konflikt nur durch einen erklärenden Satz auf den Benutzer abwälzen.

Zeige einen bestehenden Baustein kompakt: Name, Änderung und Entfernen; Sortieren bleibt über beschriftete Aktionen ohne Ziehen möglich. Die aktive Bearbeitung einer Zeile darf mehr Platz erhalten. Nicht für jede Zeile gleichzeitig dieselben vier Überschriften, Erklärungen und vollständigen Eingabeblöcke wiederholen.

Die vorhandenen Formularnamen, Werte, Reihenfolge und Serversemantik bleiben unverändert. Beachte, dass ausgeblendete und deaktivierte Controls unterschiedlich übertragen werden können. Ein rein optischer Umbau darf keine Werte verlieren oder veraltete versteckte Werte mitschreiben. Beide bestehenden Eingabearten und ihr unverändertes Speichern sind ausdrücklich zu testen.

### 5.3 Speichern und Prüfen zusammenhängend führen

Im Formular ist **„Menü speichern“** die einzige hervorgehobene Speicheraktion. **„Abbrechen“** ist nachgeordnet. Ein vorhandener zusätzlicher Weg „Speichern und zurück“ darf nur nach bewusster Entscheidung nachgeordnet bestehen bleiben; sein unterschiedlicher Effekt muss verständlich sein. Keine unterstützte Operation versehentlich entfernen oder Redirect-Semantik ändern.

Der rechte Bereich heisst beispielsweise **„Angaben prüfen“**. Er zeigt zunächst verständlich, was im gespeicherten Stand vorhanden oder nicht erfasst ist. Falls passende Felder im Editor vorhanden sind, führen beschriftete Verweise direkt zu diesen Feldern. „Prüfung öffnen“ und „Als geprüft bestätigen“ sind unterschiedliche mögliche Operationen: ihre tatsächlichen Funktionen prüfen und in diesem einen Bereich zusammenhängend anbieten, nicht unbesehen zusammenlegen.

Nach Änderungen an Formularwerten muss klar sein, dass eine vorhandene Prüfung noch nicht diese ungespeicherten Werte betrifft. Kurzer Text: **„Speichere deine Änderungen, bevor du die gespeicherten Angaben prüfst.“** Keine neue kombinierte Speichern-und-Prüfen-Transaktion erfinden.

Ein Erfolgshinweis erscheint nur nach bestätigtem Speichern. Validierungsfehler erhalten Eingaben und Bearbeitungskontext. Interne Navigation mit ungespeicherten Änderungen muss den bestehenden Schutz erhalten bzw. im erlaubten UI-Rahmen nachvollziehbar abgesichert werden.

Die untere Aktionsleiste darf Felder und Tastaturfokus nicht verdecken. Mit geringer Fensterhöhe, Browserzoom und Bildschirmtastatur prüfen. Aus dem Screenshot allein ist ein Überdeckungsfehler nicht bewiesen.

## 6. Gestaltung und Begriffe

| Thema | Vorgabe |
|---|---|
| Seitenrahmen | Volle verfügbare Arbeitsbreite auf allen Bedienseiten; gemeinsame Kanten und Seitenabstände. |
| Hierarchie | Ein klarer Seitenkopf, eine Wochensteuerung, danach Inhalt. Keine zusätzliche Karte um jede Überschrift. |
| Navigation | Die vier Haupteinstiege erhalten. Keine Rückkehr zu einer langen Liste gleichrangiger Verwaltungslinks. |
| Sidebar | Aktiver Eintrag dezent und eindeutig; keine zusätzliche dicke pinke Umrandung einführen. |
| Text | „Veröffentlichen“, „Kennzeichnungen“, „Ausgabeangaben“, „Bausteine“. Technische Fachwörter nicht in den Küchenablauf tragen. |
| Status | Aussage und Geltungsbereich vor Farbe; fehlende Angaben nicht hinter grünem Gesamteindruck verstecken. |
| Tageskopf | Datum und Belegungsinformation sichtbar trennen. Nicht „September4 von 4“ ineinanderlaufen lassen. |
| Schrift und Controls | Bestehende Projektziele für lesbare Schrift und mindestens 44 CSS-Pixel grosse Kernbedienflächen einhalten. |
| Kompaktheit | Durch Weglassen von Wiederholungen und bedarfsgerechte Verwaltung erreichen, nicht durch kleinere Schrift. |

## 7. Technische Schutzgrenzen

Erlaubter Standardumfang: bestehende Jinja-Templates/Partials, projektbezogenes CSS, kleine UI-Ergänzungen im vorhandenen JavaScript-Assetweg, Tests und Dokumentation.

Keine neuen Frameworks, Abhängigkeiten, Datenmodelle, Statuswerte, API-/Schreibrouten oder Formularverträge. Flask, Tabler, Authentifizierung, Berechtigungen, CSRF, Validierung und bestehende Speicher-/Prüf-/Veröffentlichungslogik bleiben erhalten. Python-Änderungen nur nach den bestehenden Projektfreigaben.

Keine produktiven Testveröffentlichungen. Keine neue Diagnose- oder Allergenlogik. Keine ungefragten Änderungen an Druck-, PDF- oder Signage-Ausgaben durch globale Styles.

## 8. Arbeitsreihenfolge

| Paket | Ergebnis |
|---|---|
| U00 | Ist-Dateien, gemeinsame Templates, vorhandene Formulare, Prüfstatus und Ausgabegrenzen ermitteln; Baseline dokumentieren. |
| U01 | Widersprüchliche Statusaussagen aufklären und wahrheitsgetreu darstellen; fachliche Konflikte separat eskalieren. |
| U02 | Doppelte Navigation/Prüfbuttons entfernen, kompakter Kopf und Wochenverwaltung bei Bedarf. |
| U03 | Ausgabeformulare je Mahlzeit bei Bedarf, kompakte Menükarten und vollständige erreichbare Hinweise. |
| U04 | Bausteinbedienung, Speicherführung und zusammenhängender Prüfbereich im Editor. |
| U05 | Responsive Darstellung, Fehlerfälle, bestehende Verträge und tatsächliche Browseransichten prüfen. |

Gemeinsame Styles und Partials haben eine koordinierte Verantwortung. Keine widersprüchlichen Einzelkorrekturen pro Seite. Übertrage passende gemeinsame Muster auch auf die Cafeteria, ohne deren Umfang mit dem Patientenangebot gleichzusetzen.

## 9. Abnahme

| Test | Bestanden, wenn … |
|---|---|
| A01 | Es pro Plan genau eine sichtbare Bereichsauswahl und eine eindeutige Wochen-Prüfaktion gibt. |
| A02 | Bei 1366 × 768 und 1920 × 1080 im regulären Ausgangszustand mindestens der erste Menüeintrag sichtbar ist, ohne Verwaltungsfelder wegscrollen zu müssen. |
| A03 | Alle sieben Tage, beide Mahlzeiten und beide vorhandenen Menüarten vollständig erreichbar sind; Patientenansichten keine Preise enthalten. |
| A04 | Wochen-/Ausgabeformulare bewusst geöffnet werden und bei Validierungsfehlern automatisch mit Eingaben sichtbar bleiben. |
| A05 | Leere Zeiten nicht als Schliessung oder erfundene Standardzeiten dargestellt werden. |
| A06 | Veröffentlichungsstand, gespeicherte Prüfung und fehlende Allergenangaben nicht als dieselbe Aussage erscheinen. Der widersprüchliche Ausgangsfall wird ausdrücklich getestet. |
| A07 | Lange Rezepturhinweise erreichbar bleiben, während fehlende wichtige Angaben schon auf der Menükarte erkennbar sind. |
| A08 | Bei Bausteinen die Eingabeart eindeutig ist und Katalog-/Freitextwerte beim unveränderten Speichern erhalten bleiben. |
| A09 | Hinzufügen, Entfernen und Sortieren ohne Drag-and-Drop möglich bleiben und denselben vorhandenen Schreibweg verwenden. |
| A10 | Speichern, Fehler, Abbrechen und Prüfen jeweils den tatsächlichen Datenstand und ihre unterschiedliche Wirkung erkennbar machen. |
| A11 | Alle angefassten Seiten ihre volle verfügbare Arbeitsbreite behalten. |
| A12 | 768 × 1024, 390 × 844 und 200 % Zoom ohne verdeckte Felder, abgeschnittene Warnungen oder horizontales Seitenscrollen im Kernablauf funktionieren. |
| A13 | Tastaturbedienung und Fokus funktionieren; eine fixierte Aktionsleiste keine Bedienelemente verdeckt. |
| A14 | Diff und Regressionstests keine unerlaubten Vertrags-, Datenmodell-, Sicherheits- oder Ausgabeänderungen zeigen. |

Lieferumfang: tatsächliche Dateipfade, Befund-ID → Änderung → Test → Ergebnis, Browser-Screenshots mit Viewport sowie offene/blockierte Punkte. Mockups sind keine Belege für umgesetzte Funktionalität. Nicht ausgeführte Tests gelten nicht als bestanden.

Ein Test mit technisch unerfahrenen Personen soll insbesondere zeigen, ob sie ein Menü finden, nur die Beilage ändern, speichern und den Unterschied zwischen „geprüft“ und „Allergenangaben fehlen“ erklären können. Ein Agent darf fehlende Nutzerbeobachtungen nicht als durchgeführt ausgeben.

## 10. Umsetzung Zutaten

Die Grundlagenansichten folgen demselben Korrekturmuster: Bereichsauswahl, danach sofort die Liste. Filter und Anlegeformulare
öffnen Mitarbeitende nur bei Bedarf. Auf der Zutatenansicht ist «Zutat speichern» die einzige hervorgehobene Formularaktion;
Archivieren und Reaktivieren stehen unter «Weitere Aktionen». Gespeicherter Aktivstatus, fehlender Lagerort und fehlende
Allergenangaben bleiben als getrennte Aussagen sichtbar. Mindestens ein Lagerort bleibt Pflicht; «Lagerort fehlt» wird nicht
durch einen allgemeinen Prüfstatus verdeckt. Native POST-Ziele, Feldnamen, CSRF-, Kontext- und Versionswerte bleiben unverändert.

**Kernziel: Volle Breite behalten, Wiederholungen entfernen, Menüs zuerst zeigen und Prüfzustände verständlich machen. Nicht erneut nur die Karten grösser machen.**

## Umsetzung Bereiche & Öffnungszeiten

Die Seite `/admin/bereiche-zeiten` zeigt zuerst beide Bereiche mit ihren tatsächlichen
Wochenvorgaben. Aussagen zu Wochenenden und Zeiten nennen ausdrücklich den Geltungsbereich
«für neue Ausgaben». Fehlende Zeiten werden einmal je Bereich erklärt und nicht als
Schliessung oder angebliche Standardzeit dargestellt.

Formulare für Bereichsnamen, Wochenendbetrieb, Wochenvorgaben und datierte Ausnahmen liegen
in nativen `<details>`-Bereichen. Sie bleiben ohne JavaScript bedienbar und öffnen sich beim
betroffenen Validierungsfehler automatisch. Jeder Schreib- oder Ladevorgang behält sein
eigenes Formular und genau eine Hauptaktion; POST-Ziele, Feldnamen, CSRF-Felder und
Versionswerte bleiben unverändert. Gespeicherte Ausnahmen sind als nachgeordnete Ansicht
ebenfalls bei Bedarf erreichbar.

Der Browservertrag `test_ui_korrektur_ops_browser.py` prüft Reihenfolge, genau eine
Shell-Bereichsauswahl, volle Breite, Dokumentüberlauf, Fehlerfokus und Werterhalt sowie die
abgefangenen Formular-Requests mit und ohne JavaScript. Screenshotbelege decken 1366×768,
1920×1080, 768×1024, 390×844 und den effektiven 200-%-Viewport sowie Leer- und Fehlerzustand
ab.

## Umsetzung Menüsammlung/Wochenübersicht

Im Rahmen des Arbeitspakets `wp-ui-korrektur-menus-0912` (Lane `antigravity-agy`) wurden die Grundsätze P01–P10 auf die beiden Übersichtsseiten **Menüsammlung** (`menu_collection.html`) und **Wochenübersicht** (`week_management.html`) übertragen:

### 1. Bestandsaufnahme & Bereinigung
- **Doppelte Navigation (P01):** Auf der Wochenübersicht wurde die zusätzliche, frei im Inhaltsbereich stehende Bereichszeile entfernt und stattdessen direkt als profilbezogener Umschalter im Kopfbereich der Wochenliste (`card-header`) verankert.
- **Hauptaufgabe zuerst (P03):** Die Menüsammlung bietet eine kompakte Toolbar (Bereichstabs, Suche, Karten/Listen-Toggle). Erste Menükarten bzw. die erste gespeicherte Woche sind bei Standard-Desktop (1366 × 768) ohne vertikales Scrollen sofort im Blickfeld.
- **Wahrheitsgetreue Statusdifferenzierung (P05):** Veröffentlichungsstatus (`live`, `changed`, `ready`), gespeicherte Prüfung (`Geprüft · gespeicherter Stand bestätigt`, `Prüfung offen`) und Allergenvollständigkeit (`Allergenangaben nicht erfasst`) werden nie vermischt oder als dieselbe Aussage dargestellt.
- **Lange Hinweise gebündelt (P06):** Freitexte aus `note` und `description` dominieren die Karten nicht mehr unkontrolliert; sie stehen vollständig und ungekürzt unter einem nativen `<details>`-Block («Hinweis anzeigen»). Fehlende Deklarationen («Allergenangaben nicht erfasst») verbleiben zwingend ausserhalb der Einklappung direkt sichtbar auf der Karte.
- **Aktionshierarchie (P09):** Jede Menükarte besitzt genau eine sichtbare Hauptaktion («Öffnen»). In der Wochenübersicht ist «Woche öffnen» als primärer Button (`btn-primary`) hervorgehoben; Nebenaktionen («Vorschau», «In Folgewoche kopieren») sind gruppiert.
- **Sprachliche Klarheit (P10):** Technische Begriffe wurden durch verständliche Formulierungen («Veröffentlichen», «Ausgabeangaben») ersetzt.

### 2. Statusdarstellung Wochenübersicht (`derive_admin_status`)
Die Statusspalte der Wochenliste nutzt konsistent die vertragliche Klartext-Matrix:
- `live` → «Veröffentlicht · entspricht dem gespeicherten Stand»
- `changed` → «Veröffentlicht · gespeicherte Änderungen noch nicht veröffentlicht»
- `ready` → «Noch nicht veröffentlicht · bereit»
- `review_open` → «Prüfung offen»
- `incomplete` → «Unvollständig»
- `empty` → «Noch keine Menüs erfasst»

### 3. Technische Schutzgrenzen
- Volle Arbeitsbreite (`data-layout="standard"`) bleibt ohne Breitenbegrenzung auf allen Displaygrössen erhalten.
- Alle CSS-Stile in `admin-menu-collection.css` nutzen ausschliesslich Tokens aus `tokens.css` (keine harten Hex-Werte, keine ungemappten Klassen).
- Sämtliche POST-Ziele, Formularfelder, Hidden-Inputs (`_csrf`, `row_version`), Filterparameter (`q`, `page`) und Redirect-Routen bleiben unberührt.
- Browser-Verifikation via `test_ui_korrektur_menus_browser.py` erbringt Screenshots für 1366×768, 1920×1080, 768×1024, 390×844 sowie 200 % Zoom ohne horizontales Scrollen.

## Umsetzung Bausteine (wp-ui-korrektur-components-0912)

| Befund | Änderung | Test |
|---|---|---|
| P03/P08 | Liste: kompakte Filterzeile zuerst, Ergebnisliste direkt darunter, «Baustein anlegen» als eingeklappter Bereich am Ende | `test_ui_korrektur_components_browser.py::test_list_first_row_visible_without_scroll` |
| P08/P10 | Pro Zeile eine «Bearbeiten»-Aktion; Name ohne Doppel-Link; Kennzeichnungen kompakt | `test_component_catalog_browser.py` |
| P09 | Editor: «Baustein speichern» als Primäraktion, «Abbrechen» nachgeordnet; Archivieren/Reaktivieren separat unten | `test_component_catalog_browser.py` |
| P05/P10 | Status/Verwendung/Gültigkeit getrennt mit Geltungsbereich-Hinweisen für Allergenfilter und Katalogangaben | `test_component_filters_browser.py` |
| P10 | UI-Wörter «Bausteine» statt «Komponenten» auf den beiden Seiten | Browser-Tests in Besitz |
| A11/A12 | Volle Breite, Viewports 1366×768 … 390×844 und 200 % ohne horizontales Scrollen | `test_ui_korrektur_components_browser.py` |

Screenshotnachweise: `.claude/evidence/ui-korrektur-0912/components/`.

## Umsetzung Kochbücher

Die Kochbuchliste zeigt Suche und vorhandene Kochbücher vor der optionalen
Neuanlage. «Kochbuch anlegen» bleibt für Schreibberechtigte unter einem
geschlossenen `<details>` erreichbar. Die frühere Symbollegende entfällt, weil
alle verbleibenden Handlungen direkt beschriftet sind.

Im aktiven Editor ist «Kochbuch speichern» die einzige hervorgehobene
Seitenaktion. Die weiterhin getrennte Rezept-Zuordnung besitzt die sekundäre
Abschnittsaktion «Zuordnung speichern». Rezeptauswahl und Positionszahlen bleiben
unverändert; Sortieren funktioniert weiterhin ohne Drag-and-Drop.

Beide Formulare behalten ihre bisherigen POST-Ziele, CSRF-/Kontextfelder,
`row_version` und fachlichen Nutzfelder. Der Browservertrag
`tests/test_ui_korrektur_cookbooks_browser.py` prüft beide Payloads mit und ohne
JavaScript sowie volle Breite und fehlenden Seitenüberlauf bei 1366×768,
1920×1080, 768×1024, 390×844 und dem 200-%-Äquivalent 720×450.

## Umsetzung Erscheinungsbild

Der Editor für das Erscheinungsbild folgt derselben Aktionshierarchie: «Entwurf speichern & Vorschau» ist die einzige hervorgehobene Hauptaktion. Die Aktivierung steht nachgelagert im Abschnitt «Veröffentlichte Version» und bezieht sich ausdrücklich auf den ausgewählten gespeicherten Stand. Aktive Version, ausgewählter Stand, Entwurf und Änderungszeit werden getrennt benannt.

Versionsauswahl, Übernahme eines früheren Stands und Standardentwurf stehen unter «Weitere Aktionen». Vorhandene POST-Ziele, Payloads, CSRF-, Versions-, Upload-, Aktivierungs-, Wiederherstellungs- und Zurücksetzungsverträge bleiben unverändert und ohne JavaScript bedienbar. Editor und eigenständige Vorschau verwenden die volle verfügbare Breite; die Vorschau enthält keine Attrappen-Schaltfläche.

## Umsetzung Werkzeuge

Die Korrekturwelle umfasst auch vier vorhandene Werkzeugseiten, ohne ihre Routen,
Formularfelder oder Schreiblogik zu ändern:

| Seite | Umgesetzte Ordnung |
|---|---|
| Schnittstellen | API-Schlüssel stehen zuerst. Das Anlegeformular ist bei Bedarf erreichbar und öffnet bei einem Fehler automatisch. Status und technische Endpunkte bleiben nachgeordnet sichtbar. |
| Daten importieren | Leerer Zustand, fehlerhafte Datei und gültige Import-Vorschau zeigen jeweils die nächste tatsächliche Aufgabe. Erst die Bestätigung der gültigen Vorschau übernimmt den Entwurf. |
| Vorwoche kopieren | Quelle und Ziel stehen getrennt. Der Hinweis nennt nur belegte Wirkungen: Wochenkopf, Ausgabeangaben und Menüs werden übernommen, Prüfbestätigungen nicht; die Zielwoche bleibt ein Entwurf, muss leer sein und darf keine aktive Veröffentlichung haben. |
| Wochenprüfung | Prüfstatus steht vor Erklärung und gespeicherten Angaben. Oberflächentexte verwenden «Ausgabeangaben»; das vorhandene Bestätigungsformular bleibt unverändert. |

Browsernachweis und responsive Screenshots entstehen durch
`reference_scaffold/tests/test_ui_korrektur_tools_browser.py` unter
`.claude/evidence/ui-korrektur-0912/tools/`. Die Matrix umfasst 1366×768,
1920×1080, 768×1024, 390×844 und 720×450 als 200-%-Zoomäquivalent.

## Umsetzung Bildschirme & Darstellung

Die Bildschirmübersicht verwendet eine Bereichsauswahl und zeigt je Ausgabe zuerst ihren belegbaren Geltungsbereich. Für Web-Wochenpläne stammt die aktive Vorlage aus `assignments[profile]`; Bildschirmausgaben zeigen den aktuell veröffentlichten Stand. Angaben wie «verbunden» oder «zuletzt gesehen» fehlen, weil die Routen dafür keine Template-Variablen liefern.

Die aktive Web-Wochenvorlage steht vor dem Zuweisungsformular. «Vorlage zuweisen» öffnet das unveränderte signierte Formular bei Bedarf; Konflikt- und Validierungsantworten öffnen den Bereich, erhalten alle sechs Payload-Felder und fokussieren die Fehlerregion. Tagespläne, Bildschirmausgaben und die feste Adresse ohne Bilder bleiben ausserhalb dieser Zuordnung.

Die Darstellungsseite zeigt ihre vier globalen Einstellungen zuerst. `save` bleibt einzige hervorgehobene Hauptaktion; `preview` und `reset` stehen zusammen unter «Weitere Aktionen». Werte und Wirkung von `data-density`, `data-font-size`, `data-content-width` und `data-menu-images` bleiben unverändert. Browserprüfungen decken 1366×768, 1920×1080, 768×1024, 390×844 und 200 Prozent ohne horizontalen Dokumentüberlauf ab.

## 10. Umsetzung Benutzer & Zugriff

Die Benutzerverwaltung überträgt P01–P10 ohne Änderung der IAM-Verträge: Die Kontenliste bleibt Hauptinhalt, das Anlegen eines lokalen Kontos liegt in einem nativen, bei Bedarf geöffneten `<details>`-Bereich. Die eigene Anlegeseite öffnet denselben Bereich; nach Validierungsfehlern bleibt er offen, Textwerte bleiben erhalten und Passwortfelder werden leer neu ausgegeben.

Auf der Kontoseite sind Kontostatus, vorübergehende Sperre, letzte lokale Passwortprüfung und letzter Passwortwechsel mit ihrem jeweiligen Geltungsbereich getrennt. Rollen, Passwort und Aktivierung oder Deaktivierung bleiben eigenständige Formulare mit unveränderten Zielen, Feldnamen, Versionswerten, CSRF-Schutz und ausdrücklichen Bestätigungen. Sie werden als drei klar benannte Bedarfsbereiche dargestellt; nur der fehlerhafte Bereich öffnet automatisch.

Kontoereignisse und Zugriffsverlauf bleiben getrennte Lesesichten. Wiederholte Einleitungstexte wurden in die jeweilige Tabellenüberschrift zusammengezogen. Der Zugriffsverlauf nennt weiterhin ausdrücklich seine Beweisgrenze: Ein protokollierter Entscheid belegt weder eine aktive Sitzung noch eine abgeschlossene Abmeldung.

## Umsetzung Menüeditor

Stand 12. September 2026, WP `wp-ui-korrektur-editor-0912`:

- P07/P08: Bestehende Bausteine erscheinen mit JavaScript als kompakte Zeilen. „Ändern“ öffnet die Bearbeitung; die namenlosen Schalter „Aus Liste auswählen“ und „Eigenen Text eingeben“ zeigen genau ein Eingabefeld und leeren beim Wechsel den anderen Wert. Ohne JavaScript bleiben beide bisherigen Felder sichtbar und nutzbar.
- P09: „Menü speichern“ ist die einzige hervorgehobene Aktion. „Speichern und zum Wochenplan“ behält seinen bestehenden `return_to=week`-Schreibweg. Prüfung, Änderungslinks, Datenlücken und Bestätigung des gespeicherten Stands stehen zusammen im Bereich „Angaben prüfen“; ungespeicherte Änderungen heben den Hinweis dort hervor.
- P10/U05: Menüname, Bausteine, öffentliche Texte und Kennzeichnungen folgen einer eindeutigen Reihenfolge. Das Standardlayout nutzt die volle Arbeitsbreite. Tablet-/Mobilansicht und geringe Höhe setzen die Aktionsleiste in den Dokumentfluss, damit Felder und Fokus nicht verdeckt werden.
- Formularvertrag: Namen, Reihenfolge, CSRF, Versionsfelder, POST-Ziele und Prüfroute bleiben unverändert. Katalog- und Freitextwerte werden weiterhin als geordnete Paare übertragen; versteckte Controls werden nicht deaktiviert.
- Browserbelege: `.claude/evidence/ui-korrektur-0912/editor/` enthält reguläre Ansichten für 1366×768, 1920×1080, 768×1024, 390×844 und 200 % sowie Fehler-, Herkunftskonflikt- und No-JS-Zustand.
- Gemeinsamer Scope-Gate: 10 Testdateien zusammen über `worker-test_sdd-gate.sh`; Ergebnis `183 passed, 8 skipped` in 442,12 Sekunden.

Nicht durchgeführt: Beobachtungstest mit technisch unerfahrenen Küchenmitarbeitenden. Die Screenshots sind Implementierungsbelege, keine freigegebenen visuellen Baselines.
