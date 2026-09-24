/* Progressive enhancement of the shared server-rendered navigation. */
(() => {
  'use strict';
  const key = 'dishboard.admin.navigation.collapsed';
  const body = document.body;
  let collapsed = false;
  try { collapsed = localStorage.getItem(key) === 'true'; } catch (_) { /* Storage is optional. */ }
  body.classList.toggle('admin-nav-collapsed', collapsed);

  const sidebar = document.querySelector('.admin-sidebar');
  const toggle = sidebar?.querySelector('[data-admin-nav-toggle]');
  const flyout = sidebar?.querySelector('#admin-nav-flyout');
  if (!toggle || !flyout || !flyout.showPopover) {
    body.classList.remove('admin-nav-collapsed');
    return;
  }
  const desktop = window.matchMedia('(min-width: 992px)');
  const parents = [...sidebar.querySelectorAll('#sidebar-menu .admin-nav-area > .nav-link')];
  let opener = null;
  let returnFocus = false;

  function close(restore = false) {
    returnFocus = restore;
    if (flyout.matches(':popover-open')) flyout.hidePopover();
  }

  flyout.addEventListener('toggle', event => {
    if (event.newState !== 'closed') return;
    opener?.setAttribute('aria-expanded', 'false');
    if (returnFocus) opener?.focus();
    returnFocus = false;
    // Remove cloned current-page links when the panel is no longer in use.
    flyout.replaceChildren();
  });

  function update() {
    close();
    const rail = collapsed && desktop.matches;
    body.classList.toggle('admin-nav-collapsed', collapsed);
    toggle.hidden = !desktop.matches;
    const label = collapsed ? 'Navigation ausklappen' : 'Navigation einklappen';
    toggle.title = label;
    toggle.setAttribute('aria-label', label);
    toggle.setAttribute('aria-expanded', String(!collapsed));
    for (const parent of parents) {
      if (rail) {
        parent.setAttribute('role', 'button');
        parent.setAttribute('aria-expanded', 'false');
        parent.setAttribute('aria-controls', flyout.id);
        parent.setAttribute('aria-label', parent.title);
      } else {
        for (const name of ['role', 'aria-expanded', 'aria-controls', 'aria-label']) parent.removeAttribute(name);
      }
    }
  }

  function open(parent) {
    if (opener === parent && flyout.matches(':popover-open')) {
      close(true);
      return;
    }
    opener?.setAttribute('aria-expanded', 'false');
    opener = parent;
    flyout.replaceChildren(parent.parentElement.querySelector('template').content.cloneNode(true));
    flyout.setAttribute('aria-label', parent.title);
    parent.setAttribute('aria-expanded', 'true');
    flyout.showPopover();
    flyout.querySelector('a')?.focus();
  }

  for (const parent of parents) {
    parent.addEventListener('click', event => {
      if (!collapsed || !desktop.matches || event.ctrlKey || event.metaKey || event.shiftKey || event.altKey) return;
      event.preventDefault();
      open(parent);
    });
    parent.addEventListener('keydown', event => {
      if (collapsed && desktop.matches && event.key === ' ') {
        event.preventDefault();
        open(parent);
      }
    });
  }
  flyout.addEventListener('keydown', event => {
    if (event.key === 'Escape') {
      event.preventDefault();
      close(true);
    }
    if (event.key === 'Tab') {
      const links = [...flyout.querySelectorAll('a')];
      if ((event.shiftKey && document.activeElement === links[0]) ||
          (!event.shiftKey && document.activeElement === links.at(-1))) {
        event.preventDefault();
        close(true);
      }
    }
  });
  toggle.addEventListener('click', () => {
    collapsed = !collapsed;
    try { localStorage.setItem(key, String(collapsed)); } catch (_) { /* Keep the session usable. */ }
    update();
  });
  desktop.addEventListener('change', update);
  update();
})();
