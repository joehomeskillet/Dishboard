from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from types import SimpleNamespace

import pytest
from flask import Flask
from jinja2 import ChoiceLoader, DictLoader, FileSystemLoader
from werkzeug.datastructures import MultiDict

from cafeteria import roles
from cafeteria.admin import week_review_routes as routes
from cafeteria.admin import workflow_routes
from cafeteria.admin.rendering import _cells
from cafeteria.component_catalog_store import AdminScope
from cafeteria.workflow_review_context import context_token, review_week_context


WEEK = date(2026, 8, 31)


def _saved(profile='patient'):
    context = {
        'week_public_id': '00000000-0000-0000-0000-000000000010', 'location_id': 5,
        'profile_code': profile, 'week_start': WEEK.isoformat(), 'header_revision': 2,
        'title': 'Gespeicherter Titel <script>', 'shared_note': 'Alle Hinweise unverändert prüfen',
        'services': [
            {'public_id': f'service-{index}', 'date': (WEEK + timedelta(days=index // 2)).isoformat(),
             'meal': 'LUNCH' if index % 2 == 0 else 'DINNER', 'state': 'closed',
             'row_version': 3, 'notice': f'Vollständiger Hinweis für Service {index} ENDE-{index}'}
            for index in range(14)
        ],
    }
    return {'context': context, 'token': context_token(context), 'receipt': None}


@pytest.fixture
def review_client(monkeypatch):
    app = Flask(__name__)
    app.config.update(TESTING=True, SECRET_KEY='test-week-review')
    app.extensions['cafeteria_db'] = object()
    app.register_blueprint(routes.bp)
    monkeypatch.setattr(roles, 'load_user_authorization', lambda *_: SimpleNamespace(
        authz_version=3, roles=['Cafeteria.Editor'],
    ))
    def scope(profile):
        return AdminScope(7, 5, profile)
    monkeypatch.setattr(workflow_routes, '_scope', scope)
    monkeypatch.setattr(routes, '_scope', scope)
    captured = {}
    reads, writes = [], []

    def load(engine, scoped, week):
        reads.append((scoped, week))
        return _saved(scoped.profile_code)

    def render(template, **values):
        captured.update(template=template, **values)
        return 'Saved review page'

    monkeypatch.setattr(routes, 'get_week_review', load)
    monkeypatch.setattr(routes, 'render_template', render)
    monkeypatch.setattr(routes, 'review_week_context', lambda engine, scoped, week, token: writes.append((scoped, week, token)))
    client = app.test_client()
    with client.session_transaction() as session:
        session['user'] = {'id': 7}
        session['authz_version'] = 3
    return app, client, captured, reads, writes


@pytest.mark.parametrize(('family', 'profile'), [('patienten', 'patient'), ('cafeteria', 'staff_guest')])
def test_scoped_saved_context_get_and_exact_post_contract(review_client, family, profile):
    app, client, captured, reads, writes = review_client
    path = f'/admin/{family}/wochen/pruefung'
    result = client.get(path + '?week=2026-08-31')
    assert result.status_code == 200 and result.headers['Cache-Control'] == 'no-store'
    assert reads == [(AdminScope(7, 5, profile), WEEK)] and not writes
    assert captured['template'] == 'admin/week_review.html'
    assert captured['can_write']
    fields = {'_csrf': captured['csrf'], 'week': WEEK.isoformat(), 'context_version': captured['review']['token']}
    result = client.post(path, data=fields)
    assert result.status_code == 303 and result.location == path + '?week=2026-08-31'
    assert result.headers['Cache-Control'] == 'no-store'
    assert writes == [(AdminScope(7, 5, profile), WEEK, fields['context_version'])]


@pytest.mark.parametrize('query', ['', '?week=bad', '?week=2026-09-01', '?week=2026-08-31&week=2026-08-31', '?week=2026-08-31&profile=patient', '?week=2026-08-31&location_id=6'])
def test_get_rejects_unscoped_or_ambiguous_context_without_read(review_client, query):
    _, client, _, reads, writes = review_client
    assert client.get('/admin/patienten/wochen/pruefung' + query).status_code == 400
    assert not reads and not writes


def test_post_rejects_csrf_cross_profile_duplicates_overrides_and_stale_auth(review_client, monkeypatch):
    app, client, captured, _, writes = review_client
    path = '/admin/patienten/wochen/pruefung'
    client.get(path + '?week=2026-08-31')
    fields = {'_csrf': captured['csrf'], 'week': WEEK.isoformat(), 'context_version': captured['review']['token']}
    assert client.post('/admin/cafeteria/wochen/pruefung', data=fields).status_code == 409
    assert client.post(path, data={**fields, '_csrf': 'wrong'}).status_code == 400
    assert client.post(path, data={**fields, 'location_id': '5'}).status_code == 400
    assert client.post(path + '?week=2026-08-31', data=fields).status_code == 400
    assert client.post(path, data=MultiDict([*fields.items(), ('context_version', fields['context_version'])])).status_code == 400
    monkeypatch.setattr(roles, 'load_user_authorization', lambda *_: SimpleNamespace(authz_version=3, roles=[]))
    assert client.post(path, data=fields).status_code == 403
    assert client.get(path + '?week=2026-08-31').status_code == 403
    with client.session_transaction() as session:
        session.clear()
    assert client.get(path + '?week=2026-08-31').status_code == 401
    assert not writes


def test_new_review_template_renders_all_saved_context_without_truncation(review_client):
    app, _, _, _, _ = review_client
    template_dir = Path(__file__).resolve().parents[1] / 'cafeteria' / 'templates'
    # Only the parent-shell fixture is synthetic; real Tabler shell needs integration gate.
    app.jinja_loader = ChoiceLoader([
        DictLoader({'admin/base_tabler.html': '<main>{% block page_header %}{% endblock %}{% block content %}{% endblock %}</main>'}),
        FileSystemLoader(template_dir),
    ])
    saved = _saved()
    with app.test_request_context():
        rendered = app.jinja_env.get_template('admin/week_review.html').render(
            family='patienten', profile='patient', week=WEEK.isoformat(), review=saved,
            can_write=True, csrf='synthetic-csrf', service_labels={'closed': 'Geschlossen'},
        )
    assert 'Gespeicherter Titel &lt;script&gt;' in rendered and '<script>' not in rendered
    assert saved['context']['shared_note'] in rendered
    for index in range(14):
        assert f'Vollständiger Hinweis für Service {index} ENDE-{index}' in rendered
    assert 'Wochenkopf und alle Servicehinweise als geprüft bestätigen' in rendered
    assert 'name="context_version" value="' + saved['token'] + '"' in rendered


def test_historical_checked_flag_does_not_render_as_current_approval(review_client):
    app = review_client[0]
    draft = {'days': [{'date': WEEK.isoformat(), 'services': [{
        'meal_code': 'LUNCH', 'options': [{'type_code': 'MENU_1', 'allergen_review_status': 'checked'}],
    }]}]}
    with app.test_request_context():
        cells = _cells('patient', 'patienten', WEEK, draft, {(WEEK.isoformat(), 'LUNCH', 'MENU_1'): 4}, {})
        assert cells[0]['review_open'] is True
        draft['days'][0]['services'][0]['options'][0]['review_open'] = False
        assert _cells('patient', 'patienten', WEEK, draft, {}, {})[0]['review_open'] is False


@pytest.mark.parametrize('token', ['', 'sha256:bad', None, 42])
def test_malformed_review_token_is_rejected_before_database_access(token):
    with pytest.raises(ValueError, match='Wochenprüfversion'):
        review_week_context(object(), AdminScope(7, 5, 'patient'), WEEK, token)
