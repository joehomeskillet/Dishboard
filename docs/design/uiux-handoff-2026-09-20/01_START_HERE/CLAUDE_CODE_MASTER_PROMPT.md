# Claude Code – Dishboard UI/UX Modernisierung

Du übernimmst die Rolle eines vollständigen Produkt-/UX-/Frontend-/QA-Teams. Arbeite auf der bestehenden Flask+Tabler-Anwendung **inkrementell**. Kein Framework-Wechsel, keine Businesslogik neu erfinden.

## Auftrag
1. Lies zuerst `02_SDD/UI_UX_SDD.md`, danach `05_IMPLEMENTATION/IMPLEMENTATION_PLAN.md` und `06_QA/ACCEPTANCE_CHECKLIST.md`.
2. Nutze `03_REFERENCES/accepted-settings/` als **positive visuelle Referenz**. Die Dateien in `to-redesign/` dokumentieren Inkonsistenzen, nicht Zielzustände.
3. Öffne die HTML-Mockups in `04_MOCKUPS/`. Sie definieren Informationsarchitektur und wiederkehrende Muster, nicht pixelgenaue Templates.
4. Analysiere die reale Codebasis vor Änderungen. Finde gemeinsame Layout-, Navigation-, Card-, Table-, Form-, Badge-, Empty-State- und Button-Komponenten.
5. Implementiere zuerst Shell/Navigation/Statusbar/Design-Tokens, danach Module in kleinen Work Packages.
6. Keine Funktion entfernen. Bestehende URLs, Datenmodelle und Berechtigungen soweit möglich erhalten.
7. Nach jedem WP: Tests, responsive Sichtprüfung, Tastaturbedienung, Regressionen.

## Nicht verhandelbar
- Volle verfügbare Arbeitsbreite; keine künstlich schmalen Adminseiten.
- Keine horizontale Modul-Tab-Leiste für Haupt-Unterbereiche.
- Unterpunkte erscheinen links **nur wenn ihr Oberpunkt aktiv ist**.
- `Einstellungen` erhält links: Bereiche & Öffnungszeiten, Erscheinungsbild, Darstellung, Daten importieren, Schnittstellen, Benutzer & Zugriff.
- `Menüs & Bausteine` erhält links: Menüs, Bausteine, Zutaten, Rezepte, Kochbücher, Gerichtvorlagen, Einkaufslisten, Bestellung, Lager, Kalkulation.
- Jede Arbeitsseite folgt derselben Hierarchie: Titel/Kontext → globale Statusbar → Filter/Aktionen → Inhalt → sekundäre Details.
- Eine gemeinsame Statusbar ist ein eigenes UI-System und zeigt nur entscheidungsrelevante Informationen.
- Primäraktion pro Kontext klar; Sekundäraktionen visuell zurückhaltend; destruktiv nie als Standardaktion.
- Progressive Disclosure: seltene/technische Optionen einklappen.
- Icons immer mit verständlichem Text, ausser bei etablierten Kleinstaktionen mit Tooltip/ARIA.
- Warnungen müssen erklären, **was fehlt und was als Nächstes zu tun ist**.
- Mobile und Desktop müssen funktionieren.

## Arbeitsmodus
Erstelle zuerst eine kurze Bestandsaufnahme und einen konkreten Dateiplan. Danach implementieren. Keine riesige Komplett-Neuschreibung. Wiederverwendbare Komponenten bevorzugen. Dokumentiere Abweichungen vom SDD begründet.
