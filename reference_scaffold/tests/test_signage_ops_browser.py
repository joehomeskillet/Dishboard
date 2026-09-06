"""OPS signage retains all published text across the real player rotation."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest
from playwright.sync_api import expect

from test_public_mobile_ui import http_app as http_app
from test_public_mobile_ui import public_server as public_server
from test_public_ops_browser import card_geometry, ops_snapshot
from test_rendered_ui import app as app
from test_rendered_ui import browser as browser
from test_rendered_ui import _set_legacy_snapshot, _set_unbroken_signage_boundaries

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from capture_branding_live_proof import SIGNAGE, BrandingProof  # noqa: E402


@pytest.mark.parametrize('path,profile,days,selector', [
    *[('/signage/cafeteria/woche', 'staff_guest', days, '.cafe-week-slot') for days in (5, 6, 7)],
    ('/signage/cafeteria/tag', 'staff_guest', 7, '.hero-food'),
    ('/signage/patienten/tag', 'patient', 7, '.patient-signage-option'),
    ('/signage/patienten/woche', 'patient', 7, '.patient-week-option'),
])
@pytest.mark.parametrize('width,height', [(1920, 1080), (3840, 2160)])
def test_complete_ops_signage_stays_readable_through_all_pages(
        http_app, public_server, browser, tmp_path, path, profile, days, selector, width, height):
    snapshot = ops_snapshot(http_app, profile, days)
    selected = snapshot['days'][-1:] if path.endswith('/tag') else snapshot['days']
    if path == '/signage/patienten/woche':
        # The week board pages by meal, so every menu is read meal first, then day.
        options = [option for meal in ('LUNCH', 'DINNER') for day in selected
                   for service in day['services'] if service['meal_code'] == meal
                   for option in service['options']]
    else:
        options = [option for day in selected for service in day['services']
                   for option in service['options']]
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        page = context.new_page()
        page.clock.install()
        errors = []
        page.on('pageerror', lambda error: errors.append(str(error)))
        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
        response = page.goto(public_server + path, wait_until='load')
        assert response and response.status == 200
        assert "style-src 'self'" in response.headers['content-security-policy']
        page.evaluate('document.fonts.ready')
        pages = max(1, page.locator('[data-signage-page]').count())
        if path == '/signage/patienten/woche':
            assert pages == 4
            expect(page.locator('[data-signage-rotation]')).to_have_attribute('data-signage-rotation', 'ops')
        observed = []
        all_measured = []
        for index in range(pages):
            if path == '/signage/patienten/woche':
                visible = '[data-signage-page]:not([hidden])'
                selected_days = selected[:4] if index % 2 == 0 else selected[4:]
                assert page.locator(visible + ' .patient-week-day > header h2').all_inner_texts() == [
                    day['weekday'] for day in selected_days]
                expect(page.locator(visible + ' .patient-board-page-label')).to_contain_text(
                    'Mittag' if index < 2 else 'Abend')
                expect(page.locator(visible + ' .patient-week-cell')).to_have_count(len(selected_days))
            cards = page.locator(selector + ':visible')
            observed.extend(cards.all_inner_texts())
            measured = card_geometry(page, selector + ':visible')
            all_measured.extend(measured)
            stem = f'{profile}-{path.rsplit("/", 1)[-1]}-{days}-{width}-{index}'
            (tmp_path / f'{stem}.json').write_text(json.dumps(measured, indent=2))
            page.screenshot(path=str(tmp_path / f'{stem}.png'))
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1 && document.documentElement.scrollHeight <= innerHeight + 1')
            assert not any(row['clipped'] for row in measured), measured
            assert all(row['bottom'] <= height + 1 for row in measured)
            # Cards shown together must match; a later page may group a different day count.
            for axis in ('width', 'height'):
                assert max(row[axis] for row in measured) - min(row[axis] for row in measured) <= 1, (axis, measured)
            if index + 1 < pages:
                page.clock.fast_forward(30_010)
                expect(page.locator('[data-signage-page]').nth(index + 1)).to_be_visible()
        assert len(observed) == len(options)
        for text, option in zip(observed, options, strict=True):
            for expected in (option['title'], option['note'], *option['components']):
                assert expected in text
        if path == '/signage/patienten/woche':
            assert page.locator(selector + ' h3,' + selector + ' small,' + selector + ' span,' +
                                selector + ' p').evaluate_all(
                'nodes => nodes.every(node => parseFloat(getComputedStyle(node).fontSize) >= 18)')
            for axis in ('width', 'height'):
                assert max(row[axis] for row in all_measured) - min(row[axis] for row in all_measured) <= 1
        assert errors == []


@pytest.mark.parametrize('profile,days,variant', [
    ('patient', 7, 'ops'), ('patient', 7, 'ops-long'),
    ('patient', 7, 'legacy1'), ('patient', 7, 'legacy2'),
    *[('staff_guest', days, 'ops') for days in (5, 6, 7)],
])
@pytest.mark.parametrize('width,height', [(1920, 1080), (3840, 2160)])
def test_operator_proof_observes_real_ops_rotation(
        http_app, public_server, browser, tmp_path, monkeypatch, profile, days, variant, width, height):
    if variant.startswith('ops'):
        snapshot = ops_snapshot(http_app, profile, days)
        if variant == 'ops-long':
            _set_unbroken_signage_boundaries(snapshot, title_length=36, component_length=48)
    else:
        _set_legacy_snapshot(http_app.config['TEST_SNAPSHOTS'][profile], int(variant[-1]))
    path = SIGNAGE[3 if profile == 'patient' else 1]
    with browser.new_context(viewport={'width': width, 'height': height}, reduced_motion='reduce') as context:
        page = context.new_page()
        page.clock.install()
        proof = BrandingProof(public_server, tmp_path)
        proof.capture(page, path, 'week', signage=True)
        original_wait = page.wait_for_function

        def advance_rotation(expression, **kwargs):
            page.clock.fast_forward(30_100)
            return original_wait(expression, **kwargs)

        monkeypatch.setattr(page, 'wait_for_function', advance_rotation)
        if profile == 'patient':
            proof.patient_rotation(page, 'week')
            assert proof.data['checks']['week.four_pages' if variant.startswith('ops') else 'week.two_pages']
        else:
            proof.cafeteria_rotation(page, 'week')
            assert proof.data['checks']['week.cafeteria_pages']
        (tmp_path / 'operator-proof.json').write_text(json.dumps(proof.data, indent=2))
        assert proof.outcome() == ('browser_passed', 0), proof.data['failures']
