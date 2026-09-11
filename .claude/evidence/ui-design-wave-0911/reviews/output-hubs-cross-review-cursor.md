# Cross-Vendor-Review MP-UI-OUTPUT-HUBS

| Feld | Wert |
|---|---|
| **Branch** | `feat/ui-page-output-hubs-0911` |
| **HEAD** | `db6d40ff3543a8cb599b8aba5693e56ecdb20577` |
| **Basis** | `e7845bf825a413f57956305b610a2f3657f9fead` |
| **Reviewer-Modell** | cursor composer-2.5 |
| **Autor** | agy / gemini-3.8-flash-high |
| **Worktree** | `/nvmetank1/projects/menuplan/.claude/worktrees/ui-page-output-hubs-agy-0911` |

## Befundtabelle

| Nr | Datei:Zeile | Befund | Schwere | Vorschlag |
|---|---|---|---|---|
| 1 | `vorlagen.html:42-66` | R4/KRITIK §3.F verlangt nachgeordneten Bereich **«Drucklayout ändern»** und **«Frühere Versionen»**; stattdessen dominiert weiterhin **«Druckvorlagen»** mit wiederholten **«Revision {{ id }}»**-Beschriftungen und mehreren gleichrangigen Editor-/PDF-Buttons auf der Hauptfläche (`UI_REFERENZEN.md` R4 Punkt 3, `KRITIK_UND_NACHBESSERUNG.md` §3.F). | major | Abschnitt «Drucklayout ändern» einführen; Versionsverlauf unter «Frühere Versionen» kollabieren; sichtbare Hauptaktionen auf Wochen-PDF vs. Layoutbearbeitung trennen; «Revision» nur im Verlauf (Wörterbuch §3.3). |
| 2 | `vorlagen.html:25-88` | R4 Punkt 4 / KRITIK §3.F: Cafeteria und Patienten bleiben als zwei volle parallele `col-md-6`-Verwaltungskarten nebeneinander statt klarer Bereichswahl. | major | Bereichswahl (Tabs/Radio o.ä.) mit einem Kartenkörper; Patienten-/Cafeteria-Inhalt nur für gewählten Bereich rendern — ohne neue Endpunkte. |
| 3 | `test_ui_output_hubs_browser.py:99-334` | Matrix-Zustand **`empty`** für `admin.screens`, `admin.vorlagen`, `admin.screen_template_assignment` (`ui-route-matrix.json`) fehlt im neuen Browser-Test vollständig; Brief-Punkt 5 verlangt alle Matrix-Zustände. | major | Pro Route mindestens einen `empty`-Fixture-Test (Screenshot `tmp_path`, Overflow/Fokus) ergänzen. |
| 4 | `vorlagen.html:19,37` | Wörterbuch/KRITIK N08: sichtbar bleibt **«publiziert»** (`output-week-hint`, `aria-label`), während der Button «Veröffentlichten Plan drucken» heisst — inkonsistente Terminologie. | minor | Beide Stellen auf «veröffentlicht» angleichen; `aria-label` an sichtbaren Buttontext koppeln. |
| 5 | `screens.html:9-11` | `page_header`-Description und folgender `<p>` wiederholen denselben Einleitungstext wortgleich — unnötige visuelle Doppelung, schwächt Hierarchie. | minor | Einleitung nur im `page_header` oder nur im Body belassen. |
| 6 | `vorlagen.html:17,36` | Mehrere **`btn-primary`** auf einer Seite (Wochenwahl + je Bereichskarte PDF-Hauptaktion) — widerspricht «eine dominante Aktion je Kontext» (Master §8 / Brief-Punkt 3). | minor | Nur die jeweils führende Druckaktion als Primary; «Woche anzeigen» sekundär (`btn`). |

## Geprüft und in Ordnung

- **Fach-/Formvertrag Zuordnung:** `_csrf`, `_form_context`, `version`, `renderer_revision`, `action`, Radio `template_id`, `method="post"`, `can_write`/`settings.write`-Schutz unverändert (`screen_template_assignment.html:16-34`; Route `screen_template_routes.py:54-58,96-97`).
- **409/503-Verhalten:** Konflikt behält Formtoken und fokussiert Alert (`test_ui_output_hubs_browser.py:270-294`); 503 nutzt `screen_template_unavailable.html` mit `role="alert"` (`screen_template_unavailable.html:19`; Test `:328-333`).
- **Vorschau vs. Veröffentlichung:** Screens-Iframes `inert`/`aria-hidden`, Hinweistexte und Preview-Endpunkte getrennt (`screens.html:31-37`; `screen_template_assignment.html:33`).
- **Kanonische Varianten:** Wochenplan mit/ohne Bilder, aktive Vorlage, Assignment-Link pro Web-Karte erhalten (`screens.html:17-19,38-39`).
- **Gefrorene Bausteine:** `page_header`, `layout_variant` (`standard`/`narrow`), Makros aus `_macros.html`; keine Hexwerte, kein `!important`, keine Inline-Styles in den Templates (`admin-screens.css` durchgängig `var(--app-…)` / Tabler-Fallbacks).
- **R4-Teilfortschritt:** «Wochenplan drucken» vor «Druckvorlagen»; Primary «PDF der gewählten Woche öffnen» vs. sekundär «Veröffentlichten Plan drucken» (`vorlagen.html:32-38`); Screens-Terminologie «veröffentlicht» statt «publiziert» (`screens.html:9-11,37` vs. Basis `e7845bf`).
- **`screen_template_unavailable.html`:** Card-Layout, Tokens, H1-Vertrag und Alert erhalten/verbessert (Basis hatte flachen `<main>` ohne Card).
- **Layoutvarianten-Tests:** `data-layout` standard/narrow, Breadcrumb, 5 Viewports, JS an/aus, Tastatur ≥48 px, Zoom 200 %, Kontrast (`test_ui_output_hubs_browser.py:99-230`).
- **Gate-Plausibilität «52 passed»:** 8 + 18 + 18 + 8 parametrisierte Tests über die vier Gate-Dateien — arithmetisch stimmig.
- **403/401 screens/vorlagen:** HTTP-Ebene in `test_admin_output_hubs.py:120-129`; neuer Browser-Test deckt 401 und Assignment-403 ab (`test_ui_output_hubs_browser.py:259-317`).

## Nicht geprüft

- **Eigene Gate-Ausführung** (`worker-test-iam25-image-0908-gate.sh`, Ruff, `git diff --check`) — nur Autorbericht `wp-7e17c2562ba1.md` ausgewertet; `rtk git diff`/`git show --stat` im Review-Lauf nicht verfügbar.
- **Unabhängiger `git diff --stat e7845bf..HEAD`** zur Besitzgrenze — Scope stützt sich auf Autor-Commit und Datei-Vergleich per `git cat-file` (nur die sechs Owned-Dateien inhaltlich geprüft).
- **OCR-Review** — Autor: `OCR: failed (429)`.
- **Visuelle Abnahme gegen `soll/R4-druckvorlagen.png`** — nur Text-/Strukturabgleich mit `UI_REFERENZEN.md` / KRITIK.
- **Leer-/Fehlerzustände screens/vorlagen im Browser** ausser 400/401 — nicht im neuen Testfile; teils in `test_admin_output_hubs.py` / `test_admin_template_catalog_browser.py`.

WAVE-REVIEW: FINDINGS(6)
