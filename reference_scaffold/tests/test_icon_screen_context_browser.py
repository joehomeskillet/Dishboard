"""Screen context stays distinct while repeated normal-state prose is removed."""
from __future__ import annotations

import json

import pytest
from bs4 import BeautifulSoup
from flask import url_for
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria import screen_templates
from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_screen_template_browser import published_app, server  # noqa: F401
from test_screen_template_routes import screen_app  # noqa: F401
from test_screen_template_store import state
from test_ui_list_family_browser import MEASURE_JS
from test_ui_output_hubs_browser import empty_hub_app, empty_hub_server  # noqa: F401


@pytest.fixture(params=['default', 'mixed'])
def screen_case(published_app, database_engine, request):  # noqa: F811
    if request.param == 'mixed':
        client, actor = _login(published_app, database_engine, ['Cafeteria.Admin'])
        with client.session_transaction() as session:
            actor_version = session['authz_version']
        screen_templates.activate(
            published_app.extensions['cafeteria_db'], 'staff_guest', actor,
            actor_version, 0, 'cafeteria-week-text', 1,
        )
    with database_engine.connect() as connection:
        assignments = {profile: screen_templates.read_assignment(connection, profile)
                       for profile in ('staff_guest', 'patient')}
    assert assignments['patient'].version == 0
    assert assignments['staff_guest'].version == (1 if request.param == 'mixed' else 0)
    return request.param, assignments


def _page(app, engine, pw_browser, base_url, role, width, javascript, *, touch=False):
    client, _ = _login(app, engine, [role])
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    context = pw_browser.new_context(
        base_url=base_url, viewport={'width': width, 'height': 900 if width == 1440 else 844},
        java_script_enabled=javascript, reduced_motion='reduce', has_touch=touch,
    )
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base_url}])
    return context, context.new_page()


def _targets(app):
    rows = {}
    with app.test_request_context():
        for profile, endpoint, family in (
            ('staff_guest', 'cafeteria', 'cafeteria'), ('patient', 'patient', 'patienten'),
        ):
            rows[f'{endpoint}-public-title'] = {
                'profile': profile,
                'outputs': [url_for(f'public.{endpoint}_{suffix}')
                            for suffix in ('today', 'week', 'week_without_images')],
                'assignment': url_for('admin.screen_template_assignment', family=family),
            }
            rows[f'{endpoint}-signage-title'] = {
                'profile': profile,
                'outputs': [url_for(f'signage.{endpoint}_{suffix}') for suffix in ('day', 'week')],
            }
    return rows


@pytest.mark.parametrize('role', ['Cafeteria.Admin', 'Cafeteria.Editor', 'Cafeteria.Publisher'])
@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('width', [1440, 390])
def test_screen_context_preserves_assignments_destinations_and_native_navigation(
    published_app, database_engine, browser, server, screen_case, tmp_path,  # noqa: F811
    role, javascript, width,
):
    context, page = _page(published_app, database_engine, browser, server, role, width, javascript)
    case, assignments = screen_case
    before = state(database_engine)
    writes, errors = [], []
    page.on('request', lambda request: writes.append(request.method) if request.method != 'GET' else None)
    page.on('pageerror', lambda error: errors.append(str(error)))
    targets = _targets(published_app)
    try:
        response = page.goto('/admin/screens', wait_until='networkidle')
        assert response.status == 200 and response.headers['cache-control'] == 'no-store'
        page.evaluate('document.fonts.ready')
        expect(page.get_by_role('heading', level=1)).to_have_text('Bildschirme')
        expect(page.locator('.page-header')).to_contain_text(
            'Veröffentlichte Tages- und Wochenpläne für Web und Bildschirme öffnen.')
        expect(page.locator('.screen-card')).to_have_count(4)
        expect(page.locator('table > tbody.screen-card')).to_have_count(4)
        expect(page.locator('main form, main .btn-primary, main details[open]')).to_have_count(0)
        measured = page.evaluate(MEASURE_JS)['lists']
        assert len(measured) == 1 and measured[0]['total'] == 4
        assert measured[0]['row']['divider'].startswith('1px solid ')
        evidence = page.evaluate('''() => {
            const main = document.querySelector('main').getBoundingClientRect();
            const rows = [...document.querySelectorAll('.screen-card')];
            return {viewport: {width: innerWidth, height: innerHeight}, scrollY,
                firstOffset: rows[0].getBoundingClientRect().top - main.top,
                headerCards: document.querySelectorAll('.admin-statusbar-item').length,
                rows: rows.map(row => {
                    const main = row.querySelector(':scope > tr:first-child');
                    const preview = row.querySelector(':scope > tr:last-child');
                    const cell = preview.querySelector('td');
                    const summary = row.querySelector('.screen-preview-details > summary');
                    const outer = getComputedStyle(preview), inner = getComputedStyle(cell);
                    const vertical = style => ['paddingTop', 'paddingBottom', 'borderTopWidth', 'borderBottomWidth']
                        .reduce((sum, key) => sum + parseFloat(style[key]), 0);
                    return {id: row.getAttribute('aria-labelledby'),
                        height: row.getBoundingClientRect().height, text: row.innerText,
                        mainDivider: getComputedStyle(main).borderBottomWidth,
                        divider: outer.borderBottomWidth,
                        cellDividers: [...row.querySelectorAll('th, td')].map(el => getComputedStyle(el).borderBottomWidth),
                        previewRowHeight: preview.getBoundingClientRect().height,
                        summaryHeight: summary.getBoundingClientRect().height,
                        previewVerticalInsets: vertical(outer) + vertical(inner)};
                }),
                links: [...document.querySelectorAll('main a[href]')].map(a => ({
                    href: a.getAttribute('href'), name: a.getAttribute('aria-label')})),
                frames: [...document.querySelectorAll('main iframe')].map(frame => ({
                    src: frame.getAttribute('src'), title: frame.title})),
                overflow: document.documentElement.scrollWidth > innerWidth + 1};
        }''')
        assert not evidence['overflow'] and evidence['scrollY'] == 0
        evidence.update(case=case, role=role, javascript=javascript,
                        assignments={profile: assignment.document() for profile, assignment in assignments.items()})
        name = f'screens-{case}-{role.rsplit(".", 1)[1]}-{width}-js{javascript}'
        (tmp_path / f'{name}.json').write_text(json.dumps(evidence, ensure_ascii=False, indent=2))
        page.screenshot(path=str(tmp_path / f'{name}.png'), full_page=True)
        for row in evidence['rows']:
            assert row['mainDivider'] == '0px' and row['divider'] == '1px'
            assert all(value == '0px' for value in row['cellDividers'])
            assert abs(row['previewRowHeight'] - row['summaryHeight'] - row['previewVerticalInsets']) <= 2

        all_links = []
        for identifier, target in targets.items():
            row = page.locator(f'.screen-card[aria-labelledby="{identifier}"]')
            expect(row).to_have_js_property('tagName', 'TBODY')
            heading = row.locator('th[scope="rowgroup"]')
            heading_id = heading.get_attribute('id')
            assert heading_id and page.locator(f'[id="{heading_id}"]').count() == 1
            expect(row.locator(':scope > tr')).to_have_count(2)
            expect(row.locator('td[colspan="2"]')).to_have_attribute('headers', heading_id)
            assert row.evaluate('''row => {
                const nodes = ['.admin-list-primary', '.admin-row-actions a:first-child', '.admin-row-actions a:nth-child(2)', '.screen-preview-details > summary']
                    .map(selector => row.querySelector(selector));
                return nodes.every((node, i) => node && (!i || (nodes[i - 1].compareDocumentPosition(node) & Node.DOCUMENT_POSITION_FOLLOWING)));
            }''')
            outputs = target['outputs']
            expected = outputs + ([target['assignment']] if 'assignment' in target else [])
            assert row.locator('a[href]').evaluate_all('links => links.map(a => a.getAttribute("href"))') == expected
            assert row.locator('iframe').evaluate_all('frames => frames.map(frame => frame.getAttribute("src"))') == outputs
            all_links.extend(expected)
            for destination in outputs:
                result = page.request.get(destination)
                assert result.status == 200 and result.headers['x-snapshot-revision']
                assert '?' not in destination
            if 'assignment' in target:
                assignment = assignments[target['profile']]
                expect(row.locator('.screen-status strong')).to_have_text(assignment.template.name)
                expect(row.locator('.screen-status .badge')).to_have_text('Vorgabe' if assignment.version == 0 else 'Aktiv')
                canonical = page.request.get(outputs[1])
                assert canonical.headers['x-screen-template-revision'] == assignment.revision
                assigned = page.request.get(target['assignment'])
                assert assigned.status == 200 and assigned.headers['cache-control'] == 'no-store'
                document = BeautifulSoup(assigned.text(), 'html.parser')
                form = document.select_one('#screen-assignment-details form')
                assert form['action'] == target['assignment'] and form['method'] == 'post'
                assert form.select_one('[name="version"]')['value'] == str(assignment.version)
                assert form.select_one('[name="renderer_revision"]')['value'] == '1'
                assert form.select_one('[name="template_id"][checked]')['value'] == assignment.template.id
                assert bool(form.select('[data-semantic="actions.save"]')) == (role == 'Cafeteria.Admin')

            preview = row.locator('.screen-preview-details > summary')
            actions = row.locator('.admin-row-actions a[href]')
            expect(row.locator('[data-semantic="actions.more"]')).to_have_count(0)
            actions.first.focus()
            for action in actions.all():
                expect(action).to_be_visible()
                expect(action).to_be_focused()
                assert action.evaluate('el => parseFloat(getComputedStyle(el).outlineWidth)') >= 2
                page.keyboard.press('Tab')
            expect(preview).to_be_focused()
            first_item = actions.nth(1)
            first_item.focus()
            expect(first_item).to_be_visible()
            if javascript:
                expect(first_item).to_be_focused()
                tooltip = page.get_by_role('tooltip', name=first_item.get_attribute('aria-label'), exact=True)
                expect(tooltip).to_be_visible()
                page.keyboard.press('Escape')
                expect(page.get_by_role('tooltip')).to_have_count(0)
                expect(first_item).to_be_focused()
                page.keyboard.press('Escape')
            expect(first_item).to_be_focused()
            if javascript:
                expect(page.get_by_role('tooltip')).to_have_count(0)
            preview.press('Enter')
            expect(row.locator('.screen-preview-details')).to_have_attribute('open', '')
            expect(preview).to_be_focused()
            expect(row.locator('iframe').first).to_be_visible()
            group_box = row.bounding_box()
            cell_box = row.locator('td[colspan="2"]').bounding_box()
            row_content = row.locator('td[colspan="2"]').evaluate('''cell => {
                const row = cell.parentElement;
                const box = row.getBoundingClientRect();
                const style = getComputedStyle(row);
                const paddingLeft = parseFloat(style.paddingLeft);
                const paddingRight = parseFloat(style.paddingRight);
                const borderLeft = parseFloat(style.borderLeftWidth);
                const borderRight = parseFloat(style.borderRightWidth);
                return {
                    x: box.x, width: box.width, paddingLeft, paddingRight,
                    borderLeft, borderRight,
                    left: box.left + borderLeft + paddingLeft,
                    right: box.right - borderRight - paddingRight,
                };
            }''')
            preview_box = row.locator('.screen-preview:visible').first.bounding_box()
            (tmp_path / f'{name}-{identifier}-preview.json').write_text(json.dumps({
                'group': group_box, 'cell': cell_box, 'row_content': row_content,
                'preview': preview_box,
            }, indent=2))
            if identifier == 'cafeteria-public-title':
                page.screenshot(path=str(tmp_path / f'{name}-preview.png'), full_page=True)
            assert abs(cell_box['x'] - row_content['left']) <= 1
            assert abs(cell_box['x'] + cell_box['width'] - row_content['right']) <= 1
            assert preview_box['width'] >= 220 and preview_box['x'] >= group_box['x']
            assert preview_box['x'] + preview_box['width'] <= group_box['x'] + group_box['width'] + 1
            preview.press('Enter')
            expect(row.locator('.screen-preview-details')).not_to_have_attribute('open', '')
            with page.expect_response(lambda result: result.request.is_navigation_request()
                                      and result.request.frame == page.main_frame) as navigation:
                row.locator('a[href]').first.press('Enter')
            page.wait_for_url(server + outputs[0])
            assert navigation.value.status == 200 and page.url == server + outputs[0]
            assert page.goto('/admin/screens').status == 200
        assert len(all_links) == len(set(all_links)) == 12
        assert not writes and not errors
        assert state(database_engine) == before
    finally:
        context.close()


@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('width', [1440, 390])
def test_screen_actions_keep_real_coarse_pointer_geometry(
    published_app, database_engine, browser, server, javascript, width, tmp_path,  # noqa: F811
):
    context, page = _page(published_app, database_engine, browser, server,
                          'Cafeteria.Admin', width, javascript, touch=True)
    try:
        assert page.goto('/admin/screens', wait_until='networkidle').status == 200
        assert page.evaluate("matchMedia('(pointer: coarse)').matches && matchMedia('(any-pointer: coarse)').matches")
        controls = page.locator('.screen-card .ui-sem-control--icon-only:visible')
        expect(controls).to_have_count(12)
        geometry = controls.evaluate_all('elements => elements.map(el => ({name: el.getAttribute("aria-label"), width: el.getBoundingClientRect().width, height: el.getBoundingClientRect().height}))')
        assert all(item['width'] == item['height'] == 44 for item in geometry)
        for menu in page.locator('.screen-card .admin-row-actions').all():
            expect(menu.locator('details, summary')).to_have_count(0)
            for action in menu.locator('a').all():
                expect(action).to_be_visible()
                box = action.bounding_box()
                assert box['width'] >= 44 and box['height'] >= 44
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        (tmp_path / f'screens-coarse-{width}-js{javascript}.json').write_text(json.dumps(geometry, indent=2))
        page.evaluate('scrollTo(0, 0)')
        page.screenshot(path=str(tmp_path / f'screens-coarse-{width}-js{javascript}.png'), full_page=True)
    finally:
        context.close()


def test_normal_screen_header_keeps_context_once(
    published_app, database_engine, browser, server, screen_case,  # noqa: F811
):
    context, page = _page(published_app, database_engine, browser, server, 'Cafeteria.Admin', 1440, True)
    try:
        assert page.goto('/admin/screens').status == 200
        expect(page.locator('.admin-statusbar-item')).to_have_count(0)
        expect(page.locator('.screen-status')).to_have_count(2)
        expect(page.locator('.screen-status strong')).to_have_text([
            screen_case[1]['staff_guest'].template.name, screen_case[1]['patient'].template.name,
        ])
        expect(page.get_by_text('Vorlage für Web-Wochenplan:', exact=False)).to_have_count(2)
    finally:
        context.close()


@pytest.mark.parametrize('javascript', [True, False])
@pytest.mark.parametrize('width', [1440, 390])
def test_screen_empty_publication_and_corrupt_assignment_remain_explicit(
    empty_hub_app, empty_hub_server, database_engine, browser, javascript, width, tmp_path,  # noqa: F811
):
    context, page = _page(empty_hub_app, database_engine, browser, empty_hub_server,
                          'Cafeteria.Editor', width, javascript)
    before = state(database_engine)
    try:
        assert page.goto('/admin/screens').status == 200
        expect(page.locator('.screen-status .badge')).to_have_text(['Vorgabe', 'Vorgabe'])
        first = page.locator('.screen-card').first
        first.locator('.screen-preview-details > summary').press('Enter')
        expect(page.frame_locator('.screen-preview iframe').first.get_by_text(
            'Speiseplan nicht verfügbar', exact=False)).to_be_visible()
        page.evaluate('window.scrollTo(0, 0)')
        page.screenshot(path=str(tmp_path / f'screen-empty-{width}-js{javascript}.png'), full_page=True)
        assert state(database_engine) == before
        with database_engine.begin() as connection:
            connection.execute(text('''INSERT INTO cafeteria.settings(setting_key, setting_value)
                VALUES (:key, CAST(:value AS jsonb))'''),
                {'key': screen_templates.key('patient'), 'value': json.dumps({'schema_version': 999})})
        corrupted = state(database_engine)
        response = page.goto('/admin/screens')
        assert response.status == 503 and response.headers['cache-control'] == 'no-store'
        expect(page.get_by_role('heading', level=1)).to_have_text(
            'Bildschirmvorlagen vorübergehend nicht verfügbar')
        expect(page.locator('.screen-card')).to_have_count(0)
        expect(page.get_by_text('Die gespeicherte Bildschirmvorlage ist zurzeit nicht erreichbar.', exact=True)).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        page.screenshot(path=str(tmp_path / f'screen-unavailable-{width}-js{javascript}.png'), full_page=True)
        assert state(database_engine) == corrupted
    finally:
        context.close()
