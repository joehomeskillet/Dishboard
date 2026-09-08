"""Strict native forms and original signed expectations for profile-free data."""
from __future__ import annotations

import re
from typing import Any, cast

from flask import abort, current_app, g, request
from itsdangerous import BadData, URLSafeTimedSerializer
from sqlalchemy import Engine
from werkzeug.exceptions import Conflict

from ..auth.local_users import ActorExpectation
from ..component_catalog_store import resolve_single_active_location_connection
from ..master_data_types import MasterDataValidationError, ObjectExpectation, VocabularyKind
from ..security import csrf_token, validate_csrf


KINDS = {'zutaten': 'Zutaten', 'einheiten': 'Einheiten', 'kategorien': 'Kategorien', 'tags': 'Tags', 'lagerorte': 'Lagerorte'}
QUERY_KINDS = {'zutaten': 'foods', 'einheiten': 'units', 'kategorien': 'categories', 'tags': 'tags', 'lagerorte': 'storage_locations'}
VOCABULARY: dict[str, VocabularyKind] = {'kategorien': 'food_category', 'tags': 'tag', 'lagerorte': 'storage_location'}
CORE = {'name', 'base_unit_code', 'category_public_id', 'density_g_per_ml', 'piece_weight_g', 'note'}


class FormError(MasterDataValidationError):
    def __init__(self, message: str, field: str = 'name') -> None:
        super().__init__(message)
        self.field = field


class LocationConflict(Conflict):
    description = 'Der aktive Standort wurde geändert. Ihre Eingaben wurden nicht gespeichert.'


def engine() -> Engine:
    return cast(Engine, current_app.extensions['cafeteria_db'])


def location(kind: str) -> int | None:
    if kind == 'einheiten':
        return None
    with engine().connect() as connection:
        return resolve_single_active_location_connection(connection)


def signer() -> URLSafeTimedSerializer:
    if not current_app.secret_key:
        abort(503, description='Formularsignatur nicht verfügbar.')
    return URLSafeTimedSerializer(current_app.secret_key, salt='master-data-form-v1')


def form_token(kind: str, purpose: str, row: Any, scope: int | None) -> str:
    return signer().dumps({
        'actor': g.auth_user.user_id, 'actor_version': g.auth_user.authz_version,
        'kind': kind, 'purpose': purpose, 'target': row.public_id if row else None,
        'version': row.row_version if row else None, 'location': scope, 'csrf': csrf_token(),
    })


def integer(raw: str, field: str, maximum: int = 2**63 - 1) -> int:
    if not re.fullmatch(r'[0-9]{1,19}', raw) or not 1 <= int(raw) <= maximum:
        raise FormError('Bitte eine gültige positive ganze Zahl eingeben.', field)
    return int(raw)


def expectations(kind: str, purpose: str, public_id: str | None) -> tuple[ActorExpectation, ObjectExpectation | None, int | None]:
    if any(len(request.form.getlist(key)) != 1 for key in ('_csrf', '_form_context')):
        abort(400)
    validate_csrf(request.form.get('_csrf'))
    try:
        original = signer().loads(request.form['_form_context'])
    except BadData:
        abort(400, description='Formularkontext ist ungültig.')
    if not isinstance(original, dict) or set(original) != {
        'actor', 'actor_version', 'kind', 'purpose', 'target', 'version', 'location', 'csrf',
    }:
        abort(400)
    if any(original[key] != value for key, value in (
        ('kind', kind), ('purpose', purpose), ('target', public_id), ('csrf', request.form['_csrf']),
    )):
        abort(400, description='Formularkontext passt nicht zur Aktion.')
    if (original['actor'], original['actor_version']) != (g.auth_user.user_id, g.auth_user.authz_version):
        abort(401)
    target = None
    if public_id:
        if len(request.form.getlist('row_version')) != 1:
            abort(400)
        version = integer(request.form['row_version'], 'row_version')
        if version != original['version']:
            abort(400, description='Die ursprüngliche Version wurde verändert.')
        target = ObjectExpectation(public_id, version)
    elif original['version'] is not None:
        abort(400)
    if original['location'] != location(kind):
        raise LocationConflict()
    scope = original['location']
    if kind != 'einheiten' and (type(scope) is not int or scope <= 0):
        abort(400, description='Der ursprüngliche Standort fehlt im Formularkontext.')
    return ActorExpectation(original['actor'], original['actor_version']), target, scope


def payload(kind: str, purpose: str, public_id: str | None, allergen_codes: set[str]) -> dict[str, Any]:
    base = {'_csrf', '_form_context'} | ({'row_version'} if public_id else set())
    multiple: set[str] = set()
    optional: set[str] = set()
    if purpose in ('archivieren', 'reaktivieren'):
        fields: set[str] = set()
    elif purpose == 'allergenpruefung':
        fields = {'checked'}
    elif purpose == 'metadaten':
        fields = {'allergen_' + code for code in allergen_codes}
        multiple = {'labels'}
    elif purpose == 'tags':
        fields, multiple = set(), {'tag_public_ids'}
    elif kind == 'zutaten':
        fields = CORE
        multiple = {'storage_location_public_ids'}
        optional = {'prepared_recipe_choice'}
    elif kind == 'einheiten':
        fields = {'display_name'} | ({'code', 'dimension', 'base_factor'} if not public_id else set())
    else:
        fields = {'name'} | ({'code'} if not public_id else set()) | ({'sort_order'} if kind in {'kategorien', 'lagerorte'} else set())
    if request.files or set(request.form) - base - fields - multiple - optional or any(
        len(request.form.getlist(key)) != 1 for key in base | fields
    ) or any(len(request.form.getlist(key)) > 1 for key in optional
    ):
        raise FormError('Formularfelder fehlen oder sind mehrfach beziehungsweise unerwartet vorhanden.')
    values: dict[str, Any] = {key: request.form[key] for key in fields}
    for key in multiple:
        items = request.form.getlist(key)
        if len(items) > 64 or len(items) != len(set(items)):
            raise FormError('Höchstens 64 eindeutige Angaben sind erlaubt.', key)
        values[key] = items
    if 'storage_location_public_ids' in multiple and not values['storage_location_public_ids']:
        raise FormError('Mindestens einen Lagerort auswählen.', 'storage_location_public_ids')
    if 'prepared_recipe_choice' in optional and 'prepared_recipe_choice' in request.form:
        choice = request.form['prepared_recipe_choice']
        if choice:
            match = re.fullmatch(r'([0-9a-fA-F]{8}(?:-[0-9a-fA-F]{4}){3}-[0-9a-fA-F]{12}):([0-9a-f]{64})', choice)
            if match is None:
                raise FormError('Bitte einen gültigen festgeschriebenen Rezeptstand auswählen.', 'prepared_recipe_choice')
            revision, content_hash = match.groups()
            values.update(prepared_recipe_revision_public_id=revision, prepared_recipe_content_hash_sha256=content_hash)
        else:
            values.update(prepared_recipe_revision_public_id=None, prepared_recipe_content_hash_sha256=None)
    for key in ('name', 'display_name', 'base_unit_code', 'code'):
        if key in values and not values[key].strip():
            raise FormError('Dieses Feld ist erforderlich.', key)
    for key in ('category_public_id', 'base_factor', 'density_g_per_ml', 'piece_weight_g'):
        if key in values and values[key] == '':
            values[key] = None
    if 'sort_order' in values:
        values['sort_order'] = integer(values['sort_order'], 'sort_order', 9999)
    if purpose == 'allergenpruefung':
        if values['checked'] not in ('true', 'false'):
            raise FormError('Ungültiger Prüfstatus.', 'checked')
        values['checked'] = values['checked'] == 'true'
    if purpose == 'metadaten':
        allergens = []
        for code in sorted(allergen_codes):
            presence = values.pop('allergen_' + code)
            if presence not in ('absent', 'contains', 'may_contain'):
                raise FormError('Ungültige Allergendeklaration.', 'allergen_' + code)
            if presence != 'absent':
                allergens.append({'code': code, 'presence': presence})
        if len(allergens) > 64:
            raise FormError('Höchstens 64 Allergene sind erlaubt.')
        values['allergens'] = allergens
    return values


def preparation_arguments(kind: str) -> tuple[str, int]:
    allowed = {'recipe_q', 'recipe_page'} if kind == 'zutaten' and request.method == 'GET' else set()
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        abort(400)
    query = request.args.get('recipe_q', '')
    if len(query) > 200 or '\x00' in query:
        raise FormError('Die Rezeptsuche darf höchstens 200 Zeichen enthalten.', 'recipe_q')
    return query, integer(request.args.get('recipe_page', '1'), 'recipe_page', 100000)


def list_arguments() -> tuple[str, int, dict[str, Any]]:
    args = request.args
    query_kind = args.get('kind', 'foods')
    if query_kind not in QUERY_KINDS.values():
        abort(400)
    kind = next(key for key, value in QUERY_KINDS.items() if value == query_kind)
    allowed = {'kind', 'page', 'archived'} | ({'q', 'category', 'tag'} if kind == 'zutaten' else set())
    if set(args) - allowed or any(len(args.getlist(key)) != 1 for key in args):
        abort(400)
    if args.get('archived', '0') not in ('0', '1'):
        abort(400)
    page = integer(args.get('page', '1'), 'page', 100000)
    options: dict[str, Any] = {'include_archived': args.get('archived') == '1', 'limit': 51, 'offset': (page - 1) * 50}
    if kind == 'zutaten':
        options.update(search=args.get('q') or None, category=args.get('category') or None, tag=args.get('tag') or None)
    return kind, page, options
