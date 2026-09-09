# Gemeinsamer Ausführungsvertrag für Coding-Tools

Dieser Vertrag gilt identisch für Codex, Grok-Build, Claude Code und jede weitere
beauftragte Lane. Ein Toolwechsel ändert weder Sollumfang noch Qualitätsgrenze.
Aktuelle Nutzeranweisungen und Projekt-Governance bleiben vorrangig.

Vor jeder Frontend-Änderung ist das
[konsolidierte Designsystem](../../design/2026-09-09-unified-ui-design-system.md)
vollständig zu lesen. Es ist die einzige aktuelle Quelle für Palette, Typografie,
Masse, Komponenten und Layoutvarianten. Konkrete Marken-/Projektkonflikte vor
Änderungen dokumentieren; keine Fachfunktion oder Datenmigration als UI-Nebenprodukt.

## Auftrag und Besitz

Vor Start nennt der Orchestrator genau eine `MP-*`-ID, deren JSON-Datei, den
freigegebenen vollständigen Basiscommit, eigenen Worktree/Branch und das zugehörige
`wp-*`-Routingartefakt. Er ergänzt konkrete Testumgebung und reservierte Dateien.
Ein Worker wählt keine bereits laufende Aufgabe selbst. Ausgewählte Lane und
tatsächlich verwendetes Modell werden als Ausführungsdaten erfasst; ein Vorschlag
des Routers ist kein Beweis für das tatsächlich gestartete Modell.

Vor Worktree-Erstellung Remote aktualisieren; den ausdrücklich freigegebenen
Integrationscommit verwenden, wenn er von `github/main` abweicht. Fremde dirty
Arbeit bleibt erhalten. Keine Paketinstallation im Worktree, keine neuen
Dependencies ohne spezifisch freigegebenes Paket. Ein Worker schreibt nur eigene
Dateien, commitet auf eigener Branch und pusht, merged oder deployed nicht.

Vertrags- und Anschlussdateien einer Änderung gehören zum selben WP. Erforderliche
Anschlussarbeiten dürfen nicht als angeblich erledigte Teilimplementierung
abgegeben werden. Treffen sie auf bereits reservierte Dateien, klärt der
Orchestrator Besitz und Reihenfolge vor Mutation; keine konkurrierenden Änderungen.

`contract_files` und `wiring_files` sind Schreibbesitz und müssen vollständig in
`owned_files` enthalten sein. Reine Leseverträge stehen getrennt in
`read_only_contract_files`; sie erteilen kein Schreibrecht und reservieren keinen
Writer. `source_anchors` benennen die tatsächlich zu prüfenden Quellstellen.
Eine notwendige Anschlussänderung wird nicht durch Umbenennen zur Lesereferenz.

Alle Shell-Befehle beginnen direkt mit `rtk`. Pro Shell-Aufruf genau ein Befehl,
keine Verkettung, Pipeline oder `rtk proxy`. Artefakte enthalten keine Credentials.
Keine Credential-Dateien lesen/anzeigen; bestätigte Testwrapper laden ihre eigene
Umgebung still. Datenbankpools sind exklusiv und werden nicht nach alten Notizen
wiederverwendet. Produktivdaten, bestehende Login-Baselines und fremde Container
sind keine Testfixtures.

## Status

| Zustand | Bedeutung |
|---|---|
| `PLANNED` | Vollständiger Auftrag vorhanden; Voraussetzungen noch offen. |
| `READY` | Voraussetzungen belegt, keine externe Eingabe fehlt; Besitz wird vor Start erneut geprüft. |
| `IN_PROGRESS` | Reale laufende Lane mit benanntem WP und eigenem Worktree. |
| `AWAITING_EXTERNAL` | Konkrete externe Eingabe fehlt; nur dieses Paket und abhängige Pakete warten. |
| `REVIEWED_LOCAL` | Implementierung/Artefakt unabhängig geprüft, noch kein behaupteter Deploy. |
| `INTEGRATED` | Geprüfter Commit im benannten Integrationsstand. |
| `DEPLOYED` | Release-/Image-/Schema- und Live-Beleg vorhanden. |
| `ACCEPTED` | Sämtliche zugehörigen technischen und fachlichen Kriterien belegt. |

Fehler oder Kontingentende werden als Ausführungsereignis mit unverändertem
Fachauftrag festgehalten. Ein Worker darf seinen eigenen Bericht nicht als
unabhängige Freigabe einstufen. `ACCEPTED` einzelner WPs schliesst eine Backlog-ID
nur, wenn alle ihre Kriterien und abhängigen Abnahmen erfüllt sind.

## Einheitliche Arbeitsfolge

1. Auftrag, SDD-Abschnitte, tatsächliche Dateien und Projektregeln lesen; Ursprung,
   Basiscommit und Eigentum prüfen. GitNexus bei unbekannten Abläufen verwenden.
2. Vor Symboländerungen Impact analysieren. HIGH/CRITICAL vor Änderung melden.
   Nicht indexiertes SQL ist unbekannter automatischer Impact, keine LOW-Einstufung;
   Datenbank-/ACL-Auswirkungen separat anhand Aufrufern und Privilegien prüfen.
3. Kleinsten vollständigen vertikalen Umfang implementieren. Bestehende Dateien
   gezielt patchen. Neue Python-Module unter etwa 400, nie über 600 Zeilen.
4. Vertrauensgrenzen, Fehlerfälle, Originalversionen und unveränderliche Historie
   prüfen. Fachliche Annahmen ausdrücklich markieren; keine Daten erfinden.
5. Passende Tests, Lint und Typprüfung gegen reale installierte Binaries ausführen.
   Ergebnisse mit originaler Ausgabe, Exitcode, Basis-/Quellcommit und Umgebung
   speichern. Baseline-Fehler separat vergleichen, keine pauschalen Suppressions.
6. GitNexus `detect_changes` vor Commit, Diff-/Scope-/Secret-Prüfung und vorgesehenes
   Review ausführen. Unverfügbare Gates als unverfügbar benennen.
7. Eigene Änderungen committen, Bericht dauerhaft registrieren. Orchestrator liest
   tatsächlichen Diff und führt unabhängig relevante Gates erneut aus.
8. Nur Orchestrator integriert, aktualisiert Manifest, prüft Release, deployed und
   sammelt Live-Belege. Schema-/Datenkompatibilität vor Umschaltung nachweisen.

UI-WPs benötigen echte Browserinteraktion mit 390 und 1440 Pixeln, bei relevanten
Zwischenzuständen zusätzlich 820 Pixel. Signage erhält 1920×1080 und 3840×2160.
Für die konsolidierte UI-Migration gilt zusätzlich die vollständige neue Matrix:
1440×900, 1024×768, 768×1024, 390×844 und 1920×1080. Jede migrierte Route mindestens
Desktop und Smartphone, Referenztypen und gemeinsame Komponenten in allen fünf
Viewports; Tastatur, 200%-Zoom, reduzierte Bewegung und gemessene Kontraste erfassen.
44 Pixel sind Projektstandard und keine pauschale Behauptung über WCAG-AA.
Screenshots visuell beurteilen, Rollen/CSRF/Fehlerzustände und No-JS-Grundfunktion
prüfen. Native PDF-Anzeige, heruntergeladene Bytes und Papierlayout sind getrennte
Prüfungen. Tatsächlichen Yodeck-Player und Küchendruck nicht durch Screenshots ersetzen.

## Fehler, Kontingente und Übergabe

Reine fehlgeschlagene CLI-/Toolaufrufe genau einmal identisch wiederholen, dann
beide Ausgaben mit Zustand eskalieren. Zustandsverändernde Einmalabläufe nach
Fehler zuerst anhalten und Ursache/Zustand sichern; keine blinde Wiederholung von
Login, Import, Bestellung, Seed oder Release-Umschaltung.

Keine automatische Kontingent-Vorabprüfung. Beauftragte Lane tatsächlich starten.
Ein beobachtetes Quoten-/Balance-Limit wird dokumentiert und die betroffene Lane
gestoppt; den tatsächlich betroffenen Provider mit
`rtk agent-quota-mark-down <provider>` markieren und `ESCALATE: LANE-DOWN <provider>`
melden. Kein unbezahltes Kontingent vortäuschen, kein stiller Anbieterwechsel,
keine automatisch zugeschalteten Zusatzcredits. Der Orchestrator kann einen
unfertigen Auftrag nach Zustandsprüfung an eine andere geeignete verfügbare Lane
übergeben. Diese bekommt denselben WP-Text, bisherigen Diff und Fehlerbelege.

Ein bestätigter unabhängiger Reviewbefund geht zur Korrektur an einen anderen
Autor. Dessen Fix erhält eigene Belege; alte fehlgeschlagene Nachweise bleiben
erhalten. Keine unveränderten Gesamtsuiten wiederholen, wenn gezielte Tests einen
isolierten neuen Fix vollständig prüfen können; neue Releases benötigen ihre
eigene vollständige Paketprüfung.

## Gemeinsamer Bericht

Der Bericht enthält `MP-ID`, `wp-ID`, tatsächliche Lane/Modell, Worktree, Branch,
Basis- und Ergebniscommits, geänderte Dateien, geprüfte Kriterien, exakte Gate-
Ausgaben, nicht ausgeführte Gates, Risiken und nächsten Abhängigkeitsschritt.
Review, Integration und Deploy erhalten eigene Belegfelder. Keine Klartext-Secrets.

Bestehenden Host-Berichtsspeicher verwenden:

```bash
rtk claude-wp-report dir
rtk claude-wp-report record --wp-id <wp-id> --agent <actual-lane> --path <report.md> --tldr '<concrete result>'
```

Der erste Aufruf liefert das Zielverzeichnis; den Bericht per Dateiwerkzeug dort
ablegen, ohne Shell-Verkettung oder Kommandoersetzung. Letzte Berichtzeile:
`WP-REPORT: DONE|BLOCKED — <konkreter Umfang>`. Grok-Build ergänzt seine tatsächliche
`SECURITY-CHECK:`-Zeile. Eine gespeicherte Zeile ersetzt keine gelesenen Belege.

## Gegenwärtige Umgebungsgrenzen

Der bekannte Python-Binary ist `/tmp/dishboard-shared-venv/bin/python`, Ruff und
Mypy liegen unter `/root/.local/bin/`. Reale Pfade vor Verwendung prüfen, nicht
installieren. Der bestehende vollständige Paketprüfer ist
`tools/validate_package.py`; er führt die Tests im exportierten Paket aus.
Ein Entwicklerlauf verwendet im Verzeichnis `reference_scaffold`:

```bash
rtk /tmp/dishboard-shared-venv/bin/python -B -m pytest -q -p no:cacheprovider tests/<assigned-tests>.py
rtk /root/.local/bin/ruff check <owned-python-files>
rtk /root/.local/bin/mypy --python-executable /tmp/dishboard-shared-venv/bin/python --follow-imports=silent <owned-production-files>
```

Diese Syntax allein stellt keine Testdatenbank bereit. Datenbank-/Browserpakete
erhalten vor Start einen aktuellen exklusiven Wrapper und Portzuordnung.
PostgreSQL 16 ist kein Nachweis für PostgreSQL-18-spezifisches Verhalten.
OCR war im laufenden Vorgang nach zwei HTTP-429-Antworten unverfügbar; das bleibt
ein fehlender Reviewbeleg und wird weder als CLEAN noch als Dauerfreistellung geführt.
