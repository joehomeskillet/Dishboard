"""Order admin has no send button; routes exist."""
from pathlib import Path

from flask import Flask, url_for


def test_templates_have_no_send_action() -> None:
    root = Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates' / 'admin'
    for name in ('bestellung.html', 'bestellung_korb.html'):
        text = (root / name).read_text(encoding='utf-8')
        assert 'BESTELLEN' not in text
        assert 'send_pending' not in text or 'Status' in text


def test_order_home_is_registered() -> None:
    app = Flask('orders')
    from cafeteria.admin.routes import bp
    import cafeteria.admin.order_routes  # noqa: F401
    app.register_blueprint(bp)
    with app.test_request_context():
        assert url_for('admin.order_home') == '/admin/bestellung'
        assert 'csv' in url_for('admin.order_basket_csv', public_id='00000000-0000-4000-8000-000000000001')
        assert url_for('admin.order_basket_from_demand', public_id='00000000-0000-4000-8000-000000000001').endswith('/bedarf')
