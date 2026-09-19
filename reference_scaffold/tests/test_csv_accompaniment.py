from __future__ import annotations

import csv
import io

import pytest

from cafeteria import csvio
from cafeteria import db as database
from cafeteria.csvio import (
    SCHEMA_4_CAFETERIA_HEADERS,
    SCHEMA_4_PATIENT_HEADERS,
    snapshot_to_csv,
    validate_upload,
)
from cafeteria.db import active_snapshot
from cafeteria.workflow import import_draft, load_draft, publish_draft
from cafeteria.workflow_snapshot import build_snapshot
from review_support import write_expectations
from test_admin_workflow_db import (
    APP_PASSWORD,
    BACKUP_PASSWORD,
    DATABASE_URL,
    ISSUER_PASSWORD,
    ROOT,
    WEEK_START,
    _actor_id,
    _drop_schema,
    _patient_values,
    _save_reviewed,
    database_engine,  # noqa: F401
)


def _schema_2(csv_bytes: bytes) -> bytes:
    reader = csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig')), delimiter=';')
    drop = {'beilage_dazu', 'suppe', 'suppe_geltung', 'dessert', 'dessert_geltung'}
    headers = [header for header in reader.fieldnames or [] if header not in drop]
    rows = list(reader)
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=';', lineterminator='\r\n')
    writer.writeheader()
    for row in rows:
        row['schema_version'] = '2'
        writer.writerow({header: row[header] for header in headers})
    return ('\ufeff' + buffer.getvalue()).encode()


def _first_codes(values: dict[str, object]) -> list[str]:
    days = values['days']
    assert isinstance(days, list)
    options = days[0]['services'][0]['options']
    return [option['accompaniment_code'] for option in options] + [
        days[0]['services'][1]['options'][0]['accompaniment_code']
    ]


def _snapshot_from_values(values: dict[str, object]) -> dict[str, object]:
    return build_snapshot(
        'patient',
        {
            **values,
            'week_start': WEEK_START.isoformat(),
            'location': {'code': 'KIRCHLINDACH', 'name': 'Südhang'},
            'area_name': 'Patientinnen und Patienten',
        },
        'PAT-2026-KW36-R1',
    )


def test_schema_3_export_import_maps_values_and_positions_invalid_field() -> None:
    values = _patient_values()
    options = values['days'][0]['services'][0]['options']
    options[0]['accompaniment_code'] = 'soup'
    options[1]['accompaniment_code'] = 'salad'
    values['days'][0]['services'][1]['options'][0]['accompaniment_code'] = 'none'
    snapshot = _snapshot_from_values(values)

    exported = snapshot_to_csv(snapshot)
    decoded = exported.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(decoded), delimiter=';')
    rows = list(reader)

    assert (reader.fieldnames or [])[10] == 'beilage_dazu'
    assert {row['schema_version'] for row in rows} == {'4'}
    assert 'suppe' in (reader.fieldnames or [])
    assert 'dessert' in (reader.fieldnames or [])
    assert 'suppe_geltung' in (reader.fieldnames or [])
    assert [row['beilage_dazu'] for row in rows[:3]] == ['suppe', 'salat', '']
    imported = validate_upload(io.BytesIO(exported))
    assert imported['valid'] is True
    assert _first_codes(imported['values']) == ['soup', 'salad', 'none']

    rows[1]['beilage_dazu'] = 'beides'
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=reader.fieldnames, delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    invalid = validate_upload(io.BytesIO(buffer.getvalue().encode()))
    assert invalid['valid'] is False
    assert {
        (issue['line'], issue['column'])
        for issue in invalid['issues']
    } >= {(3, 11)}

    staff_source = (ROOT / 'csv' / 'menu_cafeteria_example.csv').read_text(
        encoding='utf-8-sig'
    )
    staff_reader = csv.DictReader(io.StringIO(staff_source), delimiter=';')
    staff_rows = list(staff_reader)
    staff_rows[0]['beilage_dazu'] = 'beides'
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(
        buffer,
        fieldnames=staff_reader.fieldnames,
        delimiter=';',
        lineterminator='\n',
    )
    writer.writeheader()
    writer.writerows(staff_rows)
    staff_invalid = validate_upload(io.BytesIO(buffer.getvalue().encode()))
    assert staff_invalid['valid'] is False
    assert {
        (issue['line'], issue['column'], issue['message'])
        for issue in staff_invalid['issues']
    } >= {(2, 11, 'beilage_dazu muss leer, suppe oder salat sein.')}


def test_snapshot_to_csv_raises_on_unpaired_accompaniment_keys() -> None:
    base_option = {
        'type_code': 'MENU_1', 'external_id': 'X1', 'title': 'Titel', 'description': '',
        'components': [], 'labels': [], 'allergens': [], 'origins': [], 'note': '',
    }
    snapshot = {
        'profile_code': 'patient',
        'days': [
            {
                'date': '2026-08-31',
                'weekday': 'Montag',
                'services': [
                    {
                        'meal_code': 'LUNCH',
                        'service_state': 'open',
                        'notice': '',
                        'options': [{**base_option, 'accompaniment_code': 'soup'}],
                    }
                ],
            }
        ],
    }
    with pytest.raises(ValueError):
        snapshot_to_csv(snapshot)

    snapshot['days'][0]['services'][0]['options'][0] = {
        **base_option,
        'accompaniment_name': 'Suppe',
    }
    with pytest.raises(ValueError):
        snapshot_to_csv(snapshot)


def test_mixed_schema_version_rejects_file_but_still_flags_invalid_accompaniment() -> None:
    values = _patient_values()
    values['days'][0]['services'][0]['options'][0]['accompaniment_code'] = 'soup'
    snapshot = _snapshot_from_values(values)
    exported = snapshot_to_csv(snapshot).decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(exported), delimiter=';')
    fieldnames = reader.fieldnames or []
    rows = list(reader)
    rows[0]['schema_version'] = '2'
    rows[1]['beilage_dazu'] = 'beides'

    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=fieldnames, delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)

    result = validate_upload(io.BytesIO(('\ufeff' + buffer.getvalue()).encode()))

    assert result['valid'] is False
    assert result['schema_version'] is None
    beilage_column = fieldnames.index('beilage_dazu') + 1
    schema_column = fieldnames.index('schema_version') + 1
    columns = {issue['column'] for issue in result['issues']}
    assert schema_column in columns
    assert (3, beilage_column) in {
        (issue['line'], issue['column']) for issue in result['issues']
    }


def test_option_rejects_unknown_accompaniment_value_with_field_context() -> None:
    row = {
        'menueart': 'MENU_1', 'external_id': 'X1', 'titel': 'Titel', 'beschreibung': '',
        'beilagen': '', 'labels': '', 'allergene_enthaelt': '', 'allergene_spuren': '',
        'herkunft': '', 'hinweis': '', 'beilage_dazu': 'beides',
    }
    with pytest.raises(ValueError, match='beilage_dazu'):
        csvio._option(row, 'patient')


def test_option_normalizes_none_accompaniment_cell_without_attribute_error() -> None:
    row = {
        'menueart': 'MENU_1', 'external_id': 'X1', 'titel': 'Titel', 'beschreibung': '',
        'beilagen': '', 'labels': '', 'allergene_enthaelt': '', 'allergene_spuren': '',
        'herkunft': '', 'hinweis': '', 'beilage_dazu': None,
    }
    assert csvio._option(row, 'patient')['accompaniment_code'] == 'none'


def test_schema_2_full_replace_resets_existing_accompaniments_to_none(
    database_engine,  # noqa: F811
) -> None:
    values = _patient_values()
    values['days'][0]['services'][0]['options'][0]['accompaniment_code'] = 'soup'
    values['days'][0]['services'][0]['options'][1]['accompaniment_code'] = 'salad'
    schema_3_bytes = snapshot_to_csv(_snapshot_from_values(values))

    actor_id = _actor_id(database_engine)
    imported_schema_3 = validate_upload(io.BytesIO(schema_3_bytes))
    assert imported_schema_3['valid'] is True
    version = import_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=0,
        actor_id=actor_id,
        values=imported_schema_3['values'],
        **write_expectations(database_engine, actor_id),
    )
    assert _first_codes(
        load_draft(
            database_engine,
            'patient',
            WEEK_START,
            actor_id=actor_id,
            **write_expectations(database_engine, actor_id),
        )
    )[:2] == ['soup', 'salad']

    imported_schema_2 = validate_upload(io.BytesIO(_schema_2(schema_3_bytes)))
    assert imported_schema_2['valid'] is True
    import_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=version,
        actor_id=actor_id,
        values=imported_schema_2['values'],
        **write_expectations(database_engine, actor_id),
    )

    reloaded = load_draft(
        database_engine,
        'patient',
        WEEK_START,
        actor_id=actor_id,
        **write_expectations(database_engine, actor_id),
    )
    assert set(_first_codes(reloaded)) == {'none'}


def test_schema_2_import_defaults_none_and_reports_replacement_notice() -> None:
    values = _patient_values()
    snapshot = _snapshot_from_values(values)

    imported = validate_upload(io.BytesIO(_schema_2(snapshot_to_csv(snapshot))))

    assert imported['valid'] is True
    assert imported['schema_version'] == 2
    assert imported['warnings'] == [
        'Schema-2-Vollimport: Bestehende Beilagen werden auf «Keine» zurückgesetzt.'
    ]
    assert set(_first_codes(imported['values'])) == {'none'}


def test_templates_and_examples_ship_schema_4_accompaniment_contract() -> None:
    for profile, prefix, expected_headers in (
        ('patient', 'menu_patient', SCHEMA_4_PATIENT_HEADERS),
        ('staff_guest', 'menu_cafeteria', SCHEMA_4_CAFETERIA_HEADERS),
    ):
        template = (ROOT / 'csv' / f'{prefix}_template.csv').read_text(encoding='utf-8-sig')
        assert template.splitlines() == [';'.join(expected_headers)]

        example = (ROOT / 'csv' / f'{prefix}_example.csv').read_bytes()
        reader = csv.DictReader(
            io.StringIO(example.decode('utf-8-sig')),
            delimiter=';',
        )
        rows = list(reader)
        assert reader.fieldnames == expected_headers
        assert {row['schema_version'] for row in rows} == {'4'}
        assert {row['beilage_dazu'] for row in rows} <= {'', 'suppe', 'salat'}
        assert {'suppe', 'salat'} <= {row['beilage_dazu'] for row in rows}
        validated = validate_upload(io.BytesIO(example))
        assert validated['valid'] is True
        assert validated['profile'] == profile


def test_published_week_csv_roundtrip_preserves_accompaniments_in_empty_week(
    database_engine,  # noqa: F811
) -> None:
    values = _patient_values()
    first_service = values['days'][0]['services'][0]
    first_service['options'][0]['accompaniment_code'] = 'soup'
    first_service['options'][1]['accompaniment_code'] = 'salad'
    values['days'][0]['services'][1]['options'][0]['accompaniment_code'] = 'none'
    actor_id = _actor_id(database_engine)
    version = _save_reviewed(database_engine, 'patient', values)
    publish_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=version,
        actor_id=actor_id,
        issuer_engine=database_engine,
    )
    published = active_snapshot(database_engine, 'patient', '2026-09-02')
    assert published is not None
    exported = snapshot_to_csv(published)

    _drop_schema(database_engine)
    assert DATABASE_URL is not None
    database.init_database(
        DATABASE_URL,
        str(ROOT / 'database' / 'schema.sql'),
        str(ROOT / 'database' / 'seed.sql'),
        permissions_path=str(ROOT / 'database' / 'permissions.sql'),
        app_password=APP_PASSWORD,
        backup_password=BACKUP_PASSWORD,
        auth_issuer_password=ISSUER_PASSWORD,
    )
    imported = validate_upload(io.BytesIO(exported))
    assert imported['valid'] is True
    new_actor_id = _actor_id(database_engine)
    import_draft(
        database_engine,
        'patient',
        WEEK_START,
        expected_row_version=0,
        actor_id=new_actor_id,
        values=imported['values'],
        **write_expectations(database_engine, new_actor_id),
    )

    reloaded = load_draft(
        database_engine,
        'patient',
        WEEK_START,
        actor_id=new_actor_id,
        **write_expectations(database_engine, new_actor_id),
    )
    assert _first_codes(reloaded) == ['soup', 'salad', 'none']


def test_schema_4_invalid_course_uuid_is_a_positioned_issue() -> None:
    values = _patient_values()
    exported = snapshot_to_csv(_snapshot_from_values(values))
    decoded = exported.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(decoded), delimiter=';')
    headers = list(reader.fieldnames or [])
    rows = list(reader)
    rows[0]['suppe'] = 'not-a-uuid'
    rows[0]['suppe_geltung'] = 'gemeinsam'
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    csv_text = buffer.getvalue()
    exact = csvio._validator().validate_text(csv_text, '<upload>')
    assert exact['valid'] is False
    suppe_column = headers.index('suppe') + 1
    assert {
        (issue['line'], issue['column'])
        for issue in exact['issues']
    } >= {(2, suppe_column)}
    assert any(
        issue['line'] == 2 and 'suppe muss leer, keine oder eine gültige Rezept-UUID' in issue['message']
        for issue in exact['issues']
    )
    invalid = validate_upload(io.BytesIO(('\ufeff' + csv_text).encode()))
    assert invalid['valid'] is False
    assert {
        (issue['line'], issue['column'])
        for issue in invalid['issues']
    } >= {(2, suppe_column)}


@pytest.mark.parametrize(
    ('raw_value', 'message'),
    (
        ("''00000000-0000-4000-8000-000000000001", 'höchstens 37 Zeichen'),
        ('00000000-0000-4000-8000-000000000001\x01', 'C0-Kontrollzeichen'),
    ),
)
def test_schema_4_course_cell_rejects_raw_length_and_controls_with_position(
    raw_value: str,
    message: str,
) -> None:
    values = _patient_values()
    exported = snapshot_to_csv(_snapshot_from_values(values))
    reader = csv.DictReader(
        io.StringIO(exported.decode('utf-8-sig')),
        delimiter=';',
    )
    headers = list(reader.fieldnames or [])
    rows = list(reader)
    rows[0]['suppe'] = raw_value
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)

    exact = csvio._validator().validate_text(buffer.getvalue(), '<upload>')

    suppe_column = headers.index('suppe') + 1
    matching = [
        issue for issue in exact['issues']
        if issue['line'] == 2 and issue['column'] == suppe_column
    ]
    assert matching
    assert any('suppe' in issue['message'] and message in issue['message'] for issue in matching)
    with pytest.raises(ValueError, match=message):
        csvio._payload_from_cell(raw_value)


def test_schema_4_inaccessible_uuid_is_format_ok_and_carries_line() -> None:
    values = _patient_values()
    exported = snapshot_to_csv(_snapshot_from_values(values))
    decoded = exported.decode('utf-8-sig')
    reader = csv.DictReader(io.StringIO(decoded), delimiter=';')
    headers = list(reader.fieldnames or [])
    rows = list(reader)
    missing = '00000000-0000-4000-8000-000000000099'
    rows[0]['suppe'] = missing
    rows[0]['suppe_geltung'] = 'gemeinsam'
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=headers, delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    imported = validate_upload(io.BytesIO(('\ufeff' + buffer.getvalue()).encode()))
    assert imported['valid'] is True
    courses = imported['csv_courses']
    assert courses is not None
    first_day = values['days'][0]['date']
    payload = courses[(first_day, 'LUNCH')]['soup']
    assert payload['state'] == 'planned'
    assert payload['recipe_public_id'] == missing
    assert payload['line'] == 2
    assert payload['field'] == 'soup'
