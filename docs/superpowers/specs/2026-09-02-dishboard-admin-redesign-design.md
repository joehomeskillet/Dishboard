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

- `persist_menu_item(engine: Engine, scope: AdminScope, week_start: date, day: str, meal: str, option: str, payload: Mapping[str, object], expected_item_row_version: int) -> int`
- `persist_week_header(engine: Engine, scope: AdminScope, week_start: date, payload: Mapping[str, object], expected_week_row_version: int) -> int`
- `persist_service_state(engine: Engine, scope: AdminScope, week_start: date, day: str, meal: str, payload: Mapping[str, object], expected_service_row_version: int) -> int`

`week` und `day` sind strikt geparste ISO-Daten `YYYY-MM-DD`; `week` muss ein
Montag sein und `day` muss zwischen diesem Montag und Sonntag liegen. `meal`
ist exakt `LUNCH|DINNER`, wobei `staff_guest` nur `LUNCH` akzeptiert. `option`
ist exakt `MENU_1|VEGGIE`. Jeder andere Wert ist 400, bevor eine Transaktion
schreibt.

Jede Operation prüft route-abgeleitetes Profil, validierte ISO-Montag-Woche
(`?week=YYYY-MM-DD`), erwartete `row_version` und exact allowed keys. Ein
Konflikt liefert 409 ohne Mutation; ein Validierungsfehler 400 mit Feldpfad.
Partial-Saves ändern nur die adressierte Zeile bzw. den Header/Service-Status.
Transaktion: lock, nochmals lesen, validieren, schreiben, Version erhöhen,
Review-Status zurücksetzen, commit.

Bei Menüformularen bezeichnet `row_version` ausschließlich
`menu_items.row_version`; nach dem Parsen heißt das Argument durchgehend
`expected_item_row_version`. Die vollständige Slot-Identität
`(location_id,profile_id,week_start,service_date,meal_period_id,menu_type_id)`
wird serverseitig aus `AdminScope`, URL und Raster aufgelöst. Formulare liefern
keine internen IDs. Ein gültiger fehlender Raster-Slot wird als virtuelles Item
mit `row_version=0` gerendert, nicht als 404; ein ungültiger oder scope-fremder
Slot bleibt 404. Exakte Writes: 0+fehlend fügt Version 1 ein und liefert 1;
vorhanden+0 ist 409; fehlend+positiv ist 404; positiv aber stale ist 409; exakt
passend erhöht einmal und liefert alt+1.

Header-CAS bezieht sich ausschließlich auf `menu_weeks.row_version`: 0 plus
fehlende Woche erzeugt Version 1 und liefert 1; 0 plus vorhandene Woche ist
409; positiv plus fehlende Woche ist 404; stale positiv ist 409; exakt
passendes positives `v` schreibt einmal und liefert `v+1`. Service-CAS bezieht
sich ausschließlich auf `menu_services.row_version` und verwendet dieselbe
Matrix: 0 plus fehlender Raster-Service erzeugt Version 1 und liefert 1; 0
plus vorhandener Service ist 409; positiv plus fehlender Service ist 404;
stale positiv ist 409; exakt passendes positives `v` schreibt einmal und
liefert `v+1`. Nur die drei Engine-Write-APIs dürfen fehlende Zeilen erzeugen.
Sie serialisieren eine fehlende Woche per `ON CONFLICT`, sperren sofort die
gewinnende Wochenzeile und erzeugen Service oder Item erst unter den bereits
gehaltenen Parent-Locks. Read-Resolver erzeugen nie Daten.

Ein Service-POST mit `service_state=closed` liefert 409, sobald der Service
mindestens ein Item enthält; er löscht oder versteckt keine Items. Einen
geschlossenen Service öffnet ausschließlich ein expliziter, versionspassender
Service-POST mit `service_state=open`. Header- oder Item-Saves, Import und Copy
öffnen ihn nicht implizit.

Nach dem Form-Parser hat ein internes Patienten-Item exakt die Top-Level-Keys
`title,description,note,allergen_mode,origin_mode,label_mode,assignments,labels,allergens,origins`.
Ein internes `staff_guest`-Item hat zusätzlich exakt
`internal_rappen,external_rappen`; kein anderes internes Preis- oder
Currency-Feld ist erlaubt. `assignments` folgt dem exakten Zwei-Key-Vertrag,
`labels` ist eine Liste von Codes, `allergens` eine Liste aus exakt
`code,presence` und `origins` eine Liste aus exakt
`ingredient,country_code,text`. Alle drei Modi sind unabhängig `auto|manual`.
Der externe Draft/Publish-Snapshot wird daraus über eine explizite Allowlist
projiziert; kein internes Item-Mapping wird direkt serialisiert.

Bei manueller Herkunft müssen `origin_ingredient[]` und
`origin_country_code[]` gleich lang sein. Der Parser trimmt beide Werte,
verlangt eine nichtleere Zutat und einen Code nach `^[A-Z]{2}$` und bildet
`text` exakt als `f"{ingredient}: {country_code}"`. Eine nach diesem Trim
byte-identisch doppelte Zutat macht den gesamten Request ungültig; es gibt
keine Casefold- oder Unicode-Normalisierung.

Bei einem ersten validen Item-Write darf die scoped Woche mit Version 1 per
`ON CONFLICT` angelegt werden; danach sperrt die Transaktion die gewinnende
Wochenzeile. Ein fehlender Service wird `open` mit Version 1 angelegt. Einen
vorhandenen geschlossenen Service öffnet Item-Save nie wieder, sondern liefert
atomar 409. Bei vorhandener Woche wird `updated_by` exakt einmal geschrieben;
eine neue Woche erhält den Actor bereits beim Insert und wird nicht redundant
aktualisiert. Ein synchronisiertes Same-Slot-v0-Race hat exakt einen Gewinner
und einen 409-Verlierer. Zwei verschiedene gültige v0-Slots serialisieren am
Wochen-Lock und gewinnen beide ohne Nachbaränderung.

Der vollständige externe Draft-/Snapshot-Contract bleibt exakt:
`components: list[str]`, `labels: list[{code,name}]`,
`allergens: list[{code,name,presence}]`,
`origins: list[{ingredient,country_code,text}]` und
`allergen_review_status: string`. Er enthält keine internen IDs, Modi oder
Component-Versionen. `build_snapshot(profile_code, draft, revision_code)`
bleibt die Full-Snapshot-Schnittstelle.

## 3. Datenmodell (Migrationen 0010 und 0011, Schema v12 → v14)

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

Schema v14 ergänzt ausschließlich den schmalen Master-Lock-Helper
`cafeteria.lock_component_metadata_masters(text[], text[])`. Der
Funktions-Owner ist identisch mit dem Owner des Schemas `cafeteria` und darf
nie `cafeteria_app` sein. Der Katalog-Store ruft ihn genau einmal innerhalb
derselben äußeren Create-/Update-Transaktion mit gebundenen Arrays auf; die
erworbenen Locks bleiben damit bis Commit/Rollback erhalten. Sein verbindlicher
SQL-Contract ist:

```sql
CREATE OR REPLACE FUNCTION cafeteria.lock_component_metadata_masters(
    p_label_codes text[],
    p_allergen_codes text[]
)
RETURNS TABLE (
    master_kind text,
    master_id smallint,
    code text,
    active boolean
)
LANGUAGE plpgsql
SECURITY DEFINER
VOLATILE
PARALLEL UNSAFE
SET search_path = pg_catalog, cafeteria, pg_temp
AS $function$
BEGIN
    IF p_label_codes IS NULL
       OR p_allergen_codes IS NULL
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.unnest(p_label_codes) AS requested(code)
           WHERE requested.code IS NULL
       )
       OR EXISTS (
           SELECT 1
           FROM pg_catalog.unnest(p_allergen_codes) AS requested(code)
           WHERE requested.code IS NULL
       ) THEN
        RAISE EXCEPTION 'metadata code arrays must be non-null and contain no nulls'
            USING ERRCODE = '22023';
    END IF;

    RETURN QUERY
    SELECT 'label'::text, label.id, label.code, label.active
    FROM cafeteria.dietary_labels AS label
    WHERE label.code = ANY (p_label_codes)
    ORDER BY label.id
    FOR SHARE OF label;

    RETURN QUERY
    SELECT 'allergen'::text, allergen.id, allergen.code, allergen.active
    FROM cafeteria.allergens AS allergen
    WHERE allergen.code = ANY (p_allergen_codes)
    ORDER BY allergen.id
    FOR SHARE OF allergen;
END;
$function$;

REVOKE ALL ON FUNCTION
    cafeteria.lock_component_metadata_masters(text[], text[])
FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer;

GRANT EXECUTE ON FUNCTION
    cafeteria.lock_component_metadata_masters(text[], text[])
TO cafeteria_app;
```

Damit werden immer zuerst alle angeforderten Label-Master nach `id ASC`, dann
alle angeforderten Allergen-Master nach `id ASC` gesperrt. Leere Arrays sind
gültig. Der Store weist doppelte Request-Codes vor dem Aufruf **je Namespace
unabhängig** zurück; derselbe Code darf einmal als Label und einmal als
Allergen angefordert werden. Die Antwort wird nach `master_kind` in `label`
und `allergen` partitioniert. Ein anderer `master_kind` oder ein doppeltes
`(master_kind, code)` ist ein kontrollierter Validierungsfehler. Danach muss
die Menge der angeforderten Label-Codes exakt der Menge der zurückgegebenen
Label-Codes und getrennt davon die Menge der angeforderten Allergen-Codes
exakt der Menge der zurückgegebenen Allergen-Codes entsprechen; so werden
unbekannte Codes ohne Namespace-Kollision zurückgewiesen. Inaktive Treffer
werden bewusst zurückgegeben und nach der bestehenden Retention-Regel
bewertet. Interne `master_id`-Werte bleiben ausschließlich DB-intern. Es gibt
keinen direkten Master-`FOR SHARE` aus der App-Rolle und keinen
`UPDATE`-Grant auf Mastertabellen.

Verpflichtende Real-PG16-Sicherheitstests beweisen denselben Owner-/ACL-Zustand
für Fresh Schema, v13→v14-Migration und Restore. Direkter Master-`UPDATE` und
direktes `SELECT ... FOR SHARE` als `cafeteria_app` scheitern, der exakte
Helper-Aufruf gelingt; `PUBLIC`, `cafeteria_backup` und
`cafeteria_auth_issuer` können ihn nicht ausführen. Zwei synchronisierte
Connections ohne Timing-Sleeps beweisen auch bei umgekehrter Input-Reihenfolge
`Label id ASC → Allergen id ASC`, blockierende Owner-Updates nur für
angeforderte Master und keinen `40P01`. Abgedeckt sind leere, doppelte,
unbekannte und inaktive Codes, Null-Arrays/-Elemente, SQL-looking Werte,
gebundene Arrays und `pg_temp`-Shadowing. `database/permissions.sql` entfernt
breite Grants bei jedem Lauf idempotent; die SECURITY-DEFINER-Allowlist nennt
nur die exakte Signatur.

Die öffentlichen Create-, Find- und Get-Records einer Komponente haben
einheitlich exakt die Keys `public_id,profile_scope,category,name,`
`origin_country_code,active,row_version,usage_count,labels,allergens`. Ein
Label-Objekt hat exakt `code,name`, ein Allergen-Objekt exakt
`code,name,presence`. Labels sind stabil nach `(code ASC, name ASC)`, Allergene
nach `(code ASC, presence ASC, name ASC)` sortiert. Interne IDs und Zeitstempel
werden nie ausgegeben.

`menu_items` erhält drei unabhängige Modi: `allergen_mode`, `origin_mode`,
`label_mode`, jeweils `auto|manual`. Es gibt keinen gemeinsamen `mode`.

Zuweisungen dürfen nur dieselbe Location und entweder `common` oder den
passenden Profile-Scope referenzieren; sonst 404. Archivierte, bereits
zugewiesene Komponenten bleiben sichtbar, sind aber nicht neu auswählbar.

## 4. Deterministische Auflösung und Snapshots

- Allergene: Union aller verknüpften Komponenten; bei gleichem Allergen
  gewinnt `contains` gegen `may_contain`.
- Herkunft: Verknüpfte Katalogkomponenten mit `NULL`-Herkunft werden
  ausgeschlossen. Jede andere erzeugt exakt
  `ingredient = current component.name`, `country_code = origin_country_code`
  (kanonischer ISO-Code) und
  `text = f"{component.name}: {origin_country_code}"`. Pro aktuellem
  Komponentenname ist genau ein Land erlaubt; derselbe Name mit verschiedenen
  Ländern bricht die gesamte Mutation atomar ab.
- Ernährung: Intersection über alle verknüpften Komponenten. Ein nullable
  Link/freier `component_text` erbt keine Allergene, Herkunft oder Labels.
- Architektur A ist verbindlich: Eine Katalog-Metadatenänderung mutiert nur die
  Komponente und ihre Label-/Allergen-Childzeilen und erhöht die
  Komponenten-`row_version` exakt einmal. Sie mutiert weder verknüpfte Items,
  Review-Zeilen oder Wochen noch auto-materialisierte oder manuelle Itemwerte.
  Bestehende Assignments behalten ihre gespeicherte `component_row_version`;
  die dynamisch erkannte Abweichung zur aktuellen Komponenten-Version bedeutet
  `needs-review` und blockiert Publish. Archive und Unarchive verwenden dieselbe
  Stale-Link-Regel. Jeder Metadaten-Child-Writer sperrt zuerst die Parent-
  Komponente `FOR UPDATE`, validiert den gesamten Payload vor einem Delete und
  ersetzt Childzeilen deterministisch.
- Eine Linkänderung rematerialisiert nur die Auto-Klassen und setzt den
  Review-Status zurück. Der spätere Review eines einzelnen Items
  rematerialisiert dessen aktuelle Auto-Effekte, bewahrt jede manuelle Klasse
  byte-identisch, übernimmt die aktuellen Komponenten-Versionen in dessen
  Links, aktualisiert bei Kataloglinks `component_text` aus dem aktuellen
  Katalognamen, lässt freien Text byte-identisch und beseitigt damit den
  Versions-Mismatch. Die Katalog-UI weist nach
  Metadatenänderung, Archive oder Unarchive darauf hin, dass betroffene Gerichte
  erneut geprüft werden müssen.
- Erzeugt eine Katalogänderung für ein bereits verknüpftes Item mit
  `origin_mode='auto'` zwei aktuelle Komponenten gleichen Namens, aber mit
  verschiedenen Ländern, bleibt die Katalogänderung gemäß Architektur A
  erlaubt: Der Komponenten-Versions-Mismatch erzeugt dynamisch `needs-review`
  und blockiert Publish. Erst die Auto-Herkunftsauflösung in
  `get_component_review_token` oder `review_component` wirft den benannten,
  kontrollierten Domain-Konflikt `AutoOriginConflictError`. Dieser Fehler lässt
  Links, effektive Werte, Review, Item und Woche atomar unverändert. Die Route
  bildet ihn immer auf HTTP 409 mit der handlungsorientierten deutschen
  Meldung `Herkunftskonflikt: Komponente bearbeiten oder Herkunft dieses Menüs
  auf manuell stellen.` ab, nie auf 500. Bei `origin_mode='manual'` wird keine
  Auto-Herkunft aufgelöst: manuelle Herkunft bleibt byte-identisch und das
  Item kann trotz desselben Katalogkonflikts geprüft werden.
- Load, Status und Publish verwenden zentral exakt
  `review_open/needs_review = allergen_review_status != 'checked' OR EXISTS(stored linked_component_version <> current component row_version)`.
  Ein persistiertes `checked` überschreibt daher nie einen Versions-Mismatch.
  Publish verweigert `needs_review`; ein Review bestätigt die konkrete Version.
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
  {"allergen_mode":"auto","allergens":[{"code":"A","name":"Gluten","presence":"contains"},{"code":"B","name":"Milch","presence":"may_contain"}],"components":[{"component_public_id":"11111111-1111-4111-8111-111111111111","component_text":"Rind & Crème","current_component_row_version":4,"sort_order":1,"stored_component_row_version":3},{"component_public_id":null,"component_text":"Freitext","current_component_row_version":null,"sort_order":2,"stored_component_row_version":null}],"item_row_version":7,"label_mode":"manual","labels":[{"code":"L1","name":"Hausgemacht"}],"origin_mode":"auto","origins":[{"country_code":"CH","ingredient":"Rind","text":"Rind: CH"}]}
  ```

  Erwarteter Token ist exakt
  `sha256:b3526f90550974218338f0f890d8f02a524cfad0dee40ae387074883691e7428`.
- Eine einzige globale Lock-Hierarchie gilt überall:
  `menu_weeks → menu_services → menu_items → menu_components →
  menu_item_components → publication_revisions`. Jede Transaktion sperrt den
  kompletten Mehrzeilen-Satz einer Klasse, bevor sie zur nächsten Klasse
  übergeht. Innerhalb einer Klasse ist die Reihenfolge exakt: Wochen
  `(location_id,profile_id,week_start,id)`, Services
  `(menu_week_id,service_date,meal_period_id,id)`, Items numerische `id ASC`,
  Komponenten numerische `id ASC`, Links `(menu_item_id,sort_order)` und
  Publikationen `(menu_week_id,id)`. Caller-, Formular- oder Assignment-
  Reihenfolge darf das nie verändern; alle Locks bleiben bis Commit/Rollback.
- Die Lock-Modi je Operation sind verbindlich: Header sperrt die Woche
  `FOR UPDATE`. Service sperrt Woche → Service → alle betroffenen Items
  `FOR UPDATE`. Item-Create/Update sperrt Woche → Service → Item `FOR UPDATE`
  und, falls Assignments ändern, die Komponentenmenge `FOR SHARE` → Links
  `FOR UPDATE`. Assign/Unassign/Replace sperren Woche → zugehörigen Service
  → Item → vollständige bestehende-plus-angeforderte Komponentenmenge
  `FOR SHARE` → Links `FOR UPDATE`. Review verwendet dieselbe Folge und
  sperrt Woche und Service vor dem Item; sein späteres
  `menu_weeks.updated_by` ist reentrant. Full
  Import/Recovery sperrt Woche → alle Services → alle Items → vollständige
  Komponentenmenge → alle Links. Publish sperrt Woche → alle Services → alle
  Items → vollständige Komponentenmenge → alle Links → aktive Publikationszeile.
  Copy sperrt Source- und Target-Woche gemeinsam in kanonischer Wochenordnung,
  danach alle relevanten Source-/Target-Services als vollständigen kanonischen
  Satz, alle relevanten Source-/Target-Items als vollständigen numerischen Satz,
  die Source-Komponentenmenge, Source-Links und zuletzt die aktive
  Target-Publikationszeile.
- Katalog-Update/Archive/Unarchive sperrt ausschließlich die Komponente
  `FOR UPDATE` sowie ihre Metadaten-Children und darf danach nie einen früheren
  Lock der Hierarchie erwerben; Create fügt nur seine neue Komponente/Children
  ein. Ein eigenständiger Withdrawal sperrt nur seine
  Publikationszeile und danach nie eine Woche. Publish darf die Capability vor
  der Transaktion ohne Lock nachschlagen; in der Transaktion sperrt und
  revalidiert es den aktiven Publikationszustand zuletzt.
- Für jeden Link-Writer umfasst die Komponentenmenge alle bestehenden,
  archivierten, beim Replace entfernten und neu angeforderten Referenzen;
  Freitext hat keine Komponenten-Zeile. Public IDs werden nur über Location
  plus `common`/aktuelles Profil aufgelöst; neue archivierte Komponenten sind
  unzulässig und interne Komponenten-IDs nie Caller-Input oder Output. Ein
  Multi-Item-Import/Recovery-Pfad sperrt alle Items, danach die vollständige
  Komponentenmenge und danach **alle vorhandenen Links aller Items**, bevor
  `replace_component_links_connection` erstmals läuft.
- `review_component(engine, scope, item_id, component_version,
  expected_item_row_version)` verwendet `component_version` als den obigen
  Pre-Review-Token. Es sperrt in genau einer Transaktion und in dieser stabilen
  Reihenfolge: (1) die scoped Woche per `FOR UPDATE`, (2) den zugehörigen
  scoped `menu_services`-Service per `FOR UPDATE`, (3) das scoped
  `menu_items`-Item per `FOR UPDATE`, (4) die unter
  diesem Item-Lock aus allen aktuellen Links ermittelten Komponenten —
  einschließlich archivierter — per numerischer `menu_components.id ASC FOR
  SHARE` und (5) alle aktuellen `menu_item_components`-Linkzeilen per
  `ORDER BY menu_item_id, sort_order FOR UPDATE`. Damit verwendet Review
  dieselbe `Woche → Service → Item → Komponenten → Links`-Reihenfolge und denselben kompatiblen
  Komponenten-Lock wie jeder Link-Writer; der Item-Lock verhindert während der
  Ermittlung und Tokenprüfung Phantom-Links. Alle Locks bleiben bis Commit oder
  Rollback.
- Erst nach allen Locks werden Scope, erwartete Item-`row_version`, aktuelle
  Komponenten-Versionen, effektive Auto-/Manual-Werte und Token aus den
  gesperrten Zeilen erneut gelesen und geprüft. Ein vorher gewinnender
  Concurrent-Write führt dadurch zu 409; ein späterer Write wartet. Fremder
  Scope liefert 404. Beide Antworten erfolgen ohne Teilmutation. Bei Erfolg
  rematerialisiert die Operation aktuelle Auto-Klassen, bewahrt jede manuelle
  Klasse byte-identisch, übernimmt aktuelle Komponenten-Versionen in die Links,
  aktualisiert `component_text` bei Kataloglinks aus dem aktuellen Katalognamen,
  lässt freie Texte byte-identisch, markiert danach geprüft, erhöht die
  Item-`row_version` exakt einmal und schreibt
  `menu_weeks.updated_by=scope.actor_id` reentrant unter dem bereits gehaltenen
  Wochen-Lock in derselben Transaktion. Sie liefert die neue Item-`row_version`;
  der HTTP-Handler antwortet per 303/PRG auf den
  scoped Menü-GET, der den neuen geprüften Zustand rendert.
- Der Engine-Level-One-Item-Full-Replace ist exakt
  `replace_component_links(engine: Engine, scope: AdminScope, item_id: int,
  assignments: Sequence[Mapping[str, object]], expected_item_row_version: int) -> int`. Er öffnet
  eine Transaktion, sperrt die scoped Woche, danach den zugehörigen scoped
  Service und erst danach genau das scoped Item, prüft dessen erwartete
  `row_version` und ruft den Connection-Helper auf, der Assignments validiert
  und alle Links ersetzt. Danach rematerialisiert die Engine-API die
  Auto-Klassen, setzt den Review-Status zurück, erhöht die Item-`row_version`
  exakt einmal und liefert die neue Version. Der Connection-Helper läuft in
  der Caller-Transaktion; er committet nie und ändert selbst weder Review- noch
  Item-Versionszustand.
- Jedes Element von `assignments` ist ein Mapping mit exakt den beiden Keys
  `component_public_id` und `component_text`; genau ein Wert ist nicht `null`.
  Beim Kataloglink ist `component_public_id` ein String und
  `component_text=null`; der Server speichert den aktuellen Katalognamen und
  die aktuelle Komponenten-`row_version`. Beim Freitext ist
  `component_public_id=null` und `component_text` ein String, dessen
  `btrim()`-Ergebnis nicht leer sein darf; gespeichert wird der ursprüngliche
  String byte-identisch. Unerwartete Keys, interne IDs, caller-gelieferte
  Versionen, Preise oder `sort_order` sind ungültig. Ausschließlich die
  Sequenzreihenfolge bestimmt den persistierten `sort_order` `1..n`.
- `assign_component` hängt atomar genau ein nach denselben Regeln validiertes
  Element an die bestehende geordnete Liste an. Unassign besitzt keine
  separate Mutationssemantik: Der Caller sendet die vollständige Zielliste an
  `replace_component_links` und lässt den entfernten Eintrag aus; `[]` entfernt
  alle Links. Doppelte neu angeforderte aktive Katalogkomponenten sind
  unzulässig. Bei bereits verknüpften archivierten Komponenten darf deren
  angeforderte Multiplizität den bestehenden Wert nicht übersteigen; dadurch
  entsteht nie eine neue archivierte Zuweisung.
- Ein erfolgreicher Assign/Unassign/Replace schreibt nur die Linkzeilen und
  das Item: Er rematerialisiert Auto-Werte, setzt dessen Review zurück und
  erhöht dessen `row_version` exakt einmal. Woche, Service und Komponenten
  bleiben unverändert; insbesondere wird keine Wochenversion erhöht. Fehler
  und Konflikte hinterlassen alle diese Zeilen unverändert.
- Verpflichtende Real-PG16-Race-Tests öffnen je zwei unabhängige Connections
  und synchronisieren sie kontrolliert ohne Timing-Sleeps. Ein Test lässt zwei
  `assign_component`-Aufrufe dasselbe scoped Item ändern; ein separater Test
  macht dasselbe über `replace_component_links`. Beide beweisen: kein
  Deadlock/`40P01`, der Verlierer wartet auf den Gewinner und liefert danach
  stale 409 ohne Teilmutation; der Endzustand enthält exakt die Gewinner-Links.
  Beide Aufrufe eines Race verwenden dieselbe erwartete Item-`row_version`;
  exakt einer gewinnt. Die `replace_component_links`-Tests beweisen zusätzlich,
  dass der Gewinner exakt `old_row_version + 1` zurückgibt, den Review-Status
  zurücksetzt, alle Auto-Effekte rematerialisiert und jede manuelle Klasse
  byte-identisch erhält.
- Ein eigener Multi-Item-Test verwendet ausschließlich einen echten
  Full-Import/Recovery-Transaktionspfad. Dieser sperrt vor jedem Aufruf des
  Connection-Helpers die Woche und alle Services, löst alle betroffenen Items
  vorab auf, sperrt sie nach
  numerischer `menu_items.id ASC` und sperrt danach die vollständige
  Komponenten-Vereinigungsmenge nach numerischer `menu_components.id ASC`.
  Zwei Connections reichen dieselben zwei scoped Items mit umgekehrter
  Item-/Assignment-Reihenfolge und derselben erwarteten Version ein. Der Pfad
  sperrt alle bestehenden Linkzeilen beider Items global geordnet, bevor der
  erste Helper läuft. Ohne Timing-Sleeps beweist der Test die globale
  Woche-/Service-/Item-/Komponenten-/Link-Lock-Reihenfolge, kein Deadlock/`40P01`, exakt einen
  Gewinner und einen stale-409-Verlierer mit null Mutation. Keine Single-Item-
  oder erfundene Task-4-Batch-API wird dabei als Multi-Item-Transaktion
  dargestellt.
- Ein direkter Test des Connection-Helpers läuft in genau einer vom Caller
  kontrollierten Transaktion und beweist, dass der Helper selbst weder committet
  noch Item-, Review- oder Versionszustand verändert.
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
- Publish sperrt vor der Snapshot-Erzeugung die Woche, alle Services in
  kanonischer Ordnung, alle scoped Items nach numerischer
  `menu_items.id ASC FOR UPDATE`, danach die vollständige Komponentenmenge nach
  numerischer `menu_components.id ASC FOR SHARE`, alle Linkzeilen global nach
  `(menu_item_id, sort_order) FOR UPDATE` und zuletzt die aktive
  Publikationszeile. Unter diesen Locks revalidiert es Publikationszustand,
  Reviewstatus und gespeicherte/aktuelle Versionen und
  wendet den zentralen `review_open/needs_review`-Predicate an. Erst dann darf
  es den unveränderlichen Snapshot bauen.
- Synchronisierte Real-PG16-Races verwenden Barrieren/Events statt Timing-
  Sleeps und testen beide Gewinnerreihenfolgen für Katalogedit gegen Assign,
  Unassign, Review und Publish, außerdem Review gegen Publish, Partial Save
  gegen Publish sowie Copy gegen Source-Save, Target-Save und Target-Publish.
  Sie beweisen: kein `40P01`, kein gemischter Zustand, keine Teilmutation und
  der Verlierer blockiert am kanonischen Wochen-Lock, sofern beide Operationen
  eine Woche sperren. Eine gemeinsame `common`-Komponente über Profile und
  Wochen verändert beim Edit keine Item-/Wochenzeile; Review heilt genau ein
  Item und bewahrt Manual-Werte byte-identisch. Publish-vor-Edit bewahrt den
  alten unveränderlichen Snapshot, Edit-vor-Publish blockiert Publish, und
  persistiertes `checked` überstimmt nie einen Versions-Mismatch. Die bereits
  vorgeschriebenen Assignment- und Import/Recovery-Races bleiben bestehen.

## 5. Migration und Rückwärtskompatibilität

Migration `0010_v12_to_v13` bleibt einschließlich ihrer registrierten Checksum
byte-identisch; auch `0001` bis `0009` bleiben unverändert. Die neue,
transaktionale und idempotente Migration `0011_v13_to_v14` installiert den
oben definierten SECURITY-DEFINER-Helper und aktualisiert `SCHEMA_VERSION 14`,
`APPLICATION_VERSION dishboard-schema-v14`, Registry-Eintrag `0011`,
Schema-/Package-Validatoren, SECURITY-DEFINER-Allowlist sowie Checksums und
Manifeste. Fresh Schema, v13→v14-Migration und Restore müssen denselben
Funktions-Owner und dieselben restriktiven ACLs ergeben.
`database/permissions.sql` erteilt den App-/Backup-Rollen ACLs für alle drei
neuen Tabellen sowie die erforderliche `menu_components`-Sequence und wird in
der bestehenden Restore-Reihenfolge erneut angewendet. Es entfernt bei jedem
Lauf idempotent etwaige breite Execute-/Master-Rechte, gewährt für den Helper
ausschließlich `cafeteria_app` `EXECUTE` und gewährt keiner App-Rolle
Master-`UPDATE`. Legacy-Backfill gehört ausschließlich in Migration `0010`,
nie nach `db.py`: `0010` erstellt zuerst die
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

`workflow_partial_store.py` definiert den privaten, unveränderlichen
`WeekRef(week_id,location_id,profile_code,week_start,row_version)` sowie die
scoped Resolver `resolve_week_ref(connection, scope, week_start, *,
for_update=False) -> WeekRef` und `resolve_item_id(connection, scope, week_ref,
day, meal, option, *, for_update=False) -> int`. Beide Resolver sind
nichtoptional und lösen ausschließlich vorhandene, scoped Daten auf: Eine
fehlende Woche oder ein fehlendes Item ist immer 404; sie liefern weder `None`
noch Sentinel noch ein virtuelles Objekt und erzeugen keine Zeile. Für den
Menü-GET existiert getrennt davon ein internes reines Rendering-Modell für
einen gültigen fehlenden Raster-Slot. Es enthält `row_version=0`, aber keine
interne Woche-, Service- oder Item-ID, und ist keine neue öffentliche Store-
API. Nur die oben definierten Engine/AdminScope-Write-APIs dürfen bei
`expected_*_row_version=0` fehlende Zeilen unter der kanonischen Lock-
Hierarchie erzeugen. Die Resolver validieren ISO-Montag, ISO-Tag im
Wochenraster, `LUNCH|DINNER`, das `staff_guest`-Lunch-only-Raster,
`MENU_1|VEGGIE`, Location und URL-abgeleitetes Profil. Routes leiten Wochen-
und Item-Identität ausschließlich daraus ab; Formulare dürfen weder `week_id`
noch `item_id` oder eine andere interne ID liefern.

CSV-Full-Import behandelt jede Komponente ausschließlich als Freitext und
setzt `allergen_mode`, `origin_mode` und `label_mode` für jedes importierte
Item exakt auf `manual`; er erzeugt oder bindet keine Katalogkomponente. Hat
die Zielwoche vor dem Replace irgendwo bereits eine Zuweisung mit
`component_id IS NOT NULL`, scheitert der gesamte Full Import unter den
kanonischen Locks atomar mit 409. Es gibt dafür weder ein destruktives
Bestätigungsfeld noch einen Confirm-Override. Recovery ist davon getrennt und
darf Katalogzuweisungen ausschließlich über öffentliche Component-UUIDs
wiederherstellen; auch Recovery akzeptiert nie interne Komponenten-IDs und
verwendet den gemeinsamen Assignment-Helper.

Task 6 darf `workflow.py` seriell nur für den bestehenden Import-/Recovery-
Adapter sowie für die explizite Projektion zwischen internem Payload und
öffentlichem Draft-/Snapshot-Contract ändern. Publish-, Review- und Status-
Logik in `workflow.py` gehört nicht zu Task 6.

Komponenten-Create akzeptiert exakt die skalaren Felder
`_csrf,category,name,origin_country_code,target_scope`, wiederholtes
`label_code` sowie paarweise wiederholtes `allergen_code,allergen_presence`.
Komponenten-Update akzeptiert den identischen vollständigen Metadaten-Payload
plus skalares `row_version`, aber kein `target_scope`. Archive und Unarchive
akzeptieren jeweils exakt `_csrf,row_version`. Alle vier Parser verwerfen
doppelte skalare Keys, ungleich lange Allergen-Arrays und jeden unerwarteten
Key; ausdrücklich verboten sind `profile`, `profile_scope`, interne IDs und
Master-IDs.

Create nimmt programmatisch Kategorie, Name, Herkunft, `target_scope`, eine
`label_codes`-Sequence und eine `allergens`-Sequence aus
`(code, contains|may_contain)` entgegen. Update nimmt den vollständigen
entsprechenden Metadaten-Payload plus erwartete Version. Doppelte, unbekannte
oder ungültige Codes/Presence-Werte werden vor jedem Delete zurückgewiesen.
Neue Child-Links erfordern aktive Masterzeilen. Bereits verlinkte inaktive
Master dürfen unverändert erhalten bleiben, aber weder neu hinzugefügt noch in
ihrer Presence geändert werden. Parent und Children schreiben atomar und
erhöhen die Komponenten-Version bei einer Änderung exakt einmal; ein zum
gespeicherten Zustand byte-identischer vollständiger Payload ist ein echter
No-op und behält die Version. Die private Auflösung und Validierung liegt in
`component_catalog_metadata.py`, damit die Produktionsmodule jeweils unter
400 Zeilen bleiben.

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
| `POST /admin/{cafeteria\|patienten}/komponenten` | exact `_csrf,category,name,origin_country_code,target_scope` plus repeated `label_code,allergen_code,allergen_presence` |
| `GET /admin/{cafeteria\|patienten}/komponenten/<public_id>` | Komponente anzeigen |
| `POST /admin/{cafeteria\|patienten}/komponenten/<public_id>` | exact `_csrf,category,name,origin_country_code,row_version` plus repeated `label_code,allergen_code,allergen_presence`; kein `target_scope` |
| `POST /admin/{cafeteria\|patienten}/komponenten/<public_id>/archive` | exact `_csrf,row_version`; archivieren, keine Löschung |
| `POST /admin/{cafeteria\|patienten}/komponenten/<public_id>/unarchive` | exact `_csrf,row_version`; reaktivieren, Name bleibt reserviert |
| `GET /admin/{cafeteria\|patienten}/copy?week=` | leere Zielwochen anbieten |
| `POST /admin/{cafeteria\|patienten}/copy` | `_csrf,source_week,target_week,target_row_version` |
| `GET /admin/{cafeteria\|patienten}/preview?week=` | zuletzt gespeicherten Draft anzeigen |
| `POST /admin/{cafeteria\|patienten}/publish` | `_csrf,week,row_version` exakt; Publish |

Die Komponentensuche für eine Zuweisung zeigt nur aktive Komponenten mit
`common`- oder passendem Scope; die Katalogverwaltung darf mit
`include_archived=1` zusätzlich archivierte Komponenten anzeigen. Katalog-CRUD,
Zuweisung, Copy und Publish erzwingen Location- und Scope-Isolation.
Die route-unabhängige Implementierung liegt in `workflow_copy_store.py`.
Die exakte API ist `copy_previous_week(engine: Engine, scope: AdminScope,
target_week_start: date, target_row_version: int) -> int`. Quelle ist der
neueste committed gespeicherte Draft der Vorwoche, also exakt Ziel-Montag minus
sieben Tage, in derselben Location und demselben URL-abgeleiteten Profil; es
gibt keinen Source-Token. Eine abweichende übermittelte `source_week` wird als
400 zurückgewiesen. Der Store leitet die Quelle aus dem Ziel ab und akzeptiert
keine internen IDs.

Copy übernimmt `title` und `shared_note`, setzt die Zielwoche auf `draft` und
kopiert nie Source-IDs, `public_id`, Versionen, Zeitstempel, Workflow-State oder
Actors. Bei einem item-freien vorhandenen Target ersetzt es dessen Service-
Skeleton vollständig. Services übernehmen `service_state`, Notice und
Meal-Period mit Datum +7, erhalten aber neue IDs/Public-IDs und Version 1.
Items übernehmen Menu-Type, `dish_template_id`, Titel, Beschreibung, Note,
`sort_order` und alle drei Modi, erhalten aber neue IDs/Public-IDs, eine zum
Target gehörige `external_id` und Version 1. Jeder Review ist `not_checked`.

Aktive Kataloglinks werden unter Komponenten-Locks neu aufgelöst und als neue
Assignments mit aktuellem Namen und aktueller Version geschrieben. Ein stale
aktiver Source-Link wird sicher rebased, bleibt aber ungeprüft; ein archivierter
Source-Link macht den gesamten Copy atomar 409. Freitext bleibt byte-identisch.
Manuelle Metadaten werden für jede manuelle Klasse byte-semantisch kopiert;
Auto-Metadaten werden unter den Komponenten-Locks neu berechnet und nie
geklont. `staff_guest` übernimmt interne/externe Rappen und Currency;
`patient` erzeugt keinerlei Preis. Ein anomaler Patientenpreis in der Quelle
ist 409.

Copy übernimmt weder Publikationen noch Lifecycle-State. Eine aktive
Target-Publikation ist 409; withdrawn Target-Historie bleibt unberührt.
`target_row_version=0` plus fehlendes Target erzeugt Version 1 und liefert 1;
0 plus vorhandenes Target ist 409; positive Version plus fehlendes Target ist
404; exakt positives `v` plus vorhandenes item-freies Target ohne aktive
Publikation aktualisiert die Woche einmal und liefert `v+1`. Stale, nichtleere
oder anderweitig ungültige Targets scheitern ohne Teilmutation. Zwei Copies mit
derselben Erwartung haben exakt einen Gewinner. Copy gegen den ersten
Target-Item-Save liefert einen vollständigen Gewinnerzustand ohne Hybrid.

Null oder mehrere konfigurierte aktive Locations werden für jede betroffene
HTTP-Operation einheitlich als 503 abgebildet. Eine fehlende scoped Woche, ein
fehlender gespeicherter Draft oder eine nicht vorhandene Preview-Ressource
liefert als angeforderte gespeicherte Ressource 404; der Menü-GET für einen
gültigen Raster-Slot einer noch fehlenden Woche ist dagegen die oben definierte
virtuelle Version-0-Zeile. Ungültige/out-of-scope Slots und Scope-Leaks werden
als 404 maskiert.

## 7. Preview, Save, Publish und Fehlertexte

Preview zeigt ausschließlich den LAST-SAVED-Zustand einer vorhandenen scoped
Woche, nie Dirty-Client-State. Sie ist für jeden persistierten DB-Workflow-
State `draft|ready|published|archived` verfügbar; eine fehlende Woche ist 404.
`draft.read` ist erforderlich. Preview ist Admin-only, nicht Signage/Public,
öffnet per `target="_blank"`, trägt einen eindeutigen PREVIEW-Banner und hat
keinen Fallback auf Live-Daten oder den aktiven Publikationssnapshot.
`no-store` ist Pflicht. Dirty-State blockiert Preview und Publish bis zum
Speichern.

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
| reale PG16-Migrationen, Grants, Schema 14, unveränderte 0010-Checksum, Backfill-/Terminator-Contract | `reference_scaffold/tests/test_component_catalog_migration_db.py`, `reference_scaffold/tests/test_auth_database.py`, `reference_scaffold/tests/test_database_invariants.py` |
| schmaler Metadata-Master-Lock: Owner/ACL, feste Search-Path, Lock-Reihenfolge, App-Caller-Validierung, Fresh/Migration/Restore-Parität | `reference_scaffold/tests/test_component_metadata_master_lock_db.py`, `reference_scaffold/tests/test_component_catalog_migration_db.py`, `reference_scaffold/tests/test_auth_database.py`, `reference_scaffold/tests/test_database_invariants.py` |
| Katalog CRUD/Archiv/Suche/Usage, atomare Label-/Allergen-Metadaten, No-op und Isolation | `reference_scaffold/tests/test_component_catalog_db.py`, `reference_scaffold/tests/test_component_catalog_metadata_db.py`, `reference_scaffold/tests/test_component_catalog_routes.py` |
| exakte Komponenten-Zuweisungsmappings, Append/Full-Replace-Unassign, Duplikat-/Archiv-Multiplizität, Lock-Reihenfolge, Allergie-Union/contains, deterministische Herkunft und Diet-Intersection | `reference_scaffold/tests/test_component_assignment_db.py`, `reference_scaffold/tests/test_component_assignment_races_db.py` |
| Location/Profile-Isolation und Public-ID/404 | `reference_scaffold/tests/test_public_isolation_homoglyphs.py`, `reference_scaffold/tests/test_database_invariants.py` |
| exakter immutable Snapshot, Golden-Hash-Token, Lock-Reihenfolge und Concurrent-/Repeat-Review | `reference_scaffold/tests/test_admin_workflow_concurrency_db.py`, `reference_scaffold/tests/test_admin_workflow_review_db.py`, `reference_scaffold/tests/test_admin_workflow_snapshot_contract.py` |
| virtuelle/absente/partielle/geschlossene Slots, exakte Item-Versionen und Same-/Different-Slot-Races | `reference_scaffold/tests/test_workflow_partial_store_db.py` |
| exakte Vorwochen-Copy, absent/existing-empty Target-Version, Lock/409, neue IDs | `reference_scaffold/tests/test_workflow_copy_store_db.py`, `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_workflow_form.py` |
| LAST-SAVED Preview, no-store, Dirty-Guard | `reference_scaffold/tests/test_admin_draft_preview.py` |
| Publish/PRG/Review/Stale/CSRF/400/409 | `reference_scaffold/tests/test_admin_workflow_routes.py`, `reference_scaffold/tests/test_workflow_form.py` |
| CHF Parsing/Rappen/Patient-Preisverbot und Wochen-Familien | `reference_scaffold/tests/test_admin_week_routes.py` |
| servergerenderte 28/10-Raster, Katalogzustand, deutsche Labels und PREVIEW-Banner | `reference_scaffold/tests/test_rendered_ui.py` |
| Browser-A11y und Viewport-Matrix | `reference_scaffold/tests/test_admin_ux_browser.py` (neu erstellt durch Wiederverwendung der bestehenden Playwright-Muster/Fixtures aus `test_rendered_ui.py`) |

Gates mit verbatim Receipts: vollständiges `pytest`, reale PG16-
Compose-/Migrationsprüfung, Schema- und Package-Validatoren, Ruff, Bandit,
Secret-Scan, GitNexus `detect_changes`, OCR-Review sowie unabhängige AGY- und
Grok-Reviews. Browser: Chromium und vorhandene CI-Browser bei allen vier
Viewports, Tastatur/Fokus, Fehler/Retry, Copy/Preview/Publish.
Der finale OCR-Lauf vergleicht ausschließlich die Implementation gegen den
akzeptierten Plan:
`rtk ocr review --repo /nvmetank1/projects/menuplan --from docs/admin-redesign-plan-v1 --to feat/admin-redesign-impl-v1 --format json --audience agent`.
Die finale Eigentumsprüfung lautet exakt
`rtk claude-wp-verify --branch feat/admin-redesign-impl-v1 --base docs/admin-redesign-plan-v1`.
Kein finales Gate darf nur den Docs-Branch prüfen.

Deployment-Gate: Backup-ID, Migration auf Schema 14, unveränderlicher
Image-Digest, Healthcheck, authentifizierter Admin-Smoke, Screenshots und
Proof-ZIP; anschließend dokumentierter Rollback-/Restore-Probe. Kein Gate darf
durch „alle Tests pass“ ohne Kommandoausgabe ersetzt werden.

## 10. Umsetzungseigentum und Stop-Bedingungen

Phase 1 (Schema, 0010, Grants, Validator), Task 3 und Task 3a (Schema 0011,
schmaler SECURITY-DEFINER-Lock, Grants, Validator) sowie Phase 2 (Store, Modelle,
Inheritance) werden seriell am gemeinsamen Contract bearbeitet.
Task 1 ist bis zum Abschluss von T3 alleiniger Owner von `database/schema.sql`
und `reference_scaffold/cafeteria/db.py`; danach übernimmt T3a diese Dateien
seriell für Schema v14. Task 2 verändert und staged ausschließlich seine beiden
Testdateien. T3b startet erst nach dem committed T3a-Receipt und verwendet den
Helper, ohne Schema oder Grants zu ändern.
`component_assignment_store` und `component_effects` sind ausschließlich T4
zugeordnet; `workflow_review.py` ist ausschließlich T5 zugeordnet.
`workflow.py` gehört seriell T4, danach T5, T6 und T8; T6 darf
dort ausschließlich Import/Recovery-Adapter und private/öffentliche Payload-
Projektion ändern, nicht Publish, Review oder Status.
`workflow_store.py` hat T6 als einzigen seriellen Owner und erhält dort nur
minimale Kompatibilitätsedits für Full-Import/Recovery (kein Partial-Write und
kein Full-Replace aus Partial-Modulen). Phase 3
(Routen/Workflow/Publish) folgt erst nach Contract-Receipt. Phase 4
(Jinja/Vanilla JS/CSS) folgt danach; Test- und Review-Lanes dürfen parallel
lesen, aber niemals dieselben Dateien schreiben. CSV-Import bleibt vollständig
Freitext plus drei Modi `manual`; jede vorhandene Katalogzuweisung im Ziel
blockiert den Full Import atomar mit 409, ohne destruktiven Confirm. Recovery
darf öffentliche Component-UUIDs verwenden. Bei fehlendem
Backup, unklarem Scope, stale Version, nicht bestandenem HIGH/CRITICAL-Review
oder fehlender Auth-/Browser-Evidenz: BLOCKED, kein Push/Deploy.

Tasks 7, 8 und 9 bilden eine einzige serialisierte Integrationswelle. Nachdem
Task 7 Legacy-Routen entfernt oder deaktiviert, darf weder ein Zwischenstand
als Full-Suite-grün noch als deploy-ready bezeichnet werden, bis Task 8 die
Publish-/Statussemantik und Task 9 die zugehörigen servergerenderten
Oberflächen vollständig integriert haben. Erst danach sind Full-Regression-
und Deployment-Gates zulässig.

## 11. Selbstprüfung

Diese SDD enthält keine ungelösten oder undefinierten Anweisungen und keine
pauschale „alle Tests pass“-Behauptung. Patient-Raster, Cafeteria-Raster, Preisregeln,
Full-Replace-Ausnahme, drei Modi, Preview-Quelle und Publish-Guards sind
explizit getrennt; `dish_templates` bleibt unangetastet. Jede Implementierung
muss die oben genannten exact keys, Statuswerte, Fehlercodes und named
Receipts liefern.
