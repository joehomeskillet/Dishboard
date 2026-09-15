"""Admin shopping-list routes: create, compute, check off, manual items, CAS conflicts.

Every request builds a fresh ``ShoppingScope`` from the original request actor
(``g.auth_user``, set by ``require_capability``) and the currently active location;
all reads/writes go through ``shopping_list_store`` so authz/location/CAS checks
happen exactly once, in the store. GET never writes. Result lines render only the
names captured in the revision snapshot (no per-line lookup); ``?revision=`` shows an
older receipt read-only. A validation error with a known ``field`` is marked at that
field and linked from the summary; submitted values are kept.
"""
from __future__ import annotations

from itertools import groupby
from typing import Mapping, NoReturn, cast

from flask import abort, current_app, g, make_response, redirect, render_template, request, session, url_for
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.wrappers import Response

from .. import shopping_list_store as store
from ..branding import BrandingStateError
from ..component_catalog_store import ComponentCatalogConfigurationError
from ..master_data_reads import list_units
from ..print_branding import load_pdf_branding
from ..print_template_config import PrintTemplateValidationError
from ..print_templates import PrintTemplateStateError, active_template
from ..recipe_reads import get_location
from ..roles import capabilities, require_capability
from ..security import validate_csrf
from .rendering import DAY_NAMES
from .routes import bp
from .shopping_pdf import ShoppingPdfError, render_shopping_pdf

POLICIES = (('leaf', 'Blattbedarf (Standard)'), ('prepared', 'Vorbereiteter Bedarf'))
_PROFILE_LABELS = {'patient': 'Patienten', 'staff_guest': 'Cafeteria'}
_CREATE_IDS = {'title': 'title', 'note': 'note', 'menu_week_public_id': 'menu_week_public_id'}
_COMPUTE_IDS = {'component_ids': 'component_ids', 'policy': 'policy'}
_NEW_ITEM_IDS = {'item_text': 'new-item-text', 'quantity': 'new-item-qty', 'unit_code': 'new-item-unit'}
_ITEM_PREFIXES = {'item_text': 'item-text', 'quantity': 'item-qty', 'unit_code': 'item-unit'}
_ITEM_FIELDS = ('item_text', 'quantity', 'unit_code')


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


def _errors(error: store.ShoppingListError | None, element_ids: Mapping[str, str]) -> tuple[dict[str, str], object]:
    """Field messages for the form macros and the summary: a link to the field only when that field is rendered."""
    if error is None:
        return {}, None
    field = error.field
    if field is not None and field in element_ids:
        return {field: str(error)}, {element_ids[field]: str(error)}
    return {}, str(error)


def _no_store(html: str, status: int) -> Response:
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


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


def _list_page(*, values=None, error=None, status=200, include_archived=False):
    scope = _scope()
    try:
        rows = store.list_shopping_lists(_db(), scope, include_archived=include_archived)
    except store.ShoppingListError as caught:
        _bail(caught)
    weeks = _weeks(scope.location_id)
    field_errors, summary = _errors(error, _CREATE_IDS)
    html = render_template(
        'admin/einkaufslisten.html', family='cafeteria', profile='staff_guest',
        rows=rows, weeks=weeks, week_labels={week['public_id']: week['label'] for week in weeks},
        values=values if values is not None else {'title': '', 'note': '', 'menu_week_public_id': ''},
        field_errors=field_errors, summary=summary, can_write=_can_write(), include_archived=include_archived,
    )
    return _no_store(html, status)


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
            return _list_page(values=values, error=error, status=status)
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
            return _list_page(error=error, status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_lists_index'), 303)


def _detail_page(
    public_id: str, *, error: store.ShoppingListError | None = None, status: int = 200, form: str | None = None,
    values: Mapping[str, str] | None = None, item_public_id: str | None = None, compute_week: str | None = None,
    selected_components=None, policy: str = 'leaf', revision: str | None = None,
):
    """``form`` names the posted form (``compute``, ``new_item`` or ``item``) whose fields carry the error and ``values``."""
    scope = _scope()
    try:
        detail = store.get_shopping_list(_db(), scope, public_id, revision_public_id=revision)
    except store.ShoppingListError as caught:
        _bail(caught)
    selected = detail['selected_revision']
    is_latest_view = selected is None or selected['is_latest']
    can_write = _can_write()
    weeks = _weeks(scope.location_id)
    week_public_id = compute_week if compute_week is not None else (detail['menu_week_public_id'] or '')
    candidates: tuple[Mapping[str, object], ...] = ()
    if week_public_id and is_latest_view and can_write and not detail['archived_at']:
        try:
            candidates = store.candidate_components(_db(), scope, menu_week_public_id=week_public_id)
        except store.ShoppingListError:
            candidates = ()
    element_ids: Mapping[str, str] = {}
    if form == 'compute' and candidates:
        element_ids = _COMPUTE_IDS
    elif form == 'new_item':
        element_ids = _NEW_ITEM_IDS
    elif form == 'item' and any(item['public_id'] == item_public_id for item in detail['manual_items']):
        element_ids = {field: f'{prefix}-{item_public_id}' for field, prefix in _ITEM_PREFIXES.items()}
    field_errors, summary = _errors(error, element_ids)
    units = list_units(_db(), limit=500)
    blank = dict.fromkeys(_ITEM_FIELDS, '')
    html = render_template(
        'admin/einkaufsliste.html', family='cafeteria', profile='staff_guest', day_names=DAY_NAMES,
        detail=detail, selected=selected, weeks=weeks, week_labels={week['public_id']: week['label'] for week in weeks},
        candidates=_grouped_candidates(candidates), week_public_id=week_public_id, policies=POLICIES,
        policy=policy, selected_components=selected_components or set(), can_write=can_write,
        is_latest_view=is_latest_view, summary=summary, field_errors=field_errors, error_form=form,
        new_item_values=values if form == 'new_item' and values else blank,
        item_values=values if form == 'item' else None, error_item=item_public_id if form == 'item' else None,
        units=units, unit_names={unit.code: unit.display_name for unit in units},
    )
    return _no_store(html, status)


@bp.get('/einkaufslisten/<public_id>')
@require_capability('draft.read')
def shopping_list_detail(public_id: str) -> Response:
    return _detail_page(
        public_id, compute_week=request.args.get('compute_week'), revision=request.args.get('revision') or None,
    )


def _reject_unknown_query(allowed: set[str]) -> None:
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise store.ShoppingListValidationError('Ungültige Druckparameter.')


def _pdf_error(message: str, status: int) -> Response:
    response = make_response(message, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/einkaufslisten/<public_id>/druck.pdf')
@require_capability('draft.read')
def shopping_list_pdf(public_id: str) -> Response:
    """One immutable revision, rendered from the same snapshot as the detail page; no live reads."""
    try:
        _reject_unknown_query({'revision'})
        scope = _scope()
        detail = store.get_shopping_list(_db(), scope, public_id, revision_public_id=request.args.get('revision'))
    except store.ShoppingListError as error:
        _bail(error)
    raw_selected = detail['selected_revision']
    if raw_selected is None:
        abort(404)
    selected = cast(Mapping[str, object], raw_selected)
    try:
        with _db().connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with connection.begin():
                connection.execute(text('SET TRANSACTION READ ONLY'))
                config, template_revision_id = active_template(connection, 'recipe')
                branding = load_pdf_branding(connection, 'recipe', config)
        data = render_shopping_pdf(detail, config=config, branding=branding)
    except (PrintTemplateStateError, PrintTemplateValidationError, BrandingStateError, ShoppingPdfError):
        return _pdf_error(
            'Diese Einkaufsliste kann mit der aktiven Druckvorlage nicht vollständig als PDF ausgegeben werden.', 422)
    except SQLAlchemyError:
        return _pdf_error('Einkaufslisten sind derzeit nicht verfügbar. Bitte später erneut versuchen.', 503)
    revision_number = cast(int, selected['revision_number'])
    revision_id = cast(str, selected['public_id'])
    response = Response(data, mimetype='application/pdf')
    response.headers['Content-Disposition'] = (
        f'inline; filename="einkaufsliste-{public_id}-beleg-{revision_number}.pdf"')
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Shopping-List-Revision'] = revision_id
    response.headers['X-Print-Template-Revision'] = template_revision_id
    return response


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
                                policy=policy, error=error, form='compute', status=400)
        if status == 409:
            return _detail_page(public_id, compute_week=week, error=error, status=409)
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
            return _detail_page(public_id, error=error, status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_list_detail', public_id=public_id), 303)


def _item_values() -> dict[str, str]:
    return {field: request.form.get(field, '') for field in _ITEM_FIELDS}


@bp.post('/einkaufslisten/<public_id>/positionen')
@require_capability('draft.write')
def shopping_list_manual_create(public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    scope = _scope()
    values = _item_values()
    try:
        store.add_manual_item(
            _db(), scope, public_id, item_text=values['item_text'],
            quantity=values['quantity'] or None, unit_code=values['unit_code'] or None,
        )
    except store.ShoppingListError as error:
        status = _status_for(error)
        if status in (400, 409):
            return _detail_page(public_id, error=error, form='new_item', values=values, status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_list_detail', public_id=public_id), 303)


@bp.post('/einkaufslisten/<public_id>/positionen/<item_public_id>')
@require_capability('draft.write')
def shopping_list_manual_update(public_id: str, item_public_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    scope = _scope()
    action = request.form.get('action', 'save')
    values = _item_values()
    try:
        expected = _row_version(request.form.get('expected_row_version', ''))
        if action == 'delete':
            store.delete_manual_item(_db(), scope, public_id, item_public_id, expected_row_version=expected)
        elif action in ('check', 'uncheck'):
            store.set_manual_item_checked(
                _db(), scope, public_id, item_public_id, expected_row_version=expected, checked=action == 'check',
            )
        else:
            store.update_manual_item(
                _db(), scope, public_id, item_public_id, expected_row_version=expected,
                item_text=values['item_text'], quantity=values['quantity'] or None,
                unit_code=values['unit_code'] or None,
            )
    except store.ShoppingListError as error:
        status = _status_for(error)
        if status == 400 and action == 'save':
            return _detail_page(public_id, error=error, form='item', values=values, item_public_id=item_public_id, status=400)
        if status in (400, 409):  # a conflict reloads the current item state; nothing submitted is re-shown
            return _detail_page(public_id, error=error, status=status)
        _bail(error)
    return redirect(url_for('admin.shopping_list_detail', public_id=public_id), 303)
