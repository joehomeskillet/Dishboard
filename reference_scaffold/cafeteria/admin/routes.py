from __future__ import annotations

from flask import Blueprint, current_app, make_response, redirect, render_template, request, session, url_for

from ..csvio import snapshot_to_csv, validate_upload
from ..db import active_snapshot
from ..public.routes import effective_today
from ..roles import require_capability
from ..security import validate_csrf

bp = Blueprint('admin', __name__, url_prefix='/admin')


def snapshot(profile_code: str):
    return active_snapshot(
        current_app.extensions['cafeteria_db'],
        profile_code,
        effective_today().isoformat(),
        last_good_dir=current_app.config['LAST_GOOD_DIR'],
    )


@bp.get('/')
@require_capability('draft.read')
def dashboard():
    return redirect(url_for('admin.cafeteria'))


@bp.get('/cafeteria')
@require_capability('draft.read')
def cafeteria():
    return render_template('admin/cafeteria.html', snapshot=snapshot('staff_guest'), user=session.get('user'), roles=session.get('roles', []))


@bp.get('/patienten')
@require_capability('draft.read')
def patienten():
    return render_template('admin/patienten.html', snapshot=snapshot('patient'), user=session.get('user'), roles=session.get('roles', []))


@bp.get('/export/<profile_code>.csv')
@require_capability('csv.export')
def export_csv(profile_code: str):
    mapping = {'cafeteria': 'staff_guest', 'patienten': 'patient'}
    profile = mapping.get(profile_code)
    if not profile:
        return 'Unbekanntes Profil.', 404
    current = snapshot(profile)
    if current is None:
        return 'Keine publizierte Revision für dieses Profil.', 404
    data = snapshot_to_csv(current)
    response = make_response(data)
    response.headers['Content-Type'] = 'text/csv; charset=utf-8'
    response.headers['Content-Disposition'] = f'attachment; filename="menu-{profile_code}.csv"'
    return response


@bp.route('/import-preview', methods=['GET', 'POST'])
@require_capability('csv.validate')
def import_preview():
    result = None
    if request.method == 'POST':
        validate_csrf(request.form.get('_csrf'))
        if 'file' in request.files:
            result = validate_upload(request.files['file'].stream)
    return render_template('admin/import_preview.html', result=result, user=session.get('user'), roles=session.get('roles', []))
