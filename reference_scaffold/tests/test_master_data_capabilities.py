"""The Python capability matrix and actual PostgreSQL guard must agree."""
import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError, OperationalError
from werkzeug.exceptions import Unauthorized

from cafeteria import master_data_store as store
from cafeteria.master_data_types import MasterDataUnavailableError
from cafeteria.roles import capabilities
from test_master_data_db import (  # noqa: F401
    master, seeded_pg16, installed_pg16, pg16, app_engine, make_actor, signed_in,
)


@pytest.mark.parametrize('role', ['Cafeteria.Editor','Cafeteria.Publisher','Cafeteria.Admin'])
@pytest.mark.parametrize('capability', ['masterdata.write','recipe.write','recipe.import'])
def test_python_and_sql_capability_matrix_agree(master, role, capability):  # noqa: F811
    owner, _, _ = master
    actor = make_actor(owner, role)
    expected = '*' in capabilities([role]) or capability in capabilities([role])
    def guard():
        with owner.begin() as c:
            c.execute(text('SELECT cafeteria.require_master_data_actor(:actor,:version,:capability)'),
                      {'actor': actor.user_id,'version':actor.authz_version,'capability':capability})
    if expected:
        guard()
    else:
        with pytest.raises(DBAPIError) as error:
            guard()
        assert error.value.orig.sqlstate == 'P1902'


def test_internal_guard_is_never_application_callable(master):  # noqa: F811
    owner, _, _ = master
    with owner.connect() as c:
        assert c.execute(text("""SELECT has_function_privilege('cafeteria_app',
            'cafeteria.require_master_data_actor(bigint,bigint,text)','EXECUTE'),
            has_function_privilege('public','cafeteria.require_master_data_actor(bigint,bigint,text)','EXECUTE'),
            has_function_privilege('cafeteria_auth_issuer','cafeteria.require_master_data_actor(bigint,bigint,text)','EXECUTE')""")).one() == (False,False,False)


def test_reader_availability_wrapper_covers_capability_lookup(master, monkeypatch):  # noqa: F811
    _, engine, _ = master
    def fail(*args, **kwargs):
        raise OperationalError('private connection detail', {}, RuntimeError('private source'))
    monkeypatch.setattr(engine, 'connect', fail)
    with pytest.raises(MasterDataUnavailableError) as error:
        store.list_foods(engine)
    assert 'private' not in str(error.value)


def test_reader_requires_session(master):  # noqa: F811
    _, engine, _ = master
    from flask import session
    session.clear()
    with pytest.raises(Unauthorized):
        store.list_foods(engine)
