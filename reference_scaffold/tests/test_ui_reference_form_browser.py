"""Live component-form reference; screenshots are proposals in pytest tmp_path."""
from __future__ import annotations

import json
import threading
from pathlib import Path
from urllib.parse import parse_qs
from wsgiref.simple_server import make_server

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

from cafeteria.admin import workflow_routes as routes
from cafeteria import roles
from cafeteria.branding_config import contrast
from cafeteria.component_catalog_store import (
    ComponentCatalogConfigurationError,
    create_component,
    get_component,
    update_component,
)
from test_admin_workflow_routes import _login, _scope
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

VIEWPORTS = [(1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080)]
LONG_NAME = 'Ofengemüse mit Karotten, Zucchetti und frischen Kräutern ' * 3


@pytest.fixture(params=['cafeteria', 'patienten'])
def family(request: pytest.FixtureRequest) -> str:
    return request.param


@pytest.fixture(params=[True, False], ids=['js', 'nojs'])
def javascript(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture
def reference(request: pytest.FixtureRequest, family: str, javascript: bool):
    application = request.getfixturevalue('admin_app')
    engine = request.getfixturevalue('admin_engine')
    client, user_id = _login(application, engine, ['Cafeteria.Editor'])
    scope = _scope(engine, user_id, routes.FAMILIES[family])
    row = create_component(
        engine, scope, 'side', 'Kartoffelstock', 'CH', 'current',
        ['VEGAN'], [('MILK', 'may_contain')],
    )
    cookie = client.get_cookie('session')
    assert cookie is not None
    server = make_server('127.0.0.1', 0, application)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        with request.getfixturevalue('browser').new_context(
            base_url=f'http://127.0.0.1:{server.server_port}',
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
            yield page, engine, scope, str(row['public_id']), application
            assert not errors, errors
    finally:
        server.shutdown()
        server.server_close()
        thread.join(timeout=1)


def _open(page: Page, family: str, public_id: str, viewport: tuple[int, int]) -> None:
    page.set_viewport_size({'width': viewport[0], 'height': viewport[1]})
    response = page.goto(f'/admin/{family}/komponenten/{public_id}')
    assert response is not None and response.status == 200
    assert response.headers['cache-control'] == 'no-store'
    page.evaluate('document.fonts.ready')


def _tokens(page: Page) -> dict[str, str]:
    form = page.locator('#component-form')
    return {name: form.locator(f'[name="{name}"]').input_value()
            for name in ('_csrf', 'row_version')}


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
        fonts: [...document.fonts].filter(f => f.status === 'loaded').map(f => f.family),
        styles: [...document.querySelectorAll('main .btn-primary, main .form-hint, main .field-error, main .form-control, main .form-select')].map(e => {
            const s = getComputedStyle(e);
            const hex = color => '#' + color.match(/[\\d.]+/g).slice(0, 3)
                .map(n => Math.round(Number(n)).toString(16).padStart(2, '0')).join('');
            let parent = e;
            while (parent.parentElement && ['transparent', 'rgba(0, 0, 0, 0)'].includes(getComputedStyle(parent).backgroundColor)) parent = parent.parentElement;
            return {id: e.id, disabled: e.disabled || false, color: hex(s.color),
                background: hex(getComputedStyle(parent).backgroundColor), border: hex(s.borderTopColor)};
        })
    })''')
    evidence['browser'] = page.context.browser.version
    for style in evidence['styles']:
        style['text_contrast'] = contrast(style['color'], style['background'])
        if not style['disabled']:
            assert style['text_contrast'] >= 4.5, style
    (tmp_path / f'{name}.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')


def _controls(page: Page) -> None:
    expect(page.locator('main')).to_have_attribute('data-layout', 'narrow')
    expect(page.locator('h1')).to_have_count(1)
    expect(page.get_by_role('navigation', name='Breadcrumb')).to_contain_text('Komponenten')
    expect(page.locator('main .btn-primary')).to_have_count(1)
    expect(page.locator('#component-form [readonly]')).to_have_count(0)
    sizes = page.locator('main .btn, main .form-control, main .form-select, main .form-check').evaluate_all(
        'es => es.filter(e => e.getClientRects().length).map(e => [e.id, e.getBoundingClientRect().height])'
    )
    assert sizes and all(height >= 48 for _, height in sizes), sizes
    labels = page.locator('#component-form input:not([type="hidden"]), #component-form select').evaluate_all(
        'es => es.map(e => [e.id, [...e.labels].some(l => l.textContent.trim())])'
    )
    assert all(labelled for _, labelled in labels), labels
    assert page.locator('.page-body > .container-xl').evaluate('e => e.getBoundingClientRect().width') <= 960
    assert page.locator('#component-form .card-footer').evaluate('e => getComputedStyle(e).position') == 'static'
    for field_id in ('c-name', 'c-cat'):
        expect(page.locator(f'label[for="{field_id}"]')).to_have_class('form-label required')
    expect(page.locator('#c-origin')).not_to_have_attribute('required', '')


def _keyboard(page: Page) -> None:
    page.locator('#c-name').focus()
    page.keyboard.press('Tab')
    expect(page.locator('#c-cat')).to_be_focused()
    focus = page.locator('#c-cat').evaluate('''e => ({
        width: getComputedStyle(e).outlineWidth, style: getComputedStyle(e).outlineStyle,
        color: getComputedStyle(e).outlineColor,
        token: getComputedStyle(e).getPropertyValue('--app-focus').trim()
    })''')
    assert focus['width'] == '2px' and focus['style'] == 'solid', focus
    page.keyboard.press('Tab')
    expect(page.locator('#c-origin')).to_be_focused()


def test_reference_states_and_viewports(reference, family: str, tmp_path: Path) -> None:
    page, engine, scope, public_id, _ = reference
    for width, height in VIEWPORTS:
        _open(page, family, public_id, (width, height))
        _controls(page)
        _keyboard(page)
        expect(page.locator('#edit-presence-MILK')).to_have_value('may_contain')
        expect(page.locator('#edit-presence-GLUTEN')).to_be_disabled()
        _capture(page, tmp_path, f'normal-{width}')

    # Empty means optional metadata is empty; a component name is always required.
    for state in ('empty', 'dense-long'):
        with engine.begin() as connection:
            allergens = connection.execute(text('SELECT code FROM cafeteria.allergens ORDER BY code')).scalars().all()
            if state == 'dense-long':
                connection.execute(text("UPDATE cafeteria.allergens SET display_name=display_name || ' mit ausführlicher Deklaration und vollständigem Pflichttext'"))
        current = get_component(engine, scope, public_id, include_archived=True)
        update_component(engine, scope, public_id, {
            'name': LONG_NAME if state == 'dense-long' else 'Kartoffelstock',
            'category': 'side', 'origin_country_code': None,
            'label_codes': ['VEGAN'] if state == 'dense-long' else [],
            'allergens': [(code, 'contains') for code in allergens] if state == 'dense-long' else [],
        }, current['row_version'])
        for width, height in (VIEWPORTS[0], VIEWPORTS[3]):
            _open(page, family, public_id, (width, height))
            _controls(page)
            _keyboard(page)
            if state == 'dense-long':
                expect(page.locator('h1')).to_have_text(LONG_NAME.strip())
                assert page.locator('#component-form .form-check-label').evaluate_all(
                    'es => es.every(e => e.scrollWidth <= e.clientWidth + 1 && e.scrollHeight <= e.clientHeight + 1)'
                )
            else:
                expect(page.locator('#component-form input:checked')).to_have_count(0)
                expect(page.locator('#c-origin')).to_have_value('')
            _capture(page, tmp_path, f'{state}-{width}')

    # Browser zoom equivalent: half CSS viewport and DPR 2 preserve screen size.
    with page.context.browser.new_context(
        base_url=page.url, viewport={'width': 720, 'height': 450},
        device_scale_factor=2, java_script_enabled=False, reduced_motion='reduce',
    ) as zoom:
        zoom.add_cookies(page.context.cookies())
        zoom_page = zoom.new_page()
        _open(zoom_page, family, public_id, (720, 450))
        _controls(zoom_page)
        _keyboard(zoom_page)
        _capture(zoom_page, tmp_path, 'zoom200-equivalent')


def test_validation_preserves_inputs_tokens_and_native_submit(
    reference, family: str, javascript: bool, tmp_path: Path,
) -> None:
    page, engine, scope, public_id, _ = reference
    for width, height in (VIEWPORTS[0], VIEWPORTS[3]):
        _open(page, family, public_id, (width, height))
        before = get_component(engine, scope, public_id, include_archived=True)
        tokens = _tokens(page)
        page.locator('#c-name').fill('   ')
        page.locator('#c-origin').select_option('AT')
        with page.expect_response(lambda r: r.request.method == 'POST') as failed:
            page.get_by_role('button', name='Speichern', exact=True).press('Enter')
        assert failed.value.status == 400
        expect(page.locator('#c-name')).to_have_value('   ')
        expect(page.locator('#c-origin')).to_have_value('AT')
        expect(page.locator('#edit-label-VEGAN')).to_be_checked()
        expect(page.locator('#edit-allergen-MILK')).to_be_checked()
        expect(page.locator('#edit-presence-MILK')).to_have_value('may_contain')
        expect(page.locator('#c-name')).to_have_attribute('aria-invalid', 'true')
        expect(page.locator('#c-name')).to_have_attribute('aria-describedby', 'c-name-error')
        if javascript:
            expect(page.locator('#c-name')).to_be_focused()
        else:
            page.locator('.error-region a[href="#c-name"]').click()
            expect(page.locator('#c-name')).to_be_focused()
        assert _tokens(page) == tokens
        assert get_component(engine, scope, public_id, include_archived=True) == before
        _capture(page, tmp_path, f'invalid-{width}')
        page.locator('#c-name').fill(f'Gespeichert {width}')
        with page.expect_response(lambda r: r.request.method == 'POST') as saved:
            page.get_by_role('button', name='Speichern', exact=True).click()
        assert saved.value.status == 303
        payload = parse_qs(saved.value.request.post_data)
        assert all(payload[key] == [value] for key, value in tokens.items())
        assert payload['allergen_code'] == ['MILK']
        assert payload['allergen_presence'] == ['may_contain']
        expect(page.locator('h1')).to_have_text(f'Gespeichert {width}')
        result = get_component(engine, scope, public_id, include_archived=True)
        assert result['row_version'] == before['row_version'] + 1
        assert result['origin_country_code'] == 'AT'


@pytest.mark.parametrize('status', [409, 503])
def test_write_rejections_keep_abort_contract(
    reference, family: str, status: int, tmp_path: Path, monkeypatch: pytest.MonkeyPatch,
) -> None:
    page, engine, scope, public_id, _ = reference
    for width, height in (VIEWPORTS[0], VIEWPORTS[3]):
        _open(page, family, public_id, (width, height))
        tokens = _tokens(page)
        if status == 409:
            with engine.begin() as connection:
                connection.execute(text('UPDATE cafeteria.menu_components SET row_version=row_version+1 WHERE public_id=:id'), {'id': public_id})
        else:
            def unavailable(*_args):
                raise ComponentCatalogConfigurationError('Testweise nicht verfügbar.')
            monkeypatch.setattr(routes, 'update_component', unavailable)
        before = get_component(engine, scope, public_id, include_archived=True)
        page.locator('#c-name').fill('Ungespeicherter Entwurf')
        with page.expect_response(lambda r: r.request.method == 'POST') as rejected:
            page.get_by_role('button', name='Speichern', exact=True).click()
        assert rejected.value.status == status
        payload = parse_qs(rejected.value.request.post_data)
        assert all(payload[key] == [value] for key, value in tokens.items())
        expect(page.locator('#component-form')).to_have_count(0)
        assert get_component(engine, scope, public_id, include_archived=True) == before
        _capture(page, tmp_path, f'abort-{status}-{width}')


@pytest.mark.parametrize('status', [401, 403])
def test_unauthorized_roles_have_no_form_or_submit(
    reference, family: str, tmp_path: Path, status: int, monkeypatch: pytest.MonkeyPatch,
) -> None:
    page, engine, scope, public_id, application = reference
    _open(page, family, public_id, VIEWPORTS[0])
    tokens = _tokens(page)
    before = get_component(engine, scope, public_id, include_archived=True)
    if status == 401:
        page.context.clear_cookies()
    else:
        # Existing roles all pair draft.read with draft.write. Exercise the real
        # decorator's 403 branch with a test-only empty capability set.
        monkeypatch.setattr(roles, 'capabilities', lambda: set())
    path = f'/admin/{family}/komponenten/{public_id}'
    for width, height in (VIEWPORTS[0], VIEWPORTS[3]):
        page.set_viewport_size({'width': width, 'height': height})
        response = page.goto(path)
        assert response is not None and response.status == status
        expect(page.locator('form, button[type="submit"]')).to_have_count(0)
        assert page.context.request.post(path, form={**tokens, 'name': 'Verboten', 'category': 'side'}).status == status
        _capture(page, tmp_path, f'forbidden-{status}-{width}')
    assert get_component(engine, scope, public_id, include_archived=True) == before
