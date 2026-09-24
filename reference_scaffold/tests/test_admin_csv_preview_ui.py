from __future__ import annotations

import csv
import io
import json
import os
import re
import subprocess
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from flask import Flask
from flask import render_template
from jinja2 import ChoiceLoader, DictLoader
from playwright.sync_api import Page, expect, sync_playwright
from sqlalchemy import Engine, text

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)
from test_rendered_ui import _login
from cafeteria.template_filters import register_template_filters
from cafeteria.ui import register_ui

ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = 'e89872e4483132bff74b7df05634e740af5d01e0'
TEMPLATE = 'admin/import_preview.html'
INVALID_CSV = b'wrong;header\ninvalid;row\n'
SCHEMA_2_WARNING = 'Schema-2-Vollimport: Bestehende Beilagen werden auf «Keine» zurückgesetzt.'
PREVIEW_FIELDS = ('_csrf', 'file')
IMPORT_FIELDS = ('_csrf', 'import_token')
VIEWPORTS = ((360, 800), (768, 1024), (1024, 768), (1440, 900))


@pytest.mark.parametrize(('locale', 'pending', 'more'), (
    ('de', 'Offen', 'Weitere Optionen'), ('en', 'Pending', 'More options'),
))
def test_csv_preview_registered_semantics(locale: str, pending: str, more: str) -> None:
    application = Flask(__name__, template_folder=str(ROOT / 'reference_scaffold/cafeteria/templates'))
    application.config.update(TESTING=True, UI_LOCALE=locale)
    register_ui(application)
    register_template_filters(application)
    application.jinja_env.loader = ChoiceLoader([
        DictLoader({'admin/base_tabler.html': '{% block page_header %}{% endblock %}{% block content %}{% endblock %}'}),
        application.jinja_env.loader,
    ])
    for endpoint in ('import_preview', 'import_csv', 'cafeteria'):
        application.add_url_rule('/' + endpoint, endpoint='admin.' + endpoint, view_func=lambda: '')
    with application.test_request_context():
        rendered = render_template(TEMPLATE, result=None, import_token=None, csrf_token=lambda: 'test-csrf')
    assert pending in rendered
    assert more in rendered
    assert 'id="csv-more"' in rendered


@pytest.mark.parametrize('width', (360, 1440))
def test_csv_preview_review_evidence(
    page_context: Page, tmp_path: Path, width: int,  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': width, 'height': 900 if width == 1440 else 800})
    measurements = []
    for state, source in (
        ('empty', None), ('invalid', INVALID_CSV),
        ('ready', 'menu_cafeteria_example.csv'),
        ('warning', _schema_2_example('menu_cafeteria_example.csv')),
    ):
        page.goto('/admin/import-preview')
        if source is not None:
            _upload(page, source)
        _assert_accessible_layout(page)
        metric = _metrics(page)
        assert metric['primary'] == 1, metric
        assert metric['height'] <= (2000 if width == 360 else 1000), metric
        rows = page.locator('.csv-upload-grid, .csv-issue-row, .csv-warning-row')
        assert rows.count() > 0
        if width == 1440:
            for row in rows.all():
                box = row.bounding_box()
                assert box is not None and 0 < box['height'] <= 96, box
        if state in ('ready', 'warning'):
            expect(page.locator('.admin-statusbar-item').filter(
                has=page.get_by_text('Zeilen', exact=True),
            ).locator('dd')).to_have_text('10')
        expect(page.locator('#csv-more')).to_have_attribute('class', 'admin-compact-details admin-disclosure')
        assert page.locator('#csv-more[open]').count() == (0 if state == 'empty' else 1)
        page.evaluate('document.activeElement.blur(); window.scrollTo(0, 0)')
        page.screenshot(path=str(tmp_path / f'after-{state}-{width}.png'), full_page=True)
        measurements.append(dict(state=state, width=width, **metric))
    (tmp_path / f'measurements-{width}.json').write_text(json.dumps(measurements), encoding='utf-8')


def _schema_2_example(filename: str) -> bytes:
    source = (ROOT / 'csv' / filename).read_text(encoding='utf-8-sig')
    reader = csv.DictReader(io.StringIO(source), delimiter=';')
    drop = {'beilage_dazu', 'suppe', 'suppe_geltung', 'dessert', 'dessert_geltung'}
    headers = [header for header in reader.fieldnames or [] if header not in drop]
    output = io.StringIO(newline='')
    writer = csv.DictWriter(output, fieldnames=headers, delimiter=';', lineterminator='\r\n')
    writer.writeheader()
    for row in reader:
        row['schema_version'] = '2'
        writer.writerow({header: row[header] for header in headers})
    return ('\ufeff' + output.getvalue()).encode()


def _form_names(page: Page, selector: str) -> list[str]:
    return page.locator(f'{selector} input, {selector} select, {selector} textarea, {selector} button[name]').evaluate_all(
        """elements => elements.map(element => element.name).filter(name => name)"""
    )


def _upload(page: Page, source: str | bytes) -> None:
    upload = page.locator('input[type="file"]')
    if isinstance(source, bytes):
        upload.set_input_files({'name': 'korrektur.csv', 'mimeType': 'text/csv', 'buffer': source})
    else:
        upload.set_input_files(ROOT / 'csv' / source)
    with page.expect_response(
        lambda response: response.request.method == 'POST' and response.url.endswith('/import-preview')
    ) as checked:
        page.locator('form[enctype="multipart/form-data"] button[type="submit"]').click()
    assert checked.value.status == 200
    page.wait_for_load_state()


def _capture(page: Page, phase: str, state: str, width: int) -> None:
    proof_path = os.environ.get('CSV_PREVIEW_PROOF_DIR')
    if proof_path:
        folder = Path(proof_path)
        folder.mkdir(parents=True, exist_ok=True)
        if phase == 'after':
            assert page.locator('[style], [onclick], script:not([src])').count() == 0
        page.screenshot(
            path=str(folder / f'{phase}-{state}-{width}.png'), full_page=True, caret='initial',
        )


def _capture_original(
    page: Page, application: Flask, state: str, width: int, source: str | bytes | None = None,
) -> None:
    if not os.environ.get('CSV_PREVIEW_PROOF_DIR'):
        return
    original = subprocess.run(
        ['rtk', 'git', '-C', str(ROOT), 'cat-file', 'blob',
         f'{BASE_REVISION}:reference_scaffold/cafeteria/templates/{TEMPLATE}'],
        check=True, capture_output=True, text=True,
    ).stdout
    loader = application.jinja_env.loader
    assert loader is not None
    application.jinja_env.loader = ChoiceLoader([DictLoader({TEMPLATE: original}), loader])
    application.jinja_env.cache.clear()
    try:
        page.goto('/admin/import-preview')
        if source is not None:
            _upload(page, source)
        _capture(page, 'before', state, width)
    finally:
        application.jinja_env.loader = loader
        application.jinja_env.cache.clear()


def _metrics(page: Page) -> dict[str, object]:
    return page.evaluate(
        """() => {
            const row = document.querySelector('.csv-issue-row, .csv-upload-grid');
            return {
                height: document.documentElement.scrollHeight,
                overflow: document.documentElement.scrollWidth > innerWidth + 1,
                primary: document.querySelectorAll('main .btn-primary').length,
                open: document.querySelectorAll('main details[open]').length,
                row: row ? row.getBoundingClientRect().height : 0,
            };
        }"""
    )


def _assert_accessible_layout(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    controls = page.locator('main a:visible, main button:visible, main input:not([type="hidden"]):visible, main summary:visible')
    for control in controls.all():
        if control.get_attribute('type') in {'checkbox', 'radio'}:
            control = control.locator('xpath=ancestor::label')
        box = control.bounding_box()
        assert box is not None and box['height'] >= 48
        assert box['width'] >= 48
    assert page.locator('link[href$="/app.css"]').count() == 0
    assert page.locator('main').count() == 1
    back = page.get_by_role('link', name='Zurück zur Wochenübersicht')
    back.focus()
    expect(back).to_be_focused()
    assert back.evaluate('element => getComputedStyle(element).outlineStyle !== "none"')
    assert page.locator('[style], [onclick], script:not([src])').count() == 0


@pytest.mark.parametrize(('width', 'height'), ((360, 844), (1280, 1100)))
def test_csv_preview_empty_and_invalid_have_clear_next_actions(
    page_context: Page, admin_app: Flask, width: int, height: int,  # noqa: F811
) -> None:
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    _capture_original(page, admin_app, 'empty', width)
    page.goto('/admin/import-preview')
    expect(page.locator('main')).to_have_attribute('data-state', 'empty')
    expect(page.get_by_text('Die Vorschau speichert noch keinen Entwurf.')).to_be_visible()
    expect(page.locator('main .btn-primary')).to_have_text('Vorschau prüfen')
    expect(page.locator('main .btn-primary')).to_have_count(1)
    expect(page.get_by_label('CSV-Datei', exact=True)).to_be_visible()
    expect(page.locator('dl.admin-statusbar')).to_contain_text('Offen')
    expect(page.locator('dl.admin-statusbar .admin-statusbar-link')).to_have_attribute('href', '#csv-upload')
    assert page.locator('input[name="import_token"]').count() == 0
    assert _form_names(page, '#csv-upload') == list(PREVIEW_FIELDS)
    _capture(page, 'after', 'empty', width)
    _assert_accessible_layout(page)

    _capture_original(page, admin_app, 'invalid', width, INVALID_CSV)
    page.goto('/admin/import-preview')
    _upload(page, INVALID_CSV)
    expect(page.locator('main')).to_have_attribute('data-state', 'error')
    alert = page.get_by_role('alert')
    expect(alert).to_be_focused()
    expect(page.get_by_label('Korrigierte CSV-Datei')).to_have_attribute('aria-describedby', 'file-error')
    expect(page.get_by_label('Korrigierte CSV-Datei')).to_have_attribute('aria-invalid', 'true')
    expect(alert).to_contain_text('Datei korrigieren')
    expect(alert).to_contain_text('erneut aus')
    expect(alert).to_contain_text('Zeile 1, Spalte')
    expect(page.get_by_label('Korrigierte CSV-Datei')).to_be_visible()
    expect(page.locator('main .btn-primary')).to_have_text('Vorschau prüfen')
    expect(page.locator('main .btn-primary')).to_have_count(1)
    expect(page.locator('dl.admin-statusbar')).to_contain_text('Fehlerhaft')
    expect(page.locator('dl.admin-statusbar .admin-statusbar-link')).to_have_attribute('href', '#file-error')
    assert page.locator('input[name="import_token"]').count() == 0
    assert _form_names(page, '#csv-upload') == list(PREVIEW_FIELDS)
    _capture(page, 'after', 'invalid', width)
    _assert_accessible_layout(page)


@pytest.mark.parametrize(('width', 'height'), ((360, 844), (1280, 1100)))
@pytest.mark.parametrize(('family', 'filename', 'label', 'rows'), (
    ('patienten', 'menu_patient_example.csv', 'Patientenplan', 28),
    ('cafeteria', 'menu_cafeteria_example.csv', 'Cafeteria', 10),
))
def test_csv_preview_ready_exposes_destination_before_import(
    page_context: Page, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    width: int, height: int, family: str, filename: str, label: str, rows: int,
) -> None:
    page = page_context
    page.set_viewport_size({'width': width, 'height': height})
    _capture_original(page, admin_app, f'ready-{family}', width, filename)
    page.goto('/admin/import-preview')
    _upload(page, filename)
    expect(page.locator('main')).to_have_attribute('data-state', 'ready')
    statusbar = page.locator('dl.admin-statusbar')
    expect(statusbar).to_contain_text(label)
    expect(statusbar).to_contain_text('KW 36 · ab 31.08.2026')
    expect(statusbar).to_contain_text('Bereit')
    expect(statusbar.locator('.admin-statusbar-item').filter(has=page.get_by_text('Zeilen', exact=True)).locator('dd')).to_have_text(str(rows))
    expect(page.get_by_role('status')).to_contain_text('Geprüftes Ergebnis der zuletzt geprüften Datei')
    assert 'staff_guest' not in page.locator('main').inner_text()
    assert 'Profil patient' not in page.locator('main').inner_text()
    primary = page.locator('main .btn-primary')
    expect(primary).to_have_text('Geprüfte Datei importieren')
    expect(primary).to_have_count(1)
    for element in (statusbar, primary):
        box = element.bounding_box()
        assert box is not None and box['y'] >= 0 and box['y'] + box['height'] <= height
    expect(page.get_by_role('heading', name='Andere Datei prüfen')).to_be_visible()
    back = page.get_by_role('link', name='Zurück zur Wochenübersicht')
    expect(back).to_have_attribute('href', f'/admin/{family}?week=2026-08-31')
    fields = page.locator('form[action$="/import"] input').evaluate_all(
        'elements => elements.map(element => element.name)'
    )
    assert fields == list(IMPORT_FIELDS)
    assert _form_names(page, '#csv-upload') == list(PREVIEW_FIELDS)
    assert page.locator('input[name="import_token"]').input_value()
    if family == 'patienten':
        assert re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I) is None
    with admin_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 0
    _capture(page, 'after', f'ready-{family}', width)
    _assert_accessible_layout(page)


def test_csv_preview_warns_for_schema_2_only_and_escapes_warning(
    page_context: Page, admin_app: Flask, monkeypatch: pytest.MonkeyPatch,  # noqa: F811
) -> None:
    from cafeteria.admin import routes as admin_routes

    page = page_context
    schema_2 = _schema_2_example('menu_cafeteria_example.csv')
    page.goto('/admin/import-preview')
    _upload(page, schema_2)
    warning = page.locator('[data-csv-warnings]')
    expect(warning).to_be_visible()
    expect(warning).to_contain_text(SCHEMA_2_WARNING)
    expect(page.locator('dl.admin-statusbar')).to_contain_text('Warnungen')
    expect(page.locator('dl.admin-statusbar .admin-statusbar-link')).to_have_attribute('href', '#csv-warnings')

    validate_upload = admin_routes.validate_upload

    def validate_with_escape_probe(stream):
        result = validate_upload(stream)
        if result.get('schema_version') == 2:
            result['warnings'] = [f'{SCHEMA_2_WARNING} <script data-warning-probe>probe()</script>']
        return result

    monkeypatch.setattr(admin_routes, 'validate_upload', validate_with_escape_probe)
    _upload(page, schema_2)
    expect(warning).to_contain_text('<script data-warning-probe>probe()</script>')
    assert page.locator('script[data-warning-probe]').count() == 0

    _upload(page, 'menu_cafeteria_example.csv')
    assert page.locator('[data-csv-warnings]').count() == 0


@pytest.mark.parametrize(('family', 'profile', 'filename', 'rows'), (
    ('patienten', 'patient', 'menu_patient_example.csv', 28),
    ('cafeteria', 'staff_guest', 'menu_cafeteria_example.csv', 10),
))
def test_native_csv_preview_and_draft_import_without_javascript(
    browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, filename: str, rows: int,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    with browser.new_context(
        base_url=live_server, java_script_enabled=False, reduced_motion='reduce',
        viewport={'width': 390, 'height': 844},
    ) as context:
        cookie_name = admin_app.config['SESSION_COOKIE_NAME']
        cookie = client.get_cookie(cookie_name)
        assert cookie is not None
        context.add_cookies([{'name': cookie_name, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        page.goto('/admin/import-preview')
        source = (ROOT / 'csv' / filename).read_text(encoding='utf-8-sig')
        title = source.splitlines()[1].split(';')[7]
        _upload(page, source.replace(f';{title};', ';;', 1).encode())
        expect(page.locator('main')).to_have_attribute('data-state', 'error')
        expect(page.get_by_role('alert')).to_contain_text('Zeile 2, Spalte 8')
        assert page.locator('input[name="import_token"]').count() == 0
        with admin_engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == 0

        _upload(page, filename)
        expect(page.locator('main')).to_have_attribute('data-state', 'ready')
        expect(page.locator('.admin-statusbar-item').filter(has=page.get_by_text('Zeilen', exact=True)).locator('dd')).to_have_text(str(rows))
        expect(page.get_by_role('status')).to_contain_text('Geprüftes Ergebnis der zuletzt geprüften Datei')
        assert page.locator('form[action$="/import"] input').evaluate_all(
            'elements => elements.map(element => element.name)'
        ) == list(IMPORT_FIELDS)
        with admin_engine.connect() as connection:
            assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_weeks')).scalar_one() == 0
            assert connection.execute(text('SELECT count(*) FROM cafeteria.publication_revisions')).scalar_one() == 0

        with page.expect_response(
            lambda response: response.request.method == 'POST' and response.url.endswith('/admin/import')
        ) as imported:
            page.get_by_role('button', name='Geprüfte Datei importieren', exact=True).click()
        assert imported.value.status == 303
        expect(page).to_have_url(f'{live_server}/admin/{family}?week=2026-08-31')
        with admin_engine.connect() as connection:
            result = connection.execute(text('''
                SELECT p.code, w.workflow_state, count(i.id)
                FROM cafeteria.menu_weeks w
                JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
                JOIN cafeteria.menu_services s ON s.menu_week_id=w.id
                JOIN cafeteria.menu_items i ON i.service_id=s.id
                GROUP BY p.code, w.workflow_state
            ''')).one()
            assert tuple(result) == (profile, 'draft', rows)
            assert connection.execute(text('SELECT count(*) FROM cafeteria.publication_revisions')).scalar_one() == 0


def test_csv_preview_frame_viewports_statusbar_nojs_keyboard(
    live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    """Own sync_playwright start: 360/768/1024/1440, No-JS, keyboard, status bar, overflow."""
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie_name = admin_app.config['SESSION_COOKIE_NAME']
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    measurements: list[dict[str, object]] = []

    def inspect() -> None:
        with sync_playwright() as playwright:
            instance = playwright.chromium.launch(
                headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'],
            )
            try:
                for javascript in (False, True):
                    for width, height in VIEWPORTS:
                        context = instance.new_context(
                            base_url=live_server,
                            java_script_enabled=javascript,
                            reduced_motion='reduce',
                            viewport={'width': width, 'height': height},
                        )
                        context.add_cookies([
                            {'name': cookie_name, 'value': cookie.value, 'url': live_server},
                        ])
                        page = context.new_page()
                        page.goto('/admin/import-preview', wait_until='load')
                        metric = _metrics(page)
                        measurements.append(dict(state='empty', width=width, javascript=javascript, **metric))
                        assert metric['overflow'] is False, metric
                        assert metric['primary'] == 1, metric
                        assert metric['open'] == 0, metric
                        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
                        expect(page.locator('#csv-upload')).to_have_attribute('data-loading', '')
                        more = page.locator('#csv-more > summary')
                        more.focus()
                        expect(more).to_be_focused()
                        more.press('Enter')
                        expect(page.get_by_text('Cafeteria und Patientenplan verwenden getrennte Formate.', exact=False)).to_be_visible()
                        more.press('Enter')
                        expect(page.locator('#csv-more')).not_to_have_attribute('open', '')
                        expect(page.locator('dl.admin-statusbar')).to_contain_text('Offen')
                        expect(page.locator('main .btn-primary')).to_have_text('Vorschau prüfen')
                        if width == 360:
                            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
                        primary = page.locator('main .btn-primary')
                        primary.focus()
                        expect(primary).to_be_focused()
                        assert primary.evaluate('element => getComputedStyle(element).outlineStyle !== "none"')
                        assert _form_names(page, '#csv-upload') == list(PREVIEW_FIELDS)
                        context.close()

                context = instance.new_context(
                    base_url=live_server, java_script_enabled=False, reduced_motion='reduce',
                    viewport={'width': 360, 'height': 800},
                )
                context.add_cookies([{'name': cookie_name, 'value': cookie.value, 'url': live_server}])
                page = context.new_page()
                page.goto('/admin/import-preview', wait_until='load')
                _upload(page, INVALID_CSV)
                metric = _metrics(page)
                measurements.append(dict(state='invalid', width=360, javascript=False, **metric))
                assert metric['overflow'] is False, metric
                assert metric['primary'] == 1, metric
                expect(page.locator('dl.admin-statusbar')).to_contain_text('Fehlerhaft')
                expect(page.locator('.csv-issue-row')).to_contain_text('Zeile 1, Spalte')
                assert 0 < float(metric['row']) <= 96, metric
                assert _form_names(page, '#csv-upload') == list(PREVIEW_FIELDS)

                _upload(page, 'menu_cafeteria_example.csv')
                metric = _metrics(page)
                measurements.append(dict(state='ready', width=360, javascript=False, **metric))
                assert metric['overflow'] is False, metric
                assert metric['primary'] == 1, metric
                expect(page.locator('dl.admin-statusbar')).to_contain_text('Cafeteria')
                expect(page.locator('dl.admin-statusbar')).to_contain_text('Bereit')
                expect(page.locator('main .btn-primary')).to_have_text('Geprüfte Datei importieren')
                assert page.locator('form[action$="/import"] input').evaluate_all(
                    'elements => elements.map(element => element.name)'
                ) == list(IMPORT_FIELDS)
                page.set_viewport_size({'width': 1440, 'height': 900})
                metric = _metrics(page)
                measurements.append(dict(state='ready', width=1440, javascript=False, **metric))
                assert metric['overflow'] is False, metric
                assert metric['primary'] == 1, metric
                context.close()
            finally:
                instance.close()

    with ThreadPoolExecutor(max_workers=1) as worker:
        worker.submit(inspect).result()
    print('WP17_MEASUREMENTS', json.dumps(measurements))
    assert any(item['state'] == 'empty' and item['width'] == 360 for item in measurements)
    assert any(item['state'] == 'ready' and item['width'] == 1440 for item in measurements)
