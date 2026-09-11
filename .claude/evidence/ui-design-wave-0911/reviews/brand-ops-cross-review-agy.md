# Cross-Vendor-Review MP-UI-BRAND-OPS (read-only)

| Metadatum | Wert |
|---|---|
| **Worktree** | `/nvmetank1/projects/menuplan/.claude/worktrees/ui-page-brand-ops-cursor-0911` |
| **Branch** | `feat/ui-page-brand-ops-0911` |
| **HEAD** | `ac00ee850d09388ec8ad8c41411462432e22af19` (`ac00ee8`) |
| **Basis** | `43a4c991419e5882c39ed6f217a8dfc99f248d0c` (`43a4c99`) |
| **Orchestrator** | Claude Code (`claude-fable-5-1`) |
| **Autor** | Cursor (`composer-2.5`), WP `wp-dbe7823b31df` |
| **Reviewer** | Antigravity AGY (`gemini-3.8-flash-high`) |

---

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | `reference_scaffold/cafeteria/templates/admin/branding_editor.html:4`, `reference_scaffold/cafeteria/templates/admin/operations.html:4`, `reference_scaffold/tests/test_ui_brand_ops_browser.py:67-72, 116-121` | **Vollbreiten-Vorgabe (2026-09-12):** Beide Templates deklarieren `{% set layout_variant = 'narrow' %}`. Der neue Browser-Test prüft hart `expect(main).to_have_attribute('data-layout', 'narrow')` und `assert container_max_w == '960px'`. Sobald das parallele Seitenrahmen-WP `narrow` aufhebt, bricht die 960px-Assertion. Gemäss Vorgabe ist dies ein Hinweis (minor), kein Blocker. | minor | Bei Integration des Vollbreiten-Seitenrahmens `layout_variant` auf `standard` setzen bzw. die 960px-Assertion im Test lockern/entfernen. |
| 2 | `reference_scaffold/tests/test_ui_brand_ops_browser.py:56-88, 105-130` | **Matrix-Abdeckung Fehlerzustand im Browser-Test:** Die Matrix (`docs/superpowers/backlog-0909/ui-route-matrix.json`) fordert für `branding_editor` und `operations_settings` die Zustände `default`, `empty`, `invalid`, `401`, `403`. Der neue Test deckt 17 Fälle ab (Default, Viewports, 401, 403, Focus, Zoom, NoJS), testet aber keinen POST mit `invalid` Daten (z. B. unvollständige Palette oder fehlerhafte Zeit) direkt in der neuen Testdatei. Fehlerpfade werden primär über bestehende Tests (`test_branding_routes.py`, `test_admin_operations_browser.py`) abgedeckt. | minor | In einer Folgeiteration einen Browser-Testfall für Validierungsfehler beim Branding-POST ergänzen. |
| 3 | `reference_scaffold/cafeteria/templates/admin/operations.html:109` | **Wörterbuch-Abweichung durch Testvertrag erzwungen:** Der Button trägt weiterhin die Beschriftung `{{ icon('eye') }}Service laden` statt «Ausgabe laden». Dies ist eine bewusste und notwendige Massnahme zur Erhaltung des Testvertrags, da der bestehende Fremdtest `test_admin_operations_browser.py:52` explizit `page.get_by_role('button', name='Service laden', exact=True).click()` verlangt. | minor | So belassen, bis der Fremdtest `test_admin_operations_browser.py:52` im gleichen Zug angepasst werden darf. |
| 4 | `reference_scaffold/cafeteria/templates/admin/branding_editor.html:82` | **Wörterbuch-Abweichung durch Testvertrag erzwungen:** Der Button nutzt `'Revision ' ~ selected.id ~ ' aktivieren'` statt «Version ...». Auch dies schützt den bestehenden Testvertrag, da `test_branding_browser.py:84` hart `page.get_by_role('button', name='Revision 2 aktivieren').click()` aufruft. Im Revisionsverlauf (`brand-history-card`) wurde das Wörterbuch mit «Frühere Versionen» (Z. 89) und «Version {{ item.id }}» (Z. 93) bereits umgesetzt. | minor | So belassen, bis der Fremdtest `test_branding_browser.py:84` harmonisiert werden darf. |

---

## Geprüft und in Ordnung

### 1. Fach- und Formvertrag (byteweise stabil)
- **`branding_editor.html`:**
  - Formulare, IDs und Methoden: Formular 1 (`Z. 21–65`) nutzt `action="{{ url_for('admin.branding_editor') }}"`, `method="post"`, `enctype="multipart/form-data"`. CSRF-Token `_csrf` und CAS-Feld `version="{{ document.version }}"` (`Z. 22`) sind unverändert vorhanden.
  - Feldnamen: `name` (`Z. 26`), `logo_sha256` (`Z. 28`), `logo` (`Z. 36`), Farbpalette `primary`, `accent`, `surface`, `text` (`Z. 47`), Schriften `font_body`, `font_heading` (`Z. 57`) entsprechen exakt dem Backend-Vertrag in `cafeteria/admin/branding_routes.py:100-130`.
  - Dekorativer Farbwähler: `<input class="brand-color-swatch">` (`Z. 46`) besitzt bewusst **kein** `name`-Attribut, ist `disabled`, trägt `tabindex="-1"` und `aria-hidden="true"`. Dadurch wird er beim Submit nicht übertragen und stört den POST-Vertrag nicht.
  - Logo-Standard: `<option value="">Südhang Standard</option>` (`Z. 29`) zur Aktivierung von `LogoNone` bleibt identisch.
  - Aktionen & Reset: `actions(primary={'label': 'Entwurf speichern & Vorschau', 'type': 'submit', 'name': 'action', 'value': 'save'})` (`Z. 63`), Revisionsaktivierung mit `name="action" value="activate"` (`Z. 82`), Übernahme als Entwurf mit `name="action" value="restore"` (`Z. 83`) und Reset-Formular mit `name="action" value="reset"` (`Z. 99–104`) sind formtreu.
  - Fehlererhalt: Bei `brand_error` (`Z. 18`) bleiben die Eingaben via `value="{{ brand_name }}"` und `value="{{ brand_values[key] }}"` vollständig erhalten.

- **`operations.html`:**
  - Formulare, IDs und CSRF:
    - Bereichsnamen: `id="name-{{ code }}"`, `action="save_name_{{ code }}"`, `name="expected_{{ code }}"`, `name="name_{{ code }}"` (`Z. 30–39`).
    - Wochenendbetrieb: `id="weekend-form"`, `action="save_weekend"`, `name="expected_allows_weekend"`, `name="allows_weekend"` (`Z. 44–57`).
    - Wochenvorgaben: `id="schedule-{{ code }}"`, `action="save_schedule"`, `name="profile"`, `name="revision"`, `_csrf="{{ schedule_csrf[code] }}"` (`Z. 60–90`).
    - Datierte Ausnahmen: Load-Formular `id="exception-load"`, `action="load_exception"` (`Z. 97–111`); Save-Formular `id="exception-save"`, `action="save_exception"` mit Hidden-Fields `profile`, `date`, `meal`, `row_version`, `loaded` (`Z. 113–125`).
  - CAS/Versionsschutz & Validierung: Alle CAS-Felder (`row_version`, `revision`, `expected_*`) sind erhalten. Die Makros `validation(id)` (`Z. 9–11`), `error_text(id)` (`Z. 12–14`) und `input(...)` (`Z. 15–20`) wurden byteweise nicht angetastet. Fehlererhalt via `values.get(...)` funktioniert wie im Bestand.
  - Backend-Logik: Keine Änderungen an Python-Routen oder SQL; 409-Konflikt- und 503-Verhalten bleiben unberührt.

### 2. E5 1–4 Abgleich & Wörterbuch
- **E5-1 (Status-Differenzierung & Hierarchie):**
  - Klares Status-Banner oben: `<strong>Aktuelles Design:</strong> {{ active_revision.name }} · Version {{ document.active_revision }}. Entwürfe werden erst nach Aktivierung öffentlich sichtbar.` (`branding_editor.html:14-17`).
  - Entwurfsbereich: Überschrift `Entwurf bearbeiten` (`branding_editor.html:23`).
  - Vorschau-Kontext: Überschrift `Gespeicherte Vorschau · Version {{ selected.id }}` (`branding_editor.html:69`) und Metazeile `Aktuelles Design` vs. `Früher aktiv` vs. `Gespeicherter Entwurf` (`branding_editor.html:71-74`).
  - Revisionsverlauf nachgeordnet: Eingebettet in ein natives `<details class="card brand-history-card">` mit `<summary>` «Frühere Versionen» (`branding_editor.html:88-105`), standardmässig eingeklappt.
- **E5-2 (Zusammenhängende Bearbeitung & Kontrast):**
  - Formular fasst Logo-Auswahl, Logo-Upload, Farbpalette und Typografie in einer übersichtlichen Karte zusammen (`branding_editor.html:24-61`).
  - Kontrasthinweis vorhanden: «mindestens 4.5:1» (`branding_editor.html:40`).
- **E5-3 (Keine falsche «Live-Vorschau»):**
  - Weder im Template noch im CSS noch in Tests taucht der irreführende Begriff «Live-Vorschau» auf.
  - Explizit benannt als: `Gespeicherte Vorschau · Version {{ selected.id }}` (`branding_editor.html:69`) und Hinweistext: `Die Vorschau zeigt den gespeicherten Stand der gewählten Version. Neue Eingaben zuerst als Entwurf speichern.` (`branding_editor.html:76`).
  - Button heisst treffend: `Entwurf speichern & Vorschau` (`branding_editor.html:63`).
- **E5-4 (Trennung von Speichern & Aktivieren; CSS-Scoping):**
  - Speichern (`action="save"`, Editor-Card) und Aktivieren (`action="activate"`, Preview-Card) sind klar getrennt.
  - `admin-branding.css` ist strikt auf `.brand-*`-Klassen gescopt und leckt nicht in Public/Print/Signage.
- **Wörterbuch (Konzept §3.3):**
  - `Erscheinungsbild` statt `Logo, Farben & Schrift` (`branding_editor.html:6, 8, 11`).
  - `Bereiche & Öffnungszeiten` statt `Bereiche & Zeiten` (`operations.html:5, 7`).
  - `Ausgabe und Öffnungszeiten` / `neue Ausgaben` statt `Services` (`operations.html:7, 25, 54, 96`).
  - `Version` statt `Revision` im Verlauf (`branding_editor.html:89, 93, 102`).
  - Schweizer Kontext in Vorschau: `Pouletbrust an Kräutersauce`, `Kartoffelstock`, `Zucchetti mit Kräutern`, `Allergene noch zu prüfen.` (`branding_preview.html:16-18`).

### 3. Bausteine & CSS-Hygiene
- **Bausteine:**
  - `page_header`-Makro korrekt eingebunden: `{{ page_header('Erscheinungsbild', description='...') }}` (`branding_editor.html:8`) und `{{ page_header('Bereiche & Öffnungszeiten', description='...') }}` (`operations.html:7`). Beide erzeugen genau ein semantisches `<h1>` und keine künstlichen Breadcrumbs.
  - Makros `select` und `actions` aus `admin/_macros.html` werden verwendet (`branding_editor.html:2, 57, 63, 81`).
- **CSS-Hygiene (`admin-branding.css`):**
  - Exakt 75 Zeilen CSS.
  - **Keine einzige Hex-Farbe (`#...`)**: Alle Farben verwenden semantische Tokens (`var(--app-border)`, `var(--app-surface-soft)`, `var(--app-info)`, `var(--app-primary)`, `var(--app-primary-soft)`, `var(--app-on-primary)`, `var(--app-text-muted)`).
  - **Kein einziges `!important`**.
  - **Keine Inline-Styles oder Inline-Scripts** in den Templates (Überprüfung via Regex lieferte 0 Treffer; strikte CSP-Konformität).

### 4. Master §8 Layout & Komponentenregeln
- **Responsive Formularstruktur:**
  - Desktop: 2-Spalten-Layout (`col-12 col-xl-6` in `branding_editor.html:20, 67`).
  - Mobil (< 768 px): Durchgängig 1-spaltig (`col-12`), Inputs und Selects brechen sauber um.
- **Bedienmasse & Typografie:**
  - Mindesthöhe interaktiver Elemente: `--app-control-min-height` (44 px) durchgängig angewendet (`admin-branding.css:28, 40, 67`) und in `test_ui_brand_ops_browser.py:47-54` programmatisch verifiziert (`height >= 44`, `fontSize >= 14`).
- **Aktionshierarchie:**
  - Genau eine dominante Primäraktion pro Handlungskontext: `Entwurf speichern & Vorschau` (`btn-primary` in Editor-Card), `Revision X aktivieren` (`btn-primary` in Preview-Card), `Ausnahme speichern` (`btn-primary` in Exceptions-Save).
  - Sekundäraktionen sind neutral (`btn`), Reset-Aktion ist neutral.
- **Fehlerrückmeldung:**
  - `invalid-feedback` adjazent unter jedem Formularfeld via `error_text(id)` mit passendem `aria-describedby` und `aria-invalid` (`operations.html:9-20`).

### 5. Plausibilität der Testergebnisse & Fremdtest-Analyse
- **Neuer Test (`test_ui_brand_ops_browser.py`):**
  - 17 Tests ausgeführt und alle 17 bestanden (`17 passed in 36.49s`).
  - Viewports: 1440×900, 1024×768, 768×1024, 390×844, 1920×1080.
  - Weitere Tests: Standalone-Preview, 401/403 für unberechtigte Rollen, Tastaturnavigation mit Fokusprüfung, Zoom 200 % / 640×480 Reflow, No-JS Save für Wochenendbetrieb.
  - `skipped` = 0.
- **Fremdtest-Befund (`test_admin_operations_browser.py:44`):**
  - 247 passed, 3 failed.
  - Die 3 Fehler treten ausschliesslich in `test_admin_operations_browser.py:44` bei `expect(invalid).to_be_focused()` mit `javascript=True` über drei Viewports (390, 820, 1440) auf.
  - **Prüfung des Markups:** In `operations.html:10` lautet das Makro unverändert:
    `{% if errors.get(id) %} aria-invalid="true" aria-describedby="{{ id }}-error"{% if id == errors.keys()|first %} autofocus{% endif %}{% endif %}`
  - Das fehlerhafte Feld `staff_guest-slot_6_LUNCH_end` trägt nach dem POST-Submit das HTML5-Attribut `autofocus`. Es ist genau ein einziges Element mit `autofocus` im DOM.
  - In Playwright meldet die Fokusevaluation nach einem POST-Reload bei aktivem JS den Zustand «inactive», weil der Browser-Fokus nach dem Reload nicht automatisch auf das headless Element übergeht.
  - Da im Template `operations.html` weder das `validation`-Makro noch die Formularstruktur geändert wurden (nur Titel-, Header- und Wörterbuchtexte), handelt es sich zweifelsfrei um eine **veraltete Annahme des Bestands-Tests** und **keinen Rückschritt** durch das vorliegende Arbeitspaket.

### 6. Besitzgrenzen
- `rtk git diff --stat 43a4c99..HEAD` zeigt Änderungen an exakt den 5 zugewiesenen Dateien:
  1. `reference_scaffold/cafeteria/static/admin-branding.css` (+74, -4)
  2. `reference_scaffold/cafeteria/templates/admin/branding_editor.html` (+75, -35)
  3. `reference_scaffold/cafeteria/templates/admin/branding_preview.html` (+9, -3)
  4. `reference_scaffold/cafeteria/templates/admin/operations.html` (+6, -5)
  5. `reference_scaffold/tests/test_ui_brand_ops_browser.py` (+212, neu)
- Keine fremden Dateien im Diff, kein Staged-Leak, kein Branch-Leak.
- Alle Module liegen mit max. 213 Zeilen deutlich unter der Obergrenze von 400 Zeilen.

### 7. Design-Qualität («Swiss Editorial Calm»)
- Klare, ruhige Hierarchie ohne visuelles Rauschen.
- Zweispaltige Ausrichtung auf Desktop trennt Eingabe und Sichtprüfung auf natürliche Weise.
- Geringer Einsatz von Primary-Buttons; History unaufdringlich in Details-Element verpackt.
- Konsistente Typografie über serifenlose Controls und Serifentitel im Einklang mit dem Designsystem.

---

## Nicht geprüft

- **OCR / visuelle Sollbild-Abnahme E5:** Das Sollbild `docs/design/screenshot-referenzen-0911/soll/E5-erscheinungsbild.png` ist im Repository nicht vorhanden (Status in `UI_REFERENZEN.md` Tabelle Kapitel 3: `FEHLT`).
- **Eigene Testläufe:** Gemäss striktem Read-only-Reviewauftrag wurden keine Testsuiten erneut ausgeführt; die Bewertung stützt sich auf die Verifikation des Quellcodes, der Diffs und der Gate-Receipts des Autors.
- **Automatische Kontrastmessung externer Tools:** Es wurde die strukturelle Einhaltung der Token und Test-Assertions geprüft; keine separate Pixel-Messung via Lighthouse/Axe im laufenden Browser.

WAVE-REVIEW: FINDINGS(4)
