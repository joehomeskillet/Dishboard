"""DELTA-3-11 recipe list, images, import and scaling evidence."""
from pathlib import Path
import json
from decimal import Decimal
from dataclasses import replace

import pytest
from playwright.sync_api import expect

from cafeteria import recipe_store, recipe_import_store
from test_master_data_db import signed_in
from test_recipe_store_db import payload, line

from test_recipe_import_routes import create, snapshot
from test_recipe_template_editor_browser import recipe_server  # noqa: F401
from test_recipe_template_editor_routes import (  # noqa: F401
    recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine, example,
)
from test_print_template_browser import browser  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/state/delta3-l2final-1002/DELTA-3-11'


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('touch', [False, True])
def test_recipe_support_sections(recipe_editor, recipe_server, browser, width, touch):  # noqa: F811
    app, owner, client, _ = recipe_editor
    recipe, _, _ = example(recipe_editor)
    batch = create(client)
    before = snapshot(owner)
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             has_touch=touch, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': recipe_server}])
        page = context.new_page()
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        for label, route in [('list', '/admin/rezepte'), ('images', f'/admin/rezepte/{recipe}/bilder'),
                             ('import', batch), ('scale', f'/admin/rezepte/{recipe}/skalierung')]:
            assert page.goto(recipe_server + route).status == 200
            page.evaluate('document.fonts.ready')
            expect(page.locator('main details, main summary')).to_have_count(0)
            if label == 'images':
                expect(page.get_by_role('heading', name='Quelle (optional)', exact=True)).to_be_visible()
                for name in ('source_url', 'source_license', 'fetched_at'):
                    expect(page.locator(f'[name="{name}"]')).to_be_visible()
                expect(page.locator('#image-format-hint')).to_be_visible()
            elif label == 'import':
                expect(page.locator('#import-file-hint')).to_be_visible()
                expect(page.locator('#import-technical')).to_be_visible()
                for field in page.locator('[data-import-row] input:not([type="hidden"])').all():
                    expect(field).to_be_visible()
                expect(page.locator('[data-import-discard] button')).to_have_text('Verwerfen')
                expect(page.locator('[data-import-discard] button svg')).to_have_count(0)
                assert page.locator('[data-import-discard] button').get_attribute('data-confirm')
            elif label == 'scale':
                expect(page.locator('#yield-hint')).to_be_visible()
            modes = page.locator('main .ui-sem-control').evaluate_all("""elements => elements.filter(el => el.getClientRects().length && getComputedStyle(el).visibility !== 'hidden').map(el => ({
                name: el.getAttribute('aria-label'), text: el.innerText.trim(),
                box: (() => { const b = el.getBoundingClientRect(); return [b.width, b.height]; })(),
                icons: [...el.querySelectorAll('svg')].filter(node => {
                    const s = getComputedStyle(node), b = node.getBoundingClientRect();
                    return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 1 && b.height > 1;
                }).length,
                pseudo: ['::before', '::after'].map(p => getComputedStyle(el, p).content)
            }))""")
            pointer = page.evaluate("({coarse:matchMedia('(any-pointer: coarse)').matches, fine:matchMedia('(pointer: fine)').matches, width:innerWidth, height:innerHeight})")
            assert pointer['coarse'] is touch
            for control in modes:
                assert control['name']
                assert min(control['box']) >= (44 if touch else 36), control
                assert control['pseudo'] == ['none', 'none'], control
                assert (bool(control['text']), control['icons']) in ((True, 0), (False, 1)), control
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            page.evaluate('window.scrollTo(0, 0)')
            page.screenshot(path=str(EVIDENCE / f'after-{label}-{width}-touch{touch}.png'), full_page=False)
            (EVIDENCE / f'buttons-{label}-{width}-touch{touch}.json').write_text(json.dumps({'buttons': modes, 'pointer': pointer}, indent=2))
        assert not posts
    assert snapshot(owner) == before


@pytest.mark.parametrize('width', [1440, 390])
def test_import_result_omits_only_empty_actions(recipe_editor, recipe_server, browser, monkeypatch, width):  # noqa: F811
    """P-16/P-07: nullable result links use the real consumer and shared renderer."""
    app, owner, client, _ = recipe_editor
    recipe, _, _ = example(recipe_editor)
    route = create(client)
    before = snapshot(owner)
    read_batch = recipe_import_store.get_batch

    def result_links(*args, **kwargs):
        batch = read_batch(*args, **kwargs)
        if batch.public_id != route.rsplit('/', 1)[-1]:
            return batch
        return replace(batch, status='imported', imported_result=(
            {'row_number': 1, 'decision': 'skip', 'recipe_public_id': None},
            {'row_number': 2, 'decision': 'create_new', 'recipe_public_id': recipe},
        ))

    monkeypatch.setattr(recipe_import_store, 'get_batch', result_links)
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(viewport={'width': width, 'height': 900}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': recipe_server}])
        page = context.new_page()
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        assert page.goto(recipe_server + route).status == 200
        rows = page.locator('[aria-labelledby="recipe-import-links-title"] .admin-list-row')
        expect(rows).to_have_count(2)
        expect(rows.nth(0)).to_contain_text('Zeile 1')
        expect(rows.nth(0)).to_contain_text('skip')
        expect(rows.nth(0).locator('.admin-list-actions')).to_have_count(0)
        expect(rows.nth(1).locator('.admin-list-actions')).to_have_count(1)
        link = rows.nth(1).locator('[data-semantic="actions.edit"]')
        expect(link).to_have_attribute('href', f'/admin/rezepte/{recipe}')
        expect(link).to_be_visible()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        page.screenshot(path=str(EVIDENCE / f'import-result-{width}.png'), full_page=True)
        assert not posts
    assert snapshot(owner) == before



@pytest.mark.parametrize('width', [1440, 390])
def test_missing_unit_keeps_empty_cell_and_missing_quantity(recipe_editor, recipe_server, browser, width):  # noqa: F811
    app, owner, client, actor = recipe_editor
    engine = app.extensions['cafeteria_db']
    with signed_in(engine, actor):
        row = recipe_store.create_recipe(engine, actor, payload(ingredients=[
            line('Salz-ohne-Einheit', quantity=None, unit_code=None),
            line('Erfasste Menge', quantity='0.5', unit_code='G'),
        ]), expected_location_id=recipe_store.get_location(engine))
    before = snapshot(owner)
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(viewport={'width': width, 'height': 900}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': recipe_server}])
        page = context.new_page()
        assert page.goto(f'{recipe_server}/admin/rezepte/{row.public_id}/skalierung?yield=8').status == 200
        missing = page.locator('tbody tr').filter(has_text='Salz-ohne-Einheit')
        expect(missing.locator('td')).to_have_count(4)
        expect(missing.locator('[data-label="Einheit"]')).to_have_text('')
        expect(missing.locator('[data-label="Original"], [data-label="Berechnet"]')).to_have_text(
            ['Ohne Mengenangabe', 'Ohne Mengenangabe'])
        known = page.locator('tbody tr').filter(has_text='Erfasste Menge')
        expect(known.locator('[data-label="Original"]')).to_have_text('0.5')
        assert Decimal(known.locator('[data-label="Berechnet"]').inner_text()) == Decimal('1')
        expect(known.locator('[data-label="Einheit"]')).to_have_text('G')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert snapshot(owner) == before


@pytest.mark.parametrize('width', [1440, 390])
def test_empty_list_keeps_single_canonical_actions(recipe_editor, recipe_server, browser, width):  # noqa: F811
    app, owner, client, _ = recipe_editor
    before = snapshot(owner)
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(viewport={'width': width, 'height': 900}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': recipe_server}])
        page = context.new_page()
        assert page.goto(recipe_server + '/admin/rezepte').status == 200
        expect(page.locator('[data-empty-kind="none"]')).to_be_visible()
        expect(page.locator('main [data-semantic="actions.add"]')).to_have_count(1)
        expect(page.locator('[data-empty-kind] .ui-sem-control')).to_have_count(0)
        assert page.goto(recipe_server + '/admin/rezepte?text=DELTA-NICHTVORHANDEN').status == 200
        expect(page.locator('[data-empty-kind="no_match"]')).to_be_visible()
        reset = page.locator('main [data-semantic="view.reset"]')
        expect(reset).to_have_count(1)
        expect(reset).to_have_attribute('href', '/admin/rezepte')
        expect(page.locator('[data-empty-kind] .ui-sem-control')).to_have_count(0)
        reset.click()
        expect(page).to_have_url(recipe_server + '/admin/rezepte')
    assert snapshot(owner) == before


@pytest.mark.parametrize('width', [1440, 390])
def test_optional_import_metadata_rendering(recipe_editor, recipe_server, browser, monkeypatch, width):  # noqa: F811
    """Exercise nullable read-model fields; persisted batch and permissions stay real."""
    app, owner, client, _ = recipe_editor
    route = create(client)
    before = snapshot(owner)
    read_batch = recipe_import_store.get_batch

    def missing_metadata(*args, **kwargs):
        batch = read_batch(*args, **kwargs)
        if batch.public_id != route.rsplit('/', 1)[-1]:
            return batch
        candidates = tuple(replace(candidate, candidate_payload={
            **candidate.candidate_payload, 'source': None, 'ingredients': (),
        }) for candidate in batch.candidates)
        return replace(batch, source_sha256=None, candidates=candidates)

    monkeypatch.setattr(recipe_import_store, 'get_batch', missing_metadata)
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(viewport={'width': width, 'height': 900}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': recipe_server}])
        page = context.new_page()
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        assert page.goto(recipe_server + route).status == 200
        expect(page.locator('#import-technical')).to_contain_text('Dateihash Nicht erfasst')
        expect(page.locator('[data-import-row] .admin-compact-summary')).to_have_count(0)
        expect(page.locator('[data-import-row]')).not_to_contain_text('Quellennotiz:')
        assert '—' not in page.locator('#import-technical').inner_text()
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not posts
    assert snapshot(owner) == before
