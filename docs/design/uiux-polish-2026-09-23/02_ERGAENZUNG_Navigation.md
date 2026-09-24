# Ergänzung zum laufenden UI-Polish-Lauf – Navigation

Ergänze den laufenden UI-Polish-Auftrag um folgende **verbindliche Regeln für die Hauptnavigation**.

## Ziel

Die Sidebar soll modern, ruhig, kompakt und eindeutig wirken.

Sie darf **nicht wie ein klassischer Tree-View oder Dateibaum** aussehen.

---

## Keine Linien für Hierarchie

Entferne in aufgeklappten Menüs:

- vertikale Verbindungslinien
- Baum-/Tree-Linien
- Einrückungs-Rails
- dekorative Linien zwischen Parent und Child
- optische Verbindungen, die wie ein technisches Admin-Tree-Menü wirken

Untermenüs werden **nicht durch Linien**, sondern durch:

- Einrückung
- Abstand
- Typografie
- Hintergrund
- aktiven Zustand

gruppiert.

---

## Navigation flach und modern darstellen

Bevorzugtes Muster:

```text
▣ Wochenplan                         ˄
   Cafeteria
   Patienten
   Wochenübersicht
   Küchenkalender

🍴 Menüs & Bausteine                 ›
◉ Vorschau & Bildschirme             ›
⚙ Einstellungen                      ›
```

Kein:

```text
▣ Wochenplan
│
├─ Cafeteria
├─ Patienten
├─ Wochenübersicht
└─ Küchenkalender
```

---

## Aktiver Zustand

Es darf nicht gleichzeitig mehrere starke aktive Flächen geben.

### Parent
Ist ein Unterpunkt aktiv, darf der Parent als geöffneter Bereich erkennbar bleiben, aber nur **dezent**.

### Aktiver Unterpunkt
Der tatsächlich aktive Eintrag erhält die deutlichste Hervorhebung:

- weicher Hintergrund
- kompakter Radius
- optional schmaler Accent
- gute Kontrastwirkung
- keine zusätzliche Verbindungslinie

Beispiel:

```text
▣ Wochenplan                         ˄

   ┌──────────────────────────────┐
   │ Cafeteria                    │  ← aktiv
   └──────────────────────────────┘
     Patienten
     Wochenübersicht
     Küchenkalender
```

Die Hervorhebung soll kompakt bleiben und nicht wie eine grosse verschachtelte Card wirken.

---

## Parent-Einträge

Menüpunkte mit Untermenüs erhalten rechts einen eindeutigen Zustand:

```text
› geschlossen
⌄ geöffnet
```

oder passende Icons aus der bereits verwendeten Icon-Bibliothek.

Keine zusätzlichen Texte wie:

`Untermenü öffnen`

verwenden.

---

## Icons

Icons nur für Hauptnavigation bzw. semantisch wichtige Punkte.

Unterpunkte benötigen standardmässig **kein eigenes Icon**, wenn dadurch nur visuelles Rauschen entsteht.

Regel:

```text
Hauptebene  = Icon + kurzer Text
Unterebene  = kurzer Text
```

Icons app-weit konsistent verwenden.

---

## Abstände

Navigation stärker über Spacing als über Linien strukturieren.

### Innerhalb einer Gruppe
kleiner Abstand

### Zwischen Hauptgruppen
deutlich grösserer Abstand

Dadurch entsteht die Hierarchie ohne zusätzliche Dekoration.

---

## Maximal sichtbare Komplexität

Nicht mehrere Navigationsgruppen gleichzeitig unnötig aufgeklappt halten.

Wenn sinnvoll:

- aktuell verwendete Gruppe geöffnet
- andere Gruppen geschlossen

Die Navigation soll nicht alle verfügbaren Funktionen gleichzeitig präsentieren.

---

## Breite und Text

Menüpunkte möglichst kurz benennen.

Vermeiden:

- mehrzeilige Navigationseinträge
- erklärende Texte im Menü
- lange Funktionsbezeichnungen

Navigation benennt **Orte/Funktionen**, sie erklärt sie nicht.

---

## Collapsed Sidebar

Die Sidebar soll bei Bedarf auf eine kompakte Icon-Leiste reduziert werden können.

Beispiel:

```text
┌─────┐
│ LOGO│
├─────┤
│  ▣  │
│  🍴 │
│  ◉  │
│  ⚙  │
│     │
│  KÜ │
│  ⇥  │
└─────┘
```

Im eingeklappten Zustand:

- nur Hauptnavigation
- Tooltips beim Hover
- aktiver Zustand weiterhin klar sichtbar
- Untermenüs bei Klick/Popover oder nach Aufklappen erreichbar
- keine abgeschnittenen Labels

---

## Benutzerbereich

Profil und Abmelden bleiben am unteren Rand.

Diesen Bereich optisch vom Navigationsinhalt trennen, jedoch zurückhaltend.

Keine übermässig starken Linien oder zusätzliche Cards.

---

## Visuelle Regel

Die Sidebar soll ihre Hierarchie primär über:

1. **Position**
2. **Einrückung**
3. **Abstand**
4. **Typografie**
5. **aktiven Hintergrund**

kommunizieren.

**Nicht über Linien und Baumstrukturen.**

---

## Abschlussprüfung

Gehe nach der Anpassung alle Navigationszustände durch:

- kein aktiver Eintrag
- Parent aktiv
- Child aktiv
- Gruppe geöffnet
- Gruppe geschlossen
- Hover
- Focus
- Mobile
- eingeklappte Sidebar
- lange Bezeichnungen
- mehrere Navigationsebenen

Entferne dabei alle verbleibenden Tree-View-Muster und stelle sicher, dass dieselbe Navigationslogik app-weit verwendet wird.

## Priorität

**Flache visuelle Hierarchie > Tree-View**  
**Spacing > Verbindungslinien**  
**ein klarer aktiver Zustand > mehrere starke Hervorhebungen**  
**ruhige Navigation > sichtbare Strukturtechnik**
