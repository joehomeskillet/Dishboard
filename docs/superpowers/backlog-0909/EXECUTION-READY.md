# Gemeinsamer Ausführungsstand: Routing und Dateibesitz

Planquelle ist `de08d5101a689e3c09d2aab980cfec4dcb025017`: 136 WPs,
35 Anforderungs-IDs. [routing-receipts.json](routing-receipts.json) enthält für
jeden unveränderten Task den tatsächlichen CLI-Beleg mit Routing-WP-ID, Klasse,
Lane, Modell, Match und Fallback. Zwei identische Batchaufrufe lieferten jeweils
136 Einträge, Exit 0 und byteidentisches JSON; dessen SHA256 ist
`b1f5827ec733924e97fd3e1c2fea4061f99843fa7f7c54547afb08a0e26f1385`.

Diese Belege sind Routingempfehlungen. Modellverfügbarkeit, Kontingente,
Kostenfreiheit und Ausführungsbeginn wurden nicht geprüft. Insbesondere sind
die 113 tatsächlichen `single-file-fix`-Zuordnungen keine fachliche Bestätigung
dieser Klassifikation. Root muss Lane, Fähigkeit und Umfang vor dem Start
abgleichen; eine nötige Korrektur wird ausdrücklich zugewiesen. Die generischen
leeren CLI-Vertragsfelder ersetzen niemals die vollständigen Manifestverträge.
`existing_wp_id` bleibt die historische Ausführung; eine neu berechnete
Routing-WP-ID darf diese nicht überschreiben oder einen zweiten Writer starten.
`parallel_group=backlog-frozen136-0909` ist ausschließlich ein Router-
Transportetikett. Es erlaubt keinesfalls den gleichzeitigen Start aller 136 WPs;
die begrenzten Dateileases und aktuelle Root-Zuweisung steuern jeden Start.

## Vollständige Dateileases

[file-leases.json](file-leases.json) leitet alle 741 Owned-Claims aus allen drei
Manifesten ab: 447 unterschiedliche Pfade, davon 83 mit mehreren Anspruchstellern.
Die 196 Read-only-Claims stehen separat und erteilen keinen Schreibbesitz.
`contract_files` und `wiring_files` sind vollständig in `owned_files` enthalten.
`proposed:` wird für Konfliktvergleiche entfernt; jede Datei wird als ganze Datei
reserviert. Die geteilten Top-Level-Ownergruppen sind kein vollständiger Index.

146 Owned-Pfade existieren im eingefrorenen Gitbaum, 301 fehlen dort; bei den
Read-only-Pfaden sind es 38 vorhandene und 12 fehlende. Der Index enthält konkrete
Gitobjekte und den lokalen Existenzabgleich. Fehlende Pfade wurden nicht angelegt.
27 Platzhalter verlangen eine explizite Root-Auflösung, insbesondere die noch
nicht vergebenen Migrationen. Dateinamen sind keine Schema-Reservierung.

Geschützt bleiben Schema27, Foundations, Menübindungen und der laufende
Snapshot-Reader `wp-a05c09994a29` mit seinen zwölf Dateien. Zusätzlich wurde nach
dem Manifestfreeze Public White Polish tatsächlich durch Root als
`wp-8f0b4743f28b` im Worktree `public-white-polish-0909` zugewiesen
(Basis `5f5f6cb535922db8453c68d871279d6b2e203391`, Pool 32839/32840).
Dessen Manifeststatus bleibt als historischer Stand `PLANNED`; der Index ergänzt
die aktive Zuweisung separat.
Dieser Routing-WP hat keinen dieser Prozesse oder Pools übernommen.

Auch UI Inventory ist inzwischen reserviert: Nach dem ursprünglichen Grok-Freeze
`f136490f7b2c19805c8f6436ebdbb657c3549dd7` arbeitet laut Root seit
09.09.2026 01:00 UTC der unabhängige Claude-Code-Proof-Fix `wp-d7589450daee`
im Worktree `ui-inventory-proof-fix-0909` auf dieser Basis, Pool 32831/32833.
Das ist eine ergänzende Root-Zuweisung, keine vom Routing-WP geprüfte Runtime.
Der unveränderte Manifeststatus `READY` erteilt deshalb keinen freien Schreibbesitz.

`test_master_data_db.py` bleibt ein gemeinsamer Anspruch des eingefrorenen
Schema27-Slices und seines Foundations-Consumers. Root muss den konkreten
Vorgängerfreeze und die Versions-/Fixture-Hunks seriell freigeben. Ebenso ist
`admin/recipe_revision_routes.py` nun vollständig sowohl beim Snapshot-Reader
als auch beim späteren Freeze-Consumer indiziert. Der Reader besitzt nur seine
vertraglichen Lese-Hunks; der Freeze-Writer wartet auf dessen Übergabe. Der
Index erteilt keine gleichzeitigen Schreibrechte auf diese Überschneidungen.

## Startkandidaten, noch keine Startfreigabe

`proposed_disjoint_batches` enthält 15 derzeit dateidisjunkte Kandidaten ohne
deklarierte offene Abhängigkeiten, externe Inputs oder geschützte Dateiüberschneidung.
Das ist ein Vorschlag, keine Kapazitäts- oder Ausführungszusage. Für alle 136 WPs
sind die Gründe für Aufnahme oder Zurückhaltung einzeln maschinenlesbar aufgeführt.
Auch `READY` ist keine Ausführungserlaubnis. Für dieses Dokument wird kein ganzes
WP allein aus Status, Sourceexistenz oder einem zusammengefassten PASS als
erfolgreiche Dependency abgezogen (`satisfied_dependency_ids` ist leer).
Root kann nach Prüfung der konkreten Abschlussbelege weitere abhängige Aufgaben
freigeben; der Vorschlag nimmt solche Abschlüsse nicht vorweg.

## Identischer Auftrag für Codex, Claude Code und Grok-Build

Vor jedem Start setzt Root den gemeinsamen Prompt aus [START.md](START.md) ein;
dies ist der vorhandene Dateiname. [execution-contract.md](execution-contract.md)
und [README.md](README.md) bleiben bindend.

1. MP-ID und genau einen unveränderten Manifestvertrag auswählen; alle benötigten
   SDD-Abschnitte lesen. Bestehende Ausführungs-ID und laufenden Owner prüfen.
2. Vollständigen Basiscommit, eigenen Branch/Worktree, Routing-WP-ID und tatsächliche
   Lane/Modellzuweisung eintragen. Vorhandene Teiländerungen nicht neu erzeugen.
3. Jeden Owned-Pfad gegen den gesamten Leaseindex und aktuelle Root-Zuweisungen
   prüfen. Geteilte Dateien erst nach Vorgängerfreeze übernehmen; reine Leseinputs
   gesondert pinnen. Ein Manifest- oder Leasewechsel erfordert erneuten Abgleich.
4. Fachliche Abhängigkeiten anhand konkreter Belege freigeben, fehlende externe
   Inputs auf den betroffenen Ablauf begrenzen. DB-/Browserarbeit braucht den
   aktuell zugewiesenen exklusiven Wrapper; keine vorhandenen Pools erraten.
5. Den vollständig ausgefüllten gemeinsamen Auftrag im eigenen Worktree als
   `.claude/ROOT-START.md` hinterlegen. Erst dann genau einen der folgenden
   Einstiege benutzen. Das vorliegende WP hat keinen davon gestartet.

Beispielbefehle nach Root-Freigabe; Platzhalter sind vor Ausführung durch die
zugewiesenen Werte zu ersetzen. Alle Aufrufe laufen im eigenen Worktree, jeweils
ein direkter RTK-Befehl. Kein automatischer Fallback wird gestartet.

```bash
rtk pwd
rtk git status --short --branch
rtk git rev-parse HEAD
```

Codex:

```bash
rtk codex exec --cd '<OWN_WORKTREE>' --model '<ROOT_ASSIGNED_MODEL>' 'Lies .claude/ROOT-START.md vollständig und führe genau diesen Rootauftrag aus.'
```

Claude Code, interaktiv aus dem zugewiesenen Worktree:

```bash
rtk claude --model '<ROOT_ASSIGNED_MODEL>' 'Lies .claude/ROOT-START.md vollständig und führe genau diesen Rootauftrag aus.'
```

Grok-Build über die vorhandene Host-Bridge:

```bash
rtk node /root/.claude/plugins/marketplaces/xai-grok-build/plugins/grok-build/scripts/grok-bridge.mjs run --write --cwd '<OWN_WORKTREE>' --model '<ROOT_ASSIGNED_MODEL>' --effort high --prompt-file .claude/ROOT-START.md
```

Die CLI-Hilfen wurden gelesen, bei der Bridge zusätzlich die vorhandenen
`cwd`-/`prompt-file`-Optionen im Quellcode. Das beweist die Aufrufsyntax, keine
Anmeldung oder verfügbare Modellkapazität. Auf anderen Hosts dieselben Werkzeuge
am dort dokumentierten Pfad verwenden; der Manifestauftrag bleibt identisch.
Bei Nutzung eines Host-Sandbox-Wrappers dessen Vertrag beachten und keine zweite
Sandbox verschachteln. Report, eigener Commit und unabhängige Root-Gates bleiben
Pflicht. Diese Dokumente geben weder Merge noch Deployment frei.
