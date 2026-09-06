"""Administrator-only logo, palette and typography editor with saved preview."""
from __future__ import annotations

from typing import Any

from flask import abort, flash, g, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.wrappers import Response

from ..branding import (
    BrandingConflictError, BrandingStateError, branding_revision, change_branding, read_branding,
)
from ..branding_assets import MAX_LOGO_BYTES, LogoValidationError, load_logo, normalize_logo
from ..branding_config import FONTS, BrandingValidationError, default_config, validate_config
from ..branding_tokens import branding_css
from ..roles import require_capability
from ..security import csrf_token, validate_csrf
from .rendering import _template_context
from .workflow_routes import _db, bp


def _document() -> dict[str, Any]:
    try:
        with _db().connect() as connection:
            return read_branding(connection)
    except (SQLAlchemyError, BrandingStateError):
        abort(503, description='Markeneinstellungen sind momentan nicht verfügbar.')


def _number(value: str) -> int:
    if not value.isascii() or not value.isdecimal() or len(value) > 10:
        abort(400, description='Versionsnummer ist ungültig.')
    return int(value)


def _selected(document):
    if set(request.args) - {'revision'} or any(len(request.args.getlist(key)) != 1 for key in request.args):
        abort(400)
    revision = _number(request.args['revision']) if 'revision' in request.args else len(document['revisions'])
    try:
        return branding_revision(document, revision)
    except LookupError:
        abort(404)


@bp.route('/design/marke', methods=['GET', 'POST'])
@require_capability('settings.write')
def branding_editor() -> Response:
    document = _document()
    selected = _selected(document)
    values = dict(selected.config)
    name, error, status = selected.name, '', 200
    if request.method == 'POST':
        validate_csrf(request.form.get('_csrf'))
        action = request.form.get('action')
        if request.args or action not in {'save', 'activate', 'restore', 'reset'}:
            abort(400)
        fields = {'_csrf', 'action', 'version'}
        if action == 'save':
            fields.update({'name', *default_config()})
        elif action in {'activate', 'restore'}:
            fields.add('revision')
        if set(request.form) != fields or any(len(request.form.getlist(key)) != 1 for key in request.form):
            abort(400, description='Markenformular ist ungültig.')
        if (set(request.files) - {'logo'} or any(len(request.files.getlist(key)) != 1 for key in request.files)
                or (request.files and action != 'save')):
            abort(400, description='Logoformular ist ungültig.')
        expected = _number(request.form['version'])
        revision = _number(request.form['revision']) if 'revision' in request.form else None
        logo = None
        try:
            if action == 'save':
                values = {key: request.form[key] for key in default_config()}
                values['logo_sha256'] = values['logo_sha256'] or None
                name = request.form['name']
                upload = request.files.get('logo')
                if upload is not None and upload.filename:
                    logo = normalize_logo(upload.stream.read(MAX_LOGO_BYTES + 1))
                    values['logo_sha256'] = logo.sha256
                config = validate_config(values)
            else:
                config = None
            saved = change_branding(_db(), g.auth_user.user_id, g.auth_user.authz_version,
                                    expected, action, name=name, config=config,
                                    revision_id=revision, logo=logo)
        except PermissionError:
            abort(403)
        except BrandingConflictError as issue:
            error, status = str(issue), 409
        except (BrandingValidationError, LogoValidationError, LookupError) as issue:
            error, status = str(issue), 400
        except (SQLAlchemyError, BrandingStateError):
            error, status = 'Speichern ist momentan nicht möglich. Die aktive Marke bleibt erhalten.', 503
        else:
            flash('Marke aktiviert.' if action == 'activate' else 'Entwurf gespeichert. Bitte Vorschau prüfen und anschliessend aktivieren.')
            response = redirect(url_for('admin.branding_editor', revision=revision if action == 'activate' else len(saved['revisions'])), 303)
            response.headers['Cache-Control'] = 'no-store'
            return response
    response = make_response(render_template(
        'admin/branding_editor.html', family='cafeteria', profile='staff_guest', csrf=csrf_token(),
        document=document, selected=selected, brand_values=values, brand_name=name,
        brand_error=error, fonts=FONTS, **_template_context(),
    ), status)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/design/marke/vorschau/<int:revision>')
@require_capability('settings.write')
def branding_preview(revision: int) -> Response:
    if request.args:
        abort(400)
    try:
        selected = branding_revision(_document(), revision)
    except LookupError:
        abort(404)
    response = make_response(render_template('admin/branding_preview.html', brand=selected))
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/design/marke/vorschau/<int:revision>.css')
@require_capability('settings.write')
def branding_preview_css(revision: int) -> Response:
    if request.args:
        abort(400)
    try:
        selected = branding_revision(_document(), revision)
    except LookupError:
        abort(404)
    response = make_response(branding_css(selected.config, url_for('static', filename='').rstrip('/')))
    response.mimetype = 'text/css'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response


@bp.get('/design/marke/logo/<sha256>.png')
@require_capability('settings.write')
def branding_preview_logo(sha256: str) -> Response:
    if request.args or len(sha256) != 64 or any(char not in '0123456789abcdef' for char in sha256):
        abort(404)
    try:
        with _db().connect() as connection:
            asset = load_logo(connection, sha256)
    except LookupError:
        abort(404)
    except SQLAlchemyError:
        abort(503, description='Das Logo ist momentan nicht verfügbar.')
    response = make_response(asset.png)
    response.mimetype = 'image/png'
    response.headers['Cache-Control'] = 'no-store'
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
