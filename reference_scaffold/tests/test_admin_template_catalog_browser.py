"""Real store, route and browser contracts for the read-only PDF catalog."""
from __future__ import annotations

import json
import os
import threading
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text
from werkzeug.serving import make_server

from cafeteria.print_templates import SETTING_PREFIX
from test_admin_output_hubs import MainLinks
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, _login, database_engine  # noqa: F401
from test_print_template_routes import editor_app, fields  # noqa: F401
from test_rendered_ui import browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
EVIDENCE_DIR = Path(__file__).resolve().parents[2] / os.environ.get(
    'TPL_DISH_ENTRY_EVIDENCE_DIR', '.claude/evidence/tpl-dish-entry-fix-0913'
)
PDF_TARGETS = {f'/admin/vorlagen/{family}{suffix}' for family in ('cafeteria', 'patienten')
               for suffix in ('', '/vorschau.pdf')}
SCREEN_TARGETS = {f'/admin/vorlagen/screens/{family}/{prefix}-week-{mode}'
                  for family, prefix in [('cafeteria', 'cafeteria'), ('patienten', 'patient')]
                  for mode in ('photo', 'text')}


def settings(engine):
    with engine.connect() as connection:
        return connection.execute(text(
            'SELECT id, setting_key, setting_value FROM cafeteria.settings ORDER BY id'
        )).all()


def populate(client, engine):
    for family, profile, values in (
        ('cafeteria', 'staff_guest', _staff_values()),
        ('patienten', 'patient', _patient_values()),
    ):
        _save(engine, profile, values)
        path = f'/admin/vorlagen/{family}?week={DAY}'
        assert client.post(path, data=fields(name='Aktiver Herbst', header_text='Aktiver Stand')).status_code == 303
        assert client.post(path, data=fields('activate', 1, 2)).status_code == 303
        assert client.post(path, data=fields(version=2, revision=2, name='Winter & Festtage', header_text='Neuer Entwurf')).status_code == 303
        assert client.post(path, data=fields('copy', 3, 3, name='Festliche Kopie')).status_code == 303


def test_virtual_catalog_and_missing_week_never_initialize_settings(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    before = settings(database_engine)
    page = client.get(f'/admin/vorlagen?week={DAY}')
    assert page.status_code == 200 and page.headers['Cache-Control'] == 'no-store'
    assert page.text.count('data-template-id="standard"') == 3
    recipe_links = [link for link in MainLinks(page.text).links
                    if urlsplit(link).path == '/admin/vorlagen/rezepte']
    assert len(recipe_links) == 1
    assert parse_qs(urlsplit(recipe_links[0]).query) == {'template': ['standard'], 'revision': ['1']}
    recipe_editor = client.get(recipe_links[0])
    assert recipe_editor.status_code == 200 and recipe_editor.headers['Cache-Control'] == 'no-store'
    assert '<iframe' not in recipe_editor.text
    assert {link for link in MainLinks(page.text).links if link.startswith('/admin/vorlagen/screens/')} == SCREEN_TARGETS
    for link in SCREEN_TARGETS:
        preview = client.get(link)
        assert preview.status_code == 404 and preview.headers['Cache-Control'] == 'no-store'
    for link in MainLinks(page.text).links:
        if urlsplit(link).path not in PDF_TARGETS:
            continue
        response = client.get(link)
        if '/vorschau.pdf' in link:
            assert response.status_code == 404
        else:
            assert response.status_code == 200
            assert 'noch keine gespeicherten Menüs' in response.text
            assert '<iframe' not in response.text
    assert settings(database_engine) == before
    assert '/admin/gerichtvorlagen' in MainLinks(page.text).links


def test_recipe_active_template_link_uses_explicit_ids_and_stays_privileged(
    editor_app, database_engine,  # noqa: F811
):
    admin, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    editor = '/admin/vorlagen/rezepte?template=standard&revision=1'
    assert admin.post(editor, data=fields(name='Neuer Rezeptentwurf')).status_code == 303

    response = admin.get('/admin/vorlagen')
    recipe_links = [link for link in MainLinks(response.text).links
                    if urlsplit(link).path == '/admin/vorlagen/rezepte']

    assert response.status_code == 200
    assert '/admin/vorlagen/rezepte?template=standard&revision=2' in recipe_links
    assert '/admin/vorlagen/rezepte?template=standard&revision=1' in recipe_links
    assert 'aria-label="Aktive Vorlage öffnen"' in response.text

    reader, _ = _login(editor_app, database_engine, ['Cafeteria.Editor'])
    reader_response = reader.get('/admin/vorlagen')
    assert reader_response.status_code == 200
    assert not any(urlsplit(link).path == '/admin/vorlagen/rezepte'
                   for link in MainLinks(reader_response.text).links)
    assert 'Aktive Vorlage öffnen' not in reader_response.text
    assert reader_response.text.count('aria-label="Rezept drucken"') == 1


def test_catalog_revision_links_render_real_saved_pdfs_without_mutation(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    populate(client, database_engine)
    before = settings(database_engine)
    active = {family: client.get(f'/admin/{family}/preview/print?week={DAY}').data
              for family in ('cafeteria', 'patienten')}
    response = client.get(f'/admin/vorlagen?week={DAY}')
    assert response.status_code == 200
    assert 'Winter &amp; Festtage' in response.text and 'Winter & Festtage' not in response.text
    assert response.text.count('<h3 class="admin-list-primary text-break mb-0">Aktiver Herbst</h3>') == 2
    assert response.text.count('<p class="admin-list-secondary print-tpl-meta mb-0">Version 2</p>') == 2
    assert response.text.count('Neuer Entwurf: Winter &amp; Festtage · Version 3') == 2
    # Heading, named action group and edit name/tooltip in both weekly catalogs.
    assert response.text.count('Festliche Kopie') == 8
    links = MainLinks(response.text).links
    assert '/admin/gerichtvorlagen' in links
    assert {link for link in MainLinks(response.text).links if link.startswith('/admin/vorlagen/screens/')} == SCREEN_TARGETS
    pdf_links = [link for link in links if urlsplit(link).path in PDF_TARGETS]
    assert len(pdf_links) == 12
    for link in pdf_links:
        query = parse_qs(urlsplit(link).query)
        assert query['week'] == [DAY]
        result = client.get(link)
        assert result.status_code == 200, link
        if '/vorschau.pdf' in link:
            assert result.mimetype == 'application/pdf' and result.data.startswith(b'%PDF-')
            assert result.headers['X-Print-Template-Revision'] == f"{query['template'][0]}:{query['revision'][0]}"
            if query['revision'] == ['2']:
                family = urlsplit(link).path.split('/')[3]
                assert result.data == active[family]
    for family, payload in active.items():
        assert client.get(f'/admin/{family}/preview/print?week={DAY}').data == payload
    changed = MainLinks(client.get('/admin/vorlagen?week=2026-09-07').text).links
    assert {link for link in changed if link.startswith('/admin/vorlagen/screens/')} == SCREEN_TARGETS
    assert all(parse_qs(urlsplit(link).query)['week'] == ['2026-09-07']
               for link in changed if urlsplit(link).path in PDF_TARGETS)
    assert settings(database_engine) == before


@pytest.mark.parametrize('role', ['Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_read_roles_see_catalog_but_no_privileged_revision_links(editor_app, database_engine, role):  # noqa: F811
    admin, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    populate(admin, database_engine)
    client, _ = _login(editor_app, database_engine, [role])
    response = client.get('/admin/vorlagen')
    assert response.status_code == 200
    assert response.text.count('<h3 class="admin-list-primary text-break mb-0">Aktiver Herbst</h3>') == 2
    assert response.text.count('<p class="admin-list-secondary print-tpl-meta mb-0">Version 2</p>') == 2
    assert response.text.count('Neuer Entwurf: Winter &amp; Festtage · Version 3') == 2
    assert not any(urlsplit(link).path in PDF_TARGETS for link in MainLinks(response.text).links)
    assert '/admin/gerichtvorlagen' in MainLinks(response.text).links
    assert {link for link in MainLinks(response.text).links if link.startswith('/admin/vorlagen/screens/')} == SCREEN_TARGETS
    for link in SCREEN_TARGETS:
        assert client.get(link).status_code == 404
    assert client.get(f'/admin/vorlagen/patienten?week={DAY}&revision=3').status_code == 403
    assert client.get(f'/admin/vorlagen/patienten/vorschau.pdf?week={DAY}&revision=3').status_code == 403


@pytest.mark.parametrize('profile', ['staff_guest', 'patient'])
def test_corrupt_catalog_is_explicit_no_store_503_without_replacement(editor_app, database_engine, profile):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    populate(client, database_engine)
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.settings SET setting_value=CAST(:value AS jsonb) '
                                'WHERE setting_key=:key'), {'value': json.dumps({'broken': True}), 'key': SETTING_PREFIX + profile})
    before = settings(database_engine)
    response = client.get('/admin/vorlagen')
    assert response.status_code == 503 and response.headers['Cache-Control'] == 'no-store'
    assert 'role="alert"' in response.text and 'Gespeicherte Druckvorlagen sind ungültig' in response.text
    assert 'data-template-id' not in response.text
    assert settings(database_engine) == before


@pytest.mark.parametrize('width', [390, 1440])
def test_catalog_browser_real_assets_revision_names_and_keyboard(
    editor_app, database_engine, browser, width,  # noqa: F811
):
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    populate(client, database_engine)
    before = settings(database_engine)
    server = make_server('127.0.0.1', 0, editor_app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base = f'http://127.0.0.1:{server.server_port}'
    # Consume fixture mutation flashes before capturing the returning reader.
    assert client.get('/admin/vorlagen').status_code == 200
    cookie = client.get_cookie(editor_app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    try:
        with browser.new_context(viewport={'width': width, 'height': 1100}, service_workers='block') as context:
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            page = context.new_page()
            responses = {}
            methods = []
            errors = []
            page.on('request', lambda request: methods.append(request.method))
            page.on('pageerror', lambda error: errors.append(str(error)))
            page.on('response', lambda response: responses.update({urlsplit(response.url).path: response.status}))
            result = page.goto(f'{base}/admin/vorlagen?week={DAY}', wait_until='networkidle')
            assert result is not None and result.status == 200
            expect(page.get_by_role('heading', level=1)).to_have_text('Vorlagen')
            assert page.locator('[data-template-id]').count() == 5
            assert page.locator('[data-template-id] use[href$="#tabler-edit"]').count() == 5
            weekly_sections = page.locator('.output-area-panels .output-layouts-section')
            assert weekly_sections.count() == 2
            assert weekly_sections.locator('table.admin-table tbody tr[data-template-id]').count() == 4
            for table in page.locator('main table.admin-table').all():
                headers = table.locator('thead th').evaluate_all(
                    'cells => cells.map(cell => cell.textContent.trim())')
                assert headers[0] == 'Vorlage', headers
                assert headers[1] in {'Version', 'Revision'}, headers
                assert headers[-2:] == ['Status', 'Aktionen'], headers
            assert weekly_sections.locator('[data-template-id="standard"]').count() == 2
            for section in weekly_sections.all():
                pane_id = section.evaluate('el => el.closest(".tab-pane").id')
                page.locator(f'[aria-controls="{pane_id}"]').click()
                current = section.locator('tr[data-template-id="standard"][data-current-template]')
                expect(current.get_by_role('heading')).to_have_text('Aktiver Herbst')
                expect(current.locator('.print-tpl-meta')).to_have_text('Version 2')
                expect(current.get_by_text('Neuer Entwurf: Winter & Festtage · Version 3', exact=True)).to_be_visible()
                expect(current.locator('[data-semantic="status.active"]')).to_be_visible()
            recipe_card = page.locator('section[aria-labelledby="recipe-templates-heading"]')
            assert recipe_card.locator('[data-template-id="standard"]').count() == 1
            expect(recipe_card.locator('.print-tpl-meta')).to_have_text('Revision 1')
            dish_card = page.locator('.print-related-grid > section').filter(
                has=page.get_by_role('heading', name='Gerichtvorlagen', exact=True),
            )
            if width == 1440:
                recipe_box = recipe_card.bounding_box()
                dish_box = dish_card.bounding_box()
                count_box = dish_card.locator('p').bounding_box()
                action_box = dish_card.get_by_role(
                    'link', name='Gerichtvorlagen öffnen', exact=True,
                ).bounding_box()
                assert recipe_box is not None and dish_box is not None
                assert count_box is not None and action_box is not None
                assert dish_box['height'] <= recipe_box['height']
                assert action_box['y'] - (count_box['y'] + count_box['height']) <= 24
            recipe_link = recipe_card.get_by_role('link', name='Standard bearbeiten', exact=True)
            recipe_target = urlsplit(recipe_link.get_attribute('href'))
            assert recipe_target.path == '/admin/vorlagen/rezepte'
            assert parse_qs(recipe_target.query) == {'template': ['standard'], 'revision': ['1']}
            assets = page.locator('link[rel="stylesheet"], script[src]').evaluate_all(
                "els => els.map(el => new URL(el.href || el.src).pathname)"
            )
            assert any('tabler' in asset and asset.endswith('.css') for asset in assets)
            assert any('tabler' in asset and asset.endswith('.js') for asset in assets)
            assert all(responses.get(asset) == 200 for asset in assets)
            assert not any(asset.endswith('/app.css') for asset in assets)
            assert page.locator('tr[data-template-id]').first.evaluate("el => getComputedStyle(el).display") == ('grid' if width == 390 else 'table-row')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if width == 1440:
                action_rows = page.locator('main table.admin-table').evaluate_all('''tables => tables.flatMap(table => {
                    if (table.getClientRects().length === 0) return [];
                    const header = table.querySelector('thead th:last-child');
                    if (!header || header.textContent.trim() !== 'Aktionen') return [];
                    const headerBox = header.getBoundingClientRect();
                    return [...table.querySelectorAll('tbody .admin-row-actions')].filter(
                        group => group.getClientRects().length,
                    ).map(group => {
                        const cell = group.closest('td');
                        const cellBox = cell.getBoundingClientRect();
                        const groupBox = group.getBoundingClientRect();
                        const tops = [...group.querySelectorAll('a, button')].map(
                            node => Math.round(node.getBoundingClientRect().top),
                        );
                        return {
                            oneRow: tops.length > 0 && tops.every(top => top === tops[0]),
                            groupHeight: Math.round(groupBox.height),
                            columnAligned: Math.abs(headerBox.left - cellBox.left) < 1
                                && Math.abs(headerBox.right - cellBox.right) < 1,
                        };
                    });
                })''')
                assert action_rows, 'visible vorlagen action groups'
                for row in action_rows:
                    assert row['oneRow'] and row['groupHeight'] <= 40, row
                    assert row['columnAligned'], row
            seen_hrefs: set[str] = set()

            def check_keyboard_link(link, *, require_focus: bool = True) -> None:
                href = link.get_attribute('href')
                if href in seen_hrefs:
                    return
                seen_hrefs.add(href)
                link.scroll_into_view_if_needed()
                box = link.bounding_box()
                classes = link.get_attribute('class') or ''
                minimum = 36 if 'ui-sem-control' in classes else 48
                assert box is not None and box['height'] >= minimum
                if not require_focus:
                    return
                link.focus()
                expect(link).to_be_focused()

            for link in page.locator('main form .btn:visible, main .print-related-grid .btn:visible, main .screens-grid .btn:visible').all():
                check_keyboard_link(link)
            page.keyboard.press('Escape')
            for menu in page.locator('main .screens-grid .admin-row-actions').all():
                expect(menu.locator('details, summary')).to_have_count(0)
                for link in menu.locator('a.btn').all():
                    expect(link).to_be_visible()
                    check_keyboard_link(link)
                page.keyboard.press('Escape')
            for section in weekly_sections.all():
                pane_id = section.evaluate('el => el.closest(".tab-pane").id')
                page.locator(f'[aria-controls="{pane_id}"]').click()
                pane = page.locator(f'#{pane_id}')
                for link in pane.locator('a.btn:visible').all():
                    check_keyboard_link(link)
                menus = section.locator('.admin-table-actions .admin-row-actions')
                expect(menus).to_have_count(2)
                for menu, template_name in zip(
                    menus.all(), ('Winter & Festtage', 'Festliche Kopie'), strict=True,
                ):
                    expect(menu).to_have_accessible_name(f'Aktionen für {template_name}')
                    expect(menu.locator('details, summary')).to_have_count(0)
                    for link in menu.locator('a.btn').all():
                        expect(link).to_be_visible()
                        expect(link).to_have_text('')
                        check_keyboard_link(link)
            for link in recipe_card.locator('.btn').all():
                check_keyboard_link(link)
            EVIDENCE_DIR.mkdir(parents=True, exist_ok=True)
            EVIDENCE_DIR.chmod(0o700)
            page.get_by_role('heading', level=1).click()
            page.keyboard.press('Escape')
            expect(page.locator('[role="tooltip"]:visible')).to_have_count(0)
            page.screenshot(path=str(EVIDENCE_DIR / f'catalog-{width}.png'), full_page=True)
            Path(EVIDENCE_DIR / f'catalog-{width}.png').chmod(0o600)
            page.locator('[aria-controls="output-cafeteria"]').click()
            cafeteria_section = weekly_sections.first
            editor = cafeteria_section.locator('[data-template-id="standard"]').get_by_role(
                'link', name='Winter & Festtage bearbeiten',
            )
            target = editor.get_attribute('href')
            editor.focus()
            editor.press('Enter')
            expect(page).to_have_url(base + target)
            expect(page.locator('input[name="name"]').first).to_have_value('Winter & Festtage')
            assert methods and set(methods) == {'GET'}
            assert not errors
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
    assert settings(database_engine) == before
