# Küchenkalender-Monatsraster — Designentscheid

Stand 2026-09-16. Bindend für MP-CAL-MONTH und MP-CAL-NAV. Baut auf
`docs/design/2026-09-09-unified-ui-design-system.md` auf. Keine neue JS-Kalenderbibliothek.
`layout_variant=calendar`.

## Entscheidung

Ein ISO-Monatsraster in der Admin-Arbeitsfläche (volle Breite, R01). Jede Zelle ist ein
Kalendertag. Inhalt der Zelle, kompakt:

1. Tageszahl
2. Menü-/Workflow-Status je sichtbarem Bereich (Cafeteria `staff_guest`, Patienten `patient`)
3. Betriebliche Ausnahme (geschlossen/Feiertag/Zeiten) als Badge, nicht als dritte Mahlzeit
4. Anlass-Marker (Punkt + Kurz-Titel), sobald Anlässe existieren; Marker skalieren nichts

Filter E1: Cafeteria / Patienten / beide. Standard beide. Filter ändert nur die Anzeige,
nicht die Daten.

Navigation (MP-CAL-NAV): Vor/Zurück Monat, Sprung auf Datum, Eintrag in der bestehenden
Sidebar. Einziger neuer Schreiber von `_workflow_sidebar.html` unter MP-CAL-*.

Keine vendored Kalenderbibliothek, kein inline JS (`script-src 'self'`). Server rendert das
Raster. Anlässe sind Marker, nicht `menu_weeks.workflow_state`.

## R11

- Route in `docs/superpowers/backlog-0909/ui-route-matrix.json` vor UI-Freeze
- Pflicht-Viewports: 390×844 und 1440×900
- Neues Muster zusätzlich: 1024×768, 768×1024, 1920×1080
- `layout_variant=calendar`
- Tokens und Tabler aus dem Unified-UI-Manifest; keine harten Hex-Farben

## Werkzeugleiste und Darstellung (2026-09-16)

Eine gemeinsame Kalender-Werkzeugleiste: Vor/Zurück, zentrale Monatsauswahl (`type=month`, autosubmit, Filter bleibt in der URL), «Heute», Bereichsfilter Beide/Cafeteria/Patienten. Kein zusätzlicher Bestätigungsbutton mit JS; ohne JS bleibt ein `noscript`-Absenden.

Raster: sieben gleich breite Spalten, Mindestzellenhöhe, Nachbartage gedämpft, Heute über `effective_today()` (Europe/Zurich). Sichtbare Labels: `staff_guest`→Cafeteria, `patient`→Patienten, `LUNCH`→Mittagessen, `DINNER`→Abendessen. Menütitel aus `menu_items` in derselben Bereichsabfrage. Status nur aus `service_state` (Geschlossen/Feiertag/Betriebsferien), nie aus leerem Tag oder Wochenende.

Mobil unter 768px: Tagesliste des gewählten Monats statt sieben Mini-Spalten, dieselben Filter und Aktionen. Tageskopf führt in den bestehenden Wochenplan; Menütitel auf `admin.menu_get`.

## Nicht in diesem Entscheid

Schema 0032, Anlass-Bausteine, Einkaufssummen im Raster. MP-CAL-DAY/LIST als eigene Pakete bleiben später; die mobil Liste ist die responsive Darstellung desselben Monats.
