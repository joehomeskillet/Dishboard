# wp-fbeb0d3c5233 — bounded recorder correction

Base4479604f0237c8009832692e0f3d3e526edd03ba. Own branch
fix/ui-inventory-provenance-font-0909; fetch github/main preceded worktree creation.
Only capture.py and test_ui_inventory_capture.py are changed source files.
No product code, original screenshots/manifests, DB, production or dependency changes.

Capture execution wp_id/lane/model are caller-declared or null/not_supplied.
The original Grok inventory identity stays separately in source_provenance.
Existing callers remain valid; no executor/model is inferred from routing.

The new browser test serves existing fira-sans-400.woff2 from127.0.0.1 only.
Its response is held until the browser reports loading and fonts.check=false,
then delayed another600ms. The test requires loaded FontFace, resource time>=600ms,
and actual CDP Fira Sans glyphs before taking delayed-fira.png. No screenshot
alone substitutes for those assertions. Existing slow-GIF/error/dialog/original
preservation tests remain present and passed. No115-image inventory was rerun.

## Actual gates

`rtk /root/.local/bin/ruff check --no-cache .claude/evidence/ui-inventory-grok-0909/capture.py reference_scaffold/tests/test_ui_inventory_capture.py`

Exit0, chunk4584b8: `All checks passed!`

`rtk /tmp/dishboard-shared-venv/bin/python -B -m pytest -q -p no:cacheprovider reference_scaffold/tests/test_ui_inventory_capture.py -k capture_provenance`

Exit0, chunk3169b3: `5 passed, 6 deselected in 1.54s`

`rtk /tmp/dishboard-shared-venv/bin/python -B -m pytest -q -p no:cacheprovider reference_scaffold/tests/test_ui_inventory_capture.py`

Exit0, chunk9d61ad: `11 passed in 6.57s`

`rtk /root/.local/bin/mypy --cache-dir=/tmp/menuplan-ui-inventory-provenance-font-0909-mypy --python-executable /tmp/dishboard-shared-venv/bin/python --follow-imports=silent --disable-error-code=import-untyped .claude/evidence/ui-inventory-grok-0909/capture.py reference_scaffold/tests/test_ui_inventory_capture.py`

Exit0, chunk679452: `Success: no issues found in 2 source files`
The existing import-untyped stub boundary is explicit; no dependencies installed.

`rtk git diff --no-compact --check`: exit0, chunkccf887, no diagnostics.
`rtk git diff --quiet 4479604 -- . ':!.claude/evidence/ui-inventory-grok-0909/capture.py' ':!reference_scaffold/tests/test_ui_inventory_capture.py'`
Exit0, chunk83d0bc: no tracked changes outside the two source files before new evidence.

## Graph and command receipts

Initial token-redacting host wrapper indexed in13.5s, but registered package name
menuplan and generated untracked AGENTS/CLAUDE/skills. These files are not staged.
Impacts against the proposed WT-name alias failed; each was retried identically:
`Error: Repository "ui-inventory-provenance-font-0909" not found.`
The unambiguous absolute WT path then returned _serve LOW/direct1 and served
LOW/direct4 (tests only), start LOW/direct0; private run_capture UNKNOWN/unindexed.
Manual search found its sole existing caller in test_ui_route_inventory.py:204.

Root explicitly authorized:
`rtk npx --no-install gitnexus analyze --index-only --skip-git --name menuplan-ui-inventory-provenance-font-0909`
It returned `Already up to date`, without changing the alias. Alias impact and
identical retry returned `Repository "menuplan-ui-inventory-provenance-font-0909" not found`.
Adding --force refreshed successfully11.9s:13,965nodes/27,141edges. The exact alias
now resolves; private recorder remains UNKNOWN. No generic main-graph claims.

Other recorded discovery errors, each with exactly one identical retry:
`rtk rg --files --hidden reference_scaffold/cafeteria/static/fonts .claude/skills/gitnexus -g '*.woff2' -g 'SKILL.md'`
Exit2 both: `.claude/skills/gitnexus: No such file or directory (os error 2)`;
the four real Fira asset paths were returned. Host skills were used instead.
`rtk rg -n 'mypy|strict|pythonpath|testpaths' pyproject.toml reference_scaffold/pyproject.toml`
Exit2 both: neither pyproject.toml path exists. Subsequent filename search found
no config; actual Ruff/Mypy ran directly with the authorized binaries above.
These were path/alias discovery failures, not provider failures or skipped tests.

OCR NOT RUN: known original429 and identical retry, Root forbids further calls.
DB/full matrix/full package/deploy/production checks NOT RUN: outside this bounded WP.
This is an author-verified private recorder fix, not full UI/SDD completion.
