"""DELTA-3-12 print editor evidence for all consumers of the shared template."""
from pathlib import Path
import json
from urllib.parse import parse_qsl, urlsplit

import pytest
from playwright.sync_api import expect

from test_recipe_template_editor_routes import state

from test_icon_print_editor_calm_browser import (  # noqa: F401
    editor_case, _page, browser, editor_server, database_engine, editor_app,
    recipe_server, recipe_editor, b3, pg16, installed_pg16, seeded_pg16, app_engine,
)

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/state/delta3-l2final-1002/DELTA-3-12'


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
        expect(page.locator('main details, main summary')).to_have_count(0)
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


@pytest.mark.parametrize('editor_case', ['recipes'], indirect=True)
@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('touch', [False, True])
def test_recipe_filter_consumers_keep_geometry_and_get_fields(
        editor_case, browser, tmp_path, width, javascript, touch):  # noqa: F811
    """D-79/D-45: same GET forms, fixed overlay, native and enhanced return paths."""
    before = state(editor_case['owner'])
    with _page(browser, editor_case, tmp_path, width, 1, javascript, has_touch=touch) as page:
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        for label, route, following in (
                ('list', '/admin/rezepte', '.recipe-row'),
                ('print', editor_case['url'], '[data-recipe-selection] .admin-list-row')):
            assert page.goto(route).status == 200
            page.evaluate('document.fonts.ready')
            expect(page.locator('main details, main summary')).to_have_count(0)
            form = page.locator('form[role="search"]')
            dialog = form.locator('.admin-filter-dialog')
            trigger = form.locator('[data-semantic="view.filter"]')
            expect(dialog).not_to_be_visible()
            assert form.get_attribute('method') == 'get'
            values = form.evaluate('form => [...new FormData(form)]')
            if label == 'print':
                fields = dict(values)
                assert fields['recipe'] == editor_case['recipe']
                assert fields['recipe_revision'] == editor_case['recipe_revision']
                assert fields['yield'] == '8'
                assert fields['template'] == 'standard'
                assert fields['revision']
            trigger.scroll_into_view_if_needed()
            trigger.focus()
            geometry = """node => {
                const r = node.getBoundingClientRect();
                return [r.x + scrollX, r.y + scrollY, r.width, r.height];
            }"""
            targets = [form, page.locator(following).first]
            boxes = [node.evaluate(geometry) for node in targets]
            scroll = page.evaluate('scrollY')
            evidence = EVIDENCE / f'filter-{label}-{width}-js{javascript}-touch{touch}'
            evidence.mkdir(parents=True, exist_ok=True)
            page.screenshot(path=str(evidence / 'before.png'))
            page.keyboard.press('Enter')
            expect(dialog).to_be_visible()
            expect(dialog.get_by_role('heading', name='Filter', exact=True)).to_be_visible()
            opened = [node.evaluate(geometry) for node in targets]
            if javascript:
                assert abs(page.evaluate('scrollY') - scroll) <= 1
            for previous, current in zip(boxes, opened):
                assert all(abs(a - b) <= 1 for a, b in zip(previous, current))
            assert page.evaluate("matchMedia('(any-pointer: coarse)').matches") is touch
            for control in dialog.locator('.ui-sem-control').all():
                box = control.bounding_box()
                assert box and min(box['width'], box['height']) >= (44 if touch else 36)
                assert bool(control.inner_text().strip()) != bool(control.locator('svg').count())
            assert form.evaluate('form => [...new FormData(form)]') == values
            page.screenshot(path=str(evidence / 'open.png'))
            if javascript:
                page.keyboard.press('Escape')
                expect(trigger).to_be_focused()
                assert abs(page.evaluate('scrollY') - scroll) <= 1
            else:
                dialog.locator('[data-read-detail-close]').click()
                expect(trigger).to_be_in_viewport()
                if label == 'print':
                    assert page.evaluate('scrollY') > 0
                trigger.focus()
                expect(trigger).to_be_focused()
            expect(dialog).not_to_be_visible()
            closed = [node.evaluate(geometry) for node in targets]
            for previous, current in zip(boxes, closed):
                assert all(abs(a - b) <= 1 for a, b in zip(previous, current))
            assert form.evaluate('form => [...new FormData(form)]') == values
            page.screenshot(path=str(evidence / 'closed.png'))
            (evidence / 'geometry.json').write_text(json.dumps({
                'before': boxes, 'open': opened, 'closed': closed,
                'scroll_before': scroll, 'scroll_after': page.evaluate('scrollY'),
                'javascript': javascript, 'touch': touch, 'width': width,
            }, indent=2))
            trigger.click()
            expect(dialog).to_be_visible()
            if label == 'list':
                dialog.locator('[name="archived"]').check()
            else:
                dialog.locator('[name="archived"]').select_option('1')
            submitted = form.evaluate('form => [...new FormData(form)]')
            with page.expect_navigation(wait_until='load'):
                dialog.get_by_role('button', name='Übernehmen', exact=True).click()
            assert sorted(parse_qsl(urlsplit(page.url).query, keep_blank_values=True)) == sorted(
                (name, value) for name, value in submitted)
            expect(page.locator('.admin-filter-dialog')).not_to_be_visible()
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not posts
    assert state(editor_case['owner']) == before
