"""Admin shell uses the full working width beside the sidebar on every page."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest

from test_admin_workflow_routes import DATABASE_URL, DAY, _login, database_engine  # noqa: F401
from test_recipe_routes import create, fields
from test_rendered_ui import browser  # noqa: F401
from test_ui_master_shell_browser import _goto, _page, site  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

DESKTOP = ((1280, 900), (1440, 900), (1920, 900), (2560, 900))
COMPACT = ((390, 844), (720, 450))  # 720x450 = 1440x900 at 200% zoom.
SHELL_METRICS = '''() => {
  const main = document.querySelector('main.admin-main');
  const box = document.querySelector('.page-body > .container-xl');
  const cs = getComputedStyle(box);
  const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
  const containers = [...document.querySelectorAll(
    '.admin-page-header .container-xl, .admin-area-tabs > .container-xl, .page-body > .container-xl'
  )].map(el => el.getBoundingClientRect());
  return {
    maxWidth: cs.maxWidth,
    contentWidth: box.getBoundingClientRect().width - pad,
    expected: main.clientWidth - pad,
    overflow: document.documentElement.scrollWidth > innerWidth + 1,
    edges: containers.map(rect => ({x: rect.x, width: rect.width})),
  };
}'''


def _revision_path(client) -> str:
    recipe_path = urlsplit(create(client)).path
    list_path = f'{recipe_path}/revisionen'
    response = client.post(list_path, data=fields(client, list_path))
    assert response.status_code == 303, response.text
    return urlsplit(response.location).path


def test_admin_pages_use_full_working_width(site, tmp_path: Path):  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    routes = (
        ('darstellung', '/admin/design/darstellung'),
        ('menues', '/admin/cafeteria/menues'),
        ('cafeteria', '/admin/cafeteria'),
        ('rezeptversion', _revision_path(client)),
        ('menueditor', f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'),
    )
    page = _page(site, client, viewport={'width': 1440, 'height': 900})
    try:
        for width, height in DESKTOP:
            page.set_viewport_size({'width': width, 'height': height})
            for name, path in routes:
                _goto(page, path)
                metrics = page.evaluate(SHELL_METRICS)
                assert metrics['maxWidth'] == 'none', (name, width, metrics)
                assert abs(metrics['contentWidth'] - metrics['expected']) <= 1, (name, width, metrics)
                assert not metrics['overflow'], (name, width, metrics)
                xs = [edge['x'] for edge in metrics['edges']]
                widths = [edge['width'] for edge in metrics['edges']]
                assert len(xs) >= 2, (name, path, metrics['edges'])
                assert max(xs) - min(xs) <= 1, (name, width, metrics['edges'])
                assert max(widths) - min(widths) <= 1, (name, width, metrics['edges'])
                page.screenshot(
                    path=str(tmp_path / f'fullwidth-{name}-{width}x{height}.png'),
                    full_page=True,
                )
        for width, height in COMPACT:
            page.set_viewport_size({'width': width, 'height': height})
            for name, path in routes:
                _goto(page, path)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'), (
                    name, width, height,
                )
                page.screenshot(
                    path=str(tmp_path / f'fullwidth-{name}-{width}x{height}.png'),
                    full_page=True,
                )
    finally:
        page.context.close()
