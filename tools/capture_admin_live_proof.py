#!/usr/bin/env python3
"""Capture read-only admin proof after local login; never serialize credentials.

Use --outdir PATH --base-url https://dishboard.joelduss.xyz. Exit 0 means passed,
1 means failed, and 2 means required coverage was unavailable with existing data.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import stat
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Browser, Page, Response, Route, sync_playwright

USER = 'kueche.admin'
PASSWORD_FILE = Path('/root/.dishboard/kueche.admin.initial-password')
VIEWPORTS = {'mobile': (390, 844), 'desktop': (1440, 1100)}
COPY_FIELDS = ['_csrf', 'source_week', 'target_row_version', 'target_week']
LAYOUT_AUDIT = """() => {
    const visible = element => {
        const rect = element.getBoundingClientRect();
        return rect.width > 0 && rect.height > 0;
    };
    const controls = [...document.querySelectorAll(
        'a[href], button, input:not([type="hidden"]), select, textarea, summary'
    )].filter(visible);
    return {
        overflow_px: Math.max(0, document.documentElement.scrollWidth - window.innerWidth),
        controls_below_44px: controls.filter(element => {
            const target = element.closest('label') || element;
            const rect = target.getBoundingClientRect();
            return rect.width < 44 || rect.height < 44;
        }).length,
        inline_scripts: document.querySelectorAll('script:not([src])').length,
        inline_handlers: [...document.querySelectorAll('*')].filter(element =>
            [...element.attributes].some(attribute => /^on/i.test(attribute.name))
        ).length,
        inline_styles: document.querySelectorAll('[style]').length
    };
}"""


def _password() -> str:
    value = os.environ.pop('E2E_PW', '')
    if not value:
        info = PASSWORD_FILE.lstat()
        if not stat.S_ISREG(info.st_mode) or info.st_uid != 0 or info.st_mode & 0o077:
            raise ValueError('protected_password_file_required')
        value = PASSWORD_FILE.read_text(encoding='utf-8').rstrip('\r\n')
    if not value:
        raise ValueError('password_unavailable')
    return value


def _admin_url(url: str, base: str) -> bool:
    parsed, origin = urlsplit(url), urlsplit(base)
    return (parsed.scheme, parsed.netloc) == (origin.scheme, origin.netloc) and (
        parsed.path == '/admin' or parsed.path.startswith('/admin/')
    )


def capture_viewport(
    browser: Browser, base: str, outdir: Path, viewport: str,
    password: str, proof: dict[str, object], csv_preview: bool = False,
) -> None:
    width, height = VIEWPORTS[viewport]
    checks, failures = proof['checks'], proof['failures']
    login_pending = True
    stage = f'{viewport}.login'
    csp_errors = 0

    def check(name: str, passed: bool) -> None:
        checks[name] = bool(passed)
        if not passed:
            failures.append(name)

    def guard(route: Route) -> None:
        request = route.request
        login_post = login_pending and request.method == 'POST' and request.url == f'{base}/auth/local'
        preview_post = (csv_preview and not login_pending and request.method == 'POST'
                        and request.url == f'{base}/admin/import-preview')
        if request.method in {'GET', 'HEAD'} or login_post or preview_post:
            route.continue_()
        else:
            failures.append(f'{viewport}.unexpected_write_blocked')
            route.abort()

    def console_message(message) -> None:
        nonlocal csp_errors
        if 'content security policy' in message.text.lower():
            csp_errors += 1

    def capture(page: Page, response: Response | None, name: str, patient: bool) -> None:
        authenticated = _admin_url(page.url, base) and page.locator('input[type="password"]').count() == 0
        check(f'{name}.authenticated', authenticated)
        if not authenticated:
            raise RuntimeError('authentication_lost')
        check(f'{name}.http_200', response is not None and response.status == 200)
        policy = (response.header_value('content-security-policy') if response else '') or ''
        directives = {parts[0]: parts[1:] for item in policy.split(';') if (parts := item.split())}
        scripts = directives.get('script-src', [])
        element_scripts = directives.get('script-src-elem', scripts)
        check(f'{name}.csp_self_scripts', scripts == ["'self'"] and element_scripts == ["'self'"])
        audit = page.evaluate(LAYOUT_AUDIT)
        check(f'{name}.no_inline_script', audit['inline_scripts'] == 0 and audit['inline_handlers'] == 0)
        check(f'{name}.no_inline_style', audit['inline_styles'] == 0)
        check(f'{name}.no_horizontal_overflow', audit['overflow_px'] <= 1)
        if patient:
            check(f'{name}.no_price_vocabulary', re.search(r'preis|chf|rappen|kosten|price', page.content(), re.I) is None)
        filename = f'{name}-{width}x{height}.png'
        path = outdir / filename
        screenshot = page.screenshot(path=str(path), full_page=True)
        path.chmod(0o600)
        proof['pages'].append({
            'name': name, 'http_status': response.status if response else None,
            'screenshot': filename, 'sha256': hashlib.sha256(screenshot).hexdigest(),
            'diagnostics': audit,
        })

    with browser.new_context(
        viewport={'width': width, 'height': height}, locale='de-CH',
        reduced_motion='reduce', ignore_https_errors=False,
    ) as context:
        context.set_default_timeout(15000)
        context.route('**/*', guard)
        context.on('console', console_message)
        page = context.new_page()
        try:
            response = page.goto(f'{base}/auth/local', wait_until='load')
            if response is None or response.status != 200:
                raise RuntimeError('login_page_unavailable')
            page.locator('input[name="username"]').fill(USER)
            page.locator('input[name="password"]').fill(password)
            with page.expect_navigation(wait_until='load'):
                page.get_by_role('button', name='Anmelden', exact=True).click()
            login_pending = False
            check(f'{stage}.authenticated', _admin_url(page.url, base))
            if not _admin_url(page.url, base):
                raise RuntimeError('login_failed')
        except Exception as error:
            failures.append(f'{stage}.{type(error).__name__}')
            return

        for family, profile, slots in [('cafeteria', 'staff_guest', 10), ('patienten', 'patient', 28)]:
            prefix = f'{viewport}.{family}'
            patient = family == 'patienten'
            try:
                stage = f'{prefix}.overview'
                overview = f'{base}/admin/{family}'
                response = page.goto(overview, wait_until='load')
                capture(page, response, stage, patient)
                check(f'{stage}.slots', page.locator('article.menu-slot').count() == slots)
                week = date.fromisoformat(page.locator('main.admin-main').get_attribute('data-week') or '')
                stage = f'{prefix}.editor'
                with page.expect_navigation(wait_until='load') as editor_response:
                    page.locator('article.menu-slot a[href*="/menu?"]').first.click()
                capture(page, editor_response.value, stage, patient)
                menu_form = page.locator('form[action$="/menu"]')
                check(f'{stage}.menu_form', menu_form.count() == 1)
                check(f'{stage}.one_item_version', menu_form.locator('input[name="row_version"]').count() == 1)

                page.goto(overview, wait_until='load')
                stage = f'{prefix}.preview'
                link = page.locator('a[target="_blank"][href*="/preview"]:visible').first
                check(f'{stage}.noopener', 'noopener' in (link.get_attribute('rel') or '').split())
                preview_url = urljoin(base, link.get_attribute('href') or '')
                with context.expect_event('response', predicate=lambda reply: (
                    reply.url == preview_url and reply.request.is_navigation_request()
                )) as preview_response:
                    with page.expect_popup() as opened:
                        link.click()
                popup = opened.value
                popup.wait_for_load_state('load')
                capture(popup, preview_response.value, stage, patient)
                check(f'{stage}.new_tab', popup != page and len(context.pages) == 2)
                banner = popup.locator('.preview-banner[role="status"]')
                check(f'{stage}.banner', banner.count() == 1 and banner.inner_text().strip() == 'PREVIEW')
                saved = popup.locator('section[data-preview="last-saved"]')
                check(f'{stage}.last_saved', saved.count() == 1)
                check(f'{stage}.saved_scope', saved.count() == 1 and saved.get_attribute('data-profile') == profile
                      and saved.get_attribute('data-week') == week.isoformat())
                check(f'{stage}.saved_state', saved.count() == 1 and saved.get_attribute('data-workflow-state') in {
                    'draft', 'ready', 'published', 'archived',
                })
                popup.close()

                stage = f'{prefix}.catalog'
                response = page.goto(f'{base}/admin/{family}/komponenten', wait_until='load')
                capture(page, response, stage, patient)
                rows = page.locator('li.component-row[data-public-id]')
                proof['catalogs'][prefix] = {'existing_components': rows.count(), 'detail_available': rows.count() > 0}
                if rows.count():
                    stage = f'{prefix}.component_detail'
                    with page.expect_navigation(wait_until='load') as detail_response:
                        rows.first.locator('a').first.click()
                    capture(page, detail_response.value, stage, patient)
                    check(f'{stage}.public_id', bool(page.locator('main').get_attribute('data-public-id')))

                stage = f'{prefix}.copy'
                target = week + timedelta(days=7)
                response = page.goto(f'{base}/admin/{family}/copy?week={target.isoformat()}', wait_until='load')
                if response is not None and response.status in {404, 409}:
                    proof['unavailable'].append({'page': stage, 'http_status': response.status,
                                                 'reason': 'existing_data_prevents_copy_form'})
                    continue
                capture(page, response, stage, patient)
                form = page.locator(f'form[method="post"][action="/admin/{family}/copy"]')
                check(f'{stage}.form', form.count() == 1)
                names = form.locator('input[name], select[name], textarea[name], button[name]').evaluate_all(
                    'elements => elements.map(element => element.name)'
                )
                check(f'{stage}.exact_fields', sorted(names) == COPY_FIELDS)
                check(f'{stage}.source_week', form.locator('[name="source_week"]').input_value() == week.isoformat())
                check(f'{stage}.target_week', form.locator('[name="target_week"]').input_value() == target.isoformat())
            except Exception as error:
                failures.append(f'{stage}.{type(error).__name__}')
                for extra in context.pages:
                    if extra != page:
                        extra.close()
        if csv_preview:
            try:
                stage = f'{viewport}.csv.empty'
                response = page.goto(f'{base}/admin/import-preview', wait_until='load')
                capture(page, response, stage, False)
                check(f'{stage}.state', page.locator('main[data-state="empty"]').count() == 1)
                check(f'{stage}.primary_visible', page.locator('#csv-upload button.primary').is_visible())
                for family, label, filename in [
                    ('cafeteria', 'Cafeteria', 'menu_cafeteria_example.csv'),
                    ('patienten', 'Patientenplan', 'menu_patient_example.csv'),
                ]:
                    stage = f'{viewport}.csv.{family}'
                    upload = page.locator('form#csv-upload[action="/admin/import-preview"]')
                    example = Path(__file__).resolve().parents[1] / 'csv' / filename
                    upload.locator('input[name="file"]').set_input_files(str(example))
                    with page.expect_navigation(wait_until='load') as csv_response:
                        upload.get_by_role('button', name='Vorschau prüfen', exact=True).click()
                    capture(page, csv_response.value, stage, family == 'patienten')
                    check(f'{stage}.state', page.locator('main[data-state="ready"]').count() == 1)
                    result = page.locator('.csv-preview-result')
                    target = result.locator('.csv-target')
                    check(f'{stage}.profile', target.locator('strong').inner_text() == label)
                    check(f'{stage}.week', re.search(r'\bKW 36\b.*31\.08\.2026', target.inner_text(), re.S) is not None)
                    form = result.locator('form[method="post"][action="/admin/import"]')
                    check(f'{stage}.import_form', form.count() == 1)
                    names = form.locator('input[name], select[name], textarea[name], button[name]').evaluate_all(
                        'elements => elements.map(element => element.name)'
                    )
                    check(f'{stage}.exact_fields', sorted(names) == ['_csrf', 'import_token'])
                    check(f'{stage}.primary_visible', form.locator('button.primary[type="submit"]').is_visible())
            except Exception as error:
                failures.append(f'{stage}.{type(error).__name__}')
        check(f'{viewport}.no_csp_console_errors', csp_errors == 0)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--outdir', type=Path, required=True)
    parser.add_argument('--base-url', default='https://dishboard.joelduss.xyz')
    parser.add_argument('--csv-preview', action='store_true', help='Preview example CSV uploads; never import them')
    args = parser.parse_args()
    parsed = urlsplit(args.base_url)
    if (parsed.scheme not in {'http', 'https'} or not parsed.hostname
            or parsed.username is not None or parsed.password is not None
            or parsed.path not in {'', '/'} or parsed.query or parsed.fragment):
        parser.error('base-url must be an HTTP(S) origin without credentials, query, or path')
    base = f'{parsed.scheme}://{parsed.netloc}'
    outdir = args.outdir.resolve()
    outdir.mkdir(mode=0o700, parents=True, exist_ok=True)
    proof: dict[str, object] = {
        'captured_at': datetime.now(timezone.utc).isoformat(), 'base_url': base,
        'checks': {}, 'pages': [], 'catalogs': {}, 'unavailable': [], 'failures': [],
        'control_size_audit': 'diagnostic only; does not establish complete UI acceptance',
    }
    try:
        # Debug protocol logs can include filled values; never enable them here.
        os.environ.pop('DEBUG', None)
        os.environ.pop('PWDEBUG', None)
        password = _password()
        with sync_playwright() as playwright:
            with playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage']) as browser:
                for viewport in VIEWPORTS:
                    capture_viewport(browser, base, outdir, viewport, password, proof, args.csv_preview)
    except Exception as error:
        # Deliberately omit exception text, request details, console text and headers.
        proof['failures'].append(f'runner.{type(error).__name__}')
    status = 'failed' if proof['failures'] else 'incomplete' if proof['unavailable'] else 'passed'
    proof['status'] = status
    path = outdir / 'proof.json'
    path.write_text(json.dumps(proof, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    path.chmod(0o600)
    print(f'{status}: {path}')
    return {'passed': 0, 'failed': 1, 'incomplete': 2}[status]


if __name__ == '__main__':
    raise SystemExit(main())
