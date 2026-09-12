"""Original signed recipe expectations and bounded native aggregate forms."""
from __future__ import annotations

from collections.abc import Mapping
from dataclasses import dataclass
import re
from typing import Any

from flask import current_app, g, request
from itsdangerous import BadData, URLSafeTimedSerializer
from werkzeug.datastructures import MultiDict
from werkzeug.exceptions import Unauthorized

from .. import recipe_store
from ..auth.local_users import ActorExpectation
from ..master_data_types import ObjectExpectation
from ..recipe_types import RecipeConfigurationError, RecipeConflictError, RecipeValidationError
from .. import recipe_values as values
from ..security import csrf_token, validate_csrf

ACTIONS = frozenset('recipe.create recipe.update recipe.archive recipe.reactivate recipe.freeze recipe.image '
                    'cookbook.create cookbook.update cookbook.recipes cookbook.archive cookbook.reactivate'.split())
HEAD = ('title', 'description', 'servings', 'servings_unit_code', 'prep_minutes', 'cook_minutes')
SOURCE = ('kind', 'reference', 'url', 'note', 'fetched_at')
ROWS = {
    'ingredients': ('line_public_id', 'group_label', 'ingredient_text', 'food_public_id', 'quantity',
                    'unit_code', 'note', 'source_kind', 'source_reference', 'fetched_at'),
    'steps': ('instruction', 'duration_minutes', 'image_sha256'),
    'images': ('sha256', 'caption', 'source_url', 'source_license', 'fetched_at'),
}
CONTROL = {'_csrf', '_form_context', 'row_version', 'row_action', 'row_index', 'row_kind'}


class FormError(RecipeValidationError):
    def __init__(self, message: str, field: str = 'title') -> None:
        super().__init__(message)
        self.field = field


class LocationConflict(RecipeConflictError):
    """Verified original context now belongs to a different active location."""


@dataclass(frozen=True)
class FormExpectations:
    actor: ActorExpectation
    target: ObjectExpectation | None
    expected_location_id: int
    display_values: tuple[tuple[str, str], ...]
    dependency_hash_sha256: str | None = None


def _signer() -> URLSafeTimedSerializer:
    if not current_app.secret_key:
        raise RecipeConfigurationError('Formularsignatur nicht verfügbar.')
    return URLSafeTimedSerializer(current_app.secret_key, salt='recipe-form-v1')


def _labels(labels: object) -> dict[str, str]:
    if not isinstance(labels, Mapping) or len(labels) > 256 or any(
        not isinstance(key, str) or not isinstance(value, str) or len(key) > 128 or len(value) > 500
        for key, value in labels.items()
    ):
        raise FormError('Ungültige ursprüngliche Auswahlnamen.')
    return dict(labels)


def sign_context(*, action: str, target: ObjectExpectation | None, expected_location_id: int,
                 display_values: Mapping[str, str] | None = None,
                 dependency_hash_sha256: str | None = None) -> str:
    if request.method != 'GET':
        raise FormError('Ein neuer Formularkontext darf nur beim Laden entstehen.')
    if action not in ACTIONS or (target is None) != action.endswith('.create'):
        raise FormError('Ungültiger Formularzweck.')
    if action == 'recipe.freeze':
        if not isinstance(dependency_hash_sha256, str) or re.fullmatch('[0-9a-f]{64}', dependency_hash_sha256) is None:
            raise FormError('Der ursprüngliche Zutatenstand fehlt.', '_form_context')
    elif dependency_hash_sha256 is not None:
        raise FormError('Zutatenstand passt nicht zur Aktion.', '_form_context')
    actor = g.auth_user
    data = {'action': action, 'actor': values.positive(actor.user_id),
            'actor_version': values.positive(actor.authz_version),
            'target': values.identifier(target.public_id) if target else None,
            'version': values.positive(target.row_version) if target else None,
            'location': values.positive(expected_location_id), 'csrf': csrf_token(),
            'labels': _labels(display_values or {})}
    if action == 'recipe.freeze':
        data['dependency_hash_sha256'] = dependency_hash_sha256
    return _signer().dumps(data)


def read_context(*, action: str, target_public_id: str | None,
                 form: MultiDict[str, str] | None = None) -> FormExpectations:
    form = request.form if form is None else form
    if action not in ACTIONS or any(len(form.getlist(key)) != 1 for key in ('_csrf', '_form_context')):
        raise FormError('Ungültiger Formularkontext.', '_form_context')
    csrf = form['_csrf']
    if not csrf.isascii() or not 1 <= len(csrf) <= 128:
        raise FormError('CSRF-Prüfung fehlgeschlagen.', '_csrf')
    validate_csrf(csrf)
    if len(form['_form_context']) > 200000:
        raise FormError('Formularkontext zu groß.', '_form_context')
    try:
        data = _signer().loads(form['_form_context'])
    except BadData:
        raise FormError('Formularkontext ist ungültig.', '_form_context') from None
    keys = {'action', 'actor', 'actor_version', 'target', 'version', 'location', 'csrf', 'labels'}
    if action == 'recipe.freeze':
        keys.add('dependency_hash_sha256')
    if not isinstance(data, dict) or set(data) != keys:
        raise FormError('Formularkontext ist ungültig.', '_form_context')
    dependency = data.get('dependency_hash_sha256')
    if action == 'recipe.freeze' and (not isinstance(dependency, str) or re.fullmatch('[0-9a-f]{64}', dependency) is None):
        raise FormError('Der ursprüngliche Zutatenstand fehlt oder wurde verändert.', '_form_context')
    expected_id = values.identifier(target_public_id) if target_public_id is not None else None
    if (data['action'], data['target'], data['csrf']) != (action, expected_id, csrf):
        raise FormError('Formularkontext passt nicht zur Aktion.', '_form_context')
    actor = ActorExpectation(values.positive(data['actor']), values.positive(data['actor_version']))
    current = getattr(g, 'auth_user', None)
    if current is None or (actor.user_id, actor.authz_version) != (current.user_id, current.authz_version):
        raise Unauthorized()
    target = None
    if expected_id is not None:
        raw = form.get('row_version', '')
        if len(form.getlist('row_version')) != 1 or not re.fullmatch(r'[1-9][0-9]{0,18}', raw):
            raise FormError('Ursprüngliche Version fehlt.', 'row_version')
        version = values.positive(int(raw))
        if type(data['version']) is not int or version != data['version']:
            raise FormError('Ursprüngliche Version wurde verändert.', 'row_version')
        target = ObjectExpectation(expected_id, version)
    elif data['version'] is not None or 'row_version' in form or not action.endswith('.create'):
        raise FormError('Neuanlage besitzt keine Objektversion.', 'row_version')
    location = values.positive(data['location'])
    labels = tuple(_labels(data['labels']).items())
    g.recipe_form_display_values = dict(labels)
    if recipe_store.get_location(current_app.extensions['cafeteria_db']) != location:
        raise LocationConflict('Der aktive Standort wurde geändert. Ihre Eingaben wurden nicht gespeichert.')
    return FormExpectations(actor, target, location, labels, dependency)


def _checked(field, function, *args, **kwargs):
    try:
        return function(*args, **kwargs)
    except RecipeValidationError as error:
        raise FormError(str(error), field) from error


def parse_recipe_form(form: MultiDict[str, str], *, structural_only: bool = False) -> dict:
    if not structural_only and {'row_action', 'row_kind', 'row_index'} & set(form):
        raise FormError('Zeilenaktionen dürfen nicht als Speichern gesendet werden.')
    if len(list(form.items(multi=True))) > 1400:
        raise FormError('Zu viele Formularfelder.')
    scalar = set(HEAD) | {'source.' + field for field in SOURCE}
    grouped: dict[str, dict[int, dict[str, str]]] = {kind: {} for kind in ROWS}
    for key in form:
        if key in scalar | CONTROL | {'tag_public_ids'}:
            continue
        match = re.fullmatch(r'(ingredients|steps|images)\.(0|[1-9][0-9]?)\.([a-z0-9_]+)', key)
        if not match or int(match[2]) >= 64 or match[3] not in ROWS[match[1]]:
            raise FormError('Unerwartetes Formularfeld.', key)
        grouped[match[1]].setdefault(int(match[2]), {})[match[3]] = form[key]
        scalar.add(key)
    for key in scalar:
        if len(form.getlist(key)) != 1:
            raise FormError('Feld fehlt oder ist mehrfach vorhanden.', key)
    for key in CONTROL & set(form):
        if len(form.getlist(key)) != 1:
            raise FormError('Steuerfeld ist mehrfach vorhanden.', key)
    for key, value in form.items(multi=True):
        maximum = 200000 if key == '_form_context' else 16000
        if not isinstance(value, str) or len(value) > maximum:
            raise FormError('Formularwert ist zu groß.', key)
    tags = form.getlist('tag_public_ids')
    if len(tags) > 64 or len(set(tags)) != len(tags):
        raise FormError('Höchstens 64 eindeutige Tags.', 'tag_public_ids')
    result: dict[str, Any] = {key: form[key] for key in HEAD}
    result['source'] = {key: form['source.' + key] for key in SOURCE}
    result['tag_public_ids'] = tags
    for kind, indexed in grouped.items():
        if sorted(indexed) != list(range(len(indexed))):
            raise FormError('Zeilennummern müssen lückenlos sein.', kind)
        for index, row in indexed.items():
            if set(row) != set(ROWS[kind]):
                raise FormError('Zeilenfelder fehlen.', f'{kind}.{index}')
        result[kind] = [indexed[index] for index in sorted(indexed)]
    if structural_only:
        return result
    for field, maximum, multiline, required in [('title', 120, False, True), ('description', 2000, True, False)]:
        result[field] = _checked(field, values.recipe_text, result[field] or None, maximum, multiline=multiline, required=required)
    for field in ('prep_minutes', 'cook_minutes'):
        result[field] = _minutes(result[field], field)
    amount = _quantity(result['servings'] or None, result['servings_unit_code'] or None, 'servings', 'servings_unit_code')
    if amount.quantity is None:
        raise FormError('Ausbeute erforderlich.', 'servings')
    source = {key: value or None for key, value in result['source'].items()}
    for field, maximum in [('reference', 200), ('url', 2048), ('note', 500)]:
        _checked('source.' + field, values.recipe_text, source[field], maximum, required=False)
    _checked('source.fetched_at', values.timestamp, source['fetched_at'])
    if source['kind'] not in ('manual', 'url', 'file_import', 'ai_assisted'):
        raise FormError('Ungültige Herkunftsart.', 'source.kind')
    if source['url'] and not re.match(r'^https?://', source['url']):
        raise FormError('HTTP-Quellenadresse erforderlich.', 'source.url')
    if source['kind'] != 'manual':
        for field in ['reference', 'fetched_at'] + (['url'] if source['kind'] == 'url' else ['note']):
            if not source[field]:
                raise FormError('Quellenbeleg fehlt.', 'source.' + field)
    result['source'] = _checked('source.kind', values.source, source)
    for index, row in enumerate(result['ingredients']):
        prefix = f'ingredients.{index}.'
        for field in row:
            row[field] = row[field] or None
        for field, maximum in [('ingredient_text', 500), ('group_label', 120), ('note', 500), ('source_reference', 200)]:
            row[field] = _checked(prefix + field, values.recipe_text, row[field], maximum, required=field == 'ingredient_text')
        for field in ('line_public_id', 'food_public_id'):
            if row[field] is not None:
                row[field] = _checked(prefix + field, values.identifier, row[field])
        _quantity(row['quantity'], row['unit_code'], prefix + 'quantity', prefix + 'unit_code')
        row['fetched_at'] = _checked(prefix + 'fetched_at', values.timestamp, row['fetched_at'])
        if row['source_kind'] not in ('manual', 'url', 'file_import', 'ai_assisted'):
            raise FormError('Ungültige Herkunftsart.', prefix + 'source_kind')
        if row['source_kind'] != 'manual' and (not row['source_reference'] or not row['fetched_at']):
            raise FormError('Quellenbeleg fehlt.', prefix + ('source_reference' if not row['source_reference'] else 'fetched_at'))
    for index, row in enumerate(result['steps']):
        prefix = f'steps.{index}.'
        row['instruction'] = _checked(prefix + 'instruction', values.recipe_text, row['instruction'], 8000, multiline=True)
        row['duration_minutes'] = _minutes(row['duration_minutes'], prefix + 'duration_minutes')
        row['image_sha256'] = row['image_sha256'] or None
        if row['image_sha256'] is not None and not re.fullmatch('[0-9a-f]{64}', row['image_sha256']):
            raise FormError('Ungültiger Schrittbildhash.', prefix + 'image_sha256')
    for index, row in enumerate(result['images']):
        for field, maximum in [('caption', 500), ('source_url', 2048), ('source_license', 500)]:
            _checked(f'images.{index}.{field}', values.recipe_text, row[field] or None, maximum, required=False)
        _checked(f'images.{index}.fetched_at', values.timestamp, row['fetched_at'] or None)
        if row['source_url']:
            if not re.match(r'^https?://', row['source_url']):
                raise FormError('HTTP-Quellenadresse erforderlich.', f'images.{index}.source_url')
            for field in ('source_license', 'fetched_at'):
                if not row[field]:
                    raise FormError('Bildquelle benötigt Lizenz und Abrufzeit.', f'images.{index}.{field}')
        result['images'][index] = _checked(f'images.{index}.sha256', values.image_fields, {key: value or None for key, value in row.items()})
    result['tag_public_ids'] = [_checked('tag_public_ids', values.identifier, tag) for tag in tags]
    return _checked('title', values.recipe_payload, result)


def _minutes(raw: str, field: str) -> int | None:
    if raw == '':
        return None
    if not re.fullmatch(r'[0-9]{1,5}', raw):
        raise FormError('Minuten müssen zwischen 0 und 10080 liegen.', field)
    return _checked(field, values.recipe_minutes, int(raw))


def _quantity(amount, code, amount_field, code_field):
    if code is not None and not re.fullmatch(r'[A-Z][A-Z0-9_]{0,15}', code):
        raise FormError('Ungültiger Einheitencode.', code_field)
    field = code_field if amount is not None and code is None else amount_field
    return _checked(field, values.quantity_pair, amount, code)
