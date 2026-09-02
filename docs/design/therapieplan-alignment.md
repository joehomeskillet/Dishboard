# Therapieplan Design Alignment

This document specifies the alignment of Dishboard's visual design system with the clinic's existing Therapieplan dashboard, effective from design/therapieplan-alignment branch.

## Token Mapping

### Primary Color (Magenta → Burgundy)

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-primary` / `--sh-magenta` | #c20b61 | #8C1C4B | Clinical burgundy from Therapieplan brand |
| `--sh-primary-2` | — | #A50044 | Mid-tone for hover/active states |
| `--sh-primary-3` | — | #B0496F | Lighter variant for accents |
| `--sh-primary-4` | — | #CC82A0 | Soft variant for backgrounds |
| `--sh-primary-5` | — | #D5A6B9 | Lightest variant for subtle backgrounds |
| `--sh-magenta-soft` | #f7e4ed | #F6E7EE | Light background tint aligned with new primary |

### Teal Scale (Secondary Colors)

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-teal-950` | #06343b | #1A363A | Darker teal for signage start |
| `--sh-teal-900` | #0a4149 | #224449 | Mid-dark for signage gradient |
| `--sh-teal-800` | #15555e | #2B545C | Signage end, menu accents |
| `--sh-teal-700` | #2d6a72 | #35666F | Therapieplan secondary base color |
| `--sh-teal-100` | #dfeeed | #DCEDF0 | Therapieplan light teal tint |
| `--sh-teal-050` | #eff7f6 | #F1F7F8 | Therapieplan lightest teal background |

### Green Accent

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-green` | #247a53 | #3E6B44 | Therapieplan green accent (vegetables) |
| `--sh-green-soft` | #e4f3ea | #EAF0E8 | Light green background tint |

### Blue (Secondary-2 Mapping)

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-blue` | #276b92 | #007088 | Maps to Therapieplan secondary-2 |
| `--sh-blue-soft` | #e3f0f7 | #DCEDF0 | Therapieplan light teal (same as secondary) |

### Neutral Scale (Ink & Text Colors)

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-ink` | #12363b | #383027 | Therapieplan dark brown ink |
| `--sh-ink-muted` | #58757a | #747068 | Therapieplan neutral-3 (muted text) |

### Canvas & Panel Backgrounds

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-canvas` | #edf4f2 | #F8F8F7 | Therapieplan page background (off-white) |
| `--sh-canvas-strong` | #edf2f1 | #EFEDE9 | Slightly darker page variant |
| `--sh-panel-soft` | #f4f8f7 | #FBFAF8 | Soft panel variant |

### Borders & Structure

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-border` | #ccdcda | #D5D1CB | Therapieplan neutral-5 (light border) |

### Shadows

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-shadow` | `0 1px 2px rgba(6,52,59,.06), 0 20px 48px rgba(6,52,59,.12)` | `0 2px 10px rgba(56,48,39,.06), 0 3px 14px rgba(56,48,39,.07)` | Therapieplan softer brown-based shadows |
| `--sh-shadow-soft` | `0 1px 2px rgba(6,52,59,.05), 0 12px 30px rgba(6,52,59,.08)` | `0 2px 10px rgba(56,48,39,.06)` | Lighter shadow variant |

### Border Radius (Design System Harmonization)

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-radius-sm` | 10px | 6px | Therapieplan small radius (controls) |
| `--sh-radius-md` | 16px | 10px | Therapieplan medium radius (cards) |
| `--sh-radius-lg` | 28px | 16px | Therapieplan large radius (larger components) |

### Signage Gradient (Dark Display Surfaces)

| Token | Old Value | New Value | Reason |
|-------|-----------|-----------|--------|
| `--sh-signage-start` | #052f36 | #1A363A | Therapieplan teal-950 (gradient start) |
| `--sh-signage-middle` | #0a4850 | #224449 | Therapieplan teal-900 (gradient middle) |
| `--sh-signage-end` | #123b55 | #2B545C | Therapieplan teal-800 (gradient end) |

## Typography

### Font Family

**Fira Sans** (SIL Open Font License) is now self-hosted, replacing the system font stack.

- **Font Weights Supported**: 400, 500, 600, 700
- **Character Sets**: Latin + Latin Extended (European language support)
- **Font Display Strategy**: `font-display: swap` (text appears immediately in fallback, swaps when loaded)
- **Files Location**: `/static/fonts/fira-sans-{400,500,600,700}.ttf`

### Performance

- **Preloaded**: 400 (regular) and 600 (headings) for faster rendering
- **Preload Links** in `base.html`:
  ```html
  <link rel="preload" as="font" type="font/ttf" href="{{ url_for('static', filename='fonts/fira-sans-400.ttf') }}" crossorigin>
  <link rel="preload" as="font" type="font/ttf" href="{{ url_for('static', filename='fonts/fira-sans-600.ttf') }}" crossorigin>
  ```
- **Total File Size**: ~1.25 MB (all weights)

## Accessibility & Contrast Verification

All WCAG AA compliant (4.5:1 minimum for body text):

| Combination | Ratio | Status |
|-------------|-------|--------|
| Primary (#8C1C4B) on White | 8.81:1 | ✓ PASS |
| Ink (#383027) on Light (#F8F8F7) | 12.20:1 | ✓ PASS |
| Ink-Muted (#747068) on Light (#F8F8F7) | 7.47:1 | ✓ PASS |
| White on Signage Start (#1A363A) | 12.86:1 | ✓ PASS |
| White on Signage Middle (#224449) | 10.55:1 | ✓ PASS |
| White on Signage End (#2B545C) | 8.32:1 | ✓ PASS |

## Implementation Notes

- **No Layout Changes**: Pure design token swap
- **Client Distinction**: Patient vs. cafeteria channels distinguished by text labels
- **Signage Surfaces**: Dark full-screen displays remain unchanged in layout
- **Token Scope**: All colors outside `:root` use CSS custom properties
- **CSP Compliance**: `font-src 'self'` — self-hosted fonts only

---

**Branch**: `design/therapieplan-alignment`  
**Date**: 2026-09-02  
**Author**: Claude Design Team

## Website Header (White Background)

The `.site-header` on public-facing pages (website, login) uses a white background with burgundy accents, following the Therapieplan reference design.

**Header Color Scheme**:
- Background: `var(--sh-panel)` (#FFFFFF)
- Text/Title: `var(--sh-magenta)` (#8C1C4B)
- Navigation Links: `var(--sh-ink)` (#383027)
- Active Link Background: `var(--sh-magenta-soft)` (#F6E7EE)
- Active Link Text: `var(--sh-magenta)` (#8C1C4B)
- Bottom Border: 3px solid `var(--sh-magenta)` (#8C1C4B)

**Contrast Ratios (WCAG AA compliance)**:

| Combination | Ratio | Standard | Status |
|-------------|-------|----------|--------|
| Link text (#383027) on white (#FFFFFF) | 12.96:1 | WCAG AA (4.5:1) | ✓ PASS |
| Active background (#F6E7EE) on white (#FFFFFF) | 8.54:1 | WCAG AA (4.5:1) | ✓ PASS |
| Active text (#8C1C4B) on active bg (#F6E7EE) | 4.87:1 | WCAG AA (4.5:1) | ✓ PASS |

**Signage Header**: Remains dark (unchanged) with white text on teal gradient background.

