from __future__ import annotations

from datetime import date, timedelta
from typing import Any

from flask import g, render_template, session, url_for
from werkzeug.datastructures import MultiDict

from ..component_catalog_store import AdminScope
from ..workflow import MENU_TYPES, PROFILE_DAYS, PROFILE_MEALS

DAY_NAMES = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')
MONTHS = (
    'Januar', 'Februar', 'März', 'April', 'Mai', 'Juni',
    'Juli', 'August', 'September', 'Oktober', 'November', 'Dezember',
)
MEAL_LABELS = {'LUNCH': 'Mittag', 'DINNER': 'Abend'}
OPTION_LABELS = {'MENU_1': 'Menü 1', 'VEGGIE': 'Vegetarisch'}
STATUS_LABELS = {
    'empty': 'Leer', 'incomplete': 'Unvollständig', 'review_open': 'Prüfung offen',
    'ready': 'Bereit', 'live': 'Live', 'changed': 'Geändert',
}
CATEGORY_LABELS = {
    'meat': 'Fleisch', 'side': 'Beilage', 'vegetable': 'Gemüse',
    'sauce': 'Sauce', 'dessert': 'Dessert', 'other': 'Weiteres',
}


def _chf(rappen: object) -> str:
    if rappen in (None, '', 0):
        return ''
    return f'{int(rappen) / 100:.2f}'


def _template_context() -> dict[str, Any]:
    return {
        'user': session.get('user'),
        'roles': list(getattr(g, 'auth_roles', ())),
    }


def menu_form_values(profile: str, option: dict[str, Any]) -> dict[str, Any]:
    assignments = list(option.get('assignments') or [])
    allergens = list(option.get('allergens') or [])
    origins = list(option.get('origins') or [])
    labels = list(option.get('labels') or [])
    values: dict[str, Any] = {
        'title': str(option.get('title') or ''),
        'description': str(option.get('description') or ''),
        'note': str(option.get('note') or ''),
        'allergen_mode': str(option.get('allergen_mode') or 'manual'),
        'origin_mode': str(option.get('origin_mode') or 'manual'),
        'label_mode': str(option.get('label_mode') or 'manual'),
        'component_public_id': [
            str(assignment.get('component_public_id') or '') for assignment in assignments
        ],
        'component_text': [
            str(assignment.get('component_text') or '') for assignment in assignments
        ],
        'allergen_code': [str(allergen.get('code') or '') for allergen in allergens],
        'allergen_presence': [
            str(allergen.get('presence') or '') for allergen in allergens
        ],
        'origin_ingredient': [str(origin.get('ingredient') or '') for origin in origins],
        'origin_country_code': [
            str(origin.get('country_code') or '') for origin in origins
        ],
        'label_code': [str(label.get('code') or '') for label in labels],
    }
    if profile == 'staff_guest':
        values['internal_chf'] = _chf(option.get('internal_rappen'))
        values['external_chf'] = _chf(option.get('external_rappen'))
    return values


def _lookup(draft: dict[str, Any] | None) -> dict[tuple[str, str, str], dict[str, Any]]:
    cells: dict[tuple[str, str, str], dict[str, Any]] = {}
    if draft is None:
        return cells
    for day in draft['days']:
        for service in day['services']:
            for option in service['options']:
                key = (str(day['date']), str(service['meal_code']), str(option['type_code']))
                cells[key] = {**option, 'service_state': service.get('service_state', 'open')}
    return cells


def _cells(
    profile: str, family: str, week: date, draft: dict[str, Any] | None,
    versions: dict[tuple[str, str, str], int],
    services: dict[tuple[str, str], dict[str, Any]],
) -> list[dict[str, Any]]:
    options = _lookup(draft)
    cells: list[dict[str, Any]] = []
    for offset in range(PROFILE_DAYS[profile]):
        service_day = week + timedelta(days=offset)
        day = service_day.isoformat()
        for meal in PROFILE_MEALS[profile]:
            service = services.get((day, meal), {})
            for option_code in MENU_TYPES:
                option = options.get((day, meal, option_code), {})
                cell: dict[str, Any] = {
                    'day': day, 'day_label': DAY_NAMES[offset],
                    'day_short': f'{service_day.day}. {MONTHS[service_day.month - 1]}',
                    'meal': meal, 'meal_label': MEAL_LABELS[meal],
                    'option': option_code, 'option_label': OPTION_LABELS[option_code],
                    'row_version': versions.get((day, meal, option_code), 0),
                    'service_row_version': int(service.get('row_version', 0)),
                    'title': option.get('title', ''),
                    'components': list(option.get('components') or []),
                    'description': str(option.get('description') or ''),
                    'note': str(option.get('note') or ''),
                    'allergens': list(option.get('allergens') or []),
                    'labels': list(option.get('labels') or []),
                    'origins': list(option.get('origins') or []),
                    'allergen_review_status': option.get('allergen_review_status', 'not_checked'),
                    'review_open': option.get('review_open', True),
                    'service_state': service.get('service_state', 'open'),
                    'notice': str(service.get('notice') or ''),
                    'edit_url': url_for(
                        'admin.menu_get', family=family, week=week.isoformat(),
                        day=day, meal=meal, option=option_code,
                    ),
                }
                if profile == 'staff_guest':
                    cell['internal_chf'] = _chf(option.get('internal_rappen'))
                    cell['external_chf'] = _chf(option.get('external_rappen'))
                cells.append(cell)
    return cells


def render_admin_week(
    profile: str, family: str, week: date, scope: AdminScope, status: str,
    draft: dict[str, Any] | None, versions: dict[tuple[str, str, str], int],
    services: dict[tuple[str, str], dict[str, Any]],
    csrf: str, flashes: list[str],
) -> str:
    return render_template(
        f'admin/{family}.html', profile=profile, family=family, week=week,
        week_iso=week.isoformat(), iso_week=week.isocalendar()[1], scope=scope,
        status=status, status_label=STATUS_LABELS[status], csrf=csrf, flashes=flashes,
        draft=draft, week_row_version=0 if draft is None else int(draft.get('row_version', 0)),
        title='' if draft is None else str(draft.get('title') or ''),
        shared_note='' if draft is None else str(draft.get('shared_note') or ''),
        cells=_cells(profile, family, week, draft, versions, services),
        **_template_context(),
    )


def render_menu_editor(
    profile: str, family: str, week: date, cell: dict[str, Any],
    form_values: dict[str, Any], form_errors: dict[str, Any], csrf: str,
    review_token: str | None, catalog_choices: list[dict[str, Any]],
    allergens: list[dict[str, Any]], labels: list[dict[str, Any]],
    effects: dict[str, Any], flashes: list[str],
    origin_conflict: str | None = None,
) -> str:
    return render_template(
        'admin/menu_editor.html', profile=profile, family=family, week=week,
        week_iso=week.isoformat(), cell=cell, form_values=form_values,
        form_errors=form_errors, csrf=csrf, review_token=review_token,
        catalog_choices=catalog_choices, allergens=allergens, labels=labels,
        effects=effects, flashes=flashes, origin_conflict=origin_conflict,
        **_template_context(),
    )


def render_components(
    profile: str, family: str, rows: list[dict[str, Any]], query: str,
    category: str | None, include_archived: bool, csrf: str, flashes: list[str],
    categories: dict[str, str], allergens: list[dict[str, Any]], labels: list[dict[str, Any]],
    *, form_values: MultiDict[str, str] | None = None, form_errors: dict[str, str] | None = None,
) -> str:
    return render_template(
        'admin/components.html', profile=profile, family=family, rows=rows,
        query=query, category=category, include_archived=include_archived,
        csrf=csrf, flashes=flashes, categories=categories, allergens=allergens, labels=labels,
        form_values=form_values if form_values is not None else {}, form_errors=form_errors or {},
        **_template_context(),
    )


def render_component_detail(
    profile: str, family: str, component: dict[str, Any], csrf: str,
    flashes: list[str], categories: dict[str, str],
    allergens: list[dict[str, Any]], labels: list[dict[str, Any]],
    *, form_values: MultiDict[str, str] | None = None, form_errors: dict[str, str] | None = None,
) -> str:
    return render_template(
        'admin/component_editor.html', profile=profile, family=family,
        component=component, csrf=csrf, flashes=flashes, categories=categories,
        allergens=allergens, labels=labels,
        form_values=form_values if form_values is not None else {}, form_errors=form_errors or {},
        **_template_context(),
    )


def render_admin_preview(
    profile: str, family: str, week: date, state: str, draft: dict[str, Any],
) -> str:
    titles = [
        str(item['title'])
        for day in draft['days'] for service in day['services'] for item in service['options']
    ]
    return render_template(
        'admin/preview.html', profile=profile, family=family, week=week,
        week_iso=week.isoformat(), state=state, draft=draft, titles=titles,
        **_template_context(),
    )
