from __future__ import annotations

import re
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from flask import Flask, url_for
from playwright.sync_api import Locator, Page, expect

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, catalog_component, live_server, page_context,
)
from test_admin_workflow_routes import DAY


def _assert_brand_contained(sidebar: Locator) -> None:
    sidebar_box = sidebar.bounding_box()
    brand = sidebar.locator('.admin-brand')
    brand_box = brand.bounding_box()
    assert sidebar_box is not None and brand_box is not None
    boxes = [
        (brand_box, sidebar_box),
        (brand.locator('img').bounding_box(), brand_box),
        (brand.locator('span').bounding_box(), brand_box),
    ]
    for box, bounds in boxes:
        assert box is not None
        assert box['width'] > 0 and box['height'] > 0
        assert box['x'] >= bounds['x'] - 1
        assert box['x'] + box['width'] <= bounds['x'] + bounds['width'] + 1
        assert box['y'] >= bounds['y'] - 1
        assert box['y'] + box['height'] <= bounds['y'] + bounds['height'] + 1


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize('page_kind', ('editor', 'catalog', 'detail'))
@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 1100)))
def test_workflow_shell_has_navigation_readable_main_and_native_targets(
    page_context: Page, catalog_component: tuple, tmp_path: Path, admin_app: Flask,  # noqa: F811
    family: str, page_kind: str, width: int, height: int,
) -> None:
    page = page_context
    component, _ = catalog_component
    routes = {
        'editor': f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1',
        'catalog': f'/admin/{family}/komponenten',
        'detail': f'/admin/{family}/komponenten/{component["public_id"]}',
    }
    page.set_viewport_size({'width': width, 'height': height})
    response = page.goto(routes[page_kind])
    assert response is not None and response.status == 200

    # Migrated Tabler pages use `.page`; legacy workflow pages keep `.admin-workflow-shell`.
    shell = '.page' if page.locator('body.dishboard-admin > .page').count() else '.admin-workflow-shell'
    sidebar = page.locator(f'{shell} > aside.admin-sidebar')
    main = page.locator(f'{shell} > main#main-content')
    expect(sidebar).to_be_visible()
    expect(main).to_be_visible()
    _assert_brand_contained(sidebar)
    expect(main).to_have_attribute('data-family', family)
    expect(main).to_have_attribute('data-profile', 'patient' if family == 'patienten' else 'staff_guest')

    sidebar_box, main_box = sidebar.bounding_box(), main.bounding_box()
    assert sidebar_box is not None and main_box is not None
    if width >= 1000:
        assert main_box['x'] >= sidebar_box['x'] + sidebar_box['width'] - 1
        assert main_box['width'] >= width * 0.65
    else:
        assert main_box['y'] >= sidebar_box['y'] + sidebar_box['height'] - 1
        assert main_box['width'] >= width - 2
    assert main_box['x'] + main_box['width'] <= width + 1
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert main.evaluate('(element) => element.scrollWidth <= element.clientWidth + 1')

    navigation = sidebar.get_by_role('navigation', name='Backend')
    weeks = navigation.get_by_role('link', name='Wochenpläne')
    catalog = navigation.get_by_role('link', name='Komponenten', exact=True)
    week_href = weeks.get_attribute('href')
    assert week_href is not None
    week_url = urlsplit(week_href)
    assert week_url.path == f'/admin/{family}'
    assert parse_qs(week_url.query) == ({'week': [DAY]} if page_kind == 'editor' else {})
    expect(catalog).to_have_attribute('href', f'/admin/{family}/komponenten')
    expect(navigation.locator('[aria-current="page"]')).to_have_text(
        'Wochenpläne' if page_kind == 'editor' else 'Komponenten',
    )

    logout = navigation.locator('form')
    with admin_app.test_request_context():
        logout_url = url_for('auth.logout')
    expect(logout).to_have_attribute('method', 'post')
    expect(logout).to_have_attribute('action', logout_url)
    assert logout.locator('input[name="_csrf"]').input_value()
    assert main.locator(f'form[action="{logout_url}"]').count() == 0
    assert page.locator('[onclick], [onsubmit], [style], script:not([src])').count() == 0

    small_targets = page.locator(
        f'{shell} .admin-nav a, {shell} .admin-nav button, '
        'main#main-content input:not([type="hidden"]), '
        'main#main-content select, main#main-content textarea, '
        'main#main-content button, main#main-content a.btn, '
        'main#main-content summary, main#main-content .component-row > a',
    ).evaluate_all('''elements => elements.flatMap(element => {
        const rect = element.getBoundingClientRect();
        if (!rect.width || !rect.height) return [];
        const check = element.matches('input[type="checkbox"], input[type="radio"]');
        const target = check ? element.closest('label') || element.labels[0] : element;
        if (!target) return [{name: element.name, reason: 'missing label target'}];
        const box = target.getBoundingClientRect();
        return box.width >= 44 && box.height >= 44 ? [] : [{
            name: element.name || element.textContent.trim(),
            width: box.width, height: box.height,
        }];
    })''')
    assert small_targets == []

    if page_kind == 'editor':
        heading = main.get_by_role('heading', level=1)
        assert DAY not in heading.inner_text()
        expect(heading).to_contain_text('Mittag')
        expect(heading).to_contain_text('Menü 1')
        assert not re.search(r'LUNCH|MENU_1', heading.inner_text())
        form = main.locator('form[data-menu-editor]')
        expect(form).to_have_attribute('method', 'post')
        expect(form).to_have_attribute('action', f'/admin/{family}/menu')
        expect(form.locator('[name="week"]')).to_have_value(DAY)
        expect(form.locator('[name="day"]')).to_have_value(DAY)
        expect(form.locator('[name="meal"]')).to_have_value('LUNCH')
        expect(form.locator('[name="option"]')).to_have_value('MENU_1')
        assert form.locator('[name="_csrf"]').input_value()
        primary = form.get_by_role('button', name='Speichern', exact=True)
    elif page_kind == 'catalog':
        creation = main.locator('#create-component')
        primary = creation.locator('summary')
        assert creation.get_attribute('open') is None
        create_box, filter_box = creation.bounding_box(), main.locator('.search-form').bounding_box()
        assert create_box is not None and filter_box is not None
        assert create_box['y'] + create_box['height'] <= filter_box['y'] + 1
        row = main.locator('.component-list-container .component-row').first
        link_box, category_box = row.locator('a').bounding_box(), row.locator('.category').bounding_box()
        assert link_box is not None and category_box is not None
        if width >= 1000:
            assert category_box['x'] >= link_box['x'] + link_box['width']
        else:
            assert category_box['y'] >= link_box['y'] + link_box['height']
    elif page_kind == 'detail':
        expect(main).to_have_attribute('data-public-id', str(component['public_id']))
        expect(main.locator('[name="name"]')).to_have_value(component['name'])
        primary = main.get_by_role('button', name='Speichern', exact=True)
        for control_id in ('c-name', 'c-cat', 'c-origin'):
            label_box = main.locator(f'label[for="{control_id}"]').bounding_box()
            control_box = main.locator(f'#{control_id}').bounding_box()
            assert label_box is not None and control_box is not None
            assert control_box['y'] >= label_box['y'] + label_box['height'] - 1
            assert abs(control_box['x'] - label_box['x']) <= 1
        first_allergen = main.locator('.allergen-row').first
        label_box = first_allergen.locator('label').bounding_box()
        select_box = first_allergen.locator('select').bounding_box()
        assert label_box is not None and select_box is not None
        if width >= 1000:
            assert select_box['x'] >= label_box['x'] + label_box['width']
        else:
            assert select_box['y'] >= label_box['y'] + label_box['height']

    expect(primary).to_have_class(re.compile(r'\bprimary\b'))
    primary_box = primary.bounding_box()
    assert primary_box is not None
    assert 0 <= primary_box['y'] < primary_box['y'] + primary_box['height'] <= height

    if family == 'patienten':
        assert not re.search(r'preis|chf|rappen|kosten|price', page.content(), re.IGNORECASE)

    page.keyboard.press('Tab')
    skip = page.get_by_role('link', name='Zum Inhalt springen')
    expect(skip).to_be_focused()
    expect(skip).to_have_attribute('href', '#main-content')
    page.keyboard.press('Tab')
    expect(weeks).to_be_focused()
    assert weeks.evaluate('''element => {
        const style = getComputedStyle(element);
        return style.outlineStyle !== 'none' && parseFloat(style.outlineWidth) > 0;
    }''')
    page.screenshot(path=str(tmp_path / f'{family}-{page_kind}-{width}.png'), full_page=True)

    weeks.click()
    page.wait_for_url(f'**{week_href}')
    expect(page.locator('main#main-content')).to_have_attribute('data-family', family)


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 1100)))
def test_overview_brand_stays_inside_sidebar(
    page_context: Page, family: str, width: int, height: int,  # noqa: F811
) -> None:
    page_context.set_viewport_size({'width': width, 'height': height})
    response = page_context.goto(f'/admin/{family}?week={DAY}')
    assert response is not None and response.status == 200
    _assert_brand_contained(page_context.locator('.admin-shell > aside.admin-sidebar'))
