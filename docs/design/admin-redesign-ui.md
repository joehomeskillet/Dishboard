# Admin-Redesign — DOM- und Kontext-Vertrag

Verbindlich für Render-Adapter, Platzhalter-Templates und Admin-Rendertests.
Visuelle Ausgestaltung (CSS/JS, echte Layout-Templates) liegt bei den UI-Lanes.
Dieses Dokument friert Kontext-Keys, Statuswerte und die DOM-Selektoren ein.

## Adapter (`cafeteria.admin.rendering`)

Reine Rendering-Funktionen, kein DB-Zugriff. Datenbeschaffung bleibt in den Handlern.
`family` ist `cafeteria` für `staff_guest` und `patienten` für `patient`.

### `render_admin_week(profile, family, week, scope, status, draft, versions, csrf, flashes)`

Template: `admin/cafeteria.html` bzw. `admin/patienten.html`.

| Key | Inhalt |
|---|---|
| `profile` | `staff_guest` \| `patient` |
| `family` | `cafeteria` \| `patienten` |
| `week` | `date` (ISO-Montag) |
| `week_iso` | `week.isoformat()` |
| `iso_week` | Kalenderwochennummer |
| `status` | `empty` \| `incomplete` \| `review_open` \| `ready` \| `live` \| `changed` |
| `status_label` | deutsch: Leer, Unvollständig, Prüfung offen, Bereit, Live, Geändert |
| `csrf` | scoped `_csrf` für Zweck `overview` |
| `flashes` | HTML-String aus `_flash()` |
| `week_row_version` | int, `0` wenn die Woche fehlt |
| `title` | Wochentitel, leer wenn keine Woche |
| `shared_note` | Wochenhinweis |
| `cells` | Liste in Rasterreihenfolge Tag → Mahlzeit → Option |

Zelle:

| Key | Inhalt |
|---|---|
| `day` | ISO-Datum |
| `day_label` | Montag … Sonntag |
| `day_short` | z. B. `31. August` |
| `meal` | `LUNCH` \| `DINNER` |
| `meal_label` | `Mittag` \| `Abend` |
| `option` | `MENU_1` \| `VEGGIE` |
| `option_label` | `Menü 1` \| `Vegetarisch` |
| `row_version` | int, `0` = virtueller Slot |
| `title` | Gerichtstitel, sonst leer |
| `components` | Liste von Strings |
| `review_open` | bool |
| `service_state` | `open` \| `closed` \| … |
| `edit_url` | GET `/admin/{family}/menu?week=&day=&meal=&option=` |
| `internal_chf` / `external_chf` | nur `staff_guest`; formatiert `9.50`, leer wenn 0 |

Patient-Kontext enthält keine Preis-Keys.

### `render_menu_editor(profile, family, week, cell, form_values, form_errors, csrf, review_token, catalog_choices, allergens, labels, flashes, origin_conflict=None)`

Template: `admin/menu_editor.html`. Formularfelder exakt gemäss `workflow_partial_form.py`.
Bei Herkunftskonflikt: HTTP 409, `error-region` mit dem kanonischen `ORIGIN_CONFLICT`-Text.

### `render_components(profile, family, rows, query, category, include_archived, csrf, flashes, categories)`

Template: `admin/components.html`.

### `render_component_detail(profile, family, component, csrf, flashes, categories)`

Template: `admin/component_editor.html`.

### `render_admin_preview(profile, family, week, state, draft)`

Template: `admin/preview.html`. Nur LAST-SAVED, kein Publikations-Fallback.

## DOM-Vertrag

### Wochenübersicht (`GET /admin/cafeteria`, `GET /admin/patienten`)

- Wrapper `<main id="main-content" class="admin-main" data-profile="{profile}" data-family="{family}" data-week="{ISO-Montag}" data-status="{status}">`.
- Flash-Region `<div class="flash-region" aria-live="polite">` immer vorhanden.
- Fehlerregion `<div class="error-region" role="alert" tabindex="-1">` nur bei Fehlern.
- Hidden `_csrf` und `week` im Übersichts-Formular (`name` vor `value`).
- Genau 10 (`staff_guest`) bzw. 28 (`patient`) Slots:
  `<article class="menu-slot" data-day="…" data-meal="…" data-option="…" data-row-version="…">`
  mit `<h3>` (leer → „Noch kein Gericht"), `<a class="btn" href="{edit_url}">Bearbeiten</a>`,
  `<span class="slot-badge" data-review="open|checked">` plus deutschem Text
  (`Prüfung offen` / `Geprüft`).
- Aktionsleiste `<div class="admin-actions" data-sticky>`:
  Vorschau `<a class="btn" target="_blank" rel="noopener" href="/admin/{family}/preview?week=…">`,
  Kopieren `<a class="btn" href="/admin/{family}/copy?week=…">`,
  Publizieren `<form method="post" action="/admin/{family}/publish" data-confirm="…">`
  mit exakt `_csrf`, `week`, `row_version` (Wochen-Row-Version) und `<button type="submit">`.
- Patientenseite: keine Zeichenfolge `preis|chf|rappen|kosten|price` (case-insensitiv), auch nicht in Attributen.
- Cafeteria: Preisfelder `internal_chf` / `external_chf`, Beschriftung „Mitarbeitende" / „Externe".
- `<h1>` „Cafeteria-Plan bearbeiten" bzw. „Patientenplan bearbeiten".
- `weekbar` mit KW und „10 Menükarten · 5 Tage × 2 Menüarten" bzw.
  „28 Menükarten · 7 Tage × 2 Mahlzeiten × 2 Menüarten".
- Skip-Link aus `base.html` (`class="skip-link"`, `href="#main-content"`).

`_page` bleibt für alle übrigen Handler (Header, Service, Copy, Publish, Review-POST, CSV).

### Vorschau (`GET /admin/{family}/preview?week=`)

- `<div class="preview-banner" role="status">PREVIEW</div>`
- `<section data-preview="last-saved" data-workflow-state="{state}" data-week="…" data-profile="{profile}">`
  mit Wochentitel und allen Gerichtstiteln in Rasterreihenfolge.
- Keine Interaktion, kein Publikations-Fallback.

### Komponenten (`GET /admin/{family}/komponenten`)

- Suchformular GET: `q`, `category`, `include_archived` (native Checkbox, sichtbares Label).
- Liste `<li class="component-row" data-public-id="…" data-active="0|1">` mit Name,
  Kategorie (deutsch), Nutzung „verwendet in n Gerichten" und Archiv-Badge.
- Create-Formular POST: exakt `_csrf,category,name,origin_country_code,target_scope`
  plus `label_code[]`, `allergen_code[]` / `allergen_presence[]` (Fieldset/Legend, native Controls).

### Komponentendetail

- Wrapper mit `data-public-id`, `data-profile-scope`, `data-active`.
- Update-Formular: exakt `_csrf,category,name,origin_country_code,row_version` plus Wiederholungen.
- Archive/Unarchive: eigene POST-Formulare mit exakt `_csrf,row_version`.
- Hinweis „Betroffene Gerichte müssen erneut geprüft werden" nach Metadatenänderung (Flash).

## Formularfelder Menü-Editor

Pflicht: `_csrf, week, day, meal, option, row_version, title, allergen_mode, origin_mode, label_mode`.
Optional: `description`, `note`.
Wiederholt: `component_public_id`, `component_text`, `allergen_code`, `allergen_presence`,
`origin_ingredient`, `origin_country_code`, `label_code`.
Nur Cafeteria: `internal_chf`, `external_chf`.
Review-Token: `component_version` (nur wenn vorhanden).

## Verbote

- Keine `TEST_SNAPSHOTS`-Verzweigung in Produktionshandlern.
- Keine harten Hexwerte in `style=`-Attributen.
- `_page` nicht global ersetzen.
- Patient-Kontext und Patient-Templates ohne Preis-Vokabular.
