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

## Weitere unabhängige Prüfungen und Review-Fixes

Die folgenden Integrationen sind lokal geprüft, noch nicht produktiv. Produktiv bleibt `118a644`, Checkout `25c5984`, Schema 17.

| Root-Commit | Umfang | Unabhängiger Root-Gate auf `test-api-int2` |
|---|---|---|
| `efa7222` | Vier Signage-Legenden und Seitenwechsel | `54 passed in 55.05s`, `GATE_EXIT=0` |
| `8ee1516` | PDF-Symbole, gemessene vollständige Legende und HTML-Druck | `97 passed in 58.48s`, `GATE_EXIT=0`; Ruff und Mypy bestanden |
| `b830415` | Markenrevisionen, normalisierte Logo-Assets, Schema 18 | `43 passed in 43.15s`, `GATE_EXIT=0`; Ruff/Mypy bestanden; statischer Validator: 33 Tabellen, Schema 18 |
| `17fd00c` | Admin-Legenden und leere HTML-Druckplätze | `49 passed in 76.79s`, `GATE_EXIT=0`; Ruff bestanden |
| `1cbc650` | Keine Deklaration für leere Menüplätze im gemeinsamen Partial | `62 passed in 41.70s`, `GATE_EXIT=0`; Ruff bestanden |
| `100f9da` | Vollständiger Schema-18-Vertrag im Paketvalidator | `16 passed in 24.01s`, `GATE_EXIT=0`; Ruff bestanden |

Diese Testmengen überschneiden sich; sie werden nicht als eindeutige Gesamtsumme addiert. Vollständige Suite und Paketprüfung folgen erst auf dem endgültigen Integrationsstand. Rohlogs: `/tmp/dishboard-root-{signage-legends,pdf-legends,branding-core,admin-print-legends,final-legends,schema18-package}-gate-0906.log`. Aktuelle Legendenbilder liegen unter `/tmp/dishboard-root-final-legends-0906`, PDF-Bilder unter `/tmp/dishboard-root-pdf-legends-0906`. Jeder weitere Testlauf verwendet einen eigenen Basetemp ausserhalb des gemeinsam bereinigten `/tmp/pytest-of-root`.

Die Worker-Commits `aed1b6d`, `c4d8950`, `c774ad9` und `8d5b9f2` sind im Root-Worktree zur gemeinsamen Prüfung vorgemerkt: lokales Favicon, Tabler-Markeneditor, revisionierter CSS-Wechsel und explizite PDF-Auswahl `active_brand`. Bestehendes `palette=brand` bezeichnet weiterhin die feste Südhang-Palette; gespeicherte Vorlagenrevisionen bleiben unverändert. GitNexus meldete für die gemeinsame Branding-Oberfläche CRITICAL und für den PDF-Renderer HIGH; beide Warnungen wurden vor weiterer Integration kommuniziert.

Unabhängige Reviews fanden zwei konkrete P2-/MEDIUM-Probleme. Ihre Korrekturen übernimmt jeweils ein anderer Agent als der ursprüngliche Autor:

| Paket | Verantwortung / Basis | Abnahme |
|---|---|---|
| `wp-61d33861b568` | print_editor, eigener WT `branding-cache-fix-0906`, Basis `c4d8950`; nur öffentlicher Branding-Cache und gezielte Regression | Revision und passendes Logo als ein atomar ersetztes Bundle veröffentlichen. Überlappende Anfragen und DB-Ausfall dürfen Marke und Logo nicht vermischen. Bestehende Freigabe- und Ausfallgrenzen erhalten. |
| `wp-472ddfbb5ce7` | ps1_recovery, eigener WT `branding-pdf-review-fix-0906`, Basis `8d5b9f2`; PDF-Logoausgabe, zugehöriger Hilfetext und gezielte PDF-/HTTP-Tests | `active_brand` ohne eigenes Logo zeigt das vorhandene Südhang-Standardlogo; ausdrücklich `none` bleibt ohne Logo. Initialzustand und Rücksetzen, beide Profile sowie Vorschau/Aktivierung/Download prüfen. Zusätzlicher separater Commit korrigiert die durch Root-Mypy gefundene Response-Annotation. |
| `wp-5dadb04847c8` | admin_equal_cards, eigener WT `branding-logo-wiring-0906`, Basis `100f9da` plus separate Basiscommits `aed1b6d` und `c4d8950` | Elf vorhandene Signage-/Public-/HTML-Druck-/Login-Templates konsumieren `brand_logo`; bestehende Legenden, Seitenwechsel, Maße und Ausfallzustände erhalten. Customlogo und Standardfallback mit echten Browserbildern prüfen. Keine Änderungen an PDF-Overrides, Cache, Store oder Schema. |

Logo-Wiring besitzt `signage/{cafeteria_day,cafeteria_week,patient_day,patient_week,cafeteria_closed,unavailable}.html`, `public/{legend,unavailable,print_cafeteria_week,print_patient_week}.html` und `auth/local_login.html`, gezielte Tests sowie nur bei tatsächlichem Layoutbedarf vorhandene CSS-Regeln. Damit bleibt kein notwendiger Verbraucher zwischen den Paketen unzugeordnet.

Root-Mypy auf zwölf gemeinsam integrierten Modulen scheiterte zweimal identisch mit Exit 1:

```text
cafeteria/admin/print_template_routes.py:137: error: Incompatible return value type (got "werkzeug.wrappers.response.Response", expected "flask.wrappers.Response")  [return-value]
Found 1 error in 1 file (checked 12 source files)
```

**ESCALATE: Typprüfung noch nicht bestanden; Korrektur ist dem separaten PDF-Fix zugeordnet.** Root-Ruff und `node --check` für diesen gemeinsamen Zwischenstand bestanden. Bandit mit `/usr/bin/python3.13 -m bandit` prüfte sieben Branding-Module: Exit 0, 610 LOC, keine Befunde, keine Analysefehler, keine übersprungenen Tests; JSON `/tmp/dishboard-root-branding-bandit-0906.json`.

Nachtrag: Der gemeinsame unveränderte UI-/Signage-/PDF-Zwischenstand bestand `212 passed in 170.23s (0:02:50)`, `GATE_EXIT=0`; Log `/tmp/dishboard-root-branding-combined-gate-0906.log`. Root prüfte das mobile Editorbild und die echte Cafeteria-PDF-Ausgabe visuell. Danach wurden `eeda473` (Standardlogo und Hilfetext) sowie `e2a3b90` (Response-Import entsprechend Repo-Konvention) gelesen und vorgemerkt. Ihr unabhängiger Root-Gate bestand `75 passed in 32.25s`, `GATE_EXIT=0`, Log `/tmp/dishboard-root-brand-pdf-fix-gate-0906.log`; Ruff bestand. Derselbe Mypy-Aufruf über zwölf Module meldet nun `Success: no issues found in 12 source files`. Der oben dokumentierte Typfehler ist damit behoben; Cache-Fix und Logo-Wiring bleiben bis zu ihren eigenen Nachweisen offen.

Auch Cache-Fix `2d50acb` wurde durch Root gelesen und unabhängig geprüft: `24 passed in 28.40s`, `GATE_EXIT=0`, Log `/tmp/dishboard-root-brand-cache-fix-gate-0906.log`; Ruff und Mypy bestanden. Das unveränderliche Bundle bewahrt zusammengehörige Revision, Tokens und Logo bei überlappenden Anfragen und im begrenzten Ausfallfallback. GitNexus meldete HIGH für die zusammenhängenden Ausgabepfade; Warnung kommuniziert. Die zwei ursprünglichen Review-Befunde sind damit korrigiert. Weiter offen: abschliessendes Logo-Wiring, vollständiger Release-Gate, Paket/Manifest und tatsächlicher Deploy.

Reviewberichte: `wp-87f84a0db539.md` (Store/HTTP, Register 11986) und `wp-7a5475ab6b94.md` (PDF, Register 11987) unter `/nvmetank1/projects/rag-stack/.claude/reports`. OCR bleibt wegen tatsächlich beobachteter SambaNova-HTTP429 dieser Welle nicht verfügbar; Provider wurde erst danach als ausgefallen markiert. Keine weitere Anfrage an denselben erschöpften Provider, kein Ersatzprovider und kein CLEAN-Nachweis.
