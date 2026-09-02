# Referenzscreenshots

## Primäre Screenshots

| Datei | Auflösung | Zweck |
|---|---:|---|
| `signage-cafeteria-tag-1920x1080.png` | 1920 × 1080 | Cafeteria heute, zwei Menüarten, Mitarbeitende/Externe |
| `signage-cafeteria-woche-1920x1080.png` | 1920 × 1080 | Cafeteria Mo–Fr, 5 × 2 |
| `signage-cafeteria-geschlossen-1920x1080.png` | 1920 × 1080 | Wochenende/Feiertag geschlossen |
| `signage-patienten-tag-1920x1080.png` | 1920 × 1080 | Patienten heute, Mittag und Abend, je zwei Menüarten |
| `signage-patienten-woche-1920x1080-vorschau.png` | 1920 × 1080 | reine Layoutvorschau, nicht produktiv |
| `signage-patienten-woche-3840x2160.png` | 3840 × 2160 | Patienten-Wochenplayer, Produktionsentwurf |
| `mobile-cafeteria-heute-390x844.png` | 390 × 844 | Cafeteria heute auf Smartphone |
| `mobile-cafeteria-woche-390x844.png` | 390 × 844 | Cafeteria-Woche auf Smartphone |
| `mobile-patienten-heute-390x844.png` | 390 × 844 | Patienten heute auf Smartphone |
| `mobile-patienten-woche-390x844.png` | 390 × 844 | Patienten Mo–So auf Smartphone |
| `website-cafeteria-woche-1440x1100.png` | 1440 × 1100 | Cafeteria-Website Woche |
| `website-patienten-woche-1440x1100.png` | 1440 × 1100 | Patienten-Website Woche |
| `admin-cafeteria-1440x900.png` | 1440 × 900 | Backend-Raster Cafeteria |
| `admin-patienten-1440x900.png` | 1440 × 900 | Backend-Raster Patienten |

## Kompatibilitätskopien

`signage-1920x1080.png`, `mobile-390x844.png` und `admin-1440x900.png` verweisen auf die entsprechenden Cafeteria-Ansichten des früheren Pakets.

## Live-Screenshots

Produktiv-Screenshots aus dem laufenden System in `design/screenshots/live/`:

| Datei | Auflösung | Zweck |
|---|---:|---|
| `login-1440x900.png` | 1440 × 900 | Anmeldungsseite |
| `auth-local-1440x900.png` | 1440 × 900 | Lokale Auth-Formular |
| `website-cafeteria-heute-1440x1100.png` | 1440 × 1100 | Cafeteria heute, live |
| `website-cafeteria-woche-1440x1100.png` | 1440 × 1100 | Cafeteria Woche, live |
| `website-patienten-heute-1440x1100.png` | 1440 × 1100 | Patienten heute, live |
| `website-patienten-woche-1440x1100.png` | 1440 × 1100 | Patienten Woche, live |
| `mobile-cafeteria-heute-390x844.png` | 390 × 844 | Cafeteria Mobil heute, live |
| `mobile-cafeteria-woche-390x844.png` | 390 × 844 | Cafeteria Mobil Woche, live |
| `mobile-patienten-heute-390x844.png` | 390 × 844 | Patienten Mobil heute, live |
| `mobile-patienten-woche-390x844.png` | 390 × 844 | Patienten Mobil Woche, live |
| `admin-cafeteria-1440x900.png` | 1440 × 900 | Admin Cafeteria, live |
| `admin-patienten-1440x900.png` | 1440 × 900 | Admin Patienten, live |
| `signage-cafeteria-tag-1920x1080.png` | 1920 × 1080 | Signage Cafeteria Tag, live |
| `signage-cafeteria-woche-1920x1080.png` | 1920 × 1080 | Signage Cafeteria Woche, live |
| `signage-cafeteria-geschlossen-1920x1080.png` | 1920 × 1080 | Signage Cafeteria geschlossen, live |
| `signage-patienten-tag-1920x1080.png` | 1920 × 1080 | Signage Patienten Tag, live |
| `signage-patienten-woche-1920x1080-vorschau.png` | 1920 × 1080 | Signage Patienten Woche Vorschau, live |
| `signage-patienten-woche-3840x2160.png` | 3840 × 2160 | Signage Patienten Woche 4K, live |

Mit `INDEX.json` zur Inventarverwaltung.

### Screenshot-Erfassung

Live-Screenshots werden mit dem Capture-Tool erfasst:

```bash
python tools/capture_live_screenshots.py \
  --base-url https://dishboard.joelduss.xyz \
  --username <admin-username> \
  --password-file <0400-datei>
```

Für eine Geschlossenen-Tag-Variante (z. B. Wochenende):

```bash
python tools/capture_live_screenshots.py \
  --base-url https://dishboard.joelduss.xyz \
  --username <admin-username> \
  --password-file <0400-datei> \
  --select signage-cafeteria-geschlossen-1920x1080.png \
  --closed-today
```

Das Tool meldet Browserfehler, Netzwerkfehler und leere Ansichten als Fehler.
