() => {
    const controls = 'button, a.btn, [role="button"], summary, [role="tab"], .nav-link';
    const hidden = '.visually-hidden, .sr-only, script, style, template, noscript';
    const overlay = 'dialog, [role="dialog"], [role="listbox"], [role="menu"], [popover], '
        + '.modal, .dropdown-menu, .flatpickr-calendar, .ts-dropdown';
    const dash = /^[-–—−]$/u;
    const cache = new WeakMap();
    const visible = el => {
        if (!el || el.closest(hidden)) return false;
        if (cache.has(el)) return cache.get(el);
        const s = getComputedStyle(el), box = el.getBoundingClientRect();
        const shown = s.display !== 'none' && s.visibility === 'visible'
            && el.checkVisibility({checkOpacity: true, checkVisibilityCSS: true})
            && box.width > 0 && box.height > 0;
        cache.set(el, shown);
        return shown;
    };
    const pseudo = (el, side) => {
        const s = getComputedStyle(el, side);
        if (!visible(el) || s.display === 'none' || s.visibility !== 'visible'
            || Number(s.opacity) === 0 || ['none', 'normal'].includes(s.content)) return null;
        const width = parseFloat(s.width), height = parseFloat(s.height);
        if (width === 0 && height === 0 && !parseFloat(s.borderTopWidth)) return null;
        // Computed content contains decoded CSS escapes; quoted empty content can draw an arrow.
        const text = s.content.replace(/^['"]|['"]$/g, '').trim();
        const borderIcon = !text && ['Top', 'Right', 'Bottom', 'Left'].some(
            edge => parseFloat(s[`border${edge}Width`]) > 0
                && s[`border${edge}Style`] !== 'none');
        const icon = s.backgroundImage !== 'none' || s.maskImage !== 'none' || borderIcon
            || s.content.startsWith('url(') || /\p{Extended_Pictographic}/u.test(text)
            || /[\uE000-\uF8FF]/u.test(text) || /icon|awesome|material|tabler/i.test(s.fontFamily)
            || /^[✓✔✕×⌄⌃‹›←→↑↓]+$/u.test(text);
        return {side, text, icon};
    };
    const parts = (root, skipControls = true) => {
        const text = [], icons = [];
        const walk = el => {
            if (!visible(el)) return;
            if (skipControls && el !== root && el.matches(controls)) return;
            if (el.matches('svg, i, img') || getComputedStyle(el).backgroundImage !== 'none'
                || getComputedStyle(el).maskImage !== 'none') {
                icons.push(el.tagName.toLowerCase());
            }
            if (el.matches('svg, i, img')) return;
            for (const side of ['::before', '::after']) {
                const p = pseudo(el, side);
                if (p?.icon) icons.push(side);
                else if (p?.text) text.push(p.text);
            }
            for (const node of el.childNodes) {
                if (node.nodeType === Node.ELEMENT_NODE) walk(node);
                else if (node.nodeType === Node.TEXT_NODE && node.textContent.trim()) {
                    const range = document.createRange();
                    range.selectNodeContents(node);
                    if ([...range.getClientRects()].some(r => r.width > 0 && r.height > 0)) {
                        text.push(node.textContent);
                    }
                }
            }
        };
        walk(root);
        return {text: text.join(' ').replace(/\s+/gu, ' ').trim(), icons};
    };
    const stable = value => !/[0-9a-f]{8}-[0-9a-f-]{27}|\d{10,}/i.test(value);
    const selector = el => {
        const path = [];
        for (let node = el; node && node !== document.documentElement; node = node.parentElement) {
            if (node.id && stable(node.id)) {
                path.unshift('#' + CSS.escape(node.id));
                break;
            }
            const semantic = node.getAttribute('data-semantic');
            if (semantic && stable(semantic)) {
                const attr = `[data-semantic="${CSS.escape(semantic)}"]`;
                if (document.querySelectorAll(attr).length === 1) {
                    path.unshift(attr);
                    break;
                }
            }
            const tag = node.tagName.toLowerCase();
            const peers = [...node.parentElement.children].filter(n => n.tagName === node.tagName);
            path.unshift(tag + (peers.length > 1 ? `:nth-of-type(${peers.indexOf(node) + 1})` : ''));
        }
        return path.join(' > ');
    };
    const findings = [];
    const add = (el, category, content, extra = {}) => findings.push({
        category, selector: selector(el), text: content.text, icons: content.icons, ...extra,
    });
    for (const el of document.querySelectorAll(controls)) {
        if (!visible(el) || el.matches('input, select, option')) continue;
        // Sidebar navigation entries are exempt; its action buttons still obey B-01.
        if (el.matches('a.nav-link') && el.closest('.admin-sidebar, [data-sidebar]')) continue;
        const content = parts(el);
        if (content.icons.length && content.text) add(el, 'mixed_button', content);
    }
    const candidates = [...document.body.querySelectorAll('*')].filter(el =>
        visible(el) && !el.matches('input, select, option, svg, i, img')
        && !el.closest('select, code, pre, math') && dash.test(parts(el, false).text));
    for (const el of candidates) {
        if (!candidates.some(child => child !== el && el.contains(child))) {
            add(el, 'dash_placeholder', parts(el, false));
        }
    }
    for (const el of document.querySelectorAll('details')) {
        const summary = el.querySelector(':scope > summary');
        if (visible(summary) && !el.closest('nav, .admin-sidebar, [role="navigation"]')) {
            add(el, 'content_disclosure', parts(summary), {mechanism: 'details'});
        }
    }
    for (const el of document.querySelectorAll('[aria-expanded]')) {
        if (!visible(el) || el.closest('nav, .admin-sidebar, [role="navigation"]')
            || el.matches('summary, select, [role="combobox"]')) continue;
        const targetIds = (el.getAttribute('aria-controls') || '').split(/\s+/u).filter(Boolean);
        const cssTarget = el.getAttribute('data-bs-target') || el.getAttribute('data-target');
        const targets = targetIds.map(id => document.getElementById(id)).filter(Boolean);
        if (cssTarget?.startsWith('#')) {
            const target = document.getElementById(cssTarget.slice(1));
            if (target && !targets.includes(target)) targets.push(target);
        }
        for (const target of targets) {
            if (target.closest(overlay) || target.closest('nav, [role="navigation"]')) continue;
            let inFlow = true;
            for (let node = target; node && node !== document.body; node = node.parentElement) {
                if (['absolute', 'fixed'].includes(getComputedStyle(node).position)) inFlow = false;
            }
            if (inFlow) add(el, 'content_disclosure', parts(el), {
                mechanism: 'aria-expanded', target: selector(target),
            });
        }
    }
    return findings;
}
