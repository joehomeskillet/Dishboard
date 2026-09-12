"""Tabler lifecycle with native forms, historical PDFs and read-only catalog."""
from __future__ import annotations

from pathlib import Path
from threading import Event
from typing import Any
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import Browser, expect
from sqlalchemy import Engine
from flask import request

from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _login, database_engine  # noqa: F401
from test_print_template_archive import snapshot
from test_print_template_browser import _context, _targets, _wait_for_pdf_paint, browser, editor_server  # noqa: F401
from test_print_template_routes import editor_app  # noqa: F401


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_archive_reactivate_native_lifecycle(editor_app: Any, editor_server: str, database_engine: Engine, browser: Browser, width: int, javascript: bool, family: str, profile: str, tmp_path: Path) -> None:  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    old_pdf_url = f'/admin/vorlagen/{family}/vorschau.pdf?week={DAY}&template=standard&revision=1'
    original_pdf = client.get(old_pdf_url)
    assert original_pdf.status_code == 200
    with _context(browser, editor_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        network = context.new_cdp_session(page)
        network.send('Network.enable')
        network.send('Network.setCacheDisabled', {'cacheDisabled': True})
        assets: list[tuple[str, int]] = []
        errors: list[str] = []
        page.on('response', lambda response: assets.append((response.url, response.status)) if '/static/' in response.url else None)
        page.on('pageerror', lambda error: errors.append(str(error)))
        response = page.goto(f'/admin/vorlagen/{family}?week={DAY}')
        assert response is not None and response.status == 200
        expect(page.get_by_role('button', name='Vorlage archivieren', exact=True)).to_have_count(0)
        page.locator('details[data-template-more-actions] summary').click()
        page.get_by_label('Name der Kopie', exact=True).fill('Aktive Ersatzvorlage')
        page.get_by_role('button', name='Kopie erstellen', exact=True).click()
        copy_id = parse_qs(urlsplit(page.url).query)['template'][0]
        page.locator('details[data-template-activation] summary').click()
        page.get_by_role('button', name='Diese Version aktivieren', exact=True).click()
        expect(page.locator('[data-template-status-scope]')).to_contain_text('Version 1')
        page.get_by_label('Vorlage', exact=True).select_option('standard')
        page.get_by_role('button', name='Anzeigen', exact=True).click()
        page.locator('details[data-template-more-actions] summary').click()
        confirmation = page.get_by_role('checkbox', name='Ich möchte diese Vorlage archivieren.', exact=True)
        expect(confirmation).to_be_visible()
        label = confirmation.locator('..')
        box = label.bounding_box()
        assert box is not None and box['height'] >= 48 and box['width'] >= 48
        posts = []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        before_confirmation = snapshot(database_engine)
        page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
        expect(confirmation).to_be_focused()
        assert confirmation.evaluate('el => el.validity.valueMissing')
        assert not posts and snapshot(database_engine) == before_confirmation
        confirmation.press('Space')
        expect(confirmation).to_be_checked()
        confirmation.press('Space')
        expect(confirmation).not_to_be_checked()
        page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
        assert not posts and snapshot(database_engine) == before_confirmation
        label.click()
        expect(confirmation).to_be_checked()
        page.get_by_role('button', name='Vorlage archivieren', exact=True).focus()
        expect(page.get_by_role('button', name='Vorlage archivieren', exact=True)).to_be_focused()
        with page.expect_response(lambda response: response.request.method == 'POST') as post:
            page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
        assert post.value.status == 303
        assert len(posts) == 1
        assert set(parse_qs(posts[0].post_data)) == {'_csrf', 'action', 'version', 'revision'}
        page.locator('details[data-template-more-actions] summary').click()
        expect(page.get_by_role('button', name='Vorlage reaktivieren', exact=True)).to_be_visible()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_be_disabled()
        expect(page.get_by_role('button', name='Vorlage speichern', exact=True)).to_have_count(0)
        expect(page.get_by_role('button', name='Diese Version aktivieren', exact=True)).to_have_count(0)
        _targets(page)
        before = snapshot(database_engine)
        assert client.get(old_pdf_url).data == original_pdf.data
        page.locator('details[data-template-versions] summary').click()
        page.get_by_role('link', name='Version 1 ansehen', exact=True).click()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Version 1', exact=True)).to_be_visible()
        page.get_by_role('link', name='Alle Vorlagen', exact=True).click()
        page.locator(f'[aria-controls="output-{family}"]').click()
        page.locator(f'#output-{family} .output-layouts-section summary').click()
        expect(page.get_by_role('heading', name='Archivierte Vorlagen', exact=True)).to_be_visible()
        item = page.locator('li[data-template-id="standard"]').filter(has=page.get_by_text('Archiviert', exact=True))
        expect(item).to_have_count(1)
        expect(item.get_by_text('Standard', exact=True)).to_be_visible()
        _targets(page)
        page.screenshot(path=str(tmp_path / f'archive-catalog-{family}-{width}-js{javascript}.png'), full_page=True)
        item.get_by_role('link', name='Vorlage bearbeiten', exact=False).click()
        page.locator('details[data-template-more-actions] summary').click()
        expect(page.get_by_role('button', name='Vorlage reaktivieren', exact=True)).to_be_visible()
        assert snapshot(database_engine) == before
        if javascript:
            frame = page.locator('iframe')
            frame.scroll_into_view_if_needed()
            _wait_for_pdf_paint(page, frame, tmp_path / f'archive-pdf-{family}-{width}.png')
        # A full-page capture can include off-viewport fixed elements at its
        # expanded origin. Record actual viewport geometry before interpreting it.
        assert page.locator('.skip-link').evaluate('el => el.getBoundingClientRect().bottom <= 0')
        page.screenshot(path=str(tmp_path / f'archive-viewport-{family}-{width}-js{javascript}.png'))
        page.screenshot(path=str(tmp_path / f'archive-editor-{family}-{width}-js{javascript}.png'), full_page=True)
        page.get_by_role('button', name='Vorlage reaktivieren', exact=True).click()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_be_enabled()
        page.locator('details[data-template-more-actions] summary').click()
        expect(page.get_by_role('button', name='Vorlage archivieren', exact=True)).to_be_visible()
        expect(page.locator(f'#template-select option[value="{copy_id}"]')).to_contain_text('Aktiv: Revision 1')
        assert client.get(old_pdf_url).data == original_pdf.data
        assert assets and all(status == 200 for _, status in assets)
        assert not errors


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_archive_confirmation_survives_late_pdf_response(editor_app, editor_server, database_engine, browser, width, javascript, family, profile, tmp_path):  # noqa: F811
    from test_print_template_archive import COPY_ID, legacy_document, seed

    requested, release = Event(), Event()

    @editor_app.after_request
    def delay_first_pdf(response):
        if request.path.endswith('/vorschau.pdf') and not requested.is_set():
            assert response.status_code == 200 and response.mimetype == 'application/pdf'
            requested.set()
            assert release.wait(20), 'Test did not release the real PDF response'
        return response

    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    seed(database_engine, profile, legacy_document())
    before = snapshot(database_engine)
    url = f'/admin/vorlagen/{family}?week={DAY}&template={COPY_ID}&revision=1'
    try:
        with _context(browser, editor_server, client, width, javascript=javascript) as context:
            page = context.new_page()
            posts, errors = [], []
            page.on('request', lambda req: posts.append(req) if req.method == 'POST' else None)
            page.on('pageerror', lambda error: errors.append(str(error)))
            response = page.goto(url, wait_until='domcontentloaded')
            assert response is not None and response.status == 200
            page.locator('details[data-template-more-actions] summary').click()
            confirmation = page.get_by_role('checkbox', name='Ich möchte diese Vorlage archivieren.', exact=True)
            expect(confirmation).to_be_visible()
            assert confirmation.evaluate('el => el.form.id === "archive-form" && !el.closest("form")')
            expect(page.locator('#archive-form')).to_have_count(1)
            page.locator('details[data-template-activation] summary').click()
            active_pdf = page.get_by_role('link', name='PDF mit aktiver Vorlage öffnen', exact=True)
            original_href = active_pdf.get_attribute('href')
            assert original_href == f'/admin/{family}/preview/print?week={DAY}'
            expect(active_pdf).to_be_enabled()
            assert requested.wait(10)
            assert not release.is_set()
            confirmation.focus()
            confirmation.press('Space')
            expect(confirmation).to_be_checked()
            expect(active_pdf).to_be_enabled()
            expect(active_pdf).to_have_attribute('href', original_href)
            with page.expect_request_finished(lambda req: '/vorschau.pdf' in req.url):
                with page.expect_response(lambda reply: '/vorschau.pdf' in reply.url) as late_pdf:
                    release.set()
            assert late_pdf.value.status == 200
            expect(confirmation).to_be_checked()
            confirmation.focus()
            expect(confirmation).to_be_focused()
            confirmation.press('Space')
            expect(confirmation).not_to_be_checked()
            expect(active_pdf).to_be_enabled()
            expect(active_pdf).to_have_attribute('href', original_href)
            page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
            expect(confirmation).to_be_focused()
            assert confirmation.evaluate('el => el.validity.valueMissing')
            assert not posts and snapshot(database_engine) == before
            confirmation.press('Space')
            expect(confirmation).to_be_checked()
            _targets(page)
            tmp_path.chmod(0o700)
            image = tmp_path / f'late-pdf-confirm-{family}-{width}-js{javascript}.png'
            page.screenshot(path=str(image))
            image.chmod(0o600)
            with page.expect_response(lambda reply: reply.request.method == 'POST') as post:
                page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
            assert post.value.status == 303 and len(posts) == 1
            assert set(parse_qs(posts[0].post_data)) == {'_csrf', 'action', 'version', 'revision'}
            page.locator('details[data-template-more-actions] summary').click()
            expect(page.get_by_role('button', name='Vorlage reaktivieren', exact=True)).to_be_visible()
            assert not errors
    finally:
        release.set()


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('javascript', [True, False])
def test_historical_lifecycle_conflict_keeps_revision_until_reload(editor_app, editor_server, database_engine, browser, width, javascript, tmp_path):  # noqa: F811
    import copy

    from test_print_template_archive import COPY_ID, legacy_document, seed
    from test_print_template_routes import fields

    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    document = legacy_document()
    template = document['templates'][1]
    template['revisions'].append({**copy.deepcopy(template['revisions'][0]), 'id': 2, 'name': 'Neuster Entwurf'})
    template['current_revision'] = 2
    seed(database_engine, 'patient', document)
    url = f'/admin/vorlagen/patienten?week={DAY}&template={COPY_ID}&revision=1'
    with _context(browser, editor_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        page.goto(url)
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Kopie')
        assert client.post(url, data=fields('archive', 3, 1)).status_code == 303
        before = snapshot(database_engine)
        page.locator('details[data-template-more-actions] summary').click()
        page.get_by_role('checkbox', name='Ich möchte diese Vorlage archivieren.', exact=True).check()
        with page.expect_response(lambda response: response.request.method == 'POST') as post:
            page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
        assert post.value.status == 409
        expect(page.get_by_role('heading', name='Vorlage · Version 1', exact=True)).to_be_visible()
        expect(page.get_by_role('heading', name='PDF-Vorschau · Version 1', exact=True)).to_be_visible()
        assert page.locator('input[name="version"]').evaluate_all('items => items.length > 0 && items.every(item => item.value === "3")')
        assert page.locator('input[name="revision"]').evaluate_all('items => items.length > 0 && items.every(item => item.value === "1")')
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Kopie')
        if javascript:
            expect(page.locator('#template-error')).to_be_focused()
        _targets(page)
        tmp_path.chmod(0o700)
        screenshot = tmp_path / f'historical-conflict-{width}-js{javascript}.png'
        page.screenshot(path=str(screenshot), full_page=True)
        screenshot.chmod(0o600)
        page.get_by_role('link', name='Aktuellen Stand neu laden', exact=True).click()
        expect(page.get_by_role('heading', name='Vorlage · Version 2', exact=True)).to_be_visible()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_have_value('Neuster Entwurf')
        assert snapshot(database_engine) == before


@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_read_roles_see_archive_but_cannot_mutate(editor_app: Any, database_engine: Engine, role: str) -> None:  # noqa: F811
    from test_print_template_archive import COPY_ID, legacy_document, seed
    from test_print_template_routes import fields

    document = legacy_document()
    document['schema_version'] = 2
    for item in document['templates']:
        item['archived'] = item['id'] == COPY_ID
    seed(database_engine, 'patient', document)
    client, _ = _login(editor_app, database_engine, [role])
    before = snapshot(database_engine)
    response = client.get(f'/admin/vorlagen?week={DAY}')
    assert response.status_code == 200 and b'Archivierte Vorlagen' in response.data
    assert b'Vorlageneditor' not in response.data and b'Vorlage reaktivieren' not in response.data
    for action in ['archive', 'reactivate']:
        assert client.post(f'/admin/vorlagen/patienten?week={DAY}&template={COPY_ID}', data=fields(action, 3)).status_code == 403
    assert snapshot(database_engine) == before


def test_archive_conflict_preserves_original_version_and_focus(editor_app: Any, editor_server: str, database_engine: Engine, browser: Browser) -> None:  # noqa: F811
    from test_print_template_archive import COPY_ID, legacy_document, seed
    from test_print_template_routes import fields

    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    seed(database_engine, 'patient', legacy_document())
    url = f'/admin/vorlagen/patienten?week={DAY}&template={COPY_ID}&revision=1'
    with _context(browser, editor_server, client, 390) as context:
        page = context.new_page()
        page.goto(url)
        assert client.post(url, data=fields('archive', 3)).status_code == 303
        before = snapshot(database_engine)
        page.locator('details[data-template-more-actions] summary').click()
        page.get_by_role('checkbox', name='Ich möchte diese Vorlage archivieren.', exact=True).check()
        with page.expect_response(lambda response: response.request.method == 'POST') as post:
            page.get_by_role('button', name='Vorlage archivieren', exact=True).click()
        assert post.value.status == 409
        expect(page.locator('#template-error')).to_be_focused()
        assert page.locator('input[name="version"]').evaluate_all('items => items.every(item => item.value === "3")')
        assert snapshot(database_engine) == before
        page.get_by_role('link', name='Aktuellen Stand neu laden', exact=True).click()
        page.locator('details[data-template-more-actions] summary').click()
        expect(page.get_by_role('button', name='Vorlage reaktivieren', exact=True)).to_be_visible()
        page.get_by_role('button', name='Vorlage reaktivieren', exact=True).click()
        expect(page.get_by_label('Vorlagenname', exact=True)).to_be_enabled()
