"""Browser verification for MP-UI-MENU-EDITOR (admin.menu_get)."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from wsgiref.simple_server import make_server

import pytest
from playwright.sync_api import Page, expect

from cafeteria import roles
from cafeteria.admin import workflow_routes as routes
from cafeteria.component_catalog_store import create_component, update_component
from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_workflow_routes import DAY, ORIGIN_CONFLICT, WEEK, _login, _payload, _scope
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080)]
LONG_TITLE = 'Traditioneller geschmorter Rindsbraten mit Wurzelgemüse und Rotweinsauce ' * 2


@pytest.fixture(params=['cafeteria', 'patienten'])
def family(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(params=[True, False], ids=['js', 'nojs'])
def javascript(request: pytest.FixtureRequest) -> bool:
    return request.param


def _menu_url(family: str) -> str:
    return f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


@pytest.fixture
def editor_page(request: pytest.FixtureRequest, family: str, javascript: bool):
    application = request.getfixturevalue('admin_app')
    engine = request.getfixturevalue('admin_engine')
    client, user_id = _login(application, engine, ['Cafeteria.Editor'])
    profile = routes.FAMILIES[family]
    scope = _scope(engine, user_id, profile)
    potato = create_component(engine, scope, 'side', 'Kartoffelstock', 'CH', 'common', ['VEGAN'], ())
    payload = _payload(staff=profile == 'staff_guest')
    payload.update(
        title='Herbstteller',
        description='Mit Kräutern',
        note='Ausgabe ab 11:30 Uhr',
        assignments=[
            {'component_public_id': str(potato['public_id']), 'component_text': None},
            {'component_public_id': None, 'component_text': 'Blattsalat'},
        ],
        labels=['VEGETARIAN'],
        allergens=[{'code': 'MILK', 'presence': 'may_contain'}],
    )
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 0)
    cookie = client.get_cookie('session')
    assert cookie is not None
    httpd = make_server('127.0.0.1', 0, application)
    thread = threading.Thread(target=httpd.serve_forever, daemon=True)
    thread.start()
    try:
        with request.getfixturevalue('browser').new_context(
            base_url=f'http://127.0.0.1:{httpd.server_port}',
            java_script_enabled=javascript, reduced_motion='reduce',
            locale='de-CH', timezone_id='Europe/Zurich', device_scale_factor=1,
        ) as context:
            context.add_cookies([{
                'name': 'session', 'value': cookie.value, 'domain': '127.0.0.1',
                'path': '/', 'httpOnly': True,
            }])
            page = context.new_page()
            errors = []
            page.on('pageerror', lambda error: errors.append(str(error)))
            yield page, engine, scope, profile, application, f'http://127.0.0.1:{httpd.server_port}'
            assert not errors, errors
    finally:
        httpd.shutdown()
        httpd.server_close()
        thread.join(timeout=1)


def _open(page: Page, family: str, viewport: tuple[int, int]) -> None:
    page.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
    response = page.goto(_menu_url(family))
    assert response is not None and response.status == 200
    assert response.headers['cache-control'] == 'no-store'
    page.evaluate('document.fonts.ready')


def _tokens(page: Page) -> dict[str, str]:
    form = page.locator('form[data-menu-editor]')
    return {name: form.locator(f'[name="{name}"]').input_value()
            for name in ('_csrf', 'week', 'day', 'meal', 'option', 'row_version')}


def _capture(page: Page, tmp_path: Path, name: str) -> None:
    page.evaluate('document.fonts.ready')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    page.screenshot(path=str(tmp_path / f'{name}.png'), full_page=True)
    evidence = page.evaluate('''() => ({
        viewport: [innerWidth, innerHeight], dpr: devicePixelRatio,
        locale: navigator.language, timezone: Intl.DateTimeFormat().resolvedOptions().timeZone,
        reducedMotion: matchMedia('(prefers-reduced-motion: reduce)').matches,
        bodyFont: getComputedStyle(document.body).fontFamily,
        headingFont: getComputedStyle(document.querySelector('h1')).fontFamily,
        styles: [...document.querySelectorAll('main .btn-primary, main .form-hint, main .field-error, main .form-control, main .form-select')].slice(0, 8).map(e => {
            const s = getComputedStyle(e);
            const hex = color => '#' + color.match(/[\\d.]+/g).slice(0, 3)
                .map(n => Math.round(Number(n)).toString(16).padStart(2, '0')).join('');
            let parent = e;
            while (parent.parentElement && ['transparent', 'rgba(0, 0, 0, 0)'].includes(getComputedStyle(parent).backgroundColor)) parent = parent.parentElement;
            return {id: e.id, disabled: e.disabled || false, color: hex(s.color),
                background: hex(getComputedStyle(parent).backgroundColor), border: hex(s.borderTopColor)};
        })
    })''')
    from cafeteria.branding_config import contrast
    evidence['browser'] = page.context.browser.version
    for style in evidence['styles']:
        style['text_contrast'] = contrast(style['color'], style['background'])
        if not style['disabled']:
            assert style['text_contrast'] >= 4.5, style
    (tmp_path / f'{name}.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')


def _controls(page: Page, family: str, *, component_rows: int | None = 2, require_modes: bool = True) -> None:
    expect(page.locator('main')).to_have_attribute('data-layout', 'standard')
    expect(page.locator('h1')).to_have_count(1)
    expect(page.locator('h1')).to_have_text('Menü bearbeiten')
    expect(page.get_by_role('navigation', name='Breadcrumb')).to_contain_text('Wochenplan')
    expect(page.locator('form[data-menu-editor] .btn-primary')).to_have_count(1)
    expect(page.locator('#sec-components')).to_have_text('Bausteine')
    expect(page.locator('#sec-review')).to_have_text('Angaben prüfen')
    expect(page.locator('#review form[action$="/menu/review"]')).to_have_count(1)
    if family == 'cafeteria':
        expect(page.locator('#f-int')).to_be_visible()
        expect(page.locator('#f-ext')).to_be_visible()
    else:
        expect(page.locator('#f-int')).to_have_count(0)
    sizes = page.locator('form[data-menu-editor] .btn, form[data-menu-editor] .form-control, form[data-menu-editor] .form-select').evaluate_all(
        'es => es.filter(e => e.getClientRects().length).map(e => [e.id, e.getBoundingClientRect().height])'
    )
    assert sizes and all(height >= 48 for _, height in sizes), sizes
    box = page.locator('.page-body > .container-xl')
    viewport = page.viewport_size or {'width': 0}
    if viewport['width'] >= 1024:
        metrics = box.evaluate('''e => {
            const cs = getComputedStyle(e);
            const pad = parseFloat(cs.paddingLeft) + parseFloat(cs.paddingRight);
            const inner = e.getBoundingClientRect().width - pad;
            const kids = [...e.children].filter(el => el.getBoundingClientRect().height > 8);
            const primary = Math.max(0, ...kids.map(el => el.getBoundingClientRect().width));
            return { maxWidth: cs.maxWidth, ratio: inner ? primary / inner : 0 };
        }''')
        assert metrics['maxWidth'] in {'none', ''}, metrics
        assert metrics['ratio'] >= 0.95, metrics
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    if component_rows is not None:
        expect(page.locator('.menu-editor-component-row')).to_have_count(component_rows)
    if require_modes:
        modes = page.evaluate('''() => ({
            enhanced: document.querySelector('form[data-menu-editor]').hasAttribute('data-component-enhanced'),
            catalog: document.querySelectorAll('[data-component-kind-option][value="catalog"]:checked').length,
            text: document.querySelectorAll('[data-component-kind-option][value="text"]:checked').length,
            named: document.querySelectorAll('[data-component-kind-option][name]').length,
        })''')
        assert modes['named'] == 0, modes
        if modes['enhanced']:
            assert modes['catalog'] and modes['text'], modes
        else:
            for control in page.locator('[name="component_public_id"], [name="component_text"]').all():
                expect(control).to_be_visible()


def _keyboard(page: Page) -> None:
    page.locator('#f-title').focus()
    page.keyboard.press('Tab')
    assert page.evaluate('document.activeElement.closest("#components-list") !== null')
    page.locator('#f-desc').focus()
    focus = page.locator('#f-desc').evaluate('''e => ({
        width: getComputedStyle(e).outlineWidth, style: getComputedStyle(e).outlineStyle,
        color: getComputedStyle(e).outlineColor,
        token: getComputedStyle(e).getPropertyValue('--app-focus').trim()
    })''')
    assert focus['width'] == '2px' and focus['style'] == 'solid', focus


def test_menu_editor_states_and_viewports(editor_page, family: str, tmp_path: Path) -> None:
    page, engine, scope, profile, _, _ = editor_page
    for width, height in VIEWPORTS:
        _open(page, family, (width, height))
        _controls(page, family)
        _keyboard(page)
        _capture(page, tmp_path, f'normal-{width}')

    for state, option in (('empty', 'VEGGIE'), ('dense-long', 'MENU_1')):
        payload = _payload(staff=profile == 'staff_guest')
        if state == 'dense-long':
            payload.update(title=LONG_TITLE.strip(), description='Langtext ' * 40)
        else:
            payload.update(
                title='Milchreis',
                assignments=[{'component_public_id': None, 'component_text': 'Milchreis'}],
                labels=[], allergens=[], origins=[],
            )
        persist_menu_item(
            engine, scope, WEEK, DAY, 'LUNCH', option, payload,
            0 if option == 'VEGGIE' else 1,
        )
        url = f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option={option}'
        for width, height in (VIEWPORTS[0], VIEWPORTS[3]):
            page.set_viewport_size({'width': width, 'height': height})
            assert page.goto(url).status == 200
            _controls(page, family, component_rows=1, require_modes=False)
            _keyboard(page)
            if state == 'dense-long':
                expect(page.locator('h1')).to_have_text('Menü bearbeiten')
                expect(page.locator('.page-header-subtitle')).not_to_have_text('')
            _capture(page, tmp_path, f'{state}-{width}')


def test_validation_preserves_inputs_and_tokens(editor_page, family: str, javascript: bool, tmp_path: Path) -> None:
    page, _, _, _, _, _ = editor_page
    for width, height in (VIEWPORTS[0], VIEWPORTS[3]):
        _open(page, family, (width, height))
        tokens = _tokens(page)
        page.locator('#f-title').fill('')
        page.locator('#f-desc').fill('Behalten')
        if javascript:
            page.get_by_role('button', name='Ändern').first.click()
            page.locator('[data-component-kind-option][value="text"]').first.check()
        page.locator('#component-0-text').fill('Freitext behalten')
        with page.expect_response(lambda r: r.request.method == 'POST') as failed:
            page.get_by_role('button', name='Menü speichern', exact=True).click()
        assert failed.value.status == 400
        expect(page.locator('#f-title')).to_have_value('')
        expect(page.locator('#f-desc')).to_have_value('Behalten')
        expect(page.locator('#component-0-text')).to_have_value('Freitext behalten')
        expect(page.locator('.error-region')).to_be_visible()
        page.locator('.error-region a[data-error-link]').first.click()
        expect(page.locator('#f-title')).to_be_focused()
        assert _tokens(page) == tokens
        _capture(page, tmp_path, f'invalid-{width}')


@pytest.mark.parametrize('status', [401, 403])
def test_unauthorized_roles_have_no_menu_form(
    editor_page, family: str, status: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    page, _, _, _, application, _ = editor_page
    _open(page, family, VIEWPORTS[0])
    tokens = _tokens(page)
    if status == 401:
        page.context.clear_cookies()
    else:
        monkeypatch.setattr(roles, 'capabilities', lambda: set())
    path = _menu_url(family)
    for width, height in (VIEWPORTS[0], VIEWPORTS[3]):
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(path)
        assert response is not None and response.status == status
        expect(page.locator('form[data-menu-editor], button[type="submit"]')).to_have_count(0)
        assert page.context.request.post(
            f'/admin/{family}/menu',
            form={**tokens, 'title': 'Verboten', 'allergen_mode': 'manual', 'origin_mode': 'manual', 'label_mode': 'manual'},
        ).status == status
        _capture(page, tmp_path, f'forbidden-{status}-{width}')


def test_origin_conflict_state(editor_page, family: str, tmp_path: Path) -> None:
    page, engine, scope, profile, _, _ = editor_page
    potato = create_component(engine, scope, 'side', 'Kartoffel', 'CH', 'common', (), ())
    rice = create_component(engine, scope, 'side', 'Reis', 'DE', 'current', (), ())
    payload = _payload(staff=profile == 'staff_guest')
    payload.update(origin_mode='auto', origins=[], assignments=[
        {'component_public_id': str(potato['public_id']), 'component_text': None},
        {'component_public_id': str(rice['public_id']), 'component_text': None},
    ])
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 1)
    update_component(engine, scope, str(rice['public_id']), {
        'category': 'side', 'name': 'Kartoffel', 'origin_country_code': 'DE',
        'label_codes': [], 'allergens': [],
    }, int(rice['row_version']))
    for width, height in (VIEWPORTS[0], VIEWPORTS[3]):
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(_menu_url(family))
        assert response is not None and response.status == 409
        expect(page.locator('.error-region')).to_contain_text(ORIGIN_CONFLICT)
        expect(page.locator('form[data-menu-editor]')).to_have_count(1)
        _capture(page, tmp_path, f'origin-conflict-{width}')


def test_zoom200_equivalent(editor_page, family: str, javascript: bool, tmp_path: Path) -> None:
    page, _, _, _, _, base_url = editor_page
    with page.context.browser.new_context(
        base_url=base_url, viewport={'width': 720, 'height': 450},
        device_scale_factor=2, java_script_enabled=javascript, reduced_motion='reduce',
    ) as zoom:
        zoom.add_cookies(page.context.cookies())
        zoom_page = zoom.new_page()
        _open(zoom_page, family, (720, 450))
        _controls(zoom_page, family)
        _keyboard(zoom_page)
        _capture(zoom_page, tmp_path, 'zoom200-equivalent')
