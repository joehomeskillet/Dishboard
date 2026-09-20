# SDD — Semantic UI Language

## Problem
Dishboard modules must not invent their own labels, icons, status vocabulary or action placement. Inconsistent UI increases learning cost and creates avoidable errors.

## Architecture
Create a semantic presentation layer above templates. Domain/business code emits domain state; UI components map that state to semantic keys; registry resolves icon role and translation keys; locale resolves text.

## Components
- Icon
- IconButton
- IconLabel
- StatusBadge
- SymbolRow
- DietIcon
- AllergenIcon
- ActionMenu
- StatusBar
- FilterBar
- EmptyState
- ConfirmDialog

## Migration work packages
**WP0 Audit:** inventory all routes/templates/macros and current strings/icons.
**WP1 Registry:** implement semantic key schema, validation and duplicate detection.
**WP2 I18N:** central translation resolver and DE/EN seed locales.
**WP3 Shared components:** implement common macros/partials.
**WP4 Navigation/actions:** normalize navigation, CRUD, More menus, search/filter.
**WP5 Status/feedback:** normalize OK/warning/error/info/review/publish states.
**WP6 Food domain:** meals, diets, allergens, recipes, planning.
**WP7 Operations:** stock, shopping, ordering, costs, import/export, interfaces, users/settings.
**WP8 Responsive/A11y:** keyboard, tooltip, aria, touch targets, mobile.
**WP9 QA:** screenshots/regression tests and translation/pseudo-locale checks.

## Acceptance criteria
- no hard-coded duplicate synonyms for registered semantics;
- semantic keys validated centrally;
- icon-only policy enforceable;
- missing translation detectable;
- no status color-only;
- destructive controls labelled;
- week/menu cards use fixed symbol-row order;
- allergen editor uses progressive disclosure;
- DE and EN render without clipping;
- existing permissions/business validation unchanged.
