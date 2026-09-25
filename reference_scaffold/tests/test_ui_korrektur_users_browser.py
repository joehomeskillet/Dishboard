"""M18–M20 account density, native forms and unchanged security boundaries."""
from __future__ import annotations

import base64
import json
import re
import struct
from pathlib import Path
from tempfile import TemporaryDirectory, gettempdir
from urllib.parse import parse_qs, urljoin, urlsplit
from xml.etree import ElementTree

import pytest
from playwright.sync_api import expect, sync_playwright
from sqlalchemy import text
from sqlalchemy.exc import OperationalError

from cafeteria.auth import local_users as users
from test_access_history_reads import _seed_history
from test_admin_local_users_browser import _context, _layout, live_accounts
from test_admin_local_users_routes import _create, admin_account
from test_auth_routes import ACTOR_IDENTIFIER, auth_app

__all__ = ["admin_account", "auth_app", "browser", "live_accounts"]

EVIDENCE = Path(gettempdir()) / "uiux-wp19-0920-evidence"
CSS_PATH = Path(__file__).resolve().parents[1] / "cafeteria/static/admin-settings-benutzer.css"
VIEWPORTS = (
    (1440, 900, "1440x900"),
    (1024, 768, "1024x768"),
    (1920, 1080, "1920x1080"),
    (768, 1024, "768x1024"),
    (390, 844, "390x844"),
    (2560, 1440, "2560x1440"),
    (320, 844, "320-reflow"),
)


def test_user_settings_css_keeps_shared_list_tokens() -> None:
    css = CSS_PATH.read_text(encoding="utf-8")
    assert "#e6e7e9" not in css
    assert "calc(var(--app-list-pad-y) - 3px)" not in css
    assert "padding-block: 0" not in css


@pytest.fixture(scope="session")
def browser():
    with sync_playwright() as playwright:
        instance = playwright.chromium.launch(
            headless=True, args=['--no-sandbox', '--disable-dev-shm-usage'],
        )
        yield instance
        instance.close()


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_wp19_measured_page_frame(live_accounts, browser, javascript):
    origin, client, _, issuer = live_accounts
    target = _create(issuer, 'ui.measure.target')
    measurements = []
    evidence = EVIDENCE / ('js' if javascript else 'nojs')
    evidence.mkdir(parents=True, exist_ok=True)
    with _context(browser, origin, client, javascript=javascript) as context:
        page = context.new_page()
        for width in (360, 768, 1024, 1440):
            page.set_viewport_size({'width': width, 'height': 900})
            for name, path in (
                ('list', '/admin/benutzer'),
                ('detail', f'/admin/benutzer/{target.public_id}'),
                ('create', '/admin/benutzer/neu'),
                ('events', '/admin/benutzer/protokoll'),
                ('history', '/admin/benutzer/zugriffsverlauf'),
            ):
                _open(page, origin, path)
                page.screenshot(path=str(evidence / f'{name}-{width}.png'), full_page=True)
                metric = page.evaluate('''() => ({
                    width: innerWidth, height: document.documentElement.scrollHeight,
                    overflow: document.documentElement.scrollWidth > innerWidth,
                    primary: document.querySelectorAll('main .btn-primary').length,
                    hints: [...document.querySelectorAll('main .form-hint')].filter(el => el.checkVisibility()).length,
                    open: document.querySelectorAll('main details[open]').length,
                    row: document.querySelector('[data-account-row], tbody tr')?.getBoundingClientRect().height ?? null,
                    contentHeight: document.querySelector('main').getBoundingClientRect().height,
                })''')
                assert not metric['overflow'], metric
                assert metric['primary'] == 1, metric
                if name in ('detail', 'events', 'history'):
                    expect(page.locator('main .btn-primary:visible')).to_have_count(1)
                    expect(page.locator('table.table-mobile-lg')).to_have_count(0)
                    for table in page.locator('table.admin-table--stack').all():
                        expect(table.locator('tbody td:not([data-label])')).to_have_count(0)
                        assert table.locator('tbody tr').first.evaluate(
                            'el => getComputedStyle(el).display'
                        ) == ('grid' if width < 768 else 'table-row')
                    if name in ('detail', 'events'):
                        help_trigger = page.locator('.admin-hint > summary')
                        help_trigger.focus()
                        expect(help_trigger).to_be_focused()
                        help_trigger.press('Enter')
                        expect(page.locator('.admin-hint .form-hint')).to_be_visible()
                        help_trigger.press('Enter')
                        expect(page.locator('.admin-hint .form-hint')).to_be_hidden()
                    else:
                        scope = page.get_by_text('Geltungsbereich', exact=True)
                        scope.focus()
                        scope.press('Enter')
                        expect(page.get_by_text('Zeitangaben: Schweiz.', exact=False)).to_be_visible()
                        scope.press('Enter')
                if name == 'detail':
                    expect(page.locator('.admin-statusbar')).to_be_visible()
                    assert 'authz_version' not in page.locator('.admin-statusbar').inner_text()
                    expect(page.locator('.admin-statusbar')).to_contain_text('Aktiv')
                    expect(page.locator('.admin-statusbar')).to_contain_text('Editor')
                    expect(page.locator('.admin-statusbar')).to_contain_text('Nicht vorübergehend gesperrt')
                    primary = page.locator('main .btn-primary')
                    assert primary.evaluate('el => getComputedStyle(el).backgroundColor') != page.locator('main .btn').first.evaluate('el => getComputedStyle(el).backgroundColor')
                if name == 'list':
                    assert metric['row'] <= (144 if width < 1024 else 96), metric
                if name == 'events' and width < 1024:
                    assert metric['row'] < 200, metric
                measurements.append(dict(page=name, javascript=javascript, **metric))
                first = page.locator('main a.btn:visible, main button:visible, main summary:visible').first
                first.focus()
                expect(first).to_be_focused()
                assert first.evaluate('el => getComputedStyle(el).outlineStyle !== "none"')
        (evidence / 'wp19-metrics.json').write_text(json.dumps(measurements, indent=2))
        print('WP19_METRICS', json.dumps(measurements), 'EVIDENCE', evidence)


def _open(page, origin: str, path: str):
    response = page.goto(origin + path, wait_until="networkidle")
    assert response is not None and response.status in {200, 400, 409}
    assert response.headers["cache-control"] == "no-store"
    _layout(page)
    assert page.locator('main summary:visible').evaluate_all(
        'els => els.every(el => el.getBoundingClientRect().height >= 47.5)',
    )
    return response


def _screenshot(page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / name), full_page=True)
    metrics = page.evaluate("""() => {
        const main = document.querySelector('main');
        const first = main.querySelector('[data-account-row], tbody tr, input:not([type=hidden]), details');
        return {viewport: [innerWidth, innerHeight], pageHeight: document.documentElement.scrollHeight,
            mainWidth: main.getBoundingClientRect().width,
            firstWorkY: first ? first.getBoundingClientRect().top : null,
            rowHeights: [...main.querySelectorAll('[data-account-row], tbody tr')].map(el => el.getBoundingClientRect().height),
            font: getComputedStyle(main).fontFamily};
    }""")
    (EVIDENCE / name.replace('.png', '.json')).write_text(json.dumps(metrics, indent=2))


def _icons_and_focus(page):
    sprite = page.request.get(urljoin(page.url, '/static/vendor/tabler-icons/tabler-icons.svg'))
    assert sprite.status == 200
    symbols = {node.get('id') for node in ElementTree.fromstring(sprite.body()).iter()}
    icons = page.locator('main svg.icon:visible').evaluate_all('''icons => icons.map(icon => {
        const box = icon.getBBox();
        const rendered = icon.getBoundingClientRect();
        return {id: icon.querySelector('use').getAttribute('href').split('#')[1],
            width: box.width, height: box.height, renderedWidth: rendered.width};
    })''')
    assert icons and all(item['id'] in symbols and item['width'] > 0 and item['height'] > 0 for item in icons)
    assert all(item['renderedWidth'] >= 16 for item in icons), icons
    for control in page.locator('main .btn-icon:visible').all():
        assert control.get_attribute('aria-label') and control.get_attribute('title')
        box = control.bounding_box()
        assert box and box['width'] >= 48 and box['height'] >= 48
        control.focus()
        expect(control).to_be_focused()
        assert control.evaluate('el => getComputedStyle(el).outlineStyle !== "none"')
    page.evaluate('scrollTo(0, 0)')
    return icons


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_list_first_and_native_create_form_preserves_request_contract(
    live_accounts, browser, javascript,
):
    origin, client, _, issuer = live_accounts
    _create(issuer, f"ui.list.{'js' if javascript else 'nojs'}")
    cookie_name = client.application.config["SESSION_COOKIE_NAME"]
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    with browser.new_context(
        viewport={"width": 1440, "height": 900}, java_script_enabled=javascript,
    ) as context:
        context.add_cookies([{"name": cookie_name, "value": cookie.value, "url": origin}])
        page = context.new_page()
        _open(page, origin, "/admin/benutzer")

        expect(page.locator("#create-local-user")).to_have_count(0)
        assert page.locator(".admin-area-tabs").count() == 0
        expect(page.locator('.admin-statusbar')).to_have_count(0)
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('main .btn-primary')).to_have_attribute('href', '/admin/benutzer/neu?page=1&status=all')
        first_row = page.locator("[data-account-row]").first
        expect(first_row).to_be_visible()
        box = first_row.bounding_box()
        assert box is not None and box["y"] + box["height"] <= 900
        assert box["height"] <= 96
        expect(first_row.get_by_text("Aktiv", exact=True)).to_be_visible()
        edit = first_row.locator('a[data-semantic="actions.edit"]')
        expect(edit).to_have_attribute('aria-label', re.compile(r'Konto ui\.list\.(js|nojs) bearbeiten'))
        expect(edit).to_have_attribute('title', re.compile(r'Konto ui\.list\.(js|nojs) bearbeiten'))
        expect(edit.locator('svg.icon')).to_have_count(1)
        metrics = first_row.locator('.admin-list-row').evaluate('''el => {
            const host = document.querySelector('.dishboard-admin');
            const probe = document.createElement('div');
            probe.style.minHeight = 'var(--app-list-row-min-height)';
            probe.style.paddingTop = 'var(--app-list-pad-y)';
            host.appendChild(probe);
            const token = getComputedStyle(probe);
            const cs = getComputedStyle(el);
            const result = {minHeight: cs.minHeight, tokenMin: token.minHeight,
                            paddingTop: cs.paddingTop, tokenPad: token.paddingTop};
            probe.remove();
            return result;
        }''')
        assert metrics['minHeight'] == metrics['tokenMin'], metrics
        assert metrics['paddingTop'] == metrics['tokenPad'], metrics
        page.locator('details.admin-compact-details > summary').filter(
            has_text='Weitere Optionen'
        ).click()
        history_nav = page.get_by_role('navigation', name='Kontoverlauf')
        expect(history_nav.get_by_role('link', name='Kontoereignisse', exact=True)).to_be_visible()
        expect(history_nav.get_by_role('link', name='Zugriffsverlauf', exact=True)).to_be_visible()
        info = first_row.locator('summary')
        info.focus()
        page.keyboard.press('Enter')
        expect(first_row.get_by_text('Keine vorübergehende Anmeldesperre', exact=True)).to_be_visible()
        page.keyboard.press('Enter')
        assert not first_row.locator('details').evaluate('el => el.open')

        page.get_by_role('link', name='Anlegen', exact=True).click()
        create = page.locator("#create-local-user")
        expect(create).to_have_attribute('open', '')
        form = create.locator("form")
        assert urlsplit(form.get_attribute("action") or "").path == "/admin/benutzer"
        assert form.get_attribute("method").lower() == "post"
        assert sorted(form.locator("[name]").evaluate_all(
            "els => els.map(el => el.name)",
        )) == sorted([
            "_csrf", "return_page", "return_status", "username", "display_name",
            "roles", "roles", "roles", "password", "password_confirm",
        ])

        suffix = "js" if javascript else "nojs"
        page.get_by_label("Benutzername", exact=True).fill(f"ui.contract.{suffix}")
        page.get_by_label("Anzeigename", exact=True).fill(f"UI Vertrag {suffix}")
        page.get_by_label("Neues Passwort", exact=True).fill("Valide!Wolken77Kette")
        page.get_by_label("Neues Passwort bestätigen", exact=True).fill("Valide!Wolken77Kette")
        with page.expect_request(lambda request: request.method == "POST") as sent:
            page.get_by_role("button", name="Speichern", exact=True).click()
        request = sent.value
        assert urlsplit(request.url).path == "/admin/benutzer"
        payload = parse_qs(request.post_data or "", keep_blank_values=True)
        assert set(payload) == {
            "_csrf", "return_page", "return_status", "username", "display_name",
            "roles", "password", "password_confirm",
        }
        assert payload['roles'] == ['Cafeteria.Editor']
        assert payload['return_page'] == ['1'] and payload['return_status'] == ['all']
        assert payload['username'] == [f'ui.contract.{suffix}']
        assert payload['display_name'] == [f'UI Vertrag {suffix}']
        assert payload['password'] == payload['password_confirm'] == ['Valide!Wolken77Kette']
        expect(page.locator('.page-header-subtitle')).to_contain_text(f"UI Vertrag {suffix}")


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_create_and_role_errors_open_correct_group_preserve_safe_values_and_focus(
    live_accounts, browser, javascript,
):
    origin, client, _, issuer = live_accounts
    target = _create(issuer, "ui.error.target")
    with _context(browser, origin, client, 390, javascript) as context:
        page = context.new_page()
        page.set_viewport_size({"width": 390, "height": 844})
        _open(page, origin, "/admin/benutzer/neu")
        expect(page.locator("#create-local-user")).to_have_attribute("open", "")
        page.get_by_label("Benutzername", exact=True).fill("ui.error.create")
        page.get_by_label("Anzeigename", exact=True).fill("Erhaltener Anzeigename")
        page.get_by_label("Neues Passwort", exact=True).fill("Valide!Wolken77Kette")
        page.get_by_label("Neues Passwort bestätigen", exact=True).fill("Frische!Sterne92Tanne")
        with page.expect_navigation() as navigation:
            page.get_by_role("button", name="Speichern", exact=True).click()
        assert navigation.value.status == 400
        assert page.locator("#create-local-user").evaluate("details => details.open")
        expect(page.locator(".error-region")).to_be_focused()
        expect(page.get_by_label("Benutzername", exact=True)).to_have_value("ui.error.create")
        expect(page.get_by_label("Anzeigename", exact=True)).to_have_value("Erhaltener Anzeigename")
        assert page.locator("input[type=password]").evaluate_all(
            "els => els.every(el => el.value === '')",
        )
        _screenshot(page, f"local-user-create-error-390x844-{javascript}.png")

        _open(page, origin, f"/admin/benutzer/{target.public_id}")
        page.locator('#account-login-details summary').click()
        expect(page.locator('#account-login-details').get_by_text("Nicht vorübergehend gesperrt", exact=True)).to_be_visible()
        expect(page.get_by_text("Letzte lokale Passwortprüfung", exact=True)).to_be_visible()
        page.locator('#account-login-details summary').click()
        for selector in ("#roles-action", "#password-action", "#state-action"):
            expect(page.locator(selector)).to_have_count(1)
        page.locator("#roles-action summary").click()
        for checkbox in page.locator('#roles-action input[name="roles"]').all():
            checkbox.uncheck()
        page.get_by_label("Rollenänderung für ui.error.target bestätigen", exact=True).check()
        with page.expect_navigation() as navigation:
            page.get_by_role("button", name="Speichern", exact=True).click()
        assert navigation.value.status == 400
        assert page.locator("#roles-action").evaluate("details => details.open")
        assert not page.locator("#password-action").evaluate("details => details.open")
        expect(page.locator(".error-region")).to_be_focused()
        assert page.locator('#roles-action input[name="roles"]:checked').count() == 0
        _icons_and_focus(page)
        _screenshot(page, f"local-user-roles-error-390x844-{javascript}.png")
        page.locator('#roles-action summary').click()
        expect(page.locator('#roles-action summary')).to_contain_text('Fehler')
        assert page.locator('#roles-action input[name="roles"]:checked').count() == 0


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_security_action_requests_keep_targets_and_fields(live_accounts, browser, javascript):
    origin, client, _, issuer = live_accounts
    target = _create(issuer, f"ui.actions.{'js' if javascript else 'nojs'}")
    cookie_name = client.application.config["SESSION_COOKIE_NAME"]
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    with browser.new_context(
        viewport={"width": 390, "height": 844}, java_script_enabled=javascript,
    ) as context:
        context.add_cookies([{"name": cookie_name, "value": cookie.value, "url": origin}])
        page = context.new_page()
        cases = (
            ("#roles-action", "Speichern", "rollen", {"roles"}),
            (
                "#password-action", "Passwort zurücksetzen", "passwort",
                {"password", "password_confirm"},
            ),
            ("#state-action", "Konto deaktivieren", "deaktivieren", set()),
            ("#state-action", "Konto reaktivieren", "aktivieren", set()),
        )
        for selector, button, action, extra_fields in cases:
            _open(page, origin, f"/admin/benutzer/{target.public_id}")
            expect(page.locator('main .btn-primary')).to_have_count(1)
            if action == 'aktivieren':
                expect(page.locator('.admin-statusbar')).to_contain_text('Deaktiviert')
            details = page.locator(selector)
            details.locator("summary").click()
            original = details.locator('input[type=hidden]').evaluate_all('els => els.map(el => [el.name, el.value])')
            if action == "passwort":
                page.get_by_label("Neues Passwort", exact=True).fill("Valide!Wolken77Kette")
                page.get_by_label("Neues Passwort bestätigen", exact=True).fill("Valide!Wolken77Kette")
            confirmation = details.locator('input[name="confirm"]')
            expect(confirmation).to_have_count(1)
            submit = details.get_by_role("button", name=button, exact=True)
            if action == "passwort":
                expect(submit).to_have_attribute("data-semantic", "actions.refresh")
                expect(submit).to_have_attribute("title", "Passwort zurücksetzen")
                expect(submit.locator("span")).to_have_text("Zurücksetzen")
                expect(submit).to_have_class(re.compile(r"\bbtn-danger\b"))
                expect(details.locator('[data-semantic="view.reset"]')).to_have_count(0)
            elif action == "deaktivieren":
                expect(submit).to_have_attribute("data-semantic", "status.locked")
                expect(submit).to_have_attribute("title", "Konto deaktivieren")
                expect(submit.locator("span")).to_have_text("Deaktivieren")
                expect(submit).to_have_class(re.compile(r"\bbtn-danger\b"))
                expect(details.locator('[data-semantic="actions.archive"]')).to_have_count(0)
                expect(details.get_by_role("button", name="Archivieren", exact=True)).to_have_count(0)
            elif action == "aktivieren":
                expect(submit).to_have_attribute("data-semantic", "actions.activate")
                expect(submit).to_have_attribute("title", "Konto reaktivieren")
                expect(submit.locator("span")).to_have_text("Reaktivieren")
                expect(details.locator('[data-semantic="actions.restore"]')).to_have_count(0)
                expect(details.get_by_role("button", name="Wiederherstellen", exact=True)).to_have_count(0)
            # Required confirmation remains a native browser boundary.
            submit.click()
            expect(confirmation).to_be_focused()
            confirmation.check()
            details.locator('summary').click()
            details.locator('summary').click()
            expect(confirmation).to_be_checked()
            assert details.locator('input[type=hidden]').evaluate_all('els => els.map(el => [el.name, el.value])') == original
            with page.expect_request(lambda request: request.method == "POST") as sent:
                details.get_by_role("button", name=button, exact=True).click()
            request = sent.value
            assert urlsplit(request.url).path == f"/admin/benutzer/{target.public_id}/{action}"
            payload = parse_qs(request.post_data or "", keep_blank_values=True)
            assert set(payload) == {
                "_csrf", "return_page", "return_status", "target_version", "confirm",
            } | extra_fields
            assert payload['confirm'] == ['yes']
            for name, value in original:
                assert payload[name] == [value]
            if action == "rollen":
                assert payload["roles"] == ["Cafeteria.Editor"]


def test_user_and_access_pages_fit_required_viewports(live_accounts, browser):
    origin, client, _, issuer = live_accounts
    target = _create(issuer, "ui.viewport.target")
    with _context(browser, origin, client) as context:
        page = context.new_page()
        for width, height, label in VIEWPORTS:
            page.set_viewport_size({"width": width, "height": height})
            for name, path in (
                ("local-users", "/admin/benutzer"),
                ("local-user", f"/admin/benutzer/{target.public_id}"),
                ("local-user-create", "/admin/benutzer/neu"),
                ("local-user-events", "/admin/benutzer/protokoll"),
                ("access-history", "/admin/benutzer/zugriffsverlauf"),
            ):
                _open(page, origin, path)
                icons = _icons_and_focus(page)
                _screenshot(page, f"{name}-regular-{label}.png")
                (EVIDENCE / f'{name}-{label}-icons.json').write_text(json.dumps(icons, indent=2))


@pytest.mark.parametrize('javascript', [True, False], ids=['js', 'nojs'])
def test_stale_roles_reopen_original_choice_without_silent_write(live_accounts, browser, javascript):
    origin, client, owner, issuer = live_accounts
    target = _create(issuer, 'ui.conflict.target')
    with _context(browser, origin, client, 390, javascript) as context:
        page = context.new_page()
        _open(page, origin, f'/admin/benutzer/{target.public_id}?page=2&status=active')
        command = users.load_local_command_context(
            issuer, actor_identifier=ACTOR_IDENTIFIER, target_username='ui.conflict.target',
        )
        newer = users.replace_local_roles(
            issuer, actor=command.actor, target=command.target, roles=('Cafeteria.Publisher',),
        )
        details = page.locator('#roles-action')
        details.locator('summary').click()
        page.get_by_label('Editor · Menüs bearbeiten', exact=True).uncheck()
        page.get_by_label('Admin · Benutzer und Einstellungen verwalten', exact=True).check()
        details.locator('input[name=confirm]').check()
        csrf = details.locator('input[name=_csrf]').input_value()
        with page.expect_navigation() as navigation:
            details.get_by_role('button', name='Speichern', exact=True).click()
        assert navigation.value.status == 409
        assert details.evaluate('el => el.open')
        expect(page.locator('.error-region')).to_be_focused()
        expect(details.locator('input[name=_csrf]')).to_have_value(csrf)
        expect(details.locator('input[name=return_page]')).to_have_value('2')
        expect(details.locator('input[name=return_status]')).to_have_value('active')
        expect(details.locator('input[name=target_version]')).to_have_value(str(newer.authz_version))
        expect(page.get_by_label('Admin · Benutzer und Einstellungen verwalten', exact=True)).to_be_checked()
        expect(details.locator('input[name=confirm]')).not_to_be_checked()
        with owner.connect() as connection:
            current = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE public_id=:id'),
                                         {'id': target.public_id}).scalar_one()
        assert current == newer.authz_version
        _layout(page)
        _screenshot(page, f'local-user-conflict-390-{javascript}.png')


@pytest.mark.parametrize('width,javascript', [(1440, True), (390, False)])
def test_empty_filtered_history_readonly_and_unavailable_are_distinct(
    live_accounts, browser, monkeypatch, width, javascript,
):
    origin, client, _, issuer = live_accounts
    app = client.application
    with _context(browser, origin, client, width, javascript) as context:
        page = context.new_page()
        _open(page, origin, '/admin/benutzer')
        expect(page.get_by_text('Noch keine lokalen Konten angelegt.', exact=True)).to_be_visible()
        expect(page.locator('main .btn-primary')).to_have_count(1)
        expect(page.locator('[data-empty-kind] .btn-primary')).to_have_count(0)
        expect(page.locator('[data-empty-kind] a[data-semantic="actions.add"]')).to_be_visible()
        _screenshot(page, f'local-users-empty-{width}-{javascript}.png')
        _open(page, origin, '/admin/benutzer/protokoll')
        expect(page.locator('[data-empty-kind]')).to_contain_text('Noch keine Kontoereignisse')
        _open(page, origin, '/admin/benutzer')
        target = _create(issuer, 'ui.states.target')
        page.get_by_label('Kontostatus', exact=True).select_option('disabled')
        page.get_by_role('button', name='Filtern', exact=True).click()
        expect(page.get_by_text('Keine lokalen Konten in dieser Auswahl.', exact=True)).to_be_visible()
        expect(page.get_by_label('Kontostatus', exact=True)).to_have_value('disabled')
        page.get_by_role('link', name='Zurücksetzen', exact=True).first.click()
        expect(page.locator('[data-account-row]')).to_have_count(1)
        _open(page, origin, '/admin/benutzer/zugriffsverlauf')
        expect(page.get_by_text('Noch keine Zugriffsereignisse erfasst.', exact=True)).to_be_visible()
        page.get_by_label('Zugang', exact=True).select_option('entra')
        page.get_by_role('button', name='Filtern', exact=True).click()
        expect(page.get_by_text('Keine Zugriffsereignisse in dieser Auswahl.', exact=True)).to_be_visible()
        expect(page.get_by_label('Zugang', exact=True)).to_have_value('entra')
        _screenshot(page, f'access-history-filter-empty-{width}-{javascript}.png')
        page.get_by_role('link', name='Zurücksetzen', exact=True).click()
        expect(page.get_by_label('Zugang', exact=True)).to_have_value('all')

        app.extensions['cafeteria_auth_issuer_db'] = None
        for name, path in [('local-users', '/admin/benutzer'), ('create', '/admin/benutzer/neu'),
                           ('detail', f'/admin/benutzer/{target.public_id}')]:
            _open(page, origin, path)
            expect(page.get_by_role('status')).to_contain_text('Die Konten bleiben lesbar')
            expect(page.locator('main .btn-primary')).to_have_count(1)
            if name in ('local-users', 'create'):
                expect(page.locator('.admin-statusbar')).to_contain_text('Nur lesen')
            for summary in page.locator('details > summary').all():
                summary.click()
            for submit in page.locator('main form[method=post] button[type=submit]').all():
                expect(submit).to_be_disabled()
            _layout(page)
            _screenshot(page, f'{name}-readonly-{width}-{javascript}.png')

        def unavailable(*_args, **_kwargs):
            raise OperationalError('SYNTHETIC-PRIVATE-ERROR', {}, None)

        monkeypatch.setattr('cafeteria.roles.load_user_authorization', unavailable)
        response = page.goto(origin + '/admin/benutzer', wait_until='networkidle')
        assert response.status == 503 and response.headers['cache-control'] == 'no-store'
        expect(page.get_by_role('heading', name='Benutzerverwaltung nicht verfügbar')).to_be_visible()
        assert 'SYNTHETIC-PRIVATE-ERROR' not in page.content()
        assert page.locator('[data-account-row]').count() == 0
        assert 'Noch keine lokalen Konten' not in page.locator('main').inner_text()
        _layout(page)
        _icons_and_focus(page)
        _screenshot(page, f'local-user-unavailable-{width}-{javascript}.png')
        post = page.request.post(origin + '/admin/benutzer', form={})
        assert post.status == 503
        assert 'Der Abschluss der Kontoaktion konnte nicht bestätigt werden.' in post.text()


@pytest.mark.parametrize('width,javascript', [(1440, True), (360, False)])
def test_history_rows_and_native_filters_keep_scope_and_pagination(live_accounts, browser, width, javascript):
    origin, client, owner, _ = live_accounts
    _seed_history(owner, 56)
    with _context(browser, origin, client, width, javascript) as context:
        page = context.new_page()
        _open(page, origin, '/admin/benutzer/zugriffsverlauf')
        expect(page.locator('tbody tr')).to_have_count(50)
        expect(page.locator('main .btn-primary:visible')).to_have_count(1)
        expect(page.locator('tbody td:not([data-label])')).to_have_count(0)
        assert page.locator('tbody tr').first.evaluate(
            'el => getComputedStyle(el).display'
        ) == ('grid' if width < 768 else 'table-row')
        assert page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1')
        _screenshot(page, f'access-history-populated-{width}-{javascript}.png')
        page.get_by_label('Zugang', exact=True).focus()
        page.keyboard.press('Tab')
        expect(page.get_by_label('Ereignis', exact=True)).to_be_focused()
        page.get_by_label('Zugang', exact=True).select_option('entra')
        page.get_by_label('Ereignis', exact=True).select_option('auth.login.accepted')
        page.get_by_role('button', name='Filtern', exact=True).click()
        assert parse_qs(urlsplit(page.url).query) == {'provider': ['entra'], 'action': ['auth.login.accepted']}
        expect(page.locator('tbody tr')).to_have_count(9)
        page.get_by_role('link', name='Zurücksetzen', exact=True).click()
        page.get_by_role('navigation', name='Zugriffsereignisseiten').get_by_role('link', name='Weiter').click()
        expect(page.locator('tbody tr')).to_have_count(6)
        page.get_by_text('Geltungsbereich', exact=True).click()
        expect(page.get_by_text('Zeitangaben: Schweiz.', exact=False)).to_be_visible()
        _layout(page)


def test_roles_and_sessions_cannot_turn_denial_into_empty_state(live_accounts, browser):
    origin, client, owner, issuer = live_accounts
    target = _create(issuer, 'ui.denied.target')
    paths = ['/admin/benutzer', '/admin/benutzer/neu', '/admin/benutzer/protokoll',
             '/admin/benutzer/zugriffsverlauf', f'/admin/benutzer/{target.public_id}']
    with browser.new_context(viewport={'width': 390, 'height': 844}) as anonymous:
        page = anonymous.new_page()
        for path in paths:
            response = page.goto(origin + path)
            assert response.status == 401 and response.headers['cache-control'] == 'no-store'
            assert page.locator('[data-account-row], #create-local-user').count() == 0
    with client.session_transaction() as state:
        actor = state['user']['id']
    with owner.begin() as connection:
        connection.execute(text("UPDATE cafeteria.user_role_cache SET role_code='Cafeteria.Publisher' WHERE user_id=:id"),
                           {'id': actor})
        version = connection.execute(text('SELECT authz_version FROM cafeteria.users WHERE id=:id'),
                                     {'id': actor}).scalar_one()
    with client.session_transaction() as state:
        state['authz_version'] = version
    with _context(browser, origin, client, 390) as context:
        page = context.new_page()
        for path in paths:
            response = page.goto(origin + path)
            assert response.status == 403 and response.headers['cache-control'] == 'no-store'
            assert page.locator('[data-account-row], #create-local-user').count() == 0


def test_account_pages_use_real_browser_zoom_200(live_accounts, browser, tmp_path):
    origin, client, _, issuer = live_accounts
    target = _create(issuer, 'ui.zoom.target')
    cookie = client.get_cookie(client.application.config['SESSION_COOKIE_NAME'])
    assert cookie is not None
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='users-chrome-zoom-', dir=tmp_path) as profile:
        with browser.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            context.add_cookies([{'name': cookie.key, 'value': cookie.value, 'url': origin}])
            cdp = context.new_cdp_session(page)
            for name, path in [('list', '/admin/benutzer'), ('create', '/admin/benutzer/neu'),
                               ('detail', f'/admin/benutzer/{target.public_id}'),
                               ('events', '/admin/benutzer/protokoll'),
                               ('history', '/admin/benutzer/zugriffsverlauf')]:
                _open(page, origin, path)
                layout = cdp.send('Page.getLayoutMetrics')
                assert layout['cssVisualViewport']['zoom'] == 2
                assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
                assert page.locator('html').evaluate('el => getComputedStyle(el).zoom') == '1'
                _icons_and_focus(page)
                png = base64.b64decode(cdp.send('Page.captureScreenshot',
                                      {'format': 'png', 'captureBeyondViewport': False})['data'])
                pixels = struct.unpack('>II', png[16:24])
                assert pixels[0] == 1440 and pixels[1] >= 800
                layout.update(capture_kind='native CDP viewport, not full page', capture_pixels=pixels)
                (EVIDENCE / f'{name}-real-zoom-200.png').write_bytes(png)
                (EVIDENCE / f'{name}-real-zoom-200.json').write_text(json.dumps(layout, indent=2))
            cdp.detach()
