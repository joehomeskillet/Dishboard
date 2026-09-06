"""Tabler properties editor with saved-revision PDF preview and explicit activation."""
from __future__ import annotations

from datetime import date
from typing import Any

from flask import abort, flash, g, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import NoResultFound
from werkzeug.wrappers import Response

from ..component_catalog_store import ComponentCatalogConfigurationError
from ..branding import BrandingStateError
from ..print_branding import load_pdf_branding
from ..print_template_config import CHOICES, TEXT_LIMITS, PrintTemplateValidationError, default_config
from ..print_templates import (
    PrintTemplateConflictError, PrintTemplateStateError, change_template, read_templates, template_revision,
)
from ..roles import require_capability
from ..security import csrf_token, validate_csrf
from ..workflow_store import load_draft_connection
from .rendering import _template_context
from .week_pdf import WeekPdfFitError, render_week_pdf
from .workflow_routes import _db, _exact, _version_field, _week_arg, bp, profile_from_endpoint


def _arguments() -> tuple[date, str, int | None]:
    if set(request.args) - {'week', 'template', 'revision'} or any(
        len(request.args.getlist(key)) != 1 for key in request.args
    ):
        abort(400, description='Für Vorlagen sind nur Woche, Vorlage und Revision erlaubt.')
    raw = request.args.get('revision')
    if raw is not None and (not raw.isascii() or not raw.isdigit() or len(raw) > 2 or int(raw) < 1):
        abort(400, description='Revisionsnummer ist ungültig.')
    return _week_arg(), request.args.get('template', 'standard'), int(raw) if raw is not None else None


def _document(profile: str) -> dict[str, Any]:
    try:
        with _db().connect() as connection:
            return read_templates(connection, profile)
    except PrintTemplateStateError as error:
        return abort(503, description=str(error))


def _selected(document: dict[str, Any], template_id: str, revision_id: int | None) -> dict[str, Any]:
    try:
        return template_revision(document, template_id, revision_id)
    except LookupError:
        return abort(404, description='Vorlagenrevision nicht gefunden.')


def _pdf(profile: str, week: date, config: dict[str, str]) -> tuple[bytes, int | None]:
    with _db().connect() as connection:
        draft = load_draft_connection(connection, profile, week)
        branding = load_pdf_branding(connection, profile, config)
    return render_week_pdf(draft, profile, week, config, branding=branding), branding.revision_id if branding else None


def _render_editor(
    family: str, week: date, template_id: str, revision_id: int | None,
    *, error: str | None = None, error_field: str = 'form', status: int = 200,
) -> Response:
    profile = profile_from_endpoint(family)
    document = _document(profile)
    revision = _selected(document, template_id, revision_id)
    template = next(item for item in document['templates'] if item['id'] == template_id)
    values = {'name': revision['name'], **revision['config']}
    expected = document['version']
    if error and request.form.get('action') == 'save':
        values.update({key: request.form.get(key, values[key]) for key in values})
    if error:
        expected = request.form.get('version', expected)
    preview_error = None
    try:
        _pdf(profile, week, revision['config'])
    except NoResultFound:
        preview_error = 'Für diese Woche sind noch keine gespeicherten Menüs vorhanden. Bitte zuerst die Woche anlegen.'
    except (ComponentCatalogConfigurationError, WeekPdfFitError, BrandingStateError) as fit_error:
        preview_error = str(fit_error)
    response = make_response(render_template(
        'admin/print_template_editor.html', family=family, profile=profile, week=week.isoformat(),
        document=document, template=template, revision=revision, values=values, expected_version=expected,
        choices=CHOICES, text_limits=TEXT_LIMITS, error=error, error_field=error_field,
        error_action=request.form.get('action') if error else None,
        copy_name=request.form.get('name', '') if error and request.form.get('action') == 'copy' else revision['name'][:50] + ' · Kopie',
        preview_error=preview_error, csrf=csrf_token(), **_template_context(),
    ), status)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.route('/vorlagen/<any(cafeteria, patienten):family>', methods=['GET', 'POST'])
@require_capability('settings.write')
def print_template_editor(family: str) -> Response:
    week, template_id, revision_id = _arguments()
    if request.method == 'GET':
        return _render_editor(family, week, template_id, revision_id)
    validate_csrf(request.form.get('_csrf'))
    action = request.form.get('action')
    required = {'_csrf', 'action', 'version', 'revision'}
    if action == 'save':
        required |= {'name', *default_config()}
    elif action == 'copy':
        required.add('name')
    elif action not in {'restore', 'activate'}:
        abort(400, description='Vorlagenaktion ist ungültig.')
    _exact(required)
    profile = profile_from_endpoint(family)
    try:
        _, selected_id = change_template(
            _db(), profile, g.auth_user.user_id, g.auth_user.authz_version,
            _version_field('version'), template_id, str(action), revision_id=_version_field('revision'),
            name=request.form.get('name'), week=week,
            config={key: request.form[key] for key in default_config()} if action == 'save' else None,
        )
    except PermissionError:
        abort(403)
    except (PrintTemplateStateError, BrandingStateError) as error:
        abort(503, description=str(error))
    except (PrintTemplateValidationError, PrintTemplateConflictError, WeekPdfFitError, NoResultFound) as error:
        status = 409 if isinstance(error, PrintTemplateConflictError) else 422 if isinstance(error, WeekPdfFitError) else 400
        message = 'Aktivierung benötigt eine gespeicherte Woche. Bitte zuerst die Woche anlegen.' if isinstance(error, NoResultFound) else str(error)
        return _render_editor(family, week, template_id, revision_id, error=message,
                              error_field=getattr(error, 'field', 'form'), status=status)
    except ComponentCatalogConfigurationError as error:
        abort(503, description=str(error))
    except LookupError:
        abort(404, description='Vorlagenrevision nicht gefunden.')
    messages = {
        'save': 'Entwurf gespeichert. Die aktive Druckausgabe bleibt bestehen.',
        'copy': 'Vorlagenkopie als Entwurf erstellt.',
        'restore': 'Frühere Revision als neuer Entwurf wiederhergestellt. Zum Drucken ausdrücklich aktivieren.',
        'activate': 'Vorlage für diese Woche geprüft und für künftige PDF-Downloads aktiviert.',
    }
    flash(messages[str(action)])
    response = redirect(url_for('admin.print_template_editor', family=family, week=week.isoformat(), template=selected_id), 303)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/vorlagen/<any(cafeteria, patienten):family>/vorschau.pdf')
@require_capability('settings.write')
def print_template_preview(family: str) -> Response:
    week, template_id, revision_id = _arguments()
    profile = profile_from_endpoint(family)
    revision = _selected(_document(profile), template_id, revision_id)
    try:
        payload, brand_revision = _pdf(profile, week, revision['config'])
    except NoResultFound:
        abort(404, description='Bitte zuerst die gewählte Woche speichern.')
    except (ComponentCatalogConfigurationError, BrandingStateError) as error:
        abort(503, description=str(error))
    except WeekPdfFitError as error:
        abort(422, description=str(error))
    return Response(payload, mimetype='application/pdf', headers={
        'Cache-Control': 'no-store',
        'Content-Disposition': f'inline; filename="vorlage-{family}-{week.isoformat()}.pdf"',
        'X-Print-Template-Revision': f'{template_id}:{revision["id"]}',
        **({'X-Brand-Revision': str(brand_revision)} if brand_revision is not None else {}),
    })
