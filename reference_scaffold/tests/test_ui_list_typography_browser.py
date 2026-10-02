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
from test_ui_list_family_browser import _measure
from test_ui_route_inventory import _prepare_inventory_entities


# Selektoren benennen vorhandene Inhalte; kein DOM-Umbau im Messtest.
PAGES = (
    # Locator-Nachzug Wochen: td:first-child strong → td:first-child .admin-list-primary;
    # .text-secondary → .admin-list-secondary. Grund: Zeitraum und KW-Zusatz tragen die Rollen.
    ('Wochen', '/admin/cafeteria/wochen', 'tbody tr', 'td:first-child .admin-list-primary', '.admin-list-secondary', 'td:nth-child(2)'),
    ('Wochen Patienten', '/admin/patienten/wochen', 'tbody tr', '.admin-list-primary', '.admin-list-secondary', 'td:nth-child(2)'),
    ('Bausteine', '/admin/cafeteria/komponenten', '.component-row', 'span.admin-list-primary', '.admin-list-secondary', '.admin-list-meta'),
    ('Bausteine Patienten', '/admin/patienten/komponenten', '.component-row', 'span.admin-list-primary', '.admin-list-secondary', '.admin-list-meta'),
    ('Menüs Cafeteria', '/admin/cafeteria/menues', '.dishboard-menu-table tbody tr', '.admin-list-primary', '.admin-list-secondary', 'td:nth-child(2)'),
    ('Menüs Patienten', '/admin/patienten/menues', '.dishboard-menu-table tbody tr', '.admin-list-primary', '.admin-list-secondary', 'td:nth-child(2)'),
    # Aktive Vorlage mit Rezept: keine Warn-/Sekundärzeile; die Abwesenheit wird unten geprüft.
    ('Gerichtvorlagen', '/admin/gerichtvorlagen', 'tbody tr', 'td:first-child a', None, 'td:nth-child(2)'),
    # Locator-Nachzug Rezepte: Kartenliste → Tabelle. Name trägt admin-list-primary,
    # Ausbeute admin-list-meta. Entwurf steht nicht mehr als Sekundärzeile in jeder Zeile.
    ('Rezepte', '/admin/rezepte', 'table.recipe-list tbody tr', '.admin-list-primary', None, 'td.admin-list-meta'),
    ('Kochbücher', '/admin/kochbuecher', 'section.cookbook-list tbody tr', '.admin-list-name strong', '.admin-list-subtitle', '.admin-list-meta'),
    ('Zutaten', '/admin/grundlagen', '.admin-list-row', '.admin-list-name strong', '.admin-list-subtitle', None),
    ('Einheiten', '/admin/grundlagen?kind=units', '.admin-list-row', '.admin-list-primary', None, None),
    ('Kennzeichnungen', '/admin/grundlagen?kind=tags', '.admin-list-row', '.admin-list-primary', None, None),
    ('Lagerorte', '/admin/grundlagen?kind=storage_locations', '.admin-list-row', '.admin-list-primary', None, None),
    ('Lager', '/admin/lager', '.lager-table tbody tr', '.admin-list-primary', '.admin-list-secondary', 'td:nth-child(3)'),
    ('Rezeptimporte', '/admin/rezepte/import', '.admin-table tbody tr', '.admin-list-primary', None, None),
    ('Einkaufslisten', '/admin/einkaufslisten', '.admin-list-row', '.admin-list-name strong', '.admin-list-subtitle', None),
    ('Bestellung', '/admin/bestellung', '#lieferanten .admin-list-row', '.admin-list-name strong', '.admin-list-subtitle', None),
    ('Benutzer', '/admin/benutzer', '[data-account-row] .admin-list-row', '.admin-list-primary', '.admin-list-secondary', '.admin-list-meta'),
    # P4: Scopes sind Label-Chips, Kanal und Ablaufdatum Sekundärtext;
    # die sichtbare Schlüsselzeile hat keine reine Meta-Textrolle.
    # UI-DELTA: Der Name hat eine eigene Primärrolle neben den statischen Details.
    ('API-Schlüssel', '/admin/api', 'tbody tr', 'td[data-label="Bezeichnung"] > span.admin-list-primary', '.admin-list-secondary', None),
    ('Druckvorlagen', '/admin/vorlagen', '[data-current-template]', 'h3', '.print-tpl-meta', None),
    ('Kalkulation', '/admin/kalkulation', '.cost-lines tbody tr', 'td:first-child', None, 'td:nth-child(2)'),
    ('Kalender', '/admin/kuechenkalender?year=2026&month=9',
     '.kitchen-cal-grid:visible .kitchen-cal-day:has(.admin-list-meta), .kitchen-cal-list:visible .kitchen-cal-list-day:has(.admin-list-meta)',
     '.admin-list-primary', '.admin-list-secondary', '.admin-list-meta'),
)

MEASURE = """(el) => {
    const s = getComputedStyle(el);
    return Object.fromEntries(['fontSize', 'fontWeight', 'color', 'fontStyle', 'fontFamily'].map(k => [k, s[k]]));
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
    </tr><tr><td>Zweiter Eintrag</td><td>Metadaten</td></tr></tbody></table>
    {% endblock %}""")


def test_list_typography_across_modules(admin_app, admin_engine, live_server, tmp_path):  # noqa: F811
    admin_app.register_blueprint(public_bp)
    admin_app.add_url_rule('/_test/list-typography', view_func=_contract_page)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    entities = _prepare_inventory_entities(admin_app, admin_engine, actor)
    pages = PAGES + (('Importstapel', entities['endpoint_paths']['admin.recipe_import_detail'],
                      '.admin-table tbody tr', '.admin-list-primary', None, None),)
    create_api_key(admin_engine, actor_id=actor, label='Typografieprüfung',
                   scopes=('preview.read',), channels=('cafeteria',),
                   expires_at=datetime.now(UTC) + timedelta(days=10))
    revision = entities['endpoint_paths']['admin.recipe_revision'].rsplit('/', 1)[-1]
    cookie = client.get_cookie('session')
    measurements = []
    failures = []
    values_by_role = {'Primär': set(), 'Sekundär': set(), 'Meta': set()}
    headers = set()
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for width in (1440, 390):
                with browser.new_context(base_url=live_server, viewport={'width': width, 'height': 900}) as context:
                    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                    page = context.new_page()
                    for name, path, row_selector, primary, secondary, meta in pages:
                        response = page.goto(path, wait_until='networkidle')
                        assert response.status == 200, (path, response.status)
                        if name == 'Kalkulation':
                            page.locator('#revision_public_id').fill(revision)
                            page.locator('#as_of').fill('2026-09-25')
                            page.locator('button[form="cost-preview"]').click()
                            page.wait_for_load_state('networkidle')
                        measurements.append(dict(page=name, width=width, role='Listenstruktur', actual=_measure(page)))
                        row = page.locator(row_selector).first
                        assert row.count() == 1, f'{name}: Datenzeile fehlt'
                        assert row.is_visible(), f'{name}: Datenzeile nicht sichtbar'
                        divider = row.evaluate("el => getComputedStyle(el).borderBottomWidth")
                        # A last row may meet the shell edge without a second border.
                        if row.evaluate("el => el.nextElementSibling?.matches('tr, .admin-list-row, .print-tpl-row, .kitchen-cal-list-day')"):
                            assert divider == '1px', f'{name} ({width}): Zeilentrenner {divider}'
                        header = page.locator('.admin-table thead th:visible').first
                        # Mobile card layouts clip the table header for screen readers.
                        if header.count() and header.evaluate("el => getComputedStyle(el.closest('thead')).clipPath === 'none'"):
                            head = header.evaluate("""el => {
                                const s = getComputedStyle(el);
                                return {fontFamily: s.fontFamily, fontSize: s.fontSize,
                                        fontWeight: s.fontWeight, textTransform: s.textTransform,
                                        color: s.color, background: s.backgroundColor,
                                        height: Math.round(el.parentElement.getBoundingClientRect().height)};
                            }""")
                            headers.add(tuple(head.values()))
                            assert (head['fontSize'], head['fontWeight'], head['textTransform'], head['height']) == (
                                '12px', '500', 'uppercase', 33), (name, width, head)
                            measurements.append(dict(page=name, width=width, role='Kopf', actual=head))
                        if name == 'Gerichtvorlagen':
                            assert row.locator('.admin-list-secondary').count() == 0, 'Aktive Rezeptvorlage hat keine Warnzeile'
                        tokens = page.locator('body').evaluate(TOKEN_METRICS)
                        assert tokens == {
                            'primary': {'fontSize': '14px', 'fontWeight': '600'},
                            'secondary': {'fontSize': '13px', 'fontWeight': '400'},
                            'meta': {'fontSize': '13px', 'fontWeight': '400'},
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
                            expected = dict(fontSize='14px' if role == 'Primär' else '13px',
                                            fontWeight='600' if role == 'Primär' else '400',
                                            color=page.locator('body').evaluate("""(el, role) => {
                                                const s = getComputedStyle(el);
                                                const c = s.getPropertyValue(role === 'Primär' ? '--app-text' : '--app-text-muted');
                                                const canvas = document.createElement('canvas');
                                                const ctx = canvas.getContext('2d');
                                                ctx.fillStyle = c.trim(); ctx.fillRect(0, 0, 1, 1);
                                                const rgb = ctx.getImageData(0, 0, 1, 1).data;
                                                return `rgb(${rgb[0]}, ${rgb[1]}, ${rgb[2]})`;
                                            }""", role), fontStyle='normal',
                                            fontFamily=page.locator('body').evaluate('el => getComputedStyle(el).fontFamily'))
                            measurements.append(dict(page=name, width=width, role=role,
                                                     actual=actual, expected=expected))
                            if actual != expected:
                                failures.append(f'{name} ({width}) | {role} | {actual} | {expected}')
                        page.screenshot(path=str(tmp_path / f'{name}-{width}.png'), full_page=True)
                    page.goto('/_test/list-typography', wait_until='networkidle')
                    assert page.locator('tbody tr').first.evaluate('el => getComputedStyle(el).borderBottomWidth') == '1px'
                    for selector, size, weight in [
                        ('.admin-list-primary a', '14px', '600'),
                        ('.admin-list-primary em', '14px', '600'),
                        ('.admin-list-secondary a', '13px', '400'),
                        ('.admin-list-meta em', '13px', '400'),
                        ('th .text-secondary strong', '13px', '400'),
                        ('th > em', '14px', '600'),
                        ('td .admin-list-primary', '14px', '600'),
                        ('td em', '13px', '400'),
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
    assert len(headers) == 1, headers
