# BAS-001 / REC-001 — startfertige Arbeitspakete

Stand 6. September 2026. Gehört zu `docs/design/2026-09-06-bas-rec-data-contract.md`; dort
stehen alle Regeln, hier nur Zuschnitt, Dateibesitz, Abhängigkeiten und Gates.

**Startsperre.** Kein Paket beginnt vor Roots Prüfung des Datenvertrags und der Zuweisung von
Schema-/Dateieigentum. Migrationsnummern vergibt Root oberhalb des abgenommenen Schema-20-Vertrags
von OPS-001 (`0017_v19_to_v20.sql`, Fable 5.1). Die Testpools `test-ps5` und `test-ps1` sind
OPS-001 zugeordnet und dürfen hier nicht verwendet werden; Root weist je Welle einen eigenen
exklusiven Pool und eine eigene Testdatenbank zu.

**Regeln für jedes Paket.** Eigener Worktree, eigener Branch, disjunkter Dateibesitz, `rtk` für
jeden Shell-Aufruf, ein Befehl je Aufruf. Keine Abhängigkeitsinstallation. Keine Änderung an
`publication_revisions`, `validate_publication_revision()`, `patient_key_is_forbidden()` oder an
öffentlichen Ausgaben. Kein Paket meldet eine Backlog-ID fertig, das nur einen Teil davon
liefert.

---

## 1. Paketübersicht und Abhängigkeiten

```
B1 Mengen/Einheiten
 └─ B2 Stammdatenpersistenz
     ├─ B3 Stammdaten-Admin ─────────────┐
     └─ R1 Rezeptpersistenz + Revisionen │
         ├─ R2 Rezept-Admin ─────────────┤ → Freigabegrenze 1 (nutzbar, ohne Menübezug)
         ├─ R3 Bilder und Herkunft       │
         ├─ R4 Kochbücher                │
         ├─ R6 Importgrenze CSV/JSON     │
         └─ R5 Menü-/Komponentenbindung ─┘ → Freigabegrenze 2 (berührt Planungspfad)
             └─ R7 Rezeptdruck (R1+R3)   → Freigabegrenze 3
B4 Lagerorte (nach B2, unabhängig von R*)
```

| Paket | Zuschnitt | Migration | Gate-Art |
|---|---|---|---|
| B1 | Einheiten, Dimensionen, Umrechnung, Portionsskalierung | M-A (Teil) | echtes PG + reine Einheitentests |
| B2 | Zutaten, Kategorien, Tags, Vorschlagstabelle | M-A | echtes PG + Nebenläufigkeit |
| B3 | Admin `/admin/grundlagen` | keine | Browser + Formularverträge |
| B4 | Lagerorte und Zutaten-Lagerort-Zuordnung | M-A (Teil) | echtes PG + Browser |
| R1 | Rezeptkopf, Zutatenzeilen, Schritte, Revisionen | M-B | echtes PG + Unveränderlichkeit |
| R2 | Admin `/admin/rezepte`, Klartextschritte | keine | Browser |
| R3 | Bildablage und Herkunft | M-B (Teil) | echtes PG + Browser-Upload |
| R4 | Kochbücher und Sammlungen | M-B (Teil) | Browser |
| R5 | Bindung Menüposition ↔ Rezeptrevision | M-C | echtes PG + Publikationsregression |
| R6 | Importstapel CSV/JSON mit Vorschau | M-D | echtes PG + Browser |
| R7 | Rezept-PDF über bestehende Vorlagenbasis | keine | echtes PDF |

---

## 2. Pakete im Einzelnen

### B1 — Mengen, Einheiten, Umrechnung

**Besitzt neu:** `reference_scaffold/cafeteria/quantities.py`,
`reference_scaffold/tests/test_quantities.py`, `reference_scaffold/tests/test_quantities_db.py`.
**Besitzt mit (Vertragsdatei):** der Migrationsschritt M-A, Abschnitt `measurement_units`
inklusive Seed.
**Berührt:** `database/schema.sql`, `database/seed.sql`, `database/validate_schema.py`,
`reference_scaffold/cafeteria/db.py` (Versionspins), `tools/validate_package.py`.

Inhalt: Tabelle `measurement_units`; reine Funktionen `convert(quantity, from_unit, to_unit,
food=None)`, `to_base(...)`, `sum_in_base(...)`, `scale_servings(...)`. Kein Datenbankzugriff im
Modul. Bei fehlendem Umrechnungsfaktor eine eigene Ausnahme, kein Näherungswert, kein `None`.

**Akzeptanz.** Umrechnung innerhalb einer Dimension exakt; Masse ↔ Volumen nur mit
`density_g_per_ml`; Anzahl ↔ Masse nur mit `piece_weight_g`; fehlender Faktor wirft; Summierung
läuft in der Basiseinheit und rundet genau einmal; `PORTION` ist nicht in Masse umrechenbar;
genau eine aktive Basiszeile je Dimension (Unique-Index-Verletzung wird nachgewiesen).

**Gate.** `pytest reference_scaffold/tests/test_quantities.py test_quantities_db.py` gegen die
zugewiesene reale PostgreSQL-Testdatenbank, plus `python database/validate_schema.py`.

---

### B2 — Stammdatenpersistenz

**Besitzt neu:** `reference_scaffold/cafeteria/master_data_store.py`,
`reference_scaffold/tests/test_master_data_db.py`,
`reference_scaffold/tests/test_master_data_race_db.py`.
**Besitzt mit:** Migrationsschritt M-A, Abschnitte `food_categories`, `foods`, `tags`,
`food_tags`, `food_labels`, `food_allergens`, `food_data_proposals`.
**Abhängig von:** B1.

Inhalt: Anlegen, Ändern, Archivieren, Reaktivieren mit `row_version`-Prüfung; Zuweisung von
Kategorie, Tags, bestätigten Labels und Allergenen; Vorschlagstabelle mit
`open`/`accepted`/`rejected` und Übernahmeprüfung gegen bestätigte Werte. Rechte auf
`cafeteria_app` ohne `DELETE`.

**Akzeptanz.** Namenseindeutigkeit je Standort greift auch bei abweichender Gross-/Kleinschreibung
und Randleerzeichen; gleichzeitige Bearbeitung führt zu einem sichtbaren Konflikt statt zu
stillem Überschreiben; ein akzeptierter Vorschlag überschreibt keinen bestätigten Wert, sondern
meldet den Konflikt; jede Schreibaktion erzeugt genau einen `audit_events`-Eintrag;
`cafeteria_app` kann nachweislich nicht löschen.

**Gate.** Reales PG, Nebenläufigkeitstest nach dem Muster von
`test_component_catalog_race_db.py`, plus `test_database_role_readiness.py`.

---

### B3 — Stammdaten-Admin

**Besitzt neu:** `reference_scaffold/cafeteria/admin/master_data_routes.py`,
`reference_scaffold/cafeteria/templates/admin/grundlagen*.html`,
`reference_scaffold/cafeteria/static/admin-master-data.css`,
`reference_scaffold/tests/test_master_data_routes.py`,
`reference_scaffold/tests/test_master_data_browser.py`.
**Berührt:** Sidebar-Template und `cafeteria/admin/__init__.py` (Registrierung).
**Abhängig von:** B2.

Inhalt: `/admin/grundlagen` mit Liste, Filter, Detail, Anlegen, Archivieren; Tabler-Formulare,
keine neue Komponentensprache. Fähigkeiten `draft.read` beziehungsweise `masterdata.write`.

**Akzeptanz.** Vollständiges Tabler-Gate: Label-Feld-Bezüge, Fehlerfokus auf dem ersten
fehlerhaften Feld, sichtbare Bearbeiten-Aktionen, Touch-Ziele; Version im Formular, Konflikt
sichtbar; Archivierte sind ausgeblendet und über einen Filter erreichbar; kein CSP-Verstoss im
Browserlauf.

**Gate.** `test_master_data_browser.py` (echter Browser), `test_admin_form_contracts.py` und
`test_admin_tabler_browser.py` unverändert grün, Prüfung gegen
`docs/design/admin-tabler-contract.md`.

---

### B4 — Lagerorte

**Besitzt neu:** `reference_scaffold/cafeteria/storage_locations_store.py`, zugehörige Routen,
Templates, `reference_scaffold/tests/test_storage_locations_db.py`,
`reference_scaffold/tests/test_storage_locations_browser.py`.
**Besitzt mit:** Migrationsschritt M-A, Abschnitt `storage_locations`.
**Abhängig von:** B2.

Inhalt: Lagerorte je Standort pflegen, Zutaten einem Lagerort zuordnen.
**Ausdrücklich nicht enthalten:** Bestände, Bewegungen, Zählungen, Korrekturen. Diese gehören
INV-001. Die Oberfläche zeigt «kein Bestand erfasst», nicht null.

**Akzeptanz.** Kein Bestandsfeld auf `foods` (Schemaprüfung als Test); Archivieren eines
Lagerorts mit Zuordnungen wird verweigert oder sauber gelöst, nie stillschweigend kaskadiert.

---

### R1 — Rezeptpersistenz und Revisionen

**Besitzt neu:** `reference_scaffold/cafeteria/recipe_store.py`,
`reference_scaffold/tests/test_recipe_store_db.py`,
`reference_scaffold/tests/test_recipe_revision_immutable_db.py`.
**Besitzt mit:** Migrationsschritt M-B, Abschnitte `recipes`, `recipe_ingredients`,
`recipe_steps`, `recipe_revisions`, `recipe_tags`.
**Abhängig von:** B2.

Inhalt: Rezeptkopf mit Portionen und Herkunft; geordnete Zutatenzeilen mit Freitext, optionaler
Zutatenbindung, Menge und Einheit; geordnete Klartextschritte; Festschreiben einer Revision mit
kanonischem Snapshot und SHA-256.

**Akzeptanz.** `UPDATE` und `DELETE` auf `recipe_revisions` schlagen fehl (beide einzeln
nachgewiesen); Ändern von Zutaten oder Schritten erhöht `recipes.row_version`; eine
festgeschriebene Revision ändert sich nicht, wenn danach das Rezept bearbeitet wird — belegt
durch Vergleich von `content_hash_sha256` vor und nach der Bearbeitung; `quantity` und `unit_id`
sind nur gemeinsam gesetzt; Archivieren eines referenzierten Rezepts löscht nichts.

**Gate.** Reales PG. Der Hash-Vergleichsfall ist der Kernnachweis dieses Pakets.

---

### R2 — Rezept-Admin

**Besitzt neu:** `reference_scaffold/cafeteria/admin/recipe_routes.py`,
`reference_scaffold/cafeteria/templates/admin/rezepte*.html`,
`reference_scaffold/cafeteria/static/admin-recipes.css`,
`reference_scaffold/tests/test_recipe_routes.py`,
`reference_scaffold/tests/test_recipe_browser.py`.
**Abhängig von:** R1.

Inhalt: `/admin/rezepte` mit Liste, Suche über Titel, Detail mit Zutaten- und Schrittzeilen,
Umsortieren, Portionsanzeige, Revision festschreiben. Schritte sind `textarea`-Klartext und
werden escaped gerendert. **Kein Rich-Text-Editor.**

**Akzeptanz.** Vollständiges Tabler-Gate wie B3; Umsortieren erhält die Nummerierung lückenlos;
Portionsänderung zeigt skalierte Mengen, ohne gespeicherte Werte zu ändern; ein
Bearbeitungskonflikt ist sichtbar; keine CSP-Verletzung.

---

### R3 — Bilder und Herkunft

**Besitzt neu:** `reference_scaffold/cafeteria/recipe_images.py`,
`reference_scaffold/tests/test_recipe_images_db.py`,
`reference_scaffold/tests/test_recipe_images_browser.py`.
**Besitzt mit:** Migrationsschritt M-B, Abschnitte `recipe_assets`, `recipe_images`.
**Abhängig von:** R1.

Inhalt: Inhaltsadressierte Ablage nach dem Muster `branding_assets`, PNG und JPEG, ≤ 1 MiB;
Verknüpfung mit Bildunterschrift, Quelle, Lizenz und Abrufzeit.

**Akzeptanz.** Ein Upload mit falschen Magic Bytes wird abgelehnt; ein Hash, der nicht zu den
Bytes passt, wird von der Datenbank abgelehnt; zweimal dasselbe Bild erzeugt eine Zeile in
`recipe_assets`; ein Bild mit `source_url` ohne Lizenz und Abrufzeit wird abgelehnt;
Überschreitung der Grössengrenze wird abgelehnt.

---

### R4 — Kochbücher und Sammlungen

**Besitzt neu:** `reference_scaffold/cafeteria/cookbook_store.py`, zugehörige Routen und
Templates, `reference_scaffold/tests/test_cookbooks_db.py`,
`reference_scaffold/tests/test_cookbooks_browser.py`.
**Besitzt mit:** Migrationsschritt M-B, Abschnitte `cookbooks`, `cookbook_recipes`.
**Abhängig von:** R1.

**Akzeptanz.** Ein Rezept ist in mehreren Kochbüchern; Entfernen aus einem Kochbuch löscht kein
Rezept; Sortierung ist stabil und lückenlos.

---

### R5 — Bindung Menüposition an Rezeptrevision

**Besitzt mit:** Migrationsschritt M-C und die Erweiterung von
`validate_menu_item_component_scope()`.
**Berührt:** `reference_scaffold/cafeteria/component_assignment_store.py`,
`reference_scaffold/cafeteria/admin/workflow_routes.py`,
`reference_scaffold/cafeteria/workflow_form.py`.
**Besitzt neu:** `reference_scaffold/tests/test_recipe_menu_binding_db.py`.
**Abhängig von:** R1. **Einziges Paket dieser Welle, das den Planungspfad berührt.**

Inhalt: `menu_item_components.recipe_revision_id`, gegenseitiger Ausschluss zu `component_id`,
Standortprüfung im Trigger, Auswahl der Revision im Menüeditor.

**Ausdrücklich nicht enthalten:** jede Änderung am Publikations-Snapshot. Die veröffentlichte
Nutzlast bleibt byteidentisch.

**Akzeptanz.** `component_id` und `recipe_revision_id` gleichzeitig gesetzt wird abgelehnt; eine
Revision eines Rezepts an einem anderen Standort wird abgelehnt; `test_admin_workflow_snapshot_contract.py`
und `test_public_contracts.py` bleiben **unverändert** grün; eine bestehende veröffentlichte
Woche zeigt vor und nach der Migration denselben `content_hash_sha256`.

**Gate.** Reales PG plus die vollständige Publikationsregression. Dieses Paket wird nicht ohne
Root-Abnahme integriert.

---

### R6 — Importgrenze CSV und JSON

**Besitzt neu:** `reference_scaffold/cafeteria/recipe_import.py`, Vorschauroute und Template,
`reference_scaffold/tests/test_recipe_import_db.py`,
`reference_scaffold/tests/test_recipe_import_browser.py`.
**Besitzt mit:** Migrationsschritt M-D.
**Berührt:** `docs/CSV_IMPORT_EXPORT.md` (neuer Abschnitt Rezeptschema).
**Abhängig von:** R1.

Inhalt: Datei hochladen, validieren, zeilenweise Fehler anzeigen, Dubletten anzeigen,
transaktional übernehmen. Nur CSV und JSON nach dem Dishboard-eigenen Schema.

**Akzeptanz.** Ein Stapel schreibt vor der Übernahme nichts in `recipes`; eine fehlerhafte Zeile
verhindert die Übernahme des Stapels; Grössen- und Zeilengrenzen greifen; unbekannter
Inhaltstyp wird abgelehnt; `source_kind='file_import'` und Quelle stehen auf jedem übernommenen
Rezept; die Fähigkeit `recipe.import` wird serverseitig erzwungen (Editor bekommt 403).

**Nicht enthalten:** XLSX, Schema.org, Pauli. Jedes davon ist ein eigenes Paket und braucht
zuvor eine reale, berechtigte Beispieldatei.

---

### R7 — Rezept- und Einkaufsdruck, erste nutzbare Stufe

**Besitzt neu:** `reference_scaffold/cafeteria/admin/recipe_pdf.py`,
`reference_scaffold/tests/test_recipe_pdf.py`.
**Abhängig von:** R1 und R3.

Inhalt: Rezept-PDF auf der bestehenden fpdf2-Basis mit Logo, Portionen, Zutaten, Schritten,
Bild und automatischer Legende. Lange Rezepte dürfen lesbar mehrseitig sein. Die Einseitenpflicht
für Wochenpläne bleibt unberührt.

**Akzeptanz.** Erzeugtes PDF wird geöffnet und geprüft, nicht nur der HTTP-Status; ein langes
Rezept bricht lesbar um, ohne abzuschneiden; Legende zeigt nur tatsächlich dargestellte Symbole;
`test_week_pdf*.py` bleiben unverändert grün.

---

## 3. Freigabegrenzen

**Grenze 1 — erste nutzbare Auslieferung: B1 + B2 + B3 + R1 + R2.**
Stammdaten und Rezepte sind vollständig pflegbar, durchsuchbar und revisionierbar. Es besteht
noch keine Verbindung zu Menüs, Publikationen oder Ausgaben. Das ist der sicherste mögliche
erste Deploy dieser Welle: er berührt keinen einzigen Publikationspfad, und ein Rückbau
entfernt nur ungenutzte Tabellen. Erforderlich sind das reale PG-Gate, das Browser-Gate und die
unveränderten bestehenden Suiten.

**Grenze 2 — Menübezug: + R3 + R4 + R5 + R6.**
Erst hier wird der Planungspfad berührt. Zusätzlich erforderlich: vollständige
Publikationsregression und der Nachweis, dass eine bestehende veröffentlichte Woche ihren
Inhaltshash behält.

**Grenze 3 — Druck: + R7.** Zusätzlich erforderlich: echter PDF-Nachweis und fachliche
Druckabnahme.

---

## 4. Abdeckung der Backlog-Verpflichtungen

Vollständig heisst: durch die genannten Pakete abgedeckt. Teilweise heisst: die ID bleibt
danach offen.

**BAS-001 «Grundlagen & Lager»**

| Verpflichtung | Paket | Abdeckung |
|---|---|---|
| Zutaten und Lebensmittel zentral pflegen | B2, B3 | vollständig |
| Komponenten | vorhanden, `menu_components.food_id` in R5-Migration M-C | vollständig durch Verknüpfung des bestehenden Katalogs |
| Einheiten | B1 | vollständig |
| Kategorien | B2, B3 | vollständig |
| Tags | B2, B3 | vollständig für Pflege; Serienzuweisung und Suche bleiben REC-006 |
| Lagerorte | B4 | vollständig |
| Bestände mit Rezepten und Einkauf verbinden | B4 liefert Orte und Verknüpfung | **teilweise** — Journal, Saldo und Buchungen sind INV-001; BAS-001 bleibt bis dahin offen |
| Vorhandene Stammdaten wiederverwenden | B2, M-C | vollständig; kein Bestand wird ersetzt |
| Tandoors Lagerfunktionen gesondert prüfen | offen | nicht in dieser Welle; keine Kompatibilitätsaussage |

**REC-001 «Rezeptverwaltung»**

| Verpflichtung | Paket | Abdeckung |
|---|---|---|
| Wiederverwendbare Rezepte | R1, R2 | vollständig |
| Bilder | R3 | vollständig |
| Zutaten, Mengen, Einheiten | B1, R1 | vollständig |
| Portionen | B1, R1, R2 | vollständig |
| Geordnete Schritte | R1, R2 | vollständig als Klartext |
| Quellen | R1 (`source_kind`, `source_url`, `source_note`) | vollständig |
| Mit vorhandenen Menüs und Komponenten verbinden | R5 | vollständig |
| Kochbücher und Sammlungen | R4 | vollständig |
| HugeRTE prüfen | Vertrag §10 | **geprüft und begründet zurückgestellt**; R-RTE ist ein eigenes Paket mit fünf Eintrittsbedingungen. Keine Technologiefreigabe, keine Installation. |

REC-001 gilt nach Grenze 2 als vollständig geliefert **mit Ausnahme** des Rich-Text-Editors, der
im Backlog ausdrücklich als Prüfkandidat und nicht als Zusage geführt ist.

---

## 5. Offene Punkte für Root

1. Zuweisung der Migrationsnummern M-A bis M-D oberhalb Schema 20 und der zugehörigen
   Versionspins.
2. Zuweisung eines exklusiven Testpools und einer Testdatenbank für diese Welle
   (`test-ps5`, `test-ps1` sind OPS-001 zugeordnet).
3. Entscheidung, ob B4 und R6 in Welle 1 mitlaufen oder auf Grenze 2 warten.
4. Bestätigung, dass R5 die veröffentlichte Nutzlast nicht erweitern soll — der Vertrag geht
   davon aus und vermeidet damit jede Kollision mit dem OPS-Eigentum an
   `validate_publication_revision()`.
5. Beschaffung einer berechtigten Pauli-Beispieldatei, falls REC-004 in absehbarer Zeit
   beginnen soll.
