"""UI-16: direct actions follow ROLE_CAPABILITIES; denied writes stay 403 (V3-8)."""
from __future__ import annotations

# ruff: noqa: F811

import json
from collections import Counter
from pathlib import Path
from typing import TypedDict

import pytest
from playwright.sync_api import Error as PlaywrightError
from playwright.sync_api import TimeoutError as PlaywrightTimeout
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.roles import ROLE_CAPABILITIES
from test_admin_ux_browser import admin_app, admin_engine, browser, live_server  # noqa: F401
from test_admin_workflow_routes import DATABASE_URL, _login

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

ROLES = ('Cafeteria.Editor', 'Cafeteria.Publisher', 'Cafeteria.Admin')
CSRF = 'v3-8-csrf'
MISSING_BATCH = '00000000-0000-4000-8000-000000000001'
MISSING_USER = '00000000-0000-4000-8000-000000000099'
TABLES = (
    'menu_weeks', 'menu_services', 'menu_items', 'publication_revisions', 'audit_events',
    'settings', 'api_keys', 'users', 'user_role_cache', 'local_credentials',
    'recipe_import_batches', 'recipe_import_candidates',
)
SHARED = (
    ('rezepte', '/admin/rezepte'),
    ('kochbuecher', '/admin/kochbuecher'),
    ('bausteine-cafeteria', '/admin/cafeteria/komponenten'),
    ('bausteine-patienten', '/admin/patienten/komponenten'),
    ('zutaten', '/admin/grundlagen?kind=foods'),
    ('gerichtvorlagen', '/admin/gerichtvorlagen'),
    ('einkaufslisten', '/admin/einkaufslisten'),
    ('rezeptimport', '/admin/rezepte/import'),
    ('bildschirme', '/admin/screens'),
)
ADD_VIEWS = frozenset({
    'rezepte', 'kochbuecher', 'bausteine-cafeteria', 'bausteine-patienten',
    'zutaten', 'gerichtvorlagen', 'einkaufslisten',
})
WEEKS = (
    ('woche-cafeteria', '/admin/cafeteria', 'cafeteria'),
    ('woche-patienten', '/admin/patienten', 'patienten'),
)
ASSIGNMENTS = (
    ('zuordnung-cafeteria', '/admin/screens/cafeteria/wochenvorlage'),
    ('zuordnung-patienten', '/admin/screens/patienten/wochenvorlage'),
)
PRIVILEGED = (
    ('druck-cafeteria', '/admin/vorlagen/cafeteria', 'settings.write'),
    ('druck-patienten', '/admin/vorlagen/patienten', 'settings.write'),
    ('druck-rezepte', '/admin/vorlagen/rezepte', 'settings.write'),
    ('api', '/admin/api', 'api.keys.manage'),
    ('benutzer', '/admin/benutzer', 'users.manage'),
)
PRINT_PREFIXES = (
    '/admin/vorlagen/cafeteria',
    '/admin/vorlagen/patienten',
    '/admin/vorlagen/rezepte',
)
WEEK_EXTRA = frozenset({'actions.publish', 'actions.cancel'})
ASSIGN_EXTRA = frozenset({'actions.save', 'actions.cancel'})
# The workflow test app stubs only two signage previews. Screen and template
# pages also build these public links; the matrix checks the admin controls.
_OUTPUT_ENDPOINTS = (
    ('public.cafeteria_today', '/cafeteria/heute/'),
    ('public.cafeteria_week', '/cafeteria/wochenangebot/'),
    ('public.cafeteria_week_without_images', '/cafeteria/wochenangebot/ohne-bilder/'),
    ('public.patient_today', '/patienten/heute/'),
    ('public.patient_week', '/patienten/wochenplan/'),
    ('public.patient_week_without_images', '/patienten/wochenplan/ohne-bilder/'),
    ('public.print_cafeteria_week', '/druck/cafeteria/woche'),
    ('public.print_patient_week', '/druck/patienten/woche'),
    ('signage.cafeteria_day', '/signage/cafeteria/tag'),
    ('signage.patient_day', '/signage/patienten/tag'),
)

_KEYS_JS = """() => {
  const selectors = [
    'main .admin-row-actions [data-semantic^="actions."]',
    'main .page-header [data-semantic^="actions."]',
    'main .admin-actions [data-semantic^="actions."]',
    'main .admin-form-footer [data-semantic^="actions."]',
    'main .admin-list-actions [data-semantic^="actions."]',
    'main .modal [data-semantic^="actions."]',
    'main noscript [data-semantic^="actions."]',
  ];
  const seen = new Set();
  const keys = [];
  for (const selector of selectors) {
    for (const node of document.querySelectorAll(selector)) {
      if (node.closest('form[action$="/commit"]')) continue;
      if (seen.has(node)) continue;
      seen.add(node);
      keys.push(node.getAttribute('data-semantic'));
    }
  }
  keys.sort();
  return keys;
}"""

_COUNT_JS = """() => {
  const count = (selector) => document.querySelectorAll(selector).length;
  return {
    publish: count('[data-semantic="actions.publish"]'),
    save: count('[data-semantic="actions.save"]'),
    cancel: count('[data-semantic="actions.cancel"]'),
    add: count('[data-semantic="actions.add"]'),
    preview: count('[data-semantic="actions.preview"]'),
    open: count('[data-semantic="actions.open"]'),
    export: count('[data-semantic="actions.export"]'),
    copy: count('[data-semantic="actions.copy"]'),
    commit: count('form[action$="/commit"] [data-semantic="actions.apply"]'),
    any: count('[data-semantic^="actions."]'),
  };
}"""

_HREF_JS = """(prefixes) => [...document.querySelectorAll('a[href]')]
  .map((node) => node.getAttribute('href'))
  .filter((href) => {
    const path = href.split('?')[0].split('#')[0];
    return prefixes.some((prefix) => path === prefix || path.startsWith(prefix + '/'));
  })"""


class _View(TypedDict):
    status: int
    keys: list[str]
    counts: dict[str, int]
    hrefs: list[str]
    snippet: str


def _stub_output_endpoints(app) -> None:
    def empty() -> tuple[str, int]:
        return '', 204

    for endpoint, rule in _OUTPUT_ENDPOINTS:
        if endpoint not in app.view_functions:
            app.add_url_rule(rule, endpoint=endpoint, view_func=empty)


def _capable(role: str, capability: str) -> bool:
    caps = ROLE_CAPABILITIES[role]
    return '*' in caps or capability in caps


def _snippet(page) -> str:
    try:
        text_value = page.locator('body').inner_text(timeout=2000)
    except (PlaywrightError, PlaywrightTimeout) as error:
        return str(error)[:180]
    return ' '.join(text_value.split())[:180]


def _snapshot(engine) -> dict[str, str]:
    digest = (
        "SELECT md5(coalesce(string_agg(row_to_json(row)::text, ',' "
        "ORDER BY row_to_json(row)::text), '')) FROM cafeteria."
    )
    statements = {
        name: text(digest + name + ' AS row')
        for name in TABLES
    }
    found = {}
    with engine.connect() as connection:
        for table in TABLES:
            found[table] = connection.execute(statements[table]).scalar_one()
    return found


def _visit(page, url: str, *, hrefs: bool = False) -> _View:
    response = page.goto(url, wait_until='domcontentloaded')
    assert response is not None, url
    record = {
        'status': response.status,
        'keys': page.evaluate(_KEYS_JS),
        'counts': page.evaluate(_COUNT_JS),
        'hrefs': page.evaluate(_HREF_JS, list(PRINT_PREFIXES)) if hrefs else [],
        'snippet': '' if response.status == 200 else _snippet(page),
    }
    return record


def _week_fields(page, family: str) -> dict[str, str]:
    form = page.locator(f'form[action="/admin/{family}/header"]')
    assert form.count() == 1, family
    payload = {
        name: form.locator(f'input[name="{name}"]').input_value()
        for name in ('_csrf', 'week', 'row_version')
    }
    assert payload['week'] and payload['row_version'] != '', payload
    payload['_csrf'] = CSRF
    return payload


def _deny(context, engine, before: dict[str, str], role: str, label: str, url: str, form: dict):
    response = context.request.post(url, form=form, max_redirects=0)
    after = _snapshot(engine)
    changed = [table for table in TABLES if after[table] != before[table]]
    detail = f'{role} POST {url} -> {response.status} {response.text()[:160]}'
    assert response.status == 403, detail
    assert not changed, f'{label} changed {changed}; {detail}'
    return {'role': role, 'view': label, 'url': url, 'status': response.status}


def _same_keys(found: dict, name: str) -> None:
    groups = [found[role][name]['keys'] for role in ROLES]
    assert groups[0] == groups[1] == groups[2], (name, groups)


def _walk(page, role: str) -> tuple[dict, dict[str, dict]]:
    found = {}
    week_forms = {}
    for name, url in SHARED:
        record = _visit(page, url)
        assert record['status'] == 200, (role, name, record['status'], record['snippet'])
        assert record['counts']['publish'] == 0, (role, name, record['counts'])
        if name in ADD_VIEWS:
            assert record['counts']['add'] > 0, (role, name, record['counts'])
        if name == 'einkaufslisten':
            token = page.locator('input[name="_csrf"]').first.input_value()
            assert token == CSRF, token
        if name == 'rezeptimport':
            assert record['counts']['preview'] > 0, (role, record['counts'])
            if not _capable(role, 'recipe.import'):
                assert record['counts']['commit'] == 0
        if name == 'bildschirme':
            assert record['counts']['open'] > 0, (role, record['counts'])
            for family in ('cafeteria', 'patienten'):
                link = f'a[href*="/admin/screens/{family}/wochenvorlage"]'
                assert page.locator(link).count() > 0, (role, family)
        found[name] = record
    for name, url, family in WEEKS:
        record = _visit(page, url)
        assert record['status'] == 200, (role, name, record['status'], record['snippet'])
        counts = record['counts']
        assert counts['preview'] > 0 and counts['export'] > 0 and counts['copy'] > 0, counts
        visible = page.locator(
            '.page-header [data-semantic="actions.publish"], '
            '.admin-actions [data-semantic="actions.publish"]',
        ).locator('visible=true')
        if _capable(role, 'publication.publish'):
            assert counts['publish'] > 0, (role, name, counts)
            expect(visible.first).to_be_visible()
        else:
            assert counts['publish'] == 0, (role, name, counts)
            assert page.locator('#week-publish-modal, .admin-week-nojs-publish').count() == 0
            expect(visible).to_have_count(0)
        week_forms[family] = _week_fields(page, family)
        found[name] = record
    catalog = _visit(page, '/admin/vorlagen', hrefs=True)
    assert catalog['status'] == 200, (role, catalog['status'], catalog['snippet'])
    if _capable(role, 'settings.write'):
        assert catalog['hrefs'], catalog['hrefs']
    else:
        assert catalog['hrefs'] == [], (role, catalog['hrefs'])
    found['vorlagen'] = catalog
    for name, url in ASSIGNMENTS:
        record = _visit(page, url)
        assert record['status'] == 200, (role, name, record['status'], record['snippet'])
        assert record['counts']['preview'] > 0, (role, name, record['counts'])
        if _capable(role, 'settings.write'):
            assert record['counts']['save'] > 0, (role, name, record['counts'])
            expect(page.locator('.admin-form-footer [data-semantic="actions.save"]')).to_be_visible()
        else:
            assert record['counts']['save'] == 0, (role, name, record['counts'])
            assert record['counts']['cancel'] == 0, (role, name, record['counts'])
        found[name] = record
    for name, url, capability in PRIVILEGED:
        record = _visit(page, url)
        if _capable(role, capability):
            assert record['status'] == 200, (role, name, record['status'], record['snippet'])
            if name.startswith('druck'):
                assert record['counts']['save'] > 0, (role, name, record['counts'])
            else:
                assert record['counts']['add'] > 0, (role, name, record['counts'])
        else:
            assert record['status'] == 403, (role, name, record['status'], record['snippet'])
            assert record['counts']['any'] == 0, (role, name, record['counts'])
            assert record['keys'] == [], (role, name, record['keys'])
        found[name] = record
    return found, week_forms


def _compare(found: dict) -> None:
    for name, _url in SHARED:
        _same_keys(found, name)
        commits = [found[role][name]['counts']['commit'] for role in ROLES]
        if name == 'rezeptimport':
            assert commits[0] == 0 and commits[1] == commits[2], commits
        else:
            assert commits == [0, 0, 0], (name, commits)
    for name, _url, _family in WEEKS:
        editor = found['Cafeteria.Editor'][name]['keys']
        publisher = found['Cafeteria.Publisher'][name]['keys']
        admin = found['Cafeteria.Admin'][name]['keys']
        assert publisher == admin, (name, publisher, admin)
        assert not (Counter(editor) - Counter(publisher)), (name, editor, publisher)
        extra = Counter(publisher) - Counter(editor)
        assert set(extra) <= WEEK_EXTRA, (name, extra)
        assert found['Cafeteria.Publisher'][name]['counts']['publish'] > 0
    editor_catalog = found['Cafeteria.Editor']['vorlagen']['keys']
    publisher_catalog = found['Cafeteria.Publisher']['vorlagen']['keys']
    admin_catalog = found['Cafeteria.Admin']['vorlagen']['keys']
    assert editor_catalog == publisher_catalog
    assert not (Counter(editor_catalog) - Counter(admin_catalog))
    admin_hrefs = found['Cafeteria.Admin']['vorlagen']['hrefs']
    for prefix in PRINT_PREFIXES:
        assert any(
            href.split('?', 1)[0].split('#', 1)[0] == prefix
            or href.startswith(prefix + '/')
            or href.startswith(prefix + '?')
            for href in admin_hrefs
        ), (prefix, admin_hrefs)
    for name, _url in ASSIGNMENTS:
        editor = found['Cafeteria.Editor'][name]
        publisher = found['Cafeteria.Publisher'][name]
        admin = found['Cafeteria.Admin'][name]
        assert editor['keys'] == publisher['keys'], name
        assert not (Counter(editor['keys']) - Counter(admin['keys'])), name
        extra = Counter(admin['keys']) - Counter(editor['keys'])
        assert set(extra) <= ASSIGN_EXTRA, (name, extra)
        assert extra['actions.save'] >= 1 and extra['actions.cancel'] >= 1, (name, extra)


def _posts(context, engine, role: str, week_forms: dict[str, dict]) -> list[dict]:
    # require_capability aborts 403 before lookup, so these routes do not deny with 404.
    targets: list[tuple[str, str, dict]] = []
    if not _capable(role, 'publication.publish'):
        for family in ('cafeteria', 'patienten'):
            targets.append((f'woche-{family}', f'/admin/{family}/publish', week_forms[family]))
    if not _capable(role, 'recipe.import'):
        targets.append((
            'rezeptimport', f'/admin/rezepte/import/{MISSING_BATCH}/commit', {'_csrf': CSRF},
        ))
    if not _capable(role, 'settings.write'):
        for family in ('cafeteria', 'patienten'):
            targets.append((f'druck-{family}', f'/admin/vorlagen/{family}', {'_csrf': CSRF}))
        targets.append(('druck-rezepte', '/admin/vorlagen/rezepte', {'_csrf': CSRF}))
        for family in ('cafeteria', 'patienten'):
            targets.append((
                f'zuordnung-{family}', f'/admin/screens/{family}/wochenvorlage', {'_csrf': CSRF},
            ))
    if not _capable(role, 'api.keys.manage'):
        targets.append(('api', '/admin/api/keys', {'_csrf': CSRF}))
        targets.append((
            'api-revoke', f'/admin/api/keys/{MISSING_BATCH}/revoke', {'_csrf': CSRF},
        ))
    if not _capable(role, 'users.manage'):
        targets.append(('benutzer', '/admin/benutzer', {'_csrf': CSRF}))
        targets.append((
            'benutzer-deaktivieren',
            f'/admin/benutzer/{MISSING_USER}/deaktivieren',
            {'_csrf': CSRF},
        ))
    before = _snapshot(engine)
    return [_deny(context, engine, before, role, label, url, form) for label, url, form in targets]


def test_direct_actions_match_role_capabilities(admin_app, admin_engine, live_server, browser):
    _stub_output_endpoints(admin_app)
    matrix: dict = {'modes': {}, 'posts': []}
    for javascript in (True, False):
        found = {}
        for role in ROLES:
            client, _user_id = _login(admin_app, admin_engine, [role], csrf=CSRF)
            cookie = client.get_cookie('session')
            assert cookie is not None
            with browser.new_context(
                base_url=live_server,
                java_script_enabled=javascript,
                reduced_motion='reduce',
                has_touch=not javascript,
                viewport={
                    'width': 1440 if javascript else 390,
                    'height': 900 if javascript else 844,
                },
            ) as context:
                context.add_cookies([{
                    'name': cookie.key, 'value': cookie.value, 'url': live_server,
                }])
                page = context.new_page()
                role_found, week_forms = _walk(page, role)
                matrix['posts'].extend(_posts(context, admin_engine, role, week_forms))
            found[role] = {
                name: {
                    'status': record['status'],
                    'keys': record['keys'],
                    'counts': record['counts'],
                    'hrefs': record['hrefs'],
                }
                for name, record in role_found.items()
            }
        _compare(found)
        matrix['modes']['js' if javascript else 'nojs'] = found
    Path('/tmp/v3-8-role-matrix.json').write_text(
        json.dumps(matrix, ensure_ascii=False, indent=2) + '\n', encoding='utf-8',
    )
