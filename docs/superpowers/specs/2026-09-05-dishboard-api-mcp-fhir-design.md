# SDD: Dishboard REST-API v1, FHIR-R5-Schnittstelle, MCP-Server und API-Schlüssel

Stand 2026-09-05. Basis: Branch `integrate/admin-ux-next-0905` (Schema v16, Tabler-Admin-Shell).
Diese Spezifikation ist der eingefrorene Vertrag für die Work-Packages A1, A2, B, C, D, E, F und G.
Abweichungen nur mit Spec-Update im selben Commit.

## 1. Ziel, Grenzen, Nicht-Ziele

Ziel: Dishboard bekommt eine dokumentierte REST-API (OpenAPI 3.1 + selbst gehostetes Swagger UI),
eine FHIR-R5-Leseschnittstelle für publizierte Menüpläne, einen MCP-Server für LLM-Clients sowie
API-Schlüssel, die im Admin unter `/admin/api` erstellt, angezeigt und widerrufen werden.

Unveränderliche Regeln (aus SDD v3.0 und Admin-Redesign-SDD):

- Patientenkanal enthält nie Kosteninformationen. Das gilt für JSON, FHIR und Fehlertexte.
- Öffentliche Routen lehnen Query-Parameter ab (400, `Cache-Control: no-store`).
- CSP `script-src 'self'`: keine Inline-Skripte, keine Inline-Handler, keine `style=`-Attribute in
  Templates, keine externen CDNs. Vendor-Assets werden gepinnt und per SHA-256 verifiziert.
- Least Privilege in PostgreSQL: `cafeteria_app` schreibt sicherheitsrelevante Zustände nur über
  `SECURITY DEFINER`-Funktionen; Audit-Ereignisse sind unveränderlich.
- Keine neue Laufzeit-Dependency für die Flask-App. Der MCP-Server ist ein separater Prozess mit
  eigener `requirements-mcp.txt`.

Nicht-Ziele (bewusst nicht in dieser Welle): schreibende API-Endpunkte (Drafts anlegen, publizieren),
FHIR-Schreibzugriffe, OAuth2, Ratenbegrenzung pro Schlüssel, SNOMED-/LOINC-Mappings, FHIR-Suche
über `_include`/`_sort`, MCP-Streamable-HTTP im Container.

## 2. Basis und Koordination mit der parallelen Codex-Session

- Basis-Commit: Tip von `integrate/admin-ux-next-0905` zum Zeitpunkt des Worktree-Anlegens
  (`6f5204b` oder neuer). Alle WP-Branches zweigen von `docs/api-mcp-fhir-spec-0905` ab.
- Migration `0014_v16_to_v17.sql` ist für API-Schlüssel reserviert (WP-D). Codex nutzt ab `0015`.
- Codex besitzt: `templates/admin/_workflow_sidebar.html`, `_macros.html`, `base_tabler.html`,
  `static/admin-tabler.css`, `static/admin.js`, `tools/validate_package.py`, `admin/workflow_routes.py`.
  Diese Welle ändert diese Dateien nicht. Nav-Eintrag «API & Schnittstellen» in der Sidebar liefert
  Codex (Vertrag in §7.4).
- Diese Welle ändert an geteilten Dateien nur additiv: `cafeteria/__init__.py` (Blueprint-
  Registrierung), `cafeteria/db.py` (Schema-Version, Migrationsliste), `database/schema.sql`,
  `database/permissions.sql`, `database/validate_schema.py`, `database/README.md`,
  `tests/test_database_invariants.py` (Migrationsliste), `README.md` (Routentabelle).

## 3. REST-API v1

### 3.1 Struktur

Bestehend bleibt `cafeteria/api/routes.py` (Blueprint `api`, Prefix `/api/v1/published`,
Routen `/cafeteria` und `/patienten`, unverändert). Neu:

| Datei | Inhalt |
|---|---|
| `cafeteria/api/v1_routes.py` | Blueprint `api_v1`, Prefix `/api/v1`: `/status`, `/published/<channel>/today`, `/published/<channel>/days/<date>`, Fehlerhelfer, `status_payload()` |
| `cafeteria/api/openapi.py` | `build_openapi() -> dict` (OpenAPI 3.1.0, handgeschrieben, keine neue Dependency) |
| `cafeteria/api/docs_routes.py` | Blueprint `api_docs`, Prefix `/api/v1`: `/openapi.json`, `/docs` |
| `cafeteria/api/auth.py` (WP-G) | `require_api_scope(scope)`-Decorator, Bearer-Prüfung |
| `templates/api/docs.html`, `static/api-docs.js`, `static/vendor/swagger-ui/*` | Swagger UI |

Registrierung in `cafeteria/__init__.py` direkt nach `api_bp`:

```python
from .api.v1_routes import bp as api_v1_bp
from .api.docs_routes import bp as api_docs_bp
from .fhir.routes import bp as fhir_bp
app.register_blueprint(api_v1_bp)
app.register_blueprint(api_docs_bp)
app.register_blueprint(fhir_bp)
```

### 3.2 Gemeinsame Regeln für alle `/api/v1/*`-Routen

- `channel` ist exakt `cafeteria` (Profil `staff_guest`) oder `patienten` (Profil `patient`);
  Flask-Konverter `<any(cafeteria, patienten):channel>`. Mapping wie `admin/routes.py`.
- Jeder Query-String führt zu `400 {"error": "query_parameters_not_allowed"}` mit
  `Cache-Control: no-store` (`before_request` pro Blueprint, identisch zu `public.routes`).
- Fehlerformat immer `{"error": "<snake_code>", "detail": "<deutscher Text>"}` plus
  `Cache-Control: no-store`. Fehlertexte im Patientenkanal enthalten keine Kostenvokabeln.
- Erfolgreiche Antworten mit publizierten Daten: `Cache-Control: public, max-age=60, stale-if-error=86400`
  und `X-Snapshot-Revision: <revision_id>`. `/status` und `/openapi.json`: `Cache-Control: no-store`
  bzw. `public, max-age=300` für `openapi.json`.
- JSON via `flask.jsonify`, `ensure_ascii` bleibt Flask-Default.
- `effective_today()` aus `cafeteria.public.routes` ist die einzige «heute»-Quelle.

### 3.3 Endpunkte (öffentlich, ohne Schlüssel)

| Route | Antwort | Fehler |
|---|---|---|
| `GET /api/v1/published/{channel}` | bestehender Wochen-Snapshot (unverändert) | 404 `no_published_menu` |
| `GET /api/v1/published/{channel}/today` | `{"channel", "profile_code", "revision_id", "date", "day": <Day>}` für `effective_today()` | 404 `no_published_menu` |
| `GET /api/v1/published/{channel}/days/{date}` | wie `today` für das Datum; Snapshot über `active_snapshot(engine, profile, date, last_good_dir=…)` | 400 `invalid_date` (kein `YYYY-MM-DD` oder ungültiges Datum), 404 `no_published_menu` |
| `GET /api/v1/status` | siehe unten | – |
| `GET /api/v1/openapi.json` | OpenAPI-3.1-Dokument | – |
| `GET /api/v1/docs` | Swagger UI (HTML) | – |

`/status`-Antwort:

```json
{
  "service": "dishboard",
  "api_version": "1.0.0",
  "time": "2026-09-05T21:40:00+02:00",
  "channels": [
    {"channel": "cafeteria", "profile_code": "staff_guest", "published": true,
     "revision_id": "CAF-2026-KW36-R1", "week_start": "2026-08-31", "week_end": "2026-09-06",
     "today_state": "open"},
    {"channel": "patienten", "profile_code": "patient", "published": false,
     "revision_id": null, "week_start": null, "week_end": null, "today_state": null}
  ],
  "fhir": {"version": "5.0.0", "base_path": "/fhir", "metadata": "/fhir/metadata"},
  "docs": {"openapi": "/api/v1/openapi.json", "swagger_ui": "/api/v1/docs"}
}
```

`time` ist `datetime.now(ZoneInfo('Europe/Zurich')).isoformat(timespec='seconds')`.
`status_payload() -> dict` lebt in `api/v1_routes.py` und wird von der Admin-Seite (§7) wiederverwendet.

### 3.4 Endpunkte mit API-Schlüssel (WP-G, nach WP-D)

Header `Authorization: Bearer dbk_…`. Fehlende oder ungültige Schlüssel: `401 {"error": "unauthorized"}`
mit `WWW-Authenticate: Bearer realm="dishboard-api"`; fehlender Scope: `403 {"error": "insufficient_scope"}`.
Schlüssel werden nie geloggt.

| Route | Scope | Antwort |
|---|---|---|
| `GET /api/v1/keys/me` | jeder gültige Schlüssel | `{"label", "scopes", "expires_at", "public_id"}` |
| `GET /api/v1/weeks/{channel}` | `preview.read` | `{"channel", "weeks": [{"week_start", "week_end", "title", "workflow_state", "status"}]}` – die zwölf jüngsten Wochen des aktiven Standorts, absteigend; `status` aus `workflow.derive_admin_status` |
| `GET /api/v1/weeks/{channel}/{week_start}/preview` | `preview.read` | Draft im Snapshot-Format, gebaut wie die Admin-Vorschau (`admin.preview`), nur lesend (`load_draft_connection`, nie `ensure_week`); `X-Draft-Row-Version`; 404 `week_not_found`, 400 `invalid_week_start` (kein Montag) |

Die Wochen-Antworten unterliegen der Patientenregel (Vorschau-Snapshot des Patientenkanals läuft
durch `validate_snapshot_payload`).

### 3.5 OpenAPI-Dokument

- `openapi: "3.1.0"`, `info.title: "Dishboard Menü-API"`, `info.version: "1.0.0"`,
  `info.description` auf Deutsch, `servers: [{"url": "/"}]`.
- Tags: `published`, `status`, `docs`; WP-G ergänzt `weeks`, `keys` und
  `components.securitySchemes.ApiKeyBearer` (`type: http, scheme: bearer, bearerFormat: "dbk_…"`).
- `components.schemas`: `Snapshot`, `Location`, `Day`, `Service`, `Option`, `Label`, `Allergen`,
  `Origin`, `Prices`, `DayResponse`, `Status`, `ChannelStatus`, `Error`. Enums exakt aus
  `cafeteria/patient_payload.py` (`PATIENT_FIXED_VALUES`, Allergen- und Labelcodes). `Prices` erscheint
  nur in der Cafeteria-Beschreibung (Option-Schema mit `prices` optional, Erklärung im Text).
- Vertragstest `tests/test_openapi_contract.py`: (a) jede Regel in `app.url_map` mit Prefix `/api/v1`
  ist als Pfad (Flask-`<param>` → `{param}`) im Dokument enthalten, (b) jeder Pfad im Dokument mit
  Prefix `/api/v1` existiert in `url_map`, (c) alle `$ref` lösen auf, (d) `openapi.json` liefert
  dasselbe Dokument wie `build_openapi()`.

### 3.6 Swagger UI (selbst gehostet)

- Quelle: npm `swagger-ui-dist@5.32.15` (Apache-2.0),
  Tarball `https://registry.npmjs.org/swagger-ui-dist/-/swagger-ui-dist-5.32.15.tgz`,
  Integrity `sha512-TSFER+rFQlf1nzk6WvKkMaHTxAPQ3eAAxigFThnxQedSREanfZgSbJFayZVs/ULnSbNdrJOb99vLD6xpb3R3eg==`.
- Ausgeliefert nach `static/vendor/swagger-ui/`: `swagger-ui.css`, `swagger-ui-bundle.js`, `LICENSE`
  (aus dem Tarball; fehlt sie dort, aus dem GitHub-Tag `v5.32.15` von swagger-api/swagger-ui).
  Keine Maps, kein Standalone-Preset, keine externen Fonts (CSS auf `http` prüfen; Treffer sind ein Blocker,
  keine stillschweigende Änderung).
- Lock `static/vendor/swagger-ui.lock.json` im Schema von `tabler.lock.json` (`sources`, `files`, SHA-256).
  Werkzeug `tools/vendor_swagger_ui.py` (`--build`, `--verify`, nur Stdlib, Tar-Mitglieder im Speicher lesen,
  kein `extractall`), Aufbau analog `tools/vendor_tabler.py`. Test `tests/test_swagger_ui_assets.py` prüft
  `--verify` offline plus die SHA-256 jeder Datei gegen das Lock.
- `templates/api/docs.html`: eigenständiges HTML (nicht `base.html`), `lang="de-CH"`, Titel
  «Dishboard API», `<link rel="stylesheet" href="{{ url_for('static', filename='vendor/swagger-ui/swagger-ui.css') }}">`,
  `<div id="swagger-ui"></div>`, dann `swagger-ui-bundle.js` und `api-docs.js` (beide `defer`), ein
  sichtbarer Link «OpenAPI JSON» und «FHIR CapabilityStatement» über dem Container (`<nav class="api-docs-nav">`).
- `static/api-docs.js`: `window.SwaggerUIBundle({url: '/api/v1/openapi.json', dom_id: '#swagger-ui',
  deepLinking: true, presets: [SwaggerUIBundle.presets.apis], layout: 'BaseLayout', tryItOutEnabled: true})`
  in einem `DOMContentLoaded`-Handler. Keine Inline-Skripte.
- `/api/v1/docs` setzt vor dem `after_request`-`setdefault` den Header
  `Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'`
  (Swagger UI setzt Inline-Styles auf Elementen). `script-src` bleibt `'self'`. Test prüft den Header wörtlich
  und dass die Seite ausschliesslich `/static/`-Assets referenziert.

## 4. FHIR R5

### 4.1 Struktur

| Datei | Inhalt |
|---|---|
| `cafeteria/fhir/__init__.py` | leer |
| `cafeteria/fhir/mapping.py` | reine Funktionen Snapshot → FHIR-Dicts (kein Flask-Import) |
| `cafeteria/fhir/routes.py` | Blueprint `fhir`, Prefix `/fhir` |
| `tests/test_fhir_mapping.py` | ohne DB, Demo-Snapshots aus `tools/demo_snapshots.py` |
| `tests/test_fhir_routes.py` | DB-Fixture wie `tests/test_smoke.py` |

Signaturen (eingefroren):

```python
def system_uri(base_url: str, kind: str, name: str) -> str  # f'{base_url}/fhir/{kind}/{name}'
def product_id(external_id: str) -> str                      # '_' -> '-', sonst unverändert
def nutrition_product(snapshot: dict, day: dict, service: dict, option: dict, *, base_url: str) -> dict
def nutrition_products(snapshot: dict, *, base_url: str) -> list[dict]
def composition(snapshot: dict, *, base_url: str) -> dict
def document_bundle(snapshot: dict, *, base_url: str) -> dict
def searchset_bundle(resources: list[dict], *, base_url: str, self_url: str) -> dict
def capability_statement(*, base_url: str, software_version: str, now: str) -> dict
def operation_outcome(severity: str, code: str, diagnostics: str) -> dict
```

`base_url` ist `current_app.config['APP_PUBLIC_BASE_URL']` (ohne Slash am Ende).

### 4.2 Mapping

`NutritionProduct` (eine Ressource je Menüoption der publizierten Woche):

| Snapshot | FHIR |
|---|---|
| `external_id` | `id` = `product_id(external_id)`; `identifier[0]` = `{system: <base>/fhir/identifier/menu-option, value: external_id}` |
| – | `status: "active"` |
| `type_code`, `type_name` | `category[0].coding[0]` = `{system: <base>/fhir/CodeSystem/menu-type, code, display: type_name}` |
| `title` | `code.text` |
| `description` (nicht leer) | `note[0].text` |
| `components[]` | `ingredient[i].item.concept.text` |
| `allergens[]` | `knownAllergen[i].concept.coding[0]` = `{system: <base>/fhir/CodeSystem/allergen, code, display: name}`; `presence` als `knownAllergen[i].extension[0]` = `{url: <base>/fhir/StructureDefinition/allergen-presence, valueCode: presence}` |
| `labels[]` | `characteristic[]` mit `type.coding[0]` = `{system: <base>/fhir/CodeSystem/dietary-label, code, display: name}`, `valueBoolean: true` |
| `day.date` | `characteristic` `type.coding[0]` = `{system: <base>/fhir/CodeSystem/menu-characteristic, code: "service-date"}`, `valueString: date` |
| `service.meal_code`, `meal_name` | `characteristic` `type` `menu-characteristic|meal`, `valueCodeableConcept.coding[0]` = `{system: <base>/fhir/CodeSystem/meal, code: meal_code, display: meal_name}` |
| `snapshot.channel` | `characteristic` `menu-characteristic|channel`, `valueCodeableConcept.coding[0]` = `{system: <base>/fhir/CodeSystem/channel, code: channel}` |
| `allergen_review_status` | `characteristic` `menu-characteristic|allergen-review`, `valueCodeableConcept.coding[0]` = `{system: <base>/fhir/CodeSystem/allergen-review, code}` |
| `origins[]` | `characteristic` `menu-characteristic|origin`, `valueString: origin.text` |
| `note` (nicht leer) | `note[]` zusätzlicher Eintrag |
| `prices` (nur `staff_guest`) | `extension[]` `{url: <base>/fhir/StructureDefinition/menu-price, extension: [{url: "audience", valueCode: "internal"|"external"}, {url: "amount", valueMoney: {value: rappen/100, currency: "CHF"}}]}` je Betrag. Im Patientenkanal existiert weder `prices` noch diese Extension. |

`Composition` (eine je publizierter Revision):

- `id` = `revision_id`; `identifier[0]` = `{system: <base>/fhir/identifier/publication-revision, value: revision_id}`
- `status: "final"`, `type.coding[0]` = `{system: <base>/fhir/CodeSystem/document-type, code: "menu-plan", display: "Wochenmenüplan"}`
- `date` = `week_start`, `title` = `f'{title} – {location.name}'`, `author[0].display` = `location.name`,
  `custodian.display` = `location.name`
- `event[0].period` = `{start: week_start, end: week_end}`
- `extension`: `menu-channel` (`valueCode: channel`), `shared-note` (`valueString`, nur wenn nicht leer)
- `section[i]` je Tag: `title` = `f'{weekday} {date}'`, `code.text` = weekday,
  Untersektionen je Service: `title` = `meal_name`, `entry[]` = `{reference: f'NutritionProduct/{id}', display: title}`;
  geschlossene Services: `emptyReason.text` = `service.notice or day.notice or 'geschlossen'`, ohne `entry`.
  Tage ohne Services (Cafeteria-Wochenende): eine Sektion mit `emptyReason.text` = `day.notice or 'geschlossen'`.

`Bundle`:

- Dokument (`$document`): `type: "document"`, `identifier` wie Composition, `timestamp` = jetzt (Europe/Zurich),
  `entry[0]` = Composition, danach alle NutritionProducts; `fullUrl` = `f'{base}/fhir/{resourceType}/{id}'`.
- Suchergebnis: `type: "searchset"`, `total`, `link[0]` = `{relation: "self", url: self_url}`, `entry[].search.mode = "match"`.

`CapabilityStatement` (`/fhir/metadata`): `status: "active"`, `date` = jetzt, `kind: "instance"`,
`fhirVersion: "5.0.0"`, `format: ["json"]`, `software: {name: "Dishboard", version: <APPLICATION_VERSION aus db.py>}`,
`implementation: {description: "Dishboard Menüplanung Klinik Südhang", url: f'{base}/fhir'}`,
`rest[0].mode: "server"`, Ressourcen `NutritionProduct` (`read`, `search-type`, searchParam `channel` (token),
`date` (date)) und `Composition` (`read`, `search-type`, searchParam `channel`, `operation[0]` =
`{name: "document", definition: "http://hl7.org/fhir/OperationDefinition/Composition-document"}`).

### 4.3 Endpunkte

Alle Antworten `Content-Type: application/fhir+json; charset=utf-8`. Publizierte Daten mit
`Cache-Control: public, max-age=60, stale-if-error=86400` und `X-Snapshot-Revision` (bei Suchen über beide
Kanäle die Revisionen kommagetrennt). Fehler als `OperationOutcome` mit `Cache-Control: no-store`.

| Route | Verhalten |
|---|---|
| `GET /fhir/metadata` | CapabilityStatement, `Cache-Control: public, max-age=300` |
| `GET /fhir/NutritionProduct` | searchset über beide Kanäle; erlaubte Query-Parameter exakt `channel` (`cafeteria`/`patienten`) und `date` (`YYYY-MM-DD`, filtert `service-date`); jeder andere Parameter oder Wiederholung → 400 `invalid` |
| `GET /fhir/NutritionProduct/{id}` | Einzelressource; Suche über beide aktiven Snapshots nach `product_id(external_id) == id`; 404 `not-found` |
| `GET /fhir/Composition` | searchset der aktiven Compositions; Parameter `channel` optional |
| `GET /fhir/Composition/{id}` | `id` = Revisionscode einer aktiven Revision; sonst 404 |
| `GET /fhir/Composition/{id}/$document` | Dokument-Bundle |

Snapshot-Quelle ist `published_snapshot(profile)` aus `cafeteria.public.routes` (heute-basiert). Ein Kanal ohne
Publikation fehlt in Suchergebnissen still; Einzel-Reads antworten 404.
`404` für unbekannte `{id}`, `405`/`404` für alles andere unter `/fhir` (kein Catch-all nötig).

### 4.4 Patientenregel für FHIR

Test in `tests/test_fhir_mapping.py` und `tests/test_fhir_routes.py`: Die JSON-Serialisierung aller
Patientenressourcen (`Composition`, `$document`, `NutritionProduct?channel=patienten`, jedes Einzelprodukt) enthält
in Kleinschreibung keine der Zeichenketten `preis`, `price`, `chf`, `rappen`, `kosten`, `money`, `currency`,
`intern`, `extern`, `0.00`. Cafeteria-Ressourcen enthalten je offener Option genau zwei `menu-price`-Extensions.

## 5. API-Schlüssel (Schema v17, WP-D)

### 5.1 Schlüsselformat

- Klartext `dbk_` + 32 Zeichen aus `secrets.token_urlsafe(24)`; Regex `^dbk_[A-Za-z0-9_-]{32}$`.
- `key_prefix` = die ersten 12 Zeichen (`dbk_` + 8), `key_hash` = `'sha256:' + hashlib.sha256(klartext.encode()).hexdigest()`.
- Der Klartext wird genau einmal (beim Erstellen) angezeigt und nie gespeichert oder geloggt.
- Scopes v1: genau `preview.read`. Konstante `API_KEY_SCOPES = ('preview.read',)` in `cafeteria/api_keys.py`.

### 5.2 Migration `0014_v16_to_v17.sql` (strikt `BEGIN;` … `COMMIT;`)

```sql
CREATE TABLE IF NOT EXISTS cafeteria.api_keys (
    id bigint GENERATED ALWAYS AS IDENTITY PRIMARY KEY,
    public_id uuid NOT NULL DEFAULT gen_random_uuid() UNIQUE,
    label text NOT NULL CHECK (btrim(label) <> '' AND length(label) <= 80),
    key_prefix text NOT NULL UNIQUE CHECK (key_prefix ~ '^dbk_[A-Za-z0-9_-]{8}$'),
    key_hash text NOT NULL UNIQUE CHECK (key_hash ~ '^sha256:[0-9a-f]{64}$'),
    scopes text[] NOT NULL CHECK (cardinality(scopes) >= 1 AND scopes <@ ARRAY['preview.read']::text[]),
    created_by bigint NOT NULL REFERENCES cafeteria.users(id),
    created_at timestamptz NOT NULL DEFAULT clock_timestamp(),
    expires_at timestamptz CHECK (expires_at IS NULL OR expires_at > created_at),
    last_used_at timestamptz,
    revoked_at timestamptz,
    revoked_by bigint REFERENCES cafeteria.users(id),
    CHECK ((revoked_at IS NULL) = (revoked_by IS NULL))
);
```

Funktionen (`SECURITY DEFINER`, `SET search_path = pg_catalog, cafeteria, pg_temp`, Stil wie `0013`):

- `cafeteria.require_api_key_admin(p_actor_id bigint) RETURNS void`: Akteur existiert, nicht deaktiviert,
  hat in `user_role_cache` die Rolle `Cafeteria.Admin` (aktive `application_roles`); sonst `RAISE EXCEPTION ... ERRCODE '42501'`.
- `cafeteria.create_api_key(p_actor_id bigint, p_label text, p_key_prefix text, p_key_hash text, p_scopes text[], p_expires_at timestamptz) RETURNS uuid`:
  Admin-Check, Insert, Audit `api.key_created` (`entity_type 'api_key'`, `entity_public_id`, `details`
  `{label, key_prefix, scopes, expires_at}` – nie der Hash), gibt `public_id` zurück.
- `cafeteria.revoke_api_key(p_actor_id bigint, p_public_id uuid) RETURNS boolean`: Admin-Check, `FOR UPDATE`,
  setzt `revoked_at = clock_timestamp()`, `revoked_by`; bereits widerrufen → `false` ohne zweites Audit; Audit `api.key_revoked`.
- Rechte: `REVOKE ALL ON cafeteria.api_keys FROM PUBLIC`; `GRANT SELECT ON api_keys TO cafeteria_app`;
  `GRANT UPDATE (last_used_at) ON api_keys TO cafeteria_app`; `GRANT SELECT ON api_keys TO cafeteria_backup`;
  Funktionen: `REVOKE ... FROM PUBLIC, cafeteria_app, cafeteria_backup, cafeteria_auth_issuer` und
  `GRANT EXECUTE ... TO cafeteria_app` für `create_api_key` und `revoke_api_key`; `require_api_key_admin` nur intern.
- `schema.sql` (Leerstand v17) erhält Tabelle, Funktionen und Grants an der Stelle nach `audit_events`;
  `permissions.sql` dieselben Grants (idempotent). `validate_schema.py`: Version 17, `MIGRATION_0014` mit
  Prüfsummenpin, `api_keys` in `required_tables`, Pflichtfragmente `create_api_key`, `revoke_api_key`,
  `require_api_key_admin`. `db.py`: `SCHEMA_VERSION = 17`, `APPLICATION_VERSION = 'dishboard-schema-v17'`,
  `(17, '0014_v16_to_v17.sql')`. `tests/test_database_invariants.py`: Migrationsliste und Versionsreihe.
  `database/README.md`: Abschnitt «Schema v17».

### 5.3 Store `cafeteria/api_keys.py` (eingefroren)

```python
API_KEY_SCOPES = ('preview.read',)
API_KEY_RE = re.compile(r'^dbk_[A-Za-z0-9_-]{32}$')

@dataclass(frozen=True)
class ApiKeyRecord:
    public_id: str; label: str; key_prefix: str; scopes: tuple[str, ...]
    created_at: datetime; created_by_name: str
    expires_at: datetime | None; last_used_at: datetime | None; revoked_at: datetime | None
    @property
    def state(self) -> str  # 'active' | 'expired' | 'revoked'

@dataclass(frozen=True)
class ApiKeyIdentity:
    public_id: str; label: str; scopes: tuple[str, ...]; expires_at: datetime | None

class ApiKeyValidationError(ValueError): ...

def generate_api_key() -> tuple[str, str, str]                     # (klartext, prefix, hash)
def create_api_key(engine, *, actor_id: int, label: str, scopes: Sequence[str], expires_at: datetime | None) -> tuple[ApiKeyRecord, str]
def list_api_keys(engine) -> list[ApiKeyRecord]                    # neueste zuerst, inkl. widerrufene
def revoke_api_key(engine, *, actor_id: int, public_id: str) -> bool
def authenticate_api_key(engine, presented: str | None) -> ApiKeyIdentity | None
```

`authenticate_api_key`: Regex zuerst (sonst `None`), `SELECT` nach `key_prefix`, `hmac.compare_digest` auf
`key_hash`, Ablauf und Widerruf prüfen, danach `UPDATE last_used_at` nur wenn `NULL` oder älter als 60 s.
Fehlerklassen: DB-Rechtefehler (`42501`) → `PermissionError`, Validierung → `ApiKeyValidationError`.
Test `tests/test_api_keys_db.py`: Erstellen/Listen/Widerrufen als Admin, Editor wird abgewiesen (42501),
Audit-Ereignisse vorhanden ohne Hash, `authenticate_api_key` für gültig/abgelaufen/widerrufen/falsches Format,
`cafeteria_app`-Rolle kann `api_keys` nicht direkt einfügen oder `revoked_at` setzen.

## 6. MCP-Server (WP-C)

- Paket `reference_scaffold/dishboard_mcp/` (`__init__.py`, `__main__.py`, `server.py`), Abhängigkeiten in
  `reference_scaffold/requirements-mcp.txt`: `mcp>=1.26,<2`, `httpx>=0.28,<1`. Nicht Teil des Docker-Images.
- Start: `python -m dishboard_mcp` (Transport stdio). Umgebung: `DISHBOARD_BASE_URL` (Default
  `http://localhost:8080`), `DISHBOARD_API_KEY` (optional, für `preview.read`-Werkzeuge), `DISHBOARD_TIMEOUT_SECONDS` (Default 10).
- `build_server(client: httpx.Client) -> FastMCP` ist testbar; `main()` baut den Client aus der Umgebung
  (`base_url`, Header `Authorization: Bearer …` nur wenn gesetzt, `User-Agent: dishboard-mcp/1.0`).
- Werkzeuge (Name → HTTP → Rückgabe):
  - `get_status()` → `/api/v1/status` → Dict
  - `get_week_menu(channel)` → `/api/v1/published/{channel}` → Snapshot
  - `get_day_menu(channel, date=None)` → `/today` bzw. `/days/{date}` → DayResponse
  - `find_dishes(query, channel=None)` → Wochen-Snapshots (ein oder beide Kanäle), Treffer in `title`,
    `description`, `components`, `allergens[].name`, `labels[].name` (casefold, Substring) → Liste
    `{channel, date, weekday, meal_code, type_code, title, allergens: [code], labels: [code]}`
  - `list_weeks(channel)` → `/api/v1/weeks/{channel}` (braucht Schlüssel)
  - `get_week_preview(channel, week_start)` → `/api/v1/weeks/{channel}/{week_start}/preview` (braucht Schlüssel)
  - `get_fhir_document(channel)` → Revision aus `/status`, dann `/fhir/Composition/{rev}/$document`
- Ressourcen: `dishboard://published/{channel}` (Snapshot-JSON), `dishboard://openapi` (OpenAPI-JSON).
- Fehler: HTTP 4xx/5xx werden als `ToolError` mit `error`/`detail` aus dem JSON gemeldet; fehlender Schlüssel
  bei Schlüssel-Werkzeugen liefert eine klare Meldung («DISHBOARD_API_KEY fehlt»).
- Tests `tests/test_mcp_server.py` ohne Netzwerk: `httpx.MockTransport`, Antworten aus
  `demo/snapshots/*.json` bzw. handgebauten Status-/Fehlerantworten; prüfen `list_tools`, `call_tool` für jedes
  Werkzeug inklusive 404-Fall und Schlüssel-fehlt-Fall.
- Client-Konfiguration (Doku): Claude Code `claude mcp add dishboard -e DISHBOARD_BASE_URL=https://dishboard.joelduss.xyz -- /pfad/venv/bin/python -m dishboard_mcp`;
  Claude Desktop `mcpServers.dishboard = {command, args: ["-m", "dishboard_mcp"], env: {...}}`.

## 7. Admin-Seite «API & Schnittstellen» (WP-E, nach WP-D)

### 7.1 Routen (`cafeteria/admin/api_routes.py`, registriert wie `week_management_routes`)

| Route | Endpoint | Capability | Verhalten |
|---|---|---|---|
| `GET /admin/api` | `admin.api_overview` | `api.keys.manage` (nur `Cafeteria.Admin` über `*`) | Seite; Query-Parameter → 400 |
| `POST /admin/api/keys` | `admin.api_key_create` | `api.keys.manage` | Formular exakt `_csrf`, `label`, `scopes` (mehrfach, nur `preview.read`), `expires_at` (leer oder `YYYY-MM-DD`, wird 23:59:59 Europe/Zurich); Erfolg → Klartext in `session['api_key_created']` = `{public_id, plaintext}` und 303 auf `admin.api_overview`; Fehler → Seite mit `error` und Status 400 |
| `POST /admin/api/keys/<public_id>/revoke` | `admin.api_key_revoke` | `api.keys.manage` | Formular exakt `_csrf`; 303 auf `admin.api_overview`; unbekannte oder bereits widerrufene ID → Flash «Schlüssel war bereits widerrufen.» |

CSRF über `validate_csrf(request.form.get('_csrf'))` und `csrf_token()` (kein scoped CSRF nötig).
`GET` liest `session.pop('api_key_created', None)` und zeigt den Klartext genau einmal.

### 7.2 Template `templates/admin/api.html`

- `{% extends "admin/base_tabler.html" %}`, `{% set workflow_nav = 'api' %}`, Kontext enthält `family='cafeteria'`
  (Sidebar-Vertrag), `profile='staff_guest'`, `user`, `roles`.
- `main_attributes`: `data-page="api"`.
- Karten in dieser Reihenfolge (alle `section.card` mit `h2.card-title`):
  1. «Schnittstellen»: Liste mit Links `Swagger UI` (`/api/v1/docs`, `target="_blank" rel="noopener"`),
     `OpenAPI JSON`, `FHIR CapabilityStatement` (`/fhir/metadata`), `Doku` (`docs/API.md` als Textverweis),
     plus zwei Sätze Erklärung (öffentlich lesbar vs. Schlüssel für Vorschau).
  2. «Status» (`data-api-status`): Tabelle aus `status_payload()` — je Kanal `Publiziert`-Badge
     (`status`-Makro: `live`/`incomplete`), Revision, Woche; Zeile Schema-Version (`SCHEMA_VERSION`), API-Version, FHIR-Version.
  3. «Neuer Schlüssel»: Formular `#api-key-create` (`field`-Makro für `label`, `check` für `scopes`, Datumsfeld
     `expires_at` optional), Primäraktion `btn btn-primary` «Schlüssel erstellen». Fehler als
     `.alert.alert-danger.error[role=alert]`.
  4. Einmalanzeige nach Erstellung: `.alert.alert-success[data-new-key]` mit `<code>` Klartext und dem Satz
     «Dieser Schlüssel wird nur einmal angezeigt.»
  5. «API-Schlüssel» (`table[data-api-keys]`): Spalten Bezeichnung, Präfix, Scopes, Erstellt (von), Läuft ab,
     Zuletzt verwendet, Status (`status`-Makro: active→`live`, expired→`incomplete`, revoked→`secondary` mit Text),
     Aktion «Widerrufen» (`btn btn-outline-danger`, `data-confirm="Schlüssel wirklich widerrufen?"`, nur bei `active`).
     Leerzustand `.empty`.
- Tabular-Nums für Präfix/Datum über bestehende Tabler-Klassen; keine neuen CSS-Dateien, keine Hexwerte.

### 7.3 Tests `tests/test_admin_api_page.py`

DB-Fixture und `_login` aus `test_admin_workflow_routes.py`; `_register` dort registriert nur
`workflow_routes.bp` — im Test zusätzlich `from cafeteria.admin import api_routes` importieren (Registrierung auf
demselben Blueprint). Fälle: Admin sieht Seite mit drei Links und Statuskarte; Editor bekommt 403; Erstellen zeigt
Klartext genau einmal (zweiter GET ohne `[data-new-key]`); Widerrufen ändert Status; CSRF-Fehler 400; Query-Parameter 400;
Seite enthält keine Inline-Skripte oder `style=`-Attribute.

### 7.4 Vertrag für Codex (Sidebar)

`_workflow_sidebar.html`, Tabler-Zweig, `nav_items` um `('api', url_for('admin.api_overview'), 'info-circle',
'API & Schnittstellen')` ergänzen (Icon `info-circle` ist im Sprite; alternativ `api` nach Sprite-Erweiterung).
`workflow_nav == 'api'` markiert den Eintrag aktiv. Kein weiterer Eingriff nötig.

## 8. Dokumentation (WP-F)

`docs/API.md` (deutsch): Übersicht, Authentifizierung, alle REST-Routen mit Beispielantworten, FHIR-Ressourcen und
Beispiele, MCP-Konfiguration (Claude Code, Claude Desktop), Schlüsselverwaltung im Admin, Fehlerformate,
Nicht-Ziele. `README.md`: Routentabelle um `/api/v1/status`, `/api/v1/docs`, `/fhir/metadata`, `/admin/api` ergänzen,
Zeile «MCP-Server» im Inhaltsverzeichnis.

## 9. Work-Packages, Wellen, Gates

| WP | Branch | Dateien | Welle | Gate |
|---|---|---|---|---|
| A1 | `feat/api-v1-openapi-0905` | `api/v1_routes.py`, `api/openapi.py`, `__init__.py`, `tests/test_api_v1.py`, `tests/test_openapi_contract.py` | 1 | `pytest tests/test_api_v1.py tests/test_openapi_contract.py tests/test_public_contracts.py tests/test_smoke.py` |
| A2 | `feat/api-docs-swagger-0905` | `api/docs_routes.py`, `templates/api/docs.html`, `static/api-docs.js`, `static/vendor/swagger-ui/*`, `static/vendor/swagger-ui.lock.json`, `tools/vendor_swagger_ui.py`, `tests/test_api_docs.py`, `tests/test_swagger_ui_assets.py` | 1 | `pytest tests/test_api_docs.py tests/test_swagger_ui_assets.py tests/test_contracts.py` |
| B | `feat/fhir-r5-0905` | `fhir/*`, `__init__.py`, `tests/test_fhir_mapping.py`, `tests/test_fhir_routes.py` | 1 | `pytest tests/test_fhir_mapping.py tests/test_fhir_routes.py tests/test_public_contracts.py` |
| C | `feat/mcp-server-0905` | `dishboard_mcp/*`, `requirements-mcp.txt`, `tests/test_mcp_server.py` | 1 | `pytest tests/test_mcp_server.py` |
| D | `feat/api-keys-schema-0905` | Migration 0014, `schema.sql`, `permissions.sql`, `validate_schema.py`, `db.py`, `database/README.md`, `api_keys.py`, `tests/test_api_keys_db.py`, `tests/test_database_invariants.py` | 1 | `python database/validate_schema.py`; `pytest tests/test_api_keys_db.py tests/test_database_invariants.py tests/test_auth_database.py` |
| F | `docs/api-docs-0905` | `docs/API.md`, `README.md` | 1 | Markdown-Review |
| E | `feat/admin-api-page-0905` | `admin/api_routes.py`, `templates/admin/api.html`, `__init__.py`, `tests/test_admin_api_page.py` | 2 (nach D, A1) | `pytest tests/test_admin_api_page.py tests/test_contracts.py tests/test_rendered_ui.py -k api` |
| G | `feat/api-v1-keyed-0905` | `api/auth.py`, `api/v1_routes.py` (+Wochen), `api/openapi.py` (+Security), `tests/test_api_keyed.py` | 2 (nach D, A1) | `pytest tests/test_api_keyed.py tests/test_openapi_contract.py` |

Kombiniertes Gate vor dem Merge: Full-Suite im Integrations-Worktree, `ruff check reference_scaffold/cafeteria
reference_scaffold/tests reference_scaffold/dishboard_mcp`, `python database/validate_schema.py`,
`python tools/build_manifest.py --update`, Security-Review (API-Schlüssel, Bearer-Parsing, FHIR-Query-Whitelist),
Cross-Vendor-Review.
