from __future__ import annotations

import datetime as dt
from copy import deepcopy
from pathlib import Path
from urllib.parse import urlsplit

import pytest
from flask import Flask, render_template, render_template_string
from playwright.sync_api import Browser, Page, Route, expect

from cafeteria.food_symbols import food_legend, food_symbol
from test_rendered_ui import PATIENT_FORBIDDEN, app, browser  # noqa: F401


def _declarations() -> dict:
    return {
        'labels': [{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
        'allergens': [
            {'code': 'MILK', 'name': 'Milch', 'presence': 'contains'},
            {'code': 'CELERY', 'name': 'Sellerie', 'presence': 'may_contain'},
        ],
        'origins': [{'ingredient': 'Kartoffel', 'country_code': 'CH', 'text': 'Kartoffel: CH'}],
        'allergen_review_status': 'not_checked',
    }


@pytest.mark.parametrize('code', [None, '', 'milk', ' MILK', 'MILK ', '../MILK', ['MILK'], 1])
def test_unknown_codes_never_guess_an_icon(code: object) -> None:
    assert food_symbol(code) is None


def test_lookup_keeps_namespaces_and_pdf_compatibility_separate() -> None:
    milk = food_symbol('MILK')
    ch = food_symbol('CH', 'countries')
    us = food_symbol('US', 'countries')
    assert milk and milk.filename == 'vendor/food-symbols/allergens/milk.svg'
    assert milk.pdf_filename == milk.filename
    assert ch and ch.name == 'Schweiz' and ch.pdf_filename == ch.filename
    assert us and us.filename.endswith('/us.svg') and us.pdf_filename is None
    assert food_symbol('CH') is None
    assert food_symbol('MILK', 'countries') is None
    vegetarian = food_symbol('VEGETARIAN', 'labels')
    vegan = food_symbol('VEGAN', 'labels')
    assert vegetarian and vegetarian.name == 'Vegetarisch' and vegetarian.filename.endswith('/labels/leaf.svg')
    assert vegan and vegan.name == 'Vegan' and vegan.filename.endswith('/labels/plant.svg')
    assert vegetarian.pdf_filename == vegetarian.filename and vegan.pdf_filename == vegan.filename
    assert food_symbol('VEGETARIAN') is None
    assert food_symbol('VEGAN', 'countries') is None
    assert food_symbol('MILK', '../../allergens') is None


def test_legend_deduplicates_codes_but_preserves_presence_and_unknown_state() -> None:
    first = _declarations()
    second = deepcopy(first)
    second['allergens'][0]['presence'] = 'may_contain'
    second['origins'][0].update(ingredient='Rind', text='Rind: CH')
    original = deepcopy([first, second])
    legend = food_legend([first, second, {}])
    assert [(item.kind, item.code, item.presence) for item in legend.entries] == [
        ('allergens', 'MILK', 'contains'), ('allergens', 'MILK', 'may_contain'),
        ('allergens', 'CELERY', 'may_contain'),
        ('countries', 'CH', ''), ('labels', 'VEGETARIAN', ''),
    ]
    assert food_legend([{}, second, first]) == legend
    assert legend.allergens_unknown and legend.review_open
    assert [first, second] == original
    assert food_legend([]).entries == ()
    assert not food_legend([]).allergens_unknown
    assert not food_legend([{**first, 'allergen_review_status': 'checked'}]).review_open
    assert food_legend([{'allergens': [], 'allergen_review_status': 'checked'}]).allergens_unknown


@pytest.mark.parametrize('code', [None, '', 'VEGGIE', 'VEG', 'VGN', 'vegan', ' VEGAN',
                                  'VEGAN ', 'LACTOSE_FREE', 'GLUTEN_FREE', 'MILK', '../VEGAN'])
def test_label_symbols_require_exact_supported_declarations(code: object) -> None:
    assert food_symbol(code, 'labels') is None


@pytest.mark.parametrize(('labels', 'files'), [
    ([], []),
    ([{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}], ['leaf.svg']),
    ([{'code': 'VEGAN', 'name': 'Vegan'}], ['plant.svg']),
    ([{'code': 'CUSTOM', 'name': 'Eigenes Label'},
      {'code': 'GLUTEN_FREE', 'name': 'Glutenfrei'},
      {'code': 'LACTOSE_FREE', 'name': 'Laktosefrei'}], []),
])
def test_metadata_and_legend_never_infer_diet_from_slot_or_food_text(app, labels, files):  # noqa: F811
    option = {'title': 'Vegane vegetarische Gemüsepfanne', 'type_code': 'VEGGIE',
              'components': ['Pflanzlich'], 'labels': labels, 'allergens': [], 'origins': []}
    original = deepcopy(option)
    entries = food_legend([option]).entries
    assert [entry.symbol.filename.rsplit('/', 1)[-1] for entry in entries if entry.symbol] == files
    with app.test_request_context():
        metadata = render_template('_menu_metadata.html', option=option)
        legend = render_template_string("{% from '_food_symbols.html' import legend %}{{ legend(options) }}",
                                        options=[option])
    for body in (metadata, legend):
        assert body.count('<img') == len(files)
        assert all(f'/labels/{file}' in body for file in files)
        assert all(label['name'] in body for label in labels)
        assert 'Allergenangaben nicht erfasst' in body
    assert option == original


def test_unknown_declarations_keep_text_and_are_not_normalized_into_contains() -> None:
    legend = food_legend([{
        'allergens': [{'code': 'CUSTOM', 'name': 'Spezialangabe', 'presence': 'unknown'}],
        'origins': [{'country_code': 'ZZ', 'ingredient': 'Rind', 'text': 'Rind: ZZ'}],
        'labels': [{'code': 'CUSTOM', 'name': 'Eigenes Label'}],
    }])
    assert [(row.kind, row.code, row.name, row.presence, row.symbol) for row in legend.entries] == [
        ('allergens', 'CUSTOM', 'Spezialangabe', 'unknown', None),
        ('countries', 'ZZ', 'ZZ', '', None),
        ('labels', 'CUSTOM', 'Eigenes Label', '', None),
    ]


def test_shared_macros_escape_text_and_do_not_infer_codes(app: Flask) -> None:  # noqa: F811
    option = {
        **_declarations(),
        'origins': [{'country_code': 'ZZ', 'ingredient': 'Rind', 'text': 'Rind <CH>: Schweiz'}],
        'allergens': [{'code': 'CUSTOM', 'name': '<Milch>', 'presence': 'unknown'}],
    }
    with app.test_request_context():
        body = render_template('_menu_metadata.html', option=option)
        assert 'Rind &lt;CH&gt;: Schweiz' in body
        assert 'Allergenangabe ungeklärt: &lt;Milch&gt;' in body
        assert 'Enthält:' not in body and '/allergens/' not in body and '/flags/' not in body
        assert body.count('/labels/leaf.svg') == 1
        assert 'Vegetarisch' in body and 'Allergenprüfung offen' in body
        legend = render_template_string(
            "{% from '_food_symbols.html' import legend %}{{ legend(options) }}",
            options=[_declarations(), _declarations(), {}],
        )
        assert legend.count('Enthält: Milch') == 1
        assert legend.count('Kann enthalten: Sellerie') == 1
        assert legend.count('Schweiz') == 1
        assert legend.count('Vegetarisch') == 1
        assert 'Allergenangaben nicht erfasst' in legend
        assert 'Allergenprüfung offen' in legend
        assert legend.count('class="food-symbol') == 4


def _load_page(application: Flask, chromium: Browser, html: str, width: int) -> Page:
    client = application.test_client()
    page = chromium.new_page(viewport={'width': width, 'height': 1100})

    def serve(route: Route) -> None:
        path = urlsplit(route.request.url).path
        if path == '/symbol-test':
            route.fulfill(status=200, content_type='text/html', body=html)
        else:
            response = client.get(path)
            route.fulfill(status=response.status_code, headers=dict(response.headers), body=response.data)

    page.route('http://dishboard.test/**', serve)
    page.goto('http://dishboard.test/symbol-test', wait_until='networkidle')
    return page


def _assert_visible_symbols(page: Page) -> None:
    card = page.locator('[data-menu-metadata]').first
    icons = card.locator('img.food-symbol')
    expect(icons).to_have_count(4)
    assert icons.evaluate_all('els => els.every(el => el.complete && el.naturalWidth > 0)')
    assert sorted(icons.evaluate_all("els => els.map(el => el.getAttribute('src'))")) == [
        '/static/vendor/food-symbols/allergens/celery.svg',
        '/static/vendor/food-symbols/allergens/milk.svg',
        '/static/vendor/food-symbols/flags/ch.svg',
        '/static/vendor/food-symbols/labels/leaf.svg',
    ]
    for icon in icons.all():
        expect(icon).to_be_visible()
        expect(icon).to_have_attribute('alt', '')
        expect(icon).to_have_attribute('aria-hidden', 'true')
    assert sorted(card.locator('.label').all_text_contents()) == sorted([
        'Kartoffel: CH', 'Vegetarisch', 'Enthält: Milch', 'Kann enthalten: Sellerie',
    ])
    expect(card).to_contain_text('Allergenprüfung offen')
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    assert card.locator('.label').evaluate_all('els => els.every(el => el.scrollWidth <= el.clientWidth + 1)')


@pytest.mark.parametrize('profile,path', [
    ('staff_guest', '/cafeteria/heute/'), ('staff_guest', '/cafeteria/wochenangebot/'),
    ('patient', '/patienten/heute/'), ('patient', '/patienten/wochenplan/'),
])
@pytest.mark.parametrize('width', [390, 820, 1440])
def test_public_cards_load_real_local_symbols_without_changing_snapshot(
    app: Flask, browser: Browser, profile: str, path: str, width: int,  # noqa: F811
) -> None:
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    app.config['DEMO_TODAY'] = snapshot['days'][0]['date']
    snapshot['days'][0]['services'][0]['options'][0].update(_declarations())
    original = deepcopy(snapshot)
    response = app.test_client().get(path)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert body.count('href="/static/food-symbols.css"') == 1
    if profile == 'patient':
        assert PATIENT_FORBIDDEN.search(body) is None
    page = _load_page(app, browser, body, width)
    try:
        _assert_visible_symbols(page)
    finally:
        page.close()
    assert snapshot == original


@pytest.mark.parametrize('profile,family', [('staff_guest', 'cafeteria'), ('patient', 'patienten')])
@pytest.mark.parametrize('template', ['admin/menu_collection.html', 'admin/preview.html'])
@pytest.mark.parametrize('width', [390, 820, 1440])
def test_admin_cards_load_real_local_symbols(
    app: Flask, browser: Browser, profile: str, family: str, template: str, width: int,  # noqa: F811
    tmp_path: Path,
) -> None:
    option = deepcopy(app.config['TEST_SNAPSHOTS'][profile]['days'][0]['services'][0]['options'][0])
    date = dt.date(2026, 8, 31)
    row = {**option, **_declarations(), 'id': 77, 'service_date': date, 'week_start': date,
           'meal_code': 'LUNCH', 'workflow_state': 'draft'}
    context = {
        'profile': profile, 'family': family, 'query': '', 'page': 1, 'has_next': False,
        'area_names': {'patient': 'Patientinnen und Patienten',
                       'staff_guest': 'Mitarbeitende und externe Gäste'},
        'roles': [], 'rows': [row], 'meal_labels': {'LUNCH': 'Mittag'},
        'option_labels': {'MENU_1': 'Menü 1'}, 'state': 'draft', 'week': date,
        'week_iso': date.isoformat(), 'draft': {'title': '', 'shared_note': '', 'days': [
            {'date': date.isoformat(), 'services': [
                {'meal_code': 'LUNCH', 'service_state': 'open', 'options': [row]},
            ]},
        ]},
    }
    with app.test_request_context():
        body = render_template(template, **context)
    preview = template.endswith('preview.html')
    assert body.count('href="/static/food-symbols.css"') == int(preview)
    if profile == 'patient':
        assert PATIENT_FORBIDDEN.search(body) is None
    page = _load_page(app, browser, body, width)
    try:
        _assert_visible_symbols(page)
        if not preview:
            expect(page.locator('[data-menu-metadata] .badge')).to_have_count(4)
            expect(page.locator('[data-menu-metadata] img.icon')).to_have_count(4)
        if profile == 'patient' and width in (390, 1440):
            page.screenshot(path=str(tmp_path / f'patient-{Path(template).stem}-{width}.png'), full_page=True)
    finally:
        page.close()


@pytest.mark.parametrize('width', [390, 820, 1440])
def test_both_declared_diets_load_distinct_symbols_and_full_names_in_browser(
    app: Flask, browser: Browser, width: int, tmp_path: Path,  # noqa: F811
) -> None:
    snapshot = app.config['TEST_SNAPSHOTS']['patient']
    app.config['DEMO_TODAY'] = snapshot['days'][0]['date']
    option = snapshot['days'][0]['services'][0]['options'][0]
    option.update(_declarations())
    option['labels'] = [{'code': 'VEGETARIAN', 'name': 'Vegetarisch'},
                        {'code': 'VEGAN', 'name': 'Vegan'},
                        {'code': 'LACTOSE_FREE', 'name': 'Laktosefrei'},
                        {'code': 'CUSTOM', 'name': 'Eigene Kostform'}]
    original = deepcopy(snapshot)
    html = app.test_client().get('/patienten/heute/').get_data(as_text=True)
    page = _load_page(app, browser, html, width)
    try:
        card = page.locator('[data-menu-metadata]').first
        icons = card.locator('img[src*="/labels/"]')
        expect(icons).to_have_count(2)
        assert icons.evaluate_all('els => els.every(el => el.complete && el.naturalWidth === 24)')
        for name in ('Vegetarisch', 'Vegan', 'Laktosefrei', 'Eigene Kostform'):
            expect(card).to_contain_text(name)
        assert sorted(icons.evaluate_all('els => els.map(el => el.src.split("/").pop())')) == ['leaf.svg', 'plant.svg']
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        assert card.locator('.label').evaluate_all('els => els.every(el => el.scrollWidth <= el.clientWidth + 1)')
        page.screenshot(path=str(tmp_path / f'declared-diets-{width}.png'), full_page=True)
    finally:
        page.close()
    assert snapshot == original
