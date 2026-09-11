# Cross-Vendor-Review MP-UI-SHELL (read-only)

**Branch:** `feat/ui-shell-0911`  
**HEAD:** `c66b93ba494b59a797085c723e13aab99a36f324` (`feat(ui): rebuild the admin shell navigation and 992px breakpoint per master spec`)  
**Basis:** `25b95571864a3dd57a6303dc5ed02202d105d6c6` (feat/ui-tokens-0911)  
**Reviewer-Modell:** cursor composer-2.5  
**Autor-Modell:** grok-4.6  
**Spezifikation:** `docs/design/2026-09-11-admin-shell-navigation-spec.md` (im Worktree nicht vorhanden; Inhalt aus Scratchpad-Export und Auftragsbrief geprüft)

---

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|----|-------------|--------|---------|-----------|
| 1 | `reference_scaffold/cafeteria/static/admin-tabler.css:312` | Sidebar-`:focus-visible` nutzt `outline-color: var(--app-sidebar-indicator)` statt Spec §5.3.3/§11.2.2 (`2px` weiss via `--app-surface`). | major | Auf `outline-color: var(--app-surface)` umstellen (globaler `:focus-visible`-Block Zeile 311 bleibt für Nicht-Sidebar). |
| 2 | `reference_scaffold/tests/test_admin_shell_ui.py:102-107` | Abmelde-POST liegt in `.navbar-footer` ausserhalb von `nav[aria-label="Backend"]`; Fremdtest sucht `navigation.locator('form')`. | major | In Folge-WP Tests auf `form.admin-logout-form` umstellen (Autor darf Fremdtests nicht ändern; im WP-Bericht benennen). |
| 3 | `reference_scaffold/tests/test_admin_tabler_browser.py:65-78` | Breakpoint-Schwelle noch `width < 1200`; Implementierung nutzt `navbar-expand-lg` (992 px). Bei 1024×768 und 1199×800 erwarten Tests Burger/versteckte Nav, Sidebar sollte aber offen sein. | major | Fremdtests auf 992 px anpassen (Folge-WP); plausibel erwartete Regression. |
| 4 | `reference_scaffold/tests/test_admin_shell_ui.py:78` | `collapsed = width < 1200` weicht vom neuen 992-px-Vertrag ab; parametrisiert nur 390/1440 → aktuell grün, aber falscher Vertrag für spätere Viewports. | minor | Schwelle auf 992 setzen oder Kommentar/Assertion an K2-A koppeln. |
| 5 | `reference_scaffold/tests/test_ui_master_shell_browser.py:184-214` | Escape, Fokusrückkehr, Viewports und Overflow sind abgedeckt; Spec §11.2.3 Fokusfalle (`Tab`/`Shift+Tab` im offenen Menü) fehlt. | minor | Ein Assertion-Zyklus Tab innerhalb `#sidebar-menu.show` ergänzen. |
| 6 | `reference_scaffold/tests/test_ui_master_shell_browser.py:199` | Nach Menü-Öffnen wird `#sidebar-menu` fokussiert, Spec §6.2.2 verlangt erstes fokussierbares Element (oder Schliessen-Button). Bootstrap-Offcanvas-Verhalten, aber Spec-Abweichung. | minor | Akzeptieren wenn Offcanvas-Container als Fokusziel gilt, oder ersten `.nav-link` prüfen. |
| 7 | — | `docs/design/2026-09-11-admin-shell-navigation-spec.md` fehlt im Worktree; Review stützt sich auf Scratchpad-Export. | minor | Spec-Datei in den Branch nachziehen (Prozess, nicht Funktionsblocker). |

---

## Geprüft und in Ordnung

**1 — Navigation Spec §3.2**  
Fünf Gruppen, Reihenfolge und Labels in `_workflow_sidebar.html:75-105` und `test_ui_master_shell_browser.py:24-30` stimmen überein. Endpunkte existieren (`recipes_list`, `cookbooks_list`, `master_data_list`, `screens`, `vorlagen`, `import_preview`, `api_overview`, `local_users_list`, `branding_editor`, `operations_settings`, `week_management`). Menüs/Komponenten per Pfad (`:78-79`) → `menu_collection` / `components_get`. Rollenbedingungen unverändert: `can_browse_recipes` (`:82-85`), `can_manage_users` (`:98-100`), `can_configure_display` (`:101-104`); System-Gruppe nur Admin (`test_ui_master_shell_browser.py:144-145`). `aria-current="page"` via `nav_link` (`_workflow_sidebar.html:10`).

**2 — Abmelden/Benutzerblock Spec §4**  
POST+CSRF in `_workflow_sidebar.html:116-121`; Rollen-Klartext `:6`, `:113`; kein doppelter Benutzerblock oben; Footer mit Trennlinie `admin-tabler.css:108-109`. Test `test_logout_form_csrf_and_session` (`test_ui_master_shell_browser.py:165-181`).

**3 — Breakpoint 992 (K2-A)**  
`navbar-expand-lg` (`_workflow_sidebar.html:54`); Media Queries `admin-tabler.css:315-328`, `329-342`, `385-391`; Sidebar-Breite über `--app-sidebar-width: 248px` (`tokens.css:172`); `.admin-main{min-width:0}` (`admin-tabler.css:53`); kein 992/991.98 in `tokens.css`. Overlap-Test (`test_ui_master_shell_browser.py:217-230`). Offcanvas Escape/Rückkehr (`:184-203`).

**4 — Layoutvarianten / Seitenkopf**  
`layout_variant|default('standard')` (`base_tabler.html:23-24`); CSS `admin-tabler.css:362-375`; Testvarianten `standard|narrow|workspace` (`test_ui_master_shell_browser.py:239-249`). Kein Topbar. `page_header`-Block nur bei Inhalt (`base_tabler.html:25-26`); leerer Test (`test_ui_master_shell_browser.py:250-252`).

**5 — Tokens / Selektoren**  
Shell-Block ohne neue Hex/`!important`/Inline-Styles; keine Treffer auf `.public-page`/`.print-body`/`.signage-body`. Icons aus Sprite via `icon()`-Makro.

**6 — Besitzgrenzen**  
Ein Commit `c66b93b` auf Basis `25b9557`; sichtbar geändert: `base_tabler.html`, `_workflow_sidebar.html`, `admin-tabler.css` (Shell-Abschnitte), neu `test_ui_master_shell_browser.py`. Token-Block Zeilen 1–51 in `admin-tabler.css` unverändert strukturiert.

**7 — Neue Tests**  
Sechs Tests decken Navigation, Logout, Mobil/Viewports, Layout, Display-Optionen, Tastatur/Kontrast ab (`test_ui_master_shell_browser.py`). API-403 explizit erlaubt (`:160-161`). Fremdtest-Brüche siehe Befunde 2–4.

**8 — Design-Qualität**  
Gruppierte Nav mit Zweizeiler; Zielgrössen ≥44 px (Toggler/Logout ≥48 px, `:192`, `admin-tabler.css:112-113`). Kontrast-Assertions im Test (`test_ui_master_shell_browser.py:315-317`) gegen berechnete Sidebar-Farben.

---

## Nicht geprüft

- Gate-Ausführung (`test_ui_master_shell_browser.py`, Regression-Suite, Ruff, `git diff --check`): `rtk`/Shell in dieser Session blockiert; Autorenbericht `wp-52c02ef0f44d` nicht gefunden.
- Eigener Chromium-Lauf der Browser-Tests (kein DB-Pool in Review-Session).
- Vollständiges `git diff --stat 25b9557..HEAD` (nur Commit-Log gelesen).
- Manuelle visuelle Abnahme gegen `design-reference-0911.md` (Mockup nur beschrieben).
- Fokusfalle nur per Bootstrap-Offcanvas-Default angenommen, nicht per Test belegt.

---

WAVE-REVIEW: FINDINGS(7)
recorded 12546 wp_id=wp-cursor-run-2026-09-11T17:12:53.227445+00:00

[exited with code 0]
