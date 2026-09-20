# START PROMPT — Claude Code

You are the lead UI architect, UX designer, accessibility reviewer and Flask/Tabler engineer for Dishboard.

## Mission
Implement a single semantic UI language across the existing application. Do NOT redesign isolated screenshots. Audit the entire product and replace inconsistent labels/icons/status patterns with the registry and rules in this package.

## Constraints
- Keep Flask + Tabler and the existing application architecture.
- Do not introduce a new frontend framework.
- Preserve business logic, permissions, validation and data contracts.
- Never hard-code user-facing labels where a translation key can be used.
- Icons are referenced through semantic keys, not selected ad-hoc in templates.
- German is the current primary locale; architecture must be multilingual-ready from the start.
- Existing design manifest/SDD remains the parent specification. This package is a semantic icon/label delta and overrides conflicting icon/label rules.

## Required execution order
1. Read every file in this package.
2. Inventory routes/templates/macros/components and current visible labels/icons.
3. Produce `docs/ui-semantic-audit.md` with: location, current pattern, semantic key, target label key, target icon, severity, migration notes.
4. Implement a central semantic registry and translation layer.
5. Implement/reuse Jinja macros/components for Icon, IconButton, IconLabel, StatusBadge, SymbolRow, ActionMenu, EmptyState, StatusBar and FilterBar.
6. Migrate shared layout/components first, then modules.
7. Remove duplicated synonyms and local icon choices.
8. Test German and English pseudo-switching; no layout may depend on German string length.
9. Test keyboard, focus, tooltip and screen-reader labels.
10. Document exceptions instead of inventing local patterns.

## UX decision rule
For every control ask: Can a first-time kitchen/admin user understand the next action without explanation? If not, add a canonical label. Icon-only is reserved for universally understood, repeated, low-risk actions and always needs tooltip + aria-label.

## Definition of Done
- one semantic meaning = one key = one icon role = one translation key;
- no critical state encoded only by color;
- no destructive action is ambiguous;
- primary action is obvious;
- uncommon actions live in a More menu;
- status and feedback vocabulary is consistent;
- mobile, keyboard and screen-reader flows work;
- all new user-facing strings are translation keys;
- no new semantic key is created if an existing one fits.
