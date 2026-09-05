# CSV preview: clear destination and next action

WP: `wp-b10784c82478`. Base: `e89872e4483132bff74b7df05634e740af5d01e0`.

## Purpose and scope

Kitchen staff must see which plan and week a checked CSV will update before choosing the import action. The current preview shows internal profile codes and a row count, but omits the target week even though `result.week_start` is already available. Retain the existing Fira Sans type, `--sh-*` tokens, native controls and quiet institutional presentation.

Only `reference_scaffold/cafeteria/templates/admin/import_preview.html`, a dedicated CSV section in `reference_scaffold/cafeteria/static/app.css` if existing classes do not suffice, `reference_scaffold/tests/test_admin_csv_preview_ui.py`, and this spec are owned by this WP. Routes, stores, shared JavaScript, existing tests and validation/token contracts stay with their existing owners.

## Visible states

- **No file checked:** compact heading and plain format guidance, labelled native CSV upload, primary action “Vorschau prüfen”, and a clear return to the plan overview. State explicitly that checking the file does not save a draft.
- **Valid file:** show “Bereit zum Import”, human profile label “Cafeteria” or “Patientenplan”, ISO calendar week and target Monday as a German-formatted date, and row count. Place this summary and primary “Geprüfte Datei importieren” before the secondary action for choosing another file. Retain the existing explanation that only the explicit import writes the draft. The return link targets the matching plan and checked week.
- **Invalid file:** show “Datei korrigieren” in a focusable alert region with the existing line/column/message details. Tell the user to correct the CSV and select the corrected file for another check. Do not render an import action or an import token. The corrected-file check is the primary action; retain a return link.

Only the checked valid result supplies profile/week summary values. Unknown/invalid metadata must not be guessed. Browser file controls cannot be repopulated after a server response; the copy explains the required re-selection. Existing server-sanitized patient issues are rendered unchanged.

## Layout and accessibility contract

- Preserve the base template, viewport metadata, skip link and `main-content` target. Use the admin body and wrapper conventions with a dedicated CSV page class; avoid the large public-page hero.
- At 390×844 and 1440×1100, the valid target profile, week and primary import action are visible without scrolling. Secondary upload controls follow that summary. No horizontal overflow.
- Every interactive target is at least 44×44 CSS pixels with visible keyboard focus. Every input retains a visible label. Error messages use `role="alert"`; readiness uses `role="status"` and readable text, never color alone.
- No inline script, event handler, style attribute or hardcoded color. Reuse existing token colors, radii and spacing; add only page-scoped CSS where necessary. Respect reduced motion through existing styles; no new animation is needed.
- Patient results contain no `preis|chf|rappen|kosten|price` vocabulary, including attributes. Human labels replace `patient` / `staff_guest` in visible copy.
- Upload form remains multipart POST with `_csrf` and `file`. Import form remains POST `/admin/import` with exactly `_csrf` and `import_token`. No fabricated token, changed validation or new dependency.

## Evidence and gates

Add a focused browser test module using the existing real local Flask/PostgreSQL fixtures, browser fixture and example CSV files. Drive the real file input and submit controls; observe responses and DOM, without injected markup or a made-up import token. Test empty, invalid and valid states, both profile summaries, ISO week/date, the primary action hierarchy, return-link context, patient vocabulary, keyboard focus, target sizes and overflow at both viewports. Preview must remain read-only, reusing existing import preview/store tests for the mutation contract.

Capture before/after screenshots of the local fixture at 390×844 and 1440×1100. Save fixture-only evidence under this worktree's `.claude/state/csv-preview-proof/`; no production browser, credentials or real user data. If the orchestrator's heavy-test slot is occupied, prepare the tests/capture path and wait for that slot.

Run Jinja syntax validation, scoped Ruff and pytest collection, then the focused browser suite plus existing CSV import tests when the orchestrator grants the slot. Before commit, run GitNexus on the actual worktree diff; root independently re-gates the combined change and deploys the next verified wave. Apply the design-validator dimensions against Dishboard's contract, never Scandi defaults; an unavailable external visual validator is reported as missing rather than passed.
