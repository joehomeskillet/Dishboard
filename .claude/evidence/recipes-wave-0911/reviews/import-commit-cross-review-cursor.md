# Cross-Vendor-Review — MP-REC-IMPORT-COMMIT (wp-0930bf4acf98-review)

| Feld | Wert |
|------|------|
| **Branch** | `feat/rec-import-commit-0911` |
| **HEAD** | `46d67051667611c301a570847e1d1e9cd3adfbb6` |
| **Basis** | `79b3fe9964d6bfcd120bd3fecba204ee556fc152` |
| **Reviewer-Modell** | cursor composer-2.5 |
| **Autor** | grok-build / grok-4.6 |

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|----|-------------|--------|---------|-----------|
| 1 | `reference_scaffold/tests/test_rec_import_batch_migration_db.py:70` | Kombiniertes Gate 1 ist rot: nach `run_migrations` wird `max(version)==28` erwartet, Worktree liefert 29. Eigene Commit-/Migrationstests sind grün; Ursache ist ein harter Fremd-Pin im Batch-Migrations-Test (Besitz MP-REC-IMPORT-BATCH). | major | Pin in `test_rec_import_batch_migration_db.py` auf 29 anheben (Batch-WP/Root), nicht im Commit-WP. |
| 2 | `reference_scaffold/tests/test_tabler_package_verification.py` (Fault-Strings) | Gate 2 rot: Tabler-Paketverifikation erwartet Schema 26 / 52 Tabellen, Ist 29 / 54. Fremd-Pin-Klasse, im Autorbericht dokumentiert. | major | Root/Tabler-WP: Schema- und Tabellen-Pins auf v29 nachziehen. |
| 3 | Autorbericht §UI-Coverage | 200 %-Zoom auf dem Commit-Bestätigungsdialog nicht gefahren (nur bestehender Upload-Konfliktpfad). Akzeptanzkriterium teilweise offen. | minor | `test_commit_confirmation_and_recipe_link` um 200 %-Zoom-Param erweitern oder explizit als bewusste Ausnahme im WP festhalten. |

## Geprüft und in Ordnung

**1. Migration / Schema / Pins**

- `database/migrations/0026_v28_to_v29.sql:4` — Spalte `imported_result jsonb`; öffentliches Verb `commit_recipe_import_batch_v29`, private Helper `recipe_import_head_source_v29` / `recipe_import_recipe_payload_v29`.
- `database/migrations/0026_v28_to_v29.sql:207-212` und `database/permissions.sql:324-329` — REVOKE ALL + GRANT EXECUTE nur `commit_recipe_import_batch_v29` an `cafeteria_app`; Muster wie 0025.
- `reference_scaffold/cafeteria/db.py:22,61` — `SCHEMA_VERSION = 29`, Pin `(29, '0026_v28_to_v29.sql')`; `schema_migrations`-Eintrag über `db.py:189-200`.
- `database/schema.sql:5752,6214-6367` — Canonical enthält Spalte und Funktionskörper gleichlautend zur Migration.
- `database/validate_schema.py:702,729` und `tools/validate_package.py:138` — Schema 29, Checksum `9740215a…` für `0026_v28_to_v29.sql`; Pins 0001–0025 statisch vorhanden (Git-Diff 79b3fe9..HEAD wegen RTK-Ablehnung nicht ausgeführt, stattdessen Pin-Tabelle und Autorbericht).

**2. Atomarität / Replay / Immutability**

- `reference_scaffold/cafeteria/recipe_import_store.py:292-293` — genau ein `engine.begin()` pro Commit; kein Loop über `recipe_store.create_recipe`.
- `database/migrations/0026_v28_to_v29.sql:178` — `create_recipe_v22` in derselben PL/pgSQL-Funktion/TX.
- `reference_scaffold/tests/test_recipe_import_commit_db.py:169-199` — letzter Zeilenfehler rollt Snapshot vollständig zurück.
- `reference_scaffold/tests/test_recipe_import_commit_db.py:238-244` — Replay nach `imported` → 409, kein zweiter Write.
- `database/schema.sql:5809-5810` — Trigger `recipe_import_protect_v28`: Batch nach `imported` unveränderlich.

**3. Sperrreihenfolge (SDD §4.6, REC-004)**

- `database/migrations/0026_v28_to_v29.sql:68-69` — Actor (`require_master_data_actor` → Rollen/Users FOR SHARE in `schema.sql:3340-3341`) → Standort.
- Kein Graphlock (keine Pin-/Freeze-Aktion) — SDD-konform.
- `database/migrations/0026_v28_to_v29.sql:107-125` — Units → Tags (Vokabular) → Storage → Food → Recipe (FOR UPDATE, skip) → Batch FOR UPDATE; innerhalb jeder Klasse `ORDER BY id`.

**4. Entscheidungen / Quellen**

- `create_new`: `test_recipe_import_commit_db.py:108-137` — Version 1, `recipe.create` + `recipe.import`, Batch-Audit `recipe.import_batch`.
- `skip_existing`: `test_recipe_import_commit_db.py:267-305` — stale/archiviert/fremd → 409 ohne Teilwrite; Headsource unverändert (`234-236`).
- File `BatchUUID:row` + Hashnotiz: `test_recipe_import_commit_db.py:122-125`.
- URL/AI Ursprung: `test_recipe_import_commit_db.py:368-410`.
- Kein Update bestehender Head-/Zeilenquellen.

**5. Authz / Sicherheit**

- `reference_scaffold/cafeteria/recipe_import_store.py:296` und `admin/recipe_import_routes.py:194` — Capability `recipe.import`; Editor → 403 (`test_recipe_import_commit_db.py:146-166`, `test_recipe_import_routes.py:129-151`).
- CSRF: `recipe_import_routes.py:196`.
- Signierter Hash: SQL `134-136`, Route `206`.
- Parametrisierte SQL-Aufrufe im Store; private Helper ohne App-EXECUTE (`test_rec_import_commit_migration_db.py:80-110`).
- Kein Publikations-/Allergenreview-Write (`test_recipe_import_commit_db.py:129-137`).

**6. Vollständigkeit / Fehlerabbildung §4.8**

- Unresolved Food/Menge/Unit → P1901, Batch bleibt draft (`test_recipe_import_commit_db.py:308-332`).
- `recipe_commands.py:24-26` — P1901/P1902/55000/42501 gemappt.

**7. Eigene Tests**

- `test_recipe_import_commit_db.py` — alle sechs Akzeptanzszenarien abgedeckt.
- `test_rec_import_commit_migration_db.py` — Upgrade/Restore/ACL (2 Tests).
- Routen/Browser: Commit-Flow, 403, Links (`test_recipe_import_routes.py:92-151`, `test_recipe_import_browser.py:104-157`); Viewports 1440/390 + 1024/768/1920; NoJS-Param; `targets()` ≥48 px.

**8. UI**

- `rezepte_import.html:5-8,125-139` — `page_header`, Tabler `card`/`btn btn-primary`, Objekt (UUID, Version) und Konsequenz benannt; NoJS-Hinweis; Editor ohne Capability sieht Hinweis statt Button.

**9. Besitzgrenzen**

- Statische Referenz-Suche: Commit-Artefakte nur in owned_files (`schema.sql`, `permissions.sql`, `0026_v28_to_v29.sql`, `db.py`, `recipe_import_store.py`, `recipe_import_routes.py`, `rezepte_import.html`, Commit-Tests, `validate_schema.py`, `validate_package.py`). Keine Änderung an `recipe_store.py`, keine neuen Rezeptverben.

**10. Statische Qualität (Autorbericht)**

- Ruff/Mypy grün; `git diff --check` sauber.

## Nicht geprüft

- Eigene Gate-Läufe (RTK/Pool-Wrapper in dieser Session nicht ausführbar); Bewertung anhand Autorbericht und statischer Code-/Testanalyse.
- `rtk git diff 79b3fe9..HEAD` / `--stat -- database/migrations` (RTK-Ablehnung).
- `validate_schema.py --live`, volle `tests/`-Suite, `gitleaks detect`, PG18/Restore-Imagewechsel.
- Manuelle Kontrast-/Fontload-Prüfung; OCR (Autor: `OCR: FAILED (429)`).
- GitNexus `impact`/`detect_changes` live (Worktree nicht indexiert; Autor: LOW auf `SCHEMA_VERSION`).

WAVE-REVIEW: FINDINGS(3)
