/* === Admin-Redesign === */
(function() {
    'use strict';

    // Opt-in native submissions: defer disabling until successful controls have
    // been serialized, including the clicked submitter's name/value and overrides.
    const loadingForms = new Map();
    // ARIA keeps unavailable actions focusable so their description is reachable.
    ['click', 'auxclick', 'keydown'].forEach(type => document.addEventListener(type, event => {
        if (type === 'keydown' && !['Enter', ' '].includes(event.key)) return;
        if (!event.target.closest('[aria-disabled="true"]')) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true));
    document.addEventListener('submit', event => {
        if (!event.submitter?.matches('[aria-disabled="true"]')) return;
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);
    document.addEventListener('submit', event => {
        const form = event.target;
        if (!form.matches('form[data-loading]') || event.defaultPrevented || form.dataset.loading === 'false') return;
        if (form.method === 'dialog') return;
        if (loadingForms.has(form)) {
            event.preventDefault();
            return;
        }
        const button = event.submitter || Array.from(form.elements).find(control =>
            control.matches('button[type="submit"], button:not([type])') && !control.disabled);
        if (!button) return;
        const state = {button, busy: button.getAttribute('aria-busy'),
            spinner: button.classList.contains('admin-btn-loading')};
        loadingForms.set(form, state);
        window.setTimeout(() => {
            if (loadingForms.get(form) !== state) return;
            if (event.defaultPrevented || !form.isConnected) {
                loadingForms.delete(form);
                return;
            }
            button.disabled = true;
            button.setAttribute('aria-busy', 'true');
            button.classList.add('admin-btn-loading');
        }, 0);
    });
    window.addEventListener('pageshow', () => {
        loadingForms.forEach(({button, busy, spinner}) => {
            button.disabled = false;
            if (busy === null) button.removeAttribute('aria-busy');
            else button.setAttribute('aria-busy', busy);
            if (!spinner) button.classList.remove('admin-btn-loading');
        });
        loadingForms.clear();
    });
    // Native details remain usable without JS; enhancement never executes items.
    document.addEventListener('toggle', event => {
        const menu = event.target;
        if (!menu.matches('.ui-sem-actions') || !menu.open) return;
        // toggle is queued: do not steal focus after the user has already moved on.
        if (document.activeElement !== menu.querySelector(':scope > summary')) return;
        Array.from(menu.querySelectorAll('.ui-sem-action-items :is(a[href], button):not(:disabled)'))
            .find(control => control.getClientRects().length && !control.closest('[hidden], [inert]'))?.focus();
    }, true);
    // Legacy HTML filter slots gain chips from their rendered successful controls.
    // Explicit chips remain server-owned and work without JavaScript.
    document.querySelectorAll('.admin-filter-bar[data-filter-remove-label]').forEach(form => {
        if (form.querySelector('[data-filter-chips="explicit"]')) return;
        const panel = form.querySelector('.admin-filter-slots');
        if (!panel) return;
        const selected = Array.from(panel.querySelectorAll('input[name], select[name]')).filter(control => {
            if (control.disabled || ['hidden', 'submit', 'button'].includes(control.type)) return false;
            if (['checkbox', 'radio'].includes(control.type)) return control.checked;
            if (control.tagName === 'SELECT') return control.selectedIndex > 0;
            return control.value.trim() !== '';
        });
        const count = form.querySelector('.admin-filter-count');
        if (count && !count.hasAttribute('data-filter-count-explicit')) {
            count.textContent = selected.length;
            count.hidden = !selected.length;
            if (selected.length) count.parentElement.setAttribute('aria-describedby', count.id);
        }
        if (!selected.length) return;
        const chips = document.createElement('div');
        chips.className = 'admin-filter-chips';
        selected.forEach(control => {
            const chip = document.createElement('button');
            chip.type = 'button';
            chip.className = 'btn admin-filter-chip';
            const label = control.tagName === 'SELECT' ? control.selectedOptions[0].textContent
                : ['checkbox', 'radio'].includes(control.type) ? control.labels?.[0]?.textContent : control.value;
            chip.textContent = (label || control.name).trim();
            chip.setAttribute('aria-label', chip.textContent + ': ' + form.dataset.filterRemoveLabel);
            const removeIcon = form.querySelector('[data-filter-chip-icon]');
            if (removeIcon) chip.append(removeIcon.content.cloneNode(true));
            chip.addEventListener('click', () => {
                if (['checkbox', 'radio'].includes(control.type)) control.checked = false;
                else if (control.tagName === 'SELECT') control.selectedIndex = 0;
                else control.value = '';
                form.requestSubmit();
            });
            chips.append(chip);
        });
        form.append(chips);
    });

    // Optional modal enhancement; without JS the open dialog lives in details.
    document.querySelectorAll('.admin-hint[data-hint-mode="dialog"]').forEach(details => {
        const dialog = details.querySelector('dialog');
        const trigger = details.querySelector('summary');
        const close = details.querySelector('[data-hint-close]');
        if (!dialog || typeof dialog.showModal !== 'function') return;
        dialog.removeAttribute('open');
        close.hidden = false;
        trigger.addEventListener('click', event => {
            event.preventDefault();
            details.open = true;
            dialog.showModal();
        });
        close.addEventListener('click', () => dialog.close());
        dialog.addEventListener('close', () => {
            details.open = false;
            trigger.focus();
        });
    });

    // One Tabler tooltip per action. Text stays text, including record names.
    const iconActions = new Set(document.querySelectorAll('[data-admin-icon-action]'));
    const escapeFocus = new WeakSet();
    function focusAfterEscape(control) {
        if (control && document.activeElement !== control && iconActions.has(control)) escapeFocus.add(control);
        control?.focus();
    }
    function actionTooltip(link) {
        return (link.getAttribute('aria-describedby') || '').split(/\s+/)
            .map(id => document.getElementById(id)).find(node => node?.getAttribute('role') === 'tooltip');
    }
    function bindActionTooltip(link) {
        let description = link.getAttribute('aria-describedby');
        link.addEventListener('show.bs.tooltip', event => {
            if (escapeFocus.has(link)) {
                event.preventDefault();
                return;
            }
            description = link.getAttribute('aria-describedby');
        });
        link.addEventListener('blur', () => escapeFocus.delete(link));
        link.addEventListener('mouseenter', () => {
            // A fresh hover may explain the action even while returned focus stays here.
            if (escapeFocus.delete(link)) window.tabler.Tooltip.getInstance(link)?.show();
        });
        link.addEventListener('keydown', event => {
            if (event.target !== link || !link.matches('summary') || !['Enter', ' '].includes(event.key)) return;
            // Native keyboard activation is deliberate even when focus never left.
            if (escapeFocus.delete(link)) window.tabler.Tooltip.getInstance(link)?.show();
        });
        link.addEventListener('inserted.bs.tooltip', () => {
            const tip = actionTooltip(link);
            if (!tip) return;
            tip.classList.add('ui-sem-tooltip');
            tip.addEventListener('mouseleave', () => {
                if (!link.matches(':hover, :focus')) window.tabler.Tooltip.getInstance(link).hide();
            });
            if (description) link.setAttribute('aria-describedby', description + ' ' + tip.id);
        });
        link.addEventListener('hidden.bs.tooltip', () => {
            if (description) link.setAttribute('aria-describedby', description);
        });
        link.addEventListener('hide.bs.tooltip', event => {
            const tip = actionTooltip(link);
            description = (link.getAttribute('aria-describedby') || '').split(/\s+/)
                .filter(id => id && id !== tip?.id).join(' ');
            if (tip?.matches(':hover') && !tip.dataset.dismissed) event.preventDefault();
        });
    }
    iconActions.forEach(bindActionTooltip);
    function initSemanticTooltip(link) {
        if (!link || iconActions.has(link) || !window.tabler?.Tooltip) return;
        iconActions.add(link);
        bindActionTooltip(link);
        new window.tabler.Tooltip(link, {
            title: () => link.getAttribute('data-ui-tooltip'),
            html: false, trigger: 'hover focus', animation: false,
            // A lateral fallback covers adjacent actions in compact toolbars.
            placement: 'top', fallbackPlacements: ['bottom'],
            delay: {show: 0, hide: 150}, offset: [0, 0],
            container: link.closest('dialog') || document.body,
            customClass: 'ui-sem-tooltip',
        });
    }
    document.querySelectorAll('[data-ui-tooltip]').forEach(initSemanticTooltip);
    // Cloned editor rows get the same enhancement on their first interaction.
    ['mouseover', 'focusin'].forEach(type => document.addEventListener(type, event => {
        const link = event.target.closest('[data-ui-tooltip]');
        if (!link || iconActions.has(link)) return;
        initSemanticTooltip(link);
        window.tabler?.Tooltip.getInstance(link)?.show();
    }));
    // Dismiss the focused action or its own disclosure's summary before closing it.
    // Unrelated hover tips must still let native and Tabler modals handle Escape.
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        const details = event.target.closest('.modal, dialog') ? null : event.target.closest('details[open]');
        const summary = details?.querySelector(':scope > summary');
        let dismissedOwned = false;
        iconActions.forEach(link => {
            const tip = actionTooltip(link);
            if (!tip?.classList.contains('show') || !tip.getClientRects().length) return;
            tip.dataset.dismissed = 'true';
            window.tabler.Tooltip.getInstance(link).hide();
            if (link.contains(event.target) || tip.contains(event.target) || link === summary) dismissedOwned = true;
        });
        if (dismissedOwned) {
            event.preventDefault();
            event.stopImmediatePropagation();
        }
    }, true);
    document.addEventListener('keydown', event => {
        if (event.key !== 'Escape') return;
        const menu = event.target.closest('.ui-sem-actions[open], .admin-filter-more[open]');
        if (!menu) return;
        menu.open = false;
        focusAfterEscape(menu.querySelector(':scope > summary'));
        event.preventDefault();
        event.stopImmediatePropagation();
    }, true);

    // 1. Dirty-Tracking
    const forms = document.querySelectorAll('form:not([data-dirty-tracking="off"])');
    let isDirty = false;

    // Confirm before dirty-state clearing and the document's loading listener.
    document.querySelectorAll('form').forEach(form => {
        form.addEventListener('submit', event => {
            if (event.defaultPrevented) return;
            const confirmation = event.submitter?.getAttribute('data-confirm') || form.getAttribute('data-confirm');
            if (confirmation && !window.confirm(confirmation)) event.preventDefault();
        });
    });

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
        let flashRegion = document.querySelector('.flash-region');
        if (!flashRegion && (previewLinks.length || publishForms.length)) {
            flashRegion = document.createElement('p');
            flashRegion.className = 'flash-region';
            (document.querySelector('main') || document.body).prepend(flashRegion);
        }
        if (flashRegion) {
            if (!flashRegion.id) flashRegion.id = 'admin-dirty-action-reason';
            flashRegion.textContent = 'Zuerst speichern';
        }
        const describe = control => {
            const ids = new Set((control.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean));
            ids.add(flashRegion.id);
            control.setAttribute('aria-describedby', Array.from(ids).join(' '));
        };

        previewLinks.forEach(link => {
            link.setAttribute('aria-disabled', 'true');
            describe(link);
            link.classList.add('disabled');
            link.addEventListener('click', preventDefaultClick);
            if (!link.classList.contains('ui-sem-control--icon-only')) link.textContent = 'Zuerst speichern';
        });

        publishForms.forEach(form => {
            const btn = form.querySelector('button[type="submit"]');
            if (btn) {
                btn.setAttribute('disabled', 'true');
                describe(btn);
                if (!btn.classList.contains('ui-sem-control--icon-only')) btn.textContent = 'Zuerst speichern';
            }
        });

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

    const detailTriggers = new WeakMap();
    document.addEventListener('toggle', event => {
        if (!event.target.open) detailTriggers.delete(event.target);
    }, true);
    // Native accordions: reveal every closed ancestor before a field is focused.
    function revealAncestors(element) {
        for (let details = element && element.closest('details'); details; details = details.parentElement.closest('details')) {
            details.open = true;
        }
        const componentRow = element && element.closest('.component-row');
        if (componentRow) setComponentRowEditing(componentRow, true);
    }

    // Disclosures retain their controls and show errors even after being closed again.
    let detailsErrorSequence = 0;
    function syncDetailsErrors() {
        document.querySelectorAll('details').forEach(details => {
            const summary = details.querySelector(':scope > summary');
            if (!summary || summary.hidden) return;
            const invalid = details.querySelector('[aria-invalid="true"]:not(:disabled):not([type="hidden"]), [data-admin-native-invalid]');
            let badge = summary.querySelector('[data-admin-details-error]');
            if (invalid && !badge) {
                const template = summary.matches('.ui-sem-control--icon-only')
                    ? document.getElementById('admin-details-error-template') : null;
                badge = template ? template.content.firstElementChild.cloneNode(true) : document.createElement('span');
                badge.dataset.adminDetailsError = '';
                badge.classList.add('text-danger');
                if (template) {
                    badge.classList.add('ui-sem-summary-error');
                    badge.querySelector('span').classList.add('visually-hidden');
                    do { badge.id = 'admin-details-error-' + ++detailsErrorSequence; }
                    while (document.getElementById(badge.id));
                    const descriptions = (summary.getAttribute('aria-describedby') || '').split(/\s+/).filter(Boolean);
                    summary.setAttribute('aria-describedby', [...descriptions, badge.id].join(' '));
                } else badge.textContent = ' · Fehler';
                summary.append(badge);
            } else if (!invalid && badge) {
                if (badge.classList.contains('ui-sem-summary-error')) {
                    const descriptions = (summary.getAttribute('aria-describedby') || '').split(/\s+/)
                        .filter(id => id && id !== badge.id);
                    if (descriptions.length) summary.setAttribute('aria-describedby', descriptions.join(' '));
                    else summary.removeAttribute('aria-describedby');
                }
                badge.remove();
            }
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
            const details = target.closest('details');
            if (details && !details.contains(link)) detailTriggers.set(details, link);
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
    function syncMetadataControls(form, changedControl = null) {
        const menuEditor = form.matches('[data-menu-editor]');
        const manual = name => !menuEditor ||
            form.querySelector(`input[name="${name}_mode"]:checked`)?.value === 'manual';
        form.querySelectorAll('.allergen-row, [data-option-detail]').forEach(row => {
            const checkbox = row.querySelector('[data-option-check], input[name="allergen_code"]');
            const presence = row.querySelector('[data-option-presence], select[name^="allergen_presence__"]');
            if (checkbox && presence) {
                const group = row.closest('[data-option-group]');
                const mode = group?.dataset.optionMode || 'allergen';
                const modeControl = form.querySelector(`input[name="${mode}_mode"]:checked`);
                const editable = group
                    ? (modeControl ? modeControl.value === 'manual' : group.dataset.optionManual === 'true')
                    : manual('allergen');
                if (row.hasAttribute('data-option-keyed')) {
                    checkbox.hidden = false;
                    if (changedControl === presence) {
                        checkbox.checked = presence.value !== 'absent';
                        if (!checkbox.checked) checkbox.focus();
                    }
                    if (checkbox.checked && presence.value === 'absent') presence.value = 'contains';
                    row.querySelector('[data-option-absent]').disabled = !editable || checkbox.checked;
                }
                checkbox.disabled = !editable;
                presence.disabled = checkbox.disabled || (row.hasAttribute('data-option-keyed') && !checkbox.checked);
                presence.hidden = !checkbox.checked || !editable;
                presence.classList.toggle('d-none', presence.hidden);
            }
        });
        form.querySelectorAll('[data-option-group]').forEach(group => {
            const count = group.querySelectorAll('[data-option-check]:checked').length;
            group.querySelector('[data-option-count]').textContent = `${count} ausgewählt`;
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
        form.addEventListener('change', event => syncMetadataControls(form, event.target));
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
                // Tooltip nodes belong to the original control, never to its clone.
                clone.querySelectorAll('[data-ui-tooltip][aria-describedby]').forEach(control => {
                    const descriptions = control.getAttribute('aria-describedby').split(/\s+/)
                        .filter(id => {
                            const node = document.getElementById(id);
                            return node && node.getAttribute('role') !== 'tooltip';
                        });
                    if (descriptions.length) control.setAttribute('aria-describedby', descriptions.join(' '));
                    else control.removeAttribute('aria-describedby');
                });
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
                    // Body-mounted tooltips must not outlive their removed controls.
                    iconActions.forEach(link => {
                        if (!row.contains(link)) return;
                        window.tabler?.Tooltip?.getInstance(link)?.dispose();
                        iconActions.delete(link);
                    });
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

    // Sticky save bar: return to the flow while a virtual keyboard shrinks the visual viewport,
    // and keep focused controls clear of the bar.
    document.querySelectorAll('form[data-menu-editor] [data-sticky], [data-sticky-form], .admin-form-footer[data-sticky]').forEach(stickyBar => {
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
        let pointerId = null;
        let releaseFrame = 0;
        const revealFocus = () => {
            const active = document.activeElement;
            if (pointerId !== null || !form.contains(active) || stickyBar.contains(active)
                || getComputedStyle(stickyBar).position !== 'sticky') return;
            const bar = stickyBar.getBoundingClientRect();
            const field = active.getBoundingClientRect();
            if (stickyBar.dataset.stickyEdge === 'top') {
                if (bar.top <= 0 && field.top < bar.bottom) {
                    window.scrollBy(0, field.top - bar.bottom - 8);
                }
            } else if (bar.top < window.innerHeight && field.bottom > bar.top) {
                window.scrollBy(0, field.bottom - bar.top + 8);
            }
        };
        // Native focus changes between pointerdown and click must not move the target.
        document.addEventListener('pointerdown', (e) => {
            if (!e.isPrimary || e.button !== 0) return;
            window.cancelAnimationFrame(releaseFrame);
            pointerId = e.pointerId;
            stickyBar.dataset.stickyPointerPosition = getComputedStyle(stickyBar).position;
        }, true);
        const releasePointer = (e) => {
            if (pointerId === null || (e && e.pointerId !== pointerId)) return;
            window.cancelAnimationFrame(releaseFrame);
            // Keep the mode through the native click, including touch compatibility events.
            releaseFrame = window.requestAnimationFrame(() => {
                pointerId = null;
                delete stickyBar.dataset.stickyPointerPosition;
                revealFocus();
            });
        };
        window.addEventListener('pointerup', releasePointer, true);
        window.addEventListener('pointercancel', releasePointer, true);
        window.addEventListener('blur', () => releasePointer());
        document.addEventListener('focusin', () => {
            window.requestAnimationFrame(revealFocus);
        });
    });

    document.addEventListener('keydown', (e) => {
        if (e.key === 'Escape') {
            if (e.defaultPrevented || e.target.closest('.modal, dialog')) return;
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
                const trigger = detailTriggers.get(details) || details.querySelector(':scope > summary');
                detailTriggers.delete(details);
                details.removeAttribute('open');
                focusAfterEscape(trigger);
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

document.querySelectorAll('form[data-autosubmit]').forEach(form => {
    form.addEventListener('change', () => {
        if (typeof form.requestSubmit === 'function') form.requestSubmit();
        else form.submit();
    });
});
