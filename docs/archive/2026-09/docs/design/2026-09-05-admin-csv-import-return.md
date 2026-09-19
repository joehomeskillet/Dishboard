# CSV import return destination

After a successful CSV import, the existing 303 redirect opens the imported
profile and week. It uses the already validated `profile_code` and `week_start`
from `import_csv`; the currently displayed/default calendar week is irrelevant.

For the week beginning 2026-08-31, the destinations are
`/admin/patienten?week=2026-08-31` and `/admin/cafeteria?week=2026-08-31`.
Signed tokens, authorization, CSV parsing, persistence and error responses retain
their current contracts.

Acceptance: both existing successful-import regressions assert HTTP 303, the
correct profile/week URL, and their existing persisted-grid invariants.
