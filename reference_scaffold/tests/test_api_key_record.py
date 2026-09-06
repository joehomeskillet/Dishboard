from datetime import UTC, datetime

import pytest

from cafeteria.api_keys import _record, generate_api_key


@pytest.mark.parametrize(('field', 'value'), [
    ('scopes', 'preview.read'),
    ('scopes', {'preview.read': True}),
    ('scopes', ['preview.write']),
    ('scopes', [None]),
    ('created_at', None),
    ('created_at', '2026-09-06T00:00:00Z'),
    ('created_at', datetime(2026, 9, 6)),
    ('expires_at', '2026-10-06T00::00Z'),
    ('last_used_at', 123),
    ('revoked_at', False),
])
def test_record_rejects_invalid_database_values(field, value):
    row = {
        'public_id': '00000000-0000-0000-0000-000000000001',
        'label': 'Record boundary',
        'key_prefix': generate_api_key()[1],
        'scopes': ['preview.read'],
        'created_at': datetime(2026, 9, 6, tzinfo=UTC),
        'created_by_name': 'Test Admin',
        'expires_at': None,
        'last_used_at': None,
        'revoked_at': None,
    }
    row[field] = value
    with pytest.raises(ValueError):
        _record(row)
