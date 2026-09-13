# Open Food Facts — Feldzuordnung und Schweizer Stichprobe

Stand: 13. September 2026. Paket `MP-OFF-FIELDMAP` (`wp-645d9788f698`), Review-Korrektur `wp-7194bc889111`.
Ursprung: Worktree `off-fieldmap-agy-0913`, Branch `docs/off-fieldmap-agy-0913`, Basiscommit `a6337e66198a7c2da80862e3c9b68aff1d8de362`, Ergebnis `bdaf1435ae436c04a74ab50a6ad5ee4cace08461` (AGY-Lane).
Korrektur: Worktree `.claude/worktrees/off-fieldmap-reviewfix-0913`, Branch `docs/off-fieldmap-reviewfix-0913`, Basiscommit `bdaf1435ae436c04a74ab50a6ad5ee4cace08461`, Lane Claude Code (Modell `claude-fable-5-1`, anderer Autor gemäss Reviewbefund `wp-645d9788f698-root-review`, sechs Befunde).
Typ: Reines Spezifikations- und Feldzuordnungsdokument (Docs-Freeze). Kein Adaptercode, keine Netzwerkaufrufe im Produktivcode, keine Datenbankmutation. Dieses Dokument autorisiert keine Schemaerweiterung; es analysiert Verträge.

Kennzeichnung im ganzen Dokument: **vorhanden** = am Basiscommit im Repository belegt (Datei:Zeile), **vorgeschlagen** = Vorschlag für `MP-OFF-PROPOSAL-CONTRACT` bzw. `MP-NUT-*`, **OFF-offiziell** = aus der eingefrorenen Quelle in Abschnitt 1, **Projektvorgabe** = Dishboard-Entscheid ohne Zusage des Anbieters.

---

## 1. Offizielle Quellen, Versionierung und Rechtestatus

Alle Primärquellen wurden am 13. September 2026 direkt aus dem offiziellen Repository `openfoodfacts/openfoodfacts-server` abgerufen und auf den Commit `5a203f69738a1615d160051a661a36412d6ff252` (`main`, Committer-Datum 2026-09-12T07:28:29Z) eingefroren. Die gerenderte Dokumentation unter <https://openfoodfacts.github.io/openfoodfacts-server/api/> wird aus `main` gebaut und ist nicht eingefroren; bei Abweichung gilt der verlinkte Commit. In dieser Korrektur wurde kein Live-Produktabruf ausgeführt (das WP verlangt keine neue Produktprüfung); Aussagen zu Antwortcodes stammen aus der OpenAPI-Spezifikation.

| Ressource | Eingefrorener Link | Belegter Inhalt |
|---|---|---|
| API-Einführung | [docs/api/index.md](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/index.md) | Versionstabelle: v3 aktuell **v3.6**, «recommended for all new integrations»; v2 **deprecated**, «still supported for backward compatibility»; v1/v0 Legacy. Lizenzen, Rate-Limits, User-Agent, Staging-Zugang, Authentifizierung. |
| OpenAPI v3 | [docs/api/ref/api-v3.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/api-v3.yaml) | Pfad `GET /api/v3/product/{code}`, Parameter `fields`/`lc`/`cc`, Antworten `200`/`302`/`404`, Produktschema `product_v3.yaml`. Der Text «The current version of API v3 is v3.4» in der YAML ist älter als Einführung und Changelog (v3.6); beide Angaben sind hier dokumentiert, Einführung und Changelog sind massgebend. |
| API- und Schema-Changelog | [docs/api/ref-api-and-product-schema-change-log.md](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref-api-and-product-schema-change-log.md) | Product-Schema **1004** / API **3.6** (2026-05-27, `tags_sources`); 1003 / 3.5 neue Nährwertstruktur («still currently under active development»); 1002 / 3.3 neue Bildstruktur; 999 Barcode-Normalisierung; `schema_version` ab 1001. Undokumentierte Felder sind ausdrücklich nicht stabil. |
| Barcode-Normalisierung | [docs/api/ref-barcode-normalization.md](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref-barcode-normalization.md) | EAN-8/UPC-A/UPC-E/EAN-13/GTIN-14, Auffüllen führender Nullen, Normalisierung bei READ und WRITE. |
| Antwortstatus v3 | [responses/response-status/response_status.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/responses/response-status/response_status.yaml) | `status` ∈ `success`, `success_with_warnings`, `success_with_errors`, `failure`; `result`, `warnings[]`, `errors[]`. |
| Produktbasis | [schemas/product_base.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_base.yaml) | `code` (Z. 17), `product_name` (Z. 10), `generic_name` (Z. 46), `lc`/`lang` (Z. 55/60), `product_quantity` (Z. 81), `quantity` (Z. 95), `schema_version` (Z. 102). |
| Zutaten, Allergene, Herkunft | [schemas/product_ingredients.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_ingredients.yaml) | `allergens` (Z. 9), `allergens_tags` (Z. 19), `ingredients_text` (Z. 99), `origins` (Z. 131), `origins_tags` (Z. 141), `traces` (Z. 145), `traces_tags` (Z. 161). |
| Länder-Tags, Portionsangaben | [schemas/product_base_tags.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_base_tags.yaml), [schemas/product_misc.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_misc.yaml) | `countries_tags` (base_tags Z. 60); `serving_quantity` (misc Z. 107), `serving_size` (misc Z. 118). |
| Nährwerte v3.5+ | [schemas/product_nutrition_v3.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_nutrition_v3.yaml), [nutrients_v3_base.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/nutrients_v3_base.yaml), [nutrient_values_v3_base.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/nutrient_values_v3_base.yaml), [product_nutrition_properties.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_nutrition_properties.yaml), [nutrients_source_v3.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/nutrients_source_v3.yaml) | `nutrition.aggregated_set` (normalisiert auf 100 g **oder 100 ml**, Quellenpriorität manufacturer > packaging > usda > estimate, read-only), `nutrition.input_sets[]` (`source`, `per`, `per_quantity`, `per_unit`, `preparation`, `unspecified_nutrients`), Nährwertobjekt `{value, value_computed, value_string, unit, modifier}`, `per` ∈ `100g`/`100ml`/`serving`, `preparation` ∈ `as_sold`/`prepared`. |
| Nährwerte Legacy (v2, v3 < 3.5) | [schemas/product_nutrition.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_nutrition.yaml) | `no_nutrition_data`, `nutrition_data_per`, `nutrition_data_prepared_per`, `nutriments` mit Suffixen `_100g`, `_serving`, `_value`, `_unit`, `_prepared*`. |
| Bilder v3.3+ | [schemas/product_images_v3.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_images_v3.yaml), [image_selected.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/image_selected.yaml) | `images.uploaded`, `images.selected.<typ>.<sprache>` (Objekt), `selected_images.<typ>.<sprache oder best>.{"100","200","400"}` (URL-Strings, zur Laufzeit erzeugt). |
| Bilder Legacy (v2) | [schemas/product_images.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/product_images.yaml), [image_urls.yaml](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/ref/schemas/image_urls.yaml) | `selected_images.<typ>.{display,small,thumb}` = Objekt Sprachcode → URL; `image_url`, `image_<typ>_<grösse>_url` = String nach `lc` oder Hauptsprache, offiziell: «you should use `selected_images` field instead». |
| Lizenz-Tutorial | [docs/api/tutorials/license-be-on-the-legal-side.md](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/tutorials/license-be-on-the-legal-side.md) | Lizenzzuordnung je Datentyp, Verweise auf Nutzungsbedingungen, Wiki-Leitfaden und `reuse@openfoodfacts.org` als offizielle Kontaktadresse. |
| Nutzungsbedingungen (live, nicht eingefroren) | <https://world.openfoodfacts.org/terms-of-use>, <https://wiki.openfoodfacts.org/ODBL_License> | Aus Einführung und Tutorial verlinkt; Inhalt in dieser Korrektur nicht ausgewertet, daher keine daraus abgeleiteten Aussagen. |
| Scanning-Tutorial | [docs/api/tutorials/scanning-barcodes.md](https://github.com/openfoodfacts/openfoodfacts-server/blob/5a203f69738a1615d160051a661a36412d6ff252/docs/api/tutorials/scanning-barcodes.md) | Server normalisiert Barcodes selbst; Prüfziffer kann clientseitig berechnet werden (Empfehlung, keine Pflicht). |
| Produktionsbasis | `https://world.openfoodfacts.org` | Aus `servers` der OpenAPI v3 und der Einführung. |
| Staging-/Testbasis | `https://world.openfoodfacts.net` | Laut Einführung nur zum Testen; erfordert HTTP-Basic-Auth mit den dort veröffentlichten Testzugangsdaten (öffentlich dokumentiert, kein Geheimnis; hier nicht wiederholt). Getrennte Kontodatenbank. |

### Rechtestatus je Datentyp (OFF-offiziell) und Attributionspflicht

Die Einführung und das Lizenz-Tutorial ordnen zu:

1. **Datenbank (Gesamtwerk)**: [Open Database License (ODbL) 1.0](https://opendatacommons.org/licenses/odbl/1.0/). Namensnennung und Share-Alike für abgeleitete Datenbanken folgen aus dem Lizenztext; die konkrete Attributionsform verlangt OFF über die Nutzungsbedingungen und den Wiki-Leitfaden (beide verlinkt, hier nicht interpretiert).
2. **Einzelinhalte der Datenbank**: [Database Contents License (DbCL) 1.0](https://opendatacommons.org/licenses/dbcl/1.0/). Dieses Dokument leitet daraus keine Rechtsfolgerung ab («frei nutzbar» ist gestrichen); Herkunft bleibt nachvollziehbar (Quelle `off`, Barcode, `fetched_at`, Dokument-Prüfsumme).
3. **Produktbilder**: [Creative Commons Attribution ShareAlike 3.0](https://creativecommons.org/licenses/by-sa/3.0/deed.en). OFF-offiziell: «They may contain graphical elements subject to copyright or other rights that may, in some cases, be reproduced (quotation rights or fair use).» Ob eine konkrete Bildübernahme in Menüplan zulässig ist, entscheidet dieses Dokument nicht; es verlangt für jede Übernahme belegte Attribution (Open Food Facts, Lizenzhinweis, Link zur Produktseite) und die Prüfung der Rechte im Asset-Paket (`MP-OFF-PROPOSAL-CONTRACT` / `MP-OFF-REVIEW-UI`). Eine individuelle Urheberangabe je Foto ist in den eingefrorenen Schemas nicht enthalten; sie darf nicht erfunden werden.
4. **Datenqualitätsvorbehalt (OFF-offiziell)**: «there are no assurances that the data is accurate, complete, or reliable». Kein aus OFF übernommener Wert gilt in Menüplan als bestätigt; jeder bleibt Vorschlag bis zur ausdrücklichen Übernahme.

**Dishboard-Grenzen (vorhanden / vorgeschlagen)**:

- Vorhanden: `food_data_proposals` trägt `source IN ('off','supplier','ai','file_import')`, `source_reference` (≤ 200), `source_url` (≤ 2048, `^https?://`), `source_note` (≤ 500) und `fetched_at NOT NULL` (`database/schema.sql:3226-3245`). `foods.source_kind` kennt `'off'` und verlangt dann `source_reference` und `fetched_at` (`database/schema.sql:3157-3163`).
- Vorhanden, aber nicht verbunden: `accept_proposal_v21` überträgt bei Übernahme nur `density_g_per_ml`, `piece_weight_g`, `category_id` und `allergen_review_status` in `foods` (`database/schema.sql:4029-4031`); die Provenienzfelder von `foods` werden dabei nicht gesetzt. Die Übertragung der Provenienz ist ein Vorschlag für `MP-OFF-PROPOSAL-CONTRACT`.
- Vorgeschlagen: Bildmetadaten (URL, gewählte Sprache, Grösse) gelten als Vorschlag. Keine Roh-Einbettung externer URLs im Browser des Endanwenders (SDD 8.10). Bild-Downloads serverseitig mit MIME-/Byte-/Pixelprüfung im Asset-Paket.

---

## 2. Endpunkte, Eingabe- und Ausgabegrenzen

### Endpunktdefinition (OFF-offiziell, Auswahl = Projektvorgabe)

- **Eingefrorener Lesevertrag**: API v3 mit expliziter Subversion, `GET https://world.openfoodfacts.org/api/v3.6/product/{code}?fields=…` (Subversionspfad wie im offiziellen Staging-Beispiel der Einführung). Die feste Subversion ist Projektvorgabe, damit Schemawechsel (3.5 Nährwerte, 3.6 Tags) nicht implizit wirken; ein Versionswechsel ist eine dokumentierte Änderung dieses Freezes.
- **Legacy v2** (`GET /api/v2/product/{code}`) ist OFF-offiziell deprecated. Die v2-Feldformen (`nutriments.*_100g`, `nutrition_data_per`, `no_nutrition_data`, `selected_images.<typ>.display.<sprache>`) werden in Abschnitt 3 nur als Legacy-Zuordnung geführt, weil ihre Semantik im Reviewbefund geklärt werden musste. Neue Anschlussarbeit zielt nicht auf v2.
- **Feldselektion (`fields`)**, Namen gemäss Schema-Eigenschaften: `code,schema_version,lang,product_name,generic_name,quantity,product_quantity,serving_size,serving_quantity,ingredients_text,allergens_tags,traces_tags,origins,origins_tags,countries_tags,nutrition,selected_images`. Zusätzlich `lc=de` für sprachabhängige Auswahl. Ob `fields` die zur Laufzeit erzeugten `selected_images` liefert, wurde nicht live geprüft; `MP-OFF-FETCH` belegt das mit echten Request-Receipts.

### Eingabegrenzen (clientseitige Validierung vor jedem Netzaufruf)

1. **Barcode — Dishboard-Vertrag (Projektvorgabe)**:
   - Nur Ziffern, erlaubte Längen genau 8 (EAN-8), 12 (UPC-A), 13 (EAN-13/GTIN-13) oder 14 (GTIN-14). Regex konsistent dazu: `^(?:[0-9]{8}|[0-9]{12,14})$`. Längen 9, 10 und 11 sind ausgeschlossen; 7-stellige UPC-E werden nicht angenommen (Erweiterung wäre eine dokumentierte Vertragsänderung).
   - Barcode ist ein String; führende Nullen bleiben erhalten, nie als Zahl behandeln.
   - GS1-Prüfziffer (Mod-10) darf clientseitig geprüft werden (OFF-Tutorial: Empfehlung, keine Anforderung); ob Dishboard sie prüft, entscheidet `MP-OFF-FETCH`.
   - **Abgrenzung zu OFF**: OFF akzeptiert mehr als diesen Vertrag — «EAN-13 or internal codes for some food stores», von OFF vergebene Nummern mit Präfix `200` für Produkte ohne Barcode, sowie beliebig viele führende Nullen. OFF normalisiert bei READ und WRITE: ≤ 7 Ziffern (nach Entfernen führender Nullen) → 8 Stellen, 9–12 Ziffern → 13 Stellen. Das zurückgegebene `code` kann deshalb vom gesendeten Code abweichen (Beispiel OFF: `034000470693` → `0034000470693`). Der Adapter bewahrt beide Werte: gesendeter validierter Barcode und zurückgegebenes `code`.
2. **Netzwerk- und Sicherheitsgrenzen (SDD 8.6 / 8.10, Projektvorgaben)**:
   - Ausschliesslich HTTPS. Keine dynamischen, vom Benutzer übergebenen Hostnamen.
   - Feste Host-Allowlist: `world.openfoodfacts.org`; `world.openfoodfacts.net` nur in Testkonfiguration. Bild-URLs werden nur akzeptiert, wenn ihr Host in der Allowlist steht; der tatsächliche Bildhost wird in `MP-OFF-FETCH` aus realen Antworten belegt und nicht hier behauptet.
   - **User-Agent (OFF-offiziell)**: Format `AppName/Version (ContactEmail)`, Beispiel der Einführung `MyApp/1.0 (myapp@example.com)`; Zweck laut OFF: «to not risk being identified as a bot». Dishboard-Form: `Dishboard/<Version> (<Kontaktadresse>)`. Die tatsächliche Kontaktadresse ist ein Konfigurationswert von `MP-OFF-FETCH`; dieses Dokument legt keine Adresse fest. Eine Aussage, dass fehlende User-Agents «rasch per 403/429» blockiert würden, ist in den eingefrorenen Quellen nicht enthalten und gestrichen.
   - **Timeout**: 5 Sekunden pro HTTP-Aufruf ist Projektvorgabe (Muster SDD 8.6), keine Anbieterzusage.
   - **Rate-Limits (OFF-offiziell)**: 15 Leseanfragen pro Minute und IP-Adresse für Produktabfragen (`GET /api/v*/product`), 10 pro Minute und IP für Suchanfragen (von Dishboard nicht genutzt). Zusätzlich globale, IP-unabhängige Limits; bei Überschreitung antwortet OFF mit **HTTP 503**. Bei Verletzung behält sich OFF eine IP-Sperre vor; Entsperrung per E-Mail an `reuse@openfoodfacts.org`. Die Pro-Benutzer-Regel gilt nur für Aufrufe direkt aus Endgeräten; Dishboard ruft serverseitig von einer ausgehenden IP ab. **Projektvorgabe**: lokaler Begrenzer deutlich unter 15/min über alle Standorte, kein Bulk-Abruf, keine Suche-während-Tippen. OFF empfiehlt für hohes Volumen eine lokale Instanz mit Tagesexporten; das ist für Dishboard nicht vorgesehen.
   - **Authentifizierung (OFF-offiziell)**: Leseoperationen benötigen keine Authentifizierung ausser dem User-Agent. Niemals Kontodaten, Tokens oder geheime Konfiguration mitsenden; die Staging-Basic-Auth existiert nur in der Testkonfiguration.
   - **Antwortgrösse**: Byte-Obergrenze und Abbruch bei Überschreitung sind Pflicht aus SDD 8.10; der Wert wird in `MP-OFF-FETCH` festgelegt.

### Ausgabegrenzen (Antwortbehandlung)

1. **HTTP-Status und v3-Antworthülle (OFF-offiziell)**:
   - `HTTP 200`: Hülle `status` ∈ `success` / `success_with_warnings` / `success_with_errors` / `failure`, `result {id, name, lc_name}`, `warnings[]`, `errors[]`, `product {…}`. `warnings`/`errors` werden protokolliert; nur `product` wird gemappt.
   - `HTTP 404`: «Product not found» → kontrolliertes Ergebnis `not_found`. Es entsteht kein leerer bestätigter Datensatz.
   - `HTTP 302`: «Redirect to the correct server for the product type» (Beispiel in der Spezifikation: Open Beauty Facts). Dishboard folgt Redirects nicht (Host-Allowlist, reine Lebensmitteldomäne) → kontrolliertes Ergebnis `other_product_type`.
   - `HTTP 503`: globale Rate-Limits → kontrollierter Fehler mit Backoff, `Retry-After` beachten, falls gesetzt; kein Endlos-Retry. Andere 4xx/5xx (einschliesslich 429, in den eingefrorenen Quellen nicht dokumentiert) sind ebenfalls kontrollierte Fehler.
   - `product.schema_version` wird als Provenienz mitgespeichert (vorgeschlagen), damit spätere Schemawechsel erkennbar sind.
2. **Datenbegrenzung für die Persistenz (vorhanden)**:
   - `food_data_proposals.payload`: JSON-Objekt, `octet_length(payload::text) <= 65536` und `master_json_valid(payload)` (`database/schema.sql:3238-3239`).
   - `master_json_valid` (`database/schema.sql:3200-3222`): höchstens 200 Schlüssel insgesamt über alle verschachtelten Objekte und höchstens 200 je Objekt; Werte bis Tiefe 5 unter der Wurzel erlaubt, Tiefe 6 wird abgewiesen.
   - `source_reference` ≤ 200 Zeichen, `source_url` ≤ 2048 Zeichen mit `^https?://`, `source_note` ≤ 500 Zeichen; `master_text` normalisiert NFC, fasst Leerraum zusammen und lehnt Steuerzeichen sowie `<`/`>` ab (`database/schema.sql:3050-3062`).
   - Ein vollständiges OFF-Produktdokument überschreitet diese Grenzen regelmässig (Schlüsselzahl). `MP-OFF-ADAPTER` reduziert die Antwort auf die in Abschnitt 3 gemappten Felder, bevor irgendetwas persistiert wird.

---

## 3. Vollständige Feldzuordnungs-Matrix

Spalte «OFF-Feld» nennt die v3.6-Form; Legacy-v2-Formen stehen als eigene Zeilen, wo die Semantik abweicht. Spalte «Ziel» unterscheidet vorhanden (Datei:Zeile) und vorgeschlagen.

| Fachbereich | OFF-Feld (Quelle) | OFF-Typ | Dishboard-Ziel (Status) | Semantik und Normalisierung | Grenzen |
|---|---|---|---|---|---|
| **Barcode** | `code` (product_base.yaml:17) | `string`, von OFF normalisiert | Vorhanden: `food_data_proposals.source_reference` (≤ 200). Vorgeschlagen: typisiertes Feld `barcode` im Proposal-Vertrag; `foods.barcode` existiert nicht. | Gesendeter Barcode und zurückgegebenes `code` beide bewahren (Abschnitt 2). `codes_tags` (`code-13`/`code-8`) ist Metadatum. | Nicht in `PROPOSAL_FIELDS`. |
| **Schemaversion, Hauptsprache** | `schema_version` (product_base.yaml:102), `lang`/`lc` (product_base.yaml:60/55) | `integer`, `string` | Vorgeschlagen: Provenienz im Payload. | `lang` ist die Hauptsprache der Verpackung; steuert Sprachwahl für Texte und Bilder. | Nur Provenienz. |
| **Produktname** | `product_name` (product_base.yaml:10) | `string`, in der Hauptsprache (`lang`) | Vorhanden als Ziel nur bei ausdrücklicher Übernahme: `foods.name` (≤ 120, `master_text`; `database/schema.sql:3149`). Vorgeschlagen: `suggested_name` im Proposal-DTO. | NFC, Leerraum zusammengefasst, Steuerzeichen und `<`/`>` abgewiesen (wie `plain()` in `master_data_proposals.py:20-27`). | Nicht in `PROPOSAL_FIELDS`; sprachspezifische Varianten wurden nicht geprüft. |
| **Sachbezeichnung** | `generic_name` (product_base.yaml:46) | `string`, Hauptsprache | `foods.display_name` existiert nicht (`foods` hat `name` und `note`, `database/schema.sql:3141-3168`). Vorgeschlagen: `suggested_generic_name`. | Rechtliche Verkehrsbezeichnung als Referenztext. | Nicht in `PROPOSAL_FIELDS`. |
| **Packungsmenge** | `quantity` (product_base.yaml:95), `product_quantity` (product_base.yaml:81) | `string` (wie auf Packung), `string` (normalisiert in g oder ml) | Vorgeschlagen: Provenienz; kein automatisches Mapping auf `piece_weight_g`. | `product_quantity` ist Grundlage für die Einheit (g vs. ml) und damit für die Flüssigkeitsfrage bei Nährwerten. | `piece_weight_g` bleibt manuelle Entscheidung. |
| **Portionsangabe** | `serving_size` (product_misc.yaml:118), `serving_quantity` (product_misc.yaml:107) | `string` frei, `string` normalisiert | Vorgeschlagen: Provenienz im NUT-Vertrag. | Nur Referenz; keine Rückrechnung in Menüplan. | Kein Ziel in `foods`. |
| **Zutatenliste** | `ingredients_text` (product_ingredients.yaml:99) | `string` | Vorgeschlagen: Referenztext im Proposal-DTO. | Unverändert; Grundlage für manuelle Allergenabnahme. | Nicht in `PROPOSAL_FIELDS`. |
| **Strukturierte Zutaten** | `ingredients` (product_ingredients.yaml) | `array[object]` | Kein Persistenzziel. | Nur Lesereferenz. | Schlüssel-/Tiefengrenzen des Payloads (Abschnitt 2). |
| **Allergene (bestätigt)** | `allergens_tags` (product_ingredients.yaml:19) | `array[string]`, Taxonomie-Tags wie `en:milk` | Vorhanden: `PROPOSAL_FIELDS`-Eintrag `allergens` als `[{code, presence:'contains'}]` (`master_data_proposals.py:17`, `117-123`), DB `allergens.code ~ '^[A-Z0-9_]{1,32}$'`, `eu_number 1..14` (`database/schema.sql:254-260`). | Zuordnungstabelle OFF-Tag → Dishboard-Code ist ausdrücklicher Bestandteil von `MP-OFF-ADAPTER` (vorgeschlagen); Proposal-Code muss `^[A-Z][A-Z0-9_]{0,15}$` erfüllen (`master_data_proposals.py:43-46`). Nicht zuordenbare Tags werden als `unmapped` gemeldet, nie still verworfen. | Höchstens 64 Einträge (`master_data_proposals.py:60-63`). |
| **Spuren** | `traces_tags` (product_ingredients.yaml:161) | `array`, Elemente im eingefrorenen Schema `object` **oder** `string` | Vorhanden: derselbe `allergens`-Eintrag mit `presence:'may_contain'`. | Adapter akzeptiert beide Elementformen. Gleicher Code in beiden Listen ist ein Widerspruch; `normalize()` lehnt widersprüchliche Präsenz ab (`master_data_proposals.py:120-121`), der Adapter meldet den Konflikt statt zu raten. | Wie oben. |
| **Nährwerte v3.5+: aggregierter Satz** | `nutrition.aggregated_set` (product_nutrition_v3.yaml) mit `per`, `preparation` (product_nutrition_properties.yaml) und je Nährstoff `{value, value_computed, value_string, unit, modifier, source, source_per}` (nutrient_values_v3_base.yaml, nutrients_source_v3.yaml) | `object`, read-only | Vorgeschlagen: NUT-Vertrag (`MP-NUT-SCHEMA`/`MP-NUT-SERVICE`); am Basiscommit enthält `database/` kein Nährwertobjekt (Suche «nutri» ohne Treffer). | OFF normalisiert auf **100 g oder 100 ml** (`per`), Einheiten g / kJ / kcal; Quellenpriorität manufacturer > packaging > usda > estimate. Basis wird aus `per` übernommen, nie still als «pro 100 g» etikettiert. Nur `preparation = as_sold` in den Vorschlag; `prepared` bleibt getrennt. `source = estimate` und gesetzter `modifier` (`<`, `~` usw.) markieren den Wert als unscharf; solche Werte bleiben Vorschlag mit Kennzeichen, werden nicht als exakte Zahl geführt. `value_computed` (z. B. Energie aus Makros) ist rechnerisch, nicht deklariert. | Nährstoffnamen aus der OFF-Taxonomie; unbekannte Nährstoffe werden ignoriert, nicht abgelehnt. |
| **Nährwerte v3.5+: Eingabesätze** | `nutrition.input_sets[]` mit `source`, `per`, `per_quantity`, `per_unit`, `preparation`, `unspecified_nutrients[]`, `last_updated_t` | `array[object]` | Vorgeschlagen: Provenienz im NUT-Vertrag. | `unspecified_nutrients` bedeutet «auf der Packung nicht angegeben» und ist von «Schlüssel fehlt» zu unterscheiden. `per = serving` ohne `per_quantity`/`per_unit` ist nicht in 100 g/100 ml umrechenbar. | Nur Provenienz, keine Zielspalten. |
| **Nährwerte Legacy (v2)** | `nutriments.<n>_100g`, `_serving`, `_value` + `_unit`, `_prepared*`; `nutrition_data_per`; `no_nutrition_data` (product_nutrition.yaml) | `number`; `enum('serving','100g')`; `string 'on'` | Legacy-Zuordnung, kein neues Ziel. | `<n>_100g` ist der normalisierte Wert «for 100g (or 100ml for liquids)», as sold, read-only, von OFF aus Rohwert, Portionsgrösse und Einheit berechnet; er ist auch dann gültig, wenn `nutrition_data_per = serving` ist. `nutrition_data_per` betrifft `<n>_value`/`<n>`, nicht `<n>_100g`. `no_nutrition_data = "on"` heisst: Beitragende haben «Nutrition facts are not specified on the product» markiert; es belegt keine rechtliche Befreiung. | Ob ein `_100g`-Wert pro 100 ml gilt, ist nicht aus dem Feldnamen ablesbar (Abschnitt 4). |
| **Herkunft** | `origins` (product_ingredients.yaml:131), `origins_tags` (product_ingredients.yaml:141) | `string`; `array`, Elemente im eingefrorenen Schema `object` | Kein Feld in `foods`. `menu_components.origin_country_code` (`database/schema.sql:180`) gehört zu einer anderen Entität und ist kein Ziel. Vorgeschlagen: typisiertes Herkunftsmetadatum. | Herkunft der Zutaten laut Etikett; keine Länderzuordnung ohne Taxonomieprüfung. | Nicht in `PROPOSAL_FIELDS`. |
| **Verkaufsländer** | `countries_tags` (product_base_tags.yaml:60) | `array[string]` | Kein Persistenzziel; Plausibilität (`en:switzerland`). | Nur Hinweis, ob das Produkt in der Schweiz gelistet ist; kein Beleg für Verfügbarkeit. | Nur Lesereferenz. |
| **Bilder v3.3+: URLs** | `selected_images.<front\|ingredients\|nutrition\|packaging>.<sprache oder best>.{"100","200","400"}` (product_images_v3.yaml:48-77) | Objekt → Objekt → URL-`string` je Maximalgrösse | Vorgeschlagen: Bild-Ingest-Vertrag (URL, Bildtyp, gewählte Sprache, Grösse, SHA-256 nach serverseitigem Download, Abmessungen, Lizenz CC BY-SA 3.0, Attribution: Open Food Facts + Produktseiten-Link). Vorhanden und dafür empfohlen: `food_data_proposals.source_url` (≤ 2048) trägt die Produktseiten-URL `https://world.openfoodfacts.org/product/{code}`, nicht die Bild-URL. | Sprachcodes sind Schlüssel; `best` = Priorität `lc`-Anfrage, Hauptsprache des Produkts, andere Sprache. Dishboard-Regel (vorgeschlagen): explizite Reihenfolge `de`, `fr`, `it`, `en`, dann `lang`, dann erster vorhandener Schlüssel; gewählter Schlüssel wird gespeichert. Grösse `400` für die Prüfansicht, `100`/`200` als Vorschau. | Keine direkte UI-Rohverlinkung; nur Hosts der Allowlist. |
| **Bilder v3.3+: Auswahlmetadaten** | `images.selected.<typ>.<sprache>` (image_selected.yaml) | `object` `{imgid, rev, generation{…}}` | Vorgeschlagen: Provenienz (`imgid`, `rev`). | Kein URL-Feld; identifiziert das Quellbild und den Produktstand. | Nur Provenienz. |
| **Bilder Legacy (v2)** | `selected_images.<typ>.{display,small,thumb}` (product_images.yaml, image_urls.yaml); `image_url`, `image_<typ>[_<grösse>]_url` | `object` Sprachcode → URL; `string` | Legacy-Zuordnung, kein neues Ziel. | `display`/`small`/`thumb` sind Objekte, deren Schlüssel Sprachcodes sind; ein einzelner URL-String liegt erst unter dem Sprachschlüssel. `image_url` u. ä. wählt OFF nach `lc` oder Hauptsprache; offiziell: `selected_images` bevorzugen. | Gleiche Sprachregel wie oben. |
| **Bildtyp Nährwerttabelle / Zutaten** | `selected_images.nutrition.*`, `selected_images.ingredients.*` | wie oben | Verifikations-Asset (vorgeschlagen). | Belegfoto für manuelle Nährwert- bzw. Allergenabnahme. | Prüfnachweis; keine Rohverlinkung. |

---

## 4. Semantische Trennung: Fehlend, Null, nicht angegeben, Bezugsbasis

1. **Allergene und Spuren**:
   - Code in `allergens_tags` → `contains`; Code in `traces_tags` → `may_contain`.
   - Leere oder fehlende Listen bedeuten **nicht** «frei von». `foods.allergen_review_status` bleibt `not_checked` (`database/schema.sql:3155-3156`); der Status wird nie automatisch gesetzt. Es werden keine negativen Bestätigungen erzeugt.
2. **Nährwerte: Wertkategorien** (gilt für v3.5+ `aggregated_set` und Legacy `_100g`):
   - **Numerischer Wert, auch `0`**: ein von Beitragenden oder Herstellern erfasster Wert (bzw. bei `source = estimate` ein Schätzwert). Er wird als Zahl übernommen und bleibt Vorschlag; OFF-offiziell gibt es keine Zusage über Richtigkeit. `0` ist eine gültige Zahl, keine «verifizierte» Wahrheit.
   - **Schlüssel fehlt**: `NULL`/`None`. Niemals still zu `0` konvertieren.
   - **Auf der Packung nicht angegeben**: v3.5+ `unspecified_nutrients` bzw. Legacy `no_nutrition_data = "on"` → betroffene Werte `NULL` mit Begründung `not_on_packaging`. Das ist eine Aussage über die Verpackung, keine Aussage über eine rechtliche Befreiung; die frühere Deutung «exempt» ist gestrichen.
   - **Widerspruch**: Liegen trotz `no_nutrition_data = "on"` normalisierte Werte vor, werden diese nicht verworfen und nicht bestätigt, sondern als Vorschlag mit Konfliktkennzeichen geführt.
   - **Unscharfe Werte**: `modifier` gesetzt (`<`, `<=`, `~`, `>=`, `>`) oder `source = estimate` → Wert bleibt mit Kennzeichen erhalten, gilt nicht als exakt.
3. **Bezugsbasis (100 g, 100 ml, Portion)**:
   - v3.5+: Basis ist `aggregated_set.per` ∈ `100g` / `100ml` / `serving`. Sie wird so übernommen. Bei `serving` ohne `per_quantity` und `per_unit` (aus dem zugehörigen Eingabesatz) ist keine Umrechnung möglich; der Wert bleibt in Menüplan `NULL`, kein geratener 100-g-Wert.
   - Legacy v2: `<n>_100g` ist bereits von OFF normalisiert und wird verwendet, auch wenn `nutrition_data_per = serving` ist; vorhandene `_100g`-Werte werden nicht verworfen. Fehlt `_100g` und liegt nur `_value` mit `nutrition_data_per = serving` ohne bekannte Portionsmasse vor, bleibt der Wert `NULL`.
   - **Flüssigkeiten**: `_100g` kann laut Schema «100ml for liquids» bedeuten, und `aggregated_set.per` kann `100ml` sein. Der NUT-Vertrag muss die Basis als `per_100g` oder `per_100ml` tragen. Eine Umrechnung 100 ml → 100 g ist nur mit bekannter Dichte (`foods.density_g_per_ml`, vorhanden) und ausdrücklicher Bestätigung zulässig; sonst bleibt die Basis `per_100ml` sichtbar. Kein Wert wird still als «pro 100 g» etikettiert.
   - **Zubereitet vs. verkauft**: `preparation = prepared` bzw. `_prepared*` bleiben getrennt und fliessen nicht in den Vorschlag für das Produkt wie verkauft ein.

---

## 5. Analyse der bestehenden PROPOSAL_FIELDS und Parser-Grenzen

### Ist-Zustand im Repository (vorhanden, Basiscommit `bdaf1435`)

- `reference_scaffold/cafeteria/master_data_proposals.py:17`:

  ```python
  PROPOSAL_FIELDS = frozenset({'density_g_per_ml', 'piece_weight_g', 'category_code', 'allergens', 'labels'})
  ```

- `normalize()` (`master_data_proposals.py:66-130`): `source_reference` ≤ 200 (Z. 83), `source_url` ≤ 2048 mit `^https?://` (Z. 84-87), `labels` als sortierte Codes (Z. 114-115), `allergens` als `[{code, presence}]` mit `presence in ('contains','may_contain')` und Ablehnung widersprüchlicher Präsenz (Z. 116-123), `fields` als nicht leere Teilmenge von `PROPOSAL_FIELDS` (Z. 124-128). Listen sind auf 64 Einträge begrenzt (`bounded_list`, Z. 60-63).
- Datenbank: `create_proposal_v21` (`database/schema.sql:3924-3947`) erlaubt im Aufruf-Payload genau `source`, `source_reference`, `source_url`, `source_note`, `fetched_at`, `payload`, `food_public_id` (Z. 3930) und verlangt `masterdata.write` (Z. 3928). `accept_proposal_v21` (`database/schema.sql:3949-4046`) verlangt `recipe.import` (Z. 3958), 1–64 ausgewählte `fields` (Z. 3962-3965) und prüft:

  ```sql
  IF EXISTS(SELECT 1 FROM unnest(fields) x WHERE x IS NULL OR
    x NOT IN ('density_g_per_ml','piece_weight_g','category_code','allergens','labels')) THEN
      RAISE EXCEPTION 'Unsupported selection.' USING ERRCODE='P1901';
  END IF;
  ```

  Alle anderen Schlüssel des Payloads werden nicht übernommen, sondern in `not_supported` zurückgemeldet (Z. 4033-4037):

  ```sql
  SELECT COALESCE(array_agg(k ORDER BY k),'{}') INTO unsupported FROM jsonb_object_keys(v.payload) k
    WHERE k NOT IN ('density_g_per_ml','piece_weight_g','category_code','allergens','labels');
  ```

  Der im Ursprungsdokument genannte Name `accept_food_data_proposal_v21` existiert nicht; der tatsächliche Name ist `accept_proposal_v21`.

### Vorschlag für typisierte Metadaten (vorgeschlagen, nicht autorisiert)

Die fünf vorhandenen Felder decken Hilfsfaktoren und Deklarationen ab. Für die übrigen OFF-Daten benennt dieses Dokument den Bedarf; die Entscheidung über Schema und DTO liegt bei `MP-OFF-PROPOSAL-CONTRACT` (Proposal-/Assetvertrag) und `MP-NUT-SCHEMA`/`MP-NUT-SERVICE` (Nährwerte). Keiner der folgenden Namen existiert am Basiscommit im Code (Suche in `reference_scaffold/`, `database/`, `recipes-wps.json`, `recipes-sdd.md` ohne Treffer):

1. **Barcode**: heute nur als Freitext in `food_data_proposals.source_reference` möglich (vorhanden). Vorschlag: typisiertes Feld `barcode` mit dem Dishboard-Vertrag aus Abschnitt 2 (`^(?:[0-9]{8}|[0-9]{12,14})$`), plus zurückgegebenes OFF-`code` als Provenienz. Ob `foods` ein indizierbares Barcode-Feld erhält, entscheidet der Proposal-Vertrag.
2. **Produktname und Sachbezeichnung**: Vorschlag `suggested_name`, `suggested_generic_name` im Proposal-DTO für Neuanlage und Namensabgleich; nicht still im Payload verstecken (würde in `not_supported` landen).
3. **Spuren getrennt von Allergenen**: kein neues Feld nötig; der vorhandene `allergens`-Eintrag trägt `presence`. Neu ist nur die Zuordnungstabelle OFF-Tag → Dishboard-Code im Adapter und die Konfliktmeldung bei Doppelnennung.
4. **Nährwerte und Bezugsbasis**: gehören in den NUT-Vertrag. Vorschlag: typisiertes Nutrient-DTO mit Basis `per_100g`/`per_100ml`/`serving`, Zubereitungszustand, Quelle, `modifier`, Wert/`NULL`, `not_on_packaging`-Begründung; nicht über `PROPOSAL_FIELDS`. `MP-NUT-SERVICE` nennt bereits «festes typisiertes Nutrient-DTO» und «0 ist valider Wert, Unknown bleibt NULL».
5. **Herkunft**: kein Feld in `foods`; Vorschlag typisiertes Herkunftsmetadatum im Proposal-Vertrag.
6. **Bilder und Bildprovenienz**: Vorschlag Bild-Ingest-Vertrag (URL, Bildtyp, gewählte Sprache, Grösse, SHA-256, Abmessungen, Lizenz `CC BY-SA 3.0`, Attribution, `imgid`/`rev`, Zeitstempel). Externe Bild-URLs werden nicht als statische Links in Webseiten eingebunden.
7. **Provenienzübertragung in `foods`**: `accept_proposal_v21` setzt `foods.source_kind`/`source_reference`/`fetched_at` nicht (Abschnitt 1); Vorschlag für `MP-OFF-PROPOSAL-CONTRACT`.

### Konsequenz für Folgemodule

- `MP-OFF-ADAPTER` passt ausschliesslich die fünf vorhandenen Felder in das bestehende `PROPOSAL_FIELDS`-Schema ein und isoliert alle weiteren Daten in einem typisierten Übergabeobjekt (Arbeitsname `OffProductProposal`, vorgeschlagen), das ohne Vertragsintegration nicht persistiert wird.
- Ein Erweitern von `PROPOSAL_FIELDS` oder der SQL-Allowlist ohne Root-Lease und DDL-Migration ist unzulässig; dieses Dokument autorisiert beides nicht.
- `MP-OFF-PROPOSAL-CONTRACT` besitzt DDL, feste SQL-Verben und Store-Logik; `MP-NUT-SCHEMA`/`MP-NUT-SERVICE` besitzen den Nährwertvertrag.

---

## 6. Schweizer Stichprobe (Swiss Coverage)

### Methodische Klarstellung

- Eine repräsentative Schweizer Abdeckungsmessung (Trefferquote für Schweizer Gastronomie- und Einzelhandelsprodukte) kann **nicht** aus synthetischen Test-Fixtures oder einzelnen Beispielabfragen abgeleitet werden.
- Dieses Dokument stellt ausdrücklich fest: **Es wird keine Schweizer Trefferquote und keine Vollständigkeitsquote behauptet**, weder für internationale Markenartikel noch für Eigenmarken oder Grossgebinde. Frühere Schätzwerte sind gestrichen.
- Die empirische Erhebung mit realen, berechtigten Barcodes (Trefferquote, Feldvollständigkeit, Rechte-/Bildlücken, tatsächliche Fehler getrennt) ist Gegenstand des separaten Arbeitspakets **`MP-OFF-COVERAGE`**.
- Die fehlende Marktabdeckungsmessung blockiert die Schnittstellen- und Adapterentwicklung (`MP-OFF-ADAPTER`, `MP-OFF-FETCH`) nicht; diese wird mit deterministischen, versionierten Test-Fixtures validiert, die von echten API-Receipts getrennt bleiben.

---

## 7. Zusammenfassung und Validierungsstatus

- **Offizielle Quellen**: auf Commit `5a203f69738a1615d160051a661a36412d6ff252` eingefroren und verlinkt; Versionen (API v3.6, Product-Schema 1004, v2 deprecated) und Lizenzen (ODbL 1.0, DbCL 1.0, CC BY-SA 3.0) belegt. Nutzungsbedingungen und Wiki-Leitfaden sind verlinkt, nicht ausgewertet.
- **Feldmapping**: Barcode, Texte/Zutaten, Allergene/Spuren, Nährwerte (v3.5+ und Legacy) mit Bezugsbasis, Herkunft und Bilder gegen die eingefrorenen Schemas zugeordnet; vorhanden und vorgeschlagen getrennt.
- **Fehlend vs. 0 vs. nicht angegeben**: `NULL`, numerischer Wert, `not_on_packaging`, unscharfe Werte und Basis 100 g/100 ml/Portion definiert.
- **Systemgrenzen**: `PROPOSAL_FIELDS`, `create_proposal_v21`, `accept_proposal_v21` und Payload-Guards mit Datei und Zeile belegt; Folgeanforderungen als Vorschlag markiert.
- **Coverage**: keine Quoten; Trennung zwischen Schnittstellenfreeze und `MP-OFF-COVERAGE`.

### Korrekturen aus dem Reviewbefund `wp-645d9788f698-root-review`

1. Barcode: Längen 8/12/13/14 und Regex `^(?:[0-9]{8}|[0-9]{12,14})$` sind konsistent; Dishboard-Vertrag von der OFF-Codemenge und -Normalisierung getrennt.
2. Nährwerte: `no_nutrition_data` als Packungsaussage, `_100g` bleibt auch bei `serving`-Basis gültig, 100 ml-Fall sichtbar, `0` als erfasster Wert, zubereitet getrennt; v3.5+-Struktur ergänzt.
3. Bilder: `selected_images` als sprachkeyed Objekte (v2 `display`/`small`/`thumb`, v3.3+ `100`/`200`/`400`, `best`), Sprachwahl und Fallback definiert, `image_url` separat.
4. Coverage: `> 80 %` und Schätzungen entfernt; `MP-OFF-COVERAGE` bleibt getrennt.
5. Quellen: eingefrorene Links je Datei, Versions-/Deprecation-Belege, 15/min und 503 mit Quelle, IP-Sperre statt «403/429», Timeout und lokaler Begrenzer als Projektvorgabe, Kontaktadresse als Konfigurationswert, keine Rechtsfolgerung über den Lizenztext hinaus.
6. Verträge: `accept_proposal_v21`/`create_proposal_v21` mit tatsächlichen Zeilen, `foods.display_name`/`foods.barcode` als nicht vorhanden markiert, alle DTO-Namen als Vorschlag gekennzeichnet, keine Schemaerweiterung autorisiert.

### Nicht gefahrene Prüfungen

- Keine Produkt-, Lint- oder Datenbanktests (reines Dokument; Produktcode und Datenbank unverändert).
- Kein Live-Produktabruf gegen OFF; keine Prüfung der Wirkung von `fields` auf `selected_images`.
- Nutzungsbedingungen und Wiki-Attributionsleitfaden nicht ausgewertet.
- Review-Erststufe (OCR) und GitNexus `detect_changes` sind im WP-Report `wp-7194bc889111` mit tatsächlichem Ergebnis dokumentiert; dieser Docs-Freeze ist kein Produkt-/Live-/Fachabnahme-PASS.
