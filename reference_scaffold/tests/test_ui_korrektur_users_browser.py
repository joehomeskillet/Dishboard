"""P01-P10 browser contract for user administration and access history."""
from __future__ import annotations

from pathlib import Path
from urllib.parse import parse_qs, urlsplit

import pytest
from playwright.sync_api import expect

from test_admin_local_users_browser import _context, _layout, live_accounts
from test_admin_local_users_routes import _create, admin_account
from test_auth_routes import auth_app
from test_rendered_ui import browser

__all__ = ["admin_account", "auth_app", "browser", "live_accounts"]

EVIDENCE = Path(__file__).resolve().parents[2] / ".claude/evidence/ui-korrektur-0912/users"
VIEWPORTS = (
    (1366, 768, "1366x768"),
    (1920, 1080, "1920x1080"),
    (768, 1024, "768x1024"),
    (390, 844, "390x844"),
    (720, 450, "200-percent"),
)


def _open(page, origin: str, path: str):
    response = page.goto(origin + path, wait_until="networkidle")
    assert response is not None and response.status in {200, 400, 409}
    assert response.headers["cache-control"] == "no-store"
    _layout(page)
    return response


def _screenshot(page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / name), full_page=True)


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_list_first_and_native_create_form_preserves_request_contract(
    live_accounts, browser, javascript,
):
    origin, client, _, _ = live_accounts
    cookie_name = client.application.config["SESSION_COOKIE_NAME"]
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    with browser.new_context(
        viewport={"width": 1366, "height": 768}, java_script_enabled=javascript,
    ) as context:
        context.add_cookies([{"name": cookie_name, "value": cookie.value, "url": origin}])
        page = context.new_page()
        _open(page, origin, "/admin/benutzer")

        create = page.locator("#create-local-user")
        expect(create).to_have_count(1)
        assert not create.evaluate("details => details.open")
        assert page.locator(".admin-area-tabs").count() == 1
        assert page.locator("section[aria-labelledby=users-title]").evaluate(
            "list => Boolean(list.compareDocumentPosition(document.querySelector('#create-local-user')) "
            "& Node.DOCUMENT_POSITION_FOLLOWING)",
        )
        first_row = page.locator("section[aria-labelledby=users-title] tbody tr").first
        expect(first_row).to_be_visible()
        box = first_row.bounding_box()
        assert box is not None and box["y"] + box["height"] <= 768
        expect(page.get_by_text("Kontostatus: Aktiv", exact=True).first).to_be_visible()

        create.locator("summary").click()
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
            page.get_by_role("button", name="Benutzer speichern", exact=True).click()
        request = sent.value
        assert urlsplit(request.url).path == "/admin/benutzer"
        payload = parse_qs(request.post_data or "", keep_blank_values=True)
        assert set(payload) == {
            "_csrf", "return_page", "return_status", "username", "display_name",
            "roles", "password", "password_confirm",
        }
        expect(page.get_by_role("heading", name=f"UI Vertrag {suffix}", exact=True)).to_be_visible()


def test_create_and_role_errors_open_correct_group_preserve_safe_values_and_focus(
    live_accounts, browser,
):
    origin, client, _, issuer = live_accounts
    target = _create(issuer, "ui.error.target")
    with _context(browser, origin, client, 390) as context:
        page = context.new_page()
        page.set_viewport_size({"width": 390, "height": 844})
        _open(page, origin, "/admin/benutzer/neu")
        expect(page.locator("#create-local-user")).to_have_attribute("open", "")
        page.get_by_label("Benutzername", exact=True).fill("ui.error.create")
        page.get_by_label("Anzeigename", exact=True).fill("Erhaltener Anzeigename")
        page.get_by_label("Neues Passwort", exact=True).fill("Valide!Wolken77Kette")
        page.get_by_label("Neues Passwort bestätigen", exact=True).fill("Frische!Sterne92Tanne")
        with page.expect_navigation() as navigation:
            page.get_by_role("button", name="Benutzer speichern", exact=True).click()
        assert navigation.value.status == 400
        assert page.locator("#create-local-user").evaluate("details => details.open")
        expect(page.locator(".error-region")).to_be_focused()
        expect(page.get_by_label("Benutzername", exact=True)).to_have_value("ui.error.create")
        expect(page.get_by_label("Anzeigename", exact=True)).to_have_value("Erhaltener Anzeigename")
        assert page.locator("input[type=password]").evaluate_all(
            "els => els.every(el => el.value === '')",
        )
        _screenshot(page, "local-user-create-error-390x844.png")

        _open(page, origin, f"/admin/benutzer/{target.public_id}")
        expect(page.get_by_text("Nicht vorübergehend gesperrt", exact=True)).to_be_visible()
        expect(page.get_by_text("Letzte lokale Passwortprüfung", exact=True)).to_be_visible()
        for selector in ("#roles-action", "#password-action", "#state-action"):
            expect(page.locator(selector)).to_have_count(1)
        page.locator("#roles-action summary").click()
        for checkbox in page.locator('#roles-action input[name="roles"]').all():
            checkbox.uncheck()
        page.get_by_label("Rollenänderung für ui.error.target bestätigen", exact=True).check()
        with page.expect_navigation() as navigation:
            page.get_by_role("button", name="Benutzer speichern", exact=True).click()
        assert navigation.value.status == 400
        assert page.locator("#roles-action").evaluate("details => details.open")
        assert not page.locator("#password-action").evaluate("details => details.open")
        expect(page.locator(".error-region")).to_be_focused()
        assert page.locator('#roles-action input[name="roles"]:checked').count() == 0
        _screenshot(page, "local-user-roles-error-390x844.png")


@pytest.mark.parametrize("javascript", [True, False], ids=["js", "nojs"])
def test_security_action_requests_keep_targets_and_fields(live_accounts, browser, javascript):
    origin, client, _, issuer = live_accounts
    target = _create(issuer, f"ui.actions.{'js' if javascript else 'nojs'}")
    cookie_name = client.application.config["SESSION_COOKIE_NAME"]
    cookie = client.get_cookie(cookie_name)
    assert cookie is not None
    with browser.new_context(
        viewport={"width": 768, "height": 1024}, java_script_enabled=javascript,
    ) as context:
        context.add_cookies([{"name": cookie_name, "value": cookie.value, "url": origin}])
        page = context.new_page()
        cases = (
            ("#roles-action", "Benutzer speichern", "rollen", {"roles"}),
            (
                "#password-action", "Passwort zurücksetzen", "passwort",
                {"password", "password_confirm"},
            ),
            ("#state-action", "Konto deaktivieren", "deaktivieren", set()),
        )
        for selector, button, action, extra_fields in cases:
            _open(page, origin, f"/admin/benutzer/{target.public_id}")
            details = page.locator(selector)
            details.locator("summary").click()
            if action == "passwort":
                page.get_by_label("Neues Passwort", exact=True).fill("Valide!Wolken77Kette")
                page.get_by_label("Neues Passwort bestätigen", exact=True).fill("Valide!Wolken77Kette")
            details.get_by_label("bestätigen", exact=False).check()
            with page.expect_request(lambda request: request.method == "POST") as sent:
                details.get_by_role("button", name=button, exact=True).click()
            request = sent.value
            assert urlsplit(request.url).path == f"/admin/benutzer/{target.public_id}/{action}"
            payload = parse_qs(request.post_data or "", keep_blank_values=True)
            assert set(payload) == {
                "_csrf", "return_page", "return_status", "target_version", "confirm",
            } | extra_fields
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
                ("local-user-events", "/admin/benutzer/protokoll"),
                ("access-history", "/admin/benutzer/zugriffsverlauf"),
            ):
                _open(page, origin, path)
                _screenshot(page, f"{name}-regular-{label}.png")
