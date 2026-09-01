BEGIN;
SET search_path TO cafeteria, public;

INSERT INTO application_roles(role_code, display_name, description)
VALUES
    ('Cafeteria.Editor', 'Redaktion', 'Erfasst beide Wochenraster, validiert und importiert CSV.'),
    ('Cafeteria.Publisher', 'Redaktion und Publikation', 'Kann erfassen, prüfen, publizieren und zurückziehen.'),
    ('Cafeteria.Admin', 'Administration', 'Verwaltet Stammdaten, Rollenabbildung und Betriebseinstellungen.')
ON CONFLICT (role_code) DO UPDATE
SET display_name = EXCLUDED.display_name,
    description = EXCLUDED.description,
    active = true;

INSERT INTO users(public_id, auth_provider, display_name, last_seen_roles)
VALUES
    ('00000000-0000-0000-0000-000000000001', 'system', 'System', '[]'::jsonb),
    ('00000000-0000-0000-0000-000000000002', 'demo', 'Demo Küche', '["Cafeteria.Editor","Cafeteria.Publisher"]'::jsonb)
ON CONFLICT (public_id) DO UPDATE
SET display_name = EXCLUDED.display_name,
    last_seen_roles = EXCLUDED.last_seen_roles,
    disabled_at = NULL;

INSERT INTO locations(code, name, timezone)
VALUES ('KIRCHLINDACH', 'Klinik Südhang Kirchlindach', 'Europe/Zurich')
ON CONFLICT (code) DO UPDATE SET name = EXCLUDED.name, timezone = EXCLUDED.timezone, active = true;

INSERT INTO offer_profiles(code, display_name, allows_prices, allows_weekend, allowed_meals)
VALUES
    ('patient', 'Patientinnen und Patienten', false, true, ARRAY['LUNCH','DINNER']::text[]),
    ('staff_guest', 'Mitarbeitende und externe Gäste', true, false, ARRAY['LUNCH']::text[])
ON CONFLICT (code) DO UPDATE
SET display_name = EXCLUDED.display_name,
    allows_prices = EXCLUDED.allows_prices,
    allows_weekend = EXCLUDED.allows_weekend,
    allowed_meals = EXCLUDED.allowed_meals;

INSERT INTO meal_periods(code, display_name, sort_order)
VALUES ('LUNCH', 'Mittag', 10), ('DINNER', 'Abend', 20)
ON CONFLICT (code) DO UPDATE SET display_name = EXCLUDED.display_name, sort_order = EXCLUDED.sort_order;

INSERT INTO menu_types(code, display_name, sort_order)
VALUES ('MENU_1', 'Menü 1', 10), ('VEGGIE', 'Vegetarisch', 20)
ON CONFLICT (code) DO UPDATE SET display_name = EXCLUDED.display_name, sort_order = EXCLUDED.sort_order;

INSERT INTO dietary_labels(code, display_name)
VALUES
    ('VEGETARIAN', 'Vegetarisch'),
    ('VEGAN', 'Vegan'),
    ('LACTOSE_FREE', 'Laktosefrei'),
    ('GLUTEN_FREE', 'Glutenfrei')
ON CONFLICT (code) DO UPDATE SET display_name = EXCLUDED.display_name, active = true;

INSERT INTO allergens(code, display_name, eu_number)
VALUES
    ('GLUTEN', 'Glutenhaltiges Getreide', 1),
    ('CRUSTACEANS', 'Krebstiere', 2),
    ('EGGS', 'Eier', 3),
    ('FISH', 'Fisch', 4),
    ('PEANUTS', 'Erdnüsse', 5),
    ('SOY', 'Soja', 6),
    ('MILK', 'Milch', 7),
    ('NUTS', 'Schalenfrüchte', 8),
    ('CELERY', 'Sellerie', 9),
    ('MUSTARD', 'Senf', 10),
    ('SESAME', 'Sesam', 11),
    ('SULPHITES', 'Schwefeldioxid und Sulfite', 12),
    ('LUPIN', 'Lupinen', 13),
    ('MOLLUSCS', 'Weichtiere', 14)
ON CONFLICT (code) DO UPDATE
SET display_name = EXCLUDED.display_name, eu_number = EXCLUDED.eu_number, active = true;

INSERT INTO user_role_cache(user_id, role_code, source)
SELECT u.id, r.role_code, 'demo'
FROM users u
JOIN application_roles r ON r.role_code IN ('Cafeteria.Editor', 'Cafeteria.Publisher')
WHERE u.public_id = '00000000-0000-0000-0000-000000000002'
ON CONFLICT (user_id, role_code) DO UPDATE SET source = 'demo', last_seen_at = clock_timestamp();

INSERT INTO settings(location_id, profile_id, setting_key, setting_value, updated_by)
SELECT l.id, p.id, 'signage.refresh_seconds', '300'::jsonb, u.id
FROM locations l
CROSS JOIN offer_profiles p
CROSS JOIN users u
WHERE l.code = 'KIRCHLINDACH'
  AND u.public_id = '00000000-0000-0000-0000-000000000001'
ON CONFLICT (location_id, profile_id, setting_key) DO UPDATE
SET setting_value = EXCLUDED.setting_value, updated_by = EXCLUDED.updated_by, updated_at = clock_timestamp();

COMMIT;
