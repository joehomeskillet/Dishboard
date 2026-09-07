#!/usr/bin/env python3
"""Read-only OPS proof; use --outdir NEW_DIRECTORY --base-url HTTP(S)_ORIGIN.

Only local login may POST. Exit 0 means checks passed, 1 means failure.
Evidence contains boolean checks and authenticated screenshots, never page HTML.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from dataclasses import asdict, dataclass, field
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

from playwright.sync_api import Browser, ConsoleMessage, Response, Route, sync_playwright

from admin_tabler_proof import audit_tabler
from capture_admin_live_proof import LAYOUT_AUDIT, USER, VIEWPORTS, _admin_url, _password

OPS_PATH = '/admin/bereiche-zeiten'
OPS_AUDIT = """() => {
    const one = selector => document.querySelectorAll(selector).length === 1;
    const result = {
        names: ['staff_guest', 'patient'].every(profile =>
            one(`#name-${profile} input[name="name_${profile}"]`) &&
            one(`#name-${profile} input[name="expected_${profile}"]`)),
        weekend_switch: one('#weekend-form .form-switch input#allows_weekend[type="checkbox"]'),
        exception_loader: ['profile', 'date', 'meal'].every(name =>
            one(`#exception-load [name="${name}"]`)),
        exceptions_section: [...document.querySelectorAll('h2')].some(element =>
            element.textContent.trim() === 'Gespeicherte Ausnahmen'),
        active_navigation: one('a[href="/admin/bereiche-zeiten"][aria-current="page"]')
    };
    for (const profile of ['staff_guest', 'patient']) {
        const form = document.querySelector(`#schedule-${profile}`);
        const meals = profile === 'patient' ? ['LUNCH', 'DINNER'] : ['LUNCH'];
        result[`${profile}_seven_days`] = !!form &&
            form.querySelectorAll('tbody tr').length === 7 * meals.length;
        result[`${profile}_native_times`] = !!form && [1,2,3,4,5,6,7].every(day =>
            meals.every(meal => ['start','end'].every(part =>
                one(`#schedule-${profile} input[name="slot_${day}_${meal}_${part}"][type="time"]`))));
        result[`${profile}_original_revision`] = one(`#schedule-${profile} input[name="revision"]`);
    }
    return result;
}"""


@dataclass
class Proof:
    captured_at: str = field(default_factory=lambda: datetime.now(timezone.utc).isoformat())
    checks: dict[str, bool] = field(default_factory=dict)
    failures: list[str] = field(default_factory=list)
    pages: list[dict[str, str]] = field(default_factory=list)

    def check(self, name: str, passed: bool) -> None:
        self.checks[name] = bool(passed)
        if not passed:
            self.failures.append(name)


class ReadGuard:
    """Permit same-origin reads and consume the sole permitted login POST."""

    def __init__(self, base: str, proof: Proof, viewport: str) -> None:
        self.base, self.proof, self.viewport = base, proof, viewport
        self.login_pending = True

    def __call__(self, route: Route) -> None:
        request = route.request
        parsed, origin = urlsplit(request.url), urlsplit(self.base)
        same = ((parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc)
                and parsed.username is None and parsed.password is None)
        if same and request.method in {'GET', 'HEAD'}:
            route.continue_()
            return
        if (same and self.login_pending and request.method == 'POST'
                and request.url == f'{self.base}/auth/local'):
            self.login_pending = False
            route.continue_()
            return
        self.proof.failures.append(f'{self.viewport}.request_blocked')
        route.abort()


def _write_private(path: Path, content: bytes) -> None:
    descriptor = os.open(path, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'wb') as stream:
        stream.write(content)


def capture_viewport(browser: Browser, base: str, outdir: Path, viewport: str,
                     password: str, proof: Proof) -> None:
    width, height = VIEWPORTS[viewport]
    guard = ReadGuard(base, proof, viewport)
    csp_errors = 0
    asset_status: dict[str, bool] = {}

    def asset_response(response: Response) -> None:
        parsed, origin = urlsplit(response.url), urlsplit(base)
        branding_css = (response.request.resource_type == 'stylesheet' and not parsed.query
                        and re.fullmatch(r'/branding/revisions/[1-9][0-9]*\.css', parsed.path) is not None)
        if ((parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc)
                and (parsed.path.startswith('/static/') or branding_css)):
            asset_status[response.url] = response.status == 200

    def console(message: ConsoleMessage) -> None:
        nonlocal csp_errors
        if 'content security policy' in message.text.lower():
            csp_errors += 1

    try:
        with browser.new_context(viewport={'width': width, 'height': height}, locale='de-CH',
                                 reduced_motion='reduce', service_workers='block') as context:
            context.set_default_timeout(15000)
            context.route('**/*', guard)
            context.route_web_socket('**/*', lambda socket: socket.close())
            context.on('console', console)
            context.on('response', asset_response)
            page = context.new_page()
            response = page.goto(f'{base}/auth/local', wait_until='load')
            if response is None or response.status != 200:
                proof.failures.append(f'{viewport}.login_unavailable')
                return
            page.locator('input[name="username"]').fill(USER)
            page.locator('input[name="password"]').fill(password)
            with page.expect_navigation(wait_until='load'):
                page.get_by_role('button', name='Anmelden', exact=True).click()
            guard.login_pending = False
            if not _admin_url(page.url, base):
                proof.failures.append(f'{viewport}.login_failed')
                return
            asset_status.clear()  # Require evidence from this OPS navigation, not the login page.
            response = page.goto(f'{base}{OPS_PATH}', wait_until='load')
            authenticated = (_admin_url(page.url, base) and urlsplit(page.url).path == OPS_PATH
                             and page.locator('input[type="password"]').count() == 0)
            proof.check(f'{viewport}.authenticated', authenticated)
            ok = response is not None and response.status == 200
            proof.check(f'{viewport}.http_200', ok)
            if not authenticated or not ok:
                return  # Never screenshot a login page or error body.
            policy = (response.header_value('content-security-policy') if response else '') or ''
            directives = {parts[0]: parts[1:] for item in policy.split(';') if (parts := item.split())}
            scripts = directives.get('script-src', [])
            proof.check(f'{viewport}.csp_self_scripts', scripts == ["'self'"]
                        and directives.get('script-src-elem', scripts) == ["'self'"])
            layout = page.evaluate(LAYOUT_AUDIT)
            proof.check(f'{viewport}.no_horizontal_overflow', layout['overflow_px'] <= 1)
            proof.check(f'{viewport}.no_inline_code', layout['inline_scripts'] == 0
                        and layout['inline_handlers'] == 0 and layout['inline_styles'] == 0)
            for name, passed in page.evaluate(OPS_AUDIT).items():
                proof.check(f'{viewport}.{name}', passed)
            # Missing browser responses must fail, without an independent API GET fallback.
            for url in page.locator('link[rel="stylesheet"][href], script[src]').evaluate_all(
                    'nodes => nodes.map(node => node.href || node.src)'):
                asset_status.setdefault(url, False)
            for name, passed in audit_tabler(page, base, asset_status).items():
                proof.check(f'{viewport}.{name}', passed)
            proof.check(f'{viewport}.no_csp_console_errors', csp_errors == 0)
            screenshot = page.screenshot(full_page=True)
            filename = f'ops-{viewport}-{width}x{height}.png'
            _write_private(outdir / filename, screenshot)
            proof.pages.append({'viewport': viewport, 'screenshot': filename,
                                'sha256': hashlib.sha256(screenshot).hexdigest()})
    except Exception:
        # Exception messages, URLs, bodies and protocol logs may contain secrets.
        proof.failures.append(f'{viewport}.capture_failed')


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, required=True)
    parser.add_argument('--base-url', required=True)
    args = parser.parse_args()
    proof = Proof()
    try:
        parsed = urlsplit(args.base_url)
        if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
                or parsed.username is not None or parsed.password is not None
                or parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
            raise ValueError('invalid_origin')
        base = f'{parsed.scheme}://{parsed.netloc}'
        outdir = args.outdir.absolute()
        outdir.mkdir(mode=0o700, parents=True, exist_ok=False)
        outdir.chmod(0o700)
    except Exception:
        print('failed: invalid origin or new private output directory unavailable')
        return 1
    try:
        os.environ.pop('DEBUG', None)
        os.environ.pop('PWDEBUG', None)
        password = _password()
        with sync_playwright() as playwright:
            with playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage']) as browser:
                for viewport in VIEWPORTS:
                    capture_viewport(browser, base, outdir, viewport, password, proof)
    except Exception:
        proof.failures.append('runner.failed')
    proof.check('both_viewports_captured', len(proof.pages) == len(VIEWPORTS))
    status = 'failed' if proof.failures else 'passed'
    try:
        _write_private(outdir / 'proof.json',
                       (json.dumps({**asdict(proof), 'status': status}, indent=2) + '\n').encode())
    except Exception:
        print('failed: private evidence could not be written')
        return 1
    print(status)
    return 0 if status == 'passed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
