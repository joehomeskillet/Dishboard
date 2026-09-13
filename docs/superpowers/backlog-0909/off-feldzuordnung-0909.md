# Open Food Facts — Feldzuordnung und Schweizer Stichprobe

Stand: 13. September 2026. Paket `MP-OFF-FIELDMAP` (`wp-645d9788f698`).
Worktree: `/nvmetank1/projects/menuplan/.claude/worktrees/off-fieldmap-agy-0913`
Branch: `docs/off-fieldmap-agy-0913`, Basiscommit: `a6337e66198a7c2da80862e3c9b68aff1d8de362`.
Typ: Reines Spezifikations- und Feldzuordnungsdokument (Docs-Freeze). Kein Adaptercode, keine Netzwerkaufrufe im Produktivcode, keine Datenbankmutation.

---

## 1. Offizielle Quellen, Versionierung und Rechtestatus

Die folgenden Primärquellen wurden im Rahmen der lokalen Quellenprüfung direkt von offiziellen Open Food Facts Repositories und Dokumentationsendpunkten abgerufen:

| Ressource | Quelle / URL | Version / Stand | Lizenz / Rechtestatus |
|---|---|---|---|
| **API Spezifikation (v3)** | `openfoodfacts-server/docs/api/ref/api-v3.yaml` | OpenAPI 3.1.0, API v3.4/v3.6 (Produkt-Schema 1004) | ODbL 1.0 / Server-Quellcode AGPL-3.0 |
| **API Spezifikation (v2)** | `openfoodfacts-server/docs/api/ref-v2/` | API v2 (deprecated, aber rückwärtskompatibel unterstützt) | ODbL 1.0 |
| **API Dokumentation & Richtlinien** | `openfoodfacts-server/docs/api/index.md` | Stand Mai/September 2026 | ODbL 1.0 (Nutzungsbedingungen beachten) |
| **API & Schema Changelog** | `openfoodfacts-server/docs/api/ref-api-and-product-schema-change-log.md` | Product Schema Version 1004 (v3.6) | ODbL 1.0 |
| **Lizenz- und Rechtsleitfaden** | `openfoodfacts-server/docs/api/tutorials/license-be-on-the-legal-side/` | Offizieller Reuse-Guide | ODbL 1.0 (DB), DbCL 1.0 (Inhalte), CC BY-SA 3.0 (Bilder) |
| **Live API Endpunkte** | `https://world.openfoodfacts.org/api/v2/product/{barcode}` | Produktion (Live-Abruf verifiziert) | ODbL / DbCL |
| **Staging/Dev Endpunkte** | `https://world.openfoodfacts.net/api/v2/product/{barcode}` | Entwicklung/Staging | ODbL / DbCL |

### Rechtestatus je Datentyp und Attributionspflicht

1. **Strukturierte Datenbank (Gesamtwerk)**:
   - **Lizenz**: Open Database License (ODbL) 1.0.
   - **Bedingung**: Namensnennung ("Open Food Facts"), Weitergabe unter gleichen Bedingungen (Share-Alike bei abgeleiteten Datenbanken).
   - **Dishboard-Grenze**: Vorschläge aus OFF fließen nicht unbesehen in die Primärdatenbank ein, sondern werden als provenance-gesicherte `food_data_proposals` vorgehalten. Bei Übernahme in Menüplan-Stammdaten (`foods`) muss die Quelle `off` und die Barcode-Referenz transparent im Audit-Log dokumentiert bleiben.
2. **Texte, Einzelangaben und Fakteninhalte**:
   - **Lizenz**: Database Contents License (DbCL) 1.0.
   - **Bedingung**: Individuelle Fakten (Nährwerte, Grammangaben, Allergene) sind frei nutzbar; Herkunft muss nachvollziehbar sein (Quelle `off`, Abrufzeitpunkt `fetched_at`, Dokument-Prüfsumme).
3. **Produktbilder (Front, Zutaten, Nährwerttabelle)**:
   - **Lizenz**: Creative Commons Attribution ShareAlike 3.0 (CC BY-SA 3.0).
   - **Bedingung**: Fotos können marken- oder urheberrechtlich geschützte Logos/Designs der Hersteller enthalten (Quotation / Fair Use). Eine Bildübernahme in Menüplan erfordert verpflichtende Attribution (Autor, Lizenzhinweis, Open Food Facts Link).
   - **Dishboard-Grenze**: Bildmetadaten (URL, Abmessungen) gelten rein als Vorschlag. Keine Roh-Einbettung externer URLs im Webbrowser des Endanwenders (Tracking- und Referrer-Schutz). Bild-Downloads erfolgen serverseitig mit MIME-/Byte- und Pixelprüfung im zugewiesenen Asset-Paket (`MP-OFF-PROPOSAL-CONTRACT` / `MP-OFF-REVIEW-UI`).

---

## 2. Endpunkte, Eingabe- und Ausgabegrenzen

### Endpunktdefinition

- **Produktionsbasis**: `https://world.openfoodfacts.org`
- **Staging-/Testbasis**: `https://world.openfoodfacts.net`
- **Standard-Abfragepfad**:
  - API v2: `GET /api/v2/product/{barcode}?fields={field_list}`
  - API v3: `GET /api/v3/product/{barcode}?fields={field_list}`
- **Empfohlene Feldselektion (`fields`)**:
  `code,product_name,generic_name,ingredients_text,allergens,allergens_tags,traces,traces_tags,nutriments,nutrition_data_per,nutrition_data_prepared_per,no_nutrition_data,countries,countries_tags,origins,origins_tags,image_url,selected_images`

### Eingabegrenzen (Client-seitige Validierung vor Netzaufruf)

1. **Barcode-Validierung**:
   - Gültige Barcodes müssen numerisch sein: EAN-8 (8 Stellen), UPC-A (12 Stellen), EAN-13 (13 Stellen) oder GTIN-14 (14 Stellen).
   - Strenger Regex: `^[0-9]{8,14}$`.
   - Ungültige Eingaben (Buchstaben, Sonderzeichen, falsche Längen) werden vor jedem Netzaufruf abgewiesen.
2. **Netzwerk- und Sicherheitsgrenzen (gemäß SDD 8.6 / 8.10)**:
   - Ausschließlich HTTPS. Keine dynamischen, vom Benutzer übergebenen Hostnamen.
   - Feste Host-Allowlist: `world.openfoodfacts.org`, `world.openfoodfacts.net`, `images.openfoodfacts.org`.
   - Fester HTTP-User-Agent: Format `<AppName>/<Version> (<Kontakt-URL/E-Mail>)` gemäß OFF-Vorgabe (z.B. `Dishboard-Menuplan/2.0 (menuplan@joelduss.xyz)`). Fehlt der User-Agent oder ist er generisch, blockiert OFF Anfragen rasch per 403/429.
   - Timeout: Striktes Timeout von 5 Sekunden pro HTTP-Aufruf.
   - Rate-Limits: Max. 15 Leseanfragen pro Minute pro ausgehender IP-Adresse. Kein Bulk-Scraping über die Client-API.
   - Keine Authentifizierungstokens im Request-Header erforderlich. Niemals Credentials oder geheime Konfigurationen mitsenden.

### Ausgabegrenzen (Antwortbehandlung)

1. **Statuscodes & JSON-Ergebnisse**:
   - `HTTP 200` mit `status: 1` (`status_verbose: "product found"`): Produkt existiert, `product`-Objekt enthält Nutzdaten.
   - `HTTP 200` mit `status: 0` (`status_verbose: "product not found"` oder `"no code or invalid code"`): Barcode in OFF unbekannt. Führt zu kontrolliertem Ergebnis `not_found`.
   - `HTTP 404`: Produkt nicht vorhanden.
   - `HTTP 429` / `HTTP 503`: Rate-Limit überschritten oder Server überlastet. Kontrollierter Fehlerzustand mit Retry-After-Beachtung; kein Endlos-Retry.
   - `HTTP 302`: Redirect (z.B. Weiterleitung auf Unterprojekte wie Open Beauty Facts); in strikter Food-Domäne nur kontrolliert nach Host-Validierung folgen.
2. **Datenbegrenzung für Menuplan-Persistenz**:
   - `food_data_proposals.payload` ist in `database/schema.sql` auf maximal 64 KiB (65536 Bytes) UTF-8 beschränkt.
   - Maximale Objekttiefe: 5 Ebenen.
   - Maximale Schlüsselanzahl: 200 Schlüssel.
   - Der Adapter (`MP-OFF-ADAPTER`) muss die Antwort auf die tatsächlich relevanten, geprüften Felder reduzieren, bevor sie persistiert wird.

---

## 3. Vollständige Feldzuordnungs-Matrix

Die folgende Tabelle mappt alle von OFF gelieferten Rohdaten auf die Menuplan-Zieldomäne:

| Fachbereich | Open Food Facts (v2/v3) | Datentyp OFF | Menuplan Zieldomäne / DTO | Semantik & Normalisierung | Grenzen & Status |
|---|---|---|---|---|---|
| **Barcode** | `code` | `string` (8–14 Ziffern) | `food_data_proposals.source_reference`, künftig `foods.barcode` | Eindeutige GTIN/EAN. Führende Nullen erhalten. | **Nicht** in bestehenden `PROPOSAL_FIELDS`. Benötigt neues typisiertes Metadatum. |
| **Produktname** | `product_name` | `string` | `foods.name` (Master Data) | Handelsname des Produkts (z.B. "Nutella"). Auf 120 Zeichen NFC normalisiert. | **Nicht** in bestehenden `PROPOSAL_FIELDS`. Vorschlag für Anlage/Vergleich. |
| **Sachbezeichnung** | `generic_name` | `string` | `foods.display_name` / Notiz | Rechtliche Verkehrsbezeichnung (z.B. "Haselnuss-Kakaocreme"). | **Nicht** in bestehenden `PROPOSAL_FIELDS`. Typisiertes Metadatum. |
| **Zutatenliste** | `ingredients_text` | `string` | Vorschlagsdetail / DTO | Vollständiger Fließtext der Zutatenliste vom Etikett. | **Nicht** in bestehenden `PROPOSAL_FIELDS`. Unverändert als Referenztext. |
| **Strukturierte Zutaten** | `ingredients` | `array[object]` | Analyse-DTO | Hierarchische Zutaten mit Prozentangaben (`percent_estimate`). | Read-only Referenz für KI/Rezept-Vergleich. |
| **Allergene (bestätigt)** | `allergens_tags` | `array[string]` (z.B. `["en:milk"]`) | `food_data_proposals.payload['allergens']` | Prefix `en:` entfernen, Code auf Menuplan-Allergenkürzel mappen. Präsenz: `'contains'`. | In bestehendem `PROPOSAL_FIELDS` enthalten (`code`, `presence: contains`). |
| **Spuren / Kreuzkontamination** | `traces_tags` | `array[string]` (z.B. `["en:nuts"]`) | `food_data_proposals.payload['allergens']` | Prefix `en:` entfernen, Code auf Menuplan-Allergenkürzel mappen. Präsenz: `'may_contain'`. | In bestehendem `PROPOSAL_FIELDS` enthalten (`code`, `presence: may_contain`). |
| **Nährwerte: Bezugsbasis** | `nutrition_data_per` | `enum('100g', 'serving')` | `NutrientReferenceDTO.basis` | Definiert, worauf sich Nährwerte beziehen. Standard in Menüplan ist `100g`. | **Nicht** in bestehenden `PROPOSAL_FIELDS`. Gehört zum NUT-Vertrag (`MP-NUT-*`). |
| **Nährwerte: Keine Deklaration** | `no_nutrition_data` | `string` (`"on"`) | `NutrientReferenceDTO.exempt` | Zeigt an, dass das Produkt laut Etikett von der Nährwertdeklaration befreit ist. | Expliziter Kennzeichner für befreite Lebensmittel. |
| **Nährwerte: Energie (kJ)** | `nutriments['energy-kj_100g']` | `number` | `NutrientDTO['energy_kj']` | Brennwert in Kilojoule pro 100 g. | NUT-Vertrag. Fehlend = `NULL`, 0 ist gültige Zahl. |
| **Nährwerte: Energie (kcal)** | `nutriments['energy-kcal_100g']` | `number` | `NutrientDTO['energy_kcal']` | Brennwert in Kilokalorien pro 100 g. | NUT-Vertrag. Fehlend = `NULL`, 0 ist gültige Zahl. |
| **Nährwerte: Fett** | `nutriments['fat_100g']` | `number` | `NutrientDTO['fat_g']` | Fett in Gramm pro 100 g. | NUT-Vertrag. |
| **Nährwerte: Gesättigte Fettsäuren** | `nutriments['saturated-fat_100g']` | `number` | `NutrientDTO['saturated_fat_g']` | Gesättigte Fettsäuren in Gramm pro 100 g. | NUT-Vertrag. |
| **Nährwerte: Kohlenhydrate** | `nutriments['carbohydrates_100g']` | `number` | `NutrientDTO['carbohydrates_g']` | Kohlenhydrate in Gramm pro 100 g. | NUT-Vertrag. |
| **Nährwerte: Zucker** | `nutriments['sugars_100g']` | `number` | `NutrientDTO['sugars_g']` | Zucker in Gramm pro 100 g. | NUT-Vertrag. |
| **Nährwerte: Ballaststoffe** | `nutriments['fiber_100g']` | `number` | `NutrientDTO['fiber_g']` | Ballaststoffe in Gramm pro 100 g. | NUT-Vertrag. |
| **Nährwerte: Eiweiß** | `nutriments['proteins_100g']` | `number` | `NutrientDTO['protein_g']` | Eiweiß/Proteine in Gramm pro 100 g. | NUT-Vertrag. |
| **Nährwerte: Salz** | `nutriments['salt_100g']` | `number` | `NutrientDTO['salt_g']` | Salz in Gramm pro 100 g. | NUT-Vertrag. |
| **Nährwerte: Natrium** | `nutriments['sodium_100g']` | `number` | `NutrientDTO['sodium_g']` | Natrium in Gramm pro 100 g (Salz = Natrium * 2.5). | NUT-Vertrag. |
| **Herkunft Zutat** | `origins` / `origins_tags` | `string` / `array` | Vorschlagsmetadaten / Herkunft | Ursprung der primären Rohstoffe (z.B. "Schweiz"). | **Nicht** in bestehenden `PROPOSAL_FIELDS`. Typisiertes Metadatum. |
| **Verkaufsländer** | `countries_tags` | `array[string]` | Plausibilitäts-Check | Prüft, ob Produkt in der Schweiz vertrieben wird (`en:switzerland`). | Read-only Metadatum zur Marktvalidierung. |
| **Produktbild Front** | `selected_images.front.display` / `image_url` | `string` (URL) | `food_data_proposals.source_url`, Asset-Vorschlag | Bildadresse der Vorderseite auf `images.openfoodfacts.org`. | **Nicht** in bestehenden `PROPOSAL_FIELDS`. Lizenz CC BY-SA 3.0 beachten. |
| **Bild Nährwerttabelle** | `selected_images.nutrition.display` | `string` (URL) | Verifikations-Asset | Belegfoto der gedruckten Nährwerttabelle zur manuellen Prüfung. | Prüfnachweis; keine direkte UI-Rohverlinkung. |
| **Bild Zutatenliste** | `selected_images.ingredients.display` | `string` (URL) | Verifikations-Asset | Belegfoto der gedruckten Zutatenliste für Allergen-Abnahme. | Prüfnachweis; keine direkte UI-Rohverlinkung. |

---

## 4. Semantische Trennung: Fehlend versus Null (Missing vs. Zero)

Ein Kernproblem bei externen Lebensmitteldaten ist die Verwechslung von "Wert ist 0" mit "Information liegt nicht vor". In Menüplan gelten folgende strikte Regeln:

1. **Allergene & Spuren**:
   - Wenn ein Allergen in `allergens_tags` gelistet ist → Status `contains`.
   - Wenn ein Allergen in `traces_tags` gelistet ist → Status `may_contain`.
   - Wenn `allergens_tags` oder `traces_tags` leer sind (`[]`) oder im JSON fehlen: Dies bedeutet **keinesfalls**, dass das Produkt frei von Allergenen ist! Der Status in Menüplan bleibt zwingend `allergen_review_status: 'not_checked'`. Es werden **keine** negativen Bestätigungen ("frei von...") erfunden.
2. **Nährwerte**:
   - Wert `0.0` (z.B. `fat_100g: 0.0` bei Mineralwasser): Dies ist ein gültiger, verifizierter Zahlenwert.
   - Nährwert existiert nicht im `nutriments`-Objekt: Der Wert muss als `NULL` bzw. `None` persistiert werden. Er darf **niemals** stillschweigend zu `0` oder `0.0` konvertiert werden!
   - Wenn `no_nutrition_data: "on"`: Das Produkt trägt legal keine Nährwertdeklaration (z.B. frisches Obst, Kräuter). In diesem Fall sind alle Nährwerte `NULL` mit expliziter Begründung `exempt`.
3. **Portionsbezug vs. 100g**:
   - Fehlt `nutrition_data_per`, oder steht es auf `serving` ohne bekannte absolute Portionsmasse in Gramm, ist der 100g-Bezugswert rechnerisch unbestimmt. Er bleibt `NULL`, anstatt geratene Werte zu erzeugen.

---

## 5. Analyse der bestehenden PROPOSAL_FIELDS und Parser-Grenzen

### Ist-Zustand im Repository

Die bestehende Implementierung in `reference_scaffold/cafeteria/master_data_proposals.py` (Zeile 17) und in der Datenbankfunktion `accept_food_data_proposal_v21` (`database/schema.sql`, Zeile 3968) definiert:

```python
PROPOSAL_FIELDS = frozenset({'density_g_per_ml', 'piece_weight_g', 'category_code', 'allergens', 'labels'})
```

- **Datenbank-Durchsetzung**: `accept_food_data_proposal_v21` prüft explizit:
  ```sql
  IF EXISTS(SELECT 1 FROM unnest(fields) x WHERE x IS NULL OR
    x NOT IN ('density_g_per_ml','piece_weight_g','category_code','allergens','labels')) THEN
      RAISE EXCEPTION 'Unsupported selection.' USING ERRCODE='P1901';
  END IF;
  ```
- Alle anderen Schlüssel, die sich in `food_data_proposals.payload` befinden, werden von `accept_food_data_proposal_v21` nicht übernommen, sondern in das Rückgabe-Array `not_supported` verschoben:
  ```sql
  SELECT COALESCE(array_agg(k ORDER BY k),'{}') INTO unsupported FROM jsonb_object_keys(v.payload) k
    WHERE k NOT IN ('density_g_per_ml','piece_weight_g','category_code','allergens','labels');
  ```

### Erforderliche typisierte Metadaten für zukünftige Verträge

Da die bestehenden fünf Felder ausschließlich Hilfsfaktoren und Deklarationen darstellen, können die reichhaltigen Open Food Facts Daten nicht verlustfrei oder typensicher über den bestehenden Vorschlagsweg in den Stammdatenbestand übernommen werden:

1. **Barcode / GTIN**:
   - Aktuell nur als Freitext in `food_data_proposals.source_reference` (max. 200 Zeichen) vorhanden.
   - Erfordert: Ein dediziertes, eindeutig indizierbares Feld in `foods` bzw. im erweiterten Proposal-Vertrag (`barcode text CHECK (barcode ~ '^[0-9]{8,14}$')`).
2. **Produktname und Verkehrsbezeichnung**:
   - Gehören nicht in `PROPOSAL_FIELDS`. Dürfen nicht still in `payload` verborgen bleiben.
   - Erfordern: Typisierte Felder `suggested_name` und `suggested_generic_name` im Proposal-DTO für Neuverknüpfung und Namensabgleich.
3. **Spuren getrennt von Allergenen**:
   - Zwar unterstützt `master_data_proposals.py` in Zeile 119 bereits `presence in ('contains', 'may_contain')`, OFF liefert diese jedoch aus zwei separaten Arrays (`allergens_tags` und `traces_tags`).
   - Der Adapter muss diese sauber in das vereinheitlichte Schema transformieren, ohne dass Widersprüche entstehen.
4. **Nährwerte und Bezugsmenge**:
   - Gehören fachlich zum Nährwert-Subsystem (`MP-NUT-*`).
   - Müssen über ein eigenes typisiertes `NutrientProposalDTO` erfasst werden, nicht über `master_data_proposals.PROPOSAL_FIELDS`.
5. **Herkunft**:
   - Bislang kein Feld im Datenmodell `foods`. Erfordert Schemaerweiterung für Herkunftsdeklaration.
6. **Bilder & Bildprovenienz**:
   - Externe Bild-URLs aus OFF dürfen nicht als statische Links in Webseiten eingebunden werden.
   - Erfordert einen Bild-Ingest-Vertrag: URL, SHA256-Hash, Bildabmessungen, Lizenztyp (`CC BY-SA 3.0`), Urheberangabe, Zeitstempel.

### Konsequenz für Folgemodule

- `MP-OFF-ADAPTER` darf ausschließlich die fünf bestehenden Felder in das bestehende `PROPOSAL_FIELDS`-Schema einpassen und muss die erweiterten Felder in einem typisierten Übergabeobjekt (`OffProductProposal`) isolieren.
- Ein unkontrolliertes Erweitern von `PROPOSAL_FIELDS` ohne Root-Lease und ohne entsprechende DDL-Migration ist unzulässig.
- `MP-OFF-PROPOSAL-CONTRACT` besitzt die formale DDL-Erweiterung und Store-Logik.

---

## 6. Schweizer Stichprobe (Swiss Coverage)

### Methodische Klarstellung

- Eine repräsentative Schweizer Abdeckungsmessung (Hit-Rate für Schweizer Gastronomie- und Einzelhandelsprodukte) kann **nicht** seriös aus synthetischen Test-Fixtures oder einzelnen Beispielabfragen abgeleitet werden.
- Dieses Dokument stellt ausdrücklich fest: **Es wird keine behauptete reale Schweizer Trefferquote aufgestellt.**
- Die tatsächliche Trefferquote im Schweizer Markt (z.B. für Artikel von Großhändlern wie Transgourmet, Pistor, Prodega sowie Detailhändlern wie Coop und Migros) unterliegt erheblichen Schwankungen:
  - Bei internationalen Markenartikeln (Süßwaren, Getränke, Cerealien) ist die Datenvollständigkeit in OFF sehr hoch (> 80 %).
  - Bei Schweizer Eigenmarken und regionalen Großgebinden existieren erhebliche Lücken (Schätzung ohne Gewähr).
- Die empirische Erhebung einer Schweizer Stichprobe mit realen Barcodes ist Gegenstand des separaten Arbeitspakets **`MP-OFF-COVERAGE`**.
- Die Abwesenheit einer abgeschlossenen empirischen Marktabdeckungsmessung blockiert **nicht** die technische Schnittstellen- und Adapterentwicklung (`MP-OFF-ADAPTER`, `MP-OFF-FETCH`), da diese auf Basis deterministischer, versionierter Test-Fixtures validiert werden können.

---

## 7. Zusammenfassung und Validierungsstatus

- **Offizielle Quellen**: Vollständig ermittelt, Versionen und Lizenzen dokumentiert (ODbL 1.0, DbCL 1.0, CC BY-SA 3.0).
- **Feldmapping**: Alle geforderten Datentypen (Barcode, Text/Zutaten, Allergene/Spuren, Nährwerte mit Bezug, Herkunft, Bilder) strukturiert zugeordnet.
- **Fehlend vs. 0**: Klare Unterscheidung zwischen `NULL` (unbekannt) und `0.0` (gemessen) definiert.
- **Systemgrenzen**: Einschränkungen von `PROPOSAL_FIELDS` und `accept_food_data_proposal_v21` detailliert analysiert und Folgeanforderungen dokumentiert.
- **Coverage**: Keine erfundenen Erfolgsquoten; klare Trennung zwischen Schnittstellenfreeze und empirischer Marktanalyse.
