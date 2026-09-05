from __future__ import annotations

# ruff: noqa: F401, F811

from collections.abc import Callable
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta
from threading import Event

import pytest
from sqlalchemy import Engine, create_engine, event, text
from sqlalchemy.exc import DBAPIError
from sqlalchemy.pool import NullPool

from cafeteria import workflow
from cafeteria.component_catalog_store import (
    AdminScope,
    ComponentConflictError,
    ComponentNotFoundError,
    archive_component,
    create_component,
    update_component,
)
from cafeteria.db import withdraw_publication_revision
from cafeteria.workflow_copy_store import copy_previous_week
import test_admin_workflow_db as workflow_support
from test_component_catalog_db import CatalogDatabase, catalog_database


TARGET_WEEK = date(2026, 9, 14)


@dataclass(frozen=True)
class SeededWeek:
    week_id: int
    week_public_id: str
    service_ids: tuple[int, ...]
    service_public_ids: tuple[str, ...]
    item_id: int
    item_public_id: str
    component: dict[str, object] | None


def _scope(database: CatalogDatabase, profile: str = 'patient') -> AdminScope:
    return AdminScope(1, database.location_id, profile)  # seeded system actor


def _seed_source(database: CatalogDatabase, *, profile: str = 'patient',
                 catalog_component: bool = True) -> SeededWeek:
    scope = _scope(database, profile)
    component = None
    if catalog_component:
        component = create_component(
            database.app,
            scope,
            'side',
            'Alte Kartoffel',
            'CH',
            'current',
            ('VEGAN',),
            (('GLUTEN', 'contains'),),
        )
    source_week = TARGET_WEEK - timedelta(days=7)
    with database.owner.begin() as connection:
        profile_id = int(connection.execute(text(
            'SELECT id FROM cafeteria.offer_profiles WHERE code=:code'
        ), {'code': profile}).scalar_one())
        week = connection.execute(text(
            '''INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start,
                   workflow_state, title, shared_note, created_by, updated_by)
               VALUES (:location_id, :profile_id, :week_start, 'draft', :title, :note, 2, 2)
               RETURNING id, public_id::text AS public_id'''
        ), {
            'location_id': database.location_id,
            'profile_id': profile_id,
            'week_start': source_week,
            'title': '  Vorwoche  ',
            'note': 'Notiz\nbytegenau ',
        }).mappings().one()
        meal_codes = ('LUNCH', 'DINNER') if profile == 'patient' else ('LUNCH',)
        services = []
        for offset, meal_code in enumerate(meal_codes):
            service = connection.execute(text(
                '''INSERT INTO cafeteria.menu_services(menu_week_id, service_date,
                       meal_period_id, service_state, notice)
                   SELECT :week_id, :service_date, id, :state, :notice
                   FROM cafeteria.meal_periods WHERE code=:meal
                   RETURNING id, public_id::text AS public_id'''
            ), {
                'week_id': week['id'],
                'service_date': source_week + timedelta(days=offset),
                'state': 'open' if offset == 0 else 'closed',
                'notice': None if offset == 0 else '  Küche zu  ',
                'meal': meal_code,
            }).mappings().one()
            services.append(service)
        template_id = int(connection.execute(text(
            '''INSERT INTO cafeteria.dish_templates(menu_type_id, title, description)
               SELECT id, 'Vorlage', 'Beschreibung' FROM cafeteria.menu_types
               WHERE code='MENU_1' RETURNING id'''
        )).scalar_one())
        item = connection.execute(text(
            '''INSERT INTO cafeteria.menu_items(service_id, menu_type_id, dish_template_id,
                   external_id, title, description, note, allergen_review_status, sort_order,
                   allergen_mode, origin_mode, label_mode)
               SELECT :service_id, id, :template_id, :external_id, :title, :description,
                      :note, 'checked', 7, 'auto', 'manual', 'manual'
               FROM cafeteria.menu_types WHERE code='MENU_1'
               RETURNING id, public_id::text AS public_id'''
        ), {
            'service_id': services[0]['id'],
            'template_id': template_id,
            'external_id': f'SOURCE-{profile}',
            'title': '  Menü Quelle  ',
            'description': 'Beschreibung\n bytegenau ',
            'note': ' Hinweis ',
        }).mappings().one()
        if component is not None:
            component_row = connection.execute(text(
                '''SELECT id, row_version FROM cafeteria.menu_components
                   WHERE public_id=CAST(:public_id AS uuid)'''
            ), {'public_id': component['public_id']}).mappings().one()
            connection.execute(text(
                '''INSERT INTO cafeteria.menu_item_components(menu_item_id, sort_order,
                       component_text, component_id, component_row_version)
                   VALUES (:item_id, 1, 'alter Linkname', :component_id, :component_version)'''
            ), {
                'item_id': item['id'],
                'component_id': component_row['id'],
                'component_version': component_row['row_version'],
            })
        connection.execute(text(
            '''INSERT INTO cafeteria.menu_item_components(menu_item_id, sort_order, component_text)
               VALUES (:item_id, 2, :component_text)'''
        ), {'item_id': item['id'], 'component_text': '  Freitext\nKomponente  '})
        connection.execute(text(
            '''INSERT INTO cafeteria.menu_item_labels(menu_item_id, label_id)
               SELECT :item_id, id FROM cafeteria.dietary_labels WHERE code='GLUTEN_FREE' '''
        ), {'item_id': item['id']})
        connection.execute(text(
            '''INSERT INTO cafeteria.menu_item_allergens(menu_item_id, allergen_id, presence)
               SELECT :item_id, id, 'may_contain' FROM cafeteria.allergens WHERE code='FISH' '''
        ), {'item_id': item['id']})
        connection.execute(text(
            '''INSERT INTO cafeteria.origin_declarations(
                   menu_item_id, ingredient, country_code, declaration_text)
               VALUES (:item_id, '  Rind  ', 'CH', '  Rind: CH  ')'''
        ), {'item_id': item['id']})
        if profile == 'staff_guest':
            connection.execute(text(
                '''INSERT INTO cafeteria.menu_item_prices(
                       menu_item_id, internal_rappen, external_rappen, currency)
                   VALUES (:item_id, 950, 1450, 'CHF')'''
            ), {'item_id': item['id']})
    if component is not None:
        current_version = int(component['row_version'])
        new_version = update_component(
            database.app,
            scope,
            str(component['public_id']),
            {
                'category': 'side',
                'name': 'Neue Kartoffel',
                'origin_country_code': 'CH',
                'label_codes': ['VEGAN'],
                'allergens': [('GLUTEN', 'contains')],
            },
            current_version,
        )
        component = {**component, 'name': 'Neue Kartoffel', 'row_version': new_version}
    return SeededWeek(
        int(week['id']),
        str(week['public_id']),
        tuple(int(row['id']) for row in services),
        tuple(str(row['public_id']) for row in services),
        int(item['id']),
        str(item['public_id']),
        component,
    )


def _seed_empty_target(database: CatalogDatabase, profile: str = 'patient') -> tuple[int, str, int]:
    with database.owner.begin() as connection:
        row = connection.execute(text(
            '''WITH profile AS (SELECT id FROM cafeteria.offer_profiles WHERE code=:profile),
               week_row AS (
                 INSERT INTO cafeteria.menu_weeks(location_id, profile_id, week_start,
                   workflow_state, title, created_by, updated_by)
                 SELECT :location_id, profile.id, :week_start, 'ready', 'Alt', 2, 2 FROM profile
                 RETURNING id, public_id, row_version),
               service_row AS (
                 INSERT INTO cafeteria.menu_services(menu_week_id, service_date, meal_period_id,
                   service_state, notice)
                 SELECT week_row.id, :week_start, meal.id, 'closed', 'Alt geschlossen'
                 FROM week_row CROSS JOIN cafeteria.meal_periods meal WHERE meal.code='LUNCH'
                 RETURNING id)
               SELECT week_row.id, week_row.public_id::text AS public_id,
                 week_row.row_version, service_row.id AS service_id
               FROM week_row CROSS JOIN service_row'''
        ), {
            'profile': profile,
            'location_id': database.location_id,
            'week_start': TARGET_WEEK,
        }).mappings().one()
    return int(row['id']), str(row['public_id']), int(row['service_id'])


def _target_counts(database: CatalogDatabase, profile: str = 'patient') -> tuple[int, int, int]:
    with database.owner.connect() as connection:
        row = connection.execute(text(
            '''SELECT count(DISTINCT s.id), count(DISTINCT i.id),
                 count(DISTINCT mic.menu_item_id::text || ':' || mic.sort_order::text)
               FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
               LEFT JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
               LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
               LEFT JOIN cafeteria.menu_item_components mic ON mic.menu_item_id=i.id
               WHERE w.location_id=:location_id AND p.code=:profile AND w.week_start=:week_start'''
        ), {
            'location_id': database.location_id,
            'profile': profile,
            'week_start': TARGET_WEEK,
        }).one()
    return tuple(int(value) for value in row)


def _separate_engine(database: CatalogDatabase) -> Engine:
    return create_engine(database.app.url, poolclass=NullPool, pool_pre_ping=True)


def _patient_values(week_start: date, title: str) -> dict[str, object]:
    values = workflow_support._patient_values(title)
    for offset, day_value in enumerate(values['days']):
        day_value['date'] = (week_start + timedelta(days=offset)).isoformat()
    return values


def _blocked_pair(
    database: CatalogDatabase, first_engine: Engine, second_engine: Engine,
    first_marker: str, second_marker: str, first: Callable[[], object],
    second: Callable[[], object]) -> tuple[tuple[str, object], tuple[str, object]]:
    first_locked, release, second_attempted = Event(), Event(), Event()
    pids: dict[str, int] = {}

    def after_first(_conn, cursor, statement, _params, _ctx, _many):
        if first_marker in statement:
            pids['first'] = int(cursor.connection.info.backend_pid)
            first_locked.set()
            assert release.wait(10)

    def before_second(_conn, cursor, statement, _params, _ctx, _many):
        if second_marker in statement:
            pids['second'] = int(cursor.connection.info.backend_pid)
            second_attempted.set()

    def result(call: Callable[[], object]) -> tuple[str, object]:
        try:
            return 'ok', call()
        except Exception as error:  # asserted by exact class at each call site
            return 'error', error

    event.listen(first_engine, 'after_cursor_execute', after_first)
    event.listen(second_engine, 'before_cursor_execute', before_second)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            first_future = pool.submit(result, first)
            assert first_locked.wait(10)
            second_future = pool.submit(result, second)
            assert second_attempted.wait(10)
            try:
                with database.owner.connect() as connection:
                    for _ in range(1_000):
                        blockers = connection.execute(text(
                            'SELECT pg_blocking_pids(:pid)'
                        ), {'pid': pids['second']}).scalar_one()
                        if blockers:
                            break
                assert blockers == [pids['first']]
                assert not second_future.done()
            finally:
                release.set()
            return (first_future.result(timeout=15), second_future.result(timeout=15))
    finally:
        event.remove(first_engine, 'after_cursor_execute', after_first)
        event.remove(second_engine, 'before_cursor_execute', before_second)


def test_copy_rebases_catalog_links_and_preserves_manual_bytes(
    catalog_database: CatalogDatabase,
) -> None:
    source = _seed_source(catalog_database)
    assert source.component is not None

    assert copy_previous_week(
        catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0,
    ) == 1

    with catalog_database.owner.connect() as connection:
        week = connection.execute(text(
            '''SELECT w.id, w.public_id::text, w.workflow_state, w.title, w.shared_note,
                 w.row_version, w.created_by, w.updated_by
               FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
               WHERE w.location_id=:location_id AND p.code='patient' AND w.week_start=:week_start'''
        ), {'location_id': catalog_database.location_id, 'week_start': TARGET_WEEK}).one()
        services = connection.execute(text(
            '''SELECT s.id, s.public_id::text, s.service_date, mp.code, s.service_state,
                 s.notice, s.row_version FROM cafeteria.menu_services s
               JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
               WHERE s.menu_week_id=:week_id ORDER BY s.service_date, mp.sort_order'''
        ), {'week_id': week[0]}).all()
        item = connection.execute(text(
            '''SELECT i.id, i.public_id::text, i.external_id, i.title, i.description, i.note,
                 i.allergen_review_status, i.sort_order, i.row_version, i.allergen_mode,
                 i.origin_mode, i.label_mode, i.dish_template_id
               FROM cafeteria.menu_items i JOIN cafeteria.menu_services s ON s.id=i.service_id
               WHERE s.menu_week_id=:week_id'''
        ), {'week_id': week[0]}).one()
        links = connection.execute(text(
            '''SELECT mic.sort_order, mic.component_text, c.public_id::text,
                 mic.component_row_version, c.row_version
               FROM cafeteria.menu_item_components mic
               LEFT JOIN cafeteria.menu_components c ON c.id=mic.component_id
               WHERE mic.menu_item_id=:item_id ORDER BY mic.sort_order'''
        ), {'item_id': item[0]}).all()
        labels = connection.execute(text(
            '''SELECT l.code FROM cafeteria.menu_item_labels x
               JOIN cafeteria.dietary_labels l ON l.id=x.label_id WHERE x.menu_item_id=:item_id
               ORDER BY l.code'''
        ), {'item_id': item[0]}).scalars().all()
        allergens = connection.execute(text(
            '''SELECT a.code, x.presence FROM cafeteria.menu_item_allergens x
               JOIN cafeteria.allergens a ON a.id=x.allergen_id WHERE x.menu_item_id=:item_id
               ORDER BY a.code'''
        ), {'item_id': item[0]}).all()
        origins = connection.execute(text(
            '''SELECT ingredient, country_code, declaration_text
               FROM cafeteria.origin_declarations WHERE menu_item_id=:item_id'''
        ), {'item_id': item[0]}).all()
        publications = connection.execute(text(
            'SELECT count(*) FROM cafeteria.publication_revisions WHERE menu_week_id=:week_id'
        ), {'week_id': week[0]}).scalar_one()

    assert week[1] != source.week_public_id
    assert tuple(week[2:]) == ('draft', '  Vorwoche  ', 'Notiz\nbytegenau ', 1, 1, 1)
    assert [(row[2], row[3], row[4], row[5], row[6]) for row in services] == [
        (TARGET_WEEK, 'LUNCH', 'open', None, 1),
        (TARGET_WEEK + timedelta(days=1), 'DINNER', 'closed', '  Küche zu  ', 1),
    ]
    assert not set(source.service_ids) & {int(row[0]) for row in services}
    assert not set(source.service_public_ids) & {str(row[1]) for row in services}
    assert item[0] != source.item_id and item[1] != source.item_public_id
    assert tuple(item[2:12]) == (
        'PATIENT-2026-09-14-LUNCH-1', '  Menü Quelle  ', 'Beschreibung\n bytegenau ',
        ' Hinweis ', 'not_checked', 7, 1, 'auto', 'manual', 'manual',
    )
    assert item[12] is not None
    assert links == [
        (1, 'Neue Kartoffel', source.component['public_id'], source.component['row_version'],
         source.component['row_version']),
        (2, '  Freitext\nKomponente  ', None, None, None),
    ]
    assert labels == ['GLUTEN_FREE']
    assert allergens == [('GLUTEN', 'contains')]
    assert origins == [('  Rind  ', 'CH', '  Rind: CH  ')]
    assert publications == 0


@pytest.mark.parametrize('source_state', ['ready', 'published', 'archived'])
def test_copy_uses_saved_source_independent_of_lifecycle(catalog_database: CatalogDatabase, source_state: str) -> None:
    source = _seed_source(catalog_database, catalog_component=False)
    with catalog_database.owner.begin() as connection:
        connection.execute(
            text('UPDATE cafeteria.menu_weeks SET workflow_state=:state WHERE id=:id'),
            {'state': source_state, 'id': source.week_id},
        )

    assert copy_previous_week(
        catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0,
    ) == 1
    assert _target_counts(catalog_database) == (2, 1, 1)


def test_copy_target_version_matrix_replaces_only_empty_skeleton(catalog_database: CatalogDatabase) -> None:
    _seed_source(catalog_database, catalog_component=False)
    with pytest.raises(ComponentNotFoundError):
        copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 1)
    target_id, target_public_id, old_service_id = _seed_empty_target(catalog_database)
    with pytest.raises(ComponentConflictError):
        copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0)
    with pytest.raises(ComponentConflictError):
        copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 2)

    assert copy_previous_week(
        catalog_database.app, _scope(catalog_database), TARGET_WEEK, 1,
    ) == 2

    with catalog_database.owner.connect() as connection:
        week = connection.execute(text(
            'SELECT id, public_id::text, row_version, workflow_state, created_by, updated_by '
            'FROM cafeteria.menu_weeks WHERE id=:id'
        ), {'id': target_id}).one()
        service_ids = connection.execute(text(
            'SELECT id FROM cafeteria.menu_services WHERE menu_week_id=:id ORDER BY id'
        ), {'id': target_id}).scalars().all()
    assert week == (target_id, target_public_id, 2, 'draft', 2, 1)
    assert old_service_id not in service_ids
    before = _target_counts(catalog_database)
    with pytest.raises(ComponentConflictError):
        copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 2)
    assert _target_counts(catalog_database) == before


def test_copy_staff_prices_and_rejects_archived_or_anomalous_patient_data(catalog_database: CatalogDatabase) -> None:
    _seed_source(catalog_database, profile='staff_guest', catalog_component=False)
    assert copy_previous_week(
        catalog_database.app, _scope(catalog_database, 'staff_guest'), TARGET_WEEK, 0,
    ) == 1
    with catalog_database.owner.connect() as connection:
        price = connection.execute(text(
            '''SELECT p.internal_rappen, p.external_rappen, p.currency
               FROM cafeteria.menu_item_prices p
               JOIN cafeteria.menu_items i ON i.id=p.menu_item_id
               JOIN cafeteria.menu_services s ON s.id=i.service_id
               JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
               JOIN cafeteria.offer_profiles f ON f.id=w.profile_id
               WHERE f.code='staff_guest' AND w.week_start=:week_start'''
        ), {'week_start': TARGET_WEEK}).one()
    assert price == (950, 1450, 'CHF')

    patient = _seed_source(catalog_database, catalog_component=False)
    with catalog_database.owner.begin() as connection:
        connection.execute(text('ALTER TABLE cafeteria.menu_item_prices DISABLE TRIGGER '
                                'trg_menu_item_prices_validate'))
        connection.execute(text(
            '''INSERT INTO cafeteria.menu_item_prices(menu_item_id, internal_rappen,
                   external_rappen, currency)
               VALUES (:item_id, 1, 2, 'CHF')'''
        ), {'item_id': patient.item_id})
        connection.execute(text('ALTER TABLE cafeteria.menu_item_prices ENABLE TRIGGER '
                                'trg_menu_item_prices_validate'))
    with pytest.raises(ComponentConflictError):
        copy_previous_week(
            catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0,
        )
    assert _target_counts(catalog_database) == (0, 0, 0)


def test_copy_archived_component_rolls_back_without_target(catalog_database: CatalogDatabase) -> None:
    source = _seed_source(catalog_database)
    assert source.component is not None
    archive_component(
        catalog_database.app,
        _scope(catalog_database),
        str(source.component['public_id']),
        int(source.component['row_version']),
    )
    with pytest.raises(ComponentConflictError):
        copy_previous_week(
            catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0,
        )
    assert _target_counts(catalog_database) == (0, 0, 0)


def test_two_concurrent_copies_have_one_complete_winner(catalog_database: CatalogDatabase) -> None:
    _seed_source(catalog_database, catalog_component=False)
    first_engine, second_engine = _separate_engine(catalog_database), _separate_engine(catalog_database)
    first, second = _blocked_pair(
        catalog_database, first_engine, second_engine,
        '/* copy_week_lock */', '/* copy_week_lock */',
        lambda: copy_previous_week(
            first_engine, _scope(catalog_database), TARGET_WEEK, 0,
        ),
        lambda: copy_previous_week(
            second_engine, _scope(catalog_database), TARGET_WEEK, 0,
        ),
    )
    assert first == ('ok', 1)
    assert second[0] == 'error' and isinstance(second[1], ComponentConflictError)
    assert _target_counts(catalog_database) == (2, 1, 1)


@pytest.mark.parametrize(('saved_week', 'first_name'), [
    ('source', 'copy'), ('source', 'save'), ('target', 'copy'), ('target', 'save'),
])
def test_copy_and_real_save_block_without_hybrid(catalog_database: CatalogDatabase, saved_week: str, first_name: str) -> None:
    _seed_source(catalog_database, catalog_component=False)
    source_week = TARGET_WEEK - timedelta(days=7)
    if saved_week == 'target':
        _seed_empty_target(catalog_database)
    copy_engine, save_engine = _separate_engine(catalog_database), _separate_engine(catalog_database)
    save_week = source_week if saved_week == 'source' else TARGET_WEEK
    target_version = 0 if saved_week == 'source' else 1
    calls = {
        'copy': (copy_engine, '/* copy_week_lock */', lambda: copy_previous_week(
            copy_engine, _scope(catalog_database), TARGET_WEEK, target_version)),
        'save': (save_engine, 'FOR UPDATE OF w', lambda: workflow.save_draft(
            save_engine, 'patient', save_week, expected_row_version=1, actor_id=2,
            values=_patient_values(save_week, f'{saved_week} Save'))),
    }
    second_name = 'save' if first_name == 'copy' else 'copy'
    first, second = _blocked_pair(
        catalog_database, calls[first_name][0], calls[second_name][0],
        calls[first_name][1], calls[second_name][1], calls[first_name][2], calls[second_name][2],
    )
    if saved_week == 'source':
        assert first[0] == second[0] == 'ok'
    else:
        assert first == ('ok', 2)
        expected_error = workflow.StaleDraftError if first_name == 'copy' else ComponentConflictError
        assert second[0] == 'error' and isinstance(second[1], expected_error)
    expected_counts = (
        (2, 1, 1) if first_name == 'copy' else (14, 28, 28)
    )
    assert _target_counts(catalog_database) == expected_counts


@pytest.mark.parametrize('first_name', ['copy', 'publish'])
def test_copy_and_target_publish_block_on_week_without_hybrid(catalog_database: CatalogDatabase, first_name: str) -> None:
    _seed_source(catalog_database, catalog_component=False)
    if first_name == 'copy':
        _seed_empty_target(catalog_database)
        expected = 1
    else:
        workflow.ensure_week(catalog_database.app, 'patient', TARGET_WEEK, 2)
        expected = workflow.save_draft(
            catalog_database.app, 'patient', TARGET_WEEK, expected_row_version=1, actor_id=2,
            values=_patient_values(TARGET_WEEK, 'Publizierbares Ziel'),
        )
    copy_engine, publish_engine = _separate_engine(catalog_database), _separate_engine(catalog_database)
    calls = {
        'copy': (copy_engine, '/* copy_week_lock */', lambda: copy_previous_week(
            copy_engine, _scope(catalog_database), TARGET_WEEK, expected)),
        'publish': (publish_engine, 'FOR UPDATE OF w', lambda: workflow.publish_draft(
            publish_engine, 'patient', TARGET_WEEK, expected_row_version=expected,
            actor_id=2, issuer_engine=None)),
    }
    second_name = 'publish' if first_name == 'copy' else 'copy'
    first, second = _blocked_pair(
        catalog_database, calls[first_name][0], calls[second_name][0],
        calls[first_name][1], calls[second_name][1], calls[first_name][2], calls[second_name][2],
    )
    assert first[0] == 'ok'
    expected_error = workflow.StaleDraftError if first_name == 'copy' else ComponentConflictError
    assert second[0] == 'error' and isinstance(second[1], expected_error)
    assert _target_counts(catalog_database) == (
        (2, 1, 1) if first_name == 'copy' else (14, 28, 28)
    )


def test_active_and_inflight_withdrawal_are_conservative_and_atomic(catalog_database: CatalogDatabase) -> None:
    _seed_source(catalog_database, catalog_component=False)
    workflow.ensure_week(catalog_database.app, 'patient', TARGET_WEEK, 2)
    version = workflow.save_draft(
        catalog_database.app, 'patient', TARGET_WEEK, expected_row_version=1, actor_id=2,
        values=_patient_values(TARGET_WEEK, 'Publiziertes Ziel'),
    )
    workflow.publish_draft(
        catalog_database.app, 'patient', TARGET_WEEK,
        expected_row_version=version, actor_id=2, issuer_engine=None,
    )
    with catalog_database.owner.begin() as connection:
        row = connection.execute(text(
            '''SELECT w.id, w.row_version, r.id AS revision_id
               FROM cafeteria.menu_weeks w JOIN cafeteria.publication_revisions r
                 ON r.menu_week_id=w.id AND r.withdrawn_at IS NULL
               WHERE w.week_start=:week_start'''
        ), {'week_start': TARGET_WEEK}).mappings().one()
        connection.execute(text(
            'DELETE FROM cafeteria.menu_services WHERE menu_week_id=:week_id'
        ), {'week_id': row['id']})
        capability = str(connection.execute(text(
            'SELECT cafeteria.issue_publication_capability(:actor_id, :revision_id)'
        ), {'actor_id': 2, 'revision_id': row['revision_id']}).scalar_one())
    with pytest.raises(ComponentConflictError):
        copy_previous_week(
            catalog_database.app, _scope(catalog_database), TARGET_WEEK,
            int(row['row_version']),
        )

    withdraw_engine = _separate_engine(catalog_database)
    withdrawn_uncommitted, release = Event(), Event()

    def after_withdraw(_conn, _cursor, statement, _params, _ctx, _many):
        if 'withdraw_publication_revision' in statement:
            withdrawn_uncommitted.set()
            assert release.wait(10)

    event.listen(withdraw_engine, 'after_cursor_execute', after_withdraw)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            withdraw = pool.submit(
                withdraw_publication_revision, withdraw_engine, int(row['revision_id']),
                capability, 'Race-Test',
            )
            assert withdrawn_uncommitted.wait(10)
            copy = pool.submit(
                copy_previous_week, catalog_database.app, _scope(catalog_database),
                TARGET_WEEK, int(row['row_version']),
            )
            with pytest.raises(ComponentConflictError):
                copy.result(timeout=10)
            assert not withdraw.done()
            release.set()
            withdraw.result(timeout=10)
    finally:
        release.set()
        event.remove(withdraw_engine, 'after_cursor_execute', after_withdraw)
    assert _target_counts(catalog_database) == (0, 0, 0)
    assert copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK,
                              int(row['row_version'])) == int(row['row_version']) + 1
    with catalog_database.owner.connect() as connection:
        assert connection.execute(text('SELECT withdrawn_at IS NOT NULL FROM '
                                       'cafeteria.publication_revisions WHERE id=:id'),
                                  {'id': row['revision_id']}).scalar_one() is True
    assert _target_counts(catalog_database) == (2, 1, 1)


def _prepare_replacement(
    catalog_database: CatalogDatabase,
) -> tuple[int, int, str]:
    workflow.ensure_week(catalog_database.app, 'patient', TARGET_WEEK, 2)
    first_version = workflow.save_draft(
        catalog_database.app,
        'patient',
        TARGET_WEEK,
        expected_row_version=1,
        actor_id=2,
        values=_patient_values(TARGET_WEEK, 'Erste Revision'),
    )
    workflow.publish_draft(
        catalog_database.app,
        'patient',
        TARGET_WEEK,
        expected_row_version=first_version,
        actor_id=2,
        issuer_engine=None,
    )
    current_version = workflow.draft_row_version(catalog_database.app, 'patient', TARGET_WEEK)
    second_version = workflow.save_draft(
        catalog_database.app,
        'patient',
        TARGET_WEEK,
        expected_row_version=current_version,
        actor_id=2,
        values=_patient_values(TARGET_WEEK, 'Zweite Revision'),
    )
    with catalog_database.owner.begin() as connection:
        revision_id = int(connection.execute(text(
            'SELECT id FROM cafeteria.publication_revisions WHERE withdrawn_at IS NULL'
        )).scalar_one())
        direct_capability = str(connection.execute(text(
            'SELECT cafeteria.issue_publication_capability(:actor_id, :revision_id)'
        ), {'actor_id': 2, 'revision_id': revision_id}).scalar_one())
    return second_version, revision_id, direct_capability


def test_publish_location_lock_serializes_real_cutover(
    catalog_database: CatalogDatabase,
) -> None:
    workflow.ensure_week(catalog_database.app, 'patient', TARGET_WEEK, 2)
    version = workflow.save_draft(
        catalog_database.app,
        'patient',
        TARGET_WEEK,
        expected_row_version=1,
        actor_id=2,
        values=_patient_values(TARGET_WEEK, 'Standort-Lock'),
    )
    publish_engine = _separate_engine(catalog_database)
    cutover_engine = create_engine(
        catalog_database.owner.url,
        poolclass=NullPool,
        pool_pre_ping=True,
    )
    location_locked, release, cutover_attempted = Event(), Event(), Event()

    def after_location_lock(_conn, _cursor, statement, _params, _ctx, _many):
        if 'lock_expected_active_location' in statement:
            location_locked.set()
            assert release.wait(10)

    def before_cutover(_conn, _cursor, statement, _params, _ctx, _many):
        if 'UPDATE cafeteria.locations' in statement:
            cutover_attempted.set()

    def cutover() -> None:
        with cutover_engine.begin() as connection:
            connection.execute(
                text('UPDATE cafeteria.locations SET active=(id=:new_location_id)'),
                {'new_location_id': catalog_database.other_location_id},
            )

    event.listen(publish_engine, 'after_cursor_execute', after_location_lock)
    event.listen(cutover_engine, 'before_cursor_execute', before_cutover)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            publishing = pool.submit(
                workflow.publish_draft_scoped,
                publish_engine,
                'patient',
                TARGET_WEEK,
                expected_row_version=version,
                actor_id=2,
                issuer_engine=None,
                expected_location_id=catalog_database.location_id,
            )
            assert location_locked.wait(5)
            changing_location = pool.submit(cutover)
            assert cutover_attempted.wait(5)
            assert not changing_location.done()
            release.set()
            snapshot = publishing.result(timeout=10)
            changing_location.result(timeout=10)
    finally:
        release.set()
        event.remove(publish_engine, 'after_cursor_execute', after_location_lock)
        event.remove(cutover_engine, 'before_cursor_execute', before_cutover)
        publish_engine.dispose()
        cutover_engine.dispose()

    assert snapshot['location']['code'] == 'KIRCHLINDACH'
    with catalog_database.owner.connect() as connection:
        assert connection.execute(
            text('SELECT id FROM cafeteria.locations WHERE active')
        ).scalar_one() == catalog_database.other_location_id


def test_late_direct_withdrawal_waits_for_replacement_and_leaves_one_active(
    catalog_database: CatalogDatabase,
) -> None:
    second_version, revision_id, direct_capability = _prepare_replacement(catalog_database)

    publish_engine = _separate_engine(catalog_database)
    withdraw_engine = _separate_engine(catalog_database)
    publication_locked, withdrawal_attempted, release = Event(), Event(), Event()

    def after_publication_lock(_conn, _cursor, statement, _params, _ctx, _many):
        if 'lock_active_publication' in statement:
            publication_locked.set()
            assert release.wait(10)

    def before_direct_withdrawal(_conn, _cursor, statement, _params, _ctx, _many):
        if 'withdraw_publication_revision' in statement:
            withdrawal_attempted.set()

    event.listen(publish_engine, 'after_cursor_execute', after_publication_lock)
    event.listen(withdraw_engine, 'before_cursor_execute', before_direct_withdrawal)
    try:
        with ThreadPoolExecutor(max_workers=2) as pool:
            publishing = pool.submit(
                workflow.publish_draft,
                publish_engine,
                'patient',
                TARGET_WEEK,
                expected_row_version=second_version,
                actor_id=2,
                issuer_engine=catalog_database.owner,
            )
            assert publication_locked.wait(5)
            withdrawal = pool.submit(
                withdraw_publication_revision,
                withdraw_engine,
                revision_id,
                direct_capability,
                'Direkter paralleler Rückzug',
            )
            assert withdrawal_attempted.wait(10)
            assert not withdrawal.done()
            release.set()
            published = publishing.result(timeout=10)
            with pytest.raises(DBAPIError, match='bereits zurückgezogen|55000'):
                withdrawal.result(timeout=10)
    finally:
        release.set()
        event.remove(publish_engine, 'after_cursor_execute', after_publication_lock)
        event.remove(withdraw_engine, 'before_cursor_execute', before_direct_withdrawal)
        publish_engine.dispose()
        withdraw_engine.dispose()

    with catalog_database.owner.connect() as connection:
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.publication_revisions'
        )).scalar_one() == 2
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.publication_revisions WHERE withdrawn_at IS NULL'
        )).scalar_one() == 1
        assert connection.execute(text(
            'SELECT id FROM cafeteria.publication_revisions WHERE withdrawn_at IS NULL'
        )).scalar_one() != revision_id
    assert published['revision_id'].endswith('-R2')


def test_pre_won_direct_withdrawal_stale_aborts_with_zero_active(
    catalog_database: CatalogDatabase,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    second_version, revision_id, direct_capability = _prepare_replacement(catalog_database)
    publish_engine = _separate_engine(catalog_database)
    withdraw_engine = _separate_engine(catalog_database)
    capability_issued, release = Event(), Event()
    real_issue = workflow.issue_publication_capability

    def issue_then_pause(issuer_engine: Engine, actor_id: int, target_revision_id: int) -> str:
        capability = real_issue(issuer_engine, actor_id, target_revision_id)
        capability_issued.set()
        assert release.wait(10)
        return capability

    monkeypatch.setattr(workflow, 'issue_publication_capability', issue_then_pause)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            publishing = pool.submit(
                workflow.publish_draft,
                publish_engine,
                'patient',
                TARGET_WEEK,
                expected_row_version=second_version,
                actor_id=2,
                issuer_engine=catalog_database.owner,
            )
            assert capability_issued.wait(5)
            withdraw_publication_revision(
                withdraw_engine,
                revision_id,
                direct_capability,
                'Vorgezogener direkter Rückzug',
            )
            release.set()
            with pytest.raises(workflow.StaleDraftError):
                publishing.result(timeout=10)
    finally:
        release.set()
        publish_engine.dispose()
        withdraw_engine.dispose()

    with catalog_database.owner.connect() as connection:
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.publication_revisions'
        )).scalar_one() == 1
        assert connection.execute(text(
            'SELECT count(*) FROM cafeteria.publication_revisions WHERE withdrawn_at IS NULL'
        )).scalar_one() == 0
