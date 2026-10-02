/* Native POST remains the only recipe writer; all editor fields stay visible. */
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

    function summarize(row) {
        if (!row) return;
        const value = suffix => row.querySelector(`[name$=".${suffix}"]`)?.value || '';
        const ingredient = row.querySelector('[data-recipe-ingredient-summary]');
        const food = row.querySelector('[name$=".food_public_id"]');
        if (ingredient) ingredient.textContent = [food?.value && `Stammdaten: ${food.selectedOptions[0].textContent}`,
            value('group_label') && `Gruppe: ${value('group_label')}`,
            value('note') && `Notiz: ${value('note')}`].filter(Boolean).join(' · ');
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
    }
    form.addEventListener('invalid', event => {
        errorState(event.target, true);
    }, true);
    form.addEventListener('input', event => {
        summarize(event.target.closest('[data-recipe-ingredient], [data-recipe-step]'));
        if (invalidFields.has(event.target)) errorState(event.target, !event.target.validity.valid);
    });
    form.addEventListener('change', event => {
        summarize(event.target.closest('[data-recipe-ingredient], [data-recipe-step]'));
    });
    const focused = form.querySelector('[autofocus], [aria-invalid="true"]');
    if (focused) {
        focused.focus();
    }
})();
