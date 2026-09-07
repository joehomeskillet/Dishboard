"""Outer recipe error boundary; recovery rendering never loads database context."""
from functools import wraps
import re

from flask import current_app, g, make_response, request
from sqlalchemy.exc import SQLAlchemyError
from werkzeug.exceptions import HTTPException

from ..component_catalog_store import ComponentCatalogConfigurationError
from .. import master_data_types as master
from .. import recipe_types as recipe
from ..roles import require_capability
from .recipe_forms import FormError, LocationConflict


def render_form_error(error, *, submitted=None, display_values=None, reload_url='/admin/rezepte'):
    if isinstance(error, HTTPException):
        status = error.code or 500
    elif isinstance(error, (recipe.RecipeStaleActorError, master.StaleActorError)):
        status = 401
    elif isinstance(error, (recipe.RecipeActorDeniedError, master.ActorDeniedError)):
        status = 403
    elif isinstance(error, (recipe.RecipeNotFoundError, master.MasterDataNotFoundError)):
        status = 404
    elif isinstance(error, (recipe.RecipeValidationError, master.MasterDataValidationError)):
        status = 400
    elif isinstance(error, (recipe.RecipeConflictError, master.MasterDataConflictError)):
        status = 409
    else:
        status = 503
    messages = {400: 'Bitte prüfen Sie Ihre Eingaben.', 401: 'Bitte erneut anmelden.',
                403: 'Diese Aktion ist nicht erlaubt.', 404: 'Der Datensatz wurde nicht gefunden.',
                409: 'Zwischenzeitlich geändert. Ihre Eingaben wurden nicht gespeichert.',
                503: 'Rezepte sind momentan nicht verfügbar. Bitte später erneut versuchen.'}
    if isinstance(error, LocationConflict):
        messages[409] = 'Der aktive Standort wurde geändert. Ihre ursprünglichen Eingaben wurden nicht gespeichert.'
    if isinstance(error, FormError):
        messages[400] = str(error)
    if not re.fullmatch(r'/admin/(rezepte|kochbuecher)(/(neu|[0-9a-f-]{36}))?', reload_url):
        reload_url = '/admin/rezepte'
    original = list(request.form.items(multi=True)) if submitted is None else list(submitted)
    if status not in (400, 409):
        original = []
    html = current_app.jinja_env.get_template('admin/rezepte_conflict.html').render(
        status=status, message=messages.get(status, messages[503]), submitted=original,
        display_values=dict(display_values if display_values is not None else getattr(g, 'recipe_form_display_values', {})), error_field=getattr(error, 'field', None),
        reload_url=reload_url,
    )
    response = make_response(html, status)
    response.headers['Cache-Control'] = 'no-store'
    return response


def protected(function):
    @wraps(function)
    def wrapped(*args, **kwargs):
        try:
            capability = 'recipe.write' if request.method == 'POST' else 'draft.read'
            response = make_response(require_capability(capability)(function)(*args, **kwargs))
        except (HTTPException, SQLAlchemyError, ComponentCatalogConfigurationError,
                recipe.RecipeValidationError, recipe.RecipeNotFoundError, recipe.RecipeConflictError,
                recipe.RecipeActorDeniedError, recipe.RecipeConfigurationError, recipe.RecipeUnavailableError,
                master.MasterDataError) as error:
            response = render_form_error(error)
        response.headers['Cache-Control'] = 'no-store'
        return response
    return wrapped
