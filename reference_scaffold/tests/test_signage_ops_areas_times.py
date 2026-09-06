"""OPS-001: area names, serving times and weekend behaviour on the signage players."""
from __future__ import annotations

import pytest
from playwright.sync_api import Browser

from test_public_ops_areas_times import (  # noqa: F401
    CAFETERIA_AREA,
    PATIENT_AREA,
    cafeteria_snapshot,
    client,
    patient_snapshot,
)
from test_rendered_ui import _page
from test_rendered_ui import browser as browser  # noqa: F401

PLAYERS = ('/signage/cafeteria/tag', '/signage/cafeteria/woche',
           '/signage/patienten/tag', '/signage/patienten/woche')


def _body(published, path: str, staff=None, patient=None) -> str:
    published.snapshots['staff_guest'] = staff
    published.snapshots['patient'] = patient
    response = published.get(path)
    assert response.status_code == 200, path
    return response.get_data(as_text=True)


@pytest.mark.parametrize('path', ('/signage/cafeteria/tag', '/signage/cafeteria/woche'))
def test_cafeteria_players_show_the_area_name_and_its_serving_time(client, path: str) -> None:  # noqa: F811
    body = _body(client, path, staff=cafeteria_snapshot(area=True, times=True))
    assert CAFETERIA_AREA in body
    assert 'Mittag 11:30–13:30 Uhr' in body
    assert 'Cafeteria · Mittag für Mitarbeitende und externe Gäste' not in body


@pytest.mark.parametrize('path', ('/signage/cafeteria/tag', '/signage/cafeteria/woche'))
def test_cafeteria_players_without_area_keep_their_previous_kicker(client, path: str) -> None:  # noqa: F811
    body = _body(client, path, staff=cafeteria_snapshot(area=False, times=False))
    assert 'Cafeteria · ' in body
    assert 'Uhr' not in body


def test_patient_day_player_shows_times_and_keeps_the_closed_notice(client) -> None:  # noqa: F811
    body = _body(client, '/signage/patienten/tag',
                 patient=patient_snapshot(area=True, times=True, closed_dinner=True))
    assert PATIENT_AREA in body
    assert 'Ausgabe 11:30–13:30 Uhr' in body
    assert 'Das Abendessen wird auf der Station serviert.' in body
    assert 'Ausgabe ab 17:30 Uhr' not in body


def test_patient_day_player_keeps_the_fixed_texts_without_an_area_name(client) -> None:  # noqa: F811
    body = _body(client, '/signage/patienten/tag', patient=patient_snapshot(area=False, times=False))
    assert 'Ausgabe ab 11:30 Uhr' in body
    assert 'Ausgabe ab 17:30 Uhr' in body


def test_patient_week_player_gains_no_time_line_without_an_area_name(client) -> None:  # noqa: F811
    body = _body(client, '/signage/patienten/woche', patient=patient_snapshot(area=False, times=False))
    assert 'Ausgabe' not in body
    body_with_times = _body(client, '/signage/patienten/woche',
                            patient=patient_snapshot(area=True, times=True))
    assert 'Ausgabe 11:30–13:30 Uhr' in body_with_times


def test_open_saturday_reaches_the_cafeteria_week_player(client) -> None:  # noqa: F811
    body = _body(client, '/signage/cafeteria/woche',
                 staff=cafeteria_snapshot(area=True, times=True, saturday='open'))
    assert 'Samstag' in body
    assert 'Sonntag' not in body


def test_closed_saturday_falls_back_to_the_closed_board_with_its_notice(client) -> None:  # noqa: F811
    client.application_under_test.config['DEMO_TODAY'] = '2026-09-05'
    body = _body(client, '/signage/cafeteria/tag',
                 staff=cafeteria_snapshot(area=True, times=True, saturday='closed'))
    assert 'Am Samstag geschlossen.' in body
    assert 'hero-food-grid' not in body
    assert CAFETERIA_AREA in body


def test_open_saturday_shows_menus_on_the_cafeteria_day_player(client) -> None:  # noqa: F811
    client.application_under_test.config['DEMO_TODAY'] = '2026-09-05'
    body = _body(client, '/signage/cafeteria/tag',
                 staff=cafeteria_snapshot(area=True, times=True, saturday='open'))
    assert 'hero-food-grid' in body
    assert 'Mittag 11:30–14:00 Uhr' in body


def test_sunday_without_a_service_keeps_the_standard_weekend_text(client) -> None:  # noqa: F811
    client.application_under_test.config['DEMO_TODAY'] = '2026-09-06'
    body = _body(client, '/signage/cafeteria/tag', staff=cafeteria_snapshot(area=True, times=True))
    assert 'Am Wochenende bleibt die Cafeteria geschlossen.' in body
    assert '11:30' not in body


LEGACY_TEXTS = {
    '/signage/cafeteria/tag': (
        '<title>Cafeteria-Tagesplan</title>',
        'Cafeteria · Mittag für Mitarbeitende und externe Gäste',
    ),
    '/signage/cafeteria/woche': (
        '<title>Cafeteria-Wochenplan</title>',
        'Cafeteria · Wochenangebot · Mittag',
    ),
    '/signage/patienten/tag': (
        '<title>Patienten-Tagesplan</title>',
        'Speiseplan für Patientinnen und Patienten',
    ),
    '/signage/patienten/woche': (
        '<title>Patienten-Wochenplan</title>',
        'Patienten-Speiseplan · Mittag und Abend',
    ),
}


@pytest.mark.parametrize('path', tuple(LEGACY_TEXTS))
def test_players_without_an_area_name_keep_every_previous_heading(client, path: str) -> None:  # noqa: F811
    body = _body(client, path,
                 staff=cafeteria_snapshot(area=False, times=False),
                 patient=patient_snapshot(area=False, times=False))
    for fragment in LEGACY_TEXTS[path]:
        assert fragment in body, fragment


def test_closed_board_without_an_area_name_keeps_its_previous_headings(client) -> None:  # noqa: F811
    client.application_under_test.config['DEMO_TODAY'] = '2026-09-06'
    body = _body(client, '/signage/cafeteria/tag', staff=cafeteria_snapshot(area=False, times=False))
    assert '<title>Cafeteria geschlossen</title>' in body
    assert '<h1>Cafeteria geschlossen</h1>' in body
    assert 'Cafeteria · Tagesinformation' in body


@pytest.mark.parametrize(('width', 'height'), ((1920, 1080), (3840, 2160)))
@pytest.mark.parametrize('path', PLAYERS)
def test_players_with_times_stay_inside_the_screen(
    client, browser: Browser, path: str, width: int, height: int,  # noqa: F811
) -> None:
    body = _body(client, path,
                 staff=cafeteria_snapshot(area=True, times=True),
                 patient=patient_snapshot(area=True, times=True))
    page = _page(browser, body, width, height)
    try:
        assert page.evaluate(
            'document.documentElement.scrollWidth <= innerWidth + 1'
            ' && document.documentElement.scrollHeight <= innerHeight + 1'
        )
        assert page.locator('h1').count() == 1
    finally:
        page.close()
