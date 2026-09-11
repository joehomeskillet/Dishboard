# Cross-Vendor-Review: MP-UI-REF-SETTINGS (wp-0887ae005a92-review)

| Feld | Wert |
|---|---|
| **Branch** | `feat/ui-ref-settings-0911` |
| **HEAD** | `55c39a924e178f23a4c3630b56cbb1f47f029728` |
| **Basis** | `815fb7d0f9e3867c4bc0098c359f838bf81590a0` |
| **Reviewer-Modell** | cursor composer-2.5 |
| **Autor** | antigravity-agy / gemini-3.8-flash-high |
| **Scope** | `reference_scaffold/cafeteria/templates/admin/display_settings.html`, `reference_scaffold/tests/test_ui_reference_settings_browser.py` |

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | `reference_scaffold/cafeteria/templates/admin/display_settings.html:6` | Seitenkopf ohne `description` im `page_header`-Makro. Shell-Spec §7.2 Nr. 4 verlangt für `admin.display_settings` die funktionale Beschreibung «Zentrale Anzeigeoptionen für Abstände, Schriftgrösse, Inhaltsbreite und Menübilder im Administrationsbereich.» im Kopfbereich (nicht nur im Card-Body). Review-Prüfpunkt 3 nennt «Beschreibung» explizit; die Listen-Referenz setzt das bereits mit `description=…` um. | major | `page_header('Design & Marke', description='Zentrale Anzeigeoptionen für Abstände, Schriftgrösse, Inhaltsbreite und Menübilder im Administrationsbereich.', breadcrumbs=[…])` ergänzen; Card-Body-Hinweis zum Geltungsbereich beibehalten. |
| 2 | `reference_scaffold/cafeteria/templates/admin/display_settings.html:28-33` | Beim Reset-Button fehlt `aria-describedby="display-reset-hint"`. In der Basis-Vorlage (`815fb7d`-Stand) war die Verknüpfung zum Hinweistext gesetzt; das `actions`-Makro reicht `aria-describedby` nicht durch. | minor | `actions`-Aufruf um `aria-describedby` am Reset-Item erweitern (falls Makro das unterstützt) oder dokumentierte Makro-Erweiterung beim Macros-Owner anfragen. |
| 3 | `reference_scaffold/tests/test_ui_reference_settings_browser.py:1-336` | Matrix-Zustand `access_denied_401` (`ui-route-matrix.json:1001-1006`) fehlt in der Referenz-Suite; nur `access_denied_403` ist abgedeckt (`:223-236`). Der Autor-Brief listet 401 nicht, Review-Prüfpunkt 5 verweist aber auf die Matrix-Zustände. | minor | `test_settings_unauthenticated_gets_401` ergänzen (analog `test_ui_reference_list_browser.py:335-337`) oder im Bericht begründen, warum 401 ausschliesslich über `test_admin_display_settings.py:94` ausreicht. |

## Geprüft und in Ordnung

- **Fach-/Formvertrag (POST-Felder):** `method="post"`, `action="{{ url_for('admin.display_settings') }}"`, `_csrf`, Feldnamen `admin_density` / `admin_font_size` / `admin_content_width` / `admin_menu_images`, `action`-Werte `save`/`preview`/`reset`, IDs `admin-density` usw., `#display-settings-form`, `#display-reset-hint`, Preview-`data-*`-Attribute unverändert (`display_settings.html:8-41`; Abgleich mit Basis in `tmp-package-export/.../display_settings.html:7-43`). Keine CAS-/Versionstoken auf dieser Route; `display_routes.py` unangetastet.
- **Keine neuen Aktionen/Spalten/Suchen:** Nur die drei bestehenden Submit-Aktionen (`display_settings.html:28-33`).
- **Gefrorene Bausteine:** `layout_variant = 'narrow'` (`:4`), `page_header`/`select`/`field`/`actions`/`form_errors` aus `admin/_macros.html` (`:2-3,12,22,28-34,49`); kein eigenes CSS, keine Hexwerte, kein `!important`, keine Inline-Styles im Template.
- **Layoutvariante Schmal 960:** `data-layout="narrow"` und bei Desktop `max-width: 960px` getestet (`test_ui_reference_settings_browser.py:74-79`; Shell-Spec §8.2 Nr. 13).
- **Seitenkopf H1/Breadcrumb/keine Kopfaktionen:** H1 «Design & Marke», Breadcrumb-Link via `url_for('admin.branding_editor')`, aktiver Knoten «Darstellung», keine Header-`.btn-list` (`display_settings.html:6`; Test `:82-85`).
- **Dominante Primäraktion:** «Darstellung speichern» als `btn-primary` (`display_settings.html:29`; Test `:98-100`).
- **Master §8 Formular/Targets:** 2-spaltig ab `md`, einspaltig unter 768 px (`col-12 col-md-6`); Mindesthöhe ≥44 px und Schrift ≥16 px in Tests (`test_ui_reference_settings_browser.py:53-59,113`).
- **Matrix-Zustände (Autor-Brief):** Normal/5 Viewports, Preview beider Werte je Option, Validierungsfehler mit Eingabeerhalt, 403, NoJS Save/Reset, Tastatur/Fokus, Zoom 200 % — jeweils mit `tmp_path`-Screenshots dokumentiert (Autor-Bericht + Testdatei).
- **Besitz (lesend):** Autor-Bericht und Owned-Liste nennen ausschliesslich die zwei Dateien; keine fremden Template-/Route-Änderungen im Worktree sichtbar.
- **Design-Qualität:** Ruhige Card-Struktur, Primary sparsam, sichtbarer Burgunder-Fokus im Tastaturtest (`test_ui_reference_settings_browser.py:298-315`); keine zusätzlichen Schatten/Icons im Template.

## Nicht geprüft

- **`rtk`-Befehle / Gate-Re-Run:** Shell-Aufrufe (`rtk git …`, `rtk bash worker-test_sdd-gate.sh …`) in dieser Review-Umgebung nicht ausführbar; Gate-Ausgaben nur anhand des Autor-Berichts `wp-0887ae005a92.md` auf Plausibilität gelesen (48 passed, 0 skipped, Ruff clean).
- **`git diff --stat 815fb7d..HEAD`:** nicht unabhängig verifiziert; Besitzgrenze nur über Bericht + Dateilesen abgesichert.
- **Shell-Spec im Worktree:** `docs/design/2026-09-11-admin-shell-navigation-spec.md` fehlt im Worktree; §7.2/§8.2 über Package-Export-Snapshot und Autor-Brief gelesen.
- **Browser/Screenshots/OCR:** Keine Live-Browser- oder Screenshot-Reproduktion; keine visuelle Vorher/Nachher-Sichtung.
- **Matrix-Zustand `empty`:** Für diese Route fachlich nicht eindeutig belegbar; nicht als Testlücke gewertet ohne klaren Empty-Szenario-Contract.

WAVE-REVIEW: FINDINGS(3)
recorded 12559 wp_id=wp-cursor-run-2026-09-11T17:54:34.912066+00:00

[exited with code 0]
