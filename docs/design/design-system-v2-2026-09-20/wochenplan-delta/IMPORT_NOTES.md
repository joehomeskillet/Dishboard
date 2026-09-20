# Importhinweise zum Paket «Wochenplan Delta» (2026-09-20)

Das Paket konkretisiert laut seinem `README.md` die Regeln für den Bereich **Wochenplan**; bei direktem Widerspruch
haben seine Wochenplan-Regeln für diesen Bereich Vorrang, das Design System v2 bleibt Grundlage.

## Was geliefert wurde — und was hier liegt

- `README.md` und `04_REFERENCES/README.md`: unverändert übernommen.
- **Texte:** Die drei Textdateien des Pakets (`01_SDD/WOCHENPLAN_SDD.md`,
  `02_DESIGN_MANIFEST_UPDATE/WOCHENPLAN_DESIGN_MANIFEST_DELTA.md`, `03_CLAUDE_CODE/CLAUDE_CODE_WOCHENPLAN_PROMPT.md`)
  sind **bytegleich** mit den bereits eingecheckten v2-Dokumenten (`../02_SDD/DISHBOARD_UI_UX_SDD_V2.md`,
  `../03_DESIGN_MANIFEST/DESIGN_MANIFEST_V2.md`, `../05_CLAUDE_CODE/CLAUDE_CODE_UPDATE_PROMPT.md`; per SHA-256
  geprüft) und werden nicht doppelt abgelegt. Eine eigene, ausführlichere Wochenplan-Spezifikation war im Paket
  nicht enthalten; massgeblich bleiben SDD v2 §5–§6, Manifest v2 §10–§11 und die Muster M26–M30 der Designquelle.
- **Ist-Bilder** (`04_REFERENCES/IST/`, fünf Aufnahmen der produktiven Oberfläche): Die Browser-Leiste am oberen
  Bildrand (46 px, mit Profilfoto und Erweiterungssymbolen) ist abgeschnitten, weil dieses Repository öffentlich ist.
  Der Seiteninhalt ist unverändert.
- **Ziel-Mockup** (`04_REFERENCES/ZIELMOCKUP/01_wochenplan_mockup_uebersicht.png`): unverändert.

## Was die Ist-Bilder zeigen (Probleme und vorhandene Fachfunktion)

1. Cafeteria-Plan: horizontale Bereichs-Tabs über dem Inhalt; Statuschips «Prüfung offen», «9 Kartenprüfungen offen»,
   «10 ohne Allergenangaben»; fünf gleichgewichtige Aktionen; je Menü eine Karte mit bildschirmfüllendem Foto;
   Texte «Suppe noch nicht geplant»/«Dessert noch nicht geplant» als Fliesstext.
2. Patientenplan (zwei Ausschnitte): Mittag links oben, Abend rechts versetzt darunter — grosse Leerflächen, kein
   Raster; «Gänge planen» und «Ausgabeangaben ändern» als lose Textlinks.
3. Wochenübersicht: zweite horizontale Leiste (Cafeteria/Patienten) unter der ersten; hohe Tabellenzeilen mit
   gestapelten Schaltflächen «Öffnen» + Auge + «Kopieren»; der Rest der Seite leer.
4. Küchenkalender: Monatsraster listet für beide Bereiche jede Mahlzeit vollständig aus (sehr hohe Zellen, kein
   «+ n weitere»), Filter «Beide | Cafeteria | Patienten» und «+ Anlass» vorhanden, «Heute» markiert.

## Was das Ziel-Mockup zeigt

Fünf Bausteine in gleicher Sprache:
1. **Wochenübersicht (Liste):** Toolbar (Zurück/Zeitraum/«Heute», zwei Filter, Suche, eine Primäraktion), darunter je
   Tag/Menü EINE Zeile: Tag + Datum, kleines Thumbnail, Gerichtname + Komponenten, Kategorie-Badge, Allergen-Icons,
   Status-Badge, «Bearbeiten» + Overflow. Oben dezent der Veröffentlichungsstatus mit Hinweis
   «Änderungen speichern → Woche neu veröffentlichen».
2. **Schnell erfassen:** kurzes Formular (Tag, Menüname, Kategorie, Kurzbeschreibung, Allergene, eine Primäraktion).
3. **Tagesansicht:** Datum mit Vor/Zurück, «Tag kopieren»; Gruppen Mittagessen/Suppe/Dessert; kompakte Karten mit
   kleinem Bild, Name, Komponenten, Typ-Badge, Allergen-Icons, Status, «Bearbeiten» + Overflow.
4. **Menü bearbeiten:** kompakter Editor (Name, Kategorie, Beschreibung, Bild mit «Bild ändern», Allergene und
   Beilagen/Komponenten als Mehrfachauswahl, Tag/Zuweisung, «Weitere Optionen», «Abbrechen»/«Speichern»).
5. **Wochenansicht (Kalender):** Raster Mo–Fr × Mittagessen/Suppe/Dessert mit Thumbnail + Kurzname; Legende
   Veröffentlicht / Entwurf / Prüfung offen / Nicht geplant.

## Einordnung durch die Umsetzung (verbindlich für diese Welle)

Übernommen werden die **Muster**: eine Zeile je Menü mit kleinem Thumbnail, stabile Status- und Kategorie-Badges,
Allergen-Icons mit Text/Accessible Name, eine sichtbare Zeilenaktion + beschrifteter Overflow, kompakte
Tages- und Wochenraster, Add-Aktionen für nicht geplante Slots, eine Toolbar-Zeile, eine Primäraktion.

| Im Mockup | Entscheidung | Grund |
|---|---|---|
| Flache Sidebar mit allen Modulen als Hauptpunkte | nicht übernehmen | SDD v2 §3 (Text, bindend): drei Hauptpunkte mit Kontext-Unterpunkten links |
| «Schnell erfassen» mit freier Kategorie | nicht Teil eines UI-Pakets; separat entscheiden | neue Fachfunktion — heute entsteht ein Menü über Tages-/Slot-Editor bzw. «Gerichtvorlage einplanen» |
| «Tag kopieren», Suche und Bereichs-/Tag-Filter im Wochenplan | nur wo heute vorhanden, sonst separat entscheiden | neue Fachfunktionen (vorhanden ist das Kopieren ganzer Wochen) |
| Allergene als Dropdown-Mehrfachauswahl im Editor/Schnellerfassen | Muster M21 der Designquelle verwenden | Allergen und Präsenz sind indexgepaarte Formularfelder; Detail wird deaktiviert statt versteckt; «nicht gewählt/ungeprüft» erscheint nie als allergenfrei |
| Statuslegende Veröffentlicht/Entwurf/Prüfung offen/Nicht geplant | auf vorhandene Zustände abbilden | keine erfundenen Zustände; Prüf- und Veröffentlichungsstatus der Allergendeklaration bleiben unverändert |
| Beispielgerichte, Daten, Preise | keine Datenquelle | Mockup-Inhalte |
