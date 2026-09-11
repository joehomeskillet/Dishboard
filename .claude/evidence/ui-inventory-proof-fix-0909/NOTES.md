# Private Notiz — wp-d7589450daee (Beweiskorrektur und Freeze UI-Inventar)

Worktree `ui-inventory-proof-fix-0909`, Branch `fix/ui-inventory-proof-0909` (Doku-Nachtrag ueber `docs/ui-inv-evidence-agy-0911`).
Basis `33d135f861d1fff78deac9f372a051375d410532`.
Originalautor der Aufnahmestrecke ist Grok; die Beweiskorrektur und der anschliessende
Freeze schliessen saemtliche von Root unabhaengig geprueften Beweis- und Abdeckungsluecken.
Kein Produktcode, keine fremden Pools, keine Unterdelegation, kein Push und kein Merge.

## Was tatsaechlich geaendert wurde

| Datei | Rolle |
|---|---|
| `.claude/evidence/ui-inventory-grok-0909/capture.py` | Recorder: Listener-Lebensdauer, `await_ready` mit Lazy-Sweep, Plattformschriften via CDP `CSS.getPlatformFontsForNode`, `Outputs.into`, gemessener Publish-Dialog, Provenienz/Metadaten, Fixture-Hash, strikte Validierung in `_prepared_additions` (598 Zeilen) |
| `.claude/evidence/ui-inventory-grok-0909/build_matrix.py` | Matrix-Builder: `write_matrix(target)` + `--out`, Provenienz/Metadaten, `SHARED_STATES` mit Fixtures/Captures inkl. `role_navigation`, HTML-Fragmente, echte Rollenpruefung via Wrapper-Walk (10 Admin-Routen korrigiert), `METHOD_RESTRICTIONS` mit `method_roles`, `capability_semantics` |
| `reference_scaffold/tests/test_ui_route_inventory.py` | Fixture- und Konsistenzpruefung: Echte PostgreSQL-Store-Helfer fuer alle 17 fehlenden visuellen Admin-Endpunkte (21 Pfade total mit HTTP 200), drei Browseraktionen fuer 400-Validierungsfehler, `_visual_gaps` via `url_map.match`, Assertions fuer States, Rollen-Navigation und Metadaten, Unveraendertheitspruefung |
| `reference_scaffold/tests/test_ui_inventory_capture.py` | Recorder-Tests: 24 Tests gegen Chromium-Browser (Listener-Lebensdauer, Bildbereitschaft, Modal-Status, Ausgabenumleitung, Rollennavigation, Vorbereitungsergebnisse) |
| `.claude/evidence/ui-inventory-proof-fix-0909/` | Evidenzordner: Regressionsbeweis (`regression-proof.py`), Rohe Gate-Logs (`gates-0911/`), Review (`reviews/`), Mockup-Einordnung (`design-reference-0911.md`), promotetes Manifest und Screenshots (`capture-promoted-0911/`), Abdeckungsmatrix (`coverage-status.md`), diese Notiz |
| `docs/superpowers/backlog-0909/ui-before-manifest.json` | Versioniertes Manifest: Promoteter Freeze-Stand (172 Aufnahmen, alle 60 visuellen Routen abgedeckt, superseded_evidence mit 111 ersetzten Vorlaeufer-Zeilen) |
| `docs/superpowers/backlog-0909/ui-route-matrix.json` | Versionierte Matrix: Re-generierter Stand (116 Routen, 75 Templates, 6 Shared States, 10 korrigierte Admin-Routen, 1 method_roles-Restriktion, capability_semantics) |

Nicht angefasst: die 111 Original-PNG unter `.claude/evidence/ui-inventory-grok-0909/screenshots/`,
`endpoint_templates.json`, `visual-inspection.md` und jede Produktdatei
unter `reference_scaffold/cafeteria/`.

## Warum die Korrektur so aussieht

**Listener.** Der urspruengliche `shot()` hat `console` und `pageerror` im
`finally` direkt nach `page.goto(..., wait_until='domcontentloaded')` abgehaengt
und danach 250 ms gewartet. Jeder Fehler in diesem Fenster fiel unter den Tisch —
und genau dort passieren die interessanten Fehler. Die Listener bleiben jetzt bis
nach Screenshot und Messung attachiert. `regression-proof.py` zeigt beide
Recorder nebeneinander auf derselben Seite: Original leer, korrigiert mit beiden
Meldungen.

**Bereitschaft.** `page.wait_for_timeout(250)` ist keine Bereitschaft, sondern
eine Hoffnung. `await_ready` wartet auf `load`, macht einen begrenzten
Scroll-Durchlauf, damit `loading="lazy"`-Bilder ueberhaupt angefordert werden,
und wartet dann auf `document.fonts.status === 'loaded'` und `img.complete` fuer
alle Bilder. Ohne den Scroll-Durchlauf laufen `/cafeteria/wochenangebot/` und
`/patienten/wochenplan/` in einen echten Timeout — der urspruengliche Recorder
hat fuer diese Seiten fotografiert, bevor die Bilder da waren, und das Ergebnis
trotzdem als gerendert gefuehrt.

**Schriften.** Die deklarierte CSS-Familie beweist nichts ueber das, was der
Browser tatsaechlich rastert. `rendered_fonts` liest zusaetzlich
`CSS.getPlatformFontsForNode` ueber CDP und schreibt `platform` plus
`platform_source` ins Manifest; faellt CDP aus, steht das ausdruecklich als
`platform_source: 'unavailable'` drin statt als stille Luecke.

**Publish-Dialog.** Vorher war die Zeile hartkodiert: Status 200, kein Overflow,
keine Fehler — unabhaengig davon, ob der Dialog je aufging. Jetzt oeffnet
`open_modal` den Dialog wirklich, wartet auf sichtbar und `.show`, und wenn der
Ausloeser fehlt oder deaktiviert ist, entsteht ein `blocked_modal_not_open`-Eintrag
statt einer erfundenen Erfolgszeile. Ein blockierter Beweis ist mehr wert als ein
falscher.

**Ausgabepfade.** Ein gewoehnlicher Testlauf darf keine versionierten Belege
ueberschreiben. `Outputs` trennt Standardziel und Laufziel; der Regressionslauf
schreibt nach `tmp_path` und prueft anschliessend Matrix, Manifest und alle
Original-PNG byteweise. Nur ein ausdrueckliches `UI_CAPTURE_PROMOTE=1` erzeugt die
Promotion in die versionierten Dateien — und auch das ueberschreibt die Baseline
nicht unkontrolliert.

**Fixture statt Ausrede.** Die Begruendung, Revisionsdetail, Kopier-Erfolg und
weitere Admin-Oberflaechen seien mangels Fixture nicht belegbar, hielt nicht:
Synthetische PostgreSQL-Store-Helfer erzeugen gepruefte Wochen, echte v1-Revisionen,
Kochbuecher, Grundlagen-Tags, lokale Benutzer und Screen-Zuweisungen. Saemtliche
17 zuvor unbelegten visuellen Admin-Endpunkte rendern mit Status 200 im echten
Chromium-Browser.

## Freeze 2026-09-11

Der UI-Inventar-Freeze buendelt fuenf fokussierte Sub-Workpackages verschiedener
Lanes und Modelle zu einem konsistenten, vollstaendig geprueften Evidenzstand.

### Beteiligte Workpackages

1. **`wp-d7589450daee-agy-capture`** (Lane `antigravity-agy`, Modell `gemini-3.6-flash-high`, Commit `944b5d2`):
   Erweiterte den Recorder in `capture.py` um kanonische JSON-Serialisierung,
   Berechnung des Fixture-Hashs, Scannen lokaler Schriftarten, Erfassung der
   Laufzeitmetadaten (Browser, Playwright, Python, OS), Sidebar-Navigation je Rolle
   (`nav_items`), Zustandscaptures und `role_cookies`. Schrieb 7 neue Tests in
   `reference_scaffold/tests/test_ui_inventory_capture.py`.
2. **`wp-d7589450daee-grok-matrix`** (Lane `grok-build`, Modell `grok-4.6`, Commit `5f9b946`):
   Erweiterte `build_matrix.py` um `SHARED_STATES` mit Fixture- und Capture-Selektoren
   (inkl. `role_navigation`), HTML-Fragmente (`admin.header_get`, `admin.service_get`),
   Provenienzdaten in `meta` und leitete 10 echte Admin-Rollen durch statische Analyse
   von Wrapper- und Closure-Hierarchien (`users.manage`, `settings.write`) korrekt ab.
3. **`wp-d7589450daee-agy-matrix-fix`** (Lane `antigravity-agy`, Modell `gemini-3.8-flash-high`, Commit `57267b0`):
   Loeste die Befunde des Cross-Vendor-Reviews (`grok-matrix-cross-review-agy.md`):
   Ergaenzte `common.capability_semantics` zur Erklaerung von `capability: null` bei
   15 methodenabhaengig geschuetzten Routen und fuehrte `METHOD_RESTRICTIONS` sowie
   `method_roles` ein, um zu dokumentieren, dass POST auf `admin.screen_template_assignment`
   `settings.write` verlangt und Editor/Publisher mit 403 abweist.
4. **`wp-d7589450daee-grok-capture-fix`** (Lane `grok-build`, Modell `grok-4.6`, Commit `3006c1d`):
   Kompaktierte `capture.py` auf 598 Zeilen (unter das 600-Zeilen-Limit), implementierte
   strikte Typpruefung und lautes Scheitern via `_prepared_additions` bei fehlerhaften
   Fixture-Rueckgaben und validierte `supersedes` als JSON vor Serverstart; fuegte 6
   neue Capture-Tests hinzu (Gesamtstand 24 Tests).
5. **`wp-d7589450daee-codex-fixtures`** (Lane `codex-gpt5`, Modell `gpt-6-astra`, Commit `0754a00`):
   Implementierte in `test_ui_route_inventory.py` (564 Zeilen) den vollstaendigen
   PostgreSQL-Fixture-Store fuer alle 17 fehlenden visuellen Endpunkte (21 Pfade total mit
   HTTP 200), Browseraktionen fuer drei echte Validierungsfehler (HTTP 400),
   URL-Map-basierte Lueckenberechnung (`_visual_gaps`), Pruefung aller Zustaende und
   der Rollennavigation sowie explizite Promotionsabsicherung.

### Orchestrator-Korrekturen aus der Git-Historie

Der Orchestrator (Claude Code, `claude-fable-5-1` / Opus 5) koordinierte die
Zusammenfuehrung und fuehrte folgende Korrekturen durch:
- **`91f1fca`**: Korrigierte zwei fehlerhafte Endpunktreferenzen in den Matrix-Zustaenden
  (`auth.error` war ein Template statt Endpunkt; `admin.components_list` wurde auf den
  registrierten Namen `admin.components_get` korrigiert).
- **`a773282`**: Archivierte die Zielbild-Referenz (`design-reference-0911.md`) und das
  Cross-Vendor-Review des Grok-Matrix-Workers (`reviews/grok-matrix-cross-review-agy.md`).
- **`089f7d1`**: Re-generierte die versionierte Matrix mit dem integrierten `build_matrix.py`
  (116 Routen, 75 Templates, 6 Shared States, 10 korrigierte Rollen, `method_roles`,
  `capability_semantics`) und passte `prepare_entities` an die strikte Schnittstelle an.
- **`7f6a5c7`**: Aktualisierte die Mypy-Fehlercode-Konfiguration (`assignment`, `return-value`)
  fuer das installierte Mypy-Binary mit `MYPYPATH=reference_scaffold`.
- **`0e6a292`**: Fuehrte die finale Promotion des korrigierten Before-Manifests (172 Captures)
  und der Screenshots nach `docs/superpowers/backlog-0909/ui-before-manifest.json` und
  `.claude/evidence/ui-inventory-proof-fix-0909/capture-promoted-0911/` durch.
- **`33d135f`**: Archivierte die sechs rohen Gate- und Promotion-Logs unter `gates-0911/`.

### Warum die erste Promotion verworfen wurde

Im ersten Promotionslauf (`02-promotion-first-attempt-superseded-duplicate-menu-row.log`)
war `admin.menu_get` sowohl im Standard-Recorderlauf (alle fuenf Viewports) als auch
in `extra_admin_paths` aufgefuehrt. Dadurch wurde dieselbe Screenshot-Datei
ueberschrieben und im Manifest entstand eine doppelte Zeile fuer den Menue-Editor.
Der Fehler wurde in `reference_scaffold/tests/test_ui_route_inventory.py:305` behoben:
`'extra_admin_paths': [path for key, path in paths.items() if key != 'admin.menu_get']`.
Der erste Promotionslauf und der nachfolgende Gate-Lauf (`03-gate-run-after-first-promotion-superseded.log`)
wurden als `superseded` verworfen und im Belegordner archiviert.

### Reihenfolge: Promotion und zwei Gate-Laeufe

Nach Behebung der Doppelzeile erfolgte die Verifikation in drei sequenziellen Schritten:
1. **Finaler Promotionslauf** (`04-promotion-final.log`):
   Ausgefuehrt mit `UI_CAPTURE_PROMOTE=1` gegen den isolierten PostgreSQL-Testpool.
   Ergebnis: `1 passed, 9 deselected in 76.70s`, `GATE_EXIT=0`.
   Schrieb 172 Aufnahmen ins Manifest und 172 PNG-Dateien.
2. **Erster vollstaendiger Gate-Lauf** (`05-gate-run-1-final.log`):
   Vollstaendiger Lauf ueber alle 34 Tests in `test_ui_route_inventory.py`.
   Ergebnis: `34 passed in 113.84s`, `GATE_EXIT=0`.
3. **Zweiter vollstaendiger Gate-Lauf** (`06-gate-run-2-final.log`):
   Identischer Wiederholungslauf zur Pruefung von Idempotenz und Stabilitaet.
   Ergebnis: `34 passed in 112.49s`, `GATE_EXIT=0`.

## Hashes

Saemtliche Hashes deterministisch per SHA-256 berechnet (Stand Freeze-Commit `33d135f`):

| Datei / Artefakt | SHA-256 |
|---|---|
| `.claude/evidence/ui-inventory-grok-0909/capture.py` | `36e85d88b5b3d6631675c8b5c4383f6b8afc5db1e2d34c124a25fc4c32ca5b0f` |
| `.claude/evidence/ui-inventory-grok-0909/build_matrix.py` | `42124fc783750e9689b8b741511193f9f2c57694c4b425451121feb7c8489eeb` |
| `reference_scaffold/tests/test_ui_route_inventory.py` | `a5032cb258bb1ec2fd59c0ef909935f243279d5967decb75edbcfc8e426cb20d` |
| `reference_scaffold/tests/test_ui_inventory_capture.py` | `ffabce53d62d4c9786d4603a02facd7ba4c1545838777b97be392ddecdc21818` |
| `.claude/evidence/ui-inventory-proof-fix-0909/regression-proof.py` | `441aadc7a32962ef9e54b898972a2c62f7dc3baa2e8696f2cca5b789f7a2ecba` |
| `docs/superpowers/backlog-0909/ui-route-matrix.json` (versioniert) | `62dc038032d22d06834ecd601c623ce14431be1b6932be46b6c8c60188de2e18` |
| `docs/superpowers/backlog-0909/ui-before-manifest.json` (versioniert, promotet) | `ee42bd86e5642835aeeb78f04129e39daab888f182e8664ea0a6a4500a0c16c2` |
| `.claude/evidence/ui-inventory-proof-fix-0909/capture-promoted-0911/ui-before-manifest.json` | `ee42bd86e5642835aeeb78f04129e39daab888f182e8664ea0a6a4500a0c16c2` (byteidentisch) |
| Original-Screenshotsatz (111 PNG, historischer Wert aus der frueheren Fassung dieser Notiz, Methode dort nicht dokumentiert) | `0b2cfaee0cdc27fa243d546fe2d94bc869fed6e71884636ea3a89f4077137ba7` |
| Original-Screenshotsatz (111 PNG, transparenter Pruefwert: sha256 von sortierten `sha256  name\n`) | `b8d1f142b0e9521177c1cc830dd49548a83bebd95c4e3a8f1def571992309a4e` |
| Promoteter Screenshotsatz (172 PNG, selbe transparente Aggregation: sha256 von sortierten `sha256  name\n`) | `7fb5cccefc6a3f5e90a9aae13e52fde0a771c95e88f5fd2b76e6b79792193b60` |

*Berechnungsmethode der transparenten Screenshot-Mengenhashes:* Fuer alle PNG-Dateien
des Verzeichnisses wird der individuelle SHA-256-Hash gebildet, alphabetisch nach
Dateiname als Zeile `"<hash>  <dateiname>\n"` sortiert und darueber der zusammenfassende
SHA-256 gebildet.

## Offene Punkte fuer Nachfolgepakete

- **Fira-vs-Master-Schriftkonflikt:** Das Produkt bindet Fira Sans ein und rendert
  sie auf allen Oberflaechen. Master §5.2 verlangt fuer Hauptueberschriften (H1)
  und Card-Titel die Serifenschrift Georgia (`common.fonts.conflict` in der Matrix).
  Die Entscheidung und Bereinigung gehoert zu **`MP-UI-BRAND-DECISION`**, welches
  parallel vorbereitet wurde (`design-reference-0911.md`).
- **Sidebar-Breakpoint 1200 vs. 992:** Das Produkt klappt die Admin-Sidebar erst ab
  1200px aus (`templates/admin/_workflow_sidebar.html:34`, `navbar-expand-xl`);
  Master §10 verlangt 992px bei unveraenderten Hersteller-Breakpoints, und Master §12
  prueft 1024×768 ausdruecklich «mit Sidebar». Die Vorherbilder bei 1024×768 zeigen
  deshalb heute den eingeklappten Zustand. Entscheidung in `MP-UI-BRAND-DECISION`,
  Umsetzung in `MP-UI-SHELL`. (Es gibt kein Tailwind im Projekt; die Viewports
  1440/1024/768/390/1920 sind Pruefgroessen aus Master §12, keine Breakpoints.)
- **Semantik von `capability: null`:** 15 visuelle Admin-Routen fuehren in der Matrix
  `capability: null`, da ihre `@_protected`-Wrapper die Capability abhaengig von der
  HTTP-Methode waehlen (GET `draft.read`, POST `recipe.write` bzw. `masterdata.write`).
  Die Rollen (Editor, Publisher, Admin) sind serverseitig korrekt abgesichert und
  werden durch den Laufzeittest `test_matrix_roles_match_server_side_authorization`
  fuer jeden Request bestaetigt. Die Erklaerung ist in `common.capability_semantics`
  festgehalten; ein Refactoring gehoert zu den jeweiligen Modul-WPs (`MP-UI-RECIPE-FORMS`, `MP-UI-RECIPE-TOOLS`, `MP-UI-COOKBOOKS`,
  `MP-UI-FOUNDATIONS`).
- **Entra und Yodeck:** Authentifizierung gegen einen echten Tenant und physische
  Signage-Hardware bleiben absichtlich unsimuliert; sie werden in Testumgebungen
  nicht synthetisiert oder gefaelscht.
- **Barrierefreiheit und Kontrast:** Die Baseline-Screenshots erfassen den visuellen
  Ist-Zustand gemaess Browser-Rendering. Kontrastpruefungen, Tastaturnavigation und
  Screenreader-Semantik sind Aufgabe der Umsetzungs-WPs (`MP-UI-TOKENS`, `MP-UI-SHELL`).
