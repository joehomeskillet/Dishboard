
# SDD-Addendum: Keine Inhaltsaufklapper, keine Platzhalter-Striche, eindeutige Buttons und stabile Navigation

**Kennung:** UI-DELTA-2026-10-01  
**Version:** 1.0 – einschliesslich der Nachträge zu Lagerorten und gemischten Buttons  
**Stand:** 1. Oktober 2026  
**Art:** Ausschliesslich zusätzliche beziehungsweise gezielt ablösende Anforderungen zum laufenden Auftrag  
**Geltung:** Gesamtes Dishboard-Projekt; nicht nur die abgebildeten Seiten  
**Status:** Spezifikation. Keine Implementierungs-, Test- oder Deploymentbestätigung.

## 0. Übernahme in die laufende Session

Ergänze den laufenden Auftrag um genau diese fünf Änderungen:

| Delta | Neue verbindliche Entscheidung |
|---|---|
| **D – Inhaltsaufklapper** | Keine inhaltlichen Auf-/Zuklappbereiche mehr innerhalb von Arbeitsflächen. Insbesondere keine aufklappenden Tabellenzellen, Zusatzzeilen, Statusdetails, Karten- oder Formularakkordeons. |
| **P – Platzhalter** | Keine alleinstehenden Bindestrich-/Gedankenstrich-Platzhalter vor Aktionssymbolen oder in leeren optionalen Status-/Metadatenbereichen. |
| **R – Redundanz** | Redundante Aktionsauslöser und doppelte Symbolausgaben im gesamten Projekt anhand ihrer tatsächlichen Bedeutung prüfen und bereinigen. |
| **B – Buttondarstellung** | Jeder Aktionsbutton zeigt **entweder ein Symbol oder Text, niemals beides gleichzeitig**. Das gilt auch für Anmeldungs-, Fehler- und Bestätigungsseiten. |
| **N – Navigation** | Informationsfelder dürfen weder Bereichsnavigation noch Sidebar oder Seitenrahmen verschieben. Der Nachtrag „Lagerorte: Infofeld lässt Navigation springen“ ist ein verbindlicher Referenzfall. |

Diese Datei wiederholt keine allgemeinen Regeln für UI-Polish, Authentifizierung, Rollen, Veröffentlichung oder Formularsicherheit. Bestehende Verträge gelten weiter, soweit sie nicht in der folgenden Konfliktmatrix ausdrücklich präzisiert werden.

### 0.1 Gezielter Vorrang gegenüber älteren Formulierungen

| Bisherige Grundlage | Ausschliesslich diese Änderung |
|---|---|
| UI-Optimierungs-SDD, insbesondere Abschnitt 5.9: sekundäre Informationen dürfen aufklappbar sein. | Diese Erlaubnis entfällt für Inhaltsbereiche. Detailinformationen erhalten eine nicht aufklappende Darstellung nach D-02. |
| Bisherige Formular-/Hinweismuster mit „Weitere Optionen“, Disclosure oder Akkordeon. | Auch diese Inhalte dürfen nicht mehr im Dokumentfluss auf- und zugeschoben werden. Daten, Feldzuordnung und Speicherumfang bleiben erhalten. |
| Direktaktions-SDD: fachliche Detailabschnitte waren vom Aktionsversteck-Verbot ausgenommen. | Die Ausnahme für **Inline-Inhaltsaufklapper** entfällt. Echte Navigation und Auswahlelemente bleiben gesonderte Interaktionsarten. |
| Errorhandling-SDD: Icon plus kurze Beschriftung als Ausnahme auf Fehler-/Anmeldeseiten. | Diese Ausnahme entfällt vollständig. Dort sind kurze **reine Textbuttons** der Standard, beispielsweise „Anmelden“ oder „Neu laden“. Die Fehler- und Redirectlogik wird nicht geändert. |
| Bisherige Erlaubnis kurzer Beschriftungen bei unklaren Fachsymbolen. | Bei dieser Entscheidung wird auf **Text ohne zusätzliches Icon** umgestellt. Kein Mischmodus. |

Alte Dokumente nicht vollständig neu schreiben. Widersprechende Stellen gezielt als abgelöst markieren, zugehörige Tests korrigieren und diesen Zusatzvertrag in den aktiven Projekteinstieg aufnehmen.

## 1. Ausgangsfälle und belastbare Ansatzpunkte

### 1.1 Referenzfälle aus den neuen Bildern und Nachträgen

| Referenz | Beobachtung beziehungsweise Auftrag | Konsequenz |
|---|---|---|
| Bereiche & Öffnungszeiten, geschlossen/geöffnet | Wochenvorgaben erscheinen nach Betätigung eines Chevrons innerhalb einer Tabellenzelle. Die betroffene Zeile wächst, die übrigen Spalten enthalten viel Leerraum. | Wochenvorgaben nicht mehr in der Tabellenzeile aufklappen. |
| Patienten-Menüliste und Ausschnitt | Unter dem Prüfstatus lässt sich ein längerer Hinweis innerhalb der Zeile öffnen. | Kurzen relevanten Status stehen lassen; ausführlichen Prüfhinweis ausserhalb des Zeilenlayouts zugänglich machen. |
| Zutaten | Vor den Aktionssymbolen steht ein einzelner Strich ohne verständlichen fachlichen Inhalt. | Herkunft des Platzhalters im gemeinsamen Renderer korrigieren, nicht nur auf dieser Seite kaschieren. |
| Kochbücher | Öffnen und Bearbeiten stehen nebeneinander. | Als Redundanz-Prüffall erfassen, **nicht ungeprüft als doppelte Aktion einstufen**. |
| Lagerorte – Nutzernachtrag | Ein Infofeld lässt die Navigation springen. | Stabile Bereichsnavigation und stabilen Seitenrahmen prüfen; Ursache im aktuellen Browserlauf nachweisen. |
| Buttons – Nutzernachtrag | Gemischte Darstellung mit Symbol und Beschriftung ist noch vorhanden. | Beide erlaubten Darstellungsarten explizit trennen und sämtliche Zustände migrieren. |

Die Bilder sind IST-Referenzen, keine Sollbilder. Aus ihnen allein folgen keine verlässlichen Aussagen über Laufzeitursachen, Handlerwirkungen oder das vollständige Projektinventar.

### 1.2 Eingesehener Repository-Stand

Die folgenden Befunde stammen aus einer gezielten Einsicht am 1. Oktober 2026. Sie sind konkrete Migrationsansatzpunkte, keine vollständige Inventur und kein Nachweis, dass das aktuelle Deployment oder ein paralleler Worktree identisch ist.

| Quelle | Konkreter Befund | Ableitung |
|---|---|---|
| `templates/admin/_macros.html`, `list_row()` | Der Statusbereich wird auch ohne Inhalt gerendert und fällt auf `empty_value()` zurück. Dieser Helper gibt einen Gedankenstrich aus. | Ein fehlender optionaler Status darf keine leere Statusspalte mit Strich erzeugen. [R1] |
| `templates/admin/grundlagen.html` | Der nur für `kind == 'lagerorte'` ausgegebene Hinweis steht **vor** der Navigation „Stammdatenbereiche“. | Der Hinweis liegt an einer Stelle, an der seine Höhe die nachfolgende Navigation verschieben kann. Das ist ein konkreter struktureller Ansatzpunkt; die tatsächliche Sprungweite ist noch zu messen. [R2] |
| `templates/ui/_semantic.html`, `icon_button()` | Das Icon wird unabhängig von `show_text` ausgegeben; bei `show_text=true` kommt Text hinzu. | Mit diesem Rendervertrag kann „reiner Text“ nicht zuverlässig gewählt werden. Die gemeinsame Ausgabe braucht zwei exklusive Modi. [R3] |
| `templates/admin/kochbuecher.html` | Die Liste referenziert für Öffnen `admin.cookbook_view`, für Bearbeiten `admin.cookbook_edit`. | Unterschiedliche Endpoints sind kein Beweis einer Redundanz. Das tatsächliche Verhalten beider Ziele ist zu prüfen. [R4] |

Alle Pfade in dieser Tabelle sind relativ zu `reference_scaffold/cafeteria/`. Insbesondere keine aktuelle Gesamtzahl betroffener Seiten aus historischen Audits übernehmen.

## 2. D – Inhaltsaufklapper systemweit abschaffen

### D-01 – Verbot nach Verhalten, nicht nur nach HTML-Tag

Ein **Inhaltsaufklapper** ist ein Auslöser, der vorhandene Zusatzinformationen oder Eingabebereiche im aktuellen Dokumentfluss ein-/ausblendet und dafür Platz innerhalb oder zwischen bestehenden Inhaltsblöcken beansprucht.

Verboten sind insbesondere:

- Detailtexte in Tabellenzellen, aufklappende untergeordnete Tabellenzeilen und wachsende Listeneinträge.
- Akkordeons für Status, Prüfhinweise, Wochenvorgaben, Vorschauen, Karteninhalte und Formularabschnitte.
- „Weitere Optionen“, „Details anzeigen“, „Mehr anzeigen“ oder Infofelder, die den folgenden Arbeitsinhalt beim Betätigen nach unten schieben.
- Aufgeschobene Filter- oder Hilfeblöcke zwischen Toolbar und Liste, die das Arbeitsraster verdrängen.
- Gleiches Verhalten mit anderen Mitteln: `details/summary`, Collapse-Plugin, JavaScript, bedingtes Rendering, wechselnde Grid-Zeilen, animierte Höhe oder hinzugefügte DOM-Blöcke.

Das Verbot gilt auch innerhalb eines Dialogs oder einer mobilen Darstellung. Einen Akkordeonblock unverändert in ein Modal zu verschieben, erfüllt es nicht.

**Keine Ersatztricks:** nicht alles permanent aufklappen; nicht die Zeilenhöhe festklemmen und den Inhalt abschneiden; nicht nur den Chevron ausblenden; nicht den Inhalt löschen; nicht dieselbe Funktion in einen Push-Drawer verschieben, der die Hauptfläche verkleinert.

**Abgrenzung:** Sidebar-Navigationsgruppen, echte Selects/Comboboxen, Datums- und Zeitpicker sowie native Checkboxen sind keine Zusatzinhalts-Akkordeons. Sie werden nicht durch ein pauschales Verbot aller `details`, `aria-expanded` oder Chevrons beschädigt. Diese Abgrenzung erlaubt aber keine neue Aktionssammlung oder einen Inhaltsaufklapper unter dem Namen „Navigation“.

### D-02 – Verbindliche Ersatzentscheidung pro Fundstelle

| Bisheriger Inhalt | Neue Darstellung | Grenze |
|---|---|---|
| Kurze unmittelbar benötigte Information | Kompakter, dauerhaft sichtbarer Inhalt in der passenden Daten-/Statuszone. | Nicht hinter Hover oder einem Dialog verstecken, wenn sie für die aktuelle Entscheidung notwendig ist. |
| Ergänzende, längere Leseinformation | Ein gemeinsamer Lesedialog oder eine vorhandene Detailseite. | Keine Zusatzzeile und kein Akkordeon innerhalb des Dialogs. |
| Wochenvorgaben, strukturierte Prüfhinweise, umfangreiche Beziehungen | Strukturierte Detailansicht; kompakte Fälle dürfen denselben Lesedialog nutzen. | Keine langen Tooltiptexte als Ersatz. |
| Optionale Bearbeitungsfelder | Sinnvoller statischer Formularabschnitt, vorhandene Unterseite oder echte aufgabenbezogene Tabs. | Keine Übertragung in eine neue unabhängige Speicheraktion ohne fachlichen Auftrag. |
| Filter | Bereits sichtbare kompakte Felder oder ein Filterdialog ausserhalb des Dokumentflusses. | Das Öffnen darf weder Liste noch Toolbar verschieben. |
| Mehrere zusätzliche Kalendereinträge | Tagesdetailansicht oder Tagesdialog. | Zusätzliche Einträge bleiben zugänglich; der Monatsraster wird nicht zum Aufklapp-Akkordeon. |

Nutze pro Komponentenfamilie dieselbe Entscheidung. Keine frei wechselnde Mischung aus Tooltip, Drawer, Modal und neuer Seite für identische Aufgaben.

**Standard für diesen Auftrag:** bestehende Detailseite bevorzugen, wenn sie exakt denselben Inhalt und Kontext ohne zusätzlichen Umweg zugänglich macht. Für ergänzende Lesedetails ohne geeignete Seite den gemeinsamen Lesedialog verwenden. Kleine Informationen nicht unnötig zu Dialogen machen.

Ein neuer Lese-Endpunkt ist nur erforderlich, wenn der vorhandene sichere Datenzugang den Ersatz tatsächlich nicht ermöglicht. Kein Backend-Neubau und kein neuer Fachworkflow allein wegen der Darstellung.

### D-03 – Bereiche & Öffnungszeiten konkret migrieren

Die Tabellenzeile enthält weiterhin Bereich, die vorhandene Wochenendregel und den kompakten Status der Wochenvorgaben. Tages-/Mahlzeitdetails werden nicht in diese Zeile eingebaut.

Ein einzelner fachlich benannter Zugang öffnet die Wochenvorgaben des betreffenden Bereichs. Existiert bereits ein geeigneter direkter Zugang, wird er verwendet statt daneben ein zweites identisches Infosymbol zu ergänzen.

Die Detailansicht muss die tatsächlichen vorhandenen Angaben vollständig enthalten: Wochentag, Mahlzeit, offen/geschlossen und eingetragene beziehungsweise fehlende Zeit. Der Hinweis „Wochenvorgaben gelten für neue Ausgaben“ bleibt dort erhalten, wo sein Geltungsbereich verstanden werden muss.

**Abnahme:** Öffnen und Schliessen verändert weder Höhe der Bereichszeile noch Spaltenbreiten oder Position der Nachbarzeile. Lesen löst keine Änderung der Vorgaben aus.

### D-04 – Prüfstatus und Menühinweise konkret migrieren

Der vorhandene kurze Prüf-/Warnstatus bleibt unmittelbar erkennbar. Vollständige Hinweise wechseln in einen benannten Lesedialog oder die passende bestehende Prüf-/Detailansicht.

Der Zielinhalt muss zum gewählten Menü, Bereich, Datum, Mahlzeit und gegebenenfalls gespeicherten Prüfstand gehören. Ein generischer Name wie „Details ein- oder ausklappen“ wird durch den tatsächlichen Zweck ersetzt, beispielsweise „Prüfhinweise zu Gemüse-Pastetli anzeigen“.

Ein Lesedialog darf zusätzliche Hinweise erläutern, aber nicht allein durch das Öffnen einen Prüfstatus verändern. Für die Entscheidung notwendige Warnungen bleiben in der Übersicht; die Migration ist kein Anlass, fehlende Allergenangaben optisch verschwinden zu lassen.

**Abnahme:** Der lange Hinweis ist vollständig lesbar, ohne Abschneiden am Tabellenrand, ohne zweite Inhaltszeile und ohne Verschieben des Bearbeitungsbuttons.

### D-05 – Ersatzdialog ohne Layoutverschiebung und ohne zusätzliche Bedienredundanz

Ein Dialog überlagert die vorhandene Arbeitsfläche; er verkleinert sie nicht und reserviert darin keinen zusätzlichen Platz. Mobil darf derselbe Vertrag bildschirmfüllend dargestellt werden.

Der Dialog erhält einen eindeutigen Titel, den benötigten Objektkontext und einen sichtbaren Schliesszugang. Fokuswechsel, modale Tastaturführung und Fokusrückgabe richten sich nach dem Dialogvertrag. Bei langen strukturierten Inhalten ist ein sinnvoller Anfangsfokus am Titel zu prüfen. [W1]

Für reine Lesedialoge genügt im Normalfall ein sichtbarer Schliessbutton. Nicht gleichzeitig ein Kreuz, „OK“, „Fertig“, „Abbrechen“ und „Schliessen“ anbieten, wenn alle dieselbe Wirkung haben. Escape bleibt eine alternative Tastaturbedienung und ist keine zusätzliche sichtbare Schaltfläche.

Ein Dialog, der erst eine Liste möglicher Aktionen anbietet, ist kein gültiger Ersatz. Der erste Auslöser muss den konkret benannten Inhalt öffnen.

## 3. P – Leere Strich-Platzhalter entfernen

### P-01 – Optionalen Inhalt nicht durch Striche ersetzen

Für optionale Status-, Markierungs- und Metadatenslots gilt: Fehlt ein darzustellender Inhalt, wird kein dekorativer Ersatz ausgegeben.

Zu entfernen sind UI-generierte Einzelzeichen wie `-`, `–`, `—`, `−`, `&ndash;` und `&mdash;`, wenn sie ausschliesslich „kein optionaler Inhalt“ darstellen. Das schliesst Textknoten, Helperausgaben sowie `::before`-/`::after`-Inhalte ein.

Nach der Korrektur steht vor einer Symbolgruppe kein leerer Statusrest. Den entfernten Strich nicht durch Punkt, leeres Badge, leere Iconfläche oder unsichtbares Leerzeichen ersetzen.

### P-02 – Leerwertsemantik ausdrücklich definieren

| Eingang / Bedeutung | Ausgabe |
|---|---|
| Optionaler Slot ohne Wert | Slot entfällt. |
| Leere Zeichenfolge, nur Leerraum oder leerer Inhaltsslot | Kein Strich und kein leerer Wrapper. |
| Fachlich bedeutsamer fehlender Wert | Verständliche konkrete Angabe, etwa „Nicht erfasst“, in der passenden Datenzone. |
| Tatsächlicher Wert `0` oder `false` | Nach Fachsemantik anzeigen; nicht als fehlend behandeln. |
| Fehlender Pflichtname | Daten-/Validierungsfall, nicht kommentarlos eine namenlose Zeile rendern. |
| Echter Minuswert, Subtraktionszeichen oder Bindestrich in Benutzerdaten | Unverändert erhalten. |

Die Bereinigung erfolgt am Komponentenvertrag, nicht durch globale Zeichenersetzung über gerendertes HTML oder Datenbankinhalte.

Für zusammengesetzten HTML-Inhalt reicht eine naive Prüfung auf nichtleere Zeichenfolgen nicht aus: ein leerer `<span>` kann technisch Text enthalten, ohne fachlichen Status darzustellen. Die aufrufende Daten-/Komponentenschicht muss explizit wissen, ob Inhalt vorhanden ist.

### P-03 – Wrapper, Raster und gemeinsame Quelle bereinigen

`list_row()` darf bei fehlendem optionalem Status nicht mehr automatisch `empty_value()` aufrufen. Der eingesehene Stand ist hierfür der zentrale Ansatzpunkt. [R1]

Auch `meta`, Untertitel und Markierungen auf leere Ausgabe prüfen. Ein Leerzeichen als `status=' '` ist kein zulässiger Dauer-Workaround. Im eingesehenen Kochbuchtemplate wird eine solche Abgrenzung bereits verwendet; sie ist bei der Vertragskorrektur mitzuprüfen. [R4]

Bei flexiblen Listen/Karten entfallen nicht benötigte Wrapper und ihre zugehörigen Abstände. Bei echten Tabellen bleibt die semantische Spaltenzuordnung korrekt: einzelne Datenzellen nicht so entfernen, dass Werte unter die falschen Überschriften rutschen. Eine gegebenenfalls leere Zelle ist kein Auftrag für einen sichtbaren Strich.

## 4. R – Redundante Symbole und Auslöser prüfen

### R-01 – Redundanz ist eine fachliche Entscheidung

Zwei Bedienelemente gelten nur dann als funktional redundant, wenn sie im selben lokalen Arbeitskontext denselben Zweck, dasselbe Zielobjekt und denselben Modus ohne relevanten Unterschied bedienen.

Die Prüfung berücksichtigt mindestens:

| Prüfdimension | Beispiele für einen relevanten Unterschied |
|---|---|
| Absicht und Wirkung | Anzeigen, bearbeiten, auswählen, planen, archivieren. |
| Zielobjekt und Stand | Gleichnamige Objekte, verschiedene Revisionen, veröffentlichter Stand gegenüber Entwurf. |
| Modus und Rechte | Schreibgeschützte Ansicht gegenüber Editor; zulässige Aktion gegenüber nicht ausführbarer Aktion. |
| Route und Parameter | Profil, Datum, Mahlzeit, Anker, Dialogziel, ausgewählter Abschnitt. |
| Ausführung | Navigation gegenüber Submit; Formularzuordnung und vorhandene Sicherheitsbestätigung. |

Keine automatische Löschung nach identischem Icon, übersetztem Label oder URL-String. Unterschiedliche URLs können letztlich dieselbe Wirkung haben; dieselbe URL kann mit bewusst unterschiedlichen Parametern oder Modi verschiedene Ziele bedienen.

**Kochbuch-Referenz:** Öffnen und Bearbeiten nicht allein wegen ihrer Nachbarschaft zusammenlegen. Die eingesehenen Templates verwenden verschiedene Endpoints. Prüfe die tatsächlichen Zielansichten und etwaige Weiterleitungen. Ein belegter Lese-/Edit-Unterschied bleibt erhalten. [R4]

### R-02 – Drei Redundanzarten getrennt erfassen

| Art | Beispiele | Korrektur |
|---|---|---|
| Doppelte Symbolausgabe innerhalb eines Controls | Icon im gemeinsamen Renderer und nochmals im Aufrufer; SVG plus CSS-Pseudoelement; zwei gleiche Chevrons. | Eine verantwortliche Symbolquelle. |
| Mehrere Controls für denselben lokalen Befehl | Pfeil und Auge öffnen dieselbe Ansicht; Info-Button und danebenliegender Button zeigen denselben Hinweis. | Einen kanonischen Auslöser behalten. |
| Mehrere gleichwertige Einstiege im selben Sichtbereich | Identisches Anlegen im Kopf und unmittelbar darunter; klickbarer Titel plus zusätzlicher identischer Öffnenauslöser. | Bewusst einen Zugang auswählen oder eine konkrete notwendige Ausnahme begründen. |

Ein Icon mit mehreren SVG-Pfaden oder `use`-Referenzen ist nicht automatisch eine Mehrfachausgabe. Entscheidend sind unterscheidbare sichtbare Symbole, nicht die Anzahl grafischer DOM-Knoten.

Wiederkehrende fachliche Aktionen auf unterschiedlichen Datensätzen sind keine Redundanz. Ebenso dürfen räumlich weit entfernte notwendige Zugänge nicht pauschal entfernt werden. Lokale Ausnahmen müssen den konkreten Bediennutzen benennen; „war schon so“ genügt nicht.

### R-03 – Keine Bereinigung durch Funktionsverlust

Für jede entfernte Aktion werden verbleibender Auslöser, tatsächlich erreichbares Ziel und getestete Rolle dokumentiert. Nach der Änderung darf keine vorhandene Aufgabe nur noch durch Kenntnis einer URL erreichbar sein.

Unterschiedliche Sicherheitsbedeutungen bleiben unterscheidbar. Ein einzelnes unscharfes Symbol „Öffnen/Bearbeiten/Planen“ ist kein Ersatz für drei tatsächlich unterschiedliche Funktionen.

Keine versteckte Laufzeit-Deduplizierung auf DOM-Ebene. Die Aktion wird an ihrer fachlichen Definition beziehungsweise im geprüften Aufrufer bereinigt, damit Tests und Übersetzungen weiterhin ihre tatsächliche Bedeutung kennen.

## 5. B – Entweder Symbol oder Text, niemals beides

### B-01 – Exklusiver Darstellungsvertrag

Jeder von der Anwendung gestaltete Aktionsbutton verwendet genau einen der folgenden Modi:

| Modus | Sichtbarer Inhalt | Nicht zulässig |
|---|---|---|
| **`icon`** | Ein eindeutiges Aktionssymbol. | Gleichzeitig sichtbare Beschriftung, zweites Dekosymbol oder innerhalb desselben Buttons angehängter Text. |
| **`text`** | Eine verständliche kurze Beschriftung. | Zusätzliches Aktionsicon, Pfeil, Checkmark, dekoratives SVG oder Icon aus einem Pseudoelement. |

Die Regel betrifft native Buttons, als Buttons gestaltete Links, Dialogaktionen, Tabellen-/Kartenaktionen, Filterauslöser, Sammelaktionen, Formularfüsse, Tabs/Segmentumschalter und Wiederherstellungsaktionen. Herkunft des Controls ist unerheblich: gemeinsames Makro, handgeschriebenes Template, JavaScript oder Drittkomponente innerhalb der App.

Es ist erlaubt, in einer Symbolgruppe echte Symbolbuttons und an anderer Stelle verständliche Textbuttons zu verwenden. **Nicht erlaubt ist beides innerhalb desselben Controls.** Für dieselbe Bedeutung und denselben Kontext bleibt die Moduswahl einheitlich.

### B-02 – Auswahl des Modus, einschliesslich späterer Zustände

| Fall | Festlegung |
|---|---|
| Bekannte kompakte Objektaktion | Bestehenden Symbolmodus verwenden. |
| Fachaktion ohne hinreichend eindeutiges Symbol | Reinen kurzen Text verwenden, nicht Icon plus Erklärung. |
| Anmeldung, Wiederherstellung und Sicherheitsbestätigung | Reiner Text, etwa „Anmelden“, „Abbrechen“, „Löschen“ oder „Neu laden“. |
| Textbasierte Bereichs-/Ansichtsauswahl | Reiner Text; kein Häkchen oder Bereichsicon innerhalb des ausgewählten Buttons. |
| Symbolischer Vor-/Zurückauslöser | Reines Symbol mit zugänglichem Namen. |
| Ausschliesslicher Asset-Fallback | Symbol durch Text ersetzen, nicht Text zum defekten Symbol hinzufügen. |

Die Regel ist eine Designentscheidung dieses Projekts, keine allgemeine Aussage, dass kombinierte Buttons grundsätzlich unzulässig oder nicht barrierefrei seien.

**Konkrete Beispiele:** Ein Textbutton „Anmelden“ enthält kein Login-Symbol. Ein Druckersymbol trägt nicht zusätzlich „Drucken“. Ein Texttab „Lagerorte“ enthält kein Archivsymbol. „Beide“ erhält im ausgewählten Zustand kein zusätzliches Häkchen im selben Control.

Die linke Informationsarchitektur wird hier nicht neu gestaltet. Reine Navigationsgruppen, nichtinteraktive Warnhinweise und fachliche Kennzeichnungen sind nicht pauschal Aktionsbuttons. Wo ein Navigationseintrag aber als Aktionsbutton oder Tab/Segment angeboten wird, gilt derselbe Exklusivvertrag. Native Auswahlindikatoren von Checkboxen, Radiofeldern und Selects bleiben funktionsfähig.

### B-03 – Gemeinsamen Renderer tatsächlich exklusiv machen

Im eingesehenen `icon_button()` wird `sem_icon(key)` immer ausgegeben; `show_text=true` ergänzt lediglich Text. Deshalb reicht das Umschalten dieses Parameters für reine Textbuttons nicht. [R3]

Die gemeinsame Komponente braucht einen expliziten Darstellungsmodus mit den zwei gültigen Werten `icon` und `text`. Der konkrete Parametername darf zum bestehenden Projekt passen; seine Bedeutung darf nicht zweideutig sein.

Für die Migration gilt:

- Im Symbolmodus wird nur der Symbolzweig gerendert; im Textmodus nur der Textzweig.
- Bestehende Aufrufer mit `show_text=true` werden auf reinen Text abgebildet und überprüft. Die Bedeutung des alten Parameters nicht unbemerkt ändern, ohne seine Verbraucher und Tests zu migrieren.
- Veraltete Kombinationen von `icon_only` und `show_text` erhalten eine klare Kompatibilitätsregel oder werden nach vollständiger Migration entfernt.
- Im Textmodus entfallen reservierte Iconspalten, Iconabstände, führende Pseudoelemente und leere SVG-Wrapper.
- Eine fehlende Beschriftung wird als Komponentenfehler erkannt; ein leerer Button ist kein Fallback.

Nicht global alle `span`-Inhalte verstecken. Nicht global alle SVGs aus Buttons entfernen. Beide Vorgehensweisen würden jeweils einen der erlaubten Modi beschädigen.

### B-04 – Loading, Auswahl, Zahlen und Feedback dürfen keine Mischform zurückbringen

| Zustand / Sonderfall | Zulässige Darstellung |
|---|---|
| Symbolbutton lädt | Das Aktionssymbol wird vorübergehend durch einen Ladeindikator ersetzt. Nicht beide gleichzeitig. Rückmeldung bleibt zugänglich. |
| Textbutton lädt | Text wechselt bei Bedarf zu „Wird gespeichert …“; kein zusätzlicher Spinner im Button. |
| Textsegment ausgewählt | Auswahl über konsistente Umrandung/Gewichtung und passenden programmatischen Zustand, nicht über angehängtes Symbol. |
| Symbolfilter mit Treffer-/Filteranzahl | Zahl als separat zugeordnete, nichtinteraktive Information ausserhalb der Klickfläche oder ein reiner Textbutton „Filter (2)“. |
| Entfernbarer Filterchip | Textinformation und separater, eindeutig zugeordneter Symbolbutton zum Entfernen; keine zweite Klickfläche mit nochmals gleicher Wirkung. |
| Erfolg / Fehler | Kurze Rückmeldung in der vorgesehenen Meldungszone; kein dauerhaftes Häkchen neben einem Textlabel im Button. |

Ein ausgelagertes Wort direkt neben einem Symbolbutton darf nicht bloss eine optische Umgehung für „Symbol plus Beschriftung“ bilden. Separater Inhalt braucht eine eigenständige fachliche Bedeutung, beispielsweise der ausgewählte Filterwert.

Relevante Zustandswechsel dürfen die Nachbarbuttons nicht verschieben. Eine notwendige Breitenreserve innerhalb eines konkreten Textbuttons ist zulässig; keine neuen grossen Leercontainer.

### B-05 – Sichtbarkeit und zugänglicher Name sind unterschiedliche Ebenen

Symbolbuttons behalten verständliche zugängliche Namen und die bestehenden kontextbezogenen Tooltips. Nicht sichtbare Screenreader-Beschriftung ist kein Verstoss gegen den Symbolmodus. Ein Tooltip ausserhalb des normalen Buttonlayouts ist keine permanente Mischbeschriftung. Das zugängliche Benennen von Buttons ist durch den W3C-Buttonvertrag abgedeckt. [W2]

Bei Textbuttons muss der zugängliche Name die sichtbare Beschriftung enthalten. Unterschiedliche sichtbare und programmatische Aktionsnamen werden nicht zur Umgehung kurzer Labels verwendet. [W3]

Nichtinteraktive Warntexte dürfen ein Statussymbol plus Erklärung enthalten. Die neue Buttonregel darf keine fachlichen Hinweise, Allergeninformationen oder Formularlabels entfernen. Enthält ein Hinweis einen Aktionsbutton, folgt **dieser Button** dem Exklusivvertrag.

## 6. N – Lagerorte und alle Hinweise ohne springende Navigation

### N-01 – Bereichsnavigation steht vor bereichsspezifischen Hinweisen

Für die Stammdatenfamilie wird die Abfolge verbindlich:

```text
Seitenkopf
Bereichsnavigation: Zutaten | Einheiten | Kategorien | Kennzeichnungen | Lagerorte
Toolbar / Suche / vorhandene Filter
Bereichsspezifischer Hinweis, sofern fachlich erforderlich
Arbeitsinhalt / Liste
```

Ein nur für Lagerorte benötigter Hinweis steht nicht vor der gemeinsamen Navigation. Er wird in den betreffenden Inhaltsbereich unterhalb der Navigation und Toolbar verschoben. Erforderliche Information bleibt erhalten; fakultative ausführliche Erklärung erhält einen nicht aufklappenden Zugang nach D-02.

Keinen gleich grossen leeren Hinweiskasten auf allen anderen Tabs reservieren, um den Sprung zu kaschieren. Nicht die komplette Navigation mit absoluten Pixelkoordinaten festnageln. Die gemeinsame Struktur muss stimmen.

Der eingesehene Lagerorte-Hinweis vor dem `<nav>` ist zuerst zu prüfen und an der gemeinsamen Vorlage zu korrigieren. [R2]

### N-02 – Tabwechsel ist kein Neuaufbau des Navigationsrasters

Beim Wechsel zwischen den Stammdatenbereichen bleiben Reihenfolge, Ausrichtung und Bedienflächen der Tabs gleich. Ein ausgewählter Tab darf durch zusätzliches Häkchen, Icon, geändertes Padding oder deutlich breitere Umrandung seine Nachbarn nicht verschieben.

Bereichsspezifische Überschriften, Ladehinweise, Trefferzahlen oder Fehlermeldungen werden nicht vor die wiederkehrende Navigation eingeschoben. Bei dynamischer Aktualisierung soll die gemeinsame Navigation nicht wegen des Nachladens von Bereichsdaten unnötig entfernt und neu eingefügt werden.

Die aktive Kennzeichnung darf wechseln; die Position der übrigen Navigationselemente darf sich dadurch nicht ändern. Ein absichtlicher Wechsel der Sidebar-Gruppe ist von einem unerwarteten Sprung durch ein Infofeld zu unterscheiden.

### N-03 – Seitwärts-, Höhen-, Scroll- und Fokussprünge getrennt untersuchen

Der Prüfauftrag umfasst sowohl die horizontale Bereichsnavigation als auch die linke Sidebar und den Seitenrahmen. „Navigation springt“ darf nicht nur anhand eines einzelnen CSS-Abstands abgeschlossen werden.

| Prüfpfad | Zu untersuchende Ursache | Geforderte Behandlung |
|---|---|---|
| Infofeld erscheint nur in einem Bereich | Bedingter Inhalt vor Navigation oder Titelstruktur. | Inhalt in den vorgesehenen nachgelagerten Bereich verschieben. |
| Dialog öffnet / schliesst | Scrollbar verschwindet, Body-Lock ändert Breite oder Scrollposition. | Kein horizontaler Sprung; vorhandene Scrollposition beim Schliessen sinnvoll erhalten. |
| Inhalt lädt nach | Späte Hinweise, wechselnde Schrift-/Icongeometrie, Austausch des Navigationscontainers. | Gemeinsamen Rahmen stabil halten; Nachladeinhalt innerhalb seiner eigenen Zone. |
| Tab wird fokussiert / ausgewählt | `autofocus`, Ankersprung, `scrollIntoView`, falscher Scrollcontainer. | Nur sachlich nötige Fokusbewegung; kein ungefragter Sprung zum Seitenanfang. |
| Kurze und lange Liste wechseln | Unterschiedliche Scrollbalken, `100vw`-Überlauf oder abweichende Wrapper. | Gleiche verfügbare Arbeitsbreite und nachvollziehbarer Scrollbereich. |

`scrollbar-gutter` kann bei klassischen Scrollbars Platz stabilisieren; Overlay-Scrollbars verhalten sich anders. Der tatsächliche Scrollcontainer und die unterstützten Browser müssen geprüft werden. Nicht mehrere Kompensationen gleichzeitig einbauen oder Scrollbarkeit dauerhaft abschalten. [W4]

Das Entfernen einer Animation, langsameres Animieren oder Smooth-Scrolling ist kein Nachweis, dass der Sprung behoben wurde.

### N-04 – Messbarer Stabilitätsvertrag

Unter identischem Viewport, Zoom, Schrift-/Dichtezustand und ohne absichtliche Benutzerscrollbewegung gilt:

| Übergang | Projekt-Abnahme |
|---|---|
| Lagerorte-Hinweis gegenüber den anderen Stammdatenbereichen | Gemeinsame Tabnavigation bleibt an derselben vorgesehenen Position. |
| Öffnen / Schliessen eines neuen Lesedialogs | Hintergrundzeile, Spalten und Navigation behalten ihre Geometrie. |
| Hover / Fokus / Auswahl eines Text- oder Symbolbuttons | Keine Verschiebung benachbarter Controls. |
| Seitliche Scrollbar kommt hinzu / entfällt | Kein erkennbarer seitlicher Versatz des gemeinsamen Rahmens. |
| Dialog schliesst | Ursprünglicher sichtbarer Auslöser bleibt auffindbar; keine unbeabsichtigte Rückkehr an den Seitenanfang. |

**Messtoleranz:** höchstens 1 CSS-Pixel Abweichung in den relevanten Koordinaten bei ansonsten gleichen Bedingungen, als technische Rundungstoleranz. Das ist ein Projektziel, kein gemessener IST-Wert und kein pauschaler Webstandard.

Für Tabellen zusätzlich Zeilenhöhe und Position der Folgezeile prüfen. Für Navigation Position und Grösse stabiler Referenzelemente messen. Dokument- und interne Scrollposition getrennt erfassen. Nicht ausschliesslich einen aggregierten Layoutscore verwenden.

Ein tatsächlicher Breakpointwechsel, eine benutzerseitige Schriftvergrösserung oder bewusst hinzugefügte Fachdaten ist kein identischer Zustand. Solche Fälle werden mit eigener erwarteter Geometrie geprüft, nicht durch Abschneiden des Inhalts auf den Desktopwert gezwungen.

## 7. App-weite Umsetzung statt sechs Screenshot-Fixes

### 7.1 Zusätzliche Inventur – ausschliesslich diese fünf Deltas

Erweitere das bestehende Audit. Erfasse jede reale Oberfläche, die Inhaltsdetails, optionale Status-/Metadatenslots, Aktionsbuttons oder gemeinsame Navigation rendert.

Mindestens zu berücksichtigen sind Stammdaten mit allen Unterbereichen, Planungsansichten, Menülisten, Rezepte und deren Editoren, Kochbücher, Gerichtvorlagen, Einkauf, Bestellung, Lager, Kalkulation, Vorlagen, Vorschauen, Bildschirmverwaltung, Benutzer-/Schnittstellenverwaltung und Einstellungen. Hinzu kommen vorhandene Dialoge, Login-/Fehleransichten sowie interaktive öffentliche Oberflächen, soweit sie diese Komponenten tatsächlich verwenden.

Diese Aufzählung ist ein Prüfauftrag, keine Aussage, dass jedes Modul einen Fehler hat. Maschinenendpoints ohne visuelle Oberfläche benötigen keine Buttonmigration. Nichtinteraktive Druck-/Signage-Inhalte dürfen nicht durch globale CSS-Bereinigungen beschädigt werden.

| Zusätzliche Auditspalte | Inhalt |
|---|---|
| Fundstelle | Reale Route, Template, Makro, JS-/CSS-Quelle. |
| Delta | D, P, R, B oder N; mehrere zulässig. |
| Ausgangsverhalten | Was wird geöffnet, gerendert, dupliziert oder verschoben? |
| Inhalt / Aktionsabsicht | Objekt, Kontext und relevante Wirkung. |
| Ersatzentscheidung | Statischer Inhalt, Lesedialog, vorhandene Detailseite; reiner Symbol-/Textmodus; Wrapperentfall. |
| Ausnahme / Abgrenzung | Beispielsweise echtes Select, native Checkbox oder Navigation statt Inhaltsdetails. |
| Nachweis | Prüffall, Rolle, Zustand, Revision, Screenshot/Interaktionsmessung. |
| Ergebnis | Bestanden, fehlgeschlagen, nicht geprüft oder nicht anwendbar mit Begründung. |

### 7.2 Technische Suchsignale, nicht automatische Löschregeln

```text
D: details / summary / accordion / collapse / disclosure_section
   Details ein- oder ausklappen / Weitere Optionen / Mehr anzeigen
   aria-expanded mit nachgelagertem Inhaltsbereich
   dynamische Zusatz-tr / Row-Expansion / wechselnde Inhalts- oder Grid-Hoehe

P: empty_value / admin-empty-value / leere status-, meta- und subtitle-Slots
   einzelne UI-generierte -, –, —, − / &ndash; / &mdash;
   ::before / ::after / content / Leerzeichen als Status-Workaround

R: mehrere action-Definitionen je Kontext / Titel-Link plus identischer Button
   Iconausgabe im Makro UND im Aufrufer / mehrfacher Chevron
   gleiche Wirkung mit verschiedenen Labels oder Symbolen

B: show_text / icon_only / icon_button / handgeschriebene btn-Elemente
   SVG + sichtbarer Text / Pseudoelement-Icon + Text
   Loading-, Selected-, Success- und Disabled-Zustaende

N: Hinweise vor nav / bedingte Headerzeilen / nav-pills
   Scroll-Lock / scrollbar / 100vw / autofocus / scrollIntoView
   wechselnde Wrapper, Teilrenderings und optionale Statusbloecke
```

Jeder Treffer wird klassifiziert. Keine globale Suche-und-Ersetze-Aktion für `details`, `-`, `svg` oder `span`. Komponentenverträge und Aufrufer werden gemeinsam angepasst, nicht nur das sichtbare Ergebnis mit CSS überdeckt.

### 7.3 Direkte Integrationspunkte

Die eingesehenen Dateien `_macros.html`, `_semantic.html`, `grundlagen.html` und `kochbuecher.html` sind Startpunkte. Darüber hinaus müssen alle Verbraucher ihrer Helper, dazugehörige Styles, Initialisierungscode und Tests ermittelt werden.

Besondere Prüfstellen sind `disclosure_section`, `icon_summary`, `hint`, `filter_bar`, `list_row`, `empty_value` und `icon_button`. Namen allein belegen nicht, dass ein Helper verboten ist: Ein Hinweis kann statisch, im Dialog oder als bisheriger Aufklapper gerendert werden.

Bestehende Blöcke nicht nur in einen Dialog kopieren, wenn dadurch doppelte Element-IDs, verschachtelte Formulare, falsche Submit-Ziele oder verlorene Feldzuordnungen entstehen. Der bisherige Fachinhalt und seine Wirkung müssen im Ersatz weiterhin dieselben sein. Das ist eine Migrationsschutzregel, kein neuer Formularauftrag.

## 8. Textuelle Zielausschnitte nur für die neuen Entscheidungen

Die Grossbuchstaben in eckigen Klammern sind Symbolplatzhalter, keine geplanten sichtbaren Textlabels.

### 8.1 Wochenvorgaben ohne Inline-Expansion

```text
BEREICH                         WOCHENENDREGEL             STATUS                   AKTION
Mitarbeitende und externe Gaeste Nicht moeglich             Zeiten fehlen            [INFO]
Patientinnen und Patienten      Je Mahlzeit festgelegt     Zeiten fehlen            [INFO]

Betätigung von INFO öffnet den konkret zugehörigen Lesedialog.
Die Tabelle bleibt unverändert; keine Zusatzzeile und keine wachsende Zelle.
```

### 8.2 Fehlender optionaler Status ohne Strich

```text
VORHER:  Apfelessig      Milliliter · Trockenlager       —     [EDIT] [ARCHIVE]
NACHHER: Apfelessig      Milliliter · Trockenlager             [EDIT] [ARCHIVE]

Die Illustration reserviert keinen leeren Statuscontainer.
Relevante echte Statusinformationen bleiben dagegen sichtbar.
```

### 8.3 Exklusive Buttons

```text
ZULAESSIG:   [EDIT-ICON]        oder        [Bearbeiten]
ZULAESSIG:   [Anmelden]                    [Neu laden]
UNZULAESSIG: [EDIT-ICON Bearbeiten]         [LOGIN-ICON Anmelden]
```

### 8.4 Lagerorte mit stabiler Navigation

```text
Lagerorte                                                [ADD]
Zutaten | Einheiten | Kategorien | Kennzeichnungen | Lagerorte
[vorhandene Toolbar]

[Kurzer fachlicher Hinweis ausschliesslich in dieser Inhaltszone]
[Lagerortliste]

Beim Wechsel zu Zutaten bleiben Kopf-/Navigationsstruktur und Tabpositionen stabil.
Ein bereichsspezifischer Hinweis wird nicht vor die Tabs eingeschoben.
```

## 9. Zusätzliche Abnahmefälle

Die folgenden Fälle prüfen nur dieses Addendum. Bereits bestehende Gesamttests werden weiterverwendet, nicht hier erneut spezifiziert. Visuelle Vergleiche müssen denselben Datenstand und dieselbe getestete Revision verwenden.

| ID | Bezug | Prüfung | Erwartetes Ergebnis |
|---|---|---|---|
| DX-T01 | D-01/03 | Wochenvorgaben eines Bereichs öffnen und schliessen. | Keine vergrösserte Tabellenzelle; Folgezeile, Spalten und Auslöser bleiben stabil. |
| DX-T02 | D-04 | Langen Prüfhinweis eines Patienten-Menüs öffnen. | Vollständiger korrekter Inhalt im vorgesehenen Ziel, kein Abschneiden und keine zusätzliche Zeilenhöhe. |
| DX-T03 | D-02/04 | Kritischer Kurzstatus mit ausführlichem Zusatzhinweis. | Relevante Warnung bleibt in der Übersicht; nur Zusatzinhalt wechselt in die Detaildarstellung. |
| DX-T04 | D-01 | Karten, Editorabschnitte und Inhalte innerhalb von Dialogen prüfen. | Keine verbliebenen Inhaltsakkordeons, auch nicht in Ersatzdialogen. |
| DX-T05 | D-01/02 | Bisherige Filteraufklapper auf Desktop und mobil bedienen. | Filterdialog oder statische Felder; kein Verdrängen der Arbeitsliste durch Öffnen. |
| DX-T06 | D-02 | Optionale Formularfelder in den gewählten Ersatz überführen. | Eingaben, Fehlerzuordnung und Speicherumfang bleiben korrekt; kein neues versehentliches Teilformular. |
| DX-T07 | D-02 | Zusätzliche Einträge eines Kalendertags erschliessen. | Alle angekündigten Inhalte erreichbar, Monatsraster ohne Aufklapp-Zuwachs. |
| DX-T08 | D-05 | Lesedialog per Tastatur öffnen, lesen und schliessen. | Sinnvoller Fokus, funktionierende Modalbedienung, Rückkehr zum Auslöser; kein zusätzlicher gleicher Schliessbutton. |
| DX-T09 | D-01 | Sidebar, echte Selects und Datums-/Zeitpicker prüfen. | Funktionieren weiterhin; keine Kollateralschäden durch pauschales Entfernen von Disclosure-Tags. |
| DX-T10 | P-01/02 | Optionale Status-/Metadatenslots mit `None`, leerem String und Leerraum rendern. | Kein Strich, kein Ersatzpunkt und kein leerer Statuswrapper. |
| DX-T11 | P-02/03 | Nur leeres Markup beziehungsweise bisherigen Leerzeichen-Workaround übergeben. | Explizite Leerwertbehandlung statt scheinbar gefülltem Statusslot. |
| DX-T12 | P-02 | Nullwerte, boolesche Werte, negative Mengen und Bindestriche in Namen prüfen. | Fachwerte unverändert; keine globale Zeichenbereinigung. |
| DX-T13 | P-02 | Fachlich fehlenden Bestand/Preis gegenüber optionalem Leerstatus darstellen. | Konkrete Fehlangabe bleibt sichtbar; kein Gleichsetzen mit dekorativ leerem Slot. |
| DX-T14 | P-03 | Echte Tabelle und flexible Liste mit unterschiedlich besetzten Statusfeldern. | Tabellenüberschriften bleiben zugeordnet; keine verwaisten Abstände vor Aktionsgruppen. |
| DX-T15 | R-01/02 | Zwei verschiedene Symbole mit nachgewiesen identischem lokalem Ziel und Modus. | Ein kanonischer Auslöser; verbleibendes Ziel funktioniert. |
| DX-T16 | R-01 | Kochbuch öffnen und bearbeiten. | Tatsächliche Wirkung beider Endpoints dokumentiert; belegter Lese-/Edit-Unterschied bleibt erhalten. |
| DX-T17 | R-01 | Gleiche Basis-URL mit unterschiedlichen Revisionen, Ankern oder Formularzwecken. | Keine falsche Deduplizierung nach URL oder Icon. |
| DX-T18 | R-02 | Symbol im Makro, im Aufrufer und als CSS-Pseudoelement erzeugen. | Mehrfachausgabe erkannt und an der verantwortlichen Quelle entfernt. |
| DX-T19 | R-02 | Klickbarer Objekttitel plus benachbarter identischer Öffnenbutton. | Kanonischer Zugang oder konkret begründeter notwendiger Doppelzugang dokumentiert. |
| DX-T20 | R-02 | Gleiches Symbol auf mehreren Datensätzen und in verschiedenen Aufgabenbereichen. | Keine fälschliche globale Deduplizierung. |
| DX-T21 | R-03 | Jeden entfernten Auslöser mit den relevanten Rollen nachprüfen. | Aufgabe weiterhin erreichbar; kein versteckter Funktionsverlust. |
| DX-T22 | B-01/03 | Symbolmodus aller gemeinsamen und lokalen Renderer. | Genau ein sichtbares Aktionssymbol, keine permanente sichtbare Beschriftung im selben Control. |
| DX-T23 | B-01/03 | Textmodus derselben Renderer. | Text ohne zusätzliches Icon, Pfeil, Checkmark oder reservierte Iconlücke. |
| DX-T24 | B-03 | Alle bisherigen Kombinationen aus `show_text` und `icon_only` aufrufen. | Eindeutige Migration oder erklärter Vertragsfehler, kein stiller Mischmodus. |
| DX-T25 | B-02 | Login, 403-/500-Seite und destruktiven Bestätigungsdialog öffnen. | Reine Textaktionen; alte Icon-plus-Text-Ausnahme greift nicht mehr. |
| DX-T26 | B-02/04 | Stammdaten-/Bereichstabs und textbasierte Segmente auswählen. | Kein angehängtes Icon/Häkchen; Auswahl bleibt erkennbar, Nachbarn bleiben stabil. |
| DX-T27 | B-04 | Symbol- und Textbuttons in Lade-, Erfolgs-, Fehler- und Disabled-Zustand versetzen. | Kein Zustand erzeugt Symbol plus sichtbaren Text oder zwei Status-/Aktionsicons. |
| DX-T28 | B-04 | Aktive Filter, Zähler und entfernbare Filterchips darstellen. | Reiner Buttonmodus; Datenwert getrennt und eindeutig zugeordnet, keine doppelte Entfernenwirkung. |
| DX-T29 | B-01/03 | Handgeschriebene Buttons, JS-Ausgabe, CSS-Pseudoelemente und Drittkomponenten prüfen. | Keine versteckte zweite Symbolquelle oder unkontrollierte Mischvariante. |
| DX-T30 | B-05 | Zugängliche Namen in Symbol- und Textmodus prüfen. | Symbol ist benannt; Textlabel im zugänglichen Namen enthalten; keine bedeutungslosen leeren Controls. |
| DX-T31 | B-02/04 | Icon-Asset blockieren und vorhandenen Fallback auslösen. | Verständlicher exklusiver Ersatz, kein defektes Icon neben neu angehängtem Text. |
| DX-T32 | B-01/05 | Tooltip, nichtinteraktive Warnung und native Checkbox vergleichen. | Tooltip/Statusinformation und native Auswahlindikatoren bleiben erhalten; keine pauschale Text- oder SVG-Ausblendung. |
| DX-T33 | N-01/02 | Zutaten → Lagerorte → Einheiten → Kategorien → Kennzeichnungen → Zutaten. | Gemeinsame Tabpositionen und Sidebar-Rahmen bleiben unter vergleichbaren Bedingungen stabil. |
| DX-T34 | N-01/04 | Lagerorte-Hinweis ein-/ausblenden beziehungsweise dessen vorgesehenen Lesezugang nutzen. | Hinweis bleibt unterhalb der Navigation; Tabs verschieben sich nicht. |
| DX-T35 | N-03/04 | Kurze und lange Liste mit klassischem Scrollbalken sowie Overlay-Scrollbar testen. | Kein unkontrollierter horizontaler Versatz; funktionierende Scrollbarkeit. |
| DX-T36 | N-03/04 | Dialog öffnen/schliessen, während die Seite weiter unten gescrollt ist. | Scrollposition und sichtbare Navigation bleiben sinnvoll erhalten, kein Sprung an den Anfang. |
| DX-T37 | N-02/03 | Bereichsdaten, Hinweis und Schrift-/Iconassets verzögert laden. | Kein nachträgliches Einschieben oberhalb der Tabs und kein unnötiger Neuaufbau der Navigation. |
| DX-T38 | N-02/03 | Tabwechsel mit Hover, Tastaturfokus und anschliessendem Browser-Zurück. | Keine Breitenänderung durch Auswahlzeichen; kein unberechtigter Autofokus-/Ankersprung. |
| DX-T39 | N-04 | Dieselben Übergänge in breiter, mittlerer und schmaler vorhandener Testansicht prüfen. | Neue Stabilitätsziele je Layout eingehalten; echte Breakpointwechsel gesondert beurteilt. |
| DX-T40 | N-01/03 | Bereichsspezifischen Hinweis in Rollen-, Leer- und Fehlerzuständen anzeigen. | Gemeinsame Navigation bleibt vor den variablen Inhalten; keine grossen leeren Ersatzboxen. |
| DX-T41 | D/P/R/B/N | Lange Inhalte und Übersetzungen in allen fünf geänderten Komponentenfamilien. | Keine Rückkehr zu Aufklappern oder Mischbuttons als Platznotlösung. |
| DX-T42 | D/N | Zeilen- und Navigationsgeometrie vor, während und nach relevanten Interaktionen messen. | Projekttoleranz eingehalten; Messprotokoll statt ausschliesslich eines statischen Screenshots. |
| DX-T43 | D/P/R/B | Gemeinsame Komponentenregeln und Quellenaudit gegen neue Altpattern-Fundstellen testen. | Verbotene Renderfälle schlagen fehl; native Ausnahmen sind klassifiziert statt blind ausgeblendet. |
| DX-T44 | Alle | Unbeteiligte nichtinteraktive Ausgaben und vorhandene Fachfunktionen nach Integration prüfen. | Keine Schäden durch globale Ersetzungen; keine neuen unzugänglichen Inhalte oder entfernten Aufgaben. |

Für DX-T42 sind zu protokollieren: Referenzelement, Ausgangs- und Endkoordinaten, Zeilenhöhe, Scrollposition, Viewport, Scrollbartyp und getestete Revision. Die Messung soll den Übergang einschliessen, nicht nur zwei zufällig passende Endbilder.

Browserprüfungen untersuchen die tatsächlich sichtbare Ausgabe einschliesslich Pseudoelementen und dynamischen Zuständen. Ein Check „enthält SVG und enthält Textknoten“ allein genügt nicht: zugänglich verborgener Text, mehrteilige SVG-Pfade und separate Statusinhalte müssen richtig klassifiziert werden.

## 10. Kleine Ergänzungspakete für die laufende Umsetzung

| Paket | Ausschliesslicher Zusatzumfang | Fertig, wenn … |
|---|---|---|
| **DELTA-1 – Inventur und Entscheidungen** | D/P/R/B/N in die vorhandene Matrix aufnehmen; Ersatztyp, Buttonmodus und Redundanzfälle festlegen. | Alle realen Fundstellen klassifiziert sind; keine alten Ausnahmen unbeachtet weitergelten. |
| **DELTA-2 – Gemeinsame Renderer** | Leere Slots, exklusive Buttonausgabe und gemeinsame nicht aufklappende Detaildarstellung korrigieren. | Vertragstests bestehen und Verbraucher eine eindeutige Migrationsschnittstelle haben. |
| **DELTA-3 – Verbrauchermigration** | Fundstellen im gesamten Projekt umstellen, einschliesslich Spezial-, Fehler- und Loginoberflächen. | Keine verbotenen Inhaltsaufklapper, Mischbuttons oder unbegründeten Duplikate mehr gerendert werden. |
| **DELTA-4 – Navigation und Geometrie** | Lagerorte-Referenzfall sowie Info-, Tab-, Scrollbar- und Dialogübergänge korrigieren. | Die neuen Stabilitätsmessungen gegen den integrierten Stand bestehen. |
| **DELTA-5 – Regression und Vertragsbereinigung** | DX-T01 bis DX-T44 ausführen; gezielt abgelöste Manifest-/Testregeln aktualisieren. | Ergebnisse und reale Restpunkte vollständig vorliegen. |

Bestehende Änderungen der laufenden Session nicht zurücksetzen. Gemeinsame Makros und Layoutdateien erhalten eine klare Schreibverantwortung. Parallele Arbeiten dürfen nicht gleichzeitig unterschiedliche Buttonmodi oder Dialogverträge einführen.

Ein Pilot auf einer Seite genügt zum Prüfen einer Komponente, nicht zur Abnahme des projektweiten Auftrags. Keine zusätzliche pauschale Produktionsfreigabe durch dieses Dokument.

## 11. Zusätzliche Definition of Done

Dieses Addendum ist nur abgeschlossen, wenn:

1. Alle gefundenen Inhaltsaufklapper durch einen dokumentierten, nicht aufklappenden Ersatz ersetzt sind; kein fachlicher Inhalt ging verloren.
2. Optionale Leerwerte keine Striche oder leeren Ersatzcontainer vor Aktionen erzeugen; echte Daten bleiben korrekt.
3. Jede Redundanzentscheidung auf der tatsächlichen Wirkung beruht und entfernte Zugänge einen nachgewiesen funktionierenden Ersatz besitzen.
4. Alle betroffenen Controls in jedem geprüften Zustand entweder Symbol oder Text zeigen; die alte Login-/Fehlerseiten-Ausnahme existiert nicht mehr.
5. Lagerorte und vergleichbare Informationsfelder die gemeinsame Navigation nicht verschieben und die neuen Geometriemessungen bestehen.
6. Alle anwendbaren DX-Fälle geprüft sind. „Nicht geprüft“ bleibt von „nicht anwendbar“ getrennt; fehlgeschlagene Fälle werden nicht durch neue Screenshot-Baselines als erledigt erklärt.

Der Abschlussbericht enthält nur die Änderungsergebnisse dieser fünf Deltas: betroffene gemeinsame Komponenten, migrierte Fundstellen, entfernte echte Duplikate, neue Ersatzdarstellungen, Mess-/Testnachweise und verbleibende Punkte. Die allgemeinen älteren SDDs werden nicht erneut als Leistungsumfang aufgezählt.

## 12. Quellen, Bezug und Gültigkeitsgrenzen

### 12.1 Bestehende Dokumente – nur als Bezug

- **B1:** `SDD_Dishboard_UI_Optimierung_Ergaenzung.md`, insbesondere bisheriger Abschnitt 5.9.
- **B2:** `SDD_Dishboard_Direkte_Symbolaktionen_Appweit.md`, insbesondere bisherige Abgrenzung fachlicher Detailabschnitte.
- **B3:** `SDD_Dishboard_UI_Blinde_Flecken_Addendum.md`, insbesondere BF-17 und BF-21.
- **B4:** `SDD_Dishboard_Errorhandling_Auth_und_Fehlerseiten_Addendum.md`, insbesondere bisherige Icon-plus-Text-Ausnahme.

Die neue Anweisung und ihre beiden Nachträge sind die Grundlage dieses Addendums. Nur die in Abschnitt 0.1 benannten Konflikte werden aufgelöst; alle übrigen älteren Aufträge bleiben ausserhalb dieses Dokuments.

### 12.2 Repository-Nachweise

Gezielte Einsicht über den verbundenen GitHub-Zugang am 1. Oktober 2026, Repository `joehomeskillet/Dishboard`, Standardbranch. Die angegebenen SHA-Werte sind **Datei-/Blob-SHAs**, keine Deployment- oder Gesamtcommit-Nachweise.

| Quelle | Repositorypfad | Eingesehener Bereich / Blob-SHA |
|---|---|---|
| **R1** | `reference_scaffold/cafeteria/templates/admin/_macros.html` | Angeforderte Zeilen 430–525; `a0de4dcd6976432b3348ccbef9d2cf0e05b27034`. |
| **R2** | `reference_scaffold/cafeteria/templates/admin/grundlagen.html` | Angeforderte Zeilen 1–155; `adb8e4ec3f2bf6122684c6e198e55a1b347d98f6`. |
| **R3** | `reference_scaffold/cafeteria/templates/ui/_semantic.html` | Angeforderte Zeilen 47–124; `7c9f0d656c2af9d6efbabe3424420974103dfa00`. |
| **R4** | `reference_scaffold/cafeteria/templates/admin/kochbuecher.html` | Angeforderte Zeilen 1–110; `9647003bf6c813a40d1a7f695742f40d86e270bb`. |

Die tatsächlichen Routenwirkungen und Geometrien wurden für die Erstellung dieses Dokuments nicht im Browser ausgeführt. Insbesondere ist die Kausalität des gemeldeten Navigationssprungs durch die Struktur gut begründet, aber noch kein gemessener Fehlernachweis des Deployments.

### 12.3 Technische Primärquellen

Am 1. Oktober 2026 eingesehen. Die Quellen unterstützen einzelne technische Verträge, nicht das projektspezifische Verbot von Akkordeons oder kombinierten Buttons. Keine pauschale Barrierefreiheits- oder Browserkompatibilitätsbestätigung.

| Quelle | Verwendung |
|---|---|
| **W1 – W3C WAI: Dialog (Modal) Pattern** | Fokus, Modalbedienung und Rückkehr aus dem Ersatzdialog. |
| **W2 – W3C WAI: Button Pattern** | Zugängliche Namen und passende Buttonzustände. |
| **W3 – W3C WAI: Understanding SC 2.5.3, Label in Name** | Sichtbare Textbeschriftung im zugänglichen Namen. |
| **W4 – MDN: scrollbar-gutter** | Stabile Scrollbarreserve und Unterscheidung klassischer/Overlay-Scrollbars. |

```text
W1 https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/
W2 https://www.w3.org/WAI/ARIA/apg/patterns/button/
W3 https://www.w3.org/WAI/WCAG22/Understanding/label-in-name.html
W4 https://developer.mozilla.org/en-US/docs/Web/CSS/Reference/Properties/scrollbar-gutter
```

---

**Neue Leitentscheidung:** Keine aufklappenden Inhaltsflächen. Keine bedeutungslosen Striche. Keine ungeprüften Doppelaktionen. Jeder Button ausschliesslich Symbol oder Text. Informationen verändern den Arbeitsinhalt, nicht die Position der Navigation.
