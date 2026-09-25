"""Browser coverage for AC-11, AC-12, AC-13 regarding shared courses."""
from __future__ import annotations

import re
from pathlib import Path

import pytest
from playwright.sync_api import expect

from cafeteria.course_store import persist_service_courses
from cafeteria.workflow import publish_draft
from cafeteria.workflow_partial_store import persist_menu_item, persist_service_state
from test_admin_ux_browser import live_server as live_server
from test_admin_workflow_routes import DAY, WEEK, _login, _scope
from test_course_week_html import _recipe
from test_rendered_ui import admin_app as admin_app, admin_engine as admin_engine, browser as browser
from test_rendered_ui import app as app
from test_public_mobile_ui import http_app as http_app, public_server as public_server
from test_workflow_partial_store_db import _payload, _service_payload

EVIDENCE = Path(__file__).resolve().parents[2] / '.claude/evidence/sdd-courses-browser-0918'


def test_ac11_course_editor_retains_bound_recipe(browser, live_server, admin_app, admin_engine) -> None:
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    engine = admin_engine
    scope = _scope(engine, user_id, 'staff_guest')
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    
    soup = _recipe(engine, user_id, scope.location_id, 'Gemüsesuppe')
    other = _recipe(engine, user_id, scope.location_id, 'Tomatensuppe')
    
    persist_service_courses(
        engine, scope, WEEK, DAY, 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['public_id']},
        dessert={'state': 'unplanned'},
        exceptions=[{
            'option': 'VEGGIE', 'kind': 'soup', 'state': 'planned',
            'recipe_public_id': other['public_id'],
        }],
    )

    context = browser.new_context(base_url=live_server)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context.add_cookies([{
        'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True,
    }])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    
    try:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        
        page.goto(f'/admin/cafeteria?week={DAY}&recipe_search=zzzz-kein-treffer')
        
        page.locator('summary:has-text("Gänge planen")').first.click(force=True)
        
        expect(page.locator('select[name="soup_recipe"] option:checked').first).to_have_text(re.compile('Gemüsesuppe'))
        expect(page.locator('select[name="VEGGIE_soup_recipe"] option:checked').first).to_have_text(re.compile('Tomatensuppe'))
        
        page.screenshot(path=str(EVIDENCE / 'ac11-course-editor-retained-recipes.png'), full_page=True)
    finally:
        context.close()


def test_ac12_course_issues_in_info_bar(browser, live_server, admin_app, admin_engine) -> None:
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    engine = admin_engine
    scope = _scope(engine, user_id, 'staff_guest')
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'MENU_1', _payload(staff=True), 0)
    persist_menu_item(engine, scope, WEEK, DAY, 'LUNCH', 'VEGGIE', _payload(title='Gemüse', staff=True), 0)
    
    soup = _recipe(engine, user_id, scope.location_id, 'Gemüsesuppe')
    
    persist_service_courses(
        engine, scope, WEEK, DAY, 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['public_id']},
        dessert={'state': 'not_offered'},
        exceptions=[],
    )

    context = browser.new_context(base_url=live_server)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context.add_cookies([{
        'name': 'session', 'value': cookie.value, 'url': live_server, 'httpOnly': True,
    }])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    
    try:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        
        page.goto(f'/admin/cafeteria?week={DAY}')
        
        # Since the week plan core the course warnings live in the shared status bar;
        # the list of affected courses opens from the native «Gangangaben prüfen» disclosure.
        course_status = page.locator('dl.admin-statusbar .admin-statusbar-item').filter(
            has=page.locator('dt', has_text='Gänge'))
        expect(course_status).to_have_count(1)
        expect(course_status).to_have_class(re.compile(r'admin-statusbar-item--warning'))
        expect(course_status.locator('.admin-statusbar-value-text')).to_have_text('1 Gang prüfen')
        expect(course_status.locator('.admin-statusbar-detail')).to_have_text('1 Gang ohne Allergenangaben')

        issues = page.locator('details#course-issues')
        expect(issues).to_have_count(1)
        issues.locator('summary').click()
        expect(issues).to_have_attribute('open', '')
        expect(issues).to_be_in_viewport()
        expect(issues).to_contain_text('Allergenangaben fehlen')
        
        expect(page.locator(f'.menu-slot[data-day="{DAY}"][data-option="MENU_1"]')).not_to_contain_text('Geprüft')
        
        page.screenshot(path=str(EVIDENCE / 'ac12-course-issues-infobar.png'), full_page=True)
    finally:
        context.close()


@pytest.mark.parametrize('javascript_enabled', [True, False])
@pytest.mark.parametrize('family', ['cafeteria', 'patienten'])
def test_course_disclosure_form_contract_and_viewports(
    browser, live_server, admin_app, admin_engine, javascript_enabled, family,
) -> None:
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, user_id, 'staff_guest' if family == 'cafeteria' else 'patient')
    persist_service_state(admin_engine, scope, WEEK, DAY, 'LUNCH', _service_payload(), 0)
    recipe = _recipe(admin_engine, user_id, scope.location_id, 'Gemüsesuppe')
    context = browser.new_context(base_url=live_server, java_script_enabled=javascript_enabled)
    cookie = client.get_cookie('session')
    assert cookie is not None
    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    try:
        page = context.new_page()
        page.goto(f'/admin/{family}?week={DAY}')
        editor = page.locator(f'#course-{DAY}-LUNCH')
        form = editor.locator('form[method="post"]')
        fields = dict(form.evaluate('(form) => Array.from(new FormData(form).entries())'))
        expected = {'_csrf': fields['_csrf'], 'week': DAY, 'day': DAY, 'meal': 'LUNCH'}
        for prefix in ('soup', 'dessert', 'MENU_1_soup', 'MENU_1_dessert', 'VEGGIE_soup', 'VEGGIE_dessert'):
            expected.update({
                f'{prefix}_public_id': '', f'{prefix}_row_version': '0',
                f'{prefix}_state': 'inherit' if prefix.startswith(('MENU_1', 'VEGGIE')) else 'unplanned',
                f'{prefix}_recipe': '',
            })
        assert fields == expected
        for width in (360, 768, 1024, 1440):
            page.set_viewport_size({'width': width, 'height': 900})
            if not editor.evaluate('(el) => el.open'):
                editor.locator(':scope > summary').click()
            expect(form.locator('select[name="soup_recipe"]')).not_to_be_visible()
            for summary in editor.locator('summary:visible').all():
                assert summary.bounding_box()['height'] >= 48
            assert page.evaluate('document.documentElement.scrollWidth <= window.innerWidth')
            page.screenshot(path=str(EVIDENCE / f'wp26-{family}-{javascript_enabled}-{width}.png'), full_page=True)
        # Native disclosures never alter which fields are submitted, including CAS.
        editor.locator(':scope > summary').click()
        expect(page.get_by_role('link', name=f'Suppe planen · {DAY} · LUNCH')).to_be_visible()
        page.locator(f'a[href="#course-{DAY}-LUNCH-soup-state"]').click()
        expect(form.locator('select[name="soup_state"]')).to_be_visible()
        if javascript_enabled:
            expect(form.locator('select[name="soup_state"]')).to_be_focused()
        form.locator('select[name="soup_state"]').select_option('planned')
        expect(form.locator('select[name="soup_recipe"]')).to_be_visible()
        form.locator('select[name="soup_recipe"]').select_option(recipe['public_id'])
        expected['soup_state'] = 'planned'
        expected['soup_recipe'] = recipe['public_id']
        assert dict(form.evaluate('(form) => Array.from(new FormData(form).entries())')) == expected
        with page.expect_navigation():
            form.get_by_role('button', name='Speichern', exact=True).click()
        expect(page.locator('[data-course="soup"]').first).to_contain_text('Suppe: Gemüsesuppe')
        expect(page.locator('[data-course="soup"]').first).to_contain_text('Allergenangaben fehlen')
    finally:
        context.close()


@pytest.fixture
def live_public_server(admin_app):
    from cafeteria.public.routes import bp as public_bp
    from cafeteria.signage.routes import bp as signage_bp
    try:
        admin_app.register_blueprint(public_bp)
    except Exception:
        pass
    try:
        admin_app.register_blueprint(signage_bp, name='real_signage')
    except Exception:
        pass

    from werkzeug.serving import make_server
    import threading
    server = make_server('127.0.0.1', 0, admin_app, threaded=True)
    thread = threading.Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}'
    finally:
        server.shutdown()
        thread.join(timeout=5)
        server.server_close()

def test_ac13_public_courses_with_allergens_and_exceptions(browser, live_public_server, admin_app, admin_engine, monkeypatch) -> None:
    client, user_id = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    engine = admin_engine
    scope = _scope(engine, user_id, 'staff_guest')

    import datetime
    today = datetime.date.today()
    week_date = today - datetime.timedelta(days=today.weekday())
    DAY = week_date.isoformat()

    for offset in range(5):
        d = (week_date + datetime.timedelta(days=offset)).isoformat()
        persist_service_state(engine, scope, week_date, d, 'LUNCH', _service_payload(), 0)
        p1 = _payload(staff=True)
        persist_menu_item(engine, scope, week_date, d, 'LUNCH', 'MENU_1', p1, 0)
        p2 = _payload(title='Gemüse', staff=True)
        persist_menu_item(engine, scope, week_date, d, 'LUNCH', 'VEGGIE', p2, 0)

    def _recipe_with_allergens(name):
        from prepared_food_fixtures import create_food, create_recipe, execute, freeze
        import secrets
        from sqlalchemy import text
        with engine.connect() as connection:
            authz = connection.execute(
                text('SELECT authz_version FROM cafeteria.users WHERE id=:id'), {'id': user_id},
            ).scalar_one()
        ids = {'actor': user_id, 'authz': authz, 'location': scope.location_id}
        storage = execute(
            engine,
            '''SELECT cafeteria.create_storage_location_v21(
                :actor,:authz,:location,NULL,NULL,CAST(:payload AS jsonb))''',
            ids, {'code': 'COURSE_' + secrets.token_hex(3).upper(), 'name': 'Gangtestlager', 'sort_order': 1},
        )
        ids['storage'] = storage['public_id']
        food = create_food(engine, ids, name + '-zutat', unit='G')
        with engine.begin() as connection:
            connection.execute(
                text("INSERT INTO cafeteria.food_allergens (location_id, food_id, allergen_id, presence) SELECT f.location_id, f.id, a.id, 'contains' FROM cafeteria.foods f, cafeteria.allergens a WHERE f.public_id = :fid AND a.code = 'MILK'"),
                {'fid': food['public_id']}
            )
        recipe = create_recipe(engine, ids, [food], name=name, unit='G', quantity='1')
        freeze(engine, ids, recipe)
        return recipe

    soup = _recipe_with_allergens('Milchsuppe')
    dessert_exception = _recipe(engine, user_id, scope.location_id, 'Fruchtsalat')

    persist_service_courses(
        engine, scope, week_date, DAY, 'LUNCH',
        soup={'state': 'planned', 'recipe_public_id': soup['public_id']},
        dessert={'state': 'not_offered'},
        exceptions=[{
            'option': 'VEGGIE', 'kind': 'dessert', 'state': 'planned',
            'recipe_public_id': dessert_exception['public_id'],
        }],
    )

    with engine.begin() as connection:
        from sqlalchemy import text
        connection.execute(
            text("UPDATE cafeteria.menu_weeks SET title='Testwoche' WHERE location_id=:loc AND week_start=:wk"),
            {'loc': scope.location_id, 'wk': week_date}
        )
        connection.execute(text("UPDATE cafeteria.menu_items SET allergen_review_status='checked'"))
        connection.execute(text("UPDATE cafeteria.menu_item_components SET component_row_version = (SELECT row_version FROM cafeteria.menu_components WHERE id = component_id)"))
        draft_row_version = connection.execute(
            text("SELECT row_version FROM cafeteria.menu_weeks WHERE location_id=:loc AND week_start=:wk"),
            {'loc': scope.location_id, 'wk': week_date}
        ).scalar_one()

    from cafeteria import workflow
    monkeypatch.setattr(workflow, '_review_open_connection', lambda *args, **kwargs: False)
    monkeypatch.setattr(workflow, 'week_context_review_open_connection', lambda *args, **kwargs: False)
    monkeypatch.setattr(workflow, 'validate_publication_fit', lambda *args, **kwargs: None)

    publish_draft(
        engine, scope.profile_code, week_date,
        expected_row_version=draft_row_version,
        actor_id=user_id,
        issuer_engine=admin_app.extensions['cafeteria_auth_issuer_db']
    )

    admin_app.config['DEMO_TODAY'] = week_date.isoformat()
    # Ensure the DB connections from http_app see the new data
    
    context = browser.new_context(base_url=live_public_server)
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    
    try:
        page = context.new_page()
        page.set_viewport_size({'width': 1440, 'height': 900})
        
        page.goto('/cafeteria/wochenangebot/')
        day_section = page.locator(f'#tag-{DAY}')
        expect(day_section).to_contain_text('Milchsuppe')
        expect(day_section.locator('.signage-tags .label.amber').first).to_contain_text('Milch')
        expect(day_section).to_contain_text('Kein Dessert')
        
        expect(day_section).to_contain_text('Fruchtsalat')
        
        page.screenshot(path=str(EVIDENCE / 'ac13-public-week.png'), full_page=True)
        
        page.goto('/signage/cafeteria/woche')
        board = page.locator('.cafe-week-layout').first
        expect(board).to_contain_text('Milchsuppe')
        expect(board.locator('.signage-tags .label.amber').first).to_contain_text('Milch')
        expect(board).to_contain_text('Kein Dessert')
        
        expect(board).to_contain_text('Fruchtsalat')
        
        page.screenshot(path=str(EVIDENCE / 'ac13-signage-week.png'), full_page=True)
    finally:
        context.close()
