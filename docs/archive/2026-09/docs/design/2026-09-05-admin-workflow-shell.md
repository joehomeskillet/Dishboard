# Admin workflow pages: restore the shared navigation shell

WP: `wp-632550396a21`. Root approved this contract before implementation.
Base: `082b815ff3cb928b26724bddc9d22648675338a2`, fetched from `github/main` on 2026-09-05.

## Problem and evidence

The live screenshots in `.claude/state/handover-2026-09-05/proof/release-082b815-rotated/` show the menu editor, catalog and component detail confined to the first 270 px desktop column, with no visible administration navigation and an empty main column. Each template places only `main.admin-main` inside `.admin-shell`; the shared stylesheet defines two columns, `270px minmax(0,1fr)`. Working weekly overview pages include the sidebar before main.

## Contract

Add one shared `admin/_workflow_sidebar.html` partial, using the existing sidebar brand, user, role and navigation structure. Each of the three workflow templates includes that sidebar before its existing main element. The main ID, `data-*` attributes, native controls, form fields, actions, CSRF bindings and JavaScript hooks remain intact.

Navigation links retain the current URL family. Menu editor marks weekly plans current; catalog and component detail mark components current. The weekly link includes `week` only when the context provides a non-empty value; no missing-value or `Undefined` query strings. Logout remains a separate native POST with the regular CSRF token. Reuse the existing brand assets and safe default user label.

The pages keep the existing two-column desktop shell and its one-column mobile breakpoint. Any additional CSS belongs exclusively to `.admin-workflow-*` selectors, supplying scoped main spacing, safe minimum widths and real label target sizing where needed. Native keyboard navigation, visible focus, skip link, safe-area handling, CSP and the patient vocabulary restriction remain binding. No dependencies or inline styles/scripts.

Purpose is to restore familiar navigation and readable working space; tone and existing visual identity remain unchanged. The explicit action on the current form remains easy to locate. This package does not redesign week grids.

## Approved page completion

Root extended this package to close the visible issues on these same three pages. Menu editor uses the existing `date_long` filter and optional cell display labels for a readable slot heading. Where cell labels are absent, the template uses the same two meal and option labels already defined by the rendering contract. Saving uses the existing primary button style. No new backend label mapping or filter.

Move the complete existing `#create-component` details element before the catalog filter/list. Its summary becomes a visible primary action with a measured 44 px target. Keep its initial closed state, native click-to-open, Escape-to-close and focus restoration exactly as tested. Root explicitly retained this disclosure contract instead of the earlier proposed always-visible form and jump link. Existing category/scope/usage spans receive scoped layout separation.

Component detail and the existing create form use local field groups for consistent labels, controls and adjacent errors. Allergen rows use scoped responsive layout. Names, actions, modes, successful-control handling and input validation remain unchanged. Root will assess fresh live screenshots after the shell deployment; these changes do not constitute blanket visual acceptance.

## Ownership

- `reference_scaffold/cafeteria/templates/admin/menu_editor.html`
- `reference_scaffold/cafeteria/templates/admin/components.html`
- `reference_scaffold/cafeteria/templates/admin/component_editor.html`
- New `reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html`
- New `.admin-workflow-*` section only in `reference_scaffold/cafeteria/static/app.css`
- New `reference_scaffold/tests/test_admin_shell_ui.py`
- This specification

Weekly overview, Copy, CSV, Preview, JavaScript, production Python, parsers and stores belong to other packages. Existing shared CSS sections remain unchanged. Root integrates independently owned CSS additions.

## Acceptance and verification

Exercise both URL families and all three page types at 390x844 and 1440x1100 using real browser rendering and existing application fixtures. Check actual sidebar/main structure and positions, usable desktop main width, no horizontal overflow, scoped navigation and active state, normal logout form, skip-link target, visible keyboard focus, and label/input hit target rectangles of at least 44 px. Preserve primary form field names and current selected catalog associations. Check patient page text/attributes against the forbidden vocabulary and retain CSP.

Static checks: template parsing, scoped Ruff, whitespace diff check and GitNexus change-scope analysis. Browser tests start only after root releases the shared heavy-test slot. Root independently reviews, runs integration gates and supplies fresh live proof after deployment. Existing screenshots prove the defect; they do not prove the repaired layout or full visual acceptance.
