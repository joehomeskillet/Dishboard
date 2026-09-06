# OPS-001 — Bereiche & Zeiten: verbindliche SDD

Status: **verbindlicher Umsetzungsvertrag** (6. September 2026). Basis `3690e04`, Schema 19. Root-Auftrag `wp-aef8520e7a3a`; Bestandsaufnahme `/nvmetank1/projects/rag-stack/.claude/reports/wp-f4f47205c827.md`. Ergänzt den [Entwurf §7/§9 O01](2026-09-05-screens-vorlagen-verwaltung.md) und den [Backlog](../BACKLOG.md#L97).

## 1. Umfang und Nicht-Ziele

**Umfang.** Anzeigenamen der beiden vorhandenen Bereiche, wiederkehrende Wochenvorgaben je Bereich/Wochentag/Mahlzeit (offen/geschlossen, Beginn, Ende, Hinweis), datierte Ausnahmen über die bestehenden `menu_services`, Wirksamkeit in Admin, Web, Signage, HTML-Druck, Wochen-PDF und API-Snapshot.

**Nicht-Ziele (ausdrücklich).**

- Technische Schlüssel `patient`/`staff_guest`, Rollen und Berechtigungen bleiben unverändert. Ein Rename zu «Schüler» ist kein dritter Bereich.
- **Cafeteria-Wochenende bleibt verboten.** `offer_profiles.allows_weekend=false`, Trigger `validate_menu_service`, `validate_publication_revision`, Patienten-/Cafeteria-Snapshotvalidatoren, A4-hoch-PDF mit fünf Tagen und alle Browserverträge fixieren Cafeteria auf Mo–Fr LUNCH und Patienten auf Mo–So LUNCH/DINNER. «Wochentage konfigurieren» bedeutet: jeder Slot des festen Profilrasters ist regelmässig *offen* oder *geschlossen*. Eine Rastererweiterung (Cafeteria Sa/So, weitere Mahlzeiten) ist eine eigene Modellerweiterung wie zusätzliche Bereiche.
- Mahlzeitenbezeichnungen (`Mittag`/`Abend`) bleiben fest (`MEAL_NAMES`, OpenAPI-Enum, Patienten-Fixwerte). Der Seed überschreibt `meal_periods.display_name` künftig nicht mehr, editierbar wird es nicht.
- Keine zweite Ausnahmenverwaltung: datierte Schliessungen/Feiertage/Betriebsferien und Zeitabweichungen sind Zeilen in `menu_services`.
- Kein Live-Join globaler Konfiguration in veröffentlichte Snapshots. Publizierte Ausgaben lesen ausschliesslich ihren Snapshot; ältere Snapshots (Schema 1) bleiben gültig und werden nicht umgeschrieben.
- FHIR/MCP bleiben strukturell unverändert (zusätzliche optionale Snapshot-Schlüssel werden durchgereicht, nicht gemappt).

## 2. Datenmodell (Schema 20, `0017_v19_to_v20.sql`)

| Objekt | Änderung |
|---|---|
| `menu_services` | `service_start time NULL`, `service_end time NULL`, `CHECK (service_start IS NULL OR service_end IS NULL OR service_end > service_start)`. Altzeilen bleiben NULL. Zeiten sind Wanduhrzeiten in `locations.timezone` (Europe/Zurich); Nachtfenster (Ende ≤ Beginn) sind ungültig. |
| `offer_profiles` | `CHECK (btrim(display_name) <> '' AND length(display_name) <= 80)`; `GRANT UPDATE (display_name) ON offer_profiles TO cafeteria_app` (permissions.sql + Migration). Keine weiteren Schreibrechte auf Profilcodes, Preis- oder Rasterflags. |
| `settings` | Schlüssel `operations_schedule`, Scope `location_id = aktiver Standort`, `profile_id = Profil`. JSONB-Wert siehe §3. Keine Schemaänderung. |
| `workflow_week_context(p_week_id)` | Service-Objekt zusätzlich `'start', to_char(service_start,'HH24:MI')`, `'end', to_char(service_end,'HH24:MI')` **innerhalb `jsonb_strip_nulls`**, damit Altzeilen ohne Zeiten exakt das bisherige JSON und damit gültige Review-Belege behalten. |
| `patient_key_is_forbidden` | Allowlist um `servicestart`, `serviceend`, `areaname` ergänzen. |
| `validate_publication_revision` | Optional: `area_name` (String, nicht leer, ≤ 80) auf Snapshotebene; `service_start`/`service_end` je Service (Muster `^([01][0-9]|2[0-3]):[0-5][0-9]$`, Ende > Beginn). Fehlende Schlüssel bleiben gültig (Schema 1). |
| `seed.sql` | `offer_profiles`: `ON CONFLICT (code) DO UPDATE` ohne `display_name`; `meal_periods`: nur `sort_order`. Wiederholter Seed erhält gepflegte Namen. |
| Pins | `db.SCHEMA_VERSION=20`, `APPLICATION_VERSION='dishboard-schema-v20'`, `validate_schema.py` (Version, `MIGRATION_0017`, Checksumme), `tools/validate_package.py` (Dateiliste, Checksumme, Version), Tests mit Versionslisten. Migration 0016 und frühere bleiben byteidentisch. |

## 3. Wochenvorgaben (`cafeteria/operations_settings.py`)

```json
{"revision": 3,
 "slots": {"1": {"LUNCH": {"state": "open", "start": "11:30", "end": "13:30", "notice": ""}},
           "6": {"LUNCH": {"state": "closed", "start": null, "end": null, "notice": "Samstags geschlossen"}}}}
```

- Raster: `staff_guest` ISO-Wochentage 1–5 × `LUNCH`; `patient` 1–7 × `LUNCH`, `DINNER`. Genau diese Schlüssel, keine anderen.
- `state ∈ {open, closed}`; `closed` verlangt nicht-leeren `notice` (≤ 200 Zeichen, keine Steuerzeichen). `start`/`end` optional, `HH:MM`, Ende > Beginn. Für `patient` laufen Hinweise durch `patient_text_is_forbidden` (Patientenpreisfreiheit).
- Fehlender Datensatz = Standard: alle Rasterslots `open`, keine Zeiten, `revision 0` — identisch zum heutigen Verhalten.
- Speichern ist Compare-and-Set über `revision` in derselben SQL-Anweisung, mit Akteur-/`authz_version`-/aktivem-Admin-Nachweis wie `display_settings._save_admin_display`. Konflikt → `OperationsConflictError`; fehlende Berechtigung → `PermissionError`; ungültig → `ValueError`.
- Öffentliche API des Moduls (Vertrag für O-B/O-C):
  `PROFILE_SLOTS`, `TIME_RE`, `SlotRule(state,start,end,notice)`, `OperationsSchedule(profile_code,revision,slots)`, `default_schedule(profile)`, `parse_schedule(profile, value)`, `get_schedule_connection(connection, location_id, profile)`, `get_schedule(engine, location_id, profile)`, `save_schedule(engine, actor_id, authz_version, location_id, profile, expected_revision, slots) -> int`, `slot_defaults(schedule, service_date, meal) -> SlotRule`, `normalise_time(value) -> str | None` (`''`/`None` → `None`, sonst strikt `HH:MM`), `get_area_names(connection|engine) -> dict[code, name]`, `save_area_name(engine, actor_id, authz_version, profile, expected_name, new_name)` (Compare-and-Set auf den bisherigen Namen; Patientenname durch `patient_text_is_forbidden`).

## 4. Vorrang und Materialisierung

1. **Zeile gewinnt immer.** Ein bestehender `menu_services`-Datensatz ist die Wahrheit für Datum/Mahlzeit (Status, Hinweis, Zeiten). Vorgaben verändern bestehende Zeilen nie.
2. **Vorgaben nur bei Neuanlage.** Jeder Pfad, der eine fehlende Servicezeile erzeugt, materialisiert `slot_defaults`:
   - `load_draft_connection`: synthetische Zellen (ohne Zeile) tragen Status/Hinweis/Zeiten der Vorgabe; `service_row_version 0` kennzeichnet sie im Admin als «Vorgabe, noch nicht gespeichert».
   - `persist_service_state` mit `expected 0`: speichert die Formularwerte (Status, Hinweis, `service_start`, `service_end`).
   - `persist_menu_item` ohne Servicezeile: Vorgabe `closed` → `PartialWorkflowConflictError('Service ist gemäss Wochenvorgabe geschlossen. Bitte zuerst den Service öffnen.')`; sonst Insert `open` mit Vorgabezeiten.
   - `persist_draft_connection` (Vollersatz, Formular, CSV, API): pro Service `service_start`/`service_end` = explizite Werte, sonst Werte der bisher vorhandenen Zeile gleichen Datums/Mahlzeit, sonst Vorgabe. Manuelle Zeiten gehen durch Vollersatz nie verloren.
   - `_clone_tree` (Woche kopieren): Status, Hinweis **und Zeiten** der Quellwoche werden unverändert kopiert (bewusste Kopie, keine Zielvorgaben).
3. **Bewusste Übernahme.** `apply_schedule_defaults_to_week(engine, scope, week_start)`: fehlende Slots werden aus der Vorgabe angelegt; vorhandene offene Zeilen ohne jede Zeit erhalten die Vorgabezeiten; alles andere bleibt. Wochenversion wird berührt, Review wird dadurch regulär ungültig.
4. **Review.** Zeiten sind Teil von `workflow_week_context`; Änderungen invalidieren den Prüfbeleg wie Hinweise. Altwochen ohne Zeiten behalten ihren Beleg.
5. **Publikation.** Snapshot Schema 2 friert `area_name` und Servicezeiten ein. Danach beeinflussen weder Namens- noch Vorgabenänderungen eine bestehende Publikation.

## 5. Snapshot Schema 2 und Verbraucher

- `build_snapshot`: `schema_version: 2`; neu `area_name` (aus `draft['area_name']`, geliefert von `load_draft_connection` aus `offer_profiles.display_name`); je Service optional `service_start`, `service_end` — **nur wenn gesetzt** (kein `null`), damit `patient_payload` strikt bleibt.
- `patient_payload`: `PATIENT_OBJECT_KEYS['snapshot']` unverändert, `PATIENT_OPTIONAL_KEYS` um `snapshot: {area_name}` und `service: {service_start, service_end}` erweitert; Zeiten als Strukturmuster, `area_name` als Freitext durch den Patiententextfilter. Schema-1-Snapshots bleiben gültig.
- Verbraucher (Public, Signage, HTML-Druck): `snapshot.area_name` ersetzt die festen Bereichstitel («Cafeteria · Mitarbeitende und Externe», «Speiseplan für Patientinnen und Patienten» usw.); ohne Schlüssel (Schema 1) bleibt der bisherige Text. Zeiten: `service_start`/`service_end` → «Ausgabe ab 11:30 Uhr» / «Ausgabe 11:30–12:30 Uhr» (Patienten) bzw. «Mittag 11:30–13:30 Uhr» (Cafeteria); ohne Zeiten keine Zeitzeile. **Einzige Ausnahme:** Schema-1-Patientenausgaben zeigen weiterhin die bisherigen festen Texte `Ausgabe ab 11:30/17:30 Uhr` (Konstante `LEGACY_PATIENT_MEAL_TIMES` an genau einer Stelle), damit laufende Publikationen unverändert bleiben.
- Wochen-PDF (`week_pdf.py`, aus dem Draft): Titel aus `draft['area_name']`, Tageszeile mit Zeiten wenn vorhanden; Einseitigkeit bleibt Gate.
- OpenAPI (`api/openapi.py`): optionale Felder `area_name` (Snapshot) und `service_start`/`service_end` (Service, Pattern). `schema_version` bleibt `integer ≥ 1`.

## 6. Admin (`/admin/bereiche-zeiten`, Tabler)

- Navigation «Bereiche & Zeiten» (Icon `clock`) neben «Design & Marke», sichtbar mit `can_configure_display`; Route mit `settings.write`, GET/POST, CSRF, PRG 303, `Cache-Control: no-store`, keine URL-Parameter, Fehlerfokus wie UI-003.
- Abschnitt **Anzeigenamen**: zwei Textfelder (technischer Schlüssel read-only daneben), versteckte `expected_*`; Konflikt/Fehler als Tabler-Alert mit Feldfokus.
- Abschnitt **Wochenvorgaben** je Bereich: Tabelle Wochentag × Mahlzeit mit Betrieb (`open`/`closed`), Beginn, Ende (`input type="time"`), Hinweis; verstecktes `revision`; Zeitzone sichtbar («Zeiten in Europe/Zurich»).
- Abschnitt **Datierte Ausnahmen**: Liste der Services (heute−7 bis heute+56 Tage, beide Bereiche) mit Status ≠ open **oder** Zeiten abweichend von der Vorgabe (Datum, Bereich, Mahlzeit, Status, Hinweis, Zeiten, Link zur Wochenseite). Formular «Ausnahme erfassen» (`profile, date, meal, service_state, notice, service_start, service_end`): legt bei Bedarf die Woche an (`ensure_week_connection`) und schreibt über `persist_service_state` (bestehende Zeile: gelesene `row_version`, Konflikt wird gemeldet).
- Bestehende Serviceformulare (cafeteria.html, patienten.html): Felder `service_start`, `service_end` (Pflichtfelder im POST, leer erlaubt), Badge «Vorgabe» bei `service_row_version == 0`; Button «Wochenvorgaben übernehmen» → `apply_schedule_defaults_to_week`. `parse_service_form` verlangt exakt `_csrf, week, day, meal, row_version, service_state, notice, service_start, service_end`.
- Review-Seite zeigt Zeiten je Service. Admin-Bereichstitel (Seitenköpfe, Screens-/Vorlagen-Karten, Wochenverwaltung) verwenden `area_names[profile]` aus `_template_context`; technische URL-Familien bleiben.

## 7. Dateibesitz (ein Vertrag, ein Besitzer)

| WP | Dateien | Reihenfolge |
|---|---|---|
| **O-A** Persistenz und Vertrag | `database/migrations/0017_v19_to_v20.sql`, `database/schema.sql`, `database/permissions.sql`, `database/seed.sql`, `database/validate_schema.py`, `database/README.md`, `tools/validate_package.py`, `cafeteria/db.py`, `cafeteria/patient_payload.py`, `cafeteria/operations_settings.py` (neu), Tests: neu `test_operations_settings_db.py`, Pins in `test_auth_database.py`, `test_component_catalog_migration_db.py`, `test_database_invariants.py`, `test_tabler_package_verification.py`, `test_workflow_review_migration_db.py` | zuerst |
| **O-B** Service-Schreiber und Snapshot | `workflow_store.py`, `workflow_partial_store.py`, `workflow_partial_form.py`, `workflow_form.py`, `workflow.py`, `workflow_copy_store.py`, `workflow_snapshot.py`, `csvio.py` (falls Servicefelder enumeriert), zugehörige `test_*workflow*`, `test_admin_workflow_snapshot_contract.py`, `test_workflow_form.py` | nach O-A, parallel zu O-D |
| **O-D** Ausgaben | `public/routes.py`, `signage/routes.py`, `template_filters.py`, `templates/public/*`, `templates/signage/*`, `admin/week_pdf.py`, `print_templates.py` (nur falls nötig), `api/openapi.py`, Tests `test_public_*`, `test_signage_*`, `test_week_pdf*.py`, `test_openapi_contract.py`, `test_api_v1.py`, `test_food_legends_*` | nach O-A, parallel zu O-B, ohne DB-Pool |
| **O-C** Admin | `admin/operations_routes.py` (neu), `admin/__init__.py`, `admin/rendering.py`, `templates/admin/operations.html` (neu), `_workflow_sidebar.html`, `cafeteria.html`, `patienten.html`, `week_review.html`, Bereichstitel in `screens.html`, `vorlagen.html`, `week_management.html`, `copy.html`, `preview.html`, Tests neu `test_admin_operations_routes.py`, `test_admin_operations_browser.py`, Anpassungen in Admin-UI-Tests | nach O-A und O-B |

Integration, Manifest (`tools/build_manifest.py`), Paketprüfung und Gesamtgate: Claude (Orchestrator) auf `feat/claude-ops-0906`.

## 8. Akzeptanzfälle (echte Gates)

1. Migration 19→20 auf leerer und auf seedierter PostgreSQL; Baseline `schema.sql` strukturgleich; Rollen-Readiness; `cafeteria_app` darf nur `display_name` in `offer_profiles` ändern.
2. Seed zweimal: gepflegte Anzeigenamen bleiben erhalten; Rasterflags werden weiterhin durchgesetzt.
3. Vorgaben speichern: ungültige Slots, Nachtfenster, `24:00`, fehlender Hinweis bei `closed`, fremde Wochentage (Cafeteria Sa) → 400/ValueError; Konflikt bei veralteter `revision`; Editor/Publisher → 403; abgelaufene `authz_version` → 401/403.
4. Nicht rückwirkend: bestehende Woche mit Zeilen bleibt nach Vorgabenänderung unverändert (Status, Hinweis, Zeiten, Review-Beleg); neue Woche zeigt Vorgaben als synthetische Zellen; erste Speicherung materialisiert sie.
5. Menü in vorgabe-geschlossenem Slot ohne Zeile → Konfliktmeldung, kein Insert.
6. Vollersatz/CSV-Import erhält manuelle Zeiten; Kopie übernimmt Zeiten der Quelle.
7. Wochengrenze/Mitternacht: Sonntag DINNER `closed` in Woche A beeinflusst Woche B nicht; `00:00`–`23:59` gültig; `effective_today` unverändert.
8. Review: Zeitänderung invalidiert Beleg; Altwoche ohne Zeiten behält Beleg (Kontext-JSON byteidentisch zu v19).
9. Publikation: Snapshot 2 mit `area_name` und Zeiten passiert Python- und SQL-Validator; Patientensnapshot ohne Preise, mit sensiblem Bereichsnamen abgelehnt; alter Snapshot 1 bleibt lesbar und zeigt Legacy-Texte.
10. Browser 390/820/1440: OPS-Seite, Serviceformular mit Zeiten, Ausnahmenliste; Public/Signage bei geänderten Namen und Zeiten, geschlossenen Bereichen, leerer Woche; Tabler-Bedienelemente, 48-px-Ziele, keine horizontale Seitenbewegung.
11. PDF: beide Wochen-PDFs einseitig mit Bereichsname und Zeiten; Patienten ohne Preise.
12. Ruff, Mypy (`--python-executable /tmp/dishboard-shared-venv/bin/python`), vollständiges Paketgate, Manifest.

## 9. Risiko

GitNexus-Impact (Index `menuplan-claude-ops-0906`): `build_snapshot`, `load_draft_connection`, `validate_snapshot_payload` **CRITICAL** (Publikation, Public/Signage, API, PDF, Import). Alle Änderungen sind additiv und abwärtskompatibel (nullable Spalten, optionale Schlüssel, Schema-1-Fallbacks); jede Symboländerung läuft mit eigenem Impact und `detect_changes` vor Commit. Root wird über diesen Vertrag informiert, bevor O-A gemerged wird.
