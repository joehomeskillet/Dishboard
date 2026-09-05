# Week overview: visible status and native actions

WP: `wp-bbe38eb3f8e2`. Freshly fetched base: `77422d91cf1eedbf29404db3fdeb941c9b0d4056`.

## Problem and purpose

The published audit under `.claude/state/handover-2026-09-05/proof/release-77422d9-csv/` shows that both overview pages put publication controls below a long week grid. The action container is explicitly static. The patient header exposes a row-version number as “Arbeitsstand” while omitting the supplied human workflow status. Cafeteria service controls are stacked in a fixed 118-pixel column, and the week-title controls inherit unsuitable narrow-grid layout.

Kitchen staff should immediately see the selected calendar week, its current status, remaining checks, and the next possible action. They should retain access to that action while reviewing the grid. Keep the existing Fira Sans, Dishboard tokens, native forms and calm operational presentation.

## Ownership

- `reference_scaffold/cafeteria/templates/admin/cafeteria.html`
- `reference_scaffold/cafeteria/templates/admin/patienten.html`
- One dedicated overview section in `reference_scaffold/cafeteria/static/app.css`; every new rule must be limited to overview-only classes.
- New `reference_scaffold/tests/test_admin_week_ui.py` and this spec.
- Only the relevant overview status/action paragraphs in `docs/design/admin-redesign-ui.md`, if the rendered contract needs clarification.

No Python, shared JavaScript, store, migration, menu editor, catalog/detail or preview changes. Other writers own those surfaces. Shared selectors such as `.admin-actions[data-sticky]` must not be changed globally.

## Status and action hierarchy

1. Place the existing `weekbar` and the one existing native action group together before the editable header fields and the week grid. Move explanatory raster copy below this group. Use `status_label` and `status` on both pages; the patient page must no longer show `week_row_version` as a user-facing status.
2. Count only existing menu cards (`row_version > 0`) whose existing `cells[*].review_open` flag is true, labeled “Menükarten mit offener Prüfung”. Empty grid slots are not menu cards. The supplied week status stays authoritative: when it is `review_open` but the flag count is zero, show “Erneute Prüfung erforderlich”, never “Keine offenen Prüfungen”. For other statuses, zero can say “Keine offenen Prüfungen”; empty/incomplete guidance must remain explicit. Do not invent backend state or infer completion from only the first option in a meal.
3. Move, never clone, the original publication form. Preserve exactly `_csrf`, `week`, `row_version`, its endpoint, button label “Publizieren”, and native confirmation. Each page retains one publication form and one action group. Retain “Vorschau” and “Vorwoche kopieren” links, preview's new-tab/noopener attributes, and existing accessible routes.
4. Explain blocked publication beside its disabled action: empty → first enter dishes; incomplete → complete the week; review_open → finish the open checks. Both pages block these three statuses consistently. Other supplied statuses retain their existing server-governed publication behavior. Do not change authorization or server validation.
5. Preserve dirty-state hooks: the shared script must still disable preview/publication and say “Zuerst speichern” after a native input edit. No duplicate IDs, CSRF controls, hidden versions or extra submit payload fields.
6. After relocation, the week/status, publication action and any blocking reason are visible on initial load at 390×844 and 1440×1100. Secondary CSV navigation and raster guidance must not push this group below the initial viewport.

## Sticky behavior and form ergonomics

- Add an overview-only class to each page shell/main. Make the combined week/action group sticky at the top within the main content, and keep that overview's title bar static so two sticky regions do not overlap. Use existing token backgrounds/borders and safe-area padding. The group remains in normal document flow; controls and focus targets must not be hidden underneath it when navigating the page.
- At very short viewport heights, prefer a static action group over a sticky region that occupies most of the screen. Preserve initial action placement in either case.
- On narrow overview pages, keep the existing sidebar links in a two-column grid so navigation retains its 44-pixel targets without pushing the first action out of the viewport.
- Render week title and shared notice in usable full-width fields: two columns on desktop, one on narrow screens, with the existing explicit “Wochenangaben speichern” submit button.
- Give each cafeteria day a full-width service band above its two menu cards. Align state, notice and save controls across that band instead of the 118-pixel column. On mobile, wrap the controls without shrinking any target below 44×44 pixels. Preserve each existing service form, labels, service CAS version, day/meal payload and slot order.
- Keep all 10/28 slot wrappers and their `data-*` values, titles, edit links and review badges. Patient wording remains free of `preis|chf|rappen|kosten|price`, including attributes. No hardcoded colors, inline styles/scripts/handlers, new dependencies or new animation.

## States and evidence

The new browser tests must exercise empty, incomplete, review-open and ready overviews using real local fixtures. Native forms, their exact successful controls and server-produced status remain the basis of the test; no injected DOM or hand-built browser payload replaces the actual UI. Include both profiles and 390×844/1440×1100.

Verify initial week/status/open-check count and action visibility, specific block guidance, one publication form, preserved confirmation, dirty-state disablement, target sizes, keyboard focus and sticky behavior after scrolling. Verify header/service native round trips retain their expected CAS payloads. Inspect all controls for viewport overflow and overlap; specifically prove the cafeteria service group and week title are no longer constrained by the old narrow column.

Capture before/after local-fixture screenshots in both viewports, with screenshots configured as `caret='initial'` so the capture tool cannot inject empty style attributes before the strict CSP assertion. Production audit images are read-only baseline context, never a target for mutation or fabricated successful states.

Run focused new/affected overview browser and rendering tests only when the root grants the heavy-test slot. Run scoped static checks, GitNexus impact before existing symbol changes and own-worktree detect_changes before committing. Root reviews the combined diff, independently re-runs gates and deploys the verified wave.
