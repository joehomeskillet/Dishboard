# Cross-Vendor-Review MP-UI-MACROS (wp-c011d6e56f9a)

| Feld | Wert |
|---|---|
| **Branch** | `feat/ui-macros-0911` |
| **HEAD** | `938481adea62db82a35c4dadbca73c7eb4834d40` (Autorbericht; `rtk git rev-parse` in dieser Session blockiert) |
| **Basis** | `c66b93ba494b59a797085c723e13aab99a36f324` |
| **Reviewer / Modell** | cursor composer-2.5 |
| **Autor / Modell** | antigravity-agy / gemini-3.8-flash-high |
| **Worktree** | `/nvmetank1/projects/menuplan/.claude/worktrees/ui-macros-agy-0911` |

---

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | [`reference_scaffold/cafeteria/templates/admin/_macros.html:110`](reference_scaffold/cafeteria/templates/admin/_macros.html) | `checkbox` setzt bei `readonly` Inline-Handler `onclick="return false;"`. Global gilt `script-src 'self'` ohne `'unsafe-inline'` ([`reference_scaffold/cafeteria/__init__.py:65-67`](reference_scaffold/cafeteria/__init__.py)); verstösst gegen Prüfpunkt 4 (CSP, kein Inline-Script) und macht Readonly-Schutz unter CSP wirkungslos. | **blocker** | Inline-`onclick` entfernen; Readonly-Checkboxen per `disabled` + Hidden-Feld oder rein serverseitig absichern; Interaktionssperre nur über [`admin.js`](reference_scaffold/cafeteria/static/admin.js) ohne Inline-Attribute. |
| 2 | [`reference_scaffold/cafeteria/templates/admin/_macros.html:123`](reference_scaffold/cafeteria/templates/admin/_macros.html) | Gleiches Inline-`onclick` in `check` (Radio/Checkbox-Alias); betrifft u. a. [`menu_editor.html:38-39`](reference_scaffold/cafeteria/templates/admin/menu_editor.html), [`components.html:50-51`](reference_scaffold/cafeteria/templates/admin/components.html). | **blocker** | Wie Nr. 1; für Radio-Readonly `disabled` + Hidden-Wert oder serverseitige Validierung. |
| 3 | [`reference_scaffold/cafeteria/templates/admin/_macros.html:56`](reference_scaffold/cafeteria/templates/admin/_macros.html) | Text-`field` setzt bei `readonly` nur HTML-Attribut `readonly`, nicht `aria-readonly="true"` (Checkbox/select haben es). | **minor** | `aria-readonly="true"` analog zu `select`/`checkbox` ergänzen. |
| 4 | [`reference_scaffold/cafeteria/templates/admin/_macros.html:99`](reference_scaffold/cafeteria/templates/admin/_macros.html) | `textarea` readonly ohne `aria-readonly`. | **minor** | Wie Nr. 3. |
| 5 | [`reference_scaffold/cafeteria/templates/admin/_macros.html:134`](reference_scaffold/cafeteria/templates/admin/_macros.html) | `form_errors` rendert Alert ohne `aria-live="polite"`; Autorbericht behauptet `aria-live` und Feld-Anker `#f_{{ field }}`, Implementierung liefert nur String-Liste ohne Feldbezug. | **minor** | `aria-live="polite"` ergänzen; bei strukturierten Fehlern (`{feld: msg}`) Anker zu `#{{ id }}` wie in SDD/Master §8 vorgesehen. |
| 6 | [`reference_scaffold/cafeteria/static/admin.js:115-121`](reference_scaffold/cafeteria/static/admin.js) | `focusFirstError()` fokussiert zuerst `.error-region`, überschreibt den Fokus sofort mit erstem `[aria-invalid="true"]`; Fehlerzusammenfassung wird für Screenreader praktisch übersprungen. | **minor** | Entweder nur Fehlerregion **oder** nur erstes Feld fokussieren; bei beiden `aria-live` auf der Region belassen und kein sofortiges Überschreiben. |
| 7 | [`reference_scaffold/cafeteria/templates/admin/_macros.html:276-308`](reference_scaffold/cafeteria/templates/admin/_macros.html) | `actions` rendert `secondary` vor `primary` im DOM; Tab-Reihenfolge kann Nebenaktion vor dominanter Aktion setzen (Master §8: eine dominante Aktion). | **minor** | Primary zuerst im Markup oder explizite `order`/Flex-Umordnung mit korrekter Tab-Reihenfolge. |
| 8 | [`reference_scaffold/tests/test_ui_master_components_browser.py:281`](reference_scaffold/tests/test_ui_master_components_browser.py) | Pill-Test prüft `borderRadius >= 10`, Kommentar verlangt „≥ 16 px (999px)“; Master §8 verlangt Pill-Form via Token `--app-radius-pill`. | **minor** | Schwellwert an Master/Token anbinden (z. B. `>= 16` oder explizit gegen `--app-radius-pill`). |
| 9 | [`reference_scaffold/tests/test_ui_master_components_browser.py:42-75`](reference_scaffold/tests/test_ui_master_components_browser.py) | Browser-Test deckt `checkbox`, nicht `check` mit `type='radio'` (Produktionsmuster in `menu_editor`/`components`); vier Zustände für Radio-Makro nicht abgesichert. | **minor** | Radio-Zustände (normal/readonly/disabled/checked) in Testseite und POST-Contract ergänzen. |

---

## Geprüft und in Ordnung

| Prüfpunkt | Beleg |
|---|---|
| **1 Abwärtskompatibilität (Aufrufer-Signaturen)** | 39 Importzeilen `from 'admin/_macros.html'` in [`reference_scaffold/cafeteria/templates/admin/`](reference_scaffold/cafeteria/templates/admin/) (inkl. Partials); stichprobenartig verifiziert: `page_header(title, description\|pretitle)` ([`week_management.html:5`](reference_scaffold/cafeteria/templates/admin/week_management.html), [`menu_editor.html:15`](reference_scaffold/cafeteria/templates/admin/menu_editor.html)), `{% call page_header(...) %}` ([`rezepte_revision.html:10`](reference_scaffold/cafeteria/templates/admin/rezepte_revision.html)), `field(name, label, value, …)` ([`patienten.html:105`](reference_scaffold/cafeteria/templates/admin/patienten.html)), `check(…, value, checked, type='radio')` ([`menu_editor.html:38`](reference_scaffold/cafeteria/templates/admin/menu_editor.html)), `check('roles', label, value, checked, id=…)` ([`_local_user_forms.html:12`](reference_scaffold/cafeteria/templates/admin/_local_user_forms.html)), `pagination(page, has_next, prev_url, next_url, label)` ([`rezepte.html:24`](reference_scaffold/cafeteria/templates/admin/rezepte.html)), `status(value, label)` / `status as status_badge` ([`week_management.html:51`](reference_scaffold/cafeteria/templates/admin/week_management.html), [`api.html:32`](reference_scaffold/cafeteria/templates/admin/api.html)). Rezept-Editor nutzt separates [`_rezepte_fields.html`](reference_scaffold/cafeteria/templates/admin/_rezepte_fields.html) für `maximum`/`multiline` — kein Bruch durch `_macros.field`. |
| **2 Feld-Makros: aria-invalid / aria-describedby / required** | [`_macros.html:50-58`](reference_scaffold/cafeteria/templates/admin/_macros.html): `desc_ids` für Hint+Error, `aria-invalid="true"`, echtes `required`; analog `select`/`textarea`/`checkbox`. |
| **2 Pagination nur bei echtem has_prev/has_next** | [`_macros.html:246-273`](reference_scaffold/cafeteria/templates/admin/_macros.html): Render nur wenn `eff_has_prev or eff_has_next`; `total_items` optional ([`269-271`](reference_scaffold/cafeteria/templates/admin/_macros.html)); Test [`test_master_pagination_behaviours:328-329`](reference_scaffold/tests/test_ui_master_components_browser.py). |
| **2 Status-Text sichtbar** | [`_macros.html:197`](reference_scaffold/cafeteria/templates/admin/_macros.html): `{{ badge_text }}` immer gerendert; Kontrast-Test [`test_master_status_badges_contrast_and_shape:266-287`](reference_scaffold/tests/test_ui_master_components_browser.py). |
| **2 Empty-State drei Arten** | [`_macros.html:208-224`](reference_scaffold/cafeteria/templates/admin/_macros.html); Test [`test_master_empty_states_three_kinds:290-307`](reference_scaffold/tests/test_ui_master_components_browser.py). |
| **3 Kein `safe`, Autoescape, Schweizer Schreibweise** | Kein `\|safe` in [`_macros.html`](reference_scaffold/cafeteria/templates/admin/_macros.html); Jinja-Autoescape default; Labels wie „Zurück“, „Bitte überprüfen Sie …“, „Veröffentlicht“ ([`172`](reference_scaffold/cafeteria/templates/admin/_macros.html)). |
| **3 Master §8 Status-Badges via Tokens** | Makro nutzt `bg-*-lt`; [`admin-tabler.css:256-307`](reference_scaffold/cafeteria/static/admin-tabler.css) mappt auf `--app-*-text/-soft`, Pill-Padding/Radius. |
| **3 Master §8 Interaktionshöhe** | [`admin-tabler.css:120`](reference_scaffold/cafeteria/static/admin-tabler.css) `min-height: 48px`; Test [`test_master_actions_and_focus_ring:341-344`](reference_scaffold/tests/test_ui_master_components_browser.py) `>= 44px`. |
| **4 admin.js: Hooks, kein neues Netzwerk, Escape** | [`admin.js:111-140`](reference_scaffold/cafeteria/static/admin.js) Fehlerfokus/`revealAncestors`; [`313-347`](reference_scaffold/cafeteria/static/admin.js) Escape für Dropdown/Tooltip/details; kein `fetch`/`eval`/`XMLHttpRequest`. |
| **4 NoJS-Parität (readonly POST)** | Test [`test_master_form_readonly_vs_disabled_post:234-255`](reference_scaffold/tests/test_ui_master_components_browser.py): readonly im POST, disabled fehlt; Flask-POST-Spiegel identisch. |
| **5 Besitz (Autorbericht + Dateiinspektion)** | Geändert/neu laut Bericht und Leseprüfung: [`_macros.html`](reference_scaffold/cafeteria/templates/admin/_macros.html), [`admin.js`](reference_scaffold/cafeteria/static/admin.js), [`test_ui_master_components_browser.py`](reference_scaffold/tests/test_ui_master_components_browser.py). Keine Seiten-Templates geändert. |
| **6 Teststruktur (statisch)** | [`test_ui_master_components_browser.py`](reference_scaffold/tests/test_ui_master_components_browser.py): echtes Chromium, `getComputedStyle`, Kontrast via `contrast()`, 5 Viewports ([`17-22`](reference_scaffold/tests/test_ui_master_components_browser.py)), NoJS-POST, Screenshots nach `tmp_path` ([`352-366`](reference_scaffold/tests/test_ui_master_components_browser.py)). |
| **7 Design-Qualität: kleine benannte Makros** | Separate Makros in [`_macros.html`](reference_scaffold/cafeteria/templates/admin/_macros.html); kein Mega-Schalter; leere Blöcke unterdrückt ([`page_header:12-47`](reference_scaffold/cafeteria/templates/admin/_macros.html)). |

---

## Nicht geprüft

| Bereich | Grund |
|---|---|
| `rtk git diff --stat c66b93b..HEAD` / vollständiger Diff | Shell-Aufrufe (`rtk git …`) in dieser Session abgelehnt; Besitzgrenze nur über Autorbericht + statische Dateiinspektion. |
| Gate-Ausführung (`worker-test-api3-gate.sh`, 43 passed / 2 Fremdfehler) | Kein Testlauf in dieser Session; Plausibilität nur anhand Autorbericht [`wp-c011d6e56f9a.md`](file:///nvmetank1/projects/rag-stack/.claude/reports/wp-c011d6e56f9a.md) und Testcode. |
| `ruff check`, `git diff --check`, `git status --porcelain` | Nicht ausgeführt (Shell blockiert). |
| GitNexus Impact / `detect_changes` | Worktree laut Bericht nicht indexiert; nicht nachgezogen. |
| OCR-Review-Gate | Autorbericht: API 429 / read-only FS — nicht wiederholt. |
| Visuelle Screenshot-Baselines | Pfade im Bericht nicht geöffnet/verglichen. |
| Vollständige 34-vs-39-Aufrufer-Zählung per `rtk grep` | Statisch per Workspace-`grep`: 39 Importzeilen; Abweichung zur Brief-Zahl 34 nicht per RTK verifiziert. |

---

**Fazit:** Makro-Architektur, Aufrufer-Kompatibilität und Testaufbau sind im Wesentlichen stimmig; zwei identische CSP-Verstösse durch Inline-`onclick` in `checkbox`/`check` blockieren die Freigabe.

WAVE-REVIEW: FINDINGS(9)
recorded 12550 wp_id=wp-cursor-run-2026-09-11T17:32:54.798970+00:00

[exited with code 0]
