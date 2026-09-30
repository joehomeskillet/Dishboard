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


@pytest.fixture(autouse=True)
def _isolated_course_evidence(tmp_path, monkeypatch):
    """Keep existing screenshot assertions away from shared evidence paths."""
    monkeypatch.setitem(globals(), 'EVIDENCE', tmp_path / 'course-evidence')


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
        
        # Gang warnings stay visible in the week check summary. The affected
        # courses open from the native «Gangangaben prüfen» disclosure.
        course_status = page.locator('#week-check-summary')
        expect(course_status).to_contain_text('1 Gang prüfen')
        expect(course_status).to_contain_text('ohne Allergenangaben')
        expect(course_status).to_contain_text('nicht allergenfrei')

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
                minimum = summary.evaluate("e => parseFloat(getComputedStyle(e).getPropertyValue('--app-control-min-height'))")
                assert summary.bounding_box()['height'] >= minimum
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


@pytest.mark.parametrize('family,profile,meal', [
    ('cafeteria', 'staff_guest', 'LUNCH'),
    ('patienten', 'patient', 'LUNCH'),
    ('patienten', 'patient', 'DINNER'),
])
@pytest.mark.parametrize('javascript_enabled,width,height', [(True, 1440, 900), (False, 390, 844)])
def test_native_course_add_edit_preserves_neighbor_slots(
    browser, live_server, admin_app, admin_engine, tmp_path,
    family, profile, meal, javascript_enabled, width, height,
) -> None:
    """Wrong meal/kind writes, lost overrides and stale overwrites must fail."""
    import datetime
    import json
    import time
    from urllib.parse import parse_qs

    from cafeteria.course_store import load_week_courses

    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    scope = _scope(admin_engine, actor, profile)
    names = ('Rüeblisuppe', 'Tomatensuppe', 'Apfelcreme', 'Birnenkompott')
    recipes = [_recipe(admin_engine, actor, scope.location_id, name) for name in names]
    next_day = (datetime.date.fromisoformat(DAY) + datetime.timedelta(days=1)).isoformat()
    target = (DAY, meal)
    neighbors = [(next_day, meal)]
    if profile == 'patient':
        neighbors.append((DAY, 'DINNER' if meal == 'LUNCH' else 'LUNCH'))
    for day, period in [target, *neighbors]:
        persist_service_state(admin_engine, scope, WEEK, day, period, _service_payload(), 0)
        for option in ('MENU_1', 'VEGGIE'):
            persist_menu_item(admin_engine, scope, WEEK, day, period, option,
                              _payload(title=f'{day} {period} {option}', staff=profile == 'staff_guest'), 0)
        persist_service_courses(
            admin_engine, scope, WEEK, day, period,
            soup={'state': 'unplanned'} if (day, period) == target else {
                'state': 'planned', 'recipe_public_id': recipes[1]['public_id']},
            dessert={'state': 'unplanned'} if (day, period) == target else {
                'state': 'planned', 'recipe_public_id': recipes[3]['public_id']},
            exceptions=[{'option': 'VEGGIE', 'kind': kind, 'state': 'planned',
                         'recipe_public_id': recipes[index]['public_id']}
                        for kind, index in (('soup', 1), ('dessert', 3))],
        )

    def stored():
        return load_week_courses(admin_engine, scope.location_id, WEEK, profile)

    initial = stored()
    untouched = {key: value for key, value in initial.items() if key != target}
    cookie = client.get_cookie('session')
    assert cookie is not None
    records = []
    with browser.new_context(base_url=live_server, java_script_enabled=javascript_enabled,
                             has_touch=width == 390, viewport={'width': width, 'height': height}) as context:
        context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': live_server}])
        page = context.new_page()
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        editor = page.locator(f'#course-{DAY}-{meal}')
        form = editor.locator('form[method="post"]')
        posts = []
        page.on('request', lambda request: posts.append(request) if request.method == 'POST' else None)
        navigation = []

        def record_navigation(event, **values):
            navigation.append({'event': event, 'time': time.monotonic(), **values})
            (tmp_path / 'navigation.json').write_text(json.dumps(navigation, indent=2))

        def document_request(request):
            if request.is_navigation_request() and request.frame == page.main_frame:
                record_navigation('request', method=request.method, url=request.url,
                                  redirected_from=request.redirected_from.url if request.redirected_from else None)

        def document_response(response):
            if response.request.is_navigation_request() and response.request.frame == page.main_frame:
                record_navigation('response', status=response.status, url=response.url,
                                  location=response.headers.get('location'), refresh=response.headers.get('refresh'))

        page.on('request', document_request)
        page.on('response', document_response)
        page.on('framenavigated', lambda frame: record_navigation('navigation', url=frame.url)
                if frame == page.main_frame else None)
        expected_pointer = {'coarse': width == 390, 'anyCoarse': width == 390,
                            'fine': width == 1440, 'touch': int(width == 390)}

        def capture(stage, action):
            record_navigation('capture', stage=stage, url=page.url,
                              ready_state=page.evaluate('document.readyState'))
            record_navigation('action-state', stage=stage, state=action.evaluate('''el => ({
                connected: el.isConnected, rects: el.getClientRects().length,
                box: el.getBoundingClientRect().toJSON(), visibility: getComputedStyle(el).visibility,
                display: getComputedStyle(el).display,
                details: [...(function* () { for (let p = el.parentElement; p; p = p.parentElement)
                    if (p.tagName === 'DETAILS') yield p; })()].map(p => ({id: p.id, open: p.open}))
            })'''))
            pointer_script = '''() => ({coarse: matchMedia('(pointer: coarse)').matches,
                anyCoarse: matchMedia('(any-pointer: coarse)').matches,
                fine: matchMedia('(pointer: fine)').matches, touch: navigator.maxTouchPoints})'''
            assert page.evaluate(pointer_script) == expected_pointer
            if javascript_enabled:
                action.scroll_into_view_if_needed()
            else:
                action.focus()
                expect(action).to_be_focused()
                expect(action).to_be_in_viewport()
            box = action.bounding_box()
            assert box['width'] == box['height'] == (44 if width == 390 else 36)
            icon = action.locator('svg').bounding_box()
            assert icon['width'] == icon['height'] == 20
            assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
            page.screenshot(path=str(tmp_path / f'{stage}.png'), full_page=False)
            assert page.evaluate(pointer_script) == expected_pointer
            records.append({'stage': stage, 'box': box, 'pointer': expected_pointer})

        for kind, label, index, adding in (
            ('soup', 'Suppe', 0, True), ('soup', 'Suppe', 1, False),
            ('dessert', 'Dessert', 2, True), ('dessert', 'Dessert', 3, False),
        ):
            before = stored()
            name = f'{label} {"planen" if adding else "bearbeiten"} · {DAY} · {meal}'
            action = page.get_by_role('link', name=name, exact=True)
            expect(action).to_have_attribute('href', f'#course-{DAY}-{meal}-{kind}-state')
            expect(action).to_have_attribute('data-ui-tooltip', name)
            expect(action).to_have_text('')
            expect(action.locator('svg > use')).to_have_attribute(
                'href', '/static/vendor/tabler-icons/tabler-icons.svg#tabler-' + ('plus' if adding else 'edit'))
            capture(f'{kind}-{"add" if adding else "edit"}', action)
            if javascript_enabled:
                action.click()
            else:
                action.press('Enter')
            state = form.locator(f'[name="{kind}_state"]')
            expect(state).to_be_visible()
            if javascript_enabled:
                expect(state).to_be_focused()
            fields = dict(form.evaluate('form => [...new FormData(form)]'))
            assert fields['_csrf'] and fields['week'] == fields['day'] == DAY and fields['meal'] == meal
            prefixes = [('soup', before[target]['shared']['soup']),
                        ('dessert', before[target]['shared']['dessert'])]
            for option in ('MENU_1', 'VEGGIE'):
                for course_kind in ('soup', 'dessert'):
                    prefixes.append((f'{option}_{course_kind}',
                                     before[target]['exceptions'].get(option, {}).get(course_kind, {})))
            assert set(fields) == {'_csrf', 'week', 'day', 'meal'} | {
                prefix + suffix for prefix, _ in prefixes
                for suffix in ('_public_id', '_row_version', '_state', '_recipe')}
            for prefix, course in prefixes:
                assert fields[prefix + '_public_id'] == str(course.get('public_id') or '')
                assert fields[prefix + '_row_version'] == str(course.get('row_version', 0))
            state.select_option('planned')
            form.locator(f'[name="{kind}_recipe"]').select_option(recipes[index]['public_id'])
            expected = {**fields, kind + '_state': 'planned', kind + '_recipe': recipes[index]['public_id']}
            assert dict(form.evaluate('form => [...new FormData(form)]')) == expected
            expect(form).to_have_attribute('action', f'/admin/{family}/courses')
            submit = form.get_by_role('button', name='Speichern', exact=True)
            if not javascript_enabled:
                # Native disclosure scrolling must not consume the navigation budget.
                submit.click(trial=True)
            with page.expect_navigation(wait_until='domcontentloaded'), page.expect_response(
                lambda response: response.request.method == 'POST'
                and response.url == live_server + f'/admin/{family}/courses'
            ) as response:
                submit.click()
            assert response.value.status == 303
            assert response.value.headers['location'] == f'/admin/{family}?week={DAY}#course-{DAY}-{meal}'
            assert parse_qs(response.value.request.post_data, keep_blank_values=True) == {
                key: [value] for key, value in expected.items()}
            after = stored()
            assert set(after) == set(initial)
            assert {key: value for key, value in after.items() if key != target} == untouched
            saved = after[target]['shared'][kind]
            assert saved['state'] == 'planned' and saved['recipe_public_id'] == recipes[index]['public_id']
            assert saved['title'] == names[index] and saved['public_id']
            assert saved['row_version'] > before[target]['shared'][kind].get('row_version', 0)
            if not adding:
                assert saved['public_id'] == before[target]['shared'][kind]['public_id']
            other = 'dessert' if kind == 'soup' else 'soup'
            assert {key: value for key, value in after[target]['shared'][other].items() if key != 'row_version'} == {
                key: value for key, value in before[target]['shared'][other].items() if key != 'row_version'}
            assert set(after[target]['exceptions']) == {'VEGGIE'}
            for course_kind in ('soup', 'dessert'):
                assert {key: value for key, value in after[target]['exceptions']['VEGGIE'][course_kind].items()
                        if key != 'row_version'} == {
                    key: value for key, value in initial[target]['exceptions']['VEGGIE'][course_kind].items()
                    if key != 'row_version'}
            course_line = page.locator(f'[data-course="{kind}"]').filter(has=page.get_by_role(
                'link', name=f'{label} bearbeiten · {DAY} · {meal}', exact=True))
            expect(course_line).to_contain_text(f'{label}: {names[index]} · Für alle Menüs')
        assert len(posts) == 4
        # The browser retains the last issued CAS fields while another editor saves.
        edit = page.get_by_role('link', name=f'Dessert bearbeiten · {DAY} · {meal}', exact=True)
        if javascript_enabled:
            edit.click()
        else:
            edit.focus()
            expect(edit).to_be_focused()
            expect(edit).to_be_in_viewport()
            edit.press('Enter')
        if javascript_enabled and family == 'cafeteria':
            outside = _recipe(admin_engine, actor, scope.location_id, 'ZZZ Eingereichtes Dessert')
            for index in range(50):
                _recipe(admin_engine, actor, scope.location_id, f'AAA Seitenauswahl {index:02d}')
            search = editor.locator('form[method="get"]')
            search.locator('..').locator('summary').click()
            search.locator('[name="recipe_search"]').fill('ZZZ Eingereichtes Dessert')
            with page.expect_navigation(wait_until='domcontentloaded'):
                search.get_by_role('button').first.click()
            page.get_by_role('link', name=f'Dessert bearbeiten · {DAY} · {meal}', exact=True).click()
            form.locator('[name="dessert_recipe"]').select_option(outside['public_id'])
        stale_fields = dict(form.evaluate('form => [...new FormData(form)]'))
        current = stored()[target]
        persist_service_courses(
            admin_engine, scope, WEEK, DAY, meal,
            soup=current['shared']['soup'],
            dessert={'state': 'planned', 'public_id': current['shared']['dessert']['public_id'],
                     'recipe_public_id': recipes[2]['public_id']},
            soup_row_version=current['shared']['soup']['row_version'],
            dessert_row_version=current['shared']['dessert']['row_version'],
        )
        concurrent = stored()
        assert concurrent[target]['shared']['dessert']['recipe_public_id'] == recipes[2]['public_id']
        submit = form.get_by_role('button', name='Speichern', exact=True)
        if not javascript_enabled:
            submit.click(trial=True)
        with page.expect_navigation(wait_until='domcontentloaded'), page.expect_response(
            lambda response: response.request.method == 'POST'
            and response.url == live_server + f'/admin/{family}/courses'
        ) as conflict:
            submit.click()
        assert conflict.value.status == 409 and len(posts) == 5
        assert parse_qs(conflict.value.request.post_data, keep_blank_values=True) == {
            key: [value] for key, value in stale_fields.items()}
        assert stored() == concurrent
        assert dict(form.evaluate('form => [...new FormData(form)]')) == stale_fields
        assert page.goto(f'/admin/{family}?week={DAY}').status == 200
        assert len(posts) == 5
        assert stored() == concurrent
        assert {key: value for key, value in concurrent.items() if key != target} == untouched
        expect(form.locator('[name="dessert_recipe"]')).to_have_value(recipes[2]['public_id'])
        capture('persisted-after-conflict', page.get_by_role(
            'link', name=f'Dessert bearbeiten · {DAY} · {meal}', exact=True))
        (tmp_path / 'course-flow.json').write_text(json.dumps({
            'family': family, 'meal': meal, 'javascript': javascript_enabled,
            'native_statuses': [303, 303, 303, 303, 409], 'posts': len(posts),
            'neighbor_slots': [list(key) for key in untouched], 'geometry': records,
        }, indent=2) + '\n')
