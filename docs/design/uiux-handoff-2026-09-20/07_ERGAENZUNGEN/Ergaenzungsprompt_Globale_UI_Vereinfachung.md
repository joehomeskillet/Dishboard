# Ergänzungsprompt – Gesamtes Dishboard konsequent vereinfachen

Der gezeigte Screenshot ist **nur ein Beispiel für ein grundsätzliches Problem**. Nicht diese einzelne Seite isoliert optimieren.

## Auftrag

Gehe das **gesamte bestehende Dishboard-Frontend systematisch Seite für Seite und Zustand für Zustand durch** und vereinfache die Bedienung und Darstellung überall dort, wo dies ohne Funktionsverlust möglich ist.

Ziel ist nicht ein kosmetisches Redesign einzelner Screens, sondern eine konsistente, platzsparende und möglichst selbsterklärende Anwendung.

## Grundprinzip

> Zeige dem Benutzer nur das, was er im aktuellen Kontext wirklich braucht.

Komplexität darf im Datenmodell und Backend existieren, soll aber nicht ungefiltert im UI landen.

## Auf jeder Seite prüfen

- Kann ein Feld, Text, Button, Status oder Abschnitt entfallen?
- Kann etwas erst bei Bedarf eingeblendet werden?
- Werden dieselben Informationen mehrfach gezeigt?
- Sind Formulare unnötig lang oder breit?
- Gibt es dauerhaft sichtbare Detailfelder für Optionen, die gar nicht ausgewählt sind?
- Sind Aktionen über mehrere Stellen verteilt?
- Gibt es zu viele gleichwertig wirkende Buttons?
- Kann ein sinnvoller Standard einen Arbeitsschritt einsparen?
- Lassen sich Listen, Filter und Aktionen kompakter darstellen?
- Kann eine Tabelle statt vieler grosser Karten verwendet werden – oder umgekehrt?
- Sind Überschriften, Hilfetexte oder technische Informationen für den normalen Benutzer wirklich nötig?
- Werden interne IDs, Revisionen oder technische Zustände unnötig prominent dargestellt?
- Gibt es grosse Leerflächen oder künstlich gestreckte Eingabefelder?
- Ist sofort erkennbar: **Wo bin ich? Was ist der Zustand? Was soll ich als Nächstes tun?**
- Ist die gleiche Funktion in anderen Modulen anders aufgebaut?

## Vereinfachungsmuster

Bevorzuge konsequent:

- Progressive Disclosure statt alles gleichzeitig anzeigen
- sinnvolle Defaults statt Pflichtklicks
- Inline-Aktionen statt separater Aktionsbereiche
- kompakte Chips/Badges für Status und Kennzeichnungen
- Checkbox/Toggle + Detail erst nach Aktivierung
- Accordion/Modal/Drawer für selten benötigte Details
- klare Primäraktion pro Kontext
- Sekundäraktionen visuell zurücknehmen
- gemeinsame Filterleiste für Listen
- konsistente Tabellen-/Listenstruktur
- kompakte Status-/Kontextleiste mit den wirklich wichtigen Informationen
- 2–3 Spalten auf grossen Bildschirmen, wenn dies die Lesbarkeit verbessert
- eine Spalte auf kleinen Displays
- Icons **mit verständlicher Beschriftung**, wenn die Bedeutung nicht zweifelsfrei ist

## Konsistenz ist verbindlich

Menüs, Bausteine, Zutaten, Rezepte, Kochbücher, Gerichtvorlagen, Einkaufslisten, Bestellung, Lager, Kalkulation, Wochenplan, Vorschau/Bildschirme und Einstellungen dürfen nicht wie getrennte Anwendungen wirken.

Wiederkehrende Funktionen müssen dieselben UI-Muster verwenden:

- Seitentitel und Kontext
- Statusleiste
- Suche und Filter
- Listen und Tabellen
- Erstellen
- Öffnen/Bearbeiten
- Speichern
- Abbrechen/Zurück
- Empty States
- Warnungen
- Bestätigungen
- Detailansichten
- Archive/Status
- Pagination

Keine neue Sonderlösung entwickeln, wenn bereits ein geeignetes gemeinsames Pattern existiert.

## Informationshierarchie

Priorität:

1. aktuelle Aufgabe
2. für die Entscheidung notwendige Informationen
3. Status/Warnungen
4. Primäraktion
5. optionale Details
6. technische/administrative Informationen

Die Punkte 5 und 6 standardmässig einklappen oder zurückhaltend darstellen, sofern sie nicht unmittelbar benötigt werden.

## Platzverbrauch

Vertikalen Platz als knappe Ressource behandeln.

Vermeiden:

- riesige Karten für wenige Informationen
- einzelne Formfelder über die komplette Bildschirmbreite ohne Grund
- wiederholte Hilfetexte
- grosse Abstände zwischen logisch zusammengehörigen Elementen
- pro Datensatz mehrere Zeilen, wenn eine kompakte Zeile genügt
- permanent sichtbare Optionen für seltene Sonderfälle
- unnötige Zwischenüberschriften

Kompakt bedeutet **nicht gequetscht**. Lesbarkeit, Touch-Ziele und Accessibility bleiben erhalten.

## Vorgehen für Claude Code

Nicht sofort blind einzelne Templates ändern.

### Phase 1 – UI-Audit

Alle relevanten Routes, Templates, Partials und gemeinsamen Komponenten erfassen.

Für jede Seite kurz dokumentieren:

| Seite | Problem | Vereinfachung | gemeinsames Pattern | Priorität |
|---|---|---|---|---|

Zusätzlich wiederkehrende Anti-Patterns gruppieren, damit sie zentral statt zehnmal separat behoben werden.

### Phase 2 – gemeinsame Komponenten

Zuerst wiederverwendbare Patterns vereinheitlichen, insbesondere Navigation, Seitenkopf, Statusleiste, Filterleiste, Formgruppen, Tabellen/Listen, Aktionen, Empty States, Warnungen und Speichern/Abbrechen.

### Phase 3 – Module

Danach sämtliche Module auf diese Patterns migrieren.

### Phase 4 – Detailseiten und Sonderzustände

Auch Create/Edit/Detail, leerer Zustand, Fehler, Warnung, archiviert, read-only, lange Datenbestände und kleine Displays prüfen.

### Phase 5 – Regression

Keine vorhandene Fachfunktion entfernen. Backend-Verträge, Datenmodell, Validierung, Berechtigungen und bestehende Workflows erhalten, sofern eine Änderung nicht ausdrücklich für die Vereinfachung erforderlich und dokumentiert ist.

## Entscheidungsregel

Wenn zwei Varianten fachlich gleichwertig sind, verwende diejenige, die:

1. weniger Erklärung benötigt,
2. weniger permanente UI-Elemente zeigt,
3. weniger Klicks im häufigsten Workflow benötigt,
4. weniger Platz verbraucht,
5. bereits an anderer Stelle als gemeinsames Pattern eingesetzt werden kann.

Der aktuelle Allergene-Screenshot ist lediglich ein **Beispiel für diese Denkweise**. Suche selbstständig im gesamten Produkt nach vergleichbaren und anderen unnötig komplizierten UI-Strukturen und behebe sie systematisch.
