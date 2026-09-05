from __future__ import annotations

import os
import re
import subprocess
from pathlib import Path

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader
from playwright.sync_api import Page, expect
from sqlalchemy import Engine, text

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server, page_context,
)

ROOT = Path(__file__).resolve().parents[2]
BASE_REVISION = 'e89872e4483132bff74b7df05634e740af5d01e0'
TEMPLATE = 'admin/import_preview.html'
INVALID_CSV = b'wrong;header\ninvalid;row\n'


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


def _assert_accessible_layout(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    controls = page.locator('main a, main button, main input:not([type="hidden"])')
    for control in controls.all():
        if control.get_attribute('type') in {'checkbox', 'radio'}:
            control = control.locator('xpath=ancestor::label')
        box = control.bounding_box()
        assert box is not None and box['width'] >= 48 and box['height'] >= 48
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
    expect(page.get_by_label('CSV-Datei', exact=True)).to_be_visible()
    assert page.locator('input[name="import_token"]').count() == 0
    _capture(page, 'after', 'empty', width)
    _assert_accessible_layout(page)

    _capture_original(page, admin_app, 'invalid', width, INVALID_CSV)
    page.goto('/admin/import-preview')
    _upload(page, INVALID_CSV)
    expect(page.locator('main')).to_have_attribute('data-state', 'error')
    alert = page.get_by_role('alert')
    expect(page.get_by_label('Korrigierte CSV-Datei')).to_be_focused()
    expect(page.get_by_label('Korrigierte CSV-Datei')).to_have_attribute('aria-describedby', 'file-error')
    expect(page.get_by_label('Korrigierte CSV-Datei')).to_have_attribute('aria-invalid', 'true')
    expect(alert).to_contain_text('Datei korrigieren')
    expect(alert).to_contain_text('erneut aus')
    expect(alert).to_contain_text('Zeile 1, Spalte')
    expect(page.get_by_label('Korrigierte CSV-Datei')).to_be_visible()
    expect(page.locator('main .btn-primary')).to_have_text('Vorschau prüfen')
    assert page.locator('input[name="import_token"]').count() == 0
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
    summary = page.get_by_role('status')
    expect(summary).to_contain_text(label)
    expect(summary).to_contain_text('KW 36 · ab 31.08.2026')
    expect(summary).to_contain_text(f'{rows} Datenzeilen geprüft')
    assert 'staff_guest' not in page.locator('main').inner_text()
    assert 'Profil patient' not in page.locator('main').inner_text()
    primary = page.locator('main .btn-primary')
    expect(primary).to_have_text('Geprüfte Datei importieren')
    for element in (summary, primary):
        box = element.bounding_box()
        assert box is not None and box['y'] >= 0 and box['y'] + box['height'] <= height
    expect(page.get_by_role('heading', name='Andere Datei prüfen')).to_be_visible()
    back = page.get_by_role('link', name='Zurück zur Wochenübersicht')
    expect(back).to_have_attribute('href', f'/admin/{family}?week=2026-08-31')
    fields = page.locator('form[action$="/import"] input').evaluate_all(
        'elements => elements.map(element => element.name)'
    )
    assert fields == ['_csrf', 'import_token']
    assert page.locator('input[name="import_token"]').input_value()
    if family == 'patienten':
        assert re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I) is None
    with admin_engine.connect() as connection:
        assert connection.execute(text('SELECT count(*) FROM cafeteria.menu_items')).scalar_one() == 0
    _capture(page, 'after', f'ready-{family}', width)
    _assert_accessible_layout(page)
