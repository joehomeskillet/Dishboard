'use strict';

const printButton = document.getElementById('week-print-button');
const printStatus = document.getElementById('week-print-status');

printButton.addEventListener('click', async () => {
  printButton.disabled = true;
  printStatus.textContent = 'Druckansicht wird vorbereitet …';
  try {
    await document.fonts.ready;
    await Promise.all(Array.from(document.images, image => image.decode()));
    printStatus.textContent = 'A4 Hochformat · Massstab 100 % · Kopf- und Fusszeilen ausschalten.';
    window.print();
  } catch {
    printStatus.textContent = 'Bilder konnten nicht geladen werden. Seite neu laden und erneut drucken.';
  } finally {
    printButton.disabled = false;
  }
});
