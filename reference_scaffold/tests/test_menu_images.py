from __future__ import annotations

import datetime as dt
import hashlib
import json
from copy import deepcopy
from pathlib import Path

import pytest
from flask import Flask, render_template

from test_rendered_ui import app  # noqa: F401
from cafeteria.admin import menu_collection_routes, week_management_routes  # noqa: F401
from cafeteria.menu_images import menu_image

ROOT = Path(__file__).resolve().parents[2]
STATIC = ROOT / 'reference_scaffold/cafeteria/static'
SOURCE = json.loads((ROOT / 'design/menu-images/manifest.json').read_text())
READY = [row for row in SOURCE['images'] if row['status'] == 'ready']


def test_static_pack_covers_only_reviewed_compositions_with_original_bytes() -> None:
    rows = json.loads((STATIC / 'img/menus/manifest.json').read_text())
    assert len(rows) == len(READY) == 32
    expected = {(row['title'], tuple(row['components'])): row for row in READY}
    assert {(row['title'], tuple(row['components'])) for row in rows} == set(expected)
    files = set()
    for row in rows:
        original = expected[row['title'], tuple(row['components'])]
        assert row['status'] == 'ready'
        assert menu_image(row) == row['file']
        data = (STATIC / row['file']).read_bytes()
        assert data == (ROOT / original['file']).read_bytes()
        assert hashlib.sha256(data).hexdigest() == row['sha256'] == original['sha256']
        assert data[:2] == b'\xff\xd8'
        files.add((STATIC / row['file']).name)
    assert files == {path.name for path in (STATIC / 'img/menus').glob('*.jpg')}
    assert not {row['sha256'] for row in SOURCE['retired_assets']} & {row['sha256'] for row in rows}


@pytest.mark.parametrize('changes', [
    {'title': 'Pouletbrust'},
    {'title': READY[0]['title'] + ' '},
    {'components': list(reversed(READY[0]['components']))},
    {'components': READY[0]['components'][:1]},
    {'components': READY[0]['components'] + ['Brot']},
    {'components': None},
    {'components': 'Kartoffelstock, Zucchetti'},
    {'components': [{'name': 'Kartoffelstock'}, 'Zucchetti']},
])
def test_changed_composition_never_reuses_historical_id(changes: dict) -> None:
    option = deepcopy(READY[0])
    option.update(changes, id=77, external_id='77')
    assert menu_image(option) is None


def test_missing_and_duplicate_occurrences() -> None:
    assert menu_image(None) is None
    assert menu_image({}) is None
    option = next(row for row in READY if row['source_menu_ids'] == [81, 95])
    assert menu_image({**option, 'id': 81}) == menu_image({**option, 'id': 95})


@pytest.mark.parametrize('profile,path', [
    ('staff_guest', '/cafeteria/heute/'),
    ('staff_guest', '/cafeteria/wochenangebot/'),
    ('patient', '/patienten/heute/'),
    ('patient', '/patienten/wochenplan/'),
])
def test_public_routes_serve_matching_local_images_only(
    app: Flask, profile: str, path: str,  # noqa: F811
) -> None:
    snapshot = app.config['TEST_SNAPSHOTS'][profile]
    app.config['DEMO_TODAY'] = snapshot['days'][0]['date']
    first = snapshot['days'][0]['services'][0]['options'][0]
    filename = menu_image(first)
    assert filename is not None
    original = deepcopy(snapshot)
    client = app.test_client()
    response = client.get(path)
    assert response.status_code == 200
    body = response.get_data(as_text=True)
    assert '/static/' + filename in body
    assert 'width="1200" height="896" loading="lazy" decoding="async"' in body
    assert 'KI-generierter Serviervorschlag' in body
    image = client.get('/static/' + filename)
    assert image.status_code == 200 and image.mimetype == 'image/jpeg'
    assert image.data == (STATIC / filename).read_bytes()
    assert snapshot == original
    first['components'] = first['components'] + ['Andere Beilage']
    changed = client.get(path).get_data(as_text=True)
    assert '/static/' + filename not in changed


@pytest.mark.parametrize('profile,family', [('staff_guest', 'cafeteria'), ('patient', 'patienten')])
@pytest.mark.parametrize('template', ['admin/menu_collection.html', 'admin/preview.html'])
def test_saved_admin_templates_share_exact_image_matching(
    app: Flask, profile: str, family: str, template: str,  # noqa: F811
) -> None:
    option = deepcopy(app.config['TEST_SNAPSHOTS'][profile]['days'][0]['services'][0]['options'][0])
    filename = menu_image(option)
    assert filename
    date = dt.date(2026, 8, 31)
    row = {**option, 'id': 77, 'service_date': date, 'week_start': date,
           'meal_code': 'LUNCH', 'workflow_state': 'draft'}
    context = {
        'profile': profile, 'family': family, 'query': '', 'page': 1,
        'has_next': False, 'roles': [], 'rows': [row],
        'meal_labels': {'LUNCH': 'Mittag'}, 'option_labels': {'MENU_1': 'Menü 1'},
        'state': 'draft', 'week': date, 'week_iso': date.isoformat(),
        'draft': {'title': '', 'shared_note': '', 'days': [
            {'date': date.isoformat(), 'services': [
                {'meal_code': 'LUNCH', 'service_state': 'open', 'options': [row]},
            ]},
        ]},
    }
    with app.test_request_context():
        body = render_template(template, **context)
        assert body.count('/static/' + filename) == 1
        assert body.count('KI-generierter Serviervorschlag') == 1
        row['components'] = row['components'] + ['Neue Beilage']
        assert 'class="menu-photo"' not in render_template(template, **context)


def test_print_templates_do_not_embed_food_images() -> None:
    templates = ROOT / 'reference_scaffold/cafeteria/templates/public'
    for path in templates.glob('print_*.html'):
        assert '_menu_image.html' not in path.read_text()
