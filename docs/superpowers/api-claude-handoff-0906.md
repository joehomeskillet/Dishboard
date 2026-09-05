# API-Übergabe an Claude — 2026-09-06

Stand: 2026-09-06, ca. 00:40 Europe/Zurich. Dieses Dokument wurde separat auf `github/main` nach frischem Fetch vorbereitet; Basis dieses Dokumentations-Worktrees ist `b644dac` (Schema v16).

## 1. Aktuelle Zuständigkeit — neueste Nutzerkorrektur gilt

Der Nutzer lässt Claude parallel an der API weiterarbeiten und hat anschliessend präzisiert, dass Claude das Deployment Codex überlässt.

- **Claude besitzt die API-Entwicklung:** REST/OpenAPI/Swagger, FHIR, MCP, API-Schlüssel und deren Admin-Seite. Migration `0014_v16_to_v17.sql` / Schema v17 bleibt bei Claude. Claude liefert die fertiggestellten Branches, Commit-Hashes, offene Punkte und Gate-Belege an den Root-Codex.
- **Root-Codex besitzt finale Integration und Release:** Er sammelt Claudes fertige API-Lieferung ein, prüft Diffs, wiederholt die Gates unabhängig, integriert API und UI und führt das koordinierte Deployment durch. Claude führt kein Produktionsdeployment durch und pusht/merged nicht eigenständig nach `main`.
- **Parallele UI-Arbeit:** Root-Codex und seine UI-Lanes arbeiten am Backlog-Paket `backlog-wave1`. Sie ändern keine API-Quelldateien und keine API-Migration. Bis zur fertigen Claude-Lieferung erfolgt keine vorgezogene API-Übernahme in die UI-Welle.
- Die vorherige Annahme, Claude würde die API selbst produktiv deployen, ist ausdrücklich überholt. Zum Übergabezeitpunkt laufen bei Root noch UI-Gates mit zu untersuchenden Fehlern; daraus ist keine Deploy-Freigabe abzuleiten.

Alle bestehenden API-Worktrees sowie die zwei unten beschriebenen Recovery-Worktrees bleiben erhalten. Der dokumentierende Agent hat nach dem Zuständigkeitswechsel keine weitere API-Implementierung, Integration oder Gate-Ausführung begonnen.

## 2. Verbindliche Grundlagen

Vor Fortsetzung lesen:

1. `/nvmetank1/projects/menuplan/UEBERGABE-CODEX-API-2026-09-05.md`, besonders §4 und §6.
2. `/nvmetank1/projects/menuplan/KOORDINATION-API-CODEX-2026-09-05.md` vollständig. Die neueste Zuständigkeit in §1 dieses Dokuments ersetzt die ältere Release-Aufteilung.
3. Spec im Worktree `/nvmetank1/projects/menuplan/.claude/worktrees/api-spec-0905`: `docs/superpowers/specs/2026-09-05-dishboard-api-mcp-fhir-design.md`, Commit `5e4750f`, Branch `docs/api-mcp-fhir-spec-0905`.
4. Die Briefs und `COMMON.md` unter `/nvmetank1/projects/menuplan/.claude/state/api-mcp-fhir-0905/`.

Die API-Lanes zweigen historisch von `6f5204b` / Schema v16 ab. `main` enthält inzwischen Tabler/v16 (`b644dac` bei Anlage dieser Übergabe); die frühere v16-Vorbedingung ist damit erfüllt. Ein Rebase oder eine finale Integration wurde durch diese Übergabe nicht ausgeführt.

## 3. Fertige, eng begrenzte Recovery-Commits

Worktree-Basis für die folgenden Pfade: `/nvmetank1/projects/menuplan/.claude/worktrees/`.

| Recovery | Worktree | Branch | Explizite Basis | Commit | Einziger Dateiumfang |
|---|---|---|---|---|---|
| A1: Publikationen erhalten | `api-a1-recovery-0906` | `fix/api-a1-retain-publications-0906` | `1631264` | **`5a5f98b`** | `reference_scaffold/cafeteria/db.py`: 3 Löschungen |
| D: Schema-Vertrag im Test | `api-d-recovery-0906` | `fix/api-d-schema-test-0906` | `661eb19` | **`6bc1cc7`** | `reference_scaffold/tests/test_auth_database.py`: 3 Ersetzungen |

Beide Recovery-Worktrees waren nach dem Commit sauber. Es gab keinen Push, Merge oder Rebase. Die ursprünglichen A1-/D-Worktrees wurden nicht verändert.

### A1 — kritische Datenlöschung entfernt

Der ursprüngliche A1-Commit `1631264` enthielt ausserhalb des REST-Auftrags drei zusätzliche Zeilen in `init_database()`: Nach `run_migrations()` wurden `publication_revisions` und `menu_weeks` mit `TRUNCATE ... CASCADE` geleert. Der Schritt war unbedingt und nicht an `seed_demo` gebunden.

`5a5f98b` entfernt genau diese drei Zeilen und stellt den vorherigen Initialisierungsablauf wieder her. Keine anderen A1-Funktionen wurden geändert. **Den ursprünglichen A1-Tip nicht allein übernehmen:** Die endgültige API-Lieferung muss diese Recovery enthalten, damit der Löschschritt nicht wieder eingeführt wird.

Syntaxprüfung, Ruff und `git diff --check` bestanden. **Das vollständige A1-Datenbankgate wurde weder vom Recovery-Agenten noch als unabhängiges Root-Gate für diese Recovery ausgeführt.** Root muss es nach Claudes Lieferung auf dem endgültigen Integrationsstand wiederholen.

### D — nur veraltete Test-Erwartungen korrigiert

In `test_migration_plan_contains_auth_issuer_contract()` wurde die explizite Erwartung von Schema 16 / letzter Migration `0013_v15_to_v16.sql` auf Schema 17 / `0014_v16_to_v17.sql` korrigiert. Beide Versionswerte und der Dateiname gehören zu dieser einen Migrationplan-Prüfung.

Die Implementierung auf Basis `661eb19` führt bereits `SCHEMA_VERSION = 17` und Migration 0014. Store, SQL, Berechtigungen und Migrationsinhalt wurden von der Recovery nicht verändert.

## 4. Gate-Belege der Recoveries

### Syntax und Ruff

Die beiden betroffenen Python-Dateien wurden mit `/tmp/dishboard-shared-venv/bin/python -m py_compile` geprüft: jeweils Exit 0, keine Ausgabe. Ruff wurde je Datei mit `/root/.local/bin/ruff check` ausgeführt. Ausgabe jeweils wörtlich:

```text
All checks passed!
```

`git diff --check` lieferte in beiden Worktrees Exit 0 ohne Ausgabe.

### Vollständiges D-Gate — eigenständige Recovery-Prüfung

Ausgeführt am Recovery-Stand, anschliessend unverändert als `6bc1cc7` committed:

```bash
rtk bash /nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-api-d-gate.sh /nvmetank1/projects/menuplan/.claude/worktrees/api-d-recovery-0906 -q tests/test_api_keys_db.py tests/test_database_invariants.py tests/test_auth_database.py tests/test_database_role_readiness.py -p no:cacheprovider -rs
```

Abschlussausgabe wörtlich:

```text
153 passed in 80.18s (0:01:20)
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/api-d-recovery-0906/reference_scaffold
```

Keine Skips. Testpool: PostgreSQL-Container `menuplan-orch-api-d-pg16`, Datenbank `menuplan_api_d`, zugehöriger Redis-Container `menuplan-orch-api-d-redis`. Der Recovery-Gate-Prozess ist beendet; **der API-D-Testpool ist von dieser Recovery wieder freigegeben**. Andere Pools (`test_root`, `test_sdd`, `test_ui_other`) gehören den parallelen Arbeiten und wurden nicht verwendet.

Zusätzlich wurde im D-Recovery-Worktree ausgeführt:

```bash
rtk /tmp/dishboard-shared-venv/bin/python database/validate_schema.py
```

Exit 0. Das JSON meldet `artifact_check: passed`, `schema_version: 17` und `live_postgresql_executed: false`. Diese Artefaktprüfung ersetzt nicht das PostgreSQL-Gate.

### Grenzen der Belege

- GitNexus-Impact vor A1: MEDIUM, fünf direkte Aufrufer. Detect im eigenen Worktree erkannte eine geänderte Datei, aber keine Symbolzuordnung beim kurzen Löschdiff; manueller Diff bestätigte nur die drei Zeilen in `init_database()`.
- GitNexus-Impact vor D: LOW, keine aufrufenden Abhängigkeiten. Detect bestätigte genau `test_migration_plan_contains_auth_issuer_contract()` als geänderte Testfunktion.
- Beide Worktrees wurden abschliessend mit `rtk gitnexus-reindex <WT>` registriert; die Wrapper-Ausgabe bestätigte die Registry-Bereinigung. Automatisch erzeugte, untracked Zusatzdokumente wurden nur in den eigenen Recovery-Worktrees entfernt.
- **OCR: UNAVAILABLE.** Bekannte frühere Provider-/Timeout-Fehler wurden auf Anweisung nicht erneut versucht. Kein erfolgreicher OCR-Nachweis wird behauptet.
- Ein zusätzlicher Host-Mypy-Lauf für A1 war rot: `Found 92 errors in 34 files (checked 1 source file)`, unter anderem fehlende Imports/Stubs für SQLAlchemy/Flask. Im gemeinsamen Test-venv fehlt das Mypy-Binary. Die Typprüfung wurde nicht als bestanden gewertet.
- Root muss die erforderlichen Gates unabhängig auf der finalen Lieferung wiederholen. Kein kombiniertes API-Gate, Produktions-Smoke oder Deployment wurde durch die Recovery durchgeführt.

## 5. Ursprüngliche API-Lanes — Inventur vor dem Zuständigkeitswechsel

Diese Tabelle ist die zuletzt erhobene Inventur, keine Behauptung über spätere parallele Änderungen durch Claude. Vor Fortsetzung lokale Branches und `git status` erneut prüfen.

| Lane | Ursprünglicher Worktree | Branch | Stand der Inventur |
|---|---|---|---|
| A1 | `api-a1-0905` | `feat/api-v1-openapi-0905` | `1631264`, sauber; Recovery aus §3 separat |
| B | `fhir-b-0905` | `feat/fhir-r5-0905` | `1d64a8b` + `56758ff`; **dirty** `reference_scaffold/tests/test_fhir_mapping.py`: zwei `# noqa: E402` an Imports, unverändert erhalten |
| D | `api-keys-d-0905` | `feat/api-keys-schema-0905` | `661eb19`, sauber; alter Schlussreport BLOCKED wegen Schema-Test/OCR; Testkorrektur aus §3 separat |
| C | `mcp-c-0905` | `feat/mcp-server-0905` | `88be33f`, sauber, bereits in API-Integration |
| A2 | `api-a2-0905` | `feat/api-docs-swagger-0905` | `7c6397e`, sauber, bereits in API-Integration |
| F | `api-docs-f-0905` | `docs/api-docs-0905` | `b8e1430`, sauber, bereits in API-Integration |
| Integration | `api-integration-0905` | `integrate/api-mcp-fhir-0905` | `8fb6135`, sauber; enthält Spec, C, A2, F; A1/B/D noch nicht enthalten |

Integrations-Merges der Inventur: `dbf01a8` (C), `b3c14b1` (A2), `8fb6135` (F). Die zwei Recovery-Commits ändern diese ursprünglichen Lanes nicht. Insbesondere **dirty B weder verwerfen noch überschreiben**.

Alle damaligen Lane-Logs unter `.claude/state/api-mcp-fhir-0905/logs/` hatten terminale `*_EXIT=`-Zeilen. Die damalige `/proc`-Prüfung fand keine API-Worktree-Prozesse oder offenen API-Loghandles. Das ist historischer Abschlussbeleg, kein Laufstatus der nun gestarteten Claude-Arbeit.

## 6. Nächste Lieferung von Claude an Root-Codex

1. API-Stand und Zuständigkeiten abgleichen; beide Recovery-Commits berücksichtigen und dirty B erhalten.
2. Welle 1 gemäss ursprünglichem Handoff fachlich fertigstellen. Die A1-Recovery muss Bestandteil des finalen Inhalts sein; die D-Testkorrektur darf nicht fehlen. Frühere Lane-Prosa ersetzt keine Gate-Ausgaben.
3. Welle 2 anhand `brief-e.md` und `brief-g.md` fertigstellen. Bei Inventur waren die Briefs vorhanden, `admin-api-e-0905` und `api-keyed-g-0905` jedoch noch nicht angelegt. Keine alte Laufannahme übernehmen.
4. Fertige Lieferung an Root mit Worktree-/Branch-Namen, vollständiger Commit-Liste, Diffs, Gate-Ausgaben, fehlenden Reviews und Migrationshinweis 16→17. Root übernimmt unabhängige Prüfungen, finale Integration, Manifest/Packaging und Deployment-Abstimmung mit der UI-Welle.

Root koordiniert weiterhin Sidebar/Tabler-Layout und gemeinsame UI-Dateien. Keine parallelen ungeklärten Änderungen an `cafeteria/__init__.py`, `db.py`, Packaging oder den Sidebar-Verträgen. Für das Release bleiben Backup, Migration 0014, API/FHIR/Admin-Smokes und Patientenkanal ohne Preise verbindlich.

## 7. Arbeitsregeln für die Fortsetzung

Jeder Shell-Aufruf direkt mit `rtk`, ein Befehl pro Aufruf. Writes ausschliesslich in eigenen abgestimmten Worktrees. Keine Secrets oder Env-/Credentialdateien lesen oder ausgeben; Gate-Wrapper laden ihr Test-Env selbst. Keine Quota-Vorprüfungen oder stillen Modell-/Providerwechsel. Maximal eine schwere Last gleichzeitig; Testpools vor Verwendung mit Root koordinieren. Keine Produktionsänderung durch Claude.

Dieses Dokumentations-Arbeitspaket hat keine Produktdateien geändert und keine Produkt-Gates erneut ausgeführt. Es enthält bereits gemessene Recovery-Belege; der Dokumentationscommit ist kein API-Release.
