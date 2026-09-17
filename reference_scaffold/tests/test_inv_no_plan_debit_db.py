"""Plan, freeze, event and CSV import never write inventory movements."""
from datetime import date
from io import BytesIO

from sqlalchemy import text

from cafeteria.calendar_event_store import EventScope, create_event
from cafeteria.csvio import validate_upload
from prepared_food_fixtures import create_food, create_recipe, freeze, prepared  # noqa: F401
from test_component_metadata_master_lock_db import (  # noqa: F401
    app_engine, installed_pg16, pg16, seeded_pg16,
)


def _movements(owner) -> int:
    with owner.connect() as connection:
        return connection.execute(text('SELECT count(*) FROM cafeteria.inventory_movements')).scalar_one()


def test_freeze_and_event_do_not_post_movements(prepared):  # noqa: F811
    owner, engine, ids = prepared
    food = create_food(engine, ids, 'Planzutat', unit='G')
    recipe = create_recipe(engine, ids, [food], name='Planrezept')
    before = _movements(owner)
    freeze(engine, ids, recipe)
    create_event(
        engine, EventScope(ids['actor'], ids['location'], ids['authz']),
        event_date=date(2026, 9, 20), title='Ohne Bestand', profile_scope='staff_guest',
    )
    assert _movements(owner) == before


def test_csv_validate_does_not_post_movements(prepared):  # noqa: F811
    owner, engine, ids = prepared
    before = _movements(owner)
    validate_upload(BytesIO(b'profil;cafeteria\n'))
    assert _movements(owner) == before
