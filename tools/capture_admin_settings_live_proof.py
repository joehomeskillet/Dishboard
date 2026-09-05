#!/usr/bin/env python3
"""Read-only live proof for global density and component filters after deployment.

Only the official login sends a POST. Never submit a settings or component form.
Use --outdir NEW_DIRECTORY; exit 0 passes, 1 fails, 2 lacks existing test data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from playwright.sync_api import BrowserContext, Page, Response, Route, sync_playwright

from capture_admin_live_proof import PATIENT_PRICE_VOCABULARY, USER, _password

DISPLAY_PATH = '/admin/design/darstellung'
FIELDS = ('q', 'category', 'usage', 'allergen', 'presence', 'label', 'origin', 'status')
DEFAULT_FILTERS = dict.fromkeys(FIELDS, '') | {'status': 'active'}
WIDTHS = (390, 820, 1440)


class SettingsProof:
    def __init__(self, base: str, outdir: Path) -> None:
        self.base, self.outdir = base, outdir
        self.origin = urlsplit(base)
        self.allowed_paths = {'/auth/local', DISPLAY_PATH}
        for family in ('cafeteria', 'patienten'):
            self.allowed_paths.update((f'/admin/{family}', f'/admin/{family}/komponenten'))
        self.data: dict[str, Any] = {
            'captured_at': datetime.now(timezone.utc).isoformat(), 'base_url': base,
            'expected_density': 'compact', 'checks': {}, 'failures': [], 'unavailable': [], 'pages': [],
            'limits': 'GET-only product coverage; does not prove settings writes or unavailable catalog data.',
        }
        self.blocked = False

    def check(self, name: str, passed: bool) -> None:
        self.data['checks'][name] = bool(passed)
        if not passed:
            self.data['failures'].append(name)

    def guard(self, route: Route) -> None:
        request = route.request
        target = urlsplit(request.url)
        same_origin = (target.scheme, target.netloc) == (self.origin.scheme, self.origin.netloc)
        if (self.blocked or not same_origin or request.method not in {'GET', 'HEAD'}
                or not (target.path in self.allowed_paths or target.path.startswith('/static/'))):
            self.blocked = True
            self.check('network.unexpected_request_blocked', False)
            route.abort()
            return
        try:
            response = route.fetch(max_redirects=0, max_retries=0, timeout=15000)
            if 300 <= response.status < 400:
                self.blocked = True
                self.check('network.unexpected_redirect_blocked', False)
                route.abort()
                return
            route.fulfill(response=response)
        except Exception:
            self.blocked = True
            self.check('network.fetch_failed', False)
            route.abort()

    def configure(self, context: BrowserContext, *, legacy: str) -> None:
        context.set_default_timeout(15000)
        context.route('**/*', self.guard)
        # Deliberately disagreeing old browser values must never change server density.
        context.add_init_script(f"localStorage.setItem('admin-dense', {json.dumps(legacy)})")

    def login(self, context: BrowserContext) -> None:
        page = context.new_page()
        login_url = self.base + '/auth/local'
        response = page.goto(login_url, wait_until='load')
        if self.blocked or response is None or response.status != 200:
            raise RuntimeError('login_page_unavailable')
        form = page.locator('form[method="post"][action="/auth/local"]')
        if form.count() != 1:
            raise RuntimeError('login_form_unavailable')
        form.locator('[name="username"]').fill(USER)
        form.locator('[name="password"]').fill(_password())
        pairs = form.evaluate('(form) => [...new FormData(form).entries()]')
        # Fixed endpoint; API calls bypass browser routing, so never follow redirects.
        result = context.request.post(
            login_url, data=urlencode([(key, value) for key, value in pairs]),
            max_redirects=0, max_retries=0, timeout=15000,
            headers={'Content-Type': 'application/x-www-form-urlencoded',
                     'Origin': self.base, 'Referer': login_url},
        )
        if (result.status != 302
                or urljoin(self.base, result.headers.get('location', '')) != self.base + '/admin/cafeteria'):
            raise RuntimeError('login_failed')
        self.check('login.only_official_post', True)
        # Discard the redirect; subsequent navigation uses the explicit allowlist.
        page.close()

    def capture(self, page: Page, response: Response | None, name: str, profile: str) -> None:
        self.check(f'{name}.http_200', response is not None and response.status == 200)
        if response is None or response.status != 200 or self.blocked:
            raise RuntimeError('page_unavailable')
        main = page.locator('main#main-content')
        self.check(f'{name}.profile', main.count() == 1 and main.get_attribute('data-profile') == profile)
        self.check(f'{name}.authenticated', page.locator('input[type="password"]').count() == 0)
        self.check(f'{name}.no_store', response.header_value('cache-control') == 'no-store')
        self.check(f'{name}.get_only', response.request.method == 'GET')
        self.check(f'{name}.global_compact', main.get_attribute('data-density') == 'compact')
        self.check(f'{name}.no_local_checkbox', page.get_by_label('Kompakte Ansicht', exact=True).count() == 0)
        self.check(f'{name}.tabler_css', page.locator('link[href="/static/vendor/tabler/tabler.min.css"]').count() == 1)
        self.check(f'{name}.no_legacy_css', page.locator('link[href="/static/app.css"]').count() == 0)
        self.check(f'{name}.no_overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
        self.check(f'{name}.compact_spacing', main.locator('.card-body').first.evaluate(
            'el => getComputedStyle(el).paddingTop',
        ) == '12px')
        self.check(f'{name}.touch_and_fonts', main.locator('.btn, .form-select, .form-control').evaluate_all('''els =>
            els.every(el => { const r = el.getBoundingClientRect(); return !r.width || !r.height ||
                (r.height >= 48 && parseFloat(getComputedStyle(el).fontSize) >= 16); })'''))
        if profile == 'patient':
            self.check(f'{name}.no_patient_prices', PATIENT_PRICE_VOCABULARY.search(page.content()) is None)
        path = self.outdir / f'{name}.png'
        content = page.screenshot(path=str(path), full_page=True)
        path.chmod(0o600)
        self.data['pages'].append({'name': name, 'http_status': response.status,
                                   'screenshot': path.name, 'sha256': hashlib.sha256(content).hexdigest()})

    def filter_state(self, page: Page, name: str, values: dict[str, str]) -> list[dict[str, Any]]:
        form = page.get_by_role('form', name='Komponenten filtern', exact=True)
        self.check(f'{name}.tabler_card', 'card' in (form.get_attribute('class') or '').split())
        self.check(f'{name}.get_form', (form.get_attribute('method') or '').lower() == 'get')
        self.check(f'{name}.exact_fields', form.locator('[name]').evaluate_all(
            'els => els.map(el => el.name).sort()',
        ) == sorted(FIELDS))
        for key, value in values.items():
            self.check(f'{name}.value_{key}', form.locator(f'[name="{key}"]').input_value() == value)
        rows = page.locator('.component-row').evaluate_all(r'''els => els.map(el => ({
            id: el.dataset.publicId, active: el.dataset.active === '1',
            scope: el.querySelector('.scope').textContent.trim(),
            origin: el.querySelector('td:nth-of-type(2) > div').textContent.trim(),
            labels: [...el.querySelectorAll('td:nth-of-type(2) .badge')].map(x => x.textContent.trim()),
            usage: Number(el.querySelector('.usage').textContent.match(/\d+/)[0])
        }))''')
        count = page.locator('#component-result-count').inner_text().strip()
        self.check(f'{name}.row_count', count == f'{len(rows)} Treffer')
        self.check(f'{name}.unique_rows', len({row['id'] for row in rows}) == len(rows))
        allowed_scope = 'nur Patienten' if '/patienten/' in urlsplit(page.url).path else 'nur Cafeteria'
        self.check(f'{name}.row_scope', all(row['scope'] in {'gemeinsam', allowed_scope} for row in rows))
        self.check(f'{name}.unknown_not_free', 'keine bestätigte Allergenfreiheit' in page.locator(
            '#component-allergen-filter-hint',
        ).inner_text())
        return rows

    def submit_filters(self, page: Page, values: dict[str, str], name: str, profile: str) -> list[dict[str, Any]]:
        form = page.get_by_role('form', name='Komponenten filtern', exact=True)
        for key, value in values.items():
            field = form.locator(f'[name="{key}"]')
            field.fill(value) if key == 'q' else field.select_option(value)
        with page.expect_navigation(wait_until='load') as navigated:
            form.get_by_role('button', name='Suchen', exact=True).click()
        self.capture(page, navigated.value, name, profile)
        query = parse_qsl(urlsplit(page.url).query, keep_blank_values=True)
        self.check(f'{name}.query_contract', len(query) == len(values) and dict(query) == values)
        return self.filter_state(page, name, values)

    def family(self, page: Page, width: int, family: str, profile: str) -> None:
        name = f'{width}.{family}'
        path = f'/admin/{family}/komponenten'
        response = page.goto(self.base + path, wait_until='load')
        self.capture(page, response, name + '.default', profile)
        baseline = self.filter_state(page, name + '.default', DEFAULT_FILTERS)
        self.check(name + '.active_default', all(row['active'] for row in baseline))
        if not baseline:
            self.data['unavailable'].append(name + '.existing_active_components')
        labels = page.locator('#f-label option').evaluate_all(
            'els => els.filter(el => el.value).map(el => ({value: el.value, text: el.textContent.trim()}))',
        )
        allergens = page.locator('#f-allergen option').evaluate_all(
            'els => els.map(el => el.value).filter(value => value && value !== "unknown")',
        )
        if not labels or not allergens:
            self.data['unavailable'].append(name + '.active_filter_metadata')
        label = labels[0] if labels else {'value': '', 'text': ''}
        combined = DEFAULT_FILTERS | {'usage': 'used', 'origin': 'CH', 'label': label['value'],
                                     'allergen': allergens[0] if allergens else '',
                                     'presence': 'contains' if allergens else ''}
        selected = self.submit_filters(page, combined, name + '.combined', profile)
        eligible = {row['id'] for row in baseline if row['usage'] > 0 and row['origin'] == 'CH'
                    and (not label['value'] or label['text'] in row['labels'])}
        self.check(name + '.combined_matches_visible_metadata', {row['id'] for row in selected} <= eligible)

        selected = self.submit_filters(page, DEFAULT_FILTERS | {'label': label['value']}, name + '.label', profile)
        expected = {row['id'] for row in baseline if not label['value'] or label['text'] in row['labels']}
        self.check(name + '.label_exact_results', {row['id'] for row in selected} == expected)
        archived = self.submit_filters(page, DEFAULT_FILTERS | {'status': 'archived'}, name + '.archived', profile)
        self.check(name + '.archived_results', all(not row['active'] for row in archived))

        with page.expect_navigation(wait_until='load') as reset:
            page.get_by_role('form', name='Komponenten filtern').get_by_role('link', name='Zurücksetzen').click()
        self.capture(page, reset.value, name + '.reset', profile)
        self.check(name + '.reset_exact_route', page.url == self.base + path)
        reset_rows = self.filter_state(page, name + '.reset', DEFAULT_FILTERS)
        self.check(name + '.reset_restores_rows', {row['id'] for row in reset_rows} == {row['id'] for row in baseline})

        response = page.goto(f'{self.base}/admin/{family}', wait_until='load')
        self.capture(page, response, name + '.overview', profile)
        link = page.get_by_role('navigation', name='Backend').get_by_role('link', name='Design & Marke', exact=True)
        self.check(name + '.design_link', link.count() == 1 and link.get_attribute('href') == DISPLAY_PATH)
        if not link.is_visible():
            page.get_by_role('button', name='Menü', exact=True).click()
        with page.expect_navigation(wait_until='load') as display:
            link.click()
        self.capture(page, display.value, name + '.display', 'staff_guest')
        self.check(name + '.design_exact_route', page.url == self.base + DISPLAY_PATH)
        self.check(name + '.setting_matches_density', page.get_by_label('Abstände', exact=True).input_value() == 'compact')
        self.check(name + '.settings_help_visible', page.locator('#admin-density-hint').is_visible())
        self.check(name + '.settings_form_present', page.locator('form[action="' + DISPLAY_PATH + '"]').count() == 1)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', default='https://dishboard.joelduss.xyz')
    parser.add_argument('--outdir', type=Path, required=True, help='New private directory; never overwritten')
    args = parser.parse_args()
    origin = urlsplit(args.base_url)
    if (origin.scheme != 'https' or not origin.hostname or origin.username is not None or origin.password is not None
            or origin.path not in {'', '/'} or origin.query or origin.fragment):
        parser.error('base-url must be an HTTPS origin without credentials, query, or path')
    os.umask(0o077)
    outdir = args.outdir.resolve()
    outdir.mkdir(mode=0o700, parents=True, exist_ok=False)
    proof = SettingsProof(f'{origin.scheme}://{origin.netloc}', outdir)
    stage = 'login'
    try:
        os.environ.pop('DEBUG', None)
        os.environ.pop('PWDEBUG', None)
        with sync_playwright() as playwright:
            with playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage']) as browser:
                with browser.new_context(service_workers='block') as authenticated:
                    proof.configure(authenticated, legacy='true')
                    proof.login(authenticated)
                    auth_state = authenticated.storage_state()  # Memory only; never write auth state to reports.
                for width in WIDTHS:
                    with browser.new_context(storage_state=auth_state, viewport={'width': width, 'height': 1100},
                                             locale='de-CH', reduced_motion='reduce', service_workers='block') as context:
                        proof.configure(context, legacy='true')
                        page = context.new_page()
                        for family, profile in (('cafeteria', 'staff_guest'), ('patienten', 'patient')):
                            stage = f'{width}.{family}'
                            proof.family(page, width, family, profile)
                        proof.check(f'{width}.old_local_value_unchanged', page.evaluate(
                            "localStorage.getItem('admin-dense')",
                        ) == 'true')
                    stage = f'{width}.independent'
                    with browser.new_context(storage_state=auth_state, viewport={'width': width, 'height': 1100},
                                             locale='de-CH', reduced_motion='reduce', service_workers='block') as second:
                        proof.configure(second, legacy='false')
                        page = second.new_page()
                        response = page.goto(proof.base + DISPLAY_PATH, wait_until='load')
                        proof.capture(page, response, stage, 'staff_guest')
                        proof.check(stage + '.same_global_value', page.get_by_label('Abstände', exact=True).input_value() == 'compact')
                        proof.check(stage + '.old_local_value_unchanged', page.evaluate(
                            "localStorage.getItem('admin-dense')",
                        ) == 'false')
    except Exception as error:
        # No exception messages, request data, credentials, cookies, traces or video.
        proof.data['failures'].append(f'{stage}.{type(error).__name__}')
    status = 'failed' if proof.data['failures'] else 'incomplete' if proof.data['unavailable'] else 'passed'
    proof.data['status'] = status
    report = outdir / 'proof.json'
    report.write_text(json.dumps(proof.data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report.chmod(0o600)
    print(f'{status}: {report}')
    return {'passed': 0, 'failed': 1, 'incomplete': 2}[status]


if __name__ == '__main__':
    raise SystemExit(main())
