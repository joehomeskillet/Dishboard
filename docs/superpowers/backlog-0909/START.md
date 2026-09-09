# Startauftrag für jedes Coding-Tool

Dieser Start braucht keine vorangegangene Unterhaltung. Der Orchestrator setzt
die fünf Werte ein: **MP-ID, WP-Datei, vollständiger Basiscommit, eigener Worktree,
Routing-WP-ID**. Bei DB-/Browserarbeit gehört eine aktuelle exklusive Testumgebung
zur Zuweisung. Solange diese fehlt, sind Quellenarbeit und reine Tests möglich;
keine fremde Datenbank übernehmen.

## Gemeinsamer Prompt

```text
Arbeite genau MP-ID=<ID> aus WP-Datei=<JSON-PFAD> ab.
Routing-WP=<wp-ID>; Basis=<vollstaendiger SHA>; eigener Worktree=<ABSOLUTER PFAD>.

Lies docs/superpowers/backlog-0909/README.md, execution-contract.md und die im
WP genannten SDD-Abschnitte vollstaendig. Lies vorhandene Projekt-AGENTS.md;
fehlt sie im Worktree, gilt trotzdem der versionierte execution-contract.md.
Vor jeder Frontend-Arbeit docs/design/2026-09-09-unified-ui-design-system.md
vollstaendig lesen. Gemeinsame Tokens/Komponenten/Layoutvarianten verwenden;
keine fachlichen Aenderungen als Nebenprodukt, keine Baselines blind ersetzen.
Pruefe tatsächlichen HEAD, zugewiesenen Branch und Dateibesitz. Du bist Worker,
nicht Orchestrator, und nicht allein im Repository. Keine eigene weitere
Delegation, keine Bearbeitung eines anderen MP, kein Push/Merge/Deploy.

Alle Shell-Aufrufe direkt rtk, jeweils ein Befehl, keine Pipelines/Verkettungen
oder rtk proxy. Keine Credentials lesen/ausgeben, keine Dependencies installieren,
keine Produktivdaten als Fixture. Bestehende Dateien gezielt patchen. Vor jedem
Symbol-Edit GitNexus-Impact, vor Commit detect_changes. HIGH/CRITICAL melden.

Implementiere den vollstaendigen zugewiesenen Vertrag samt Anschluessen. Sichere
Originalauthz/Standort/CAS/Audit, vorhandene Historie und Mengenvertraege.
Gates laut WP mit echten Binaries ausführen, rohe Ausgaben und Exitcodes bewahren.
Ein fehlendes Gate ist kein PASS. Screenshots bei UI selbst kritisch ansehen.

Committe ausschliesslich eigene Dateien. Schreibe und registriere vollständigen
WP-Bericht mit Quelle, Commitliste, Gatebelegen, fehlenden Checks und Grenzen.
Bei Fehler genau ein identischer Retry gemaess Ausfuehrungsvertrag; Einmalabläufe
nicht blind replayen. Bei beobachtetem Kontingentende Zustand sichern und melden,
kein stiller Modellwechsel. Beende mit WP-REPORT: DONE|BLOCKED und konkretem Umfang.
```

## Werkzeugeinstiege

Die CLI steuert nur Transport und Authentifizierung. Inhalt bleibt der gemeinsame
Prompt. Lange Aufträge als Datei im eigenen Worktree ablegen und deren Pfad im
Prompt nennen. Dateitext nicht per `eval` oder ungeschützter Shell-Interpolation
ausführen. Modellwahl entsprechend zugewiesenem WP und tatsächlich verfügbarer Lane.

Codex kann im eigenen Worktree mit `codex exec` gestartet werden. Bei Verwendung
des vorhandenen Host-Sandbox-Wrappers dessen dokumentierten Aufruf verwenden;
keine zweite Sandbox ineinander verschachteln. Für Grok-Build ist der vorhandene
Plugin-Bridge-Aufruf mit `--cwd <worktree>` vorgesehen. Claude Code kann interaktiv
denselben Prompt erhalten oder über den vorhandenen `csd`-Controller gestartet
werden. Root hat im Planungsdurchlauf tatsächlich gestartet:

| Lane | Einstieg | Laufender Planungsteil |
|---|---|---|
| Claude Code | `csd launch` und worker-spezifisches `send` | Rezepte/Grundlagen/Importe |
| Grok-Build | `grok-bridge.mjs run --write --cwd ... --effort high` | Kosten/Lager/Bestellungen/Fachwissen |
| AGY | `agy-run -p ... --add-dir ... --dangerously-skip-permissions` | Oberfläche/Zugriff/Abnahme: Original und identischer Retry mit Timeout beendet; an eigenen Codex-Worktree übergeben |
| Codex | Aktuelle Orchestratorsession und bestehende isolierte Worker | Integration, Prüfung und laufende Rezeptverträge |

Dies beweist gestartete Aufrufe, keine identischen Modellfähigkeiten und keinen
Abschluss ihrer Aufgaben. Konkrete Instanz-/Commitbelege stehen im Planungsbericht.

## Übernahme eines unterbrochenen WP

Alten Worktree, Commit, uncommitteten Diff und Belege erhalten. Tatsächlichen
Prozesszustand prüfen, bevor eine zweite Lane Schreibbesitz erhält. Danach eigener
Worktree auf benanntem Stand, ursprünglicher Auftrag unverändert, vorhandene
Teiländerungen ausdrücklich übernehmen. Keine automatische Neuerstellung anhand
eines alten Statusnamens. Orchestrator hält den einzigen Besitz- und Integrationsplan.
