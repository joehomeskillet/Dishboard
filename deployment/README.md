# Docker-Compose-Deployment

Das Deployment startet PostgreSQL, Redis, SQL-Baseline, Flask/Gunicorn sowie Backup und optional Restore. Der fachliche Aufbau der zwei Profile steht im SDD; der vollständige Betriebsablauf in `../docs/DOCKER_COMPOSE_RUNBOOK.md`.

## Lokale Demo

Die Standarddatei `.env.example` ist fuer den oeffentlichen Host `dishboard.joelduss.xyz` produktionssicher vorbelegt. Fuer eine lokale Demo nach `bootstrap.sh` in `.env` bewusst `APP_IMAGE=suedhang-cafeteria:local`, `APP_ENV=development`, `APP_PUBLIC_BASE_URL=http://localhost:8080`, `DEMO_MODE=true`, `SEED_DEMO=true`, `DEMO_TODAY=2026-09-01` und `SESSION_COOKIE_SECURE=false` setzen.

```bash
./bootstrap.sh
docker compose config
docker compose build app migrate
docker compose up -d
```

| Ansicht | URL |
|---|---|
| Patienten heute / Woche | `http://localhost:8080/patienten/heute/` · `http://localhost:8080/patienten/wochenplan/` |
| Cafeteria heute / Woche | `http://localhost:8080/cafeteria/heute/` · `http://localhost:8080/cafeteria/wochenangebot/` |
| Vier Player | `/signage/cafeteria/tag`, `/signage/cafeteria/woche`, `/signage/patienten/tag`, `/signage/patienten/woche` |
| Backend | `http://localhost:8080/auth/login` |

Der Demo-Modus darf nie mit `APP_ENV=production` verwendet werden. Player-URLs akzeptieren keine Query-Parameter.

## Produktion

`bootstrap.sh` erzeugt nur technische Secrets und kopiert die produktionssicheren Defaults nach `.env`. Es provisioniert keine Benutzer. Der lokale Provider ist fuer den ersten Start aktiv; Entra bleibt deaktiviert, bis reale Tenant-ID, Client-ID und Client Secret gesetzt sind. Sobald `ENTRA_ENABLED=true` gilt, lehnt der App-Entrypoint fehlende oder bekannte Entra-Platzhalter ab. Demo-Werte, Abweichungen vom exakten oeffentlichen Ursprung, mutable Images und unsichere Session-Cookies werden immer abgelehnt. Der Migrationsdienst erzwingt separat `APP_ENV=migration` und erhaelt ausschliesslich die vier PostgreSQL-Secrets fuer Owner, App, Backup und Auth-Issuer. Die Issuer-Verbindungs-URL wird nur im Speicher aus dem dedizierten Passwort-File und dem normalen Datenbankziel gebildet; eine persistierte `AUTH_ISSUER_DATABASE_URL` ist verboten.

Das feste interne Netz reserviert `172.31.213.10` fuer das optionale
Compose-Caddy-Overlay und `172.31.213.20` fuer die App. Bei einem Caddy auf dem
Docker-Host erreicht der Proxy die App ueber den Loopback-Port und erscheint im
Container ausschliesslich als exaktes Gateway `172.31.213.1`. Nur diese beiden
Peers duerfen `X-Forwarded-For` liefern; direkte Clients und breite Docker-CIDRs
werden nicht vertraut.

Auf einem Host mit bereits laufendem Caddy wird nur die Basisdatei verwendet. Das App-Image wird lokal gebaut und ueber seine von Docker ausgegebene, unveraenderliche `sha256:<64-hex>`-ID gestartet; Tags sind nicht erlaubt. `APP_IMAGE` in `.env` auf den Inhalt der IID-Datei setzen:

```bash
./bootstrap.sh
docker build --iidfile /tmp/dishboard-image-id --file Dockerfile ..
docker compose config
docker compose up -d --pull never
docker compose ps
docker compose run --rm app python /app/manage.py provision-local-user --actor deployment-bootstrap --username admin --display-name Administrator --role Cafeteria.Admin
```

Der letzte Befehl fragt das Passwort interaktiv ab. Danach leitet `/auth/login` auf `/auth/local` um. `caddy/Caddyfile.host.example` ersetzt den bisherigen statischen Dishboard-VHost und proxyt ausschliesslich auf `127.0.0.1:8789`. Vor dem Reload die vorhandene VHost-Datei sichern und `caddy validate --config /etc/caddy/Caddyfile` ausfuehren. Das Compose-Caddy-Overlay ist nur fuer Hosts ohne bestehenden Listener auf 80/443 bestimmt.

Der App-Container speichert die Last-Good-Player-Snapshots im benannten Volume `last_good_data` unter `/var/lib/cafeteria/last-good`; sie ueberstehen Container-Neustarts. Redis- und PostgreSQL-Secrets werden aus Docker-Secret-Dateien gelesen und nicht als Prozessargumente an Healthchecks uebergeben.
