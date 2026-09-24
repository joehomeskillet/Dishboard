# Ergänzung zum laufenden UI-Polish-Auftrag

Ergänze den bestehenden UI-Polish-Auftrag um folgende **verbindliche, app-weite Regeln**.

## 1. Buttons radikal vereinfachen

Buttons dürfen nicht unnötig mit langen Texten beschriftet sein.

### Regeln
- **Symbole bevorzugen**, wenn die Aktion eindeutig verständlich ist.
- Bei nicht selbsterklärenden Aktionen: **Icon + sehr kurzes Label**.
- Lange Beschriftungen wie `Speichern und zurück zum Wochenplan` vermeiden.
- Stattdessen kurze, eindeutige Varianten verwenden, z. B.:
  - `✓ Speichern`
  - `✎ Bearbeiten`
  - `＋ Anlegen`
  - `⌕ Suchen`
  - `⚙ Optionen`
  - `⋯ Mehr`
- Sekundäre und seltene Aktionen nach Möglichkeit in Icon-Buttons, `⋯`-Menüs, Kontextmenüs oder Dropdowns verschieben.
- Nicht mehrere gleich stark gewichtete Textbuttons nebeneinander darstellen.
- Für dieselbe Aktion muss in der gesamten Anwendung **immer dasselbe Symbol** verwendet werden.
- Destruktive Aktionen müssen klar von normalen Aktionen unterscheidbar bleiben.
- Reine Icon-Buttons benötigen Tooltip und zugängliche Beschriftung (`aria-label`).

### Ziel
Aktionen sollen visuell schnell erfassbar sein und möglichst wenig horizontale Breite verbrauchen.

---

## 2. Alle Listen auf ein gemeinsames Muster bringen

Listen, Tabellen, Datensammlungen und zeilenbasierte Übersichten dürfen **nicht je Modul anders aussehen**.

Definiere eine einzige app-weite Listensprache und migriere bestehende Listen darauf.

### Gemeinsame Struktur

```text
┌──────────────────────────────────────────────────────────────────────┐
│ Hauptinhalt / Name        Zusatzinfo        Status        Aktionen  │
│ optionale Sekundärinfo                                            ⋯ │
└──────────────────────────────────────────────────────────────────────┘
```

### Verbindliche Regeln
- gleiche Zeilenhöhe
- gleiche horizontalen Innenabstände
- gleiche vertikalen Innenabstände
- gleiche Schriftgrössen
- gleiche Trennlinien
- gleiche Hover-Zustände
- gleiche Statusposition
- gleiche Aktionsposition
- gleiche Button-/Icon-Grösse
- gleiche Darstellung sekundärer Informationen
- gleiche Behandlung leerer Werte
- gleiche Tabellenköpfe
- gleiche Sortierindikatoren
- gleiche Filterdarstellung
- gleiche Pagination
- gleiche Empty States

### Inhaltshierarchie
1. **Name / Primärinformation**
2. **kurze Sekundärinformation**
3. **Status**
4. **Aktionen**

Aktionen möglichst rechtsbündig. Sekundärinformationen visuell zurücknehmen.

Listen sollen **kompakt, ruhig und scanbar** sein.

Keine Seite soll eine eigene Sonderform von Listen entwickeln, wenn dieselbe Information mit der Standardkomponente dargestellt werden kann.

---

## 3. Labels vollständig vereinheitlichen

Alle Labels, Badges, Statuschips und kleinen Kennzeichnungen müssen aus einem gemeinsamen Designsystem stammen.

Unterschiede zwischen Statuslabels, Kategorien, Warnungen, Filtern, Profilen, Kennzeichnungen und Zuständen sollen beseitigt werden.

### Ein gemeinsames Label-System

Verwende nur wenige definierte Varianten:

```text
[ Neutral ]
[ Info ]
[ Aktiv ]
[ Erfolg ]
[ Warnung ]
[ Fehler ]
```

Optional für fachliche Kategorien:

```text
[ Kategorie ]
```

### Verbindliche Regeln
Alle Labels müssen identisch definiert sein hinsichtlich:

- Höhe
- Padding
- Border-Radius
- Schriftgrösse
- Schriftgewicht
- Icon-Grösse
- Abstand zwischen Icon und Text
- Farblogik
- vertikaler Ausrichtung

Keine individuellen Badge-Stile pro Modul.

### Text
Labels möglichst kurz halten.

Nicht:

```text
Prüfung offen · Allergenangaben nicht erfasst
```

wenn die Information sinnvoll getrennt werden kann:

```text
[ Prüfung offen ]  [ Allergene fehlen ]
```

oder kompakter:

```text
⚠ Prüfung offen
```

mit Details bei Hover, Tooltip oder Aufklappen.

---

## 4. Einheitliche Komponenten statt lokaler Sonderlösungen

Suche im gesamten Frontend nach mehrfach implementierten:

- Buttons
- Listen
- Tabellen
- Badges
- Labels
- Statusanzeigen
- Filterleisten
- Suchleisten
- Aktionsgruppen

und ersetze sie nach Möglichkeit durch gemeinsame Komponenten bzw. gemeinsame CSS-Klassen.

Keine neue Sonderklasse nur für eine einzelne Seite erstellen, wenn eine bestehende Standardkomponente erweitert werden kann.

---

## 5. Visuelle Priorität reduzieren

Viele aktuelle Elemente wirken gleich wichtig. Das ändern.

### Hierarchie

**Primär**
- Seitentitel
- Hauptinhalt
- wichtigste Aktion

**Sekundär**
- Filter
- Status
- häufige Aktionen

**Tertiär**
- Details
- Zusatzinformationen
- seltene Aktionen

Tertiäre Aktionen nicht als grosse beschriftete Buttons darstellen.

---

## 6. App-weite Prüfung durchführen

Nicht nur die aktuell sichtbaren Seiten ändern.

Gehe danach **alle Views/Templates der Anwendung** durch und suche gezielt nach Abweichungen.

Insbesondere prüfen:

- Gibt es unterschiedlich gestaltete `Bearbeiten`-Buttons?
- Gibt es verschiedene `Anlegen`-Buttons?
- Gibt es mehrere Arten von Status-Badges?
- Gibt es Listen mit anderer Zeilenhöhe?
- Gibt es unterschiedliche Filterleisten?
- Gibt es unterschiedliche Suchfelder?
- Gibt es identische Aktionen mit unterschiedlichen Icons?
- Gibt es Labels mit abweichender Höhe oder Farbe?
- Gibt es lange Buttontexte, die durch Symbol oder kurzes Label ersetzt werden können?

Jede gefundene Inkonsistenz beheben.

---

# Entscheidungsregel

Wenn zwei UI-Elemente **dieselbe Bedeutung oder Funktion** besitzen, müssen sie:

1. gleich aussehen,
2. gleich positioniert sein, soweit sinnvoll,
3. dasselbe Symbol verwenden,
4. dieselbe Interaktionslogik besitzen.

Nicht pro Seite optimieren.

**Das Ziel ist ein gemeinsames, wiedererkennbares UI-System für die gesamte Anwendung.**

# Erwartetes Ergebnis

Nach diesem Lauf sollen Nutzer nicht mehr merken, dass verschiedene Bereiche möglicherweise zu unterschiedlichen Zeitpunkten entwickelt wurden.

Die komplette Anwendung soll wirken, als wäre sie aus **einem einzigen konsistenten Designsystem** entstanden.

Prioritäten:

**Konsistenz > Individualität**  
**Symbol + Kürze > lange Buttontexte**  
**Scanbarkeit > sichtbare Informationsmenge**  
**gemeinsame Komponenten > lokale Sonderlösungen**
