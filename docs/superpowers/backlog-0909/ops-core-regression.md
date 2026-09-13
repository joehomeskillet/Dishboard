# OPS-001 Kernregression — MP-OPS-CORE-REGRESSION

Stand: 13. September 2026. Keine OPS-Neuimplementierung.

Historischer Cursor-Lauf auf unveränderten Tests: **9 FAIL, kein Runtime-PASS.**
Korrektur durch unabhängigen Autor (Grok) auf denselben zwei Admin-Modulen: siehe Abschnitt «Korrektives Gate».

## Quelle

| Feld | Wert |
|---|---|
| MP-ID | `MP-OPS-CORE-REGRESSION` |
| Historisches wp-ID | `wp-0550a6f132cf` (Cursor, Dokumentation des 9-FAIL-Laufs) |
| Korrektur-wp-ID | `wp-e5ff3dfa8ab0` (Grok) |
| Historische Lane | Cursor |
| Korrektur-Lane | grok-build |
| Historischer Worktree | `/nvmetank1/projects/menuplan/.claude/worktrees/ops-regression-cursor-0913` |
| Korrektur-Worktree | `/nvmetank1/projects/menuplan/.claude/worktrees/ops-gatefix-grok-0913` |
| Korrektur-Branch | `test/ops-gatefix-grok-0913` |
| Historische Basis | `a6337e66198a7c2da80862e3c9b68aff1d8de362` |
| Korrektur-Basis | `d4ad17958f3874dd704f882c106ee21340baa5c1` plus Cherry-Pick `267f2ae1f18c28359e9d698e13afc1cea69389e6` |
| Pool | `test_ui_other` — PostgreSQL `127.0.0.1:32853/menuplan_test_ui_other`, Redis `32854` |
| Container | `menuplan-orch-test_ui_other-pg16` |
| Wrapper | `/nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test_ui_other-gate.sh` |

Vertragsanker unverändert gelesen: `operations_settings.py` (save_schedule/save_area_name/save_weekend_switch), `operations_store.py` (list_service_exceptions/load_dated_service), `admin/operations_routes.py` (operations_settings), [OPS-001 SDD](../../design/2026-09-06-ops-bereiche-zeiten-sdd.md). Codeexistenz allein ist kein Gate.

### Schema (Korrektur)

OPS-001 landete historisch in Schema 20 (`database/migrations/0017_v19_to_v20.sql`, Betriebszeiten und geschützte Bereichsnamen). Das ist die Migrationsversion der Fachfunktion, nicht die aktuelle produktive Schemaversion.

Aktueller Quellvertrag in diesem Checkout: `SCHEMA_VERSION = 30` und `APPLICATION_VERSION = 'dishboard-schema-v30'` in `reference_scaffold/cafeteria/db.py`; `database/validate_schema.py` verlangt Live-`max(version)` gleich 30. Belegter Schema-30-Release laut [Korrekturwellen-Lieferstand](../../design/2026-09-12-correction-wave-delivery.md) (`35da76c`, Ready meldet Schema 30). **«Schema 20 produktiv» ist für den aktuellen Deploy falsch.**

## Synthetische Regression (wp-0550a6f132cf, Cursor)

Dateien laut `test_plan`, unverändert, ein Lauf auf zugewiesenem Pool:

```
tests/test_operations_settings_db.py
tests/test_operations_weekend_db.py
tests/test_admin_operations_routes.py
tests/test_admin_operations_browser.py
tests/test_public_ops_areas_times.py
tests/test_signage_ops_areas_times.py
tests/test_week_pdf_ops.py
```

Befehl (Root-Zuweisung):

```
rtk bash /nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test_ui_other-gate.sh \
  /nvmetank1/projects/menuplan/.claude/worktrees/ops-regression-cursor-0913 \
  -q -p no:cacheprovider -p no:randomly --basetemp=/tmp/dishboard-ops-cursor-0913 \
  tests/test_operations_settings_db.py tests/test_operations_weekend_db.py \
  tests/test_admin_operations_routes.py tests/test_admin_operations_browser.py \
  tests/test_public_ops_areas_times.py tests/test_signage_ops_areas_times.py \
  tests/test_week_pdf_ops.py
```

Ergebnis 2026-09-13:

```
157 passed, 9 failed in 271.14s (0:04:31)
GATE_EXIT=1
cwd=/nvmetank1/projects/menuplan/.claude/worktrees/ops-regression-cursor-0913/reference_scaffold
```

### Bestanden (157)

Datenbank-, Public-, Signage- und Wochen-PDF-Verbraucher liefen grün: `test_operations_settings_db.py`, `test_operations_weekend_db.py`, `test_public_ops_areas_times.py`, `test_signage_ops_areas_times.py`, `test_week_pdf_ops.py`.

### Fehlgeschlagen (9) — Admin-Routen und Browser

| Test | Befund |
|---|---|
| `test_admin_operations_routes.py::test_get_authorization_csrf_and_shape` | HTML enthält nicht mehr den erwarteten Text `Zeiten in Europe/Zurich`. |
| `test_admin_operations_routes.py::test_weekend_editor_links_defaults_and_existing_services_survive_switch_off` | Wochenübersicht fehlt `14 Menükarten · 7 Tage`. |
| `test_admin_operations_routes.py::test_loaded_exception_retains_original_location_expectation` | 409-Text lautet `Berechtigung oder aktiver Standort wurde zwischenzeitlich geändert.` statt erwartet `Der aktive Standort wurde zwischenzeitlich geändert.` |
| `test_admin_operations_browser.py::test_native_operations_controls_save_focus_and_original_exception` (6 Varianten: 390/820/1440 × JS an/aus) | `#allows_weekend` nicht sichtbar/klickbar (`TimeoutError`: Element in `<details>` oder versteckt). |

Diese neun Fehler deuten auf Drift zwischen unveränderten Tests und der aktuellen Admin-Oberfläche auf `a6337e6` hin (u. a. UI-Korrektur mit `<details>`-Editoren und geänderten Fehlermeldungen). **Kein Produktcode in diesem WP geändert; keine Testanpassung durch diesen Lane-Lauf.**

### Vergleich früherer Beleg

Auf Freeze-Pool `32845/32846` und älterer Basis `b4b9dfaa` lief dieselbe Testmenge 2026-09-09 laut Cursor-Bericht zweimal `166 passed`, `GATE_EXIT=0`. Der historische relative Pfad `../../../ops-core-regression-0909/docs/superpowers/backlog-0909/ops-core-regression.md` ist in diesem Checkout nicht vorhanden (kein Worktree/Dateibaum `ops-core-regression-0909`); es wird kein Ersatzlink erfunden. Der Cursor-Lauf auf `a6337e6` / `test_ui_other` bleibt **9 FAIL** und wird durch den späteren Korrekturlauf nicht umgeschrieben.

## Getrennt: fachliche Abnahme

Datierte Feiertags-/Betriebsferienfälle in Admin/Public/Signage/HTML-Druck/Wochen-PDF/API bleiben `MP-OPS-DATED-EXCEPTION-ACCEPTANCE` (`AWAITING_EXTERNAL`: benannter echter Fall, Abnahmeperson, zugewiesene Umgebung). Synthetische Tests ersetzen das nicht.

`test_capture_ops_live_proof.py` steht in der SDD-Liste, nicht im JSON-`test_plan`; **nicht gelaufen**. Live-Proof, Yodeck-Player und Küchendruck sind kein Runtime-PASS dieses Pakets.

Profilschutz «genau zwei Keys, Rename ändert keine technischen Schlüssel» bleibt `MP-OPS-NO-THIRD-AREA` (hängt am Kernregressionsgate; eigener Regressionsbeleg offen, bis Root das Sieben-Modul-Sprintgate unabhängig wiederholt).

## Korrektives Gate (wp-e5ff3dfa8ab0, Grok)

Unabhängiger Autor, nicht Cursor. Produktcode unverändert (read-only). Die neun Fehler waren Drift gegen die genehmigte Admin-UI, kein gebrochenes Fachverhalten:

| Test | Produktverhalten | Testkorrektur |
|---|---|---|
| `test_get_authorization_csrf_and_shape` | Übersichtsfuss `Zeitzone: {{ timezone }}` (`operations.html`), Standort `Europe/Zurich` | Semantische Zeitzone aus aktiver Location im Overview, nicht der alte SDD-Satz `Zeiten in Europe/Zurich` |
| `test_weekend_editor_links_defaults_and_existing_services_survive_switch_off` | Cafeteria-Raster: 7 Tageskarten, 14 `menu-slot`, Hinweis «Wochenendbetrieb: Samstag und Sonntag sind im Raster.» | Positives Raster (Tage, Slots, Hinweis); nach Abschalten Samstag bleibt, Sonntag entfällt |
| `test_loaded_exception_retains_original_location_expectation` | `workflow_scope.py`: `Berechtigung oder aktiver Standort wurde zwischenzeitlich geändert.` | 409, `no-store`, kombinierte Meldung, keine `menu_services`-Zeile |
| `test_native_operations_controls_save_focus_and_original_exception` (6) | `#allows_weekend` und Folgeformulare liegen in nativen `<details>` | Summary öffnen, dann Schalter/Raster/Ausnahme/Fokus/JS-NoJS unverändert |

Guard-Assertions (Authz, CSRF, CAS, Standortwechsel, Wochenend-URLs, Autofokus, Outline) bleiben.

Befehl (Root-Zuweisung, nur die zwei Admin-Module; die übrigen 157 Checks dieses Pakets nicht erneut durch den Worker):

```
rtk bash /nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test_ui_other-gate.sh \
  /nvmetank1/projects/menuplan/.claude/worktrees/ops-gatefix-grok-0913 \
  -q -p no:cacheprovider -p no:randomly --basetemp=/tmp/dishboard-ops-grokfix-0913 \
  tests/test_admin_operations_routes.py tests/test_admin_operations_browser.py
```

Ergebnis 2026-09-13:

```
31 passed in 63.63s (0:01:03)
GATE_EXIT=0
cwd=/nvmetank1/projects/menuplan/.claude/worktrees/ops-gatefix-grok-0913/reference_scaffold
```

Das ersetzt nicht den historischen 9-FAIL-Beleg und nicht das vollständige Sieben-Modul-Sprintgate durch Root.

## Grenzen

- Historischer Cursor-Lauf: kein OPS-Codediff, kein Testfix, kein Deploy, kein Merge; 9 FAIL bleibt dokumentiert.
- Korrektur-WP: nur die drei Besitzdateien (zwei Admin-Tests + dieses Dokument). Kein Produktcodediff, kein Push/Merge/Deploy.
- Vollständige sieben OPS-Module und Paketvalidator bleiben Root-Sprintgate.
- Pool `test_ui_other` nach Cursor-Lauf durch Root freigegeben, danach exklusiv an wp-e5ff3dfa8ab0 vergeben; nach diesem Korrekturgate wieder freigegeben.
