# Rezepte, Grundlagen und Importe

Stand: 9. September 2026, Europe/Zurich. Planungsquellstand
`e813806b51fb5efaef5d5755c292f8027ce1b2eb` (lokal integriert, Schema 26).
Letzter von Root belegter Produktivstand: `5f5f6cb535922db8453c68d871279d6b2e203391`,
Schema 25. Der Integrationsstand ist nicht ausgeliefert.

Dieses Dokument ist die ausführbare Spezifikation für die Backlog-IDs
**BAS-001, REC-001, REC-002, REC-003, REC-004, REC-005, REC-006, REC-007,
NUT-001 und OFF-001**. Die zugehörigen Arbeitspakete stehen maschinenlesbar in
[recipes-wps.json](recipes-wps.json). Der gemeinsame Arbeitsvertrag steht in
[execution-contract.md](execution-contract.md), der Einstieg in
[START.md](START.md), die Gesamtübersicht in [README.md](README.md).

Das Dokument ist bewusst selbsttragend: sämtliche für die Umsetzung nötigen
Schema-27-, Payload-, Sperr- und Hashverträge stehen in den Abschnitten
[4](#4-schema-27-vertrag) bis [7](#7-migration-backfill-und-rollback). Private
absolute Pfade auf Root-Beschlussdateien werden als Herkunftsbeleg genannt, sind
aber niemals die einzige ausführbare Quelle.

---

## 1. Auftrag und Geltungsbereich

### 1.1 Zugewiesene Anforderungen

| ID | Auftrag laut Backlog | Abschnitt |
|---|---|---|
| BAS-001 | Grundlagen und Lager: Lebensmittel, Einheiten, Kategorien, Tags, Lagerorte; Verbindung zu Rezepten und Einkauf | [8.1](#81-bas-001-grundlagen-und-lager) |
| REC-001 | Rezepte, Revisionen, Bilder, Kochbücher und Menübindung | [8.2](#82-rec-001-rezepte-revisionen-und-bindungen) |
| REC-002 | KI-Hilfen und geprüfte Extraktion | [8.3](#83-rec-002-ki-hilfen-und-extraktion) |
| REC-003 | Rezeptplanung und Einkaufslisten | [8.4](#84-rec-003-planung-und-einkauf) |
| REC-004 | CSV/JSON/XLSX und Sammlungsimporte | [8.5](#85-rec-004-dateien-und-sammlungen-importieren) |
| REC-005 | Webseiten-Rezeptimport | [8.6](#86-rec-005-webseitenimport) |
| REC-006 | Suche und Tags | [8.7](#87-rec-006-suche-und-tags) |
| REC-007 | Rezept- und Einkaufslisten-PDF, Drucklayout | [8.8](#88-rec-007-rezeptdruck-und-layout) |
| NUT-001 | Quellenbezogene Produkt- und Nährwertdaten | [8.9](#89-nut-001-produktdaten-und-nährwerte) |
| OFF-001 | Open Food Facts als Vorschlagskanal | [8.10](#810-off-001-open-food-facts) |

### 1.2 Nicht in diesem Dokument

CALC-001, INV-001, ORD-001, PKS-001, TRN-001 und OPS-001 gehören zum
Warenfluss-Plan (`operations-sdd.md`). UI-, Screen-, Vorlagen-Hub-, IAM-, API-,
QA- und DATA-Anforderungen gehören zum Oberflächenplan (`surfaces-sdd.md`).
Wo dieses Dokument solche IDs berührt, benennt es ausschliesslich die
Abhängigkeit, niemals einen zweiten Besitzer.

Insbesondere gilt: **Lagerorte sind keine Bestände.** Journal, Saldo, Chargen und
Bewegungen sind INV-001. Diese Planung liefert dafür keinen Schreibpfad und
zeigt bis zum Vorliegen des Journals ausdrücklich `Kein Bestand erfasst`.

### 1.3 Verwendete Quellen

- [docs/BACKLOG.md](../../BACKLOG.md), Abschnitte 3 und 4 sowie die Zeilen zu
  BAS-001, REC-001 bis REC-007, NUT-001 und OFF-001.
- [docs/design/2026-09-05-screens-vorlagen-verwaltung.md](../../design/2026-09-05-screens-vorlagen-verwaltung.md),
  Abschnitte 5, 10, 11 und 12.
- [docs/superpowers/bas-rec-work-packages-0906.md](../bas-rec-work-packages-0906.md),
  Pakete B1 bis B4 und R1 bis R7 samt Freigabegrenzen.
- [docs/superpowers/backlog-execution-0906.md](../backlog-execution-0906.md),
  Ausführungspfad Stufen 9 bis 12.
- [docs/CSV_IMPORT_EXPORT.md](../../CSV_IMPORT_EXPORT.md) für die bestehenden
  CSV-Konventionen (Semikolon, UTF-8 mit optionalem BOM, führende Spalte
  `schema_version`).
- Tatsächlicher Code und tatsächliches Schema im eigenen Checkout auf
  `e813806b`; alle Quellanker in diesem Dokument wurden dort gelesen.
- Projekt-Governance: `AGENTS.md` liegt nicht im Arbeitsbaum, sondern nur im
  gemeinsamen Projektverzeichnis `/nvmetank1/projects/menuplan/AGENTS.md`. Sie
  fordert GitNexus-Impact vor jeder Symboländerung und `detect_changes` vor jedem
  Commit. Fehlt sie im Worktree, gilt trotzdem der versionierte
  [Ausführungsvertrag](execution-contract.md).
- Herkunftsbelege ausserhalb des Repositories, nur als Nachweis:
  `/nvmetank1/projects/rag-stack/.claude/reports/wp-5f432dde609e.md`
  (Abdeckungsaudit aller 35 IDs) und
  `/nvmetank1/projects/menuplan/.claude/worktrees/sdd-bindings-root-0908/.claude/prepared-food-sql27-contract-0908.md`
  (Root-Beschluss Schema 27, Variante A).

---

## 2. Ausgangsstand und Lieferzustand

Die folgende Trennung ist verbindlich. Sie unterscheidet **produktiv**,
**lokal geprüft**, **laufend in fremdem Besitz**, **nicht implementiert** und
**externe Eingabe fehlt**. Testanzahlen sind Belege einzelner Läufe, keine
Gesamtabnahme.

### 2.1 Produktiv ausgeliefert

| Baustein | Quellpfad; Auslieferungsbeleg separat |
|---|---|
| Mengen- und Einheitenlogik, Decimal-Arithmetik | [`quantities.py`](../../../reference_scaffold/cafeteria/quantities.py): `parse_quantity`, `convert`, `to_base`, `sum_in_base`, `scale_servings` |
| Stammdatenpersistenz und vorhandene Pflege; Lager-Backend ohne daraus abgeleitete B4-UI-Abnahme | `master_data_store.py`, `master_data_commands.py`, `admin/master_data_routes.py`, Schema `foods`, `measurement_units`, `food_categories`, `tags`, `storage_locations`, `food_storage_locations`; vollständige Storage-UI im separaten Foundations-Freeze |
| Lebensmittel-Vorschlagsdienst mit Quelle und manueller Entscheidung | `master_data_proposals.py`, SQL `create_proposal_v21`, `accept_proposal_v21`, `reject_proposal_v21`, Tabelle `food_data_proposals` |
| Rezeptkern, Revisionen, Bilder, Kochbücher, Rezepteditor | `recipe_store.py`, `recipe_reads.py`, `recipe_commands.py`, `admin/recipe_routes.py`, `admin/recipe_revision_routes.py`, `admin/recipe_image_routes.py`, `admin/cookbook_routes.py` |
| Rezeptfilter Titel, Zutat, Tag | `recipe_reads.py:list_recipes` |
| Rezept-PDF-Kern und HTTP | `admin/recipe_pdf.py:render_recipe_pdf`, `recipe_reads.py:recipe_print_input`, `admin/recipe_revision_routes.py` Route `/rezepte/<uuid>/revisionen/<uuid>/druck.pdf` |

Der Rezepteditor und die weissen Public Screens sind seit 8. September 2026,
21:46 Uhr Schweiz live; der Zugriffsverlauf seit 22:34 Uhr. Produktion läuft auf
Schema 25. Rezept-PDF-Kern, HTTP und Vorlageneditor sind seit 9. September
2026, 01:25 Uhr Schweiz (8. September 23:25:32 UTC) mit
`5f5f6cb535922db8453c68d871279d6b2e203391` ausgeliefert. Root meldet
5810 PASS / 18 SKIP im vollständigen Paketgate und Health PASS, Container
`6e6cfcb`, healthy 0. Der authentifizierte Live-Nachweis dieses Releases ist
noch offen. Diese Zahlen stammen aus Root-Receipts, nicht aus diesem Docs-WP.

### 2.2 Lokal geprüft, nicht ausgeliefert

| Baustein | Beleg |
|---|---|
| **R5a**, vollständiger SQL-Bindungsvertrag Menü/Rezept | integriert in `e813806`, Autorcommit `af1ecbe`; Schema 26 in [`database/schema.sql`](../../../database/schema.sql): `menu_components.food_id`, `menu_item_components.recipe_revision_id`, `dish_templates.recipe_id`, `validate_menu_recipe_scope_v26`, `validate_dish_recipe_scope_v26`, `validate_menu_dish_scope_v26`, `begin_menu_binding_write_v26`, `lock_menu_recipe_revisions_v26`, `lock_component_foods_v26`, `record_menu_binding_write_v26`, `record_component_food_write_v26`, `create_dish_template_v26`, `update_dish_template_v26`, `set_dish_template_active_v26`; DB-Tests `tests/test_recipe_menu_binding_db.py`, `tests/test_recipe_binding_migration_db.py` |
| **R6a**, reiner CSV-/JSON-Vorschauparser | integriert in `7800e39`; [`recipe_import.py:parse_recipe_import`](../../../reference_scaffold/cafeteria/recipe_import.py), [`recipe_import_types.py`](../../../reference_scaffold/cafeteria/recipe_import_types.py), Tests `tests/test_recipe_import.py` |
| **Verknüpfter Gerichtsdatenentwurf** | Commit `7d18feb261ca2d8341d2dd0fc8799f682e073f81` im Worktree `complete-dish-data-0908`, Datei `demo/linked_recipe_drafts.json`. Root-Datensatzgate: 31 PASS in 1.36 s. Der Entwurf ist **nicht importiert**. |

Wichtig zu `recipe_import.py`: eine Suche über das gesamte Paket zeigt genau
zwei Vorkommen des Modulnamens, beide innerhalb des Moduls selbst. Es gibt
**keine Route, keinen Store und keine Persistenz** für Rezeptimporte.

Wichtig zu `dish_templates`: die drei SQL-Verben `create_dish_template_v26`,
`update_dish_template_v26` und `set_dish_template_active_v26` existieren, sind
`cafeteria_app` erteilt und DB-getestet. Es gibt jedoch **keinen Python-Aufrufer**;
`dish_template_id` erscheint in Python nur lesend/kopierend in
`workflow_copy_store.py`.

### 2.3 Laufende Pakete in fremdem Besitz

Schema27 und R5b sind autorseitig eingefroren, ihre Root-Integration/Abnahme
ist noch offen; Foundations ist auf `4d5074e` autorseitig eingefroren und unabhängig Root-geprüft;
die gemeinsame Releasefreigabe bleibt offen. Dateien bleiben bis zur ausdrücklichen
Root-Lease gesperrt. Kein Paket dieses Plans darf sie gleichzeitig beanspruchen.

| Anker | WP | Worktree | Besitz |
|---|---|---|---|
| `MP-BAS-SCHEMA27` | `wp-972f785f0b97` | `prepared-food-schema27-0909` | `database/schema.sql`, `database/permissions.sql`, `database/validate_schema.py`, `reference_scaffold/cafeteria/db.py`, `tools/validate_package.py`, `database/migrations/0024_v26_to_v27.sql`, neue fokussierte PostgreSQL-Tests |
| `MP-BAS-FOUNDATIONS` | `wp-34b1b5212bfd` | `linked-foundations-v27-0909` | `master_data_types.py`, `master_data_reads.py`, `master_data_commands.py`, `master_data_store.py`, `master_data_proposals.py`, `admin/master_data_forms.py`, `admin/master_data_routes.py`, `templates/admin/grundlagen.html`, `grundlagen_food.html`, `grundlagen_vocabulary.html`, `grundlagen_location_conflict.html` (11 Produktdateien) und fokussierte Tests |
| `MP-REC-BINDINGS` | `wp-538a38904ef6` | `recipe-menu-binding-writer-0908` | 16 Produktdateien: `component_assignment_store.py`, `component_catalog_store.py`, `workflow_partial_store.py`, `workflow_store.py`, `workflow_copy_store.py`, `workflow.py`, `workflow_partial_form.py`, `workflow_review.py`, `workflow_review_context.py`, `admin/workflow_routes.py`, `admin/routes.py`, `admin/rendering.py`, neu `component_binding_state.py`, `workflow_write_context.py`, `workflow_item_write.py`, `admin/workflow_scope.py` |

Schema27: Autorcommit `5d7edc115ff4f0bb00a36db200f8e686a47a308f`, Autor-PG16
58 PASS / 91.11 s, Root-PG16 58 PASS / 89.89 s. Der unabhängige statische
Review `wp-28783dcbad34` ist ein begrenzter DB-Slice-Review. PG18, kombinierte
Consumerprüfung und Release bleiben offen. Seine historische Angabe zur
Produktionsversion wird hier ausdrücklich korrigiert: Produktion ist Schema25.
Foundations ist autorseitig auf `4d5074e3d8e9249ffa51733fa5fbcd3af781ffa0`
eingefroren (Report12444): 114 PASS / 113.57 s PG16/HTTP/Offline und
35 PASS / 236.86 s Browser. Root bestätigte unabhängig 114 DB PASS /
113.07 s und 35 Browser PASS / 241.91 s sowie Review CLEAN12446. Die gemeinsame
Schema27-Releaseabnahme bleibt offen.
Die reale Storagezuordnung des Gerichtskorpus ist weiterhin eine gezielte
offene Eingabe.

SQL27 darf nicht allein ausgeliefert werden: alte Food-/Freeze-Aufrufer verlieren
EXECUTE, alte App-Versionen lehnen Schema27 beim Start ab.

### 2.4 Nicht implementiert

Für die folgenden Punkte findet sich im Prüfschnitt weder Schema noch Reader,
Writer, Route oder Test:

- Volltext-, Trigram- oder gespeicherte Suche. `schema.sql` enthält kein
  `tsvector`, kein `to_tsquery`, keine `saved_search`-Tabelle; die einzige
  aktivierte Erweiterung ist `pgcrypto`. Titelsuche verwendet heute
  `strpos(lower(title),lower(:search))>0`.
- Serienzuweisung von Tags auf bestätigte Filtertreffer.
- Persistenter Importstapel, Feldzuordnung, Dublettenentscheidung und
  transaktionale Übernahme von Rezepten.
- Schema.org-Adapter, ausgehender Rezept-URL-Abruf, XLSX-Adapter.
- Nährwertpersistenz. `schema.sql` enthält kein `nutrient`/`nutrition`;
  `fhir/mapping.py:nutrition_product` projiziert ausschliesslich Menüangaben und
  ist kein Nährwertmodell.
- KI-Extraktionspfad. `foods.source_kind` und `food_data_proposals.source`
  kennen `ai_assisted` beziehungsweise `ai`; eine Enum-Ausprägung ist kein
  Adapter.
- Open-Food-Facts-Anschluss. `food_data_proposals.source` erlaubt `off`; es gibt
  keinen Adapter, keine Feldzuordnung und keine Abdeckungsmessung.
- Rezeptplanportionen, Einkaufslistenaggregat, Einkaufslistenzeilen und
  Einkaufslisten-PDF.
- Geometrie im Rezeptdrucklayout. `print_template_config.py` erlaubt für das
  Profil `recipe` genau die acht gemeinsamen Eigenschaften `palette`, `font`,
  `text_size`, `logo`, `margin`, `spacing`, `header_text`, `footer_text`; der
  `layout`-Block mit Raster und Bindungen gilt nur für die Wochenprofile.

### 2.5 Fehlende externe Eingaben

| Eingabe | Blockiert | Nicht blockiert |
|---|---|---|
| Reale, berechtigte XLSX-Beispieldatei und Formatentscheid | `MP-REC-IMPORT-XLSX` | CSV-/JSON-Import, Schema.org |
| Freigabe eines konkreten OCR-/KI-Anbieters | `MP-REC-AI-PROVIDER` | Extraktionsvertrag und Vorschauübernahme |
| Offizielle OFF-Feld-/Rechte-/Endpointfestlegung | abhängiger Adapter und realer Fetch | Nährwertpflege |
| Repräsentative berechtigte Schweizer Barcode-Stichprobe | `MP-OFF-COVERAGE` | Feldmapping, Adapter und Anschlussentwicklung mit benannten Fixtures |
| Fachliche Küchen-/Allergenprüfung (DATA-001, Root-Besitz) | fachliche Freigabe und belastbare Mengen-/Allergenabnahme | ausdrücklich beauftragte, sichtbar ungeprüfte Draft-Erfassung |
| Reale Lagerortzuordnung und explizite Food-/Einheitenzuordnung | vollständige Food-Anlage und bestätigter v27-Rezeptimport der betroffenen Zeilen | gespeicherter, korrigierbarer Importentwurf; keine erfundenen Lager |
| Entscheid zu Richtext (HugeRTE 1.0.13, offene Style-CSP-Verletzung) | `MP-REC-RICHTEXT-DECISION` | gesamte Klartext-Rezeptpflege |
| Erweiterungsfreigabe `pg_trgm` durch Betrieb | `MP-REC-SEARCH-TRGM` | Volltextsuche mit Bordmitteln |

---

## 3. Gemeinsames Datenmodell

### 3.1 Identitäten

Jede Zutat verweist auf genau eine kanonische `foods`-Identität desselben
Standorts. Namensähnlichkeit begründet keine Verknüpfung. Alle Mengen verwenden
`measurement_units` und die Decimal-Arithmetik aus `quantities.py`. Es gibt keine
zweite Einheitenliste und keine Gleitkommarechnung.

Tatsächliche Speichergrenzen aus dem Code:

- `parse_quantity`: 12 Vorkomma-, 6 Nachkommastellen, endlich und positiv, keine
  automatische Rundung (`quantities.py:_parse`, `parse_quantity`).
- `parse_factor`: 11 Vorkomma-, 9 Nachkommastellen.
- Rechenkontext: `prec=50`, `ROUND_HALF_UP`, Traps für `InvalidOperation`,
  `DivisionByZero`, `Overflow`, `Underflow` (`quantities.py:_arithmetic`).
- Dimensionen: `mass` (Basis `G`), `volume` (Basis `ML`), `count` (Basis `STK`),
  `contextual` ohne Basisfaktor. Feste Seed-Bedeutungen: `G=1`, `KG=1000`,
  `ML=1`, `L=1000`, `EL=15`, `TL=5`, `STK=1`, `PORTION` und `PRISE`
  kontextabhängig.
- `convert` erlaubt Dimensionswechsel nur über die tatsächlich vorhandenen
  Faktoren des Lebensmittels (`density_g_per_ml`, `piece_weight_g`).
  Kontextabhängige Einheiten sind ausschliesslich als Identität desselben Codes
  zulässig.

### 3.2 Ausbeute

`recipes.servings` und `recipes.servings_unit_id` sind die deklarierte
Produktionsausbeute. Es gibt kein zweites Ausbeutemodell und keine geratene
Portion-zu-Masse-Umrechnung. Skalierung erfolgt ausschliesslich über
`quantities.py:scale_servings`.

### 3.3 Lagerorte

Jedes Lebensmittel erhält mindestens einen aktiven Lagerort desselben Standorts
(`food_storage_locations`). Eine Lagerzuordnung ist **kein** Bestand. Alle
Oberflächen zeigen bis zum Vorliegen des INV-001-Journals den festen Text
`Kein Bestand erfasst`.

### 3.4 Vorbereitete Lebensmittel

Ein Lebensmittel darf genau eine unveränderliche Rezeptrevision desselben
Standorts fest referenzieren (Feldpaar in [4.2](#42-payloadvertrag)). Rezept-UUID
und Inhaltshash werden aus dieser gewählten Revision abgeleitet; es gibt keine
zweite veränderliche Hash- oder Ausbeutespalte am Lebensmittel.

### 3.5 Entwürfe und Freeze

Unvollständige Rezeptköpfe bleiben speicherbare Entwürfe. Erst der
v27-Freeze und der v27-Import verlangen für **jede** Zutatenzeile ein
Lebensmittel, eine positive gültige Menge und eine existierende Einheit sowie
eine nichtleere Zutatenliste. Unvollständige Entwürfe müssen in der Oberfläche
sichtbar unvollständig sein. Werte werden nie erfunden, um einen Entwurf
freezefähig zu machen.

### 3.6 Zwei Graphen

Es existieren zwei streng getrennte Graphen:

1. **Semantischer Schreibgraph.** Bei Schreibvorgängen wird der aktuelle
   Zusammenhang Lebensmittel → Rezept → Lebensmittel über die Lebensmittel-IDs
   im Zutatenarray der jeweils gewählten unveränderlichen Revision traversiert.
   Auch v1-Zutatenreferenzen nehmen daran teil.
2. **Historischer Rendergraph.** Historische Darstellung und Berechnung folgen
   ausschliesslich den eingefrorenen Kindpins und Snapshots. Alte v1-Ausgaben
   werden nie mit heutigen Lebensmitteldefinitionen neu interpretiert.

Die beiden Graphen dürfen nicht vermischt werden.

---

## 4. Schema 27 Vertrag

Dieser Abschnitt gibt den Root-Beschluss (Variante A) vollständig wieder, damit
die Umsetzung ohne den privaten Beschlusspfad möglich ist. Besitzer ist
`MP-BAS-SCHEMA27`; alle anderen Pakete konsumieren ihn.

### 4.1 Reservierung

Schema 27 und `database/migrations/0024_v26_to_v27.sql` sind allein diesem
Writer zugewiesen. Bestehende Migrationsbytes bleiben unverändert. In diesem
Slice entstehen keine Änderungen an R5-Workflow-, UI-, Importparser-,
Arithmetik- oder PDF-Python.

### 4.2 Payloadvertrag

Der bestehende Lebensmittel-Payload wird um genau zwei Bereiche erweitert:

- `storage_location_public_ids`: nichtleere Liste vorhandener aktiver
  Lagerort-UUIDs desselben Standorts. Ein Fehlen ist **keine** leere Liste,
  sondern ein Fehler.
- Optionales, vollständiges Pinpaar
  `prepared_recipe_revision_public_id` **und**
  `prepared_recipe_content_hash_sha256` (64 Zeichen, kleingeschriebenes Hex).
  Ein halbes Paar wird abgelehnt. Unbekannte Felder werden abgelehnt.

Fehlende Pinfelder bei einer Aktualisierung erhalten den bisherigen Pin.
Ausdrückliches `null`/`null` löst den Pin. Die Lagerpflicht bleibt in jedem Fall
bestehen.

### 4.3 Öffentliche Verben

Die folgenden eingefrorenen SQL-Signaturen sind der Consumervertrag:

| Verb | Argumenttypen, in Reihenfolge | JSON-Rückgabe |
|---|---|---|
| `create_food_v27` | `bigint actor, bigint expected_authz, bigint original_location, jsonb payload` | `{public_id, row_version}` |
| `update_food_v27` | `bigint actor, bigint expected_authz, bigint original_location, uuid food_uuid, bigint expected_food_version, jsonb payload` | `{public_id, row_version}` |
| `freeze_recipe_v27` | `bigint actor, bigint expected_authz, bigint original_location, uuid recipe_uuid, bigint expected_recipe_version, text expected_dependency_hash` | `{public_id, recipe_public_id, revision_number, recipe_row_version, content_hash_sha256}` |
| `recipe_dependency_preview_v27` | `bigint original_location, uuid recipe_uuid, bigint expected_recipe_version` | `{recipe_public_id, recipe_row_version, complete, issues, snapshot, dependency_hash_sha256}` |

UUIDs und Hashes sind Textwerte im JSON; Versionen Zahlen, `complete` Boolean,
`issues` ein Array, `snapshot` ein Objekt. Hashes sind 64 kleine Hexzeichen.
Die Vorschau ist `STABLE`, SELECT-only und unter READ ONLY REPEATABLE READ
verwendbar. **Der Service muss `draft.read` prüfen** und den ursprünglichen
aktiven Standort auflösen; der SQL-Reader ersetzt keine HTTP/API/MCP-Autorisierung.
Kein Writeguard, Actorbump, Audit oder Graphlock im Preview.
Kein neuer generischer Dispatcher; interne IDs/Locks/Auditdaten kommen nicht aus
dem Formular. Der freigegebene SQL-Freeze ist der einzige Snapshot-Erzeuger.

### 4.4 Versions- und Auditregel

Eine vollständige erfolgreiche Anlage hat Version 1 und genau einen
Auditvorgang. Eine wirksame Änderung erhöht genau einmal und erzeugt genau einen
abgeleiteten Auditvorgang. Eine bytegleiche normalisierte Aktualisierung erhöht
nicht und auditiert nicht. Kern, Lager und Pin ändern sich atomar. Es werden
nicht zwei `engine.begin`-Stores aufgerufen, und kein Audit bleibt ohne die neuen
Änderungen erhalten.

### 4.5 Mengenkompatibilität

Basiseinheit des Lebensmittels und Ausbeute der gewählten Revision müssen
kompatibel sein: gleiche physikalische Dimension über den unveränderlichen
`base_factor`, oder exakt derselbe kontextabhängige Code innerhalb dieses
Rezeptkontexts. Eine ausdrücklich vorhandene Dichte des Lebensmittels darf Masse
und Volumen verbinden. Ein Stückgewichtsübergang für die vorbereitete Ausbeute
ist in diesem Slice nicht erforderlich. Kein geratenes Gramm je Portion, keine
rezeptübergreifende kontextabhängige Summe, keine Zwischenrundung.

SQL prüft ausschliesslich Eignung und Metadaten. Die tatsächliche Umrechnung und
Decimal-Skalierung bleibt bei `quantities.py`.

### 4.6 Sperrreihenfolge

Alle Pin-Anlagen, -Änderungen, -Entfernungen und der Elternfreeze erwerben genau
**eine** private transaktionale Advisory-Sperre für den ursprünglichen Standort
und einen festen Namensraum des vorbereiteten Graphen. Reihenfolge:

1. Ursprünglicher Akteurs-, Rollen- und Standortguard.
2. Genau diese eine Graphsperre.
3. Danach Einheiten, Vokabular, Lagerorte, Lebensmittel, Rezeptköpfe.

Die Sperre wird nie spät in einem Trigger oder Beleg erworben, nie mit dem
IAM-Bootstrapschlüssel gebildet und nie in normale R5-Menüwriter eingebaut.
Nach dem Warten werden die aktuellen Kanten unter `READ COMMITTED` erneut
gelesen; die ursprüngliche CAS-Erwartung wird unter der zuständigen
Aggregatsperre erneut geprüft. Unveränderliche Kindsnapshots benötigen keine
Sperren auf veränderlichen Köpfen.

### 4.7 Zyklen und Grenzen

Wiederholte Lebensmittel- oder Rezeptidentität auf einem Pfad wird direkt und
indirekt abgelehnt. Ein gemeinsames Kind in zwei Geschwistern ist gültig. Eine
Pinaktualisierung wirkt innerhalb derselben gesperrten Transaktion als
Überschreibung ihrer bisherigen Kante. Archivierte Knoten nehmen an der
Validierung teil. Zwei gleichzeitige Schreibvorgänge F→R1(G) und G→R2(F) dürfen
niemals beide gelingen, auch nicht mit v1-Kindern.

Verbindliche Obergrenzen, jeweils **vor** Expansion, Einreihung oder
Materialisierung eines unbegrenzten Ergebnisses zu prüfen:

| Grenze | Wert |
|---|---|
| Kindkanten je Pfad | 8 |
| eindeutige Kindrevisionen | 64 |
| traversierte Grapharbeitseinträge/Kanten | 4096 |
| expandierte Zutatenvorkommen | 4096 |
| kanonisches v2-Snapshot-JSON ohne Assetbytes | 2 MiB |

Der aktuelle semantische Foodgraph verwendet einen gemeinsamen Arbeitszähler;
die unveränderliche Snapshot-Closure hat getrennte Zähler für Arbeit und
expandierte Zutaten. Diese Implementierungen nicht gleichsetzen. Gezählt wird
bei der Mengenexpansion je Zutatenzeile. Eine Deduplizierung von Snapshotidentitäten darf
legitime wiederholte Mengen nicht verwerfen. Überlauf wird ausdrücklich
abgelehnt.

### 4.8 Fehlerabbildung

Neue Schreibpfade behalten die dokumentierte Abbildung bei; sie ist im Service
bereits vorhanden (`recipe_commands.py:ERRORS`):

| SQLSTATE | Ausnahme |
|---|---|
| `P1901` | `RecipeValidationError` |
| `P1902` | `RecipeActorDeniedError` |
| `P1903` | `RecipeStaleActorError` |
| `P1904` | `RecipeConfigurationError` |
| `22023` | `RecipeNotFoundError` |
| `55000` | `RecipeConflictError` |
| `23505` | `RecipeConflictError` |
| `42501` | `RecipeActorDeniedError` |

Begrenzte Validierungs- und Konfliktmeldungen für Benutzereingaben. Kein roher
SQL-Text und kein Credentialinhalt in HTTP-Fehlern oder Testartefakten.

### 4.9 Legacy-Verben

Jedes anwendungsaufrufbare Altverb, das vollständige Anlage,
Pin-Kompatibilität, Pinvalidierung oder die neuen Freezeregeln umgehen könnte,
wird geschlossen. Unveränderte v21-Metadatenverben dürfen nur bleiben, wenn
Constraints und Guards dieselben Endinvarianten erzwingen. Jede beibehaltene und
jede entzogene Signatur wird mit getestetem Grund aufgeführt. Keine
grossflächigen neuen `EXECUTE`- oder DML-Rechte. Private Guard-, Mutator- und
Graphhelfer bleiben privat.

---

## 5. Revisionen und Snapshots

### 5.1 Bestehende v1-Revision

`recipe_revisions` ist unveränderlich (`recipe_protect_v22` verbietet Update,
Delete und Truncate). Der Inhaltshash ist per Check-Constraint an den Snapshot
gebunden:

```
content_hash_sha256 = encode(digest(convert_to(snapshot_json::text,'UTF8'),'sha256'),'hex')
```

Der v1-Snapshot (`recipe_snapshot_v22`) hat die Schlüssel `schema_version` (Wert
1), `recipe` (Ergebnis von `recipe_payload_v22`), `calculation` (Präzision 50,
`ROUND_HALF_UP`, 6 Mengenstellen, Basen `G`/`ML`/`STK`, `contextual`
= `same-code-only`), `units` und `foods`. `foods` enthält je Lebensmittel
`public_id`, `name`, `row_version`, `density_g_per_ml`, `piece_weight_g`, die
Quellfelder und `factor_decisions` aus akzeptierten Vorschlägen.

**v1-Bytes, v1-Hashes, v1-Leser und die v1-PDF-Ausgabe bleiben unverändert.**

### 5.2 Neuer v2-Snapshot

Der SQL27-Freeze erzeugt die kanonische Form; Python erzeugt keinen zweiten
Snapshot. Top-level sind `schema_version: 2`, **`recipe`** (unveränderte v1-Form),
`calculation`, `units`, `foods`, `prepared_revisions`. Root-Units enthalten auch
Food-Basiseinheiten, deterministisch nach UUID sortiert. Food-Metadaten enthalten
die bisherigen Felder plus Basiseinheitenmetadaten, `storage_locations` mit
UUID/Version/Name und `prepared_recipe: null | {recipe_public_id,
revision_public_id, content_hash_sha256}`. Keine zusätzliche Rezeptausbeute.

`prepared_revisions` ist ein flacher, nach Revisions-UUID sortierter Index aus
`{recipe_public_id, revision_public_id, content_hash_sha256, snapshot}`.
Beim v2-Kind fehlt nur dessen top-level `prepared_revisions`; v1-Kinder bleiben
exakte vollständige terminale v1-Objekte. v1-Foods werden niemals durch heutige
Food→Recipe-Pins zu vorbereiteten Zutaten umgedeutet.

Der versionierte Reader rekonstruiert ein v2-Kind so:

1. Von dessen `foods[].prepared_recipe` aus nur die erreichbaren Einträge im
   Elternindex traversieren, innerhalb der Grenzen aus 4.7.
2. Nach Revisions-UUID deduplizieren, in kanonischer UUID-Reihenfolge sortieren
   und diesen Teilindex als `prepared_revisions` wieder einsetzen. V1 ist terminal.
3. Den rekonstruierten Inhalt gegen den Hash der tatsächlich gespeicherten
   ursprünglichen Childrevision prüfen, mit derselben PostgreSQL-jsonb-Text-
   Kanonisierung. Ein Python-JSON-Serializer wird nicht ungeprüft gleichgesetzt.

Geteilte Enkel bei mehreren Geschwistern müssen exakt gespeicherte Childbytes
rekonstruieren. Fehlende/zusätzliche Indexeinträge, falsche Identitäten und Hashes
werden kontrolliert abgelehnt. Der Hash eines gestrippten Knotens ist **kein**
Originalhash. Reine Consumption fragt keine heutigen Heads, Foodpins oder
Faktoren nach. Benötigte Bilder werden nur für die exakt gewählten Rezept- und
Revisionsidentitäten im vorhandenen RR-Read erhoben, nie über fremde Asset-URLs.

`MP-REC-SNAPSHOT-V2` besitzt den Reader und seine direkten PDF-/Scaling-Consumer:
`recipe_reads.py`, `recipe_types.py`, neuer bounded `recipe_snapshot_v2.py`,
`admin/recipe_pdf.py` und `admin/recipe_scaling.py`; dazu die READ-Hunks
`render_scaled`/`recipe_revision` in `admin/recipe_revision_routes.py` und
`templates/admin/rezepte_revision.html`. Das umfasst auch die erneute Anzeige
nach ungueltiger Ausbeute. FreezePOST bleibt dem nachfolgenden Freeze-WP zugeteilt;
die gemeinsame Routendatei wird ausschliesslich nacheinander bearbeitet.
`tests/test_recipe_scaling.py` gehoert neben den vier Reader-/PDF-Gatedateien dazu.
Der PDF-Renderer akzeptiert
heute ausdrücklich nur schema_version 1; bloss neue DTOs reichen nicht.
V1-Ausgabe bleibt bytegleich, v2-Darstellung und Skalierung nutzen geschlossene
Metadaten und bestehende Mengenlogik. Keine zweite SQL-/Snapshot-Architektur.
Interne rekursive Decimal-Zielmengen duerfen nicht erneut durch die sechsstellige
Storagevalidierung gerundet oder abgewiesen werden. `recipe_snapshots.py` bleibt
als versionsneutrale immutable Konvertierung unveraendert. Root hat diese
zwoelf Dateien nach konkreter Callerpruefung fuer `wp-a05c09994a29` zugewiesen;
die Umsetzung ist begonnen, Laufzeit- und Releaseabnahme bleiben offen.

### 5.3 Abhängigkeitshash und Freeze

Der Vorschauhash deckt ab: angezeigte Lebensmittel- und Lagerortnamen samt
Versionen, Pin, unveränderlichen Kindhash, Einheiten- und Faktormetadaten sowie
den Vollständigkeitszustand. Exakt gehasht wird das kanonische PostgreSQL-jsonb-
Textobjekt der Preview ohne `dependency_hash_sha256`; der Snapshot-Inhaltshash
ist davon verschieden. Der Freeze berechnet unter den Sperren neu,
vergleicht mit der ursprünglichen signierten Erwartung und liefert bei jeder
Abweichung **409**.

Das spätere Formular trägt diesen ursprünglichen Hash in seinem bestehenden
signierten Kontext. Die Erwartung wird beim POST **niemals** neu erzeugt.

---

## 6. Schreibvertrag und Vertrauensgrenzen

### 6.1 Bestehende Grenze

Der bestehende Rezeptservice ist die Vorlage für alle neuen Schreibpfade
(`recipe_store.py`, `recipe_commands.py`):

- Fähigkeit über `roles.require_capability`. Vorhandene Fähigkeiten:
  `recipe.write` bei `Cafeteria.Editor`, `Cafeteria.Publisher` und
  `Cafeteria.Admin`; `recipe.import` bei `Cafeteria.Publisher` und
  `Cafeteria.Admin`; `masterdata.write` bei Editor, Publisher und Admin
  (`roles.py:ROLE_CAPABILITIES`).
- Ursprünglicher Akteur als `ActorExpectation` mit `user_id` und
  `authz_version`; Zielobjekt als `ObjectExpectation` mit `public_id` und
  `row_version`.
- Genau ein Standort, aufgelöst über
  `component_catalog_store.resolve_single_active_location_connection`.
- Lesetransaktionen laufen als `SET TRANSACTION ISOLATION LEVEL REPEATABLE READ
  READ ONLY` (`recipe_reads.connection`).
- Der `safe`-Dekorator bildet Datenbankfehler auf die Ausnahmen aus
  [4.8](#48-fehlerabbildung) ab und lässt keine SQL-Details nach aussen.

Neue Pakete verwenden diese Grenze unverändert weiter. Sie legen keine zweite
Fehlerabbildung, keinen zweiten Standortauflöser und keinen generischen
Dispatcher an.

### 6.2 Menübindung

Der Menü-Schreibpfad besitzt seinen eigenen Guard
`begin_menu_binding_write_v26(actor, authz, location)`. Er verlangt
`read committed`, positive Akteurs- und Berechtigungswerte, setzt
`lock_timeout=5s`, sperrt Rollendefinitionen und Benutzer `FOR SHARE`, prüft
`authz_version` und eine feste Rollenmenge (`Cafeteria.Editor`,
`Cafeteria.Publisher`, `Cafeteria.Admin`) und ruft `master_location`. Der
Aufrufer kann keine Fähigkeit wählen.

Belege werden ausschliesslich in derselben Transaktion wie der genau eine
Aggregatschreibvorgang erzeugt und erhöhen selbst keine Version:

- `record_menu_binding_write_v26` prüft `p_after - 1 = p_before`, sperrt die
  Menüposition `FOR UPDATE`, verlangt `row_version = p_after` und lehnt eine
  zweite Protokollierung derselben Version ab. Der eindeutige Index
  `audit_binding_entity_version_v26` erzwingt das zusätzlich auf Datenbankebene.
- `record_component_food_write_v26` verhält sich für `menu_components` analog.

Standortgrenzen werden von den Triggern `menu_item_components_recipe_scope`,
`dish_templates_recipe_scope` und `menu_items_dish_recipe_scope` erzwungen. Der
Gerichtvorlagen-Trigger sperrt `dish_templates` beim Menüpositionsschreiben
`FOR SHARE`, damit eine gleichzeitige `recipe_id`-Änderung kollidiert.

### 6.3 Öffentliche Projektion

Nur der interne Review erhält Revisionsreferenz und Hash. Öffentliche
JSON-Schlüssel, die Patientenerlaubnisliste, bereits veröffentlichte Snapshots
und deren Hashes sowie die Renderer bleiben unverändert. Kein Import
veröffentlicht automatisch ein Menü. Keine KI- oder Importaktion erzeugt
bestätigte Allergene oder Frei-von-Labels.

### 6.4 Historie

Publizierte Menü-Snapshots und historische Rezeptrevisionen werden durch
Importe, Backfills oder Migrationen niemals umgeschrieben. Quellenkennzeichen
und Allergenvorschläge werden niemals stillschweigend zu bestätigten Tatsachen.
Eine Änderung der Quellart in einem importierten Vorschlag ist eine Entscheidung
vor der Erzeugung neuer Entitäten, keine Erlaubnis, vorhandene Herkunft
umzuschreiben.

---

## 7. Migration, Backfill und Rollback

### 7.1 Nummernvergabe

Der aktuelle Stand ist Schema 26 mit den Migrationen `0001` bis `0023`
(`database/migrations/`) und `db.py:SCHEMA_VERSION = 26`. `0024_v26_to_v27.sql`
ist reserviert.

**Jede weitere Migration wird erst nach dem Freeze ihres Vorgängers nummeriert.**
Kein Paket dieses Plans schreibt eine feste Nummer oder Zielversion in seinen
Auftrag. Die Pakete tragen stattdessen eine `migration_group`; der Orchestrator
vergibt Nummer und Version bei der Reservierung. Vorgeschlagene Dateiform:
`database/migrations/00NN_v<N>_to_v<N+1>.sql`.

Migrationsgruppen dieses Plans, in vorgesehener Serialisierungsreihenfolge:

| Gruppe | Inhalt | Vorgänger |
|---|---|---|
| `prepared-food-27` | vorbereitete Lebensmittel und Lagerpflicht | Schema 26 |
| `recipe-import-batch` | persistenter Importstapel und Übernahmeaudit | `prepared-food-27` |
| `recipe-search` | Volltextspalten, Indizes, gespeicherte Suchen | `recipe-import-batch` |
| `nutrition` | Nährwerte je Bezugsmenge und Nährwertvorschläge | `recipe-search` |
| `shopping-list` | Einkaufslisten, Zeilen, Abhakstatus | `nutrition` |
| `recipe-search-trgm` | `pg_trgm` und Ähnlichkeitsindizes, nur nach Betriebsfreigabe | `recipe-search` |

Die Reihenfolge ist eine Serialisierungsempfehlung für den gemeinsamen
Schemabesitz, keine fachliche Abhängigkeit. Der Orchestrator darf umsortieren,
solange pro Welle genau ein Besitzer für `database/schema.sql`,
`database/permissions.sql`, `database/validate_schema.py`, `cafeteria/db.py` und
`tools/validate_package.py` existiert.

### 7.2 Vorbedingung Lagerpflicht

Vor jeder DDL-, Daten- oder Ledgeränderung der Gruppe `prepared-food-27` lehnt
die Migration ab, wenn vorhandene Lebensmittel — archivierte eingeschlossen —
keine aktive Lagerzuordnung desselben Standorts besitzen. Sie liefert eine
begrenzte, nützliche Diagnose mit Anzahl und Liste. Kein erfundener
Standardlagerort, keine implizite Zuweisung, kein temporäres Gültigkeitsflag,
keine stille Ausnahme.

Eine zulässige alte Datenbank mit fehlender Zuordnung muss **ohne** Änderung von
Schema, Ledger oder Geschäftszustand scheitern, danach eine ausdrücklich
getrennte v21-Zuweisung erlauben und beim erneuten Lauf durchlaufen. Der
tatsächliche Produktivstand enthält null Lebensmittel; ein Datenbackfill ist
gegenwärtig nicht erforderlich. Vollständigkeit wird nach
Löschen-und-Ersetzen-Vorgängen geprüft, nicht bei jedem Zwischenschritt.

### 7.3 Rollback

Schema27 ist eine gemeinsame App/DB-Vertragsänderung. Alte v21-Food-Anlage und
v22-Freeze verlieren ihre App-Freigabe; die alte App kennt Schema27 nicht.
Ein altes Image, das neue Spalten vermeintlich ignoriert, ist kein Rückweg.
Keine erneuten Grants auf die umgehenden Verben, keine v2→v1-JSON-Umschreibung.

`MP-BAS-V27-RELEASE-ACCEPTANCE` verlangt vor Auslieferung integrierte Foods-
Consumer, v27-Freeze und versionierte Reader/PDF-Consumer mit kombinierten
PG/HTTP/Browser- und historischen Bytegates. Root erstellt entweder einen
Schema27-kompatiblen Source-Fallback mit denselben Daten-/Readerverträgen und
prüft echten Imagewechsel auf derselben isolierten DB, oder einen geprüften
Restore des vorherigen DB-/Assetzustands. Ein blosses Versionsfeld-Downgrade ist
verboten. Neue Folgeschemata erhalten jeweils dieselbe konkrete Prüfung.

PG18-Zusatzbeweise bleiben ausdrücklich offen: kanonische UUID-/Textsortierung
unter tatsächlich verwendeter Kollation, rekonstruierte Childhashes, begrenzte
Laufzeit und Lockdauer an 8/64/4096/2-MiB-Grenzen, Restore samt Extension-vor-
Import und ACL-/Ledgerprüfung. Das sind Review-/Releaseanforderungen, keine
bestätigten aktuellen Produktfehler. SQL27 allein darf nicht deployed werden.

---

## 8. Anforderungen

Jede Anforderung enthält Ist-Stand mit Quellanker, Sollverhalten, Datenmodell
oder DTO, API- und Oberflächenverhalten sowie überprüfbare Akzeptanzbeispiele.

### 8.1 BAS-001 Grundlagen und Lager

**Ist.** Lebensmittel-/Einheiten-/Kategorien-/Tagpflege und die Lagerpersistenz
existieren produktiv (`master_data_store.py:create_food`,
`replace_food_storage_locations`, `admin/master_data_routes.py`). Vollständiges
Storage-CRUD und Pflichtlagerauswahl waren damit nicht als B4-UI ausgeliefert;
sie gehören zum nun autorseitig eingefrorenen Foundations-Consumer4d5074e,
Root-Prüfung114DBPASS113.07s/35BrowserPASS241.91s und ReviewCLEAN12446;
Integration und gemeinsame Releaseabnahme bleiben separat. Die
Vorschlagsverben `create_proposal_v21`, `accept_proposal_v21`,
`reject_proposal_v21` existieren; `master_data_proposals.PROPOSAL_FIELDS` umfasst
genau `density_g_per_ml`, `piece_weight_g`, `category_code`, `allergens`,
`labels`. `menu_components.food_id` existiert seit `e813806`, hat aber keinen
Python-Writer und keine Auswahl in der Oberfläche.

**Soll.** Ein gemeinsamer Einstieg pflegt Lebensmittel, Komponenten, Einheiten,
Kategorien, Tags und Lagerorte. Jedes Lebensmittel hat mindestens einen
Lagerort. Komponenten binden ein Lebensmittel. Bestände bleiben INV-001.

**Verhalten.**

1. `MP-BAS-SCHEMA27` liefert die Lagerpflicht und den vorbereiteten Pin auf
   Datenbankebene, siehe [4](#4-schema-27-vertrag).
2. `MP-BAS-FOUNDATIONS` liefert Lagerort-CRUD, die verpflichtende Lagerauswahl im
   Lebensmittelformular, die Wiederverwendung des bestehenden Einheiten-FK, die
   exakte Anzeige und Bindung von Revisions-/Hashpin sowie das atomare
   v27-Speichern. Es zeigt `Kein Bestand erfasst`.
3. `MP-REC-COMPONENT-FOOD-UI` ergänzt Auswahl, Rücklesung und ausdrückliches
   Ablösen für `menu_components.food_id` über
   `record_component_food_write_v26` und `lock_component_foods_v26`.
4. `MP-BAS-STORAGE-TANDOOR-REVIEW` prüft Tandoors tatsächliche Lagerfunktionen
   (`InventoryLocation`, `InventoryEntry`, `InventoryLog` in `cookbook/models.py`
   auf `e160ceec`) als reine Quellenanalyse und ordnet sie INV-001 zu. Es wird
   keine Eins-zu-eins-Kompatibilität behauptet und kein Code übernommen.

**Akzeptanzbeispiele.**

- Ein Lebensmittel ohne Lagerauswahl kann nicht angelegt werden; die Antwort ist
  ein Validierungsfehler mit Feldbezug, kein leeres Speichern.
- Ein Lebensmittel mit genau einem Lagerort verliert diesen nicht, wenn nur der
  Name geändert wird; Version steigt genau um 1, genau ein Auditvorgang entsteht.
- Ein bytegleiches erneutes Speichern erhöht die Version nicht und erzeugt keinen
  Auditvorgang.
- Das Entfernen des letzten Lagerorts wird abgelehnt, auch für ein archiviertes
  Lebensmittel.
- Eine Komponente mit gebundenem Lebensmittel zeigt nach dem Neuladen dieselbe
  UUID; ein Ablösen verlangt eine ausdrückliche Bestätigung und erzeugt genau
  einen `component.food_saved`-Beleg.
- Überall, wo Lagerorte erscheinen, steht `Kein Bestand erfasst`; es existiert
  kein Feld, das eine Menge suggeriert.

**Abgrenzung.** Bestände, Bewegungen und Inventur bleiben INV-001. BAS-001 kann
nach Abnahme seiner Grundlagen- und Verknüpfungsverträge abgeschlossen werden;
es wartet nicht auf die spätere Bestandsverwaltung.

### 8.2 REC-001 Rezepte, Revisionen und Bindungen

**Ist.** Rezeptkern, Revisionen, Bilder und Kochbücher sind produktiv. Drei
zugesagte Bindungswege sind auf SQL-Ebene seit `e813806` vorhanden, in Python
jedoch unterschiedlich weit:

| Weg | SQL | Python |
|---|---|---|
| Menüposition → Rezeptrevision | `menu_item_components.recipe_revision_id`, `lock_menu_recipe_revisions_v26`, `record_menu_binding_write_v26` | in Arbeit in `MP-REC-BINDINGS` |
| Komponente → Lebensmittel | `menu_components.food_id`, `lock_component_foods_v26`, `record_component_food_write_v26` | fehlt (Oberfläche), Backendanteil in `MP-REC-BINDINGS` |
| Gerichtvorlage → Rezept | `dish_templates.recipe_id`, `create_dish_template_v26`, `update_dish_template_v26`, `set_dish_template_active_v26` | **vollständig fehlend** |

**Soll.** Alle drei Wege sind bedienbar, verlustfrei rücklesbar, standortgeprüft,
CAS-gesichert und auditiert. Revisionen bleiben unveränderlich. Publizierte
Wochen behalten ihren Inhaltshash.

**Datenmodell und DTO.**

- Das Zuweisungs-DTO trägt zusätzlich zur bestehenden Katalogbindung eine
  nullable Revisionsreferenz. Das bisherige Paar aus Komponenten-ID und Version
  bleibt bestehen; ein Legacy-Zweifeldersatz darf eine vorhandene
  Rezeptreferenz nicht verlieren.
- Der Gerichtvorlagen-Payload ist durch das SQL fest vorgegeben und enthält genau
  `menu_type_code`, `profile_scope`, `title`, `description`, `recipe_public_id`.
  `profile_scope` ist eines aus `common`, `patient`, `staff_guest`. Die
  CAS-Erwartung ist der `updated_at`-Zeitstempel, nicht eine Zeilenversion.
- Eine unveränderte Aktualisierung liefert dieselbe Zeile ohne neuen
  Auditvorgang zurück; ein unveränderter Aktivstatus ist ein Konflikt
  (`55000`).
- Ein archiviertes Rezept kann nicht frei neu zugeordnet werden (`55000`).
  Die begrenzte Vorwochenkopie darf exakte historische Recipe-/Food-/Katalog-
  referenzen des gesperrten Quellbaums erhalten: Original-Quell-/Wochen-CAS und
  scoped Quelllocks, keine freie Neuauswahl, keine Latestauflösung/Detach und
  keine kopierte Freigabe.

**Oberfläche.** Der Menüeditor zeigt Rezepttitel, Revisionsnummer und Ausbeute
sowie ein ausdrücklich bestätigtes Ablösen. UUID und Hash bleiben exakte interne
Bindungs- und Prüfwerte; sie werden nicht pauschal als Bedieninhalt erzwungen.
Pflichtfehler und
Originalkontext dürfen bei 422 und 409 nicht verloren gehen. Die
Gerichtvorlagenpflege erhält eine eigene Liste mit Anlegen, Ändern, Archivieren
und Reaktivieren.

**Akzeptanzbeispiele.**

- Eine Menüposition mit gebundener Revision zeigt nach Speichern und Neuladen
  dieselbe Revisions-UUID und denselben 64-stelligen Hash.
- Eine Revision eines anderen Standorts wird mit `23514` und Constraintnamen
  `menu_item_components_recipe_scope` abgewiesen.
- Ein textgleicher Revisionswechsel und der Wechsel zurück verwerfen bestehende
  Reviewtokens; Nachbarmenüs und der Wochenkontext werden nicht unnötig
  invalidiert.
- Die Vorwochenkopie überträgt die exakte Revision, kopiert jedoch keine
  Freigabe.
- Ein vollständiger Menü-CSV-Ersatz darf eine reine Rezeptbindung nicht still
  löschen.
- Eine bereits veröffentlichte Woche behält ihren Publikationshash unverändert.
- Gerichtvorlage: `update` mit falschem `updated_at` liefert `55000`; `update`
  ohne inhaltliche Änderung liefert dieselbe Zeile ohne zweiten Auditvorgang;
  `active` auf denselben Wert liefert `55000`.

**Richtext.** HugeRTE 1.0.13 wurde lokal browsergeprüft: Richtext funktioniert,
eine Style-CSP-Verletzung bleibt offen, und Silver ist keine vollständige
Tabler-Bedienoberfläche. Richtext ist **keine** Voraussetzung für die
Klartext-Rezeptpflege. `MP-REC-RICHTEXT-DECISION` liefert einen begrenzten
Entscheidungsbericht mit CSP-Befund, Tabler-Lücke, Lizenz und Alternativen. Es
installiert keine Dependency und verändert kein Produktverhalten.

**Abschluss.** `MP-REC-BINDINGS-ACCEPT` prüft nach Fertigstellung aller drei Wege
unabhängig, dass REC-001 tatsächlich bedienbar ist, und benennt jede
verbleibende Lücke einzeln.

### 8.3 REC-002 KI-Hilfen und Extraktion

**Ist.** `foods.source_kind` erlaubt `ai_assisted`, `food_data_proposals.source`
erlaubt `ai`, und `recipes.source_kind` erlaubt `ai_assisted` mit Pflicht auf
`source_reference`, `fetched_at` und `source_note`
(`database/schema.sql`, `recipe_values.py:source`). Es gibt keinen
Extraktionspfad. Die vorhandene Menübilderzeugung erfüllt diesen Auftrag nicht.

**Soll.** Bilder, Dokumente und Text werden in einen bearbeitbaren Entwurf
überführt: Schritte geordnet, Zutaten zugeordnet, Metadaten vorgeschlagen.
Quelle, erkannte Werte und Unsicherheit sind vor der Übernahme sichtbar.

**Verhalten.**

1. `MP-REC-AI-EXTRACTION` definiert und implementiert einen **reinen** Adapter
   von einem strukturierten Extraktionsergebnis auf das bestehende
   `RecipeImportPreview`-DTO. Er nimmt bereits vorliegendes strukturiertes JSON
   entgegen, ruft keinen Anbieter auf und schreibt nichts. Er trägt je Feld eine
   Unsicherheitsangabe und den Quelldateibezug (`sha256`, Seite oder Zeile) und
   setzt `source.kind = 'ai_assisted'` mit Pflichtnotiz.
2. `MP-REC-AI-PROVIDER` schliesst erst nach ausdrücklicher Freigabe einen
   konkreten OCR-/Modellanbieter an. Ohne Freigabe bleibt das Paket
   `AWAITING_EXTERNAL`.

**Akzeptanzbeispiele.**

- Ein Extraktionsergebnis ohne Quellbezug wird abgelehnt; die Fehlermeldung nennt
  das Feld, nicht den Eingabewert.
- Ein erkannter Nährwert erscheint als Vorschlag und niemals als bestätigter
  Wert; Allergene werden nie automatisch bestätigt.
- Ein Zutatenvorschlag ohne auflösbares Lebensmittel bleibt im gespeicherten
  Importentwurf mit Unsicherheit editierbar. Er führt zu keinem teilweisen
  bestätigten v27-Import. Normale unvollständige Rezeptentwürfe bleiben unabhängig
  davon speicherbar; dieser Altwriter wird nicht als Import-Bypass benutzt.
- Die Übernahme läuft über denselben geprüften Importweg wie REC-004 und legt
  ohne Bestätigung nichts an.

### 8.4 REC-003 Planung und Einkauf

**Ist.** Planung, Decimal-Konvertierung und reine Skalierung existieren;
persistente Zielmengen an Rezeptbindungen und Einkaufslisten fehlen.

`MP-REC-PLAN-PORTIONS` ergänzt die exakte Revisionbindung um eine optionale
positive Zielmenge mit vorhandener Einheit. Ohne Ziel gilt die vorhandene
deklarierte Ausbeute (`servings`/`servings_unit`). DTO, Formular, POST, Load/Save,
Copy und Review besitzen denselben Original-Item-/Wochen-CAS-Vertrag. Keine
öffentliche Projektion oder automatische Publikation.

`MP-REC-SHOPPING-AGGREGATE` nimmt **bereits aufgelöste unveränderliche** Revision-
DTOs mit gewählten Zielmengen an; keine Engine und kein Lookup heutiger Foods.
Der Aufrufer lädt die exakten Quellen und Assets konsistent im RR-Read. Zwei
ausdrückliche, im Beleg gespeicherte Bedarfspolitiken:

- **Blattbedarf (Standard):** Prepared-Kinder aus der geprüften Closure expandieren
  und über deren vorhandene deklarierte Ausbeute skalieren. Die vorbereitete
  Zwischenzutat nicht zusätzlich einkaufen; geteilte Kinder zählen je realem
  Zutatenvorkommen, nicht nur einmal je Indexknoten.
- **Vorbereiteter Bedarf:** An einer ausdrücklich gewählten Prepared-Food-Zeile
  stoppen und deren Menge aufnehmen; dieselbe Teilstruktur nicht zusätzlich als
  Blattbedarf zählen. Die Wahl ist kein Bestandsabzug und keine Herstellung.

Zusammenführen nur gleicher Foodidentitäten mit kompatibler **erfasster** Unit-/
Faktorprovenienz. Physikalische Dimensionen verwenden erfasste base_factors;
Masse↔Volumen nur mit explizit erfasster Food-Dichte, Stück↔Masse nur, soweit die
bestehende Mengenlogik es mit erfasstem Stückgewicht erlaubt. Kontextabhängige
Einheiten nur innerhalb desselben exakten Rezeptkontexts; keine Dichte oder
Gramm-pro-Portion raten. Widersprüchliche historische Faktoren bleiben getrennte
Positionen mit Grund. V1-Zeilen bleiben terminal; alte Freitextzeilen erscheinen
getrennt als unvollständig, nicht als erfundene Food-FKs oder Nullmengen.

`MP-REC-SHOPPING-PERSIST` speichert Listenhead mit Standort/CAS, manuelle Zeilen
und unveränderliche Berechnungsrevisionen: Quellrevision+Hash, Zielausbeute,
Bedarfspolitik, Childpins, erfasste Unit-/Faktorwerte und Ergebnisherkunft.
Neuberechnung verlangt bewusste Auswahl und Original-CAS; alte Belege bleiben.
Unveränderte Positionen behalten den Abhakstatus, geänderte abgeleitete Mengen
werden sichtbar als geändert und erneut offen geführt; manuelle Positionen
bleiben erhalten. Keine Stock-/Journalbuchung, keine automatische Veröffentlichung.
Lesen `draft.read`, Schreiben `draft.write`, CSRF und Original-Actor/Authz/Site.

`MP-REC-SHOPPING-PDF` verbindet den tatsächlichen Listen-/Revisionslink mit dem
bestehenden nativen PDF-Weg und Vorlagenstore. Exakte Listenrevision, no-store,
sichere Fehler und authentifizierter Read; Druckvorschau ist keine Bestellung.
Einkauf hängt nicht von Nährwertschema/-freigabe oder Rezept-PDF-Geometrie ab.

**Akzeptanz:** 500 G + 1 KG gleicher Quelle → 1500 G; 500 ML bei explizit
erfasster 1.2 G/ML plus 400 G → 1000 G. Ohne Dichte getrennte Positionen.
Spätere Food-/Pin-/Einheitenänderung verändert alten Beleg nicht. Ein Prepared-
Zweig erscheint entweder als Zwischenzutat oder seine Blätter, nie beides.
Kein Snapshot-/Audit-/Inventarwrite durch Preview, Tastatur/NoJS und Drucklink
funktionieren auf der echten Listenroute.

### 8.5 REC-004 Dateien und Sammlungen importieren

**Ist.** R6a `recipe_import.py` ist ein reiner CSV-/JSON-Parser, kein persistenter
Import. Seine Datei-Provenienz bleibt `file_import`, mit der bereits definierten
Datei-Hash-/Zeilenreferenz. Limits aus `recipe_import_types.py` bleiben verbindlich.
`recipe_values.source` erlaubt `manual`, `url`, `file_import`, `ai_assisted`;
`reference` ≤200, URL ≤2048, Notiz ≤500; nichtmanuell braucht Referenz/Abrufzeit,
URL braucht URL, file_import/ai_assisted eine Pflichtnotiz.

**Gespeicherter Stapel (`MP-REC-IMPORT-BATCH`).** Pro Standort: UUID, Version,
Status draft/imported/cancelled, unveränderlicher Ursprungsbeleg (Adapterart,
Quelldatei-/Dokumenthash, BatchUUID:row und Originalquelle jeder Zeile), getrennt
bearbeitbare Kandidaten, Food-/Unitzuordnung, Dublettenentscheidung und
Ziel-UUID/-Version. Änderungen an Preview oder Entscheidungen erhöhen Batch-CAS
und entwerten die alte Bestätigung. Das Rohdokument wird nicht als öffentliche
Download-URL exponiert. Bounded Payload/Dateigrösse, JSON-Tiefe und Zeilenanzahl
an der Grenze prüfen, keine Einheiten aus Freitext erfinden.

**Bestätigte Übernahme (`MP-REC-IMPORT-COMMIT`).** Ein signierter Originalkontext
bindet Actor/Authz, Standort, Batchversion, vollständigen Kandidatenhash,
Zeilenentscheidungen und alle Ziel-/Referenzversionen. Vorschau braucht
`recipe.write`, Bestätigung **`recipe.import`**; der reale Publisher/Admin darf,
der Editor ohne recipe.import nicht. Die einzige Transaktion prüft ursprüngliche
Actor-/Rollen-/Siteguards, Vokabular/Units/Storage/Foods sortiert vor Rezeptköpfen,
danach Batch-/Ziel-CAS. Pin-/Freeze-Aktionen gehören nicht in diesen Batch;
dafür wäre der Graphlock bereits vor den Referenzlocks nötig.

Die minimal vollständigen Entscheidungen sind **Neuanlage** und **Überspringen**
einer explizit geprüften Dublette. Auch Skip prüft die originale aktive
Zielidentität/-version unter Lock; veraltete oder neu archivierte Ziele →409,
gesamter Batch unverändert. Keine Namensähnlichkeit als implizite Entscheidung.
Ein Update bestehender Rezepte ist hier nicht freigegeben: Es würde einen
eigenen vorhandenen Zielwritervertrag mit unveränderlicher Head-/Zeilenquelle
und zusätzlichem immutable Batchbeleg benötigen. Kein Umgehen von
`recipe_protect_v22` oder `update_recipe_v22` und keine Herkunfts-Umetikettierung.

Alle übernommenen Zutaten brauchen Food+positive Menge+Unit, nichtleere Zutaten
und echte vorhandene Storagezuordnung. Unvollständige Vorschau bleibt draft;
keine Teilübernahme der übrigen Zeilen. Die bestehenden unvollständigen normalen
Rezeptentwürfe bleiben davon unberührt. Neue Datei-Rezepte verwenden die
unveränderliche BatchUUID:row-Referenz plus Datei-Hashnotiz; URL- und AI-Adapter
behalten dagegen ihre URL-/AI-Ursprungsfelder unverändert. Ihr Batchbeleg ergänzt
die Herkunft. Die gemeinsame Pipeline setzt **nicht** alles auf file_import.

`create_recipe_v22` ist in derselben Connection-/SQL-Transaktion aufrufbar.
`recipe_store.create_recipe`/`recipe_commands.command` öffnen dagegen je
`engine.begin()` und dürfen nicht als Schleife für einen atomaren Batch dienen.
Der enge neue Importverb/Store bindet den festen recipe.import-Guard und ruft
vorhandene SQL-Fachverben innerhalb einer TX; kein App-DML/private EXECUTE und
keine generische vom Client übergebene SQL-/Auditoperation. Jeder erstellte
Rezepthead bekommt genau sein bestehendes Versions-/Auditpaar; ein abgeleiteter
Batchbeleg protokolliert den vollständigen Import. Fehler rollt beides zurück.
Imported-Batches sind unveränderlich; erneute Bestätigung →409 ohne neue Rezepte,
Versionen oder Audits. SQLSTATEs folgen 4.8, HTTP-Fehler bleiben begrenzt.

CSV/JSON → persistierter Preview → editierbare Zuordnung → signierte Bestätigung
→ Rezeptlink ist eine echte Route-/Store-/Formularkette. XLSX erhält nach realer
Beispieldatei/Formatentscheidung einen separaten Adapter, denselben Batchweg und
keine eigene SQL-Persistenz. Eine Dependency ist erst nach Root-Freigabe zulässig.

**Akzeptanz:** Fehler in letzter Zeile lässt null neu erstellte Rezepte/Audits;
gleichzeitige Bestätigungen erzeugen genau einen Import; editierter Preview,
veralteter Skip-Ziel-CAS, Actorentzug und Standortwechsel schreiben nichts.
File-, URL- und AI-Quellen behalten jeweils ihre Originalart und Pflichtfelder.
GET schreibt nichts; anonyme, capability-falsche und CSRF-falsche Requests sind
separat geprüft. Keine Veröffentlichung oder fachliche Allergenfreigabe.

### 8.6 REC-005 Webseitenimport

**Ist.** Rezeptquellenfelder und deren Validierung existieren
(`recipe_values.py:source`, `recipes.source_kind`). `master_data_proposals.py`
ist ein Vorschlagsdienst für Lebensmittel, kein Schema.org-Rezeptimport. Ein
Webimport existiert nicht.

**Soll.** Schema.org-Rezepte aus JSON-LD und Microdata übernehmen, Quelle und
Importzeit erhalten, vor der Speicherung korrigieren. Es wird keine Unterstützung
jeder Website zugesagt.

**Verhalten.**

1. `MP-REC-SCHEMAORG-ADAPTER` implementiert einen **reinen** Adapter von einem
   bereits vorliegenden HTML- oder JSON-LD-Text auf `RecipeImportPreview`. Er
   führt keinen Netzwerkzugriff aus. Grenzen: Dokument höchstens 2 MiB,
   Verschachtelung höchstens 8, `@graph`-Auflösung ohne Rekursionszyklus,
   `recipeYield`, `recipeIngredient`, `recipeInstructions`, `name`,
   `description`, `prepTime`, `cookTime` mit ISO-8601-Dauer. Nicht erkannte oder
   mehrdeutige Werte werden Feldfehler, keine geratenen Werte.
   `source.kind = 'url'` mit Pflicht auf `source_url`.
2. `MP-REC-URL-FETCH` ergänzt einen eng begrenzten ausgehenden Abruf: nur
   `https`, DNS-Auflösung und Zielprüfung vor dem Verbindungsaufbau,
   Ablehnung privater, Loopback-, Link-Local-, Multicast- und
   Metadatenadressen, keine Weiterleitung auf ein abweichendes Ziel ohne erneute
   Prüfung, harte Zeit- und Grössenbegrenzung, feste erlaubte Inhaltstypen. Er
   führt keine Makros und keine importierten Skripte aus. Danach folgt der
   Microdata-Adapter.

**Akzeptanzbeispiele.**

- Ein JSON-LD mit `"recipeYield": "4 Portionen"` erzeugt Ausbeute `4` mit
  Einheitencode `PORTION`; `"recipeYield": "ca. 4-6"` erzeugt einen Feldfehler.
- `"prepTime": "PT20M"` ergibt `prep_minutes = 20`; `"PT1H30M"` ergibt `90`;
  `"P1D"` überschreitet keine Grenze, `"PT200H"` wird abgelehnt.
- Ein Dokument ohne `@type: Recipe` liefert einen Dateifehler ohne Zeilen.
- Ein Abruf gegen `http://169.254.169.254/` wird vor dem Verbindungsaufbau
  abgelehnt; der Fehler nennt kein internes Ziel.
- Die Übernahme verwendet denselben Stapel- und Bestätigungsweg wie REC-004.

### 8.7 REC-006 Suche und Tags

**Ist.** Titel-/Zutaten-/Tagfilter existieren; FTS, gespeicherte Suche und
Sammelzuordnung fehlen. Archivfilter und Standortgrenze bleiben erhalten.

**FTS mit bestehenden PostgreSQL-Mitteln.** Generierte Spalten dürfen nur Werte
der aktuellen Zeile und immutable Ausdrücke verwenden, keine Subqueries oder
fremden Zeilen ([PostgreSQL 18](https://www.postgresql.org/docs/18/ddl-generated-columns.html)).
`MP-REC-SEARCH-FTS` verwendet deshalb zeilenlokale `tsvector`-Ausdrücke mit
explizitem `'pg_catalog.german'::regconfig`: Recipe-Titel Gewicht A/Beschreibung C,
`recipe_ingredients.ingredient_text` B, `recipe_steps.instruction` C und
`foods.name` B. Kein als immutable getarnter Tabellenlookup und kein neuer
SECURITY-DEFINER-Bypass. Bestehende Create/Update/Replace-Children-Verben pflegen
automatisch nur die tatsächlich geänderten Zeilen; keine zweiten Auditbumps.

Der RR-Reader baut daraus je standortgebundenem Rezept ein deterministisch
geordnetes gewichtet zusammengesetztes Suchdokument und prüft den **gesamten**
`websearch_to_tsquery` dagegen. Somit kann ein AND-Begriff im Titel und der
andere in einer Zutat stehen. Phrasen beziehen sich auf dieses dokumentierte
Suchdokument, mit Tests für Reihenfolge/Abstände. Reihenfolge nach `ts_rank_cd`,
danach lower(title)/UUID. Keine Titel-only-Vorfilterung, die gültige gemischte
Treffer verliert. GIN-Indizes nur, wo echte PG-EXPLAIN-Belege den konkreten
Zugriff stützen; kein pauschales Geschwindigkeitsversprechen für den zusammengesetzten
Reader. Begrenzte Suche/Seite, frühe Standort-/Archivfilter und echte Messung.

Food-Rename aktualisiert ausschliesslich seine eigene Zeile/deren Suchausdruck.
Es gibt keinen Food→Recipe-Fanout und damit keine inverse Food-/Recipe-Lockfolge.
Die nächste RR-Transaktion sieht den neuen Namen konsistent; eine schon laufende
behält ihren Snapshot. Grants und Originalwriter bleiben unverändert.
`kartoffel suppe` findet ein Dokument mit beiden Lexemen. Ein Treffer für das
Kompositum `Kartoffelsuppe` wird ohne belegte Zerlegung nicht zugesichert;
`ts_debug`/echte deutsche PG-Suchfälle belegen die genaue Tokenisierung.

`MP-REC-SEARCH-TRGM` folgt einer eigenen Betriebsentscheidung zu pg_trgm und
echten Messungen. Keine stille Extension-Installation; Migration/Restore müssen
die genehmigte Extension vor abhängigen Objekten bereitstellen. FTS kann ohne
diese Entscheidung geliefert werden. `MP-REC-SAVED-SEARCH` speichert strikt
versionierte Filter mit Standort, Besitzer und Original-CAS; keine Query-SQL-
Strings. Gespeicherte Ergebnisse werden weiterhin mit aktueller Read-Berechtigung
gefiltert, keine Berechtigungsvergabe durch eine gespeicherte Suche.

**Sammel-Tagging ist atomar.** Signierter Preview bindet den exakten sortierten,
begrenzten Zielsatz aus UUID+row_version, Tagidentität/-version, Aktion und
Original-Actor/Authz/Site. Die konkrete Obergrenze wird vor Writer-READY als
Payload-/Lockbudget mit Messfall fixiert, nicht als unbegrenzter Filtercursor.
Tag-/Vokabularlocks kommen vor sortierten Rezeptlocks; nach den Locks alle
ursprünglichen Erwartungen erneut prüfen. Ein veraltetes/archiviertes Ziel
oder Actorentzug →409 für **den ganzen Satz**, kein partieller Erfolg, kein
erneutes stilles Ausführen der Suchanfrage. Neuer Preview ist nötig. Je wirksamer
Rezeptänderung genau eine Version/Audit, No-op keines; Replay kein Doppelbump.

**Akzeptanz:** gemischte Feldbegriffe, Foodrename unter zwei RR-Transaktionen,
Archiv-/Fremdstandortfilter, deutsche Tokenisierung und EXPLAIN. Bei 12 bestätigten
Zielen und einem Konflikt bleiben alle 12 unverändert. UI zeigt diese Policy,
Filter erhalten ihre Werte; keyboard/NoJS und sichere Fehlermeldungen.

### 8.8 REC-007 Rezeptdruck und Layout

**Ist.** Der Rezeptdruck ist funktionsfähig:
`admin/recipe_pdf.py:render_recipe_pdf`, `recipe_reads.py:recipe_print_input`
(liest genau die gewählte unveränderliche Revision und ausschliesslich
referenzierte geprüfte Bilder), `print_templates.py:_validate_recipe`,
`print_template_config.py:validate_config` und die Route
`/rezepte/<uuid>/revisionen/<uuid>/druck.pdf`. Der native Rezept-Vorlageneditor
liegt als `admin/recipe_print_template_routes.py` mit
`/vorlagen/rezepte` und `/vorlagen/rezepte/vorschau.pdf` vor. Das Rezeptprofil
kennt genau die acht gemeinsamen Eigenschaften und **keine**
`layout`-Geometrie; diese gilt nur für die Wochenprofile.

**Soll.** Rezept- und Einkaufslisten-PDF unter Vorlagen mit bearbeitbarem Layout,
Logo, Zutaten, Portionen, Schritten, Bildern und automatischen Legenden. Lange
Rezepte dürfen lesbar mehrseitig sein. Wochenpläne bleiben je eine Seite.

**Verhalten.**

1. `MP-REC-PDF-RELEASE` verwendet den bereits ausgelieferten Quellenstand
   `5f5f6cb535922db8453c68d871279d6b2e203391`/Schema25 und die Root-Full-/Health-
   Receipts. Offen bleibt der autorisierte authentifizierte Live-Nachweis.
   Kein erneuter Implementierungs-/Deploymentauftrag aus diesem Restanker.
2. `MP-REC-PDF-GEOMETRY` entscheidet den restlichen zugesagten Layoutumfang
   konkret gegen Abschnitt 5 des Designentwurfs und implementiert den kleinsten
   fehlenden erlaubten Blocktyp beziehungsweise Geometriegriff im vorhandenen
   Validator und Renderer. Es wird kein freier Canvas behauptet und keine
   ungeprüfte pdfme-Editorfreigabe erteilt.
3. `MP-REC-SHOPPING-PDF` ergänzt das Einkaufslisten-PDF, sobald der Datensatz aus
   [8.4](#84-rec-003-planung-und-einkauf) existiert.

**Akzeptanzbeispiele.**

- Das erzeugte PDF wird geöffnet und inhaltlich geprüft, nicht nur der
  HTTP-Status.
- Ein Rezept mit 60 Zutaten und 40 Schritten bricht lesbar um und schneidet
  nichts ab.
- Die Legende zeigt ausschliesslich tatsächlich dargestellte Symbole.
- Eine Skalierung auf abweichende Zielausbeute erscheint im PDF als Decimal ohne
  Zwischenrundung.
- Alle `tests/test_week_pdf*.py` bleiben unverändert grün; die Einseitenpflicht
  für Wochenpläne bleibt erfüllt.
- Ein Layoutwert ausserhalb der erlaubten Auswahl wird vom Validator abgelehnt.

### 8.9 NUT-001 Produktdaten und Nährwerte

**Ist.** `foods`, `food_allergens` und `food_data_proposals` liefern die
Quellen- und Freigabegrundlage. Allergene kennen genau die Ausprägungen
`contains` und `may_contain` (`master_data_proposals.normalize`,
`food_allergens.presence`). Eine Nährwertpersistenz existiert nicht;
`fhir/mapping.py:nutrition_product` ist eine Menüprojektion.

**Soll.** Strukturierte, quellenbezogene Produkt- und Lieferantendaten mit
Allergenen, Spuren, Nährwerten, Bezugsmenge, Aktualität und Prüfstatus.
Rezept- und Portionsbezug. Schätzungen bleiben getrennt von bestätigten Daten.
Unbekannte Angaben bleiben unbekannt und werden nicht zu null gerechnet.

**Datenmodell.** `MP-NUT-SCHEMA` legt an:

- eine Nährstoffliste mit festen Fachcodes und Einheiten (Energie in kJ und
  kcal, Fett, gesättigte Fettsäuren, Kohlenhydrate, Zucker, Eiweiss, Salz als
  Mindestumfang);
- Nährwerte je Lebensmittel und je **Bezugsmenge** (Menge plus Einheit, in der
  Regel `100 G` oder `100 ML`), als nichtnegative Decimalwerte (gültige Null erlaubt, Unknown separat NULL)
  mit denselben Präzisionsgrenzen wie Mengen, positiver Bezugsmenge und Quelle, Referenz, Abrufzeit, Prüfstatus und ausdrücklichem
  Zustand `unbekannt`;
- eine Erweiterung des Vorschlagswegs, sodass Nährwerte über
  `food_data_proposals` vorgeschlagen und einzeln manuell freigegeben werden.

Bestätigungen erzeugen append-only Nährwerteditionen mit unveränderlicher Unit-/
Faktor-/Quellenprovenienz und einem CAShead. Alte Editionen bleiben erhalten.
Historische Projektionen nennen die ausdrücklich gewählten Editionen samt
Recipehash; SQL27-Snapshots enthalten keine Nährwerte und werden nicht nachträglich
umgeschrieben. `master_quantity > 0` ist kein gültiger Nullfett-Constraint.

Bestätigte Werte werden nie automatisch überschrieben. Ein Vorschlag, der einen
bestätigten Wert ändern würde, zeigt die Abweichung und verlangt eine
ausdrückliche Entscheidung.

**Verhalten.**

- `MP-NUT-SERVICE` liefert Service, Reads, Commands und die Tabler-Pflege für
  Nährwerte, Spuren und Prüfstatus.
- `MP-NUT-RECIPE-PROJECTION` berechnet Rezept- und Portionswerte ausschliesslich
  mit `quantities.py` aus vollständigen Zeilen. Fehlt an einer Zeile
  Lebensmittel, Menge, Einheit oder Nährwert, ist das Ergebnis **unvollständig**
  und wird als solches ausgewiesen; es entsteht kein Teilwert, der wie ein
  Gesamtwert aussieht. Es gibt keinen Zutaten-Einkaufspreis in diesem Paket; das
  ist CALC-001.

**Akzeptanzbeispiele.**

- Ein Lebensmittel ohne Nährwerte liefert für jeden Nährstoff `unbekannt`,
  niemals `0`.
- Ein Rezept mit einer Zeile ohne Lebensmittel liefert Status `unvollständig`
  und nennt die betroffene Zeilennummer.
- `100 G` mit `12.5 g` Fett ergibt bei einer Zutatenzeile `250 G` exakt `31.25 g`
  ohne Zwischenrundung.
- Eine Portionsangabe verwendet die deklarierte Ausbeute; fehlt eine
  konvertierbare Beziehung zwischen Ausbeuteeinheit und Basiseinheit, bleibt der
  Portionswert unbekannt statt geschätzt.
- Ein KI-Vorschlag erscheint niemals als bestätigter Nährwert.

### 8.10 OFF-001 Open Food Facts

**Ist.** Es gibt den vorhandenen Vorschlagsweg und source=`off`, aber keinen
realen OFF-Anschluss. Die frühere Quellenprüfung ordnet Daten ODbL, Inhalte DbCL,
Bilder CC BY-SA 3.0 zu; der Adapterfreeze muss aktuelle offizielle Bedingungen,
Felder und Attribution belegen. Dieser Docs-Fix prüft keine neuen OFF-Inhalte.

1. `MP-OFF-FIELDMAP` friert anhand offizieller Quellen Barcode, Produktname,
   Zutaten, Allergene versus Spuren, Nährwerte/Bezugsmenge, Herkunft und Bilder
   mit Feldgrenzen, fehlend/unknown und Attribution ein. Ein autorisiertes Sample
   ist für die spätere Abdeckungsmessung nötig, nicht für jede reine Adapterarbeit.
2. `MP-OFF-ADAPTER` bildet ein vorhandenes Produktdokument rein auf ein bounded
   Proposal-DTO ab. Bestehendes `PROPOSAL_FIELDS` erlaubt nur Dichte, Stückgewicht,
   Kategorie, Allergene und Labels. Nährwerte kommen über den NUT-Vertrag;
   Produkt-/Barcode-/Herkunfts-/Bildmetadaten benötigen ausdrücklich typisierte
   Felder im erweiterten Proposalvertrag. Keine unbekannten Keys durchreichen.
3. **`MP-OFF-FETCH`** ergänzt den tatsächlichen, serverseitig festen OFF-Endpunkt:
   validierter Barcode, benannte User-Agent-/Rate-/Timeout-/Bytegrenzen, HTTPS,
   erlaubte Hosts und Redirect-/DNS-/Peerprüfung wie 8.6. Kein beliebiger URL-
   Parameter, kein Env-Proxy, keine Tokens im Artefakt. Ergebnis enthält Original-
   Dokumenthash, Endpoint, Abrufzeit, Versions-/Lizenzbeleg. Fetch alleine schreibt
   keine bestätigten Fooddaten. Echte genehmigte API-Fixture/Requestbelege sind
   von lokalen Testresponses getrennt; Timeout/429 sind kontrollierte Fehler.
4. **`MP-OFF-PROPOSAL-CONTRACT`** besitzt zuerst die bounded Erweiterung des
   bestehenden Proposal-/Assetvertrags, feste SQL-Verben, ACL/Migration und
   Consumerstore samt echten Atomaritäts-/Provenienztests.
   **`MP-OFF-REVIEW-UI`** verdrahtet Barcodeformular → Fetch → Vorschlagsstore →
   tatsächliche Vergleichs-/Übernahmeseite. `masterdata.write`, CSRF und Original-
   Actor/Authz/Site/Food-/Proposal-CAS. Netzwerk liegt ausserhalb der Write-TX;
   die danach gespeicherte Vorschau bindet den Originalkontext. Jede Übernahme
   wählt explizite Felder, führt durch feste fachliche SQL-Verben und aktualisiert
   Food/Proposal/Nährwertedition atomar mit genau dem vorgesehenen Audit-/Versions-
   paar. Kein GET-Fetch, kein automatisches Überschreiben bestätigter Allergene.
   Bildübernahme erst bei belegten Rechten: nur erlaubter Bildhost, Byte-/Pixel-
   validation und Attribution; keine Roh-Remote-URL im Browser. Das vorgeschaltete Proposal-Vertragspaket
   besitzt die dazugehörige DDL und den festen Store; der UI-Writer besitzt alle
   direkten Route-/Formular-/Registrierungsconsumer.
5. `MP-OFF-COVERAGE` misst die reale berechtigte Schweizer Stichprobe und prüft
   die ganze Kette einschliesslich Vorschlag/ausdrücklicher Übernahme. Trefferquote,
   Feldvollständigkeit, Rechte-/Bildlücken und tatsächliche Fehler getrennt nennen.
   Pure Adaptertests oder ein source-Enum sind kein vollständiger OFF-PASS.

**Akzeptanz:** unbekannter Barcode erzeugt keinen leeren bestätigten Datensatz;
`allergens_tags`/`traces_tags` bleiben contains/may_contain. Vorschau ändert keine
bestätigten Werte. Staler Food-/Proposal-CAS, Standortwechsel und Entzug rollen
die ganze Übernahme zurück. Feldweise bewusste Übernahme funktioniert real auf
der Route, keyboard/NoJS; ein Bild trägt seine tatsächliche Zuschreibung.

### 8.11 Verknüpfter Gerichtsdatenentwurf

Der Entwurf `demo/linked_recipe_drafts.json` (Commit `7d18feb2`) ist der reservierte
Anker `MP-REC-DATA-DRAFTS`. Gemessener Inhalt:

| Sammlung | Anzahl |
|---|---|
| `foods` | 100 |
| `recipes` | 61 (davon 29 Vorbereitungen) |
| `dish_mappings` | 32 echte Gerichtstitel |
| `source_components` | 37 |
| `existing_unit_codes` | 9 |
| `storage_proposals` | 3, bearbeitbar |

Die Metadaten des Entwurfs weisen ihn ausdrücklich als
`runtime_import_format: false` und `status: unreviewed_preparation_only` aus.
Ausbeuten sind `proposed_not_measured`, alle Rezepte tragen
`review_status: unreviewed` und `allergen_review_status: not_checked`, die
Quellart ist `ai_assisted` mit Pflichtnotiz. Root hat den Datensatz unabhängig
geprüft: 31 PASS in 1.36 s.

`MP-REC-DATA-IMPORT` überführt diesen Entwurf **nicht** direkt in die Datenbank.
Er wird in das Importformat aus [8.5](#85-rec-004-dateien-und-sammlungen-importieren)
übersetzt, durchläuft Vorschau, Dublettenentscheidung und ausdrückliche
Bestätigung und erhält eine dauerhafte Provenienz aus Stapel- und
Entwurfsbindung. Voraussetzungen: `MP-BAS-SCHEMA27`, `MP-BAS-FOUNDATIONS`,
`MP-REC-IMPORT-COMMIT` sowie die konkrete Zuordnung zu existierenden Foods,
Einheiten und echten Lagerorten. Küchen-/Allergenfreigabe ist eine spätere
fachliche Abnahme (Root-DATA-001), keine pauschale Voraussetzung für die bereits
beauftragte ungeprüfte Erfassung.

Verbindliche Grenzen für den Import:

- Die vier Quellwochen sind bereits publiziert und werden nicht rückwirkend
  umgeschrieben. Es gibt derzeit null `dish_templates`.
- Zuordnungen erfolgen ausschliesslich über die ausdrückliche persistente
  Provenienz aus Stapel und Entwurf, niemals über unscharfe Namensähnlichkeit.
- Vorgeschlagene Mengen und Ausbeuten bleiben als AI-/nicht-gemessen markierte,
  bearbeitbare Draftwerte speicherbar. Reale Lagerorte müssen vor der jeweiligen
  Food-Anlage explizit zugeordnet werden; die drei Vorschlagsnamen sind keine
  automatisch gültigen Produktionslager.
- Quellenkennzeichen und Allergenvorschläge werden nicht stillschweigend zu
  bestätigten Tatsachen. `ai_assisted` bleibt erhalten, kein file_import-Relabel.
  Unreviewed/Mengen-/Allergenhinweise werden als begrenzte Batchannotation und
  sichtbare Recipe-source.note gespeichert; keine unbekannten Top-levelkeys im
  strikten bestehenden recipe_payload und keine neue automatische Freigabe.
- Die 100 Foods werden zuerst über die vorhandene Grundlagenpflege mit echten
  Lagerzuordnungen kanonisch bereitgestellt und ihre UUID-Zuordnung im Stapel
  dokumentiert. Der reine Rezeptbatch erzeugt keine Foods nebenbei. Dieser
  explizite Vorbereitungsschritt und die atomare Rezeptübernahme haben getrennte
  Belege; kein falsches corpusweites All-or-nothing über mehrere Transaktionen.
- Der übersetzte Stapel enthält die 61 vollständigen Mengenrezepte als sichtbar
  ungeprüfte Heads. Ungeklärte Quellen-/Food-/Unitzuordnung bleibt Import-draft,
  nicht als teilweise erfolgreicher Gesamtimport ausgegeben.
- Prepared-Pins werden im vorhandenen v27-Pfad aus explizit gewählten, bottom-up
  eingefrorenen Revisionen gesetzt; keine freie JSON-Kindschliessung und kein
  automatisches Freeze beim Import. Bis dahin ist die Verknüpfungsabnahme offen.
  Ein technischer Freeze ist keine Küchen-/Allergenfreigabe. Die Zuordnungs-
  und Revisionswahl ist im tatsächlichen Formular sichtbar und CAS-geschützt.

---

## 9. Arbeitspakete und Abhängigkeiten

### 9.1 Reservierte Anker

39 ursprüngliche IDs bleiben erhalten; vier bounded Anschlussnodes kommen hinzu:
`MP-BAS-V27-RELEASE-ACCEPTANCE`, `MP-OFF-FETCH`, `MP-OFF-PROPOSAL-CONTRACT`,
`MP-OFF-REVIEW-UI`. Die folgenden IDs sind von Root reserviert und werden hier definiert. Der
Warenfluss-Plan referenziert sie, definiert sie jedoch nicht erneut.

| Anker | Zustand | Beleg |
|---|---|---|
| `MP-BAS-SCHEMA27` | Autor-Freeze, Root-DB-Test geprüft, Consumerfreigabe offen | Worktree `prepared-food-schema27-0909`, Migration `0024` reserviert |
| `MP-BAS-FOUNDATIONS` | Autor-Freeze4d5074e, Root114DB/35Browser + ReviewCLEAN12446 | Worktree `linked-foundations-v27-0909` |
| `MP-REC-BINDINGS` | Autor-Freeze, Root-Abnahme offen | Worktree `recipe-menu-binding-writer-0908`, 16 Produktdateien |
| `MP-REC-DATA-DRAFTS` | lokal geprüft | Commit `7d18feb2`, Root-Datensatzgate 31 PASS |
| `MP-REC-PDF-RELEASE` | live, Auth-Live offen | `5f5f6cb5`/Schema25, Full 5810 PASS/18 SKIP, Health PASS |
| `MP-REC-IMPORT-PARSER` | integriert in `e813806` | Commit `7800e39`, `tests/test_recipe_import.py` |
| `MP-REC-SNAPSHOT-V2` | geplant | Abschnitt [5.2](#52-neuer-v2-snapshot) |
| `MP-REC-FREEZE-V2` | geplant | Abschnitt [5.3](#53-abhängigkeitshash-und-freeze) |
| `MP-REC-IMPORT-BATCH` | geplant | Abschnitt [8.5](#85-rec-004-dateien-und-sammlungen-importieren) |
| `MP-REC-PLAN-PORTIONS` | geplant | Abschnitt [8.4](#84-rec-003-planung-und-einkauf) |
| `MP-REC-SHOPPING-AGGREGATE` | geplant | Abschnitt [8.4](#84-rec-003-planung-und-einkauf) |

### 9.2 Fachliche Reihenfolge

Die maschinenlesbaren `depends_on` enthalten ausschliesslich Fachverträge:

```
Schema27 → Foundations; Schema27 → Snapshot-v2-Reader/PDF → Freeze-v2
Foundations + Snapshot-v2 + Freeze-v2 → MP-BAS-V27-RELEASE-ACCEPTANCE
Parser → Import-Batch → Import-Commit → ungeprüfte Data-Drafts-Erfassung
Schema.org → URL-Fetch; AI-Extraktion → genehmigter Provider; XLSX-Input → XLSX
Bindings → Binding-UI/Component-UI; beide + Dish-CRUD → Bindings-Accept
Snapshot-v2 → Shopping-Aggregate; Binding-UI + Freeze-v2 → Plan-Zielmengen
Shopping-Aggregate + Plan-Zielmengen → Shopping-Persist → Shopping-PDF
FTS → Saved-Search; FTS → Batch-Tags; FTS + Trgm-Entscheid → Trgm
Foundations → NUT-Schema → NUT-Service → NUT-Projektion
OFF-Fieldmap + NUT-Service → OFF-Adapter → OFF-Fetch
OFF-Adapter + NUT-Service → OFF-Proposal-Contract
OFF-Fetch + OFF-Proposal-Contract → OFF-Review-UI → Coverage
```

Einkauf braucht keine Nährwertfreigabe, AI kein XLSX-Beispiel und FTS keinen
Rezeptimport. Ein gemeinsamer Registry-/SQL-/Formularpfad wird über Root-Leases
serialisiert, nicht durch diese fachfremden harten Abhängigkeiten. Forschung
ohne Produktwrites kann bei freien Dateien beginnen; externe Voraussetzungen
blockieren nur die abhängige tatsächliche Ausführung/Abnahme.

### 9.3 Serialisierung gemeinsamer Dateien

`recipes-wps.json` enthält `shared_owner_groups` und je WP `shared_owner_gate`.
Vor READY muss Root jede gemeinsame Datei mit genau einem aktiven Writer und
dem tatsächlichen Vorgängerfreeze-Commit leasen. Das gilt auch gegenüber dem
Operations-/UI-Slice, insbesondere SQL/ACL/Versionen, Mengen, Workflow, Recipe-
Reader/Store, Registry, Sidebar, Foundations und Print-Template-Dateien.

`contract_files` und `wiring_files` sind vollständig Teilmengen von
`owned_files`. Unveränderte SDD-/Quellinputs stehen ausschliesslich unter
`read_only_contract_files` und begründen keinen Schreibbesitz. Keine unbekannten Consumerdateien, kein
gleichzeitiger Writer auf anderem Branch als vermeintliche Entkopplung.
Root reserviert Folgemigrationsnummern und genaue Version-/Ledgerfixture-Hunks
nach Schema27-Freeze; Platzhalter in zukünftigen WPs sind keine Reservierung.
Jede Migration besitzt canonical SQL, ACL, Validator, db.py, Packagevalidator,
Upgrade-/Restore-/ACLtests zusammen. Kein nachträglicher Alt-Migrationsrewrite.

### 9.4 Besitzregeln dieses Plans

- Vertrags- und Anschlussdatei einer Änderung gehören zum selben Paket. Kein
  Paket gibt eine halbe Verdrahtung als erledigt aus.
- `database/schema.sql`, `database/permissions.sql`,
  `database/validate_schema.py`, `reference_scaffold/cafeteria/db.py` und
  `tools/validate_package.py` haben pro Welle genau einen Besitzer.
- Die 16 Produktdateien aus [2.3](#23-laufende-pakete-in-fremdem-besitz) sind bis
  zum Freeze von `MP-REC-BINDINGS` für alle anderen Pakete gesperrt.
- Die elf Grundlagendateien sind bis zum Freeze von `MP-BAS-FOUNDATIONS`
  gesperrt.
- Neue Python-Module bleiben unter etwa 400 und nie über 600 Zeilen.

---

## 10. Test- und Gatevertrag

### 10.1 Verifizierter Aufruf

Die im Repository dokumentierte Prüfung
([VALIDATION.md](../../../VALIDATION.md)) lautet im Verzeichnis
`reference_scaffold`:

```
python -m pytest -q -rs -p no:cacheprovider tests
```

Der gemeinsame Ausführungsvertrag nennt für Entwicklerläufe denselben Runner mit
dem gemeinsamen Interpreter. Der ursprüngliche Planungsautor hat diese Formen real
geprüft — ausschliesslich mit `--collect-only`, ohne Produkttest:

```
rtk env -C <worktree>/reference_scaffold /tmp/dishboard-shared-venv/bin/python -B \
  -m pytest -q -p no:cacheprovider --collect-only tests/test_recipe_menu_binding_db.py
→ 12 tests collected in 2.31s
```

```
rtk env -C <worktree>/reference_scaffold /tmp/dishboard-shared-venv/bin/python -B \
  -m pytest -q -p no:cacheprovider --collect-only tests/test_recipe_import.py
→ 69 tests collected in 1.36s
```

`/tmp/dishboard-shared-venv/bin/pytest` existiert **nicht**; `python -m pytest`
funktioniert dort dennoch (pytest 9.0.2, Python 3.14.4). Lint und Typprüfung
liegen unter `/root/.local/bin/ruff` und `/root/.local/bin/mypy` und sind
vorhanden.

**Es wurde kein Produkttest ausgeführt. Dieser Plan behauptet kein PASS.**

### 10.2 Verbindliche Testarten je Paket

| Art | Aufruf | Zusatzbedingung |
|---|---|---|
| `unit` | `rtk /tmp/dishboard-shared-venv/bin/python -B -m pytest -q -p no:cacheprovider tests/<datei>.py` im Verzeichnis `reference_scaffold` | keine |
| `postgres` | derselbe Aufruf mit gesetzten `TEST_DATABASE_URL` und `TEST_REDIS_URL` | **unzugewiesene Harness-Anforderung:** exklusiver PostgreSQL-18- und Redis-Pool samt aktuellem Wrapper und Portzuordnung durch den Orchestrator. PostgreSQL 16 belegt kein PostgreSQL-18-Verhalten. |
| `browser` | derselbe Aufruf auf den vorhandenen `*_browser.py`-Modulen | verbindliche Matrix aus 10.6 (1440/390 je Route, zusätzlich 1024/768/1920 für Seitentypen); Rollen, CSRF, Fehlerfokus und No-JS-Grundfunktion prüfen; Screenshots selbst beurteilen |
| `security` | `rtk /root/.local/bin/ruff check <eigene Dateien>`, `rtk /root/.local/bin/mypy --python-executable /tmp/dishboard-shared-venv/bin/python --follow-imports=silent <eigene Produktdateien>`, `rtk gitleaks detect --redact --no-banner --log-opts=<base>..HEAD` | Baselinevergleich statt pauschaler Suppression |
| `manual` | Öffnen und inhaltliche Beurteilung erzeugter PDF-Bytes, Papierlayout, fachliche Freigabe | Screenshots ersetzen weder Küchendruck noch Yodeck-Player |

Vor jedem Commit zusätzlich: GitNexus `detect_changes`, `rtk git diff --check`
und der vollständige Secret-Scan.

### 10.3 Vorgeschlagene neue Testmodule

Diese Dateien existieren noch nicht. Sie werden vom jeweiligen Paket angelegt;
ihre Harness-Zuweisung steht in der Tabelle oben.

| Datei | Paket |
|---|---|
| `reference_scaffold/tests/test_recipe_snapshot_v2_db.py` | `MP-REC-SNAPSHOT-V2` |
| `reference_scaffold/tests/test_recipe_freeze_v2_db.py` | `MP-REC-FREEZE-V2` |
| `reference_scaffold/tests/test_dish_template_routes.py`, `test_dish_template_browser.py` | `MP-REC-DISH-TEMPLATE-WRITER` |
| `reference_scaffold/tests/test_menu_recipe_selection_browser.py` | `MP-REC-BINDING-UI` |
| `reference_scaffold/tests/test_component_food_selection_browser.py` | `MP-REC-COMPONENT-FOOD-UI` |
| `reference_scaffold/tests/test_recipe_import_batch_db.py`, `test_recipe_import_routes.py`, `test_recipe_import_browser.py` | `MP-REC-IMPORT-BATCH` |
| `reference_scaffold/tests/test_recipe_import_commit_db.py` | `MP-REC-IMPORT-COMMIT` |
| `reference_scaffold/tests/test_recipe_import_xlsx.py` | `MP-REC-IMPORT-XLSX` |
| `reference_scaffold/tests/test_recipe_schemaorg.py` | `MP-REC-SCHEMAORG-ADAPTER` |
| `reference_scaffold/tests/test_recipe_url_fetch.py` | `MP-REC-URL-FETCH` |
| `reference_scaffold/tests/test_recipe_search_db.py`, `test_recipe_search_routes.py` | `MP-REC-SEARCH-FTS` |
| `reference_scaffold/tests/test_recipe_search_similarity_db.py` | `MP-REC-SEARCH-TRGM` |
| `reference_scaffold/tests/test_recipe_saved_search_db.py` | `MP-REC-SAVED-SEARCH` |
| `reference_scaffold/tests/test_recipe_batch_tags_db.py` | `MP-REC-BATCH-TAGS` |
| `reference_scaffold/tests/test_recipe_plan_portions_db.py` | `MP-REC-PLAN-PORTIONS` |
| `reference_scaffold/tests/test_shopping_aggregate.py` | `MP-REC-SHOPPING-AGGREGATE` |
| `reference_scaffold/tests/test_shopping_list_db.py`, `test_shopping_list_browser.py` | `MP-REC-SHOPPING-PERSIST` |
| `reference_scaffold/tests/test_shopping_list_pdf.py` | `MP-REC-SHOPPING-PDF` |
| `reference_scaffold/tests/test_nutrition_db.py` | `MP-NUT-SCHEMA` |
| `reference_scaffold/tests/test_nutrition_routes.py`, `test_nutrition_browser.py` | `MP-NUT-SERVICE` |
| `reference_scaffold/tests/test_nutrition_projection.py` | `MP-NUT-RECIPE-PROJECTION` |
| `reference_scaffold/tests/test_off_adapter.py` | `MP-OFF-ADAPTER` |
| `reference_scaffold/tests/test_recipe_ai_extraction.py` | `MP-REC-AI-EXTRACTION` |
| `reference_scaffold/tests/test_recipe_data_import_db.py` | `MP-REC-DATA-IMPORT` |

Schema27 hat bereits sechs neue Module: `prepared_food_fixtures.py`,
`test_prepared_food_db.py`, `test_prepared_food_closure_db.py`,
`test_prepared_food_migration_db.py`, `test_prepared_food_race_db.py`,
`test_prepared_food_security_db.py`. Bestehende Fixture-Dateien wurden in
`test_database_invariants.py`, `test_master_data_db.py` und
`test_recipe_binding_migration_db.py` angepasst. Alle liegen unter
`reference_scaffold/tests`; keine erfundene `test_prepared_food_schema27_db.py`.
Der schmale Versionspin in master_data_db bleibt vom Foundations-Fixturebesitz
getrennt und wird von Root hunkgenau integriert.

### 10.4 Bestehende Suiten, die grün bleiben müssen

`test_recipe_store_db.py`, `test_recipe_routes.py`, `test_recipe_revision_routes.py`,
`test_recipe_revision_immutable_db.py`, `test_recipe_pdf.py`,
`test_recipe_pdf_http.py`, `test_recipe_print_input_db.py`,
`test_recipe_import.py`, `test_recipe_menu_binding_db.py`,
`test_recipe_binding_migration_db.py`, `test_component_assignment_db.py`,
`test_component_assignment_races_db.py`, `test_admin_workflow_snapshot_contract.py`,
`test_public_contracts.py`, `test_master_data_db.py`, `test_quantities.py`,
`test_quantities_db.py`, `test_database_invariants.py`,
`test_week_pdf.py` und die übrigen `test_week_pdf*.py`.

### 10.5 Nicht verfügbare Gates

**OCR** (`ocr review`, alibaba/open-code-review) war in diesem Vorgang nach zwei
tatsächlichen HTTP-429-Antworten nicht verfügbar. Das bleibt ein fehlender
Reviewbeleg. Es wird weder als CLEAN geführt noch als Dauerfreistellung
behandelt, und es findet keine erneute Anbieterschleife statt.

---

### 10.6 Verbindlicher UI-Master und Prüfmatrix

Alle bestehenden/neuen UI-WPs lesen vor Änderungen den vollständigen
[UI-Master](../../design/2026-09-09-unified-ui-design-system.md). Er liegt im
Root-Planungsslice `sdd-backlog-root-0909`; Root integriert ihn sowie AGENTS/CLAUDE.
Dieser Slice verändert ihn nicht. Er ist eine verbindliche Vertragsvoraussetzung,
kein Verweis auf ein optionales späteres Design.

| Umfang | Viewports |
|---|---|
| jede geänderte Route | 1440×900 und 390×844 |
| jeder repräsentative Seitentyp und gemeinsame Komponenten | zusätzlich 1024×768, 768×1024 und 1920×1080 |

Native Browserinteraktion, keyboard/NoJS, 200%-Zoom, echter Fontload, Fokus,
Overflow und Kontrast gehören zur tatsächlichen Abnahme. Tabler und vorhandene
Token/Utilityklassen verwenden, mindestens 44px Ziele; bestehende 48px-Ziele
nicht schrumpfen. Keine neue Palette, harten Hexfarben oder Dependency.
R5-Formularänderungen besitzen auch `static/admin.js` FormData-Erzeugung:
Leerzeile, Add/Remove/Reorder und archivierte Referenzen müssen mit und ohne JS
alle Bindungsfelder erhalten. Screenshots/ausgelassene Gates ehrlich berichten.
Dieses Docs-WP führt keine solchen Produkttests und keinen Provideraufruf aus.

## 11. Nicht-Ziele

- Keine Bestandsführung, keine Buchungen, keine Inventur (INV-001).
- Keine Einkaufspreise und keine Menüpreiskalkulation (CALC-001).
- Kein Pauli-Adapter und kein PKS-Bestand (PKS-001).
- Keine Übersetzung und kein Fachglossar (TRN-001).
- Keine neue Produktabhängigkeit. HugeRTE, GrapesJS, Puck und pdfme bleiben
  bewertete Kandidaten ohne Freigabe. Tabler und der native PDF-Weg bleiben
  Standard.
- Keine Übernahme von Tandoor-Code. Der geprüfte Lizenztext nennt AGPL v3 mit
  Commons Clause; Tandoor bleibt Funktions- und UX-Referenz.
- Keine automatische Veröffentlichung, keine automatische Allergenbestätigung,
  keine automatische Überschreibung bestätigter Daten.
- Keine Änderung an v1-Snapshotbytes, v1-Hashes oder publizierten Menü-Snapshots.
