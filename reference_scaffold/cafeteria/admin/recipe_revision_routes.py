"""Original-context revision commands and immutable, read-only recipe views."""
from __future__ import annotations

import re
from collections.abc import Mapping
from uuid import UUID

from flask import Response, abort, current_app, redirect, render_template, request, url_for
from sqlalchemy import text

from .. import recipe_store as store
from ..branding import BrandingStateError
from ..master_data_types import ObjectExpectation
from ..print_branding import load_pdf_branding
from ..print_template_config import PrintTemplateValidationError
from ..print_templates import PrintTemplateStateError, active_template
from ..quantities import QuantityError, parse_quantity
from ..recipe_reads import recipe_print_input
from ..recipe_types import RecipeConfigurationError, RecipeValidationError
from ..roles import capabilities
from . import recipe_forms as forms
from .recipe_errors import protected
from .recipe_pdf import RecipePdfError, render_recipe_pdf
from .recipe_scaling import scaled_recipe
from .routes import bp


def query_fields(allowed: set[str]) -> None:
    if set(request.args) - allowed or any(len(request.args.getlist(key)) != 1 for key in request.args):
        raise forms.FormError('Ungültige Vorschauparameter.')


def render_scaled(template: str, payload: Mapping[str, object], **context):
    context.update(family='cafeteria', profile='staff_guest')
    try:
        calculated = scaled_recipe(payload, request.args.get('yield'))
    except forms.FormError as error:
        return render_template(template, payload=payload, calculated=scaled_recipe(payload),
                               target_value=request.args.get('yield'), error=str(error), **context), 400
    return render_template(template, payload=payload, calculated=calculated, **context)


@bp.get('/rezepte/<uuid:recipe_id>/revisionen')
@protected
def recipe_revisions(recipe_id: UUID):
    query_fields({'page'})
    raw = request.args.get('page', '1')
    if not re.fullmatch(r'[1-9][0-9]{0,5}', raw):
        raise forms.FormError('Ungültige Revisionsseite.', 'page')
    page = int(raw)
    engine = current_app.extensions['cafeteria_db']
    location = store.get_location(engine)
    row = store.get_recipe(engine, str(recipe_id))
    revisions = store.list_revisions(engine, row.public_id, limit=51, offset=(page - 1) * 50)
    writable = row.active and bool(capabilities() & {'*', 'recipe.write'})
    token = forms.sign_context(action='recipe.freeze', target=ObjectExpectation(row.public_id, row.row_version),
                               expected_location_id=location, display_values={'recipe': str(row.payload['title'])}) if writable else None
    return render_template('admin/rezepte_revisionen.html', family='cafeteria', profile='staff_guest', recipe=row, revisions=revisions[:50],
                           page=page, has_next=len(revisions) > 50, token=token)


@bp.post('/rezepte/<uuid:recipe_id>/revisionen')
@protected
def recipe_freeze(recipe_id: UUID):
    query_fields(set())
    expected = forms.read_context(action='recipe.freeze', target_public_id=str(recipe_id))
    if set(request.form) != {'_csrf', '_form_context', 'row_version'} or request.files or expected.target is None:
        raise forms.FormError('Unerwartete Felder beim Festschreiben.')
    result = store.freeze_revision(current_app.extensions['cafeteria_db'], expected.actor, expected.target,
                                   expected_location_id=expected.expected_location_id)
    return redirect(url_for('admin.recipe_revision', recipe_id=result.recipe_public_id,
                            revision_id=result.public_id), code=303)


@bp.get('/rezepte/<uuid:recipe_id>/revisionen/<uuid:revision_id>')
@protected
def recipe_revision(recipe_id: UUID, revision_id: UUID):
    query_fields({'yield'})
    revision = store.get_revision(current_app.extensions['cafeteria_db'], str(revision_id))
    if revision.recipe_public_id != str(recipe_id):
        abort(404)
    payload = revision.snapshot.get('recipe')
    if not isinstance(payload, Mapping):
        raise RecipeConfigurationError('Revisionsstand nicht verfügbar.')
    return render_scaled('admin/rezepte_revision.html', payload, revision=revision, recipe_id=str(recipe_id))


@bp.get('/rezepte/<uuid:recipe_id>/revisionen/<uuid:revision_id>/druck.pdf')
@protected
def recipe_revision_pdf(recipe_id: UUID, revision_id: UUID) -> Response:
    query_fields({'yield'})
    target = request.args.get('yield')
    if target is not None:
        try:
            parse_quantity(target)
        except QuantityError as error:
            raise forms.FormError(str(error), 'yield') from None
    engine = current_app.extensions['cafeteria_db']
    try:
        with engine.connect().execution_options(isolation_level='REPEATABLE READ') as connection:
            with connection.begin():
                connection.execute(text('SET TRANSACTION READ ONLY'))
                revision, assets = recipe_print_input(connection, str(recipe_id), str(revision_id))
                config, template_revision = active_template(connection, 'recipe')
                branding = load_pdf_branding(connection, 'recipe', config)
        data = render_recipe_pdf(revision, config=config, images=assets, target=target, branding=branding)
    except (PrintTemplateStateError, PrintTemplateValidationError, BrandingStateError, RecipeValidationError):
        raise RecipeConfigurationError('Gespeicherte Rezeptdruckdaten sind nicht verfügbar.') from None
    except RecipePdfError:
        abort(422)
    response = Response(data, mimetype='application/pdf')
    response.headers['Content-Disposition'] = f'inline; filename="rezept-{recipe_id}-{revision_id}.pdf"'
    response.headers['X-Print-Template-Revision'] = template_revision
    response.headers['X-Recipe-Revision'] = revision.public_id
    response.headers['X-Recipe-Content-SHA256'] = revision.content_hash_sha256
    if branding is not None:
        response.headers['X-Brand-Revision'] = str(branding.revision_id)
    return response


@bp.get('/rezepte/<uuid:recipe_id>/skalierung')
@protected
def recipe_scale(recipe_id: UUID):
    query_fields({'yield'})
    row = store.get_recipe(current_app.extensions['cafeteria_db'], str(recipe_id))
    return render_scaled('admin/rezepte_scale.html', row.payload, recipe=row, recipe_id=row.public_id)
