'use strict';

const TIME_ZONE = 'Europe/Zurich';
const DEFAULT_INTERVAL_MS = 60000;
const FADE_MS = 300;
const PAGE_INTERVAL_MS = 30000;

function readIntervalMs(root) {
  const raw = root.dataset.signageInterval;
  const parsed = Number.parseInt(raw || '', 10);
  if (Number.isFinite(parsed) && parsed > 0) {
    return parsed;
  }
  return DEFAULT_INTERVAL_MS;
}

function zurichDateString(date) {
  return new Intl.DateTimeFormat('en-CA', {
    timeZone: TIME_ZONE,
    year: 'numeric',
    month: '2-digit',
    day: '2-digit',
  }).format(date);
}

function formatClock(date) {
  return new Intl.DateTimeFormat('de-CH', {
    timeZone: TIME_ZONE,
    hour: '2-digit',
    minute: '2-digit',
    hour12: false,
  }).format(date);
}

function formatStatusTime(date) {
  return `Stand ${formatClock(date)}`;
}

function prefersReducedMotion() {
  return window.matchMedia('(prefers-reduced-motion: reduce)').matches;
}

function updateClock() {
  const now = new Date();
  const clockNode = document.querySelector('[data-signage-clock]');
  const clockText = formatClock(now);
  if (clockNode) {
    clockNode.textContent = clockText;
    clockNode.dateTime = now.toISOString();
  }
}

function markOffline() {
  const statusNode = document.querySelector('[data-signage-status]');
  if (!statusNode) {
    return;
  }
  statusNode.dataset.offline = 'true';
  const base = statusNode.textContent.replace(/\s*\(offline\)\s*$/, '');
  if (!base.includes('(offline)')) {
    statusNode.textContent = `${base} (offline)`;
  }
}

function clearOffline() {
  const statusNode = document.querySelector('[data-signage-status]');
  if (!statusNode) {
    return;
  }
  delete statusNode.dataset.offline;
  statusNode.textContent = formatStatusTime(new Date());
}

function replaceSection(currentNode, nextNode) {
  if (!currentNode || !nextNode) {
    return false;
  }
  currentNode.replaceWith(document.importNode(nextNode, true));
  return true;
}

function syncRootAttributes(currentRoot, nextRoot) {
  currentRoot.dataset.signageRevision = nextRoot.dataset.signageRevision || '';
  currentRoot.dataset.signageDate = nextRoot.dataset.signageDate || '';
  currentRoot.dataset.signageInterval = nextRoot.dataset.signageInterval || String(DEFAULT_INTERVAL_MS);
}

async function fetchDocument(pathname) {
  const controller = new AbortController();
  const timeout = window.setTimeout(() => controller.abort(), 15000);
  try {
    const response = await fetch(pathname, {
      method: 'GET',
      cache: 'no-store',
      credentials: 'omit',
      redirect: 'error',
      signal: controller.signal,
    });
    if (response.status >= 500) {
      throw new Error(`get-${response.status}`);
    }
    const html = await response.text();
    return {
      parsed: new DOMParser().parseFromString(html, 'text/html'),
      revision: response.ok ? response.headers.get('X-Snapshot-Revision') || '' : '',
    };
  } finally {
    window.clearTimeout(timeout);
  }
}

async function applyDocumentSwap(parsed, revision) {
  const frameNode = document.querySelector('[data-signage-frame]');
  const nextRoot = parsed.documentElement;
  const nextHeader = parsed.querySelector('[data-signage-header]');
  const nextMain = parsed.querySelector('[data-signage-root]');
  const nextFooter = parsed.querySelector('[data-signage-footer]');
  const currentHeader = document.querySelector('[data-signage-header]');
  const currentMain = document.querySelector('[data-signage-root]');
  const currentFooter = document.querySelector('[data-signage-footer]');

  if (!nextMain || !currentMain || (!revision && nextRoot.dataset.signageRevision)) {
    // A client error or a withdrawn publication must never retain the old menu.
    const section = document.createElement('section');
    section.className = 'signage-empty';
    const title = document.createElement('h1');
    title.textContent = 'Speiseplan nicht verfügbar';
    const message = document.createElement('p');
    message.textContent = 'Der Speiseplan kann zurzeit nicht angezeigt werden.';
    section.append(title, message);
    currentMain.replaceChildren(section);
    document.documentElement.dataset.signageRevision = '';
    document.documentElement.dataset.signageDate = zurichDateString(new Date());
    document.querySelector('.signage-revision').textContent = '';
    return;
  }

  const useFade = Boolean(revision) && !prefersReducedMotion();
  if (useFade && frameNode) {
    frameNode.classList.add('is-updating');
    await new Promise(resolve => window.setTimeout(resolve, FADE_MS));
  }

  replaceSection(currentHeader, nextHeader);
  replaceSection(currentMain, nextMain);
  replaceSection(currentFooter, nextFooter);
  syncRootAttributes(document.documentElement, nextRoot);
  document.documentElement.dataset.signageRevision = revision;
  document.title = parsed.title;
  const nextFrame = parsed.querySelector('[data-signage-frame]');
  if (frameNode && nextFrame) {
    frameNode.className = nextFrame.className;
  }

  if (useFade && frameNode) {
    window.setTimeout(() => {
      frameNode.classList.remove('is-updating');
    }, FADE_MS);
  } else if (frameNode) {
    frameNode.classList.remove('is-updating');
  }
}

function initSignageEngine() {
  const root = document.documentElement;
  const pathname = window.location.pathname;
  let activePage = 0;
  let pageTimer;
  let pageFadeTimer;

  function selectPage(index) {
    // Resolve the current DOM every time: a withdrawal must never revive detached menus.
    const pages = [...document.querySelectorAll('[data-signage-pages] > [data-signage-page]')];
    activePage = Math.max(0, Math.min(index, pages.length - 1));
    pages.forEach((page, pageIndex) => { page.hidden = pageIndex !== activePage; });
    return pages.length;
  }

  function stopPaging() {
    window.clearTimeout(pageTimer);
    window.clearTimeout(pageFadeTimer);
    document.querySelector('[data-signage-frame]')?.classList.remove('is-updating');
  }

  function schedulePage() {
    window.clearTimeout(pageTimer);
    const count = document.querySelectorAll('[data-signage-pages] > [data-signage-page]').length;
    if (count < 2) return;
    pageTimer = window.setTimeout(() => {
      const rotate = () => {
        selectPage((activePage + 1) % count);
        document.querySelector('[data-signage-frame]')?.classList.remove('is-updating');
        schedulePage();
      };
      if (prefersReducedMotion()) {
        rotate();
      } else {
        document.querySelector('[data-signage-frame]')?.classList.add('is-updating');
        pageFadeTimer = window.setTimeout(rotate, FADE_MS);
      }
    }, PAGE_INTERVAL_MS);
  }

  updateClock();
  clearOffline();
  selectPage(activePage);
  schedulePage();

  async function pollOnce() {
    try {
      const { parsed, revision } = await fetchDocument(pathname);
      const localRevision = root.dataset.signageRevision || '';
      const localDate = root.dataset.signageDate || '';
      // The server owns the display date; its Zurich date can change within one revision.
      const remoteDate = parsed.documentElement.dataset.signageDate || '';
      if (!revision || revision !== localRevision || remoteDate !== localDate) {
        stopPaging();
        await applyDocumentSwap(parsed, revision);
        selectPage(activePage);
        schedulePage();
      }
      clearOffline();
      updateClock();
    } catch (_error) {
      markOffline();
    } finally {
      // Schedule after completion so slow responses cannot overlap or race a withdrawal.
      window.setTimeout(pollOnce, readIntervalMs(root));
    }
  }

  window.setTimeout(pollOnce, readIntervalMs(root));
  window.setInterval(updateClock, 60000);
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', initSignageEngine);
} else {
  initSignageEngine();
}
