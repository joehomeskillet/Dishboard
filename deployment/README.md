# Docker-Compose-Deployment

Das Deployment startet PostgreSQL, Redis, SQL-Baseline, Flask/Gunicorn sowie Backup und optional Restore. Der fachliche Aufbau der zwei Profile steht im SDD; der vollständige Betriebsablauf in `../docs/DOCKER_COMPOSE_RUNBOOK.md`.

## Lokale Demo

Die Standarddatei `.env.example` ist fuer den oeffentlichen Host `dishboard.joelduss.xyz` produktionssicher vorbelegt. Fuer eine lokale Demo nach `bootstrap.sh` in `.env` bewusst `APP_ENV=development`, `APP_PUBLIC_BASE_URL=http://localhost:8080`, `DEMO_MODE=true`, `SEED_DEMO=true`, `DEMO_TODAY=2026-09-01` und `SESSION_COOKIE_SECURE=false` setzen.

```bash
./bootstrap.sh
docker compose config
docker compose up --build -d
```

| Ansicht | URL |
|---|---|
| Patienten heute / Woche | `http://localhost:8080/patienten/heute/` · `http://localhost:8080/patienten/wochenplan/` |
| Cafeteria heute / Woche | `http://localhost:8080/cafeteria/heute/` · `http://localhost:8080/cafeteria/wochenangebot/` |
| Vier Player | `/signage/cafeteria/tag`, `/signage/cafeteria/woche`, `/signage/patienten/tag`, `/signage/patienten/woche` |
| Backend | `http://localhost:8080/auth/login` |

Der Demo-Modus darf nie mit `APP_ENV=production` verwendet werden. Player-URLs akzeptieren keine Query-Parameter.

## Produktion

`bootstrap.sh` erzeugt nur technische Secrets und kopiert die produktionssicheren Defaults nach `.env`. Es provisioniert weder Entra noch lokale Benutzer. Vor dem Produktionsstart hinterlegt der Betreiber reale Entra-IDs sowie das Client Secret; erst danach `ENTRA_ENABLED=true` setzen. Der App-Entrypoint lehnt Demo-Werte, unsichere oder abweichende oeffentliche URLs, unsichere Session-Cookies sowie bekannte Entra-Platzhalter ab. Der Migrationsdienst erzwingt separat `APP_ENV=migration` und erhaelt ausschliesslich die drei PostgreSQL-Secrets.

Der Produktionsstart verwendet immer Basisdatei und Caddy-Overlay:

```bash
./bootstrap.sh
docker compose -f docker-compose.yml -f docker-compose.caddy.yml config
docker compose -f docker-compose.yml -f docker-compose.caddy.yml up --build -d
docker compose -f docker-compose.yml -f docker-compose.caddy.yml ps
```

Der App-Container speichert die Last-Good-Player-Snapshots im benannten Volume `last_good_data` unter `/var/lib/cafeteria/last-good`; sie ueberstehen Container-Neustarts. Redis- und PostgreSQL-Secrets werden aus Docker-Secret-Dateien gelesen und nicht als Prozessargumente an Healthchecks uebergeben.
