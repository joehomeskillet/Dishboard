"""Distinct original/target yields, native GET scaling, and unchanged recipe storage."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from test_recipe_images_browser import (  # noqa: F401
    a3, app_engine, b3, browser, installed_pg16, pg16, recipe_server, seeded_pg16,
)
from test_recipe_revision_routes import complete_a3, fields
from test_recipe_store_db import snapshot


@pytest.mark.parametrize('width', (1440, 390))
@pytest.mark.parametrize('javascript', (True, False))
def test_recipe_scale_context_get_and_readonly(
    a3, recipe_server, browser, width, javascript, tmp_path: Path,  # noqa: F811
) -> None:
    complete_a3(a3)
    _, owner, client, _, recipe_id = a3
    revisions = f'/admin/rezepte/{recipe_id}/revisionen'
    frozen = client.post(revisions, data=fields(client, revisions))
    assert frozen.status_code == 303
    revision_path = frozen.location
    assert revision_path.startswith(revisions + '/')
    before = {name: rows for name, rows in snapshot(owner).items() if name.startswith('recipe')}
    base, cookie = recipe_server
    methods, errors, evidence, redundant_headers = [], [], [], []
    with browser.new_context(
        base_url=base, viewport={'width': width, 'height': 844 if width == 390 else 900},
        java_script_enabled=javascript, reduced_motion='reduce', service_workers='block',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.on('request', lambda request: methods.append(request.method))
        page.on('pageerror', lambda error: errors.append(str(error)))

        def capture(stage):
            page.mouse.move(0, 0)
            page.get_by_role('heading', name='Zutaten und Mengen', exact=True).click()
            page.evaluate('scrollTo(0, 0)')
            if javascript:
                expect(page.get_by_role('tooltip')).to_have_count(0)
            measure = '''() => ({
                width: innerWidth, scrollWidth: document.documentElement.scrollWidth,
                fine: matchMedia('(pointer: fine)').matches,
                coarse: matchMedia('(any-pointer: coarse)').matches,
                touch: navigator.maxTouchPoints,
                cards: document.querySelectorAll('.page-header .admin-statusbar-item').length
            })'''
            first = page.evaluate(measure)
            assert first['width'] == width and first['scrollWidth'] <= width + 1
            assert first['fine'] and not first['coarse'] and first['touch'] == 0
            page.screenshot(path=str(tmp_path / f'{stage}-{width}-js{javascript}.png'), full_page=False)
            assert page.evaluate(measure) == first
            evidence.append({'stage': stage, 'measurements': first})
            (tmp_path / 'scale-context.json').write_text(json.dumps(evidence, indent=2))
            if first['cards']:
                redundant_headers.append({'stage': stage, 'cards': first['cards']})

        for kind, action, mode in (
            ('draft', f'/admin/rezepte/{recipe_id}/skalierung', {}),
            ('revision', revision_path, {'mode': ['scale']}),
        ):
            query = '?mode=scale&yield=6' if mode else '?yield=6'
            assert page.goto(action + query).status == 200
            expect(page.locator('.page-header h1')).to_have_text('Rezepte')
            expect(page.locator('.page-header-subtitle')).to_have_text('Suppe')
            status = page.locator('main .alert-info[role="status"]')
            expect(status).to_have_text(
                'Gespeicherter Stand 1 · unverändert. Diese Ansicht verändert das Rezept nicht.'
                if mode else 'Gespeicherter Entwurf. Diese Ansicht verändert das Rezept nicht.'
            )
            form = page.locator(f'main form[action="{action}"]')
            expect(form).to_have_attribute('method', 'get')
            expect(page.locator('main form[method="post"], main [name="_form_context"]')).to_have_count(0)
            amount = page.get_by_label('Zielmenge · PORTION', exact=True)
            expect(amount).to_have_value('6')
            context_text = page.locator('main p').filter(has_text='Ausbeute/Menge im Original:')
            expect(context_text.locator('strong')).to_have_text(['4 PORTION', '6 PORTION'])
            expect(page.get_by_text(
                'Nur berechnet · Keine Speicherung und keine Einheitenumrechnung. '
                'Berechnungswerte werden nicht auf sechs Nachkommastellen gerundet.', exact=True,
            )).to_be_visible()
            ingredient = page.locator('main table tbody tr').first
            expect(ingredient.locator('[data-label="Original"]')).to_have_text('0.125')
            expect(ingredient.locator('[data-label="Berechnet"]')).to_have_text('0.1875')
            expect(ingredient.locator('[data-label="Einheit"]')).to_have_text('KG')
            capture(kind + '-target6')

            amount.fill('8')
            expected = form.evaluate('el => Object.fromEntries(new FormData(el))')
            assert expected == {**({ 'mode': 'scale'} if mode else {}), 'yield': '8'}
            with page.expect_navigation() as submitted:
                amount.press('Enter')
            assert submitted.value.status == 200 and submitted.value.request.method == 'GET'
            assert parse_qs(urlsplit(submitted.value.url).query) == {**mode, 'yield': ['8']}
            expect(context_text.locator('strong')).to_have_text(['4 PORTION', '8 PORTION'])
            expect(ingredient.locator('[data-label="Original"]')).to_have_text('0.125')
            expect(ingredient.locator('[data-label="Berechnet"]')).to_have_text('0.250')
            expect(ingredient.locator('[data-label="Einheit"]')).to_have_text('KG')
            capture(kind + '-target8')

            amount.fill('NaN')
            calculate = page.get_by_role('button', name='Mengen berechnen', exact=True)
            expect(calculate).to_have_text('')
            expect(calculate).to_have_attribute('data-semantic', 'recipe.quantity')
            expect(calculate).to_have_attribute('data-ui-tooltip', 'Mengen berechnen')
            calculate.focus()
            with page.expect_navigation() as invalid:
                calculate.press('Space')
            assert invalid.value.status == 400 and invalid.value.request.method == 'GET'
            assert parse_qs(urlsplit(invalid.value.url).query) == {**mode, 'yield': ['NaN']}
            expect(amount).to_have_value('NaN')
            expect(amount).to_have_attribute('aria-invalid', 'true')
            expect(amount).to_be_focused()
            expect(page.locator('#yield-error')).to_be_visible()
            capture(kind + '-invalid')

            amount.fill('6')
            with page.expect_navigation() as corrected:
                calculate.press('Enter')
            assert corrected.value.status == 200 and corrected.value.request.method == 'GET'
            expect(context_text.locator('strong')).to_have_text(['4 PORTION', '6 PORTION'])
            back = page.get_by_role('link', name='Rezept ansehen', exact=True)
            expected_path = revision_path if mode else f'/admin/rezepte/{recipe_id}/ansicht'
            expect(back).to_have_attribute('href', expected_path + '?yield=6')
            back.focus()
            with page.expect_navigation() as navigated:
                back.press('Enter')
            assert navigated.value.status == 200 and navigated.value.request.method == 'GET'
            assert urlsplit(page.url).path == expected_path
            assert parse_qs(urlsplit(page.url).query) == {'yield': ['6']}
            assert {name: rows for name, rows in snapshot(owner).items() if name.startswith('recipe')} == before
        assert methods and set(methods) == {'GET'} and not errors
    assert {name: rows for name, rows in snapshot(owner).items() if name.startswith('recipe')} == before
    assert redundant_headers == [], redundant_headers
