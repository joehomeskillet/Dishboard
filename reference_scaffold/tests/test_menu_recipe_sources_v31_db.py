"""Runtime-role locks for original recipe sources, including unrevisioned heads."""
# ruff: noqa: F401, F811
from concurrent.futures import ThreadPoolExecutor
from queue import Queue
import time
from uuid import uuid4

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from test_recipe_menu_binding_db import binding, app_engine, seeded_pg16, installed_pg16, pg16
from test_rec_import_commit_migration_db import rows_and_sequences

LOCK = text("""SELECT * FROM cafeteria.lock_menu_recipe_sources_v31(
    :actor,:authz,:location,CAST(:revisions AS bigint[]),CAST(:source AS uuid))""")


@pytest.fixture
def sources(binding):
    owner, engine, ids = binding
    with owner.begin() as c:
        for key in ('source', 'high'):
            row = c.execute(text("""INSERT INTO cafeteria.recipes(
                location_id,created_by,updated_by,title,servings,servings_unit_id,source_kind)
                VALUES(:location,:actor,:actor,'Quelle',4,(SELECT id FROM cafeteria.measurement_units
                WHERE code='PORTION'),'manual') RETURNING id,public_id"""), ids).one()
            ids[key + '_recipe'], ids[key] = row[0], str(row[1])
        ids['high_revision'] = c.execute(text("""INSERT INTO cafeteria.recipe_revisions(
            location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
            VALUES(:location,:high_recipe,1,'{}',encode(pg_catalog.sha256(convert_to('{}','UTF8')),'hex'),:actor)
            RETURNING id"""), ids).scalar_one()
        ids['low'] = str(c.execute(text(
            'SELECT public_id FROM cafeteria.recipes WHERE id=:location_recipe'), ids).scalar_one())
        ids['foreign'] = str(c.execute(text(
            'SELECT public_id FROM cafeteria.recipes WHERE id=:other_location_recipe'), ids).scalar_one())
    return owner, engine, ids


def call(c, ids, revisions=None, **overrides):
    return c.execute(LOCK, {**ids, 'revisions': [] if revisions is None else revisions, **overrides}).all()


def wait_blocked(owner, pid):
    deadline = time.monotonic() + 3
    while time.monotonic() < deadline:
        with owner.connect() as c:
            if c.execute(text('SELECT cardinality(pg_blocking_pids(:pid))>0'), {'pid': pid}).scalar_one():
                return
        time.sleep(0.01)
    pytest.fail('Expected PostgreSQL lock wait did not occur')


@pytest.mark.parametrize('archived', [False, True])
def test_app_locks_unrevisioned_source_without_writes_or_audits(sources, archived):
    owner, engine, ids = sources
    if archived:
        with owner.begin() as c:
            c.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:source_recipe'), ids)
    before = rows_and_sequences(owner)
    with engine.begin() as c:
        assert c.execute(text('SELECT current_user')).scalar_one() == 'cafeteria_app'
        assert call(c, ids) == []
    assert rows_and_sequences(owner) == before


@pytest.mark.parametrize('mutation', ["active=false", "title='Concurrent update'"])
def test_source_lock_blocks_archive_and_update_until_transaction_end(sources, mutation):
    owner, engine, ids = sources
    statement = text(f'UPDATE cafeteria.recipes SET {mutation} WHERE id=:source_recipe')
    with engine.begin() as c:
        assert call(c, ids) == []
        with pytest.raises(DBAPIError) as error:
            with owner.begin() as writer:
                writer.execute(text("SET LOCAL lock_timeout='200ms'"))
                writer.execute(statement, ids)
        assert error.value.orig.sqlstate == '55P03'
    with owner.begin() as writer:
        assert writer.execute(statement, ids).rowcount == 1


@pytest.mark.parametrize('source', ['low', 'source', 'high'])
def test_revision_and_source_union_locks_in_numeric_order(sources, source):
    owner, engine, ids = sources
    pid = Queue()
    revisions = [ids['high_revision'], ids['location_revision']]

    def read():
        with engine.begin() as c:
            pid.put(c.execute(text('SELECT pg_backend_pid()')).scalar_one())
            return call(c, ids, revisions, source=ids[source])

    blocker = owner.connect()
    tx = blocker.begin()
    blocker.execute(text('SELECT id FROM cafeteria.recipes WHERE id=:high_recipe FOR UPDATE'), ids)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(read)
            try:
                wait_blocked(owner, pid.get(timeout=3))
                # A high-head wait must already hold the lower revision head.
                with pytest.raises(DBAPIError) as error:
                    with owner.begin() as c:
                        c.execute(text('SELECT id FROM cafeteria.recipes '
                            'WHERE id=:location_recipe FOR UPDATE NOWAIT'), ids)
                assert error.value.orig.sqlstate == '55P03'
                if source == 'source':
                    with pytest.raises(DBAPIError) as error:
                        with owner.begin() as c:
                            c.execute(text('SELECT id FROM cafeteria.recipes '
                                'WHERE id=:source_recipe FOR UPDATE NOWAIT'), ids)
                    assert error.value.orig.sqlstate == '55P03'
                else:
                    with owner.begin() as c:
                        c.execute(text('SELECT id FROM cafeteria.recipes '
                            'WHERE id=:source_recipe FOR UPDATE NOWAIT'), ids)
            finally:
                tx.rollback()
            rows = result.result(timeout=5)
            assert [row.revision_id for row in rows] == sorted(revisions)
            assert [row.recipe_id for row in rows] == [ids['location_recipe'], ids['high_recipe']]
    finally:
        tx.close()
        blocker.close()


def test_source_identity_is_reproved_after_waiting_for_lock(sources):
    owner, engine, ids = sources
    pid = Queue()

    def read():
        with pytest.raises(DBAPIError) as error:
            with engine.begin() as c:
                pid.put(c.execute(text('SELECT pg_backend_pid()')).scalar_one())
                call(c, ids)
        return error.value.orig.sqlstate

    blocker = owner.connect()
    tx = blocker.begin()
    blocker.execute(text('SELECT id FROM cafeteria.recipes WHERE id=:source_recipe FOR UPDATE'), ids)
    try:
        with ThreadPoolExecutor(max_workers=1) as pool:
            result = pool.submit(read)
            try:
                wait_blocked(owner, pid.get(timeout=3))
                blocker.execute(text('UPDATE cafeteria.recipes SET public_id=:new WHERE id=:source_recipe'),
                                {**ids, 'new': uuid4()})
                tx.commit()
            finally:
                if tx.is_active:
                    tx.rollback()
            assert result.result(timeout=5) == '55000'
    finally:
        blocker.close()


@pytest.mark.parametrize('source', ['null', 'missing', 'foreign'])
def test_invalid_original_source_fails_closed_without_mutation(sources, source):
    owner, engine, ids = sources
    value = {'null': None, 'missing': str(uuid4()), 'foreign': ids['foreign']}[source]
    before = rows_and_sequences(owner)
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as c:
            call(c, ids, source=value)
    assert error.value.orig.sqlstate == 'P1901'
    assert rows_and_sequences(owner) == before


def test_deleted_original_source_fails_closed(sources):
    owner, engine, ids = sources
    # Owner-only adversarial fixture: supported recipe writers prohibit deletion.
    # Restore the protection in the same transaction before exercising the app role.
    with owner.begin() as c:
        c.execute(text('ALTER TABLE cafeteria.recipes DISABLE TRIGGER recipes_protect'))
        c.execute(text('DELETE FROM cafeteria.recipes WHERE id=:source_recipe'), ids)
        c.execute(text('ALTER TABLE cafeteria.recipes ENABLE TRIGGER recipes_protect'))
    before = rows_and_sequences(owner)
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as c:
            call(c, ids)
    assert error.value.orig.sqlstate == 'P1901'
    assert rows_and_sequences(owner) == before


@pytest.mark.parametrize('kind', ['null', 'null_element', 'zero', 'negative', 'duplicate',
                                  'multidimensional', 'too_many', 'foreign', 'missing'])
def test_v26_revision_validation_remains_fail_closed(sources, kind):
    owner, engine, ids = sources
    valid = ids['location_revision']
    values = {'null': None, 'null_element': [None], 'zero': [0], 'negative': [-1],
              'duplicate': [valid, valid], 'multidimensional': [[valid]],
              'too_many': list(range(1, 32769)), 'foreign': [ids['other_location_revision']],
              'missing': [9223372036854775807]}
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as c:
            c.execute(LOCK, {**ids, 'revisions': values[kind]})
    assert error.value.orig.sqlstate == 'P1901'


@pytest.mark.parametrize('change,state', [('missing', 'P1901'), ('stale', 'P1903'),
    ('disabled', 'P1902'), ('role', 'P1902'), ('definition', 'P1902')])
def test_original_guard_precedes_all_source_and_revision_reads(sources, change, state):
    owner, engine, ids = sources
    params = dict(ids)
    with owner.begin() as c:
        if change == 'missing':
            params['actor'] = None
        elif change == 'stale':
            params['authz'] -= 1
        elif change == 'disabled':
            c.execute(text('UPDATE cafeteria.users SET disabled_at=now() WHERE id=:actor'), ids)
        elif change == 'role':
            c.execute(text('DELETE FROM cafeteria.user_role_cache WHERE user_id=:actor'), ids)
            params['authz'] = c.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:actor'), ids).scalar_one()
        else:
            c.execute(text("UPDATE cafeteria.application_roles SET active=false WHERE role_code='Cafeteria.Publisher'"))
    before = rows_and_sequences(owner)
    # Invalid business inputs cannot mask the original actor failure.
    with pytest.raises(DBAPIError) as error:
        with engine.begin() as c:
            call(c, params, [0], source=None)
    assert error.value.orig.sqlstate == state
    assert rows_and_sequences(owner) == before


def test_v26_return_contract_and_multiple_revisions_share_one_head(sources):
    owner, engine, ids = sources
    with owner.begin() as c:
        extra = c.execute(text("""INSERT INTO cafeteria.recipe_revisions(
            location_id,recipe_id,revision_number,snapshot_json,content_hash_sha256,created_by)
            VALUES(:location,:location_recipe,2,'{}',encode(pg_catalog.sha256(convert_to('{}','UTF8')),'hex'),:actor)
            RETURNING id"""), ids).scalar_one()
        c.execute(text('UPDATE cafeteria.recipes SET active=false WHERE id=:location_recipe'), ids)
    revisions = [extra, ids['high_revision'], ids['location_revision']]
    with engine.begin() as c:
        expected = c.execute(text('SELECT * FROM cafeteria.lock_menu_recipe_revisions_v26('
            ':actor,:authz,:location,CAST(:revisions AS bigint[]))'), {**ids, 'revisions': revisions}).all()
        assert call(c, ids, revisions, source=ids['low']) == expected
        assert len(expected) == 3 and expected[0].active is False
        assert c.execute(text('SELECT * FROM cafeteria.lock_menu_recipe_revisions_v26('
            ':actor,:authz,:location,ARRAY[]::bigint[])'), ids).all() == []
