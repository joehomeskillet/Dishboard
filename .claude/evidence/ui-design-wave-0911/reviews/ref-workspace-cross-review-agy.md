# Review-Bericht MP-UI-REF-WORKSPACE (`wp-aff8638d6f3f`)

- **Worktree:** `/nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911`
- **Branch:** `feat/ui-ref-workspace-0911`
- **HEAD:** `ced933c0c0c3984a793a5e8a4d8299fad8fe58b9` (`ced933c`)
- **Basis:** `815fb7d0f9e3867c4bc0098c359f838bf81590a0` (`815fb7d`)
- **Reviewer-Modell:** Antigravity (Gemini 3.8 Flash High)
- **Autor:** Cursor (Composer 2.5)
- **Art:** Read-Only Cross-Vendor-Review

---

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | `reference_scaffold/cafeteria/static/admin-week-tabler.css:160` | Fester Wert `padding-left: 1.25rem;` (20 px) in `.patient-admin-option ul` statt Abstands-Token aus der Design-Skala. | minor | Auf `var(--app-space-4)` (16 px) oder `var(--app-space-6)` (24 px) umstellen, um strikt der Skala aus `tokens.css` zu entsprechen. |
| 2 | `reference_scaffold/cafeteria/templates/admin/cafeteria.html:82–84`, `patienten.html:80–82` | Redundanter Aktionslink: «Wochenangaben prüfen» ist sowohl im `page_header` (Zeilen 21 bzw. 19) als auch weiterhin im Flashtext/Body (`.admin-week-review-link`) vorhanden. | minor | Nach Klärung etwaiger Test-Abhängigkeiten auf `.admin-week-review-link` den doppelten Body-Link zugunsten der Header-Aktion entfernen. |

---

## Geprüft und in Ordnung

### 1. Fach- und Formvertrag byteweise gleich
- **Cafeteria:**
  - `#week-publish-form` ([`cafeteria.html:58–78`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L58-L78)): `method="post" action="/admin/{{ family }}/publish"`, Hidden-Felder `_csrf`, `week`, `row_version`, Abbrechen/Publizieren unverändert.
  - `#schedule-defaults` ([`cafeteria.html:91–96`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L91-L96)): `action="{{ url_for('admin.schedule_defaults', family=family) }}"`, Hidden-Felder `_csrf`, `week`, `row_version` identisch.
  - `.admin-overview-form` ([`cafeteria.html:99–116`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L99-L116)): `action="/admin/{{ family }}/header"`, Felder `title`, `shared_note`, CAS `row_version`, `_csrf`.
  - `.admin-week-service` ([`cafeteria.html:137–167`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L137-L167)): Felder `service_state`, `notice`, `service_start`, `service_end`, `_csrf`, `week`, `day`, `meal`, `row_version`.
- **Patienten:**
  - `#week-publish-form` ([`patienten.html:56–76`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L56-L76)), `#patient-header` ([`patienten.html:89–106`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L89-L106)), `#schedule-defaults` ([`patienten.html:109–114`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L109-L114)) und `.admin-week-service` ([`patienten.html:131–163, 188–220`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L131-L163)) behalten sämtliche Attribute, CAS-Felder und POST-Semantiken.
- Keine erfundenen Aktionen, Summen, Suchen oder Tabellenspalten.

### 2. Nur gefrorene Bausteine und Token-Disziplin
- Makro-Imports in [`cafeteria.html:3`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L3) und [`patienten.html:3`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L3) konsumieren ausschliesslich die gefrorenen Makros `icon`, `profile_tabs`, `field`, `page_header`, `status_badge`, `form_errors` aus `admin/_macros.html`.
- Layout-Variable: `{% set layout_variant = 'workspace' %}` ([`cafeteria.html:5`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L5), [`patienten.html:5`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L5)).
- Keine Inline-Styles (`style=`), kein `!important` in CSS, keine Hex-Farben (`#...`) in CSS oder Templates.
- Alle 8 verwendeten Icons (`clipboard-check`, `eye`, `copy`, `check`, `calendar-cog`, `device-floppy`, `pencil`, `file-import`) existieren verifiziert im gepinnten Sprite `tabler-icons.svg`.
- CSS-Scoping: Jede einzelne Regel in [`admin-week-tabler.css:1–250`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/static/admin-week-tabler.css#L1-L250) ist strikt unter `.dishboard-admin .admin-main[data-layout="workspace"]` isoliert; Duplikate zu `admin-tabler.css` wurden restlos bereinigt.

### 3. Seitenkopf und Layoutvariante
- Seitenkopf entspricht exakt Shell-Spec §7.2 Nr. 5:
  - H1 «Cafeteria-Plan bearbeiten» ([`cafeteria.html:20`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L20)) bzw. «Patientenplan bearbeiten» ([`patienten.html:18`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L18)).
  - Beschreibung dynamisch aus Variablen: `KW {{ iso_week }} · {{ area_names[profile] }} · {{ cells|length }} Menükarten` ([`cafeteria.html:13`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L13), [`patienten.html:11`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L11)).
  - Breadcrumb mit echtem URL-Helper `url_for('admin.cafeteria')` bzw. `url_for('admin.patienten')` ([`cafeteria.html:20`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L20), [`patienten.html:18`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L18)).
  - Kopfaktion «Wochenangaben prüfen» verlinkt auf `/admin/{{ family }}/wochen/pruefung?week={{ week_value }}`.
- Layoutvariante «Arbeitsfläche volle Breite» gemäss Shell-Spec §8.2 Nr. 5 & 26: `data-layout="workspace"` setzt über `admin-tabler.css:370–373` `max-width: none;` auf `.container-xl`.

### 4. Master §8 Komponenten- und Layoutregeln
- **Cards & Geometrie:** `.admin-day-card`, `.menu-slot` und `.admin-overview-form` nutzen `var(--app-radius-card)` (12 px) und `var(--app-border)`. Menü-Slots sind über CSS Subgrid ([`admin-week-tabler.css:163–231`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/static/admin-week-tabler.css#L163-L231)) exakt ausgerichtet; Höhen-/Breiten-Delta <= 1 px ist im Test belegt ([`test_ui_reference_workspace_browser.py:121–123`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L121-L123)).
- **Typografie:** Keine Texte unter 14 px (`var(--app-font-size-label)` = 14 px, Titel `var(--app-font-size-title)` = 20 px).
- **Status-Badges:** Text + Fläche über `status_badge(status, label=status_label)` ([`cafeteria.html:42`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L42), [`patienten.html:40`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L40)).
- **Dominante Aktion:** Primary-Button ausschliesslich für «Publizieren» (`.btn-primary`, [`cafeteria.html:47, 76`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/cafeteria.html#L47), [`patienten.html:45, 74`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/templates/admin/patienten.html#L45)) und Formular-Speichern; alle Nebenaktionen neutral (`.btn`).
- **Bedienhöhe:** `min-height: var(--app-control-min-height)` (44 px) in [`admin-week-tabler.css:4, 19`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/static/admin-week-tabler.css#L4).
- **Einspaltig mobil:** Formularfelder und Menükarten stapeln responsiv unter 768 px (`col-12 col-md-6`, `@media (min-width: 768px)`).
- **Kein Pflichttext-Clamp:** Notizen, Allergene und Titel werden vollständig angezeigt und sind im Test abgesichert ([`test_ui_reference_workspace_browser.py:127–139`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L127-L139)).

### 5. Matrix- und Testabdeckung (`test_ui_reference_workspace_browser.py`)
- Neue Testdatei hat 258 Zeilen (< 400 Zeilen Limit), ruff check meldet `All checks passed!`.
- 5 Viewports abgedeckt: `(1440, 900)`, `(1024, 768)`, `(768, 1024)`, `(390, 844)`, `(1920, 1080)` ([Zeile 26](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L26)).
- Zustände: `empty`, `ready`, `dense`, `longtext`, `dialog_publish` (inkl. Escape und Fokus-Rückkehr, [Zeilen 141–156](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L141-L156)), NoJS-Publish ([Zeilen 158–179](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L158-L179)), NoJS-409-Konflikt ([Zeilen 181–208](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L181-L208)), 403-Berechtigungsprüfung ([Zeilen 210–222](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L210-L222)), Editor-Navigation ([Zeilen 224–236](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L224-L236)) und Menübilder-Einstellung ([Zeilen 238–259](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L238-L259)).
- Dokumentüberlauf: `_assert_no_overflow` ([Zeilen 38–40](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L38-L40)) prüft `document.documentElement.scrollWidth <= innerWidth + 1` in allen Zuständen.
- Screenshots werden ausschliesslich nach `tmp_path` geschrieben ([Zeile 106](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/tests/test_ui_reference_workspace_browser.py#L106)).
- Rote Fremdtests: Der Ausfall in `test_admin_week_tabler_browser.py:70` (`expect(toggle).to_be_visible()`) ist plausibel belegt, da jener Test noch die alte 1200-px-Schwelle abfragt, während MP-UI-SHELL auf 992 px standardisiert wurde. Die Datei ist nicht owned und wurde korrekterweise nicht modifiziert.

### 6. Besitzgrenzen
- `git diff --stat 815fb7d..HEAD` betrifft exakt die vier Owned-Dateien:
  - `reference_scaffold/cafeteria/templates/admin/cafeteria.html` (28 Zeilen Diff)
  - `reference_scaffold/cafeteria/templates/admin/patienten.html` (34 Zeilen Diff)
  - `reference_scaffold/cafeteria/static/admin-week-tabler.css` (207 Zeilen Diff)
  - `reference_scaffold/tests/test_ui_reference_workspace_browser.py` (258 Zeilen neu)
- Keine Fremddateien berührt.

### 7. Design-Qualität («Swiss Editorial Calm»)
- Keine Schlagschatten hinzugefügt; ruhige Farb- und Schriftführung.
- Fokus sichtbar und bedienbar: `scroll-margin-top: 12rem` (bzw. `var(--app-space-6)` mobil) sichert Tastaturnavigation bei fixierten Controls ab ([`admin-week-tabler.css:232–248`](file:///nvmetank1/projects/menuplan/.claude/worktrees/ui-ref-workspace-cursor-0911/reference_scaffold/cafeteria/static/admin-week-tabler.css#L232-L248)).

---

## Nicht geprüft

- Keine erneute interaktive Playwright- oder Pytest-Ausführung im Pool-Wrapper, da dies ein reiner Read-Only-Reviewauftrag ist (Verbot von Datenbankzugriffen und Pool-Kollisionen).
- Dedizierte Prüfung für 200%-Zoom und `@media (prefers-reduced-motion: reduce)` (nur über die Defaults im Page-Context abgedeckt).
- OCR-Pass (OpenCodeReview via externem Nebius-LLM wurde abgebrochen, um Hänger zu vermeiden).

WAVE-REVIEW: FINDINGS(2)

[exited with code 0]
