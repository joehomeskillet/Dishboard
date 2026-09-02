from __future__ import annotations

import io
from datetime import date, timedelta

from flask import (
    Blueprint,
    abort,
    current_app,
    make_response,
    redirect,
    render_template,
    request,
    session,
    url_for,
)
from itsdangerous import BadData, URLSafeTimedSerializer

from ..csvio import snapshot_to_csv, validate_upload
from ..db import active_snapshot
from ..public.routes import effective_today
from ..roles import require_capability
from ..security import validate_csrf
from ..workflow import (
    PublicationConfigurationError,
    StaleDraftError,
    WorkflowValidationError,
    load_draft,
    publish_draft,
    save_draft,
)
from ..workflow_form import ParsedDraft, parse_draft_form

bp = Blueprint('admin', __name__, url_prefix='/admin')


def snapshot(profile_code: str):
    return active_snapshot(
        current_app.extensions['cafeteria_db'],
        profile_code,
        effective_today().isoformat(),
        last_good_dir=current_app.config['LAST_GOOD_DIR'],
    )


def _current_week_start() -> date:
    today = effective_today()
    return today - timedelta(days=today.isoweekday() - 1)


def _actor_id() -> int:
    user = session.get('user') or {}
    actor_id = user.get('id')
    if type(actor_id) is not int or actor_id <= 0:
        abort(401)
    return actor_id


def _draft(profile_code: str):
    return load_draft(
        current_app.extensions['cafeteria_db'],
        profile_code,
        _current_week_start(),
        actor_id=_actor_id(),
    )


def _parse_form() -> ParsedDraft:
    validate_csrf(request.form.get('_csrf'))
    profile_code = 'patient' if request.path.startswith('/admin/patienten') else 'staff_guest'
    try:
        parsed = parse_draft_form(profile_code, request.form)
    except WorkflowValidationError as error:
        abort(400, description=str(error))
    if parsed.week_start != _current_week_start():
        abort(400, description='Formularwoche stimmt nicht mit dem aktuellen Raster überein.')
    return parsed


def _save(profile_code: str, endpoint: str, *, publish: bool = False):
    parsed = _parse_form()
    try:
        row_version = save_draft(
            current_app.extensions['cafeteria_db'],
            profile_code,
            parsed.week_start,
            expected_row_version=parsed.row_version,
            actor_id=_actor_id(),
            values=parsed.values,
        )
        if publish:
            publish_draft(
                current_app.extensions['cafeteria_db'],
                profile_code,
                parsed.week_start,
                expected_row_version=row_version,
                actor_id=_actor_id(),
                issuer_engine=current_app.extensions.get('cafeteria_auth_issuer_db'),
            )
    except (WorkflowValidationError, ValueError) as error:
        abort(400, description=str(error))
    except StaleDraftError as error:
        abort(409, description=str(error))
    except PublicationConfigurationError as error:
        abort(503, description=str(error))
    return redirect(url_for(endpoint), code=303)


@bp.get('/')
@require_capability('draft.read')
def dashboard():
    return redirect(url_for('admin.cafeteria'))


@bp.get('/cafeteria')
@require_capability('draft.read')
def cafeteria():
    return render_template(
        'admin/cafeteria.html',
        draft=_draft('staff_guest'),
        user=session.get('user'),
        roles=session.get('roles', []),
    )


@bp.get('/patienten')
@require_capability('draft.read')
def patienten():
    try:
        draft = _draft('patient')
    except ValueError as error:
        abort(422, description=str(error))
    return render_template(
        'admin/patienten.html',
        draft=draft,
        user=session.get('user'),
        roles=session.get('roles', []),
    )


@bp.post('/cafeteria/save')
@require_capability('draft.write')
def save_cafeteria():
    return _save('staff_guest', 'admin.cafeteria')


@bp.post('/cafeteria/publish')
@require_capability('publication.publish')
def publish_cafeteria():
    return _save('staff_guest', 'admin.cafeteria', publish=True)


@bp.post('/patienten/save')
@require_capability('draft.write')
def save_patienten():
    return _save('patient', 'admin.patienten')


@bp.post('/patienten/publish')
@require_capability('publication.publish')
def publish_patienten():
    return _save('patient', 'admin.patienten', publish=True)


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
    import_token = None
    if request.method == 'POST':
        validate_csrf(request.form.get('_csrf'))
        upload = request.files.get('file')
        if upload is None or not upload.filename:
            abort(400, description='CSV-Datei fehlt.')
        result = validate_upload(upload.stream)
        if result['valid']:
            serializer = URLSafeTimedSerializer(
                current_app.secret_key,
                salt='dishboard-csv-import-v1',
            )
            import_token = serializer.dumps(result['text'])
    return render_template(
        'admin/import_preview.html',
        result=result,
        import_token=import_token,
        user=session.get('user'),
        roles=session.get('roles', []),
    )


@bp.post('/import')
@require_capability('csv.import')
def import_csv():
    validate_csrf(request.form.get('_csrf'))
    if set(request.form) != {'_csrf', 'import_token'}:
        abort(400, description='Importformular ist ungültig.')
    serializer = URLSafeTimedSerializer(
        current_app.secret_key,
        salt='dishboard-csv-import-v1',
    )
    try:
        text_value = serializer.loads(request.form['import_token'], max_age=15 * 60)
    except BadData:
        abort(400, description='Importvorschau ist ungültig oder abgelaufen.')
    if not isinstance(text_value, str):
        abort(400, description='Importvorschau ist ungültig.')
    result = validate_upload(io.BytesIO(text_value.encode('utf-8')))
    if not result['valid']:
        abort(400, description='CSV-Datei ist nicht mehr gültig.')
    profile_code = str(result['profile'])
    week_start = result['week_start']
    draft = load_draft(
        current_app.extensions['cafeteria_db'],
        profile_code,
        week_start,
        actor_id=_actor_id(),
    )
    try:
        save_draft(
            current_app.extensions['cafeteria_db'],
            profile_code,
            week_start,
            expected_row_version=draft['row_version'],
            actor_id=_actor_id(),
            values=result['values'],
        )
    except (WorkflowValidationError, ValueError) as error:
        abort(400, description=str(error))
    except StaleDraftError as error:
        abort(409, description=str(error))
    endpoint = 'admin.patienten' if profile_code == 'patient' else 'admin.cafeteria'
    return redirect(url_for(endpoint), code=303)
