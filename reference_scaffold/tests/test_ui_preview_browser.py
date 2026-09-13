"""Browser suite for standalone, script-free admin.preview (MP-UI-PREVIEW, MP-UI-DENSITY-PREVIEW / M14)."""
from __future__ import annotations

import json
import re
from copy import deepcopy
from datetime import date, timedelta
from io import BytesIO
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from flask import Flask
from playwright.sync_api import Browser, BrowserContext, Page, expect
from pypdf import PdfReader
from sqlalchemy import Engine, text

from cafeteria import roles
from cafeteria.branding_config import contrast
from cafeteria.public import routes as public_routes
from cafeteria.workflow import load_draft, publish_draft, save_draft
from review_support import review_saved_week, write_expectations
from test_admin_ux_browser import live_server  # noqa: F401
from test_admin_workflow_db import _actor_id, _patient_values, _save, _staff_values
from test_admin_workflow_routes import DATABASE_URL, DAY, WEEK, _login
from test_recipe_freeze_v2_browser import native_full_page_capture
from test_rendered_ui import admin_app, admin_engine, browser  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude' / 'evidence' / 'density-preview-0913' / 'after'
NEXT_WEEK = WEEK + timedelta(days=7)
PRIMARY_LABEL = 'PDF der gewählten Woche öffnen'
BACK_LABEL = 'Zurück zum Wochenplan'
PUBLISHED_LABEL = 'Veröffentlichten Plan drucken'
ACTIONS = '.preview-links a, .preview-profiles a, .preview-published a'
METRICS = '''() => {
  const first = document.querySelector('.preview-day, .preview-empty');
  const rect = el => el.getBoundingClientRect();
  return {
    innerWidth, innerHeight, devicePixelRatio,
    documentWidth: document.documentElement.scrollWidth,
    documentHeight: document.documentElement.scrollHeight,
    firstContentTop: first ? rect(first).top + scrollY : null,
    actions: [...document.querySelectorAll('%s')].map(el => ({
      text: el.textContent.trim(), width: rect(el).width, height: rect(el).height,
    })),
    icons: [...document.querySelectorAll('.admin-preview use')].map(el => ({
      href: el.getAttribute('href'), width: el.getBBox().width,
    })),
  };
}''' % ACTIONS
VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080), (2560, 1440))
FAMILIES = (
    ('cafeteria', 'staff_guest', 'Mitarbeitende und externe Gäste'),
    ('patienten', 'patient', 'Patientinnen und Patienten'),
)
SCRIPT_FREE = 'script, style, [style], [onclick], form, button'
STATUS_LABELS = (
    ('ready', 'Nicht veröffentlicht · Bereit'),
    ('published', 'Veröffentlicht'),
    ('archived', 'Nicht veröffentlicht · Archiviert'),
    ('draft', 'Nicht veröffentlicht · Entwurf'),
)


def _hex(color: str) -> str:
    match = re.match(r'rgba?\((\d+),\s*(\d+),\s*(\d+)', color)
    if match:
        red, green, blue = (int(value) for value in match.groups())
        return f'#{red:02x}{green:02x}{blue:02x}'
    return color


def _cookie_page(
    browser: Browser, live_server: str, cookie_value: str, *,  # noqa: F811
    width: int, height: int, java_script_enabled: bool,
) -> tuple[BrowserContext, Page]:
    context = browser.new_context(
        base_url=live_server,
        java_script_enabled=java_script_enabled,
        viewport={'width': width, 'height': height},
    )
    context.add_cookies([{
        'name': 'session', 'value': cookie_value, 'url': live_server, 'httpOnly': True,
    }])
    return context, context.new_page()


def _setup(app: Flask, profile: str) -> dict:
    values = _staff_values() if profile == 'staff_guest' else _patient_values()
    closed = values['days'][-1]['services'][-1]
    closed.update(service_state='closed', notice='Feiertag – Küche geschlossen')
    _save(app.extensions['cafeteria_db'], profile, values)
    return values


def _shift(values: dict, days: int, title: str) -> dict:
    shifted = deepcopy(values)
    shifted['title'] = title
    for day in shifted['days']:
        day['date'] = (date.fromisoformat(day['date']) + timedelta(days=days)).isoformat()
    return shifted


def _save_week(engine: Engine, profile: str, week: date, values: dict) -> int:
    actor_id = _actor_id(engine)
    expectations = write_expectations(engine, actor_id)
    draft = load_draft(engine, profile, week, actor_id=actor_id, **expectations)
    return save_draft(
        engine, profile, week, expected_row_version=draft['row_version'], actor_id=actor_id,
        values=values, **expectations,
    )


def _publish_week(engine: Engine, profile: str, week: date) -> dict:
    actor_id = _actor_id(engine)
    version = review_saved_week(engine, profile, week, actor_id)
    return publish_draft(
        engine, profile, week, expected_row_version=version, actor_id=actor_id, issuer_engine=engine,
    )


def _evidence(page: Page, name: str, **extra: object) -> dict:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    metrics = page.evaluate(METRICS)
    metrics.update(extra)
    (EVIDENCE / f'{name}.json').write_text(json.dumps(metrics, ensure_ascii=False, indent=2))
    page.screenshot(path=str(EVIDENCE / f'{name}.png'), full_page=True)
    return metrics


def _assert_actions(page: Page) -> None:
    """M14/A16: labelled actions, primary first, loaded icons, 44px targets (48px kept)."""
    links = page.locator(ACTIONS)
    assert links.count() == 5
    primary = page.locator('.preview-links a').first
    assert primary.inner_text().strip() == PRIMARY_LABEL
    assert primary.evaluate('el => el.classList.contains("primary")')
    for index in range(links.count()):
        link = links.nth(index)
        assert link.inner_text().strip()
        box = link.bounding_box()
        assert box is not None and box['height'] >= 44 and box['width'] >= 44, box
    uses = page.locator('.preview-links use, .preview-published use')
    assert uses.count() == 3
    for use in uses.all():
        assert use.evaluate('el => el.getBBox().width > 0'), use.get_attribute('href')
        assert use.evaluate('el => el.closest("svg").getAttribute("aria-hidden")') == 'true'


def _assert_script_free(page: Page) -> None:
    assert page.locator(SCRIPT_FREE).count() == 0


def _assert_no_overflow(page: Page) -> None:
    assert page.evaluate(
        'document.documentElement.scrollWidth <= document.documentElement.clientWidth',
    )


@pytest.mark.parametrize('family,profile,label', FAMILIES)
def test_preview_standalone_script_free_saved_states(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, label: str,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    values = _setup(admin_app, profile)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900,
        java_script_enabled=False,
    )
    try:
        for state, translated in STATUS_LABELS:
            with admin_engine.begin() as connection:
                connection.execute(
                    text('UPDATE cafeteria.menu_weeks SET workflow_state=:state'),
                    {'state': state},
                )
            response = page.goto(f'/admin/{family}/preview?week={DAY}')
            assert response is not None and response.status == 200
            expect(page.locator('.preview-saved')).to_have_text(
                f'Veröffentlichungsstand dieser Woche: {translated}',
            )
            assert page.locator('[data-preview]').get_attribute('data-workflow-state') == state
        expect(page.get_by_role('heading', level=1)).to_have_text(f'Vorschau · {label}')
        expect(page.locator('.preview-banner[role="status"]')).to_have_text('PREVIEW')
        expect(page.locator('.preview-context')).to_have_text(
            'KW 36 / 2026 · Woche ab 31. August 2026',
        )
        expect(page.locator('.preview-notice')).to_contain_text(
            'Gewählter Stand: gespeicherte Woche KW 36, nicht automatisch der veröffentlichte Plan.',
        )
        expect(page.get_by_role('link', name=BACK_LABEL)).to_have_attribute(
            'href', f'/admin/{family}?week={DAY}',
        )
        expect(page.get_by_role('link', name=PRIMARY_LABEL)).to_have_attribute(
            'href', f'/admin/{family}/preview/print?week={DAY}',
        )
        published = page.locator('.preview-published')
        expect(published.get_by_role('heading', level=2)).to_have_text('Veröffentlichter Plan')
        expect(published).to_contain_text('nicht automatisch diese gespeicherte Woche')
        expect(published.get_by_role('link', name=PUBLISHED_LABEL)).to_have_attribute(
            'href', f'/druck/{family}/woche',
        )
        _assert_actions(page)
        prices = page.locator('.prices')
        meals = page.locator('.preview-service > h4').all_text_contents()
        if profile == 'staff_guest':
            assert prices.count() == 8
            expect(prices.first).to_contain_text('Mitarbeitende: 9.50')
            expect(prices.first).to_contain_text('Externe: 14.50')
            assert meals == ['Mittagessen'] * 5
        else:
            assert prices.count() == 0
            assert meals.count('Mittagessen') == 7 and meals.count('Abendessen') == 7
            assert re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I) is None
        current = page.locator('.preview-profiles a[aria-current="page"]')
        expect(current).to_have_text(label)
        expect(page.locator('.preview-profiles a')).to_have_count(2)
        expect(page.locator('main#main-content.admin-preview')).to_have_count(1)
        assert page.locator('.skip-link').get_attribute('href') == '#main-content'
        assert page.locator('nav.admin-sidebar, .navbar-vertical, .admin-main').count() == 0
        _assert_script_free(page)
        expect(page.locator('.service-notice')).to_have_text('Feiertag – Küche geschlossen')
        if values.get('title'):
            expect(page.get_by_role('heading', level=2, name=values['title'])).to_have_text(
                values['title'],
            )
        assert 'Allergen' in page.locator('main').inner_text()
        _assert_no_overflow(page)
        _evidence(page, f'preview-default-{family}-1440')
    finally:
        context.close()


@pytest.mark.parametrize('family,profile,label', FAMILIES)
@pytest.mark.parametrize(
    'width,height,java_script_enabled',
    [
        (1440, 900, False), (1366, 768, False), (1024, 768, False), (768, 1024, False),
        (390, 844, False), (1920, 1080, False), (2560, 1440, False), (320, 844, False),
        (1440, 900, True), (390, 844, True),
    ],
)
def test_preview_viewports_no_overflow(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, label: str, width: int, height: int,
    java_script_enabled: bool,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _setup(admin_app, profile)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=width, height=height,
        java_script_enabled=java_script_enabled,
    )
    try:
        response = page.goto(f'/admin/{family}/preview?week={DAY}')
        assert response is not None and response.status == 200
        if java_script_enabled:
            page.evaluate('document.fonts.ready')
        expect(page.get_by_role('heading', level=1)).to_have_text(f'Vorschau · {label}')
        _assert_script_free(page)
        _assert_no_overflow(page)
        _assert_actions(page)
        suffix = 'js' if java_script_enabled else 'nojs'
        metrics = _evidence(
            page, f'preview-{family}-{width}x{height}-{suffix}', viewport=[width, height],
        )
        assert metrics['documentWidth'] <= width
        if width >= 768:
            # Core content starts within the first screen (A03); no admin wall before it.
            assert metrics['firstContentTop'] < height, metrics['firstContentTop']
        if width >= 1366:
            assert metrics['firstContentTop'] <= 400, metrics['firstContentTop']
    finally:
        context.close()


def test_preview_keyboard_focus(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _setup(admin_app, 'staff_guest')
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900,
        java_script_enabled=True,
    )
    try:
        page.goto(f'/admin/cafeteria/preview?week={DAY}')
        page.evaluate('document.fonts.ready')
        _assert_script_free(page)
        page.keyboard.press('Tab')
        expect(page.locator('.skip-link')).to_be_focused()
        order = []
        for _ in range(5):
            page.keyboard.press('Tab')
            order.append(page.evaluate('document.activeElement.textContent.trim()'))
        assert order == [
            'Mitarbeitende und externe Gäste', 'Patientinnen und Patienten',
            PRIMARY_LABEL, BACK_LABEL, PUBLISHED_LABEL,
        ]
        for label in (PRIMARY_LABEL, BACK_LABEL, PUBLISHED_LABEL):
            page.get_by_role('link', name=label).focus()
            focused = page.evaluate(
                '''() => {
                    const el = document.activeElement;
                    const style = getComputedStyle(el);
                    return {tag: el.tagName, text: el.textContent.trim(),
                            outline: style.outlineStyle, width: parseFloat(style.outlineWidth)};
                }''',
            )
            assert focused['tag'] == 'A' and focused['text'] == label
            assert focused['outline'] != 'none' and focused['width'] >= 2, focused
        _evidence(page, 'preview-keyboard-1440')
    finally:
        context.close()


def test_preview_contrast_empty_invalid_and_authz(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _setup(admin_app, 'staff_guest')
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900,
        java_script_enabled=False,
    )
    try:
        page.goto(f'/admin/cafeteria/preview?week={DAY}')
        for selector in (
            'h1', '.preview-saved', '.preview-context', '.preview-notice',
            '.preview-links .btn.primary', '.preview-published h2', '.preview-published p',
            '.preview-day > h3', '.preview-option h5', '.prices',
        ):
            locator = page.locator(selector).first
            color = locator.evaluate('el => getComputedStyle(el).color')
            background = locator.evaluate(
                '''el => {
                    let node = el;
                    while (node) {
                        const bg = getComputedStyle(node).backgroundColor;
                        if (bg && bg !== 'rgba(0, 0, 0, 0)' && bg !== 'transparent') return bg;
                        node = node.parentElement;
                    }
                    return 'rgb(255, 255, 255)';
                }''',
            )
            assert contrast(_hex(color), _hex(background)) >= 4.5, (selector, color, background)
        empty_values = _staff_values('Leere Woche')
        for day in empty_values['days']:
            for service in day['services']:
                service.update(service_state='closed', notice='Noch keine Menüs gespeichert')
        _save(admin_app.extensions['cafeteria_db'], 'staff_guest', empty_values)
        empty = page.goto(f'/admin/cafeteria/preview?week={DAY}')
        assert empty is not None and empty.status == 200
        assert page.locator('.preview-option').count() == 0
        expect(page.locator('.service-notice').first).to_have_text('Noch keine Menüs gespeichert')
        _assert_script_free(page)
        _evidence(page, 'preview-empty-1440')
        assert page.goto('/admin/cafeteria/preview?week=invalid-date').status == 400
        assert page.goto('/admin/cafeteria/preview?week=2026-08-30').status == 400
        assert page.goto('/admin/cafeteria/preview?week=2099-01-05').status == 404
    finally:
        context.close()

    with browser.new_context(base_url=live_server, viewport={'width': 1440, 'height': 900}) as anon:
        denied = anon.new_page().goto(f'/admin/cafeteria/preview?week={DAY}')
        assert denied is not None and denied.status == 401

    monkeypatch.setattr(roles, 'capabilities', lambda: set())
    forbidden_ctx, forbidden_page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900,
        java_script_enabled=False,
    )
    try:
        forbidden = forbidden_page.goto(f'/admin/cafeteria/preview?week={DAY}')
        assert forbidden is not None and forbidden.status == 403
    finally:
        forbidden_ctx.close()


@pytest.mark.parametrize('family,profile,label', FAMILIES)
def test_preview_prints_selected_week_and_published_plan_as_separate_states(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    family: str, profile: str, label: str,
) -> None:
    """M14/A15: the primary action prints exactly the chosen saved week; the published plan is
    a different, existing output with its own data state (deliberately another week)."""
    # The browser app factory omits the real public blueprint; register it read-only here.
    admin_app.register_blueprint(public_routes.bp)
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    engine = admin_app.extensions['cafeteria_db']
    # No digits: the patient payload guard rejects numeric tokens as cost values.
    published_title, saved_title = 'Publizierte Herbstwoche', 'Gespeicherte Folgewoche'
    base = (_staff_values if profile == 'staff_guest' else _patient_values)(published_title)
    _save_week(engine, profile, WEEK, base)
    revision = _publish_week(engine, profile, WEEK)
    _save_week(engine, profile, NEXT_WEEK, _shift(base, 7, saved_title))
    next_day = NEXT_WEEK.isoformat()
    cookie = client.get_cookie('session')
    assert cookie is not None
    context, page = _cookie_page(
        browser, live_server, cookie.value, width=1440, height=900, java_script_enabled=False,
    )
    try:
        response = page.goto(f'/admin/{family}/preview?week={next_day}')
        assert response is not None and response.status == 200
        expect(page.locator('.preview-context')).to_have_text(
            'KW 37 / 2026 · Woche ab 7. September 2026',
        )
        expect(page.locator('[data-preview]')).to_have_attribute('data-workflow-state', 'draft')
        expect(page.get_by_role('heading', level=2, name=saved_title)).to_have_text(saved_title)
        expect(page.locator('.preview-notice')).to_contain_text('gespeicherte Woche KW 37')
        href = page.get_by_role('link', name=PRIMARY_LABEL).get_attribute('href')
        assert href == f'/admin/{family}/preview/print?week={next_day}'
        pdf = context.request.get(href)
        assert pdf.status == 200, pdf.status
        assert pdf.headers['content-type'].startswith('application/pdf')
        assert pdf.headers['content-disposition'] == (
            f'inline; filename="wochenplan-{family}-{next_day}.pdf"'
        )
        EVIDENCE.mkdir(parents=True, exist_ok=True)
        (EVIDENCE / f'pdf-{family}-{next_day}.pdf').write_bytes(pdf.body())
        body = ' '.join(PdfReader(BytesIO(pdf.body())).pages[0].extract_text().split())
        assert saved_title in body and published_title not in body
        last = '11' if profile == 'staff_guest' else '13'
        assert f'07. bis {last}. September 2026' in body, body[:120]
        assert ('CHF' in body) == (profile == 'staff_guest')
        other = context.request.get(f'/admin/{family}/preview/print?week={DAY}')
        assert other.status == 200
        other_body = ' '.join(PdfReader(BytesIO(other.body())).pages[0].extract_text().split())
        assert published_title in other_body and saved_title not in other_body
        published = page.locator('.preview-published').get_by_role('link', name=PUBLISHED_LABEL)
        assert published.get_attribute('href') == f'/druck/{family}/woche'
        _evidence(page, f'preview-{family}-saved-kw37-vs-published-kw36-1440')
        printed = page.goto(f'/druck/{family}/woche')
        assert printed is not None and printed.status == 200
        assert printed.headers.get('x-snapshot-revision') == revision['revision_id']
        text = ' '.join(page.locator('main').inner_text().split())
        if profile == 'staff_guest':
            assert published_title in text
        else:
            assert re.search(r'31\. August 2026 bis 6\. September 2026', text), text[:200]
        assert saved_title not in text
        assert ('CHF' in text) == (profile == 'staff_guest')
        page.screenshot(path=str(EVIDENCE / f'published-print-{family}-1440.png'), full_page=True)
        page.goto(f'/admin/{family}/preview?week={DAY}')
        expect(page.locator('.preview-context')).to_have_text(
            'KW 36 / 2026 · Woche ab 31. August 2026',
        )
        expect(page.locator('[data-preview]')).to_have_attribute('data-workflow-state', 'published')
        expect(page.get_by_role('link', name=PRIMARY_LABEL)).to_have_attribute(
            'href', f'/admin/{family}/preview/print?week={DAY}',
        )
    finally:
        context.close()


def test_preview_real_browser_zoom_200_keeps_labels_and_reflow(
    browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine,  # noqa: F811
    tmp_path: Path,
) -> None:
    """Real Chrome default zoom (chrome://settings + CDP), not a CSS zoom probe."""
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    _setup(admin_app, 'staff_guest')
    _setup(admin_app, 'patient')
    cookie = client.get_cookie('session')
    assert cookie is not None
    with TemporaryDirectory(prefix='preview-native-zoom-', dir=tmp_path) as profile_dir:
        with browser.browser_type.launch_persistent_context(
            profile_dir, channel='chromium', headless=True, no_viewport=True, base_url=live_server,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate(
                'new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))',
            ) == 2
            context.add_cookies([{
                'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True,
            }])
            cdp = context.new_cdp_session(page)
            EVIDENCE.mkdir(parents=True, exist_ok=True)
            for family in ('cafeteria', 'patienten'):
                response = page.goto(f'/admin/{family}/preview?week={DAY}', wait_until='networkidle')
                assert response is not None and response.status == 200
                page.evaluate('document.fonts.ready')
                assert cdp.send('Page.getLayoutMetrics')['cssVisualViewport']['zoom'] == 2
                assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
                assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
                _assert_script_free(page)
                _assert_no_overflow(page)
                _assert_actions(page)
                metrics = page.evaluate(METRICS)
                metrics['cssVisualViewportZoom'] = 2
                (EVIDENCE / f'preview-{family}-zoom200-1440.json').write_text(
                    json.dumps(metrics, ensure_ascii=False, indent=2),
                )
                native_full_page_capture(page, EVIDENCE / f'preview-{family}-zoom200-1440.png')
