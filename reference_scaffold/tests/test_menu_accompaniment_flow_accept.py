"""Independent REC-008 acceptance across browser, database, exports and APIs."""
from __future__ import annotations
import csv
from concurrent.futures import ThreadPoolExecutor
import datetime as dt
import hashlib
import io
import json
# ruff: noqa: F811
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import parse_qs, urlsplit
import httpx
import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect
from pypdf import PdfReader
from sqlalchemy import Engine, text
import cafeteria
from cafeteria import db as database
from cafeteria import roles
from cafeteria.api_keys import API_KEY_SCOPES, create_api_key
from cafeteria.csvio import snapshot_to_csv
from cafeteria.workflow import derive_admin_status, load_draft, publish_draft, save_draft
from cafeteria.workflow_copy_store import copy_previous_week
from dishboard_mcp import server as dishboard_mcp
from review_support import review_saved_week, write_expectations
from test_admin_csv_import import _preview, _token
from test_admin_ux_browser import _submit_menu, live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, WEEK, _scope
from test_csv_accompaniment import _schema_2
from test_mcp_server import invoke_tool
from test_rendered_ui import admin_engine, browser  # noqa: F401
pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
ROOT = Path(__file__).resolve().parents[2]
EVIDENCE = ROOT / '.claude/evidence/acc-accept-0914'
OLD_WEEK = WEEK - dt.timedelta(days=7)
COPY_WEEK = WEEK + dt.timedelta(days=7)
IMPORT_WEEK = WEEK + dt.timedelta(days=14)
CONFIRM_WEEK = 'Wochenkopf und alle Ausgabehinweise als geprüft bestätigen'
ACCOMPANIMENT_NAMES = {'soup': 'Suppe', 'salad': 'Salat (gemischt und grün)'}
@pytest.fixture
def admin_app(admin_engine: Engine, monkeypatch: pytest.MonkeyPatch, tmp_path: Path) -> Flask:  # noqa: F811
    monkeypatch.setenv('DEMO_MODE', 'true')
    monkeypatch.setenv('SESSION_REDIS_URL', '')
    monkeypatch.setattr(cafeteria, 'init_app_database', lambda _app: None)
    app = cafeteria.create_app()
    app.config.update(
        TESTING=True,
        SECRET_KEY='accompaniment-acceptance-fixture',
        LAST_GOOD_DIR=str(tmp_path / 'last-good'),
        DEMO_MODE=True,
        DEMO_TODAY=DAY,
    )
    app.extensions['cafeteria_db'] = admin_engine
    app.extensions['cafeteria_auth_issuer_db'] = admin_engine
    return app
def _login_as(app: Flask, engine: Engine, role: str, identity: str, *, csrf: str = 'accept-csrf'):
    suffix = {'editor': '101', 'publisher': '102', 'reader': '103', 'admin': '104'}[identity]
    actor = database.upsert_entra_user(
        engine,
        {
            'tid': '00000000-0000-0000-0000-000000000001',
            'oid': f'00000000-0000-0000-0000-000000000{suffix}',
            'sub': f'accompaniment-accept-{identity}',
            'name': {'editor': 'Redaktion', 'publisher': 'Publikation', 'reader': 'Leser', 'admin': 'Admin'}[identity],
            'preferred_username': f'{identity}@example.invalid',
        },
        [role],
    )
    with engine.connect() as connection:
        authz_version = connection.execute(
            text('SELECT authz_version FROM cafeteria.users WHERE id=:actor'),
            {'actor': actor},
        ).scalar_one()
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': actor, 'name': identity.title()}
        session['authz_version'] = authz_version
        session['_csrf_token'] = csrf
    return client, actor
def _add_session(context, client, base_url: str) -> None:
    cookie = client.get_cookie(client.application.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    context.add_cookies([{
        'name': client.application.config['SESSION_COOKIE_NAME'], 'value': cookie.value, 'url': base_url,
    }])
def _week_values(week: dt.date, profile: str) -> dict[str, object]:
    values = _patient_values('Herbstwoche') if profile == 'patient' else _staff_values('Herbstwoche')
    weekdays = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')
    for offset, day in enumerate(values['days']):
        day['date'] = (week + dt.timedelta(days=offset)).isoformat()
        for service in day['services']:
            for option in service['options']:
                base = 'Kartoffelgratin' if option['type_code'] == 'MENU_1' else 'Gemüseteller'
                suffix = '' if offset == 0 and service['meal_code'] == 'LUNCH' else f' {weekdays[offset]} {service["meal_code"].title()}'
                option['title'] = base + suffix
    return values
def _save_review_publish(engine: Engine, actor: int, profile: str, week: dt.date, values: dict[str, object]) -> None:
    draft = load_draft(engine, profile, week, actor_id=actor, **write_expectations(engine, actor))
    version = save_draft(
        engine,
        profile,
        week,
        expected_row_version=draft['row_version'],
        actor_id=actor,
        values=values,
        **write_expectations(engine, actor),
    )
    version = review_saved_week(engine, profile, week, actor)
    publish_draft(
        engine,
        profile,
        week,
        expected_row_version=version,
        actor_id=actor,
        issuer_engine=engine,
    )
def _complete_week(engine: Engine, actor: int, profile: str, replacements: tuple[tuple[str, str, str, str], ...]) -> None:
    values = _week_values(WEEK, profile)
    first_day = values['days'][0]
    for meal, option_code, title, accompaniment in replacements:
        service = next(item for item in first_day['services'] if item['meal_code'] == meal)
        option = next(item for item in service['options'] if item['type_code'] == option_code)
        option['title'] = title
        option['accompaniment_code'] = accompaniment
    draft = load_draft(engine, profile, WEEK, actor_id=actor, **write_expectations(engine, actor))
    save_draft(
        engine, profile, WEEK, expected_row_version=draft['row_version'], actor_id=actor,
        values=values, **write_expectations(engine, actor),
    )
def _revision_bytes(engine: Engine, profile: str, week: dt.date) -> bytes:
    with engine.connect() as connection:
        raw = connection.execute(
            text(
                'SELECT r.snapshot_json::text FROM cafeteria.publication_revisions r '
                'JOIN cafeteria.menu_weeks w ON w.id=r.menu_week_id '
                'JOIN cafeteria.offer_profiles p ON p.id=w.profile_id '
                'WHERE p.code=:profile AND w.week_start=:week '
                'ORDER BY r.revision_number DESC LIMIT 1'
            ),
            {'profile': profile, 'week': week},
        ).scalar_one()
    return str(raw).encode()
def _menu_url(family: str, meal: str, option: str) -> str:
    return f'/admin/{family}/menu?week={DAY}&day={DAY}&meal={meal}&option={option}'
def _post_button(page: Page, name: str, status: int = 303) -> None:
    with page.expect_response(lambda result: result.request.method == 'POST') as result:
        page.get_by_role('button', name=name, exact=True).click()
    assert result.value.status == status
    page.wait_for_load_state()
def _create_template(page: Page, title: str) -> str:
    assert page.goto('/admin/gerichtvorlagen/neu').status == 200
    page.get_by_label('Titel', exact=True).fill(title)
    page.get_by_label('Menüart', exact=True).select_option('MENU_1')
    page.get_by_label('Geltungsbereich', exact=True).select_option('common')
    page.get_by_role('radio', name='Salat (gemischt und grün)', exact=True).check()
    _post_button(page, 'Speichern')
    link = page.get_by_role('link', name=title, exact=True)
    expect(link).to_be_visible()
    href = link.get_attribute('href')
    assert href is not None
    return urlsplit(href).path.rsplit('/', 1)[-1]
def _plan_template_menu(
    page: Page, template_id: str, family: str, title: str, accompaniment: str, *, javascript: bool = True,
) -> None:
    assert page.goto(f'/admin/gerichtvorlagen/{template_id}/einplanen?week={DAY}').status == 200
    page.get_by_label('Bereich', exact=True).select_option(
        'patient' if family == 'patienten' else 'staff_guest'
    )
    page.get_by_label('Woche ab Montag', exact=True).fill(DAY)
    _post_button(page, 'Ziel aktualisieren', 200)
    page.get_by_label('Wochentag', exact=True).select_option('0')
    page.get_by_label('Mahlzeit', exact=True).select_option('LUNCH')
    page.get_by_label('Menüart', exact=True).select_option('MENU_1')
    _post_button(page, 'Weiter zum Menü')
    expect(page.locator('#accompaniment-salad')).to_be_checked()
    expect(page.get_by_text('Aus Vorlage vorgeschlagen', exact=True)).to_be_visible()
    page.locator(f'#accompaniment-{accompaniment}').check()
    page.get_by_label('Menüname', exact=True).fill(title)
    if family == 'cafeteria':
        page.locator('[name="internal_chf"]').fill('9.50')
        page.locator('[name="external_chf"]').fill('14.50')
    with page.expect_response(lambda result: result.request.method == 'POST') as result:
        page.get_by_role('button', name='Menü speichern', exact=True).click()
    assert result.value.status == 303
    submitted = parse_qs(result.value.request.post_data or '', keep_blank_values=True)
    page.wait_for_load_state()
    assert submitted['accompaniment'] == [accompaniment]
def _save_direct_menu(
    page: Page, family: str, meal: str, option: str, title: str, accompaniment: str,
) -> None:
    assert page.goto(_menu_url(family, meal, option)).status == 200
    page.get_by_label('Menüname', exact=True).fill(title)
    page.locator(f'#accompaniment-{accompaniment}').check()
    if family == 'cafeteria':
        page.locator('[name="internal_chf"]').fill('8.50')
        page.locator('[name="external_chf"]').fill('13.50')
    submitted = _submit_menu(page)
    assert submitted['accompaniment'] == [accompaniment]
def _review_menu(page: Page, family: str, meal: str, option: str) -> None:
    assert page.goto(_menu_url(family, meal, option)).status == 200
    _post_button(page, 'Als geprüft bestätigen')
def _assert_grid(page: Page, family: str, selected: str, plain: str) -> None:
    assert page.goto(f'/admin/{family}?week={DAY}').status == 200
    selected_card = page.locator('.menu-slot').filter(has_text=selected)
    plain_card = page.locator('.menu-slot').filter(has_text=plain)
    expect(selected_card.locator('.menu-accompaniment')).to_have_text('Dazu: Suppe')
    expect(plain_card.locator('.menu-accompaniment')).to_have_count(0)
    line = selected_card.locator('.menu-accompaniment')
    ratio = line.evaluate('''node => {
        const values = value => value.match(/[\\d.]+/g).slice(0, 3).map(Number);
        const luminance = rgb => {
            const channels = rgb.map(value => value / 255).map(value =>
                value <= .04045 ? value / 12.92 : ((value + .055) / 1.055) ** 2.4);
            return .2126 * channels[0] + .7152 * channels[1] + .0722 * channels[2];
        };
        let background = node;
        while (background.parentElement && getComputedStyle(background).backgroundColor.includes('0)'))
            background = background.parentElement;
        const foreground = luminance(values(getComputedStyle(node).color));
        const behind = luminance(values(getComputedStyle(background).backgroundColor));
        return (Math.max(foreground, behind) + .05) / (Math.min(foreground, behind) + .05);
    }''')
    assert ratio >= 4.5, ratio
def _assert_output_page(page: Page, route: str, expected: list[str], plain_title: str) -> None:
    response = page.goto(route, wait_until='load')
    assert response is not None and response.status == 200
    body = page.locator('body').inner_text()
    assert plain_title in body
    lines = page.locator('.menu-accompaniment').all_text_contents()
    for value in expected:
        assert lines.count(f'Dazu: {value}') == 1, (route, lines)
    assert len(lines) == len(expected), (route, lines)
    assert 'Dazu: Dazu:' not in body
def _snapshot_options(payload: dict[str, object]) -> list[dict[str, object]]:
    return [
        option
        for day in payload.get('days', [])
        for service in day.get('services', [])
        for option in service.get('options', [])
    ]
def test_editor_to_publish_all_consumers_and_legacy_week(
    admin_app: Flask, admin_engine: Engine, browser: Browser, live_server: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:  # noqa: F811
    publisher, publisher_id = _login_as(
        admin_app, admin_engine, 'Cafeteria.Publisher', 'publisher'
    )
    _save_review_publish(admin_engine, publisher_id, 'patient', OLD_WEEK, _week_values(OLD_WEEK, 'patient'))
    old_bytes = _revision_bytes(admin_engine, 'patient', OLD_WEEK)
    old_hash = hashlib.sha256(old_bytes).hexdigest()
    assert b'accompaniment_' not in old_bytes and b'Dazu:' not in old_bytes
    assert derive_admin_status(admin_engine, 'patient', OLD_WEEK) == 'live'
    editor, _ = _login_as(admin_app, admin_engine, 'Cafeteria.Editor', 'editor')
    with browser.new_context(
        base_url=live_server,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        reduced_motion='reduce',
    ) as context:
        _add_session(context, editor, live_server)
        page = context.new_page()
        template_id = _create_template(page, 'Herbstteller')
        _plan_template_menu(
            page, template_id, 'patienten', 'Herbstteller Patienten', 'soup'
        )
        _save_direct_menu(
            page, 'patienten', 'LUNCH', 'VEGGIE', 'Ofengemüse Patienten', 'none'
        )
        _save_direct_menu(
            page, 'patienten', 'DINNER', 'MENU_1', 'Kräuterreis Patienten', 'salad'
        )
        _plan_template_menu(
            page, template_id, 'cafeteria', 'Herbstteller Cafeteria', 'soup'
        )
        _save_direct_menu(
            page, 'cafeteria', 'LUNCH', 'VEGGIE', 'Ofengemüse Cafeteria', 'none'
        )
        for family, slots in (
            ('patienten', (('LUNCH', 'MENU_1'), ('LUNCH', 'VEGGIE'), ('DINNER', 'MENU_1'))),
            ('cafeteria', (('LUNCH', 'MENU_1'), ('LUNCH', 'VEGGIE'))),
        ):
            for meal, option in slots:
                _review_menu(page, family, meal, option)
        _assert_grid(page, 'patienten', 'Herbstteller Patienten', 'Ofengemüse Patienten')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / 'patienten-grid-editor.png'), full_page=True)
        _assert_grid(page, 'cafeteria', 'Herbstteller Cafeteria', 'Ofengemüse Cafeteria')
        page.screenshot(path=str(EVIDENCE / 'cafeteria-grid-editor.png'), full_page=True)
        for family, selected, plain in (
            ('patienten', 'Herbstteller Patienten', 'Ofengemüse Patienten'),
            ('cafeteria', 'Herbstteller Cafeteria', 'Ofengemüse Cafeteria'),
        ):
            assert page.goto(f'/admin/{family}/menues').status == 200
            page.get_by_role('tab', name='Karten', exact=True).click()
            selected_card = page.locator('#menu-cards [data-menu-id]').filter(has_text=selected)
            plain_card = page.locator('#menu-cards [data-menu-id]').filter(has_text=plain)
            expect(selected_card.locator('.menu-accompaniment')).to_have_text('Dazu: Suppe')
            expect(plain_card.locator('.menu-accompaniment')).to_have_count(0)
        _complete_week(admin_engine, publisher_id, 'patient', (
            ('LUNCH', 'MENU_1', 'Herbstteller Patienten', 'soup'),
            ('LUNCH', 'VEGGIE', 'Ofengemüse Patienten', 'none'),
            ('DINNER', 'MENU_1', 'Kräuterreis Patienten', 'salad'),
        ))
        _complete_week(admin_engine, publisher_id, 'staff_guest', (
            ('LUNCH', 'MENU_1', 'Herbstteller Cafeteria', 'soup'),
            ('LUNCH', 'VEGGIE', 'Ofengemüse Cafeteria', 'none'),
        ))
        context.clear_cookies()
        _add_session(context, publisher, live_server)
        for family in ('patienten', 'cafeteria'):
            assert page.goto(f'/admin/{family}/wochen/pruefung?week={DAY}').status == 200
            _post_button(page, CONFIRM_WEEK)
            review_saved_week(
                admin_engine, 'patient' if family == 'patienten' else 'staff_guest', WEEK, publisher_id
            )
            assert page.goto(f'/admin/{family}?week={DAY}').status == 200
            trigger = page.locator('[data-bs-target="#week-publish-modal"]')
            assert trigger.is_enabled(), page.locator('#week-publish-guidance').inner_text()
            trigger.click()
            modal = page.locator('#week-publish-modal')
            expect(modal).to_be_visible()
            with page.expect_response(lambda result: result.request.method == 'POST') as published:
                modal.get_by_role('button', name='Veröffentlichen', exact=True).click()
            assert published.value.status == 303
            page.wait_for_load_state()
            expect(page.locator('main')).to_have_attribute('data-status', 'live')
        html_routes = (
            ('/cafeteria/heute/', ['Suppe'], 'Ofengemüse Cafeteria'),
            ('/cafeteria/wochenangebot/', ['Suppe'], 'Ofengemüse Cafeteria'),
            ('/druck/cafeteria/woche', ['Suppe'], 'Ofengemüse Cafeteria'),
            ('/patienten/heute/', ['Suppe', ACCOMPANIMENT_NAMES['salad']], 'Ofengemüse Patienten'),
            ('/patienten/wochenplan/', ['Suppe', ACCOMPANIMENT_NAMES['salad']], 'Ofengemüse Patienten'),
            ('/druck/patienten/woche', ['Suppe', ACCOMPANIMENT_NAMES['salad']], 'Ofengemüse Patienten'),
        )
        for route, expected, plain in html_routes:
            _assert_output_page(page, route, expected, plain)
        signage_routes = (
            ('/signage/cafeteria/tag', ['Suppe'], 'Ofengemüse Cafeteria'),
            ('/signage/cafeteria/woche', ['Suppe'], 'Ofengemüse Cafeteria'),
            ('/signage/patienten/tag', ['Suppe', ACCOMPANIMENT_NAMES['salad']], 'Ofengemüse Patienten'),
            ('/signage/patienten/woche', ['Suppe', ACCOMPANIMENT_NAMES['salad']], 'Ofengemüse Patienten'),
        )
        for width, height in ((1920, 1080), (3840, 2160)):
            page.set_viewport_size({'width': width, 'height': height})
            for route, expected, plain in signage_routes:
                _assert_output_page(page, route, expected, plain)
                assert page.evaluate(
                    'document.documentElement.scrollWidth <= innerWidth + 1 && '
                    'document.documentElement.scrollHeight <= innerHeight + 1'
                )
                assert page.locator('.menu-accompaniment').evaluate_all(
                    'nodes => nodes.every(node => node.scrollWidth <= node.clientWidth + 1 && '
                    'node.scrollHeight <= node.clientHeight + 1)'
                )
                page.screenshot(
                    path=str(EVIDENCE / f'{route.strip("/").replace("/", "-")}-{width}x{height}.png')
                )
        original = roles.ROLE_CAPABILITIES['Cafeteria.Editor']
        monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'draft.read', 'preview.read'})
        reader, _ = _login_as(admin_app, admin_engine, 'Cafeteria.Editor', 'reader')
        context.clear_cookies()
        _add_session(context, reader, live_server)
        for family, selected, plain in (
            ('patienten', 'Herbstteller Patienten', 'Ofengemüse Patienten'),
            ('cafeteria', 'Herbstteller Cafeteria', 'Ofengemüse Cafeteria'),
        ):
            _assert_grid(page, family, selected, plain)
            assert page.locator('form[data-menu-editor]').count() == 0
        assert page.goto(f'/admin/gerichtvorlagen/{template_id}').status == 200
        expect(page.get_by_role('button', name='Speichern', exact=True)).to_have_count(0)
        roles.ROLE_CAPABILITIES['Cafeteria.Editor'] = original
    assert hashlib.sha256(_revision_bytes(admin_engine, 'patient', OLD_WEEK)).hexdigest() == old_hash
    assert _revision_bytes(admin_engine, 'patient', OLD_WEEK) == old_bytes
    assert derive_admin_status(admin_engine, 'patient', OLD_WEEK) == 'live'
    for family, expected in (
        ('cafeteria', ['Dazu: Suppe']),
        ('patienten', ['Dazu: Suppe', f'Dazu: {ACCOMPANIMENT_NAMES["salad"]}']),
    ):
        response = publisher.get(f'/admin/{family}/preview/print?week={DAY}')
        assert response.status_code == 200 and response.mimetype == 'application/pdf'
        body = ' '.join(PdfReader(BytesIO(response.data)).pages[0].extract_text().split())
        for value in expected:
            assert body.count(value) == 1, body
        assert body.count('Dazu:') == len(expected)
        assert 'Ofengemüse' in body
    _, admin_id = _login_as(admin_app, admin_engine, 'Cafeteria.Admin', 'admin')
    record, token = create_api_key(
        admin_engine,
        actor_id=admin_id,
        label='Abnahme',
        scopes=API_KEY_SCOPES,
        channels=('cafeteria', 'patienten'),
        expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=1),
    )
    assert record.public_id
    headers = {'Authorization': f'Bearer {token}'}
    weeks = publisher.get('/api/v1/weeks/patienten', headers=headers)
    assert weeks.status_code == 200
    assert any(item['week_start'] == DAY and item['status'] == 'live' for item in weeks.get_json()['weeks'])
    preview = publisher.get(f'/api/v1/weeks/patienten/{DAY}/preview', headers=headers)
    assert preview.status_code == 200
    preview_options = _snapshot_options(preview.get_json())
    selected = next(item for item in preview_options if item['title'] == 'Herbstteller Patienten')
    plain = next(item for item in preview_options if item['title'] == 'Ofengemüse Patienten')
    assert (selected['accompaniment_code'], selected['accompaniment_name']) == ('soup', 'Suppe')
    assert 'accompaniment_code' not in plain and 'accompaniment_name' not in plain
    assert all(not str(item.get('accompaniment_name', '')).startswith('Dazu:') for item in preview_options)
    fhir = publisher.get('/fhir/NutritionProduct?channel=patienten').get_json()
    resources = [entry['resource'] for entry in fhir['entry']]
    selected_resource = next(item for item in resources if item['code']['text'] == 'Herbstteller Patienten')
    plain_resource = next(item for item in resources if item['code']['text'] == 'Ofengemüse Patienten')
    assert [note for note in selected_resource.get('note', []) if note['text'].startswith('Dazu:')] == [
        {'text': 'Dazu: Suppe'}
    ]
    assert not any(note['text'].startswith('Dazu:') for note in plain_resource.get('note', []))
    with httpx.Client(base_url=live_server, headers=headers, timeout=10.0) as http_client:
        mcp = dishboard_mcp.build_server(http_client)
        with ThreadPoolExecutor(max_workers=1) as executor:
            mcp_week = executor.submit(invoke_tool, mcp, 'get_week_menu', {'channel': 'patienten'}).result()
            mcp_preview = executor.submit(
                invoke_tool, mcp, 'get_week_preview', {'channel': 'patienten', 'week_start': DAY}
            ).result()
            assert any(item.get('accompaniment_code') == 'soup' for item in _snapshot_options(mcp_week))
            assert any(item.get('accompaniment_code') == 'soup' for item in _snapshot_options(mcp_preview))
            assert executor.submit(
                invoke_tool, mcp, 'list_weeks', {'channel': 'patienten'}
            ).result() == weeks.get_json()
    openapi = publisher.get('/api/v1/openapi.json').get_json()
    encoded_openapi = json.dumps(openapi)
    assert 'accompaniment_code' in encoded_openapi and 'accompaniment_name' in encoded_openapi
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_template_none_validation_viewports_keyboard_and_focus(
    admin_app: Flask, admin_engine: Engine, browser: Browser, live_server: str, javascript: bool,
) -> None:  # noqa: F811
    editor, _ = _login_as(admin_app, admin_engine, 'Cafeteria.Editor', 'editor')
    with browser.new_context(
        base_url=live_server,
        java_script_enabled=javascript,
        locale='de-CH',
        timezone_id='Europe/Zurich',
        reduced_motion='reduce',
    ) as context:
        _add_session(context, editor, live_server)
        page = context.new_page()
        title = 'Vorlage mit Skript' if javascript else 'Vorlage ohne Skript'
        template_id = _create_template(page, title)
        _plan_template_menu(
            page, template_id, 'patienten', 'Menü ohne Beilage', 'none', javascript=javascript
        )
        assert page.goto(_menu_url('patienten', 'LUNCH', 'MENU_1')).status == 200
        expect(page.locator('#accompaniment-none')).to_be_checked()
        group = page.get_by_role('group', name='Suppe oder Salat dazu')
        for width, height in ((1440, 900), (390, 844), (1024, 768), (768, 1024), (1920, 1080)):
            page.set_viewport_size({'width': width, 'height': height})
            expect(group).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            sizes = group.locator('label.form-check').evaluate_all(
                'labels => labels.map(label => label.getBoundingClientRect().height)'
            )
            assert len(sizes) == 3 and all(size >= 48 for size in sizes), sizes
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            page.screenshot(
                path=str(EVIDENCE / f'editor-{width}x{height}-{"js" if javascript else "nojs"}.png'),
                full_page=True,
            )
        none = page.locator('#accompaniment-none')
        none.focus()
        expect(none).to_be_focused()
        assert none.evaluate(
            "node => getComputedStyle(node).outlineStyle !== 'none' || "
            "getComputedStyle(node).boxShadow !== 'none'"
        )
        none.press('ArrowRight')
        expect(page.locator('#accompaniment-soup')).to_be_checked()
        page.locator('#accompaniment-none').check()
        if javascript:
            page.get_by_label('Menüname', exact=True).fill('Eingabe bleibt erhalten')
            invalid = page.locator('#accompaniment-salad')
            invalid.evaluate("input => { input.value = 'both'; }")
            invalid.check()
            submitted = _submit_menu(page, 400)
            assert submitted['accompaniment'] == ['both']
            expect(page.locator('#err-accompaniment')).to_be_visible()
            expect(page.locator('[name="accompaniment"][aria-invalid="true"]')).to_have_count(3)
            expect(page.get_by_label('Menüname', exact=True)).to_have_value('Eingabe bleibt erhalten')
    with admin_engine.connect() as connection:
        stored = connection.execute(text(
            'SELECT i.accompaniment FROM cafeteria.menu_items i '
            'JOIN cafeteria.menu_services s ON s.id=i.service_id '
            'JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id '
            "WHERE w.week_start=:week AND s.service_date=:day AND i.title='Menü ohne Beilage'"
        ), {'week': WEEK, 'day': WEEK}).scalar_one()
    assert stored == 'none'
def test_editor_real_browser_zoom_two_hundred_percent(
    admin_app: Flask, admin_engine: Engine, browser: Browser, live_server: str, tmp_path: Path,
) -> None:  # noqa: F811
    editor, _ = _login_as(admin_app, admin_engine, 'Cafeteria.Editor', 'editor')
    with TemporaryDirectory(prefix='accept-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(
            profile,
            channel='chromium',
            headless=True,
            no_viewport=True,
            locale='de-CH',
            timezone_id='Europe/Zurich',
            reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate(
                'new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))'
            ) == 2
            _add_session(context, editor, live_server)
            assert page.goto(live_server + _menu_url('patienten', 'LUNCH', 'MENU_1')).status == 200
            metrics = context.new_cdp_session(page).send('Page.getLayoutMetrics')
            assert metrics['cssVisualViewport']['zoom'] == 2
            assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
            expect(page.get_by_role('group', name='Suppe oder Salat dazu')).to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(EVIDENCE / 'editor-native-zoom-two-hundred.png'), full_page=True)
def _shift_csv_week(payload: bytes, days: int) -> bytes:
    reader = csv.DictReader(io.StringIO(payload.decode('utf-8-sig')), delimiter=';')
    rows = list(reader)
    assert reader.fieldnames is not None
    for row in rows:
        source_date = row['datum']
        row['datum'] = (dt.date.fromisoformat(source_date) + dt.timedelta(days=days)).isoformat()
        row['external_id'] = row['external_id'].replace(source_date, row['datum'])
    target = io.StringIO(newline='')
    writer = csv.DictWriter(target, fieldnames=reader.fieldnames, delimiter=';', lineterminator='\r\n')
    writer.writeheader()
    writer.writerows(rows)
    return ('\ufeff' + target.getvalue()).encode()
def _stored_codes(engine: Engine, week: dt.date) -> dict[str, str]:
    with engine.connect() as connection:
        rows = connection.execute(text(
            'SELECT i.title,i.accompaniment FROM cafeteria.menu_items i '
            'JOIN cafeteria.menu_services s ON s.id=i.service_id '
            'JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id '
            'JOIN cafeteria.offer_profiles p ON p.id=w.profile_id '
            "WHERE p.code='patient' AND w.week_start=:week ORDER BY s.service_date,i.id"
        ), {'week': week}).all()
    return {str(title): str(code) for title, code in rows}
def test_csv_three_roundtrip_schema_two_replacement_and_previous_week_copy(
    admin_app: Flask, admin_engine: Engine,
) -> None:  # noqa: F811
    client, actor = _login_as(
        admin_app, admin_engine, 'Cafeteria.Publisher', 'publisher', csrf='csv-import-csrf'
    )
    values = _week_values(WEEK, 'patient')
    first = values['days'][0]['services']
    first[0]['options'][0]['accompaniment_code'] = 'soup'
    first[0]['options'][1]['accompaniment_code'] = 'salad'
    first[1]['options'][0]['accompaniment_code'] = 'none'
    _save_review_publish(admin_engine, actor, 'patient', WEEK, values)
    published = database.active_snapshot(admin_engine, 'patient', DAY)
    assert published is not None
    source = load_draft(
        admin_engine, 'patient', WEEK, actor_id=actor, **write_expectations(admin_engine, actor)
    )
    copy_previous_week(
        admin_engine,
        _scope(admin_engine, actor, 'patient'),
        COPY_WEEK,
        0,
        source_row_version=source['row_version'],
    )
    copied = _stored_codes(admin_engine, COPY_WEEK)
    assert copied['Kartoffelgratin'] == 'soup' and copied['Gemüseteller'] == 'salad'
    schema_three = snapshot_to_csv(published)
    shifted = _shift_csv_week(schema_three, 14)
    preview = _preview(client, shifted, 'beilagen-schema-drei.csv')
    assert preview.status_code == 200 and 'Bereit zum Import' in preview.get_data(as_text=True)
    imported = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': _token(preview)},
    )
    assert imported.status_code == 303
    stored = _stored_codes(admin_engine, IMPORT_WEEK)
    assert stored['Kartoffelgratin'] == 'soup' and stored['Gemüseteller'] == 'salad'
    assert set(stored.values()) >= {'soup', 'salad', 'none'}
    schema_two = _schema_2(shifted)
    replacement = _preview(client, schema_two, 'beilagen-schema-zwei.csv')
    assert replacement.status_code == 200
    assert 'Bestehende Beilagen werden auf «Keine» zurückgesetzt.' in replacement.get_data(as_text=True)
    replaced = client.post(
        '/admin/import',
        data={'_csrf': 'csv-import-csrf', 'import_token': _token(replacement)},
    )
    assert replaced.status_code == 303
    assert set(_stored_codes(admin_engine, IMPORT_WEEK).values()) == {'none'}
