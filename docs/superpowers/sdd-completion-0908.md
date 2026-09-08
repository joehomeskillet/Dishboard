# SDD completion and public display refinement — 8 September 2026

Base: `424bfc1` from freshly fetched `github/main`. Integration branch:
`integrate/sdd-public-0908`; all existing worktrees and untracked handoffs remain protected.

User direction: continue current implementation until the SDD is complete. Public displays
should be minimal, attractive and white. Remove redundant colored presentation variants;
retain distinct information layouts where the SDD requires them. Inspect real screenshots
and correct the upper card edges. This direction supersedes older colored-background styling.

## Delivery sequence

1. Read-only audit: identify current binding specifications and remaining requirements with
   exact implementation evidence. Separate application requirements from external acceptance.
2. Public visual refinement: cohesive white surfaces, restrained accents, consistent nested
   card corners, readable typography, responsive spacing and accessible navigation.
3. Browser evidence: capture the current public/signage pages, inspect images, verify mobile,
   desktop, 1080p and 4K layouts. Use deterministic local fixture evidence for populated states
   where production has no current published menu; label fixture and live evidence separately.
4. Close remaining verified SDD gaps in bounded packages after the audit, with contract and
   consumer ownership assigned together.
5. Independently review each diff, run appropriate real-binary tests/lint/type checks, run
   GitNexus change detection and OCR; integrate only reviewed commits. Preserve gate failures
   and explicit skips. No claim of deployment or full acceptance without corresponding proof.

## Initial parallel ownership

| Package | Responsibility | Branch / worktree |
|---|---|---|
| wp-b71c624714aa | Read-only SDD and current implementation audit | shared tree, read-only |
| wp-655add115644 | Public/signage CSS and template visual refinement | `fix/public-white-0908` / `public-white-0908` |
| Public proof | Runtime discovery, before screenshots and browser validation | `test/public-proof-0908` / `public-proof-0908` |

Screenshots must be visually inspected. Automated dimensions alone do not establish design quality.
Patient outputs stay free of price vocabulary. Existing CSP and signage query rejection stay enforced.
No dependencies, credentials in reports, production fixtures, or shared main-tree edits.

## Verified discovery and first review

- Existing execution plan `backlog-execution-0906.md` preserves the entire extended backlog.
  The public refinement is one delivery within that goal, not a completion of all requirements.
- Screen assignment and the recipe editor exist in `424bfc1`; older backlog status paragraphs
  are not evidence that they are absent. Live still runs `783fab3`; current public menu and
  both health endpoints returned HTTP 200 on 8 September.
- Prior candidate/fallback suites finished with 5318/5316 passing tests and 15 opt-in skips.
  Both overall package gates failed because their exports contained eight bytecode-cache
  directories. New release proof needs a clean archive and a fresh complete package gate.
- Browser-MCP failed twice during Chromium sandbox initialization. Existing project-native
  Playwright launched successfully and captured 32 baseline views (fixture and live).
- Visual review confirmed straight status bars extending across rounded card edges, heavy
  dark signage backgrounds, and exact duplicate component descriptions on public fixture cards.
- First author commit `ade6be4` changes six CSS/public-template files. Independent screenshots
  exposed white-on-white patient meal headings. Computed browser styles traced this to the
  later generated branding stylesheet, not the patient templates. WP `wp-d7fe52dcb22b` owns
  the independent correction and its regression coverage before release.

## Reviewed public refinement

Integrated author commits: `ade6be4` (white surfaces and duplicate descriptions), `20f2821`
(branding contrast and retained cached stylesheet compatibility), `7ad735d` (browser evidence).
The correction deletes obsolete generated meal-header overrides and gives the three canonical
signage text selectors precedence over earlier immutable branding CSS. Brand tokens remain supported.
GitNexus impact on `branding_css`: LOW, two direct callers (`stylesheet`, `branding_preview_css`),
one affected flow; staged change detection matches the expected files.

Fresh independent Root gates:

```text
2039 passed in 140.91s (0:02:20)
64 passed in 171.95s (0:02:51)
GATE_EXIT=0
All checks passed!
Success: no issues found in 1 source file
2 commits scanned.
no leaks found
```

The 2039-test selection covers public contracts/copy, image-free weeks, UI contracts and all
three signage rendering modules. The 64-test selection uses an exclusive PostgreSQL/Redis pool
and covers branding routes, browser/header/logo behavior, cached revisions and card/contrast
regressions. Ruff covers changed Python source/test and capture helper; Mypy is scoped to the
changed production module, not a claim of a globally clean type check. Gitleaks scans the two
product commits. [Committed screenshot evidence](../../design/screenshots/public-white-0908/README.md)
includes a complete 16-view final metric matrix and seven representative PNGs. Raw baseline,
rejected intermediate and additional final images remain protected in the proof worktree.

OCR failed twice with HTTP 429 and zero completed file reviews; no CLEAN result is claimed.
Bandit emitted an internal analysis exception twice despite exit zero, so its check is unavailable.
The full package gate and deployment remain pending; none of these focused checks closes the
entire SDD/backlog goal.

## Remaining scope

The read-only audit report is `/nvmetank1/projects/rag-stack/.claude/reports/wp-b71c624714aa.md`.
Verified wider gaps include the free PDF layout editor, complete template hub categories and
login/logout access history. Recipe import/search/planning, inventory, calculation and external
integrations retain their full backlog contracts. Physical player and kitchen acceptance need
actual external evidence; browser screenshots do not replace them.
