# Dishboard – erweiterte Screenshot-Referenzen

**Acht neue Sollbilder: sechs Desktopansichten und zwei mobile Ansichten.** Neun ursprüngliche Ist-Bilder sind unverändert enthalten. Die neuen Bilder sind browsergerenderte statische Designentwürfe, keine Aufnahmen der laufenden Anwendung.

Öffne [ANSICHTEN.html](ANSICHTEN.html) für die lokale Bildgalerie oder [UI_REFERENZEN.md](UI_REFERENZEN.md) für den Agentenauftrag mit Ist/Soll-Paaren, Anforderungen und Freigaben. [Übersicht der sechs Desktopentwürfe](vergleich/UEBERSICHT.png).

| Bild | Datei | Viewport (CSS-Pixel) | Vollständiges Bild (Pixel) |
|---|---|---:|---:|
| R1-menues | [Bild öffnen](soll/R1-menues.png) | 1600 × 1100 | 2400 × 1713 |
| R2-wochenverwaltung | [Bild öffnen](soll/R2-wochenverwaltung.png) | 1600 × 1100 | 2400 × 1650 |
| R3-baustein-bearbeiten | [Bild öffnen](soll/R3-baustein-bearbeiten.png) | 1600 × 1100 | 2400 × 1701 |
| R4-druckvorlagen | [Bild öffnen](soll/R4-druckvorlagen.png) | 1600 × 1100 | 2400 × 1719 |
| E1-wochenplan | [Bild öffnen](soll/E1-wochenplan.png) | 1600 × 1100 | 2400 × 1901 |
| E2-menueeditor | [Bild öffnen](soll/E2-menueeditor.png) | 1600 × 1100 | 2400 × 1662 |
| R1-menues-mobil | [Bild öffnen](soll/R1-menues-mobil.png) | 390 × 844 | 780 × 3198 |
| E1-wochenplan-mobil | [Bild öffnen](soll/E1-wochenplan-mobil.png) | 390 × 844 | 780 × 7218 |

## Bedeutung und Grenzen

Alle acht neuen Zielbilder sind `ENTWURF`. Die Freigabe wird ausschliesslich in `UI_REFERENZEN.md` gepflegt. Beispieldaten, Rollenanzeigen, Prüfstände und Menüpreise definieren keine echten Daten oder neue Backendfunktionen. Für E3–E5 fehlen weiterhin neue Zielbilder. Der Menüeditor ist als vollständige Seite gezeigt; ein seitlicher Editor ist hier nicht als bereits umgesetzt nachgewiesen.

Die separaten generierten Bilder X1 und X2 sind keine verbindlichen Sollreferenzen. X2 ist als Zielbild verworfen. Die neun Originale unter `ist/` wurden nicht verändert.

## Für Coding-Agenten

Die Vorgaben bleiben: Flask und Tabler erhalten; technische und fachliche Verträge nicht verändern. Bilder ergänzen den Textauftrag, sie ersetzen keine Bestandsaufnahme. Zuerst `AGENTS.md`, `UI_REFERENZEN.md` und die referenzierten Grundlagen lesen.

## Reproduzierbare Referenzdateien

Unter `vorlagen/` liegen sechs isolierte HTML-Seiten, eine gemeinsame CSS-Datei und ein Logo-Ausschnitt aus einem vorhandenen Screenshot. Keine Fontdateien und keine zusätzlichen Frameworks sind mitgeliefert. Das ist keine produktionsfertige Flask-Anwendung. Der Rendering-Fallback verwendet vorhandene Systemschriften; im Projekt die bereits eingebundene Schrift beibehalten.

Die optionalen Werkzeuge unter `werkzeuge/` bauen diese Referenzen neu. `build_mockups.py` benötigt nur die Python-Standardbibliothek. `render_mockups.py` benötigt separat vorhandenes Playwright und Chromium; diese Werkzeuge nicht als neue Produktionsabhängigkeiten installieren. Die vorhandenen PNGs und die Galerie funktionieren ohne Python. Alle Referenzseiten sind lokal und ohne externe Schrift-/Bildabrufe nutzbar.

[Prüfung des Referenzpakets](grundlagen/PRUEFUNG_REFERENZPAKET.md) · [Bildherkunft](grundlagen/BILDHERKUNFT.md)
