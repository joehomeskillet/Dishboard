# Dishboard Design Manifest v2

Dieses Manifest ist **verbindlich für bestehende und zukünftige Seiten**.

## Leitsatz
**So wenig UI wie möglich, so viel Information wie nötig.** Eine Funktion soll überall gleich aussehen und sich gleich verhalten.

## 1. Nutzer zuerst
Die Oberfläche ist für Küchen- und Administrationsalltag gebaut, nicht für die Darstellung des Datenmodells. Technische Begriffe, UUIDs, Revisionen, Quellen und interne Zustände sind sekundär.

## 2. Platz ist eine Ressource
Keine unnötig hohen Formblöcke, keine gigantischen Bilder in Arbeitsansichten, keine Karten mit Leerraum, keine permanenten Detailfelder. Volle verfügbare Arbeitsbreite sinnvoll nutzen.

## 3. Progressive Disclosure
Der Normalfall ist sofort bedienbar. Sonderfälle werden aufgeklappt. Beispiele: Allergen-Details erst nach Auswahl; technische Metadaten in `Details`; seltene Aktionen in Overflow; erweiterte Filter nur bei Bedarf.

## 4. Konsistente Hierarchie
Jede Ansicht folgt: **Kontext → Status → Aufgabe → Primäraktion → Details**. Nicht jedes Modul erfindet seine eigene Seitenstruktur.

## 5. Navigation
Hauptnavigation links. Kontext-Untermenüs ebenfalls links und nur sichtbar, wenn der Hauptpunkt aktiv ist. Keine horizontale Doppel-Navigation. Editor-Schritte dürfen Tabs/Stepper nutzen.

## 6. Aktionen
Eine Primäraktion pro Kontext in Bordeaux. Sekundäraktionen neutral. Destruktive Aktionen nicht prominent, aber eindeutig. Seltene Aktionen in Overflow. Gleiche Aktion = gleiches Icon, Label, Position und Verhalten.

## 7. Status
Status als kompakte Badges mit Text + Farbe. Farben unterstützen, ersetzen aber nie die Beschriftung. Gleiche Statusfamilie überall gleich. Warnungen nur bei Handlungsbedarf.

## 8. Formulare
Kompakt, logisch gruppiert, sinnvolle Defaults, Inline-Validierung. Felder nur zeigen, wenn relevant. Keine 100%-Breite ohne Grund. Wiederholte Datensätze als Zeilen/Repeater statt riesige Einzelkarten.

## 9. Listen
Informationen so anordnen, dass Scannen möglich ist. Titel zuerst, Kontext darunter, Status an stabiler Position, Aktionen rechts. Direktaktionen begrenzen.

## 10. Bilder
Bilder sind Inhalt, keine Platzfüller. In Übersichten kleine Thumbnails; gross nur in Vorschau/Detail, wenn visuell relevant. Lazy Loading und konsistente Seitenverhältnisse.

## 11. Wochenplan
Der Wochenplan ist ein Arbeitswerkzeug. Möglichst viele relevante Tage/Slots auf einen Blick. Nicht geplante Slots werden als kompakte Add-Aktion gezeigt. Warnungen sind filter-/bearbeitbar. Wechsel zwischen Cafeteria, Patienten, Wochenübersicht und Küchenkalender erfolgt über die linke Kontextnavigation.

## 12. Responsive
Desktop nutzt Breite; Tablet/Mobile reduzieren Spalten und priorisieren Inhalte. Keine Desktop-Tabelle stumpf horizontal scrollbar machen, wenn eine sinnvolle mobile Liste möglich ist.

## 13. Accessibility
Keyboard, Fokus, Kontrast, semantische Labels, Touch-Ziele und Screenreader-Namen sind Teil des Designs, kein späteres Add-on.

## 14. Verbotene Anti-Patterns
- horizontale Subnavigation zusätzlich zur Sidebar;
- mehrere gleich starke Primärbuttons;
- permanent sichtbare Sonderoptionen;
- Status nur durch Farbe;
- technische IDs als Hauptinformation;
- grosse leere Karten;
- Fullscreen-Food-Fotos in operativen Planungslisten;
- unterschiedliche Filter-/Speicherlogik pro Modul;
- Icons ohne Text, wenn Bedeutung nicht offensichtlich;
- Hilfetexte, die dieselbe Information ständig wiederholen.

## 15. Definition of Done für jede UI-Änderung
Die Seite ist konsistent mit bestehenden Komponenten, platzsparender als vorher, der häufigste Workflow ist nicht länger, Keyboard/Responsive funktionieren, Status/Aktionen sind eindeutig, und es existiert ein Vorher/Nachher-Screenshot für Review.
