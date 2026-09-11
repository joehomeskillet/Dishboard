# Cross-Vendor-Review MP-UI-WEEKS (wp-27fc916afbb9)

- **Branch:** `feat/ui-page-weeks-0911`
- **HEAD:** `da1ed771976e874b0458cdef27e68f07e3fd0e02` (`feat(ui): align week management and review pages with R2 reference`)
- **Basis:** `cbed49229d3dbd041542d86af41d6d3e735ea0c1`
- **Reviewer-Modell:** `gemini-3.8-flash-high` (agy / Antigravity)
- **Autoren:** `codex` (`gpt-6-astra`, Entwurf) und `cursor` (`composer-2.5`, Abschluss)
- **Worktree:** `/nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911`
- **Review-Tooling:** `rtk ocr review`: `OCR: FAILED (429)` (Rate-Limit bei Sambanova Meta-Llama-3.3-70B-Instruct)

---

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere (blocker/major/minor) | Vorschlag |
|---|---|---|---|---|
| – | – | Keine Abweichungen oder Vertragsverletzungen festgestellt. | – | – |

*(Hinweis zur Begriffskonsistenz: In [`week_review.html:9`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_review.html#L9) führt der Link `Zur Wochenübersicht` auf `url_for('admin.' ~ family, week=week)`. Dies entspricht exakt dem unveränderten Bestandsstand aus `cbed492` und wahrt die Routing-Stabilität. Da `admin.week_management` nun offiziell den H1-Titel «Wochenübersicht» trägt, kann in einer späteren Welle eine Schärfung des Labels auf «Zum Wochenplan» erwogen werden.)*

---

## Geprüft und in Ordnung

### 1. Fach- und Formularvertrag
- **Formular «Neue Woche anlegen»** ([`week_management.html:64–85`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L64-L85)):
  - Methode `POST`, Ziel `url_for('admin.week_create', family=family)`.
  - Byteweise übereinstimmende Feld- und Token-Namen: `_csrf` ([`Z. 67`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L67)), versioniertes Formtoken `row_version` mit Wert `"0"` ([`Z. 68`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L68)), `week` (ID `new-week-date`, [`Z. 71`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L71)), `title` (ID `new-week-name`, [`Z. 74`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L74)), `shared_note` (ID `new-week-note`, [`Z. 78`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L78)).
  - Werteerhalt bei Servervalidierungsfehlern gesichert über `values.week`, `values.title`, `values.shared_note`.
- **Formular «Wochenprüfung bestätigen»** ([`week_review.html:58–63`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_review.html#L58-L63)):
  - Methode `POST`, Ziel `url_for('admin.week_review_post', family=family)`.
  - Felder: `_csrf`, `week`, `context_version` mit `review.token` (CAS-Token).
  - Bei vorliegendem Prüfbeleg (`review.receipt`, [`Z. 16–20`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_review.html#L16-L20)) bzw. fehlenden Schreibrechten ([`Z. 64–66`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_review.html#L64-L66)) wird das Formular unterdrückt.
- **Kopieraktion** ([`week_management.html:40–42`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L40-L42)):
  - Ziel-Link `url_for('admin.copy_get', family=family, week=row.next_week.isoformat())`.
  - Benennt Quelle, Ziel und Wirkung gemäss KRITIK 3.D Punkt 4 und ist via `aria-describedby="copy-{{ row.id }}"` zugänglich verknüpft.
- **Fehler- und Abort-Verhalten**:
  - In [`test_ui_weeks_browser.py:178–217, 262–285, 339–381`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/tests/test_ui_weeks_browser.py#L178-L217) ist verifiziert, dass HTTP 400, 409 (Stale Context), 503 sowie 401/403 zu keinem unbeabsichtigten Schreibvorgang führen und die Datenbank-Snapshots vor und nach dem Fehler exakt übereinstimmen.

### 2. Gefrorene Bausteine und Codehygiene
- **Makros**: Ausschließlich gefrorene Makros aus `admin/_macros.html` importiert (`page_header`, `profile_tabs`, `pagination`, `field`, `status`, `empty_state`, `icon`).
- **Layoutvariante**: Beide Seiten definieren `{% set layout_variant = 'standard' %}` gemäss Shell-Spec §8.2 Nr. 40/41 ([`week_management.html:3`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L3), [`week_review.html:3`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_review.html#L3)).
- **Styles & Scripts**: Keine harten Hex-Farbcodes (`#...`), keine `!important`-Deklarationen, keine Inline-Styles und keine Inline-Scripts vorhanden. Dies wird automatisiert durch Playwright in [`test_ui_weeks_browser.py:87–89`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/tests/test_ui_weeks_browser.py#L87-L89) geprüft.
- **`<details>`-Element für Neuanlage** ([`week_management.html:62–86`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L62-L86)):
  - Nativ HTML5; öffnet bei serverseitigem Fehler automatisch (`{% if error %} open{% endif %}`).
  - Funktioniert vollständig ohne JavaScript (NoJS) und ist uneingeschränkt tastaturbedienbar (`Tab`, `Enter` auf `<summary>`), wie in [`test_ui_weeks_browser.py:166–172`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/tests/test_ui_weeks_browser.py#L166-L172) getestet.

### 3. R2-Vorgaben («Verbindlich übernehmen» 1–5) und Wörterbuch
1. **Vorhandene Wochen zuerst** ([`week_management.html:12–60`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L12-L60)): Die Tabelle der gespeicherten Wochen steht im DOM vor dem Anlegebereich. Datumsbereich ([`Z. 24`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L24)) und Kalenderwoche (`KW ... / ...`, [`Z. 25`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L25)) sind verständlich und ohne 5-Tage-Verkürzung aufbereitet.
2. **Neuanlage bei Bedarf** ([`week_management.html:62`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L62)): Standardmässig geschlossen, bei Fehler geöffnet, Eingaben bleiben erhalten.
3. **Hauptaktion «Woche öffnen»** ([`week_management.html:36`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L36)): Eindeutiger Primär-Button der Zeile (`class="btn text-wrap"`). Vorschau ([`Z. 37`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L37)) und Kopieren ([`Z. 40`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L40)) sind dezent als `btn-ghost-secondary border-0` nachgeordnet.
4. **Kopieren mit Quell-/Zielnachweis** ([`week_management.html:40–42`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L40-L42)): Quelle, Ziel und Bedingung («Ziel muss leer und unveröffentlicht sein») vollständig deklariert.
5. **Paginierung nur bei weiteren Seiten** ([`week_management.html:51–58`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L51-L58)): Umschlossen von `{% if has_next or page > 1 %}`; keine Paginierungsanzeige bei Einzelseiten.
- **Wörterbuch gemäss Konzept §3.3**:
  - «Veröffentlicht» statt «live» ([`week_management.html:29`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L29)).
  - «Noch zu prüfen» mit Grundangabe ([`week_management.html:30`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L30), [`week_review.html:23–25`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_review.html#L23-L25)).
  - «Ausgabehinweis» und «Öffnungszeit» statt «Service» ([`week_review.html:8, 15, 18, 36, 47, 48, 62`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_review.html#L8)).
  - Ehrliches Prüfstatus-Banner: Geltungsbereich («Wochenkopf und Ausgabehinweise für diesen gespeicherten Stand», [`week_review.html:18`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_review.html#L18)) sowie Prüfender und Zeitstempel transparent ausgewiesen.
  - Keine Beispieldaten, Mockup-Preise oder funktionslose Demo-Buttons aus dem Sollbild übernommen.

### 4. Master §8: Typografie, Geometrie und Barrierefreiheit
- **Schriftgrössen & Bedienhöhen**: Interaktive Elemente (`.btn`, Inputs, `textarea`, `summary`) besitzen eine Mindesthöhe von ≥ 48 px ([`test_ui_weeks_browser.py:90–92`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/tests/test_ui_weeks_browser.py#L90-L92)), was die Mindestvorgabe von 44 px sicher erfüllt.
- **Scrollregion**: Horizontale Scrollregion der Wochenliste ist als Region mit Tastaturfokus ausgezeichnet (`role="region" aria-label="Wochenliste" tabindex="0"`, [`week_management.html:14`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/cafeteria/templates/admin/week_management.html#L14)) und tastaturbedienbar ([`test_ui_weeks_browser.py:140–145`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/tests/test_ui_weeks_browser.py#L140-L145)).
- **Kontraste**: Alle Text-/Hintergrundkombinationen erreichen ein Kontrastverhältnis von ≥ 4.5:1 ([`test_ui_weeks_browser.py:116`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/tests/test_ui_weeks_browser.py#L116)).
- **Zoom 200 %**: Beide Routen reflowen bei 200 % Browserzoom auf 1440 px und 390 px ohne horizontalen Dokumentüberlauf ([`test_ui_weeks_browser.py:147–153, 323–337`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-page-weeks-codex-0911/reference_scaffold/tests/test_ui_weeks_browser.py#L147-L153)).

### 5. Testabdeckung und Fremdtest-Klassifizierung
- **Testsuite `test_ui_weeks_browser.py`**: 20/20 Tests grün (5 Tests × 4 Parametrisierungen: Cafeteria/Patienten × JS an/aus). Alle geforderten Zustände aus der Matrix (`empty`, `normal`, `dense-long`, `last-page`, `ready`, `live`, `changed`, `read-only`, `400`, `409`, `503`, `401/403`) und alle 5 Viewports (1440×900, 1024×768, 768×1024, 390×844, 1920×1080) sind abgedeckt. `skipped` = 0.
- **Rote Fremdtests (84 passed, 2 failed)**:
  1. `tests/test_week_management_browser.py:17`: Erwartet H1 `Wochenverwaltung`. **Einstufung: Veraltete Annahme.** R2 und KRITIK 3.D schreiben für diese Ansicht den Titel «Wochenübersicht» verbindlich vor.
  2. `tests/test_week_review_routes.py:137`: Erwartet Button-Text `Servicehinweise`. **Einstufung: Veraltete Annahme.** Konzept §3.3 (Wörterbuch) verlangt zwingend die Ersetzung von «Service» durch «Ausgabe» / «Ausgabehinweis».
  Beide Testfehlschläge stellen somit keinen Regressionsdefekt dar.

### 6. Besitzgrenzen
- `git diff --stat cbed492..HEAD` zeigt ausschliesslich Änderungen an den drei zugewiesenen Dateien:
  - `reference_scaffold/cafeteria/templates/admin/week_management.html` (89 Zeilen)
  - `reference_scaffold/cafeteria/templates/admin/week_review.html` (68 Zeilen)
  - `reference_scaffold/tests/test_ui_weeks_browser.py` (381 Zeilen)
- Keine unberührten Dateien im Diff; alle Module bleiben weit unter 400 Zeilen. Keine neuen Abhängigkeiten.

### 7. Design-Qualität («Swiss Editorial Calm»)
- Ruhige, strukturierte Darstellung mit klarer typografischer Hierarchie.
- Sparsamer Einsatz der Primärfarbe (nur für den Erstell-Button und die Prüfbestätigung).
- Keine Schlagschatten; Fokusringe deutlich sichtbar (`solid`, Stärke ≥ 2 px).

---

## Nicht geprüft
- **Eigene Testausführung**: Gemäss Review-Auftrag nicht ausgeführt (Auswertung und Plausibilisierung des vorliegenden autoritativen Testberichts).
- **`tests/test_admin_week_ui.py`**: Wurde bereits im Bericht des Autors als nicht gefahrenes Gate deklariert.

WAVE-REVIEW: CLEAN
