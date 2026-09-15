# Register der 145 ursprünglichen SDD-Arbeitspakete

Stand der Übertragung: 13. September 2026. Dieses Register übernimmt die drei abgeschlossenen Audits zum historischen Ausgangsstand `2fa44dea36675692bfb8ad4b681dca73dba06737` / Schema 30. Es ist kein neuer Audit und keine aktuelle Laufzeit- oder Abnahmebestätigung.

Manifeststatus und auditierte Ist-Einordnung bleiben getrennt. `DEPLOYED` beweist keine vollständige fachliche Abnahme; `PLANNED` kann bereits gelieferte Teile enthalten. Die nächste Aktion stammt aus dem jeweiligen Audit. Es werden weder WP-JSON-Status noch ursprüngliche Anforderungen geändert oder pauschal als `ACCEPTED` eingestuft.

Die ursprünglichen 145 IDs stehen je genau einmal in den Tabellen: 37 Operations, 43 Rezepte/Grundlagen und 65 Oberfläche/Zugriff/Abnahme. Kommende Fable-UI-WPs werden separat ergänzt und nicht in diese 145 eingerechnet. Weitere Auditvorschläge ohne ursprüngliche ID bleiben in ihren Quellreports.

## Quellen und Leseschlüssel

- **O:** [Operations-Audit](/nvmetank1/projects/rag-stack/.claude/reports/wp-4a3597a72ed7.md); Originalmanifest [operations-wps.json](../backlog-0909/operations-wps.json).
- **R:** [Rezept-Audit](/nvmetank1/projects/rag-stack/.claude/reports/wp-20bbdcac693e.md); Originalmanifest [recipes-wps.json](../backlog-0909/recipes-wps.json).
- **S:** [Surface-Audit](/nvmetank1/projects/rag-stack/.claude/reports/wp-855e496d2bb5.md); Originalmanifest [surfaces-wps.json](../backlog-0909/surfaces-wps.json).

`O:10`, `R:15` oder `S:19` bezeichnet die konkrete Zeile der WP-Tabelle im jeweiligen Quellreport. Surface-Gruppen wurden auf einzelne Original-IDs aufgeteilt; ihre gemeinsame Auditbewertung bleibt eine Gruppenbewertung. SDD-Anker, vollständige Besitzverträge, Prioritäten und Abhängigkeiten stehen in den Quellen. Vor Writerstart gelten [START](../backlog-0909/START.md), [Ausführungsvertrag](../backlog-0909/execution-contract.md), aktueller UI-Prompt sowie erneut vergebene Dateileases; alte Platzhalter reservieren keine Migration.

## Operations — 37 IDs

Manifest: 3 READY, 30 PLANNED, 4 AWAITING_EXTERNAL.

| Original-ID | Manifeststatus | Auditierte Ist-Einordnung | Nächster Schritt / Blocker laut Audit | Quelle |
|---|---|---|---|---|
| MP-CALC-COST-CORE | DEPLOYED | Abnahme 15.9.: `f75bc3c` im Livestand `47428b7`; Root-Nachprüfung `test_cost_calc.py` + `test_quantities.py` 111 passed (`operations-wps.json` `acceptance_2026_09_15`). | Keine UI-/Persistenzanbindung; Küchenabnahme extern offen. | O:11 |
| MP-CALC-PATIENT-GUARD | PLANNED | In HEAD: `c72acc1`; Autorbericht 22 Tests zweimal. End-to-end Preisfreiheit ist dadurch nicht vollständig abgenommen. | DTO-Deny, Altpatientensnapshot, staff_guest-Preise; HTML/PDF-Kostenausschluss zuordnen. | O:12 |
| MP-CALC-PRICE-LEDGER | PLANNED | Vorgesehener Store/Tests fehlen. Datierte immutable Preisrevisionen, CAS/ACL/Migration fehlen als Lieferbeleg. | Zwei konkurrierende Editionen, Intervallgrenzen, Altbytes, PG-Upgrade/Restore/ACL. | O:13 |
| MP-CALC-RECIPE-PROJECTION | PLANNED | `recipe_cost.py` fehlt; Kosten aus exakt gewählter Rezept-/Preisrevision. | 250 G × 4 CHF/KG = 1 CHF; Preview ohne Writes, alte Preisedition stabil. | O:14 |
| MP-CALC-PREPARED-GRAPH | PLANNED | Graphkostenprojektion fehlt. Historische Closure/Hashprüfung und eindeutige Kostenart nötig. | Geteilter Enkel, doppelte Mengenverwendung, Limits/Zyklus; direkter Preis und Expansion nie addieren. | O:15 |
| MP-CALC-MENU-PROJECTION | PLANNED | `menu_cost.py` fehlt. Gebundene Revision und Planportion auswerten. | Pin/Hash/Zielportion; ungebundene Zeile incomplete; Publikationsbytes unverändert. | O:16 |
| MP-CALC-RULES-SUGGEST | PLANNED | Regelstore fehlt; Vorschlag und ausdrückliche Übernahme noch offen. | Vorschau schreibt keinen Verkaufspreis; bewusste Übernahme mit Item-/Wochen-CAS. | O:17 |
| MP-CALC-CALCULATION-RECEIPTS | PLANNED | `cost_receipts.py` fehlt. Unveränderliche Inputs/Ergebnisse einschließlich Quelleneditionen erforderlich. | Replay einmalig; Preis/Faktor/Pin/Regeländerung lässt alte Belegbytes und Ergebnis gleich. | O:18 |
| MP-CALC-ADMIN-UI | PLANNED | Kalkulationsroute/-template fehlen. | Reale Editorrechte; Patient404; CSRF/CAS/NoJS; vorgegebene Browsermatrix. | O:19 |
| MP-CALC-KITCHEN-ACCEPTANCE | AWAITING_EXTERNAL | Abnahmedokument fehlt; echte Referenzgerichte/Preise und zuständige Küche fehlen als Beleg. | Küche bestätigt Referenzrechnung mit Schwund, Portionen und Preisvorschlag. | O:20 |
| MP-INV-MOVEMENT-CORE | PLANNED | `inventory_store.py` fehlt. Lagerorte aus Import sind kein Bestandsjournal. | 5−1 KG = 4000 G; echter konkurrierender Abgang; Replay, ACL, keine Überziehung. | O:21 |
| MP-INV-BALANCE-READ | PLANNED | `inventory_reads.py` fehlt. Unbekannt versus bestätigte Null erfassen. | Ohne Journal/Count unbekannt; posted Count0 bekannt; historische Basis stabil. | O:22 |
| MP-INV-TRANSFER | PLANNED | Transferwriter fehlt. | Beide Buchungsseiten/Audit atomar; gleiche UUID einmalig; Lockreihenfolge. | O:23 |
| MP-INV-COUNT-CORRECTION | PLANNED | Count-/Korrekturvertrag fehlt als Implementierung. | Count5→3 bucht −2; Count3→3 posted mit Receipt ohne Movement; erster Count0 erfasst. | O:24 |
| MP-INV-NO-PLAN-DEBIT | PLANNED | Vorgesehener Regressionstest fehlt; sinnvoll erst mit Journal. | Plan, Portionsänderung, Freeze und Import erzeugen jeweils keine Bewegung. | O:25 |
| MP-INV-ADMIN-UI | PLANNED | Inventurroute/-template fehlen. Food-Karten-Anschluss ist nicht in dessen Besitz, siehe Lücke unten. | Zugang/Abgang/Transfer/Count über echte Formulare; unbekannter Bestand sichtbar. | O:26 |
| MP-INV-DEMAND-COUPLING | PLANNED | `demand_netting.py` fehlt. | max(0, Bedarf−bekannter Bestand); unbekannt/unmöglich konvertierbar bleibt markiert. | O:27 |
| MP-INV-PREPARED-BATCH-PRODUCTION | PLANNED | Chargen-/Produktionsmodule fehlen. | Dieselbe Charge an zwei Tagen; Inputs/Output atomar; Replay; MHD manuell; Altjournal unverändert. | O:28 |
| MP-ORD-SUPPLIER-ARTICLE | PLANNED | `order_store.py` fehlt; `foods.source_kind=supplier` erfüllt keinen Artikelkatalog. | Standort/Actor/CAS, Artikelreferenzen, Archivierung und unveränderte Herkunft. | O:29 |
| MP-ORD-BASKET-DRAFT | PLANNED | Korbwriter fehlt. | Manueller Korb bleibt draft; CAS/No-op; kein Versand. | O:30 |
| MP-ORD-EXPORT-PREVIEW | PLANNED | `order_export.py` fehlt. | Formelzellen neutralisiert; Vorschau und Download verwenden identische Bytes. | O:31 |
| MP-ORD-ADMIN-PREVIEW | PLANNED | Bestellroute/-template fehlen; ohne Lieferantenanschluss lieferbarer erster Ablauf. | Editor pflegt Korb; CSV ohne BESTELLEN/Intent; signierter Kontext/CAS/NoJS. | O:32 |
| MP-ORD-DEMAND-LINK | PLANNED | Bedarf→Korb-Anschluss fehlt. | Unbekannter Bestand sichtbar; stale Korb409; weder Movement noch Sendung. | O:33 |
| MP-ORD-SEND-RIGHTS | AWAITING_EXTERNAL | Anschlussvertrag/-freigabe fehlt als Artefakt. | Berechtigter Transport, Receipt, Idempotenz/Statusabfrage und unknown_result dokumentiert. | O:34 |
| MP-ORD-CONFIRM-SEND | PLANNED | Versandmodule fehlen; darf nicht aus CSV-Download abgeleitet werden. | Admin+BESTELLEN; langlebiger Intent; Replay; Crash vor/nach Claim/Versand; echter autorisierter Adapter. | O:35 |
| MP-PKS-RIGHTS-SCOPE | READY | Historischer Kurzbericht vorhanden; genanntes `pks-rights.md` fehlt in HEAD, kein Commit/Quelleninventar im Bericht. Erst Artefakt wiederbeschaffen. | Quelle/Datum und offene versus belegte Rechte unabhängig prüfen. | O:36 |
| MP-PKS-EXPORT-FIXTURE | AWAITING_EXTERNAL | Berechtigte Datei/Version/Hash fehlen. | Originalbytes ≤5 MiB, SHA256/Version und Rechtsbeleg. | O:37 |
| MP-PKS-FIELD-MAP | PLANNED | Mapping fehlt; durch echte Fixture blockiert. | Jedes Pflichtfeld zugeordnet oder explizites Issue; keine Mengenverluste. | O:38 |
| MP-PKS-PREVIEW-ADAPTER | PLANNED | `pks_import.py` fehlt. | Autorisierte Fixture→RecipeImportPreview; ungültige Dateien/Dubletten; kein DBwrite. | O:39 |
| MP-PKS-BATCH-TAKEOVER | PLANNED | PKS-Uploadroute fehlt; nativer Rezeptimport ersetzt den Adapter nicht. | Upload→Preview→bestätigte bestehende Batch-TX; stale409; Replay ohne Zweitanlage. | O:40 |
| MP-TRN-LICENSE-SCOPE | READY | Historischer Kurzbericht vorhanden; `trn-license.md` fehlt in HEAD, kein Commit/Quelleninventar im Bericht. | Artefakt wiederbeschaffen; eigene Quellen und nicht lizenzierter Fremdbestand getrennt prüfen. | O:41 |
| MP-TRN-GLOSSARY-MODEL | PLANNED | `glossary_store.py` fehlt. | Fünf Sprachen; reviewed unvollständig400; vollständiger draft/rejected erlaubt; CAS/Provenienz. | O:42 |
| MP-TRN-CRUD-UI | PLANNED | Glossarroute/-template fehlen. | Explizites Review; Editorrechte; vollständiger Entwurf wird nicht automatisch reviewed. | O:43 |
| MP-TRN-RECIPE-MENU-APPLY | PLANNED | `glossary_apply.py` fehlt; Rezept-/Menüconsumer noch anzuschliessen. | Exakter reviewed-Vorschlag; ausdrückliches Speichern/CAS; historische Revision/PDF unverändert. | O:44 |
| MP-OPS-CORE-REGRESSION | PLANNED | Bericht/Commit `4027d1b`: 166 Tests zweimal; Commit nicht in HEAD. `test_capture_ops_live_proof.py` ausdrücklich nicht ausgeführt. | Vorhandenes Artefakt prüfen/integrieren; fehlenden Capture-Beleg getrennt nachholen. | O:45 |
| MP-OPS-NO-THIRD-AREA | PLANNED | Bericht/Commit `9a9fc81`: 71 Tests zweimal, zusätzlich vier fokussiert; Commit nicht in HEAD. | Vorhandene Profilbelege prüfen: zwei Codes, Rename nur display_name, Rechte/URLs gleich. | O:46 |
| MP-OPS-DATED-EXCEPTION-ACCEPTANCE | AWAITING_EXTERNAL | Echte datierte Fachabnahme fehlt; ausgelieferte OPS-Seite und synthetische Regression ersetzen sie nicht. | Derselbe Feiertags-/Betriebsfall in Admin, Public, Signage, HTML-Druck, Wochen-PDF und API-Snapshot. | O:47 |

## Rezepte und Grundlagen — 43 IDs

Manifest: 24 PLANNED, 3 IN_PROGRESS, 4 READY, 4 AWAITING_EXTERNAL, 3 REVIEWED_LOCAL, 5 DEPLOYED (Stand 14.9.).

| Original-ID | Manifeststatus | Auditierte Ist-Einordnung | Nächster Schritt / Blocker laut Audit | Quelle |
|---|---|---|---|---|
| MP-BAS-SCHEMA27 | DEPLOYED | Im Schema30-Livequellstand enthalten. Status korrigiert 14.9.: Migration 0024 (v27) ist Voraussetzung der aktuellen Live-Schemaversion 33 (`recipes-wps.json` `delivery_2026_09_14`); besondere PG18-Abnahme unten weiterhin getrennt. | vorhandene Migration-/Releasebelege zuordnen. | R:15 |
| MP-BAS-FOUNDATIONS | IN_PROGRESS | Consumer und zugehörige Tests vorhanden; aktuelle Grundlagenkorrekturen ausgeliefert. Keine Neuimplementierung. | Pflichtlager, Pin und No-op-Belege bündeln. | R:16 |
| MP-REC-BINDINGS | IN_PROGRESS | Backendbindung integriert; aktueller Release enthält Menübindungsregression. | drei Wege in BINDINGS-ACCEPT vollständig zuordnen. | R:17 |
| MP-REC-DATA-DRAFTS | REVIEWED_LOCAL | Datensatz integriert und über Folgepaket importiert. | Dataset-/Importprovenienz verbinden. | R:18 |
| MP-REC-PDF-RELEASE | REVIEWED_LOCAL | PDF bereits ausgeliefert; benannter Live-Abnahmebericht fehlt. | authentifizierten tatsächlichen Rezept-PDF-Download öffnen und prüfen. | R:19 |
| MP-REC-IMPORT-PARSER | REVIEWED_LOCAL | Integriert, produktiver Import nutzt ihn. | bestehenden Parser-/Importbeleg referenzieren. | R:20 |
| MP-REC-SNAPSHOT-V2 | IN_PROGRESS | Reader, Skalierung, Revision-/PDF-Consumer vorhanden; `ac424a6`, `02f64b2` integriert. | besondere Historien-/PG18-Belege in Releaseabnahme nachweisen. | R:21 |
| MP-REC-FREEZE-V2 | DEPLOYED | `01b97e0` samt Freeze-DB-Test integriert; produktiver Prepared-Pin-Import vorhanden. Status korrigiert 14.9.: Code vollständig commitet in Live-Release 7d0595d (`recipes-wps.json` `delivery_2026_09_14`). | Originalkontext/Childhash-Belege bündeln. | R:22 |
| MP-REC-BINDING-UI | DEPLOYED | Menüeditor und Browsertests vorhanden; Root14 im Release29-Bericht. Status korrigiert 14.9.: Code vollständig commitet in Live-Release 7d0595d (`recipes-wps.json` `delivery_2026_09_14`). | exakte Revision, Ablösen, Copy/CSV in Gesamtabnahme. | R:23 |
| MP-REC-COMPONENT-FOOD-UI | READY | Auswahl-/Writer-/Browserdateien vorhanden; keine erneute Vergabe. | Foodauswahl, Rücklesen und ausdrückliches Ablösen zuordnen. | R:24 |
| MP-REC-DISH-TEMPLATE-WRITER | PLANNED | `739713c` integriert; 32 Vorlagen produktiv über nativen Writer. | CRUD/CAS/Archivierung in Gesamtabnahme. | R:25 |
| MP-REC-BINDINGS-ACCEPT | PLANNED | Benannter Gesamtbericht fehlt; einzelne | Gates ersetzen vollständige Kriterienzuordnung nicht. Gate: alle drei Wege, vollständige Publikations-/Review-/Copyregression und unveränderter Publikationshash. | R:26 |
| MP-REC-RICHTEXT-DECISION | READY | Bericht `5fa04c5` vorhanden: Empfehlung Klartext, Nutzerentscheid offen. | Entscheidung dokumentieren; keine neue Untersuchung anfangen. | R:27 |
| MP-BAS-STORAGE-TANDOOR-REVIEW | READY | Analyse `e40c18d` plus Quellenkorrektur `0260e41` integriert. | Berichtabnahme/Statusnachtrag. | R:28 |
| MP-REC-IMPORT-BATCH | PLANNED | Persistenter Batch, SQL, Store, Route und Tests vorhanden. | bestehende Batch-/Browserbelege zuordnen. | R:29 |
| MP-REC-IMPORT-COMMIT | PLANNED | Native atomare Übernahme produktiv bewiesen. | vorhandene Authz/CAS/Replay-Belege zuordnen; nicht erneut importieren. | R:30 |
| MP-REC-IMPORT-XLSX-INPUT | AWAITING_EXTERNAL | Entscheidungsdatei fehlt; reales berechtigtes Exportbeispiel und Format-/Dependencyentscheid fehlen. | Dateiherkunft, Spalten, Format und Leseweg festhalten. | R:31 |
| MP-REC-IMPORT-XLSX | PLANNED | Adapter und Test fehlen. | reales XLSX → korrigierbare Vorschau → bestehender Batch; keine Makros/zweite Persistenz. | R:32 |
| MP-REC-SCHEMAORG-ADAPTER | PLANNED | `092a029` integriert; Autor12/12, ausschließlich reine Tests als Aufrufer. | unabhängigen Adapterbeleg zuordnen; URL-Feature bleibt Folge-WP. | R:33 |
| MP-REC-URL-FETCH | PLANNED | Fetchdatei/-tests fehlen; kein tatsächlicher Webimport. Microdata und Routeanschluss ebenfalls in diesem WP. | öffentliche HTTPS-Quelle → Preview/Commit; DNS-/Redirect-/Bytegrenzen und interne Ziele abweisen. | R:34 |
| MP-REC-AI-EXTRACTION | PLANNED | `3ee468c` integriert; Autor6/6, keine Produktaufrufer. | reine Adapterabnahme und Originalprovenienz bei Folgeanschluss. | R:35 |
| MP-REC-AI-PROVIDER | AWAITING_EXTERNAL | Providerdatei/-tests fehlen; Anbieterfreigabe fehlt. | Nach Freigabe: Dokument → Unsicherheit → manuelle Batchübernahme, keine automatische Allergenbestätigung. | R:36 |
| MP-REC-SEARCH-FTS | INTEGRATED | 15.9.: Suchfeld «Suche» + gewichtetes Lesezeit-Suchdokument ohne Schemaänderung (Root-Entscheid F2, `recipes-wps.json` `integration_2026_09_15`). | Auslieferung mit nächstem Release; Kompositum ohne Zerlegung. | R:37 |
| MP-REC-TRGM-DECISION | READY | Bericht `e86a429` integriert; ausdrücklich keine Betriebs-/Aktivierungsfreigabe. | Betriebsentscheidung protokollieren. | R:38 |
| MP-REC-SEARCH-TRGM | PLANNED | Extension/Tests fehlen. | genehmigte Migration+Restore sowie echte Tippfehler-/Performancefälle. | R:39 |
| MP-REC-SAVED-SEARCH | PLANNED | Store/Schema/Tests fehlen. | Filter speichern/laden, Besitzer-/Standort/CAS, aktuelle Readrechte. | R:40 |
| MP-REC-BATCH-TAGS | PLANNED | Modul/Schema/Tests fehlen. | 12 bestätigte Ziele, ein Konflikt → alle unverändert; Replay ohne Doppelbump. | R:41 |
| MP-REC-PLAN-PORTIONS | DEPLOYED | Status korrigiert 14.9.: Zielmenge über PP-SCHEMA (Schema 33, f5aa399)/PP-STORE (c052eda)/PP-UI (5e5c055) live (`recipes-wps.json` `delivery_2026_09_14`). | Keine separate unabhängige Abnahme-Session; UI-Capture-Promotion offen; Nachfolger MP-REC-SHOPPING-PERSIST wartet auf GPT-Lanes (Codex ab 2026-09-19 10:16). | R:42 |
| MP-REC-SHOPPING-AGGREGATE | DEPLOYED | `396fc49` integriert; Autor9/9, nur Testaufrufer. Status korrigiert 14.9.: vor Release d306f7a (13.9.) bereits live, genaue Release nicht bestimmt (`recipes-wps.json` `delivery_2026_09_14`). | unabhängige reine Mengen-/Prepared-/Provenienzabnahme; Produktanschluss folgt. | R:43 |
| MP-REC-SHOPPING-PERSIST | DEPLOYED | Status korrigiert 15.9.: Einkaufslisten über Schema 34 (47428b7) live (`recipes-wps.json` `delivery_2026_09_15`). | Live-Validator P3 behoben 15.9.; Demo-Reseed blockiert, Tabellensperre; MP-REC-SHOPPING-PDF wartet auf Abnahme. | R:44 |
| MP-REC-SHOPPING-PDF | PLANNED | PDF-Modul und Listenroute fehlen. | genaue Listenrevision authentifiziert herunterladen/öffnen; Umbruch und no-store. | R:45 |
| MP-REC-PDF-GEOMETRY | PLANNED | Rezeptprofil weiterhin acht Eigenschaften; `layout` abgelehnt. | begrenzten gewählten Layoutgriff sichtbar im PDF beweisen; Wochenregression bleibt grün. | R:46 |
| MP-NUT-SCHEMA | PLANNED | Keine Nährwertpersistenz/-tests. | Unknown≠0, Decimal/Bezugsmenge, append-only Editionen, CAS/ACL/Migration. | R:47 |
| MP-NUT-SERVICE | PLANNED | Store, Forms, Route, Template und Tests fehlen. | quellenbezogen pflegen/vorschlagen/feldweise bestätigen; atomare Provenienz. | R:48 |
| MP-NUT-RECIPE-PROJECTION | PLANNED | Projektionsmodul/-tests fehlen. | 250G bei 12,5g/100G → 31,25g; fehlende Zeile → unvollständig. | R:49 |
| MP-OFF-FIELDMAP | PLANNED | Feldmappingdatei fehlt. | aktuelle offizielle Felder, Attribution, Unknown-/Spurenregeln und Bildrechte. | R:50 |
| MP-OFF-ADAPTER | PLANNED | Adapter/-tests fehlen. | bounded Produktdokument → typisierter Vorschlag, enthält/Spuren getrennt. | R:51 |
| MP-OFF-COVERAGE | AWAITING_EXTERNAL | Bericht und berechtigte repräsentative Schweizer Stichprobe fehlen. | reale Trefferquote, Feldvollständigkeit und vollständige Übernahmekette. | R:52 |
| MP-REC-DATA-IMPORT | AWAITING_EXTERNAL | **Erledigt und produktiv belegt.** Status-/Titelkorrektur; Küchenprüfung separat DATA-001. | Release29/30/Finalberichte verknüpfen. | R:53 |
| MP-BAS-V27-RELEASE-ACCEPTANCE | PLANNED | Restore mit pgcrypto jetzt belegt; benannter Gesamtbericht fehlt. Spezifische PG18-Kollations-/Childhash-/Boundary-Lockzeitbelege in gelesenen Releaseberichten nicht gefunden. | vorhandene Belege abgleichen und nur fehlende Kriterien prüfen. | R:54 |
| MP-OFF-FETCH | PLANNED | Fetchmodul/-tests fehlen. | fester Endpoint, DNS/Peer/Redirect/Timeout/429, Originalhash und Herkunft; kein Write. | R:55 |
| MP-OFF-PROPOSAL-CONTRACT | PLANNED | Erweiterte SQL-/Proposal-/Assetkette fehlt. | feldweise atomare Übernahme mit Food/Proposal/Nährwertedition und Original-CAS. | R:56 |
| MP-OFF-REVIEW-UI | PLANNED | Route, Reviewtemplate und Tests fehlen. | Barcode → Fetch → Vergleich → ausdrückliche Feldübernahme; NoJS/Keyboard. | R:57 |

## Oberfläche, Zugriff und Abnahme — 65 IDs

Manifest: 24 DEPLOYED, 28 PLANNED, 8 READY, 5 AWAITING_EXTERNAL.

| Original-ID | Manifeststatus | Auditierte Ist-Einordnung | Nächster Schritt / Blocker laut Audit | Quelle |
|---|---|---|---|---|
| MP-UI-INVENTORY | READY | Inventar historisch: Schema25, 116 Routen/75 Templates; Gerichtvorlagen fehlen darin. | Vor Matrixplanung Registrierung/Rollen/Zustände abgleichen; bestehende Matrix/Manifest aktualisieren, Altbilder erhalten. | S:23 |
| MP-UI-BRAND-DECISION | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-TOKENS | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-SHELL | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-MACROS | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-REF-LIST | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-REF-FORM | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-REF-DETAIL | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-REF-SETTINGS | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-REF-WORKSPACE | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-MENU-EDITOR | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-WEEKS | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-PREVIEW | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-COPY-IMPORT | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-COMPONENTS | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-RECIPE-LISTS | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-RECIPE-FORMS | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-RECIPE-TOOLS | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-COOKBOOKS | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-FOUNDATIONS | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-OUTPUT-HUBS | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-PRINT-EDITOR | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. Rezeptdruck-Sonderzustände nicht aus Wochendruckkorrekturen ableiten. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-BRAND-OPS | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-LOCAL-USERS | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-ACCESS-HISTORY | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-AUTH | PLANNED | Vollständige Erfüllung unbelegt; geplanter Auth-Browsertest fehlt; kein belegter neuer UI-Defekt. | Nach UI-Prompt Autofill, Fehlerfokus, Tastatur, NoJS und 390/1440 prüfen; Session/Callback erhalten. | S:22 |
| MP-UI-API | PLANNED | Teilweise Statusdrift: Familienkorrekturen geliefert, ursprünglicher Gesamtauftrag nicht vollständig abgenommen. API-Dokumentationshülle nicht aus Schlüsselkorrekturen ableiten. | Originalkriterien mit Änderungen/Tests abgleichen; nur Differenzen; Desktop/Mobil, JS/NoJS, Fehler/CAS. | S:21 |
| MP-UI-SPECIAL-OUTPUTS | PLANNED | Gesamtprüfung unvollständig; keine pauschal fehlende Implementierung. | Mit Matrix nach UI-Freeze Public/HTML-Druck/TV, Marken/Logo-None und globale Einstellungen prüfen; native PDF getrennt. | S:26 |
| MP-UI-PUBLIC-WHITE-POLISH | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-MATRIX | PLANNED | Abnahmemanifest und Matrix-Browsertest fehlen; vollständige Matrix nicht abgenommen. | Nach aktuellem Inventar/UI-Freeze unabhängig alle Routen/Zustände, fünf Viewports und Accessibility nachweisen. | S:24 |
| MP-SCR-WEB-DAY | PLANNED | Featurekette im geplanten Umfang fehlt; Registry weiterhin web.week/v1. | Sequenziell Tag → TV → Geräte → Playlist; Schema-/Registry-Lease, Authz/CAS, Ziel-/Zeit-/Cachegrenzen prüfen. | S:27 |
| MP-SCR-TV-VARIANTS | PLANNED | Featurekette im geplanten Umfang fehlt; Registry weiterhin web.week/v1. | Sequenziell Tag → TV → Geräte → Playlist; Schema-/Registry-Lease, Authz/CAS, Ziel-/Zeit-/Cachegrenzen prüfen. | S:27 |
| MP-SCR-DEVICES | PLANNED | Featurekette im geplanten Umfang fehlt; Registry weiterhin web.week/v1. | Sequenziell Tag → TV → Geräte → Playlist; Schema-/Registry-Lease, Authz/CAS, Ziel-/Zeit-/Cachegrenzen prüfen. | S:27 |
| MP-SCR-PLAYLISTS | PLANNED | Featurekette im geplanten Umfang fehlt; Registry weiterhin web.week/v1. | Sequenziell Tag → TV → Geräte → Playlist; Schema-/Registry-Lease, Authz/CAS, Ziel-/Zeit-/Cachegrenzen prüfen. | S:27 |
| MP-SCR-EDITOR-DECISION | READY | Engineentscheidung/Prototyp und geplante Editor-Module fehlen. | Entscheidung zuerst; Core nach Playlist/Makros; CSP, Touch/Tastatur, Limits/Pflichtblöcke, Preview/Runtime-Fit. | S:28 |
| MP-SCR-EDITOR-CORE | PLANNED | Engineentscheidung/Prototyp und geplante Editor-Module fehlen. | Entscheidung zuerst; Core nach Playlist/Makros; CSP, Touch/Tastatur, Limits/Pflichtblöcke, Preview/Runtime-Fit. | S:28 |
| MP-SCR-EDITOR-FIELDS | PLANNED | Engineentscheidung/Prototyp und geplante Editor-Module fehlen. | Entscheidung zuerst; Core nach Playlist/Makros; CSP, Touch/Tastatur, Limits/Pflichtblöcke, Preview/Runtime-Fit. | S:28 |
| MP-TPL-FREE-DECISION | READY | Freie Geometrie offen; bestehende Raster/Bilder/Feldreihenfolge bereits vorhanden. | Layoutentscheidung → Core → Controls; Druckeditor-Besitz serialisieren; Einseiten-PDF/Fitfehler/Pflichtfelder prüfen. | S:29 |
| MP-TPL-FREE-CORE | PLANNED | Freie Geometrie offen; bestehende Raster/Bilder/Feldreihenfolge bereits vorhanden. | Layoutentscheidung → Core → Controls; Druckeditor-Besitz serialisieren; Einseiten-PDF/Fitfehler/Pflichtfelder prüfen. | S:29 |
| MP-TPL-FREE-CONTROLS | PLANNED | Freie Geometrie offen; bestehende Raster/Bilder/Feldreihenfolge bereits vorhanden. | Layoutentscheidung → Core → Controls; Druckeditor-Besitz serialisieren; Einseiten-PDF/Fitfehler/Pflichtfelder prüfen. | S:29 |
| MP-TPL-HUB-COMPLETE | PLANNED | Anschlussrestarbeit; vorhandener Hub deckt die geplanten Kataloge noch nicht vollständig ab. | Nach Rezept-/Screenfeatures echte Endpunkte, Rollen, aktive/archivierte/verwendete Stände; ein Hubowner. | S:30 |
| MP-TPL-PAPER | AWAITING_EXTERNAL | Externe Abnahme: benannter Drucker/Küche und vollständiger Nachweis fehlen. | Tatsächlichen Wochen-/Rezeptdruck mit Person, Datum, Version und Ergebnis dokumentieren. | S:33 |
| MP-IAM-CURRENT | READY | Bestehende Funktion; vollständiger Abnahmevertrag durch gezielte Gates nicht ersetzt. | Unabhängige Regression: echte Rollen sowie Redis-/Auditfehler. | S:32 |
| MP-IAM-SECRET-DECISION | READY | IAM-Erweiterung fehlt; Login statisch; Resolverweg braucht Betreiberbestätigung. | Betreiberentscheidung zuerst; danach gepinnte Revision/Secretversion, Test/Aktivierung, Adminschutz und alte Callbacks prüfen. | S:31 |
| MP-IAM-CONNECTION-DRAFTS | PLANNED | IAM-Erweiterung fehlt; Login statisch; Resolverweg braucht Betreiberbestätigung. | Betreiberentscheidung zuerst; danach gepinnte Revision/Secretversion, Test/Aktivierung, Adminschutz und alte Callbacks prüfen. | S:31 |
| MP-IAM-CONNECTION-TEST | PLANNED | IAM-Erweiterung fehlt; Login statisch; Resolverweg braucht Betreiberbestätigung. | Betreiberentscheidung zuerst; danach gepinnte Revision/Secretversion, Test/Aktivierung, Adminschutz und alte Callbacks prüfen. | S:31 |
| MP-IAM-CONNECTION-ACTIVATE | PLANNED | IAM-Erweiterung fehlt; Login statisch; Resolverweg braucht Betreiberbestätigung. | Betreiberentscheidung zuerst; danach gepinnte Revision/Secretversion, Test/Aktivierung, Adminschutz und alte Callbacks prüfen. | S:31 |
| MP-IAM-TENANT | AWAITING_EXTERNAL | Externe Abnahme: autorisierter Tenant/Identitäten und vollständiger Nachweis fehlen. | Echten Tenantfall mit Person, Datum, Version und Ergebnis dokumentieren. | S:33 |
| MP-BRD-DSP-REGRESSION | PLANNED | Gesamtprüfung unvollständig; keine pauschal fehlende Implementierung. | Mit Matrix nach UI-Freeze Public/HTML-Druck/TV, Marken/Logo-None und globale Einstellungen prüfen; native PDF getrennt. | S:26 |
| MP-ICO-REGRESSION | READY | Bestehende Funktion; vollständiger Abnahmevertrag durch gezielte Gates nicht ersetzt. | Unabhängige Regression der Symbol-/Legendenfälle. | S:32 |
| MP-API-REGRESSION | READY | Bestehende Funktion; vollständiger Abnahmevertrag durch gezielte Gates nicht ersetzt. | Unabhängige REST/OpenAPI/FHIR/MCP-/Authz-Regression. | S:32 |
| MP-API-CLIENT | AWAITING_EXTERNAL | Externe Abnahme: benannter Client/Operator und vollständiger Nachweis fehlen. | Konkreten Clientfall mit Person, Datum, Version und Ergebnis dokumentieren. | S:33 |
| MP-DATA-KITCHEN | AWAITING_EXTERNAL | Externe Abnahme: fachlich bestätigte Rezeptrevisionen fehlen als vollständiger Nachweis. | Küchenprüfung mit Person, Datum, Version und tatsächlichem Ergebnis dokumentieren. | S:33 |
| MP-QA-PUBLIC-RUNTIME | READY | Bestehende Funktion; vollständiger Abnahmevertrag durch gezielte Gates nicht ersetzt. | Unabhängiger Public-/TV-Runtimebeleg samt Rücknahme, Datumswechsel und Ausfall. | S:32 |
| MP-QA-PLAYER | AWAITING_EXTERNAL | Externe Abnahme: physischer Player und vollständiger Nachweis fehlen. | Echten Player-/Langlauf mit Person, Datum, Version und Ergebnis dokumentieren; keine Screenshotersetzung. | S:33 |
| MP-UI-RELEASE | PLANNED | Aktueller Release bereits live; Gesamt-UI-Abschluss weiter offen. | Nach MATRIX, BRD-DSP-REGRESSION und QA-PUBLIC-RUNTIME Release-/Freigabebelege ergänzen. | S:25 |
| MP-UI-FULLWIDTH-SHELL | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-FULLWIDTH-AUDIT | DEPLOYED | Grundlage ausgeliefert; fachliche Gesamtfreigabe offen. | Erhalten; Änderungen nach neuem UI-Prompt und betroffene Routen-/Zustandsmatrix prüfen. | S:19 |
| MP-UI-KORREKTUR-WEEK | DEPLOYED | Korrekturwelle ausgeliefert; keine erneut offene P1/P2-Implementierung. | Nach neuem UI-Prompt abnehmen; gemeinsame JS-/Dokumentationsbesitzer serialisieren. | S:20 |
| MP-UI-KORREKTUR-EDITOR | DEPLOYED | Korrekturwelle ausgeliefert; keine erneut offene P1/P2-Implementierung. | Nach neuem UI-Prompt abnehmen; gemeinsame JS-/Dokumentationsbesitzer serialisieren. | S:20 |
| MP-UI-KORREKTUR-COMPONENTS | DEPLOYED | Korrekturwelle ausgeliefert; keine erneut offene P1/P2-Implementierung. | Nach neuem UI-Prompt abnehmen; gemeinsame JS-/Dokumentationsbesitzer serialisieren. | S:20 |
| MP-UI-KORREKTUR-MENUS | DEPLOYED | Korrekturwelle ausgeliefert; keine erneut offene P1/P2-Implementierung. | Nach neuem UI-Prompt abnehmen; gemeinsame JS-/Dokumentationsbesitzer serialisieren. | S:20 |
| MP-UI-KORREKTUR-OPS | DEPLOYED | Korrekturwelle ausgeliefert; keine erneut offene P1/P2-Implementierung. | Nach neuem UI-Prompt abnehmen; gemeinsame JS-/Dokumentationsbesitzer serialisieren. | S:20 |
| MP-UI-KORREKTUR-VORLAGEN | DEPLOYED | Korrekturwelle ausgeliefert; keine erneut offene P1/P2-Implementierung. | Nach neuem UI-Prompt abnehmen; gemeinsame JS-/Dokumentationsbesitzer serialisieren. | S:20 |
| MP-UI-KORREKTUR-SCREENS | DEPLOYED | Korrekturwelle ausgeliefert; keine erneut offene P1/P2-Implementierung. | Nach neuem UI-Prompt abnehmen; gemeinsame JS-/Dokumentationsbesitzer serialisieren. | S:20 |

## Nachtrag 14. September 2026 — Beilagen-Welle, 12 neue IDs

Diese zwölf IDs gehören nicht zu den 145 ursprünglichen SDD-Arbeitspaketen. Git-Graph und Deploy-Berichte belegen jeweils die erste Live-Release; `DEPLOYED` ersetzt keine getrennte physische Abnahme.

| ACC-ID | Status | Erste Live-Release | Beleg / Abgrenzung |
|---|---|---|---|
| MP-REC-ACC-ICONS | DEPLOYED | `d306f7a8913d9c8c79e88edd39013b43a389a0e0` | `wp-d306f7a8913d-deploy.md`; Tabler-Generatorprüfung bestanden. |
| MP-REC-ACC-SNAPSHOT | DEPLOYED | `17fa06f13836915f2fe7dba73f20858bf5f88b79` | `wp-17fa06f13836-deploy.md`; 2197 Tests bestanden. |
| MP-REC-ACC-SCHEMA | DEPLOYED | `e0eee83ad0e4aec32e4fafae1395aac4fcbe3e78` | `wp-e0eee83ad0e4-deploy.md`; Schema 32 manuell migriert und live belegt. |
| MP-REC-ACC-MENU-CORE | DEPLOYED | `e0eee83ad0e4aec32e4fafae1395aac4fcbe3e78` | `wp-e0eee83ad0e4-deploy.md`; MENU-CORE/SNAPSHOT/Patienten-E2E 2252 Tests bestanden. |
| MP-REC-ACC-API-FHIR | DEPLOYED | `826c245259b397d0b78a55abfa81e770fb91ebcc` | `wp-826c245259b3-deploy.md`; 63 Tests sowie Live-OpenAPI/FHIR belegt. |
| MP-REC-ACC-PUBLIC-OUTPUT | DEPLOYED | `485aeda9908436bc6f5b5b30fb0858b3eadfc89c` | `wp-485aeda99084-deploy.md`; 2130 Tests und Signage-Fit FHD/4K. |
| MP-REC-ACC-WEEK-PDF | DEPLOYED | `89e8c972fabf1f71568db2a4f73b544da0cf5938` | `wp-89e8c972fabf-deploy.md`; 78 Tests bestanden. |
| MP-REC-ACC-TEMPLATE | DEPLOYED | `7d0595d28d2eee9dfdb5861ff310b638ae574338` | `wp-7d0595d28d2e-deploy.md`; kombinierter Integrations-Gate 430 bestanden, 12 übersprungen. |
| MP-REC-ACC-EDITOR-UI | DEPLOYED | `7d0595d28d2eee9dfdb5861ff310b638ae574338` | `wp-7d0595d28d2e-deploy.md`; 201 Tests bestanden, A02-Baseline getrennt offen. |
| MP-REC-ACC-COLLECTION | DEPLOYED | `7d0595d28d2eee9dfdb5861ff310b638ae574338` | `wp-7d0595d28d2e-deploy.md`; 101 Tests bestanden, acht Baselinefehler. |
| MP-REC-ACC-CSV | DEPLOYED | `7d0595d28d2eee9dfdb5861ff310b638ae574338` | `wp-7d0595d28d2e-deploy.md`; 94 Tests bestanden; zwei CSV-Review-P3 bleiben offen. |
| MP-REC-ACC-ACCEPT | DEPLOYED | `7d0595d28d2eee9dfdb5861ff310b638ae574338` | `wp-acc-accept-0914.md`; A1–A16 bestanden, physischer Player und Küchendruck getrennt. |

Offen bleiben A02 Cafeteria 1366×768, nicht gelaufene UI-Capture-Promotion `ui-before-manifest.json`, CSV-P3 für gemischte `schema_version`-Tests und Doku-Aufzählung sowie Root-Beobachtung P3: Proposal auf belegtem Slot zeigt im Prüfkontext «Keine Beilage». Diese Punkte erzeugen keine neuen Pakete.

## Grenze der Übertragung

Die drei Audits führten keine neuen Tests, Browserprüfungen oder OCR-Reviews aus. Ihre zitierten Autoren-, Integrations- und Releasebelege bleiben entsprechend begrenzt. Fehlende zugeordnete Abnahmebelege sind keine neu bestätigten Produktfehler. Dieses Register ersetzt weder die spätere unabhängige Abnahme noch den aktuellen Freigabe- und Besitzplan.
