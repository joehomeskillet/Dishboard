# Designregeln für Website, Mobile und Digital Signage

## Kanaltrennung

| Kanal | Kennzeichnung | Inhalt |
|---|---|---|
| Patienten | „Patienten-Speiseplan“ | Mo–So, Mittag und Abend, Menü 1 und Vegetarisch; keine Kosteninformation |
| Cafeteria | „Cafeteria · Mitarbeitende und externe Gäste“ | Mo–Fr, Mittag, Menü 1 und Vegetarisch; zwei Kostenansätze |

Die Trennung erfolgt nicht nur über Farbe. Überschrift, Route, Raster und Datenquelle bezeichnen das Profil eindeutig.

## Signage

| Fläche | Raster | Mindestauflösung | Scrollen |
|---|---|---:|:---:|
| Cafeteria Tag | 2 Karten | 1920 × 1080 | Nein |
| Cafeteria Woche | 5 Tage × 2 Menüarten | 1920 × 1080 | Nein |
| Patienten Tag | 2 Mahlzeiten × 2 Menüarten | 1920 × 1080 | Nein |
| Patienten Woche | 7 Tage × 2 Mahlzeiten; je zwei Menüarten | 3840 × 2160 | Nein |

Die Patienten-Woche in 1920 × 1080 ist ausdrücklich nur eine Referenzvorschau. Player zeigen keine Navigation, Interaktion, Cookies, Login oder Profilumschalter. Kopfzeile und Statuszeile enthalten Kanal, Datum/Kalenderwoche, Revision und Aktualisierungsstatus.

## Mobile

- Tagesansicht zuerst Überschrift und Datum, danach Menü 1 und Vegetarisch.
- Patienten-Woche: pro Tag Mittag, danach Abend; in jeder Mahlzeit Menü 1, danach Vegetarisch.
- Cafeteria-Woche: pro Tag zwei Menüarten und die beiden Kostenansätze.
- Keine horizontalen Desktoptabellen auf dem Smartphone.
- Grundtext mindestens 16 CSS-px; interaktive Ziele mindestens 44 × 44 CSS-px.

## Textgrenzen

| Element | Maximum |
|---|---|
| Signage-Gerichtstitel | 36–46 Zeichen, höchstens zwei Zeilen je Fläche |
| Komponenten/Beilagen | 48–70 Zeichen, höchstens zwei Zeilen |
| Hinweise | maximal eine kurze Zeile; längere Hinweise gehören in Website/Druck |
| Kostenbezeichnung | „Mitarbeitende“ und „Externe“, nicht nur „intern/extern“ |

Die Publikationsvorschau muss Überläufe markieren. Schriftgrössen werden nicht unter die im SDD genannten Mindestwerte verkleinert.

## Prototypen

Die statischen Dateien unter `design/prototype/` sind ohne Backend lesbar und dienen als verbindliche visuelle Referenz. `tools/capture_screenshots.py` erzeugt die Bilder reproduzierbar mit Chromium. Die vollständige Liste steht in `SCREENSHOT_INDEX.md`.
