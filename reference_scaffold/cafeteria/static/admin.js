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
    const forms = document.querySelectorAll('form:not([data-dirty-tracking="off"])');
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
        const componentRow = element && element.closest('.component-row');
        if (componentRow) setComponentRowEditing(componentRow, true);
    }

    // Disclosures retain their controls and show errors even after being closed again.
    function syncDetailsErrors() {
        document.querySelectorAll('details').forEach(details => {
            const summary = details.querySelector(':scope > summary');
            if (!summary || summary.hidden) return;
            const invalid = details.querySelector('[aria-invalid="true"]:not(:disabled):not([type="hidden"]), [data-admin-native-invalid]');
            let badge = summary.querySelector('[data-admin-details-error]');
            if (invalid && !badge) {
                badge = document.createElement('span');
                badge.dataset.adminDetailsError = '';
                badge.className = 'text-danger';
                badge.textContent = ' · Fehler';
                summary.append(badge);
            } else if (!invalid) badge?.remove();
        });
    }
    document.addEventListener('invalid', event => {
        revealAncestors(event.target);
        event.target.setAttribute('data-admin-native-invalid', '');
        syncDetailsErrors();
    }, true);
    document.addEventListener('input', event => {
        if (!event.target.hasAttribute('data-admin-native-invalid')) return;
        if (event.target.validity.valid) event.target.removeAttribute('data-admin-native-invalid');
        syncDetailsErrors();
    });

    // 3. Fehlerfokus
    const errorRegion = document.querySelector('.error-region');
    const retryBtn = errorRegion ? errorRegion.querySelector('[data-retry-page]') : null;
    function focusFirstError() {
        const invalidFields = document.querySelectorAll('[aria-invalid="true"]:not(:disabled):not([type="hidden"])');
        invalidFields.forEach(revealAncestors);
        syncDetailsErrors();
        if (errorRegion) {
            errorRegion.focus();
            if (!errorRegion.hasAttribute('data-focus-invalid')) return;
        }
        const firstInvalid = invalidFields[0];
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
    document.querySelectorAll('a[data-error-link]').forEach(link => {
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
            form.querySelectorAll('select[name="recipe_revision_public_id"] option[data-archived="1"]').forEach(option => {
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
            const kindGroup = row.querySelector('[data-component-kind] [role="radiogroup"]');
            if (kindGroup) kindGroup.setAttribute('aria-label', `Eingabeart für ${title} ${index + 1}`);
        });
    }

    function componentEntryKind(row) {
        const selected = row.querySelector('[data-component-kind-option]:checked');
        if (selected) return selected.value;
        const catalog = row.querySelector('[name="component_public_id"]');
        const text = row.querySelector('[name="component_text"]');
        return catalog?.value || !text?.value ? 'catalog' : 'text';
    }

    function syncComponentRow(row) {
        const kind = componentEntryKind(row);
        const catalog = row.querySelector('[name="component_public_id"]');
        const text = row.querySelector('[name="component_text"]');
        row.querySelectorAll('[data-component-kind-option]').forEach(option => {
            option.checked = option.value === kind;
        });
        row.querySelectorAll('[data-component-control]').forEach(control => {
            control.hidden = control.dataset.componentControl !== kind;
        });
        const selected = catalog?.selectedOptions[0];
        const summary = kind === 'catalog' && catalog?.value ? selected?.textContent.trim() : text?.value.trim();
        const summaryTarget = row.querySelector('[data-component-summary]');
        if (summaryTarget) summaryTarget.textContent = summary || 'Noch nicht erfasst';
    }

    function setComponentRowEditing(row, editing) {
        row.classList.toggle('is-editing', editing);
        syncComponentRow(row);
        if (editing) {
            const kind = componentEntryKind(row);
            row.querySelector(`[data-component-control="${kind}"] input, [data-component-control="${kind}"] select`)?.focus();
        }
    }

    // Target quantity: unit always mirrors the bound revision's own unit (D3, no conversion),
    // and only accompanies a non-empty quantity (component_assignment_contract pair rule).
    function revisionUnitCode(select) {
        const option = select?.selectedOptions[0];
        if (!option || !option.value) return '';
        const parts = (option.dataset.yield || '').split(' ');
        return parts.length > 1 ? parts[parts.length - 1] : '';
    }

    function syncTargetQuantityField(row, unitDisplayNames, { resetQuantity = false } = {}) {
        const quantity = row.querySelector('[name="target_quantity"]');
        const unit = row.querySelector('[name="target_quantity_unit_code"]');
        const select = row.querySelector('select[name="recipe_revision_public_id"]');
        if (!quantity || !unit || !select) return;
        if (resetQuantity) {
            quantity.value = '';
            quantity.classList.remove('is-invalid');
            quantity.removeAttribute('aria-invalid');
        }
        const bound = Boolean(select.value);
        quantity.readOnly = !bound;
        const selectedOption = bound ? select.selectedOptions[0] : null;
        // An archived/unreadable-but-still-bound revision carries no metadata (data-readable="0");
        // its stored unit cannot be recomputed here, so the hidden field is left untouched
        // instead of clobbering a value the server correctly rendered. The unit always mirrors
        // the bound revision regardless of whether a quantity is typed yet (an empty quantity
        // makes the form parser ignore the unit anyway), so a NoJS user can type a brand-new
        // value into an already-bound row without any script keeping the pairing in sync.
        const metadataAvailable = Boolean(selectedOption && selectedOption.dataset.readable === '1');
        const code = metadataAvailable ? revisionUnitCode(select) : '';
        if (!bound) {
            unit.value = '';
        } else if (metadataAvailable) {
            unit.value = code;
        }
        const unitLabel = row.querySelector('[data-target-quantity-unit-label]');
        if (unitLabel) unitLabel.textContent = code ? ` (${unitDisplayNames[code] || code})` : '';
        const hint = row.querySelector('[data-target-quantity-hint]');
        if (hint) {
            const yieldParts = metadataAvailable ? (selectedOption.dataset.yield || '').split(' ') : [];
            const yieldUnit = yieldParts.length > 1 ? yieldParts.pop() : '';
            const yieldText = yieldUnit ? `${yieldParts.join(' ')} ${unitDisplayNames[yieldUnit] || yieldUnit}` : '';
            hint.textContent = !bound
                ? 'Nur mit gebundener Rezeptrevision verfügbar.'
                : yieldText
                    ? `leer = deklarierte Ausbeute (${yieldText}). Dezimalpunkt verwenden, z. B. 2.5.`
                    : 'Angaben zur deklarierten Ausbeute für diese Revision derzeit nicht verfügbar. Dezimalpunkt verwenden, z. B. 2.5.';
        }
    }

    forms.forEach(form => {
        syncMetadataControls(form);
        form.addEventListener('change', () => syncMetadataControls(form));
    });

    document.querySelectorAll('form[data-menu-editor]').forEach(form => {
        form.setAttribute('data-component-enhanced', '');
        let unitDisplayNames = {};
        try {
            unitDisplayNames = JSON.parse(form.dataset.unitDisplayNames || '{}');
        } catch { /* keep raw unit codes if the map failed to parse */ }
        form.querySelectorAll('.component-row').forEach(row => {
            row.querySelector('[data-component-summary-view]')?.removeAttribute('hidden');
            row.querySelector('[data-component-kind]')?.removeAttribute('hidden');
            row.querySelector('[data-finish-row]')?.removeAttribute('hidden');
            syncComponentRow(row);
            syncTargetQuantityField(row, unitDisplayNames);
        });
        const dirtyNote = document.querySelector('[data-menu-editor-dirty-note]');
        const markReviewDirty = () => dirtyNote?.classList.add('is-dirty');
        form.addEventListener('input', markReviewDirty);
        form.addEventListener('change', markReviewDirty);
        form.addEventListener('input', (e) => {
            const row = e.target.closest('.component-row');
            if (!row) return;
            syncComponentRow(row);
            if (e.target.matches('[data-target-quantity-input]')) syncTargetQuantityField(row, unitDisplayNames);
        });
        form.addEventListener('change', (e) => {
            const kindOption = e.target.closest('[data-component-kind-option]');
            const row = e.target.closest('.component-row');
            if (!row) return;
            if (kindOption) {
                row.querySelectorAll('[data-component-kind-option]').forEach(option => {
                    option.checked = option === kindOption;
                });
                const otherName = kindOption.value === 'catalog' ? 'component_text' : 'component_public_id';
                row.querySelector(`[name="${otherName}"]`).value = '';
            }
            syncComponentRow(row);
        });

        form.addEventListener('formdata', (e) => {
            for (const [selector, names] of [
                ['.component-row', [
                    'component_public_id', 'component_text', 'recipe_revision_public_id',
                    'target_quantity', 'target_quantity_unit_code',
                ]],
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

        form.addEventListener('input', (e) => {
            const search = e.target.closest('[data-recipe-search]');
            if (!search) return;
            const select = search.closest('[data-row]')?.querySelector('select[name="recipe_revision_public_id"]');
            if (!select) return;
            const query = search.value.trim().toLowerCase();
            select.querySelectorAll('option').forEach(option => {
                if (!option.value) return;
                const haystack = `${option.textContent || ''} ${option.dataset.yield || ''}`.toLowerCase();
                option.hidden = Boolean(query) && !haystack.includes(query) && !option.selected;
            });
            select.querySelectorAll('optgroup').forEach(group => {
                group.hidden = !Array.from(group.querySelectorAll('option')).some(option => !option.hidden);
            });
        });

        form.addEventListener('change', (e) => {
            const select = e.target.closest('select[name="recipe_revision_public_id"]');
            if (!select) return;
            const previous = select.getAttribute('data-previous-value') || '';
            if (previous && !select.value &&
                !window.confirm('Rezeptbindung für diese Komponente lösen? Die gespeicherte Revision bleibt unverändert, bis Sie bestätigen.')) {
                select.value = previous;
                return;
            }
            select.setAttribute('data-previous-value', select.value);
            const row = select.closest('.component-row');
            if (row) syncTargetQuantityField(row, unitDisplayNames, { resetQuantity: true });
        });

        form.addEventListener('click', (e) => {
            const addButton = e.target.closest('[data-add-row]');
            const removeButton = e.target.closest('[data-remove-row]');
            const moveButton = e.target.closest('[data-move-row]');
            const editButton = e.target.closest('[data-edit-row]');
            const finishButton = e.target.closest('[data-finish-row]');
            if (!addButton && !removeButton && !moveButton && !editButton && !finishButton) return;
            if (editButton) {
                setComponentRowEditing(editButton.closest('.component-row'), true);
                return;
            }
            if (finishButton) {
                const row = finishButton.closest('.component-row');
                setComponentRowEditing(row, false);
                row.querySelector('[data-edit-row]').focus();
                return;
            }
            let focusTarget;
            let list;
            if (addButton) {
                list = document.getElementById(addButton.dataset.addRow);
                const clone = list.lastElementChild.cloneNode(true);
                clone.querySelectorAll('input[name], select[name]').forEach(control => {
                    control.value = '';
                    control.classList.remove('is-invalid');
                    control.removeAttribute('aria-invalid');
                    if (control.matches('select[name="recipe_revision_public_id"]')) {
                        control.setAttribute('data-previous-value', '');
                    }
                    const descriptions = (control.getAttribute('aria-describedby') || '').split(/\s+/)
                        .filter(id => id && !document.getElementById(id)?.classList.contains('field-error'));
                    if (descriptions.length) control.setAttribute('aria-describedby', descriptions.join(' '));
                    else control.removeAttribute('aria-describedby');
                });
                clone.querySelectorAll('.field-error').forEach(error => error.remove());
                list.appendChild(clone);
                if (clone.matches('.component-row')) {
                    clone.classList.add('is-editing');
                    clone.querySelectorAll('[data-component-kind-option]').forEach(option => {
                        option.checked = option.value === 'catalog';
                    });
                    syncComponentRow(clone);
                    syncTargetQuantityField(clone, unitDisplayNames, { resetQuantity: true });
                    focusTarget = clone.querySelector('[name="component_public_id"]');
                } else {
                    focusTarget = clone.querySelector('input, select');
                }
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
                    focusTarget = list.lastElementChild.querySelector('[data-edit-row], input, select');
                } else {
                    row.querySelectorAll('input[name], select[name]').forEach(control => {
                        control.value = '';
                        if (control.matches('select[name="recipe_revision_public_id"]')) {
                            control.setAttribute('data-previous-value', '');
                        }
                    });
                    if (row.matches('.component-row')) {
                        row.querySelectorAll('[data-component-kind-option]').forEach(option => {
                            option.checked = option.value === 'catalog';
                        });
                        setComponentRowEditing(row, true);
                        syncTargetQuantityField(row, unitDisplayNames, { resetQuantity: true });
                    }
                    focusTarget = row.querySelector('[name="component_public_id"], input, select');
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
    document.querySelectorAll('form[data-menu-editor] [data-sticky], [data-sticky-form]').forEach(stickyBar => {
        const form = stickyBar.dataset.stickyForm
            ? document.getElementById(stickyBar.dataset.stickyForm)
            : stickyBar.closest('form');
        if (!form) return;
        const viewport = window.visualViewport;
        const syncSticky = () => {
            const height = viewport ? viewport.height : window.innerHeight;
            stickyBar.classList.toggle('is-static', height < 700
                || height < window.innerHeight - 120 || stickyBar.offsetHeight > height / 3);
        };
        stickyBar.dataset.stickyReady = 'true';
        if (viewport) viewport.addEventListener('resize', syncSticky);
        window.addEventListener('resize', syncSticky);
        syncSticky();
        document.addEventListener('focusin', (e) => {
            if (!form.contains(e.target) || stickyBar.contains(e.target)) return;
            window.requestAnimationFrame(() => {
                if (getComputedStyle(stickyBar).position !== 'sticky') return;
                const bar = stickyBar.getBoundingClientRect();
                const field = e.target.getBoundingClientRect();
                if (stickyBar.dataset.stickyEdge === 'top') {
                    if (bar.top <= 0 && field.top < bar.bottom) {
                        window.scrollBy(0, field.top - bar.bottom - 8);
                    }
                } else if (bar.top < window.innerHeight && field.bottom > bar.top) {
                    window.scrollBy(0, field.bottom - bar.top + 8);
                }
            });
        });
    });

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
