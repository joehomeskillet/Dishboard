# WP fix/altlasten-routes-contracts-0919 — Report

Branch: `fix/altlasten-routes-contracts-0919`  
Worktree: `/nvmetank1/projects/menuplan/.claude/worktrees/alt-routes-0919`  
Gate: **225 passed, 0 failed** (`GATE_EXIT=0`)

## Entscheidungen je Fehlerbild

| Fehler | Entscheidung | Beleg |
|--------|--------------|-------|
| CSV 20/18 Spalten (`test_contracts`) | Test veraltet | Header in `csv/menu_*_example.csv`; Cafeteria 20, Patient 18 |
| `(?<!show_)prices` in patienten.html | Test veraltet | `patienten.html` nutzt `{% with show_prices=false %}`; Präzedenz `tools/validate_package.py` |
| `KeyError: 'channels'` (`test_api_key_record`) | Test veraltet | `_record()` erwartet `channels`; Fixture ergänzt |
| schema29-Migration Signatur | Test veraltet | Cutoff `< 30` (v29); v30+ SQL-Signatur anders |
| CSRF 400 statt 409 (`test_operations_scoped_csrf`) | Test veraltet | v2-Token: Raw-Segment Index `[1]`, nicht `[0]` |
| Frontchannel-Logout 400 (`test_access_event_routes`) | Produkt falsch | Lokale Session ohne OIDC-Params → 200 + Clear; Entra ohne Params → 400 |
| Wochenübersicht-Regex / Weekend-Hint | Test veraltet | `admin-week-days`-Layout; 5-Tage-Grid ohne Wochenend-Hinweis |
| Allergen-Hinweis / Zurücksetzen-Link | Test veraltet | Guillemets in `components.html`; Icon vor Linktext erlaubt |
| `icon` macro `class` kwarg | Test veraltet (Stub) | Macro-Stub in `test_capture_ops_live_proof.py` akzeptiert `class` |
| OPS `exceptions_section` | Produkt falsch | Titel in `.card-title`, nicht `h2`; `tools/capture_ops_live_proof.py` |
| GitHub Pages `.menu-board` / data-URLs | Test veraltet + Produkt | `site/responsive.css` ergänzt; Inline-SVG data-URLs erlaubt |
| UI-Matrix fehlende Routen | Inventar nachziehen | `merge_matrix_routes.py`; cost/inventory/order/kitchen/templates |
| Order-Korb 500 | Produkt falsch | `get_basket` ValidationError → 404 in `order_routes.py` |
| Basket/Kitchen-Fixture 404 | Test veraltet | Synthetische Supplier/Basket/Event in `_prepare_inventory_entities` |
| CSV-Screenshot Download-Fehler | Test veraltet | `order_basket_csv` aus Capture-`extra_admin_paths`, bleibt in Role-Probes |
| Density `acceptance` leer | Inventar nachziehen | Merge-Script backfillt `A01` für alle Routen |
| `cost_preview` visual gap | Inventar nachziehen | Coverage-Block `blocked_post_only_html` |

## Geänderte Dateien

**Produkt:** `reference_scaffold/cafeteria/auth/routes.py`, `reference_scaffold/cafeteria/admin/order_routes.py`, `tools/capture_ops_live_proof.py`, `site/responsive.css`

**Tests:** `reference_scaffold/tests/test_*.py` (12 Dateien)

**Inventar:** `docs/superpowers/backlog-0909/ui-route-matrix.json`, `docs/superpowers/backlog-0909/ui-before-manifest.json`, `.claude/evidence/ui-inventory-grok-0909/merge_matrix_routes.py`

## Gate — letzte 15 Zeilen (wörtlich)

```
........................................................................ [ 96%]
.........                                                                [100%]
=============================== warnings summary ===============================
tests/test_access_event_routes.py: 34 warnings
  /tmp/dishboard-shared-venv/lib/python3.14/site-packages/flask_session/base.py:172: DeprecationWarning: The 'use_signer' option is deprecated and will be removed in the next minor release. Please update your configuration accordingly or open an issue.
    warnings.warn(

-- Docs: https://docs.pytest.org/en/stable/how-to/capture-warnings.html
225 passed, 34 warnings in 295.85s (0:04:55)
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/alt-routes-0919/reference_scaffold
```

## Nicht geschafft / nicht ausgeführt

- Kein Push (explizit verboten).
- `tools/validate_package.py` / `tests/test_tabler_package_verification.py` nicht angefasst (fremdes Paket).
- DB-Migrationen unverändert gelassen.
- Browser-Screenshot-Baseline unter `.claude/evidence/**` nicht promoted (`UI_CAPTURE_PROMOTE` nicht gesetzt).
- `gitnexus_detect_changes()` vor Commit nicht ausgeführt (MCP nicht in Worker-Session).
