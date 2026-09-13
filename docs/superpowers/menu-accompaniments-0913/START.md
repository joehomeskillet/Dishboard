# Startauftrag — Menübeilage «Suppe oder Salat» (REC-008)

Planung `wp-f9d0d3e72dfe`, Fable 5.1, 13. September 2026; Root-Abschluss nach
Sitzungslimit. Letzter Nutzerauftrag: «Mit verfügbaren GPT-Workern fortsetzen».
Er ersetzt die frühere ausschliessliche Spark-Vorgabe; tatsächliche Modelle je Start belegen. Spezifikation:
[`docs/design/2026-09-13-menu-accompaniments-sdd.md`](../../design/2026-09-13-menu-accompaniments-sdd.md).
Pakete: [`work-packages.json`](work-packages.json). Dieser Start braucht keine vorangegangene
Unterhaltung. Root setzt die fünf Werte ein: **MP-ID, WP-Datei, vollständiger Basiscommit,
eigener Worktree, Routing-WP-ID** (`rtk claude-workpackage`). Bei DB-/Browserarbeit gehört
ein exklusiver Testpool zur Zuweisung.

Schema31 ist laut Root mit `4be7b79d69e38e70875981a70d7b975591e5218c` seit
13.09., 08:53 CEST gesund live. Registrierungsbasis ist
`4711c22075383126d2af90ecaa85184ed53589eb`. SCHEMA ist als `wp-65e15658fc4b`
`IN_PROGRESS`: Root bestätigt `gpt-5.6-sol`/high, Profil `effort-high`, Provider
OpenAI, PTY 90840, Start 07:08:58Z / 09:08 CEST im eigenen Worktree
`accompaniment-schema-codex-0913`, APIint2 exklusiv. Noch kein Quellfreeze oder Gate.
Historischer Spark-Aufruf 7070: Usage-Limit/Exit 1 («try again at 1:28 PM»),
`BLOCKED_PROVIDER`, sauberer Spark-Worktree `4711c220` ohne Produktänderungen.
Die nutzerautorisierte Fortsetzung und dieser frühere Abbruch sind getrennte Belege.
ICONS ist mit Quelle `0ca81ee` nach
Root-Recovery und Generatorprüfung `REVIEWED_LOCAL`, nicht deployed. Die zehn
weiteren Pakete bleiben `PLANNED`; Root vergibt Leases/Pools vor jedem Start.

REC-008 und alle zwölf Pakete stehen im zentralen
[`recipes-wps.json`](../backlog-0909/recipes-wps.json); der datierte ACC-Nachtrag in
[`file-leases.json`](../backlog-0909/file-leases.json) enthält die genauen Pfade und
aktuellen Grants. Historische Plan-/UI-Stände dort sind keine konkurrierende Freigabe.

## Gemeinsamer Prompt

```text
Arbeite genau MP-ID=<ID> aus WP-Datei=docs/superpowers/menu-accompaniments-0913/work-packages.json ab.
Routing-WP=<wp-ID>; Basis=<vollstaendiger SHA nach Schema-31-Release>; eigener Worktree=<ABSOLUTER PFAD>.

Lies docs/superpowers/backlog-0909/execution-contract.md, docs/superpowers/menu-accompaniments-0913/START.md
und die im WP genannten Abschnitte von docs/design/2026-09-13-menu-accompaniments-sdd.md vollstaendig.
Vor jeder Frontend-Arbeit docs/design/2026-09-09-unified-ui-design-system.md vollstaendig lesen.
Pruefe tatsaechlichen HEAD, zugewiesenen Branch und Dateibesitz. Du bist Worker, nicht Orchestrator,
und nicht allein im Repository. Keine weitere Delegation, kein anderes MP, kein Push/Merge/Deploy.

Fachliche Leitplanken: genau ein Wert je Menue aus none|soup|salad; Salat ist ein Angebot
(gemischt und gruen); Beilage ist kein Baustein, kein Rezept, hat weder Preis noch Allergen-
noch Naehrwertaussage; Vorlage schlaegt nur vor, gespeichert wird der Formularwert; alte Menues,
gespeicherte Publikationsrevisionen, Hashes und Review-Tokens bleiben bytegleich
(Snapshot-Schluesselpaar nur bei gewaehlter Beilage). Keine neue Dependency, kein Framework,
keine admin.js-Aenderung, keine Datenumschreibung.

Alle Shell-Aufrufe direkt rtk, jeweils ein Befehl, keine Pipelines/Verkettungen oder rtk proxy.
Keine Credentials lesen/ausgeben, keine Dependencies installieren, keine Produktivdaten als Fixture,
keine gestoppten Container starten, keine Screenshot-Baselines ersetzen. Bestehende Dateien gezielt
patchen. Vor jedem Symbol-Edit GitNexus-Impact (Index-Stand pruefen; nicht indexiertes SQL ist
unbekannter Impact, keine LOW-Einstufung), vor Commit detect_changes. HIGH/CRITICAL melden.

Implementiere den vollstaendigen zugewiesenen Vertrag samt Anschluessen und Tests. Sichere
Original-Actor/Authz/Standort/CSRF/Slot-CAS, vorhandene Historie, Playergrenzen und Mengenvertraege.
Gates laut WP mit echten Binaries ausfuehren, rohe Ausgaben und Exitcodes bewahren. Ein fehlendes
Gate ist kein PASS. Screenshots bei UI selbst kritisch ansehen.

Committe ausschliesslich eigene Dateien. Schreibe und registriere den WP-Bericht
(rtk claude-wp-report dir / record) mit Quelle, Commitliste, Gatebelegen, fehlenden Checks und Grenzen.
Bei Fehler genau ein identischer Retry; Einmalablaeufe nicht blind replayen. Bei Kontingentende
Zustand sichern, rtk agent-quota-mark-down <provider>, ESCALATE: LANE-DOWN <provider>; kein stiller
Modellwechsel. Beende mit WP-REPORT: DONE|BLOCKED und konkretem Umfang.
```

## Root-Checkliste vor dem ersten READY

1. Schema-31-Release integriert und live belegt; Basiscommit festhalten.
2. Registrierung **REC-008** in `docs/BACKLOG.md`, `validate-plan.py`,
   `recipes-wps.json` und dem ACC-Nachtrag in `file-leases.json` ist erfolgt.
   Vor jedem Start die tatsächliche Root-Zuweisung und den Vorgängerfreeze prüfen.
3. Root reserviert `0029_v31_to_v32.sql` für ACC-SCHEMA. PLAN-PORTIONS wartet und
   braucht eine spätere eigene Nummer. Nie bestehende Migrationen umnummerieren.
4. Icons: Quelle `0ca81ee` aus `wp-0bdbe5f2eaec` und Root-Generatorprüfung sind
   belegt; tatsächliche Glyphen, Layout und Integration in den jeweiligen
   Verbraucher-Gates prüfen. Ein Quellbeleg ersetzt keinen Deploybeleg.
5. Fachfragen F1–F6 der SDD §11: Defaults gelten, F3-Formulierung und F5-CSV-Roundtrip
   sind durch Root entschieden; eine andere Antwort zu F1 (Gästewahl) vor
   `MP-REC-ACC-SCHEMA` starten lassen (vierter Wert), sonst später als kleine Constraint-Migration.
6. Pools: ein exklusiver Pool je DB-/Browser-Writer; höchstens fünf schwere Jobs auf dem Host;
   `rtk pgrep -fc pytest` unter 12; gestoppte Container bleiben gestoppt.

## Reihenfolge und Parallelität

| Welle | Pakete | Voraussetzung |
|---|---|---|
| 0 | `MP-REC-ACC-SCHEMA` (ein SQL-Writer) ∥ `MP-REC-ACC-ICONS` (Root) | Schema-31-Freeze, Migrationsnummer |
| 1 | `MP-REC-ACC-MENU-CORE` ∥ `MP-REC-ACC-SNAPSHOT` ∥ `MP-REC-ACC-TEMPLATE` | SCHEMA integriert; CORE seriell mit PLAN-PORTIONS/BINDING-Cluster; TEMPLATE seriell mit RECIPEPAGES auf `gerichtvorlagen.html` |
| 2 | `MP-REC-ACC-EDITOR-UI` ∥ `MP-REC-ACC-PUBLIC-OUTPUT` ∥ `MP-REC-ACC-WEEK-PDF` ∥ `MP-REC-ACC-API-FHIR` | CORE + SNAPSHOT integriert; EDITOR-UI seriell mit PLAN-PORTIONS auf `menu_editor.html` |
| 3 | `MP-REC-ACC-COLLECTION`, verpflichtendes `MP-REC-ACC-CSV`, `MP-REC-ACC-ACCEPT` | Welle 2 integriert; LISTS-Freeze für COLLECTION; ACCEPT erst nach COLLECTION und CSV |

Drei parallele Worker je Welle sind vorgesehen; jede gemeinsame Datei hat genau einen aktiven
Writer (SDD §12.1). Additive Schema-/Leser-Grundlagen können vorab veröffentlicht werden.
Sichtbare Beilagen-Schreiboberflächen erst freigeben, wenn Snapshot-Validatoren,
Public/Signage/Druck/API und CSV-Roundtrip vollständig angeschlossen sind. Welle1 allein
enthält noch keinen fertigen Editor. Keine Zwischenfreigabe mit still verlorenem Exportwert.

## Gates

Gezielte Tests je WP stehen in `work-packages.json` (`test_plan`) und SDD §14. Entwicklerlauf im
Verzeichnis `reference_scaffold` mit dem von Root zugewiesenen Wrapper:

```bash
rtk <ROOT_ASSIGNED_GATE> <OWN_WORKTREE> -q -p no:cacheprovider tests/<zugewiesene-tests>.py
rtk /root/.local/bin/ruff check <owned-python-files>
rtk /root/.local/bin/mypy --python-executable /tmp/dishboard-shared-venv/bin/python --follow-imports=silent <owned-production-files>
```

UI-Pakete: echte Browserinteraktion 1440 × 900 und 390 × 844 (Editor zusätzlich NoJS,
Tastatur, 200 %-Zoom); Signage 1920 × 1080 und 3840 × 2160. Screenshots sind Vorschläge, keine
Baselines. Textarbeit (SDD, START, JSON) erhält nur Validator-, JSON- und Diffprüfung, keine
Gesamt-Suite. Das Sprintende-Gate ist die Vereinigung der WP-Listen plus
`tools/validate_package.py` durch Root.

## Übergabe und Bericht

Bericht nach Ausführungsvertrag: `MP-ID`, `wp-ID`, tatsächliche Lane/Modell, Worktree, Branch,
Basis-/Ergebniscommits, geänderte Dateien, geprüfte Kriterien (SDD §13 A1–A16), exakte
Gate-Ausgaben, nicht ausgeführte Gates, Risiken, nächster Schritt. Letzte Zeile
`WP-REPORT: DONE|BLOCKED — <konkreter Umfang>`. Root liest den Diff, führt die Gates unabhängig
aus, integriert im Integrations-Worktree und liefert per `github/main` mit Revision/Image/Schema/
HTTP-Beleg aus; Schemaänderungen brauchen Backup, Migration, Restore-Probe und die Rollback-Regel
I10 der SDD.
