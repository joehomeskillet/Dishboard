# Private Notiz — wp-d7589450daee (Beweiskorrektur UI-Inventar)

Worktree `ui-inventory-proof-fix-0909`, Branch `fix/ui-inventory-proof-fix-0909`.
Originalautor der Aufnahmestrecke ist Grok; dieses WP korrigiert ausschliesslich
die von Root unabhängig geprüften Beweislücken. Kein Produktcode, kein fremder
Pool, keine Unterdelegation, kein Push und kein Merge.

## Was tatsächlich geändert wurde

| Datei | Rolle |
|---|---|
| `.claude/evidence/ui-inventory-grok-0909/capture.py` | Recorder: Listener-Lebensdauer, `await_ready`, `rendered_fonts` via CDP, `Outputs`, gemessener Publish-Dialog |
| `.claude/evidence/ui-inventory-grok-0909/build_matrix.py` | `write_matrix(target)` + `--out`, damit ein Lauf nicht zwingend die versionierte Matrix überschreibt |
| `reference_scaffold/tests/test_ui_route_inventory.py` | echte Revisions-Fixture, Kopier-Erfolgspfad, Umleitung der Ausgaben, Unverändertheitsprüfung |
| `reference_scaffold/tests/test_ui_inventory_capture.py` | neu, fünf Recorder-Tests gegen einen echten Browser |
| `.claude/evidence/ui-inventory-proof-fix-0909/` | neu: Regressionsbeweis, neuer Aufnahmesatz, Abdeckungsmatrix, diese Notiz |

Nicht angefasst: die 111 Original-PNG, `endpoint_templates.json`,
`visual-inspection.md`, `docs/superpowers/backlog-0909/ui-route-matrix.json`,
`docs/superpowers/backlog-0909/ui-before-manifest.json` und jede Produktdatei
unter `reference_scaffold/cafeteria/`.

## Warum die Korrektur so aussieht

**Listener.** Der ursprüngliche `shot()` hat `console` und `pageerror` im
`finally` direkt nach `page.goto(..., wait_until='domcontentloaded')` abgehängt
und danach 250 ms gewartet. Jeder Fehler in diesem Fenster fiel unter den Tisch —
und genau dort passieren die interessanten Fehler. Die Listener bleiben jetzt bis
nach Screenshot und Messung attachiert. `regression-proof.py` zeigt beide
Recorder nebeneinander auf derselben Seite: Original leer, korrigiert mit beiden
Meldungen.

**Bereitschaft.** `page.wait_for_timeout(250)` ist keine Bereitschaft, sondern
eine Hoffnung. `await_ready` wartet auf `load`, macht einen begrenzten
Scroll-Durchlauf, damit `loading="lazy"`-Bilder überhaupt angefordert werden,
und wartet dann auf `document.fonts.status === 'loaded'` und `img.complete` für
alle Bilder. Ohne den Scroll-Durchlauf laufen `/cafeteria/wochenangebot/` und
`/patienten/wochenplan/` in einen echten Timeout — der ursprüngliche Recorder
hat für diese Seiten fotografiert, bevor die Bilder da waren, und das Ergebnis
trotzdem als gerendert geführt.

**Schriften.** Die deklarierte CSS-Familie beweist nichts über das, was der
Browser tatsächlich rastert. `rendered_fonts` liest zusätzlich
`CSS.getPlatformFontsForNode` über CDP und schreibt `platform` plus
`platform_source` ins Manifest; fällt CDP aus, steht das ausdrücklich als
`platform_source: 'unavailable'` drin statt als stille Lücke.

**Publish-Dialog.** Vorher war die Zeile hartkodiert: Status 200, kein Overflow,
keine Fehler — unabhängig davon, ob der Dialog je aufging. Jetzt öffnet
`open_modal` den Dialog wirklich, wartet auf sichtbar und `.show`, und wenn der
Auslöser fehlt oder deaktiviert ist, entsteht ein `blocked_modal_not_open`-Eintrag
statt einer erfundenen Erfolgszeile. Ein blockierter Beweis ist mehr wert als ein
falscher.

**Ausgabepfade.** Ein gewöhnlicher Testlauf darf keine versionierten Belege
überschreiben. `Outputs` trennt Standardziel und Laufziel; der Regressionslauf
schreibt nach `tmp_path` und prüft anschliessend Matrix, Manifest und alle
Original-PNG byteweise. Nur ein ausdrückliches `UI_CAPTURE_OUT` erzeugt einen
getrennten neuen Satz — und auch der überschreibt die Baseline nicht.

**Fixture statt Ausrede.** Die Begründung, Revisionsdetail und Kopier-Erfolg
seien mangels Fixture nicht belegbar, hielt nicht: `recipe_store.create_recipe`
plus `freeze_revision` erzeugen eine echte unveränderliche v1-Revision, und die
gespeicherte Woche 2026-08-31 ist die reale Vorwoche zu 2026-09-07, deren
Zielwoche noch nicht existiert — damit rendert der Kopierpfad das echte Formular
statt eines 404.

## Offene Punkte für Nachfolgepakete

- Der Lazy-Load-Befund an `templates/_menu_image.html:4` ist ein reales
  Aufnahmeproblem, kein Produktdefekt. Wer künftig Ganzseiten-Screenshots macht,
  braucht denselben Scroll-Durchlauf.
- Barrierefreiheit, Kontrast und Tastaturbedienung sind hier nicht abgedeckt und
  gehören in die Migrationspakete.
- Entra gegen einen echten Tenant und der physische Yodeck-Player bleiben offen;
  sie werden nicht simuliert.

## Hashes

- `capture.py` `a6add255605253641943eb562e70fc0a375017013a6f01ac16ea40497a5bb9ec`
- `build_matrix.py` `257b0d5877f5760f07dc6daa2507b574e2b6a6878ff2306284afb3dbf2c8f7e0`
- `test_ui_route_inventory.py` `7650620a5b2db1f8d80685b9ae84ebb17c711fcc788dd07d9411379d9eeb684f`
- `test_ui_inventory_capture.py` `7b32e039f1616416a880b59f631eec51992a95d45bb60baf9abbe068b9249d5f`
- neues Manifest `5380e3ecd2971a451705a4acd23bc0b4cce8138f39c132cba4ef70db1e27d5d1`
- Original-Screenshotsatz unverändert `0b2cfaee0cdc27fa243d546fe2d94bc869fed6e71884636ea3a89f4077137ba7`
