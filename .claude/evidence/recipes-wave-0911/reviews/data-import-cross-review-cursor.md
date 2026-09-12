# Cross-Vendor-Review: MP-REC-DATA-IMPORT (wp-rec-data-import-0912)

| Feld | Wert |
|---|---|
| **Branch** | `feat/rec-data-import-0912` |
| **HEAD** | `625d8b3` (laut Autorbericht) |
| **Basis** | `1fff037` (integrate/recipes-0911, Schema 29) |
| **Reviewer-Modell** | composer-2.5 (Ersatz für agy) |
| **Autor-Modell** | composer-2.5 |
| **Worktree** | `/nvmetank1/projects/menuplan/.claude/worktrees/rec-data-import-cursor-0912` |
| **Modus** | read-only, keine Dateiänderungen |

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---:|---|---|---|---|
| 1 | `tools/build_recipe_draft_import.py:1-494` | Tool-Modul hat 494 Zeilen und überschreitet den Prüfpunkt-Grenzwert von 400 Zeilen. | minor | Mit Root klären oder in kleinere Hilfsmodule aufteilen (z. B. `translate` / `apply` / `pin`). |
| 2 | `tools/build_recipe_draft_import.py:444-449` | `apply_import` prüft Batch-Ergebnisse nicht: bei `commit_group`→`status: conflict` läuft `pin_prepared_foods` trotzdem weiter; kein Abbruch, keine Fehlerausgabe an den Aufrufer. | minor | Vor dem Pin-Schritt `summary['batches']` auf `imported`/`skipped` prüfen; bei `conflict` abbrechen und melden. |
| 3 | `tools/build_recipe_draft_import.py:127-196` | `translate_draft` validiert `base_unit_code`/`unit_code` nicht gegen `existing_unit_codes` des Entwurfs. | minor | Beim Übersetzen Assert/Validierung gegen `draft['existing_unit_codes']` ergänzen. |

## Geprüft und in Ordnung

**1. Datenwahrheit / Entwurf unverändert (indirekt)**

- Das Tool liest den Entwurf nur (`DRAFT_PATH`, `load_draft` Z. 16–17, 31–32) und schreibt ausschließlich `linked_recipe_drafts_import.json` (`write_import` Z. 199–200).
- `demo/linked_recipe_drafts_import.json` trägt `source_draft_sha256` in `meta` (Z. 6).
- Zähler im Entwurf: 100 Foods (`"key": "draft.food.` → 100 Treffer), 61 Rezepte (29×`"role": "preparation"` + 32×`"role": "dish"`), 32 `dish_mappings` (32×`"source_occurrences"`-Arrays), 29 `preparation_recipe_key`-Foods.
- Import-JSON: gleiche Food-/Rezept-/Mapping-Anzahl; `dish_mappings` wird 1:1 kopiert (`translate_draft` Z. 189).
- Stichprobe Pouletbrust: Name, `base_unit_code` G, Lager `proposed.storage.kuehlraum` stimmen zwischen Entwurf und Import überein (`demo/linked_recipe_drafts.json:63-68` vs. `demo/linked_recipe_drafts_import.json:47-52`).
- `recipe_payload` enthält Annotationen nur in `source.note`, nicht als Top-Level-Keys (Beispiel Apfelmus Z. 1666–1671); erlaubte Top-Level-Keys sind `title`, `description`, `servings`, `servings_unit_code`, `prep_minutes`, `cook_minutes`, `source`, `ingredients`, `steps`, `tag_public_ids`, `images`.

**2. Foundations zuerst**

- Lagerorte über `masters.create_vocabulary` / Namenslookup (`ensure_storage` Z. 230–250), keine direkten SQL-Writes im Tool.
- Foods ausschließlich über `masters.create_food` / `replace_food_storage_locations` (`ensure_foods` Z. 253–284).
- UUID-Zuordnung in `resolved.food_keys` / `resolved.storage_keys` mit Write-back nach `--apply` (`apply_import` Z. 450–451; Import-JSON-Schema Z. 10839–10844 leer im committed Artefakt, befüllt zur Laufzeit).
- Basiseinheiten stammen unverändert aus dem Entwurf (`item['base_unit_code']` Z. 149, 268); Entwurf nutzt nur Codes aus `existing_unit_codes` (Z. 30–39 im Entwurf).

**3. Import / Batches / Annotationen**

- Zwei getrennte Gruppen `preparation` / `dish` (`batch_group` Z. 167; Schleife Z. 444–448).
- `adapter_kind: ai_assisted`, `duplicate_decision: create_new` via `mapped_rows` Z. 294.
- Annotationen `unreviewed`/`proposed_not_measured`/`allergen_not_checked` als Batch-Metadaten (`ANNOTATIONS` Z. 18; `batch_payload` Z. 224; `update_batch` Z. 337), plus sichtbare `source.note` (Z. 78–83, 1670).
- Keine Publikationswrites im Tool (kein `publish`/`publication`-Bezug in `build_recipe_draft_import.py`).
- Test prüft: keine Änderung an `publication_revisions`, `allergen_reviews == 0`, `allergen_review_status == not_checked` (`test_recipe_data_import_db.py:121-122, 115-120`).

**4. Prepared-Pins (bewusst, getrennt — zulässig)**

- Freeze/Pin ist **kein** Nebeneffekt von `commit_batch`: eigene Phase `pin_prepared_foods` **nach** beiden Batches (`apply_import` Z. 444–449).
- Expliziter `recipes.freeze_revision` mit `expected_dependency_hash` (Z. 390–393), danach Pin über `update_food` mit `prepared_recipe_revision_public_id` + `prepared_recipe_content_hash_sha256` (Z. 402–410) — exakte Revisions-UUID + Hash, keine Latest-Auswahl.
- Bottom-up-Reihenfolge über `bottom_up_order` (Z. 58–69) und Erhalt in `document['recipes']`.
- Bereits gepinnte Foods werden übersprungen (Z. 375–380, 399–401).
- Test: Prep-Rezepte `row_version == 2` (nach Freeze), Gerichte `== 1` (Z. 106–107); 29 Foods mit `prepared_recipe` (Z. 115–119).
- Entspricht SDD §8.11 (`recipes-sdd.md:1231-1235`): bewusster v27-Pfad nach Import, kein Auto-Freeze beim Commit.

**5. Idempotenz / Atomarität**

- Zweiter Lauf: Batches `skipped` via `resolved.batch_public_ids` (Z. 309–313); Test bestätigt DB-Snapshot-Gleichheit (`test_recipe_data_import_db.py:125-132`).
- Fehler in einer Zeile rollt Batch zurück: dedizierter Test mit `RecipeValidationError` und unverändertem Snapshot (`test_recipe_data_import_db.py:135-187`).
- DB-URL nur per `--database-url` / `DATABASE_URL` (Z. 475–478); kein Hardcoding.
- `--dry-run` ohne `--apply` schreibt nichts (Z. 425–436, 472–474).

**6. Sicherheit**

- Store-APIs mit Capability-Guards: `create_food`/`create_vocabulary` → `masterdata.write`, `create_batch`/`update_batch` → `recipe.write`, `commit_batch` → `recipe.import` (`master_data_store.py:51,99`; `recipe_import_store.py:252-253,296-297`).
- Actor `Cafeteria.Admin` im CLI (`build_recipe_draft_import.py:486`); Test-Fixture `Cafeteria.Publisher` hat `recipe.import` + `masterdata.write` (`roles.py:14-19`).
- Keine SQL-Verkettung im Tool; keine Secrets in Owned-Dateien sichtbar.

**7. Tests / Gates (Code-Review, nicht neu ausgeführt)**

- Owned-Testdatei: 3 Tests — Vollpipeline, Idempotenz, Batch-Rollback (`test_recipe_data_import_db.py:73,125,135`).
- Deckung der Akzeptanzkriterien in diesen 3 Tests: Zähler 3/100/61/32/76, getrennte Batches, Annotationen, Pins, keine Publikation/Allergenfreigabe.
- Autorbericht: Gate-Suite 21 passed, ruff/mypy grün — **nicht eigenständig verifiziert** (s. unten).

**8. Besitzgrenzen (indirekt)**

- Autorbericht: 2 Commits, nur `tools/build_recipe_draft_import.py`, `demo/linked_recipe_drafts_import.json`, `reference_scaffold/tests/test_recipe_data_import_db.py`.
- `recipes-wps.json` owned_files stimmen überein (Z. 6157–6160).
- Verbotene Pfade (`linked_recipe_drafts.json`, `recipe_import_store.py` etc.) nicht im Tool geändert.

## Nicht geprüft

- **Alle `rtk`-Shell-Aufrufe abgelehnt** (u. a. `rtk git diff`, `rtk python3`, `rtk pgrep`, `rtk wc`) — RTK-Vertrag im Reviewer-Lauf nicht ausführbar.
- Byteweiser `git diff 1fff037..HEAD -- demo/linked_recipe_drafts.json` (Prüfpunkt 1 explizit).
- Vollständiger `git diff --stat` gegen Basis (Prüfpunkt 8).
- Eigenständiger SHA-256-Abgleich Entwurf ↔ `meta.source_draft_sha256`.
- Eigenständiger pytest/ruff/mypy-Gate-Lauf auf dem Pool.
- Summe 76 `source_occurrences` per Skript (Autor + Test-Assertion übernommen; Struktur mit 32 Mapping-Einträgen plausibel).
- Browser/UI, gitleaks, GitNexus `detect_changes`.

## Gesamtbewertung

Die Implementierung folgt dem WP-Vertrag und der SDD §8.11 eng: Foundations-first, getrennte `ai_assisted`-Batches, Annotationen korrekt ausgelagert, Prepared-Pins als bewusste Nachphase mit exakter Revisionswahl. Die drei Befunde sind minor und blockieren die Übernahme nicht; Punkt 2 sollte vor Produktions-Replays ohne `resolved`-Block gehärtet werden.

WAVE-REVIEW: FINDINGS(3)
