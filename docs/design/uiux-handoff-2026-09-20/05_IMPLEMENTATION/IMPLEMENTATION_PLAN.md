# Implementierungsplan

## WP0 – Inventar
Routen/Templates/Partials/CSS/JS erfassen; bestehende Tabler-Komponenten identifizieren; Screenshot-Baseline erstellen. Keine Funktion ändern.

## WP1 – Design Tokens + App Shell
Gemeinsame Spacing-, Radius-, Border-, Button-, Input-, Badge- und Typografieklassen; Content-Container auf volle verfügbare Breite; responsive Shell.

## WP2 – Navigation
Kontextsensitive Sidebar. Unterpunkte nur bei aktivem Oberpunkt. Aktive Route eindeutig. Mobile Drawer. Alte horizontale Hauptnavigation entfernen, lokale Editor-Tabs behalten.

## WP3 – Statusbar
Reusable Partial/Component mit Slots/Items und Statusvarianten. In jedem Modul passende, wirklich relevante Werte anbinden; keine erfundenen Daten.

## WP4 – Listenmuster
Shared Page Header, Filterbar, Table/List, Row Actions, Pagination/Trefferzahl, Empty State. Zuerst Menüs/Bausteine/Zutaten, dann Gerichtvorlagen/Lager.

## WP5 – Rezeptsystem
Rezeptliste und Editor vereinheitlichen. Zutaten und Schritte kompakt; lokale Editor-Navigation; Warnungen und Speichern konsistent.

## WP6 – Arbeitsprozesse
Kochbücher, Einkaufslisten, Bestellung und Kalkulation auf geführte Workflows umstellen. Keine Businesslogik verändern.

## WP7 – Einstellungen
Akzeptiertes Erscheinungsbild erhalten, aber horizontale Settings-Navigation in Sidebar überführen. Regression gegen Referenzscreenshots.

## WP8 – Responsive/A11y/QA
360/768/1024/1440+ testen; Keyboard; Fokus; Kontrast; Labels; leere/volle/Fehlerzustände; visuelle Regression.

## Reihenfolge-Regel
Kein Modul isoliert mit Sonder-CSS lösen. Fehlt ein Muster, zuerst gemeinsame Komponente erweitern. Änderungen klein und reviewbar halten.
