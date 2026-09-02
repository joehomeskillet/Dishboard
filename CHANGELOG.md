# Änderungsprotokoll

## Welle 3: Finalisierung vom 2. September 2026

### Authentifizierung und Benutzer-Management

- Lokale Anmeldung aktiviert: `/auth/login` leitet auf `/auth/local` um; Logout erfordert POST mit CSRF-Token.
- Login-Rate-Limits in Redis pro normalisiertem Benutzernamen und vertrauenswürdiger Client-IP.
- Session-Regeneration nach erfolgreichem Login.
- Client-Adresse wird aus dem rechtesten nicht vertrauenswürdigen Hop von `X-Forwarded-For` aufgelöst (XFF-Hardening).

### Erst-Administrator-Bootstrap

- Migration `database/migrations/0009_bootstrap_first_local_admin.sql` etabliert fail-closed Bootstrap-Logik.
- Befehl `python manage.py bootstrap-local-admin --username X --display-name Y` fragt Passwort zweimal ab oder liest aus `DISHBOARD_BOOTSTRAP_PASSWORD_FILE` (Modus 0400).
- Bootstrap ist nur möglich, wenn kein aktiver Administrator (lokal oder Entra) existiert; danach sperrt sich die Funktion.
- Weitere Benutzer werden von verifizierten Administratoren via `provision-local-user --actor <admin-uuid>` provisioniert.

### Deployment und Infrastruktur

- **Host-Caddy-Modus**: Caddy auf dem Docker-Host proxied ausschliesslich auf `127.0.0.1:8789` (keine Compose-interne Caddy).
- Secrets-Verzeichnis `deployment/secrets/` mit Modus 0700; Secret-Dateien 0444 pro Service als Bind-Mount.
- Compose-Netzwerk `10.213.0.0/24` reserviert ausserhalb Docker-Defaults (172.16.0.0/12, 192.168.0.0/16).
- Redis läuft als UID 999:GID 1000.
- App-Image ID fixiert: `APP_IMAGE` auf unveränderliche SHA-256-Hash setzen (kein Tag, kein Registry-Digest).
- Redeploy-Ablauf: `docker build --iidfile /tmp/dishboard-image-id --file Dockerfile ..`, dann `APP_IMAGE` aus der IID-Datei setzen, `docker compose up -d --pull never --no-build`.
- CSV-Validator unter `/app/csv/validate_menu_csv.py` im Docker-Image verpackt.

### Benutzeroberfläche und Design

- Moderne Login-Seite im Therapieplan-Stil: zentrierte Karte, Therapieplan-Magenta-Button mit Teal-Hover, Fehler inline statt Redirect, Benutzername erhalten bei Fehler.
- Therapieplan-Designtokens (`--sh-*`) für konsistente Farben und Typografie.
- Fira Sans selbstgehostet über `woff2`-Schriften.
- Preiszeilen auf gleicher Höhe als Karten-Basiszeile via Flexbox (`.price-row`).
- White Header mit verbessertem Kontrast pro Reference-Design.

### In-Arbeit (Branches für Welle 3+)

**design/header-brand:**
- Südhang-Logo oben rechts im Header.
- Kanalnavigation (Patienten/Cafeteria) oben links.
- Beilagen-Pills gleich hoch und in Menüart-Farbe gerenderrt.
- Patienten-Wochenansicht: Datumsbereich (z. B. „Montag 31. Aug – Sonntag 6. Sept") als Seitentitel.

**feat/labels-allergens:**
- Labels-Feld für Gerichte (z. B. Regional, Bio, Vegetarisch).
- Allergene-Felder: „enthält" und „Spuren" als Multi-Select.
- Herkunft `Zutat=CH|EU|…` pro Gericht.
- Review-Status `not_checked`/`checked` für jedes Allergen/Label pro Item.
- Publikation erfordert, dass alle offenen Allergen-Optionen auf `checked` gesetzt sind (Review-Gate).
- Rendering als Pills in Web-Ansichten, Signage, Druck und API.
- Admin-Formular mit Checkboxen für Review-Status und Multi-Select für Allergen-/Label-Kategorien.

---

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
- Restore-Skript: Kandidaten-Datenbank, Lease-Akquisa, Lifecycle-Atomarität, explizite Recovery nach Host-Crash.

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
