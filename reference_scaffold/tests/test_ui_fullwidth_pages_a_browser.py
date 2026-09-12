"""MP-UI-FULLWIDTH-AUDIT Gruppe A: Listen, Wochen, Bildschirme, Betrieb."""
from __future__ import annotations

import threading
from pathlib import Path

import pytest
from sqlalchemy import text
from werkzeug.serving import make_server

from cafeteria import recipe_store as store
from cafeteria.auth.local_users import ActorExpectation
from cafeteria.component_catalog_store import create_component
from cafeteria.screen_templates import key
from test_admin_workflow_db import WEEK_START
from test_admin_workflow_routes import DATABASE_URL, _login, _scope, database_engine  # noqa: F401
from test_master_data_db import signed_in
from test_recipe_store_db import payload as recipe_payload
from test_rendered_ui import browser  # noqa: F401
from test_screen_template_routes import screen_app  # noqa: F401
from test_ui_output_hubs_browser import published_hub_app  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'ui-fullwidth-0912' / 'a'
DESKTOP = ((1024, 768), (1440, 900), (1920, 1080), (2560, 1440))
COMPACT = ((390, 844), (720, 450))
WIDTH_METRICS = '''() => {
  const shell = document.querySelector('.page-body > .container-xl');
  const standalone = document.querySelector('main.container-xl, main.container-fluid');
  const box = shell || standalone;
  if (!box) return {error: 'no container'};
  const cs = getComputedStyle(box);
  const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
  const inner = box.getBoundingClientRect().width - pad;
  const blocks = [...box.querySelectorAll(
    ':scope > .card, :scope > .row, :scope > .screens-grid, :scope > .cookbook-cards, :scope > .menu-grid, :scope > section, :scope > form.card, :scope > h2 + .row'
  )].filter(el => el.getBoundingClientRect().width > 0);
  const primary = blocks.length
    ? Math.max(...blocks.map(el => el.getBoundingClientRect().width))
    : inner;
  return {
    inner,
    primary,
    ratio: primary / inner,
    overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
  };
}'''


@pytest.fixture
def fullwidth_site(published_hub_app, database_engine, browser):  # noqa: F811
    app = published_hub_app
    client, user_id = _login(app, database_engine, ['Cafeteria.Admin'])
    scope = _scope(database_engine, user_id, 'staff_guest')
    component = create_component(
        database_engine, scope, 'side', 'Kartoffelstock', 'CH', 'current', ['VEGAN'], [],
    )
    with database_engine.connect() as connection:
        authz = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': user_id},
        ).scalar_one()
    actor = ActorExpectation(user_id, int(authz))
    with signed_in(database_engine, actor):
        location = store.get_location(database_engine)
        cookbook = store.create_cookbook(
            database_engine, actor, name='Probebuch', expected_location_id=location,
        )
        store.create_recipe(
            database_engine, actor, recipe_payload(title='Testrezept'), expected_location_id=location,
        )
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    origin = f'http://127.0.0.1:{server.server_port}'
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    try:
        yield {
            'origin': origin,
            'cookie': cookie,
            'component_id': str(component['public_id']),
            'cookbook_id': cookbook.public_id,
        }
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


def _page(browser, site, width: int, height: int):  # noqa: F811
    context = browser.new_context(
        base_url=site['origin'], viewport={'width': width, 'height': height},
        locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
    )
    context.add_cookies([{
        'name': site['cookie'].key, 'value': site['cookie'].value, 'url': site['origin'],
    }])
    return context, context.new_page()


def _assert_width(page, name: str, width: int, height: int):
    metrics = page.evaluate(WIDTH_METRICS)
    assert 'error' not in metrics, (name, width, metrics)
    assert not metrics['overflow'], (name, width, height, metrics)
    if width >= 1024:
        assert metrics['ratio'] >= 0.95, (name, width, metrics)


def _shot(page, endpoint: str, state: str, width: int, height: int):
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(
        path=str(EVIDENCE / f'{endpoint}-{state}-{width}x{height}.png'),
        full_page=True,
    )


def test_group_a_pages_use_full_working_width(fullwidth_site, browser):  # noqa: F811
    site = fullwidth_site
    week = WEEK_START.isoformat()
    routes = (
        ('bereiche-zeiten', 'normal', '/admin/bereiche-zeiten'),
        ('screens', 'normal', '/admin/screens'),
        ('vorlagen', 'normal', '/admin/vorlagen'),
        ('wochenvorlage', 'normal', '/admin/screens/cafeteria/wochenvorlage'),
        ('wochen', 'normal', '/admin/cafeteria/wochen'),
        ('wochenpruefung', 'normal', f'/admin/cafeteria/wochen/pruefung?week={week}'),
        ('menues', 'normal', '/admin/cafeteria/menues'),
        ('komponenten', 'normal', '/admin/cafeteria/komponenten'),
        ('komponente', 'normal', f'/admin/cafeteria/komponenten/{site["component_id"]}'),
        ('kochbuecher', 'normal', '/admin/kochbuecher'),
        ('kochbuch-neu', 'normal', '/admin/kochbuecher/neu'),
        ('kochbuch-edit', 'normal', f'/admin/kochbuecher/{site["cookbook_id"]}'),
        ('cafeteria', 'referenz', '/admin/cafeteria'),
        ('patienten', 'referenz', '/admin/patienten'),
    )
    for width, height in DESKTOP + COMPACT:
        context, page = _page(browser, site, width, height)
        try:
            for endpoint, state, path in routes:
                response = page.goto(path)
                assert response is not None and response.status == 200, (endpoint, path, response)
                _assert_width(page, endpoint, width, height)
                _shot(page, endpoint, state, width, height)
        finally:
            context.close()


def test_screen_template_unavailable_uses_full_width(fullwidth_site, database_engine, browser):  # noqa: F811
    site = fullwidth_site
    bad_value = (
        '{"schema_version": 999, "version": 0, '
        '"template_id": "cafeteria-week-text", "renderer_revision": 1}'
    )
    with database_engine.begin() as connection:
        connection.execute(
            text(
                'INSERT INTO cafeteria.settings (location_id, profile_id, setting_key, setting_value) '
                'VALUES (NULL, NULL, :k, CAST(:v AS jsonb)) '
                'ON CONFLICT (location_id, profile_id, setting_key) '
                'DO UPDATE SET setting_value = EXCLUDED.setting_value'
            ),
            {'k': key('staff_guest'), 'v': bad_value},
        )
    for width, height in DESKTOP + COMPACT:
        context, page = _page(browser, site, width, height)
        try:
            response = page.goto('/admin/screens/cafeteria/wochenvorlage')
            assert response is not None and response.status == 503
            metrics = page.evaluate(WIDTH_METRICS)
            assert not metrics['overflow'], (width, metrics)
            if width >= 1024:
                assert metrics['ratio'] >= 0.95, (width, metrics)
            _shot(page, 'wochenvorlage', 'unavailable-503', width, height)
        finally:
            context.close()
