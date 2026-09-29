"""Direct recipe actions retain localized names, exact revisions and native targets."""
from __future__ import annotations

import base64
import json
from urllib.parse import urlsplit
from tempfile import TemporaryDirectory

import pytest
from playwright.sync_api import expect

from test_recipe_images_browser import recipe_server  # noqa: F401
from test_recipe_revision_routes import (  # noqa: F401
    a3, app_engine, b3, complete_a3, edit, fields, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import snapshot
from test_rendered_ui import browser  # noqa: F401
from test_dish_template_routes import create as create_template, fields as template_fields, snapshot as template_snapshot
from cafeteria import roles


@pytest.mark.parametrize('width', [1440, 1280, 1024, 768, 390, 320])
@pytest.mark.parametrize('locale', ['de', 'en'])
def test_recipe_direct_actions_geometry_and_native_navigation(
    a3, recipe_server, browser, tmp_path, width, locale,  # noqa: F811
):
    app, owner, _, _, public_id = a3
    app.config['UI_LOCALE'] = locale
    complete_a3(a3)
    title = 'Apfelmus'
    edit(a3, title=title)
    before = snapshot(owner)
    base, cookie = recipe_server
    coarse = width < 768
    with browser.new_context(viewport={'width': width, 'height': 844 if coarse else 900},
                             has_touch=coarse, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + '/admin/rezepte', wait_until='networkidle').status == 200
        row = page.locator('.recipe-row').filter(has_text=title)
        actions = row.locator('.admin-row-actions [data-semantic]')
        assert actions.evaluate_all('(els) => els.map(el => el.dataset.semantic)') == [
            'actions.open', 'actions.edit', 'actions.open_pdf', 'actions.history',
            'actions.snapshot', 'actions.create_template',
        ]
        expect(row.locator('details, [data-semantic="actions.more"]')).to_have_count(0)
        height = row.bounding_box()['height']
        boxes = []
        for action in actions.all():
            expect(action).to_be_visible()
            expect(action).to_have_text('')
            assert action.get_attribute('aria-label')
            box = action.bounding_box()
            size = 44 if coarse else 36
            assert box['width'] == size and box['height'] == size, box
            assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1, box
            boxes.append(box)
            if not action.is_disabled():
                action.hover()
                assert abs(row.bounding_box()['height'] - height) <= 1
                action.focus()
                assert abs(row.bounding_box()['height'] - height) <= 1
                action.press('Escape')
        for index, box in enumerate(boxes):
            for other in boxes[index + 1:]:
                assert (box['x'] + box['width'] <= other['x'] or
                        other['x'] + other['width'] <= box['x'] or
                        box['y'] + box['height'] <= other['y'] or
                        other['y'] + other['height'] <= box['y'])
        if width == 1440:
            assert 48 <= height <= 56, height
            assert max(box['y'] for box in boxes) - min(box['y'] for box in boxes) <= 1
        pdf = row.locator('[data-semantic="actions.open_pdf"]')
        expect(pdf).to_be_disabled()
        expect(pdf).to_have_accessible_description('Noch kein gespeicherter Stand vorhanden')
        expect(pdf).not_to_have_attribute('href', '.*')
        page.mouse.move(0, 0)
        page.screenshot(path=str(tmp_path / f'rezepte-publisher-{locale}-{width}.png'))
        with context.expect_page() as opened:
            row.locator('[data-semantic="actions.open"]').click(modifiers=['Control'])
        tab = opened.value
        tab.wait_for_load_state()
        expect(tab).to_have_url(base + f'/admin/rezepte/{public_id}/ansicht')
        expect(tab.locator('#recipe-document')).to_be_visible()
        tab.close()
        destinations = [
            ('actions.open', f'/admin/rezepte/{public_id}/ansicht'),
            ('actions.edit', f'/admin/rezepte/{public_id}'),
            ('actions.history', f'/admin/rezepte/{public_id}/revisionen'),
            ('actions.snapshot', f'/admin/rezepte/{public_id}/revisionen#recipe-freeze'),
            ('actions.create_template', f'/admin/gerichtvorlagen/neu?recipe={public_id}'),
        ]
        for key, destination in destinations:
            action = row.locator(f'[data-semantic="{key}"]')
            expect(action).to_have_attribute('href', destination)
            action.focus()
            with page.expect_navigation(wait_until='networkidle') as navigation:
                action.press('Enter')
            assert navigation.value.status == 200
            assert page.url == base + destination
            page.goto(base + '/admin/rezepte', wait_until='networkidle')
        assert snapshot(owner) == before


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('has_revision', [False, True])
def test_recipe_more_actions_use_localized_names_and_exact_revision(
    a3, recipe_server, browser, tmp_path, locale, has_revision,  # noqa: F811
):
    app, owner, client, _, public_id = a3
    app.config['UI_LOCALE'] = locale
    title = 'Suppe "A" & Kräuter'
    edit(a3, title=title)
    complete_a3(a3)  # Complete draft permits History GET200 without freezing a revision.
    assert not snapshot(owner)['recipe_revisions']
    root = f'/admin/rezepte/{public_id}'
    history = root + '/revisionen'
    if has_revision:
        first = client.post(history, data=fields(client, history))
        assert first.status_code == 303
        edit(a3, description='Zweiter gespeicherter Stand')
        second = client.post(history, data=fields(client, history))
        assert second.status_code == 303 and second.location != first.location
        pdf = second.location + '/druck.pdf'
    before = snapshot(owner)
    base, cookie = recipe_server
    javascript, width = (True, 1440) if has_revision else (False, 390)
    words = ('Öffnen', 'Verlauf', 'PDF öffnen') if locale == 'de' else ('Open', 'History', 'Open PDF')
    open_name = f'{title} öffnen' if locale == 'de' else f'Open {title}'
    history_name = f'Verlauf für {title}' if locale == 'de' else f'History for {title}'
    pdf_name = f'PDF öffnen · Stand 2 · {title}' if locale == 'de' else f'Open PDF · Revision 2 · {title}'
    with browser.new_context(viewport={'width': width, 'height': 900}, java_script_enabled=javascript,
                             reduced_motion='reduce', service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        posts, errors, captures = [], [], []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        cdp = context.new_cdp_session(page)
        assert page.goto(base + '/admin/rezepte', wait_until='networkidle').status == 200
        row = page.locator('.recipe-row').filter(has=page.get_by_text(title, exact=True))
        expect(row).to_have_count(1)
        expect(row.locator('details.ui-sem-actions, [data-semantic="actions.more"]')).to_have_count(0)
        page.mouse.move(0, 0)
        items = row.locator('.admin-row-actions')
        actions = [(root + '/ansicht', words[0], open_name, 'actions.open', 'arrow-right')]
        if has_revision:
            actions.append((pdf, words[2], pdf_name, 'actions.open_pdf', 'file-type-pdf'))
            expect(items.locator(f'a[href="{first.location}/druck.pdf"]')).to_have_count(0)
        else:
            snapshot_name = f'Stand von {title} festhalten' if locale == 'de' else f'Save a revision of {title}'
            actions.append((history + '#recipe-freeze', '', snapshot_name, 'actions.snapshot', 'file-check'))
            unavailable = items.locator('[data-semantic="actions.open_pdf"]')
            expect(unavailable).to_be_disabled()
            expect(unavailable).to_have_accessible_description('Noch kein gespeicherter Stand vorhanden')
        actions.append((history, words[1], history_name, 'actions.history', 'history'))
        for index, (href, _label, name, key, glyph) in enumerate(actions):
            link = items.locator(f'a[href="{href}"]')
            expect(link).to_have_count(1)
            expect(link).to_have_text('')
            expect(link).to_have_accessible_name(name)
            expect(link).to_have_attribute('data-ui-tooltip', name)
            expect(link).to_have_attribute('data-semantic', key)
            assert link.locator('use').get_attribute('href').endswith('#tabler-' + glyph)
            assert link.get_attribute('title') is None
            for _ in range(80):
                page.keyboard.press('Tab')
                if link.evaluate('el => el === document.activeElement'):
                    break
            expect(link).to_be_focused()
            if javascript:
                expect(page.get_by_role('tooltip')).to_have_text([name])
                expect(page.get_by_role('tooltip', name=name, exact=True)).to_be_visible()
            else:
                expect(page.get_by_role('tooltip')).to_have_count(0)
            state = page.evaluate('''() => ({width: innerWidth, dpr: devicePixelRatio,
                overflow: document.documentElement.scrollWidth > innerWidth + 1,
                coarse: matchMedia('(pointer: coarse)').matches, touch: navigator.maxTouchPoints,
                tooltips: [...document.querySelectorAll('[role="tooltip"]')].map(el => el.textContent)})''')
            assert not state['overflow'] and not state['coarse'] and state['touch'] == 0
            image = cdp.send('Page.captureScreenshot', {'format': 'png', 'fromSurface': True,
                                                       'captureBeyondViewport': False})
            (tmp_path / f'action-{index}.png').write_bytes(base64.b64decode(image['data']))
            assert page.evaluate("[matchMedia('(pointer: coarse)').matches,navigator.maxTouchPoints]") == [False, 0]
            captures.append({'href': href, 'name': name, **state})
            (tmp_path / 'actions.json').write_text(json.dumps(captures, indent=2, ensure_ascii=False))
        assert not posts and not errors and snapshot(owner) == before
        if has_revision:
            response = context.request.get(base + pdf)
            assert response.status == 200 and response.headers['content-type'].startswith('application/pdf')
            assert response.body().startswith(b'%PDF-')
        with page.expect_navigation(wait_until='networkidle') as navigation:
            page.keyboard.press('Enter')
        assert navigation.value.status == 200 and urlsplit(page.url).path == history
        assert not posts and not errors
    assert snapshot(owner) == before


def test_recipe_actions_in_narrow_desktop_card(a3, recipe_server, browser, tmp_path):  # noqa: F811
    complete_a3(a3)
    base, cookie = recipe_server
    with browser.new_context(viewport={'width': 1440, 'height': 900}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + '/admin/rezepte').status == 200
        card = page.locator('.recipe-list').locator('..')
        card.evaluate("el => el.style.width = '360px'")
        box = card.bounding_box()
        actions = card.locator('.admin-row-actions [data-semantic]')
        expect(actions).to_have_count(6)
        page.screenshot(path=str(tmp_path / 'recipe-actions-card360-viewport1440.png'), full_page=True)
        for action in actions.all():
            expect(action).to_be_visible()
            target = action.bounding_box()
            assert target['x'] >= box['x'] and target['x'] + target['width'] <= box['x'] + box['width'] + 1


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('count', [0, 1, 3])
@pytest.mark.parametrize('reader', [False, True])
def test_recipe_template_associations_have_distinct_native_actions(
    a3, recipe_server, browser, monkeypatch, tmp_path, locale, count, reader,  # noqa: F811
):
    app, owner, client, _, public_id = a3
    app.config['UI_LOCALE'] = locale
    title = 'Langer Rezepttitel mit Kräutern, Gemüse und einer ausführlichen Bezeichnung'
    edit(a3, title=title)
    complete_a3(a3)
    targets = []
    for index in range(count):
        name = f'Vorlage {index + 1} mit langem Namen'
        path = create_template(client, title=name, recipe_public_id=public_id)
        archived = index == 2
        if archived:
            data = template_fields(client, path)
            data['action'] = 'archive'
            assert client.post(path, data=data).status_code == 303
        targets.append((name, path, archived))
    if reader:
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
    before = snapshot(owner), template_snapshot(owner)
    base, cookie = recipe_server
    width = 390 if reader else 1440
    with browser.new_context(viewport={'width': width, 'height': 844 if reader else 900},
                             has_touch=reader, java_script_enabled=not reader,
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + '/admin/rezepte').status == 200
        row = page.locator('.recipe-row').filter(has_text=title)
        expect(row.locator('[data-semantic="actions.open_template"]')).to_have_count(count)
        expect(row.locator('[data-semantic="actions.create_template"]')).to_have_count(int(not count and not reader))
        expect(row.locator('[data-semantic="actions.edit"]')).to_have_count(int(not reader))
        expect(row.locator('[data-semantic="actions.snapshot"]')).to_have_count(int(not reader))
        expect(row.locator('[data-semantic="actions.more"], details')).to_have_count(0)
        expect(row.locator('[data-semantic="actions.open_pdf"]')).to_be_disabled()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        for action in row.locator('.admin-row-actions [data-semantic]').all():
            expect(action).to_be_visible()
            expect(action).to_have_text('')
            box = action.bounding_box()
            assert box['x'] >= 0 and box['x'] + box['width'] <= width + 1
        page.screenshot(path=str(tmp_path / f'associations-{count}-{locale}-{width}.png'), full_page=True)
        for name, path, archived in targets:
            action = row.locator(f'a[href="{path}"]')
            archived_label = 'archiviert' if locale == 'de' else 'archived'
            object_name = name + (' · ' + archived_label if archived else '')
            label = f'Gerichtvorlage für {object_name} öffnen' if locale == 'de' else f'Open dish template for {object_name}'
            expect(action).to_have_accessible_name(label)
            expect(action).to_have_attribute('data-ui-tooltip', label)
            action.focus()
            with page.expect_navigation() as navigation:
                action.press('Enter')
            assert navigation.value.status == 200
            assert page.url == base + path
            assert page.goto(base + '/admin/rezepte').status == 200
        # The object view retains the association state after removing list copy.
        assert page.goto(base + f'/admin/rezepte/{public_id}/ansicht').status == 200
        for name, path, _ in targets:
            expect(page.locator(f'a[href="{path}"]').filter(has_text=name)).to_be_visible()
        if not targets:
            expect(page.locator('.text-break').filter(has_text='Keine Gerichtvorlage')).to_be_visible()
    assert (snapshot(owner), template_snapshot(owner)) == before


def test_recipe_direct_actions_native_zoom(a3, recipe_server, browser, tmp_path):  # noqa: F811
    _, owner, _, _, _ = a3
    complete_a3(a3)
    before = snapshot(owner)
    base, cookie = recipe_server
    with TemporaryDirectory(prefix='recipe-actions-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True,
            reduced_motion='reduce', args=['--no-sandbox', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            assert page.goto(base + '/admin/rezepte').status == 200
            assert page.evaluate('[devicePixelRatio, innerWidth]') == [2, 720]
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            actions = page.locator('.recipe-row .admin-row-actions [data-semantic]')
            expect(actions).to_have_count(6)
            for action in actions.all():
                expect(action).to_be_visible()
                box = action.bounding_box()
                assert box['x'] >= 0 and box['x'] + box['width'] <= 721
                if not action.is_disabled():
                    action.focus()
                    expect(action).to_be_focused()
            page.keyboard.press('Escape')
            page.screenshot(path=str(tmp_path / 'recipe-actions-native-200-percent.png'), full_page=True)
            (tmp_path / 'zoom.json').write_text(json.dumps({
                'browser_zoom': 2, 'viewport_css': page.evaluate('[innerWidth, innerHeight]'),
                'role': 'Cafeteria.Publisher',
                'route': '/admin/rezepte',
            }))
    assert snapshot(owner) == before
