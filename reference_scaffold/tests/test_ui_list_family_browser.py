"""Listenfamilie: jede Admin-Liste vermessen, vergleichen und per Baseline absichern.

Zielwerte aus docs/design/2026-09-26-icon-first-simplification-spec.md (§3.2, §4, §5):
keine sichtbare Beschriftung an Zeilen- und Kopf-Aktionsbuttons, höchstens zwei
Zeilenaktionen, keine Karte je Zeile, gleiche Kopf-/Haupt-/Sekundärtypografie.
UI_LIST_FAMILY_REPORT=1 schreibt den Vergleich, die Screenshots und die Baseline.
Ohne diese Variable schlägt der Test nur bei einer neuen Seite oder einer neuen
Abweichung fehl und nennt erfüllte Baseline-Einträge.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import UTC, datetime, timedelta
from pathlib import Path

from playwright.sync_api import sync_playwright

from cafeteria.api_keys import create_api_key
from cafeteria.public.routes import bp as public_bp
from test_admin_ux_browser import admin_app, admin_engine, live_server  # noqa: F401
from test_admin_workflow_routes import _login
from test_ui_route_inventory import _prepare_inventory_entities

ROOT = Path(__file__).resolve().parents[2]
BASELINE_PATH = Path(__file__).resolve().parent / 'list_family_baseline.json'
REPORT_PATH = ROOT / 'docs/design/2026-09-26-list-family-comparison.md'
EVIDENCE = ROOT / '.claude/evidence/list-family-0926'
WEEK = '2026-08-31'

MEASURE_JS = r"""() => {
  const main = document.querySelector('main') || document.querySelector('.page-body') || document.body;
  const cls = (el) => (typeof el.className === 'string' ? el.className : '');
  const inClosed = (el) => {
    for (let p = el.parentElement; p; p = p.parentElement) {
      if (p.tagName === 'DETAILS' && !p.open) {
        const summary = p.querySelector(':scope > summary');
        if (summary && (el === summary || summary.contains(el))) continue;
        return true;
      }
    }
    return false;
  };
  const hiddenBox = (el) => {
    const s = getComputedStyle(el);
    if (s.display === 'none' || s.visibility === 'hidden' || Number(s.opacity) === 0) return true;
    const r = el.getBoundingClientRect();
    return r.width < 1 || r.height < 1;
  };
  const visible = (el) => !!el && !el.closest('[hidden], [inert]') && !inClosed(el) && !hiddenBox(el);
  const clipped = (el) => {
    if (!el || el.closest('.visually-hidden, .sr-only')) return true;
    const s = getComputedStyle(el);
    return parseFloat(s.fontSize) === 0 || (s.position === 'absolute' && parseFloat(s.width) <= 1 && parseFloat(s.height) <= 1);
  };
  const visibleText = (el) => {
    const walker = document.createTreeWalker(el, NodeFilter.SHOW_TEXT);
    let text = '';
    while (walker.nextNode()) {
      const parent = walker.currentNode.parentElement;
      if (!parent || parent.closest('.admin-filter-count') || clipped(parent) || !visible(parent)) continue;
      text += walker.currentNode.nodeValue;
    }
    return text.replace(/\s+/g, ' ').trim();
  };
  const chrome = 'nav, .navbar, .pagination, .breadcrumb, .nav-tabs, .nav-pills, .profile-tabs, .week-filter, .kitchen-cal-filters, .menu-view-switch, aside';
  const isControl = (el) => {
    if (!el.matches('a, button, summary') || !visible(el) || el.closest(chrome)) return false;
    const c = cls(el);
    if (c.includes('btn') || c.includes('ui-sem-control') || el.hasAttribute('data-semantic') || el.hasAttribute('data-admin-icon-action')) return true;
    return !!el.closest('.admin-list-actions, .admin-table-actions, .admin-row-actions, .admin-week-card-action, .component-action, .lager-row-action, .week-actions, .admin-compact-actions, .week-more');
  };
  const controls = (root) => [...root.querySelectorAll('a, button, summary')].filter((el) => {
    if (!root.contains(el) || !isControl(el)) return false;
    const outer = el.parentElement && el.parentElement.closest('a, button, summary');
    return !outer || !root.contains(outer);
  });
  const iconNames = (el) => [...el.querySelectorAll('use')].map((use) => (use.getAttribute('href') || use.getAttribute('xlink:href') || '').split('#').pop()).filter(Boolean);
  const packActions = (acts) => {
    const texts = acts.map(visibleText).filter(Boolean);
    const icons = [...new Set(acts.flatMap(iconNames))];
    return {
      count: acts.length,
      withText: texts.length,
      texts: texts.slice(0, 8),
      icons: icons.slice(0, 8),
      family: icons.length ? (icons.every((name) => name.startsWith('tabler')) ? 'tabler' : 'gemischt') : 'keins',
      hits: acts.slice(0, 6).map((el) => {
        const r = el.getBoundingClientRect();
        return Math.round(r.width) + '×' + Math.round(r.height);
      }),
      filled: acts.filter((el) => cls(el).includes('btn-primary')).length,
    };
  };
  const paint = (el) => {
    const s = getComputedStyle(el);
    return {tag: el.tagName.toLowerCase(), border: s.borderTopWidth + ' ' + s.borderTopStyle + ' ' + s.borderTopColor, radius: s.borderRadius, shadow: s.boxShadow === 'none' ? 'none' : 'vorhanden'};
  };
  const isCard = (row) => {
    if (row.matches('article.recipe-card, article.menu-slot, article.screen-card, article.screen-choice-card')) return true;
    if (row.closest('table')) return false;
    const s = getComputedStyle(row);
    const radius = s.borderRadius.split(/\s+/).some((v) => parseFloat(v) >= 4);
    const shadow = !!s.boxShadow && s.boxShadow !== 'none';
    const gap = parseFloat(s.marginTop) + parseFloat(s.marginBottom) >= 8;
    return (radius && shadow) || (radius && gap) || (shadow && gap);
  };
  const textInfo = (el) => {
    if (!el) return null;
    const s = getComputedStyle(el);
    const link = el.matches('a') ? el : (el.querySelector('a') || el.closest('a'));
    return {fontSize: s.fontSize, fontWeight: String(s.fontWeight), color: s.color, link: !!link, linkColor: link ? getComputedStyle(link).color : ''};
  };
  const shellOf = (root, kind) => {
    if (kind === 'karten') return root;
    const card = root.closest('.card');
    if (card && card !== root && main.contains(card) && !card.matches('article')) return card;
    return root;
  };
  const labelOf = (root) => {
    if (root.tagName === 'TABLE') {
      const cap = root.querySelector('caption');
      if (cap && cap.textContent.trim()) return cap.textContent.trim().replace(/\s+/g, ' ').slice(0, 80);
      const labelled = root.getAttribute('aria-label');
      if (labelled) return labelled.slice(0, 80);
    }
    const own = root.getAttribute && root.getAttribute('aria-label');
    if (own) return own.slice(0, 80);
    let p = root;
    for (let i = 0; i < 5 && p; i += 1, p = p.parentElement) {
      const heading = [...p.children].find((child) => /^H[2-4]$/.test(child.tagName) && child.textContent.trim());
      if (heading) return heading.textContent.trim().replace(/\s+/g, ' ').slice(0, 80);
    }
    return root.tagName.toLowerCase();
  };
  const groups = [];
  const used = new Set();
  const push = (root, rows, kind) => {
    const fresh = rows.filter((row) => row && !used.has(row) && visible(row) && !row.closest('nav, .navbar, .pagination, .breadcrumb, aside'));
    if (!fresh.length) return;
    fresh.forEach((row) => used.add(row));
    groups.push({root, rows: fresh.slice(0, 3), total: fresh.length, kind});
  };
  const cluster = (selector, kind, rootOf) => {
    const map = new Map();
    for (const el of main.querySelectorAll(selector)) {
      const parent = rootOf(el) || main;
      if (!map.has(parent)) map.set(parent, []);
      map.get(parent).push(el);
    }
    for (const [parent, rows] of map) push(parent, rows, kind);
  };
  const parentOf = (el) => el.parentElement || main;
  cluster('article.menu-slot', 'karten', (el) => el.closest('section') || parentOf(el));
  cluster('article.recipe-card', 'karten', parentOf);
  cluster('article.screen-card', 'karten', parentOf);
  cluster('article.screen-choice-card', 'karten', parentOf);
  cluster('li.print-tpl-row', 'zeilen', parentOf);
  cluster('li.kitchen-cal-list-day:not(.kitchen-cal-list-day-empty)', 'zeilen', parentOf);
  for (const table of main.querySelectorAll('table')) {
    if (!visible(table) || table.closest('nav, .navbar, article.menu-slot, article.recipe-card, article.screen-card')) continue;
    let rows = [...table.querySelectorAll(':scope > tbody > tr')].filter((tr) => tr.querySelector('td, th[scope=row]'));
    if (table.classList.contains('kitchen-cal-table')) {
      const days = [...table.querySelectorAll('td.kitchen-cal-day')].filter((td) => !td.classList.contains('kitchen-cal-day-muted') && visible(td));
      const busy = days.filter((td) => td.querySelector('.kitchen-cal-dish, .kitchen-cal-event, .kitchen-cal-meal'));
      rows = busy.length ? busy : days;
    }
    push(table, rows, 'tabelle');
  }
  const loose = new Map();
  for (const el of main.querySelectorAll('.admin-list-row')) {
    if (used.has(el) || el.closest('article.recipe-card, article.menu-slot, table')) continue;
    const item = el.closest('[role=listitem], [data-account-row]') || el;
    const parent = item.parentElement || main;
    if (!loose.has(parent)) loose.set(parent, []);
    if (!loose.get(parent).includes(item)) loose.get(parent).push(item);
  }
  for (const [parent, rows] of loose) push(parent, rows, 'zeilen');
  const header = packActions(document.querySelector('.page-header') ? controls(document.querySelector('.page-header')) : []);
  const filterRoots = [...main.querySelectorAll('.admin-filter-bar, form[role=search], .component-filter-toolbar, .search-form, .output-week-form, .menu-toolbar, .kitchen-cal-jump')];
  const filterSet = new Set();
  for (const root of filterRoots) {
    if (root.classList.contains('week-filter')) continue;
    for (const el of root.querySelectorAll('a, button, summary')) {
      if (visible(el) && !el.closest(chrome)) filterSet.add(el);
    }
  }
  const filterEntries = [...filterSet].filter(el =>
    el.dataset.semantic === 'view.filter' || iconNames(el).includes('tabler-filter') ||
    /^(Filtern|Weitere Filter|Filter|More filters)$/i.test(visibleText(el)));
  const filtersWithText = filterEntries.filter(el => visibleText(el)).length;
  const emptyOverflow = [...main.querySelectorAll('details, .dropdown')].filter(menu => {
    const trigger = menu.querySelector(':scope > summary, :scope > [data-bs-toggle="dropdown"]');
    if (!trigger || !visible(trigger) || !iconNames(trigger).includes('tabler-dots')) return false;
    return ![...menu.querySelectorAll('a[href], button, input[type=submit]')].some(el =>
      !trigger.contains(el) && !el.hidden && !el.closest('[hidden], [inert]'));
  }).length;
  const doubleMarkers = [...main.querySelectorAll('summary')].filter(summary => {
    if (!visible(summary)) return false;
    const chevrons = iconNames(summary).filter(name => /^tabler-chevron-(right|down)$/.test(name));
    const style = getComputedStyle(summary);
    const native = style.display === 'list-item' && style.listStyleType !== 'none' &&
      !['none', '""'].includes(getComputedStyle(summary, '::marker').content);
    return chevrons.length > 1 || (chevrons.length === 1 && native);
  }).length;
  const emptyInfo = [...main.querySelectorAll('svg')].filter(svg => {
    if (!visible(svg) || !iconNames(svg).includes('tabler-info-circle')) return false;
    const hint = svg.closest('.admin-hint');
    if (hint) return ![...hint.children].filter(el => el.tagName !== 'SUMMARY')
      .some(el => el.textContent.trim() || el.querySelector('a[href], button, input, img'));
    if (svg.closest('a[href], button, summary, [data-ui-tooltip], [title]')) return false;
    const content = svg.closest('.empty, .alert') || svg.parentElement;
    return !content.textContent.trim();
  }).length;
  // Compare the same visible action in both viewports, not responsive copies or navigation.
  const actionTexts = {};
  [...main.querySelectorAll('a, button, summary')].forEach((el, index) => {
    if (!isControl(el) || el.closest('.ui-sem-action-items, dialog, .dropdown-menu, .admin-filter-chips')) return;
    const key = [index, el.tagName, el.id, el.getAttribute('href'), el.getAttribute('name'), el.getAttribute('value')].join('|');
    actionTexts[key] = visibleText(el);
  });
  const kindCount = {};
  const lists = groups.map((group) => {
    kindCount[group.kind] = (kindCount[group.kind] || 0) + 1;
    const sample = group.rows;
    const rowPacks = sample.map((row) => packActions(controls(row)));
    const worst = rowPacks.reduce((best, pack) => (pack.count > best.count ? pack : best), {count: 0, withText: 0, texts: [], icons: [], family: 'keins', hits: [], filled: 0});
    const texts = [...new Set(rowPacks.flatMap((pack) => pack.texts))];
    const icons = [...new Set(rowPacks.flatMap((pack) => pack.icons))];
    const first = sample[0];
    const shell = shellOf(group.root, group.kind);
    const table = group.root.tagName === 'TABLE' ? group.root : group.root.querySelector('table');
    const th = table ? [...table.querySelectorAll(':scope > thead th')].find((cell) => visible(cell)) : null;
    let headerStyle = null;
    if (th) {
      const s = getComputedStyle(th);
      headerStyle = {fontSize: s.fontSize, fontWeight: String(s.fontWeight), textTransform: s.textTransform, color: s.color, background: s.backgroundColor, height: Math.round(th.parentElement.getBoundingClientRect().height)};
    }
    const primary = textInfo(first.querySelector('.admin-list-primary, .admin-list-name strong, h2, h3, h4, h5, th[scope=row], td a, th a, a'));
    const secondary = textInfo(first.querySelector('.admin-list-secondary, .admin-list-subtitle, .print-tpl-meta, .text-secondary'));
    const statusEl = first.querySelector('.admin-label, .badge, [data-status]');
    const rowStyle = getComputedStyle(first);
    return {
      key: group.kind + '-' + kindCount[group.kind],
      label: labelOf(group.root),
      kind: group.kind,
      total: group.total,
      container: paint(shell),
      header: headerStyle,
      row: {height: Math.round(first.getBoundingClientRect().height), divider: rowStyle.borderBottomWidth + ' ' + rowStyle.borderBottomStyle + ' ' + rowStyle.borderBottomColor, background: rowStyle.backgroundColor, radius: rowStyle.borderRadius, shadow: rowStyle.boxShadow === 'none' ? 'none' : 'vorhanden', card: sample.some(isCard)},
      primary, secondary,
      status: statusEl ? [...statusEl.classList].sort().join('.') : 'keine',
      rowActions: {count: worst.count, withText: Math.max(0, ...rowPacks.map((pack) => pack.withText), 0), texts, icons, family: icons.length ? (icons.every((name) => name.startsWith('tabler')) ? 'tabler' : 'gemischt') : 'keins', hits: worst.hits},
    };
  });
  return {header, filters: filterEntries.length, filtersWithText, emptyOverflow, doubleMarkers, emptyInfo, actionTexts, lists};
}"""


def test_filter_and_empty_overflow_measurement():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox'])
        try:
            page = browser.new_page()
            page.set_content('''<main>
                <form role="search"><details><summary data-semantic="view.filter">
                <svg><use href="#tabler-filter"></use></svg><span class="admin-filter-count">2</span>
                </summary><input name="status"></details></form>
                <form role="search"><button data-semantic="view.filter">Filtern</button></form>
                <details><summary><svg><use href="#tabler-dots"></use></svg></summary></details>
                <details><summary><svg><use href="#tabler-dots"></use></svg></summary><a href="/edit">Bearbeiten</a></details>
                </main>''')
            measured = page.evaluate(MEASURE_JS)
            assert measured['filters'] == 2
            assert measured['filtersWithText'] == 1
            assert measured['emptyOverflow'] == 1
        finally:
            browser.close()


def test_c3_measurements_distinguish_empty_help_native_markers_and_responsive_text():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox'])
        try:
            page = browser.new_page(viewport={'width': 1440, 'height': 900})
            page.set_content('''<style>svg {width:20px;height:20px}
                .single {list-style:none}
                @media(max-width:500px){.responsive span{display:none}}</style><main>
                <details><summary><svg><use href="#tabler-chevron-right"></use></svg>Double</summary>Text</details>
                <details><summary class="single"><svg><use href="#tabler-chevron-right"></use></svg>Single</summary>Text</details>
                <details><summary>Native only</summary>Text</details>
                <details class="admin-hint"><summary><svg><use href="#tabler-info-circle"></use></svg></summary><p>Useful help</p></details>
                <details class="admin-hint"><summary><svg><use href="#tabler-info-circle"></use></svg></summary><p> </p></details>
                <div><svg><use href="#tabler-info-circle"></use></svg></div>
                <p><svg><use href="#tabler-info-circle"></use></svg>Useful information</p>
                <div class="empty"><div class="empty-icon"><svg><use href="#tabler-info-circle"></use></svg></div><p>No records</p></div>
                <button class="btn responsive" aria-label="Save"><svg></svg><span>Save</span></button>
                <button class="btn" aria-label="Edit"><svg></svg></button>
                </main>''')
            desktop = _flatten('probe', 'Probe', '/', 1440, 900, _measure(page))
            page.set_viewport_size({'width': 390, 'height': 844})
            mobile = _flatten('probe', 'Probe', '/', 390, 844, _measure(page))
            assert desktop[0]['double_markers'] == mobile[0]['double_markers'] == 1
            assert desktop[0]['empty_info'] == mobile[0]['empty_info'] == 2
            codes = _deviations(desktop, mobile, _modes(desktop))
            assert 'buttontext_viewport_unterschied' in codes
            assert '1440:aufklappmarker_doppelt' in codes
            assert '390:info_leer' in codes
            page.locator('.responsive span').evaluate('el => el.remove()')
            fixed = _flatten('probe', 'Probe', '/', 390, 844, _measure(page))
            assert 'buttontext_viewport_unterschied' not in _deviations(fixed, fixed, _modes(fixed))
        finally:
            browser.close()


def _catalog(paths: dict) -> list[tuple[str, str, str, str | None]]:
    static = [
        ('wochenuebersicht-cafeteria', 'Wochenübersicht Cafeteria', '/admin/cafeteria/wochen', None),
        ('wochenuebersicht-patienten', 'Wochenübersicht Patienten', '/admin/patienten/wochen', None),
        ('wochenplan-cafeteria', 'Wochenplan Cafeteria', f'/admin/cafeteria?week={WEEK}', None),
        ('wochenplan-patienten', 'Wochenplan Patienten', f'/admin/patienten?week={WEEK}', None),
        ('wochenpruefung-cafeteria', 'Wochenprüfung Cafeteria', f'/admin/cafeteria/wochen/pruefung?week={WEEK}', None),
        ('wochenpruefung-patienten', 'Wochenprüfung Patienten', f'/admin/patienten/wochen/pruefung?week={WEEK}', None),
        ('menues-cafeteria', 'Menüs Cafeteria', '/admin/cafeteria/menues', None),
        ('menues-patienten', 'Menüs Patienten', '/admin/patienten/menues', None),
        ('bausteine-cafeteria', 'Bausteine Cafeteria', '/admin/cafeteria/komponenten', None),
        ('bausteine-patienten', 'Bausteine Patienten', '/admin/patienten/komponenten', None),
        ('kuechenkalender', 'Küchenkalender', '/admin/kuechenkalender?year=2026&month=9', None),
        ('zutaten', 'Zutaten', '/admin/grundlagen?kind=foods', None),
        ('einheiten', 'Einheiten', '/admin/grundlagen?kind=units', None),
        ('kategorien', 'Kategorien', '/admin/grundlagen?kind=categories', None),
        ('kennzeichnungen', 'Kennzeichnungen', '/admin/grundlagen?kind=tags', None),
        ('lagerorte', 'Lagerorte', '/admin/grundlagen?kind=storage_locations', None),
        ('rezepte', 'Rezepte', '/admin/rezepte', None),
        ('gerichtvorlagen', 'Gerichtvorlagen', '/admin/gerichtvorlagen', None),
        ('lager', 'Lager', '/admin/lager', None),
        ('kochbuecher', 'Kochbücher', '/admin/kochbuecher', None),
        ('einkaufslisten', 'Einkaufslisten', '/admin/einkaufslisten', None),
        ('bestellungen', 'Bestellungen', '/admin/bestellung', None),
        ('kalkulation', 'Kalkulation', '/admin/kalkulation', 'cost'),
        ('vorlagen', 'Druckvorlagen und Vorlagenkatalog', f'/admin/vorlagen?week={WEEK}', 'catalog'),
        ('bildschirme', 'Bildschirme', '/admin/screens', None),
        ('bildschirmvorlagen-cafeteria', 'Bildschirmvorlagen Cafeteria', '/admin/screens/cafeteria/wochenvorlage', None),
        ('bildschirmvorlagen-patienten', 'Bildschirmvorlagen Patienten', '/admin/screens/patienten/wochenvorlage', None),
        ('benutzer', 'Benutzer', '/admin/benutzer', None),
        ('benutzerprotokoll', 'Kontoereignisse', '/admin/benutzer/protokoll', None),
        ('api-schluessel', 'API-Schlüssel', '/admin/api', None),
        ('zugriffsverlauf', 'Zugriffsverlauf', '/admin/benutzer/zugriffsverlauf', None),
        ('importe', 'Rezeptimporte', '/admin/rezepte/import', None),
        ('datenimport', 'Datenimport', '/admin/import-preview', None),
        ('bereiche-zeiten', 'Bereiche und Zeiten', '/admin/bereiche-zeiten', None),
    ]
    dynamic = [
        ('rezept-revisionen', 'Rezeptverlauf', paths['admin.recipe_revisions'], None),
        ('rezept-skalierung', 'Rezeptskalierung', paths['admin.recipe_scale'], None),
        ('rezept-bilder', 'Rezeptbilder', paths['admin.recipe_images'], None),
        ('kochbuch', 'Kochbuch', paths['admin.cookbook_edit'], None),
        ('einkaufsliste', 'Einkaufsliste', paths['admin.shopping_list_detail'], None),
        ('bestellkorb', 'Bestellkorb', paths['admin.order_basket'], None),
        ('import-detail', 'Importstapel', paths['admin.recipe_import_detail'], None),
    ]
    return static + dynamic


def _hook(page, hook: str | None, revision: str) -> None:
    if hook == 'catalog':
        page.evaluate("""() => {
          for (const details of document.querySelectorAll('details')) {
            if (details.querySelector('.print-tpl-row')) details.open = true;
          }
          for (const pane of document.querySelectorAll('.output-area-panels .tab-pane')) {
            pane.classList.add('active', 'show');
            pane.style.display = 'block';
          }
        }""")
    elif hook == 'cost':
        page.locator('#revision_public_id').fill(revision)
        page.locator('#as_of').fill('2026-09-25')
        page.locator('button[form="cost-preview"]').click()
        page.wait_for_load_state('domcontentloaded')


def _sig_header(style: dict | None) -> str | None:
    if not style:
        return None
    return '|'.join(str(style[key]) for key in ('fontSize', 'fontWeight', 'textTransform', 'color', 'background', 'height'))


def _sig_text(style: dict | None) -> str | None:
    if not style:
        return None
    return '|'.join(str(style[key]) for key in ('fontSize', 'fontWeight', 'color', 'link', 'linkColor'))


def _fmt_header(style: dict | None) -> str:
    if not style:
        return 'keine Kopfzeile'
    return (f"{style['fontSize']} / {style['fontWeight']} / {style['textTransform']} / {style['color']}"
            f" / Grund {style['background']} / Höhe {style['height']}px")


def _fmt_text(style: dict | None) -> str:
    if not style:
        return 'keine'
    link = f"Link {style['linkColor']}" if style['link'] else 'kein Link'
    return f"{style['fontSize']} / {style['fontWeight']} / {style['color']} / {link}"


def _fmt_actions(pack: dict) -> str:
    texts = ', '.join(pack['texts']) if pack['texts'] else '—'
    icons = ', '.join(pack['icons']) if pack['icons'] else pack['family']
    hits = ', '.join(pack['hits']) if pack['hits'] else '—'
    return (f"{pack['count']} sichtbar, {pack['withText']} mit Text ({texts}); "
            f"Icons {pack['family']}: {icons}; Treffer {hits}")


def _measure(page) -> dict:
    data = page.evaluate(MEASURE_JS)
    if data['lists']:
        return data
    return {**data, 'lists': [{
        'key': 'keine-1', 'label': 'keine Datenliste', 'kind': 'keine', 'total': 0,
        'container': None, 'header': None, 'row': None, 'primary': None, 'secondary': None,
        'status': 'keine', 'rowActions': {'count': 0, 'withText': 0, 'texts': [], 'icons': [], 'family': 'keins', 'hits': []},
    }]}


def _flatten(slug: str, title: str, path: str, width: int, height: int, data: dict) -> list[dict]:
    rows = []
    header_pack = data['header']
    for index, item in enumerate(data['lists']):
        metrics = []
        if index == 0:
            metrics.append(('Kopfaktionen', _fmt_actions(header_pack) + f"; gefüllte Primärflächen {header_pack['filled']}"))
            metrics.append(('Filtereinstiege', str(data['filters'])))
            metrics.append(('Filtereinstiege mit sichtbarem Text', str(data['filtersWithText'])))
            metrics.append(('Überlaufmenü ohne Einträge', str(data['emptyOverflow'])))
            metrics.append(('Doppelte Aufklappmarker', str(data['doubleMarkers'])))
            metrics.append(('Leere Info-Symbole', str(data['emptyInfo'])))
        container = item['container']
        if container:
            metrics.append(('Listencontainer', f"{container['tag']} · Rahmen {container['border']} · Radius {container['radius']} · Schatten {container['shadow']}"))
        else:
            metrics.append(('Listencontainer', 'keine Liste'))
        metrics.append(('Kopfzeile', _fmt_header(item['header'])))
        row = item['row']
        if row:
            metrics.append(('Zeile', f"Höhe {row['height']}px · Trenner {row['divider']} · Grund {row['background']} · Radius {row['radius']} · Schatten {row['shadow']} · Karte {'ja' if row['card'] else 'nein'}"))
        else:
            metrics.append(('Zeile', 'keine Datenzeile'))
        metrics.append(('Haupttext', _fmt_text(item['primary'])))
        metrics.append(('Sekundärtext', _fmt_text(item['secondary'])))
        metrics.append(('Status', item['status']))
        metrics.append(('Zeilenaktionen', _fmt_actions(item['rowActions'])))
        rows.append({
            'slug': slug, 'title': title, 'path': path, 'width': width, 'height': height,
            'list_key': item['key'], 'label': item['label'], 'metrics': metrics,
            'header_sig': _sig_header(item['header']), 'primary_sig': _sig_text(item['primary']),
            'secondary_sig': _sig_text(item['secondary']),
            'card': bool(row and row['card']),
            'row_count': item['rowActions']['count'], 'row_text': bool(item['rowActions']['withText']),
            'header_text': bool(header_pack['withText']), 'header_filled': header_pack['filled'],
            'filter_text': data['filtersWithText'], 'empty_overflow': data['emptyOverflow'],
            'double_markers': data['doubleMarkers'], 'empty_info': data['emptyInfo'],
            'action_texts': data['actionTexts'],
        })
    return rows


def _modes(rows: list[dict]) -> dict[str, str | None]:
    def mode(values: list[str]) -> str | None:
        return Counter(values).most_common(1)[0][0] if values else None
    return {
        'kopf': mode([row['header_sig'] for row in rows if row['header_sig']]),
        'haupt': mode([row['primary_sig'] for row in rows if row['primary_sig']]),
        'sek': mode([row['secondary_sig'] for row in rows if row['secondary_sig']]),
    }


def _deviations(desktop: list[dict], mobile: list[dict], modes: dict[str, str | None]) -> list[str]:
    codes: set[str] = set()
    for width, rows in ((1440, desktop), (390, mobile)):
        for row in rows:
            if row['filter_text']:
                codes.add(f'{width}:filtereinstieg_text')
            if row['empty_overflow']:
                codes.add(f'{width}:ueberlauf_leer')
            if row['double_markers']:
                codes.add(f'{width}:aufklappmarker_doppelt')
            if row['empty_info']:
                codes.add(f'{width}:info_leer')
    if desktop and mobile:
        wide, narrow = desktop[0]['action_texts'], mobile[0]['action_texts']
        if any(wide[key] != narrow[key] for key in wide.keys() & narrow.keys()):
            codes.add('buttontext_viewport_unterschied')
    for row in desktop:
        key = row['list_key']
        if row['row_text']:
            codes.add(f"1440:zeilenaktion_text:{key}")
        if row['row_count'] > 2:
            codes.add(f"1440:zeilenaktionen_gt2:{key}")
        if row['card']:
            codes.add(f"karte_je_zeile:{key}")
        if row['header_sig'] and row['header_sig'] != modes['kopf']:
            codes.add(f"kopf_typografie:{key}")
        if row['primary_sig'] and row['primary_sig'] != modes['haupt']:
            codes.add(f"haupt_typografie:{key}")
        if row['secondary_sig'] and row['secondary_sig'] != modes['sek']:
            codes.add(f"sekundaer_typografie:{key}")
        if row['header_text']:
            codes.add('1440:kopfaktion_text')
    for row in mobile:
        key = row['list_key']
        if row['row_text']:
            codes.add(f"390:zeilenaktion_text:{key}")
        if row['row_count'] > 2:
            codes.add(f"390:zeilenaktionen_gt2:{key}")
        if row['header_text']:
            codes.add('390:kopfaktion_text')
    return sorted(codes)


def _markdown(desktop: list[dict], mobile_by_slug: dict[str, list[dict]]) -> str:
    metric_values: dict[str, list[str]] = {}
    lines_raw: list[tuple[str, str, str, str]] = []

    def add(page: str, viewport: str, name: str, value: str) -> None:
        metric_values.setdefault(name, []).append(value)
        lines_raw.append((page, viewport, name, value))

    seen_mobile_header: set[str] = set()
    paired = {(row['slug'], row['list_key']) for row in desktop}
    for row in desktop:
        page = f"{row['title']} · {row['label']}"
        for name, value in row['metrics']:
            add(page, '1440×900', name, value)
        mobile_rows = mobile_by_slug.get(row['slug'], [])
        match = next((item for item in mobile_rows if item['list_key'] == row['list_key']), None)
        if match and dict(match['metrics']).get('Zeilenaktionen'):
            add(page, '390×844', 'Zeilenaktionen schmal', dict(match['metrics'])['Zeilenaktionen'])
        if row['slug'] not in seen_mobile_header and mobile_rows:
            seen_mobile_header.add(row['slug'])
            header = dict(mobile_rows[0]['metrics']).get('Kopfaktionen')
            if header:
                add(f"{row['title']} · {mobile_rows[0]['label']}", '390×844', 'Kopfaktionen schmal', header)
    for slug, mobile_rows in mobile_by_slug.items():
        for item in mobile_rows:
            if (slug, item['list_key']) in paired:
                continue
            page = f"{item['title']} · {item['label']}"
            for name in ('Zeilenaktionen', 'Kopfaktionen'):
                value = dict(item['metrics']).get(name)
                if value:
                    add(page, '390×844', name + ' schmal', value)
    modes = {name: Counter(values).most_common(1)[0][0] for name, values in metric_values.items() if values}

    def cell(name: str, value: str) -> str:
        text = value.replace('|', '/').replace('\n', ' ')
        return f'**{text}**' if modes.get(name) not in (None, value) else text

    body = ['| Seite | Viewport | Messgrösse | Wert |', '|---|---|---|---|']
    body.extend(f'| {page} | {viewport} | {name} | {cell(name, value)} |' for page, viewport, name, value in lines_raw)
    button_pages = sorted({row['title'] for row in desktop if row['row_text'] or row['header_text']})
    card_pages = sorted({row['title'] for row in desktop if row['card']})
    many = sorted({row['title'] for row in desktop if row['row_count'] > 2})
    type_pages = sorted({row['title'] for row in desktop if (
        (row['header_sig'] and row['header_sig'] != _modes(desktop)['kopf'])
        or (row['primary_sig'] and row['primary_sig'] != _modes(desktop)['haupt'])
        or (row['secondary_sig'] and row['secondary_sig'] != _modes(desktop)['sek'])
    )})
    def listing(pages: list[str]) -> str:
        return ', '.join(pages) if pages else 'keine'
    summary = [
        '# Listenfamilie — Vergleich der administrativen Listen',
        '',
        'Gemessen am 2026-09-26 gegen `docs/design/2026-09-26-icon-first-simplification-spec.md` (§3.2 Aktionsbudget, §4 gemeinsames Listenmuster, §5 Symbolbuttons; Abnahme UI-02, UI-03, UI-04, UI-05, UI-24).',
        'Fett markiert ist jeder Wert, der von der häufigsten Ausprägung dieser Messgrösse abweicht.',
        'Geschlossene Überlaufmenüs und Bestätigungsdialoge (§5.4) sind nicht geöffnet und zählen nicht als sichtbarer Text.',
        '',
        f'Seiten: {len({row["slug"] for row in desktop})}. Listenblöcke bei 1440×900: {len(desktop)}.',
        '',
        '## Zusammenfassung',
        '',
        f'- Seiten mit Buttontext in Zeile oder Kopf: {listing(button_pages)}',
        f'- Seiten mit Karte je Zeile: {listing(card_pages)}',
        f'- Seiten mit mehr als zwei Zeilenaktionen: {listing(many)}',
        f'- Seiten mit abweichender Kopf-, Haupt- oder Sekundärtypografie: {listing(type_pages)}',
        '',
        '## Messwerte',
        '',
        *body,
        '',
    ]
    return '\n'.join(summary)


def _contact_sheet(page, images: list[tuple[str, Path]]) -> None:
    html_path = EVIDENCE / '_contact-sheet.html'
    figures = []
    for title, path in images:
        figures.append(f'<figure><img src="{path.name}" alt=""><figcaption>{title}</figcaption></figure>')
    html_path.write_text(
        '<!DOCTYPE html><meta charset="utf-8"><style>'
        'body{margin:0;background:#f4f1ea;font:12px/1.3 sans-serif;color:#222}'
        '.grid{display:grid;grid-template-columns:repeat(4,1fr);gap:8px;padding:8px}'
        'img{width:100%;height:auto;background:#fff;border:1px solid #ccc}'
        'figcaption{padding:4px 0 8px}</style>'
        f'<div class="grid">{"".join(figures)}</div>',
        encoding='utf-8')
    page.goto(html_path.as_uri(), wait_until='load')
    page.screenshot(path=str(EVIDENCE / 'contact-sheet.png'), full_page=True)
    html_path.unlink()


def _shots(report: bool, page, slug: str, width: int, height: int, images: list[tuple[str, Path]], title: str) -> None:
    if not report:
        return
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    target = EVIDENCE / f'{slug}-{width}x{height}.png'
    page.screenshot(path=str(target))
    if width == 1440:
        images.append((title, target))


def _mount_public_targets(application) -> None:
    """Bildschirme und Vorlagen bauen öffentliche und Player-URLs. Die Test-App hat dafür nur einen Signage-Stub."""
    application.register_blueprint(public_bp)
    application.add_url_rule('/signage/cafeteria/tag', endpoint='signage.cafeteria_day', view_func=lambda: '')
    application.add_url_rule('/signage/patienten/tag', endpoint='signage.patient_day', view_func=lambda: '')


def test_list_family_across_admin_pages(admin_app, admin_engine, live_server):  # noqa: F811
    _mount_public_targets(admin_app)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    entities = _prepare_inventory_entities(admin_app, admin_engine, actor)
    create_api_key(admin_engine, actor_id=actor, label='Listenfamilie', scopes=('preview.read',),
                   channels=('cafeteria',), expires_at=datetime.now(UTC) + timedelta(days=10))
    revision = entities['endpoint_paths']['admin.recipe_revision'].rsplit('/', 1)[-1]
    pages = _catalog(entities['endpoint_paths'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    report = os.environ.get('UI_LIST_FAMILY_REPORT') == '1'
    desktop: list[dict] = []
    mobile: dict[str, list[dict]] = {}
    failures = []
    images: list[tuple[str, Path]] = []
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            for width, height in ((1440, 900), (390, 844)):
                with browser.new_context(base_url=live_server, viewport={'width': width, 'height': height},
                                          device_scale_factor=1) as context:
                    context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                    page = context.new_page()
                    for slug, title, path, hook in pages:
                        response = page.goto(path, wait_until='domcontentloaded', timeout=30000)
                        status = response.status if response else 0
                        if status != 200:
                            failures.append(f'{slug} {path} → {status}')
                            continue
                        _hook(page, hook, revision)
                        _shots(report, page, slug, width, height, images, title)
                        measured = _flatten(slug, title, path, width, height, _measure(page))
                        if width == 1440:
                            desktop.extend(measured)
                        else:
                            mobile[slug] = measured
            if report and images:
                sheet = browser.new_context(viewport={'width': 1440, 'height': 900})
                sheet_page = sheet.new_page()
                _contact_sheet(sheet_page, images)
                sheet.close()
        finally:
            browser.close()
    assert not failures, 'Seite nicht messbar:\n' + '\n'.join(failures)
    assert {row['slug'] for row in desktop} == {slug for slug, *_ in pages}
    modes = _modes(desktop)
    current = {}
    for slug, title, path, _hook_name in pages:
        rows = [row for row in desktop if row['slug'] == slug]
        current[slug] = _deviations(rows, mobile.get(slug, []), modes)
    if report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        REPORT_PATH.write_text(_markdown(desktop, mobile), encoding='utf-8')
        BASELINE_PATH.write_text(json.dumps({'pages': current}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'LIST_FAMILY_REPORT={REPORT_PATH}')
        print(f'LIST_FAMILY_BASELINE={BASELINE_PATH}')
        print(f'LIST_FAMILY_CONTACT={EVIDENCE / "contact-sheet.png"}')
    assert BASELINE_PATH.is_file(), 'Baseline fehlt. Einmal mit UI_LIST_FAMILY_REPORT=1 erzeugen.'
    baseline = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))['pages']
    new_pages = sorted(set(current) - set(baseline))
    new_codes = [f'{slug}: {code}' for slug, codes in current.items() for code in codes if code not in baseline.get(slug, [])]
    satisfied = [f'{slug}: {code}' for slug, codes in baseline.items() if slug in current for code in codes if code not in current[slug]]
    if satisfied:
        print('LIST_FAMILY_SATISFIED=' + '; '.join(satisfied))
    assert not new_pages, 'Neue Listen ohne Baseline: ' + ', '.join(new_pages)
    assert not new_codes, 'Neue Abweichungen:\n' + '\n'.join(new_codes)
