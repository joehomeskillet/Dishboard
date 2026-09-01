# Docker-Compose-Deployment

Das Deployment startet PostgreSQL, Redis, SQL-Baseline, Flask/Gunicorn sowie Backup und optional Restore. Der fachliche Aufbau der zwei Profile steht im SDD; der vollständige Betriebsablauf in `../docs/DOCKER_COMPOSE_RUNBOOK.md`.

## Lokale Demo

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
