# BAS-001 / REC-001 — startfertige Arbeitspakete

Stand 6. September 2026. Gehört zu `docs/design/2026-09-06-bas-rec-data-contract.md`; dort
stehen alle Regeln, hier nur Zuschnitt, Dateibesitz, Abhängigkeiten und Gates.

**Startsperre.** Kein Paket beginnt vor Roots Prüfung des Datenvertrags und der Zuweisung von
Schema-/Dateieigentum. Migrationsnummern vergibt Root oberhalb des abgenommenen Schema-20-Vertrags
von OPS-001 (`0017_v19_to_v20.sql`, nach Fable-Sessionlimit durch Root/Codex übernommen,
weiterhin ungeprüft). Die Testpools `test-ps5` und `test-ps1` sind
OPS-001 zugeordnet und dürfen hier nicht verwendet werden; Root weist je Welle einen eigenen
exklusiven Pool und eine eigene Testdatenbank zu. Ausnahme: Nach ausdrücklicher Freigabe von
§3 des Datenvertrags kann B1 vor Schema 20 beginnen; es braucht weder Migration noch DB-Pool.

**Regeln für jedes Paket.** Eigener Worktree, eigener Branch, disjunkter Dateibesitz, `rtk` für
jeden Shell-Aufruf, ein Befehl je Aufruf. Keine Abhängigkeitsinstallation. Genau ein Autor pro
Schemaeinheit: B2 besitzt **ganz M-A**, R1 **ganz M-B**, R5 M-C und R6 M-D. Root serialisiert
diese Reihenfolge für `database/schema.sql`, `seed.sql`, `permissions.sql`,
`database/README.md` (vollständige Migrationsliste), `database/validate_schema.py`,
`tools/validate_package.py`, Versionspins in `reference_scaffold/cafeteria/db.py` und sämtliche
betroffenen Schema-/Migrations-/Paketfixtures samt historischer permissions-Kette. UI-/Service-
Folgepakete ändern keine registrierten Migrationen; weitere SQL-Funktionen benötigen bei
Bedarf einen neuen, Root zugewiesenen Migrationsschritt. Frühere Migrationen bleiben byteidentisch, und vor
jedem Schemawechsel steht ein geprüftes Backup. Keine Änderung an
`publication_revisions`, `validate_publication_revision()`, `patient_key_is_forbidden()` oder an
öffentlichen Ausgaben. Kein Paket meldet eine Backlog-ID fertig, das nur einen Teil davon
liefert.

**Geprüft im aktuellen Code-Stand enthalten, noch nicht deployed:** B1 `e0fb93e` (ursprünglich
`c7873fa`), gesamter 433-Zeilen-Diff
von Root gelesen; unabhängig **101 passed in 1.26s**, Ruff bestanden, Mypy ohne Fehler in
zwei Dateien ([JUnit](/tmp/dishboard-root-quantities-b1-0906.xml)). Der §3-/B1-Vertrag bleibt
unverändert. B2 beginnt erst nach abgenommenem OPS-Schema 20; BAS-001/REC-001 sind nicht fertig.

---

## 1. Paketübersicht und Abhängigkeiten

```
B1 Mengen/Einheiten
 └─ B2 Stammdatenpersistenz
     ├─ B3 Stammdaten-Admin ─────────────┐
     └─ R1 Rezeptpersistenz + Revisionen │
         ├─ R2 Rezept-Admin ─────────────┤ → Freigabegrenze 1 (nutzbar, ohne Menübezug)
         ├─ R3 Bilder und Herkunft ─ R7 Rezeptdruck (zusätzlich R1) → Freigabegrenze 3
         ├─ R4 Kochbücher                │
         ├─ R6 Importgrenze CSV/JSON     │
         └─ R5 Menü-/Komponentenbindung ─┘ → Freigabegrenze 2 (berührt Planungspfad)
B4 Lagerorte (nach B2, unabhängig von R*)
```

| Paket | Zuschnitt | Migration | Gate-Art |
|---|---|---|---|
| B1 | Reine Mengen-/Einheitenfunktionen und Portionsskalierung | keine | stdlib-Einheitentests, kein PG |
| B2 | Gesamtes Stammdatenschema, Einheiten, Lagerzuordnung, Herkunft und Fachguard | ganz M-A | echtes PG + Nebenläufigkeit |
| B3 | Admin `/admin/grundlagen` | keine | Browser + Formularverträge |
| B4 | Bedienung Lagerorte und Zutaten-Lagerort-Zuordnung auf B2-Vertrag | keine | echtes PG + Browser |
| R1 | Gesamtes Rezept-/Bild-/Kochbuchschema und Rezeptpersistenz | ganz M-B | echtes PG + Unveränderlichkeit |
| R2 | Admin `/admin/rezepte`, Klartextschritte | keine | Browser |
| R3 | Upload/Bildzuordnung auf R1-Vertrag | keine | echtes PG + Browser-Upload |
| R4 | Kochbücher und Sammlungen auf R1-Vertrag | keine | Browser |
| R5 | Bindung Menüposition ↔ Rezeptrevision | M-C | echtes PG + Publikationsregression |
| R6 | Importstapel CSV/JSON mit Vorschau | M-D | echtes PG + Browser |
| R7 | Rezept-PDF über bestehende Vorlagenbasis | keine | echtes PDF |

**Gemeinsames Wiring.** Root allein besitzt `cafeteria/admin/__init__.py`, die gemeinsamen
Sidebar-/Adminbasistemplates und `roles.py` für die Fähigkeitsregistrierung aus §8.
B3/R2/R3/R4/B4/R6 liefern eigene Routen/Tests und benennen benötigte Imports/Navigationsziele;
Root registriert sie einzeln auf dem jeweils integrierten Stand. Gemeinsame Rezepttemplates,
`recipe_routes.py` und `admin-recipes.css` besitzen zuerst R2, danach ausdrücklich und seriell
R3→R4→R6→R7, soweit ein Paket diese Stellen wirklich benötigt; kein paralleler Dateibesitz.
B3 besitzt `grundlagen*.html`, B4 eigene Lagerorttemplates. Read-only abhängige Arbeit kann
parallel laufen; kein ungetestetes Wiring gilt als fertige Oberfläche.

---

## 2. Pakete im Einzelnen

### B1 — Mengen, Einheiten, Umrechnung

**Besitzt neu:** `reference_scaffold/cafeteria/quantities.py`,
`reference_scaffold/tests/test_quantities.py`. **Keine** Schema-, Seed-, Versionspin-,
Migrations- oder Datenbanktest-Datei; diese gehören vollständig B2.

Inhalt: stdlib-only, unveränderliche `Unit(code, dimension, base_factor)` und
`FoodFactors(density_g_per_ml=None, piece_weight_g=None)` mit validierten Decimal-Werten.
`parse_quantity(str | Decimal) -> Decimal` und `parse_factor(str | Decimal) -> Decimal`
prüfen die Speicherwertegebiete aus §3.2. Reine Funktionen
`convert(quantity, from_unit, to_unit, food=None)`, `to_base(quantity, unit)`,
`sum_in_base(quantities_and_units)` und `scale_servings(quantity, source_servings, target_servings)`
liefern `Decimal`. `sum_in_base` erhält eine Folge von `(Decimal, Unit)` derselben
konvertierbaren Dimension; leere Folge ergibt Decimal-Null, gemischte oder kontextabhängige
Dimensionen werden abgelehnt. Berechnete Zwischenwerte dürfen mehr als 6 Dezimalstellen haben;
die Parser sind die ausdrückliche Grenze vor Persistenz. Kein Datenbankzugriff, kein ORM.
Ungültige Werte/Dimensionen oder fehlende Faktoren liefern eine verständliche eigene
`ValueError`-Unterklasse, niemals Näherungsersatz, `None` oder stillschweigende Null.

**Akzeptanz.** G/ML/STK sind feste kanonische Basen; PORTION/PRISE sind nur zu demselben Code
identisch umrechenbar, auch mit Dichte/Stückgewicht nie nach STK/G/ML. EL/TL bedeuten 15/5 ml.
Masse ↔ Volumen braucht Dichte, Anzahl ↔ Masse Stückgewicht, Anzahl ↔ Volumen beide Faktoren
derselben Zutat. Endlichkeit/Positivität/Präzisionsgrenzen gelten auch für optionale Faktoren
und Portionszahlen. Eigener Kontext mit 50 Stellen und `ROUND_HALF_UP`, einschliesslich
periodischer Division und absichtlich verändertem globalem Decimal-Kontext getestet.
Keine Zwischenquantisierung; Speicherung/Import wird durch die Parser gegen stillen Verlust
geschützt. Skalierung einer kontextabhängigen Zeile ist erlaubt, dimensionsübergreifende
oder kontextlose Aggregation nicht. DB-Erhalt und Unveränderlichkeit der Einheiten prüft B2.

**Gate.** `rtk /tmp/dishboard-shared-venv/bin/python -m pytest
reference_scaffold/tests/test_quantities.py -q`, Ruff und Mypy der beiden Dateien.
Kein PostgreSQL-Gate; Start nach Root-Freigabe dieses Vertrags unabhängig von Schema 20.

---

### B2 — Stammdatenpersistenz

**Besitzt neu:** `reference_scaffold/cafeteria/master_data_store.py`,
`reference_scaffold/tests/test_master_data_db.py`,
`reference_scaffold/tests/test_master_data_race_db.py`.
**Besitzt allein:** Migrationsschritt M-A vollständig: `measurement_units` samt Seed/Erhalt,
`food_categories`, `foods`, `tags`, `food_tags`, `food_labels`, `food_allergens`,
`storage_locations`, `food_storage_locations`, `food_data_proposals`, alle Mengen-/Quellen-/
Standortconstraints, Fachmutatorfunktionen und deren Rechte. Dazu alle oben genannten
Schema-/Pin-/Fixture-Dateien sowie `test_quantities_db.py`; kein M-A-Teileigentum von B1/B4.
**Abhängig von:** B1 und abgenommenem OPS-Schema 20.

Inhalt: Anlegen, Ändern, Archivieren, Reaktivieren mit `row_version`-Prüfung; Zuweisung von
Kategorie, Tags, bestätigten Labels und Allergenen; Vorschlagstabelle mit
`open`/`accepted`/`rejected` und Übernahmeprüfung gegen bestätigte Werte. Rechte auf
`cafeteria_app` nur über eng erlaubte Funktionen (§8), ohne direktes Tabellen-DML.

**Akzeptanz.** Namenseindeutigkeit je Standort greift auch bei abweichender Gross-/Kleinschreibung
und Randleerzeichen; gleichzeitige Bearbeitung führt zu einem sichtbaren Konflikt statt zu
stillem Überschreiben; ein akzeptierter Vorschlag überschreibt keinen bestätigten Wert, sondern
meldet den Konflikt; jede Schreibaktion erzeugt genau einen `audit_events`-Eintrag;
`cafeteria_app` kann nachweislich weder direkt ändern noch löschen. Tests belegen Erhalt der
drei kanonischen Einheiten und semantische Unveränderlichkeit aller Einheiten, endliche
Decimal-Grenzen ohne DB-Rundung, Standortgleichheit jedes neuen FK-/Join-Paars sowie
Actor-Version/Capability unter gleichzeitigem Rollenentzug/Passwortreset. Quellenfelder und
unbekannte Allergene bleiben erhalten; angenommene Vorschlagsentscheidungen sind unveränderlich.

**Gate.** Reales PG, Nebenläufigkeitstest nach dem Muster von
`test_component_catalog_race_db.py`, plus `test_database_role_readiness.py`.

---

### B3 — Stammdaten-Admin

**Besitzt neu:** `reference_scaffold/cafeteria/admin/master_data_routes.py`,
`reference_scaffold/cafeteria/templates/admin/grundlagen*.html`,
`reference_scaffold/cafeteria/static/admin-master-data.css`,
`reference_scaffold/tests/test_master_data_routes.py`,
`reference_scaffold/tests/test_master_data_browser.py`.
**Gemeinsame Registrierung/Sidebar:** ausschliesslich Root nach §1.
**Abhängig von:** B2.

Inhalt: `/admin/grundlagen` mit Liste, Filter, Detail, Anlegen, Archivieren einschliesslich
Einheitenpflege nach §3 (geschützte Semantik, neue Einheit für andere Bedeutung); Tabler-Formulare,
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
**Schema:** nur Verbraucher der von B2 vollständig gelieferten Lagerort-/Zuordnungsfunktionen.
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
**Besitzt allein:** Migrationsschritt M-B vollständig: `recipes`, `recipe_ingredients`,
`recipe_steps`, `recipe_revisions`, `recipe_tags`, `recipe_assets`, `recipe_images`,
`cookbooks`, `cookbook_recipes`, sämtliche zugehörigen Funktionen, Herkunfts-/Mengen-/Scope-
Constraints, Rechte und alle Schema-/Pin-/Fixture-Dateien. R3/R4 bekommen keine M-B-Teile.
**Abhängig von:** B2.

Inhalt: Rezeptkopf mit Portionen und Herkunft; geordnete Zutatenzeilen mit Freitext, optionaler
Zutatenbindung, Menge und Einheit; geordnete Klartextschritte; Festschreiben einer Revision mit
kanonischem Snapshot und SHA-256.

**Akzeptanz.** `UPDATE` und `DELETE` auf `recipe_revisions` schlagen fehl (beide einzeln
nachgewiesen); Ändern von Zutaten oder Schritten erhöht `recipes.row_version`; eine
festgeschriebene Revision ändert sich nicht, wenn danach das Rezept bearbeitet wird — belegt
durch Vergleich von `content_hash_sha256` vor und nach der Bearbeitung; `quantity` und `unit_id`
sind nur gemeinsam gesetzt; Archivieren eines referenzierten Rezepts löscht nichts.
Snapshot friert Decimal-Mengen, Portions-/Einheitsmetadaten, verwendete Faktoren und Herkunft
ein; spätere Änderungen am Food-Faktor oder Einheitenname ändern alte Revisionsberechnung
nicht. Bild-/Schritt-/Kochbuch-/Tag-/Food-Zuordnungen sind in DB und Dienst standortgleich.
Alle Mutationserwartungen und Audit bleiben atomar nach §7/§8.

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
**Schema:** Verbraucher der von R1 gelieferten Asset-/Bildfunktionen, keine Migration.
**UI-Wiring:** erst nach Übergabe der gemeinsamen R2-Dateien (§1).
**Abhängig von:** R1.

Inhalt: Inhaltsadressierte Ablage nach dem Muster `branding_assets`, PNG und JPEG, ≤ 1 MiB;
Verknüpfung mit Bildunterschrift, Quelle, Lizenz und Abrufzeit.

**Akzeptanz.** Ein Upload mit falschen Magic Bytes wird abgelehnt; ein Hash, der nicht zu den
Bytes passt, wird von der Datenbank abgelehnt; zweimal dasselbe Bild am selben Standort erzeugt eine Zeile in
`recipe_assets`; ein Bild mit `source_url` ohne Lizenz und Abrufzeit wird abgelehnt;
Überschreitung der Grössengrenze wird abgelehnt.

---

### R4 — Kochbücher und Sammlungen

**Besitzt neu:** `reference_scaffold/cafeteria/cookbook_store.py`, zugehörige Routen und
Templates, `reference_scaffold/tests/test_cookbooks_db.py`,
`reference_scaffold/tests/test_cookbooks_browser.py`.
**Schema:** Verbraucher der von R1 gelieferten Kochbuch-/Zuordnungsfunktionen, keine Migration.
**UI-Wiring:** seriell nach §1, keine parallelen Änderungen an Rezepttemplates.
**Abhängig von:** R1.

**Akzeptanz.** Ein Rezept ist in mehreren Kochbüchern; Entfernen aus einem Kochbuch löscht kein
Rezept; Sortierung ist stabil und lückenlos.

---

### R5 — Bindung Menüposition an Rezeptrevision

**Besitzt allein:** Migrationsschritt M-C mit allen Schema-/Pin-/Fixture-Dateien;
Scope-Trigger einschliesslich UPDATE-OF-Listen und alle benötigten Bindungsfunktionen.
**Konkrete Consumer-Ownership:** `component_assignment_store.py` (exakter DTO/Append/Replace),
`workflow_partial_form.py` (`_assignments`, `parse_menu_item_form`),
`workflow_partial_store.py` (`_validate_item`, tatsächlicher POST-Writer `persist_menu_item`),
`admin/workflow_routes.py`, `admin/rendering.py` (`menu_form_values`),
`templates/admin/menu_editor.html`, `workflow_store.py` (Load/Replace),
`workflow_copy_store.py` (`_clone_tree`), `workflow.py` (bestehender Menü-CSV-Vollimport),
`workflow_review.py` (Payload/Tokenvergleich), `workflow_review_context.py` (Wochenkontext).
Zusätzlich `component_catalog_store.py`, dessen vorhandene Komponentenformulare und
`admin/menu_collection_store.py` für Food-Bindung bzw. Readback; `component_effects.py`,
`workflow_form.py` und `workflow_snapshot.py` mindestens vollständig auf Erhaltung prüfen.
Keine Änderung am öffentlichen Snapshot-Format. Root weist vor R5 die konkrete bestehende
Vorlagenpflege für `dish_templates.recipe_id` samt Tests zu; ohne Writer/Readback/Auswahl ist
diese zweite Rezeptbindung ausdrücklich **nicht geliefert** und BAS/REC bleiben dafür offen.
**Besitzt neu:** `reference_scaffold/tests/test_recipe_menu_binding_db.py`.
**Abhängig von:** R1 und R2 (bestehende Rezeptauswahl), integriertes B3 für Food-Bindung.
**Einziges Paket dieser Welle, das den Planungspfad berührt, und
deshalb das grösste Risiko dieser Welle.** Root teilt es vor Ausführung in serielle kleine
Pakete R5a (vollständiger DB-/DTO-Vertrag), R5b (Writer/Readback/Copy/CSV), R5c (Review/Editor
und übrige zugesagte Bindungen). Ein Zwischenstand mit nur nullable Spalte ist keine Abnahme.
R5a registrierte Migrationen werden von R5b/c nicht nachträglich geändert.

Inhalt: optionale **zusätzliche** Rezeptrevision neben `component_id`, kein XOR und kein
stilles Ersetzen bestätigter Katalogmetadaten. Exaktes Drei-Feld-Assignment aus §5.3 mit
UUID-Auflösung im Standort, Auswahl und ausdrückliches Ablösen im Menüeditor. Legacy-DTOs
ohne Rezeptfeld dürfen bestehende nichtleere Bindungen nicht verlieren. Create/Replace,
Append/Umsortieren, Readback und Vorwochenkopie erhalten dieselbe Revision. Menü-CSV-Vollersatz
verweigert destruktiven Ersatz auch bei reiner Rezeptbindung. Food-/Vorlagenbindung brauchen
jeweils Auswahl, Readback, Änderung, Archivierungsverhalten und ausdrückliche Auflösung des
Vorschlags auf eine festgeschriebene Revision; eine vorgeschlagene Rezept-ID ist keine automatische Bindung.

**Ausdrücklich nicht enthalten:** jede Änderung am Publikations-Snapshot. Die veröffentlichte
Nutzlast bereits veröffentlichter Wochen bleibt byteidentisch. Interner Review-Context,
DTOs, Hash und Anzeige werden ausdrücklich nach §5.3 erweitert.

**Akzeptanz.** Reale nicht-NULL-Roundtrips über alle oben benannten Pfade. Eine metadatahaltige
Katalogposition behält nach zusätzlicher Rezeptbindung Milch, Herkunft CH und bestätigte
Labels in allen drei Auto-/Manual-Modi und mit gemischten Positionen. Reine Rezeptpositionen
bleiben unbekannt oder manuell bestätigt. Standortfremde Verknüpfung wird auch beim alleinigen
UPDATE der Rezept-FK abgelehnt. Bindungswechsel unter ursprünglicher Actor-/Item-Erwartung
versioniert genau das betroffene Item einmal, setzt Review zurück und auditiert atomar.
Textgleicher Revisionswechsel und Wechsel zurück machen alte Tokens ungültig; paralleler
Review/Write ist konsistent, Copy übernimmt keine Freigabe, Nachbarmenübelege und unabhängiger
Wochenkontext bleiben erhalten. `test_admin_workflow_snapshot_contract.py` und
`test_public_contracts.py` bleiben unverändert grün; bestehende Publikation hat denselben Hash.

**Gate.** Reales PG plus die vollständige Publikationsregression. Dieses Paket wird nicht ohne
Root-Abnahme integriert.

---

### R6 — Importgrenze CSV und JSON

**Besitzt neu:** `reference_scaffold/cafeteria/recipe_import.py`, Vorschauroute und Template,
`reference_scaffold/tests/test_recipe_import_db.py`,
`reference_scaffold/tests/test_recipe_import_browser.py`.
**Besitzt mit:** Migrationsschritt M-D.
**Berührt:** `docs/CSV_IMPORT_EXPORT.md` (neuer Abschnitt Rezeptschema).
**Abhängig von:** R1, Schema-/Pin-Übergabe nach R5/M-C und serielles UI-Wiring nach §1.

Inhalt: Datei hochladen, validieren, zeilenweise Fehler anzeigen, Dubletten anzeigen,
transaktional übernehmen. Nur CSV und JSON nach dem Dishboard-eigenen Schema. Das CSV folgt den
bestehenden Konventionen aus `docs/CSV_IMPORT_EXPORT.md`: Semikolon als Trennzeichen, UTF-8 mit
optionalem BOM, führende Spalte `schema_version`.

**Akzeptanz.** Ein Stapel schreibt vor der Übernahme nichts in `recipes`; eine fehlerhafte Zeile
verhindert die Übernahme des Stapels; Grössen- und Zeilengrenzen greifen; unbekannter
Inhaltstyp wird abgelehnt; `source_kind='file_import'` und Quelle stehen auf jedem übernommenen
Rezept und jeder importierten Mengenzeile samt Abrufzeit und Referenz; Dezimalstellen werden
nicht still gekürzt. Actor-/Stapel-/Zielversionen, Standort, Zielwrite und Audit werden atomar
geprüft; doppelte Übernahme ist ausgeschlossen. `recipe.import` wird serverseitig erzwungen
(Editor bekommt 403), Import erzeugt nie bestätigte Allergene/Frei-von-Labels.

**Nicht enthalten:** XLSX, Schema.org, Pauli. Jedes davon ist ein eigenes Paket und braucht
zuvor eine reale, berechtigte Beispieldatei.

---

### R7 — Rezeptdruck, erste nutzbare Stufe

**Besitzt neu:** `reference_scaffold/cafeteria/admin/recipe_pdf.py`,
`reference_scaffold/tests/test_recipe_pdf.py`.
**Abhängig von:** R1 und R3.

Inhalt: Rezept-PDF auf der bestehenden fpdf2-Basis mit Logo, Portionen, Zutaten, Schritten,
Bild und automatischer Legende. Lange Rezepte dürfen lesbar mehrseitig sein. Die Einseitenpflicht
für Wochenpläne bleibt unberührt.
Einkaufsdruck ist ohne den noch offenen REC-003-Einkaufslistenvertrag nicht Bestandteil
dieses Pakets und wird damit nicht als geliefert geführt. R7 hängt fachlich an R1/R3, nicht R5.

**Akzeptanz.** Erzeugtes PDF wird geöffnet und geprüft, nicht nur der HTTP-Status; ein langes
Rezept bricht lesbar um, ohne abzuschneiden; Legende zeigt nur tatsächlich dargestellte Symbole;
`test_week_pdf*.py` bleiben unverändert grün.

---

## 3. Freigabegrenzen

**Grenze 1 — erste nutzbare Auslieferung: B1 + B2 + B3 + R1 + R2.**
Stammdaten und Rezepte sind vollständig pflegbar, durchsuchbar und revisionierbar. Es besteht
noch keine Verbindung zu Menüs, Publikationen oder Ausgaben. Nach Nutzereingaben sind diese
Tabellen nicht ungenutzt: kein Drop und kein Restore auf ältere Daten/IAM-Versionen als
Rückbau. Nur ein zum aktuellen Schema kompatibler Forward-Fix unter Erhalt aller Daten ist
zulässig. Erforderlich sind das reale PG-Gate, das Browser-Gate und die
unveränderten bestehenden Suiten.

**Grenze 2 — Menübezug: + R3 + R4 + R5 + R6.**
Erst hier wird der Planungspfad berührt. Zusätzlich erforderlich: vollständige
Publikationsregression und der Nachweis, dass eine bestehende veröffentlichte Woche ihren
Inhaltshash behält.

**Grenze 3 — Druck: + R7.** Zusätzlich erforderlich: echter PDF-Nachweis und fachliche
Druckabnahme.

---

## 4. Abdeckung der Backlog-Verpflichtungen

Die Tabelle beschreibt **geplante** Abdeckung nach Umsetzung und unabhängiger Abnahme,
keinen gegenwärtigen Fertigstatus. Teilweise heisst: die ID bleibt auch danach offen.

**BAS-001 «Grundlagen & Lager»**

| Verpflichtung | Paket | Abdeckung |
|---|---|---|
| Zutaten und Lebensmittel zentral pflegen | B2, B3 | vollständig |
| Komponenten | vorhanden, `menu_components.food_id` in R5 samt Writer/Readback/Editor | erst mit vollständig geprüftem Bindungsweg |
| Einheiten | B1, B2, B3 | reine Logik, Persistenz und Pflege gemeinsam erforderlich |
| Kategorien | B2, B3 | vollständig |
| Tags | B2, B3 | vollständig für Pflege; Serienzuweisung und Suche bleiben REC-006 |
| Lagerorte | B2, B4 | Schema und Bedienung gemeinsam erforderlich |
| Bestände mit Rezepten und Einkauf verbinden | B4 liefert Orte und Verknüpfung | **teilweise** — Journal, Saldo und Buchungen sind INV-001; BAS-001 bleibt bis dahin offen |
| Vorhandene Stammdaten wiederverwenden | B2, M-C | vollständig; kein Bestand wird ersetzt |
| Tandoors Lagerfunktionen gesondert prüfen | offen | nicht in dieser Welle; keine Kompatibilitätsaussage |

**REC-001 «Rezeptverwaltung»**

| Verpflichtung | Paket | Abdeckung |
|---|---|---|
| Wiederverwendbare Rezepte | R1, R2 | vollständig |
| Bilder | R3 | vollständig |
| Zutaten, Mengen, Einheiten | B1, B2, R1 | vollständig nach gemeinsamer Abnahme |
| Portionen | B1, R1, R2 | vollständig |
| Geordnete Schritte | R1, R2 | vollständig als Klartext |
| Quellen | R1 (`source_kind`, `source_url`, `source_note`) | vollständig |
| Mit vorhandenen Menüs und Komponenten verbinden | R5a–c | offen bis alle drei Bindungswege tatsächlich bedienbar und geprüft sind |
| Kochbücher und Sammlungen | R4 | vollständig |
| HugeRTE prüfen | Vertrag §10, [lokaler Prüfbericht](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md) | **1.0.13 lokal browsergeprüft:** Richtext funktioniert, eine Style-CSP-Verletzung bleibt; Silver ist kein vollständiges Tabler-UI. R-RTE und Produktabnahme offen, keine Technologiefreigabe oder Produktinstallation. |

Grenze 2 allein beweist keine vollständige REC-001-Abnahme. Offene Bindungswege und die
vollständige HugeRTE-CSP-/Tabler-Integration bleiben nach der lokalen Eignungsprobe offen; Rich-Text ist keine Voraussetzung
für die erste Klartext-Rezeptverwaltung. Einkaufsdruck bleibt REC-003/REC-007-Folgeumfang.

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
