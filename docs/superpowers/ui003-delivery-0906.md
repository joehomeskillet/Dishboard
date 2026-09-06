# UI-003 — sichtbare Feldbeschriftungen und eindeutige Wochenkartenaktionen

Status: unabhängig geprüft, noch nicht produktiv. Root-WP `wp-8b57137108b3`, Basis `cc6c8ce`; eigener Worktree `backlog-ui003-0906`. Der separat eingefrorene Branding-Release wird dadurch nicht verändert.

## Umsetzung und Review

- `1c8d9e9`: vorhandene Tabler-Feldbeschriftungen für Komponenten und Herkunft sichtbar; Präsenz-Auswahlen für Allergene haben direkte Labels. Komponentenhinweis wird korrekt referenziert. Beim Hinzufügen, Verschieben oder Entfernen von Zeilen bleiben ID-, Label- und Beschreibungsbezüge erhalten; neue Zeilen übernehmen keine alten Fehlermeldungen. Die vorhandene mobile Fehlerübersicht nutzt die Tabler-Utility `d-block` und hält ihre Wiederholungsaktion im Bildschirm.
- `34d704f`: drei vorhandene Bearbeiten-Links bekommen konkrete zugängliche Namen aus Tag, Mahlzeit, Menüoption und Titel. Sichtbarer Text, Zielparameter und vollständige gleich grosse Karten bleiben erhalten.
- Unabhängiger Review `wp-eb61f4e22d6c` fand ein fehlerhaftes Initialfokus-Ziel bei deaktivierten Allergen-Präsenzen. Anderer Autor korrigierte dies in `0504d94`: nur aktive tatsächlich ungültige Werte werden markiert; Fokus überspringt deaktivierte/verborgene Controls und bleibt ohne gültiges Ziel auf der Fehlerübersicht. Kein erfundener Titel-Fehlerfallback. Echte HTTP-400-Tests prüfen den Fokus vor manueller Interaktion und den anschliessenden korrigierten Save.

Produktdiff: bestehende Templates und `admin.js`; keine neue Dependency, Route, Palette oder Formpayload. Der gemeinsame Editorrenderer wurde als HIGH-Impact-Verbraucher vorab gemeldet; seine Pythonimplementierung bleibt unverändert. Root las die finalen Diffs und prüfte sie unabhängig.

## Unabhängige Root-Gates

Alle DB-Läufe im eigenen Integrations-Worktree auf exklusivem Pool `test-ps1`, jeweils beide bzw. alle genannten Module vollständig und mit eigenem Basetemp. Die Testmengen überschneiden sich; keine Addition zu einer Gesamtsuite.

```text
Wochenkarten, Tabler-Wochenworkflow und Formularfokus:
34 passed in 72.93s (0:01:12)
GATE_EXIT=0

Feldbeschriftungen, Save/Back und Formvertrag vor gesondertem Fokusfix:
53 passed in 70.90s (0:01:10)
GATE_EXIT=0

Finaler Fokusfix, vollständige Editor-/Saveback-/Form-/AdminUX-Module:
75 passed in 109.05s (0:01:49)
GATE_EXIT=0
```

Logs `/tmp/dishboard-root-ui003-{week-links,editor-labels,editor-focus}-gate-0906.log`. Root betrachtete das mobile kompakte Fehlerbild aus `/tmp/dishboard-root-ui003-editor-focus-0906`; zwölf aktuelle Bilder decken 390/820/1440 und beide Dichten ab. Ruff sowie `node --check` bestanden. GitNexus-Index mit offiziellem `--index-only` erzeugt, vor Commit staged Detect: LOW, erwartete UI-/Test-Symbole, keine erkannten Ausgabeflows.

Testhygiene `2cc677f` verlegt die vier bestehenden Food-Symbol-Screenshots mit identischen Namen nach `tmp_path`. Keine Assertion entfällt; Root wiederholte das vollständige Modul: `36 passed in 20.41s`, `GATE_EXIT=0`, Log `/tmp/dishboard-root-food-symbol-test-artifacts-gate-0906.log`. So hinterlassen die Tests keine `.claude`-Dateien im sauberen Paketexport.

## Lesender Branding-Prüfer

`3491a21` und unabhängiger Fix `4cc47ba` werden im Folgestand versioniert. Der Prüfer führt nur vorhandenen Login und GET/HEAD aus. Er verlangt aktuelle aktive Revision/Tokens/Logo, vollständige tatsächliche Menükarten, seitenbezogene Legenden, geladene Symbolassets und korrekte Abmessungen. Fehlende veröffentlichte Daten oder geschlossene Dienste ergeben gesonderte unvollständige Abdeckung. PDF-Abnahme bleibt ein ausdrücklicher separater Schritt.

Root prüfte beide vollständigen Offline-Module unabhängig: `91 passed in 15.71s`, Exit 0; Log `/tmp/dishboard-root-branding-proof-offline-gate-0906.log`. Der echte lokale HTTP-/Chrome-Test setzt strikte CSP und führt die Patientenrotation aus. Keine Produktionsmutation durch diese Tests, kein daraus abgeleiteter Live-PASS.

Die vollständige Scopeprüfung nach Aufnahme des Prüfers und der Zusatzdokumente meldet MEDIUM: zwölf Dateien, vier ausschliessliche Prüfer-CLI-Abläufe, keine zusätzlichen App-Routen. Der graphische LOW-Befund oben bezieht sich auf den zuvor getrennt geprüften UI-Teil. Der nachfolgende Prüfer-Launcher-Fix bindet die automatische Produktionsanmeldung an ihre feste Origin und den tatsächlich vorhandenen Chrome-Pfad; vor dessen eigener Abnahme kein abschliessender Prüfer-Commit.

Mitgeführt werden die separat geprüfte IAM-001-SDD `553d25e`/`4b95d7d` und die belegte pdfme-Designer-/Tabler-Lücke `87a361d`. Die SDD definiert einen engen UUID-/Namenskontext vor der Passwortpolicy und vollständige Schema-/Paket-/Fixture-Ownership; sie ist keine implementierte Benutzerverwaltung. Der offizielle pdfme-Designer erfüllt die verlangte vollständige Tabler-Bedienoberfläche nicht; TPL-002 bleibt offen.

## Noch offen

Eigenständiger vollständiger Paket-/Manifest-Gate und tatsächlicher Folgedeploy mit lesender Browserabnahme. OCR bleibt wegen belegter Providerfehler dieser laufenden Welle nicht verfügbar; kein CLEAN. Externer Design-Validator war mangels Gemini nicht ausführbar; seine frühere Dummy-GREEN-Ausgabe wird nicht als Abnahme verwendet. Bestehende Backlog-Abnahmegrenzen bleiben offen, bis ihre tatsächliche Lieferung belegt ist.
