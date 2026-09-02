# Änderungsprotokoll

## Finalisierung vom 2. September 2026

### Datenbank und Migrations

- Schema-Version auf 12 erhöht (von 11).
- Migrationen um 0009_bootstrap_first_local_admin.sql erweitert.
- Lokales Auth-Bootstrap mit einmaligem `bootstrap-local-admin`-Befehl und nachfolgender `provision-local-user`.
- Tabellenzahl auf 28 erhöht (Audit-Events, Capability-Verwaltung, lokale Credentials).

### Authentifizierung und Bootstrap

- Lokale Benutzer-Bootstrap: `python manage.py bootstrap-local-admin --username X --display-name Y` auf der Migrate-Verbindung (Owner-Rolle).
- Weitere Benutzer über verifizierte Administratoren: `provision-local-user --actor <bootstrap-admin-username>`.
- Auth-Issuer-Rolle mit restriktiven Ausführungsrechten auf schmale Provisioning-Funktionen.
- Passwortbefehle fragen interaktiv oder lesen aus `DISHBOARD_BOOTSTRAP_PASSWORD_FILE` (Mode 0400).

### Kitchen Workflows und Publikation

- Menü-Import mit Preview-Ansicht (`/admin/import-preview`).
- Publikation und Rückzug mit profilbezogenen Capabilities.
- Publish-Withdraw-Fähigkeiten für `Cafeteria.Publisher` aktiviert.
- CSV-Validator verpackt unter `/app/csv/validate_menu_csv.py` im Docker-Image.

### Öffentliche API und Signage

- Strikte Isolierung: öffentliche Signage- und API-Routen lehnen Query-Parameter ab.
- Bei Datenbankfehlern wird die zuletzt gespeicherte gültige Revision desselben Profils angezeigt (Last-Good-Snapshots).
- Vier Player (`/signage/cafeteria/tag`, `/signage/cafeteria/woche`, `/signage/patienten/tag`, `/signage/patienten/woche`) mit festen Auflösungen.

### Deployment-Hardening

- Interne App-Port: 8789 (nicht 8080).
- App läuft als UID 10001 (nicht root).
- Netzwerk: reserviertes 10.213.0.0/24-Subnetz (ausserhalb Docker-Defaults 172.16.0.0/12 und 192.168.0.0/16).
- Secrets als 0700-root-Verzeichnis mit 0444-Dateien pro Service.
- Redis läuft als UID 999:GID 1000.
- Healthchecks über Shell-Ausführung ohne Secrets als CLI-Argumente.
- Secrets-Verzeichnis: deployment/secrets/ (nicht in .env, nicht in Git).
- Image-ID fixiert: APP_IMAGE=sha256:<64hex> (kein Registry-Digest, kein Tag).
- Bootstrap-Phase erzwingt APP_ENV=migration mit nur PostgreSQL-Secrets.
- Docker Compose `--pull never` und `--no-build` in Produktion (nur lokal gebautes Image).

### Datenbankrechte und Publikations-Capabilities

- `cafeteria_app` erhält EXECUTE auf Validator-Funktionen für sichere Publikation.
- Capability-Secrets und Replay-Nonces explizit aus Backups ausgeschlossen (`--exclude-table` in pg_dump).
- Restore-Reihenfolge: Migration → permissions.sql → ensure_auth_capability_state() → hard_reset_auth_capability_state().
- Active-Publications zeigt nur nicht zurückgezogene, veröffentlichte Revisionen.

### QA und Nachweise

- Live-Screenshots: 18 Dateien in design/screenshots/live/ mit INDEX.json.
- Screenshot-Capture-Tool: `python tools/capture_live_screenshots.py --base-url https://dishboard.joelduss.xyz --username <admin> --password-file <0400 file>`.
- Compose-Probe: Start mit lokalem Image-ID, Healthcheck-Validation.
- Restore-Drill: Dump, Hash, separate Testkandidaten-Datenbank, Punktwiederherstellung, Owner-Watchdog.
- Integrierte Vollsuite: 2199 passed, 14 skipped (Restore-Drills separat mit RUN_LIVE_RESTORE_DRILL=1).

### Betriebskonzept

- Lokale Demo-Werte: DEMO_MODE=true, SEED_DEMO=true, APP_ENV=development, DEMO_TODAY=2026-09-01.
- Produktion lehnt Demo-Konfiguration ab und verlangt: APP_ENV=production, reale Entra-Credentials (falls ENTRA_ENABLED=true), sichere Cookies, valide Ursprungs-URLs.
- Backup-Skript: pg_dump mit Secret-Ausschlusstabellen, SHA-256-Validierung, automatische Rotation.
- Restore-Skript: Kandidaten-Datenbank, Lease-Akquise, Lifecycle-Atomarität, explizite Recovery nach Host-Crash.

### Dokumentation

- SDD-Abschnitte aktualisiert: Authentifizierung, Deployment, Datenmodell, Operationen, Backlog.
- GROK_KRITIK_UMSETZUNG: Abschluss mit Live-Test-Nachweis und Wochenentwurf.
- VALIDATION.md: Evidenztabelle für Release-Lauf-Integration (Kombinierte Suite, Drills, Compose, Validator, Deploy, ZIP).
- Screenshot-Index mit Live-Satz (18 Dateien) und Capture-Kommando.
- ENTRA_SSO_BETRIEBSKONZEPT: Koexistenz von lokal und Entra, Bootstrap, Abnahmetestvorgaben.
- ABNAHME_CHECKLISTE: Fachmodell, Website/Mobile, Signage, Datenbank, Sicherheit und Betrieb.
- DOCKER_COMPOSE_RUNBOOK: Health-Check auf 8789, Image-ID-Format, Restore-Reihenfolge mit Capability-State.

## Rework vom 1. September 2026

### Fachmodell

- Zwei getrennte Profile eingeführt: `patient` und `staff_guest`.
- Patientenplan auf Montag bis Sonntag, Mittag und Abend erweitert.
- Zwei feste Menüarten für jeden offenen Service: Menü 1 und Vegetarisch.
- Cafeteria auf Montag bis Freitag und Mittag begrenzt.
- Kosten in eigene Tabelle verschoben; Patientenpreise werden durch Datenbankregeln verhindert.
- Schliessungen auf Profil × Datum × Mahlzeit verfeinert.
- Publikationsrevisionen und letzte gültige Playerkopien profilbezogen getrennt.

### Oberflächen und Signage

- Vier feste Player-Routen und getrennte Templates ergänzt.
- Cafeteria-Wochenplayer mit 5 × 2 Menükarten erstellt.
- Patienten-Tagesplayer mit Mittag und Abend erstellt.
- Patienten-Wochenplayer als 4K-Layout erstellt; 1080p nur Vorschau.
- Cafeteria-Geschlossenfläche für Wochenende/Feiertage ergänzt.
- Mobile Tages- und Wochenansichten für beide Profile ergänzt.
- Zwei getrennte Backend-Raster als Prototypen ergänzt.
- Insgesamt 14 primäre Referenzscreenshots erzeugt.

### Daten, CSV und Tests

- Zwei Demo-Snapshots derselben Kalenderwoche erzeugt.
- Getrennte Patienten- und Cafeteria-CSV-Vorlagen samt Beispielen erstellt.
- Vertragsprüfungen für Profilisolation, Kostenverbot, vier Routen und Template-Syntax ergänzt.
- Paketvalidator auf die neue Struktur umgestellt.

### Sicherheit und Betrieb

- Öffentliche Datums- und Profilparameter entfernt beziehungsweise abgewiesen.
- Demo-Konfiguration in Produktion technisch blockiert.
- Demo-Benutzer auf Editor/Publisher begrenzt.
- Rollenmodell von fünf auf drei verständliche Rollen reduziert.
- Alembic-Behauptung entfernt; SQL-Baseline klar benannt.
- Redis-Healthcheck liest das Secret ohne Passwort im Healthcheck-Kommando.

### Dokumentation

- SDD vollständig auf zwei Publikationskanäle umgebaut.
- Umsetzung der Grok-Kritik und offene Live-Nachweise separat dokumentiert.
- Abnahmecheckliste, CSV-, Entra-, Design- und Betriebsdokumentation aktualisiert.
