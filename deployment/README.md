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

## Produktion mit Host-Caddy

Das Deployment nutzt einen Reverse Proxy (Caddy) auf dem Docker-Host, der ausschliesslich auf den Docker-Compose-Stack auf `127.0.0.1:8789` proxied. Die App läuft intern ohne feste IP im Compose-Netzwerk `10.213.0.0/24` und erscheint dem Proxy als Gateway `10.213.0.1`.

### Vorbereitung

`bootstrap.sh` erzeugt nur technische Secrets und kopiert die produktionssicheren Defaults nach `.env`. Es provisioniert keine Benutzer.

```bash
./bootstrap.sh
```

Das Verzeichnis `secrets/` wird mit Modus 0700 angelegt; die Secret-Dateien darin sind 0444. Der lokale Provider ist für den ersten Start aktiv; Entra bleibt deaktiviert, bis reale Tenant-ID, Client-ID und Client Secret gesetzt sind. Sobald `ENTRA_ENABLED=true` gilt, lehnt der App-Entrypoint fehlende oder Platzhalter-Credentials ab.

### Image-Build und APP_IMAGE-Setzung

Das App-Image wird lokal gebaut und über die unveränderliche SHA-256-ID gestartet (kein Tag, kein Registry-Digest).

```bash
docker build --iidfile /tmp/dishboard-image-id --file Dockerfile ..
```

Die `--iidfile` speichert die vollständige `sha256:<64-hex>`-ID in die Datei. Diese ID dann in `.env` setzen:

```bash
export APP_IMAGE=$(cat /tmp/dishboard-image-id)
echo "APP_IMAGE=$APP_IMAGE" >> .env
```

### Compose-Start ohne Build

Mit lokaler Image-ID und Docker Compose:

```bash
docker compose config
docker compose up -d --pull never --no-build
docker compose ps
```

Der `--pull never`-Flag sperrt Registry-Zugriffe; `--no-build` verhindert lokales Rebuild. Healthchecks prüfen PostgreSQL auf 5432, Redis auf 6379 und die App auf 127.0.0.1:8789.

### Erst-Administrator-Bootstrap

Nach erfolgreichem Compose-Start den Migrate-Container nutzen, um den ersten Administrator fail-closed zu bootstrappen:

```bash
docker compose run --rm --no-deps migrate python /app/manage.py bootstrap-local-admin \
  --username admin \
  --display-name Administrator
```

Der Befehl fragt das Passwort zweimal interaktiv ab, oder liest es aus der Datei `DISHBOARD_BOOTSTRAP_PASSWORD_FILE` (Modus 0400), falls diese gesetzt ist:

```bash
# Optional: Passwort-Datei für automatisierte Bootstrap
echo "mein-sicheres-passwort" > /tmp/dishboard-bootstrap.pwd
chmod 0400 /tmp/dishboard-bootstrap.pwd
export DISHBOARD_BOOTSTRAP_PASSWORD_FILE=/tmp/dishboard-bootstrap.pwd

# Bootstrap mit Datei-Passwort
docker compose run --rm --no-deps migrate python /app/manage.py bootstrap-local-admin \
  --username admin \
  --display-name Administrator
```

Nach erfolgreichem Bootstrap sperrt sich die Bootstrap-Funktion fail-closed: weitere Aufrufe schlagen fehl, wenn bereits ein aktiver Administrator (lokal oder Entra) existiert.

Danach leitet `/auth/login` auf `/auth/local` um. Weitere Benutzer können von verifizierten Administratoren provisioniert werden:

```bash
docker compose exec -it app python /app/manage.py provision-local-user \
  --actor admin \
  --username operator \
  --display-name Betreiber \
  --role Cafeteria.Publisher
```

### Host-Caddy-Konfiguration

Falls Caddy bereits auf dem Docker-Host läuft, wird nur die Basisdatei `docker-compose.yml` verwendet (nicht `compose.caddy.yml`). Der Host-Caddy proxied ausschliesslich auf `127.0.0.1:8789`:

```caddyfile
# Excerpt from /etc/caddy/Caddyfile
dishboard.example.com {
    reverse_proxy 127.0.0.1:8789
}
```

Vor dem Reload die existierende VHost-Datei sichern und validieren:

```bash
sudo cp /etc/caddy/Caddyfile /etc/caddy/Caddyfile.backup
sudo caddy validate --config /etc/caddy/Caddyfile
sudo caddy reload --config /etc/caddy/Caddyfile
```

Nur das Gateway `10.213.0.1` darf `X-Forwarded-For` liefern; die App wertet den rechtesten nicht vertrauenswürdigen Hop aus.

Das Compose-Caddy-Overlay (`compose.caddy.yml`) ist nur für Hosts ohne bestehenden Listener auf 80/443 bestimmt.

### Datenspeicherung und Restore

Der App-Container speichert die Last-Good-Player-Snapshots im benannten Volume `last_good_data` unter `/var/lib/cafeteria/last-good`; sie überstehen Container-Neustarts und dienen als Fallback bei Datenbankfehlern.

Backups werden periodisch über den `backup`-Service erstellt (mit Secrets-Ausschlusstabellen). Das Restore-Profil ermöglicht manuelle Wiederherstellung:

```bash
docker compose --profile ops up -d restore
docker compose logs restore
```

### Redeploy nach Update

Beim Redeploy nach Code-Updates:

1. Neues Image bauen:
   ```bash
   docker build --iidfile /tmp/dishboard-image-id-new --file Dockerfile ..
   ```

2. `APP_IMAGE` in `.env` aktualisieren:
   ```bash
   export APP_IMAGE=$(cat /tmp/dishboard-image-id-new)
   sed -i "s|^APP_IMAGE=.*|APP_IMAGE=$APP_IMAGE|" .env
   ```

3. Compose neu starten (alte Container werden beendet und neue gestartet):
   ```bash
   docker compose up -d --pull never --no-build
   docker compose ps
   ```

4. (Optional) Alte Images aufräumen:
   ```bash
   docker image prune -a --filter "until=24h"
   ```

### Sicherheit und Secrets

Das Verzeichnis `deployment/secrets/` gehört root mit Modus 0700; die Secret-Dateien sind 0444 und werden pro Service als Bind-Mount eingebunden:

- `secrets/pg_password_cafeteria_app`: PostgreSQL-Passwort für `cafeteria_app`
- `secrets/pg_password_cafeteria_owner`: PostgreSQL-Passwort für Owner (Migrationslauf)
- `secrets/pg_password_cafeteria_backup`: PostgreSQL-Passwort für `cafeteria_backup`
- `secrets/pg_password_cafeteria_auth_issuer`: PostgreSQL-Passwort für `cafeteria_auth_issuer`
- `secrets/redis_password`: Redis-Passwort (falls AUTH aktiv)

Keine Geheimnisse in `.env`, in Git oder in Prozessargumenten (besonders nicht in Healthcheck-Befehlen).

App und Migrate laufen als UID 10001; Redis als 999:1000. Healthchecks werden über `sh` aufgerufen und lesen Secrets ohne Passwort als CLI-Argumente.

### Netzwerk und interne Adressierung

Das feste interne Netz reserviert `10.213.0.10` für das optionale Compose-Caddy-Overlay und `10.213.0.1` als Gateway. Die App erhält keine feste interne IP; bei einem Caddy auf dem Docker-Host erreicht der Proxy die App über den Loopback-Port `127.0.0.1:8789` und erscheint im Container ausschliesslich als exaktes Gateway `10.213.0.1`.

Das Subnetz `10.213.0.0/24` liegt bewusst ausserhalb der Docker-Standard-Adressbereiche (172.16.0.0/12 und 192.168.0.0/16) und muss auf dem Host frei bleiben, um Kollisionen mit anderen Netzwerken zu vermeiden.
