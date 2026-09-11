# Cross-Vendor-Review: Marke und Mastertokens (MP-UI-BRAND-DECISION)

Prüfobjekt: `docs/superpowers/backlog-0909/ui-brand-compatibility-decision.md`  
Worktree: `/nvmetank1/projects/menuplan/.claude/worktrees/ui-brand-decision-codex-0911`  
Branch: `docs/ui-brand-decision-0911`  
Commit: `61935eabec0de132623df1f35ee8d7fc3478e4ad` (Autor: codex gpt-6-astra)  
Basis: `2db9c56563012609c5753047e4ff1ce08b85d9d3`  
Reviewer: Gemini 3.8 Flash (agy, read-only). Keine Repo-Edits.  

Massstab: Master `docs/design/2026-09-09-unified-ui-design-system.md` §§5–10, 12; SDD `docs/superpowers/backlog-0909/surfaces-sdd.md` Abschnitt 4; Auftrag `.claude/ROOT-START.md`.

---

## Befunde

docs/superpowers/backlog-0909/ui-brand-compatibility-decision.md:40 NIEDRIG Quellstellenangabe `admin/display_routes.py:21–51` schneidet die Route `display_settings()` vor dem Template-Rendering ab; Zeilen 21–52 behandeln nur den POST-Redirect bei save/reset (`303, no-store`), während die vollständige Funktion inklusive GET- und Preview-Template-Rendering (`admin/display_settings.html`) bis Zeile 60 reicht. Korrektur: Zeilenbereich auf `admin/display_routes.py:21–60` korrigieren.

docs/superpowers/backlog-0909/ui-brand-compatibility-decision.md:39 NIEDRIG Quellstellenangabe `display_settings.py:19–30,37–72` lässt die abschliessende Ausnahmezeile 73 (`raise PermissionError(...)`) von `_save_admin_display` aus (`display_settings.py` umfasst 73 Zeilen). Korrektur: Zeilenbereich auf `display_settings.py:19–30,37–73` anpassen.

docs/superpowers/backlog-0909/ui-brand-compatibility-decision.md:218 NIEDRIG In Tabelle 2 (Zeilen 217–227) werden für Status-/Alert-Farben `--tblr-*-lt`, `--tblr-*-bg-subtle` und `--tblr-*-text-emphasis` gemappt, aber die in Tabler 1.5.0 für Alert-Rahmen genutzten Variablen `--tblr-*-border-subtle` (z. B. `--tblr-danger-border-subtle`, `--tblr-success-border-subtle`) fehlen in der Zuordnung. Korrektur: `--tblr-*-border-subtle` in Tabelle 2 ergänzen oder dokumentieren, dass Alert-Rahmen unberührt bleiben.

docs/superpowers/backlog-0909/ui-brand-compatibility-decision.md:252 MITTEL In Abschnitt 2.1 (Zeile 252) und Abschnitt 8 (Zeile 823) werden neue Token-Namen `--app-font-body` und `--app-font-heading` vorgeschlagen, jedoch ohne den genauen CSS-Wert oder Fallback-Stack anzugeben (z. B. ob sie direkt `var(--sh-font)` / `var(--sh-font-display)` referenzieren oder den vollständigen Stack `"Fira Sans", Aptos, ...` deklarieren sollen). Korrektur: Den genauen CSS-Zuweisungswert für `--app-font-body` und `--app-font-heading` in der Anschlussliste für MP-UI-TOKENS festlegen (z. B. `--app-font-body: var(--sh-font);`).

docs/superpowers/backlog-0909/ui-brand-compatibility-decision.md:826 MITTEL Die Anschlussliste für MP-UI-TOKENS verlangt in `branding_tokens.py` eine Kontrastprüfung aller §3-Primary-Paare zur Laufzeit vor Ausgabe der Admin-Tokens, spezifiziert aber nicht, welche Kontrastfunktion dafür importiert/genutzt werden soll. Korrektur: Konkretisieren, dass die bestehende Funktion `contrast()` aus `reference_scaffold/cafeteria/branding_config.py:39–45` verwendet werden soll und gegen welche festen Masterflächen (`#FFFFFF`, `#F6F4F1`, `#FAF9F7`, `#F7E8EE`) der Kandidaten-Primary geprüft werden muss.

docs/superpowers/backlog-0909/ui-brand-compatibility-decision.md:244 NIEDRIG In Abschnitt 2.1 wird für Formulare der Zustand `disabled` spezifiziert (`Text-Muted/Surface-Soft`), aber der Zustand `readonly` (der im Gegensatz zu `disabled` Formulardaten per POST übermittelt und in Admin-Formularen wie Token- oder ID-Anzeigen vorkommt) wird in Tabelle 2.1 nicht explizit von `disabled` abgegrenzt. Korrektur: `readonly`-Zustand in Tabelle 2.1 aufnehmen und festlegen, ob er visuell `disabled` folgt oder eine abweichende Kontur/Fläche erhält.

---

## Was hält

1. **Vollständigkeit der Ist-Analyse**: Alle 72 `--sh-*`-Tokens in `tokens.css` sind lückenlos und zeilengenau erfasst (Zeilen 3–106). Reihenfolge in `base_tabler.html:9–14`, Scope `.dishboard-admin` (`base_tabler.html:19`), Tabler-Version 1.5.0 und Icons 3.46.0 (`tabler.lock.json:4–5`), Sidebar-Markup (`_workflow_sidebar.html:34–36,44,52`), selbstgehostete Fira-Fonts (`tokens.css:110–140`) und `branding_config.py:34–36, 56–74` stimmen exakt mit dem Quellcode überein.
2. **Tabler-Vendorprüfung (125 Namen)**: Alle 83 in der Mapping-Tabelle verwendeten `--tblr-*`-Variablen existieren tatsächlich in `reference_scaffold/cafeteria/static/vendor/tabler/tabler.min.css`. Die beiden fehlenden Variablen `--tblr-form-control-focus-border-color` und `--tblr-primary-lt-fg` sind ausdrücklich als nicht existent ("intentionally absent") belegt; es werden keine Vendor-Variablen erfunden.
3. **Mathematisch exakte Kontrastrechnung**: Sämtliche 118 geprüften Farbpaare (59 Master, 59 Brand-Default-Vorschlag) wurden unabhängig per Python nachgerechnet. Sowohl WCAG 2.2 Relative Luminance als auch APCA 0.0.98G-4g stimmen bis auf 4 bzw. 2 Nachkommastellen exakt mit dem Dokument überein (maximale WCAG-Differenz 0.000045, weit unter der Schwelle von 0.05). Alle Werte erfüllen die Schwellen (Text ≥ 4.5:1, Nicht-Text ≥ 3.0:1).
4. **Konflikte K1–K6 und zusätzliche Befunde K7/K8**:
   - K1 (Fira Sans vs Arial/Georgia): Klare Trennung zwischen Empfehlung A und Masterwortlaut B, Verzicht auf Systemschriften fundiert begründet.
   - K2 (Sidebar-Breakpoint 1200 vs 992): Exakte rechnerische Nutzbreite bei 1024 px (728 px bei 24 px Padding bzw. 712 px bei 32 px Inset) nachgewiesen.
   - K3/K4 (Palette & Scope): Admin standardmässig auf Master festgelegt; Marke darf nur Logo und kontrastgeprüftes Primary/RGB steuern. Globale `!important`-Regeln werden über Selektorbegrenzung (z. B. `:where(body:not(.dishboard-admin))`) neutralisiert.
   - K5 (Unbekannte Livemarken): Ehrlich dokumentiert, dass keine Produktionsdaten vorliegen. Saubere Laufzeit-Gate-Spezifikation statt Spekulation.
   - K6 (Mockup-Abgrenzung): Klare Negativliste für fehlende Mockup-Funktionen (Ctrl+K, Archivrouten, dekorative Fotos).
   - K7/K8 (Dichte/Schrift & Haarlinien): Offene Differenzen zu Mastermassen (12px Cardpadding vs 24px) und Master-Minimalschatten sauber als zusätzliche Konflikte herausgearbeitet.
5. **Schutz von Public, Print und TV**: Exakte Datei:Zeile-Belege für `public.css` (2–34, 35–50, 51–63), `app.css` (335–352, 382–393), `base.html:10–17`, `print_cafeteria_week.html:1–9`, `print_patient_week.html:1–9` und `signage.css` (1–9, 13–16, 139–158, 166–185, 195–223). Die Trennung über Selektoren (`.dishboard-admin` vs `.public-page`, `.print-body`, `.signage-body`) verhindert Regressionsschäden.
6. **Darstellungseinstellungen ohne Schemaänderung**: Alle 4 Optionen (`admin_density`, `admin_font_size`, `admin_content_width`, `admin_menu_images`) werden rein über Datenattribute an `.admin-main` und `.display-preview` abgebildet; DB-Speicherung, Formular, CSRF und Validierung bleiben unverändert.
7. **Keine erfundenen Freigaben**: Das Dokument deklariert sich konsequent als Vorschlag (`AWAITING_EXTERNAL`) und fordert explizite Auftraggeberentscheide ein.

---

## Detaillierte Prüfung der 7 Prüfpunkte

### 1. Ist-Befund
- `templates/admin/base_tabler.html:9–14`: Reihenfolge stimmt (tokens.css → tabler.min.css → admin-tabler.css → menu-images.css → page_styles → brand stylesheet).
- `templates/admin/base_tabler.html:19–23`: Body-Klassen `admin-body dishboard-admin` und Datenattribute an `.admin-main` verifiziert.
- `static/vendor/tabler.lock.json:4–5`: `@tabler/core: 1.5.0`, `@tabler/icons: 3.46.0` exakt belegt.
- `templates/admin/_workflow_sidebar.html:34–36,44,52`: Tabler-Aside-Struktur, Navbar-Toggler, No-JS-Nav und Collapse-ID exakt belegt.
- `static/tokens.css:110–140`: Vier `@font-face`-Blöcke für Fira Sans (400, 500, 600, 700) mit `local()` und WOFF2 exakt belegt.
- `branding_config.py:34–36`: `default_config()` mit `primary: #8c1c4b`, `accent: #35666f`, `surface: #ffffff`, `text: #383027` exakt belegt.
- `branding_config.py:9,56–74`: `FONTS`, Hex-Validierung und Kontrastprüfung ≥ 4.5:1 exakt belegt.
- `display_settings.py:8–16`: Choices und Defaults exakt belegt.
- `display_settings.py:19–30,37–72` & `admin/display_routes.py:21–51`: Siehe Befunde 1 und 2 bzgl. Zeilengrenzen 73 und 60.

### 2. Mapping-Tabelle app → tblr
- Vendor-Check: Mittels `rtk grep -c -E -- '--tblr-<name>' reference_scaffold/cafeteria/static/vendor/tabler/tabler.min.css` wurden alle 125 geprüften Bezeichner überprüft. 123 sind nachweisbar vorhanden. Die 2 abwesenden (`--tblr-form-control-focus-border-color`, `--tblr-primary-lt-fg`) sind explizit als abwesend deklariert.
- Zustände: Hover, Active, Focus, Disabled, Invalid sind für Buttons, Links, Formulare, Tabs und Pagination abgedeckt.
- Siehe Befunde 3 und 6 bzgl. `--tblr-*-border-subtle` für Alerts und Formularzustand `readonly`.

### 3. Kontrasttabelle (unabhängige Nachrechnung)
Vergleich von 15 repräsentativen Paaren (WCAG 2.2 Luminance und APCA 0.0.98G-4g Lc):

| Paar | FG / BG | Berechnet WCAG | Dokument WCAG | Diff WCAG | Berechnet APCA | Dokument APCA | Diff APCA |
|---|---|---|---|---|---|---|---|
| text/bg | #1F2937 / #F6F4F1 | 13.3713:1 | 13.3713:1 | 0.00001 | +95.05 | +95.05 | 0.0003 |
| text-muted/bg | #596273 / #F6F4F1 | 5.5943:1 | 5.5943:1 | 0.00005 | +74.23 | +74.23 | 0.0001 |
| sidebar-text/sidebar | #C7D8D9 / #173C3F | 8.1233:1 | 8.1233:1 | 0.00002 | -73.82 | -73.82 | 0.0017 |
| sidebar-label/sidebar | #9AB7BA / #173C3F | 5.6176:1 | 5.6176:1 | 0.00004 | -53.39 | -53.39 | 0.0006 |
| on-primary/sidebar-active | #FFFFFF / #31585B | 7.8430:1 | 7.8430:1 | 0.00001 | -91.86 | -91.86 | 0.0017 |
| on-primary/primary | #FFFFFF / #A3164D | 7.5560:1 | 7.5560:1 | 0.00004 | -89.45 | -89.45 | 0.0030 |
| primary/surface | #A3164D / #FFFFFF | 7.5560:1 | 7.5560:1 | 0.00004 | +84.53 | +84.53 | 0.0033 |
| primary-hover/surface | #8E123F / #FFFFFF | 9.0970:1 | 9.0970:1 | 0.00001 | +89.27 | +89.27 | 0.0031 |
| control-border/surface | #808B99 / #FFFFFF | 3.4591:1 | 3.4591:1 | 0.00004 | +62.15 | +62.15 | 0.0008 |
| focus/surface | #A3164D / #FFFFFF | 7.5560:1 | 7.5560:1 | 0.00004 | +84.53 | +84.53 | 0.0033 |
| sidebar-indicator/sidebar-active | #F3A6C0 / #31585B | 4.1182:1 | 4.1182:1 | 0.00004 | -50.29 | -50.29 | 0.0043 |
| brand-on-primary/primary | #FFFFFF / #8C1C4B | 8.8132:1 | 8.8132:1 | 0.00001 | -93.42 | -93.42 | 0.0037 |
| brand-primary/surface | #8C1C4B / #FFFFFF | 8.8132:1 | 8.8132:1 | 0.00001 | +88.85 | +88.85 | 0.0047 |
| brand-primary-hover/surface | #7B1942 / #FFFFFF | 10.1946:1 | 10.1946:1 | 0.00001 | +92.46 | +92.46 | 0.0009 |
| brand-primary-active/surface | #6A1539 / #FFFFFF | 11.8032:1 | 11.8032:1 | 0.00002 | +95.96 | +95.96 | 0.0001 |

Ergebnis: Maximale Abweichung 0.000045 (WCAG) und 0.0047 (APCA). Keine Abweichung > 0.05. PASS.

### 4. Konflikte K1–K6
- Alle Optionen A/B/(C) sind klar strukturiert und mit Konsequenzen für Admin, Public, Print, TV und Baselines hinterlegt.
- Kein stilles Überschreiben: Public/Print/TV behalten ihre Markenwirkung vollständig.
- Keine erfundene Corporate-Freigabe: Status bleibt AWAITING_EXTERNAL.

### 5. Darstellungseinstellungen
- Abbildung ohne DB-Änderung über reine CSS-Attribute an `.admin-main` und `.display-preview`.
- Bild-Einstellung wird als Jinja-Template-Funktion belassen und nicht fehlerhaft als reines Token deklariert.

### 6. Anschlussliste für MP-UI-TOKENS
- Sehr präzise Aufgabenverteilung für `tokens.css`, `admin-tabler.css` und `branding_tokens.py`.
- Ergänzungsbedarf (Befunde 4 und 5): CSS-Wert der neuen Font-Tokens sowie Import/Nutzung von `contrast()` aus `branding_config.py` präzisieren.

### 7. Widersprüche zum Master oder zum Auftrag
- Keine unbegründeten Abweichungen. K7 (Dichte vs. Master 24px) und K8 (Haarlinien vs. Master-Minimalschatten) sind transparent offengelegt und als Entscheidungsbedarf formuliert.

---

WAVE-REVIEW: FINDINGS (6)
