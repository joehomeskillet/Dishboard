from __future__ import annotations

import datetime as dt
from zoneinfo import ZoneInfo

from flask import Blueprint, current_app, jsonify, make_response, request
from cafeteria.db import APPLICATION_VERSION
from ..public import routes as public_routes
from . import mapping

bp = Blueprint('fhir', __name__, url_prefix='/fhir')


def fhir_json_response(resource: dict, status_code: int = 200, cache_control: str | None = None, revisions: list[str] | None = None):
    response = make_response(jsonify(resource), status_code)
    if cache_control:
        response.headers['Cache-Control'] = cache_control
    if revisions:
        response.headers['X-Snapshot-Revision'] = ','.join(sorted(revisions))
    response.headers['Content-Type'] = 'application/fhir+json; charset=utf-8'
    return response


def no_store_outcome(severity: str, code: str, diagnostics: str, status_code: int = 400):
    outcome = mapping.operation_outcome(severity, code, diagnostics)
    return fhir_json_response(outcome, status_code=status_code, cache_control='no-store')


@bp.errorhandler(404)
def handle_404(e):
    return no_store_outcome('error', 'not-found', 'Nicht gefunden.', 404)


@bp.errorhandler(405)
def handle_405(e):
    return no_store_outcome('error', 'not-supported', 'Methode nicht erlaubt.', 405)


@bp.before_request
def restrict_query_parameters():
    path = request.path
    if path.rstrip('/') == '/fhir/NutritionProduct':
        allowed = {'channel', 'date'}
    elif path.rstrip('/') == '/fhir/Composition':
        allowed = {'channel'}
    else:
        allowed = set()

    for key in request.args:
        if key not in allowed or len(request.args.getlist(key)) > 1:
            return no_store_outcome('fatal', 'invalid', 'Unzulässige Query-Parameter.')


@bp.get('/metadata')
def metadata():
    now = dt.datetime.now(ZoneInfo('Europe/Zurich')).isoformat(timespec='seconds')
    base_url = current_app.config['APP_PUBLIC_BASE_URL'].rstrip('/')
    cap = mapping.capability_statement(
        base_url=base_url,
        software_version=APPLICATION_VERSION,
        now=now
    )
    return fhir_json_response(cap, cache_control='public, max-age=300')


def _active_snapshots() -> dict[str, dict]:
    res = {}
    for profile, channel in [('staff_guest', 'cafeteria'), ('patient', 'patienten')]:
        snap = public_routes.published_snapshot(profile)
        if snap:
            res[channel] = snap
    return res


@bp.get('/NutritionProduct')
def search_nutrition_product():
    channel = request.args.get('channel')
    date_filter = request.args.get('date')

    base_url = current_app.config['APP_PUBLIC_BASE_URL'].rstrip('/')
    snaps = _active_snapshots()
    if channel:
        if channel not in snaps:
            snaps = {}
        else:
            snaps = {channel: snaps[channel]}

    products = []
    revisions = []
    for snap in snaps.values():
        revisions.append(snap['revision_id'])
        prods = mapping.nutrition_products(snap, base_url=base_url)
        for p in prods:
            if date_filter:
                date_chars = [c for c in p.get('characteristic', []) if c.get('type', {}).get('coding', [{}])[0].get('code') == 'service-date']
                if not date_chars or date_chars[0].get('valueString') != date_filter:
                    continue
            products.append(p)

    bundle = mapping.searchset_bundle(products, base_url=base_url, self_url=request.url)
    return fhir_json_response(bundle, cache_control='public, max-age=60, stale-if-error=86400', revisions=revisions)


@bp.get('/NutritionProduct/<id>')
def read_nutrition_product(id):
    base_url = current_app.config['APP_PUBLIC_BASE_URL'].rstrip('/')
    snaps = _active_snapshots()

    for snap in snaps.values():
        prods = mapping.nutrition_products(snap, base_url=base_url)
        for p in prods:
            if p['id'] == id:
                return fhir_json_response(p, cache_control='public, max-age=60, stale-if-error=86400', revisions=[snap['revision_id']])

    return no_store_outcome('error', 'not-found', 'Ressource nicht gefunden.', status_code=404)


@bp.get('/Composition')
def search_composition():
    channel = request.args.get('channel')

    base_url = current_app.config['APP_PUBLIC_BASE_URL'].rstrip('/')
    snaps = _active_snapshots()
    if channel:
        if channel not in snaps:
            snaps = {}
        else:
            snaps = {channel: snaps[channel]}

    compositions = []
    revisions = []
    for snap in snaps.values():
        revisions.append(snap['revision_id'])
        compositions.append(mapping.composition(snap, base_url=base_url))

    bundle = mapping.searchset_bundle(compositions, base_url=base_url, self_url=request.url)
    return fhir_json_response(bundle, cache_control='public, max-age=60, stale-if-error=86400', revisions=revisions)


@bp.get('/Composition/<id>')
def read_composition(id):
    base_url = current_app.config['APP_PUBLIC_BASE_URL'].rstrip('/')
    snaps = _active_snapshots()

    for snap in snaps.values():
        if snap['revision_id'] == id:
            comp = mapping.composition(snap, base_url=base_url)
            return fhir_json_response(comp, cache_control='public, max-age=60, stale-if-error=86400', revisions=[snap['revision_id']])

    return no_store_outcome('error', 'not-found', 'Ressource nicht gefunden.', status_code=404)


@bp.get('/Composition/<id>/$document')
def document_composition(id):
    base_url = current_app.config['APP_PUBLIC_BASE_URL'].rstrip('/')
    snaps = _active_snapshots()

    for snap in snaps.values():
        if snap['revision_id'] == id:
            doc = mapping.document_bundle(snap, base_url=base_url)
            return fhir_json_response(doc, cache_control='public, max-age=60, stale-if-error=86400', revisions=[snap['revision_id']])

    return no_store_outcome('error', 'not-found', 'Ressource nicht gefunden.', status_code=404)
