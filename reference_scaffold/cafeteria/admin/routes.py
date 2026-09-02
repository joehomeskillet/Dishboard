from __future__ import annotations

import io
from datetime import date, timedelta
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
from ..workflow import (
    PublicationConfigurationError,
    StaleDraftError,
    WorkflowValidationError,
    current_draft_row_version,
    import_draft,
    load_draft,
    publish_draft,
    save_draft,
    validate_publication_fit,
)
from ..workflow_store import get_dietary_labels_and_allergens
from ..workflow_form import ParsedDraft, parse_draft_form, submitted_form_values

bp = Blueprint('admin', __name__, url_prefix='/admin')
PATIENT_FORM_ERROR = 'Patientenformular ist ungültig.'
PATIENT_CSV_ERROR = 'Patienten-CSV ist ungültig.'


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


def _current_week_start() -> date:
    today = effective_today()
    return today - timedelta(days=today.isoweekday() - 1)


def _actor_id() -> int:
    user = session.get('user') or {}
    actor_id = user.get('id')
    if type(actor_id) is not int or actor_id <= 0:
        abort(401)
    return cast(int, actor_id)


def _draft(profile_code: str):
    return load_draft(
        current_app.extensions['cafeteria_db'],
        profile_code,
        _current_week_start(),
        actor_id=_actor_id(),
    )


def _parse_form(profile_code: str) -> ParsedDraft:
    validate_csrf(request.form.get('_csrf'))
    parsed = parse_draft_form(profile_code, request.form)
    if parsed.week_start != _current_week_start():
        raise WorkflowValidationError(
            'Formularwoche stimmt nicht mit dem aktuellen Raster überein.',
            field_name='week_start',
        )
    return parsed


def _render_editor(
    profile_code: str,
    *,
    form_values: dict[str, str] | None = None,
    form_errors: dict[str, str] | None = None,
    form_message: str | None = None,
    first_error: str | None = None,
):
    template = 'admin/patienten.html' if profile_code == 'patient' else 'admin/cafeteria.html'
    # Load master data for form controls
    engine = current_app.extensions["cafeteria_db"]
    with engine.connect() as conn:
        dietary_labels, allergens = get_dietary_labels_and_allergens(conn)

    return render_template(
        template,
        dietary_labels=dietary_labels,
        allergens=allergens,
        draft=_draft(profile_code),
        user=session.get('user'),
        roles=session.get('roles', []),
        form_values=form_values or {},
        form_errors=form_errors or {},
        form_message=form_message,
        first_error=first_error,
    )


def _form_error_response(profile_code: str, error: Exception, status_code: int):
    values = submitted_form_values(profile_code, request.form)
    field_name = getattr(error, 'field_name', None)
    if field_name not in values:
        field_name = None
    first_error = field_name if field_name not in {'week_start', 'row_version'} else None
    message = PATIENT_FORM_ERROR if profile_code == 'patient' else str(error)
    field_message = 'Eingabe prüfen.' if profile_code == 'patient' else str(error)
    return (
        _render_editor(
            profile_code,
            form_values=values,
            form_errors={field_name: field_message} if field_name else {},
            form_message=message,
            first_error=first_error,
        ),
        status_code,
    )


def _save(profile_code: str, endpoint: str, *, publish: bool = False):
    try:
        parsed = _parse_form(profile_code)
        if publish:
            validate_publication_fit(profile_code, parsed.values)
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
        return _form_error_response(profile_code, error, 400)
    except StaleDraftError as error:
        return _form_error_response(profile_code, error, 409)
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
    return _render_editor('staff_guest')


@bp.get('/patienten')
@require_capability('draft.read')
def patienten():
    try:
        return _render_editor('patient')
    except ValueError:
        abort(422, description=PATIENT_FORM_ERROR)


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
