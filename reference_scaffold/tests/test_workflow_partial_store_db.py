from __future__ import annotations

import json
import os
import re
import secrets
import subprocess
from collections.abc import Iterator
from concurrent.futures import ThreadPoolExecutor
from copy import deepcopy
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from threading import Barrier

import pytest
from sqlalchemy import Engine, create_engine, text
from sqlalchemy.engine import URL, make_url
from sqlalchemy.pool import NullPool

from cafeteria import db as database
from cafeteria.component_catalog_store import AdminScope, create_component
from cafeteria.workflow import StaleDraftError, _draft_values, import_draft
from cafeteria.workflow_partial_store import (
    PartialWorkflowConflictError,
    PartialWorkflowNotFoundError,
    PartialWorkflowValidationError,
    persist_menu_item,
    persist_service_state,
    persist_week_header,
    resolve_item_id,
    resolve_week_ref,
)
from cafeteria.workflow_store import load_draft_connection


ROOT = Path(__file__).resolve().parents[2]
DATABASE_URL = os.getenv('TEST_DATABASE_URL')
WEEK = date(2026, 8, 31)


@dataclass(frozen=True)
class WorkflowDatabase:
    owner: Engine
    app: Engine
    location_id: int
    actor_id: int


def _docker_inspect(container: str, template: str) -> str:
    return subprocess.run(
        ['docker', 'inspect', '--type', 'container', '--format', template, container],
        check=True,
        capture_output=True,
        text=True,
        timeout=10,
    ).stdout.strip()


def _verify_target(database_url: str | None, container: str | None) -> URL:
    if not database_url or not container:
        pytest.skip('TEST_DATABASE_URL und TEST_DATABASE_CONTAINER fehlen.')
    url = make_url(database_url)
    if (
        url.get_backend_name() != 'postgresql'
        or url.host not in {'127.0.0.1', '::1'}
        or url.port is None
        or url.query
        or re.fullmatch(r'menuplan_(?:test|task)[a-z0-9_]*', url.database or '') is None
        or re.fullmatch(r'menuplan_(?:test|task)[a-z0-9_]*', url.username or '') is None
    ):
        raise RuntimeError('Unsichere Testdatenbank: URL ist nicht explizit test-lokal.')
    identity = _docker_inspect(
        container, '{{.Name}}|{{.State.Running}}|{{.Config.Image}}'
    ).split('|', 2)
    bindings = json.loads(
        _docker_inspect(container, '{{json (index .NetworkSettings.Ports "5432/tcp")}}')
    )
    if (
        identity[:2] != [f'/{container}', 'true']
        or re.fullmatch(r'postgres:16(?:-alpine)?(?:@sha256:[0-9a-f]{64})?', identity[2])
        is None
        or bindings != [{'HostIp': url.host, 'HostPort': str(url.port)}]
    ):
        raise RuntimeError('Unsichere Testdatenbank: Container stimmt nicht.')
    return url


def _drop_schema(engine: Engine) -> None:
    with engine.begin() as connection:
        connection.execute(text('DROP SCHEMA IF EXISTS cafeteria CASCADE'))


@pytest.fixture
def workflow_database() -> Iterator[WorkflowDatabase]:
    target = _verify_target(DATABASE_URL, os.getenv('TEST_DATABASE_CONTAINER'))
    assert DATABASE_URL is not None
    owner = create_engine(DATABASE_URL, poolclass=NullPool, pool_pre_ping=True)
    with owner.connect() as connection:
        connection.execute(text('SET TRANSACTION READ ONLY'))
        identity = connection.execute(
            text(
                'SELECT current_database(), current_user, '
                "current_setting('server_version_num')::int, "
                "current_setting('transaction_read_only')"
            )
        ).one()
    if (
        identity[0] != target.database
        or identity[1] != target.username
        or not 160_000 <= int(identity[2]) < 170_000
        or identity[3] != 'on'
    ):
        raise RuntimeError('Unsichere Testdatenbank: PostgreSQL-Identität stimmt nicht.')
    _drop_schema(owner)
    app_password = secrets.token_urlsafe(24)
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=app_password,
        backup_password=secrets.token_urlsafe(24),
        auth_issuer_password=secrets.token_urlsafe(24),
    )
    app_url = make_url(DATABASE_URL).set(
        username='cafeteria_app', password=app_password
    ).render_as_string(hide_password=False)
    app = create_engine(app_url, poolclass=NullPool, pool_pre_ping=True)
    with owner.connect() as connection:
        location_id = int(
            connection.execute(
                text('SELECT id FROM cafeteria.locations WHERE active ORDER BY id')
            ).scalar_one()
        )
        actor_id = int(
            connection.execute(
                text(
                    "SELECT id FROM cafeteria.users WHERE "
                    "public_id='00000000-0000-0000-0000-000000000002'"
                )
            ).scalar_one()
        )
    try:
        yield WorkflowDatabase(owner, app, location_id, actor_id)
    finally:
        app.dispose()
        _drop_schema(owner)
        owner.dispose()


def _scope(db: WorkflowDatabase, profile: str = 'patient') -> AdminScope:
    return AdminScope(db.actor_id, db.location_id, profile)  # type: ignore[arg-type]


def _payload(
    *,
    title: str = 'Rindsgeschnetzeltes',
    assignments: list[dict[str, object]] | None = None,
    modes: tuple[str, str, str] = ('manual', 'manual', 'manual'),
    staff: bool = False,
) -> dict[str, object]:
    value: dict[str, object] = {
        'title': title,
        'description': 'Rahmsauce',
        'note': 'Heute frisch',
        'allergen_mode': modes[0],
        'origin_mode': modes[1],
        'label_mode': modes[2],
        'assignments': assignments
        if assignments is not None
        else [{'component_public_id': None, 'component_text': '  Freitext\t'}],
        'labels': ['VEGETARIAN'],
        'allergens': [{'code': 'MILK', 'presence': 'contains'}],
        'origins': [
            {'ingredient': 'Rind', 'country_code': 'CH', 'text': 'Rind: CH'}
        ],
    }
    if staff:
        value.update(internal_rappen=950, external_rappen=1450)
    return value


def _full_values(marker: str, *, reverse_components: bool = False) -> dict[str, object]:
    days = []
    for offset in range(7):
        service_date = (WEEK + timedelta(days=offset)).isoformat()
        services = []
        for meal in ('LUNCH', 'DINNER'):
            options = []
            for option in ('MENU_1', 'VEGGIE'):
                components = [f'{marker}-A', f'{marker}-B']
                if reverse_components:
                    components.reverse()
                options.append(
                    {
                        'type_code': option,
                        'title': f'{marker} Gericht',
                        'components': components,
                        'allergen_review_status': 'checked',
                    }
                )
            services.append(
                {
                    'meal_code': meal,
                    'service_state': 'open',
                    'notice': '',
                    'options': options,
                }
            )
        days.append({'date': service_date, 'services': services})
    return {'title': marker, 'shared_note': '', 'days': days}


def _week_state(db: WorkflowDatabase, week: date = WEEK) -> tuple[object, ...]:
    with db.owner.connect() as connection:
        return tuple(
            connection.execute(
                text(
                    '''
                    SELECT w.row_version, w.title, count(DISTINCT s.id), count(DISTINCT i.id),
                           count(*) FILTER (WHERE mic.component_id IS NOT NULL)
                    FROM cafeteria.menu_weeks w
                    JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                    LEFT JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
                    LEFT JOIN cafeteria.menu_items i ON i.service_id=s.id
                    LEFT JOIN cafeteria.menu_item_components mic ON mic.menu_item_id=i.id
                    WHERE w.location_id=:location AND p.code='patient' AND w.week_start=:week
                    GROUP BY w.id
                    '''
                ),
                {'location': db.location_id, 'week': week},
            ).one()
        )


def test_existing_only_resolvers_and_exact_header_cas(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db)
    with db.app.connect() as connection:
        with pytest.raises(PartialWorkflowNotFoundError):
            resolve_week_ref(connection, scope, WEEK)

    assert persist_week_header(db.app, scope, WEEK, {'title': 'Woche', 'shared_note': ''}, 0) == 1
    with pytest.raises(PartialWorkflowConflictError):
        persist_week_header(db.app, scope, WEEK, {'title': 'Stale', 'shared_note': ''}, 0)
    with pytest.raises(PartialWorkflowConflictError):
        persist_week_header(db.app, scope, WEEK, {'title': 'Stale', 'shared_note': ''}, 2)
    assert persist_week_header(db.app, scope, WEEK, {'title': 'Neu', 'shared_note': 'Hinweis'}, 1) == 2

    with db.app.connect() as connection:
        week_ref = resolve_week_ref(connection, scope, WEEK)
        assert (
            week_ref.location_id,
            week_ref.profile_code,
            week_ref.week_start,
            week_ref.row_version,
        ) == (db.location_id, 'patient', WEEK, 2)
        with pytest.raises(PartialWorkflowNotFoundError):
            resolve_item_id(connection, scope, week_ref, '2026-08-31', 'LUNCH', 'MENU_1')
    with pytest.raises(PartialWorkflowNotFoundError):
        persist_week_header(
            db.app,
            scope,
            WEEK + timedelta(days=7),
            {'title': 'Fehlt', 'shared_note': ''},
            1,
        )


def test_service_cas_reopen_and_nonempty_close_are_atomic(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db)
    closed = {'service_state': 'closed', 'notice': 'Ruhetag'}
    assert persist_service_state(db.app, scope, WEEK, '2026-08-31', 'LUNCH', closed, 0) == 1
    with pytest.raises(PartialWorkflowConflictError):
        persist_service_state(db.app, scope, WEEK, '2026-08-31', 'LUNCH', closed, 0)
    assert persist_service_state(
        db.app,
        scope,
        WEEK,
        '2026-08-31',
        'LUNCH',
        {'service_state': 'open', 'notice': ''},
        1,
    ) == 2
    assert persist_menu_item(
        db.app, scope, WEEK, '2026-08-31', 'LUNCH', 'MENU_1', _payload(), 0
    ) == 1
    before = _week_state(db)
    with pytest.raises(PartialWorkflowConflictError, match='Menü'):
        persist_service_state(db.app, scope, WEEK, '2026-08-31', 'LUNCH', closed, 2)
    assert _week_state(db) == before
    with pytest.raises(PartialWorkflowNotFoundError):
        persist_service_state(
            db.app, scope, WEEK, '2026-09-01', 'DINNER', {'service_state': 'open', 'notice': ''}, 1
        )


def test_item_payload_effects_prices_and_neighbour_isolation(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    patient = _scope(db)
    component = create_component(
        db.app,
        patient,
        'meat',
        'Rind',
        'CH',
        'current',
        ['GLUTEN_FREE'],
        [('MILK', 'contains')],
    )
    assignments = [
        {'component_public_id': str(component['public_id']), 'component_text': None},
        {'component_public_id': None, 'component_text': '  Freitext\t'},
    ]
    auto = _payload(assignments=assignments, modes=('auto', 'auto', 'auto'))
    assert persist_menu_item(
        db.app, patient, WEEK, '2026-08-31', 'LUNCH', 'MENU_1', auto, 0
    ) == 1
    assert persist_menu_item(
        db.app,
        patient,
        WEEK,
        '2026-09-01',
        'DINNER',
        'VEGGIE',
        _payload(title='Nachbar'),
        0,
    ) == 1
    with db.owner.connect() as connection:
        rows = connection.execute(
            text(
                '''
                SELECT i.title, i.row_version, i.allergen_review_status,
                       array_agg(mic.component_text ORDER BY mic.sort_order),
                       array_agg(mc.public_id::text ORDER BY mic.sort_order),
                       array_agg(DISTINCT dl.code), array_agg(DISTINCT a.code),
                       array_agg(DISTINCT o.declaration_text)
                FROM cafeteria.menu_items i
                JOIN cafeteria.menu_services s ON s.id=i.service_id
                JOIN cafeteria.menu_item_components mic ON mic.menu_item_id=i.id
                LEFT JOIN cafeteria.menu_components mc ON mc.id=mic.component_id
                LEFT JOIN cafeteria.menu_item_labels il ON il.menu_item_id=i.id
                LEFT JOIN cafeteria.dietary_labels dl ON dl.id=il.label_id
                LEFT JOIN cafeteria.menu_item_allergens ia ON ia.menu_item_id=i.id
                LEFT JOIN cafeteria.allergens a ON a.id=ia.allergen_id
                LEFT JOIN cafeteria.origin_declarations o ON o.menu_item_id=i.id
                WHERE s.service_date=DATE '2026-08-31'
                GROUP BY i.id
                '''
            )
        ).one()
        assert rows[0:3] == ('Rindsgeschnetzeltes', 1, 'not_checked')
        assert rows[3] == ['Rind', '  Freitext\t']
        assert str(component['public_id']) in rows[4]
        assert 'GLUTEN_FREE' in rows[5] and 'MILK' in rows[6] and 'Rind: CH' in rows[7]

    manual = _payload(title='Geändert')
    assert persist_menu_item(
        db.app, patient, WEEK, '2026-08-31', 'LUNCH', 'MENU_1', manual, 1
    ) == 2
    before = _week_state(db)
    with pytest.raises(PartialWorkflowConflictError):
        persist_menu_item(
            db.app, patient, WEEK, '2026-08-31', 'LUNCH', 'MENU_1', auto, 1
        )
    assert _week_state(db) == before
    with db.owner.connect() as connection:
        neighbour = connection.execute(
            text(
                '''
                SELECT i.title, i.row_version FROM cafeteria.menu_items i
                JOIN cafeteria.menu_services s ON s.id=i.service_id
                JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
                JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
                WHERE s.service_date=DATE '2026-09-01' AND mp.code='DINNER' AND mt.code='VEGGIE'
                '''
            )
        ).one()
        assert neighbour == ('Nachbar', 1)

    staff = _scope(db, 'staff_guest')
    assert persist_menu_item(
        db.app,
        staff,
        WEEK,
        '2026-08-31',
        'LUNCH',
        'MENU_1',
        _payload(staff=True),
        0,
    ) == 1
    with db.owner.connect() as connection:
        assert connection.execute(
            text(
                '''
                SELECT pr.internal_rappen, pr.external_rappen, pr.currency
                FROM cafeteria.menu_item_prices pr
                JOIN cafeteria.menu_items i ON i.id=pr.menu_item_id
                JOIN cafeteria.menu_services s ON s.id=i.service_id
                JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                WHERE p.code='staff_guest'
                '''
            )
        ).one() == (950, 1450, 'CHF')


@pytest.mark.parametrize(
    ('profile', 'week', 'day', 'meal', 'option'),
    [
        ('patient', date(2026, 9, 1), '2026-09-01', 'LUNCH', 'MENU_1'),
        ('patient', WEEK, '2026-09-07', 'LUNCH', 'MENU_1'),
        ('patient', WEEK, '2026-08-31T00:00:00', 'LUNCH', 'MENU_1'),
        ('patient', WEEK, '2026-08-31', 'BREAKFAST', 'MENU_1'),
        ('patient', WEEK, '2026-08-31', 'LUNCH', 'MENU_3'),
        ('staff_guest', WEEK, '2026-09-05', 'LUNCH', 'MENU_1'),
        ('staff_guest', WEEK, '2026-08-31', 'DINNER', 'MENU_1'),
    ],
)
def test_invalid_raster_is_rejected_before_writes(
    workflow_database: WorkflowDatabase,
    profile: str,
    week: date,
    day: str,
    meal: str,
    option: str,
) -> None:
    db = workflow_database
    with pytest.raises(PartialWorkflowValidationError):
        persist_menu_item(
            db.app, _scope(db, profile), week, day, meal, option, _payload(), 0
        )
    with db.owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == 0


def test_load_projection_hides_internal_fields_and_full_import_is_safe(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db)
    component = create_component(
        db.app, scope, 'side', 'Kartoffelstock', 'CH', 'current', [], []
    )
    assert persist_menu_item(
        db.app,
        scope,
        WEEK,
        '2026-08-31',
        'LUNCH',
        'MENU_1',
        _payload(
            assignments=[
                {'component_public_id': str(component['public_id']), 'component_text': None}
            ]
        ),
        0,
    ) == 1
    with db.app.connect() as connection:
        internal = load_draft_connection(connection, 'patient', WEEK)
    public = _draft_values(internal)
    option = public['days'][0]['services'][0]['options'][0]
    assert set(option) == {
        'type_code', 'external_id', 'title', 'description', 'components',
        'labels', 'allergens', 'origins', 'note', 'allergen_review_status',
    }
    assert 'assignments' not in option and 'allergen_mode' not in option

    before = _week_state(db)
    with pytest.raises(StaleDraftError, match='Katalog'):
        import_draft(
            db.app,
            'patient',
            WEEK,
            expected_row_version=int(before[0]),
            actor_id=db.actor_id,
            values=_full_values('IMPORT'),
        )
    assert _week_state(db) == before

    clean_week = WEEK + timedelta(days=7)
    clean_values = deepcopy(_full_values('FREE'))
    for day in clean_values['days']:
        day['date'] = (date.fromisoformat(day['date']) + timedelta(days=7)).isoformat()
    assert import_draft(
        db.app,
        'patient',
        clean_week,
        expected_row_version=0,
        actor_id=db.actor_id,
        values=clean_values,
    ) == 2
    with db.owner.connect() as connection:
        assert connection.execute(
            text(
                '''
                SELECT count(*) FILTER (WHERE mic.component_id IS NOT NULL),
                       bool_and(i.allergen_mode='manual' AND i.origin_mode='manual'
                                AND i.label_mode='manual')
                FROM cafeteria.menu_weeks w
                JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
                JOIN cafeteria.menu_items i ON i.service_id=s.id
                JOIN cafeteria.menu_item_components mic ON mic.menu_item_id=i.id
                WHERE w.week_start=:week
                '''
            ),
            {'week': clean_week},
        ).one() == (0, True)


def test_missing_slot_races_have_exact_winners(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    scope = _scope(db)

    def race(days: tuple[str, str]) -> list[object]:
        barrier = Barrier(2)

        def save(day: str) -> object:
            barrier.wait()
            try:
                return persist_menu_item(
                    db.app, scope, WEEK, day, 'LUNCH', 'MENU_1', _payload(title=day), 0
                )
            except Exception as error:  # assertion captures exact domain outcome
                return error

        with ThreadPoolExecutor(max_workers=2) as pool:
            return list(pool.map(save, days))

    same = race(('2026-08-31', '2026-08-31'))
    assert sorted(type(value).__name__ for value in same) == [
        'PartialWorkflowConflictError',
        'int',
    ]
    assert [value for value in same if type(value) is int] == [1]

    different = race(('2026-09-01', '2026-09-02'))
    assert different == [1, 1]
    with db.owner.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 3


def test_full_import_same_version_race_has_one_complete_winner(
    workflow_database: WorkflowDatabase,
) -> None:
    db = workflow_database
    assert persist_week_header(
        db.app, _scope(db), WEEK, {'title': 'Leer', 'shared_note': ''}, 0
    ) == 1
    barrier = Barrier(2)

    def run(args: tuple[str, bool]) -> object:
        barrier.wait()
        try:
            return import_draft(
                db.app,
                'patient',
                WEEK,
                expected_row_version=1,
                actor_id=db.actor_id,
                values=_full_values(args[0], reverse_components=args[1]),
            )
        except Exception as error:  # assertion captures stale versus success
            return error

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(run, [('FIRST', False), ('SECOND', True)]))
    assert sorted(type(value).__name__ for value in results) == ['StaleDraftError', 'int']
    assert [value for value in results if type(value) is int] == [2]
    state = _week_state(db)
    assert state[0] == 2 and state[2:4] == (14, 28)
    assert state[1] in {'FIRST', 'SECOND'}
