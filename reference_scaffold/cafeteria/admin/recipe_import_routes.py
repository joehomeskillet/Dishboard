"""Admin recipe-import preview; GET is no-store and never writes."""
from __future__ import annotations

from datetime import datetime, timezone

from flask import current_app, g, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from .. import recipe_import_store as store
from ..auth.local_users import ActorExpectation
from ..master_data_types import ObjectExpectation
from ..recipe_import import parse_recipe_import
from ..recipe_reads import get_location
from ..recipe_types import (
    RecipeActorDeniedError, RecipeConflictError, RecipeNotFoundError, RecipeValidationError,
)
from ..roles import capabilities, require_capability
from ..security import validate_csrf
from .routes import bp

ANNOTATION_LABELS = (
    ('unreviewed', 'ungeprüft'),
    ('proposed_not_measured', 'vorgeschlagen, nicht gemessen'),
    ('allergen_not_checked', 'Allergene nicht geprüft'),
)
DECISIONS = (
    ('undecided', 'Offen'),
    ('create_new', 'Neu anlegen'),
    ('skip_existing', 'Vorhandenes überspringen'),
)


def _db():
    return current_app.extensions['cafeteria_db']


def _actor() -> ActorExpectation:
    return ActorExpectation(g.auth_user.user_id, g.auth_user.authz_version)


def _can_write() -> bool:
    allowed = capabilities()
    return '*' in allowed or 'recipe.write' in allowed


def _can_import() -> bool:
    allowed = capabilities()
    return '*' in allowed or 'recipe.import' in allowed


def _page(
    *, batches=(), batch=None, values=None, error: str | None = None, status: int = 200,
) -> Response:
    html = render_template(
        'admin/rezepte_import.html', family='cafeteria', profile='staff_guest',
        batches=batches, batch=batch, values=values or {}, error=error,
        can_write=_can_write(), can_import=_can_import(),
        annotation_labels=ANNOTATION_LABELS, decisions=DECISIONS,
    )
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


def _content_type(filename: str, declared: str | None) -> str:
    name = filename.lower()
    if name.endswith('.csv'):
        return 'text/csv'
    if name.endswith('.json'):
        return 'application/json'
    if declared in ('text/csv', 'application/json'):
        return declared
    return declared or ''


def _form_payload(batch, form) -> dict[str, object]:
    action = form.get('action', 'save')
    if action in ('acknowledge', 'cancel'):
        return {'action': action}
    rows = []
    for candidate in batch.candidates:
        prefix = f'row.{candidate.row_number}.'
        ingredients = []
        original_ingredients = list(candidate.candidate_payload.get('ingredients') or [])
        for index, ingredient in enumerate(original_ingredients):
            thawed = store.thaw(ingredient)
            item = dict(thawed) if isinstance(thawed, dict) else {}
            item['food_public_id'] = form.get(f'{prefix}ingredient.{index}.food_public_id') or None
            item['unit_code'] = form.get(f'{prefix}ingredient.{index}.unit_code') or item.get('unit_code')
            item['quantity'] = form.get(f'{prefix}ingredient.{index}.quantity') or item.get('quantity')
            ingredients.append(item)
        thawed_payload = store.thaw(candidate.candidate_payload)
        payload = dict(thawed_payload) if isinstance(thawed_payload, dict) else {}
        title = form.get(f'{prefix}title')
        if title is not None:
            payload['title'] = title
        payload['ingredients'] = ingredients
        target = form.get(f'{prefix}target_recipe_public_id') or None
        version = form.get(f'{prefix}target_row_version') or None
        rows.append({
            'row_number': candidate.row_number,
            'candidate_payload': payload,
            'duplicate_decision': form.get(f'{prefix}duplicate_decision', candidate.duplicate_decision),
            'target_recipe_public_id': target,
            'target_row_version': None if version in (None, '') else version,
        })
    return {
        'action': 'save',
        'annotations': [item for item in form.getlist('annotation') if item in store.ANNOTATIONS],
        'rows': rows,
    }


@bp.get('/rezepte/import')
@require_capability('recipe.write')
def recipe_import_list() -> Response:
    return _page(batches=store.list_batches(_db()))


@bp.post('/rezepte/import')
@require_capability('recipe.write')
def recipe_import_create() -> Response:
    validate_csrf(request.form.get('_csrf'))
    upload = request.files.get('source_file')
    batches = store.list_batches(_db())
    if upload is None or not upload.filename:
        return _page(batches=batches, error='Eine CSV- oder JSON-Datei ist erforderlich.', status=400)
    data = upload.read()
    preview = parse_recipe_import(
        data, filename=upload.filename,
        content_type=_content_type(upload.filename, upload.mimetype),
        fetched_at=datetime.now(timezone.utc),
    )
    if preview.errors and not preview.rows:
        message = preview.errors[0].message if preview.errors else 'Ungültige Importdatei.'
        return _page(batches=batches, error=message, status=400)
    try:
        payload = store.payload_from_preview(
            preview, annotations=tuple(
                item for item in request.form.getlist('annotation') if item in store.ANNOTATIONS
            ),
        )
        result = store.create_batch(_db(), _actor(), payload, expected_location_id=get_location(_db()))
    except RecipeValidationError as error:
        return _page(batches=batches, error=str(error), status=400)
    except RecipeConflictError as error:
        return _page(batches=batches, error=str(error), status=409)
    return redirect(url_for('admin.recipe_import_detail', batch_id=result.public_id), 303)


@bp.get('/rezepte/import/<batch_id>')
@require_capability('recipe.write')
def recipe_import_detail(batch_id: str) -> Response:
    try:
        batch = store.get_batch(_db(), batch_id)
    except RecipeNotFoundError:
        return _page(batches=store.list_batches(_db()), error='Unbekannter Importstapel.', status=404)
    except RecipeValidationError:
        return _page(batches=store.list_batches(_db()), error='Unbekannter Importstapel.', status=404)
    return _page(batch=batch, batches=store.list_batches(_db()))


@bp.post('/rezepte/import/<batch_id>')
@require_capability('recipe.write')
def recipe_import_save(batch_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    try:
        batch = store.get_batch(_db(), batch_id)
    except (RecipeNotFoundError, RecipeValidationError):
        return _page(batches=store.list_batches(_db()), error='Unbekannter Importstapel.', status=404)
    values = dict(request.form)
    try:
        expected = int(request.form.get('row_version', ''))
        store.update_batch(
            _db(), _actor(), ObjectExpectation(batch.public_id, expected),
            _form_payload(batch, request.form), expected_location_id=get_location(_db()),
        )
    except RecipeValidationError as error:
        return _page(batch=batch, batches=store.list_batches(_db()), values=values,
                     error=str(error), status=400)
    except RecipeConflictError as error:
        return _page(batch=batch, batches=store.list_batches(_db()), values=values,
                     error=str(error), status=409)
    except RecipeActorDeniedError as error:
        return _page(batch=batch, batches=store.list_batches(_db()), values=values,
                     error=str(error), status=403)
    except ValueError:
        return _page(batch=batch, batches=store.list_batches(_db()), values=values,
                     error='Ursprünglicher Stand erforderlich.', status=400)
    return redirect(url_for('admin.recipe_import_detail', batch_id=batch.public_id), 303)


@bp.post('/rezepte/import/<batch_id>/commit')
@require_capability('recipe.import')
def recipe_import_commit(batch_id: str) -> Response:
    validate_csrf(request.form.get('_csrf'))
    try:
        batch = store.get_batch(_db(), batch_id)
    except (RecipeNotFoundError, RecipeValidationError):
        return _page(batches=store.list_batches(_db()), error='Unbekannter Importstapel.', status=404)
    values = dict(request.form)
    try:
        expected = int(request.form.get('row_version', ''))
        store.commit_batch(
            _db(), _actor(), ObjectExpectation(batch.public_id, expected),
            {'candidate_hash_sha256': request.form.get('candidate_hash_sha256', '')},
            expected_location_id=get_location(_db()),
        )
    except RecipeActorDeniedError as error:
        return _page(batch=batch, batches=store.list_batches(_db()), values=values,
                     error=str(error), status=403)
    except RecipeValidationError as error:
        return _page(batch=batch, batches=store.list_batches(_db()), values=values,
                     error=str(error), status=400)
    except RecipeConflictError as error:
        return _page(batch=batch, batches=store.list_batches(_db()), values=values,
                     error=str(error), status=409)
    except ValueError:
        return _page(batch=batch, batches=store.list_batches(_db()), values=values,
                     error='Ursprünglicher Stand erforderlich.', status=400)
    return redirect(url_for('admin.recipe_import_detail', batch_id=batch.public_id), 303)
