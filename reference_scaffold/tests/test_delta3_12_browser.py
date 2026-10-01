"""DELTA-3-12 print editor evidence for all consumers of the shared template."""
from pathlib import Path
import json

import pytest
from playwright.sync_api import expect

from test_recipe_template_editor_routes import state

from test_icon_print_editor_calm_browser import (  # noqa: F401
    editor_case, _page, browser, editor_server, database_engine, editor_app,
    recipe_server, recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine,
)

EVIDENCE = Path('/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18/.claude/state/claude-session-2026-09-29/audit/DELTA/DELTA-3-12')


@pytest.mark.parametrize('editor_case', ['cafeteria', 'patienten', 'recipes'], indirect=True)
@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('touch', [False, True])
def test_print_editor_sections(editor_case, browser, tmp_path, width, touch):  # noqa: F811
    before = state(editor_case['owner'])
    with _page(browser, editor_case, tmp_path, width, 1, True, has_touch=touch) as page:
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        assert page.goto(editor_case['url']).status == 200
        page.evaluate('document.fonts.ready')
        # Shared filter_bar_sem remains a reported contract gap (D-45).
        expect(page.locator('main details:not(.admin-filter-more)')).to_have_count(0)
        for area in ('appearance', 'texts', 'activation', 'copy', 'lifecycle'):
            section = page.locator(f'[data-template-{area}]')
            expect(section).to_be_visible()
            expect(section.locator(':scope > summary')).to_have_count(0)
            expect(section.get_by_role('heading').first).to_be_visible()
        for label in ('Druckschrift', 'Zusatz unter dem Kopfbereich', 'Zusatz in der Fusszeile', 'Name der Kopie'):
            expect(page.get_by_label(label, exact=True)).to_be_visible()
        if editor_case['kind'] == 'recipes':
            choices = page.locator('[data-recipe-selection] .admin-list-row')
            expect(choices.first).to_be_visible()
            expect(choices.locator('.admin-list-status')).to_have_count(0)
            for choice in choices.all():
                expect(choice.locator('.admin-list-actions .ui-sem-control')).to_have_count(1)
        expect(page.locator('.admin-form-footer a')).to_have_count(0)
        expect(page.locator('.page-header [data-semantic="actions.back"]')).to_have_count(1)
        selection = page.locator('#template-select').locator('xpath=ancestor::form')
        navigation_box = selection.bounding_box()
        status_box = page.locator('[data-template-status-scope]').bounding_box()
        assert navigation_box and status_box
        assert navigation_box['y'] + navigation_box['height'] <= status_box['y'] + 1
        forms = page.locator('main form')
        form_values = forms.evaluate_all('forms => forms.map(form => [...new FormData(form)])')
        copy_name = page.get_by_label('Name der Kopie', exact=True)
        copy_name.focus()
        page.keyboard.press('Escape')
        expect(copy_name).to_be_focused()
        assert forms.evaluate_all('forms => forms.map(form => [...new FormData(form)])') == form_values
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
        page.screenshot(path=str(EVIDENCE / f'after-{editor_case["kind"]}-{width}-touch{touch}.png'), full_page=False)
        (EVIDENCE / f'buttons-{editor_case["kind"]}-{width}-touch{touch}.json').write_text(json.dumps({'buttons': modes, 'pointer': pointer}, indent=2))
        assert not posts
    assert state(editor_case['owner']) == before
