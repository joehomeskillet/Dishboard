# Menüplanung Klinik Südhang – Patienten und Cafeteria

**Status:** Entwurf, intern technisch geprüft; nicht fachlich abgenommen.  
**Stand:** 1. September 2026.

Das Paket modelliert zwei getrennte Publikationskanäle:

| Kanal | Zeitraum und Mahlzeiten | Menüarten | Kosten |
|---|---|---|---|
| Patienten | Montag bis Sonntag, Mittag und Abend | Menü 1 und Vegetarisch | keine Kosteninformation im Kanal |
| Cafeteria | Montag bis Freitag, nur Mittag | Menü 1 und Vegetarisch | Mitarbeitende und Externe |

## Wichtigste Inhalte

| Pfad | Inhalt |
|---|---|
| `docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.md/.docx` | korrigiertes SDD mit Produktregeln, Informationsarchitektur, Fit-Regeln und Backlog |
| `docs/GROK_KRITIK_UMSETZUNG.md` | Punkt-für-Punkt-Umsetzung und verbleibende Nachweise |
| `review/Grok_Kritik_original.txt` | unveränderte Reviewgrundlage |
| `database/` | PostgreSQL-Schema, SQL-Baseline, Seeds, Rechte und statischer Validator |
| `demo/snapshots/` | getrennte publizierte Demo-Revisionen für dieselbe Kalenderwoche |
| `csv/` | je eine Vorlage und ein Beispiel für Patienten und Cafeteria, plus Validator |
| `reference_scaffold/` | Flask-Referenzgerüst mit Website, Druck, API, Backend-Prototypen und vier Signage-Routen |
| `design/prototype/` | elf eigenständige HTML-Prototypen plus Kompatibilitätskopien |
| `design/screenshots/` | 14 primäre Screenshots plus drei Kompatibilitätskopien |
| `architecture/` | System-, Daten-, Auth- und CSV-Fluss als DOT, PNG und SVG |
| `deployment/` | Docker Compose, Secrets, Backup/Restore, Healthchecks und Runbook |
| `entra/` | drei App-Rollen, Gruppenbeispiel und PowerShell-Bereitstellung |

## Feste URLs

| Zweck | Route |
|---|---|
| Patienten heute / Woche | `/patienten/heute/` · `/patienten/wochenplan/` |
| Cafeteria heute / Woche | `/cafeteria/heute/` · `/cafeteria/wochenangebot/` |
| Patienten Druck | `/druck/patienten/woche` |
| Cafeteria Druck | `/druck/cafeteria/woche` |
| Signage Cafeteria Tag / Woche | `/signage/cafeteria/tag` · `/signage/cafeteria/woche` |
| Signage Patienten Tag / Woche | `/signage/patienten/tag` · `/signage/patienten/woche` |
| Veröffentlichte API | `/api/v1/published/cafeteria` · `/api/v1/published/patienten` |

Öffentliche Player- und API-Routen akzeptieren keine Query-Parameter. Der Patienten-Wochenplayer ist für 3840 × 2160 festgelegt; die 1920 × 1080-Datei ist nur eine Vorschau.

## Offline prüfen

```bash
python database/validate_schema.py
python csv/validate_menu_csv.py csv/menu_patient_example.csv --json
python csv/validate_menu_csv.py csv/menu_cafeteria_example.csv --json
python deployment/validate_compose.py
pytest -q reference_scaffold/tests
python tools/validate_package.py
```

## Artefakte neu erzeugen

```bash
python tools/capture_screenshots.py
python tools/build_sdd_docx.py
python tools/build_manifest.py
python tools/build_manifest.py --verify
```

Für einen abweichenden Browserpfad akzeptiert das Screenshot-Skript `--browser-path /pfad/zu/chromium`.

## Demo mit Docker Compose

```bash
cd deployment
./bootstrap.sh
cp .env.example .env
# Nur für die lokale Demo: DEMO_MODE=true und SEED_DEMO=true.
docker compose config
docker compose up --build -d
docker compose ps
```

Die Lieferung ist kein Produktionsfreigabebeleg. Live-PostgreSQL, vollständige CRUD-/Publish-Oberfläche, Entra, Backup/Restore, 4K-Player und fachliche Abnahme bleiben zwingende nächste Nachweise.
