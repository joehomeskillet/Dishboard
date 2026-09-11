# Quellenanalyse der Tandoor-Lagerfunktionen

## 1. Metadaten und Rahmen

- **Arbeitspaket-ID:** `MP-BAS-STORAGE-TANDOOR-REVIEW`
- **Routing-WP:** `wp-e3783b8768d4`
- **Anforderungs-ID:** `BAS-001` (Stammdaten & Grundlagen; Abgrenzung zu `INV-001`)
- **Bearbeiter / Agent:** `antigravity-agy` (Antigravity CLI Worker)
- **Verwendetes Modell:** Gemini 3.8 Flash (High) (`gemini-3.8-flash-high`)
- **Datum:** 2026-09-11
- **Geprüfter Quell-Commit:** `e160ceecaee0b269924be600a6d01ecb0bd55e30` (Repository: [TandoorRecipes/recipes](https://github.com/TandoorRecipes/recipes/tree/e160ceecaee0b269924be600a6d01ecb0bd55e30))
- **Geprüfte Quellcodedatei:** `cookbook/models.py` ([Web-Ansicht](https://github.com/TandoorRecipes/recipes/blob/e160ceecaee0b269924be600a6d01ecb0bd55e30/cookbook/models.py), [Rohfassung](https://raw.githubusercontent.com/TandoorRecipes/recipes/e160ceecaee0b269924be600a6d01ecb0bd55e30/cookbook/models.py))
- **Lizenz:** GNU Affero General Public License Version 3 (AGPL v3, 19. November 2007) mit «Commons Clause» License Condition v1.0
  - Lizenzdatei im geprüften Commit: `LICENSE.md` ([Web-Ansicht](https://github.com/TandoorRecipes/recipes/blob/e160ceecaee0b269924be600a6d01ecb0bd55e30/LICENSE.md), [Rohfassung](https://raw.githubusercontent.com/TandoorRecipes/recipes/e160ceecaee0b269924be600a6d01ecb0bd55e30/LICENSE.md))
  - Klauselbedingung (Zitate aus `LICENSE.md:9-16`): *«Without limiting other conditions in the License, the grant of rights under the License will not include, and the License does not grant to you, the right to Sell the Software. For purposes of the foregoing, "Sell" means practicing any or all of the rights granted to you under the License to provide to third parties, for a fee or other consideration [...] a product or service whose value derives, entirely or substantially, from the functionality of the Software.»*
- **Rechtlicher und architektonischer Grundsatz:** Es wird **kein Code** aus Tandoor übernommen; es wird **keine Kompatibilität** behauptet (`recipes-sdd.md:1461-1462`, `docs/design/2026-09-06-bas-rec-data-contract.md:889-890`). Tandoor dient ausschliesslich als funktionale und ergonomische Referenz.

---

## 2. Gegenüberstellung der Tandoor-Strukturen und Dishboard-Zuordnung

Die folgende Tabelle analysiert jedes lagerbezogene Modell aus Tandoors `cookbook/models.py` auf Commit `e160ceec` und stellt es den Dishboard-Tabellen und -Slices gegenüber.

| Tandoor-Modell & Quellanker (`cookbook/models.py`) | Felder, Relationen & Constraints in Tandoor | Dishboard-Pendant & Architektur-Zuordnung | Begründung & wesentliche Unterschiede |
|---|---|---|---|
| **`InventoryLocation`**<br>(`cookbook/models.py:1362-1373`) | • `name`: `CharField(max_length=64)`<br>• `is_freezer`: `BooleanField(default=False)`<br>• `household`: `ForeignKey(Household, on_delete=models.PROTECT)`<br>• `created_by`: `ForeignKey(User, on_delete=models.CASCADE)`<br>• `created_at`: `DateTimeField(auto_now_add=True)`<br>• `updated_at`: `DateTimeField(auto_now=True)`<br>• `space`: `ForeignKey(Space, on_delete=models.CASCADE)`<br>• `objects = ScopedManager(space='space')` | **`storage_locations`**<br>(`BAS-001`, Stammdaten)<br>`database/schema.sql:3114-3127` | **Zuordnung: BAS-001 (Lagerort-Stammdaten).**<br>Beide Modelle definieren einen physischen/organisatorischen Lagerort.<br>• *Dishboard-Struktur:* `id`, `public_id`, `row_version`, `location_id` (Betriebsstandort), `code` (`^[A-Z][A-Z0-9_]{0,15}$`), `name` (max. 120 Zeichen), `sort_order` (1–9999), `active`, Zeitstempel und User-Audits.<br>• *Unterschiede:* Dishboard kennt kein `is_freezer`-Sonderflag und kein `household` (Gemeinschaftsgastronomie statt Privathaushalt). Mandantentrennung erfolgt über relationales `location_id` mit Fremdschlüsseln und RLS, nicht über Django-Scopes (`Space`). Dishboard schützt Mutationen über CAS (`row_version`). |
| **`InventoryEntry`**<br>(`cookbook/models.py:1375-1400`) | • `inventory_location`: `ForeignKey(InventoryLocation, on_delete=models.CASCADE)`<br>• `sub_location`: `CharField(max_length=64, blank=True, null=True)`<br>• `code`: `CharField(max_length=16, null=True, blank=True)`<br>• `amount`: `DecimalField(default=0, decimal_places=16, max_digits=32)`<br>• `unit`: `ForeignKey(Unit, on_delete=models.SET_NULL, null=True, blank=True)`<br>• `food`: `ForeignKey(Food, on_delete=models.CASCADE, null=True, blank=True)`<br>• `expires`: `DateField(null=True, blank=True)`<br>• `note`: `CharField(max_length=256, null=True, blank=True)`<br>• `created_by`: `ForeignKey(User, on_delete=models.CASCADE)`<br>• `created_at`, `updated_at`<br>• `space`: `ForeignKey(Space, on_delete=models.CASCADE)`<br>• Constraint: `UniqueConstraint(fields=['space', 'code'])` | **Geteilte Zuordnung:**<br>1. **`food_storage_locations`** (`BAS-001`) für Relation Food ↔ Ort (`database/schema.sql:3166-3171`)<br>2. **`inventory_movements` / `inventory_accounts`** (`INV-001`) für Bestand/Saldo (`operations-sdd.md:170-195`)<br>3. **`MP-INV-PREPARED-BATCH-PRODUCTION`** für Charge/MHD (`operations-sdd.md:217-224`) | **Architektonische Trennung in Dishboard:**<br>Tandoors `InventoryEntry` vermischt drei Ebenen in einer einzigen mutierbaren Zeile: Stammdatenzuordnung, Bestandsmenge und Chargenverfall.<br>• *Ebene 1 (BAS-001):* Die Zuordnung Food ↔ Lagerort ist in Dishboard eine reine Relation (`food_storage_locations`) ohne Mengenfelder.<br>• *Ebene 2 (INV-001):* Dishboard führt **keine** veränderliche Bestandsspalte. Bestand ist die Summe unveränderlicher Journalzeilen (`inventory_movements`).<br>• *Ebene 3 (Chargen):* Ablaufdaten und Chargencodes gehören in Dishboard zur kontrollierten Vorbereitungsproduktion mit unveränderlicher Chargen-UUID.<br>• *Löschverhalten:* Tandoor löscht Einträge kaskadierend (`CASCADE`); Dishboard schützt Integrität mit `RESTRICT` (`database/schema.sql:3170-3171`). |
| **`InventoryLog`**<br>(`cookbook/models.py:1402-1428`) | • `entry`: `ForeignKey(InventoryEntry, on_delete=models.CASCADE)`<br>• `booking_type`: `CharField(choices=[('add','Add'), ('remove','Remove'), ('move','Move')])`<br>• `old_amount`: `DecimalField(default=0, decimal_places=16, max_digits=32)`<br>• `new_amount`: `DecimalField(default=0, decimal_places=16, max_digits=32)`<br>• `old_inventory_location`: `ForeignKey(InventoryLocation, on_delete=models.CASCADE)`<br>• `new_inventory_location`: `ForeignKey(InventoryLocation, on_delete=models.CASCADE)`<br>• `note`: `CharField(max_length=256, null=True, blank=True)`<br>• `created_at`: `DateTimeField(auto_now_add=True)`<br>• `space`: `ForeignKey(Space, on_delete=models.CASCADE)` | **`inventory_movements`**<br>(`INV-001`, Bewegungsjournal)<br>`operations-sdd.md:170-195`, geplantes Paket `MP-INV-MOVEMENT-CORE` (`operations-wps.json:941-975`) | **Zuordnung: INV-001 (Bestandsbewegungsjournal).**<br>Beide Strukturen zeichnen Mengenänderungen und Umbuchungen auf.<br>• *Fundamentale Unterschiede:*<br>1. *Manipulationssicherheit:* Tandoor hängt Logs als Fremdschlüssel an den mutierbaren `InventoryEntry` mit `on_delete=CASCADE`. Wird der Eintrag gelöscht, wird die gesamte Historie vernichtet. Dishboards `inventory_movements` ist append-only; kein UPDATE, kein DELETE (`operations-sdd.md:188`).<br>2. *Buchungstypen:* Tandoor kennt nur `add`, `remove`, `move`. Dishboard kennt 6 exakte Buchungsarten (`receipt`, `issue`, `transfer_out`, `transfer_in`, `count_adjust`, `correction`).<br>3. *Transaktionssicherheit bei Transfers:* Dishboard bucht Umlagerungen atomar als verknüpftes Zeilenpaar (`transfer_out` am Quellort mit sign -1, `transfer_in` am Zielort mit sign +1) über `related_movement_public_id` (`operations-sdd.md:185, 199`). Tandoors `move` modifiziert nur einen Eintrag.<br>4. *Idempotenz:* Dishboard verlangt `request_uuid`, `request_hash` und liefert Beleg `receipt_uuid` (`operations-sdd.md:182`). |
| **`Household`**<br>(`cookbook/models.py:339-348`) | • Gruppierung von Benutzern innerhalb eines `Space` für Einkaufslisten und Vorratskammern. | **Keine Zuordnung.** | Dishboard bedient Bildungsgastronomie, Mensen und Grossküchen (`locations`), keine Privathaushalte. Ein Haushaltskonstrukt existiert nicht und wird nicht benötigt. |
| **`Space` & `ScopedManager`**<br>(`cookbook/models.py:350-395`) | • Django-Scopes-Modell zur Multi-Tenancy-Isolation (`objects = ScopedManager(space='space')`).<br>• Kaskadierende Löschung aller Bestände bei Space-Löschung (`models.py:378-379`). | **Keine Zuordnung.** | Dishboard löst Mandantentrennung auf Datenbankebene über `locations`-Fremdschlüssel (`location_id bigint NOT NULL REFERENCES locations(id)` in `schema.sql:3121, 3136, 3167`) sowie PostgreSQL-Rollenberechtigungen, nicht über ein Python-Scope-Framework. |
| **`Food.onhand_users`**<br>(`cookbook/models.py:790`) | • `onhand_users = models.ManyToManyField(User, blank=True)` am Lebensmittelmodell zur Kennzeichnung privater Vorräte («Habe ich zu Hause»). | **Keine Zuordnung.** | In der professionellen Gemeinschaftsgastronomie gibt es keine privaten Vorräte einzelner Benutzer. Vorräte gehören ausschliesslich dem Betrieb/Standort (`location_id`). |
| **Kopplung an Einkaufslisten**<br>(`cookbook/models.py:1330-1350`, `ShoppingListEntry`) | • Direkte Verknüpfung zwischen Rezept, Zutat, Einkaufsliste und Bestandsprüfung. | **Keine Zuordnung in BAS.**<br>Entkoppelte Bedarfsrechnung in `ORD-001` (`operations-sdd.md:247`). | Dishboard entkoppelt Einkaufsvorschau strikt von automatischen Buchungen. Fehlender Saldo erzeugt den Status `bestand_unbekannt` und niemals eine geratene Nullabbuchung (`operations-sdd.md:247`). |

---

## 3. Vertiefte architektonische Analyse

### 3.1 Fundamentaler Grundsatz: Lagerzuordnung ≠ Bestand

Der wichtigste strukturelle Unterschied zwischen Tandoor und Dishboard liegt in der Trennung von Zuordnung und Bestand:

1. **Lagerort und Zuordnung gehören zu BAS-001 (Stammdaten):**
   - Die Tabelle `storage_locations` (`database/schema.sql:3114-3127`) definiert, welche physischen Räume oder Stationen an einem Standort existieren (z. B. «Trockenlager», «Kühlraum Fleisch», «Tiefkühler 1»).
   - Die Zuordnungstabelle `food_storage_locations` (`database/schema.sql:3166-3171`) legt fest, an welchen Lagerorten ein bestimmtes Lebensmittel gelagert werden darf bzw. standardmässig geführt wird:
     ```sql
     CREATE TABLE IF NOT EXISTS food_storage_locations (
         location_id bigint NOT NULL,
         food_id bigint NOT NULL,
         storage_location_id bigint NOT NULL,
         PRIMARY KEY(food_id, storage_location_id),
         FOREIGN KEY(location_id, food_id) REFERENCES foods(location_id, id) ON DELETE RESTRICT,
         FOREIGN KEY(location_id, storage_location_id) REFERENCES storage_locations(location_id, id) ON DELETE RESTRICT
     );
     ```
   - In Schema 27 (`MP-BAS-SCHEMA27`, `recipes-sdd.md:231-232, 666-671`) gilt die Pflicht: Jedes Lebensmittel muss mindestens einem aktiven Lagerort zugewiesen sein.
   - **Diese Zuweisung ist ausdrücklich kein Bestand!** Die Tabelle enthält weder ein Mengenfeld noch eine Einheit.
   - Solange kein INV-001-Journal vorliegt, gilt überall in der Benutzeroberfläche die verbindliche Invariante: Anzeige von **`Kein Bestand erfasst`**, niemals der Wert `0` oder ein leeres Feld (`recipes-sdd.md:232-234, 671`, `operations-sdd.md:166, 201`).

2. **Mengen, Buchungen und Salden gehören ausschliesslich zu INV-001 (Warenfluss):**
   - Weder die Lebensmitteltabelle `foods` (`database/schema.sql:3129-3156`) noch `food_storage_locations` besitzen Spalten wie `stock`, `balance`, `amount` oder `quantity_on_hand` (`operations-sdd.md:166, 212`).
   - Bestände existieren nicht als veränderliche Zahlen in Stammdatentabellen, sondern werden im geplanten Paket `MP-INV-MOVEMENT-CORE` (`operations-wps.json:941-975`, `operations-sdd.md:162-224`) als Saldo über das unveränderliche Bewegungsjournal `inventory_movements` berechnet:
     $$\text{Saldo} = \sum (\text{sign} \times \text{normalized\_base\_quantity})$$
   - Beim ersten bestätigten Zugang fixiert `inventory_accounts` die unveränderliche Basiseinheit und Kontokontext (`operations-sdd.md:180-181, 190`).
   - Eine nachträgliche Änderung der Stammdaten-Einheit auf `foods` oder eine Anpassung von Dichte/Stückgewicht verändert niemals historische Buchungen oder berechnete Salden (`operations-sdd.md:190, 213`).

### 3.2 Tandoor-Konzepte: Abgrenzung zwischen BAS-001 und INV-001

| Funktionaler Aspekt | Tandoor-Realisierung | Dishboard BAS-001 | Dishboard INV-001 (geplant) |
|---|---|---|---|
| **Lagerort-Definition** | `InventoryLocation` (Name, Freezer-Flag) | `storage_locations` (Code, Name, Sortierung, Aktiv-Status) | Keine Definition; referenziert `storage_locations_id` |
| **Lebensmittel ↔ Lagerort** | `InventoryEntry.inventory_location` + `food` (kombiniert mit Menge) | `food_storage_locations` (reine Pflichtzuordnung ohne Menge) | Validierungsbedingung: Buchung nur auf aktiver Zuordnung erlaubt |
| **Bestandsführung** | Modifizierbares `amount`-Feld in `InventoryEntry` | **Streng verboten**; keine Bestandsspalte in Stammdaten | Berechneter Saldo aus `inventory_movements` in fixierter Kontobasis |
| **Verlaufsaufzeichnung** | `InventoryLog` (`add`, `remove`, `move`) als Child von `InventoryEntry` | Nicht in BAS | `inventory_movements` (Append-only, 6 Buchungsarten, Transaktionspaare bei Transfer) |
| **Inventur / Zählung** | Nicht vorhanden (manuelles Überschreiben von `amount`) | Nicht in BAS | `inventory_counts` (Status draft/posted, CAS, Differenzbuchung) |
| **Chargen & Haltbarkeit** | `expires` und `code` direkt am `InventoryEntry` | Nicht in BAS | `MP-INV-PREPARED-BATCH-PRODUCTION` (Herstelldatum, optionales MHD, Rezeptpin) |

### 3.3 Was Dishboard bewusst nicht übernimmt

Aus der Analyse der Tandoor-Quelltexte (`cookbook/models.py` auf Commit `e160ceec`) ergeben sich folgende bewusste Nicht-Übernahmen:

1. **Keine veränderlichen Bestandsdatensätze (`InventoryEntry`):**
   In Tandoor wird bei einer Bestandsänderung der Datensatz `InventoryEntry` direkt mutiert (`amount` wird überschrieben). In einem professionellen Gastronomiebetrieb verletzt dies die Nachvollziehbarkeit, Revisionssicherheit und CAS-Garantien. Dishboard setzt auf ein striktes Buchungsjournal ohne `UPDATE` und `DELETE`.
2. **Keine kaskadierende Löschung (`on_delete=models.CASCADE`):**
   In Tandoor führt das Löschen eines `InventoryEntry` zum automatischen Löschen aller zugehörigen `InventoryLog`-Einträge (`cookbook/models.py:1412`). In Dishboard gilt strikt `ON DELETE RESTRICT` für Stammdatenreferenzen (`database/schema.sql:3170-3171`), um Audit-Verluste zu verhindern.
3. **Keine Freitext-Unterlagerorte (`sub_location`):**
   Tandoor erlaubt ein beliebiges Textfeld `sub_location` (max. 64 Zeichen). Dishboard verlangt klar definierte, standortbezogene Lagerorte mit normiertem Code (`database/schema.sql:3122`).
4. **Keine privaten Haushaltsstrukturen (`Household`, `onhand_users`):**
   Tandoors Modelle richten sich an Mehrpersonenhaushalte (`cookbook/models.py:1365`). Dishboards Mandantenmodell basiert auf Grossküchen- und Schulstandorten (`locations`), bei denen Vorräte institutionell verwaltet werden.
5. **Kein Python-Framework-Scoping (`Space`, `django-scopes`):**
   Dishboard sichert Mandantengrenzen durch PostgreSQL-Fremdschlüssel (`location_id`), CHECK-Constraints und serviceorientierte Berechtigungsprüfungen (`database/permissions.sql`), nicht durch thread-lokale Django-Scope-Manager.
6. **Keine automatische Bestandsabbuchung durch Menü- oder Wochenplanung:**
   In Tandoor besteht eine enge Verzahnung zwischen Rezepten, Mahlzeitenplan und Vorratskammer. In Dishboard gilt als Kerninvariante: **Planänderung, Portionsänderung, Rezept-Freeze oder CSV-Import erzeugen niemals Bestandsbuchungen** (`recipes-sdd.md:1454`, `operations-sdd.md:166, 203`). Jeder Verbrauch erfordert eine bewusste, autorisierte Buchungsaktion im INV-001-Journal.

---

## 4. Rechtliche Bewertung und Verzicht auf Kompatibilität

- **Lizenzlage:**
  Tandoor Recipes wird unter der GNU Affero General Public License Version 3 (AGPL v3) in Verbindung mit der «Commons Clause» License Condition v1.0 vertrieben (`LICENSE.md:9-16`).
  Die Commons Clause schliesst das Recht aus, die Software oder daraus abgeleitete Produkte entgeltlich zu verkaufen, zu hosten oder als bezahlte Dienstleistung anzubieten. Sie ist damit eine Non-Free/Source-Available-Lizenzbedingung.
- **Konsequenz für Dishboard:**
  Eine Übernahme von Quelltext, DDL-Schnipseln oder Klassenstrukturen aus Tandoor in Dishboard verbietet sich aus lizenzrechtlichen Gründen zwingend.
- **Keine Kompatibilität:**
  Es wird zu keinem Zeitpunkt eine Binär-, Schema- oder Import-/Exportkompatibilität zu Tandoors Lagerstrukturen hergestellt oder behauptet (`recipes-sdd.md:677-678, 1461-1462`). Tandoors Datenstrukturen eignen sich weder für die Anforderungen der Schul- und Betriebsgastronomie noch für die von Dishboard garantierte Unveränderlichkeit des Revisions- und Buchungsledgers.

---

## 5. Nicht geprüft

Gemäss Arbeitsauftrag beschränkte sich diese Analyse auf den Quelltext der Backend-Modelle und Lizenztexte auf Commit `e160ceecaee0b269924be600a6d01ecb0bd55e30`. Folgende Bereiche wurden **nicht** geprüft:
1. **Frontend-Komponenten von Tandoor:** Die Vue3-Implementierung der Lager- und Inventuransichten (`vue3/src/...`) wurde nicht analysiert.
2. **REST-API-Controller von Tandoor:** Serializer und Viewsets (`cookbook/views/api.py` etc.) für Inventory wurden nicht auf Validierungslogik hin untersucht.
3. **Laufzeit- und Integrationsverhalten:** Es wurde kein lokaler Tandoor-Server instanziiert und kein Testdurchlauf gegen eine laufende Tandoor-Instanz durchgeführt.
4. **Performance und Mengengerüste:** Das Verhalten von Tandoors `InventoryLog` bei Millionen von Buchungszeilen wurde nicht empirisch gemessen.
5. **Neuere Commits oder Releases:** Änderungen im Tandoor-Repository nach Commit `e160ceecaee0b269924be600a6d01ecb0bd55e30` wurden nicht berücksichtigt.
