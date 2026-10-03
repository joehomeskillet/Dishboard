"""DELTA-3-09: recipe editor evidence on synthetic PostgreSQL data."""
from pathlib import Path
import json

import pytest
from playwright.sync_api import expect

from cafeteria import recipe_store
from test_master_data_db import signed_in
from test_master_data_browser import master_server  # noqa: F401
from test_recipe_density_browser import reference
from test_recipe_routes import app_engine, b3, fields, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_recipe_store_db import payload, snapshot
from test_rendered_ui import browser  # noqa: F401


EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/state/delta3-l2final-1002/DELTA-3-09'


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('touch', [False, True])
def test_editor_static_sections(b3, master_server, browser, width, touch):  # noqa: F811
    path = reference(b3[2])
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             has_touch=touch, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + path).status == 200
        page.evaluate('document.fonts.ready')
        expect(page.locator('main details, main summary, [data-recipe-toggle]')).to_have_count(0)
        expect(page.get_by_label('Zutatennotiz', exact=True).first).to_be_visible()
        expect(page.locator('[name="steps.0.instruction"]')).to_be_visible()
        expect(page.locator('[name="steps.1.duration_minutes"]')).to_have_value('0')
        expect(page.get_by_label('Quellenbeleg', exact=True)).to_be_visible()
        expect(page.locator('[data-recipe-step-summary], [data-recipe-step-extra]')).to_have_count(0)
        expect(page.locator('.recipe-editor-toolbar [data-semantic="actions.back"]')).to_have_count(1)
        expect(page.locator('.admin-form-footer a')).to_have_count(0)
        # Check actual paint, including pseudo-content, not just SVG/text DOM counts.
        modes = page.locator('main .ui-sem-control').evaluate_all('''elements => elements.map(el => {
            const visible = node => {const s = getComputedStyle(node); const b = node.getBoundingClientRect();
                return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 1 && b.height > 1;};
            return {name: el.getAttribute('aria-label'), mode: el.dataset.uiMode,
                text: el.innerText.trim(), icons: [...el.querySelectorAll('svg')].filter(visible).length,
                pseudo: ['::before', '::after'].map(p => getComputedStyle(el, p).content)};
        })''')
        for control in modes:
            assert control['name']
            assert control['pseudo'] == ['none', 'none'], control
            assert (bool(control['text']), control['icons']) in ((True, 0), (False, 1)), control
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f'after-{width}-touch{touch}.png'), full_page=True)
        (EVIDENCE / f'buttons-{width}-touch{touch}.json').write_text(json.dumps(modes, indent=2))


def test_ai_warning_follows_section_navigation(b3, master_server, browser):  # noqa: F811
    app, owner, _, actor = b3
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        row = recipe_store.create_recipe(engine, actor, payload(source={
            'kind': 'ai_assisted', 'reference': 'Prüfbeleg', 'url': None,
            'note': 'Ungeprüfte Vorlage', 'fetched_at': '2026-10-01T10:00:00+02:00',
        }), expected_location_id=recipe_store.get_location(engine))
    before = snapshot(owner)
    base, cookie = master_server
    with browser.new_context(viewport={'width': 390, 'height': 844}, has_touch=True) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(f'{base}/admin/rezepte/{row.public_id}').status == 200
        nav = page.get_by_role('navigation', name='Rezeptabschnitte', exact=True)
        warning = page.locator('main [role="status"]').filter(has_text='KI-unterstützte Vorlage')
        expect(warning).to_be_visible()
        assert warning.bounding_box()['y'] >= nav.bounding_box()['y'] + nav.bounding_box()['height']
        expect(page.get_by_label('Quellenbeleg', exact=True)).to_have_value('Prüfbeleg')
    assert snapshot(owner) == before


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('touch', [False, True])
def test_conflict_copy_hint_is_static(b3, master_server, browser, width, touch):  # noqa: F811
    _, owner, client, _ = b3
    path = reference(client)
    base, cookie = master_server
    with browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             has_touch=touch, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        assert page.goto(base + path).status == 200
        fresh = fields(client, path)
        fresh['title'] = 'Parallele Änderung'
        assert client.post(path, data=fresh).status_code == 303
        before = snapshot(owner)
        page.get_by_label('Titel', exact=True).fill('Mein ungespeicherter Entwurf')
        with page.expect_response(lambda response: response.request.method == 'POST') as saved:
            page.get_by_role('button', name='Speichern', exact=True).click()
        assert saved.value.status == 409
        expect(page.locator('main details, main summary')).to_have_count(0)
        expect(page.locator('#copy-hint')).to_be_visible()
        original = page.get_by_label('Titel', exact=True)
        expect(original).to_have_value('Mein ungespeicherter Entwurf')
        expect(original).to_have_attribute('readonly', '')
        original.focus()
        page.keyboard.press('Escape')
        expect(original).to_be_focused()
        expect(page.locator('main .btn')).to_have_text('Aktuellen Stand bewusst neu laden')
        expect(page.locator('main .btn svg')).to_have_count(0)
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f'after-conflict-{width}-touch{touch}.png'), full_page=True)
    assert snapshot(owner) == before
