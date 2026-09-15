"""HTTP contract for the shopping-list print route (SPDF-ROUTE): real PostgreSQL, real Flask
client, real PDF bytes through the actual ``render_shopping_pdf`` module -- no stand-ins.
"""
from __future__ import annotations

from io import BytesIO
from uuid import uuid4

from pypdf import PdfReader
from sqlalchemy.exc import OperationalError

from cafeteria import roles
from cafeteria.admin import shopping_list_routes as routes
from cafeteria.admin.shopping_pdf import ShoppingPdfError
from cafeteria.print_templates import PrintTemplateStateError
from cafeteria.shopping_list_store import add_manual_item, create_shopping_list
from test_shopping_list_db import (  # noqa: F401
    _bound_component, _compute, _ingredient, _item_public, _scope, app_engine, create_food,
    installed_pg16, pg16, seeded_pg16, store,
)
from test_shopping_list_routes import _state, client  # noqa: F401


def _path(list_id: str, revision: str | None = None) -> str:
    url = f'/admin/einkaufslisten/{list_id}/druck.pdf'
    return url if revision is None else f'{url}?revision={revision}'


def _extract(response) -> tuple[PdfReader, str]:
    pdf = PdfReader(BytesIO(response.data))
    return pdf, '\n'.join(page.extract_text() for page in pdf.pages)


def test_pdf_route_requires_draft_read(client, monkeypatch):  # noqa: F811
    owner, engine, test_client, ids = client
    list_id = create_shopping_list(engine, _scope(ids), title='Rechtecheck')
    anonymous = test_client.application.test_client()
    assert anonymous.get(_path(list_id)).status_code == 401
    monkeypatch.setitem(roles.ROLE_CAPABILITIES, 'Cafeteria.Publisher', set())
    assert test_client.get(_path(list_id)).status_code == 403


def test_pdf_route_renders_selected_revision_not_latest(client):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Alterbeleg')
    revision_1 = _compute(engine, ids, list_id)
    _compute(engine, ids, list_id, expected_row_version=2)
    response = test_client.get(_path(list_id, revision_1))
    assert response.status_code == 200
    assert response.headers['X-Shopping-List-Revision'] == revision_1
    _, text_content = _extract(response)
    assert 'Beleg 1' in text_content


def test_pdf_route_defaults_to_latest_revision(client):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Neueste')
    _compute(engine, ids, list_id)
    revision_2 = _compute(engine, ids, list_id, expected_row_version=2)
    response = test_client.get(_path(list_id))
    assert response.status_code == 200
    assert response.headers['X-Shopping-List-Revision'] == revision_2
    _, text_content = _extract(response)
    assert 'Beleg 2' in text_content


def test_pdf_route_headers_no_store_inline_filename(client):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Kopfzeilen')
    revision = _compute(engine, ids, list_id)
    response = test_client.get(_path(list_id, revision))
    assert response.status_code == 200
    assert response.mimetype == 'application/pdf' and response.data.startswith(b'%PDF')
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.headers['Content-Disposition'] == f'inline; filename="einkaufsliste-{list_id}-beleg-1.pdf"'
    assert response.headers['X-Shopping-List-Revision'] == revision
    assert response.headers['X-Print-Template-Revision'] == 'standard:1'


def test_pdf_route_unknown_or_foreign_revision_404(client):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Eigene')
    other_list = create_shopping_list(engine, scope, title='Fremd')
    foreign_revision = _compute(engine, ids, other_list)
    assert test_client.get(_path(list_id, str(uuid4()))).status_code == 404
    assert test_client.get(_path(list_id, foreign_revision)).status_code == 404


def test_pdf_route_list_without_revision_404(client):  # noqa: F811
    owner, engine, test_client, ids = client
    list_id = create_shopping_list(engine, _scope(ids), title='Ohne Beleg')
    assert test_client.get(_path(list_id)).status_code == 404


def test_pdf_route_rejects_unknown_query_400(client):  # noqa: F811
    owner, engine, test_client, ids = client
    list_id = create_shopping_list(engine, _scope(ids), title='Query')
    assert test_client.get(f'/admin/einkaufslisten/{list_id}/druck.pdf?unknown=1').status_code == 400
    assert test_client.get(f'/admin/einkaufslisten/{list_id}/druck.pdf?revision=a&revision=b').status_code == 400


def test_pdf_route_contains_manual_items_and_decimal_quantities(client):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Mehl')
    _bound_component(owner, engine, ids, [_ingredient(food, '133.25', 'G')])
    list_id = create_shopping_list(engine, scope, title='Inhaltstest')
    _compute(engine, ids, list_id)
    add_manual_item(engine, scope, list_id, item_text='Servietten', quantity='3.333', unit_code='STK')
    response = test_client.get(_path(list_id))
    assert response.status_code == 200
    _, text_content = _extract(response)
    assert '133,25 Gramm' in text_content
    assert 'Servietten' in text_content and '3,333000 STK' in text_content


def test_pdf_route_get_performs_no_writes(client):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Schreibfrei')
    _compute(engine, ids, list_id)
    add_manual_item(engine, scope, list_id, item_text='Servietten')
    before = _state(owner)
    assert test_client.get(_path(list_id)).status_code == 200
    assert _state(owner) == before


def test_pdf_route_error_responses_are_no_store(client):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Fehlerkopf')
    _compute(engine, ids, list_id)
    bad_query = test_client.get(f'/admin/einkaufslisten/{list_id}/druck.pdf?unknown=1')
    assert bad_query.status_code == 400
    assert bad_query.headers['Cache-Control'] == 'no-store'
    missing_revision = test_client.get(_path(list_id, str(uuid4())))
    assert missing_revision.status_code == 404
    assert missing_revision.headers['Cache-Control'] == 'no-store'


def test_pdf_route_template_failure_returns_422_no_store(client, monkeypatch):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Vorlagenfehler')
    _compute(engine, ids, list_id)

    def fail_template(*args, **kwargs):
        raise PrintTemplateStateError('Vorlagen nicht verfügbar')

    monkeypatch.setattr(routes, 'active_template', fail_template)
    response = test_client.get(_path(list_id))
    assert response.status_code == 422
    assert 'nicht vollständig als PDF' in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.mimetype != 'application/pdf'
    assert not response.data.startswith(b'%PDF')


def test_pdf_route_renderer_failure_returns_422(client, monkeypatch):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Rendererfehler')
    _compute(engine, ids, list_id)

    def fail_render(*args, **kwargs):
        raise ShoppingPdfError('nicht darstellbar')

    monkeypatch.setattr(routes, 'render_shopping_pdf', fail_render)
    response = test_client.get(_path(list_id))
    assert response.status_code == 422
    assert 'nicht vollständig als PDF' in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.mimetype != 'application/pdf'
    assert not response.data.startswith(b'%PDF')


def test_pdf_route_database_failure_returns_503_no_store(client, monkeypatch):  # noqa: F811
    owner, engine, test_client, ids = client
    ids['owner'] = owner
    scope = _scope(ids)
    food = create_food(engine, ids, 'Zutat')
    _bound_component(owner, engine, ids, [_ingredient(food, '100', 'G')])
    list_id = create_shopping_list(engine, scope, title='Datenbankfehler')
    _compute(engine, ids, list_id)

    def fail_database(*args, **kwargs):
        raise OperationalError('PRIVATE_DETAIL', {}, RuntimeError('PRIVATE_DETAIL'))

    monkeypatch.setattr(routes, 'active_template', fail_database)
    response = test_client.get(_path(list_id))
    assert response.status_code == 503
    assert 'Einkaufslisten sind derzeit nicht verfügbar' in response.text
    assert 'PRIVATE_DETAIL' not in response.text
    assert response.headers['Cache-Control'] == 'no-store'
    assert response.mimetype != 'application/pdf'
    assert not response.data.startswith(b'%PDF')
