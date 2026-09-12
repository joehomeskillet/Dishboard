"""UX-01: cookbook list/editor hierarchy, native forms, and responsive evidence."""
from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, render_template, session
from playwright.sync_api import expect

from test_cookbook_routes import Forms
from test_cookbooks_browser import cookbook_server  # noqa: F401
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'ui-korrektur-0912' / 'cookbooks'
VIEWPORTS = (
    (1366, 768, '1366x768'),
    (1920, 1080, '1920x1080'),
    (768, 1024, '768x1024'),
    (390, 844, '390x844'),
    (720, 450, 'zoom-200'),
)


def _render_template(name: str, **values) -> str:
    app = Flask(
        'cookbook-ui-contract',
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
        static_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'static'),
    )
    app.config.update(SECRET_KEY='cookbook-ui-contract', TESTING=True)

    def fake_url_for(endpoint: str, **arguments) -> str:
        if endpoint == 'static':
            return '/static/' + arguments['filename']
        if endpoint == 'admin.cookbook_edit':
            return '/admin/kochbuecher/' + arguments['cookbook_id']
        if endpoint == 'admin.cookbook_status':
            return '/admin/kochbuecher/' + arguments['cookbook_id'] + '/status'
        if endpoint == 'admin.cookbook_recipes':
            return '/admin/kochbuecher/' + arguments['cookbook_id'] + '/rezepte'
        if endpoint == 'admin.cookbook_new':
            return '/admin/kochbuecher/neu'
        if endpoint == 'admin.cookbooks_list':
            return '/admin/kochbuecher'
        return '/' + endpoint.replace('.', '/')

    app.jinja_env.globals.update(url_for=fake_url_for, csrf_token=lambda: 'csrf')
    with app.test_request_context('/admin/kochbuecher'):
        session['user'] = {'id': 1, 'name': 'Küche'}
        return render_template(
            name,
            family='cafeteria',
            profile='staff_guest',
            roles=['Cafeteria.Admin'],
            can_browse_recipes=True,
            can_manage_users=True,
            can_configure_display=True,
            **values,
        )


def test_templates_expose_list_first_and_one_editor_primary_action(browser):  # noqa: F811
    book = SimpleNamespace(
        public_id='book-1',
        row_version=3,
        name='Testkochbuch',
        description='Beschreibung',
        active=True,
        recipe_public_ids=(),
    )
    list_html = _render_template(
        'admin/kochbuecher.html',
        rows=[book],
        page=1,
        has_next=False,
        search='',
        include_archived=False,
        can_write=True,
        prev_url='/admin/kochbuecher',
        next_url='/admin/kochbuecher?page=2',
    )
    editor_html = _render_template(
        'admin/kochbuch_editor.html',
        book=book,
        can_write=True,
        header_token='header-token',
        recipes_token='recipes-token',
        status_token='',
        status_action=None,
        options=[('recipe-1', 'Testrezept')],
        names={'recipe-1': 'Testrezept'},
        assignment_rows=[{'position': 1, 'public_id': '', 'url': None}],
    )
    page = browser.new_page(viewport={'width': 1366, 'height': 768})
    try:
        page.set_content(list_html)
        cards = page.locator('section[aria-label="Kochbücher"]')
        create = page.locator('details#cookbook-create')
        expect(cards).to_be_visible()
        expect(create).to_be_visible()
        assert cards.evaluate(
            '(list, disclosure) => Boolean('
            'list.compareDocumentPosition(disclosure) & Node.DOCUMENT_POSITION_FOLLOWING)',
            create.element_handle(),
        )

        page.set_content(editor_html)
        expect(page.get_by_role('heading', level=2, name='Rezept-Zuordnung')).to_be_visible()
        expect(page.get_by_role('button', name='Kochbuch speichern', exact=True)).to_be_visible()
        assignment = page.get_by_role('button', name='Zuordnung speichern', exact=True)
        assert 'btn-primary' not in (assignment.get_attribute('class') or '').split()
        assert page.locator('.btn-primary:visible').count() == 1
    finally:
        page.close()


def _create_book(server, name: str = 'Browserbuch') -> str:
    client = server['client']
    form = Forms(client.get('/admin/kochbuecher/neu').text).forms['/admin/kochbuecher/neu']
    form['name'] = name
    response = client.post('/admin/kochbuecher/neu', data=form)
    assert response.status_code == 303
    return urlsplit(response.location).path


def _context(browser, server, width: int, height: int, *, javascript: bool = True):  # noqa: F811
    context = browser.new_context(
        viewport={'width': width, 'height': height},
        java_script_enabled=javascript,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        reduced_motion='reduce',
        service_workers='block',
    )
    cookie = server['cookie']
    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': server['base']}])
    return context


def _assert_page_width(page, width: int):
    metrics = page.evaluate(
        """() => {
          const container = document.querySelector('.page-body > .container-xl')
            || document.querySelector('main.container-fluid');
          const block = [...container.children].find(element =>
            element.matches('.card, .cookbook-cards, section, .empty'));
          const style = getComputedStyle(container);
          const inner = container.getBoundingClientRect().width
            - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight);
          return {
            overflow: document.documentElement.scrollWidth > window.innerWidth + 1,
            ratio: block ? block.getBoundingClientRect().width / inner : 1,
          };
        }""",
    )
    assert not metrics['overflow']
    if width >= 1024:
        assert metrics['ratio'] >= 0.95


def _assert_core_controls(page):
    for control in page.locator('main :is(.btn, .form-control, .form-select, summary)').all():
        if not control.is_visible():
            continue
        box = control.bounding_box()
        assert box is not None and box['height'] >= 44


def test_cookbook_list_and_editor_follow_task_hierarchy_at_all_viewports(
    cookbook_server, browser,  # noqa: F811
):
    path = _create_book(cookbook_server)
    EVIDENCE.mkdir(parents=True, exist_ok=True)

    for width, height, label in VIEWPORTS:
        context = _context(browser, cookbook_server, width, height)
        page = context.new_page()
        try:
            page.goto(cookbook_server['base'] + '/admin/kochbuecher')
            cards = page.locator('section[aria-label="Kochbücher"]')
            create = page.locator('details#cookbook-create')
            expect(cards).to_be_visible()
            expect(create).not_to_have_attribute('open', '')
            expect(create.locator(':scope > summary').get_by_text('Kochbuch anlegen', exact=True)).to_be_visible()
            assert cards.evaluate(
                '(list, create) => Boolean(list.compareDocumentPosition(create) & Node.DOCUMENT_POSITION_FOLLOWING)',
                create.element_handle(),
            )
            assert page.locator('.btn-primary:visible').count() == 0
            _assert_page_width(page, width)
            _assert_core_controls(page)
            page.screenshot(
                path=str(EVIDENCE / f'kochbuecher-regular-{label}.png'), full_page=True,
            )

            page.goto(cookbook_server['base'] + '/admin/kochbuecher?q=KeinTreffer')
            expect(page.get_by_text('Keine passenden Kochbücher', exact=True)).to_be_visible()
            expect(page.locator('details#cookbook-create')).to_be_visible()
            _assert_page_width(page, width)
            page.screenshot(
                path=str(EVIDENCE / f'kochbuecher-empty-{label}.png'), full_page=True,
            )

            page.goto(cookbook_server['base'] + path)
            expect(page.get_by_role('heading', level=2, name='Rezept-Zuordnung')).to_be_visible()
            expect(page.get_by_text('Rezepte auswählen, Positionen festlegen und Zuordnung speichern.')).to_be_visible()
            expect(page.get_by_role('button', name='Kochbuch speichern', exact=True)).to_be_visible()
            assignment = page.get_by_role('button', name='Zuordnung speichern', exact=True)
            expect(assignment).to_be_visible()
            assert 'btn-primary' not in (assignment.get_attribute('class') or '').split()
            assert page.locator('.btn-primary:visible').count() == 1
            _assert_page_width(page, width)
            _assert_core_controls(page)
            page.screenshot(
                path=str(EVIDENCE / f'kochbuch-editor-regular-{label}.png'), full_page=True,
            )
        finally:
            context.close()


@pytest.mark.parametrize('javascript', [False, True])
def test_cookbook_native_posts_keep_targets_and_payloads(cookbook_server, browser, javascript):  # noqa: F811
    path = _create_book(cookbook_server, f'Vertrag {javascript}')
    context = _context(browser, cookbook_server, 1366, 768, javascript=javascript)
    page = context.new_page()
    try:
        page.goto(cookbook_server['base'] + path)
        page.get_by_label('Name', exact=True).fill(f'Gespeichert {javascript}')
        with page.expect_request(
            lambda request: request.method == 'POST' and urlsplit(request.url).path == path,
        ) as header_request:
            page.get_by_role('button', name='Kochbuch speichern', exact=True).click()
        header = parse_qs(header_request.value.post_data or '', keep_blank_values=True)
        assert set(header) == {'_csrf', '_form_context', 'row_version', 'name', 'description'}
        assert urlsplit(header_request.value.url).path == path

        assignment_form = page.locator(f'form[action="{path}/rezepte"]')
        assignment_form.locator('[name="recipe_public_ids"]').first.select_option(
            cookbook_server['first'],
        )
        with page.expect_request(
            lambda request: request.method == 'POST'
            and urlsplit(request.url).path == path + '/rezepte',
        ) as assignment_request:
            assignment_form.get_by_role('button', name='Zuordnung speichern', exact=True).click()
        assignment = parse_qs(assignment_request.value.post_data or '', keep_blank_values=True)
        assert set(assignment) == {
            '_csrf', '_form_context', 'row_version', 'recipe_positions', 'recipe_public_ids',
        }
        assert len(assignment['recipe_positions']) == len(assignment['recipe_public_ids'])
        assert urlsplit(assignment_request.value.url).path == path + '/rezepte'
    finally:
        context.close()


def test_cookbook_header_conflict_is_visible_and_preserves_input(cookbook_server, browser):  # noqa: F811
    path = _create_book(cookbook_server, 'Konfliktbuch')
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    for index, (width, height, label) in enumerate(VIEWPORTS):
        context = _context(browser, cookbook_server, width, height)
        page = context.new_page()
        try:
            draft_name = f'Mein ungespeicherter Name {index}'
            page.goto(cookbook_server['base'] + path)
            page.get_by_label('Name', exact=True).fill(draft_name)
            concurrent = Forms(cookbook_server['client'].get(path).text).forms[path]
            concurrent['name'] = f'Anderer Tab {index}'
            assert cookbook_server['client'].post(path, data=concurrent).status_code == 303

            with page.expect_response(
                lambda response: response.request.method == 'POST'
                and urlsplit(response.url).path == path,
            ) as response:
                page.get_by_role('button', name='Kochbuch speichern', exact=True).click()
            assert response.value.status == 409
            expect(page.get_by_label('Name', exact=True)).to_have_value(draft_name)
            expect(page.locator('#recipe-error')).to_be_focused()
            _assert_page_width(page, width)
            page.screenshot(
                path=str(EVIDENCE / f'kochbuch-editor-conflict-{label}.png'), full_page=True,
            )
        finally:
            context.close()
