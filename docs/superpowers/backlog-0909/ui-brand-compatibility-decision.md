# MP-UI-BRAND-DECISION — Marke und Mastertokens

Stand: 11. September 2026. **Entscheidungsvorlage / VORSCHLAG, keine Freigabe.**
MP-ID: MP-UI-BRAND-DECISION; Routing-WP: wp-10e17980d6a1; Lane: codex-gpt5;
Modell: gpt-6-astra. Basis: 2db9c56563012609c5753047e4ff1ce08b85d9d3.
Worktree: /nvmetank1/projects/menuplan/.claude/worktrees/ui-brand-decision-codex-0911;
Branch: docs/ui-brand-decision-0911.

Der [Master](../../design/2026-09-09-unified-ui-design-system.md), insbesondere §§5–10,
bleibt einzige Sollwerttabelle. Dieses Dokument ordnet Werte und Verantwortlichkeiten zu.
Bestandswerte und berechnete Messergebnisse unten sind Belege, keine zweite Sollpalette.
Gelesen: Master vollständig, surfaces-sdd.md §§4–5, START.md, execution-contract.md,
README.md, surfaces-wps.json (dieses MP), ui-route-matrix.json/common und
[Mockup-Einordnung](../../../.claude/evidence/ui-inventory-proof-fix-0909/design-reference-0911.md).

**Abnahmestatus:** Dokumentationsauftrag lieferbar; fachliche Annahme AWAITING_EXTERNAL.
Die WP-Anforderung „konkrete akzeptierte Konfliktentscheidung“ ist ohne Auftraggeberentscheid
noch nicht erfüllt. Keine aktive Marke aus Produktion gelesen. Kein Produktcode geändert.
TOKENS/SHELL dürfen Vorschläge erst nach dokumentiertem Entscheid übernehmen.

## 1. Ist-Befund am benannten Quellstand

Dateikürzel in Tabellen sind Pfade relativ zu reference_scaffold/cafeteria/.
Jeder Datei:Zeile-Beleg bezieht sich auf obige Basis, nicht auf einen laufenden Server.
Scope bezeichnet Quellselektoren; tatsächliche berechnete Styles wurden hier nicht gemessen.

### 1.1 Ladereihenfolge, Versionen, Fonts und Einstellungen

| Quelle | Datei:Zeile | Wert | Wirkung / Scope | Widerspruch zum Master |
|---|---|---|---|---|
| Admin-Assets | templates/admin/base_tabler.html:9–14 | tokens.css → vendor/tabler/tabler.min.css → admin-tabler.css → menu-images.css → page_styles → Branding mit data-brand-stylesheet | body.dishboard-admin, Branding zuletzt und bedingt durch brand | Nein für Reihenfolge; Ja für daraus mögliche Overrides, K4 |
| Admin-Wurzel | templates/admin/base_tabler.html:19–23 | .dishboard-admin auf body; vier data-* auf .admin-main | Admin-Adapter kann vollständig hier begrenzt werden | Nein |
| Vendor-Lock | static/vendor/tabler.lock.json:4–5 | Tabler core 1.5.0; Icons 3.46.0 | Kein Upgrade, kein zweites Bootstrap | Nein; Matrix common.assets bestätigt |
| Sidebar | templates/admin/_workflow_sidebar.html:34–36,44,52 | navbar-expand-xl; data-bs-theme=dark; Collapse; No-JS d-xl-none | .admin-sidebar: Expansion ab 1200 px; Hersteller-lg bleibt 992 px | Ja, Master §10; K2 |
| Lokale Fonts | static/tokens.css:110–140 | Fira Sans 400/500/600/700; local() zuerst, dann vier WOFF2-Dateien, font-display:swap | globale @font-face, keine externe Font-URL | Ja bei Familienwahl; Nein bei lokalem Laden |
| Brand-Standard | branding_config.py:34–36 | logo_sha256=None; font_body=fira; font_heading=fira; primary=#8c1c4b; accent=#35666f; surface=#ffffff; text=#383027 | Konfigurationsdefault, keine ausgelesene aktive Revision | Ja, Schrift/Primary/Accent/Text; Weiss entspricht Master |
| Brand-Allowlist | branding_config.py:9,56–74 | Fira Sans oder Carlito; sechsstellige Hexwerte; Text/Primary/Accent gegen eigene Brand-Surface mindestens 4.5:1 | validate_config; prüft nicht Admin-Masterflächen oder abgeleitete Zustände | Nein als bestehender Speichervertrag; als Admin-Gate unzureichend |
| Vier globale Optionen | display_settings.py:8–16 | compact/comfortable; normal/large; contained/full; show/hide; jeweils erster Wert als Default | Anwendungsglobale Darstellung | Abbildung offen, §6/K7 |
| Lesen/Speichern | display_settings.py:19–30,37–72 | cafeteria.settings, location_id/profile_id NULL; setting_key/setting_value; letzte updated_by/updated_at | Global, kein personenbezogener Browser-Storage; ungültige gelesene Werte fallen auf Defaults | Nein; Speicherung nicht verändern |
| Autorisierung | display_settings.py:55–72; admin/display_routes.py:21–51 | atomarer UPSERT nur für aktiven Admin mit aktueller authz_version; CSRF; genaue Feldmenge; preview/save/reset | GET/POST /design/darstellung; Preview speichert nicht; Save/Reset 303, no-store | Nein; unverändert |
| CSS-Anschluss | admin/display_routes.py:16–18; templates/admin/base_tabler.html:23; templates/admin/display_settings.html:43 | Contextprocessor → data-density/font-size/content-width/menu-images | .admin-main und lokale .display-preview | Ja bei bisheriger Mass-/Schriftabbildung; siehe §6 |
| Bilder | templates/_menu_image.html:2 | admin_menu_images != hide entscheidet serverseitig | Template-Ausgabe; data-menu-images allein ist kein CSS-Schalter | Nein; bestehende Funktion erhalten |

Fontbeleg aus eingefrorenem Inventar, nicht neu gemessen:
.claude/evidence/ui-inventory-proof-fix-0909/capture/ui-before-manifest.json:70–80
nennt Fira Sans als berechnete Familie und Fira Sans SemiBold als gerasterten
CDP-Plattformfont. local() kann je Betriebssystem andere Fontdateien treffen;
das ist kein Beweis identischer Rasterung auf allen Rechnern. TOKENS muss tatsächliche
Referenzfonts erneut protokollieren.

### 1.2 Vollständiger Tokenbestand

static/tokens.css definiert **72 --sh-*, null --app-* und null --tblr-***.
Alle Definitionen stehen in :root: sie vererben Werte, beweisen für sich keine sichtbare Nutzung.
„Ja“ meint Abweichung, wenn diese Legacy-Rolle als entsprechender Adminstandard verwendet wird.
Geschützte Nicht-Admin-Nutzung ist dadurch nicht zum Ändern freigegeben.

| Quelle | Datei:Zeile | Wert | Wirkung / Scope-Selektor | Widerspruch zum Master |
|---|---|---|---|---|
| tokens.css | static/tokens.css:3 | --sh-primary: #8C1C4B | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:4 | --sh-primary-2: #A50044 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:5 | --sh-primary-3: #B0496F | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:6 | --sh-primary-4: #CC82A0 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:7 | --sh-primary-5: #D5A6B9 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:10 | --sh-teal-950: #1A363A | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:11 | --sh-teal-900: #224449 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:12 | --sh-teal-800: #2B545C | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:13 | --sh-teal-700: #35666F | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:14 | --sh-teal-100: #DCEDF0 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:15 | --sh-teal-050: #F1F7F8 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:18 | --sh-secondary: #35666F | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:19 | --sh-secondary-2: #007088 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:20 | --sh-secondary-3: #9BC1C9 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:23 | --sh-magenta: #8C1C4B | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:24 | --sh-magenta-soft: #F6E7EE | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:27 | --sh-green: #3E6B44 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:28 | --sh-green-soft: #EAF0E8 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:31 | --sh-amber: #986500 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:32 | --sh-amber-soft: #fff0c9 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:33 | --sh-amber-ink: #715000 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:36 | --sh-blue: #007088 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:37 | --sh-blue-soft: #DCEDF0 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:40 | --sh-neutral: #383027 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:41 | --sh-neutral-2: #59503F | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:42 | --sh-neutral-3: #747068 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:43 | --sh-neutral-4: #B7B3AA | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:44 | --sh-neutral-5: #D5D1CB | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:47 | --sh-canvas: #F8F8F7 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:48 | --sh-canvas-strong: #EFEDE9 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:49 | --sh-panel: #ffffff | :root; weisse Fläche/Vordergrund | Nein, entspricht Surface/On-Primary |
| tokens.css | static/tokens.css:50 | --sh-panel-soft: #FBFAF8 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:51 | --sh-panel-quiet: #F8F8F7 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:54 | --sh-border: #D5D1CB | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:55 | --sh-border-warm: #e7ce86 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:56 | --sh-ink: #383027 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:57 | --sh-ink-muted: #747068 | :root; Legacy-Farbrolle; konkrete Admin-Verwendungen unten | Ja, als entsprechende Admin-Farbrolle; §5.1/K3 |
| tokens.css | static/tokens.css:58 | --sh-white: #ffffff | :root; weisse Fläche/Vordergrund | Nein, entspricht Surface/On-Primary |
| tokens.css | static/tokens.css:61 | --sh-signage-start: #1A363A | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:62 | --sh-signage-middle: #224449 | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:63 | --sh-signage-end: #2B545C | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:66 | --sh-status: #62d996 | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:69 | --sh-shadow: 0 2px 10px rgba(56, 48, 39, .06), 0 3px 14px rgba(56, 48, 39, .07) | :root; Schatten/Alphaeffekt | Ja, falls im Admin benutzt; §5.2/§8 und K8 |
| tokens.css | static/tokens.css:70 | --sh-shadow-soft: 0 2px 10px rgba(56, 48, 39, .06) | :root; Schatten/Alphaeffekt | Ja, falls im Admin benutzt; §5.2/§8 und K8 |
| tokens.css | static/tokens.css:73 | --sh-tap-highlight: rgba(194, 11, 97, .18) | :root; Schatten/Alphaeffekt | Ja, falls im Admin benutzt; §5.2/§8 und K8 |
| tokens.css | static/tokens.css:74 | --sh-white-062: rgba(255, 255, 255, .62) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:75 | --sh-white-070: rgba(255, 255, 255, .7) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:76 | --sh-white-072: rgba(255, 255, 255, .72) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:77 | --sh-white-075: rgba(255, 255, 255, .75) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:78 | --sh-white-076: rgba(255, 255, 255, .76) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:79 | --sh-white-078: rgba(255, 255, 255, .78) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:80 | --sh-white-096: rgba(255, 255, 255, .96) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:81 | --sh-white-098: rgba(255, 255, 255, .98) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:82 | --sh-white-0985: rgba(255, 255, 255, .985) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:83 | --sh-white-border-024: rgba(255, 255, 255, .24) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:84 | --sh-white-border-034: rgba(255, 255, 255, .34) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:85 | --sh-white-surface-008: rgba(255, 255, 255, .08) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:86 | --sh-white-surface-012: rgba(255, 255, 255, .12) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:87 | --sh-white-surface-014: rgba(255, 255, 255, .14) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:88 | --sh-primary-glow: rgba(194, 11, 97, .38) | :root; Schatten/Alphaeffekt | Ja, falls im Admin benutzt; §5.2/§8 und K8 |
| tokens.css | static/tokens.css:89 | --sh-primary-badge: rgba(194, 11, 97, .72) | :root; Schatten/Alphaeffekt | Ja, falls im Admin benutzt; §5.2/§8 und K8 |
| tokens.css | static/tokens.css:90 | --sh-status-glow: rgba(98, 217, 150, .16) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:91 | --sh-logo-shadow: rgba(0, 0, 0, .1) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:92 | --sh-card-shadow: rgba(0, 0, 0, .16) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:93 | --sh-card-shadow-strong: rgba(0, 0, 0, .18) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:94 | --sh-card-shadow-heavy: rgba(0, 0, 0, .2) | :root; Spezial-/Alphawert; Public/TV-Verbrauch geschützt | Nein, keine gleichnamige Mastervorgabe; kein Admin-Sollwert |
| tokens.css | static/tokens.css:97 | --sh-focus: 0 0 0 3px var(--sh-panel), 0 0 0 6px var(--sh-primary) | :root; zusammengesetzter Fokusschatten | Ja, andere Geometrie; zentraler Admin-Outline nötig |
| tokens.css | static/tokens.css:100 | --sh-radius-sm: 6px | :root; gemeinsame Kanten | Ja, §5.2 |
| tokens.css | static/tokens.css:101 | --sh-radius-md: 10px | :root; gemeinsame Kanten | Ja, §5.2 |
| tokens.css | static/tokens.css:102 | --sh-radius-lg: 16px | :root; gemeinsame Kanten | Ja, §5.2 |
| tokens.css | static/tokens.css:105 | --sh-font: "Fira Sans", Aptos, "Segoe UI Variable", "Segoe UI", ui-sans-serif, sans-serif | :root; UI-/Heading-Schrift | Ja, §5.2; K1 |
| tokens.css | static/tokens.css:106 | --sh-font-display: "Fira Sans", Aptos, "Segoe UI Variable Display", "Segoe UI", ui-sans-serif, sans-serif | :root; UI-/Heading-Schrift | Ja, §5.2; K1 |

### 1.3 Gesamter vorhandener Admin-Adapter

| Quelle | Datei:Zeile | Wert / Override | Wirkung / Scope | Widerspruch zum Master |
|---|---|---|---|---|
| Font/Body | static/admin-tabler.css:2–7,18–19 | --tblr-font-sans-serif/--tblr-body-font-family=--sh-font; --tblr-body-font-size=1rem; direkte 16px; --tblr-body-color=--sh-ink; --tblr-secondary=--sh-ink-muted; Hintergrund --sh-canvas-strong | .dishboard-admin | Ja: K1/K3, direkte px statt skalierbarer Schrift |
| Primary | static/admin-tabler.css:8–15 | --tblr-primary=--sh-primary; --tblr-primary-rgb=140,28,75 konstant; --tblr-primary-fg=--sh-white; --tblr-primary-lt=--sh-magenta-soft; --tblr-primary-lt-fg=--sh-primary; --tblr-primary-darken=--sh-primary-2 | .dishboard-admin | Ja: fehlende RGB-Synchronität bei Custombrand; lt-fg hat keinen Vendor-Verbrauch |
| Links/Radien | static/admin-tabler.css:13–17 | Link --sh-primary, Hover --sh-teal-950; --tblr-border-radius=--sh-radius-sm, lg=--sh-radius-md | .dishboard-admin | Ja: Hover petrol; Radien nicht Master |
| Hauptbereich/Sidebar | static/admin-tabler.css:21–22 | min-width:0; --tblr-navbar-bg=--sh-teal-950, border=--sh-teal-900 | .admin-main / .admin-sidebar | Nein für min-width; Ja für Farben |
| Logo/Benutzer | static/admin-tabler.css:23–34 | Logo 164×32; weisse Brandfläche; 8px Gap; Benutzerpadding 16px; Umbruch erlaubt | .admin-brand/.admin-logo/.admin-user/.nav-link-title | Kein pauschaler Konflikt; Original-Logo und Umbruch erhalten |
| Ziele/Text | static/admin-tabler.css:35–38 | Controls/Nav/Page-Link/Form-Check mindestens 48px; Schrift 16px; Toggler mindestens 48px | Admin-Nachfahren | Nein für grössere Ziele: SDD verbietet künstliche Verkleinerung; Schriftrollen an Master anschliessen |
| Buttonzustände | static/admin-tabler.css:40–44 | Hover/Active-BG und Border beide --sh-primary-2; Focus-Box-Shadow 2px Panel + 4px Primary | .btn-primary | Ja: Hover/Active nicht getrennt, kein Master-Focus-Token |
| Listen/Checkboxen | static/admin-tabler.css:45–50 | 8px Gaps; Page-Link inline-flex; Form-Check flex, kein linker Float | .btn-list/.pagination/.nav-pills/.navbar-nav/.form-check | Nein, funktionale Anordnung erhalten |
| Cards/Metadaten | static/admin-tabler.css:51–56 | Cardpadding 16px; Titel 1.125rem; Badgeumbruch; Label 4px/8px mit kleinem Radius | .card-body/.card-title/.badge/[data-menu-metadata] | Ja: Desktop-Masse/Titel/Status-Pill weichen ab; Umbruch erhalten |
| Fokus/Skip | static/admin-tabler.css:57–60 | 2px Primary-Outline, 2px Offset; Sidebar weiss; Skip-Link wird per Fokus eingeblendet | interaktive Admin-Nachfahren | Nein für Grundfunktion; Farbe künftig --app-focus |
| Responsive | static/admin-tabler.css:61–72 | ab 1200 Nav-Spaltenlayout, Logout unten, Cardpadding24; bis1199.98 Navigationpadding12/16, Brandtext verborgen | Admin-Shell | Ja: K2; nicht nur HTML-Klasse ändern |
| Compact | static/admin-tabler.css:73 | Cardpadding12 | [data-density=compact] .card-body | Ja: Master Cardpadding; K7 |
| Schriftoption | static/admin-tabler.css:75–84 | large: --admin-text-size=1.125rem, --admin-title-size=1.375rem; Preview-normal 1rem/1.125rem; viele Rollen vereinheitlicht | .admin-main/.display-preview mit data-font-size | Ja: Cardtitel/Labels/Hinweise verlieren Master-Hierarchie; K7 |
| Breitenoption | static/admin-tabler.css:85–87 | full entfernt Container-Maximum; contained Preview maximal48rem | .admin-main[data-content-width=full], .display-preview | Ja: keine durchgängige 1440/960/Arbeitsfläche-Abbildung |
| Preview-Dichte | static/admin-tabler.css:88–91 | comfortable16, ab1200 comfortable24 | .display-preview | Ja: soll dieselben künftig freigegebenen Tokens wie Hauptansicht benutzen |

### 1.4 Jede Regel aus branding_css und vorgelagerte Ableitung

| Quelle | Datei:Zeile | Wert / Regel | Wirkung / Scope | Widerspruch zum Master |
|---|---|---|---|---|
| Fonts | branding_tokens.py:69–74 | zwei @font-face Carlito, 400/700, lokale WOFF-Dateien | globale Fontregistrierung | Nein für Abruf; K1 entscheidet Admin-Familie |
| Deklarationen | branding_tokens.py:68,74 | alle brand_tokens(config)-Werte in :root | global vererbte --sh-*/--brand-* | Ja, wenn Admin keine eigene Grenze hat |
| Logo | branding_tokens.py:75 | object-fit:contain; max-width:100% | .brand-logo | Nein; erhalten |
| Überschriften | branding_tokens.py:76–77 | font-family:var(--sh-font-display) | .dishboard-admin h1/h2/h3 und .public-page h1/h2/h3 | Ja im Admin; Public schützen |
| Primary-FG | branding_tokens.py:78 | --tblr-primary-fg=--brand-on-primary mit --sh-white-Fallback | .dishboard-admin,.public-page,.signage-body | Ja im Admin: eigene Brand-Surface ist nicht festes --app-on-primary |
| Text/Form/Flächen | branding_tokens.py:79–81 | --tblr-heading-color=--sh-ink; --tblr-bg-forms=--sh-panel; --tblr-body-bg=--sh-canvas; --tblr-bg-surface=--sh-panel; secondary/tertiary=--sh-panel-soft | dieselben drei Scopes | Ja im Admin: schützt Masterflächen nicht |
| Sidebar | branding_tokens.py:82 | --tblr-navbar-bg=--brand-sidebar mit --sh-teal-950-Fallback | .dishboard-admin .admin-sidebar | Ja: aktive Marke färbt Sidebar |
| Erzwungener FG | branding_tokens.py:83 | color:var(--brand-on-primary,var(--sh-white)) !important | .bg-primary.text-white,.btn-primary, global | Ja im Admin; kann lokale Buttonzustände überstimmen |
| Aktive Liste | branding_tokens.py:84 | background=--sh-primary; color=--brand-on-primary/--sh-white | .list-group-item.active, global | Ja im Admin; lokale Komponentenquelle erforderlich |
| Listenbadge | branding_tokens.py:85 | color:inherit | .list-group-item.active .badge, global | Nein allein; abhängig von aktivem Listen-FG |
| Tabs | branding_tokens.py:86 | color=--sh-primary | .dishboard-admin .nav-tabs .nav-link | Ja: kein getrenntes Disabled-/Active-/Hover-Mapping |
| Datei-Button | branding_tokens.py:87 | color=--sh-ink; background=--sh-panel-soft | .dishboard-admin .form-control::file-selector-button | Ja: Marke überschreibt Adminwerte |

brand_tokens ist ebenfalls relevant: branding_tokens.py:16–18 setzt immer beide Fonts.
Zeilen20–27 leiten bei abweichendem Primary zunächst dunklere und hellere Abstufungen ab;
29–36 bauen bei abweichendem Accent Teal-/Signagewerte; 37–41 betreffen Surface/Text.
**Zeilen42–63 überschreiben bei irgendeiner Palettenabweichung viele dieser Werte erneut:**
Primary, Primary-2 und Primary-3 werden identisch; Text und Muted identisch; Panels/Canvas
gleich Brand-Surface; Teal-950/900/800/700 gleich Accent. --brand-on-primary ist Surface,
--brand-sidebar ist Accent um85% nach Schwarz gemischt. Grün wird gegen Brand-Surface
geprüft; weitere Signage-/Weiss-/Glowwerte entstehen hier. Daher beweist die erste
_blend-Ableitung keinen heutigen Hoverkontrast. Bei völligem Default werden primär Fonts
geliefert, viele Farben bleiben aus tokens.css. Diese Sonderbehandlung darf den künftigen
Admin-Renderer nicht davon abhalten, auch Default-Primary explizit zu prüfen und abzubilden.

## 2. Vorschlag: vollständiges app → tblr-Mapping

Alle 35 Farbtoken des Masters sind unten zugeordnet. Tokenwerte ausschliesslich aus Master §5.1.
Definitionen in **tokens.css unter .dishboard-admin**, Zuweisungen an Tabler und direkte
Komponentenregeln in **admin-tabler.css nach Vendor-CSS**. Legacy-:root und globale
Public-/Print-/TV-Brandtokens bleiben erhalten. Kein Vendorwrite, keine neue Palette.

In dieser Tabelle bedeutet A=admin-tabler.css, T=tokens.css (Definition). Jede Tabellenzeile
hat T als Definitionsort und A als Verbrauchsort. Auch direkte Eigenschaften sind explizite
Verbraucher; fehlende Vendorvariablen werden nicht erfunden.

| Mastertoken | Ziel / direkte Eigenschaft in A | Scope unter .dishboard-admin | Zustände | RGB-Kanäle |
|---|---|---|---|---|
| --app-bg | --tblr-body-bg; background-color | Adminwurzel | normal | --tblr-body-bg-rgb aus Token ableiten, falls RGB-Verbrauch |
| --app-surface | --tblr-bg-surface; --tblr-bg-forms; --tblr-card-bg; --tblr-pagination-bg | Wurzel; .card; .pagination; Formfelder | normal | nein |
| --app-surface-soft | --tblr-bg-surface-secondary/tertiary; --tblr-bg-forms-disabled; --tblr-pagination-disabled-bg; --tblr-btn-disabled-bg nur neutrale Buttons | Wurzel, Formfelder, .pagination | normal/disabled | nein |
| --app-sidebar | --tblr-navbar-bg; background-color | .admin-sidebar | normal | nein |
| --app-sidebar-hover | --tblr-nav-link-hover-bg; background-color | .admin-sidebar .navbar-nav; .nav-link:hover | hover/focus-visible | nein |
| --app-sidebar-active | --tblr-navbar-active-bg; --tblr-nav-active-bg; background-color | .admin-sidebar; aktive .nav-link | active/aria-current | nein |
| --app-sidebar-text | --tblr-navbar-color/hover-color; --tblr-nav-link-color/hover-color | .admin-sidebar und .navbar-nav | normal/hover | nein |
| --app-sidebar-label | color | vorhandene Gruppentitel und sekundäre Sidebartexte | normal | nein |
| --app-sidebar-indicator | --tblr-navbar-active-border-color; ::before/background; outline-color | aktive Navigation; Sidebar :focus-visible | active/focus | nein |
| --app-primary | --tblr-primary; --tblr-link-color; --tblr-primary-text-emphasis; --tblr-nav-tabs-link-active-color; --tblr-pagination-color/active-bg/active-border-color; --tblr-btn-bg/border-color | Wurzel; .btn-primary; .nav-tabs; .pagination | normal/active | ja, --app-primary-rgb; Link-RGB synchron |
| --app-primary-rgb | --tblr-primary-rgb; --tblr-link-color-rgb | Wurzel; lokale Color-Utilities mit Komponentenüberschreibung abgleichen | normal/abgeleitete Utility-Opacity | **Kanäle**, kein Hex und kein rgb()-Wrapper |
| --app-primary-hover | --tblr-primary-darken; --tblr-link-hover-color; --tblr-btn-hover-bg/border-color; --tblr-nav-link-hover-color; --tblr-pagination-hover-color/focus-color | Wurzel, .btn-primary, .nav-tabs, .pagination | hover/focus | --tblr-link-hover-color-rgb aus effektivem Hover ableiten |
| --app-primary-active | --tblr-btn-active-bg/border-color; direkte Linkfarbe :active | .btn-primary; Links ausserhalb Sidebar | active/pressed | nein, solange kein aktiver RGB-Verbrauch |
| --app-primary-soft | --tblr-primary-lt; --tblr-primary-bg-subtle; --tblr-active-bg; --tblr-nav-tabs-link-active-bg; --tblr-pagination-hover-bg/focus-bg | Wurzel; .nav-tabs; .pagination; Auswahlflächen | selected/hover/focus | --tblr-primary-lt-rgb aus genau diesem Token ableiten |
| --app-on-primary | --tblr-primary-fg; --tblr-btn-color/hover-color/active-color/disabled-color; --tblr-pagination-active-color; --tblr-navbar-active-color | .btn-primary; .pagination; aktive Sidebar-Links direkt color gemäss Master §7 | normal/hover/active/disabled | nein |
| --app-text | --tblr-body-color; --tblr-heading-color; --tblr-table-color; color | Wurzel; .table; neutrale Buttons | normal | --tblr-body-color-rgb aus Token ableiten |
| --app-text-muted | --tblr-secondary; --tblr-tertiary; --tblr-disabled-color; --tblr-nav-link-disabled-color; --tblr-pagination-disabled-color | Wurzel; Hinweise; .nav-tabs; .pagination | normal/disabled | --tblr-secondary-rgb aus Muted ableiten, damit .text-secondary stimmt |
| --app-border | --tblr-border-color/translucent; --tblr-card-border-color; --tblr-table-border-color; --tblr-nav-tabs-border-color; --tblr-pagination-border-color | Wurzel; Cards/Tabellen/Tabs/Pagination | dekorativ normal | nein; nicht als notwendige Feldkontur |
| --app-border-soft | border-color / border-block-color | dekorative Card-Innenteiler, nicht Controls | normal | nein |
| --app-control-border | --tblr-border-color und --tblr-border-color-translucent **lokal am Feld**; border-color | .form-control/.form-select/.form-check-input; erforderliche neutrale Buttonkontur | normal/hover; disabled soweit Kontur erhalten | nein |
| --app-focus | --tblr-focus-ring-color; --tblr-btn-focus-box-shadow; --tblr-pagination-focus-box-shadow; outline-color und Form-focus border-color | interaktive Admin-Elemente auf hellen Flächen | focus/focus-visible | nein; voller Ring, keine ungeprüfte Alphaabschwächung |
| --app-success | --tblr-success | Wurzel; nicht allein informativer Akzent | normal | nein ohne RGB-Utility; sonst explizit ableiten |
| --app-success-text | --tblr-success-text-emphasis; --tblr-form-valid-color/border-color; color | Erfolgsbadge/Alert, validiertes Feld | normal/valid | nein |
| --app-success-soft | --tblr-success-lt; --tblr-success-bg-subtle; background-color | Erfolgsbadge/Alert | normal | --tblr-success-lt-rgb bei .bg-success-lt anbinden |
| --app-warning | --tblr-warning | Wurzel; dekorativer Akzent | normal | nein ohne RGB-Utility |
| --app-warning-text | --tblr-warning-text-emphasis; color | Warnbadge/Alert | normal | nein |
| --app-warning-soft | --tblr-warning-lt; --tblr-warning-bg-subtle; background-color | Warnbadge/Alert | normal | --tblr-warning-lt-rgb bei entsprechender Utility |
| --app-danger | --tblr-danger nur als Akzent, nicht Buttonfläche | Wurzel; dekorativer Akzent | normal | nein ohne RGB-Utility |
| --app-danger-text | --tblr-danger-text-emphasis; --tblr-form-invalid-color/border-color; --tblr-btn-bg/hover-bg/active-bg für .btn-danger; color/border-color | Fehlerbadge/Alert/Feld, destruktiver Button | invalid/normal/hover/active | nein |
| --app-danger-soft | --tblr-danger-lt; --tblr-danger-bg-subtle; background-color | Fehlerbadge/Alert | invalid/normal | --tblr-danger-lt-rgb bei entsprechender Utility |
| --app-info | --tblr-info | Wurzel; dekorativer Akzent | normal | nein ohne RGB-Utility |
| --app-info-text | --tblr-info-text-emphasis; color | Infobadge/Alert | normal | nein |
| --app-info-soft | --tblr-info-lt; --tblr-info-bg-subtle; background-color | Infobadge/Alert | normal | --tblr-info-lt-rgb bei entsprechender Utility |
| --app-neutral-text | color; --tblr-btn-color für neutrale Sekundäraktion bei passender Fläche | neutraler Status / Sekundäraktion | normal/disabled | nein |
| --app-neutral-soft | background-color | neutraler Status | normal | nein |

Slashnotation bündelt vollständige --tblr-Namen mit gleichem Präfix, nicht eine neue Variable.
RGB-Geschwister sind aus ihrem jeweiligen Farbtoken abzuleiten: Primary-LT ist Primary-Soft,
Secondary-RGB ist Text-Muted. RGB nie aus früherem Default hardcoden. Auch lokale
[data-bs-theme=dark]-Definitionen in Sidebar gegen Vererbung prüfen; dort Navbar- und
Navwerte am tatsächlichen Consumer setzen.

### 2.1 Komponenten-Zustände und Typografie

| Consumer / Datei A, Scope .dishboard-admin | Vollständiger Zustandsanschluss |
|---|---|
| .btn-primary | --tblr-btn-bg/border-color=Primary; --tblr-btn-color=On-Primary; hover/active jeweils eigene Mastertoken; beide FG=On-Primary. Disabled-bg=Primary, disabled-color=On-Primary, disabled-border-color=Primary. --tblr-btn-disabled-opacity ausdrücklich prüfen; für lesbares Projekt-Disabled 1 vorschlagen, echte disabled-Semantik erhalten. Fokus voller --app-focus-Ring, Abstandsring Surface. |
| .btn-outline-primary / .btn-ghost-primary | Normal Primary auf Surface; Hover/Active gefüllt mit jeweiligen Zustandstoken + On-Primary; Disabled und Pressed explizit. Keine globale .btn-Farbe, die Varianten ungewollt füllt. |
| .btn-danger | Danger-Text mit On-Primary auch hover/active; voller Focus-Ring. Kein helles --app-danger als ungeprüfte Textbuttonfläche. |
| .form-control, .form-select, .form-check-input | Normal Text/Surface und Control-Border. Hover bleibt kontrastierend; :focus ersetzt Vendor-Festfarbe und ungeprüften Alpha-Schatten. Checkbox checked=Primary, geprüftes weisses Häkchen; indeterminate ebenso. Disabled Text-Muted/Surface-Soft, keine semantischen Änderungen. |
| .is-invalid, [aria-invalid=true], .was-validated :invalid | Text-/Borderfarbe Danger-Text, Feldinhalt weiter Text; Surface/Surface-Soft. Fehler und Fokus gleichzeitig unterscheidbar. Vorhandene Vendor-SVG-Fehlersymbole prüfen: feste SVG-Farben folgen keinem CSS-Token automatisch. Valid entsprechend Success-Text. |
| .form-control::file-selector-button | direkte Eigenschaften Text/Surface-Soft/Control-Border und Hover/Focus aus gemeinsamen Tokens; spätes Brand-Override entfällt. Keine erfundene --tblr-form-control-focus-border-color. |
| .nav-tabs und .nav-tabs .nav-link | normal Text; hover Primary-Hover; active Primary auf Primary-Soft plus 2px Unterlinie. --tblr-nav-tabs-link-active-color/bg/border-color und --tblr-nav-link-color/hover-color/disabled-color am Consumer. Tabler ergänzt weitere .card-header-tabs-Regeln: active-Farbe, Fläche und Unterlinie bei dieser Variante direkt prüfen/überschreiben. Fokus --app-focus; disabled Text-Muted, keine aktive Interaktion. |
| .pagination | --tblr-pagination-color/bg/border-color normal; hover-color/bg/border-color; focus-color/bg/focus-box-shadow; active-color/bg/border-color; disabled-color/bg/border-color sämtlich explizit. Aktiv On-Primary auf Primary, Hover Primary-Hover auf Primary-Soft. |
| .admin-sidebar .nav-link | normal Sidebar-Text, Hoverfläche Sidebar-Hover, aktive Fläche Sidebar-Active und **weisser Text gemäss §7** (On-Primary als weisser Alias), Gewicht700; 3px Indicator. Label bleibt Sidebar-Label. Fokus helle Indicator-Outline statt Burgunder auf Petrol. |
| Links/Utilities/Listen | --tblr-link-color-rgb und hover-color-rgb mappen, damit Tabler-rgba-Verbrauch folgt; .text-primary/.bg-primary/.bg-*-lt auf echte Ausgabe prüfen. Aktive .list-group-item lokal Farbe/Fläche/Border anbinden; --tblr-list-group-active-color/bg/border-color existieren. |
| Status | dunkles *-text auf *-soft, Icon und realer Statustext; alte .bg-green/.text-green nicht pauschal als Success gelten lassen. Kein --tblr-*-lt-fg-Vertrag erfinden; tatsächliche color/background-Consumer setzen. |
| Schriftfamilien | Vorschlag K1: zentraler --app-font-body/--app-font-heading in T, beide bestehender Fira-Stack. A: --tblr-font-sans-serif, --tblr-body-font-family, --tblr-btn-font-family; direkte h1/h2/h3/.card-title-Familie. Diese zwei neuen Tokenbezeichnungen referenzieren K1, keine neue Farbpalette. |
| Schriftrollen | Zentrale Mass-/Typotoken in T nach Master §5.2, Verbrauch in A. hero alias h1 (Master definiert keine zusätzliche Hero-Grösse), h2=Card-/Bereichstitel, body und small gemäss Master. --tblr-font-size-h1/h2, --tblr-body-font-size/line-height, --tblr-btn-font-size sowie direkte Labels/Tabellen/Formen anbinden; Herstellerselektoren können Rootwerte übersteuern. |
| Geometrie | --tblr-sidebar-width, --tblr-border-radius, --tblr-card-border-radius, --tblr-btn-border-radius, --tblr-nav-pills-border-radius, --tblr-pagination-border-radius und --tblr-shadow-card in A an zentrale §5.2-Tokens anschliessen; Fokus/Outline direkt. Keine Verkleinerung existierender 48px-Ziele. |

### 2.2 Vendor-Nachweis, ausschliesslich grep

Vendor: static/vendor/tabler/tabler.min.css, minifizierte Deklarationen/Verbraucher.
Die Datei wurde nur mit rtk grep abgefragt. Für jeden unten ausgeschriebenen Namen lief:

```text
rtk grep -c -E -- '--tblr-NAME([:),; ]|$)' reference_scaffold/cafeteria/static/vendor/tabler/tabler.min.css
```

-c zählt **Zeilen**, nicht Vorkommen. Name mit Ausgabe1/Exit0 ist belegt; Ausgabe0/Exit1 ist
ein regulärer Nichttreffer. Vorkommen allein beweist noch keine wirksame Vererbung.
Grep-Extrakte zeigen insbesondere feste blaue border-color in .form-control:focus und
.form-select:focus sowie zusätzliche aktive .card-header-tabs-Regeln. Deshalb direkte
Scoped-Regeln plus Browserbeweis, keine Scheinsicherheit durch Rootvariablen.

```text
name | grep stdout | exit
--tblr-active-bg | 1 | 0
--tblr-bg-forms | 1 | 0
--tblr-bg-forms-disabled | 1 | 0
--tblr-bg-surface | 1 | 0
--tblr-bg-surface-secondary | 1 | 0
--tblr-bg-surface-tertiary | 1 | 0
--tblr-body-bg | 1 | 0
--tblr-body-bg-rgb | 1 | 0
--tblr-body-color | 1 | 0
--tblr-body-color-rgb | 1 | 0
--tblr-body-font-family | 1 | 0
--tblr-body-font-size | 1 | 0
--tblr-body-line-height | 1 | 0
--tblr-border-color | 1 | 0
--tblr-border-color-translucent | 1 | 0
--tblr-border-radius | 1 | 0
--tblr-border-radius-lg | 1 | 0
--tblr-btn-active-bg | 1 | 0
--tblr-btn-active-border-color | 1 | 0
--tblr-btn-active-color | 1 | 0
--tblr-btn-bg | 1 | 0
--tblr-btn-border-color | 1 | 0
--tblr-btn-border-radius | 1 | 0
--tblr-btn-color | 1 | 0
--tblr-btn-disabled-bg | 1 | 0
--tblr-btn-disabled-border-color | 1 | 0
--tblr-btn-disabled-color | 1 | 0
--tblr-btn-disabled-opacity | 1 | 0
--tblr-btn-focus-box-shadow | 1 | 0
--tblr-btn-font-family | 1 | 0
--tblr-btn-font-size | 1 | 0
--tblr-btn-hover-bg | 1 | 0
--tblr-btn-hover-border-color | 1 | 0
--tblr-btn-hover-color | 1 | 0
--tblr-card-bg | 1 | 0
--tblr-card-border-color | 1 | 0
--tblr-card-border-radius | 1 | 0
--tblr-danger | 1 | 0
--tblr-danger-bg-subtle | 1 | 0
--tblr-danger-lt | 1 | 0
--tblr-danger-lt-rgb | 1 | 0
--tblr-danger-text-emphasis | 1 | 0
--tblr-disabled-color | 1 | 0
--tblr-focus-ring-color | 1 | 0
--tblr-font-sans-serif | 1 | 0
--tblr-font-size-h1 | 1 | 0
--tblr-font-size-h2 | 1 | 0
--tblr-form-control-focus-border-color | 0 | 1
--tblr-form-invalid-border-color | 1 | 0
--tblr-form-invalid-color | 1 | 0
--tblr-form-valid-border-color | 1 | 0
--tblr-form-valid-color | 1 | 0
--tblr-heading-color | 1 | 0
--tblr-info | 1 | 0
--tblr-info-bg-subtle | 1 | 0
--tblr-info-lt | 1 | 0
--tblr-info-lt-rgb | 1 | 0
--tblr-info-text-emphasis | 1 | 0
--tblr-link-color | 1 | 0
--tblr-link-color-rgb | 1 | 0
--tblr-link-hover-color | 1 | 0
--tblr-link-hover-color-rgb | 1 | 0
--tblr-list-group-active-bg | 1 | 0
--tblr-list-group-active-border-color | 1 | 0
--tblr-list-group-active-color | 1 | 0
--tblr-nav-active-bg | 1 | 0
--tblr-nav-link-color | 1 | 0
--tblr-nav-link-disabled-color | 1 | 0
--tblr-nav-link-hover-bg | 1 | 0
--tblr-nav-link-hover-color | 1 | 0
--tblr-nav-pills-border-radius | 1 | 0
--tblr-nav-tabs-border-color | 1 | 0
--tblr-nav-tabs-link-active-bg | 1 | 0
--tblr-nav-tabs-link-active-border-color | 1 | 0
--tblr-nav-tabs-link-active-color | 1 | 0
--tblr-nav-tabs-link-hover-border-color | 1 | 0
--tblr-navbar-active-bg | 1 | 0
--tblr-navbar-active-border-color | 1 | 0
--tblr-navbar-active-color | 1 | 0
--tblr-navbar-bg | 1 | 0
--tblr-navbar-border-color | 1 | 0
--tblr-navbar-color | 1 | 0
--tblr-navbar-hover-color | 1 | 0
--tblr-pagination-active-bg | 1 | 0
--tblr-pagination-active-border-color | 1 | 0
--tblr-pagination-active-color | 1 | 0
--tblr-pagination-bg | 1 | 0
--tblr-pagination-border-color | 1 | 0
--tblr-pagination-border-radius | 1 | 0
--tblr-pagination-color | 1 | 0
--tblr-pagination-disabled-bg | 1 | 0
--tblr-pagination-disabled-border-color | 1 | 0
--tblr-pagination-disabled-color | 1 | 0
--tblr-pagination-focus-bg | 1 | 0
--tblr-pagination-focus-box-shadow | 1 | 0
--tblr-pagination-focus-color | 1 | 0
--tblr-pagination-hover-bg | 1 | 0
--tblr-pagination-hover-border-color | 1 | 0
--tblr-pagination-hover-color | 1 | 0
--tblr-primary | 1 | 0
--tblr-primary-bg-subtle | 1 | 0
--tblr-primary-darken | 1 | 0
--tblr-primary-fg | 1 | 0
--tblr-primary-lt | 1 | 0
--tblr-primary-lt-fg | 0 | 1
--tblr-primary-lt-rgb | 1 | 0
--tblr-primary-rgb | 1 | 0
--tblr-primary-text-emphasis | 1 | 0
--tblr-secondary | 1 | 0
--tblr-secondary-rgb | 1 | 0
--tblr-shadow-card | 1 | 0
--tblr-sidebar-width | 1 | 0
--tblr-success | 1 | 0
--tblr-success-bg-subtle | 1 | 0
--tblr-success-lt | 1 | 0
--tblr-success-lt-rgb | 1 | 0
--tblr-success-text-emphasis | 1 | 0
--tblr-table-border-color | 1 | 0
--tblr-table-color | 1 | 0
--tblr-tertiary | 1 | 0
--tblr-warning | 1 | 0
--tblr-warning-bg-subtle | 1 | 0
--tblr-warning-lt | 1 | 0
--tblr-warning-lt-rgb | 1 | 0
--tblr-warning-text-emphasis | 1 | 0
125 names: 123 present, 2 intentionally absent; vendor unchanged.
```

## 3. Gerechnete Kontraste

Offline-Skript:
 /tmp/claude-0/-nvmetank1-projects-menuplan/9e4f1af2-43c1-4bd9-b63b-d4da92579062/scratchpad/tmp-codex-brand/contrast.py.
Python-Standardbibliothek; keine Appimporte, Datenbank, Netzwerk oder Paketinstallation.
Masterfarben werden aus Master §5.1 gelesen, Brand-Default per ast.literal_eval aus
default_config. Das Skript ist bewusst nicht im Repository.

WCAG: sRGB-Linearisierung mit Schwelle0.04045, Koeffizienten0.2126/0.7152/0.0722,
(Lhell+0.05)/(Ldunkel+0.05). Textgrenze4.5, notwendige Kontur/Fokus/Indikator3.0;
Entscheidung vor Rundung. APCA **0.0.98G-4g**: mainTRC2.4,
sRGBco0.2126729/0.7151522/0.0721750; normBG0.56/normTXT0.57,
revTXT0.62/revBG0.65; blkThrs0.022/blkClmp1.414; scaleBoW/scaleWoB1.14,
loBoWoffset/loWoBoffset0.027, deltaYmin0.0005, loClip0.1.
Unter blkThrs wird (blkThrs−Y)^blkClmp addiert. Bei dunklem Text:
((Ybg^normBG−Ytext^normTXT)×scaleBoW−loBoWoffset)×100;
inverse Polarität mit revBG/revTXT und +loWoBoffset. Kleine Differenzen bzw.
SAPC unter loClip werden null. Die gerundeten Koeffizienten werden nicht normiert.

Positives Lc = dunkler Text auf heller Fläche, negatives Lc = umgekehrt.
APCA ist ergänzende polaritätsabhängige Lesbarkeitsinformation, **kein WCAG-AA-Gate**
und kein pauschaler APCA-PASS für kleine Schrift. Insbesondere Sidebarlabel-Lc ist
bei echter Schriftgrösse/Gewicht gesondert zu beurteilen. Nichttext-Lc wird nur rechnerisch
mitgeführt; normativer Nichttextnachweis bleibt das verlangte WCAG-Verhältnis.

Brand-Szenario ist **Admin-Vorschlag**, nicht heutiger Renderer: Primary aus Default,
Hover/Active um12%/24% nach Schwarz (kanalweise round wie bestehendes _blend).
Nur diese drei Rollen plus notwendige abgeleitete RGB-Kanäle verändern sich.
Focus, Primary-Soft, On-Primary, Sidebar und Flächen bleiben Master. In beiden Szenarien
werden auch unveränderte Paare vollständig ausgegeben; alle fünf *-text/*-soft-Paare sind
enthalten. Primary auf Primary-Soft deckt Tabs/ausgewählte Links ab.

Rohe Ausgabe des abschliessenden Skriptlaufs; Exitcode0:

```text
WCAG: opaque sRGB; text >=4.5:1, non-text >=3:1; unrounded comparisons.
APCA: 0.0.98G-4g signed Lc, supplementary; no WCAG pass/fail inferred from Lc.
Self-checks PASS: WCAG black/white=21, identical=1; APCA B/W=106.0407, W/B=-107.8847 (tolerance 0.00005), identical=0.
Master SHA256: 8175160671890cdba1a6241da5963944a36755c514d37ccf81d6d1d7eebbd1bc
Brand fixture: default_config primary=#8c1c4b; hover=#7b1942 (-12%); active=#6a1539 (-24%); other tokens unchanged.

MASTER
foreground/background | WCAG ratio | APCA Lc | minimum | result
text/bg | 13.3713:1 | +95.05 | 4.5:1 | PASS
text-muted/bg | 5.5943:1 | +74.23 | 4.5:1 | PASS
text/surface | 14.6791:1 | +101.48 | 4.5:1 | PASS
text-muted/surface | 6.1414:1 | +80.66 | 4.5:1 | PASS
text/surface-soft | 13.9509:1 | +97.93 | 4.5:1 | PASS
text-muted/surface-soft | 5.8367:1 | +77.11 | 4.5:1 | PASS
sidebar-text/sidebar | 8.1233:1 | -73.82 | 4.5:1 | PASS
sidebar-label/sidebar | 5.6176:1 | -53.39 | 4.5:1 | PASS
sidebar-text/sidebar-hover | 6.6250:1 | -69.68 | 4.5:1 | PASS
sidebar-text/sidebar-active | 5.3230:1 | -64.84 | 4.5:1 | PASS
on-primary/sidebar-active | 7.8430:1 | -91.86 | 4.5:1 | PASS
on-primary/primary | 7.5560:1 | -89.45 | 4.5:1 | PASS
primary/surface | 7.5560:1 | +84.53 | 4.5:1 | PASS
primary/bg | 6.8828:1 | +78.09 | 4.5:1 | PASS
primary/surface-soft | 7.1812:1 | +80.98 | 4.5:1 | PASS
primary/primary-soft | 6.3802:1 | +73.10 | 4.5:1 | PASS
on-primary/primary-hover | 9.0970:1 | -93.81 | 4.5:1 | PASS
primary-hover/surface | 9.0970:1 | +89.27 | 4.5:1 | PASS
primary-hover/bg | 8.2865:1 | +82.83 | 4.5:1 | PASS
primary-hover/surface-soft | 8.6457:1 | +85.72 | 4.5:1 | PASS
primary-hover/primary-soft | 7.6814:1 | +77.84 | 4.5:1 | PASS
on-primary/primary-active | 10.5724:1 | -97.13 | 4.5:1 | PASS
primary-active/surface | 10.5724:1 | +92.99 | 4.5:1 | PASS
primary-active/bg | 9.6305:1 | +86.55 | 4.5:1 | PASS
primary-active/surface-soft | 10.0479:1 | +89.44 | 4.5:1 | PASS
primary-active/primary-soft | 8.9272:1 | +81.56 | 4.5:1 | PASS
success-text/success-soft | 6.5016:1 | +77.99 | 4.5:1 | PASS
success-text/surface | 7.1303:1 | +84.35 | 4.5:1 | PASS
success-text/bg | 6.4950:1 | +77.92 | 4.5:1 | PASS
success-text/surface-soft | 6.7766:1 | +80.80 | 4.5:1 | PASS
warning-text/warning-soft | 6.2519:1 | +77.02 | 4.5:1 | PASS
warning-text/surface | 6.8511:1 | +83.32 | 4.5:1 | PASS
warning-text/bg | 6.2407:1 | +76.89 | 4.5:1 | PASS
warning-text/surface-soft | 6.5112:1 | +79.77 | 4.5:1 | PASS
danger-text/danger-soft | 5.6653:1 | +70.77 | 4.5:1 | PASS
danger-text/surface | 6.5743:1 | +80.88 | 4.5:1 | PASS
danger-text/bg | 5.9886:1 | +74.44 | 4.5:1 | PASS
danger-text/surface-soft | 6.2481:1 | +77.33 | 4.5:1 | PASS
info-text/info-soft | 5.3720:1 | +71.74 | 4.5:1 | PASS
info-text/surface | 5.9865:1 | +79.18 | 4.5:1 | PASS
info-text/bg | 5.4531:1 | +72.74 | 4.5:1 | PASS
info-text/surface-soft | 5.6895:1 | +75.63 | 4.5:1 | PASS
neutral-text/neutral-soft | 6.7285:1 | +77.62 | 4.5:1 | PASS
neutral-text/surface | 7.6870:1 | +86.70 | 4.5:1 | PASS
neutral-text/bg | 7.0021:1 | +80.27 | 4.5:1 | PASS
neutral-text/surface-soft | 7.3056:1 | +83.15 | 4.5:1 | PASS
on-primary/danger-text | 6.5743:1 | -86.02 | 4.5:1 | PASS
control-border/surface | 3.4591:1 | +62.15 | 3.0:1 | PASS
control-border/bg | 3.1510:1 | +55.72 | 3.0:1 | PASS
control-border/surface-soft | 3.2875:1 | +58.60 | 3.0:1 | PASS
focus/surface | 7.5560:1 | +84.53 | 3.0:1 | PASS
focus/bg | 6.8828:1 | +78.09 | 3.0:1 | PASS
focus/surface-soft | 7.1812:1 | +80.98 | 3.0:1 | PASS
danger-text/surface | 6.5743:1 | +80.88 | 3.0:1 | PASS
danger-text/bg | 5.9886:1 | +74.44 | 3.0:1 | PASS
danger-text/surface-soft | 6.2481:1 | +77.33 | 3.0:1 | PASS
sidebar-indicator/sidebar | 6.2846:1 | -59.27 | 3.0:1 | PASS
sidebar-indicator/sidebar-hover | 5.1254:1 | -55.13 | 3.0:1 | PASS
sidebar-indicator/sidebar-active | 4.1182:1 | -50.29 | 3.0:1 | PASS
MASTER: 59 pairs; 0 below minimum.

BRAND-DEFAULT-ADMIN-PROPOSAL
foreground/background | WCAG ratio | APCA Lc | minimum | result
text/bg | 13.3713:1 | +95.05 | 4.5:1 | PASS
text-muted/bg | 5.5943:1 | +74.23 | 4.5:1 | PASS
text/surface | 14.6791:1 | +101.48 | 4.5:1 | PASS
text-muted/surface | 6.1414:1 | +80.66 | 4.5:1 | PASS
text/surface-soft | 13.9509:1 | +97.93 | 4.5:1 | PASS
text-muted/surface-soft | 5.8367:1 | +77.11 | 4.5:1 | PASS
sidebar-text/sidebar | 8.1233:1 | -73.82 | 4.5:1 | PASS
sidebar-label/sidebar | 5.6176:1 | -53.39 | 4.5:1 | PASS
sidebar-text/sidebar-hover | 6.6250:1 | -69.68 | 4.5:1 | PASS
sidebar-text/sidebar-active | 5.3230:1 | -64.84 | 4.5:1 | PASS
on-primary/sidebar-active | 7.8430:1 | -91.86 | 4.5:1 | PASS
on-primary/primary | 8.8132:1 | -93.42 | 4.5:1 | PASS
primary/surface | 8.8132:1 | +88.85 | 4.5:1 | PASS
primary/bg | 8.0280:1 | +82.41 | 4.5:1 | PASS
primary/surface-soft | 8.3760:1 | +85.30 | 4.5:1 | PASS
primary/primary-soft | 7.4417:1 | +77.42 | 4.5:1 | PASS
on-primary/primary-hover | 10.1946:1 | -96.67 | 4.5:1 | PASS
primary-hover/surface | 10.1946:1 | +92.46 | 4.5:1 | PASS
primary-hover/bg | 9.2863:1 | +86.03 | 4.5:1 | PASS
primary-hover/surface-soft | 9.6888:1 | +88.91 | 4.5:1 | PASS
primary-hover/primary-soft | 8.6082:1 | +81.04 | 4.5:1 | PASS
on-primary/primary-active | 11.8032:1 | -99.72 | 4.5:1 | PASS
primary-active/surface | 11.8032:1 | +95.96 | 4.5:1 | PASS
primary-active/bg | 10.7516:1 | +89.53 | 4.5:1 | PASS
primary-active/surface-soft | 11.2176:1 | +92.41 | 4.5:1 | PASS
primary-active/primary-soft | 9.9664:1 | +84.54 | 4.5:1 | PASS
success-text/success-soft | 6.5016:1 | +77.99 | 4.5:1 | PASS
success-text/surface | 7.1303:1 | +84.35 | 4.5:1 | PASS
success-text/bg | 6.4950:1 | +77.92 | 4.5:1 | PASS
success-text/surface-soft | 6.7766:1 | +80.80 | 4.5:1 | PASS
warning-text/warning-soft | 6.2519:1 | +77.02 | 4.5:1 | PASS
warning-text/surface | 6.8511:1 | +83.32 | 4.5:1 | PASS
warning-text/bg | 6.2407:1 | +76.89 | 4.5:1 | PASS
warning-text/surface-soft | 6.5112:1 | +79.77 | 4.5:1 | PASS
danger-text/danger-soft | 5.6653:1 | +70.77 | 4.5:1 | PASS
danger-text/surface | 6.5743:1 | +80.88 | 4.5:1 | PASS
danger-text/bg | 5.9886:1 | +74.44 | 4.5:1 | PASS
danger-text/surface-soft | 6.2481:1 | +77.33 | 4.5:1 | PASS
info-text/info-soft | 5.3720:1 | +71.74 | 4.5:1 | PASS
info-text/surface | 5.9865:1 | +79.18 | 4.5:1 | PASS
info-text/bg | 5.4531:1 | +72.74 | 4.5:1 | PASS
info-text/surface-soft | 5.6895:1 | +75.63 | 4.5:1 | PASS
neutral-text/neutral-soft | 6.7285:1 | +77.62 | 4.5:1 | PASS
neutral-text/surface | 7.6870:1 | +86.70 | 4.5:1 | PASS
neutral-text/bg | 7.0021:1 | +80.27 | 4.5:1 | PASS
neutral-text/surface-soft | 7.3056:1 | +83.15 | 4.5:1 | PASS
on-primary/danger-text | 6.5743:1 | -86.02 | 4.5:1 | PASS
control-border/surface | 3.4591:1 | +62.15 | 3.0:1 | PASS
control-border/bg | 3.1510:1 | +55.72 | 3.0:1 | PASS
control-border/surface-soft | 3.2875:1 | +58.60 | 3.0:1 | PASS
focus/surface | 7.5560:1 | +84.53 | 3.0:1 | PASS
focus/bg | 6.8828:1 | +78.09 | 3.0:1 | PASS
focus/surface-soft | 7.1812:1 | +80.98 | 3.0:1 | PASS
danger-text/surface | 6.5743:1 | +80.88 | 3.0:1 | PASS
danger-text/bg | 5.9886:1 | +74.44 | 3.0:1 | PASS
danger-text/surface-soft | 6.2481:1 | +77.33 | 3.0:1 | PASS
sidebar-indicator/sidebar | 6.2846:1 | -59.27 | 3.0:1 | PASS
sidebar-indicator/sidebar-hover | 5.1254:1 | -55.13 | 3.0:1 | PASS
sidebar-indicator/sidebar-active | 4.1182:1 | -50.29 | 3.0:1 | PASS
BRAND-DEFAULT-ADMIN-PROPOSAL: 59 pairs; 0 below minimum.
Checked 118 opaque pairs; 0 below minimum. No browser or production measurements.
```

118 geprüfte Paare, keine Unterschreitung. Keine Deckkraft, Gradient-, Häkchen- oder
Browser-Compositing-Messung behauptet. Disabled bleibt im Browser zu prüfen; aktive
Texte dürfen nicht über eine Disabled-Ausnahme aus der Prüfung verschwinden.
Der erste Selbstchecklauf scheiterte an einer zu exakten Referenz mit Yweiss=1;
die angegebenen APCA-Koeffizienten summieren sich zu1.0000001. Referenzvergleich auf
vier Dezimalstellen korrigiert, Algorithmus unverändert. Fehlgeschlagener Lauf im WP-Bericht.

## 4. Konflikte und konkrete Entscheidungsvorlage

Alle Empfehlungen sind **VORSCHLÄGE**. Auftraggeberannahme mit Datum und gewählten Optionen
fehlt. Zustimmung zum Erstellen dieses Dokuments ist keine Corporate-Design-Freigabe.

### K1 — Schrift

Beleg: Master §5.2 Arial/Georgia, tokens.css:105–140 Fira; branding_tokens.py:76–77
setzt Headingfamilie zuletzt; Mockup-Einordnung zeigt serifenlose Titel.
design-excellence §2 lehnt Systemfonts als Default ab, **§0 ordnet sich ausdrücklich
Projektmarke/Master unter**. Der Skill kann daher Master nicht selbst ändern.

- **A, Orchestrator-Empfehlung:** Fira Sans für Fliesstext UND Überschriften; H1/Cardtitel700,
  Body400, Labels600. Georgia entfällt als dokumentierte Masterabweichung. Alle Mastermasse
  bleiben Referenz; gesonderte Darstellungsoption K7 wird nicht durch K1 freigegeben.
- **B:** Master wortgetreu Arial/Georgia; lokal verfügbare Fontfallbacks protokollieren.

Konsequenz: Admin-Typografie zentral; Public/Print/TV behalten bestehende Brandfamilien.
A nutzt vorhandene WOFF2-Dateien, B verändert Laufweiten und Umbrüche. Beide benötigen
neue vorgeschlagene Font-/Screenshotbelege, keine blinde Baselineerneuerung.
**Auftraggeberfreigabe: ja.**

### K2 — Sidebar 1200 oder 992 px

Beleg: _workflow_sidebar.html:34,44 und admin-tabler.css:61–72,89–91; Master §§10/12.
Hersteller-lg ist992; keine Änderung des Herstellers erforderlich.

- **A, Orchestrator-Empfehlung:** navbar-expand-lg, zugehörige d-lg-none-/CSS-Grenzen
  gemeinsam in SHELL angleichen; Fokus/Collapse/No-JS weiter funktionsfähig.
- **B:** xl beibehalten; wäre Abweichung von Master und ausdrücklich benannter
  1024×768-Prüfung „mit Sidebar“.

Bei1024: 1024−248−2×24 = **728px nutzbare Inhaltsbreite**, vor Cards/innerem Grid/Scrollbar.
Die 24px gelten hier als vorgeschlagene Tablet-Innenabstandszuordnung unterhalb1200,
während Sidebar bereits ab992 offen ist. „Desktoppadding32 schon ab992“ ergäbe712px;
diese Terminologieüberschneidung zwischen Master §§5.2/10 muss der Entscheid mit abdecken.
Breite Wochenarbeitsflächen brauchen lokale Scroll-/Layoutlösung, keine Schriftschrumpfung.
Admin-Baselines bei1024 ändern sich; Public/Print/TV-Breakpoints bleiben unverändert.
**Auftraggeberfreigabe: ja** (Änderung des Bestands, nicht des gewünschten Sidebar-Breakpoints).

### K3 — Adminpalette und erlaubter Markeneinfluss

Beleg: Master §5.1; vollständige Ist-Tabelle; default_config; §3-Rechnung.

- **A, Orchestrator-Empfehlung:** Master als Adminstandard; Original-Logo bleibt markengeführt.
  Primary/Primary-Hover/Primary-Active dürfen aus geprüfter Marke kommen. Primary-RGB
  ist zwingend synchron abgeleiteter Kanalwert, keine vierte unabhängig konfigurierbare Farbe.
  Keine Markensteuerung von Sidebar, Hintergrund, Flächen, Status oder Heading-Font.
- **B:** ausschliesslich Masterpalette im Admin, Marke nur als Logo.
- **C:** heutiges vollständiges Branding im Admin fortführen; verletzt Masterflächen und
  braucht eigene breite Abweichungsentscheidung statt stiller Fortsetzung.

A mit Default-Primary besteht 59 Paarprüfungen (zusammen mit Master 118); gültige Livewerte unbekannt.
Admin-Auswahl-/Link-/Buttonzustände ändern sich konsistent. Public/Print/TV behalten ihre
Markenwirkung vollständig. Brand-Default und Custombrand benötigen getrennte Browserfixtures,
Statechecks und geprüfte neue Admin-Baselines; geschützte Baselines dürfen nicht mitwandern.
**Auftraggeberfreigabe: ja.**

### K4 — Scope, Reihenfolge und !important

Beleg: base_tabler.html:14 und jede branding_css-Regel in §1.4.

- **A, Orchestrator-Empfehlung:** Branding-Renderer liefert für .dishboard-admin nur die
  geprüften Primarytoken samt abgeleiteten Kanälen; Logo bleibt vorhandener Markenausgabeweg.
  Direkte Admin-Heading-, Form-, Flächen-, Sidebar-, Tab-, File-Button-Overrides entfallen.
  Globale Button-/Listenregeln einschliesslich !important werden von Admin ausgeschlossen.
- **B:** vollständigen Admin-Brand-Scope behalten und Masterabweichungen akzeptieren.
- **C:** Brandstylesheet früher laden; allein unzureichend wegen !important und geerbter
  Legacywerte, gefährdet zudem Spezialansichten. Nicht empfohlen.

A in MP-UI-TOKENS (Besitz branding_tokens.py) umsetzen. Nicht nur .dishboard-admin aus
einer Selektorliste entfernen: die bisher **globalen** .btn-primary/.bg-primary/.list-group
dürfen ihn ebenfalls nicht treffen. Nicht-Admin-Regeln mit gleicher Spezifität erhalten,
z.B. neutralem :where(body:not(.dishboard-admin))-Scope; alle tatsächlichen Public-,
Print-, TV- und Auth-Consumer dabei regressionsprüfen. Brand-:root-Werte bleiben für diese
Varianten wirksam, Admin konsumiert eigene Tokens. Kein Admin-!important als Gegenwehr.
Keine Änderung gespeicherter Brandrevisionen/Logos oder URL-/Speicherverträge.
Tests: Ausgabe und Schutz aller Consumer, einschliesslich Print mit .print-body.
**Auftraggeberfreigabe: ja**, gemeinsame Annahme mit K3; neue API/DB-Funktion nicht erforderlich.

### K5 — Unbekannte aktive Produktionsmarke

**Aktive Markenwerte: nicht aus Produktion gelesen.** Kein Default als Livewert ausgeben.

- **A, Orchestrator-Empfehlung:** vorhandene validierte Revision erst beim Rendern beurteilen.
  Effektiven Primary samt deterministischen Hover-/Activewerten berechnen; alle davon
  abhängigen §3-Paare gegen feste Admin-Masterflächen/On-Primary/Primary-Soft prüfen.
  Text mindestens4.5, notwendige UI-Information mindestens3, vor Rundung. Nur vollständigen
  Kandidatensatz ausgeben; bei Kontrastfehler gesamten Primary-Satz **inklusive RGB** auf
  Master zurücksetzen. Focus/Sidebar/Status/Surface bleiben unverändert.
- **B:** im Admin immer Master verwenden, bis individuelle Zuordnung freigegeben ist.
- **C:** gespeicherte Validierung allein vertrauen; nicht empfohlen, da sie nur die
  Brand-Surface und keine Admin-Hover-/Activezustände prüft.

Gate gehört in den Admin-Override-Renderer, nicht in DB-Migration/Editorvalidierung.
Bestehende Fehlerbehandlung für beschädigte Konfiguration, fehlende Revision, Zugriffs-
oder Speicherfehler bleibt bestehen: solche Fehler nicht unter „Kontrastfallback“ verstecken.
A muss synthetisch auch „gegen eigene Brand-Surface gültig, gegen Adminweiss ungültig“
prüfen, dazu Grenzwerte, RGB-Kohärenz und Defaultfall. Public/Print/TV bekommen weiterhin
originale validierte Brandwerte; gespeicherte Historie und deren Baselines bleiben geschützt.
**Auftraggeberfreigabe: ja**, zur Laufzeitregel; keine Behauptung einer Live-Abnahme.

### K6 — Mockup und Produktumfang

Beleg: design-reference-0911.md, Abschnitte „Konflikte“ und „Im Produkt nicht vorhanden“.
Das Chatbild wurde hier nicht visuell geprüft; die versionierte Einordnung ist Quelle.

- **A, Orchestrator-Empfehlung:** Stil übernehmen: Petrolsidebar, weisse Karten,
  warmer Hintergrund, Burgunder für Handlung/Auswahl, Status mit Icon/Text. Nur bestehende
  Navigation, Felder, Aktionen und optionale reale Menübilder verwenden.
- **B:** fehlende Mockupfunktionen separat fachlich beauftragen. Ohne eigenen Auftrag
  bleiben sie ausserhalb TOKENS/SHELL/MACROS.

**Nicht Teil von Tokens/Shell:** globale Ctrl+K-Suche; neue Archiv-/Preis-/Allergenrouten;
Menüvorlagen unter dem bestehenden Ausgabevorlagen-Endpunkt; neue Menüarten Vegan/Dessert;
erfundene Vollständigkeitszahlen; Claim/Herz; zusätzliche Editor-Tabs oder Kategorie;
frei wählbarer Prüfstatus; generierte/dekorative Foodfotos. Offcanvas, Wochenhinweis,
Wochenraster und Wochenaktionslogik gehören in bestehende fachliche Seiten-WPs, nicht hier.

Für benannte Konflikte lautet Vorschlag: Datum vor KW; „Veröffentlichen“ gemäss Wörterbuch;
bei offenen Prüfungen „Offene Angaben prüfen“ als Hauptaktion nur mit vorhandenem
Workflowzustand; „Bearbeiten“ sichtbar statt universellem Kebab; vorhandene technische
Rollenbezeichnungen nicht als neues Küchentextmuster übernehmen. Original-AuthZ bleibt.
Kochbücher, API/Schnittstellen, Wochenverwaltung/-prüfung, Grundlagen-Details, Benutzer-
Protokoll, Zugriffsverlauf und Patientenplan müssen mit bisheriger Berechtigung erreichbar bleiben.

Konsequenz A: gemeinsame Adminsprache; keine Funktionsverluste oder neuen Daten in irgendeinem
Kanal. Bestehende Public-/Print-/TV-Verträge unverändert; Browser-/Rollenprüfungen statt
pixelgenauem Abzeichnen des Mockups. **Freigabe:** für Beibehalten des Funktionsumfangs nein;
Annahme dieser visuellen Konfliktvorlage ja; neue Funktionen unter B eigener Auftrag.

### K7 — Darstellungseinstellungen gegenüber festen Mastermassen (zusätzlicher Befund)

Beleg: admin-tabler.css:73–91; display_settings.py:8–16; Master §5.2.
Der globale Default compact setzt heute12px Cardpadding; Master nennt24px/16px mobil.
Schriftoption large und full sind echte gespeicherte Funktionen und dürfen nicht verschwinden.

- **A, Vorschlag dieses Workers:** normal/compact wird Masterbasis; comfortable nutzt eine
  ausdrücklich freizugebende geräumigere Variante aus derselben Abstandsskala (Card-Inset
  nächste Stufe, mobile Variante ebenfalls nächste Stufe). Alle Werte zentral; beide
  Optionen bleiben sichtbar verschieden. Large skaliert jede Schriftrolle um den bestehenden
  Faktor1.125 statt Rollen auf dieselbe Grösse zu drücken; normale Masterhierarchie bleibt.
- **B:** Compact-Cardpadding12 und heutige Large-Grössen als dokumentierte Bestandsausnahme
  bewahren; weniger Umbruchänderung, aber keine einheitliche Masterbasis.
- **C:** beide Optionen auf gleiche CSS-Ausgabe mappen; verworfen, weil vorhandene Auswahl
  ihre Funktion verlöre.

A braucht eine zusätzliche zentrale Variantenfreigabe; dafür liegt **keine gesonderte
Orchestrator-Empfehlung** vor. §6 beschreibt Anschluss ohne voreilige Umsetzung.
Admin-Baselines sämtlicher Optionen ändern sich, Public/Print/TV nicht.
**Auftraggeberfreigabe: ja.** Kein stilles „alle Mastermasse erhalten“ für diese Ausnahme.

### K8 — Haarlinien statt Schatten gegenüber Master-Minimalschatten

Beleg: Brief-Designrichtung „Haarlinien statt Schatten“; Master §§5.2/8 nennt Minimalschatten.

- **A, Orchestrator-Designrichtung aus Brief:** schattenfreie Admin-Cards mit Haarlinien;
  explizite Ausnahme vom Schattenwert im Master dokumentieren.
- **B:** Master-Minimalschatten zusätzlich zum Rand beibehalten.

Admin-Baselines unterscheiden sich geringfügig; Public/Print/TV-Schatten unberührt.
**Empfehlung des Orchestrators: A laut Brief; Auftraggeberfreigabe: ja** für Masterabweichung.

## 5. Geschützte Public-/Print-/TV-Werte

Schutz beruht auf **Admin-Selektorgrenze und erhaltenen Legacy-:root-Werten**.
Ein nur global neu gesetztes --sh-Token wäre trotz unveränderter Spezial-CSS ein Eingriff.
Weisse Flächen bleiben im Standard weiss; vorhandene Custombrand-Surface darf im
geschützten Kanal weiterhin ihren bisherigen Einfluss behalten.

| Kanal / Datei:Zeile | Geschützter Wert / Wirkung | Trennung |
|---|---|---|
| Public static/public.css:2–34 | eigene --tblr-Font-/Surface-/Border-/Radius-Anbindung an --sh; Weiss als Body-BG; Cardradius --sh-radius-lg, Schatten --sh-shadow-soft | Diese :root-Zuweisungen nicht global durch Adminadapter ersetzen |
| Public static/public.css:35–50 | .public-page Weiss; Links mindestens48px; H1 clamp(1.75rem,3vw,2.75rem), Cardtitel1.375rem/1.3/600; Cards overflow:hidden | .public-page ist keine .dishboard-admin |
| Public static/public.css:51–63,72–75,101–117 | Statuskante an Cardkurve; lokale Navigationsscrollregion; Rastergap1.5rem, responsive Subgrid statt Text-Clamp | .public-page und ihre Komponenten geschützt |
| Print templates/public/print_cafeteria_week.html:1–9 und print_patient_week.html:1–9 | base.html, body.print-body, .print-shell, Original-Markenausgabe | Kein Adminbasis-Template und keine .dishboard-admin |
| Print templates/base.html:10–17; static/app.css:335–352 | eigene Assets tokens/app/menu-images/food-symbols/brand; Printheader2px Teal; Footer.78rem; A4 quer,10mm Seitenrand | app.css wird im Printpfad geladen; Adminadapter nicht |
| Print static/app.css:382–393 | weisser Grund; H1 28pt, Copy10pt; Gridgap4mm; Radius3mm; Padding2.5mm/3mm; keine Kartenschatten; break-inside:avoid | @media print plus Printlayout; diese generischen Regeln nicht in Admin-CSS verschieben |
| TV static/signage.css:1–9 | eigene Root-Fonts/Radien; .signage-body 100vw×100vh; .signage-shell 16:9, vh/vw-Abstände, bestehende300ms-Updateblendung und reduced-motion | .signage-body, keine Adminklasse; Admin-Motionregel nicht global anwenden |
| TV static/signage.css:13–16 | Kicker clamp(15px,1.04vw,23px); Wochentag clamp(34px,3.2vw,66px); Datum/Uhr clamp(16px,1.1vw,24px) | Signageklassen behalten entfernungsgerechte Schrift |
| TV static/signage.css:139–158 | Wochenkarten weisse Panels, gemeinsame Kanten; Tageskopf clamp(24px,1.25vw,48px), Gericht clamp(36px,1.875vw,72px), Komponenten clamp(20px,1.04vw,40px); Footer clamp(18px,.94vw,36px) | .cafe-week-board/.signage-cafe-week |
| TV static/signage.css:166–185 | weisse Patient-Duo-Cards, Titel clamp(46px,2.4vw,94px), Komponenten clamp(28px,1.46vw,56px); keine Admin-Cardgeometrie | .patient-duo/.patient-signage-option |
| TV static/signage.css:195–223 | Vier-Spalten-Board, vorhandene OPS-Subgrid-Geometrie, helle Meal-Flächen; Gericht clamp(20px,1.05vw,42px), Hinweis clamp(18px,.94vw,36px); Unavailable-H1 clamp(60px,5vw,192px) | .patient-board/.patient-unavailable |

Alle weiteren Spezialwerte in diesen Dateien bleiben ebenfalls geschützt; Tabelle hebt
prüfkritische Geometrie hervor. Druck-HTML, native PDF-Geometrie/Paintbilder und physischer
Küchendruck sind verschiedene Nachweise; hier keiner ausgeführt. Patientenausgaben
bleiben ohne Preise. Keine „einheitlichen 16px“ auf TV oder Print übertragen.

## 6. Abbildung aller globalen Darstellungseinstellungen

Vorhandene Speicherung, Schlüssel, Auswahlmengen, Defaults, Formular, Preview/Save/Reset,
Validierung, Berechtigungen und globaler Geltungsbereich bleiben unverändert.
Readpfad: display_settings.get_admin_display → display_context → base_tabler.main;
lokale Preview benutzt dieselben CSS-Consumer mit display_values. Keine DB- oder
LocalStorage-Neuerfindung. Es existieren genau diese vier Admin-Darstellungsschlüssel:

| Einstellung / gespeicherte Werte | Heutige Wirkung | Vorgeschlagener Token-/Klassenanschluss im Adminscope |
|---|---|---|
| admin_density: compact (Default), comfortable | Cardpadding12 gegenüber16/24 je Viewport; Previewparallel | .dishboard-admin :is(.admin-main,.display-preview)[data-density=…] setzt zentrale Abstandstoken für Card-Inset, optionale Gruppengaps und Tabellenpadding. K7-A: compact Masterbasis, comfortable nächste Stufe der Masterskala. Beispiel Desktop Card-Inset24→32, mobil16→24, als **freizugebende Variante**, keine zweite Skala. Tabellen wachsen über Padding, mindestens ungefähr64px, keine feste abschneidende Höhe; bestehende48px-Controls erhalten. |
| admin_font_size: normal (Default), large | normal Rollen aus Adapter; large text1.125rem/titel1.375rem für viele Elemente, H1 nicht mitgeführt | derselbe data-font-size-Scope setzt zentrale rollenbezogene Typotoken; normal Master, large Faktor1.125 für jede Rolle. --tblr-body-font-size/btn-font-size plus direkte Felder/Labels/Hinweise/Titel. Rootschrift und Browserzoom unverändert. K7-Freigabe nötig; Sidebar wie bisher ausserhalb .admin-main nicht still mitverändern. |
| admin_content_width: contained (Default), full | contained Vendor-Container; full max-width:none; Preview48rem | data-content-width konsumiert gemeinsame Standard-/schmal-/Arbeitsfläche-Varianten. contained: Mastermaximum innerhalb Hauptbereich. full: vorhandene Entgrenzung der äusseren Inhaltsfläche erhalten; innere Felder dürfen fachlich schmal bleiben. Explizite schmale Seiten nicht versehentlich durch festen Selector gegen full immun machen. Preview als begrenztes Beispiel kennzeichnen, identischen Tokenanschluss nutzen. |
| admin_menu_images: show (Default), hide | _menu_image.html entscheidet Ausgabe, Preview reicht Wert explizit weiter | data-menu-images bleibt bestehender Zustandsmarker. **Keine reine Tokenabbildung** und kein neuer CSS-only-Ersatz für Jinja-Gate. Serverrender erhält Bilderfunktion, Texte/Allergene/Hinweise bleiben. Kein Einfluss auf Public-/Print-/TV-Ausgaben ausser vorhandener Adminpreview. |

Nicht abbildbar als Farbe/Abstand: Bildausgabe ist Templatefunktion; Logo/Brandrevision
sind eigener bestehender Markenkontrakt, keine weiteren vierteilig gespeicherten
Darstellungsoptionen. Dichte/Schriftvariation ist in K7 zu entscheiden, nicht in einem
Token-WP nebenbei aus gespeicherten Daten abzuleiten.

## 7. Designrichtung und Zuständigkeit

**Zweck:** Küchenmitarbeitende bearbeiten und veröffentlichen Wochenpläne. Eine Hauptaktion
je Kontext, nach echtem Workflowzustand; Lesbarkeit vor Dichte.

**Stil: Swiss Editorial Calm.** --app-bg trägt warmes Papier, --app-surface die weissen
Arbeitsflächen. Haarlinien aus --app-border/--app-border-soft gliedern ohne Dekoschatten
(K8). --app-sidebar bildet dunkles Petrol; Burgunder über --app-primary-Familie markiert
Handlung, Auswahl und Links. Status nur dunkles *-text auf *-soft als Pill mit Icon
und echter Bezeichnung. Kein Card-in-Card ohne fachlichen Grund, kein dekorativer
Verlauf, keine Food-Fotos als Schmuck.

**Typografie:** K1-A Fira Sans; hero/h1/h2/body/small nach Master §5.2, hero kein neuer
Grössenwert. H1/Cardtitel700, Body400, Labels600. Preise/Mengen mit font-variant-numeric:
tabular-nums. Echte Ellipse „…“, geschütztes Leerzeichen in „CHF 11.00“. Formatierung
ändert keine Daten-/Währungsverträge. Reale Texte und vorhandene Schweizer Anrede erhalten.

**Signatur:** helle --app-sidebar-indicator-Linie am aktiven Navigationseintrag und
Burgunderfokus auf hellen Flächen; in Sidebar heller Fokus. Kein Layoutsprung.
Allenfalls120–220ms transform/opacity als kurze Interaktionsbewegung, nur unter
prefers-reduced-motion:no-preference; bei reduce keine Bewegung. Kein transition:all,
keine neue automatische Animation, keine Übertragung auf bestehendes TV-Polling.

| Paket | Verantwortete Übersetzung |
|---|---|
| MP-UI-TOKENS | zentrale Mastertokens, freigegebene Fonts/Varianten, alle realen Tablerzustände, Brand-Gate und Scope; Kontrast-/Computed-Style-Belege |
| MP-UI-SHELL | Sidebar248, freigegebene992-Grenze samt Collapse/No-JS, Indicator/aria-current, Logout erreichbar, min-width:0, zentrale Container; Original-Logo; keine erfundenen Navigationsziele/Topbar |
| MP-UI-MACROS | page_header, Felder/Hilfen/Fehler, Status, Empty State, echte Pagination/Aktionen; Pflichtzustände leer/spärlich/dicht/ladend/fehler je Komponente im echten Kontext |
| bestehende fachliche Seiten-WPs | Wochenraster/Editor/Veröffentlichungszustand und übrige inventarisierte Seiten konsumieren gefrorene Komponenten; keine neue Fachfunktion aus Mockup |

## 8. Konkreter Anschluss für MP-UI-TOKENS

Diese Liste ist Umsetzungsvorlage, **keine Implementierung oder Schreibberechtigung ausserhalb
des jeweiligen nächsten WP-Besitzes**. Voraussetzung: K1–K5/K7/K8 entschieden; K6-Scope bestätigt.

| Datei | Konkrete Änderung nach Freigabe |
|---|---|
| static/tokens.css | alle35 --app-Farbtoken des Masters und zentrale Master-Mass-/Schrift-/Abstandstoken unter .dishboard-admin definieren; neue Fontrollen aus K1. Vorhandene72 --sh-Rootwerte und @font-face für geschützte Kanäle bewahren. Keine globale Migration von --sh-primary/--sh-font. Noch benötigte Admin-Legacyaliases nur hier im Adminscope zur jeweiligen --app-Rolle binden und Nutzer prüfen, keine globale Löschung vermeintlich ungenutzter Werte. |
| static/admin-tabler.css | bestehenden --tblr-Block und direkte Bodyfarbe/Schrift auf §2-Vertrag umstellen; hartes Primary-RGB entfernen, sämtliches RGB dynamisch aus effektiven Tokenfarben ableiten. Wirkungsloses --tblr-primary-lt-fg entfernen. Master-Farben an Buttons/Formen/Links/Tabs/Pagination/Status/Card/Sidebar samt Zuständen anbinden. Alte --sh-Abhängigkeiten im Admin durch passende Rolle ersetzen; Formfocus-Festfarbe, aktive Cardheader-Tabs und File-Selector direkt scoped korrigieren. Keine !important-Kaskade. |
| static/admin-tabler.css | Grössen/Radien/Cardpadding und Fontoptionen auf zentrale Tokens umstellen; globales16px vermeiden, grössere48px-Ziele erhalten. K7-Varianten und K8-Schattenentscheid umsetzen. Breakpointänderung61–72/89–91 mit SHELL synchronisieren: gemeinsamer Dateibesitz darf nicht parallel kollidieren; TOKENS liefert Grundlagen, SHELL ändert korrespondierendes HTML nach Freeze. |
| branding_tokens.py | vorhandenes Public-/Print-/TV-brand_tokens-Verhalten erhalten; dedizierte Adminableitung aus validiertem Primary, deterministische12%/24%-Schwarzblendung oder konkret freigegebene Alternative. Alle §3-Primary-Paare prüfen, atomarer Masterfallback samt RGB. Keine Abhängigkeit von Default-Sonderfall. Nur .dishboard-admin Primaryfamilie/RGB ausgeben; Tabellenregeln §1.4 wie K4 von Admin abgrenzen, Nicht-Admin-Spezifität/Verhalten schützen. Keine Brandrevision mutieren. |

Keine Änderungen an branding_config.py, display_settings.py, display_routes.py,
Datenbankschema oder gespeicherten Revisionen für diese Entscheidung erforderlich.
Falls nächste Umsetzung weiteren Dateibesitz braucht, reserviert Root ihn vor Dispatch;
nicht hier nebenbei ausweiten.

**Browser-Abnahme durch test_ui_master_tokens_browser.py im TOKENS-WP:**

- Echte vorhandene Komponenten rendern, keine unabhängige Demoattrappe. Default ohne
  Custompalette, Brand-Default, kontrastfeste Custompalette, gültige kontrastschwache
  Adminmarke mit Fallback, Fira/Carlito als geschützte Brandfixture.
- Berechnete color/background/border/font/line-height/radius/min-height für Button,
  Feld, Tab und Pagination **normal/hover/active/focus/disabled/invalid soweit semantisch
  vorhanden** messen. Nicht anwendbare Zustände benennen, z.B. invalid an Pagination.
  Pressed, checked/indeterminate, focus+invalid und aktive Cardheader-Tabs einschliessen.
- CSS-Variablen und tatsächliche Eigenschaften prüfen: Primary-RGB/Link-RGB/LT-RGB,
  Utility-Opacity, dynamisches Compositing; keine blaue Vendor-Fokusrestfarbe. APCA
  zusätzlich protokollieren, WCAG aus tatsächlich angrenzenden Farben rechnen.
- Alle vier Einstellungen in Hauptansicht und ungespeicherter Preview, beide Werte je
  Einstellung sowie sinnvolle Kombinationen prüfen; Rollen/POST/CSRF/disabled/readonly
  erhalten. Grössere Schrift darf keine abgeschnittenen Controls erzeugen.
- Reale Fontdateien/Plattformfonts und Fontbereitschaft dokumentieren; alle fünf
  Masterviewports1440×900,1024×768,768×1024,390×844,1920×1080 an Referenzkomponenten;
  Sidebargrenze991/992 zusätzlich im SHELL-Verbund. Tastatur,200%-Zoom und reduced-motion.
- Geschützte Public/Print/TV-Styles und Brand-Ausgabe gegen dieselben synthetischen
  Ausgangsfixtures vergleichen. Keine Baseline blind ersetzen; native Print-/PDF-Gates
  und physischer TV/Küchendruck separat. Auth-/Loginpfad gegen unbeabsichtigte globale
  Brand-Scopeänderung prüfen.

## 9. Grenzen, Freigaben und nicht Geprüftes

- Keine Live-Markenwerte, Produktionsdaten, DB-Verbindung, Credentials oder Env-Dateien gelesen.
- Keine neue Browsermessung berechneter Styles, Screenshots, tatsächlichen Fonts oder
  Interaktionen. Inventarmanifest nur als vorhandener datierter Beleg gelesen.
- Keine Corporate-Design-Freigabe, kein Nutzertest; Auftraggeberannahme aller benannten
  offenen Optionen fehlt. Dieses Dokument markiert keine WP-/Gesamtmigration als ACCEPTED.
- Keine Produktdatei, Manifest/Matrix, Baseline, Schema oder Migration geändert;
  keine Delegation, Installation, Netzwerkabfrage, OCR, Push, Merge oder Deploy.
- RAG-Kontextpack wegen explizitem Netzwerkverbot nicht aufgerufen. GitNexus nur lokale
  Quellenorientierung und vor Commit Scopeanalyse; kein bestehendes Symbol geändert,
  deshalb kein Symbol-Impact-Editgate erforderlich.
- Nicht gefahren: pytest-/Browser-/axe-/CSS-Computed-/PDF-/Signage-/Rollenregressionssuite,
  Ruff/Mypy für Produktcode, vollständiger Paketprüfer, OCR und unabhängiger Review.
  Das ist kein PASS; diese Umsetzungsgates gehören zur nächsten Lane und Root-Abnahme.
- Ausgeführt: Standardbibliothek-Kontrastrechnung, Quell-/Vendorvergleich und Git-Diff-/Scope-
  Prüfungen. Exakte Gateausgaben, Scriptfingerprint, Commit und Reportregistrierung stehen
  im Bericht wp-10e17980d6a1.md im bestehenden Host-Berichtsspeicher.

**Entscheidungsauftrag an Root/Auftraggeber:** K1-A, K2-A inklusive Paddingzuordnung,
K3-A, K4-A, K5-A, K6-A bestätigen oder Alternativen festlegen; K7-A als zusätzliche
Variantenentscheidung, K8-A als Schattenabweichung explizit annehmen oder ablehnen.
Bis dahin bleiben abhängige Token-/Shelländerungen AWAITING_EXTERNAL.
