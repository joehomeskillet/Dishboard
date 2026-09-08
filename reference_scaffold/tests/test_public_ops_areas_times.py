"""OPS-001: area names and serving times in the public web and print outputs."""
from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))

from cafeteria.public import routes as public_routes  # noqa: E402
from cafeteria.signage import routes as signage_routes  # noqa: E402
from cafeteria.template_filters import (  # noqa: E402
    LEGACY_PATIENT_MEAL_TIMES,
    cafeteria_visible_days,
    patient_day_time_label,
    register_template_filters,
    service_time_label,
    weekday_range_label,
)

WEEK = ('2026-08-31', '2026-09-01', '2026-09-02', '2026-09-03', '2026-09-04', '2026-09-05', '2026-09-06')
WEEKDAYS = ('Montag', 'Dienstag', 'Mittwoch', 'Donnerstag', 'Freitag', 'Samstag', 'Sonntag')
TODAY = '2026-09-02'
CAFETERIA_AREA = 'Team-Restaurant'
PATIENT_AREA = 'Schülerinnen und Schüler'


def _option(index: int, prices: bool) -> dict[str, Any]:
    option: dict[str, Any] = {
        'external_id': f'OPT-{index}',
        'type_code': 'MENU_1' if index == 1 else 'VEGGIE',
        'type_name': 'Menü 1' if index == 1 else 'Vegetarisch',
        'title': f'Tagesgericht {index}',
        'description': 'Sorgfältig zubereitet',
        'components': ['Kartoffeln', 'Gemüse'],
        'labels': [],
        'allergens': [],
        'origins': [],
        'note': '',
        'allergen_review_status': 'checked',
    }
    if prices:
        option['prices'] = {'internal_rappen': 1100, 'external_rappen': 1660, 'currency': 'CHF'}
    return option


def _service(meal_code: str, meal_name: str, *, prices: bool, start: str | None = None,
             end: str | None = None, notice: str = '') -> dict[str, Any]:
    service: dict[str, Any] = {'meal_code': meal_code, 'meal_name': meal_name}
    if notice:
        service.update(service_state='closed', notice=notice, options=[])
        return service
    service.update(service_state='open', notice='', options=[_option(1, prices), _option(2, prices)])
    if start:
        service['service_start'] = start
    if end:
        service['service_end'] = end
    return service


def cafeteria_snapshot(*, area: bool, times: bool, saturday: str | None = None,
                       sunday: str | None = None) -> dict[str, Any]:
    """Cafeteria week; `saturday`/`sunday` open ('open') or close ('closed') that weekend day."""
    weekend = {'Samstag': saturday, 'Sonntag': sunday}
    days = []
    for date_value, weekday in zip(WEEK, WEEKDAYS, strict=True):
        services = []
        state = weekend.get(weekday, 'open')
        if state == 'open':
            end = ('14:00' if weekday == 'Samstag' else '13:30') if times else None
            services = [_service('LUNCH', 'Mittag', prices=True,
                                 start='11:30' if times else None, end=end)]
        elif state == 'closed':
            services = [_service('LUNCH', 'Mittag', prices=True, notice=f'Am {weekday} geschlossen.')]
        days.append({
            'date': date_value, 'weekday': weekday,
            'state': 'open' if services else 'closed',
            'notice': '' if services else 'Cafeteria geschlossen',
            'services': services,
        })
    snapshot: dict[str, Any] = {
        'schema_version': 2, 'profile_code': 'staff_guest', 'channel': 'cafeteria',
        'revision_id': 'CAF-OPS-R1',
        'location': {'code': 'KIRCHLINDACH', 'name': 'Klinik Südhang Kirchlindach'},
        'week_start': WEEK[0], 'week_end': WEEK[-1],
        'title': '31. August bis 4. September', 'shared_note': '', 'days': days,
    }
    if area:
        snapshot['area_name'] = CAFETERIA_AREA
    return snapshot


def patient_snapshot(*, area: bool, times: bool, closed_dinner: bool = False) -> dict[str, Any]:
    days = []
    for date_value, weekday in zip(WEEK, WEEKDAYS, strict=True):
        dinner_closed = closed_dinner and date_value == TODAY
        days.append({
            'date': date_value, 'weekday': weekday, 'state': 'open', 'notice': '',
            'services': [
                _service('LUNCH', 'Mittag', prices=False,
                         start='11:30' if times else None, end='13:30' if times else None),
                _service('DINNER', 'Abend', prices=False,
                         notice='Das Abendessen wird auf der Station serviert.' if dinner_closed else '',
                         start='17:30' if times and not dinner_closed else None),
            ],
        })
    snapshot: dict[str, Any] = {
        'schema_version': 2, 'profile_code': 'patient', 'channel': 'patienten',
        'revision_id': 'PAT-OPS-R1',
        'location': {'code': 'KIRCHLINDACH', 'name': 'Klinik Südhang Kirchlindach'},
        'week_start': WEEK[0], 'week_end': WEEK[-1],
        'title': '31. August bis 6. September', 'shared_note': '', 'days': days,
    }
    if area:
        snapshot['area_name'] = PATIENT_AREA
    return snapshot


@pytest.fixture
def client(monkeypatch: pytest.MonkeyPatch):
    """DB-free app that serves whichever snapshots a test installs."""
    application = Flask(
        'ops-outputs',
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
        static_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'static'),
    )
    application.config.update(TESTING=True, SECRET_KEY='ops-outputs', DEMO_MODE=True, DEMO_TODAY=TODAY,
                              LAST_GOOD_DIR=str(ROOT / '.test-last-good'))
    from contextlib import nullcontext
    from types import SimpleNamespace
    def absent_screen_setting(statement, parameters):
        assert ' '.join(str(statement).split()) == (
            'SELECT setting_value FROM cafeteria.settings WHERE location_id IS NULL '
            'AND profile_id IS NULL AND setting_key=:key')
        assert set(parameters) == {'key'}
        assert parameters['key'] in ('screen_assignment.v1.staff_guest.web.week', 'screen_assignment.v1.patient.web.week')
        return SimpleNamespace(one_or_none=lambda: None)
    application.extensions['cafeteria_db'] = SimpleNamespace(
        connect=lambda: nullcontext(SimpleNamespace(execute=absent_screen_setting)),
    )
    register_template_filters(application)
    application.register_blueprint(public_routes.bp)
    application.register_blueprint(signage_routes.bp)
    snapshots: dict[str, Any] = {'staff_guest': None, 'patient': None}

    def fake_active_snapshot(_engine, profile_code, _date, *, last_good_dir):
        return deepcopy(snapshots[profile_code])

    monkeypatch.setattr(public_routes, 'active_snapshot', fake_active_snapshot)
    test_client = application.test_client()
    test_client.snapshots = snapshots  # type: ignore[attr-defined]
    test_client.application_under_test = application  # type: ignore[attr-defined]
    return test_client


def _body(client, path: str, staff: Any = None, patient: Any = None) -> str:
    client.snapshots['staff_guest'] = staff
    client.snapshots['patient'] = patient
    response = client.get(path)
    assert response.status_code == 200, path
    return response.get_data(as_text=True)


# --- filters ---------------------------------------------------------------

@pytest.mark.parametrize(('start', 'end', 'profile', 'expected'), (
    ('11:30', '12:30', 'patient', 'Ausgabe 11:30–12:30 Uhr'),
    ('11:30', '13:30', 'staff_guest', 'Mittag 11:30–13:30 Uhr'),
    ('11:30', None, 'patient', 'Ausgabe ab 11:30 Uhr'),
    ('11:30', None, 'staff_guest', 'Mittag ab 11:30 Uhr'),
    (None, '12:30', 'patient', 'Ausgabe bis 12:30 Uhr'),
    (None, '13:30', 'staff_guest', 'Mittag bis 13:30 Uhr'),
    (None, None, 'patient', ''),
    (None, None, 'staff_guest', ''),
))
def test_service_time_label_covers_every_time_combination(
    start: str | None, end: str | None, profile: str, expected: str,
) -> None:
    service: dict[str, Any] = {'meal_code': 'LUNCH'}
    if start:
        service['service_start'] = start
    if end:
        service['service_end'] = end
    label = service_time_label(service, profile)
    assert label == expected
    # The range separator is the en dash U+2013, never a hyphen.
    assert '-' not in label
    assert bool(start and end) == ('–' in label)


def test_closed_service_never_shows_a_time() -> None:
    closed = {'meal_code': 'LUNCH', 'service_state': 'closed', 'notice': 'Geschlossen',
              'service_start': '11:30', 'service_end': '13:30'}
    assert service_time_label(closed, 'staff_guest') == ''
    assert service_time_label(closed, 'patient') == ''
    assert patient_day_time_label(closed, '') == ''


def test_patient_day_label_falls_back_only_without_an_area_name() -> None:
    bare = {'meal_code': 'LUNCH'}
    assert patient_day_time_label(bare, '') == LEGACY_PATIENT_MEAL_TIMES['LUNCH']
    assert patient_day_time_label({'meal_code': 'DINNER'}, '') == LEGACY_PATIENT_MEAL_TIMES['DINNER']
    assert patient_day_time_label(bare, PATIENT_AREA) == ''
    timed = {'meal_code': 'LUNCH', 'service_start': '12:00'}
    assert patient_day_time_label(timed, PATIENT_AREA) == 'Ausgabe ab 12:00 Uhr'


def test_visible_cafeteria_days_drop_weekends_without_an_open_service() -> None:
    days = cafeteria_snapshot(area=True, times=True, saturday='closed')['days']
    assert [day['weekday'] for day in cafeteria_visible_days(days)] == list(WEEKDAYS[:5])
    open_days = cafeteria_snapshot(area=True, times=True, saturday='open')['days']
    assert [day['weekday'] for day in cafeteria_visible_days(open_days)] == list(WEEKDAYS[:6])


@pytest.mark.parametrize(('count', 'expected'), (
    (5, 'Montag bis Freitag'), (6, 'Montag bis Samstag'), (7, 'Montag bis Sonntag'), (1, 'Montag'),
))
def test_weekday_range_label_names_a_run_from_monday(count: int, expected: str) -> None:
    days = [{'date': date_value} for date_value in WEEK[:count]]
    assert weekday_range_label(days) == expected


def test_weekday_range_label_enumerates_a_gap() -> None:
    days = [{'date': WEEK[0]}, {'date': WEEK[2]}, {'date': WEEK[4]}]
    assert weekday_range_label(days) == 'Montag, Mittwoch und Freitag'
    assert weekday_range_label([]) == ''


# --- public web pages ------------------------------------------------------

@pytest.mark.parametrize('path', ('/cafeteria/heute/', '/cafeteria/wochenangebot/',
                                  '/cafeteria/wochenangebot/ohne-bilder/', '/druck/cafeteria/woche'))
def test_cafeteria_pages_show_the_area_name_and_its_serving_time(client, path: str) -> None:
    body = _body(client, path, staff=cafeteria_snapshot(area=True, times=True))
    assert CAFETERIA_AREA in body
    assert 'Mittag 11:30–13:30 Uhr' in body
    assert 'Cafeteria · Mitarbeitende und Externe' not in body


@pytest.mark.parametrize('path', ('/cafeteria/heute/', '/cafeteria/wochenangebot/',
                                  '/cafeteria/wochenangebot/ohne-bilder/', '/druck/cafeteria/woche'))
def test_cafeteria_pages_without_area_keep_their_previous_texts(client, path: str) -> None:
    body = _body(client, path, staff=cafeteria_snapshot(area=False, times=False))
    assert 'Montag bis Freitag' in body
    assert 'Uhr' not in body
    assert CAFETERIA_AREA not in body


def test_open_saturday_is_shown_and_named_in_the_cafeteria_week(client) -> None:
    body = _body(client, '/cafeteria/wochenangebot/',
                 staff=cafeteria_snapshot(area=True, times=True, saturday='open'))
    assert 'Samstag' in body
    assert 'Sonntag' not in body
    assert 'Montag bis Samstag' in body
    assert 'Mittag 11:30–14:00 Uhr' in body


def test_closed_saturday_stays_out_of_the_cafeteria_week(client) -> None:
    body = _body(client, '/cafeteria/wochenangebot/',
                 staff=cafeteria_snapshot(area=True, times=True, saturday='closed'))
    assert 'Am Samstag geschlossen.' not in body
    assert 'Montag bis Freitag' in body


@pytest.mark.parametrize('path', ('/patienten/heute/', '/patienten/wochenplan/',
                                  '/patienten/wochenplan/ohne-bilder/', '/druck/patienten/woche'))
def test_patient_pages_show_the_area_name_and_stay_free_of_prices(client, path: str) -> None:
    body = _body(client, path, patient=patient_snapshot(area=True, times=True))
    assert PATIENT_AREA in body
    assert 'Ausgabe 11:30–13:30 Uhr' in body
    assert 'Ausgabe ab 17:30 Uhr' in body
    for forbidden in ('CHF', 'Rappen', 'internal_rappen', 'Preis'):
        assert forbidden not in body


def test_patient_day_keeps_the_fixed_texts_for_snapshots_without_an_area_name(client) -> None:
    body = _body(client, '/patienten/heute/', patient=patient_snapshot(area=False, times=False))
    assert 'Ausgabe ab 11:30 Uhr' in body
    assert 'Ausgabe ab 17:30 Uhr' in body
    assert 'Speiseplan für Patientinnen und Patienten' in body


@pytest.mark.parametrize('path', ('/patienten/wochenplan/', '/patienten/wochenplan/ohne-bilder/',
                                  '/druck/patienten/woche'))
def test_patient_week_gains_no_time_line_for_snapshots_without_an_area_name(client, path: str) -> None:
    body = _body(client, path, patient=patient_snapshot(area=False, times=False))
    assert 'Ausgabe' not in body
    assert 'Uhr' not in body


def test_closed_patient_service_shows_its_notice_without_a_time(client) -> None:
    body = _body(client, '/patienten/heute/',
                 patient=patient_snapshot(area=True, times=True, closed_dinner=True))
    assert 'Das Abendessen wird auf der Station serviert.' in body
    assert 'Ausgabe ab 17:30 Uhr' not in body
    assert 'Ausgabe 11:30–13:30 Uhr' in body


# --- byte-identical texts for snapshots without an area name ---------------

LEGACY_TEXTS = {
    '/cafeteria/heute/': (
        '<title>Cafeteria heute – Klinik Südhang</title>',
        '<div class="page-pretitle">Cafeteria · Mitarbeitende und Externe</div>',
        # The minimal public header keeps the day range without redundant menu-count copy.
        'Mittagsmenüs von Montag bis Freitag.',
    ),
    '/cafeteria/wochenangebot/': (
        '<title>Cafeteria-Woche – Klinik Südhang</title>',
        '<div class="page-pretitle">Cafeteria · Wochenangebot</div>',
        'Cafeteria-Mittagessen von Montag bis Freitag.',
    ),
    '/druck/cafeteria/woche': (
        '<title>Druckansicht Cafeteria-Woche</title>',
        '<span>Cafeteria · Mitarbeitende und externe Gäste</span>',
        '<p class="eyebrow">Druck · Cafeteria</p>',
        '<p class="hero-copy">Mittag von Montag bis Freitag.</p>',
    ),
    '/patienten/heute/': (
        '<title>Speiseplan heute – Klinik Südhang</title>',
        '<div class="page-pretitle">Speiseplan für Patientinnen und Patienten</div>',
    ),
    '/patienten/wochenplan/': (
        '<title>Wochenspeiseplan – Klinik Südhang</title>',
        '<div class="page-pretitle">Patienten-Speiseplan · Wochenübersicht</div>',
    ),
    '/druck/patienten/woche': (
        '<title>Druckansicht Wochenspeiseplan</title>',
        '<span>Patienten-Speiseplan</span>',
        '<p class="eyebrow">Druck · Patienten-Speiseplan</p>',
    ),
}


@pytest.mark.parametrize('path', tuple(LEGACY_TEXTS))
def test_pages_without_an_area_name_keep_every_previous_heading(client, path: str) -> None:
    """Keep legacy area and meal headings alongside the current concise public copy."""
    staff = cafeteria_snapshot(area=False, times=False)
    patient = patient_snapshot(area=False, times=False)
    body = _body(client, path, staff=staff, patient=patient)
    for fragment in LEGACY_TEXTS[path]:
        assert fragment in body, fragment


# --- weekend behaviour of the cafeteria day page ---------------------------

def _saturday(client) -> None:
    client.application_under_test.config['DEMO_TODAY'] = '2026-09-05'


def test_open_saturday_shows_menus_on_the_cafeteria_day_page(client) -> None:
    _saturday(client)
    body = _body(client, '/cafeteria/heute/',
                 staff=cafeteria_snapshot(area=True, times=True, saturday='open'))
    assert 'Heutige Cafeteria-Menüs' in body
    assert 'Mittag 11:30–14:00 Uhr' in body
    assert 'Cafeteria geschlossen' not in body


def test_closed_saturday_shows_its_notice_on_the_cafeteria_day_page(client) -> None:
    _saturday(client)
    body = _body(client, '/cafeteria/heute/',
                 staff=cafeteria_snapshot(area=True, times=True, saturday='closed'))
    assert 'Cafeteria geschlossen' in body
    assert 'Am Samstag geschlossen.' in body
    assert '11:30' not in body


def test_saturday_without_a_service_keeps_the_day_notice(client) -> None:
    _saturday(client)
    body = _body(client, '/cafeteria/heute/', staff=cafeteria_snapshot(area=True, times=True))
    assert '<div class="text-secondary">Cafeteria geschlossen</div>' in body
    assert '11:30' not in body


def test_a_fully_open_weekend_names_the_range_monday_to_sunday(client) -> None:
    body = _body(client, '/cafeteria/wochenangebot/',
                 staff=cafeteria_snapshot(area=True, times=True, saturday='open', sunday='open'))
    assert 'Montag bis Sonntag' in body
    assert 'Samstag' in body and 'Sonntag' in body
