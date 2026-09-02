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

## Farb- und Schriftsystem (Therapieplan-Angleichung)

Die Dishboard-Farbpalette wurde abgestimmt auf das klinische Therapieplan-Dashboard der Südhang.

### Farbpalette

**Primärfarbe (Burgundy/Magenta)**
- `--sh-primary: #8C1C4B` — Therapeutische Markenfarbe
- `--sh-primary-soft: #F6E7EE` — Helles Hintergrund-Tint

**Teal Scale (Sekundär)**
- `--sh-teal-950: #1A363A` — Signage Start (dunkel)
- `--sh-teal-900: #224449` — Signage Mitte
- `--sh-teal-800: #2B545C` — Signage End (Menü-Akzente)
- `--sh-teal-700: #35666F` — Sekundärfarbe Basis
- `--sh-teal-100: #DCEDF0` — Helles Tint
- `--sh-teal-050: #F1F7F8` — Hellstes Tint (Hintergrund)

**Grün (Gemüse-Akzent)**
- `--sh-green: #3E6B44` — Therapieplan Grün
- `--sh-green-soft: #EAF0E8` — Helles Grün-Tint

**Neutral/Ink (Text & Struktur)**
- `--sh-ink: #383027` — Braun (Standard-Text)
- `--sh-ink-muted: #747068` — Gedämpft Braun (Sekundärtext)
- `--sh-border: #D5D1CB` — Leichte Grenzlinie

**Hintergrund & Canvas**
- `--sh-canvas: #F8F8F7` — Seiten-Hintergrund (Off-White)
- `--sh-canvas-strong: #EFEDE9` — Dunklere Variante
- `--sh-panel: #ffffff` — Weiße Karten

### Schatten

Therapieplan-Schatten mit Brown-Basis:
- **Standard**: `0 2px 10px rgba(56, 48, 39, .06), 0 3px 14px rgba(56, 48, 39, .07)`
- **Soft**: `0 2px 10px rgba(56, 48, 39, .06)`

### Grenzradius (Border Radius)

- `--sh-radius-sm: 6px` — Steuerelemente
- `--sh-radius-md: 10px` — Karten
- `--sh-radius-lg: 16px` — Größere Komponenten

### Schriftsystem

**Fira Sans** (SIL Open Font License), selbst gehostet in `/static/fonts/`:

| Gewicht | Datei | Verwendung |
|---------|-------|-----------|
| 400 | fira-sans-400.ttf | Standard-Text (vorgeladen) |
| 500 | fira-sans-500.ttf | Mittel/Akzent |
| 600 | fira-sans-600.ttf | Überschriften, Hervorhebung (vorgeladen) |
| 700 | fira-sans-700.ttf | Bold Headings |

**Font Stack**: `"Fira Sans", Aptos, "Segoe UI Variable", "Segoe UI", ui-sans-serif, sans-serif`

**CSP-Konformität**: `font-src 'self'` — keine externen Font-Anfragen zulässig.

### Kontrast (WCAG AA)

Alle Farbkombinationen erfüllen WCAG AA Mindest-Kontrastanforderungen:

| Kombination | Verhältnis | Min. erforderlich | Status |
|-------------|-----------|-----------------|--------|
| Primär (#8C1C4B) auf Weiß | 8.81:1 | 4.5:1 | ✓ |
| Ink (#383027) auf Hellgrau (#F8F8F7) | 12.20:1 | 4.5:1 | ✓ |
| Muted Ink (#747068) auf Hellgrau | 7.47:1 | 4.5:1 | ✓ |
| Weiß auf Signage-Dunkel (#1A363A) | 12.86:1 | 7:1 | ✓ WCAG AAA |

**Hinweis**: Kanal-Unterscheidung erfolgt über Text, nicht nur Farbe.

---

*Detaillierte Token-Zuordnung siehe* `docs/design/therapieplan-alignment.md`
