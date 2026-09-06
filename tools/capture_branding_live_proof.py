#!/usr/bin/env python3
"""Read-only branding browser acceptance AFTER deployment; no production writes.

Exit 0: browser checks pass (PDF proof remains separate), 1: failure, 2: missing
published data. Screenshots and JSON are private; authentication stays in memory.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from urllib.parse import urlencode, urljoin, urlsplit

from playwright.sync_api import BrowserContext, Page, Request, Response, Route, sync_playwright

from capture_admin_live_proof import PATIENT_PRICE_VOCABULARY, USER, _password

BASE_URL = 'https://dishboard.joelduss.xyz'
EDITOR = '/admin/design/marke'
PUBLIC = ('/cafeteria/heute/', '/cafeteria/wochenangebot/', '/patienten/heute/', '/patienten/wochenplan/')
SIGNAGE = ('/signage/cafeteria/tag', '/signage/cafeteria/woche',
           '/signage/patienten/tag', '/signage/patienten/woche')
AUX = ('/druck/cafeteria/woche', '/druck/patienten/woche', '/cafeteria/legende/', '/auth/local')
PDF_RUNNER = '/nvmetank1/projects/rag-stack/.claude/reports/artifacts/wp-bd5539046da6/dishboard-api-admin-live-0906.py'
SYMBOLS = Path(__file__).resolve().parents[1] / 'reference_scaffold/cafeteria/static/vendor/food-symbols/manifest.json'
WARNINGS = ('Allergenangaben nicht erfasst', 'Allergenprüfung offen')
CLOSED = '.hero-food-closed,.public-menu-notice,.cafe-week-closed,.patient-duo-closed,.patient-board-closed,.closed-row'
MENU_SELECTORS = ('.hero-food', '.cafe-week-slot', '.patient-signage-option:not(.patient-duo-closed)',
                  '.patient-week-option:not(.patient-board-closed)')


class BrandingProof:
    def __init__(self, base: str, outdir: Path) -> None:
        self.base, self.outdir, self.blocked = base, outdir, False
        self.active_css: str | None = None
        self.active_logo: str | None = None
        self.active_values: dict[str, str] = {}
        self.catalog = json.loads(SYMBOLS.read_text(encoding='utf-8'))
        self.assets: set[str] = set()
        self._completed_logo_urls: set[tuple[BrowserContext | None, str]] = set()
        self._pending_logos: dict[Request, tuple[BrowserContext | None, str] | None] = {}
        self.data: dict[str, Any] = {
            'captured_at': datetime.now(timezone.utc).isoformat(), 'base_url': base,
            'scope': 'Read-only browser acceptance; no upload, activation, publication or write acceptance.',
            'checks': dict.fromkeys(('network.requests_complete', 'browser.no_javascript_errors',
                                     'browser.no_console_errors'), True),
            'failures': [], 'unavailable': [], 'coverage_limits': [], 'pages': [], 'observations': {},
            'pdf': {'status': 'pending_separate_post_deploy_run', 'runner': PDF_RUNNER, 'week': '2026-08-31',
                    'required': 'Fresh complete patient/cafeteria downloads; historical results are not evidence.'},
        }

    def check(self, name: str, passed: bool) -> None:
        self.data['checks'][name] = self.data['checks'].get(name, True) and bool(passed)
        if not passed and name not in self.data['failures']:
            self.data['failures'].append(name)

    def guard(self, route: Route) -> None:
        request, target = route.request, urlsplit(route.request.url)
        allowed = target.path in (*PUBLIC, *SIGNAGE, *AUX, EDITOR)
        allowed |= target.path.startswith(('/static/', '/branding/', EDITOR + '/'))
        if (self.blocked or f'{target.scheme}://{target.netloc}' != self.base
                or request.method not in {'GET', 'HEAD'} or not allowed):
            self.blocked = True
            self.check('network.unexpected_request_blocked', False)
            route.abort()
        else:
            route.continue_()

    def response(self, response: Response, context: BrowserContext | None = None) -> None:
        path = urlsplit(response.url).path
        if response.request.resource_type != 'document':
            self.check('network.resources_success', response.status < 400)
        protected = path.startswith(EDITOR + '/')
        branded = path.startswith('/branding/')
        if protected and response.request.resource_type == 'document':
            self.check('preview.http_mime_cache', response.status == 200 and
                       response.headers.get('content-type', '').startswith('text/html') and
                       response.headers.get('cache-control') == 'no-store')
            self.csp(response, 'preview')
        asset = path.endswith(('.css', '.png')) and (protected or branded or '/img/suedhang-logo' in path)
        if not asset:
            return
        headers = response.headers
        key = 'preview' if protected else 'public' if branded else 'standard'
        kind = 'css' if path.endswith('.css') else 'logo'
        self.assets.add(f'{key}.{kind}')
        mime = headers.get('content-type', '').split(';')[0]
        valid = response.status == 200 and mime == ('text/css' if kind == 'css' else 'image/png')
        if key == 'standard' and kind == 'logo':
            cache_key = (context, response.url)
            # A 304 has no representation of its own; require a completed PNG GET in this context.
            self._pending_logos[response.request] = cache_key if valid and response.request.method == 'GET' else None
            valid |= response.status == 304 and cache_key in self._completed_logo_urls and (
                'content-type' not in headers or mime == 'image/png')
        self.check(f'assets.{key}.{kind}.http_mime', valid)
        self.check(f'assets.{key}.{kind}.nosniff', headers.get('x-content-type-options') == 'nosniff')
        if protected or branded:
            cache = headers.get('cache-control', '')
            self.check(f'assets.{key}.{kind}.cache', cache == 'no-store' if protected else
                       'public' in cache and 'immutable' in cache and bool(headers.get('etag')))
            if branded:
                self.check(f'assets.{key}.{kind}.no_session_cookie', 'set-cookie' not in headers)

    def logo_requested(self, request: Request) -> None:
        path = urlsplit(request.url).path
        if path.endswith('.png') and '/img/suedhang-logo' in path:
            self._pending_logos[request] = None

    def request_finished(self, request: Request) -> None:
        candidate = self._pending_logos.pop(request, None)
        if candidate is not None:
            self._completed_logo_urls.add(candidate)

    def request_failed(self, request: Request) -> None:
        self._pending_logos.pop(request, None)
        self.check('network.requests_complete', False)

    def csp(self, response: Response, name: str) -> None:
        csp = response.header_value('content-security-policy') or ''
        directives = {parts[0]: parts[1:] for item in csp.split(';') if (parts := item.split())}
        self.check(name + '.strict_csp', all(directives.get(kind) == ["'self'"] for kind in
                                           ('script-src', 'style-src')) and "'unsafe-" not in csp)

    def configure(self, context: BrowserContext) -> Page:
        context.set_default_timeout(15000)
        context.route('**/*', self.guard)
        context.on('request', self.logo_requested)
        context.on('response', lambda response: self.response(response, context))
        context.on('requestfinished', self.request_finished)
        context.on('requestfailed', self.request_failed)
        page = context.new_page()
        page.on('pageerror', lambda _: self.check('browser.no_javascript_errors', False))
        page.on('console', lambda message: self.check('browser.no_console_errors', False)
                if message.type == 'error' else None)
        return page

    def login(self, context: BrowserContext, page: Page) -> None:
        target = self.base + '/auth/local'
        response = page.goto(target, wait_until='load')
        if response is None or response.status != 200 or self.blocked:
            raise RuntimeError('login_page_unavailable')
        form = page.locator('form[method="post"][action="/auth/local"]')
        form.locator('[name="username"]').fill(USER)
        form.locator('[name="password"]').fill(_password())
        pairs = [tuple(pair) for pair in form.evaluate('(form) => [...new FormData(form).entries()]')]
        # Only this fixed, official POST bypasses the GET/HEAD browser guard.
        result = context.request.post(target, data=urlencode(pairs), max_redirects=0, max_retries=0,
                                      headers={'Content-Type': 'application/x-www-form-urlencoded',
                                               'Origin': self.base, 'Referer': target})
        if result.status != 302 or urljoin(self.base, result.headers.get('location', '')) != self.base + '/admin/cafeteria':
            raise RuntimeError('login_failed')
        self.check('login.only_official_post', True)

    def capture(self, page: Page, path: str, name: str, *, signage: bool = False) -> None:
        response = page.goto(self.base + path, wait_until='load')
        if response is None or self.blocked:
            raise RuntimeError('page_unavailable')
        self.check(name + '.http', response.status in {200, 404})
        self.check(name + '.exact_route', page.url == self.base + path)
        if response.status == 404:
            self.data['unavailable'].append(name + '.published_plan_missing')
        self.csp(response, name)
        if path == EDITOR:
            self.check(name + '.no_store', response.header_value('cache-control') == 'no-store')
            self.check(name + '.authenticated', page.locator('input[type="password"]').count() == 0)
        stylesheet = page.locator('link[data-brand-stylesheet]')
        href = stylesheet.get_attribute('href') if stylesheet.count() == 1 else None
        if self.active_css is None:
            self.active_css = href
        self.check(name + '.same_active_revision', bool(href) and href == self.active_css)
        page.evaluate('document.fonts.ready')
        if self.active_values:
            self.brand_values(page, name, self.active_values)
        self.check(name + '.no_horizontal_overflow', page.evaluate('document.documentElement.scrollWidth <= innerWidth + 1'))
        if signage:
            self.check(name + '.fits_screen', page.evaluate('document.documentElement.scrollHeight <= innerHeight + 1'))
        logos = page.locator('img.brand-logo:visible')
        self.check(name + '.single_logo', logos.count() == 1)
        if logos.count() == 1:
            src = logos.get_attribute('src')
            if self.active_logo is None:
                self.active_logo = src
            self.check(name + '.same_active_logo', bool(src) and src == self.active_logo)
            self.check(name + '.logo_dimensions', logos.evaluate('''(el, signage) => {
                const r = el.getBoundingClientRect(); return el.complete && el.naturalWidth > 0 &&
                  (signage ? r.height >= 36 && r.height <= 85 : [32,40].some(h => Math.abs(r.height-h) <= 1)) &&
                  r.left >= -1 && r.right <= innerWidth+1 && getComputedStyle(el).objectFit === 'contain';
            }''', signage))
        self.text_layout(page, name)
        missing = response.status == 404 or page.locator('main h1,main h2,.empty-title').filter(
            has_text=re.compile(r'(?:nicht|kein.*) verfügbar', re.I)).count() > 0
        self.data['observations'][name + '.plan_unavailable'] = missing
        if missing and name + '.published_plan_missing' not in self.data['unavailable']:
            self.data['unavailable'].append(name + '.published_plan_missing')
        if (path in PUBLIC or signage or path.startswith('/druck/')) and not missing:
            self.menu_evidence(page, path, name)
        if path in PUBLIC or signage or path.startswith('/druck/'):
            self.legends(page, name, signage=signage)
        if 'patienten' in path:
            self.check(name + '.patient_price_free', PATIENT_PRICE_VOCABULARY.search(page.locator('body').inner_text()) is None)
        self.data['observations'][name + '.closed_state_observed'] = page.locator(
            '.hero-food-closed, .public-closed').count() > 0 or page.get_by_role(
                'heading', name='Cafeteria geschlossen', exact=True).count() > 0
        self.shot(page, name, response.status)

    def text_layout(self, page: Page, name: str) -> None:
        self.check(name + '.no_clipped_text', page.locator('h1,h2,h3,h4,p,li,strong,small,.signage-tags,.food-legend span,.patient-board-components').evaluate_all('''els =>
          els.every(el => { const r = el.getBoundingClientRect(); if (!r.width || !r.height) return true;
            const clips = value => ['hidden','clip','auto','scroll'].includes(value), own = getComputedStyle(el);
            // Scroll dimensions alone do not imply clipping when overflow remains visible.
            if (el.clientWidth && ((clips(own.overflowX) && el.scrollWidth > el.clientWidth+1) ||
                (clips(own.overflowY) && el.scrollHeight > el.clientHeight+1))) return false;
            const range = document.createRange(); range.selectNodeContents(el);
            const rects = [r, ...range.getClientRects()];
            for (let a=el.parentElement;a;a=a.parentElement) { const s=getComputedStyle(a), b=a.getBoundingClientRect();
              const left=b.left+a.clientLeft, top=b.top+a.clientTop;
              if (clips(s.overflowX) && rects.some(t => t.left < left-1 || t.right > left+a.clientWidth+1)) return false;
              if (clips(s.overflowY) && rects.some(t => t.top < top-1 || t.bottom > top+a.clientHeight+1)) return false;
            } return true; })'''))

    def cards(self, page: Page, name: str, selector: str, expected: int) -> None:
        sizes = page.locator(selector + ':visible').evaluate_all('''els => els.map(el => {
            const r=el.getBoundingClientRect(); return [r.width,r.height,
              el.scrollWidth <= el.clientWidth+1 && el.scrollHeight <= el.clientHeight+1]; })''')
        self.check(name + '.menu_count', len(sizes) == expected)
        if sizes:
            self.check(name + '.equal_unclipped_cards', all(item[2] for item in sizes) and all(
                max(item[axis] for item in sizes) - min(item[axis] for item in sizes) <= 1 for axis in (0, 1)))
        self.data['observations'][name + '.visible_card_count'] = len(sizes)

    def menu_evidence(self, page: Page, path: str, name: str, *, second: bool = False) -> None:
        if path in SIGNAGE:
            index = SIGNAGE.index(path)
            selector, expected = MENU_SELECTORS[index], (2, 10, 4, 16 if second else 12)[index]
            if index in (1, 3) and page.locator('[data-signage-page]').count():
                groups = self.week_page_counts(page, path, name)
                visible_index = page.locator('[data-signage-page]').evaluate_all(
                    'nodes => nodes.findIndex(node => !node.hidden)')
                self.check(name + '.one_visible_page', page.locator('[data-signage-page]:visible').count() == 1)
                expected = groups[visible_index] if 0 <= visible_index < len(groups) else 0
        elif path in PUBLIC:
            selector, expected = '.card:has(> .card-status-top)', (2, 10, 4, 28)[PUBLIC.index(path)]
        else:
            selector, expected = '.week-menu:has([data-menu-metadata])', 28 if 'patienten' in path else 10
        closed = page.locator(':is(' + CLOSED + ',.public-menu-meal > .alert):visible').count()
        if not closed:
            closed = page.get_by_role('heading', name='Cafeteria geschlossen', exact=True).count()
        if path.startswith('/druck/patienten'):
            closed += page.locator('.week-menu-type').filter(has_text=re.compile('^Geschlossen$')).count()
        if closed:
            self.data['unavailable'].append(name + '.closed_services_limit_full_menu_proof')
        self.check(name + '.closed_service_count', closed <= expected // 2)
        self.cards(page, name, selector, max(0, expected - closed * 2))
        self.check(name + '.metadata_for_every_menu', page.locator('[data-menu-metadata]:visible').count()
                   == page.locator(selector + ':visible').count())

    def legends(self, page: Page, name: str, *, signage: bool = False) -> None:
        evidence = page.evaluate('''() => {
          const visible = e => e.checkVisibility({checkOpacity:true,checkVisibilityCSS:true});
          const read = e => ({text:e.innerText.trim(), image:e.querySelector('img')?.getAttribute('src') || '',
            kind:e.classList.contains('amber')?'allergens':e.classList.contains('green')?'labels':'countries'});
          const blocks = [...document.querySelectorAll('[data-menu-metadata]')].filter(visible);
          const legends = [...document.querySelectorAll('.food-legend')].filter(visible);
          return {metadata:blocks.flatMap(e=>[...e.querySelectorAll('.label')].filter(visible).map(read)),
            warnings:blocks.flatMap(e=>[...e.querySelectorAll('p')].filter(visible).map(e=>e.innerText.trim())),
            legends:legends.map(e=>({entries:[...e.querySelectorAll('.label')].map(read),
              warnings:[...e.querySelectorAll('p')].map(e=>e.innerText.trim())})),
            images:[...document.querySelectorAll('[data-menu-metadata] .food-symbol,.food-legend .food-symbol')]
              .filter(visible).map(e=>{const r=e.getBoundingClientRect(),s=getComputedStyle(e);return {
                loaded:e.complete&&e.naturalWidth>0, width:r.width,height:r.height,font:parseFloat(s.fontSize),
                country:e.getAttribute('src').includes('/flags/'),fit:s.objectFit,
                patientMetadata:!!e.closest('[data-menu-metadata]') && !!e.closest('.patient-board,.patient-duo')};}),
            legendFonts:legends.flatMap(e=>[e,...e.querySelectorAll('span,p,h2')]).filter(visible)
              .map(e=>parseFloat(getComputedStyle(e).fontSize))}; }''')
        expected: set[tuple[str, str]] = set()
        for entry in evidence['metadata']:
            text, source = entry['text'], entry['image']
            if entry['kind'] == 'countries':
                code = text.rsplit(':', 1)[-1].strip()
                row = next((row for row in self.catalog['countries'].values()
                            if source == '/static/vendor/food-symbols/' + row['file']), None)
                row = row or self.catalog['countries'].get(code)
                if row:
                    text, wanted = row['name'], '/static/vendor/food-symbols/' + row['file']
                    self.check(name + '.origin_symbol', source == wanted)
                elif re.fullmatch('[A-Z]{2}', code):
                    text = code
                else:
                    self.data['unavailable'].append(name + '.origin_text_not_independently_resolvable')
            expected.add((text, source))
        warnings = set(evidence['warnings']) & set(WARNINGS)
        wanted_count = int(bool(expected or warnings))
        self.check(name + '.legend_count', len(evidence['legends']) == wanted_count)
        actual = [entry for legend in evidence['legends'] for entry in legend['entries']]
        actual_pairs = [(entry['text'], entry['image']) for entry in actual]
        self.check(name + '.legend_matches_visible_metadata', set(actual_pairs) == expected and
                   len(actual_pairs) == len(expected) and
                   {value for legend in evidence['legends'] for value in legend['warnings']} == warnings)
        self.check(name + '.symbols_loaded_and_sized', all(image['loaded'] and image['fit'] == 'contain' and
                   image['height'] >= (1.2 if image['patientMetadata'] else 1.5) * image['font'] - 1 and
                   image['width'] >= ((1.6 if image['country'] else 1.2) if image['patientMetadata'] else
                                      (2 if image['country'] else 1.5)) * image['font'] - 1
                   for image in evidence['images']))
        if signage:
            self.check(name + '.legend_minimum_font', all(size >= 18 for size in evidence['legendFonts']))

    def brand_values(self, page: Page, name: str, values: dict[str, str]) -> None:
        tokens = {'primary': '--sh-primary', 'accent': '--sh-secondary', 'surface': '--sh-panel',
                  'text': '--sh-ink', 'font_body': '--sh-font', 'font_heading': '--sh-font-display'}
        actual = page.evaluate('''tokens => Object.fromEntries(Object.entries(tokens).map(([key,token]) =>
            [key,getComputedStyle(document.documentElement).getPropertyValue(token).trim().toLowerCase()]))''', tokens)
        self.check(name + '.active_colors', all(actual[key] == values[key].lower()
                   for key in ('primary', 'accent', 'surface', 'text')))
        self.check(name + '.active_fonts', all(actual[key].split(',')[0].strip('"\' ') ==
                   {'fira': 'fira sans', 'carlito': 'carlito'}[values[key]] for key in ('font_body', 'font_heading')))
        for selector, key in (('body', 'font_body'), ('h1:visible', 'font_heading')):
            font = page.locator(selector).first.evaluate('e => getComputedStyle(e).fontFamily')
            self.check(name + '.rendered_' + key, font.lower().split(',')[0].strip('"\' ') ==
                       {'fira': 'fira sans', 'carlito': 'carlito'}[values[key]])

    def outcome(self) -> tuple[str, int]:
        self.check('network.requests_complete', not self._pending_logos)
        if self.data['failures']:
            return 'failed', 1
        return ('incomplete', 2) if self.data['unavailable'] else ('browser_passed', 0)

    def week_page_counts(self, page: Page, path: str, name: str) -> tuple[int, ...]:
        """Declared rotation contracts, independent of rendered menu-card counts."""
        if path == SIGNAGE[3]:
            marker = page.locator('[data-signage-rotation]')
            rotation = marker.get_attribute('data-signage-rotation') if marker.count() == 1 else 'legacy'
            self.check(name + '.known_rotation', rotation in ('legacy', 'ops'))
            self.data['observations'][name + '.rotation'] = rotation
            return (8, 6, 8, 6) if rotation == 'ops' else (12, 16)
        days = page.locator('.cafe-week-day').count()
        self.check(name + '.cafeteria_day_count', days in (5, 6, 7))
        self.data['observations'][name + '.cafeteria_days'] = days
        return (8, 6) if days == 7 else (days * 2,)

    def patient_rotation(self, page: Page, name: str) -> None:
        self.week_rotation(page, SIGNAGE[3], name)

    def cafeteria_rotation(self, page: Page, name: str) -> None:
        self.week_rotation(page, SIGNAGE[1], name)

    def week_rotation(self, page: Page, path: str, name: str) -> None:
        pages = page.locator('[data-signage-page]')
        groups = self.week_page_counts(page, path, name)
        patient = path == SIGNAGE[3]
        contract = 'two_pages' if patient and len(groups) == 2 else 'four_pages' if patient else 'cafeteria_pages'
        self.check(name + '.' + contract, pages.count() == len(groups))
        if pages.count() != len(groups):
            return
        selector = MENU_SELECTORS[3 if patient else 1]
        closed = '.patient-board-closed' if patient else '.cafe-week-closed'
        self.check(name + ('.full_patient_week' if patient else '.full_cafeteria_week'),
                   page.locator(selector).count() + 2 * page.locator(closed).count() == sum(groups))
        self.check(name + '.first_page_visible', pages.evaluate_all(
            'nodes => nodes.every((node, index) => node.hidden === (index !== 0))'))
        for index in range(1, len(groups)):
            page.wait_for_function('''index => [...document.querySelectorAll('[data-signage-page]')]
                .findIndex(el => !el.hidden) === index''', arg=index, timeout=40000)
            label = name + f'-page{index + 1}'
            self.check(label + '.fits_screen', page.evaluate(
                'document.documentElement.scrollWidth <= innerWidth + 1 && document.documentElement.scrollHeight <= innerHeight + 1'))
            self.text_layout(page, label)
            self.menu_evidence(page, path, label, second=True)
            self.legends(page, label, signage=True)
            self.shot(page, label, 200)

    def shot(self, page: Page, name: str, status: int) -> None:
        path = self.outdir / f'{name}.png'
        content = page.screenshot(path=str(path), full_page=True)
        path.chmod(0o600)
        self.data['pages'].append({'name': name, 'http_status': status, 'screenshot': path.name,
                                   'sha256': hashlib.sha256(content).hexdigest()})

    def editor(self, page: Page, width: int) -> None:
        name = f'admin-{width}'
        self.capture(page, EDITOR, name)
        active = page.locator('.list-group-item').filter(has=page.locator('span', has_text=re.compile('^Aktiv$')))
        self.check(name + '.one_active_revision', active.count() == 1)
        href = active.get_attribute('href') if active.count() == 1 else ''
        match = re.fullmatch(re.escape(EDITOR) + r'\?revision=(\d+)', href or '')
        if not match:
            raise RuntimeError('active_revision_not_identified')
        self.check(name + '.active_revision_identity', self.active_css == '/branding/revisions/' + match[1] + '.css')
        for field in ('name', 'logo-select', 'upload', 'primary', 'accent', 'surface', 'text', 'font_body', 'font_heading'):
            self.check(name + '.field_' + field, page.locator('#brand-' + field).count() == 1)
        self.check(name + '.revision_history', page.locator('.list-group-item[aria-current="true"]').count() == 1)
        self.check(name + '.active_status', page.locator('.brand-status[role="status"]').count() == 1)
        self.check(name + '.actions_present', all(page.locator(f'button[value="{action}"]').count() == 1
                                                for action in ('save', 'activate', 'restore', 'reset')))
        frame = page.locator('iframe.brand-preview-frame')
        self.check(name + '.preview_present', frame.count() == 1)
        if frame.count() == 1:
            preview = frame.content_frame
            self.check(name + '.preview_loaded', preview.locator('h1').inner_text() == 'Frisch zubereitet')
            self.check(name + '.preview_logo', preview.locator('img.brand-logo').evaluate(
                'el => el.complete && el.naturalWidth > 0 && Math.abs(el.getBoundingClientRect().height-40) <= 1'))
        self.capture(page, match[0], name + '-active')
        self.active_values = {key: page.locator('#brand-' + key).input_value() for key in
                              ('primary', 'accent', 'surface', 'text', 'font_body', 'font_heading')}
        logo = page.locator('#brand-logo-select').input_value()
        self.check(name + '.active_logo_identity', self.active_logo ==
                   ('/branding/logos/' + logo + '.png' if logo else '/static/img/suedhang-logo.png'))
        self.brand_values(page, name, self.active_values)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--base-url', choices=(BASE_URL,), default=BASE_URL)
    parser.add_argument('--outdir', required=True, type=Path, help='New private artifact directory')
    args = parser.parse_args()
    os.umask(0o077)
    args.outdir.mkdir(mode=0o700, parents=True, exist_ok=False)
    proof = BrandingProof(args.base_url, args.outdir)
    stage = 'login'
    try:
        os.environ.pop('DEBUG', None)
        os.environ.pop('PWDEBUG', None)
        with sync_playwright() as playwright:
            with playwright.chromium.launch(executable_path='/opt/google/chrome/chrome',
                                             args=['--no-sandbox', '--disable-dev-shm-usage']) as browser:
                with browser.new_context(service_workers='block') as auth:
                    proof.login(auth, proof.configure(auth))
                    state = auth.storage_state()  # Never persist this state or form contents.
                for width in (390, 820, 1440):
                    stage = f'admin-{width}'
                    with browser.new_context(storage_state=state, viewport={'width': width, 'height': 1100},
                                             locale='de-CH', service_workers='block') as context:
                        proof.editor(proof.configure(context), width)
                    with browser.new_context(viewport={'width': width, 'height': 1100}, locale='de-CH',
                                             service_workers='block') as context:
                        page = proof.configure(context)
                        for path in (*PUBLIC, *AUX):
                            stage = f'{width}-' + path.strip('/').replace('/', '-')
                            proof.capture(page, path, stage)
                for width, height in ((1920, 1080), (3840, 2160)):
                    with browser.new_context(viewport={'width': width, 'height': height}, locale='de-CH',
                                             service_workers='block') as context:
                        page = proof.configure(context)
                        for path in SIGNAGE:
                            stage = f'{width}-' + path.strip('/').replace('/', '-')
                            proof.capture(page, path, stage, signage=True)
                            if path == SIGNAGE[3] and not proof.data['observations'].get(stage + '.plan_unavailable'):
                                proof.patient_rotation(page, stage)
                            if path == SIGNAGE[1] and not proof.data['observations'].get(stage + '.plan_unavailable'):
                                proof.cafeteria_rotation(page, stage)
        proof.check('assets.public_css_observed', 'public.css' in proof.assets)
        proof.check('assets.preview_css_observed', 'preview.css' in proof.assets)
        proof.data['observed_assets'] = sorted(proof.assets)
        for key in ('public.logo', 'preview.logo', 'standard.logo'):
            if key not in proof.assets:
                proof.data['coverage_limits'].append(key + '.not_used_by_current_live_revisions')
        proof.data['coverage_limits'].append('Closed/unavailable states are covered only when returned by real live routes.')
    except Exception as error:
        # Exception messages, DOM, request data, credentials, cookies, traces and videos stay out of reports.
        proof.data['failures'].append(f'{stage}.{type(error).__name__}')
    status, exit_code = proof.outcome()
    proof.data['status'] = status
    report = args.outdir / 'proof.json'
    report.write_text(json.dumps(proof.data, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
    report.chmod(0o600)
    print(f'{status}: {report}; PDF acceptance requires the separate fresh runner')
    return exit_code


if __name__ == '__main__':
    raise SystemExit(main())
