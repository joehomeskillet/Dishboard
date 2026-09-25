"""P01–P10: Werkzeugseiten priorisieren Aufgabe, Wirkung und Prüfstatus."""
from __future__ import annotations

import datetime as dt
import json
from pathlib import Path
from tempfile import TemporaryDirectory

import pytest
from playwright.sync_api import Page, expect
from sqlalchemy import text

from cafeteria.api_keys import create_api_key, revoke_api_key

from test_admin_workflow_routes import WEEK, _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_korrektur_cookbooks_browser import _native_viewport_capture
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
    return page.locator('details.admin-api-key-details[open] [data-label="Präfix"] code')


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
        create = page.locator('#api-key-create').locator('xpath=ancestor::details')
        expect(create).not_to_have_attribute('open', '')
        _assert_no_duplicate_primary_action(page)
        create.locator('summary').click()
        page.locator('#api-key-create').evaluate('form => { form.noValidate = true; }')
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            page.locator('#api-key-create button[type="submit"]').click()
        assert rejected.value.status == 400
        expect(create).to_have_attribute('open', '')
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
        expect(page.locator('#copy-description')).to_contain_text('Quelle:')
        expect(page.locator('#copy-description')).to_contain_text('Ziel:')
        expect(page.locator('#copy-effects')).to_contain_text(
            'Wochenkopf, Ausgabeangaben und Menüs werden aus der Quellwoche übernommen.'
        )
        expect(page.locator('#copy-effects')).to_contain_text(
            'Prüfbestätigungen werden nicht übernommen; die Zielwoche bleibt ein Entwurf.'
        )
        _assert_no_duplicate_primary_action(page)

        _goto(page, f'/admin/cafeteria/wochen/pruefung?week={WEEK.isoformat()}')
        expect(page.get_by_role('heading', name='Wochenkopf und Ausgabeangaben prüfen')).to_be_visible()
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
                expect(page.locator('[data-api-status]')).to_contain_text('Nicht veröffentlicht')
                for state in ('active', 'expired', 'revoked'):
                    expect(page.locator(f'[data-key-state="{state}"]')).to_be_visible()
                assert page.locator('[data-key-state="active"] button').count() == 1
                assert page.locator('[data-key-state="expired"] button, [data-key-state="revoked"] button').count() == 0
                expect(page.locator('[data-api-help], [data-api-versions]')).to_have_count(2)
                for selector in ('[data-api-help]', '[data-api-versions]'):
                    details = page.locator(selector)
                    expect(details).not_to_have_attribute('open', '')
                    summary = details.locator('summary')
                    summary.focus()
                    page.keyboard.press('Enter')
                    expect(details).to_have_attribute('open', '')
                    _assert_full_width(page, width)
                    _assert_rendered_icons(page)
                    assert summary.bounding_box()['height'] >= 48
                    page.keyboard.press('Enter')
                    expect(details).not_to_have_attribute('open', '')
                assert 'dbk_' not in ' '.join(page.locator('main summary').all_text_contents())
                key_details = page.locator('[data-key-state="active"] .admin-api-key-details')
                key_details.locator('summary').click()
                expect(key_details).to_have_attribute('open', '')
                prefix_mask = _api_prefix_mask_locators(page)
                expect(prefix_mask).to_have_count(1)
                page.evaluate('if (document.activeElement && document.activeElement.blur) { document.activeElement.blur(); }')
                page.evaluate('window.scrollTo(0, 0)')
                geometry = page.evaluate('''() => ({
                    height: document.documentElement.scrollHeight,
                    firstContentY: document.querySelector('[data-api-keys]').getBoundingClientRect().y,
                    publicationY: document.querySelector('[data-api-status]').getBoundingClientRect().y,
                    documentOverflow: document.documentElement.scrollWidth - innerWidth
                })''')
                assert geometry['documentOverflow'] <= 1, (width, javascript, geometry)
                measurements.append({'width': width, 'javascript': javascript, **geometry})
                page.screenshot(path=str(API_EVIDENCE / f'keys-{width}-js-{javascript}.png'),
                                full_page=True, mask=[prefix_mask])
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
        summary = page.locator('#api-key-create-title')
        form = page.locator('#api-key-create')
        summary.focus()
        page.keyboard.press('Enter')
        page.get_by_role('button', name='Schlüssel erstellen').click()
        expect(page.locator('#api-key-label')).to_be_focused()
        page.get_by_label('Bezeichnung', exact=True).fill('Synthetischer Browserzugang')
        page.locator('#api-key-channel-cafeteria').check()
        page.locator('#api-key-channel-patienten').check()
        expiry = page.locator('#api-key-expires').input_value()
        original = form.evaluate('form => [...new FormData(form)]')
        summary.click()
        summary.click()
        assert bool(original == form.evaluate('form => [...new FormData(form)]'))
        with page.expect_response(lambda response: response.request.method == 'POST') as rejected:
            page.get_by_role('button', name='Schlüssel erstellen').click()
        assert rejected.value.status == 400  # No scope selected: existing server validation.
        expect(form.get_by_role('alert')).to_be_visible()
        if javascript:
            expect(form.get_by_role('alert')).to_be_focused()
        expect(page.locator('#api-key-label')).to_have_value('Synthetischer Browserzugang')
        expect(page.locator('#api-key-expires')).to_have_value(expiry)
        for channel in ('cafeteria', 'patienten'):
            expect(page.locator(f'#api-key-channel-{channel}')).to_be_checked()
        summary.click()
        expect(summary).to_contain_text('Fehler')
        summary.click()
        page.locator('#api-key-scope-preview').check()
        page.get_by_role('button', name='Schlüssel erstellen').click()
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
        details = row.locator('details')
        expect(details.locator('summary')).to_have_attribute(
            'aria-label', 'Details zu Synthetischer Browserzugang'
        )
        details.locator('summary').click()
        expect(details).to_contain_text('Zuletzt verwendet')
        _assert_full_width(page, width)
        if javascript:
            page.once('dialog', lambda dialog: dialog.dismiss())
            row.get_by_role('button', name='Widerrufen').click()
            expect(row).to_be_visible()
            page.once('dialog', lambda dialog: dialog.accept())
        row.get_by_role('button', name='Widerrufen').click()
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
         'form.admin-copy-actions button.btn-primary'),
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
            page.locator('summary#api-key-create-title').click()
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
    icons = page.locator('main svg.icon')
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
         'form.admin-copy-actions button.btn-primary'),
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
        expect(result).to_contain_text('Cafeteria')
        expect(result).not_to_contain_text('andere-datei.csv')
        page.locator('#file').set_input_files({
            'name': 'andere-datei.csv',
            'mimeType': 'text/csv',
            'buffer': b'wrong;header\ninvalid;row\n',
        })
        assert page.locator('[data-checked-identity]').inner_text() == identity
        assert result.get_attribute('data-checked-week') == week
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
            expect(upload.locator('details')).not_to_have_attribute('open', '')
            names = set(upload.locator('[name]').evaluate_all('nodes => nodes.map(node => node.name)'))
            assert names == {'_csrf', 'file'}
            summary = upload.locator('details summary').first
            summary.focus()
            expect(summary).to_be_focused()
            page.keyboard.press('Enter')
            expect(upload.locator('details').first).to_have_attribute('open', '')
            expect(upload.locator('details').first).to_contain_text('getrennte Formate')
            page.keyboard.press('Enter')
            expect(upload.locator('details').first).not_to_have_attribute('open', '')
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
                expect(page.locator('.admin-compact-row')).to_have_count(5)
                expect(page.locator('main')).to_contain_text('Kein Ausgabehinweis')
            if name == 'copy':
                expect(page.locator('#copy-description')).to_contain_text('Quelle:')
                expect(page.locator('#copy-description')).to_contain_text('Ziel:')
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
