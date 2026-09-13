from __future__ import annotations

import csv
import io

from cafeteria import db as database
from cafeteria.csvio import CAFETERIA_HEADERS, PATIENT_HEADERS, snapshot_to_csv, validate_upload
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
    database_engine,
)


def _schema_2(csv_bytes: bytes) -> bytes:
    reader = csv.DictReader(io.StringIO(csv_bytes.decode('utf-8-sig')), delimiter=';')
    headers = [header for header in reader.fieldnames or [] if header != 'beilage_dazu']
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
    assert {row['schema_version'] for row in rows} == {'3'}
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


def test_templates_and_examples_ship_schema_3_accompaniment_contract() -> None:
    for profile, prefix, expected_headers in (
        ('patient', 'menu_patient', PATIENT_HEADERS),
        ('staff_guest', 'menu_cafeteria', CAFETERIA_HEADERS),
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
        assert {row['schema_version'] for row in rows} == {'3'}
        assert {row['beilage_dazu'] for row in rows} <= {'', 'suppe', 'salat'}
        assert {'suppe', 'salat'} <= {row['beilage_dazu'] for row in rows}
        validated = validate_upload(io.BytesIO(example))
        assert validated['valid'] is True
        assert validated['profile'] == profile


def test_published_week_csv_roundtrip_preserves_accompaniments_in_empty_week(
    database_engine,
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
