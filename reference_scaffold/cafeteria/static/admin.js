/* === Admin-Redesign === */
(function() {
    'use strict';

    // 1. Dirty-Tracking
    const forms = document.querySelectorAll('form');
    let isDirty = false;

    forms.forEach(form => {
        form.addEventListener('input', () => {
            if (!isDirty) {
                isDirty = true;
                updateDirtyState();
            }
        });
        form.addEventListener('change', () => {
            if (!isDirty) {
                isDirty = true;
                updateDirtyState();
            }
        });
        form.addEventListener('submit', (e) => {
            const confirmation = form.getAttribute('data-confirm');
            if (confirmation && !window.confirm(confirmation)) {
                e.preventDefault();
                return;
            }
            if (!e.defaultPrevented) {
                isDirty = false;
            }
        });
    });

    window.addEventListener('beforeunload', (e) => {
        if (isDirty) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    function updateDirtyState() {
        const previewLinks = document.querySelectorAll('a[href*="/preview"]');
        const publishForms = document.querySelectorAll('form[action*="/publish"]');
        
        previewLinks.forEach(link => {
            link.setAttribute('aria-disabled', 'true');
            link.classList.add('disabled');
            link.addEventListener('click', preventDefaultClick);
            link.textContent = 'Zuerst speichern';
        });

        publishForms.forEach(form => {
            const btn = form.querySelector('button[type="submit"]');
            if (btn) {
                btn.setAttribute('disabled', 'true');
                btn.textContent = 'Zuerst speichern';
            }
        });

        let flashRegion = document.querySelector('.flash-region');
        if (flashRegion) {
            flashRegion.textContent = 'Zuerst speichern';
        }
    }

    function preventDefaultClick(e) {
        e.preventDefault();
    }

    // 3. Fehlerfokus
    const errorRegion = document.querySelector('.error-region');
    const retryBtn = errorRegion ? errorRegion.querySelector('[data-retry-page]') : null;
    function focusFirstError() {
        if (!errorRegion) {
            return;
        }
        errorRegion.focus();
        let firstInvalid = document.querySelector('[aria-invalid="true"]');
        if (!firstInvalid) {
            const menuForm = document.querySelector('form[action$="/menu"]');
            const focusableFields = menuForm ? Array.from(menuForm.elements).filter(control => {
                return control.matches(
                    'input:not([type="hidden"]), select, textarea'
                ) && !control.disabled && control.offsetParent !== null;
            }) : [];
            firstInvalid = focusableFields[0];
            if (firstInvalid) {
                firstInvalid.setAttribute('aria-invalid', 'true');
            }
        }
        if (firstInvalid) {
            firstInvalid.focus();
        }
    }
    if (document.readyState === 'complete') {
        focusFirstError();
    } else {
        document.addEventListener('DOMContentLoaded', focusFirstError, { once: true });
    }
    if (retryBtn) {
        retryBtn.addEventListener('click', () => window.location.reload());
    }

    // 4. Loading State Skeleton Delay & Error Retry
    const mainContent = document.getElementById('main-content');
    if (mainContent) {
        const state = mainContent.getAttribute('data-status');
        if (state === 'loading') {
            setTimeout(() => {
                if (mainContent.getAttribute('data-status') === 'loading') {
                    mainContent.setAttribute('aria-busy', 'true');
                }
            }, 150);
        }
        if (state === 'error' && !retryBtn) {
            const generatedRetryBtn = document.createElement('button');
            generatedRetryBtn.type = 'button';
            generatedRetryBtn.textContent = 'Erneut versuchen';
            generatedRetryBtn.className = 'btn';
            generatedRetryBtn.addEventListener('click', () => window.location.reload());
            if (errorRegion) {
                errorRegion.appendChild(generatedRetryBtn);
            }
        }
        
        // dense toggle
        const denseToggleLabel = document.createElement('label');
        denseToggleLabel.textContent = 'Kompakte Ansicht';
        const denseToggle = document.createElement('input');
        denseToggle.type = 'checkbox';
        denseToggle.checked = localStorage.getItem('admin-dense') === 'true';
        
        if (denseToggle.checked) {
            mainContent.setAttribute('data-state', 'dense');
        }
        
        denseToggle.addEventListener('change', (e) => {
            if (e.target.checked) {
                mainContent.setAttribute('data-state', 'dense');
                localStorage.setItem('admin-dense', 'true');
            } else {
                mainContent.removeAttribute('data-state');
                localStorage.setItem('admin-dense', 'false');
            }
        });
        denseToggleLabel.prepend(denseToggle);
        
        const actions = document.querySelector('.admin-actions');
        if (actions) {
            actions.appendChild(denseToggleLabel);
        } else {
            mainContent.prepend(denseToggleLabel);
        }
    }

    // Native successful controls must match the strict repeated-field contract.
    function syncMetadataControls(form) {
        const menuEditor = form.matches('[data-menu-editor]');
        const manual = name => !menuEditor ||
            form.querySelector(`input[name="${name}_mode"]:checked`)?.value === 'manual';
        form.querySelectorAll('.allergen-row').forEach(row => {
            const checkbox = row.querySelector('input[name="allergen_code"]');
            const presence = row.querySelector('select[name="allergen_presence"]');
            if (checkbox && presence) {
                checkbox.disabled = !manual('allergen');
                presence.disabled = checkbox.disabled || !checkbox.checked;
            }
        });
        if (menuEditor) {
            form.querySelectorAll('select[name="component_public_id"] option[data-active="0"]').forEach(option => {
                option.disabled = !option.selected;
            });
            form.querySelectorAll('[name="label_code"]').forEach(control => {
                control.disabled = !manual('label');
            });
            form.querySelectorAll('.origin-row input, .origin-row button, [data-add-row="origins-list"]').forEach(control => {
                control.disabled = !manual('origin');
            });
        }
    }

    forms.forEach(form => {
        syncMetadataControls(form);
        form.addEventListener('change', () => syncMetadataControls(form));
    });

    document.querySelectorAll('form[data-menu-editor]').forEach(form => {
        form.addEventListener('formdata', (e) => {
            for (const [selector, names] of [
                ['.component-row', ['component_public_id', 'component_text']],
                ['.origin-row', ['origin_ingredient', 'origin_country_code']],
            ]) {
                names.forEach(name => e.formData.delete(name));
                form.querySelectorAll(selector).forEach(row => {
                    const controls = names.map(name => row.querySelector(`[name="${name}"]`));
                    if (controls.every(control => !control.disabled) &&
                        controls.some(control => control.value.trim() !== '')) {
                        controls.forEach((control, index) => {
                            e.formData.append(names[index], control.value);
                        });
                    }
                });
            }
        });

        form.addEventListener('click', (e) => {
            const addButton = e.target.closest('[data-add-row]');
            const removeButton = e.target.closest('[data-remove-row]');
            if (!addButton && !removeButton) return;
            let focusTarget;
            if (addButton) {
                const list = document.getElementById(addButton.dataset.addRow);
                const clone = list.lastElementChild.cloneNode(true);
                clone.querySelectorAll('input, select').forEach(control => {
                    control.value = '';
                    control.removeAttribute('aria-invalid');
                    control.removeAttribute('aria-describedby');
                });
                list.appendChild(clone);
                focusTarget = clone.querySelector('input, select');
            } else {
                const row = removeButton.closest('.component-row, .origin-row');
                const list = row.parentElement;
                if (list.children.length > 1) {
                    row.remove();
                    focusTarget = list.lastElementChild.querySelector('input, select');
                } else {
                    row.querySelectorAll('input, select').forEach(control => {
                        control.value = '';
                    });
                    focusTarget = row.querySelector('input, select');
                }
            }
            syncMetadataControls(form);
            form.dispatchEvent(new Event('input', { bubbles: true }));
            focusTarget.focus();
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            const openDetails = document.querySelectorAll('details[open]');
            openDetails.forEach(details => {
                details.removeAttribute('open');
                const summary = details.querySelector('summary');
                if (summary) summary.focus();
            });
        }
    });
})();
