# Cross-Vendor-Review MP-UI-REF-DETAIL (wp-d4d493887de3-review)

| Feld | Wert |
|---|---|
| **Branch** | `feat/ui-ref-detail-0911` |
| **HEAD** | `71762bf` (`feat(ui): align recipe revision detail reference with master design system and shell spec`; Autorbericht — `rtk git rev-parse` in dieser Session nicht ausführbar) |
| **Basis** | `815fb7d0f9e3867c4bc0098c359f838bf81590a0` |
| **Reviewer / Modell** | cursor composer-2.5 |
| **Autor / Modell** | antigravity-agy / gemini-3.8-flash-high |
| **Worktree** | `/nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-detail-agy-0911` |
| **Scope** | `reference_scaffold/cafeteria/templates/admin/rezepte_revision.html`, `reference_scaffold/tests/test_ui_reference_detail_browser.py` |

---

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | `reference_scaffold/tests/test_ui_reference_detail_browser.py:1-348` | Zoom-200-%-Prüfung fehlt. `surfaces-wps.json` verlangt für MP-UI-REF-DETAIL explizit «Zoom200/reduced-motion»; die Suite setzt nur `reduced_motion='reduce'` (z. B. `:137-138`), aber kein `document.documentElement.style.zoom = '2'` wie in der Listen-Referenz (`ui-ref-list-codex-0911/.../test_ui_reference_list_browser.py:263-269`). | **major** | Pro Viewport (mindestens 1440 und 390) Zoom-200-%-Block ergänzen, Overflow/Geometrie erneut assertieren, Screenshot nach `tmp_path`. |
| 2 | `reference_scaffold/tests/test_ui_reference_detail_browser.py:313-348` | Matrix-Zustand `access_denied_401` (`ui-route-matrix.json:2252-2257`) fehlt; nur `403` ist abgedeckt (`:332-347`). Review-Prüfpunkt 5 verweist auf Matrix-Zustände. | **minor** | `test_detail_reference_unauthenticated_gets_401` ergänzen (analog `test_ui_reference_list_browser.py:330-337`) oder im Bericht begründen, warum 401 ausschliesslich über Routen-/Auth-Tests ausreicht. |
| 3 | `reference_scaffold/tests/test_ui_reference_detail_browser.py:296-307` | «Fokus sichtbar» nur per programmatischem `.focus()` geprüft, ohne `outlineStyle`/`outlineWidth`/`outlineColor` (Master §10, Listen-Referenz `:180-181`). Sichtbarer Burgunder-Fokusring ist nicht belegt. | **minor** | Nach Tab/Fokus `getComputedStyle` auf mindestens «Alle Revisionen», «PDF öffnen» und `#target-yield` prüfen (`outlineStyle === 'solid'`, `outlineWidth >= 2`, Farbe `rgb(163, 22, 77)`). |
| 4 | `reference_scaffold/tests/test_ui_reference_detail_browser.py:30-91` | Matrix-Zustand `empty` (`ui-route-matrix.json:2252-2254`) nicht abgebildet. Fixtures decken normal, ohne Bilder, langtextig ab; keine Revision ohne Zutaten und ohne Schritte mit Leerzustands-Assertion (`[data-empty-kind]` oder Tabellenzeile «Keine Zutaten gespeichert.» / «Keine Schritte gespeichert.»). | **minor** | Drittes Fixture mit leerer Revision anlegen und mindestens 1440×900 + 390×844 testen; Leerzustand von «kein Suchtreffer»/«keine Berechtigung» unterscheiden (Master §8). |

---

## Geprüft und in Ordnung

| Prüfpunkt | Beleg |
|---|---|
| **1 Fach-/Formvertrag (Skalierung)** | `amount_form`-Aufruf byteweise unverändert gegen Basis (`rezepte_revision.html:49` vs. Basis in `ui-ref-list-codex-0911/.../rezepte_revision.html:16`): `method="get"`, `name="yield"`, `id="target-yield"`, Action `url_for('admin.recipe_revision', …)` via Makro `rezepte_scale.html:4-6`. Kein POST, kein CSRF/CAS auf dieser GET-Route — fachlich korrekt. |
| **1 PDF-/Navigationslinks** | «Alle Revisionen» → `url_for('admin.recipe_revisions', recipe_id=recipe_id)` (`:21`); «PDF öffnen» → `url_for('admin.recipe_revision_pdf', …, yield=calculated.target)` (`:22`); identisch zur Basis (`:10`). Test prüft href und `yield`-Sync (`test_ui_reference_detail_browser.py:159-165,268-272`). |
| **1 Keine neuen Aktionen/Spalten** | Nur bestehende Header-Links, Skalierungsformular, Snapshot-`details`, `symbols()`; keine Suche, Pagination oder zusätzliche Tabellenspalten. |
| **1 404/403-Verhalten** | Route `recipe_revision_routes.py:79-81` (`abort(404)`); Test 404/403 (`test_ui_reference_detail_browser.py:323-347`). 409/503 nicht im Template-Besitz; bestehende `test_recipe_revision_routes.py`-Semantik unangetastet. |
| **2 Gefrorene Bausteine** | `layout_variant = 'standard'` (`rezepte_revision.html:2`), `page_header`/`icon`/`status_badge` aus `admin/_macros.html` (`:3,12-23,29`); `amount_form`/`ingredients`/`symbols` aus `rezepte_scale.html` (`:4,49-50,103`). Kein eigenes CSS, kein `!important`, keine Hexwerte, keine Inline-Styles im Template. |
| **3 Seitenkopf (lesbarer Abgleich mit Brief)** | H1 = `payload.title` (`:13`); Beschreibung mit Revisionsnummer und `created_at.isoformat()` (`:14`); Breadcrumb `Rezepte` → Titel → `Revisionen` mit echten `url_for` (`:15-18`); sekundär «Alle Revisionen», primär «PDF öffnen» (`:21-22`). |
| **3 Layoutvariante Standard 1440** | Explizit gesetzt; Test `data-layout="standard"` (`test_ui_reference_detail_browser.py:145`). `base_tabler.html:23-24` rendert Attribut auf `main.admin-main`. |
| **4 Master §8 Cards/Tabellen/Badges** | Strukturierte Cards (`:26-48,51-74,76-97,99-102`); semantische Zutatentabelle via `ingredients`-Makro; `status_badge('archived', label='Unveränderlich')` mit sichtbarem Text (`:29`, Test `:169-170`); Tabellen-Schrift ≥14 px (`:117-122,177-178`); Bilder mit expliziten Massen (`:65,85`). |
| **4 Dominante Primäraktion** | Genau ein `btn-primary` im Kopf («PDF öffnen», `:22`); Skalierungs-Primary im Formular unverändert seit Basis. |
| **4 Interaktionshöhe** | `assert_geometry` verlangt sichtbare `.btn`/`.form-control` ≥48×48 px (`:113-116`) — über Master-Minimum 44 px. |
| **5 Viewports (Normalzustand)** | Alle fünf Viewports parametrisiert (`:21-27,131-201`); Screenshots nach `tmp_path` (`:125-128`). |
| **5 JS an/aus, Tastatur, Overflow** | NoJS-Test (`:284-310`); `java_script_enabled=False`; Overflow-Check `scrollWidth <= innerWidth + 1` (`:111`). |
| **5 Skalierung/invalid** | `yield=8` in URL und PDF-Query (`:250-272`); ungültige Eingabe → `#yield-error` (`:274-279`). |
| **6 Besitz (lesend)** | Autorbericht und Brief nennen ausschliesslich Template + neuer Test; keine fremden Route-/Store-Änderungen im Worktree-Lesebild. |
| **7 Design-Qualität** | Ruhige Card-Hierarchie, Primary sparsam im Kopf, `text-secondary` für Metadaten, responsive Bildraster, keine zusätzlichen Schatten/Icons ausser `arrow-left`-Sprite (`:21`). |

---

## Nicht geprüft

| Bereich | Grund |
|---|---|
| `rtk git diff --stat 815fb7d..HEAD` / vollständiger Diff | Shell-Aufrufe (`rtk git …`) in dieser Session abgelehnt; Basis-Vergleich statisch über Parallel-Worktree `ui-ref-list-codex-0911` (Stand vor Detail-WP). |
| Gate-Re-Run (Pytest 90 passed, Ruff, `git diff --check`, `git status`) | Nicht ausgeführt; Plausibilität nur anhand Autorbericht `wp-d4d493887de3.md`. |
| `docs/design/2026-09-11-admin-shell-navigation-spec.md` §7.2 Nr. 3 / §8.2 Nr. 31 | Datei fehlt im Worktree; Seitenkopf-/Layout-Anforderungen über Autor-Brief und Template-Leseprüfung abgeglichen. |
| Live-Browser-Lauf / Screenshot-Dateien | Keine Reproduktion; Pfade nur aus Autorbericht gelesen. |
| OCR-Review-Gate | Autorbericht: `rtk ocr review` übersprungen (read-only FS). |
| GitNexus Impact / `detect_changes` | Laut Vertrag entfällt für Templates/Tests. |
| Matrix-Zustand `empty` (fachliche Einordnung) | Ohne klaren Empty-Szenario-Contract nur als Testlücke (Nr. 4) gewertet, nicht als Template-Fehler. |

---

**Fazit:** Template-Umsetzung ist fachlich und formal stimmig (Formvertrag erhalten, Shell-/Master-Bausteine korrekt konsumiert, Normalzustand solide getestet). Für die Freigabe fehlen noch Zoom-200-%-Nachweis und ergänzende Matrix-/Fokus-Tests.

WAVE-REVIEW: FINDINGS(4)
recorded 12560 wp_id=wp-cursor-run-2026-09-11T17:57:00.681704+00:00

[exited with code 0]
