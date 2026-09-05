from __future__ import annotations

import pytest
from sqlalchemy import create_engine, text
from sqlalchemy.pool import NullPool

from cafeteria.admin import week_management_routes
from cafeteria.component_catalog_store import ComponentCatalogConfigurationError
from test_admin_workflow_routes import (
    DATABASE_URL, app as app, client as client, database_engine as database_engine,
)
from test_menu_collection import _save, _scope

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='Isolierte PostgreSQL-Testdatenbank fehlt.')


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_week_index_works_with_actual_runtime_location_read_privileges(
    app, client, database_engine, monkeypatch, family, profile,
):
    scope = _scope(client, database_engine, profile)
    _save(database_engine, scope)
    runtime = create_engine(database_engine.url, poolclass=NullPool,
                            connect_args={'options': '-c role=cafeteria_app'})
    try:
        with runtime.connect() as connection:
            privileges = connection.execute(text("""
                SELECT current_user,
                  has_table_privilege(current_user, 'cafeteria.locations', 'SELECT'),
                  has_table_privilege(current_user, 'cafeteria.locations', 'UPDATE'),
                  has_any_column_privilege(current_user, 'cafeteria.locations', 'UPDATE')
            """)).one()
            assert tuple(privileges) == ('cafeteria_app', True, False, False)
            before = connection.execute(text('SELECT id,row_version FROM cafeteria.menu_weeks ORDER BY id')).all()
        monkeypatch.setitem(app.extensions, 'cafeteria_db', runtime)
        response = client.get(f'/admin/{family}/wochen')
        assert response.status_code == 200
        assert response.headers['Cache-Control'] == 'no-store'
        assert 'Testwoche' in response.get_data(as_text=True)
        with runtime.connect() as connection:
            assert connection.execute(text('SELECT id,row_version FROM cafeteria.menu_weeks ORDER BY id')).all() == before
    finally:
        runtime.dispose()


@pytest.mark.parametrize('change', ['different', 'none', 'multiple'])
def test_location_change_during_status_read_fails_closed(client, database_engine, monkeypatch, change):
    scope = _scope(client, database_engine)
    _save(database_engine, scope)

    def status_with_location_change(*_args):
        with database_engine.begin() as connection:
            if change != 'multiple':
                connection.execute(text('UPDATE cafeteria.locations SET active=false'))
            if change != 'none':
                connection.execute(text("INSERT INTO cafeteria.locations(code,name,active) VALUES ('NEXT','Andere Küche',true)"))
        return 'empty'

    monkeypatch.setattr(week_management_routes, 'derive_admin_status', status_with_location_change)
    with pytest.raises(ComponentCatalogConfigurationError):
        week_management_routes.find_weeks(database_engine, scope)
