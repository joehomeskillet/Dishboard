# Docker-Compose-Deployment

Das Deployment startet PostgreSQL, Redis, SQL-Baseline, Flask/Gunicorn sowie Backup und optional Restore. Der fachliche Aufbau der zwei Profile steht im SDD; der vollständige Betriebsablauf in `../docs/DOCKER_COMPOSE_RUNBOOK.md`.

## Lokale Demo

Die Standarddatei `.env.example` ist für den öffentlichen Host `dishboard.joelduss.xyz` produktionssicher vorbelegt. Für eine lokale Demo nach `bootstrap.sh` in `.env` bewusst `APP_IMAGE=suedhang-cafeteria:local`, `APP_ENV=development`, `APP_PUBLIC_BASE_URL=http://localhost:8080`, `DEMO_MODE=true`, `SEED_DEMO=true`, `DEMO_TODAY=2026-09-01` und `SESSION_COOKIE_SECURE=false` setzen.

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

`bootstrap.sh` erzeugt nur technische Secrets und kopiert die produktionssicheren Defaults nach `.env`. Es provisioniert keine Benutzer. Der lokale Provider ist für den ersten Start aktiv; Entra bleibt deaktiviert, bis reale Tenant-ID, Client-ID und Client Secret gesetzt sind. Sobald `ENTRA_ENABLED=true` gilt, lehnt der App-Entrypoint fehlende oder bekannte Entra-Platzhalter ab. Demo-Werte, Abweichungen vom exakten öffentlichen Ursprung, unveränderliche Images und unsichere Session-Cookies werden immer abgelehnt. Der Migrationsdienst erzwingt separat `APP_ENV=migration` und erhält ausschliesslich die vier PostgreSQL-Secrets für Owner, App, Backup und Auth-Issuer. Die Issuer-Verbindungs-URL wird nur im Speicher aus dem dedizierten Passwort-File und dem normalen Datenbankziel gebildet; eine persistierte `AUTH_ISSUER_DATABASE_URL` ist verboten.
Das Verzeichnis `secrets/` gehört root mit Modus 0700; die Secret-Dateien sind 0444 und werden pro Service als Bind-Mount eingebunden. App und Migrate laufen als UID 10001, Redis als 999:1000, Healthchecks werden über `sh` aufgerufen.

Das feste interne Netz reserviert `10.213.0.10` für das optionale Compose-Caddy-Overlay und `10.213.0.1` als Gateway. Die App erhält keine feste interne IP; bei einem Caddy auf dem Docker-Host erreicht der Proxy die App über den Loopback-Port `127.0.0.1:8789` und erscheint im Container ausschliesslich als exaktes Gateway `10.213.0.1`. Nur das Gateway und im Overlay-Betrieb der Overlay-Caddy dürfen `X-Forwarded-For` liefern; die App wertet den rechtesten nicht vertrauenswürdigen Hop der Kette aus. Direkte Clients und breite Docker-CIDRs werden nicht vertraut.
Das Subnetz 10.213.0.0/24 liegt bewusst ausserhalb der Docker-Standard-Adressbereiche (172.16.0.0/12 und 192.168.0.0/16) und muss auf dem Host frei bleiben, um Kollisionen mit anderen Netzwerken zu vermeiden.

Auf einem Host mit bereits laufendem Caddy wird nur die Basisdatei verwendet. Das App-Image wird lokal gebaut und über seine von Docker ausgegebene, unveränderliche `sha256:<64-hex>`-ID gestartet; Tags sind nicht erlaubt. `APP_IMAGE` in `.env` auf den Inhalt der IID-Datei setzen:

```bash
./bootstrap.sh
docker build --iidfile /tmp/dishboard-image-id --file Dockerfile ..
docker compose config
docker compose up -d --pull never --no-build
docker compose ps
docker compose run --rm --no-deps migrate python /app/manage.py bootstrap-local-admin --username admin --display-name Administrator
```

Der letzte Befehl fragt das Passwort zweimal interaktiv ab oder liest aus `DISHBOARD_BOOTSTRAP_PASSWORD_FILE` (Mode 0400). Danach leitet `/auth/login` auf `/auth/local` um. `caddy/Caddyfile.host.example` ersetzt den bisherigen statischen Dishboard-VHost und proxyt ausschliesslich auf `127.0.0.1:8789`. Vor dem Reload die vorhandene VHost-Datei sichern und `caddy validate --config /etc/caddy/Caddyfile` ausführen. Das Compose-Caddy-Overlay ist nur für Hosts ohne bestehenden Listener auf 80/443 bestimmt.

Der App-Container speichert die Last-Good-Player-Snapshots im benannten Volume `last_good_data` unter `/var/lib/cafeteria/last-good`; sie überstehen Container-Neustarts. Redis- und PostgreSQL-Secrets werden aus Docker-Secret-Dateien gelesen und nicht als Prozessargumente an Healthchecks übergeben.
