"""UI-DELTA regression probes; test-only, computed output rather than SVG counts."""
from __future__ import annotations

import json
from pathlib import Path
from urllib.parse import urlsplit

from test_delta_renderer_browser import source_revision

ROOT = Path(__file__).resolve().parents[2]
MATRIX = ROOT / 'docs/superpowers/backlog-0909/ui-route-matrix.json'


class DocumentedFinding(AssertionError):
    """Only documented terminal findings qualify for strict XFAIL."""


# Native navigation/selection exceptions are explicit. Ordinary navs and arbitrary
# aria-expanded controls are deliberately not exempted.
PROBE = r'''() => {
  const native = '.admin-sidebar, [role="combobox"], [role="listbox"], '
    + '.ts-wrapper, .datepicker, .flatpickr-calendar';
  function visible(el) {
    if (!el || !el.getClientRects().length) return false;
    for (let p = el; p; p = p.parentElement) {
      if (p.tagName === 'DETAILS' && !p.open && p !== el) {
        const summary = [...p.children].find(child => child.tagName === 'SUMMARY');
        if (!summary?.contains(el)) return false;
      }
      const s = getComputedStyle(p), r = p.getBoundingClientRect();
      if (p.hidden || s.display === 'none' || s.visibility !== 'visible' || +s.opacity === 0
          || s.clipPath === 'inset(50%)' || s.clip === 'rect(0px, 0px, 0px, 0px)'
          || (r.width <= 1 && r.height <= 1 && s.overflow === 'hidden')) return false;
    }
    return true;
  }
  function selector(el) {
    if (el.id) return '#' + CSS.escape(el.id);
    const parts = [];
    while (el && el.tagName !== 'HTML') {
      const n = [...el.parentElement.children].indexOf(el) + 1;
      parts.unshift(el.tagName.toLowerCase() + ':nth-child(' + n + ')');
      el = el.parentElement;
      if (el?.id) {parts.unshift('#' + CSS.escape(el.id)); break;}
    }
    return parts.join(' > ');
  }
  function output(el) {
    let text = '', icons = 0;
    const pseudos = [];
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let part;
    while ((part = walker.nextNode())) {
      if (visible(part.parentElement) && !part.parentElement.closest('svg, script, style'))
        text += part.textContent;
    }
    if (el.matches('input[type="submit"], input[type="button"]')) text += el.value;
    icons += [...el.querySelectorAll('svg, img, .spinner-border, .spinner-grow, i.ti')]
      .filter(visible).length;
    for (const node of [el, ...el.querySelectorAll('*')]) {
      if (!visible(node)) continue;
      if (/url\(/.test(getComputedStyle(node).backgroundImage)
          && !node.matches('svg, img')) icons++;
      // Tabler's hamburger is one CSS graphic made from three solid bars.
      // Its generated bars are parts of that graphic, just like SVG paths.
      if (node.matches('.navbar-toggler-icon')
          && getComputedStyle(node).backgroundImage === 'none'
          && getComputedStyle(node).backgroundColor !== 'rgba(0, 0, 0, 0)') icons++;
      for (const pseudo of ['::before', '::after']) {
        const s = getComputedStyle(node, pseudo);
        if (s.display === 'none' || s.visibility !== 'visible' || +s.opacity === 0
            || ['none', 'normal'].includes(s.content)) continue;
        const value = s.content.replace(/^['"]|['"]$/g, '');
        const triangle = parseFloat(s.borderTopWidth) > 0
          && parseFloat(s.borderLeftWidth) > 0 && parseFloat(s.borderRightWidth) > 0;
        const rotated = s.transform !== 'none' && (parseFloat(s.borderTopWidth) > 0
          || parseFloat(s.borderRightWidth) > 0);
        const glyph = /[\u2190-\u21ff\u25a0-\u27ff\ue000-\uf8ff]/u.test(value)
          || /icon|tabler/i.test(s.fontFamily) || /url\(/.test(s.content + s.backgroundImage)
          || (!value && (triangle || rotated));
        if (glyph) icons++; else text += value;
        pseudos.push({selector:selector(node), pseudo, value, glyph});
      }
    }
    return {text:text.replace(/\s+/g, ' ').trim(), icons, pseudos};
  }
  const controls = [], findings = [], exceptions = [];
  const add = (kind, el, data) => findings.push({kind, selector:selector(el), ...data});
  for (const el of document.querySelectorAll('button, a.btn, a.ui-sem-control, '
       + '.admin-segments a, [role="button"], [role="tab"], summary, '
       + 'input[type="submit"], input[type="button"]')) {
    if (!visible(el)) continue;
    const result = output(el);
    controls.push({selector:selector(el), name:el.getAttribute('aria-label') || result.text,
      semantic:el.dataset.semantic || null, disabled:el.disabled || false, ...result});
    if (result.icons && result.text) add('mixed', el, result);
    if (result.icons > 1) add('duplicate-icon', el, result);
  }
  for (const el of document.querySelectorAll('.admin-list-status, .admin-list-meta, '
       + '.admin-list-subtitle, .admin-list-markings, td')) {
    if (!visible(el)) continue;
    const result = output(el);
    if (/^[-–—−]$/.test(result.text) && !result.icons) add('placeholder', el, result);
  }
  for (const el of document.querySelectorAll('details > summary, [aria-expanded]')) {
    if (!visible(el)) continue;
    let target = el.parentElement?.tagName === 'DETAILS' ? el.parentElement : null;
    const id = el.getAttribute('aria-controls');
    if (!target && id) target = document.getElementById(id);
    const query = el.getAttribute('data-bs-target') || el.getAttribute('href');
    if (!target && query?.startsWith('#')) {
      try {target = document.querySelector(query);} catch (_) { /* An invalid selector is not a target. */ }
    }
    if (el.closest(native) || target?.matches('[role="listbox"]')) {
      exceptions.push({selector:selector(el), kind:'native-navigation-or-selection'}); continue;
    }
    if (target && !target.matches('dialog, .modal, [role="dialog"]'))
      add('disclosure', el, {text:output(el).text, target:selector(target)});
  }
  return {controls, findings, exceptions};
}'''

MEASURE = r'''selectors => {
  const boxes = {}, fixed = {};
  for (const selector of selectors) {
    const el = document.querySelector(selector);
    if (!el) throw new Error('Missing geometry reference: ' + selector);
    const r = el.getBoundingClientRect();
    boxes[selector] = {x:r.x, y:r.y, width:r.width, height:r.height};
    fixed[selector] = false;
    for (let p = el; p; p = p.parentElement)
      if (getComputedStyle(p).position === 'fixed') fixed[selector] = true;
  }
  return {boxes, fixed, scroll:{x:scrollX,y:scrollY},
    documentScroll:document.scrollingElement.scrollTop,
    internalScroll:document.querySelector('.page-wrapper')?.scrollTop || 0,
    scrollbar:innerWidth-document.documentElement.clientWidth,
    viewport:{width:innerWidth,height:innerHeight,zoom:visualViewport.scale}};
}'''


def write_json(path, value):
    path.write_text(json.dumps(value, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')


def record_transition(path, purpose, samples, browser_version, *, javascript=True):
    """Full coordinates, row heights and scroll state for every transition phase."""
    before = samples[0]['measurement']
    record = dict(purpose=purpose, revision=source_revision(), browser=browser_version,
                  javascript=javascript, tolerance_css_px=1, samples=samples,
                  scrollbar_type='classic' if before['scrollbar'] else 'overlay',
                  viewport=before['viewport'], references=list(before['boxes']))
    write_json(path.with_suffix('.json'), record)
    rows = ['# DX-T42 — ' + purpose, '', 'Revision: ' + record['revision']['head'], '',
            '| Phase | Referenzelement | x / y / Breite / Zeilenhöhe | Scroll x / y |',
            '|---|---|---|---|']
    for sample in samples:
        m = sample['measurement']
        for name, box in m['boxes'].items():
            values = ' / '.join(f'{box[k]:.3f}' for k in ('x', 'y', 'width', 'height'))
            rows.append(f'| {sample["phase"]} | `{name}` | {values} '
                        f'| {m["scroll"]["x"]} / {m["scroll"]["y"]} |')
    rows.extend(['', f'Viewport: {record["viewport"]}; Scrollbartyp: {record["scrollbar_type"]}.',
                 'JSON enthält zusätzlich Dokument- und interne Scrollposition, Quellhashes und Browser.'])
    path.with_suffix('.md').write_text('\n'.join(rows) + '\n', encoding='utf-8')


def admin_routes(application, prepared):
    """Resolve the versioned inventory against actual Flask rules and fixture IDs."""
    matrix = json.loads(MATRIX.read_text())
    adapter = application.url_map.bind('localhost')
    result = []
    for row in matrix['routes']:
        if not row['visual'] or 'GET' not in row['methods'] or not row['endpoint'].startswith('admin.'):
            continue
        endpoint = row['endpoint']
        paths = set()
        for rule in application.url_map.iter_rules(endpoint):
            if rule.arguments <= {'family'}:
                for family in ('cafeteria', 'patienten') if rule.arguments else (None,):
                    paths.add(adapter.build(endpoint, {'family': family} if family else {}))
        if endpoint in prepared['endpoint_paths']:
            paths.add(prepared['endpoint_paths'][endpoint])
            query = urlsplit(prepared['endpoint_paths'][endpoint]).query
            if query:
                paths = {p if '?' in p else p + '?' + query for p in paths}
        if endpoint == 'admin.week_review_get':
            paths = {p + '?week=2026-08-31' for p in paths}
        if endpoint == 'admin.master_data_list':
            paths.update('/admin/grundlagen?kind=' + kind
                         for kind in ('foods', 'units', 'categories', 'tags', 'storage_locations'))
        result.append(dict(endpoint=endpoint, templates=row['templates'], paths=sorted(paths),
                           classification=row['classification']))
    return result
