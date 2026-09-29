"""Empty stacked cells disappear without losing mixed statuses or desktop columns."""
import pytest
from playwright.sync_api import expect

from test_recipe_images_browser import recipe_server  # noqa: F401
from test_recipe_revision_routes import (  # noqa: F401
    a3, app_engine, b3, complete_a3, installed_pg16, pg16, seeded_pg16,
)
from test_recipe_routes import create, fields
from test_recipe_store_db import snapshot
from test_rendered_ui import browser  # noqa: F401


@pytest.mark.parametrize('touch', [False, True], ids=['fine', 'coarse'])
@pytest.mark.parametrize('width,height', [(390, 844), (1440, 900)])
def test_recipe_stack_hides_only_empty_cells(
    a3, recipe_server, browser, tmp_path, touch, width, height,  # noqa: F811
):
    complete_a3(a3)
    _, owner, client, _, _ = a3
    archived_path = create(client, title='Archivierte Suppe')
    status_path = archived_path + '/status'
    assert client.post(status_path, data=fields(client, status_path)).status_code == 303
    before = snapshot(owner)
    base, cookie = recipe_server
    with browser.new_context(
        viewport={'width': width, 'height': height}, has_touch=touch,
        reduced_motion='reduce', service_workers='block', locale='de-CH',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        errors = []
        for query, statuses in (('?archived=1', {'Suppe': 'Entwurf', 'Archivierte Suppe': 'Archiviert'}),
                                ('', {'Suppe': ''})):
            page = context.new_page()
            page.on('pageerror', lambda error: errors.append(str(error)))
            response = page.goto(base + '/admin/rezepte' + query, wait_until='networkidle')
            assert response is not None and response.status == 200
            page.evaluate('document.fonts.ready')
            assert page.evaluate('matchMedia("(pointer: coarse)").matches') == touch
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            table = page.locator('table.recipe-list')
            rows = table.locator('tbody tr.recipe-row')
            expect(rows).to_have_count(len(statuses))
            headers = table.locator('thead th')
            expect(headers).to_have_text(['Name', 'Ausbeute', 'Zustand', 'Aktionen'])
            if width == 1440:
                expect(table).to_have_css('display', 'table')
                expect(headers.nth(2)).to_be_visible()
            for title, status in statuses.items():
                row = rows.filter(has=page.get_by_text(title, exact=True))
                cells = row.locator(':scope > :is(th, td)')
                expect(cells).to_have_count(4)
                cell = row.locator('[data-label="Zustand"]')
                expect(cell).to_have_text(status)
                for label in ('Name', 'Ausbeute', 'Aktionen'):
                    expect(row.locator(f'[data-label="{label}"]')).to_be_visible()
                if not status:
                    assert cell.evaluate('element => element.matches(":empty")')
                    assert cell.evaluate('element => element.childNodes.length') == 0
                if width == 390:
                    if status:
                        expect(cell).to_be_visible()
                        expect(cell).to_have_css('display', 'block')
                        assert cell.evaluate('element => getComputedStyle(element, "::before").content') == '"Zustand"'
                        assert cell.evaluate('element => getComputedStyle(element, "::before").display') == 'block'
                    else:
                        expect(cell).to_be_hidden()
                        expect(cell).to_have_css('display', 'none')
                        assert cell.bounding_box() is None
                else:
                    expect(cell).to_be_visible()
                    assert cell.evaluate('element => getComputedStyle(element, "::before").content') == 'none'
                    for index, column in enumerate(cells.all()):
                        expect(column).to_have_css('display', 'table-cell')
                        box, heading = column.bounding_box(), headers.nth(index).bounding_box()
                        assert box is not None and heading is not None
                        assert abs(box['x'] - heading['x']) < 1
                        assert abs(box['width'] - heading['width']) < 1
            page.screenshot(path=str(tmp_path / ('mixed.png' if query else 'active.png')), full_page=True)
            page.close()
        assert not errors
    assert snapshot(owner) == before
