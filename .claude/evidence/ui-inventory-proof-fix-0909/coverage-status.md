# Abdeckungs- und Statusmatrix — UI-Inventar-Freeze 2026-09-11

## 1. Belegstand

- **Freeze-Commit:** `33d135f861d1fff78deac9f372a051375d410532` (`docs(ui): archive the raw gate and promotion logs of the inventory freeze`)
- **Promotion-Commit:** `0e6a292e3f7c396770a0cb33024e38cd7cef4d4c` (`test(ui): promote the corrected before-screenshot set into the versioned manifest`)
- **Versioniertes Manifest:** `docs/superpowers/backlog-0909/ui-before-manifest.json`
  SHA-256: `ee42bd86e5642835aeeb78f04129e39daab888f182e8664ea0a6a4500a0c16c2`
- **Promotete Manifest-Kopie:** `.claude/evidence/ui-inventory-proof-fix-0909/capture-promoted-0911/ui-before-manifest.json`
  SHA-256: `ee42bd86e5642835aeeb78f04129e39daab888f182e8664ea0a6a4500a0c16c2` (byteidentisch zum versionierten Manifest)
- **Versionierte Matrix:** `docs/superpowers/backlog-0909/ui-route-matrix.json`
  SHA-256: `62dc038032d22d06834ecd601c623ce14431be1b6932be46b6c8c60188de2e18`
- **Aufnahme-Metadaten (`meta` des Manifests):**
  - Aufgenommen durch: Workpackage `wp-d7589450daee`, Lane `claude-code`, Modell `claude-fable-5-1`
  - Status der Identitaet: `caller_supplied`
  - Zeitstempel der Aufnahme: `2026-09-11T14:33:09.136595+00:00`
  - Browser: `playwright-chromium 151.0.7922.34` (Chromium Version 151.0.7922.34)
  - Laufzeit-Umgebung: Playwright `1.58.0`, Python `3.14.4`, Plattform `Linux-7.0.0-31-generic-x86_64-with-glibc2.43`
  - Lokalisierung / Zeitzone / Device Pixel Ratio: `de-CH` / `Europe/Zurich` / `1`
  - Fixture: `status = caller_supplied`, SHA-256: `8e8bee98a50ed8a11bf2193d8bfa11fb5ea57ea2f3fdd48c173278d0cd75bd4f`
  - Schriftdateien: 10 lokale WOFF2/TTF/WOFF-Dateien (4 Fira Sans, 4 Carlito, 2 Fira Print)
  - Demo-Datum: `2026-09-02`, Live-Netzwerk-Requests: `False`
  - Umfang: 172 Aufnahmen im Manifest, 172 PNG-Dateien unter `.claude/evidence/ui-inventory-proof-fix-0909/capture-promoted-0911/screenshots/`
- **Ersetzter Vorlaeufer-Stand (`superseded_evidence`):**
  - Altes Manifest: SHA-256 `56041a9510224afb162abf6c0d2d94d29becb735ee0b1550f43770004ebc315c`
  - Quell-Commit: `5f5f6cb535922db8453c68d871279d6b2e203391`
  - Aufgenommen am: `2026-09-09T00:20:06.968625+00:00`
  - Abgeloest durch: `wp-d7589450daee`
  - Umfang und Status der 111 ersetzten Zeilen:
    - `superseded_unverified_readiness`: 106 Zeilen
    - `invalid_blank_lazy_images`: 4 Zeilen (Bilder unterhalb des Sichtbereichs blieben ungeladen)
    - `invalid_hardcoded_record`: 1 Zeile (Publish-Dialog war hartkodiert)
    - Total: 111 Zeilen
  - Drei dokumentierte Recorder-Defekte:
    1. *«Listener nach DOMContentLoaded entfernt.»*
    2. *«Feste 250-ms-Wartezeit statt Bereitschaft.»*
    3. *«Publish-Dialog-Zeile hartkodiert.»*

---

## 2. Roots fuenf Befunde

| # | Befund | Status | Beleg |
|---|---|---|---|
| 1 | Listener werden direkt nach DOMContentLoaded entfernt, spaetere Fehler fehlen | **bestanden** | `regression-proof.py`: Originalrecorder `console=[]`, korrigierter Recorder `['error: late console failure']` und `['late page error']`; Test `test_console_failure_after_dom_content_loaded_is_recorded` in `reference_scaffold/tests/test_ui_inventory_capture.py`. |
| 2 | Feste Verzoegerung statt Schrift-/Bildbereitschaft, nur deklarierte CSS-Familie | **bestanden** | `await_ready` wartet auf `load`, fuehrt einen begrenzten Scroll-Durchlauf fuer `loading="lazy"` durch, wartet auf `document.fonts.status === 'loaded'` und alle `img.complete`; `rendered_fonts` liest ueber CDP `CSS.getPlatformFontsForNode` die real gerasterte Schrift (172 von 172 Aufnahmen mit echtem Plattformfont und vollstaendiger Bereitschaft, 0 `readiness.error`); Test `test_readiness_waits_for_late_image_instead_of_a_fixed_delay`. |
| 3 | Publish-Dialog mit hartkodiertem Status 200, `overflow=false`, leeren Fehlern | **bestanden** | `open_modal` oeffnet das Modal wirklich, wartet auf Sichtbarkeit und `.show`; bei fehlendem Ausloeser entsteht ein `blocked_modal_not_open`-Eintrag statt einer erfundenen Erfolgszeile; Test `test_absent_publish_modal_produces_a_blocked_record_not_a_success`. |
| 4 | Tests ueberschrieben Matrix, Manifest und private Belege bedingungslos | **bestanden** | `Outputs.into`, `build_matrix.write_matrix(--out)`; der Regressionslauf schreibt isoliert nach `tmp_path` und prueft Matrix, Manifest und alle Original-PNG auf Unveraendertheit; nur `UI_CAPTURE_PROMOTE=1` schreibt die versionierten Belege nach Vorabpruefung; Test `test_redirected_run_leaves_versioned_outputs_untouched`. |
| 5 | Kopier-Erfolg und Revisionsdetail angeblich mangels Fixture nicht belegbar | **bestanden** | Echte PostgreSQL-Fixtures via `_prepare_inventory_entities` in `reference_scaffold/tests/test_ui_route_inventory.py` erzeugen gepruefte Wochen, unveraenderliche Revisionen, Kochbuecher, Grundlagen-Tags, lokale Benutzer und Zuweisungen. Revisionsdetail in allen 5 Viewports; Kopiererfolg in beiden Primaerviewports; saemtliche 17 bisher fehlenden visuellen Admin-Endpunkte rendern mit Status 200. |

---

## 3. Ergaenzte Luecken dieses Freeze

Im Urspruenglichen Manifest fehlten 17 visuelle HTML-Admin-Endpunkte vollstaendig. Der Freeze-Commit `0e6a292` schliesst diese Luecken ueber synthetische Store-Fixtures ab.

### Die 17 neu ergaenzten visuellen HTML-Endpunkte

| Endpunkt | Konkreter Fixture-Pfad im Testlauf | 1440 × 900 | 390 × 844 | Status | Rendered |
|---|---|:---:|:---:|:---:|:---:|
| `admin.branding_preview` | `/admin/design/marke/vorschau/2` | ja | ja | 200 | True |
| `admin.cookbook_edit` | `/admin/kochbuecher/<uuid>` | ja | ja | 200 | True |
| `admin.cookbook_status` | `/admin/kochbuecher/<uuid>/status` | ja | ja | 200 | True |
| `admin.header_get` | `/admin/cafeteria/header?week=2026-08-31` | ja | ja | 200 | True |
| `admin.local_user_detail` | `/admin/benutzer/<uuid>` | ja | ja | 200 | True |
| `admin.master_data_detail` | `/admin/grundlagen/tags/<uuid>` | ja | ja | 200 | True |
| `admin.master_data_new` | `/admin/grundlagen/tags/neu` | ja | ja | 200 | True |
| `admin.print_template_editor` | `/admin/vorlagen/cafeteria?week=2026-08-31` | ja | ja | 200 | True |
| `admin.recipe_edit` | `/admin/rezepte/<uuid>` | ja | ja | 200 | True |
| `admin.recipe_images` | `/admin/rezepte/<uuid>/bilder` | ja | ja | 200 | True |
| `admin.recipe_print_template_editor` | `/admin/vorlagen/rezepte?recipe=<uuid>&recipe_revision=<uuid>` | ja | ja | 200 | True |
| `admin.recipe_revisions` | `/admin/rezepte/<uuid>/revisionen` | ja | ja | 200 | True |
| `admin.recipe_scale` | `/admin/rezepte/<uuid>/skalierung` | ja | ja | 200 | True |
| `admin.recipe_status` | `/admin/rezepte/<uuid>/status` | ja | ja | 200 | True |
| `admin.screen_template_assignment` | `/admin/screens/cafeteria/wochenvorlage` | ja | ja | 200 | True |
| `admin.screen_template_preview` | `/admin/vorlagen/screens/cafeteria/cafeteria-week-photo` | ja | ja | 200 | True |
| `admin.service_get` | `/admin/cafeteria/service?week=2026-08-31&day=2026-08-31&meal=LUNCH` | ja | ja | 200 | True |

*(Hinweis: `admin.recipe_revision` wurde zusaetzlich als Referenzpfad in allen fuenf Viewports mit Status 200 erfasst; `admin.component_detail`, `admin.copy_get` und `admin.menu_get` besitzen nun echte Store-Fixtures statt synthetischer Platzhalter).*

### Abdeckung visueller Routen gesamt

- **Gesamtzahl visueller Routen in Matrix:** 61
- **Visuelle Routen mit voller Primaerabdeckung (1440×900 und 390×844 mit Status 200 & rendered=True):** 60 von 61
- **Einzige visuelle Route ohne Aufnahmen:** `auth.callback` (`/auth/callback`, Klassifikation `html`, Owning-MP `MP-UI-AUTH`).
  - **Begruendung:** Gemaess Matrix `coverage_blocks` traegt der Endpunkt den Status `blocked_not_fake_pass` mit der Begruendung: *«Cannot safely synthesize a real Entra tenant callback or production person. Keinerlei Fälschung von Produktivpersonen oder externen Tenants.»*

---

## 4. Zustaende (Shared States)

Das Manifest belegt saemtliche 6 in `ui-route-matrix.json` definierten gemeinsamen Zustaende deterministisch mit konkreten Aufnahmen:

| Zustand (`id`) | Owning MP | Fixture | Enthaltene Endpunkte & Pfade | Suffix | Viewport | Status |
|---|---|---|---|---|:---:|:---:|
| `login` | `MP-UI-AUTH` | `local_auth_enabled_no_production_persons` | `auth.local_login` (`/auth/local`) | `''` | 1440×900, 390×844 | 200 |
| | | | `auth.login` (`/auth/login`) | `auth-login` | 1440×900, 390×844 | 200 |
| `empty` | `MP-UI-MACROS` | `isolated_pg_schema25_seed_before_prepare_entities` | `admin.menu_collection` (`/admin/cafeteria/menues`) | `empty` | 1440×900, 390×844 | 200 |
| | | | `admin.recipes_list` (`/admin/rezepte`) | `empty` | 1440×900, 390×844 | 200 |
| | | | `admin.cookbooks_list` (`/admin/kochbuecher`) | `empty` | 1440×900, 390×844 | 200 |
| | | | `admin.master_data_list` (`/admin/grundlagen`) | `empty` | 1440×900, 390×844 | 200 |
| | | | `admin.components_get` (`/admin/cafeteria/komponenten`) | `empty` | 1440×900, 390×844 | 200 |
| `invalid` | `MP-UI-MACROS` | `isolated_pg_schema25_seed_plus_synthetic_entities_invalid_submit` | `admin.menu_get` (`/admin/cafeteria/menu?...`) | `invalid` | 1440×900, 390×844 | 200 |
| | | | `admin.display_settings` (`/admin/design/darstellung`) | `invalid` | 1440×900, 390×844 | 200 |
| | | | `admin.recipe_edit` (`/admin/rezepte/<uuid>`) | `invalid` | 1440×900, 390×844 | 200 |
| `access_denied` | `MP-UI-AUTH` | `anonymous_context_and_synthetic_editor_without_users_manage` | `admin.cafeteria` (`/admin/cafeteria`) | `anonymous-401` | 1440×900 | 401 |
| | | | `admin.local_users_list` (`/admin/benutzer`) | `editor-403` | 1440×900 | 403 |
| `dialogs` | `MP-UI-WEEKS` | `isolated_pg_schema25_seed_plus_synthetic_week` | `admin.cafeteria` (`/admin/cafeteria`) | `dialog-publish` | 1440×900 | 200 |
| `role_navigation` | `MP-UI-SHELL` | `synthetic_entra_users_editor_publisher_admin` | `admin.cafeteria` (`/admin/cafeteria`) | `role-nav-admin` | 1440×900, 390×844 | 200 |
| | | | `admin.cafeteria` (`/admin/cafeteria`) | `role-nav-editor` | 1440×900, 390×844 | 200 |
| | | | `admin.cafeteria` (`/admin/cafeteria`) | `role-nav-publisher` | 1440×900, 390×844 | 200 |

---

## 5. Rollen und Navigation

### Gemessene Sidebar-Navigation je Rolle

Die Erfassung erfolgte per DOM-Auslesung ueber den Recorder fuer alle drei Rollen bei beiden Primaerviewports:

| Rolle | Viewport | Anzahl `nav_items` | Sichtbare Navigationseintraege |
|---|:---:|:---:|---|
| `Cafeteria.Admin` | 1440 × 900 | **14** | Wochenplaene, Wochenverwaltung, Menues, Komponenten, Grundlagen, Rezepte, Kochbuecher, CSV Import, Screens, Vorlagen, API & Schnittstellen, **Benutzer & Zugriff**, **Design & Marke**, **Bereiche & Zeiten** |
| `Cafeteria.Admin` | 390 × 844 | **14** | Identisch zu 1440 × 900 |
| `Cafeteria.Editor` | 1440 × 900 | **11** | Wochenplaene, Wochenverwaltung, Menues, Komponenten, Grundlagen, Rezepte, Kochbuecher, CSV Import, Screens, Vorlagen, API & Schnittstellen |
| `Cafeteria.Editor` | 390 × 844 | **11** | Identisch zu 1440 × 900 |
| `Cafeteria.Publisher` | 1440 × 900 | **11** | Identisch zu Editor |
| `Cafeteria.Publisher` | 390 × 844 | **11** | Identisch zu Editor |

- **Admin-only Navigationseintraege (genau 3):**
  1. `Benutzer & Zugriff`
  2. `Design & Marke`
  3. `Bereiche & Zeiten`
- **Editor- und Publisher-Navigation:** Voellig identisch (11 Eintraege); beide Rollen sehen keine administrativen Verwaltungsbereiche.

### Die 10 korrigierten Admin-Routen

Vor dem Freeze fuehrte die Matrix faelschlicherweise auch `Cafeteria.Editor` und `Cafeteria.Publisher` an 10 Routen, die serverseitig ausschliesslich Administratoren zustehen. Durch statische Wrapper- und Closure-Analyse in `build_matrix.py` (Bestaetigt durch den Laufzeittest `test_matrix_roles_match_server_side_authorization`) wurden diese auf `['Cafeteria.Admin']` korrigiert:

| Endpunkt | Berechtigung / Capability | Belegstelle im Quellcode |
|---|---|---|
| `admin.local_users_list` | `users.manage` | `cafeteria/admin/local_user_routes.py:27-28` (`_protected` -> `users.manage`) |
| `admin.local_user_new` | `users.manage` | `cafeteria/admin/local_user_routes.py:146-147` |
| `admin.local_user_create` | `users.manage` | `cafeteria/admin/local_user_routes.py:154-155` |
| `admin.local_user_detail` | `users.manage` | `cafeteria/admin/local_user_routes.py:170-171` |
| `admin.local_user_change` | `users.manage` | `cafeteria/admin/local_user_routes.py:179-180` |
| `admin.local_user_events` | `users.manage` | `cafeteria/admin/local_user_routes.py:215-216` |
| `admin.access_history` | `users.manage` | `cafeteria/admin/access_history_routes.py:13-14` |
| `admin.operations_settings` | `settings.write` | `cafeteria/admin/operations_routes.py:214-215` (`_authorized_operations`) |
| `admin.recipe_print_template_editor` | `settings.write` | `cafeteria/admin/recipe_print_template_routes.py:37-41` |
| `admin.recipe_print_template_preview` | `settings.write` | `cafeteria/admin/recipe_print_template_routes.py:37-41` |

### Methodenabhaengige Rollen (`method_roles`)

- **`admin.screen_template_assignment`** (`/admin/screens/<family>/wochenvorlage`):
  Die GET-Methode (visuell) traegt `@require_capability('draft.read')` und ist fuer Editor, Publisher und Admin zugaenglich.
  Die POST-Methode verlangt serverseitig jedoch `settings.write` (`cafeteria/admin/screen_template_routes.py:96-97`) und weist Editor und Publisher mit HTTP 403 ab.
  In der Matrix ist dies via `method_roles` formal dokumentiert:
  `'method_roles': {'POST': ['Cafeteria.Admin']}`.

---

## 6. Ausgefuehrte Gates

Saemtliche Pruefungen wurden gegen die realen Projekt-Binaries auf dem isolierten PostgreSQL/Redis-Testpool ausgefuehrt:

### Gate-Logs im Belegordner (`gates-0911/`)

| Log-Datei | Befehlszweck | Ergebniszeile | Exit | Einordnung |
|---|---|---|:---:|---|
| `01-integration-gate-before-promotion.log` | Pytest Integrationsgate vor Promotion (`tests/test_ui_route_inventory.py`) | `1 failed, 33 passed in 116.15s` | 1 | **Massgeblich**: Belegt das erwartete Scheitern von `test_versioned_manifest_covers_every_visual_route` vor Promotion der neuen Fixtures. |
| `02-promotion-first-attempt-superseded-duplicate-menu-row.log` | Erster Promotionslauf mit `UI_CAPTURE_PROMOTE=1` | `1 passed, 9 deselected in 78.68s` | 0 | **Ersetzt**: Menue-Editor war doppelt aufgefuehrt (`extra_admin_paths`). |
| `03-gate-run-after-first-promotion-superseded.log` | Gesamtlauf nach der ersten Promotion | `34 passed in 125.10s` | 0 | **Ersetzt**: Betraf das verworfene Zwischenmanifest. |
| `04-promotion-final.log` | Finaler Promotionslauf mit bereinigten Pfaden (`UI_CAPTURE_PROMOTE=1`) | `1 passed, 9 deselected in 76.70s` | 0 | **Massgeblich**: Schrieb die 172 Captures und PNG-Dateien final ins Manifest. |
| `05-gate-run-1-final.log` | Erster vollstaendiger Integrationslauf nach finaler Promotion | `34 passed in 113.84s` | 0 | **Massgeblich**: Bestaetigt alle 34 Tests gruen gegen das neue Manifest. |
| `06-gate-run-2-final.log` | Zweiter vollstaendiger Integrationslauf nach finaler Promotion | `34 passed in 112.49s` | 0 | **Massgeblich**: Idempotenz- und Stabilitaetsnachweis (`34 passed in 112.49s`). |

### Statische Pruefungen des Orchestrators

| Pruefwerkzeug | Befehl / Parameter | Ergebnis | Einordnung |
|---|---|---|---|
| `ruff` | `ruff check --no-cache` ueber alle Quell- und Testdateien | `All checks passed!` | Bestanden (`GATE_EXIT=0`) |
| `mypy` | `mypy --python-executable /tmp/dishboard-shared-venv/bin/python` mit `MYPYPATH=reference_scaffold` | `Success: no issues found in 2 source files` | Bestanden (`GATE_EXIT=0`) |
| `git diff --check` | Whitespace- und Syntax-Pruefung | Keine Ausgabe | Bestanden (`GATE_EXIT=0`) |
| `regression-proof.py` | Standalone Loopback-Pruefung fuer Listener-Lebensdauer | `REGRESSION_PROOF=PASS` | Bestanden (`GATE_EXIT=0`) |

---

## 7. Nicht ausgefuehrt oder blockiert

| Pruefung / Bereich | Status | Begruendung |
|---|:---:|---|
| Entra-Tenant-Callback | **blockiert** | Externe Azure-AD-Infrastruktur; weder reale Tenants noch synthetische Personen duerfen gefaelscht werden (`blocked_not_fake_pass`). |
| Physischer Yodeck-Player | **nicht ausgefuehrt** | Externe Hardware; reine Web-Signage-Ansichten sind im Inventar erfasst, Hardwaretests gehoeren nicht in den Browser-Recorder. |
| Native PDF-Bytes und Papierlayout | **nicht ausgefuehrt** | Reine Download-Artefakte; die HTML-Drucktemplates sind visuell abgedeckt. |
| Barrierefreiheit, Kontrast, Tastaturnavigation | **nicht ausgefuehrt** | Screenshots ersetzen keine a11y-Audits; gehoert verbindlich in die Umsetzungs-WPs `MP-UI-TOKENS` und `MP-UI-SHELL`. |
| GitNexus `detect_changes` | **blockiert** | Der temporaere Worktree ist in der GitNexus-Instanz nicht indexiert. |
| OCR (`ocr review`) | **nicht ausgefuehrt** | In frueheren Laeufen echtes HTTP 429; per Arbeitsauftrag strikt untersagt. |
| Endnutzer-Akzeptanztests | **nicht ausgefuehrt** | Rein automatisierte Pipeline-Verifikation auf Code- und Renderebene. |

---

## 8. Baseline-Status

> [!WARNING]
> Der Status saemtlicher Referenzen dieses Freeze lautet unveraendert:
> **`meta.baseline_status = "proposed_never_user_approved"`**
> Ein Screenshot ist **keine** Funktions-, Barrierefreiheits- oder Abnahmebestaetigung durch den Auftraggeber. Die Bilder dokumentieren ausschliesslich den maschinell messbaren Ist-Zustand des Browsers unter definierten Testbedingungen.

---

## Anhang: Vollstaendige Ausgabe von `stats.py` (Verbatim)

```text
================================================================================
UI-INVENTAR-FREEZE 2026-09-11: KENNZAHLEN UND STATISTIKEN
================================================================================

--- 1. DATEI-HASHES (SHA-256) ---
Versioniertes Manifest         : ee42bd86e5642835aeeb78f04129e39daab888f182e8664ea0a6a4500a0c16c2
Promotete Manifest-Kopie       : ee42bd86e5642835aeeb78f04129e39daab888f182e8664ea0a6a4500a0c16c2
Versionierte Matrix            : 62dc038032d22d06834ecd601c623ce14431be1b6932be46b6c8c60188de2e18
capture.py                     : 36e85d88b5b3d6631675c8b5c4383f6b8afc5db1e2d34c124a25fc4c32ca5b0f
build_matrix.py                : 42124fc783750e9689b8b741511193f9f2c57694c4b425451121feb7c8489eeb
test_ui_route_inventory.py     : a5032cb258bb1ec2fd59c0ef909935f243279d5967decb75edbcfc8e426cb20d
test_ui_inventory_capture.py   : ffabce53d62d4c9786d4603a02facd7ba4c1545838777b97be392ddecdc21818
regression-proof.py            : 441aadc7a32962ef9e54b898972a2c62f7dc3baa2e8696f2cca5b789f7a2ecba
Manifest-Kopien byteidentisch  : True

Original-Screenshots (111 PNG) : b8d1f142b0e9521177c1cc830dd49548a83bebd95c4e3a8f1def571992309a4e (Mengenhash: sha256 von sortierten 'sha256  name\n')
Promotete Screenshots (172 PNG): 7fb5cccefc6a3f5e90a9aae13e52fde0a771c95e88f5fd2b76e6b79792193b60 (Mengenhash: sha256 von sortierten 'sha256  name\n')

--- 2. MANIFEST METADATEN (meta) ---
wp_id                          : wp-d7589450daee
lane                           : claude-code
model                          : claude-fable-5-1
identity_status                : caller_supplied
baseline_status                : proposed_never_user_approved
demo_today                     : 2026-09-02
captured_at                    : 2026-09-11T14:33:09.136595+00:00
browser                        : playwright-chromium 151.0.7922.34 151.0.7922.34
runtime.playwright             : 1.58.0
runtime.python                 : 3.14.4
runtime.platform               : Linux-7.0.0-31-generic-x86_64-with-glibc2.43
locale / timezone / dpr        : de-CH / Europe/Zurich / 1
fixture.status                 : caller_supplied
fixture.sha256                 : 8e8bee98a50ed8a11bf2193d8bfa11fb5ea57ea2f3fdd48c173278d0cd75bd4f
font_files Anzahl              : 10
  - reference_scaffold/cafeteria/static/fonts/fira-sans-400.woff2: 38b2ab6f40cfa497c37e1f7fa6317b4583229303e44dae6860c8bb74d73947f8
  - reference_scaffold/cafeteria/static/fonts/fira-sans-500.woff2: 6488cae070f854b23c377e4c5ccb84fb3649a004f96bdda51194631bfb860f0f
  - reference_scaffold/cafeteria/static/fonts/fira-sans-600.woff2: 7a6da1251597145e70a2cfa1b6be4727b5e2c4c610d958163c1f5ae04a51390e
  - reference_scaffold/cafeteria/static/fonts/fira-sans-700.woff2: d6a1857ca75e34de49b33e958905587dc48d37dd20389038396a2b11036f77f3
  - reference_scaffold/cafeteria/static/fonts/weekly-print-carlito-bold.ttf: ea8b86a7bd9beb41b681ceccfe7c0bfe3d75c7ac41ad32f5767a58e628a8826c
  - reference_scaffold/cafeteria/static/fonts/weekly-print-carlito-bold.woff: 6292892e0f09dd80ccc510280831d1ecffe512b95558be1699ca5d4154889657
  - reference_scaffold/cafeteria/static/fonts/weekly-print-carlito.ttf: 9817da6f347152ce89e6539260ea792dbb4c5c5e1a1fca4876bb6ff3210e0077
  - reference_scaffold/cafeteria/static/fonts/weekly-print-carlito.woff: 550cd5fa32077c2db8c5ccd50edecd5f6fc344e4fd919601b76e57828bc18548
  - reference_scaffold/cafeteria/static/fonts/weekly-print-fira-bold.ttf: 79d3729d2c6b8d1993657acab398f8a0632433a9007a8c6129375d7fe6020485
  - reference_scaffold/cafeteria/static/fonts/weekly-print-fira.ttf: 1a02a34eca8eda26e871a6da5cf48510ff0b9f3a9f1290195520455911e95773

--- 3. ERSETZTE EVIDENZ (superseded_evidence) ---
manifest_sha256 (alt)          : 56041a9510224afb162abf6c0d2d94d29becb735ee0b1550f43770004ebc315c
source_commit                  : 5f5f6cb535922db8453c68d871279d6b2e203391
captured_at                    : 2026-09-09T00:20:06.968625+00:00
superseded_by_wp               : wp-d7589450daee
recorder_defects:
  - Listener nach DOMContentLoaded entfernt.
  - Feste 250-ms-Wartezeit statt Bereitschaft.
  - Publish-Dialog-Zeile hartkodiert.
Anzahl ersetzte Zeilen         : 111
Status-Verteilung ersetzte Zeilen:
  - superseded_unverified_readiness    : 106
  - invalid_blank_lazy_images          : 4
  - invalid_hardcoded_record           : 1

--- 4. AUFNAHMEN IM PROMOTETEN MANIFEST ---
Gesamtzahl Aufnahmen           : 172
Gesamtzahl PNG-Dateien         : 172
Aufnahmen je Viewport:
  - 1440 x  900 :  81 Aufnahmen
  -  390 x  844 :  75 Aufnahmen
  - 1920 x 1080 :   6 Aufnahmen
  -  768 x 1024 :   5 Aufnahmen
  - 1024 x  768 :   5 Aufnahmen
Suffix-Verteilung:
  - '' (Standardpfad)        : 124 Aufnahmen
  - 'reference'              :  15 Aufnahmen
  - 'empty'                  :  10 Aufnahmen
  - 'invalid'                :   6 Aufnahmen
  - 'auth-login'             :   2 Aufnahmen
  - 'closed-sunday'          :   2 Aufnahmen
  - 'role-nav-admin'         :   2 Aufnahmen
  - 'role-nav-editor'        :   2 Aufnahmen
  - 'role-nav-publisher'     :   2 Aufnahmen
  - 'anonymous-401'          :   1 Aufnahmen
  - 'dialog-publish'         :   1 Aufnahmen
  - 'editor-403'             :   1 Aufnahmen
  - 'editor-nav'             :   1 Aufnahmen
  - 'editor-settings'        :   1 Aufnahmen
  - 'missing-week-400'       :   1 Aufnahmen
  - 'missing-week-404'       :   1 Aufnahmen
HTTP-Status-Verteilung:
  - HTTP 200 : 165 Aufnahmen
  - HTTP 400 :   1 Aufnahmen
  - HTTP 401 :   1 Aufnahmen
  - HTTP 403 :   2 Aufnahmen
  - HTTP 404 :   3 Aufnahmen
Zeilen mit readiness.error     : 0
Zeilen mit overflow_horizontal : 0

--- 5. ROLLEN UND NAVIGATION ---
Anzahl Rollen-Navigationszeilen: 6
  - Rolle 'Cafeteria.Admin' (390x844): 14 Eintraege
    Eintraege: Wochenpläne, Wochenverwaltung, Menüs, Komponenten, Grundlagen, Rezepte, Kochbücher, CSV Import, Screens, Vorlagen, API & Schnittstellen, Benutzer & Zugriff, Design & Marke, Bereiche & Zeiten
  - Rolle 'Cafeteria.Admin' (1440x900): 14 Eintraege
    Eintraege: Wochenpläne, Wochenverwaltung, Menüs, Komponenten, Grundlagen, Rezepte, Kochbücher, CSV Import, Screens, Vorlagen, API & Schnittstellen, Benutzer & Zugriff, Design & Marke, Bereiche & Zeiten
  - Rolle 'Cafeteria.Editor' (390x844): 11 Eintraege
    Eintraege: Wochenpläne, Wochenverwaltung, Menüs, Komponenten, Grundlagen, Rezepte, Kochbücher, CSV Import, Screens, Vorlagen, API & Schnittstellen
  - Rolle 'Cafeteria.Editor' (1440x900): 11 Eintraege
    Eintraege: Wochenpläne, Wochenverwaltung, Menüs, Komponenten, Grundlagen, Rezepte, Kochbücher, CSV Import, Screens, Vorlagen, API & Schnittstellen
  - Rolle 'Cafeteria.Publisher' (390x844): 11 Eintraege
    Eintraege: Wochenpläne, Wochenverwaltung, Menüs, Komponenten, Grundlagen, Rezepte, Kochbücher, CSV Import, Screens, Vorlagen, API & Schnittstellen
  - Rolle 'Cafeteria.Publisher' (1440x900): 11 Eintraege
    Eintraege: Wochenpläne, Wochenverwaltung, Menüs, Komponenten, Grundlagen, Rezepte, Kochbücher, CSV Import, Screens, Vorlagen, API & Schnittstellen
Admin Eintraege (1440x900)     : 14
Editor Eintraege (1440x900)    : 11
Publisher Eintraege (1440x900) : 11
Editor == Publisher            : True
Admin-only Eintraege (3)       : ['Benutzer & Zugriff', 'Bereiche & Zeiten', 'Design & Marke']

--- 6. MATRIX-ZAEHLER UND ZUSTAENDE ---
route_count                    : 116 (meta: 116)
template_count                 : 75 (meta: 75)
html_routes                    : 59
visual_routes                  : 61
Anzahl Shared States in Matrix : 6
  * State 'login':
      owning_mp : MP-UI-AUTH
      fixture   : local_auth_enabled_no_production_persons
      Routen (2): ['auth.local_login', 'auth.login']
      Matrix-Captures: 2, Manifest-Zeilen: 4
        - /auth/local [suffix=''] 1440x900 -> Status 200
        - /auth/local [suffix=''] 390x844 -> Status 200
        - /auth/login [suffix='auth-login'] 1440x900 -> Status 200
        - /auth/login [suffix='auth-login'] 390x844 -> Status 200
  * State 'empty':
      owning_mp : MP-UI-MACROS
      fixture   : isolated_pg_schema25_seed_before_prepare_entities
      Routen (5): ['admin.menu_collection', 'admin.recipes_list', 'admin.cookbooks_list', 'admin.master_data_list', 'admin.components_get']
      Matrix-Captures: 5, Manifest-Zeilen: 10
        - /admin/cafeteria/menues [suffix='empty'] 1440x900 -> Status 200
        - /admin/cafeteria/menues [suffix='empty'] 390x844 -> Status 200
        - /admin/rezepte [suffix='empty'] 1440x900 -> Status 200
        - /admin/rezepte [suffix='empty'] 390x844 -> Status 200
        - /admin/kochbuecher [suffix='empty'] 1440x900 -> Status 200
        - /admin/kochbuecher [suffix='empty'] 390x844 -> Status 200
        - /admin/grundlagen [suffix='empty'] 1440x900 -> Status 200
        - /admin/grundlagen [suffix='empty'] 390x844 -> Status 200
        - /admin/cafeteria/komponenten [suffix='empty'] 1440x900 -> Status 200
        - /admin/cafeteria/komponenten [suffix='empty'] 390x844 -> Status 200
  * State 'invalid':
      owning_mp : MP-UI-MACROS
      fixture   : isolated_pg_schema25_seed_plus_synthetic_entities_invalid_submit
      Routen (3): ['admin.menu_get', 'admin.display_settings', 'admin.recipe_edit']
      Matrix-Captures: 3, Manifest-Zeilen: 6
        - /admin/cafeteria/menu?week=2026-08-31&day=2026-08-31&meal=LUNCH&option=MENU_1 [suffix='invalid'] 1440x900 -> Status 200
        - /admin/cafeteria/menu?week=2026-08-31&day=2026-08-31&meal=LUNCH&option=MENU_1 [suffix='invalid'] 390x844 -> Status 200
        - /admin/design/darstellung [suffix='invalid'] 1440x900 -> Status 200
        - /admin/design/darstellung [suffix='invalid'] 390x844 -> Status 200
        - /admin/rezepte/37514d5c-5c12-46f0-a895-873c85c2f7e0 [suffix='invalid'] 1440x900 -> Status 200
        - /admin/rezepte/37514d5c-5c12-46f0-a895-873c85c2f7e0 [suffix='invalid'] 390x844 -> Status 200
  * State 'access_denied':
      owning_mp : MP-UI-AUTH
      fixture   : anonymous_context_and_synthetic_editor_without_users_manage
      Routen (1): ['admin.*']
      Matrix-Captures: 2, Manifest-Zeilen: 2
        - /admin/cafeteria [suffix='anonymous-401'] 1440x900 -> Status 401
        - /admin/benutzer [suffix='editor-403'] 1440x900 -> Status 403
  * State 'dialogs':
      owning_mp : MP-UI-WEEKS
      fixture   : isolated_pg_schema25_seed_plus_synthetic_week
      Routen (2): ['admin.cafeteria', 'admin.patienten']
      Matrix-Captures: 1, Manifest-Zeilen: 1
        - /admin/cafeteria [suffix='dialog-publish'] 1440x900 -> Status 200
  * State 'role_navigation':
      owning_mp : MP-UI-SHELL
      fixture   : synthetic_entra_users_editor_publisher_admin
      Routen (1): ['admin.cafeteria']
      Matrix-Captures: 3, Manifest-Zeilen: 6
        - /admin/cafeteria [suffix='role-nav-admin'] 1440x900 -> Status 200
        - /admin/cafeteria [suffix='role-nav-admin'] 390x844 -> Status 200
        - /admin/cafeteria [suffix='role-nav-editor'] 1440x900 -> Status 200
        - /admin/cafeteria [suffix='role-nav-editor'] 390x844 -> Status 200
        - /admin/cafeteria [suffix='role-nav-publisher'] 1440x900 -> Status 200
        - /admin/cafeteria [suffix='role-nav-publisher'] 390x844 -> Status 200

--- 7. ABDECKUNG DER VISUELLEN ROUTEN (1440x900 & 390x844) ---
Visuelle Routen mit voller Primaerabdeckung (200 & rendered): 60 / 61
Visuelle Routen ohne volle Primaerabdeckung                : 1
  - auth.callback: vorhanden=set(), fehlend={(1440, 900), (390, 844)}
    Block-Status: blocked_not_fake_pass, Grund: Cannot safely synthesize a real Entra tenant callback or production person.

--- 8. DIE 17 NEU ERGAENZTEN ENDPUNKTE DIESES FREEZE ---
Anzahl ergaenzte Endpunkte: 17
  - admin.branding_preview             : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.cookbook_edit                : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.cookbook_status              : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.header_get                   : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.local_user_detail            : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.master_data_detail           : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.master_data_new              : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.print_template_editor        : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.recipe_edit                  : 4 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True), (1440, 900, 200, True), (390, 844, 200, True)]
  - admin.recipe_images                : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.recipe_print_template_editor : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.recipe_revisions             : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.recipe_scale                 : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.recipe_status                : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.screen_template_assignment   : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.screen_template_preview      : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]
  - admin.service_get                  : 2 Aufnahmen -> [(1440, 900, 200, True), (390, 844, 200, True)]

--- 9. DIE 10 KORRIGIERTEN ADMIN-ROUTEN UND METHOD_ROLES ---
  - admin.local_users_list             : Rollen=['Cafeteria.Admin'], cap=users.manage, Beleg=local_user_routes.py:27-28
  - admin.local_user_new               : Rollen=['Cafeteria.Admin'], cap=users.manage, Beleg=local_user_routes.py:146-147
  - admin.local_user_create            : Rollen=['Cafeteria.Admin'], cap=users.manage, Beleg=local_user_routes.py:154-155
  - admin.local_user_detail            : Rollen=['Cafeteria.Admin'], cap=users.manage, Beleg=local_user_routes.py:170-171
  - admin.local_user_change            : Rollen=['Cafeteria.Admin'], cap=users.manage, Beleg=local_user_routes.py:179-180
  - admin.local_user_events            : Rollen=['Cafeteria.Admin'], cap=users.manage, Beleg=local_user_routes.py:215-216
  - admin.access_history               : Rollen=['Cafeteria.Admin'], cap=users.manage, Beleg=access_history_routes.py:13-14
  - admin.operations_settings          : Rollen=['Cafeteria.Admin'], cap=settings.write, Beleg=operations_routes.py:214-215
  - admin.recipe_print_template_editor : Rollen=['Cafeteria.Admin'], cap=settings.write, Beleg=recipe_print_template_routes.py:37-41
  - admin.recipe_print_template_preview: Rollen=['Cafeteria.Admin'], cap=settings.write, Beleg=recipe_print_template_routes.py:37-41

Routen mit method_roles (1):
  - admin.screen_template_assignment   : method_roles={'POST': ['Cafeteria.Admin']}
    Beleg: screen_template_routes.py:96-97 (POST verlangt settings.write)
================================================================================
ENDE KENNZAHLEN
================================================================================
```
