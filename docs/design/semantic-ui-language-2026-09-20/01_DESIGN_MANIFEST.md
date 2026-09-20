# Design Manifest — Symbols, Labels & Idiot-Proof Interaction

## Core model
`semantic_key -> icon token -> label key -> tooltip key -> aria key -> allowed presentation -> severity/color role`

ASCII tokens are documentation/fallback notation, not production artwork. Production uses one controlled icon family (Tabler where available; controlled custom SVG only where required, especially allergens).

## Presentation levels
1. **Icon only**: repeated, low-risk, universally recognized actions. Tooltip + aria required.
2. **Icon + short label**: default for important actions.
3. **Icon + explicit label + helper**: destructive, uncommon, safety-relevant, complex or first-use actions.

## Canonical verbs
- `Anlegen`: create a new object.
- `Hinzufügen`: attach an existing object to a collection/context.
- `Bearbeiten`: change data.
- `Öffnen`: view without implying edit.
- `Speichern`: persist edits.
- `Bestätigen`: confirm a decision/process.
- `Löschen`: destructive removal.
- `Archivieren`: retain but remove from active use.
- `Kopieren`: create duplicate.
- `Vorschau`: preview output.

Do not mix synonyms per module.

## Idiot-proof rules
- One obvious primary action per context.
- Put rare actions under `More`.
- Never make Save, Delete and Cancel visually equivalent.
- Explain consequences before destructive actions.
- Use sensible defaults; reveal exceptional details progressively.
- Do not show disabled detail controls for unselected options.
- Empty states contain state + one short explanation + next action.
- Error text says what happened and what the user can do.
- Status is icon/form + text when important; color is supplemental.
- Navigation remains icon + label on desktop.
- Minimum practical touch target: ~44x44 CSS px.
- Visible keyboard focus.
- Icon-only controls have tooltip and aria-label.

## Multilingual rules
- No literal UI text in templates except data content.
- Use stable keys such as `action.save`, `status.ok`, `allergen.milk`.
- Never build sentences by concatenating translated fragments.
- Support grammatical reordering via complete message keys.
- Do not encode language into semantic keys.
- Allow labels to grow ~40% without clipping.
- Do not use icon initials derived from translated words in production.
- ASCII codes are stable technical fallbacks only.
- Dates/numbers/currency use locale-aware formatting.
- Tooltips, aria labels, empty states and validation messages are translated too.

## Symbol row order
For menu/meal cards always: `[diet] [allergens] [properties] [review/status]`.
