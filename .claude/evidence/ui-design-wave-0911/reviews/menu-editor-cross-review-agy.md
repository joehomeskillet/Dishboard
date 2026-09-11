# Cross-Vendor-Review MP-UI-MENU-EDITOR (read-only)

- **Worktree:** `/nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911`
- **Branch:** `feat/ui-page-menu-editor-0911`
- **HEAD:** `9639a8fdcb8bf06ed080a7ad4b8626c080b8cc21`
- **Basis:** `e7845bf825a413f57956305b610a2f3657f9fead`
- **Reviewer:** Gemini 3.8 Flash (High) (agy, Claude Code Worker)
- **Autor:** Cursor Composer-2.5
- **Orchestrator:** Claude Code (claude-fable-5-1)
- **Modus:** Read-only (keine Dateiänderungen, keine Paketinstallationen, keine Commits)

---

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | [`menu_editor.html:132`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L132), [`menu_editor.html:141`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L141) | **Accessible Name vs. Visible Label Konflikt (WCAG 2.5.3):** Das sichtbare Label wurde auf «Baustein aus Katalog» (Z. 131) bzw. «Eigener Baustein als Text» (Z. 140) angepasst. Auf den Controls verblieben jedoch veraltete Attribute `aria-label="Komponente aus Katalog"` und `aria-label="Freitext-Komponente"`. Gemäss W3C AccName überschreibt `aria-label` das `<label for="...">`, sodass Screenreader weiterhin «Komponente» ansagen und der zugängliche Name den sichtbaren Begriff «Baustein» nicht enthält. | minor | Die redundanten Attribute `aria-label` auf `<select>` und `<input>` entfernen, da beide Controls über semantische `<label for="...">` eindeutig benannt sind. |
| 2 | [`admin-menu-editor.css:18-19`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/static/admin-menu-editor.css#L18-L19) | **Keine dynamische Modus-Umschaltung für Freitext:** Die CSS-Selektoren `:has(input[name="component_text"][value]:not([value=""]))` und `:not(:has(...))` prüfen nur das HTML-Attribut `value="..."`. Bei interaktiver Texteingabe im Browser ändert sich die DOM-Eigenschaft `.value`, nicht das Attribut. Die Modus-Anzeige (`.menu-editor-row-mode`) aktualisiert sich bei Benutzereingabe daher nicht dynamisch im Browser. | minor | Auf `:has(input[name="component_text"]:not(:placeholder-shown))` umstellen, da das Feld `placeholder="Freitext"` besitzt. |
| 3 | [`admin-menu-editor.css:31-32`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/static/admin-menu-editor.css#L31-L32), [`menu_editor.html:257-261`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L257-L261) | **Ungenutzte CSS-Token-Klassen in Review-Liste:** In der CSS-Datei sind `.menu-editor-review-label` und `.menu-editor-review-value` deklariert. In `menu_editor.html` werden die Review-Punkte jedoch als unstrukturierter Flashtext gerendert (`<li class="menu-editor-review-item">Labels: ...</li>`), wodurch das vorbereitete 2-Ebenen-Grid und die Muted-Tokens für Labels wirkungslos bleiben. | minor | Review-Listenelemente mit separaten `<span class="menu-editor-review-label">` und `<span class="menu-editor-review-value">` strukturieren. |
| 4 | [`test_ui_menu_editor_browser.py:276`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/tests/test_ui_menu_editor_browser.py#L276) | **Zoom-200%-Test deckt aktives JavaScript nicht ab:** In `test_zoom200_equivalent` wird der Browserkontext fest mit `java_script_enabled=False` erstellt. Obwohl die Fixture `editor_page` für `js` und `nojs` durchläuft, wird Zoom 200 % mit aktiven Client-Skripten (insb. `visualViewport`- und Sticky-Handler aus `admin.js`) nicht verifiziert. | minor | Den Context in `test_zoom200_equivalent` mit `java_script_enabled=javascript` an die Fixture koppeln. |
| 5 | [`menu_editor.html:95, 100, 174, 233`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L95) | **Zweispaltige Felder zwischen 576 px und 767 px:** Preisfelder, Allergenzeilen und Labels nutzen `col-sm-6`. Dadurch brechen sie ab dem Tabler/Bootstrap `sm`-Breakpoint (576 px) zweispaltig um. Gemäss Prüfpunkt 4 («Formulare einspaltig < 768 px») sollten Formularzeilen unterhalb von 768 px einspaltig geführt werden. | minor | Wenn strikte Einspaltigkeit bis 767 px gefordert ist, auf `col-md-6` umstellen. |

---

## Geprüft und in Ordnung

1. **Fach- und Formularvertrag byteweise identisch:**
   - Alle Feldnamen (`title`, `description`, `note`, `internal_chf`, `external_chf`, `component_public_id`, `component_text`, `allergen_mode`, `allergen_code`, `allergen_presence`, `origin_mode`, `origin_ingredient`, `origin_country_code`, `label_mode`, `label_code`), IDs, Actions (`/admin/{{ family }}/menu`), Methoden (`POST`), CSRF-Tokens (`_csrf`), versionierte Formtokens (`row_version`) und Buttons (`formaction="/admin/{{ family }}/menu?return_to=week"`) stimmen exakt mit dem Backend-Vertrag überein ([`menu_editor.html:59-66`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L59-L66) und [`workflow_partial_form.py:387-430`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/workflow_partial_form.py#L387-L430)).
   - Die drei Bindungsfelder (`allergen_mode`, `origin_mode`, `label_mode`) bleiben sauber erhalten. Bewusster Detach (`manual`) und Herkunftskonflikt (409 `AutoOriginConflictError`) funktionieren fehlerfrei ([`workflow_routes.py:516-520`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/admin/workflow_routes.py#L516-L520)).
   - Speichern und Prüfen bleiben strikt getrennt: Separates Review-Formular mit exakt den geforderten 7 Feldern inklusive `component_version` ([`menu_editor.html:270-280`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L270-L280)). Kein neues Panel und keine neue Speicher-API.
2. **Gefrorene Bausteine und Token-Treue:**
   - Layoutvariante über `{% set layout_variant = 'narrow' %}` deklariert ([`menu_editor.html:5`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L5)); Seitenkopf konsumiert `page_header` aus `admin/_macros.html` ([`menu_editor.html:16-18`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L16-L18)).
   - Keine Hardcoded-Hexfarben, kein `!important`, keine Inline-Styles/-Scripts in `menu_editor.html` oder `admin-menu-editor.css`.
   - `admin-menu-editor.css` nutzt ausschliesslich Design-Tokens (`var(--app-space-*)`, `var(--app-border*)`, `var(--app-surface*)`, `var(--app-radius-card)`). Keine Stilduplikate zu `admin-tabler.css`.
   - Sticky-Verhalten geprüft: `.review-block` wechselt unter 1200 px in `position: static` ([`admin-menu-editor.css:42`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/static/admin-menu-editor.css#L42)); `.admin-actions` wechselt bei Viewporthöhen <= 480 px in `position: static` ([`admin-menu-editor.css:43`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/static/admin-menu-editor.css#L43)).
3. **Wörterbuch §3.3 und Referenz E2 (1–4):**
   - «Baustein» durchgängig im sichtbaren UI verwendet und einmalig erläutert: «Zum Beispiel eine Beilage, Sauce oder ein Gemüse.» ([`menu_editor.html:113`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L113)).
   - «Eigener Baustein als Text» korrekt verwendet ([`menu_editor.html:125, 140`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L125)).
   - Genau eine dominante Primäraktion: `.btn-primary` für «Speichern» ([`menu_editor.html:242`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L242)). Nebenaktionen sind neutral.
   - Kontext Tag · Mahlzeit · Menüart im Seitenkopf vollständig abgebildet ([`menu_editor.html:9, 16`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L9)).
   - Ehrlicher Review-Bereich: Titel «Prüfung des gespeicherten Menüs», sauber differenziert zwischen «Nicht erfasst» und «Allergenangaben nicht erfasst» ([`menu_editor.html:253-261`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L253-L261)). Keine erfundenen Demo-Buttons oder Beispieldaten aus dem Sollbild übernommen.
4. **Master §8 und Ergonomie:**
   - Mindesthöhe aller interaktiven Steuerelemente (Buttons, Inputs, Selects) beträgt mindestens 48 px ([`test_ui_menu_editor_browser.py:141-144`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/tests/test_ui_menu_editor_browser.py#L141-L144)).
   - Bausteinzeilen besitzen einheitliche Geometrie mit Karten-Optik (`--app-surface-soft`, `--app-border`, `--app-radius-card`).
   - Fehlermeldungen sind adjazent am jeweiligen Feld platziert ([`menu_editor.html:74, 98, 153, 220`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/cafeteria/templates/admin/menu_editor.html#L74)) und mit `aria-describedby` verknüpft; `focusFirstError` fokussiert das erste fehlerhafte Feld.
   - Werte und Tokens bleiben bei Validierungsfehlern erhalten ([`test_ui_menu_editor_browser.py:204-223`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/tests/test_ui_menu_editor_browser.py#L204-L223)).
5. **Verifikationstests & Gate-Ergebnisse:**
   - Eigener Testlauf über den Pool-Wrapper ausgeführt:
     `rtk bash .../worker-test-iam-access-0908-gate.sh ... tests/test_ui_menu_editor_browser.py tests/test_admin_form_contracts.py`
     Ergebnis: **55 passed in 82.95s (GATE_EXIT=0)**. Die Testanzahl (24 Browser-Matrix-Tests + 31 Formular-Vertragstests) ist absolut plausibel.
   - `ruff check --no-cache reference_scaffold/tests/test_ui_menu_editor_browser.py`: **All checks passed!**
   - `git diff --check`: Keine Whitespace-/Formatierungsfehler.
   - `git status --porcelain`: Clean.
6. **Besitzgrenzen:**
   - `git diff --stat e7845bf..HEAD` betrifft exakt die 3 zugewiesenen Dateien:
     - `reference_scaffold/cafeteria/static/admin-menu-editor.css`
     - `reference_scaffold/cafeteria/templates/admin/menu_editor.html`
     - `reference_scaffold/tests/test_ui_menu_editor_browser.py`
7. **Design-Qualität («Swiss Editorial Calm»):**
   - Ruhiges, zurückhaltendes Erscheinungsbild ohne visuelle Unruhe oder zusätzliche Schlagschatten.
   - Fokus-Indikator gemäss Master: 2px solid Burgunder (`--app-focus`) mit sauberer Outline ([`test_ui_menu_editor_browser.py:167`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-menu-editor-cursor-0911/reference_scaffold/tests/test_ui_menu_editor_browser.py#L167)).
   - Textkontraste dynamisch nach WCAG 2.2 AA (>= 4.5:1) in `_capture` überprüft.

---

## Nicht geprüft

1. **Physische Screenreader:** Nicht mit NVDA / JAWS / VoiceOver auf nativen OS-Plattformen gegengelesen (accessible name computation wurde anhand des DOM-Inspektors und der W3C-Spezifikation verifiziert).
2. **Reale Touch-Geräte mit Bildschirmtastatur:** Nur über Playwright-Emulation (390×844) und Zoom-Äquivalent getestet; keine physische Hardware-Tastaturüberlagerung getestet.
3. **Open Code Review (OCR):** Fehlgeschlagen mit Rate Limit und schreibgeschütztem Dateisystem (`OCR: FAILED (429)`).

---

WAVE-REVIEW: FINDINGS(5)
