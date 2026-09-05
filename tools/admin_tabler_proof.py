"""Read-only checks for the migrated admin shell; no application mutations."""
from urllib.parse import urljoin, urlsplit

from playwright.sync_api import Page, expect


def audit_tabler(page: Page, base: str, asset_status: dict[str, bool]) -> dict[str, bool]:
    result = {'tabler_shell': page.locator('body.dishboard-admin').count() == 1}
    if not result['tabler_shell']:
        return result
    styles = page.locator('link[rel="stylesheet"][href]').evaluate_all(
        'nodes => nodes.map(node => node.getAttribute("href"))')
    scripts = page.locator('script[src]').evaluate_all(
        'nodes => nodes.map(node => node.getAttribute("src"))')
    result['local_styles_order'] = styles[:4] == [
        '/static/tokens.css', '/static/vendor/tabler/tabler.min.css',
        '/static/admin-tabler.css', '/static/menu-images.css',
    ]
    result['local_scripts_order'] = scripts[:2] == [
        '/static/vendor/tabler/tabler.min.js', '/static/admin.js',
    ]
    paths = [urlsplit(urljoin(base, value)).path for value in styles + scripts]
    result['no_legacy_app_css'] = '/static/app.css' not in paths
    result['one_tabler_no_extra_bootstrap'] = (
        scripts.count('/static/vendor/tabler/tabler.min.js') == 1
        and styles.count('/static/vendor/tabler/tabler.min.css') == 1
        and len(scripts) == len(set(scripts))
        and not any('bootstrap' in path.lower() for path in paths)
    )
    origin = urlsplit(base)
    local = True
    for value in styles + scripts:
        url = urljoin(base, value)
        parsed = urlsplit(url)
        if ((parsed.scheme, parsed.netloc) != (origin.scheme, origin.netloc)
                or not parsed.path.startswith('/static/') or parsed.fragment):
            local = False
            continue
        if url not in asset_status:
            response = page.request.get(url, max_redirects=0)
            asset_status[url] = response.status == 200
        local = local and asset_status[url]
    result['local_assets_http_200'] = local
    sidebar = page.locator('aside.navbar-vertical')
    nav = page.locator('nav[aria-label="Backend"]')
    toggle = page.get_by_role('button', name='Menü', exact=True)
    result['one_sidebar'] = sidebar.count() == 1 and nav.count() == 1
    width = page.evaluate('innerWidth')
    if width < 1200:
        result['nav_initially_collapsed'] = toggle.is_visible() and not nav.is_visible()
        result['nav_aria_controls'] = toggle.get_attribute('aria-controls') == 'sidebar-menu'
        box = toggle.bounding_box()
        result['nav_touch_48px'] = box is not None and box['width'] >= 48 and box['height'] >= 48
        toggle.focus()
        toggle.press('Enter')
        expect(toggle).to_have_attribute('aria-expanded', 'true')
        expect(nav).to_be_visible()
        result['nav_keyboard_expands'] = all(link.is_visible() for link in nav.locator('a').all())
        toggle.press('Enter')
        expect(toggle).to_have_attribute('aria-expanded', 'false')
        expect(nav).not_to_be_visible()
        result['nav_keyboard_collapses'] = True
        toggle.blur()
    else:
        result['nav_fixed_desktop'] = sidebar.evaluate("el => getComputedStyle(el).position === 'fixed'")
        result['nav_visible_desktop'] = nav.is_visible() and not toggle.is_visible()
    return result
