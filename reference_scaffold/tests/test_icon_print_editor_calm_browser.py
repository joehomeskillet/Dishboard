"""Print editors retain native revision/safety flows without duplicate context cards."""
from __future__ import annotations

import base64
import json
import struct
from contextlib import contextmanager
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _login
from test_master_data_db import make_actor
from test_print_template_browser import browser, editor_server  # noqa: F401
from test_print_template_routes import database_engine, editor_app  # noqa: F401
from test_recipe_template_editor_browser import recipe_server  # noqa: F401
from test_recipe_template_editor_routes import (  # noqa: F401
    recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine, example, path,
)


@pytest.fixture
def editor_case(request):
    kind = request.param
    if kind == 'recipes':
        fixture = request.getfixturevalue('recipe_editor')
        app, owner, client, _ = fixture
        recipe, revision, _ = example(fixture)
        return dict(kind=kind, app=app, owner=owner, client=client,
                    server=request.getfixturevalue('recipe_server'),
                    url=path(recipe, revision.public_id, **{'yield': '8'}),
                    label='Rezepte', scope='Rezept-PDFs', recipe=recipe,
                    recipe_revision=revision.public_id)
    app = request.getfixturevalue('editor_app')
    owner = request.getfixturevalue('database_engine')
    client, _ = _login(app, owner, ['Cafeteria.Admin'])
    profile = 'patient' if kind == 'patienten' else 'staff_guest'
    _save(owner, profile, _patient_values() if kind == 'patienten' else _staff_values())
    label = 'Patienten' if kind == 'patienten' else 'Cafeteria'
    return dict(kind=kind, app=app, owner=owner, client=client,
                server=request.getfixturevalue('editor_server'),
                url=f'/admin/vorlagen/{kind}?week={DAY}', label=label,
                scope=label + '-Wochenpläne')


@contextmanager
def _page(playwright_browser, case, tmp_path, width, zoom, javascript, has_touch=False):
    options = dict(base_url=case['server'], java_script_enabled=javascript, reduced_motion='reduce', has_touch=has_touch)
    if zoom == 2:
        context = playwright_browser.browser_type.launch_persistent_context(
            str(tmp_path / 'chrome-profile'), channel='chromium', headless=True, no_viewport=True,
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'], **options,
        )
        page = context.pages[0]
        page.goto('chrome://settings/appearance')
        page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
        assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
    else:
        context = playwright_browser.new_context(viewport={'width': width, 'height': 844 if width == 390 else 900}, **options)
        page = context.new_page()
    cookie = case['client'].get_cookie(case['app'].config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': case['server']}])
    try:
        yield page
    finally:
        context.close()


def _static_section(page, selector, javascript):
    section = page.locator(selector)
    expect(section).to_be_visible()
    expect(section.locator(':scope > summary')).to_have_count(0)
    expect(section.get_by_role('heading').first).to_be_visible()
    assert section.evaluate('el => el.tagName') != 'DETAILS'
    return section

def _form_fields(form, action):
    fields = form.evaluate('f => [...new FormData(f)]')
    names = [name for name, _ in fields]
    expected = {'_csrf', 'action', 'version', 'revision'} | ({'name'} if action == 'copy' else set())
    assert len(names) == len(expected) and set(names) == expected
    values = {name: [value] for name, value in fields}
    assert values['action'] == [action] and values['_csrf'][0]
    assert values['version'][0].isdigit() and values['revision'][0].isdigit()
    return values


def _label_issue(issues, control, expected_text, expected_name):
    actual = {'text': control.inner_text().strip(), 'name': control.get_attribute('aria-label'),
              'tooltip': control.get_attribute('data-ui-tooltip')}
    expected = {'text': expected_text, 'name': expected_name, 'tooltip': expected_name}
    if actual != expected:
        issues.append({'expected': expected, 'actual': actual})


def _capture(page, path, zoom):
    # Viewport evidence preserves coarse-pointer emulation and native zoom.
    page.screenshot(path=str(path), full_page=False)
    session = page.context.new_cdp_session(page)
    try:
        metrics = session.send('Page.getLayoutMetrics')
        layout = page.evaluate('''() => ({url: location.href, innerWidth, innerHeight,
            devicePixelRatio, scrollX, scrollY,
            scrollWidth: document.documentElement.scrollWidth,
            rootZoom: getComputedStyle(document.documentElement).zoom,
            bodyZoom: getComputedStyle(document.body).zoom,
            rootTransform: getComputedStyle(document.documentElement).transform,
            bodyTransform: getComputedStyle(document.body).transform})''')
        evidence = {'requestedZoom': zoom, 'layout': layout, 'cdp': metrics}
        if zoom == 2:
            captured = session.send('Page.captureScreenshot', {
                'format': 'png', 'captureBeyondViewport': False,
            })
            png = base64.b64decode(captured['data'])
            path.with_suffix('.viewport.png').write_bytes(png)
            width, height = struct.unpack('>II', png[16:24])
            evidence['viewportImage'] = {'width': width, 'height': height}
        path.with_suffix('.json').write_text(json.dumps(evidence, indent=2))
        assert abs(metrics['cssVisualViewport']['zoom'] - zoom) < 0.01, evidence
        assert layout['rootZoom'] == layout['bodyZoom'] == '1', evidence
        assert layout['rootTransform'] == layout['bodyTransform'] == 'none', evidence
        assert layout['scrollWidth'] <= layout['innerWidth'] + 1, evidence
        if zoom == 2:
            assert abs(width - layout['innerWidth'] * layout['devicePixelRatio']) <= 2, evidence
            assert abs(height - layout['innerHeight'] * layout['devicePixelRatio']) <= 2, evidence
    finally:
        session.detach()


@pytest.mark.parametrize('editor_case', ['cafeteria', 'patienten', 'recipes'], indirect=True)
@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('width,zoom', [(1440, 1), (390, 1), (1440, 2)])
def test_print_editor_context_disclosures_and_native_archive(
    editor_case, browser, tmp_path, width, zoom, javascript,  # noqa: F811
):
    case = editor_case
    with _page(browser, case, tmp_path, width, zoom, javascript, has_touch=width == 390) as page:
        posts, errors, presentation = [], [], []
        page.on('request', lambda req: posts.append(req) if req.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto(case['url'])
        assert response.status == 200
        assert "script-src 'self'" in response.headers['content-security-policy']
        page.evaluate('document.fonts.ready')
        expect(page.locator('.page-header-subtitle')).to_have_text(case['label'] + ' · Vorlageneditor.')
        navigation = page.locator('#template-select').locator('xpath=ancestor::form')
        expect(page.locator('[data-template-status-scope]')).to_contain_text('Aktiv für ' + case['scope'])
        if case['kind'] == 'recipes':
            expect(page.locator('[data-template-normal-print]')).to_contain_text('Suppe · Stand 1')
        else:
            expect(page.get_by_label('Vorschauwoche ab Montag', exact=True)).to_have_value(DAY)
        prefix = f'{case["kind"]}-{width}-{zoom}x-js{javascript}'
        _capture(page, tmp_path / f'{prefix}-initial.png', zoom)
        for attribute, heading in [('appearance', 'Druckgestaltung'), ('texts', 'Kopf- und Fusszeile')]:
            section = _static_section(page, f'[data-template-{attribute}]', javascript)
            expect(section.get_by_role('heading')).to_have_text(heading)
        page.get_by_label('Vorlagenname', exact=True).fill('Ungespeicherter Vorlagenname')
        page.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Mein Text bleibt erhalten')
        before = page.locator('main form').evaluate_all('forms => forms.map(f => [...new FormData(f)])')
        _static_section(page, '[data-template-activation]', javascript)
        expect(page.locator('[data-semantic="actions.more"]')).to_have_count(0)
        _static_section(page, '[data-template-copy]', javascript)
        expect(page.locator('[data-template-activation]')).to_contain_text('Aktive Druckvorlage')
        expect(page.locator('#template-versions-heading')).to_have_text('Versionen')
        assert page.locator('main form').evaluate_all('forms => forms.map(f => [...new FormData(f)])') == before
        _capture(page, tmp_path / f'{prefix}-opened.png', zoom)
        # Defer only presentation mismatches so RED captures the complete native flow.
        if page.locator('.page-header .admin-statusbar').count():
            presentation.append('Redundant header status cards remain')
        expect(page.locator('#template-activation-heading')).to_have_text('Aktivieren')
        expect(page.locator('#copy-heading')).to_have_text('Vorlage kopieren')
        copy_name = page.get_by_label('Name der Kopie', exact=True)
        copy_name.focus()
        assert copy_name.evaluate('el => getComputedStyle(el).outlineStyle != "none" || getComputedStyle(el).boxShadow != "none"')
        page.keyboard.press('Escape')
        expect(copy_name).to_be_focused()
        expect(page.locator('[data-template-copy]')).to_be_visible()
        assert page.locator('main form').evaluate_all('forms => forms.map(f => [...new FormData(f)])') == before
        assert not posts
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Ungespeicherter Vorlagenname')
        expect(page.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Mein Text bleibt erhalten')
        page.get_by_label('Name der Kopie', exact=True).fill('Kontextkopie')
        copy = page.get_by_role('button', name='Kopie erstellen', exact=True)
        expect(copy).to_have_text('')
        copy_form = copy.locator('xpath=ancestor::form')
        copy_fields = _form_fields(copy_form, 'copy')
        copy_url = copy_form.evaluate('f => new URL(f.getAttribute("action"), f.baseURI).href')
        page.on('dialog', lambda dialog: dialog.accept())
        with page.expect_navigation() as copied:
            copy.click()
        assert copied.value.status == 200 and len(posts) == 1
        assert posts[-1].url == copy_url and parse_qs(posts[-1].post_data) == copy_fields
        expect(page.locator('[data-template-status-scope]')).to_contain_text('Nicht aktiv für ' + case['scope'])
        query = parse_qs(urlsplit(page.url).query)
        assert query['template'] != ['standard']
        if case['kind'] == 'recipes':
            assert query['recipe'] == [case['recipe']] and query['recipe_revision'] == [case['recipe_revision']]
            assert query['yield'] == ['8']
        else:
            assert query['week'] == [DAY]
        # Measure local navigation relative to the shared shell's flash boundary.
        # Global flash text wraps independently and remains outside this consumer.
        page.evaluate('document.fonts.ready')
        navigation_before = navigation.evaluate(
            'el => { const b = el.getBoundingClientRect(), flash = document.querySelector(".flash-region").getBoundingClientRect(); return {x:b.x+scrollX, y:b.y-flash.bottom, width:b.width, height:b.height}; }')
        _static_section(page, '[data-template-lifecycle]', javascript)
        confirm = page.get_by_label('Ich möchte diese Vorlage archivieren.', exact=True)
        archive = page.get_by_role('button', name='Vorlage archivieren', exact=True)
        _label_issue(presentation, archive, 'Archivieren', 'Vorlage archivieren')
        archive_form = page.locator('#archive-form')
        archive_fields = _form_fields(archive_form, 'archive')
        archive_url = archive_form.evaluate('f => new URL(f.getAttribute("action"), f.baseURI).href')
        assert confirm.evaluate('el => el.form.id === "archive-form" && !el.closest("form")')
        archive.click()
        expect(confirm).to_be_focused()
        assert confirm.evaluate('el => el.validity.valueMissing') and len(posts) == 1
        _capture(page, tmp_path / f'{prefix}-confirmation.png', zoom)
        confirm.check()
        with page.expect_navigation():
            archive.click()
        assert len(posts) == 2
        assert posts[-1].url == archive_url and parse_qs(posts[-1].post_data) == archive_fields
        page.evaluate('document.fonts.ready')
        navigation_after = navigation.evaluate(
            'el => { const b = el.getBoundingClientRect(), flash = document.querySelector(".flash-region").getBoundingClientRect(); return {x:b.x+scrollX, y:b.y-flash.bottom, width:b.width, height:b.height}; }')
        assert all(abs(navigation_after[key] - value) <= 1 for key, value in navigation_before.items()), (navigation_before, navigation_after)
        expect(page.get_by_label('Vorlagenname', exact=True)).to_be_disabled()
        expect(page.get_by_text('Diese Vorlage ist archiviert.', exact=False)).to_be_visible()
        _static_section(page, '[data-template-lifecycle]', javascript)
        restore_form = page.locator('form').filter(has=page.locator('input[name="action"][value="reactivate"]'))
        restore = restore_form.locator('button[type="submit"]')
        _label_issue(presentation, restore, 'Reaktivieren', 'Druckvorlage Kontextkopie reaktivieren')
        if case['kind'] == 'recipes' and width == 1440 and zoom == 1 and javascript:
            case['app'].config['UI_LOCALE'] = 'en'
            page.reload(wait_until='networkidle')
            _static_section(page, '[data-template-lifecycle]', javascript)
            _label_issue(presentation, restore, 'Reactivate', 'Reactivate print template Kontextkopie')
            _capture(page, tmp_path / f'{prefix}-reactivate-en.png', zoom)
            case['app'].config['UI_LOCALE'] = 'de'
            page.reload(wait_until='networkidle')
            _static_section(page, '[data-template-lifecycle]', javascript)
        restore_fields = _form_fields(restore_form, 'reactivate')
        restore_url = restore_form.evaluate('f => new URL(f.getAttribute("action"), f.baseURI).href')
        expect(page.get_by_text('ohne sie für den Druck zu aktivieren.', exact=False)).to_be_visible()
        _capture(page, tmp_path / f'{prefix}-archived.png', zoom)
        with page.expect_navigation():
            restore.click()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_be_enabled()
        assert len(posts) == 3
        assert posts[-1].url == restore_url and parse_qs(posts[-1].post_data) == restore_fields
        expect(page.locator('[data-template-status-scope]')).to_contain_text('Nicht aktiv für ' + case['scope'])
        _static_section(page, '[data-template-activation]', javascript)
        activate_form = page.locator('[data-template-activation] form')
        activate = activate_form.locator('button[type="submit"]')
        activate_name = 'Revision 1 prüfen und aktivieren' if case['kind'] == 'recipes' else 'Diese Version aktivieren'
        _label_issue(presentation, activate, 'Aktivieren', activate_name)
        if page.locator('[data-template-activation]').get_by_role('heading', name='Aktivieren', exact=True).count() != 1:
            presentation.append('Activation confirmation has no readable section heading')
        activate_fields = _form_fields(activate_form, 'activate')
        activate_url = activate_form.evaluate('f => new URL(f.getAttribute("action"), f.baseURI).href')
        _capture(page, tmp_path / f'{prefix}-activation.png', zoom)
        with page.expect_navigation():
            activate.click()
        assert len(posts) == 4 and not errors
        assert posts[-1].url == activate_url and parse_qs(posts[-1].post_data) == activate_fields
        expect(page.locator('[data-template-status-scope]')).to_contain_text('Aktiv für ' + case['scope'])
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        _capture(page, tmp_path / f'{prefix}-active.png', zoom)
        (tmp_path / f'{prefix}-presentation.json').write_text(json.dumps(presentation, ensure_ascii=False, indent=2))
        assert not presentation, presentation


@pytest.mark.parametrize('editor_case', ['cafeteria', 'patienten', 'recipes'], indirect=True)
@pytest.mark.parametrize('javascript', [True, False])
def test_print_editor_coarse_controls_preserve_native_forms(
    editor_case, browser, tmp_path, javascript,  # noqa: F811
):
    case = editor_case
    with _page(browser, case, tmp_path, 390, 1, javascript, has_touch=True) as page:
        posts, errors, measurements, failures = [], [], [], []
        page.on('request', lambda req: posts.append(req) if req.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto(case['url'])
        assert response.status == 200
        page.evaluate('document.fonts.ready')
        page.get_by_label('Vorlagenname', exact=True).fill('Touch-Entwurf bleibt erhalten')
        _static_section(page, '[data-template-texts]', javascript)
        page.get_by_label('Zusatz unter dem Kopfbereich', exact=True).fill('Touch-Zusatz bleibt erhalten')
        forms = page.locator('main form')
        form_state = '''forms => forms.map(f => ({
            action: f.getAttribute('action'), method: f.getAttribute('method'),
            fields: [...new FormData(f)]
        }))'''
        before = forms.evaluate_all(form_state)
        copy_form = page.locator('[data-template-copy] form').filter(
            has=page.locator('input[name="action"][value="copy"]'),
        )
        copy_before = _form_fields(copy_form, 'copy')
        selectors = ('[data-template-activation]', '[data-template-copy]')
        for selector in selectors:
            _static_section(page, selector, javascript)
        copy_name = page.get_by_label('Name der Kopie', exact=True)
        for stage in ('initial', 'focused', 'escaped'):
            if stage == 'focused':
                copy_name.focus()
            elif stage == 'escaped':
                page.keyboard.press('Escape')
                expect(copy_name).to_be_focused()
            for selector in selectors:
                _static_section(page, selector, javascript)
            copy_name.scroll_into_view_if_needed()
            for moment in ('before-capture', 'after-capture'):
                if moment == 'after-capture':
                    page.screenshot(path=str(tmp_path / f'{case["kind"]}-coarse-{stage}.png'), full_page=False)
                state = page.evaluate('''() => ({
                    pointerCoarse: matchMedia('(pointer: coarse)').matches,
                    anyPointerCoarse: matchMedia('(any-pointer: coarse)').matches,
                    pointerFine: matchMedia('(pointer: fine)').matches,
                    maxTouchPoints: navigator.maxTouchPoints, innerWidth, innerHeight,
                    scrollWidth: document.documentElement.scrollWidth,
                    controls: [...document.querySelectorAll('main .ui-sem-control--icon-only')]
                        .filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden')
                        .map(el => ({tag: el.tagName, name: el.getAttribute('aria-label'),
                            semantic: el.getAttribute('data-semantic'),
                            width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height}))
                })''')
                measurements.append({'stage': stage, 'moment': moment, 'state': state})
                (tmp_path / 'coarse-controls.json').write_text(json.dumps(measurements, ensure_ascii=False, indent=2))
                assert state['pointerCoarse'] and state['anyPointerCoarse'] and not state['pointerFine'], state
                assert state['maxTouchPoints'] > 0 and state['innerWidth'] == 390, state
                assert state['scrollWidth'] <= state['innerWidth'] + 1, state
                assert state['controls'], state
                for control in state['controls']:
                    assert control['name'], control
                    if (control['width'], control['height']) != (44, 44):
                        failures.append({'stage': stage, 'moment': moment, 'control': control})
            assert forms.evaluate_all(form_state) == before
            assert _form_fields(copy_form, 'copy') == copy_before
            expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Touch-Entwurf bleibt erhalten')
            expect(page.get_by_label('Zusatz unter dem Kopfbereich', exact=True)).to_have_value('Touch-Zusatz bleibt erhalten')
            assert not posts and not errors
        assert not failures, failures


@pytest.mark.parametrize('editor_case', ['cafeteria', 'patienten', 'recipes'], indirect=True)
@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher'])
@pytest.mark.parametrize('width,javascript', [(390, False), (1440, True)])
def test_print_editor_reduced_roles_keep_existing_denial(editor_case, browser, tmp_path, role, width, javascript):  # noqa: F811
    case = editor_case
    if case['kind'] == 'recipes':
        actor = make_actor(case['owner'], role)
        client = case['app'].test_client()
        with client.session_transaction() as session:
            session['user'] = {'id': actor.user_id, 'name': 'Lesende Person'}
            session['authz_version'] = actor.authz_version
    else:
        client, _ = _login(case['app'], case['owner'], [role])
    with _page(browser, case | {'client': client}, tmp_path, width, 1, javascript) as page:
        assert page.goto(case['url']).status == 403
        expect(page.locator('[data-template-properties], [data-template-activation], #archive-form')).to_have_count(0)
        page.screenshot(path=str(tmp_path / f'{case["kind"]}-{role}-{width}-denied.png'), full_page=True)
