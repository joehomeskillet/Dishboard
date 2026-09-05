from __future__ import annotations

import io
from typing import cast

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
from ..template_filters import register_template_filters
from ..workflow import (
    StaleDraftError,
    WorkflowValidationError,
    current_draft_row_version,
    import_draft,
)

bp = Blueprint('admin', __name__, url_prefix='/admin')
PATIENT_CSV_ERROR = 'Patienten-CSV ist ungültig.'


@bp.record_once
def _register_template_filters(state) -> None:
    register_template_filters(state.app)


def snapshot(profile_code: str):
    try:
        return active_snapshot(
            current_app.extensions['cafeteria_db'],
            profile_code,
            effective_today().isoformat(),
            last_good_dir=current_app.config['LAST_GOOD_DIR'],
        )
    except ValueError:
        return None


def _actor_id() -> int:
    user = session.get('user') or {}
    actor_id = user.get('id')
    if type(actor_id) is not int or actor_id <= 0:
        abort(401)
    return cast(int, actor_id)


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
            profile_code = str(result['profile'])
            week_start = result['week_start']
            signed_token = serializer.dumps(
                {
                    'text': result['text'],
                    'profile_code': profile_code,
                    'week_start': week_start.isoformat(),
                    'expected_row_version': current_draft_row_version(
                        current_app.extensions['cafeteria_db'],
                        profile_code,
                        week_start,
                    ),
                }
            )
            import_token = signed_token.encode('ascii').hex()
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
        signed_token = bytes.fromhex(request.form['import_token']).decode('ascii')
        token_payload = serializer.loads(signed_token, max_age=15 * 60)
    except (BadData, UnicodeDecodeError, ValueError):
        abort(400, description='Importvorschau ist ungültig oder abgelaufen.')
    if not isinstance(token_payload, dict) or set(token_payload) != {
        'text',
        'profile_code',
        'week_start',
        'expected_row_version',
    }:
        abort(400, description='Importvorschau ist ungültig.')
    text_value = token_payload['text']
    token_profile = token_payload['profile_code']
    token_week_start = token_payload['week_start']
    expected_row_version = token_payload['expected_row_version']
    if (
        not isinstance(text_value, str)
        or token_profile not in {'patient', 'staff_guest'}
        or not isinstance(token_week_start, str)
        or type(expected_row_version) is not int
        or expected_row_version < 0
    ):
        abort(400, description='Importvorschau ist ungültig.')
    result = validate_upload(io.BytesIO(text_value.encode('utf-8')))
    if not result['valid']:
        abort(
            400,
            description=PATIENT_CSV_ERROR if token_profile == 'patient' else 'CSV-Datei ist ungültig.',
        )
    profile_code = str(result['profile'])
    week_start = result['week_start']
    if profile_code != token_profile or week_start.isoformat() != token_week_start:
        abort(400, description='Importvorschau ist ungültig.')
    try:
        import_draft(
            current_app.extensions['cafeteria_db'],
            profile_code,
            week_start,
            expected_row_version=expected_row_version,
            actor_id=_actor_id(),
            values=result['values'],
        )
    except (WorkflowValidationError, ValueError) as error:
        abort(
            400,
            description=PATIENT_CSV_ERROR if profile_code == 'patient' else str(error),
        )
    except StaleDraftError as error:
        abort(409, description=str(error))
    endpoint = 'admin.patienten' if profile_code == 'patient' else 'admin.cafeteria'
    return redirect(url_for(endpoint), code=303)
