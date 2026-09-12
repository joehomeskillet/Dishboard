"""A04: full week error pages preserve input without weakening write boundaries."""
from __future__ import annotations

from html.parser import HTMLParser

import pytest
from sqlalchemy import text
from werkzeug.datastructures import MultiDict

from cafeteria import roles
from test_admin_week_routes import app, client, database_engine  # noqa: F401
from test_admin_workflow_routes import DATABASE_URL, _login, _overview_csrf

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')
WEEK = '2026-09-14'
DAY = '2026-09-16'


class Forms(HTMLParser):
    def __init__(self, html: str):
        super().__init__(convert_charrefs=True)
        self.forms: list[dict] = []
        self.details: list[bool] = []
        self.current: dict | None = None
        self.select = ''
        self.feed(html)

    def handle_starttag(self, tag, attrs):
        attributes = dict(attrs)
        if tag == 'details':
            self.details.append('open' in attributes)
        elif tag == 'form':
            self.current = {'action': attributes.get('action'), 'fields': {},
                            'open': all(self.details), 'invalid': {}}
            self.forms.append(self.current)
        elif self.current is not None:
            name = attributes.get('name')
            if tag == 'input' and name:
                self.current['fields'][name] = attributes.get('value', '')
                if attributes.get('aria-invalid') == 'true':
                    self.current['invalid'][name] = attributes
            elif tag == 'select':
                self.select = name
            elif tag == 'option' and 'selected' in attributes:
                self.current['fields'][self.select] = attributes.get('value', '')

    def handle_endtag(self, tag):
        if tag == 'details':
            self.details.pop()
        elif tag == 'form':
            self.current = None
        elif tag == 'select':
            self.select = ''


def _fields(test_client, family, kind):
    values = {'_csrf': _overview_csrf(test_client, family), 'week': WEEK, 'row_version': '0'}
    if kind == 'header':
        values.update(title='Meine Woche', shared_note='  Hinweis <b> & "Text"  ')
    else:
        values.update(day=DAY, meal='LUNCH' if family == 'cafeteria' else 'DINNER',
                      service_state='holiday', notice='  Keine Ausgabe <b> & "Text"  ',
                      service_start='12:15', service_end='13:45')
    return values


def _form(response, family, kind):
    forms = Forms(response.get_data(as_text=True)).forms
    return next(form for form in forms if form['action'] == f'/admin/{family}/{kind}'
                and (kind == 'header' or form['fields']['day'] == DAY
                     and form['fields']['meal'] == ('LUNCH' if family == 'cafeteria' else 'DINNER')))


def _snapshot(engine):
    with engine.connect() as connection:
        return (
            connection.execute(text('SELECT id, title, shared_note, row_version '
                                    'FROM cafeteria.menu_weeks ORDER BY id')).all(),
            connection.execute(text('SELECT id, service_state, notice, service_start, '
                                    'service_end, row_version FROM cafeteria.menu_services ORDER BY id')).all(),
        )


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize(('kind', 'field', 'bad', 'fixed'), [
    ('header', 'title', '   ', 'Meine korrigierte Woche'),
    ('service', 'notice', '   ', 'Keine Ausgabe'),
    ('service', 'service_end', '11:00', '13:30'),
    ('service', 'service_start', '  falsch  ', '12:00'),
])
def test_invalid_values_reopen_only_target_then_save(client, database_engine, family, kind, field, bad, fixed):  # noqa: F811
    values = _fields(client, family, kind)
    values[field] = bad
    before = _snapshot(database_engine)
    response = client.post(f'/admin/{family}/{kind}', data=values)
    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'
    assert f'data-week="{WEEK}"' in response.text
    assert _snapshot(database_engine) == before
    form = _form(response, family, kind)
    assert form['open'] and field in form['invalid']
    for key, value in values.items():
        if key != '_csrf':
            assert form['fields'][key] == value
    assert form['invalid'][field]['aria-describedby'].endswith('-error')
    assert '<b>' not in response.text
    others = [entry for entry in Forms(response.text).forms
              if entry['action'] in (f'/admin/{family}/header', f'/admin/{family}/service')]
    assert sum(entry['open'] for entry in others) == 1
    form['fields'][field] = fixed
    saved = client.post(form['action'], data=form['fields'])
    assert saved.status_code == 303 and saved.location == f'/admin/{family}?week={WEEK}'
    loaded = _form(client.get(saved.location), family, kind)
    assert loaded['fields'][field] == fixed


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('kind', ['header', 'service'])
@pytest.mark.parametrize('existing', [False, True])
def test_conflict_and_resubmit_keep_original_version(client, database_engine, family, kind, existing):  # noqa: F811
    values = _fields(client, family, kind)
    path = f'/admin/{family}/{kind}'
    if existing:
        assert client.post(path, data=values).status_code == 303
        values = _form(client.get(f'/admin/{family}?week={WEEK}'), family, kind)['fields']
    competing = dict(values)
    target = 'title' if kind == 'header' else 'notice'
    competing[target] = 'Parallel gespeicherter Stand'
    assert client.post(path, data=competing).status_code == 303
    before = _snapshot(database_engine)
    values[target] = 'Mein ungespeicherter Stand'
    for _ in range(2):
        response = client.post(path, data=values)
        assert response.status_code == 409
        assert 'Aktuellen Wochenplan öffnen' in response.text
        form = _form(response, family, kind)
        assert form['open']
        assert form['fields'][target] == values[target]
        assert form['fields']['row_version'] == values['row_version']
        assert _snapshot(database_engine) == before
        values = form['fields']


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('kind', ['header', 'service'])
def test_validation_after_concurrent_write_does_not_adopt_fresh_version(client, database_engine, family, kind):  # noqa: F811
    values = _fields(client, family, kind)
    path = f'/admin/{family}/{kind}'
    assert client.post(path, data=values).status_code == 303
    target = 'title' if kind == 'header' else 'notice'
    values[target] = ' '
    response = client.post(path, data=values)
    assert response.status_code == 400
    form = _form(response, family, kind)
    assert form['fields']['row_version'] == '0'
    form['fields'][target] = 'Nicht überschreiben'
    before = _snapshot(database_engine)
    assert client.post(path, data=form['fields']).status_code == 409
    assert _snapshot(database_engine) == before


@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
@pytest.mark.parametrize('kind', ['header', 'service'])
def test_malformed_context_and_csrf_stay_fail_closed(client, database_engine, family, kind):  # noqa: F811
    values = _fields(client, family, kind)
    target = 'title' if kind == 'header' else 'notice'
    values[target] = ' '
    attacks = [dict(values, row_version='bad'), dict(values, week='2026-09-15'),
               dict(values, profile='patient'), dict(values, extra='untrusted'),
               dict(values, _csrf='invalid')]
    duplicate = MultiDict(values)
    duplicate.add(target, 'zweiter Wert')
    attacks.append(duplicate)
    missing = dict(values)
    del missing[target]
    attacks.append(missing)
    other_family = 'patienten' if family == 'cafeteria' else 'cafeteria'
    attacks.append(dict(values, _csrf=_overview_csrf(client, other_family)))
    if kind == 'service':
        attacks.extend([dict(values, day='2026-10-01'), dict(values, meal='INVALID'),
                        dict(values, service_state='INVALID')])
    before = _snapshot(database_engine)
    for attack in attacks:
        response = client.post(f'/admin/{family}/{kind}', data=attack)
        assert response.status_code in (400, 404, 409)
        assert 'admin-week-settings' not in response.text
        assert 'admin-week-service-form' not in response.text
        assert _snapshot(database_engine) == before


@pytest.mark.parametrize('kind', ['header', 'service'])
def test_location_cutover_rejects_invalid_form_before_rerender(client, database_engine, kind):  # noqa: F811
    values = _fields(client, 'patienten', kind)
    values['title' if kind == 'header' else 'notice'] = ' '
    with database_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.locations SET active=false'))
        connection.execute(text("INSERT INTO cafeteria.locations(code, name) VALUES ('NORD', 'Nordküche')"))
    response = client.post(f'/admin/patienten/{kind}', data=values)
    assert response.status_code == 409
    assert 'admin-week-settings' not in response.text
    assert _snapshot(database_engine) == ([], [])


@pytest.mark.parametrize('kind', ['header', 'service'])
def test_removed_write_role_cannot_rerender_week(app, database_engine, monkeypatch, kind):  # noqa: F811
    denied, _ = _login(app, database_engine, ['Cafeteria.Editor'])
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Editor', {'draft.read'})
    response = denied.post(f'/admin/patienten/{kind}', data={'title': ' '})
    assert response.status_code == 403
    assert 'admin-week-settings' not in response.text
