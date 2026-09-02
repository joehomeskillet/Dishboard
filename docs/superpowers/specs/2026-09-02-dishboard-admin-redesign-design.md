# SDD: Dishboard-Admin-Redesign

## 1. Ziel, Grenzen und unveränderliche Regeln

Der Admin erfasst Wochenmenüs für zwei strikt getrennte Profile: `patient` und
`staff_guest` (Cafeteria Personal/Gäste). Stack und UI bleiben Flask, Jinja,
PostgreSQL und Vanilla JS; keine neue Dependency. `dish_templates` bleibt
unverändert. Die bestehende Therapieplan-Oberfläche liefert `--sh-*`-Tokens
und Fira Sans; neue harte Hex-Farben oder ungemappte Arbitrary-Klassen sind
nicht zulässig.

Die tatsächlichen Grids sind Vertragsbestandteil:

| Profil | Raster | Einträge |
|---|---|---:|
| `patient` | 7 Tage × (Lunch + Dinner) × 2 Menüoptionen | 28 |
| `staff_guest` | 5 Tage × Lunch × 2 Menüoptionen | 10 |

Patienten haben keine Preise. Cafeteria hat weder Nächte noch Wochenenden.
Server und UI lehnen Zeilen außerhalb des Profilrasters ab; die Darstellung
zeigt immer genau dieses Raster.

## 2. Persistenz- und Versionsvertrag

Der vorhandene Full-Week-Replace bleibt ausschließlich als explizite
Full-Grid-Operation für Import/Recovery erhalten. Partial-Forms dürfen ihn
nie aufrufen. Neue Transaktionen sind atomar und optimistisch gesperrt:

- `persist_menu_item(week_id, profile, day, meal, option, payload, version)`
- `persist_week_header(week_id, profile, payload, version)`
- `persist_service_state(week_id, profile, payload, version)`

Jede Operation prüft route-abgeleitetes Profil, validierte ISO-Montag-Woche
(`?week=YYYY-MM-DD`), erwartete `row_version` und exact allowed keys. Ein
Konflikt liefert 409 ohne Mutation; ein Validierungsfehler 400 mit Feldpfad.
Partial-Saves ändern nur die adressierte Zeile bzw. den Header/Service-Status.
Transaktion: lock, nochmals lesen, validieren, schreiben, Version erhöhen,
Review-Status zurücksetzen, commit.

Der vollständige externe Draft-/Snapshot-Contract bleibt exakt:
`components: list[str]`, `labels: list[{code,name}]`,
`allergens: list[{code,name,presence}]`,
`origins: list[{ingredient,country_code,text}]` und
`allergen_review_status: string`. Er enthält keine internen IDs, Modi oder
Component-Versionen. `build_snapshot(profile_code, draft, revision_code)`
bleibt die Full-Snapshot-Schnittstelle.

## 3. Datenmodell (Migration 0010, Schema v12 → v13)

`menu_components` erhält: `id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY`
(interne PK), `public_id uuid UNIQUE` (externe URL-ID), `location_id`,
`profile_scope` (`common|patient|staff_guest`), `category`
(`meat|side|vegetable|sauce|dessert|other`), `name`, `origin_country_code`,
`active`, `row_version`, `created_at`, `updated_at`. Unique ist
`(location_id, profile_scope, lower(trim(name)))`. Ein archivierter Name bleibt
reserviert; es gibt kein DELETE.

Labels und Allergene sind Child-Zuordnungen und referenzieren mit ihren
`component_id`-FKs die interne `menu_components.id`-Bigint-ID. Die Allergen-PK ist
`(component_id, allergen_id)`; `allergen_id` referenziert die bestehende
Allergen-Masterzeile und enthält zusätzlich `presence` (`contains` oder
`may_contain`). Die Label-Kindzeile hat den Primärschlüssel
`(component_id, label_id)` und referenziert die bestehende Label-Masterzeile;
der Labelwert wird nicht dupliziert. `menu_item_components` erhält nullable `component_id` und
`component_row_version`; `component_text` bleibt exakt erhalten und ist bei
freien Texten der alleinige Inhalt.

`menu_items` erhält drei unabhängige Modi: `allergen_mode`, `origin_mode`,
`label_mode`, jeweils `auto|manual`. Es gibt keinen gemeinsamen `mode`.

Zuweisungen dürfen nur dieselbe Location und entweder `common` oder den
passenden Profile-Scope referenzieren; sonst 404. Archivierte, bereits
zugewiesene Komponenten bleiben sichtbar, sind aber nicht neu auswählbar.

## 4. Deterministische Auflösung und Snapshots

- Allergene: Union aller verknüpften Komponenten; bei gleichem Allergen
  gewinnt `contains` gegen `may_contain`.
- Herkunft: pro Komponentenname genau eine Country-Zeile; gleicher Name mit
  verschiedenen Ländern ist ein harter Fehler.
- Ernährung: Intersection über alle verknüpften Komponenten. Ein nullable
  Link/freier `component_text` erbt keine Allergene, Herkunft oder Labels.
- In `auto` rematerialisiert jede Änderung die effektiven bestehenden Tabellen;
  `manual` bewahrt die Werte je Klasse. Eine Komponenten- oder Linkänderung
  rematerialisiert nur Auto-Klassen und setzt den Review-Status zurück.
- Publish verweigert ungeprüfte oder stale Component-Versionen. Ein Review
  bestätigt die konkrete Version; bei Änderung muss neu geprüft werden.
- `get_component_review_token(engine, scope, item_id)` liefert einen
  **Single-Use-Pre-Review-Token** im Format `sha256:` plus 64
  Kleinbuchstaben-Hexzeichen. Er ist ein Optimistic-Concurrency-Token und kein
  Authentifizierungs- oder Capability-Ersatz. Sein kanonisches Tokenobjekt hat
  exakt diese acht Top-Level-Keys und Typen: `item_row_version: int > 0`,
  `allergen_mode|origin_mode|label_mode: 'auto'|'manual'`,
  `components: list`, `labels: list`, `allergens: list` und `origins: list`.
  Jedes Component-Objekt hat exakt
  `sort_order: int > 0,component_public_id: str|null,component_text: str,stored_component_row_version: int|null,current_component_row_version: int|null`;
  `null` ist nur bei den drei so markierten Component-Feldern erlaubt. Jedes
  Label hat exakt `code: str,name: str`, jedes Allergen exakt
  `code: str,name: str,presence: 'contains'|'may_contain'` und jede Herkunft
  exakt `ingredient: str,country_code: str,text: str`.
- Array-Reihenfolge ist ebenfalls Contract: Komponenten nach `sort_order ASC`
  (der Primärschlüssel `(menu_item_id, sort_order)` macht sie eindeutig),
  Labels nach `(code ASC, name ASC)`, Allergene nach
  `(code ASC, presence ASC, name ASC)` und Herkünfte nach
  `(ingredient ASC, country_code ASC, text ASC)`. UUIDs werden als kanonische
  Lowercase-Strings serialisiert; sonst bleiben Strings byteinhaltlich erhalten
  (kein Trim, Case-Folding oder Unicode-Normalisieren). Die Serialisierung ist
  exakt
  `json.dumps(payload, ensure_ascii=False, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('utf-8')`,
  ohne BOM oder abschließenden Zeilenumbruch. `sha256:` gehört nicht zu den
  gehashten Bytes. Der Review-Status selbst ist ausgeschlossen.
- Der verpflichtende Golden-Test verwendet exakt diese eine UTF-8-JSON-Zeile:

  ```json
  {"allergen_mode":"auto","allergens":[{"code":"A","name":"Gluten","presence":"contains"},{"code":"B","name":"Milch","presence":"may_contain"}],"components":[{"component_public_id":"11111111-1111-4111-8111-111111111111","component_text":"Rind & Crème","current_component_row_version":4,"sort_order":1,"stored_component_row_version":3},{"component_public_id":null,"component_text":"Freitext","current_component_row_version":null,"sort_order":2,"stored_component_row_version":null}],"item_row_version":7,"label_mode":"manual","labels":[{"code":"L1","name":"Hausgemacht"}],"origin_mode":"auto","origins":[{"country_code":"CH","ingredient":"Rind","text":"Schweiz"}]}
  ```

  Erwarteter Token ist exakt
  `sha256:46fe2582022c284f54706d9d57f8c2dd783154fd6d7d9bc434bcd22665542507`.
- Jede Transaktion, die `menu_item_components` erzeugt, ersetzt oder löscht,
  verwendet dieselbe globale Lock-Reihenfolge. Das gilt für
  `assign_component`, vollständigen Replace über
  `replace_component_links_connection`, Partial-Persistenz und
  Import/Recovery, sobald dieser Pfad Komponenten-Links schreibt. Sie sperrt
  zuerst das scoped `menu_items`-Item per `FOR UPDATE`; ein Batch-Pfad sperrt
  alle betroffenen Items nach numerischer `menu_items.id ASC`, bevor er
  Komponenten sperrt. Unter diesen Item-Locks bildet sie die Vereinigungsmenge
  aus allen bisher verlinkten Komponenten — einschließlich archivierter und
  beim Replace entfernter Links — sowie allen neu angeforderten Komponenten.
  Freitext-Links haben keine Komponenten-Zeile. Angeforderte Public-IDs werden
  ausschließlich über Location plus `common`/aktuelles Profil aufgelöst und
  validiert; neue archivierte Komponenten sind unzulässig, bestehende
  archivierte Links bleiben auflösbar. Kein Caller darf interne Komponenten-IDs
  liefern oder aus dem Scope heraustragen.
- Vor jedem Link-Lock oder Link-Write sperrt der Writer diese vollständige
  Komponentenmenge mit einem nach numerischer `menu_components.id ASC`
  geordneten `SELECT ... FOR SHARE`. Danach sperrt er bestehende Linkzeilen per
  `ORDER BY menu_item_id, sort_order FOR UPDATE`, löscht oder aktualisiert sie
  in derselben Reihenfolge und fügt neue Links nach
  `(menu_item_id, sort_order ASC)` ein. Alle Locks bleiben bis Commit oder
  Rollback. Diese Reihenfolge ist auch bei umgekehrter Caller- oder
  Assignment-Reihenfolge verbindlich.
- `review_component(engine, scope, item_id, component_version,
  expected_row_version)` verwendet `component_version` als den obigen
  Pre-Review-Token. Es sperrt in genau einer Transaktion und in dieser stabilen
  Reihenfolge: (1) das scoped `menu_items`-Item per `FOR UPDATE`, (2) die unter
  diesem Item-Lock aus allen aktuellen Links ermittelten Komponenten —
  einschließlich archivierter — per numerischer `menu_components.id ASC FOR
  SHARE` und (3) alle aktuellen `menu_item_components`-Linkzeilen per
  `ORDER BY menu_item_id, sort_order FOR UPDATE`. Damit verwendet Review
  dieselbe `Item → Komponenten → Links`-Reihenfolge und denselben kompatiblen
  Komponenten-Lock wie jeder Link-Writer; der Item-Lock verhindert während der
  Ermittlung und Tokenprüfung Phantom-Links. Alle Locks bleiben bis Commit oder
  Rollback.
- Erst nach allen Locks werden Scope, erwartete Item-`row_version`, aktuelle
  Komponenten-Versionen, effektive Auto-/Manual-Werte und Token aus den
  gesperrten Zeilen erneut gelesen und geprüft. Ein vorher gewinnender
  Concurrent-Write führt dadurch zu 409; ein späterer Write wartet. Fremder
  Scope liefert 404. Beide Antworten erfolgen ohne Teilmutation. Bei Erfolg
  rematerialisiert die Operation aktuelle Auto-Klassen, übernimmt aktuelle
  Komponenten-Versionen in die Links, markiert danach geprüft, erhöht die
  Item-`row_version` exakt einmal und schreibt
  `menu_weeks.updated_by=scope.actor_id` in derselben Transaktion. Sie liefert
  die neue Item-`row_version`; der HTTP-Handler antwortet per 303/PRG auf den
  scoped Menü-GET, der den neuen geprüften Zustand rendert.
- Ein verpflichtender Real-PG16-Test öffnet zwei unabhängige Connections und
  lässt beide dieselben zwei scoped Items mit umgekehrter Item- und
  Assignment-Reihenfolge ändern. Kontrollierte Synchronisation beweist ohne
  Timing-Annahme: kein Deadlock/`40P01`, ein deterministischer Gewinner, Warten
  des zweiten Writers und danach dessen stale 409 ohne Teilmutation; der
  Endzustand enthält exakt die Links des Gewinners. Derselbe Test deckt
  Single-Assign, Full-Replace und den von Partial-/Import-/Recovery genutzten
  Connection-Helper ab.
- Der akzeptierte Token ist absichtlich verbraucht: Erfolg ändert mindestens
  Item-`row_version` und gegebenenfalls gespeicherte Link-Versionen. Derselbe
  POST mit alter `row_version` und altem `component_version` liefert deshalb
  deterministisch 409 ohne Mutation. Ein nach dem Commit ändernder
  Komponenten-Write macht gespeicherte und aktuelle Komponenten-Version wieder
  verschieden; Publish bleibt bis zu einem neuen Review gesperrt. Es wird
  keine unveränderliche Per-Item-Audit-Historie ergänzt.
- Der Publish-Snapshot folgt exakt dem oben definierten externen verschachtelten
  Contract: `components` ist `list[str]`, `labels`, `allergens` und `origins`
  sind Listen von Dicts, und `allergen_review_status` ist ein String. Er enthält
  keine IDs, Modi oder Versionen und ist nach Publish unveränderlich.

## 5. Migration und Rückwärtskompatibilität

Migration `0010_v12_to_v13` ist die einzige Schemaänderung; `0001` bis `0009`
bleiben byte-identisch. Sie aktualisiert `SCHEMA_VERSION 13`,
`APPLICATION_VERSION dishboard-schema-v13`, Registry-Eintrag `0010`,
Schema-/Package-Validatoren, die Tabellenanzahl sowie Checksums und Manifeste.
`database/permissions.sql` erteilt den App-/Backup-Rollen ACLs für alle drei
neuen Tabellen sowie die erforderliche `menu_components`-Sequence und wird in
der bestehenden Restore-Reihenfolge erneut angewendet. Legacy-Backfill gehört
ausschließlich in die Migration, nie nach `db.py`: Sie erstellt zuerst die
Tabellen, ergänzt Mode-/Link-Spalten nullable oder mit sicherem Default,
setzt alle Legacy-Modi auf `manual`, legt danach pro Location, Profile und
Kategorie `other` deterministisch exakt eine Komponente für jeden alten Text
an und verlinkt Text, Link und Version exakt. Unmatched-Referenzen bleiben
gültig und als freier Text erhalten. Bei Legacy-Allergenen werden Duplikate
mit `contains`-Vorrang bereinigt. Erst nach Vollständigkeitsprüfungen folgen
Constraints, FKs, Unique- und NOT-NULL-Regeln. Das SQL beginnt mit `BEGIN;`
und endet mit einem nicht-leeren `COMMIT;`, dem kein Kommentar folgt; leerer
und befüllter Bestand, Idempotenz, Rollback und Terminator sind getestet.
Allergen- und Label-Metadaten werden nur bei einem Legacy-Item mit exakt einer
Komponenten-Zeile auf dessen Komponente projiziert; bei mehreren Komponenten
gibt es keine solche Projektion. Die bestehenden Item-Zeilen, alle `manual`-
Modi und Herkunftswerte bleiben dabei unverändert.

Vor Migration: benanntes PostgreSQL-Backup und Down-Probe-Kopie. Down-Probe
prüft restaurierbare v12-Daten; sie behauptet keine magische Reversibilität.
Die Migration ist idempotent, transaktional und bei Fehlern vollständig
rollbackbar.

## 6. Exakte Admin-Routen und Berechtigungen

Alle Routen verlangen eine gültige authentifizierte Session sowie die jeweils
aufgeführten bestehenden Capabilities: Übersichts-, Menü-, Header-, Service-,
Preview- und Kataloglisten-GETs benötigen `draft.read`; Menü-, Header-,
Service-, Review- und Katalog-Create/Edit/Archive/Unarchive/Copy-POSTs benötigen
`draft.write`; Publish benötigt `publication.publish`. Das bestehende
Rollen-/Capability-Modell bleibt unverändert; es gibt keinen neuen
Admin-only-Bypass. Alle POSTs verlangen CSRF und `Cache-Control: no-store`.
Bestehende URL-Familien bleiben erhalten:
`/admin/cafeteria` wird serverseitig fest auf `staff_guest` und
`/admin/patienten` fest auf `patient` abgebildet. Das Profil kommt ausschließlich
aus dieser URL-Familie; kein Handler akzeptiert es im Body oder Query-String.
Komponenten-URLs verwenden `public_id`, nie die interne Bigint-ID.
Jede POST-Form enthält den aktuellen Feldnamen `_csrf` (nie `csrf`) sowie nur
die für ihre Operation explizit erlaubten Felder und, wo sie schreibt, die
erwartete `row_version`.
Login, Session-Cookie und der bestehende Auth-CSRF-Token `csrf_token` bleiben
unverändert; der neue `_csrf`-Name gilt ausschließlich für den Admin-POST-
Contract und ersetzt keinen Auth-Contract.

| Methode und Route | Zweck / erlaubte Eingabe |
|---|---|
| `GET /admin/cafeteria?week=` und `GET /admin/patienten?week=` | Wochenübersicht, Header, Service und Grid |
| `GET /admin/{cafeteria\|patienten}/menu?week=&day=&meal=&option=` | fokussierte Menüzeile |
| `POST /admin/{cafeteria\|patienten}/menu` | exact `_csrf,week,day,meal,option,row_version,fields` |
| `POST /admin/{cafeteria\|patienten}/menu/review` | `draft.write`; exact `_csrf,week,day,meal,option,row_version,component_version`; `component_version` ist der Single-Use-Pre-Review-Token; Item wird serverseitig aus dem Raster aufgelöst, internes `item_id` ist verboten; Erfolg ist 303/PRG, Wiederholung mit altem Token 409 |
| `GET /admin/{cafeteria\|patienten}/header?week=` | Header laden |
| `POST /admin/{cafeteria\|patienten}/header` | Header speichern |
| `GET /admin/{cafeteria\|patienten}/service?week=` | Service-Status laden |
| `POST /admin/{cafeteria\|patienten}/service` | Service-Status speichern |
| `GET /admin/{cafeteria\|patienten}/komponenten?q=&category=&include_archived=` | Suche, Kategorie, Archivfilter, Nutzung und Sortierung; Profil aus URL-Familie |
| `POST /admin/{cafeteria\|patienten}/komponenten` | Komponente mit exact Feldern anlegen |
| `GET /admin/{cafeteria\|patienten}/komponenten/<public_id>` | Komponente anzeigen |
| `POST /admin/{cafeteria\|patienten}/komponenten/<public_id>` | Komponente bearbeiten, row_version erforderlich |
| `POST /admin/{cafeteria\|patienten}/komponenten/<public_id>/archive` | archivieren, keine Löschung |
| `POST /admin/{cafeteria\|patienten}/komponenten/<public_id>/unarchive` | reaktivieren, Name bleibt reserviert |
| `GET /admin/{cafeteria\|patienten}/copy?week=` | leere Zielwochen anbieten |
| `POST /admin/{cafeteria\|patienten}/copy` | `_csrf,source_week,target_week,target_row_version` |
| `GET /admin/{cafeteria\|patienten}/preview?week=` | zuletzt gespeicherten Draft anzeigen |
| `POST /admin/{cafeteria\|patienten}/publish` | `_csrf,week,row_version` exakt; Publish |

Die Komponentensuche für eine Zuweisung zeigt nur aktive Komponenten mit
`common`- oder passendem Scope; die Katalogverwaltung darf mit
`include_archived=1` zusätzlich archivierte Komponenten anzeigen. Katalog-CRUD,
Zuweisung, Copy und Publish erzwingen Location- und Scope-Isolation.
Copy ist nur für eine wirklich leere Zielwoche desselben Profils erlaubt,
läuft atomar unter Locks, erzeugt neue `external_id`s, setzt Reviews zurück,
publiziert nicht und kopiert beim Patient keine Preise. Nicht leere oder
gleichzeitig geänderte Ziele liefern 409 ohne Teilmutation.
„Wirklich leer“ bedeutet dabei exakt: null `menu_items` für Zielwoche und
Profil sowie keine aktive Veröffentlichung für dieses Ziel.

## 7. Preview, Save, Publish und Fehlertexte

Preview zeigt ausschließlich den LAST-SAVED-Draft, nie Dirty-Client-State;
`draft.read` ist erforderlich. Sie ist Admin-only, nicht Signage/Public,
öffnet per `target="_blank"`, trägt einen eindeutigen PREVIEW-Banner und hat
keinen Fallback auf Live-Daten. `no-store` ist Pflicht. Dirty-State blockiert
Preview und Publish bis zum Speichern.

Publish ist ausschließlich POST mit den drei Feldern `_csrf`, `week`, `row_version`;
native `confirm()` vor dem Absenden. Server prüft gespeicherten Draft,
Rasterschema, Review und Component-Versionen, erzeugt immutable Snapshot und
antwortet PRG mit Revision/Flash in `aria-live`. 400/409 darf nichts ändern.

Die UI berechnet `derive_admin_status` unabhängig vom DB-Enum: `empty`, wenn
es null Menüeinträge und keine aktive Veröffentlichung gibt; `incomplete`,
wenn Draft-Validierung fehlschlägt; `review_open`, wenn ein vollständiger Draft
unchecked oder stale ist; `live`, wenn der aktive Snapshot dem frisch aus dem
gespeicherten Draft mit derselben Revisionsidentität gebauten Snapshot gleicht;
`changed`, wenn eine aktive Veröffentlichung abweicht; sonst `ready`. Der
DB-Workflow-State bleibt ausschließlich `draft|ready|published|archived`.
Statuswerte der UI sind damit exakt `empty`, `incomplete`, `review_open`,
`ready`, `live`, `changed`. Deutsche Novice-Texte nennen Tag, Mahlzeit, Option und Feld, z.B.
„Mittwoch, Abend, Vegetarisch: Preis darf höchstens zwei Nachkommastellen haben.“
CHF akzeptiert Punkt oder Komma, normalisiert zu Decimal und speichert exakt
positive Rappen; Cafeteria erfordert `external >= internal` sowie beide
positiv. Patienten senden und speichern keine Preisfelder.

## 8. UI- und Accessibility-Vertrag

Native Checkbox plus sichtbares `label` in `fieldset/legend`; Label-Trefferzone
mindestens 44 px, Checkbox 18–24 px. Tastaturreihenfolge, sichtbarer
Fokusindikator, Escape/Cancel und kein Status allein über Farbe sind Pflicht.
Sticky Save/Preview/Publish-Aktionen berücksichtigen Safe-Area-Inset.
Zustände `empty`, `loading` (`aria-busy` plus Skeleton), `error` (Retry) und
`dense` sind implementiert und deutsch beschriftet. Zu prüfen bei 390×844,
1440×1100, 2560×1440 und 50-%-Zoom. Bestehende `--sh-*`-Tokens und Fira Sans
werden wiederverwendet; keine neuen Abhängigkeiten oder harten Hexwerte.

## 9. Verbindliche Abnahmematrix

Named RED-Tests (zuerst rot, danach grün) und Dateien:

| Test | Datei / Beweis |
|---|---|
| reale PG16-Migration, Grants, Schema 13, Backfill-/Terminator-Contract | `reference_scaffold/tests/test_component_catalog_migration_db.py`, `reference_scaffold/tests/test_auth_database.py`, `reference_scaffold/tests/test_database_invariants.py` |
| Katalog CRUD/Archiv/Suche/Usage und Isolation | `reference_scaffold/tests/test_component_catalog_db.py`, `reference_scaffold/tests/test_component_catalog_routes.py` |
| Komponenten-Zuweisung, Allergie-Union/contains, Herkunft-Konflikt, Diet-Intersection | `reference_scaffold/tests/test_component_assignment_db.py` |
| Location/Profile-Isolation und Public-ID/404 | `reference_scaffold/tests/test_public_isolation_homoglyphs.py`, `reference_scaffold/tests/test_database_invariants.py` |
| exakter immutable Snapshot, Golden-Hash-Token, Lock-Reihenfolge und Concurrent-/Repeat-Review | `reference_scaffold/tests/test_admin_workflow_db.py` |
| leerer Same-Profile-Copy, Lock/409, neue IDs | `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_workflow_form.py` |
| LAST-SAVED Preview, no-store, Dirty-Guard | `reference_scaffold/tests/test_admin_draft_preview.py` |
| Publish/PRG/Review/Stale/CSRF/400/409 | `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_workflow_form.py` |
| CHF Parsing/Rappen/Patient-Preisverbot und Wochen-Familien | `reference_scaffold/tests/test_admin_week_routes.py` |
| Browser-A11y und Viewport-Matrix | `reference_scaffold/tests/test_admin_ux_browser.py` (neu erstellt durch Wiederverwendung der bestehenden Playwright-Muster/Fixtures aus `test_rendered_ui.py`) |

Gates mit verbatim Receipts: vollständiges `pytest`, reale PG16-
Compose-/Migrationsprüfung, Schema- und Package-Validatoren, Ruff, Bandit,
Secret-Scan, GitNexus `detect_changes`, OCR-Review sowie unabhängige AGY- und
Grok-Reviews. Browser: Chromium und vorhandene CI-Browser bei allen vier
Viewports, Tastatur/Fokus, Fehler/Retry, Copy/Preview/Publish.

Deployment-Gate: Backup-ID, Migration auf Schema 13, unveränderlicher
Image-Digest, Healthcheck, authentifizierter Admin-Smoke, Screenshots und
Proof-ZIP; anschließend dokumentierter Rollback-/Restore-Probe. Kein Gate darf
durch „alle Tests pass“ ohne Kommandoausgabe ersetzt werden.

## 10. Umsetzungseigentum und Stop-Bedingungen

Phase 1 (Schema, 0010, Grants, Validator) und Phase 2 (Store, Modelle,
Inheritance) werden seriell am gemeinsamen Contract bearbeitet.
`component_assignment_store` ist erst T4 und danach T5 zugeordnet;
`workflow_store.py` hat T6 als einzigen seriellen Owner und erhält dort nur
minimale Kompatibilitätsedits für Full-Import/Recovery (kein Partial-Write und
kein Full-Replace aus Partial-Modulen). Phase 3
(Routen/Workflow/Publish) folgt erst nach Contract-Receipt. Phase 4
(Jinja/Vanilla JS/CSS) folgt danach; Test- und Review-Lanes dürfen parallel
lesen, aber niemals dieselben Dateien schreiben. CSV-Import bleibt Freitext
plus `manual`; er führt keine stillen Katalogeinträge ein. Bei fehlendem
Backup, unklarem Scope, stale Version, nicht bestandenem HIGH/CRITICAL-Review
oder fehlender Auth-/Browser-Evidenz: BLOCKED, kein Push/Deploy.

## 11. Selbstprüfung

Diese SDD enthält keine ungelösten oder undefinierten Anweisungen und keine
pauschale „alle Tests pass“-Behauptung. Patient-Raster, Cafeteria-Raster, Preisregeln,
Full-Replace-Ausnahme, drei Modi, Preview-Quelle und Publish-Guards sind
explizit getrennt; `dish_templates` bleibt unangetastet. Jede Implementierung
muss die oben genannten exact keys, Statuswerte, Fehlercodes und named
Receipts liefern.
