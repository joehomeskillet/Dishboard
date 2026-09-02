# Docker-Compose-Runbook

## Services

| Service | Aufgabe |
|---|---|
| `db` | PostgreSQL, Fachconstraints und persistente Daten |
| `redis` | Serverseitige Sessions |
| `migrate` | SQL-Baseline, Stammdaten und Rollenrechte |
| `app` | Flask/Gunicorn |
| `backup` | periodischer `pg_dump` |
| `restore` | manueller Restore im Profil `ops` |
| `caddy` | optionales TLS-Overlay |

## Lokale Demo

```bash
cd deployment
./bootstrap.sh
docker compose config
docker compose build app migrate
docker compose up -d
docker compose ps
```

Die mit `bootstrap.sh` erzeugte `.env` ist produktionssicher. Für eine lokale Demo darin bewusst `APP_IMAGE=suedhang-cafeteria:local`, `APP_ENV=development`, `APP_PUBLIC_BASE_URL=http://localhost:8080`, `DEMO_MODE=true`, `SEED_DEMO=true`, `DEMO_TODAY=2026-09-01` und `SESSION_COOKIE_SECURE=false` setzen. Öffentliche URLs besitzen trotzdem keinen Datumsparameter.

## Produktionswerte

```dotenv
APP_ENV=production
APP_IMAGE=registry.example.invalid/dishboard@sha256:<64-hex-image-digest>
DEMO_MODE=false
SEED_DEMO=false
DEMO_TODAY=
APP_PUBLIC_BASE_URL=https://dishboard.joelduss.xyz
CAFETERIA_DOMAIN=dishboard.joelduss.xyz
SESSION_COOKIE_SECURE=true
POSTGRES_SSLMODE=prefer
```

Tenant-ID, Client-ID und Secrets müssen real gesetzt sein. Secrets liegen unter `deployment/secrets/` und nicht in `.env`. Der Redis-Healthcheck ruft ein Skript auf; das Passwort steht nicht im Healthcheck-Kommando.
Das Verzeichnis `secrets/` gehört root mit Modus 0700; die Secret-Dateien sind 0444 und werden pro Service als Bind-Mount eingebunden. App und Migrate laufen als UID 10001, Redis als 999:1000; Healthchecks werden über `sh` aufgerufen.

Der App-Entrypoint akzeptiert in Produktion nur den exakten Ursprung `https://dishboard.joelduss.xyz` (ohne Port, Pfad, Query, Fragment oder Userinfo), die exakte Domain und ein per `@sha256:` fixiertes `APP_IMAGE`. Unsichere Session-Cookies und bekannte Entra-Platzhalter werden ebenfalls abgelehnt. `migrate` überschreibt die Laufzeitwerte mit `APP_ENV=migration`, ausgeschaltetem Demo-/Entra-Modus und erhält nur PostgreSQL-Secrets; Flask-, Redis- und Entra-Secrets werden dort nicht benötigt.

## Startprüfung

```bash
docker compose -f docker-compose.yml -f docker-compose.caddy.yml config
docker compose -f docker-compose.yml -f docker-compose.caddy.yml pull app migrate
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d
docker compose -f docker-compose.yml -f docker-compose.caddy.yml ps
docker compose -f docker-compose.yml -f docker-compose.caddy.yml logs --tail=200 migrate app db redis caddy

docker compose -f docker-compose.yml -f docker-compose.caddy.yml run --rm app python /app/manage.py validate-db --wait-seconds 30
curl --fail https://dishboard.joelduss.xyz/health/live
curl --fail https://dishboard.joelduss.xyz/health/ready
```

Zusätzlich sind alle vier Player sowie beide API-Snapshots aufzurufen. Die Header `X-Snapshot-Revision` von Tag und Woche desselben Profils müssen übereinstimmen.

## Backup

```bash
./backup.sh
```

Das Backup erhält SHA-256-Datei und JSON-Manifest. Mindestens eine Kopie wird ausserhalb des Docker-Hosts abgelegt.

## Restore

```bash
./restore.sh /absoluter/pfad/cafeteria-YYYYMMDDTHHMMSSZ.dump
```

Die gleichnamige `.dump.sha256` ist verpflichtend. Das Skript prüft Hash und Archivliste vor jeder Lifecycle-Mutation und erwirbt danach eine PostgreSQL-weite Lease in der Kontroll-Datenbank `postgres`. Ein langlebiger Shared-Advisory-Lock gehört genau einem Backend; ein Controller-Watchdog beweist Backend-Identität, Lock und Heartbeat vor jedem destruktiven Schritt. Stirbt Holder oder Controller, werden `app` und `backup` gestoppt und der Lauf bricht geschlossen ab. Owner- und Ressourcen-Token, Ablaufzeit und jeder Promotion-Zustand werden in `menuplan_restore_control` persistiert und in `menuplan_restore_audit` protokolliert. Jeder Lauf verwendet eindeutige Kandidat-, Rollback- und Fehlerdatenbanken mit tokengebundenen Eigentumsmarkern; vorhandene oder fremde Namen werden weder beendet noch umbenannt oder gelöscht. Der Kandidat entsteht aus `template0`, installiert und prüft deshalb `pgcrypto` inklusive `public.digest()` vor Migration und Datenbankvalidator.

Capability-Secret- und Replay-Nonce-Tabellen samt Sequenz werden wegen der bewusst entzogenen Backup-Leserechte vollständig vom Dump ausgeschlossen. Die feste Reihenfolge ist: Migration inklusive erster `permissions.sql`-Anwendung (schliesst die durch `--no-privileges` entstandenen PUBLIC-EXECUTE-Rechte), Owner-Aufruf von `cafeteria.ensure_auth_capability_state()`, erneute Migration/Permissions-Anwendung, Owner-Aufruf von `cafeteria.hard_reset_auth_capability_state()`, Datenbankvalidator, erst danach Writer. Beide Funktionen müssen exakt `1` liefern. Das Skript beweist anschliessend genau ein frisches aktives Secret und null Nonces. Dieselbe Kette läuft nach alter oder Candidate-Recovery sowie beim Wiederaufnehmen eines bereits `complete` markierten Laufs gegen die gewählte Produktionsdatenbank. Fehlt ein DB-Vertrag oder ACL-Beweis, bleiben `app` und `backup` gestoppt; alte und bereits konsumierte Tokens erhalten keine Grace Period.

Erst danach stoppt das Skript `app` und `backup`, tauscht die Datenbanknamen über die Kontroll-Datenbank `postgres` und validiert erneut. `writer_release_committed` ist der dauerhaft protokollierte Point of no return: davor stellt Recovery ausschliesslich den verifizierten alten Stand wieder her; danach behält und finalisiert sie zwingend den Kandidaten, damit bereits angenommene Writes nie durch automatisches Zurückschalten verloren gehen. `app` startet erst nach diesem Zustand. Erst nach App-Healthcheck wird `complete` persistiert; erst danach startet `backup`. Bei unbekanntem Zustand bleiben beide Dienste gestoppt.

Nach einem Host-Crash läuft die Lease aus, ein normaler Restore bleibt aber absichtlich gesperrt. Die explizite Recovery rotiert den Owner-Token, protokolliert `lease_expired_takeover`, stoppt beide Dienste und führt dieselben Beweise aus:

```bash
./restore.sh --recover
```

Nur bei Exitcode 0 sind die Dienste wieder freigegeben. Bei unbekanntem oder fremd markiertem Zustand nichts manuell umbenennen oder löschen; Audit-Tabelle und PostgreSQL-Katalog sichern und den Incident eskalieren. Anschliessend beide Snapshot-APIs, Patienten-Sonntagabend und Cafeteria-Geschlossenfläche prüfen.

Erfolgreiche Restores behalten die markierte alte Datenbank standardmässig sieben Tage (`RESTORE_ROLLBACK_RETENTION_SECONDS=604800`). Die tägliche, persistente systemd-Zeitsteuerung wird auf Hosts mit Deployment-Pfad `/opt/dishboard/deployment` einmalig installiert und geprüft:

```bash
sudo install -m 0644 systemd/dishboard-retention-prune.service /etc/systemd/system/
sudo install -m 0644 systemd/dishboard-retention-prune.timer /etc/systemd/system/
sudo systemctl daemon-reload
sudo systemctl enable --now dishboard-retention-prune.timer
systemctl list-timers dishboard-retention-prune.timer
sudo systemctl start dishboard-retention-prune.service
systemctl status dishboard-retention-prune.service
```

Der One-shot verwendet nur den bestehenden Owner-Ops-Restore-Container; der kontinuierliche Backup-Dienst erhält keine Owner-Credentials. Er löscht ausschliesslich abgelaufene, exakt tokenmarkierte Rollback-Datenbanken und schreibt `rollback_retention_pruned` ins Audit. Eine fremde oder fehlende Eigentumsmarke bricht den Lauf ab. Wiederholte Timer-Fehler sind ein Incident; nicht mit manuellen `DROP DATABASE`-Befehlen umgehen.

## Update

```bash
previous_image=$(sed -n 's/^APP_IMAGE=//p' .env)
printf '%s\n' "$previous_image" > .previous-app-image
backup_path=$(./backup.sh /srv/dishboard-backups)
printf '%s\n' "$backup_path" > .previous-database-backup

# APP_IMAGE in .env auf den neuen, unveränderlichen registry/repo@sha256:<digest> setzen.
docker compose -f docker-compose.yml -f docker-compose.caddy.yml pull app migrate
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d db redis
docker compose -f docker-compose.yml -f docker-compose.caddy.yml run --rm migrate
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d app backup caddy
docker compose -f docker-compose.yml -f docker-compose.caddy.yml ps
```

`backup.sh` legt Dump, JSON-Manifest und Checksum im absoluten Host-Verzeichnis ab; die gleichnamige `.sha256` muss beim Dump bleiben. Image-Referenz und Backup-Pfad bilden gemeinsam den Rollback-Punkt. Tags wie `local`, `latest` oder `production` sind kein Ersatz für den Digest.

Expliziter Rollback bei einer nicht rückwärtskompatiblen Datenbankänderung:

```bash
previous_image=$(cat .previous-app-image)
previous_backup=$(cat .previous-database-backup)
sed -i "s|^APP_IMAGE=.*$|APP_IMAGE=$previous_image|" .env
./restore.sh "$previous_backup"
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up -d app backup caddy
docker compose -f docker-compose.yml -f docker-compose.caddy.yml ps
```

Ist die Migration nachweislich rückwärtskompatibel, darf der `restore.sh`-Schritt entfallen; die gespeicherte Image-Referenz bleibt trotzdem Pflicht. Die mitgelieferte Migration ist eine versionierte SQL-Baseline. Das Paket behauptet kein Alembic-Verfahren. Spätere SQL-Migrationen müssen nummeriert, wiederholbar getestet und mit einem Restorepfad dokumentiert werden.

## Störung

| Symptom | Prüfung |
|---|---|
| Player leer | API desselben Profils, aktive Revision, Last-good-Verzeichnis |
| Cafeteria zeigt Wochenende | Systemdatum/Zeitzone und `service_state`; kein Datumsparameter verwenden |
| Patientenansicht enthält Kosten | Veröffentlichung sofort zurückziehen; Snapshot- und DB-Vertrag prüfen |
| Tag und Woche unterscheiden sich | `X-Snapshot-Revision` vergleichen; beide Renderer müssen denselben Snapshot laden |
| Redis nicht bereit | `docker compose logs redis`; Secretdatei und Healthcheck-Skript prüfen |
| Migration scheitert | `migrate`-Log prüfen; App nicht manuell vor erfolgreicher Migration starten |
