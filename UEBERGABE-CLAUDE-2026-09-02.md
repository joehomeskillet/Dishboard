# Übergabe an Claude Code — Dishboard

Stand: 2026-09-02. Diese Übergabe beendet die laufende Codex-Orchestrierung. Nichts hierin ist als Produktivfreigabe oder erledigtes Gesamtziel zu lesen.

## Auftrag

Dishboard als echte Flask/PostgreSQL-Menüplanung fertigstellen und unter `https://dishboard.joelduss.xyz/` betreiben:

- Patienten: Montag–Sonntag, Mittag und Abend, zwei Menüarten, technisch nirgends Preise.
- Cafeteria: Montag–Freitag, nur Mittag, zwei Menüarten, Mitarbeitenden- und Externenpreis; Wochenende geschlossen; kein Patienten-Fallback.
- Vier getrennte Signage-Player ohne Profil-/Datumsquery, Navigation oder Scrollen.
- Zwei getrennte Küchenraster, lokale Benutzer zusätzlich zu optionalem Entra.
- Profilgetrennte Drafts, Publikationen und Revisionen; Draft nie öffentlich.
- Reale PostgreSQL-, Browser-, Security-, Screenshot-, Paket-, ZIP- und SHA-256-Nachweise.
- Öffentliches GitHub-Repo `joehomeskillet/Dishboard`; grüne Integrationswellen regelmässig pushen.

Bindend: Projekt-`AGENTS.md`, SDD, README, Grok-Kritik und vorhandener Plan. Vor Writes GitNexus-Impact; vor Commits `gitnexus_detect_changes`. Jedes Shellkommando exakt als einzelnes `rtk <cmd>`, keine Pipelines/Verkettungen. Untracked `.claude/`, `AGENTS.md`, `CLAUDE.md` und fremde Änderungen erhalten. Keine Secrets lesen oder ausgeben.

## Nutzerpriorität

Aktuelle Domain zeigt nur falsche statische Landingpage. Nutzer verlangt zuerst echte Webapp mit Login. Nächste öffentliche Änderung muss Flask-App sein; keine weitere Landingpage-Arbeit. Danach Screenshots, Doku, Paket und ZIP.

## Git-Stand

Repository: `/nvmetank1/projects/menuplan`

- Geschützter Haupt-Tree: Branch `main`, HEAD `854c53f`.
- Integration: Worktree `.claude/worktrees/integration-wave-a`, Branch `integrate/wave-a`, HEAD `a3b5541`.
- GitHub-Branch `integration/wave-a` ist auf `a3b5541` gepusht; laut letzter Prüfung 21 Commits vor `main`.
- Auth-Readiness-Fix: Worktree `.claude/worktrees/auth-readiness-fix`, Branch `fix/auth-readiness-final`, Commit `308e3c0`; GitHub-Branch gleichnamig gepusht.
- Kein Merge nach `main` seit altem Stand. Nutzer kritisiert zurecht acht bis neun Stunden ohne Main-/App-Update.

Nur Orchestrator darf integrieren, pushen und deployen. Worker committen in eigenen Worktrees.

## Fertiger, aber noch nicht integrierter Auth-Fix

Commit `308e3c0` (`fix(auth): fail closed on runtime role drift`) basiert auf `f81708c`.

Änderungen:

- `runtime_role_hardening_status` validiert LOGIN, SUPERUSER/CREATEDB/CREATEROLE/INHERIT/REPLICATION/BYPASSRLS, Connection Limit, `VALID UNTIL`, exakte `rolconfig` und Memberships beider Richtungen für alle drei Laufzeitrollen.
- `validate_database` nutzt diesen Status fail-closed.
- Neue reale Drift-/Reprovisionierungs-Tests.

Beleg vom Autor: PostgreSQL 16 Fokus `44 passed, 0 failed, 0 skipped`; Ruff/Bandit/diff grün. Root las Diff und führte Ruff/Bandit/diff-check grün aus. GitNexus-Impact für `validate_database`: LOW, drei direkte Aufrufer (`init_database`, Health-Ready, `manage.py`). Unabhängiger Grok-Prozess verschwand ohne Schlussbericht; nicht als Review zählen. Neuer Review-Agent wurde durch Session-Reset ebenfalls beendet. Vor Cherry-pick unabhängigen Review und kombinierten Gate nachholen.

## Gestrandeter UI-P1-Worktree — nicht resetten

Worktree: `.claude/worktrees/ui-final-p1-fix`

Branch-HEAD noch `65e0c08`; kohärente Änderungen liegen **uncommittet** vor:

- `reference_scaffold/cafeteria/admin/routes.py`
- `reference_scaffold/cafeteria/static/app.css`
- `reference_scaffold/tests/test_admin_workflow_db.py`
- `reference_scaffold/tests/test_admin_workflow_routes.py`
- `reference_scaffold/tests/test_rendered_ui.py`
- neu: `reference_scaffold/tests/test_admin_workflow_concurrency_db.py`

Ziele/Finding-Liste:

1. Lange erlaubte Tokens dürfen bei allen vier Signage-Playern weder 1080p noch 4K horizontal/vertikal überlaufen.
2. Cafeteria-Adminfelder bei 390 und 1440 Pixel: alle interaktiven Ziele mindestens 44 Pixel, keine Überlappungen.
3. Fehler auf versteckten `week_start`/`row_version`-Feldern müssen bei Save und Publish beider Profile eine fokussierbare, sichtbare Fehlerzusammenfassung fokussieren; DB bleibt unverändert.
4. `test_admin_workflow_db.py` unter 600 Zeilen aufteilen.

Vor Reset standen RED-Regressionstests und Teilfix; frühere Lane meldete Ruff/fokussierte Gates grün, aber kein finaler Commit und kein belastbarer Gesamtbeleg. Erst Diff prüfen, GitNexus-Gates nachholen, checkpoint-committen, dann reale PostgreSQL-/Chromium-Gates.

## Gestrandeter Production-Start-Worktree — nicht resetten

Worktree: `.claude/worktrees/urgent-local-production-deploy`

Branch-HEAD noch `a3b5541`; Änderungen liegen **uncommittet** vor:

- `deployment/.env.example`
- `deployment/README.md`
- `deployment/docker-compose.yml`
- `deployment/entrypoint.sh`
- `deployment/validate_compose.py`
- `reference_scaffold/cafeteria/auth/routes.py`
- `reference_scaffold/cafeteria/config.py`
- `reference_scaffold/tests/test_auth_config.py`
- `reference_scaffold/tests/test_auth_routes.py`
- `reference_scaffold/tests/test_deployment_contracts.py`
- neu: `deployment/caddy/Caddyfile.host.example`

Ziele/Finding-Liste:

1. Produktion mit `ENTRA_ENABLED=false` und `LOCAL_AUTH_ENABLED=true` muss ohne Entra-Platzhalter starten.
2. `/auth/login` muss dann auf `/auth/local` führen; Callback/Frontchannel/Entra-Flows fail-closed. Bei Entra=true bleiben Tenant/Client/Secret strikt erforderlich.
3. Zusätzlich zu Registry-Digest `name@sha256:<64>` muss lokales unveränderliches Image `sha256:<64>` zulässig sein; Tags, kurze oder nichthexadezimale IDs ablehnen.
4. Reale Compose-Probe: lokal gebautes Image per ID und `--pull never`, kein Produktions-Build durch Compose.
5. Host-Caddy-Modus: App nur `127.0.0.1:8789`; Basis-Compose verwenden. Caddy-Overlay darf auf diesem Host nicht laufen, weil 80/443 belegt sind.

Letzter Agent meldete nur einen falschen pytest-cwd-Aufruf (`ModuleNotFoundError: cafeteria`) und wollte aus `reference_scaffold` neu laufen. Kein finaler Commit/Gate.

## Laufzeit- und Deploy-Stand

- Öffentlich: `https://dishboard.joelduss.xyz/` liefert derzeit falsche statische Landingpage aus `/srv/dishboard/releases/fe2e784`.
- Aktiver Caddy-Snippet: `/etc/caddy/dishboard.caddy`.
- Caddy-Hauptbackup: `/etc/caddy/Caddyfile.pre-dishboard-20260902`.
- Aktuelle Caddy-Konfiguration wurde zuletzt erfolgreich mit `caddy validate` geprüft.
- `systemctl reload caddy` scheiterte zweimal an bestehendem systemd-NAMESPACE-/`/var/tmp`-Problem. Direkter Befehl `rtk caddy reload --config /etc/caddy/Caddyfile --force` funktionierte.
- Port `8789` war frei; Port `8080` ist belegt.
- Warmes, **nicht finales** Image: `dishboard-warm:a3b5541`, ID `sha256:3def8761f3a9a9f867d106d6d0f51a7f01f8b4a1061694a0f63955ddddd64ac7`.
- Im Integrations-Worktree wurden `deployment/.env` und technische Secret-Dateien per `deployment/bootstrap.sh` erzeugt; alle Modus `0600`, gitignored. Inhalte niemals lesen/ausgeben. `.env` enthält noch alte Defaults und muss nach integriertem Deploy-Fix gezielt auf Port 8789/local auth/finales Image gesetzt werden.

Rollback bei Caddy-Umschaltung: bisherigen statischen Snippet sichern/wiederherstellen, komplette Caddy-Konfiguration validieren, direkt reloaden. Compose-Rollback ohne `-v`, damit Datenvolumes bleiben.

## Bisherige Testevidenz

- Frühere integrierte DB/Public/Deploy-Welle: `1973 passed, 0 failed, 0 skipped` gegen reale PostgreSQL-Umgebung.
- Auth-Endstand vor letztem Fix: `2033 passed, 0 failed, 0 skipped` inklusive PG16/Redis/Restore-Drill.
- UI-Review-Fix `65e0c08`: `1999 passed, 0 failed, 0 skipped` gegen PG16 + Chromium; danach wurden obige neuen UI-Findings entdeckt.
- Auth-Readiness-Fix `308e3c0`: Fokus `44 passed, 0 failed, 0 skipped` gegen PG16; Vollsuite nach Fix nicht final bestätigt.
- OCR war wiederholt durch Provider-429 nicht verfügbar; nie als bestanden zählen.

Alte Belege ersetzen keinen kombinierten Lauf nach finalen Cherry-picks.

## Paketvalidator — echte offene Arbeit

Sauberes Git-Archiv von `a3b5541` wurde unter `/tmp/dishboard-validator-a3b.IakUqN` geprüft. Secret-/Cachefehler verschwanden im sauberen Archiv; verbleibend:

1. Validator erwartet veraltet exakt 24 Tabellen.
2. Validator verlangt veraltet Bytegleichheit von SQL-Baseline und `schema.sql`.
3. Validator startet Vertragstests aus falschem cwd/PYTHONPATH; zehn `ModuleNotFoundError` bei `cafeteria`/`manage`.
4. Validator verlangt veraltet Gleichheit von Prototype- und Scaffold-CSS, obwohl Produkt-UI weiterentwickelt wurde.

Validator nicht abschwächen: Erwartungen auf tatsächlichen, sicherheitsrelevanten Vertrag aktualisieren, Tests aus korrektem `reference_scaffold`-cwd starten und negative Secret-/Cacheprüfungen erhalten. Danach auf finalem ZIP und neu entpacktem ZIP erneut ausführen.

## Empfohlene Reihenfolge

1. Beide gestrandeten Worktrees unverändert übernehmen; sofort kohärente Checkpoint-Commits, dann Gates/Folgefixes.
2. Auth `308e3c0` unabhängig reviewen.
3. Drei Fixserien einzeln verifizieren und in `.claude/worktrees/integration-wave-a` cherry-picken.
4. Reale kombinierte PostgreSQL-16-/Redis-/Restore-/Chromium-Vollsuite ohne relevante Skips; Security-, Ruff-, Bandit-, GitNexus- und Diff-Gates.
5. Grüne Integration sofort auf GitHub pushen; danach `main` integrieren/pushen. Kein weiterer mehrstündiger Push-Abstand.
6. Finales Image bauen, immutable ID verwenden, Base-Compose auf `127.0.0.1:8789` starten: DB, Redis, Migration, App, Backup. Migration exit 0 und `/health/live`/`ready` 200 beweisen.
7. Lokalen Benutzer `kueche.admin` interaktiv mit starkem, root-only gespeichertem Initialpasswort und Rolle `Cafeteria.Admin` provisionieren. `/auth/login` → `/auth/local`; echten Login testen. Optionales Entra deaktiviert lassen, solange reale Tenant-Daten fehlen.
8. Vorhandene aktuelle Beispieldaten decken Woche 2026-08-31 bis 2026-09-06 ab. Falls als Startinhalt genutzt: explizit einmalig importieren/publizieren, während `DEMO_MODE=false` und `SEED_DEMO=false` bleiben; danach beide Profile und Revisionstrennung prüfen.
9. Erst bei gesunder App `/etc/caddy/dishboard.caddy` von statischem Root auf `reverse_proxy 127.0.0.1:8789` umstellen; validieren, direkt reloaden, extern testen.
10. Kernrouten, Login, beide Websites, beide Mobile-Ansichten, beide Adminraster, vier Signage-Player, Wochenende geschlossen und Patientenwoche zusätzlich 3840×2160 screenshotten; Bilder öffnen und visuell prüfen.
11. README/SDD auf echten Stand, Paketvalidator reparieren, vollständiges ZIP erstellen, neu entpacken, Validator/tests erneut ausführen, SHA-256 erzeugen.

## Pflichtprobes nach Live-Schaltung

- `/health/live`, `/health/ready`
- `/auth/login`, `/auth/local`
- `/patienten/heute/`, `/patienten/wochenplan/`
- `/cafeteria/heute/`, `/cafeteria/wochenangebot/`
- `/signage/cafeteria/tag`
- `/signage/cafeteria/woche`
- `/signage/patienten/tag`
- `/signage/patienten/woche`
- Query-Parameter an öffentlichen/Signage-Routen ablehnen.
- Patientenantworten/HTML/JSON/CSV/Snapshots vollständig auf `CHF`, `Intern`, `Extern`, `0.00` und Preisfelder prüfen.

## Start-Prompt für Claude Code

```text
Übernimm Dishboard als primärer Orchestrator. Arbeitsverzeichnis: /nvmetank1/projects/menuplan. Lies zuerst vollständig AGENTS.md und UEBERGABE-CLAUDE-2026-09-02.md; danach SDD, Grok-Kritik und aktuellen Plan. Bewahre alle Dirty-/Untracked-Dateien. Setze nichts zurück. Übernimm zuerst die uncommitteten Änderungen in .claude/worktrees/ui-final-p1-fix und .claude/worktrees/urgent-local-production-deploy, checkpoint-committe sie nach GitNexus-Prüfung und bringe P1-Fixes mit realen PG/Redis/Chromium-Gates fertig. Reviewe 308e3c0 unabhängig, integriere nur grüne Commits in integration-wave-a, pushe jede grüne Welle regelmässig und deploye als erste sichtbare Änderung die echte Flask-Webapp mit lokalem Login auf https://dishboard.joelduss.xyz/. Danach Screenshots, README/SDD, Paketvalidator, ZIP-Neuentpackprüfung und SHA-256 abschliessen. Jedes Shellkommando exakt als einzelnes rtk <cmd>; keine Secrets ausgeben. Nur du mergst, pushst und deployest.
```
