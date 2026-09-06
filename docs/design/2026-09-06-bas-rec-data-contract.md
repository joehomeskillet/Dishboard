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

Paralleler Auftrag OPS-001 besitzt Schema 20 und `0017_v19_to_v20.sql`; nach dem belegten
Fable-Sessionlimit übernimmt Root mit Codex-Lanes. Der OPS-Stand bleibt aktiv und ungeprüft. Dieser
Vertrag reserviert **keine** Migrationsnummer und beschreibt seine Migrationen ausdrücklich
oberhalb des dann geprüften Schema-20-Vertrags. Nummern und Reihenfolge weist Root zu.

**Geprüfter Teilstand:** B1 (`e0fb93e`, ursprünglich `c7873fa`) ist von Root unabhängig geprüft
und im aktuellen Code-Stand enthalten: **101 passed in 1.26s**, Ruff bestanden, Mypy ohne Fehler
in zwei Dateien ([JUnit](/tmp/dishboard-root-quantities-b1-0906.xml)). Noch nicht deployed;
BAS/REC bleiben offen. B2 wartet auf das abgenommene OPS-Schema 20.

**Vertragsentscheid B2 vom 6. September 2026**, Branch `docs/bas-b2-contract-decisions-0906`:
Die fünf offenen Punkte aus dem B2-Startbericht
([wp-b32fd34ebb6e](/nvmetank1/projects/rag-stack/.claude/reports/wp-b32fd34ebb6e.md)) sind hier
abschliessend entschieden — Feldgrenzen, Normalisierung und No-op-Semantik (§4.3),
Lagerortarchivierung (§4.4), öffentlicher Python-Servicevertrag (§4.5), Vorschlagsübernahme
(§6.1) sowie die gemeinsame Sperrreihenfolge samt begründet korrigierter Actor-Sperre (§8.1).
Es bleibt bei keiner reservierten Migrationsnummer und keinem Schema-Pin; B2 beginnt weiterhin
erst auf dem geprüften OPS-Schema-20-Freeze.

---

## 1. Identität, Geltungsbereich und Namensraum

Alle neuen Objekte liegen im Schema `cafeteria`. Bearbeitbare Entitäten folgen diesem Muster;
Zuordnungstabellen und inhaltsadressierte Assets haben die in §4/§5 genannten Schlüssel:

- `id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY`
- `public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE` als einzige nach aussen sichtbare Kennung
- `row_version bigint NOT NULL DEFAULT 1 CHECK (row_version > 0)` auf jeder direkt bearbeitbaren Tabelle
- `created_at`/`updated_at timestamptz NOT NULL DEFAULT clock_timestamp()`
- `created_by`/`updated_by bigint REFERENCES users(id)` überall dort, wo ein Mensch schreibt

**Standortbindung.** Stammdaten und Rezepte sind standortgebunden
(`location_id bigint NOT NULL REFERENCES locations(id)`).
Standort-IDs werden dienstseitig über `resolve_single_active_location_connection()` aufgelöst,
nicht aus einem Formular vertraut; keine oder mehrere aktive Standorte brechen geschlossen ab.
Jeder Read, Join und Write filtert diesen Standort. Alle Verknüpfungen standortgebundener
Objekte müssen zusätzlich in der DB Gleichheit erzwingen, über zusammengesetzte FKs auf
`(location_id, id)` oder einen vollständig benannten Scope-Trigger bei indirekter Auflösung:
food↔category/tag/storage, recipe↔food/tag/revision/image, cookbook↔recipe,
proposal↔food und import-row↔batch/target. Unterzeilen tragen dazu den Standort des Kopfs;
Elternstandorte sind ab Anlage unveränderlich. Standortfremde UUIDs ergeben keine Verknüpfung.

M-C prüft `menu_components.food_id` gegen den Komponentenstandort und
`menu_item_components.recipe_revision_id` über Rezept→Woche. `dish_templates` hat heute
keinen Standort: ohne Rezept bleibt eine Vorlage global, mit Rezept gilt dessen Standort.
Ein DB-Trigger prüft bei Rezeptzuweisung **alle** schon referenzierenden Menüwochen; ein
Trigger auf `menu_items.dish_template_id` prüft jede neue Verwendung. Readback/Auswahl filtern
rezeptgebundene Vorlagen entsprechend. UPDATE-OF-Listen enthalten jeweils auch die neuen
FK-Spalten; nur die Triggerfunktion zu erweitern reicht nicht. Globale Einheiten,
`allergens` und `dietary_labels` sind die ausdrücklich globalen Vokabular-Ausnahmen.

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
| `settings` | vorhandener Speicher; ohne konkret benötigte Anzeigeoption kein neuer Schlüssel | keine zugesagte Änderung |
| `publication_revisions` | unverändert | **keine** |

`component_allergens`, `component_labels`, `origin_declarations`, `menu_item_prices` und der
öffentliche Snapshotform bleiben unverändert. Interne Admin-DTOs, Speichern, Kopieren und
Menüprüfbelege benötigen dagegen den vollständigen R5-Vertrag (§5.3).

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
  dimension       text NOT NULL CHECK (dimension IN ('mass','volume','count','contextual')),
  base_factor     numeric NULL,
  active          boolean NOT NULL DEFAULT true,
  row_version, created_at, updated_at, created_by, updated_by
)
```

Für `mass`, `volume` und `count` ist `base_factor` verpflichtend, endlich und positiv (§3.2).
Er bezeichnet Gramm, Milliliter beziehungsweise Stück je Einheit. Die kanonischen Zeilen
sind ausdrücklich `G/mass/1`, `ML/volume/1` und `STK/count/1`, jeweils aktiv. Seed,
DB-Änderungs-/Lösch-/TRUNCATE-Schutz und Schema-Prüfung sichern ihre Existenz und ihren
unveränderten Inhalt. Ein Unique-Index auf Faktor 1 würde weder Existenz noch die richtige
Einheit beweisen und wird nicht verwendet; allein `code` ist eindeutig.

`contextual` hat zwingend `base_factor IS NULL`: `PORTION` und `PRISE` haben keine globale
Grösse, auch keine Stückzahl. Umrechnung ist nur zum selben Code als Identität erlaubt,
niemals zwischen diesen Codes oder nach `STK`, `G` oder `ML`, auch nicht mit Zutatenfaktoren.
Einheiten sind global; ihre kontextabhängige Verwendung erzeugt keine universelle Prise.

Startbestand im Seed: `G`, `KG`, `ML`, `L`, `EL` (15 ml), `TL` (5 ml), `STK`, `PORTION`,
`PRISE` (beide `contextual`, Faktor NULL). EL/TL bezeichnen ausdrücklich die hier festgelegten
15-/5-ml-Masse, keine beliebigen Haushaltslöffel. `code`, `dimension` und `base_factor` sind
ab Anlage unveränderlich; eine andere Bedeutung erfordert eine neue Einheit. Name und
Aktivstatus sind versioniert bearbeitbar, die drei kanonischen Einheiten bleiben aktiv.
Kein Löschen. Archivierte Einheiten bleiben für bestehende Rezepte und Revisionen auflösbar.

### 3.2 Mengenzahl

Mengen einschliesslich Portionszahlen sind endliche positive `Decimal`-Werte mit höchstens
12 Vorkomma- und 6 Nachkommastellen; Faktoren einschliesslich Dichte/Stückgewicht höchstens
11 Vorkomma- und 9 Nachkommastellen. `NaN`, `sNaN`, positive/negative Unendlichkeit, Null,
negative Werte und binäre `float`-/bool-Eingaben werden abgelehnt. Numerisch bedeutungslose
Endnullen dürfen normalisiert werden; zusätzliche nichtnullige Dezimalstellen nicht.

Persistenz verwendet `numeric` ohne still rundenden `(p,s)`-Typmodifikator, mit CHECKs für
Endlichkeit, `> 0`, Obergrenze und die genannte Nachkommastellengrenze. Dienst und DB prüfen
dasselbe Wertegebiet. CSV/JSON werden dezimalverlustfrei eingelesen; Überpräzision ist ein
sichtbarer Importfehler vor dem Schreiben, keine automatische Kürzung auf drei Stellen.
Kanonische Dezimalzeichenketten in JSON-Snapshots erhalten den Wert ohne Float-Zwischenschritt.

### 3.3 Umrechnungsregeln

1. **Innerhalb von mass, volume oder count** ist jede Umrechnung erlaubt:
   `menge_ziel = menge_quelle * base_factor_quelle / base_factor_ziel`.
2. **Zwischen Dimensionen** ist keine allgemeine Umrechnung erlaubt. Sie ist ausschliesslich
   zutatenbezogen möglich über zwei optionale Felder auf `foods`:
   - `density_g_per_ml` im Faktorwertegebiet (§3.2) für Masse ↔ Volumen
   - `piece_weight_g` im Faktorwertegebiet (§3.2) für Anzahl ↔ Masse
   Anzahl ↔ Volumen benötigt beide Faktoren derselben Zutat. Kein Faktor gilt für `contextual`.
3. **Fehlt der benötigte Faktor, schlägt die Umrechnung fehl.** Sie liefert kein
   Näherungsergebnis und keine Null. Aufrufer müssen den Fehler behandeln; Einkaufslisten und
   Kalkulationen zeigen die Positionen dann getrennt und kennzeichnen sie als nicht
   zusammenführbar. Das erfüllt die Backlog-Vorgabe «unvereinbare Einheiten getrennt zeigen».
4. **Präzision und Rundung.** Die reinen Funktionen verwenden einen eigenen Decimal-Kontext
   mit 50 signifikanten Stellen und `ROUND_HALF_UP`, unabhängig vom globalen Kontext.
   Division kann periodisch sein und wird dann auf diese Präzision gerundet; beliebige exakte
   Division wird nicht versprochen. Keine Zwischenquantisierung auf die Speicher-/Anzeige-Skala.
   Aggregation summiert kompatible Werte zuerst in der Basiseinheit und konvertiert einmal am
   Ende. Anzeige rundet ausdrücklich auf höchstens 6 Nachkommastellen mit `ROUND_HALF_UP`;
   dies ändert keine gespeicherten Werte. Ein berechneter Wert ausserhalb des Speichergebiets
   wird nicht still gespeichert: ausdrückliche Rundungsentscheidung und erneute Validierung
   sind notwendig. Import bleibt ohne solche automatische Rundung.
5. Portionsskalierung multipliziert mit `ziel_portionen / recipes.servings`; sie ist keine
   Einheitenumrechnung und funktioniert auch für eine einzelne Prisen-/Portionszeile.
   `to_base` und `sum_in_base` lehnen kontextabhängige Einheiten ab: ohne konkreten
   Rezept-/Zeilenkontext darf eine gleichnamige Prise nicht über Rezepte aggregiert werden.

Die Regeln 1 bis 5 leben in einem einzigen Modul `cafeteria/quantities.py` mit reinen
Funktionen ohne Datenbankzugriff. Es gibt keine zweite Umrechnungsstelle im Code.
B1 liefert diesen stdlib-Vertrag vor Schema 20; B2 liefert alle DB-Constraints und Seeds.

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
| `food_storage_locations` | Zutat ↔ Lagerort | `location_id`, PK `(food_id, storage_location_id)`, beide FKs mit Standortgleichheit; keine Menge/Bestandsspalte |

**Archivierung von Lagerorten:** Ein Lagerort wird nur archiviert (`active=false`), wenn keine
`food_storage_locations`-Zuordnung mehr auf ihn verweist; sonst wird der Versuch sichtbar
verweigert und die Zuordnungen werden vorher ausdrücklich entfernt. Reaktivieren bleibt möglich.
Archivierte Lagerorte werden in Auswahllisten ausgeblendet, bleiben aber für bestehende
Referenzen und den Verlauf lesbar. Die vollständige Regel samt Sperr- und Fehlerverhalten
steht in §4.4.

Ein Tagvokabular für Zutaten und Rezepte, zwei Verknüpfungstabellen. Getrennte Vokabulare
würden REC-006 («Tags suchen und gesammelt zuweisen») ohne Gegenwert verdoppeln.
`foods` speichert zusätzlich `source_kind` (`manual`, `url`, `file_import`, `ai_assisted`,
`off`, `supplier`), `source_reference NULL`, `source_url NULL`, `source_note NULL`,
`fetched_at NULL`. Nichtmanuelle Herkunft braucht Referenz, Abrufzeit und Quelle oder Notiz;
`url` zusätzlich die URL. Diese Herkunft bleibt bei Bearbeitung erhalten; neue Feldherkünfte
aus bestätigten Vorschlägen bleiben in der unveränderlichen Entscheidung samt Audit erhalten.
`allergen_review_status IN ('not_checked','checked')` mit Standard `not_checked` erfasst die
ausdrückliche Küchenprüfung; Änderungen der Angaben setzen sie zurück. Auch `checked` plus
leere Liste ist kein Frei-von-Label. Labels erfordern ihre eigene positive Bestätigung.

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

### 4.3 Feldgrenzen, Normalisierung und identische Speicherung

Diese Grenzen gelten für alle Tabellen aus §4, identisch in Dienst und Datenbank; R1 übernimmt
sie unverändert für §5. B2 liefert die zugehörigen CHECKs.

| Feld | Grenze |
|---|---|
| `code` (`measurement_units`, `food_categories`, `tags`, `storage_locations`) | `^[A-Z][A-Z0-9_]{0,15}$`, also höchstens 16 Zeichen; ab Anlage unveränderlich; keine stille Grossschreibung, abweichende Eingabe wird abgelehnt |
| `display_name`, `name` | 1 bis 120 Zeichen nach Normalisierung |
| `foods.note`, `source_note` | höchstens 500 Zeichen |
| `source_reference` | höchstens 200 Zeichen |
| `source_url` | höchstens 2048 Zeichen, `^https?://`, keine Steuerzeichen |
| `sort_order` | `smallint` zwischen 1 und 9999 |
| `food_data_proposals.payload` | kanonisch serialisiert höchstens 64 KiB, höchstens 200 Schlüssel, Verschachtelungstiefe höchstens 5 |
| Listen je Fachaktion (Tags, Labels, Allergene, Lagerorte, Vorschlagsfelder) | höchstens 64 Einträge, wie `component_catalog_metadata._MAX_METADATA_ENTRIES` |
| Mengen und Faktoren | ausschliesslich §3.2; Ein- und Ausgabe als kanonische Decimal-Zeichenkette ohne Float-Zwischenschritt, wie B1 |

Die Normalisierung ist deterministisch und läuft vor jeder Prüfung: Unicode-NFC; Steuer- und
Formatzeichen (Unicode-Kategorie `C`) sowie `<` und `>` werden abgelehnt statt entfernt —
dieselbe Regel wie `print_template_config.plain_text`; Rand-Leerzeichen werden entfernt, innere
Leerzeichenfolgen zu genau einem `U+0020` zusammengefasst. Erst danach greifen Längengrenze und
die Eindeutigkeit `(location_id, lower(btrim(name)))`. Codes werden nie umgeschrieben. Dieselbe
Normalisierung gilt für Vorschlagswerte vor jedem Vergleich (§6.1).

**Identische Speicherung ist keine Fachaktion.** Ergibt eine Eingabe nach Normalisierung exakt
den gespeicherten Zustand, bleiben `row_version`, `updated_at` und `updated_by` unverändert, es
entsteht kein `audit_events`-Eintrag, und der Dienst liefert die aktuelle Version zurück — genau
das Verhalten von `component_catalog_store.update_component`. Ein angeforderter Zustandswechsel
muss dagegen wechseln: Archivieren eines bereits archivierten oder Reaktivieren eines aktiven
Objekts ist ein sichtbarer Konflikt, kein stiller Erfolg. Eine wirksame Fachaktion erhöht genau
eine Aggregatversion um eins und schreibt genau einen Audit-Eintrag (§7).

### 4.4 Lagerorte: Zuordnen, Archivieren, Reaktivieren

- Zuordnen und Lösen in `food_storage_locations` ist eine Aktion am **Food**-Aggregat: sie führt
  die erwartete `foods.row_version` mit, erhöht sie einmal und schreibt einen Audit-Eintrag. Die
  Lagerortzeile wird dabei nach §8.1 als Vokabular (Rang 5) `FOR SHARE` gesperrt und muss unter
  dieser Sperre aktiv sein; einem archivierten Lagerort wird nichts neu zugeordnet.
- **Archivieren eines Lagerorts mit bestehenden Zuordnungen wird sichtbar verweigert**
  (`ERRCODE 55000`, im Dienst `MasterDataConflictError`) und nennt die Zahl der betroffenen
  Zutaten. Die Zuordnungen werden vorher ausdrücklich je Zutat entfernt. Es gibt keine Kaskade,
  kein stilles Lösen und keine zweite SQL-Semantik in B4; B4 ist reiner Verbraucher.
- Reaktivieren ist jederzeit möglich und prüft keine Zuordnungen.
- Die Reihenfolge ist kollisionsfrei: Archivieren sperrt die Lagerortzeile als geschriebenes
  Aggregat `FOR UPDATE` und zählt erst danach; Zuordnen sperrt dieselbe Zeile vorher als
  Vokabular `FOR SHARE`, danach das Food. Beide Wege berühren die Lagerortzeile also, bevor sie
  das Food berühren; es entsteht kein Zyklus. Eine gleichzeitige Zuordnung wird entweder
  mitgezählt und verhindert das Archivieren, oder sie läuft nach dem Archivieren in die erneute
  `active`-Prüfung und wird abgelehnt. Eine Zuordnung zu einem archivierten Lagerort kann so
  nicht entstehen.
- Archivierte Lagerorte bleiben für Verlauf und bestehende Referenzen lesbar.

### 4.5 Öffentlicher Python-Servicevertrag

«Öffentlich» meint stabile Python-Importe für B3, B4 und R1, **keine** neue HTTP-Schnittstelle.
B2 liefert fünf Module mit je unter 400 Zeilen: `master_data_store.py` als einzige Importfläche,
`master_data_types.py` für DTOs und Fehler, `master_data_reads.py` für feste Leseabfragen,
`master_data_commands.py` für gebundene Definer-Aufrufe und `master_data_proposals.py` für
Normalisierung und Erlaubnisliste nach §6.1. B3, B4 und R1 importieren ausschliesslich
`master_data_store` und `master_data_types` und legen keine eigenen DML-, Migrations- oder
Definer-Pfade an.

- Actor: das vorhandene `auth.local_users.ActorExpectation(user_id, authz_version)` wird
  wiederverwendet, kein zweiter Typ.
- Ziel: `ObjectExpectation(public_id: str, row_version: int)`. Nie eine Datenbank-ID und nie ein
  Standort aus dem Formular; der Standort wird serverseitig auf derselben Verbindung aufgelöst.
- Ergebnis jedes Mutators: `MutationResult(public_id: str, row_version: int)`.
- DTOs sind eingefrorene Dataclasses ohne interne IDs: `UnitDTO(public_id, code, display_name,
  dimension, base_factor: Decimal | None, active, row_version)`; `VocabularyDTO(public_id, kind,
  code, name, sort_order: int | None, active, row_version)` für Kategorie, Tag und Lagerort;
  `SourceDTO(kind, reference, url, note, fetched_at)`; `FoodDTO(public_id, name, category:
  VocabularyDTO | None, base_unit: UnitDTO, density_g_per_ml, piece_weight_g, note,
  allergen_review_status, source: SourceDTO, active, row_version, allergens: tuple[tuple[str,
  str], ...], labels, tags, storage_locations)`; `ProposalDTO(public_id, row_version, status,
  source: SourceDTO, food_public_id, payload, decision: ProposalDecision | None)` mit
  `ProposalDecision(status, decided_at, adopted, unchanged, not_supported, food_public_id,
  food_row_version_before, food_row_version_after)`.

Engine-gebundene Dienste, je Aufruf genau eine Transaktion:

```
list_units(engine, *, include_archived=False, limit=200, offset=0) -> tuple[UnitDTO, ...]
get_unit(engine, public_id) -> UnitDTO
create_unit(engine, actor, *, code, display_name, dimension, base_factor) -> MutationResult
rename_unit(engine, actor, target, *, display_name) -> MutationResult
set_unit_active(engine, actor, target, *, active) -> MutationResult
list_vocabulary(engine, kind, *, include_archived=False, limit=200, offset=0) -> tuple[VocabularyDTO, ...]
get_vocabulary(engine, kind, public_id) -> VocabularyDTO
create_vocabulary(engine, kind, actor, *, code, name, sort_order=None) -> MutationResult
update_vocabulary(engine, kind, actor, target, *, name, sort_order=None) -> MutationResult
set_vocabulary_active(engine, kind, actor, target, *, active) -> MutationResult
list_foods(engine, *, include_archived=False, category=None, tag=None, search=None,
           limit=200, offset=0) -> tuple[FoodDTO, ...]
get_food(engine, public_id) -> FoodDTO
create_food(engine, actor, payload) -> MutationResult
update_food(engine, actor, target, payload) -> MutationResult
set_food_active(engine, actor, target, *, active) -> MutationResult
replace_food_tags(engine, actor, target, tag_public_ids) -> MutationResult
replace_food_metadata(engine, actor, target, *, allergens, labels) -> MutationResult
set_food_allergen_review(engine, actor, target, *, checked) -> MutationResult
replace_food_storage_locations(engine, actor, target, storage_public_ids) -> MutationResult
list_proposals(engine, *, status=None, food=None, limit=200, offset=0) -> tuple[ProposalDTO, ...]
get_proposal(engine, public_id) -> ProposalDTO
create_proposal(engine, actor, *, source, source_reference, fetched_at, payload,
                source_url=None, source_note=None, food_public_id=None) -> MutationResult
accept_proposal(engine, actor, proposal, food, fields) -> ProposalDecision
reject_proposal(engine, actor, proposal, *, reason=None) -> ProposalDecision
```

`kind` ist `Literal['food_category','tag','storage_location']` und wählt aus einer festen
Zuordnung die passende Definer-Funktion; dynamisches SQL entsteht dabei nicht. Jede `list_*`
nimmt `limit` und `offset` entgegen und begrenzt `limit` auf höchstens 500; die Sortierung ist je
Entität deterministisch und verwendet ausschliesslich tatsächlich vorhandene Spalten, `public_id`
immer als letzten Tie-break — keine Extra-Spalte wird dafür neu eingeführt:

- `list_vocabulary` für `kind IN ('food_category','storage_location')`, die beide `sort_order`
  besitzen: `sort_order` (NULLS LAST), dann `lower(btrim(name))`, dann `public_id`.
- `list_vocabulary` für `kind='tag'`, ohne `sort_order`-Spalte (§4.1): `lower(btrim(name))`,
  dann `public_id`.
- `list_units`, ohne `sort_order`- und ohne `name`-Spalte — Einheiten haben `display_name`
  (§3.1): `code`, dann `public_id`. `code` ist eindeutig und ab Anlage unveränderlich, damit
  bleibt die Reihenfolge auch über eine spätere `rename_unit`-Umbenennung von `display_name`
  stabil.
- `list_foods`, ohne `sort_order`-Spalte (§4.1): `lower(btrim(name))`, dann `public_id`.
- `list_proposals`, ohne Namens- oder Sortierfeld (§6): `created_at`, dann `public_id`.

Einheiten sind global und werden ohne Standortfilter gelesen; ihre Semantikfelder `code`,
`dimension` und `base_factor` sind unveränderlich, deshalb gibt es nur `rename_unit`. Kanonische
Einheiten sind nicht deaktivierbar.

Verbindungsgebundene Auflösung innerhalb einer fremden Transaktion, für R1 und später R5:

```
resolve_food(connection, location_id, public_id, *, include_archived=True) -> FoodDTO
resolve_unit(connection, code) -> UnitDTO
resolve_tag(connection, location_id, public_id, *, include_archived=True) -> VocabularyDTO
```

Diese drei öffnen keine eigene Transaktion und keine zweite Engine-Verbindung; archivierte
Referenzen bleiben lesbar, damit alte Rezepte und Revisionen auflösbar sind.

Fehlerklassen in `master_data_types.py`, alle von `MasterDataError` abgeleitet — nie `None`,
nie eine rohe SQL-Ausnahme: `MasterDataValidationError`, `MasterDataNotFoundError`,
`MasterDataConflictError` mit Unterklasse `StaleObjectError`, `ActorDeniedError` mit Unterklasse
`StaleActorError`, `MasterDataConfigurationError` und `MasterDataUnavailableError`. Der
Verbraucher bildet **vollständig** fest ab: 400 bei `MasterDataValidationError`, mit dem
bestehenden Formular-/Fehlerfokus-Verhalten; 401 bei fehlender Sitzung oder `StaleActorError`;
403 bei `ActorDeniedError`; 404 bei `MasterDataNotFoundError`; 409 bei `MasterDataConflictError`
(einschliesslich `StaleObjectError`); 503 mit `no-store` bei `MasterDataConfigurationError` und
bei `MasterDataUnavailableError`. `MasterDataConfigurationError` deckt insbesondere den
fehlenden oder nicht eindeutigen aktiven Standort aus
`resolve_single_active_location_connection()` ab: die Antwort ist 503/`no-store` ohne weiteren,
selbst wieder von der Datenbank abhängigen Versuch, die Fehlermeldung anzureichern — eine
Konfigurationsstörung wird nicht durch eine zusätzliche DB-abhängige Fehlerrekursion aufgelöst.
Die Zuordnung bleibt konsistent zur SQLSTATE-Tabelle aus §8.1 (`P1901`→400, `P1902`/`42501`→403,
`P1903`→401, `22023`→404, `55000`/`23505`→409); keine rohe SQL-Ausgabe erreicht den Aufrufer.
Der Ausfallwrapper liegt wie `auth.local_users._safe_account_read` **ausserhalb** von
Fähigkeitsprüfung und Reader. Kein automatischer Wiederholversuch mit frisch geladener Actor-
oder Objektversion.

---

## 5. REC-001 — Rezepte

### 5.1 Neue Tabellen

| Tabelle | Zweck | Wesentliche Felder |
|---|---|---|
| `recipes` | Rezeptkopf, veränderlich | `location_id`, `title`, `description`, `servings` nach §3.2, `servings_unit_id NOT NULL`, `prep_minutes NULL`, `cook_minutes NULL`, `source_kind`, `source_reference NULL`, `source_url NULL`, `source_note NULL`, `fetched_at NULL`, `active`, `row_version`, `created_by`, `updated_by` |
| `recipe_ingredients` | Zutatenzeilen | `location_id`, PK `(recipe_id, sort_order)`, `group_label NULL`, `ingredient_text NOT NULL`, `food_id NULL`, `quantity NULL` nach §3.2, `unit_id NULL`, `note NULL` |
| `recipe_steps` | geordnete Schritte | PK `(recipe_id, step_number)`, `instruction text NOT NULL`, `duration_minutes NULL`, `image_sha256 NULL` |
| `recipe_revisions` | festgeschriebene, unveränderliche Fassung | `recipe_id`, `revision_number`, `snapshot_json jsonb`, `content_hash_sha256`, `created_by`, `created_at`; unique `(recipe_id, revision_number)` |
| `recipe_assets` | inhaltsadressierte Bilddaten je Standort | PK `(location_id, sha256)`, `image_data bytea`, `content_type`, `width`, `height`, `created_by`, `created_at` |
| `recipe_images` | Bild ↔ Rezept mit Herkunft | PK `(recipe_id, sort_order)`, `sha256`, `caption NULL`, `source_url NULL`, `source_license NULL`, `fetched_at NULL` |
| `cookbooks` | Kochbücher und Sammlungen | `location_id`, `name`, `description NULL`, `active`, `row_version` |
| `cookbook_recipes` | Zuordnung | PK `(cookbook_id, sort_order)`, `recipe_id` |

`source_kind text NOT NULL CHECK (source_kind IN ('manual','url','file_import','ai_assisted'))`.
Bei `url` ist `source_url` verpflichtend, bei `file_import` und `ai_assisted` ist `source_note`
verpflichtend. Jede nichtmanuelle Herkunft braucht zusätzlich `source_reference` und
`fetched_at`; Dateiimporte verwenden Stapel-UUID plus Zeilennummer und den Dateihash als
Quellenbeleg. Ein Rezept verliert seine Herkunft nie durch spätere Bearbeitung; eine
Bearbeitung ändert diese Ursprungsfelder nicht. `recipe_ingredients` erhält ebenfalls
`source_kind`, `source_reference`, `fetched_at` für importierte Zutaten-/Mengenzeilen; manuell
erfasste Zeilen brauchen keinen Fremdbeleg. Mengenänderungen bleiben im Audit nachvollziehbar.

`recipe_ingredients`: `CHECK ((quantity IS NULL) = (unit_id IS NULL))`. `ingredient_text` ist
immer gefüllt, auch wenn `food_id` gesetzt ist — exakt das Muster von
`menu_item_components.component_text`. Ein Rezept bleibt lesbar und druckbar, auch wenn eine
Zutat später archiviert wird.

Titel sind **nicht** eindeutig. Zwei Häuser dürfen «Rindsgeschnetzeltes» unterschiedlich
kochen. Dublettenerkennung ist Sache des Imports (§9), keine Datenbankregel.

### 5.2 Bilder

`recipe_assets` übernimmt das Muster von `branding_assets`: Primärschlüssel ist der
SHA-256 der Bytes zusammen mit dem Standort, ein `CHECK` prüft die Magic Bytes und die Selbstkonsistenz des Hashes.
Unterschied: erlaubt sind PNG **und** JPEG (`content_type IN ('image/png','image/jpeg')`),
weil Rezeptfotos Fotos sind. Obergrenze 1 MiB je Bild, gleiche Grössenordnung wie
`branding_assets`. Identische Bilder werden innerhalb desselben Standorts dedupliziert.
`recipe_steps.image_sha256` und `recipe_images.sha256` referenzieren `(location_id, sha256)`;
Auslieferung verlangt die berechtigte Rezeptzuordnung, keine standortübergreifende Hashsuche.

Herkunft liegt auf der Verknüpfung, nicht auf den Bytes: Ein aus einer Webseite übernommenes
Bild trägt `source_url`, `source_license` und `fetched_at` verpflichtend
(`CHECK (source_url IS NULL OR (source_license IS NOT NULL AND fetched_at IS NOT NULL))`).
Ohne belegte Lizenz kein importiertes Bild.

### 5.3 Revisionen und Menübindung

`recipe_revisions` ist der Anker gegen nachträgliche Änderung veröffentlichter Inhalte und
kopiert das Muster von `publication_revisions`:

- `snapshot_json` enthält Kopf, Zutatenzeilen, Schritte, Bild-Hashes und Herkunft der Fassung.
  Mengen/Portionen werden als kanonische Decimal-Zeichenketten eingefroren. Jede verwendete
  Einheit enthält UUID, Code, damaligen Namen, Dimension und Basisfaktor (ggf. NULL); dazu
  kanonische Basiskennung, tatsächlich verwendete Dichte/Stückgewichte und deren Herkunft
  sowie den Rechenvertrag aus §3.3. Zutaten-ID/-Name/-Version und Zeilenherkunft werden
  mitgespeichert. Alte Revisionen rechnen/drucken allein aus diesen Daten, niemals mit
  später bearbeiteten Food-Faktoren oder umbenannten Einheiten.
- `content_hash_sha256` über den kanonisierten Snapshot.
- Ein Trigger nach dem Vorbild von `protect_publication_revision()`
  (`database/schema.sql:1066`). Genauer als das Vorbild: jenes verweigert `DELETE` unbedingt,
  bei `UPDATE` lässt es genau eine eng geprüfte Ausnahme zu — den kontrollierten Rückzug über
  `withdrawn_at`/`withdrawal_reason`/`withdrawn_by`, abgeglichen gegen einen passenden
  `publication_lifecycle_events`-Eintrag. Für `recipe_revisions` gibt es **keine** solche
  Ausnahme: `UPDATE` und `DELETE` werden beide vollständig verweigert. Eine Fassung wird nicht
  zurückgezogen, sondern durch eine neue Revision abgelöst.
- Eine Revision entsteht nur durch die ausdrückliche Aktion «Revision festschreiben», nie als
  Nebenwirkung eines Speicherns.

`menu_item_components.recipe_revision_id` bindet eine Menüposition an eine **Revision**, nie an
den veränderlichen Rezeptkopf. Ein späteres Bearbeiten des Rezepts kann eine bestehende
Menüwoche damit nicht rückwirkend verändern.

Die Rezeptrevision ist eine **zusätzliche** optionale Verwaltungsreferenz; sie darf neben
`component_id` bestehen. Kein gegenseitiger Ausschluss und kein stilles Ablösen einer
Katalogbindung. Die bestehende Paarbedingung `component_id`/`component_row_version` bleibt
unverändert. `effective_rows()` und `rematerialize_auto_effects()` arbeiten weiterhin aus
der Katalogbindung: Hinzufügen/Wechseln/Ablösen nur des Rezeptbezugs erhält deren bestätigte
Allergene, Herkunft und Labels in allen Auto-/Manual-Modi. Eine reine Rezept-/Freitextzeile
bleibt ohne erfundene Zutatenableitung unbekannt oder ausdrücklich manuell bestätigt.
Der vorhandene Trigger
`validate_menu_item_component_scope()` wird um eine Standortprüfung erweitert: die Revision muss
zu einem Rezept desselben `location_id` gehören wie die Menüwoche; sein UPDATE-OF-Ereignis
umfasst `recipe_revision_id`.

**Vollständiger interner Roundtrip.** Das Assignment-DTO enthält `component_public_id`,
`component_text` und nullable `recipe_revision_public_id`. Fremde Schlüssel bleiben verboten.
Alte Zwei-Feld-Eingaben sind nur für Positionen ohne gespeicherte Rezeptbindung kompatibel;
sonst wird ein verlustbehafteter Ersatz als Konflikt abgelehnt. Create/Replace/Append,
Umsortieren, Load/Form-Readback und Vorwochenkopie erhalten die konkrete Revision; Ablösen
braucht eine ausdrückliche Aktion. Der bestehende Menü-CSV-Vollimport schützt Rezeptbindungen
ebenso wie Katalogbindungen vor Vollersatz. R6 ist dafür nicht zuständig.

**Prüfbeleg.** Jede tatsächliche Bindungsänderung läuft nach Actor-Guard (§8) unter dem
bestehenden Week→Service→Item-/Link-Lockvertrag mit ursprünglicher Item-CAS-Erwartung.
Sie erhöht die Item-Version genau einmal, setzt den Menüprüfstatus zurück und schreibt Audit
atomar. Der interne kanonische Menü-Review-Payload und seine Anzeige enthalten die aufgelöste
Revisions-UUID und den unveränderlichen Hash; alte ungebundene Menüs behalten ihren bisherigen
Payload. Textgleicher Revisionswechsel macht alte Tokens ungültig, auch Wechsel zurück
belebt sie nicht. Copy übernimmt keine Freigabe. Parallel laufender Review/Bindungswechsel
wird serialisiert; unabhängige Nachbarmenüs und der Kopf-/Service-Wochenkontext bleiben gültig.

### 5.4 Die öffentliche Snapshotform bleibt unverändert

**Entscheidung: Die Rezeptbindung fügt dem Publikations-Snapshot keinen einzigen Schlüssel hinzu.**

`validate_publication_revision()` prüft Struktur und Kennwerte des Snapshots — Profil,
Kalenderwoche, genau sieben Tage, Revisionskennung, Preisstruktur — und wird in dieser Welle
bereits von OPS-001 für Schema 20 geändert. Zusätzlich begrenzt
`patient_key_is_forbidden()` zusammen mit `jsonb_has_patient_forbidden_key()` über eine
Erlaubnisliste, welche Schlüssel im Patienten-Snapshot überhaupt vorkommen dürfen; auch diese
Liste erweitert OPS-001 gerade. Die veröffentlichte Nutzlast enthält schon heute den gedruckten
Komponententext; ein Rezeptbezug ist Verwaltungsherkunft, keine Gastinformation. Folgen:

- `publication_revisions`, `patient_key_is_forbidden()` und alle öffentlichen Ausgaben bleiben
  byteidentisch zum heutigen Stand.
- Bestehende, veröffentlichte Wochen bleiben unveränderlich und preisfrei.
- Es entsteht kein Konflikt mit dem OPS-Eigentum an `validate_publication_revision()`.

Diese Grenze betrifft die öffentliche Projektion, nicht den internen Review-Context aus
§5.3. Dessen DTO-/Hash-/Editor-/Write-Anpassung ist ausdrücklich Teil von R5.

Der Nachweis ist konkret: `patient_key_is_forbidden()` erlaubt im Patienten-Snapshot genau 35
normalisierte Schlüsselnamen (`database/schema.sql:788`) und verwirft zusätzlich jeden Schlüssel, der auf ein Preis- oder Kostenwort
passt. Ein Schlüssel wie `recipeid` oder `recipe_revision` würde heute abgelehnt. Eine
Snapshot-Erweiterung wäre damit zwingend eine Änderung an einer Funktion, die in dieser Welle
OPS-001 gehört.

Ein späteres Paket, das Rezeptangaben tatsächlich in eine Ausgabe drucken will, ist ein eigener
Snapshot-Schemaschritt mit eigener Abnahme und **nicht** Teil von REC-001.

---

## 6. Bestätigte Daten, Vorschläge und Küchenfreigabe

Der bestehende Metadatenmechanismus bleibt gültig; die interne Bindungsprüfung wird nach §5.3 erweitert:
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
3. **Vorschläge leben getrennt** in `food_data_proposals`: `location_id`, `row_version`, `food_id NULL`, `source` (`off`,
   `supplier`, `ai`, `file_import`), `source_reference`, `fetched_at`, `payload jsonb`,
   `status IN ('open','accepted','rejected')`, `decided_by`, `decided_at`, `decision_detail jsonb`.
   Die Übernahme
   einzelner Felder ist eine bewusste Handlung, die einen `audit_events`-Eintrag erzeugt.
   Bestätigte Daten werden dabei nie automatisch überschrieben; ein Konflikt wird angezeigt.
   Quellenpayload bleibt unverändert, eine Entscheidung ist nur einmal von `open` möglich.
   Übernahme prüft erwartete Vorschlags- und Food-Version, Standort und Actor-Version atomar.
   Ziel, Erlaubnisliste, Zusammenführung und Buchung stehen abschliessend in §6.1.
4. **Fehlende Angabe bleibt fehlend.** Weder eine leere Allergenliste noch ein fehlender
   Nährwert ist eine Frei-von-Aussage. Die Anzeigen «Enthält», «Kann enthalten» und
   «Nicht erfasst» bleiben getrennt, wie in ICO-002 abgenommen.
5. Patientenausgaben bleiben preisfrei. Kosten aus CALC-001 hängen an Rezept und Zutat, nie am
   Patienten-Snapshot.

### 6.1 Vorschlagsübernahme: Ziel, Erlaubnisliste und Zusammenführung

**Ziel.** Ein Vorschlag darf mit `food_id NULL` entstehen und so gespeichert bleiben; Quelle,
Abrufzeit und Payload sind ab Anlage unveränderlich. Eine Annahme braucht immer ein bereits
bestehendes Ziel: entweder eine ausdrücklich ausgewählte Zutat oder eine zuvor über den
gewöhnlichen kontrollierten Weg (`create_food`, §4.5) angelegte Zutat. **Die Annahme erzeugt
niemals selbst eine Zutat.** Sie setzt `food_id` von NULL auf das gewählte Ziel und führt
Vorschlags-UUID mit ursprünglicher Vorschlagsversion, Ziel-UUID mit ursprünglicher
`foods.row_version` und die ursprüngliche Actor-Version mit. Jede Abweichung ist ein sichtbarer
Konflikt ohne Teilschreibung. Ein Vorschlag mit gesetztem `food_id` kann nur auf genau dieses
Ziel angenommen werden.

**Erlaubnisliste.** Übernehmbar sind in Stufe 1 genau fünf Felder, jedes einzeln und
ausdrücklich benannt. Ein leerer Feldsatz ist ein Validierungsfehler; wer nichts übernehmen
will, lehnt den Vorschlag ab.

| Feld | Typ und Grenze | Zusammenführung mit bestätigtem Wert |
|---|---|---|
| `density_g_per_ml` | Faktor nach §3.2 | NULL → übernehmen; gleich → `unchanged`; abweichend → Konflikt |
| `piece_weight_g` | Faktor nach §3.2 | wie oben |
| `category_code` | Code nach §4.3, muss auf eine aktive Kategorie desselben Standorts auflösen | wie oben |
| `allergens` | höchstens 64 Paare `{code, presence}` mit `presence IN ('contains','may_contain')`, Codes auf aktive `allergens` | fehlendes Paar → übernehmen; identisches Paar → `unchanged`; gleicher Code mit anderer Präsenz → Konflikt |
| `labels` | höchstens 64 Codes auf aktive `dietary_labels` | fehlend → übernehmen; vorhanden → `unchanged`; Entfernen ist nie eine Übernahme |

Name, Basiseinheit, Notiz, Tags, Lagerorte und Herkunftsfelder sind **nicht** übernehmbar. Ein
falscher Name oder eine falsche Basiseinheit wird über die gewöhnliche Zutatenbearbeitung
korrigiert, nie über eine Vorschlagsannahme. Weitere Felder — etwa Nährwerte aus NUT-001 oder
Zuordnungen aus OFF-001 — erweitern diese Liste ausdrücklich in ihrem eigenen Paket mit eigener
Abnahme; dieser Vertrag schneidet sie nicht ab, er verbietet nur die beliebige Feldübernahme.

**Nicht unterstützte Payloadschlüssel** bleiben unverändert in `payload` als begrenzte
Originalquelle erhalten. Sie gelten nie als übernommen und werden in der Entscheidung
ausdrücklich als `not_supported` geführt, damit ein späteres Paket sie nicht für bestätigte
Daten hält. Ein Schlüssel ausserhalb der Erlaubnisliste löst nie eine Übernahme aus.

**Konflikt.** Ein einziger Feldkonflikt bricht die ganze Annahme ab: kein Schreibvorgang, keine
Versionserhöhung, kein Audit, der Vorschlag bleibt `open`. Der Mensch korrigiert dann entweder
die Zutat über die gewöhnliche Bearbeitung — danach ist das Feld `unchanged` und die Annahme
möglich — oder lehnt den Vorschlag ab. Bestätigte Werte werden nie still überschrieben.
«Enthält», «Kann enthalten» und «nicht erfasst» bleiben in Payload, Übernahme und Anzeige
getrennt; eine leere Liste bleibt eine fehlende Angabe und wird nie zur Frei-von-Aussage.

**Entscheidung.** `decision_detail jsonb NOT NULL DEFAULT '{}'::jsonb` hält die Feldnamenlisten
`adopted`, `unchanged` und `not_supported` sowie Ziel-UUID und alte/neue `foods.row_version`.
Ein Trigger nach dem Vorbild von `protect_publication_revision()` verweigert jedes `DELETE`
sowie jede Änderung an einer Zeile, deren `status` nicht mehr `open` ist, und jede nachträgliche
Änderung von `location_id`, `source*`, `fetched_at` und `payload`. Für `food_id` gilt genau eine
Ausnahme, sonst gilt dasselbe Verbot: die eine atomare, kontrollierte Annahme (`open →
accepted`) darf `food_id` von NULL auf das gewählte Ziel setzen, geführt mit ursprünglicher
Actor-, Vorschlags- und Food-Version sowie Standortgleichheit (siehe **Ziel** oben). Ausserhalb
dieser einen Annahme bleibt `food_id` unveränderlich; ein bereits gesetztes Ziel wird nie
gewechselt, auch nicht durch eine zweite Annahme. Eine Ablehnung (`open → rejected`) lässt
`food_id` exakt so, wie es war: ein zuvor NULL gebliebener Vorschlag bleibt ohne Ziel, ein
Vorschlag mit gesetztem Ziel behält genau dieses Ziel. Eine Ablehnung setzt, wechselt und löscht
also nie ein Ziel. Der Übergang `open → accepted|rejected` ist
einmalig und unumkehrbar; jede abgeschlossene Entscheidung (`accepted` oder `rejected`) ist
danach vollständig unveränderlich, einschliesslich `food_id`. Dienst (`accept_proposal`/
`reject_proposal`, §4.5), Trigger und Testspezifikation setzen genau diese eine Ausnahme
identisch um.

**Buchung.** Eine Annahme mit mindestens einem übernommenen Feld erhöht `foods.row_version`
genau einmal; wurde dabei `food_allergens` geändert, setzt sie `allergen_review_status` auf
`not_checked` zurück. Sie erhöht `food_data_proposals.row_version` genau einmal und schreibt
**genau einen** `audit_events`-Eintrag mit `entity_type` `food_proposal`, der Ziel-UUID und
beide Food-Versionen in `details` führt; ein zweites Ereignis am Food-Aggregat entsteht nicht.
Sind alle benannten Felder `unchanged`, bleibt das Food-Aggregat unberührt, die Entscheidung
wird trotzdem einmalig festgeschrieben und einmal auditiert. Eine Ablehnung berührt kein Food.

---

## 7. Revision, Konflikt, Löschung und Verlauf

**Optimistische Sperre.** `foods`, `food_categories`, `tags`, `storage_locations`, `recipes`,
`cookbooks`, `measurement_units`, `food_data_proposals` tragen `row_version` und den vorhandenen Trigger
`bump_row_version_and_updated_at()`. Jedes Formular führt die gelesene Version mit; eine
Abweichung bricht mit derselben Konfliktklasse ab, die der Komponentenkatalog schon nutzt
(`ComponentConflictError`-Muster, für Rezepte `RecipeConflictError`).

**Eine Sperre je Aggregat.** Änderungen an `recipe_ingredients`, `recipe_steps` und
`recipe_images` und `recipe_tags` erhöhen `recipes.row_version`; Food-Zuordnungen einschliesslich
Lagerort erhöhen `foods.row_version`, Kochbuchzuordnungen `cookbooks.row_version`.
Es gibt keine Version je Zeile. Zwei Personen,
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
`storage_location`, `cookbook`, `food_proposal`, `measurement_unit`, `food_category`,
`recipe_import_batch`), `entity_public_id`, `actor_user_id` und erwartete Actor-Version.
Begrenzte strukturierte `details` halten Standort, Aktion, alte/neue Aggregatversion,
geänderte Feldnamen, Mengen-/Einheitswerte und Quellenreferenzen fest, keine Rohdateien,
Credentials oder unbeschränkten Importpayloads. Write, Versionsbump und Audit committen
gemeinsam oder gar nicht. Revisions-/Vorschlags-/Importaktionen haben genau einen Ereignistyp
je fachlicher Aktion; Unterzeilenänderungen erzeugen keine irreführenden Doppelereignisse. `audit_events`
ist bereits durch `trg_audit_events_immutable` und `trg_audit_events_no_truncate` geschützt.

**Wirkungslose Speicherung, Zustandswechsel und Unterzeilen.** Nach §4.3 erzeugt eine Eingabe,
die nach Normalisierung exakt den gespeicherten Zustand ergibt, weder Versionserhöhung noch
Zeitstempeländerung noch Audit-Eintrag; ein angeforderter Zustandswechsel, der nichts wechselt,
ist dagegen ein sichtbarer Konflikt. Eine Fachaktion, die Unterzeilen ändert — Tags, Labels,
Allergene, Lagerortzuordnungen; später Zutatenzeilen, Schritte, Bilder, Kochbuchzuordnungen —
erhöht genau eine Aggregatversion um eins und schreibt genau einen Audit-Eintrag, unabhängig
von der Zahl der geänderten Unterzeilen. In M-A berührt nur die Vorschlagsannahme zwei
Aggregate; auch sie bleibt bei genau einem Ereignis (§6.1).

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

**Vollständiger B2-Besitz.** B2 besitzt alle zehn M-A-Tabellen (`measurement_units`,
`food_categories`, `foods`, `tags`, `food_tags`, `food_labels`, `food_allergens`,
`storage_locations`, `food_storage_locations`, `food_data_proposals`) samt sämtlichen
Mutatoren, Rechten, Seeds, Validatoren und Registrierungen sowie die drei neuen Fähigkeiten in
`cafeteria/roles.py` und deren Matrixtest. B3 und B4 sind Verbraucher; es gibt keine zweite
DML- oder Migrationslane und keinen Teilbesitz an M-A. Der Modulzuschnitt, die eingefrorenen
DTOs und die genauen öffentlichen Signaturen stehen abschliessend in §4.5; vorhandene
Utilities werden bevorzugt, insbesondere `auth.local_users.ActorExpectation` und
`component_catalog_store.resolve_single_active_location_connection`. Rezept-DTOs gehören R1,
nicht B2.

**Datenbankrollen.** `cafeteria_app` erhält `SELECT` und ausschliesslich die ausdrücklich
aufgelisteten fachlichen Mutatorfunktionen, keine direkten `INSERT`-/`UPDATE`-/`DELETE`-/
`TRUNCATE`-Rechte auf den neuen Tabellen. Ausserbetriebnahme läuft über `active`.
`cafeteria_backup` erhält `SELECT`
auf Tabellen und Sequenzen, nach dem Muster der Zeilen für `cafeteria.api_keys`.
`cafeteria_auth_issuer` erhält nichts.

**Jeder neue Fachwrite** — auch Anlage, gewöhnliche Änderung, Zuordnung, Archivierung,
Reaktivierung, Revision, Vorschlag und Import — läuft über eng erlaubte `SECURITY DEFINER`-
Funktionen mit festem `search_path`, PUBLIC-Entzug und ohne dynamisches SQL. Eingaben führen
`actor_id`, `expected_actor_authz_version`, erwartete Ziel-`row_version` und Standort mit.
Die notwendige Fähigkeit ist je Operation fest kodiert, kein frei wählbarer Client-Parameter.
Die ursprüngliche Actor-Erwartung aus Sitzung/Command bleibt bis zur Mutation unverändert;
ein Konflikt wird nicht durch Nachladen und Wiederholen umgangen. Actor-Name allein reicht nie.

Der Fachguard prüft innerhalb derselben Transaktion aktiven Benutzer, aktive Rollen, Fähigkeit
und Version und hält Sperren bis Write/Audit. Er nimmt sie in der festen gemeinsamen Reihenfolge
aus §8.1: Rollendefinitionen geordnet `FOR SHARE`, die Actor-Zeile `FOR SHARE`, danach Standort,
globale Einheiten, Vokabular, Food, Vorschlag und später Rezepte. Transaktionsisolation
`READ COMMITTED` und die ursprünglichen Versionen bleiben Pflicht.
Kein nachträglicher Erwerb des IAM-Bootstrap-Advisory-Locks. Er schreibt weder Credentials
noch Rollen. Die adminexklusive `lock_local_user_v19()` ist kein wiederverwendbarer Editor-Guard.
`roles.require_capability()` bleibt die vorgelagerte Sessionprüfung, ersetzt diesen
transaktionalen Guard aber nicht. Gatefälle: Rollenentzug, Passwortreset, Stale-Actor und
unverändertes Zielobjekt bei gleichzeitigem Write; alle brechen ohne Fachwrite/Audit-Teilstand
ab, falls der Entzug zuerst serialisiert wurde. Fehlende Sitzung 401, fehlende Fähigkeit 403,
Objektkonflikt 409, DB-Ausfall kontrolliert 503/no-store, bestehende CSRF-Grenze unverändert.

### 8.1 Gemeinsame Sperrreihenfolge

Jeder Fachmutator aus M-A und M-B nimmt seine Sperren in genau dieser Reihenfolge, innerhalb
jeder Klasse aufsteigend nach `id` beziehungsweise nach dem genannten Sortierschlüssel.
Übersprungen wird nur, was eine Aktion nicht berührt; die relative Reihenfolge bleibt gleich.

| Rang | Objekt | Modus | Bemerkung |
|---|---|---|---|
| 1 | Isolation und Wartegrenze | — | `READ COMMITTED` ist Pflicht, sonst `P1901`; `set_config('lock_timeout','5s',true)` wie `begin_local_admin_v19()` |
| 2 | `application_roles` | `ORDER BY role_code FOR SHARE` | wortgleich zu `begin_local_admin_v19()`, aber **ohne** dessen Advisory-Lock |
| 3 | `users`, nur die Actor-Zeile | `FOR SHARE` | danach `disabled_at`, aktive Rolle, fest kodierte Fähigkeit und ursprüngliche `authz_version` prüfen |
| 4 | `locations` | `SHARE` über `lock_expected_active_location()` | die Funktion nimmt `LOCK TABLE cafeteria.locations IN SHARE MODE` (`database/schema.sql:2015`), keine Zeilensperre; gilt auch für die global gespeicherten Einheiten |
| 5 | globale Einheiten und Vokabular | `FOR SHARE` | `measurement_units`, `food_categories`, `tags`, `storage_locations`, `allergens`, `dietary_labels`; nach der Sperre `active` erneut prüfen |
| 6 | geschriebenes Aggregat, genau eines je Aktion | `FOR UPDATE` | Klassenfolge `measurement_units` → `food_categories` → `tags` → `storage_locations` → `foods` → `food_data_proposals` → (M-B) `recipes` → `cookbooks` |

Rang 5 und 6 fallen zusammen, wenn eine Vokabularzeile selbst das geschriebene Aggregat ist;
dann gilt allein Rang 6. Unterzeilen (`food_tags`, `food_labels`, `food_allergens`,
`food_storage_locations`; später `recipe_ingredients`, `recipe_steps`, `recipe_images`,
`recipe_tags`, `cookbook_recipes`) sind durch die Sperre ihres Aggregats gedeckt und werden
aufsteigend geschrieben. Berührt eine Aktion zwei Aggregate — in M-A ausschliesslich die
Vorschlagsannahme —, gilt die Klassenfolge aus Rang 6: erst das Food, dann der Vorschlag. R1 und
später R5 übernehmen diese Reihenfolge unverändert; sie sperren Einheiten, Vokabular und
Zutaten vor ihrem eigenen Aggregat und nie `FOR UPDATE`.

**Actor-Sperre `FOR SHARE` statt `FOR UPDATE`, mit Begründung.** Die Formulierung «betroffene
Benutzer nach ID `FOR UPDATE`» stammt aus dem adminexklusiven IAM-Pfad. **Klarstellung:** Heute,
vor M-C, existiert `menu_components.food_id` nirgends im Schema. `record_menu_review()`
(`database/schema.sql:2321–2378`) sperrt nach `lock_expected_active_location()` Woche und
Service `FOR UPDATE`, liest den Menüposten `FOR UPDATE`, liest Komponenten nur über `SELECT` und
schreibt einen Audit-Eintrag; `require_workflow_review_actor()`
(`database/schema.sql:2296`, `users … FOR SHARE`) läuft danach. Ein lesender `SELECT` durchläuft
keine FK-Prüfung; ohne Food-Fremdschlüssel gibt es dort weder eine implizite `FOR KEY SHARE`-
Sperre noch sonst eine belegte Sperre auf einer Food-Zeile. Ein heute bestehender, bewiesener
Sperrzyklus ist das **nicht** — die vorherige Darstellung als bereits eingetretener Deadlock war
falsch und ist hiermit korrigiert.

Auch das blosse Hinzufügen der Spalte `menu_components.food_id` als Fremdschlüssel ändert daran
nichts: ein lesender `SELECT` prüft auch nach M-C keinen Fremdschlüssel und nimmt deshalb keine
Sperre auf einer Food-Zeile. Eine implizite `FOR KEY SHARE`-Sperre kann allein ein
Schreibvorgang erzeugen, der eine Food-Referenz tatsächlich einfügt oder ändert, und auch dann
nur, wenn dieser Schreibvorgang in derselben Transaktion **vor** der Actor-Prüfung liegt. Ob ein
solcher Pfad in M-C/R5 wirklich entsteht, hängt am dann geschriebenen Code und ist heute weder
belegt noch getestet.

Das ist damit ein **konkret zu prüfendes künftiges Schreibpfad-Risiko**, kein bewiesener Zyklus
und keine automatische Sperre. Root entscheidet deshalb vorsorglich `FOR SHARE`: verträglich mit
dem bestehenden `FOR SHARE`-Actor-Read-Lock des Workflow-Guards und konfliktbehaftet mit dem
tatsächlichen `users.authz_version`-UPDATE (siehe unten) — die Sicherungswirkung bleibt erhalten,
ohne ein solches Risiko überhaupt erst zu eröffnen. Eine schwächere `FOR KEY SHARE`-Actorsperre
ersetzt `FOR SHARE` dabei nicht. Verbindlich bleibt: R5 und jeder weitere Pfad, der eine
Food-Referenz schreibt, prüft vor seiner Abnahme am realen Code, ob er eine Food-Zeile vor der
Actor-Prüfung sperrt, hält die Rangfolge dieses Abschnitts ein (Rang 3 vor Rang 6) und belegt das
Verhalten mit echten Nebenläufigkeitstests statt mit einer Herleitung.

Die Sicherungswirkung bleibt vollständig: jede Rollenvergabe, jeder Rollenentzug und jeder
Passwortreset erhöht `users.authz_version` — über `bump_user_authz_version()`
(`database/schema.sql:518`) beziehungsweise die IAM-Funktionen —, und dieses `UPDATE` kollidiert
mit `FOR SHARE`. Wer zuerst serialisiert, gewinnt: entweder wartet der Entzug auf den Fachwrite,
oder der Fachwrite liest anschliessend die neue Version und bricht als Stale-Actor ohne Write
und ohne Audit ab. Das Deaktivieren einer Rollendefinition, das keine Actor-Version erhöht,
deckt Rang 2 ab. `user_role_cache` wird nicht zusätzlich gesperrt, weil jede Änderung dort
dieselbe Actor-Zeile anfasst. Ein Nachladen der Actor-Version zur Umgehung bleibt verboten.

**Globale Einheiten.** `measurement_units` bleibt ohne `location_id` global; Lesen und Auflösen
sind standortfrei, auch für R1 innerhalb seiner Transaktion. Der Admin-Dienst, der Einheiten
pflegt, verlangt trotzdem ausdrücklich genau einen aktiven Standort (Rang 4) — dieselbe
Konfigurationsgrenze wie für alle übrigen Stammdatenmutatoren, damit ein mehrdeutiger
Standortzustand nicht unbemerkt bleibt. Das ist eine Dienstgrenze, keine Datenbindung.

**Guard-Freigabe.** Der interne Guard `require_master_data_actor(bigint, bigint, text)` nimmt
die Fähigkeit als Parameter, wird aber weder `cafeteria_app` noch `PUBLIC` noch
`cafeteria_auth_issuer` freigegeben. Nur die öffentlichen Mutatoren rufen ihn mit einem
literalen Fähigkeitsnamen; ein Client wählt nie eine Fähigkeit. Die Zuordnung Fähigkeit ↔ Rollen
steht in SQL und in `cafeteria/roles.py` und wird durch einen ausdrücklichen Matrixtest
gegeneinander geprüft. Da `permissions.sql` am Ende pauschal alle Funktionsrechte entzieht und
explizit wieder aufbaut, trägt B2 seine endgültigen öffentlichen Signaturen dort nach; Grants
allein innerhalb der Migration verschwinden beim erneuten Anwenden.

**Fehlercodes.** Die Fachfunktionen verwenden ausschliesslich diese SQLSTATEs, der Dienst bildet
sie fest ab: `P1901` ungültige Eingabe oder falsche Isolation → Validierung; `P1902` fehlende
aktive Rolle oder Fähigkeit → 403; `P1903` veraltete Actor-Version → 401; `22023` unbekanntes
oder untypisiertes Ziel → 404; `55000` veralteter oder blockierter Fachzustand, einschliesslich
Lagerortarchivierung mit bestehenden Zuordnungen → 409; `23505` Namens- oder Codekollision →
409; `42501` fehlendes Datenbankrecht → 403. Kein weiterer Code wird erfunden, keine rohe
SQL-Ausnahme erreicht den Aufrufer.

---

## 9. Importe: Grenze und Prüfung

**Eigene Stapeltabellen**, formgleich zu `import_batches`/`import_rows`, aber ohne `profile_id`:

```
recipe_import_batches(id, public_id, location_id, row_version, source_kind, source_filename, source_sha256,
                      status IN ('validated','rejected','imported'),
                      row_count, error_count, fetched_at, created_by, created_at)
recipe_import_rows(location_id, import_batch_id, row_number, row_payload jsonb,
                   validation_errors jsonb DEFAULT '[]', target_kind NULL,
                   target_public_id uuid NULL, expected_target_row_version NULL,
                   PRIMARY KEY (import_batch_id, row_number))
```

`target_kind` ist ausschliesslich `food` oder `recipe`; Kind/UUID sind gemeinsam NULL oder
gesetzt. Für ein bestehendes Übernahmeziel bleibt seine ursprüngliche Version gespeichert,
bei Neuanlage ist sie NULL. Ein DB-Scope-Trigger löst jede gesetzte Ziel-UUID typgebunden
auf und erzwingt denselben Standort wie Zeile/Stapel. Dienst und Formular prüfen das ebenso;
ein untypisierter UUID-Verweis ersetzt keinen Standortnachweis.

Verbindliche Regeln:

1. **Ein Importlauf schreibt nie direkt in `foods` oder `recipes`.** Er erzeugt einen Stapel.
   Die Übernahme ist eine getrennte, bestätigte Aktion mit `recipe.import` und läuft
   transaktional: entweder alle freigegebenen Zeilen oder keine. Übernahme prüft ursprüngliche
   Actor-/Stapel-/Zielversionen und Standort; ein übernommener Stapel ist nicht erneut übernehmbar.
2. **Herkunft ist Pflicht.** Jede übernommene Zeile schreibt `source_kind`, Quelle und
   Abrufzeit in die vorhandenen Zielfelder `source_kind`, `source_reference`, `source_note`
   beziehungsweise `source_url` und `fetched_at` auf `foods`/`recipes` (§4/§5), bei Mengen auch
   auf Zutatenzeilen. Referenz ist Stapel-UUID plus Zeilennummer; Notiz enthält den Dateihash.
   Stapel, Payload, Quellenbeleg und endgültige Zuordnung sind nach Übernahme unveränderlich.
3. **Grenzen in Stufe 1:** Datei ≤ 5 MiB, ≤ 2000 Zeilen, Inhaltstypen `text/csv`,
   `application/json`. Bilder gehören zur separaten Uploadgrenze §5.2, nicht zum CSV-/JSON-
   Stapel. Keine Makroformate. Kein Ausführen
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

**Belegte lokale Probe.** [HugeRTE 1.0.13](https://github.com/hugerte/hugerte/releases/tag/v1.0.13)
wurde am 6. September in echtem Chrome unter Dishboards strikter HTTP-CSP mit lokalen Assets
geprüft: Text, Fett, Listen und der Silver-Linkdialog funktionieren. Dennoch bleibt eine
`style-src-attr`-Verletzung durch einen internen Style-Marker, auch mit externen Tabler-Buttons
und ohne Silver-Theme. Richtext ist damit grundsätzlich möglich; das Null-CSP-Fehler-Gate
ist nicht bestanden. Silver liefert eigene Werkzeugleisten/Dialoge, in der Desktopprobe
unter 48px Touch-Grösse, keine vollständige Tabler-Bedienung. Ein Skin genügt dafür nicht.
[Prüfbericht mit Quellen und Grenzen](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md),
[roher Browserbeleg](/tmp/dishboard-hugerte-wp-28dc5618ccd1/proof.json),
[Silver-Dialog](/tmp/dishboard-hugerte-wp-28dc5618ccd1/strict-dialog.png),
[externe Tabler-Buttons](/tmp/dishboard-hugerte-wp-28dc5618ccd1/external.png).

Primärreferenzen: [offizielle Theme-/Dokumentationshinweise](https://github.com/hugerte/hugerte-docs/blob/main/README.md)
und [getaggte DOMUtils-Implementierung](https://raw.githubusercontent.com/hugerte/hugerte/v1.0.13/modules/hugerte/src/core/main/ts/api/dom/DOMUtils.ts).
Die Probe umfasst ausgewählte Funktionen bei 1440×900, keine vollständige mobile, Screenreader-,
Langdokument-, Upload- oder Serverfilter-Abnahme. Eine globale Lockerung auf `unsafe-inline`
bleibt ausgeschlossen; ein CSP-kompatibler, vollständiger Tabler-Prototyp braucht eigene Abnahme.

**Auslieferung.** Ein Offline-Pin wäre machbar: `static/vendor/` enthält bereits Tabler,
Tabler-Icons, Swagger UI und Food-Symbole mit `*.lock.json` und Paketprüfungen
(`test_tabler_package_verification.py`, `test_swagger_ui_assets.py`). Die Verfügbarkeit ist
also nicht das Hindernis.

**Entscheidung für REC-001.** Rezeptschritte werden als **Klartext** gespeichert
(`recipe_steps.instruction text`) und escaped gerendert. Das erfüllt die REC-001-Vorgabe
«geordnete Schritte» vollständig, ohne gespeichertes HTML, ohne Sanitizer-Pflicht und ohne
CSP-Änderung. Das ist die gewählte erste Liefergrenze, keine Behauptung, Richtext sei technisch
unmöglich. Ein Rich-Text-Editor ist ein **eigenes späteres Arbeitspaket (R-RTE)** und
**keine Voraussetzung** für eine nutzbare Rezeptverwaltung.

Eintrittsbedingungen für R-RTE, alle vor einer Technologiefreigabe zu erfüllen:

1. Nachgewiesener Betrieb ohne `unsafe-inline`, belegt durch einen Browserlauf mit leerer
   CSP-Verletzungsliste — oder ein begründeter, sicherheitsgeprüfter Header-Vorschlag.
2. Serverseitige Erlaubnisliste für gespeichertes HTML mit Tests gegen Skript-, Stil- und
   Ereignisattribute.
3. Tastatur- und Screenreader-Nachweis auf der tatsächlichen Oberfläche.
4. Vollständige Tabler-Formularintegration einschliesslich Fehlerfokus, nicht nur eine Hülle.
5. Offline-Pin mit Lizenznachweis und Paketprüfung.

Es ist keine Produktabhängigkeit installiert und keine Technologie freigegeben. Die lokale
Eignungsprobe ist durchgeführt; vollständige CSP-/Tabler-Integration und Produktabnahme bleiben offen.

---

## 11. Migrationen

Dieser Vertrag reserviert keine Nummer. Beschrieben wird die Reihenfolge oberhalb des
abgenommenen Schema-20-Vertrags von OPS-001; Root serialisiert und vergibt Nummern.

| Schritt | Inhalt | Voraussetzung |
|---|---|---|
| M-A (B2 allein) | `measurement_units`, `food_categories`, `foods`, `tags`, `food_tags`, `food_labels`, `food_allergens`, `storage_locations`, `food_storage_locations`, `food_data_proposals`, Mengen-/Quellen-/Scope-Constraints, Seed-Einheiten, Rechte, Trigger | geprüftes Schema 20; B1 reine Funktionen |
| M-B (R1 allein) | `recipes`, `recipe_ingredients`, `recipe_steps`, `recipe_revisions`, `recipe_assets`, `recipe_images`, `cookbooks`, `cookbook_recipes`, `recipe_tags`, Unveränderlichkeits-/Scope-Trigger | M-A |
| M-C | `menu_components.food_id`, `menu_item_components.recipe_revision_id`, `dish_templates.recipe_id`, Erweiterung `validate_menu_item_component_scope()` | M-B |
| M-D | `recipe_import_batches`, `recipe_import_rows` | M-B |

Jeder Schritt hebt `db.SCHEMA_VERSION`, `APPLICATION_VERSION`, `database/validate_schema.py`
und `tools/validate_package.py` nach dem in `0016_v18_to_v19.sql` und dem OPS-Vertrag gezeigten
Muster, einschliesslich Schema-/Seed-/permissions-Dateien, vollständiger Migrationslisten und
aller Schema-/Paket-/historischen Fixture-Verträge. Root serialisiert B2→R1→R5(M-C)→R6(M-D)
für sämtliche gemeinsam betroffenen Dateien; genau ein Autor besitzt jede Releaseeinheit.
B1/B3/B4/R2/R3/R4/R7 ändern keine Migration, keinen Schema-Pin und keine bereits registrierte
Migration nachträglich. M-C lässt vorhandene Daten gültig, erweitert aber zusätzlich zu den
nullable FKs die benötigten Scope-/Bindungs-/Review-Verträge. Nach Nutzereingaben gibt es
keinen Rückbau durch Tabellendrop oder Datenrestore auf einen älteren Zustand: Fehler werden
mit einem zum aktuellen Schema kompatiblen Forward-Fix behoben, Daten und IAM-Stand bleiben erhalten.

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
