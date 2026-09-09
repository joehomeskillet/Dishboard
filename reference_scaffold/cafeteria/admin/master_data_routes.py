"""Tabler consumers of the stable master-data service, without persistence logic."""
from __future__ import annotations

from functools import wraps
from collections.abc import Callable
from typing import Any, ParamSpec

from flask import abort, current_app, flash, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from .. import master_data_store as store
from ..component_catalog_store import ComponentCatalogConfigurationError
from ..master_data_types import (
    ActorDeniedError, MasterDataConfigurationError, MasterDataConflictError,
    MasterDataNotFoundError, MasterDataUnavailableError, MasterDataValidationError, StaleActorError,
)
from ..roles import capabilities, require_capability
from ..workflow_store import get_dietary_labels_and_allergens
from . import master_data_forms as forms
from .routes import bp

P = ParamSpec('P')


def protected(function: Callable[P, Any]) -> Callable[P, Response]:
    @wraps(function)
    def wrapped(*args: P.args, **kwargs: P.kwargs) -> Response:
        try:
            capability = 'masterdata.write' if request.method == 'POST' else 'draft.read'
            response = make_response(require_capability(capability)(function)(*args, **kwargs))
        except (ComponentCatalogConfigurationError, MasterDataConfigurationError,
                MasterDataUnavailableError, SQLAlchemyError):
            html = current_app.jinja_env.get_template('admin/grundlagen_unavailable.html').render()
            response = make_response(html, 503)
        except HTTPException as error:
            response = make_response(error)
        except (StaleActorError, ActorDeniedError, MasterDataNotFoundError,
                MasterDataValidationError, MasterDataConflictError) as error:
            status = 401 if isinstance(error, StaleActorError) else 403 if isinstance(error, ActorDeniedError) else (
                404 if isinstance(error, MasterDataNotFoundError) else 400 if isinstance(error, MasterDataValidationError) else 409)
            response = make_response(current_app.jinja_env.get_template('admin/grundlagen_unavailable.html').render(
                message=str(error), title='Stammdatenaktion nicht möglich'), status)
        response.headers['Cache-Control'] = 'no-store'
        return response
    return wrapped


def check_kind(kind: str) -> None:
    if kind not in forms.KINDS:
        abort(404)


def complete_choices(reader: Callable[..., Any], *args: Any) -> list[Any]:
    result = []
    offset = 0
    while True:
        batch = reader(forms.engine(), *args, include_archived=True, limit=500, offset=offset)
        result.extend(batch)
        if len(batch) < 500:
            return result
        offset += 500


def choices(row: Any = None) -> dict[str, Any]:
    with forms.engine().connect() as connection:
        labels, allergens = get_dietary_labels_and_allergens(connection)
    for group, existing in ((labels, row.labels if row else ()),
                            (allergens, (code for code, _ in row.allergens) if row else ())):
        active = {item['code'] for item in group}
        for code in existing:
            if code not in active:
                group.append({'code': code, 'display_name': code + ' (nicht mehr auswählbar)'})
    return {
        'units': complete_choices(store.list_units),
        'categories': complete_choices(store.list_vocabulary, 'food_category'),
        'storages': complete_choices(store.list_vocabulary, 'storage_location'),
        'tags': complete_choices(store.list_vocabulary, 'tag'), 'labels': labels, 'allergens': allergens,
    }


def get_row(kind: str, public_id: str) -> Any:
    if kind == 'zutaten':
        return store.get_food(forms.engine(), public_id)
    if kind == 'einheiten':
        return store.get_unit(forms.engine(), public_id)
    return store.get_vocabulary(forms.engine(), forms.VOCABULARY[kind], public_id)


def render_detail(kind: str, row: Any = None, *, error: Exception | None = None, purpose: str | None = None) -> Response:
    scope = forms.location(kind)
    selected = choices(row) if kind == 'zutaten' else {}
    values: dict[str, Any] = dict(vars(row)) if row else {}
    if kind == 'zutaten':
        values.update(base_unit_code=row.base_unit.code if row else 'G',
                      category_public_id=row.category.public_id if row and row.category else '',
                      tag_public_ids=[tag.public_id for tag in row.tags] if row else [],
                      labels=list(row.labels) if row else [],
                      storage_location_public_ids=[item.public_id for item in row.storage_locations] if row else [],
                      prepared_recipe_choice=(row.prepared_recipe.revision_public_id + ':' + row.prepared_recipe.content_hash_sha256) if row and row.prepared_recipe else '')
        query, page = forms.preparation_arguments(kind)
        prepared = list(store.list_prepared_revisions(forms.engine(), search=query or None, limit=26, offset=(page - 1) * 25))
        selected.update(prepared_revisions=prepared[:25], recipe_query=query, recipe_page=page, recipe_has_next=len(prepared) > 25)
        if row and row.prepared_recipe and all(item.revision_public_id != row.prepared_recipe.revision_public_id for item in selected['prepared_revisions']):
            selected['prepared_revisions'].insert(0, row.prepared_recipe)
        endpoint = 'admin.master_data_detail' if row else 'admin.master_data_new'
        route_values = {'kind': kind, **({'public_id': row.public_id} if row else {})}
        selected.update(recipe_search_url=url_for(endpoint, **route_values),
            recipe_prev_url=url_for(endpoint, **route_values, recipe_q=query, recipe_page=page - 1),
            recipe_next_url=url_for(endpoint, **route_values, recipe_q=query, recipe_page=page + 1))
        declarations = dict(row.allergens) if row else {}
        values.update({'allergen_' + item['code']: declarations.get(item['code'], 'absent') for item in selected['allergens']})
    actions = ['stammdaten' if kind == 'zutaten' else 'name', 'archivieren', 'reaktivieren'] if row else ['neu']
    if row and kind == 'zutaten':
        actions += ['tags', 'metadaten', 'allergenpruefung']
    tokens = {action: forms.form_token(kind, action, row, scope) for action in actions}
    versions = {action: row.row_version if row else None for action in actions}
    if error and purpose is not None:
        values.update(request.form.to_dict())
        if kind == 'zutaten' and purpose in {'neu', 'stammdaten'}:
            values['storage_location_public_ids'] = request.form.getlist('storage_location_public_ids')
        if purpose == 'tags':
            values['tag_public_ids'] = request.form.getlist('tag_public_ids')
        if purpose == 'metadaten':
            values['labels'] = request.form.getlist('labels')
            known_labels = {item['code'] for item in selected['labels']}
            selected['labels'].extend({'code': code, 'display_name': code + ' (ungültige Auswahl, bitte entfernen)'}
                                      for code in values['labels'] if code not in known_labels)
        tokens[purpose] = request.form.get('_form_context', '')
        versions[purpose] = request.form.get('row_version')
    allowed = capabilities()
    template = 'food' if kind == 'zutaten' else 'unit' if kind == 'einheiten' else 'vocabulary'
    return make_response(render_template(
        f'admin/grundlagen_{template}.html', family='cafeteria', profile='staff_guest', kind=kind,
        kinds=forms.KINDS, query_kinds=forms.QUERY_KINDS, row=row, values=values, tokens=tokens, versions=versions, error=error,
        error_field=getattr(error, 'field', 'display_name' if kind == 'einheiten' else 'name'),
        error_purpose=purpose, can_write='*' in allowed or 'masterdata.write' in allowed, **selected,
    ), 409 if isinstance(error, MasterDataConflictError) else 400 if error else 200)


def render_location_conflict(kind: str, purpose: str, public_id: str | None) -> Response:
    # Recover only the original submission; the new scope must not supply an object or new CAS.
    reload_url = url_for('admin.master_data_detail', kind=kind, public_id=public_id) if public_id else (
        url_for('admin.master_data_new', kind=kind))
    action = url_for('admin.master_data_change', kind=kind, public_id=public_id, purpose=purpose) if public_id else reload_url
    return make_response(render_template(
        'admin/grundlagen_location_conflict.html', family='cafeteria', profile='staff_guest',
        kind=kind, query_kinds=forms.QUERY_KINDS, action=action, reload_url=reload_url,
        submitted=list(request.form.items(multi=True)), message=forms.LocationConflict.description,
    ), 409)


@bp.get('/grundlagen')
@protected
def master_data_list() -> str:
    kind, page, options = forms.list_arguments()
    if kind == 'zutaten':
        rows = store.list_foods(forms.engine(), **options)
    elif kind == 'einheiten':
        rows = store.list_units(forms.engine(), **options)
    else:
        rows = store.list_vocabulary(forms.engine(), forms.VOCABULARY[kind], **options)
    filters: dict[str, Any] = {key: value for key, value in request.args.items() if key != 'page'}
    allowed = capabilities()
    return render_template('admin/grundlagen.html', family='cafeteria', profile='staff_guest',
        kind=kind, kinds=forms.KINDS, query_kinds=forms.QUERY_KINDS, rows=rows[:50], page=page, has_next=len(rows) > 50,
        prev_url=url_for('admin.master_data_list', **filters, page=page - 1),
        next_url=url_for('admin.master_data_list', **filters, page=page + 1),
        categories=complete_choices(store.list_vocabulary, 'food_category') if kind == 'zutaten' else [],
        tags=complete_choices(store.list_vocabulary, 'tag') if kind == 'zutaten' else [],
        can_write='*' in allowed or 'masterdata.write' in allowed)


@bp.route('/grundlagen/<kind>/neu', methods=['GET', 'POST'])
@protected
def master_data_new(kind: str) -> Response:
    check_kind(kind)
    forms.preparation_arguments(kind)
    if request.method == 'GET':
        return render_detail(kind)
    try:
        actor, _, scope = forms.expectations(kind, 'neu', None)
    except forms.LocationConflict:
        return render_location_conflict(kind, 'neu', None)
    try:
        values = forms.payload(kind, 'neu', None, set())
        if kind == 'zutaten':
            result = store.create_food(forms.engine(), actor, {**values, 'source_kind': 'manual'}, original_location=scope)
        elif kind == 'einheiten':
            result = store.create_unit(forms.engine(), actor, **values)
        else:
            result = store.create_vocabulary(forms.engine(), forms.VOCABULARY[kind], actor, original_location=scope, **values)
    except (MasterDataValidationError, MasterDataConflictError) as error:
        return render_detail(kind, error=error, purpose='neu')
    flash('Stammdatensatz angelegt.')
    return redirect(url_for('admin.master_data_detail', kind=kind, public_id=result.public_id), 303)


@bp.get('/grundlagen/<kind>/<public_id>')
@protected
def master_data_detail(kind: str, public_id: str) -> Response:
    check_kind(kind)
    forms.preparation_arguments(kind)
    return render_detail(kind, get_row(kind, public_id))


@bp.post('/grundlagen/<kind>/<public_id>/<purpose>')
@protected
def master_data_change(kind: str, public_id: str, purpose: str) -> Response:
    check_kind(kind)
    allowed = {'archivieren', 'reaktivieren'} | ({'stammdaten', 'tags', 'metadaten', 'allergenpruefung'}
                                              if kind == 'zutaten' else {'name'})
    if purpose not in allowed:
        abort(404)
    if request.args:
        abort(400)
    try:
        actor, target, scope = forms.expectations(kind, purpose, public_id)
    except forms.LocationConflict:
        return render_location_conflict(kind, purpose, public_id)
    row = get_row(kind, public_id)
    if target is None:
        abort(400)
    try:
        codes = {entry['code'] for entry in choices(row)['allergens']} if purpose == 'metadaten' else set()
        values = forms.payload(kind, purpose, public_id, codes)
        if purpose in ('archivieren', 'reaktivieren'):
            active = purpose == 'reaktivieren'
            if kind == 'zutaten':
                store.set_food_active(forms.engine(), actor, target, active=active, original_location=scope)
            elif kind == 'einheiten':
                store.set_unit_active(forms.engine(), actor, target, active=active)
            else:
                store.set_vocabulary_active(forms.engine(), forms.VOCABULARY[kind], actor, target, active=active, original_location=scope)
        elif kind == 'einheiten':
            store.rename_unit(forms.engine(), actor, target, **values)
        elif kind in forms.VOCABULARY:
            store.update_vocabulary(forms.engine(), forms.VOCABULARY[kind], actor, target, original_location=scope, **values)
        elif purpose == 'stammdaten':
            store.update_food(forms.engine(), actor, target, values, original_location=scope)
        elif purpose == 'tags':
            store.replace_food_tags(forms.engine(), actor, target, values['tag_public_ids'], original_location=scope)
        elif purpose == 'metadaten':
            store.replace_food_metadata(forms.engine(), actor, target, original_location=scope, **values)
        else:
            store.set_food_allergen_review(forms.engine(), actor, target, original_location=scope, **values)
    except (MasterDataValidationError, MasterDataConflictError) as error:
        return render_detail(kind, row, error=error, purpose=purpose)
    flash('Stammdatenaktion gespeichert.')
    return redirect(url_for('admin.master_data_detail', kind=kind, public_id=public_id), 303)
