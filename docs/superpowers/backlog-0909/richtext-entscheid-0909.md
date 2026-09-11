# Richtext für Rezeptschritte: Entscheidungsgrundlage

| Feld | Wert |
|---|---|
| MP-ID | `MP-REC-RICHTEXT-DECISION` |
| Routing-WP | `wp-555394ec312f` |
| Lane / verwendetes Modell | Codex / `gpt-6-astra` |
| Datum | 11. September 2026 |
| Basis-Commit | `4ca6df79827477d5682ccae9d76345adf3c3a4f7` |
| Worktree | `/nvmetank1/projects/menuplan/.claude/worktrees/docs-rec-decisions-codex-0911` |
| Branch | `docs/rec-decisions-0911` |
| Status | Empfehlung; Entscheid beim Auftraggeber, keine Technologiefreigabe |

**Empfehlung:** Option A, Klartext, als bestehende Liefergrenze behalten. Falls
Formatierung fachlich benötigt wird, zuerst Option B gegen Option C entscheiden.
HugeRTE 1.0.13 ist unter unveränderter CSP und mit Silver kein abnahmefähiger
Drop-in. Dieser Auftrag installiert keine Dependency und ändert kein
Produktverhalten. Das entspricht [recipes-wps.json:1846–1852](recipes-wps.json#L1846)
und [recipes-sdd.md:761–766](recipes-sdd.md#L761).

## Ausgangsvertrag und Belegstand

`recipe_values.recipe_text` bezeichnet die **Python-Validierungsfunktion**, keine
SQL-Spalte. Sie normalisiert NFC und bei mehrzeiligem Text CRLF/CR zu LF, verwirft
`<`, `>` sowie Unicode-Kategorien `C*` mit Ausnahme des erlaubten LF und prüft die
Länge nach Normalisierung/Trimmen. Jeder Schritt erlaubt höchstens **8000 Zeichen**,
nicht 8000 UTF-8-Bytes. SQL speichert `recipe_steps.instruction` und sichert die
Grenze zusätzlich mit `recipe_text_v22(instruction,8000)`. HTML aus einem Editor
würde heute abgewiesen, nicht serverseitig in sicheren Richtext verwandelt.
Belege: [recipe_values.py:32–45,161–164](../../../reference_scaffold/cafeteria/recipe_values.py#L32),
[schema.sql:4135–4147,4201–4208](../../../database/schema.sql#L4135).

Der frühere Bericht
[wp-hugerte-backlog-0906.md:15–17](/nvmetank1/projects/rag-stack/.claude/reports/wp-hugerte-backlog-0906.md#L15)
belegt MIT, wählt aber keine Version. Die spätere lokale Browserprobe
[wp-28dc5618ccd1.md:9–45](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L9)
bezieht sich ausdrücklich auf **1.0.13**, Chrome 152.0.7977.82 und 1440×900.
Die folgenden Browserbefunde sind daraus übernommen, keine neue Browserprüfung.
Die [MIT-Lizenz am Tag v1.0.13](https://raw.githubusercontent.com/hugerte/hugerte/v1.0.13/LICENSE.TXT)
wurde für dieses Dokument zusätzlich als Primärquelle abgerufen; Lizenz- und
Copyright-Hinweise müssen erhalten bleiben.

## Konkrete CSP-Verletzung und Wege ohne `unsafe-inline`

Die aktuelle HTTP-CSP enthält `style-src 'self'`, ohne eigene
`style-src-attr`-Erlaubnis:
[__init__.py:63–68](../../../reference_scaffold/cafeteria/__init__.py#L63).
Die Vorprobe meldet `effectiveDirective=style-src-attr`, `blockedURI=inline`,
`hugerte.js:1284`. Ursache ist ein intern gebauter Scroll-/Caret-Marker:
`createMarker$1` erzeugt einen temporären `span` mit dem Style-Attribut
`display: inline-block;` (Release-Bundle Zeilen 10607–10612). Das ist ein
Inline-Style-Attribut, kein externes Stylesheet und kein Nutzer-HTML. Dieselbe
Verletzung trat mit `inline:true`, `theme:false`, `skin:false` und externen
Tabler-Buttons auf. Beleg:
[Vorprobe:34–45](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L34).

| Weg | Aussage und Grenze |
|---|---|
| Enger Attribut-Hash | CSP3 erlaubt Style-Attribut-Hashes mit `'unsafe-hashes'`. Für genau den belegten Marker wäre eine ausdrückliche `style-src-attr`-Direktive mit diesem Schlüsselwort und dem unten angegebenen Hash möglich. Das löst diesen Treffer nach CSP-Regeln ohne `unsafe-inline`, ändert aber die Policy und ist kein Browser-PASS für den ganzen Editor. [CSP3 §6.7.3.3](https://www.w3.org/TR/CSP3/#match-element-to-source-list) |
| Nonce oder einfacher Style-Hash | Nonces gelten für `style`-Elemente, nicht für Style-Attribute. Ein blosser Hash ohne `'unsafe-hashes'` behebt diesen Marker ebenfalls nicht. Keine belegte HugeRTE-Konfigurationsoption in der Vorprobe entfernt ihn. [CSP3 §6.7.3.3](https://www.w3.org/TR/CSP3/#match-element-to-source-list), [Vorprobe:53–57](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L53) |
| Externe Content-CSS / Skin-CSS | `content_css` und `skin_url` vermeiden entsprechende eingebettete Stylesheets, beseitigen den internen Marker aber nicht. Nicht mit `content_style` oder einer Iframe-Meta-CSP als pauschalem Fix verwechseln. [Vorprobe:53–56](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L53) |
| Geprüfte Upstream-/Quellanpassung | Vorschlag bei zwingend unveränderter CSP: Marker mit Klasse und lokaler CSS-Regel erzeugen; Caret, Scrollen und Serialisierung erneut prüfen. Dies ist eine noch nicht implementierte Änderung, keine vorhandene Option und keine Freigabe zum Editieren minifizierter Vendor-Dateien. [Vorprobe:45,69–73](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L45), [Designsystem:219](../../design/2026-09-09-unified-ui-design-system.md#L219) |

Illustration des ersten Wegs, **nicht angewendet**:

```text
style-src 'self'; style-src-attr 'unsafe-hashes' 'sha256-BSTKIYoPCaklkJ9YS/ZVYuKW8e+DG8jZJCXznBzHjgg=';
```

Der Hash wurde lokal aus den exakten UTF-8-Bytes `display: inline-block;`
nachgerechnet und stimmt mit [Vorprobe:45](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L45)
überein. Eine solche Erlaubnis ist nicht auf diesen einen `span` beschränkt:
gleiche Attributbytes würden im Geltungsbereich ebenfalls passen. Deshalb braucht
auch diese begrenzte Policy-Änderung einen separaten Entscheid. Unter gleichzeitig
**unverändertem Release, unveränderter CSP und null CSP-Verletzungen** bleibt
1.0.13 für diesen Vertrag ungeeignet. Das sagt nicht, dass CSP grundsätzlich
Richtext verbietet. [CSP3 §6.7.3.3](https://www.w3.org/TR/CSP3/#match-element-to-source-list),
[Vorprobe:71](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L71).

## Tabler-Konformität nach Komponenten

Massstab ist das gemeinsame Designsystem vom 9. September. Die historische
Vorprobe verwendete 48px als Gate; der aktuelle allgemeine Projektstandard ist
44px. Die gemessenen Silver-Controls unterschreiten beide. Weder CSS-Skin noch
Tabler-Aussenrahmen belegen konforme innere Controls.
[Designsystem:197,243–254,290](../../design/2026-09-09-unified-ui-design-system.md#L197),
[Vorprobe:26,34–36](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L26).

| Bestandteil | Belegter Iststand | Erforderlicher Anschluss / Bewertung |
|---|---|---|
| Toolbar-Buttons | Silver `.tox-tbtn` 34×28px; externe `.btn` in der Probe 48px hoch. [Vorprobe:34–36](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L34) | Silver fällt beim Mass durch. Externe echte Tabler-Buttons sind ein belegter Teilweg; aktive/gedrückte Zustände, Selection und Undo bleiben Integrationsarbeit. |
| Dialoge / Felder | Silver `.tox-dialog`, `.tox-textfield` 448×36px, Buttons 34px hoch. Externe Probe ohne eigenen Linkdialog. [Vorprobe:34–36,57](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L34) | Echte Projekt-Modals und Formularfelder samt Labels, Fehlern, Escape und Fokus-Rückgabe erforderlich. Ein HTML-Panel im Silver-Dialog ersetzt dessen Rahmen nicht. |
| Fokus-Ring | Vorprobe berichtet sichtbaren Fokus und funktionierende Tastaturaktionen, keine Messung des heutigen Fokus-Tokens. [Vorprobe:58](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L58) | Mindestens 2px Burgunder-Outline mit Abstand auf heller Fläche; vollständige Fokusreihenfolge und Rückkehr prüfen. Konformität nicht belegt. [Designsystem:292](../../design/2026-09-09-unified-ui-design-system.md#L292) |
| Schrift | Keine Messung der aktuellen Sollschrift für Silver und Editorinhalt in der Vorprobe. | Controls/Inhalt an `Arial, Helvetica, sans-serif` und 1rem/1.5 anschliessen; H1/Card-Titel verwenden die vorgegebene Serifenschrift. Content-CSS eines Iframes separat berücksichtigen. [Designsystem:180–205](../../design/2026-09-09-unified-ui-design-system.md#L180), [Vorprobe:53](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L53) |
| Farben / Zustände | Kein Messbeleg für vollständige heutige Tokenzuordnung oder Kontraste der Silver-Komponenten. | Projektvariablen an tatsächliche Komponenten anbinden; Normal/Hover/Active/Focus/Disabled/Invalid und Kontrast messen. Keine freie Schrift-/Farbpalette für Rezeptautoren vorgeschlagen. [Designsystem:215–221,288](../../design/2026-09-09-unified-ui-design-system.md#L215) |

## Daten, Snapshotbytes und PDF

1. **Validierung:** Für HTML wären Python- und SQL-Vertrag gemeinsam zu ändern.
   Vorschlag für einen Folgeauftrag: nur Absätze, Fett/Kursiv und Listen;
   serverseitige Normalisierung mit begrenzter Element-/Attributliste, keine
   Styles, Eventhandler oder eingebetteten Medien. Links zunächst weglassen;
   spätere Links brauchen eigene URL-Prüfung. Der bisherige Klartextvalidator
   ist kein HTML-Sanitizer. Clientfilter oder CSP ersetzen diese Grenze nicht.
   Ausgangsbelege: [recipe_values.py:32–45,161–164](../../../reference_scaffold/cafeteria/recipe_values.py#L32),
   [schema.sql:4204,4348](../../../database/schema.sql#L4204).
2. **Revisionen:** Der Snapshot enthält Schritte mit `instruction` und
   `schema_version=1`. Der SHA-256 bezieht sich auf
   `convert_to(snapshot_json::text,'UTF8')`, nicht auf Browser-HTML oder PDF-Bytes.
   Unterschiedliche Markup-/Entity-/Whitespace-Serialisierung kann somit trotz
   gleicher Darstellung andere Hashes ergeben. Vorschlag: neues explizites
   Format samt Format-/Sanitizer-Version vor dem Freeze definieren; bestehende
   Snapshots und Hashes unverändert lassen. Keine nachträgliche Interpretation
   alter `*`-Zeichen als Formatierung. Belege:
   [schema.sql:4230–4235,4275–4276,4289–4290,4325–4329](../../../database/schema.sql#L4230).
3. **PDF:** Route → `recipe_print_input` → `render_recipe_pdf`. Reader und
   Renderer prüfen erneut `recipe_payload`; der Renderer akzeptiert hier
   Snapshotversion 1 und druckt die ursprünglichen eingefrorenen Werte.
   `pdf.paragraph(step['instruction'])` führt über FPDF `multi_cell`, nicht über
   einen HTML-Renderer. HTML würde bereits an der Validierung scheitern; nur
   diese zu lockern ergäbe noch keinen formatierten Druck. Vorschlag: erlaubte
   Struktur deterministisch auf Textläufe und Listen abbilden, Umbruch und
   Schriftabdeckung prüfen; keinen pauschalen HTML-/`safe`-Pfad hinzufügen.
   Der HTTP-Header `X-Recipe-Content-SHA256` bezeichnet den Revisionsinhalt,
   nicht den Hash der PDF-Datei. Belege:
   [recipe_reads.py:144–166](../../../reference_scaffold/cafeteria/recipe_reads.py#L144),
   [recipe_pdf.py:50–62,113–118,202–208](../../../reference_scaffold/cafeteria/admin/recipe_pdf.py#L50),
   [recipe_revision_routes.py:100–117](../../../reference_scaffold/cafeteria/admin/recipe_revision_routes.py#L100).

## Optionen A/B/C und Aufwand

Schätzungen des Autors für einen begrenzten Folgeauftrag, ein Personentag =
acht Arbeitsstunden; keine Laufzeitmessungen oder zugesagten Termine. Aufwand
umfasst Anschluss und fokussierte Prüfungen, ohne Wartezeit auf Fachfreigaben.
Grundlage sind die oben belegten Grenzen und
[recipes-sdd.md:761–766](recipes-sdd.md#L761).

| Option | Bibliothek / Lizenz / Version | Umfang und Schätzung | Abwägung |
|---|---|---|---|
| **A – Klartext behalten (empfohlen für jetzt)** | Keine neue Bibliothek; separate Lizenz/Version entfällt. | **0 PT Produktänderung**, optional **0,5–1 PT** für einen gesonderten bestehenden Editor-/Druck-Abnahmeauftrag. | Bewahrt Text-, Snapshot- und Druckvertrag; keine formatierte Prosa. |
| **B – Markdown-Teilmenge im Klartext** | Keine Editorbibliothek vorgesehen; externe Lizenz/Version entfällt. Eigene Teilmengen-Version erst zu spezifizieren, keine CommonMark-Kompatibilität behauptet. | **4–6 PT**: vorhandene Textarea/Tabler-Buttons, kleine klar begrenzte Syntax, Formatkennung, Serverprüfung, deterministische Browser-/PDF-Darstellung und Tests. | Roh-HTML bleibt verboten. Gespeicherte Syntax zählt zum 8000-Zeichen-Limit. Bis zu einem ausdrücklichen neuen Rendervertrag bleiben Markdownzeichen wörtlicher Klartext; bestehende Revisionen nicht umdeuten. |
| **C – HugeRTE mit echten Tabler-Controls** | HugeRTE **1.0.13**, **MIT**, [getaggte Lizenz](https://raw.githubusercontent.com/hugerte/hugerte/v1.0.13/LICENSE.TXT). Noch kein ausgewählter serverseitiger HTML-Sanitizer; dessen Bibliothek/Lizenz/Version **nicht belegt**. | **10–15 PT**: zuerst **2–3 PT** begrenzte CSP-/Tabler-Probe, danach **8–12 PT** für Sanitizervertrag, Adapter, Revisionen, PDF und Browserprüfungen; ohne Zusage für unvorhersehbare Upstreamkorrekturen. | Grössere Bedienfunktion, aber höchste Integrations- und Wartungslast. Keine Freigabe allein durch funktionierende Fett-/Listenprobe. |

Der Auftraggeber entscheidet A/B/C sowie bei C getrennt über den CSP-Weg und
einen konkret belegten Sanitizer. Ein Folgeauftrag muss Save/Reload, Paste,
8000-Zeichen-Grenze, historische Hashes, PDF-Bytes/Umbruch, Tastatur/Touch und
null CSP-Verletzungen prüfen. Das Dokument erteilt weder diesen Folgeauftrag
noch eine Dependency- oder Technologiefreigabe.
[Ausführungsvertrag:22–26,66–76](execution-contract.md#L22),
[Vorprobe:69–73](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md#L69).

## Nicht geprüft

- Keine neue Browser-, Samsung-, Screenreader-, CSP-Hash- oder Caret-Langtextprobe;
  historische Browserbelege oben sind ausdrücklich fremde Vorbefunde.
- Keine Dependency installiert, kein HTML-Sanitizer ausgewählt oder geprüft;
  keine Datenbank-, Produktcode-, Snapshot- oder PDF-Änderung.
- Keine pytest-/Ruff-/Mypy-/vollständige Paket-/Liveprüfung: reiner Dokumentauftrag
  gemäss [recipes-wps.json:1846–1852](recipes-wps.json#L1846).
- Der ergänzend angefragte getaggte `CaretContainerInline.ts`-Abruf scheiterte
  zweimal mit `Internal Error` / `Cache miss`. Er ist kein Quellenbeleg; der
  konkrete Markerbefund stammt aus dem oben zitierten Vorbericht.
- `context-mode/ctx_fetch_and_index` war bei Erstaufruf und identischem Retry
  mit `Transport closed` unverfügbar. Erfolgreiche Primärquellenabrufe erfolgten
  über Webzugriff. Git-/Link-/Review-Ergebnisse stehen im separaten WP-Bericht.
