"""Complete OPS output geometry through the real local HTTP/CSP application."""
from __future__ import annotations

import json
from copy import deepcopy

import pytest

from test_public_mobile_ui import http_app as http_app
from test_public_mobile_ui import public_server as public_server
from test_rendered_ui import app as app
from test_rendered_ui import browser as browser
from test_week_pdf import saved_week


def ops_snapshot(application, profile, days=7):
    """Published snapshot with an area name, serving times and complete menu notes."""
    snapshot = application.config['TEST_SNAPSHOTS'][profile]
    snapshot['area_name'] = (
        'Restaurant für Mitarbeitende und Gäste' if profile == 'staff_guest'
        else 'Schülerinnen und Schüler'
    )
    if profile == 'staff_guest':
        for offset in (5, 6):
            day = snapshot['days'][offset]
            day['services'] = deepcopy(snapshot['days'][offset - 5]['services']) if offset < days else []
            day['state'] = 'open' if day['services'] else 'closed'
    source = saved_week(profile)['days']
    for index, day in enumerate(snapshot['days']):
        for service in day['services']:
            service['service_start'] = '11:30' if service['meal_code'] == 'LUNCH' else '17:30'
            service['service_end'] = '13:30' if service['meal_code'] == 'LUNCH' else '18:30'
            notes = next(s for s in source[index % len(source)]['services'] if s['meal_code'] == service['meal_code'])
            for option, original in zip(service['options'], notes['options'], strict=True):
                option['note'] = original['note']
    application.config['DEMO_TODAY'] = snapshot['days'][min(days, 7) - 1]['date']
    return snapshot


def card_geometry(page, selector):
    """Box of every card plus whether any of its content leaves that box."""
    return page.locator(selector).evaluate_all('''elements => elements.map(e => {
      const r=e.getBoundingClientRect();
      const outside=[...e.querySelectorAll('h3,h4,p,[data-menu-metadata],footer')].some(child=>{
        const b=child.getBoundingClientRect();return b.left<r.left-1||b.right>r.right+1||b.bottom>r.bottom+1;
      });
      return {width:r.width,height:r.height,top:r.top,bottom:r.bottom,left:r.left,right:r.right,
        clipped:outside||e.scrollWidth>e.clientWidth+1||e.scrollHeight>e.clientHeight+1};})''')


CASES = [(path, 'staff_guest', count) for path in (
    '/cafeteria/wochenangebot/', '/cafeteria/wochenangebot/ohne-bilder/', '/druck/cafeteria/woche',
) for count in (5, 6, 7)] + [(path, 'patient', 7) for path in (
    '/patienten/heute/', '/patienten/wochenplan/', '/patienten/wochenplan/ohne-bilder/', '/druck/patienten/woche',
)]


@pytest.mark.parametrize('path,profile,days', CASES)
def test_full_ops_web_and_html_print_keep_equal_readable_cards(
        http_app, public_server, browser, tmp_path, path, profile, days):
    snapshot = ops_snapshot(http_app, profile, days)
    original = deepcopy(snapshot)
    selected = snapshot['days'][-1:] if path.endswith('/heute/') else snapshot['days']
    options = [option for day in selected for service in day['services'] for option in service['options']]
    selector = '.week-menu:has([data-menu-metadata])' if path.startswith('/druck/') else '.card:has(>.card-status-top)'
    with browser.new_context(java_script_enabled=False) as context:
        page = context.new_page()
        for width, height in ((390, 844), (820, 1180), (1440, 1100)):
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto(public_server + path, wait_until='networkidle')
            assert response and response.status == 200
            assert "style-src 'self'" in response.headers['content-security-policy']
            assert "script-src 'self'" in response.headers['content-security-policy']
            page.evaluate('document.fonts.ready')
            cards = page.locator(selector)
            assert cards.count() == len(options)
            for card, option in zip(cards.all(), options, strict=True):
                text = card.inner_text()
                for expected in (option['title'], option['note'], *option['components']):
                    assert expected in text
            geometry = card_geometry(page, selector)
            stem = f'{path.strip("/").replace("/", "-")}-{days}-{width}'
            (tmp_path / f'{stem}.json').write_text(json.dumps(geometry, indent=2))
            page.screenshot(path=str(tmp_path / f'{stem}.png'), full_page=True)
            for axis in ('width', 'height'):
                assert max(row[axis] for row in geometry) - min(row[axis] for row in geometry) <= 1, (axis, geometry)
            assert not any(row['clipped'] for row in geometry), geometry
            for index, left in enumerate(geometry):
                for right in geometry[index + 1:]:
                    assert min(left['right'], right['right']) - max(left['left'], right['left']) <= 1 or min(left['bottom'], right['bottom']) - max(left['top'], right['top']) <= 1
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            assert snapshot['area_name'] in page.locator('body').text_content()
            if profile == 'patient':
                assert 'CHF' not in page.locator('body').inner_text()
    assert snapshot == original
