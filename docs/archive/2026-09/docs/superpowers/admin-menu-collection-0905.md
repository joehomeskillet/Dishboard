# Admin Menüs collection

Selected concept: ASTRA. Show complete saved menu occurrences across weeks, scoped
to the active location and selected profile. Purpose: find a menu by title or
component and open its original planning slot. Keep the calm Südhang typography,
existing tokens and sidebar; dates and meal labels distinguish repeated titles.

GET `/admin/<family>/menues` requires `draft.read`, rejects scope overrides,
validates bounded query/page inputs and never mutates drafts. Fetch 24 rows plus
one next-page sentinel in stable date/meal/type/id order. Literal search escapes
SQL wildcard characters. Saved components, labels, origins and allergens stay
visible; stale component versions force an open review indication. No recipe
entity, deduplication, inferred declarations or copy action. Patient pages have
no prices. Empty and filtered-empty states link back to planning.

Validation: real PostgreSQL route/store tests for location/profile isolation,
literal search, pagination, stale review, escaped metadata and read-only behavior;
existing sidebar/render regressions. No new dependency or schema changes.
