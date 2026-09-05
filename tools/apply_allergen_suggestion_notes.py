#!/usr/bin/env python3
"""Bounded week-36 recipe notes. Default dry run; --apply enables menu Save only."""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import subprocess
from collections import Counter
from dataclasses import dataclass
from datetime import date, timedelta
from pathlib import Path
from typing import Any
from urllib.parse import parse_qsl, urlencode, urljoin, urlsplit

from capture_admin_live_proof import USER, _password
from playwright.sync_api import APIRequestContext, APIResponse, Page, Route, sync_playwright

BASE = 'https://dishboard.joelduss.xyz'
WEEK = '2026-08-31'
DOCUMENT = Path(__file__).resolve().parents[1] / 'docs/superpowers/allergen-proposals-0905.md'
DOCUMENT_SHA256 = 'b53f771cbb49df7b621be6acd7faf4a4cd21dbe5624365e11332e168da107865'
SQL = """BEGIN READ ONLY;
SELECT jsonb_agg(x ORDER BY x.id) FROM (
 SELECT i.id,p.code AS profile,w.week_start AS week,s.service_date AS day,
 mp.code AS meal,mt.code AS option,i.title,COALESCE(i.note,'') AS note,
 i.allergen_review_status AS review,i.row_version AS version,
 ARRAY(SELECT c.component_text FROM cafeteria.menu_item_components c
       WHERE c.menu_item_id=i.id ORDER BY c.sort_order) AS components,
 jsonb_build_object(
 'item',to_jsonb(i)-'note'-'allergen_review_status'-'row_version'-'updated_at'-'created_at',
 'location',w.location_id,'week_id',w.id,'service_id',s.id,'service_state',s.service_state,
 'links',(SELECT jsonb_agg(to_jsonb(c) ORDER BY c.sort_order)
          FROM cafeteria.menu_item_components c WHERE c.menu_item_id=i.id),
 'allergens',(SELECT jsonb_agg(to_jsonb(a) ORDER BY a.allergen_id,a.presence)
              FROM cafeteria.menu_item_allergens a WHERE a.menu_item_id=i.id),
 'labels',(SELECT jsonb_agg(to_jsonb(l) ORDER BY l.label_id)
           FROM cafeteria.menu_item_labels l WHERE l.menu_item_id=i.id),
 'origins',(SELECT jsonb_agg(to_jsonb(o)-'id'-'created_at'-'updated_at' ORDER BY o.ingredient)
            FROM cafeteria.origin_declarations o WHERE o.menu_item_id=i.id),
 'prices',(SELECT jsonb_agg(to_jsonb(pr)-'created_at'-'updated_at')
           FROM cafeteria.menu_item_prices pr WHERE pr.menu_item_id=i.id)) AS state
 FROM cafeteria.menu_items i JOIN cafeteria.menu_services s ON s.id=i.service_id
 JOIN cafeteria.menu_weeks w ON w.id=s.menu_week_id
 JOIN cafeteria.offer_profiles p ON p.id=w.profile_id
 JOIN cafeteria.meal_periods mp ON mp.id=s.meal_period_id
 JOIN cafeteria.menu_types mt ON mt.id=i.menu_type_id
 WHERE i.id BETWEEN 77 AND 114
) x;
COMMIT;"""
FORM_DATA = '(form) => [...new FormData(form)].map(([k,v]) => [k,String(v)])'


@dataclass(frozen=True)
class Proposal:
    id: int
    day: str
    profile: str
    meal: str
    option: str
    title: str
    components: tuple[str, ...]
    note: str

    @property
    def action(self) -> str:
        family = 'cafeteria' if self.profile == 'staff_guest' else 'patienten'
        return f'{BASE}/admin/{family}/menu'

    @property
    def url(self) -> str:
        return self.action + '?' + urlencode({
            'week': WEEK, 'day': self.day, 'meal': self.meal, 'option': self.option,
        })


def parse_proposals(raw: bytes) -> list[Proposal]:
    if hashlib.sha256(raw).hexdigest() != DOCUMENT_SHA256:
        raise ValueError('proposal_document_changed')
    rows = []
    for line in raw.decode('utf-8').splitlines():
        cells = [part.strip() for part in line.split('|')]
        if len(cells) != 7 or not cells[1].isdigit():
            continue
        profile, meal, option = cells[3].split(' / ')
        title, components = cells[4].split('; ')
        rows.append(Proposal(int(cells[1]), cells[2], profile, meal, option, title,
                             tuple(components.split(', ')), cells[5]))
    if [row.id for row in rows] != list(range(77, 115)):
        raise ValueError('proposal_ids_invalid')
    for row in rows:
        index = row.id - (77 if row.id < 87 else 87)
        expected_day = date.fromisoformat(WEEK) + timedelta(days=index // (2 if row.id < 87 else 4))
        if (row.day != expected_day.isoformat()
                or row.profile != ('staff_guest' if row.id < 87 else 'patient')
                or row.option != ('MENU_1' if index % 2 == 0 else 'VEGGIE')
                or row.meal != ('LUNCH' if row.id < 87 or index % 4 < 2 else 'DINNER')):
            raise ValueError('proposal_slot_invalid')
    return rows


def classify(proposal: Proposal, row: dict[str, Any]) -> str:
    if proposal.id == 108:
        return 'skipped_checked'
    expected = {key: getattr(proposal, key) for key in ('id', 'day', 'profile', 'meal', 'option', 'title')}
    expected.update(week=WEEK, components=list(proposal.components))
    if any(row.get(key) != value for key, value in expected.items()):
        return 'conflict'
    if row.get('note') == proposal.note:
        return 'already_present'
    if row.get('note') != '' or row.get('review') != 'not_checked' or row.get('version') != 4:
        return 'conflict'
    return 'eligible'


def verified_save(proposal: Proposal, before: dict[str, Any], after: dict[str, Any]) -> bool:
    ignored = {'note', 'review', 'version'}
    return (after.get('note') == proposal.note and after.get('review') == 'not_checked'
            and isinstance(after.get('version'), int) and after['version'] > before['version']
            and {k: v for k, v in before.items() if k not in ignored}
            == {k: v for k, v in after.items() if k not in ignored})


def form_unchanged(before: list[list[str]], after: list[list[str]], note: str) -> bool:
    ignored = {'_csrf', 'row_version', 'note'}
    return ([v for k, v in after if k == 'note'] == [note]
            and [(k, v) for k, v in before if k not in ignored]
            == [(k, v) for k, v in after if k not in ignored])


class NetworkGate:
    def __init__(self) -> None:
        self.login_pending = True
        self.pending: tuple[str, list[tuple[str, str]]] | None = None
        self.blocked = False

    def allow(self, method: str, url: str, body: str = '') -> bool:
        parsed = urlsplit(url)
        if (parsed.scheme != 'https' or parsed.netloc != 'dishboard.joelduss.xyz'
                or parsed.username or parsed.password or parsed.fragment):
            return False
        if method in {'GET', 'HEAD'}:
            return (parsed.path in {'/auth/local', '/admin', '/admin/',
                    '/admin/cafeteria', '/admin/patienten',
                    '/admin/cafeteria/menu', '/admin/patienten/menu'}
                    or parsed.path.startswith('/static/'))
        if method == 'POST' and url == BASE + '/auth/local' and self.login_pending:
            self.login_pending = False
            return True
        if method == 'POST' and self.pending is not None:
            action, expected = self.pending
            if url == action and parse_qsl(body, keep_blank_values=True) == expected:
                self.pending = None
                return True
        return False

    def allow_redirect(self, method: str, from_url: str, status: int, location: str) -> bool:
        if method != 'POST' or not location:
            return False
        target = urljoin(from_url, location)
        if not self.allow('GET', target):
            return False
        if from_url == BASE + '/auth/local':
            return status == 302 and target == BASE + '/admin/cafeteria'
        return status == 303 and urlsplit(target).path == urlsplit(from_url).path

    def post(self, request: APIRequestContext, url: str, data: list[list[str]]) -> APIResponse:
        # Browser route hooks do not govern API requests: authorize before transmission.
        body = urlencode([(key, value) for key, value in data])
        if self.blocked or not self.allow('POST', url, body):
            self.blocked = True
            raise RuntimeError('post_not_authorized')
        try:
            response = request.post(
                url, data=body, max_redirects=0, max_retries=0, timeout=15000,
                headers={'Content-Type': 'application/x-www-form-urlencoded',
                         'Origin': BASE, 'Referer': url},
            )
        except Exception:
            self.blocked = True
            raise RuntimeError('post_failed_or_uncertain') from None
        if 300 <= response.status < 400 and not self.allow_redirect(
                'POST', url, response.status, response.headers.get('location', '')):
            self.blocked = True
            raise RuntimeError('post_redirect_rejected')
        return response

    def route(self, route: Route) -> None:
        request = route.request
        if self.blocked or request.method not in {'GET', 'HEAD'} or not self.allow(request.method, request.url):
            self.blocked = True
            route.abort()
            return
        try:
            response = route.fetch(max_redirects=0)
        except Exception:
            self.blocked = True
            route.abort()
            return
        # Never hand a 3xx back to Chromium: it can follow without another route hook.
        if 300 <= response.status < 400:
            self.blocked = True
            route.abort()
            return
        route.fulfill(response=response)


def read_rows() -> dict[int, dict[str, Any]]:
    command = ['rtk', 'docker', 'compose', 'exec', '-T', 'db', 'psql', '-U',
               'cafeteria_owner', '-d', 'cafeteria', '-X', '-qAt', '-v', 'ON_ERROR_STOP=1', '-c', SQL]
    for attempt in range(2):
        try:
            result = subprocess.run(command, cwd='/srv/dishboard/app/deployment',
                                    capture_output=True, text=True, timeout=30, check=False)
        except subprocess.TimeoutExpired:
            result = None
        if result is not None and result.returncode == 0:
            values = json.loads(result.stdout)
            return {row['id']: row for row in values or []}
        if attempt == 1:
            raise RuntimeError('read_only_snapshot_failed_twice')
    raise RuntimeError('snapshot_unavailable')


def load_form(page: Page, proposal: Proposal) -> tuple[Any, list[list[str]]]:
    response = page.goto(proposal.url, wait_until='load')
    if response is None or response.status != 200 or page.url != proposal.url:
        raise RuntimeError('menu_get_failed')
    form = page.locator(f'form[data-menu-editor][action="{urlsplit(proposal.action).path}"]')
    if form.count() != 1:
        raise RuntimeError('menu_form_missing')
    return form, form.evaluate(FORM_DATA)


def form_matches(proposal: Proposal, data: list[list[str]], page: Page) -> bool:
    expected = {'week': WEEK, 'day': proposal.day, 'meal': proposal.meal,
                'option': proposal.option, 'title': proposal.title, 'row_version': '4', 'note': ''}
    if any([v for k, v in data if k == key] != [value] for key, value in expected.items()):
        return False
    main = page.locator('main[data-profile][data-week]')
    if (main.count() != 1 or main.get_attribute('data-profile') != proposal.profile
            or main.get_attribute('data-week') != WEEK):
        return False
    components = page.locator('form[data-menu-editor] #components-list .component-row').evaluate_all(
        "rows => rows.map(r => {const s=r.querySelector('select'); return s.value ? "
        "s.selectedOptions[0].textContent.trim() : r.querySelector('input').value;})")
    return components == list(proposal.components)


def process(page: Page, gate: NetworkGate, proposal: Proposal, apply: bool) -> str:
    before = read_rows().get(proposal.id, {})
    decision = classify(proposal, before)
    if decision != 'eligible':
        return decision
    form, data = load_form(page, proposal)
    if gate.blocked:
        raise RuntimeError('network_request_blocked')
    if not form_matches(proposal, data, page):
        return 'conflict'
    latest = read_rows().get(proposal.id, {})
    if latest != before or classify(proposal, latest) != 'eligible':
        return 'conflict'
    if not apply:
        return 'would_save'
    form.locator('[name="note"]').fill(proposal.note)
    changed = form.evaluate(FORM_DATA)
    if not form_unchanged(data, changed, proposal.note):
        raise RuntimeError('form_mutation_detected')
    gate.pending = (proposal.action, [tuple(pair) for pair in changed])
    try:
        saved = gate.post(page.context.request, proposal.action, changed)
    finally:
        gate.pending = None
    if saved.status == 409:
        return 'conflict'
    if gate.blocked or saved.status != 303:
        raise RuntimeError('save_failed_or_uncertain')
    _, after_data = load_form(page, proposal)
    after = read_rows().get(proposal.id, {})
    if not form_unchanged(data, after_data, proposal.note) or not verified_save(proposal, before, after):
        raise RuntimeError('saved_state_mismatch')
    return 'saved'


def login(page: Page, gate: NetworkGate) -> None:
    login_url = BASE + '/auth/local'
    response = page.goto(login_url, wait_until='load')
    if gate.blocked or response is None or response.status != 200 or page.url != login_url:
        raise RuntimeError('login_page_failed')
    form = page.locator('form[method="post"][action="/auth/local"]')
    if form.count() != 1:
        raise RuntimeError('login_form_missing')
    form.locator('[name="username"]').fill(USER)
    form.locator('[name="password"]').fill(_password())
    response = gate.post(page.context.request, login_url, form.evaluate(FORM_DATA))
    if gate.blocked or response.status != 302:
        raise RuntimeError('login_failed')
    # Discard Location; cookies are shared with context.request. Navigate only here.
    overview = BASE + '/admin/cafeteria'
    response = page.goto(overview, wait_until='load')
    if (gate.blocked or response is None or response.status != 200 or page.url != overview
            or page.locator('main[data-profile="staff_guest"]').count() != 1):
        raise RuntimeError('login_failed')


def arguments(argv: list[str] | None = None) -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--apply', action='store_true')
    parser.add_argument('--report', type=Path, required=True, help='New JSON report path; never overwritten')
    return parser.parse_args(argv)


def main() -> int:
    args = arguments()
    report: dict[str, Any] = {'mode': 'apply' if args.apply else 'dry_run', 'items': [], 'status': 'running'}
    # Disable Playwright debug channels before ever obtaining a password.
    os.environ.pop('DEBUG', None)
    os.environ.pop('PWDEBUG', None)
    descriptor = os.open(args.report, os.O_WRONLY | os.O_CREAT | os.O_EXCL, 0o600)
    with os.fdopen(descriptor, 'w', encoding='utf-8') as artifact:
        def checkpoint() -> None:
            report['counts'] = dict(Counter(item['status'] for item in report['items']))
            artifact.seek(0)
            artifact.truncate()
            json.dump(report, artifact, ensure_ascii=False, indent=2)
            artifact.flush()
        current_id = None
        try:
            proposals = parse_proposals(DOCUMENT.read_bytes())
            with sync_playwright() as playwright:
                with playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage']) as browser:
                    with browser.new_context(service_workers='block') as context:
                        context.set_default_timeout(15000)
                        gate = NetworkGate()
                        context.route('**/*', gate.route)
                        page = context.new_page()
                        login(page, gate)
                        for proposal in proposals:
                            current_id = proposal.id
                            status = process(page, gate, proposal, args.apply)
                            report['items'].append({'id': current_id, 'status': status})
                            checkpoint()
            report['status'] = 'completed'
        except Exception as error:
            # Exception text, HTTP payloads, credentials and cookies never enter artifacts.
            report.update(status='stopped', error_type=type(error).__name__, stopped_id=current_id)
        checkpoint()
    print(json.dumps({'status': report['status'], 'counts': report['counts']}))
    return 0 if report['status'] == 'completed' else 1


if __name__ == '__main__':
    raise SystemExit(main())
