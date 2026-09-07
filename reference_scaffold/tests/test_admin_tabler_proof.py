"""The shared auditor must enforce stylesheet provenance even with positive evidence."""
from __future__ import annotations

import sys
from pathlib import Path
from urllib.parse import urljoin

import pytest
from playwright.sync_api import Browser

from test_rendered_ui import browser  # noqa: F401

sys.path.insert(0, str(Path(__file__).resolve().parents[2] / 'tools'))
from admin_tabler_proof import audit_tabler  # noqa: E402


@pytest.mark.parametrize(('url', 'script', 'allowed'), [
    ('/branding/revisions/1.css', False, True),
    ('/branding/revisions/12.css', False, True),
    ('https://dishboard.example.invalid/branding/revisions/1.css', False, True),
    ('/branding/revisions/1.css', True, False),
    ('https://other.invalid/branding/revisions/1.css', False, False),
    ('/branding/revisions/0.css', False, False),
    ('/branding/revisions/01.css', False, False),
    ('/branding/revisions/-1.css', False, False),
    ('/branding/revisions/١.css', False, False),
    ('/branding/revisions/1.css?preview=1', False, False),
    ('/branding/revisions/1.css#fragment', False, False),
    ('/branding/revisions/1.css/extra', False, False),
    ('/branding/revisions/../revisions/1.css', False, False),
    ('/branding/logos/1.css', False, False),
    ('/admin/branding/preview/1.css', False, False),
])
def test_branding_contract_with_positive_asset_evidence(
        browser: Browser, url: str, script: bool, allowed: bool) -> None:  # noqa: F811
    base = 'https://dishboard.example.invalid'
    styles = ['/static/tokens.css', '/static/vendor/tabler/tabler.min.css',
              '/static/admin-tabler.css', '/static/menu-images.css']
    scripts = ['/static/vendor/tabler/tabler.min.js', '/static/admin.js']
    (scripts if script else styles).append(url)
    html = ('<body class="dishboard-admin">'
            + ''.join(f'<link rel="stylesheet" href="{value}">' for value in styles)
            + ''.join(f'<script src="{value}"></script>' for value in scripts)
            + '<aside class="navbar-vertical"><nav aria-label="Backend"></nav></aside></body>')
    with browser.new_context(viewport={'width': 1440, 'height': 900}) as context:
        context.route('**/*', lambda route: route.abort())
        page = context.new_page()
        page.set_content(html)
        # Positive evidence cannot grant an unapproved URL or a CSS URL used as a script.
        statuses = {urljoin(base, value): True for value in styles + scripts}
        result = audit_tabler(page, base, statuses)
        assert result['local_assets_http_200'] is allowed
        assert result['local_styles_order'] and result['local_scripts_order']
