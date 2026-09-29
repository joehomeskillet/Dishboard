"""Weekly template disclosure names identify their exact slot in DE and EN."""
from __future__ import annotations

from datetime import timedelta
import json
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect
from sqlalchemy import text

from cafeteria.workflow_partial_store import persist_menu_item, persist_week_header
from test_admin_ux_browser import live_server
from test_admin_workflow_routes import DAY, WEEK, _login, _payload
from test_menu_collection import _scope
from test_menu_template_binding_db import make_template, stored_state
from test_rendered_ui import admin_app, admin_engine, browser

__all__ = ['admin_app', 'admin_engine', 'browser', 'live_server']

TITLE = 'Kartoffeln "Kräuter" & Gemüse'
TEMPLATE = 'Vorlage "Küche" & Garten'
FORM_STATE = '''forms => forms.map(form => ({
    action: form.getAttribute('action'), method: form.getAttribute('method'),
    fields: [...new FormData(form)]
}))'''


def _seed_slots(engine, client, profile):
    scope = _scope(client, engine, profile)
    templates = [make_template(engine, title=TEMPLATE), make_template(engine, title=TEMPLATE)]
    persist_week_header(engine, scope, WEEK, {'title': 'Kontextwoche', 'shared_note': ''}, 0)
    slots = [(0, 'LUNCH', 'MENU_1'), (0, 'LUNCH', 'VEGGIE'), (1, 'LUNCH', 'MENU_1')]
    if profile == 'patient':
        slots.append((0, 'DINNER', 'MENU_1'))
    expected = []
    for index, (offset, meal, option) in enumerate(slots):
        day = (WEEK + timedelta(days=offset)).isoformat()
        archived = index == 1
        template = templates[int(archived)]
        payload = _payload(staff=profile == 'staff_guest')
        payload.update(title=TITLE, dish_template_public_id=template['public_id'])
        persist_menu_item(engine, scope, WEEK, day, meal, option, payload, 0)
        identity = ', '.join((
            'Montag' if offset == 0 else 'Dienstag',
            '31. August' if offset == 0 else '1. September',
            'Mittag' if meal == 'LUNCH' else 'Abend',
            'Menü 1' if option == 'MENU_1' else 'Vegetarisch',
        )) + ' – ' + TITLE
        expected.append((f'#week-slot-{day}-{meal}-{option}', identity, template['public_id'], archived))
    with engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.dish_templates SET active=false WHERE id=:id'), templates[1])
    return expected


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('locale', ['de', 'en'])
@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('width', [1440, 390])
def test_week_template_menu_context_is_localized_distinct_and_native(
    browser, live_server, admin_app, admin_engine, tmp_path,
    family, profile, locale, javascript, width,
):
    # The action grammar is translated; existing German week data labels are unchanged.
    admin_app.config['UI_LOCALE'] = locale
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    slots = _seed_slots(admin_engine, client, profile)
    before = stored_state(admin_engine)
    cookie = client.get_cookie('session')
    assert cookie is not None
    with browser.new_context(
        base_url=live_server, java_script_enabled=javascript, reduced_motion='reduce',
        has_touch=width == 390, viewport={'width': width, 'height': 900 if width == 1440 else 844},
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        trace = []

        def record(stage):
            state = page.evaluate('''() => {
                const describe = node => node ? {
                    tag: node.tagName, id: node.id, name: node.getAttribute('aria-label'),
                    slot: node.closest('.menu-slot')?.id,
                    focused: node === document.activeElement, hovered: node.matches(':hover'),
                    detailsOpen: node.closest('details')?.open,
                    describedBy: node.getAttribute('aria-describedby'),
                    activeTrigger: window.tabler?.Tooltip.getInstance(node)?._activeTrigger,
                    box: node.getBoundingClientRect().toJSON()
                } : null;
                return {
                    pointerFine: matchMedia('(pointer: fine)').matches,
                    pointerCoarse: matchMedia('(pointer: coarse)').matches,
                    anyPointerFine: matchMedia('(any-pointer: fine)').matches,
                    anyPointerCoarse: matchMedia('(any-pointer: coarse)').matches,
                    maxTouchPoints: navigator.maxTouchPoints, innerWidth, innerHeight,
                    devicePixelRatio, visualViewport: {
                        width: visualViewport.width, height: visualViewport.height,
                        scale: visualViewport.scale
                    }, activeElement: describe(document.activeElement),
                    summaries: [...document.querySelectorAll('.admin-week-template > summary')].map(describe),
                    tooltips: [...document.querySelectorAll('[role="tooltip"]')].map(tip => ({
                        id: tip.id, text: tip.textContent, visible: !!tip.getClientRects().length,
                        shown: tip.classList.contains('show'), hovered: tip.matches(':hover'),
                        owners: [...document.querySelectorAll('[data-ui-tooltip]')].filter(node =>
                            (node.getAttribute('aria-describedby') || '').split(/\\s+/).includes(tip.id)
                            || window.tabler?.Tooltip.getInstance(node)?.tip === tip).map(describe)
                    }))
                };
            }''')
            trace.append({'stage': stage, 'configuredHasTouch': width == 390, 'state': state})
            (tmp_path / 'interaction-diagnostic.json').write_text(
                json.dumps(trace, ensure_ascii=False, indent=2), encoding='utf-8',
            )

        methods = []
        page.on('request', lambda request: methods.append(request.method))
        response = page.goto(f'/admin/{family}?week={DAY}', wait_until='networkidle')
        assert response is not None and response.status == 200
        expect(page.locator('html')).to_have_attribute('lang', locale)
        page.evaluate('document.fonts.ready')
        record('loaded-fonts-ready')
        forms_before = page.locator('main form').evaluate_all(FORM_STATE)
        summaries = page.locator('.admin-week-template > summary')
        expect(summaries).to_have_count(len(slots))
        observations = summaries.evaluate_all('''nodes => nodes.map(node => ({
            name: node.getAttribute('aria-label'), tooltip: node.getAttribute('data-ui-tooltip'),
            html: node.outerHTML, box: node.getBoundingClientRect().toJSON()
        }))''')
        (tmp_path / 'summary-context.json').write_text(
            json.dumps(observations, ensure_ascii=False, indent=2), encoding='utf-8',
        )
        first = page.locator(slots[0][0]).locator('.admin-week-template')
        first.scroll_into_view_if_needed()
        record('after-first-scroll')
        page.screenshot(path=str(tmp_path / 'week-template-closed.png'), full_page=False)
        record('after-closed-viewport-screenshot')
        first.locator('summary').press('Enter')
        expect(first).to_have_attribute('open', '')
        record('after-first-enter')
        page.screenshot(path=str(tmp_path / 'week-template-open.png'), full_page=False)
        record('after-open-viewport-screenshot')
        first.locator('summary').press('Space')
        expect(first).not_to_have_attribute('open', '')
        record('after-first-space')

        names = []
        for selector, identity, public_id, archived in slots:
            card = page.locator(selector)
            details = card.locator('.admin-week-template')
            trigger = details.locator('summary')
            name = f'Weitere Aktionen für {identity}' if locale == 'de' else f'More actions for {identity}'
            # Expected RED: current manual summary omits slot context and has a different tooltip.
            expect(trigger).to_have_accessible_name(name)
            expect(trigger).to_have_attribute('data-ui-tooltip', name)
            expect(trigger).to_have_text('')
            expect(trigger).to_have_attribute('data-semantic', 'actions.more')
            expect(trigger.locator('svg')).to_have_attribute('aria-hidden', 'true')
            expect(trigger.locator('use')).to_have_attribute(
                'href', '/static/vendor/tabler-icons/tabler-icons.svg#tabler-dots',
            )
            assert trigger.get_attribute('title') is None
            assert trigger.locator('button, a, input').count() == 0
            assert trigger.evaluate('e => e.getAttribute("aria-label").includes("&amp;")') is False
            record(f'{selector}:before-pointer-assertion')
            coarse = page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches")
            assert coarse is (width == 390)
            size = 44 if coarse else 36
            box = trigger.bounding_box()
            assert box and (box['width'], box['height']) == (size, size), box
            names.append(trigger.get_attribute('aria-label'))
            trigger.focus()
            expect(trigger).to_be_focused()
            record(f'{selector}:after-focus')
            if javascript:
                tooltip = page.get_by_role('tooltip', name=name, exact=True)
                try:
                    expect(tooltip).to_be_visible()
                    expect(tooltip).to_have_text(name)
                except Exception:
                    record(f'{selector}:tooltip-assertion-failed')
                    raise
                trigger.press('Escape')
                expect(tooltip).to_be_hidden()
                record(f'{selector}:after-escape')
            trigger.press('Enter')
            expect(details).to_have_attribute('open', '')
            record(f'{selector}:after-enter')
            link = details.locator('a')
            expect(link).to_be_visible()
            expect(link).to_have_attribute('href', f'/admin/gerichtvorlagen/{public_id}')
            expect(link).to_have_text(f'Aus Vorlage «{TEMPLATE}»' + (' (archiviert)' if archived else ''))
            trigger.press('Space')
            expect(details).not_to_have_attribute('open', '')
            expect(link).to_be_hidden()
            record(f'{selector}:after-space')
            expect(card.locator('[data-allergen-state="missing"]')).to_contain_text('nicht allergenfrei')
        assert len(set(names)) == len(slots)
        assert page.locator('main form').evaluate_all(FORM_STATE) == forms_before
        expect(page.locator('#week-publish-form [type="submit"]')).to_be_disabled()
        empty_day = (WEEK + timedelta(days=1)).isoformat()
        actions = [(selector, identity, 'edit') for selector, identity, _, _ in slots]
        actions.append((f'#week-slot-{empty_day}-LUNCH-VEGGIE',
                        'Dienstag, 1. September, Mittag, Vegetarisch – Noch kein Gericht', 'add'))
        name_failures = []
        for index, (selector, identity, semantic) in enumerate(actions):
            card = page.locator(selector)
            action = card.locator('.admin-week-card-action > a')
            label = {'de': {'edit': 'bearbeiten', 'add': 'anlegen'},
                     'en': {'edit': 'Edit', 'add': 'Create'}}[locale][semantic]
            expected_name = f'{identity} {label}' if locale == 'de' else f'{label} {identity}'
            actual = action.get_attribute('aria-label')
            tooltip_name = action.get_attribute('data-ui-tooltip')
            if actual != expected_name or tooltip_name != expected_name:
                name_failures.append({'slot': selector, 'semantic': semantic,
                                      'expected': expected_name, 'actual': actual,
                                      'tooltip': tooltip_name})
            expect(action).to_have_accessible_name(actual)
            expect(action).to_have_text('')
            expect(action).to_have_attribute('data-semantic', f'actions.{semantic}')
            expect(action.locator('use')).to_have_attribute(
                'href', '/static/vendor/tabler-icons/tabler-icons.svg#tabler-' +
                ('edit' if semantic == 'edit' else 'plus'),
            )
            expect(action.locator('svg')).to_have_attribute('aria-hidden', 'true')
            target = urlsplit(action.get_attribute('href'))
            assert target.path == f'/admin/{family}/menu'
            assert parse_qs(target.query) == {
                'week': [DAY], 'day': [card.get_attribute('data-day')],
                'meal': [card.get_attribute('data-meal')], 'option': [card.get_attribute('data-option')],
            }
            action.scroll_into_view_if_needed()
            page.mouse.move(0, 0)
            action.focus()
            expect(action).to_be_focused()
            assert action.evaluate('el => getComputedStyle(el).outlineStyle') != 'none'
            box = action.bounding_box()
            size = 44 if width == 390 else 36
            assert box and (box['width'], box['height']) == (size, size)
            if javascript:
                tooltip = page.get_by_role('tooltip', name=actual, exact=True)
                expect(tooltip).to_be_visible()
                action.press('Escape')
                expect(tooltip).to_be_hidden()
                expect(action).to_be_focused()
            for moment in ('before', 'after'):
                record(f'{selector}:slot-action-{moment}-capture')
                state = trace[-1]['state']
                assert state['pointerCoarse'] == state['anyPointerCoarse'] == (width == 390)
                assert state['maxTouchPoints'] == int(width == 390)
                if moment == 'before' and (index == 0 or semantic == 'add'):
                    page.screenshot(path=str(tmp_path / f'slot-action-{semantic}.png'), full_page=False)
        (tmp_path / 'slot-action-names.json').write_text(
            json.dumps({'failures': name_failures, 'checked': len(actions)}, ensure_ascii=False, indent=2),
            encoding='utf-8',
        )
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert methods and set(methods) == {'GET'}
        assert not name_failures, name_failures
    assert stored_state(admin_engine) == before


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('width', [1440, 390])
def test_week_template_menu_geometry_and_open_content(
    browser, live_server, admin_app, admin_engine, tmp_path, family, profile, width,
):
    """Record sizing and open-content failures independently of the name RED."""
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    slots = _seed_slots(admin_engine, client, profile)
    cookie = client.get_cookie('session')
    assert cookie is not None
    with browser.new_context(
        base_url=live_server, java_script_enabled=False, has_touch=width == 390,
        viewport={'width': width, 'height': 900 if width == 1440 else 844},
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        response = page.goto(f'/admin/{family}?week={DAY}', wait_until='networkidle')
        assert response is not None and response.status == 200
        page.evaluate('document.fonts.ready')
        card = page.locator(slots[0][0])
        details = card.locator('.admin-week-template')
        trigger = details.locator('summary')
        title = card.locator('.admin-week-card-title')
        before_title = title.bounding_box()
        text_blocks = card.locator('.admin-week-card-title, .admin-week-components, [data-menu-metadata]')
        before_text = text_blocks.evaluate_all('nodes => nodes.map(node => node.getBoundingClientRect().toJSON())')
        summary_box = trigger.bounding_box()
        assert before_title and summary_box
        coarse = page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches")
        assert coarse is (width == 390)
        size = 44 if coarse else 36
        failures = []
        if (summary_box['width'], summary_box['height']) != (size, size):
            failures.append({'kind': 'semantic-square', 'expected': size, 'actual': summary_box})
        css = trigger.evaluate('''node => {
            const sheet = [...document.styleSheets].find(s => s.href?.endsWith('/admin-wochenplan-kern.css'));
            return {
                minHeight: getComputedStyle(node).minHeight, padding: getComputedStyle(node).padding,
                matchingLocalRules: [...sheet.cssRules].filter(rule => rule.selectorText
                    && node.matches(rule.selectorText) && rule.style.minHeight)
                    .map(rule => ({selector: rule.selectorText, declarations: rule.style.cssText}))
            };
        }''')
        card.scroll_into_view_if_needed()
        page.screenshot(path=str(tmp_path / 'geometry-closed.png'), full_page=False)
        trigger.press('Enter')
        expect(details).to_have_attribute('open', '')
        open_coarse = page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches")
        assert open_coarse is coarse
        open_summary = trigger.bounding_box()
        assert open_summary and (open_summary['width'], open_summary['height']) == (size, size), open_summary
        link = details.locator('a')
        expect(link).to_be_visible()
        after_title, card_box, link_box = title.bounding_box(), card.bounding_box(), link.bounding_box()
        assert after_title and card_box and link_box
        after_text = text_blocks.evaluate_all('nodes => nodes.map(node => node.getBoundingClientRect().toJSON())')
        if after_title['width'] < before_title['width'] - 1:
            failures.append({'kind': 'open-content-compression', 'before': before_title, 'after': after_title})
        for before, after in zip(before_text, after_text, strict=True):
            if after['width'] < before['width'] - 1:
                failures.append({'kind': 'open-text-compression', 'before': before, 'after': after})
        panel_box = details.bounding_box()
        assert panel_box
        for kind, box in (('panel', panel_box), ('link', link_box)):
            if (box['x'] < card_box['x'] - 1 or box['y'] < card_box['y'] - 1
                    or box['x'] + box['width'] > card_box['x'] + card_box['width'] + 1
                    or box['y'] + box['height'] > card_box['y'] + card_box['height'] + 1):
                failures.append({'kind': f'template-{kind}-outside-card', 'card': card_box, 'actual': box})
        rows = page.locator('.menu-slot').evaluate_all('nodes => nodes.map(node => node.getBoundingClientRect().toJSON())')
        for index, first in enumerate(rows):
            for second in rows[index + 1:]:
                if (min(first['right'], second['right']) - max(first['left'], second['left']) > 1
                        and min(first['bottom'], second['bottom']) - max(first['top'], second['top']) > 1):
                    failures.append({'kind': 'overlapping-menu-slots', 'first': first, 'second': second})
        page.screenshot(path=str(tmp_path / 'geometry-open.png'), full_page=False)
        assert page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches") is coarse
        (tmp_path / 'geometry.json').write_text(json.dumps({
            'css': css, 'closedSummary': summary_box, 'closedTitle': before_title,
            'openSummary': open_summary, 'coarsePointer': open_coarse,
            'openTitle': after_title, 'closedText': before_text, 'openText': after_text,
            'panel': panel_box, 'link': link_box, 'failures': failures,
        }, ensure_ascii=False, indent=2), encoding='utf-8')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert not failures, failures
