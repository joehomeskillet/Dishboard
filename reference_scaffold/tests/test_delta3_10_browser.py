"""DELTA-3-10 recipe document and revision evidence."""
from pathlib import Path
import json

import pytest
from playwright.sync_api import expect

from test_recipe_template_editor_browser import recipe_server  # noqa: F401
from test_recipe_template_editor_routes import (  # noqa: F401
    recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine, example, state,
)
from test_print_template_browser import browser  # noqa: F401

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/state/delta3-l2final-1002/DELTA-3-10'


@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('touch', [False, True])
def test_recipe_document_sections(recipe_editor, recipe_server, browser, width, touch):  # noqa: F811
    app, owner, client, _ = recipe_editor
    recipe, revision, _ = example(recipe_editor)
    before = state(owner)
    cookie = client.get_cookie(app.config['SESSION_COOKIE_NAME'])
    with browser.new_context(viewport={'width': width, 'height': 900 if width == 1440 else 844},
                             has_touch=touch, reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': recipe_server}])
        page = context.new_page()
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        for label, suffix in [('view', 'ansicht'), ('history', 'revisionen'),
                              ('revision', 'revisionen/' + revision.public_id)]:
            assert page.goto(f'{recipe_server}/admin/rezepte/{recipe}/{suffix}').status == 200
            page.evaluate('document.fonts.ready')
            expect(page.locator('main details, main summary')).to_have_count(0)
            if label == 'history':
                expect(page.locator('#history-hint')).to_be_visible()
                proof = page.locator('#recipe-dependency-proof code').inner_text()
                assert len(proof) == 64 and all(char in '0123456789abcdef' for char in proof)
                expect(page.locator('#recipe-history code')).to_have_count(0)
                actions = page.locator('#recipe-history tr').filter(has_text=f'Gespeicherter Stand {revision.revision_number}')
                expect(actions.get_by_role('link', name=f'Gespeicherten Stand {revision.revision_number} ansehen', exact=True)).to_have_attribute(
                    'href', f'/admin/rezepte/{recipe}/revisionen/{revision.public_id}')
                expect(actions.get_by_role('link', name=f'PDF von Stand {revision.revision_number} öffnen', exact=True)).to_have_attribute(
                    'href', f'/admin/rezepte/{recipe}/revisionen/{revision.public_id}/druck.pdf')
            else:
                expect(page.locator('.recipe-originals > h2').first).to_have_text('Originalmengen')
                expect(page.locator('.recipe-provenance > h2').first).to_have_text('Herkunft')
                for section in page.locator('.recipe-originals, .recipe-provenance').all():
                    expect(section).to_be_visible()
                    assert section.inner_text().strip()
                if label == 'revision':
                    expect(page.locator('#recipe-technical-heading')).to_be_visible()
                    expect(page.get_by_text(revision.content_hash_sha256, exact=True).first).to_be_visible()
                    expect(page.get_by_role('heading', name='Vollständige Daten', exact=True)).to_be_visible()
            modes = page.locator('main .ui-sem-control').evaluate_all("""elements => elements.map(el => ({
                name: el.getAttribute('aria-label'), text: el.innerText.trim(),
                icons: [...el.querySelectorAll('svg')].filter(node => {
                    const s = getComputedStyle(node), b = node.getBoundingClientRect();
                    return s.display !== 'none' && s.visibility !== 'hidden' && b.width > 1 && b.height > 1;
                }).length,
                pseudo: ['::before', '::after'].map(p => getComputedStyle(el, p).content)
            }))""")
            for control in modes:
                assert control['name']
                assert control['pseudo'] == ['none', 'none'], control
                assert (bool(control['text']), control['icons']) in ((True, 0), (False, 1)), control
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(EVIDENCE / f'after-{label}-{width}-touch{touch}.png'), full_page=True)
            (EVIDENCE / f'buttons-{label}-{width}-touch{touch}.json').write_text(json.dumps(modes, indent=2))
            if label == 'history':
                open_revision = page.get_by_role('link', name=f'Gespeicherten Stand {revision.revision_number} ansehen', exact=True)
                open_revision.focus()
                page.keyboard.press('Enter')
                expect(page).to_have_url(f'{recipe_server}/admin/rezepte/{recipe}/revisionen/{revision.public_id}')
                expect(page.locator('#recipe-technical-heading')).to_be_visible()
                expect(page.get_by_text(revision.content_hash_sha256, exact=True).first).to_be_visible()
        assert not posts
    assert state(owner) == before
