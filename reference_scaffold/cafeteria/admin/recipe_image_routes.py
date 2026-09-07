"""Bounded multipart upload and recipe-scoped immutable image bytes."""
from __future__ import annotations

from datetime import datetime
from uuid import UUID

from flask import current_app, make_response, redirect, render_template, request, url_for

from .. import recipe_store as store
from ..master_data_types import ObjectExpectation
from ..roles import capabilities
from . import recipe_forms as forms
from .recipe_errors import protected
from .routes import bp


@bp.route('/rezepte/<uuid:recipe_id>/bilder', methods=['GET', 'POST'])
@protected
def recipe_images(recipe_id: UUID):
    if request.args:
        raise forms.FormError('Bildverwaltung erlaubt keine Vorschauparameter.')
    engine = current_app.extensions['cafeteria_db']
    if request.method == 'POST':
        expected = forms.read_context(action='recipe.image', target_public_id=str(recipe_id))
        fields = {'_csrf', '_form_context', 'row_version', 'caption', 'source_url', 'source_license', 'fetched_at'}
        if set(request.form) != fields or any(len(request.form.getlist(key)) != 1 for key in fields):
            raise forms.FormError('Uploadfelder fehlen oder sind mehrfach vorhanden.')
        if set(request.files) != {'file'} or len(request.files.getlist('file')) != 1 or expected.target is None:
            raise forms.FormError('Genau eine Bilddatei auswählen.', 'file')
        for key, maximum in [('caption', 500), ('source_url', 2048), ('source_license', 500), ('fetched_at', 64)]:
            if len(request.form[key]) > maximum:
                raise forms.FormError('Eingabe ist zu lang.', key)
        fetched = None
        if request.form['fetched_at']:
            try:
                fetched = datetime.fromisoformat(request.form['fetched_at'])
                if fetched.tzinfo is None or fetched.utcoffset() is None:
                    raise ValueError
            except ValueError:
                raise forms.FormError('Abrufzeit mit Zeitzone erforderlich.', 'fetched_at') from None
        upload = request.files['file']
        store.add_recipe_image(engine, expected.actor, expected.target, data=upload.stream.read(1048577),
                               content_type=upload.mimetype, caption=request.form['caption'] or None,
                               source_url=request.form['source_url'] or None,
                               source_license=request.form['source_license'] or None, fetched_at=fetched,
                               expected_location_id=expected.expected_location_id)
        return redirect(url_for('admin.recipe_images', recipe_id=recipe_id), code=303)
    location = store.get_location(engine)
    row = store.get_recipe(engine, str(recipe_id))
    writable = row.active and bool(capabilities() & {'*', 'recipe.write'})
    token = forms.sign_context(action='recipe.image', target=ObjectExpectation(row.public_id, row.row_version),
                               expected_location_id=location, display_values={'recipe': str(row.payload['title'])}) if writable else None
    return render_template('admin/rezepte_images.html', family='cafeteria', profile='staff_guest', recipe=row, token=token)


@bp.get('/rezepte/<uuid:recipe_id>/bilder/<sha256>')
@protected
def recipe_asset(recipe_id: UUID, sha256: str):
    if request.args:
        raise forms.FormError('Bildadresse erlaubt keine Zusatzparameter.')
    asset = store.get_recipe_asset(current_app.extensions['cafeteria_db'], str(recipe_id), sha256)
    response = make_response(asset.data)
    response.headers['Content-Type'] = asset.content_type
    response.headers['X-Content-Type-Options'] = 'nosniff'
    return response
