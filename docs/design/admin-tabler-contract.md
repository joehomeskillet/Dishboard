# Admin-UI-Vertrag: Tabler-Integration (v1.0, 2026-09-05)

Gilt für alle Backend-Ansichten mit `body_class = admin-body`. Öffentliche Tages-/Wochenseiten,
Signage und Druck bleiben ohne Framework. Grundlage ist das offizielle, selbst gehostete
`@tabler/core` 1.5.0 plus Tabler Icons 3.46.0 (`static/vendor/README.md`, pinned, SHA256).
Erste Tranche: gemeinsamer Admin-Rahmen, Menülisten und Wochenverwaltung.
Bestehende Editor-, Komponenten-, CSV-, Kopier- und Wochenformulare bleiben
funktional erhalten; ihre vollständige Tabler-Konvertierung ist eine Folgetranche.
Neue Listen-Steuerelemente nutzen echte Tabler-Klassen; der Adapter
`static/admin-tabler.css` liefert nur Marken-Tokens, 44-px-Touchziele und die Shell-Verdrahtung.

## PAGE

| Baustein | Markup |
|---|---|
| Shell | `<div class="admin-shell …">` → `{% include 'admin/_workflow_sidebar.html' %}` + `<main id="main-content" class="page-wrapper admin-main …">` |
| Sidebar | `aside.navbar.navbar-vertical.navbar-expand-lg.admin-sidebar[data-bs-theme=dark]`; ab 992 px fest links (16 rem), darunter horizontale Leiste mit umbrechenden Einträgen; keine Klapp-Navigation |
| Kopf | Makro `page_header(title)` → `.page-header > .container-xl`, `h1.page-title`; Aktionen rechts per `{% call page_header(...) %}…{% endcall %}` in `.btn-list` |
| Inhalt | `.page-body > .container-xl`; Profilwechsel per Makro `profile_tabs(links, family)` (`nav.profile-tabs > ul.nav.nav-pills`) |
| Seitenwechsel | Makro `pagination(page, has_next, prev_url, next_url, label)` → `ul.pagination` |
| Meldungen | `.flash-region[aria-live=polite]` mit `.alert.alert-info.flash`; Fehler `.alert.alert-danger[role=alert]` (Hook-Klasse `error-region` bleibt) |

## FIELD

| Baustein | Markup |
|---|---|
| Feld | `<div class="col-…"><label class="form-label" for=…>…</label><input class="form-control" …></div>` in `.row.g-3` |
| Auswahl | `select.form-select` |
| Mehrzeilig | `textarea.form-control` mit `rows` nach Inhalt (2–4), kein Standardblock |
| Kontrollkästchen / Radio | `<label class="form-check"><input class="form-check-input" …><span class="form-check-label">…</span></label>`; Schalter zusätzlich `form-switch` |
| Optionaler Zusatz | `<span class="form-label-description">optional</span>` im Label |
| Hinweis / Fehler | `.form-hint` bzw. `.invalid-feedback.d-block.field-error` und `is-invalid` auf dem Control; `aria-invalid`, `aria-describedby` bleiben |
| Breiten | Immer über Grid-Spalten begrenzen (`col-12 col-sm-5 col-lg-3` für Datum, ISO-Code `col-4 col-md-2`); niemals `style=` |
| Suche | `.input-icon > .input-icon-addon + input.form-control[type=search]` |

## CARD

| Baustein | Markup |
|---|---|
| Karte | `article.card` (bzw. `section.card`) → `.card-header > h2.card-title`, `.card-body`, `.card-footer` |
| Kartenraster | `.row.row-cards > .col-12.col-md-6.col-xl-4 > .card.h-100` |
| Listen in Karten | `table.table.table-vcenter.card-table.table-mobile-lg` mit `data-label` je Zelle (stapelt unter 992 px) |
| Leerzustand | `.empty > .empty-icon + p.empty-title + .empty-action` |
| Status | `span.badge.bg-{green,teal,yellow,orange,secondary}-lt` immer mit Text, nie nur Farbe |
| Chips | `ul.list-inline > li.list-inline-item.badge.bg-secondary-lt` |

## BUTTONS

| Rang | Klasse | Einsatz |
|---|---|---|
| Primär | `btn btn-primary` | genau eine Hauptaktion pro Ansicht (Speichern, Suchen, Woche anlegen, Publizieren) |
| Sekundär | `btn` | Öffnen, Vorschau, Kopieren, Zurück |
| Gefährlich | `btn btn-outline-danger` | Archivieren, Entfernen (mit `data-confirm`) |
| Gruppe | `.btn-list` | mehrere Aktionen nebeneinander, bricht um |

Alle `.btn`, `.form-control`, `.form-select`, `.page-link`, `.nav-link` sind mindestens 44 px hoch,
Text 16 px (Adapter). Kein `style`, keine Inline-Skripte, keine Hex-Farben in Templates.

## ICONS

Makro `icon(name, class='', label=None)` aus `admin/_macros.html` rendert
`<svg class="icon"><use href="…/vendor/tabler-icons/tabler-icons.svg#tabler-<name>">`.
Ohne `label` ist das Icon `aria-hidden`; Icon-only-Aktionen bekommen `label` oder ein sichtbares
`aria-label` am Button. Provenienz und Reproduktion des ausgewählten Sprites stehen
in `static/vendor/README.md`.

| Bedeutung | Icon |
|---|---|
| Wochenpläne / Wochenverwaltung / Woche anlegen | `calendar-week` / `calendar-cog` / `calendar-plus` |
| Menüs / Komponenten / CSV Import | `tools-kitchen-2` / `components` / `file-import` |
| Suchen / Zurücksetzen / Hinzufügen / Entfernen | `search` / `x` / `plus` / `trash` |
| Speichern / Bearbeiten / Vorschau / Kopieren | `device-floppy` / `pencil` / `eye` / `copy` |
| Zurück / Weiter / Abmelden | `arrow-left`, `chevron-left` / `chevron-right` / `logout` |
| Prüfen / Warnung / Info / Archiv | `check`, `clipboard-check`, `circle-check` / `alert-triangle` / `info-circle` / `archive`, `archive-off` |

## Prüfmatrix

Tablets 768×1024, 800×1280, 1024×768, 1280×800; Rückfall 390×844 und 1440×1100.
Keine horizontale Dokumentbreite über den Viewport, primäre Aktion im ersten Viewport,
alle Ziele ≥ 44 px, sichtbarer Fokusring auf jedem Control.
