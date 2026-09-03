from __future__ import annotations

# ruff: noqa: F401, F811

import threading
from concurrent.futures import ThreadPoolExecutor
from dataclasses import dataclass
from datetime import date, timedelta

import pytest
from sqlalchemy import text

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


def _seed_source(
    database: CatalogDatabase,
    *,
    profile: str = 'patient',
    catalog_component: bool = True,
) -> SeededWeek:
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
        profile_id = int(connection.execute(
            text('SELECT id FROM cafeteria.offer_profiles WHERE code=:code'),
            {'code': profile},
        ).scalar_one())
        week = connection.execute(text(
            '''
            INSERT INTO cafeteria.menu_weeks(
                location_id, profile_id, week_start, workflow_state, title, shared_note,
                created_by, updated_by
            ) VALUES (:location_id, :profile_id, :week_start, 'draft', :title, :note, 2, 2)
            RETURNING id, public_id::text AS public_id
            '''
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
                '''
                INSERT INTO cafeteria.menu_services(
                    menu_week_id, service_date, meal_period_id, service_state, notice
                )
                SELECT :week_id, :service_date, id, :state, :notice
                FROM cafeteria.meal_periods WHERE code=:meal
                RETURNING id, public_id::text AS public_id
                '''
            ), {
                'week_id': week['id'],
                'service_date': source_week + timedelta(days=offset),
                'state': 'open' if offset == 0 else 'closed',
                'notice': None if offset == 0 else '  Küche zu  ',
                'meal': meal_code,
            }).mappings().one()
            services.append(service)
        template_id = int(connection.execute(text(
            '''
            INSERT INTO cafeteria.dish_templates(menu_type_id, title, description)
            SELECT id, 'Vorlage', 'Beschreibung' FROM cafeteria.menu_types WHERE code='MENU_1'
            RETURNING id
            '''
        )).scalar_one())
        item = connection.execute(text(
            '''
            INSERT INTO cafeteria.menu_items(
                service_id, menu_type_id, dish_template_id, external_id, title, description,
                note, allergen_review_status, sort_order, allergen_mode, origin_mode, label_mode
            )
            SELECT :service_id, id, :template_id, :external_id, :title, :description,
                   :note, 'checked', 7, 'auto', 'manual', 'manual'
            FROM cafeteria.menu_types WHERE code='MENU_1'
            RETURNING id, public_id::text AS public_id
            '''
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
                '''
                SELECT id, row_version FROM cafeteria.menu_components
                WHERE public_id=CAST(:public_id AS uuid)
                '''
            ), {'public_id': component['public_id']}).mappings().one()
            connection.execute(text(
                '''
                INSERT INTO cafeteria.menu_item_components(
                    menu_item_id, sort_order, component_text, component_id,
                    component_row_version
                ) VALUES (:item_id, 1, 'alter Linkname', :component_id, :component_version)
                '''
            ), {
                'item_id': item['id'],
                'component_id': component_row['id'],
                'component_version': component_row['row_version'],
            })
        connection.execute(text(
            '''
            INSERT INTO cafeteria.menu_item_components(menu_item_id, sort_order, component_text)
            VALUES (:item_id, 2, :component_text)
            '''
        ), {'item_id': item['id'], 'component_text': '  Freitext\nKomponente  '})
        connection.execute(text(
            '''
            INSERT INTO cafeteria.menu_item_labels(menu_item_id, label_id)
            SELECT :item_id, id FROM cafeteria.dietary_labels WHERE code='GLUTEN_FREE'
            '''
        ), {'item_id': item['id']})
        connection.execute(text(
            '''
            INSERT INTO cafeteria.menu_item_allergens(menu_item_id, allergen_id, presence)
            SELECT :item_id, id, 'may_contain' FROM cafeteria.allergens WHERE code='FISH'
            '''
        ), {'item_id': item['id']})
        connection.execute(text(
            '''
            INSERT INTO cafeteria.origin_declarations(
                menu_item_id, ingredient, country_code, declaration_text
            ) VALUES (:item_id, '  Rind  ', 'CH', '  Rind: CH  ')
            '''
        ), {'item_id': item['id']})
        if profile == 'staff_guest':
            connection.execute(text(
                '''
                INSERT INTO cafeteria.menu_item_prices(
                    menu_item_id, internal_rappen, external_rappen, currency
                ) VALUES (:item_id, 950, 1450, 'CHF')
                '''
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
            '''
            WITH profile AS (
                SELECT id FROM cafeteria.offer_profiles WHERE code=:profile
            ), week_row AS (
                INSERT INTO cafeteria.menu_weeks(
                    location_id, profile_id, week_start, workflow_state, title,
                    created_by, updated_by
                ) SELECT :location_id, profile.id, :week_start, 'ready', 'Alt', 2, 2
                  FROM profile
                RETURNING id, public_id, row_version
            ), service_row AS (
                INSERT INTO cafeteria.menu_services(
                    menu_week_id, service_date, meal_period_id, service_state, notice
                ) SELECT week_row.id, :week_start, meal.id, 'closed', 'Alt geschlossen'
                  FROM week_row CROSS JOIN cafeteria.meal_periods meal
                  WHERE meal.code='LUNCH'
                RETURNING id
            )
            SELECT week_row.id, week_row.public_id::text AS public_id,
                   week_row.row_version, service_row.id AS service_id
            FROM week_row CROSS JOIN service_row
            '''
        ), {
            'profile': profile,
            'location_id': database.location_id,
            'week_start': TARGET_WEEK,
        }).mappings().one()
    return int(row['id']), str(row['public_id']), int(row['service_id'])


def _target_counts(database: CatalogDatabase, profile: str = 'patient') -> tuple[int, int, int]:
    with database.owner.connect() as connection:
        row = connection.execute(text(
            '''
            SELECT count(DISTINCT s.id) AS services, count(DISTINCT i.id) AS items,
                   count(DISTINCT mic.menu_item_id::text || ':' || mic.sort_order::text) AS links
            FROM cafeteria.menu_weeks w
            JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            LEFT JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
            LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
            LEFT JOIN cafeteria.menu_item_components mic ON mic.menu_item_id=i.id
            WHERE w.location_id=:location_id AND p.code=:profile AND w.week_start=:week_start
            '''
        ), {
            'location_id': database.location_id,
            'profile': profile,
            'week_start': TARGET_WEEK,
        }).one()
    return tuple(int(value) for value in row)


def test_copy_rebases_catalog_links_and_preserves_manual_bytes(
    catalog_database: CatalogDatabase,
) -> None:
    source = _seed_source(catalog_database)
    assert source.component is not None

    assert copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0) == 1

    with catalog_database.owner.connect() as connection:
        week = connection.execute(text(
            '''
            SELECT w.id, w.public_id::text, w.workflow_state, w.title, w.shared_note,
                   w.row_version, w.created_by, w.updated_by
            FROM cafeteria.menu_weeks w JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
            WHERE w.location_id=:location_id AND p.code='patient' AND w.week_start=:week_start
            '''
        ), {'location_id': catalog_database.location_id, 'week_start': TARGET_WEEK}).one()
        services = connection.execute(text(
            '''
            SELECT s.id, s.public_id::text, s.service_date, mp.code, s.service_state,
                   s.notice, s.row_version
            FROM cafeteria.menu_services s
            JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
            WHERE s.menu_week_id=:week_id ORDER BY s.service_date, mp.sort_order
            '''
        ), {'week_id': week[0]}).all()
        item = connection.execute(text(
            '''
            SELECT i.id, i.public_id::text, i.external_id, i.title, i.description, i.note,
                   i.allergen_review_status, i.sort_order, i.row_version, i.allergen_mode,
                   i.origin_mode, i.label_mode, i.dish_template_id
            FROM cafeteria.menu_items i JOIN cafeteria.menu_services s ON s.id=i.service_id
            WHERE s.menu_week_id=:week_id
            '''
        ), {'week_id': week[0]}).one()
        links = connection.execute(text(
            '''
            SELECT mic.sort_order, mic.component_text, c.public_id::text,
                   mic.component_row_version, c.row_version
            FROM cafeteria.menu_item_components mic
            LEFT JOIN cafeteria.menu_components c ON c.id=mic.component_id
            WHERE mic.menu_item_id=:item_id ORDER BY mic.sort_order
            '''
        ), {'item_id': item[0]}).all()
        labels = connection.execute(text(
            '''SELECT l.code FROM cafeteria.menu_item_labels x
               JOIN cafeteria.dietary_labels l ON l.id=x.label_id
               WHERE x.menu_item_id=:item_id ORDER BY l.code'''
        ), {'item_id': item[0]}).scalars().all()
        allergens = connection.execute(text(
            '''SELECT a.code, x.presence FROM cafeteria.menu_item_allergens x
               JOIN cafeteria.allergens a ON a.id=x.allergen_id
               WHERE x.menu_item_id=:item_id ORDER BY a.code'''
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


def test_copy_target_version_matrix_replaces_only_empty_skeleton(
    catalog_database: CatalogDatabase,
) -> None:
    _seed_source(catalog_database, catalog_component=False)
    with pytest.raises(ComponentNotFoundError):
        copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 1)
    target_id, target_public_id, old_service_id = _seed_empty_target(catalog_database)
    with pytest.raises(ComponentConflictError):
        copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0)
    with pytest.raises(ComponentConflictError):
        copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 2)

    assert copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 1) == 2

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


def test_copy_staff_prices_and_rejects_archived_or_anomalous_patient_data(
    catalog_database: CatalogDatabase,
) -> None:
    _seed_source(catalog_database, profile='staff_guest', catalog_component=False)
    assert copy_previous_week(
        catalog_database.app, _scope(catalog_database, 'staff_guest'), TARGET_WEEK, 0
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


def test_copy_archived_component_rolls_back_without_target(
    catalog_database: CatalogDatabase,
) -> None:
    source = _seed_source(catalog_database)
    assert source.component is not None
    archive_component(
        catalog_database.app,
        _scope(catalog_database),
        str(source.component['public_id']),
        int(source.component['row_version']),
    )
    with pytest.raises(ComponentConflictError):
        copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0)
    assert _target_counts(catalog_database) == (0, 0, 0)


def test_two_concurrent_copies_have_one_complete_winner(
    catalog_database: CatalogDatabase,
) -> None:
    _seed_source(catalog_database, catalog_component=False)
    barrier = threading.Barrier(2)

    def run() -> str:
        barrier.wait(timeout=10)
        try:
            copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0)
            return 'copied'
        except ComponentConflictError:
            return 'stale'

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = sorted(pool.map(lambda _: run(), range(2)))

    assert results == ['copied', 'stale']
    assert _target_counts(catalog_database) == (2, 1, 1)


def test_copy_and_first_item_save_never_create_hybrid_target(
    catalog_database: CatalogDatabase,
) -> None:
    _seed_source(catalog_database, catalog_component=False)
    barrier = threading.Barrier(2)

    def copy() -> str:
        barrier.wait(timeout=10)
        try:
            copy_previous_week(catalog_database.app, _scope(catalog_database), TARGET_WEEK, 0)
            return 'copy'
        except ComponentConflictError:
            return 'conflict'

    def first_save() -> str:
        barrier.wait(timeout=10)
        with catalog_database.app.begin() as connection:
            week_id = connection.execute(text(
                '''
                INSERT INTO cafeteria.menu_weeks(
                    location_id, profile_id, week_start, workflow_state, created_by, updated_by
                ) SELECT :location_id, id, :week_start, 'draft', 1, 1
                  FROM cafeteria.offer_profiles WHERE code='patient'
                ON CONFLICT (location_id, profile_id, week_start) DO NOTHING RETURNING id
                '''
            ), {
                'location_id': catalog_database.location_id,
                'week_start': TARGET_WEEK,
            }).scalar_one_or_none()
            if week_id is None:
                return 'conflict'
            service_id = connection.execute(text(
                '''INSERT INTO cafeteria.menu_services(
                       menu_week_id, service_date, meal_period_id
                   ) SELECT :week_id, :week_start, id FROM cafeteria.meal_periods
                     WHERE code='LUNCH' RETURNING id'''
            ), {'week_id': week_id, 'week_start': TARGET_WEEK}).scalar_one()
            connection.execute(text(
                '''INSERT INTO cafeteria.menu_items(
                       service_id, menu_type_id, external_id, title, sort_order
                   ) SELECT :service_id, id, 'RACE-FIRST-SAVE', 'Erstspeicherung', 1
                     FROM cafeteria.menu_types WHERE code='MENU_1' '''
            ), {'service_id': service_id})
        return 'save'

    with ThreadPoolExecutor(max_workers=2) as pool:
        outcomes = {pool.submit(copy), pool.submit(first_save)}
        results = sorted(future.result(timeout=20) for future in outcomes)

    assert results in (['conflict', 'copy'], ['conflict', 'save'])
    counts = _target_counts(catalog_database)
    with catalog_database.owner.connect() as connection:
        titles = connection.execute(text(
            '''SELECT i.title FROM cafeteria.menu_items i
               JOIN cafeteria.menu_services s ON s.id=i.service_id
               JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
               WHERE w.week_start=:week_start ORDER BY i.title'''
        ), {'week_start': TARGET_WEEK}).scalars().all()
    if 'copy' in results:
        assert counts == (2, 1, 1) and titles == ['  Menü Quelle  ']
    else:
        assert counts == (1, 1, 0) and titles == ['Erstspeicherung']


def test_copy_and_real_withdrawal_allow_no_partial_target(
    catalog_database: CatalogDatabase,
) -> None:
    _seed_source(catalog_database, catalog_component=False)
    actor_id = 2  # seeded demo publisher
    values = workflow_support._patient_values('Publiziertes Ziel')
    for offset, day_value in enumerate(values['days']):
        day_value['date'] = (TARGET_WEEK + timedelta(days=offset)).isoformat()
    workflow.ensure_week(catalog_database.app, 'patient', TARGET_WEEK, actor_id)
    version = workflow.save_draft(
        catalog_database.app, 'patient', TARGET_WEEK,
        expected_row_version=1, actor_id=actor_id, values=values,
    )
    workflow.publish_draft(
        catalog_database.app, 'patient', TARGET_WEEK,
        expected_row_version=version, actor_id=actor_id, issuer_engine=None,
    )
    with catalog_database.owner.begin() as connection:
        row = connection.execute(text(
            '''SELECT w.id, w.row_version, r.id AS revision_id
               FROM cafeteria.menu_weeks w
               JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
               JOIN cafeteria.publication_revisions r ON r.menu_week_id=w.id
               WHERE p.code='patient' AND w.week_start=:week_start
                 AND r.withdrawn_at IS NULL'''
        ), {'week_start': TARGET_WEEK}).mappings().one()
        connection.execute(
            text('DELETE FROM cafeteria.menu_services WHERE menu_week_id=:week_id'),
            {'week_id': row['id']},
        )
        capability = str(connection.execute(text(
            'SELECT cafeteria.issue_publication_capability(:actor_id, :revision_id)'
        ), {'actor_id': actor_id, 'revision_id': row['revision_id']}).scalar_one())
    barrier = threading.Barrier(2)

    def copy() -> str:
        barrier.wait(timeout=10)
        try:
            copy_previous_week(
                catalog_database.app, _scope(catalog_database), TARGET_WEEK,
                int(row['row_version']),
            )
            return 'copy'
        except ComponentConflictError:
            return 'conflict'

    def withdraw() -> str:
        barrier.wait(timeout=10)
        withdraw_publication_revision(
            catalog_database.app, int(row['revision_id']), capability, 'Race-Test'
        )
        return 'withdrawn'

    with ThreadPoolExecutor(max_workers=2) as pool:
        futures = (pool.submit(copy), pool.submit(withdraw))
        results = sorted(future.result(timeout=20) for future in futures)

    assert results in (['conflict', 'withdrawn'], ['copy', 'withdrawn'])
    with catalog_database.owner.connect() as connection:
        target = connection.execute(text(
            'SELECT workflow_state, row_version FROM cafeteria.menu_weeks WHERE id=:id'
        ), {'id': row['id']}).one()
        withdrawn = connection.execute(text(
            'SELECT withdrawn_at IS NOT NULL FROM cafeteria.publication_revisions WHERE id=:id'
        ), {'id': row['revision_id']}).scalar_one()
    assert withdrawn is True
    if 'copy' in results:
        assert target == ('draft', int(row['row_version']) + 1)
        assert _target_counts(catalog_database) == (2, 1, 1)
    else:
        assert target == ('published', int(row['row_version']))
        assert _target_counts(catalog_database) == (0, 0, 0)
