from __future__ import annotations

import base64
import datetime as dt
import re
import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from flask import Blueprint, Flask
from playwright.sync_api import Browser, sync_playwright

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

from cafeteria.admin import routes as admin_routes  # noqa: E402
from cafeteria.public import routes as public_routes  # noqa: E402
from cafeteria.security import csrf_token  # noqa: E402
from cafeteria.signage import routes as signage_routes  # noqa: E402
from demo_snapshots import cafeteria_snapshot, patient_snapshot  # noqa: E402
import cafeteria.roles  # noqa: E402

CSS_PATH = ROOT / 'reference_scaffold' / 'cafeteria' / 'static' / 'app.css'
STATIC_IMG_PATH = ROOT / 'reference_scaffold' / 'cafeteria' / 'static' / 'img'
PATIENT_FORBIDDEN = re.compile(
    r'\b(?:CHF|Rappen|Intern|Extern|0\.00|price|prices|pricing|preis|preise|currency)\b'
    r'|(?:internal|external)_rappen|price-row|signage-price|admin-price',
    re.IGNORECASE,
)



def _fixture_master_data() -> tuple[list[dict], list[dict]]:
    """Return realistic fixture labels and allergens for UI testing."""
    labels = [
        {'code': 'vegan', 'display_name': 'Vegan'},
        {'code': 'vegetarian', 'display_name': 'Vegetarisch'},
        {'code': 'gluten_free', 'display_name': 'Glutenfrei'},
        {'code': 'lactose_free', 'display_name': 'Laktosefrei'},
    ]
    allergens = [
        {'code': 'gluten', 'display_name': 'Gluten', 'eu_number': '1', 'presence': 'contains'},
        {'code': 'milk', 'display_name': 'Milch', 'eu_number': '7', 'presence': 'contains'},
        {'code': 'eggs', 'display_name': 'Eier', 'eu_number': '3', 'presence': 'contains'},
        {'code': 'nuts', 'display_name': 'Nüsse', 'eu_number': '8', 'presence': 'contains'},
        {'code': 'soy', 'display_name': 'Soja', 'eu_number': '11', 'presence': 'contains'},
    ]
    return labels, allergens

def _draft(snapshot: dict[str, Any], profile_code: str) -> dict[str, Any]:
    draft = deepcopy(snapshot)
    if profile_code == 'staff_guest':
        draft['days'] = draft['days'][:5]
    draft['row_version'] = 1
    draft['shared_note'] = ''
    for day in draft['days']:
        for meal in day['services']:
            meal.setdefault('notice', '')
            for option in meal['options']:
                if profile_code == 'staff_guest':
                    option['internal_rappen'] = option['prices']['internal_rappen']
                    option['external_rappen'] = option['prices']['external_rappen']
    return draft


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    application = Flask(
        'rendered-ui',
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
        static_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'static'),
    )
    application.config.update(
        TESTING=True,
        SECRET_KEY='rendered-ui-tests',
        DEMO_MODE=True,
        DEMO_TODAY='2026-09-02',
        LAST_GOOD_DIR=str(ROOT / '.test-last-good'),
    )
    application.extensions['cafeteria_db'] = object()
    application.add_template_filter(lambda value: value, 'date_long')
    application.add_template_filter(lambda value: value, 'date_short')
    application.add_template_filter(lambda value: f'{int(value) / 100:.2f}', 'chf')
    application.add_template_filter(lambda _value: 36, 'iso_week')

    auth = Blueprint('auth', __name__)
    auth.add_url_rule('/logout', endpoint='logout', view_func=lambda: '')
    # Add local_login route for testing
    def mock_local_login():
        from flask import render_template
        return render_template('auth/local_login.html')
    auth.add_url_rule('/local', endpoint='local_login', view_func=mock_local_login, methods=['GET'])
    application.register_blueprint(auth, url_prefix='/auth')
    application.register_blueprint(public_routes.bp)
    application.register_blueprint(signage_routes.bp)
    application.register_blueprint(admin_routes.bp)

    snapshots = {
        'staff_guest': cafeteria_snapshot(),
        'patient': patient_snapshot(),
    }
    application.config['TEST_SNAPSHOTS'] = snapshots

    def fake_active_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict[str, Any]:
        return deepcopy(snapshots[profile_code])

    def fake_draft(profile_code: str) -> dict[str, Any]:
        return _draft(snapshots[profile_code], profile_code)

    # Mock load_user_authorization to return authorized user without DB
    class MockAuthorization:
        def __init__(self):
            self.authz_version = 1
            self.roles = ['Cafeteria.Admin']

    def mock_load_user_authorization(db_engine, user_id):
        return MockAuthorization()

    monkeypatch.setattr(cafeteria.roles, 'load_user_authorization', mock_load_user_authorization)
    monkeypatch.setattr(public_routes, 'active_snapshot', fake_active_snapshot)
    monkeypatch.setattr(admin_routes, '_draft', fake_draft)
    monkeypatch.setattr(admin_routes, '_master_data', _fixture_master_data)

    @application.context_processor
    def inject_csrf() -> dict[str, object]:
        return {'csrf_token': csrf_token}

    return application


@pytest.fixture(scope='module')
def browser() -> Browser:
    with sync_playwright() as playwright:
        browser_instance = playwright.chromium.launch(
            headless=True,
            args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        try:
            yield browser_instance
        finally:
            browser_instance.close()


def _client(app: Flask):
    client = app.test_client()
    with client.session_transaction() as current:
        current['user'] = {'id': 1, 'name': 'Küche'}
        current['authz_version'] = 1
        current['_csrf_token'] = 'rendered-ui-csrf'
    return client


def _inline_css(html: str) -> str:
    css = CSS_PATH.read_text(encoding='utf-8')
    inlined = re.sub(r'<link rel="stylesheet"[^>]+>', f'<style>{css}</style>', html, count=1)
    for filename in ('suedhang-logo.png', 'suedhang-logo@2x.png'):
        image_data = base64.b64encode((STATIC_IMG_PATH / filename).read_bytes()).decode('ascii')
        inlined = inlined.replace(f'/static/img/{filename}', f'data:image/png;base64,{image_data}')
    return inlined


def _page(browser: Browser, html: str, width: int, height: int):
    page = browser.new_page(viewport={'width': width, 'height': height})
    page.set_content(_inline_css(html), wait_until='load')
    page.emulate_media(reduced_motion='reduce')
    return page


def _assert_no_viewport_overflow(page, selectors: tuple[str, ...]) -> None:
    result = page.evaluate(
        """
        selectors => {
          const overflow = element =>
            element.scrollWidth > element.clientWidth + 1 ||
            element.scrollHeight > element.clientHeight + 1;
          return {
            viewport: document.documentElement.scrollWidth <= innerWidth + 1,
            documentHeight: document.documentElement.scrollHeight <= innerHeight + 1,
            clipped: selectors.flatMap(selector =>
              [...document.querySelectorAll(selector)]
                .filter(overflow)
                .map(element =>
                  `${selector}:${element.scrollWidth}/${element.clientWidth}:` +
                  `${element.scrollHeight}/${element.clientHeight}:` +
                  element.textContent.trim().slice(0, 30)
                )
            ),
          };
        }
        """,
        selectors,
    )
    assert result == {'viewport': True, 'documentHeight': True, 'clipped': []}


def _bounded_text(length: int) -> str:
    value = ('Kartoffel Gemüse Kräuter ' * 10)[:length]
    return f'{value[:-1]}x' if value.endswith(' ') else value


def _set_signage_boundaries(
    snapshot: dict[str, Any],
    *,
    title_length: int,
    component_length: int,
    description_length: int | None = None,
) -> None:
    for day in snapshot['days']:
        for meal in day['services']:
            for option in meal['options']:
                option['title'] = _bounded_text(title_length)
                option['components'] = [_bounded_text(component_length)]
                if description_length is not None:
                    option['description'] = _bounded_text(description_length)


def _set_unbroken_signage_boundaries(
    snapshot: dict[str, Any],
    *,
    title_length: int,
    component_length: int,
) -> tuple[str, str]:
    title = 'W' * title_length
    component = 'W' * component_length
    for day in snapshot['days']:
        for meal in day['services']:
            for option in meal['options']:
                option['title'] = title
                option['components'] = [component]
                if 'description' in option:
                    option['description'] = component
    return title, component


def test_css_rgba_colors_outside_root_use_design_tokens() -> None:
    css = CSS_PATH.read_text(encoding='utf-8')
    root_block = re.search(r':root\s*\{.*?\}', css, re.DOTALL)

    assert root_block is not None
    outside_root = css[: root_block.start()] + css[root_block.end() :]
    rgba_violations = [line.strip() for line in outside_root.splitlines() if 'rgba(' in line]
    hex_violations = [
        line.strip()
        for line in outside_root.splitlines()
        if re.search(r'#[0-9a-fA-F]{3,8}\b', line)
    ]
    assert rgba_violations == []
    assert hex_violations == []


def test_documented_header_contrast_ratios_remain_wcag_aa() -> None:
    css = CSS_PATH.read_text(encoding='utf-8')

    assert '--sh-magenta: #8C1C4B;' in css
    assert '--sh-green: #3E6B44;' in css
    manual_ratios = {'magenta': 7.38, 'green': 5.35}

    assert all(ratio >= 4.5 for ratio in manual_ratios.values())


def test_public_headers_keep_navigation_left_and_logo_right(app: Flask, browser: Browser) -> None:
    client = _client(app)
    paths = (
        '/cafeteria/heute/',
        '/cafeteria/wochenangebot/',
        '/patienten/heute/',
        '/patienten/wochenplan/',
    )
    for path in paths:
        html = client.get(path).get_data(as_text=True)
        assert html.index('class="site-nav"') < html.index('class="site-logo"')

        for width in (390, 1440):
            page = _page(browser, html, width, 900)
            try:
                positions = page.evaluate(
                    """
                    () => {
                      const nav = document.querySelector('.site-nav').getBoundingClientRect();
                      const logo = document.querySelector('.site-logo').getBoundingClientRect();
                      return {
                        navLeft: Math.round(nav.left),
                        navRight: Math.round(nav.right),
                        logoLeft: Math.round(logo.left),
                        logoRight: Math.round(logo.right),
                      };
                    }
                    """
                )
                assert positions['navLeft'] < positions['logoLeft']
                assert positions['navRight'] <= positions['logoLeft']
                assert positions['logoRight'] <= width + 1
                logo_state = page.locator('.site-logo-img').evaluate(
                    "element => ({ complete: element.complete, naturalWidth: element.naturalWidth, naturalHeight: element.naturalHeight })"
                )
                assert logo_state['complete']
                assert logo_state['naturalWidth'] > 0
                assert logo_state['naturalHeight'] > 0
            finally:
                page.close()


@pytest.mark.parametrize(
    'path',
    ('/static/img/suedhang-logo.png', '/static/img/suedhang-logo@2x.png'),
)
def test_logo_assets_are_served_as_nonempty_pngs(app: Flask, path: str) -> None:
    response = app.test_client().get(path)

    assert response.status_code == 200
    assert response.content_type == 'image/png'
    assert response.data


def test_public_patient_week_title_uses_date_range_and_no_profile_banners(app: Flask) -> None:
    client = _client(app)
    html = client.get('/patienten/wochenplan/').get_data(as_text=True)

    assert '<h1>2026-08-31 bis 2026-09-06</h1>' in html
    for path in (
        '/cafeteria/heute/',
        '/cafeteria/wochenangebot/',
        '/patienten/heute/',
        '/patienten/wochenplan/',
    ):
        assert 'profile-banner' not in client.get(path).get_data(as_text=True)


@pytest.mark.parametrize('path', ('/admin/cafeteria', '/admin/patienten'))
def test_admin_review_checkboxes_rehydrate_canonical_checked_status(
    app: Flask,
    path: str,
) -> None:
    html = _client(app).get(path).get_data(as_text=True)
    review_inputs = re.findall(
        r'<input type="checkbox" name="[^"]+_allergen_reviewed"([^>]*)>',
        html,
    )

    assert review_inputs
    assert all(re.search(r'\bchecked\b', attributes) for attributes in review_inputs)


@pytest.mark.parametrize(
    ('path', 'expected_pills'),
    (
        (
            '/cafeteria/heute/',
            {'Einmalig Vegan', 'Enthält: Einmalig Gluten', 'Einmalig Rind: Schweiz'},
        ),
        (
            '/patienten/heute/',
            {'Einmalig Vegan', 'Enthält: Einmalig Gluten', 'Einmalig Rind: Schweiz'},
        ),
        (
            '/signage/patienten/tag',
            {'Einmalig Vegan', 'Einmalig Gluten', 'Einmalig Rind: Schweiz'},
        ),
    ),
)
def test_today_channels_render_each_menu_metadata_pill_once(
    app: Flask,
    path: str,
    expected_pills: set[str],
) -> None:
    for snapshot in app.config['TEST_SNAPSHOTS'].values():
        for day in snapshot['days']:
            for meal in day['services']:
                for option in meal['options']:
                    option['labels'] = []
                    option['allergens'] = []
                    option['origins'] = []

        today = next(day for day in snapshot['days'] if day['date'] == '2026-09-02')
        option = today['services'][0]['options'][0]
        option['labels'] = [{'code': 'UNIQUE_LABEL', 'name': 'Einmalig Vegan'}]
        option['allergens'] = [
            {'code': 'UNIQUE_ALLERGEN', 'name': 'Einmalig Gluten', 'presence': 'contains'},
        ]
        option['origins'] = [
            {
                'ingredient': 'Einmalig Rind',
                'country_code': 'CH',
                'text': 'Einmalig Rind: Schweiz',
            },
        ]

    html = _client(app).get(path).get_data(as_text=True)
    pills = {
        value.strip()
        for value in re.findall(r'<span class="label(?: [^"]*)?">([^<]*)</span>', html)
    }

    assert len(re.findall(r'<span class="label(?: [^"]*)?">', html)) == 3
    assert pills == expected_pills


def test_real_routes_render_exact_profile_grids_without_cross_profile_data(app: Flask) -> None:
    client = _client(app)
    cafeteria = client.get('/signage/cafeteria/woche').get_data(as_text=True)
    patient = client.get('/signage/patienten/woche').get_data(as_text=True)

    assert len(re.findall(r'class="cafe-week-day"', cafeteria)) == 5
    assert len(re.findall(r'class="cafe-week-slot(?: [^"]*)?"', cafeteria)) == 10
    assert cafeteria.count('Mitarbeitende CHF') == 10
    assert cafeteria.count('Externe CHF') == 10
    assert 'Pastetli mit Brätkügeli' not in cafeteria

    assert len(re.findall(r'class="patient-week-day"', patient)) == 7
    assert len(re.findall(r'class="patient-week-cell(?: [^"]*)?"', patient)) == 14
    assert len(re.findall(r'class="patient-week-option"', patient)) == 28
    assert 'Kichererbsen-Curry' not in patient
    assert PATIENT_FORBIDDEN.search(patient) is None


@pytest.mark.parametrize(
    'path',
    (
        '/signage/cafeteria/tag',
        '/signage/cafeteria/woche',
        '/signage/patienten/tag',
        '/signage/patienten/woche',
    ),
)
def test_real_signage_routes_have_no_navigation_or_interaction(app: Flask, path: str) -> None:
    html = _client(app).get(path).get_data(as_text=True)

    assert re.search(r'<(?:a|nav|form|button|input|select|textarea)\b', html, re.I) is None
    assert '?date=' not in html
    assert '?profil=' not in html


@pytest.mark.parametrize(
    ('profile', 'path', 'width', 'height', 'title_limit', 'detail_limit', 'description_limit'),
    (
        ('staff_guest', '/signage/cafeteria/tag', 1920, 1080, 46, 70, 70),
        ('staff_guest', '/signage/cafeteria/woche', 1920, 1080, 36, 48, None),
        ('patient', '/signage/patienten/tag', 1920, 1080, 42, 62, None),
        ('patient', '/signage/patienten/woche', 1920, 1080, 36, 48, None),
        ('patient', '/signage/patienten/woche', 3840, 2160, 36, 48, None),
    ),
)
def test_signage_surface_boundaries_render_without_hidden_clipping(
    app: Flask,
    browser: Browser,
    profile: str,
    path: str,
    width: int,
    height: int,
    title_limit: int,
    detail_limit: int,
    description_limit: int | None,
) -> None:
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    _set_signage_boundaries(
        snapshot,
        title_length=title_limit,
        component_length=detail_limit,
        description_length=description_limit,
    )
    html = _client(app).get(path).get_data(as_text=True)
    page = _page(browser, html, width, height)
    try:
        _assert_no_viewport_overflow(
            page,
            (
                '.signage-shell',
                '.signage-menu-card',
                '.cafe-week-slot',
                '.patient-signage-meal',
                '.patient-week-cell',
                '.slot-body h3',
                '.slot-body p',
                '.patient-signage-option h3',
                '.patient-signage-option p',
                '.patient-week-option strong',
                '.patient-week-option span',
            ),
        )
    finally:
        page.close()


@pytest.mark.parametrize(
    ('profile', 'path'),
    (
        ('staff_guest', '/signage/cafeteria/tag'),
        ('staff_guest', '/signage/cafeteria/woche'),
        ('patient', '/signage/patienten/tag'),
        ('patient', '/signage/patienten/woche'),
    ),
)
@pytest.mark.parametrize(('width', 'height'), ((1920, 1080), (3840, 2160)))
@pytest.mark.parametrize(('title_length', 'component_length'), ((36, 48), (37, 49)))
def test_unbroken_signage_text_remains_visible_without_clipping(
    app: Flask,
    browser: Browser,
    profile: str,
    path: str,
    width: int,
    height: int,
    title_length: int,
    component_length: int,
) -> None:
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    title, component = _set_unbroken_signage_boundaries(
        snapshot,
        title_length=title_length,
        component_length=component_length,
    )
    html = _client(app).get(path).get_data(as_text=True)

    assert title in html
    assert component in html
    page = _page(browser, html, width, height)
    selectors = (
        '.signage-menu-card .content h3',
        '.signage-menu-card .content p',
        '.signage-components li',
        '.cafe-week-slot h3',
        '.cafe-week-slot p',
        '.patient-signage-option h3',
        '.patient-signage-option p',
        '.patient-week-option strong',
        '.patient-week-option span',
    )
    try:
        _assert_no_viewport_overflow(
            page,
            (
                '.signage-shell',
                '.signage-menu-card',
                '.cafe-week-slot',
                '.patient-signage-meal',
                '.patient-week-cell',
                *selectors,
            ),
        )
        text_state = page.evaluate(
            """
            selectors => selectors.flatMap(selector =>
              [...document.querySelectorAll(selector)].map(element => {
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return {
                  visible: style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity) > 0 && rect.width > 0 && rect.height > 0,
                  clamp: style.webkitLineClamp,
                  ellipsis: style.textOverflow === 'ellipsis',
                };
              })
            )
            """,
            selectors,
        )
        assert text_state
        assert all(item == {'visible': True, 'clamp': 'none', 'ellipsis': False} for item in text_state)
    finally:
        page.close()

@pytest.mark.parametrize(
    ('profile', 'path', 'width', 'height', 'title_limit', 'component_limit'),
    (
        ('staff_guest', '/signage/cafeteria/tag', 1920, 1080, 46, 70),
        ('staff_guest', '/signage/cafeteria/woche', 1920, 1080, 36, 48),
        ('patient', '/signage/patienten/tag', 1920, 1080, 42, 62),
        ('patient', '/signage/patienten/woche', 1920, 1080, 36, 48),
        ('patient', '/signage/patienten/woche', 3840, 2160, 36, 48),
    ),
)
def test_unbroken_signage_text_at_surface_maxima_remains_visible_without_clipping(
    app: Flask,
    browser: Browser,
    profile: str,
    path: str,
    width: int,
    height: int,
    title_limit: int,
    component_limit: int,
) -> None:
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    title, component = _set_unbroken_signage_boundaries(
        snapshot,
        title_length=title_limit,
        component_length=component_limit,
    )
    html = _client(app).get(path).get_data(as_text=True)

    assert title in html
    assert component in html
    page = _page(browser, html, width, height)
    selectors = (
        '.signage-menu-card .content h3',
        '.signage-menu-card .content p',
        '.signage-components li',
        '.cafe-week-slot h3',
        '.cafe-week-slot p',
        '.patient-signage-option h3',
        '.patient-signage-option p',
        '.patient-week-option strong',
        '.patient-week-option span',
    )
    try:
        _assert_no_viewport_overflow(
            page,
            (
                '.signage-shell',
                '.signage-menu-card',
                '.cafe-week-slot',
                '.patient-signage-meal',
                '.patient-week-cell',
                *selectors,
            ),
        )
        text_state = page.evaluate(
            """
            selectors => selectors.flatMap(selector =>
              [...document.querySelectorAll(selector)].map(element => {
                const style = getComputedStyle(element);
                const rect = element.getBoundingClientRect();
                return {
                  visible: style.display !== 'none' && style.visibility !== 'hidden' &&
                    Number(style.opacity) > 0 && rect.width > 0 && rect.height > 0,
                  clamp: style.webkitLineClamp,
                  ellipsis: style.textOverflow === 'ellipsis',
                };
              })
            )
            """,
            selectors,
        )
        assert text_state
        assert all(item == {'visible': True, 'clamp': 'none', 'ellipsis': False} for item in text_state)
    finally:
        page.close()



@pytest.mark.parametrize('path', ('/cafeteria/wochenangebot/', '/patienten/wochenplan/'))
@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 1100)))
def test_public_week_routes_have_no_horizontal_viewport_overflow(
    app: Flask,
    browser: Browser,
    path: str,
    width: int,
    height: int,
) -> None:
    html = _client(app).get(path).get_data(as_text=True)
    page = _page(browser, html, width, height)
    try:
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
    finally:
        page.close()


def test_mobile_interactive_targets_focus_and_layout_contracts(
    app: Flask,
    browser: Browser,
) -> None:
    client = _client(app)
    for path, selectors in (
        ('/cafeteria/wochenangebot/', ('.site-logo', '.site-nav a')),
        ('/admin/cafeteria', ('.admin-nav a', '.profile-tabs a')),
        ('/admin/patienten', ('.admin-nav a', '.profile-tabs a')),
    ):
        page = _page(browser, client.get(path).get_data(as_text=True), 390, 844)
        try:
            metrics = page.evaluate(
                """
                selectors => selectors.flatMap(selector =>
                  [...document.querySelectorAll(selector)].map(element => {
                    const rect = element.getBoundingClientRect();
                    return {
                      selector,
                      width: rect.width,
                      height: rect.height,
                      left: rect.left,
                      right: rect.right,
                    };
                  })
                )
                """,
                selectors,
            )
            assert metrics
            assert all(item['width'] >= 44 and item['height'] >= 44 for item in metrics)
            assert all(item['left'] >= -1 and item['right'] <= 391 for item in metrics)
            target = page.locator(selectors[0]).first
            target.focus()
            assert target.evaluate(
                "element => element.matches(':focus-visible') && getComputedStyle(element).boxShadow !== 'none'"
            )
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        finally:
            page.close()


@pytest.mark.parametrize('path', ('/admin/cafeteria', '/admin/patienten'))
@pytest.mark.parametrize(('width', 'height'), ((390, 844), (1440, 1100)))
def test_every_admin_control_is_reachable_sized_and_non_overlapping(
    app: Flask,
    browser: Browser,
    path: str,
    width: int,
    height: int,
) -> None:
    page = _page(browser, _client(app).get(path).get_data(as_text=True), width, height)
    try:
        result = page.evaluate(
            """
            () => {
              const selector = 'a[href], button, input:not([type="hidden"]), select, textarea';
              const controls = [...document.querySelectorAll(selector)].filter(element => {
                const style = getComputedStyle(element);
                return style.display !== 'none' && style.visibility !== 'hidden';
              });
              const reachable = controls.map(element => {
                element.focus({preventScroll: true});
                element.scrollIntoView({block: 'center', inline: 'center'});
                const rect = element.getBoundingClientRect();
                const hit = document.elementFromPoint(
                  Math.min(innerWidth - 1, Math.max(0, rect.left + rect.width / 2)),
                  Math.min(innerHeight - 1, Math.max(0, rect.top + rect.height / 2)),
                );
                return {
                  target: element.id || element.name || element.textContent.trim(),
                  width: rect.width,
                  height: rect.height,
                  reachable: Boolean(hit && (hit === element || element.contains(hit))),
                };
              });
              scrollTo(0, 0);
              const boxes = controls.map(element => {
                const rect = element.getBoundingClientRect();
                const cell = element.closest(
                  '.admin-day, .admin-dish, .patient-admin-meal, .patient-admin-option, .toolbar, .admin-nav, .profile-tabs'
                );
                const cellRect = cell?.getBoundingClientRect();
                return {
                  target: element.id || element.name || element.textContent.trim(),
                  left: rect.left,
                  top: rect.top,
                  right: rect.right,
                  bottom: rect.bottom,
                  contained: !cellRect || (
                    rect.left >= cellRect.left - 1 && rect.right <= cellRect.right + 1 &&
                    rect.top >= cellRect.top - 1 && rect.bottom <= cellRect.bottom + 1
                  ),
                };
              });
              const overlaps = [];
              for (let left = 0; left < boxes.length; left += 1) {
                for (let right = left + 1; right < boxes.length; right += 1) {
                  const a = boxes[left];
                  const b = boxes[right];
                  if (
                    Math.min(a.right, b.right) - Math.max(a.left, b.left) > 1 &&
                    Math.min(a.bottom, b.bottom) - Math.max(a.top, b.top) > 1
                  ) {
                    overlaps.push(`${a.target} <> ${b.target}`);
                  }
                }
              }
              return {reachable, contained: boxes.filter(box => !box.contained), overlaps};
            }
            """
        )
        assert result['reachable']
        assert all(
            item['width'] >= 44 and item['height'] >= 44 for item in result['reachable']
        ), result['reachable']
        assert all(item['reachable'] for item in result['reachable']), result['reachable']
        assert result['contained'] == []
        assert result['overlaps'] == []
    finally:
        page.close()


def test_cafeteria_weekend_route_is_closed_full_surface(app: Flask, browser: Browser) -> None:
    app.config['DEMO_TODAY'] = dt.date(2026, 9, 5).isoformat()
    html = _client(app).get('/signage/cafeteria/tag').get_data(as_text=True)

    assert 'Cafeteria geschlossen' in html
    assert 'Pastetli mit Brätkügeli' not in html
    page = _page(browser, html, 1920, 1080)
    try:
        _assert_no_viewport_overflow(page, ('.signage-shell', '.closed-card'))
    finally:
        page.close()


def test_local_login_error_alert_has_role_and_focus(app: Flask, browser: Browser) -> None:
    """Test that the login error alert is properly accessible."""
    app.config['LOCAL_AUTH_ENABLED'] = True
    client = _client(app)
    
    # Render login with error
    html = client.get('/auth/local').get_data(as_text=True)
    html_with_error = html.replace(
        '<h1 id="local-login-title">Anmelden</h1>',
        '<h1 id="local-login-title">Anmelden</h1>\n    <div class="auth-alert" role="alert" tabindex="-1" autofocus>\n      Test error message\n    </div>'
    )
    
    page = _page(browser, html_with_error, 1440, 900)
    try:
        result = page.evaluate(
            """
            () => {
                const alert = document.querySelector('.auth-alert');
                return {
                    hasRole: alert.getAttribute('role') === 'alert',
                    hasTabindex: alert.getAttribute('tabindex') === '-1',
                    hasAutofocus: alert.hasAttribute('autofocus'),
                    visible: alert.offsetHeight > 0
                };
            }
            """
        )
        assert result['hasRole'], 'Alert should have role="alert"'
        assert result['hasTabindex'], 'Alert should have tabindex="-1"'
        assert result['hasAutofocus'], 'Alert should have autofocus'
        assert result['visible'], 'Alert should be visible'
    finally:
        page.close()


def test_local_login_page_renders_without_overflow(app: Flask, browser: Browser) -> None:
    """Test that the modern login page renders correctly at mobile and desktop sizes."""
    app.config['LOCAL_AUTH_ENABLED'] = True
    client = _client(app)
    
    html = client.get('/auth/local').get_data(as_text=True)
    assert '<form' in html
    assert 'name="username"' in html
    assert 'name="password"' in html
    assert 'name="csrf_token"' in html
    assert 'Anmelden' in html
    
    # Test at mobile size (390x844) - check horizontal overflow only
    page_mobile = _page(browser, html, 390, 844)
    try:
        result = page_mobile.evaluate(
            """
            () => {
                return {
                    viewport: document.documentElement.scrollWidth <= innerWidth + 1,
                    clipped: [...document.querySelectorAll('.auth-shell, .auth-card')]
                        .filter(el => el.scrollWidth > el.clientWidth + 1)
                        .length === 0
                };
            }
            """
        )
        assert result['viewport'], 'Page has horizontal overflow'
        assert result['clipped'], 'Elements are horizontally clipped'
    finally:
        page_mobile.close()
    
    # Test at desktop size (1440x900)
    page_desktop = _page(browser, html, 1440, 900)
    try:
        result = page_desktop.evaluate(
            """
            () => {
                return {
                    viewport: document.documentElement.scrollWidth <= innerWidth + 1,
                    clipped: [...document.querySelectorAll('.auth-shell, .auth-card')]
                        .filter(el => el.scrollWidth > el.clientWidth + 1)
                        .length === 0
                };
            }
            """
        )
        assert result['viewport'], 'Page has horizontal overflow at desktop'
        assert result['clipped'], 'Elements are horizontally clipped at desktop'
    finally:
        page_desktop.close()
