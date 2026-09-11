from __future__ import annotations

from collections.abc import Mapping
from pathlib import Path
from uuid import uuid4

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text
from werkzeug.datastructures import MultiDict

from cafeteria.component_catalog_store import (
    AdminScope,
    ComponentCatalogValidationError,
    StaleComponentError,
    create_component,
    find_components,
    get_component,
    update_component,
)
from cafeteria.workflow import WorkflowValidationError
from cafeteria.workflow_partial_form import parse_component_update_form
from test_component_catalog_browser import _assert_component_controls_fit, catalog_page  # noqa: F401
from test_component_catalog_db import CatalogDatabase, _create, _scope, catalog_database  # noqa: F401
from test_rendered_ui import DATABASE_URL, _login, admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(
    not DATABASE_URL,
    reason='TEST_DATABASE_URL für eine isolierte PostgreSQL-Testdatenbank fehlt.',
)

VIEWPORTS = (
    (1440, 900),
    (390, 844),
    (1024, 768),
    (768, 1024),
    (1920, 1080),
)


def _payload(name: str = 'Kartoffelstock', **updates: object) -> dict[str, object]:
    payload: dict[str, object] = {
        'category': 'side',
        'name': name,
        'origin_country_code': 'CH',
        'label_codes': ('VEGAN',),
        'allergens': (('MILK', 'contains'),),
    }
    payload.update(updates)
    return payload


def _insert_location_food(
    engine,
    *,
    actor_id: int,
    location_id: int,
    name: str,
    active: bool = True,
) -> dict[str, object]:
    with engine.begin() as connection:
        storage_id = connection.execute(
            text(
                '''
                SELECT id FROM cafeteria.storage_locations
                WHERE location_id=:location AND active
                ORDER BY id LIMIT 1
                '''
            ),
            {'location': location_id},
        ).scalar_one_or_none()
        if storage_id is None:
            storage_id = connection.execute(
                text(
                    '''
                    INSERT INTO cafeteria.storage_locations(
                        location_id, code, name, created_by, updated_by
                    ) VALUES (
                        :location, 'COLD', 'Lager', :actor, :actor
                    )
                    RETURNING id
                    '''
                ),
                {'location': location_id, 'actor': actor_id},
            ).scalar_one()
        row = connection.execute(
            text(
                '''
                INSERT INTO cafeteria.foods(
                    location_id, created_by, updated_by, name, base_unit_id, active
                ) VALUES (
                    :location, :actor, :actor, :name,
                    (SELECT id FROM cafeteria.measurement_units WHERE code='G'),
                    :active
                )
                RETURNING id, public_id::text AS public_id, name, active
                '''
            ),
            {
                'location': location_id,
                'actor': actor_id,
                'name': name,
                'active': active,
            },
        ).mappings().one()
        connection.execute(
            text(
                '''
                INSERT INTO cafeteria.food_storage_locations(
                    location_id, food_id, storage_location_id
                ) VALUES (:location, :food, :storage)
                '''
            ),
            {'location': location_id, 'food': row['id'], 'storage': storage_id},
        )
    return dict(row)


def _insert_food(
    database: CatalogDatabase,
    *,
    name: str = 'Karotte',
    location_id: int | None = None,
    active: bool = True,
) -> dict[str, object]:
    return _insert_location_food(
        database.owner,
        actor_id=database.actor_id,
        location_id=database.location_id if location_id is None else location_id,
        name=name,
        active=active,
    )


def _food_saved(engine, public_id: str) -> list[Mapping[str, object]]:
    with engine.connect() as connection:
        return list(
            connection.execute(
                text(
                    '''
                    SELECT details->>'row_version_before' AS before_version,
                           details->>'row_version_after' AS after_version,
                           details->>'food_public_id' AS food_public_id
                    FROM cafeteria.audit_events
                    WHERE action='component.food_saved'
                      AND entity_public_id=CAST(:public_id AS uuid)
                    ORDER BY (details->>'row_version_after')::bigint
                    '''
                ),
                {'public_id': public_id},
            ).mappings()
        )


def _update_form(**fields: str) -> MultiDict[str, str]:
    form = MultiDict([
        ('_csrf', 'test-csrf'),
        ('category', 'meat'),
        ('name', 'Rindsragout'),
        ('origin_country_code', 'CH'),
        ('row_version', '7'),
        ('label_code', 'HIGH_PROTEIN'),
        ('allergen_code', 'A'),
        ('allergen_presence', 'contains'),
    ])
    for key, value in fields.items():
        form[key] = value
    return form


def test_parse_component_update_form_food_detach_and_uuid() -> None:
    bound = str(uuid4())
    parsed = parse_component_update_form(_update_form(food_public_id=bound))
    assert parsed.payload['food_public_id'] == bound
    with pytest.raises(WorkflowValidationError, match='bestätigen') as missing:
        parse_component_update_form(
            _update_form(food_public_id=''), current_food_public_id=bound,
        )
    assert missing.value.field_name == 'food_detach_confirm'
    with pytest.raises(WorkflowValidationError, match='bestätigen') as invalid:
        parse_component_update_form(
            _update_form(food_public_id='', food_detach_confirm='0'),
            current_food_public_id=bound,
        )
    assert invalid.value.field_name == 'food_detach_confirm'
    detached = parse_component_update_form(
        _update_form(food_public_id='', food_detach_confirm='1'),
        current_food_public_id=bound,
    )
    assert detached.payload['food_public_id'] is None
    unbound = parse_component_update_form(_update_form(food_public_id=''))
    assert unbound.payload['food_public_id'] is None
    with pytest.raises(WorkflowValidationError, match='UUID') as bad:
        parse_component_update_form(_update_form(food_public_id='not-a-uuid'))
    assert bad.value.field_name == 'food_public_id'
    unchanged = parse_component_update_form(_update_form())
    assert 'food_public_id' not in unchanged.payload


def test_catalog_food_writer_roundtrip_receipt_and_rejects(
    catalog_database: CatalogDatabase,  # noqa: F811
) -> None:
    component = _create(
        catalog_database, labels=('VEGAN',), allergens=(('MILK', 'contains'),),
    )
    public_id = str(component['public_id'])
    food = _insert_food(catalog_database, name='Karotte')
    archived = _insert_food(catalog_database, name='Alte Rübe', active=False)
    foreign = _insert_food(
        catalog_database, name='Fremde Rübe', location_id=catalog_database.other_location_id,
    )
    scope = _scope(catalog_database)
    version = update_component(
        catalog_database.app, scope, public_id,
        _payload(food_public_id=str(food['public_id'])), 1,
    )
    assert version == 2
    loaded = get_component(catalog_database.app, scope, public_id)
    assert loaded['food_public_id'] == food['public_id']
    assert loaded['food_name'] == 'Karotte'
    assert loaded['labels'] == component['labels']
    assert loaded['allergens'] == component['allergens']
    assert loaded['origin_country_code'] == 'CH'
    receipts = _food_saved(catalog_database.owner, public_id)
    assert [(row['before_version'], row['after_version'], row['food_public_id']) for row in receipts] == [
        ('1', '2', food['public_id']),
    ]
    assert update_component(
        catalog_database.app, scope, public_id,
        _payload(food_public_id=str(food['public_id'])), 2,
    ) == 2
    assert len(_food_saved(catalog_database.owner, public_id)) == 1
    listed = find_components(catalog_database.app, scope, 'Kartoffelstock', None, False)
    assert listed[0]['food_name'] == 'Karotte' and listed[0]['food_public_id'] == food['public_id']
    for invalid in (str(archived['public_id']), str(foreign['public_id']), str(uuid4())):
        with pytest.raises(ComponentCatalogValidationError, match='Aktives Lebensmittel') as raised:
            update_component(
                catalog_database.app, scope, public_id,
                _payload(food_public_id=invalid), 2,
            )
        assert raised.value.field_name == 'food_public_id'
    assert get_component(catalog_database.app, scope, public_id)['food_public_id'] == food['public_id']
    assert len(_food_saved(catalog_database.owner, public_id)) == 1
    with pytest.raises(StaleComponentError):
        update_component(
            catalog_database.app, scope, public_id,
            _payload(food_public_id=None), 1,
        )
    assert get_component(catalog_database.app, scope, public_id)['row_version'] == 2
    detached = update_component(
        catalog_database.app, scope, public_id, _payload(food_public_id=None), 2,
    )
    assert detached == 3
    cleared = get_component(catalog_database.app, scope, public_id)
    assert cleared['food_public_id'] is None and cleared['food_name'] is None
    assert cleared['allergens'] == component['allergens']
    after = _food_saved(catalog_database.owner, public_id)
    assert len(after) == 2
    assert after[1]['before_version'] == '2' and after[1]['after_version'] == '3'
    assert after[1]['food_public_id'] is None


def test_component_food_selection_browser_roundtrip(
    catalog_page: Page, request: pytest.FixtureRequest, tmp_path: Path,  # noqa: F811
) -> None:
    page = catalog_page
    engine = request.getfixturevalue('admin_engine')
    with engine.connect() as connection:
        actor = connection.execute(text(
            "SELECT id FROM cafeteria.users WHERE public_id='00000000-0000-0000-0000-000000000002'"
        )).scalar_one()
        location = connection.execute(text(
            'SELECT id FROM cafeteria.locations WHERE active ORDER BY id'
        )).scalar_one()
    food = _insert_location_food(
        engine, actor_id=int(actor), location_id=int(location),
        name=f'Karotte-{uuid4().hex[:8]}',
    )
    family = 'patienten'
    list_path = f'/admin/{family}/komponenten'
    page.set_viewport_size({'width': 1440, 'height': 900})
    page.goto(list_path)
    page.locator('#create-component summary').click()
    form = page.locator(f'form[action="{list_path}"][method="post"]')
    form.locator('[name="name"]').fill(f'Komponenten-Karotte-{uuid4().hex[:8]}')
    form.locator('[name="category"]').select_option('side')
    form.locator('[name="origin_country_code"]').select_option('CH')
    form.locator('[name="label_code"][value="VEGAN"]').check()
    gluten = form.locator('.allergen-row').filter(has=page.locator('[value="GLUTEN"]'))
    gluten.locator('[name="allergen_code"]').check()
    gluten.locator('select').select_option('contains')
    form.get_by_role('button', name='Komponente erstellen', exact=True).click()
    page.wait_for_url(f'**{list_path}/*')
    public_id = page.locator('main').get_attribute('data-public-id')
    assert public_id
    detail = page.locator('#component-form')
    expect(page.locator('#c-food')).to_be_visible()
    expect(page.locator('#c-food option[value=""]')).to_have_text('Kein Lebensmittel')
    page.locator('#c-food').select_option(food['public_id'])
    with page.expect_response(lambda response: response.request.method == 'POST') as bound:
        detail.get_by_role('button', name='Speichern', exact=True).click()
    assert bound.value.status == 303
    page.wait_for_load_state()
    expect(page.locator('#c-food')).to_have_value(food['public_id'])
    expect(page.locator('#c-food-current')).to_contain_text(food['public_id'])
    expect(page.locator('#c-food-current')).to_contain_text(str(food['name']))
    expect(detail.locator('[name="label_code"][value="VEGAN"]')).to_be_checked()
    expect(detail.locator('[name="allergen_code"][value="GLUTEN"]')).to_be_checked()
    receipts = _food_saved(engine, public_id)
    assert len(receipts) == 1
    assert receipts[0]['food_public_id'] == food['public_id']
    page.goto(list_path)
    row = page.locator(f'.component-row[data-public-id="{public_id}"]')
    expect(row).to_contain_text(f"Lebensmittel: {food['name']}")
    page.goto(f'{list_path}/{public_id}')
    page.locator('#c-food').select_option('')
    with page.expect_response(lambda response: response.request.method == 'POST') as denied:
        page.locator('#component-form').get_by_role('button', name='Speichern', exact=True).click()
    assert denied.value.status == 400
    expect(page.locator('#c-food-detach-error')).to_be_visible()
    assert len(_food_saved(engine, public_id)) == 1
    expect(page.locator('#c-food-current')).to_contain_text(food['public_id'])
    page.locator('#c-food').select_option('')
    page.locator('#c-food-detach').check()
    with page.expect_response(lambda response: response.request.method == 'POST') as detached:
        page.locator('#component-form').get_by_role('button', name='Speichern', exact=True).click()
    assert detached.value.status == 303
    page.wait_for_load_state()
    expect(page.locator('#c-food')).to_have_value('')
    expect(page.locator('#c-food-current')).to_have_count(0)
    after = _food_saved(engine, public_id)
    assert len(after) == 2
    assert after[1]['food_public_id'] is None
    page.goto(list_path)
    expect(page.locator(f'.component-row[data-public-id="{public_id}"]')).to_contain_text(
        'kein Lebensmittel'
    )
    page.goto(f'{list_path}/{public_id}')
    page.locator('#c-food').select_option(food['public_id'])
    page.locator('#component-form').get_by_role('button', name='Speichern', exact=True).click()
    page.wait_for_load_state()
    page.locator('#component-form input[name="row_version"]').evaluate(
        'el => el.value = "1"',
    )
    page.locator('#c-food').select_option('')
    page.locator('#c-food-detach').check()
    with page.expect_response(lambda response: response.request.method == 'POST') as stale:
        page.locator('#component-form').get_by_role('button', name='Speichern', exact=True).click()
    assert stale.value.status == 409
    expect(page.locator('#c-food-detach')).to_be_checked()
    expect(page.locator('#component-form [name="_csrf"]')).not_to_have_value('')
    for width, height in VIEWPORTS:
        page.set_viewport_size({'width': width, 'height': height})
        page.goto(f'{list_path}/{public_id}')
        expect(page.locator('#c-food')).to_be_visible()
        page.locator('#c-food').focus()
        assert page.evaluate('document.activeElement && document.activeElement.id') == 'c-food'
        _assert_component_controls_fit(page)
        page.screenshot(path=str(tmp_path / f'component-food-{family}-{width}x{height}.png'), full_page=True)
    page.set_viewport_size({'width': 390, 'height': 844})
    page.evaluate('document.documentElement.style.zoom = "2"')
    page.screenshot(path=str(tmp_path / 'component-food-390-zoom200.png'), full_page=True)
    page.evaluate('document.documentElement.style.zoom = "1"')
    _assert_component_controls_fit(page)


def test_component_food_selection_nojs(
    request: pytest.FixtureRequest, tmp_path: Path,
) -> None:
    application = request.getfixturevalue('admin_app')
    engine = request.getfixturevalue('admin_engine')
    browser_instance = request.getfixturevalue('browser')
    client, _ = _login(application, engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    from wsgiref.simple_server import make_server
    import threading
    server = make_server('127.0.0.1', 0, application)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with browser_instance.new_context(
            base_url=f'http://127.0.0.1:{server.server_port}',
            java_script_enabled=False,
            reduced_motion='reduce',
        ) as context:
            context.add_cookies([{
                'name': 'session', 'value': cookie.value,
                'domain': '127.0.0.1', 'path': '/', 'httpOnly': True,
            }])
            page = context.new_page()
            page.set_viewport_size({'width': 1440, 'height': 900})
            with engine.connect() as connection:
                actor = connection.execute(text(
                    "SELECT id FROM cafeteria.users "
                    "WHERE public_id='00000000-0000-0000-0000-000000000002'"
                )).scalar_one()
                location = connection.execute(text(
                    'SELECT id FROM cafeteria.locations WHERE active ORDER BY id'
                )).scalar_one()
            food = _insert_location_food(
                engine, actor_id=int(actor), location_id=int(location),
                name=f'Sellerie-{uuid4().hex[:8]}',
            )
            scope_row = connection_scope(engine)
            created = create_component(
                engine, scope_row, 'side', f'NoJS-Karotte-{uuid4().hex[:8]}',
                'CH', 'current', (), (),
            )
            page.goto(f'/admin/patienten/komponenten/{created["public_id"]}')
            expect(page.locator('#c-food')).to_be_visible()
            page.locator('#c-food').select_option(str(food['public_id']))
            page.locator('#component-form').get_by_role('button', name='Speichern', exact=True).click()
            page.wait_for_load_state()
            expect(page.locator('#c-food')).to_have_value(str(food['public_id']))
            page.screenshot(path=str(tmp_path / 'component-food-nojs.png'), full_page=True)
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def connection_scope(engine) -> AdminScope:
    with engine.connect() as connection:
        actor = connection.execute(text(
            "SELECT id, authz_version FROM cafeteria.users "
            "WHERE public_id='00000000-0000-0000-0000-000000000002'"
        )).one()
        location = connection.execute(text(
            'SELECT id FROM cafeteria.locations WHERE active ORDER BY id'
        )).scalar_one()
    return AdminScope(actor.id, int(location), 'patient', actor.authz_version)
