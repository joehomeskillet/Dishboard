# SDD – Dishboard konsistente Menü-Designsprache

## 1. Ziel
Dishboard soll wie **eine Anwendung** wirken. Heute unterscheiden sich Menüs, Bausteine, Zutaten, Rezepte, Kochbücher, Gerichtvorlagen, Einkaufslisten, Bestellung, Lager und Kalkulation stark in Informationsdichte, Filterlogik, Aktionen, Empty States und Formularaufbau. Ziel ist ein fehlertolerantes, schnell erfassbares Arbeitswerkzeug für Küche und Administration.

## 2. Produktprinzipien
**Konsistenz vor Individualität.** Gleiche Aufgabe = gleiches Muster. **Arbeitsfläche vor Dekoration.** Desktopbreite nutzen. **Erkennen vor Erinnern.** Status, nächste Aktion und Kontext sichtbar machen. **Progressive Disclosure.** Details erst öffnen, wenn nötig. **Fehler verhindern.** Pflichtfelder, Konsequenzen und unvollständige Daten früh anzeigen. **Ein primärer Weg.** Pro Zustand eine klar hervorgehobene Hauptaktion.

## 3. Informationsarchitektur
### Globale Navigation
- Wochenplan
- Menüs & Bausteine
- Vorschau & Bildschirme
- Einstellungen
- Benutzer/Abmelden im unteren Bereich

### Kontextnavigation: Menüs & Bausteine
Nur bei aktivem Oberpunkt sichtbar, eingerückt in der linken Sidebar: Menüs; Bausteine; Zutaten; Rezepte; Kochbücher; Gerichtvorlagen; Einkaufslisten; Bestellung; Lager; Kalkulation.

### Kontextnavigation: Einstellungen
Nur bei aktivem Oberpunkt sichtbar: Bereiche & Öffnungszeiten; Erscheinungsbild; Darstellung; Daten importieren; Schnittstellen; Benutzer & Zugriff.

Horizontale Haupt-Untermenüs werden entfernt. Kleine lokale Tabs sind nur innerhalb eines einzelnen Editors erlaubt, z.B. Rezept / Zutaten / Zubereitung / Weitere Angaben.

## 4. Standard-Seitenrahmen
Jede Arbeitsseite benutzt dieselbe Reihenfolge:
1. Seitentitel + ein Satz Zweck/Kontext.
2. Rechts maximal eine primäre globale Aktion.
3. **Statusbar** über die volle Inhaltsbreite.
4. Filter-/Suchbereich, nur wenn erforderlich.
5. Hauptinhalt als Tabelle, Liste, Editor oder Empty State.
6. Sekundäre/technische Bereiche nachrangig bzw. einklappbar.

## 5. Statusbar – eigenes Designsystem
Die Statusbar ist ein wiederverwendbarer Baustein und kein beliebiger Alert. 3–5 kompakte Felder, gleiche Position auf allen Modulen. Nur Informationen, die die nächste Entscheidung beeinflussen.

Mögliche Slots: Bereich/Profil; Objektstatus; Prüfstatus; Woche/Stichtag; Revision; Veröffentlichung; offene Aufgaben; Lager-/Bestellstatus. Statusfarben: neutral, Erfolg, Warnung, Fehler. Farbe nie alleiniger Informationsträger. Jeder Warnstatus enthält verständlichen Text. Bei editierbaren Objekten zeigt die Bar z.B. `Entwurf`, `ungespeicherte Änderungen`, `Allergenprüfung offen`, `Version 2`.

## 6. Listenstandard
Ein gemeinsames Listenschema: kompakter Filterblock; Trefferzahl; Tabellenkopf; Zeilen mit Hauptbezeichnung + höchstens einer sekundären Zeile; Status als Badge; Aktionen rechts. Ganze Tabellen sollen nicht durch riesige Zeilenhöhen auseinandergezogen werden. `Öffnen/Bearbeiten` konsistent benennen. Seltene Aktionen in `Weitere Aktionen`.

## 7. Formulare/Editoren
Felder logisch gruppieren, nicht einfach über die gesamte Breite strecken. Häufige Felder zuerst. Optionales und technisches Material einklappen. Speichern immer an vorhersehbarer Stelle. Bei langen Editoren darf eine kompakte sticky Aktionsleiste eingesetzt werden. Feldhilfen nur dort, wo sie eine Entscheidung unterstützen.

## 8. Module
### Menüs
Liste mit Profil/Bereich, Datum, Mahlzeit/Zuweisung und Prüfstatus. Warnungen wie Allergene nicht nur als zwei gelbe Badges wiederholen; zu einem verständlichen Prüfstatus zusammenführen. Detail öffnet fokussierten Editor.

### Bausteine
Gemeinsame Listenkomponente. Kategorie, Kennzeichnungen, Verwendung, Status. Kennzeichnungen nicht als unkontrollierte Badge-Wolke; priorisieren und Überlauf zusammenfassen.

### Zutaten / Grundlagen
Begrifflichkeit vereinheitlichen: Seitentitel soll dem Navigationspunkt entsprechen; `Grundlagen` nur verwenden, wenn es wirklich eine übergeordnete Domäne ist. Unterfunktionen Einheiten/Kategorien/Kennzeichnungen/Lagerorte als lokale Sekundärnavigation. Zutatenzeilen kompakt; Bearbeiten eindeutig.

### Rezepte
Filter deutlich reduzieren. Rezeptkarten nur, wenn Karten Mehrwert bieten; bei vielen Rezepten ist eine kompakte Liste/Tabelle vorzuziehen. Editor: lokaler Schritt-Navigator für Rezept, Zutaten, Zubereitung, weitere Angaben. Zutatenzeilen tabellarisch und kompakt. KI-Hinweis klar als Prüfpflicht kennzeichnen.

### Kochbücher
Empty State erklärt Zweck und bietet direkt `Kochbuch anlegen`. Suchleiste nicht dominanter als Inhalt. Leerer Bildschirm ohne nächsten Schritt ist verboten.

### Gerichtvorlagen
Tabellenstandard. Status, gebundenes Rezept und Planungsaktion klar trennen. Primäre Aktion `Vorlage anlegen`; Zeilenaktion nicht unnötig dominant.

### Einkaufslisten
Erstellung nicht dauerhaft als grosses Formular unter die Liste hängen. `Neue Einkaufsliste` öffnet fokussierten Bereich/Modal/Editor. Detailseite zeigt Statusbar mit Woche, Berechnungsstatus und offenen Positionen. Manuelle Positionen als kompakte Tabelle.

### Bestellung
Begriffe aus Küchensicht formulieren. Lieferanten, Artikel und Körbe als klar getrennte Arbeitsbereiche; Erstellung nicht drei gleichgewichtige Grosskarten. Leere Zustände mit nächster Aktion.

### Lager
Bestand, Lagerort und Zutat in kompakter Tabelle. Statusbar zeigt z.B. Zählstand/letzte bestätigte Zählung/offene Zuordnungen. `Kein Bestand erfasst` ist ein Zustand, nicht ein versteckter Text.

### Kalkulation
Aktuell sehr leer. Nutzer braucht geführten Ablauf: Berechnungsart → Objekt → Stichtag → Vorschau. Nach Berechnung Ergebniszusammenfassung mit fehlenden Preisen, Vollständigkeit und Gesamtsumme. Ohne Ergebnis klarer Empty State.

## 9. Einstellungen
Die gelieferten Screenshots sind positive Designreferenz: ruhige helle Fläche, dunkle Sidebar, Südhang-Akzent, kompakte Karten, klare Typografie. Bestehende horizontale Settings-Tabs werden in die kontextsensitive Sidebar verschoben. Inhalt und Funktionen bleiben erhalten.

## 10. Visuelles System
Bestehende Südhang-Farben beibehalten: dunkles Petrol für Navigation, Bordeaux/Pink als Akzent, warme helle Hintergrundfläche, weisse Cards. Keine neuen dekorativen Farbwelten pro Modul. Einheitliche Radius-, Border-, Spacing-, Input- und Button-Tokens definieren. Typografie mit klarer H1/H2/Label/Meta-Hierarchie.

## 11. Interaktion
Primärbutton: gefüllt in Akzentfarbe. Sekundär: Outline/neutral. Tertiär: Link/Icon+Text. Destruktiv: erst im Kontext sichtbar und Bestätigung bei irreversiblen Aktionen. Such- und Filterzustände müssen zurücksetzbar sein. Browser-Zurück darf nicht die einzige Navigation sein.

## 12. Accessibility
Tastaturbedienbar, sichtbarer Fokus, semantische Labels, ARIA bei Iconbuttons, ausreichender Kontrast, Status nicht nur durch Farbe, Touchziele sinnvoll gross. Responsive: Sidebar darf auf kleineren Geräten zu Drawer/kompakter Navigation werden; Tabellen erhalten sinnvolle mobile Darstellung statt horizontal unlesbarer Miniatur.

## 13. Nicht-Ziele
Kein Frameworkwechsel. Keine neue Businesslogik. Keine Datenbankmigration nur fürs Design. Keine grossflächige SPA-Neuentwicklung. Keine funktionslosen Design-Spielereien.

## 14. Definition of Done
Alle genannten Module teilen Navigation, Statusbar, Seitenkopf, Buttons, Filter, Tabellen, Forms, Badges und Empty-State-Muster. Horizontale Haupt-Untermenüs sind entfernt. Desktop nutzt Breite sinnvoll. Mobile ist bedienbar. Keine bestehende Kernfunktion ist verloren. Screenshots vor/nachher und Regressionstests liegen vor.
