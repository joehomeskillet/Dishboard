# Visual inspection — MP-UI-INVENTORY before baseline

Proposed, never user-approved. Source 5f5 / schema 25. Playwright Chromium 151.0.7922.34,
locale de-CH, timezone Europe/Zurich, DPR 1. Synthetic isolated PG/Redis only.

Distinguish **source-discovered** (url_map + 75 templates) from **rendered and tested**
(111 local screenshots in `screenshots/`). Source-only rows are not visual acceptance.

## Samples inspected

| Sample | File | What was looked at |
|---|---|---|
| Admin week desktop | `admin_cafeteria-1440x900.png` | Shell, sidebar, hierarchy, overflow |
| Admin week mobile | `admin_cafeteria-390x844.png` | Hamburger, stacking, touch actions |
| Login | `auth_local-1440x900.png` | No admin sidebar, auth layout |
| Public cafeteria | `cafeteria_heute-1440x900.png` | White public, prices, no admin chrome |
| Signage closed | `signage_cafeteria_tag-closed-sunday-1920x1080.png` | Closed Sunday, no admin |
| Empty recipes | `admin_rezepte-1440x900.png` | Empty state vs pagination |
| Anonymous 401 | `admin_cafeteria-anonymous-401-1440x900.png` | Access denied |
| Editor 403 | `admin_benutzer-editor-403-1440x900.png` | Role gate |
| Editor nav | `admin_cafeteria-editor-nav-1440x900.png` | Conditional sidebar |
| Publish dialog | `admin_cafeteria-dialog-publish-1440x900.png` | Modal, not sidebar |

## Findings

### 1. Werkzeug English 401/403/404 instead of branded German access-denied

- **Issue:** Anonymous `/admin/cafeteria` and Editor `/admin/benutzer` render stock Werkzeug HTML (`Unauthorized` / `Forbidden` in English). Copy without a source week is stock `Not Found`.
- **Evidence:** `admin_cafeteria-anonymous-401-1440x900.png`, `admin_benutzer-editor-403-1440x900.png`, `admin_cafeteria_copy-missing-week-404-1440x900.png`.
- **Impact:** Masterprompt §3 requires login / access-denied / error pages in the shared brand, without an admin shell before login. Current gates work (401/403/404) but are not UI-migrated. Users get no German explanation and no login path.
- **Correction:** MP-UI-AUTH (and error shells for 404/400) must add branded templates without weakening `require_capability`. Do not treat Werkzeug pages as the target design.

### 2. Empty list still shows page navigation

- **Issue:** Recipes empty state shows “Noch keine Rezepte” and still renders Zurück / Seite 1 / Weiter.
- **Evidence:** `admin_rezepte-1440x900.png`.
- **Impact:** Masterprompt §2.1 forbids pagination controls when there is only one page. Confuses empty vs paginated.
- **Correction:** MP-UI-MACROS / MP-UI-RECIPE-LISTS: show count only when `not has_next and page==1`.

### 3. Sidebar is a flat ungrouped list

- **Issue:** Admin sidebar lists Wochenpläne through Design & Marke at similar weight; no task groups. Editor correctly hides Benutzer & Zugriff and Design & Marke; logout stays.
- **Evidence:** `admin_cafeteria-1440x900.png` vs `admin_cafeteria-editor-nav-1440x900.png`.
- **Impact:** Masterprompt §7 requires grouping by actual tasks and a clear active item. Role conditionals already work and must be preserved.
- **Correction:** MP-UI-SHELL regroup existing entries only; do not add invented items.

### 4. Dense inner week workspace vs unused outer margin

- **Issue:** Desktop week editor has large beige side margins while inner cards, small labels and many equal-weight actions stay dense. H1 is only slightly stronger than card titles. Mobile stacks with a hamburger; no horizontal document overflow measured.
- **Evidence:** `admin_cafeteria-1440x900.png`, `admin_cafeteria-390x844.png`; manifest `overflow_horizontal=false` on captured rows.
- **Impact:** Matches masterprompt §2.1. MP-UI-REF-WORKSPACE / tokens must raise type and control height together, not stretch cards full-bleed.
- **Correction:** MP-UI-TOKENS then MP-UI-SHELL / MP-UI-REF-WORKSPACE.

### 5. Font stack conflicts with the 2026-09-09 masterprompt

- **Issue:** Computed body/H1 fonts are Fira Sans (self-hosted woff2). Masterprompt requires Arial/Helvetica body and Georgia headings.
- **Evidence:** `tokens.css` `--sh-font` / `@font-face`; manifest `computed_fonts`; network loads `/static/fonts/fira-sans-*.woff2`.
- **Impact:** Pixel-equal migration against the masterprompt cannot start until MP-UI-BRAND-DECISION maps or rejects Fira vs Arial/Georgia. This inventory records the conflict.
- **Correction:** MP-UI-BRAND-DECISION before MP-UI-TOKENS overwrite.

### 6. Public and signage stay white and admin-free

- **Issue:** None as a leak. Public cafeteria shows both CHF prices; patient public was not used as a price check in this sample set (separate assertion exists in product tests). Signage Sunday closed is a real closed board, not an admin page.
- **Evidence:** `cafeteria_heute-1440x900.png`, `signage_cafeteria_tag-closed-sunday-1920x1080.png`.
- **Impact:** MP-UI-SPECIAL-OUTPUTS must keep this isolation while admin migrates.
- **Correction:** Regression, not a change in this WP.

### 7. Login has no admin chrome

- **Issue:** None. Local login uses `base.html` + auth card, no Tabler sidebar.
- **Evidence:** `auth_local-1440x900.png`.
- **Impact:** Preserve as the auth layout variant.
- **Correction:** MP-UI-AUTH may restyle the card; do not wrap login in `base_tabler.html`.

### 8. Copy form happy path not rendered

- **Issue:** `copy_get` resolves the previous week as source. Isolated seed has only the target week, so `/admin/cafeteria/copy?week=2026-08-31` is 404.
- **Evidence:** capture status 404 for that URL; source `workflow_routes.py:copy_get`.
- **Impact:** Copy HTML template is source-mapped (`admin/copy.html`) but not visually accepted.
- **Correction:** Follow-up capture with a synthetic prior week, or keep blocked. Not a fake pass.

### 9. Recipe revision detail not rendered

- **Issue:** Seed has no recipes. List empty and `/admin/rezepte/neu` were captured. Revision detail needs a persisted revision.
- **Evidence:** coverage block `recipe_revision_detail_entity`.
- **Impact:** MP-UI-REF-DETAIL before-image is missing.
- **Correction:** Later WP may add a synthetic recipe; this inventory does not invent one.

### 10. Publish dialog exists and is a real inventory row

- **Issue:** Dialog is not in the sidebar. With a reviewed week it opens, names KW 36, Abbrechen + Publizieren.
- **Evidence:** `admin_cafeteria-dialog-publish-1440x900.png`.
- **Impact:** MP-UI-WEEKS must migrate the modal, not only the page.
- **Correction:** Include `#week-publish-modal` in shell/week WPs.

## Overflow, console, requests

- Horizontal overflow: none recorded on captured viewports.
- Console/request “errors” are the expected 401/403/404 document responses, not JS exceptions.
- No live/production requests. No production persons.

## Baseline status

New proposed before-baseline only. Not user-approved. Not visual acceptance of the migration.
