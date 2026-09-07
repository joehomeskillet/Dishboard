# REC R1: verbindliche Ergänzungen und Servicevertrag

Root-Freigabe 07.09.2026, WP wp-c9f66fa61496. Ergänzt den BAS/REC-Datenvertrag
vom 06.09.; bestehende B2-Regeln bleiben unverändert. R1 besitzt vollständig
M-B, Migration `0019_v21_to_v22.sql`. Kein Menübezug, Import oder R2-UI.

## Fachliche Ergänzungen

- Nur `description` und `instruction` sind mehrzeilig: NFC, CRLF/CR zu LF,
  äußeren Whitespace entfernen, innere LF erhalten; andere Unicode-C-Zeichen
  und `<`/`>` ablehnen. Andere Texte behalten die einzeilige BAS-Regel.
- Titel/Gruppenlabel 120, Zutatenfreitext/Notiz 500, Beschreibung 2000,
  Anleitung 8000 Zeichen. Maximal 64 Zutaten/Schritte/Tags/Bilder je Rezept.
  Minuten sind Integer 0..10080 oder NULL, nie bool.
- Ausbeute verwendet jede aktive existierende Einheit. Spätere UI nennt sie
  „Ausbeute/Menge“. Skalieren ausschließlich als Verhältnis derselben Einheit;
  keine kg-zu-Portion-Ableitung.
- Festschreiben eines identischen vollständigen Snapshots ergibt 409 ohne
  Audit/Version. Geänderte eingefrorene Foodfaktoren erlauben eine neue Revision.
  Bereits bestehende archivierte Referenzen dürfen erhalten bleiben; neue
  archivierte Zuordnungen ergeben 409. Archivierte Rezepte sind nur reaktivierbar.
- Titel sind nicht eindeutig. Quellen sind unveränderlich; manuelle Eingaben
  erfinden keine Fremdquelle oder bestätigte Allergen-/Kostformaussage.

## Öffentliche Python-Imports

`recipe_store` ist die Service-Fassade; `recipe_types` besitzt immutable DTOs
und Fehler. Bestehende `ActorExpectation`, `ObjectExpectation`, `MutationResult`
aus IAM/B2 werden unverändert verwendet. Einheiten bleiben Codes, andere
Referenzen UUIDs. Listen sind Tupel; JSON in DTOs rekursiv immutable.

Alle Writes haben zusätzlich das verpflichtende keyword-only
`expected_location_id: int`: originaler **serverseitig ermittelter** Standort
des Formular-/Command-Kontexts, nicht eine autorisierende Clientauswahl.
SQL prüft ihn nach dem Actor-Guard unter Standort-Sperre gegen den einzigen
aktiven Standort. Kein Nachladen einer neuen Actor-/Objekt-/Standorterwartung.
`get_location(engine) -> int` dient diesem internen Kontext, nicht einem neuen
öffentlichen HTTP-Feld. DTOs enthalten keine internen Objekt-IDs.

```text
get_location(engine) -> int
list_recipes(engine, *, include_archived=False, search=None, limit=200, offset=0) -> tuple[RecipeDTO,...]
get_recipe(engine, public_id) -> RecipeDTO
create_recipe(engine, actor, payload, *, expected_location_id) -> MutationResult
update_recipe(engine, actor, target, payload, *, expected_location_id) -> MutationResult
set_recipe_active(engine, actor, target, *, active, expected_location_id) -> MutationResult
freeze_revision(engine, actor, target, *, expected_location_id) -> RevisionResult
get_revision(engine, public_id) -> RecipeRevisionDTO
list_revisions(engine, recipe_public_id, *, limit=50, offset=0) -> tuple[RecipeRevisionSummaryDTO,...]
add_recipe_image(engine, actor, target, *, data, content_type, caption=None,
                 source_url=None, source_license=None, fetched_at=None,
                 expected_location_id) -> MutationResult
get_recipe_asset(engine, recipe_public_id, sha256) -> RecipeAssetDTO
list_cookbooks(engine, *, include_archived=False, limit=200, offset=0) -> tuple[CookbookDTO,...]
get_cookbook(engine, public_id) -> CookbookDTO
create_cookbook(engine, actor, *, name, description=None, expected_location_id) -> MutationResult
update_cookbook(engine, actor, target, *, name, description=None, expected_location_id) -> MutationResult
set_cookbook_active(engine, actor, target, *, active, expected_location_id) -> MutationResult
replace_cookbook_recipes(engine, actor, target, recipe_public_ids, *, expected_location_id) -> MutationResult
```

`list_revisions` ergänzt den Vertrag in WP wp-d8105af574dc: eingefrorene Summary-DTOs
mit public_id,recipe_public_id,revision_number,content_hash_sha256,created_at,created_by;
kein Snapshotfeld und kein Laden vollständiger Snapshots für die Liste. Ein gemeinsamer
READ ONLY/REPEATABLE READ-Stand prüft zuerst das Rezept im aktiven Standort, auch wenn
archiviert. Fehlender/fremder Parent ergibt RecipeNotFoundError; vorhandener Parent ohne
Revisionen ergibt (). Sortierung revision_number DESC,public_id, vorhandene Pagingprüfung
(limit 1..500, offset >=0, echte Integer). Fassade safe + draft.read; get_revision unverändert.

Rezept-Payload ist ein vollständiger Aggregate-Replace mit exakt diesen Feldern:
`title`, `description`, `servings`, `servings_unit_code`, `prep_minutes`,
`cook_minutes`, `source`, `ingredients`, `steps`, `tag_public_ids`, `images`.
`source`: `kind`, `reference`, `url`, `note`, `fetched_at`; nur manual/url/file_import/ai_assisted.
Zutaten: `line_public_id`, `group_label`, `ingredient_text`, `food_public_id`, `quantity`, `unit_code`,
`note`, `source_kind`, `source_reference`, `fetched_at`.
Schritte: `instruction`, `duration_minutes`, `image_sha256`.
Bilder: `sha256`, `caption`, `source_url`, `source_license`, `fetched_at`.
Jedes Feld ist explizit vorhanden; optionale Werte sind None, Listen leer statt
fehlend. Array-Reihenfolge definiert lückenlos1..n. Tags sind eindeutige UUIDs.
Root-Ergänzung: Zutaten erhalten stabile `line_public_id` (UUID), unique pro
Rezept; PK(recipe_id,sort_order) bleibt. Bestehende Zeilen führen diese UUID
mit, neue ausschließlich None; SQL vergibt die UUID. Fremde/unbekannte und
doppelte UUIDs werden abgelehnt. Ursprung hängt an dieser Identität, niemals
am Arrayindex: Umsortieren/Einfügen und Mengen-/Food-/Textänderung erhalten ihn.
Ausdrückliches Entfernen löscht die Entwurfszeile, Revision/Audit bleiben erhalten.
RezeptDTO enthält public_id,row_version,active und den vollständig lesbaren
Payload. RevisionResult enthält public_id (Revisions-UUID), recipe_public_id,
revision_number, recipe_row_version, content_hash_sha256. RecipeRevisionDTO
ergänzt snapshot,created_at,created_by. AssetDTO enthält sha256,data,content_type,
width,height. CookbookDTO enthält public_id,row_version,name,description,active,
recipe_public_ids in gespeicherter Reihenfolge.

Mengen/Portionen werden über B1 geprüft und dezimalverlustfrei übertragen.
Archivierte Referenzen werden unter Sperre mit den vorher vorhandenen
Referenzen desselben Aggregats verglichen; beliebige fremde Archiv-IDs sind
keine gültige „bestehende“ Zuordnung. Quellen pro bestehender Zeilen-UUID
bleiben erhalten; geordnete Zeilen dürfen nicht unbemerkt Fremdherkunft verlieren.

## Sicherheits-/Snapshotvertrag

Lesen draft.read; jeder Write recipe.write, in Python und SQL. Öffentliche
Mutatoren wählen ihre Fähigkeit literal; interne Dispatcher/Guards bleiben
PUBLIC/App/Auth-Issuer entzogen. Keine direkte App-DML. SQLSTATE-Mapping wie
B2:400 Validierung,401 StaleActor,403 ActorDenied,404 unbekannt,409 Konflikt,
503 Ausfall/Konfiguration. Fehlerklassen: RecipeValidationError,
RecipeNotFoundError,RecipeConflictError,RecipeStaleActorError,
RecipeActorDeniedError,RecipeConfigurationError,RecipeUnavailableError.
Ausfallwrapper umfasst Session-/Capabilityprüfung; keine DB-Fehlerrekursion.
READ COMMITTED, Role FOR SHARE vor Actor FOR SHARE, dann Standort, Einheiten,
Vokabulare/Foods in ID-Reihenfolge vor Rezept/Kochbuch FOR UPDATE. Unterzeilen,
ein Versionsbump und ein Audit committen gemeinsam. Normales identisches Save
bleibt No-op; aktive Zustandsaktionen müssen wechseln.
Revisionssnapshot Version 1 enthält den vollständigen kanonischen Inhalt,
damalige Einheitenmetadaten/Foodnamen/-versionen/Faktoren/Herkunft, Bildhashes
und B1-Rechenvertrag. Keine mutable Kopfversion/Aktivstatus/Zeitstempel im
Inhaltshash: erneutes Festschreiben allein erzeugt keinen anderen Inhalt.
Kanonisierung ist PostgreSQL-16-`jsonb::text`, SHA-256 über dessen UTF-8-Bytes;
Decimalwerte stehen als `trim_scale(numeric)::text` ohne Exponenten im Snapshot.
UPDATE/DELETE/TRUNCATE von Revisionen und Assets verboten. Bildbytes PNG/JPEG,
höchstens 1 MiB, SHA256/MagicBytes selbstkonsistent, standortgebunden; Auslieferung
nur über berechtigte Rezept-/Revisionszuordnung, keine globale Hashsuche.
Entfernen eines Entwurfsbildes hebt seine Berechtigung in erhaltenen Revisionen
desselben Rezepts nicht auf. Aggregate-Replace erhält die ursprüngliche Bildquelle,
Lizenz und Abrufzeit; Bildunterschrift und Reihenfolge sind bearbeitbar. Audit
erhält ursprüngliche und neue Zutaten-/Bildzuordnungen einschließlich Herkunft.
Ein Hash identifiziert genau eine Bildzuordnung pro Rezept; doppelte Hashes im
Aggregat ergeben atomar 400/`P1901`. Anhängen prüft Quelle, Lizenz und Abrufzeit
gegen Entwurf und Historie desselben Rezepts; Abweichungen ergeben 409/`55000`.
Ein aktuell zugeordneter Hash mit identischer Herkunft und Bildunterschrift ist
ein echter No-op ohne Versions-/Auditänderung; abweichende Bildunterschriften
beim Anhängen ergeben 409 und werden ausschließlich per Aggregate-Edit geändert.
Ein nur historischer Hash darf mit ursprünglicher Herkunft und neuer Bildunterschrift
wieder angehängt werden (Version/Audit ändern sich). Andere Rezepte behalten bei
eigenem Upload derselben Bytes ihre unabhängig erfasste Herkunft.
Ungültige Standortkonfiguration ergibt `P1904`/503; ein inzwischen anderer
einziger aktiver Standort ergibt 409 gegen die ursprüngliche Erwartung.
Nach fachlichen Writes kein Drop/älterer Daten- oder IAM-Restore als Rollback.
Nur schema-kompatibler Forward-Fix. R1 allein ist keine REC-001-Gesamtabnahme.
