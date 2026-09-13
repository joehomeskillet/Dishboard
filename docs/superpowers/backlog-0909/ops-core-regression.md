# OPS-001 Kernregression — MP-OPS-CORE-REGRESSION

Stand: 13. September 2026. Keine OPS-Neuimplementierung. **Kein Runtime-PASS.**

## Quelle

| Feld | Wert |
|---|---|
| MP-ID | `MP-OPS-CORE-REGRESSION` |
| wp-ID | `wp-0550a6f132cf` |
| Lane | Cursor |
| Worktree | `/nvmetank1/projects/menuplan/.claude/worktrees/ops-regression-cursor-0913` |
| Branch | `docs/ops-regression-cursor-0913` |
| Basis / Quellrevision | `a6337e66198a7c2da80862e3c9b68aff1d8de362` |
| Pool | `test_ui_other` — PostgreSQL `127.0.0.1:32853/menuplan_test_ui_other`, Redis `32854` |
| Container | `menuplan-orch-test_ui_other-pg16` |
| Wrapper | `/nvmetank1/projects/menuplan/.claude/state/handover-2026-09-05/worker-test_ui_other-gate.sh` |

Vertragsanker unverändert gelesen: `operations_settings.py` (save_schedule/save_area_name/save_weekend_switch), `operations_store.py` (list_service_exceptions/load_dated_service), `admin/operations_routes.py` (operations_settings), [OPS-001 SDD](../../design/2026-09-06-ops-bereiche-zeiten-sdd.md). Schema 20 produktiv. Codeexistenz allein ist kein Gate.

## Synthetische Regression (dieses WP)

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

Auf Freeze-Pool `32845/32846` und älterer Basis `b4b9dfaa` lief dieselbe Testmenge 2026-09-09 zweimal `166 passed`, `GATE_EXIT=0` ([ops-core-regression-0909](../../../ops-core-regression-0909/docs/superpowers/backlog-0909/ops-core-regression.md)). Der aktuelle Lauf auf `a6337e6` / `test_ui_other` ist **nicht** PASS und ersetzt keinen Runtime-Nachweis.

## Getrennt: fachliche Abnahme

Datierte Feiertags-/Betriebsferienfälle in Admin/Public/Signage/HTML-Druck/Wochen-PDF/API bleiben `MP-OPS-DATED-EXCEPTION-ACCEPTANCE` (`AWAITING_EXTERNAL`: benannter echter Fall, Abnahmeperson, zugewiesene Umgebung). Synthetische Tests ersetzen das nicht.

`test_capture_ops_live_proof.py` steht in der SDD-Liste, nicht im JSON-`test_plan`; **nicht gelaufen**. Live-Proof, Yodeck-Player und Küchendruck sind kein Runtime-PASS dieses Pakets.

Profilschutz «genau zwei Keys, Rename ändert keine technischen Schlüssel» bleibt `MP-OPS-NO-THIRD-AREA` (hängt an diesem Gate; eigener Regressionsbeleg offen solange Kernregression FAIL).

## Grenzen

- Kein OPS-Codediff, kein Testfix, kein Deploy, kein Merge.
- Gate-FAIL ist dokumentierter Ist-Stand; MP-OPS-CORE-REGRESSION bleibt ohne grünes Regressionsgate auf dieser Revision.
- Pool `test_ui_other` nach Gate-Laufende durch Root freigegeben (exklusive Zuweisung wp-0550a6f132cf beendet).
