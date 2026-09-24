"""MP-UI-DENSITY-COOKBOOKS: compact cookbook rows, native forms, viewport, reflow and real zoom evidence."""
from __future__ import annotations

import base64
import json
import struct
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path
from tempfile import TemporaryDirectory
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, render_template, session
from playwright.sync_api import expect, sync_playwright

from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui
from test_cookbook_routes import Forms
from test_cookbooks_browser import cookbook_server  # noqa: F401
from test_master_data_routes import app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude' / 'evidence' / 'cookbook-mobile-fix-0913' / 'after'
LONG_NAME = ('Sommergemüse mit Kräuterkartoffeln und hausgemachter Zitronensauce '
             'für die Gemeinschaftsküche am Sonntag')
LONG_DESCRIPTION = ('Saisonale Rezepte für die Gemeinschaftsküche, sortiert nach Aufwand. ' * 6).strip()
# CSS viewports only: reflow-320 is the 320 px reflow check, not browser zoom.
# Real 200 % browser zoom runs separately in a persistent Chromium profile.
VIEWPORTS = (
    (1440, 900, '1440x900'),
    (1024, 768, '1024x768'),
    (768, 1024, '768x1024'),
    (390, 844, '390x844'),
    (1920, 1080, '1920x1080'),
    (2560, 1440, '2560x1440'),
    (320, 844, 'reflow-320'),
)
# Header, status bar and one filter row occupy the top band; the first row follows.
FIRST_CONTENT_LIMIT = 400
# Manifest §5.2: compact working rows are typically 56–72 px and may grow when wrapping.
ROW_HEIGHT_LIMIT = 80
DENSITY_METRICS = '''() => {
  const top = selector => {
    const element = document.querySelector(selector);
    return element ? Math.round(element.getBoundingClientRect().top) : null;
  };
  const overflows = selector => [...document.querySelectorAll(selector)]
    .some(element => element.scrollWidth > element.clientWidth + 1);
  return {
    innerWidth, innerHeight,
    overflow: document.documentElement.scrollWidth > innerWidth + 1,
    documentHeight: document.documentElement.scrollHeight,
    firstCardTop: top('section[aria-label="Kochbücher"] article'),
    statusbar: document.querySelector('dl.admin-statusbar')?.innerText || '',
    primaryCount: document.querySelectorAll('main .btn-primary').length,
    cards: [...document.querySelectorAll('section[aria-label="Kochbücher"] article')].map(card => {
      const body = card.querySelector('.card-body');
      const title = card.querySelector('.card-title');
      const description = card.querySelector('.admin-list-subtitle');
      const action = card.querySelector('.cookbook-row-action');
      const count = card.querySelector('.cookbook-recipe-count');
      const rect = element => {
        const {x, y, width, height, right, bottom} = element.getBoundingClientRect();
        return {x, y, width, height, right, bottom};
      };
      const range = document.createRange();
      range.selectNodeContents(title);
      const style = getComputedStyle(body);
      return {
        name: title.textContent.trim(), card: rect(card), title: rect(title), text: rect(range),
        description: description ? rect(description) : null,
        action: rect(action), count: rect(count), countText: count.textContent.trim(),
        contentWidth: body.clientWidth - parseFloat(style.paddingLeft) - parseFloat(style.paddingRight),
        contentOverflow: body.scrollHeight > body.clientHeight + 1,
      };
    }),
    firstFieldLabelTop: top('label[for="cookbook-name"]'),
    firstFieldTop: top('#cookbook-name'),
    assignmentRows: [...document.querySelectorAll('form[action$="/rezepte"] tbody tr')]
      .map(row => Math.round(row.getBoundingClientRect().height)),
    cardTitleOverflow: overflows('section[aria-label="Kochbücher"] .card-title'),
    headingOverflow: overflows('h1'),
    iconButtons: [...document.querySelectorAll('main .btn-icon')].map(element => {
      const rect = element.getBoundingClientRect();
      return {name: element.getAttribute('aria-label'), width: Math.round(rect.width), height: Math.round(rect.height)};
    }),
  };
}'''


def _render_template(name: str, **values) -> str:
    app = Flask(
        'cookbook-ui-contract',
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
        static_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'static'),
    )
    app.config.update(SECRET_KEY='cookbook-ui-contract', TESTING=True)
    register_template_filters(app)
    register_ui(app)

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


def _book(**overrides) -> SimpleNamespace:
    values = dict(public_id='book-1', row_version=3, name='Testkochbuch', description='Beschreibung',
                  active=True, recipe_public_ids=())
    values.update(overrides)
    return SimpleNamespace(**values)


def _list_html(rows, *, search: str = '', can_write: bool = True) -> str:
    return _render_template(
        'admin/kochbuecher.html', rows=rows, page=1, has_next=False, search=search,
        include_archived=False, can_write=can_write, prev_url='/admin/kochbuecher',
        next_url='/admin/kochbuecher?page=2',
    )


def _editor_html(book, **overrides) -> str:
    values = dict(
        book=book, can_write=True, header_token='header-token', recipes_token='recipes-token',
        status_token='', status_action=None, options=[('recipe-1', 'Testrezept')],
        names={'recipe-1': 'Testrezept'},
        assignment_rows=[{'position': 1, 'public_id': 'recipe-1', 'url': '/admin/rezepte/recipe-1'},
                         {'position': 2, 'public_id': '', 'url': None}],
    )
    values.update(overrides)
    return _render_template('admin/kochbuch_editor.html', **values)


def _icon_control(control) -> tuple[str, str]:
    """Icon-only controls carry an accessible name, a native title and the same tooltip title."""
    assert not control.inner_text().strip()
    name = control.get_attribute('aria-label') or ''
    # Without JavaScript the native title stays; Tabler's tooltip moves it to data-bs-original-title.
    title = control.get_attribute('title') or control.get_attribute('data-bs-original-title') or ''
    assert name and title and control.get_attribute('data-bs-title') == title, (name, title)
    assert control.locator('svg[aria-hidden="true"] use').count() == 1
    return name, title


def _symbol(control) -> str:
    return (control.locator('use').get_attribute('href') or '').rsplit('#tabler-', 1)[-1]


def _open_archive_action(page):
    # P2 keeps rare actions behind a native, keyboard-operable disclosure.
    scroll_position = page.evaluate('[scrollX, scrollY]')
    details = page.locator('details.admin-form-rare')
    archive = details.get_by_role('link', name='Archivieren', exact=True, include_hidden=True)
    expect(archive).to_have_count(1)
    expect(archive).to_be_hidden()
    summary = details.locator('summary')
    expect(summary).to_have_text('Mehr')
    summary.focus()
    page.keyboard.press('Enter')
    expect(archive).to_be_visible()
    page.keyboard.press('Tab')
    expect(archive).to_be_focused()
    assert _symbol(archive) == 'archive'
    # Keyboard focus must not move the origin of density metrics/top captures.
    page.evaluate('([x, y]) => window.scrollTo(x, y)', scroll_position)
    return archive


def test_templates_keep_hierarchy_symbols_and_one_primary_action(browser):  # noqa: F811
    page = browser.new_page(viewport={'width': 1440, 'height': 900})
    try:
        page.set_content(_list_html([
            _book(), _book(public_id='book-2', name='Altes Buch', description='', active=False),
        ]))
        cards = page.locator('section[aria-label="Kochbücher"]')
        expect(cards).to_be_visible()
        expect(page.locator('details#cookbook-create')).to_have_count(0)
        expect(page.locator('dl.admin-statusbar')).to_contain_text('Aktiv')
        assert page.locator('main .btn-primary').count() == 1
        rows = cards.locator('article')
        assert rows.count() == 2
        edit = rows.nth(0).get_by_role('link', name='Testkochbuch bearbeiten', exact=True)
        view = rows.nth(1).get_by_role('link', name='Altes Buch öffnen', exact=True)
        expect(edit).to_contain_text('Bearbeiten')
        expect(view).to_contain_text('Öffnen')
        # actions.edit resolves to the vendored Tabler 'edit' symbol since the sprite package.
        assert (_symbol(edit), _symbol(view)) == ('edit', 'chevron-right')
        # Active is the default; only archived rows carry a status badge, so "Aktiv" is not repeated per row.
        expect(rows.nth(0).locator('.badge')).to_have_count(0)
        expect(rows.nth(1).locator('.badge')).to_have_text('Archiviert')
        assert 'Aktiv' not in cards.inner_text()
        expect(rows.nth(0).get_by_text('0 Rezepte', exact=True)).to_be_visible()

        page.set_content(_list_html([], search='Nichts'))
        no_match = page.locator('.empty[data-empty-kind="no_match"]')
        expect(no_match.get_by_text('Keine passenden Kochbücher', exact=True)).to_be_visible()
        expect(no_match.get_by_role('link', name='Zurücksetzen', exact=True)).to_be_visible()
        expect(page.locator('dl.admin-statusbar')).to_contain_text('Nichts')
        expect(page.locator('details#cookbook-create')).to_have_count(0)

        page.set_content(_list_html([]))
        none = page.locator('.empty[data-empty-kind="none"]')
        expect(none.get_by_text('Noch keine Kochbücher', exact=True)).to_be_visible()
        expect(none.get_by_role('link', name='Anlegen', exact=True)).to_be_visible()
        assert 'btn-primary' not in (none.locator('a').get_attribute('class') or '').split()
        expect(page.locator('details#cookbook-create')).to_have_count(0)
        assert page.locator('main .btn-primary').count() == 1
        expect(page.locator('main .btn-primary')).to_contain_text('Anlegen')

        page.set_content(_editor_html(_book()))
        expect(page.get_by_role('heading', level=2, name='Rezept-Zuordnung')).to_be_visible()
        expect(page.locator('dl.admin-statusbar')).to_contain_text('Aktiv')
        expect(page.locator('dl.admin-statusbar')).to_contain_text('0 Rezepte')
        header_save = page.locator('form[action="/admin/kochbuecher/book-1"]').get_by_role(
            'button', name='Speichern', exact=True,
        )
        assignment = page.locator('form[action$="/rezepte"]').get_by_role('button', name='Speichern', exact=True)
        expect(header_save).to_be_visible()
        expect(assignment).to_be_visible()
        assert 'btn-primary' not in (assignment.get_attribute('class') or '').split()
        assert page.locator('main .btn-primary').count() == 1
        # Each row input keeps its own accessible name; the visible header names the columns once.
        expect(page.get_by_label('Position 1', exact=True)).to_have_value('1')
        expect(page.get_by_label('Rezept 1', exact=True)).to_have_value('recipe-1')
        expect(page.get_by_label('Rezept 2', exact=True)).to_have_value('')
        assert page.locator('form[action$="/rezepte"] label').evaluate_all(
            'labels => labels.length === 4 && labels.every(label => label.classList.contains("visually-hidden"))',
        )
        expect(page.locator('form[action$="/rezepte"] thead')).to_contain_text('Position')
        expect(page.locator('form[action$="/rezepte"] thead')).to_contain_text('Rezept')
        open_recipe = page.get_by_role('link', name='Testrezept öffnen', exact=True)
        assert _icon_control(open_recipe) == ('Testrezept öffnen', 'Öffnen')
        assert _symbol(open_recipe) == 'chevron-right'
        archive = _open_archive_action(page)
        assert archive.get_attribute('href') == '/admin/kochbuecher/book-1/status'
        assert _symbol(archive) == 'archive'
        assert page.locator('form[action="/admin/kochbuecher/book-1"] textarea[rows="2"]').count() == 1

        page.set_content(_editor_html(_book(), status_action='cookbook.archive', status_token='status-token'))
        expect(page.get_by_role('heading', level=2, name='Kochbuch archivieren')).to_be_visible()
        confirm = page.get_by_role('button', name='Archivieren', exact=True)
        assert 'btn-danger' in (confirm.get_attribute('class') or '').split()
        assert _symbol(confirm) == 'archive'
        assert _symbol(page.get_by_role('link', name='Abbrechen', exact=True)) == 'x'
        assert page.get_by_role('link', name='Archivieren', exact=True).count() == 0
        assert page.locator('main .btn-primary').count() == 0
        status_form = Forms(page.content()).forms['/admin/kochbuecher/book-1/status']
        assert dict(status_form) == {
            '_csrf': 'csrf', '_form_context': 'status-token', 'row_version': '3',
            'status_action': 'cookbook.archive',
        }

        archived = _book(active=False, recipe_public_ids=('recipe-1',))
        page.set_content(_editor_html(archived, header_token='', recipes_token=''))
        expect(page.locator('section[aria-labelledby="cookbook-header-title"] .badge')).to_have_text('Archiviert')
        expect(page.locator('dl.admin-statusbar')).to_contain_text('Archiviert')
        expect(page.locator('dl.admin-statusbar')).to_contain_text('1 Rezept')
        assert page.locator('section[aria-labelledby="cookbook-header-title"] h3').count() == 0
        expect(page.get_by_text('Schreibgeschützt · zum Ändern zuerst reaktivieren.')).to_be_visible()
        reactivate = page.get_by_role('link', name='Reaktivieren', exact=True)
        assert _symbol(reactivate) == 'archive-off'
        assert page.locator('form[action$="/rezepte"]').count() == 0
        expect(page.locator('ol').get_by_role('link', name='Testrezept', exact=True)).to_be_visible()
        assert page.locator('main .btn-primary').count() == 1

        page.set_content(_editor_html(
            archived, header_token='', recipes_token='', status_token='status-token',
            status_action='cookbook.reactivate',
        ))
        confirm = page.get_by_role('button', name='Reaktivieren', exact=True)
        assert 'btn-primary' in (confirm.get_attribute('class') or '').split()
        assert _symbol(confirm) == 'archive-off'
        assert page.locator('main .btn-primary').count() == 1
    finally:
        page.close()


def _create_book(server, name: str = 'Browserbuch', description: str = '') -> str:
    client = server['client']
    form = Forms(client.get('/admin/kochbuecher/neu').text).forms['/admin/kochbuecher/neu']
    form['name'] = name
    if description:
        form['description'] = '\n' + description
    response = client.post('/admin/kochbuecher/neu', data=form)
    assert response.status_code == 303
    return urlsplit(response.location).path


def _assign(server, path: str, recipe_ids: list[str]) -> None:
    client = server['client']
    form = Forms(client.get(path).text).forms[path + '/rezepte']
    ids = list(form.getlist('recipe_public_ids'))
    ids[:len(recipe_ids)] = recipe_ids
    form.setlist('recipe_public_ids', ids)
    form.setlist('recipe_positions', list(form.getlist('recipe_positions')))
    assert client.post(path + '/rezepte', data=form).status_code == 303


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
            element.matches('.card, .cookbook-list, section, .empty, .admin-filter-bar'));
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
        if 'btn-icon' in (control.get_attribute('class') or '').split():
            assert box['width'] >= 48 and box['height'] >= 48
            _icon_control(control)


def _assert_mobile_cards(cards):
    for entry in cards:
        card, title, text = entry['card'], entry['title'], entry['text']
        assert not entry['contentOverflow'], entry
        assert title['width'] >= entry['contentWidth'] - 1, entry
        assert text['x'] >= title['x'] - 1 and text['right'] <= title['right'] + 1, entry
        assert text['y'] >= title['y'] - 1 and text['bottom'] <= title['bottom'] + 1, entry
        for name in ('count', 'action'):
            control = entry[name]
            assert control['x'] >= card['x'] and control['right'] <= card['right'] + 1, entry
            assert control['bottom'] <= card['bottom'] + 1, entry
        assert entry['action']['height'] >= 48, entry
        if entry['description']:
            assert entry['description']['bottom'] <= card['bottom'] + 1, entry
        assert card['bottom'] - max(entry['count']['bottom'], entry['action']['bottom']) <= 24, entry


def test_cookbook_list_and_editor_stay_compact_at_all_viewports(cookbook_server, browser):  # noqa: F811
    path = _create_book(cookbook_server)
    long_path = _create_book(cookbook_server, LONG_NAME, LONG_DESCRIPTION)
    _assign(cookbook_server, path, [cookbook_server['first']])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    metrics = {}

    for width, height, label in VIEWPORTS:
        context = _context(browser, cookbook_server, width, height)
        page = context.new_page()
        try:
            page.goto(cookbook_server['base'] + '/admin/kochbuecher')
            cards = page.locator('section[aria-label="Kochbücher"]')
            expect(cards).to_be_visible()
            expect(page.locator('details#cookbook-create')).to_have_count(0)
            expect(page.locator('dl.admin-statusbar')).to_be_visible()
            assert page.locator('main .btn-primary:visible').count() == 1
            expect(cards.get_by_role('link', name='Browserbuch bearbeiten', exact=True)).to_be_visible()
            expect(cards.get_by_role('link', name=f'{LONG_NAME} bearbeiten', exact=True)).to_be_visible()
            expect(cards.get_by_text('1 Rezept', exact=True)).to_be_visible()
            # The list shows a teaser; the full description stays editable in the editor.
            teaser = cards.get_by_text(LONG_DESCRIPTION[:60])
            expect(teaser).to_be_visible()
            assert len(teaser.inner_text()) < len(LONG_DESCRIPTION)
            _assert_page_width(page, width)
            _assert_core_controls(page)
            listed = page.evaluate(DENSITY_METRICS)
            assert not listed['overflow'] and not listed['cardTitleOverflow'], listed
            assert {entry['name'] for entry in listed['cards']} == {'Browserbuch', LONG_NAME}
            if width < 768:
                _assert_mobile_cards(listed['cards'])
                short, long = (next(entry for entry in listed['cards'] if entry['name'] == name)
                               for name in ('Browserbuch', LONG_NAME))
                # A short book remains a compact row beside a fully readable long fixture.
                assert short['card']['height'] <= 144 < long['card']['height'], listed
                assert short['countText'] == '1 Rezept' and long['countText'] == '0 Rezepte'
            if (width, height) == (1440, 900):
                assert listed['firstCardTop'] <= FIRST_CONTENT_LIMIT, listed
            page.screenshot(path=str(EVIDENCE / f'kochbuecher-regular-{label}.png'), full_page=True)

            page.goto(cookbook_server['base'] + '/admin/kochbuecher?q=KeinTreffer')
            no_match = page.locator('.empty[data-empty-kind="no_match"]')
            expect(no_match.get_by_text('Keine passenden Kochbücher', exact=True)).to_be_visible()
            expect(no_match.get_by_role('link', name='Zurücksetzen', exact=True)).to_be_visible()
            expect(page.locator('details#cookbook-create')).to_have_count(0)
            _assert_page_width(page, width)
            page.screenshot(path=str(EVIDENCE / f'kochbuecher-empty-{label}.png'), full_page=True)

            page.goto(cookbook_server['base'] + path)
            expect(page.get_by_role('heading', level=2, name='Rezept-Zuordnung')).to_be_visible()
            expect(page.locator('dl.admin-statusbar')).to_be_visible()
            expect(page.locator(f'form[action="{path}"]').get_by_role('button', name='Speichern', exact=True)).to_be_visible()
            assignment = page.locator(f'form[action="{path}/rezepte"]').get_by_role(
                'button', name='Speichern', exact=True,
            )
            expect(assignment).to_be_visible()
            assert 'btn-primary' not in (assignment.get_attribute('class') or '').split()
            assert page.locator('main .btn-primary:visible').count() == 1
            expect(page.get_by_label('Position 1', exact=True)).to_have_value('1')
            expect(page.get_by_label('Rezept 1', exact=True)).to_have_value(cookbook_server['first'])
            expect(page.get_by_role('link', name='Alpha öffnen', exact=True)).to_be_visible()
            expect(_open_archive_action(page)).to_have_attribute('href', path + '/status')
            expect(page.get_by_role('link', name='Archivieren', exact=True)).to_be_visible()
            _assert_page_width(page, width)
            _assert_core_controls(page)
            editor = page.evaluate(DENSITY_METRICS)
            assert not editor['overflow'] and len(editor['assignmentRows']) == 4, editor
            if width >= 992:
                assert max(editor['assignmentRows']) <= ROW_HEIGHT_LIMIT, editor
            if (width, height) == (1440, 900):
                assert editor['firstFieldLabelTop'] <= FIRST_CONTENT_LIMIT, editor
            page.screenshot(path=str(EVIDENCE / f'kochbuch-editor-regular-{label}.png'), full_page=True)

            page.goto(cookbook_server['base'] + long_path)
            expect(page.get_by_role('heading', level=1)).to_have_text(LONG_NAME)
            expect(page.locator('#cookbook-description')).to_have_value(LONG_DESCRIPTION)
            long_editor = page.evaluate(DENSITY_METRICS)
            assert not long_editor['overflow'] and not long_editor['headingOverflow'], long_editor
            page.screenshot(path=str(EVIDENCE / f'kochbuch-editor-long-{label}.png'), full_page=True)
            metrics[label] = {'list': listed, 'editor': editor, 'long_editor': long_editor}
        finally:
            context.close()
    (EVIDENCE / 'density-metrics.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2))


@pytest.mark.parametrize('javascript', [False, True])
def test_cookbook_native_posts_keep_targets_and_payloads(cookbook_server, browser, javascript):  # noqa: F811
    path = _create_book(cookbook_server, f'Vertrag {javascript}')
    context = _context(browser, cookbook_server, 1440, 900, javascript=javascript)
    page = context.new_page()
    try:
        page.goto(cookbook_server['base'] + path)
        page.get_by_label('Name', exact=True).fill(f'Gespeichert {javascript}')
        with page.expect_request(
            lambda request: request.method == 'POST' and urlsplit(request.url).path == path,
        ) as header_request:
            page.locator(f'form[action="{path}"]').get_by_role('button', name='Speichern', exact=True).click()
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
            assignment_form.get_by_role('button', name='Speichern', exact=True).click()
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
    for index, (width, height, label) in enumerate(VIEWPORTS[:4]):
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
                page.locator(f'form[action="{path}"]').get_by_role('button', name='Speichern', exact=True).click()
            assert response.value.status == 409
            expect(page.get_by_label('Name', exact=True)).to_have_value(draft_name)
            expect(page.locator('#recipe-error')).to_be_focused()
            _assert_page_width(page, width)
            page.screenshot(
                path=str(EVIDENCE / f'kochbuch-editor-conflict-{label}.png'), full_page=True,
            )
        finally:
            context.close()


def _tab_to(page, target, limit: int = 12) -> None:
    for _ in range(limit):
        if target.evaluate('el => el === document.activeElement'):
            return
        page.keyboard.press('Tab')
    raise AssertionError('keyboard focus never reached the target control')


def _focus_ring(control) -> dict:
    ring = control.evaluate('''el => {
      const style = getComputedStyle(el);
      return {outlineStyle: style.outlineStyle, outlineWidth: style.outlineWidth, boxShadow: style.boxShadow};
    }''')
    assert (ring['outlineStyle'] != 'none' and ring['outlineWidth'] != '0px') or ring['boxShadow'] != 'none', ring
    return ring


@pytest.mark.parametrize('width,height,label', [(1440, 900, '1440x900'), (390, 844, '390x844')])
def test_cookbook_pages_work_without_javascript_and_by_keyboard(
    cookbook_server, browser, width, height, label,  # noqa: F811
):
    name = f'Tastaturbuch {label}'
    path = _create_book(cookbook_server, name)
    _assign(cookbook_server, path, [cookbook_server['second']])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    context = _context(browser, cookbook_server, width, height, javascript=False)
    page = context.new_page()
    try:
        page.goto(cookbook_server['base'] + '/admin/kochbuecher')
        edit = page.get_by_role('link', name=f'{name} bearbeiten', exact=True)
        expect(edit).to_contain_text('Bearbeiten')
        expect(page.locator('dl.admin-statusbar')).to_be_visible()
        page.get_by_label('Suche', exact=True).focus()
        _tab_to(page, page.get_by_label('Archivierte einschliessen', exact=True))
        _tab_to(page, page.get_by_role('button', name='Suchen', exact=True))
        _tab_to(page, edit)
        expect(edit).to_be_focused()
        rings = {'row-action': _focus_ring(edit)}
        expect(page.locator('main .btn-primary')).to_contain_text('Anlegen')
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
        page.screenshot(path=str(EVIDENCE / f'kochbuecher-nojs-{label}.png'), full_page=True)

        page.goto(cookbook_server['base'] + path)
        expect(page.get_by_label('Name', exact=True)).to_be_visible()
        expect(page.locator('#cookbook-description')).to_be_visible()
        expect(page.locator(f'form[action="{path}"]').get_by_role('button', name='Speichern', exact=True)).to_be_visible()
        expect(page.locator(f'form[action="{path}/rezepte"]').get_by_role(
            'button', name='Speichern', exact=True,
        )).to_be_visible()
        position = page.get_by_label('Position 1', exact=True)
        position.focus()
        position.fill('5')
        page.keyboard.press('Tab')
        expect(page.get_by_label('Rezept 1', exact=True)).to_be_focused()
        page.keyboard.press('Tab')
        open_recipe = page.get_by_role('link', name='Beta öffnen', exact=True)
        expect(open_recipe).to_be_focused()
        assert _icon_control(open_recipe) == ('Beta öffnen', 'Öffnen')
        rings['recipe-link'] = _focus_ring(open_recipe)
        expect(position).to_have_value('5')
        archive = _open_archive_action(page)
        expect(archive).to_have_attribute('href', path + '/status')
        rings['archive-link'] = _focus_ring(archive)
        assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
        page.screenshot(path=str(EVIDENCE / f'kochbuch-editor-nojs-{label}.png'), full_page=True)
        (EVIDENCE / f'focus-rings-{label}.json').write_text(json.dumps(rings, indent=2))
    finally:
        context.close()


def _native_viewport_capture(page, destination: Path) -> dict:
    """Capture the native (zoomed) viewport via CDP, like the verified shell zoom evidence.

    A beyond-viewport capture lays out hidden <details> children in Chromium, so the
    list page with its create disclosure is captured viewport by viewport instead.
    """
    cdp = page.context.new_cdp_session(page)
    try:
        layout = cdp.send('Page.getLayoutMetrics')
        png = base64.b64decode(cdp.send('Page.captureScreenshot', {
            'format': 'png', 'captureBeyondViewport': False,
        })['data'], validate=True)
    finally:
        cdp.detach()
    destination.write_bytes(png)
    assert png[:8] == b'\x89PNG\r\n\x1a\n' and png[12:16] == b'IHDR'
    width, height = struct.unpack('>II', png[16:24])
    outer_width, visual_height = page.evaluate('[outerWidth, visualViewport.height]')
    assert width == outer_width and height == round(visual_height * 2), (width, height, outer_width, visual_height)
    return {'layout': layout, 'png': {'width': width, 'height': height}}


def test_real_browser_zoom_keeps_cookbook_rows_and_labels(cookbook_server, browser, tmp_path):  # noqa: F811
    path = _create_book(cookbook_server, 'Zoombuch')
    _create_book(cookbook_server, LONG_NAME, LONG_DESCRIPTION)
    _assign(cookbook_server, path, [cookbook_server['first']])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    base, cookie = cookbook_server['base'], cookbook_server['cookie']
    with TemporaryDirectory(prefix='cookbook-native-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True, base_url=base,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
            cdp = context.new_cdp_session(page)
            proof = {}
            for name, route in (('list', '/admin/kochbuecher'), ('editor', path)):
                page.goto(base + route)
                layout = cdp.send('Page.getLayoutMetrics')
                assert layout['cssVisualViewport']['zoom'] == 2, layout
                assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
                assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                _assert_core_controls(page)
                if name == 'list':
                    expect(page.get_by_role('link', name='Zoombuch bearbeiten', exact=True)).to_be_visible()
                    expect(page.get_by_role('link', name=f'{LONG_NAME} bearbeiten', exact=True)).to_be_visible()
                    expect(page.get_by_text('1 Rezept', exact=True)).to_be_visible()
                    cards = page.evaluate(DENSITY_METRICS)['cards']
                    _assert_mobile_cards(cards)
                    assert next(entry for entry in cards if entry['name'] == 'Zoombuch')['card']['height'] <= 144
                else:
                    expect(page.locator(f'form[action="{path}"]').get_by_role(
                        'button', name='Speichern', exact=True,
                    )).to_be_visible()
                    expect(page.locator(f'form[action="{path}/rezepte"]').get_by_role(
                        'button', name='Speichern', exact=True,
                    )).to_be_visible()
                    expect(page.get_by_role('link', name='Alpha öffnen', exact=True)).to_be_visible()
                    expect(_open_archive_action(page)).to_have_attribute('href', path + '/status')
                    expect(page.get_by_role('link', name='Archivieren', exact=True)).to_be_visible()
                captures = {'top': _native_viewport_capture(page, EVIDENCE / f'native-200-{name}.png')}
                if name == 'list':
                    page.get_by_role('heading', level=2, name=LONG_NAME, exact=True).scroll_into_view_if_needed()
                    captures['long-card'] = _native_viewport_capture(page, EVIDENCE / 'native-200-list-long-card.png')
                if name == 'editor':
                    page.locator('#cookbook-recipes-title').scroll_into_view_if_needed()
                    captures['assignment'] = _native_viewport_capture(
                        page, EVIDENCE / f'native-200-{name}-assignment.png',
                    )
                proof[name] = {'layout': layout, 'captures': captures, 'metrics': page.evaluate(DENSITY_METRICS)}
            (EVIDENCE / 'native-200.cdp.json').write_text(json.dumps(proof, indent=2))


def test_cookbook_frame_viewports_statusbar_and_no_overflow(cookbook_server):  # noqa: F811
    """Independent Chromium start: 360/768/1024/1440, No-JS and keyboard, status bar and overflow."""
    path = _create_book(cookbook_server, 'Rahmenbuch')
    _create_book(cookbook_server, LONG_NAME, LONG_DESCRIPTION)
    _assign(cookbook_server, path, [cookbook_server['first']])
    cookie = cookbook_server['cookie']
    base = cookbook_server['base']

    def inspect() -> None:
        with sync_playwright() as playwright:
            instance = playwright.chromium.launch(
                headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'],
            )
            try:
                for javascript in (False, True):
                    context = instance.new_context(
                        java_script_enabled=javascript, locale='de-CH', timezone_id='Europe/Zurich',
                        reduced_motion='reduce', service_workers='block',
                    )
                    context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
                    page = context.new_page()
                    try:
                        for width, height in ((360, 800), (768, 1024), (1024, 768), (1440, 900)):
                            page.set_viewport_size({'width': width, 'height': height})
                            assert page.goto(base + '/admin/kochbuecher').status == 200
                            page.evaluate('document.fonts.ready')
                            listed = page.evaluate(DENSITY_METRICS)
                            assert not listed['overflow'], listed
                            expect(page.locator('main .btn-primary')).to_have_count(1)
                            expect(page.locator('dl.admin-statusbar')).to_contain_text('Aktiv')
                            if width == 1440:
                                assert listed['firstCardTop'] is not None
                                assert listed['firstCardTop'] <= FIRST_CONTENT_LIMIT, listed
                                short = next(entry for entry in listed['cards'] if entry['name'] == 'Rahmenbuch')
                                assert short['card']['height'] <= 96, listed
                            if width == 360:
                                _assert_mobile_cards(listed['cards'])
                            assert page.goto(base + path).status == 200
                            editor = page.evaluate(DENSITY_METRICS)
                            assert not editor['overflow'], editor
                            expect(page.locator('main .btn-primary')).to_have_count(1)
                            expect(page.locator('dl.admin-statusbar')).to_contain_text('1 Rezept')
                        page.set_viewport_size({'width': 360, 'height': 800})
                        page.goto(base + '/admin/kochbuecher')
                        page.get_by_label('Suche', exact=True).focus()
                        page.keyboard.press('Tab')
                        expect(page.get_by_label('Archivierte einschliessen', exact=True)).to_be_focused()
                        _focus_ring(page.get_by_label('Archivierte einschliessen', exact=True))
                    finally:
                        context.close()
            finally:
                instance.close()

    with ThreadPoolExecutor(max_workers=1) as worker:
        worker.submit(inspect).result()


def test_p3_polish_cookbook_editor_primary_stack_hint(cookbook_server, browser):  # noqa: F811
    path = _create_book(cookbook_server, 'Polishbuch')
    _assign(cookbook_server, path, [cookbook_server['first']])
    context = _context(browser, cookbook_server, 360, 800)
    page = context.new_page()
    try:
        page.goto(cookbook_server['base'] + path)
        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
        _assert_page_width(page, 360)
        row = page.locator('table.admin-table--stack tbody tr').first
        assert row.evaluate("e => getComputedStyle(e).display") == 'grid'
        expect(page.locator('td[data-label="Position"]').first).to_be_visible()
        page.goto(cookbook_server['base'] + path + '/status')
        page.get_by_role('button', name='Archivieren', exact=True).click()
        page.goto(cookbook_server['base'] + path)
        trigger = page.locator('summary[aria-describedby="cookbook-readonly-hint"]')
        trigger.focus()
        expect(trigger).to_be_focused()
        page.keyboard.press('Enter')
        expect(page.locator('#cookbook-readonly-hint')).to_be_visible()
        _assert_page_width(page, 360)
    finally:
        page.close()
        context.close()
