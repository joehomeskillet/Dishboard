"""Admin shopping-list routes: create, compute, check off, manual items, CAS conflicts.

Every request builds a fresh ``ShoppingScope`` from the original request actor
(``g.auth_user``, set by ``require_capability``) and the currently active location;
all reads/writes go through ``shopping_list_store`` so authz/location/CAS checks
happen exactly once, in the store. GET never writes.
"""
from __future__ import annotations

from itertools import groupby
from typing import Mapping, NoReturn

from flask import abort, current_app, g, make_response, redirect, render_template, request, session, url_for
from sqlalchemy import text
from werkzeug.wrappers import Response

from .. import shopping_list_store as store
from ..component_catalog_store import ComponentCatalogConfigurationError
from ..master_data_reads import get_food, list_units
from ..master_data_types import MasterDataNotFoundError
from ..recipe_reads import get_location
from ..roles import capabilities, require_capability
from ..security import validate_csrf
from .rendering import DAY_NAMES
from .routes import bp

POLICIES = (('leaf', 'Blattbedarf (Standard)'), ('prepared', 'Vorbereiteter Bedarf'))
_PROFILE_LABELS = {'patient': 'Patienten', 'staff_guest': 'Cafeteria'}


def _db():
    return current_app.extensions['cafeteria_db']


def _can_write() -> bool:
    allowed = capabilities()
    return '*' in allowed or 'draft.write' in allowed


def _scope() -> store.ShoppingScope:
    try:
        location = get_location(_db())
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    return store.ShoppingScope(g.auth_user.user_id, location, g.auth_user.authz_version)


def _status_for(error: store.ShoppingListError) -> int:
    if isinstance(error, store.ShoppingListStaleActorError):
        session.clear()
        return 401
    if isinstance(error, store.ShoppingListActorDeniedError):
        return 403
    if isinstance(error, store.ShoppingListRetryError):
        return 409
    if isinstance(error, store.ShoppingListConflictError):
        return 409
    if isinstance(error, store.ShoppingListValidationError):
        return 400
    if isinstance(error, store.ShoppingListNotFoundError):
        return 404
    return 503


def _bail(error: store.ShoppingListError) -> NoReturn:
    abort(_status_for(error), description=str(error))


def _row_version(raw: str) -> int:
    try:
        value = int(raw)
    except ValueError:
        raise store.ShoppingListValidationError('Ungültiger Bearbeitungsstand.') from None
    if value <= 0:
        raise store.ShoppingListValidationError('Ungültiger Bearbeitungsstand.')
    return value


def _weeks(location_id: int) -> tuple[dict[str, str], ...]:
    with _db().connect() as connection:
        rows = connection.execute(text('''
            SELECT w.public_id, w.week_start, w.title, p.code AS profile_code
            FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            WHERE w.location_id=:location ORDER BY w.week_start DESC, w.id DESC LIMIT 200
        '''), {'location': location_id}).mappings().all()
    result = []
    for row in rows:
        label = f"{row['week_start']:%d.%m.%Y} · {_PROFILE_LABELS.get(row['profile_code'], row['profile_code'])}"
        if row['title']:
            label += f" · {row['title']}"
        result.append({'public_id': str(row['public_id']), 'label': label})
    return tuple(result)


def _grouped_candidates(rows: tuple[Mapping[str, object], ...]) -> list[dict[str, object]]:
    groups = []
    for (service_date, meal_name), day_rows in groupby(rows, key=lambda row: (row['service_date'], row['meal_period_display_name'])):
        items = []
        for (item_id, item_title), item_rows in groupby(day_rows, key=lambda row: (row['menu_item_public_id'], row['menu_item_title'])):
            items.append({'menu_item_public_id': item_id, 'menu_item_title': item_title, 'components': list(item_rows)})
        groups.append({'service_date': service_date, 'meal_period_display_name': meal_name, 'menu_items': items})
    return groups


def _food_names(lines: tuple[Mapping[str, object], ...], incomplete: tuple[Mapping[str, object], ...]) -> dict[str, str]:
    """Display names for result lines; the store snapshot only carries the food's public_id."""
    cache: dict[str, str] = {}
    for line in (*lines, *incomplete):
        food_public_id = line.get('food_public_id')
        if not food_public_id or food_public_id in cache:
            continue
        try:
            cache[food_public_id] = get_food(_db(), food_public_id).name
        except MasterDataNotFoundError:
            pass
    return cache


def _list_page(*, values=None, error=None, status=200, include_archived=False):
    scope = _scope()
    try:
        rows = store.list_shopping_lists(_db(), scope, include_archived=include_archived)
    except store.ShoppingListError as caught:
        _bail(caught)
    weeks = _weeks(scope.location_id)
    week_labels = {week['public_id']: week['label'] for week in weeks}
    html = render_template(
        'admin/einkaufslisten.html', family='cafeteria', profile='staff_guest',
        rows=rows, weeks=weeks, week_labels=week_labels,
        values=values if values is not None else {'title': '', 'note': '', 'menu_week_public_id': ''},
        error=error, can_write=_can_write(), include_archived=include_archived,
    )
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/einkaufslisten')
@require_capability('draft.read')
def shopping_lists_index() -> Response:
    return _list_page(include_archived=request.args.get('archived') == '1')


@bp.post('/einkaufslisten')
@require_capability('draft.write')
def shopping_lists_create() -> Response:
    validate_csrf(request.form.get('_csrf'))
    values = {'title': request.form.get('title', ''), 'note': request.form.get('note', ''),
              'menu_week_public_id': request.form.get('menu_week_public_id', '')}
    scope = _scope()
    try:
        public_id = store.create_shopping_list(
            _db(), scope, title=values['title'], note=values['note'] or None,
            menu_week_public_id=values['menu_week_public_id'] or None,
        )
    except store.ShoppingListError as error:
        status = _status_for(error)
        if status in (400, 409):
            return _list_page(values=values, error=str(error), status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_list_detail', public_id=public_id), 303)


@bp.post('/einkaufslisten/<public_id>/archivieren')
@require_capability('draft.write')
def shopping_list_archive(public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    scope = _scope()
    try:
        expected = _row_version(request.form.get('row_version', ''))
        store.archive_shopping_list(_db(), scope, public_id, expected_row_version=expected)
    except store.ShoppingListError as error:
        status = _status_for(error)
        if status in (400, 409):
            return _list_page(error=str(error), status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_lists_index'), 303)


def _detail_page(
    public_id: str, *, error=None, status=200, compute_week=None, selected_components=None,
    policy='leaf', manual_error=None, manual_values=None, viewed_revision_public_id=None,
):
    scope = _scope()
    try:
        detail = store.get_shopping_list(_db(), scope, public_id)
    except store.ShoppingListError as caught:
        _bail(caught)
    weeks = _weeks(scope.location_id)
    week_labels = {week['public_id']: week['label'] for week in weeks}
    revisions = detail['revisions']
    latest_public_id = revisions[0]['public_id'] if revisions else None
    viewed = next((rev for rev in revisions if rev['public_id'] == viewed_revision_public_id), None) \
        if viewed_revision_public_id else None
    is_latest_view = viewed is None or viewed['public_id'] == latest_public_id
    current_number = viewed['revision_number'] if viewed else (revisions[0]['revision_number'] if revisions else 0)
    week_public_id = compute_week if compute_week is not None else (detail['menu_week_public_id'] or '')
    candidates: tuple[Mapping[str, object], ...] = ()
    if week_public_id and is_latest_view:
        try:
            candidates = store.candidate_components(_db(), scope, menu_week_public_id=week_public_id)
        except store.ShoppingListError:
            candidates = ()
    food_names: dict[str, str] = {}
    if detail['selected_revision']:
        food_names = _food_names(detail['selected_revision']['lines'], detail['selected_revision']['incomplete_lines'])
    html = render_template(
        'admin/einkaufsliste.html', family='cafeteria', profile='staff_guest', day_names=DAY_NAMES,
        detail=detail, weeks=weeks, week_labels=week_labels, food_names=food_names,
        candidates=_grouped_candidates(candidates), week_public_id=week_public_id, policies=POLICIES,
        policy=policy, selected_components=selected_components or set(), can_write=_can_write(),
        error=error, manual_error=manual_error,
        manual_values=manual_values or {'item_text': '', 'quantity': '', 'unit_code': ''},
        revision_count=len(revisions), current_number=current_number, viewed_revision=viewed,
        viewed_public_id=viewed['public_id'] if viewed else latest_public_id, is_latest_view=is_latest_view,
        units=list_units(_db(), limit=500),
    )
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/einkaufslisten/<public_id>')
@require_capability('draft.read')
def shopping_list_detail(public_id: str) -> Response:
    return _detail_page(
        public_id, compute_week=request.args.get('compute_week'),
        viewed_revision_public_id=request.args.get('revision'),
    )


@bp.post('/einkaufslisten/<public_id>/berechnen')
@require_capability('draft.write')
def shopping_list_compute(public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    scope = _scope()
    week = request.form.get('menu_week_public_id', '') or None
    component_ids = request.form.getlist('component_ids')
    policy = request.form.get('policy', 'leaf')
    try:
        expected = _row_version(request.form.get('row_version', ''))
        store.compute_revision(
            _db(), scope, public_id, component_ids=component_ids, policy=policy, expected_row_version=expected,
        )
    except store.ShoppingListError as error:
        status = _status_for(error)
        if status == 400:
            return _detail_page(public_id, compute_week=week, selected_components=set(component_ids),
                                policy=policy, error=str(error), status=400)
        if status == 409:
            return _detail_page(public_id, compute_week=week, error=str(error), status=409)
        _bail(error)
    return redirect(url_for('admin.shopping_list_detail', public_id=public_id), 303)


@bp.post('/einkaufslisten/<public_id>/zeilen')
@require_capability('draft.write')
def shopping_list_line_toggle(public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    scope = _scope()
    try:
        store.set_line_checked(
            _db(), scope, public_id, revision_public_id=request.form.get('revision_public_id', ''),
            line_key=request.form.get('line_key', ''), checked=request.form.get('checked') == 'true',
        )
    except store.ShoppingListError as error:
        status = _status_for(error)
        if status in (400, 404, 409):
            return _detail_page(public_id, error=str(error), status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_list_detail', public_id=public_id), 303)


@bp.post('/einkaufslisten/<public_id>/positionen')
@require_capability('draft.write')
def shopping_list_manual_create(public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    scope = _scope()
    values = {'item_text': request.form.get('item_text', ''), 'quantity': request.form.get('quantity', ''),
              'unit_code': request.form.get('unit_code', '')}
    try:
        store.add_manual_item(
            _db(), scope, public_id, item_text=values['item_text'],
            quantity=values['quantity'] or None, unit_code=values['unit_code'] or None,
        )
    except store.ShoppingListError as error:
        status = _status_for(error)
        if status in (400, 409):
            return _detail_page(public_id, manual_error=str(error), manual_values=values, status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_list_detail', public_id=public_id), 303)


@bp.post('/einkaufslisten/<public_id>/positionen/<item_public_id>')
@require_capability('draft.write')
def shopping_list_manual_update(public_id: str, item_public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    scope = _scope()
    action = request.form.get('action', 'save')
    values = {'item_text': request.form.get('item_text', ''), 'quantity': request.form.get('quantity', ''),
              'unit_code': request.form.get('unit_code', '')}
    try:
        if action == 'delete':
            store.delete_manual_item(_db(), scope, public_id, item_public_id)
        elif action == 'check':
            store.set_manual_item_checked(_db(), scope, public_id, item_public_id, checked=True)
        elif action == 'uncheck':
            store.set_manual_item_checked(_db(), scope, public_id, item_public_id, checked=False)
        else:
            expected = _row_version(request.form.get('expected_row_version', ''))
            store.update_manual_item(
                _db(), scope, public_id, item_public_id, expected_row_version=expected,
                item_text=values['item_text'], quantity=values['quantity'] or None,
                unit_code=values['unit_code'] or None,
            )
    except store.ShoppingListError as error:
        status = _status_for(error)
        if status in (400, 409):
            return _detail_page(public_id, error=str(error), status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_list_detail', public_id=public_id), 303)
