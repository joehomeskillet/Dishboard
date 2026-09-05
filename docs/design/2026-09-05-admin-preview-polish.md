# Lesbare Vorschau des gespeicherten Wochenplans

Stand: 05.09.2026. WP `wp-68f10bd94989`. Basis `77422d9`.
Status: vom Root-Orchestrator freigegeben.

## Zweck und Gestaltung

Die Küche kontrolliert den zuletzt gespeicherten Plan für das gewählte Profil
und die gewählte Woche. Die heutige ungestaltete Vorschau zeigt vorhandene
Inhalte als schmale, lange Spalte. Eine klar eingerückte Wochenüberschrift und
ein responsives Tagesraster machen Tage, Mahlzeiten und Gerichte lesbar.
Die bestehende Südhang-Palette, Fira Sans und `--sh-*`-Tokens bleiben verbindlich.
Keine neuen Schriften, Bilder, Abhängigkeiten oder harten Farbwerte.

```text
PREVIEW
Vorschau · Patienten-Speiseplan
KW 36 / 2026 · Woche ab 31. August 2026
Zuletzt gespeicherter Stand · Entwurf
Wochentitel und gemeinsamer Hinweis

Montag                 Dienstag                Mittwoch
  Mittagessen            Mittagessen             Mittagessen
    Gericht + Beilagen     Gericht + Beilagen      Gericht + Beilagen
    Gericht + Beilagen     Gericht + Beilagen      Gericht + Beilagen
  Abendessen             Abendessen              Abendessen
    …                      …                      …

Donnerstag             Freitag                 Samstag
Sonntag
```

Das Raster zeigt bei 390 px eine Spalte, ab 800 px zwei und ab 1200 px drei
Spalten. Der Inhalt bleibt auch auf breiten Bildschirmen auf etwa 88 rem
begrenzt. Innerhalb eines Tages bleiben Mahlzeiten und ihre Optionen in der
vorhandenen Reihenfolge untereinander. Keine Textkürzung, feste Kartenhöhe oder
abgeschnittenen Inhalte. Tagesüberschriften sind optisch deutlich von Mahlzeiten
und Gerichten getrennt; die Tagesflächen verwenden ruhige bestehende Panels.

## Unveränderter Daten- und DOM-Vertrag

- `.preview-banner[role="status"]` enthält weiterhin exakt `PREVIEW`, ohne
  ergänzenden Text im Banner. Profil, Woche und Stand stehen separat darunter.
- Die bestehende `section` behält `data-preview="last-saved"`, `data-profile`,
  `data-week` und `data-workflow-state`; H1 und Titelreihenfolge bleiben erhalten.
- Ein umschliessendes `main#main-content.admin-preview` verbindet den bestehenden
  Skip-Link mit dem Inhalt. Keine zusätzlichen interaktiven Bedienelemente.
- KW, ISO-Wochenjahr und Montag kommen ausschliesslich aus vorhandenen
  `week`/`week_iso`-Werten und Datumsfiltern. Der Stand bezeichnet den bestehenden
  Workflow-State: Entwurf, Bereit, Publiziert oder Archiviert. Kein erfundener
  Speicherzeitpunkt und kein Zugriff auf publizierte Snapshots.
- Vorhandene Schleifen und Bedingungen für Tage, Services, Optionen, Komponenten,
  Servicehinweise und Cafeteria-Angaben bleiben erhalten. Keine neuen Datenquellen.
- Patienten-HTML enthält keine Zeichenfolge `preis|chf|rappen|kosten|price`.
- Keine Formulare, Writes, Scripts oder Inline-Styles. Public/Signage, Backend,
  Filter und übrige CSS-Abschnitte bleiben unverändert.

## Umsetzung und Abnahme

Änderungen nur an `admin/preview.html`, einem eigenen `.admin-preview`-Abschnitt
am Ende von `app.css`, neuen lokalen UI-Tests und dieser Spec. Der vorhandene
DOM-Vertrag bleibt fachlich unverändert. Im Projekt sind keine Komponenten-
Generatoren oder Frontend-Paketmanifeste vorhanden; bestehende Jinja-/CSS-Muster
werden verwendet. Bestehende Datumsfilter sind in `template_filters.py`.

Lokale Browserfixtures prüfen beide Profile bei 390×844 und 1440×1100 mit
vollständig gespeicherten Wochen. Assertions sichern alle gelieferten Tage,
Mahlzeiten, Titel, Komponenten und vorhandenen Hinweise/Angaben in Reihenfolge,
exakten PREVIEW-Text, Profil-/Wochen-/Standkontext, fehlenden horizontalen
Überlauf, sichtbaren Seitenrand und tatsächlich mehrspaltige Desktop-Geometrie.
Ohne JavaScript müssen alle Inhalte sichtbar bleiben. Kein Inline-Code; vorhandene
Route-Tests in `test_admin_draft_preview.py` sichern LAST-SAVED und fehlenden
Publikations-Fallback. Neue Screenshots entstehen nur lokal im Test-Artefaktpfad.
Teststart erst nach Abstimmung des exklusiven Slots mit dem Root.
