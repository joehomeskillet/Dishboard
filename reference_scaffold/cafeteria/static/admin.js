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
        form.addEventListener('submit', () => {
            isDirty = false;
        });
    });

    window.addEventListener('beforeunload', (e) => {
        if (isDirty) {
            e.preventDefault();
            e.returnValue = '';
        }
    });

    function updateDirtyState() {
        const previewLinks = document.querySelectorAll('.admin-actions a[target="_blank"]');
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

    // 2. Publizieren / Archivieren confirm
    const confirmForms = document.querySelectorAll('form[data-confirm]');
    confirmForms.forEach(form => {
        form.addEventListener('submit', (e) => {
            if (!window.confirm(form.getAttribute('data-confirm'))) {
                e.preventDefault();
            }
        });
    });

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

    // 5. Menü-Editor "Zeile hinzufügen" & Escape für Details
    const buttons = document.querySelectorAll('button');
    buttons.forEach(btn => {
        if (btn.textContent.trim() === 'Zeile hinzufügen') {
            btn.addEventListener('click', (e) => {
                e.preventDefault();
                const container = btn.closest('fieldset, tbody');
                if (container) {
                    // find rows that are typically cloned
                    const rows = container.querySelectorAll('.cloneable-row, tr, .row, .field-row, .component-row');
                    if (rows.length > 0) {
                        const lastRow = rows[rows.length - 1];
                        const clone = lastRow.cloneNode(true);
                        const inputs = clone.querySelectorAll('input, select, textarea');
                        inputs.forEach(input => {
                            if (input.type === 'checkbox' || input.type === 'radio') {
                                input.checked = false;
                            } else {
                                input.value = '';
                            }
                            input.removeAttribute('aria-invalid');
                        });
                        lastRow.parentNode.insertBefore(clone, lastRow.nextSibling);
                    }
                }
            });
        }
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
