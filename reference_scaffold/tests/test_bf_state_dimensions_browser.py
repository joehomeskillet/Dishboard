"""BF-T02/T03: persisted state, review, publication and local edits stay distinct."""
from __future__ import annotations

import re
from collections.abc import Iterator

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine, text

from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _counts, _login
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

FAMILIES = (('cafeteria', 'staff_guest'), ('patienten', 'patient'))


@pytest.fixture(params=(True, False), ids=('js', 'no-js'))
def javascript_enabled(request) -> bool:
    return request.param


@pytest.fixture
def bf_page(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    javascript_enabled: bool,
) -> Iterator[Page]:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    context = browser.new_context(
        base_url=live_server, java_script_enabled=javascript_enabled,
        viewport={'width': 1440, 'height': 900}, reduced_motion='reduce',
    )
    context.add_cookies([{
        'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True,
    }])
    try:
        yield context.new_page()
    finally:
        context.close()


def _editor(family: str) -> str:
    return f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


def _unreviewed_week(engine: Engine, profile: str) -> None:
    values = (_staff_values if profile == 'staff_guest' else _patient_values)(
        'Herbstwoche',
    )
    for day in values['days']:
        for service in day['services']:
            for option in service['options']:
                option['allergen_review_status'] = 'not_checked'
                option['allergens'] = [{'code': 'MILK', 'name': 'Milch', 'presence': 'contains'}]
    _save(engine, profile, values)


def _persisted_dimensions(engine: Engine) -> tuple:
    with engine.connect() as connection:
        week = connection.execute(text(
            'SELECT workflow_state,row_version FROM cafeteria.menu_weeks',
        )).one()
        reviews = set(connection.execute(text(
            'SELECT DISTINCT allergen_review_status FROM cafeteria.menu_items',
        )).scalars())
        publications = connection.execute(text(
            'SELECT count(*) FROM cafeteria.publication_revisions',
        )).scalar_one()
    return week.workflow_state, week.row_version, reviews, publications


@pytest.mark.parametrize('family,profile', FAMILIES)
def test_t02_saved_draft_does_not_claim_review_or_publication(
    bf_page: Page, admin_engine: Engine, family: str, profile: str,  # noqa: F811
) -> None:
    """Saving alone leaves review and publication open in all four rendered views."""
    _unreviewed_week(admin_engine, profile)
    before = _persisted_dimensions(admin_engine)
    assert before[0] == 'draft' and before[1] > 0
    assert before[2:] == ({'not_checked'}, 0)
    page = bf_page
    response = page.goto(f'/admin/{family}?week={DAY}')
    assert response is not None and response.status == 200
    expect(page.locator('.page-header-subtitle')).to_contain_text('Prüfung offen')
    expect(page.locator('#week-check-summary')).to_contain_text('offener Kartenprüfung')
    card = page.locator(f'#week-slot-{DAY}-LUNCH-MENU_1')
    expect(card).to_have_attribute('data-row-version', re.compile(r'[1-9]\d*'))
    expect(card.locator('[data-allergen-state]')).to_have_text('Allergenprüfung offen')
    expect(page.locator('[data-bs-target="#week-publish-modal"]').first).to_be_disabled()

    page.goto(f'/admin/{family}/preview?week={DAY}')
    expect(page.locator('[data-preview]')).to_have_attribute('data-workflow-state', 'draft')
    expect(page.locator('.preview-saved')).to_contain_text('Nicht veröffentlicht · Entwurf')
    expect(page.locator('.preview-notice')).to_contain_text('gespeicherte Woche')
    expect(page.locator('main').get_by_text('Geprüft', exact=True)).to_have_count(0)

    page.goto(f'/admin/{family}/wochen/pruefung?week={DAY}')
    expect(page.locator('.alert-warning')).to_contain_text('Noch zu prüfen')
    expect(page.locator('.alert-warning')).to_contain_text('keine gültige Prüfung')
    expect(page.locator('[data-week-review-intro]')).to_contain_text(
        'Eine Bestätigung veröffentlicht noch keinen Wochenplan',
    )
    expect(page.locator('.alert-success')).to_have_count(0)
    assert _persisted_dimensions(admin_engine) == before


@pytest.mark.parametrize('family,profile', FAMILIES)
def test_t03_empty_editor_and_reset_observation(
    bf_page: Page, admin_engine: Engine, family: str, profile: str,  # noqa: F811
    javascript_enabled: bool, record_property,
) -> None:
    """Record reset's current behavior without treating its stale guard as the target."""
    page = bf_page
    page.goto(_editor(family))
    name = page.get_by_label('Menüname', exact=True)
    expect(name).to_have_value('')
    dirty_note = page.locator('[data-menu-editor-dirty-note]')
    # The neutral explanation is always visible; only is-dirty marks local edits.
    expect(dirty_note).not_to_have_class(re.compile(r'\bis-dirty\b'))
    expect(page.get_by_text('Nicht gespeichert', exact=True)).to_have_count(0)
    before = _counts(admin_engine)
    assert before == (0, 0, 0)
    name.fill('Lokaler Entwurf')
    expect(name).to_have_value('Lokaler Entwurf')
    if javascript_enabled:
        expect(dirty_note).to_have_class(re.compile(r'\bis-dirty\b'))
    else:
        expect(dirty_note).not_to_have_class(re.compile(r'\bis-dirty\b'))
    record_property('after_input_warning', dirty_note.inner_text() if dirty_note.is_visible() else '')
    name.fill('')
    expect(name).to_have_value('')
    record_property('after_reset_dirty', 'is-dirty' in (dirty_note.get_attribute('class') or '').split())
    dialogs = []

    def dismiss(dialog) -> None:
        dialogs.append(dialog.type)
        dialog.dismiss()

    page.on('dialog', dismiss)
    page.locator('[data-semantic="navigation.weekplan"]').click()
    record_property('after_reset_dialogs', ','.join(dialogs))
    if dialogs:
        expect(name).to_have_value('')
    else:
        expect(page).to_have_url(re.compile(rf'/admin/{family}\?week={DAY}$'))
    assert _counts(admin_engine) == before


# BF-Lücke: reference_scaffold/cafeteria/templates/admin/_week_controls.html:16
# BF-Lücke: reference_scaffold/cafeteria/templates/admin/week_review.html:26
@pytest.mark.parametrize('family,profile', FAMILIES)
@pytest.mark.parametrize('view', ('week-header', 'card-with-week-context', 'preview', 'week-review'))
def test_t02_each_view_distinguishes_saved_review_and_publication(
    bf_page: Page, admin_engine: Engine, family: str, profile: str, view: str,  # noqa: F811
) -> None:
    _unreviewed_week(admin_engine, profile)
    before = _persisted_dimensions(admin_engine)
    assert before[0] == 'draft' and before[2:] == ({'not_checked'}, 0)
    page = bf_page
    if view in ('week-header', 'card-with-week-context'):
        page.goto(f'/admin/{family}?week={DAY}')
        visible = page.locator('.page-header').inner_text()
        if view == 'card-with-week-context':
            # Shared week context may explain persistence/publication; no duplicate badges required.
            visible += page.locator(f'#week-slot-{DAY}-LUNCH-MENU_1').inner_text()
    elif view == 'preview':
        page.goto(f'/admin/{family}/preview?week={DAY}')
        visible = page.locator('main').inner_text()
    else:
        page.goto(f'/admin/{family}/wochen/pruefung?week={DAY}')
        visible = page.locator('main').inner_text()
    patterns = {
        'gespeichert': r'gespeichert|Entwurf',
        'ungeprüft': r'Prüfung offen|Prüfungen offen|Noch zu prüfen|ungeprüft|keine gültige Prüfung',
        'unveröffentlicht': r'nicht veröffentlicht|unveröffentlicht',
    }
    missing = [dimension for dimension, pattern in patterns.items()
               if not re.search(pattern, visible, re.IGNORECASE)]
    assert _persisted_dimensions(admin_engine) == before
    assert not missing, f'{view}: fehlende Dimensionen {missing}; sichtbarer Text: {visible}'


# BF-Lücke: reference_scaffold/cafeteria/templates/admin/cafeteria.html:77
# BF-Lücke: reference_scaffold/cafeteria/templates/admin/_week_service.html:38
@pytest.mark.parametrize('family,profile', FAMILIES)
def test_t03_empty_week_has_no_unsaved_warning(
    bf_page: Page, admin_engine: Engine, family: str, profile: str,  # noqa: F811
) -> None:
    page = bf_page
    page.goto(f'/admin/{family}?week={DAY}')
    assert _counts(admin_engine) == (0, 0, 0)
    expect(page.locator(f'#week-slot-{DAY}-LUNCH-MENU_1')).to_have_attribute('data-row-version', '0')
    warnings = page.locator('main').get_by_text('Nicht gespeichert', exact=True)
    assert warnings.count() == 0, f'Leere Woche ohne Eingabe: {warnings.count()} Warnungen Nicht gespeichert'


# BF-Lücke: reference_scaffold/cafeteria/templates/admin/menu_editor.html:399
# BF-Lücke: reference_scaffold/cafeteria/static/admin.js:293
@pytest.mark.parametrize('family,profile', FAMILIES)
@pytest.mark.parametrize('javascript_enabled', (True,), ids=('js',))
def test_t03_actual_input_has_exact_unsaved_wording(
    bf_page: Page, admin_engine: Engine, family: str, profile: str,  # noqa: F811
) -> None:
    page = bf_page
    page.goto(_editor(family))
    expect(page.get_by_text('Nicht gespeichert', exact=True)).to_have_count(0)
    page.get_by_label('Menüname', exact=True).fill('Tatsächliche lokale Eingabe')
    expect(page.locator('[data-menu-editor-dirty-note]')).to_have_class(re.compile(r'\bis-dirty\b'))
    assert _counts(admin_engine) == (0, 0, 0)
    expect(page.get_by_text('Nicht gespeichert', exact=True)).to_be_visible()
