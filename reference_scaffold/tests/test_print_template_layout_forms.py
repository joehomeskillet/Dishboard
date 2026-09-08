"""Native layout forms keep stored revisions and explicit render failures usable."""
from __future__ import annotations

import pytest
from playwright.sync_api import expect
from werkzeug.datastructures import MultiDict

from cafeteria.print_template_config import PrintTemplateValidationError, default_layout
from cafeteria.print_templates import default_document, read_templates, template_revision
from cafeteria.admin.week_pdf import WeekPdfFitError
from test_admin_workflow_db import _patient_values, _save, _staff_values
from test_admin_workflow_routes import DAY, _login, database_engine  # noqa: F401
from test_print_template_archive import seed, snapshot
from test_print_template_routes import editor_app, fields  # noqa: F401
from test_print_template_browser import _context, _targets, browser, editor_server  # noqa: F401


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
@pytest.mark.parametrize('render_error', [PrintTemplateValidationError, WeekPdfFitError])
def test_stored_layout_reports_unsupported_renderer_without_500(editor_app, database_engine, monkeypatch, family, profile, render_error):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    document = default_document()
    document['schema_version'] = 3
    template_revision(document, 'standard')['config']['layout'] = default_layout(profile)
    seed(database_engine, profile, document)
    before = snapshot(database_engine)
    message = 'neuen PDF-Renderer'

    def incompatible_renderer(*args, **kwargs):
        # Keep the fallback error contract covered after the new renderer lands.
        raise render_error('Diese Vorlage benötigt den neuen PDF-Renderer.')

    monkeypatch.setattr('cafeteria.admin.print_template_routes.render_week_pdf', incompatible_renderer)
    monkeypatch.setattr('cafeteria.admin.print_routes.render_week_pdf', incompatible_renderer)
    editor = client.get(f'/admin/vorlagen/{family}?week={DAY}&revision=1')
    assert editor.status_code == 200 and message in editor.text
    assert '<iframe' not in editor.text
    assert 'name="revision" value="1"' in editor.text
    assert 'name="version" value="0"' in editor.text
    for path in (f'/admin/vorlagen/{family}/vorschau.pdf', f'/admin/{family}/preview/print'):
        response = client.get(f'{path}?week={DAY}')
        assert response.status_code == 422 and message in response.text
    assert snapshot(database_engine) == before


def layout_fields(profile, **extra):
    layout = default_layout(profile)
    result = fields(layout_mode='custom')
    for key, value in layout.items():
        if isinstance(value, list):
            result.update({f'layout_{key}_{index}': item for index, item in enumerate(value)})
        elif key != 'version':
            result[f'layout_{key}'] = value
    result.update(extra)
    return result


@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_explicit_layout_intent_preserves_legacy_and_historical_revisions(editor_app, database_engine, family, profile):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    path = f'/admin/vorlagen/{family}?week={DAY}'
    old = default_document()['templates'][0]['revisions'][0]
    assert client.post(path, data=layout_fields(profile, layout_mode='preserve')).status_code == 303
    with database_engine.connect() as connection:
        legacy = read_templates(connection, profile)
    assert legacy['schema_version'] == 2
    assert 'layout' not in template_revision(legacy, 'standard')['config']
    data = layout_fields(profile, version='1', revision='2', layout_grid='days_columns',
                         layout_photo='small', layout_alignment='center', layout_day_label_width='wide',
                         layout_row_spacing='roomy', layout_legend_position='top',
                         layout_header_0='title', layout_header_1='logo')
    assert client.post(path, data=data).status_code == 303
    with database_engine.connect() as connection:
        saved = read_templates(connection, profile)
    config = template_revision(saved, 'standard')['config']
    assert saved['schema_version'] == 3 and saved['active_revision'] == 1
    assert saved['templates'][0]['revisions'][0] == old
    assert saved['templates'][0]['revisions'][:2] == legacy['templates'][0]['revisions']
    assert config['layout'] == {**default_layout(profile), 'grid': 'days_columns', 'photo': 'small',
                                'alignment': 'center', 'day_label_width': 'wide', 'row_spacing': 'roomy',
                                'legend_position': 'top', 'header': ['title', 'logo', 'date_range', 'week_number', 'header_note']}
    # Editing appearance on a saved layout keeps that exact layout without migration.
    data.update(version='2', revision='3', layout_mode='preserve', header_text='Guten Appetit')
    assert client.post(path, data=data).status_code == 303
    with database_engine.connect() as connection:
        assert template_revision(read_templates(connection, profile), 'standard')['config']['layout'] == config['layout']


@pytest.mark.parametrize('case', ['partial', 'duplicate', 'unknown', 'missing_binding', 'price', 'url', 'unconfirmed'])
def test_invalid_layout_never_writes_or_refreshes_form_version(editor_app, database_engine, case):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    path = f'/admin/vorlagen/patienten?week={DAY}'
    data = layout_fields('patient', layout_grid='days_columns', header_text='Mein Entwurf')
    if case == 'partial':
        del data['layout_photo']
    elif case == 'duplicate':
        data = MultiDict([*data.items(), ('layout_grid', 'days_rows')])
    elif case == 'unknown':
        data['layout_html'] = '<script>alert(1)</script>'
    elif case == 'missing_binding':
        data['layout_header_0'] = 'title'
    elif case == 'price':
        data['layout_menu_fields_0'] = 'prices'
    elif case == 'url':
        data['layout_photo'] = 'https://example.invalid/remote.jpg'
    else:
        data['layout_mode'] = 'preserve'
    before = snapshot(database_engine)
    response = client.post(path, data=data)
    assert response.status_code == 400
    assert 'name="version" value="0"' in response.text and 'name="revision" value="1"' in response.text
    assert 'Mein Entwurf</textarea>' in response.text
    assert 'value="days_columns" selected' in response.text
    assert 'aria-invalid="true"' in response.text and 'autofocus' in response.text
    assert '<script>alert(1)</script>' not in response.text
    assert '<option value="prices"' not in response.text
    assert snapshot(database_engine) == before


def test_layout_conflict_retains_original_revision_and_all_control_values(editor_app, database_engine):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    path = f'/admin/vorlagen/patienten?week={DAY}'
    assert client.post(path, data=fields(header_text='Andere Sitzung')).status_code == 303
    before = snapshot(database_engine)
    response = client.post(path, data=layout_fields('patient', layout_grid='days_columns', name='Mein Layout'))
    assert response.status_code == 409
    assert 'Eigenschaften · Revision 1' in response.text and 'PDF-Vorschau · Revision 1' in response.text
    assert 'name="version" value="0"' in response.text and 'name="revision" value="2"' not in response.text
    assert 'value="days_columns" selected' in response.text and 'value="custom" selected' in response.text
    assert 'value="Mein Layout"' in response.text
    assert snapshot(database_engine) == before


@pytest.mark.parametrize('case,status', [('csrf', 400), ('actor', 400), ('oversize', 413), ('role', 403)])
def test_layout_boundaries_cannot_bypass_authority_or_payload_limits(editor_app, database_engine, case, status):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Editor' if case == 'role' else 'Cafeteria.Admin'])
    data = layout_fields('patient')
    if case == 'csrf':
        data['_csrf'] = 'wrong'
    elif case == 'actor':
        data['actor_id'] = '1'
    elif case == 'oversize':
        data['layout_grid'] = 'x' * 17_000
    before = snapshot(database_engine)
    assert client.post(f'/admin/vorlagen/patienten?week={DAY}', data=data).status_code == status
    assert snapshot(database_engine) == before


@pytest.mark.parametrize('width,javascript', [(390, False), (1440, True)])
@pytest.mark.parametrize('family,profile', [('cafeteria', 'staff_guest'), ('patienten', 'patient')])
def test_native_layout_controls_keyboard_errors_and_no_js_save(editor_app, editor_server, database_engine, browser, tmp_path, width, javascript, family, profile):  # noqa: F811
    client, _ = _login(editor_app, database_engine, ['Cafeteria.Admin'])
    _save(database_engine, profile, _staff_values() if profile == 'staff_guest' else _patient_values())
    with _context(browser, editor_server, client, width, javascript=javascript) as context:
        page = context.new_page()
        page.goto(f'/admin/vorlagen/{family}?week={DAY}')
        expect(page.locator('iframe')).to_be_visible()
        if profile == 'patient':
            assert page.locator('option[value="prices"]').count() == 0
        page.get_by_text('Raster, Bilder und Abstände', exact=True).click()
        page.get_by_label('Wochenraster', exact=True).select_option('days_columns')
        _targets(page)
        with page.expect_response(lambda response: response.request.method == 'POST') as result:
            page.get_by_role('button', name='Entwurf speichern und prüfen', exact=True).click()
        assert result.value.status == 400
        expect(page.get_by_label('Layout beim Speichern', exact=True)).to_be_focused()
        expect(page.get_by_label('Wochenraster', exact=True)).to_have_value('days_columns')
        page.get_by_label('Layout beim Speichern', exact=True).select_option('custom')
        page.locator('summary').filter(has_text='Reihenfolge im Kopfbereich').click()
        first = page.get_by_label('Reihenfolge im Kopfbereich · Position 1', exact=True)
        first.focus()
        page.keyboard.press('ArrowDown')
        page.keyboard.press('Tab')
        expect(page.get_by_label('Reihenfolge im Kopfbereich · Position 2', exact=True)).to_be_focused()
        first.select_option('title')
        page.get_by_label('Reihenfolge im Kopfbereich · Position 2', exact=True).select_option('logo')
        page.get_by_role('button', name='Entwurf speichern und prüfen', exact=True).click()
        expect(page.get_by_role('heading', name='Eigenschaften · Revision 2', exact=True)).to_be_visible()
        expect(page.get_by_text('Individuelles Wochenlayout gespeichert.', exact=False)).to_be_visible()
        _targets(page)
        page.screenshot(path=str(tmp_path / f'layout-editor-{family}-{width}-js-{javascript}.png'), full_page=True, caret='initial')
        for summary in page.locator('form.card summary').all():
            summary.click()
        _targets(page)
        page.locator('form.card').filter(has=page.locator('#template-name')).screenshot(
            path=str(tmp_path / f'layout-controls-{family}-{width}-js-{javascript}.png'), caret='initial')
    with database_engine.connect() as connection:
        config = template_revision(read_templates(connection, profile), 'standard')['config']
    assert config['layout']['grid'] == 'days_columns'
    assert config['layout']['header'][:2] == ['title', 'logo']
