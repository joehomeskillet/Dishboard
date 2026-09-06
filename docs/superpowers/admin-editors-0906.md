# Admin corrections and usable editors — 6 September 2026

The user has moved visible admin functionality ahead of optional backlog extensions.
The existing Screens and Vorlagen hubs are navigation foundations, not completed editors.

## Immediate delivery

- All comparable menu cards in each week view share width and height at the current viewport.
  Preserve complete content, allergens, unknown-state warnings and 48 px controls.
  Reuse the preview's CSS subgrid pattern; no fixed-height clipping or JavaScript sizing.
- Remove the four Signage shortcuts and their sidebar heading; keep Screens and all routes.
- Show the actual eight public/signage targets inside the four Screens cards, with day/week
  selection, proportional previews and links to the full pages. Keep URLs and CSP unchanged.
- Extend global admin display preferences with text size, content width and menu images,
  alongside density. Every offered control has persistent, visible consumers and a preview.
  Defaults preserve the current appearance. Reset must say which saved values it changes.

## First functional print-template editor

Use the existing two fpdf2 weekly renderers for a bounded property editor. This is not a
universal JSON-to-PDF renderer, and does not imply approval or completion of a free-layout
canvas. The complete TPL-002 scope remains in BACKLOG.md. No new dependency is needed for
the first usable editor; pdfme remains a separate, conditional technology candidate.

The editor must provide an actual end-to-end operation: choose a template, edit supported
properties, save a draft, preview the selected saved week, activate a checked revision,
download through the same renderer, duplicate and restore an earlier revision.

### Ownership and persistence

One worker owns the entire print-template service, routes, form, preview, renderer adapters
and tests. Its namespace in the existing settings JSONB table is separate from display
preferences. No schema migration may collide with the reserved API migration 16 to 17.
No worker may modify the display worker's base template or shared admin CSS.

Use a validated, bounded document for each profile and explicit revision identifiers.
Update under a transaction and expected-version check, with safe initialization under
concurrent requests. A stale save or activation returns 409 and preserves the other edit.
Recheck current admin authority inside writes, using existing authorization conventions.
GET must not create records. Draft saves must not change active output. Active revisions
remain available until replaced, and restoring creates an explicit new current revision.
Application revision records are not a claim of database-enforced immutable audit history.

### Properties and rendering

Expose only properties that the renderer actually consumes: bounded header/footer text,
existing logo selection, approved existing palettes and installed fonts, readable type size,
page margins and cell spacing. Preserve the complete week and profile-specific orientations:
Cafeteria A4 portrait, Patients A4 landscape. Do not invent unsupported controls.

The selected active configuration must reach both existing profile PDF download routes.
Preview renders the same saved draft/configuration with the same function. The editor is
Tabler-native with a properties form beside the real PDF preview, and works on mobile.
Use existing style tokens; no arbitrary HTML, CSS, external resource URLs or filesystem paths
from form input. Image options refer only to existing allowlisted assets. Broader branding,
uploads, field rearrangement, food photos and symbol legends remain explicit TPL/BRD work
until their consumers are implemented and independently checked.

Every preview and download retains the existing overflow refusal. Activation must validate
the selected week, while future weeks are checked when printed. Never hide text or shrink
below readable limits to force success. Patient output remains free of prices in the full
rendered document. Unverified allergen data must remain visibly unverified.

### Acceptance

- Real PostgreSQL: read/write permissions, strict input validation, conflict handling,
  draft isolation, activation, duplication, restore and persistence across sessions.
- Real PDFs: both A4 orientations, one page, full week, complete glyphs, bounded settings,
  meaningful output changes, shared preview/download revision and explicit overflow errors.
- Real HTTP/browser: editable form, save/preview/activate/restore flow, two browser sessions,
  390/820/1440 widths, no overflow or CSP errors, keyboard access and 48 px controls.
- Independent root review/gates before merge; manifest, clean export package validation,
  deployment and live proof afterwards. External OCR failure is reported as unavailable.

## Integration boundaries

The API repair, public-screen layouts and these admin corrections continue independently.
Changes to shared registration or templates are integrated additively by root. No feature is
called deployed from a worker commit alone. Public-screen browser evidence does not replace
the separate physical Yodeck acceptance.
