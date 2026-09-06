# Dishboard-API

Stand 5. September 2026. Vertrag: `docs/superpowers/specs/2026-09-05-dishboard-api-mcp-fhir-design.md`.

Dishboard stellt eine REST-API v1, eine FHIR-R5-Leseschnittstelle, einen MCP-Server und API-Schlüssel
bereit. Beispiele nutzen `https://dishboard.joelduss.xyz`. Lokal lautet die Basis
`http://localhost:8080` (`APP_PUBLIC_BASE_URL`). JSON-Beispiele stammen aus
`demo/snapshots/cafeteria_kw36.json` und `demo/snapshots/patienten_kw36.json` (gekürzt, syntaktisch
vollständig). Der Patientenkanal enthält in JSON, FHIR und Fehlertexten keine Kosteninformation.

## Überblick und Zugriffsebenen

| Ebene | Authentifizierung | Inhalt |
|---|---|---|
| Öffentlich | keine | publizierte Wochen- und Tagesdaten, Status, OpenAPI, Swagger UI, FHIR-Lesezugriff |
| API-Schlüssel | `Authorization: Bearer dbk_…`, Scope `preview.read` | Wochenliste, Draft-Vorschau, Schlüssel-Selbstauskunft |
| Admin | Sitzung, Rolle `Cafeteria.Admin`, Capability `api.keys.manage` | Schlüssel erstellen und widerrufen unter `/admin/api` |

`channel` ist exakt `cafeteria` (Profil `staff_guest`) oder `patienten` (Profil `patient`).
«Heute» kommt ausschliesslich aus `effective_today()`.

## REST-API v1

### Gemeinsame Regeln

Jeder Query-String unter `/api/v1/*` ergibt `400` mit `Cache-Control: no-store`:

```json
{"error": "query_parameters_not_allowed", "detail": "Query-Parameter sind nicht erlaubt."}
```

Fehlerformat aller `/api/v1/*`-Antworten:

```json
{"error": "no_published_menu", "detail": "Kein publizierter Speiseplan vorhanden."}
```

`error` ist ein `snake_code`, `detail` ein deutscher Text ohne Kostenvokabeln im Patientenkanal.
Ausnahmen laut Vertrag: `401 {"error": "unauthorized"}` und `403 {"error": "insufficient_scope"}`
ohne `detail`.

| Antwort | Cache-Control | weitere Header |
|---|---|---|
| publizierte Daten | `public, max-age=60, stale-if-error=86400` | `X-Snapshot-Revision: <revision_id>` |
| `/api/v1/status` | `no-store` | – |
| `/api/v1/openapi.json` | `public, max-age=300` | – |
| Fehler | `no-store` | bei `401`: `WWW-Authenticate: Bearer realm="dishboard-api"` |

### `GET /api/v1/status`

```bash
curl -sS https://dishboard.joelduss.xyz/api/v1/status
```

```json
{
  "service": "dishboard",
  "api_version": "1.0.0",
  "time": "2026-09-05T21:40:00+02:00",
  "channels": [
    {
      "channel": "cafeteria",
      "profile_code": "staff_guest",
      "published": true,
      "revision_id": "CAF-2026-KW36-R1",
      "week_start": "2026-08-31",
      "week_end": "2026-09-06",
      "today_state": "open"
    },
    {
      "channel": "patienten",
      "profile_code": "patient",
      "published": false,
      "revision_id": null,
      "week_start": null,
      "week_end": null,
      "today_state": null
    }
  ],
  "fhir": {
    "version": "5.0.0",
    "base_path": "/fhir",
    "metadata": "/fhir/metadata"
  },
  "docs": {
    "openapi": "/api/v1/openapi.json",
    "swagger_ui": "/api/v1/docs"
  }
}
```

`time` ist `datetime.now(ZoneInfo("Europe/Zurich")).isoformat(timespec="seconds")`. Dieselbe
Nutzlast verwendet die Admin-Seite.

### `GET /api/v1/published/{channel}`

Bestehender Wochensnapshot. 404 `no_published_menu`, wenn keine Publikation aktiv ist.

Drei Felder sind optional und fehlen in Snapshots, die vor der Bereichsverwaltung publiziert wurden:
`area_name` auf Snapshotebene (Anzeigename des Bereichs, 1 bis 80 Zeichen) sowie `service_start` und
`service_end` je Service (Wanduhrzeit in Europe/Zurich, Muster `^([01][0-9]|2[0-3]):[0-5][0-9]$`).
Im Cafeteria-Kanal tragen Samstag und Sonntag entweder keinen Service oder genau einen LUNCH-Service;
Werktage tragen weiterhin genau einen.

```bash
curl -sS https://dishboard.joelduss.xyz/api/v1/published/cafeteria
```

```json
{
  "schema_version": 2,
  "profile_code": "staff_guest",
  "channel": "cafeteria",
  "revision_id": "CAF-2026-KW36-R1",
  "location": {
    "code": "KIRCHLINDACH",
    "name": "Klinik Südhang Kirchlindach"
  },
  "week_start": "2026-08-31",
  "week_end": "2026-09-06",
  "title": "31. August bis 4. September",
  "shared_note": "Cafeteria-Mittag für Mitarbeitende und externe Gäste.",
  "days": [
    {
      "date": "2026-08-31",
      "weekday": "Montag",
      "state": "open",
      "notice": "",
      "services": [
        {
          "meal_code": "LUNCH",
          "meal_name": "Mittag",
          "options": [
            {
              "external_id": "STAFF_GUEST-2026-08-31-LUNCH-1",
              "type_code": "MENU_1",
              "type_name": "Menü 1",
              "title": "Pouletbrust an Kräutersauce",
              "description": "Kartoffelstock · Zucchetti",
              "components": ["Kartoffelstock", "Zucchetti"],
              "labels": [],
              "allergens": [],
              "origins": [
                {
                  "ingredient": "Poulet",
                  "country_code": "CH",
                  "text": "Poulet: Schweiz"
                }
              ],
              "note": "",
              "allergen_review_status": "checked",
              "prices": {
                "currency": "CHF",
                "internal_rappen": 1100,
                "external_rappen": 1660
              }
            },
            {
              "external_id": "STAFF_GUEST-2026-08-31-LUNCH-2",
              "type_code": "VEGGIE",
              "type_name": "Vegetarisch",
              "title": "Spinat-Ricotta-Ravioli",
              "description": "Tomatensauce · Blattsalat",
              "components": ["Tomatensauce", "Blattsalat"],
              "labels": [{"code": "VEGETARIAN", "name": "Vegetarisch"}],
              "allergens": [
                {"code": "MILK", "name": "Milch", "presence": "contains"},
                {"code": "GLUTEN", "name": "Glutenhaltiges Getreide", "presence": "contains"}
              ],
              "origins": [],
              "note": "",
              "allergen_review_status": "checked",
              "prices": {
                "currency": "CHF",
                "internal_rappen": 1100,
                "external_rappen": 1660
              }
            }
          ]
        }
      ]
    }
  ]
}
```

```bash
curl -sS https://dishboard.joelduss.xyz/api/v1/published/patienten
```

Patientenoptionen haben kein Feld `prices`:

```json
{
  "schema_version": 2,
  "profile_code": "patient",
  "channel": "patienten",
  "revision_id": "PAT-2026-KW36-R1",
  "location": {
    "code": "KIRCHLINDACH",
    "name": "Klinik Südhang Kirchlindach"
  },
  "week_start": "2026-08-31",
  "week_end": "2026-09-06",
  "title": "31. August bis 6. September",
  "shared_note": "Allgemeiner Speiseplan für Patientinnen und Patienten.",
  "days": [
    {
      "date": "2026-08-31",
      "weekday": "Montag",
      "state": "open",
      "notice": "",
      "services": [
        {
          "meal_code": "LUNCH",
          "meal_name": "Mittag",
          "options": [
            {
              "external_id": "PATIENT-2026-08-31-LUNCH-1",
              "type_code": "MENU_1",
              "type_name": "Menü 1",
              "title": "Pouletgeschnetzeltes Paprika",
              "description": "Reis · Zucchetti",
              "components": ["Reis", "Zucchetti"],
              "labels": [],
              "allergens": [],
              "origins": [
                {
                  "ingredient": "Poulet",
                  "country_code": "CH",
                  "text": "Poulet: Schweiz"
                }
              ],
              "note": "",
              "allergen_review_status": "checked"
            },
            {
              "external_id": "PATIENT-2026-08-31-LUNCH-2",
              "type_code": "VEGGIE",
              "type_name": "Vegetarisch",
              "title": "Gemüsegeschnetzeltes",
              "description": "Reis · Zucchetti",
              "components": ["Reis", "Zucchetti"],
              "labels": [{"code": "VEGETARIAN", "name": "Vegetarisch"}],
              "allergens": [],
              "origins": [],
              "note": "",
              "allergen_review_status": "checked"
            }
          ]
        }
      ]
    }
  ]
}
```

### `GET /api/v1/published/{channel}/today`

Tag für `effective_today()`. 404 `no_published_menu`.

```bash
curl -sS https://dishboard.joelduss.xyz/api/v1/published/cafeteria/today
```

```json
{
  "channel": "cafeteria",
  "profile_code": "staff_guest",
  "revision_id": "CAF-2026-KW36-R1",
  "date": "2026-08-31",
  "day": {
    "date": "2026-08-31",
    "weekday": "Montag",
    "state": "open",
    "notice": "",
    "services": [
      {
        "meal_code": "LUNCH",
        "meal_name": "Mittag",
        "options": [
          {
            "external_id": "STAFF_GUEST-2026-08-31-LUNCH-1",
            "type_code": "MENU_1",
            "type_name": "Menü 1",
            "title": "Pouletbrust an Kräutersauce",
            "description": "Kartoffelstock · Zucchetti",
            "components": ["Kartoffelstock", "Zucchetti"],
            "labels": [],
            "allergens": [],
            "origins": [
              {
                "ingredient": "Poulet",
                "country_code": "CH",
                "text": "Poulet: Schweiz"
              }
            ],
            "note": "",
            "allergen_review_status": "checked",
            "prices": {
              "currency": "CHF",
              "internal_rappen": 1100,
              "external_rappen": 1660
            }
          }
        ]
      }
    ]
  }
}
```

Patienten-`today` ohne `prices`:

```bash
curl -sS https://dishboard.joelduss.xyz/api/v1/published/patienten/today
```

```json
{
  "channel": "patienten",
  "profile_code": "patient",
  "revision_id": "PAT-2026-KW36-R1",
  "date": "2026-08-31",
  "day": {
    "date": "2026-08-31",
    "weekday": "Montag",
    "state": "open",
    "notice": "",
    "services": [
      {
        "meal_code": "LUNCH",
        "meal_name": "Mittag",
        "options": [
          {
            "external_id": "PATIENT-2026-08-31-LUNCH-1",
            "type_code": "MENU_1",
            "type_name": "Menü 1",
            "title": "Pouletgeschnetzeltes Paprika",
            "description": "Reis · Zucchetti",
            "components": ["Reis", "Zucchetti"],
            "labels": [],
            "allergens": [],
            "origins": [
              {
                "ingredient": "Poulet",
                "country_code": "CH",
                "text": "Poulet: Schweiz"
              }
            ],
            "note": "",
            "allergen_review_status": "checked"
          }
        ]
      },
      {
        "meal_code": "DINNER",
        "meal_name": "Abend",
        "options": [
          {
            "external_id": "PATIENT-2026-08-31-DINNER-1",
            "type_code": "MENU_1",
            "type_name": "Menü 1",
            "title": "Schinken-Käse-Toast",
            "description": "Tomatensalat",
            "components": ["Tomatensalat"],
            "labels": [],
            "allergens": [
              {"code": "MILK", "name": "Milch", "presence": "contains"},
              {"code": "GLUTEN", "name": "Glutenhaltiges Getreide", "presence": "contains"}
            ],
            "origins": [
              {
                "ingredient": "Schwein",
                "country_code": "CH",
                "text": "Schwein: Schweiz"
              }
            ],
            "note": "",
            "allergen_review_status": "checked"
          }
        ]
      }
    ]
  }
}
```

### `GET /api/v1/published/{channel}/days/{date}`

Wie `/today` für ein Kalenderdatum. Snapshot über `active_snapshot` (inkl. Last-good).
400 `invalid_date`, wenn `{date}` kein gültiges `YYYY-MM-DD` ist; 404 `no_published_menu`.

```bash
curl -sS https://dishboard.joelduss.xyz/api/v1/published/cafeteria/days/2026-08-31
```

```json
{
  "channel": "cafeteria",
  "profile_code": "staff_guest",
  "revision_id": "CAF-2026-KW36-R1",
  "date": "2026-08-31",
  "day": {
    "date": "2026-08-31",
    "weekday": "Montag",
    "state": "open",
    "notice": "",
    "services": [
      {
        "meal_code": "LUNCH",
        "meal_name": "Mittag",
        "options": [
          {
            "external_id": "STAFF_GUEST-2026-08-31-LUNCH-1",
            "type_code": "MENU_1",
            "type_name": "Menü 1",
            "title": "Pouletbrust an Kräutersauce",
            "description": "Kartoffelstock · Zucchetti",
            "components": ["Kartoffelstock", "Zucchetti"],
            "labels": [],
            "allergens": [],
            "origins": [
              {
                "ingredient": "Poulet",
                "country_code": "CH",
                "text": "Poulet: Schweiz"
              }
            ],
            "note": "",
            "allergen_review_status": "checked",
            "prices": {
              "currency": "CHF",
              "internal_rappen": 1100,
              "external_rappen": 1660
            }
          }
        ]
      }
    ]
  }
}
```

```bash
curl -sS https://dishboard.joelduss.xyz/api/v1/published/cafeteria/days/31.08.2026
```

```json
{"error": "invalid_date", "detail": "Datum ist kein gültiges YYYY-MM-DD."}
```

### `GET /api/v1/keys/me`

Jeder gültige Schlüssel. Header `Authorization: Bearer dbk_…`.

```bash
curl -sS -H 'Authorization: Bearer dbk_…' https://dishboard.joelduss.xyz/api/v1/keys/me
```

```json
{
  "label": "MCP lokal",
  "scopes": ["preview.read"],
  "expires_at": null,
  "public_id": "3f1c0a2e-7b44-4c1a-9d2e-8a0b1c2d3e4f"
}
```

Fehlender oder ungültiger Schlüssel:

```json
{"error": "unauthorized"}
```

### `GET /api/v1/weeks/{channel}`

Scope `preview.read`. Die zwölf jüngsten Wochen des aktiven Standorts, absteigend.
`status` stammt aus `workflow.derive_admin_status`.

```bash
curl -sS -H 'Authorization: Bearer dbk_…' \
  https://dishboard.joelduss.xyz/api/v1/weeks/cafeteria
```

```json
{
  "channel": "cafeteria",
  "weeks": [
    {
      "week_start": "2026-08-31",
      "week_end": "2026-09-06",
      "title": "31. August bis 4. September",
      "workflow_state": "published",
      "status": "live"
    }
  ]
}
```

Fehlender Scope:

```json
{"error": "insufficient_scope"}
```

### `GET /api/v1/weeks/{channel}/{week_start}/preview`

Scope `preview.read`. Draft im Snapshot-Format, gebaut wie die Admin-Vorschau, nur lesend.
Header `X-Draft-Row-Version`. 400 `invalid_week_start` (kein Montag), 404 `week_not_found`.
Die Patienten-Vorschau läuft durch `validate_snapshot_payload` und enthält keine Kostenfelder.

```bash
curl -sS -H 'Authorization: Bearer dbk_…' \
  https://dishboard.joelduss.xyz/api/v1/weeks/patienten/2026-08-31/preview
```

```json
{
  "schema_version": 2,
  "profile_code": "patient",
  "channel": "patienten",
  "revision_id": "PAT-2026-KW36-R1",
  "location": {
    "code": "KIRCHLINDACH",
    "name": "Klinik Südhang Kirchlindach"
  },
  "week_start": "2026-08-31",
  "week_end": "2026-09-06",
  "title": "31. August bis 6. September",
  "shared_note": "Allgemeiner Speiseplan für Patientinnen und Patienten.",
  "days": [
    {
      "date": "2026-08-31",
      "weekday": "Montag",
      "state": "open",
      "notice": "",
      "services": [
        {
          "meal_code": "LUNCH",
          "meal_name": "Mittag",
          "options": [
            {
              "external_id": "PATIENT-2026-08-31-LUNCH-1",
              "type_code": "MENU_1",
              "type_name": "Menü 1",
              "title": "Pouletgeschnetzeltes Paprika",
              "description": "Reis · Zucchetti",
              "components": ["Reis", "Zucchetti"],
              "labels": [],
              "allergens": [],
              "origins": [
                {
                  "ingredient": "Poulet",
                  "country_code": "CH",
                  "text": "Poulet: Schweiz"
                }
              ],
              "note": "",
              "allergen_review_status": "checked"
            }
          ]
        }
      ]
    }
  ]
}
```

```json
{"error": "invalid_week_start", "detail": "week_start muss ein Montag im Format YYYY-MM-DD sein."}
```

```json
{"error": "week_not_found", "detail": "Woche nicht gefunden."}
```

## OpenAPI und Swagger UI

### `GET /api/v1/openapi.json`

OpenAPI 3.1, handgeschrieben, ohne Extra-Dependency. Cache `public, max-age=300`.

```bash
curl -sS https://dishboard.joelduss.xyz/api/v1/openapi.json
```

```json
{
  "openapi": "3.1.0",
  "info": {
    "title": "Dishboard Menü-API",
    "version": "1.0.0",
    "description": "Lesende Menü-API für publizierte Speisepläne, Status und FHIR-R5."
  },
  "servers": [{"url": "/"}]
}
```

Tags: `published`, `status`, `docs`, `weeks` und `keys`. Das Schema enthält
`components.securitySchemes.ApiKeyBearer` (`type: http`, `scheme: bearer`, `bearerFormat: "dbk_…"`).
`Prices` steht nur in der Cafeteria-Beschreibung; im Patienten-Option-Schema fehlt das Feld.

### `GET /api/v1/docs`

Selbst gehostetes Swagger UI (HTML). Vendor-Assets unter `/static/vendor/swagger-ui/`, keine
externen CDNs, keine Inline-Skripte.

```bash
curl -sS -D - -o /dev/null https://dishboard.joelduss.xyz/api/v1/docs
```

CSP vor dem `after_request`-`setdefault`, wörtlich:

```
Content-Security-Policy: default-src 'self'; img-src 'self' data:; style-src 'self' 'unsafe-inline'; script-src 'self'; frame-ancestors 'none'
```

`style-src` enthält `'unsafe-inline'`, weil Swagger UI Inline-Styles auf Elementen setzt.
`script-src` bleibt `'self'`. Die Seite verweist ausschliesslich auf `/static/`-Assets und enthält
Links auf OpenAPI JSON und FHIR CapabilityStatement.

## FHIR R5

Alle Antworten `Content-Type: application/fhir+json; charset=utf-8`.
`base_url` ist `APP_PUBLIC_BASE_URL` ohne Slash am Ende. Snapshot-Quelle ist
`published_snapshot(profile)` (heute-basiert). Ein Kanal ohne Publikation fehlt in Suchergebnissen
still; Einzel-Reads antworten 404. Unbekannte `{id}` → 404; andere Verben unter `/fhir` → 405/404.

Publizierte Daten: `Cache-Control: public, max-age=60, stale-if-error=86400` und
`X-Snapshot-Revision`. Suchen über beide Kanäle setzen die Revisionen kommagetrennt.
`/fhir/metadata`: `public, max-age=300`. Fehler: `OperationOutcome` mit `Cache-Control: no-store`.

### Ressourcen

| Ressource | Entstehung |
|---|---|
| `NutritionProduct` | eine je Menüoption der publizierten Woche; `id` = `product_id(external_id)` (`_` → `-`) |
| `Composition` | eine je publizierter Revision; `id` = `revision_id` |
| `Bundle` `document` | `$document`: Composition zuerst, danach alle NutritionProducts |
| `Bundle` `searchset` | Suchergebnis mit `total`, `link.relation=self`, `entry.search.mode=match` |
| `CapabilityStatement` | `/fhir/metadata` |
| `OperationOutcome` | Fehler |

`fullUrl` lautet `{base}/fhir/{resourceType}/{id}`.

### CodeSystem- und Identifier-URIs

`system_uri(base, kind, name)` → `{base}/fhir/{kind}/{name}`.

| Art | Name | Verwendung |
|---|---|---|
| `identifier` | `menu-option` | `NutritionProduct.identifier.value` = `external_id` |
| `identifier` | `publication-revision` | `Composition.identifier` und Dokument-Bundle |
| `CodeSystem` | `menu-type` | `type_code` / `type_name` |
| `CodeSystem` | `allergen` | Allergencode und -name |
| `CodeSystem` | `dietary-label` | Labelcode und -name, `valueBoolean: true` |
| `CodeSystem` | `menu-characteristic` | `service-date`, `meal`, `channel`, `allergen-review`, `origin` |
| `CodeSystem` | `meal` | `meal_code` / `meal_name` |
| `CodeSystem` | `channel` | `cafeteria` / `patienten` |
| `CodeSystem` | `allergen-review` | `allergen_review_status` |
| `CodeSystem` | `document-type` | `menu-plan` / `Wochenmenüplan` |
| `StructureDefinition` | `allergen-presence` | `contains` / `may_contain` |
| `StructureDefinition` | `menu-price` | nur Cafeteria: `audience` `internal`\|`external`, `amount` als `valueMoney` CHF |
| `StructureDefinition` | `menu-channel` | Composition, `valueCode` |
| `StructureDefinition` | `shared-note` | Composition, nur wenn nicht leer |

### Suchparameter

| Route | Parameter | Regel |
|---|---|---|
| `GET /fhir/NutritionProduct` | `channel` (`cafeteria`/`patienten`), `date` (`YYYY-MM-DD`, filtert `service-date`) | jeder andere Parameter oder Wiederholung → 400 `invalid` |
| `GET /fhir/Composition` | `channel` optional | sonst wie oben |

### Patientenregel

Die JSON-Serialisierung aller Patientenressourcen (`Composition`, `$document`,
`NutritionProduct?channel=patienten`, jedes Einzelprodukt) enthält in Kleinschreibung keine der
Zeichenketten `preis`, `price`, `chf`, `rappen`, `kosten`, `money`, `currency`, `intern`, `extern`,
`0.00`. Cafeteria-Ressourcen enthalten je offener Option genau zwei `menu-price`-Extensions
(Mitarbeitende und Externe). Im Patientenkanal existiert weder Snapshot-`prices` noch die Extension.

### `GET /fhir/metadata`

```bash
curl -sS -H 'Accept: application/fhir+json' https://dishboard.joelduss.xyz/fhir/metadata
```

```json
{
  "resourceType": "CapabilityStatement",
  "status": "active",
  "date": "2026-09-05T21:40:00+02:00",
  "kind": "instance",
  "fhirVersion": "5.0.0",
  "format": ["json"],
  "software": {
    "name": "Dishboard",
    "version": "dishboard-schema-v17"
  },
  "implementation": {
    "description": "Dishboard Menüplanung Klinik Südhang",
    "url": "https://dishboard.joelduss.xyz/fhir"
  },
  "rest": [
    {
      "mode": "server",
      "resource": [
        {
          "type": "NutritionProduct",
          "interaction": [{"code": "read"}, {"code": "search-type"}],
          "searchParam": [
            {"name": "channel", "type": "token"},
            {"name": "date", "type": "date"}
          ]
        },
        {
          "type": "Composition",
          "interaction": [{"code": "read"}, {"code": "search-type"}],
          "searchParam": [{"name": "channel", "type": "token"}],
          "operation": [
            {
              "name": "document",
              "definition": "http://hl7.org/fhir/OperationDefinition/Composition-document"
            }
          ]
        }
      ]
    }
  ]
}
```

`software.version` ist `APPLICATION_VERSION` aus `cafeteria/db.py`.

### `GET /fhir/NutritionProduct`

```bash
curl -sS -H 'Accept: application/fhir+json' \
  'https://dishboard.joelduss.xyz/fhir/NutritionProduct?channel=cafeteria'
```

```json
{
  "resourceType": "Bundle",
  "type": "searchset",
  "total": 1,
  "link": [
    {
      "relation": "self",
      "url": "https://dishboard.joelduss.xyz/fhir/NutritionProduct?channel=cafeteria"
    }
  ],
  "entry": [
    {
      "fullUrl": "https://dishboard.joelduss.xyz/fhir/NutritionProduct/STAFF-GUEST-2026-08-31-LUNCH-1",
      "resource": {
        "resourceType": "NutritionProduct",
        "id": "STAFF-GUEST-2026-08-31-LUNCH-1",
        "status": "active"
      },
      "search": {"mode": "match"}
    }
  ]
}
```

Anderer oder wiederholter Query-Parameter:

```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "error",
      "code": "invalid",
      "diagnostics": "Query-Parameter nicht erlaubt."
    }
  ]
}
```

### `GET /fhir/NutritionProduct/{id}`

Suche über beide aktiven Snapshots nach `product_id(external_id) == id`. 404 `not-found`.

```bash
curl -sS -H 'Accept: application/fhir+json' \
  https://dishboard.joelduss.xyz/fhir/NutritionProduct/STAFF-GUEST-2026-08-31-LUNCH-1
```

Cafeteria (mit zwei `menu-price`-Extensions, Betrag = Rappen/100):

```json
{
  "resourceType": "NutritionProduct",
  "id": "STAFF-GUEST-2026-08-31-LUNCH-1",
  "identifier": [
    {
      "system": "https://dishboard.joelduss.xyz/fhir/identifier/menu-option",
      "value": "STAFF_GUEST-2026-08-31-LUNCH-1"
    }
  ],
  "status": "active",
  "category": [
    {
      "coding": [
        {
          "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-type",
          "code": "MENU_1",
          "display": "Menü 1"
        }
      ]
    }
  ],
  "code": {"text": "Pouletbrust an Kräutersauce"},
  "ingredient": [
    {"item": {"concept": {"text": "Kartoffelstock"}}},
    {"item": {"concept": {"text": "Zucchetti"}}}
  ],
  "characteristic": [
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "service-date"
          }
        ]
      },
      "valueString": "2026-08-31"
    },
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "meal"
          }
        ]
      },
      "valueCodeableConcept": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/meal",
            "code": "LUNCH",
            "display": "Mittag"
          }
        ]
      }
    },
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "channel"
          }
        ]
      },
      "valueCodeableConcept": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/channel",
            "code": "cafeteria"
          }
        ]
      }
    },
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "allergen-review"
          }
        ]
      },
      "valueCodeableConcept": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/allergen-review",
            "code": "checked"
          }
        ]
      }
    },
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "origin"
          }
        ]
      },
      "valueString": "Poulet: Schweiz"
    }
  ],
  "note": [{"text": "Kartoffelstock · Zucchetti"}],
  "extension": [
    {
      "url": "https://dishboard.joelduss.xyz/fhir/StructureDefinition/menu-price",
      "extension": [
        {"url": "audience", "valueCode": "internal"},
        {"url": "amount", "valueMoney": {"value": 11.0, "currency": "CHF"}}
      ]
    },
    {
      "url": "https://dishboard.joelduss.xyz/fhir/StructureDefinition/menu-price",
      "extension": [
        {"url": "audience", "valueCode": "external"},
        {"url": "amount", "valueMoney": {"value": 16.6, "currency": "CHF"}}
      ]
    }
  ]
}
```

```bash
curl -sS -H 'Accept: application/fhir+json' \
  https://dishboard.joelduss.xyz/fhir/NutritionProduct/PATIENT-2026-08-31-LUNCH-1
```

Patientenprodukt ohne Preis-Extension:

```json
{
  "resourceType": "NutritionProduct",
  "id": "PATIENT-2026-08-31-LUNCH-1",
  "identifier": [
    {
      "system": "https://dishboard.joelduss.xyz/fhir/identifier/menu-option",
      "value": "PATIENT-2026-08-31-LUNCH-1"
    }
  ],
  "status": "active",
  "category": [
    {
      "coding": [
        {
          "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-type",
          "code": "MENU_1",
          "display": "Menü 1"
        }
      ]
    }
  ],
  "code": {"text": "Pouletgeschnetzeltes Paprika"},
  "ingredient": [
    {"item": {"concept": {"text": "Reis"}}},
    {"item": {"concept": {"text": "Zucchetti"}}}
  ],
  "characteristic": [
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "service-date"
          }
        ]
      },
      "valueString": "2026-08-31"
    },
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "meal"
          }
        ]
      },
      "valueCodeableConcept": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/meal",
            "code": "LUNCH",
            "display": "Mittag"
          }
        ]
      }
    },
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "channel"
          }
        ]
      },
      "valueCodeableConcept": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/channel",
            "code": "patienten"
          }
        ]
      }
    },
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "allergen-review"
          }
        ]
      },
      "valueCodeableConcept": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/allergen-review",
            "code": "checked"
          }
        ]
      }
    },
    {
      "type": {
        "coding": [
          {
            "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/menu-characteristic",
            "code": "origin"
          }
        ]
      },
      "valueString": "Poulet: Schweiz"
    }
  ],
  "note": [{"text": "Reis · Zucchetti"}]
}
```

```json
{
  "resourceType": "OperationOutcome",
  "issue": [
    {
      "severity": "error",
      "code": "not-found",
      "diagnostics": "NutritionProduct nicht gefunden."
    }
  ]
}
```

### `GET /fhir/Composition`

```bash
curl -sS -H 'Accept: application/fhir+json' \
  'https://dishboard.joelduss.xyz/fhir/Composition?channel=cafeteria'
```

```json
{
  "resourceType": "Bundle",
  "type": "searchset",
  "total": 1,
  "link": [
    {
      "relation": "self",
      "url": "https://dishboard.joelduss.xyz/fhir/Composition?channel=cafeteria"
    }
  ],
  "entry": [
    {
      "fullUrl": "https://dishboard.joelduss.xyz/fhir/Composition/CAF-2026-KW36-R1",
      "resource": {
        "resourceType": "Composition",
        "id": "CAF-2026-KW36-R1",
        "status": "final",
        "title": "31. August bis 4. September – Klinik Südhang Kirchlindach"
      },
      "search": {"mode": "match"}
    }
  ]
}
```

### `GET /fhir/Composition/{id}`

`id` = Revisionscode einer aktiven Revision.

```bash
curl -sS -H 'Accept: application/fhir+json' \
  https://dishboard.joelduss.xyz/fhir/Composition/CAF-2026-KW36-R1
```

```json
{
  "resourceType": "Composition",
  "id": "CAF-2026-KW36-R1",
  "identifier": [
    {
      "system": "https://dishboard.joelduss.xyz/fhir/identifier/publication-revision",
      "value": "CAF-2026-KW36-R1"
    }
  ],
  "status": "final",
  "type": {
    "coding": [
      {
        "system": "https://dishboard.joelduss.xyz/fhir/CodeSystem/document-type",
        "code": "menu-plan",
        "display": "Wochenmenüplan"
      }
    ]
  },
  "date": "2026-08-31",
  "title": "31. August bis 4. September – Klinik Südhang Kirchlindach",
  "author": [{"display": "Klinik Südhang Kirchlindach"}],
  "custodian": {"display": "Klinik Südhang Kirchlindach"},
  "event": [
    {"period": {"start": "2026-08-31", "end": "2026-09-06"}}
  ],
  "extension": [
    {
      "url": "https://dishboard.joelduss.xyz/fhir/StructureDefinition/menu-channel",
      "valueCode": "cafeteria"
    },
    {
      "url": "https://dishboard.joelduss.xyz/fhir/StructureDefinition/shared-note",
      "valueString": "Cafeteria-Mittag für Mitarbeitende und externe Gäste."
    }
  ],
  "section": [
    {
      "title": "Montag 2026-08-31",
      "code": {"text": "Montag"},
      "section": [
        {
          "title": "Mittag",
          "entry": [
            {
              "reference": "NutritionProduct/STAFF-GUEST-2026-08-31-LUNCH-1",
              "display": "Pouletbrust an Kräutersauce"
            },
            {
              "reference": "NutritionProduct/STAFF-GUEST-2026-08-31-LUNCH-2",
              "display": "Spinat-Ricotta-Ravioli"
            }
          ]
        }
      ]
    },
    {
      "title": "Samstag 2026-09-05",
      "code": {"text": "Samstag"},
      "emptyReason": {"text": "Cafeteria geschlossen"}
    }
  ]
}
```

Geschlossene Services setzen `emptyReason.text` auf `service.notice` oder `day.notice` oder
`geschlossen`, ohne `entry`. Tage ohne Services (Cafeteria-Wochenende) erhalten eine Sektion mit
`emptyReason.text` = `day.notice` oder `geschlossen`.

### `GET /fhir/Composition/{id}/$document`

```bash
curl -sS -H 'Accept: application/fhir+json' \
  https://dishboard.joelduss.xyz/fhir/Composition/CAF-2026-KW36-R1/\$document
```

```json
{
  "resourceType": "Bundle",
  "type": "document",
  "identifier": {
    "system": "https://dishboard.joelduss.xyz/fhir/identifier/publication-revision",
    "value": "CAF-2026-KW36-R1"
  },
  "timestamp": "2026-09-05T21:40:00+02:00",
  "entry": [
    {
      "fullUrl": "https://dishboard.joelduss.xyz/fhir/Composition/CAF-2026-KW36-R1",
      "resource": {
        "resourceType": "Composition",
        "id": "CAF-2026-KW36-R1",
        "status": "final",
        "title": "31. August bis 4. September – Klinik Südhang Kirchlindach"
      }
    },
    {
      "fullUrl": "https://dishboard.joelduss.xyz/fhir/NutritionProduct/STAFF-GUEST-2026-08-31-LUNCH-1",
      "resource": {
        "resourceType": "NutritionProduct",
        "id": "STAFF-GUEST-2026-08-31-LUNCH-1",
        "status": "active",
        "code": {"text": "Pouletbrust an Kräutersauce"}
      }
    }
  ]
}
```

`timestamp` ist jetzt in `Europe/Zurich`. `entry[0]` ist die Composition, danach alle
NutritionProducts der Revision.

## API-Schlüssel

### Format und Scopes

Klartext `dbk_` plus 32 Zeichen aus `secrets.token_urlsafe(24)`. Regex `^dbk_[A-Za-z0-9_-]{32}$`.
`key_prefix` sind die ersten 12 Zeichen (`dbk_` plus 8). Gespeichert wird nur
`sha256:` plus Hex-Digest, nie der Klartext.

Scope v1: genau `preview.read`.

### Erstellen und Widerrufen

Verwaltung unter `/admin/api` (nur `Cafeteria.Admin`). Query-Parameter auf dem GET ergeben 400.

| Route | Methode | Verhalten |
|---|---|---|
| `/admin/api` | `GET` | Übersicht, Status, Schlüsselliste; Klartext aus der Session genau einmal |
| `/admin/api/keys` | `POST` | Formular `_csrf`, `label`, `scopes` (nur `preview.read`), `expires_at` (leer oder `YYYY-MM-DD`, wird 23:59:59 Europe/Zurich); Erfolg 303, Klartext in der Session |
| `/admin/api/keys/<public_id>/revoke` | `POST` | Formular `_csrf`; 303; bereits widerrufen → Flash «Schlüssel war bereits widerrufen.» |

### Bearer-Header

```
Authorization: Bearer dbk_…
```

Schlüssel werden nie geloggt. `authenticate_api_key` prüft Format, Hash, Ablauf und Widerruf.

### Sicherheitsregeln

- Klartext wird genau einmal angezeigt (direkt nach dem Erstellen) und nie gespeichert.
- Schlüssel nie in URLs, Query-Strings oder Logs.
- Widerruf ist sofort wirksam: anschliessende Requests mit demselben Klartext ergeben `401`.
- Editor-Konten können Schlüssel nicht anlegen (Datenbank `42501`).

## MCP-Server

Separater Prozess, nicht Teil des Docker-Images. Abhängigkeiten nur in
`reference_scaffold/requirements-mcp.txt`.

### Installation und Start

```bash
pip install -r reference_scaffold/requirements-mcp.txt
cd reference_scaffold
python -m dishboard_mcp
```

Transport: stdio.

### Umgebungsvariablen

| Variable | Default | Zweck |
|---|---|---|
| `DISHBOARD_BASE_URL` | `http://localhost:8080` | API-Basis ohne Slash am Ende |
| `DISHBOARD_API_KEY` | unset | optional, für `preview.read`-Werkzeuge; setzt `Authorization: Bearer …` |
| `DISHBOARD_TIMEOUT_SECONDS` | `10` | HTTP-Timeout |

`User-Agent: dishboard-mcp/1.0`. HTTP 4xx/5xx werden als `ToolError` mit `error`/`detail` aus dem
JSON gemeldet. Fehlt der Schlüssel bei Schlüssel-Werkzeugen, lautet die Meldung
«DISHBOARD_API_KEY fehlt».

### Werkzeuge

| Werkzeug | Satz |
|---|---|
| `get_status()` | Liefert `/api/v1/status` als Dict. |
| `get_week_menu(channel)` | Liefert den publizierten Wochensnapshot von `/api/v1/published/{channel}`. |
| `get_day_menu(channel, date=None)` | Liefert `/today` oder `/days/{date}` als DayResponse. |
| `find_dishes(query, channel=None)` | Sucht casefold als Substring in Titel, Beschreibung, Komponenten, Allergen- und Labelnamen; Ergebnis `{channel, date, weekday, meal_code, type_code, title, allergens, labels}`. |
| `list_weeks(channel)` | Listet `/api/v1/weeks/{channel}` (braucht Schlüssel). |
| `get_week_preview(channel, week_start)` | Liefert den Draft von `/api/v1/weeks/{channel}/{week_start}/preview` (braucht Schlüssel). |
| `get_fhir_document(channel)` | Liest die Revision aus `/status` und holt `/fhir/Composition/{rev}/$document`. |

Ressourcen: `dishboard://published/{channel}` (Snapshot-JSON), `dishboard://openapi` (OpenAPI-JSON).

### Claude Code

```bash
claude mcp add dishboard -e DISHBOARD_BASE_URL=https://dishboard.joelduss.xyz -- /pfad/venv/bin/python -m dishboard_mcp
```

```json
{
  "mcpServers": {
    "dishboard": {
      "command": "/pfad/venv/bin/python",
      "args": ["-m", "dishboard_mcp"],
      "env": {
        "DISHBOARD_BASE_URL": "https://dishboard.joelduss.xyz",
        "DISHBOARD_API_KEY": "dbk_…",
        "DISHBOARD_TIMEOUT_SECONDS": "10"
      }
    }
  }
}
```

### Claude Desktop

```json
{
  "mcpServers": {
    "dishboard": {
      "command": "/pfad/venv/bin/python",
      "args": ["-m", "dishboard_mcp"],
      "env": {
        "DISHBOARD_BASE_URL": "https://dishboard.joelduss.xyz",
        "DISHBOARD_API_KEY": "dbk_…"
      }
    }
  }
}
```

`DISHBOARD_API_KEY` nur setzen, wenn Vorschau-Werkzeuge genutzt werden. Den Klartext nicht in
Versionskontrolle legen.

## Nicht-Ziele und Ausblick

Nicht in dieser Welle:

- schreibende API-Endpunkte (Drafts anlegen, publizieren)
- FHIR-Schreibzugriffe
- OAuth2
- Ratenbegrenzung pro Schlüssel
- SNOMED-/LOINC-Mappings
- FHIR-Suche über `_include` / `_sort`
- MCP-Streamable-HTTP im Container

Endpunkte mit API-Schlüssel und die Admin-Seite `/admin/api` sind Bestandteil dieser
Version und benötigen das Datenbankschema 17.
