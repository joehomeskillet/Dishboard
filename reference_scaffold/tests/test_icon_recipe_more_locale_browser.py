"""Opened recipe actions retain localized text, exact revisions and native targets."""
from __future__ import annotations

import base64
import json
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import expect

from test_recipe_images_browser import recipe_server  # noqa: F401
from test_recipe_revision_routes import (  # noqa: F401
    a3, app_engine, b3, complete_a3, edit, fields, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_store_db import snapshot
from test_rendered_ui import browser  # noqa: F401


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
        expect(row.locator('.admin-row-actions > a')).to_have_text('')
        details = row.locator('details.ui-sem-actions')
        summary = details.locator(':scope > summary')
        page.mouse.move(0, 0)
        for _ in range(60):
            page.keyboard.press('Tab')
            if summary.evaluate('el => el === document.activeElement'):
                break
        expect(summary).to_be_focused()
        summary.press('Enter')
        expect(details).to_have_attribute('open', '')
        items = details.locator('.ui-sem-action-items')
        actions = [(root + '/ansicht', words[0], open_name, 'actions.open', 'arrow-right')]
        if has_revision:
            actions.append((pdf, words[2], pdf_name, 'actions.print', 'printer'))
            expect(items.locator(f'a[href="{first.location}/druck.pdf"]')).to_have_count(0)
        else:
            actions.append((history + '#recipe-freeze', words[1], history_name, 'actions.history', 'history'))
            fallback = items.locator(f'a[href="{history}#recipe-freeze"]')
            expect(fallback).to_have_attribute('aria-describedby', f'print-hint-{public_id}')
            expect(fallback).to_have_accessible_description('Zum Drucken zuerst einen Stand festhalten.')
        actions.append((history, words[1], history_name, 'actions.history', 'history'))
        for index, (href, label, name, key, glyph) in enumerate(actions):
            link = items.locator(f'a[href="{href}"]')
            expect(link).to_have_count(1)
            expect(link).to_have_text(label)
            expect(link).to_have_accessible_name(name)
            expect(link).to_have_attribute('data-ui-tooltip', name)
            expect(link).to_have_attribute('data-semantic', key)
            assert link.locator('use').get_attribute('href').endswith('#tabler-' + glyph)
            assert link.get_attribute('title') is None
            if index or not javascript:
                page.keyboard.press('Tab')
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
