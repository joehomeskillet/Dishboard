from __future__ import annotations

from flask import Flask
from flask_session import Session
from redis import Redis

from .config import Config
from .db import init_app_database
from .security import csrf_token
from .template_filters import register_template_filters


def create_app() -> Flask:
    app = Flask(__name__, instance_relative_config=False)
    app.config.from_object(Config())
    register_template_filters(app)

    redis_url = app.config.get('SESSION_REDIS_URL')
    redis_client = None
    if redis_url:
        redis_client = Redis.from_url(redis_url)
        app.config['SESSION_TYPE'] = 'redis'
        app.config['SESSION_REDIS'] = redis_client
        app.config['SESSION_USE_SIGNER'] = True
        Session(app)
    app.extensions['cafeteria_rate_redis'] = redis_client

    init_app_database(app)

    from .public.routes import bp as public_bp
    from .signage.routes import bp as signage_bp
    from .auth.routes import bp as auth_bp
    from .admin.workflow_routes import bp as admin_bp
    from .admin import menu_collection_routes  # noqa: F401 - register collection routes
    from .admin import week_management_routes  # noqa: F401 - register week management
    from .api.routes import bp as api_bp
    from .health.routes import bp as health_bp

    app.register_blueprint(public_bp)
    app.register_blueprint(signage_bp)
    app.register_blueprint(auth_bp)
    app.register_blueprint(admin_bp)
    app.register_blueprint(api_bp)
    app.register_blueprint(health_bp)

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
