# Cross-Vendor-Review MP-UI-TOKENS — wp-e8edcc4213f4-review

| Feld | Wert |
|---|---|
| Branch | `feat/ui-tokens-0911` |
| HEAD | `25b95571864a3dd57a6303dc5ed02202d105d6c6` |
| Basis | `docs/ui-brand-decision-0911` @ `05b6c81acc6ea26096fe1b1824463badeee5287c` |
| Worktree | `/nvmetank1/projects/menuplan/.claude/worktrees/ui-tokens-codex-0911` |
| Autor | Codex gpt-6-astra (`wp-e8edcc4213f4`) |
| Reviewer | grok-4.6 |
| Diff | `05b6c81..HEAD` — 4 Dateien, +925/−55 |

Read-only. Keine Repo-Änderung, kein Commit, kein Push, kein Browser, keine Paketinstallation. Quellen: Worktree, Autorbericht `wp-e8edcc4213f4.md`, Gate-Logs unter `scratchpad/tmp-codex-tokens/`.

## Befunde

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | `reference_scaffold/cafeteria/static/admin-tabler.css:30–31` und `:164`; Mapping `ui-brand-compatibility-decision.md` §2 | `--tblr-link-color-rgb` ist an `--app-primary-rgb` gebunden; `--tblr-link-hover-color` ist `--app-primary-hover`. **`--tblr-link-hover-color-rgb` fehlt** (grep 0 Treffer). Vendor-Default bleibt `4.8,88.8,167.2` (Tabler-Blau-Kanäle). Direkte Regel `a:not(.btn):not(.nav-link):not(.page-link):hover` deckt normale Links ab; Tabler-Utilities, die nur die RGB-Kanäle lesen, können Hover-Blau behalten. Autor begründet das mit den vier Brand-Override-Werten ohne Hover-RGB. | minor | `--tblr-link-hover-color-rgb` aus dem effektiven Hover ableiten (Master `142,18,63` bzw. Brand-Hover-Kanäle), analog zu `--tblr-link-color-rgb`. |
| 2 | Autorbericht OCR-Abschnitt; Log `tmp-codex-tokens/ocr-required.log:1–7` | Vorgeschriebenes `ocr review` ist **failed/cancelled** (`0 finding(s); 4 of 4 selected item(s) failed`, SambaNova Llama-3.3-70B). Bericht markiert OCR noch als PENDING. Kein Produktfehler, aber Check 6 des WP-Vertrags fehlt. | minor | OCR einmal ohne Extra-Background erneut fahren oder den Fehlschlag im WP-Bericht als `OCR: FAILED` statt PENDING führen. Dieser Cross-Vendor-Review ersetzt die inhaltliche Prüfung. |

Keine blocker, keine major. Master-Farbwerte, K8-B-Schatten, Fira-Stacks, Brand-Gate, Besitzgrenzen und Chromium-`getComputedStyle`-Tests halten.

## Geprüft und in Ordnung

### 1. Master-Treue (`tokens.css` unter `.dishboard-admin`)

Alle 35 Farbtoken aus Master §5.1 stehen in `tokens.css:112–146` mit **exakt denselben Hex-/Kanalwerten**. Abweichungstabelle: leer.

| Token | Soll (Master §5.1) | Ist | Zeile |
|---|---|---|---|
| `--app-bg` | `#F6F4F1` | `#F6F4F1` | 112 |
| `--app-surface` | `#FFFFFF` | `#FFFFFF` | 113 |
| `--app-surface-soft` | `#FAF9F7` | `#FAF9F7` | 114 |
| `--app-sidebar` | `#173C3F` | `#173C3F` | 115 |
| `--app-sidebar-hover` | `#214A4D` | `#214A4D` | 116 |
| `--app-sidebar-active` | `#31585B` | `#31585B` | 117 |
| `--app-sidebar-text` | `#C7D8D9` | `#C7D8D9` | 118 |
| `--app-sidebar-label` | `#9AB7BA` | `#9AB7BA` | 119 |
| `--app-sidebar-indicator` | `#F3A6C0` | `#F3A6C0` | 120 |
| `--app-primary` | `#A3164D` | `#A3164D` | 121 |
| `--app-primary-rgb` | `163, 22, 77` | `163, 22, 77` | 122 |
| `--app-primary-hover` | `#8E123F` | `#8E123F` | 123 |
| `--app-primary-active` | `#7C1037` | `#7C1037` | 124 |
| `--app-primary-soft` | `#F7E8EE` | `#F7E8EE` | 125 |
| `--app-on-primary` | `#FFFFFF` | `#FFFFFF` | 126 |
| `--app-text` | `#1F2937` | `#1F2937` | 127 |
| `--app-text-muted` | `#596273` | `#596273` | 128 |
| `--app-border` | `#E5E7EB` | `#E5E7EB` | 129 |
| `--app-border-soft` | `#EFECE8` | `#EFECE8` | 130 |
| `--app-control-border` | `#808B99` | `#808B99` | 131 |
| `--app-focus` | `#A3164D` | `#A3164D` | 132 |
| `--app-success` / `-text` / `-soft` | `#2FB344` / `#166534` / `#EAF8ED` | gleich | 133–135 |
| `--app-warning` / `-text` / `-soft` | `#F59F00` / `#854D0E` / `#FFF4D6` | gleich | 136–138 |
| `--app-danger` / `-text` / `-soft` | `#D63939` / `#B42318` / `#FCEAEA` | gleich | 139–141 |
| `--app-info` / `-text` / `-soft` | `#4299E1` / `#175CD3` / `#EAF4FC` | gleich | 142–144 |
| `--app-neutral-text` / `-soft` | `#475467` / `#EEF0F2` | gleich | 145–146 |

Mass-/Typo-/Abstandstoken §5.2 plus K1-A: Sidebar 248px (`:172`), Topbar 64px (`:173`), Container 1440/960 (`:174–175`), Radien 12/8/999 (`:176–178`), Interaktion 44px (`:179`), Skala 4/8/12/16/24/32/40/48 (`:180–187`), Schatten **`0 1px 2px rgba(0, 0, 0, 0.025)`** (`:188`, K8-B / Entscheidung §10). `--app-font-body` / `--app-font-heading` sind die ausgeschriebenen Stacks aus `:105–106`, nicht `var(--sh-font)` (`:161–162`). Schriftrollen 1rem / 2.125rem / 1.75rem / 1.25rem / 0.875rem / 0.8125rem und Line-Heights 1.5 / 1.2 / 1.3 (`:163–171`).

K1-A weicht bewusst von Master-Wortlaut Arial/Georgia ab; das ist die angenommene Entscheidung, kein Tokenfehler.

### 2. Geschützte Kanäle

- `git diff 05b6c81..HEAD -- tokens.css` ist **nur Addition** nach `:root` (Zeile 106). Die 72 `--sh-*`-Rootwerte (`:3–106`) und vier `@font-face`-Blöcke (`:240`, `:248`, `:256`, `:264`) sind unangetastet.
- `admin-tabler.css`: grep auf `.public-page`, `.print-body`, `.signage-body`, `auth-` → 0 Treffer. Alle Regeln unter `.dishboard-admin`.
- `branding_tokens.py`: Admin-Heading/Flächen/Sidebar/Tabs/File-Button-Overrides entfernt (`:91–101`). Globales `!important` nur noch unter `:where(body:not(.dishboard-admin))` (`:96–97`). `.public-page`/`.signage-body` behalten die bisherigen Nicht-Admin-`--tblr-*`-Flächen (`:92–95`). `brand_tokens()` selbst unverändert (`:12–64`).
- Tests mit **Vorher-Konstanten**: `test_ui_master_tokens_browser.py:39–123` — Kommentar «Measured before product edits at 05b6c81»; `test_protected_channels` (`:203–217`) vergleicht `getComputedStyle` (Farbe, Fläche, Font, Größe, Radius) für `/cafeteria/heute/`, `/druck/cafeteria/woche`, `/signage/cafeteria/tag`, `/auth/local` × drei Marken. Before-Lauf: `before-fixed.log` → `3 passed`, `GATE_EXIT=0`.

CSS-Quelle von `branding_css` ist nicht byte-identisch (nötige `:where`-Umstellung). Berechnete Schlüsselwerte der geschützten Kanäle sind getestet.

### 3. Tabler-Mapping

- `--tblr-*-border-subtle` → `--app-border` für success/warning/danger/info/secondary (`admin-tabler.css:207–217`).
- `readonly`: Kontur `--app-control-border`, Fläche `--app-surface-soft`, Text `--app-text`, `opacity: 1` (`:136–139`). Browserbeleg `test_brand_gate_real_admin` `:357–360`.
- Fokus: `outline: 2px solid var(--app-focus); outline-offset: 2px; box-shadow: none` an Controls (`:130–132`) und interaktiven Elementen (`:275`); Sidebar-Fokus `--app-sidebar-indicator` (`:276`). Tests hart auf `rgb(163, 22, 77)` / `2px` / Offset (`:240–242`).
- Hartes `--tblr-primary-rgb: 140,28,75` und `--tblr-primary-lt-fg` entfernt; `--tblr-primary-rgb: var(--app-primary-rgb)` (`:21`).
- Breakpoints `992px` / `991.98px` (`:279`, `:284`, `:317`); kein `1200px`/`1199.98px`.
- `!important`: 0 in `admin-tabler.css`. Hex-grep `#[0-9a-fA-F]{3,8}` in derselben Datei: **0 Treffer**.
- Zustände: `.btn-primary` / outline / danger (`:97–119`), Felder disabled/invalid/valid/file (`:126–161`), Tabs inkl. `.nav.nav-tabs` (deckt `card-header-tabs` im Fixture, `:166–182`), Pagination alle Zustände (`:183–195`), `.list-group-item.active` (`:201–203`), Status-Pills 13px / 4px 10px / `999px` (`:220–248`, `:267–271`), Alerts Rahmen `--app-border` (`:249–258`).
- Schrift: `--tblr-font-sans-serif` / `--tblr-body-font-family` = `--app-font-body` (`:3–4`); `--tblr-btn-font-family` am `.btn` (`:91`); `h1,h2,h3,.card-title` = `--app-font-heading` 700 (`:299–301`). Kein festes `16px` am Root.
- K7-A: compact Card-Inset 24/16, comfortable 32/24 (`:307–308`, `:322–323`); large `--app-font-scale: 1.125` (`:298`); contained `max-width: var(--app-container-width)` 1440, `min-width: 0` am Main (`:52`, `:309–316`). 48px-Ziele erhalten (`:83–84`).
- `navbar-expand-xl` bleibt HTML (SHELL); Autorbericht nennt das ausdrücklich.

### 4. Brand-Gate (K5-A)

`branding_tokens.py:67–79`:

- `validate_config` → `contrast()` aus `branding_config.py:39–45` (unrunded `(L+0.05)/(l+0.05)`).
- Flächen `#FFFFFF`, `#F6F4F1`, `#FAF9F7`, `#F7E8EE` (`:73`). Weiss-als-On-Primary ist dasselbe Paar wie Primary gegen `#FFFFFF`.
- Textgrenze 4.5 für Primary/Hover/Active auf allen vier Flächen; 4.5 impliziert Nicht-Text ≥ 3 für dieselben Paare (`:74–75`).
- Atomar: bei einem Fehlschlag nur Kommentar, **kein** Teilsatz (`:76`); sonst alle vier Variablen (`:78–79`).
- Hover/Active: `_blend(primary, 0, .12)` / `.24` (`:70`) — dieselbe `round`-Formel wie `:7–9`.
- Default `#8c1c4b`: Hover `round(140×0.88)=123`, `round(28×0.88)=25`, `round(75×0.88)=66` → `#7b1942`; Active `round(140×0.76)=106`, `round(28×0.76)=21`, `round(75×0.76)=57` → `#6a1539`; RGB `140, 28, 75`. Tests `:323–342`.
- `brand_tokens()` unverändert; Fehlerpfade von `validate_config` laufen zuerst in `branding_css:83`. Keine Mutation gespeicherter Revisionen.
- Browser: Default wendet Brand-Primary an; `#d98fb0` (dark) fällt auf Master `#a3164d`; `/__tokens__` mit `brand=undefined()` (`:159`) hält Master ohne Brand-Stylesheet (`:253–255`). Grenzfall `#bd4573` (Weiss ≥ 4.5, Primary-Soft < 4.5) atomar abgelehnt (`:410–415`).

### 5. Tests (`test_ui_master_tokens_browser.py`)

Acht Auftragspunkte:

| Punkt | Beleg |
|---|---|
| 1 Tokens + Fokus + `--tblr-primary-rgb` | `getComputedStyle` `:193–200`, `:251–255`, `:240–242` — kein Quelltext-Grep als Beweis |
| 2 Schrift + CDP | `font-family` startswith Fira (`:343–344`); `CSS.getPlatformFontsForNode` (`:345–354`) |
| 3 Zustände | Button/Feld/Tab/Pagination/Checkbox/readonly; nicht anwendbare Zustände kommentiert (`:312–313`) |
| 4 Darstellung | beide Werte aller vier Attribute, Main + Preview, Höhe ≥ Inhalt (`:378–407`) |
| 5 Brand-Gate | Default / Reject / kein Stylesheet (`:323–360`, `:245`, `:159`) |
| 6 Schutz + Vorher-Konstanten | `:39–217` |
| 7 WCAG aus angrenzenden berechneten Farben | `:418–443` |
| 8 Viewports 1440/1024/768/390/1920, Overflow, Padding 32/32/24/16/32, Screenshots `tmp_path` | `:363–376` |

`skipped`: verified.log `26 passed` ohne skipped; regression.log `14 failed, 641 passed, 8 warnings` ohne skipped. Pool-DB über `_factory`/`change_branding`; Screenshots und JSON nur unter `tmp_path`. Keine Produktivdaten.

### 6. Besitzgrenzen

`git diff --name-status 05b6c81..HEAD`:

```
M  reference_scaffold/cafeteria/branding_tokens.py
M  reference_scaffold/cafeteria/static/admin-tabler.css
M  reference_scaffold/cafeteria/static/tokens.css
A  reference_scaffold/tests/test_ui_master_tokens_browser.py
```

Keine Fremdtests geändert. Rote Fremdtests im Bericht (12px-Compact, comfortable-Padding, rgba-außerhalb-`:root`, Paket-Hex-Validator, doppeltes `--sh-primary`) passen zu K7-A und den neuen `.dishboard-admin`-Hexwerten. Worktree `git status --porcelain`: leer.

### 7. Gates (Abgleich Logs)

| Gate | Log / Bericht | Inhalt |
|---|---|---|
| Neue Tests + branding_browser | `verified.log` | `26 passed in 89.60s` / `GATE_EXIT=0` — deckungsgleich mit Bericht |
| Vorher Schutz | `before-fixed.log` | `3 passed in 14.25s` / `GATE_EXIT=0` |
| 28-Datei-Regression | `regression.log:1174–1175` | `14 failed, 641 passed, 8 warnings in 785.29s` / `GATE_EXIT=1` — deckungsgleich; 13 Restfälle Fremdbesitz, ein Alert-Fall laut Autor in owned CSS nachgezogen |
| ruff / mypy / `git diff --check` | nur im Bericht zitiert | `All checks passed!` / `Success: no issues found` / leere `--check`-Ausgabe; **keine separaten .log-Dateien** neben `mypy/`-Cache |

### 8. Design-Qualität

Code und Referenzscreenshot `darstellung-1440.png` (Autor-Artefakt, kein Live-Browser dieses Reviews): warme Fläche `#F6F4F1`, Petrol-Sidebar, weisse Karten mit Haarlinie plus K8-B-Minimalschatten, **eine** gefüllte Primary-Aktion, Outline für Nebenaktionen, Status als Text+Fläche (Pills in Komponenten-Tests), Fokus 2px mit Offset, keine Vendor-Schlagschatten, Original-Logo. Sidebar-Gruppierung und `navbar-expand-xl` sind SHELL, nicht dieses WP. Kein TOKENS-Verstoß gegen «Swiss Editorial Calm».

## Nicht geprüft

- Kein erneuter pytest-/ruff-/mypy-Lauf in diesem Review (nur Log- und Quellabgleich).
- Kein Live-Server, keine Produktionsmarke, kein physischer Druck/TV, kein axe.
- GitNexus `detect_changes` am Worktree (Autor: Index fehlt); Impact nur aus Autorbericht.
- Nicht alle Viewport-Screenshots pixelweise nachbewertet; eine 1440-Darstellung plus CSS/Tests.
- Vendor-`a:hover`-RGB-Pfad nicht im Browser nachgestellt (Befund 1 bleibt theoretisch plus Mapping-Lücke).
- 28-Datei-Regression nach dem Alert-Fix nicht wiederholt; Restliste der 13 Fremdtests bleibt die des Original-Logs.

WAVE-REVIEW: FINDINGS(2)
