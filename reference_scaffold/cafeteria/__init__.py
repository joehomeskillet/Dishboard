from __future__ import annotations

import datetime as dt

from flask import Flask
from flask_session import Session
from redis import Redis
from werkzeug.middleware.proxy_fix import ProxyFix

from .config import Config
from .db import init_app_database
from .security import csrf_token

MONTHS = {
    1: 'Januar', 2: 'Februar', 3: 'März', 4: 'April', 5: 'Mai', 6: 'Juni',
    7: 'Juli', 8: 'August', 9: 'September', 10: 'Oktober', 11: 'November', 12: 'Dezember',
}


def _date(value: str) -> dt.date:
    return dt.date.fromisoformat(value)


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config())

    hops = int(app.config.get('TRUSTED_PROXY_HOPS', 1))
    app.wsgi_app = ProxyFix(app.wsgi_app, x_for=hops, x_proto=hops, x_host=hops, x_port=hops)

    redis_url = app.config.get('SESSION_REDIS_URL')
    if redis_url:
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_REDIS'] = Redis.from_url(redis_url)
        app.config['SESSION_USE_SIGNER'] = True
        Session(app)

    init_app_database(app)

    from .public.routes import bp as public_bp
    from .signage.routes import bp as signage_bp
    from .auth.routes import bp as auth_bp
    from .admin.routes import bp as admin_bp
    from .api.routes import bp as api_bp
    from .health.routes import bp as health_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(signage_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(health_bp)

    @app.template_filter('date_long')
    def date_long(value: str) -> str:
        parsed = _date(value)
        return f'{parsed.day}. {MONTHS[parsed.month]} {parsed.year}'

    @app.template_filter('date_short')
    def date_short(value: str) -> str:
        parsed = _date(value)
        return f'{parsed.day}. {MONTHS[parsed.month]}'

    @app.template_filter('chf')
    def chf(value: int) -> str:
        return f'{int(value) / 100:.2f}'

    @app.template_filter('iso_week')
    def iso_week(value: str) -> int:
        return _date(value).isocalendar().week

    @app.context_processor
    def inject_security_helpers():
        return {'csrf_token': csrf_token}

    @app.after_request
    def security_headers(response):
        response.headers.setdefault('X-Content-Type-Options', 'nosniff')
        response.headers.setdefault('Referrer-Policy', 'strict-origin-when-cross-origin')
        response.headers.setdefault('Permissions-Policy', 'camera=(), microphone=(), geolocation=()')
        frame_ancestors = app.config.get('FRAME_ANCESTORS', "'self'")
        if frame_ancestors == "'self'":
            response.headers.setdefault('X-Frame-Options', 'SAMEORIGIN')
        response.headers.setdefault(
            'Content-Security-Policy',
            "default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'; "
            f'frame-ancestors {frame_ancestors}',
        )
        return response

    return app
