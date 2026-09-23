# Global UI Polish Run

Du arbeitest an einer bestehenden Webanwendung.

## Ziel

Führe einen **app-weiten UI/UX-Polish-Lauf** durch.

Die Anwendung soll danach:

- moderner
- ruhiger
- klarer
- kompakter
- hochwertiger
- konsistenter
- einfacher bedienbar

wirken.

Es geht **nicht** darum, einzelne Seiten isoliert neu zu gestalten. Entwickle stattdessen eine **einheitliche visuelle und funktionale Sprache für die gesamte Anwendung** und wende sie konsequent auf alle bestehenden und zukünftigen Oberflächen an.

## Grundprinzip

Ein Benutzer soll innerhalb von 2–3 Sekunden erkennen:

1. Wo bin ich?
2. Was ist hier wichtig?
3. Was kann oder soll ich als Nächstes tun?
4. Was ist nur Zusatzinformation?

Die Oberfläche darf nicht wie ein technisches Admin-Backend wirken, sondern wie eine fertige, moderne Fachanwendung.

---

## 1. Zuerst analysieren, dann ändern

Gehe die gesamte Anwendung systematisch durch und suche nach:

- unnötigem Leerraum
- zu hohen oder zu grossen Blöcken
- zu vielen sichtbaren Informationen gleichzeitig
- inkonsistenten Abständen
- inkonsistenten Buttons
- inkonsistenten Formularfeldern
- zu vielen Rahmen und Boxen
- unnötigen Card-in-Card-Strukturen
- wiederholten Informationen
- schlechten visuellen Hierarchien
- unklaren Hauptaktionen
- konkurrierenden Aktionen
- unnötigem Erklärungstext
- langen Textwänden
- inkonsistenten Icons
- schlechtem Alignment
- schlechter Nutzung der verfügbaren Bildschirmbreite
- Desktop-Layouts, die auf kleinen Displays nur verkleinert statt angepasst werden
- Informationen, die besser verborgen, zusammengefasst oder bei Bedarf eingeblendet werden könnten

Nicht nur offensichtliche Fehler korrigieren. Suche aktiv nach Bereichen, die technisch funktionieren, aber unnötig kompliziert, altmodisch oder unruhig wirken.

---

## 2. Einheitliches Designsystem

Definiere aus dem bestehenden Design ein kleines, verbindliches UI-System.

Vereinheitliche mindestens:

- Seitenabstände
- vertikale Abstände
- horizontale Abstände
- Grid
- Content-Breiten
- Schriftgrössen
- Schriftgewichte
- Überschriftenhierarchie
- Farben
- Hintergrundflächen
- Rahmen
- Radius
- Schatten
- Buttons
- Icon-Buttons
- Badges
- Statusanzeigen
- Inputs
- Selects
- Checkboxen
- Radios
- Tabellen
- Cards
- Dialoge
- Dropdowns
- Accordions
- Navigation
- Tooltips
- leere Zustände
- Ladezustände
- Fehlermeldungen
- Erfolgsmeldungen
- Warnungen

Vermeide individuelle Sonderlösungen pro Seite.

Wo möglich, bestehende Komponenten verbessern und wiederverwenden.

---

## 3. Informationshierarchie

Jede Ansicht braucht eine klare Reihenfolge:

**Primär**
- Seitentitel
- aktueller Kontext
- wichtigste Information
- wichtigste Aktion

**Sekundär**
- häufig benötigte Funktionen
- relevante Statusinformationen

**Tertiär**
- Details
- seltene Aktionen
- technische Informationen
- Zusatzinformationen

Tertiäre Inhalte sollen nicht dauerhaft denselben visuellen Stellenwert wie Primärinformationen haben.

Nutze dafür bei Bedarf:

- Accordion
- Dropdown
- Popover
- Tooltip
- Modal
- Drawer
- „Mehr“-Menü
- aufklappbare Details

Prinzip:

> So wenig wie möglich gleichzeitig anzeigen, aber alles mit wenigen Klicks erreichbar lassen.

---

## 4. Aktionen vereinfachen

Pro Bereich soll möglichst genau **eine visuell dominante Hauptaktion** existieren.

Unterscheide klar:

- Primary Action
- Secondary Action
- Tertiary Action
- Destructive Action

Nicht jede Aktion braucht einen grossen Button.

Nutze für kleinere Aktionen bevorzugt:

- Icon + Text
- Icon-Button
- Kontextmenü
- Inline-Aktion

Vermeide Reihen aus vielen gleich starken Buttons.

Destruktive Aktionen dürfen nie gleich aussehen wie normale Aktionen.

---

## 5. Texte reduzieren

Die Benutzeroberfläche soll sich weitgehend selbst erklären.

Prüfe jeden sichtbaren Hilfetext:

- Muss dieser Text permanent sichtbar sein?
- Kann ein kürzeres Label reichen?
- Kann er als Tooltip erscheinen?
- Kann er in einen Info-Dialog?
- Kann er vollständig entfernt werden?

Bevorzuge:

`Icon + kurzes Label`

statt:

`Icon + langer Erklärungssatz`

Labels sollen verständlich und handlungsorientiert sein.

---

## 6. Formulare vereinfachen

Formulare müssen kompakt und schnell erfassbar sein.

Regeln:

- zusammengehörige Felder gruppieren
- keine unnötig hohen Formularzeilen
- sinnvolle Mehrspaltenlayouts auf Desktop
- klare Einspaltenstruktur auf kleinen Displays
- Labels kurz halten
- optionale Details bei Bedarf aufklappen
- Standardwerte sinnvoll vorbelegen
- seltene Einstellungen zurücknehmen
- Validierung möglichst direkt am Feld
- Fehlermeldungen konkret und verständlich formulieren

Keine riesigen vertikalen Formulare erzeugen, wenn Inhalte sinnvoll nebeneinander passen.

---

## 7. Statusdarstellung vereinheitlichen

Statusinformationen müssen auf einen Blick erkennbar sein.

Verwende eine kleine Anzahl konsistenter Statusstile, zum Beispiel:

- neutral
- aktiv
- erfolgreich
- Warnung
- Fehler
- Information

Status möglichst als kompakte Kombination aus:

`Icon + kurzer Text`

darstellen.

Keine grossen Warnboxen verwenden, wenn ein Badge oder Inline-Hinweis genügt.

---

## 8. Platz effizient nutzen

Die Anwendung soll die verfügbare Arbeitsfläche sinnvoll verwenden.

Vermeide:

- künstlich schmale Inhaltsbereiche
- grosse leere Seitenränder
- riesige Cards mit wenig Inhalt
- überdimensionierte Header
- überdimensionierte Formulare
- unnötig hohe Tabellenzeilen
- übermässige vertikale Abstände

Gleichzeitig darf die Oberfläche nicht gedrängt wirken.

Ziel ist **hohe Informationsdichte mit guter Lesbarkeit**.

Desktop-Fläche aktiv nutzen.

---

## 9. Icons konsequent einsetzen

Icons sollen die Orientierung beschleunigen.

Verwende eine konsistente Icon-Bibliothek.

Icons müssen dieselbe Bedeutung überall gleich darstellen.

Beispiele für Kategorien:

- Hinzufügen
- Bearbeiten
- Löschen
- Speichern
- Zurück
- Weiter
- Öffnen
- Schliessen
- Prüfen
- Bestätigen
- Warnung
- Fehler
- Information
- Suche
- Filter
- Sortierung
- Einstellungen
- Mehr
- Kalender
- Benutzer
- Drucken
- Download
- Upload
- Sichtbarkeit
- Kopieren
- Verschieben

Wichtige Aktionen nicht ausschliesslich über schwer verständliche Icons darstellen.

Bei Bedarf:

`Icon + Text`

verwenden.

---

## 10. Navigation vereinfachen

Navigation muss ruhig und eindeutig sein.

Prüfe:

- unnötige Hierarchieebenen
- doppelte Navigation
- unnötig grosse Navigationselemente
- uneindeutige aktive Zustände
- inkonsistente Einrückungen
- zu viele gleichzeitig sichtbare Unterpunkte

Der aktuelle Bereich muss sofort erkennbar sein.

Unterbereiche nur anzeigen, wenn dies der Orientierung dient.

---

## 11. Responsive Verhalten

Nicht einfach die Desktop-Oberfläche verkleinern.

Definiere bewusst:

### Desktop
- breite Arbeitsfläche nutzen
- mehrere Spalten sinnvoll einsetzen
- schnelle Übersicht

### Tablet
- Spalten reduzieren
- Aktionen zusammenfassen
- ausreichend grosse Touch-Ziele

### Mobile
- klare lineare Struktur
- unwichtige Details einklappen
- Tabellen gegebenenfalls in Karten-/Listenansichten überführen
- keine horizontal unbenutzbaren Ansichten
- Hauptaktionen leicht erreichbar halten

---

## 12. Interaktion

Die Anwendung soll direkt und ruhig reagieren.

Sicherstellen:

- Hover-Zustände
- Focus-Zustände
- Active-Zustände
- Disabled-Zustände
- Loading-Zustände
- Success-Feedback
- Error-Feedback

Keine unnötigen Animationen.

Animationen nur dort einsetzen, wo sie Zustandswechsel verständlicher machen.

---

## 13. Accessibility

Bei allen Änderungen beachten:

- ausreichende Kontraste
- sichtbare Tastatur-Fokussierung
- sinnvolle Tab-Reihenfolge
- verständliche Labels
- klickbare Bereiche gross genug
- Status nicht nur durch Farbe darstellen
- Screenreader-taugliche Controls
- semantisch sinnvolles HTML

---

## 14. Bestehende Technik respektieren

Kein neues Frontend-Framework einführen, nur um das Design zu ändern.

Bestehende:

- Komponenten
- Templates
- CSS-Struktur
- JavaScript-Struktur
- UI-Bibliotheken

zuerst wiederverwenden und vereinheitlichen.

Neue Abstraktionen nur dann erstellen, wenn sie mehrere Stellen vereinfachen.

Keine unnötige technische Migration.

---

## 15. Konsistenz vor Kreativität

Das Ergebnis soll nicht aus vielen einzelnen „schönen“ Seiten bestehen.

Wichtiger ist:

- gleiche Logik
- gleiche Abstände
- gleiche Komponenten
- gleiche Aktionen
- gleiche Begriffe
- gleiche Statussprache
- gleiche visuelle Hierarchie

Wenn zwei Elemente dieselbe Funktion haben, sollen sie auch gleich aussehen und sich gleich verhalten.

---

## 16. Kein reines Cosmetic Polish

Nicht nur:

- Farben ändern
- Border-Radius erhöhen
- Schatten hinzufügen
- Buttons einfärben

Stattdessen auch aktiv verbessern:

- Informationsarchitektur
- Priorisierung
- Gruppierung
- Bedienwege
- Scanbarkeit
- Platznutzung
- Interaktionslogik
- visuelle Hierarchie

Das Ziel ist eine **spürbar einfachere Bedienung**, nicht nur ein moderner Skin.

---

## 17. Abschlussprüfung

Nach dem Umbau nochmals die gesamte Anwendung visuell und funktional prüfen.

Für jede Ansicht kontrollieren:

- Ist sofort klar, worum es geht?
- Ist die wichtigste Aktion sichtbar?
- Gibt es unnötige Informationen?
- Gibt es unnötigen Leerraum?
- Gibt es zu viele Buttons?
- Sind ähnliche Funktionen konsistent?
- Sind Statusinformationen verständlich?
- Ist die Ansicht auf Desktop gut genutzt?
- Ist sie auf Mobile sinnvoll bedienbar?
- Wirkt sie wie dieselbe Anwendung wie alle anderen Ansichten?

Danach verbleibende Inkonsistenzen selbstständig korrigieren.

---

# Gewünschtes Endergebnis

Die Anwendung soll sich anfühlen wie eine moderne, professionelle Fachanwendung:

- klar
- ruhig
- schnell erfassbar
- kompakt
- fehlertolerant
- visuell konsistent
- modern, aber nicht verspielt
- auch für technisch unerfahrene Benutzer verständlich

**Einfachheit hat Vorrang vor sichtbarer Funktionsfülle.**

**Konsistenz hat Vorrang vor individuellen Seitendesigns.**

**Bedienbarkeit hat Vorrang vor dekorativen Effekten.**

Führe den Polish-Lauf selbstständig über die gesamte Anwendung aus und behebe dabei auch Inkonsistenzen, die nicht explizit genannt wurden.
