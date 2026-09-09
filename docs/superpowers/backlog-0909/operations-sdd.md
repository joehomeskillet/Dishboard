# Operations-Slice SDD — CALC-001, INV-001, ORD-001, PKS-001, TRN-001, OPS-001

Stand: 9. September 2026. Planbasis `e813806b51fb5efaef5d5755c292f8027ce1b2eb` (Root-Integration, Schema 26). Der ursprüngliche Planungsschnitt nennt Produktion `693eb74f1a54bd97616dbfc8e0f90bdc1197f508`, Schema 25. Runtime-Nachtrag laut Root: Rezept-PDF inzwischen auf `5f5f6cb`, Schema 25, Container `6e6cfcb`, seit 23:25:32 UTC gesund; öffentliche HTTP-Belege folgen separat. Schema26/27-Integration ist damit nicht deployed. Dieses Docs-WP hat keinen Livezugriff und ersetzt keine Releaseabnahme. Dieser Text beschreibt den Umsetzungsvertrag der Operations-Planung.

Portable relative Links. Maschinenlesbare Arbeitspakete: [operations-wps.json](operations-wps.json). Root-Bindungsvertrag: Worktree `sdd-backlog-root-0909`, Datei `.claude/planning-contract.md`. Quellprüfung der 35 IDs: `/nvmetank1/projects/rag-stack/.claude/reports/wp-5f432dde609e.md`. Fachquellen: [BACKLOG.md](../../BACKLOG.md), [SDD v3.0](../../SDD_Klinik_Suedhang_Cafeteria_v3.0.md), [Entwurf §11](../../design/2026-09-05-screens-vorlagen-verwaltung.md#11-kalkulation-warenwirtschaft-und-gastro-übersetzer), [BAS/REC-Datenvertrag](../../design/2026-09-06-bas-rec-data-contract.md), [OPS-001 SDD](../../design/2026-09-06-ops-bereiche-zeiten-sdd.md), [Tabler-Vertrag](../../design/admin-tabler-contract.md).

## 0. Bindung, Besitz und Nicht-Ziele

Operations besitzt ausschliesslich CALC-001, INV-001, ORD-001, PKS-001, TRN-001 und OPS-001. Recipe besitzt BAS-001 und REC-/NUT-/OFF-IDs. Root besitzt globale SDD, UI/Screens/Templates/IAM/API/QA/DATA und die DAG-Assemblierung. Keine doppelten Knoten.

**Querschnittanker, die dieser Slice nicht definiert.** Operations hängt daran, dupliziert sie nicht: `MP-BAS-SCHEMA27` (DB-FREEZE `972f785f0b97`, Root-Abnahme offen), `MP-BAS-FOUNDATIONS` (aktiv `34b1b5212bfd`), `MP-REC-BINDINGS` (aktiv `538a38904ef6`), `MP-REC-DATA-DRAFTS` (reviewed Entwurf `7d18feb261ca2d8341d2dd0fc8799f682e073f81`, keine Küchenfreigabe/kein Import), `MP-REC-PDF-RELEASE`, `MP-REC-IMPORT-PARSER` (lokal reviewed `7800e39`), `MP-REC-SNAPSHOT-V2`, `MP-REC-FREEZE-V2`, `MP-REC-IMPORT-BATCH`, `MP-REC-PLAN-PORTIONS`, `MP-REC-SHOPPING-AGGREGATE`.

**Architektur, die dieser Slice nicht ändert.**

- Ein Food pro Zutat, vorhandene `measurement_units`, vorhandenes `quantities.py`. Kein Float, keine zweite Ausbeute neben `recipes.servings` + `servings_unit_id`, keine erfundenen Portion-zu-Masse-Umrechnungen.
- Jedes Food hat mindestens einen echten standortgleichen Lagerort (Schema-27-Vertrag). Lagerorte sind keine Bestände.
- Zubereitetes Food pinnt höchstens eine unveränderliche standortgleiche Rezeptrevision plus Content-Hash. Historische Kosten und historische Darstellung lösen den Pin der eingefrorenen Revision, niemals den heutigen Food-Pin.
- Actor, `authz_version`, Standort, Compare-and-Set, No-op bei Bytegleichheit, ein atomares Versions-/Auditpaar. Der zur tatsächlichen Capability passende SQL-Actor-/Standortguard steht vor Fachschlössern; `lock_operations_actor` ist ein Admin-Guard, kein Ersatz für Editor-Stammdatenrechte.
- Veröffentlichte Menü-Snapshots und historische Rezeptrevisionen werden durch Importe, Backfill, Kalkulation, Inventur oder Übersetzung nicht umgeschrieben.
- Patientenausgaben bleiben preisfrei. Kosten hängen an Rezept und Zutat, nie am Patienten-Snapshot (`patient_payload.py`).
- Keine neue Dependency. HugeRTE, GrapesJS, Puck, PDFme, Pauli-SDK und fremde Wörterbuchpakete sind nicht freigegeben.
- Migration `0024_v26_to_v27.sql` bleibt allein bei `MP-BAS-SCHEMA27`. Folgemigrationen nur serialisiert nach Freeze; dieser Plan hartcodiert keine Versionsnummer 27→28.
- Kein Produktcode, kein SQL, kein Test und kein AGENTS-Edit in diesem Dokumentations-WP.

**Aktive fremde Dateibesitzer (verboten bis Freeze).** Schema-27-Writer: `database/migrations/0024_v26_to_v27.sql`, kanonisches Schema/ACL/Validation/Version-Plumbing. Foundations-Consumer: `master_data_types.py`, `master_data_reads.py`, `master_data_commands.py`, `master_data_store.py`, `master_data_proposals.py`, `admin/master_data_forms.py`, `admin/master_data_routes.py`, `templates/admin/grundlagen.html`, `grundlagen_food.html`, `grundlagen_vocabulary.html`. R5b-Writer: Workflow-/Komponenten-Stores und -Routen inklusive `component_assignment_store.py`, `component_assignment_contract.py`, `workflow_store.py`, `workflow_copy_store.py`, `workflow_partial_store.py`, `workflow.py`, `workflow_review.py`. Datenentwurf: `demo/linked_recipe_drafts.json`. Importparser: `recipe_import.py`, `recipe_import_types.py`.

## 1. Ist-Stand je ID (dieser Checkout, Schema 26)

Quellwurzel `reference_scaffold/cafeteria/` und `database/schema.sql`. Zeilen sind Belege am Commit `e813806`, keine neuen Laufzeitgates.

| ID | Soll | Implementiert in e813 | Offen | Statusklasse |
|---|---|---|---|---|
| OPS-001 | Anzeigenamen, Wochenregeln, Schliessungen, datierte Ausnahmen; technische Schlüssel `patient`/`staff_guest` unverändert | `operations_settings.py:219 save_schedule`, `:310 save_area_name`, `:278 save_weekend_switch`; `operations_store.py:27 list_service_exceptions`, `:48 load_dated_service`; `admin/operations_routes.py:253 operations_settings` mit `settings.write`; Schema 20 produktiv | Fachliche Abnahme datierter Ausnahmen in echten Ausgaben; kein dritter Bereich | **deployed / lokal vorhanden**; keine Neuimplementierung |
| CALC-001 | Einkaufspreise, Mengen/Einheiten/Portionen, Ausbeute/Verlust, nachvollziehbare Kosten und Vorschläge; Patienten preisfrei | `quantities.py:114 FoodFactors`, `:149 convert`, `:180 sum_in_base`, `:203 scale_servings`; `menu_item_prices` (`schema.sql:212`) sind **Verkaufspreise in Rappen**, kein datierter Einkaufspreis | Reiner Decimal-Kostenrechner, Preisgültigkeiten, Rezept-/Menüprojektion, Vorgaben/Vorschläge | **nicht implementiert** |
| INV-001 | Zugang/Abgang/Umbuchung/Zählung/Korrektur mit Verlauf; Plan ändert keinen Bestand | `storage_locations` `:3114`, `food_storage_locations` `:3166`, `master_data_store.py:86 replace_food_storage_locations`. Keine Bestandsspalte auf `foods` `:3129` | Bewegungsjournal, Saldo als Summe, UI «Kein Bestand erfasst» | **nicht implementiert**; Orte sind BAS |
| ORD-001 | Bedarf, Lieferantenwarenkorb, geprüfter Export, ausdrücklich bestätigtes Absenden | Nur `foods.source_kind='supplier'` und `food_data_proposals.source='supplier'` (`schema.sql:3146`, `:3221`). Keine Lieferanten-/Bestelltabelle, keine Route | Katalog, Entwurfskorb, Vorschau, Bedarfskopplung, Adapter, Bestätigung/Idempotenz | **nicht implementiert** |
| PKS-001 | Berechtigte eigene/importierte Bestände; kein ungeprüfter 4400/1655-Import | Zielmodell `recipes` `:4152`, Previewparser `recipe_import.py:223 parse_recipe_import` → `RecipeImportPreview`. Kein PKS-Adapter, kein Pauli-Bestand | Rechte, berechtigtes Exportbeispiel, Feldmapping, Adapter auf R6 | **nicht implementiert**; Parser ist Recipe |
| TRN-001 | DE/FR/EN/IT/ES, Quellen, Synonyme, Fachprüfung; kein 50k-Wörterbuch ohne Rechte | Deutsche Labels in `food_symbols.py`, `template_filters.py`, Templates. Keine Übersetzungsdaten oder -routen | Eigenes Fünf-Sprachen-Glossar plus Tabler-CRUD; Textanwendung danach | **nicht implementiert** |

Unterscheidung gegenüber älteren Backlog-Absätzen: OPS-001 ist seit Schema 20 produktiv (`3d35cbb`), in diesem Checkout unverändert nutzbar. B1-Mengenlogik und Rezepteditor/Rezeptkern sind seit dem c9-Release produktiv. Der R6a-CSV/JSON-Previewparser ist lokal integriert; persistierter Rezeptimport fehlt. REC-007-Rezept-PDF und sein Editor waren im ursprünglichen Planungsschnitt lokal; der Runtime-Nachtrag oben nennt die inzwischen erfolgte Root-Bereitstellung, deren öffentliche HTTP-Abnahme separat folgt. Schema27 ist inzwischen als DB-Slice autorverifiziert eingefroren (`5d7edc115ff4f0bb00a36db200f8e686a47a308f`, 58 fokussierte PG16-Tests); Root-Review/Integration, PG18 und Verbraucher fehlen weiterhin. Foundations-UI, R5b-Writer und Datenentwurf bleiben separat reserviert. Diese Statusquellen sind kein neuer Laufzeitnachweis dieses Plan-WP.

## 2. Gemeinsame Ausführungsregeln

### 2.1 Arithmetik und Einheiten

Nur `quantities.py`. `parse_quantity` (12+6), `parse_factor` (11+9), Kontext Präzision 50 und `ROUND_HALF_UP`, Traps auf Invalid/Division/Overflow/Underflow. `convert` nur mit validierter `Unit` und optionalem `FoodFactors`. Masse↔Volumen braucht `density_g_per_ml` derselben Zutat; Anzahl↔Masse `piece_weight_g`; Anzahl↔Volumen beide. `PORTION`/`PRISE` sind nur zum selben Code identisch. `scale_servings` skaliert eine Zeile inclusive kontextabhängiger Zeilen. `sum_in_base` nur gleiche konvertierbare Dimension.

Kosten- und Bedarfsprojektionen zeigen `QuantityError` als **unvollständige Zeile**, niemals als `Decimal('0')`. Eine bestätigte INV-Buchung mit ungültiger oder unmöglicher Umrechnung wird dagegen mit400 vollständig abgewiesen; kein partielles Journal. Fehlender Einkaufspreis bleibt fehlend. Fehlender Umrechnungsfaktor bleibt fehlend. Keine Zwischenquantisierung auf Speicher- oder Rappen-Skala im Kernrechner. `PORTION`→Masse bleibt auch mit Stückgewicht verboten; nur `STK` als Anzahl darf über explizites Stückgewicht konvertieren. Die aus erklärte Rezeptausbeute berechnete Skalierung ersetzt diese Einheitenregel nicht.

### 2.2 Ausbeute

`recipes.servings` plus `servings_unit_id` ist die erklärte Zubereitungsausbeute (`recipe_values.py:137–140`, `schema.sql:4161–4162`). Kalkulation skaliert Zutatenmengen mit `scale_servings` auf die Zielportionszahl. Es gibt **kein** zweites Yield-Feld am Rezeptkopf.

Optionaler Food-`yield_factor` (0 < Faktor ≤ 1) bedeutet den nutzbaren Anteil der eingekauften Menge (Schwund/Putzverlust). Abwesend gilt genau `1` (kein Schwund). Das ist kein Portionsmodell und keine Dichte. Beispiel: 0,750 kg bei Faktor 0,8 → verrechnete Einkaufsmenge 0,750 / 0,8 = 0,9375 kg.

### 2.3 Geld

Einkaufspreise sind `Decimal` in CHF pro Einheit, Währung fest `CHF`. Verkaufspreise in `menu_item_prices` bleiben ganze Rappen (`internal_rappen`, `external_rappen`) und werden **niemals automatisch** geschrieben. Preisvorschläge runden erst an der Vorschlagsgrenze mit `quantize(Decimal('0.01'), ROUND_HALF_UP)` und wandeln zu Rappen; Übernahme ist eine bewusste Cafeteria-Aktion mit CAS auf das Menüitem. Patientenpfade enthalten keine dieser Felder.

### 2.4 Trust, CAS, Audit, Archiv

Jeder Schreiber erhält Original-Actor, Original-`authz_version` und Original-Standort aus dem signierten Formular. Eine Engine-Transaktion umfasst SQL-Verb, Fachschreibung und abgeleiteten Audit; interne Helfer erhalten dieselbe Connection. Die vorhandenen SQL-Guards prüfen und sperren Rollen/Actor sowie den ursprünglichen aktiven Standort. Für Stammdatenaktionen gilt `require_master_data_actor(...,'masterdata.write')`; der Settings-Guard ist kein pauschaler Ersatz für Editor-Rechte. Die Reihenfolge lautet: Rollen/Actor → ursprünglicher Standort → gegebenenfalls Schema27-Graphlock → Einheiten/Vokabular → Lagerorte → Foods → Rezeptköpfe → Journal-/Preis-/Korbaggregate. Innerhalb jeder Klasse nach stabiler interner ID sperren, alte und neue Referenzen vor dem Aggregat sammeln, unter Original-CAS erneut vergleichen. Neu entdeckte Referenzen führen zu409 statt später inverser Sperrnahme. Lagerorte werden immer vor Foods gesperrt.

Den Graphlock brauchen nur Verben, die aktuelle Prepared-Food-Kanten ändern oder eine neue Rezeptrevision einfrieren. Sie nehmen ihn nach Original-Actor/Standort und vor allen Referenzsperren. Journal-, Preis-, Bestell- und normale R5-Menüschreiber erhalten keinen zusätzlichen Graphlock; sie nutzen geprüfte immutable Pins und die bestehende Referenzreihenfolge. Keine Graphsperre in einem späten Trigger oder Receipt. Öffentliche SQL-Verben haben feste Capability, festen search_path und abgeleiteten Audit; keine App-DML oder private EXECUTE-Freigabe. Original-CAS-Konflikt409 rollt alles zurück. Bytegleiche Entwurfsänderung ist No-op0; bestätigte Journal-/Abnahmeaktionen folgen ihrer ausdrücklich beschriebenen Receipt-Semantik.

`audit_events`: Aktion, Entitätstyp, `entity_public_id`, Actor, `details` ohne Secrets, Tokens, HTML oder Roh-SQL. Bewegungen sind unveränderlich; Korrektur ist eine neue Zeile.

Archivierte Foods/Lagerorte bleiben in historischen Journal- und Preiszeilen lesbar, verschwinden aus neuen Auswahllisten. Schema27 verweigert das Entfernen der letzten erforderlichen Lagerortzuordnung einer Zutat, auch bei archivierten Foods; INV legt keinen Ersatzort an.

### 2.5 Oberflächen

Verbindlicher gemeinsamer UI-Master ist `docs/design/2026-09-09-unified-ui-design-system.md` aus dem reservierten Root-Slice (Quell-WT `sdd-backlog-root-0909`), vor jeder UI-Arbeit vollständig lesen; seine Integration ist eine Readiness-Bedingung, kein zweiter Operations-Designauftrag. Bestehender Tabler-/Sicherheitsvertrag bleibt erhalten: zentrale Tokens und Komponenten statt eigener Palette, mindestens44px nach Master, vorhandene grössere48px-Ziele nicht verkleinern, Label-Feld-Bezüge, Fehlerfokus, CSRF, PRG303, `Cache-Control: no-store`, keine URL-Steuerparameter/Query-Rücksprungpfade. Fähigkeitsmodell unverändert: Lesen `draft.read`, Stammdaten/Belege `masterdata.write`, verbindliches Bestell-Absenden nur Admin (`settings.write` oder `*`) **und** explizite Bestätigung. Keine neue Rolle. Sidebar-Einträge in `templates/admin/_workflow_sidebar.html` sind additiv und brauchen einen Shared-Owner-Gate (bestehende Links unverändert).

Browsermatrix nach UI-Master: jede betroffene Route mindestens1440×900 und390×844, repräsentative Seitentypen/gemeinsame Komponenten zusätzlich1024×768,768×1024 und1920×1080. Keyboard, NoJS,200%-Zoom, Kontrast/Fokus, reale Leer-/Fehlerzustände und tatsächliche Fonts/Browser/Zeitzone getrennt belegen. Kein UI-PASS allein aus Template-Render oder Plan; Operations verändert keine zentrale UI-Masterdatei.

### 2.6 Migration, Backfill, Rollback

Persistente Operations-Tabellen erst nach Freeze von `MP-BAS-SCHEMA27`. Root vergibt die nächste freie Migrationsnummer. Vor DDL: keine stillen Defaults für Bestände oder Preise. Ist-Zustand: Produktion hat null Foods, daher kein Preis-/Journal-Backfill. Rollback ist Forward-Fix auf dem dann aktuellen Schema, kein Drop auf v25/v26. Alte v1-Rezeptbytes und Leser bleiben.

### 2.7 Tests und Gates

Bestehende, in diesem Checkout vorhandene Aufrufe (nicht als PASS dieses Plan-WP behauptet):

```text
rtk /tmp/dishboard-shared-venv/bin/python -B -m pytest reference_scaffold/tests/test_quantities.py -q -p no:cacheprovider
rtk /tmp/dishboard-shared-venv/bin/python -B -m pytest reference_scaffold/tests/test_recipe_import.py -q -p no:cacheprovider
rtk /tmp/dishboard-shared-venv/bin/python -B -m pytest reference_scaffold/tests/test_operations_settings_db.py -q -p no:cacheprovider
```

PostgreSQL-Tests überspringen ohne `TEST_DATABASE_URL` (`test_operations_settings_db.py:50`). Browser-Harness: vorhandene `test_admin_operations_browser.py`, `test_admin_tabler_browser.py`, `test_admin_form_contracts.py`. Neue Tests legen vorgeschlagene Dateien an; Root weist den exklusiven DB-Pool zu. Keine erfundenen PASS-Ausgaben.

## 3. CALC-001 — Warenaufwand und Menüpreiskalkulation

### 3.1 Ziel und Grenze

Nachvollziehbare Rezept- und Menükosten aus datierten Einkaufspreisen, Decimal-Mengen, Einheiten und optionalem Schwund. Kalkulationsvorgaben und Verkaufspreisvorschläge sind Folgeschritte. Nährwerte sind NUT-001. Einkaufslistenmengen sind REC-003/`MP-REC-SHOPPING-AGGREGATE`. `menu_item_prices` bleiben Cafeteria-Verkaufspreise.

### 3.2 Datenmodell und DTO

Neue Tabellen (Vorschlag, Migration serialisiert nach Schema27): `food_price_heads` mit CAS und gewählter Preislistenrevision; `food_purchase_price_revisions` als unveränderliche vollständige Edition der Gültigkeitsintervalle eines Foods. Preisänderung hängt eine neue Edition an und verschiebt den Head per Original-CAS. Keine bestehenden Preiszeilen werden per Upsert oder nachträglichem valid_to-Update umgeschrieben.

| Feld | Vertrag |
|---|---|
| `location_id`, `food_id` | Standortgleicher FK auf `foods(location_id,id)` |
| `valid_from date` | inklusiv, Pflicht |
| `valid_to date NULL` | exklusiv; NULL = offen. Ausschluss überlappender Intervalle je Food |
| `unit_id` | existierende `measurement_units`; Dimension muss zur Preisumrechnung passen |
| `unit_price numeric` | `master_quantity`, > 0, CHF je Einheit |
| `currency` | fest `CHF` |
| `yield_factor numeric NULL` | `master_factor`, CHECK NULL oder (0 < x ≤ 1) |
| `price_revision_public_id`, `entry_public_id` | Unveränderliche Identitäten, aufgezeichnet mit Erstellungszeit und Actor |
| `unit_snapshot` | Einheit-UUID, Code, Dimension, base_factor der Preisrevision; keine historische Umrechnung gegen heutige Metadaten |
| `row_version` | Nur der Preis-Head trägt CAS; Revision und Intervallzeilen sind append-only |
| Intervalle | Nicht überlappend innerhalb einer Edition; Prüfung mit PostgreSQL-daterange-Überlappung unter gesperrtem Food/Preis-Head, direkte App-DML verboten |

Kein Preis auf `foods`. Kein denormalisierter «aktueller Preis». Die vorhandene Datenbank installiert pgcrypto, nicht btree_gist. Dieser Plan verlangt keine neue Extension: die serialisierte SQL-Intervallprüfung ersetzt die zuvor unbeschriebene GiST-Exclusion. Zwei konkurrierende Editionen müssen an derselben Head-CAS scheitern oder seriell validiert werden; Eigentümer-/Restoretests prüfen zusätzlich die Intervallinvariante. Ein späterer Extensionwunsch braucht eigene begründete Freigabe.

Reines Modul `reference_scaffold/cafeteria/cost_calc.py` (neu), **ohne** DB:

```text
CostIssue(code, field, message)
CostLine(food_public_id, quantity, unit_code, unit_price, yield_factor,
         status: complete|incomplete, amount: Decimal|None, issues: tuple[CostIssue])
CostResult(currency='CHF', complete: bool, total: Decimal|None, lines: tuple[CostLine],
           servings, servings_unit_code, target_servings)
```

`total` ist `None`, wenn irgendeine Pflichtzeile unvollständig ist. Es wird nicht «0 plus vollständige Zeilen» gezeigt, als wäre der Rest kostenlos. UI darf vollständige Teilzeilen ausweisen, muss die Gesamtsumme aber als unvollständig kennzeichnen.

Öffentliche API des Kerns: `parse_money`, `line_cost`, `scale_recipe_costs`. Keine SQLAlchemy-Imports.

Persistenzmodul `food_price_store.py` (neu): `append_price_revision`, `get_price_on(food, date, price_revision_uuid)`, `list_price_revisions`. Die aktuelle Vorschau darf eine aktuelle Head-Revision ausdrücklich auswählen; ein historischer Beleg verwendet immer seine gespeicherte Preisrevision. Writer analog vorhandener Transaktions-/CAS-Grenze, ohne `master_data_store.py` zu erweitern.

Rezeptprojektion `recipe_cost.py` (neu) liest nur `recipe_reads.get_revision` (`recipe_reads.py:82`). Sie verändert keine Revision. Eine reine Vorschau schreibt keinen Kalkulationsbeleg. Bestätigtes Speichern erzeugt im Folge-WP `MP-CALC-CALCULATION-RECEIPTS` einen unveränderlichen Beleg mit eigener UUID/Request-UUID, Original-Actor/Standort, Revisions-UUID und Hash, Zielmenge und deklarierter Rezeptausbeute, Kostendatum, allen ausgewählten Preisrevisionen/Intervallen, Menge/Einheit/Unitfactor, FoodFactors/Schwund mit Herkunft, Prepared-Pins und validierter Closure, Regelversion samt Regelbytes, Rundungs-/Rechnerversion und Ergebnis. Die gespeicherten Eingaben und Ergebnisse sind kanonisch gehasht; erneute Berechnung benutzt ausschließlich diesen Beleg. Preis-, Food-, Unit-Anzeigenamen-, Faktor-, Regel- oder Pin-Änderungen verändern alte Belege nicht. Unvollständigkeit bleibt ausdrücklich gespeichert, nicht als vollständiger Nullpreis ausgegeben.

### 3.3 Verhalten

1. Kern ohne DB: gegebene Mengen/Preis/Faktoren → Betrag oder unvollständig. Referenzrechnung Kartoffeln: Menge `0.750` `KG`, Preis `2.40` CHF/`KG`, Faktor fehlend → `1.80`; Ziel `4` `PORTION` bei Rezeptausbeute `4` → je Portion `0.45`. Faktor `0.8` → Einkaufsmenge `0.9375` kg, Betrag `2.250`. Fehlender Preis → `amount is None`, Issue `unit_price`. `PORTION`-Zutat gegen `KG`-Preis → `QuantityError` auch mit Stückgewicht; `STK` gegen `KG` ohne Stückgewicht ebenfalls unvollständig, nicht0.
2. Preisledger: Editor/Publisher mit `masterdata.write`. Überlappende Gültigkeit innerhalb der neuen Edition400. Das Schliessen eines offenen Intervalls erfolgt ausschließlich in einer neuen Preislistenrevision; frühere Editionen und Kalkulationsbelege bleiben bytegleich. Identische normalisierte neue Edition ist No-op0.
3. Rezeptprojektion: nur eingefrorene Revision. Ungebundene Zutatentexte ohne `food_public_id` machen das Ergebnis unvollständig. Skalierung über `scale_servings`. Datum der Kostenwahl default `effective_today` (Europe/Zurich), überschreibbar im Admin, nie per öffentlicher Query.
4. Zubereitungsgraph: nur Snapshot-v2 mit geschlossenem Pin. Kindhash erst nach Rekonstruktion seines exakt erreichbaren sortierten Teilindexes prüfen; der gestrippte Flatindex-Knoten allein ist kein Originalhashbeweis. Grenzen8 Kindkanten/Pfad,64 eindeutige Revisionen,4096 expandierte Vorkommen,2MiB kanonisches JSON. Zyklus oder Limitüberschreitung ist Fehler, kein Abschneiden. Die ausdrücklich gewählte und im Beleg gespeicherte Kostenart verwendet entweder den direkten Einkaufspreis des Prepared-Foods oder skaliert dessen Kindzutaten auf die vorhandene deklarierte Kindausbeute. Beides wird niemals addiert. Wiederholte Mengenverwendungen bleiben erhalten. v1 bleibt flach und verwendet seine aufgezeichneten Faktoren; fehlende historische Daten machen den Beleg unvollständig, nie durch heutige Food-Werte ergänzt.
5. Menüprojektion: erst nach `MP-REC-BINDINGS` und `MP-REC-PLAN-PORTIONS`. Gebundene `recipe_revision_public_id` + `recipe_content_hash_sha256` und Zielportion. Ungebundene Menüzeile → unvollständig. Ergebnis nie in `publication_revisions.snapshot_json`.
6. Vorgaben/Vorschläge: Aufschlag/Rundungsregel als `settings`-Dokument `cost_rules.v1` je Standort, CAS über `version`, Pflege mit `settings.write`. Der vorhandene OPS-Writer ist fest an `operations_schedule` gebunden (`operations_settings.py:36–58`); ein enger neuer SQL-Writer nur für cost_rules.v1 benutzt die vorhandenen Actor-/Standortguards. Vorschlag schreibt nicht `menu_item_prices`. Übernahme ist eigener POST `action=apply_price_suggestion` mit vorhandenem `draft.write` nur in `staff_guest`-Entwürfen, Original-Actor/Authz/Standort und Item-/Wochen-CAS, über den nach R5-Freeze vorhandenen Workflowwriter; ein Versions-/Auditpaar.
7. Admin `/admin/kalkulation`: Tabler, `draft.read` GET, Preis- und Belegpflege `masterdata.write`, Regeln `settings.write`, Preisübernahme `draft.write`. Editor besitzt bereits masterdata.write; eine echte Editor403 auf Preis-Pflege wäre falsch. Patienten-Familie der Route404.
8. Wächter: bestehende `patient_key_is_forbidden` und Snapshot-Validator bleiben. Neue Schlüssel `unit_price`, `yield_factor`, `line_cost`, `cost_total`, `rappen_suggestion` auf die Patient-Deny-Liste, bevor irgendetwas persistiert wird.

### 3.4 API

Kein öffentlicher REST-Endpunkt in den ersten Paketen. Interne Funktionen, Admin-SSR. Spätere API-001-Erweiterung ist Root, nicht dieser Slice.

### 3.5 Akzeptanzbeispiele

- A1 Kern: `line_cost('0.750', KG, KG, '2.40', yield=None) == Decimal('1.80')`; fehlender Preis → `complete is False` und `amount is None`.
- A2 Floatverbot: absichtlich gesetzter `decimal.localcontext` mit `Inexact` darf nicht verschluckt werden; kein `float()` im Modul (Ruff/AST-Test).
- A3 Ledger: zwei Intervalle 2026-01-01–2026-09-01 und 2026-09-01–∞; Abfrage am 2026-08-31 liefert den ersten Preis; Überlapp-Insert 400; veraltete `row_version` 409.
- A4 Revision: Frozen-Hash bleibt; Kostenlauf ändert `recipe_revisions` nicht (Zeilenzahl und Hash-Vergleich).
- A5 Patient: GET/POST Kalkulation unter Patienten-URLs 404; Snapshot-Fixture ohne Kostenkeys bleibt gültig; Fixture mit `cost_total` wird vom Patientenvalidator abgelehnt.
- A6 Keine Auto-Verkaufspreise: Vorschlag zeigt Rappen, `menu_item_prices` unverändert bis ausdrückliche Übernahme.
- A7 Preisänderung/Faktoränderung/anderer Prepared-Pin: vorhandener Kalkulationsbeleg reproduziert exakt denselben Betrag und Hash; eine neue Vorschau kennzeichnet die neu gewählte Preisedition.
- A8 Zwei konkurrierende Preiseditionen blockieren nachweislich; eine veraltete CAS scheitert ohne teilweise Intervall-/Auditänderung. Kein btree_gist vorausgesetzt.

## 4. INV-001 — Bestände, Bewegungen und Inventur

### 4.1 Ziel und Grenze

BAS besitzt Orte und Food↔Ort (`schema.sql:3114`, `:3166`). INV besitzt Journal und Zählungen. `foods` erhält keine Bestandsspalte. Solange weder Bewegung noch bestätigte Zählung existiert, zeigen Oberflächen «Kein Bestand erfasst», nicht0. Eine Planänderung, ein Freeze, ein CSV-Wochenimport oder eine Portionsänderung erzeugt **keine** Bewegung. Verbrauch ist eine ausdrückliche INV-Aktion.

Manueller erster Zugang braucht weder Einkaufsliste noch Menübindung.

### 4.2 Datenmodell

`inventory_movements` (unveränderlich nach Insert):

| Feld | Vertrag |
|---|---|
| `kind` | `receipt`, `issue`, `transfer_out`, `transfer_in`, `count_adjust`, `correction` |
| `food_id`, `storage_location_id` | standortgleich, Zuordnung in `food_storage_locations` muss zum Buchungszeitpunkt aktiv sein |
| `quantity`, `sign` | Menge positiv nach master_quantity; sign exakt +1/-1. receipt/transfer_in nur+1, issue/transfer_out nur-1; count_adjust und correction haben explizites geprüftes Vorzeichen |
| `unit_id`, `unit_snapshot` | Bestehende Eingabeeinheit plus immutable UUID/Code/Dimension/base_factor; keine Floatarithmetik |
| `normalized_base_quantity` | Unveränderliche positive Decimal-Menge in der fixierten Bestandsbasis, einmal bei Buchung ermittelt; Vorzeichen separat |
| `basis_snapshot`, `factor_provenance` | Fixierte Kontoeinheit samt Kontext; tatsächlich verwendete Dichte/Stückgewicht mit Foodversion und bestätigter Quelle/Entscheidung, Eingabemenge und Rechnungsversion |
| `request_uuid`, `request_hash`, `receipt_uuid` | Stabiler Buchungsauftrag und abgeleiteter unveränderlicher Beleg; genau eine Anwendung desselben normalisierten Auftrags |
| `reason` | 1–200 Zeichen |
| `occurred_at` | `timestamptz`, default `clock_timestamp()` |
| `related_movement_public_id` | Pflicht und wechselseitig für Transfer-Paare in **einer** Transaktion |
| `count_public_id` | nur `count_adjust` |

Kein UPDATE/DELETE für die App-Rolle. Korrektur = neue Zeile.

`inventory_accounts` fixiert je Food/Ort beim ersten bestätigten Zugang oder Zählergebnis die Bestandsbasis (Unit-UUID/Code/Dimension/base_factor, kontextuelle Rezeptidentität falls nötig). Es enthält keinen autoritativen Saldo. Diese Basis und alte Buchungsmengen bleiben unverändert. Änderung der heutigen Food-Basiseinheit in derselben Dimension darf die Anzeige umrechnen, aber nie alte Bewegungen. Wechsel in eine inkompatible Dimension oder einen anderen kontextuellen Rezeptbezug sperrt neue INV-Buchungen mit sichtbarem Klärungsbedarf; alte Salden bleiben in ihrer fixierten Basis lesbar. Ein automatisches Rebase mit heutigen Faktoren ist ausgeschlossen; eine solche spätere Fachmigration braucht einen separaten Vertrag und Abnahme.

`inventory_counts`: Entwurf mit CAS, Status `draft`/`posted`; gezählte Menge ist ausdrücklich nichtnegativ, inklusive0, mit derselben Decimal-Präzisionsgrenze (kein positive-only master_quantity-CHECK für dieses Feld). Bestätigen berechnet unter Konto-/Count-Lock die Differenz gezählt minus Originalsaldo. Bei Abweichung genau eine Bewegung mit Betrag abs(Differenz)>0 und sign(Differenz). Bei Differenz0 keine Nullbewegung, aber der Count wechselt einmal zu posted, seine Version steigt einmal, ein Count-Receipt/Audit hält den bestätigten Nullunterschied fest. Erst ein identischer Request-Replay ist No-op0; posted-Zustand wird nicht wegen Nullunterschied offen gelassen.

Saldo ist ausschließlich die Decimal-Summe `sign * normalized_base_quantity` des Journals in der fixierten Kontobasis. Der Reader führt keine erneute Umrechnung alter Bewegungen gegen heutige Food-Basis/Dichte/Stückgewicht durch. Dieselbe Request-UUID plus identischer Payloadhash/Originalkontext liefert nach Autorisierungsprüfung dasselbe Receipt ohne neue Bewegung oder Audit. Abweichender Payload bei gleicher UUID409; neue bewusste Buchung braucht neue UUID. Request-Receipt wird in derselben DB-Transaktion wie Movement/Count geschrieben, damit auch ein verlorenes Commit-ACK sicher wiederholt werden kann.

### 4.3 Verhalten

1. Zugang: Food, Ort, Menge, Einheit, Grund. Ergebnis-Saldo darf 0 nicht unterschreiten? Zugang erhöht. Abgang und transfer_out werden abgelehnt, wenn der neue Saldo < 0 wäre (400, sichtbare Restmenge). Korrektur nach unten bis 0 erlaubt, negatives Lager nur mit `kind=correction` und Grundpräfix `Negativbestand:` **nicht** in Stufe 1 — Stufe 1 verbietet Saldo < 0 vollständig.
2. Transfer: eine Transaktion, zwei Zeilen, gleiche Menge/Einheit/Food, verschiedene Orte desselben Standorts, beide Zuordnungen aktiv.
3. Gleichzeitige Buchungen: Original-Rollen/Actor/Standort, Einheiten/Vokabular, beide Lagerorte sortiert, danach Foods, anschließend Konto-/Journal-/Countaggregate sortiert; nie Food vor Lagerort. Konto-Lock serialisiert Saldoentscheidung und atomaren Append, auch wenn bisher keine Movement-Zeile existiert. Keine neue Graphsperre.
4. Leser `inventory_reads.balance(food, storage) -> BalanceDTO`: `captured: bool`, `quantity: Decimal|None`, aufgezeichnete `unit_code`/Kontextidentität. `captured is False` nur ohne Bewegung und ohne posted Count. Ein ausdrücklich bestätigter erster Nullcount ist captured true/0; ein Nullsaldo nach Abgang ebenso.
5. UI `/admin/inventur` und Anzeige an der Food-Karte: Text «Kein Bestand erfasst» aus dem Reader, nie aus fehlendem JSON-Feld als 0 gerendert. Foundations-Templates nicht umschreiben, solange `MP-BAS-FOUNDATIONS` aktiv ist; Kopplung über expliziten Shared-Owner-Gate nach Freeze.
6. Kein Plan-Debit: Tests ändern Wochenentwurf/Rezeptportionen und zählen `inventory_movements` = unverändert.

### 4.4 Akzeptanz

- I1: kein Journal → Reader `captured is False`; HTML enthält «Kein Bestand erfasst» und nicht «0».
- I2: Zugang 5 `KG` + Abgang 1 `KG` → Saldo `4` `KG` in Basis `4000` `G` bei `base_unit G`.
- I3: Abgang 10 `KG` bei Saldo 5 → 400, keine Zeile.
- I4: Transfer atomar; Abbruch nach erster Zeile unmöglich (Trigger oder zwei Inserts vor Commit, Test killt Verbindung nicht nötig — CHECK wechselseitiger FK in derselben TX und Unique-Paar).
- I5: Plan-POST ohne INV-action → 0 neue Movements.
- I6: Schema-Test: `foods` hat keine Spalte `stock`/`balance`/`quantity_on_hand`.
- I7: Foodbasis G→KG oder heutige Dichteänderung verändert keine historische normalized_base_quantity und keinen Saldo; inkompatible neue Buchung400 mit Klärungshinweis.
- I8: Count5→3 bucht sign=-1/Betrag2; Count3→3 erzeugt posted-Receipt ohne Movement. Identischer Request-Replay liefert exakt denselben Beleg; gleiche UUID mit anderem Inhalt409. Erster bestätigter Count0 ist erfasst.
- I9: Gleichzeitige Abgänge und Lagerortarchivierung beobachten tatsächliche Sperren; keine inverse Reihenfolge zum Schema27-Foodwriter, keine Überziehung/Teilbuchung.

### 4.5 Chargen und tatsächliche Vorbereitungsproduktion

Folge-WP `MP-INV-PREPARED-BATCH-PRODUCTION` ergänzt echte Chargen, nicht nur einen Food-Pin. Eine Charge hat Standort/Food/Ort, unveränderliche Chargen-UUID, manuell bestätigtes Herstellungsdatum, optional manuell bestätigtes MHD (nicht vor Herstellung), exakte RecipeRevision-UUID+Hash und tatsächliche Produktionsausbeute mit bestehender Einheit. Diese beobachtete Produktionsmenge ist kein zweites Rezept-Yield. Keine aus Namen/Beispieldaten geratene Haltbarkeit.

Eine ausdrückliche Produktion bestätigt Original-Preview, ausgewählte verbrauchte Chargen/Orte und Mengen sowie neue Zielcharge. Eine Transaktion erzeugt korrelierte Input-Abgänge und Output-Zugang plus einen Produktionsbeleg; alle oder keine, mit stabiler Request-UUID und Original-CAS. Keine Buchung aus Menüplanung, Rezeptfreeze oder Import. Mehrtägige Verwendung bucht tatsächliche Abgänge derselben Charge; Transfer hält die Chargenidentität. Historische Chargen bleiben auch nach Food-Pin-Änderung der alten Revision zugeordnet. Ablauf-/MHD-Anzeige ist Information, keine automatische Freigabe oder Küchenbestätigung. Akzeptanz: gleiche Charge an zwei Tagen, unveränderte alte Rezeptzuordnung, Teilfehler rollback, identischer Replay einmalig, MHD leer erlaubt und nie automatisch errechnet.

Bestehende Journalzeilen erhalten keine erfundene Charge. Raw-Zugänge und vorhandener Altbestand dürfen eine ausdrücklich als nicht chargenverfolgt markierte Restmenge behalten. Ab Einführung erzeugt jede Prepared-Produktion eine konkrete Charge; deren Abgang/Transfer verlangt die exakte Auswahl. Summe der Chargensalden plus unzugeordnete Restmenge entspricht dem Kontosaldo. Upgradeprüfung: alte Journalbytes unverändert, keine erfundenen Herstellungsdaten/MHD/Recipepins, neue Produktionscharge und alte Restmenge rechnerisch konsistent.

## 5. ORD-001 — Bestellvorbereitung und bestätigtes Absenden

### 5.1 Ziel und Grenze

Zuerst manueller Lieferantenartikel und Warenkorb mit prüfbarer Exportvorschau. Bedarf aus Plan/Bestand folgt `MP-REC-PLAN-PORTIONS`, `MP-REC-SHOPPING-AGGREGATE` und INV-Saldo. Verbindliches Absenden erst nach konkretem, berechtigten Anschluss und expliziter Bestätigung plus Idempotenz. Unbeaufsichtigtes Senden ist kein Lieferumfang. Fehlender Vendor-HTTP blockiert den Entwurfskern nicht.

### 5.2 Datenmodell

`suppliers`: standortgleich, `code` wie Stammdaten (`^[A-Z][A-Z0-9_]{0,15}$`), `name`, `active`, CAS.

`supplier_articles`: `supplier_id`, optionales `food_id` (gleiche Site), `article_code` ≤ 64, `name`, `order_unit_id`, `active`. Artikel ohne Food dürfen in den Korb, machen Bedarfsabgleich unvollständig.

`order_baskets`: Status `draft`, `abandoned`, `send_pending`, `sent`, `send_unknown`; CAS. Vorschau/CSV-Download sind Lesevorgänge und setzen keinen Bestellstatus. Jeder editierbare Artikel sowie der Lieferant haben eigene Version; Korbzeilen behalten eine explizite Artikelreferenz.

Ein signiertes Original-Preview bindet Actor/Authz/Standort, Korbversion, Lieferant-/Artikelversionen, Zieladapter und Empfängeridentität, normalisierte Positionen, exakte CSV-/Requestbytes samt SHA256, Ablaufzeit und stabile Request-UUID. Bestätigung erzeugt atomar einen dauerhaften `order_send_intent` mit diesen unveränderlichen Bytes, Receipt-UUID und Status `pending`; kein Netzwerk in dieser Transaktion. Pro Korbversion/Bestellabsicht nur ein Auftrag, auch bei zwei unterschiedlichen Request-UUIDs.

`order_basket_lines`: Menge `master_quantity`, Einheit, Sortierung 1–64, CAS über den Korbkopf (Zeilenersatz in einer TX).

### 5.3 Verhalten

1. Katalog-CRUD `masterdata.write`, Tabler.
2. Korb entwerfen: manuelle Mengen. Vorschau rendert CSV mit derselben Formelneutralisierung wie `csvio.py` (Zellen, die mit `=`, `+`, `-`, `@` beginnen). PDF nur nach vorhandenem Print-Kind-Store; Stufe 1 ist CSV-Download plus HTML-Vorschau.
3. Bedarfskopplung: max(0, Shopping-Aggregate minus erfasster verfügbarer INV-Menge) bei explizit möglicher Umrechnung aus der fixierten Kontobasis; fehlender Saldo (`captured is False`) oder unmögliche Umrechnung markiert die Zeile `bestand_unbekannt`/unvollständig. Keine scheinbar sichere Menge aus unbekanntem Bestand.
4. CSV-Download heißt «CSV herunterladen», braucht keine Eingabe BESTELLEN und behauptet weder Bestellung noch Lieferantenzustellung. Er verwendet dieselben neutralisierten Bytes wie die Vorschau. Kein LocalExportSender, keine leere Senderhierarchie und kein ungeprüfter lokaler Exportpfad. Das separate `MP-ORD-ADMIN-PREVIEW` liefert diesen nutzbaren Ablauf bereits ohne Lieferantenanschluss.
5. Verbindliches Absenden erst mit nachgewiesenem Anschluss: eigener CSRF-POST `action=confirm_send`, `confirm_text=BESTELLEN`, Admin. Originalsignatur und alle Korb-/Artikel-/Lieferantversionen unter passenden Locks erneut prüfen; geändert/abgelaufen409 ohne Sendauftrag. Request-UUID-Replay mit identischen Bytes liefert vorhandenes Receipt, abweichender Inhalt409; eine frische UUID darf dieselbe bereits bestätigte Korbversion nicht erneut bestellen.
6. Dauerhafte Zustände `pending → dispatching → sent | failed_before_send | unknown_result`. Ein kurzer Claim-TX mit Compare-and-Set/Fencing verhindert zwei Sender. Erst nach Commit arbeitet der konkrete freigegebene Adapter ohne DB-Locks am Netzwerk. Ein kurzer Abschluss-TX speichert den belegten Lieferanten-Receipt oder die begrenzte Fehlerklasse. Nach Verbindungsabbruch/Prozessverlust ist ein bereits geclaimter Auftrag unknown_result, niemals automatisch «fehlgeschlagen» oder «gesendet».
7. Kein pauschales Exactly-once-Versprechen über HTTP/Dateisystem. Bei unknown_result erst Lieferantenstatus mit derselben Request-UUID abgleichen. Nur wenn der konkrete Anschluss nachweislich dieselbe Idempotenz-ID dedupliziert, ist höchstens ein dokumentierter Transport-Retry mit exakt denselben Bytes zulässig; sonst manuelle Klärung und keine erneute Sendung. Ein neuer Browser-POST oder Prozessneustart setzt dieses Budget nicht zurück. Bestätigte Aufträge werden bei Source-Rollback nicht auf draft zurückgesetzt. Kein unautorisierter Cron; Fortsetzen/Abgleich gehört zur ausdrücklich bestätigten Absicht.

### 5.4 Akzeptanz

- O1: Korb speichern, Preview und CSV-Download bleiben draft; kein Sendauftrag, keine Lieferantenverbindung, kein BESTELLEN für Download.
- O2: Vorschau enthält neutralisierte Formelzelle.
- O3: `confirm_send` ohne `BESTELLEN` → 400, Status unverändert.
- O4: Doppelte Request-UUID/gleiche Bytes → gleiches durable Receipt/ein order.confirm-Audit; geänderte Bytes409; auch neue UUID für dieselbe bestätigte Korbversion sendet nicht erneut.
- O5: Editor-Rolle 403 auf `confirm_send`.
- O6: kein `requests`/`httpx`-Import in ORD-Modulen der Stufe 1 (AST-Test).
- O7: Artikelversion nach Preview ändern →409 ohne Intent. Prozessabbruch vor Claim, nach Claim und nach tatsächlichem Versand wird gesondert geprüft; unknown_result kann nicht blind neu senden. Netzwerk läuft ohne offene DB-Fachlocks. Ein autorisierter Adaptertest beweist, welche Idempotenz/Abfrage der echte Anschluss tatsächlich liefert.

## 6. PKS-001 — Berechtigte Rezeptbestände und Pauli

### 6.1 Ziel und Grenze

Eigene und **importberechtigte** Bestände. Herstellerangabe «über 4'400 PKS, davon 1'655 Pauli» ist Referenz, keine Liefermenge. Historische PDFs (Export Juni 2021, Produktübersicht Juni 2023) sind kein aktueller API-Nachweis. Adapter schreibt nicht selbst; er erzeugt `RecipeImportPreview` und nutzt `MP-REC-IMPORT-PARSER` / `MP-REC-IMPORT-BATCH`. XLSX bleibt eigenes Recipe-Paket.

### 6.2 Pakete

1. **Rechte-Recherche** (kein Code): dokumentieren, welche Nutzung (Servermodul, Dateiexport, welche Rezepte) der Betreiber berechtigt hat. Ergebnisdatei unter `docs/superpowers/backlog-0909/pks-rights.md` erst im Recherche-WP, nicht in diesem Plan als Fakt.
2. **Export-Fixture** `AWAITING_EXTERNAL`: eine berechtigte Datei plus Versionsangabe im Testordner `reference_scaffold/tests/fixtures/pks/`. Ohne Datei kein Mapping-WP READY.
3. **Feldmapping**: PKS/Pauli-Felder → bestehendes `recipe_payload`-Feldset (`recipe_values.py:133`). Unbekannte Felder → `RecipeImportIssue`, keine stillen Drops kritischer Mengen. Dubletten über Titel wie bestehender Parser (`recipe_import_types.py:25 RecipeImportDuplicate`).
4. **Preview-Adapter** `pks_import.py`: `parse_pks_import(data, filename, content_type, fetched_at) -> RecipeImportPreview`. Dateigrenze analog Parser (5 MiB, UTF-8, kein NUL). `recipe_import.py` nicht forken. Übernahme nur über Recipe-Batch.
5. **Batch**: hängt an `MP-REC-IMPORT-BATCH`. Operations liefert nur den Adapteraufruf, keinen zweiten Importstapel.

### 6.3 Akzeptanz

- P1: Recherche nennt Quelle, Datum, ob Nutzungsrecht vorliegt; ohne Recht bleibt Adapter `AWAITING_EXTERNAL`.
- P2: Fixture-Hash und Version im Test fest; Parser-Ausgabe `is_valid` nur bei vollständigen Pflichtfeldern.
- P3: keine Behauptung, 4400 Rezepte lägen im Repo.
- P4: Adapter ändert keine `recipes`-Zeile (Unit ohne Engine).

## 7. TRN-001 — Gastro-Übersetzer

### 7.1 Ziel und Grenze

Eigenes, quellenbezogenes Fachglossar mit genau fünf Sprachfeldern `de`, `fr`, `en`, `it`, `es`, Synonymen und Prüfstatus. Deutsche UI-Labels erfüllen die ID nicht. Anbieterumfang «rund 50'000 Begriffe» ist keine zu installierende Datei. Keine Maschinenübersetzungs-API, keine neue Dependency.

### 7.2 Datenmodell

`glossary_terms`: Standort, CAS, `source_kind` in `manual|file_import|url`, Herkunftspflicht analog Foods, `status` in `draft|reviewed|rejected`. Texte `master_text(..., 200, false)` — leer in draft erlaubt. CHECK ausschließlich reviewed ⇒ alle fünf Sprachen nach Normalisierung nicht leer, also `status <> 'reviewed' OR complete_languages`. Vollständige drafts und rejected-Zeilen bleiben erlaubt; Vollständigkeit erteilt keine Fachfreigabe. Review erfolgt ausdrücklich mit Actor/CAS/Audit. `synonyms jsonb` Array≤64, jedes Element `{lang,text}` mit Sprachcode de/fr/en/it/es.

### 7.3 Verhalten

1. Tabler-CRUD `/admin/glossar`, `draft.read` / `masterdata.write`.
2. Review-Aktion setzt Status nur bei vollständigen fünf Feldern.
3. Anwendung auf Rezept-/Menütexte (`MP-TRN-RECIPE-MENU-APPLY`) ist ein **Vorschlag** am Entwurf, keine Mutation veröffentlichter Snapshots und keine Mutation historischer `recipe_revisions`. Lookup exakt und nur reviewed, kein Fuzzy, der den Fachsinn ändert. Direkte Verbraucher sind die vorhandenen recipe_forms/recipe_routes und workflow_routes/rendering mit rezepte_editor.html/menu_editor.html; nach deren Owner-Freeze ergänzen sie sichtbare Vorschläge. Nur die ausdrückliche normale Speichernaktion nutzt die vorhandenen Commands mit Originalkontext und Ziel-CAS. Kein neuer Recipe-/Workflowwriter.
4. Public/Signage bleiben in Stufe 1 deutsch; Mehrsprach-Ausgabe ist ein späteres Root-UI-Paket.

### 7.4 Akzeptanz

- T1: Review mit leerem `it` → 400.
- T2: Synonym > 64 → 400.
- T3: Freeze/Publikation nach Glossar-Edit ändert alte Snapshot-Bytes nicht.
- T4: keine HTTP-Client-Imports.
- T5: Fünf vollständige Felder bleiben ohne Review-Aktion draft; dieselbe vollständige Zeile darf rejected sein. Nur reviewed mit fehlendem Sprachtext ist ungültig.

## 8. OPS-001 — Bereiche und Zeiten

Vertrag bleibt [2026-09-06-ops-bereiche-zeiten-sdd.md](../../design/2026-09-06-ops-bereiche-zeiten-sdd.md). In e813 vorhanden und seit Schema 20 produktiv. Dieser Slice **implementiert OPS nicht erneut**.

Restumfang:

1. **Regressionsgate** der vorhandenen Tests (`test_operations_settings_db.py`, `test_operations_weekend_db.py`, `test_admin_operations_routes.py`, `test_admin_operations_browser.py`, `test_public_ops_areas_times.py`, `test_signage_ops_areas_times.py`, `test_week_pdf_ops.py`, `test_capture_ops_live_proof.py`). Nicht als in diesem Plan-WP ausgeführt behaupten.
2. **Abnahme datierter Ausnahmen**: ein dokumentierter Feiertag/Betriebsferien-Fall in Admin, Public, Signage, HTML-Druck, Wochen-PDF und API-Snapshot; Zeile gewinnt gegen Vorgabe (`operations_store.py` listet Abweichungen).
3. **Bestehende Profilregression**: `offer_profiles` bleibt `{patient, staff_guest}`. Rename auf «Schüler» ändert nur display_name. Dies ist eine bestehende Schutzbedingung, keine neue Anforderung und kein neuer pauschaler Testmodul-Auftrag. Das stabile WP-ID MP-OPS-NO-THIRD-AREA bezeichnet nur den gezielten vorhandenen Regressionsbeleg.

Codeexistenz ist kein REVIEWED_LOCAL-Gate. MP-OPS-CORE-REGRESSION bleibt PLANNED bis zu tatsächlichen unveränderten Testausgaben auf zugewiesenem Pool. Fachliche Ausnahmeabnahme ist AWAITING_EXTERNAL bis zu benanntem echtem Feiertags-/Betriebsfall, zuständiger Abnahmeperson und zugewiesener Umgebung; ein Plantext oder rein synthetischer Test ersetzt diese Abnahme nicht.

Zusätzliche unabhängige Bereiche sind eine eigene Modellerweiterung ausserhalb dieses Slices.

## 9. Dateibesitz künftiger Implementierer

Neue Module (Vorschläge, nicht in e813 vorhanden):

| Pfad | Slice |
|---|---|
| `reference_scaffold/cafeteria/cost_calc.py` | CALC Kern |
| `reference_scaffold/cafeteria/food_price_store.py` | CALC Ledger |
| `reference_scaffold/cafeteria/recipe_cost.py` | CALC Projektion |
| `reference_scaffold/cafeteria/admin/cost_routes.py` | CALC UI |
| `reference_scaffold/cafeteria/templates/admin/kalkulation.html` | CALC UI |
| `reference_scaffold/cafeteria/inventory_store.py` | INV Writer |
| `reference_scaffold/cafeteria/inventory_reads.py` | INV Leser |
| `reference_scaffold/cafeteria/admin/inventory_routes.py` | INV UI |
| `reference_scaffold/cafeteria/templates/admin/inventur.html` | INV UI |
| `reference_scaffold/cafeteria/order_store.py` | ORD |
| `reference_scaffold/cafeteria/order_export.py` | ORD Vorschau |
| `reference_scaffold/cafeteria/admin/order_routes.py` | ORD UI |
| `reference_scaffold/cafeteria/templates/admin/bestellung.html` | ORD UI |
| `reference_scaffold/cafeteria/pks_import.py` | PKS Adapter |
| `reference_scaffold/cafeteria/glossary_store.py` | TRN |
| `reference_scaffold/cafeteria/admin/glossary_routes.py` | TRN UI |
| `reference_scaffold/cafeteria/templates/admin/glossar.html` | TRN UI |
| `reference_scaffold/tests/test_cost_calc.py` u. a. unten | Tests |

Geteilte Dateien nur additiv nach Shared-Owner-Gate: `admin/__init__.py` (Import), `templates/admin/_workflow_sidebar.html` (ein Nav-Link), `patient_payload.py` nur Deny-Listen-Erweiterung vor CALC-Persistenz, `database/schema.sql` + `permissions.sql` + `validate_schema.py` + `cafeteria/db.py` + `tools/validate_package.py` nur im serialisierten Migrations-WP. roles.py bleibt unverändert; bestehende Capabilities reichen. Gemeinsame Fixtures test_database_invariants.py/test_master_data_db.py erhalten nur die nötigen Versions-/Tabellenzahl-/Ledgerhunks nach Foundations-Freeze, keinen Vollersatz.

Unverändert zu lassen: `quantities.py` (Import erlaubt), `recipe_import.py`, `0024_v26_to_v27.sql`, historische Snapshots und Public-/Signage-Renderer. Foundations-/R5b-Dateien bleiben bis Owner-Freeze gesperrt; spätere ausdrücklich benannte Verbraucher-Hunks, etwa Preisvorschlag-Übernahme oder Glossarvorschlag, brauchen den serialisierten gemeinsamen Besitz im JSON-WP. Read-only Imports zählen nicht als Edit-Wiring. Für jedes WP sind alle nötigen SQL-/Registrierungs-/Formular-/Store-Änderungen tatsächlich in owned_files enthalten; externe Vertragsdateien sind nur Lesequellen.

Zusätzliche vorgeschlagene Module: `cost_receipts.py` und Test für immutable Kalkulationsbelege; `inventory_production.py`, Produktionsformular und Tests für Charge/Herstellung; konkretes `order_send.py` nur nach Anschlussentscheidung. Es wird kein allgemeines Senderframework vorgeschrieben. Migrationen besitzen jeweils die vollständige Kette Migration/Schema/ACL/Validator/Registry/Packagevalidator und ihre fokussierten Version-/Ledgerfixtures. Der Platzhalter `database/migrations/<ROOT_RESERVED_WP_ID>.sql` wird vor READY durch die exklusiv reservierte echte Dateinummer ersetzt. Jede betroffene shared_owner_gate-Dateiliste verweist auf die vollständige Mitbesitzerliste in shared_owner_groups. Root trägt vor READY den konkreten Vorgängerfreeze/Commit und exklusiven Lease ein; erst dann darf der nächste Writer arbeiten. Diese Laufzeitreihenfolge verhindert parallele SQL-/Sidebar-/Storewriter, ohne unabhängige Fachpakete künstlich an Lieferantenrechte zu hängen. Alle fehlenden vorgeschlagenen Pfade sind im JSON als proposed_files markiert; bestehende direkte Verbraucher sind tatsächlich benannt. Quelldaten aus Demo/Hersteller bleiben Vorschläge und liefern weder Nutzungsrechte noch Küchenfreigabe.

## 10. Abhängigkeitsgraph

```text
MP-PKS-RIGHTS-SCOPE                     (READY, research)
MP-TRN-LICENSE-SCOPE                    (READY, research)
MP-CALC-COST-CORE                       (READY, pure)
MP-CALC-PATIENT-GUARD                   (PLANNED, enger bestehender Consumer)
MP-OPS-CORE-REGRESSION                  (PLANNED, tatsächlicher Gate fehlt)
MP-OPS-DATED-EXCEPTION-ACCEPTANCE       (AWAITING_EXTERNAL, echter Fachfall)
MP-OPS-NO-THIRD-AREA                    (PLANNED, bestehende Profilregression)

MP-BAS-SCHEMA27 ──► MP-CALC-PRICE-LEDGER ──► MP-CALC-RECIPE-PROJECTION
MP-REC-FREEZE-V2 ─┘                         └─► MP-CALC-PREPARED-GRAPH (needs SNAPSHOT-V2)
MP-REC-BINDINGS + MP-REC-PLAN-PORTIONS ──► MP-CALC-MENU-PROJECTION
MP-CALC-RECIPE-PROJECTION ──► MP-CALC-RULES-SUGGEST ──► MP-CALC-ADMIN-UI
MP-CALC-PRICE-LEDGER + MP-CALC-PREPARED-GRAPH ──► MP-CALC-CALCULATION-RECEIPTS
MP-CALC-KITCHEN-ACCEPTANCE (external)

MP-BAS-SCHEMA27 + MP-BAS-FOUNDATIONS ──► MP-INV-MOVEMENT-CORE ──► MP-INV-BALANCE-READ
                                                      ├─► MP-INV-TRANSFER
                                                      ├─► MP-INV-NO-PLAN-DEBIT
                                                      └─► MP-INV-COUNT-CORRECTION ──► MP-INV-ADMIN-UI
MP-INV-TRANSFER + MP-REC-FREEZE-V2 ──► MP-INV-PREPARED-BATCH-PRODUCTION
MP-REC-SHOPPING-AGGREGATE + INV-BALANCE ──► MP-INV-DEMAND-COUPLING
                                         └─► MP-ORD-DEMAND-LINK

MP-BAS-SCHEMA27 ──► MP-ORD-SUPPLIER-ARTICLE ──► MP-ORD-BASKET-DRAFT ──► MP-ORD-EXPORT-PREVIEW
MP-ORD-SEND-RIGHTS (external) ──► MP-ORD-CONFIRM-SEND
MP-ORD-EXPORT-PREVIEW ──► MP-ORD-ADMIN-PREVIEW ──► MP-ORD-CONFIRM-SEND

MP-PKS-EXPORT-FIXTURE (external) ──► MP-PKS-FIELD-MAP ──► MP-PKS-PREVIEW-ADAPTER
MP-REC-IMPORT-PARSER ────────────────────────────────────┘
MP-REC-IMPORT-BATCH ──► MP-PKS-BATCH-TAKEOVER

MP-BAS-SCHEMA27 ──► MP-TRN-GLOSSARY-MODEL ──► MP-TRN-CRUD-UI ──► MP-TRN-RECIPE-MENU-APPLY
```

Der Graph zeigt die fachlichen Hauptkanten; operations-wps.json ist die vollständige DAG mit 34 erhaltenen und drei ergänzten IDs. Shared-Owner-Leases stehen zusätzlich vor READY, ihre konkreten Vorgänger werden bei Root-Dispatch eingetragen. Unabhängige Recherche und der pure Kostenkern warten nicht auf Pauli-Dateien. READY-Recherche bezeichnet einen startbaren Quellencheck, keine bereits erteilten Nutzungsrechte.

## 11. Sicherheit

Trust-Boundary ist jede Admin-POST-Route und jeder künftige Sender. CSRF, Capability, Original-Actor, Standortisolation. Journal- und Preisdetails enthalten keine Credentials. ORD Stufe 1 ohne Netz. CSV-Export formula-safe. Patienten-Deny-Liste vor Kostenfeldern. Glossartexte durch bestehende Textnormalisierung ohne `<>`/Steuerzeichen. PKS-Upload wie Recipe-Import: Grösse, UTF-8, kein Pfad im Dateinamen. Keine Secrets in Testdateien oder Planbefehlen.

## 12. Was dieser Vertrag ausdrücklich nicht zusagt

- Keine 4400 PKS-Rezepte, keine 1655 Pauli-Rezepte, keine 50'000 Glossarbegriffe im Produkt.
- Keine unbeaufsichtigte Bestellung, kein Lightspeed-/Optisoft-HTTP ohne Rechte-WP.
- Keine automatische Buchung aus Planung oder Freeze.
- Keine Verkaufspreisänderung veröffentlichter Pläne, keine Preise in Patientenausgaben.
- Kein dritter OPS-Bereich, keine Neuimplementierung von Bereichen & Zeiten.
- Keine Nährwertberechnung, keine OFF-Integration, keine KI-Preisschätzung.
- Kein Rewrite der Migration0024, des Importparsers oder Datenentwurfs; keine Änderung aktiv reservierter Schema-/Foundations-/R5b-Dateien. Nach deren Freeze sind ausschließlich die im JSON mitbesessenen Consumer-/Registryhunks und spätere separat reservierte Migrationen zulässig.

<a id="vertragsdateien-und-lesende-eingaenge"></a>
## Vertragsdateien und lesende Eingänge

`contract_files` und `wiring_files` eines Pakets sind ausschliesslich Dateien, die
dasselbe Paket auch besitzt. Alles, was ein Paket nur liest — Spezifikationen,
Designdokumente, bestehender Fremdcode und Dateien, die ein anderes Paket besitzt —
steht in `read_only_contract_files`. Diese Trennung verbreitert keinen Schreibbesitz
und entfernt keine Verdrahtung; sie macht nur sichtbar, welche Datei ein Paket
tatsächlich anfassen darf.

Drei Punkte sind dabei ausdrücklich festgehalten:

- `MP-CALC-RULES-SUGGEST` besitzt `database/schema.sql`. Die Tabellenauswahl
  `database/schema.sql:settings` ist deshalb kein zweiter Vertragsanspruch, sondern
  ein Quellanker und steht in `source_anchors`. In `contract_files` steht nur der
  reine besessene Dateipfad.
- `MP-ORD-CONFIRM-SEND` führt `reference_scaffold/cafeteria/admin/__init__.py` und
  `templates/admin/_workflow_sidebar.html` bewusst als lesende Eingänge. Sein
  Vorgänger `MP-ORD-ADMIN-PREVIEW` besitzt beide Dateien und verdrahtet die
  Bestellroute dort bereits; dieses Paket ergänzt nur den Aktionshandler in der
  eigenen `admin/order_routes.py`. Entsteht wider Erwarten echte neue Verdrahtung,
  wird sie vor Ausführung vollständig dort besessen statt lesend geführt.
- `MP-CALC-CALCULATION-RECEIPTS`, `MP-INV-PREPARED-BATCH-PRODUCTION` und
  `MP-ORD-ADMIN-PREVIEW` nennen jetzt reale, im Prüfstand verifizierte Quellanker.
  Sie benennen bestehende Muster, an die das jeweilige Paket anschliesst:
  Belegschreibung in derselben Transaktion mit genau einem Versionsschritt
  (`database/schema.sql:record_menu_binding_write_v26`,
  `database/schema.sql:audit_binding_entity_version_v26`), unveränderliche
  Revisionsauflösung und Mengenlogik (`recipe_reads.py:get_revision`,
  `quantities.py:sum_in_base`, `quantities.py:scale_servings`) sowie den
  bestehenden Admin-Routenvertrag mit signiertem Originalkontext und
  Fähigkeitsprüfung (`admin/recipe_forms.py:sign_context`,
  `admin/cookbook_routes.py:can_write`, `roles.py:require_capability`).
  Es wurde kein Symbol erfunden; jeder Anker wurde gegen den Arbeitsbaum geprüft.
