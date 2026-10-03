"""Shared native disclosures retain import/upload data and explicit discard safety."""
from __future__ import annotations

import json
from io import BytesIO
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from cafeteria import recipe_store, roles
from test_master_data_db import signed_in
from test_recipe_images_browser import (  # noqa: F401
    a3, app_engine, b3, browser, installed_pg16, pg16, recipe_server, seeded_pg16,
)
from test_recipe_import import json_bytes, recipe
from test_recipe_import_routes import create, snapshot as import_snapshot
from test_recipe_revision_routes import edit, png, snapshot as recipe_snapshot
from test_recipe_store_db import target

TITLE = 'Suppe " data-hostile="title" & Kräuter'
FILENAME = "Import 'Kräuter' &.json"


def _values(form):
    return form.evaluate('''form => [...new FormData(form)].map(([key, value]) =>
        [key, typeof value === 'string' ? value : {name: value.name, size: value.size, type: value.type}])''')


def _confirmation_control(page, summary, name, javascript, failures, tmp_path):
    expect(summary).to_be_visible()
    assert summary.evaluate("el => el.tagName === 'BUTTON'")
    expect(summary).to_have_text('Verwerfen')
    expect(summary.locator('svg')).to_have_count(0)
    expect(summary.locator('button, a')).to_have_count(0)
    minimum = page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches ? 44 : 36")
    box = summary.bounding_box()
    assert box and box['width'] >= minimum and box['height'] >= minimum
    if summary.get_attribute('aria-label') != name:
        failures.append(('accessible name', name, summary.get_attribute('aria-label')))
    tooltip_name = summary.get_attribute('data-ui-tooltip')
    if tooltip_name != name:
        failures.append(('tooltip name', name, tooltip_name))
    summary.scroll_into_view_if_needed()
    if javascript and tooltip_name:
        summary.hover()
        tooltip = page.get_by_role('tooltip', name=name, exact=True)
        expect(tooltip).to_be_visible()
        expect(tooltip).to_have_text(name)
        expect(tooltip.locator('[data-hostile]')).to_have_count(0)
        tooltip_state = '''el => ({
            summary: el.outerHTML,
            active: {tag: document.activeElement.tagName, id: document.activeElement.id,
                     name: document.activeElement.getAttribute('name')},
            describedby: el.getAttribute('aria-describedby'),
            hovered: el.matches(':hover'),
            instanceTip: window.tabler.Tooltip.getInstance(el)?.tip?.id,
            activeTrigger: window.tabler.Tooltip.getInstance(el)?._activeTrigger,
            tips: [...document.querySelectorAll('[role="tooltip"]')].map(tip => ({
                id: tip.id, text: tip.textContent, classes: tip.className,
                visible: !!tip.getClientRects().length, dismissed: tip.dataset.dismissed
            }))
        })'''
        before_escape = summary.evaluate(tooltip_state)
        page.keyboard.press('Escape')
        try:
            expect(tooltip).to_be_hidden()
        except AssertionError:
            (tmp_path / 'tooltip-dismissal.json').write_text(json.dumps({
                'before': before_escape, 'after': summary.evaluate(tooltip_state),
            }, indent=2), encoding='utf-8')
            page.screenshot(path=str(tmp_path / 'tooltip-dismissal.png'), full_page=False)
            raise
        page.mouse.move(0, 0)
    summary.focus()
    page.keyboard.press('Shift')
    expect(summary).to_be_focused()
    assert summary.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
    if javascript and tooltip_name:
        expect(page.get_by_role('tooltip', name=name, exact=True)).to_be_visible()
        page.keyboard.press('Escape')
        expect(page.get_by_role('tooltip', name=name, exact=True)).to_be_hidden()
    page.keyboard.press('Escape')
    expect(summary).to_be_focused()
    expect(summary).to_be_visible()
    assert summary.evaluate("el => getComputedStyle(el, '::after').content") == 'none'


def _static_fields(page, section, fields):
    expect(section).to_be_visible()
    expect(section.locator('details, summary')).to_have_count(0)
    for field in fields:
        expect(field).to_be_visible()
        field.focus()
        page.keyboard.press('Escape')
        expect(field).to_be_focused()
        expect(field).to_be_visible()


@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('javascript', [False, True], ids=['nojs', 'js'])
@pytest.mark.parametrize('width', [1440, 390])
def test_native_import_image_disclosures(
    a3, recipe_server, browser, monkeypatch, tmp_path, locale, javascript, width,  # noqa: F811
):
    app, owner, client, actor, recipe_id = a3
    monkeypatch.setitem(app.config, 'UI_LOCALE', locale)
    edit(a3, title=TITLE)
    source = json_bytes(recipe(TITLE), recipe('Zweite Suppe'))
    initial_path = create(client, source_file=(BytesIO(source), 'initial.json'))
    image_path = f'/admin/rezepte/{recipe_id}/bilder'
    base, cookie = recipe_server
    failures, posts = [], []
    names = {
        'de': ('Hochladen', 'Details für Zeile {}', f'{FILENAME} löschen',
               f'{TITLE}: Weitere Optionen ein- oder ausklappen'),
        'en': ('Upload', 'Details for row {}', f'Delete {FILENAME}',
               f'Expand or collapse more options: {TITLE}'),
    }[locale]
    with browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             java_script_enabled=javascript, reduced_motion='reduce', has_touch=width == 390,
                             service_workers='block') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        assert page.goto(base + initial_path).status == 200
        upload = page.locator('[data-import-upload]')
        expect(upload.get_by_role('heading')).to_have_text('Andere Datei wählen')
        upload_form = page.locator('form[action="/admin/rezepte/import"]')
        expect(upload_form).to_have_attribute('method', 'post')
        expect(upload_form).to_have_attribute('enctype', 'multipart/form-data')
        page.locator('#source_file').set_input_files(
            {'name': FILENAME, 'mimeType': 'application/json', 'buffer': source})
        upload_form.locator('input[name="annotation"][value="unreviewed"]').check()
        original_upload = _values(upload_form)
        before = import_snapshot(owner)
        _static_fields(page, upload, [page.locator('#source_file')])
        assert _values(upload_form) == original_upload
        assert import_snapshot(owner) == before and posts == []
        with page.expect_response(lambda response: response.request.method == 'POST') as response:
            upload_form.locator('button[data-semantic="actions.preview"]').click()
        assert response.value.status == 303
        assert response.value.request.headers['content-type'].startswith('multipart/form-data; boundary=')
        expect(page.locator('[data-checked-file]')).to_have_attribute('data-checked-file', FILENAME)
        batch_path = urlsplit(page.url).path
        assert batch_path != initial_path and len(posts) == 1
        form = page.locator(f'form[action="{batch_path}"]')
        expect(form).to_have_attribute('method', 'post')
        expect(form.locator('input[name="_csrf"]')).not_to_have_value('')
        expect(form.locator('input[name="row_version"]')).not_to_have_value('')
        page.locator('#row-1-title').fill('Ungespeicherte Suppe')
        original = _values(form)
        before = import_snapshot(owner)
        for row in (1, 2):
            section = page.locator(f'#row-{row}-details')
            _static_fields(page, section, section.locator('input').all())
        expect(page.locator('[data-semantic="actions.more"]')).to_have_count(0)
        more = form.locator('[data-import-discard] button[name="action"][value="cancel"]')
        _confirmation_control(page, more, 'Verwerfen bestätigen', javascript, failures, tmp_path)
        assert _values(form) == original
        assert import_snapshot(owner) == before and len(posts) == 1
        expect(page.locator('[data-hostile]')).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        more.scroll_into_view_if_needed()
        expect(more).to_be_in_viewport(ratio=1)
        (tmp_path / 'import-capture.json').write_text(json.dumps({
            'route': batch_path, 'viewport': page.viewport_size, 'role': 'Cafeteria.Publisher',
            'locale': locale, 'javascript': javascript, 'coarse': width == 390,
        }, indent=2))
        page.screenshot(path=str(tmp_path / 'import-closed.png'), full_page=False)
        confirm = form.locator('button[name="action"][value="cancel"]')
        expect(confirm).to_be_visible()
        expect(confirm).to_have_text('Verwerfen')
        expect(confirm).to_have_accessible_name('Verwerfen bestätigen')
        expect(confirm).to_have_attribute('data-semantic', 'actions.delete')
        expect(confirm).to_have_attribute('aria-describedby', 'discard-consequence')
        expect(form.locator('#discard-consequence')).to_contain_text('vorhandene Rezepte bleiben unverändert')
        assert _values(form) == original and len(posts) == 1
        confirm.scroll_into_view_if_needed()
        expect(confirm).to_be_in_viewport(ratio=1)
        page.screenshot(path=str(tmp_path / 'import-confirmation.png'), full_page=False)
        if javascript:
            dismissed = []
            def dismiss(dialog):
                dismissed.append({'type': dialog.type, 'message': dialog.message})
                dialog.dismiss()
            page.once('dialog', dismiss)
            confirm.click()
            assert dismissed == [{'type': 'confirm', 'message': confirm.get_attribute('data-confirm')}]
            assert _values(form) == original and len(posts) == 1
            assert import_snapshot(owner) == before
            page.once('dialog', lambda dialog: dialog.accept())
        with page.expect_response(lambda response: response.request.method == 'POST') as response:
            confirm.click()
        assert response.value.status == 303 and len(posts) == 2
        sent = parse_qs(response.value.request.post_data, keep_blank_values=True)
        assert sent['action'] == ['cancel']
        for key, value in original:
            assert value in sent[key]
        batch_status = form.locator(':scope > p > .admin-label')
        expect(batch_status).to_be_visible()
        expect(batch_status).to_have_text('Verworfen')
        expect(page.locator('.page-header .admin-statusbar')).to_have_count(0)
        assert import_snapshot(owner)['recipes'] == before['recipes']

        assert page.goto(base + image_path).status == 200
        header = page.locator('.page-header')
        expect(header.locator('.page-header-subtitle')).to_contain_text(TITLE)
        expect(header).to_contain_text('Entwurf' if locale == 'de' else 'Draft')
        status_cards = header.locator('.admin-statusbar-item').count()
        if status_cards:
            failures.append(('image draft status cards', status_cards))
        image_form = page.locator(f'form[action="{image_path}"]')
        expect(image_form).to_have_attribute('method', 'post')
        expect(image_form).to_have_attribute('enctype', 'multipart/form-data')
        image_upload = image_form.locator('button[data-semantic="actions.upload"]')
        expect(image_upload).to_have_accessible_name(names[0])
        expect(image_upload).to_have_attribute('data-ui-tooltip', names[0])
        upload_text = image_upload.inner_text().strip()
        if upload_text:
            failures.append(('image upload visible text', upload_text))
        page.screenshot(path=str(tmp_path / 'image-before-upload.png'), full_page=False)
        page.locator('#image-file').set_input_files(
            {'name': 'recipe.png', 'mimeType': 'image/png', 'buffer': png()})
        image_form.locator('[name="caption"]').fill(TITLE)
        options = image_form.locator('section[aria-labelledby="image-source-heading"]')
        expect(options.get_by_role('heading')).to_have_text('Quelle (optional)')
        image_form.locator('[name="source_url"]').fill('https://example.invalid/image.png')
        image_form.locator('[name="source_license"]').fill('CC0')
        image_form.locator('[name="fetched_at"]').fill('2026-09-28T10:30:00+02:00')
        image_values = _values(image_form)
        assert {key for key, _ in image_values} == {
            '_csrf', '_form_context', 'row_version', 'file', 'caption',
            'source_url', 'source_license', 'fetched_at',
        }
        before_image = recipe_snapshot(owner)
        _static_fields(page, options, options.locator('input').all())
        assert _values(image_form) == image_values
        assert recipe_snapshot(owner) == before_image and len(posts) == 2
        expect(page.locator('[data-hostile]')).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(tmp_path / 'image-options-open.png'), full_page=False)
        page.keyboard.press('Escape')
        expect(options).to_be_visible()
        assert _values(image_form) == image_values
        page.screenshot(path=str(tmp_path / 'image-options-closed.png'), full_page=False)
        with page.expect_response(lambda response: response.request.method == 'POST') as response:
            image_form.locator('button[data-semantic="actions.upload"]').click()
        assert response.value.status == 303 and len(posts) == 3
        assert response.value.request.headers['content-type'].startswith('multipart/form-data; boundary=')
        expect(page.locator('td[data-label="Bildunterschrift"]')).to_have_text(TITLE)
        expect(page.locator('td[data-label="Herkunft"]')).to_contain_text('CC0')
        expect(page.locator('main img')).to_have_count(1)
        expect(page.locator('[data-hostile]')).to_have_count(0)
        page.screenshot(path=str(tmp_path / 'image-saved.png'), full_page=False)
        publisher_capabilities = roles.ROLE_CAPABILITIES['Cafeteria.Publisher']
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', {'draft.read'})
        before_readonly = recipe_snapshot(owner)
        assert page.goto(base + image_path).status == 200
        expect(page.locator('main form, main [data-semantic="actions.upload"]')).to_have_count(0)
        expect(page.locator('td[data-label="Bildunterschrift"]')).to_have_text(TITLE)
        assert page.goto(base + '/admin/rezepte/import').status == 403
        assert client.post(batch_path, data={'_csrf': 'b3-test-csrf', 'action': 'cancel'}).status_code == 403
        assert recipe_snapshot(owner) == before_readonly
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', publisher_capabilities)
        engine = app.extensions['cafeteria_db']
        with signed_in(engine, actor):
            row = recipe_store.get_recipe(engine, recipe_id)
            recipe_store.set_recipe_active(engine, actor, target(row), active=False,
                                           expected_location_id=recipe_store.get_location(engine))
        before_archived = recipe_snapshot(owner)
        assert page.goto(base + image_path).status == 200
        expect(header.locator('.page-header-subtitle')).to_contain_text(TITLE)
        expect(header).to_contain_text('Archiviert')
        status_cards = header.locator('.admin-statusbar-item').count()
        if status_cards:
            failures.append(('image archived status cards', status_cards))
        expect(page.locator('main form, main [data-semantic="actions.upload"]')).to_have_count(0)
        expect(page.locator('main .alert')).to_have_text(
            'Archiviert · Bilder bleiben lesbar. Ein Upload ist erst nach Reaktivieren möglich.')
        expect(page.locator('td[data-label="Bildunterschrift"]')).to_have_text(TITLE)
        expect(page.locator('[data-hostile]')).to_have_count(0)
        assert recipe_snapshot(owner) == before_archived and len(posts) == 3
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(tmp_path / 'image-archived.png'), full_page=False)
    assert not failures, failures
