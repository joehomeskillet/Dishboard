# Bildlose Wochenplan-Vorschauen und UI-003-Editorverbesserungen

Status: **`0acd992` produktiv seit 06.09.2026, 11:14:04 Uhr Schweiz**, Image `sha256:110bbc6ce858cc881b825d0b2b78c282c727ca804fc0ccbafb983e881aaa7e30`, frisch als `healthy` bestätigt. Schema **18** bleibt unverändert; externe Readiness HTTP 200. Root-WP `wp-8b57137108b3`, Basis `cc6c8ce`; Integrationsworktree `backlog-ui003-0906`. [Vollständiger aktueller Releasebeleg](/nvmetank1/projects/rag-stack/.claude/reports/wp-8b57137108b3.md).

Die vollständige unabhängige Paketprüfung und Manifestprüfung sind abgeschlossen: **3877 bestanden, 15 ausdrücklich optionale Compose-/Restore-Skips, keine Fehler/Fehlschläge**, `PACKAGE_GATE_EXIT=0`. Nach dem tatsächlichen Neustart bestanden **386 Screens-Checks sowie 194 API-/Admin-/PDF-Checks** mit 38 neuen Screenshots und echten neuen Wochen-PDF-Downloads. Diese frischen Belege stehen getrennt von den älteren Teilgates unten; überlappende Testmengen werden nicht addiert. UI-003 und die zusätzlichen bildlosen Wochenrouten samt Hub-Vorschauen sind damit live.

## Zusätzliche Wochenpläne ohne Bilder

Der Nutzerauftrag vom 06.09.2026 ergänzt zwei feste Web-Varianten: `/cafeteria/wochenangebot/ohne-bilder/` und `/patienten/wochenplan/ohne-bilder/`. Commit `c5d79c3` verwendet dieselben bestehenden Handler und Templates mit einer serverseitigen Bildoption; Foto- und Fallbackcontainer entfallen vollständig. Der Profilwechsel behält die bildlose Variante. Die bestehenden URLs mit Bildern und die strikte Ablehnung aller Queryparameter bleiben erhalten.

Unter `/admin/screens` bieten die beiden Web-Karten jeweils einen dritten Vorschau-Tab und Link «Wochenplan ohne Bilder». Vier gleich grosse Karten enthalten insgesamt zehn echte Vorschauen. Die schon zuvor bildlosen Signage-Wochen sind entsprechend beschriftet. Keine Datenbankänderung, kein neuer Editor, keine Dependency.

Root hat den finalen Diff gelesen und die drei vollständigen Public-/Hub-Module plus das gesamte Branding-Header-Modul im eigenen Integrationsstand erneut auf `test-ps5` ausgeführt:

```text
53 passed in 96.17s (0:01:36)
GATE_EXIT=0
```

Log `/tmp/dishboard-root-screens-no-images-gate-0906.log`. Eigene echte Browserbelege bei 390/820/1920 px prüfen zehn Cafeteria- und 28 Patientenkarten, null Fotoabrufe, vollständig erhaltene Metadaten und Legenden, gleiche Abmessungen und ungekürzte Langtexte. Root hat das Patientenbild ohne Fotos und die mobile Hub-Vorschau selbst betrachtet. GitNexus meldet HIGH: zehn bestehende Snapshot-/Cache-/Datumsabläufe mit Änderungen ausschliesslich am jeweiligen Wochenplan-Handler. Die Helfer selbst sind unverändert; Warnung vor Root-Integration kommuniziert. Ruff und begrenzte Mypy-Prüfung beider betroffener Pythonquellen bestanden.

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

Die damalige Scopeprüfung nach Aufnahme des Prüfers und der Zusatzdokumente meldete MEDIUM: zwölf Dateien, vier ausschliessliche Prüfer-CLI-Abläufe. Der graphische LOW-Befund oben bezieht sich auf den zuvor getrennt geprüften UI-Teil. Entrypointfix `e23e820` bindet die automatische Produktionsanmeldung an ihre feste Origin und den tatsächlich vorhandenen Chrome-Pfad; Root wiederholte beide vollständigen Module: `97 passed in 15.95s`, Exit 0.

Der erste echte Branding-Aufruf und genau ein identischer Retry endeten trotzdem beim Login mit `TypeError`: Playwright-FormData lieferte Listenpaare, die urllib nicht als Tupel-Sequenz akzeptierte. Ein unabhängiger Autor korrigierte genau diese Serialisierungszeile in `b63fad6`. Ein realer lokaler HTTP-/Chrome-Test prüft jetzt tatsächlich gesendete URL-encoded Werte einschliesslich Duplikaten/Unicode, unverfolgte Weiterleitung und Session-Cookie. Root wiederholte beide vollständigen Module auf dem integrierten Stand: `98 passed in 16.91s`, Exit 0, Log `/tmp/dishboard-root-branding-proof-login-gate-0906.log`. Keine Produktionscredentials in Fixtures oder Belegen. Der neue Live-Aufruf erreicht alle Seiten; seine gesonderten MIME-/Geometriebefunde werden geprüft und sind noch kein Branding-Browser-PASS.

Mitgeführt werden die separat geprüfte IAM-001-SDD `553d25e`/`4b95d7d` und die belegte pdfme-Designer-/Tabler-Lücke `87a361d`. Die SDD definiert einen engen UUID-/Namenskontext vor der Passwortpolicy und vollständige Schema-/Paket-/Fixture-Ownership; sie ist keine implementierte Benutzerverwaltung. Der offizielle pdfme-Designer erfüllt die verlangte vollständige Tabler-Bedienoberfläche nicht; TPL-002 bleibt offen.

## Verbleibende Abnahmegrenzen

Paket-/Manifest-Gate, tatsächlicher Folgedeploy und frische lesende Live-Abnahme dieser Lieferung sind abgeschlossen. Offen bleibt der getrennte Befund zur mobilen Patienten-HTML-Druckkartenhöhe; die allgemeine Branding-Prüfung mit ihren gesonderten MIME-/Geometriegrenzen wird nicht zu einem pauschalen PASS umgedeutet. Physische Yodeck- und fachliche Küchenabnahme bleiben eigenständig. OCR bleibt wegen belegter Providerfehler dieser Welle nicht verfügbar; kein CLEAN. Externer Design-Validator war mangels Gemini nicht ausführbar; seine frühere Dummy-GREEN-Ausgabe wird nicht als Abnahme verwendet.

IAM-A/B/C sowie Guard-/Ausfallkorrekturen sind inzwischen in einer getrennten Folgewelle integriert: Root prüfte 17 vollständige Module mit **284 bestanden, 59 Warnungen in 216.40 Sekunden**, `GATE_EXIT=0`. Mypy nach Testfix `374e9da` unabhängig bestanden: `Success: no issues found in 15 source files`; Schema-19-Migration und Baseline-Gleichheit auf echtem PostgreSQL ebenfalls bestätigt. Die gemeinsame Release-/Paketabnahme bleibt offen. **IAM ist in Abnahme, nicht deploybereit; Schema 19 ist nicht produktiv und nicht Teil von `0acd992`.** Der oben beschriebene SDD-Mittransport bleibt historischer Umfang dieses Releases. Alle 35 Backlog-IDs samt Teilfunktionen und Restumfang bleiben im [Backlog](../BACKLOG.md) erhalten; keine Gesamtfreigabe aus dem abgeschlossenen UI-003-Deploy.
