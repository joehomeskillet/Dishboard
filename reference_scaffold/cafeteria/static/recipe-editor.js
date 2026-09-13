/* Native POST remains the only recipe writer; disclosures never recreate fields. */
(() => {
    'use strict';
    const form = document.getElementById('recipe-editor');
    if (!form) return;
    if (!form.querySelector('fieldset').disabled) form.classList.add('admin-compact-enhanced');
    // admin.js tracks field edits; a structural POST also contains unsaved row changes.
    let unsavedRows = form.dataset.recipeUnsaved === 'true';
    window.addEventListener('beforeunload', event => {
        if (unsavedRows) {
            event.preventDefault();
            event.returnValue = '';
        }
    });
    form.addEventListener('submit', () => { unsavedRows = false; });

    const controls = new Map();
    function reveal(field) {
        for (let panel = field.closest('details'); panel; panel = panel.parentElement.closest('details')) {
            panel.open = true;
        }
    }
    form.querySelectorAll('[data-recipe-toggle]').forEach(button => {
        // Disabled/archived forms keep their readable native disclosures.
        if (button.matches(':disabled')) return;
        const panel = document.getElementById(button.dataset.recipeToggle);
        if (!panel) return;
        controls.set(panel, button);
        const instruction = panel.querySelector('textarea[required]');
        if (instruction && instruction.value.trim() && !instruction.autofocus && !instruction.matches('[aria-invalid="true"]')) {
            panel.open = false;
        }
        panel.querySelector(':scope > summary').hidden = true;
        button.hidden = false;
        const sync = () => button.setAttribute('aria-expanded', String(panel.open));
        sync();
        panel.addEventListener('toggle', sync);
        button.addEventListener('click', () => {
            panel.open = !panel.open;
            sync();
            if (panel.open) panel.querySelector('input:not([type="hidden"]), select, textarea')?.focus();
        });
    });

    function summarize(row) {
        if (!row) return;
        const value = suffix => row.querySelector(`[name$=".${suffix}"]`)?.value || '';
        const ingredient = row.querySelector('[data-recipe-ingredient-summary]');
        const food = row.querySelector('[name$=".food_public_id"]');
        if (ingredient) ingredient.textContent = [food?.value && `Stammdaten: ${food.selectedOptions[0].textContent}`,
            value('group_label') && `Gruppe: ${value('group_label')}`,
            value('note') && `Notiz: ${value('note')}`].filter(Boolean).join(' · ');
        const step = row.querySelector('[data-recipe-step-summary]');
        if (step) {
            const instruction = value('instruction').trim();
            step.textContent = instruction.length > 140 ? instruction.slice(0, 140) + ' …' : instruction;
            const image = row.querySelector('[name$=".image_sha256"]');
            row.querySelector('[data-recipe-step-extra]').textContent = [
                value('duration_minutes') !== '' && `Dauer: ${value('duration_minutes')} Minuten`,
                image?.value && `Bild: ${image.selectedOptions[0].textContent}`,
            ].filter(Boolean).join(' · ');
        }
    }
    const invalidFields = new Set();
    function errorState(field, invalid) {
        const id = field.id + '-error';
        let message = document.getElementById(id);
        if (invalid) {
            invalidFields.add(field);
            field.setAttribute('aria-invalid', 'true');
            field.setAttribute('aria-describedby', id);
            if (!message) {
                message = document.createElement('p');
                message.id = id;
                message.className = 'invalid-feedback d-block mb-0';
                field.after(message);
            }
            message.textContent = field.validationMessage;
        } else {
            invalidFields.delete(field);
            field.removeAttribute('aria-invalid');
            field.removeAttribute('aria-describedby');
            message?.remove();
        }
        for (const [panel, button] of controls) {
            const errors = [...invalidFields].filter(control => panel.contains(control));
            const hasError = errors.length > 0;
            if (hasError) button.setAttribute('aria-describedby', errors.map(control => control.id + '-error').join(' '));
            else button.removeAttribute('aria-describedby');
            let badge = button.querySelector('[data-recipe-error-badge]');
            if (hasError && !badge) {
                badge = document.createElement('span');
                badge.dataset.recipeErrorBadge = '';
                badge.className = 'text-danger';
                badge.textContent = ' · Fehler';
                button.append(badge);
            } else if (!hasError) badge?.remove();
        }
    }
    form.addEventListener('invalid', event => {
        reveal(event.target);
        errorState(event.target, true);
    }, true);
    // Shared Escape handling targets native summaries; these panels use an inline toggle.
    form.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        const nearest = event.target.closest('details[open]');
        const panel = nearest || [...controls.keys()].find(candidate => candidate.open);
        const button = controls.get(panel);
        if (!button) return;
        event.preventDefault();
        event.stopPropagation();
        panel.open = false;
        button.focus();
    });
    form.addEventListener('input', event => {
        summarize(event.target.closest('[data-recipe-ingredient], [data-recipe-step]'));
        if (invalidFields.has(event.target)) errorState(event.target, !event.target.validity.valid);
    });
    form.addEventListener('change', event => {
        summarize(event.target.closest('[data-recipe-ingredient], [data-recipe-step]'));
    });
    form.querySelectorAll('[data-recipe-step]').forEach(summarize);
    const focused = form.querySelector('[autofocus], [aria-invalid="true"]');
    if (focused) {
        reveal(focused);
        focused.focus();
    }
})();
