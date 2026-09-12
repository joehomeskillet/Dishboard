"""Fixed, location-bound reads; resolvers reuse the caller's connection."""
from __future__ import annotations

from collections.abc import Mapping
from contextlib import contextmanager
from types import MappingProxyType
from typing import Any, Iterator

from sqlalchemy import Connection, Engine, text

from .component_catalog_store import resolve_single_active_location_connection
from .master_data_commands import decision
from .master_data_proposals import code as validate_code, identifier
from .master_data_types import (
    FoodDTO, MasterDataNotFoundError, MasterDataUnavailableError, PreparedRecipeDTO,
    MasterDataValidationError, ProposalDTO, SourceDTO, UnitDTO, VocabularyDTO, VocabularyKind,
)
from .quantities import parse_quantity


VOCABULARY = {
    'food_category': '''SELECT public_id::text, 'food_category' AS kind, code, name,
        sort_order, active, row_version, location_id FROM cafeteria.food_categories''',
    'tag': '''SELECT public_id::text, 'tag' AS kind, code, name,
        NULL::smallint AS sort_order, active, row_version, location_id FROM cafeteria.tags''',
    'storage_location': '''SELECT public_id::text, 'storage_location' AS kind, code, name,
        sort_order, active, row_version, location_id FROM cafeteria.storage_locations''',
}
UNIT = '''SELECT public_id::text,code,display_name,dimension,base_factor,active,row_version
          FROM cafeteria.measurement_units'''
FOOD = '''SELECT f.*,u.code AS unit_code,c.public_id::text AS category_public_id
          FROM cafeteria.foods f JOIN cafeteria.measurement_units u ON u.id=f.base_unit_id
          LEFT JOIN cafeteria.food_categories c ON c.id=f.category_id AND c.location_id=f.location_id'''
PROPOSAL = '''SELECT p.*,f.public_id::text AS food_public_id FROM cafeteria.food_data_proposals p
              LEFT JOIN cafeteria.foods f ON f.id=p.food_id AND f.location_id=p.location_id'''
PREPARED = '''SELECT r.public_id::text AS recipe_public_id, v.public_id::text AS revision_public_id,
    v.revision_number, v.content_hash_sha256, v.snapshot_json->'recipe'->>'title' AS title,
    v.snapshot_json->'recipe'->>'servings' AS yield_quantity,
    v.snapshot_json->'recipe'->>'servings_unit_code' AS yield_unit_code, r.active AS recipe_active
    FROM cafeteria.recipe_revisions v JOIN cafeteria.recipes r
      ON r.id=v.recipe_id AND r.location_id=v.location_id'''


@contextmanager
def connection(engine: Engine) -> Iterator[Connection]:
    if engine is None:
        raise MasterDataUnavailableError('Stammdaten sind derzeit nicht verfügbar.')
    with engine.begin() as current:
        current.execute(text('SET TRANSACTION READ ONLY'))
        yield current


def paging(limit: int, offset: int, include_archived: bool = False) -> dict[str, object]:
    if type(limit) is not int or not 1 <= limit <= 500 or type(offset) is not int or offset < 0:
        raise MasterDataValidationError('Ungültiger Seitenausschnitt.')
    if type(include_archived) is not bool:
        raise MasterDataValidationError('Ungültiger Archivfilter.')
    return {'limit': limit, 'offset': offset, 'archived': include_archived}


def vocabulary_sql(kind: VocabularyKind) -> str:
    if kind not in VOCABULARY:
        raise MasterDataValidationError('Unbekanntes Stammdatenvokabular.')
    return VOCABULARY[kind]


def vocabulary(row: Mapping[str, Any]) -> VocabularyDTO:
    return VocabularyDTO(**{key: value for key, value in row.items() if key != 'location_id'})


def resolve_unit(connection: Connection, code: str) -> UnitDTO:
    row = connection.execute(text(UNIT + ' WHERE code=:code'), {'code': validate_code(code)}).mappings().one_or_none()
    if row is None:
        raise MasterDataNotFoundError('Einheit nicht gefunden.')
    return UnitDTO(**row)


def resolve_vocabulary(connection: Connection, location_id: int, kind: VocabularyKind,
                       public_id: str, include_archived: bool = True) -> VocabularyDTO:
    row = connection.execute(text('SELECT * FROM (' + vocabulary_sql(kind) + ''') v
        WHERE public_id=:id AND location_id=:location AND (:archived OR active)'''),
        {'id': identifier(public_id), 'location': location_id, 'archived': include_archived}).mappings().one_or_none()
    if row is None:
        raise MasterDataNotFoundError('Stammdatensatz nicht gefunden.')
    return vocabulary(dict(row))


def resolve_tag(connection: Connection, location_id: int, public_id: str, *, include_archived: bool = True) -> VocabularyDTO:
    return resolve_vocabulary(connection, location_id, 'tag', public_id, include_archived)


def source(row: Mapping[str, Any]) -> SourceDTO:
    return SourceDTO(row.get('source_kind', row.get('source')), row['source_reference'],
                     row['source_url'], row['source_note'], row['fetched_at'])


def food(connection: Connection, row: Mapping[str, Any]) -> FoodDTO:
    ids = {'food': row['id'], 'location': row['location_id']}
    labels = connection.execute(text('''SELECT l.code FROM cafeteria.food_labels fl
        JOIN cafeteria.dietary_labels l ON l.id=fl.label_id JOIN cafeteria.foods f ON f.id=fl.food_id
        WHERE f.id=:food AND f.location_id=:location ORDER BY l.code'''), ids).scalars().all()
    allergens = connection.execute(text('''SELECT a.code,fa.presence FROM cafeteria.food_allergens fa
        JOIN cafeteria.allergens a ON a.id=fa.allergen_id JOIN cafeteria.foods f ON f.id=fa.food_id
        WHERE f.id=:food AND f.location_id=:location ORDER BY a.code'''), ids).all()
    tags = connection.execute(text('''SELECT t.public_id::text FROM cafeteria.food_tags ft
        JOIN cafeteria.tags t ON t.id=ft.tag_id AND t.location_id=ft.location_id
        WHERE ft.food_id=:food AND ft.location_id=:location ORDER BY lower(btrim(t.name)),t.public_id'''), ids).scalars().all()
    storage = connection.execute(text('''SELECT s.public_id::text FROM cafeteria.food_storage_locations fs
        JOIN cafeteria.storage_locations s ON s.id=fs.storage_location_id AND s.location_id=fs.location_id
        WHERE fs.food_id=:food AND fs.location_id=:location ORDER BY s.sort_order,lower(btrim(s.name)),s.public_id'''), ids).scalars().all()
    return FoodDTO(str(row['public_id']), row['name'],
        resolve_vocabulary(connection, row['location_id'], 'food_category', row['category_public_id'])
        if row['category_public_id'] else None, resolve_unit(connection, row['unit_code']),
        row['density_g_per_ml'], row['piece_weight_g'], row['note'], row['allergen_review_status'],
        source(row), row['active'], row['row_version'], tuple((r[0], r[1]) for r in allergens), tuple(labels),
        tuple(resolve_tag(connection, row['location_id'], key) for key in tags),
        tuple(resolve_vocabulary(connection, row['location_id'], 'storage_location', key) for key in storage),
        prepared_food_revision(connection, row['location_id'], row['prepared_recipe_revision_id'])
        if row['prepared_recipe_revision_id'] is not None else None)


def prepared_revision(row: Mapping[str, Any]) -> PreparedRecipeDTO:
    return PreparedRecipeDTO(row['recipe_public_id'], row['revision_public_id'], row['revision_number'],
        row['content_hash_sha256'], row['title'], parse_quantity(row['yield_quantity']), row['yield_unit_code'], row['recipe_active'])


def prepared_food_revision(connection: Connection, location_id: int, revision_id: int) -> PreparedRecipeDTO:
    row = connection.execute(text(PREPARED + ' WHERE v.location_id=:location AND v.id=:revision'),
        {'location': location_id, 'revision': revision_id}).mappings().one_or_none()
    if row is None:
        raise MasterDataNotFoundError('Der zugeordnete Rezeptstand ist nicht verfügbar.')
    return prepared_revision(dict(row))


def list_prepared_revisions(engine: Engine, *, search: str | None = None,
                            limit: int = 26, offset: int = 0) -> tuple[PreparedRecipeDTO, ...]:
    values = paging(limit, offset)
    if search is not None and (not isinstance(search, str) or len(search) > 200 or '\x00' in search):
        raise MasterDataValidationError('Ungültige Rezeptsuche.')
    values['search'] = (search or '').replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_')
    with connection(engine) as current:
        values['location'] = resolve_single_active_location_connection(current)
        rows = current.execute(text(PREPARED + ''' WHERE v.location_id=:location AND r.active
            AND (v.snapshot_json->'recipe'->>'title') ILIKE '%'||:search||'%' ESCAPE E'\\\\'
            ORDER BY lower(btrim(v.snapshot_json->'recipe'->>'title')),r.public_id,v.revision_number DESC,v.public_id
            LIMIT :limit OFFSET :offset'''), values).mappings()
        return tuple(prepared_revision(dict(row)) for row in rows)


def resolve_food(connection: Connection, location_id: int, public_id: str, *, include_archived: bool = True) -> FoodDTO:
    row = connection.execute(text(FOOD + ''' WHERE f.public_id=CAST(:id AS uuid)
        AND f.location_id=:location AND (:archived OR f.active)'''),
        {'id': identifier(public_id), 'location': location_id, 'archived': include_archived}).mappings().one_or_none()
    if row is None:
        raise MasterDataNotFoundError('Zutat nicht gefunden.')
    return food(connection, dict(row))


def list_units(engine: Engine, *, include_archived: bool = False, limit: int = 200, offset: int = 0) -> tuple[UnitDTO, ...]:
    values = paging(limit, offset, include_archived)
    with connection(engine) as current:
        return tuple(UnitDTO(**row) for row in current.execute(text(UNIT + '''
            WHERE (:archived OR active) ORDER BY code,public_id LIMIT :limit OFFSET :offset'''), values).mappings())


def get_unit(engine: Engine, public_id: str) -> UnitDTO:
    with connection(engine) as current:
        row = current.execute(text(UNIT + ' WHERE public_id=CAST(:id AS uuid)'),
                              {'id': identifier(public_id)}).mappings().one_or_none()
        if row is None:
            raise MasterDataNotFoundError('Einheit nicht gefunden.')
        return UnitDTO(**row)


def list_vocabulary(engine: Engine, kind: VocabularyKind, *, include_archived: bool = False,
                    limit: int = 200, offset: int = 0) -> tuple[VocabularyDTO, ...]:
    values = paging(limit, offset, include_archived)
    sql = 'SELECT * FROM (' + vocabulary_sql(kind) + ''') v WHERE location_id=:location AND (:archived OR active)
        ORDER BY sort_order NULLS LAST,lower(btrim(name)),public_id LIMIT :limit OFFSET :offset'''
    with connection(engine) as current:
        values['location'] = resolve_single_active_location_connection(current)
        return tuple(vocabulary(dict(row)) for row in current.execute(text(sql), values).mappings())


def get_vocabulary(engine: Engine, kind: VocabularyKind, public_id: str) -> VocabularyDTO:
    with connection(engine) as current:
        return resolve_vocabulary(current, resolve_single_active_location_connection(current), kind, public_id)


def list_foods(engine: Engine, *, include_archived: bool = False, category: str | None = None,
               tag: str | None = None, search: str | None = None, limit: int = 200, offset: int = 0) -> tuple[FoodDTO, ...]:
    values = paging(limit, offset, include_archived)
    if search is not None and (not isinstance(search, str) or len(search) > 200 or '\x00' in search):
        raise MasterDataValidationError('Ungültige Suche.')
    values.update(category=identifier(category) if category else None, tag=identifier(tag) if tag else None,
                  search=(search or '').replace('\\', '\\\\').replace('%', '\\%').replace('_', '\\_'))
    with connection(engine) as current:
        values['location'] = resolve_single_active_location_connection(current)
        rows = current.execute(text(FOOD + ''' WHERE f.location_id=:location AND (:archived OR f.active)
            AND (CAST(:category AS uuid) IS NULL OR c.public_id=CAST(:category AS uuid))
            AND (CAST(:tag AS uuid) IS NULL OR EXISTS(SELECT 1 FROM cafeteria.food_tags ft
                JOIN cafeteria.tags t ON t.id=ft.tag_id AND t.location_id=ft.location_id
                WHERE ft.food_id=f.id AND ft.location_id=f.location_id AND t.public_id=CAST(:tag AS uuid)))
            AND f.name ILIKE '%'||:search||'%' ESCAPE E'\\\\'
            ORDER BY lower(btrim(f.name)),f.public_id LIMIT :limit OFFSET :offset'''), values).mappings().all()
        return tuple(food(current, dict(row)) for row in rows)


def get_food(engine: Engine, public_id: str) -> FoodDTO:
    with connection(engine) as current:
        return resolve_food(current, resolve_single_active_location_connection(current), public_id)


def frozen_json(value: Any) -> Any:
    if isinstance(value, dict):
        return MappingProxyType({key: frozen_json(item) for key, item in value.items()})
    if isinstance(value, list):
        return tuple(frozen_json(item) for item in value)
    return value


def proposal(row: Mapping[str, Any]) -> ProposalDTO:
    detail = row['decision_detail']
    return ProposalDTO(str(row['public_id']), row['row_version'], row['status'], source(row),
                       row['food_public_id'], frozen_json(row['payload']), decision(detail) if detail else None)


def list_proposals(engine: Engine, *, status: str | None = None, food: str | None = None,
                   limit: int = 200, offset: int = 0) -> tuple[ProposalDTO, ...]:
    values = paging(limit, offset)
    if status not in (None, 'open', 'accepted', 'rejected'):
        raise MasterDataValidationError('Ungültiger Vorschlagsstatus.')
    values.update(status=status, food=identifier(food) if food else None)
    with connection(engine) as current:
        values['location'] = resolve_single_active_location_connection(current)
        rows = current.execute(text(PROPOSAL + ''' WHERE p.location_id=:location
            AND (CAST(:status AS text) IS NULL OR p.status=:status)
            AND (CAST(:food AS uuid) IS NULL OR f.public_id=CAST(:food AS uuid))
            ORDER BY p.created_at,p.public_id LIMIT :limit OFFSET :offset'''), values).mappings()
        return tuple(proposal(dict(row)) for row in rows)


def get_proposal(engine: Engine, public_id: str) -> ProposalDTO:
    with connection(engine) as current:
        row = current.execute(text(PROPOSAL + ' WHERE p.location_id=:location AND p.public_id=CAST(:id AS uuid)'),
            {'location': resolve_single_active_location_connection(current), 'id': identifier(public_id)}).mappings().one_or_none()
        if row is None:
            raise MasterDataNotFoundError('Vorschlag nicht gefunden.')
        return proposal(dict(row))
