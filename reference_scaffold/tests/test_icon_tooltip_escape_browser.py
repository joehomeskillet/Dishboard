"""Escape ownership with real semantic macros, Tabler and native disclosures."""
import pytest
from playwright.sync_api import expect

from test_admin_shared_patterns_browser import _run_polish_check


MACROS = '''{% from 'ui/_semantic.html' import icon_summary, icon_button,
    more_actions, filter_bar_sem, confirm_dialog %}
    {% from 'admin/_macros.html' import field %}'''
TABLER = '<script src="/static/vendor/tabler/tabler.min.js"></script>'
FIELDS = '''{{ field('note', 'Notiz', 'Entwurf') }}
    <label><input type="checkbox" name="choice" value="a" checked>Auswahl A</label>
    <label><input type="checkbox" name="choice" value="b" checked>Auswahl B</label>'''
OTHER = '''<details id="other" open><summary>Anderer Abschnitt</summary>
    <p>Dieser Bereich bleibt offen.</p></details>
    {{ icon_button('actions.preview', type='button', id='outside') }}'''
DETAILS = MACROS + '''<form id="draft" method="post" action="/__polish__">
    <details id="related" open>
    {{ icon_summary('actions.upload', attrs={'aria-describedby': 'upload-help'}) }}
    <p id="upload-help">Die gewählte Datei bleibt erhalten.</p>''' + FIELDS + '''
    <label for="upload">Datei</label><input id="upload" name="source_file" type="file">
    </details></form>''' + OTHER + TABLER
FILTER = MACROS + '{% set filters %}' + FIELDS + '''{% endset %}
    {{ filter_bar_sem('/__polish__', search_value='Suppe', more_filters=filters,
        id='extra', active_count=2, open=true) }}''' + OTHER + TABLER


def _values(form):
    return form.evaluate('''el => [...new FormData(el)].map(([key, value]) =>
        [key, value instanceof File ? [value.name, value.size, value.type] : value])''')


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('kind', ['details', 'filter'])
def test_related_hover_preserves_field_before_escape_closes_own_details(kind, width, tmp_path):
    """A summary's hover tip must not close its focused form or immediately reopen."""
    def verify(page):
        requests = []
        page.on('request', lambda request: requests.append(request.url)
                if request.method != 'GET' or request.is_navigation_request() else None)
        form = page.locator('#draft' if kind == 'details' else 'form[role="search"]')
        details = form.locator('details').first
        summary = details.locator(':scope > summary')
        field = page.locator('#note')
        if kind == 'details':
            page.locator('#upload').set_input_files(
                {'name': 'Entwurf.txt', 'mimeType': 'text/plain', 'buffer': b'Entwurf'})
            page.locator('#upload').evaluate('el => { window.originalFile = el.files[0]; }')
        field.fill('Behalten " & Kräuter')
        before = _values(form)
        description = summary.get_attribute('aria-describedby')
        expect(field).to_be_focused()
        summary.hover()
        tooltip = page.get_by_role('tooltip', name=summary.get_attribute('aria-label'), exact=True)
        expect(tooltip).to_be_visible()
        expect(field).to_be_focused()
        page.screenshot(path=str(tmp_path / 'hover-before-escape.png'), full_page=True)

        page.keyboard.press('Escape')
        page.screenshot(path=str(tmp_path / 'hover-first-escape.png'), full_page=True)
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(field).to_be_focused()
        expect(details).to_have_attribute('open', '')
        assert _values(form) == before and requests == []

        page.keyboard.press('Escape')
        page.screenshot(path=str(tmp_path / 'hover-second-escape.png'), full_page=True)
        expect(details).not_to_have_attribute('open', '')
        expect(summary).to_be_focused()
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(page.locator('#other')).to_have_attribute('open', '')
        assert summary.get_attribute('aria-describedby') == description
        assert _values(form) == before and requests == []
        if kind == 'details':
            assert page.locator('#upload').evaluate('el => el.files[0] === window.originalFile')
        # A fresh hover clears only the Escape-return suppression, without blur.
        page.mouse.move(0, 0)
        summary.hover()
        expect(tooltip).to_be_visible()
        expect(summary).to_be_focused()
        page.keyboard.press('Escape')
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(summary).to_be_focused()
        expect(details).not_to_have_attribute('open', '')
        expect(page.locator('#other')).to_have_attribute('open', '')
        # A new deliberate interaction must still explain the action.
        page.mouse.move(0, 0)
        page.locator('#outside').focus()
        summary.focus()
        expect(tooltip).to_be_visible()

    _run_polish_check(DETAILS if kind == 'details' else FILTER, verify, width)


@pytest.mark.parametrize('width', [390, 1440])
def test_focused_tooltip_keeps_details_open_until_second_escape(width, tmp_path):
    def verify(page):
        form = page.locator('#draft')
        details = page.locator('#related')
        summary = details.locator(':scope > summary')
        before = _values(form)
        navigations = []
        page.on('request', lambda request: navigations.append(request.url)
                if request.method != 'GET' or request.is_navigation_request() else None)
        summary.focus()
        expect(page.get_by_role('tooltip')).to_be_visible()
        page.keyboard.press('Escape')
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(summary).to_be_focused()
        expect(details).to_have_attribute('open', '')
        page.keyboard.press('Escape')
        expect(details).not_to_have_attribute('open', '')
        expect(summary).to_be_focused()
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(page.locator('#other')).to_have_attribute('open', '')
        assert summary.get_attribute('aria-describedby') == 'upload-help'
        assert _values(form) == before and navigations == []
        page.screenshot(path=str(tmp_path / 'focused-second-escape.png'), full_page=True)

    _run_polish_check(DETAILS, verify, width)


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('key', ['Enter', 'Space'])
def test_keyboard_reopen_restores_tooltip_without_blur(key, width):
    def verify(page):
        form = page.locator('#draft')
        details = page.locator('#related')
        summary = details.locator(':scope > summary')
        field = page.locator('#note')
        field.fill('Unveränderter Entwurf')
        before = _values(form)
        requests = []
        page.on('request', lambda request: requests.append(request.url)
                if request.method != 'GET' or request.is_navigation_request() else None)
        page.mouse.move(0, 0)
        page.keyboard.press('Escape')
        expect(details).not_to_have_attribute('open', '')
        expect(summary).to_be_focused()
        expect(page.get_by_role('tooltip')).to_have_count(0)
        summary.press(key)
        expect(details).to_have_attribute('open', '')
        expect(summary).to_be_focused()
        tooltip = page.get_by_role('tooltip', name=summary.get_attribute('aria-label'), exact=True)
        expect(tooltip).to_be_visible()
        page.keyboard.press('Escape')
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(details).to_have_attribute('open', '')
        expect(summary).to_be_focused()
        page.keyboard.press('Escape')
        expect(details).not_to_have_attribute('open', '')
        expect(summary).to_be_focused()
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(page.locator('#other')).to_have_attribute('open', '')
        assert summary.get_attribute('aria-describedby') == 'upload-help'
        assert _values(form) == before and requests == []

    _run_polish_check(DETAILS, verify, width)


@pytest.mark.parametrize('width', [390, 1440])
def test_menu_capture_dismisses_item_tooltip_before_closing_menu(width, tmp_path):
    markup = MACROS + '''<form id="draft" method="post" action="/__polish__">
        {{ field('note', 'Notiz', 'Unveränderter Entwurf') }}</form>
        {{ more_actions([{'key':'actions.copy', 'name':'intent', 'value':'copy',
            'form':'draft', 'id':'copy'}], object='Entwurf') }}''' + OTHER + TABLER

    def verify(page):
        navigations = []
        page.on('request', lambda request: navigations.append(request.url)
                if request.method != 'GET' or request.is_navigation_request() else None)
        form = page.locator('#draft')
        before = _values(form)
        menu = page.get_by_role('group', name='Aktionen für Entwurf', exact=True)
        expect(menu.locator('details, summary')).to_have_count(0)
        item = page.locator('#copy')
        item.focus()
        expect(item).to_be_focused()
        expect(item).to_have_text('')
        expect(item).to_have_accessible_name('Entwurf kopieren')
        expect(page.get_by_role('tooltip', name=item.get_attribute('aria-label'), exact=True)).to_be_visible()
        page.keyboard.press('Escape')
        page.screenshot(path=str(tmp_path / 'menu-first-escape.png'), full_page=True)
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(menu).to_be_visible()
        expect(item).to_be_focused()
        assert _values(form) == before and navigations == []
        page.keyboard.press('Escape')
        expect(menu).to_be_visible()
        expect(item).to_be_focused()
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(page.locator('#other')).to_have_attribute('open', '')
        assert _values(form) == before and navigations == []

    _run_polish_check(markup, verify, width)


@pytest.mark.parametrize('width', [390, 1440])
@pytest.mark.parametrize('kind', ['native', 'tabler'])
@pytest.mark.parametrize('focus_direct', [False, True])
def test_unrelated_hover_does_not_consume_modal_escape(kind, width, tmp_path, focus_direct):
    content = '''{{ field('modal-note', 'Notiz', 'Modalentwurf') }}
        {{ more_actions([{'key':'actions.copy', 'type':'button', 'id':'foreign'}]) }}'''
    if kind == 'native':
        modal = '''{{ icon_button('actions.preview', type='button', id='opener') }}
            {% call confirm_dialog('actions.delete', 'actions.delete', 'actions.delete',
                id='modal', form='draft') %}
            <form id="modal-fields" method="post" action="/__polish__">''' + content + '''</form>
            {% endcall %}'''
    else:
        modal = '''{{ icon_button('actions.preview', type='button', id='opener',
            attrs={'data-bs-toggle':'modal', 'data-bs-target':'#modal'}) }}
            <div class="modal" id="modal" tabindex="-1" aria-labelledby="modal-title">
            <div class="modal-dialog"><div class="modal-content"><div class="modal-body">
            <h2 id="modal-title">Entwurf prüfen</h2>
            <form id="modal-fields" method="post" action="/__polish__">''' + content + '''</form>
            </div></div></div></div>'''
    markup = MACROS + '<form id="draft" method="post"></form>' + modal + TABLER

    def verify(page):
        navigations = []
        page.on('request', lambda request: navigations.append(request.url)
                if request.method != 'GET' or request.is_navigation_request() else None)
        opener = page.locator('#opener')
        modal = page.locator('#modal')
        if kind == 'native':
            opener.focus()
            modal.evaluate('el => el.showModal()')
            assert modal.evaluate('el => el.matches(":modal")')
        else:
            opener.click()
        expect(modal).to_be_visible()
        field = page.locator('#modal-note')
        field.fill('Behalten & nicht ausführen')
        before = _values(page.locator('#modal-fields'))
        foreign = page.locator('#foreign')
        foreign.hover()
        tooltip = page.get_by_role('tooltip', name=foreign.get_attribute('aria-label'), exact=True)
        expect(tooltip).to_be_visible()
        expect(field).to_be_focused()
        if focus_direct:
            foreign.focus()
            expect(foreign).to_be_focused()
            page.keyboard.press('Escape')
            expect(tooltip).to_be_hidden()
            expect(modal).to_be_visible()
            expect(foreign).to_be_focused()
        page.screenshot(path=str(tmp_path / 'modal-hover-before-escape.png'), full_page=True)
        page.keyboard.press('Escape')
        expect(modal).to_be_hidden()
        expect(tooltip).to_be_hidden()
        expect(opener).to_be_focused()
        assert _values(page.locator('#modal-fields')) == before and navigations == []
        page.screenshot(path=str(tmp_path / 'modal-after-escape.png'), full_page=True)

    _run_polish_check(markup, verify, width)


@pytest.mark.parametrize('width', [390, 1440])
def test_direct_action_preserves_owning_native_details_escape(width):
    markup = MACROS + '''<details id="owner" open><summary>Inhaltsabschnitt</summary>
        {{ more_actions([{'key':'actions.copy', 'type':'button', 'id':'copy'}]) }}
        </details>''' + OTHER + TABLER

    def verify(page):
        owner = page.locator('#owner')
        action = owner.locator('#copy')
        action.focus()
        expect(page.get_by_role('tooltip')).to_be_visible()
        action.press('Escape')
        expect(page.get_by_role('tooltip')).to_have_count(0)
        expect(owner).to_have_attribute('open', '')
        expect(action).to_be_focused()
        action.press('Escape')
        expect(owner).not_to_have_attribute('open', '')
        expect(owner.locator('summary')).to_be_focused()
        expect(page.locator('#other')).to_have_attribute('open', '')

    _run_polish_check(markup, verify, width)
