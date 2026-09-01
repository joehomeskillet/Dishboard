#!/usr/bin/env python3
"""Rendert alle statischen Designprototypen reproduzierbar mit Chromium."""
from __future__ import annotations

import argparse
import shutil
from dataclasses import dataclass
from pathlib import Path

from playwright.sync_api import sync_playwright


@dataclass(frozen=True)
class Capture:
    source: str
    target: str
    width: int
    height: int
    full_page: bool = False


CAPTURES = (
    Capture('signage-cafeteria-tag.html', 'signage-cafeteria-tag-1920x1080.png', 1920, 1080),
    Capture('signage-cafeteria-woche.html', 'signage-cafeteria-woche-1920x1080.png', 1920, 1080),
    Capture('signage-cafeteria-geschlossen.html', 'signage-cafeteria-geschlossen-1920x1080.png', 1920, 1080),
    Capture('signage-patienten-tag.html', 'signage-patienten-tag-1920x1080.png', 1920, 1080),
    Capture('signage-patienten-woche.html', 'signage-patienten-woche-1920x1080-vorschau.png', 1920, 1080),
    Capture('signage-patienten-woche.html', 'signage-patienten-woche-3840x2160.png', 3840, 2160),
    Capture('cafeteria-heute.html', 'mobile-cafeteria-heute-390x844.png', 390, 844),
    Capture('cafeteria-woche.html', 'mobile-cafeteria-woche-390x844.png', 390, 844),
    Capture('patienten-heute.html', 'mobile-patienten-heute-390x844.png', 390, 844),
    Capture('patienten-woche.html', 'mobile-patienten-woche-390x844.png', 390, 844),
    Capture('cafeteria-woche.html', 'website-cafeteria-woche-1440x1100.png', 1440, 1100),
    Capture('patienten-woche.html', 'website-patienten-woche-1440x1100.png', 1440, 1100),
    Capture('admin-cafeteria.html', 'admin-cafeteria-1440x900.png', 1440, 900),
    Capture('admin-patienten.html', 'admin-patienten-1440x900.png', 1440, 900),
)


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument('--root', type=Path, default=Path(__file__).resolve().parents[1])
    parser.add_argument('--browser-path', type=Path, help='Optionaler Pfad zu Chromium/Chrome.')
    args = parser.parse_args()
    root = args.root.resolve()
    prototype = root / 'design' / 'prototype'
    output = root / 'design' / 'screenshots'
    output.mkdir(parents=True, exist_ok=True)

    css = (prototype / 'assets' / 'app.css').read_text(encoding='utf-8')

    browser_path = str(args.browser_path.resolve()) if args.browser_path else (
        shutil.which('chromium') or shutil.which('chromium-browser') or shutil.which('google-chrome')
    )
    launch_options = {
        'headless': True,
        'args': ['--no-sandbox', '--disable-dev-shm-usage', '--font-render-hinting=none'],
    }
    if browser_path:
        launch_options['executable_path'] = browser_path

    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(**launch_options)
        try:
            for capture in CAPTURES:
                source = prototype / capture.source
                if not source.is_file():
                    raise FileNotFoundError(source)
                html = source.read_text(encoding='utf-8')
                html = html.replace(
                    '<link rel="stylesheet" href="assets/app.css">',
                    f'<style>{css}</style>',
                )
                html = html.replace('<meta http-equiv="refresh" content="300">', '')
                context = browser.new_context(
                    viewport={'width': capture.width, 'height': capture.height},
                    device_scale_factor=1,
                    locale='de-CH',
                    color_scheme='light',
                )
                page = context.new_page()
                page.set_content(html, wait_until='load')
                page.emulate_media(reduced_motion='reduce')
                page.screenshot(
                    path=str(output / capture.target),
                    full_page=capture.full_page,
                    animations='disabled',
                )
                context.close()
                print(f'{capture.target}: {capture.width}x{capture.height}')
        finally:
            browser.close()

    # Kompatibilitätsnamen aus dem bisherigen Paket.
    shutil.copyfile(output / 'signage-cafeteria-tag-1920x1080.png', output / 'signage-1920x1080.png')
    shutil.copyfile(output / 'mobile-cafeteria-heute-390x844.png', output / 'mobile-390x844.png')
    shutil.copyfile(output / 'admin-cafeteria-1440x900.png', output / 'admin-1440x900.png')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
