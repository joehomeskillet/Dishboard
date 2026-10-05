#!/usr/bin/env python3
"""Operator-only live diagnostic: JSONL image metadata, no bodies or credentials.

Uses the unchanged fixed-origin login helper and its GET/HEAD browser guard.
Only the helper's official login POST may write. Exit 2 means missing evidence
or runner failure; exit 1 preserves a failing source proof; exit 0 means observed.
"""
from __future__ import annotations

import json
import os
import re
from pathlib import Path
from tempfile import TemporaryDirectory
from typing import Any
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import BrowserContext, Request, Response, sync_playwright

from capture_branding_live_proof import BASE_URL, EDITOR, BrandingProof

LOGO_PATHS = frozenset(('/static/img/suedhang-logo.png', '/static/img/suedhang-logo@2x.png'))


def logo_path(url: str) -> str | None:
    target = urlsplit(url)
    return target.path if f'{target.scheme}://{target.netloc}' == BASE_URL and target.path in LOGO_PATHS else None


def emit(data: dict[str, Any]) -> None:
    print(json.dumps(data, ensure_ascii=True, sort_keys=True), flush=True)


class LogoEvents:
    def __init__(self) -> None:
        self.phase = 'login'
        self.requests: dict[Request, dict[str, Any]] = {}
        self.finished: set[Request] = set()

    def attach(self, context: BrowserContext) -> None:
        context.on('request', self.request)
        context.on('response', self.response)
        context.on('requestfinished', lambda request: self.terminal(request, 'requestfinished'))
        context.on('requestfailed', lambda request: self.terminal(request, 'requestfailed'))

    def request(self, request: Request) -> None:
        path = logo_path(request.url)
        if path is None or request in self.requests:
            return
        self.requests[request] = {
            'request_id': len(self.requests) + 1, 'started_phase': self.phase,
            'path': path, 'method': request.method, 'resource_type': request.resource_type,
            'status': None, 'content_type': None, 'content_type_present': None,
            'redirected_from_logo': logo_path(request.redirected_from.url) if request.redirected_from else None,
        }
        self.write(request, 'request')

    def write(self, request: Request, event: str, **extra: Any) -> None:
        emit({'event': event, 'phase': self.phase, **self.requests[request], **extra})

    def response(self, response: Response) -> None:
        request = response.request
        if logo_path(request.url) is None:
            return
        self.request(request)
        headers = response.headers
        location = headers.get('location')
        target = urljoin(response.url, location) if location else ''
        destination = urlsplit(target)
        self.requests[request].update(
            status=response.status, content_type=headers.get('content-type'),
            content_type_present='content-type' in headers,
        )
        self.write(request, 'response', from_service_worker=response.from_service_worker,
                   redirect_present=location is not None, redirect_to_logo=logo_path(target),
                   redirect_external=bool(target) and f'{destination.scheme}://{destination.netloc}' != BASE_URL)

    def terminal(self, request: Request, event: str) -> None:
        if logo_path(request.url) is None:
            return
        self.request(request)
        self.finished.add(request)
        # Browser error strings may contain URLs; only emit the stable Chromium error code.
        failure = re.search(r'\bnet::ERR_[A-Z_]+\b', request.failure or '') if event == 'requestfailed' else None
        self.write(request, event, failure_code=failure.group() if failure else
                   'other' if event == 'requestfailed' else None)


def main() -> int:
    os.umask(0o077)
    events = LogoEvents()
    try:
        with TemporaryDirectory(prefix='dishboard-logo-diagnostic-') as directory:
            proof = BrandingProof(BASE_URL, Path(directory))
            with sync_playwright() as playwright:
                with playwright.chromium.launch(executable_path='/opt/google/chrome/chrome',
                                                args=['--no-sandbox']) as browser:
                    with browser.new_context(service_workers='block') as context:
                        events.attach(context)
                        page = proof.configure(context)
                        proof.login(context, page)
                        events.phase = 'branding_editor'
                        response = page.goto(BASE_URL + EDITOR, wait_until='networkidle')
                        if response is None or response.status != 200 or page.url != BASE_URL + EDITOR:
                            raise RuntimeError('editor_unavailable')
                        pending = len(events.requests.keys() - events.finished)
                        observed = bool(events.requests) and pending == 0 and all(
                            item['status'] is not None for item in events.requests.values())
                        code = 2 if not observed else 1 if proof.data['failures'] else 0
                        emit({'event': 'image_summary', 'phase': events.phase,
                              'image_requests': len(events.requests), 'image_pending': pending,
                              'source_http_mime_check': proof.data['checks'].get('assets.standard.logo.http_mime'),
                              'exit_code': code})
                        events.phase = 'closing'
            return code
    except Exception as error:
        # Never serialize exception messages, form data, cookies, request headers or tracebacks.
        emit({'event': 'diagnostic_error', 'phase': events.phase, 'error_type': type(error).__name__, 'exit_code': 2})
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
