# Dishboard – Ergänzung der laufenden /goal-Session
## Einheitliche Listen · Symbolbuttons · einfache, ruhige Bedienung

**Auftragstyp:** verbindliche Ergänzung des laufenden Goals, kein Neustart und kein unabhängiges Redesign.

**Priorität:** Die gesamte Anwendung soll simpel, konsistent und nicht überladen wirken. Nicht nur Textbuttons durch Icons ersetzen, sondern unnötige sichtbare Bedienelemente, Wiederholungen und Verwaltungsdetails reduzieren.

**Geltungsbereich:** alle bestehenden und neu entstehenden administrativen Oberflächen von Dishboard, beide Profile, alle erreichbaren Rollen- und Zustandsvarianten. Öffentliche Menüpläne, Druckansichten und Digital Signage behalten ihre lesbaren Inhalte; sie werden nicht in symbolbasierte Verwaltungsoberflächen umgebaut.

---

## 0. Direkte Arbeitsanweisung

Ergänze das aktive `/goal` um die folgende Spezifikation. Behalte den bisherigen Arbeitsstand und alle fachlichen Anforderungen. Starte kein zweites konkurrierendes Goal.

Behandle diesen Auftrag nicht als weiteren oberflächlichen CSS-Polish. Die Screenshots zeigen mehrere unterschiedliche Listen-, Button-, Filter- und Statusmuster innerhalb derselben Anwendung. Konsolidiere die zugrunde liegenden Komponenten und migriere ihre Verwendungen appweit.

Die aktuell präzisierte Nutzervorgabe ersetzt ältere Regeln, die standardmässig sichtbare Beschriftungen neben Aktionsicons verlangt haben:

> **Aktionsbuttons sind standardmässig reine Symbolbuttons. Gleiche Aktionen sehen überall gleich aus und funktionieren gleich. Die Standardansicht zeigt nur das, was man für die aktuelle Aufgabe braucht.**

Das bedeutet ausdrücklich nicht, Fachinhalte durch schwer verständliche Piktogramme zu ersetzen. Gerichtnamen, Mengen, Termine, Formulareingaben und notwendige Orientierung bleiben lesbarer Text.

Arbeite im bestehenden Flask-/Jinja-/Tabler-Stack. Nutze und konsolidiere vorhandene Design-Tokens, Makros, UI-Komponenten und das bestehende Symbolkonzept. Kein Frameworkwechsel, keine neue parallele Komponentenwelt und kein zusätzliches Theme.

Bleibe im vereinbarten Orchestrator-Modus: kleine überprüfbare Arbeitspakete, Implementierung durch verfügbare Worker, unabhängige Prüfung und kontrollierte Zusammenführung. Parallele Bearbeitung erst nach abgestimmten gemeinsamen Komponentenverträgen. Erfinde weder Agentenläufe noch Testergebnisse.

**Leitsatz für jede Änderung:** Weniger sichtbar, aber nicht weniger verständlich. Kompakter, aber nicht kleiner und schwerer bedienbar.

---

## 1. Ziel und Nicht-Ziele

### 1.1 Gewünschtes Ergebnis

Eine Benutzerin soll ein bekanntes Bedienmuster auf jeder anderen Seite wiedererkennen: gleicher Seitenkopf, gleiche Such- und Filterlogik, gleiche Listenanatomie, gleiche Aktionsposition, gleiche Icons und gleiche Statusdarstellung.

Die Inhalte stehen im Vordergrund. Die Oberfläche soll nicht wie eine Sammlung unterschiedlicher Verwaltungsformulare oder wie ein Dashboard voller Kennzahlen, Warnkarten und Buttons wirken.

Entscheidungsreihenfolge:

1. Fachliche Richtigkeit und sichere Bedienung erhalten.
2. Unnötige sichtbare Komplexität entfernen.
3. Bestehende Muster vereinheitlichen.
4. Verfügbaren Platz sinnvoll nutzen.

Platzgewinn durch kleinere Schrift, winzige Klickziele oder das Verbergen wichtiger Warnungen ist keine akzeptierte Verbesserung.

### 1.2 Nicht Bestandteil dieses Auftrags

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Die Erlaubnis, seltene Aktionen ins Überlaufmenü zu verschieben, ist abgelöst. Vorhandene zulässige Befehle bleiben direkt erreichbar; keine Funktionen erfinden oder ersatzlos entfernen.

Keine neuen Fachmodule, kein Umbau des Datenmodells, keine Änderung von Freigaberegeln und keine pauschale Migration von Daten. Keine zusätzlichen Ansichts-, Dichte-, Experten- oder Personalisierungsschalter nur zur Lösung dieses UI-Problems.

Bestehende Funktionen werden nicht ersatzlos entfernt. Seltene Aktionen dürfen in das gemeinsame Überlaufmenü wandern. Offensichtlich redundante Bedienelemente dürfen zusammengeführt werden.

---

## 2. Sichtbare Ausgangsprobleme aus den Referenzbildern

Die folgenden Beobachtungen beziehen sich auf die bereitgestellten Screenshots, nicht auf einen behaupteten Live-Audit. Ermittle im Repository die tatsächlich zuständigen Routen, Templates und Komponenten.

| Ansicht | Sichtbares Problem | Geforderte Korrektur |
|---|---|---|
| Patienten-Wochenplan | Mehrere Statuskarten, viele wiederholte Prüfhinweise, grosse Bearbeiten-Buttons, auseinandergezogene Aktionen für Suppe und Dessert. | Ein kompakter Wochenkontext, gebündelte Prüfhinweise, einheitliche Menüzeilen und kleine kontextbezogene Symbolaktionen. |
| Wochenübersicht | Eigenes Tabellenmuster, grosse Öffnen-/Mehr-Buttons, wiederholter Prüfstatus und viel Abstand vor der eigentlichen Liste. | Gemeinsame Listenhülle, kompakte Statusspalte und dieselbe Aktionsgruppe wie auf anderen Listen. |
| Küchenkalender | Wiederholte Bereichs-/Mahlzeittexte in engen Zellen, grosse Informationsleiste und isoliertes Infozeichen. | Ein kompakter Kalenderkopf, einheitliche Eintragsdarstellung und klarer Zugang zu weiteren Tagesinhalten. |
| Menüs | Hohe Zeilen, permanente Details-Zeile, wiederholte Warntexte und breite Bearbeiten-Buttons. | Gemeinsame kompakte Datensatzzeile; Details erst bei Bedarf; Warnungen ohne redundante Textblöcke. |
| Bausteine | Anderes Tabellen-, Badge- und Filtermuster; in vielen Zeilen dieselben Zuordnungs- und Herkunftstexte. | Einheitliche Liste und Filterleiste; normale Kontextinformationen bündeln, relevante Ausnahmen sichtbar lassen. |
| Zutaten | Andere Link- und Listenoptik, zusätzliche Containerüberschrift, zwei sichtbare Filterbedienungen und bereits teilweise reine Iconbuttons. | Dasselbe Listen- und Buttonsystem; genau ein Filtereinstieg; keine doppelte Überschrift. |
| Rezepte | Jede Zeile wirkt wie eine eigene abgerundete Karte; grosse Aktionsbuttons und wiederholte Entwurf-Badges. | Eine zusammenhängende Liste mit standardisierten Zeilen und Statusdarstellungen. |
| Gerichtvorlagen | Wiederholte Rezeptnamen, viele zweite Textzeilen, kaum informative Strich-Spalten und breite Einplanen-Buttons. | Nur entscheidungsrelevante Spalten, technische Historie in Details, standardisierte Symbolaktionen. |
| Lager | Flächige Warnung und in jeder Zeile erneut ein langes Warnbadge; wiederum andere Tabellenoptik. | Ein klarer Gesamthinweis und kompakte, weiterhin eindeutige Bestandsinformation je Datensatz. |

Diese Seiten sind Pflichtreferenzen, keine abschliessende Liste. Prüfe auch Kochbücher, Einkaufslisten, Bestellungen, Kalkulation, Einstellungen, Editor-Unterlisten, Dialoge, Suchergebnisse und weitere vorhandene Verwaltungsseiten.

Auch uneinheitliche Leer-, Lade-, Fehler-, Archiv- und Nur-Lesen-Zustände gehören zum Auftrag.

---

## 3. Verbindliches Einfachheitsbudget

### 3.1 Seitenkopf

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Das Limit von zwei Zusatzaktionen und der Verweis weiterer Befehle ins Überlaufmenü sind abgelöst. Alle verfügbaren Kopfaktionen erscheinen direkt. Maximal eine gefüllte Primärgewichtung und die Regeln für Kontext/Leerraum bleiben erhalten.

Ein normaler Seitenkopf besteht aus Titel, bei Bedarf einem kurzen Kontext und einer kleinen Aktionsgruppe. Maximal eine fachliche Primäraktion erhält eine gefüllte Akzentfläche. Daneben stehen höchstens zwei zusätzliche fachliche Aktionen; weitere Aktionen gehören in das Überlaufmenü.

Datumsnavigation und Profilauswahl sind Kontextsteuerungen und werden nicht künstlich in dieses Aktionslimit gepresst. Trotzdem müssen sie als eine zusammengehörige, kompakte Gruppe erscheinen.

Entferne standardmässige grosse Informationskarten, wenn sie nur bereits sichtbare Angaben wiederholen: aktives Profil, eingestellter Monat, Filterstatus oder Trefferzahl. Ein Profil benötigt nicht gleichzeitig eine Infokarte, einen ausgewählten Tab und einen weiteren erklärenden Satz.

Beschreibungen unter dem Titel nur behalten, wenn sie eine echte Unklarheit auflösen. Keine generischen Bedienungsanleitungen auf jeder Seite. Leere Infobereiche und alleinstehende Infoicons ohne hilfreichen Inhalt vollständig entfernen, einschliesslich ihrer Abstände.

### 3.2 Datensatzaktionen

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Das Zwei-Button-Budget, Hauptaktion plus Überlauf und das Verbot eines permanenten Symbolstreifens sind abgelöst. Alle verfügbaren Aktionen erscheinen direkt, schmal mit sichtbarem Umbruch; leere Gruppen und erfundene Funktionen bleiben ausgeschlossen.

In der normalen Datensatzzeile sind rechts maximal zwei eigenständige Aktionsbuttons sichtbar:

- die wichtigste tatsächlich benötigte Datensatzaktion;
- das Überlaufmenü, sofern es weitere Aktionen enthält.

Ein leeres Überlaufmenü wird nicht gerendert. Eine Zeile ohne mögliche Aktion erhält keinen dekorativen Button und keinen Platzhalter.

Kein permanenter Streifen aus Bearbeiten, Öffnen, Kopieren, Archivieren, Löschen, Drucken und Exportieren. Icons reduzieren nicht automatisch Überladung; auch sieben kleine Icons sind zu viel.

### 3.3 Inhalt und Details

Die Standardzeile zeigt einen verständlichen Hauptinhalt und höchstens eine sekundäre Informationszeile. Zusätzliche Metadaten, technische Zuordnungen, Versionshistorie und selten benötigte Angaben liegen hinter dem gemeinsamen Detailmuster.

Diese Regel ist keine Abschneideregel für wichtige Daten: Lange Gerichtnamen dürfen sinnvoll umbrechen; notwendige Warnungen bleiben verständlich. Fehlende Inhalte dürfen nicht durch Ellipsen unsichtbar werden, ohne dass eine erreichbare vollständige Ansicht besteht.

Keine Standardauswahl mit Checkboxen, wenn gerade keine Mehrfachaktion angeboten oder benötigt wird. Keine zusätzliche Sammelbearbeitungsfunktion erfinden.

### 3.4 Leerraum

Nutze die gesamte verfügbare Arbeitsbreite mit sinnvollen Aussenabständen. Verteile diese Breite nach Inhalt: Hauptspalte flexibel, Mengen/Status/Aktionen kompakt. Keine riesigen leeren Aktionsspalten.

Reduziere unnötige Innenabstände, leere Kartenbereiche und wiederholte Überschriften. Freie Fläche unter einer kurzen Liste ist dagegen kein Fehler und muss nicht mit weiteren Karten aufgefüllt werden.

---

## 4. Ein gemeinsames Listenmuster

### 4.1 Verbindliche Anatomie

Jede normale Liste verwendet dieselbe visuelle Grundstruktur:

`Hauptinhalt | relevante Zusatzspalten | Zustand, falls nötig | Aktionen`

Der Hauptinhalt besteht aus einem klaren Namen/Titel und optional einer dezenten zweiten Zeile. Zusatzspalten enthalten echte, für die jeweilige Aufgabe nützliche Daten, nicht leere Platzhalter oder wiederholte Erklärungen.

Überall identisch sind Typografie, vertikale Ausrichtung, Zeilenabstände, Trennlinien, Interaktionszustände, Aktionsposition und Grundform der Statusanzeigen.

Eine echte Datentabelle bleibt semantisch eine Tabelle. Eine einfache Datensatzliste darf semantisch eine Liste bleiben. Verwende dieselben Design-Tokens und gemeinsamen Renderbausteine mit passenden Adaptern; erzwinge kein ungültiges HTML nur für ein einziges Makro.

### 4.2 Zeilen und Container

Eine Liste hat eine gemeinsame ruhige Hülle und feine Zeilentrenner. Keine eigene abgerundete, schattierte Karte für jeden normalen Datensatz.

Tabellenköpfe erhalten überall dieselbe Schrift, Höhe, Ausrichtung und Hintergrundbehandlung. Keine Mischung aus winzigen Grossbuchstaben, fetten Überschriften und kaum sichtbaren Labels.

Haupttexte verwenden dieselbe Schriftgrösse und Gewichtung. Links erhalten eine gemeinsame Behandlung; nicht auf einer Seite alle Namen in kräftiger Akzentfarbe und auf einer anderen dieselben Interaktionen wie normalen Text darstellen.

Ist ein Name bereits der direkte Einstieg in dieselbe Zielansicht, füge daneben nicht nochmals einen identischen Öffnen-Button hinzu. Falls Anzeigen und Bearbeiten unterschiedliche Aufgaben sind, darf ein Namenslink zusammen mit einem Bearbeiten-Icon bestehen.

Keine vollständig klickbaren Zeilen mit verschachtelten Buttons oder überraschender Navigation beim Markieren von Text. Bevorzuge einen klaren Namenslink und unabhängige Aktionen. Ein an den Namen gebundener Detailzugang darf diesen Namenslink ersetzen; dafür keinen dritten isolierten Aktionsbutton neben Bearbeiten und Überlauf hinzufügen.

### 4.3 Konsistenz ohne Gleichmacherei

Gleiche Gestaltung bedeutet nicht, dass jede Liste dieselben Fachspalten erhalten muss. Rezepte benötigen andere Daten als Lagerbestände. Sie müssen aber erkennbar dieselbe Listenfamilie sein.

Kalender und Wochenplan bleiben geeignete Planungsansichten. Ihre Buttons, Statusanzeigen, Details und eingebetteten Listen verwenden jedoch dieselben Grundbausteine.

---

## 5. Symbolbuttons als Standard

### 5.1 Sichtbare Darstellung

Normale Aktionsbuttons zeigen nur ein Symbol. Entferne sichtbare Begleittexte wie „Bearbeiten“, „Öffnen“, „Mehr“, „Suchen“ und „Anlegen“ aus den standardisierten Aktionsflächen.

Verwende eine einzige Iconfamilie aus der vorhandenen Tabler-Integration. Keine Mischung aus Emoji, Unicode-Ersatzzeichen, Font Awesome, Material Icons und unterschiedlich gezeichneten SVGs.

Gleiche Aktion bedeutet identisches Icon, identische Grösse, identische Reihenfolge und dasselbe Verhalten. Die Position im Layout darf sich responsiv verändern, nicht die Semantik.

Icons dürfen im Ruhezustand dezent sein, müssen aber sichtbar und als Aktionen erkennbar bleiben. Wesentliche Funktionen nicht ausschliesslich bei Hover einblenden.

### 5.2 Eine gemeinsame Button-Komponente

Die zentrale Umsetzung muss mindestens Folgendes abbilden können:

| Eigenschaft | Vertrag |
|---|---|
| Semantische Aktion | Stabile Kennung aus dem vorhandenen Symbol-/Aktionskonzept. |
| Zugänglicher Name | Übersetzter Aktionsname, bei Datensatzaktionen mit sinnvoller Objektzuordnung. |
| Symbol | Zentral bestimmt, nicht pro Template frei gewählt. |
| Elementtyp | Link für Navigation, Button für Aktionen; bestehende Formularsemantik erhalten. |
| Gewichtung | Primär, neutral oder gefährlich; keine frei erfundenen Seitenvarianten. |
| Zustand | Normal, Hover, Fokus, aktiv, deaktiviert und laufender Vorgang. |
| Erklärung | Gemeinsamer Tooltip; bei Bedarf zusätzliche zugängliche Beschreibung. |
| Ausführung | Bestehende Zielroute, Formulardaten, Berechtigungsprüfung und Ereignisbindung erhalten. |

Das ist ein Komponentenvertrag, keine Aufforderung zu einem neuen umfangreichen UI-Framework. Erweitere bevorzugt vorhandene Makros und Helfer.

### 5.3 Zugängliche Namen, Fokus und Touch

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** „Weitere Aktionen für Broccoli“ als normaler Zugang und das Touch-Überlaufmenü für ungewohnte Aktionen sind abgelöst. Auch auf Touch bleiben Befehle direkt erreichbar; lokalisierte Namen, Tooltip-, Tastatur- und Fokusvertrag bleiben erhalten.

Jeder Iconbutton benötigt einen zugänglichen Namen, beispielsweise „Broccoli bearbeiten“ oder „Weitere Aktionen für Broccoli“. Verwende korrektes `aria-label` oder passend verknüpften Text. Das dekorative SVG darf nicht zusätzlich als unbenanntes Bedienelement vorgelesen werden. Siehe technische Referenz R1.

Tooltips erscheinen konsistent bei Hover und Tastaturfokus. Sie sind bei Bedarf mit Escape schliessbar, mit dem Zeiger erreichbar und verschwinden nicht willkürlich nach kurzer Zeit. Ein natives `title`-Attribut allein ist für diesen Auftrag keine ausreichende Erklärung. Siehe R2.

Tastaturfokus muss deutlich sichtbar sein. Normale Buttons funktionieren mit Enter und Leertaste; Links behalten ihr natives Tastaturverhalten. Menüs und Dialoge erhalten korrektes Fokusmanagement und eine nachvollziehbare Rückkehr zum Auslöser. Siehe R1.

Auf Touchgeräten darf Verstehen nicht von Hover oder einem versteckten Langdruck abhängen. Ungewohnte Fachaktionen erscheinen vorzugsweise im aufklappbaren Überlaufmenü mit kurzem Text. Häufige eindeutige Aktionen wie Hinzufügen oder Bearbeiten bleiben direkt erreichbar.

### 5.4 Bewusste Text-Ausnahmen

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Die Ausnahme für geöffnete Aktionsmenüs erlaubt keine generischen Mehr-/Drei-Punkte-Sammler mehr. Fachinhalte, Formulare, Navigation, echte Auswahl, Warnungen und Sicherheitsbestätigungen behalten sichtbaren Text.

Icon-first ist kein Verbot von Sprache. Text bleibt sichtbar bei:

- Fachinhalten, Formularlabels, verständlicher Navigation und Profilauswahl;
- Einträgen eines geöffneten Aktionsmenüs: Icon plus kurzer Aktionsname;
- sicherheitsrelevanten Bestätigungsdialogen: eindeutige Aktion statt „OK“ oder zweier namenloser Icons;
- Zuständen oder Warnungen, deren Bedeutung sonst nicht zuverlässig erkennbar wäre.

Für normale Toolbar- und Zeilenbuttons gilt weiterhin konsequent icon-only. Keine pauschale Rückkehr zu beschrifteten Hauptbuttons und keine wechselnde Beschriftung je Bildschirmbreite.

### 5.5 Deaktivierte und laufende Aktionen

Ein deaktiviertes Symbol darf nicht nur unerklärlich ausgegraut sein. Der Grund muss ohne Hover erreichbar sein, beispielsweise in einer kurzen kontextbezogenen Meldung oder in der zugehörigen Prüfzusammenfassung.

Unterscheide echte native Deaktivierung von `aria-disabled`. Bei `aria-disabled` müssen Maus- und Tastaturausführung tatsächlich unterbunden werden. Ein ARIA-Attribut allein darf keine weiterhin ausführbare Aktion kaschieren.

Laufende Aktionen blockieren Doppelübermittlung, behalten ihren zugänglichen Namen und zeigen einen ruhigen Fortschrittszustand. Keine springenden Buttonbreiten.

---

## 6. Verbindliche Icon-Semantik

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** „Weitere Aktionen = dots“ ist als normaler Aktionszugang abgelöst. Historische Schlüssel dürfen bestehen; verfügbare Befehle verwenden direkt ihre eigene Semantik.

Verwende die bereits vorhandene zentrale Registry. Lege keine zweite riesige Symbolsammlung an. Konsolidiere widersprüchliche Zuordnungen und ergänze nur reale Lücken.

Die folgenden Tabler-Namen sind Zuordnungsvorschläge. Prüfe ihre Verfügbarkeit in der installierten Version. Die semantische Trennung ist verbindlich; vorhandene geeignete Registry-Einträge dürfen weiterverwendet werden.

| Aktion | Vorgesehene Symbolbedeutung / Tabler-Beispiel |
|---|---|
| Neu anlegen / hinzufügen | Plus, `plus` |
| Bearbeiten | Stift, `pencil` |
| Speichern | Speicheraktion, `device-floppy` |
| Schliessen / abbrechen | Kreuz, `x`, mit kontextgenauem Namen |
| Öffnen / zur Detailansicht | Navigationspfeil, `arrow-right` |
| Details auf-/zuklappen | Chevron, `chevron-right` / `chevron-down` |
| Weitere Aktionen | Drei Punkte, `dots` |
| Suchen | Lupe, `search` |
| Filter öffnen | Trichter, `filter` |
| Filter zurücksetzen | Durchgestrichener Trichter, `filter-off` |
| Duplizieren | Kopie, `copy` |
| Archivieren | Archiv, `archive` |
| Löschen | Papierkorb, `trash` |
| Vorschau | Auge, `eye` |
| Einplanen | Kalender mit Plus, `calendar-plus` |
| Prüfpunkte anzeigen / prüfen | Prüfliste, `list-check` |
| Veröffentlichen | Veröffentlichung, eigener Registry-Eintrag, z. B. `world-upload` |
| Importieren | Upload, `upload` |
| Exportieren | Download, `download` |
| Drucken | Drucker, `printer` |
| Vorher / nachher | `chevron-left` / `chevron-right` im eindeutigen Navigationskontext |

Ein Häkchen darf nicht pauschal Speichern, Veröffentlichen, Prüfen und Bestätigen ersetzen. Prüfstatus und Veröffentlichungsstatus bleiben verschiedene fachliche Aussagen.

Bei Zustandswechseln ändert sich das Icon nur, wenn sich die Bedeutung tatsächlich ändert. Ein dekoratives Erfolgszeichen ist keine zusätzliche Aktion.

Keine dekorativen Icons vor jedem Textabschnitt. Symbole dienen Bedienung und Orientierung, nicht dem Füllen von Leerraum.

---

## 7. Design-Tokens statt lokaler Sonderwerte

Die folgenden Werte sind Projektvorgaben für diesen Konsolidierungslauf, keine Behauptung über vorgeschriebene WCAG-Mindestwerte. Überführe sie in vorhandene Tokens und prüfe sie gegen die tatsächliche Darstellung.

| Element | Zielwert / Regel |
|---|---|
| Arbeitsfläche | Volle verfügbare Breite, kein unnötiges zentriertes Max-Width. |
| Aussenabstand | Typisch 24 px Desktop, 16 px schmale Ansicht. |
| Abstandsleiter | 4 / 8 / 12 / 16 / 24 px; wenige gemeinsame Abstufungen. |
| Aktionsbutton | 36 × 36 CSS-px am Desktop mit präzisem Zeiger. |
| Touch-Aktionsfläche | Mindestens 44 × 44 CSS-px bei möglicher grober Zeigereingabe; nicht nur anhand der Fensterbreite entscheiden. |
| Aktionsicon | Einheitlich 20 × 20 px, konsistente Strichstärke. |
| Einzeilige Standardzeile | Richtwert 48 px, kein Abschneiden bei grösserer Schrift. |
| Zweizeilige Standardzeile | Richtwert 64 px, darf für lange Inhalte wachsen. |
| Haupttext | Gemeinsamer gut lesbarer Wert im Bereich 14–16 px. |
| Sekundärtext | Gemeinsamer Wert im Bereich 12–13 px; nicht beliebig verkleinern. |
| Rundung | Ein gemeinsamer ruhiger Wert, vorzugsweise 8 px für Container und Controls. |
| Trennung | Dezente 1-px-Linien, keine Schatten pro Datensatz. |
| Statusanzeige | Gemeinsame kompakte Form; interaktive Statusflächen erhalten trotzdem die volle Aktionsgrösse. |

Kleine sichtbare Symbole dürfen innerhalb ausreichend grosser Trefferflächen liegen. Trefferflächen dürfen sich nicht gegenseitig überdecken. R3 erklärt die Unterscheidung zwischen Symbolgrösse, Zielgrösse und den WCAG-Mindestanforderungen.

Behalte die vorhandene Grundpalette bei. Normale Zeilen und Buttons neutral; Akzent für den klaren Hauptschritt oder die aktive Auswahl; Warn- und Fehlerfarben für entsprechende Bedeutung. Keine zusätzlichen bunten Kategorien nur als Dekoration.

Prüfe Lesbarkeit und Kontraste. Verstecke schlechte Lesbarkeit nicht hinter sehr hellem Sekundärtext. Keine Skalierung der gesamten Seite mit `zoom`, verkleinerten Root-Schriften oder Transform-Tricks.

---

## 8. Labels, Badges und Warnungen

### 8.1 Gemeinsame Darstellung

Verwende einen gemeinsamen Badge-/Statusbaustein mit einheitlicher Form, Typografie, Innenabständen und Iconposition. Die Bedeutung bestimmt die Variante, nicht die Seite.

„Aktiv“ ist nicht auf einer Seite kräftig pink, auf einer anderen grün und anderswo ein gewöhnlicher Textlink. Unterschiedliche fachliche Zustände dürfen unterschiedliche semantische Varianten erhalten, aber nicht unterschiedliche Designsysteme.

Formularlabels, Tabellenüberschriften, Tags und Statusbadges sind verschiedene Rollen. Vereinheitliche jeweils dieselbe Rolle; forme nicht jedes Label zu einer farbigen Pille um.

### 8.2 Normalzustand nicht endlos wiederholen

Wenn eine Liste ausdrücklich nur aktive Einträge zeigt, muss „Aktiv“ nicht in jeder Zeile erneut stehen. Zeige den aktiven Filter einmal. In gemischten Listen muss der Zustand dagegen wieder unterscheidbar sein.

Dasselbe gilt für Profile und redundante Verwaltungsinformationen. Das Weglassen ist nur zulässig, wenn der Kontext eindeutig bleibt und es nach Filterwechsel keine falsche Schlussfolgerung erzeugt.

### 8.3 Prüfungen bündeln, Bedeutung erhalten

Identische Warnursachen werden in einer kompakten Zusammenfassung gebündelt. Die betroffenen Einträge bleiben direkt auffindbar, etwa durch Filter oder einen bestehenden Prüfbereich.

In der Zeile genügt bei klarer Semantik ein kompakter Hinweis statt dreier gleichbedeutender Warntexte. Unabhängige relevante Probleme dürfen jedoch nicht zu einem bedeutungslosen Sammelpunkt verschmelzen.

Zähle korrekt: 28 betroffene Menüs mit jeweils zwei offenen Feldern sind nicht automatisch 56 verschiedene problematische Menüs. Gib an, ob eine Zahl Datensätze oder einzelne Prüfpunkte zählt.

Wichtige Warnungen dürfen nicht ausschliesslich über Farbe oder Tooltip vermittelt werden. Vor einer riskanten Aktion müssen Hindernis und nächste sinnvolle Handlung verständlich sein.

### 8.4 Fachliche Schutzregeln

- Nicht erfasste Allergene sind nicht gleichbedeutend mit „allergenfrei“.
- Nicht erfasster Lagerbestand ist nicht gleichbedeutend mit null.
- Ein gespeicherter Entwurf ist nicht automatisch geprüft oder veröffentlicht.
- Fehlende Herkunftsangaben werden durch das Einklappen ihrer Darstellung nicht erledigt.

Die vorhandene Validierung und Veröffentlichungssperre bleibt vollständig wirksam. Keine automatischen Freigaben und keine Datenbereinigung, um Warnungen optisch verschwinden zu lassen.

Im Lager darf beispielsweise eine kompakte, klar beschriftete Spalte „Nicht erfasst“ verwendet werden. Ein blosses „0“ oder ein unkommentierter Strich wäre eine falsche Vereinfachung.

---

## 9. Suche, Filter, Auswahl und Details

### 9.1 Eine Such- und Filterlogik

Jede Standardliste verwendet dieselbe Toolbar. Normal sichtbar sind Suche, bei Bedarf Profilauswahl und genau ein Filtereinstieg. Trefferzahl als kleiner Text im Kontext, nicht als zusätzliche Kennzahlenkarte.

Suche funktioniert mit Enter. Falls ein sichtbarer Suchauslöser benötigt wird, integriere einen standardisierten Lupenbutton in dieselbe Suchgruppe. Kein zusätzlicher breiter „Suchen“-Button neben einem bereits gleichwertigen Suchauslöser.

Bestehende automatische Suche nur konsistent über den vorhandenen gemeinsamen Mechanismus weiterverwenden; kein neuer Such-Stack nur für den Polish.

Aktive Zusatzfilter zeigen eine kompakte Anzahl am Filtereinstieg und bei Bedarf kurze entfernbare Filterchips. Ohne aktive Filter wird keine leere Filterzeile reserviert.

Der Filterbereich öffnet sich unmittelbar bei der Toolbar. Ein gemeinsames Muster für Anwenden und Zurücksetzen. Keine gleichzeitig sichtbaren Varianten „Filtern“, „Weitere Filter“ und nochmals ein Filterbutton für dieselbe Funktion.

### 9.2 Profilauswahl und Ansichten

„Cafeteria“ und „Patienten“ bleiben als verständliche Textauswahl erhalten. Ersetze diese Fachbereiche nicht durch zwei schwer deutbare Symbole. Rendere die Auswahl pro Aufgabenbereich nur einmal.

Vorhandene Listen-/Kartenumschaltung darf in einen kompakten gemeinsamen Ansichtsumschalter wandern. Füge keine neue Kartenansicht hinzu. Die Standardlisten müssen trotzdem gleich aussehen.

Suchbegriff, Filter und aktuelle Position sollen bei Detailaufruf und Rückkehr soweit mit der vorhandenen Architektur möglich erhalten bleiben. Kein unnötiger Kontextverlust.

### 9.3 Details

Kurze Zusatzinformationen werden über ein gemeinsames Aufklappmuster unmittelbar am Datensatz sichtbar. Kein permanenter „Details“-Text in jeder Zeile mit eigener grosser Leerfläche.

Verwende `aria-expanded`, sinnvolle Beziehungen zum Detailbereich und eindeutige IDs. Keine doppelt vergebenen IDs durch wiederholte Templates.

Für umfangreiche Bearbeitung bestehende geeignete Editorseiten oder Dialoge konsolidieren. Nicht allein für diesen Auftrag zusätzlich Drawer, neue Modals und weitere Detailseiten einführen.

Öffnen, Schliessen, Zurückkehren und der Umgang mit ungespeicherten Änderungen funktionieren überall gleich. Kein automatisches Zuklappen eines bearbeiteten Bereichs mit Datenverlust.

---

## 10. Anwendung auf Wochenplan und Kalender

### 10.1 Patienten- und Cafeteria-Planung

Ein kompakter Wochenkopf zeigt Zeitraum, Profil und den tatsächlichen Freigabestatus. Zusätzliche Prüfinformationen werden gebündelt, ohne blockierende Probleme zu verschweigen.

Ein Tag besitzt einen verständlichen Tageskopf. Mittag und Abend haben eine gemeinsame Struktur. Innerhalb einer Mahlzeit folgen die Menüvarianten als kompakte Einträge mit denselben Aktionen und Statusbausteinen.

Ausgabezeiten und allgemeine Mahlzeitangaben nicht pro Menükarte wiederholen. Ihre Bearbeitung erfolgt am passenden gemeinsamen Kontext. Fehlende Pflichtangaben bleiben erkennbar.

Suppe und Dessert bleiben eigenständige verständliche Gänge. Vorhandene Einträge erscheinen kompakt mit ihrem Namen. Leere Slots erhalten eine kleine Hinzufügen-Aktion direkt beim jeweiligen Gang, nicht grosse Buttons an weit auseinanderliegenden Kartenrändern.

Nur wenn das Datenmodell Suppe oder Dessert tatsächlich gemeinsam für eine Mahlzeit führt, darf die Anzeige entsprechend zusammengefasst werden. Keine fachlich getrennten Slots aus optischen Gründen zusammenlegen.

Erzwinge nicht, dass sieben Tage vollständig in einen Bildschirm passen. Ziel ist eine ruhigere, dichtere Planung ohne Informationsverlust, nicht ein unlesbares Miniaturraster.

### 10.2 Wochenübersicht

Verwende die gemeinsame Liste mit Zeitraum als primärer Information. Ein frei vergebener Titel darf nachgeordnet erscheinen, soweit er sinnvoll ist. Technische Prüftexte und Veröffentlichungsdetails nicht doppelt unter einem gleichbedeutenden Badge darstellen.

Datums- oder Titelwidersprüche aus den Referenzen separat prüfen und dokumentieren. Frei vergebene Titel nicht eigenmächtig ändern oder als abgeleitete Datumsfelder behandeln.

### 10.3 Küchenkalender

Ein Kalenderkopf bündelt Monat, Vor-/Zurücknavigation, Heute, Bereichsauswahl und die wichtigste Aktion. Separate Karten, die denselben Monat und dieselbe Auswahl wiederholen, entfallen.

Kalenderzellen verwenden eine gemeinsame Eintragsgestaltung. Bereich und Mahlzeit sinnvoll gruppieren statt vor jedem Gericht erneut auszuschreiben. Einträge bleiben lesbare Namen, keine reine Symbolmatrix.

Begrenze bei Platzmangel die direkt sichtbaren Einträge nach einer gemeinsamen Regel und mache den Rest über „+n“ zugänglich. Die Zahl muss genau die tatsächlich verborgenen Einträge beschreiben. Keine still verworfenen Termine oder Gänge.

Die heutige Auswahl und der aktuelle Tag dürfen visuell nicht verwechselt werden. Auf kleinen Bildschirmen eine vorhandene geeignete kompakte/Agenda-Darstellung nutzen; kein winzig skaliertes Desktopraster.

---

## 11. ASCII-Zielbilder

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Sämtliche `[...]`-Aktionssammler und festen Aktionsbudgets in §11.1–11.7 sind als Zielbilder abgelöst. Aktuelle Direktaktionsbilder stehen in SDD §5; Fachspalten, Inhalte, Detailzugänge, Warnungen und Responsive-Regeln bleiben erhalten.

Diese Zielbilder beschreiben Anordnung und Informationsmenge, nicht konkrete Schriftzeichen für die Produktion. `[e]`, `[f]`, `[p]` und ähnliche Kürzel stehen ausschliesslich für echte Tabler-Icons. Sie dürfen nicht als Buchstabenbuttons implementiert werden.

Legende: `[+]` Hinzufügen, `[e]` Bearbeiten, `[...]` weitere Aktionen, `[f]` Filter, `[->]` zur Detailansicht navigieren, `[>]` Detail aufklappen, `[v]` Detail zuklappen, `[o]` Vorschau, `[p]` Veröffentlichen. `!` innerhalb eines Status ist ein Warnsymbol, nicht automatisch ein weiterer Button.

### 11.1 Gemeinsame Listenansicht

```text
Bausteine                                                   14 Treffer   [+]

[ Suche ...................................... ]  Cafeteria | Patienten  [f]

Name                           Kategorie       Verwendung          Aktionen
---------------------------------------------------------------------------
Basmatireis                    Beilage         8 Gerichte         [e] [...]
Broccoli                       Gemuese         8 Gerichte         [e] [...]
Blattsalat                     Weiteres        8 Gerichte         [e] [...]
Bohnen                         Weiteres        8 Gerichte         [e] [...]
---------------------------------------------------------------------------
```

Keine separate Karte „Bereich: Cafeteria“. Keine Wiederholung „nur Cafeteria“ in jeder Zeile. Werden Herkunft oder Kennzeichnungen für die Aufgabe benötigt, erscheinen sie als passende gemeinsame Spalte oder in den Details, nicht als willkürlicher Zusatzblock.

### 11.2 Dieselbe Listenfamilie für Rezepte

```text
Rezepte                                                     18 Treffer   [+]

[ Suche ............................................................ ]  [f]

Name                              Ausbeute        Zustand          Aktionen
---------------------------------------------------------------------------
Apfelmus                          1600 g          Entwurf         [e] [...]
Basmatireis                       2800 g          Entwurf         [e] [...]
Blaetterteigpastetli               20 Portionen    Entwurf         [e] [...]
---------------------------------------------------------------------------
```

Dieselbe Hülle, dieselben Zeilen, dieselben Buttons. Unterschiedliche Fachspalten sind erlaubt. Statusdarstellung abhängig vom tatsächlichen Filterkontext; kein Pflichtbadge für jede normale Zeile.

### 11.3 Zusatzinformationen nur geöffnet

```text
Name                           Kategorie       Verwendung          Aktionen
---------------------------------------------------------------------------
[v] Broccoli                   Gemuese         8 Gerichte         [e] [...]
    Herkunft: Albanien     Kennzeichnungen: [nur tatsaechliche Angaben]
    Weitere Zuordnungen und Details erscheinen ausschliesslich hier.
---------------------------------------------------------------------------
[>] Basmatireis                 Beilage         8 Gerichte         [e] [...]
---------------------------------------------------------------------------
```

Das Chevron gehört hier zum verständlich beschrifteten Detailzugang am Namen und bildet keinen dritten isolierten Iconbutton. Herkunft und Kennzeichnungen im Beispiel sind Platzhalter für echte Datensatzwerte, nicht zu importierende Stammdaten. Lange Detailinhalte dürfen wachsen. Die gesamte Liste wird dadurch nicht zu einem permanenten Formular.

### 11.4 Ruhiger Wochenplan

```text
Patienten          [<]  21.-27. September 2026  [>]            [o] [p] [...]
! 28 Menues zu pruefen                                        [Pruef-Icon]

Montag, 21. September
---------------------------------------------------------------------------
Mittag                                      Abend
---------------------------------------------------------------------------
Menue 1                                     Menue 1
Pouletgeschnetzeltes Paprika       [e] [...] Schinken-Kaese-Toast    [e] [...]
Reis, Zucchetti                             Tomatensalat

Vegetarisch                                 Vegetarisch
Gemuesegeschnetzeltes              [e] [...] Gemuese-Toast          [e] [...]
Reis, Zucchetti                             Tomatensalat

Suppe: noch nicht geplant              [+] Suppe: noch nicht geplant    [+]
Dessert: noch nicht geplant            [+] Dessert: noch nicht geplant  [+]
---------------------------------------------------------------------------
```

Zusätzlich erforderliche datensatzbezogene Warnungen erhalten kompakte, verständliche Zustände. Die ASCII-Skizze ist kein Auftrag, sämtliche Warnungen in eine globale Zeile zu verlagern. Zeitangaben und vorhandene Gänge aus echten Daten bleiben erhalten.

### 11.5 Lager ohne Warnbadge-Wand

```text
Lager
! Fuer 100 Zuordnungen ist noch kein Bestand erfasst.

[ Suche ............................................................ ]  [f]

Zutat                          Lagerort        Bestand             Aktionen
---------------------------------------------------------------------------
Apfelessig                     Trockenlager    Nicht erfasst      [->] [...]
Basmatireis                    Trockenlager    Nicht erfasst      [->] [...]
Blattsalat                     Kuehlraum       Nicht erfasst      [->] [...]
---------------------------------------------------------------------------
```

Der Warninhalt bleibt verständlich. Er wird nicht auf jeder Zeile nochmals in einer grossen gelben Pille wiederholt. Die endgültige Öffnen-Aktion nutzt die zentrale Semantik, nicht das ASCII-Zeichen.

### 11.6 Schmale Ansicht

```text
Rezepte                                      [+]
[ Suche ............................... ]    [f]
------------------------------------------------
Apfelmus                               [e] [...]
1600 g  /  Entwurf
------------------------------------------------
Basmatireis                            [e] [...]
2800 g  /  Entwurf
------------------------------------------------
```

Gleiche Reihenfolge und Symbolbedeutung. Metadaten dürfen unter den Hauptinhalt rutschen. Trefferflächen wachsen bei Touch; Schrift und Inhalte werden nicht zusammengeschrumpft.

### 11.7 Aktionsmenü erst bei Bedarf

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Das geöffnete Aktionsmenü samt erst dann sichtbaren Kurztexten ist als Standard abgelöst. Alle tatsächlich verfügbaren Befehle bleiben unmittelbar als Symbole erreichbar.

```text
Broccoli                                          [e] [...]
                                                       |
                                      +----------------------+
                                      | [copy] Duplizieren   |
                                      | [plan] Einplanen     |
                                      | [arch] Archivieren   |
                                      |----------------------|
                                      | [trash] Loeschen     |
                                      +----------------------+
```

Die tatsächlichen Einträge richten sich nach verfügbaren Aktionen und Berechtigungen. Keine leeren oder erfundenen Funktionen. Hier sind kurze Textlabels ausdrücklich gewünscht: Sie werden erst nach Öffnen sichtbar und erklären seltene Aktionen.

---

## 12. Umsetzung im bestehenden Projekt

### 12.1 Inventar zuerst

Ermittle alle erreichbaren betroffenen Ansichten, Templates, Partials und dynamisch nachgeladenen Bereiche. Erfasse pro Ansicht mindestens Listentyp, Aktionsvarianten, Badge-/Labelvarianten, Filtermuster und verwendete gemeinsame Bausteine.

Berücksichtige beide Profile, erlaubte Rollen, archivierte Einträge und fehlende Daten. Führe eine kompakte Abdeckungsliste: noch offen, migriert, geprüft oder konkret blockiert.

Lies vorhandenes Designmanifest, SDDs und Agentenanweisungen im Projekt. Aktualisiere die bestehenden verbindlichen Dokumente, statt widersprüchliche neue Parallelregeln daneben zu legen.

### 12.2 Gemeinsame Basis vor Einzelmigrationen

Konsolidiere diese Verantwortlichkeiten in der vorhandenen Architektur:

- Symbol-/Aktionsauflösung mit Buttonrenderer und Aktionsgruppe;
- Listen-/Tabellenhülle, Datensatzzeile und passende Detaildarstellung;
- Status-/Badge-Darstellung und kontextbezogene Prüfzusammenfassung;
- Seitenkopf sowie gemeinsame Suche/Filter/Profilauswahl.

Nicht jede Verantwortung braucht eine neue Datei oder Klasse. Nutze vorhandene Strukturen. Kein Konfigurationsgenerator und kein neues Designsystem-Framework.

Migriere zunächst zwei deutlich unterschiedliche Referenzen, vorzugsweise Bausteine und Rezepte. Prüfe daran, ob dieselbe gemeinsame Basis beide ohne seitenbezogene Stilkorrekturen abbildet.

### 12.3 Keine kosmetischen Abkürzungen

Nicht erlaubt sind globale Regeln wie „Text in allen Buttons verstecken“, leere Schriftgrössen, willkürliche `nth-child`-Korrekturen oder seitenweise `!important`-Sammlungen.

Der tatsächliche Renderer muss korrekte Symbolbuttons erzeugen. Bewahre Formulartypen, CSRF-Schutz, `name`-/`value`-Paare, `form`-Zuordnung, URLs, Datenattribute, Eventbindungen und Selektoren beziehungsweise migriere sie kontrolliert mit.

Keine Änderung bestehender HTTP-Aktionssemantik: Speichern, Löschen oder Veröffentlichen werden durch den Umbau nicht zu zustandsverändernden GET-Links.

Bereinigung erfolgt nach nachgewiesener Migration. Entferne ungenutzte alte Varianten und überschreibende Styles, ohne unbeteiligte Ansichten zu beschädigen.

### 12.4 Navigation

Behalte die vereinbarte Navigation ohne aufgeklappte Verbindungslinien oder Tree-View-Striche bei. Hierarchie durch Einrückung, Typografie und dezenten aktiven Hintergrund.

Parent-, Child-, Hover-, Fokus- und Aktivzustände konsistent behandeln. Kein versehentlich gleichzeitig aktiv wirkender Eintrag. Sidebar-Icons aus derselben Familie; sinnvolle Navigationsnamen bleiben sichtbar, sofern die Sidebar nicht bewusst eingeklappt ist.

### 12.5 Sprache und Daten

Tooltips, zugängliche Namen, Statusbezeichnungen und Menüeinträge nutzen das vorhandene Übersetzungssystem. Keine zusammengesetzten deutschen Strings, die in anderen Sprachen zerbrechen. Datensatznamen korrekt maskieren und nicht als ungeprüftes Tooltip-HTML einsetzen.

Alle gelieferten Texte verwenden korrekte Umlaute. ASCII-Umschreibungen in den Skizzen sind kein Produkttext. Mengen und Einheiten dürfen einheitlich formatiert werden, aber nicht ohne fachlichen Auftrag umgerechnet werden.

---

## 13. Arbeitspakete für den Orchestrator

| Paket | Ergebnis | Abhängigkeit |
|---|---|---|
| WP1 – Audit und Vertrag | Vollständiges Ansichteninventar, vorhandene Komponenten identifiziert, Konflikte im Manifest geklärt. | Start |
| WP2 – Gemeinsame Primitive | Tokens, Iconbuttons, Statusbaustein, Listenbasis und Toolbar konsolidiert; Komponententests vorhanden. | WP1 |
| WP3 – Pilot und Review | Bausteine und Rezepte mit denselben Grundbausteinen migriert; visueller und funktionaler Vergleich. | WP2 |
| WP4 – Listenmigration | Alle weiteren Verwaltungslisten inklusive Unterlisten, Dialoge und Zustandsvarianten umgestellt. | WP3 |
| WP5 – Planung und Kalender | Wochenkontext, Menüs, Gänge, Prüfhinweise und Kalendersteuerung vereinfacht. | WP3 |
| WP6 – Appweite Prüfung | Interaktionen, Rollen, Responsive-Verhalten, Symbolverständlichkeit und Restvarianten geprüft. | WP4 + WP5 |
| WP7 – Bereinigung und Abschluss | Tote Stile entfernt, Manifest und Tests aktualisiert, Abdeckung und offene Punkte ehrlich dokumentiert. | WP6 |

WP4 und WP5 dürfen nach stabilen gemeinsamen Verträgen parallel laufen. Weise Dateibesitz und Schnittstellen ausdrücklich zu, damit Worker nicht gleichzeitig die gemeinsame Button- oder Listenbasis unterschiedlich verändern.

Jedes Paket liefert nachvollziehbaren Diff, betroffene Ansichten, Testnachweise und offene Risiken. Fehler gehen als kleine Korrekturpakete an Worker zurück. Nicht nur aufgrund eines hübschen Screenshots akzeptieren.

---

## 14. Abnahmekriterien

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** UI-05s „höchstens Hauptaktion plus Überlauf“ ist abgelöst: alle verfügbaren Aktionen direkt sichtbar prüfen, ohne Doppelbefehle mit gleichem Ziel und gleicher Wirkung. UI-15 erlaubt kein generisches Aktionsmenü; vorhandene Bestätigungs- und Schutzschritte bleiben Pflicht. Neue Direktaktionskriterien: SDD §10.

Ein Punkt gilt nur mit tatsächlichem Nachweis als erfüllt. Automatische Prüfungen ergänzen die visuelle und manuelle Prüfung, ersetzen sie nicht.

| ID | Prüfung | Erwartetes Ergebnis |
|---|---|---|
| UI-01 | Ansichteninventar gegen migrierte Seiten abgleichen. | Alle betroffenen erreichbaren Verwaltungsansichten erfasst; keine pauschale Behauptung „appweit“ bei offener Restliste. |
| UI-02 | Bausteine, Zutaten, Rezepte, Menüs und Gerichtvorlagen nebeneinander vergleichen. | Eine erkennbare gemeinsame Listenfamilie, keine unterschiedlichen Zeilenkarten oder Aktionsstile. |
| UI-03 | Gleiche Aktion auf verschiedenen Seiten prüfen. | Identisches Icon, gemeinsame Geometrie, gleiche Bedeutung und konsistente Position. |
| UI-04 | Standardtoolbars und Zeilen prüfen. | Icon-only-Aktionsbuttons; sichtbare Textausnahmen entsprechen ausdrücklich dieser Spezifikation. |
| UI-05 | Zahl sichtbarer Aktionen pro Standardzeile prüfen. | Rechts höchstens Hauptaktion plus Überlauf; kein zusätzlicher isolierter Öffnen-/Details-Button neben einem gleichwertigen Namenszugang. |
| UI-06 | Zugängliche Namen aus dem gerenderten DOM prüfen. | Jeder Iconbutton besitzt einen sinnvollen lokalisierten Namen; Datensatzbezug dort, wo nötig. |
| UI-07 | Bedienung nur mit Tastatur. | Erreichbare Aktionen, sichtbarer Fokus, korrekte Aktivierung und nachvollziehbare Rückkehr nach Dialogen. |
| UI-08 | Tooltip mit Maus und Fokus öffnen, Escape drücken. | Gemeinsames Verhalten, schliessbar und ausreichend beständig; keine Hover-only-Erklärung wichtiger Funktionen. |
| UI-09 | Touch-/grobe Zeigereingabe prüfen. | Projektziel 44 × 44 CSS-px für Aktionsflächen, keine Überlappung und keine erforderliche Langdruckgeste. |
| UI-10 | Suche, Filter und Zurücksetzen auf mehreren Listen ausführen. | Ein gemeinsamer Einstieg; Enter funktioniert; keine doppelten Filterbuttons und keine verlorenen Bedingungen. |
| UI-11 | Aktive und gemischte Statusfilter wechseln. | Normalzustände nur bei eindeutigem Kontext weggelassen; in gemischten Listen wieder erkennbar. |
| UI-12 | Fehlende Allergene, fehlende Herkunft und fehlenden Bestand anzeigen. | Fehlend bleibt fehlend; keine Umdeutung zu allergenfrei, vollständig oder null. |
| UI-13 | Veröffentlichen bei offenen blockierenden Prüfungen versuchen. | Bisherige serverseitige Sperre bleibt wirksam; Grund ist verständlich erreichbar. |
| UI-14 | Speichern, Öffnen, Prüfen und Veröffentlichen vergleichen. | Nicht dasselbe generische Häkchen für verschiedene Aktionen; bestehende Abläufe bleiben getrennt. |
| UI-15 | Löschen/Archivieren/Duplizieren ausführen beziehungsweise abbrechen. | Bestehende Rechte und Bestätigungen erhalten; keine versehentliche Ausführung beim Öffnen eines Menüs. |
| UI-16 | Rollen mit geringeren Rechten und Nur-Lesen-Ansichten prüfen. | Keine neuen Bearbeitungswege; sichtbare Aktionen entsprechen tatsächlichen Berechtigungen. |
| UI-17 | Suppe und Dessert in beiden Profilen und Mahlzeiten prüfen. | Bestehende Zuordnung bleibt korrekt; Hinzufügen/Bearbeiten bleibt erreichbar; keine verlorenen Slots. |
| UI-18 | Details öffnen, bearbeiten und zurückkehren. | Konsistentes Muster, keine verlorenen ungespeicherten Änderungen, Filterkontext soweit vorgesehen erhalten. |
| UI-19 | Kalender mit vielen Einträgen und Randtagen prüfen. | „+n“ stimmt, versteckte Einträge sind erreichbar; Datum und Auswahl bleiben unterscheidbar. |
| UI-20 | Leere Liste, Ladezustand, Fehler und lange Texte prüfen. | Dieselbe Gestaltungssprache, klare nächste Handlung; keine abgeschnittenen essenziellen Inhalte. |
| UI-21 | 1440 × 900, 1024 × 768, 768 × 1024 und 390 × 844 prüfen. | Kein überlappendes Layout; schmale Standardlisten ohne seitliches Seitenscrollen. |
| UI-22 | 200 % Zoom und schmale Reflow-Situation prüfen. | Inhalte bleiben lesbar und bedienbar; keine starren Zeilenhöhen mit abgeschnittenem Text. |
| UI-23 | Seitenkopf einer normalen Liste bei 1440 × 900 messen. | Richtziel: erster Datensatz spätestens ca. 220 CSS-px unter Beginn des App-Inhalts, sofern keine notwendige Sondermeldung angezeigt wird. |
| UI-24 | Standardliste mit mindestens zehn kurzen zweizeiligen Datensätzen bei 1440 × 900 prüfen. | Richtziel: mindestens acht vollständig sichtbare Datensätze ohne Schriftverkleinerung; Abweichung mit tatsächlicher Ursache begründen. |
| UI-25 | Infokarten und wiederholte Warnungen prüfen. | Keine dekorativen Doppelanzeigen; gleichartige Warnursachen gebündelt, wichtige Einzelprobleme weiterhin verständlich. |
| UI-26 | Gemeinsame Tokens und verbleibende lokale Varianten prüfen. | Keine neue Patchwork-Schicht; veraltete Komponenten und ungenutzte Overrides kontrolliert entfernt. |
| UI-27 | Navigation prüfen. | Keine unerwünschten Verbindungslinien; konsistente Parent-/Child-/Aktivzustände. |
| UI-28 | Vorher-/Nachher-Aufnahmen vergleichen. | Gleicher Datensatzbestand, gleiche Rolle, gleiche Filter, gleicher Viewport und Zoom; keine geschönten Vergleiche durch andere Daten. |

Bei technisch geeigneten bestehenden Tests automatisiert nach unlabeled Iconbuttons, inkonsistenten Aktionskennungen und unerlaubten Varianten suchen. Ein einfacher Text-Grep allein ist kein Accessibility-Nachweis.

Die Dichteziele UI-23 und UI-24 sind Projektziele für normale Listen, nicht für Kalender, geöffnete Editoren oder wichtige Fehlersituationen. Verletze keine Verständlichkeits- oder Sicherheitsregel, um eine Pixelzahl zu erreichen.

---

## 15. Dauerhafte Absicherung und Abschluss

Aktualisiere das vorhandene UI-Manifest sowie die einschlägigen Agentenanweisungen so, dass auch künftige Seiten die gemeinsamen Muster verwenden. Dokumentiere mindestens:

- Symbolbuttons als Standard mit eng definierten Textausnahmen;
- gemeinsame Listenanatomie und zentrale Komponentenverwendung;
- begrenzte sichtbare Aktionen und Details nur bei Bedarf;
- gemeinsame Status-, Label- und Filterregeln;
- Erhalt fachlicher Warnungen und aller Berechtigungs-/Freigaberegeln.

Nutze vorhandene Dokumentationsorte. Eine kompakte SDD-/Auditdatei mit Abdeckung und Ausnahmen genügt neben dem aktualisierten Manifest und den Tests. Erzeuge keine Flut nahezu identischer Dokumente.

Der Abschlussbericht nennt die migrierten Ansichten, wiederverwendeten gemeinsamen Komponenten, tatsächlich ausgeführten Tests und verbleibenden Blockaden. Füge Vorher-/Nachher-Nachweise für mindestens die beiden Pilotlisten, einen Wochenplan und eine schmale Ansicht hinzu.

Behaupte keine Bereitstellung oder Liveprüfung, wenn nur lokal gearbeitet wurde. Keine Veröffentlichung von Planungsdaten im Rahmen eines UI-Tests. Nutze für Änderungen an Testdaten eine geeignete Entwicklungs-/Testumgebung.

**Definition of Done:** Die Anwendung wirkt wie ein einziges ruhiges Werkzeug. Listen gehören sichtbar zusammen. Aktionen werden konsequent durch verständliche Symbole dargestellt. Der Normalzustand ist nicht mit Warnkarten, Labels oder Aktionsleisten überfrachtet. Alle Funktionen, fachlichen Bedeutungen und Schutzmechanismen bleiben erhalten. Offene Abweichungen sind konkret benannt und nicht als erledigt ausgegeben.

Beginne mit dem vollständigen Inventar und der Konsolidierung der gemeinsamen Grundbausteine. Arbeite danach die Ansichten systematisch durch. Liefere keine weitere Runde rein lokaler Schönheitskorrekturen.

---

## Technische Referenzen

Die Quellen begründen nur die genannten technischen Accessibility- und Icon-Grundlagen. Aktionsbudgets, Layoutmasse, Dichteziele und die konkrete Dishboard-Gestaltung sind Vorgaben dieses Auftrags, keine angeblich extern vorgeschriebenen Standards.

**R1 – W3C/WAI: Button Pattern.** Zugängliche Namen, Unterscheidung von Link und Button, Tastaturaktivierung und Fokusführung.
https://www.w3.org/WAI/ARIA/apg/patterns/button/

**R2 – W3C/WAI: Content on Hover or Focus.** Zusätzliche Inhalte müssen unter den beschriebenen Bedingungen schliessbar, mit dem Zeiger erreichbar und beständig sein.
https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html

**R3 – W3C/WAI: Target Size (Minimum).** WCAG 2.2 AA nennt 24 × 24 CSS-px mit Ausnahmen. Das hier gewählte Projektziel von 36 px beziehungsweise 44 px ist eine gesonderte Designvorgabe.
https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html

**R4 – Tabler: offizielle Icon-Dokumentation.** Grundlage für die Nutzung einer einheitlichen vorhandenen Iconfamilie; tatsächlich installierte Version und verfügbare Symbole im Projekt prüfen.
https://docs.tabler.io/icons
