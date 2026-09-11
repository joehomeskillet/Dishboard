"""MP-UI-WEEKS: real routes, isolated PostgreSQL and proposed browser evidence."""
from __future__ import annotations

import hashlib
import json
import subprocess
from datetime import timedelta
from pathlib import Path

import pytest
from jinja2 import ChoiceLoader, DictLoader
from playwright.sync_api import Page, expect
from sqlalchemy import text

from cafeteria import roles
from cafeteria.admin import week_management_routes, week_review_routes
from cafeteria.branding_config import contrast
from cafeteria.component_catalog_store import ComponentCatalogConfigurationError
from cafeteria.workflow import publish_draft
from cafeteria.workflow_partial_store import persist_week_header, resolve_week_ref
from cafeteria.workflow_review_context import get_week_review
from review_support import review_saved_week
from test_admin_workflow_db import _save, _save_reviewed, _staff_values, _patient_values
from test_admin_workflow_routes import (
    WEEK, _scope, app as workflow_app, database_engine as database_engine,  # noqa: F401
)
from test_branding_browser import live_branding as live_branding
from test_rendered_ui import browser as browser
from test_ui_reference_form_browser import _capture
from test_ui_reference_list_browser import _context, _goto
from test_week_review_browser import _values

BASE = 'cbed49229d3dbd041542d86af41d6d3e735ea0c1'
ROOT = Path(__file__).resolve().parents[2]
VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080))
CORE = ((1440, 900), (390, 844))
CONFIRM = 'Wochenkopf und alle Ausgabehinweise als geprüft bestätigen'


@pytest.fixture(params=[(family, profile, js) for family, profile in
                       (('cafeteria', 'staff_guest'), ('patienten', 'patient'))
                       for js in (True, False)])
def weeks_ui(request, live_branding, database_engine, browser):
    family, profile, javascript = request.param
    origin, app, client, actor, _ = live_branding
    with _context(browser, origin, client, javascript) as context:
        page = context.new_page()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('requestfailed', lambda req: errors.append(req.failure))
        page.on('console', lambda msg: errors.append(msg.text) if msg.type == 'error'
                and not msg.text.startswith('Failed to load resource: the server responded with a status of') else None)
        yield page, database_engine, _scope(database_engine, actor, profile), family, javascript, app
        assert not errors, errors


def _snapshot(engine) -> list:
    with engine.connect() as connection:
        return [connection.execute(text(query)).all() for query in (
            'SELECT id,row_version,workflow_state,title,shared_note FROM cafeteria.menu_weeks ORDER BY id',
            'SELECT id,row_version,notice FROM cafeteria.menu_services ORDER BY id',
            'SELECT id,row_version,allergen_review_status FROM cafeteria.menu_items ORDER BY id',
            'SELECT id,details FROM cafeteria.audit_events ORDER BY id',
            'SELECT id,snapshot_json,withdrawn_at FROM cafeteria.publication_revisions ORDER BY id',
        )]


def _fields(page: Page, selector: str) -> dict:
    return page.locator(selector).evaluate('form => Object.fromEntries(new FormData(form))')


def _focus(page: Page, locator) -> None:
    locator.focus()
    page.keyboard.press('Shift+Tab')
    page.keyboard.press('Tab')
    expect(locator).to_be_focused()
    assert locator.evaluate('e => getComputedStyle(e).outlineStyle') == 'solid'
    assert locator.evaluate('e => parseFloat(getComputedStyle(e).outlineWidth)') >= 2


def _views(page: Page, tmp_path: Path, state: str, viewports=VIEWPORTS) -> None:
    for width, height in viewports:
        page.set_viewport_size({'width': width, 'height': height})
        expect(page.locator('h1')).to_have_count(1)
        expect(page.locator('main')).to_have_attribute('data-layout', 'standard')
        # Playwright restores screenshot caret styles as empty style attributes.
        assert page.locator('main [style]:not([style=""]), main script:not([src])').evaluate_all(
            'es => es.map(e => e.outerHTML)'
        ) == []
        assert page.locator('main :is(.btn, input:not([type=hidden]), textarea, summary):visible').evaluate_all(
            'es => es.every(e => e.getBoundingClientRect().height >= 48)'
        )
        assert page.locator('main :is(td, dd, p):visible').evaluate_all('''es => es.every(e => {
            const s = getComputedStyle(e);
            return s.webkitLineClamp === 'none' && e.scrollWidth <= e.clientWidth + 1;
        })''')
        pairs = page.locator('main :is(.badge, .btn, .text-secondary, dd, dt, th, .form-label):visible').evaluate_all('''es => es.map(e => {
            const canvas = document.createElement('canvas');
            canvas.width = canvas.height = 1;
            const ctx = canvas.getContext('2d', {willReadFrequently: true});
            const hex = () => '#' + [...ctx.getImageData(0, 0, 1, 1).data].slice(0, 3)
                .map(n => n.toString(16).padStart(2, '0')).join('');
            ctx.fillStyle = 'white'; ctx.fillRect(0, 0, 1, 1);
            const parents = [];
            for (let p = e; p; p = p.parentElement) parents.unshift(p);
            for (const p of parents) {
                ctx.fillStyle = getComputedStyle(p).backgroundColor; ctx.fillRect(0, 0, 1, 1);
            }
            const background = hex();
            ctx.fillStyle = getComputedStyle(e).color; ctx.fillRect(0, 0, 1, 1);
            return {label: e.textContent, color: hex(), background};
        })''')
        for pair in pairs:
            pair['contrast'] = contrast(pair['color'], pair['background'])
        (tmp_path / f'{state}-{width}-contrast.json').write_text(json.dumps(pairs), encoding='utf-8')
        assert all(pair['contrast'] >= 4.5 for pair in pairs), [p for p in pairs if p['contrast'] < 4.5]
        _capture(page, tmp_path, f'{state}-{width}')


def _before(page: Page, app, path: str, template: str, tmp_path: Path) -> None:
    source = subprocess.run(
        ['rtk', 'git', 'cat-file', 'blob', f'{BASE}:reference_scaffold/cafeteria/templates/admin/{template}'],
        cwd=ROOT, check=True, capture_output=True, text=True,
    ).stdout
    loader = app.jinja_env.loader
    app.jinja_env.loader = ChoiceLoader([DictLoader({f'admin/{template}': source}), loader])
    app.jinja_env.cache.clear()
    try:
        _goto(page, path)
        for width, height in CORE:
            page.set_viewport_size({'width': width, 'height': height})
            page.screenshot(path=str(tmp_path / f'before-{width}.png'), full_page=True)
    finally:
        app.jinja_env.loader = loader
        app.jinja_env.cache.clear()


def _zoom(page: Page, tmp_path: Path, name: str) -> bool:
    page.evaluate("document.documentElement.style.zoom = '2'")
    region = page.get_by_role('region', name='Wochenliste', exact=True)
    if region.count() and region.evaluate('e => e.scrollWidth > e.clientWidth + 1'):
        _focus(page, region)
        page.keyboard.press('ArrowRight')
        expect(region).not_to_have_js_property('scrollLeft', 0)
        region.evaluate('e => e.scrollLeft = 0')
    page.screenshot(path=str(tmp_path / f'zoom200-{name}.png'), full_page=True)
    overflow = page.locator('body *:visible').evaluate_all('''es => es.filter(e => {
        const r = e.getBoundingClientRect(); return r.right > innerWidth + 1;
    }).map(e => ({tag: e.tagName, class: e.className, text: e.textContent.slice(0, 100)}))''')
    fits = page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    (tmp_path / f'zoom200-{name}.json').write_text(json.dumps({'fits': fits, 'overflow': overflow}), encoding='utf-8')
    page.evaluate("document.documentElement.style.zoom = ''")
    return fits


def test_management_states_creation_copy_and_pagination(weeks_ui, tmp_path):
    page, engine, scope, family, javascript, app = weeks_ui
    path = f'/admin/{family}/wochen'
    _before(page, app, path, 'week_management.html', tmp_path)
    _goto(page, path)
    before = _snapshot(engine)
    expect(page.locator('[data-empty-kind="none"]')).to_be_visible()
    expect(page.get_by_role('navigation', name='Wochenseiten')).to_have_count(0)
    _views(page, tmp_path, 'empty')
    assert _snapshot(engine) == before
    summary = page.locator('#new-week-title')
    _focus(page, summary)
    expect(page.locator('#new-week-date')).to_be_hidden()
    page.keyboard.press('Enter')
    expect(page.locator('#new-week-date')).to_be_visible()
    page.keyboard.press('Tab')
    expect(page.locator('#new-week-date')).to_be_focused()
    form = 'form.admin-form'
    token = _fields(page, form)['_csrf']
    page.locator('#new-week-date').fill('2026-09-01')
    page.locator('#new-week-name').fill('Eigene Woche <script>')
    page.locator('#new-week-note').fill('Hinweis behalten')
    for expected in (400, 303, 409):
        if expected == 303:
            page.locator('#new-week-date').fill(str(WEEK))
        with page.expect_response(lambda r: r.request.method == 'POST') as posted:
            page.get_by_role('button', name='Woche anlegen', exact=True).click()
        assert posted.value.status == expected
        page.wait_for_load_state()
        if expected == 303:
            page.wait_for_url(f'**/admin/{family}?week={WEEK}')
            _goto(page, path)
            _views(page, tmp_path, 'normal')
            row = page.locator('tr[data-week-id]')
            expect(row).to_contain_text('31.08.2026 – 06.09.2026')
            expect(row).to_contain_text('KW 36 / 2026')
            row.get_by_role('link', name='Woche öffnen', exact=True).click()
            assert page.url.endswith(f'/admin/{family}?week={WEEK}')
            _goto(page, path)
            row.get_by_role('link', name='Vorschau', exact=True).click()
            assert '/preview?week=' in page.url
            _goto(page, path)
            row.get_by_role('link', name='In Folgewoche kopieren', exact=True).click()
            expect(page.locator('main')).to_have_attribute('data-source-week', str(WEEK))
            expect(page.locator('main')).to_have_attribute('data-target-week', str(WEEK + timedelta(days=7)))
            expect(page.locator('#copy-description')).to_contain_text('in die leere Woche')
            _goto(page, path)
            page.locator('#new-week-title').click()
            page.locator('#new-week-date').fill(str(WEEK))
            page.locator('#new-week-name').fill('Eigene Woche <script>')
            page.locator('#new-week-note').fill('Hinweis behalten')
            before = _snapshot(engine)
        else:
            expect(page.locator('details[open] #new-week-date')).to_be_visible()
            expect(page.locator('#new-week-error')).to_be_visible()
            expect(page.locator('#new-week-name')).to_have_value('Eigene Woche <script>')
            expect(page.locator('#new-week-note')).to_have_value('Hinweis behalten')
            fields = _fields(page, form)
            assert fields['_csrf'] == token and fields['row_version'] == '0'
            assert set(fields) == {'_csrf', 'row_version', 'week', 'title', 'shared_note'}
            assert _snapshot(engine) == before
            _views(page, tmp_path, f'error-{expected}')
    for offset in range(1, 14):
        persist_week_header(engine, scope, WEEK + timedelta(weeks=offset),
                            {'title': 'Langtext ' + 'Wintergemüse' * 20, 'shared_note': ''}, 0)
    _goto(page, path)
    _views(page, tmp_path, 'dense-long')
    expect(page.locator('tr[data-week-id]')).to_have_count(12)
    page.get_by_role('navigation', name='Wochenseiten').get_by_role('link', name='Weiter').click()
    expect(page.locator('tr[data-week-id]')).to_have_count(2)
    _views(page, tmp_path, 'last-page', CORE)
    (tmp_path / 'fixture.json').write_text(json.dumps({
        'base': BASE, 'family': family, 'javascript': javascript,
        'fixture_sha256': hashlib.sha256(str(_snapshot(engine)).encode()).hexdigest(),
    }), encoding='utf-8')


def test_review_saved_context_receipt_and_stale_submission(weeks_ui, tmp_path):
    page, engine, scope, family, javascript, app = weeks_ui
    path = f'/admin/{family}/wochen/pruefung?week={WEEK}'
    persist_week_header(engine, scope, WEEK, {'title': 'Nur Wochenkopf', 'shared_note': ''}, 0)
    _goto(page, path)
    _views(page, tmp_path, 'empty-context')
    _save(engine, scope.profile_code, _values(scope.profile_code))
    _before(page, app, path, 'week_review.html', tmp_path)
    _goto(page, path)
    expected_context = get_week_review(engine, scope, WEEK)
    expect(page.locator('main .badge')).to_have_text('Noch zu prüfen')
    for service in expected_context['context']['services']:
        expect(page.get_by_text(service['notice'], exact=True)).to_be_visible()
    _views(page, tmp_path, 'unreviewed-long')
    fields = _fields(page, 'form:has([name=context_version])')
    assert set(fields) == {'_csrf', 'week', 'context_version'}
    assert fields['context_version'] == expected_context['token']
    before = _snapshot(engine)
    _focus(page, page.get_by_role('button', name=CONFIRM))
    with page.expect_response(lambda r: r.request.method == 'POST') as posted:
        page.keyboard.press('Enter')
    assert posted.value.status == 303
    page.wait_for_url('**' + path)
    expect(page.get_by_role('status')).to_contain_text('Dieser Stand wurde von Küche')
    expect(page.get_by_role('button', name=CONFIRM)).to_have_count(0)
    _views(page, tmp_path, 'checked')
    after = _snapshot(engine)
    assert before[:3] == after[:3] and before[4] == after[4]
    assert len(after[3]) == len(before[3]) + 1
    with engine.connect() as connection:
        version = resolve_week_ref(connection, scope, WEEK).row_version
    persist_week_header(engine, scope, WEEK, {'title': 'Geänderter Wochenkopf', 'shared_note': ''}, version)
    before = _snapshot(engine)
    response = page.context.request.post(path.split('?')[0], form=fields)
    assert response.status == 409
    _goto(page, path)
    expect(page.locator('main .badge')).to_have_text('Noch zu prüfen')
    expect(page.get_by_role('button', name=CONFIRM)).to_be_visible()
    assert get_week_review(engine, scope, WEEK)['receipt'] is None
    assert _snapshot(engine) == before
    _views(page, tmp_path, 'stale-review')
    with engine.connect() as connection:
        version = resolve_week_ref(connection, scope, WEEK).row_version
    persist_week_header(engine, scope, WEEK, {'title': 'Parallel geändert', 'shared_note': ''}, version)
    before = _snapshot(engine)
    with page.expect_response(lambda r: r.request.method == 'POST') as posted:
        page.get_by_role('button', name=CONFIRM).click()
    assert posted.value.status == 409
    page.wait_for_load_state()
    for width, height in CORE:
        page.set_viewport_size({'width': width, 'height': height})
        _capture(page, tmp_path, f'stale-409-{width}')
    assert _snapshot(engine) == before


def test_real_publication_statuses_and_read_only(weeks_ui, monkeypatch, tmp_path):
    page, engine, scope, family, javascript, app = weeks_ui
    values = _staff_values() if scope.profile_code == 'staff_guest' else _patient_values()
    version = _save_reviewed(engine, scope.profile_code, values)
    path = f'/admin/{family}/wochen'
    _goto(page, path)
    expect(page.locator('tr[data-week-id]')).to_have_attribute('data-status', 'ready')
    _views(page, tmp_path, 'ready', CORE)
    publish_draft(engine, scope.profile_code, WEEK, expected_row_version=version,
                  actor_id=scope.actor_id, issuer_engine=engine)
    _goto(page, path)
    expect(page.locator('tr[data-week-id]')).to_have_attribute('data-status', 'live')
    expect(page.locator('tr .badge')).to_have_text('Veröffentlicht')
    _views(page, tmp_path, 'published', CORE)
    with engine.connect() as connection:
        version = resolve_week_ref(connection, scope, WEEK).row_version
    persist_week_header(engine, scope, WEEK, {'title': 'Geänderter Plan', 'shared_note': ''},
                        version)
    review_saved_week(engine, scope.profile_code, WEEK, scope.actor_id)
    _goto(page, path)
    expect(page.locator('tr[data-week-id]')).to_have_attribute('data-status', 'changed')
    _views(page, tmp_path, 'changed', CORE)
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Admin', {'draft.read'})
    before = _snapshot(engine)
    _goto(page, path)
    expect(page.locator('#new-week-title')).to_have_count(0)
    expect(page.get_by_role('link', name='In Folgewoche kopieren')).to_have_count(0)
    expect(page.get_by_role('link', name='Vorschau', exact=True)).to_have_count(0)
    _views(page, tmp_path, 'read-only', CORE)
    _goto(page, path + f'/pruefung?week={WEEK}')
    expect(page.get_by_role('button', name=CONFIRM)).to_have_count(0)
    _views(page, tmp_path, 'read-only-checked', CORE)
    assert _snapshot(engine) == before


def test_zoom_200_percent_both_routes(weeks_ui, tmp_path):
    page, engine, scope, family, javascript, app = weeks_ui
    _save(engine, scope.profile_code, _values(scope.profile_code))
    for offset in range(1, 13):
        persist_week_header(engine, scope, WEEK + timedelta(weeks=offset),
                            {'title': 'Weitere gespeicherte Woche', 'shared_note': ''}, 0)
    outcomes = {}
    for route, name in ((f'/admin/{family}/wochen?page=2', 'list'),
                        (f'/admin/{family}/wochen/pruefung?week={WEEK}', 'review')):
        _goto(page, route)
        for width, height in CORE:
            page.set_viewport_size({'width': width, 'height': height})
            outcomes[f'{name}-{width}'] = _zoom(page, tmp_path, f'{name}-{width}')
    assert all(outcomes.values()), outcomes


def test_access_errors_and_failed_writes_preserve_versions(weeks_ui, monkeypatch, tmp_path):
    page, engine, scope, family, javascript, app = weeks_ui
    path = f'/admin/{family}/wochen'
    persist_week_header(engine, scope, WEEK, {'title': 'Geschützter Wochenkopf', 'shared_note': ''}, 0)
    review_path = path + f'/pruefung?week={WEEK}'
    _goto(page, review_path)
    fields = _fields(page, 'form:has([name=context_version])')
    before = _snapshot(engine)
    assert page.context.request.post(review_path.split('?')[0], form={**fields, '_csrf': ''}).status == 400
    assert page.context.request.post('/admin/' + ('patienten' if family == 'cafeteria' else 'cafeteria')
                                     + '/wochen/pruefung', form=fields).status == 409
    for route in (path + '?page=0', path + '/pruefung?week=invalid'):
        _goto(page, route, 400)
        for width, height in CORE:
            page.set_viewport_size({'width': width, 'height': height})
            _capture(page, tmp_path, f'invalid-{route.split("?")[0].split("/")[-1]}-{width}')
    def unavailable(*args, **kwargs):
        raise ComponentCatalogConfigurationError('Prüfumgebung nicht verfügbar.')
    with monkeypatch.context() as patch:
        patch.setattr(week_review_routes, 'review_week_context', unavailable)
        assert page.context.request.post(review_path.split('?')[0], form=fields).status == 503
        patch.setattr(week_review_routes, 'get_week_review', unavailable)
        patch.setattr(week_management_routes, 'find_weeks', unavailable)
        for route in (path, review_path):
            _goto(page, route, 503)
            for width, height in CORE:
                page.set_viewport_size({'width': width, 'height': height})
                _capture(page, tmp_path, f'503-{route.split("?")[0].split("/")[-1]}-{width}')
    cookie = page.context.cookies()
    for status_code in (403, 401):
        if status_code == 403:
            monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Admin', {'csv.export'})
            assert page.context.request.post(review_path.split('?')[0], form=fields).status == 403
        else:
            page.context.clear_cookies()
        for route in (path, review_path):
            _goto(page, route, status_code)
            expect(page.get_by_text('Geschützter Wochenkopf', exact=True)).to_have_count(0)
            for width, height in CORE:
                page.set_viewport_size({'width': width, 'height': height})
                _capture(page, tmp_path, f'{status_code}-{route.split("?")[0].split("/")[-1]}-{width}')
    page.context.add_cookies(cookie)
    assert _snapshot(engine) == before
