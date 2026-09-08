#!/usr/bin/env python3
"""Capture public routes with project HTTP fixtures and optional read-only live URLs."""
from __future__ import annotations

import argparse
import hashlib
import json
import logging
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--source-root', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    parser.add_argument('--live-url')
    args = parser.parse_args()
    root = args.source_root.resolve()
    output = args.output.resolve()
    output.mkdir(parents=True, exist_ok=True)
    sys.path[:0] = [str(root / 'reference_scaffold/tests'), str(root / 'reference_scaffold'), str(root / 'tools')]
    from test_public_mobile_ui import http_app, public_server
    from test_rendered_ui import app, browser

    logging.getLogger('werkzeug').setLevel(logging.ERROR)
    routes = [
        ('cafeteria-heute', '/cafeteria/heute/', [(1440, 1100), (390, 844)]),
        ('cafeteria-woche', '/cafeteria/wochenangebot/', [(1440, 1100), (390, 844)]),
        ('patienten-heute', '/patienten/heute/', [(1440, 1100), (390, 844)]),
        ('patienten-woche', '/patienten/wochenplan/', [(1440, 1100), (390, 844)]),
        ('signage-cafeteria-tag', '/signage/cafeteria/tag', [(1920, 1080), (3840, 2160)]),
        ('signage-cafeteria-woche', '/signage/cafeteria/woche', [(1920, 1080), (3840, 2160)]),
        ('signage-patienten-tag', '/signage/patienten/tag', [(1920, 1080), (3840, 2160)]),
        ('signage-patienten-woche', '/signage/patienten/woche', [(1920, 1080), (3840, 2160)]),
    ]
    results = []
    monkeypatch = pytest.MonkeyPatch()
    application = http_app.__wrapped__(app.__wrapped__(monkeypatch), monkeypatch)
    server_fixture = public_server.__wrapped__(application)
    fixture_url = next(server_fixture)
    browser_fixture = browser.__wrapped__()
    instance = next(browser_fixture)
    try:
        sources = [('fixture', fixture_url)]
        if args.live_url:
            sources.append(('live', args.live_url.rstrip('/')))
        for source, base_url in sources:
            for name, route, viewports in routes:
                for width, height in viewports:
                    errors: list[str] = []
                    failed_requests: list[str] = []
                    with instance.new_context(viewport={'width': width, 'height': height}, locale='de-CH') as context:
                        page = context.new_page()
                        page.on('pageerror', lambda error: errors.append(str(error)))
                        page.on('console', lambda message: errors.append(message.text) if message.type == 'error' else None)
                        page.on('requestfailed', lambda request: failed_requests.append(request.url))
                        page.on('response', lambda response: failed_requests.append(f'{response.status}: {response.url}') if response.status >= 400 else None)
                        response = page.goto(base_url + route, wait_until='networkidle')
                        page.evaluate('document.fonts.ready')
                        page.emulate_media(reduced_motion='reduce')
                        filename = f'{source}-{name}-{width}x{height}.png'
                        page.screenshot(path=str(output / filename), full_page=False, animations='disabled')
                        if not name.startswith('signage-'):
                            for position in range(0, page.evaluate('document.documentElement.scrollHeight'), height):
                                page.evaluate('(position) => scrollTo(0, position)', position)
                                page.wait_for_timeout(60)
                            page.evaluate('scrollTo(0, 0)')
                            page.wait_for_load_state('networkidle')
                            page.screenshot(path=str(output / f'{source}-{name}-{width}x{height}-full.png'), full_page=True, animations='disabled')
                        if source == 'fixture' and name == 'cafeteria-heute' and width == 1440:
                            page.locator('.card:has(> .card-status-top)').first.screenshot(path=str(output / 'fixture-card-corner.png'))
                        metrics = page.evaluate('''() => ({
                            viewport: [innerWidth, innerHeight],
                            document: [document.documentElement.scrollWidth, document.documentElement.scrollHeight],
                            background: getComputedStyle(document.body).backgroundColor,
                            backgroundImage: getComputedStyle(document.body).backgroundImage,
                            cards: [...document.querySelectorAll('.card:has(> .card-status-top), .signage-menu-card')].map(el => ({
                                radius: getComputedStyle(el).borderRadius, overflow: getComputedStyle(el).overflow,
                                height: el.getBoundingClientRect().height, width: el.getBoundingClientRect().width
                            })),
                            headings: [...document.querySelectorAll('h1,h2')].map(el => el.textContent.trim()),
                            imagesMissing: [...document.images].filter(el => !el.complete || !el.naturalWidth).map(el => el.src),
                            patientPriceText: /CHF|Rappen|Intern|Extern/.test(document.body.innerText)
                        })''')
                        result = dict(source=source, route=route, screenshot=filename,
                                      captured_at=datetime.now(timezone.utc).isoformat(),
                                      http_status=response.status if response else None,
                                      csp=response.headers.get('content-security-policy') if response else None,
                                      snapshot_revision=response.headers.get('x-snapshot-revision') if response else None,
                                      set_cookie=bool(response and 'set-cookie' in response.headers),
                                      errors=errors, failed_requests=failed_requests, metrics=metrics,
                                      sha256=hashlib.sha256((output / filename).read_bytes()).hexdigest())
                        results.append(result)
                        print(f'{filename}: HTTP {result["http_status"]}; errors={len(errors)}; missing_images={len(metrics["imagesMissing"])}', flush=True)
    finally:
        browser_fixture.close()
        server_fixture.close()
        monkeypatch.undo()
        (output / 'metrics.json').write_text(json.dumps({'source_root': str(root), 'results': results}, indent=2) + '\n')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
