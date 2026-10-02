"""Focused ingredient fields remain reachable when the shared footer changes mode."""
from __future__ import annotations

import json

from playwright.sync_api import expect

from test_master_data_browser import master_server  # noqa: F401
from test_master_data_routes import (  # noqa: F401
    app_engine, b3, installed_pg16, pg16, seeded_pg16,
)
from test_rendered_ui import browser  # noqa: F401


def test_mobile_note_focus_stays_in_viewport(b3, master_server, browser, tmp_path):  # noqa: F811
    base, cookie = master_server
    with browser.new_context(viewport={'width': 390, 'height': 1100}, java_script_enabled=True,
                             reduced_motion='reduce') as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + '/admin/grundlagen/zutaten/neu')
        page.get_by_label('Name', exact=True).fill('Mein erhaltener Entwurf')
        page.get_by_label('Testlager', exact=True).check()
        page.evaluate('''() => {
            window.d21Events = [];
            for (const name of ['mousedown', 'mouseup', 'click', 'focusin', 'scroll']) {
                document.addEventListener(name, event => {
                    const section = document.querySelector('#food-optional');
                    window.d21Events.push({type: name, tag: event.target.tagName, id: event.target.id,
                        y: event.clientY, scrollY,
                        section: section.getBoundingClientRect().toJSON()});
                }, true);
            }
        }''')
        note = page.get_by_label('Notiz', exact=True)
        expect(note).to_be_visible()
        expect(note.locator('xpath=ancestor::details')).to_have_count(0)
        note.focus()
        note.scroll_into_view_if_needed()
        try:
            expect(note).to_be_focused()
            expect(note).to_be_in_viewport(ratio=1)
        finally:
            geometry = page.evaluate('''() => ({
                scrollY, height: innerHeight, active: document.activeElement.id, events: window.d21Events,
                note: document.querySelector('#note').getBoundingClientRect().toJSON(),
                footer: document.querySelector('.admin-form-footer').getBoundingClientRect().toJSON(),
                footerPosition: getComputedStyle(document.querySelector('.admin-form-footer')).position,
                optional: document.querySelector('#food-optional').getBoundingClientRect().toJSON(),
                details: document.querySelectorAll('#food-core-form details').length
            })''')
            print('D21_NOTE_GEOMETRY', json.dumps(geometry))
            (tmp_path / 'note-geometry.json').write_text(json.dumps(geometry, indent=2), encoding='utf-8')
            page.screenshot(path=str(tmp_path / 'note-focus.png'))
