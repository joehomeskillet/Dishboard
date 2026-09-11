/* === Admin-Redesign === */
(function() {
    'use strict';

    // Tabler already initializes these tooltips. Keep its instance and positioning.
    const iconActions = document.querySelectorAll('[data-admin-icon-action]');
    iconActions.forEach(link => {
        link.addEventListener('inserted.bs.tooltip', () => {
            const tip = document.getElementById(link.getAttribute('aria-describedby'));
            tip.addEventListener('mouseleave', () => {
                if (!link.matches(':hover, :focus')) window.tabler.Tooltip.getInstance(link).hide();
            });
        });
        link.addEventListener('hide.bs.tooltip', event => {
            const tip = document.getElementById(link.getAttribute('aria-describedby'));
            if (tip?.matches(':hover') && !tip.dataset.dismissed) event.preventDefault();
        });
    });

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
        keepWeekFieldVisible();
    }

    // Native focus scrolling can leave a field partly visible after the status row grows.
    function keepWeekFieldVisible() {
        const field = document.activeElement;
        if (!field || !field.matches('.admin-overview-form input, .admin-overview-form textarea, .admin-overview-form select')) return;
        window.requestAnimationFrame(() => {
            if (document.activeElement !== field) return;
            const viewport = window.visualViewport;
            const top = viewport ? viewport.offsetTop : 0;
            const bottom = top + (viewport ? viewport.height : window.innerHeight);
            const box = field.getBoundingClientRect();
            if (box.height > bottom - top - 16) return;
            const shift = box.bottom > bottom - 8 ? box.bottom - bottom + 8
                : box.top < top + 8 ? box.top - top - 8 : 0;
            if (shift) window.scrollBy({ top: shift, behavior: 'instant' });
        });
    }
    document.addEventListener('focusin', keepWeekFieldVisible);

    function preventDefaultClick(e) {
        e.preventDefault();
    }

    // Native accordions: reveal every closed ancestor before a field is focused.
    function revealAncestors(element) {
        for (let details = element && element.closest('details'); details; details = details.parentElement.closest('details')) {
            details.open = true;
        }
    }

    // 3. Fehlerfokus
    const errorRegion = document.querySelector('.error-region');
    const retryBtn = errorRegion ? errorRegion.querySelector('[data-retry-page]') : null;
    function focusFirstError() {
        if (errorRegion) {
            errorRegion.focus();
        }
        const firstInvalid = document.querySelector('[aria-invalid="true"]:not(:disabled):not([type="hidden"])');
        if (firstInvalid) {
            revealAncestors(firstInvalid);
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
    document.querySelectorAll('.error-region a[data-error-link]').forEach(link => {
        link.addEventListener('click', (e) => {
            const target = document.getElementById(link.getAttribute('href').slice(1));
            if (!target) return;
            e.preventDefault();
            revealAncestors(target);
            target.focus();
        });
    });

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
            form.querySelectorAll('.origin-row input, .origin-row select, .origin-row button, [data-add-row="origins-list"]').forEach(control => {
                control.disabled = !manual('origin');
            });
            form.querySelectorAll('[data-mode-badge]').forEach(badge => {
                badge.textContent = manual(badge.dataset.modeBadge) ? 'manuell festgelegt' : 'automatisch geerbt';
            });
        }
    }

    // Repeated rows keep unique ids, label targets and a numbered legend.
    function renumberRows(list) {
        const prefix = list.dataset.rowList;
        const title = list.dataset.rowTitle;
        Array.from(list.children).forEach((row, index) => {
            row.querySelectorAll('[id], [for], [aria-describedby]').forEach(element => {
                for (const attribute of ['id', 'for', 'aria-describedby']) {
                    const value = element.getAttribute(attribute);
                    if (value) {
                        element.setAttribute(attribute, value.split(/\s+/).map(id => id.startsWith(prefix + '-')
                            ? id.replace(/^([a-z]+)-\d+-/, `$1-${index}-`) : id).join(' '));
                    }
                }
            });
            const legend = row.querySelector('[data-row-legend]');
            if (legend) legend.textContent = `${title} ${index + 1}`;
        });
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
            const moveButton = e.target.closest('[data-move-row]');
            if (!addButton && !removeButton && !moveButton) return;
            let focusTarget;
            let list;
            if (addButton) {
                list = document.getElementById(addButton.dataset.addRow);
                const clone = list.lastElementChild.cloneNode(true);
                clone.querySelectorAll('input, select').forEach(control => {
                    control.value = '';
                    control.classList.remove('is-invalid');
                    control.removeAttribute('aria-invalid');
                    const descriptions = (control.getAttribute('aria-describedby') || '').split(/\s+/)
                        .filter(id => id && !document.getElementById(id)?.classList.contains('field-error'));
                    if (descriptions.length) control.setAttribute('aria-describedby', descriptions.join(' '));
                    else control.removeAttribute('aria-describedby');
                });
                clone.querySelectorAll('.field-error').forEach(error => error.remove());
                list.appendChild(clone);
                focusTarget = clone.querySelector('input, select');
            } else if (moveButton) {
                const row = moveButton.closest('.component-row, .origin-row');
                list = row.parentElement;
                const sibling = moveButton.dataset.moveRow === 'up' ? row.previousElementSibling : row.nextElementSibling;
                if (sibling) {
                    sibling[moveButton.dataset.moveRow === 'up' ? 'before' : 'after'](row);
                }
                focusTarget = moveButton;
            } else {
                const row = removeButton.closest('.component-row, .origin-row');
                list = row.parentElement;
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
            if (list.dataset.rowList) renumberRows(list);
            syncMetadataControls(form);
            form.dispatchEvent(new Event('input', { bubbles: true }));
            focusTarget.focus();
        });
    });

    // Sticky save bar: leave the flow while a virtual keyboard shrinks the visual viewport,
    // and keep focused controls clear of the bar.
    const stickyBar = document.querySelector('form[data-menu-editor] [data-sticky]');
    if (stickyBar) {
        const viewport = window.visualViewport;
        const syncSticky = () => {
            if (!viewport) return;
            stickyBar.classList.toggle('is-static', viewport.height < window.innerHeight - 120);
        };
        if (viewport) {
            viewport.addEventListener('resize', syncSticky);
            syncSticky();
        }
        document.addEventListener('focusin', (e) => {
            if (!e.target.closest('form[data-menu-editor]') || stickyBar.contains(e.target)) return;
            window.requestAnimationFrame(() => {
                if (getComputedStyle(stickyBar).position !== 'sticky') return;
                const bar = stickyBar.getBoundingClientRect();
                const field = e.target.getBoundingClientRect();
                if (bar.top < window.innerHeight && field.bottom > bar.top) {
                    window.scrollBy(0, field.bottom - bar.top + 8);
                }
            });
        });
    }

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            let dismissedTooltip = false;
            iconActions.forEach(link => {
                const tip = document.getElementById(link.getAttribute('aria-describedby'));
                if (tip?.classList.contains('show')) {
                    tip.dataset.dismissed = 'true';
                    window.tabler.Tooltip.getInstance(link).hide();
                    dismissedTooltip = true;
                }
            });
            if (dismissedTooltip) return;
            const openDropdown = document.querySelector('.dropdown-menu.show');
            if (openDropdown) {
                const toggle = openDropdown.closest('.dropdown')?.querySelector('[data-bs-toggle="dropdown"]');
                if (toggle) {
                    if (window.tabler?.Dropdown || window.bootstrap?.Dropdown) {
                        const DropdownClass = window.tabler?.Dropdown || window.bootstrap?.Dropdown;
                        DropdownClass.getInstance(toggle)?.hide();
                    } else {
                        openDropdown.classList.remove('show');
                        toggle.setAttribute('aria-expanded', 'false');
                    }
                    toggle.focus();
                    return;
                }
            }
            const active = document.activeElement && document.activeElement.closest('details[open]');
            const openDetails = active ? [active] : document.querySelectorAll('details[open]');
            openDetails.forEach(details => {
                details.removeAttribute('open');
                const summary = details.querySelector('summary');
                if (summary) summary.focus();
            });
        }
    });
})();

// MP-UI-SHELL: aria-expanded für Offcanvas-Toggler
document.querySelectorAll('[data-bs-toggle="offcanvas"][aria-controls]').forEach(toggle => {
    const target = document.getElementById(toggle.getAttribute('aria-controls'));
    if (!target) return;
    target.addEventListener('shown.bs.offcanvas', () => toggle.setAttribute('aria-expanded', 'true'));
    target.addEventListener('hidden.bs.offcanvas', () => toggle.setAttribute('aria-expanded', 'false'));
});
