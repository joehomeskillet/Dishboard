"""Group B admin pages use the full working width beside the sidebar."""
from __future__ import annotations

import datetime as dt
import re
from pathlib import Path
from collections.abc import Sequence
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page

from test_admin_workflow_routes import DATABASE_URL, DAY, WEEK, _login, database_engine  # noqa: F401
from test_master_data_routes import create as create_master
from test_recipe_routes import create, fields
from test_rendered_ui import browser  # noqa: F401
from test_ui_master_shell_browser import _page, site  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/ui-fullwidth-0912/b'
WIDE = ((1024, 768), (1440, 900), (1920, 1080), (2560, 1440))
COMPACT = ((390, 844), (720, 450))
VIEWPORTS = COMPACT + WIDE
UUID = r'[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}'
METRICS = '''() => {
  const box = document.querySelector('.page-body > .container-xl')
    || document.querySelector('main.container-fluid')
    || document.querySelector('main');
  const cs = getComputedStyle(box);
  const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
  const inner = box.getBoundingClientRect().width - pad;
  const kids = [...box.children].filter(el => el.getBoundingClientRect().height > 8);
  const primary = Math.max(0, ...kids.map(el => el.getBoundingClientRect().width));
  return {
    inner, primary, ratio: inner ? primary / inner : 0,
    overflow: document.documentElement.scrollWidth > innerWidth + 1,
    maxWidth: cs.maxWidth,
  };
}'''


def _open(page: Page, path: str, allowed: Sequence[int] = (200, 400, 409)) -> object:
    response = page.goto(path, wait_until='networkidle')
    assert response is not None and response.status in allowed, (path, getattr(response, 'status', None))
    page.evaluate('document.fonts.ready')
    return response


def _first(html: str, prefix: str) -> str:
    match = re.search(re.escape(prefix) + '(' + UUID + ')', html)
    assert match, (prefix, html[:800])
    return match.group(1)


def _check(page: Page, endpoint: str, state: str, width: int) -> None:
    metrics = page.evaluate(METRICS)
    assert not metrics['overflow'], (endpoint, state, width, metrics)
    if width >= 1024:
        assert metrics['maxWidth'] in {'none', ''}, (endpoint, state, width, metrics)
        assert metrics['ratio'] >= 0.95, (endpoint, state, width, metrics)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / f'{endpoint}-{state}-{width}.png'), full_page=True)


def _local_user(client) -> str:
    listed = client.get('/admin/benutzer')
    assert listed.status_code == 200, listed.text
    found = re.search(r'/admin/benutzer/(' + UUID + ')', listed.text)
    if found:
        return found.group(1)
    neu = client.get('/admin/benutzer/neu')
    csrf = re.search(r'name="_csrf" value="([^"]+)"', neu.text)
    assert csrf, neu.text[:800]
    created = client.post('/admin/benutzer', data={
        '_csrf': csrf.group(1), 'return_page': '1', 'return_status': 'all',
        'username': 'fullwidth.user', 'display_name': 'Fullwidth Konto',
        'password': 'Valide!Wolken77Kette', 'password_confirm': 'Valide!Wolken77Kette',
        'roles': 'Cafeteria.Editor',
    })
    assert created.status_code == 303, created.text
    return _first(created.headers.get('Location') or created.location, '/admin/benutzer/')


def _pages(client) -> list[tuple[str, str, str]]:
    recipe = urlsplit(create(client, 'Fullwidth A')).path
    frozen = client.post(f'{recipe}/revisionen', data=fields(client, f'{recipe}/revisionen'))
    assert frozen.status_code == 303, frozen.text
    revision = urlsplit(frozen.headers.get('Location', frozen.location)).path
    draft = urlsplit(create(client, 'Fullwidth B')).path
    food = urlsplit(create_master(client, name='Fullwidth Karotte')).path
    unit = urlsplit(create_master(
        client, 'einheiten', display_name='Fullwidth Kilogramm', code='FWKG',
        dimension='mass', base_factor='1',
    )).path
    category = urlsplit(create_master(
        client, 'kategorien', name='Fullwidth Gemüse', code='FWVEG', sort_order='1',
    )).path
    user = _local_user(client)
    copy_week = (WEEK + dt.timedelta(days=7)).isoformat()
    menu = f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
    empty_menu = f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=VEGGIE'
    return [
        ('admin.menu_get', 'default', menu),
        ('admin.menu_get', 'empty', empty_menu),
        ('admin.master_data_list', 'default', '/admin/grundlagen'),
        ('admin.master_data_list', 'empty', '/admin/grundlagen?q=zzzz-fullwidth-empty'),
        ('admin.master_data_detail', 'default', food),
        ('admin.master_data_detail', 'default-unit', unit),
        ('admin.master_data_detail', 'default-category', category),
        ('admin.master_data_new', 'default', '/admin/grundlagen/zutaten/neu'),
        ('admin.master_data_new', 'empty', '/admin/grundlagen/einheiten/neu'),
        ('admin.local_users_list', 'default', '/admin/benutzer'),
        ('admin.local_users_list', 'empty', '/admin/benutzer?status=disabled'),
        ('admin.local_user_new', 'default', '/admin/benutzer/neu'),
        ('admin.local_user_detail', 'default', f'/admin/benutzer/{user}'),
        ('admin.local_user_events', 'default', '/admin/benutzer/protokoll'),
        ('admin.local_user_events', 'empty', '/admin/benutzer/protokoll?page=2'),
        ('admin.access_history', 'default', '/admin/benutzer/zugriffsverlauf'),
        ('admin.access_history', 'empty', '/admin/benutzer/zugriffsverlauf?provider=local&action=auth.logout.requested'),
        ('admin.recipes_list', 'default', '/admin/rezepte'),
        ('admin.recipes_list', 'empty', '/admin/rezepte?q=zzzz-fullwidth-empty'),
        ('admin.recipe_new', 'default', '/admin/rezepte/neu'),
        ('admin.recipe_edit', 'default', recipe),
        ('admin.recipe_revisions', 'default', f'{recipe}/revisionen'),
        ('admin.recipe_revisions', 'empty', f'{draft}/revisionen'),
        ('admin.recipe_revision', 'default', revision),
        ('admin.recipe_images', 'default', f'{recipe}/bilder'),
        ('admin.recipe_images', 'empty', f'{draft}/bilder'),
        ('admin.recipe_scale', 'default', f'{recipe}/skalierung'),
        ('admin.recipe_scale', 'invalid', f'{recipe}/skalierung?yield=nope'),
        ('admin.branding_editor', 'default', '/admin/design/marke'),
        ('admin.branding_preview', 'default', '/admin/design/marke/vorschau/1'),
        ('admin.display_settings', 'default', '/admin/design/darstellung'),
        ('admin.print_template_editor', 'default', f'/admin/vorlagen/cafeteria?week={DAY}'),
        ('admin.recipe_print_template_editor', 'default', '/admin/vorlagen/rezepte'),
        ('admin.api_overview', 'default', '/admin/api'),
        ('admin.copy_get', 'default', f'/admin/cafeteria/copy?week={copy_week}'),
        ('admin.import_preview', 'empty', '/admin/import-preview'),
    ]


def test_group_b_pages_use_full_working_width(site):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    pages = _pages(client)
    for endpoint, state, path in pages:
        probe = client.get(path)
        assert probe.status_code in {200, 400, 409}, (endpoint, state, path, probe.status_code)
    page = _page(site, client, viewport={'width': 1440, 'height': 900})
    try:
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            for endpoint, state, path in pages:
                _open(page, path)
                _check(page, endpoint, state, width)
        page.set_viewport_size({'width': 1440, 'height': 900})
        _open(page, '/admin/benutzer/neu')
        page.fill('#new-username', 'bad.user')
        page.fill('#new-display-name', 'X')
        page.fill('#create-password', 'Valide!Wolken77Kette')
        page.fill('#create-password-confirm', 'Valide!Wolken77Andere')
        page.locator('form.card').evaluate('form => { form.noValidate = true; }')
        page.locator('form.card button[type="submit"]').click()
        page.wait_for_load_state('networkidle')
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate('document.fonts.ready')
            _check(page, 'admin.local_user_new', 'invalid', width)
        _open(page, '/admin/rezepte/neu')
        page.locator('#recipe-editor').evaluate('form => { form.noValidate = true; }')
        page.get_by_role('button', name='Rezept anlegen').click()
        page.wait_for_load_state('networkidle')
        for width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})
            page.evaluate('document.fonts.ready')
            _check(page, 'admin.recipe_new', 'invalid', width)
    finally:
        page.context.close()
