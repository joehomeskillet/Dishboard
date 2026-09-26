"""P5a: echte Listen mit Daten, gemessene Textrollen und Screenshots."""
from __future__ import annotations

import json
from datetime import UTC, datetime, timedelta

from flask import render_template_string
from playwright.sync_api import sync_playwright

from cafeteria.api_keys import create_api_key
from cafeteria.public.routes import bp as public_bp
from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_ui_route_inventory import _prepare_inventory_entities


# Selektoren benennen vorhandene Inhalte; kein DOM-Umbau im Messtest.
PAGES = (
    ('Wochen', '/admin/cafeteria/wochen', 'tbody tr', 'td:first-child strong', '.text-secondary', 'td:nth-child(2)'),
    ('Bausteine', '/admin/cafeteria/komponenten', '.component-row', 'th[scope=row]', '.text-secondary', 'td.category'),
    ('Gerichtvorlagen', '/admin/gerichtvorlagen', 'tbody tr', 'td:first-child a', '.text-secondary', 'td:nth-child(2)'),
    ('Rezepte', '/admin/rezepte', '.recipe-list-row', 'h2', '.text-secondary', None),
    ('Kochbücher', '/admin/kochbuecher', '.admin-list-row', '.admin-list-name strong', '.admin-list-subtitle', '.admin-list-meta'),
    ('Zutaten', '/admin/grundlagen', '.admin-list-row', '.admin-list-name strong', '.admin-list-subtitle', None),
    ('Einkaufslisten', '/admin/einkaufslisten', '.admin-list-row', '.admin-list-name strong', '.admin-list-subtitle', None),
    ('Bestellung', '/admin/bestellung', '#lieferanten .admin-list-row', '.admin-list-name strong', '.admin-list-subtitle', None),
    ('Benutzer', '/admin/benutzer', '[data-account-row] .admin-list-row', '.admin-list-primary', '.admin-list-secondary', '.admin-list-meta .small'),
    # P4: Scopes sind Label-Chips, Kanal und Ablaufdatum Sekundärtext;
    # die sichtbare Schlüsselzeile hat keine reine Meta-Textrolle.
    ('API-Schlüssel', '/admin/api', 'tbody tr', 'td:first-child strong', '.text-secondary', None),
    ('Druckvorlagen', '/admin/vorlagen', '[data-current-template]', 'h3', '.print-tpl-meta', None),
    ('Kalkulation', '/admin/kalkulation', '.cost-lines tbody tr', 'td:first-child', None, 'td:nth-child(2)'),
)

MEASURE = """(el) => {
    const s = getComputedStyle(el);
    return Object.fromEntries(['fontSize', 'fontWeight', 'color', 'fontStyle'].map(k => [k, s[k]]));
}"""

TOKEN_METRICS = """el => {
    const s = getComputedStyle(el);
    const rootSize = parseFloat(getComputedStyle(document.documentElement).fontSize);
    return Object.fromEntries(['primary', 'secondary', 'meta'].map(role => {
        const size = s.getPropertyValue(`--app-list-${role}-size`).trim();
        return [role, {fontSize: `${parseFloat(size) * (size.endsWith('rem') ? rootSize : 1)}px`,
                       fontWeight: s.getPropertyValue(`--app-list-${role}-weight`).trim()}];
    }));
}"""


def _contract_page():
    return render_template_string("""{% extends 'admin/base_tabler.html' %}
    {% from 'admin/_macros.html' import list_row, label, empty_value %}
    {% block content %}
    {% set primary %}<a href="#">Name <em>Zusatz</em></a>{% endset %}
    {% set secondary %}<strong><a href="#">Sekundär</a></strong>{% endset %}
    {% set meta %}<em>Metadaten</em>{% endset %}
    {{ list_row(primary=primary, secondary=secondary, meta=meta, status=label('Aktiv', 'active')) }}
    <table class="admin-table admin-table--stack"><tbody><tr>
      <th scope="row"><em>Name</em> <div class="text-secondary"><strong>Sekundär</strong></div></th>
      <td><em>Metadaten</em></td><td>{{ label('Aktiv', 'active') }}</td>
      <td>{{ empty_value() }}</td>
      <td><span class="admin-list-primary">Expliziter Name</span></td>
    </tr></tbody></table>
    {% endblock %}""")


def test_list_typography_across_modules(admin_app, admin_engine, live_server, tmp_path):  # noqa: F811
    admin_app.register_blueprint(public_bp)
    admin_app.add_url_rule('/_test/list-typography', view_func=_contract_page)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    entities = _prepare_inventory_entities(admin_app, admin_engine, actor)
    create_api_key(admin_engine, actor_id=actor, label='Typografieprüfung',
                   scopes=('preview.read',), channels=('cafeteria',),
                   expires_at=datetime.now(UTC) + timedelta(days=10))
    revision = entities['endpoint_paths']['admin.recipe_revision'].rsplit('/', 1)[-1]
    cookie = client.get_cookie('session')
    measurements = []
    failures = []
    values_by_role = {'Primär': set(), 'Sekundär': set(), 'Meta': set()}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for width in (1440, 390):
                with browser.new_context(base_url=live_server, viewport={'width': width, 'height': 900}) as context:
                    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                    page = context.new_page()
                    for name, path, row_selector, primary, secondary, meta in PAGES:
                        response = page.goto(path, wait_until='networkidle')
                        assert response.status == 200, (path, response.status)
                        if name == 'Kalkulation':
                            page.locator('#revision_public_id').fill(revision)
                            page.locator('#as_of').fill('2026-09-25')
                            page.locator('button[form="cost-preview"]').click()
                            page.wait_for_load_state('networkidle')
                        row = page.locator(row_selector).first
                        assert row.count() == 1, f'{name}: Datenzeile fehlt'
                        assert row.is_visible(), f'{name}: Datenzeile nicht sichtbar'
                        tokens = page.locator('body').evaluate(TOKEN_METRICS)
                        assert tokens == {
                            'primary': {'fontSize': '14px', 'fontWeight': '600'},
                            'secondary': {'fontSize': '13px', 'fontWeight': '400'},
                            'meta': {'fontSize': '14px', 'fontWeight': '400'},
                        }, f'{name}: Tokenvertrag weicht ab: {tokens}'
                        for role, selector in [('Primär', primary), ('Sekundär', secondary), ('Meta', meta)]:
                            if selector is None:
                                measurements.append(dict(page=name, width=width, role=role,
                                                         absent='Keine solche Textrolle in der Datenzeile'))
                                continue
                            element = row.locator(selector).first
                            assert element.count() == 1, f'{name}: {role} fehlt ({selector})'
                            actual = element.evaluate(MEASURE)
                            values_by_role[role].add(tuple(actual.values()))
                            expected = dict(fontSize='13px' if role == 'Sekundär' else '14px',
                                            fontWeight='600' if role == 'Primär' else '400',
                                            color=page.locator('body').evaluate("""(el, role) => {
                                                const s = getComputedStyle(el);
                                                const c = s.getPropertyValue(role === 'Sekundär' ? '--app-text-muted' : '--app-text');
                                                const canvas = document.createElement('canvas');
                                                const ctx = canvas.getContext('2d');
                                                ctx.fillStyle = c.trim(); ctx.fillRect(0, 0, 1, 1);
                                                const rgb = ctx.getImageData(0, 0, 1, 1).data;
                                                return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
                                            }""", role), fontStyle='normal')
                            measurements.append(dict(page=name, width=width, role=role,
                                                     actual=actual, expected=expected))
                            if actual != expected:
                                failures.append(f'{name} ({width}) | {role} | {actual} | {expected}')
                        page.screenshot(path=str(tmp_path / f'{name}-{width}.png'), full_page=True)
                    page.goto('/_test/list-typography', wait_until='networkidle')
                    for selector, size, weight in [
                        ('.admin-list-primary a', '14px', '600'),
                        ('.admin-list-primary em', '14px', '600'),
                        ('.admin-list-secondary a', '13px', '400'),
                        ('.admin-list-meta em', '14px', '400'),
                        ('th .text-secondary strong', '13px', '400'),
                        ('th > em', '14px', '600'),
                        ('td .admin-list-primary', '14px', '600'),
                        ('td em', '14px', '400'),
                    ]:
                        style = page.locator(selector).evaluate(MEASURE)
                        assert (style['fontSize'], style['fontWeight'], style['fontStyle']) == (
                            size, weight, 'normal'), (selector, style)
                    labels = page.locator('.admin-label').evaluate_all(
                        "els => els.map(el => {const s = getComputedStyle(el); return [s.fontSize, s.fontWeight, s.color]})")
                    assert len(labels) == 2 and labels[0] == labels[1], labels
        finally:
            browser.close()
            (tmp_path / 'list-typography.json').write_text(
                json.dumps(measurements, ensure_ascii=False, indent=2), encoding='utf-8')
            print(f'P5A_MESSMATRIX={tmp_path / "list-typography.json"}')
    assert not failures, 'Seite | Rolle | Ist | Soll\n' + '\n'.join(failures)
    assert all(len(values) == 1 for values in values_by_role.values()), values_by_role
