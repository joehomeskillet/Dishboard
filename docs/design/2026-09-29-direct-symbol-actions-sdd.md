# SDD: Direkte Symbolaktionen in der gesamten Dishboard-App

**Kennung:** UI-DIRECT-ACTIONS-2026-09-29  
**Stand:** 29. September 2026  
**Art:** Verbindlicher Korrekturauftrag für die laufende Implementierungs-/`/goal`-Session  
**Geltung:** Bestehende und zukünftige Verwaltungsoberflächen der gesamten App  
**Technischer Rahmen:** Bestehende Flask-/Jinja-/Tabler-Architektur und vorhandenes semantisches Icon-System weiterverwenden  
**Status dieses Dokuments:** Spezifikation. Keine durch dieses Dokument bereits erfolgte Implementierung, Veröffentlichung oder Browserabnahme.

> Alle für den aktuellen Benutzer und Datensatz verfügbaren Aktionen müssen direkt als kompakte, einheitliche Symbole sichtbar sein. Keine vorgeschalteten Drei-Punkte-Menüs, keine aufklappenden Aktionslisten und keine künstlich vergrösserten Tabellenzeilen. Einfachheit entsteht durch konsistente Gestaltung, nicht durch das Verstecken von Funktionen.

---

## 0. Direkter Auftrag an die laufende Session

Übernimm diese SDD als Ergänzung und Korrektur des laufenden UI-Polish-Auftrags. Setze sie im bestehenden Projekt um; beginne kein neues Projekt und liefere nicht lediglich einen weiteren Designvorschlag.

Die Rezeptliste ist der reproduzierbare Ausgangsfall, **nicht die Begrenzung des Auftrags**. Korrigiere die gemeinsame Komponentenlogik, alle entsprechenden Sonderimplementierungen und die zugehörigen Design- und Testverträge. Prüfe danach die tatsächlich betroffenen Oberflächen im Browser.

Diese Entscheidung ersetzt ausdrücklich ältere Regeln wie „nur die wichtigste Aktion direkt“, „maximal ein oder zwei Aktionen pro Zeile“ und „seltene Aktionen ins Overflow-Menü“. Solche Regeln dürfen weder im neuen Renderer noch in Manifesten, Agentenanweisungen, Tests oder neuen Seiten weiter als Standard gelten. Andere Vorgaben bleiben erhalten: volle Arbeitsbreite, kompakte Darstellung, verständliche Bedienung, einheitliche Symbole, Zugänglichkeit und funktionale Sicherheit.

**Nicht als Lösung akzeptiert:** nur die Dropdown-Position korrigieren, die aufgeklappte Liste hübscher gestalten, das Mehr-Menü standardmässig öffnen, weitere Aktionen ausschliesslich bei Hover zeigen oder die ausgeblendeten Funktionen ersatzlos entfernen.

## 1. Ausgangslage und nachgewiesene Ansatzpunkte

### 1.1 Beobachtung aus den mitgelieferten Screenshots

Die Liste unter `/admin/rezepte` zeigt zunächst Bearbeiten und „…“. Nach dem Öffnen des Aktionsbereichs erscheinen Öffnen, PDF öffnen und Verlauf untereinander als breite Textbuttons. Darunter steht die Vorlageninformation beziehungsweise der Einstieg zum Anlegen einer Vorlage. Dadurch wird die einzelne Rezeptzeile deutlich höher als die benachbarten Zeilen. Der Aktionsbereich dominiert den Datensatz, obwohl die verfügbare Desktopbreite eine kompakte Symbolreihe zulässt.

Die beiden Referenzbilder dokumentieren denselben problematischen IST-Zustand, einmal geschlossen und einmal geöffnet. Sie sind **keine Zielbilder**.

### 1.2 Codebefund aus der Repository-Einsicht

Die folgenden Dateien wurden für diese Spezifikation über GitHub eingesehen. Die Einsicht belegt den jeweiligen Repository-Inhalt, nicht die Identität mit einem bestimmten produktiv laufenden Deployment.

| Quelle | Befund | Konsequenz für die Umsetzung |
|---|---|---|
| `reference_scaffold/cafeteria/templates/ui/_semantic.html` | `row_actions(items, object=none)` rendert das erste Element direkt und übergibt weitere Elemente an `more_actions`. `more_actions` erzeugt `details.ui-sem-actions`; `action_menu` delegiert darauf. | Zentrale Renderregel ändern, nicht lediglich einzelne Seiten nachstylen. |
| `reference_scaffold/cafeteria/templates/admin/rezepte.html` | Die Rezeptliste verwendet zusätzlich einen eigenen `details`-Block mit `actions.more`, `ui-sem-action-items` und mehreren Aufrufen mit `show_text=true`. | Auch diese handgeschriebene Variante auf den gemeinsamen Direktaktionsvertrag migrieren. |
| `reference_scaffold/cafeteria/static/ui-semantic.css` | `.ui-sem-action-items` wird als Spalte mit gestreckten Elementen angeordnet. Der geschlossene Zustand wird ausdrücklich ausgeblendet. | Der neue Aktionsstreifen darf kein aufgeklappter Bereich im normalen Zeilenlayout sein. |
| `reference_scaffold/cafeteria/templates/ui/_semantic.html` | Bei `icon_button` steuert im eingesehenen Stand `show_text` die sichtbare Beschriftung; `icon_only` bleibt aus Kompatibilitätsgründen erhalten. | Nicht annehmen, dass `icon_only=true` ein vorhandenes `show_text=true` neutralisiert. |

Zusätzliche Suchtreffer zeigen das Muster unter anderem in `kochbuecher.html`, `api.html`, `rezepte_ansicht.html`, `_week_menu_card.html`, `_week_controls.html` und `_rezepte_fields.html` sowie in Browsertests. Dies sind **Audit-Startpunkte, keine vollständige App-Inventur**.

Besonders zu beachten: `_rezepte_fields.html` besitzt einen eigenen Helper namens `row_actions` mit anderer Signatur. Namensgleichheit bedeutet nicht, dass bereits der gemeinsame Renderer verwendet wird.

## 2. App-weiter Geltungsbereich

### 2.1 Zu migrierende Oberflächen

Der Auftrag umfasst sämtliche administrativen Listen, Tabellen, wiederholten Karten, eingebetteten Zeilen und Aktionsgruppen, die verfügbare Befehle hinter einem generischen Mehr-Zugang verstecken.

| Oberflächengruppe | Zu prüfende Beispiele | Verbindliches Ergebnis |
|---|---|---|
| Stammdaten und Inhalte | Menüs, Bausteine, Zutaten, Rezepte, Kochbücher, Gerichtvorlagen | Gleicher Direktaktionsvertrag je Datensatz. |
| Planung | Wochenplan, Karten und Slots, vorhandene Planungsübersichten | Verfügbare Objekt- und Planaktionen direkt sichtbar; bestehende fachliche Anordnung erhalten. |
| Eingebettete Editorlisten | Zutaten, Zubereitungsschritte und andere wiederholte Formularzeilen | Einfügen, Verschieben und Entfernen nicht hinter „…“ verstecken. |
| Operative Verwaltung | Einkaufslisten, Bestellungen, Lager und weitere tatsächlich vorhandene Bereiche | Dieselbe Symbolsemantik und dieselbe Komponentenfamilie. |
| Technische Administration | Beispielsweise API-Schlüssel und weitere vorhandene Verwaltungslisten | Direkte Aktionen unter Beibehaltung der Berechtigungen und Sicherheitsabfragen. |
| Detailseiten und Formulare | Objektkopf, Seitenwerkzeuge und Formularfuss | Vorhandene Befehle nicht weiter in generischen Mehr-Aktionsmenüs verstecken. |

Die Aufzählung ist ein Mindestprüfumfang. Ermittle vorhandene Routen und Oberflächen aus dem aktuellen Arbeitsstand. Erfinde weder Routen noch Module, um die Tabelle zu vervollständigen.

### 2.2 Was ausdrücklich nicht pauschal entfernt wird

> **Abgelöst durch UI-DELTA-2026-10-01 §0.1 (D):** Die Ausnahme für fachliche Akkordeons und Inhaltsaufklapper gilt nicht mehr; diese dürfen nicht im Dokumentfluss aufklappen. — siehe [UI-DELTA](2026-10-01-ui-delta-sdd.md).

Navigationsuntermenüs, echte Auswahllisten, Filterpanels, fachliche Akkordeons und Detailabschnitte dürfen bestehen bleiben. Sie sind kein generisches Versteck für bereits verfügbare Befehle. Ein Dialog für ein Formular, eine Vorschau oder eine Sicherheitsbestätigung ist ebenfalls zulässig. Ein Dialog, der nach Klick auf „…“ lediglich dieselbe Aktionsliste anzeigt, ist nicht zulässig.

Fachliche Inhalte bleiben lesbar: Namen, Mengen, Formularlabels, Warnungen, Allergene, Statusinformationen und Bestätigungstexte werden nicht blind in Symbole verwandelt. Öffentliche Website- und Signage-Ansichten erhalten keine neuen Verwaltungsaktionen.

## 3. Verbindlicher Interaktionsvertrag

### 3.1 Direkte Sichtbarkeit

Jede aktuell verfügbare Aktion erhält einen eigenen sichtbaren, unmittelbar erreichbaren Auslöser. Die Verfügbarkeit richtet sich nach Rolle, Objektzustand und bestehenden fachlichen Regeln, **nicht nach einer willkürlichen Höchstzahl sichtbarer Buttons**.

Verboten sind Drei-Punkte-Auslöser, „Mehr“, „Weitere Aktionen“, ein ersatzweises Zahnrad als Aktionssammler, Hover-only-Buttons, Swipe-only-Aktionen und Aufklappmechanismen, die erst die eigentlichen Befehle zugänglich machen. Ein Kontextmenü darf allenfalls zusätzliche Bedienung anbieten, niemals der einzige Zugang sein.

„Direkt“ bedeutet: Der erste Klick auf das entsprechende Symbol führt zum fachlichen Ziel oder startet den notwendigen Fach-/Bestätigungsdialog. Es bedeutet nicht, dass Löschen, Widerrufen oder Veröffentlichen ohne die vorhandenen Schutzschritte ausgeführt werden sollen.

### 3.2 Keine erfundenen und keine doppelten Aktionen

Zeige ausschliesslich Funktionen, die tatsächlich vorhanden und im Kontext sinnvoll sind. Keine zusätzlichen Kopier-, Export-, Lösch- oder Archivierungsbuttons nur deshalb ergänzen, weil das Design Platz bietet.

Identische Befehle mit identischem Ziel und identischer Wirkung erscheinen pro Aktionsgruppe nur einmal. Unterschiedliche Bedeutungen dürfen nicht allein wegen ähnlicher URLs zusammengelegt werden. Beispielsweise können Verlauf öffnen und zu „Stand festhalten“ springen dieselbe Seite, aber unterschiedliche fachliche Ziele haben.

### 3.3 Reihenfolge und Wiedererkennbarkeit

Die semantische Reihenfolge ist über die App hinweg stabil. Nicht vorhandene Kategorien entfallen; die verbleibenden Aktionen behalten ihre relative Reihenfolge.

| Reihenfolge | Kategorie | Beispiele, nur soweit vorhanden |
|---:|---|---|
| 1 | Öffnen / Ansehen | Objekt öffnen, eigenständige Vorschau |
| 2 | Bearbeiten | Objekt bearbeiten |
| 3 | Ausgabe | PDF öffnen, tatsächlich drucken, Export |
| 4 | Verlauf und Versionen | Verlauf, vorhandener Einstieg zum Festhalten eines Stands |
| 5 | Zuordnung und Ableitung | Zugeordnete Vorlage öffnen, Vorlage anlegen, kopieren |
| 6 | Kontextbezogene Arbeitsbefehle | Vorhandene Prüf-, Planungs- oder Statusaktionen |
| 7 | Entfernende / sensible Aktionen | Archivieren, widerrufen, löschen |

Verwende bestehende semantische Schlüssel. Ein neuer Schlüssel ist nur nötig, wenn eine vorhandene Bedeutung tatsächlich fehlt oder bisher falsch abgebildet wurde. Gleiche Bedeutung bedeutet gleiches Symbol, gleichen Tooltipaufbau und gleiche Behandlung in allen Modulen.

### 3.4 Berechtigungen und Verfügbarkeit

| Situation | Darstellung | Verhalten |
|---|---|---|
| Berechtigt und fachlich ausführbar | Direktes, aktives Symbol | Bestehende Aktion unverändert starten. |
| Nicht berechtigt | Aktion nicht rendern | Keine lediglich per CSS versteckte Möglichkeit; serverseitige Prüfung bleibt. |
| Vorübergehend nicht ausführbar, aber fachlich relevant | Deaktiviertes Symbol mit zugänglicher Begründung | Keine Navigation, kein Submit und keine Datenänderung. |
| Für diesen Objekttyp nicht vorhanden | Kein Symbol | Keine erfundene Funktion und kein dekorativer Platzhalter. |
| Aktion läuft | Auslöser mit gleichbleibender Geometrie im Ladezustand | Mehrfachauslösung verhindern; Ergebnis verständlich zurückmelden. |
| Keine Aktionen vorhanden | Kein leerer Buttonstreifen | Keine sinnlosen Leerflächen erzeugen. |

Innerhalb einer homogenen Liste sollen gemeinsame Aktionspositionen möglichst stabil bleiben. Dafür nicht vorsorglich Dutzende leere Slots reservieren. Zustandsbedingt deaktivierte Symbole und eine einheitliche Reihenfolge sind einem unnötig breiten Universalraster vorzuziehen.

## 4. Visueller Vertrag: ruhig, kompakt und direkt

### 4.1 Symbolbuttons

Alle Zeilenaktionen verwenden denselben Renderer und dieselben Designtokens. Standardaktionen erhalten eine zurückhaltende Outline-/Ghost-Darstellung passend zum bestehenden Tabler-Design. Nicht jeder Button bekommt eine eigene Akzentfarbe oder einen kräftigen Rahmen. Hover, Tastaturfokus und aktive Zustände bleiben klar erkennbar.

In gewöhnlichen Zeilenaktionen gibt es keine dauerhaften langen Beschriftungen. Der verständliche Name bleibt im Tooltip und im zugänglichen Namen erhalten. Sicherheitsdialoge und notwendige Konsequenztexte dürfen und sollen dagegen verständlichen sichtbaren Text enthalten.

Keine Emojis, keine gemischten Icon-Familien, keine unterschiedlichen Strichstärken und keine auf einzelnen Seiten improvisierten SVGs. Das vorhandene lokale Tabler-Sprite und die semantische Registry bleiben die Grundlage.

### 4.2 Geometrie als gemeinsame Designziele

Die folgenden Werte sind Projektziele, keine Behauptung über bereits vorhandene Styles. Prüfe die vorhandenen Tokens und führe die Werte konsistent zusammen. Grössere notwendige Bedienflächen nicht blind verkleinern.

| Eigenschaft | Desktop / präziser Zeiger | Touch / kleiner Bildschirm |
|---|---:|---:|
| Bedienfläche pro Symbol | Ziel 36 × 36 CSS-Pixel | Mindestens 44 × 44 CSS-Pixel |
| Sichtbares Icon | Einheitlich etwa 18–20 CSS-Pixel | Etwa 20 CSS-Pixel innerhalb der grösseren Bedienfläche |
| Abstand zwischen Aktionen | Ziel 4 CSS-Pixel | Ziel 6 CSS-Pixel |
| Einfache Datenzeile | Ziel etwa 52 CSS-Pixel | Inhaltsabhängig, nicht auf 52 Pixel festklemmen |
| Position | Am logischen Zeilenende, vertikal zentriert | Eigene sichtbare Aktionszeile, falls nötig |

Rechenbeispiel für fünf Desktopaktionen: `5 × 36 + 4 × 4 = 196` CSS-Pixel reine Symbolleiste. Mit zusammen 32 Pixel Zellinnenabstand ergibt sich ein Platzbedarf von etwa 228 Pixel. Diese Breite wird nicht blind jeder Tabelle aufgezwungen; sie zeigt aber, dass fünf Symbole keine aufgeklappte Textspalte benötigen.

### 4.3 Tabellen und Platznutzung

Die Tabelle nutzt weiterhin die gesamte verfügbare Arbeitsbreite. Die Aktionsspalte bekommt den notwendigen Platz, aber keinen unverhältnismässig grossen Anteil der Tabelle. Namen und Fachinformationen behalten den übrigen Raum.

Aktionskopf und Aktionsgruppe sind konsistent am logischen Ende ausgerichtet. Buttons werden nicht auf volle Zellbreite gestreckt. Hinweise, Folgenbeschreibungen und Vorlageninformationen werden nicht als zusätzliche Textblöcke unter die Symbolreihe gestapelt.

Eine Desktopzeile mit einzeiligem Inhalt bleibt kompakt. Eine Zeile mit langem Namen, Warnung oder mehrzeiligem Fachinhalt darf wachsen. Kein fixes `height` zusammen mit Abschneiden des Inhalts. Hover, Fokus und Tooltips dürfen die Zeilenhöhe nicht verändern.

### 4.4 Responsive Verhalten ohne erneutes Verstecken

Bei ausreichender tatsächlicher Komponentenbreite stehen die Aktionen in einer Reihe. Entscheidend ist die verfügbare Breite, nicht allein die Bildschirmklasse: Auch eine Karte auf einem grossen Bildschirm kann schmal sein.

Reicht der Platz nicht, erhält der Datensatz eine weiterhin sichtbare Aktionszeile unter den Kerninformationen. Die Symbole dürfen dort geordnet umbrechen. Bei sehr vielen tatsächlich notwendigen Aktionen sind weitere kompakte Symbolreihen zulässig; eine lange vertikale Liste breiter Textbuttons ist es nicht.

Es gibt keine mobile Rückkehr zum Drei-Punkte-Menü. Keine Aktionen verschwinden hinter horizontalem Scrollen, werden abgeschnitten oder zur Platzrettung unter die vereinbarte Bediengrösse verkleinert. Fachlich notwendige breite Tabellen dürfen separat scrollen; der Zugang zu den Aktionen darf dadurch nicht ausschliesslich ausserhalb des sichtbaren Bereichs liegen.

## 5. ASCII-Zielbilder

Die Bezeichner in eckigen Klammern stehen **für Icons**. Sie sind maschinenlesbare Platzhalter, keine sichtbaren Buchstabenbuttons und keine endgültigen SVG-Namen.

### 5.1 Rezeptliste: alle Aktionen unmittelbar sichtbar

```text
REZEPTE                                                             [ADD]
[ Suchen ........................................ ] [SEARCH] [FILTER]

NAME                         AUSBEUTE      ZUSTAND              AKTIONEN
------------------------------------------------------------------------
Apfelmus                     1600 g             [OPEN][EDIT][PDF][HIST][T+]
Basmatireis                   2800 g             [OPEN][EDIT][PDF][HIST][T+]
Blattsalat                    900 g             [OPEN][EDIT][PDF][HIST][T>]
Bohnen                       1500 g             [OPEN][EDIT][PDF][HIST][T>]
------------------------------------------------------------------------
```

`OPEN` = Öffnen; `EDIT` = Bearbeiten; `PDF` = PDF öffnen; `HIST` = Verlauf; `T+` = Gerichtvorlage anlegen; `T>` = vorhandene Gerichtvorlage öffnen. Die konkreten Aktionen hängen von Rechten, Zustand und vorhandenen Verknüpfungen ab.

### 5.2 Mobile Darstellung: kein Mehr-Menü

```text
+------------------------------------------+
| Apfelmus                                 |
| 1600 g                                   |
|                                          |
| [OPEN] [EDIT] [PDF] [HIST] [T+]            |
+------------------------------------------+
| Basmatireis                              |
| 2800 g                                   |
|                                          |
| [OPEN] [EDIT] [PDF] [HIST] [T+]            |
+------------------------------------------+
```

Die Leerzeile illustriert nur die Trennung von Daten und Aktionen; kein zusätzlicher hoher Leerraum ist zu implementieren.

### 5.3 Schmale Karte mit vielen vorhandenen Aktionen

```text
+----------------------------------+
| Objektname                       |
| Menge / Status                   |
| [OPEN] [EDIT] [PDF] [HIST]         |
| [LINK] [COPY] [ARCHIVE] [DELETE]   |
+----------------------------------+
```

Alle acht Symbole bleiben sichtbar. Diese Beispielaktionen dürfen nicht pauschal Objekten hinzugefügt werden, die sie bisher nicht anbieten.

### 5.4 Fehlende Voraussetzung statt doppeltem Verlauf

```text
Apfelmus   1600 g   [OPEN][EDIT][PDF-off][HIST][SNAP+][T+]

PDF-off : Noch kein gespeicherter Stand vorhanden.
SNAP+   : Vorhandenen Einstieg zu "Stand festhalten" oeffnen,
          nur soweit diese Funktion im Kontext bereits verfuegbar ist.
```

Die Erklärungen gehören zur Spezifikation. Im regulären Zeilenlayout stehen dort keine mehrzeiligen Hilfetexte.

### 5.5 Zutaten und Arbeitsschritte im Editor

```text
ZUTAT                         MENGE       EINHEIT               AKTIONEN
------------------------------------------------------------------------
Apfel                         [1600]      [g]            [INSERT][UP][DN][X]
Wasser                        [ 200]      [ml]           [INSERT][UP][DN][X]
------------------------------------------------------------------------
```

Erste und letzte Position erhalten passende deaktivierte Verschiebeaktionen. Vorhandene Einfüge-, Formular- und Validierungsregeln bleiben erhalten. Nicht vorhandene Befehle werden nicht ergänzt.

### 5.6 Objektkopf und Sicherheitsdialog

```text
REZEPT: APFELMUS             [BACK] [EDIT] [PDF] [HIST] [ARCHIVE]

Klick auf ARCHIVE, sofern Bestaetigung erforderlich:
+---------------------------------------------------+
| Rezept archivieren?                               |
| Apfelmus wird ...                                  |
| Konkrete, vorhandene Folgen verstaendlich erklaeren.|
|                         [Abbrechen] [Archivieren]  |
+---------------------------------------------------+
```

Der Archivierungszugang ist direkt. Die Sicherheitsbestätigung bleibt explizit und lesbar.

## 6. Fachlich korrekte Migration der Rezeptliste

### 6.1 Öffnen und Bearbeiten

Öffnen und Bearbeiten sind getrennte Befehle mit getrennten Zielen. Für schreibberechtigte Benutzer dürfen beide direkt sichtbar sein. Für reine Leser bleibt Öffnen, während Bearbeiten entsprechend den vorhandenen Regeln entfällt. Archivierte Objekte erhalten keine plötzlich neu erlaubte Bearbeitung.

Die derzeit verwendeten Rechtebedingungen, insbesondere `can_write`, `item.active` und `can_create_template`, müssen bei der Migration erhalten beziehungsweise aus den bestehenden zuständigen Helpers übernommen werden.

### 6.2 PDF ist nicht automatisch Drucken

Der vorhandene Rezeptlink führt im eingesehenen Template zum PDF eines gespeicherten Stands. Das sichtbare beziehungsweise zugängliche Wording lautet entsprechend „PDF öffnen“. Verwende dafür ein eindeutig passendes Dokument-/PDF-Symbol, nicht pauschal ein Druckersymbol.

Prüfe zuerst die vorhandene Registry. Fehlt eine passende Semantik, ergänze genau den benötigten PDF-Öffnen-Schlüssel inklusive Übersetzungen und Sprite-Prüfung. **Nicht** `actions.print` global auf ein PDF-Symbol umbiegen, wenn andere Stellen damit tatsächlich drucken. Die Funktion, Auswahl des gespeicherten Stands und Zielroute bleiben unverändert.

### 6.3 Kein gespeicherter Stand

Der eingesehene Code nutzt bei fehlendem Stand einen Verlaufsschlüssel mit Sprungziel `recipe-freeze` und zusätzlich einen weiteren Verlaufsauslöser. Die Migration darf daraus nicht zwei optisch identische, unverständliche Verlaufssymbole machen.

PDF wird als aktuell nicht verfügbar behandelt und erhält eine zugängliche Begründung. Verlauf bleibt direkt erreichbar. Der bereits vorhandene Weg zum Festhalten eines Stands bleibt erhalten, bekommt bei separater Darstellung aber eine eigene verständliche Bedeutung und die korrekten Rechte. Es wird kein neuer Versionierungsworkflow erfunden und kein zusätzlicher gespeicherter Stand automatisch angelegt.

### 6.4 Gerichtvorlagen

Der Textblock „Keine Gerichtvorlage · Vorlage anlegen“ entfällt als zusätzliche Zeilenhöhe im Aktionsbereich. Der vorhandene Erstellweg wird als direktes Symbol mit dem Namen „Gerichtvorlage für {Rezeptname} anlegen“ dargestellt, soweit zulässig.

Eine vorhandene Einzelzuordnung kann direkt geöffnet werden. Bei mehreren Zuordnungen darf nicht stillschweigend nur die erste übrig bleiben. Nutze eine vorhandene fachliche Zuordnungsübersicht, falls sie genau diese Beziehungen zugänglich macht; andernfalls bleiben die bestehenden Einzelziele direkt erreichbar und eindeutig benannt. Keine neue generische Aktionsauswahl erfinden.

Fachlich erforderliche Information über vorhandene oder fehlende Zuordnungen bleibt in einer kompakten Metadaten-/Statusdarstellung oder in der bestehenden Objektansicht erhalten. **Statusinformationen nicht allein aus Platzgründen ersatzlos löschen.**

## 7. Gemeinsame Komponenten und Migration

### 7.1 Zentraler Renderer

Erweitere den bestehenden Renderer in `templates/ui/_semantic.html`, statt eine zweite parallele Komponentenfamilie zu bauen. `row_actions(items, object=none)` rendert künftig alle bereits gefilterten Elemente unmittelbar über `icon_button`.

Der Renderer führt keine neue Berechtigungsentscheidung anhand von Icon-Namen durch. URLs, Objektbezug, Formularzuordnung und fachliche Verfügbarkeit kommen weiterhin aus den zuständigen Aufrufern beziehungsweise bestehenden View-Modellen.

| Bestehender Vertrag | Muss bei der Direktdarstellung erhalten bleiben |
|---|---|
| `key`, `object`, `aria_label`, `title` | Semantik, Übersetzung und verständlicher Objektbezug. |
| `href` | Unverändertes Navigationsziel und Linkverhalten. |
| `type`, `name`, `value`, `form` | Native Formularwirkung und korrekte Formularzuordnung. |
| `attrs` | Bestehende Attributprüfung; unter anderem notwendige `formaction`-/`formmethod`-/`formnovalidate`-Verträge. |
| `consequence_key`, `emphasis` | Konsequenzprüfung und sichere Behandlung sensibler Befehle. |
| `id`, bestehende Datenattribute | Eindeutige Zuordnung, Fokusmanagement und benötigte Testschnittstellen. |

Setze die sichtbare Darstellung gewöhnlicher Aktionen explizit auf icon-only beziehungsweise `show_text=false`. Das darf nicht bedeuten, zugängliche Namen oder fachliche Konsequenztexte zu entfernen.

### 7.2 Alte Renderer und handgeschriebene Varianten

Migriere alle Aufrufer von `more_actions` und `action_menu`. Eine vorübergehende Kompatibilitätsschicht darf nur dieselbe direkte Symbolgruppe rendern; sie darf keine verborgene Aktionsliste erhalten. Im endgültigen normalen Renderpfad werden die alten Mehr-Aktionsmakros nicht mehr benötigt. Entfernen beziehungsweise Deprecation erfolgt nach Prüfung aller Aufrufer.

Prüfe auch die Legacy- und Slot-Renderer in `admin/_macros.html`, insbesondere die im bisherigen Komponentenvertrag beschriebenen Varianten `actions`, `list_row` und `form_footer`. Verifiziere deren aktuelle Implementierung, statt ältere Dokumentationssignaturen ungeprüft zu übernehmen. Vermeide zyklische Jinja-Imports zwischen den bestehenden Makrodateien.

Handgeschriebene `details`-/Dropdown-/Popover-Varianten und der lokale Rezepteditor-Helper werden auf denselben Vertrag gebracht. Aus Formularzeilen werden dabei keine verschachtelten Formulare, und ein bisheriger `formnovalidate`-Befehl darf nicht unbeabsichtigt ein vollständiges Speichern auslösen.

### 7.3 Styles und JavaScript

Passe die bestehende `.admin-row-actions`-Komponente und die gemeinsamen Tokens an. Entferne nicht mehr benötigte aktionsbezogene Spalten-, Stretch- und Disclosure-Regeln erst nach vollständiger Verbrauchermigration. Prüfe ausdrücklich die Sonderregeln in `recipe-admin.css`.

In `admin.js` sind vorhandene Listener für `.ui-sem-actions` zu prüfen und bei entfallenen Verbrauchern zu entfernen. Generische Tooltip-, Fokus-, Bestätigungs- und fachliche Disclosure-Funktionen bleiben erhalten. Kein globales Entfernen sämtlicher `details`-Logik.

Keine Notlösung mit app-weitem `display:none` für Mehr-Buttons: Dadurch würden die Funktionen lediglich unzugänglich. Keine pauschale Umstellung aller `details` auf `open`. Keine wachsende Sammlung rezeptbezogener CSS-Ausnahmen.

### 7.4 Semantik, Übersetzung und vorhandene Dateien

Verwende die vorhandene Registry und Übersetzungsstruktur. Im bisherigen Komponentenvertrag sind folgende Integrationspunkte dokumentiert; prüfe sie gegen den aktuellen Arbeitsstand:

```text
reference_scaffold/cafeteria/ui/semantic_registry.json
reference_scaffold/cafeteria/ui/icon_fallbacks.json
reference_scaffold/cafeteria/static/vendor/tabler-icons/tabler-icons.svg
reference_scaffold/cafeteria/translations/de.json
reference_scaffold/cafeteria/translations/en.json
reference_scaffold/cafeteria/static/tokens.css
reference_scaffold/cafeteria/static/admin-tabler.css
```

Eine Registry darf historische Schlüssel enthalten. Entscheidend ist, dass `actions.more` nicht mehr als generischer Aktionsverstecker gerendert wird. Kein unbedachtes Entfernen von Übersetzungsschlüsseln, die ausserhalb dieses Renderpfads noch benötigt werden.

### 7.5 Daten und Architektur

Diese Änderung benötigt ihrem Zweck nach keine neuen Geschäftsobjekte, Datenbanktabellen, Migrationsskripte oder API-Endpunkte. Änderungen an Backend-View-Modellen sind nur zulässig, soweit sie vorhandene Aktionen korrekt für den gemeinsamen Renderer bereitstellen. Keine N+1-Abfragen zur Ermittlung von Symbolen oder Vorlagenzuständen einführen.

Keine Umstellung auf ein anderes Frontendframework, keinen zweiten Icon-Provider und keine neue UI-Bibliothek. Bestehende fachliche Regeln, Profiltrennung, Veröffentlichungslogik und Authentisierung bleiben unverändert.

## 8. Zugänglichkeit und fehlertolerante Bedienung

### 8.1 Namen und Tooltips

Jeder Symbolauslöser besitzt einen verständlichen zugänglichen Namen mit Objektbezug, beispielsweise „Apfelmus bearbeiten“ oder „PDF von Apfelmus öffnen“. Ein SVG-Titel oder ein natives `title`-Attribut allein ist nicht der Komponentenvertrag. Verwende die vorhandenen `aria-label`-/Tooltip-Mechanismen konsistent.

Tooltips erscheinen bei Hover und Tastaturfokus, verändern kein Layout, bleiben innerhalb des Viewports und sind per Escape schliessbar. Sie nehmen keinen Fokus an und enthalten keine zusätzlichen Befehle. Auf Touch bleibt der erste Tap der eigentlichen Aktion vorbehalten; kein verpflichtender erster Tap nur zum Anzeigen eines Tooltips.

### 8.2 Native Semantik und Tastatur

Navigation bleibt ein echter Link. Befehle bleiben Buttons mit explizit korrektem `type`. Ein gewöhnlicher Dialogauslöser darf nicht wegen eines übernommenen Submit-Defaults das umgebende Formular absenden. Alle Aktionen sind per Tastatur in visueller Reihenfolge erreichbar.

Die sichtbare Symbolleiste kann technisch eine normale, benannte Gruppe sein. **Kein `role="toolbar"` nur für die Optik hinzufügen.** Wird der vollständige ARIA-Toolbar-Vertrag verwendet, müssen auch seine Fokus- und Pfeiltastenregeln implementiert und getestet werden. Für die erste Migration ist die native Tab-Reihenfolge ohne neue komplexe Widgetlogik ausreichend.

### 8.3 Deaktivierung, Fehler und sensible Befehle

`aria-disabled` allein verhindert keine Ausführung. Deaktivierte Aktionen müssen Navigation und Datenänderung tatsächlich unterbinden; insbesondere darf ein deaktivierter Link nicht weiter einem aktiven `href` folgen. Begründungen müssen auch für Tastaturnutzer und assistive Technik erreichbar sein. Nutze dafür ein einheitliches bestehendes beziehungsweise geprüftes Komponentenverhalten.

Bestätigungen für sensible Aktionen benennen Objekt und konkrete Folge. Die vorhandene Konsequenzprüfung wird nicht entfernt, nur weil ihr bisheriger Text unter einem Mehr-Menü stand. Binde notwendige ausführliche Informationen an den eigentlichen Bestätigungsschritt statt an jede Tabellenzeile.

CSRF-Schutz, serverseitige Autorisierung und vorhandene HTTP-Methoden bleiben erhalten. Datenänderungen werden nicht zu GET-Links umgebaut. Ohne JavaScript darf ein bisher sicherer Bestätigungsablauf nicht plötzlich unmittelbar mutieren.

### 8.4 Einordnung der Grössenvorgaben

WCAG 2.2 SC 2.5.8 beschreibt eine Mindestzielgrösse von 24 × 24 CSS-Pixeln mit definierten Ausnahmen. SC 2.5.5 beschreibt 44 × 44 CSS-Pixel auf dem erweiterten Niveau. Die in dieser SDD gewählten Desktop- und Touchwerte sind Projektentscheidungen; die komplette App ist damit nicht automatisch WCAG-konform. Quellen stehen in Abschnitt 13.

## 9. Vollständiges Audit statt Rezept-Sonderlösung

Erzeuge zuerst eine kurze, nachvollziehbare Inventur. Suche semantisch und technisch nach Mehr-Aktionsmustern; ein blosser Texttreffer auf drei Punkte reicht nicht.

```text
Zu untersuchende Muster:
  row_actions / more_actions / action_menu / render_actions
  actions.more
  ui-sem-actions / ui-sem-action-items
  admin-compact-actions / admin-week-more
  details + summary mit Aktionssammlung
  dropdown-menu / popover mit Objektbefehlen
  Sichtbarkeit von Aktionen nur bei Hover, Fokus oder Swipe
  primary/secondary/rare-Slots mit versteckten Befehlen
  lokale Helper mit gleichem Namen und anderer Signatur
```

Für jeden Treffer ist zwischen Aktionsversteck, fachlichem Disclosure, Navigation und echter Auswahl zu unterscheiden. Keine globale Ersetzung von „…“ in Fliesstext, Ladeanzeigen oder Benutzerdaten.

Führe eine Matrix mit mindestens diesen Spalten:

```text
Oberflaeche | reale Route | Template/Komponente | Rolle/Zustand
Aktionen vorher | Aktionen nachher | Berechtigung erhalten
Direkt sichtbar | Responsive geprueft | Test/Evidenz | Restpunkt
```

Nutze eine bestehende Routenmatrix, soweit aktuell, und ergänze fehlende Oberflächen. Die Gesamtmenge muss benannt werden. „Alle geprüft“ ist ohne nachvollziehbaren Umfang kein Abnahmenachweis.

## 10. Tests und messbare Abnahme

### 10.1 Bestehende Tests gezielt aktualisieren

Die Repository-Suche liefert bereits Browsertests mit Erwartungen an `.ui-sem-actions`, beispielsweise `test_ui_semantic_macros_browser.py`, `test_icon_pilot_filters_browser.py`, `test_icon_tooltip_viewport_browser.py`, `test_icon_api_browser.py` und `test_icon_screen_context_browser.py` unter `reference_scaffold/tests/`.

Prüfe die aktuellen Inhalte und ändere veraltete Menü-Erwartungen auf die neue Direktdarstellung. Behalte deren übrige Sicherheits-, Tooltip-, Rollen- und Funktionsprüfungen bei. Nicht einfach Tests löschen oder Screenshots neu akzeptieren, bis der Lauf grün wird.

### 10.2 Pflichtfälle

| ID | Prüfung | Erfolgskriterium |
|---|---|---|
| A01 | Gemeinsamer Renderer mit 0, 1, 2, 5 und 8 Aktionen | Jede gelieferte verfügbare Aktion direkt sichtbar; kein Mehr-Auslöser. |
| A02 | Rezeptreferenz mit gespeicherter Revision | Öffnen, zulässiges Bearbeiten, PDF, Verlauf und zulässige Vorlagenaktion unmittelbar erreichbar. |
| A03 | Rezept ohne gespeicherte Revision | Kein kaputter PDF-Link; verständliche Nichtverfügbarkeit; bestehender Vorbereitungsweg bleibt erhalten. |
| A04 | Rollen und Objektzustände | Keine neuen Rechte; aktive, archivierte und lesbare Objekte korrekt. |
| A05 | Vorlagenzustände | Keine, eine und mehrere Zuordnungen ohne verlorene Ziele. |
| A06 | Doppelte oder ähnliche Ziele | Kein doppelter Befehl; unterschiedliche Bedeutungen bleiben erhalten. |
| A07 | Desktopgeometrie | Bei einzeiligen Referenzdaten ungefähr 52-Pixel-Zeilen; fünf Symbole in einer Reihe bei ausreichender Breite. |
| A08 | Hover und Tastaturfokus | Unveränderte Zeilenhöhe, abgesehen von höchstens 1 CSS-Pixel Messrundung. |
| A09 | Touch | Mindestens 44 × 44 CSS-Pixel Bedienfläche; keine Überschneidungen. |
| A10 | Schmale Darstellung | Alle Aktionen sichtbar, geordneter Umbruch, kein benötigter Mehr-Klick und kein abgeschnittener Aktionszugang. |
| A11 | Zugängliche Namen | Kein unbeschrifteter Icon-Auslöser; Objektbezug eindeutig. |
| A12 | Tooltips | Hover, Fokus, Escape und Viewportränder geprüft; kein Layoutsprung. |
| A13 | Native Bedienung | Tastatur, Link-Ziel, neuer Tab und Formularzuordnung bleiben korrekt. |
| A14 | Deaktivierte Aktionen | Keine Datenänderung durch Maus, Tastatur, Enter oder indirekten Submit; Grund zugänglich. |
| A15 | Sensible Aktionen | Bestehende Bestätigung und serverseitige Schutzmechanismen weiterhin wirksam. |
| A16 | Eingebettete Editorzeilen | Einfügen, Verschieben und Entfernen wirken auf die richtige Zeile; Werte gehen nicht unbeabsichtigt verloren. |
| A17 | Lange Inhalte und Zoom | Lange Namen, 200 Prozent Zoom und umgebrochene Daten werden nicht abgeschnitten. |
| A18 | Übersetzungen | DE/EN-Namen und Tooltips korrekt; keine fehlenden Schlüssel; mehrsprachige Texte sprengen das Layout nicht. |
| A19 | Weitere Objektköpfe und Formularfüsse | Kein verbliebenes generisches Mehr-Aktionsmenü. |
| A20 | Daten- und Publikationsneutralität | Kein automatisches Speichern, Anlegen eines Stands oder Veröffentlichen durch Darstellung oder Navigation. |
| A21 | JavaScript-Fallback | Keine neue unbeabsichtigte Mutation bei fehlendem JS; vorhandene sichere Fallbacks erhalten. |
| A22 | Vollständige Abdeckung | Alle Audit-Treffer klassifiziert und alle betroffenen realen Oberflächen migriert oder als offener Mangel benannt. |
| A23 | Gemeinsamer Standard | Keine neuen seitenlokalen Kopien des Aktionsrenderers oder abweichenden Icongrössen. |
| A24 | Dokumentation | Alte Overflow-Budgets als Standard entfernt beziehungsweise ausdrücklich durch diese Regel ersetzt. |

### 10.3 Browser- und Zustandsmatrix

Prüfe mindestens 1440, 1280, 1024, 768, 390 und 320 CSS-Pixel Viewportbreite sowie eine schmale Karte innerhalb eines breiten Layouts. Prüfe Touch-Emulation, Tastatur und 200 Prozent Zoom. Vergleiche dabei identische Datenzustände; eine durch tatsächliche Datenänderung grössere Zeile ist kein Hover-Layoutfehler.

Automatisierte Assertions müssen gerenderte Sichtbarkeit und tatsächliche Bedienbarkeit prüfen, nicht nur das Vorhandensein von HTML. Ergänze eine visuelle Kontrolle der Gesamtliste: ruhige Symbolreihe, ausreichende Datenbreite, keine farbige Buttonwand und keine unnötigen Leerblöcke.

Screenshots der fertigen Lösung sind mit Route, Viewport, Rolle/Zustand und getesteter Revision zu dokumentieren. Alte Referenzbilder oder Entwürfe dürfen nicht als Nachweis der Umsetzung ausgegeben werden.

## 11. Arbeitspakete für die laufende Implementierung

| Paket | Auftrag | Abhängigkeit / Verantwortung |
|---|---|---|
| WP1 – Bestandsaufnahme | Aktions- und Routeninventur, Konflikte in Manifesten und Tests, Rollen-/Zustandsfälle erfassen. | Früh starten; eindeutiger Umfang vor Abschluss. |
| WP2 – Gemeinsamer Vertrag | Renderer, Symbolsemantik, gemeinsame Styles, Zustände und Verträge korrigieren. | Eine verantwortliche Integrationsperson für gemeinsam genutzte Dateien. |
| WP3 – Listen und Karten | Rezeptliste und weitere Inhalts-/Verwaltungslisten migrieren. | Nach festgelegter WP2-Schnittstelle; Dateien klar aufteilen. |
| WP4 – Planung und Editoren | Wochenansichten, Detailköpfe, Formularfüsse und eingebettete Editoraktionen migrieren. | Nach WP2-Vertrag; keine konkurrierenden Änderungen an gemeinsamen Makros. |
| WP5 – Tests und Review | Neue Direktaktionsprüfungen, aktualisierte Altprüfungen, Accessibility- und Responsive-Review. | Testentwurf parallel möglich; abschliessend gegen integrierten Stand. |
| WP6 – Integration | Alte Aktionsverstecker bereinigen, Designregeln aktualisieren, Gesamtabnahme und Bericht. | Nach Integration aller betroffenen Oberflächen. |

Parallelisiere unabhängige Pakete, soweit die laufende Umgebung entsprechende Werkzeuge bereitstellt. Gemeinsame Dateien erhalten eine klare Schreibverantwortung. Kleine integrierbare Änderungen sind einer grossen unkontrollierten CSS-/Template-Umschreibung vorzuziehen.

Vorhandene Änderungen der laufenden Session nicht zurücksetzen. Deployment nur im Rahmen des bereits erteilten Auftrags; diese SDD ist keine zusätzliche pauschale Produktionsfreigabe. Ein freigegebenes Deployment erfolgt erst nach erfolgreicher Integration und erforderlicher Abnahme.

### Verpflichtender Abschlussbericht der implementierenden Session

Berichte die geänderten gemeinsamen Komponenten, die tatsächlich migrierten Oberflächen, ausgeführte Tests mit Ergebnissen und vorhandene Browsernachweise. Nenne offene Punkte konkret. Trenne „Code geändert“, „Tests bestanden“, „im Browser geprüft“ und „deployed“ voneinander.

**Definition of Done:** Die Rezeptseite und alle weiteren erfassten Aktionsverstecker sind korrigiert; verfügbare Befehle sind direkt sichtbar; die Zeilen bleiben kompakt; Rechte und fachliche Abläufe funktionieren unverändert; Tests und verbindliche Designregeln sichern das Verhalten für neue Seiten ab.

## 12. Übernahmetext für das bestehende UI-Manifest

> ### Direkte Symbolaktionen
>
> Sämtliche im aktuellen Kontext verfügbaren Objekt- und Zeilenaktionen werden direkt als einheitliche Symbole dargestellt. Generische Mehr-/Drei-Punkte-Menüs, Hover-only-Aktionen und aufklappende Aktionslisten sind für diesen Zweck nicht zulässig. Diese Regel gilt auch für Objektköpfe, Formularaktionsgruppen und eingebettete Listen und ersetzt frühere feste Budgets sichtbarer Aktionen.
>
> Die gemeinsame Aktionskomponente rendert alle berechtigten und fachlich vorgesehenen Aktionen. Sie wahrt stabile Semantik und Reihenfolge, eindeutige zugängliche Namen, gemeinsame Geometrie sowie native Link- und Formularverträge. Keine seitenlokalen Sonderrenderer.
>
> Desktop: eine kompakte Symbolreihe, soweit der Platz reicht. Schmale Oberflächen: sichtbare Aktionszeile mit geordnetem Umbruch. Mobile Darstellung ist keine Ausnahme für versteckte Aktionen.
>
> Fachliche Informationen, notwendige Warnungen, Berechtigungen und Schutzschritte bleiben erhalten. Sicherheitsbestätigungen dürfen lesbaren Text enthalten. Echte Auswahl-, Filter-, Navigations- und Detailkomponenten bleiben von dieser Regel unberührt, solange sie keine generische Aktionssammlung verstecken.

## 13. Quellen und Gültigkeitsgrenzen

### Repository-Basis

Die Codebefunde in Abschnitt 1 beziehen sich auf die am 29. September 2026 über den verbundenen GitHub-Zugang eingesehenen Dateien von `joehomeskillet/Dishboard`. Dateipfade und Makronamen sind konkrete Ansatzpunkte. Suchtreffer und ältere Komponentenanalysen ersetzen keine vollständige Prüfung des aktuellen Worktrees.

Verwandte Dokumente aus den Such-/Leseergebnissen:

```text
docs/design/2026-09-26-icon-first-contract.md
docs/design/2026-09-09-unified-ui-design-system.md
docs/ui-semantic-audit.md
tools/ui_consistency_inventory.py
```

Der Komponentenvertrag vom 26. September verweist zusätzlich auf `docs/design/2026-09-26-icon-first-simplification-spec.md`. Dessen aktuellen Status im Worktree prüfen; seine vollständigen Inhalte wurden für diese neue SDD nicht gesondert eingesehen. Keine historischen Trefferzahlen aus älteren Audits als aktuellen Umfang ausgeben.

### Externe Primärquellen für die Accessibility-Hinweise

Abgerufen am 29. September 2026. Die folgenden Adressen dienen der technischen Nachprüfung; die Layoutziele dieser SDD sind eigenständige Projektentscheidungen.

```text
W3C WAI — Button Pattern:
https://www.w3.org/WAI/ARIA/apg/patterns/button/

W3C WAI — Toolbar Pattern:
https://www.w3.org/WAI/ARIA/apg/patterns/toolbar/

W3C WAI — Tooltip Pattern:
https://www.w3.org/WAI/ARIA/apg/patterns/tooltip/

W3C WAI — WCAG 2.2, SC 2.5.8 Target Size (Minimum):
https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

W3C WAI — WCAG 2.2, SC 2.5.5 Target Size (Enhanced):
https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html
```

Das APG-Tooltip-Muster ist dort als noch in Bearbeitung bezeichnet; es wird hier als Umsetzungshilfe verwendet, nicht als eigenständiger Konformitätsnachweis. Die native Button-/Linksemantik, zugängliche Namen und die bewusst gewählte Tastaturstrategie sind unabhängig davon zu prüfen.

---

**Leitentscheidung: Alle sinnvollen, erlaubten Aktionen direkt sehen und erreichen – ohne „…“, ohne Aktionsaufklappen und ohne Rückfall in inkonsistente Sonderlösungen.**
