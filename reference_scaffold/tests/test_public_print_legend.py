from copy import deepcopy

import pytest
from flask import render_template

from test_rendered_ui import PATIENT_FORBIDDEN, app  # noqa: F401


@pytest.mark.parametrize('profile,family', [('staff_guest', 'cafeteria'), ('patient', 'patienten')])
def test_public_prints_use_shared_symbols_and_one_exact_week_legend(app, profile, family):  # noqa: F811
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    first = snapshot['days'][0]['services'][0]['options'][0]
    first.update(
        description='Vollständige Beschreibung', note='Deklaration sorgfältig prüfen',
        allergens=[{'code': 'MILK', 'name': 'Milch', 'presence': 'may_contain'}],
        origins=[{'country_code': 'CH', 'ingredient': 'Kartoffel', 'text': 'Kartoffel: Schweiz'}],
        labels=[{'code': 'VEGETARIAN', 'name': 'Vegetarisch'}],
        allergen_review_status='not_checked',
    )
    original = deepcopy(snapshot)
    response = app.test_client().get(f'/druck/{family}/woche')
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert body.count('class="food-legend') == 1
    assert 'Legende der gedruckten Menüs' in body
    assert 'Vollständige Beschreibung' in body and 'Deklaration sorgfältig prüfen' in body
    assert 'Allergenprüfung offen' in body
    assert '/static/vendor/food-symbols/allergens/milk.svg' in body
    assert '/static/vendor/food-symbols/flags/ch.svg' in body
    for filename in ('allergens/milk.svg', 'flags/ch.svg'):
        assert app.test_client().get('/static/vendor/food-symbols/' + filename).status_code == 200
    if profile == 'patient':
        assert PATIENT_FORBIDDEN.search(body) is None
    assert snapshot == original


@pytest.mark.parametrize('profile,template', [
    ('staff_guest', 'print_cafeteria_week.html'), ('patient', 'print_patient_week.html'),
])
def test_closed_meals_do_not_contribute_hidden_legend_entries(app, profile, template):  # noqa: F811
    snapshot = deepcopy(app.config['TEST_SNAPSHOTS'][profile])
    meal = snapshot['days'][0]['services'][0]
    meal.update(service_state='closed', notice='Heute geschlossen')
    meal['options'][0]['labels'] = [{'code': 'CUSTOM', 'name': 'NURVERBORGEN'}]
    with app.test_request_context():
        body = render_template('public/' + template, snapshot=snapshot,
                               open_days=[day for day in snapshot['days'] if day['services']])
    assert 'Heute geschlossen' in body
    assert 'NURVERBORGEN' not in body
