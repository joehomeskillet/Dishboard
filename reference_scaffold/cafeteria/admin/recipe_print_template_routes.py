"""Native recipe-template forms over the shared revisioned template store."""
from __future__ import annotations

from functools import wraps
import re
from typing import Any

from flask import abort, current_app, flash, g, make_response, redirect, render_template, request, url_for
from sqlalchemy import text
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException
from werkzeug.wrappers import Response

from .. import recipe_store as recipes
from ..branding import BrandingStateError
from ..component_catalog_store import ComponentCatalogConfigurationError
from ..print_branding import load_pdf_branding
from ..print_template_config import CHOICES, TEXT_LIMITS, PrintTemplateValidationError, default_config, validate_config
from ..print_templates import (
    IDENTIFIER, PrintTemplateConflictError, PrintTemplateStateError, change_template, read_templates,
)
from ..quantities import QuantityError, parse_quantity
from ..recipe_reads import recipe_print_input
from ..recipe_types import RecipeConfigurationError, RecipeNotFoundError, RecipeRevisionDTO, RecipeUnavailableError, RecipeValidationError
from ..recipe_values import identifier
from ..roles import require_capability
from ..security import csrf_token, validate_csrf
from .print_template_routes import _document, _selected
from .recipe_pdf import RECIPE_MARGINS, RecipePdfError, render_recipe_pdf
from .rendering import _template_context
from .workflow_routes import _db, _exact, _version_field, bp

SELECTION = {'template', 'revision', 'recipe', 'recipe_revision', 'yield'}
CHOOSER = {'q', 'page', 'revision_page', 'archived'}


def _protected(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            response = make_response(require_capability('settings.write')(function)(*args, **kwargs))
        except (SQLAlchemyError, ComponentCatalogConfigurationError, PrintTemplateStateError,
                BrandingStateError, RecipeConfigurationError, RecipeUnavailableError):
            html = current_app.jinja_env.get_template('admin/print_template_unavailable.html').render()
            response = make_response(html, 503)
        except HTTPException as error:
            response = make_response(error.get_response())
        except (RecipeNotFoundError, RecipeValidationError, PrintTemplateValidationError, RecipePdfError) as error:
            status = 404 if isinstance(error, RecipeNotFoundError) else 422 if isinstance(error, RecipePdfError) else 400
            html = current_app.jinja_env.get_template('admin/recipe_template_error.html').render(message=str(error))
            response = make_response(html, status)
        response.headers['Cache-Control'] = 'no-store'
        return response
    return wrapped


def _arguments(*, preview: bool = False) -> dict[str, str]:
    allowed = SELECTION if preview or request.method == 'POST' else SELECTION | CHOOSER
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        abort(400, description='Ungültige oder mehrfach gesendete Vorlagenparameter.')
    values = request.args.to_dict()
    values.setdefault('template', 'standard')
    if IDENTIFIER.fullmatch(values['template']) is None:
        raise RecipeValidationError('Ungültige Vorlagenkennung.')
    if 'revision' in values and re.fullmatch(r'[1-9][0-9]?', values['revision']) is None:
        raise RecipeValidationError('Ungültige Vorlagenrevision.')
    for field in ('recipe', 'recipe_revision'):
        if field in values:
            values[field] = identifier(values[field])
    if 'recipe_revision' in values and 'recipe' not in values:
        raise RecipeValidationError('Bitte zuerst ein Rezept auswählen.')
    for field in ('page', 'revision_page'):
        if field in values and re.fullmatch(r'[1-9][0-9]{0,5}', values[field]) is None:
            raise RecipeValidationError('Ungültige Auswahlseite.')
    if values.get('archived', '0') not in {'0', '1'} or len(values.get('q', '')) > 200 or '\x00' in values.get('q', ''):
        raise RecipeValidationError('Ungültige Rezeptsuche.')
    if 'yield' in values:
        try:
            parse_quantity(values['yield'])
        except QuantityError as error:
            raise RecipeValidationError(f'Gewünschte Ausbeute: {error}') from None
    return values


def _url(arguments: dict[str, str], **changes: Any) -> str:
    values: dict[str, Any] = {key: value for key, value in arguments.items() if key in SELECTION}
    values.update(changes)
    return url_for('admin.recipe_print_template_editor', **values)


def _pdf(arguments: dict[str, str]) -> tuple[bytes, dict[str, str], RecipeRevisionDTO]:
    if not all(key in arguments for key in ('recipe', 'recipe_revision')):
        raise RecipeValidationError('Bitte ein Rezept und eine festgeschriebene Revision auswählen.')
    with _db().connect().execution_options(isolation_level='REPEATABLE READ') as connection:
        with connection.begin():
            connection.execute(text('SET TRANSACTION READ ONLY'))
            document = read_templates(connection, 'recipe')
            selected = _selected(document, arguments['template'], int(arguments['revision']) if 'revision' in arguments else None)
            try:
                revision, assets = recipe_print_input(connection, arguments['recipe'], arguments['recipe_revision'])
            except RecipeValidationError:
                raise RecipeConfigurationError('Gespeicherte Rezeptrevision ist ungültig.') from None
            branding = load_pdf_branding(connection, 'recipe', selected['config'])
    data = render_recipe_pdf(revision, config=selected['config'], images=assets,
                             target=arguments.get('yield'), branding=branding)
    headers = {
        'X-Print-Template-Revision': f'{arguments["template"]}:{selected["id"]}',
        'X-Recipe-Revision': revision.public_id, 'X-Recipe-Content-SHA256': revision.content_hash_sha256,
        'Content-Disposition': f'inline; filename="rezeptvorlage-{revision.public_id}.pdf"',
    }
    if branding is not None:
        headers['X-Brand-Revision'] = str(branding.revision_id)
    return data, headers, revision


def _render_editor(arguments: dict[str, str], *, error=None, status: int = 200, selected_revision: int | None = None) -> Response:
    document = _document('recipe')
    revision = _selected(document, arguments['template'], selected_revision if selected_revision is not None
                         else int(arguments['revision']) if 'revision' in arguments else None)
    template = next(item for item in document['templates'] if item['id'] == arguments['template'])
    values = {'name': revision['name'], **revision['config']}
    expected = document['version']
    if error is not None:
        expected = request.form.get('version', expected)
        if request.form.get('action') == 'save':
            values.update({key: request.form.get(key, values[key]) for key in ('name', *default_config())})
    page = int(arguments.get('page', '1'))
    revision_page = int(arguments.get('revision_page', '1'))
    rows = recipes.list_recipes(_db(), search=arguments.get('q'), include_archived=arguments.get('archived') == '1',
                                limit=51, offset=(page - 1) * 50)
    recipe = recipes.get_recipe(_db(), arguments['recipe']) if 'recipe' in arguments else None
    revisions = recipes.list_revisions(_db(), recipe.public_id, limit=51, offset=(revision_page - 1) * 50) if recipe else ()
    preview_error: str | None = 'Bitte ein Rezept und eine festgeschriebene Revision für die Vorschau auswählen.'
    recipe_revision = None
    preview_arguments: dict[str, Any] = {key: value for key, value in arguments.items() if key in SELECTION}
    preview_arguments['revision'] = str(revision['id'])
    if 'recipe_revision' in arguments:
        try:
            _, _, recipe_revision = _pdf(preview_arguments)
            preview_error = None
        except RecipePdfError as fit_error:
            preview_error = str(fit_error)
    choices = {**CHOICES, 'margin': {key: f'{CHOICES["margin"][key].split(" · ")[0]} · {value:g} pt'
                                    for key, value in RECIPE_MARGINS.items()},
               'text_size': {'auto': 'Automatisch · 11 pt', 'standard': 'Standard · 11 pt', 'large': 'Gross · 12 pt'}}
    active_url = None
    if recipe_revision is not None and 'admin.recipe_revision_pdf' in current_app.view_functions:
        target_query: dict[str, Any] = {'yield': arguments['yield']} if 'yield' in arguments else {}
        active_url = url_for('admin.recipe_revision_pdf', recipe_id=recipe_revision.recipe_public_id,
                             revision_id=recipe_revision.public_id, **target_query)
    return make_response(render_template(
        'admin/print_template_editor.html', recipe_editor=True, family='cafeteria', profile='recipe',
        document=document, template=template, revision=revision, values=values, expected_version=expected,
        choices=choices, text_limits=TEXT_LIMITS, error=str(error) if error else None,
        error_field=getattr(error, 'field', 'form'), error_action=request.form.get('action') if error else None,
        copy_name=request.form.get('name', '') if error and request.form.get('action') == 'copy' else revision['name'][:50] + ' · Kopie',
        preview_error=preview_error, csrf=csrf_token(), recipe=recipe, recipe_revision=recipe_revision,
        arguments=arguments, recipe_rows=rows[:50], recipe_page=page, recipe_has_next=len(rows) > 50,
        recipe_revisions=revisions[:50], revision_page=revision_page, revision_has_next=len(revisions) > 50,
        recipe_url=lambda **changes: _url(arguments, **changes),
        editor_url=_url(arguments, revision=None), preview_url=url_for('admin.recipe_print_template_preview', **preview_arguments),
        active_recipe_url=active_url, **_template_context(),
    ), status)


@bp.route('/vorlagen/rezepte', methods=['GET', 'POST'])
@_protected
def recipe_print_template_editor() -> Response:
    arguments = _arguments()
    if request.method == 'GET':
        return _render_editor(arguments)
    if request.content_length is not None and request.content_length > 16_384:
        abort(413, description='Das Vorlagenformular ist zu gross.')
    validate_csrf(request.form.get('_csrf'))
    if request.files:
        abort(400, description='Die Druckvorlage nimmt keine Dateien entgegen.')
    action = request.form.get('action')
    required = {'_csrf', 'action', 'version', 'revision'}
    if action == 'save':
        required |= {'name', *default_config()}
    elif action == 'copy':
        required.add('name')
    elif action not in {'restore', 'activate', 'archive', 'reactivate'}:
        abort(400, description='Vorlagenaktion ist ungültig.')
    _exact(required)
    selected_revision = _version_field('revision')
    if not 1 <= selected_revision <= 50:
        abort(400, description='Vorlagenrevision ist ungültig.')
    try:
        config = validate_config({key: request.form[key] for key in default_config()}, 'recipe') if action == 'save' else None
        if action == 'activate' and not all(key in arguments for key in ('recipe', 'recipe_revision')):
            raise PrintTemplateValidationError('Bitte zuerst ein Rezept und eine festgeschriebene Revision auswählen.')
        _, selected_id = change_template(
            _db(), 'recipe', g.auth_user.user_id, g.auth_user.authz_version, _version_field('version'),
            arguments['template'], str(action), revision_id=selected_revision, name=request.form.get('name'), config=config,
            recipe_public_id=arguments.get('recipe'), recipe_revision_public_id=arguments.get('recipe_revision'),
            target_yield=arguments.get('yield'),
        )
    except PermissionError:
        abort(403)
    except (PrintTemplateValidationError, PrintTemplateConflictError, RecipePdfError) as error:
        status = 409 if isinstance(error, PrintTemplateConflictError) else 422 if isinstance(error, RecipePdfError) else 400
        return _render_editor(arguments, error=error, status=status, selected_revision=selected_revision)
    except LookupError:
        abort(404, description='Vorlagenrevision nicht gefunden.')
    messages = {
        'save': 'Entwurf gespeichert. Die aktive Druckvorlage bleibt bestehen.',
        'copy': 'Vorlagenkopie als Entwurf erstellt.',
        'restore': 'Frühere Revision als neuer Entwurf wiederhergestellt. Zum Drucken ausdrücklich aktivieren.',
        'activate': 'Vorlage mit dieser Rezeptrevision geprüft und für künftige Rezept-PDFs aktiviert.',
        'archive': 'Vorlage archiviert. Alle Revisionen bleiben erhalten.',
        'reactivate': 'Vorlage wieder verfügbar. Die aktive Druckvorlage bleibt bestehen.',
    }
    flash(messages[str(action)])
    return redirect(_url(arguments, template=selected_id, revision=selected_revision if action in {'archive', 'reactivate'} else None), 303)


@bp.get('/vorlagen/rezepte/vorschau.pdf')
@_protected
def recipe_print_template_preview() -> Response:
    data, headers, _ = _pdf(_arguments(preview=True))
    return Response(data, mimetype='application/pdf', headers=headers)
