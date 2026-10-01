"""DELTA-2: actual visibility, modal geometry/focus and native submit states."""
from __future__ import annotations

import hashlib
import json
import subprocess
from threading import Event, Thread

import pytest
from flask import render_template_string, request
from playwright.sync_api import expect, sync_playwright
from werkzeug.serving import make_server
from urllib.parse import parse_qs, urlsplit

from cafeteria.ui.semantics import ROOT, STATIC
from test_ui_semantics import semantic_app  # noqa: F401

PAGE = '''<!doctype html><html lang="de"><head>
<meta name="viewport" content="width=device-width, initial-scale=1">
{% for file in ['tokens.css', 'vendor/tabler/tabler.min.css', 'admin-tabler.css', 'ui-semantic.css'] %}
<link rel="stylesheet" href="{{ url_for('static', filename=file) }}">{% endfor %}
{% for file in ['vendor/tabler/tabler.min.js', 'admin.js', 'admin-asset-fallback.js'] %}
<script defer src="{{ url_for('static', filename=file) }}"></script>{% endfor %}
</head><body class="dishboard-admin"><main id="frame" class="container-fluid">
{% from 'admin/_macros.html' import list_row %}
{% from 'ui/_semantic.html' import icon_button, icon_summary, row_actions,
    read_detail_trigger, read_detail_dialog, status_badge_sem %}
<nav id="navigation"><a href="#target">Zum Objekt</a></nav>
{% for n in range(18) %}{{ list_row(primary='Vorher ' ~ n) }}{% endfor %}
<div id="target">{{ list_row(primary='Gemüse-Pastetli',
    actions=read_detail_trigger('review', 'ui.read_detail.review', 'Gemüse-Pastetli')) }}</div>
<div id="following">{{ list_row(primary='Folgeobjekt', meta=0, status=false,
    actions=read_detail_trigger('review', 'ui.read_detail.review', 'Gemüse-Pastetli', trigger_id='review-second')) }}</div>
{% call read_detail_dialog('review', 'Prüfhinweise', 'Gemüse-Pastetli · Patienten · Mittag') %}
{% for n in range(30) %}<p>Prüfhinweis {{ n }}: Vollständiger Hinweis bleibt lesbar.</p>{% endfor %}
{% endcall %}
<section id="controls">
{% for mode in ['icon', 'text'] %}
<form id="form-{{ mode }}" method="post" data-loading action="/save">
{{ icon_button('actions.save', mode=mode, id=mode, name='intent', value=mode) }}</form>
<details>{{ icon_summary('actions.edit', mode=mode, id='summary-' ~ mode) }}<p>Altadapter</p></details>
{{ row_actions([{'key':'actions.edit', 'mode':mode, 'id':'row-' ~ mode,
    'text':'Ändern', 'aria_label':'Suppe bearbeiten', 'type':'button'}]) }}
{% endfor %}
{{ icon_button('actions.edit', show_text=true, id='legacy-text', type='button') }}
{{ status_badge_sem('status.warning') }}
<label><input type="checkbox" id="choice">Option</label>
</section>
{% for n in range(18) %}{{ list_row(primary='Nachher ' ~ n) }}{% endfor %}
</main></body></html>'''

FILTER_PAGE = PAGE.split('<nav id="navigation">')[0] + '''
{% from 'ui/_semantic.html' import filter_bar_sem %}
<nav id="navigation">Bereiche</nav>
{% for n in range(18) %}{{ list_row(primary='Vorher ' ~ n) }}{% endfor %}
{% set filters %}<input name="scope" type="hidden" value="patienten">
<div><label for="tag">Kategorie</label><select name="tag" id="tag" class="form-select">
<option value="">Alle</option><option value="soup" selected>Suppe</option></select></div>
<label><input type="checkbox" name="archived" value="1" checked>Archivierte</label>{% endset %}
<div id="toolbar">{{ filter_bar_sem('/filters', id='catalog', search_value='Kraut & Brot',
    filters=filters, active=true, open=true, reset_url='/filters',
    segments='<nav id="profiles">Patienten</nav>'|safe) }}</div>
<div id="following">{{ list_row(primary='Folgeobjekt') }}</div>
{% for n in range(30) %}{{ list_row(primary='Nachher ' ~ n) }}{% endfor %}
</main></body></html>'''

# Inspect computed visibility, including ancestors, clipping and generated content.
# SVG path counts are irrelevant: one SVG is one rendered action symbol.
VISIBILITY = '''node => {
  function visible(el) {
    if (!el.getClientRects().length) return false;
    for (let p = el; p; p = p.parentElement) {
      const s = getComputedStyle(p);
      if (s.display === 'none' || s.visibility !== 'visible' || +s.opacity === 0 ||
          s.clipPath === 'inset(50%)' || p.hidden) return false;
    }
    return true;
  }
  const icons = [...node.querySelectorAll('svg, img')].filter(visible).length;
  const walker = document.createTreeWalker(node, NodeFilter.SHOW_TEXT);
  let text = '', part;
  while ((part = walker.nextNode())) {
    if (visible(part.parentElement)) text += part.textContent.trim();
  }
  let generatedIcons = 0;
  const pseudos = [];
  for (const el of [node, ...node.querySelectorAll('*')]) {
    if (!visible(el)) continue;
    for (const pseudo of ['::before', '::after']) {
      const s = getComputedStyle(el, pseudo);
      if (s.display === 'none' || s.visibility !== 'visible' || +s.opacity === 0 ||
          ['none', 'normal'].includes(s.content)) continue;
      const value = s.content.replace(/^"|"$/g, '');
      const glyph = !value && (parseFloat(s.borderTopWidth) > 0 || s.backgroundImage !== 'none');
      if (glyph) generatedIcons++;
      else text += value;
      pseudos.push({pseudo, value, glyph});
    }
  }
  return {icons: icons + generatedIcons, text, pseudos, gap: getComputedStyle(node).gap};
}'''

GEOMETRY = '''() => {
  const boxes = {};
  for (const id of ['navigation', 'frame', 'target', 'following', 'review-trigger']) {
    const r = document.getElementById(id).getBoundingClientRect();
    boxes[id] = {x:r.x, y:r.y, width:r.width, height:r.height};
  }
  return {boxes, scroll:{x:scrollX, y:scrollY},
    documentScroll:document.scrollingElement.scrollTop,
    internalScroll:document.getElementById('frame').scrollTop,
    scrollbar:innerWidth - document.documentElement.clientWidth};
}'''


@pytest.fixture
def delta_site(semantic_app):  # noqa: F811
    release = Event()
    submissions = []

    @semantic_app.get('/')
    def page():
        return render_template_string(PAGE)

    @semantic_app.get('/filters')
    def filters():
        return render_template_string(FILTER_PAGE)

    @semantic_app.post('/save')
    def save():
        submissions.append(request.form.to_dict())
        release.wait(15)
        return '', 204

    server = make_server('127.0.0.1', 0, semantic_app, threaded=True)
    thread = Thread(target=server.serve_forever, daemon=True)
    thread.start()
    try:
        yield f'http://127.0.0.1:{server.server_port}', release, submissions
    finally:
        release.set()
        server.shutdown()
        server.server_close()
        thread.join(timeout=5)


def source_revision():
    repo = ROOT.parents[2]
    head = subprocess.check_output(['rtk', 'git', 'rev-parse', 'HEAD'], cwd=repo,
                                   text=True, timeout=10).strip()
    paths = [ROOT.parent / 'templates/ui/_semantic.html',
             ROOT.parent / 'templates/admin/_macros.html',
             STATIC / 'admin.js', STATIC / 'ui-semantic.css', STATIC / 'admin-tabler.css']
    return {'head': head, 'source_sha256': {
        str(p.relative_to(ROOT.parent)): hashlib.sha256(p.read_bytes()).hexdigest() for p in paths}}


def assert_stable(before, during):
    for name, box in before['boxes'].items():
        for axis, value in box.items():
            assert abs(value - during['boxes'][name][axis]) <= 1, (name, axis, before, during)
    assert before['scroll'] == during['scroll']
    assert before['documentScroll'] == during['documentScroll']
    assert before['internalScroll'] == during['internalScroll']


@pytest.mark.parametrize(('width', 'height', 'touch'), [
    (1440, 900, False), (1024, 768, False), (768, 1024, True),
    (390, 844, True), (1920, 1080, False),
])
def test_read_dialog_geometry_focus_and_escape(delta_site, tmp_path, width, height, touch):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(viewport={'width': width, 'height': height}, has_touch=touch)
        try:
            page.goto(delta_site[0])
            page.evaluate('document.fonts.ready')
            trigger = page.locator('#review-trigger')
            trigger.scroll_into_view_if_needed()
            trigger.evaluate('el => window.scrollTo(0, el.getBoundingClientRect().top + scrollY - 200)')
            trigger.evaluate('el => el.focus({preventScroll:true})')
            before = page.evaluate(GEOMETRY)
            assert before['scroll']['y'] > 0
            page.screenshot(path=str(tmp_path / 'before.png'))
            trigger.press('Enter')
            expect(page.locator('#review-title')).to_be_focused()
            assert page.locator('#review').evaluate('d => d.matches(":modal")')
            expect(page.locator('#review a, #review button')).to_have_count(1)
            expect(page.locator('[data-read-detail-close]')).to_be_in_viewport(ratio=1)
            during = page.evaluate(GEOMETRY)
            page.screenshot(path=str(tmp_path / 'during.png'))
            assert_stable(before, during)
            page.keyboard.press('Tab')
            expect(page.locator('.ui-read-detail-content')).to_be_focused()
            page.keyboard.press('PageDown')
            page.wait_for_function('document.querySelector(".ui-read-detail-content").scrollTop > 0')
            page.keyboard.press('Tab')
            expect(page.locator('[data-read-detail-close]')).to_be_focused()
            page.locator('.ui-read-detail-content').evaluate('d => {d.scrollTop = 300}')
            expect(page.locator('#review-title')).to_be_in_viewport(ratio=1)
            expect(page.locator('[data-read-detail-close]')).to_be_in_viewport(ratio=1)
            page.keyboard.press('Escape')
            expect(trigger).to_be_focused()
            expect(page.locator('#review')).not_to_be_visible()
            after = page.evaluate(GEOMETRY)
            assert_stable(before, after)
            trigger.press('Enter')
            expect(page.locator('#review-title')).to_be_focused()
            assert page.locator('.ui-read-detail-content').evaluate('d => d.scrollTop') == 0
            page.locator('[data-read-detail-close]').click()
            expect(trigger).to_be_focused()
            assert_stable(before, page.evaluate(GEOMETRY))
            page.screenshot(path=str(tmp_path / 'after.png'))
            (tmp_path / 'geometry.json').write_text(json.dumps({
                'revision': source_revision(), 'viewport': [width, height], 'touch': touch,
                'browser': browser.version, 'scrollbar_type': 'classic' if before['scrollbar'] else 'overlay',
                'before': before, 'during': during, 'after': after,
            }, indent=2), encoding='utf-8')
        finally:
            browser.close()


@pytest.mark.parametrize('width', [390, 1440])
def test_nojs_read_content_remains_reachable(delta_site, width):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page(java_script_enabled=False, viewport={'width': width, 'height': 900})
        try:
            page.goto(delta_site[0])
            page.locator('#review-trigger').click()
            expect(page.locator('#review')).to_be_visible()
            expect(page.locator('[data-read-detail-close]')).to_be_in_viewport(ratio=1)
            expect(page.locator('#review p').last).to_contain_text('Prüfhinweis 29')
            page.locator('[data-read-detail-close]').click()
            expect(page.locator('#review')).not_to_be_visible()
            expect(page.locator('#review-trigger')).to_be_in_viewport()
        finally:
            browser.close()


def test_computed_modes_loading_disabled_and_asset_fallback(delta_site, tmp_path):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(delta_site[0])
            evidence = {}
            for mode in ['icon', 'text']:
                for prefix in ['', 'summary-', 'row-']:
                    control = page.locator('#' + prefix + mode)
                    control.scroll_into_view_if_needed()
                    result = control.evaluate(VISIBILITY)
                    evidence[prefix + mode] = result
                    assert result['icons'] == (1 if mode == 'icon' else 0)
                    assert bool(result['text']) == (mode == 'text')
                    if mode == 'text':
                        assert result['gap'] == '0px'
                        assert result['text'] in control.get_attribute('aria-label')
                control = page.locator('#' + mode)
                control.scroll_into_view_if_needed()
                before_width = control.bounding_box()['width']
                control.click()
                expect(control).to_have_attribute('aria-busy', 'true')
                expect(control).to_be_disabled()
                result = control.evaluate(VISIBILITY)
                evidence[mode + '-loading'] = result
                assert result['icons'] == (1 if mode == 'icon' else 0)
                assert bool(result['text']) == (mode == 'text')
                assert abs(before_width - control.bounding_box()['width']) <= 1
                page.evaluate('window.dispatchEvent(new Event("pageshow"))')
                expect(control).to_be_enabled()
            assert page.locator('#legacy-text').evaluate(VISIBILITY)['icons'] == 0
            page.locator('#choice').check()
            expect(page.locator('#choice')).to_be_checked()
            assert page.locator('[data-semantic="status.warning"]').evaluate(VISIBILITY)['icons'] == 1
            page.route('**/tabler-icons.svg', lambda route: route.abort())
            page.reload()
            expect(page.locator('html')).to_have_class('ui-asset-sprite-missing')
            fallback = page.locator('#icon').evaluate(VISIBILITY)
            assert fallback['icons'] == 0 and fallback['text'] == 'Speichern'
            assert page.locator('#text').evaluate(VISIBILITY)['icons'] == 0
            evidence['fallback'] = fallback
            (tmp_path / 'visibility.json').write_text(json.dumps(evidence, indent=2), encoding='utf-8')
        finally:
            delta_site[1].set()
            browser.close()


@pytest.mark.parametrize('width', [390, 1440])
def test_delta2b_filter_modal_geometry_query_focus_and_nojs(delta_site, tmp_path, width):
    geometry = GEOMETRY.replace("'target', 'following', 'review-trigger'",
                                "'toolbar', 'following', 'catalog-trigger', 'profiles'")
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        try:
            evidence = {}
            for javascript in [False, True]:
                page = browser.new_page(java_script_enabled=javascript,
                                        viewport={'width': width, 'height': 900})
                page.goto(delta_site[0] + '/filters')
                trigger = page.locator('#catalog-trigger')
                dialog = page.locator('#catalog-dialog')
                expect(dialog).not_to_be_visible()
                expect(page.locator('.admin-filter-chip')).to_have_count(2)
                expect(page.locator('#profiles')).to_be_visible()
                trigger.scroll_into_view_if_needed()
                if javascript:
                    trigger.evaluate('el => el.focus({preventScroll:true})')
                    before = page.evaluate(geometry)
                    page.screenshot(path=str(tmp_path / 'filter-before.png'))
                    trigger.press('Enter')
                    expect(page.locator('#catalog-dialog-title')).to_be_focused()
                    assert dialog.evaluate('d => d.matches(":modal")')
                    during = page.evaluate(geometry)
                    assert_stable(before, during)
                    page.screenshot(path=str(tmp_path / 'filter-during.png'))
                    page.keyboard.press('Tab')
                    expect(page.get_by_label('Kategorie')).to_be_focused()
                    page.keyboard.press('Escape')
                    expect(trigger).to_be_focused()
                    expect(dialog).not_to_be_visible()
                    assert_stable(before, page.evaluate(geometry))
                    trigger.press('Enter')
                    dialog.locator('[data-read-detail-close]').click()
                    expect(trigger).to_be_focused()
                    assert_stable(before, page.evaluate(geometry))
                    evidence = {'before': before, 'during': during, 'after': page.evaluate(geometry)}
                trigger.click()
                expect(dialog).to_be_visible()
                expect(dialog.locator('[data-read-detail-close]')).to_have_count(1)
                page.get_by_label('Kategorie').select_option('')
                page.get_by_label('Archivierte', exact=True).uncheck()
                dialog.locator('[data-semantic="actions.apply"]').click()
                page.wait_for_url('**/filters?**')
                assert parse_qs(urlsplit(page.url).query, keep_blank_values=True) == {
                    'q': ['Kraut & Brot'], 'scope': ['patienten'], 'tag': ['']}
                expect(dialog).not_to_be_visible()
                page.close()
            (tmp_path / 'filter-geometry.json').write_text(json.dumps({
                'revision': source_revision(), 'viewport': width, **evidence,
            }, indent=2), encoding='utf-8')
        finally:
            browser.close()


def test_delta2b_read_dialog_returns_to_actual_trigger(delta_site):
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        page = browser.new_page()
        try:
            page.goto(delta_site[0])
            for identifier in ['review-trigger', 'review-second', 'review-trigger']:
                trigger = page.locator('#' + identifier)
                trigger.click()
                expect(page.locator('#review-title')).to_be_focused()
                page.keyboard.press('Escape')
                expect(trigger).to_be_focused()
        finally:
            browser.close()
