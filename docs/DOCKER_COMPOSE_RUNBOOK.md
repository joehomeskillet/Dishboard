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
cp .env.example .env
docker compose config
docker compose up --build -d
docker compose ps
```

Demo-Routen verwenden `DEMO_TODAY=2026-09-01`. Öffentliche URLs besitzen trotzdem keinen Datumsparameter.

## Produktionswerte

```dotenv
APP_ENV=production
DEMO_MODE=false
SEED_DEMO=false
DEMO_TODAY=
APP_PUBLIC_BASE_URL=https://cafeteria.suedhang.ch
SESSION_COOKIE_SECURE=true
POSTGRES_SSLMODE=prefer
```

Tenant-ID, Client-ID und Secrets müssen real gesetzt sein. Secrets liegen unter `deployment/secrets/` und nicht in `.env`. Der Redis-Healthcheck ruft ein Skript auf; das Passwort steht nicht im Healthcheck-Kommando.

## Startprüfung

```bash
docker compose config
docker compose up --build -d
docker compose ps
docker compose logs --tail=200 migrate app db redis

docker compose run --rm app python /app/manage.py validate-db --wait-seconds 30
curl --fail http://127.0.0.1:8080/health/live
curl --fail http://127.0.0.1:8080/health/ready
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

Der Restore wird zuerst in einem separaten Testsystem ausgeführt. Anschliessend: Datenbankvalidator, beide Snapshot-APIs, Patienten-Sonntagabend und Cafeteria-Geschlossenfläche prüfen.

## Update

```bash
./backup.sh
docker compose build --pull
docker compose up -d db redis
docker compose run --rm migrate
docker compose up -d app backup
docker compose ps
```

Die mitgelieferte Migration ist eine versionierte SQL-Baseline. Das Paket behauptet kein Alembic-Verfahren. Spätere SQL-Migrationen müssen nummeriert, wiederholbar getestet und mit einem Restorepfad dokumentiert werden.

## Störung

| Symptom | Prüfung |
|---|---|
| Player leer | API desselben Profils, aktive Revision, Last-good-Verzeichnis |
| Cafeteria zeigt Wochenende | Systemdatum/Zeitzone und `service_state`; kein Datumsparameter verwenden |
| Patientenansicht enthält Kosten | Veröffentlichung sofort zurückziehen; Snapshot- und DB-Vertrag prüfen |
| Tag und Woche unterscheiden sich | `X-Snapshot-Revision` vergleichen; beide Renderer müssen denselben Snapshot laden |
| Redis nicht bereit | `docker compose logs redis`; Secretdatei und Healthcheck-Skript prüfen |
| Migration scheitert | `migrate`-Log prüfen; App nicht manuell vor erfolgreicher Migration starten |
