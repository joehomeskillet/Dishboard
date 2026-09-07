"""Cross-profile navigation respects the target assignment, not the source's images."""
from html.parser import HTMLParser

import pytest
from playwright.sync_api import expect

from test_admin_workflow_routes import _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_screen_template_browser import published_app, server  # noqa: F401
from test_screen_template_routes import form, screen_app  # noqa: F401
from test_screen_template_store import state

AREAS = (
    ('cafeteria', 'cafeteria', '/cafeteria/wochenangebot/', 'Patientenplan'),
    ('patienten', 'patient', '/patienten/wochenplan/', 'Cafeteria'),
)


class Links(HTMLParser):
    def __init__(self, html):
        super().__init__()
        self.hrefs = []
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        if tag == 'a':
            self.hrefs.append(dict(attrs).get('href'))


def select(client, modes):
    for (family, prefix, _, _), mode in zip(AREAS, modes, strict=True):
        if mode == 'text':
            values = form(client, family) | {'template_id': f'{prefix}-week-text'}
            assert client.post(f'/admin/screens/{family}/wochenvorlage', data=values).status_code == 303


@pytest.mark.parametrize('modes', [('photo', 'photo'), ('photo', 'text'), ('text', 'photo'), ('text', 'text')])
def test_all_assignments_and_previews_keep_canonical_and_explicit_navigation(published_app, database_engine, modes):  # noqa: F811
    client, _ = _login(published_app, database_engine, ['Cafeteria.Admin'])
    select(client, modes)
    before = state(database_engine)
    for index, (family, prefix, path, _) in enumerate(AREAS):
        other = AREAS[1 - index][2]
        for explicit in (False, True):
            response = client.get(path + ('ohne-bilder/' if explicit else ''))
            assert response.status_code == 200
            html = response.get_data(as_text=True)
            assert other + ('ohne-bilder/' if explicit else '') in Links(html).hrefs
            assert other + ('' if explicit else 'ohne-bilder/') not in Links(html).hrefs
            assert ('card-img-top' in html) == (not explicit and modes[index] == 'photo')
        for preview_mode in ('photo', 'text'):
            response = client.get(f'/admin/vorlagen/screens/{family}/{prefix}-week-{preview_mode}')
            assert response.status_code == 200 and response.headers['Cache-Control'] == 'no-store'
            html = response.get_data(as_text=True)
            assert other in Links(html).hrefs
            assert other + 'ohne-bilder/' not in Links(html).hrefs
            assert ('card-img-top' in html) == (preview_mode == 'photo')
    assert state(database_engine) == before


@pytest.mark.parametrize('width', [390, 820, 1440])
@pytest.mark.parametrize('javascript', [False, True])
@pytest.mark.parametrize('source', [0, 1])
def test_native_text_to_photo_navigation_and_explicit_variant(published_app, server, database_engine, browser, width, javascript, source, tmp_path):  # noqa: F811
    client, _ = _login(published_app, database_engine, ['Cafeteria.Admin'])
    select(client, ('text', 'photo') if source == 0 else ('photo', 'text'))
    before = state(database_engine)
    _, _, path, label = AREAS[source]
    other = AREAS[1 - source][2]
    with browser.new_context(base_url=server, viewport={'width': width, 'height': 1100},
                             java_script_enabled=javascript) as context:
        page = context.new_page()
        writes = []
        page.on('request', lambda request: writes.append(request.method) if request.method not in ('GET', 'HEAD') else None)
        for explicit in (False, True):
            assert page.goto(path + ('ohne-bilder/' if explicit else '')).status == 200
            expect(page.locator('.card-img-top')).to_have_count(0)
            link = page.get_by_role('link', name=label, exact=True)
            target = other + ('ohne-bilder/' if explicit else '')
            expect(link).to_have_attribute('href', target)
            link.focus()
            expect(link).to_be_focused()
            with page.expect_response(lambda response: response.url == server + target) as response:
                link.press('Enter')
            assert response.value.status == 200
            expect(page).to_have_url(server + target)
            assert (page.locator('.card-img-top').count() > 0) == (not explicit)
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.screenshot(path=str(tmp_path / f'navigation-{source}-{width}-{javascript}-{explicit}.png'))
        assert not writes
    assert state(database_engine) == before
