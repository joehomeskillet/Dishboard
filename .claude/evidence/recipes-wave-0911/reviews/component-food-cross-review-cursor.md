# Cross-Vendor-Review — MP-REC-COMPONENT-FOOD-UI (wp-component-food-ui-0911)

| Feld | Wert |
|---|---|
| **Branch** | `feat/rec-component-food-0911` |
| **HEAD** | `dfca95b` (`feat(components): bind catalog foods in the component editor`) |
| **Basis** | `f2b3102` (integrate/recipes-0911, Schema 28) |
| **Reviewer** | cursor / composer-2.5 |
| **Autoren** | codex gpt-6-astra (Entwurf), grok-4.6 (Abschluss) |
| **Autorbericht** | `/nvmetank1/projects/rag-stack/.claude/reports/wp-component-food-ui-0911.md` |

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | `reference_scaffold/cafeteria/templates/admin/component_editor.html:52-61` | Lebensmittel-Select ist ein Roh-`<select>` (wie Kategorie), nicht das im Auftrag genannte `select`-Makro aus `_macros.html`. Bewusst so dokumentiert (kein `select`-Makro vorhanden); funktional korrekt, leichte Abweichung vom Briefwortlaut. | minor | Beim Merge mit MP-UI-REF-FORM auf gemeinsames Select-Makro umstellen, sobald verfügbar. |
| 2 | `reference_scaffold/cafeteria/component_catalog_store.py:489-493` | Bestehende Zuordnung zu einem **archivierten** Lebensmittel: Jeder Speichervorgang schlägt fehl (`active`-Prüfung nach Lock), auch wenn `food_public_id` unverändert bleibt und nur Name/Kategorie/Herkunft/Labels geändert werden. Aktive Foods: bytegleiche Zuordnung korrekt ohne Bump (getestet). | minor | Entweder dokumentieren („archivierte Zuordnung zuerst ablösen“) oder in `_lock_assignment_foods` bei `new_id == current_food_id` die Active-Prüfung überspringen, solange keine Änderung beabsichtigt ist. |
| 3 | `reference_scaffold/cafeteria/templates/admin/component_editor.html:49-76` | Food-Block ist lokal eingefügt; Template-Stand liegt **vor** MP-UI-REF-FORM (Makro-Referenzseite). Diff ist gut lokalisierbar und sollte beim Integrationsmerge ohne Konflikt mit Kategorie/Herkunft-Block übertragbar sein. | minor | Beim Merge Food-Block in den REF-FORM-Stand übernehmen, nicht blind rebasen. |

## Geprüft und in Ordnung

### 1. Writer (`component_catalog_store.py`)

- **Eine Transaktion:** `update_component` nutzt `write_transaction` → `begin_menu_binding_write_v26` (`workflow_write_context.py:51-55`, `component_catalog_store.py:284`).
- **Sperrreihenfolge:** Zuerst Komponente `FOR UPDATE` (`_lock_component`, Z. 390-418), danach `lock_component_foods_v26` (`_lock_assignment_foods`, Z. 477-483). Kommentar Z. 291 verweist auf `component_binding_state.py:146-151`; dort werden Food-IDs sortiert gelockt — hier ebenfalls `sorted({...})` (Z. 472-474). Keine neue Deadlock-Gefahr gegenüber dem bestehenden Binding-Writer erkennbar.
- **UPDATE + Versionsbump:** `food_id` im selben `UPDATE` mit `row_version + 1` (Z. 307-327).
- **Beleg:** Genau ein `record_component_food_write_v26` nur bei `food_changed` (Z. 329-334); `before`/`after` = erwartete Version / neue Version (+1).
- **Unverändert:** Early return ohne Bump/Beleg (Z. 302-303); DB-Test `test_catalog_food_writer_roundtrip_receipt_and_rejects` (Z. 228-232) belegt bytegleiche Zuordnung.
- **Validierung:** Nur aktive Foods desselben Standorts; archiviert/fremd/unbekannt → `ComponentCatalogValidationError` mit `field_name='food_public_id'` (Z. 467-493); kein Teilwrite (Rollback via Transaktion).
- **Read-Pfad additiv:** `get_component`/`find_components` liefern `food_public_id`/`food_name` per `LEFT JOIN` (Z. 175, 245); `component_catalog_metadata.py:113-114` mappt additiv; bestehende Schlüssel unverändert.
- **SQL parametrisiert:** Alle neuen Queries nutzen Bound Parameters.

### 2. Parser (`workflow_partial_form.py`)

- Optionale Felder `food_public_id`, `food_detach_confirm` (Z. 536); keine weiteren neuen Felder (`_validate_shape` Z. 533-537).
- `food_public_id` leer erlaubt; Ablösen nur mit `food_detach_confirm` wenn `current_food_public_id` gesetzt (Z. 554-558).
- UUID-Validierung (Z. 547-551); fehlender `food_public_id`-Schlüssel = unverändert (Z. 196-197 im Test).
- Bestehende Pflichtfelder/Fehlertexte unverändert.

### 3. Routen/Render (`workflow_routes.py`, `rendering.py`)

- Geändert nur im Komponentenpfad: `component_detail` (Z. 732-747), `component_update` (Z. 749-770), `_component_error_response` (Z. 662-682).
- Foodliste einmal je Render via `_active_location_foods()` in `render_component_detail` (Z. 220-241, 245).
- Fehlerpfad: Eingaben (`form_values`) und `_csrf` aus `request.form` erhalten (Z. 665, 680-681); 409 bei CAS-Konflikt (`StaleComponentError`/`WriteConflictError`, Z. 682).
- `draft.write`, CSRF-Validierung (`_validate_scoped_csrf`), Scope, CAS (`row_version`) unverändert im Vertragsfluss.

### 4. Editor/Liste (Templates)

- Select mit Leeroption „Kein Lebensmittel“ (Z. 54); aktuelle Zuordnung Name + UUID (Z. 65-68); Link zu `master_data_detail` wenn Route existiert (Z. 66).
- Ablösen: Checkbox-Makro `check` mit Objekt + Konsequenz (Z. 72); Fehlerfokus `#c-food` / `#c-food-detach` (Z. 20).
- NoJS-Test `test_component_food_selection_nojs` (Z. 367-420).
- Liste: „Lebensmittel: …“ / „kein Lebensmittel“ (`components.html:167`); keine erfundenen Statuswerte.
- Touch-Ziele: `_assert_component_controls_fit` prüft ≥ 48 px (bestehende Schwelle, ≥ 44 px Anforderung erfüllt).

### 5. Allergene/Herkunft/Labels

- Keine Änderungen an `component_effects.py` oder `master_data_*.py` (nur Read via `list_foods`).
- Tests belegen Erhalt von Labels/Allergenen/Herkunft nach Food-Bindung und -Ablösung (`test_catalog_food_writer_roundtrip_receipt_and_rejects` Z. 221-223, 256-257; Browser-Test Z. 307-308).
- Hinweistext: keine Allergenübernahme (`component_editor.html:62`).

### 6. Tests

- Neu: `test_component_food_selection_browser.py` — Parser, DB-Writer, Browser-Roundtrip, Detach-Bestätigung, CAS-409, Viewports, NoJS, Screenshots.
- Angepasst: `test_component_catalog_*`, `test_admin_form_contracts.py` (Fixtures mit `food_public_id`/`food_name`); `OUTPUT_KEYS`/`FULL_KEYS` erweitert, keine Assertions abgeschwächt.
- v27-Lagerort: `_insert_location_food` legt `storage_locations` + `food_storage_locations` an (Z. 62-115).
- Akzeptanzkriterien einzeln in Tests belegt (siehe Autorbericht Gates 205 passed / 85 passed, skipped 0).

### 7. Besitzgrenzen

- Geänderte Dateien gemäß Autorbericht: Store, Metadata, Parser, `rendering.py`, `workflow_routes.py`, zwei Templates, fünf Testdateien — alles innerhalb Root-Lease aus `recipes-wps.json` → MP-REC-COMPONENT-FOOD-UI.
- Mypy-Altlasten (`RowMapping`/`int(object)`) im Autorbericht dokumentiert; `_lock_assignment_foods` nutzt `type(food_id) is int` statt neuem `int(object)`.

## Nicht geprüft

- **RTK/Git:** `rtk git diff --stat f2b3102..HEAD` und `rtk git log` in dieser Session nicht ausführbar (RTK-Aufruf abgelehnt); Dateiumfang anhand Autorbericht und Quellcode-Lektüre verifiziert.
- **Gate-Neulauf:** pytest 205/85, ruff, mypy, gitleaks, `git diff --check` — nur Autorbericht ausgewertet, nicht selbst gefahren.
- **OCR/Screenshots:** OCR 429 im Autorbericht; Screenshot-Baselines nicht visuell geprüft.
- **GitNexus Impact/Detect:** nicht erneut ausgeführt (Autorbericht referenziert).
- **Live-Browser/Manuelle UI:** nicht ausgeführt.

WAVE-REVIEW: FINDINGS(3)
