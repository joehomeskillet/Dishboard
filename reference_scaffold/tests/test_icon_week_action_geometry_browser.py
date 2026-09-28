"""Week actions inherit shared pointer geometry without shrinking navigation."""
from __future__ import annotations

import json

import pytest
from playwright.sync_api import expect

from test_admin_ux_browser import (  # noqa: F401
    admin_app, admin_engine, browser, live_server,
)
from test_admin_workflow_db import _patient_values, _save
from test_admin_workflow_routes import DAY, _login


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
@pytest.mark.parametrize('width', [1440, 390])
@pytest.mark.parametrize('coarse', [False, True], ids=['fine', 'coarse'])
def test_week_edit_add_and_header_use_shared_pointer_geometry(
    admin_app, admin_engine, browser, live_server, tmp_path,  # noqa: F811
    javascript, width, coarse,
):
    _save(admin_engine, 'patient', _patient_values())
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    with browser.new_context(
        base_url=live_server, viewport={'width': width, 'height': 900 if width == 1440 else 844},
        java_script_enabled=javascript, has_touch=coarse, reduced_motion='reduce',
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        methods = []
        page.on('request', lambda request: methods.append(request.method))
        response = page.goto(f'/admin/patienten?week={DAY}', wait_until='networkidle')
        assert response is not None and response.status == 200
        page.evaluate('document.fonts.ready')
        assert page.evaluate("matchMedia('(pointer: coarse), (any-pointer: coarse)').matches") is coarse
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        expected = 44 if coarse else 36
        day = page.locator('.patient-admin-day').first
        groups = (
            ('menu-edit', day.locator('.admin-week-card-action [data-semantic="actions.edit"]'), 4),
            ('soup-add', day.locator('[data-course="soup"] [data-semantic="actions.add"]'), 2),
            ('dessert-add', day.locator('[data-course="dessert"] [data-semantic="actions.add"]'), 2),
            ('header', page.locator('.admin-page-header .ui-sem-control--icon-only'), 1),
        )
        measurements = []
        for group, controls, count in groups:
            expect(controls).to_have_count(count)
            for control in controls.all():
                expect(control).to_be_visible()
                expect(control).to_have_text('')
                name = control.get_attribute('aria-label')
                assert name and control.get_attribute('data-ui-tooltip') == name
                box = control.bounding_box()
                assert box is not None
                measurement = {'group': group, 'name': name, 'width': box['width'], 'height': box['height']}
                measurements.append(measurement)
                assert (box['width'], box['height']) == (expected, expected), measurement
        for control in page.locator('.navbar-toggler:visible, .admin-nav:visible a').all():
            box = control.bounding_box()
            assert box is not None and box['height'] >= 48
        label = f'patienten-{width}-js{javascript}-coarse{coarse}'
        page.screenshot(path=str(tmp_path / f'{label}.png'), full_page=True)
        (tmp_path / f'{label}.json').write_text(json.dumps(measurements, indent=2), encoding='utf-8')
        assert methods and set(methods) == {'GET'}
