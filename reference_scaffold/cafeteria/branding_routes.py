"""Same-origin public brand resources and a last-known valid rendering context."""
from __future__ import annotations

import re
from dataclasses import dataclass

from flask import Blueprint, abort, current_app, make_response, request, url_for
from sqlalchemy import Engine
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.wrappers import Response

from .branding import BrandingStateError, branding_revision, default_document, public_revision, read_branding
from .branding_assets import LogoAsset, load_logo
from .branding_config import BrandRevision, validate_config
from .branding_tokens import branding_css

bp = Blueprint('branding', __name__, url_prefix='/branding')


@dataclass(frozen=True)
class _BrandingBundle:
    revision_id: int
    name: str
    # Validated branding tokens are scalar strings/None. Capture them as an
    # immutable tuple instead of sharing a mutable context/config dictionary.
    tokens: tuple[tuple[str, object], ...]
    logo: LogoAsset | None

    @property
    def brand(self) -> BrandRevision:
        return BrandRevision(self.revision_id, self.name, validate_config(dict(self.tokens)))


def _cached_bundle() -> _BrandingBundle | None:
    cached = current_app.extensions.get('branding_bundle')
    return cached if isinstance(cached, _BrandingBundle) else None


@bp.app_context_processor
def branding_context() -> dict[str, object]:
    engine = current_app.extensions.get('cafeteria_db')
    if isinstance(engine, Engine):
        try:
            with engine.connect() as connection:
                document = read_branding(connection)
                selected = public_revision(document, document['active_revision'])
                logo = load_logo(connection, selected.config['logo_sha256']) if selected.config['logo_sha256'] else None
            # One reference exchange publishes the revision and its logo together.
            current_app.extensions['branding_bundle'] = _BrandingBundle(
                selected.id, selected.name, tuple(selected.config.items()), logo,
            )
            return {'brand': selected}
        except (SQLAlchemyError, BrandingStateError, LookupError):
            # This cosmetic fallback must not break or extend publication LastGood.
            current_app.logger.warning('Markenstatus nicht verfügbar; zuletzt gültige Marke wird angezeigt.')
    cached = _cached_bundle()
    return {'brand': cached.brand if cached else branding_revision(default_document(), 1)}


def _public_brand(revision: int) -> BrandRevision:
    if revision == 1:
        return branding_revision(default_document(), 1)
    try:
        with current_app.extensions['cafeteria_db'].connect() as connection:
            return public_revision(read_branding(connection), revision)
    except (SQLAlchemyError, BrandingStateError):
        cached = _cached_bundle()
        if cached is not None and cached.revision_id == revision:
            return cached.brand
        return abort(503)
    except LookupError:
        return abort(404)


@bp.get('/revisions/<int:revision>.css')
def stylesheet(revision: int) -> Response:
    if request.args:
        abort(400)
    brand = _public_brand(revision)
    response = make_response(branding_css(brand.config, url_for('static', filename='').rstrip('/')))
    response.mimetype = 'text/css'
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.set_etag(f'branding-{revision}')
    return response.make_conditional(request)


@bp.get('/logos/<sha256>.png')
def logo(sha256: str) -> Response:
    if request.args or not re.fullmatch('[0-9a-f]{64}', sha256):
        abort(404)
    try:
        with current_app.extensions['cafeteria_db'].connect() as connection:
            document = read_branding(connection)
            if not any(item['published'] and item['config']['logo_sha256'] == sha256 for item in document['revisions']):
                abort(404)
            asset = load_logo(connection, sha256)
    except (SQLAlchemyError, BrandingStateError):
        cached = _cached_bundle()
        if cached is None or cached.logo is None or cached.logo.sha256 != sha256:
            return abort(503)
        asset = cached.logo
    except LookupError:
        abort(404)
    response = make_response(asset.png)
    response.mimetype = 'image/png'
    response.headers['Cache-Control'] = 'public, max-age=31536000, immutable'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.set_etag(sha256)
    return response.make_conditional(request)
