from __future__ import annotations

import datetime as dt
from collections.abc import Iterator
from copy import deepcopy
from pathlib import Path
from threading import Thread

import pytest
from flask import Flask, render_template
from playwright.sync_api import Browser, expect
from werkzeug.serving import make_server

from test_menu_images import app  # noqa: F401
from test_rendered_ui import browser  # noqa: F401


@pytest.fixture
def image_server(app: Flask) -> Iterator[str]:  # noqa: F811
    def saved_view(profile: str, view: str) -> str:
        snapshot = deepcopy(app.config['TEST_SNAPSHOTS'][profile])
        snapshot['days'] = [day for day in snapshot['days'] if day['services']]
        for day in snapshot['days']:
            for service in day['services']:
                service.setdefault('service_state', 'open')
        week = dt.date.fromisoformat(snapshot['week_start'])
        rows = [
            {**option, 'id': index, 'service_date': dt.date.fromisoformat(day['date']),
             'week_start': week, 'meal_code': service['meal_code'], 'workflow_state': 'draft'}
            for day in snapshot['days']
            for service in day['services']
            for index, option in enumerate(service['options'])
        ]
        if view == 'preview':
            last = snapshot['days'][-1]['services'][-1]['options'][-1]
            last['description'] = 'Frisch zubereitet mit saisonalem Gemüse. ' * 8
            last['note'] = 'Vollständiger Zubereitungshinweis bleibt sichtbar.'
        return render_template(
            'admin/preview.html' if view == 'preview' else 'admin/menu_collection.html',
            profile=profile, family='cafeteria' if profile == 'staff_guest' else 'patienten',
            query='', page=1, has_next=False, roles=[], rows=rows,
            meal_labels={'LUNCH': 'Mittag', 'DINNER': 'Abend'},
            option_labels={'MENU_1': 'Menü 1', 'VEGGIE': 'Vegetarisch'},
            state='draft', week=week, week_iso=week.isoformat(), draft=snapshot,
        )

    app.add_url_rule('/__images/<profile>/<view>', view_func=saved_view)
    app.config['DEMO_TODAY'] = '2026-08-31'
    server = make_server('127.0.0.1', 0, app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()


@pytest.mark.parametrize('path', [
    '/cafeteria/heute/', '/cafeteria/wochenangebot/',
    '/patienten/heute/', '/patienten/wochenplan/',
    '/__images/staff_guest/menus', '/__images/patient/menus',
    '/__images/staff_guest/preview', '/__images/patient/preview',
])
def test_local_images_fit_compact_phone_and_tablets_without_clipping(
    browser: Browser, image_server: str, path: str, tmp_path: Path,  # noqa: F811
) -> None:
    with browser.new_context(base_url=image_server, java_script_enabled=False) as context:
        page = context.new_page()
        for width, height in [(360, 800), (390, 844), (768, 1024), (1024, 768)]:
            page.set_viewport_size({'width': width, 'height': height})
            response = page.goto(path)
            assert response is not None and response.status == 200
            page.evaluate('document.fonts.ready')
            photos = page.locator('.menu-photo')
            assert photos.count() > 0
            first = photos.first.locator('img')
            first.scroll_into_view_if_needed()
            expect(first).to_be_visible()
            page.wait_for_function(
                'document.querySelector(".menu-photo img").naturalWidth === 1200'
            )
            assert photos.evaluate_all('''figures => figures.every(figure => {
                const image = figure.querySelector('img');
                const box = image.getBoundingClientRect();
                return box.width > 0 && box.height > 0 &&
                    Math.abs(box.width / box.height - 1200 / 896) < 0.01 &&
                    image.getAttribute('loading') === 'lazy' &&
                    image.getAttribute('src').startsWith('/static/img/menus/') &&
                    figure.scrollWidth <= figure.clientWidth + 1;
            })''')
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            if path.endswith('/preview'):
                cards = page.locator('.preview-option')
                expect(cards.last).to_contain_text('Vollständiger Zubereitungshinweis bleibt sichtbar.')
                geometry = cards.evaluate_all('''cards => cards.map(card => ({
                    width: card.getBoundingClientRect().width,
                    height: card.getBoundingClientRect().height,
                    visible: card.scrollHeight <= card.clientHeight + 1 &&
                             card.scrollWidth <= card.clientWidth + 1
                }))''')
                assert all(card['visible'] for card in geometry)
                for axis in ('width', 'height'):
                    sizes = [card[axis] for card in geometry]
                    assert max(sizes) - min(sizes) <= 1, (path, width, axis, sizes)
            if width in (360, 768):
                page.screenshot(path=str(tmp_path / f'menu-images-{width}.png'), full_page=True)
            page.emulate_media(media='print')
            expect(photos.first).to_be_hidden()
            page.emulate_media(media='screen')
