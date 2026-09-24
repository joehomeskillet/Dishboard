"""Native Gerichtvorlagen pages at the UI-master viewports."""
from __future__ import annotations

import json
import os
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria.branding_config import contrast
from test_dish_template_routes import COLUMNS, create, fields, make_recipe, snapshot
from test_recipe_freeze_v2_browser import proof
from test_recipe_link_reads_db import seed_recipe_page
from test_master_data_browser import master_server, targets  # noqa: F401
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_rendered_ui import browser  # noqa: F401

EVIDENCE = Path(os.environ.get(
    'DISH_TEMPLATE_EVIDENCE_DIR', str(Path(__file__).resolve().parents[2] / '.claude/evidence/acc-template-0913'),
))
ROUTE_VIEWPORTS = ((360, 800), (390, 844), (1440, 900))
SHARED_VIEWPORTS = ((1024, 768), (768, 1024), (1920, 1080), (2560, 1440))


@pytest.mark.parametrize('width', [360, 390, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_rework_layout_measurements(b3, master_server, browser, width, javascript):  # noqa: F811
    _, owner, client, actor = b3
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 900},
                             java_script_enabled=javascript, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        measurements = {}
        console_errors = []
        page.on('console', lambda message: console_errors.append(message.text) if message.type == 'error' else None)
        routes = [('empty', '/admin/gerichtvorlagen'), ('new', '/admin/gerichtvorlagen/neu')]
        for state, route in routes:
            _open(page, base, route)
            measurements[state] = _rework_measure(page, state, width)
            if state == 'new':
                expect(page.locator('[name="recipe_search"]')).to_be_visible()
                expect(page.get_by_role('button', name='Rezepte suchen')).to_be_visible()
        path = create(client, title='Messvorlage', menu_type_code='MENU_1', profile_scope='common')
        for state, route in [('list', '/admin/gerichtvorlagen'), ('editor', path),
                             ('planning', path + '/einplanen')]:
            _open(page, base, route)
            measurements[state] = _rework_measure(page, state, width)
            if state == 'editor':
                expect(page.locator('.admin-statusbar')).to_contain_text('Aktiv')
                expect(page.locator('.admin-statusbar')).to_contain_text('Gemeinsam')
                expect(page.locator('.admin-statusbar')).to_contain_text('Fehlt')
            if state == 'planning':
                summary = page.locator('#planning-summary')
                expect(summary).to_be_visible()
                expect(summary).to_contain_text('Messvorlage')
                page.get_by_label('Menüart', exact=True).select_option('VEGGIE')
                if not javascript:
                    page.get_by_role('button', name='Ziel aktualisieren').click()
                expect(summary).to_contain_text('Vegetarisch')
                for name in ('area', 'meal', 'option'):
                    selected = page.locator(f'#planning-target [name="{name}"] option:checked').inner_text()
                    expect(summary).to_contain_text(selected)
        recipe = make_recipe(owner, actor)
        linked = create(client, title='Rezeptvorlage', recipe_public_id=recipe.public_id)
        _open(page, base)
        measurements['linked-list'] = _rework_measure(page, 'linked-list', width)
        _open(page, base, linked)
        measurements['linked-editor'] = _rework_measure(page, 'linked-editor', width)
        expect(page.locator('.admin-statusbar')).to_contain_text('Gebunden')
        expect(page.locator('.admin-statusbar')).to_contain_text('Gebundenes Rezept')
        data = fields(client, path)
        data['action'] = 'archive'
        assert client.post(path, data=data).status_code == 303
        _open(page, base)
        expect(page.get_by_role('link', name='Messvorlage', exact=True)).to_have_count(0)
        page.get_by_label('Archivierte einschliessen').check()
        expect(page.get_by_role('link', name='Messvorlage', exact=True)).to_have_count(0)
        page.get_by_role('button', name='Filtern', exact=True).click()
        expect(page.get_by_role('link', name='Messvorlage', exact=True)).to_be_visible()
        assert 'archived=1' in page.url
        _open(page, base, path)
        expect(page.locator('.admin-statusbar')).to_contain_text('Archiviert')
        measurements['archived-editor'] = _rework_measure(page, 'archived-editor', width)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / f'rework-{width}-js-{javascript}.json').write_text(json.dumps(measurements, indent=2))
        for state, result in measurements.items():
            assert result['primary'] == 1, (state, result)
            assert result['scrollWidth'] <= width, (state, result)
            if width == 1440:
                assert all(height <= 96 for height in result['rows']), (state, result)
            for control in result['controls']:
                assert control['width'] >= 48 and control['height'] >= 48, (state, control)
        assert not console_errors, console_errors


def _rework_measure(page, state, width):
    expect(page.get_by_role('heading', level=1)).to_have_text('Gerichtvorlagen')
    expect(page).to_have_title('Gerichtvorlagen · Menüplanung')
    result = page.locator('main').evaluate('''main => {
        const visible = e => e.getClientRects().length && getComputedStyle(e).visibility !== 'hidden';
        const controls = [...main.querySelectorAll('a, button, input:not([type=hidden]), select, textarea')]
            .filter(visible).map(e => {
                const target = ['checkbox', 'radio'].includes(e.type) ? e.closest('label') || e : e;
                const r = target.getBoundingClientRect();
                return {name: e.getAttribute('aria-label') || e.textContent.trim() || e.name,
                    width: r.width, height: r.height};
            });
        return {viewport: innerWidth, scrollWidth: document.documentElement.scrollWidth,
            primary: main.querySelectorAll('.btn-primary').length,
            rows: [...main.querySelectorAll('tbody tr')].map(e => e.getBoundingClientRect().height),
            controls};
    }''')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / f'rework-{state}-{width}.png'), full_page=True)
    return result


def _open(context_page, base, path='/admin/gerichtvorlagen'):
    page = context_page
    page.goto(base + path)
    page.evaluate('document.fonts && document.fonts.ready')
    return page


def _accessible_capture(page, name, *, methods, native=False):
    """Record measured contrast after exercising the real focus styles."""
    pairs = page.locator('main a, main .btn, main .form-label, main .form-hint, main .text-secondary').evaluate_all(r'''els => {
        const hex = value => '#' + value.match(/[\d.]+/g).slice(0, 3)
            .map(n => Math.round(Number(n)).toString(16).padStart(2, '0')).join('');
        return els.filter(e => e.getClientRects().length).map(e => {
            let parent = e;
            while (parent.parentElement && ['transparent', 'rgba(0, 0, 0, 0)'].includes(getComputedStyle(parent).backgroundColor)) parent = parent.parentElement;
            return {text: e.textContent.trim(), color: hex(getComputedStyle(e).color),
                background: hex(getComputedStyle(parent).backgroundColor)};
        });
    }''')
    assert pairs
    for pair in pairs:
        pair['contrast'] = contrast(pair['color'], pair['background'])
        assert pair['contrast'] >= 4.5, pair
    page.evaluate('document.activeElement.blur(); scrollTo({top: 0, left: 0, behavior: "instant"})')
    page.wait_for_function('scrollY === 0 && scrollX === 0')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    (EVIDENCE / f'{name}.contrast.json').write_text(json.dumps(pairs, ensure_ascii=False, indent=2))
    proof(page, EVIDENCE / f'{name}.png', expected_status=200, requests=methods, native_capture=native)


@pytest.mark.parametrize('width,height', ROUTE_VIEWPORTS)
@pytest.mark.parametrize('javascript', [False, True])
def test_list_create_conflict_and_tabler(b3, master_server, browser, width, height, javascript, tmp_path):  # noqa: F811
    _, owner, client, _ = b3
    base, cookie = master_server
    with browser.new_context(
        viewport={'width': width, 'height': height}, java_script_enabled=javascript,
        reduced_motion='reduce', service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('dialog', lambda dialog: dialog.accept())
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        _open(page, base)
        expect(page.get_by_role('heading', level=1)).to_have_text('Gerichtvorlagen')
        for column in COLUMNS:
            expect(page.get_by_role('columnheader', name=column)).to_have_count(0)
        expect(page.get_by_text('Noch keine Gerichtvorlagen')).to_be_visible()
        page.get_by_role('link', name='Vorlage anlegen').click()
        expect(page.get_by_role('heading', level=1)).to_have_text('Gerichtvorlagen')
        expect(page.locator('.page-header')).to_contain_text('Vorlage anlegen')
        targets(page)
        _accessible_capture(page, f'new-{width}-js-{javascript}', methods=['GET'])
        page.get_by_label('Titel', exact=True).fill('Browser Vorlage')
        page.get_by_label('Menüart').select_option('MENU_1')
        page.get_by_label('Geltungsbereich').select_option('common')
        page.get_by_role('button', name='Speichern').click()
        expect(page.get_by_role('link', name='Browser Vorlage')).to_be_visible()
        for column in COLUMNS:
            if width >= 768:
                expect(page.get_by_role('columnheader', name=column)).to_be_visible()
            else:
                expect(page.locator(f'table.admin-table--stack [data-label="{column}"]').first).to_be_visible()
        expect(page.get_by_text('Menü 1', exact=True)).to_be_visible()
        expect(page.get_by_text('Gemeinsam', exact=True)).to_be_visible()
        if width < 768:
            assert page.locator('table.admin-table--stack tbody tr').first.evaluate(
                "e => getComputedStyle(e).display") == 'grid'
        expect(page.locator('.badge:visible').filter(has_text='Aktiv')).to_have_count(1)
        page.get_by_role('link', name='Browser Vorlage').click()
        expect(page.get_by_label('Status', exact=True)).to_be_visible()
        expect(page.get_by_label('Status', exact=True).locator('dt').filter(has_text='Status')).to_be_visible()
        expect(page.get_by_label('Status', exact=True).locator('dd').filter(has_text='Aktiv')).to_be_visible()
        expect(page.get_by_label('Status', exact=True).locator('dt').filter(has_text='Bereich')).to_be_visible()
        expect(page.get_by_label('Status', exact=True).locator('dd').filter(has_text='Gemeinsam')).to_be_visible()
        path = urlsplit(page.url).path
        token = page.locator('input[name="updated_at"]').input_value()
        assert fields(client, path)['updated_at'] == token
        stale_title = page.get_by_label('Titel', exact=True)
        data = fields(client, path)
        data['title'] = 'Andere Sitzung'
        assert client.post(path, data=data).status_code == 303
        stale_title.fill('Mein ursprünglicher Entwurf')
        with page.expect_response(lambda response: response.request.method == 'POST') as outcome:
            page.get_by_role('button', name='Speichern').click()
        assert outcome.value.status == 409
        expect(page.locator('#dish-template-error')).to_be_visible()
        expect(page.get_by_label('Titel', exact=True)).to_have_value('Mein ursprünglicher Entwurf')
        page.get_by_role('link', name='Aktuellen Stand neu laden').click()
        expect(page.get_by_label('Titel', exact=True)).to_have_value('Andere Sitzung')
        targets(page)
        assets = page.locator('link[rel="stylesheet"]').evaluate_all(
            'els => els.map(el => new URL(el.href).pathname)')
        assert any('tabler' in asset and asset.endswith('.css') for asset in assets)
        assert page.locator('main style, main [style]').count() == 0
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        EVIDENCE.chmod(0o700)
        shot = EVIDENCE / f'gerichtvorlagen-{width}-js-{javascript}.png'
        page.screenshot(path=str(shot), full_page=True)
        shot.chmod(0o600)
        expected_conflict = 'Failed to load resource: the server responded with a status of 409 (CONFLICT)'
        assert all(error == expected_conflict for error in errors)
        assert snapshot(owner)['dish_templates']


@pytest.mark.parametrize('width,height', ROUTE_VIEWPORTS)
@pytest.mark.parametrize('javascript', [False, True])
def test_accompaniment_radio_is_native_keyboard_operable_and_visible(
    b3, master_server, browser, width, height, javascript,  # noqa: F811
):
    _, _, _, _ = b3
    base, cookie = master_server
    with browser.new_context(
        viewport={'width': width, 'height': height}, java_script_enabled=javascript,
        locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + '/admin/gerichtvorlagen/neu').status == 200
        group = page.get_by_role(
            'group', name='Suppe oder Salat dazu (Vorschlag für neue Menüs)', exact=True,
        )
        expect(group).to_be_visible()
        none = page.get_by_role('radio', name='Keine', exact=True)
        soup = page.get_by_role('radio', name='Suppe', exact=True)
        salad = page.get_by_role('radio', name='Salat (gemischt und grün)', exact=True)
        expect(none).to_be_checked()
        for code in ('none', 'soup', 'salad'):
            bounds = page.locator(
                f'label.form-check:has(input[name="accompaniment_default"][value="{code}"])',
            ).bounding_box()
            assert bounds and bounds['height'] >= 48, bounds
        none.focus()
        page.keyboard.press('ArrowRight')
        expect(soup).to_be_checked()
        page.keyboard.press('ArrowRight')
        expect(salad).to_be_checked()
        page.get_by_label('Titel', exact=True).fill(f'Tastatur Salat {width} {javascript}')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        EVIDENCE.chmod(0o700)
        form_shot = EVIDENCE / f'accompaniment-form-{width}x{height}-js-{javascript}.png'
        page.screenshot(path=str(form_shot), full_page=True)
        form_shot.chmod(0o600)
        with page.expect_navigation(wait_until='load'):
            page.get_by_role('button', name='Speichern', exact=True).click()
        if width >= 768:
            expect(page.get_by_role('columnheader', name='Dazu', exact=True)).to_be_visible()
        else:
            expect(page.locator('td[data-label="Dazu"]').filter(has_text='Salat')).to_be_visible()
        expect(page.locator('use[href$="#tabler-salad"]')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        shot = EVIDENCE / f'accompaniment-{width}x{height}-js-{javascript}.png'
        page.screenshot(path=str(shot), full_page=True)
        shot.chmod(0o600)


@pytest.mark.parametrize('width,height', ROUTE_VIEWPORTS)
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('read_only', [False, True])
def test_recipe_link_search_and_retained_selection_without_data_loss(
    b3, master_server, browser, monkeypatch, width, height, javascript, read_only,  # noqa: F811
):
    from cafeteria import roles
    _, owner, client, actor = b3
    ids = seed_recipe_page(owner, actor)
    path = create(client, title='Verknüpfte Vorlage', recipe_public_id=ids[-1])
    if read_only:
        # No built-in reader role exists; exercise draft.read without draft.write.
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': height}, java_script_enabled=javascript,
                             locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors = []
        methods = []
        page.on('request', lambda request: methods.append(request.method))
        page.on('pageerror', lambda error: errors.append(str(error)))
        _open(page, base)
        _accessible_capture(page, f'list-{width}-js-{javascript}-reader-{read_only}', methods=methods.copy())
        link = page.get_by_role('link', name='Rezept: Rezept 205', exact=True)
        link.focus()
        expect(link).to_be_focused()
        assert link.evaluate('el => getComputedStyle(el).outlineStyle !== "none" || getComputedStyle(el).boxShadow !== "none"')
        with page.expect_navigation(wait_until='load') as navigation:
            page.keyboard.press('Enter')
        assert navigation.value.status == 200 and urlsplit(page.url).path == '/admin/rezepte/' + ids[-1] + '/ansicht'
        expect(page.get_by_text('Entwurf · nicht festgeschrieben', exact=True)).to_be_visible()
        assert page.goto(base + path).status == 200
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        if read_only:
            expect(page.locator('main button[name="action"]')).to_have_count(0)
            expect(page.get_by_role('link', name='Rezept: Rezept 205', exact=True)).to_be_visible()
        else:
            selected = page.get_by_label('Gebundenes Rezept', exact=True)
            expect(selected).to_have_value(ids[-1])
            expect(selected.locator('option:checked')).to_contain_text('Aktuelle Auswahl')
            token = page.locator('[name="updated_at"]').input_value()
            page.get_by_label('Titel', exact=True).fill('')
            page.get_by_label('Beschreibung', exact=True).fill('Ungespeicherte Beschreibung')
            page.get_by_label('Rezept nach Titel suchen', exact=True).fill('001')
            before = snapshot(owner)
            with page.expect_response(lambda response: response.request.method == 'POST') as response:
                page.get_by_role('button', name='Rezepte suchen', exact=True).click()
            assert response.value.status == 200 and '_csrf' not in page.url
            expect(page.get_by_label('Titel', exact=True)).to_have_value('')
            expect(page.get_by_label('Beschreibung', exact=True)).to_have_value('Ungespeicherte Beschreibung')
            expect(page.locator('[name="updated_at"]')).to_have_value(token)
            expect(page.get_by_label('Gebundenes Rezept', exact=True)).to_have_value(ids[-1])
            assert snapshot(owner) == before
            page.get_by_label('Rezept nach Titel suchen', exact=True).fill('')
            page.get_by_role('button', name='Rezepte suchen', exact=True).click()
            page.get_by_role('button', name='Weitere Rezepte', exact=True).click()
            expect(page.get_by_text('Seite 2', exact=True)).to_be_visible()
            expect(page.get_by_label('Gebundenes Rezept', exact=True)).to_have_value(ids[-1])
            expect(page.locator('[name="updated_at"]')).to_have_value(token)
            assert snapshot(owner) == before
            page.get_by_label('Titel', exact=True).fill('Gespeicherte Zuordnung')
            page.get_by_role('button', name='Speichern', exact=True).click()
            expect(page.get_by_label('Titel', exact=True)).to_have_value('Gespeicherte Zuordnung')
            expect(page.get_by_label('Gebundenes Rezept', exact=True)).to_have_value(ids[-1])
        targets(page)
        _accessible_capture(page, f'link-form-{width}-js-{javascript}-reader-{read_only}', methods=methods.copy())
        assert not errors


def test_link_pages_native_200_percent_zoom_and_320_reflow(b3, master_server, browser, tmp_path):  # noqa: F811
    _, owner, client, actor = b3
    ids = seed_recipe_page(owner, actor)
    path = create(client, title='Zoom Vorlage', recipe_public_id=ids[-1])
    base, cookie = master_server
    before = snapshot(owner)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='dish-native-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(profile, channel='chromium', headless=True,
                no_viewport=True, locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
                args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900']) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            for label, route in [('list', '/admin/gerichtvorlagen'), ('form', path), ('new', '/admin/gerichtvorlagen/neu')]:
                assert page.goto(base + route).status == 200
                assert page.evaluate('devicePixelRatio') == 2 and page.evaluate('innerWidth') == 720
                targets(page)
                _accessible_capture(page, f'{label}-native-200-percent', methods=['GET'], native=True)
    with browser.new_context(viewport={'width': 320, 'height': 844}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        for label, route in [('list', '/admin/gerichtvorlagen'), ('form', path)]:
            assert page.goto(base + route).status == 200
            targets(page)
            _accessible_capture(page, f'{label}-reflow-320', methods=['GET'])
    assert snapshot(owner) == before


@pytest.mark.parametrize('width,height', SHARED_VIEWPORTS)
def test_shared_layout_viewports(b3, master_server, browser, width, height, tmp_path):  # noqa: F811
    _, _, client, _ = b3
    create(client, title=f'Liste {width}')
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        _open(page, base)
        expect(page.get_by_role('heading', level=1)).to_have_text('Gerichtvorlagen')
        for column in COLUMNS:
            expect(page.get_by_role('columnheader', name=column)).to_be_visible()
        targets(page)
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        _accessible_capture(page, f'gerichtvorlagen-shared-{width}x{height}', methods=['GET'])
        page.get_by_role('link', name=f'Liste {width}', exact=True).click()
        targets(page)
        _accessible_capture(page, f'gerichtvorlagen-form-{width}', methods=['GET'])


def test_p3_polish_dish_templates_primary_stack_hint(b3, master_server, browser):  # noqa: F811
    _, _, client, _ = b3
    path = create(client, title='Polish Vorlage', menu_type_code='MENU_1', profile_scope='common')
    base, cookie = master_server
    with browser.new_context(viewport={'width': 360, 'height': 800}, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        _open(page, base)
        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        stacked = page.locator('table.admin-table--stack tbody tr').first
        assert stacked.evaluate("e => getComputedStyle(e).display") == 'grid'
        expect(page.locator('td[data-label="Menüart"]').first).to_be_visible()
        _open(page, base, path)
        expect(page.locator('#accompaniment-hint')).to_be_visible()
        expect(page.locator('#recipe-search-hint')).to_be_visible()
        _open(page, base, path + '/einplanen')
        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
        plan_hint = page.locator('summary[aria-describedby="planning-refresh-hint"]')
        plan_hint.focus()
        expect(plan_hint).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('#planning-refresh-hint')).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
