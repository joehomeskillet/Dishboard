"""Tabler properties editor with saved-revision PDF preview and explicit activation."""
from __future__ import annotations

from datetime import date
from functools import wraps
from typing import Any

from flask import abort, current_app, flash, g, make_response, redirect, render_template, request, url_for
from sqlalchemy.exc import NoResultFound, SQLAlchemyError
from werkzeug.wrappers import Response

from ..component_catalog_store import ComponentCatalogConfigurationError
from ..branding import BrandingStateError
from ..print_branding import load_pdf_branding
from ..print_template_config import (
    CHOICES, LAYOUT_BINDINGS, LAYOUT_CHOICES, LAYOUT_LABELS, TEXT_LIMITS, PrintTemplateConfig,
    PrintTemplateValidationError, default_config, default_layout, validate_config, validate_layout,
)
from ..print_templates import (
    PrintTemplateConflictError, PrintTemplateStateError, change_template, read_templates, template_revision,
)
from ..roles import require_capability
from ..security import csrf_token, validate_csrf
from ..workflow_store import load_draft_connection
from .rendering import _template_context
from .week_pdf import WeekPdfFitError, render_week_pdf
from .workflow_routes import _db, _exact, _version_field, _week_arg, bp, profile_from_endpoint


LAYOUT_OPTIONS = {
    'grid': ('Wochenraster', {'days_rows': 'Tage untereinander', 'days_columns': 'Tage nebeneinander'}),
    'photo': ('Menübilder', {'none': 'Ohne Bilder', 'small': 'Kleine Bilder', 'medium': 'Mittlere Bilder'}),
    'alignment': ('Textausrichtung', {'left': 'Linksbündig', 'center': 'Zentriert'}),
    'day_label_width': ('Breite der Tagesbeschriftung', {'compact': 'Schmal', 'standard': 'Standard', 'wide': 'Breit'}),
    'row_spacing': ('Abstand zwischen Menüzeilen', {'compact': 'Kompakt', 'standard': 'Standard', 'roomy': 'Grosszügig'}),
    'legend_position': ('Position der Legende', {'top': 'Über dem Wochenraster', 'bottom': 'Unter dem Wochenraster'}),
}


def _layout_form_values(profile: str, config: PrintTemplateConfig) -> dict[str, str]:
    layout: dict[str, Any] = dict(config.get('layout', default_layout(profile)))
    values = {'layout_mode': 'preserve', **{f'layout_{key}': str(layout[key]) for key in LAYOUT_CHOICES}}
    for group in LAYOUT_BINDINGS:
        values.update({f'layout_{group}_{index}': value for index, value in enumerate(layout[group])})
    return values


def _save_config(profile: str, template_id: str, revision_id: int, required: set[str]) -> PrintTemplateConfig:
    values: dict[str, Any] = {key: request.form.get(key, '') for key in default_config()}
    layout_fields = _layout_form_values(profile, default_config())
    if not any(key.startswith('layout_') for key in request.form):
        _exact(required)
        return validate_config(values, profile)
    expected = required | layout_fields.keys()
    if set(request.form) != expected or any(len(request.form.getlist(key)) != 1 for key in expected):
        raise PrintTemplateValidationError('Bitte das vollständige Layoutformular einmal senden.', 'layout_mode')
    mode = request.form['layout_mode']
    if mode not in {'preserve', 'custom'}:
        raise PrintTemplateValidationError('Bitte wählen, ob das Layout angepasst werden soll.', 'layout_mode')
    layout: dict[str, Any] = {'version': 1}
    layout.update({key: request.form[f'layout_{key}'] for key in LAYOUT_CHOICES})
    for group in LAYOUT_BINDINGS:
        names = [key for key in layout_fields if key.startswith(f'layout_{group}_')]
        layout[group] = [request.form[key] for key in names]
    try:
        checked = validate_layout(layout, profile)
    except PrintTemplateValidationError as error:
        field = f'layout_{error.field}'
        if error.field in LAYOUT_BINDINGS:
            field += '_0'
        raise PrintTemplateValidationError(str(error), field) from error
    original = _selected(_document(profile), template_id, revision_id)['config']
    if mode == 'custom':
        values['layout'] = checked
    elif checked != original.get('layout', default_layout(profile)):
        raise PrintTemplateValidationError(
            'Layouteinstellungen wurden geändert. Bitte «Eigenes Layout speichern» auswählen.', 'layout_mode')
    elif 'layout' in original:
        values['layout'] = original['layout']
    return validate_config(values, profile)


def _database_available(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            return function(*args, **kwargs)
        except SQLAlchemyError:
            # Do not run context processors or retry database reads after a failed transaction.
            html = current_app.jinja_env.get_template('admin/print_template_unavailable.html').render()
            response = make_response(html, 503)
            response.headers['Cache-Control'] = 'no-store'
            return response
    return wrapped


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


def _pdf(profile: str, week: date, config: PrintTemplateConfig) -> tuple[bytes, int | None]:
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
    layout_values = _layout_form_values(profile, revision['config'])
    expected = document['version']
    if error and request.form.get('action') == 'save':
        values.update({key: request.form.get(key, values[key]) for key in ('name', *default_config())})
        layout_values.update({key: request.form.get(key, value) for key, value in layout_values.items()})
    if error:
        expected = request.form.get('version', expected)
    preview_error = None
    try:
        _pdf(profile, week, revision['config'])
    except NoResultFound:
        preview_error = 'Für diese Woche sind noch keine gespeicherten Menüs vorhanden. Bitte zuerst die Woche anlegen.'
    except (ComponentCatalogConfigurationError, WeekPdfFitError, BrandingStateError, PrintTemplateValidationError) as fit_error:
        preview_error = str(fit_error)
    response = make_response(render_template(
        'admin/print_template_editor.html', family=family, profile=profile, week=week.isoformat(),
        document=document, template=template, revision=revision, values=values, expected_version=expected,
        choices=CHOICES, text_limits=TEXT_LIMITS, error=error, error_field=error_field,
        layout_values=layout_values, layout_options=LAYOUT_OPTIONS, layout_labels=LAYOUT_LABELS,
        layout_groups={key: dict(default_layout(profile))[key] for key in LAYOUT_BINDINGS},
        error_action=request.form.get('action') if error else None,
        copy_name=request.form.get('name', '') if error and request.form.get('action') == 'copy' else revision['name'][:50] + ' · Kopie',
        preview_error=preview_error, csrf=csrf_token(), **_template_context(),
    ), status)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.route('/vorlagen/<any(cafeteria, patienten):family>', methods=['GET', 'POST'])
@_database_available
@require_capability('settings.write')
def print_template_editor(family: str) -> Response:
    week, template_id, revision_id = _arguments()
    if request.method == 'GET':
        return _render_editor(family, week, template_id, revision_id)
    if request.content_length is not None and request.content_length > 16_384:
        abort(413, description='Das Vorlagenformular ist zu gross.')
    validate_csrf(request.form.get('_csrf'))
    action = request.form.get('action')
    required = {'_csrf', 'action', 'version', 'revision'}
    if action == 'save':
        required |= {'name', *default_config()}
    elif action == 'copy':
        required.add('name')
    elif action not in {'restore', 'activate', 'archive', 'reactivate'}:
        abort(400, description='Vorlagenaktion ist ungültig.')
    profile = profile_from_endpoint(family)
    if any(len(request.form.getlist(key)) != 1 for key in ('_csrf', 'action', 'version', 'revision')):
        abort(400, description='Formularfelder sind ungültig.')
    form_revision = _version_field('revision')
    if form_revision < 1:
        abort(400, description='Revisionsnummer ist ungültig.')
    try:
        config = _save_config(profile, template_id, form_revision, required) if action == 'save' else None
        if action != 'save':
            _exact(required)
        _, selected_id = change_template(
            _db(), profile, g.auth_user.user_id, g.auth_user.authz_version,
            _version_field('version'), template_id, str(action), revision_id=form_revision,
            name=request.form.get('name'), week=week,
            config=config,
        )
    except PermissionError:
        abort(403)
    except (PrintTemplateStateError, BrandingStateError) as error:
        abort(503, description=str(error))
    except (PrintTemplateValidationError, PrintTemplateConflictError, WeekPdfFitError, NoResultFound) as error:
        status = 409 if isinstance(error, PrintTemplateConflictError) else 422 if isinstance(error, WeekPdfFitError) else 400
        message = 'Aktivierung benötigt eine gespeicherte Woche. Bitte zuerst die Woche anlegen.' if isinstance(error, NoResultFound) else str(error)
        return _render_editor(family, week, template_id, form_revision, error=message,
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
        'archive': 'Vorlage archiviert. Alle Revisionen und PDF-Vorschauen bleiben erhalten.',
        'reactivate': 'Vorlage wieder verfügbar. Die aktive Druckvorlage bleibt bestehen.',
    }
    flash(messages[str(action)])
    response = redirect(url_for(
        'admin.print_template_editor', family=family, week=week.isoformat(), template=selected_id,
        revision=request.form['revision'] if action in {'archive', 'reactivate'} else None,
    ), 303)
    response.headers['Cache-Control'] = 'no-store'
    return response


@bp.get('/vorlagen/<any(cafeteria, patienten):family>/vorschau.pdf')
@_database_available
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
    except (WeekPdfFitError, PrintTemplateValidationError) as error:
        abort(422, description=str(error))
    return Response(payload, mimetype='application/pdf', headers={
        'Cache-Control': 'no-store',
        'Content-Disposition': f'inline; filename="vorlage-{family}-{week.isoformat()}.pdf"',
        'X-Print-Template-Revision': f'{template_id}:{revision["id"]}',
        **({'X-Brand-Revision': str(brand_revision)} if brand_revision is not None else {}),
    })
