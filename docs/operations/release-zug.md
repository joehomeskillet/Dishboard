# Release-Zug – Vorgehen für laufende Deploys

Verbindlich für jede Sitzung (Claude, Codex, Grok, agy), die an Dishboard arbeitet. Stand 2026-09-25.
Anlass: Zwischen Release 11 (2026-09-24 15:21) und Release 12 (2026-09-25 10:06) lagen 18 h 45 min ohne
Deploy, obwohl laufend Arbeit fertig wurde. Die Ursachen stehen am Ende dieses Dokuments.

## 1. Grundregel: Der Zug fährt nach Fahrplan

- Solange Arbeit läuft, fährt **spätestens alle 2 Stunden** ein Zug (Deploy). Ohne neue angenommene Arbeit fährt keiner.
- Mit fährt, was angenommen (Judge ACCEPT) und gegatet ist. Was nicht fertig ist, wartet auf den nächsten Zug.
- Der Zug wird **nie für ein Paket angehalten**, weder für ein fast fertiges noch für ein rotes.
- Jeder Status (Chat, Ledger, Übergabe) nennt Zeit und Alter des letzten Deploys:
  `rtk bash tools/release/deploy_status.sh`. Exit 1 heisst: Zug überfällig oder Produktion nicht gesund.

## 2. Pakete

- Höchstens **3 Templates bzw. ~1 h** Worker-Arbeit je Paket; Grösseres wird vor dem Start geteilt.
- **Judge sofort nach jedem Paket**, nicht nach der Welle. Hersteller ≠ Worker, Diff ab `git merge-base`.
- Fehlt einer gemeinsamen Komponente (Makro, Registry, CSS/JS) eine Fähigkeit, meldet der Worker das und
  bildet nichts ersatzweise ab. Die Erweiterung ist ein eigenes kleines Paket und fährt zuerst.
- Aktionen mit eigener fachlicher Wirkung behalten ihren spezifischen Text («Vorwoche kopieren»); generische
  Registry-Verben («Bestätigen», «Öffnen») nur dort, wo die Wirkung generisch ist. Das steht in jedem Brief.
- Abnahme je Paket, bevor es in die Integrationslinie geht:
  `rtk python3 tools/release/test_delta.py <paket-wt> <branch-basis>` (Exit 0: keine verlorenen Tests,
  Assertions oder neuen skips) und `rtk python3 tools/release/label_grep.py <paket-wt> main` (Treffer in den
  Paket-Gate aufnehmen, LOCKED = Text bleibt).

## 3. Pflicht-Checks vor jedem Zug

Feste Reihenfolge, je ein Befehl, im Integrations-Worktree `<int-wt>` (Branch `integrate/<welle>`), nie im
geteilten Haupt-Tree. Neue Dateien vorher mit `git add` erfassen.

| # | Check | Befehl | Weiter, wenn |
|---|---|---|---|
| 1 | Stand | `rtk bash tools/release/deploy_status.sh` | Stand gelesen (Exit 1 = überfällig, sofort fahren) |
| 2 | Label-Grep | `rtk python3 tools/release/label_grep.py <int-wt> main` | Exit 0; Trefferdateien nimmt das Gate automatisch in Teil D auf |
| 3 | Template-Hashes | `rtk python3 tools/release/refresh_template_hashes.py <int-wt> --apply` | Exit 0 |
| 4 | Manifest | `rtk python3 tools/release/sync_manifest.py <int-wt> main` | «Paketliste und SHA-256-Manifest: OK» |
| 5 | Commit | `rtk git -C <int-wt> commit -am "chore: release <n> manifest and template hashes"` | nur Matrix und Manifeste im Commit |
| 6 | Release-Gate + bekannte Rote | `rtk bash tools/release/release_gate.sh <int-wt> main [paket-tests …]` | `NEW_FAILURES=0`, verdict=0 |
| 7 | PII-Blob-Beweis | `rtk git -C <int-wt> rev-list --count HEAD -- docs/design/uiux-handoff-2026-09-20/03_REFERENCES/accepted-settings/a02b14e0-da12-4edd-b57e-8b3ce2d3082d.png` | `0` |
| 8 | Merge | `rtk git -C /nvmetank1/projects/menuplan merge --ff-only integrate/<welle>` | fast-forward |
| 9 | Push | `rtk git -C /nvmetank1/projects/menuplan push github main` | angenommen |
| 10 | Deploy | `rtk systemctl start dishboard-deploy-main.service` | Exit 0 |
| 11 | Verify | `rtk bash tools/release/deploy_status.sh` | Live = main, healthy, Login 200, Alter ≈ 0 min |

Das Gate (Schritt 6) läuft in vier Teilen parallel auf eigenen Pools (A Signage/Public, B Shell/Woche,
C Routen/Stores/Semantik, D Paket- und Label-Treffer) und wertet die JUnit-Dateien gegen
`tools/release/known_red.txt` aus. Danach Ledger-Eintrag: Revision, Deploy-Zeit, Inhalt, Gate-Zahlen.

## 4. Entscheidungsregeln

- **Nur der Test ist veraltet → blockiert nicht.** Test-ID mit Kommentarzeile (Datum, Grund, belegender Commit
  aus `git log -S '<assertierter Text>'`) in `known_red.txt`, Nachzug als eigenes Paket im nächsten Zug.
- **Produktregression → blockiert**, aber nur die betroffene Datei, nicht den Zug (Abschnitt 5).
- **Gesperrte Abnahmetests `*_accept.py` werden nie geändert.** Sie pinnen Produkttexte: Ein LOCKED-Treffer im
  Label-Grep oder ein roter `*_accept.py` heisst, das Produkt behält den alten Text.
- **Infrastruktur ist nie ein Produktfehler:** `Connection refused`, «Sync API inside the asyncio loop» oder ein
  ImportError aus dem Venv → Teil neu starten, nichts im Produkt «reparieren».
- Unklar, ob veraltet oder Regression? Ohne Beleg gilt Regression.

## 5. Zeitbox gegen Detailarbeit

- Findet der Orchestrator im Zug einen Fehler, setzt er die betroffene Datei (und die Dateien desselben Pakets,
  die von ihr abhängen) auf den Live-Stand zurück (`rtk git -C <int-wt> checkout main -- <datei>`, committen)
  und fährt ohne sie. Die Reparatur ist ein eigenes Paket für den nächsten Zug.
- **Höchstens 30 Minuten Orchestrator-Handarbeit pro Zug.** Kein Hunk-weises Retten, kein Nachziehen einzelner
  Test-Locators im Zug; das sind Pakete für Worker.

## 6. Sitzungsende und Übergabe

- Worker und Gates, die die Claude-Sitzung überdauern müssen, laufen ausserhalb von ihr, z. B.
  `rtk systemd-run --unit=dishboard-gate-<name> --collect bash <repo>/tools/release/release_gate.sh <int-wt> main`
  (Log: `journalctl -u dishboard-gate-<name>`; als root ohne `--user`) oder
  `rtk setsid -f nohup bash <skript> > <log> 2>&1`. Nie als Hintergrund-Task der Sitzung.
- Vor Sitzungsende Übergabe-Eintrag im Wellen-Ledger (`.claude/state/<welle>-ledger.md`): letzter Deploy
  (Zeit, Revision), was in der Integrationslinie wartet, laufende Units und Logs, nächster Zug fällig um.
  Zusätzlich `rtk claude-handoff`.
- Die nächste Sitzung beginnt mit `deploy_status.sh` und fährt einen überfälligen Zug zuerst.

## 7. Infrastruktur

- Test-Venv: `DISHBOARD_TEST_VENV`, Default `/var/lib/dishboard-test-venv`. Fehlt er, nutzt `gate.sh` mit
  Warnung `/tmp/dishboard-shared-venv`; dort löscht systemd-tmpfiles Dateien nach 10 Tagen. Aufbau:
  `rtk python3 -m venv --system-site-packages /var/lib/dishboard-test-venv`, dann
  `rtk /var/lib/dishboard-test-venv/bin/pip install -r reference_scaffold/requirements.txt`
  (pytest und Playwright kommen aus den System-Paketen).
- Pools: `gate.sh` liest die Pool-Env-Dateien aus `.claude/state/handover-2026-09-05/` im Haupt-Checkout (lokal,
  nicht im Repo; enthalten Zugangsdaten, nie ausgeben) und löst die Ports per `docker port` auf.
- Host-Grenze: höchstens vier Gate-Prozesse gleichzeitig, vor dem Zug `rtk pgrep -fc "python -m pytest"` < 10;
  ein Pool nie von zwei Gates zugleich.
- Release-Werkzeuge liegen in `tools/release/`, nie nur in einem Session-Scratchpad.

## Ursachen des Vorfalls 2026-09-24/25 (Herkunft der Regeln)

1. Pakete mit 5–13 Templates; die Welle von 6 Paketen wurde abgewartet (Wochenplan fertig 15:55, ausgeliefert
   erst 10:06 am Folgetag). → Abschnitte 1, 2
2. Judges erst nach Wellenende; 5 von 6 Paketen REJECT (generische Verben für Aktionen mit eigener Wirkung),
   zwei davon auch nach der Nacharbeit. → Abschnitt 2
3. `icon_button` konnte keine Kontextnamen, Zusatzklassen und Hervorhebung; erst die Judges fanden die Lücke. → Abschnitt 2
4. Label-Änderungen brachen Tests ausserhalb der Gate-Listen, auch den gesperrten `*_accept.py`. → Schritt 2, Abschnitt 4
5. Keine gepflegte Liste bekannter roter Tests; jeder Baseline-Vergleich wurde ad hoc gefahren. → `known_red.txt`
6. Test-Venv in `/tmp` von systemd-tmpfiles beschädigt; Werkzeuge nur im Scratchpad. → Abschnitt 7
7. Sitzungsende 00:50 stoppte alle Worker und Gates, ohne Übergabe bis zum Morgen. → Abschnitt 6
8. Der Orchestrator reparierte Hunk für Hunk und Locator für Locator, statt den Zug fahren zu lassen. → Abschnitt 5
