/* Failed <use> sprites have no CSS error state. One probe marks <html>; labels live in ui-semantic.css. */
(() => {
  'use strict';
  const root = document.documentElement;
  if (root.dataset.adminAssetFallback === '1') return;
  root.dataset.adminAssetFallback = '1';

  const CONTENT = [
    'img.recipe-image',
    'img.recipe-image-thumb',
    'img.admin-logo',
    'img.brand-logo',
    'img.eh-logo',
    '[data-menu-image] img',
    '.menu-photo img',
  ].join(', ');

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
    fetch(url, {credentials: 'same-origin'}).then(response => {
      if (!response.ok) throw new Error('sprite');
      return response.text();
    }).then(text => {
      if (!text.includes('<svg')) throw new Error('sprite');
    }).catch(error => {
      if (error && error.name === 'AbortError') return;
      root.classList.add('ui-asset-sprite-missing');
    });
  }

  function applyImage(img) {
    if (!(img instanceof HTMLImageElement) || !img.matches(CONTENT)) return;
    if (img.dataset.assetImageFallback === '1' || !img.getAttribute('src')) return;
    img.dataset.assetImageFallback = '1';
    const alt = (img.getAttribute('alt') || '').trim() || 'Bild nicht verfügbar';
    const frame = document.createElement('div');
    frame.className = 'asset-image-frame';
    img.before(frame);
    frame.append(img);
    const placeholder = document.createElement('div');
    placeholder.className = 'asset-image-placeholder';
    placeholder.setAttribute('role', 'img');
    placeholder.setAttribute('aria-label', alt);
    placeholder.textContent = alt;
    frame.append(placeholder);
    img.classList.add('asset-image-failed');
    img.setAttribute('aria-hidden', 'true');
  }

  function scanImages() {
    document.querySelectorAll(CONTENT).forEach(img => {
      // Lazy images that have not started report complete with an empty currentSrc.
      if (img.complete && img.naturalWidth === 0 && img.currentSrc) applyImage(img);
    });
  }

  document.addEventListener('error', event => {
    if (event.target instanceof HTMLImageElement) applyImage(event.target);
  }, true);
  probeSprite();
  scanImages();
  requestAnimationFrame(scanImages);
  window.addEventListener('pageshow', () => { scanImages(); });
})();
