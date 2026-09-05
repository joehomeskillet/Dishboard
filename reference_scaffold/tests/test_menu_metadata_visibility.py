from __future__ import annotations

from copy import deepcopy

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine

from cafeteria.workflow_partial_store import persist_menu_item
from test_admin_workflow_routes import DATABASE_URL, DAY, WEEK, _hidden, _login, _payload, _scope
from test_rendered_ui import (  # noqa: F401
    PATIENT_FORBIDDEN,
    _page,
    admin_app,
    admin_engine,
    app,
    browser,
)

DESCRIPTION = 'Mit Kräutern & Gemüse'
NOTE = 'Ausgabe ab 11:30 Uhr'
MISSING = 'Allergenangaben nicht erfasst'


def _assert_metadata(page: Page, *, filled: bool) -> None:
    metadata = page.locator('[data-menu-metadata]')
    assert metadata.count() >= 2
    first, second = metadata.nth(0), metadata.nth(1)
    if filled:
        expect(first).to_contain_text(DESCRIPTION)
        expect(first).to_contain_text(NOTE)
        assert sorted(first.locator('.label').all_text_contents()) == sorted([
            'Kartoffel: CH', 'Vegetarisch', 'Enthält: Milch', 'Kann enthalten: Sellerie',
        ])
        expect(first).not_to_contain_text(MISSING)
    else:
        expect(first).to_contain_text(MISSING)
        assert first.locator('.label').count() == 0
        assert first.locator('.menu-description, .shared-note').count() == 0
    expect(second).to_contain_text(MISSING)
    assert second.locator('.label').count() == 0
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert metadata.evaluate_all(
        'els => els.every(el => el.scrollWidth <= el.clientWidth + 1)'
    )


@pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_saved_metadata_reaches_overview_preview_editor_and_error_response(
    admin_app: Flask, admin_engine: Engine, browser: Browser,  # noqa: F811
    family: str, profile: str,
) -> None:
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    payload = _payload(staff=profile == 'staff_guest')
    payload.update(
        description=DESCRIPTION, note=NOTE,
        labels=['VEGETARIAN'],
        allergens=[
            {'code': 'MILK', 'presence': 'contains'},
            {'code': 'CELERY', 'presence': 'may_contain'},
        ],
    )
    engine = admin_app.extensions['cafeteria_db']
    scope = _scope(admin_engine, user_id, profile)
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', payload, 0)
    partial = client.get(f'/admin/{family}/preview?week={DAY}')
    assert partial.status_code == 200
    partial_body = partial.get_data(as_text=True)
    assert partial_body.count('class="preview-option"') == 1
    assert partial_body.count('data-menu-metadata') == 1
    assert MISSING not in partial_body
    empty = _payload(staff=profile == 'staff_guest')
    empty.update(title='Milchreis', origins=[])
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'VEGGIE', empty, 0)

    for path in (f'/admin/{family}?week={DAY}', f'/admin/{family}/preview?week={DAY}'):
        response = client.get(path)
        assert response.status_code == 200
        body = response.get_data(as_text=True)
        assert 'Mit Kräutern &amp; Gemüse' in body
        assert body.count('data-menu-metadata') == 2  # No phantom virtual-slot declarations.
        if profile == 'patient':
            assert PATIENT_FORBIDDEN.search(body) is None
        for width in (390, 1440):
            page = _page(browser, body, width, 1100)
            try:
                _assert_metadata(page, filled=True)
                expect(page.locator('[data-menu-metadata]').first).to_contain_text(
                    'Allergenprüfung offen'
                )
            finally:
                page.close()

    editor = client.get(
        f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
    )
    assert editor.status_code == 200
    editor_body = editor.get_data(as_text=True)
    invalid = client.post(f'/admin/{family}/menu', data={
        '_csrf': _hidden(editor_body, '_csrf', form_action=f'/admin/{family}/menu'),
        'week': DAY, 'day': DAY, 'meal': 'LUNCH', 'option': 'MENU_1', 'row_version': '1',
        'title': '', 'allergen_mode': 'manual', 'origin_mode': 'manual', 'label_mode': 'manual',
    })
    assert invalid.status_code == 400
    for body in (editor_body, invalid.get_data(as_text=True)):
        review = body.split('<div class="review-block">', 1)[1]
        assert 'Enthält: Milch' in review
        assert 'Kann enthalten: Sellerie' in review
        assert 'Enthält: Sellerie' not in review
        assert MISSING not in review
        assert 'Zuletzt gespeicherter Stand' in review
    empty_editor = client.get(
        f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=VEGGIE'
    )
    assert empty_editor.status_code == 200
    assert MISSING in empty_editor.get_data(as_text=True)


@pytest.mark.parametrize('profile,path', [
    ('staff_guest', '/cafeteria/heute/'),
    ('staff_guest', '/cafeteria/wochenangebot/'),
    ('patient', '/patienten/heute/'),
    ('patient', '/patienten/wochenplan/'),
])
@pytest.mark.parametrize('filled', [False, True])
def test_public_day_and_week_show_only_published_metadata_and_honest_empty_status(
    app: Flask, browser: Browser, profile: str, path: str, filled: bool,  # noqa: F811
) -> None:
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    for day in snapshot['days']:
        for service in day['services']:
            for option in service['options']:
                option.update(
                    description='', note='', allergens=[], labels=[], origins=[],
                    allergen_review_status='checked', title='Milchreis',
                )
    today = snapshot['days'][0]
    app.config['DEMO_TODAY'] = today['date']
    if filled:
        today['services'][0]['options'][0].update(
            description=DESCRIPTION, note=NOTE,
            labels=[{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
            allergens=[
                {'code': 'MILK', 'name': 'Milch', 'presence': 'contains'},
                {'code': 'CELERY', 'name': 'Sellerie', 'presence': 'may_contain'},
            ],
            origins=[{'ingredient': 'Kartoffel', 'country_code': 'CH', 'text': 'Kartoffel: CH'}],
        )
    original = deepcopy(snapshot)
    response = app.test_client().get(path)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    if profile == 'patient':
        assert PATIENT_FORBIDDEN.search(body) is None
    for width in (390, 1440):
        page = _page(browser, body, width, 1100)
        try:
            _assert_metadata(page, filled=filled)
            assert page.get_by_text('Allergenprüfung offen', exact=True).count() == 0
        finally:
            page.close()
    assert snapshot == original
