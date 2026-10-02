"""P01–P10: Werkzeugseiten priorisieren Aufgabe, Wirkung und Prüfstatus."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

from cafeteria.api_keys import create_api_key, revoke_api_key

from test_admin_workflow_routes import WEEK, _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_korrektur_cookbooks_browser import _native_viewport_capture
from test_delta_renderer_browser import VISIBILITY
from test_ui_master_shell_browser import _cookie, _page, site as admin_site  # noqa: F401

site = admin_site


ROOT = Path(__file__).resolve().parents[2]
API_EVIDENCE = ROOT / '.claude/evidence/density-api-fix-0913'
VIEWPORTS = (
    ('desktop-1366', 1366, 768),
    ('desktop-1440', 1440, 900),
    ('desktop-1920', 1920, 1080),
    ('tablet', 768, 1024),
    ('mobile', 390, 844),
    ('zoom-200', 720, 450),
)


def _goto(page: Page, path: str) -> None:
    response = page.goto(path, wait_until='networkidle')
    assert response is not None and response.status == 200, (path, response)
    page.evaluate('document.fonts.ready')


def _assert_no_duplicate_primary_action(page: Page) -> None:
    assert page.locator('.admin-area-tabs').count() <= 1
    assert page.locator('main .btn-primary:visible').count() <= 1


def _assert_full_width(page: Page, width: int) -> None:
    metrics = page.evaluate(r'''() => {
      const container = document.querySelector('.page-body > .container-xl');
      const style = getComputedStyle(container);
      const padding = parseFloat(style.paddingLeft) + parseFloat(style.paddingRight);
      const inner = container.getBoundingClientRect().width - padding;
      const blocks = [...container.children].filter(node => node.getBoundingClientRect().height > 8);
      const primary = Math.max(...blocks.map(node => node.getBoundingClientRect().width));
      return {
        overflow: document.documentElement.scrollWidth > innerWidth + 1,
        documentWidth: document.documentElement.scrollWidth,
        viewportWidth: innerWidth,
        ratio: primary / inner,
        offenders: [...document.querySelectorAll('body *')]
          .map(node => {
            const rect = node.getBoundingClientRect();
            return {
              tag: node.tagName,
              id: node.id,
              className: String(node.className).slice(0, 120),
              text: String(node.textContent).trim().replace(/\s+/g, ' ').slice(0, 120),
              left: rect.left,
              right: rect.right,
              clientWidth: node.clientWidth,
              scrollWidth: node.scrollWidth,
            };
          })
          .filter(item => item.right > innerWidth + 1 || item.scrollWidth > item.clientWidth + 1)
          .sort((left, right) => right.right - left.right)
          .slice(0, 12),
      };
    }''')
    assert not metrics['overflow'], json.dumps({'width': width, **metrics}, indent=2)
    if width >= 1024:
        assert metrics['ratio'] >= 0.95, (width, metrics)


def _screenshot(page: Page, name: str, width: int, height: int, masks: list[object] | None = None) -> None:
    API_EVIDENCE.mkdir(parents=True, exist_ok=True)
    options = {'path': str(API_EVIDENCE / f'{name}-{width}x{height}.png'), 'full_page': True}
    if masks:
        options['mask'] = masks
    page.screenshot(**options)


def _api_prefix_mask_locators(page: Page):
    return page.locator('[data-api-key-prefix]')


def test_tool_pages_put_primary_content_before_administration(site) -> None:  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 1366, 'height': 768})
    try:
        _goto(page, '/admin/api')
        expect(page.get_by_role('heading', name='Schnittstellen', exact=True)).to_be_visible()
        assert page.evaluate('''() => Boolean(
          document.querySelector('[data-api-keys]').closest('section')
            .compareDocumentPosition(document.querySelector('[data-api-status]'))
            & Node.DOCUMENT_POSITION_FOLLOWING
        )''')
        create = page.locator('#api-create')
        expect(create.locator('summary')).to_have_count(0)
        expect(page.locator('#api-key-create')).to_be_visible()
        _assert_no_duplicate_primary_action(page)
        page.locator('#api-key-create').evaluate('form => { form.noValidate = true; }')
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            page.locator('#api-key-create button[type="submit"]').click()
        assert rejected.value.status == 400
        expect(page.locator('#api-key-create')).to_be_visible()
        expect(create.get_by_role('alert')).to_be_visible()
        _assert_no_duplicate_primary_action(page)
        _screenshot(page, 'schnittstellen-fehler', 1366, 768)

        _goto(page, '/admin/import-preview')
        expect(page.get_by_role('heading', name='Daten importieren', exact=True)).to_be_visible()
        expect(page.get_by_role('heading', name='CSV-Datei auswählen', exact=True)).to_be_visible()
        _assert_no_duplicate_primary_action(page)
        page.locator('input[type="file"]').set_input_files(ROOT / 'csv/menu_cafeteria_example.csv')
        page.get_by_role('button', name='Vorschau prüfen', exact=True).click()
        page.wait_for_load_state('networkidle')
        expect(page.get_by_role('heading', name='Bereit zum Import', exact=True)).to_be_visible()
        assert page.evaluate('''() => Boolean(
          document.querySelector('.csv-preview-result')
            .compareDocumentPosition(document.querySelector('#csv-upload'))
            & Node.DOCUMENT_POSITION_FOLLOWING
        )''')
        _assert_no_duplicate_primary_action(page)
        _screenshot(page, 'import-bereit', 1366, 768)

        target = (WEEK + dt.timedelta(days=7)).isoformat()
        _goto(page, f'/admin/cafeteria/copy?week={target}')
        for label, date in (('Quellwoche', WEEK), ('Zielwoche', dt.date.fromisoformat(target))):
            status = page.locator('.admin-statusbar-item').filter(
                has=page.get_by_text(label, exact=True)
            )
            expect(status).to_be_visible()
            expect(status.locator('dd')).to_contain_text(date.strftime('%d.%m.%Y'))
        expect(page.locator('#copy-effects')).to_contain_text(
            'Wochenkopf, Ausgabeangaben und Menüs werden aus der Quellwoche übernommen.'
        )
        expect(page.locator('#copy-effects')).to_contain_text(
            'Prüfbestätigungen werden nicht übernommen; die Zielwoche bleibt ein Entwurf.'
        )
        _assert_no_duplicate_primary_action(page)

        _goto(page, f'/admin/cafeteria/wochen/pruefung?week={WEEK.isoformat()}')
        expect(page.get_by_role('heading', name='Wochenangaben prüfen', exact=True)).to_be_visible()
        status_box = page.locator('main .alert').first
        assert page.evaluate('''() => Boolean(
          document.querySelector('main .alert')
            .compareDocumentPosition(document.querySelector('[data-week-review-intro]'))
            & Node.DOCUMENT_POSITION_FOLLOWING
        )''')
        expect(status_box).to_contain_text('gespeicherten Wochenkopf und seine Ausgabeangaben')
        _assert_no_duplicate_primary_action(page)
    finally:
        page.context.close()


def _api_density_client(site, monkeypatch):
    from cafeteria.public import routes as public_routes
    app, _, engine, _ = site
    client, actor = _login(app, engine, ['Cafeteria.Admin'])
    for state, channels in (('active', ['cafeteria', 'patienten']),
                            ('expired', ['patienten']), ('revoked', ['cafeteria'])):
        key, _ = create_api_key(engine, actor_id=actor, label=f'Synthetischer {state} Testzugang',
                               scopes=['preview.read'], channels=channels,
                               expires_at=dt.datetime.now(dt.UTC) + dt.timedelta(days=30))
        if state == 'revoked':
            revoke_api_key(engine, actor_id=actor, public_id=key.public_id)
        if state == 'expired':
            with engine.begin() as connection:
                connection.execute(text('''UPDATE cafeteria.api_keys
                    SET created_at=now()-interval '2 days', expires_at=now()-interval '1 day'
                    WHERE public_id=CAST(:id AS uuid)'''), {'id': key.public_id})
    monkeypatch.setattr(public_routes, 'published_snapshot', lambda profile: {
        'revision_id': 'SYNTHETISCH-CAF-R7', 'week_start': '2026-08-31',
        'week_end': '2026-09-04', 'days': [],
    } if profile == 'staff_guest' else None)
    return client


def test_api_density_viewports_and_publication_truth(site, monkeypatch) -> None:
    client = _api_density_client(site, monkeypatch)
    measurements = []
    for javascript in (True, False):
        for width, height in ((1440, 900), (390, 844), (320, 844), (2560, 1440),
                              (1024, 768), (768, 1024), (1920, 1080)):
            page = _page(site, client, viewport={'width': width, 'height': height},
                         java_script_enabled=javascript)
            try:
                _goto(page, '/admin/api')
                _assert_full_width(page, width)
                _assert_rendered_icons(page)
                expect(page.locator('[data-api-status]')).to_contain_text('SYNTHETISCH-CAF-R7')
                expect(page.locator('.admin-statusbar')).to_contain_text('Nicht veröffentlicht')
                for state in ('active', 'expired', 'revoked'):
                    expect(page.locator(f'[data-key-state="{state}"]')).to_be_visible()
                assert page.locator('[data-key-state="active"] button').count() == 1
                assert page.locator('[data-key-state="expired"] button, [data-key-state="revoked"] button').count() == 0
                expect(page.locator('[data-api-help], [data-api-versions]')).to_have_count(2)
                technical = page.locator('#api-technical')
                expect(technical.locator('summary')).to_have_count(0)
                docs = technical.locator('a[href="/api/v1/docs"]')
                docs.focus()
                expect(docs).to_be_focused()
                for selector in ('[data-api-help]', '[data-api-versions]'):
                    expect(page.locator(f'section{selector}')).to_be_visible()
                expect(page.locator('[data-api-status]')).to_be_visible()
                _assert_full_width(page, width)
                _assert_rendered_icons(page)
                minimum = page.evaluate(
                    "matchMedia('(pointer: coarse), (any-pointer: coarse)').matches ? 44 : 36"
                )
                box = docs.bounding_box()
                assert box and box['height'] >= minimum and box['width'] >= minimum
                for state in ('active', 'expired', 'revoked'):
                    expect(page.locator(f'[data-key-state="{state}"] [data-semantic="actions.more"]')).to_have_count(0)
                    menu = page.locator(f'[data-key-state="{state}"] .admin-api-key-details')
                    expect(menu.locator('summary')).to_have_count(0)
                    expect(menu.locator('dl')).to_be_visible()
                    _assert_rendered_icons(page)
                assert 'dbk_' not in ' '.join(page.locator('main summary').all_text_contents())
                key_details = page.locator('[data-key-state="active"] .admin-api-key-details')
                expect(key_details.locator('dl')).to_be_visible()
                _assert_rendered_icons(page)
                prefix_mask = _api_prefix_mask_locators(page)
                expect(prefix_mask).to_have_count(3)
                page.evaluate('if (document.activeElement && document.activeElement.blur) { document.activeElement.blur(); }')
                page.evaluate('window.scrollTo(0, 0)')
                geometry = page.evaluate('''() => ({
                    height: document.documentElement.scrollHeight,
                    firstContentY: document.querySelector('[data-api-keys]').getBoundingClientRect().y,
                    publicationY: document.querySelector('[data-api-status]').getBoundingClientRect().y,
                    documentOverflow: document.documentElement.scrollWidth - innerWidth,
                    overflowNodes: [...document.querySelectorAll('body *')]
                        .filter(node => node.checkVisibility())
                        .map(node => ({tag: node.tagName, className: String(node.className),
                            right: node.getBoundingClientRect().right}))
                        .filter(node => node.right > innerWidth + 1).slice(0, 12)
                })''')
                measurements.append({'width': width, 'javascript': javascript, **geometry})
                (API_EVIDENCE / 'geometry.json').write_text(json.dumps(measurements, indent=2))
                page.screenshot(path=str(API_EVIDENCE / f'keys-{width}-js-{javascript}.png'),
                                full_page=True, mask=[prefix_mask])
                assert geometry['documentOverflow'] <= 1, (width, javascript, geometry)
            finally:
                page.context.close()
    (API_EVIDENCE / 'geometry.json').write_text(json.dumps(measurements, indent=2))


@pytest.mark.parametrize('javascript,width', ((True, 1440), (False, 1440), (True, 390), (False, 390)))
def test_api_density_native_lifecycle_and_error_retention(site, javascript, width) -> None:
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': width, 'height': 900}, java_script_enabled=javascript)
    try:
        _goto(page, '/admin/api')
        expect(page.get_by_text('Noch keine API-Schlüssel vorhanden.', exact=True)).to_be_visible()
        expect(page.locator('table[data-api-keys]')).to_have_count(0)
        _screenshot(page, f'empty-api-js-{javascript}', width, 900)
        expect(page.locator('#api-create > summary')).to_have_count(0)
        form = page.locator('#api-key-create')
        expect(form).to_be_visible()
        form.get_by_role('button', name='Anlegen', exact=True).click()
        expect(page.locator('#api-key-label')).to_be_focused()
        page.get_by_label('Bezeichnung', exact=True).fill('Synthetischer Browserzugang')
        page.locator('#api-key-channel-cafeteria').check()
        page.locator('#api-key-channel-patienten').check()
        expiry = page.locator('#api-key-expires').input_value()
        original = form.evaluate('form => [...new FormData(form)]')
        page.locator('#api-key-expires').focus()
        expect(page.locator('#api-key-expires')).to_be_focused()
        assert bool(original == form.evaluate('form => [...new FormData(form)]'))
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            form.get_by_role('button', name='Anlegen', exact=True).click()
        assert rejected.value.status == 400  # No scope selected: existing server validation.
        expect(form.get_by_role('alert')).to_be_visible()
        if javascript:
            expect(form.get_by_role('alert')).to_be_focused()
        expect(page.locator('#api-key-label')).to_have_value('Synthetischer Browserzugang')
        expect(page.locator('#api-key-expires')).to_have_value(expiry)
        for channel in ('cafeteria', 'patienten'):
            expect(page.locator(f'#api-key-channel-{channel}')).to_be_checked()
        expect(page.locator('#api-key-create-title')).to_contain_text('Fehler')
        expect(page.locator('#api-create > summary')).to_have_count(0)
        page.locator('#api-key-scope-preview').check()
        form.get_by_role('button', name='Anlegen', exact=True).click()
        expect(page.locator('[data-new-key]')).to_be_visible()
        assert 'dbk_' not in ' '.join(page.locator('main summary').all_text_contents())
        if width == 390:
            alert_geometry = page.locator('[data-new-key]').evaluate('''alert => {
              const key = alert.querySelector('[data-new-key-value]').getBoundingClientRect();
              const hint = alert.querySelector('[data-new-key-hint]').getBoundingClientRect();
              return {
                documentOverflow: document.documentElement.scrollWidth - innerWidth,
                keyBottom: key.bottom,
                hintTop: hint.top,
              };
            }''')
            assert alert_geometry['documentOverflow'] <= 1, alert_geometry
            assert alert_geometry['hintTop'] >= alert_geometry['keyBottom'], alert_geometry
        page.screenshot(path=str(API_EVIDENCE / f'created-{width}-js-{javascript}.png'), full_page=True,
                        mask=[page.locator('[data-new-key] code'), _api_prefix_mask_locators(page)])
        _goto(page, '/admin/api')
        expect(page.locator('[data-new-key]')).to_have_count(0)
        expect(page.locator('[data-api-keys] table')).to_have_count(1)
        row = page.locator('[data-key-state="active"]')
        expect(row.locator('[data-label="Scopes / Kanäle"]')).to_contain_text('preview.read')
        expect(row.locator('[data-label="Scopes / Kanäle"]')).to_contain_text('Cafeteria, Patienten')
        expect(row.locator('[data-semantic="actions.more"]')).to_have_count(0)
        details = row.locator('.admin-api-key-details')
        expect(details.locator('summary')).to_have_count(0)
        expect(details).to_contain_text('Zuletzt verwendet')
        expect(details.locator('dl')).to_be_visible()
        _assert_rendered_icons(page)
        _assert_full_width(page, width)
        revoke = row.locator('form[action$="/revoke"]')
        expect(revoke.locator('summary')).to_have_count(0)
        confirm = revoke.get_by_role(
            'button', name='Schlüssel Synthetischer Browserzugang widerrufen', exact=True
        )
        posts = []
        page.on('request', lambda request: posts.append(request.url) if request.method == 'POST' else None)
        expect(confirm).to_be_visible()
        expect(confirm).to_have_text('Widerrufen')
        expect(confirm.locator('svg')).to_have_count(0)
        confirm.focus()
        expect(confirm).to_be_focused()
        if javascript:
            confirm.press('Escape')
            expect(page.get_by_role('tooltip')).not_to_be_visible()
        expect(revoke.locator('.ui-sem-consequence')).to_have_text(
            'Schlüssel wirklich widerrufen? Anwendungen verlieren damit den Vorschauzugriff.'
        )
        expect(confirm).to_be_visible()
        expect(row).to_be_visible()
        assert posts == []
        confirm.scroll_into_view_if_needed()
        geometry = confirm.evaluate('''el => {
            const b = el.getBoundingClientRect();
            const hit = document.elementFromPoint(b.x + b.width / 2, b.y + b.height / 2);
            return {trigger: b.toJSON(), hit: {tag: hit?.tagName, className: hit?.className},
                tooltips: [...document.querySelectorAll('[role="tooltip"]')].map(tip => ({
                    box: tip.getBoundingClientRect().toJSON(), text: tip.textContent}))};
        }''')
        (API_EVIDENCE / f'revoke-reopen-{width}-js-{javascript}.json').write_text(json.dumps(geometry, indent=2))
        if javascript:
            page.once('dialog', lambda dialog: dialog.dismiss())
            confirm.click()
            expect(row).to_be_visible()
            assert posts == []
            page.once('dialog', lambda dialog: dialog.accept())
        with page.expect_response(lambda response: response.request.method == 'POST') as revoked:
            confirm.click()
        assert revoked.value.status == 303
        assert len(posts) == 1
        expect(page.locator('[data-key-state="revoked"]')).to_be_visible()
        expect(page.locator('[data-key-state="revoked"] button')).to_have_count(0)
    finally:
        page.context.close()


def test_tool_forms_keep_native_targets_and_payloads_without_javascript(site) -> None:  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    target = (WEEK + dt.timedelta(days=7)).isoformat()
    cases = (
        ('/admin/api', '#api-key-create', '/admin/api/keys',
         {'_csrf', 'label', 'expires_at', 'scopes', 'channels'}),
        ('/admin/import-preview', '#csv-upload', '/admin/import-preview', {'_csrf', 'file'}),
        (f'/admin/cafeteria/copy?week={target}', 'form.admin-copy-actions',
         '/admin/cafeteria/copy', {'_csrf', 'source_week', 'target_week', 'target_row_version'}),
        (f'/admin/cafeteria/wochen/pruefung?week={WEEK.isoformat()}',
         'form:has(input[name="context_version"])', '/admin/cafeteria/wochen/pruefung',
         {'_csrf', 'week', 'context_version'}),
    )
    observed = {}
    for java_script_enabled in (True, False):
        page = _page(
            site,
            client,
            viewport={'width': 390, 'height': 844},
            java_script_enabled=java_script_enabled,
        )
        try:
            contracts = []
            for path, selector, action, fields in cases:
                _goto(page, path)
                form = page.locator(selector)
                expect(form).to_have_attribute('method', 'post')
                expect(form).to_have_attribute('action', action)
                names = set(form.locator('[name]').evaluate_all('nodes => nodes.map(node => node.name)'))
                assert names == fields
                contracts.append((action, names))
                _assert_full_width(page, 390)
            observed[java_script_enabled] = contracts
        finally:
            page.context.close()
    assert observed[True] == observed[False]


def test_tool_pages_fit_required_viewports_and_capture_evidence(site) -> None:  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    target = (WEEK + dt.timedelta(days=7)).isoformat()
    routes = (
        ('schnittstellen', '/admin/api', '#api-keys-title'),
        ('import-leer', '/admin/import-preview', '#csv-upload button.btn-primary'),
        ('vorwoche-kopieren', f'/admin/cafeteria/copy?week={target}',
         'button.btn-primary[form="week-copy-form"]'),
        ('wochenpruefung-offen', f'/admin/cafeteria/wochen/pruefung?week={WEEK.isoformat()}',
         'main .alert'),
    )
    for _, width, height in VIEWPORTS:
        page = _page(site, client, viewport={'width': width, 'height': height})
        try:
            for name, path, primary in routes:
                _goto(page, path)
                _assert_full_width(page, width)
                expect(page.locator(primary).first).to_be_visible()
                if width in {1366, 1440, 1920}:
                    box = page.locator(primary).first.bounding_box()
                    assert box is not None and box['y'] + box['height'] <= height, (name, box)
                _screenshot(page, name, width, height)
        finally:
            page.context.close()

    for width, height in ((1366, 768), (390, 844)):
        page = _page(site, client, viewport={'width': width, 'height': height})
        try:
            _goto(page, '/admin/api')
            expect(page.locator('#api-create > summary')).to_have_count(0)
            expect(page.locator('#api-key-create')).to_be_visible()
            page.locator('#api-key-create').evaluate('form => { form.noValidate = true; }')
            page.locator('#api-key-create button[type="submit"]').click()
            page.wait_for_load_state('networkidle')
            expect(page.locator('#api-key-create').get_by_role('alert')).to_be_visible()
            _assert_full_width(page, width)
            _screenshot(page, 'schnittstellen-fehler', width, height)

            _goto(page, '/admin/import-preview')
            page.locator('input[type="file"]').set_input_files({
                'name': 'ungueltig.csv',
                'mimeType': 'text/csv',
                'buffer': b'wrong;header\ninvalid;row\n',
            })
            page.get_by_role('button', name='Vorschau prüfen', exact=True).click()
            page.wait_for_load_state('networkidle')
            expect(page.locator('.error-region')).to_be_visible()
            _assert_full_width(page, width)
            _screenshot(page, 'import-fehler', width, height)
        finally:
            page.context.close()


def _assert_rendered_icons(page: Page) -> None:
    # UI-DELTA B-02: copy confirmation uses two explicit text actions.
    if urlsplit(page.url).path in {'/admin/cafeteria/copy', '/admin/patienten/copy'}:
        controls = page.locator('main .ui-sem-control:visible')
        expect(controls).to_have_count(2)
        expect(controls).to_have_text(['Vorwoche kopieren', 'Zurück'])
        for control in controls.all():
            assert control.evaluate('el => el.classList.contains("ui-sem-control--text")')
            assert control.locator('svg, img').count() == 0
            assert control.inner_text().strip() in control.get_attribute('aria-label')
            rendered = control.evaluate(VISIBILITY)
            assert rendered['text'] and not rendered['icons'] and not rendered['pseudos'], rendered
        return
    icons = page.locator('main svg.icon:visible')
    assert icons.count() > 0
    missing = icons.evaluate_all('''icons => icons.flatMap(icon => {
      const box = icon.getBBox();
      const use = icon.querySelector('use');
      const href = use && use.getAttribute('href');
      if (href && href.includes('#tabler-') && box.width > 0 && box.height > 0) return [];
      return [{href, width: box.width, height: box.height}];
    })''')
    assert missing == []


def test_owned_import_copy_review_fit_density_viewports(site) -> None:  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    target = (WEEK + dt.timedelta(days=7)).isoformat()
    routes = (
        ('import-leer', '/admin/import-preview', '#csv-upload button.btn-primary'),
        ('vorwoche-kopieren', f'/admin/cafeteria/copy?week={target}',
         'button.btn-primary[form="week-copy-form"]'),
        ('wochenpruefung-offen', f'/admin/cafeteria/wochen/pruefung?week={WEEK.isoformat()}',
         'main .alert'),
    )
    for width, height in ((1440, 900), (1024, 768), (390, 844)):
        page = _page(site, client, viewport={'width': width, 'height': height})
        try:
            for name, path, primary in routes:
                _goto(page, path)
                _assert_full_width(page, width)
                expect(page.locator(primary).first).to_be_visible()
                _assert_rendered_icons(page)
                _screenshot(page, f'density-{name}', width, height)
        finally:
            page.context.close()


def test_import_checked_result_is_not_relabeled_after_new_selection(site) -> None:  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    page = _page(site, client, viewport={'width': 1440, 'height': 900})
    try:
        _goto(page, '/admin/import-preview')
        expect(page.locator('main')).to_have_attribute('data-state', 'empty')
        page.locator('input[type="file"]').set_input_files(ROOT / 'csv/menu_cafeteria_example.csv')
        page.get_by_role('button', name='Vorschau prüfen', exact=True).click()
        page.wait_for_load_state('networkidle')
        result = page.locator('.csv-preview-result')
        expect(result).to_be_visible()
        identity = page.locator('[data-checked-identity]').inner_text()
        week = result.get_attribute('data-checked-week')
        profile = result.get_attribute('data-checked-profile')
        assert week == '2026-08-31'
        assert profile == 'staff_guest'
        status = page.locator('.admin-statusbar')
        expect(status).to_contain_text('Cafeteria')
        expect(status).to_contain_text('KW 36')
        expect(status).to_contain_text('31.08.2026')
        expect(result).not_to_contain_text('andere-datei.csv')
        page.locator('#file').set_input_files({
            'name': 'andere-datei.csv',
            'mimeType': 'text/csv',
            'buffer': b'wrong;header\ninvalid;row\n',
        })
        assert page.locator('[data-checked-identity]').inner_text() == identity
        assert result.get_attribute('data-checked-week') == week
        assert result.get_attribute('data-checked-profile') == profile
        expect(status).to_contain_text('Cafeteria')
        expect(status).to_contain_text('KW 36')
        expect(status).to_contain_text('31.08.2026')
        assert 'andere-datei.csv' not in result.inner_text()
        expect(page.get_by_role('heading', name='Bereit zum Import', exact=True)).to_be_visible()
        assert page.locator('input[name="import_token"]').input_value()
        expect(page.get_by_role('heading', name='Andere Datei prüfen', exact=True)).to_be_visible()
        _assert_rendered_icons(page)
        _screenshot(page, 'import-stale-selection', 1440, 900)
    finally:
        page.context.close()


def test_import_copy_review_disclosures_keep_payloads_and_keyboard(site) -> None:  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    target = (WEEK + dt.timedelta(days=7)).isoformat()
    for javascript in (True, False):
        page = _page(
            site, client, viewport={'width': 390, 'height': 844},
            java_script_enabled=javascript,
        )
        try:
            _goto(page, '/admin/import-preview')
            upload = page.locator('#csv-upload')
            expect(upload.locator('details, summary')).to_have_count(0)
            names = set(upload.locator('[name]').evaluate_all('nodes => nodes.map(node => node.name)'))
            assert names == {'_csrf', 'file'}
            expect(upload.locator('#csv-more')).to_be_visible()
            expect(upload.locator('#csv-more')).to_contain_text('getrennte Formate')
            page.locator('#file').focus()
            expect(page.locator('#file')).to_be_focused()
            assert set(upload.locator('[name]').evaluate_all('nodes => nodes.map(node => node.name)')) == names

            _goto(page, f'/admin/cafeteria/copy?week={target}')
            form = page.locator('form.admin-copy-actions')
            fields = form.evaluate('form => Object.fromEntries(new FormData(form))')
            assert set(fields) == {'_csrf', 'source_week', 'target_week', 'target_row_version'}
            assert fields['source_week'] == WEEK.isoformat()
            assert fields['target_week'] == target
            _assert_rendered_icons(page)

            _goto(page, f'/admin/cafeteria/wochen/pruefung?week={WEEK.isoformat()}')
            review = page.locator('form:has(input[name="context_version"])')
            review_fields = review.evaluate('form => Object.fromEntries(new FormData(form))')
            assert set(review_fields) == {'_csrf', 'week', 'context_version'}
            assert review_fields['week'] == WEEK.isoformat()
            expect(page.locator('.admin-list-row h3').first).to_be_visible()  # shared list row (P4)
            _assert_full_width(page, 390)
            _screenshot(page, f'disclosure-nojs-{javascript}', 390, 844)
        finally:
            page.context.close()


def test_import_copy_review_native_cdp_zoom_is_not_css_zoom(site) -> None:  # noqa: F811
    app, origin, engine, playwright_browser = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    target = (WEEK + dt.timedelta(days=7)).isoformat()
    API_EVIDENCE.mkdir(parents=True, exist_ok=True)
    with TemporaryDirectory(prefix='density-imports-zoom-') as profile:
        with playwright_browser.browser_type.launch_persistent_context(
            profile, channel='chromium', headless=True, no_viewport=True,
            locale='de-CH', timezone_id='Europe/Zurich', reduced_motion='reduce',
            args=['--no-sandbox', '--disable-dev-shm-usage', '--window-size=1440,900'],
        ) as context:
            context.add_cookies([_cookie(app, client, origin)])
            page = context.pages[0]
            page.goto('chrome://settings/appearance')
            page.evaluate('new Promise(resolve => chrome.settingsPrivate.setDefaultZoom(2, resolve))')
            assert page.evaluate('new Promise(resolve => chrome.settingsPrivate.getDefaultZoom(resolve))') == 2
            proof = {}
            for name, path in (
                ('api', '/admin/api'),
                ('import-leer', '/admin/import-preview'),
                ('vorwoche-kopieren', f'/admin/cafeteria/copy?week={target}'),
                ('wochenpruefung', f'/admin/cafeteria/wochen/pruefung?week={WEEK.isoformat()}'),
            ):
                response = page.goto(origin + path, wait_until='networkidle')
                assert response is not None and response.status == 200
                page.evaluate('document.fonts.ready')
                assert page.evaluate('[innerWidth, outerWidth, devicePixelRatio]') == [720, 1440, 2]
                assert page.evaluate('getComputedStyle(document.documentElement).zoom') == '1'
                capture = _native_viewport_capture(page, API_EVIDENCE / f'native-200-{name}.png')
                zoom = capture['layout']['cssVisualViewport']['zoom']
                assert zoom == 2, capture['layout']
                _assert_rendered_icons(page)
                assert not page.evaluate('document.documentElement.scrollWidth > innerWidth + 1')
                proof[name] = {'zoom': zoom, 'png': capture['png']}
            (API_EVIDENCE / 'native-200.cdp.json').write_text(json.dumps(proof, indent=2))


@pytest.mark.parametrize('width,height', ((320, 844), (2560, 1440)))
@pytest.mark.parametrize('javascript', (False, True))
def test_import_density_missing_viewports(site, width, height, javascript) -> None:  # noqa: F811
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    target = (WEEK + dt.timedelta(days=7)).isoformat()
    API_EVIDENCE.mkdir(parents=True, exist_ok=True)
    page = _page(site, client, viewport={'width': width, 'height': height},
                 java_script_enabled=javascript)
    try:
        for name, path, action in (
            ('copy', f'/admin/cafeteria/copy?week={target}', 'Vorwoche kopieren'),
            ('review', f'/admin/cafeteria/wochen/pruefung?week={WEEK.isoformat()}',
             'Wochenkopf und alle Ausgabehinweise als geprüft bestätigen'),
            ('csv-empty', '/admin/import-preview', 'Vorschau prüfen'),
        ):
            _goto(page, path)
            page.screenshot(path=str(API_EVIDENCE / f'{name}-{width}-js-{javascript}.png'), full_page=True)
            _assert_full_width(page, width)
            _assert_rendered_icons(page)
            button = page.get_by_role('button', name=action, exact=True)
            expect(button).to_be_visible()
            button.focus()
            expect(button).to_be_focused()
            if name == 'review':
                expect(page.get_by_role('list', name='Ausgabeangaben').get_by_role('listitem')).to_have_count(5)
                expect(page.locator('#week-service-normal')).to_contain_text(
                    'Normalzustand: geöffnet, kein Ausgabehinweis.'
                )
                expect(page.locator('#week-service-normal')).to_contain_text(
                    'Alle gespeicherten Angaben entsprechen diesem Normalzustand.'
                )
            if name == 'copy':
                for label, date in (('Quellwoche', WEEK), ('Zielwoche', dt.date.fromisoformat(target))):
                    status = page.locator('.admin-statusbar-item').filter(
                        has=page.get_by_text(label, exact=True)
                    )
                    expect(status).to_be_visible()
                    expect(status.locator('dd')).to_contain_text(date.strftime('%d.%m.%Y'))
        page.locator('#file').set_input_files(ROOT / 'csv/menu_cafeteria_example.csv')
        page.get_by_role('button', name='Vorschau prüfen', exact=True).click()
        expect(page.get_by_role('heading', name='Bereit zum Import', exact=True)).to_be_visible()
        expect(page.get_by_role('button', name='Geprüfte Datei importieren')).to_be_visible()
        assert page.locator('input[name="import_token"]').input_value()
        page.screenshot(path=str(API_EVIDENCE / f'csv-ready-{width}-js-{javascript}.png'), full_page=True)
        _assert_full_width(page, width)
        _assert_rendered_icons(page)
        page.locator('#file').set_input_files({
            'name': 'ungueltig.csv', 'mimeType': 'text/csv',
            'buffer': b'wrong;header\ninvalid;row\n',
        })
        page.get_by_role('button', name='Vorschau prüfen', exact=True).click()
        expect(page.locator('#file-error')).to_be_visible()
        expect(page.locator('#file')).to_have_attribute('aria-invalid', 'true')
        page.screenshot(path=str(API_EVIDENCE / f'csv-error-{width}-js-{javascript}.png'), full_page=True)
        _assert_full_width(page, width)
        _assert_rendered_icons(page)
    finally:
        page.context.close()
