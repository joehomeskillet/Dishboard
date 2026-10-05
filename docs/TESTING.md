# Tests: vier Stufen

Alle Befehle im Repository-Root mit dem vorhandenen Projekt-venv ausführen.
Keine Installation im geteilten venv. `rtk` muss im PATH stehen.

```bash
rtk /path/to/venv/bin/python tools/test_gate.py --tier 0
rtk /path/to/venv/bin/python tools/test_gate.py --tier 1 --changed main --pools /path/pool1.env
rtk /path/to/venv/bin/python tools/test_gate.py --tier 2 --pools /path/pool1.env,/path/pool2.env,/path/pool3.env,/path/pool4.env
rtk /path/to/venv/bin/python tools/test_gate.py --tier 3 --pools /path/pool1.env,/path/pool2.env,/path/pool3.env,/path/pool4.env
```

Alternativ enthält `TEST_GATE_POOLS` die kommaseparierten Env-Dateien. Hostpfade
und Zugangsdaten gehören nicht ins Repository. `--python` wählt bei Bedarf den
pytest-Interpreter; standardmäßig wird derselbe Interpreter wie für den Runner
verwendet.

| Stufe | Umfang | Budget und Grenze |
|---|---|---|
| 0 | Ruff für Gate-Infrastruktur, Syntax aller Admin-Templates, Manifest-Verify, Paketprüfung offline | Ziel <1 min; Syntaxprüfung ersetzt kein Rendern mit echtem Kontext |
| 1 | Diff-basierte Auswahl einschließlich nicht getrackter Quellen | Ziel <5 min; unbekannte Inputs und breite UI-Abhängigkeiten können Vollauswahl verlangen |
| 2 | Alle Testdateien, dauerbalanciert auf höchstens vier Pools | Ziel <=20 min; tatsächlich gemessene Laufzeit steht im Bericht |
| 3 | Vollauswahl zweimal, Seeds 920 und 1920, Ergebnisvergleich je ID | Nachtlauf, vollständige bestehende Matrizen; keine automatische Matrix-Reduktion |

Die Budgets sind Abnahmeziele, keine impliziten Timeouts. Kein Test wird dafür
abgebrochen, übersprungen oder mit schwächeren Assertions ausgeführt.

## Pools und Isolation

Jeder Pool braucht eine eigene PostgreSQL-Instanz mit Testdatenbank und eine
eigene Redis-Instanz. Zwei Datenbanken desselben PostgreSQL-Servers sind wegen
clusterweiter Rollen keine unabhängigen Pools und werden abgelehnt.
Literal-Env-Dateien dürfen `export KEY=value` verwenden. Shell-Expansion,
Command-Substitution und ausführbare Env-Dateien werden abgelehnt. Der Runner
löst `TEST_DATABASE_CONTAINER`/`TEST_REDIS_CONTAINER` über `docker port` auf und setzt die
Ports in den Test-URLs. Namen und Schlüssel müssen dem vorhandenen Pool-Vertrag
entsprechen; `tools/_test_gate_pools.py` ist die maßgebliche Schnittstelle.
Nur Loopback-Ziele und PostgreSQL-Datenbanknamen mit `test` werden akzeptiert.
Produktionsdatenbanken sind ausgeschlossen.

Der Runner prüft vorhandene pytest-Prozesse, sperrt DB-/Redis-Ressourcen per
Dateilock und gibt Locks an Kindprozesse weiter. Bei weniger als 30 GB verfügbarem
RAM läuft er sequenziell. Niemals mehrere Runner mit denselben Pools starten.
Native PDF-/Chrome-Starter bleiben unverändert und laufen pro Datei in getrennten,
sequenziellen Prozessen ihres Shards. Dasselbe gilt für Asyncio-Testmodule und
ihre importierenden Testmodule. Gemeinsame Browser-Fixtures verwenden einen
Playwright-Lebenszyklus. Ein gemischter Direktaufruf von pytest wird vorab
abgelehnt; der Runner übernimmt die passende Aufteilung.

Golden-DB-Resets sind als explizit verwendbarer Fixture-Adapter verfügbar. Bestehende
Fixture-Provider bleiben unverändert; der Adapter wird mit echtem PostgreSQL geprüft.
Sie behalten DB-URL, Fixture-Namen und echte Rollen-/Schema-Validierung. Belegte
Verbindungen werden nicht beendet. Ein Reset mit noch aktiven Clients ist INFRA.
Bei verbliebenen Clients läuft einmal Garbage Collection, um nicht mehr
erreichbare Pool-Zyklen freizugeben. Weiter referenzierte Clients bleiben geschützt.
Native Zoom-Tests behalten ihre eigenen persistenten Browser-Kontexte.

## Auswahl, Historie und Flaky-Prüfung

```bash
rtk /path/to/venv/bin/python tools/test_gate.py --build-map
rtk /path/to/venv/bin/python tools/test_gate.py --changed main --list
rtk /path/to/venv/bin/python tools/test_gate.py --files tests/test_api_docs.py tests/test_public_contracts.py --flaky --pools /path/pool1.env
```

Die Karte wird aus Python-Imports, Route-URL-Fragmenten, Template-/Asset-Verweisen
generiert und bei jeder Änderungsauswahl erneuert. Unbekanntes erweitert auf alle
Tests. Template-/CSS-/JS-/Snapshot-/Signage-Änderungen behalten Browser-Tests und
die festen Public-/Signage-Guardrails. `.timings.json` wird nur nach vollständigen
Läufen ohne erkannte Infrastrukturfehler aktualisiert. Zeiten sind Hinweise für
LPT-Sharding, kein Nachweis eines Speedups.

`pytest-testmon` wurde im ursprünglichen Versuch evaluiert: Python-Änderungen wurden
erkannt, CSS-Änderungen übersehen. Es ist deshalb noch kein Selektionsfilter des
Runners. Testmon-Deselektion mit pytest-Exit 5 gilt nicht als bestandenes Gate.

## Resultate und bekannte Fehler

Jeder Lauf schreibt private Logs, exakte Befehle, Phasenereignisse, JUnit und
`summary.json` je Seed. Der Terminal zeigt Fortschritt und nur neue, behobene,
weiter bekannte Fehler beziehungsweise INFRA. Exit 0 bedeutet: vollständiger
Lauf ohne neue Fehler oder Seed-Differenzen. Exit 1 bedeutet neue Fehler oder
abweichende Ergebnisse, Exit 2 Infrastruktur-/Vollständigkeitsfehler.

Ohne ausdrücklich bereitgestellte `reference_scaffold/tests/known-failures.txt`
gilt eine leere Fehlerliste: jeder fehlgeschlagene Test macht das Gate rot.
Die 42 roten IDs des ursprünglichen Versuchs wurden nicht übernommen. Eine
explizite Referenz braucht bestätigten Grund, Owner und Datum im Kommentarblock.
Ein nicht ausgewählter oder übersprungener Test ist nicht
behoben. Neue Fehler niemals automatisch übernehmen. `--reference-junit`
vergleicht zusätzlich IDs und Status einer expliziten Referenz; neue IDs werden
dabei ebenfalls gemeldet. Neue Werkzeugtests bei Vergleichen mit alten Suites
separat ausweisen.

URL-Userinfo in parametrisierten IDs wird vor Event-/JUnit-Ausgabe durch einen
stabilen SHA-256-Marker ersetzt. Unterschiedliche Fälle behalten unterschiedliche
IDs; die Log-Redaktion verändert diese Kennungen nicht. Zufällige Parameter-IDs
in bestehenden Tests bleiben ein möglicher Flaky-Befund und werden nicht kaschiert.

Flaky-Befunde brauchen Owner, Ablaufdatum und reproduzierbare Seeds im Report.
Keine neuen Skip-/Xfail-Regeln als Reparatur. Bis zur Klärung bleibt der Gate rot.

## Nachtjob und Evidence

`deployment/systemd/dishboard-test-gate.{service,timer}` ist nur eine Vorlage.
Sie wurde nicht aktiviert oder installiert. Der Orchestrator setzt Arbeitsbaum,
Interpreter und `/etc/dishboard/test-gate.env` mit `TEST_GATE_PYTHON` und vier
exklusiven `TEST_GATE_POOLS`. Der Dienst läuft zweimal mit voller Matrix und legt
Berichte unter `.claude/state/test-gate-nightly-*` ab. Gemeinsame Host-Ressourcen
und nötige Rechte vor Aktivierung prüfen.

Evidence-Schreiber können `_support.evidence.isolate_evidence` explizit als
Fixture importieren; dann nutzen sie standardmäßig pytest-Temporärpfade.
Bestehende Schreiber bleiben unverändert. `UI_EVIDENCE=1` erlaubt explizites
Erneuern ihrer getrackten Baselines. Baselines niemals blind übernehmen; Layout-/Funktionsbeweise bleiben
erforderlich. Manifest-/Paketprüfungen dürfen nicht durch automatische
Neugenerierung geschützter Dateien grün gemacht werden.
