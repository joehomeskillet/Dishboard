"""Real lock ordering, original expectations and all-or-nothing writes."""
import json
import threading
from concurrent.futures import ThreadPoolExecutor

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError
from werkzeug.security import generate_password_hash

from cafeteria import master_data_store as store
from test_master_data_db import (  # noqa: F401
    master, seeded_pg16, installed_pg16, pg16, app_engine, payload, target, audit_count, make_actor, STORAGE_PUBLIC_ID,
)


UPDATE_FOOD = '''SELECT cafeteria.update_food_v27(:actor,:version,:location,CAST(:target AS uuid),
                 :target_version,CAST(:payload AS jsonb))'''
ASSIGN = '''SELECT cafeteria.replace_food_storage_locations_v21(:actor,:version,:location,CAST(:target AS uuid),
           :target_version,CAST(:payload AS jsonb))'''
ARCHIVE = '''SELECT cafeteria.set_active_storage_location_v21(:actor,:version,:location,CAST(:target AS uuid),
            :target_version,CAST(:payload AS jsonb))'''


def arguments(owner, actor, item, data):
    with owner.connect() as c:
        location = c.execute(text('SELECT id FROM cafeteria.locations WHERE active')).scalar_one()
    return {'actor': actor.user_id,'version':actor.authz_version,'location':location,
            'target':item.public_id,'target_version':item.row_version,'payload':json.dumps(data)}


def worker(engine, sql, params, started, state):
    try:
        with engine.begin() as c:
            state['pid'] = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            started.set()
            return c.execute(text(sql), params).scalar_one()
    except DBAPIError as error:
        return error.orig.sqlstate


def blocked(owner, started, state, blocker):
    assert started.wait(10)
    with owner.connect() as c:
        for _ in range(2000):
            if c.execute(text('SELECT pg_blocking_pids(:pid)'), {'pid':state['pid']}).scalar_one() == [blocker]:
                return
    pytest.fail('The competing write never waited on the expected PostgreSQL lock.')


@pytest.mark.parametrize('change', ['role_revoke','password_reset','role_definition'])
def test_first_serialized_authorization_change_prevents_food_write_and_audit(master, change):  # noqa: F811
    owner, engine, actor = master
    food = store.create_food(engine, actor, payload())
    if change == 'password_reset':
        admin = make_actor(owner, 'Cafeteria.Admin')
        password_hash = generate_password_hash('Isolierte-Testpassphrase-0907')
        with owner.begin() as c:
            for user, username in [(actor.user_id, 'master.actor'), (admin.user_id, 'master.admin')]:
                c.execute(text('INSERT INTO cafeteria.local_credentials(user_id,username,password_hash) VALUES(:id,:name,:hash)'),
                          {'id':user,'name':username,'hash':password_hash})
            actor_public_id = c.execute(text('SELECT public_id FROM cafeteria.users WHERE id=:id'), {'id':actor.user_id}).scalar_one()
    params = arguments(owner, actor, food, payload('Geändert'))
    count = audit_count(owner)
    started, state = threading.Event(), {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        with owner.begin() as c:
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            if change == 'role_revoke':
                c.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:id'), {'id':actor.user_id})
            elif change == 'password_reset':
                c.execute(text('SELECT * FROM cafeteria.reset_local_password_v19(:admin,:admin_version,:target,:version,:hash)'),
                          {'admin':admin.user_id,'admin_version':admin.authz_version,'target':actor_public_id,
                           'version':actor.authz_version,'hash':generate_password_hash('Neue-Isolierte-Testpassphrase-0907')}).one()
            else:
                c.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Publisher'"))
            future = pool.submit(worker,engine,UPDATE_FOOD,params,started,state)
            blocked(owner,started,state,blocker)
        assert future.result(10) == ('P1902' if change == 'role_definition' else 'P1903')
    assert audit_count(owner) == count
    with owner.connect() as c:
        assert c.execute(text('SELECT name,row_version FROM cafeteria.foods WHERE public_id=CAST(:id AS uuid)'),
                         {'id':food.public_id}).one() == ('Karotte',food.row_version)


def test_simultaneous_food_edits_keep_original_cas(master):  # noqa: F811
    owner, engine, actor = master
    food = store.create_food(engine,actor,payload())
    first = arguments(owner,actor,food,payload('Erste Fassung'))
    second = arguments(owner,actor,food,payload('Zweite Fassung'))
    count = audit_count(owner)
    started, state = threading.Event(), {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as c:
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            assert c.execute(text(UPDATE_FOOD),first).scalar_one()['row_version'] == food.row_version+1
            future = pool.submit(worker,engine,UPDATE_FOOD,second,started,state)
            blocked(owner,started,state,blocker)
        assert future.result(10) == '55000'
    assert store.get_food(engine,food.public_id).name == 'Erste Fassung'
    assert audit_count(owner) == count+1


@pytest.mark.parametrize('archive_first', [True,False])
def test_storage_archive_and_assignment_serialize_without_dangling_active_state(master, archive_first):  # noqa: F811
    owner, engine, actor = master
    food = store.create_food(engine,actor,payload())
    storage = store.create_vocabulary(engine,'storage_location',actor,code='STORE',name='Lager')
    assign = arguments(owner,actor,food,{'storage_locations':[storage.public_id]})
    archive = arguments(owner,actor,storage,{'active':False})
    first_sql, first_args, second_sql, second_args = (ARCHIVE,archive,ASSIGN,assign) if archive_first else (ASSIGN,assign,ARCHIVE,archive)
    count = audit_count(owner)
    started, state = threading.Event(), {}
    with ThreadPoolExecutor(max_workers=1) as pool:
        with engine.begin() as c:
            blocker = c.execute(text('SELECT pg_backend_pid()')).scalar_one()
            c.execute(text(first_sql),first_args).scalar_one()
            future = pool.submit(worker,engine,second_sql,second_args,started,state)
            blocked(owner,started,state,blocker)
        assert future.result(10) == ('P1901' if archive_first else '55000')
    read = store.get_food(engine,food.public_id)
    assert [item.public_id for item in read.storage_locations] == ([STORAGE_PUBLIC_ID] if archive_first else [storage.public_id])
    assert store.get_vocabulary(engine,'storage_location',storage.public_id).active is not archive_first
    assert audit_count(owner) == count+1
