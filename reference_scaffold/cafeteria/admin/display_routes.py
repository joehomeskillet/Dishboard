"""Central Tabler display settings; the existing Admin wildcard grants access."""
from __future__ import annotations

from flask import abort, flash, g, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..display_settings import (
    ADMIN_DISPLAY_CHOICES, DEFAULT_ADMIN_DISPLAY, get_admin_display, set_admin_display,
)
from ..roles import capabilities, require_capability
from ..security import csrf_token, validate_csrf
from .rendering import _template_context
from .workflow_routes import _db, bp


@bp.context_processor
def display_context() -> dict[str, object]:
    return {**get_admin_display(_db()), 'can_configure_display': '*' in capabilities()}


@bp.route('/design/darstellung', methods=['GET', 'POST'])
@require_capability('settings.write')
def display_settings() -> Response:
    if request.args:
        abort(400, description='Die Darstellung benötigt keine URL-Parameter.')
    values = get_admin_display(_db())
    errors = {}
    preview = False
    if request.method == 'POST':
        validate_csrf(request.form.get('_csrf'))
        if set(request.form) != {'_csrf', 'action', *ADMIN_DISPLAY_CHOICES} or any(
            len(request.form.getlist(key)) != 1 for key in request.form
        ):
            abort(400, description='Darstellungsformular ist ungültig.')
        action = request.form['action']
        if action not in {'preview', 'save', 'reset'}:
            abort(400, description='Darstellungsaktion ist ungültig.')
        values = {key: request.form[key] for key in ADMIN_DISPLAY_CHOICES}
        errors = {key: 'Bitte eine der angebotenen Optionen auswählen.' for key, value in values.items()
                  if value not in ADMIN_DISPLAY_CHOICES[key]}
        if not errors and action != 'preview':
            if action == 'reset':
                values = DEFAULT_ADMIN_DISPLAY.copy()
            try:
                set_admin_display(_db(), g.auth_user.user_id, g.auth_user.authz_version, values)
            except PermissionError:
                abort(403)
            flash('Standardwerte für alle Benutzer und Geräte gespeichert.' if action == 'reset'
                  else 'Darstellung für alle Benutzer und Geräte gespeichert.')
            response = redirect(url_for('admin.display_settings'), 303)
            response.headers['Cache-Control'] = 'no-store'
            return response
        preview = not errors
    response = make_response(render_template(
        'admin/display_settings.html', family='cafeteria', profile='staff_guest',
        csrf=csrf_token(), display_values=values, display_errors=errors,
        display_preview=preview, **_template_context(),
    ), 400 if errors else 200)
    response.headers['Cache-Control'] = 'no-store'
    return response
