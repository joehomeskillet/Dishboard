"""Inventory UI never shows a fake zero stock."""
from pathlib import Path

from flask import Flask, url_for


def test_lager_template_unknown_label() -> None:
    text = (Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin' / 'lager.html').read_text(encoding='utf-8')
    assert 'Kein Bestand erfasst' in text
    assert 'BESTELLEN' not in text
    assert 'admin.inventory_transfer' in text
    assert 'admin.inventory_count' in text
    assert 'Umbuchung' in text
    assert 'Zählung' in text
    assert 'Zuordnungen aus Grundlagen' in text
    assert 'admin.master_data_detail' in text
    assert 'admin.inventory_home' in text
    assert 'Zutat-UUID' not in text
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
