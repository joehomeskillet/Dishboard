from __future__ import annotations

import importlib.util
import sys
from pathlib import Path
from unittest.mock import MagicMock
from urllib.parse import urlsplit

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))
SPEC = importlib.util.spec_from_file_location('capture_admin_live_proof', ROOT / 'tools/capture_admin_live_proof.py')
assert SPEC is not None and SPEC.loader is not None
capture_tool = importlib.util.module_from_spec(SPEC)
SPEC.loader.exec_module(capture_tool)
BASE = 'https://dishboard.example.invalid'


@pytest.mark.parametrize('content', [
    'CHF12', '12CHF', 'CHF 12', '12 CHF', 'chf', 'chf12.50', '12.50cHf',
    'CHF\u00a012.50', '12\u202fCHF', 'Preiselbeeren CHF12',
    'Preis', 'Preise', 'Menüpreis', 'Preisangaben', 'price', 'prices', 'Kosten', 'Rappen',
    '<input type="hidden" name="internal_rappen" value="1200">',
    '<input name="external_rappen">', '<input name="internalPrice">',
    '<input name="preis_intern">', '<div class="price-row"></div>',
    '<div data-chf="12"></div>', '<div data-price="12">Preiselbeeren</div>',
])
def test_patient_price_guard_rejects_currency_vocabulary_and_structural_fields(content: str) -> None:
    assert capture_tool.PATIENT_PRICE_VOCABULARY.search(content) is not None


@pytest.mark.parametrize('content', [
    'Milchfreiheit', 'Milchfrei', 'MILCHFREIHEIT prüfen', 'Fleischfond',
    'Preiselbeeren', 'PREISELBEEREN', 'Preiselbeere', 'Preiselbeerkompott',
    '<main><p>Milchfreiheit prüfen; Fleischfond und Preiselbeeren.</p></main>',
])
def test_patient_price_guard_accepts_food_names_and_notes(content: str) -> None:
    assert capture_tool.PATIENT_PRICE_VOCABULARY.search(content) is None


@pytest.mark.parametrize('fault', [None, 'empty_query', 'empty_weeks', 'http_500', 'wrong_profile', 'missing_nav', 'wrong_row_scope', 'missing_row_links', 'food_note', 'berries', 'patient_price'])
def test_planning_pages_are_required_even_when_legacy_workflow_fails(tmp_path: Path, fault: str | None, monkeypatch) -> None:
    # Real Tabler behavior/assets are exercised by test_capture_admin_tabler_browser.py.
    monkeypatch.setattr(capture_tool, 'audit_tabler', lambda *_: {})
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
    content = {
        'food_note': 'Milchfreiheit prüfen; Fleischfond enthalten.',
        'berries': 'Preiselbeeren mit Preiselbeerkompott',
        'patient_price': 'CHF12.50',
    }.get(fault or '', 'Menüplanung')
    page.content.return_value = f'<html><main>{content}</main></html>'

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
    if fault in (None, 'empty_query', 'empty_weeks', 'food_note', 'berries'):
        assert failures == []
        assert all(proof['checks'].values())
    elif fault == 'patient_price':
        assert set(failures) == {
            f'desktop.patienten.{section}.no_price_vocabulary' for section in ('menus', 'weeks')
        }
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


@pytest.mark.parametrize(('fault', 'failed_check'), [
    ('legacy_css', 'no_legacy_app_css'), ('duplicate_js', 'one_tabler_no_extra_bootstrap'),
    ('bootstrap', 'one_tabler_no_extra_bootstrap'), ('external', 'local_assets_http_200'),
    ('http_404', 'local_assets_http_200'),
])
def test_tabler_asset_audit_rejects_legacy_duplicate_external_and_missing_assets(fault, failed_check):
    from admin_tabler_proof import audit_tabler
    page = MagicMock()
    styles = ['/static/tokens.css', '/static/vendor/tabler/tabler.min.css',
              '/static/admin-tabler.css', '/static/menu-images.css']
    scripts = ['/static/vendor/tabler/tabler.min.js', '/static/admin.js']
    if fault == 'legacy_css':
        styles.append('/static/app.css')
    elif fault == 'duplicate_js':
        scripts.append(scripts[0])
    elif fault == 'bootstrap':
        scripts.append('/static/bootstrap.bundle.min.js')
    elif fault == 'external':
        styles.append('https://other.example.invalid/theme.css')
    def locator(selector):
        result = MagicMock()
        result.count.return_value = 1
        result.is_visible.return_value = True
        result.evaluate_all.return_value = styles if selector.startswith('link') else scripts
        result.evaluate.return_value = True
        return result
    page.locator.side_effect = locator
    page.get_by_role.return_value.is_visible.return_value = False
    page.evaluate.return_value = 1440
    page.request.get.return_value.status = 404 if fault == 'http_404' else 200
    result = audit_tabler(page, BASE, {})
    assert result[failed_check] is False
    assert all(call.args[0].startswith(BASE + '/static/') for call in page.request.get.call_args_list)
