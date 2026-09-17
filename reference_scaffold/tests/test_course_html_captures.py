"""Write week/calendar HTML twice to the goal scratch dir for launch comparison."""
from __future__ import annotations

from pathlib import Path

from cafeteria.admin import calendar_routes as calendar_routes  # noqa: F401
from cafeteria.course_store import persist_service_courses
from cafeteria.workflow_partial_store import persist_menu_item, persist_service_state
from test_admin_workflow_routes import DAY, WEEK, _login, _scope
from test_course_week_html import _recipe
from test_workflow_partial_store_db import _payload, _service_payload

pytest_plugins = ['test_admin_workflow_routes']

SCRATCH = Path('/tmp/grok-goal-f7e8c549e979/implementer')
TARGETS = {
    'cafeteria': ('/admin/cafeteria?week=' + DAY, SCRATCH / 'week-cafeteria.html'),
    'patienten': ('/admin/patienten?week=' + DAY, SCRATCH / 'week-patienten.html'),
    'kuechenkalender': ('/admin/kuechenkalender?year=2026&month=8', SCRATCH / 'kuechenkalender.html'),
}


def test_week_and_calendar_html_is_stable_across_two_launches(app, database_engine) -> None:
    client, user_id = _login(app, database_engine, ['Cafeteria.Admin'])
    engine = app.extensions['cafeteria_db']
    cafeteria = _scope(database_engine, user_id, 'staff_guest')
    patient = _scope(database_engine, user_id, 'patient')
    persist_service_state(engine, cafeteria, WEEK, DAY, 'LUNCH', _service_payload(), 0)
    persist_menu_item(engine, cafeteria, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(engine, cafeteria, WEEK, DAY, 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    persist_service_state(engine, patient, WEEK, DAY, 'LUNCH', _service_payload(), 0)
    persist_menu_item(engine, patient, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(), 0)
    recipe = _recipe(engine, user_id, cafeteria.location_id, 'Gemüsesuppe')
    persist_service_courses(
        engine, cafeteria, WEEK, DAY, 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': recipe['public_id']},
        dessert={'state': 'not_offered'},
        exceptions=[],
    )
    SCRATCH.mkdir(parents=True, exist_ok=True)
    first: dict[str, str] = {}
    for launch in (1, 2):
        lines = []
        for name, (path, dest) in TARGETS.items():
            response = client.get(path)
            html = response.get_data(as_text=True)
            lines.append(f'{path} {response.status_code} {len(html)}')
            assert response.status_code == 200, path
            dest.write_text(html)
            if launch == 1:
                first[name] = html
            else:
                assert html == first[name]
        (SCRATCH / f'launch-{launch}.log').write_text('\n'.join(lines) + '\n')
    cafeteria_html = first['cafeteria']
    assert cafeteria_html.count('Suppe: Gemüsesuppe') == 1
    assert 'Kein Dessert' in cafeteria_html
    assert 'data-course="soup"' in cafeteria_html
    assert 'Gänge planen' in cafeteria_html
    assert 'Gänge planen' in first['patienten']
    assert 'kitchen-cal-toolbar' in first['kuechenkalender']
    assert 'patient LUNCH' not in first['kuechenkalender']
