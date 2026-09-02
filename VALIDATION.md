# Validierungsbericht

**Stand:** 2. September 2026  
**Paket:** Menüplanung Klinik Südhang – getrennte Patienten- und Cafeteria-Publikation  
**Status:** Entwurf, intern technisch geprüft; nicht fachlich abgenommen  
**Erstellungsumgebung:** Python 3.13.5, Graphviz 2.42.4, Pandoc 3.1.11.1, LibreOffice 25.2.3.2

## Erfolgreich offline geprüft

| Bereich | Prüfergebnis |
|---|---|
| Produktvertrag | Zwei getrennte Profile: `patient` und `staff_guest`; vier feste Signage-Routen; keine öffentliche Datumssteuerung |
| Patientenplan | Montag bis Sonntag, Mittag und Abend, je Menü 1 und Vegetarisch; 14 Mahlzeiten und 28 Menüoptionen in der Demo-Woche |
| Kostenverbot Patienten | Keine Kostenfelder in Patienten-Snapshot, Patienten-CSV, Patienten-Prototypen oder Patienten-Jinja-Templates |
| Cafeteriaplan | Montag bis Freitag, nur Mittag, je Menü 1 und Vegetarisch; 5 Mahlzeiten und 10 Menüoptionen mit Mitarbeitenden- und Externenpreis |
| PostgreSQL-Schema | Statische Vertragsprüfung erfolgreich: 28 Tabellen, 2 Angebotsprofile, 3 App-Rollen und 14 Allergengruppen |
| Schema-Version | 12 mit Migrationen 0001–0009 |
| SQL-Baseline | `database/schema.sql` und `database/migrations/0001_initial_postgresql.sql` sind byteidentisch |
| DB-Regeln | Prüf-Funktionen für Profil/Mahlzeit/Wochentag, Preise, Publikationsrevision, verbotene Patienten-Kostenschlüssel und lokales Auth-Bootstrap statisch vorhanden |
| Publikation | Getrennte Demo-Snapshots und Revisions-IDs pro Profil; Tag und Woche eines Profils lesen dieselbe Revision |
| CSV Patienten | 17 Spalten, 28 gültige Datenzeilen, keine Kostenfelder; Validator ohne Fehler und Warnungen |
| CSV Cafeteria | 19 Spalten, 10 gültige Datenzeilen, zwei Kostenfelder; Validator ohne Fehler und Warnungen |
| Integrationstests | `2199 passed, 14 skipped` auf der Integration-Line; die 14 übersprungenen Tests sind Restore-Drills (separat mit `RUN_LIVE_RESTORE_DRILL=1` bestätigt) |
| Jinja/HTML | Alle gelieferten Jinja-Templates syntaktisch geparst; getrennte Patienten- und Cafeteria-Templates geprüft |
| Compose | Dienste, Secrets, Healthchecks und Startabhängigkeiten statisch geprüft; kein Container gestartet |
| Redis-Secret | Healthcheck verwendet eine gemountete Scriptdatei; kein Passwort über `redis-cli -a` in der Compose-Datei |
| Entra-Rollen | `Cafeteria.Editor`, `Cafeteria.Publisher`, `Cafeteria.Admin` konsistent in Manifest, Mapping, Code und SDD |
| Shell/Python | 6 Shell-Skripte bestehen `sh -n`; 34 Python-Dateien syntaktisch geprüft |
| JSON/YAML | Gelieferte JSON- und YAML-Dateien erfolgreich geparst |
| Prototypen | 14 HTML-Dateien: eigenständige Mobile-, Website-, Backend- und Player-Ansichten sowie Kompatibilitätsseiten |
| Design-Screenshots | 14 primäre Referenzscreenshots plus 3 Kompatibilitätskopien in `design/screenshots/`; Abmessungen und nichtleerer Bildinhalt geprüft |
| Live-Screenshots | 18 Screenshot-Dateien in `design/screenshots/live/` mit Index; erstellt von der LAUFENDEN Anwendung |
| Player-Auflösungen | Cafeteria Tag/Woche, geschlossen und Patienten Tag in 1920 × 1080; Patienten-Woche zusätzlich in 3840 × 2160 |
| Word-SDD | 27 Seiten gerendert und visuell auf Überlagerungen, abgeschnittene Tabellen, Grafiken sowie Kopf-/Fusszeilen geprüft |
| DOCX-Barrierefreiheit | Audit: 0 hohe, 0 mittlere und 0 niedrige Befunde |
| Diagramme | Systemarchitektur, ERD, Authentisierung und CSV-Fluss jeweils als DOT, PNG und SVG vorhanden |

## Evidenz über die Testsuiten

| Testtyp | Ergebnis | Notizen |
|---|---|---|
| Kombinierte Vollsuite (Integration) | 2199 passed, 14 skipped | Integration-Line 2026-09-02; 14 Skips sind Restore-Drill |
| Restore-Drill | wird beim Release-Lauf eingetragen | RUN_LIVE_RESTORE_DRILL=1 mit PostgreSQL 18.6 + Redis |
| Compose-Probe | wird beim Release-Lauf eingetragen | RUN_LIVE_COMPOSE_PROBE=1; Image-ID, Start, Healthchecks |
| Paketvalidator (Live-Gate) | wird beim Release-Lauf eingetragen | Tools und Screenshot-Inventar |
| Deploy-Probes dishboard.joelduss.xyz | wird beim Release-Lauf eingetragen | Health-Checks und vier Player |
| ZIP SHA-256 | wird beim Release-Lauf eingetragen | Reproduzierbare Paket-Identität |

## Nicht als live getestet oder abgenommen ausgeben

| Offener Nachweis | Erforderliche Prüfung |
|---|---|
| PostgreSQL-Ausführung | Schema und Trigger gegen eine isolierte PostgreSQL 18.6-Instanz ausführen; Negativfälle `patient+Preis`, `staff_guest+DINNER` und `staff_guest+Sa/So` verifizieren |
| Docker Compose | `docker compose config`, Image-Build, Migration, Containerstart, Healthchecks und Logs auf dem Zielhost prüfen |
| Backup und Restore | Restore-Drill mit `RUN_LIVE_RESTORE_DRILL=1` bestätigt; echter Produktions-Restore auf separater Infrastruktur noch offen |
| Microsoft Entra ID | App-Rollen und Gruppenzuweisungen zuerst mit `-WhatIf`, danach mit Testkonten im Südhang-Tenant prüfen; Live-Login noch nicht getestet |
| PowerShell-Skript | `entra/configure-entra-app.ps1` unter PowerShell 7.2 oder neuer ausführen und Resultat protokollieren |
| Vollständige Bedienoberfläche | Das Gerüst enthält Referenzrouten und Backend-Raster, aber noch keinen vollständig umgesetzten CRUD-/Prüf-/Publikationsworkflow |
| Reale Digital-Signage-Player | Yodeck-/Browser-Player mit 16:9, Refresh, Offline-/Last-good-Verhalten und Wochenwechsel testen |
| Patienten-Woche in 4K | Lesbarkeit aus realem Betrachtungsabstand mit Pflege/Hotellerie prüfen; 3840×2160-Datei vorhanden, Sichtprüfung am Gerät offen |
| Fachliche Abnahme | Küche, Hotellerie, Pflege, Kommunikation, Datenschutz und Betrieb müssen Inhalte, Begriffe, Kosten, Allergene und Schliessungsfälle abnehmen |

## Reproduzierbare Offline-Prüfung

```bash
cd Klinik_Suedhang_Cafeteria_Rework
export PYTHONDONTWRITEBYTECODE=1

python database/validate_schema.py
python csv/validate_menu_csv.py csv/menu_patient_example.csv --json
python csv/validate_menu_csv.py csv/menu_cafeteria_example.csv --json
python deployment/validate_compose.py
python -m pytest -q -rs -p no:cacheprovider reference_scaffold/tests
python tools/validate_package.py
python tools/build_manifest.py
python tools/build_manifest.py --verify
find deployment -type f -name '*.sh' -print0 | xargs -0 -n1 sh -n
```

## Zusätzliche DB-Prüfung auf einer isolierten PostgreSQL-Instanz

```bash
export TEST_DATABASE_URL='postgresql+psycopg://cafeteria_test:PASSWORT@127.0.0.1:5432/cafeteria_test'
python -m pytest -q -rs -p no:cacheprovider reference_scaffold/tests
```

Die angegebene Testdatenbank muss ausschliesslich für automatisierte Tests bestimmt sein und darf keine produktiven Daten enthalten.

## Prüfung auf dem Docker-Zielhost

```bash
cd Klinik_Suedhang_Cafeteria_Rework/deployment
./bootstrap.sh
cp .env.example .env
# Werte und Secret-Dateien setzen; Demo nur ausserhalb Produktion aktivieren.

docker compose config
docker compose up --build -d
docker compose ps
docker compose logs --tail=200 migrate app db redis

docker compose run --rm app python /app/manage.py validate-db --wait-seconds 30
curl --fail http://127.0.0.1:8789/health/live
curl --fail http://127.0.0.1:8789/health/ready
```

`VALIDATION.md` dokumentiert Artefakt- und Offline-Vertragsprüfungen. Es ist weder Produktionsfreigabe noch fachliche Abnahme.
