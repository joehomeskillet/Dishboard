# Dishboard UI/UX SDD v2 – Gesamtsystem & Wochenplan

**Verbindliche Zielarchitektur.** Stack bleibt Flask + Tabler; kein Framework-Rewrite. Geltungsbereich: gesamter Adminbereich, Schwerpunkt Wochenplan. Akzeptierte Screenshots definieren die Designsprache; Ist-Screenshots zeigen Fachlichkeit/Probleme; generierte Mockups zeigen die Zielrichtung, sind aber nicht pixelgenau umzusetzen.

## 1. Produktziel
Dishboard muss wie **eine Anwendung** wirken. Nutzer erkennen sofort: Wo bin ich? Was ist der Zustand? Was ist als Nächstes zu tun? Welche Aktion ist primär? Backend-Komplexität wird nicht ungefiltert im UI gezeigt.

**Nicht-Ziele:** kein Funktionsabbau, kein neues Frontend-Framework, kein Datenmodell-Rewrite nur für Optik, keine pixelgenaue Kopie der Mockups.

## 2. Verbindliche Prinzipien
1. Progressive Disclosure: Sonderfälle/Technik erst bei Bedarf.
2. Eine dominante Primäraktion je Kontext.
3. Kompakt ohne gequetscht zu wirken; vertikalen Platz schützen.
4. Konsistenz vor Modul-Sonderdesign.
5. Verständliche Status vor Revisionen/IDs.
6. Fehlerprävention durch Defaults, Inline-Validierung und klare Folgen.
7. Übersicht zeigt Entscheidungskriterien; Details im Editor/Accordion/Drawer.
8. Keine tote UI: irrelevante Detailfelder nicht permanent anzeigen.
9. Weniger Klicks im häufigsten Workflow.
10. Fachfunktion erhalten, Darstellung vereinfachen.

## 3. Informationsarchitektur & Navigation
Die linke Hauptnavigation bleibt. Untermenüs wandern **in die linke Navigation** und erscheinen nur unter dem aktiven Hauptpunkt. Horizontale Navigationsleisten, die diese Funktion duplizieren, entfallen.

### Einstellungen
Bereiche & Öffnungszeiten · Erscheinungsbild · Darstellung · Daten importieren · Schnittstellen · Benutzer & Zugriff.

### Menüs & Bausteine
Menüs · Bausteine · Zutaten · Rezepte · Kochbücher · Gerichtvorlagen · Einkaufslisten · Bestellung · Lager · Kalkulation.

### Wochenplan
Cafeteria · Patienten · Wochenübersicht · Küchenkalender.

Editor-interne Tabs sind erlaubt, wenn sie echte Bearbeitungsschritte darstellen und keine globale Navigation duplizieren.

## 4. Einheitlicher Seitenrahmen
Reihenfolge: Seitentitel + Kurzbeschreibung → Statusleiste → Toolbar → Hauptinhalt → optionale/technische Details.

### Globale Statusleiste
Eigene wiederverwendbare Komponente. Zeigt nur entscheidungsrelevante Informationen, z. B. `Prüfung offen`, `9 Kartenprüfungen`, `10 ohne Allergenangaben`, Veröffentlichungsstatus, Zeitraum/KW. Statuschips dürfen direkt filtern/navigieren. Keine Dekoration ohne Aktion oder Informationswert.

## 5. Wochenplan – Zielmodell
Der Wochenplan wird in vier konsistente Ansichten verdichtet.

### 5.1 Cafeteria
Kompakte Wochenplanung statt riesiger Einzelkarten. Toolbar: Zeitraum/KW, Vor/Zurück, Heute, Filter, Suche, `+ Menü`.

Je Tag: Tag/Datum, Öffnungs-/Zeitstatus, konfigurierte Slots (z. B. Suppe, Menü 1, Vegetarisch, Dessert), Gerichtname, wichtigste Komponenten, Status, Allergenwarnung, kleines Thumbnail, Bearbeiten. **Keine bildschirmfüllenden Food-Fotos in der operativen Planung.** Grosse Bilder nur Vorschau/Detail.

### 5.2 Patienten
Klare Rasterstruktur statt verstreuter Karten und Leerflächen. Zeile = Tag; Spaltengruppe = Mittag/Abend; darin kompakte Slots. Nicht geplante Positionen als `+ Suppe planen`, `+ Dessert planen` usw. statt wiederholtem Fliesstext. Tagesdetail bei Bedarf öffnen.

### 5.3 Wochenübersicht
Kompakte Tabelle: KW/Zeitraum · Titel · Bereich · Status · offene Punkte · Aktionen. `Öffnen` primär; Kopieren/Vorschau/Archivieren sekundär oder Overflow.

### 5.4 Küchenkalender
Monatskalender zur Orientierung. Kurze Gerichtnamen, Bereich/Meal-Label, Filter `Beide | Cafeteria | Patienten`, Klick öffnet Tagesdetail. Bei Überfüllung `+ n weitere`. Heute klar markieren, aber nicht dominant.

## 6. Tagesansicht
Operativer Arbeitsplatz: Datum, Vor/Zurück, Heute, optional Tag kopieren. Meal-Gruppen Mittag/Abend. Karten zeigen kleines Bild, Gerichtname, Typ, Komponenten, Allergene, Status, Bearbeiten + Overflow. Nicht geplante Slots werden kompakte Add-Karten.

## 7. Menüeditor
Konsistenter Workflow: Basisdaten → Komponenten/Zutaten → Zubereitung → Kennzeichnungen/Allergene → weitere Angaben → Vorschau. Sticky Speicherleiste nur wenn sinnvoll: Abbrechen sekundär, Speichern primär. Keine zwei gleich starken Speichern-Aktionen.

## 8. Allergene & Kennzeichnungen
Das Muster `Checkbox + für jedes Allergen permanentes Dropdown` ist verboten. Standard: kompakte Mehrfachauswahl als Chips/Checkbox-Kacheln; ausgewählte Allergene klar markiert; Standardbedeutung `enthält`; abweichende Präsenzangabe erst nach Auswahl/in Details; Modus `automatisch aus Bausteinen` vs. `manuell`; Zusammenfassung der Auswahl. Desktop 2–4 Spalten, responsive.

**Wichtig:** Allergene sind nur ein Beispiel. Das Team sucht systemweit nach demselben Grundproblem: UI zeigt Optionen/Details, bevor sie gebraucht werden.

## 9. Listen, Tabellen, Karten
Tabellen für viele vergleichbare Objekte (Wochen, Zutaten, Lager, Bestellungen, Vorlagen). Karten nur bei visuellem Inhalt oder mehreren fachlich relevanten Informationen. Kompakte Zeilen; Status konsistent; Aktionen rechts; max. 1–2 direkte Aktionen, Rest Overflow; keine Karten mit überwiegend Leerraum.

## 10. Suche & Filter
Gemeinsame Filterbar: Suche · wichtigste Filter · Weitere Filter · Zurücksetzen. Aktive Filter sichtbar. Zurücksetzen nur wenn nötig. Trefferzahl dezent. Keine modulindividuellen Filter-Layouts ohne Grund.

## 11. Formulare
Labels oberhalb; zusammengehörige Felder nebeneinander; keine Full-Width-Felder ohne Grund; optionale Sonderfälle unter `Weitere Optionen`; Hilfetexte nur bei Bedarf; Inline-Validierung nahe am Feld; sinnvolle Defaults.

## 12. Empty States
Jeder Empty State beantwortet: Was fehlt? Warum? Was kann ich tun? Kompakter Call-to-Action statt riesiger leerer Fläche.

## 13. Responsive
Desktop primär, Tablet/Mobile verpflichtend. Sidebar → Drawer; Tabellen dürfen in priorisierte Listen wechseln; kein horizontales Scrollen bei Standardformularen; Statusbar darf umbrechen; Primäraktion erreichbar; Touch-Ziele ca. 44 px.

## 14. Accessibility
WCAG-orientierter Kontrast; Status nie nur Farbe; sichtbarer Fokus; semantische Labels; Accessible Names; korrekte Tabellenstruktur; Fehler programmatisch Feldern zuordnen.

## 15. Visuelle Tokens
Bestehende Südhang-Sprache: dunkles Petrol/Grün Sidebar, Bordeaux/Magenta Akzent/Primäraktion, warmer heller Hintergrund, weisse Karten, feine neutrale Borders, pastellige Statusfarben, zurückhaltende Radien, bestehende Fira-Sans-Typografie. Keine neuen Modulfarben, keine dekorativen Gradients, kein generischer „AI SaaS“-Look.

## 16. Systemweiter Audit
Vor Massenänderungen alle Routes/Templates/Partials erfassen: `Route | Template | Pattern | Problem | Zielkomponente | Priorität | Risiko`.

Suchen: horizontale Subnavigation; wiederholte Labels/Hilfetexte; permanente Detailfelder; inkonsistente Save/Cancel-Positionen; unterschiedliche Filterbars/Status; riesige Bilder; ungenutzte Breite/Höhe; technische Informationen im Vordergrund; unterschiedliche Empty States; redundante Aktionen.

## 17. Implementierungsstrategie
- **WP0 Inventar:** Routes, Templates, Komponenten, CSS/JS, Tests.
- **WP1 Tokens/Primitives:** Spacing, Buttons, Badges, Forms, Cards, Tables.
- **WP2 Shell/Navigation:** kontextuelle linke Subnavigation.
- **WP3 Status/Toolbar:** gemeinsame Komponenten.
- **WP4 Wochenplan:** Cafeteria, Patienten, Wochenübersicht, Kalender, Tagesansicht.
- **WP5 Editor/Formulare:** Menüeditor inkl. Allergene.
- **WP6 Menüs & Bausteine:** alle Module migrieren.
- **WP7 Einstellungen:** akzeptierte Designsprache bewahren, Navigation migrieren.
- **WP8 Responsive/A11y.**
- **WP9 Regression/Visual QA.**

Jedes WP klein halten, Tests ausführen, Vorher/Nachher-Screenshots erzeugen und erst dann weiter.

## 18. Acceptance Criteria
- keine globale horizontale Subnavigation für Wochenplan, Menüs & Bausteine, Einstellungen;
- Unterpunkte links nur beim aktiven Hauptpunkt;
- Wochenplan auf 1440px ohne unnötige riesige Leerflächen;
- operative Übersichten ohne bildschirmfüllende Food-Fotos;
- einheitliche Badge-, Toolbar-, Filter-, Listen- und Aktionslogik;
- Allergene ohne permanente Dropdown-Liste;
- primäre Workflows benötigen weniger Interaktionen;
- Desktop/Tablet/Mobile funktionieren;
- bestehende Berechtigungen, Validierungen und Fachfunktionen bleiben erhalten;
- visuelle Regression wird anhand der Referenzscreens geprüft.

## 19. Referenzpriorität
1. `accepted-settings`: verbindliche reale Designsprache.
2. `generated-mockups`: gewünschte Vereinfachungslogik/Informationsarchitektur.
3. `current-weekplan` und `current-modules`: fachlicher Ist-Stand und Anti-Patterns.

Bei Konflikt gilt: Fachfunktion des Ist-Systems erhalten, visuelle Sprache der akzeptierten Screens nutzen, Interaktionsprinzipien der Mockups anwenden.
