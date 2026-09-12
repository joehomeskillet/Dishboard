"""Recipe correction UX keeps native contracts and full-width browser behavior."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, expect

from test_recipe_images_browser import recipe_server  # noqa: F401
from test_recipe_navigation_browser import navigation  # noqa: F401
from test_recipe_revision_routes import a3, app_engine, b3, installed_pg16, pg16, seeded_pg16  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/ui-korrektur-0912/recipes'
VIEWPORTS = (
    ('desktop-1366', 1366, 768),
    ('desktop-1920', 1920, 1080),
    ('tablet', 768, 1024),
    ('mobile', 390, 844),
    ('zoom-200', 720, 450),
)


def _open(page: Page, base: str, path: str, allowed: tuple[int, ...] = (200,)) -> None:
    response = page.goto(base + path, wait_until='networkidle')
    assert response is not None and response.status in allowed, (path, getattr(response, 'status', None))
    page.evaluate('document.fonts.ready')


def _check_layout(page: Page, width: int) -> None:
    metrics = page.evaluate('''() => {
      const box = document.querySelector('.page-body > .container-xl')
        || document.querySelector('main.container-fluid') || document.querySelector('main');
      const cs = getComputedStyle(box);
      const inner = box.getBoundingClientRect().width
        - parseFloat(cs.paddingLeft) - parseFloat(cs.paddingRight);
      const children = [...box.children].filter(element => element.getBoundingClientRect().height > 8);
      const primary = Math.max(0, ...children.map(element => element.getBoundingClientRect().width));
      return {
        maxWidth: cs.maxWidth,
        ratio: inner ? primary / inner : 0,
        overflow: document.documentElement.scrollWidth > innerWidth + 1,
      };
    }''')
    assert not metrics['overflow'], metrics
    if width >= 1024:
        assert metrics['maxWidth'] in {'none', ''}, metrics
        assert metrics['ratio'] >= 0.95, metrics
    for control in page.locator('main :is(.btn, .form-control, .form-select)').all():
        if control.is_visible():
            box = control.bounding_box()
            assert box is not None and box['height'] >= 44 and box['width'] >= 24


def _capture(page: Page, state: str, width: int, height: int, javascript: bool) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    suffix = 'js' if javascript else 'nojs'
    page.screenshot(path=str(EVIDENCE / f'{state}-{width}x{height}-{suffix}.png'), full_page=True)


@pytest.mark.parametrize('javascript', [False, True])
def test_recipe_pages_follow_correction_contract(
    navigation,  # noqa: F811
    recipe_server,  # noqa: F811
    browser,  # noqa: F811
    javascript: bool,
) -> None:
    recipe_id, _, revision_id = navigation
    base, cookie = recipe_server
    with browser.new_context(
        viewport={'width': 1366, 'height': 768},
        java_script_enabled=javascript,
        reduced_motion='reduce',
        service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        errors: list[str] = []
        page.on('pageerror', lambda error: errors.append(str(error)))

        for _, width, height in VIEWPORTS:
            page.set_viewport_size({'width': width, 'height': height})

            _open(page, base, '/admin/rezepte')
            expect(page.get_by_label('Kennzeichnung', exact=True)).to_be_visible()
            expect(page.locator('main summary').filter(has_text='Symbole')).to_have_count(0)
            expect(page.locator('.recipe-card a').first).to_contain_text('Bearbeiten')
            assert page.locator('.recipe-card a').first.get_attribute('href').startswith('/admin/rezepte/')
            _check_layout(page, width)
            _capture(page, 'liste-regulaer', width, height, javascript)

            _open(page, base, '/admin/rezepte?q=zzzz-ui-korrektur-empty')
            expect(page.get_by_role('heading', name='Keine passenden Rezepte', exact=True)).to_be_visible()
            _check_layout(page, width)
            _capture(page, 'liste-leer', width, height, javascript)

            editor_path = f'/admin/rezepte/{recipe_id}'
            _open(page, base, editor_path)
            expect(page.get_by_text('Entwurf · Änderungen werden erst mit Speichern übernommen.', exact=True)).to_be_visible()
            expect(page.get_by_text('Weitere Aktionen', exact=True)).to_be_visible()
            expect(page.locator('details', has=page.get_by_text('Weitere Aktionen', exact=True))).not_to_have_attribute('open', '')
            expect(page.locator('#recipe-editor')).to_be_visible()
            expect(page.get_by_role('heading', name='Kennzeichnungen', exact=True)).to_be_visible()
            expect(page.locator('#recipe-editor button[formaction]').first).not_to_have_text('')
            assert page.locator('#recipe-editor').get_attribute('method') == 'post'
            assert page.locator('#recipe-editor').get_attribute('action') == editor_path
            page.get_by_text('Weitere Aktionen', exact=True).click()
            expected_links = {
                'Bilder verwalten': f'{editor_path}/bilder',
                'Gespeicherte Stände': f'{editor_path}/revisionen',
                'Mengen berechnen': f'{editor_path}/skalierung',
            }
            for label, path in expected_links.items():
                assert page.get_by_role('link', name=label, exact=True).get_attribute('href') == path
            _check_layout(page, width)
            _capture(page, 'editor-regulaer', width, height, javascript)

            images_path = f'{editor_path}/bilder'
            _open(page, base, images_path)
            upload = page.get_by_role('button', name='Bild hochladen', exact=True)
            expect(page.get_by_label('Bilddatei', exact=True)).to_be_visible()
            expect(upload).to_be_visible()
            assert page.locator(f'form[action="{images_path}"]').get_attribute('method') == 'post'
            assert set(page.locator(f'form[action="{images_path}"] [name]').evaluate_all(
                'elements => elements.map(element => element.name)'
            )) >= {'_csrf', '_form_context', 'row_version', 'file', 'caption', 'source_url', 'source_license', 'fetched_at'}
            if height >= 768:
                content_box = page.locator('.page-body').bounding_box()
                upload_box = upload.bounding_box()
                assert content_box is not None and upload_box is not None
                assert upload_box['y'] - content_box['y'] < height
            expect(page.locator('td[data-label="Herkunft"] details').first).not_to_have_attribute('open', '')
            _check_layout(page, width)
            _capture(page, 'bilder-regulaer', width, height, javascript)

            revisions_path = f'{editor_path}/revisionen'
            _open(page, base, revisions_path)
            expect(page.get_by_role('heading', name='Gespeicherte Stände', exact=True)).to_be_visible()
            freeze = page.locator(f'form[action="{revisions_path}"]')
            assert freeze.get_attribute('method') == 'post'
            assert set(freeze.locator('[name]').evaluate_all('elements => elements.map(element => element.name)')) == {
                '_csrf', '_form_context', 'row_version',
            }
            expect(page.get_by_role('link', name='Gespeicherten Stand 1 öffnen', exact=True)).to_be_visible()
            _check_layout(page, width)
            _capture(page, 'staende-regulaer', width, height, javascript)

            revision_path = f'{revisions_path}/{revision_id}'
            _open(page, base, revision_path)
            expect(page.get_by_role('heading', name='Gespeicherter Stand 1', exact=True)).to_be_visible()
            expect(page.get_by_text('Dieser gespeicherte Stand bleibt unverändert.', exact=False)).to_have_count(1)
            technical = page.locator('details.card > summary').filter(has_text='Technische Details')
            expect(technical).to_have_count(1)
            technical.click()
            expect(page.get_by_text('Vollständige Daten', exact=True)).to_be_visible()
            _check_layout(page, width)
            _capture(page, 'stand-regulaer', width, height, javascript)

            scale_path = f'{editor_path}/skalierung'
            _open(page, base, scale_path)
            amount = page.locator(f'form[action="{scale_path}"]')
            assert amount.get_attribute('method') == 'get'
            expect(page.locator('main summary').filter(has_text='Symbole')).to_have_count(0)
            _check_layout(page, width)
            _capture(page, 'mengen-regulaer', width, height, javascript)

            _open(page, base, '/admin/rezepte/neu')
            page.locator('#recipe-editor').evaluate('form => { form.noValidate = true; }')
            with page.expect_request(lambda request: request.method == 'POST') as submitted:
                page.get_by_role('button', name='Rezept anlegen', exact=True).click()
            request = submitted.value
            assert urlsplit(request.url).path == '/admin/rezepte/neu'
            assert request.post_data is not None and '_csrf=' in request.post_data and '_form_context=' in request.post_data
            page.wait_for_load_state('networkidle')
            expect(page.get_by_role('heading', name='Rezeptaktion nicht möglich', exact=True)).to_be_visible()
            expect(page.locator('#recipe-error')).to_be_visible()
            _check_layout(page, width)
            _capture(page, 'konflikt', width, height, javascript)

        assert errors == []
