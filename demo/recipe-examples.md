# Rezept-Beispieldaten KW36 — Import-Übergabe

Stand 2026-09-07, WP `wp-2f15cfd4e437`. **Nicht importiert, nicht publiziert.**
Die Datei `demo/recipe_examples.json` ist ein additiver, idempotenter Handoff.
Root führt den Import über die bestehenden authentifizierten Admin-Formulare
nach geprüftem Schema- und A2/A3/A4/A5-Wiring aus. Zwei DRAFT-Wochen benötigen
keinen Publikationsentscheid; Veröffentlichung bleibt separat offen.

Validiert DB-frei mit `tools/validate_recipe_examples.py` gegen die echten Parser
`recipe_payload`, `parse_quantity`, `Unit`, `plain`/`code`/`factor` und
`build_snapshot`.

## Validierte Zählung

| Entität | Anzahl |
|---|---:|
| Einheiten (Seed, skip_if_exists) | 9 |
| food_categories | 10 |
| tags | 18 |
| foods | 54 |
| recipes | 18 |
| recipe_revision_intents (`freeze_revision`) | 18 |
| cookbooks | 3 |
| weekly_drafts | 2 |
| menu_recipe_intents | 38 |
| unresolved_gaps | 6 |

Status im Datensatz: `examples_only_not_imported_not_published`.
`imported=false`, `published=false`.

## Wiederverwendete Rezept- und Menünamen

Quelle: `demo/snapshots/cafeteria_kw36.json` und
`demo/snapshots/patienten_kw36.json` (unverändert, Schema 2).

Cafeteria Mo–Fr, identische Titel und Beilagen:

- Pouletbrust an Kräutersauce / Spinat-Ricotta-Ravioli
- Rindsgeschnetzeltes Stroganoff / Kichererbsen-Curry
- Kalbsbratwurst mit Zwiebelsauce / Gemüse-Lasagne
- Schweinsragout Tessiner Art / Polenta mit Pilzragout
- Gebratenes Zanderfilet / Falafel-Teller

Patienten, soweit im 18er-Satz:

- Pouletgeschnetzeltes Paprika / Gemüsegeschnetzeltes
- Kartoffelsuppe mit Wienerli / Kartoffelsuppe mit Kräutern
- Rührei mit Kräutern / Tofu-Rührei
- Griessbrei mit Zwetschgenkompott / Kokos-Griessbrei

Übrige Patiententage wiederverwenden Cafeteria-Rezepte. Die Snapshot-Titel
Ofen-Pouletschenkel, Kichererbsen-Eintopf, Gerstensuppen, Rindsschmorbraten,
Nussbraten, Pastetli, Hackbraten, Linsenbraten, Toasts und Älplermagronen
sind **nicht** in diesem Satz; der Entwurf ersetzt sie bewusst, damit jedes
offene Menü auf ein geliefertes Rezept zeigt.

## Kochbücher (Reihenfolge verbindlich)

1. `Beispiel: Cafeteria-Mittag KW36` — 10 Rezepte, Mo–Fr MENU_1/VEGGIE.
2. `Beispiel: Patienten-Ergänzung KW36` — 8 patientenspezifische Rezepte.
3. `Beispiel: Vegetarisch und vegan` — 11 vegetarische/vegane Rezepte.

## Additive, idempotente Importzuordnung

Kein ausführbarer Importer in diesem WP. Mapping auf vorhandene Dienste:

| Schritt | Dienst |
|---|---|
| Einheiten | `list_units` / vorhandener Seed; `skip_if_exists`; Konflikt bei Semantikabweichung |
| Kategorien, Tags | `master_data_store.create_vocabulary` (`food_category`, `tag`) |
| Zutaten | `create_food` (`source_kind=manual`) |
| Zutaten-Tags | `replace_food_tags` |
| Rezepte | `recipe_store.create_recipe` (R1-Payload, `expected_location_id`) |
| Bilder | `add_recipe_image`: 18 passende vorhandene Katalogbytes nach Hash-/Formatprüfung übernehmen |
| Revisionen | `freeze_revision` je Intent erst nach finalem Bildzustand |
| Kochbücher | `create_cookbook` + `replace_cookbook_recipes` in Dateireihenfolge |
| Wochen | Native Header-/Service-/Menüformulare über `persist_week_header`, `persist_service_state`, `persist_menu_item`; nur neue DRAFT-Wochen, Konflikt bei vorhandener fremder Woche |

Nicht aufrufen: `set_food_allergen_review`,
`replace_food_metadata`, Publikation, `recipe_import_batches`.

Dies ist ein Datenvertrag, kein ausführbarer oder bereits bewiesener Importer.
Der Folgeoperator benötigt einen vollständigen Dry-run, ein privates Journal,
Original-Actor/Standort/CAS/CSRF und getrennte Readbacks. Keine direkte SQL-
oder künstliche Sessionvariante; kein atomarer Gesamtrollback behauptet.
Die Zielwoche ist ein ausdrücklicher Parameter, keine automatische KW36-Auswahl.

**Idempotenz:** Wiederholter Import sucht nur eigene `example.*`-Schlüssel in
`source.reference` / `source.note` / `foods.note`. Unverändert: überspringen.
Abweichend: Konflikt melden, nicht überschreiben. Manuell gepflegte Daten ohne
`example.*` bleiben unberührt.

`food_key` und `tag_keys` sind symbolisch. Server-UUIDs entstehen erst beim
Anlegen. Der Validator mappt dafür nur im Speicher uuid5 aus
`8f3e2c10-0907-4d2a-9b61-6c7d8e9f0a1b`. Diese Werte sind keine
Produktions-`public_id`.

## Offene Lücken (kein stilles Weglassen)

1. **R5-Menübindung fehlt.** `menu_item_components.recipe_revision_id` und
   `dish_templates.recipe_id` stehen im Vertrag, nicht im verfügbaren Schema.
   Schema 23 ist Screen-Assignment. `menu_recipe_intents.binding` ist
   `intent_only_r5_unavailable`.
2. **R6-Importstapel fehlt.** Keine `recipe_import_batches`. Diese JSON-Datei
   ist kein Importer.
3. **Schema.** Source hat `create_recipe_v22`; Produktion bleibt Schema 21.
   Rezeptimport folgt Deployment.
4. **Publikation.** User-Entscheid steht aus. DRAFT-Vorbereitung und späteres
   DRAFT-Apply sind davon unabhängig; kein Publish oder Review.
5. **Bilder.** Passende Manifest-Dateien sind KI-Serviervorschläge. Rezepte haben
   `images: []`. Die Übernahme der 18 vorhandenen passenden Bilder ist für den
   Folgeoperator beauftragt, noch nicht ausgeführt. Keine erfundenen Lizenzen
   oder Abrufzeiten; Originalbytes, Kataloghash und Nutzungshinweis bewahren.
6. **Allergene.** `allergen_review_status=not_checked`, leere Allergen- und
   Label-Listen auf foods. Menü-Labels VEGETARIAN/VEGAN sind kulinarische
   Menüformulierung, keine medizinische Freigabe.

## Prüfen

```text
rtk /tmp/dishboard-shared-venv/bin/python -B tools/validate_recipe_examples.py
rtk env PYTHONDONTWRITEBYTECODE=1 /tmp/dishboard-shared-venv/bin/python -B -m pytest reference_scaffold/tests/test_recipe_examples.py -q -p no:cacheprovider
```
