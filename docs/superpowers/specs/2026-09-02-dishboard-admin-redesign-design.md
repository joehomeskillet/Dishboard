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

## 3. Datenmodell (Migration 0010, Schema v12 → v13)

`menu_components` erhält: `id UUID` (interne PK), `location_id`,
`profile_scope` (`common|patient|staff_guest`), `category`
(`meat|side|vegetable|sauce|dessert|other`), `name`, `origin_country_code`,
`active`, `row_version`, `created_at`, `updated_at`. Unique ist
`(location_id, profile_scope, lower(trim(name)))`. Ein archivierter Name bleibt
reserviert; es gibt kein DELETE.

Labels und Allergene sind Child-Zuordnungen. Die Allergen-PK ist
`(component_id, allergen)` und enthält zusätzlich `presence` (`contains` oder
`may_contain`). Label-Zuordnungen tragen den Labelwert und den jeweils nötigen
Klassenschlüssel. `menu_item_components` erhält nullable `component_id` und
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
- Der Publish-Snapshot enthält exakt die bestehenden externen Schlüssel und
  `list[str]`-Werte. Er enthält keine internen IDs, Modi oder Versionen und ist
  nach Publish unveränderlich.

## 5. Migration und Rückwärtskompatibilität

Migration `0010_v12_to_v13` ist die einzige Schemaänderung; `0001` bis `0009`
bleiben byte-identisch. Sie aktualisiert Schema-/DB-Konstanten, Grants,
Validatoren und Tests. Legacy-Zeilen werden je Location, Profile und Kategorie
`other` getrennt backgefüllt; der exakte alte Text wird einmalig angelegt und
exakt verlinkt. Unmatched-Referenzen bleiben gültig und als freier Text
erhalten. Bestehende Menüs werden in allen drei Klassen auf `manual` gesetzt.
Bei Legacy-Allergenen bereinigt die Migration Duplikate mit
`contains`-Vorrang.

Vor Migration: benanntes PostgreSQL-Backup und Down-Probe-Kopie. Down-Probe
prüft restaurierbare v12-Daten; sie behauptet keine magische Reversibilität.
Die Migration ist idempotent, transaktional und bei Fehlern vollständig
rollbackbar.

## 6. Exakte Admin-Routen und Berechtigungen

Alle Routen liegen unter `/admin/dishboard`, verlangen Session-Admin,
`draft.read` bzw. `draft.write`, CSRF bei POST und `Cache-Control: no-store`.
UUIDs werden in URLs verwendet; `profile` kommt ausschließlich aus der Route.

| Methode und Route | Zweck / erlaubte Eingabe |
|---|---|
| `GET /admin/dishboard/<profile>/overview?week=` | Wochenübersicht, Header, Service und Grid |
| `GET /admin/dishboard/<profile>/menu?week=&day=&meal=&option=` | fokussierte Menüzeile |
| `POST /admin/dishboard/<profile>/menu` | exact `csrf,week,day,meal,option,version,fields` |
| `GET /admin/dishboard/<profile>/header?week=` / `POST .../header` | Header laden/speichern |
| `GET /admin/dishboard/<profile>/service?week=` / `POST .../service` | Service-Status laden/speichern |
| `GET /admin/dishboard/catalog?profile=&q=&category=&archived=` | Suche, Kategorie, Archivfilter, Nutzung und Sortierung |
| `POST /admin/dishboard/catalog` | Komponente mit exact Feldern anlegen |
| `GET /admin/dishboard/catalog/<uuid>` / `POST .../<uuid>` | anzeigen/bearbeiten, row_version erforderlich |
| `POST /admin/dishboard/catalog/<uuid>/archive` | archivieren, keine Löschung |
| `POST /admin/dishboard/catalog/<uuid>/unarchive` | reaktivieren, Name bleibt reserviert |
| `GET /admin/dishboard/<profile>/copy?week=` | leere Zielwochen anbieten |
| `POST /admin/dishboard/<profile>/copy` | `csrf,source_week,target_week,target_version` |
| `GET /admin/dishboard/<profile>/preview?week=` | zuletzt gespeicherten Draft anzeigen |
| `POST /admin/dishboard/<profile>/publish` | `csrf,week,version` exakt; Publish |

`<profile>` ist nur `patient` oder `staff_guest`; andere Werte 404. Katalog-
CRUD, Zuweisung, Copy und Publish erzwingen Location- und Scope-Isolation.
Copy ist nur für eine wirklich leere Zielwoche desselben Profils erlaubt,
läuft atomar unter Locks, erzeugt neue `external_id`s, setzt Reviews zurück,
publiziert nicht und kopiert beim Patient keine Preise. Nicht leere oder
gleichzeitig geänderte Ziele liefern 409 ohne Teilmutation.

## 7. Preview, Save, Publish und Fehlertexte

Preview zeigt ausschließlich den LAST-SAVED-Draft, nie Dirty-Client-State;
`draft.read` ist erforderlich. Sie ist Admin-only, nicht Signage/Public,
öffnet per `target="_blank"`, trägt einen eindeutigen PREVIEW-Banner und hat
keinen Fallback auf Live-Daten. `no-store` ist Pflicht. Dirty-State blockiert
Preview und Publish bis zum Speichern.

Publish ist ausschließlich POST mit den drei Feldern `csrf`, `week`, `version`;
native `confirm()` vor dem Absenden. Server prüft gespeicherten Draft,
Rasterschema, Review und Component-Versionen, erzeugt immutable Snapshot und
antwortet PRG mit Revision/Flash in `aria-live`. 400/409 darf nichts ändern.

Statuswerte sind exakt `empty`, `incomplete`, `review_open`, `ready`, `live`,
`changed`. Deutsche Novice-Texte nennen Tag, Mahlzeit, Option und Feld, z.B.
„Mittwoch, Abend, Menü 2: Preis darf höchstens zwei Nachkommastellen haben.“
CHF akzeptiert Punkt oder Komma, normalisiert zu Decimal und speichert exakt
positive Rappen; Cafeteria erfordert `external > internal` sowie beide
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
| reale PG16-Migration, Grants, Schema 13 | `tests/db/test_migration_0010.py` |
| Katalog CRUD/Archiv/Suche/Usage und Isolation | `tests/admin/test_catalog.py` |
| Allergie-Union/contains, Herkunft-Konflikt, Diet-Intersection | `tests/menu/test_component_inheritance.py` |
| Location/Profile-Isolation und UUID/404 | `tests/admin/test_isolation.py` |
| exakter immutable Snapshot | `tests/menu/test_snapshot.py` |
| leerer Same-Profile-Copy, Lock/409, neue IDs | `tests/admin/test_copy.py` |
| LAST-SAVED Preview, no-store, Dirty-Guard | `tests/admin/test_preview.py` |
| Publish/PRG/Review/Stale/CSRF/400/409 | `tests/admin/test_publish.py` |
| CHF Parsing/Rappen/Patient-Preisverbot | `tests/menu/test_prices.py` |
| Browser-A11y und Viewport-Matrix | `tests/e2e/admin_dishboard.spec.ts` |

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
Inheritance) werden seriell am gemeinsamen Contract bearbeitet. Phase 3
(Routen/Workflow/Publish) folgt erst nach Contract-Receipt. Phase 4
(Jinja/Vanilla JS/CSS) folgt danach; Test- und Review-Lanes dürfen parallel
lesen, aber niemals dieselben Dateien schreiben. CSV-Import bleibt Freitext
plus `manual`; er führt keine stillen Katalogeinträge ein. Bei fehlendem
Backup, unklarem Scope, stale Version, nicht bestandenem HIGH/CRITICAL-Review
oder fehlender Auth-/Browser-Evidenz: BLOCKED, kein Push/Deploy.

## 11. Selbstprüfung

Diese SDD enthält keine TBD/TODO-Platzhalter und keine pauschale
„alle Tests pass“-Behauptung. Patient-Raster, Cafeteria-Raster, Preisregeln,
Full-Replace-Ausnahme, drei Modi, Preview-Quelle und Publish-Guards sind
explizit getrennt; `dish_templates` bleibt unangetastet. Jede Implementierung
muss die oben genannten exact keys, Statuswerte, Fehlercodes und named
Receipts liefern.
