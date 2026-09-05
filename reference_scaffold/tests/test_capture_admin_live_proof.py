from __future__ import annotations

import importlib.util
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
SPEC = importlib.util.spec_from_file_location('capture_admin_live_proof', ROOT / 'tools/capture_admin_live_proof.py')
assert SPEC is not None and SPEC.loader is not None
capture_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture_tool)
BASE = 'https://dishboard.example.invalid'


@pytest.mark.parametrize('fault', [None, 'empty_query', 'empty_weeks', 'http_500', 'wrong_profile', 'missing_nav', 'wrong_row_scope', 'missing_row_links'])
def test_planning_pages_are_required_even_when_legacy_workflow_fails(tmp_path: Path, fault: str | None) -> None:
    browser = MagicMock()
    context = browser.new_context.return_value.__enter__.return_value
    page = context.new_page.return_value
    context.pages = [page]
    response = MagicMock(status=200)
    response.header_value.return_value = "script-src 'self'"

    def goto(url: str, **kwargs):
        page.url = url
        path = urlsplit(url).path
        if path == '/auth/local':
            return response
        if path.endswith(('/menues', '/wochen')):
            return MagicMock(status=500, header_value=response.header_value) if fault == 'http_500' else response
        raise RuntimeError('legacy_workflow_unavailable_in_mock')

    page.goto.side_effect = goto
    page.get_by_role.return_value.click.side_effect = lambda: setattr(page, 'url', f'{BASE}/admin/cafeteria')
    page.evaluate.return_value = {
        'inline_scripts': 0, 'inline_handlers': 0, 'inline_styles': 0,
        'overflow_px': 0, 'controls_below_44px': 0,
    }
    page.content.return_value = '<html><main>Menüplanung</main></html>'

    def screenshot(path: str, **kwargs) -> bytes:
        data = b'mocked screenshot, no browser launched'
        Path(path).write_bytes(data)
        return data

    page.screenshot.side_effect = screenshot

    def locator(selector: str):
        result = MagicMock()
        family = 'patienten' if '/patienten/' in page.url else 'cafeteria'
        profile = 'patient' if family == 'patienten' else 'staff_guest'
        result.count.return_value = 0 if selector == 'input[type="password"]' else 1
        if selector == 'main.admin-main':
            result.get_attribute.return_value = 'wrong' if fault == 'wrong_profile' else profile
        if selector.startswith('nav[aria-label="Profil"]'):
            result.get_attribute.return_value = urlsplit(page.url).path
            if fault == 'empty_query' and page.url.endswith('/menues'):
                result.get_attribute.return_value += '?q='
        if fault == 'missing_nav' and selector.startswith('a[href='):
            result.count.return_value = 0
        row_family = 'patienten' if fault == 'wrong_row_scope' and family == 'cafeteria' else family
        if selector == '.menu-card a[href]':
            raise AssertionError('Tabler rows need data attribute selectors')
        result.evaluate_all.return_value = [f'/admin/{row_family}/menu?week=2026-08-31']
        if fault == 'missing_row_links':
            result.evaluate_all.return_value = []
            if ':has(a[href])' in selector:
                result.count.return_value = 0
        if fault == 'empty_weeks' and page.url.endswith('/wochen') and selector.startswith('[data-'):
            result.count.return_value = 0
            result.evaluate_all.return_value = []
        result.locator.side_effect = locator
        return result

    page.locator.side_effect = locator
    proof = {'checks': {}, 'pages': [], 'catalogs': {}, 'unavailable': [], 'failures': []}
    capture_tool.capture_viewport(browser, BASE, tmp_path, 'desktop', 'synthetic-test-password', proof)
    expected = {
        f'desktop.{family}.{section}'
        for family in ('cafeteria', 'patienten') for section in ('menus', 'weeks')
    }
    assert {item['name'] for item in proof['pages']} == expected
    assert proof['unavailable'] == []
    for name in expected:
        assert f'{name}.http_200' in proof['checks']
        assert f'{name}.profile' in proof['checks']
        assert f'{name}.nav_current' in proof['checks']
    failures = [name for name in proof['failures'] if '.overview.' not in name]
    if fault in (None, 'empty_query', 'empty_weeks'):
        assert failures == []
        assert all(proof['checks'].values())
    else:
        suffix = {
            'http_500': 'http_200', 'wrong_profile': 'profile',
            'missing_nav': 'nav_current', 'wrong_row_scope': 'row_scope',
            'missing_row_links': 'row_links',
        }[fault]
        assert f'desktop.cafeteria.weeks.{suffix}' in failures
    assert page.goto.call_count == 7  # Login, all four planning pages, two legacy overviews.
    page.get_by_role.return_value.click.assert_called_once()  # Only login is clicked.


@pytest.mark.parametrize('href,expected', [
    ('/admin/cafeteria/menues', True),
    ('/admin/cafeteria/menues?q=', True),
    (BASE + '/admin/cafeteria/menues?q=', True),
    ('https://other.example.invalid/admin/cafeteria/menues?q=', False),
    ('/admin/patienten/menues?q=', False),
    ('/admin/cafeteria/menues?profile=patient', False),
    ('/admin/cafeteria/menues?q=rice', False),
    ('/admin/cafeteria/menues?q=&q=', False),
    ('/admin/cafeteria/menues#other', False),
    (None, False),
])
def test_profile_tab_only_accepts_same_route_and_empty_search(href, expected):
    assert capture_tool._profile_tab_matches(href, BASE, '/admin/cafeteria/menues') is expected
