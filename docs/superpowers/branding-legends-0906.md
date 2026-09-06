# Markenpflege und durchgängige Legenden

Basis: `25c5984`, produktiver Anwendungscode `118a644`, Schema 17. Gesamtziel bleibt die vollständige Umsetzung aller 35 Backlog-IDs. Diese Welle schliesst fehlende Verbraucher von ICO-001/ICO-002 und baut BRD-001 aus; sie ersetzt weder den freien Vorlageneditor noch übrige Backlog-Aufträge.

## Verbindliche Architektur

- Bestehende Flask-/Jinja-/Tabler-Oberfläche, `food_symbols` und fpdf2 weiterverwenden. Keine zusätzlichen Bibliotheken und kein neuer universeller PDF-Renderer.
- Gemeinsame Legende nur aus tatsächlich dargestellten Menüoptionen; Allergene mit Präsenzstatus, Länder und Labels dedupliziert und stabil sortiert. Unbekannt bleibt unbekannt. Keine neuen medizinischen Angaben ableiten.
- Patienten-Signage bekommt eine Legende pro sichtbarer Seite; Wochen-PDFs eine Legende für den tatsächlich gedruckten Wocheninhalt. Vollständige lesbare Einseitigkeit, richtige A4-Orientierung und Patientenpreisfreiheit bleiben zwingend.
- Die Symbol-Lane besitzt gemeinsame Hilfsfunktionen und Web-/Admin-/Signage-Verbraucher, einschließlich aller Signage-Inhaltstemplates ausser `base_signage.html`. Die PDF-Lane besitzt ausschliesslich den PDF-Renderer und die beiden öffentlichen HTML-Druckvorlagen. Keine parallelen Änderungen an `week_pdf.py`.
- Branding verwendet validierte Revisionen in einem eigenen Settings-Namespace. Logo-Uploads werden tatsächlich mit vorhandener Pillow-Version dekodiert, normalisiert und grössenbegrenzt; keine SVG-, CSS-, JavaScript- oder fremden URL-Uploads.
- Für unveränderliche Logo-Assets wird Schema 18 reserviert: neue Tabelle mit Inhalts-Hash als Schlüssel und begrenzten normalisierten PNG-Daten, Dimensionen und Ersteller/Zeit. Keine Sequenz nötig. Damit sichert das bestehende Datenbankbackup Assets mit. Revisionen referenzieren Asset-IDs; aktive/benutzte Assets dürfen nicht ersatzlos gelöscht werden.
- Brand-Entwurf, aktive Revision und Wiederherstellung folgen dem bestehenden Vorlagenmuster: aktuelle Adminberechtigung, CSRF, Versionskonflikt und DB-Lock, keine GET-Schreibaktion, Fehler bewahren aktive Revision. Erlaubte lokale Schriften und validierte semantische Farben, kein beliebiges CSS.
- Öffentliche Branding-/Assetausgaben dürfen nur aktivierte beziehungsweise historisch aktivierte Assets freigeben. Entwurfsvorschau bleibt angemeldet und `no-store`; öffentliche Queryparameter schalten keinen Entwurf frei.
- Gleichoriginige, revisionierte CSS-/Assetantworten erhalten strenge CSP. Branding-Lesen darf den bestehenden begrenzten Ausfallpuffer nicht aushebeln. Laufende Signage benötigt eigenes Branding-Revisionssignal und kontrollierten Stylesheetwechsel, auch wenn Menüdaten unverändert sind.
- PDF-Branding wird nach den unabhängigen Symbol- und Branding-Basiscommits über einen expliziten Adapter angeschlossen. Dann besitzt die PDF-Lane auch die erforderliche Vorlagenkonfiguration/-UI: Markeneinstellung übernehmen versus ausdrücklicher Override. Alte Revisionen nicht umschreiben; Daten-/Vorlagen-/Brandrevision nachvollziehbar halten.

## Pakete und Reihenfolge

| Paket | Ausführung und exklusive Verantwortung | Abhängigkeiten / Abschluss |
|---|---|---|
| `wp-0d80830ddf5e` | Codex-Lane ps1_recovery: `food_symbols.py`, `_food_symbols.html`, `_menu_metadata.html`, `food-symbols.css`, die vier öffentlichen Webseiten, vier Signage-Seiten samt ihren Inhaltsblöcken, gezielte Admin-Metadatenverbraucher und passende Tests. Keine Rahmen-/Logo-/Branding-/PDF-Dateien. | Erst Sortierungsvertrag als kleiner Commit, dann Web, Signage und Admin als getrennte Verbraucher-Commits. Übergabe genau gerenderter Optionen. Vorhandene 14 Allergene und 249 Flaggen wiederverwenden. |
| `wp-ca238aab7f13` | Codex-Lane print_editor: `admin/week_pdf.py`, nötiger kleiner PDF-Symbol-/Legendenhelfer, zwei `public/print_*_week.html` und PDF-Tests. | Bestehende `FoodSymbol`/`FoodLegend`-Schnittstelle konsumieren, nicht verändern. Symbole, Ländertextfallback und vollständige gemessene Legende; Platzberechnung vor Zeichnung. Keine parallele Markenverdrahtung bis gemeinsamer Adapter festgelegt ist. |
| `wp-cee6d58fa08f` | Codex-Lane admin_equal_cards: Branding-Store/Assetservice, Migration `0015_v17_to_v18.sql`, Schema-/Berechtigungs-/Validierungsverträge, Tabler-Markenroute/-UI, App-/Blueprint-Registrierung, Rahmen/Logo-Partial, `signage.js` und Branding-Tests. | Kleine Commits: Schema/Store; Upload/Assetgrenze; Editor/Aktivierung; Admin-/Web-/Signage-Rahmen. Keine Änderungen an Signage-Inhaltstemplates oder PDF-Dateien dieser Welle. Erforderliche Logo-/PDF-Verbraucher sind im folgenden Integrationsschritt ausdrücklich zugeordnet, kein unverdrahtetes Gesamt-PASS. |

Nach den Basiscommits führt Root die unabhängigen Ergebnisse zusammen. Die Symbol-Lane verdrahtet anschliessend den gemeinsam vereinbarten Logo-Partial in ihren Signage-Inhaltstemplates. Die PDF-Lane bindet danach zentrale Marke und ausdrückliche Vorlagen-Overrides an. Diese notwendigen Verbraucher gehören zum Abschluss von BRD-001; vorher ist nur das jeweilige Teilpaket erledigt. Alte Vorlage- und Publikationsrevisionen bleiben unverändert.

Die deterministische WP-Erzeugung klassifizierte diese Integrationspakete unzutreffend als `single-file-fix`. Die tatsächlichen Mikroaufgaben, Verantwortlichkeiten und Schnittstellen stehen deshalb explizit hier; ausgeführt wird mit den vorhandenen Codex-Lanes. Es wird keine kostenlose Provider-Ausführung behauptet.

## Reservierungen und Gates

- Symbol-Lane: Pool `test-ps1`; PDF-Lane: `test-ps5`; Branding-Lane: `test-api-int`; Root: `test-api-int2`. Nur vorhandene jeweilige Gate-Wrapper und isolierte Namen `menuplan_(test|task)*` verwenden; Secrets niemals ausgeben.
- Jede Lane arbeitet nach frischem `git fetch github main` im eigenen Worktree. Keine Paketinstallation und kein Push/Merge durch Worker. Andere Änderungen erhalten.
- Vor Änderungen an vorhandenen Symbolen GitNexus Impact, vor Commit Detect; HIGH/CRITICAL an Root melden. Keine wiederholte Indexer-Reparaturschleife nach zwei gleichen Fehlern.
- Root liest Diffs und wiederholt passende Gates unabhängig: semantische Legendenfälle, PDF-Grenzen/Einseitigkeit, Admin-/Rollen-/Konflikt-/Uploadgrenzen, aktuelle Schrift-/CSP-/Equal-Card-Regressionsprüfungen und echte Browserbilder.
- OCR bleibt ein gesonderter Nachweis. Frühere 429/Timeouts sind kein CLEAN; ein nicht durchgeführter Review wird benannt. Keine stillen Providerwechsel.
- Integration, frisches Backup, Migration 17→18, Paket-/Manifestprüfung aus sauberem Git-Export, Deploy und neue Live-Belege durch Root. Nur diese Welle gilt nach ihren tatsächlichen Nachweisen als geliefert; Gesamtziel bleibt bis zur vollständigen Backlog-Abnahme aktiv.

## Zwischenstand der unabhängigen Integration

`65d3d75` integriert die Worker-Commits `0ad84ee` und `36d4230`: stabile Legendensortierung und Legenden auf den vier öffentlichen Webseiten. Root hat die Diffs gelesen und auf seinem Pool `test-api-int2` selbst geprüft: `46 passed in 26.46s`, `GATE_EXIT=0`; Ruff: `All checks passed!`; GitNexus staged: LOW, acht Dateien, zwei bekannte Symbole, keine erkannten Python-Aufrufketten. Die Jinja-Verbraucher wurden zusätzlich durch echte HTTP-/Browserprüfungen abgedeckt. Keine Produktivänderung durch diesen Zwischenstand.

OCR für genau diesen Worker-Stand scheiterte zweimal mit Exit 1: `Review failed: 0 finding(s); 8 of 8 selected item(s) failed.` und `Error: review failed: all 8 file review(s) failed — check your LLM configuration and API key`. Tatsächlich ausgewählter Provider: SambaNova, Modell `Meta-Llama-3.3-70B-Instruct`, jeweils null Tokens. **ESCALATE: OCR nicht verfügbar; kein CLEAN-Nachweis.** Rohbelege: `/tmp/dishboard-food-legends-web-ocr-first-0906.log` und `/tmp/dishboard-food-legends-web-ocr-0906.log`; unabhängiger Gate-Beleg: `/tmp/dishboard-brand-legends-web-gate-0906.log`.

UI-003 ist anhand der Originalbilder konkretisiert: [MiseOS-/Tabler-Übertragung](../design/2026-09-06-miseos-tabler-adaption.md). Dies ist Vorbereitung; laufende Verbraucher- und Branding-Arbeit bleibt vorrangig.
