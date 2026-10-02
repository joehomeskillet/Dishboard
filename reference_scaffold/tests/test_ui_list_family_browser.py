"""Listenfamilie: jede Admin-Liste vermessen, vergleichen und per Baseline absichern.

Zielwerte aus UI-DIRECT-ACTIONS-2026-09-29 (§3, §4, §10): alle verfügbaren
Zeilenaktionen direkt, benannt und icon-only; keine Karte je Zeile,
gleiche Kopf-/Haupt-/Sekundärtypografie.
UI_LIST_FAMILY_REPORT=1 schreibt Vergleich und Screenshots; die Baseline darf
dabei nur sinken. Neue Abweichungen werden auch im Berichtsmodus abgewiesen.
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

# Offen, WP3/WP4: handgeschriebene Aktionsmenüs, nicht vom Renderer umgestellt.
# rezepte.html, kochbuecher.html, api.html, rezepte_import.html (WP3);
# _week_menu_card.html, _week_controls.html, print_template_editor.html (WP4).
# Weitere WP4-Editoren ausserhalb dieses Katalogs: rezepte_ansicht.html,
# menu_editor.html, component_editor.html, rezepte_editor.html, _rezepte_fields.html.
PENDING_DIRECT_ACTION_PAGES = {
    'rezepte', 'kochbuecher', 'api-schluessel', 'importe',
    'wochenplan-cafeteria', 'wochenplan-patienten',
}

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
      if (!parent || clipped(parent) || !visible(parent)) continue;
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
  // Icon-first §5.4 / UC-G0e: these hub links name another destination.
  // Keep their geometry/text measurements; only object-action text is a deviation.
  const namedDestination = (el) => {
    if (!['/admin/vorlagen', '/admin/screens'].includes(location.pathname)) return false;
    if (!el.matches('a[href]')) return false;
    const url = new URL(el.href, location.href);
    if (url.origin !== location.origin) return false;
    const text = visibleText(el), semantic = el.dataset.semantic, path = url.pathname;
    const assignment = /^\/admin\/screens\/(cafeteria|patienten)\/wochenvorlage$/.test(path);
    if (location.pathname === '/admin/vorlagen') {
      return (assignment && semantic === 'actions.edit' && text === 'Zuordnen') ||
        (path === '/admin/cafeteria/preview/print' && semantic === 'actions.print' && text === 'PDF Mitarbeitende');
    }
    if (location.pathname !== '/admin/screens') return false;
    if (assignment) return semantic === 'actions.edit' && text === 'Zuweisen';
    if (semantic !== 'actions.open') return false;
    if (/^\/(cafeteria|patienten)\/heute\/$/.test(path) || /^\/signage\/(cafeteria|patienten)\/tag$/.test(path)) return text === 'Tagesplan';
    if (/^\/(cafeteria\/wochenangebot|patienten\/wochenplan)\/ohne-bilder\/$/.test(path)) return text === 'Ohne Bilder';
    if (/^\/signage\/(cafeteria|patienten)\/woche$/.test(path)) return text === 'Wochenplan';
    // admin_app binds the two signage week endpoints to these fixture URLs.
    if (/^\/preview\/(cafeteria|patient)$/.test(path)) return text === 'Wochenplan';
    return /^\/(cafeteria\/wochenangebot|patienten\/wochenplan)\/$/.test(path) && ['Öffnen', 'Wochenplan'].includes(text);
  };
  const packActions = (acts) => {
    // UI-DELTA §0.1/B-03 supersedes mandatory icon-only actions: explicit
    // text mode is valid, while a mixed renderer remains a deviation.
    const pureText = (el) => el.matches('.ui-sem-control--text') && !el.querySelector('svg, img') &&
      [el, ...el.querySelectorAll('*')].filter(visible).every(node =>
        ['::before', '::after'].every(pseudo => {
          const s = getComputedStyle(node, pseudo);
          return s.display === 'none' || s.visibility !== 'visible' || Number(s.opacity) === 0 ||
            ['none', 'normal'].includes(s.content);
        }));
    const texts = acts.filter(el => !pureText(el)).map(visibleText).filter(Boolean);
    const icons = [...new Set(acts.flatMap(iconNames))];
    return {
      count: acts.length,
      withText: texts.length,
      objectWithText: acts.filter(el => visibleText(el) && !namedDestination(el) && !pureText(el)).length,
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
    groups.push({root, rows: fresh, total: fresh.length, kind});
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
  cluster('li.kitchen-cal-list-day:not(.kitchen-cal-list-day-empty)', 'zeilen', parentOf);
  for (const table of main.querySelectorAll('table')) {
    if (!visible(table) || table.closest('nav, .navbar, article.menu-slot, article.recipe-card, article.screen-card')) continue;
    let rows = [...table.querySelectorAll(':scope > tbody > tr')].filter((tr) => tr.querySelector('td, th[scope=row]'));
    const screenGroups = table.matches('.screens-overview > table') ? [...table.querySelectorAll(':scope > tbody.screen-card')] : [];
    if (screenGroups.length) rows = screenGroups;
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
    return ![...menu.querySelectorAll('a[href], button, input[type=submit], summary')].some(el =>
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
    const sample = group.rows.slice(0, 3);
    const rowPacks = group.rows.map((row) => packActions(controls(row)));
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
    const rowBody = first.matches('.admin-list-row') ? first : (first.querySelector('.admin-list-row') || first);
    const rowStyle = getComputedStyle(rowBody);
    const dividerStyle = first.matches('tbody.screen-card') ? getComputedStyle(first.querySelector(':scope > tr:last-child')) : rowStyle;
    const checkRowBudget = (row) => {
      const overflows = [...row.querySelectorAll('details.ui-sem-actions, .ui-sem-actions')].filter(visible);
      const otherOverflows = [...row.querySelectorAll('details')].filter((d) =>
        visible(d) && !overflows.includes(d) &&
        [...d.querySelectorAll(':scope > summary use')].some((u) => (u.getAttribute('href') || u.getAttribute('xlink:href') || '').includes('tabler-dots'))
      );
      const allOverflows = [...overflows, ...otherOverflows];
      const emptyOverflows = allOverflows.filter((menu) => {
        const trigger = menu.querySelector(':scope > summary');
        const items = [...menu.querySelectorAll('a[href], button, input[type=submit], summary')].filter((el) =>
          (!trigger || !trigger.contains(el)) && !el.hidden && !el.closest('[hidden], [inert]')
        );
        return items.length === 0;
      });
      const rowControls = controls(row);
      const directActions = rowControls.filter((ctrl) => {
        if (allOverflows.some((o) => o.contains(ctrl))) return false;
        if (ctrl.matches('summary') && ctrl.parentElement?.matches('details.ui-sem-actions, .ui-sem-actions')) return false;
        return true;
      });
      const visibleLinks = [...row.querySelectorAll('a[href]')].filter((a) =>
        visible(a) && !allOverflows.some((o) => !o.open && o.contains(a))
      );
      const normHref = (el) => {
        const raw = el.getAttribute('href') || '';
        if (!raw || raw.startsWith('#') || raw.startsWith('javascript:')) return null;
        try {
          const u = new URL(raw, window.location.href);
          let p = u.pathname;
          if (p.length > 1 && p.endsWith('/')) p = p.slice(0, -1);
          return p + u.search + u.hash;
        } catch {
          return raw;
        }
      };
      const hrefMap = new Map();
      const duplicateTargets = [];
      for (const a of visibleLinks) {
        const target = normHref(a);
        if (!target) continue;
        if (hrefMap.has(target)) {
          duplicateTargets.push({href: target, firstText: visibleText(hrefMap.get(target)) || hrefMap.get(target).getAttribute('aria-label') || '', secondText: visibleText(a) || a.getAttribute('aria-label') || ''});
        } else {
          hrefMap.set(target, a);
        }
      }
      const actionsToCheck = [];
      directActions.forEach((a) => actionsToCheck.push({el: a, role: 'direct'}));
      allOverflows.forEach((o) => {
        const sum = o.querySelector(':scope > summary');
        if (sum) actionsToCheck.push({el: sum, role: 'overflow-summary'});
        const items = [...o.querySelectorAll('a[href], button, input[type=submit]')].filter((el) =>
          (!sum || !sum.contains(el)) && !el.hidden && !el.closest('[hidden], [inert]')
        );
        items.forEach((it) => actionsToCheck.push({el: it, role: 'overflow-item'}));
      });
      const genericPattern = /^(bearbeiten|löschen|drucken|kopieren|archivieren|öffnen|anlegen|hinzufügen|aktivieren|übernehmen|verlauf|schliessen|abbrechen|wiederherstellen|verschieben|weitere aktionen|zurück|weiter|aktualisieren|vorschau|herunterladen|hochladen|importieren|exportieren|prüfen|veröffentlichen|speichern|bestätigen|details|optionen|aktionen|mehr|neu|auswählen|entfernen|filter|filtern|weitere optionen|rezeptverlauf|rezeptskalierung|rezeptbilder|planen|edit|delete|print|copy|archive|open|add|close|cancel|save|preview|download|upload|import|export|more|more actions|actions)$/i;
      const missingRecordContext = [];
      for (const {el, role} of actionsToCheck) {
        const aria = (el.getAttribute('aria-label') || '').trim();
        const tooltip = (el.getAttribute('data-ui-tooltip') || '').trim();
        const title = (el.getAttribute('title') || '').trim();
        const vis = visibleText(el) || (el.textContent || '').replace(/\s+/g, ' ').trim();
        const accessible = aria || tooltip || title || vis;
        if (!accessible) {
          missingRecordContext.push({role, label: '', reason: 'missing_label'});
        } else if (genericPattern.test(accessible)) {
          missingRecordContext.push({role, label: accessible, reason: 'generic_label'});
        }
      }
      const violations = [];
      const hiddenActions = [...row.querySelectorAll('.admin-row-actions a, .admin-row-actions button')]
        .filter(el => visible(el.closest('.admin-row-actions')) && !visible(el));
      if (hiddenActions.length) {
        violations.push({criterion: 'hidden_actions', message: `Verborgene Direktaktionen: ${hiddenActions.length}`});
      }
      if (allOverflows.length) {
        violations.push({criterion: 'overflow_actions', message: `Generischer Mehr-Auslöser: ${allOverflows.length}`});
      }
      if (emptyOverflows.length > 0) {
        violations.push({criterion: 'empty_overflow', message: 'Leeres Überlaufmenü gefunden'});
      }
      if (duplicateTargets.length > 0) {
        violations.push({criterion: 'duplicate_targets', message: `Identisches Linkziel mehrfach vorhanden: ${duplicateTargets.map((d) => d.href).join(', ')}`});
      }
      if (missingRecordContext.length > 0) {
        violations.push({criterion: 'missing_record_context', message: `Aktion ohne Datensatzbezug: ${missingRecordContext.map((m) => m.label || '<leer>').join(', ')}`});
      }
      return {
        directActions: directActions.length,
        overflowActions: allOverflows.length,
        emptyOverflow: emptyOverflows.length,
        duplicateTargets: duplicateTargets.length,
        missingRecordContext: missingRecordContext.length,
        violations,
      };
    };
    const rowBudgets = group.rows.map((row, index) => {
      const b = checkRowBudget(row);
      return {...b, index};
    });
    const groupViolations = rowBudgets.flatMap((b) => b.violations.map((v) => ({row: b.index, ...v})));
    return {
      key: group.kind + '-' + kindCount[group.kind],
      label: labelOf(group.root),
      kind: group.kind,
      total: group.total,
      container: paint(shell),
      header: headerStyle,
      row: {height: Math.round(first.getBoundingClientRect().height), divider: dividerStyle.borderBottomWidth + ' ' + dividerStyle.borderBottomStyle + ' ' + dividerStyle.borderBottomColor, background: rowStyle.backgroundColor, radius: rowStyle.borderRadius, shadow: rowStyle.boxShadow === 'none' ? 'none' : 'vorhanden', card: sample.some(isCard)},
      primary, secondary,
      status: statusEl ? [...statusEl.classList].sort().join('.') : 'keine',
      rowActions: {count: worst.count, withText: Math.max(0, ...rowPacks.map((pack) => pack.withText), 0), objectWithText: Math.max(0, ...rowPacks.map(pack => pack.objectWithText)), texts, icons, family: icons.length ? (icons.every((name) => name.startsWith('tabler')) ? 'tabler' : 'gemischt') : 'keins', hits: worst.hits},
      budget: {
        totalRows: group.rows.length,
        directActionsMax: Math.max(0, ...rowBudgets.map((b) => b.directActions)),
        overflowActionsMax: Math.max(0, ...rowBudgets.map((b) => b.overflowActions)),
        emptyOverflowTotal: rowBudgets.reduce((sum, b) => sum + b.emptyOverflow, 0),
        duplicateTargetsTotal: rowBudgets.reduce((sum, b) => sum + b.duplicateTargets, 0),
        missingRecordContextTotal: rowBudgets.reduce((sum, b) => sum + b.missingRecordContext, 0),
        violations: groupViolations,
      },
    };
  });
  const allViolations = lists.flatMap((l) => l.budget.violations.map((v) => ({listKey: l.key, listLabel: l.label, ...v})));
  return {header, filters: filterEntries.length, filtersWithText, emptyOverflow, doubleMarkers, emptyInfo, actionTexts, lists, budgetViolations: allViolations};
}"""


def test_filter_and_empty_overflow_measurement():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox'])
        try:
            page = browser.new_page()
            page.set_content('''<main>
                <form role="search"><a data-semantic="view.filter" href="#filters">
                <svg><use href="#tabler-filter"></use></svg></a><span class="admin-filter-count">2</span>
                <dialog id="filters"><input name="status"></dialog></form>
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


def test_named_hub_destinations_keep_metrics_without_exempting_object_actions():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox'])
        try:
            page = browser.new_page()
            page.route('http://list.test/**', lambda route: route.fulfill(body='<main></main>', content_type='text/html'))
            for source, target, key, label in (
                ('vorlagen', '/admin/screens/cafeteria/wochenvorlage', 'actions.edit', 'Zuordnen'),
                ('vorlagen', '/admin/cafeteria/preview/print?week=2026-08-31', 'actions.print', 'PDF Mitarbeitende'),
                ('screens', '/cafeteria/heute/', 'actions.open', 'Tagesplan'),
                ('screens', '/patienten/wochenplan/ohne-bilder/', 'actions.open', 'Ohne Bilder'),
                ('screens', '/signage/patienten/woche', 'actions.open', 'Wochenplan'),
                ('screens', '/preview/patient', 'actions.open', 'Wochenplan'),
                ('screens', '/admin/screens/patienten/wochenvorlage', 'actions.edit', 'Zuweisen'),
            ):
                page.goto(f'http://list.test/admin/{source}')
                page.set_content(f'<main><table><tbody><tr><td><a class="btn" data-semantic="{key}" '
                                 f'href="{target}">{label}</a></td></tr></tbody></table></main>')
                pack = page.evaluate(MEASURE_JS)['lists'][0]['rowActions']
                assert pack['count'] == pack['withText'] == 1
                assert pack['texts'] == [label] and pack['objectWithText'] == 0
                link = page.locator('a')
                for attribute, value in (('href', '/admin/object/1'), ('href', 'https://other.test' + target),
                                         ('data-semantic', 'actions.delete')):
                    link.evaluate('(el, change) => el.setAttribute(...change)', [attribute, value])
                    assert page.evaluate(MEASURE_JS)['lists'][0]['rowActions']['objectWithText'] == 1
                    link.evaluate('(el, original) => { el.href = original[0]; el.dataset.semantic = original[1]; }', [target, key])
                link.evaluate("el => el.textContent = 'Bearbeiten'")
                assert page.evaluate(MEASURE_JS)['lists'][0]['rowActions']['objectWithText'] == 1
                # UI-DELTA permits an explicit text mode, including object actions.
                link.evaluate("el => el.classList.add('ui-sem-control--text')")
                assert page.evaluate(MEASURE_JS)['lists'][0]['rowActions']['objectWithText'] == 0
                link.evaluate("el => el.insertAdjacentHTML('beforeend', '<svg></svg>')")
                assert page.evaluate(MEASURE_JS)['lists'][0]['rowActions']['objectWithText'] == 1
                link.locator('svg').evaluate('el => el.remove()')
                style = page.add_style_tag(content='.ui-sem-control--text::after { content: "→"; }')
                assert page.evaluate(MEASURE_JS)['lists'][0]['rowActions']['objectWithText'] == 1
                style.evaluate('el => el.remove()')
        finally:
            browser.close()


def test_action_budget_measurement_detects_all_five_criteria():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox'])
        try:
            page = browser.new_page()
            page.set_content('''<main>
                <table class="admin-table">
                  <tbody>
                    <tr class="admin-list-row">
                      <td class="admin-list-primary"><a href="/item/1">Suppe 1</a></td>
                      <td class="admin-row-actions">
                        <a class="btn ui-sem-control" data-semantic="actions.edit" aria-label="Suppe 1 bearbeiten" href="/item/1/edit"><svg><use href="#tabler-pencil"></use></svg></a>
                        <details class="ui-sem-actions">
                          <summary class="btn ui-sem-control" data-semantic="actions.more" aria-label="Weitere Aktionen für Suppe 1"><svg><use href="#tabler-dots"></use></svg></summary>
                          <div class="ui-sem-action-items">
                            <a class="btn ui-sem-control" data-semantic="actions.delete" aria-label="Suppe 1 löschen" href="/item/1/delete">Löschen</a>
                          </div>
                        </details>
                      </td>
                    </tr>
                    <tr class="admin-list-row">
                      <td class="admin-list-primary"><a href="/item/2">Suppe 2</a></td>
                      <td class="admin-row-actions">
                        <a class="btn ui-sem-control" data-semantic="actions.edit" aria-label="Suppe 2 bearbeiten" href="/item/2/edit"><svg><use href="#tabler-pencil"></use></svg></a>
                        <a class="btn ui-sem-control" data-semantic="actions.delete" aria-label="Suppe 2 löschen" href="/item/2/delete"><svg><use href="#tabler-trash"></use></svg></a>
                      </td>
                    </tr>
                    <tr class="admin-list-row">
                      <td class="admin-list-primary"><a href="/item/3">Suppe 3</a></td>
                      <td class="admin-row-actions">
                        <details class="ui-sem-actions">
                          <summary class="btn ui-sem-control" data-semantic="actions.more" aria-label="Weitere Aktionen 1 für Suppe 3"><svg><use href="#tabler-dots"></use></svg></summary>
                          <div class="ui-sem-action-items"><a class="btn ui-sem-control" href="/item/3/a">A</a></div>
                        </details>
                        <details class="ui-sem-actions">
                          <summary class="btn ui-sem-control" data-semantic="actions.more" aria-label="Weitere Aktionen 2 für Suppe 3"><svg><use href="#tabler-dots"></use></svg></summary>
                          <div class="ui-sem-action-items"><a class="btn ui-sem-control" href="/item/3/b">B</a></div>
                        </details>
                      </td>
                    </tr>
                    <tr class="admin-list-row">
                      <td class="admin-list-primary"><a href="/item/4">Suppe 4</a></td>
                      <td class="admin-row-actions">
                        <details class="ui-sem-actions">
                          <summary class="btn ui-sem-control" data-semantic="actions.more" aria-label="Weitere Aktionen für Suppe 4"><svg><use href="#tabler-dots"></use></svg></summary>
                          <div class="ui-sem-action-items"></div>
                        </details>
                      </td>
                    </tr>
                    <tr class="admin-list-row">
                      <td class="admin-list-primary"><a href="/item/5">Suppe 5</a></td>
                      <td class="admin-row-actions">
                        <a class="btn ui-sem-control" data-semantic="actions.open" aria-label="Suppe 5 öffnen" href="/item/5"><svg><use href="#tabler-arrow-right"></use></svg></a>
                      </td>
                    </tr>
                    <tr class="admin-list-row">
                      <td class="admin-list-primary"><a href="/item/6">Suppe 6</a></td>
                      <td class="admin-row-actions">
                        <a class="btn ui-sem-control" data-semantic="actions.edit" aria-label="Bearbeiten" href="/item/6/edit"><svg><use href="#tabler-pencil"></use></svg></a>
                        <details class="ui-sem-actions">
                          <summary class="btn ui-sem-control" data-semantic="actions.more" aria-label="Weitere Aktionen"><svg><use href="#tabler-dots"></use></svg></summary>
                          <div class="ui-sem-action-items">
                            <a class="btn ui-sem-control" data-semantic="actions.delete" aria-label="Löschen" href="/item/6/delete">Löschen</a>
                          </div>
                        </details>
                      </td>
                    </tr>
                  </tbody>
                </table>
                </main>''')
            measured = page.evaluate(MEASURE_JS)
            assert len(measured['lists']) == 1
            b = measured['lists'][0]['budget']
            assert b['totalRows'] == 6
            r0_violations = [v for v in b['violations'] if v['row'] == 0]
            assert any(v['criterion'] == 'overflow_actions' for v in r0_violations)
            r1_violations = [v for v in b['violations'] if v['row'] == 1]
            assert not r1_violations, 'Multiple direct, named actions are valid'
            page.locator('tr').nth(1).locator('a.btn').first.evaluate('el => el.hidden = true')
            hidden = page.evaluate(MEASURE_JS)['budgetViolations']
            assert any(v['criterion'] == 'hidden_actions' and v['row'] == 1 for v in hidden)
            r2_violations = [v for v in b['violations'] if v['row'] == 2]
            assert any(v['criterion'] == 'overflow_actions' for v in r2_violations)
            r3_violations = [v for v in b['violations'] if v['row'] == 3]
            assert any(v['criterion'] == 'empty_overflow' for v in r3_violations)
            r4_violations = [v for v in b['violations'] if v['row'] == 4]
            assert any(v['criterion'] == 'duplicate_targets' for v in r4_violations)
            r5_violations = [v for v in b['violations'] if v['row'] == 5]
            assert any(v['criterion'] == 'missing_record_context' for v in r5_violations)
        finally:
            browser.close()


def test_native_summary_is_an_entry_but_empty_hidden_and_inert_menus_stay_empty():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox'])
        try:
            page = browser.new_page()
            entries = [
                ('', 1),
                ('<a href="/details" hidden>Details</a>', 1),
                ('<div inert><button>Details</button></div>', 1),
                ('<details hidden><summary>Details</summary><p>Content</p></details>', 1),
                ('<details inert><summary>Details</summary><p>Content</p></details>', 1),
                ('<a href="/details">Details</a>', 0),
                ('<details><summary>Details</summary><p>Content</p></details>', 0),
            ]
            for entry, expected in entries:
                for opened in ('', ' open'):
                    page.set_content(f'''<main><details{opened}>
                        <summary><svg><use href="#tabler-dots"></use></svg></summary>
                        {entry}</details></main>''')
                    assert page.evaluate(MEASURE_JS)['emptyOverflow'] == expected, (entry, opened)
        finally:
            browser.close()


def test_regenerated_comparison_preserves_manual_visual_findings():
    findings = '## Sichtprüfung und verbleibende Arbeit (Prüfung)\n\nUngeprüfte Rollen bleiben offen.\n'
    for previous in (
        '# Alter Bericht\n\n' + findings + '\n## Messwerte\n\nAlte Tabelle\n',
        '# Alter Bericht\n\n## Messwerte\n\nAlte Tabelle\n\n' + findings,
    ):
        regenerated = _markdown([], {}, previous)
        assert findings.strip() in regenerated
        assert regenerated.count('## Sichtprüfung und verbleibende Arbeit') == 1
        assert 'Alte Tabelle' not in regenerated


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
            if (details.querySelector('tr[data-template-id]')) details.open = true;
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
    return '|'.join(str(style[key]) for key in ('fontSize', 'fontWeight', 'textTransform', 'color'))


def _sig_text(style: dict | None) -> str | None:
    if not style:
        return None
    values = [str(style[key]) for key in ('fontSize', 'fontWeight', 'color')]
    if style['linkColor'] and style['linkColor'] != style['color']:
        values.append(style['linkColor'])
    return '|'.join(values)


def test_typography_compares_present_roles_without_hiding_real_differences():
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox'])
        try:
            page = browser.new_page()
            page.set_content('''<style>
                th, .admin-list-primary {font-size:14px;font-weight:500;color:rgb(30,30,30)}
                a {color:inherit}.admin-list-secondary {font-size:12px;color:rgb(70,70,70)}
                .tall th {padding:20px;background:rgb(230,230,230)}
                .different th {font-size:16px}.different .admin-list-primary {font-weight:700}
                .different .admin-list-secondary {color:rgb(100,100,100)}
                </style><main>'''+ ''.join(
                f'''<table class="{kind}">{'<thead><tr><th>Name</th></tr></thead>' if kind != 'headless' else ''}
                <tbody><tr><td><span class="admin-list-primary">{primary}</span>
                <span class="admin-list-secondary">Secondary</span></td></tr></tbody></table>'''
                for kind, primary in [('plain', 'Plain'), ('linked', '<a href="/detail">Linked</a>'),
                                      ('tall', 'Tall'), ('headless', 'Headless'), ('different', 'Different')]
            ) + '</main>')
            rows = _flatten('probe', 'Probe', '/', 1440, 900, _measure(page))
            assert rows[0]['header_sig'] == rows[2]['header_sig']
            assert dict(rows[0]['metrics'])['Kopfzeile'] != dict(rows[2]['metrics'])['Kopfzeile']
            assert rows[0]['primary_sig'] == rows[1]['primary_sig']
            assert rows[3]['header_sig'] is None
            assert _deviations(rows, [], _modes(rows)) == [
                'haupt_typografie:tabelle-5', 'kopf_typografie:tabelle-5', 'sekundaer_typografie:tabelle-5']
            markdown = _markdown(rows, {})
            assert '| Kopfzeile | keine Kopfzeile |' in markdown
            assert '| Kopfzeile | **16px' in markdown
            assert '| Haupttext | **14px / 700' in markdown
            assert '| Sekundärtext | **12px / 400 / rgb(100, 100, 100)' in markdown
            page.locator('a').evaluate("el => el.style.color = 'rgb(200, 0, 0)'")
            changed = _flatten('probe', 'Probe', '/', 1440, 900, _measure(page))
            assert 'haupt_typografie:tabelle-2' in _deviations(changed, [], _modes(changed))
        finally:
            browser.close()


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
        'status': 'keine', 'rowActions': {'count': 0, 'withText': 0, 'objectWithText': 0, 'texts': [], 'icons': [], 'family': 'keins', 'hits': []},
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
            'row_count': item['rowActions']['count'], 'row_text': bool(item['rowActions']['objectWithText']),
            'header_text': bool(header_pack['objectWithText']), 'header_filled': header_pack['filled'],
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
        if row['header_text']:
            codes.add('390:kopfaktion_text')
    return sorted(codes)


def _markdown(desktop: list[dict], mobile_by_slug: dict[str, list[dict]], previous_report: str = '') -> str:
    metric_values: dict[str, list[str]] = {}
    lines_raw: list[tuple[str, str, str, str, str | None]] = []
    typography = {'Kopfzeile': 'header_sig', 'Haupttext': 'primary_sig', 'Sekundärtext': 'secondary_sig'}

    def add(page: str, viewport: str, name: str, value: str, signature: str | None = None) -> None:
        comparison = signature if name in typography else value
        if comparison is not None:
            metric_values.setdefault(name, []).append(comparison)
        lines_raw.append((page, viewport, name, value, comparison))

    seen_mobile_header: set[str] = set()
    paired = {(row['slug'], row['list_key']) for row in desktop}
    for row in desktop:
        page = f"{row['title']} · {row['label']}"
        for name, value in row['metrics']:
            add(page, '1440×900', name, value, row.get(typography.get(name)))
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

    def cell(name: str, value: str, comparison: str | None) -> str:
        text = value.replace('|', '/').replace('\n', ' ')
        return f'**{text}**' if comparison is not None and modes.get(name) not in (None, comparison) else text

    body = ['| Seite | Viewport | Messgrösse | Wert |', '|---|---|---|---|']
    body.extend(f'| {page} | {viewport} | {name} | {cell(name, value, comparison)} |' for page, viewport, name, value, comparison in lines_raw)
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
        f'Gemessen {datetime.now(UTC).isoformat(timespec="seconds")} gegen `UI-DIRECT-ACTIONS-2026-09-29` (§3 direkte Aktionen, §4 Geometrie, §10 Abnahme).',
        'Fett markiert ist jeder Wert, der von der häufigsten Ausprägung dieser Messgrösse abweicht.',
        'Typografie wird nur zwischen vorhandenen Textrollen verglichen; fehlende Kopfzeilen zählen nicht als Abweichung. Kopf-Hintergrund, Kopf-Höhe und Linkstatus bleiben Messwerte, gehören aber nicht zur Schrift-Signatur. Abweichende Linkfarben zählen weiterhin.',
        'Geschlossene Überlaufmenüs und Bestätigungsdialoge (§5.4) sind nicht geöffnet und zählen nicht als sichtbarer Text.',
        '',
        f'Seiten: {len({row["slug"] for row in desktop})}. Listenblöcke bei 1440×900: {len(desktop)}.',
        '',
        '## Zusammenfassung',
        '',
        f'- Seiten mit Buttontext in Zeile oder Kopf: {listing(button_pages)}',
        f'- Seiten mit Karte je Zeile: {listing(card_pages)}',
        f'- Seiten mit mehr als zwei direkten Zeilenaktionen (zulässig): {listing(many)}',
        f'- Seiten mit abweichender Kopf-, Haupt- oder Sekundärtypografie: {listing(type_pages)}',
        '',
        '## Messwerte',
        '',
        *body,
        '',
    ]
    _, marker, findings = previous_report.partition('## Sichtprüfung und verbleibende Arbeit')
    if marker:
        manual_section = marker + findings.split('\n## Messwerte', 1)[0].rstrip()
        summary[summary.index('## Messwerte'):summary.index('## Messwerte')] = [manual_section, '']
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


def test_list_family_across_admin_pages(admin_app, admin_engine, live_server, tmp_path):  # noqa: F811
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
    (tmp_path / 'list-family-measurements.json').write_text(
        json.dumps({'desktop': desktop, 'mobile': mobile, 'deviations': current}, ensure_ascii=False, indent=2),
        encoding='utf-8')
    assert BASELINE_PATH.is_file(), 'Geprüfte Listenfamilien-Baseline fehlt.'
    baseline = json.loads(BASELINE_PATH.read_text(encoding='utf-8'))['pages']
    new_pages = sorted(set(current) - set(baseline))
    new_codes = [f'{slug}: {code}' for slug, codes in current.items() for code in codes if code not in baseline.get(slug, [])]
    satisfied = [f'{slug}: {code}' for slug, codes in baseline.items() if slug in current for code in codes if code not in current[slug]]
    if satisfied:
        print('LIST_FAMILY_SATISFIED=' + '; '.join(satisfied))
    assert not new_pages, 'Neue Listen ohne Baseline: ' + ', '.join(new_pages)
    assert not new_codes, 'Neue Abweichungen:\n' + '\n'.join(new_codes)
    if report:
        REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
        previous_report = REPORT_PATH.read_text(encoding='utf-8') if REPORT_PATH.exists() else ''
        REPORT_PATH.write_text(_markdown(desktop, mobile, previous_report), encoding='utf-8')
        BASELINE_PATH.write_text(json.dumps({'pages': current}, ensure_ascii=False, indent=2) + '\n', encoding='utf-8')
        print(f'LIST_FAMILY_REPORT={REPORT_PATH}')
        print(f'LIST_FAMILY_BASELINE={BASELINE_PATH}')
        print(f'LIST_FAMILY_CONTACT={EVIDENCE / "contact-sheet.png"}')


def test_action_budget_across_all_normal_rows(admin_app, admin_engine, live_server):  # noqa: F811
    _mount_public_targets(admin_app)
    client, actor = _login(admin_app, admin_engine, ['Cafeteria.Admin'])
    entities = _prepare_inventory_entities(admin_app, admin_engine, actor)
    create_api_key(admin_engine, actor_id=actor, label='Listenfamilie', scopes=('preview.read',),
                   channels=('cafeteria',), expires_at=datetime.now(UTC) + timedelta(days=10))
    revision = entities['endpoint_paths']['admin.recipe_revision'].rsplit('/', 1)[-1]
    pages = _catalog(entities['endpoint_paths'])
    cookie = client.get_cookie('session')
    assert cookie is not None
    violations_by_page: dict[str, list[tuple[str, dict]]] = {}
    with sync_playwright() as playwright:
        browser = playwright.chromium.launch(args=['--no-sandbox', '--disable-dev-shm-usage'])
        try:
            with browser.new_context(base_url=live_server, viewport={'width': 1440, 'height': 900},
                                     device_scale_factor=1) as context:
                context.add_cookies([{'name': 'session', 'value': cookie.value, 'url': live_server}])
                page = context.new_page()
                for slug, _title, path, hook in pages:
                    # Planungsansicht (Spec §4.3, §14): Dichteziele gelten nicht für
                    # Kalender; Tagestitel und Planen bleiben dort bewusst erhalten.
                    if slug == 'kuechenkalender' or slug in PENDING_DIRECT_ACTION_PAGES:
                        continue
                    response = page.goto(path, wait_until='domcontentloaded', timeout=30000)
                    assert response and response.status == 200, (slug, path)
                    _hook(page, hook, revision)
                    data = page.evaluate(MEASURE_JS)
                    for item in data.get('budgetViolations', []):
                        violations_by_page.setdefault(slug, []).append((path, item))
        finally:
            browser.close()
    if violations_by_page:
        summary_lines = []
        for slug, items in sorted(violations_by_page.items()):
            for path, v in items:
                summary_lines.append(f"- {slug} ({path}) [{v['listLabel']} Zeile {v['row']}]: {v['criterion']} — {v['message']}")
        assert not violations_by_page, (
            "Aktionsbudget-Verstösse in normalen Listen gefunden:\n" + "\n".join(summary_lines)
        )
