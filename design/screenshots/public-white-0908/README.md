# Public white design proof — 2026-09-08

The final candidate (white design `fae3a22` plus contrast fix `20f2821`) uses white
public and signage backgrounds. Public card status
bars share the card's rounded clipping. Patient meal headings and service times
remain readable when a browser reuses the old immutable branding stylesheet.

## Capture sets

- `before/`: original 424bfc1 fixtures and the actual public deployment captured
  read-only on 2026-09-08. Names beginning `live-` identify production; `fixture-`
  identifies deterministic project demo publications dated 2026-09-02.
- `after/`: **rejected intermediate candidate**. Screenshots expose white patient
  headings on white backgrounds. These images are not final acceptance evidence.
- `final/`: complete corrected local fixture matrix, captured through the actual
  Flask factory, HTTP routes, CSS and CSP. These are not deployment screenshots.

Each matrix covers four web routes at 390×844 and 1440×1100, and four signage
routes at 1920×1080 and 3840×2160. Public full-page images additionally inspect
prices, declarations and footer content. Native scrolling loads deferred images
before the full-page capture; missing offscreen images in `before/metrics.json`
were deferred loading, not failed asset requests.

Only six representative final images, the card close-up and matrix metrics are
versioned here. All original captures remain in the isolated proof worktree at
`/nvmetank1/projects/menuplan/.claude/worktrees/public-proof-0908/design/screenshots/public-white-0908`.

## Final measurements

From `final/metrics.json`: 16 views, all HTTP 200, white body backgrounds,
zero console errors, failed requests or missing loaded images. CSP is present on
every response; no session cookie was issued. No horizontal overflow, signage
vertical overflow or patient price text was detected.

The browser contrast regression tests exercise current and legacy branding CSS,
default and inverted custom palettes, and both patient routes at Full HD and 4K.
Every visible meal heading/time label must meet a 4.5:1 contrast ratio. The initial
failing measurement was 1:1; screenshot review identified the same missing text.

## Reproduce

Run from the repository root, using the existing environment and bundled browser:

```bash
rtk /tmp/dishboard-shared-venv/bin/python tools/capture_public_white_proof.py --source-root /path/to/candidate --output /path/to/evidence
```

Add `--live-url https://dishboard.joelduss.xyz` only for read-only production
captures. This helper records observations; acceptance comes from the browser
tests and visual inspection, not its exit code alone.

Focused browser gate, from `reference_scaffold`:

```bash
rtk /tmp/dishboard-shared-venv/bin/python -B -m pytest -q -p no:cacheprovider tests/test_public_equal_cards_browser.py
```

Focused browser gate: **24 passed in 35.85s**, including all 16 contrast cases.
Ruff and scoped Mypy passed. This proof lane's broader database attempt and
identical retry each yielded 32 passed and 28 setup errors because
`TEST_DATABASE_URL` was absent. These are not passing database gates. The earlier
broader UI run yielded 115 passed and 14 database-dependent skips.

The orchestrator subsequently reserved an isolated PostgreSQL pool, independently
reviewed the exact fix and ran the six relevant branding/browser suites:
**64 passed in 171.95s; GATE_EXIT=0**. Root Ruff and Mypy also passed before the fix
commit. GitNexus staged analysis of the registered proof worktree confirmed three
expected changed files, four changed symbols, zero affected processes, LOW risk.

OCR was unavailable after the orchestrator's two real provider failures; no
provider was switched. Independent root review and database gates passed. The
complete SDD, full release package gate and deployment are outside this proof's
verdict.
