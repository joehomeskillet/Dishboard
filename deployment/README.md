# Docker-Compose-Deployment

Das Deployment startet PostgreSQL, Redis, SQL-Baseline, Flask/Gunicorn sowie Backup und optional Restore. Der fachliche Aufbau der zwei Profile steht im SDD; der vollständige Betriebsablauf in `../docs/DOCKER_COMPOSE_RUNBOOK.md`.

## Lokale Demo

Die Standarddomain fuer Reverse Proxy und Entra ist `dishboard.joelduss.xyz`. Fuer einen lokalen Browserstart in `.env` mindestens `APP_PUBLIC_BASE_URL=http://localhost:8080` setzen; die Werte bleiben Operator-Overrides.

```bash
./bootstrap.sh
cp .env.example .env
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

`bootstrap.sh` erzeugt nur technische Secrets. Es provisioniert weder Entra noch lokale Benutzer. Vor dem Produktionsstart setzt der Betreiber `APP_ENV=production`, deaktiviert `DEMO_MODE` und `SEED_DEMO`, leert `DEMO_TODAY` und hinterlegt reale Entra-IDs sowie das Client Secret. Erst danach `ENTRA_ENABLED=true` setzen. Der Entrypoint lehnt Demo-Werte, Standard-IDs und das Bootstrap-Platzhaltersecret in diesem Modus ab.

Der App-Container speichert die Last-Good-Player-Snapshots im benannten Volume `last_good_data` unter `/var/lib/cafeteria/last-good`; sie ueberstehen Container-Neustarts. Redis- und PostgreSQL-Secrets werden aus Docker-Secret-Dateien gelesen und nicht als Prozessargumente an Healthchecks uebergeben.
