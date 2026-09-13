"""Application-store contract for dish-template accompaniment defaults on schema 32."""
from __future__ import annotations

import pytest
from sqlalchemy import text

from cafeteria import dish_template_store as store
from cafeteria.recipe_reads import get_location
from cafeteria.recipe_types import RecipeValidationError
from test_dish_template_routes import b3, snapshot  # noqa: F401
from test_master_data_routes import app_engine, installed_pg16, pg16, seeded_pg16  # noqa: F401


def _payload(**updates) -> dict[str, object]:
    values: dict[str, object] = {
        'menu_type_code': 'MENU_1',
        'profile_scope': 'common',
        'title': 'Store-Vorschlag',
        'description': None,
        'recipe_public_id': None,
    }
    values.update(updates)
    return values


def test_store_uses_v32_optional_default_and_preserves_noop_cas(b3):  # noqa: F811
    app, owner, _, actor = b3
    engine = app.extensions['cafeteria_db']
    location = get_location(engine)

    created = store.create_template(
        engine, actor, _payload(), expected_location_id=location,
    )
    row = store.get_template(engine, created['public_id'])
    assert row.accompaniment_default == 'none'

    changed = store.update_template(
        engine, actor, row.public_id, row.updated_at,
        _payload(accompaniment_default='soup'), expected_location_id=location,
    )
    row = store.get_template(engine, row.public_id)
    assert row.accompaniment_default == 'soup'
    assert row.updated_at.isoformat() == changed['updated_at']
    with owner.connect() as connection:
        audit = connection.execute(text("""SELECT action,details FROM cafeteria.audit_events
            WHERE entity_public_id=CAST(:public_id AS uuid)
            ORDER BY id DESC LIMIT 1"""), {'public_id': row.public_id}).one()
    assert audit.action == 'dish_template.updated'
    assert audit.details['accompaniment_default'] == 'soup'

    before_noop = snapshot(owner)
    retained = store.update_template(
        engine, actor, row.public_id, row.updated_at, _payload(),
        expected_location_id=location,
    )
    assert retained['updated_at'] == changed['updated_at']
    assert snapshot(owner) == before_noop
    assert store.get_template(engine, row.public_id).accompaniment_default == 'soup'

    with pytest.raises(RecipeValidationError, match='Bitte eine gültige Beilage wählen'):
        store.update_template(
            engine, actor, row.public_id, row.updated_at,
            _payload(accompaniment_default='both'), expected_location_id=location,
        )
    assert snapshot(owner) == before_noop
