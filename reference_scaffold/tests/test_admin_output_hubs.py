"""Output navigation uses authoritative roles and existing rendered destinations."""
from __future__ import annotations

import re

import threading
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from flask import Blueprint, Flask
from playwright.sync_api import expect
from sqlalchemy import text
from werkzeug.serving import make_server

import cafeteria
from cafeteria import dish_template_store
from cafeteria.admin import display_routes, workflow_routes  # noqa: F401
from cafeteria.public import routes as public_routes
from cafeteria.security import csrf_token
from cafeteria.signage import routes as signage_routes
from cafeteria.ui import register_ui
from sqlalchemy.exc import SQLAlchemyError
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import (  # noqa: F401
    DATABASE_URL, DAY, ROOT, _login, database_engine,
)
from test_rendered_ui import browser, cafeteria_snapshot, patient_snapshot  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
PATHS = ('/admin/screens', '/admin/vorlagen')


@pytest.fixture
def hub_app(database_engine, tmp_path, monkeypatch):  # noqa: F811
    application = Flask(
        __name__,
        template_folder=str(ROOT / 'reference_scaffold/cafeteria/templates'),
        static_folder=str(ROOT / 'reference_scaffold/cafeteria/static'),
    )
    application.config.update(
        TESTING=True, SECRET_KEY='output-hub-test', LAST_GOOD_DIR=str(tmp_path),
        DEMO_MODE=True, DEMO_TODAY='2026-09-02',
    )
    register_ui(application)
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    auth = Blueprint('auth', __name__)
    auth.add_url_rule('/auth/logout', endpoint='logout', view_func=lambda: '')
    for blueprint in (auth, public_routes.bp, signage_routes.bp, workflow_routes.bp):
        application.register_blueprint(blueprint)
    application.context_processor(lambda: {'csrf_token': csrf_token})
    snapshots = {'staff_guest': cafeteria_snapshot(), 'patient': patient_snapshot()}
    monkeypatch.setattr(public_routes, 'active_snapshot', lambda _db, profile, *a, **kw: snapshots[profile])
    return application


class MainLinks(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.inside = False
        self.links = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'main':
            self.inside = True
        if tag == 'a' and self.inside:
            self.links.append(dict(attrs)['href'])

    def handle_endtag(self, tag):
        if tag == 'main':
            self.inside = False


class _HubNavLinks(HTMLParser):
    """Cross-route links in main.

    Object row actions stay icon-only. Navigation groups keep a visible destination.
    """

    _VOID = frozenset({
        'area', 'base', 'br', 'col', 'embed', 'hr', 'img', 'input', 'link', 'meta',
        'source', 'track', 'wbr',
    })

    def __init__(self, html, page_path):
        super().__init__(convert_charrefs=True)
        self.page_path = page_path
        self.stack = []
        self.capture = None
        self.unlabeled = []
        self.row_actions = []
        self.groups = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attr = dict(attrs)
        classes = set((attr.get('class') or '').split())
        parent_skip = self.stack[-1]['skip'] if self.stack else False
        in_main = tag == 'main' or any(frame['tag'] == 'main' for frame in self.stack)
        in_row = any(frame['tag'] == 'tr' for frame in self.stack)
        frame = {
            'tag': tag,
            'skip': parent_skip or 'admin-list-actions' in classes,
            'group': None,
            'template_id': attr.get('data-template-id') if tag == 'tr' else None,
            'primaries': [],
            'primary': [],
            'collect_primary': 'admin-list-primary' in classes,
        }
        if (
            in_main and not frame['skip'] and tag == 'div'
            and ({'output-print-actions', 'admin-row-actions'} & classes)
        ):
            frame['group'] = []
        self.stack.append(frame)
        if tag == 'a' and in_main and not frame['skip']:
            self.capture = {
                'href': attr.get('href') or '',
                'text': [],
                'name': ' '.join((attr.get('aria-label') or '').split()),
                'icon_only': 'ui-sem-control--icon-only' in classes,
                'in_row': in_row,
            }
        if tag in self._VOID:
            self.stack.pop()

    def handle_endtag(self, tag):
        while self.stack:
            frame = self.stack.pop()
            if frame['tag'] == 'a' and self.capture is not None:
                self._finish(frame)
            if frame['collect_primary']:
                text = ' '.join(''.join(frame['primary']).split())
                if text:
                    for ancestor in reversed(self.stack):
                        if ancestor['tag'] == 'tr':
                            ancestor['primaries'].append(text)
                            break
            if frame['group'] is not None:
                self.groups.append(frame['group'])
            if frame['tag'] == tag:
                break

    def handle_data(self, data):
        if self.capture is not None:
            self.capture['text'].append(data)
        for frame in reversed(self.stack):
            if frame['collect_primary']:
                frame['primary'].append(data)
                break

    def _innermost_group(self):
        for frame in reversed(self.stack):
            if frame['group'] is not None:
                return frame['group']
        return None

    def _object_row_action(self, href, name, icon_only, in_row):
        """Icon button of this row's object: template id in the href, or the row name in aria-label."""
        if not (icon_only and in_row and name):
            return False
        template_id = None
        primaries = []
        for frame in self.stack:
            if frame['tag'] == 'tr':
                template_id = frame['template_id'] or template_id
                primaries = frame['primaries'] or primaries
        parts = urlsplit(href)
        if template_id and (
            f'template={template_id}' in parts.query
            or parts.path.rstrip('/').endswith('/' + template_id)
        ):
            return True
        return any(primary and primary in name for primary in primaries)

    def _finish(self, frame):
        href = self.capture['href']
        text = ' '.join(''.join(self.capture['text']).split())
        name = self.capture['name']
        icon_only = self.capture['icon_only']
        in_row = self.capture['in_row']
        self.capture = None
        if self._object_row_action(href, name, icon_only, in_row):
            self.row_actions.append({'href': href, 'name': name})
            return
        group = self._innermost_group()
        path = urlsplit(href).path
        if group is not None:
            group.append((text, path))
        if not path or href.startswith('#') or path == self.page_path:
            return
        if not text:
            self.unlabeled.append(href)


def test_hub_navigation_links_keep_visible_destination_labels(hub_app, database_engine):  # noqa: F811
    """Links to another route on the output hubs show a destination label.

    Alt: every icon-only link in .admin-row-actions counted as navigation.
    Neu: object row actions stay icon-only and carry a nonempty accessible name.
    output-print-actions, the vorlagen hub labels and the screen links stay visible.
    """
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Admin'])
    expected = {
        '/admin/vorlagen': (
            'PDF Mitarbeitende', 'gewählte Woche', 'Menüs', 'Komponenten', 'Wochenplan',
            'PDF Patienten', 'Rezept drucken', 'Gerichtvorlagen', 'Zutaten', 'Kochbücher',
            'Zuordnen',
        ),
        '/admin/screens': ('Tagesplan', 'Wochenplan', 'Ohne Bilder', 'Zuweisen'),
    }
    object_paths = (
        '/admin/vorlagen/cafeteria',
        '/admin/vorlagen/cafeteria/vorschau.pdf',
        '/admin/vorlagen/patienten',
        '/admin/vorlagen/patienten/vorschau.pdf',
        '/admin/vorlagen/rezepte',
        '/admin/vorlagen/screens/cafeteria/cafeteria-week-photo',
        '/admin/vorlagen/screens/cafeteria/cafeteria-week-text',
        '/admin/vorlagen/screens/patienten/patient-week-photo',
        '/admin/vorlagen/screens/patienten/patient-week-text',
    )
    for path, labels in expected.items():
        response = client.get(path)
        assert response.status_code == 200
        html = response.get_data(as_text=True)
        scan = _HubNavLinks(html, path)
        assert scan.unlabeled == [], (path, scan.unlabeled)
        for label in labels:
            assert label in html, (path, label)
        for action in scan.row_actions:
            assert action['name'].strip(), action
        if path == '/admin/vorlagen':
            assert sorted(urlsplit(item['href']).path for item in scan.row_actions) == sorted(object_paths)
            assert html.count('>Zuordnen<') == 2
            for item in scan.row_actions:
                target = urlsplit(item['href']).path
                if target.endswith('/vorschau.pdf'):
                    assert item['name'] == 'Version 1 als PDF prüfen', item
                elif '/screens/' not in target:
                    assert item['name'] == 'Standard bearbeiten', item
                else:
                    assert 'Wochenplan' in item['name'] and item['name'].endswith(' prüfen'), item
        else:
            assert scan.row_actions == []
        for group in scan.groups:
            seen = {}
            for label, target in group:
                assert label, (path, group)
                assert seen.get(label, target) == target, (path, label, seen[label], target)
                seen[label] = target


def test_app_factory_registers_each_hub_once(monkeypatch):
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    rules = [rule.rule for rule in cafeteria.create_app().url_map.iter_rules()]
    for path in PATHS + (
        '/admin/screens/<any(cafeteria,patienten):family>/wochenvorlage',
        '/admin/vorlagen/screens/<any(cafeteria,patienten):family>/<template_id>',
    ):
        assert rules.count(path) == 1


@pytest.mark.parametrize('role', ['Cafeteria.Admin', 'Cafeteria.Editor', 'Cafeteria.Publisher'])
def test_hubs_use_existing_read_roles_and_link_all_real_targets(hub_app, database_engine, role):  # noqa: F811
    client, _ = _login(hub_app, database_engine, [role])
    for profile, values in [('staff_guest', _staff_values()), ('patient', _patient_values())]:
        _save(database_engine, profile, values)
    for path in PATHS:
        response = client.get(path)
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        html = response.get_data(as_text=True)
        assert 'data-semantic="actions.more"' not in html
        # The active sidebar link carries href, class and aria-current (other attributes such as the
        # collapsed-sidebar tooltip may sit in between).
        assert re.search(
            rf'<a\b(?=[^>]*\bhref="{re.escape(path)}")(?=[^>]*\bclass="nav-link active")[^>]*\baria-current="page"',
            html,
        )
        links = MainLinks(html).links
        screen_links = [link for link in links if link.startswith(('/admin/screens/', '/admin/vorlagen/screens/'))]
        assert len(set(screen_links)) == (2 if path == '/admin/screens' else 6)
        if path == '/admin/vorlagen':
            # Assignment is per family, not per photo/text preview card.
            assert len(screen_links) == 6
        links = [link for link in links if link not in screen_links]
        if path == '/admin/vorlagen':
            # Area tabs (2), print/public/content (10),
            # dish templates/recipes/master data/cookbooks (4), admin editors/previews (5).
            # The header owns the cafeteria PDF action; status and overflow add no duplicates.
            expected_links = 21 if role == 'Cafeteria.Admin' else 16
            expected_unique_links = expected_links
            assert {link for link in links if link.startswith('#')} == {
                '#output-cafeteria', '#output-patienten',
            }
            template_links = [link for link in links if link.startswith('/admin/vorlagen/')]
            assert len(template_links) == (5 if role == 'Cafeteria.Admin' else 0)
            assert '/admin/gerichtvorlagen' in links
            assert '/admin/rezepte' in links
            assert html.count('aria-label="Rezept drucken"') == 1
            assert {'/admin/grundlagen?kind=foods', '/admin/rezepte', '/admin/kochbuecher'} <= set(links)
        else:
            # Ten public destinations; module tabs and two area anchors are gone.
            expected_links = 10
            expected_unique_links = 10
        recipe_editor_links = [link for link in links if link.startswith('/admin/vorlagen/rezepte')]
        expected_recipe_links = (
            ['/admin/vorlagen/rezepte?template=standard&revision=1']
            if path == '/admin/vorlagen' and role == 'Cafeteria.Admin' else []
        )
        assert recipe_editor_links == expected_recipe_links
        assert len(links) == expected_links and len(set(links)) == expected_unique_links
        for link in links:
            if link.startswith('#'):
                continue
            target = client.get(link)
            assert target.status_code == 200, (link, target.status_code)
            if '/preview/print' in link:
                assert f'week={DAY}' in link
                assert target.data.startswith(b'%PDF-')
            elif link.startswith(('/cafeteria/', '/patienten/', '/signage/', '/druck/')):
                assert '?' not in link
                assert target.headers['X-Snapshot-Revision']


def test_dish_template_count_failure_is_explicit_no_store_503(
    hub_app, database_engine, monkeypatch,  # noqa: F811
):
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Editor'])

    def fail_count(*_args, **_kwargs):
        raise SQLAlchemyError('Gerichtvorlagen-Zählung nicht verfügbar.')

    monkeypatch.setattr(dish_template_store, 'list_templates', fail_count)
    response = client.get('/admin/vorlagen')

    assert response.status_code == 503
    assert response.headers['Cache-Control'] == 'no-store'
    assert 'vorübergehend nicht verfügbar' in response.get_data(as_text=True)


def test_hub_counts_active_and_archived_dish_templates_exactly(hub_app, database_engine):  # noqa: F811
    with database_engine.begin() as connection:
        connection.execute(text(
            "INSERT INTO cafeteria.dish_templates(title,active) "
            "VALUES ('Aktive Hubvorlage',true),('Archivierte Hubvorlage',false)"
        ))
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Editor'])

    response = client.get('/admin/vorlagen')

    assert response.status_code == 200
    assert 'Menüvorlagen (1 aktiv, 1 archiviert)' in response.get_data(as_text=True)


def test_draft_read_only_role_gets_working_recipe_print_entry(
    hub_app, database_engine, monkeypatch,  # noqa: F811
):
    monkeypatch.setitem(cafeteria.roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'draft.read'})
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Editor'])

    response = client.get('/admin/vorlagen')
    links = MainLinks(response.get_data(as_text=True)).links

    assert response.status_code == 200
    assert response.get_data(as_text=True).count('aria-label="Rezept drucken"') == 1
    # One recipe-print entry, with no duplicate in the optional content links.
    assert links.count('/admin/rezepte') == 1
    assert client.get('/admin/rezepte').status_code == 200
    assert not any(
        link.startswith('/admin/vorlagen/') and not link.startswith('/admin/vorlagen/screens/')
        for link in links
    )


def test_hubs_reject_missing_roles_and_stale_authorization(hub_app, database_engine, monkeypatch):  # noqa: F811
    for path in PATHS:
        assert hub_app.test_client().get(path).status_code == 401
    client, _ = _login(hub_app, database_engine, [])
    for path in PATHS:
        assert client.get(path).status_code == 401
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Editor'])
    monkeypatch.setitem(cafeteria.roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'csv.export'})
    for path in PATHS:
        assert client.get(path).status_code == 403
    client, actor = _login(hub_app, database_engine, ['Cafeteria.Admin'])
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.users SET authz_version=authz_version+1 WHERE id=:id'), {'id': actor})
    for path in PATHS:
        assert client.get(path).status_code == 401


@pytest.mark.parametrize('path', [
    '/admin/screens?week=2026-08-31', '/admin/screens?profile=patient',
    '/admin/vorlagen?profile=patient', '/admin/vorlagen?week=2026-09-01',
    '/admin/vorlagen?week=invalid', '/admin/vorlagen?week=2026-08-31&week=2026-09-07',
])
def test_hubs_reject_invalid_query_parameters(hub_app, database_engine, path):  # noqa: F811
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Admin'])
    assert client.get(path).status_code == 400


def test_selected_week_only_changes_saved_week_destinations(hub_app, database_engine):  # noqa: F811
    client, _ = _login(hub_app, database_engine, ['Cafeteria.Editor'])
    response = client.get('/admin/vorlagen?week=2026-09-07')
    assert response.status_code == 200
    links = MainLinks(response.get_data(as_text=True)).links
    # The removed module tab linked to preview; the four saved-week actions remain.
    week_links = [link for link in links if 'week=2026-09-07' in link]
    assert len(week_links) == 4
    assert set(week_links) == {
        '/admin/cafeteria?week=2026-09-07', '/admin/patienten?week=2026-09-07',
        '/admin/cafeteria/preview/print?week=2026-09-07',
        '/admin/patienten/preview/print?week=2026-09-07',
    }
    assert '/druck/cafeteria/woche' in links and '/druck/patienten/woche' in links


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
def test_hubs_responsive_keyboard_and_native_week_selection(
    hub_app, database_engine, browser, width, javascript, tmp_path: Path,  # noqa: F811
):
    def check_controls(controls):
        # Native :focus-visible requires keyboard modality after opening details by click.
        page.keyboard.press('Tab')
        for control in controls:
            # Closed overflow items stay out of the tab order until the menu is opened.
            if not control.is_visible():
                continue
            control.scroll_into_view_if_needed()
            box = control.bounding_box()
            classes = control.get_attribute('class') or ''
            # Symbols and G0 fields follow --app-control-min-height (36 fine / 44 coarse).
            # Other text controls keep the 44px floor.
            field = 'form-control' in classes or 'form-select' in classes
            if 'ui-sem-control' in classes or field:
                minimum = 44 if page.evaluate("matchMedia('(any-pointer: coarse)').matches") else 36
            else:
                minimum = 44
            assert box is not None and box['height'] >= minimum
            control.focus()
            expect(control).to_be_focused()
            assert control.evaluate(
                "el => { const s = getComputedStyle(el); return s.boxShadow !== 'none' || "
                "(s.outlineStyle !== 'none' && parseFloat(s.outlineWidth) > 0); }"
            )

    client, _ = _login(hub_app, database_engine, ['Cafeteria.Admin'])
    server = make_server('127.0.0.1', 0, hub_app)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    base_url = f'http://127.0.0.1:{server.server_port}'
    cookie = client.get_cookie('session')
    assert cookie is not None
    try:
        with browser.new_context(
            base_url=base_url, java_script_enabled=javascript,
            viewport={'width': width, 'height': 1100}, reduced_motion='reduce',
        ) as context:
            context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': base_url}])
            page = context.new_page()
            for path, title in zip(PATHS, ('Bildschirme', 'Vorlagen'), strict=True):
                response = page.goto(path)
                assert response is not None and response.status == 200
                expect(page.get_by_role('heading', level=1)).to_have_text(title)
                assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                if path == '/admin/screens':
                    # Alt: empty icon. Neu: the screen link names the destination.
                    expect(page.get_by_role(
                        'link', name='Mitarbeitende und externe Gäste Bildschirm Tagesplan öffnen', exact=True,
                    )).to_contain_text('Tagesplan')
                else:
                    expect(page.get_by_role('link', name='Gerichtvorlagen öffnen', exact=True)).to_contain_text(
                        'Gerichtvorlagen',
                    )
                    expect(page.get_by_role(
                        'link', name='Mitarbeitende und externe Gäste gewählte Woche öffnen', exact=True,
                    )).to_contain_text('gewählte Woche')
                if path == '/admin/screens':
                    expect(page.locator('.screen-card [data-semantic="actions.more"]')).to_have_count(0)
                    expect(page.locator('.screen-card .admin-row-actions')).to_have_count(4)
                    for action in page.locator('.screen-card .admin-row-actions .ui-sem-control').all():
                        expect(action).to_be_visible()
                    controls = page.locator('main .screen-card .btn').all()
                else:
                    controls = []
                    controls.extend(page.locator('main form :is(.btn, .form-control)').all())
                    controls.extend(page.locator(
                        'main .print-related-grid .btn, main .screens-grid .btn, '
                        'main .page-header .btn'
                    ).all())
                    expect(page.locator('main [data-semantic="actions.more"]')).to_have_count(0)
                    related = page.locator('main .admin-row-actions').filter(
                        has=page.locator('a[href="/admin/grundlagen?kind=foods"]'))
                    expect(related).to_have_count(1)
                    expect(related.locator('.btn')).to_have_count(2)
                    controls.extend(related.locator('.btn').all())
                    families = ('cafeteria', 'patienten')
                    for family in families:
                        page.locator(f'[aria-controls="output-{family}"]').click()
                        pane = page.locator(f'#output-{family}')
                        expect(pane).to_be_visible()
                        for summary in pane.locator('details summary').all():
                            summary.click()
                        # Check each family's controls while that tab is still active.
                        check_controls(pane.locator('.btn').all())
                check_controls(controls)
                page.screenshot(path=str(tmp_path / f'{title}-{width}-js-{javascript}.png'), full_page=True)
            page.get_by_label('Woche ab Montag').fill('2026-09-07')
            page.get_by_role('button', name='Woche öffnen', exact=True).click()
            expect(page).to_have_url(f'{base_url}/admin/vorlagen?week=2026-09-07')
            expect(page.get_by_label('Mitarbeitende und externe Gäste gewählte Woche öffnen')).to_have_attribute(
                'href', '/admin/cafeteria?week=2026-09-07',
            )
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()
