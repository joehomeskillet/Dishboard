# pg_trgm: Entscheidungsgrundlage für den Betrieb

| Feld | Wert |
|---|---|
| MP-ID | `MP-REC-TRGM-DECISION` |
| Routing-WP | `wp-eef8b83d102d` |
| Lane / verwendetes Modell | Codex / `gpt-6-astra` |
| Datum | 11. September 2026 |
| Basis-Commit | `4ca6df79827477d5682ccae9d76345adf3c3a4f7` |
| Worktree | `/nvmetank1/projects/menuplan/.claude/worktrees/docs-rec-decisions-codex-0911` |
| Branch | `docs/rec-decisions-0911` |
| Status | Empfehlung; Betriebsentscheid beim Auftraggeber, keine Aktivierungsfreigabe |

**Empfehlung:** `pg_trgm` nach ausdrücklicher Betriebsfreigabe in einer eigenen
Migration nach dem integrierten Schema-27-Stand bereitstellen; Restorevorbereitung
im selben Lieferumfang ergänzen. Einen GIN-Index erst in `MP-REC-SEARCH-TRGM`
mit echten Messungen und zugewiesenem Dateibesitz liefern. Hier wurde **keine
Datenbank verändert und nichts installiert**.
[recipes-wps.json:3591–3597,3680–3688](recipes-wps.json#L3591),
[recipes-sdd.md:1003–1006](recipes-sdd.md#L1003).

## Betriebsimage: zitierter Befund, keine eigene Liveabfrage

Der Orchestrator erhob am 11. September 2026 folgende Werte; sie werden hier
aus dem [Auftrag:27–32](/tmp/claude-0/-nvmetank1-projects-menuplan/9e4f1af2-43c1-4bd9-b63b-d4da92579062/scratchpad/brief-codex-rec-decisions.md#L27)
zitiert und zur dauerhaften Nachvollziehbarkeit ausgeschrieben:

| Gegenstand | Vom Orchestrator erhobener Wert |
|---|---|
| Produktionscontainer / Image | `suedhang-cafeteria-db-1` / `postgres:18.6-alpine` |
| `pg_trgm` | Version **1.6 verfügbar, nicht installiert** |
| `pgcrypto` | Version **1.4 verfügbar und installiert** |
| `unaccent` | Version **1.1 verfügbar, nicht installiert** |
| Deployment von Migrationen | `dishboard-deploy-main` (stündlicher Timer) verweigert Diffs unter `database/migrations/`; manueller Root-Deploy mit vorherigem `deployment/backup.sh`-Dump und Compose-Dienst `migrate`. |

Die Imagekonfiguration stimmt damit überein:
[docker-compose.yml:16–22](../../../deployment/docker-compose.yml#L16).
Das ist ein zusätzlicher Konfigurationsbeleg, kein erneuter Livebeweis.
Verfügbarkeit bedeutet vorhandene Erweiterungsdateien; `CREATE EXTENSION`
registriert daraus Objekte in einer bestimmten Datenbank.
[PostgreSQL 18: CREATE EXTENSION](https://www.postgresql.org/docs/18/sql-createextension.html).

## Berechtigungsweg und ausführende Rolle

`pg_trgm` ist bereits in PostgreSQL 13 als **trusted extension** dokumentiert;
dies gilt auch für PostgreSQL 18. Ein Superuser kann sie anlegen; ein
Nicht-Superuser benötigt `CREATE` auf der Zieldatenbank. Für ein ausdrücklich
gewähltes bestehendes Zielschema sind die passenden Schema-Rechte zu prüfen.
Der Aufrufer besitzt anschliessend die Extension; bei trusted Installation durch
einen Nicht-Superuser gehören die enthaltenen Objekte grundsätzlich dem
Bootstrap-Superuser. «Extension braucht immer Superuser» wäre hier falsch.
[PostgreSQL 13: pg_trgm](https://www.postgresql.org/docs/13/pgtrgm.html),
[PostgreSQL 18: pg_trgm](https://www.postgresql.org/docs/18/pgtrgm.html),
[CREATE EXTENSION](https://www.postgresql.org/docs/18/sql-createextension.html).

Der belegte Projektweg ist:

1. Compose `migrate` setzt `POSTGRES_USER: cafeteria_owner`,
   `APP_ENV: migration` und startet `python /app/manage.py init-db`.
   Der Appdienst verwendet dagegen `cafeteria_app`.
   [docker-compose.yml:95–123,145–150](../../../deployment/docker-compose.yml#L95).
2. `entrypoint.sh` prüft im Migrationsmodus die Konfiguration und führt am Ende
   das übergebene Kommando aus. Es wechselt nicht per `SET ROLE` zur Approlle.
   Die Verbindungs-URL wird aus `POSTGRES_USER` gebildet, sofern keine explizite
   URL vorliegt; `init-db` reicht sie an `init_database` weiter.
   [entrypoint.sh:36–43 und Dateiende](../../../deployment/entrypoint.sh#L36),
   [config.py:65–78](../../../reference_scaffold/cafeteria/config.py#L65),
   [manage.py:191–202](../../../reference_scaffold/manage.py#L191).
3. `init_database` provisioniert Rollen, führt `run_migrations` aus und wendet
   danach `permissions.sql` an. Migration und neue Extension sind somit im
   konfigurierten **Owner-Pfad** vorzusehen, nicht in einem HTTP-Request.
   [db.py:263–280](../../../reference_scaffold/cafeteria/db.py#L263).

Compose setzt auch beim DB-Bootstrap `POSTGRES_USER=cafeteria_owner`. Das
offizielle Image übergibt diesen Namen an `initdb --username`; dieser Parameter
bestimmt den Bootstrap-Superuser. Damit ist der Superuserweg für eine frische
Standardinitialisierung erklärt. Die heutigen `rolsuper`-/Datenbankrechte des
bestehenden Produktionsclusters wurden hier **nicht live geprüft**; Root muss
vor Ausführung `current_user`, `rolsuper`, Datenbank-CREATE und Schema-Rechte
belegen. Die Hostrolle Root ist nicht mit PostgreSQL-Superuser gleichzusetzen.
[docker-compose.yml:16–25](../../../deployment/docker-compose.yml#L16),
[offizieller Image-Entrypoint](https://raw.githubusercontent.com/docker-library/postgres/master/docker-entrypoint.sh),
[PostgreSQL 18: initdb](https://www.postgresql.org/docs/18/app-initdb.html).

`permissions.sql` entzieht `PUBLIC` CREATE auf `public` und den Laufzeitrollen
alle expliziten Rechte auf diesem Schema. Daraus folgt keine Berechtigung der
App, Extensions zu installieren. Vorschlag: Extensionobjekte wie `pgcrypto`
gezielt in `public` anlegen, Schema und erwartete Version prüfen, niemals
pauschal Datenbank-CREATE oder breites App-DML freigeben. Spätere
`public.similarity`-/Operator-Aufrufe benötigen eine ausdrücklich geprüfte
USAGE-/EXECUTE- und Suchpfadstrategie im Such-WP; Schemaqualifikation allein
ersetzt keine Rechte.
[permissions.sql:13–19](../../../database/permissions.sql#L13),
[postgres-backup.sh:289–293](../../../deployment/postgres-backup.sh#L289),
[recipes-wps.json:3687–3688](recipes-wps.json#L3687).

## Migration und Schemaversion

**Ist dieses Worktrees:** `SCHEMA_VERSION=25`, `APPLICATION_VERSION` v25 und
letzte registrierte Migration `0022_v24_to_v25.sql`. Der Schema27-Writer ist
separat reserviert. Die hier vorhandenen Dateien belegen weder ein integriertes
Schema 27 noch eine bereits freie Migrationsnummer 28. Ältere Kommentarstände
in `schema.sql`/README sind keine zuverlässige Versionsquelle.
[db.py:22–23,35–58](../../../reference_scaffold/cafeteria/db.py#L22),
[recipes-sdd.md:127–152,274–279](recipes-sdd.md#L127).

Vorgeschlagener SQL-Kern für eine **später von Root nummerierte** eigene Migration,
nicht ausgeführt und noch keine vollständige Migrationsdatei:

```sql
BEGIN;
CREATE EXTENSION IF NOT EXISTS pg_trgm WITH SCHEMA public VERSION '1.6';
COMMIT;
```

Das Muster folgt den bestehenden transaktionalen Migrationen und der
Extensionbereitstellung. Zusätzlich muss die spätere Migration bei bereits
vorhandener Extension Version, Namespace und freigegebenen Eigentümer prüfen
und bei Abweichung abbrechen. `IF NOT EXISTS` prüft diese Eigenschaften nicht
und führt kein Upgrade aus.
[0022_v24_to_v25.sql:1–2](../../../database/migrations/0022_v24_to_v25.sql#L1),
[schema.sql:5–9](../../../database/schema.sql#L5),
[CREATE EXTENSION](https://www.postgresql.org/docs/18/sql-createextension.html).

**Schemaversion-Bump: im Projekt ja**, auch ohne neue Fachtabelle. PostgreSQL
selbst verlangt keine Dishboard-Versionsnummer; hier führt der Runner eine feste
Migrationsliste, SHA-256-Prüfung und einen Ledger-Eintrag in derselben Transaktion.
Ein ausserhalb des Ledgers ausgeführtes SQL-Snippet wäre kein vollständiger
Projekt-Upgradepfad. Root muss nächste freie Version, `MIGRATION_FILES`,
`SCHEMA_VERSION`/`APPLICATION_VERSION`, kanonisches Schema, ACL-/Schema-Validator,
Paketvalidator und Versions-/Ledgerfixtures zusammen reservieren. Historische
Migrationen bleiben byteidentisch. Der aktuelle Bump ist erst nach Integration
der Vorgänger festzulegen, nicht jetzt im reservierten Schema27-WP.
[db.py:144–157,174–229](../../../reference_scaffold/cafeteria/db.py#L144),
[recipes-wps.json:3687–3688](recipes-wps.json#L3687).

Der manuelle Root-Deploy benötigt vorher einen geprüften Backup-Dump und danach
Upgrade-/ACL-/Restorebelege. `deployment/backup.sh` startet den Backupdienst und
kann Dump plus SHA-256-Datei in ein absolutes Exportverzeichnis liefern. Ein
grüner stündlicher Source-Deploy ersetzt diesen Migrationsweg nicht.
[Auftrag:31–32](/tmp/claude-0/-nvmetank1-projects-menuplan/9e4f1af2-43c1-4bd9-b63b-d4da92579062/scratchpad/brief-codex-rec-decisions.md#L31),
[backup.sh:10–38](../../../deployment/backup.sh#L10).

## Backup und Restore: der Schemafilter ist entscheidend

**Allgemein:** Ein vollständiger logischer Dump einer installierten Extension
enthält deren `CREATE EXTENSION`-Anweisung, nicht einfach alle Extension-internen
Objektdefinitionen. PostgreSQLs `dumpExtension` erzeugt regulär
`CREATE EXTENSION IF NOT EXISTS ... WITH SCHEMA ...` ohne Versionspin; die
Zielinstallation bestimmt ihre Defaultversion. Ein Plain-SQL-Dump wird mit
`psql`, ein Custom-Archiv mit `pg_restore` eingespielt.
[pg_dump-Implementierung: dumpExtension](https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/src/bin/pg_dump/pg_dump.c),
[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).

**Hier:** Der Backupdienst nutzt `--schema=cafeteria --format=custom`, ohne
`--extension`. PostgreSQLs `selectDumpableExtension` schliesst benutzerinstallierte
Extensions bei diesem Filter aus. Der Dump enthält daher keine automatische
Bereitstellung von `pg_trgm`; dies ist ein statischer Quellbefund, kein in diesem
Auftrag untersuchtes reales Archiv. Das liegt am Schemafilter, nicht allein am
gewählten Ort `public`. Die Schemafilter-Dokumentation warnt ausdrücklich vor
fehlenden Abhängigkeiten.
[postgres-backup.sh:37–51](../../../deployment/postgres-backup.sh#L37),
[pg_dump: --schema](https://www.postgresql.org/docs/18/app-pgdump.html),
[pg_dump-Implementierung: selectDumpableExtension](https://raw.githubusercontent.com/postgres/postgres/REL_18_STABLE/src/bin/pg_dump/pg_dump.c).

**Folgerung für den genehmigten Folgeauftrag:** In jedem frischen Restorekandidaten
`pg_trgm` mit geprüftem Schema/Version/Eigentümer **vor `pg_restore`** bereitstellen,
analog zum vorhandenen `pgcrypto`-Schritt. Nach Einführung eines Trigram-GIN-Index
wäre `run_migrations` erst nach dem Import zu spät: seine Operator-Klasse wird
bereits beim Indexaufbau benötigt. Auch ohne Index kann der restaurierte Ledger
die Extensionmigration als erledigt markieren, obwohl die Extension im frischen
Kandidaten fehlt; ein späterer Runner überspringt sie dann.
[postgres-backup.sh:288–294](../../../deployment/postgres-backup.sh#L288),
[db.py:217–225](../../../reference_scaffold/cafeteria/db.py#L217),
[pg_trgm: Index Support](https://www.postgresql.org/docs/18/pgtrgm.html#PGTRGM-INDEX).

Die bestehende Restore-Reihenfolge bleibt erhalten, ergänzt um die freigegebene
Extensionvorbereitung: isolierter Kandidat und Erweiterungen → geprüftes
`pg_restore` → `run_migrations` → `permissions.sql` →
`ensure_auth_capability_state()` → nochmals `permissions.sql` →
`hard_reset_auth_capability_state()` → Validator/erfolgreicher Abschluss →
Writerstart. Bestehende Ausschlüsse für Capability-Secrets/-Nonces sowie die
geregelte Writer-/Promotion-Steuerung bleiben verbindlich. `--no-owner` und
`--no-privileges` ersetzen weder Installationsrechte noch abschliessende ACLs.
[database/README.md:101–116](../../../database/README.md#L101),
[postgres-backup.sh:42–49,288–294](../../../deployment/postgres-backup.sh#L42),
[pg_restore](https://www.postgresql.org/docs/18/app-pgrestore.html).

Die Extension allein erzeugt noch keinen Trigramindex auf Rezeptdaten. Ein
späterer GIN-Index benötigt zusätzlichen Datenbankplatz und Schreibarbeit.
Logische Dumps speichern seine Definition, nicht seine physischen Indexseiten;
die Dumpgrösse wächst daher nicht um die volle Indexgrösse. Restorezeit und
Platzbedarf beim Neuaufbau können steigen. Konkrete Byte-/Zeitwerte sind
unbekannt und im Such-WP mit realistischen Daten zu messen; ein GIN-Index ist
kein pauschales Beschleunigungsversprechen.
[pg_trgm: Index Support](https://www.postgresql.org/docs/18/pgtrgm.html#PGTRGM-INDEX),
[pg_dump](https://www.postgresql.org/docs/18/app-pgdump.html),
[recipes-sdd.md:990–1005](recipes-sdd.md#L990).

## Rollbackgrenze und Datenverlustfreiheit

- Vorschlag ohne Suchabhängigkeiten: unbenutzte Extension zunächst belassen und
  kompatiblen Forward-Fix bevorzugen. Falls Entfernung beschlossen wird, nur nach
  Abhängigkeitsprüfung und als neue registrierte Korrektur. Keine Ledgerzeile
  löschen oder frühere Migration umschreiben; alte Binaries können unbekannte
  Schemaversionen ablehnen. [db.py:211–227](../../../reference_scaffold/cafeteria/db.py#L211).
- `DROP EXTENSION pg_trgm RESTRICT` ist nur ohne blockierende abhängige Objekte,
  insbesondere Trigramindizes, zulässig. Zuerst Suchconsumer deaktivieren und
  ausdrücklich benannte abhängige Indizes entfernen; deren Entfernung löscht
  keine Rezeptzeilen, nimmt aber den Zugriffsvorteil. Kein blindes `CASCADE`:
  es kann weitere abhängige Objekte entfernen. Extension-Mitglieder und explizit
  an die Extension gebundene Routinen werden beim Drop ohnehin mit entfernt.
  [DROP EXTENSION](https://www.postgresql.org/docs/18/sql-dropextension.html).
- Die vorgeschlagene reine Aktivierung verändert keine Rezept-/Snapshotwerte;
  bei Rücknahme nur abgeleiteter Indizes bleiben diese fachlichen Daten erhalten.
  Das ist eine Eigenschaft des vorgeschlagenen Umfangs, kein hier gemessener
  Rollback-PASS. Ein Restore des Vor-Migrations-Dumps würde spätere Writes
  verlieren und ist deshalb nach neuen Writes kein pauschal datenverlustfreier
  Rückweg. [SQL-Kern dieses Dokuments](#migration-und-schemaversion),
  [database/README.md:73–75](../../../database/README.md#L73).

## Entscheid und Nicht geprüft

Zur Entscheidung vorgeschlagen: eigener Extension-/Restore-Schritt nach dem
integrierten Schema27-Stand, dann getrennte Suchintegration mit GIN/EXPLAIN in
`MP-REC-SEARCH-TRGM`. FTS bleibt unabhängig lieferbar. Freigabe, reale
Folgemigrationsnummer und genaue ACLs legt der Auftraggeber beziehungsweise
Root fest. [recipes-sdd.md:1003–1006](recipes-sdd.md#L1003),
[recipes-wps.json:3680–3688](recipes-wps.json#L3680).

- Keine eigene Produktionsabfrage; Image- und Extensionwerte oben sind
  ausdrücklich die gelieferten Orchestratorbefunde.
- Keine Datenbank verändert, keine Extension/Dependency installiert; kein
  Upgrade, Restore, Rollback oder Backup ausgeführt und kein Dump geöffnet.
- Keine Liveprüfung von Rollen, Datenbank-/Schemarechten, Extension-ACLs,
  Indexgrösse, Schreiblast oder EXPLAIN; diese Belege benötigt der Folgeauftrag.
- Keine pytest-/Ruff-/Mypy-/Paket-/Browserprüfung für diesen Dokumentdiff.
- `context-mode/ctx_fetch_and_index` lieferte bei Erstaufruf und identischem Retry
  `Transport closed`; offizielle PostgreSQL-Quellen wurden über Webzugriff
  gelesen. Git-/Link-/Review-Ergebnisse stehen im separaten WP-Bericht.
