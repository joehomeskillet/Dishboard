"""Inventory UI never shows a fake zero stock."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from flask import Flask, url_for
from playwright.sync_api import expect, sync_playwright

from test_master_data_browser import master_server  # noqa: F401
from test_master_data_db import STORAGE_PUBLIC_ID
from test_master_data_routes import (  # noqa: F401
    app_engine,
    b3,
    create,
    installed_pg16,
    pg16,
    seeded_pg16,
)

MOVE_FIELDS = ('_csrf', 'food_public_id', 'storage_public_id', 'kind', 'quantity', 'unit_code')
TRANSFER_FIELDS = (
    '_csrf', 'food_public_id', 'source_storage_public_id', 'dest_storage_public_id',
    'quantity', 'unit_code',
)
COUNT_FIELDS = ('_csrf', 'food_public_id', 'storage_public_id', 'counted_quantity', 'unit_code')


def test_lager_template_unknown_label() -> None:
    text = (Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin' / 'lager.html').read_text(encoding='utf-8')
    assert 'Kein Bestand erfasst' in text
    assert 'BESTELLEN' not in text
    assert 'admin.inventory_transfer' in text
    assert 'admin.inventory_count' in text
    assert 'Umbuchung' in text
    assert 'Zählung' in text
    assert 'Zuordnungen' in text
    assert 'status_items=lager_status' in text
    assert 'admin-lager.css' in text
    assert 'admin.master_data_detail' in text
    assert 'admin.inventory_home' in text
    assert 'Zutat-UUID' not in text
    assert 'row_version' not in text
    food = (Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin' / 'grundlagen_food.html').read_text(encoding='utf-8')
    assert 'admin.inventory_home' in food
    assert 'food_public_id' in food


def test_inventory_routes_registered() -> None:
    app = Flask('lager')
    from cafeteria.admin.routes import bp
    import cafeteria.admin.inventory_routes  # noqa: F401
    app.register_blueprint(bp)
    with app.test_request_context():
        assert url_for('admin.inventory_home') == '/admin/lager'
        assert url_for('admin.inventory_transfer') == '/admin/lager/umbuchung'
        assert url_for('admin.inventory_count') == '/admin/lager/zaehlung'
        lookup = url_for('admin.inventory_home', food_public_id='abc', storage_public_id='def')
        assert 'food_public_id=abc' in lookup
        assert 'storage_public_id=def' in lookup


def test_lager_statusbar_viewports_nojs_and_keyboard(b3, master_server, tmp_path):  # noqa: F811
    """Own sync_playwright start: 360/768/1024/1440, No-JS, keyboard, POST field names."""
    _, _, client, _ = b3
    base, cookie = master_server
    measurements = []
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for javascript in (False, True):
                for width in (360, 768, 1024, 1440):
                    metric = _open_lager(instance, base, cookie, '/admin/lager', width, javascript)
                    measurements.append(dict(state='empty', width=width, javascript=javascript, **metric))
                    assert metric['overflow'] is False
                    assert metric['primary'] == 1
                    assert metric['open'] == 0
            food_id = urlsplit(create(client, name='Lagermehl')).path.rstrip('/').rsplit('/', 1)[-1]
            other_storage = urlsplit(create(
                client, 'lagerorte', name='Zweitlager', code='SECOND', sort_order='2',
            )).path.rstrip('/').rsplit('/', 1)[-1]
            create(client, name='Zweitzutat', storage_location_public_ids=other_storage)
            selected = f'/admin/lager?food_public_id={food_id}&storage_public_id={STORAGE_PUBLIC_ID}'
            for javascript in (False, True):
                for width in (360, 768, 1024, 1440):
                    with instance.new_context(
                        viewport={'width': width, 'height': 900},
                        java_script_enabled=javascript,
                    ) as context:
                        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
                        page = context.new_page()
                        page.goto(base + selected, wait_until='networkidle')
                        metric = page.evaluate('''() => ({
                            height: document.documentElement.scrollHeight,
                            row: document.querySelector('.lager-row')?.getBoundingClientRect().height ?? 0,
                            primary: document.querySelectorAll('main .btn-primary').length,
                            open: document.querySelectorAll('main details[open]').length,
                            overflow: document.documentElement.scrollWidth > innerWidth + 1
                        })''')
                        measurements.append(dict(state='selected', width=width, javascript=javascript, **metric))
                        assert metric['overflow'] is False
                        assert metric['primary'] == 1
                        assert metric['open'] == 0
                        if width == 1440:
                            assert metric['row'] < 100
                        expect(page.locator('.admin-statusbar')).to_be_visible()
                        expect(page.locator('.admin-statusbar')).to_contain_text('Kein Bestand erfasst')
                        expect(page.locator('.admin-statusbar')).to_contain_text('Lagermehl')
                        expect(page.locator('.lager-row a.active')).to_have_attribute('aria-current', 'true')
                        move = _form_fields(page, '#lager-move-form')
                        transfer = _form_fields(page, '#lager-transfer-form')
                        count = _form_fields(page, '#lager-count-form')
                        assert [name for name, _ in move] == list(MOVE_FIELDS)
                        assert [name for name, _ in transfer] == list(TRANSFER_FIELDS)
                        assert [name for name, _ in count] == list(COUNT_FIELDS)
                        assert dict(move)['food_public_id'] == food_id
                        assert dict(move)['storage_public_id'] == STORAGE_PUBLIC_ID
                        assert dict(move)['kind'] == 'receipt'
                        assert dict(transfer)['source_storage_public_id'] == STORAGE_PUBLIC_ID
                        assert dict(transfer)['dest_storage_public_id'] == other_storage
                        assert dict(count)['food_public_id'] == food_id
                        for control in page.locator('main :is(.btn, .form-control, .form-select)').all():
                            if control.is_visible():
                                box = control.bounding_box()
                                assert box is not None and box['height'] >= 48
                        if width == 1440 and javascript:
                            quantity = page.locator('#quantity')
                            quantity.focus()
                            expect(quantity).to_be_focused()
                            focus = page.locator(':focus').evaluate(
                                'el => { const s = getComputedStyle(el); return [s.outlineStyle, s.boxShadow]; }'
                            )
                            assert focus[0] != 'none' or focus[1] != 'none'
                            page.keyboard.press('Tab')
                            expect(page.locator('#unit_code')).to_be_focused()
                            summary = page.locator('#lager-more > summary')
                            summary.focus()
                            page.keyboard.press('Enter')
                            expect(page.locator('#dest_storage_public_id')).to_be_visible()
                            expect(page.locator('#counted_quantity')).to_be_visible()
                            expect(page.locator('#lager-transfer-form .btn-primary')).to_have_count(0)
                            expect(page.locator('#lager-count-form .btn-primary')).to_have_count(0)
                        if width == 360 and not javascript:
                            page.locator('#lager-more > summary').click()
                            expect(page.locator('#dest_storage_public_id')).to_be_visible()
                            expect(page.locator('#counted_quantity')).to_be_visible()
                            print('WP12_FIELDS', json.dumps({
                                'move': move, 'transfer': transfer, 'count': count,
                            }, ensure_ascii=False))
            print('WP12_MEASUREMENTS', json.dumps(measurements))
            (tmp_path / 'measurements.json').write_text(json.dumps(measurements, indent=2), encoding='utf-8')
        finally:
            instance.close()


def _open_lager(instance, base: str, cookie, path: str, width: int, javascript: bool) -> dict:
    with instance.new_context(
        viewport={'width': width, 'height': 900},
        java_script_enabled=javascript,
    ) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': base}])
        page = context.new_page()
        page.goto(base + path, wait_until='networkidle')
        expect(page.locator('.admin-statusbar')).to_be_visible()
        expect(page.locator('.admin-statusbar')).to_contain_text('Kein Bestand erfasst')
        expect(page.get_by_role('link', name='Zutaten').first).to_be_visible()
        metric = page.evaluate('''() => ({
            height: document.documentElement.scrollHeight,
            row: document.querySelector('.lager-row')?.getBoundingClientRect().height ?? 0,
            primary: document.querySelectorAll('main .btn-primary').length,
            open: document.querySelectorAll('main details[open]').length,
            overflow: document.documentElement.scrollWidth > innerWidth + 1
        })''')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        return metric


def _form_fields(page, selector: str) -> list[list[str]]:
    return page.locator(selector).evaluate('''form => [...new FormData(form)].map(([name, value]) =>
        [name, name === '_csrf' ? '<token>' : value])''')
