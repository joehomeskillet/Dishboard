# API key channel and expiry policy

SEC002/005, approved by the requester through the orchestrator on 2026-09-12.

- `preview.read` remains the read-only draft capability. Each new key additionally
  requires an explicit selection of Cafeteria, Patienten, or both channels.
- Schema 30 adds a non-null `channels` array. Existing keys receive both channels,
  preserving existing access and expiry. New inserts have no channel default.
- Creation requires an aware future expiry no more than 90 elapsed days away.
  The UI proposes 30 calendar days; date input expires at 23:59:59 Europe/Zurich.
  Its maximum date is the latest whole local day inside the 90-day limit.
- Python and the SECURITY DEFINER database writer enforce the creation policy.
  The old six-argument writer is removed. Existing non-expiring keys stay valid
  and are visibly labelled as legacy keys without an expiry.
- All protected preview routes, including aliases using their decorated handler,
  reject unauthorized channels with 403 before loading draft data. `/keys/me`
  exposes the granted channels. Public published menus remain public.
- Create/revoke reject duplicate scalar fields, extra fields and query arguments
  without key or audit mutation. Existing role and CSRF checks remain required.
- API publication status and technical version metadata occupy separate sections.

Verification: focused PostgreSQL authorization, migration compatibility, expiry
boundaries, strict-form checks, and a no-JavaScript browser creation/revocation
flow. Independent review and release gates belong to the orchestrator.
