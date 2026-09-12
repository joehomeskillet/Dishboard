# Cross-Vendor-Review: MP-UI-FULLWIDTH-SHELL (wp-ui-fullwidth-shell-0912)

| Feld | Wert |
|---|---|
| **Branch** | `feat/ui-fullwidth-shell-0912` |
| **HEAD** | `4d600420ff47d9a1a6d85c03e8a70078691a1ea2` |
| **Basis** | `3bc918520e35ada6e036a634dfbd16f9ab733fc7` (Shell v2) |
| **Reviewer** | cursor / composer-2.5 |
| **Autor** | grok-build / grok-4.6 |
| **Modus** | read-only (keine Dateiänderungen, keine eigenen Testläufe) |

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | `reference_scaffold/cafeteria/static/tokens.css:176` | `--app-container-narrow: 960px` hat keinen CSS-Verbraucher mehr (nur `--app-container-width` in `admin-tabler.css:383` für `.display-preview`). Vorgabe: Token nur für lokale Scrollregionen/Tabellen-Mindestbreiten **oder entfernen**. | minor | Token entfernen oder in Follow-up-WP auf lokale Tabellen-`min-width` umbenennen; Kommentar in `tokens.css:174` entsprechend anpassen. |
| 2 | `docs/design/2026-09-11-admin-shell-navigation-spec.md:542` | §11.1 Viewport-Matrix erwartet noch `standard` 1440 px / `narrow` 960 px — widerspricht §8.1 (Vorgabe 2026-09-12: immer volle Breite). Liegt ausserhalb des WP-Besitzes (§8.1/§8.2), aber Dokumentationsdrift. | minor | In separatem Doku-WP §11.1 auf volle Arbeitsbreite angleichen; kein Blocker für diesen CSS-/Shell-Commit. |
| 3 | Gate-Auftrag (Brief) / Autorbericht §Gates | Vollständiger Gate-Aufruf lief zweimal mit `GATE_EXIT=4` (`tests/test_ui_reference_settings_browser.py` u. a. fehlen auf Basis `3bc9185`). Autor-Subset: 172 passed, `skipped` 0. Implementierung plausibel, formeller Gate-Vertrag des Briefs nicht erfüllt. | minor | Gate-Skript im Orchestrator-Brief an tatsächlich vorhandene Tests anpassen; Subset-Ergebnis als Nachweis akzeptieren, bis Brief korrigiert ist. |

## Geprüft und in Ordnung

**1. Vollbreite / keine Einengung (Prüfpunkt 1)**  
- `admin-tabler.css:360-363`: `.dishboard-admin .admin-main > :is(header, .admin-area-tabs, .page-body) > .container-xl` und `.page-header > .container-xl` mit `max-width: none; width: 100%; margin-inline: 0; padding-inline: var(--app-page-padding)`.  
- Keine `[data-layout=…]`- oder `[data-content-width]`-Regeln am `.admin-main` mehr (Repo-weite Suche: 0 Treffer für `[data-layout`).  
- `admin-tabler.css:54`: `.admin-main { min-width: 0 }` erhalten.  
- Sidebar-Overflow: `admin-tabler.css:317-319`, `333-334` (`overflow-y: auto` auf `.admin-nav`).  
- Tabler-`container-xl`-Defaults werden durch `.dishboard-admin …` überschrieben (höhere Spezifität).

**2. Seitenabstand / gemeinsame Kante (Prüfpunkt 2)**  
- `admin-tabler.css:48`: Desktop `--app-page-padding: var(--app-space-8)` (32 px).  
- `admin-tabler.css:385-389`: Tablet 24 px (`--app-space-6`), Smartphone 16 px (`--app-space-4`).  
- Einheitliches `padding-inline` auf Header-, Tabs- und Body-`.container-xl` (`admin-tabler.css:363`).  
- Tests: `test_ui_master_shell_browser.py:332-337` (32/24/16), `test_ui_master_shell_browser.py:359-363` (gleiche linke Kante ±1 px).

**3. Keine Nebenwirkung Public/Print/Signage (Prüfpunkt 3)**  
- Autorbericht: `public.css` / `signage.css` nicht im Diff.  
- `.display-preview` bewusst separat behandelt (`admin-tabler.css:383-384`), nicht `.public-page` / `.signage-body`.

**4. Option «Inhaltsbreite» (Prüfpunkt 4)**  
- Feld `admin_content_width`, Werte `contained`/`full` unverändert (`display_settings.html:16`, `22-23`).  
- Hilfetext ehrlich: volle Arbeitsfläche; Begrenzt/Voll nur Vorschau (`display_settings.html:16`).  
- CSS-Wirkung nur auf `.display-preview[data-content-width=…]` (`admin-tabler.css:383-384`); `main.admin-main` trägt Attribut (`base_tabler.html:26`), ohne Breiten-CSS.  
- Test deckt Vorschau vs. Shell ab (`test_admin_display_options_browser.py:35-36`, `57-62`, `90-91`).

**5. Tokens / keine Hex-/`!important`-/Inline-Einführung (Prüfpunkt 5)**  
- Kein `!important` und keine neuen Hexwerte in `admin-tabler.css` (Suche leer).  
- Keine Inline-Styles in `base_tabler.html` / `display_settings.html`.  
- `--app-container-width` nur für Preview-Cap (`admin-tabler.css:383`); Kommentar in `tokens.css:174`.

**6. Doku (Prüfpunkt 6)**  
- Master §5.2: eine Zeile «Arbeitsbreite» volle Breite, 24–32/16 (`2026-09-09-unified-ui-design-system.md:190-191`); alte Standard-/Schmal-Zeilen entfernt.  
- Shell-Spec §8.1/§8.2: «Volle Breite», Vorgabe 2026-09-12, historische Begründungen erhalten (`2026-09-11-admin-shell-navigation-spec.md:369-384`).

**7. Tests (Prüfpunkt 7)**  
- Neuer `test_ui_fullwidth_shell_browser.py`: 5 Routen × 1280/1440/1920/2560, Container = Main − 2·Padding ±1 px (`:61-62`), gemeinsame Kante (`:64-68`), kein Overflow (`:63`, `:77-79`), 390/720×450 (`:73-79`).  
- `test_ui_master_shell_browser.py:339-366`: alle drei früheren Varianten messen `maxWidth: none` und volle Breite.  
- Overflow-/Fokus-/44-px-Prüfungen in Shell-Tests erhalten (`:473-479`, Keyboard-/Kontrast-Tests unverändert im Scope).  
- Fremdtests `test_ui_reference_*`, `test_ui_menu_editor_browser.py`, `test_ui_brand_ops_browser.py` existieren auf Basis `3bc9185` nicht — nicht anpassbar, kein Rückschritt durch diesen Diff.  
- Autorbericht: Subset 172 passed, `skipped` 0; Ruff clean.

**8. Template-Kommentar (Prüfpunkt 1 Ergänzung)**  
- `base_tabler.html:24-26`: Kommentar + `layout_variant` bleibt, ohne Breitenwirkung.

## Nicht geprüft

- **Eigene Browser-/Gate-Läufe** (laut Auftrag Autorbericht auswerten).  
- **`rtk git diff 3bc9185..HEAD --stat`** — `rtk` in dieser Session nicht verfügbar; natives `git diff`/`git log`/`git show` abgelehnt. Besitzgrenze (Prüfpunkt 8) nur über Autorbericht + Stichproben der erwarteten Dateien beurteilt, nicht per Diff-Stat verifiziert.  
- **Screenshots** unter `tmp-grok-fullwidth/pytest/…` (nicht eingelesen).  
- **OCR-Review** (Autor: SambaNova 429×2, keine Findings).  
- **design-validator**, mypy, Token-AST-Audit.  
- **Laufzeit-Verifikation** Tabler-Spezifitätsreihenfolge im echten Browser (CSS-Logik und Tests als Proxy).

---

WAVE-REVIEW: FINDINGS(3)
