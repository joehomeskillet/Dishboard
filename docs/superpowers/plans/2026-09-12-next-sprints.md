# Dishboard — nächste Sprints nach der Korrekturwelle

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Tatsächlich offene SDD-Anforderungen in kurze, überprüfbare Lieferungen aufteilen und den angekündigten UI-Korrekturprompt vor dem nächsten UI-Dispatch integrieren.

**Architecture:** Bestehende 145 MP-Verträge bleiben führend. Dieser Plan ergänzt den tatsächlichen Lieferstand, Abhängigkeiten, fehlende Anschlüsse und die Sprintreihenfolge; er ersetzt keine vorhandenen Writer durch konkurrierende Neuimplementierungen. Gemeinsame SQL- und UI-Verträge haben jeweils genau einen Besitzer.

**Tech Stack:** Bestehendes Flask/Jinja/Tabler, PostgreSQL 18.6, Redis, Docker Compose und vorhandene Python-/Playwright-Testumgebung. Keine neue Dependency durch diesen Plan.

**Spec:** `docs/superpowers/backlog-0909/{recipes,operations,surfaces}-sdd.md`, zugehörige `*-wps.json`, `execution-contract.md`, `docs/BACKLOG.md`, `docs/design/2026-09-09-unified-ui-design-system.md`, `docs/design/2026-09-12-patientenplan-menueditor-korrektur.md`.

**Baseline:** `2fa44dea36675692bfb8ad4b681dca73dba06737`, `github/main`, Schema 30; letzter belegter Deploy 12. September 2026 um 23:15:29 CEST.

**Planungsstatus:** Vorplanung. Der angekündigte UI-Korrekturprompt ist noch nicht eingegangen. Der UI-Sprint und seine Dateiüberlappungen werden nach Eingang konkretisiert; bis dahin kein neuer Produkt-Writer aus diesem Plan.

## Global Constraints

- Aktuelle Nutzeranweisungen vor historischen Dokumentständen; „SDD“ bezeichnet die vorhandenen Software-Design-Verträge.
- Patientenkanal strukturell ohne Kostenfelder oder Kostenwerte; getrennte Profile und unveränderliche Publikationsrevisionen erhalten.
- Originalactor, Berechtigungsversion, Standort, CAS, CSRF, Audit und historische Mengen-/Preis-/Rezeptbelege bleiben verbindlich.
- Nur Worktrees unter `.claude/worktrees/`; Shell ausschließlich `rtk`, ein Befehl pro Aufruf, keine Verkettungen, Pipes oder `rtk proxy`.
- Keine Secrets lesen, keine Dependencies installieren, keine fremden Screenshots als Baseline übernehmen.
- Pro Writer ein Worktree und vollständiger Vertrag samt erforderlichen Verbrauchern. Autor und Reviewer getrennt; bestätigte Fixes an anderen Autor.
- Native Sitzung: drei parallele Workerplätze. Host: höchstens fünf schwere Jobs insgesamt; vor Dispatch Speicher und tatsächliche Testlast prüfen.
- Keine gleichzeitigen SQL-Writer. Migrationsnummer erst nach Freeze des Vorgängers reservieren; bestehende Migrationen niemals neu nummerieren oder neu abspielen.
- Temporär gestoppte Container bleiben gestoppt. Keine fremden Testpools oder Produktionsdaten als Fixtures.
- Grün geprüfte Integrationen regelmäßig über `github/main` ausliefern; Schemaänderungen brauchen manuellen Backup-/Restore-/Kompatibilitätsablauf. Der reguläre Deployservice verweigert Migrationsdiffs.
- Planung ist keine pauschale Produktabnahme. `DEPLOYED` und `ACCEPTED` bleiben getrennt.

## Prüfstand und führende Audits

[SDD-Abgleich](2026-09-12-sdd-open-work-audit.md) enthält Zählung und Statusregeln.
Die drei Audits prüfen zusammen alle 145 vorhandenen Pakete:

| Bereich | WPs | Vollständiger Auditbericht |
|---|---:|---|
| Operations | 37 | `/nvmetank1/projects/rag-stack/.claude/reports/wp-4a3597a72ed7.md` |
| Rezepte | 43 | `/nvmetank1/projects/rag-stack/.claude/reports/wp-20bbdcac693e.md` |
| Surfaces | 65 | `/nvmetank1/projects/rag-stack/.claude/reports/wp-855e496d2bb5.md` |

Nicht erneut bauen: importierte Beispielgerichte/Lagerorte, Schema27–30, vorhandene Rezeptbindungen, Stapelimport, reine Schema.org-/KI-/Einkaufsadapter, Kostenkern/Patient-Guard und ausgelieferte UI-Korrekturen. Fehlende unabhängige Einzelbelege werden zugeordnet oder gezielt ergänzt.

## Sprintfolge und Lieferpunkte

Sprints sind hier abgeschlossene Funktionsabschnitte, keine erfundenen Kalenderzusagen.
Die Reihenfolge nach Sprint 1 ist der begründete Vorschlag; ein UI-Prompt mit neuen
fachlichen Abhängigkeiten kann sie ändern, ohne erledigte Arbeit neu zu starten.

| Sprint | Nutzbarer Ausgang | Umfang | Voraussetzung / Lieferpunkt |
|---|---|---|---|
| 0 — belastbarer Start | Aktueller Status, vollständiger Besitzplan und aufbereiteter UI-Auftrag | Aufgaben 1–3 unten; vorhandene Belege wiederverwenden, externe Eingaben isolieren | Kein Produktrelease nötig; Planvalidator und unabhängiger Planreview |
| 1 — angekündigte UI-Korrektur | Vom Nutzer konkret benannte Bedienprobleme behoben | Neue Promptanforderungen mit bestehenden UI-WPs/DEBT-Paketen zusammenführen; vorhandene P1/P2 nicht erneut bauen; danach beobachtete Bedienaufgabe | Exakter Prompt, aktuelle Routenmatrix, konfliktfreie Writer; ein oder mehrere kurze UI-Releases |
| 2 — Portionen und Einkauf | Zielmengen im Plan; gespeicherte Einkaufsliste aus Plan oder Rezeptauswahl; druckbare Liste | `MP-REC-PLAN-PORTIONS` → `MP-REC-SHOPPING-PERSIST` → `MP-REC-SHOPPING-PDF`; vorhandenen Aggregator verwenden | UI-Editor-Freeze, Binding-/Freeze-/PDF-Belege; je grüner vertikaler Lieferung eigener Release |
| 3 — Rezepte finden und wiederverwenden | Suche über Titel und Zutaten; danach gespeicherte Suchen und bestätigte Stapel-Tags | `MP-REC-SEARCH-FTS` → `MP-REC-SAVED-SEARCH`, `MP-REC-BATCH-TAGS`; TRGM nur nach eigenem Betriebsentscheid | Gemeinsame SQL-Dateien nach Sprint 2 frei; FTS benötigt keine TRGM-Freigabe |
| 4 — nachvollziehbare Kosten | Datierte Preise, historische Rezept-/Menükalkulation und bewusste Preisvorschläge | PRICE-LEDGER → RECIPE-PROJECTION → PREPARED-GRAPH → MENU-PROJECTION → RULES-SUGGEST → CALCULATION-RECEIPTS → CALC-ADMIN-UI | Vorhandener Patient-Guard nachgewiesen; PLAN-PORTIONS und Freeze-Verträge; Küchenabnahme separat |
| 5 — echter Lagerbestand | Journal, unbekannt/Null korrekt, Transfer/Inventur und Bestand auf Zutatenkarte | INV-MOVEMENT-CORE → BALANCE-READ → TRANSFER → COUNT-CORRECTION → ADMIN-UI; NO-PLAN-DEBIT, DEMAND-COUPLING und Food-Karten-Anschluss | Keine Gleichsetzung der bereits importierten Lagerorte mit Bestand; Journal-Writer serialisieren |
| 6 — Bestellvorbereitung | Manueller Korb, sichere Vorschau/CSV und Bedarfsübernahme | ORD-SUPPLIER-ARTICLE → BASKET-DRAFT → EXPORT-PREVIEW → ADMIN-PREVIEW; danach DEMAND-LINK | Ohne Lieferantenanschluss lieferbar; verbindlicher Versand bleibt eigenes Paket nach ORD-SEND-RIGHTS |

Präfixe in den letzten drei Zeilen sind `MP-CALC-`, `MP-INV-` bzw. `MP-ORD-`.
Vorbereitete Chargenproduktion folgt der Inventurabnahme; keine verdeckte Warenbuchung beim Planen.

## Task 1: Lieferstatus und Abnahmebelege abgleichen

**Files:** `docs/superpowers/backlog-0909/{recipes,operations,surfaces}-wps.json`,
`README.md`, `EXECUTION-READY.md`, `docs/BACKLOG.md`; Statusänderungen nur mit belegtem MP-Bezug.

**Interfaces:** Konsumiert unveränderte Commit-/Release-/Auditbelege. Produziert pro MP
einen begründeten aktuellen Status und getrennte noch offene Kriterien; keine neuen Produkt-DTOs.

- [ ] Vollständige 145-Paket-Tabelle aus den drei Audits mit den MP-Verträgen abgleichen.
- [ ] Erledigten Rezeptimport sowie vorhandene Kern-/UI-Pakete richtig zuordnen. Für
  `MP-BAS-V27-RELEASE-ACCEPTANCE`, `MP-REC-BINDINGS-ACCEPT`, PDF und UI-Matrix fehlende
  Einzelkriterien separat führen; keinen allgemeinen Autorbericht zu `ACCEPTED` hochstufen.
- [ ] Alte OPS-Belegcommits `4027d1b` und `9a9fc81` lesen und auf heutige Anwendbarkeit
  prüfen; fehlende Capture-Prüfung offen halten. PKS-/TRN-Rechteartefakte erst wiederbeschaffen.
- [ ] „Null Foods“ und alte Schemastände als historischen Stand kennzeichnen. Neue
  Migrationsfixtures enthalten nichtleere Lebensmittel-/Rezeptdaten und unveränderliche Altbytes.
- [ ] Planvalidator ausführen:

```bash
rtk python3 docs/superpowers/backlog-0909/validate-plan.py docs/superpowers/backlog-0909/operations-wps.json docs/superpowers/backlog-0909/recipes-wps.json docs/superpowers/backlog-0909/surfaces-wps.json --source-commit e813806b51fb5efaef5d5755c292f8027ce1b2eb --quiet
```

Der ursprüngliche `source_commit` benennt die historische Planquelle; den aktuellen
Ausführungs-/Reviewcommit getrennt ergänzen. Keine künstliche Änderung dieses Werts,
um alte Belege wie neue erscheinen zu lassen. Ausgangswert: 145 Pakete, 35/35 Anforderungen,
0 Fehler, 62 Hinweise. Hinweise prüfen und erhalten, keine vermeintliche warnungsfreie Freigabe.

## Task 2: Neuen UI-Prompt in vorhandene Verträge einordnen

**Files:** Die neue Prompt-Spezifikation unter `docs/design/`, das bestehende
`docs/superpowers/backlog-0909/ui-route-matrix.json`, `ui-before-manifest.json`,
`surfaces-wps.json` sowie dieser Sprintplan. Produktdateien erst nach der Zuordnung reservieren.

**Interfaces:** Konsumiert den unveränderten Nutzerprompt und die aktuelle Routenmatrix.
Produziert je Anforderung: konkrete Route/Zustand, erwartetes Verhalten, existierende
MP-ID oder begründete Ergänzung, Dateibesitz, Abhängigkeit und gezieltes Gate.

- [ ] Prompt vollständig als Quelle bewahren; keine zusätzlichen Layoutwünsche erfinden.
- [ ] Jede Anforderung als bereits geliefert, Regression, echter neuer Umfang oder
  präzisierter bestehender Auftrag einordnen. Teilweise vorhandene Lösung ausdrücklich kennzeichnen.
- [ ] Inventar auf den neuen Basiscommit aktualisieren; `/admin/gerichtvorlagen` und
  ihre Liste/Formularzustände ergänzen. Alte 116-Routen-/Schema25-Metadaten sind kein aktueller Vollständigkeitsbeleg.
- [ ] DEBT01–04 und die neue Zutatenkarten-Bestandsanzeige gegen den Prompt abgleichen.
  Mehrere Anforderungen an dieselbe Datei in einem vollständigen Writervertrag bündeln.
- [ ] Für gemeinsam betroffene Dateien eine Konflikttabelle und Merge-Reihenfolge festhalten.
- [ ] Ersten UI-Dispatch erst mit konkretem Prompt, Basis, Writer, Reviewer und exklusivem
  Testpool durchführen. Fehlender Prompt blockiert ausschließlich diesen Ausführungsschritt.

## Task 3: Fehlende Vertragszuordnungen ergänzen

**Files:** Zugehörige `*-sdd.md`/`*-wps.json`, dieser Plan und begründete Entscheidungs-/Abnahmeberichte.

- [ ] `MP-INV-FOOD-CARD-BALANCE` ergänzen oder den vollständigen bestehenden INV-ADMIN-UI-
  Vertrag erweitern. Voraussetzungen: `MP-INV-BALANCE-READ`, `MP-BAS-FOUNDATIONS` und
  abgeschlossene Grundlagen-UI-Korrektur. Schreibbesitz enthält mindestens
  `admin/master_data_routes.py`, `templates/admin/grundlagen_food.html` und gezielte
  Read-/Browsertests. Gate: unbekannt, ausdrücklich gezählte Null und positiver Saldo.
- [ ] `MP-OPS-BACKUP-OFFHOST-ACCEPT` als QA-001-Nachweis ergänzen: benanntes autorisiertes
  Ziel/Operator, Quelle/Zieldatei samt SHA256/Manifest und isolierter Restore von der
  Offhostkopie. Zunächst nur Evidenzauftrag; keinen Transfer auf unbekanntes Ziel starten.
- [ ] Begrenzten Fremdmanager-Format-/Fixtureentscheid zu REC-004 ergänzen; vorhandene
  PKS-Kette zusätzlich nachvollziehbar zu REC-004 zuordnen. Keine erfundenen Pauli-Daten.
- [ ] `MP-REC-SHOPPING-PERSIST` präzisieren: echter Einstieg aus Wochenplan **und**
  Rezeptauswahl, RR-Lesen exakter Revisionen, DTO-Anbindung zum vorhandenen Aggregator.
- [ ] Guard-Freeze von `MP-CALC-PATIENT-GUARD` vor jedem persistierenden CALC-WP als
  ausdrückliche Readiness-Bedingung ergänzen.
- [ ] `MP-UI-USABILITY-OBSERVATION` ergänzen: benannte repräsentative Küchenperson
  findet ein Menü, ändert nur die Beilage, speichert und erklärt danach Prüfstand
  sowie fehlende Allergenprüfung. Beobachtung und Bedienprobleme getrennt von
  fachlicher DATA-KITCHEN-Freigabe festhalten; keine Produktionsänderung als Testfixture.
- [ ] Richtext-Folge-WP erst bei entsprechendem konkretem Funktionsentscheid ergänzen.
  Vorhandene Klartextempfehlung und CSP-Befund bleiben sichtbar; keine ungefragte Editorinstallation.

## Ausführungsverträge für den ersten fachlichen Folgesprint

Die vollständigen `owned_files`, `contract_files`, `wiring_files`, Kriterien und
Verbote stehen unter der jeweils genannten ID in `recipes-wps.json`. Die folgende
Tabelle hebt die kollidierenden Anschlüsse und minimalen Regressionen hervor; sie
verkleinert diesen Dateibesitz nicht.

| Reihenfolge | WP / Vertrag | Kritische Anschlüsse | Nachzuweisender kurzer Ablauf |
|---|---|---|---|
| 2.1 | MP-REC-PLAN-PORTIONS | `component_assignment_contract.py`, Assignment-/Workflow-Stores, Copy/Review, `workflow_routes.py`, `admin/rendering.py`, `menu_editor.html`, `admin.js`, SQL-Vertrag | Exakte Zielmenge 2.500000 erhalten; 0/negativ/fehlende Einheit abweisen; Save/Load/Copy/Review plus native Add/Remove/Reorder; alte Publikationshashes gleich |
| 2.2 | MP-REC-SHOPPING-PERSIST | `shopping_list_store.py`, `admin/shopping_list_routes.py`, `admin/__init__.py`, `einkaufslisten.html`, SQL-Vertrag | Wochenplan/Rezeptauswahl → Liste; manuelle Zeilen/Abhaken; bewusste Neuberechnung; Original-CAS409 ohne Verlust; historische Inputs reproduzierbar |
| 2.3 | MP-REC-SHOPPING-PDF | `admin/shopping_pdf.py`, Listenroute/-template, `print_template_config.py`, `print_templates.py` | Authentifizierter Download genauer Listenrevision; PDF öffnen; 200 Positionen mit lesbarem Umbruch; Mengen/Einheiten korrekt, Wochen-PDF unverändert |

Gezielte Tests für 2.1: `test_recipe_plan_portions_db.py`,
`test_rec_plan_portions_migration_db.py`; für 2.2: `test_shopping_list_db.py`,
`test_shopping_list_browser.py`, `test_rec_shopping_persist_migration_db.py`;
für 2.3: `test_shopping_list_pdf.py` plus betroffene bestehende Wochen-PDF-Verträge.
Neue Tests entstehen gemeinsam mit ihrer Funktion, keine wertlosen Doppeltests des Implementierungscodes.

Alle genannten Python-/Templatepfade liegen unter `reference_scaffold/cafeteria/`,
Tests unter `reference_scaffold/tests/`. Jede schemaändernde Aufgabe besitzt zusätzlich
`database/schema.sql`, `database/permissions.sql`, `database/validate_schema.py`,
`cafeteria/db.py`, `tools/validate_package.py`, ihre echte neue Migration und eng begrenzte
Versions-/Ledgerfixtures. Die vorhandenen `<ROOT_RESERVED_…>`-Einträge sind **keine**
fertigen Pfade: vor `READY` durch reale Reservierung auf dem dann gefrorenen Schema ersetzen.

## Parallelität und Konfliktplan

| Gemeinsame Fläche | Betroffene Aufgaben | Regel |
|---|---|---|
| SQL/Migrationsledger | Portionen, Einkauf, FTS, Preise, Inventur, Nährwerte, Bestellungen, Glossar | Ein Writer; Consumerphase parallel nur nach veröffentlichtem Freeze |
| Menüeditor/`admin.js`/Rendering | Neuer UI-Prompt, DEBT-Bereinigung, Portionen, spätere Glossarübernahme | UI-Korrektur vor Funktionsanschluss; keine konkurrierenden Edits |
| Grundlagen/Food-Formular | Neuer UI-Prompt, Bestandsanzeige, Nährwerte, OFF-Review | Einen vollständigen Vertrag pro kollidierendem Abschnitt vergeben |
| Rezeptliste/-reader/-route | Neuer UI-Prompt, FTS, Saved Search, Batch Tags | UI-Freeze, dann Suche; Folgefunktionen auf derselben integrierten Basis |
| Einkaufsliste/-route | Persistenz, PDF | Erst Persistenz; PDF danach |
| PDF-Konfiguration/-store | Einkaufs-PDF, Rezeptgeometrie, freie Druckgeometrie | Nicht parallel schreiben; exakte aktive Revision und Legacy-Verträge erhalten |
| `admin/__init__.py`/Sidebar | Neue fachliche Oberflächen | Ein Registrierungsbesitzer bzw. serialisierte vollständige Integrationen |

Praktische Belegung: Writer A bearbeitet den aktuellen vertikalen Funktionsvertrag;
Worker B prüft unabhängig den vorherigen Freeze; Worker C bereitet eine nicht
kollidierende Quellen-/Fixture-/Abnahmeaufgabe vor. Drei gleichzeitige SQL-Writer
erhöhen keine sichere Parallelität. Root integriert und liefert grüne Abschnitte aus.

## Weitere eingeplante Ketten und externe Eingaben

| Kette | Nächster eigener Schritt | Wartet nur auf |
|---|---|---|
| URL-Rezeptimport | MP-REC-URL-FETCH nutzt vorhandenen Schema.org-Adapter und Stapelweg | Bestehender Import-Freeze, Ausgangsschutz und eigener UI-Besitz |
| XLSX/Fremdmanager | Tatsächliche berechtigte Beispieldatei/Formatentscheidung | Genau diesen Quelldatensatz und Leseweg; CSV/JSON bleiben nutzbar |
| KI-Import | Vorhandene reine Extraktion übernehmen, danach MP-REC-AI-PROVIDER | Freigegebenen konkreten Provider; keine automatische Allergenfreigabe |
| Nährwerte/OFF | NUT-SCHEMA → SERVICE → RECIPE-PROJECTION; OFF-FIELDMAP parallel als Quellenarbeit, dann Adapter/Fetch/Proposal/UI | Serialisierten Schema-/Food-Vertrag; Schweizer Coverage zusätzlich reale berechtigte Stichprobe |
| Screens/freie Druckgeometrie | Bestehende Decision-WPs und vollständige Anschlussketten nach UI-Prompt auswählen | Konkreten Layoutbedarf; kein Frameworkwechsel aus dem Audit |
| Entra | Resolver-/Connection-Verträge technisch planen | Echter Tenant-Operator erst für externe Abnahme |
| PKS/Glossar | Fehlende Rechteartefakte wiederbeschaffen; danach vorhandene Adapter-/Glossar-WPs | Autorisierte PKS-Datei und tatsächlich belegte Datenrechte |
| Küche/Druck/API/Player | Bestehende Abnahme-WPs mit Gerät/Person/Client und gefrorener Revision terminieren | Jeweiligen externen Teilnehmer; kein globaler Entwicklungsstopp |

## Gates und Übergabe je Sprint

- [ ] Vor Start tatsächliche Basis, vollständige Dateileases, freien Testpool und
  Originalanforderung festhalten; GitNexus-Impact vor Symboländerung.
- [ ] Autor prüft kleinsten vollständigen Verhaltensumfang; keine stummen Skips oder
  Herkunftsumdeutung alter Tests. Lint/Typprüfung nur passend zur Änderung.
- [ ] Unabhängiger Reviewer prüft Spezifikation und Qualität. Root führt passende
  Gates unabhängig aus; bestätigte Fixes gehen an anderen Autor.
- [ ] UI: betroffene Route auf Desktop und Mobil; zusätzliche Viewports/Zustände für
  gemeinsame Komponenten nach bestehendem Vertrag. Fokus, NoJS, Zoom und Fehlerrückgabe prüfen.
- [ ] Bei Migrationen echter Upgrade/Restore/ACL-Beleg mit nichtleerem Bestand;
  Rollback braucht kompatibles Image und passende Datenwiederherstellung.
- [ ] Vor Release Manifeste aus sauberem Export erzeugen, Paketprüfung, Push nach
  `github/main`, autorisierten Deploy ausführen, Revision/Image/Schema und HTTP live prüfen.
- [ ] Status erst mit jeweiligem Beleg fortschreiben. Physischer Player, Küchendruck,
  fachliche Mengen/Allergene und Tenantabnahme bleiben eigene Aussagen.

Nach Eingang des UI-Prompts werden Sprint 1, die ersten konkreten Writerbriefs und
die Konflikttabelle finalisiert. Die Folgeketten oben bleiben nachvollziehbar erhalten.
