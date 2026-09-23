(() => {
  const form = document.getElementById('planning-target');
  if (!form) return;
  const label = name => form.elements[name].selectedOptions[0]?.textContent || '';
  const summary = document.getElementById('planning-summary');
  form.addEventListener('change', () => {
    const day = new Date(`${form.elements.week.value}T00:00:00Z`);
    day.setUTCDate(day.getUTCDate() + Number(form.elements.day.value));
    const date = Number.isNaN(day.getTime()) ? form.elements.week.value :
      new Intl.DateTimeFormat('de-CH', {weekday:'long', day:'numeric', month:'long', year:'numeric', timeZone:'UTC'}).format(day);
    summary.textContent = `${form.elements.title.value} → ${label('area')} · ${date} · ${label('meal')} · ${label('option')}`;
  });
})();
