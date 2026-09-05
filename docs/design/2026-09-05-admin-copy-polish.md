# Copy-Bestätigung im Admin-Design

Stand: 05.09.2026. WP `wp-2dea2e9283d2`. Basis `082b815`.
Status: vom Root-Orchestrator freigegeben.

## Zweck und Gestaltung

Küchenmitarbeitende bestätigen die Übernahme der gespeicherten Vorwoche in
eine leere Zielwoche. Die heutige rohe HTML-Seite wird zu einer fokussierten
Admin-Ansicht mit Südhang-Logo, Fira Sans und bestehenden `--sh-*`-Tokens.
Der ruhige, links ausgerichtete Inhalt zeigt zuerst das Profil und danach
Quelle und Ziel als beschriftetes Wochenpaar. Die Zielwoche wird typografisch
hervorgehoben. Keine zusätzliche Navigation oder neue Bildsprache.

```text
Klinik Südhang                         Menüplanung
Vorwoche kopieren
Cafeteria / Patienten

Quellwoche                           Zielwoche
KW 36 · 31.08.2026                  KW 37 · 07.09.2026

Woche vom 31.08.2026 in die leere Woche vom 07.09.2026 kopieren.

[Vorwoche kopieren] [Zurück zur Wochenübersicht]
```

Es erscheint genau das URL-abgeleitete Profil, als „Cafeteria“ oder
„Patienten“. Quelle und Ziel enthalten ISO-KW, ISO-Wochenjahr und das lokale
Montagsdatum `DD.MM.YYYY`, damit auch Jahreswechsel eindeutig bleiben.
Auf schmalen Geräten stehen Wochen und Aktionen untereinander.

## Unveränderter Vertrag

- H1 und Primäraktion: exakt „Vorwoche kopieren“.
- Erklärung: exakt „Woche vom {Quelle} in die leere Woche vom {Ziel} kopieren.“
- Abbrechen über „Zurück zur Wochenübersicht“; normales GET-Linkziel
  ist die Übersicht desselben Profils und derselben Zielwoche.
- Ein natives POST-Formular an `admin.copy_post` mit exakt vier Hiddenfields:
  `_csrf`, `source_week`, `target_week`, `target_row_version`. Der Submit-Button
  hat keinen Namen. Kein neuer Bestätigungsschritt und kein JavaScript nötig.
- `main#main-content` behält `data-profile`, `data-source-week`, `data-target-week`.
- Patienten-HTML enthält keine Zeichenfolge `preis|chf|rappen|kosten|price`.
- Copy-POST, AuthZ, CSRF, Validierung, Zielprüfung und Store bleiben unverändert.

## Umsetzung und Abnahme

Neue `admin/copy.html` erweitert `base.html`: Viewport, externer Stylesheet,
lokale Schriften und Skip-Link. Der Copy-GET-Erfolgszweig rendert diese Vorlage;
dafür wird nur `render_template` zu den Flask-Imports ergänzt. Globale `_page`
und alle übrigen Handler bleiben unverändert. Falls nötig, ergänzt ein eigener
`.admin-copy`-Abschnitt am Ende von `app.css` ausschließlich diese Ansicht.
Keine Inline-Skripte/-Styles, neuen Abhängigkeiten oder harten Farbwerte.
Im Projekt sind keine Komponenten-Generatoren oder Frontend-Paketmanifeste
vorhanden. Bestehende native Jinja-/CSS-Muster werden wiederverwendet.

Alle sichtbaren Aktionen sind mindestens 44 px hoch; Fokus bleibt sichtbar,
Zoom erlaubt und die Seite funktioniert ohne JavaScript. Keine Animationen.
Neue lokale Browsertests prüfen beide Profile bei 390×844 und 1440×1100:
Viewport/geladene CSS, Profil/Datums-/KW-Kontext, kein horizontaler Überlauf,
44-px-Aktionen, exakte vier Formwerte sowie native Kopie mit 303 und Zielinhalt.
Abbrechen kehrt zur Zielwoche zurück und erzeugt keine Kopie. Bestehende
Route-/Storetests sichern Fehlerfälle weiterhin ab. Browser-/DB-Tests laufen
erst im exklusiv vom Root vergebenen Testslot; keine Produktionsschreibaktionen.
