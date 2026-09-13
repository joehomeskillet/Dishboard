from __future__ import annotations

import re
from copy import deepcopy
from datetime import date
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, expect
from sqlalchemy import Engine

from cafeteria.admin import menu_collection_routes
from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_workflow_routes import (
    DAY,
    ROOT,
    WEEK,
    _login,
    _payload,
    _register,
    _scope,
    database_engine as database_engine,
)
from test_public_mobile_ui import http_app as http_app
from test_public_mobile_ui import public_server as public_server
from test_public_ops_browser import card_geometry
from test_rendered_ui import app as app
from test_rendered_ui import browser as browser


ACCOMPANIMENT_NAME = 'Salat (gemischt und grün)'
ACCOMPANIMENT_TEXT = f'Dazu: {ACCOMPANIMENT_NAME}'
ACCOMPANIMENT_MARKUP = (
    f'<p class="menu-accompaniment">{ACCOMPANIMENT_TEXT}</p>'
)

SNAPSHOT_ROUTES = (
    pytest.param('/cafeteria/heute/', 'staff_guest', 2, id='public-cafeteria-today'),
    pytest.param('/cafeteria/wochenangebot/', 'staff_guest', 10, id='public-cafeteria-week'),
    pytest.param('/druck/cafeteria/woche', 'staff_guest', 10, id='print-cafeteria-week'),
    pytest.param('/patienten/heute/', 'patient', 4, id='public-patient-today'),
    pytest.param('/patienten/wochenplan/', 'patient', 28, id='public-patient-week'),
    pytest.param('/druck/patienten/woche', 'patient', 28, id='print-patient-week'),
    pytest.param('/signage/cafeteria/tag', 'staff_guest', 2, id='signage-cafeteria-day'),
    pytest.param('/signage/cafeteria/woche', 'staff_guest', 10, id='signage-cafeteria-week'),
    pytest.param('/signage/patienten/tag', 'patient', 4, id='signage-patient-day'),
    pytest.param('/signage/patienten/woche', 'patient', 28, id='signage-patient-week'),
)

SIGNAGE_ROUTES = (
    pytest.param('/signage/cafeteria/tag', 'staff_guest', '.hero-food', id='cafeteria-day'),
    pytest.param('/signage/cafeteria/woche', 'staff_guest', '.cafe-week-slot', id='cafeteria-week'),
    pytest.param('/signage/patienten/tag', 'patient', '.patient-signage-option', id='patient-day'),
    pytest.param('/signage/patienten/woche', 'patient', '.patient-week-option', id='patient-week'),
)


def _set_accompaniment(snapshot: dict[str, object]) -> None:
    for day in snapshot['days']:
        for service in day['services']:
            for option in service['options']:
                option['accompaniment_code'] = 'salad'
                option['accompaniment_name'] = ACCOMPANIMENT_NAME


def _assert_only_accompaniment_changed(before: str, after: str, count: int) -> None:
    assert after.count(ACCOMPANIMENT_MARKUP) == count
    assert after.replace(ACCOMPANIMENT_MARKUP, '') == before
    metadata_blocks = re.findall(r'<div data-menu-metadata>(.*?)</div>', after, re.S)
    selected_blocks = [block for block in metadata_blocks if ACCOMPANIMENT_MARKUP in block]
    assert len(selected_blocks) == count
    for block in selected_blocks:
        labels = re.search(r'<div class="(?:labels|signage-tags)', block)
        assert labels is not None
        assert block.index(ACCOMPANIMENT_MARKUP) < labels.start()


@pytest.fixture
def admin_app(database_engine: Engine, tmp_path: Path) -> Flask:  # noqa: F811
    application = Flask(
        __name__,
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
    )
    application.config.update(
        SECRET_KEY='accompaniment-public-tests',
        LAST_GOOD_DIR=str(tmp_path),
        DEMO_MODE=True,
        DEMO_TODAY='2026-09-02',
    )
    application.extensions['cafeteria_db'] = database_engine
    application.extensions['cafeteria_auth_issuer_db'] = database_engine
    return _register(application)


@pytest.mark.parametrize(('path', 'profile', 'count'), SNAPSHOT_ROUTES)
def test_snapshot_routes_add_only_the_selected_accompaniment_line(
    app: Flask,
    path: str,
    profile: str,
    count: int,
) -> None:
    client = app.test_client()
    baseline = client.get(path)
    assert baseline.status_code == 200
    baseline_body = baseline.get_data(as_text=True)
    assert 'menu-accompaniment' not in baseline_body
    assert 'Dazu:' not in baseline_body

    _set_accompaniment(app.config['TEST_SNAPSHOTS'][profile])
    selected = client.get(path)
    assert selected.status_code == 200
    selected_body = selected.get_data(as_text=True)
    _assert_only_accompaniment_changed(baseline_body, selected_body, count)
    if profile == 'patient':
        assert 'CHF' not in selected_body


def test_admin_preview_adds_only_the_selected_accompaniment_line(
    admin_app: Flask,
    database_engine: Engine,
) -> None:
    client, actor_id = _login(admin_app, database_engine, ['Cafeteria.Admin'])
    scope = _scope(database_engine, actor_id)
    payload = _payload()
    version = persist_menu_item(
        database_engine,
        scope,
        WEEK,
        DAY,
        'LUNCH',
        'MENU_1',
        payload,
        0,
    )
    baseline = client.get(f'/admin/patienten/preview?week={DAY}')
    assert baseline.status_code == 200
    baseline_body = baseline.get_data(as_text=True)
    assert 'menu-accompaniment' not in baseline_body

    selected_payload = deepcopy(payload)
    selected_payload['accompaniment_code'] = 'salad'
    persist_menu_item(
        database_engine,
        scope,
        WEEK,
        DAY,
        'LUNCH',
        'MENU_1',
        selected_payload,
        version,
    )
    selected = client.get(f'/admin/patienten/preview?week={DAY}')
    assert selected.status_code == 200
    _assert_only_accompaniment_changed(
        baseline_body,
        selected.get_data(as_text=True),
        1,
    )


def test_menu_collection_partial_renders_the_name_supplied_by_its_reader(
    admin_app: Flask,
    database_engine: Engine,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _login(admin_app, database_engine, ['Cafeteria.Admin'])
    row = {
        'id': 1,
        'title': 'Gespeichertes Menü',
        'description': '',
        'note': '',
        'allergen_review_status': 'checked',
        'week_start': WEEK,
        'workflow_state': 'draft',
        'service_date': date.fromisoformat(DAY),
        'meal_code': 'LUNCH',
        'type_code': 'MENU_1',
        'stale_components': False,
        'review_open': False,
        'components': ['Kartoffelstock'],
        'labels': [],
        'allergens': [],
        'origins': [],
    }
    rows = [row]
    monkeypatch.setattr(
        menu_collection_routes,
        'find_menus',
        lambda *_args, **_kwargs: (rows, False),
    )
    monkeypatch.setattr(
        menu_collection_routes,
        'review_open',
        lambda *_args, **_kwargs: False,
    )
    baseline = client.get('/admin/patienten/menues')
    assert baseline.status_code == 200
    baseline_body = baseline.get_data(as_text=True)
    assert 'menu-accompaniment' not in baseline_body

    rows[0] = {**row, 'accompaniment_name': ACCOMPANIMENT_NAME}
    selected = client.get('/admin/patienten/menues')
    assert selected.status_code == 200
    _assert_only_accompaniment_changed(
        baseline_body,
        selected.get_data(as_text=True),
        1,
    )


@pytest.mark.parametrize(('path', 'profile', 'selector'), SIGNAGE_ROUTES)
@pytest.mark.parametrize(('width', 'height'), ((1920, 1080), (3840, 2160)))
def test_longest_accompaniment_fits_every_signage_surface(
    http_app: Flask,
    public_server: str,
    browser: Browser,
    tmp_path,
    path: str,
    profile: str,
    selector: str,
    width: int,
    height: int,
) -> None:
    assert len(ACCOMPANIMENT_TEXT) <= 32
    _set_accompaniment(http_app.config['TEST_SNAPSHOTS'][profile])
    with browser.new_context(
        viewport={'width': width, 'height': height},
        reduced_motion='reduce',
    ) as context:
        page = context.new_page()
        page.clock.install()
        response = page.goto(public_server + path, wait_until='load')
        assert response is not None and response.status == 200
        page.evaluate('document.fonts.ready')
        page_count = max(1, page.locator('[data-signage-page]').count())
        for page_index in range(page_count):
            cards = page.locator(f'{selector}:visible')
            lines = cards.locator('.menu-accompaniment')
            expect(lines).to_have_count(cards.count())
            expect(lines).to_have_text([ACCOMPANIMENT_TEXT] * lines.count())
            assert page.evaluate(
                'document.documentElement.scrollWidth <= innerWidth + 1 && '
                'document.documentElement.scrollHeight <= innerHeight + 1'
            )
            assert not any(row['clipped'] for row in card_geometry(page, f'{selector}:visible'))
            assert lines.evaluate_all(
                'nodes => nodes.every(node => '
                'node.scrollWidth <= node.clientWidth + 1 && '
                'node.scrollHeight <= node.clientHeight + 1)'
            )
            page.screenshot(
                path=str(
                    tmp_path
                    / f'{profile}-{path.rsplit("/", 1)[-1]}-{width}-{page_index}.png'
                )
            )
            if page_index + 1 < page_count:
                page.clock.fast_forward(30_010)
                expect(page.locator('[data-signage-page]').nth(page_index + 1)).to_be_visible()
        if profile == 'patient':
            assert 'CHF' not in page.locator('body').inner_text()
