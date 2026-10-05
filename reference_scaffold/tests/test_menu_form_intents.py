"""Native menu form intents: rearrangement, real search/paging, and closed failures.

Every case posts to the existing authenticated, CSRF-protected menu endpoint. A form
intent must answer from the submitted values alone: no menu, recipe, audit or sequence
write may happen before a deliberate save, the originally submitted row version has to
survive so a concurrent change still conflicts, and an unknown, duplicated or malformed
intent must be rejected before any write.
"""
from __future__ import annotations

import re

import pytest
from flask import Flask
from sqlalchemy import Engine, text
from werkzeug.datastructures import MultiDict

from test_admin_workflow_routes import DAY, _hidden, _login, _menu_form
from test_menu_recipe_choices_reader import (
    active_location, admin_app, admin_engine, create_recipe, freeze_revision)  # noqa: F401

from cafeteria.menu_recipe_choices import CHOICE_PAGE_LIMIT

MENU_URL = '/admin/patienten/menu'
EDITOR = f'{MENU_URL}?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
# One static statement per relation; PostgreSQL quotes the identifier itself.
_TABLE_COUNTS = '''SELECT c.relname AS relation,
    (xpath('/row/c/text()', query_to_xml(
        format('SELECT count(*) AS c FROM cafeteria.%I', c.relname), false, true, ''))
    )[1]::text::bigint AS total
    FROM pg_class c JOIN pg_namespace n ON n.oid=c.relnamespace
    WHERE n.nspname='cafeteria' AND c.relkind='r'
    AND has_table_privilege(c.oid,'SELECT') '''
_SEQUENCES = "SELECT sequencename, last_value FROM pg_sequences WHERE schemaname='cafeteria'"


def _state(engine: Engine) -> dict[str, int]:
    """Every row count and sequence position of the application schema."""
    with engine.connect() as connection:
        counts = connection.execute(text(_TABLE_COUNTS)).all()
        sequences = connection.execute(text(_SEQUENCES)).all()
    assert counts, 'Schema-Momentaufnahme ist leer.'
    state = {f'table:{row.relation}': int(row.total or 0) for row in counts}
    state.update({
        f'sequence:{row.sequencename}': int(row.last_value or 0) for row in sequences
    })
    return state


def _rows(html: str, name: str) -> list[str]:
    """Values of one repeated text input in document order."""
    return re.findall(rf'<input[^>]*name="{name}"[^>]*value="([^"]*)"', html)


def _selected(html: str) -> list[str]:
    return [
        match.group(1)
        for block in re.findall(r'<select[^>]*name="recipe_revision_public_id".*?</select>', html, re.S)
        for match in [re.search(r'<option value="([^"]*)"[^>]*selected', block)]
        if match is not None
    ]


def _assignments(engine: Engine) -> list[tuple[int, str, str | None, str | None]]:
    with engine.connect() as connection:
        return [
            (int(row.sort_order), str(row.component_text or ''), row.revision, row.hash)
            for row in connection.execute(text(
                '''SELECT c.sort_order, c.component_text, rr.public_id::text AS revision,
                          rr.content_hash_sha256 AS hash
                   FROM cafeteria.menu_item_components c
                   LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
                   ORDER BY c.menu_item_id, c.sort_order'''))
        ]


@pytest.fixture
def client(admin_app: Flask, admin_engine: Engine):  # noqa: F811
    session_client, actor_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    return session_client, actor_id, admin_engine


def _token(session_client, family: str = 'patienten') -> str:
    response = session_client.get(f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1')
    assert response.status_code == 200
    return _hidden(response.get_data(as_text=True), '_csrf', form_action=f'/admin/{family}/menu')


def _revision(engine: Engine, actor_id: int, title: str, *, servings: str = '4') -> dict[str, str]:
    recipe_id = create_recipe(engine, actor_id, title, servings=servings)
    frozen = freeze_revision(engine, actor_id, recipe_id)
    return {'public_id': frozen['public_id'], 'hash': frozen['hash'], 'title': title}


def _two_row_form(token: str, first: str, second: str, **changes: str) -> MultiDict[str, str]:
    data = MultiDict(_menu_form(_csrf=token, title='Zwei Zeilen', allergen_mode='auto',
                                origin_mode='auto', label_mode='auto', **changes))
    data.setlist('component_public_id', ['', ''])
    data.setlist('component_text', ['Erste Zeile', 'Zweite Zeile'])
    data.setlist('recipe_revision_public_id', [first, second])
    data.setlist('target_quantity', ['2.5', '7'])
    data.setlist('target_quantity_unit_code', ['PORTION', 'PORTION'])
    return data


def test_add_move_and_remove_rearrange_without_any_write(client) -> None:
    session_client, actor_id, engine = client
    first = _revision(engine, actor_id, 'Erste Bindung')
    second = _revision(engine, actor_id, 'Zweite Bindung')
    token = _token(session_client)
    before = _state(engine)

    added = session_client.post(MENU_URL, data=_two_row_form(
        token, first['public_id'], second['public_id'], form_intent='component_add'))
    assert added.status_code == 200 and added.headers['Cache-Control'] == 'no-store'
    html = added.get_data(as_text=True)
    assert _rows(html, 'component_text') == ['Erste Zeile', 'Zweite Zeile', '']
    assert _rows(html, 'target_quantity') == ['2.5', '7', '']
    assert _selected(html) == [first['public_id'], second['public_id']]
    assert re.search(r'id="component-2-id"[^>]*autofocus', html) is not None
    assert _hidden(html, 'row_version', form_action=MENU_URL) == '0'

    reversed_rows = session_client.post(MENU_URL, data=_two_row_form(
        token, first['public_id'], second['public_id'], form_intent='component_move_up:1'))
    assert reversed_rows.status_code == 200
    reversed_html = reversed_rows.get_data(as_text=True)
    assert _rows(reversed_html, 'component_text') == ['Zweite Zeile', 'Erste Zeile']
    assert _rows(reversed_html, 'target_quantity') == ['7', '2.5']
    assert _rows(reversed_html, 'target_quantity_unit_code') == ['PORTION', 'PORTION']
    assert _selected(reversed_html) == [second['public_id'], first['public_id']]

    removed = session_client.post(MENU_URL, data=_two_row_form(
        token, first['public_id'], second['public_id'], form_intent='component_remove:0'))
    assert removed.status_code == 200
    removed_html = removed.get_data(as_text=True)
    assert _rows(removed_html, 'component_text') == ['Zweite Zeile']
    assert _rows(removed_html, 'target_quantity') == ['7']
    assert _selected(removed_html) == [second['public_id']]

    assert _state(engine) == before
    assert _assignments(engine) == []


def test_search_omitting_whole_row_group_retains_saved_bindings(client):
    session_client, actor, engine = client
    first, second = _revision(engine, actor, 'Ganz A'), _revision(engine, actor, 'Ganz B')
    token = _token(session_client)
    assert session_client.post(MENU_URL, data=_two_row_form(token, first['public_id'], second['public_id'])).status_code == 303
    before = _state(engine)
    data = _menu_form(_csrf=token, row_version='1', form_intent='recipe_search',
        recipe_search='Ganz', allergen_mode='auto', origin_mode='auto', label_mode='auto')
    response = session_client.post(MENU_URL, data=data)
    assert response.status_code == 200
    assert _selected(response.text) == [first['public_id'], second['public_id']]
    assert _rows(response.text, 'target_quantity') == ['2.500000', '7.000000']
    assert _state(engine) == before


def test_last_row_is_cleared_and_unsaved_fields_survive_every_intent(client) -> None:
    session_client, actor_id, engine = client
    bound = _revision(engine, actor_id, 'Einzige Bindung')
    token = _token(session_client)
    before = _state(engine)
    data = MultiDict(_menu_form(
        _csrf=token, title='Unveränderter Titel', description='Beschreibung bleibt',
        note='Hinweis bleibt', allergen_mode='auto', origin_mode='auto', label_mode='auto',
        recipe_search='Einzige', recipe_offset='0', form_intent='component_remove:0',
    ))
    data.setlist('component_public_id', [''])
    data.setlist('component_text', ['Wird geleert'])
    data.setlist('recipe_revision_public_id', [bound['public_id']])
    data.setlist('target_quantity', [''] * len(data.getlist('component_public_id')))
    data.setlist('target_quantity_unit_code', [''] * len(data.getlist('component_public_id')))
    response = session_client.post(MENU_URL, data=data)
    assert response.status_code == 200
    html = response.get_data(as_text=True)
    assert _rows(html, 'component_text') == ['']
    assert 'Unveränderter Titel' in html and 'Beschreibung bleibt' in html
    assert 'Hinweis bleibt' in html
    assert re.search(r'name="recipe_search"[^>]*value="Einzige"', html) is not None
    assert _selected(html) == []
    assert _state(engine) == before


def test_search_and_paging_read_the_whole_eligible_set(client) -> None:
    session_client, actor_id, engine = client
    location_id = active_location(engine)
    with engine.begin() as connection:
        ids = [int(row.id) for row in connection.execute(text(
            '''INSERT INTO cafeteria.recipes(location_id,created_by,updated_by,title,servings,
               servings_unit_id,source_kind,active)
               SELECT :location,:actor,:actor,'Serienrezept '||to_char(n,'FM000'),4,u.id,'manual',true
               FROM generate_series(1,201) n,cafeteria.measurement_units u
               WHERE u.code='PORTION' RETURNING id'''),
            {'location': location_id, 'actor': actor_id})]
        connection.execute(text(
            '''INSERT INTO cafeteria.recipe_revisions(location_id,recipe_id,revision_number,
               snapshot_json,content_hash_sha256,created_by)
               SELECT r.location_id,r.id,1,cafeteria.recipe_snapshot_v22(r.id),
                encode(public.digest(convert_to(cafeteria.recipe_snapshot_v22(r.id)::text,'UTF8'),'sha256'),'hex'),
                :actor
               FROM cafeteria.recipes r WHERE r.id=ANY(:ids)'''),
            {'actor': actor_id, 'ids': ids})
    assert len(ids) == 201
    token = _token(session_client)
    before = _state(engine)

    first_page = session_client.get(EDITOR).get_data(as_text=True)
    assert 'Serienrezept 201' not in first_page

    data = MultiDict(_menu_form(_csrf=token, title='Suche', allergen_mode='auto',
                                origin_mode='auto', label_mode='auto',
                                recipe_search='Serienrezept 201', form_intent='recipe_search'))
    searched = session_client.post(MENU_URL, data=data)
    assert searched.status_code == 200
    searched_html = searched.get_data(as_text=True)
    assert 'Serienrezept 201' in searched_html
    assert _hidden(searched_html, 'recipe_offset', form_action=MENU_URL) == '0'

    paged = MultiDict(_menu_form(_csrf=token, title='Seite', allergen_mode='auto',
                                 origin_mode='auto', label_mode='auto',
                                 recipe_search='Serienrezept', recipe_offset='150',
                                 form_intent='recipe_page_next'))
    next_page = session_client.post(MENU_URL, data=paged)
    assert next_page.status_code == 200
    next_html = next_page.get_data(as_text=True)
    assert _hidden(next_html, 'recipe_offset', form_action=MENU_URL) == str(150 + CHOICE_PAGE_LIMIT)
    assert 'Serienrezept 201' in next_html
    assert _state(engine) == before


def test_unknown_duplicate_and_malformed_intents_fail_closed(client) -> None:
    session_client, actor_id, engine = client
    bound = _revision(engine, actor_id, 'Geschützte Bindung')
    token = _token(session_client)
    before = _state(engine)

    def _post(**changes: str) -> tuple[int, str]:
        data = MultiDict(_menu_form(_csrf=token, title='Fehlerhaft', allergen_mode='auto',
                                    origin_mode='auto', label_mode='auto', **changes))
        data.setlist('component_public_id', [''])
        data.setlist('component_text', ['Zeile'])
        data.setlist('recipe_revision_public_id', [bound['public_id']])
        data.setlist('target_quantity', [''] * len(data.getlist('component_public_id')))
        data.setlist('target_quantity_unit_code', [''] * len(data.getlist('component_public_id')))
        response = session_client.post(MENU_URL, data=data)
        return response.status_code, response.get_data(as_text=True)

    for intent in ('component_drop:0', 'component_add:0', 'component_remove',
                   'component_remove:1', 'save', 'recipe_search:0', 'COMPONENT_ADD',
                   'component_remove:-1', 'component_move_up:9999'):
        status, _ = _post(form_intent=intent)
        assert status == 400, intent

    for view in ({'recipe_offset': 'x'}, {'recipe_offset': '-1'}, {'recipe_offset': '1000000'},
                 {'recipe_search': 'x' * 201}, {'recipe_search': 'stop\x00'}):
        status, _ = _post(form_intent='component_add', **view)
        assert status == 400, view

    duplicate = MultiDict(_menu_form(_csrf=token, title='Doppelt', allergen_mode='auto',
                                     origin_mode='auto', label_mode='auto'))
    duplicate.setlist('component_public_id', [''])
    duplicate.setlist('component_text', ['Zeile'])
    duplicate.setlist('form_intent', ['component_add', 'component_remove:0'])
    assert session_client.post(MENU_URL, data=duplicate).status_code == 400

    unaligned = MultiDict(_menu_form(_csrf=token, title='Schief', allergen_mode='auto',
                                     origin_mode='auto', label_mode='auto',
                                     form_intent='component_move_up:1'))
    unaligned.setlist('component_public_id', ['', ''])
    unaligned.setlist('component_text', ['Nur eine'])
    unaligned.setlist('recipe_revision_public_id', [bound['public_id'], ''])
    unaligned.setlist('target_quantity', [''] * len(unaligned.getlist('component_public_id')))
    unaligned.setlist('target_quantity_unit_code', [''] * len(unaligned.getlist('component_public_id')))
    assert session_client.post(MENU_URL, data=unaligned).status_code == 400

    assert _state(engine) == before


def test_intents_need_the_existing_csrf_and_write_authorisation(
    client, admin_app: Flask, admin_engine: Engine,  # noqa: F811
) -> None:
    session_client, actor_id, engine = client
    token = _token(session_client)
    before = _state(engine)
    forged = MultiDict(_menu_form(_csrf='forged-token', title='Ohne CSRF', allergen_mode='auto',
                                  origin_mode='auto', label_mode='auto',
                                  form_intent='component_add'))
    assert session_client.post(MENU_URL, data=forged).status_code in {400, 403}

    anonymous = admin_app.test_client().post(MENU_URL, data=MultiDict(_menu_form(
        _csrf=token, title='Anonym', allergen_mode='auto', origin_mode='auto',
        label_mode='auto', form_intent='component_add')))
    assert anonymous.status_code in {400, 401, 403}
    assert _state(engine) == before

    # Last: this login strips the shared actor's roles, so every later request of this
    # test is roleless. Signing in also writes user, role cache and audit bookkeeping,
    # which is why the no-write comparison above closes before it.
    roleless, _ = _login(admin_app, admin_engine, [])
    denied = roleless.post(MENU_URL, data=MultiDict(_menu_form(
        _csrf=token, title='Ohne Rolle', allergen_mode='auto', origin_mode='auto',
        label_mode='auto', form_intent='component_add')))
    assert denied.status_code in {401, 403}
    assert _assignments(engine) == []


def test_form_intents_keep_the_conflicting_version_across_two_submits(client, monkeypatch) -> None:
    session_client, actor_id, engine = client
    bound = _revision(engine, actor_id, 'Konfliktbindung')
    token = _token(session_client)
    created = MultiDict(_menu_form(_csrf=token, title='Erstfassung', allergen_mode='auto',
                                   origin_mode='auto', label_mode='auto'))
    created.setlist('component_public_id', [''])
    created.setlist('component_text', ['Erste Zeile'])
    created.setlist('recipe_revision_public_id', [bound['public_id']])
    created.setlist('target_quantity', [''] * len(created.getlist('component_public_id')))
    created.setlist('target_quantity_unit_code', [''] * len(created.getlist('component_public_id')))
    assert session_client.post(MENU_URL, data=created).status_code == 303

    concurrent = MultiDict(_menu_form(_csrf=token, title='Fremde Änderung', row_version='1',
                                      allergen_mode='auto', origin_mode='auto', label_mode='auto'))
    concurrent.setlist('component_public_id', [''])
    concurrent.setlist('component_text', ['Fremde Zeile'])
    concurrent.setlist('recipe_revision_public_id', [bound['public_id']])
    concurrent.setlist('target_quantity', [''] * len(concurrent.getlist('component_public_id')))
    concurrent.setlist('target_quantity_unit_code', [''] * len(concurrent.getlist('component_public_id')))
    assert session_client.post(MENU_URL, data=concurrent).status_code == 303
    after_concurrent = _state(engine)

    stale = MultiDict(_menu_form(_csrf=token, title='Eigene Fassung', row_version='1',
                                 allergen_mode='auto', origin_mode='auto', label_mode='auto',
                                 form_intent='component_add'))
    stale.setlist('component_public_id', [''])
    stale.setlist('component_text', ['Eigene Zeile'])
    stale.setlist('recipe_revision_public_id', [bound['public_id']])
    stale.setlist('target_quantity', [''] * len(stale.getlist('component_public_id')))
    stale.setlist('target_quantity_unit_code', [''] * len(stale.getlist('component_public_id')))
    stale['recipe_search'], stale['recipe_offset'] = 'Konfliktbindung', '50'
    intent = session_client.post(MENU_URL, data=stale)
    assert intent.status_code == 200
    intent_html = intent.get_data(as_text=True)
    assert _hidden(intent_html, 'row_version', form_action=MENU_URL) == '1'
    assert _state(engine) == after_concurrent

    saved = MultiDict(stale)
    saved.poplist('form_intent')
    from test_menu_template_binding_routes import forbid_redisplay_reads
    forbid_redisplay_reads(monkeypatch)
    conflict = session_client.post(MENU_URL, data=saved)
    assert conflict.status_code == 409
    conflict_html = conflict.get_data(as_text=True)
    assert _hidden(conflict_html, 'row_version', form_action=MENU_URL) == '1'
    assert _hidden(conflict_html, 'recipe_offset', form_action=MENU_URL) == '50'
    assert re.search(r'name="recipe_search"[^>]*value="Konfliktbindung"', conflict_html)

    again = session_client.post(MENU_URL, data=saved)
    assert again.status_code == 409
    assert _hidden(again.get_data(as_text=True), 'row_version', form_action=MENU_URL) == '1'
    assert _state(engine) == after_concurrent


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
def test_save_ignores_view_fields_and_still_rejects_unknown_fields(client, family: str) -> None:
    session_client, actor_id, engine = client
    bound = _revision(engine, actor_id, f'Speicherbindung {family}')
    token = _token(session_client, family)
    url = f'/admin/{family}/menu'
    prices = {'internal_chf': '9.50', 'external_chf': '12.00'} if family == 'cafeteria' else {}
    data = MultiDict(_menu_form(_csrf=token, title='Gespeichert', allergen_mode='auto',
                                origin_mode='auto', label_mode='auto',
                                recipe_search='Speicherbindung', recipe_offset='0', **prices))
    data.setlist('component_public_id', [''])
    data.setlist('component_text', ['Gespeicherte Zeile'])
    data.setlist('recipe_revision_public_id', [bound['public_id']])
    data.setlist('target_quantity', [''] * len(data.getlist('component_public_id')))
    data.setlist('target_quantity_unit_code', [''] * len(data.getlist('component_public_id')))
    assert session_client.post(url, data=data).status_code == 303
    stored = [row for row in _assignments(engine) if row[2] == bound['public_id']]
    assert stored and stored[0][3] == bound['hash']

    unknown = MultiDict(data)
    unknown['row_version'] = '1'
    unknown['bastelfeld'] = 'x'
    rejected = session_client.post(url, data=unknown)
    assert rejected.status_code == 400
    assert 'Unzulässiges Formularfeld' in rejected.get_data(as_text=True)


def _posted_selects(html: str, name: str) -> list[str]:
    """Current value of every named select, empty when the browser would send the first option."""
    posted = []
    for block in re.findall(rf'<select[^>]*name="{name}".*?</select>', html, re.S):
        match = re.search(r'<option value="([^"]*)"[^>]*selected', block)
        posted.append(match.group(1) if match is not None else '')
    return posted


def _posted_texts(html: str, name: str) -> list[str]:
    return re.findall(rf'<input[^>]*name="{name}"[^>]*value="([^"]*)"', html)


def _save_payload_from_editor(html: str, url: str, family: str) -> MultiDict[str, str]:
    """Rebuild a deliberate Save from the editor HTML a form-only response actually returned."""
    title = re.search(r'id="f-title"[^>]*value="([^"]*)"', html)
    assert title is not None
    data = MultiDict([
        ('_csrf', _hidden(html, '_csrf', form_action=url)),
        ('week', DAY),
        ('day', DAY),
        ('meal', 'LUNCH'),
        ('option', 'MENU_1'),
        ('row_version', _hidden(html, 'row_version', form_action=url)),
        ('title', title.group(1)),
        ('allergen_mode', 'auto'),
        ('origin_mode', 'auto'),
        ('label_mode', 'auto'),
    ])
    data.setlist('component_public_id', _posted_selects(html, 'component_public_id'))
    data.setlist('component_text', _posted_texts(html, 'component_text'))
    data.setlist('recipe_revision_public_id', _posted_selects(html, 'recipe_revision_public_id'))
    data.setlist('target_quantity', _posted_texts(html, 'target_quantity'))
    data.setlist('target_quantity_unit_code', _posted_texts(html, 'target_quantity_unit_code'))
    if family == 'cafeteria':
        internal = re.search(r'id="f-int"[^>]*value="([^"]*)"', html)
        external = re.search(r'id="f-ext"[^>]*value="([^"]*)"', html)
        assert internal is not None and external is not None
        data['internal_chf'] = internal.group(1)
        data['external_chf'] = external.group(1)
    return data


@pytest.mark.parametrize('family', ('cafeteria', 'patienten'))
@pytest.mark.parametrize('intent,recipe_mode', (
    ('recipe_search', 'missing'),
    ('recipe_page_next', 'missing'),
    ('component_remove:0', 'missing'),
    ('component_move_up:1', 'missing'),
    ('recipe_search', 'shifted'),
    ('component_remove:0', 'shifted'),
))
def test_form_only_intents_do_not_turn_omitted_recipe_arrays_into_a_detach(
    client, family: str, intent: str, recipe_mode: str,
) -> None:
    """Row and search/page intents must not render an editable empty detach.

    The unfixed form-only path skipped complete-shape validation, padded missing
    recipe selects to empty, and a later Save then cleared stored bindings. A 400
    that still returns those empty selects is the same two-step detach. Direct
    legacy Save without the recipe array must remain 409.
    """
    session_client, actor_id, engine = client
    first = _revision(engine, actor_id, f'Erste {family} {intent} {recipe_mode}')
    second = _revision(engine, actor_id, f'Zweite {family} {intent} {recipe_mode}')
    token = _token(session_client, family)
    url = f'/admin/{family}/menu'
    prices = {'internal_chf': '9.50', 'external_chf': '12.00'} if family == 'cafeteria' else {}
    created = MultiDict(_menu_form(_csrf=token, title='Gebundene Fassung', allergen_mode='auto',
                                   origin_mode='auto', label_mode='auto', **prices))
    created.setlist('component_public_id', ['', ''])
    created.setlist('component_text', ['Erste Zeile', 'Zweite Zeile'])
    created.setlist('recipe_revision_public_id', [first['public_id'], second['public_id']])
    created.setlist('target_quantity', [''] * len(created.getlist('component_public_id')))
    created.setlist('target_quantity_unit_code', [''] * len(created.getlist('component_public_id')))
    assert session_client.post(url, data=created).status_code == 303
    bound = [
        (row[1], row[2], row[3])
        for row in _assignments(engine)
        if row[2] in {first['public_id'], second['public_id']}
    ]
    assert bound == [
        ('Erste Zeile', first['public_id'], first['hash']),
        ('Zweite Zeile', second['public_id'], second['hash']),
    ]
    before = _state(engine)

    intent_form = MultiDict(_menu_form(_csrf=token, title='Gebundene Fassung', row_version='1',
                                       allergen_mode='auto', origin_mode='auto', label_mode='auto',
                                       form_intent=intent, **prices))
    intent_form.setlist('component_public_id', ['', ''])
    intent_form.setlist('component_text', ['Erste Zeile', 'Zweite Zeile'])
    if recipe_mode == 'shifted':
        intent_form.setlist('recipe_revision_public_id', [first['public_id']])
        intent_form.setlist('target_quantity', [''] * len(intent_form.getlist('component_public_id')))
        intent_form.setlist('target_quantity_unit_code', [''] * len(intent_form.getlist('component_public_id')))
    response = session_client.post(url, data=intent_form)
    html = response.get_data(as_text=True)
    assert response.status_code == 400
    posted_recipes = _posted_selects(html, 'recipe_revision_public_id')
    assert posted_recipes != ['', '']
    assert first['public_id'] in posted_recipes
    assert second['public_id'] in posted_recipes
    stored_after_intent = [
        (row[1], row[2], row[3])
        for row in _assignments(engine)
        if row[2] in {first['public_id'], second['public_id']}
    ]
    assert stored_after_intent == bound
    assert _state(engine) == before

    legacy = MultiDict(_menu_form(_csrf=token, title='Gebundene Fassung', row_version='1',
                                  allergen_mode='auto', origin_mode='auto', label_mode='auto',
                                  **prices))
    legacy.setlist('component_public_id', ['', ''])
    legacy.setlist('component_text', ['Erste Zeile', 'Zweite Zeile'])
    refused = session_client.post(url, data=legacy)
    assert refused.status_code == 409
    assert 'Rezeptbezüge sind vorhanden' in refused.get_data(as_text=True)
    stored_after_legacy = [
        (row[1], row[2], row[3])
        for row in _assignments(engine)
        if row[2] in {first['public_id'], second['public_id']}
    ]
    assert stored_after_legacy == bound
    assert _state(engine) == before

    saved = session_client.post(url, data=_save_payload_from_editor(html, url, family))
    assert saved.status_code in {303, 409}
    stored_after_save = [
        (row[1], row[2], row[3])
        for row in _assignments(engine)
        if row[2] in {first['public_id'], second['public_id']}
    ]
    assert stored_after_save == bound


@pytest.mark.parametrize('field', ('target_quantity', 'target_quantity_unit_code'))
def test_incomplete_target_arrays_cannot_detach_stored_quantities(client, field) -> None:
    session_client, actor, engine = client
    first, second = _revision(engine, actor, 'Menge A'), _revision(engine, actor, 'Menge B')
    token = _token(session_client)
    data = _two_row_form(token, first['public_id'], second['public_id'])
    assert session_client.post(MENU_URL, data=data).status_code == 303
    data['row_version'], data['form_intent'] = '1', 'component_move_up:1'
    data.setlist(field, ['2.5'] if field == 'target_quantity' else ['PORTION'])
    before = _state(engine)
    response = session_client.post(MENU_URL, data=data)
    assert response.status_code == 400
    assert _rows(response.text, 'target_quantity') == ['2.500000', '7.000000']
    assert _selected(response.text) == [first['public_id'], second['public_id']]
    assert _state(engine) == before


def test_template_intent_preserves_signed_create_authority(client, admin_app):  # noqa: F811
    from test_menu_template_binding_db import make_template
    from test_menu_template_binding_routes import proposal, proposal_form
    session_client, actor, engine = client
    template = make_template(engine)
    _, token, url = proposal(admin_app, engine, actor, template)
    data = MultiDict(proposal_form(session_client, url, token, template))
    data['target_quantity'], data['target_quantity_unit_code'] = '', ''
    data['form_intent'], data['recipe_search'] = 'component_add', 'Vorlage'
    before = _state(engine)
    response = session_client.post(MENU_URL, data=data)
    assert response.status_code == 200
    assert _hidden(response.text, 'template_context', form_action=MENU_URL) == token
    assert _hidden(response.text, '_csrf', form_action=MENU_URL) == data['_csrf']
    assert _hidden(response.text, 'row_version', form_action=MENU_URL) == '0'
    assert 'Neues Menü aus Vorlage' in response.text and 'name="dish_template_detach"' not in response.text
    assert _rows(response.text, 'component_text') == ['Rösti', '']
    assert _state(engine) == before


@pytest.mark.parametrize('status', (400, 409))
def test_saved_effects_on_validation_errors_respect_retained_only(admin_app, monkeypatch, status):  # noqa: F811
    from unittest.mock import Mock
    from datetime import date
    from cafeteria.admin import workflow_routes as routes
    from cafeteria.menu_recipe_choices import RecipeChoicePage, RecipeChoiceQuery
    from cafeteria.component_catalog_store import AdminScope
    saved = {'labels': ['Gespeichertes Label'], 'allergens': ['Milch'], 'origins': ['CH']}
    reader = Mock(return_value=object())
    monkeypatch.setattr(routes, '_load_item', Mock(return_value=(17, 3, 'Gespeichert')))
    monkeypatch.setattr(routes, '_load_draft_option', Mock(return_value={'assignments': []}))
    monkeypatch.setattr(routes, '_catalog_choices', Mock(return_value=[]))
    monkeypatch.setattr(routes, '_master_choices', Mock(return_value=([], [])))
    monkeypatch.setattr(routes, '_recipe_choice_page', Mock(return_value=RecipeChoicePage(
        query=RecipeChoiceQuery(), choices=(), retained=(), has_next=False,
        next_offset=None, previous_offset=None)))
    monkeypatch.setattr(routes, 'resolve_component_effects', reader)
    monkeypatch.setattr(routes, '_display_effects', lambda _: saved)
    review = Mock()
    monkeypatch.setattr(routes, 'get_component_review_token', review)
    render = Mock(return_value='rendered')
    monkeypatch.setattr(routes, 'render_menu_editor', render)
    with admin_app.test_request_context(MENU_URL, method='POST', data={'_csrf': 'retained'}):
        routes._render_menu_page('patient', 'patienten', AdminScope(1, 1, 'patient', 1),
            date.fromisoformat(DAY), DAY, 'LUNCH', 'MENU_1', status=status,
            form_values={'component_public_id': [], 'recipe_revision_public_id': []},
            submitted_row_version='1')
    assert render.call_args.args[11] == (saved if status == 400 else {'labels': [], 'allergens': [], 'origins': []})
    assert reader.call_count == (1 if status == 400 else 0)
    review.assert_not_called()
    if status == 409:
        for name in ('_load_item', '_load_draft_option', '_catalog_choices', '_master_choices', '_recipe_choice_page'):
            getattr(routes, name).assert_not_called()
