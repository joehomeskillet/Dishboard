"""BF-E3 T24/T26/T34: focus successor, low-height reach, single open/close effect."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Error, expect

from test_admin_workflow_routes import DATABASE_URL, DAY, _login, database_engine  # noqa: F401
from test_recipe_routes import create
from test_rendered_ui import browser  # noqa: F401
from test_ui_master_shell_browser import _goto, _page, site  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/state/claude-session-2026-09-29/audit/BF/E3'
VIEWPORTS = ((1280, 720), (390, 430))
REACH = """(el) => {
  const style = getComputedStyle(el);
  const pad = (parseFloat(style.outlineWidth) || 0) + Math.max(parseFloat(style.outlineOffset) || 0, 0);
  const rect = el.getBoundingClientRect();
  const box = {left: rect.left - pad, top: rect.top - pad, right: rect.right + pad, bottom: rect.bottom + pad};
  const hit = document.elementFromPoint(
    Math.min(Math.max(rect.left + rect.width / 2, 0), innerWidth - 1),
    Math.min(Math.max(rect.top + rect.height / 2, 0), innerHeight - 1),
  );
  const covered = [];
  for (const bar of document.querySelectorAll(
    '[data-sticky], [data-sticky-form], .admin-form-footer, .admin-week-controls, .admin-actions'
  )) {
    const position = getComputedStyle(bar).position;
    if (position !== 'sticky' && position !== 'fixed') continue;
    if (bar === el || bar.contains(el)) continue;
    const bounds = bar.getBoundingClientRect();
    const overlaps = !(box.right < bounds.left || box.left > bounds.right
      || box.bottom < bounds.top || box.top > bounds.bottom);
    if (overlaps) covered.push(String(bar.id || bar.className || bar.tagName).slice(0, 80));
  }
  return {
    inView: box.left >= -1 && box.top >= -1 && box.right <= innerWidth + 1 && box.bottom <= innerHeight + 1,
    hitOk: !!hit && (hit === el || el.contains(hit) || hit.contains(el)),
    covered,
    top: Math.round(box.top),
    right: Math.round(box.right),
    bottom: Math.round(box.bottom),
    left: Math.round(box.left),
    view: [innerWidth, innerHeight],
  };
}"""
LISTENER = """
window.__bfListenerAdds = 0;
const bfOriginalListener = EventTarget.prototype.addEventListener;
EventTarget.prototype.addEventListener = function bfCountListener() {
  window.__bfListenerAdds += 1;
  return bfOriginalListener.apply(this, arguments);
};
"""
SETTLE = "() => new Promise(resolve => requestAnimationFrame(() => requestAnimationFrame(resolve)))"


def _shot(page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / f'{name}.png'))


def _recipe(client) -> str:
    return urlsplit(create(client, title='BF-E3 Dialog')).path


def _menu() -> str:
    return f'/admin/cafeteria/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


def _settle(page, javascript: bool) -> None:
    if javascript:
        page.evaluate(SETTLE)
        return
    # Chromium does not run requestAnimationFrame while JavaScript is disabled.
    page.wait_for_timeout(32)


def _open_field(page, selector: str) -> str | None:
    """Open closed ancestors from the keyboard. Return the navigation error, if one happens."""
    try:
        page.locator(selector).first.wait_for(state='attached')
        holders = page.locator(f'details:has({selector})')
        for index in range(holders.count()):
            details = holders.nth(index)
            if details.evaluate('el => el.open'):
                continue
            summary = details.locator('> summary')
            summary.focus()
            page.keyboard.press('Enter')
            if not details.evaluate('el => el.open'):
                summary.click()
    except Error as exc:
        return str(exc).splitlines()[0]
    return None


def _reachable(page, selector: str, shot: str, failures: list, javascript: bool) -> None:
    target = page.locator(selector).first
    try:
        target.focus()
        _settle(page, javascript)
        detail = target.evaluate(REACH)
    except Error as exc:
        url = ''
        try:
            url = page.url
            _shot(page, shot)
        except Error:
            pass
        failures.append((shot, selector, url, str(exc).splitlines()[0]))
        return
    if not (detail['inView'] and detail['hitOk'] and not detail['covered']):
        _shot(page, shot)
        failures.append((shot, selector, detail))


def _surfaces(recipe: str) -> tuple[tuple[str, str, str, str], ...]:
    return (
        ('rezept', recipe, '[name="source.note"]',
         '.admin-form-footer[data-sticky-form="recipe-editor"] [form="recipe-editor"][data-semantic="actions.save"]'),
        ('menue', _menu(), '#f-ext', '[aria-label="Menü speichern"]'),
        ('zutat', '/admin/grundlagen/zutaten/neu', '#note', '.admin-form-footer [data-semantic="actions.save"]'),
        ('einkauf', '/admin/einkaufslisten', '[name="menu_week_public_id"]', '#einkaufsliste-neu button[type="submit"]'),
        ('benutzer', '/admin/benutzer/neu', '#create-password-confirm', '#create-local-user [data-semantic="actions.save"]'),
        ('woche', '/admin/cafeteria', '#week_shared_note', '.admin-week-settings [data-semantic="actions.save"]'),
    )


def test_t24_remove_and_close_move_focus_to_successor(site) -> None:  # noqa: F811
    """Removing a row focuses the successor; closing a disclosure returns to its trigger."""
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    recipe = _recipe(client)
    for javascript in (True, False):
        page = _page(site, client, viewport={'width': 1280, 'height': 900}, java_script_enabled=javascript)
        try:
            _goto(page, recipe)
            page.get_by_role('button', name='Zutat hinzufügen', exact=True).click()
            page.wait_for_load_state('networkidle')
            expect(page.locator('[data-recipe-ingredient]')).to_have_count(2)
            page.get_by_role('button', name='Zutat 1 entfernen', exact=True).click()
            page.wait_for_load_state('networkidle')
            expect(page.locator('[data-recipe-ingredient]')).to_have_count(1)
            successor = page.locator('[id="ingredients.0.ingredient_text"]')
            expect(successor).to_be_focused()
            page.keyboard.press('Tab')
            in_form = page.evaluate('!!document.activeElement.closest("#recipe-editor")')
            if not in_form:
                _shot(page, f't24-tab-js{int(javascript)}')
            assert in_form
            opened = page.evaluate('document.getElementById("ingredient-details-0").open')
            if javascript:
                trigger = page.locator('[data-recipe-toggle="ingredient-details-0"]')
                if not opened:
                    trigger.click()
                page.locator('#ingredient-details-0 input, #ingredient-details-0 select, #ingredient-details-0 textarea').first.focus()
                page.keyboard.press('Escape')
                closed = page.evaluate("""() => !document.getElementById('ingredient-details-0').open
                  && document.activeElement === document.querySelector('[data-recipe-toggle="ingredient-details-0"]')""")
                if not closed:
                    _shot(page, 't24-escape')
                expect(trigger).to_be_focused()
                assert not page.evaluate('document.getElementById("ingredient-details-0").open')
            else:
                summary = page.locator('#ingredient-details-0 > summary')
                if not opened:
                    summary.click()
                summary.click()
                closed = page.evaluate("""() => !document.getElementById('ingredient-details-0').open
                  && document.activeElement === document.querySelector('#ingredient-details-0 > summary')""")
                if not closed:
                    _shot(page, 't24-summary-close')
                expect(summary).to_be_focused()
                assert not page.evaluate('document.getElementById("ingredient-details-0").open')
        finally:
            page.context.close()


def test_t24_menu_remove_focuses_remaining_row(site) -> None:  # noqa: F811
    """One client-side remove leaves focus on a control in the remaining row."""
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 1280, 'height': 900})
    try:
        _goto(page, _menu())
        rows = page.locator('#components-list .component-row')
        start = rows.count()
        page.get_by_role('button', name='Baustein hinzufügen', exact=True).click()
        expect(rows).to_have_count(start + 1)
        # A new row opens in edit mode; its delete control lives in the summary.
        expect(rows.last.locator('[data-component-edit-view]')).to_be_visible()
        rows.last.locator('[data-remove-row]').click()
        expect(rows).to_have_count(start)
        placed = page.evaluate("""() => {
          const active = document.activeElement;
          return !!active && active !== document.body && !!active.closest('#components-list');
        }""")
        if not placed:
            _shot(page, 't24-menu-remove')
        assert placed
    finally:
        page.context.close()


def test_t26_last_field_and_save_remain_uncovered(site) -> None:  # noqa: F811
    """Last field and save stay fully visible at desktop height and narrow short height."""
    # BF-Lücke: reference_scaffold/cafeteria/static/admin-tabler.css:577
    # BF-Lücke: reference_scaffold/cafeteria/static/admin.js:848
    # BF-Lücke: reference_scaffold/cafeteria/static/app.css:786
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    surfaces = _surfaces(_recipe(client))
    failures: list = []
    for width, height in VIEWPORTS:
        for javascript in (True, False):
            page = _page(
                site, client, viewport={'width': width, 'height': height}, java_script_enabled=javascript,
            )
            try:
                for label, path, field, save in surfaces:
                    _goto(page, path)
                    shot = f't26-{label}-{width}x{height}-js{int(javascript)}'
                    opened = _open_field(page, field)
                    if opened:
                        try:
                            _shot(page, shot + '-open')
                        except Error:
                            pass
                        failures.append((shot + '-open', field, page.url, opened))
                        continue
                    _reachable(page, field, shot + '-field', failures, javascript)
                    _reachable(page, save, shot + '-save', failures, javascript)
            finally:
                page.context.close()
    assert not failures, failures


def _ids(page) -> list:
    return page.evaluate("""() => {
      const seen = new Set();
      const duplicate = [];
      for (const id of [...document.querySelectorAll('[id]')].map(el => el.id).filter(Boolean)) {
        if (seen.has(id)) duplicate.push(id);
        seen.add(id);
      }
      return duplicate.slice(0, 8);
    }""")


def _cycle(page, details: str, trigger, shot: str, javascript: bool) -> None:
    page.evaluate(
        """selector => { const el = document.querySelector(selector); if (el && el.open) el.open = false; }""",
        details,
    )
    for index in range(20):
        trigger.click()
        opened = page.evaluate('selector => document.querySelector(selector).open', details)
        if opened != (index % 2 == 0):
            _shot(page, shot)
            raise AssertionError((details, index, opened))
        if javascript and index == 1:
            page.evaluate(SETTLE)
            page.evaluate('() => { window.__bfE3Base = window.__bfListenerAdds; }')
    if javascript:
        grown = page.evaluate('() => window.__bfListenerAdds - window.__bfE3Base')
        if grown != 0:
            _shot(page, shot + '-listeners')
            raise AssertionError((details, 'listeners', grown))


def _cycle_publish(page) -> None:
    trigger = page.locator('[data-bs-target="#week-publish-modal"]:not([disabled])')
    if trigger.count() == 0:
        return
    opener = trigger.first
    close = page.locator('#week-publish-modal [aria-label="Schliessen"]')
    for index in range(10):
        opener.click()
        try:
            expect(page.locator('.modal-backdrop')).to_have_count(1)
        except AssertionError:
            _shot(page, 't34-publish-open')
            raise
        close.click()
        try:
            expect(page.locator('.modal-backdrop')).to_have_count(0)
            expect(page.locator('#week-publish-modal.show')).to_have_count(0)
        except AssertionError:
            _shot(page, 't34-publish-close')
            raise
        if index == 0:
            page.evaluate('() => { window.__bfE3Base = window.__bfListenerAdds; }')
    grown = page.evaluate('() => window.__bfListenerAdds - window.__bfE3Base')
    if grown != 0:
        _shot(page, 't34-publish-listeners')
        raise AssertionError(('publish', 'listeners', grown))


def test_t34_open_close_does_not_duplicate_listeners(site) -> None:  # noqa: F811
    """Twenty open/close cycles keep one effect per click and do not rebind."""
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    recipe = _recipe(client)
    for javascript in (True, False):
        page = _page(site, client, viewport={'width': 1280, 'height': 900}, java_script_enabled=javascript)
        page.on('dialog', lambda dialog: dialog.accept())
        if javascript:
            page.context.add_init_script(LISTENER)
        try:
            _goto(page, recipe)
            if javascript:
                _cycle(
                    page, '#ingredient-details-0',
                    page.locator('[data-recipe-toggle="ingredient-details-0"]'),
                    't34-ingredient', True,
                )
            else:
                _cycle(page, '#ingredient-details-0', page.locator('#ingredient-details-0 > summary'), 't34-ingredient', False)
            _cycle(page, '#recipe-source', page.locator('#recipe-source > summary'), 't34-source', javascript)
            duplicate = _ids(page)
            if duplicate:
                _shot(page, f't34-ids-recipe-js{int(javascript)}')
            assert not duplicate, duplicate
            before = page.locator('[data-recipe-ingredient]').count()
            page.get_by_role('button', name='Zutat hinzufügen', exact=True).click()
            page.wait_for_load_state('networkidle')
            expect(page.locator('[data-recipe-ingredient]')).to_have_count(before + 1)
            _goto(page, '/admin/import-preview')
            expect(page.locator('#csv-more > summary')).to_have_count(0)
            expect(page.locator('#csv-more')).to_be_visible()
            expect(page.locator('#csv-more')).to_contain_text('getrennte Formate')
            page.locator('#file').focus()
            expect(page.locator('#file')).to_be_focused()
            _goto(page, '/admin/benutzer/neu')
            expect(page.locator('#create-local-user > summary')).to_have_count(0)
            expect(page.locator('#create-local-user form')).to_be_visible()
            _goto(page, '/admin/einkaufslisten')
            expect(page.locator('#einkaufsliste-neu-extra > summary')).to_have_count(0)
            expect(page.locator('#note')).to_be_visible()
            expect(page.locator('#menu_week_public_id')).to_be_visible()
            before = _ids(page)
            page.locator('#note').focus()
            page.locator('#menu_week_public_id').focus()
            assert _ids(page) == before
            _goto(page, '/admin/cafeteria')
            expect(page.locator('details.admin-week-settings')).to_have_count(0)
            title = page.locator('.admin-week-settings [name="title"]')
            if javascript:
                page.evaluate('() => { window.__bfE3Base = window.__bfListenerAdds; }')
            for _ in range(20):
                title.focus()
                expect(title).to_be_focused()
                expect(title).to_be_visible()
            if javascript:
                assert page.evaluate('() => window.__bfListenerAdds - window.__bfE3Base') == 0
            if javascript:
                _cycle_publish(page)
            duplicate = _ids(page)
            if duplicate or page.locator('dialog[open]').count() or page.locator('.modal-backdrop').count():
                _shot(page, f't34-after-js{int(javascript)}')
            assert not duplicate, duplicate
            assert page.locator('dialog[open]').count() == 0
            assert page.locator('.modal-backdrop').count() == 0
        finally:
            page.context.close()
