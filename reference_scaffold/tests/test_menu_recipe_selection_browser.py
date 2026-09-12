"""Menu recipe-revision selector: persistence, aligned arrays, NoJS and viewports."""
from __future__ import annotations

import re
from collections.abc import Iterator
from pathlib import Path

import pytest
from flask import Flask
from playwright.sync_api import Browser, Page, expect
from sqlalchemy import Engine, text
from werkzeug.datastructures import MultiDict

from test_admin_ux_browser import (  # noqa: F401
    _submit_menu, admin_app, admin_engine, browser, live_server, page_context,
)
from test_admin_workflow_routes import DAY, _counts, _hidden, _login, _menu_form
from test_menu_recipe_choices_reader import create_recipe, freeze_revision, update_head
from test_rendered_ui import PATIENT_FORBIDDEN

EDITOR = f'/admin/patienten/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'
VIEWPORTS = ((1440, 900), (1024, 768), (768, 1024), (390, 844), (1920, 1080))


def _editor(family: str = 'patienten') -> str:
    return f'/admin/{family}/menu?week={DAY}&day={DAY}&meal=LUNCH&option=MENU_1'


def _insert_revision(engine: Engine, actor_id: int, title: str, *, revision_number: int = 1,
                     recipe_id: int | None = None, servings: str = '4',
                     location_id: int | None = None, active: bool = True) -> dict[str, str]:
    """Freeze a genuine snapshot; a further revision first moves the head it snapshots.

    The immutable label of an existing revision must survive that head change, so the
    fixture writes real differing snapshot bytes instead of one shared placeholder.
    """
    if recipe_id is None:
        recipe_id = create_recipe(engine, actor_id, title, servings=servings,
                                  location_id=location_id, active=active)
    else:
        update_head(engine, actor_id, recipe_id, title=title, servings=servings)
    frozen = freeze_revision(engine, actor_id, recipe_id)
    assert frozen['number'] == str(revision_number)
    return {
        'public_id': frozen['public_id'],
        'hash': frozen['hash'],
        'number': frozen['number'],
        'title': title,
        'recipe_id': str(recipe_id),
        'yield': f'{servings} PORTION',
    }


def _foreign_revision(engine: Engine, actor_id: int) -> dict[str, str]:
    with engine.begin() as connection:
        location_id = int(connection.execute(text(
            "INSERT INTO cafeteria.locations(code,name,active) VALUES('FREMD','Fremdes Haus',false) RETURNING id"
        )).scalar_one())
    return _insert_revision(engine, actor_id, 'Fremde Suppe', location_id=location_id)


def _token(client, family: str = 'patienten') -> str:
    response = client.get(_editor(family))
    assert response.status_code == 200
    return _hidden(response.get_data(as_text=True), '_csrf', form_action=f'/admin/{family}/menu')


def _form(token: str, revision: str, **changes: str) -> MultiDict[str, str]:
    data = MultiDict(_menu_form(
        _csrf=token, component_public_id='', component_text='Suppe',
        recipe_revision_public_id=revision, **changes,
    ))
    return data


def _assignments(engine: Engine) -> list:
    with engine.connect() as connection:
        return list(connection.execute(text(
            '''SELECT c.sort_order, c.component_text, rr.public_id::text AS revision,
                      rr.content_hash_sha256 AS hash
               FROM cafeteria.menu_item_components c
               LEFT JOIN cafeteria.recipe_revisions rr ON rr.id=c.recipe_revision_id
               ORDER BY c.menu_item_id, c.sort_order'''
        )))


def _bound(engine: Engine) -> dict[str, object] | None:
    rows = _assignments(engine)
    if not rows:
        return None
    return {'recipe_revision_public_id': rows[0].revision, 'hash': rows[0].hash}


def _ready(page: Page) -> None:
    page.wait_for_load_state()
    page.evaluate('document.fonts.ready')


def _no_overflow(page: Page) -> None:
    assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')


def _option(page: Page, revision: str):
    return page.locator(f'select[name="recipe_revision_public_id"] option[value="{revision}"]')


def _label(body: str, revision: str) -> str:
    match = re.search(rf'<option[^>]*value="{re.escape(revision)}"[^>]*>([^<]*)</option>', body)
    assert match is not None, f'Option für {revision} fehlt.'
    return match.group(1)


@pytest.fixture
def http_client(admin_app: Flask, admin_engine: Engine):  # noqa: F811
    client, actor_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    return client, actor_id, admin_engine


@pytest.fixture
def nojs_page(browser: Browser, live_server: str, admin_app: Flask, admin_engine: Engine) -> Iterator[Page]:  # noqa: F811
    client, _ = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    context = browser.new_context(base_url=live_server, java_script_enabled=False, reduced_motion='reduce')
    cookie = client.get_cookie('session')
    if cookie:
        context.add_cookies([{
            'name': 'session', 'value': cookie.value, 'domain': '127.0.0.1',
            'path': '/', 'httpOnly': True,
        }])
    page = context.new_page()
    try:
        yield page
    finally:
        context.close()


def test_http_roundtrip_hash_legacy_conflict_detach_and_foreign(http_client) -> None:
    client, actor_id, engine = http_client
    first = _insert_revision(engine, actor_id, 'Bindungssuppe')
    later = _insert_revision(engine, actor_id, 'Bindungssuppe', revision_number=2,
                             recipe_id=int(first['recipe_id']), servings='6')
    foreign = _foreign_revision(engine, actor_id)
    token = _token(client)
    saved = client.post('/admin/patienten/menu', data=_form(token, first['public_id']))
    assert saved.status_code == 303 and saved.headers['Cache-Control'] == 'no-store'
    bound = _bound(engine)
    assert bound == {'recipe_revision_public_id': first['public_id'], 'hash': first['hash']}
    page = client.get(EDITOR)
    body = page.get_data(as_text=True)
    assert page.status_code == 200
    assert f'value="{first["public_id"]}"' in body and 'selected' in body
    assert f'data-content-hash="{first["hash"]}"' in body and later['public_id'] in body
    labels = re.findall(
        rf'<option[^>]*value="{re.escape(first["public_id"])}"[^>]*>([^<]*)</option>', body,
    )
    assert labels and first['hash'] not in labels[0] and first['public_id'] not in labels[0]
    assert re.search(r'Revision 1[^<]*4 PORTION', labels[0])
    assert 'Gebundene Revision bleibt erhalten' not in body
    assert later['public_id'] in body
    assert foreign['public_id'] not in body
    assert PATIENT_FORBIDDEN.search(body) is None
    legacy = _form(token, first['public_id'], row_version='1')
    legacy.pop('recipe_revision_public_id')
    denied = client.post('/admin/patienten/menu', data=legacy)
    assert denied.status_code == 409
    assert _bound(engine) == bound
    foreign_post = client.post('/admin/patienten/menu', data=_form(token, foreign['public_id'], row_version='1'))
    assert foreign_post.status_code == 400
    assert foreign_post.headers['Cache-Control'] == 'no-store'
    assert 'Rezeptrevision nicht gefunden' in foreign_post.get_data(as_text=True)
    assert 'Bindungssuppe' in foreign_post.get_data(as_text=True)
    assert _bound(engine) == bound
    detached = client.post('/admin/patienten/menu', data=_form(token, '', row_version='1'))
    assert detached.status_code == 303
    assert _bound(engine)['recipe_revision_public_id'] is None


def test_http_option_labels_never_follow_a_renamed_recipe_head(http_client) -> None:
    client, actor_id, engine = http_client
    first = _insert_revision(engine, actor_id, 'Ursprüngliche Suppe', servings='4')
    second = _insert_revision(engine, actor_id, 'Umbenannte Suppe', revision_number=2,
                              recipe_id=int(first['recipe_id']), servings='9')
    body = client.get(EDITOR).get_data(as_text=True)
    old_label, new_label = _label(body, first['public_id']), _label(body, second['public_id'])
    assert 'Ursprüngliche Suppe' in old_label and 'Revision 1' in old_label and '4 PORTION' in old_label
    assert 'Umbenannte Suppe' not in old_label and '9 PORTION' not in old_label
    assert 'Umbenannte Suppe' in new_label and 'Revision 2' in new_label and '9 PORTION' in new_label
    # The page filter must not claim a full-set search before the form intents wire one.
    assert 'Angezeigte Revisionen filtern' in body and 'Rezept suchen' not in body


def test_http_invalid_keeps_signed_values_and_role_denial(http_client, admin_app, admin_engine) -> None:  # noqa: F811
    client, actor_id, engine = http_client
    revision = _insert_revision(engine, actor_id, 'Prüfungssuppe')
    token = _token(client)
    client.post('/admin/patienten/menu', data=_form(token, revision['public_id']))
    before = _counts(engine)
    bound = _bound(engine)
    invalid = _form(token, 'not-a-uuid', row_version='1', title='Geänderter Titel')
    response = client.post('/admin/patienten/menu', data=invalid)
    assert response.status_code == 400
    html = response.get_data(as_text=True)
    assert 'Geänderter Titel' in html
    assert 'not-a-uuid' in html or 'Rezept' in html
    assert _bound(engine) == bound and _counts(engine) == before
    stale = client.post('/admin/patienten/menu', data=_form(token, revision['public_id'], row_version='0'))
    assert stale.status_code == 409
    assert revision['public_id'] in stale.get_data(as_text=True)
    assert _bound(engine) == bound
    write_token = _token(client)
    editor, _ = _login(admin_app, admin_engine, [])
    denied = editor.post('/admin/patienten/menu', data=_form(write_token, revision['public_id']))
    assert denied.status_code in {401, 403, 409}
    assert _bound(engine) == bound
    anonymous = admin_app.test_client().get(EDITOR)
    assert anonymous.status_code == 401


def test_http_aligned_blank_add_remove_reorder(http_client) -> None:
    client, actor_id, engine = http_client
    first = _insert_revision(engine, actor_id, 'Erste Sauce')
    second = _insert_revision(engine, actor_id, 'Zweite Sauce')
    token = _token(client)
    data = MultiDict(_menu_form(_csrf=token, title='Zwei Zeilen', allergen_mode='auto',
                                origin_mode='auto', label_mode='auto'))
    data.setlist('component_public_id', ['', ''])
    data.setlist('component_text', ['Erste Sauce', 'Zweite Sauce'])
    data.setlist('recipe_revision_public_id', [first['public_id'], second['public_id']])
    assert client.post('/admin/patienten/menu', data=data).status_code == 303
    rows = _assignments(engine)
    assert [(row.component_text, row.revision) for row in rows] == [
        ('Erste Sauce', first['public_id']), ('Zweite Sauce', second['public_id']),
    ]
    reordered = MultiDict(_menu_form(_csrf=token, title='Zwei Zeilen', row_version='1',
                                     allergen_mode='auto', origin_mode='auto', label_mode='auto'))
    reordered.setlist('component_public_id', ['', '', ''])
    reordered.setlist('component_text', ['Zweite Sauce', 'Erste Sauce', ''])
    reordered.setlist('recipe_revision_public_id', [second['public_id'], first['public_id'], ''])
    assert client.post('/admin/patienten/menu', data=reordered).status_code == 303
    rows = _assignments(engine)
    assert [(row.component_text, row.revision) for row in rows] == [
        ('Zweite Sauce', second['public_id']), ('Erste Sauce', first['public_id']),
    ]


def test_browser_select_save_reload_and_no_latest_swap(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    first = _insert_revision(admin_engine, actor, 'Browser-Suppe')
    later = _insert_revision(admin_engine, int(actor), 'Browser-Suppe', revision_number=2,
                             recipe_id=int(first['recipe_id']), servings='8')
    page.goto(EDITOR)
    _ready(page)
    page.get_by_label('Titel', exact=True).fill('Gebundenes Menü')
    page.get_by_label('Eigener Baustein als Text').fill('Browser-Suppe')
    page.get_by_label('Rezeptrevision').select_option(first['public_id'])
    expect(_option(page, first['public_id'])).to_be_attached()
    assert _option(page, first['public_id']).get_attribute('data-content-hash') == first['hash']
    payload = _submit_menu(page)
    assert payload['recipe_revision_public_id'] == [first['public_id']]
    assert payload['component_text'] == ['Browser-Suppe']
    assert payload['component_public_id'] == ['']
    page.wait_for_load_state()
    expect(page.get_by_label('Rezeptrevision')).to_have_value(first['public_id'])
    selected = page.locator('select[name="recipe_revision_public_id"] option:checked')
    assert selected.get_attribute('data-content-hash') == first['hash']
    assert selected.get_attribute('data-revision-number') == '1'
    assert later['public_id'] in page.locator('select[name="recipe_revision_public_id"]').inner_html()
    assert page.get_by_label('Rezeptrevision').input_value() != later['public_id']
    assert PATIENT_FORBIDDEN.search(page.content()) is None
    _no_overflow(page)


def test_browser_detach_confirm_is_not_a_side_effect(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    revision = _insert_revision(admin_engine, actor, 'Lösesuppe')
    page.goto(EDITOR)
    page.get_by_label('Titel', exact=True).fill('Mit Bindung')
    page.get_by_label('Eigener Baustein als Text').fill('Lösesuppe')
    page.get_by_label('Rezeptrevision').select_option(revision['public_id'])
    _submit_menu(page)
    expect(page.get_by_label('Rezeptrevision')).to_have_value(revision['public_id'])
    page.get_by_label('Titel', exact=True).fill('Anderer Titel')
    expect(page.get_by_label('Rezeptrevision')).to_have_value(revision['public_id'])
    page.once('dialog', lambda dialog: dialog.dismiss())
    page.get_by_label('Rezeptrevision').select_option('')
    expect(page.get_by_label('Rezeptrevision')).to_have_value(revision['public_id'])
    page.once('dialog', lambda dialog: dialog.accept())
    page.get_by_label('Rezeptrevision').select_option('')
    expect(page.get_by_label('Rezeptrevision')).to_have_value('')
    payload = _submit_menu(page)
    assert payload['recipe_revision_public_id'] == ['']
    page.wait_for_load_state()
    expect(page.get_by_label('Rezeptrevision')).to_have_value('')
    assert _bound(admin_engine)['recipe_revision_public_id'] is None


def test_browser_add_remove_reorder_keeps_three_arrays(
    page_context: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    first = _insert_revision(admin_engine, actor, 'Oben')
    second = _insert_revision(admin_engine, actor, 'Unten')
    page.goto(EDITOR)
    page.get_by_label('Titel', exact=True).fill('Reihenfolge')
    page.locator('[name="component_text"]').fill('Oben')
    page.locator('[name="recipe_revision_public_id"]').select_option(first['public_id'])
    page.get_by_role('button', name='Baustein hinzufügen').click()
    page.locator('[name="component_text"]').nth(1).fill('Unten')
    page.locator('[name="recipe_revision_public_id"]').nth(1).select_option(second['public_id'])
    page.locator('#components-list [data-row]').nth(1).get_by_role('button', name='Nach oben', exact=True).click()
    payload = _submit_menu(page)
    assert payload['component_text'] == ['Unten', 'Oben']
    assert payload['recipe_revision_public_id'] == [second['public_id'], first['public_id']]
    assert payload['component_public_id'] == ['', '']
    page.get_by_role('button', name='Baustein entfernen').last.click()
    leftover = _submit_menu(page)
    assert leftover['component_text'] == ['Unten']
    assert leftover['recipe_revision_public_id'] == [second['public_id']]


def test_nojs_native_select_search_absent_and_archived_readable(
    nojs_page: Page, admin_engine: Engine,  # noqa: F811
) -> None:
    page = nojs_page
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    revision = _insert_revision(admin_engine, actor, 'Archivsuppe')
    page.goto(EDITOR)
    _ready(page)
    page.get_by_label('Titel', exact=True).fill('Ohne JavaScript')
    page.get_by_label('Eigener Baustein als Text').fill('Archivsuppe')
    page.get_by_label('Rezeptrevision').select_option(revision['public_id'])
    page.locator('form[data-menu-editor] button[type="submit"]').click()
    page.wait_for_load_state()
    expect(page.get_by_label('Rezeptrevision')).to_have_value(revision['public_id'])
    with admin_engine.begin() as connection:
        connection.execute(text('UPDATE cafeteria.recipes SET active=false WHERE title=:title'),
                           {'title': 'Archivsuppe'})
    page.reload()
    _ready(page)
    selected = page.locator('select[name="recipe_revision_public_id"] option:checked')
    expect(page.get_by_label('Rezeptrevision')).to_have_value(revision['public_id'])
    assert 'archiviert' in (selected.text_content() or '').lower()
    assert selected.get_attribute('data-content-hash') == revision['hash']
    page.get_by_label('Rezeptrevision').select_option('')
    page.locator('form[data-menu-editor] button[type="submit"]').click()
    page.wait_for_load_state()
    expect(page.get_by_label('Rezeptrevision')).to_have_value('')
    assert _bound(admin_engine)['recipe_revision_public_id'] is None


@pytest.mark.parametrize(('width', 'height'), VIEWPORTS)
def test_recipe_selector_viewports_keyboard_zoom_and_fonts(
    page_context: Page, admin_engine: Engine, width: int, height: int, tmp_path: Path,  # noqa: F811
) -> None:
    page = page_context
    with admin_engine.connect() as connection:
        actor = int(connection.execute(text('SELECT id FROM cafeteria.users ORDER BY id LIMIT 1')).scalar_one())
    revision = _insert_revision(admin_engine, actor, f'Sicht-{width}')
    page.set_viewport_size({'width': width, 'height': height})
    page.goto(_editor('patienten'))
    _ready(page)
    page.get_by_label('Titel', exact=True).fill(f'Viewport {width}')
    page.get_by_label('Eigener Baustein als Text').fill(f'Sicht-{width}')
    select = page.get_by_label('Rezeptrevision')
    expect(select).to_be_visible()
    box = select.bounding_box()
    assert box is not None and box['height'] >= 44
    page.get_by_label('Angezeigte Revisionen filtern', exact=True).fill('Sicht')
    expect(_option(page, revision['public_id'])).to_be_attached()
    select.select_option(revision['public_id'])
    select.focus()
    outline = page.evaluate('getComputedStyle(document.activeElement).outlineStyle')
    assert outline != 'none'
    _no_overflow(page)
    page.evaluate('document.documentElement.style.zoom = "2"')
    _ready(page)
    if width >= 1440:
        _no_overflow(page)
    page.evaluate('document.documentElement.style.zoom = "1"')
    shot = tmp_path / f'recipe-select-{width}x{height}.png'
    page.screenshot(path=str(shot), full_page=True)
    cafeteria = _editor('cafeteria')
    page.goto(cafeteria)
    _ready(page)
    expect(page.get_by_label('Rezeptrevision')).to_be_visible()
    assert page.locator('[name="internal_chf"]').count() == 1
    _no_overflow(page)
