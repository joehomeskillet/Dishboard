# P5a catalog 390 px fixup — PARTIAL

Worktree: /nvmetank1/projects/menuplan/.claude/worktrees/p5a-catalog-390-0926
Branch: fix/polish-p5a-catalog-390-0926
Base: 40f4a8d3f8db17d4f722e6e7c6738b909741c0f8
No push, merge, rebase or branch switch. Scratchpad scripts unchanged.

## Cause and change

Inherited line-height 1.5 produced 19.5 px secondary text at 13 px and 21 px primary/meta at 14 px.
A shared --app-list-line-height: 20px now applies to all three existing role selectors.
This alone did not fix native scroll rounding: the shared mobile header retained a 33.59375 px title
(computed 33.6 px = 28 x 1.2) and 19.5 px status label, yielding a .09375 px page offset.
Mobile header titles now round upward to integer CSS pixels while preserving font scaling; mobile
status labels use the same 20 px token. Desktop header rules stay unchanged.
No module CSS, template, test assertion, or baseline changed.

## Measurements (real Chromium, existing catalog fixtures, both families)

| Metric | Before | After |
| --- | --- | --- |
| Primary/meta line-height | 21 px | 20 px |
| Secondary line-height | 19.5 px | 20 px |
| Mobile title height | 33.59375 px | 34 px |
| Mobile status label height | 19.5 px | 20 px |
| Mobile catalog row | 243 px | 242 px |
| Mobile primary summary bottom after native scroll | 844.09375 px | 844 px |
| Desktop catalog row at 1440 px | 56.5 px | 56.5 px |
| Desktop summary bottom | 449 px | 449 px |

Desktop half-pixel table border geometry is unchanged; text line boxes are integer.
Measured role font sizes/weights remain primary 14px/600, secondary 13px/400, meta 14px/400.
Colors remain rgb(31, 41, 55), rgb(89, 98, 115), rgb(31, 41, 55); fontStyle normal.
Supplementary matrix: /tmp/pytest-of-root/pytest-2309/test_typography_current_markup0/list-typography.json
That supplementary diagnostic used current user list selectors and reached an additional stale API
selector (td:nth-child(2) > div). It was not treated as a passing gate. Temporary diagnostic file removed.
Original gate matrix: /tmp/pytest-of-root/pytest-2310/test_list_typography_across_mo0/list-typography.json

## Commands and results

Before each gate: rtk pgrep -fc "python -m pytest"; every observed count below 22.

Original focused reproduction:
2 failed, 14 deselected in 7.98s
Both failures: assert (785.09375 + 59) <= 844

Final focused shell regression:
2 passed, 14 deselected in 9.23s
GATE_EXIT=0 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/p5a-catalog-390-0926/reference_scaffold

Full final gate:
rtk bash /tmp/claude-0/-nvmetank1-projects-menuplan/2f4bbcec-0188-43ba-9334-2cbe2fa40c97/scratchpad/gate.sh worker-test-recipe-template-editor-0908 /nvmetank1/projects/menuplan/.claude/worktrees/p5a-catalog-390-0926 -q tests/test_admin_shell_ui.py tests/test_ui_list_typography_browser.py tests/test_ui_master_tokens_browser.py tests/test_component_catalog_browser.py -p no:cacheprovider -p no:randomly --tb=short -rfE

FAILED tests/test_ui_list_typography_browser.py::test_list_typography_across_modules
1 failed, 52 passed in 306.30s (0:05:06)
GATE_EXIT=1 cwd=/nvmetank1/projects/menuplan/.claude/worktrees/p5a-catalog-390-0926/reference_scaffold

Failure: AssertionError: Benutzer: Datenzeile fehlt; selector .admin-users-row.
Current unchanged local_users.html uses list_row() / .admin-list-row, not .admin-users-row.
All 16 shell tests and all master-token/catalog tests passed.
Full 12-module, two-width role comparison remains open; no claim of a globally green typography gate.

## Review / limitations

OCR: FAILED — HTTP 402 from configured sambanova / Meta-Llama-3.3-70B-Instruct.
Session: 95091fc6-4023-44c7-9048-5822fc49701c.
"Review failed: 0 finding(s); 2 of 2 selected item(s) failed."
"review failed: all 2 file review(s) failed — check your LLM configuration and API key"
No retry on exhausted billing, no model/provider switch. No clean OCR claim.
Branch-range OCR not run after provider billing failure.
GitNexus impact twice: CSS target not found, risk UNKNOWN.
detect_changes(repo=menuplan) resolved another worktree; explicit target worktree is not indexed.
Thus no valid GitNexus flow verification; local explicit diff reviewed instead.
No additional full suite, separate lint/typecheck, cross-vendor judge or human visual acceptance.
Report kept here because user restricts all writes to this worktree; central report registration
and provider mark-down would write outside that boundary and were not performed.

