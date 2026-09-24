# UI consistency inventory — P4 migration queue

Static source counts across all templates; runtime branches and dynamic labels
need rendered review. Public/signage entries are inventory, not migration permission.
Zero rows retained so every template is accounted for.

Categories: literal buttons, long labels (>2 words or >18 characters), legacy labels,
wrong canonical icons, local tables/row lists, local filter/search forms.

Update after reviewed reductions: `rtk python3 tools/ui_consistency_inventory.py --update-baseline`.
Existing ceilings only decrease; regressions refuse the update. New templates start at zero.

| Template | literal_buttons | long_labels | legacy_labels | wrong_icons | local_lists | local_filters |
|---|---:|---:|---:|---:|---:|---:|
| _brand_logo.html | 0 | 0 | 0 | 0 | 0 | 0 |
| _food_symbols.html | 0 | 0 | 0 | 0 | 0 | 0 |
| _menu_image.html | 0 | 0 | 0 | 0 | 0 | 0 |
| _menu_metadata.html | 0 | 0 | 1 | 0 | 0 | 0 |
| admin/_area_tabs.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_country_select.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/_course_editor.html | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/_course_line.html | 2 | 0 | 2 | 1 | 0 | 0 |
| admin/_course_recipe_search.html | 3 | 0 | 0 | 0 | 0 | 1 |
| admin/_local_user_forms.html | 0 | 0 | 1 | 0 | 0 | 0 |
| admin/_macros.html | 3 | 1 | 1 | 1 | 0 | 0 |
| admin/_recipe_document.html | 2 | 1 | 0 | 0 | 0 | 0 |
| admin/_recipe_template_selection.html | 10 | 6 | 0 | 0 | 1 | 3 |
| admin/_rezepte_fields.html | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/_service_courses.html | 0 | 0 | 1 | 0 | 0 | 0 |
| admin/_week_controls.html | 6 | 2 | 0 | 0 | 0 | 0 |
| admin/_week_menu_card.html | 1 | 1 | 5 | 0 | 0 | 0 |
| admin/_week_service.html | 1 | 1 | 1 | 0 | 0 | 0 |
| admin/_week_settings.html | 1 | 1 | 0 | 0 | 0 | 0 |
| admin/_workflow_sidebar.html | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/access_history.html | 3 | 1 | 0 | 1 | 1 | 1 |
| admin/api.html | 4 | 1 | 2 | 0 | 2 | 0 |
| admin/base_tabler.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/bestellung.html | 0 | 0 | 0 | 0 | 3 | 0 |
| admin/bestellung_korb.html | 0 | 0 | 0 | 0 | 1 | 0 |
| admin/branding_editor.html | 3 | 2 | 4 | 0 | 1 | 0 |
| admin/branding_preview.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/cafeteria.html | 1 | 1 | 1 | 0 | 0 | 0 |
| admin/component_editor.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/components.html | 0 | 0 | 2 | 0 | 1 | 1 |
| admin/copy.html | 2 | 1 | 0 | 0 | 0 | 0 |
| admin/display_settings.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/einkaufsliste.html | 6 | 0 | 0 | 0 | 2 | 2 |
| admin/einkaufslisten.html | 1 | 1 | 0 | 0 | 0 | 0 |
| admin/gerichtvorlage_einplanen.html | 5 | 2 | 0 | 0 | 0 | 0 |
| admin/gerichtvorlagen.html | 7 | 2 | 2 | 0 | 1 | 0 |
| admin/grundlagen.html | 0 | 0 | 1 | 0 | 1 | 1 |
| admin/grundlagen_food.html | 4 | 1 | 0 | 0 | 0 | 1 |
| admin/grundlagen_location_conflict.html | 2 | 0 | 0 | 0 | 0 | 0 |
| admin/grundlagen_unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/grundlagen_unit.html | 1 | 0 | 0 | 0 | 0 | 0 |
| admin/grundlagen_vocabulary.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/import_preview.html | 2 | 2 | 0 | 0 | 0 | 0 |
| admin/kalkulation.html | 0 | 0 | 0 | 0 | 1 | 0 |
| admin/kochbuch_editor.html | 0 | 0 | 0 | 0 | 1 | 0 |
| admin/kochbuecher.html | 0 | 0 | 0 | 0 | 1 | 1 |
| admin/kuechenkalender.html | 3 | 0 | 0 | 0 | 1 | 0 |
| admin/kuechenkalender_anlass.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/lager.html | 0 | 0 | 1 | 0 | 1 | 0 |
| admin/local_user_create.html | 1 | 1 | 0 | 0 | 0 | 0 |
| admin/local_user_editor.html | 4 | 3 | 3 | 0 | 0 | 0 |
| admin/local_user_events.html | 2 | 1 | 0 | 0 | 1 | 0 |
| admin/local_user_unavailable.html | 1 | 1 | 0 | 0 | 0 | 0 |
| admin/local_users.html | 2 | 0 | 1 | 0 | 1 | 1 |
| admin/menu_collection.html | 5 | 0 | 0 | 2 | 1 | 0 |
| admin/menu_editor.html | 17 | 6 | 1 | 1 | 0 | 1 |
| admin/operations.html | 1 | 0 | 1 | 0 | 3 | 0 |
| admin/patienten.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/preview.html | 3 | 3 | 0 | 0 | 0 | 0 |
| admin/print_template_editor.html | 19 | 11 | 1 | 0 | 1 | 1 |
| admin/print_template_unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/recipe_template_error.html | 1 | 1 | 0 | 0 | 0 | 0 |
| admin/rezepte.html | 4 | 2 | 1 | 0 | 1 | 1 |
| admin/rezepte_ansicht.html | 4 | 1 | 0 | 0 | 0 | 0 |
| admin/rezepte_conflict.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/rezepte_editor.html | 9 | 2 | 0 | 0 | 0 | 0 |
| admin/rezepte_images.html | 3 | 1 | 0 | 0 | 1 | 0 |
| admin/rezepte_import.html | 4 | 3 | 0 | 0 | 1 | 0 |
| admin/rezepte_revision.html | 3 | 0 | 0 | 0 | 0 | 0 |
| admin/rezepte_revisionen.html | 2 | 1 | 0 | 0 | 2 | 0 |
| admin/rezepte_scale.html | 2 | 0 | 0 | 0 | 1 | 0 |
| admin/screen_template_assignment.html | 2 | 2 | 0 | 0 | 0 | 0 |
| admin/screen_template_unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 |
| admin/screens.html | 1 | 0 | 1 | 0 | 0 | 0 |
| admin/vorlagen.html | 17 | 11 | 6 | 0 | 2 | 1 |
| admin/week_management.html | 3 | 2 | 0 | 0 | 1 | 0 |
| admin/week_review.html | 2 | 2 | 0 | 0 | 0 | 0 |
| api/docs.html | 0 | 0 | 0 | 0 | 0 | 0 |
| auth/error.html | 1 | 1 | 0 | 0 | 0 | 0 |
| auth/local_login.html | 0 | 0 | 0 | 0 | 0 | 0 |
| base.html | 0 | 0 | 0 | 0 | 0 | 0 |
| public/base_public.html | 1 | 1 | 0 | 0 | 0 | 0 |
| public/cafeteria_today.html | 2 | 1 | 1 | 0 | 0 | 0 |
| public/cafeteria_week.html | 2 | 0 | 1 | 0 | 0 | 0 |
| public/legend.html | 0 | 0 | 0 | 0 | 0 | 0 |
| public/patient_today.html | 2 | 1 | 1 | 0 | 0 | 0 |
| public/patient_week.html | 2 | 0 | 1 | 0 | 0 | 0 |
| public/print_cafeteria_week.html | 0 | 0 | 0 | 0 | 0 | 0 |
| public/print_patient_week.html | 0 | 0 | 0 | 0 | 0 | 0 |
| public/unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/base_signage.html | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/cafeteria_closed.html | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/cafeteria_day.html | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/cafeteria_week.html | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/patient_day.html | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/patient_week.html | 0 | 0 | 0 | 0 | 0 | 0 |
| signage/unavailable.html | 0 | 0 | 0 | 0 | 0 | 0 |
| ui/_semantic.html | 0 | 0 | 0 | 0 | 0 | 0 |
| **TOTAL** | 198 | 85 | 44 | 6 | 35 | 16 |
