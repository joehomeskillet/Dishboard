from __future__ import annotations

import re
from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from typing import Literal
from uuid import UUID

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import IntegrityError

from .workflow_write_context import actor_parameters, write_transaction

from cafeteria.component_catalog_filters import ComponentFilters
from cafeteria.component_catalog_metadata import (
    AllergenInput,
    MetadataValidationError,
    NormalizedMetadata,
    category as _category,
    component_name as _name,
    escape_like as _escape_like,
    load_public_metadata,
    normalize_metadata,
    origin_country_code as _origin_country_code,
    positive_integer as _positive_integer,
    public_component as _public_component,
    replace_metadata,
    resolve_metadata,
)


_PROFILES = ('patient', 'staff_guest')
_TARGET_SCOPES = ('common', 'current')
_UPDATE_KEYS = frozenset(
    {'category', 'name', 'origin_country_code', 'label_codes', 'allergens'}
)
_UUID_PATTERN = re.compile(
    r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}', re.IGNORECASE
)
_NAME_UNIQUE_CONSTRAINT = 'uq_menu_components_location_scope_name'


ComponentCatalogValidationError = MetadataValidationError


class ComponentCatalogConfigurationError(RuntimeError):
    pass


class ComponentNotFoundError(LookupError):
    pass


class ComponentConflictError(RuntimeError):
    pass


class StaleComponentError(ComponentConflictError):
    pass


@dataclass(frozen=True)
class AdminScope:
    actor_id: int
    location_id: int
    profile_code: Literal['patient', 'staff_guest']
    expected_authz_version: int | None = None

    def __post_init__(self) -> None:
        _positive_integer(self.actor_id, 'actor_id')
        _positive_integer(self.location_id, 'location_id')
        if type(self.profile_code) is not str or self.profile_code not in _PROFILES:
            raise ComponentCatalogValidationError('Ungültiges Profil.')
        if self.expected_authz_version is not None:
            _positive_integer(self.expected_authz_version, 'expected_authz_version')


def resolve_single_active_location_connection(connection: Connection) -> int:
    location_ids = connection.execute(
        text('SELECT id FROM cafeteria.locations WHERE active ORDER BY id')
    ).scalars().all()
    if len(location_ids) != 1:
        raise ComponentCatalogConfigurationError(
            'Es muss genau ein aktiver Standort konfiguriert sein.'
        )
    return int(location_ids[0])


def create_component(
    engine: Engine,
    scope: AdminScope,
    category: str,
    name: str,
    origin_country_code: str | None,
    target_scope: Literal['common', 'current'],
    label_codes: Sequence[str],
    allergens: Sequence[AllergenInput],
) -> dict[str, object]:
    clean_category = _category(category)
    clean_name = _name(name)
    clean_origin = _origin_country_code(origin_country_code)
    clean_metadata = normalize_metadata(label_codes, allergens)
    if type(target_scope) is not str or target_scope not in _TARGET_SCOPES:
        raise ComponentCatalogValidationError('Ungültiger Komponenten-Scope.')
    profile_scope = 'common' if target_scope == 'common' else scope.profile_code
    try:
        with write_transaction(engine, scope) as connection:
            _require_scope_location(connection, scope)
            row = connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.menu_components(
                        location_id, profile_scope, category, name, origin_country_code
                    ) VALUES (
                        :location_id, :profile_scope, :category, :name, :origin_country_code
                    )
                    RETURNING id, public_id::text AS public_id, profile_scope, category, name,
                              origin_country_code, active, row_version, 0::bigint AS usage_count
                    '''
                ),
                {
                    'location_id': scope.location_id,
                    'profile_scope': profile_scope,
                    'category': clean_category,
                    'name': clean_name,
                    'origin_country_code': clean_origin,
                },
            ).mappings().one()
            component_id = int(row['id'])
            resolved = resolve_metadata(connection, component_id, clean_metadata)
            replace_metadata(connection, component_id, resolved)
            public_metadata = load_public_metadata(connection, [component_id])[component_id]
            return _public_component(row, public_metadata)
    except IntegrityError as error:
        _raise_name_conflict(error)
        raise


def find_components(
    engine: Engine,
    scope: AdminScope,
    query: str,
    category: str | None,
    include_archived: bool,
    *,
    filters: ComponentFilters | None = None,
) -> list[dict[str, object]]:
    if type(query) is not str or len(query) > 200:
        raise ComponentCatalogValidationError('Ungültige Suche.')
    clean_category = None if category is None else _category(category)
    if type(include_archived) is not bool:
        raise ComponentCatalogValidationError('Ungültiger Archivfilter.')
    if filters is None:
        filters = ComponentFilters()
    if type(filters) is not ComponentFilters:
        raise ComponentCatalogValidationError('Komponentenfilter sind ungültig.')
    status = filters.status or ('all' if include_archived else 'active')
    escaped_query = _escape_like(query.strip())
    with engine.begin() as connection:
        _require_scope_location(connection, scope)
        if filters.label or filters.allergen not in {'', 'unknown'}:
            known = connection.execute(text('''
                SELECT (:label='' OR EXISTS (
                    SELECT 1 FROM cafeteria.dietary_labels WHERE code=:label))
                  AND (:allergen IN ('', 'unknown') OR EXISTS (
                    SELECT 1 FROM cafeteria.allergens WHERE code=:allergen))
            '''), {'label': filters.label, 'allergen': filters.allergen}).scalar_one()
            if not known:
                raise ComponentCatalogValidationError('Unbekanntes Label oder Allergen im Filter.')
        rows = connection.execute(
            text(
                '''
                SELECT c.id, c.public_id::text AS public_id, c.profile_scope, c.category, c.name,
                       c.origin_country_code, c.active, c.row_version,
                       f.public_id::text AS food_public_id, f.name AS food_name,
                       (SELECT count(*) FROM cafeteria.menu_item_components mic
                        WHERE mic.component_id=c.id) AS usage_count
                FROM cafeteria.menu_components c
                LEFT JOIN cafeteria.foods f ON f.id=c.food_id AND f.location_id=c.location_id
                WHERE c.location_id=:location_id
                  AND c.profile_scope IN ('common', :profile_code)
                  AND (:status='all' OR (:status='active' AND c.active)
                       OR (:status='archived' AND NOT c.active))
                  AND (CAST(:category AS text) IS NULL OR c.category=CAST(:category AS text))
                  AND c.name ILIKE :query ESCAPE E'\\\\'
                  AND (:usage='' OR (:usage='used') = EXISTS (
                      SELECT 1 FROM cafeteria.menu_item_components mic WHERE mic.component_id=c.id))
                  AND (:origin='' OR (:origin='unknown' AND c.origin_country_code IS NULL)
                       OR c.origin_country_code=:origin)
                  AND (:label='' OR EXISTS (
                      SELECT 1 FROM cafeteria.component_labels cl
                      JOIN cafeteria.dietary_labels l ON l.id=cl.label_id
                      WHERE cl.component_id=c.id AND l.code=:label))
                  AND (:allergen='' OR (:allergen='unknown' AND NOT EXISTS (
                      SELECT 1 FROM cafeteria.component_allergens ca WHERE ca.component_id=c.id))
                      OR EXISTS (
                          SELECT 1 FROM cafeteria.component_allergens ca
                          JOIN cafeteria.allergens a ON a.id=ca.allergen_id
                          WHERE ca.component_id=c.id AND a.code=:allergen
                            AND (:presence='' OR ca.presence=:presence)))
                ORDER BY CASE c.category
                             WHEN 'meat' THEN 1
                             WHEN 'side' THEN 2
                             WHEN 'vegetable' THEN 3
                             WHEN 'sauce' THEN 4
                             WHEN 'dessert' THEN 5
                             ELSE 6
                         END,
                         c.active DESC,
                         lower(btrim(c.name)) COLLATE "C",
                         c.public_id::text COLLATE "C"
                '''
            ),
            {
                'location_id': scope.location_id,
                'profile_code': scope.profile_code,
                'status': status,
                'category': clean_category,
                'query': f'%{escaped_query}%',
                'usage': filters.usage, 'origin': filters.origin, 'label': filters.label,
                'allergen': filters.allergen, 'presence': filters.presence,
            },
        ).mappings().all()
        metadata = load_public_metadata(connection, [int(row['id']) for row in rows])
        return [_public_component(row, metadata[int(row['id'])]) for row in rows]


def get_component(
    engine: Engine,
    scope: AdminScope,
    public_id: str,
    *,
    include_archived: bool = True,
) -> dict[str, object]:
    canonical_public_id = _public_id(public_id)
    if type(include_archived) is not bool:
        raise ComponentCatalogValidationError('Ungültiger Archivfilter.')
    with engine.begin() as connection:
        _require_scope_location(connection, scope)
        row = connection.execute(
            text(
                '''
                SELECT c.id, c.public_id::text AS public_id, c.profile_scope, c.category, c.name,
                       c.origin_country_code, c.active, c.row_version,
                       f.public_id::text AS food_public_id, f.name AS food_name,
                       (SELECT count(*) FROM cafeteria.menu_item_components mic
                        WHERE mic.component_id=c.id) AS usage_count
                FROM cafeteria.menu_components c
                LEFT JOIN cafeteria.foods f ON f.id=c.food_id AND f.location_id=c.location_id
                WHERE c.public_id=CAST(:public_id AS uuid)
                  AND c.location_id=:location_id
                  AND c.profile_scope IN ('common', :profile_code)
                  AND (:include_archived OR c.active)
                '''
            ),
            {
                'public_id': canonical_public_id,
                'location_id': scope.location_id,
                'profile_code': scope.profile_code,
                'include_archived': include_archived,
            },
        ).mappings().one_or_none()
        if row is None:
            raise ComponentNotFoundError('Komponente nicht gefunden.')
        component_id = int(row['id'])
        return _public_component(
            row, load_public_metadata(connection, [component_id])[component_id]
        )


def update_component(
    engine: Engine,
    scope: AdminScope,
    public_id: str,
    payload: Mapping[str, object],
    version: int,
) -> int:
    canonical_public_id = _public_id(public_id)
    clean_category, clean_name, clean_origin, clean_metadata = _update_payload(payload)
    food_specified = 'food_public_id' in payload
    requested_food = _food_public_id(payload.get('food_public_id')) if food_specified else None
    expected_version = _positive_integer(version, 'row_version')
    try:
        with write_transaction(engine, scope) as connection:
            row = _lock_component(
                connection, scope, canonical_public_id, expected_version
            )
            component_id = int(row['id'])
            assigned_food_id: object = row['food_id']
            if food_specified:
                # Lock foods after the component row, matching component_binding_state.
                assigned_food_id = _lock_assignment_foods(
                    connection, scope, row['food_id'], requested_food,
                )
            food_changed = row['food_id'] != assigned_food_id
            resolved = resolve_metadata(connection, component_id, clean_metadata)
            scalar_changed = (
                str(row['category']) != clean_category
                or str(row['name']) != clean_name
                or row['origin_country_code'] != clean_origin
            )
            if not scalar_changed and not resolved.changed and not food_changed:
                return int(row['row_version'])
            replace_metadata(connection, component_id, resolved)
            new_version = int(
                connection.execute(
                    text(
                        '''
                        UPDATE cafeteria.menu_components
                        SET category=:category,
                            name=:name,
                            origin_country_code=:origin_country_code,
                            food_id=:food_id,
                            row_version=row_version + 1,
                            updated_at=clock_timestamp()
                        WHERE id=:component_id
                        RETURNING row_version
                        '''
                    ),
                    {
                        'component_id': component_id,
                        'category': clean_category,
                        'name': clean_name,
                        'origin_country_code': clean_origin,
                        'food_id': assigned_food_id,
                    },
                ).scalar_one()
            )
            if food_changed:
                connection.execute(text(
                    'SELECT cafeteria.record_component_food_write_v26('
                    ':actor,:authz,:location,:component,:before,:after)'
                ), {**actor_parameters(scope), 'component': component_id,
                    'before': expected_version, 'after': new_version})
            return new_version
    except IntegrityError as error:
        _raise_name_conflict(error)
        raise


def archive_component(
    engine: Engine,
    scope: AdminScope,
    public_id: str,
    version: int,
) -> int:
    return _set_component_active(engine, scope, public_id, version, active=False)


def unarchive_component(
    engine: Engine,
    scope: AdminScope,
    public_id: str,
    version: int,
) -> int:
    return _set_component_active(engine, scope, public_id, version, active=True)


def _set_component_active(
    engine: Engine,
    scope: AdminScope,
    public_id: str,
    version: int,
    *,
    active: bool,
) -> int:
    canonical_public_id = _public_id(public_id)
    expected_version = _positive_integer(version, 'row_version')
    with write_transaction(engine, scope) as connection:
        row = _lock_component(connection, scope, canonical_public_id, expected_version)
        if bool(row['active']) is active:
            raise ComponentConflictError('Komponente hat diesen Archivstatus bereits.')
        return int(
            connection.execute(
                text(
                    '''
                    UPDATE cafeteria.menu_components
                    SET active=:active,
                        row_version=row_version + 1,
                        updated_at=clock_timestamp()
                    WHERE id=:component_id
                    RETURNING row_version
                    '''
                ),
                {'component_id': row['id'], 'active': active},
            ).scalar_one()
        )


def _lock_component(
    connection: Connection,
    scope: AdminScope,
    public_id: str,
    expected_version: int,
) -> Mapping[str, object]:
    _require_scope_location(connection, scope)
    row = connection.execute(
        text(
            '''
            SELECT id, active, row_version, category, name, origin_country_code, food_id
            FROM cafeteria.menu_components
            WHERE public_id=CAST(:public_id AS uuid)
              AND location_id=:location_id
              AND profile_scope IN ('common', :profile_code)
            FOR UPDATE
            '''
        ),
        {
            'public_id': public_id,
            'location_id': scope.location_id,
            'profile_code': scope.profile_code,
        },
    ).mappings().one_or_none()
    if row is None:
        raise ComponentNotFoundError('Komponente nicht gefunden.')
    if int(row['row_version']) != expected_version:
        raise StaleComponentError('Komponente wurde zwischenzeitlich geändert.')
    return row


def _require_scope_location(connection: Connection, scope: AdminScope) -> None:
    if resolve_single_active_location_connection(connection) != scope.location_id:
        raise ComponentCatalogConfigurationError('Standort-Scope ist nicht aktiv.')


def _update_payload(
    payload: Mapping[str, object],
) -> tuple[str, str, str | None, NormalizedMetadata]:
    if (not isinstance(payload, Mapping)
            or frozenset(payload) not in (_UPDATE_KEYS, _UPDATE_KEYS | {'food_public_id'})):
        raise ComponentCatalogValidationError('Ungültige Bearbeitungsfelder.')
    return (
        _category(payload['category']),
        _name(payload['name']),
        _origin_country_code(payload['origin_country_code']),
        normalize_metadata(payload['label_codes'], payload['allergens']),
    )


def _food_public_id(value: object) -> str | None:
    if value is None or value == '':
        return None
    if type(value) is not str or _UUID_PATTERN.fullmatch(value) is None:
        raise ComponentCatalogValidationError(
            'Lebensmittel-ID muss eine UUID sein.', field_name='food_public_id',
        )
    return str(UUID(value))


def _lock_assignment_foods(
    connection: Connection,
    scope: AdminScope,
    current_food_id: object,
    requested_public_id: str | None,
) -> int | None:
    new_id = None
    if requested_public_id is not None:
        new_id = connection.execute(
            text(
                '''
                SELECT id FROM cafeteria.foods
                WHERE public_id=CAST(:public_id AS uuid) AND location_id=:location
                '''
            ),
            {'public_id': requested_public_id, 'location': scope.location_id},
        ).scalar_one_or_none()
        if new_id is None:
            raise ComponentCatalogValidationError(
                'Aktives Lebensmittel dieses Standorts auswählen.',
                field_name='food_public_id',
            )
    lock_ids = sorted({
        food_id for food_id in (current_food_id, new_id) if type(food_id) is int
    })
    locked = {}
    if lock_ids:
        for row in connection.execute(
            text(
                'SELECT * FROM cafeteria.lock_component_foods_v26('
                ':actor,:authz,:location,CAST(:ids AS bigint[]))'
            ),
            {**actor_parameters(scope), 'ids': lock_ids},
        ).mappings():
            locked[int(row['food_id'])] = row
    if requested_public_id is None:
        return None
    target_id = int(new_id) if new_id is not None else None
    selected = locked.get(target_id) if target_id is not None else None
    if selected is None or not selected['active']:
        raise ComponentCatalogValidationError(
            'Aktives Lebensmittel dieses Standorts auswählen.',
            field_name='food_public_id',
        )
    return int(selected['food_id'])


def _public_id(value: object) -> str:
    if type(value) is not str or _UUID_PATTERN.fullmatch(value) is None:
        raise ComponentNotFoundError('Komponente nicht gefunden.')
    return str(UUID(value))


def _raise_name_conflict(error: IntegrityError) -> None:
    original = error.orig
    diagnostic = getattr(original, 'diag', None)
    if (
        getattr(original, 'sqlstate', None) == '23505'
        and getattr(diagnostic, 'constraint_name', None) == _NAME_UNIQUE_CONSTRAINT
    ):
        raise ComponentConflictError('Dieser Komponentenname ist bereits vergeben.') from error
