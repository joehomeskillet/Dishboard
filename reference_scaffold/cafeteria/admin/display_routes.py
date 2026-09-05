"""Central Tabler display settings; the existing Admin wildcard grants access."""
from __future__ import annotations

from flask import abort, flash, g, make_response, redirect, render_template, request, url_for
from werkzeug.wrappers import Response

from ..display_settings import ADMIN_DENSITIES, get_admin_density, set_admin_density
from ..roles import capabilities, require_capability
from ..security import csrf_token, validate_csrf
from .rendering import _template_context
from .workflow_routes import _db, bp


@bp.context_processor
def display_context() -> dict[str, object]:
    return {'admin_density': get_admin_density(_db()), 'can_configure_display': '*' in capabilities()}


@bp.route('/design/darstellung', methods=['GET', 'POST'])
@require_capability('settings.write')
def display_settings() -> Response:
    if request.args:
        abort(400, description='Die Darstellung benötigt keine URL-Parameter.')
    error = None
    if request.method == 'POST':
        validate_csrf(request.form.get('_csrf'))
        if set(request.form) != {'_csrf', 'admin_density'} or any(
            len(request.form.getlist(key)) != 1 for key in request.form
        ):
            abort(400, description='Darstellungsformular ist ungültig.')
        value = request.form['admin_density']
        if value not in ADMIN_DENSITIES:
            error = 'Bitte Kompakt oder Komfortabel auswählen.'
        else:
            try:
                set_admin_density(_db(), g.auth_user.user_id, g.auth_user.authz_version, value)
            except PermissionError:
                abort(403)
            flash('Darstellung für alle Benutzer und Geräte gespeichert.')
            response = redirect(url_for('admin.display_settings'), 303)
            response.headers['Cache-Control'] = 'no-store'
            return response
    response = make_response(render_template(
        'admin/display_settings.html', family='cafeteria', profile='staff_guest',
        csrf=csrf_token(), density_error=error, **_template_context(),
    ), 400 if error else 200)
    response.headers['Cache-Control'] = 'no-store'
    return response
