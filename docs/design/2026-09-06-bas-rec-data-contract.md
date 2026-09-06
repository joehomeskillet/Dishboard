# Dishboard: Gemeinsamer Datenvertrag BAS-001 und REC-001

Stand 6. September 2026. Verfasst im Worktree `.claude/worktrees/claude-bas-rec-contract-0906`,
Branch `docs/claude-bas-rec-contract-0906`, Basis `3690e04` (Schema 19).

Dieses Dokument ist ein **Vertrag, keine Umsetzung**. Es legt fest, welche Tabellen, Regeln,
Rechte und Grenzen BAS-001 und REC-001 gemeinsam haben, damit alle Folgepakete
(REC-002 bis REC-007, NUT-001, OFF-001, CALC-001, INV-001, ORD-001) daran andocken können,
ohne den Vertrag erneut zu verhandeln. Es wurde kein Produktcode geändert, keine Migration
geschrieben und keine Abhängigkeit installiert.

Belegter Ausgangsstand, alle Angaben aus dem Repository dieses Worktrees:

| Prüfung | Befund |
|---|---|
| `database/schema.sql` | 33 Tabellen, Schema `cafeteria`, Version `19`. |
| Mengen/Einheiten/Portionen | **Nicht vorhanden.** Keine Spalte oder Tabelle mit `unit`, `quantity`, `portion`, `serving` oder `yield`. Der gesamte Mengenteil ist neu. |
| Stammdaten heute | `menu_components` (Komponentenkatalog), `dish_templates`, `dietary_labels`, `allergens`, `origin_declarations`. |
| Katalogoberfläche heute | `/admin/<cafeteria|patienten>/komponenten` mit Anlegen, Bearbeiten, Archivieren, Entarchivieren (`cafeteria/admin/workflow_routes.py`). |
| Schreibmuster | `SECURITY DEFINER`-Funktionen im Schema `cafeteria` mit Akteurs-ID, dazu `row_version` und `bump_row_version_and_updated_at()`. |
| CSP heute | `default-src 'self'; img-src 'self' data:; style-src 'self'; script-src 'self'` (`cafeteria/__init__.py`). Kein `unsafe-inline`. |
| Fremdassets | `static/vendor/{tabler,tabler-icons,swagger-ui,food-symbols}` mit `*.lock.json` und Offline-Paketprüfungen. |

Paralleler Auftrag OPS-001 (Fable 5.1) besitzt Schema 20 und `0017_v19_to_v20.sql`. Dieser
Vertrag reserviert **keine** Migrationsnummer und beschreibt seine Migrationen ausdrücklich
oberhalb des dann geprüften Schema-20-Vertrags. Nummern und Reihenfolge weist Root zu.

---

## 1. Identität, Geltungsbereich und Namensraum

Alle neuen Objekte liegen im Schema `cafeteria` und folgen dem vorhandenen Muster ohne
Ausnahme:

- `id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY`
- `public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE` als einzige nach aussen sichtbare Kennung
- `row_version bigint NOT NULL DEFAULT 1 CHECK (row_version > 0)` auf jeder direkt bearbeitbaren Tabelle
- `created_at`/`updated_at timestamptz NOT NULL DEFAULT clock_timestamp()`
- `created_by`/`updated_by bigint REFERENCES users(id)` überall dort, wo ein Mensch schreibt

**Standortbindung.** Stammdaten und Rezepte sind standortgebunden
(`location_id bigint NOT NULL REFERENCES locations(id)`).

**Keine Profiltrennung auf Stammdaten und Rezepten.** `menu_components.profile_scope` existiert,
weil ein Komponententext direkt in eine Patienten- oder Cafeteria-Ausgabe gelangt. Eine Zutat
oder ein Rezept erreicht niemals unmittelbar eine Publikation; die Profiltrennung bleibt
vollständig dort, wo sie heute steht (`menu_items`, `menu_components`, `offer_profiles`).
Damit wird der Zutatenstamm nicht je Profil dupliziert. Diese Entscheidung ist bindend: ein
späteres Paket darf `profile_scope` nicht nachträglich auf `foods` oder `recipes` einführen,
ohne diesen Vertrag zu ändern.

**Freitext bleibt führend für die Ausgabe.** Wie `menu_item_components.component_text` heute
schon zeigt, ist der gedruckte Text niemals von einem Stammdatensatz abgeleitet, sondern
gespeichert. Eine Rezept- oder Zutatenbindung ist eine zusätzliche, auflösbare Referenz, nie
die Quelle der veröffentlichten Zeichenkette.

---

## 2. Wiederverwendete vorhandene Tabellen

| Tabelle | Verwendung durch BAS/REC | Änderung |
|---|---|---|
| `locations` | Standortbindung aller neuen Objekte | keine |
| `users` | `created_by`, `updated_by`, Akteur in Funktionen | keine |
| `allergens` | Allergenvokabular (14 EU-Gruppen) | keine |
| `dietary_labels` | Kostform-/Labelvokabular | keine |
| `menu_components` | Komponentenkatalog bleibt der Katalog | **eine** neue Spalte `food_id bigint NULL REFERENCES foods(id) ON DELETE RESTRICT` |
| `menu_item_components` | Bindung Menüposition ↔ Rezept | **eine** neue Spalte `recipe_revision_id bigint NULL REFERENCES recipe_revisions(id) ON DELETE RESTRICT` |
| `dish_templates` | Menüvorlage kann ein Rezept vorschlagen | **eine** neue Spalte `recipe_id bigint NULL REFERENCES recipes(id) ON DELETE RESTRICT` |
| `audit_events` | jede Stamm-/Rezeptänderung | keine; neue `action`/`entity_type`-Werte |
| `settings` | Anzeigeoptionen der neuen Admin-Seiten | keine; neue Schlüssel |
| `publication_revisions` | unverändert | **keine** |

`component_allergens`, `component_labels`, `origin_declarations`, `menu_item_prices` und der
gesamte Publikationspfad bleiben unangetastet.

**Nicht wiederverwendet: `import_batches`/`import_rows`.** Diese Tabellen tragen
`profile_id smallint NOT NULL REFERENCES offer_profiles(id)` und sind Teil des produktiven
Menü-CSV-Vertrags. Ein Rezeptimport hat kein Profil. Die Spalte nachträglich nullable zu
machen, würde einen abgenommenen Produktionsvertrag aufweichen. REC bekommt daher eigene,
formgleiche Tabellen (§9). Das ist bewusst etwas Duplikation gegen ein Risiko am
Publikationspfad.

---

## 3. Mengen und dimensionssichere Umrechnung

### 3.1 Einheiten

```
measurement_units(
  id, public_id,
  code            text UNIQUE  CHECK (code ~ '^[A-Z][A-Z0-9_]{0,15}$'),
  display_name    text NOT NULL,
  dimension       text NOT NULL CHECK (dimension IN ('mass','volume','count')),
  base_factor     numeric(20,9) NOT NULL CHECK (base_factor > 0),
  active          boolean NOT NULL DEFAULT true
)
```

`base_factor` ist der Faktor auf die kanonische Basiseinheit der Dimension: Masse → Gramm,
Volumen → Milliliter, Anzahl → Stück. Genau eine aktive Zeile je Dimension hat
`base_factor = 1` (partieller Unique-Index). Einheiten sind global, nicht standortgebunden;
ein Gramm ist an jedem Standort ein Gramm.

Startbestand im Seed: `G`, `KG`, `ML`, `L`, `EL` (15 ml), `TL` (5 ml), `STK`, `PORTION`,
`PRISE`. Weitere Einheiten legt die Verwaltung an; Löschen ist nicht vorgesehen, nur
`active=false`.

### 3.2 Mengenzahl

Alle Mengen sind `numeric(12,3) CHECK (> 0)`. Kein Gleitkomma. Begründung: Rappen-Ganzzahlen
sind für Preise richtig (`menu_item_prices`), für Rezeptmengen aber unbrauchbar; `numeric`
vermeidet Rundungsdrift bei Skalierung und Summierung. Drei Nachkommastellen decken 1 g in
Kilogramm und 1 ml in Litern ab.

### 3.3 Umrechnungsregeln

1. **Innerhalb einer Dimension** ist jede Umrechnung erlaubt und exakt:
   `menge_ziel = menge_quelle * base_factor_quelle / base_factor_ziel`.
2. **Zwischen Dimensionen** ist keine allgemeine Umrechnung erlaubt. Sie ist ausschliesslich
   zutatenbezogen möglich über zwei optionale Felder auf `foods`:
   - `density_g_per_ml numeric(10,4) CHECK (> 0)` für Masse ↔ Volumen
   - `piece_weight_g numeric(10,3) CHECK (> 0)` für Anzahl ↔ Masse
3. **Fehlt der benötigte Faktor, schlägt die Umrechnung fehl.** Sie liefert kein
   Näherungsergebnis und keine Null. Aufrufer müssen den Fehler behandeln; Einkaufslisten und
   Kalkulationen zeigen die Positionen dann getrennt und kennzeichnen sie als nicht
   zusammenführbar. Das erfüllt die Backlog-Vorgabe «unvereinbare Einheiten getrennt zeigen».
4. **Rundung.** Zwischenschritte rechnen unverkürzt in der Basiseinheit. Gerundet wird
   ausschliesslich bei der Darstellung. Aggregation summiert in der Basiseinheit je Dimension
   und rechnet genau einmal am Ende in die Anzeigeeinheit.
5. `PORTION` ist eine Zähleinheit ohne Umrechnung in Masse. Portionsskalierung eines Rezepts
   ist eine Multiplikation aller Zutatenmengen mit `ziel_portionen / recipes.servings`, keine
   Einheitenumrechnung.

Die Regeln 1 bis 5 leben in einem einzigen Modul `cafeteria/quantities.py` mit reinen
Funktionen ohne Datenbankzugriff. Es gibt keine zweite Umrechnungsstelle im Code.

---

## 4. BAS-001 — Grundlagen und Lager

### 4.1 Neue Tabellen

| Tabelle | Zweck | Wesentliche Felder |
|---|---|---|
| `food_categories` | Kategorien für Zutaten | `location_id`, `code`, `name`, `sort_order`, `active`; unique `(location_id, lower(btrim(name)))` |
| `foods` | Zutaten und Lebensmittel | `location_id`, `name`, `category_id NULL`, `base_unit_id NOT NULL`, `density_g_per_ml NULL`, `piece_weight_g NULL`, `note`, `active`, `row_version`; unique `(location_id, lower(btrim(name)))` |
| `tags` | gemeinsames Schlagwortvokabular | `location_id`, `code`, `name`, `active`; unique `(location_id, code)` |
| `food_tags` | Zutat ↔ Tag | PK `(food_id, tag_id)` |
| `recipe_tags` | Rezept ↔ Tag | PK `(recipe_id, tag_id)` |
| `food_labels` | **bestätigte** Kostformlabels je Zutat | PK `(food_id, label_id)`, Form identisch `component_labels` |
| `food_allergens` | **bestätigte** Allergene je Zutat | PK `(food_id, allergen_id)`, `presence IN ('contains','may_contain')`, Form identisch `component_allergens` |
| `storage_locations` | Lagerorte | `location_id`, `code`, `name`, `sort_order`, `active`; unique `(location_id, code)` |

Ein Tagvokabular für Zutaten und Rezepte, zwei Verknüpfungstabellen. Getrennte Vokabulare
würden REC-006 («Tags suchen und gesammelt zuweisen») ohne Gegenwert verdoppeln.

### 4.2 Grenze zu INV-001

BAS-001 fordert «Lagerorte und Bestände mit Rezepten und Einkaufslisten verbinden»,
INV-001 fordert «Zugänge, Abgänge, Umbuchungen, Zählung und Korrekturen». Die Grenze:

- **BAS besitzt** `storage_locations` und die Verknüpfung Zutat ↔ Lagerort.
- **INV besitzt** das Bewegungsjournal (`inventory_movements`) und die Zählungen
  (`inventory_counts`) mit Akteur, Zeit, Menge, Einheit und Grund.
- **`foods` bekommt keine Bestandsspalte.** Ein denormalisierter Saldo neben einem Journal ist
  eine zweite Wahrheit und die klassische Fehlerquelle. Der Bestand ist ausschliesslich die
  Summe des Journals je `(food_id, storage_location_id)` in der Basiseinheit der Dimension.
- Solange INV-001 nicht geliefert ist, zeigen Stammdaten- und Einkaufsoberflächen
  «kein Bestand erfasst» und **nicht** null. Fehlende Erfassung ist kein Nullbestand.
- Eine Planänderung bucht niemals Bestand ab. Verbrauch ist eine ausdrückliche INV-Aktion.

BAS verliert dadurch keine Verpflichtung: Lagerorte, Zutaten-Lagerort-Zuordnung und die
Verbindung zu Rezept und Einkauf sind BAS-Lieferungen; nur das Buchen selbst ist INV.

---

## 5. REC-001 — Rezepte

### 5.1 Neue Tabellen

| Tabelle | Zweck | Wesentliche Felder |
|---|---|---|
| `recipes` | Rezeptkopf, veränderlich | `location_id`, `title`, `description`, `servings numeric(8,2) CHECK (>0)`, `servings_unit_id NOT NULL`, `prep_minutes NULL`, `cook_minutes NULL`, `source_kind`, `source_url NULL`, `source_note NULL`, `active`, `row_version`, `created_by`, `updated_by` |
| `recipe_ingredients` | Zutatenzeilen | PK `(recipe_id, sort_order)`, `group_label NULL`, `ingredient_text NOT NULL`, `food_id NULL`, `quantity numeric(12,3) NULL`, `unit_id NULL`, `note NULL` |
| `recipe_steps` | geordnete Schritte | PK `(recipe_id, step_number)`, `instruction text NOT NULL`, `duration_minutes NULL`, `image_sha256 NULL` |
| `recipe_revisions` | festgeschriebene, unveränderliche Fassung | `recipe_id`, `revision_number`, `snapshot_json jsonb`, `content_hash_sha256`, `created_by`, `created_at`; unique `(recipe_id, revision_number)` |
| `recipe_assets` | inhaltsadressierte Bilddaten | `sha256 text PK`, `image_data bytea`, `content_type`, `width`, `height`, `created_by`, `created_at` |
| `recipe_images` | Bild ↔ Rezept mit Herkunft | PK `(recipe_id, sort_order)`, `sha256`, `caption NULL`, `source_url NULL`, `source_license NULL`, `fetched_at NULL` |
| `cookbooks` | Kochbücher und Sammlungen | `location_id`, `name`, `description NULL`, `active`, `row_version` |
| `cookbook_recipes` | Zuordnung | PK `(cookbook_id, sort_order)`, `recipe_id` |

`source_kind text NOT NULL CHECK (source_kind IN ('manual','url','file_import','ai_assisted'))`.
Bei `url` ist `source_url` verpflichtend, bei `file_import` und `ai_assisted` ist `source_note`
verpflichtend. Ein Rezept verliert seine Herkunft nie durch spätere Bearbeitung; eine
Bearbeitung ändert `source_kind` nicht.

`recipe_ingredients`: `CHECK ((quantity IS NULL) = (unit_id IS NULL))`. `ingredient_text` ist
immer gefüllt, auch wenn `food_id` gesetzt ist — exakt das Muster von
`menu_item_components.component_text`. Ein Rezept bleibt lesbar und druckbar, auch wenn eine
Zutat später archiviert wird.

Titel sind **nicht** eindeutig. Zwei Häuser dürfen «Rindsgeschnetzeltes» unterschiedlich
kochen. Dublettenerkennung ist Sache des Imports (§9), keine Datenbankregel.

### 5.2 Bilder

`recipe_assets` übernimmt das Muster von `branding_assets`: Primärschlüssel ist der
SHA-256 der Bytes, ein `CHECK` prüft die Magic Bytes und die Selbstkonsistenz des Hashes.
Unterschied: erlaubt sind PNG **und** JPEG (`content_type IN ('image/png','image/jpeg')`),
weil Rezeptfotos Fotos sind. Obergrenze 1 MiB je Bild, gleiche Grössenordnung wie
`branding_assets`. Identische Bilder werden automatisch dedupliziert.

Herkunft liegt auf der Verknüpfung, nicht auf den Bytes: Ein aus einer Webseite übernommenes
Bild trägt `source_url`, `source_license` und `fetched_at` verpflichtend
(`CHECK (source_url IS NULL OR (source_license IS NOT NULL AND fetched_at IS NOT NULL))`).
Ohne belegte Lizenz kein importiertes Bild.

### 5.3 Revisionen und Menübindung

`recipe_revisions` ist der Anker gegen nachträgliche Änderung veröffentlichter Inhalte und
kopiert das Muster von `publication_revisions`:

- `snapshot_json` enthält Kopf, Zutatenzeilen, Schritte, Bild-Hashes und Herkunft der Fassung.
- `content_hash_sha256` über den kanonisierten Snapshot.
- Ein Trigger nach dem Vorbild von `protect_publication_revision()` verweigert `UPDATE` und
  `DELETE`.
- Eine Revision entsteht nur durch die ausdrückliche Aktion «Revision festschreiben», nie als
  Nebenwirkung eines Speicherns.

`menu_item_components.recipe_revision_id` bindet eine Menüposition an eine **Revision**, nie an
den veränderlichen Rezeptkopf. Ein späteres Bearbeiten des Rezepts kann eine bestehende
Menüwoche damit nicht rückwirkend verändern.

Constraint auf `menu_item_components`:
`CHECK (component_id IS NULL OR recipe_revision_id IS NULL)` — eine Position ist entweder an
eine Katalogkomponente oder an eine Rezeptrevision gebunden, nicht an beides. Die bestehende
Paarbedingung `component_id`/`component_row_version` bleibt unverändert. Der vorhandene Trigger
`validate_menu_item_component_scope()` wird um eine Standortprüfung erweitert: die Revision muss
zu einem Rezept desselben `location_id` gehören wie die Menüwoche.

### 5.4 Der Publikationsvertrag wird nicht angefasst

**Entscheidung: Die Rezeptbindung fügt dem Publikations-Snapshot keinen einzigen Schlüssel hinzu.**

`validate_publication_revision()` prüft den Snapshot gegen eine enge Erlaubnisliste und wird in
dieser Welle bereits von OPS-001 für Schema 20 geändert. Die veröffentlichte Nutzlast enthält
schon heute den gedruckten Komponententext; ein Rezeptbezug ist Verwaltungsherkunft, keine
Gastinformation. Folgen:

- `publication_revisions`, `patient_key_is_forbidden()` und alle öffentlichen Ausgaben bleiben
  byteidentisch zum heutigen Stand.
- Bestehende, veröffentlichte Wochen bleiben unveränderlich und preisfrei.
- Es entsteht kein Konflikt mit dem OPS-Eigentum an `validate_publication_revision()`.

Ein späteres Paket, das Rezeptangaben tatsächlich in eine Ausgabe drucken will, ist ein eigener
Snapshot-Schemaschritt mit eigener Abnahme und **nicht** Teil von REC-001.

---

## 6. Bestätigte Daten, Vorschläge und Küchenfreigabe

Der bestehende Mechanismus bleibt vollständig gültig und wird nicht erweitert:
`menu_items.allergen_mode`/`label_mode`/`origin_mode` (`auto` oder `manual`) und
`allergen_review_status` (`not_checked` oder `checked`) trennen heute Ableitung von
Küchenfreigabe. `component_effects.py` leitet im Automodus Labels nur ab, wenn **alle**
zugeordneten Komponenten sie tragen, und verweigert die Ableitung, sobald eine Position
unaufgelöster Freitext ist.

Daran ändert BAS/REC nichts. Zusätzlich gilt:

1. **Keine Ableitungskette Zutat → Komponente → Menü.** `foods.food_allergens` fliesst in
   dieser Stufe **nicht** automatisch in `component_allergens`. Der Automodus arbeitet weiter
   ausschliesslich auf dem Komponentenkatalog. Eine Zutatenableitung wäre eine stille
   Änderung publikationsnaher Daten und braucht ein eigenes Paket mit eigener Abnahme.
2. **`food_allergens` und `food_labels` enthalten ausschliesslich bestätigte Angaben.**
   Import, Barcode-Abgleich und KI schreiben dort nie direkt.
3. **Vorschläge leben getrennt** in `food_data_proposals`: `food_id NULL`, `source` (`off`,
   `supplier`, `ai`, `file_import`), `source_reference`, `fetched_at`, `payload jsonb`,
   `status IN ('open','accepted','rejected')`, `decided_by`, `decided_at`. Die Übernahme
   einzelner Felder ist eine bewusste Handlung, die einen `audit_events`-Eintrag erzeugt.
   Bestätigte Daten werden dabei nie automatisch überschrieben; ein Konflikt wird angezeigt.
4. **Fehlende Angabe bleibt fehlend.** Weder eine leere Allergenliste noch ein fehlender
   Nährwert ist eine Frei-von-Aussage. Die Anzeigen «Enthält», «Kann enthalten» und
   «Nicht erfasst» bleiben getrennt, wie in ICO-002 abgenommen.
5. Patientenausgaben bleiben preisfrei. Kosten aus CALC-001 hängen an Rezept und Zutat, nie am
   Patienten-Snapshot.

---

## 7. Revision, Konflikt, Löschung und Verlauf

**Optimistische Sperre.** `foods`, `food_categories`, `tags`, `storage_locations`, `recipes`,
`cookbooks` tragen `row_version` und den vorhandenen Trigger
`bump_row_version_and_updated_at()`. Jedes Formular führt die gelesene Version mit; eine
Abweichung bricht mit derselben Konfliktklasse ab, die der Komponentenkatalog schon nutzt
(`ComponentConflictError`-Muster, für Rezepte `RecipeConflictError`).

**Eine Sperre je Aggregat.** Änderungen an `recipe_ingredients`, `recipe_steps` und
`recipe_images` erhöhen `recipes.row_version`. Es gibt keine Version je Zeile. Zwei Personen,
die gleichzeitig dasselbe Rezept bearbeiten, kollidieren sichtbar; die zweite Speicherung
schlägt fehl und zeigt den aktuellen Stand.

**Löschung.** Kein Hard Delete auf Stammdaten und Rezepten. `active=false` ist die
Ausserbetriebnahme, wie im Komponentenkatalog. Fremdschlüssel aus `recipe_ingredients.food_id`,
`menu_item_components.recipe_revision_id`, `cookbook_recipes.recipe_id` und
`menu_components.food_id` sind `ON DELETE RESTRICT`. Ein Datensatz, auf den je verwiesen wurde,
verschwindet nicht.

**Verlauf.** `recipe_revisions` ist unveränderlich. Jede Anlage, Änderung, Archivierung,
Reaktivierung, Revisionsfestschreibung und Vorschlagsentscheidung schreibt einen
`audit_events`-Eintrag mit `entity_type` (`food`, `recipe`, `recipe_revision`, `tag`,
`storage_location`, `cookbook`, `food_proposal`), `entity_public_id` und Akteur. `audit_events`
ist bereits durch `trg_audit_events_immutable` und `trg_audit_events_no_truncate` geschützt.

---

## 8. Rollen und Rechte

**Anwendungsfähigkeiten** (`cafeteria/roles.py`), drei neue Werte:

| Fähigkeit | Bedeutung | Editor | Publisher | Admin |
|---|---|---|---|---|
| `masterdata.write` | Zutaten, Kategorien, Tags, Lagerorte pflegen | ja | ja | `*` |
| `recipe.write` | Rezepte, Schritte, Bilder, Kochbücher pflegen und Revisionen festschreiben | ja | ja | `*` |
| `recipe.import` | Importstapel übernehmen, Vorschläge in bestätigte Daten überführen | nein | ja | `*` |

Lesen läuft über die vorhandene Fähigkeit `draft.read`. `recipe.import` ist getrennt, weil dort
herkunftsbehaftete Fremddaten zu bestätigten Daten werden — dieselbe Trennschärfe, die
`publication.publish` heute hat.

**Datenbankrollen.** `cafeteria_app` erhält `SELECT, INSERT, UPDATE` auf den neuen Tabellen und
**kein** `DELETE`; Ausserbetriebnahme läuft über `active`. `cafeteria_backup` erhält `SELECT`
auf Tabellen und Sequenzen, nach dem Muster der Zeilen für `cafeteria.api_keys`.
`cafeteria_auth_issuer` erhält nichts.

Alles, was Revisionen festschreibt, Vorschläge übernimmt oder Importstapel überführt, läuft über
`SECURITY DEFINER`-Funktionen im Schema `cafeteria` mit `p_actor_id`, Rechteprüfung in der
Funktion und Audit im selben Transaktionsschritt — Muster
`cafeteria.create_api_key` / `cafeteria.record_menu_review`.

---

## 9. Importe: Grenze und Prüfung

**Eigene Stapeltabellen**, formgleich zu `import_batches`/`import_rows`, aber ohne `profile_id`:

```
recipe_import_batches(id, public_id, source_kind, source_filename, source_sha256,
                      status IN ('validated','rejected','imported'),
                      row_count, error_count, created_by, created_at)
recipe_import_rows(import_batch_id, row_number, row_payload jsonb,
                   validation_errors jsonb DEFAULT '[]', target_public_id uuid NULL,
                   PRIMARY KEY (import_batch_id, row_number))
```

Verbindliche Regeln:

1. **Ein Importlauf schreibt nie direkt in `foods` oder `recipes`.** Er erzeugt einen Stapel.
   Die Übernahme ist eine getrennte, bestätigte Aktion mit `recipe.import` und läuft
   transaktional: entweder alle freigegebenen Zeilen oder keine.
2. **Herkunft ist Pflicht.** Jede übernommene Zeile schreibt `source_kind`, Quelle und
   Abrufzeit auf das Zielobjekt.
3. **Grenzen in Stufe 1:** Datei ≤ 5 MiB, ≤ 2000 Zeilen, Inhaltstypen `text/csv`,
   `application/json`, `image/png`, `image/jpeg`. Keine Makroformate. Kein Ausführen
   importierter Skripte. Bei Netzabruf: begrenzte Antwortgrösse, begrenzte Weiterleitungen,
   feste Zieladressliste.
4. **Dubletten** werden angezeigt und entschieden, nicht automatisch zusammengeführt.
5. **Kein Import veröffentlicht.** Ein Import erzeugt nie eine Menüwoche, nie eine Publikation
   und nie eine bestätigte Allergenangabe.

**Formatzusagen.** Stufe 1 unterstützt genau zwei Formate: CSV und JSON nach einem in
`docs/CSV_IMPORT_EXPORT.md` zu ergänzenden **Dishboard-eigenen** Schema. XLSX, Schema.org und
Pauli Kitchen Solution sind je ein eigenes Adapterpaket.

Zu Pauli liegt **kein** Format- oder Quellnachweis vor. Belegt sind eine
Fremdprogramm-Exportbeschreibung von Juni 2021 und eine Produktübersicht von Juni 2023; eine
heute offen dokumentierte API, ein Feldschema oder eine berechtigte Beispieldatei sind nicht
belegt. Vor Beginn eines Pauli-Adapters ist eine reale, berechtigte Beispieldatei mit
Exportversion erforderlich. Bis dahin wird keine Pauli-Kompatibilität behauptet.

Zu Tandoor: `develop` auf `e160ceecaee0b269924be600a6d01ecb0bd55e30` zeigt formatspezifische
Adapter und einen URL-Importer auf der separat MIT-lizenzierten Bibliothek `recipe-scrapers`;
ein generischer Excel-/CSV-/Pauli-Rezeptimport ist dort nicht nachgewiesen. Tandoor steht unter
AGPL v3 mit Commons Clause. Es wurde kein Tandoor-Code übernommen; dieser Vertrag übernimmt
Funktionsziele, keinen Quellcode. Eine Eins-zu-eins-Kompatibilität wird nicht behauptet.

---

## 10. Rezepteditor: Bewertung von HugeRTE

Der Nutzerwunsch nach HugeRTE ist aufgenommen. Belegter Befund und Entscheidung:

**Vorhandene Editoroberfläche.** Der Admin arbeitet heute vollständig mit Tabler-Formularen und
`textarea`; es ist kein Rich-Text-Editor eingebunden. Die Menü-, Komponenten-, Marken- und
Druckvorlageneditoren sind serverseitig gerenderte Formulare mit gezielt ergänztem JavaScript
(`static/admin.js`, 13 KB).

**CSP.** Der aktive Header ist `default-src 'self'; img-src 'self' data:; style-src 'self';
script-src 'self'` und enthält an keiner Stelle `unsafe-inline`. TinyMCE-Abkömmlinge — HugeRTE
ist der Community-Fork von TinyMCE 6 — setzen Skin- und Inhaltsstile zur Laufzeit. **Ob HugeRTE
ohne `unsafe-inline` betrieben werden kann, ist unbelegt.** Diese Frage ist vor jeder Einbindung
mit einem echten Browserlauf gegen genau diesen Header zu beantworten. Eine Lockerung auf
`style-src 'unsafe-inline'` würde den Header für den gesamten Admin schwächen und ist ohne
gesonderte Sicherheitsabnahme ausgeschlossen.

**Auslieferung.** Ein Offline-Pin wäre machbar: `static/vendor/` enthält bereits Tabler,
Tabler-Icons, Swagger UI und Food-Symbole mit `*.lock.json` und Paketprüfungen
(`test_tabler_package_verification.py`, `test_swagger_ui_assets.py`). Die Verfügbarkeit ist
also nicht das Hindernis.

**Entscheidung für REC-001.** Rezeptschritte werden als **Klartext** gespeichert
(`recipe_steps.instruction text`) und escaped gerendert. Das erfüllt die REC-001-Vorgabe
«geordnete Schritte» vollständig, ohne gespeichertes HTML, ohne Sanitizer-Pflicht und ohne
CSP-Änderung. Ein Rich-Text-Editor ist ein **eigenes späteres Arbeitspaket (R-RTE)** und
**keine Voraussetzung** für eine nutzbare Rezeptverwaltung.

Eintrittsbedingungen für R-RTE, alle vor einer Technologiefreigabe zu erfüllen:

1. Nachgewiesener Betrieb ohne `unsafe-inline`, belegt durch einen Browserlauf mit leerer
   CSP-Verletzungsliste — oder ein begründeter, sicherheitsgeprüfter Header-Vorschlag.
2. Serverseitige Erlaubnisliste für gespeichertes HTML mit Tests gegen Skript-, Stil- und
   Ereignisattribute.
3. Tastatur- und Screenreader-Nachweis auf der tatsächlichen Oberfläche.
4. Vollständige Tabler-Formularintegration einschliesslich Fehlerfokus, nicht nur eine Hülle.
5. Offline-Pin mit Lizenznachweis und Paketprüfung.

Es ist keine Abhängigkeit installiert und keine Technologie freigegeben.

---

## 11. Migrationen

Dieser Vertrag reserviert keine Nummer. Beschrieben wird die Reihenfolge oberhalb des
abgenommenen Schema-20-Vertrags von OPS-001; Root serialisiert und vergibt Nummern.

| Schritt | Inhalt | Voraussetzung |
|---|---|---|
| M-A | `measurement_units`, `food_categories`, `foods`, `tags`, `food_tags`, `food_labels`, `food_allergens`, `storage_locations`, `food_data_proposals`, Seed-Einheiten, Rechte, Trigger | geprüftes Schema 20 |
| M-B | `recipes`, `recipe_ingredients`, `recipe_steps`, `recipe_revisions`, `recipe_assets`, `recipe_images`, `cookbooks`, `cookbook_recipes`, `recipe_tags`, Unveränderlichkeitstrigger | M-A |
| M-C | `menu_components.food_id`, `menu_item_components.recipe_revision_id`, `dish_templates.recipe_id`, Erweiterung `validate_menu_item_component_scope()` | M-B |
| M-D | `recipe_import_batches`, `recipe_import_rows` | M-B |

Jeder Schritt hebt `db.SCHEMA_VERSION`, `APPLICATION_VERSION`, `database/validate_schema.py`
und `tools/validate_package.py` nach dem in `0016_v18_to_v19.sql` und dem OPS-Vertrag gezeigten
Muster. Frühere Migrationen bleiben byteidentisch. M-C ist der einzige Schritt, der bestehende
Tabellen berührt; er fügt ausschliesslich nullable Spalten hinzu und lässt jede vorhandene
Zeile gültig.

---

## 12. Abgrenzung zu den Folgeverträgen

| ID | Was dieser Vertrag festlegt | Was offen bleibt |
|---|---|---|
| REC-002 KI | Vorschläge landen in `food_data_proposals` und in Importstapeln, nie direkt in bestätigten Daten | Modelle, Erkennung, Oberfläche |
| REC-003 Planung/Einkauf | Portionsskalierung, Basiseinheiten-Aggregation, Fehlschlag bei fehlender Umrechnung | Einkaufslistenmodell, Abhakstatus |
| REC-004 Sammlungsimporte | Stapel-, Herkunfts- und Grenzvertrag aus §9 | XLSX-, Pauli-, Fremdmanager-Adapter je einzeln |
| REC-005 Webimport | `source_kind='url'`, Pflichtherkunft, Netzgrenzen | Parserwahl, Prüfung von `recipe-scrapers` |
| REC-006 Suche/Tags | `tags`, `food_tags`, `recipe_tags` als gemeinsames Vokabular | Volltext-/Trigram-Indizes, Gewichtung, Batch-Zuweisung |
| REC-007 Druck | Rezepte sind aus kanonischen Daten druckbar; keine Snapshot-Änderung | Layout, Seitenumbruch, Vorlageneditor-Anbindung |
| NUT-001 | Trennung bestätigt/Vorschlag, Bezugsmenge über `measurement_units` | Nährwertmodell je 100 g/ml, Lieferantendaten |
| OFF-001 | Barcode-Treffer sind Vorschläge mit Quelle und Abrufzeit | Feldzuordnung, Schweizer Abdeckung, Lizenzhinweise |
| CALC-001 | Mengen, Einheiten, Portionen, Ausbeute rechnen auf `quantities.py`; fehlender Preis bleibt fehlend | Preisgültigkeiten, Kalkulationsvorgaben |
| INV-001 | `storage_locations` gehört BAS, Journal und Saldo gehören INV; keine Bestandsspalte auf `foods` | Bewegungs- und Zählmodell |
| ORD-001 | Bedarf leitet sich aus Rezept, Portion und Einheit ab | Lieferanten, Warenkorb, Absendevertrag |

---

## 13. Was dieser Vertrag ausdrücklich nicht zusagt

- Keine Pauli- oder Tandoor-Kompatibilität, keine Übernahme fremder Rezeptbestände.
- Keine Technologiefreigabe für HugeRTE oder einen anderen Rich-Text-Editor.
- Keine Änderung an bestehenden Publikationen, an `publication_revisions` oder an
  patientenseitigen Ausgaben.
- Keine automatische Ableitung von Allergenen oder Kostformen aus Zutaten in Menüpositionen.
- Keine Bestandsbuchung durch Planung.
- Keine installierte Abhängigkeit, keine geschriebene Migration, kein Produktcode in diesem
  Arbeitsschritt.
