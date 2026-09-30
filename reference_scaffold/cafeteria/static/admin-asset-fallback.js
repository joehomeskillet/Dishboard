/* Failed <use> sprites have no CSS error state. One probe marks <html>; labels live in ui-semantic.css. */
(() => {
  'use strict';
  const root = document.documentElement;
  if (root.dataset.adminAssetFallback === '1') return;
  root.dataset.adminAssetFallback = '1';

  function spriteUrl() {
    for (const use of document.querySelectorAll('use')) {
      const href = use.getAttribute('href') || use.getAttribute('xlink:href') || '';
      if (!href.includes('tabler-icons.svg')) continue;
      const hash = href.indexOf('#');
      return hash === -1 ? href : href.slice(0, hash);
    }
    return '';
  }

  function probeSprite() {
    const url = spriteUrl();
    if (!url) return;
    fetch(url, {credentials: 'same-origin', cache: 'no-store'}).then(response => {
      if (!response.ok) throw new Error('sprite');
      return response.text();
    }).then(text => {
      if (!text.includes('<svg')) throw new Error('sprite');
    }).catch(error => {
      if (error && error.name === 'AbortError') return;
      root.classList.add('ui-asset-sprite-missing');
    });
  }

  probeSprite();
  window.addEventListener('pageshow', () => {});
})();
