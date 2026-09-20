# Semantic UI audit — S1, 2026-09-20

Scope: shared presentation foundation. Source baseline `760ca1cc270f42c91c0e58dde24abe10caca0e96`.
No module migration is implied by this inventory. Business values, rights and URLs stay with their owners.

## Shared components

Each row records source location and proposed semantic candidate. Matches from current labels/icons
are candidates, not automatic substitutions: for example “Anlegen” and “Hinzufügen” depend on whether
an object is created or attached. Existing macro parameters containing business data stay data.

| Ort (Datei:Zeile) | heutiges Muster | semantic key | Ziel-Label-Key | Ziel-Icon | Schwere | Migrationshinweis |
|---|---|---|---|---|---|---|
| reference_scaffold/cafeteria/templates/admin/_macros.html:3 | {%- macro icon(name, class='', label=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:4 | <svg class="icon{% if class %} {{ class }}{% endif %}"{% if label %} role="img" aria-label="{{ label }}"{% else %} aria-hidden="true"{% endif %} focusable="false"><use href="{{ url_for('static', filename='vendor/tabler-icons/tabler-icons.svg') }}#tabler-{{ nam | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:5 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:7 | {%- macro icon_link(href, label) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:8 | <a class="btn btn-icon w-100" href="{{ href }}" aria-label="{{ label }}" data-admin-icon-action data-bs-toggle="tooltip" data-bs-title="{{ label }}">{{ icon('pencil') }}</a> | publish.draft | publish.draft.label | pencil | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:9 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:11 | {%- macro page_header(title, description=none, breadcrumbs=none, actions=none, pretitle=none, status_items=[]) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:40 | <nav aria-label="Breadcrumb" class="page-breadcrumb mb-2"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:56 | <h1 class="page-title">{{ title }}</h1> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:68 | <dl class="admin-statusbar" aria-label="Status"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:75 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:77 | {%- macro field(name, label, value='', type='text', id=none, required=false, error=none, hint=none, readonly=false, disabled=false, autofocus=false, placeholder=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:86 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:88 | {%- macro select(name, label, choices=none, value='', id=none, required=false, error=none, hint=none, readonly=false, disabled=false, placeholder=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:118 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:120 | {%- macro textarea(name, label, value='', id=none, required=false, error=none, hint=none, readonly=false, disabled=false, rows=3, placeholder=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:129 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:131 | {%- macro checkbox(name, label, value='1', checked=false, id=none, required=false, error=none, hint=none, readonly=false, disabled=false) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:143 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:145 | {%- macro check(name, label, value='1', checked=false, id=none, type='checkbox', required=false, error=none, hint=none, readonly=false, disabled=false) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:157 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:159 | {%- macro form_errors(errors, title=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:170 | <div>{{ icon('alert-triangle', class='alert-icon me-2') }}</div> | status.warning, allergen.unknown | status.warning.label, allergen.unknown.label | alert-triangle, alert-triangle | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:172 | <h4 class="alert-title mb-1">{{ title or 'Bitte überprüfen Sie die folgenden Fehler:' }}</h4> | status.error | status.error.label | circle-x | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:193 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:195 | {%- macro status_badge(value, mapping=none, label=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:198 | 'ready': ('Bereit', 'info'), | publish.ready | publish.ready.label | checks | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:199 | 'review_open': ('Prüfung offen', 'warning'), | review.pending | review.pending.label | alert-circle | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:202 | 'active': ('Aktiv', 'success'), | status.active | status.active.label | circle-check | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:203 | 'inactive': ('Inaktiv', 'secondary'), | status.inactive | status.inactive.label | circle-minus | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:205 | 'draft': ('Entwurf', 'secondary'), | publish.draft | publish.draft.label | pencil | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:207 | 'error': ('Fehler', 'danger'), | status.error | status.error.label | circle-x | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:208 | 'success': ('Erfolgreich', 'success'), | status.success | status.success.label | circle-check | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:211 | 'info': ('Info', 'info'), | status.info | status.info.label | info-circle | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:212 | 'published': ('Veröffentlicht', 'success') | publish.published | publish.published.label | world-check | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:238 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:240 | {%- macro status(value, label=none, mapping=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:246 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:248 | {%- macro empty_state(kind, title, text, action=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:252 | 'no_match': 'search', | view.search | view.search.label | search | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:253 | 'forbidden': 'alert-triangle' | status.warning, allergen.unknown | status.warning.label, allergen.unknown.label | alert-triangle, alert-triangle | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:255 | {%- set kind_icon = icon_map.get(kind, 'info-circle') -%} | status.info | status.info.label | info-circle | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:264 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:266 | {%- macro pagination(page, has_next=none, prev_url=none, next_url=none, label='Pagination', has_prev=none, total_pages=none, total_items=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:287 | <nav class="mt-3" aria-label="{{ eff_label }}"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:291 | <a class="page-link" href="{{ eff_prev_url }}">{{ icon('chevron-left') }}Zurück</a> | actions.back, time.previous | actions.back.label, time.previous.label | arrow-left, chevron-left | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:293 | <span class="page-link" aria-disabled="true">{{ icon('chevron-left') }}Zurück</span> | actions.back, time.previous | actions.back.label, time.previous.label | arrow-left, chevron-left | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:303 | <a class="page-link" href="{{ eff_next_url }}">Weiter{{ icon('chevron-right') }}</a> | actions.open, actions.next, time.next | actions.open.label, actions.next.label, time.next.label | chevron-right, arrow-right, chevron-right | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:305 | <span class="page-link" aria-disabled="true">Weiter{{ icon('chevron-right') }}</span> | actions.open, actions.next, time.next | actions.open.label, actions.next.label, time.next.label | chevron-right, arrow-right, chevron-right | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:314 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:316 | {%- macro actions(primary=none, secondary=none, class='') -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:350 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:352 | {%- macro profile_tabs(links, current) %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:353 | <nav class="profile-tabs mb-3" aria-label="Profil"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:360 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:362 | {%- macro flash_region(messages) %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:366 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:368 | {%- macro option_detail_group(options, submitted=none, errors=none, id='allergen', label='Allergene', code_name='allergen_code', detail_name='allergen_presence', manual=true, field_prefix=none, choices=none, mode='allergen') -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | hoch | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:394 | <span class="form-check-label">{% if mode == 'allergen' and code\|food_symbol('allergens') %}{{ symbol('allergens', code, true) }}{% else %}{{ icon(option.icon\|default('check')) }}{% endif %}{{ title }}</span> | actions.confirm | actions.confirm.label | check | hoch | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:398 | <select class="form-select{{ ' is-invalid' if presence_invalid else '' }}" id="{{ field_id }}-presence" name="{{ field_prefix ~ code if field_prefix else detail_name }}" data-option-presence aria-label="Präsenz für {{ title }}"{% if presence_invalid %} aria-in | zu ergänzen | vollständiger Message-Key | nach Bedeutung | hoch | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:409 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:411 | {%- macro filter_bar(action, search_name='q', search_value='', filters=none, more_filters=none, active=false, reset_url=none, id='filters') -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:413 | <div class="admin-filter-search">{{ field(search_name, 'Suche', search_value, type='search', id=id ~ '-search') }}</div> | view.search | view.search.label | search | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:415 | {% if more_filters %}<details class="admin-compact-details admin-filter-more"><summary>{{ icon('search') }}Weitere Filter</summary><div class="admin-filter-slots">{{ more_filters }}</div></details>{% endif %} | actions.next, view.search, view.filter | actions.next.label, view.search.label, view.filter.label | arrow-right, search, filter | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:416 | <button class="btn" type="submit">{{ icon('search') }}Filtern</button> | view.search, view.filter | view.search.label, view.filter.label | search, filter | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:417 | {% if active and reset_url %}<a class="btn" href="{{ reset_url }}">{{ icon('x') }}Filter zurücksetzen</a>{% endif %} | actions.cancel, actions.close, view.filter | actions.cancel.label, actions.close.label, view.filter.label | x, x, filter | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:419 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:421 | {%- macro list_row(name, subtitle, state, action, markings=none, overflow=0, more_actions=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:423 | <div class="admin-list-name"><strong>{{ name }}</strong><div class="admin-list-subtitle" title="{{ subtitle }}">{{ subtitle }}</div></div> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:425 | {% if markings or overflow %}<div class="admin-list-markings">{{ markings or '' }}{% if overflow %}<span class="badge" aria-label="{{ overflow }} weitere Kennzeichnungen">+{{ overflow }}</span>{% endif %}</div>{% endif %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:428 | {% if more_actions %}<details class="admin-compact-actions"><summary>{{ icon('dots') }}Weitere Aktionen</summary>{{ more_actions }}</details>{% endif %} | actions.more, actions.next, allergen.sesame | actions.more.label, actions.next.label, allergen.sesame.label | dots, arrow-right, dots | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:431 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:433 | {%- macro form_footer(primary, cancel_url, rare=none, sticky=false, form_id=none) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:437 | <a class="btn" href="{{ cancel_url }}">{{ icon('x') }}Abbrechen</a> | actions.cancel, actions.close | actions.cancel.label, actions.close.label | x, x | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:441 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:443 | {%- macro disclosure_section(title='Weitere Optionen', id=none, open=false, has_content=false, has_error=false) -%} | actions.next | actions.next.label | arrow-right | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:445 | <summary>{{ icon('chevron-right') }}{{ title }}{% if has_content %}<span class="text-secondary"> · enthält Angaben</span>{% endif %}</summary> | actions.open, time.next | actions.open.label, time.next.label | chevron-right, chevron-right | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_macros.html:448 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/base_tabler.html:2 | <html lang="de-CH"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/base_tabler.html:8 | <title>{% block title %}Südhang Menüplanung{% endblock %}</title> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/base_tabler.html:16 | {% set user = session.get('user') %} | admin.user | admin.user.label | user | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:8 | ('weeks', 'Wochenplan', 'calendar-week', 'family', [ | time.week, navigation.weekplan | time.week.label, navigation.weekplan.label | calendar-week, calendar-week | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:11 | ('management', 'week_management', 'Wochenübersicht', true, family_args), | time.week | time.week.label | calendar-week | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:12 | ('calendar', 'kitchen_calendar', 'Küchenkalender', true, {}) | time.date | time.date.label | calendar | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:14 | ('menus', 'Menüs & Bausteine', 'tools-kitchen-2', 'menus', [ | meal.lunch, meal.main, navigation.menus, navigation.components | meal.lunch.label, meal.main.label, navigation.menus.label, navigation.components.label | tools-kitchen-2, tools-kitchen-2, tools-kitchen-2, blocks | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:15 | ('menus', 'menu_collection', 'Menüs', true, family_args), | navigation.menus | navigation.menus.label | tools-kitchen-2 | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:16 | ('components', 'components_get', 'Bausteine', true, family_args), | navigation.components | navigation.components.label | blocks | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:17 | ('master_data', 'master_data_list', 'Zutaten', true, {}), | recipe.ingredient, navigation.ingredients | recipe.ingredient.label, navigation.ingredients.label | carrot, carrot | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:18 | ('recipes', 'recipes_list', 'Rezepte', can_browse_recipes, {}), | recipe.recipe, navigation.recipes | recipe.recipe.label, navigation.recipes.label | recipe, recipe | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:19 | ('cookbooks', 'cookbooks_list', 'Kochbücher', can_browse_recipes, {}), | navigation.cookbooks | navigation.cookbooks.label | book | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:20 | ('dish_templates', 'dish_templates_list', 'Gerichtvorlagen', can_browse_recipes, {}), | navigation.templates | navigation.templates.label | template | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:21 | ('shopping_lists', 'shopping_lists_index', 'Einkaufslisten', can_browse_recipes, {}), | order.shopping_list, navigation.shopping | order.shopping_list.label, navigation.shopping.label | list-check, list-check | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:22 | ('orders', 'order_home', 'Bestellung', can_browse_recipes, {}), | order.order, navigation.orders | order.order.label, navigation.orders.label | clipboard-list, clipboard-list | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:23 | ('inventory', 'inventory_home', 'Lager', can_browse_recipes, {}), | navigation.stock | navigation.stock.label | packages | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:24 | ('cost', 'cost_home', 'Kalkulation', can_browse_recipes, {}) | data.calculation, navigation.costing | data.calculation.label, navigation.costing.label | calculator, calculator | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:26 | ('output', 'Vorschau & Bildschirme', 'eye', 'screens', [ | actions.preview, status.readonly, data.image, navigation.screens | actions.preview.label, status.readonly.label, data.image.label, navigation.screens.label | eye, eye, photo, device-tv | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:27 | ('preview', 'preview', 'Vorschau', true, dict(family=nav_family, **week_args)), | actions.preview | actions.preview.label | eye | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:28 | ('screens', 'screens', 'Bildschirme', true, {}), | data.image | data.image.label | photo | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:31 | ('settings', 'Einstellungen', 'calendar-cog', 'operations', [ | admin.settings, navigation.settings | admin.settings.label, navigation.settings.label | settings, settings | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:32 | ('operations', 'operations_settings', 'Bereiche & Öffnungszeiten', can_configure_display, {}), | admin.opening_hours, admin.area | admin.opening_hours.label, admin.area.label | clock-hour-4, layout | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:33 | ('design', 'branding_editor', 'Erscheinungsbild', can_configure_display, {}), | admin.appearance | admin.appearance.label | palette | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:36 | ('api', 'api_overview', 'Schnittstellen', true, {}), | admin.interface | admin.interface.label | plug-connected | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:37 | ('users', 'local_users_list', 'Benutzer & Zugriff', can_manage_users, {}) | recipe.portion, admin.user, admin.users | recipe.portion.label, admin.user.label, admin.users.label | users, user, users | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:48 | ('calendar', ['admin.kitchen_calendar', 'admin.kitchen_event_new', 'admin.kitchen_event_create', | time.date | time.date.label | calendar | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:90 | ('users', ['admin.local_users_list', 'admin.local_user_new', 'admin.local_user_create', | recipe.portion, admin.users | recipe.portion.label, admin.users.label | users, users | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:110 | {% macro href(tab) -%}{{ url_for('admin.' ~ tab[1], **tab[4]) }}{%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:112 | {% macro render_tabs() %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:114 | <nav class="admin-area-tabs" aria-label="{{ label }}"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_area_tabs.html:124 | {% endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:6 | {% macro area_links() %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:22 | <ul class="admin-nav-subitems" aria-label="{{ label }} Unterpunkte"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:36 | {% endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:44 | <nav class="admin-nav" aria-label="Backend"> | recipe.bake | recipe.bake.label | oven | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:52 | <button class="navbar-toggler btn" type="button" data-bs-toggle="offcanvas" data-bs-target="#sidebar-menu" aria-controls="sidebar-menu" aria-expanded="false" aria-label="Menü"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:60 | <summary>{{ icon('dots') }}<span>Menü</span></summary> | actions.more, allergen.sesame | actions.more.label, allergen.sesame.label | dots, dots | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:61 | <nav class="admin-nav" aria-label="Backend"> | recipe.bake | recipe.bake.label | oven | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:65 | <button type="submit" class="admin-logout-btn" aria-label="Abmelden"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:74 | <nav class="admin-nav" aria-label="Backend"> | recipe.bake | recipe.bake.label | oven | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/admin/_workflow_sidebar.html:87 | <button type="submit" class="admin-logout-btn" aria-label="Abmelden"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/_food_symbols.html:1 | {% macro symbol(kind, code, tabler=false) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/_food_symbols.html:6 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/_food_symbols.html:8 | {% macro allergen_text(item) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | hoch | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/_food_symbols.html:10 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/_food_symbols.html:12 | {% macro legend(options, heading='Legende', tabler=false) -%} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/_food_symbols.html:15 | <section class="food-legend{% if tabler %} mt-3{% endif %}" aria-label="{{ heading }}"> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/_food_symbols.html:16 | <h2{% if tabler %} class="h4"{% endif %}>{{ heading }}</h2> | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |
| reference_scaffold/cafeteria/templates/_food_symbols.html:26 | {%- endmacro %} | zu ergänzen | vollständiger Message-Key | nach Bedeutung | mittel | Nur Inventur; Eigentümer migriert, Fachwerte und Rechte erhalten. |

### Coverage and decisions

- `_macros.html`: icon/icon_link; page_header and status_items; actions; fields/selects;
  form errors; status/status_badge; empty_state; pagination; M21 option_detail_group,
  M22 filter_bar, M23 list_row, M24 form_footer, M25 disclosure_section.
- `base_tabler.html`: document language, title, assets, shell includes and flash messages.
  Static document language needs owner migration; UI_LOCALE alone does not translate shell.
- `_area_tabs.html`: area/item captions and navigation icons; explicit endpoint membership
  and capability predicates must remain unchanged.
- `_workflow_sidebar.html`: desktop/mobile/no-JS navigation, active labels and logout.
- `_food_symbols.html`: asset rendering, presence texts, legend heading, missing declaration
  and pending review. Missing data remains unknown; never infer “free from”.
- Legacy statuses live/ready/review_open/incomplete/changed/active/inactive/archived/draft/
  conflict/error/success/warning/danger/info/published need explicit domain-to-key mapping.
  Suggested mappings: live/published → publish.published; ready → publish.ready;
  review_open → review.pending; changed → review.changed; draft → publish.draft;
  error → status.error; success → status.success; active/inactive → status.active/inactive.
  Incomplete, archived and conflict need dedicated complete messages before migration;
  do not erase distinct business states by coercing them into generic success/error.
- Common filter labels (“Suche”, “Weitere Filter”, “Filtern”, “Filter zurücksetzen”) and
  page_header's fixed “Status” accessible label remain in the locked legacy macro.
  Thin S1 wrappers reuse these components; multilingual migration is an owner follow-up.
- Destructive flows still own CSRF, authorization and submit endpoints. confirm_dialog
  only supplies markup and named form controls, without introducing a new confirmation route.

## Literal measurement per admin template

Heuristic implemented in `tests/test_ui_hardcoded_strings_report.py`: Jinja TemplateData
through HTMLParser, visible text and accessible attributes, Output Const strings and constant
arguments to selected legacy macros. Ignore script/style, dynamic domain data and t/semantic
macro arguments. Counts are occurrences, not unique messages. Conditional expression literals
and dictionaries can be undercounted; macro identifier arguments can overcount. This is a
migration baseline, not a complete i18n proof. Only the explicitly migrated proof page has a
zero-literal gate. Test writes the complete measurement to its pytest tmp_path.

| Template | Literal occurrences |
|---|---:|
| _area_tabs.html | 0 |
| _country_select.html | 2 |
| _course_editor.html | 16 |
| _course_line.html | 9 |
| _course_recipe_search.html | 7 |
| _local_user_forms.html | 15 |
| _macros.html | 23 |
| _recipe_document.html | 31 |
| _recipe_template_selection.html | 31 |
| _rezepte_fields.html | 4 |
| _service_courses.html | 6 |
| _week_controls.html | 43 |
| _week_menu_card.html | 17 |
| _week_service.html | 20 |
| _week_settings.html | 7 |
| _workflow_sidebar.html | 15 |
| access_history.html | 26 |
| api.html | 47 |
| base_tabler.html | 2 |
| bestellung.html | 23 |
| bestellung_korb.html | 20 |
| branding_editor.html | 58 |
| branding_preview.html | 9 |
| cafeteria.html | 13 |
| component_editor.html | 35 |
| components.html | 64 |
| copy.html | 18 |
| display_settings.html | 22 |
| einkaufsliste.html | 65 |
| einkaufslisten.html | 29 |
| gerichtvorlage_einplanen.html | 19 |
| gerichtvorlagen.html | 56 |
| grundlagen.html | 22 |
| grundlagen_food.html | 81 |
| grundlagen_location_conflict.html | 8 |
| grundlagen_unavailable.html | 1 |
| grundlagen_unit.html | 9 |
| grundlagen_vocabulary.html | 6 |
| import_preview.html | 24 |
| kalkulation.html | 22 |
| kochbuch_editor.html | 22 |
| kochbuecher.html | 19 |
| kuechenkalender.html | 24 |
| kuechenkalender_anlass.html | 15 |
| lager.html | 32 |
| local_user_create.html | 4 |
| local_user_editor.html | 35 |
| local_user_events.html | 15 |
| local_user_unavailable.html | 5 |
| local_users.html | 24 |
| menu_collection.html | 32 |
| menu_editor.html | 111 |
| operations.html | 47 |
| patienten.html | 7 |
| preview.html | 18 |
| print_template_editor.html | 96 |
| print_template_unavailable.html | 0 |
| recipe_template_error.html | 3 |
| rezepte.html | 24 |
| rezepte_ansicht.html | 19 |
| rezepte_conflict.html | 5 |
| rezepte_editor.html | 89 |
| rezepte_images.html | 30 |
| rezepte_import.html | 54 |
| rezepte_revision.html | 15 |
| rezepte_revisionen.html | 41 |
| rezepte_scale.html | 26 |
| screen_template_assignment.html | 21 |
| screen_template_unavailable.html | 6 |
| screens.html | 11 |
| vorlagen.html | 69 |
| week_management.html | 25 |
| week_review.html | 22 |

## Action synonym inventory

Basis: `/nvmetank1/projects/menuplan/.claude/state/uiux-0920-label-audit.md`
(258 lines). Counts and locations below were recalculated against the current
worktree; the earlier model's line numbers are not accepted as evidence. Match whole words
in admin template source, case-sensitive; includes hidden branches and source literals, not runtime frequency.

| Verb | Source lines | Verified locations |
|---|---:|---|
| Öffnen | 7 | `reference_scaffold/cafeteria/templates/admin/lager.html:23`, `reference_scaffold/cafeteria/templates/admin/local_users.html:27`, `reference_scaffold/cafeteria/templates/admin/menu_collection.html:92`, `reference_scaffold/cafeteria/templates/admin/menu_collection.html:128`, `reference_scaffold/cafeteria/templates/admin/menu_editor.html:71`, `reference_scaffold/cafeteria/templates/admin/week_management.html:76`, `reference_scaffold/cafeteria/templates/admin/week_management.html:93` |
| Ansehen | 4 | `reference_scaffold/cafeteria/templates/admin/kochbuecher.html:47`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:182`, `reference_scaffold/cafeteria/templates/admin/rezepte.html:28`, `reference_scaffold/cafeteria/templates/admin/rezepte_revisionen.html:44` |
| Anzeigen | 6 | `reference_scaffold/cafeteria/templates/admin/display_settings.html:26`, `reference_scaffold/cafeteria/templates/admin/display_settings.html:41`, `reference_scaffold/cafeteria/templates/admin/kuechenkalender.html:62`, `reference_scaffold/cafeteria/templates/admin/kuechenkalender.html:70`, `reference_scaffold/cafeteria/templates/admin/kuechenkalender.html:71`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:62` |
| Details | 16 | `reference_scaffold/cafeteria/templates/admin/_course_editor.html:42`, `reference_scaffold/cafeteria/templates/admin/api.html:32`, `reference_scaffold/cafeteria/templates/admin/api.html:133`, `reference_scaffold/cafeteria/templates/admin/import_preview.html:82`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:83`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:49`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:53`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:58`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:74`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:89`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:102`, `reference_scaffold/cafeteria/templates/admin/rezepte_images.html:22`, `reference_scaffold/cafeteria/templates/admin/rezepte_import.html:66`, `reference_scaffold/cafeteria/templates/admin/rezepte_import.html:103`, `reference_scaffold/cafeteria/templates/admin/rezepte_revision.html:27`, `reference_scaffold/cafeteria/templates/admin/rezepte_revisionen.html:44` |
| Anlegen | 4 | `reference_scaffold/cafeteria/templates/admin/_local_user_forms.html:40`, `reference_scaffold/cafeteria/templates/admin/grundlagen.html:44`, `reference_scaffold/cafeteria/templates/admin/grundlagen_food.html:43`, `reference_scaffold/cafeteria/templates/admin/week_management.html:93` |
| Neu | 9 | `reference_scaffold/cafeteria/templates/admin/einkaufsliste.html:54`, `reference_scaffold/cafeteria/templates/admin/einkaufsliste.html:63`, `reference_scaffold/cafeteria/templates/admin/einkaufsliste.html:117`, `reference_scaffold/cafeteria/templates/admin/einkaufslisten.html:80`, `reference_scaffold/cafeteria/templates/admin/grundlagen.html:19`, `reference_scaffold/cafeteria/templates/admin/grundlagen_location_conflict.html:45`, `reference_scaffold/cafeteria/templates/admin/grundlagen_location_conflict.html:47`, `reference_scaffold/cafeteria/templates/admin/rezepte_conflict.html:12`, `reference_scaffold/cafeteria/templates/admin/rezepte_import.html:151` |
| Erstellen | 0 |  |
| Hinzufügen | 0 |  |
| Bearbeiten | 12 | `reference_scaffold/cafeteria/templates/admin/_course_line.html:24`, `reference_scaffold/cafeteria/templates/admin/_week_menu_card.html:63`, `reference_scaffold/cafeteria/templates/admin/components.html:132`, `reference_scaffold/cafeteria/templates/admin/kochbuecher.html:47`, `reference_scaffold/cafeteria/templates/admin/menu_collection.html:61`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:38`, `reference_scaffold/cafeteria/templates/admin/rezepte.html:29`, `reference_scaffold/cafeteria/templates/admin/rezepte_ansicht.html:17`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:22`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:71`, `reference_scaffold/cafeteria/templates/admin/rezepte_revisionen.html:11`, `reference_scaffold/cafeteria/templates/admin/rezepte_revisionen.html:38` |
| Speichern | 21 | `reference_scaffold/cafeteria/templates/admin/_course_editor.html:95`, `reference_scaffold/cafeteria/templates/admin/component_editor.html:134`, `reference_scaffold/cafeteria/templates/admin/einkaufsliste.html:218`, `reference_scaffold/cafeteria/templates/admin/gerichtvorlagen.html:156`, `reference_scaffold/cafeteria/templates/admin/gerichtvorlagen.html:180`, `reference_scaffold/cafeteria/templates/admin/grundlagen_food.html:63`, `reference_scaffold/cafeteria/templates/admin/grundlagen_food.html:111`, `reference_scaffold/cafeteria/templates/admin/kuechenkalender_anlass.html:28`, `reference_scaffold/cafeteria/templates/admin/local_user_editor.html:25`, `reference_scaffold/cafeteria/templates/admin/menu_editor.html:100`, `reference_scaffold/cafeteria/templates/admin/menu_editor.html:358`, `reference_scaffold/cafeteria/templates/admin/menu_editor.html:359`, `reference_scaffold/cafeteria/templates/admin/menu_editor.html:362`, `reference_scaffold/cafeteria/templates/admin/operations.html:140`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:100`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:145`, `reference_scaffold/cafeteria/templates/admin/rezepte.html:9`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:22`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:95`, `reference_scaffold/cafeteria/templates/admin/rezepte_images.html:19`, `reference_scaffold/cafeteria/templates/admin/rezepte_import.html:12` |
| Bestätigen | 2 | `reference_scaffold/cafeteria/templates/admin/kalkulation.html:7`, `reference_scaffold/cafeteria/templates/admin/week_review.html:64` |
| Löschen | 1 | `reference_scaffold/cafeteria/templates/admin/einkaufsliste.html:224` |
| Archivieren | 13 | `reference_scaffold/cafeteria/templates/admin/component_editor.html:138`, `reference_scaffold/cafeteria/templates/admin/component_editor.html:143`, `reference_scaffold/cafeteria/templates/admin/einkaufslisten.html:58`, `reference_scaffold/cafeteria/templates/admin/gerichtvorlagen.html:182`, `reference_scaffold/cafeteria/templates/admin/grundlagen.html:31`, `reference_scaffold/cafeteria/templates/admin/grundlagen_vocabulary.html:10`, `reference_scaffold/cafeteria/templates/admin/kochbuch_editor.html:28`, `reference_scaffold/cafeteria/templates/admin/kochbuch_editor.html:43`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:202`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:204`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:11`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:14`, `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html:20` |
| Kopieren | 4 | `reference_scaffold/cafeteria/templates/admin/grundlagen_location_conflict.html:10`, `reference_scaffold/cafeteria/templates/admin/week_management.html:81`, `reference_scaffold/cafeteria/templates/admin/week_management.html:82`, `reference_scaffold/cafeteria/templates/admin/week_management.html:83` |
| Vorschau | 41 | `reference_scaffold/cafeteria/templates/admin/_area_tabs.html:26`, `reference_scaffold/cafeteria/templates/admin/_area_tabs.html:27`, `reference_scaffold/cafeteria/templates/admin/_recipe_template_selection.html:8`, `reference_scaffold/cafeteria/templates/admin/_week_controls.html:77`, `reference_scaffold/cafeteria/templates/admin/api.html:88`, `reference_scaffold/cafeteria/templates/admin/bestellung.html:7`, `reference_scaffold/cafeteria/templates/admin/bestellung_korb.html:12`, `reference_scaffold/cafeteria/templates/admin/bestellung_korb.html:52`, `reference_scaffold/cafeteria/templates/admin/branding_editor.html:72`, `reference_scaffold/cafeteria/templates/admin/branding_editor.html:76`, `reference_scaffold/cafeteria/templates/admin/branding_editor.html:84`, `reference_scaffold/cafeteria/templates/admin/branding_editor.html:95`, `reference_scaffold/cafeteria/templates/admin/branding_editor.html:130`, `reference_scaffold/cafeteria/templates/admin/display_settings.html:19`, `reference_scaffold/cafeteria/templates/admin/display_settings.html:25`, `reference_scaffold/cafeteria/templates/admin/display_settings.html:26`, `reference_scaffold/cafeteria/templates/admin/display_settings.html:38`, `reference_scaffold/cafeteria/templates/admin/display_settings.html:45`, `reference_scaffold/cafeteria/templates/admin/display_settings.html:46`, `reference_scaffold/cafeteria/templates/admin/import_preview.html:53`, `reference_scaffold/cafeteria/templates/admin/import_preview.html:64`, `reference_scaffold/cafeteria/templates/admin/import_preview.html:71`, `reference_scaffold/cafeteria/templates/admin/kalkulation.html:7`, `reference_scaffold/cafeteria/templates/admin/kalkulation.html:29`, `reference_scaffold/cafeteria/templates/admin/preview.html:4`, `reference_scaffold/cafeteria/templates/admin/preview.html:14`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:145`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:150`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:152`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:153`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:156`, `reference_scaffold/cafeteria/templates/admin/print_template_editor.html:157`, `reference_scaffold/cafeteria/templates/admin/rezepte_import.html:29`, `reference_scaffold/cafeteria/templates/admin/rezepte_import.html:140`, `reference_scaffold/cafeteria/templates/admin/screen_template_assignment.html:44`, `reference_scaffold/cafeteria/templates/admin/screens.html:36`, `reference_scaffold/cafeteria/templates/admin/screens.html:38`, `reference_scaffold/cafeteria/templates/admin/screens.html:59`, `reference_scaffold/cafeteria/templates/admin/screens.html:67`, `reference_scaffold/cafeteria/templates/admin/vorlagen.html:193`, `reference_scaffold/cafeteria/templates/admin/week_management.html:77` |

“Öffnen” replaces Ansehen/Anzeigen/Details only where the action is read-only. “Anlegen”
creates an object; “Hinzufügen” attaches an existing one. “Neu” and “Erstellen” require
semantic review per call site. Module owners extend this audit with exact migration rows.

## Formatting inventory — unchanged

No formatting behavior changed. Existing local date, time, number and currency conventions
remain authoritative for Public/PDF/Signage. Proposed next package: locale-aware wrappers
around current date_long/date_short/datetime_short/chf contracts; explicit formatting locale,
Europe/Zurich timezone, exact monetary arithmetic and snapshot regression tests before migration.
No implicit translation of persisted dates, domain values or publication snapshots.

| Ort | Existing formatting |
|---|---|
| reference_scaffold/cafeteria/admin/calendar_event_routes.py:112 | 'starts_at': event['starts_at'].strftime('%H:%M') if event['starts_at'] else '', |
| reference_scaffold/cafeteria/admin/calendar_event_routes.py:113 | 'ends_at': event['ends_at'].strftime('%H:%M') if event['ends_at'] else '', |
| reference_scaffold/cafeteria/admin/rendering.py:48 | return f'{int(rappen) / 100:.2f}' |
| reference_scaffold/cafeteria/admin/shopping_pdf.py:44 | return value.astimezone(_ZURICH).strftime('%d.%m.%Y %H:%M') |
| reference_scaffold/cafeteria/admin/week_pdf.py:114 | return f'{value / 100:.2f} CHF' if isinstance(value, int) else 'nicht erfasst' |
| reference_scaffold/cafeteria/admin/week_pdf_layout.py:332 | day_labels = [' · '.join([DAY_NAMES[offset].upper(), (week + timedelta(days=offset)).strftime('%d.%m.'), |
| reference_scaffold/cafeteria/template_filters.py:23 | def date_long(value: str) -> str: |
| reference_scaffold/cafeteria/template_filters.py:28 | def date_short(value: str) -> str: |
| reference_scaffold/cafeteria/template_filters.py:33 | def datetime_short(value: dt.datetime \| str \| None) -> str: |
| reference_scaffold/cafeteria/template_filters.py:41 | return value.astimezone(ZoneInfo('Europe/Zurich')).strftime('%d.%m.%Y %H:%M') if value else 'Noch nicht erfasst' |
| reference_scaffold/cafeteria/template_filters.py:44 | def chf(value: int) -> str: |
| reference_scaffold/cafeteria/template_filters.py:45 | return f'{int(value) / 100:.2f}' |
| reference_scaffold/cafeteria/template_filters.py:48 | def iso_week(value: str) -> int: |
| reference_scaffold/cafeteria/template_filters.py:64 | def service_time_label(service: Mapping[str, Any], profile_code: str) -> str: |
| reference_scaffold/cafeteria/template_filters.py:85 | def patient_day_time_label(service: Mapping[str, Any], area_name: object = '') -> str: |
| reference_scaffold/cafeteria/template_filters.py:114 | def weekday_range_label(days: Sequence[Mapping[str, Any]]) -> str: |
| reference_scaffold/cafeteria/templates/admin/_recipe_document.html:6 | <p class="text-secondary">Erstellt: <time datetime="{{ doc.identity.created_at }}">{{ doc.identity.created_at\|datetime_short }}</time> · Dieser gespeicherte Stand bleibt unverändert.</p> |
| reference_scaffold/cafeteria/templates/admin/_recipe_template_selection.html:40 | {% if recipe_revision and recipe_revision.public_id not in recipe_revisions\|map(attribute='public_id')\|list %}<option value="{{ recipe_revision.public_id }}" selected>Gespeicherter Stand {{ recipe_revision.revision_number }} · {{  |
| reference_scaffold/cafeteria/templates/admin/_recipe_template_selection.html:41 | {% for saved in recipe_revisions %}<option value="{{ saved.public_id }}" {% if arguments.get('recipe_revision') == saved.public_id %}selected{% endif %}>Gespeicherter Stand {{ saved.revision_number }} · {{ saved.created_at\|datetim |
| reference_scaffold/cafeteria/templates/admin/api.html:35 | <dt>Erstellt</dt><dd>{{ key.created_at.strftime('%d.%m.%Y %H:%M') }}<br>von {{ key.created_by_name }}</dd> |
| reference_scaffold/cafeteria/templates/admin/api.html:36 | <dt>Zuletzt verwendet</dt><dd class="mb-0">{% if key.last_used_at %}{{ key.last_used_at.strftime('%d.%m.%Y %H:%M') }}{% else %}—{% endif %}</dd> |
| reference_scaffold/cafeteria/templates/admin/api.html:46 | <td data-label="Läuft ab" class="text-secondary text-wrap">{% if key.expires_at %}{{ key.expires_at.strftime('%d.%m.%Y') }}{% else %}Bestandsschlüssel ohne Ablaufdatum{% endif %}</td> |
| reference_scaffold/cafeteria/templates/admin/branding_editor.html:114 | <small class="d-block mt-1 text-secondary">{% if active_revision.activated_at %}Aktiviert am {{ active_revision.activated_at\|datetime_short }}{% else %}Mitgelieferter Standard{% endif %}</small> |
| reference_scaffold/cafeteria/templates/admin/branding_editor.html:126 | <dd class="col-12 col-md-7 mb-0">{% if selected_revision.created_at %}<time datetime="{{ selected_revision.created_at }}">{{ selected_revision.created_at\|datetime_short }}</time>{% else %}Mitgelieferter Standard{% endif %}</dd> |
| reference_scaffold/cafeteria/templates/admin/copy.html:19 | <time class="d-block" datetime="{{ source.isoformat() }}">{{ source.strftime('%d.%m.%Y') }}</time> |
| reference_scaffold/cafeteria/templates/admin/copy.html:26 | <time class="d-block" datetime="{{ target.isoformat() }}">{{ target.strftime('%d.%m.%Y') }}</time> |
| reference_scaffold/cafeteria/templates/admin/copy.html:31 | <p id="copy-description"><strong>Quelle:</strong> Woche vom {{ source.strftime('%d.%m.%Y') }}. <strong>Ziel:</strong> in die leere Woche vom {{ target.strftime('%d.%m.%Y') }}.</p> |
| reference_scaffold/cafeteria/templates/admin/einkaufsliste.html:37 | <option value="{{ rev.public_id }}"{% if selected.public_id == rev.public_id %} selected{% endif %}>Revision {{ rev.revision_number }} · {{ rev.computed_at.strftime('%d.%m.%Y %H:%M') }}</option> |
| reference_scaffold/cafeteria/templates/admin/einkaufsliste.html:53 | <div class="fw-bold">Beleg vom {{ selected.computed_at.strftime('%d.%m.%Y %H:%M') }}, nicht aktuell.</div> |
| reference_scaffold/cafeteria/templates/admin/einkaufsliste.html:89 | <legend class="form-label">{{ day_names[group.service_date.weekday()] }}, {{ group.service_date.strftime('%d.%m.%Y') }} · {{ group.meal_period_display_name }}</legend> |
| reference_scaffold/cafeteria/templates/admin/einkaufslisten.html:40 | {% if item.latest_computed_at %}{{ item.latest_computed_at.strftime('%d.%m.%Y %H:%M') }}{% else %}Noch nicht berechnet{% endif %} |
| reference_scaffold/cafeteria/templates/admin/einkaufslisten.html:45 | <td class="d-none d-md-table-cell">{% if item.latest_computed_at %}{{ item.latest_computed_at.strftime('%d.%m.%Y %H:%M') }}{% else %}Noch nicht berechnet{% endif %}</td> |
| reference_scaffold/cafeteria/templates/admin/import_preview.html:21 | <p class="csv-target"><strong>{{ profile_label }}</strong><br>KW {{ result.week_start.isocalendar().week }} · ab {{ result.week_start.strftime('%d.%m.%Y') }}</p> |
| reference_scaffold/cafeteria/templates/admin/menu_collection.html:80 | <td><time datetime="{{ row.service_date.isoformat() }}">{{ row.service_date.strftime('%d.%m.%Y') }}</time>{% if row.workflow_state == 'archived' %}<span class="d-block text-secondary">Archivierte Woche</span>{% endif %}</td> |
| reference_scaffold/cafeteria/templates/admin/menu_collection.html:92 | <td><a class="btn w-100" href="{{ url_for('admin.menu_get', family=family, week=row.week_start.isoformat(), day=row.service_date.isoformat(), meal=row.meal_code, option=row.type_code) }}" aria-label="{{ row.title ~ ' vom ' ~ row.s |
| reference_scaffold/cafeteria/templates/admin/menu_collection.html:108 | <p class="text-secondary small mb-1">{{ row.service_date.strftime('%d.%m.%Y') }} · {{ meal_labels[row.meal_code] }} · {{ option_labels[row.type_code] }}{% if row.workflow_state == 'archived' %} · Archivierte Woche{% endif %}</p> |
| reference_scaffold/cafeteria/templates/admin/menu_collection.html:128 | <a class="btn w-100" href="{{ url_for('admin.menu_get', family=family, week=row.week_start.isoformat(), day=row.service_date.isoformat(), meal=row.meal_code, option=row.type_code) }}" aria-label="{{ row.title ~ ' vom ' ~ row.servi |
| reference_scaffold/cafeteria/templates/admin/menu_editor.html:6 | {% set day_title = cell.day_label\|default(cell.day\|date_long) %} |
| reference_scaffold/cafeteria/templates/admin/operations.html:186 | <th scope="row">{{ item.service_date.strftime('%d.%m.%Y') }} · {{ area_names[item.profile_code] }} · {{ meal_labels[item.meal_code] }}</th> |
| reference_scaffold/cafeteria/templates/admin/preview.html:18 | <p class="preview-context">KW {{ week_iso\|iso_week }} / {{ week.isocalendar().year }} · Woche ab <time datetime="{{ week_iso }}">{{ week_iso\|date_long }}</time></p> |
| reference_scaffold/cafeteria/templates/admin/preview.html:31 | <p class="preview-notice" role="note">Gewählter Stand: gespeicherte Woche KW {{ week_iso\|iso_week }}, nicht automatisch der veröffentlichte Plan. Veröffentlichen bleibt ein eigener, bestätigter Schritt im Wochenplan.</p> |
| reference_scaffold/cafeteria/templates/admin/preview.html:54 | <h3>{{ day.date\|date_long }}</h3> |
| reference_scaffold/cafeteria/templates/admin/preview.html:80 | Mitarbeitende: {{ option.internal_rappen\|default(0)\|chf }} \| |
| reference_scaffold/cafeteria/templates/admin/preview.html:81 | Externe: {{ option.external_rappen\|default(0)\|chf }} |
| reference_scaffold/cafeteria/templates/admin/print_template_editor.html:53 | <span class="text-secondary">{% if recipe_editor %}{{ recipe_revision.snapshot.recipe.title }} · Stand {{ recipe_revision.revision_number }}{% else %}Gespeicherte Woche ab {{ week\|date_long }}{% endif %}</span> |
| reference_scaffold/cafeteria/templates/admin/print_template_editor.html:153 | <p>Gespeicherte Woche ab {{ week\|date_long }}. Die Vorschau verwendet die angezeigte gespeicherte Vorlagenversion.</p>{% endif %} |
| reference_scaffold/cafeteria/templates/admin/print_template_editor.html:181 | <div class="text-secondary">{% if saved.created_at %}<time datetime="{{ saved.created_at }}">{{ saved.created_at\|datetime_short }}</time>{% else %}Mitgelieferte Standardvorlage{% endif %}{% if saved.restored_from %} · Wiederherges |
| reference_scaffold/cafeteria/templates/admin/rezepte_revisionen.html:44 | {% for item in revisions %}<tr><td data-label="Stand">Gespeicherter Stand {{ item.revision_number }}</td><td data-label="Erstellt"><time datetime="{{ item.created_at.isoformat() }}">{{ item.created_at\|datetime_short }}</time></td> |
| reference_scaffold/cafeteria/templates/admin/vorlagen.html:43 | <p class="text-secondary small mb-3 output-publication-note" role="note">Gewählte Woche: ab {{ week\|date_long }}. Öffentliche Druckansichten zeigen den aktuell veröffentlichten Plan. Ohne Veröffentlichung erscheint ein Hinweis.</p |
| reference_scaffold/cafeteria/templates/admin/week_management.html:56 | <strong><time datetime="{{ row.week_start.isoformat() }}">{{ row.week_start.strftime('%d.%m.%Y') }}</time>{% if row.next_week %} – <time datetime="{{ row.week_start.fromordinal(row.week_start.toordinal() + 6).isoformat() }}">{{ ro |
| reference_scaffold/cafeteria/templates/admin/week_management.html:77 | {% if can_preview %}<a class="btn btn-icon btn-outline-secondary border-0" href="{{ url_for('admin.preview', family=family, week=row.week_start.isoformat()) }}" aria-label="Vorschau für Woche ab {{ row.week_start.strftime('%d.%m.% |
| reference_scaffold/cafeteria/templates/admin/week_management.html:82 | <p class="text-secondary small my-2" id="copy-{{ row.id }}">Quelle: {{ row.week_start.strftime('%d.%m.%Y') }} → Ziel: {{ row.next_week.strftime('%d.%m.%Y') }}. Kopieren wird im nächsten Schritt bestätigt; Ziel muss leer und unverö |
| reference_scaffold/cafeteria/templates/admin/week_review.html:19 | <p class="mb-0">Dieser Stand wurde von {{ review.receipt.actor_name }} am {{ review.receipt.occurred_at\|datetime_short }} geprüft.</p> |
| reference_scaffold/cafeteria/templates/public/cafeteria_today.html:25 | <div class="mt-3"><span class="badge bg-primary-lt date-chip">{{ day.weekday if day else '' }}, {{ today\|date_long }}</span></div> |
| reference_scaffold/cafeteria/templates/public/cafeteria_today.html:32 | {% set time_label = lunch\|service_time_label('staff_guest') %} |
| reference_scaffold/cafeteria/templates/public/cafeteria_today.html:64 | <div class="fs-3 fw-bold">CHF {{ option.prices.internal_rappen\|chf }}</div> |
| reference_scaffold/cafeteria/templates/public/cafeteria_today.html:68 | <div class="fs-3 fw-bold">CHF {{ option.prices.external_rappen\|chf }}</div> |
| reference_scaffold/cafeteria/templates/public/cafeteria_week.html:22 | {% if snapshot %}<span class="badge bg-primary-lt date-chip">Kalenderwoche {{ snapshot.week_start\|iso_week }}</span>{% endif %} |
| reference_scaffold/cafeteria/templates/public/cafeteria_week.html:35 | <a href="#tag-{{ day.date }}" class="nav-item nav-link flex-column gap-1 {{ 'active' if day.date == today or (not has_today and loop.first) else '' }}" aria-label="{{ day.weekday }}, {{ day.date\|date_long }}" {% if day.date == tod |
| reference_scaffold/cafeteria/templates/public/cafeteria_week.html:45 | {% set time_label = service\|service_time_label('staff_guest') %} |
| reference_scaffold/cafeteria/templates/public/cafeteria_week.html:48 | <h2 class="{{ 'mb-1' if time_label else 'mb-3' }}">{{ day.weekday }}, {{ day.date\|date_long }}</h2> |
| reference_scaffold/cafeteria/templates/public/cafeteria_week.html:81 | <strong class="fs-4">CHF {{ option.prices.internal_rappen\|chf }}</strong> |
| reference_scaffold/cafeteria/templates/public/cafeteria_week.html:85 | <strong class="fs-4">CHF {{ option.prices.external_rappen\|chf }}</strong> |
| reference_scaffold/cafeteria/templates/public/patient_today.html:25 | <div class="mt-3"><span class="badge bg-primary-lt date-chip">{{ day.weekday if day else '' }}, {{ today\|date_long }}</span></div> |
| reference_scaffold/cafeteria/templates/public/patient_week.html:16 | <h1 class="page-title">{{ (snapshot.week_start\|date_long) ~ ' bis ' ~ (snapshot.week_end\|date_long) if snapshot else 'Wochenplan nicht verfügbar' }}</h1> |
| reference_scaffold/cafeteria/templates/public/patient_week.html:22 | {% if snapshot %}<span class="badge bg-primary-lt date-chip">Kalenderwoche {{ snapshot.week_start\|iso_week }}</span>{% endif %} |
| reference_scaffold/cafeteria/templates/public/patient_week.html:35 | <a href="#tag-{{ day.date }}" class="nav-item nav-link flex-column gap-1 {{ 'active' if day.date == today or (not has_today and loop.first) else '' }}" aria-label="{{ day.weekday }}, {{ day.date\|date_long }}" {% if day.date == tod |
| reference_scaffold/cafeteria/templates/public/patient_week.html:45 | <h2 class="mb-3">{{ day.weekday }}, {{ day.date\|date_long }}</h2> |
| reference_scaffold/cafeteria/templates/public/patient_week.html:49 | {% set time_label = meal\|service_time_label('patient') %} |
| reference_scaffold/cafeteria/templates/public/print_cafeteria_week.html:20 | <header><h2>{{ day.weekday }}</h2><span>{{ day.date\|date_long }}</span></header> |
| reference_scaffold/cafeteria/templates/public/print_cafeteria_week.html:21 | {% set time_label = meal\|service_time_label('staff_guest') %} |
| reference_scaffold/cafeteria/templates/public/print_cafeteria_week.html:26 | <span class="week-price">Mitarbeitende CHF {{ option.prices.internal_rappen\|chf }} · Externe CHF {{ option.prices.external_rappen\|chf }}</span></div>{% endfor %}{% else %}<div class="closed-row"><strong>{{ meal.notice }}</strong>< |
| reference_scaffold/cafeteria/templates/public/print_patient_week.html:12 | <section class="hero"><div><p class="eyebrow">Druck · {{ area_name if area_name else 'Patienten-Speiseplan' }}</p><h1>{{ (snapshot.week_start\|date_long) ~ ' bis ' ~ (snapshot.week_end\|date_long) if snapshot else 'Wochenplan nicht  |
| reference_scaffold/cafeteria/templates/public/print_patient_week.html:17 | <article class="week-day"><header><h2>{{ day.weekday }}</h2><span>{{ day.date\|date_long }}</span></header><div class="week-day-grid">{% for meal in day.services %}{% set time_label = meal\|service_time_label('patient') %}<div class |
| reference_scaffold/cafeteria/templates/signage/base_signage.html:26 | <span class="signage-calendar-date">{% if today is defined %}{{ today\|date_long }}{% endif %}</span> |
| reference_scaffold/cafeteria/templates/signage/cafeteria_day.html:11 | <span class="text-truncate">{{ area_name if area_name else 'Cafeteria · Mittag für Mitarbeitende und externe Gäste' }}{% if lunch %}{% set time_label = lunch\|service_time_label('staff_guest') %}{% if time_label %} · {{ time_label  |
| reference_scaffold/cafeteria/templates/signage/cafeteria_day.html:48 | <span class="fs-2 fw-bold">Mitarbeitende CHF {{ option.prices.internal_rappen\|chf }}</span> |
| reference_scaffold/cafeteria/templates/signage/cafeteria_day.html:49 | <span class="hero-food-external">Externe CHF {{ option.prices.external_rappen\|chf }}</span> |
| reference_scaffold/cafeteria/templates/signage/cafeteria_week.html:20 | {% set page_label = page_days\|weekday_range_label %} |
| reference_scaffold/cafeteria/templates/signage/cafeteria_week.html:28 | {% set time_label = meal\|service_time_label('staff_guest') %} |
| reference_scaffold/cafeteria/templates/signage/cafeteria_week.html:29 | <header class="card-header bg-teal-lt"><h2 class="card-title mb-0">{{ day.weekday }}</h2><span>{{ day.date\|date_short }}{% if time_label %} · {{ time_label }}{% endif %}</span></header> |
| reference_scaffold/cafeteria/templates/signage/cafeteria_week.html:44 | <footer class="card-footer"><span>Mitarbeitende CHF {{ option.prices.internal_rappen\|chf }}</span><span>Externe CHF {{ option.prices.external_rappen\|chf }}</span></footer> |
| reference_scaffold/cafeteria/templates/signage/patient_week.html:27 | {% set page_label = days\|weekday_range_label %} |
| reference_scaffold/cafeteria/templates/signage/patient_week.html:35 | <header class="card-header d-flex flex-column"><h2 class="card-title m-0">{{ day.weekday }}</h2><span>{{ day.date\|date_short }}</span></header> |
| reference_scaffold/cafeteria/templates/signage/patient_week.html:37 | {% set time_label = meal\|service_time_label('patient') if meal else '' %} |
| reference_scaffold/cafeteria/templates/signage/patient_week.html:73 | <header class="card-header d-flex flex-column"><h2 class="card-title m-0">{{ day.weekday }}</h2><span>{{ day.date\|date_short }}</span></header> |
| reference_scaffold/cafeteria/templates/signage/patient_week.html:76 | {% set time_label = meal\|service_time_label('patient') %} |
