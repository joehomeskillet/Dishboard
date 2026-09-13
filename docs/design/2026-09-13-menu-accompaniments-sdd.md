# Menübeilage «Suppe oder Salat» — Feature-SDD

Stand: 13. September 2026. Planungs-WP `wp-f9d0d3e72dfe`, Planer Claude Fable 5.1
(`claude-fable-5-1`), Worktree `menu-accompaniment-sdd-fable-0913`, Branch
`docs/menu-accompaniment-sdd-fable-0913`, Basis `dd1491ee82d61579863f317fc7b64017777ae88d`
(Produktion Schema 30). Geprüfter Nachfolgestand: Menüvorschlag-Branch
`fix/proposal-mobile-fix-0913` @ `66be61edcdd3b6bef07c1047b53e5cb22b186d9a` mit additiver
Schema-31-Migration `database/migrations/0028_v30_to_v31.sql`. Dieser Plan zielt auf die
Integration **nach** dem Schema-31-Release; er blockiert kein laufendes Release.

Dieses Dokument ist Spezifikation und WP-Zuordnung, keine Implementierung, keine
Browserprüfung und keine Abnahme. Verbindlich bleiben
[Ausführungsvertrag](../superpowers/backlog-0909/execution-contract.md),
[UI-Manifest](2026-09-09-unified-ui-design-system.md),
[Feature-SDD Gerichtvorlagen/Rezepte/Planung](2026-09-13-gerichtvorlagen-rezepte-planung-sdd.md),
[Korrekturvertrag Patientenplan/Menüeditor](2026-09-12-patientenplan-menueditor-korrektur.md)
und `docs/superpowers/plans/2026-09-12-next-sprints.md`. Arbeitspakete:
`docs/superpowers/menu-accompaniments-0913/work-packages.json`, Start:
`docs/superpowers/menu-accompaniments-0913/START.md`.

Root-Abschluss nach tatsächlichem Fable-Sitzungslimit am 13.09.: Planung bleibt Fables
Teilbeitrag; Umsetzung gemäss letzter Nutzerkorrektur ausschliesslich mit
`gpt-5.3-codex-spark`, ohne stillen Modellwechsel. Root reserviert Schema32 für diese
Funktion nach Schema31; PLAN-PORTIONS wartet. CSV-Roundtrip (F5) ist entschieden und
gehört zum vollständigen Feature. Kein sichtbarer Beilagen-Release, bevor alle
Snapshot-Reader, Ausgaben und CSV-Anschlüsse die neue Wahl erhalten können.

## 1. Originalauftrag, unverändert

> weitere anforderung: pro menü entweder eine suppe oder ein salat (gemisch&grün, hat immer beides) kann dazu genommen werden. dies muss auch in der menü struktur, gericht usw. schlau integriert werden. (claude fable 5.1 subagent)

## 2. Entscheidung in Kürze

Jedes gespeicherte Menü (Slot Woche · Tag · Mahlzeit · Menüart) erhält genau **eine**
Beilagenwahl aus drei Werten: **keine**, **Suppe** oder **Salat**. «Salat» ist ein einziges
Angebot «gemischter und grüner Salat, immer beides»; es gibt keine getrennte Wahl
«gemischt oder grün». Nie Suppe und Salat gleichzeitig. Die Beilagenwahl ist etwas anderes
als die bestehenden Bausteine (Kartoffelstock, Gemüse …) und als ein Hauptgericht, das
selbst eine Suppe oder ein Salat ist. Die Gerichtvorlage trägt einen sichtbaren Vorschlag
(«Dazu: Suppe»), den der Menüvorschlag ins Formular vorbefüllt; gespeichert wird nur, was
im Formular steht.

Technisch: eine additive Textspalte `menu_items.accompaniment` (`'none'|'soup'|'salad'`,
Standard `'none'`), eine additive Spalte `dish_templates.accompaniment_default`
(gleiche Werte), zwei neue Vorlagen-Verben v32 neben den eingefrorenen v26-Verben, ein
optionales Formularfeld, ein optionales Snapshot-Paar `accompaniment_code`/
`accompaniment_name`, das nur bei einer gewählten Beilage ausgegeben wird. Bestehende
Menüs, gespeicherte Publikationsrevisionen, Hashes, Review-Tokens und Preise bleiben
bytegleich. Keine neue Dependency, kein Framework, keine Allergen-, Preis- oder
Nährwertaussage zur Beilage.

## 3. Ist-Stand mit Quellenankern

Alle Produktpfade unter `reference_scaffold/cafeteria/`, Tests unter
`reference_scaffold/tests/`, SQL unter `database/`. Anker gelten für die Basis `dd1491e`;
Abweichungen des Vorschlag-Branches sind markiert.

| Bereich | Belegter Ist-Stand | Anker |
|---|---|---|
| Menüposition | `menu_items` je `(service_id, menu_type_id)` mit `title`, `description`, `note`, `dish_template_id` (nullable), Modi, `allergen_review_status`, `row_version`. Keine Spalte für eine Beilagenwahl. | `database/schema.sql:190` |
| Bausteine | `menu_item_components` (Position, Text, optional Katalogbaustein + Version, seit v26 `recipe_revision_id`). Katalogkategorien fest: `meat, side, vegetable, sauce, dessert, other`; **kein** Typ Suppe/Salat. | `schema.sql:173`, `:222`; `workflow_partial_form.py:_COMPONENT_CATEGORIES` |
| Gerichtvorlage | `dish_templates` mit `menu_type_id`, `profile_scope`, `title`, `description`, `active`, `updated_at` (CAS), seit v26 `recipe_id`. Verben `create/update/set_dish_template_active_v26` rufen `dish_template_mutate_v26`; `master_payload` lehnt **jeden unbekannten Payload-Schlüssel** ab (P1901). | `schema.sql:161`, `:3386`, `:5107–5208`; `dish_template_store.py:SQL,_payload,LIST` |
| Vorlagenpflege | `/admin/gerichtvorlagen` Liste/Formular (`draft.read/write`), Payload exakt `menu_type_code, profile_scope, title, description, recipe_public_id`. Importwerkzeug `tools/import_dish_templates.py` ruft `create_template` mit demselben Payload. | `admin/dish_template_routes.py`; `dish_template_store.py:_payload`; `tools/import_dish_templates.py:121–164` |
| Menüformular | `parse_menu_item_form`: exakte Feldmengen `_MENU_REQUIRED`/`_MENU_OPTIONAL`/`_MENU_REPEATED`; unbekannte Felder → 400. Routen halten `_MENU_VALUE_FIELDS` für die Fehler-Neuanzeige. | `workflow_partial_form.py:33–37`, `:420–470`; `admin/workflow_routes.py:86–95` |
| Menüwriter (Slot) | `persist_menu_item`: `_validate_item` prüft exakte Payload-Schlüssel (`_PATIENT_KEYS`/`_STAFF_KEYS` + optionale Vorlagenfelder), `_ITEM_QUERY[_FOR_UPDATE]` liest `current`, INSERT/UPDATE nennen Spalten explizit, genau ein Versionsschritt (`record_item_write`). | `workflow_partial_store.py:31–41`, `:111–135`, `:420–545` |
| Menüwriter (Gesamtentwurf) | `persist_draft_connection` → `write_draft_item` (CSV-Vollersatz, Gesamtimport); INSERT/UPDATE nennen Spalten explizit. | `workflow_store.py:304–420`; `workflow_item_write.py:27–75` |
| Entwurf lesen | `load_draft_connection` liefert je Option `type_code, external_id, title, description, components, assignments, Modi, labels, allergens, origins, note, dish_template{...}, allergen_review_status` (+ Preise). | `workflow_store.py:140–255` |
| Entwurfsvalidierung | `_validate_values`: exakte erlaubte Optionsschlüssel; `_public_option` projiziert feste Schlüssel; `validate_publication_fit` prüft Titel 36 / Bausteine 48 Zeichen (Player). | `workflow.py:78–200`, `:305–335`, `:395–420` |
| Vorwochenkopie | `_lock_items` liest und INSERT kopiert explizit `dish_template_id, title, description, note, …`; nicht genannte Spalten fallen auf Defaults. | `workflow_copy_store.py:170–185`, `:265–300` |
| Review-Token | `_TOKEN_KEYS` exakt: `item_row_version, Modi, components, labels, allergens, origins`; `dish_template_id` ist bewusst **nicht** enthalten (Root-Präzisierung 13.09.). | `workflow_review.py:26–37`; Feature-SDD §4 |
| Publikationssnapshot | `build_snapshot._option` baut feste Schlüssel (`type_code`, `type_name`, `components` …); Patientenvalidator kennt exakte Objektschlüssel plus optionale (`area_name`, Servicezeiten) und lehnt jeden weiteren Schlüssel ab; kompakte Schlüsselmenge wird daraus abgeleitet. Gespeicherte Revisionen werden beim Lesen (`active_snapshot`, `_read_last_good`) erneut validiert. | `workflow_snapshot.py:60–110`; `patient_payload.py:7–33`, `:262–345`, `:348–405`; `db.py:442`, `:488` |
| Status «live/changed» | `derive_admin_status` vergleicht `build_snapshot(draft)` bytegenau mit `snapshot_json` der aktiven Revision. | `workflow.py:511–560` |
| Öffentliche Ausgabe | Signage (4), Public (6) und Admin-Vorschau/Menüsammlung binden **ein** gemeinsames Partial `_menu_metadata.html` mit `option`-Kontext ein; Titel und Bausteine stehen direkt in den Templates. | `templates/_menu_metadata.html`; 12 Einbindungen (`grep -rl`) |
| Wochen-PDF | Native Absätze aus `option` (`_paragraphs`, `binding_text`), keine Jinja-Templates. | `admin/week_pdf.py:112–130`; `admin/week_pdf_layout.py:52–75` |
| API v1 / OpenAPI | `weeks` liefert `snapshot_json`, `weeks_preview` baut `build_snapshot(draft)`; `Option`-Schema mit `required`-Liste und Enums aus `PATIENT_FIXED_VALUES`. | `api/v1_routes.py:212`; `api/openapi.py:6`, `:404–430` |
| FHIR R5 | `nutrition_product`: Kategorie aus `type_code/type_name`, Bausteine als `ingredient[].item.concept.text`, `description`/`note` als `note[]`. | `fhir/mapping.py:20–60` |
| MCP | Reicht Snapshot-JSON durch; kein Feldwissen über Optionen (kein `components`-Treffer in `dishboard_mcp/`). | `test_mcp_server.py` |
| CSV | Export/Import mit festen Headern (Schema 2), Validator verlangt **exakt** die Headerliste; Import ist Vollersatz (`import_draft` → `_full_replace_values`). | `csvio.py:17–24`, `:100–140`; `csv/validate_menu_csv.py:15–22`, `:134`, `:177`; `workflow.py:335–395` |
| Menüsammlung | `find_menus` liest Titel/Beschreibung/Hinweis/Bausteine/Labels/Allergene/Herkunft je Seite; Template bindet `_menu_metadata.html` ein. | `admin/menu_collection_store.py`; `templates/admin/menu_collection.html` |
| Schemaversion-Pins | `db.py:SCHEMA_VERSION=30` (+`MIGRATION_FILES`), `validate_schema.py:202/703`, `tools/validate_package.py:329`; der v31-Branch bumpt zusätzlich 15 Test-Pins. | `db.py:22`; `validate_schema.py`; v31-Diffstat |
| Icons | Lokaler Sprite hält 33 Tabler-Icons aus Pin `@tabler/icons 3.46.0`; **weder `soup` noch `salad`** enthalten. Generator `tools/vendor_tabler.py` datengetrieben über `tabler.lock.json`; Vendor-Wiring ausschliesslich Root. | `static/vendor/tabler.lock.json`; Icon-Manifest §P0 |
| Vorschlag (v31-Branch) | `_proposal_values` baut die Vorbefüllung aus der gesperrten Vorlagenzeile (`lock_templates`), `TemplateContext` bindet Vorlage, `updated_at`, Rezept und Ziel; Menü-GET/POST prüfen Original-Kontext. | Diff `66be61e`: `admin/workflow_routes.py:+326–367`, `menu_template_binding.py:lock_templates` |
| Reuse-Scan | Kein bestehendes Konzept «Suppe/Salat/Beilage-Wahl» in Code, Schema, CSV oder Backlog; Treffer nur als Freitext in Demodaten/Beispiel-CSV (`beilagen` = Bausteine). | `grep -rli` über `cafeteria/`, `database/`, `csv/`, `docs/BACKLOG.md` |

## 4. Begriffe und kanonischer Datenvertrag

| Begriff (UI) | Datensatz / Feld | Werte | Veränderlich |
|---|---|---|---|
| Beilagenwahl des Menüs | `menu_items.accompaniment` | `none` · `soup` · `salad` | ja, mit dem Menü (`row_version`) |
| Beilagen-Vorschlag der Vorlage | `dish_templates.accompaniment_default` | `none` · `soup` · `salad` | ja, mit der Vorlage (`updated_at`-CAS) |
| Beilage in der Publikation | Option `accompaniment_code` + `accompaniment_name` | `soup`/`Suppe` · `salad`/`Salat (gemischt und grün)` | nein, Revision unveränderlich |

Feste Anzeigetexte (eine Quelle je Schicht, wie `TYPE_NAMES`/`OPTION_LABELS` heute):

| Code | Formular (Radio) | Karte/Editor-Kurztext | Öffentlich (Snapshot `accompaniment_name`, Public, Signage, Druck) |
|---|---|---|---|
| `none` | «Keine» | — (Zeile entfällt) | — (Schlüssel entfällt) |
| `soup` | «Suppe» | «Dazu: Suppe» | Snapshot: «Suppe»; Ausgabe: «Dazu: Suppe» |
| `salad` | «Salat (gemischt und grün)» | «Dazu: Salat (gemischt und grün)» | Snapshot: «Salat (gemischt und grün)»; Ausgabe: «Dazu: Salat (gemischt und grün)» |

`accompaniment_name` enthält niemals den Präfix «Dazu:». Jeder Ausgabeverbraucher
ergänzt ihn genau einmal. Die Namen oben sind Roots verbindliche Entscheidung F3.

Der öffentliche Name ist ab der ersten Publikation Vertragsinhalt einer gespeicherten
Revision (bytegleich, Hash). Eine spätere Umbenennung ändert nur neue Revisionen; alte
Revisionen bleiben, wie sie sind. Deshalb wird die Formulierung vor der ersten Publikation
bestätigt (§11, F3).

### 4.1 Schema (neue Migration, additiv, nach Schema 31)

Root reserviert `database/migrations/0029_v31_to_v32.sql` für ACC-SCHEMA nach
dem Schema31-Release. PLAN-PORTIONS erhält eine spätere eigene Reservierung. Weder
`0028_v30_to_v31.sql` noch eine ältere Migration wird verändert.

```sql
BEGIN;
ALTER TABLE cafeteria.menu_items
    ADD COLUMN accompaniment text NOT NULL DEFAULT 'none'
    CONSTRAINT menu_items_accompaniment_check CHECK (accompaniment IN ('none','soup','salad'));
ALTER TABLE cafeteria.dish_templates
    ADD COLUMN accompaniment_default text NOT NULL DEFAULT 'none'
    CONSTRAINT dish_templates_accompaniment_default_check
    CHECK (accompaniment_default IN ('none','soup','salad'));
-- dish_template_mutate_v32: Kopie von v26 mit optionalem Payload-Schlüssel
-- accompaniment_default (fehlend: create → 'none', update → unverändert),
-- gleiche Sperrfolge, gleiche CAS-/Audit-Semantik, Audit-Details + accompaniment_default.
-- create_dish_template_v32 / update_dish_template_v32 (gleiche 6 Parameter wie v26).
-- v26-Verben bleiben unverändert und weiterhin ausführbar (Rollback-Pfad).
-- REVOKE ALL … FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;
-- GRANT EXECUTE … TO cafeteria_app;  (Muster 0027/0028)
COMMIT;
```

Kein Backfill nötig: Defaults füllen beide Spalten deterministisch; bestehende Zeilen
bedeuten «keine Beilage», genau der heutige fachliche Zustand. Keine Datenumschreibung,
keine Trigger-Änderung, keine Index-Änderung. `schema.sql`, `permissions.sql`,
`validate_schema.py` (Version 32, neue Constraint-Fragmente), `db.py`
(`SCHEMA_VERSION=32`, `MIGRATION_FILES` + Eintrag), `tools/validate_package.py`
(Version 32), `database/README.md` (Listeneintrag 25 + Absatz «Schema v32») und die
Versionspin-Hunks derselben 15 Tests wie im v31-Diff gehören zum Schema-WP.

### 4.2 Draft-Lesemodell, Schreibmodell, Formular

| Schicht | Schlüssel | Regel |
|---|---|---|
| Entwurf lesen (`load_draft_connection`) | `accompaniment_code` (immer, Standard `'none'`), `accompaniment_name` (Kurztext oder `''`) | Lesemodell wie `dish_template{…}`; Name aus einer Konstante. |
| Entwurf schreiben (`_validate_values`, `persist_draft_connection`, `write_draft_item`) | `accompaniment_code` optional | Fehlt → `'none'` (Vollersatz-Semantik wie beim Vorlagenbezug). Ungültiger Wert → `WorkflowValidationError`. `accompaniment_name` ist im Schreibmodell **unzulässig**. |
| Slot schreiben (`parse_menu_item_form` → `persist_menu_item`) | Formularfeld `accompaniment` (Einzelwert) → Payload `accompaniment_code` optional | Fehlt → bestehender Wert bleibt (Create → `'none'`); vorhanden → genau ein Wert aus den drei Codes, sonst 400 am Feld. |
| Vorlage (`dish_template_store`, v32-Verb) | Payload `accompaniment_default` optional | Fehlt → Create `'none'`, Update unverändert; Importwerkzeug bleibt unverändert lauffähig. |
| Vorschlag (`_proposal_values`) | `option['accompaniment_code'] = source['accompaniment_default']` | `lock_templates` liest die Spalte mit; `require_template_source` deckt Änderungen über `updated_at` bereits ab. |
| Publikation (`build_snapshot._option`) | `accompaniment_code`, `accompaniment_name` **nur wenn Code ≠ `none`** | Omit-when-none hält alte Wochen bytegleich (`derive_admin_status` bleibt «live»). |
| Patienten-/Cafeteria-Validator | beide Schlüssel optional, immer paarweise, feste Werte | `PATIENT_OPTIONAL_KEYS['option']` + `PATIENT_FIXED_VALUES`; die kompakte Schlüsselmenge folgt automatisch. Alte Revisionen ohne Schlüssel bleiben gültig (wie Schema 1 → 2 in v20). |

### 4.3 Was sich ausdrücklich nicht ändert

- `menu_item_components`, Katalogkategorien, Allergen-/Label-/Herkunftsableitung.
- Review-Token (`_TOKEN_KEYS`), `record_item_write`, Slot-CAS, Wochen-CAS, Audit-Verben.
- `external_id`, `sort_order`, Preise, Patienten-Preisfreiheit, Playergrenzen 36/48.
- Hash und Bytes gespeicherter Publikationsrevisionen; `schema_version: 2` des Snapshots
  bleibt (optionaler Zusatzschlüssel, wie `area_name` in v20).

## 5. Invarianten und Validierungspfade

| Nr. | Invariante | Durchgesetzt in |
|---|---|---|
| I1 | Genau ein Wert je Menü aus `{none, soup, salad}`; nie zwei Beilagen. | CHECK-Constraint; Parser (Einzelwert); `_validate_values`; `_validate_item`. |
| I2 | «Salat» ist ein Angebot (gemischt und grün); keine Unterwahl. | Kein weiterer Wert/Feld; Text in einer Konstante. |
| I3 | Beilage ist kein Baustein und kein Rezept: keine Zeile in `menu_item_components`, keine Rezeptbindung, keine Mengen. | Kein Writer legt eine Komponente an; Bausteintests unverändert. |
| I4 | Alte Menüs bleiben `none`; keine stille Änderung. | Spalten-Default; Partial-Writer «fehlend = unverändert»; keine Datenmigration. |
| I5 | Gespeicherte Revisionen, Hashes, Review-Belege bleiben bytegleich. | Omit-when-none; `_TOKEN_KEYS` unverändert; Snapshot-Kontrakttests. |
| I6 | Vorlage schlägt nur vor; gespeichert wird der Formularwert. | Vorbefüllung nur im Menü-GET; Save liest ausschliesslich das Formular. |
| I7 | Kein Preis-, Allergen-, Nährwert- oder Kalorienwert für die Beilage. | Kein Feld, kein Text mit Zahlen; Patientenfilter bleibt strikt (feste Werte). |
| I8 | Öffentliche Projektion enthält keine internen IDs für die Beilage. | Nur Code + Name; `_forbidden_external_identifier_key_paths` unverändert. |
| I9 | AuthZ/Standort/CSRF/CAS/Signaturen unverändert: Beilage reist als normales Formularfeld im bestehenden POST. | Kein neuer Endpoint; Original-Erwartungen und `template_context` bleiben. |
| I10 | Rollback-Fenster: v32-Schema mit v31-App läuft (Spalten haben Defaults, alte Writer nennen sie nicht); eine **mit Beilage publizierte** Revision ist für den v31-Validator ungültig. | Release-Ablauf §7; Abnahme A16. |

Validierungspfade (jeder mit eigenem Test):

1. Formular ohne Feld → alter Wert bleibt (bestehende Browsertests posten weiter ohne Feld).
2. Formular `accompaniment=salad` → 303, Rücklesen zeigt Salat, `row_version +1`, ein Beleg.
3. Formular `accompaniment=both`/leer-String → 400 am Feld, Werte erhalten, Detail offen.
4. Vollimport/CSV ohne Angabe → `none` (dokumentiert, getestet).
5. Vorwochenkopie kopiert den Wert.
6. Publikation ohne Beilage → Snapshot ohne die zwei Schlüssel, bytegleich zu vorher.
7. Publikation mit Beilage → Schlüsselpaar vorhanden, Validator beider Profile akzeptiert;
   Paar unvollständig oder fremder Wert → Validator lehnt ab.
8. Alte Revision (ohne Schlüssel) wird von `active_snapshot`/`_read_last_good` weiterhin
   angenommen.
9. Vorlagen-Update mit `accompaniment_default` → CAS/Audit wie heute; unveränderter Payload
   → kein Versionsschritt (v26-Regel «IS NOT DISTINCT FROM» bleibt).
10. Vorschlag aus Vorlage «Dazu: Suppe» → Radio «Suppe» vorbelegt; Benutzer wählt «Keine»
    → gespeichert `none`.

## 6. Benutzerabläufe und UI-Skizzen (UI-Manifest R03/R04/R05/R07, M10–M12)

ASCII-Kürzel wie im Manifest; Icons sind Tabler-Sprite-IDs. Neue Pins: `soup`, `salad`
(beide aus `@tabler/icons 3.46.0`, Verifikation im gepinnten Archiv durch den
Vendor-Writer; fehlt eines, gilt Text ohne Icon, keine erfundene Sprite-ID). «Keine»
braucht kein Icon.

### 6.1 Menüeditor (M12) — Feldgruppe direkt unter dem Menünamen

```text
+-------------------------------------------------------------------+
| MENUE BEARBEITEN / Dienstag 8. September                          |
| Patienten / Mittag / Menue 1                                      |
+-------------------------------------------------------------------+
| Menuename [Hackbraten an Rosmarinjus                           ]  |
| Suppe oder Salat dazu                                             |
|   (o) Keine    ( ) [soup] Suppe    ( ) [salad] Salat (gemischt und gruen)   |
|   Nur eine Wahl. Bausteine und Rezepte bleiben unveraendert.      |
+-------------------------------------------------------------------+
| BAUSTEINE                           [+] Baustein hinzufuegen      |
| ...                                                               |
+-------------------------------------------------------------------+
| Nicht gespeichert                  [S] Menue speichern            |
+-------------------------------------------------------------------+
```

- Native Radiogruppe (`fieldset`/`legend`, Name `accompaniment`, IDs
  `accompaniment-none|soup|salad`), mindestens 48 px Touch-Ziel, mobil untereinander; NoJS-fähig;
  keine `admin.js`-Änderung, keine neue CSS-Datei (bestehende `form-check`-Klassen).
- Fehlerlink der Zusammenfassung zeigt auf `accompaniment-none`.
- Beim Vorschlag aus Vorlage: vorbelegt nach `accompaniment_default`; Hinweiszeile
  «Aus Vorlage vorgeschlagen» nur, wenn `cell.template_proposal`.
- Prüfkontext rechts (gespeicherter Stand) zeigt eine Zeile «Dazu: Suppe» / «Keine
  Beilage», ohne Bestätigungssemantik (Review-Token unverändert).

### 6.2 Wochenplan-Karte (M10/M11) und Menüsammlung (M07)

```text
| MENUE 1                       |
| Hackbraten an Rosmarinjus     |
| Kartoffelgratin, Broccoli     |
| [soup] Dazu: Suppe            |
| [!] Allergene fehlen          |
| Mitarbeitende: CHF 11 ...     |
```

Zeile nur bei gewählter Beilage (Aussage vor Farbe, kein Badge). Menüsammlung: gleiche
Zeile im Kurztext, nach den Bausteinen.

### 6.3 Gerichtvorlage — Formular und Liste

```text
| Titel [Roesti                                   ]  Menueart [Menue 1 v]  Bereich [Gemeinsam v] |
| Suppe oder Salat dazu (Vorschlag fuer neue Menues)                                          |
|   (o) Keine   ( ) [soup] Suppe   ( ) [salad] Salat (gemischt und gruen)                       |
|   Wird beim Einplanen vorbelegt und kann im Menue geaendert werden.                          |
```

Liste: Spalte «Dazu» mit Icon + Kurztext («Suppe», «Salat», «—»). Keine Auswirkung auf
bereits gespeicherte Menüs (I6).

### 6.4 Öffentliche Ausgabe, Signage, Druck

Eine Zeile «Dazu: Suppe» bzw. «Dazu: Salat (gemischt und grün)» unter den Bausteinen,
vor Kennzeichnungen — zentral im Partial `_menu_metadata.html` (alle 12 Einbindungen:
Public heute/Woche/Druck, Signage Tag/Woche, Admin-Vorschau, Menüsammlung). Reine
Textzeile, keine Symbole (öffentliche Layouts haben eigene Symbolsprache). Wochen-PDF:
gleiche Zeile als eigener Absatz in `_paragraphs`/`binding_text`. Signage-Fit bei
1920 × 1080 und 3840 × 2160 prüfen; die Zeile ist fest ≤ 32 Zeichen und zählt nicht zur
48-Zeichen-Bausteingrenze.

## 7. Kompatibilität, Migration, Release

| Thema | Entscheid |
|---|---|
| Alte Menüs | `none` per Default; kein Backfill; UI zeigt nichts an. |
| Alte Revisionen | Ohne Schlüssel weiterhin gültig (optionales Paar); Bytes und Hash unverändert; `derive_admin_status` bleibt «live» für unveränderte Wochen. |
| Neue Revisionen ohne Beilage | Bytegleich zu heutigem `build_snapshot`-Ergebnis (Omit-when-none). |
| Vollimport/CSV | Root entscheidet F5: Schema3 mit `beilage_dazu` (leer/`suppe`/`salat`) und verlustfreiem Export/Import gehört zum sichtbaren Feature-Release. Schema2 bleibt ausdrücklich importierbar und setzt `none` nach klarer Vollersatz-Vorschau. Vor CSV-Anschluss keine Beilagen-Schreiboberfläche freigeben. |
| Kopie Vorwoche | Wert wird mitkopiert (Test). |
| App-Rollback nach Migration | v31-App auf v32-Schema läuft (Defaults). Wurde bereits eine Revision **mit** Beilage publiziert, muss vor einem App-Rollback diese Revision zurückgezogen oder der Rollback als Forward-Fix geführt werden (I10). Release-Beleg wie bei v20/v31: Backup, Migration, `validate_schema`, Restore-Probe, Live-HTTP. |
| Migrationsnummer | Root reserviert `0029_v31_to_v32.sql`; ACC-SCHEMA ist der nächste SQL-Writer nach Schema31. PLAN-PORTIONS wartet. |

## 8. Konsumentenmatrix

| Konsument | Quelle | Änderung | WP |
|---|---|---|---|
| Menüeditor, Fehler-Neuanzeige | Draft-Lesemodell, Formular | Radiogruppe, `menu_form_values`, `_MENU_VALUE_FIELDS`, `error_targets` | CORE, EDITOR-UI |
| Wochenkarte, Preview (Admin) | `_cells`, Draft | Zeile «Dazu: …»; Preview über Partial | EDITOR-UI, PUBLIC-OUTPUT |
| Menüsammlung | `find_menus` | SELECT + Name; Partial zeigt Zeile | COLLECTION |
| Public heute/Woche/Druck-HTML, Signage Tag/Woche | Snapshot | Partial-Zeile | PUBLIC-OUTPUT |
| Wochen-PDF | Draft oder Snapshot | Absatz «Dazu: …» | WEEK-PDF |
| API v1 `weeks`, `weeks_preview`, OpenAPI | Snapshot | Schema: zwei optionale Properties, Enums aus `PATIENT_FIXED_VALUES` | API-FHIR |
| FHIR `NutritionProduct` | Snapshot | `note[]` + `{"text": "Dazu: Suppe"}`; keine neue Struktur | API-FHIR |
| MCP | Snapshot | Durchreichung; nur Test, keine Änderung | API-FHIR (Gate) |
| CSV Export/Import | Snapshot / Werte | Welle 3 (F5) | CSV |
| Portionen/Einkauf/Kosten (`quantities.py`, `shopping_aggregate.py`, `cost_calc.py`) | Rezeptrevisionen/Bausteine | **keine** — Beilage hat weder Rezept noch Menge noch Preis | — |

## 9. Sicherheit

- Kein neuer Endpoint, keine neue Berechtigung: Menü `draft.read/draft.write`, Vorlage
  `draft.read/draft.write` wie heute. CSRF (scoped) und `template_context`-Signatur
  unverändert; das Feld wird vom bestehenden Parser exakt geprüft (400 bei fremdem Wert).
- Original-Actor/Authz/Standort/Slot-CAS: keine Änderung; der Writer prüft unter den
  bestehenden Sperren; ein reiner Beilagenwechsel erzeugt genau einen Versionsschritt und
  einen Beleg.
- Patientenkanal: feste Werte, keine Zahlen, keine Währungsstämme; die Namen «Suppe»
  und «Salat (gemischt und grün)» stehen als exakte Werte im Validator (kein Freitext).
- SQL: neue Verben `SECURITY DEFINER` mit `search_path=pg_catalog,cafeteria,pg_temp`,
  `REVOKE`/`GRANT` wie 0027/0028; kein App-DML auf `dish_templates`.
- Kein Secret, keine Fixture aus Produktionsdaten; Screenshots synthetisch.

## 10. Entscheidungen

| Nr. | Entscheidung | Begründung |
|---|---|---|
| D1 | Eigene Enum-Spalte statt Baustein/Katalogkategorie | Bausteine sind Freitext/Katalog mit Allergen-Ableitung, Reihenfolge und 48-Zeichen-Grenze; die Beilage ist eine Wahl ohne Mengen/Rezept. Ein Baustein «Suppe» wäre weder exklusiv noch als Salat-Bündel abbildbar. |
| D2 | Drei Werte `none/soup/salad`, Text-Spalte mit CHECK | Verständlich, additiv, ohne Enum-Typ; ein späterer vierter Wert (`soup_or_salad`, F1) ist eine kleine Constraint-Migration, kein Umbau. |
| D3 | Vorlage trägt `accompaniment_default` in derselben Migration | «Gericht usw.» im Auftrag; ein Schema-Release statt zwei; der Vorschlag ist Vorbefüllung, nie Live-Kopplung (I6). |
| D4 | Neue Verben v32 neben v26 | v26 ist eingefroren; `master_payload` lehnt neue Schlüssel ab; v26 bleibt für Rollback und das unveränderte Importwerkzeug ausführbar. |
| D5 | Snapshot: Paar `accompaniment_code/_name`, nur bei Wahl | Muster `type_code/type_name`; alte Bytes/Hashes und «live»-Status bleiben unverändert. |
| D6 | Review-Token unverändert | Wie beim Vorlagenbezug: Beilage trägt keine Allergen-/Herkunftsaussage; Versionsschritt erneuert den Token ohnehin. |
| D7 | Partial-Zeile statt 12 Template-Edits | Ein Owner, eine Regel, gleiche Darstellung in Public/Signage/Druck/Vorschau/Sammlung. |
| D8 | Kein Suppenname, kein Preis, keine Allergene an der Beilage | Nicht beauftragt; Hinweisfeld deckt den Suppennamen ab; Fachfragen F2/F4/F6 offen. |
| D9 | CSV-Schema3 samt Roundtrip vor sichtbarem Feature-Release | Root entscheidet F5; strikter Header-Vertrag und klarer Schema2-Vollersatz bleiben erhalten. |
| D10 | Icons `soup`/`salad` als Root-Vendor-Handoff, Fallback Text | Sprite-Wiring ist Root-Besitz; kein Aufruf erfundener Sprite-IDs. |
| D11 | Root reserviert Schema32 für ACC; kein READY ohne Dateilease | Ein SQL-Writer; PLAN-PORTIONS wartet auf eigene spätere Reservierung. |

## 11. Offene Fachfragen (konservativer Default, blockiert nicht)

| Nr. | Frage | Default in diesem Plan | Folge bei anderer Antwort |
|---|---|---|---|
| F1 | Wählt die **Küche** je Menü (Suppe *oder* Salat), oder wählt der **Gast** am Ausgabepunkt zwischen Suppe und Salat, sodass ein Menü beides anbietet? Der Wortlaut «kann dazu genommen werden» lässt beides zu; der Auftrag an den Planer fixiert die Küchenwahl. | Küchenwahl je Menü, drei Werte. | Vierter Wert `soup_or_salad` («Dazu: Suppe oder Salat») per kleiner CHECK-Migration; Radio erhält eine vierte Option; Snapshot-Name ergänzt. Kein Umbau. |
| F2 | Soll die Tagessuppe benannt werden («Kürbissuppe»)? | Nein; Hinweisfeld steht zur Verfügung. | Optionales Textfeld `accompaniment_text` (Patientenfilter!) als eigenes WP. |
| F3 | Öffentliche Formulierung «Salat (gemischt und grün)» — Alternativen «gemischter und grüner Salat», «Salat gemischt & grün». | «Salat (gemischt und grün)»; Formular gleichlautend. | Vor der ersten Publikation ändern; danach nur für neue Revisionen. |
| F4 | Gilt die Beilage in beiden Bereichen (Cafeteria und Patienten) und für Mittag **und** Abend? | Ja, überall; keine Profilregel. | Profil-/Mahlzeitregel im Parser und in `_validate_values`. |
| F5 | CSV-Roundtrip | Entschieden durch Root: neue Spalte mit Schema3, kompatibler Schema2-Import. | CSV-WP ist Pflicht vor sichtbarem Feature-Release. |
| F6 | Allergen-/Preisaussage zur Beilage (z. B. «im Preis inbegriffen», Suppenallergene)? | Keine Aussage; öffentliche Allergenzeile bezieht sich weiterhin nur auf das Menü. | Eigenes Fach-WP mit Datenvertrag; nicht aus diesem Plan ableiten. |

## 12. Arbeitspakete, Reihenfolge, Besitz

Alle Pakete `PLANNED`; Root vergibt Leases, Migrationsnummer, Pools und setzt `READY`.
Vollständige Verträge in `work-packages.json`. Neue Backlog-Anforderung: **REC-008
«Menübeilage Suppe oder Salat je Menü»** (Root ergänzt `docs/BACKLOG.md` und die
Slice-Liste in `validate-plan.py`; beide sind Root-Besitz).

| Welle | WP | Kern | Exklusiver Besitz (Auszug) | Abhängig von |
|---|---|---|---|---|
| 0 | `MP-REC-ACC-SCHEMA` | Migration v32, Verben v32, Pins, README | `database/*`, `db.py`, `tools/validate_package.py`, 15 Pin-Hunks, neuer Migrationstest | Schema-31-Freeze; Root-Reservierung |
| 0 | `MP-REC-ACC-ICONS` (Root) | Sprite + Lock um `soup`, `salad` | `static/vendor/tabler-icons/tabler-icons.svg`, `tabler.lock.json` | — |
| 1 | `MP-REC-ACC-MENU-CORE` | Parser, beide Writer, Reader, Kopie, Rendering-Werte, Vorschlag-Vorbefüllung | Workflow-Cluster (`workflow*.py`, `workflow_item_write.py`, `workflow_copy_store.py`, `admin/rendering.py`, `admin/workflow_routes.py`, `menu_template_binding.py`) + neue Tests | SCHEMA, MENU-TEMPLATE-BINDING, MENU-PROPOSAL; **seriell** mit PLAN-PORTIONS |
| 1 | `MP-REC-ACC-SNAPSHOT` | Snapshot-Paar, Validatoren beider Profile | `workflow_snapshot.py`, `patient_payload.py`, Snapshot-/Public-Kontrakttests | SCHEMA (Publikationstests); parallel zu CORE gegen Draft-Schlüssel-Freeze |
| 1 | `MP-REC-ACC-TEMPLATE` | Vorlagen-Store/Routen/Formular/Liste | `dish_template_store.py`, `admin/dish_template_routes.py`, `gerichtvorlagen.html`, Vorlagentests | SCHEMA, MENU-PROPOSAL; seriell mit RECIPEPAGES auf `gerichtvorlagen.html` |
| 2 | `MP-REC-ACC-EDITOR-UI` | Radiogruppe, Wochenkarte, Prüfkontextzeile | `menu_editor.html`, `_week_menu_card.html`, neuer Browsertest | CORE, ICONS; seriell mit PLAN-PORTIONS auf `menu_editor.html` |
| 2 | `MP-REC-ACC-PUBLIC-OUTPUT` | Partial-Zeile, Signage-/Public-Fit | `templates/_menu_metadata.html`, Signage-/Public-Tests | SNAPSHOT, CORE |
| 2 | `MP-REC-ACC-WEEK-PDF` | PDF-Absatz | `admin/week_pdf.py`, `admin/week_pdf_layout.py`, PDF-Tests | SNAPSHOT, CORE |
| 2 | `MP-REC-ACC-API-FHIR` | OpenAPI-Properties, FHIR-Note, MCP-Gate | `api/openapi.py`, `fhir/mapping.py`, API-/FHIR-/MCP-Tests | SNAPSHOT |
| 3 | `MP-REC-ACC-COLLECTION` | Sammlung liest Beilage | `admin/menu_collection_store.py`, Sammlungstest | CORE, DENSITY-LISTS |
| 3 | `MP-REC-ACC-CSV` | Spalte `beilage_dazu`, Schema 3 | `csvio.py`, `csv/validate_menu_csv.py`, CSV-Vorlagen/Beispiele, CSV-Tests | CORE, SNAPSHOT, Entscheid F5 |
| 3 | `MP-REC-ACC-ACCEPT` | Unabhängige Browser-/Ausgabe-Abnahme, Inventaranschluss (Root) | eigener Test + Evidenz | EDITOR-UI, PUBLIC-OUTPUT, WEEK-PDF, API-FHIR, TEMPLATE |

Empfohlene Reihenfolge: SCHEMA unmittelbar nach dem Schema-31-Release als nächster
SQL-Writer (zwei additive Spalten, zwei Verben; kleiner als PLAN-PORTIONS), ICONS
parallel durch Root; danach CORE ∥ SNAPSHOT ∥ TEMPLATE; danach EDITOR-UI ∥ PUBLIC-OUTPUT ∥
WEEK-PDF ∥ API-FHIR; zuletzt COLLECTION, CSV (nach F5) und ACCEPT. Zieht Root
PLAN-PORTIONS später nach, benötigt es eine neue eigene Nummer nach Schema32;
ACC-SCHEMA bleibt `0029_v31_to_v32.sql`.

### 12.1 Gemeinsame Dateien und Serialisierung (ein Writer je Datei)

| Datei | Aktive/geplante Writer | Regel |
|---|---|---|
| `database/schema.sql`, `permissions.sql`, `validate_schema.py`, `db.py`, `tools/validate_package.py`, Migrationsledger | PROPOSAL (v31, in Review) → **ACC-SCHEMA** ↔ PLAN-PORTIONS (Root-Reihenfolge) | Ein SQL-Writer; Nummer erst nach Freeze des Vorgängers. |
| `workflow_partial_form.py`, `workflow_partial_store.py`, `workflow_store.py`, `workflow_item_write.py`, `workflow.py`, `workflow_copy_store.py` | BINDINGS (Anker) · MENU-TEMPLATE-BINDING (IN_PROGRESS) · PLAN-PORTIONS · **ACC-CORE** | Seriell nach Root-Lease; ACC-CORE nie parallel zu PLAN-PORTIONS. |
| `admin/workflow_routes.py`, `admin/rendering.py` | MENU-TEMPLATE-BINDING → MENU-PROPOSAL → PLAN-PORTIONS ↔ **ACC-CORE** | Seriell. |
| `menu_template_binding.py` | MENU-TEMPLATE-BINDING → **ACC-CORE** (eine SELECT-Erweiterung) | Nach Merge des Binding-/Proposal-Standes. |
| `templates/admin/menu_editor.html` | MENUEDITOR (deployed) → BINDING → PROPOSAL → PLAN-PORTIONS ↔ **ACC-EDITOR-UI** | Seriell; keine `admin.js`-Änderung durch ACC. |
| `templates/admin/_week_menu_card.html` | WEEKS (deployed) → MENU-TEMPLATE-BINDING → **ACC-EDITOR-UI** | Lease. |
| `static/admin.js` | RECIPE → SHARED → PLAN-PORTIONS | **Nicht** von ACC berührt (Radiogruppe ist nativ). |
| `templates/admin/gerichtvorlagen.html`, `admin/dish_template_routes.py`, `tests/test_dish_template_*.py` | LINK-READS → VIEW-PRINT → MENU-PROPOSAL → **ACC-TEMPLATE** ↔ RECIPEPAGES | Root legt fest, ob ACC-TEMPLATE vor oder nach RECIPEPAGES läuft; nie gleichzeitig. |
| `dish_template_store.py` | DISH-TEMPLATE-WRITER (geliefert) → **ACC-TEMPLATE** | Lease. |
| `templates/_menu_metadata.html` | keine aktive Lease → **ACC-PUBLIC-OUTPUT** | Globale Wirkung: Regression aller 12 Einbindungen im WP-Gate. |
| `workflow_snapshot.py`, `patient_payload.py` | in PLAN-PORTIONS und BINDING **forbidden** → **ACC-SNAPSHOT** | Exklusiv; Kontrakttests im selben WP. |
| `admin/week_pdf*.py`, `api/openapi.py`, `fhir/mapping.py` | keine aktive Lease → ACC-WEEK-PDF / ACC-API-FHIR | Lease bei READY. |
| `templates/admin/menu_collection.html` | DENSITY-LISTS (aktiver Grant) | ACC-COLLECTION ändert **nur** den Store; Template zeigt die Zeile über das Partial. |
| `templates/admin/preview.html`, `admin-preview.css` | DENSITY-PREVIEW (geplant) | ACC ändert nichts daran; Zeile kommt über das Partial. |
| Sprite/Lock | RECIPE-Fix (abgeschlossen) → VIEW-PRINT-Grant → **ACC-ICONS (Root)** | Generator unverändert; Root-Vendor-Wiring. |
| `docs/superpowers/backlog-0909/*-wps.json`, `file-leases.json`, `ui-route-matrix.json`, `ui-before-manifest.json`, `docs/BACKLOG.md`, `validate-plan.py` | Root | Aufnahme von REC-008/ACC-Paketen und Inventarzeilen durch Root. |

## 13. Abnahmefälle

| ID | Fall | WP |
|---|---|---|
| A1 | Migration auf nichtleerem v31-Bestand: beide Spalten mit Default, Constraints aktiv, v26- und v32-Verben ausführbar, ACL wie 0027/0028; Restore-Probe; `validate_schema` 32 | SCHEMA |
| A2 | `update_dish_template_v32` mit `accompaniment_default='soup'` → CAS/Audit; ohne Schlüssel unverändert; fremder Wert → P1901; v26-Update ohne Schlüssel lässt den Wert stehen | SCHEMA, TEMPLATE |
| A3 | Formular ohne Feld → Wert unverändert; `soup`/`salad`/`none` → gespeichert, Rücklesen im Editor und auf der Karte; fremder Wert → 400 am Feld, Werte erhalten | CORE, EDITOR-UI |
| A4 | Reiner Beilagenwechsel: genau `row_version +1`, ein Beleg, Review-Payload ändert nur `item_row_version` | CORE |
| A5 | Vorwochenkopie kopiert die Beilage; Vollimport ohne Angabe → `none`, mit Hinweis in der Vorschau | CORE |
| A6 | Vorschlag aus Vorlage «Dazu: Salat» → Radio vorbelegt; Benutzer wählt «Keine» → `none` gespeichert; Vorlage inzwischen geändert → 409 wie heute | CORE, TEMPLATE |
| A7 | Publikation ohne Beilage bytegleich zu vorher (Hash gleich), Status «live» unverändert; mit Beilage: Schlüsselpaar in Snapshot, beide Validatoren grün, unpaariges/fremdes Paar rot | SNAPSHOT |
| A8 | Alte Revisionen (Fixture ohne Schlüssel) werden von `active_snapshot` und `_read_last_good` angenommen | SNAPSHOT |
| A9 | Public heute/Woche/Druck-HTML, Signage Tag/Woche zeigen «Dazu: …» nur bei Wahl; Signage-Fit 1920 × 1080 und 3840 × 2160 ohne Überlauf | PUBLIC-OUTPUT |
| A10 | Wochen-PDF (Cafeteria und Patienten) enthält den Absatz; ohne Wahl unverändert (Bytes/Layout-Tests) | WEEK-PDF |
| A11 | OpenAPI-Kontrakttest kennt die optionalen Properties; `weeks`/`weeks_preview` liefern sie nur bei Wahl; FHIR `note` enthält «Dazu: …»; MCP reicht durch | API-FHIR |
| A12 | Vorlagenliste/-formular: Radiogruppe, Spalte «Dazu», Leser ohne Schreibaktionen; Importwerkzeug läuft unverändert | TEMPLATE |
| A13 | Menüsammlung zeigt die Zeile für gespeicherte Menüs mit Wahl | COLLECTION |
| A14 | CSV Schema 3: Export/Import round-trip mit `beilage_dazu`; Schema-2-Dateien weiterhin importierbar (setzen `none`) | CSV |
| A15 | Editor 1440 × 900 und 390 × 844, NoJS, Tastatur, 200 %-Zoom, Fokus; Karte in beiden Rastern; Icons geladen oder Text-Fallback dokumentiert | EDITOR-UI, ACCEPT |
| A16 | Release: v31-App gegen v32-Schema lauffähig (Smoke); Rollback-Regel I10 dokumentiert und in der Release-Checkliste | SCHEMA, ACCEPT |

## 14. Gate-Matrix (gezielt, kein Gesamt-Suite-Zwang für Textarbeit)

| WP | Gezielte Tests (Wrapper/Pool von Root) | Zusätzlich |
|---|---|---|
| SCHEMA | `test_menu_accompaniment_migration_db.py` (neu), `test_database_invariants.py`, die 15 Pin-Tests des v31-Diffs | `rtk /tmp/dishboard-shared-venv/bin/python database/validate_schema.py` (Artefaktmodus), Restore-Probe durch Root |
| CORE | `test_menu_accompaniment_db.py` (neu), `test_menu_accompaniment_form.py` (neu), `test_workflow_form.py`, `test_workflow_partial_store_db.py`, `test_workflow_copy_store_db.py`, `test_admin_workflow_routes.py`, `test_admin_form_contracts.py`, `test_menu_template_binding_db.py`, `test_menu_proposal_routes.py` | Ruff/Mypy auf eigene Dateien |
| SNAPSHOT | `test_menu_accompaniment_snapshot.py` (neu), `test_admin_workflow_snapshot_contract.py`, `test_public_contracts.py`, `test_admin_workflow_db.py` | — |
| TEMPLATE | `test_dish_template_routes.py`, `test_dish_template_browser.py`, `test_dish_template_import_db.py`, `test_recipe_link_reads_db.py` | Browser 1440/390 |
| EDITOR-UI | `test_menu_accompaniment_browser.py` (neu), `test_ui_korrektur_editor_browser.py`, `test_ui_korrektur_week_browser.py`, `test_menu_conflict_nojs_browser.py` | Screenshots als Vorschlag, keine Baselines |
| PUBLIC-OUTPUT | `test_public_contracts.py`, `test_signage_cafeteria_day.py`, `test_signage_cafeteria_week.py`, `test_signage_patient.py`, `test_public_display_copy.py`, `test_admin_draft_preview.py`, `test_menu_collection.py` | Signage 1920/3840 |
| WEEK-PDF | `test_week_pdf.py`, `test_week_pdf_layout.py`, `test_admin_week_print.py` | PDF öffnen (nativer Paint getrennt) |
| API-FHIR | `test_openapi_contract.py`, `test_api_v1.py`, `test_api_keyed.py`, `test_fhir_mapping.py`, `test_fhir_routes.py`, `test_mcp_server.py` | — |
| COLLECTION | `test_menu_collection.py`, `test_menu_collection_browser.py` | — |
| CSV | `test_admin_csv_import.py`, `test_csv_validation_followup.py`, `test_csv_weekend_contract.py`, `test_csv_runtime_packaging.py` | Beispiel-CSV aktualisiert |
| ACCEPT | eigener Browser-Ablauftest Editor → Karte → Publikation → Public/Signage/Druck/API | Evidenzdatei, Inventarzeilen (Root) |
| Docs-only (dieses SDD, START, JSON) | Markdown-Lesbarkeit, JSON-Strukturprüfung mit den Funktionen aus `validate-plan.py`, Diffcheck | kein Pytest |
| Sprintende | Vereinigung der obigen Listen + `tools/validate_package.py` (Root-Release) | Live-Belege Revision/Image/Schema/HTTP |

## 15. Nicht-Ziele

- Keine Gästewahl-Semantik, kein Suppenname, keine Beilagen-Allergene, -Preise oder
  -Nährwerte (F1/F2/F6).
- Keine neue Menüart, kein neuer Bereich, keine Änderung an Bausteinen, Rezepten,
  Portionen (`MP-REC-PLAN-PORTIONS`), Einkauf oder Kalkulation.
- Kein Umbau der Playergrenzen, keine neue Signage-Vorlage, kein Drucklayout-Editorfeld.
- Keine Änderung an Review-Algorithmus, Publikationsablauf oder Capabilities.
- Keine Migration bestehender Daten, keine Umschreibung alter Revisionen, keine neue
  Dependency, kein Framework, kein `admin.js`-Edit.

## 16. Quellenstand und Werkzeugbefunde dieser Planung

- GitNexus-Index «menuplan» (`/nvmetank1/projects/menuplan`, 2026-09-13 02:38 UTC,
  Commit `486c793`) liegt **vor** der Basis `dd1491e`; 59 Produktdateien unterscheiden
  sich (u. a. `workflow_item_write.py`, `workflow_partial_store.py`, `workflow_store.py`,
  `menu_template_binding.py`, `admin/workflow_routes.py`). Impact-Befunde gelten
  deshalb nur für unveränderte Dateien: `build_snapshot` upstream **CRITICAL**
  (5 direkte Aufrufer: `weeks_preview`, `load_draft`, `validate_draft_values`,
  `derive_admin_status`, `publish_draft_scoped`; 7 Abläufe), `validate_snapshot_payload`
  upstream **CRITICAL** (3 direkte, 12 Abläufe inkl. Public/Signage/API/Screen-Vorschau).
  Der LOW-Befund zu `write_draft_item` stammt aus dem veralteten Stand und wurde per
  `grep` bestätigt (einziger Aufrufer `persist_draft_connection`); er wird **nicht** als
  Freigabe geführt. Die Writer-Kette gilt damit als HIGH.
- Kein Webabruf; alle Aussagen aus Quellstand `dd1491e`, dem geprüften Diff
  `dd1491e..66be61e` des Vorschlag-Branches und den genannten Manifesten.
- Icons: lokal ist kein `@tabler/icons`-Archiv entpackt; die Existenz von `soup` und
  `salad` in 3.46.0 ist vom Vendor-Writer im gepinnten Archiv (SHA im Lock) zu belegen.
