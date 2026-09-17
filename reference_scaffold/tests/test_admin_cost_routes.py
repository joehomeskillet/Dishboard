"""Kalkulation routes exist; preview has no BESTELLEN; missing price stays incomplete."""
from pathlib import Path

from flask import Flask, url_for


def test_kalkulation_template_preview_not_send() -> None:
    text = (Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin' / 'kalkulation.html').read_text(encoding='utf-8')
    assert 'Vorschau schreibt nichts' in text
    assert 'unvollständig, nie 0' in text
    assert 'BESTELLEN' not in text
    assert 'admin.cost_preview' in text
    assert 'admin.cost_confirm' in text
    assert 'menu_revision_public_id' in text


def test_cost_routes_registered() -> None:
    app = Flask('cost')
    from cafeteria.admin.routes import bp
    import cafeteria.admin.cost_routes  # noqa: F401
    app.register_blueprint(bp)
    with app.test_request_context():
        assert url_for('admin.cost_home') == '/admin/kalkulation'
        assert url_for('admin.cost_preview') == '/admin/kalkulation/vorschau'
        assert url_for('admin.cost_confirm') == '/admin/kalkulation/beleg'
