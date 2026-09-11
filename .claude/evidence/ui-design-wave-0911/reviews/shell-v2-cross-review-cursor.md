# Cross-Vendor-Review MP-UI-SHELL v2

| Feld | Wert |
|---|---|
| **WP-ID** | wp-52c02ef0f44d-v2-review |
| **Branch** | `feat/ui-shell-v2-0911` |
| **HEAD** | `3bc918520e35ada6e036a634dfbd16f9ab733fc7` |
| **Basis** | `514ced93cb48db59d904f1a9612de44c3c1c317d` |
| **Reviewer** | cursor composer-2.5 |
| **Autoren** | codex gpt-6-astra (Entwurf), grok-4.6 (Abschluss) |
| **Worktree** | `/nvmetank1/projects/menuplan/.claude/worktrees/ui-shell-v2-codex-0911` |
| **Modus** | read-only (keine Repo-Änderungen) |

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| — | — | Keine Befunde | — | — |

## Geprüft und in Ordnung

### 1. NAV-01 — Vier flache Sidebar-Einträge

- Vier Bereiche modelliert in [`_area_tabs.html:17-42`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html): Wochenplan · Menüs & Bausteine · Vorschau & Bildschirme · Einstellungen.
- Rendering über `area_links()` in [`_workflow_sidebar.html:16-28`](reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html); Labels nur in `.nav-link-title` ([`8:14`](reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html)), kein `.nav-link-desc` (Repo-weite Suche in Admin-Templates leer).
- Aktiver Eintrag per `aria-current="page"` an `area_nav.selected.area` / `workflow_nav` ([`10:10`](reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html), [`44-47`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html)).
- Icons aus Sprite via `icon()`-Makro ([`_macros.html:3-4`](reference_scaffold/cafeteria/templates/admin/_macros.html)): `calendar-week`, `tools-kitchen-2`, `eye`, `calendar-cog` ([`_area_tabs.html:18,23,30,35`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html)).
- Test: vier Titel je Rolle, keine Gruppen/Beschreibungen ([`test_ui_master_shell_browser.py:27,168-169`](reference_scaffold/tests/test_ui_master_shell_browser.py)).

### 2. NAV-02 — Alt→Neu-Zuordnung und Rechte

- Vollständige Alt→Neu-Tabelle im Test [`ENTRIES`](reference_scaffold/tests/test_ui_master_shell_browser.py:29-54) deckt alle 16 früheren Sidebar-Endpunkte ab.
- Sichtbarkeitsbedingungen in Tab-Definition [`_area_tabs.html:27-28,36-41`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html): `can_browse_recipes`, `can_configure_display`, `can_manage_users`; API-Tab sichtbar, Server 403 für Nicht-Admin ([`test_ui_master_shell_browser.py:191-192`](reference_scaffold/tests/test_ui_master_shell_browser.py)).
- Rollenmatrix Admin/Editor/Publisher mit je vier Sidebar-Einträgen und gefilterten Einstellungs-Tabs ([`159-195`](reference_scaffold/tests/test_ui_master_shell_browser.py)).
- `url_for`-Ziele existieren (z. B. `cafeteria`, `patienten`, `week_management`, `menu_collection`, `components_get`, `master_data_list`, `recipes_list`, `cookbooks_list`, `preview`, `screens`, `vorlagen`, `operations_settings`, `branding_editor`, `display_settings`, `import_preview`, `api_overview`, `local_users_list` in `reference_scaffold/cafeteria/admin/`).
- Family-abhängige URLs: Patienten-Worktree-Test [`241-243`](reference_scaffold/tests/test_ui_master_shell_browser.py); Wochenplan-Landung über `landing: 'family'` [`_area_tabs.html:18-21`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html).
- Vorschau ohne Admin-Shell: [`preview.html:1`](reference_scaffold/cafeteria/templates/admin/preview.html) extends `base.html`; Sidebar-Landung explizit `screens` statt Preview ([`_area_tabs.html:30-33`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html), Test [`199-220`](reference_scaffold/tests/test_ui_master_shell_browser.py)).
- Einstellungen: Admin landet auf `operations`; Editor/Publisher auf erste sichtbare Tab (`import`) via `area_links()`-Fallback [`_workflow_sidebar.html:19-24`](reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html).
- Fallback `not tabler_admin` unverändert (alte flache Links) [`31-58`](reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html); Stringprüfung [`test_master_data_routes.py:387`](reference_scaffold/tests/test_master_data_routes.py).

### 3. Bereichs-Tabs `_area_tabs.html`

- Echte `<a href>`-Links, kein JS [`57:57`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html).
- Aktiver Tab per `workflow_nav` / Endpoint-Override (Preview, Display) [`5-14`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html).
- Wörterbuch §3.3: Bausteine, Zutaten, Bildschirme, Druckvorlagen, Bereiche & Öffnungszeiten, Erscheinungsbild, Daten importieren, Schnittstellen [`23-41`](reference_scaffold/cafeteria/templates/admin/_area_tabs.html).
- Einbindung unter Seitenkopf in [`base_tabler.html:27-28`](reference_scaffold/cafeteria/templates/admin/base_tabler.html).
- CSS: Primary-Text, helle Fläche, 2 px Unterlinie [`384-386`](reference_scaffold/cafeteria/static/admin-tabler.css); min-height 48 px (≥ 44) [`379-380`](reference_scaffold/cafeteria/static/admin-tabler.css); Wrap/Scroll < 768 px [`397-399`](reference_scaffold/cafeteria/static/admin-tabler.css); gemeinsame `container-xl`-Kante [`356-358`](reference_scaffold/cafeteria/static/admin-tabler.css).
- Keine dritte Shell-Ebene in Templates/CSS der Shell.

### 4. Geometrie / CSS

- Sidebar 248 px über `--app-sidebar-width: 248px` [`tokens.css:172`](reference_scaffold/cafeteria/static/tokens.css) und [`admin-tabler.css:310-311`](reference_scaffold/cafeteria/static/admin-tabler.css); Test messen 248 px [`302`](reference_scaffold/tests/test_ui_master_shell_browser.py).
- Sidebar-Einträge min-height 56 px [`111-112`](reference_scaffold/cafeteria/static/admin-tabler.css); Test ≥ 56 px / Schrift ≥ 15 px [`309-311`](reference_scaffold/tests/test_ui_master_shell_browser.py).
- Breakpoint 992 px: `navbar-expand-lg`, Offcanvas, Media Queries [`309,323,390`](reference_scaffold/cafeteria/static/admin-tabler.css), Test [`296-301`](reference_scaffold/tests/test_ui_master_shell_browser.py).
- Offcanvas: `tabindex="-1"`, `aria-expanded` am Toggler [`72-73`](reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html), Sync in [`admin.js:337-342`](reference_scaffold/cafeteria/static/admin.js); Fokus/Escape-Tests [`278-293`](reference_scaffold/tests/test_ui_master_shell_browser.py).
- Shell-Selektoren: nur `var(--app-…)` / Tabler-Mapping, kein Hex und kein `!important` in [`admin-tabler.css`](reference_scaffold/cafeteria/static/admin-tabler.css) (Shell-Bereich geprüft); keine Treffer auf `.public-page`/`.print-body`/`.signage-body`.
- Skip-Link vorhanden [`base_tabler.html:21`](reference_scaffold/cafeteria/templates/admin/base_tabler.html), CSS [`307-308`](reference_scaffold/cafeteria/static/admin-tabler.css).

### 5. Abmelden / Konto / Tab-Reihenfolge

- POST + CSRF Logout [`85-90`](reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html); Test [`248-261`](reference_scaffold/tests/test_ui_master_shell_browser.py).
- Konto-Block im Footer unverändert [`77-83`](reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html).
- Tab-Reihenfolge Skip → Menü → Sidebar (Offcanvas) → Tabs → Inhalt getestet [`387-415`](reference_scaffold/tests/test_ui_master_shell_browser.py); auf Seiten mit `page_header` liegen Header-Aktionen DOM-konform vor den Tabs (Master §7 / [`base_tabler.html:27-28`](reference_scaffold/cafeteria/templates/admin/base_tabler.html)).

### 6. Besitzgrenzen / Fremdtests

- Ein Ergebniscommit laut Worktree-Log: `3bc9185` — `feat(ui): flatten the admin navigation to four areas with in-page tabs`.
- Fremdtests strukturell an v2 angepasst, 44-px-Prüfungen erhalten: z. B. [`test_admin_shell_ui.py:122-140`](reference_scaffold/tests/test_admin_shell_ui.py) (≥ 44 px), [`test_ui_route_inventory.py:377`](reference_scaffold/tests/test_ui_route_inventory.py) (vier Sidebar-Namen), [`test_recipe_navigation_browser.py:50-75`](reference_scaffold/tests/test_recipe_navigation_browser.py) (Tabs statt Sidebar-Titel), [`test_week_management_browser.py:16-37`](reference_scaffold/tests/test_week_management_browser.py) (Tab + Offcanvas-API).
- Keine Abschwächung der Kontrast-/Overlap-Checks in der Shell-Suite [`317-330,431-445`](reference_scaffold/tests/test_ui_master_shell_browser.py).

### 7. Tests `test_ui_master_shell_browser.py`

- 9 Testfunktionen, 10 pytest-Items (Parametrisierung `width`) — passt zu Autoren-Gate „10 passed“.
- Abdeckung: vier Einträge je Rolle, Alt→Neu, aktiver Eintrag + Tab, Output-Landung, Offcanvas, 5 Viewports, Kontraste ≥ 4.5/3, No-JS-Tabs, Layout-Padding 32/24/16.
- Gate-Zahlen im Autorenbericht plausibel (10 + 183 Fremdtests); **nicht** in dieser Session neu ausgeführt.

### 8. Design-Qualität

- Keine erfundene Topbar; flache Sidebar + Bereichs-Tabs entsprechen Referenzpaket NAV-01/§3 und Shell-Spec §5–§8.
- Keine Demo-Buttons/Daten in Shell-Templates; „Publizieren“ nur in Seiteninhalt (`cafeteria.html`/`patienten.html`), nicht in Shell-Navigation.
- Profil-Pills bleiben Seiteninhalt (Autorenbericht bestätigt; kein Shell-Verstoß).

## Nicht geprüft

- **`rtk git diff --stat 514ced9..HEAD`** und Zeile-für-Zeile-Diff der Fremdtests (Shell-Aufrufe in dieser Session blockiert); Besitzgrenzen nur über Commit-Log, Autorenbericht und Stichproben der Fremdtests belegt.
- **Gate-Neulauf** (eigene Suite, 183 Fremdtests, Ruff, Pool-Wrapper) — nur Autorenbericht [`wp-52c02ef0f44d-v2.md`](file:///nvmetank1/projects/rag-stack/.claude/reports/wp-52c02ef0f44d-v2.md) plausibilisiert.
- **Token-/Komponentenblock** in `admin-tabler.css` vs. Basis `514ced9` (Diff fehlt); Shell-Abschnitt (`admin-sidebar`, `admin-area-tabs`) stichprobenartig geprüft.
- **OCR / Live-Browser-MCP / Screenshot-Pixelvergleich** gegen Referenzpaket-Sollbilder.
- **`mypy`**, **`tools/validate_package.py`**, GitNexus `detect_changes`.

WAVE-REVIEW: CLEAN
