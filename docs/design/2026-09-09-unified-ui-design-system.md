<!-- Verbindlicher Nutzerauftrag vom 9. September 2026, konsolidiert mit dem Dichteauftrag vom 13. September 2026. Fachliche, Sicherheits- und Architekturverträge bleiben erhalten. -->

# Verbindliches UI-Manifest: gemeinsame Flask-/Tabler-Gestaltung und kompakte Arbeitsflächen

**Einsatz:** Gemeinsamer Arbeitsvertrag für alle beauftragten Coding-Tools im bestehenden Repository.

**Geltungsbereich:** Die gesamte Anwendung, alle vorhandenen Tools, Module, Verwaltungsseiten und gemeinsam verwendeten UI-Komponenten. Keine Bindung an eine bestimmte Fachdomäne, Beispielseite oder Route.

**Technische Basis:** Flask, Jinja2, Tabler, das zur installierten Tabler-Version gehörende Bootstrap und Tabler Icons.

**Ziel:** Gemeinsame, überprüfbare Gestaltung aller bestehenden und künftigen Oberflächen: volle interne Arbeitsbreite, kompakte Inhalte und sichere unmittelbare Bedienung. Der Rezepteditor ist die erste Referenz, keine Begrenzung der Migration.

Dieses Dokument ist eigenständig verwendbar. Die beiden älteren Entwürfe zum UI-Design und zur seitenbezogenen Migration werden für diese UI-Aufgabe durch diesen konsolidierten Standard ersetzt. Bestehende Sicherheits-, Architektur- und Repository-Vorgaben bleiben gültig. Bei einem Konflikt mit einem freigegebenen Corporate Design oder Projektvertrag: Konflikt benennen, nicht stillschweigend überschreiben.

---

## Auftraggeber-Entscheid 2026-09-20

Gemäss Auftraggeber-Entscheid im Handoff (`docs/design/uiux-handoff-2026-09-20/`) werden folgende Regeln und Strukturen ersetzt bzw. präzisiert:
* **M01 Seitenrahmen/Tabs/Statuslage:** Horizontale Haupt-Untermenüs entfallen; stattdessen eingerückte Kontextnavigation in der Sidebar (nur bei aktivem Oberpunkt). Neue Seitenstruktur: Titel + ein Satz Kontext → rechts höchstens EINE primäre globale Aktion → Statusbar über volle Inhaltsbreite → Filter/Suche nur wenn nötig → Hauptinhalt → Sekundäres/Technisches.
* **R07:** Das Statusbar-Designsystem rückt als globale Komponente zentral unter den Titel. Die frühere Angabe «3–5 Slots» ist am 2026-09-20 durch **1–5 echte Slots** ersetzt.
* **R08:** Hauptaktion standardmässig oben rechts im Seitenkopf. Bei langen Editoren ist eine kompakte sticky Aktionsleiste zulässig.
* **A17 (Testmatrix) & Mobile:** Pflichtbreiten 360, 768, 1024, 1440 px. Sidebar darf mobil zu Drawer werden.
* **Begrifflichkeiten:** Der Navigationspunkt «Grundlagen» heisst neu «Zutaten». Der Seitentitel entspricht stets dem Navigationspunkt. Bestehende URLs und Endpoints bleiben unverändert.

**Ausdrücklich unverändert bleiben:**
* 200-%-Browserzoom-Test und sichtbarer Fokus (2px Outline mit Abstand).
* Mindesthöhen der Bedienelemente (hier gilt der strengere Wert von **48px** basierend auf Test `test_rendered_ui.py` gegenüber den Token-Variablen).
* Fehlende Angaben dürfen niemals als «allergenfrei» dargestellt werden.
* Ohne-JS-Bedienbarkeit und Erhalt der `<noscript>`-Redundanz.
* Erhalt bestehender CSRF- und Backend-Sicherheitsgrenzen.
* Verbindliche Token-Pflicht für alle Styles.
* Signage und öffentliche Seiten sind nicht Teil dieser Umsetzungs-Welle.

## Auftraggeber-Ergänzung 2026-09-20: Vereinfachung und kompakte Formulare

Ergänzung zu den Auftraggeber-Prompts «Kompakte Formulare» und «Globale UI-Vereinfachung» (`docs/design/uiux-handoff-2026-09-20/07_ERGAENZUNGEN/`). Beispielbilder sind Denkweise und Komposition, keine Datenquelle und kein Funktionsumfang.

### Grundprinzip

> «Zeige nur, was im aktuellen Kontext gebraucht wird.»

Komplexität darf im Datenmodell und Backend existieren; sie darf nicht ungefiltert und dauerhaft im UI landen. Funktionalität, Validierung und Speichersemantik bleiben unverändert.

### Entscheidungsregel

Wenn zwei Varianten fachlich gleichwertig sind, verwende diejenige, die:

1. weniger Erklärung benötigt,
2. weniger permanente UI-Elemente zeigt,
3. weniger Klicks im häufigsten Workflow benötigt,
4. weniger Platz verbraucht,
5. bereits an anderer Stelle als gemeinsames Pattern eingesetzt werden kann.

### Informationshierarchie

Priorität absteigend:

1. aktuelle Aufgabe,
2. für die Entscheidung notwendige Informationen,
3. Status und Warnungen,
4. Primäraktion,
5. optionale Details,
6. technische und administrative Informationen.

Stufen 5 und 6 standardmässig einklappen oder zurückhaltend darstellen, sofern sie nicht unmittelbar benötigt werden.

### Platzverbrauch

Vertikalen Platz als knappe Ressource behandeln. «Kompakt ist nicht gequetscht»: Mindesthöhen der Bedienelemente (**48 px**), sichtbarer Fokus, Lesbarkeit und 200-%-Zoom bleiben verbindlich. Keine riesigen Karten für wenige Informationen, keine dauerhaft sichtbaren Detailfelder für nicht ausgewählte Optionen, keine künstlich gestreckten Einzelfelder über die volle Breite ohne Grund.

### Prüffragen je Seite

Vor jeder Vereinfachung kurz prüfen:

- Kann Feld, Text, Button, Status oder Abschnitt entfallen?
- Kann etwas erst bei Bedarf eingeblendet werden?
- Werden dieselben Informationen mehrfach gezeigt?
- Sind Formulare unnötig lang oder breit?
- Gibt es dauerhaft sichtbare Detailfelder für nicht ausgewählte Optionen?
- Sind Aktionen über mehrere Stellen verteilt?
- Gibt es zu viele gleichwertig wirkende Buttons?
- Kann ein sinnvoller Standard einen Arbeitsschritt einsparen?
- Lassen sich Listen, Filter und Aktionen kompakter darstellen?
- Ist Tabelle statt vieler grosser Karten sinnvoller – oder umgekehrt?
- Sind Überschriften, Hilfetexte oder technische Angaben für den Normalfall nötig?
- Werden interne IDs, Revisionen oder technische Zustände unnötig prominent gezeigt?
- Gibt es grosse Leerflächen oder gestreckte Eingabefelder?
- Ist sofort erkennbar: Wo bin ich? Was ist der Zustand? Was ist die nächste Handlung?
- Ist die gleiche Funktion in anderen Modulen anders aufgebaut?

### Vorgehen

Phase 1 — UI-Audit → Phase 2 — gemeinsame Komponenten → Phase 3 — Module → Phase 4 — Detailseiten und Sonderzustände → Phase 5 — Regression. Keine vorhandene Fachfunktion entfernen; Backend-Verträge, Datenmodell, Validierung und Berechtigungen erhalten.

### Beispielbilder: übernommen / nicht übernommen

| Im Beispielbild | Entscheidung | Grund |
|---|---|---|
| Horizontale Modul-Tabs über der Liste und alle Module flach in der Sidebar | nicht übernehmen | SDD «nicht verhandelbar»: keine horizontale Modul-Untermenüleiste; Unterpunkte nur eingerückt in der Sidebar bei aktivem Oberpunkt |
| Globale Suche mit Tastenkürzel, Benachrichtigungsglocke, Hilfe, Datumsnavigation in einer Kopfleiste | nicht Teil der Welle | neue Fachfunktionen; Handoff verlangt «keine neue Businesslogik» |
| «Löschen» im Formularfuss | nur wo die Funktion heute existiert (sonst Archivieren/Reaktivieren) | keine neue Fachfunktion |
| Schritt-Assistent, Timer/Bild je Zubereitungsschritt, Raster-Ansicht, Duplizieren | nur wo heute vorhanden | keine neue Fachfunktion |
| «Alle als ‹nicht enthalten› setzen» und stiller Standardwert | nur mit unveränderter Speichersemantik | «Nicht ausgewählt» oder «ungeprüft» darf nie als «allergenfrei» gespeichert oder angezeigt werden; Prüfstatus wird durch die Oberfläche nicht verändert |
| Beispielwerte (Gerichte, Daten, Lieferanten, Bestände) | keine Datenquelle | Mockup-Inhalte |
| Eine Filterzeile, eine Zeile pro Datensatz, Status-Badges, Zeilenaktionen, Auswahl-Chips mit Detail nach Auswahl, «Weitere Optionen» eingeklappt, einheitlicher Formularfuss, 2–3 Spalten gross / 1 Spalte mobil | übernehmen | verbindliche Muster M21–M25 |

## Auftraggeber-Design-System v2 (2026-09-20)

Verbindliche Ergänzung aus `docs/design/design-system-v2-2026-09-20/` (SDD v2, Manifest v2, Update-Prompt, Review-Checkliste). **Vorrangregel:** Dieses Paket geht dem ersten Handoff (`docs/design/uiux-handoff-2026-09-20/`) vor. Referenzpriorität gemäss SDD v2 §19: akzeptierte Einstellungs-Screens definieren die Designsprache; generierte Mockups liefern Interaktionsprinzipien, keine pixelgenaue Vorlage; Ist-Screens belegen Fachlichkeit und Anti-Patterns. Bei Konflikt: Fachfunktion des Ist-Systems erhalten.

**Leitsatz (Manifest v2):** «So wenig UI wie möglich, so viel Information wie nötig.» Jede Ansicht folgt der Seitenhierarchie **Kontext → Status → Aufgabe → Primäraktion → Details**.

### Navigation

Drei Hauptpunkte mit Kontext-Unterpunkten in der linken Sidebar (nur sichtbar beim aktiven Hauptpunkt; keine horizontale Doppel-Navigation):

| Hauptpunkt | Unterpunkte |
|---|---|
| **Wochenplan** | Cafeteria · Patienten · Wochenübersicht · Küchenkalender |
| **Menüs & Bausteine** | Menüs · Bausteine · Zutaten · Rezepte · Kochbücher · Gerichtvorlagen · Einkaufslisten · Bestellung · Lager · Kalkulation |
| **Einstellungen** | Bereiche & Öffnungszeiten · Erscheinungsbild · Darstellung · Daten importieren · Schnittstellen · Benutzer & Zugriff |

Editor-interne Tabs oder Stepper sind zulässig, wenn sie echte Bearbeitungsschritte darstellen und keine globale Navigation duplizieren. Der bisherige Unterpunkt «Wochenverwaltung» heisst neu **«Wochenübersicht»**; URL und Endpoint bleiben unverändert.

### Statusleiste

Eigene wiederverwendbare Komponente unter dem Seitenkopf. Nur entscheidungsrelevante Angaben (z. B. Prüfstand, offene Kartenprüfungen, fehlende Allergenangaben, Veröffentlichungsstatus, Zeitraum/KW). **Statuschips dürfen direkt filtern oder navigieren** — als Link mit sichtbarem Text, nicht nur als Farbindikator. Keine Dekoration ohne Informations- oder Aktionswert.

**Statusbar-Ziele (Fundament 2):** `page_header(status_items=[…])` akzeptiert optional `href` je Eintrag. Das Ziel darf nur auf einen **vorhandenen Query-Parameter oder Anker** derselben oder einer bestehenden Seite zeigen; keine neuen Routen. Beispiel: `{'label': 'Gangprüfung', 'value': 'Offene Angaben', 'href': '#course-issues'}` auf einer Wochenplanseite mit vorhandenem `#course-issues`. Der Wert wird innerhalb des bestehenden `dd` als `.admin-statusbar-link` verlinkt, mit geerbter Wertfarbe, Unterstreichung bei Hover/Fokus, mindestens 2 px Fokus-Outline und 48 px Zielhöhe. Ohne Ziel bleibt die Ausgabe bytegleich; `dl/dt/dd`, Varianten, Text-vor-Farbe und maximal fünf Einträge bleiben erhalten.

### Bilder

In operativen Planungs- und Listenansichten nur **kleine Thumbnails** mit festem Seitenverhältnis und Lazy Loading. Grosse Bilder nur in Vorschau oder Detail, wenn visuell relevant. Keine bildschirmfüllenden Food-Fotos in der Arbeitsplanung.

### Verbotene Anti-Patterns (Manifest v2 §14)

1. horizontale Subnavigation zusätzlich zur Sidebar;
2. mehrere gleich starke Primärbuttons;
3. permanent sichtbare Sonderoptionen;
4. Status nur durch Farbe;
5. technische IDs als Hauptinformation;
6. grosse leere Karten;
7. Fullscreen-Food-Fotos in operativen Planungslisten;
8. unterschiedliche Filter-/Speicherlogik pro Modul;
9. Icons ohne Text, wenn Bedeutung nicht offensichtlich;
10. Hilfetexte, die dieselbe Information ständig wiederholen.

### Definition of Done (Manifest v2 §15)

Jede UI-Änderung ist konsistent mit bestehenden Komponenten, platzsparender als vorher, Keyboard- und Responsive-tauglich, Status und Aktionen eindeutig. Der **häufigste Workflow darf nicht länger** werden. Es existiert ein **Vorher/Nachher-Screenshot** für Review.

### Reihenfolge der Umsetzung (Update-Prompt)

1. Shell und kontextuelle Navigation
2. Statusbar, Toolbar, Filter und Actions
3. Wochenplan vollständig (Cafeteria, Patienten, Wochenübersicht, Küchenkalender, Tagesansicht)
4. Menüeditor inkl. Allergene
5. Menüs & Bausteine vollständig
6. Einstellungen ohne Verschlechterung
7. Responsive, A11y und Regression

### Abweichungen und Präzisierungen gegenüber v2

| Thema | Entscheidung |
|---|---|
| Touch-Ziele | **48 px** für zentrale Bedienelemente bleiben verbindlich (strenger als «ca. 44 px» in SDD v2 §13; erfüllt die v2-Vorgabe). |
| Allergen-Detail | Inline-Detail direkt an der gewählten Option (M21): Formulare senden Allergen und Präsenz als indexgepaarte Wiederholfelder; das Detailfeld wird deaktiviert statt versteckt und bleibt im selben Container. |
| Referenzbilder v2 | Die Ordner `accepted-settings/`, `current-modules/`, `current-weekplan/` und `generated-mockups/` fehlten in der Lieferung; bis zur Nachlieferung gilt für den Wochenplan der Text des SDD v2 §5–§6 als Zielmodell (M26–M30). |

## Auftraggeber-Polish-Lauf (2026-09-23)

Quelle: `docs/design/uiux-polish-2026-09-23/00_PROMPT_Global_UI_Polish_Run.md`. **Vorrang:** Design System v2 (M26–M30, Manifest §14–§15) und Semantic UI Language bleiben gültig; dieser Abschnitt präzisiert den app-weiten Polish-Lauf. **Leitsätze:** Einfachheit vor sichtbarer Funktionsfülle · Konsistenz vor Seitendesign · Bedienbarkeit vor Dekoration. **2–3-Sekunden-Regel:** Jede Ansicht beantwortet sofort Ort, Priorität, nächste Handlung und Zusatzinformation. **Phasen:** P0 Regelabbildung in der Designquelle · P1 App-weites Audit (lesen) · P2 Konsolidierung gemeinsamer Tokens/Komponenten · P3 Anwendung je Modul · P4 Abschlussprüfung mit Vorher/Nachher-Belegen. Definition of Done je Paket: v2-Checkliste (A31) **und** Abschlussprüfung §17 (unten).

### R-Regeln (Polish-Lauf)

#### Informationshierarchie (Prompt §3)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R11 | Primär sichtbar: Seitentitel (`page_header` H1), aktueller Kontext (Statusbar/Breadcrumb), wichtigste Information und genau eine dominante Primäraktion im Kopf. | Screenshot 360/1024/1440 px: H1 + Statusbar + Primärbutton innerhalb des ersten Viewports ohne Scroll; `templates/admin/_macros.html:11` |
| R12 | Sekundär: häufige Filter/Aktionen in `filter_bar` / Toolbar; Tertiär: Details, seltene Aktionen und technische Angaben nur in `disclosure_section`, `action_menu`, Tooltip oder Modal — nicht gleichwertig zu Primär. | DOM: tertiäre Blöcke in `<details>`/Overflow; keine dauerhaft offenen Detailfelder bei nicht ausgewählter Option (`admin-option-row .form-select:disabled`, `admin-tabler.css:453`) |
| R13 | Tertiäre Inhalte dürfen visuell nicht dieselbe Prominenz wie Primär haben (kein gleich grosser Button, keine volle Card für Zusatzinfo). | Visuell: Tertiär nutzt `btn-ghost-*`, `disclosure_section` oder `action_menu`; höchstens ein `btn-primary` je Kontext |

#### Aktionen (Prompt §4)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R14 | Pro Bereich genau eine visuell dominante Primäraktion (`btn-primary` / `icon_button` role=primary); weitere als Secondary (`btn-outline-*`) oder Tertiary (`btn-ghost-*`, Icon+Text). | `git grep` je Template: höchstens ein `.btn-primary` im `page_header`-Aktionsbereich und je `form_footer` |
| R15 | Destruktive Aktionen (`btn-danger`, Registry `role=danger`) nie gleich gestaltet wie normale Speichern/Öffnen-Aktionen; mit explizitem Label und Folgetext (`consequence_key`). | `status_badge_sem`/`icon_button` mit `actions.delete`: sichtbares Label + `ui-sem-consequence`; kein `btn-primary` für Löschen |
| R16 | Kleine/häufige Aktionen als Icon+Text, `icon_button` oder `action_menu` — keine Reihe gleich starker Buttons. | Zeilenaktionen: `list_row` + maximal eine sichtbare Primärzeilenaktion; Rest in `action_menu` (`_semantic.html:56`) |

#### Textreduktion (Prompt §5)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R17 | Permanente Hilfetexte nur wenn ohne sie die Aufgabe scheitert; sonst Tooltip (`data-bs-title`), `disclosure_section` oder Entfernen. | Seiten ohne Absätze >120 Zeichen unterhalb des Titels ausser Validierungs-/Fehlerhinweisen |
| R18 | Labels handlungsorientiert und kurz; bevorzugt Icon + kurzes Label statt Erklärungssatz. | Registry-Labels (`label_key`) ≤3 Wörter für Hauptaktionen; `test_ui_hardcoded_strings_report.py` Trend |

#### Formulare (Prompt §6)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R19 | Zusammengehörige Felder gruppieren (`admin-option-group`, `fieldset`, `disclosure_section`); keine isolierten Einzelfelder über volle Breite ohne Grund. | Formular-Grid: verwandte Inputs im selben Flex/Grid-Container (`admin-compact-line`, `admin-option-grid`) |
| R20 | Mehrspaltigkeit ab **768 px** (2 Spalten), ab **1440 px** (3 Spalten) für Options-/Chip-Gruppen; unter 768 px einspaltig. | CSS Breakpoints `admin-tabler.css:475–479`; Browser 360 vs 768 vs 1440 px |
| R21 | Validierung am Feld: `.is-invalid`, `.invalid-feedback` direkt am Control; Fehler öffnet betroffenes `disclosure_section` (`has_error=true`). | POST mit Fehler: Fokus auf erstes `.is-invalid`; geschlossenes Detail öffnet (`M19`, `disclosure_section` Makro) |

#### Statusdarstellung (Prompt §7)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R22 | Sechs konsistente Statusstile: neutral, aktiv, erfolgreich, Warnung, Fehler, Information — jeweils Icon + kurzer Text, keine grossen Warnboxen wenn Badge/Inline reicht. | Status nutzt `status_badge_sem` oder `admin-statusbar-item--*`; keine `.alert` für reinen Zeilenstatus |
| R23 | Statusbar-Slots (`admin-statusbar-item--neutral/success/warning/danger`) nur für entscheidungsrelevante Werte (1–5 Slots). | `page_header` `status_items`: 1–5 `.admin-statusbar-item`; Varianten aus erlaubter Liste (`_macros.html:15`) |
| R24 | Status nie nur durch Farbe: immer sichtbarer Text/Label; Registry-Schlüssel `status.*` mit `label_key`. | Axe/ manuell: Badge/Statusbar enthält Textnode; `data-semantic` gesetzt |

#### Platznutzung (Prompt §8)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R25 | Volle Arbeitsbreite: kein künstlicher `max-width`-Wrapper im Hauptbereich; Seitenpadding höchstens `--app-page-padding` (32/24/16 px). | Computed style `.admin-main`: `max-width: none`; padding = Token (`tokens.css:181–188`, `admin-tabler.css:48–49,549–552`) |
| R26 | Obergrenzen Dichte: Listenzeile Padding vertikal `var(--app-space-2)` (8 px); Bedienelemente min-height **48 px**; Topbar `--app-topbar-min-height` **64 px**; Abschnittsabstand höchstens `var(--app-space-3)` (12 px) ausser bei Fehlerblöcken. | Messung DevTools: `.admin-list-row` padding; `.btn` min-height 48 (`admin-tabler.css:124,468`); `--app-topbar-min-height` (`tokens.css:173`) |
| R27 | Keine leeren Riesen-Cards: Card-Innenabstand `--app-card-inset` (`var(--app-space-6)` compact / `var(--app-space-8)` comfortable), nicht weiter aufblähen. | `data-density` auf `.admin-main`; Card ohne Inhalt >50 % Leerfläche im Screenshot = Verstoß |

#### Icons (Prompt §9)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R28 | Icons nur über Registry/Sprite (`sem_icon`, `icon` Makro, `tabler-{{ name }}`); gleiche Semantik = gleiches Symbol projektweit. | `test_ui_semantics.py`: Registry-Keys, Assets, verbotene Icon-only-Aufrufe |
| R29 | Wichtige Aktionen nicht icon-only ohne Erlaubnis (`icon_only_allowed=yes` in Registry); Navigation immer Icon + Text. | `icon_button` mit `icon_only=false` für `icon_only_allowed=no`; Sidebar-Links mit sichtbarem Text |

#### Navigation (Prompt §10)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R30 | Keine doppelte Navigation (Sidebar + horizontale Modul-Tabs); aktiver Bereich eindeutig (`admin-sidebar` active state, Einrückung Unterpunkte). | Kein zweites Nav-`<nav>` auf Modulebene; aktiver `.nav-link` mit Indikator (`admin-tabler.css:96–105`) |
| R31 | Unterpunkte nur bei aktivem Hauptpunkt sichtbar; kompakte Einrückung, min-height 48 px. | Sidebar DOM: `.admin-nav-subitems` nur unter aktivem Oberpunkt |

#### Responsive (Prompt §11)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R32 | Desktop (≥992 px): volle Breite, Mehrspalten-Grids, Status+Toolbar sichtbar. | Viewport 1440 px: kein horizontaler Scroll; Grid ≥2 Spalten wo fachlich sinnvoll |
| R33 | Tablet (768–991 px): Spalten reduzieren, Touch-Ziele 48 px, Filter umbrechen. | 768 px: `admin-filter-bar` wrap; Buttons min-height 48 |
| R34 | Mobile (<768 px): lineare Struktur, unwichtige Details eingeklappt; Tabellen → Listen/Karten statt Miniatur-Desktop. | 360 px: keine Tabelle mit horizontalem Scroll ohne Umschaltmuster; Primäraktion im Kopf erreichbar |

#### Interaktion (Prompt §12)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R35 | Hover/Focus/Active für alle klickbaren Elemente: `:hover`, `:focus-visible` (2 px `--app-focus`), `:active` auf Links/Buttons (`admin-tabler.css:209–221,320`). | Tastatur-Tab durch Seite: sichtbarer Fokusring; Hover in Desktop-Screenshot |
| R36 | Disabled klar unterscheidbar (`--tblr-btn-disabled-*`, `:disabled` Form-Controls mit `--app-surface-soft`). | `.btn:disabled` Kontrast; keine pointer-events auf aktiven Controls |
| R37 | Loading/Success/Error-Feedback: Form `.is-invalid`/`.alert-*`; keine dekorativen Animationen. | Fehler-POST zeigt `.alert-danger` oder Feldfehler; Ladezustand zu prüfen (P1-Audit) |

#### Accessibility (Prompt §13)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R38 | Kontrast WCAG 2.2 AA auf Token-Kombinationen (Text/Status siehe §5 Palette — unverändert lassen). | `test_ui_master_tokens_browser.py`; manuell 200 % Zoom |
| R39 | Tastatur: sinnvolle Tab-Reihenfolge, Skip-Link, Fokus nicht von Sticky-Leiste verdeckt (`admin-form-footer` wechselt bei Fokus zu `static`). | Tab-Flow-Test; `admin-tabler.css:481–483` |
| R40 | Labels für alle Controls; Status mit Text; semantisches HTML (`<button>`, `<details>`, `aria-label` bei Icon-only). | axe-Scan; `aria-label` auf `icon_button` icon-only |

#### Technik (Prompt §14)

| ID | Regel | Prüfbar durch: |
|---|---|---|
| R41 | Kein neues Frontend-Framework; bestehende Templates/CSS/JS/Tabler wiederverwenden und vereinheitlichen. | Diff: keine neuen UI-Dependencies; Änderungen in `admin-tabler.css`, `_macros.html`, `_semantic.html` |
| R42 | Neue Abstraktion nur wenn ≥2 Stellen vereinfacht; keine Migration als Nebenprodukt. | PR-Beschreibung nennt betroffene Makros; keine DB-/API-Änderung |

### M-Muster — verbindliches Kleinst-Designsystem (Prompt §2)

**P2 Aktionsvertrag:** Primär `btn btn-primary` (genau eine je `main`, P3 prüft
die Modul-Aufrufer), sekundär `btn` oder `btn-outline-*`, tertiär `btn btn-ghost`
oder `icon_button` mit Kurztext bzw. erlaubtem Icon-only samt Tooltip. Destruktiv
`btn btn-danger` mit Icon, Label und Folgetext; `confirm_dialog` prüft
`consequence_key` vor Ausgabe für Titel- und Bestätigungsrolle. `form_footer`
erhält zusätzlich `secondary` und `danger`: häufige Aktionen in `admin-form-main`,
seltene in geschlossenem `details.admin-form-rare` mit `admin-form-tertiary`,
destruktive separat in `admin-form-danger`. Bestehende Positionsargumente bleiben.

**P2 gemeinsame Klassen/Verträge:**
- `admin-status--{neutral,active,success,warning,danger,info}` gilt für Badges und
  Statusbar-Inhalte; `admin-statusbar-item--*` bleiben kompatible CSS-Aliase.
  `status_badge_sem` und `status_bar` liefern Icon + sichtbaren Text. Legacy-
  `page_header` ohne explizites Icon bleibt bytegleich; P3 ergänzt dort `icon`.
- `admin-option-grid`: ein Wrapper je `field`/`select`, 1/2/3 Spalten unter
  768/ab 768/ab 1440 px. Label-Abstand `--app-space-1`, Controls ≥48 px,
  Checkbox-/Radio-Zeilen ≥44 px; `.is-invalid` mit zugeordneter `.invalid-feedback`.
- `table.admin-table--stack`: semantische Header (`scope`) und `data-label` je
  Datenzelle; unter 768 px gestapelte Zeilen. `--app-table-row-height: 56px`
  ist Desktop-Standard; mehrzeilige Inhalte, Fehlermeldungen und 200%-Text dürfen
  Zeilen vergrössern. Keine feste Clip-Höhe. P3 migriert die Modul-Tabellen.
- `.card .card` ist flach ohne zweiten Rahmen/Schatten. H1/H2/H3 nutzen
  `--app-font-size-h1`/`--app-font-size-h2`/`--app-font-size-h3` (34/20/18 px,
  H1 mobil 28 px). Seitenkopf einschliesslich Statusbar ≤200 px bei 1440 px mit
  kurzen Werten; lange Übersetzungen/Zoom bleiben vollständig lesbar.
- `form[data-loading]` aktiviert beim nativen Submit `admin-btn-loading`,
  `disabled` und `aria-busy` am Primärbutton, auch bei externer Form-Zuordnung.
  Deaktivierung erfolgt nach Serialisierung von `name/value`; abgebrochene oder
  ungültige Submits bleiben bedienbar. `pageshow` stellt den vorherigen Zustand
  wieder her. AJAX-Aufrufer übernehmen ihren eigenen Abschluss-/Fehlerzustand.
  Das Label bleibt sichtbar; Spinner nur während Submit, bei Reduced Motion statisch.
  `--app-focus-width: 2px`, Hover-/Active-Tokens und gestrichelte Disabled-Ränder
  sichern erkennbare Interaktion ohne verringerte Textdeckkraft.
- `hint(text, id, mode='tooltip')`: eindeutige ID vom Aufrufer; Standard ist
  `info-circle` mit `title`, `aria-describedby` und nativem `details`-Fallback.
  `mode='dialog'` ergänzt ein modales Dialogfenster mit Escape/Fokusrückgabe;
  ohne JS bleibt es im `details` erreichbar. `mode='inline'` für Sicherheits-
  informationen. Bestehende `field(..., hint=...)` bleiben bis P3 kompatibel inline;
  «Nicht ausgewählt bedeutet nicht: allergenfrei bestätigt.» bleibt immer sichtbar.

| ID | Baustein | heutige Umsetzung (Datei/Makro/Klasse) | Sollzustand | Lücke |
|---|---|---|---|---|
| M31 | Seitenabstände | `--app-page-padding` in `admin-tabler.css:48,497`; Tablet/Mobile `549–552` | 32/24/16 px nach Breakpoint, volle Breite | Erledigt: bestehende Padding-/Breiten-Gates; Modulprüfung P3 offen |
| M32 | Vertikale Abstände | `--app-space-1`…`--app-space-12` in `tokens.css:181–188` | Skala 4–48 px; Abschnitte ≤`--app-space-3` | Erledigt: gemeinsame Token-Abstände; Abschnittsmigration P3 offen |
| M33 | Horizontale Abstände | `gap: var(--app-space-2)` in Listen/Filter (`admin-tabler.css:461`) | Einheitlich `--app-space-2` in Toolbars | Erledigt: btn-list/Toolbar-Gaps über --app-space-2; P3 offen |
| M34 | Grid | `admin-option-grid` 1/2/3 Spalten (`admin-tabler.css:439,475–479`) | Responsive Grid ab 768/1440 px | Erledigt: Grid 1/2/3 bei 360/768/1024/1440/1920 px geprüft |
| M35 | Content-Breiten | Kein Shell-`max-width`; Preview `data-content-width` (`admin-tabler.css:546–547`) | Hauptarbeit immer `full` | Erledigt: gemeinsame Shell unverändert; P3-Seitenprüfung offen |
| M36 | Schriftgrössen | `--app-font-size-*` `tokens.css:163–168`; Skalierung `--app-font-scale` | Body 1 rem, H1 2.125/1.75 rem mobil | Erledigt: H1/H2/H3-Tokens und Skalierung geprüft |
| M37 | Schriftgewichte | Fira 400–700 `@font-face` `tokens.css:241–270` | Labels 600, Werte 700 in Statusbar | Erledigt: Fira-/Label-Vertrag erhalten |
| M38 | Überschriftenhierarchie | `h1`/`h2`/`h3` in `admin-tabler.css:368–369`; `page_header` | Eine H1 je Seite, Titel > Card-Titel | Erledigt: H1 34/28, H2 20, H3 18 px; Kopf mit Status <=200 px bei 1440 |
| M39 | Farben | `.dishboard-admin` Token-Block `tokens.css:111–160` | Nur `--app-*` / `--sh-*` Aliase | Erledigt: Palette unverändert; sechs Statuskontraste >=4.5:1 |
| M40 | Hintergrundflächen | `--app-bg`, `--app-surface`, `--app-surface-soft` | Canvas + weisse Arbeitsflächen | Erledigt: vorhandene Flächentokens wiederverwendet |
| M41 | Rahmen | `--app-border`, `--app-border-soft`; Cards/Inputs 1 px | Ruhige 1-px-Kanten, keine Doppelrahmen | Erledigt: verschachtelte Cards ohne zweiten Rahmen |
| M42 | Radius | `--app-radius-control` 8 px, `--app-radius-card` 12 px (`tokens.css:177–178`) | Controls 8 px, Cards 12 px | Erledigt: bestehende Radius-Tokens erhalten |
| M43 | Schatten | `--app-card-shadow` (`tokens.css:189`) | Dezent, keine Schmuckschatten | Erledigt: verschachtelte Cards ohne Schatten |
| M44 | Buttons | Tabler `.btn-*` themed in `admin-tabler.css:135–162` | Primary/Outline/Ghost/Danger konsistent | Erledigt: vier Aktionsstufen; genau eine Primäraktion je main in P3 prüfen |
| M45 | Icon-Buttons | `icon_button` in `_semantic.html:17`; `ui-sem-control` 48 px | 48 px, Tooltip+aria bei icon-only | Erledigt: bestehender 48-px-/Tooltip-/Aria-Vertrag erhalten |
| M46 | Badges | `.badge.bg-*-lt` `admin-tabler.css:265–312`; `status_badge_sem` | Icon + Text, Soft-Background | Erledigt: status_badge_sem nutzt admin-status--* mit Icon und Text |
| M47 | Statusanzeigen | `admin-statusbar-*` `admin-tabler.css:509–545`; `status_bar` `_semantic.html:85` | 6 Stile; kompakt unter Titel | Erledigt: sechs Stile samt --info/--active; semantische Icons; Legacy ohne Icon unverändert |
| M48 | Inputs | `.form-control` themed `admin-tabler.css:175–178` | 48 px Höhe, Fokus `--app-focus` | Erledigt: >=48 px, 4-px-Labelabstand und feldnahe Fehler geprüft |
| M49 | Selects | `.form-select` gleiche Regeln | Wie Inputs | Erledigt: >=48 px und Grid geprüft |
| M50 | Checkboxen/Radios | `.form-check-input` min-height 48 px | Inline in `admin-option-label` | Erledigt: Checkbox-/Radio-Zeilen >=44 px (bestehend 48 px) geprüft |
| M51 | Tabellen | `.table` Token `admin-tabler.css:487` | Kompakte Zeilen, lesbare Header | Erledigt: admin-table--stack und 56-px-Zeilentoken; Modulübernahme P3 offen |
| M52 | Cards | `.card` Spacer `admin-tabler.css:304–310` | `--app-card-inset`, kein Card-in-Card | Erledigt: .card .card ohne Rahmen/Schatten; Strukturabbau in P3 offen |
| M53 | Dialoge | `confirm_dialog` `_semantic.html:74`; Tabler Modal | Bestätigung mit Folgetext | Erledigt: danger verlangt consequence_key; bestehende Modul-Modals in P3 prüfen |
| M54 | Dropdowns | Bootstrap Dropdown/Select; `action_menu` als `<details>` | Seltene Aktionen gebündelt | Erledigt: seltene Footer-Aktionen in geschlossenem details; P3 offen |
| M55 | Accordions | `disclosure_section` `_macros.html:445`; `admin-disclosure` | Natives `<details>`, auto-open bei Fehler | Erledigt: native Fehler-/Inhaltsöffnung bleibt regressionsgeprüft |
| M56 | Navigation | Sidebar `admin-sidebar`; `page_header` Breadcrumb | 3 Hauptpunkte, Kontext-Unterpunkte | Offen P3: Seiten-/Navigationsprüfung; Shell in P2 unverändert |
| M57 | Tooltips | `data-bs-toggle="tooltip"` in `icon_link` `_macros.html:8` | Für icon-only und Zusatzinfo | Erledigt: hint(text, id, mode) mit Tooltip-/Details-Fallback; P3-Migration offen |
| M58 | Leere Zustände | `empty_state` `_macros.html:248`; `empty_state_sem` `_semantic.html:65` | Art unterscheiden (keine Daten/Treffer/Recht) | Erledigt: bestehende differenzierte Leerzustände erhalten; Modulaudit P3 offen |
| M59 | Ladezustände | zu prüfen (P1-Audit) | Tabler-Spinner/Button-disabled während Submit | Erledigt: form[data-loading], admin-btn-loading, pageshow-Reset; P3-Opt-in offen |
| M60 | Fehlermeldungen | `.alert-danger`, `.is-invalid` | Konkret am Feld + optional Alert | Erledigt: is-invalid + invalid-feedback am Feld; Fehlertexte bleiben Modulbesitz |
| M61 | Erfolgsmeldungen | `.alert-success` `admin-tabler.css:299` | Kurz, nach Aktion, nicht dauerhaft | Erledigt: vorhandene Erfolgsstile erhalten; tatsächliches Aktionsfeedback in P3 prüfen |
| M62 | Warnungen | `.alert-warning`; Statusbar `--warning` | Badge/Inline vor grosser Box | Erledigt: gemeinsamer Warning-Stil mit Icon/Text; P3-Einsatz offen |
| M63 | Information | `.alert-info`; `status.info` Registry | Neutral/informativ, nicht warnend | Erledigt: status.info und admin-statusbar-item--info; P3-Einsatz offen |

### A-Anti-Patterns (Prompt §1)

| ID | Woran erkennbar | Ersatz |
|---|---|---|
| A32 | Grosse leere Randflächen, schmaler Inhaltssäule | R25: volle Breite + `--app-page-padding` |
| A33 | Überhohe Blöcke/Cards mit wenig Inhalt | R27, M52: kompakte Zeilen/`admin-list-row` |
| A34 | Zu viele gleichzeitig sichtbare Informationen | R11–R13: Primär/Sekundär/Tertiär trennen |
| A35 | Inkonsistente Abstände zwischen gleichartigen Elementen | M31–M33: Token-Skala |
| A36 | Inkonsistente Buttons (verschiedene Stile für gleiche Aktion) | R14, M44: Registry + `btn-*` Rollen |
| A37 | Inkonsistente Formularfelder | M48–M50: gemeinsame `.form-*` Regeln |
| A38 | Zu viele Rahmen/Boxen, Card-in-Card | R09, M52: eine Card-Ebene, Listen statt Karten-Reihen |
| A39 | Wiederholte Information (Titel + Status + Hinweis identisch) | R17: ein Kanal pro Fakt |
| A40 | Schlechte visuelle Hierarchie (alles gleich gross) | R11, M38: H1 > Titel > Body |
| A41 | Unklare Hauptaktion (kein oder mehrere Primary) | R14, A26 |
| A42 | Konkurrierende gleich starke Aktionen in einer Reihe | R16, `action_menu` |
| A43 | Unnötiger permanenter Erklärungstext | R17, Tooltip/`disclosure_section` |
| A44 | Lange Textwände unter dem Titel | R17, R18 |
| A45 | Inkonsistente Icons für gleiche Bedeutung | R28, Semantic Registry |
| A46 | Schlechtes Alignment (Labels/Felder/Aktionen) | Flex/Grid-Makros `list_row`, `form_footer` |
| A47 | Schlechte Breitennutzung auf Desktop | R25, R32 |
| A48 | Desktop-Layout nur verkleinert auf Mobile | R34, eigene Mobile-Struktur |
| A49 | Informationen die einklappbar wären, dauerhaft offen | R12, `disclosure_section` |
| A50 | Technisch funktionierend, aber unnötig kompliziert/altmodisch | Polish-Lauf §16: IA/Gruppierung, nicht nur Skin |

### Abschlussprüfung §17 (je Ansicht)

Vor Abnahme jede Ansicht anhand dieser zehn Fragen prüfen (ergänzt A31/v2-DoD, ersetzt sie nicht):

1. Ist sofort klar, worum es geht?
2. Ist die wichtigste Aktion sichtbar?
3. Gibt es unnötige Informationen?
4. Gibt es unnötigen Leerraum?
5. Gibt es zu viele Buttons?
6. Sind ähnliche Funktionen konsistent?
7. Sind Statusinformationen verständlich?
8. Ist die Ansicht auf Desktop gut genutzt?
9. Ist sie auf Mobile sinnvoll bedienbar?
10. Wirkt sie wie dieselbe Anwendung wie alle anderen Ansichten?

Verbleibende Inkonsistenzen vor Merge selbst beheben oder als P1-Fund dokumentieren.

### Icon-Zuordnung Prompt §9

| Kategorie | Registry-Key / Tabler-Icon | Anmerkung |
|---|---|---|
| Hinzufügen/Anlegen | `actions.add` / `plus`, `actions.add_existing` / `circle-plus` | — |
| Bearbeiten | `actions.edit` / `edit` | — |
| Löschen | `actions.delete` / `trash` | immer mit Label |
| Speichern | `actions.save` / `device-floppy` | — |
| Zurück/Weiter | `actions.back` / `arrow-left`, `actions.next` / `arrow-right` | — |
| Öffnen/Schliessen | `actions.open` / `chevron-right`, `actions.close` / `x` | — |
| Prüfen/Bestätigen | `actions.confirm` / `check` | — |
| Warnung/Fehler/Info | `status.warning` / `alert-triangle`, `status.error` / `circle-x`, `status.info` / `info-circle` | — |
| Suche/Filter | `view.search` / `search`, `view.filter` / `filter` | — |
| Sortierung | — | **Sprite-Bedarf:** kein `view.sort` in Registry |
| Einstellungen | `navigation.settings` / `settings` | — |
| Mehr | `actions.more` / `dots` | — |
| Kalender | `time.date` / `calendar`, `time.week` / `calendar-week` | — |
| Benutzer | `admin.user` / `user` | — |
| Drucken/Download/Upload | `actions.print` / `printer`, `actions.download` / `download`, `actions.upload` / `upload` | — |
| Sichtbarkeit | `actions.preview` / `eye`, `publish.hidden` / `eye-off` | kein dediziertes `view.visibility` |
| Kopieren/Verschieben | `actions.copy` / `copy`, `actions.move` / `arrows-move` | — |

### Offene Sprite-/Registry-Bedarfe aus §9

- `view.sort` (Sortierung) — Tabler-Icon festlegen und Registry ergänzen
- `view.visibility` (Sichtbarkeit umschalten) — oder bestehende `eye`/`eye-off`-Semantik dokumentieren
- Erledigt P2: `status.neutral` mit vorhandenem `circle-dashed`; `circle-dot` ist
  im ausgelieferten Sprite nicht enthalten. Bestehende Status-Seeds bleiben erhalten.
- Erledigt P2: `admin-statusbar-item--info` und `--active` (R22).
- Erledigt P2: gemeinsames Submit-Lademuster (R37, M59); Modul-Opt-in bleibt P3.

### Nicht-Ziele

Kein neues Frontend-Framework, keine technische Migration, keine fachlichen Änderungen, keine Datenbankmigration, kein Ersetzen der v2- oder Semantic-Pakete — nur Vereinheitlichung und Verdichtung im bestehenden Tabler/Flask-Stack.

## Auftraggeber-Paket Semantic UI Language (2026-09-20)

Verbindliche Quelle: `docs/design/semantic-ui-language-2026-09-20/`, einschliesslich
`IMPORT_NOTES.md`. Dieses Paket präzisiert Icon-/Label-Regeln; Fachlichkeit,
Berechtigungen, URLs, Datenverträge und die bestehenden M21–M30 bleiben erhalten.

**Modell:** `semantic_key → icon → resolved_icon → label_key → tooltip_key → aria_key
→ erlaubte Darstellung → Rolle`. Die Laufzeit-Registry enthält keine übersetzten
sichtbaren Texte. Die 184 Seed-Semantiken bleiben erhalten; vollständige Nachrichten
für zusätzliche Zustände werden zentral ergänzt, nicht in Templates erfunden.

**Fundament 2 (2026-09-23):** Die Admin-Shell lädt `ui-semantic.css` einmal direkt
nach `admin-tabler.css` und vor Marken-Stylesheets; `html.lang` folgt `ui_locale`
(Fallback `de`). Die eigenständige Druck-Fehlerseite behält ihren eigenen CSS-Link.
Die Projektschlüssel `ui.disclosure.details` («Details») und
`ui.disclosure.more_options` («Weitere Optionen») gelten ausschliesslich für
Aufklappbereiche, mit vorhandenem `chevron-right` und DE/EN-Label/Aria/Tooltip.
Die 184 Auftraggeber-Seeds bleiben unverändert. `disclosure_section()` löst seinen
Default zur Renderzeit auf; explizite Titel bleiben möglich. Overflow nutzt
`actions.more` («Weitere Aktionen»). `_macros.html` verwendet `t()`/`sem()` direkt,
weil `_semantic.html` diese Makros bereits importiert; kein Importzyklus.

**Kanonische Verben:** Anlegen = neues Objekt; Hinzufügen = bestehendes Objekt
zuordnen; Bearbeiten = ändern; **Öffnen ersetzt Ansehen** für reines Lesen;
Speichern = persistieren; Bestätigen = Entscheidung bestätigen; Löschen = destruktiv
entfernen; Archivieren = aufbewahren, aus aktiver Nutzung nehmen; Kopieren = Duplikat;
Vorschau = Ausgabe prüfen. Gleiche Bedeutung verwendet denselben Schlüssel.

**Darstellungsstufen:** Icon-only ausschliesslich bei expliziter Registry-Erlaubnis,
immer mit übersetztem `title` und `aria-label`; sonst Icon + kurzes Label.
Destruktive Aktionen benötigen Icon + explizites Label + Folgetext. Navigation bleibt
Icon + Text. Status besitzt sichtbaren Text; Farbe ergänzt nur. Bedienziele mindestens
48 × 48 px, sichtbarer Tastaturfokus, native Bedienbarkeit ohne JavaScript.

**Polish P2 (2026-09-23):** 184 unveränderte Seeds + 10 Projektschlüssel = 194.
Neu `status.neutral` mit DE/EN-Label/Aria/Tooltip und vorhandenem `circle-dashed`.
`status.active` und `status.info` bleiben unverändert; ihre Präsentation nutzt
`admin-status--active` bzw. `admin-status--info`. Rollen-/Registry-Schema bleibt
gleich. Erfolgreich/Warnung/Fehler werden aus der Rolle abgeleitet; andere Rollen
bleiben neutral. Sechs Statusstile haben sichtbaren Text und Kontrast ≥4.5:1.
`confirm_dialog` prüft die Konsequenz für Titel- und Bestätigungsrolle, bevor
Dialog-Markup ausgegeben wird. Semantische Statusbar-Aufrufer liefern das Icon;
Legacy-Aufrufer behalten ihren bestehenden Markup-Vertrag bis zur P3-Migration.

**Symbolreihenfolge:** Kostform → Allergene → Eigenschaften → Prüf-/Status.
Fehlende und ungeprüfte Allergendaten erhalten einen eigenen Texthinweis. Sie sind
keine Bestätigung von Allergenfreiheit. Deklarierte Präsenz bleibt Teil der Anzeige.

**Mehrsprachigkeit:** DE primär, EN zweite Seed-Locale. `UI_LOCALE` wählt nur
vorhandene Locales; kein Sprachschalter und keine URL-/Cookie-Auswahl. `t(key, **params)`
verwendet vollständige Message-Keys und benannte, escapte Parameter. Entwicklung/Test
zeigt fehlende Übersetzungen als `⟦key⟧` mit Warnung; Produktion nutzt DE-Fallback und
warnt einmal je Schlüssel. Test-Locale `xx` wird zur Laufzeit verlängert. Schlüssel,
Locale-Symmetrie, Assets und Icon-only-Politik werden beim App-Start validiert.

**Icon-Fallback:** Ziel-Icon bleibt dokumentiert; `resolved_icon` benennt das
ausgelieferte Symbol. Fehlende Tabler-Icons erhalten ausschliesslich zentrale,
bewusste Ersatzzuordnungen. Ein neutrales Ersatzsymbol erzwingt Text. Geprüfte eigene
Food-SVGs haben bei Allergenen und vorhandenen Kostformen Vorrang. Sprite-Erweiterung
ist ein separates Paket mit Herkunfts-/Lizenznachweis.

**Makros** in `templates/ui/_semantic.html` (Schlüssel sind Registry-Keys):

```jinja
sem_icon(key)
icon_label(key)
icon_button(key, href=none, name=none, value=none, icon_only=false,
            type='submit', id=none, form=none, consequence_key=none)
status_badge_sem(key)
symbol_row(diets=[], allergens=[], properties=[], status=[])
diet_icon(key)
allergen_icon(key, presence=none, checked=false)
action_menu(items)
empty_state_sem(key, description_key=none, action_key=none, href=none)
confirm_dialog(key, consequence_key, confirm_key, id='semantic-confirm',
               open=false, name=none, value=none, form=none)
status_bar(title_key, items=[], description_key=none, actions=none)
filter_bar_sem(action, search_name='q', search_value='', filters=none,
               more_filters=none, active=false, reset_url=none, id='filters')
```

StatusBar delegiert an `page_header(status_items=…)`, FilterBar an `filter_bar`.
Bestehende gemeinsame Makros werden nicht doppelt implementiert. Ihre noch festen
deutschen Labels bleiben bis zur Migration durch ihren Eigentümer dokumentierter
Nachzug. ConfirmDialog ist ein Markup-Baustein für vorhandene Bestätigungsflüsse,
keine neue Bestätigungsseite, kein neues Submit-/CSRF-Verhalten.

**Nachweise:** `test_ui_semantics.py` prüft Registry, reale Assets, Locales,
Fehlerschlüssel, Fallback, Escaping, Pseudo-Länge und verbotene Icon-only-Aufrufe.
`test_ui_semantic_macros_browser.py` prüft echte Browser mit eigenem Playwright-Start:
DE/EN/xx bei 360/768/1024/1440 px, Namen, Tooltips, Fokus, native Tastaturbedienung,
48-px-Ziele, Symbolreihenfolge und Reflow. `test_ui_hardcoded_strings_report.py`
misst übrige Templates; ausschliesslich die migrierte Beweis-Seite hat Nulltoleranz.
Zusätzlich gelten bestehende Shell-/Public-/Signage-/Factory-Gates.

Abgleich gemäss `IMPORT_NOTES.md`:

| Thema | Befund | Verbindliche Folge |
|---|---|---|
| Icon-Verfügbarkeit | 35 lokale Symbole; 118 von 143 Ziel-Icons fehlen | Zentrales Mapping; Sprite separat erweitern |
| Allergen-Icons | Eigene geprüfte Food-SVGs vorhanden | Diese statt Tabler verwenden |
| Verb Öffnen | Frühere Regel verwendete Ansehen | Öffnen für Lesen, Bearbeiten für Ändern |
| Bedienziele | Paket nennt ungefähr 44 px | Strengere Projektvorgabe 48 px bleibt |
| Allergen-Editor | Paket zeigt separate Detailliste | M21: Inline-Detail, indexgepaarte Felder, deaktiviert statt versteckt |
| Mehrsprachigkeit | Bisher keine zentrale Übersetzungsschicht | Registry + Resolver + Makros vor Modul-Migration; keine neue Abhängigkeit |
| Doppelte Labels | Sieben deutsche Labels mehrfach | Zulässig bei verschiedener Semantik; Schlüssel müssen eindeutig sein |

## 1. Dein Auftrag

Migriere das bestehende Frontend auf das hier festgelegte Designsystem. Setze die Änderungen im Repository um; liefere nicht lediglich Vorschläge oder ein weiteres Konzept.

Arbeite von gemeinsamen Grundlagen zu den einzelnen Seitentypen: Design-Tokens, Tabler-Anbindung, Layout, Navigation, Komponenten und danach sämtliche betroffenen Tools und Routen. Eine Referenzseite dient der Entwicklung und Prüfung des Standards, nicht als Begrenzung des Auftrags.

**Gleiche Gestaltung bedeutet gemeinsame Komponenten und Regeln. Es bedeutet nicht, jede Seite in dasselbe Formular-plus-Tabelle-Layout zu zwingen.**

Erhalte Geschäftslogik, Daten, Berechtigungen und bestehende Bedienabläufe. Erfinde keine Funktionen, Datenspalten, Pflichtfelder, Zeichenlimits, Menüpunkte oder Statuswerte. Verändere keine API-Verträge und führe keine Datenbankmigration als Nebenprodukt der Gestaltung durch.

Die Farben in diesem Dokument sind die vorgeschlagene gemeinsame Anwendungspalette. Sie sind kein Nachweis einer offiziell freigegebenen Corporate-Design-Farbdefinition.

Die Nutzerentscheidung vom 13. September ersetzt frühere Breiten-, Dichte- und Navigationsvorgaben an ihrer jeweiligen Stelle in diesem Manifest. Alle internen Arbeitsseiten nutzen die volle verfügbare Breite. Nur kurze einzelne Felder oder sinnvoll begrenzte Lesetexte dürfen lokal schmal bleiben, niemals der gesamte Seiten- oder Formulararbeitsbereich. Das Manifest ist die einzige zentrale Quelle; kein paralleles Designsystem und keine separate Stilwelt pro Seite.

**Entscheidungsreihenfolge:** Korrekte Daten und sichere Bedienung → unveränderter Unterbau → verständliche Aufgabenführung → volle Arbeitsbreite und kompakte Inhalte → konsistente Gestaltung.

Versteckte Warnungen, verlorene Werte und eine breite Hülle mit weiterhin riesigen Zutatenblöcken erfüllen den Auftrag nicht. Bestehende Freigaben und Dateiverantwortlichkeiten erhalten; ein konkreter Werkzeug- oder Fachblocker stoppt nur den betroffenen Teil. Unabhängige zulässige Arbeit weiterführen.

### 1.1 Verbindliche Regeln R01–R10

| ID | Regel | Konkrete Umsetzung |
|---|---|---|
| R01 | Volle Arbeitsbreite | Hauptbereich rechts der Navigation vollständig nutzen; keine schmalen inneren Gesamtwrapper und kein `100vw` über die Sidebar hinweg. Verschärft durch Polish-Lauf: R25, R26. |
| R02 | Inhalt statt Verwaltungswand | Nach kompaktem Kopf und notwendiger Orientierung kommt die eigentliche Arbeit. Keine lange Strecke aus Hinweisen, Einrichtung und doppelten Aktionen davor. Verschärft durch Polish-Lauf: R11. |
| R03 | Kompakte wiederholte Objekte | Eine Arbeitszeile pro Zutat, Schritt, Baustein oder Zuordnung. Zusatzfelder nur bei Bedarf; nicht eine hohe offene Card je Objekt. *(präzisiert am 2026-09-20: siehe Auftraggeber-Ergänzung / Muster M21, M23)* Verschärft durch Polish-Lauf: R25, R27. |
| R04 | Häufige Änderungen unmittelbar | Menge und Einheit direkt in der Zutatenübersicht ändern. Eine einfache Änderung darf keine zusätzliche Klickstrecke benötigen. |
| R05 | Verständliche Symbole | Tabler-Icon plus kurzer sichtbarer Text für Navigation und Hauptaktionen. Gleiche Bedeutung überall gleich darstellen. Verschärft durch Polish-Lauf: R28, R29. |
| R06 | Sichere Detailbereiche | Auf-/Zuklappen speichert und verwirft nichts. Neue oder fehlerhafte Einträge passend öffnen. Gefüllte Zusatzangaben im Kurztext erkennbar lassen. *(präzisiert am 2026-09-20: siehe Auftraggeber-Ergänzung / Muster M21, M25)* Verschärft durch Polish-Lauf: R13, R21. |
| R07 | Wahrheitsgetreue Zustände | Gespeichert, geprüft und veröffentlicht unterscheiden. Fehlende Angaben nicht durch einen allgemeinen grünen Haken verdecken. *(Ersetzt am 2026-09-20 durch: Statusbar als globales Designsystem mit 1–5 echten Slots zentral unter dem Titel; die frühere Angabe 3–5 ist damit abgelöst. Warnungen immer mit Text, Farbe nie alleiniger Träger. Keine erfundenen Daten.)* Verschärft durch Polish-Lauf: R22, R23, R24. |
| R08 | Erreichbare Aktionen | Eine hervorgehobene Speicherhandlung je Formular, erreichbar ohne Scrollreise. Seltene Aktionen in einem beschrifteten Menü. *(Ersetzt am 2026-09-20 durch: Primäraktion standardmässig oben rechts im Seitenkopf. Bei langen Editoren ist eine kompakte sticky Aktionsleiste das zulässige Mittel.)* *(präzisiert am 2026-09-20: siehe Auftraggeber-Ergänzung / Muster M24)* Verschärft durch Polish-Lauf: R14, R15, R16. |
| R09 | Ruhige Gestaltung | Bestehende Farben, Schriften und Tokens behalten. Weniger verschachtelte Rahmen, klare Kanten, keine Schmuckkarten oder dekorativen Kennzahlen. Verschärft durch Polish-Lauf: R25, R27. |
| R10 | Vollständiger Nachweis | Jede Seite prüfen. Ein Screenshot, HTTP 200, erfolgreicher Build oder Breitenwert ersetzt weder Interaktion noch Gesamtaudit. Verschärft durch Polish-Lauf: Abschlussprüfung §17 (oben). |

## 2. Konkrete Stellungnahme zum bisherigen Stand

### 2.1 Am gezeigten Ist-Interface erkennbar

Diese Befunde stammen aus der gezeigten Oberfläche. Ob dieselben Probleme auf weiteren Seiten bestehen, musst du im Repository und Browser prüfen.

| Befund | Was daran nicht stimmt | Verbindliche Korrektur |
|---|---|---|
| Grosse freie Randflächen bei gleichzeitig kleinen Texten und Bedienelementen | Der verfügbare Platz hilft der Lesbarkeit nicht. Innen ist die Oberfläche dicht, aussen bleibt viel Fläche leer. | Gesamten Hauptbereich und seine inneren Arbeitscontainer nutzen; kompakte Zeilen statt hoher Wiederholungs-Cards. Lesbare Schrift und mindestens 44px Bedienhöhe erhalten. |
| Seitenüberschrift kaum dominanter als ein Card-Titel | Seite, Bereich und einzelne Aufgabe haben zu wenig unterschiedliche Gewichtung. | Eindeutige H1, kurze hilfreiche Beschreibung und einheitlicher Seitenkopf. |
| Lange, praktisch ungegliederte Sidebar | Alltagsaufgaben, Stammdaten und Systemeinstellungen erscheinen nahezu gleichrangig. | Vorhandene Einträge nach tatsächlichen Aufgaben gruppieren, aktive Position eindeutig zeigen und Berechtigungen erhalten. |
| Ähnlich klingende Navigationsbegriffe ohne Erklärung | Der Unterschied zwischen benachbarten Funktionen ist für neue Benutzer nicht sofort klar. | Aufgaben und Zielseiten prüfen; verständliche Benennung oder kurze Erklärung verwenden. Nicht blind Funktionen zusammenlegen. |
| Formularfelder nutzen nur einen Teil der grossen Card | Kartenbreite und innere Feldaufteilung wirken nicht aufeinander abgestimmt. | Inhalt sinnvoll an ein gemeinsames Grid binden. Kurze Felder nicht endlos dehnen, längere Felder erhalten den nötigen Raum. |
| Feldhinweis „optional“ weit entfernt vom Label | Information und zugehöriges Feld sind visuell voneinander getrennt. | „Optional“ beim Label oder im direkt zugeordneten Hilfetext anzeigen. |
| Kleine Tabellenüberschriften und unauffällige Statusanzeigen | Die Lesbarkeit der eigentlichen Daten erhält zu wenig Gewicht. | Gut lesbare Tabellenbeschriftungen, klarer Abstand und ausreichend kontrastierende Status-Badges. |
| Mehrere ähnlich gewichtete Zeilenaktionen | Wichtigkeit und Nutzungshäufigkeit werden nicht unterschieden. | Häufige Aktionen beschriftet sichtbar lassen; seltene Aktionen nur bei Bedarf in ein funktionierendes Menü verschieben. |
| Pagination mit Vor-/Zurück-Steuerung bei nur einer Seite | Sichtbare Bedienung erzeugt keine zusätzliche Funktion. | Bei einer Seite nur die Anzahl anzeigen; Seitensteuerung erst bei mehreren Seiten. |

**Nicht als Fehler behaupten:** Eine fehlende Suche bei zwei Datensätzen ist kein grundsätzliches UX-Problem. Ein Screenshot belegt weder defekte Funktionen noch fehlende Barrierefreiheitstests oder eine bestimmte CSS-Ursache. Behaupte solche Dinge erst nach Prüfung.

### 2.2 Fehler und Lücken in den bisherigen Prompt-Entwürfen

| Bisherige Vorgabe | Warum sie nicht genügt | Neue Entscheidung |
|---|---|---|
| Eine konkrete Fachseite bestimmt die gesamte Migration. | Andere Tools und Seitentypen können unbearbeitet bleiben. | Vollständiges UI-Inventar und Nachweis pro vorhandener Route. |
| „Modern“, „ruhig“, „hochwertig“ ohne prüfbare Umsetzung. | Der Agent muss wichtige Entscheidungen jedes Mal neu interpretieren. | Feste Tokens, Komponentenverträge, Layoutvarianten und visuelle Referenzen. |
| Wertebereiche wie 240–260 px oder 32–36 px. | Mehrere unterschiedliche Ergebnisse erfüllen denselben Prompt. | Zentrale Standardwerte und responsive Zuordnung; Arbeitszeilen typischerweise 56–72px, bei Inhalt, Fehlern oder Zoom wachsend. |
| „Tabler-Standardschrift“, obwohl das Mockup Serifentitel zeigt. | Textvorgabe und visuelles Ziel widersprechen sich. | Feste Schriftfamilien für Bedientext und Überschriften; siehe Typografie. |
| Nur eigene CSS-Variablen definieren. | Das beweist nicht, dass Tabler-Komponenten diese tatsächlich verwenden. | Tokens an die installierte Tabler-Version anbinden und berechnete Browser-Styles prüfen. [S1, S2] |
| Helle Status- und Hilfstextfarben. | Einige konkret vorgeschlagene Kombinationen sind für kleine Schrift zu kontrastarm. | Dunklere Textfarben, getrennte Status-Texttokens und Kontrastprüfung. [S3] |
| Suche, Benachrichtigungen und Änderungsmetadaten als feste Mockup-Elemente. | Aus einer Illustration wird sonst unbeabsichtigt eine neue Funktionsanforderung. | Nur tatsächlich vorhandene Funktionen und Daten darstellen. |
| „Responsive prüfen“, aber ohne benannte Werkzeuge oder Belege. | Es bleibt unklar, ob wirklich im Browser geprüft wurde. | Playwright beziehungsweise vorhandene Browser-Werkzeuge, dokumentierte Viewports, Screenshots und Teststatus. [S4] |
| „Alles gleich“ ohne Abgrenzung der Ansichten. | Login, Formulare, Kalender und Digital Signage könnten unpassend gleichgeschaltet werden. | Gemeinsame Designsprache, aber passende Layoutvarianten. |

Konkrete Nachrechnung der alten Farbwerte, jeweils als voll deckender Text auf dem genannten Hintergrund: `#238636` auf `#EAF8ED` ergibt rund **4,22:1**, `#B26A00` auf `#FFF4D6` rund **3,87:1**, `#9CA3AF` auf Weiss rund **2,54:1**. Für normalen Text ist nach WCAG 2.2 AA grundsätzlich mindestens **4,5:1** erforderlich. Die neuen Tokens korrigieren diese Kombinationen. Das ist eine Bewertung der früher vorgeschlagenen Werte, keine Kontrastmessung der laufenden Anwendung. [S3]

## 3. Geltungsbereich: Alle vorhandenen Tools und Seitentypen

Erstelle eine vollständige Bestandsaufnahme aus Routen, Blueprints, Templates, Navigation, Dialogen und erreichbaren UI-Zuständen. Beschränke dich nicht auf Links in der Sidebar: Auch Bearbeitungsseiten, Unterseiten und rollenabhängige Ansichten zählen.

| Vorhandener Seitentyp / Tool | Designauftrag |
|---|---|
| Dashboard und Übersichtsseiten | Verständliche Hierarchie, echte Kennzahlen und konsistente Karten. Keine zusätzlichen Statistik-Kacheln als Dekoration. |
| Listen, Suche und Stammdatenverwaltung | Einheitlicher Seitenkopf, Tabellen, Filter, Aktionen, Status, leere Zustände und Pagination. |
| Anlegen, Bearbeiten und Detailansichten | Einheitliche Labels, Feldgruppen, Validierung, Aktionsleiste und Darstellung von Metadaten. |
| Einstellungen und Konfiguration | Thematische Gruppen, verständliche Erklärungen, konsistente Speichern-/Abbrechen-Logik. |
| Benutzer, Rollen und Zugriffe | Dasselbe Design; Rollenmodell und serverseitige Autorisierung unverändert. |
| Import, Export und Schnittstellenverwaltung | Einheitliche Dateiauswahl, Resultate und Fehlermeldungen; Fortschritt nur bei vorhandener technischer Grundlage. |
| Kalender, Planung, Kanban und ähnliche Fachwerkzeuge | Gemeinsame Farben, Schrift, Navigation und Bedienelemente; das fachlich notwendige Arbeitslayout erhalten. |
| Medien, Vorlagen und Inhaltsverwaltung | Gemeinsame Karten, Vorschauen, Auswahlzustände und Aktionen. |
| Modals, Dropdowns, Tabs und Bestätigungen | Auch diese Oberflächen migrieren, nicht nur vollständige HTML-Seiten. |
| Login, Zugriff verweigert und Fehlerseiten | Gemeinsame Marken- und Formgestaltung; kein erzwungener Admin-Seitenrahmen vor der Anmeldung. |
| Öffentliche Ansichten, Druck, Kiosk und Digital Signage | Gemeinsame Tokens nur dort übernehmen, wo passend. Keine Sidebar, keine Admin-Aktionen, keine pauschale Desktop-Schriftgrösse übertragen. Als eigene Layoutvarianten erfassen und gegen unbeabsichtigte Änderungen prüfen. |

Diese Tabelle ist eine Prüfliste, kein Auftrag, fehlende Module neu zu entwickeln. Verwende die echten Modulnamen und Routen des jeweiligen Projekts.

## 4. Technologien und Werkzeuge: explizit und mit klaren Grenzen

### 4.1 Laufzeit und Implementierung

| Technologie | Vorgabe |
|---|---|
| Flask | Bestehende Anwendung, Blueprints, Endpoints, Request-Verarbeitung und Sessions weiterverwenden. |
| Jinja2 | Vorhandene Template-Vererbung, Partials und Macros nutzen; wiederkehrende UI nicht kopieren. |
| Tabler / `@tabler/core` | Verbindliche Komponentenbasis. Installierte Version aus Projekt und Assets ermitteln, nicht automatisch aktualisieren. |
| Bootstrap | Nur die vorhandene, zur Tabler-Integration passende Basis nutzen. Kein zweites Bootstrap-CSS oder zweiter JS-Bundle. |
| Tabler Icons | Ein einziges konsistentes Icon-System. Bestehende SVG-/Sprite-Einbindung weiterverwenden. Keine Emojis als UI-Icons. |
| CSS / vorhandenes Sass | Zentrale Tokens und Komponenten-Styles. Vorhandenen Build verwenden, keinen neuen Build nur für die Neugestaltung einführen. |
| JavaScript | Vorhandene Skripte und Bootstrap-/Tabler-Interaktionen wiederverwenden. Neue kleine Interaktionen ohne neue Laufzeitbibliothek. |
| Vorhandene Bibliotheken | Zum Beispiel HTMX oder Alpine nur weiterverwenden, wenn schon Teil der Anwendung. Nicht neu einführen. |
| Nicht zulässig | React, Vue, Svelte, Tailwind, neue UI-Kits, Frameworkwechsel oder eine neue SPA als Nebenprodukt. |

### 4.2 Arbeits- und Prüfwerkzeuge des Coding Agents

| Werkzeug | Konkreter Einsatz | Grenze / Fallback |
|---|---|---|
| Codex oder Claude Code | Repository lesen, begrenzte Änderungen implementieren, Tests ausführen und Befunde dokumentieren. | Nur tatsächlich verfügbare Werkzeuge verwenden. |
| Git | Arbeitszustand vorab prüfen, Diffs lesen, fremde Änderungen erhalten, eigene Änderungen nachvollziehbar halten. | Kein `reset --hard`, kein automatischer Push, kein Deployment ohne Auftrag. |
| Shell / Terminal | Bestehende Start-, Build- und Testbefehle ausführen; Versionen und Assets ermitteln. | Bestehende Projektumgebung verwenden. Keine produktiven Daten verändern. |
| ripgrep (`rg`) | Templates, Inline-Styles, Farbwerte, Klassen, Duplikate und JS-Selektoren suchen. | Falls nicht vorhanden: `git grep`, vorhandene Dateisuche oder PowerShell `Select-String`. |
| Playwright | Echte Seiten öffnen, Navigation und Formulare bedienen, Viewports prüfen und Screenshots erstellen. | Vorhandene Integration nutzen. Fehlende Browser-/Testumgebung ausdrücklich als Blocker melden. |
| Playwright Test | Wenn im Projekt vorhanden: Screenshot-Vergleiche mit freigegebenen Referenzen, zum Beispiel `toHaveScreenshot()`. [S4] | Diese Assertion gehört zum Playwright-Test-Runner; nicht eine identische Python-API erfinden. |
| Browser-DevTools / vorhandenes Chrome-DevTools-MCP | Berechnete CSS-Werte, Box-Modell, Netzwerk, Konsole, Fokus und überlaufende Elemente untersuchen. | Kein MCP als vorhanden voraussetzen. Vorhandene gleichwertige Browser-Werkzeuge sind ausreichend. |
| axe-core / `@axe-core/playwright` | Automatisierte Accessibility-Prüfung, wenn verfügbar. [S5] | Nur Prüfwerkzeug, keine neue Produktionsabhängigkeit. Ersetzt keine manuelle Tastaturprüfung. |
| Flask-Testclient und bestehendes pytest/unittest | GET-/POST-Verhalten, Weiterleitungen, Berechtigungen und Regressionen prüfen. [S6] | Vorhandenes Testframework behalten. Kein Wechsel allein wegen dieses Prompts. |
| Vorhandene Linter und Formatter | Bestehende Qualitätsprüfungen für Python, Templates, CSS und JavaScript ausführen. | Nicht das ganze Repository unnötig neu formatieren. |

Nicht verfügbare Werkzeuge zuerst durch vorhandene gleichwertige Mittel ersetzen. Neue reine Entwicklungsabhängigkeiten nur nach den Repository-Regeln beziehungsweise mit nötiger Freigabe installieren. Fehlende Tests nicht als bestanden deklarieren und Sicherheitsmechanismen nicht deaktivieren, um Tests zu erleichtern.

## 5. Feste visuelle Basis

Die Stilrichtung bleibt: dunkle Petrol-Sidebar, warmer heller Hintergrund, weisse Inhaltsflächen, Burgunder als Handlungsakzent und zurückhaltende Trennlinien.

### 5.1 Zentrale Farb-Tokens

Definiere diese Werte einmal in einer gemeinsamen Token-Datei oder der entsprechenden vorhandenen zentralen Struktur. Die Namen sind der gemeinsame Vertrag; keine zweite parallele Palette anlegen.

```css
:root {
  --app-bg: #F6F4F1;
  --app-surface: #FFFFFF;
  --app-surface-soft: #FAF9F7;

  --app-sidebar: #173C3F;
  --app-sidebar-hover: #214A4D;
  --app-sidebar-active: #31585B;
  --app-sidebar-text: #C7D8D9;
  --app-sidebar-label: #9AB7BA;
  --app-sidebar-indicator: #F3A6C0;

  --app-primary: #A3164D;
  --app-primary-rgb: 163, 22, 77;
  --app-primary-hover: #8E123F;
  --app-primary-active: #7C1037;
  --app-primary-soft: #F7E8EE;
  --app-on-primary: #FFFFFF;

  --app-text: #1F2937;
  --app-text-muted: #596273;
  --app-border: #E5E7EB;
  --app-border-soft: #EFECE8;
  --app-control-border: #808B99;
  --app-focus: #A3164D;

  --app-success: #2FB344;
  --app-success-text: #166534;
  --app-success-soft: #EAF8ED;
  --app-warning: #F59F00;
  --app-warning-text: #854D0E;
  --app-warning-soft: #FFF4D6;
  --app-danger: #D63939;
  --app-danger-text: #B42318;
  --app-danger-soft: #FCEAEA;
  --app-info: #4299E1;
  --app-info-text: #175CD3;
  --app-info-soft: #EAF4FC;
  --app-neutral-text: #475467;
  --app-neutral-soft: #EEF0F2;
}
```

Burgunder bezeichnet die wichtigste Handlung, Auswahl oder einen Link, nicht eine beliebige grosse Hintergrundfläche. Für kleine Statustexte immer `*-text` auf `*-soft` verwenden, nicht die hellere Akzentfarbe. Destruktive Buttons verwenden einen geprüften dunklen Rotton, beispielsweise `--app-danger-text` mit Weiss.

Die helle Sidebar-Akzentlinie bleibt als optionaler Token verfügbar: Dunkles Burgunder hebt sich gegen Petrol schlecht ab. Aktive Navigation primär durch sanft getönten Hintergrund, Schriftgewicht und `aria-current` kennzeichnen; höchstens eine feine Akzentlinie ohne Layoutsprung ergänzen. Keine auffällige pinke Kontur plus Unterstreichung. Tastaturfokus bleibt davon getrennt deutlich sichtbar.

Helle Card-Rahmen sind dekorative Trennlinien. Wo eine Umrandung nötig ist, um ein Eingabefeld oder Bedienelement zu erkennen, `--app-control-border` und die tatsächliche Hintergrundfarbe auf ausreichenden Kontrast prüfen. [S7]

### 5.2 Typografie, Masse und Abstände

| Element | Fester Standard |
|---|---|
| Schrift für Fliesstext, Navigation, Tabellen, Formulare und Buttons | `Arial, Helvetica, sans-serif` |
| Schrift für H1 und Card-Überschriften | `Georgia, "Times New Roman", serif` |
| Fliesstext / Eingabefelder | `1rem`, Zeilenhöhe `1.5` |
| H1 ab Desktop-Breakpoint | `2.125rem`, Gewicht `700`, Zeilenhöhe `1.2` |
| H1 unter Desktop-Breakpoint | `1.75rem`, Gewicht `700`, Zeilenhöhe `1.2` |
| Card-Überschrift | `1.25rem`, Gewicht `700`, Zeilenhöhe `1.3` |
| Navigation / Tabellen / Labels | `0.875rem`; Labels Gewicht `600` |
| Hilfetext / sekundäre Metadaten | `0.8125rem`; wichtige Handlungsinformationen nicht kleiner setzen |
| Sidebar | `248px` breit auf Desktop |
| Topbar, nur bei tatsächlicher Funktion | `64px` Mindesthöhe, darf bei Zoom/Inhalten wachsen; keine leere zusätzliche Leiste |
| Arbeitsbreite | Volle verfügbare Breite neben der Sidebar, keine Obergrenze oder schmale innere Gesamtspalte; auch für Formulare |
| Inhaltspadding | Desktop `32px`, Tablet `24px`, Smartphone `16px` |
| Card-Radius | `12px` |
| Button-/Feld-/Nav-Radius | `8px` |
| Status-Badge-Radius | `999px` |
| Standard-Interaktionshöhe | mindestens `44px`; unterstützende Iconbuttons mindestens `44 × 44px` Trefferfläche, Iconzeichnung etwa `20px`; mehrzeilige Labels dürfen wachsen |
| Kompakte Arbeits-/Tabellenzeile | typischerweise `56–72px`, bei Umbruch, Fehlern oder Zoom wachsend; keine fixe Maximalhöhe |
| Card-Innenabstand | `24px`, auf Smartphone `16px` |
| Abstand zwischen Hauptblöcken | `24px` |
| Formular-Grid-Abstand | `24px` |
| Erlaubte allgemeine Abstandsskala | `4 / 8 / 12 / 16 / 24 / 32 / 40 / 48px` |
| Schatten | `0 1px 2px rgba(0, 0, 0, 0.025)` |

Die Serifentitel greifen die visuelle Richtung des Mockups ausdrücklich auf. Die Schriftwahl bleibt nicht mehr der jeweiligen Tabler-Standardkonfiguration überlassen. Keine pro Seite abweichende Schrift, keine nachträglich eingeführte Condensed-Schrift und kein unkontrollierter externer Font-Aufruf.

Die `rem`-Werte gehen vom unveränderten Browser-Standard aus. Keine erzwungene 16px-Root-Grösse, keine Zoom-Sperre und keine Schriftverkleinerung, um Probleme zu kaschieren. Fontstacks garantieren ohne identische installierte Fonts keine pixelgleichen Ergebnisse über Betriebssysteme hinweg; dokumentiere deshalb den tatsächlich verwendeten Font der Referenzumgebung. Eine spätere freigegebene selbst gehostete Markenschrift wird zentral und mit neuen geprüften Referenzen eingeführt.

Lege wiederkehrende Masswerte und kompakte Varianten zentral als Tokens an. Keine leicht unterschiedlichen Radien oder Paddings über einzelne Templates verteilen. Freiraum zwischen Gruppen bleibt sinnvoll; künstlich aufgeblähte Container und abgeschnittene Pflichtinformationen nicht.

Kurze Felder nebeneinander: Menge/Einheit, Preis/Zielgruppe, Dauer/Zeiteinheit. Ein Zahlenwert benötigt nicht eine komplette Bildschirmzeile. Textareas beginnen mit angemessener Höhe und bleiben vergrösserbar; lange Texte nicht in winzige Scrollschlitze pressen. Formulare bleiben ungefähr 1rem, wichtige Labels mindestens 0,875rem. Dies sind Projektziele, kein behaupteter Konformitätsnachweis.

### 5.3 Gemeinsame Symbolsprache

Nutze das vorhandene zentrale `icon`-Makro und die tatsächlich verfügbaren Tabler-Sprite-IDs. Keine neue Iconbibliothek und keine Emojis als Bedienelemente. Ein fehlendes Symbol darf nicht unbemerkt leer bleiben.

| ASCII-Kürzel in den Skizzen | In der Anwendung | Sichtbarer Text, beispielsweise |
|---|---|---|
| `[S]` | Speicher-Symbol | Rezept speichern |
| `[+]` | Plus | Zutat hinzufügen |
| `[E]` | Stift | Bearbeiten |
| `[>]` / `[v]` | Chevron geschlossen/offen | Details / Details schliessen |
| `[...]` | Menü-/Drei-Punkte-Symbol | Aktionen / Weitere Aktionen |
| `[^]` / `[v]` | Auf-/Ab-Pfeil im Sortierkontext | Nach oben / Nach unten |
| `[X]` | Kontextgerechtes Entfernen-Symbol | Aus Rezept entfernen |
| `[?]` | Lupe, nicht ein Fragezeichen | Suchen |
| `[O]` | Auge | Vorschau |
| `[P]` | Drucker | PDF öffnen / Drucken |
| `[<]` | Pfeil nach links | Zur Rezeptliste |
| `[!]` | Warnsymbol | Konkrete fehlende oder ungeklärte Angabe |
| `[OK]` | Haken | Nur den tatsächlich bestätigten Zustand benennen |

**Die ASCII-Kürzel werden nicht als Buchstaben in die Anwendung übernommen.** Sie veranschaulichen Icon plus Text. Produkttexte verwenden korrekte Umlaute und Schweizer Schreibweise; `ae/oe/ue` kommen nur in den ASCII-Skizzen zum Einsatz.

Hauptaktionen auch auf dem Smartphone beschriften. Ein Tooltipp oder zugänglicher Name allein ersetzt für unerfahrene Benutzer keinen sichtbaren Text. Unterstützende reine Iconbuttons nur in eindeutigem Kontext; Fokus, Name und Trefferfläche prüfen. Dekorative Icons neben Text nicht nochmals vorlesen lassen. Status nie nur durch Farbe darstellen.

**Auftraggeber-Präzisierung vom 13. September 2026:** Mehr verständliche Symbole und weniger wiederholte Wörter machen die Oberfläche ruhiger. Vorhandene Tabler-Symbole gezielt auch bei kurzen Labels und unterstützenden Hinweisen einsetzen; gleichartige Texte nicht in jeder Zeile ausschreiben. Hauptaktionen und Navigation behalten kurze sichtbare Labels. Eindeutige Nebenaktionen dürfen im klaren Zeilenkontext als Symbolbutton erscheinen, mit zugänglichem Namen und verständlichem Tooltip; notwendige Warnungen und Formfeldbezeichnungen bleiben verständlich. Beispielsweise genügt in einer bereits nummerierten History-Zeile «Ansehen» mit Auge statt eines erneut ausgeschriebenen Standtitels. Keine zusätzlichen dekorativen Symbole ohne Informationswert. Diese Präzisierung gilt bei der Prüfung laufender und folgender UI-Pakete.

## 6. Tabler tatsächlich anbinden, nicht nur umfärben

Untersuche zuerst die installierte Tabler-/Bootstrap-Version und die ausgelieferten CSS-Dateien. Dokumentation neuerer Versionen ist keine Aufforderung zum Upgrade.

Eigene `--app-*`-Variablen müssen an die tatsächlich verwendeten Theme- und Komponentenvariablen angeschlossen werden. Tabler dokumentiert beispielsweise `--tblr-primary`; Bootstrap-Komponenten können eigene lokale Variablen besitzen. Deshalb ist ein Eintrag in `:root` allein kein Nachweis, dass Buttons, Checkboxen, Tabs und Pagination richtig aussehen. [S1, S2]

Prüfe insbesondere Primärfarbe und RGB-Varianten, Body-Hintergrund, Schriftfamilien, Linkfarben sowie Normal-, Hover-, Active-, Focus-, Disabled- und Invalid-Zustände. `--app-primary-rgb` steht hier für RGB-Kanäle und wird nicht aus einem Hex-String zusammengesetzt.

Nutze den bestehenden Sass-Build, falls dieser bereits die Theme-Erstellung übernimmt. Sonst verwende schlanke, korrekt nach den Herstellerstyles geladene zentrale Overrides. Bearbeite keine minifizierten Vendor-Dateien und löse Konflikte nicht durch eine wachsende Sammlung von `!important`.

Prüfe berechnete Styles im Browser. Verhindere unbeabsichtigte Auswirkungen auf Druck, öffentliche Seiten, Signage und eingebundene Drittkomponenten durch passende Layout-/Bereichsselektoren. Entferne alte Überschreibungen erst nach Prüfung ihrer bisherigen Nutzung.

## 7. Gemeinsamer Seitenrahmen und Navigation

Alle regulären internen Tools verwenden denselben Seitenrahmen: Sidebar, bei benötigten Funktionen Topbar, Seitenkopf und Hauptinhalt. Topbar-Inhalte nicht erfinden; ohne zusätzliche Funktion keine leere Zierleiste erzeugen. Die gewählte Anwendungslösung wird zentral umgesetzt, nicht pro Tool neu entschieden.

Der Hauptbereich braucht `min-width: 0`. Seine Breite wird aus dem verfügbaren Bereich neben der Sidebar berechnet; kein `100vw` über die Sidebar hinweg. Die frühere Vorgabe «Kopf, Bereichsnavigation und Hauptinhalt teilen dieselben äusseren Kanten» ist am 2026-09-20 ersetzt durch: Seitenkopf, Statusbar und Hauptinhalt teilen dieselben äusseren Kanten; eine horizontale Bereichsnavigation existiert nicht mehr. Auch innere Gesamtcontainer und Formulare nutzen die volle Arbeitsbreite. Nur einzelne kurze Felder und Lesetexte lokal begrenzen; breite Hauptarbeit mit schmalerem Prüfkontext ist ein gemeinsames Layoutmuster, keine schmale Gesamtspalte.

Die Sidebar erhält das vorhandene Original-Logo und den Produktnamen. Kein Logo nachzeichnen, keinen Claim ergänzen. Die vier fachlichen Haupteinstiege bleiben **Wochenplan**, **Menüs & Bausteine**, **Vorschau & Bildschirme** und **Einstellungen**, entsprechend vorhandenen Rechten. Unterfunktionen im Bereich zeigen, nicht erneut als 14 gleichrangige Sidebarlinks.

Navigationseinträge: mindestens 44px hoch, Icon 20px plus sichtbarer Text, Abstand 12px, Radius 8px. Gruppentitel: 12px, Gewicht 600, dezente Grossschreibung. Aktiver Eintrag: sanft getönte Fläche, kontrastgeprüfte Schrift, etwas stärkeres Schriftgewicht; eine feine Akzentlinie ist optional. Keine auffällige pinke Kontur plus Unterstreichung. Fokus ist ein eigener deutlich sichtbarer Zustand.

Der Navigationsbereich scrollt bei Platzmangel, der Logout bleibt erreichbar. Profilfunktionen an einem klaren Ort bündeln, nicht mehrfach dieselbe Benutzerinformation in Sidebar und Topbar wiederholen. Rollenabhängige Sichtbarkeit erhalten; sie ersetzt keine serverseitige Autorisierung.

Seitenkopf: logisch korrekter Breadcrumb, genau eine H1, gegebenenfalls ein kurzer wirklich hilfreicher Satz und die wichtigsten Seitenaktionen. Danach folgt die Kernarbeit vor optionaler Verwaltung. Kein erfundener Breadcrumb-Zielpfad, kein dekorativer Eyebrow und kein Fülltext wie „Hier können Sie die Verwaltung verwalten“. Eine Bereichsauswahl pro Kontext: globale Navigation, Bereichslinks und lokale Abschnittslinks erfüllen verschiedene Aufgaben; keine doppelten Cafeteria-/Patientenreihen.

## 8. Komponentenregeln für alle Tools

| Komponente | Verbindliche Regel |
|---|---|
| Cards | Weisse Fläche, 12px Radius, dezenter Rand und minimaler Schatten nur bei inhaltlich nötiger Gruppierung. Wiederholte Zutaten, Schritte, Bausteine und Zuordnungen als kompakte Arbeitszeilen, keine hohe offene Card je Objekt oder Schmuckkarte. Keine Card in Card ohne fachlichen Grund. |
| Bereichs- und Abschnittsnavigation | Eine Auswahl je Kontext, zurückhaltende aktive Kennzeichnung aus zentralen Tokens. Echte Seitenwechsel als Links; lokale Rezeptlinks führen zu sichtbaren Abschnitten statt Zutaten hinter Tab-Inhalten zu verbergen. Dynamische Tabs nur für passende vorhandene Aufgaben mit Tastatur-/ARIA-Semantik; keine doppelte Auswahl oder vorgeschriebene Kombination von Kontur und Unterlinie. |
| Buttons | Eine hervorgehobene Speicherhandlung je bestehendem Formular, ohne Scrollreise erreichbar. Hauptaktionen mit Icon und sichtbarem kurzem Text auch mobil. Nebenaktionen neutral; mindestens 44px Bedienhöhe. Keine universelle Primäraktion auf Leseseiten oder globale Speicherung unabhängiger Formulare erzwingen. |
| Formularfelder | Sichtbares Label, tatsächlicher Pflichtstatus, sinnvoller Datentyp, 44px Mindesthöhe und verständlicher Hilfetext. Kurze Felder gemeinsam gruppieren; Menge/Einheit direkt in der Zutatenzeile bearbeiten. Genau ein massgebliches Feld je Wert. Placeholder ersetzt kein Label. |
| Validierung | Bestehende native und serverseitige Regeln erhalten. Fehlerzusammenfassung mit sichtbarem Feld verknüpfen, betroffenen geschlossenen Bereich öffnen/erschliessen, Fokus sinnvoll setzen; `aria-invalid`/`aria-describedby` passend setzen. Werte und Fehlermarker nach erneutem Schliessen erhalten. |
| Textareas | Sinnvolle Mindesthöhe und vertikale Vergrösserung erlauben. Zeichenlimit und Zähler nur aus echten bestehenden Vorgaben ableiten. |
| Tabellen | Semantische Tabelle, Header in normaler Schreibweise, ausreichend Padding, dezente Zeilentrennung. Daten und Aktionen nicht abschneiden oder unter 14px verkleinern. |
| Status-Badges | 13px Text, 4px/10px Padding, Pill-Form, dunkle Status-Textfarbe auf heller Statusfläche. Reale Backend-Zustände mit Text zuordnen: gespeichert, geprüft, aktiviert und veröffentlicht unterscheiden; alter Prüfstand bestätigt keine neuen Eingaben. Fehlend ist weder null noch allergenfrei. |
| Zeilenaktionen | Häufige Aktionen beschriftet sichtbar; seltene in ein echtes Dropdown. Keine versteckten Nur-Hover-Aktionen. Kein leeres Dreipunktmenü. |
| Suche und Filter | Suche und höchstens zwei häufige vorhandene Filter standardmässig; zusätzliche Filter bei Bedarf, aktive Auswahl und Reset bleiben erkennbar. Bestehende Suchparameter kombinierbar erhalten; bei serverseitiger Pagination nicht nur die sichtbare Seite als Gesamtbestand filtern. |
| Pagination | In den Listenabschluss integrieren. Gesamtzahl und Seitengrösse aus echten Daten. Keine Seitennavigation bei nur einer Seite. |
| Leere Zustände | „Noch keine Daten“, „kein Suchtreffer“, „Laden fehlgeschlagen“ und „keine Berechtigung“ unterscheiden. Keine erfundene Nullzählung; nur vorhandene erlaubte Folgeaktionen, keine Pagination ohne Daten. |
| Erfolg und Fehler | Gemeinsame Flash-/Alert-Komponente, verständliche Texte, Feldfehler zusätzlich lokal. Wichtige Informationen nicht nach kurzer Zeit automatisch entfernen. |
| Modals | Nur für passende kurze Aufgaben. Aussagekräftiger Titel, korrekter Fokus, Tastaturbedienung, Rückkehr zum Auslöser. Lange Formulare nicht in kleine Modals pressen. |
| Destruktive Aktionen | Bestehende Bestätigungen und Schutzmassnahmen erhalten. Objekt und Konsequenz benennen. Keine zusätzlichen riskanten Aktionen erfinden. |
| Ladezustände | Nur dort anzeigen, wo tatsächlich geladen wird. Keine künstlichen Wartezeiten oder erfundenen Fortschrittsprozente. |

Ein statisches Anlegeformular braucht nicht automatisch einen „Abbrechen“-Button. Ein Dashboard braucht nicht automatisch eine Suche. Eine Datentabelle braucht nicht automatisch eine Spalte „Letzte Änderung“. Das Mockup ist keine Datenquelle.

Sprache: Bestehende Anrede und Anwendungssprache konsistent halten. Für deutschsprachige Schweizer Anwendungen Schweizer Rechtschreibung verwenden. Sichtbare Datumsformate können lokalisiert werden; maschinelle Feldwerte und erwartete Backend-Formate unverändert lassen. Keine technischen Interna oder vertraulichen Informationen in Endbenutzer-Fehlermeldungen.

### 8.1 Interaktions- und Formularinvarianten

Die Skizzen sind nicht allein durch CSS abzuhaken. Folgende Verhaltensregeln gelten bei jeder Umsetzung:

| Situation | Verpflichtendes Verhalten |
|---|---|
| Detailbereich öffnen/schliessen | Keine Speicherung, kein Reset, keine verlorenen Werte. Auslöser benennt Zustand; Tastaturbedienung möglich. |
| Gefüllte Zusatzfelder schliessen | Bedeutung bleibt in kurzer Zusammenfassung erkennbar; Quellenrohwerte müssen nicht ständig sichtbar sein. |
| Neue Zutat oder neuer Schritt | Betroffenes neues Objekt öffnen und Fokus sinnvoll setzen; bestehende Eingaben und Reihenfolge erhalten. |
| Menge direkt ändern | Kein zusätzlicher Detaildialog nötig; genau ein massgebliches Eingabefeld im Formular. |
| Reihenfolge ändern | Vorhandenen Strukturweg nutzen; beim betroffenen Objekt bleiben; keine alleinige Drag-and-drop-Bedienung. |
| Entfernen | Lokalen und globalen Geltungsbereich unterscheiden; bestehende Schutzregeln erhalten, keine ungefragte neue Löschfunktion. |
| Intern navigieren mit Änderungen | Sichere Rückfrage mit „Weiter bearbeiten“ und „Änderungen verwerfen“, soweit darstellungsseitig möglich. Keine neue ungefragte Speicherung. |
| Speichern bestätigt | Erst nach erfolgreicher Antwort den tatsächlichen Speicherzustand anzeigen. Nur betroffenen Formularbereich als gespeichert kennzeichnen. |
| Speicherantwort unklar | Unsicherheit benennen; aktuellen Stand prüfen, bevor erneut geschrieben wird. Keine automatische Wiederholung nicht nachweislich sicher wiederholbarer Aktionen. |
| Ungespeicherte Änderungen prüfen | Nicht als vom alten Prüfergebnis bestätigt darstellen. Speichern, Prüfen, Aktivieren und Veröffentlichen getrennt halten. |
| Inhalt nicht erfasst | Nicht als null, vollständig, allergenfrei oder geprüft ausgeben. Quelle und Prüfstand nicht aus Titel oder Bild ableiten. |
| Session oder Berechtigung fehlt | Bestehenden Schutzweg nutzen, kein falscher Erfolg und keine Sicherheitsabschwächung. |
| 200 % Zoom / Smartphone | Umordnen statt schrumpfen; Fokus und Aktionsleiste verdecken nichts; Hauptaktionen bleiben beschriftet. |

**Keine doppelte Formularimplementierung:** Eine kompakte Zeile und ihr Detailbereich gehören zu denselben vorhandenen Feldern. Keine konkurrierenden `name`-Attribute, IDs oder versteckten Kopien mit veralteten Werten. Kein Entfernen aus dem DOM, wenn dadurch vorhandene Werte nicht mehr übermittelt werden. `readonly` und `disabled` sind nicht austauschbar.

**Fehler gehen vor Kompaktheit:** Ein geöffneter Pflichtfehler darf mehr Raum benötigen. Eine Warnung zur ungeprüften Rezeptquelle bleibt in der Übersicht; Rohwerte wie Quellen-IDs können nachgeordnet sein. Nicht jede fehlende optionale Notiz mit einer Warnung versehen.

**Keine zusätzliche Pflichtklickstrecke:** Menüs, Dropdowns und Details reduzieren seltene Bedienung. Häufige Schritte wie Mengenänderung, Öffnen des gewünschten Eintrags oder Speichern dürfen dadurch nicht umständlicher werden. Vergleiche Aufgabenaufwand, nicht nur Screenshot-Höhe.

### 8.2 Verbindliche Strukturreferenzen M01–M20

Die Mockups sind **verbindliche Struktur- und Interaktionsmuster**, keine pixelgenauen Screenshots und kein Nachweis einer bereits funktionierenden Anwendung. Breite Rahmen zeigen die gesamte verfügbare Arbeitsfläche, nicht eine feste Zeichen- oder Pixelbreite. Die Darstellungen sind absichtlich ohne zusätzliche Bilder verständlich. Im Rezepteditor sind „Rezept“, „Zutaten“ und „Zubereitung“ lokale Sprunglinks zu sichtbaren Abschnitten, keine Pflicht für versteckte Tab-Inhalte. So bleibt die Zutatenübersicht unmittelbar nutzbar.

Alle Datensätze, Mengen, Zeiträume, Zählungen und Statusbeispiele sind synthetisch. Keine Rezeptanweisung oder fachliche Freigabe daraus ableiten. Kein neues Feature, Filterfeld, Statuswert, Berechtigungsmodell oder Backendverhalten allein aus einer Skizze einbauen. Angezeigte Zahlen aus echten Daten berechnen bzw. nur vorhandene Werte nutzen; sonst die entsprechende Information weglassen oder als nicht verfügbar benennen.

Die Skizzen zeigen verschiedenartige Seitentypen und Zustände, nicht 20 neu zu bauende Seiten. Ordne jede tatsächliche Seite einem Muster zu und dokumentiere notwendige fachliche Unterschiede. Jede Skizze wird zusammen mit ihren anschliessenden Verhaltensregeln umgesetzt. Erklärende Anmerkungen innerhalb der Rahmen, beispielsweise „Weitere Treffer folgen“, sind Kommentare zum Layout, keine zusätzlich zu erzeugenden Hilfetextblöcke. Sichtbare Labels und Aktionen sind dagegen bewusst vorgegeben.



**Mockup-Verzeichnis**

| ID | Strukturreferenz |
|---|---|
| M01 | Gemeinsamer Seitenrahmen für alle internen Arbeitsseiten |
| M02 | Rezepteditor: kompakter Ausgangszustand |
| M03 | Rezeptzutat: nur die benötigten Details öffnen |
| M04 | Zubereitung: Kurzfassung und gezielte Bearbeitung |
| M05 | Zeilenaktionen: kompakt, beschriftet und kontextbezogen |
| M06 | Rezepteditor auf dem Smartphone |
| M07 | Menüübersicht: Text und Handlung vor Bildern |
| M08 | Bausteinliste mit gezielt erweiterten Filtern |
| M09 | Wochenübersicht: auswählen zuerst, anlegen bei Bedarf |
| M10 | Cafeteriaplan: Arbeitsraster statt Verwaltungsblöcke |
| M11 | Patientenplan: kompakte Tagesgruppen mit Mittag und Abend |
| M12 | Menüeditor: breite Hauptarbeit, schmalerer Prüfkontext |
| M13 | Baustein bearbeiten: eindeutige Allergenfelder |
| M14 | Drucken und Vorschau: Arbeitsauftrag von Layoutverwaltung trennen |
| M15 | Einstellungen: kompakte Zusammenfassung, Bearbeitung bei Bedarf |
| M16 | Erscheinungsbild: gespeicherten Entwurf eindeutig kennzeichnen |
| M17 | Datenimport: Aufgabe und Fehler, nicht technische Rohdaten |
| M18 | Benutzer und ähnliche Verwaltungslisten |
| M19 | Fehler in einem zuvor geschlossenen Detailbereich |
| M20 | Leere Daten, keine Treffer und Ladefehler unterscheiden |

#### M01 — Gemeinsamer Seitenrahmen für alle internen Arbeitsseiten

*(Ersetzt am 2026-09-20 durch: Eingerückte Sidebar, Statusbar unter dem Titel, keine horizontalen Tabs)*
Desktop; Sidebar links, gesamte verbleibende Breite rechts. Der Marker `>` steht nur für die dezente aktive Auswahl. Unterpunkte erscheinen eingerückt NUR bei aktivem Oberpunkt.

```text
+----------------------+  +---------------------------------------------------------------------------------+
| SUEDHANG             |  | SEITENTITEL / aktuelles Objekt                            [Hauptaktion]         |
| Menueplanung         |  | Kurzer Kontext nur, wenn er bei dieser Aufgabe hilft.                           |
+----------------------+  +---------------------------------------------------------------------------------+
|   Wochenplan         |  | [STATUSBAR: 1-5 echte Felder | Neutral/Erfolg/Warnung/Fehler]                  |
| > Menues & Bausteine |  +---------------------------------------------------------------------------------+
|     Menues           |  | Suche / Filter: nur wenn noetig, unter der Statusbar                            |
|     Bausteine        |  +---------------------------------------------------------------------------------+
|     Zutaten          |  | ARBEITSINHALT: Liste, Formular, Wochenplan oder Editor                          |
|     ...              |  |                                                                                 |
|   Vorschau &         |  | Die Flaeche reicht bis zum gemeinsamen rechten Seitenrand.                      |
|   Bildschirme        |  | Keine zusaetzliche schmale zentrierte Gesamtspalte.                             |
|   Einstellungen      |  |                                                                                 |
|                      |  | Kurze Felder nebeneinander. Lange Inhalte erhalten mehr Raum.                   |
|                      |  | Keine leeren Karten, um freie Flaeche kuenstlich zu fuellen.                    |
|                      |  |                                                                                 |
|                      |  | Details am betroffenen Objekt oeffnen, nicht alles dauerhaft.                   |
|                      |  |                                                                                 |
|                      |  +---------------------------------------------------------------------------------+
|                      |  | [Sekundaeres / Technisches nachrangig bzw. einklappbar]                         |
| Konto                |  |                                                                                 |
| Abmelden             |  |                                                                                 |
+----------------------+  +---------------------------------------------------------------------------------+
```

**Pflicht:** Kopf, Bereichsnavigation und Hauptinhalt nutzen dieselben äusseren Kanten. Eine zusätzliche Topbar nur für tatsächliche Funktionen, nie als leere Zierfläche. Der Bereichstitel darf ohne Karte stehen.

**WP1-Shell-Vertrag, umgesetzt am 2026-09-20:** Der frühere Pflichtsatz «Kopf, Bereichsnavigation und Hauptinhalt» ist ersetzt durch «Seitenkopf, Statusbar und Hauptinhalt». `base_tabler.html` ruft `render_tabs()` nicht mehr auf. `.admin-statusbar` stellt 1–5 Slots als responsive Grid ohne horizontales Dokument-Scrolling dar. Jeder Slot verwendet `.admin-statusbar-item` plus genau eine Variante `--neutral`, `--success`, `--warning` oder `--danger`; Varianten bilden ausschliesslich auf die bestehenden `--app-*-text`-/`--app-*-soft`-Tokens ab. `.admin-nav-subitems` liefert Einrückung, Trennlinie und mindestens 48 px hohe Unterpunkte. Die 34 zentralen `--app-*`-Farbtokens bleiben unverändert. Nachweis: `test_ui_fullwidth_shell_browser.py`, `test_admin_display_browser.py`, `test_ui_master_tokens_browser.py`.

**WP2-Navigationsvertrag, umgesetzt am 2026-09-20:** `_area_tabs.html` bleibt das einzige serverseitige Navigationsmodell und ordnet Routen ausschliesslich über explizite Endpoint-Mengen zu; präfixbasierte Zuordnung ist unzulässig. Das Modell exportiert `area_nav.areas`, `area_nav.selected.area`, `area_nav.selected.item` und `area_nav.href`. `_workflow_sidebar.html` rendert daraus vier `.admin-nav-area`-Oberpunkte und nur unter dem aktiven Oberpunkt eine eingerückte `.admin-nav-subitems`-Liste. Der aktive Unterpunkt trägt `aria-current="page"`; Desktop, Offcanvas und No-JS verwenden dasselbe Makro und dieselben Capability-Prädikate. «Menüs & Bausteine» enthält Menüs, Bausteine, Zutaten, Rezepte, Kochbücher, Gerichtvorlagen, Einkaufslisten, Bestellung, Lager und Kalkulation. «Einstellungen» enthält Bereiche & Öffnungszeiten, Erscheinungsbild, Darstellung, Daten importieren, Schnittstellen und Benutzer & Zugriff. «Zutaten» behält die bestehenden Grundlagen-Endpunkte und URLs. Nachweis: `test_admin_shell_ui.py`, `test_ui_master_shell_browser.py`, `test_recipe_navigation_browser.py`, `test_calendar_nav.py`, `test_branding_header_browser.py`.

**WP3-Statusbar-Makrovertrag, umgesetzt am 2026-09-20:** `page_header(title, description=none, breadcrumbs=none, actions=none, pretitle=none, status_items=[])` bleibt für alle bisherigen Aufrufe kompatibel. Jeder Eintrag ist ein Mapping mit `label`, `value`, optional `detail` und optional `variant`; zugelassen sind `neutral`, `success`, `warning` und `danger`, unbekannte Varianten fallen auf `neutral` zurück. Das Makro rendert höchstens fünf nichtleere, beschriftete Werte als semantische Liste `dl.admin-statusbar` mit `dt.admin-statusbar-label` und `dd.admin-statusbar-value`. `0` ist ein echter Wert; `none`, leere Zeichenketten und unbeschriftete Werte werden weggelassen. Varianten nutzen `.admin-statusbar-item--neutral|success|warning|danger`; sichtbare Labels und Werte tragen die Bedeutung, nie Farbe allein. Nachweis: `test_ui_master_components_browser.py` und `test_admin_statusbar_browser.py`, inklusive Browser-Reflow bei 360 px ohne horizontalen Dokument-Overflow.

**Responsive:** Unterhalb der bestehenden Sidebar-Schwelle wird die Navigation über „Menü“ geöffnet (als Drawer/kompakte Navigation zulässig). Ohne JavaScript bleibt die Mobilnavigation in einem nativen, standardmässig geschlossenen `details.admin-nojs-nav` mit 48 px hoher, fokussierbarer Summary «Menü»; Links und Unterpunkte werden erst nach dem Öffnen angezeigt. Sie darf das Formular nicht auf eine schmale Restfläche drücken. Für Login und öffentliche Ausgaben dieses Muster nicht blind erzwingen.

##### Modul Zutaten / Grundlagen (2026-09-20)

Die Grundlagen-Endpunkte bleiben unter dem Navigationstitel «Zutaten». Der
Untertitel unterscheidet Anlage, Bearbeitung und Wiederherstellung; die lokale
Stammdatenwahl bleibt als fachlicher Filter erhalten. Liste: eine Primäraktion
«Anlegen» im Seitenkopf, Suche vor den Daten, zusätzliche Filter in einem nativen
Aufklappbereich, aktive Auswahl mit `active` und `aria-current="true"`. Zeilen
zeigen Name, Status und Zuordnung ohne technische Version; genau eine beschriftete
Bearbeiten-/Öffnen-Aktion. Leere Ergebnisse bieten einen direkten nächsten Schritt.

Der frühere offene Statusblock ist ersetzt am 2026-09-20 durch `page_header`
mit `status_items`: Aktiv/Archiviert, vorhandene Lagerorte, Erfassungszustand der
Allergene und separat deren gespeicherter Prüfstatus. Nur bestätigte Prüfung nutzt
`success`; fehlende Angaben bleiben textuelle Warnungen. Listen zeigen den echten
Archivfilter, keine scheinbare globale Anzahl. Version, IDs und Revisionen sind
keine Statusslots. Fehlende Bestands-/Aufgabensummen werden nicht erfunden.

Im Editor bleibt Stammdaten-Speichern die einzige Primäraktion.
Speichern bleibt unterhalb von 1024 px im Dokumentfluss, damit ohne JavaScript
kein Eingabefeld durch die Leiste verdeckt wird. Unabhängige
Preis-, Kennzeichnungs- und Allergenformulare speichern weiterhin separat und
neutral. Optionale Rezeptverknüpfung, Dichte, Stückgewicht und Notiz nutzen
`disclosure_section` («Weitere Optionen»), geöffnet bei Inhalt oder Feldfehler.
Technische Angaben und Archivierung sind nachrangig. Versteckte CAS-/CSRF-Felder
bleiben direkt in ihren ursprünglichen Formularen.

Allergene verwenden das gemeinsame `option_detail_group` mit `field_prefix='allergen_'`:
`allergen_CODE=absent|contains|may_contain` bleibt der POST-Vertrag. Mit JavaScript
erscheint das Präsenzfeld erst nach Auswahl; ohne JavaScript bleiben native Selects
mit «Keine Angabe» erreichbar. Erfasste Allergene und fehlerhafte Angaben
öffnen den zugehörigen Abschnitt serverseitig.
`absent` heisst weiterhin «Keine Angabe», niemals «allergenfrei». Kostformen und
Allergenbereiche nutzen mehrere Spalten ab 1024 px und eine Spalte mobil.

Nachweis: `test_wp06_measured_layout_and_native_forms` misst 360/768/1024/1440 px
mit und ohne JavaScript, Primäraktionen, Zeilen-/Seitenhöhe, Überlauf und
Tastaturfokus. `test_wp06_allergen_payload_and_review_are_independent` vergleicht
native POST-Felder vor/nach Auswahl und prüft den getrennten Prüfstatus. Bestehende
Browsertests behalten CAS-, Standortkonflikt-, Recovery- und 48-px-Assertions.

#### M02 — Rezepteditor: kompakter Ausgangszustand

Desktop; vier Beispielzutaten, zwei Schritte. Der Seitenkopf enthält ein eindeutiges Objekt, nicht mehrfach denselben Titel.

```text
+----------------------------------------------------------------------------------------------------------+
| REZEPT BEARBEITEN / Apfelmus                                         [<] Zur Rezeptliste                 |
| Entwurf  |  Beispielzustand: noch keine neuen Aenderungen                                                |
| [Rezept]  [Zutaten (4)]  [Zubereitung (2)]  [Weitere Angaben]                                            |
| [!] KI-Vorschlag: Rezept, Ausbeute und Allergene noch nicht fachlich geprueft.                           |
+----------------------------------------------------------------------------------------------------------+
| Name         [Apfelmus                                                                               ]   |
| Beschreibung [Optional                                                                               ]   |
| Ausbeute [1600] [Gramm v]     Vorbereitung [    ] Min.      Kochzeit [    ] Min.                         |
+----------------------------------------------------------------------------------------------------------+
| ZUTATEN                                                                         [+] Zutat hinzufuegen    |
| Zutat                    Menge          Einheit             Zusatzangaben / Aktionen                     |
| Aepfel                   [1800       ]  [Gramm        v]     [>] Details   [...] Aktionen                |
| Wasser                   [100        ]  [Milliliter   v]     [>] Details   [...] Aktionen                |
| Zucker                   [60         ]  [Gramm        v]     [>] Details   [...] Aktionen                |
| Zimt                     [           ]  [Auswaehlen   v]     [>] Details   [...] Aktionen                |
+----------------------------------------------------------------------------------------------------------+
| ZUBEREITUNG                                                                   [+] Schritt hinzufuegen    |
| 1  Aepfel vorbereiten ...                                   [E] Bearbeiten  [...] Aktionen               |
| 2  Fertige Menge messen und Angaben pruefen ...              [E] Bearbeiten  [...] Aktionen              |
+----------------------------------------------------------------------------------------------------------+
| [>] Kennzeichnungen und Bilder  |  [>] Quelle und technische Angaben                                     |
+----------------------------------------------------------------------------------------------------------+
| Speichern uebernimmt die Eingaben.                               [Abbrechen]  [S] Rezept speichern       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Mengen und Einheiten sind unmittelbar bearbeitbar. Nicht erst jede Zutat öffnen. Ausbeute, Vorbereitung und Kochzeit stehen bei ausreichendem Platz in einer gemeinsamen Feldgruppe. Namen und Angaben dürfen umbrechen.

**Keine Scheinlösung:** Nicht die gesamte Zutatenliste hinter einem Akkordeon verstecken. Nicht alle Zutaten gleichzeitig in grossen Detailkarten darstellen. Die Warnung bleibt sichtbar, auch wenn technische Quellenangaben geschlossen sind. Der Standardzustand darf bei echten Pflichtfehlern automatisch grösser werden.

##### Modul Rezepte (2026-09-20)

Die Rezeptübersicht verwendet M22/M23: Suche und Kennzeichnung zuerst, Titel-,
Zutaten- und Archivfilter in nativen Details. Aktive Zusatzfilter öffnen sich;
alle bestehenden GET-Parameter bleiben kombinierbar. Rezeptkarten sind ersetzt
am 2026-09-20 durch kompakte, unabhängig wachsende Zeilen: Titel/Ausbeute,
textlicher Entwurfsstatus, eine direkte Bearbeiten-/Öffnen-Aktion und weitere
Aktionen im nativen Menü. Ein ausgeklapptes Menü streckt keine Nachbarzeilen.

Alle Rezeptseiten verwenden `page_header(..., status_items=...)` mit echten
Filter-, Objekt-, Mengen- oder Importzuständen. Technische Revisionen, IDs und
Hashes sind keine Statusslots. KI-Prüfpflicht bleibt Warnung; ein gespeicherter
Entwurf oder Import bestätigt keine Allergenfreigabe. Fehlende globale Prüfzahlen
werden nicht durch Zahlen der aktuellen Ergebnisseite ersetzt.

Editor-Sprunglinks und direkt bedienbare Mengen bleiben erhalten. Kennzeichnungen
verwenden ab 1024 px drei Spalten, mobil eine; ausgewählte Werte öffnen den
Bereich. Quellenangaben stehen unter «Weitere Optionen», bei Inhalt geöffnet.
Im Import liegt ein weiterer Upload nachrangig. Zielrezept und Zielversion
erscheinen mit JavaScript bei «Vorhandenes überspringen», bei vorhandenen Werten
oder Fehlern; ohne JavaScript bleiben sie in nativen Details erreichbar. Die
Controls bleiben stets im Formular und werden weder deaktiviert noch geleert.
Bestätigter Import hat genau eine dominante Übernahmeaktion; Speichern bleibt
dann sekundär. CSRF, CAS, signierte Kontexte und alle gesendeten Werte bleiben
unverändert. Browsernachweise: Rezeptsuche, Filter, Import und Portionsplanung.

**Polish P3: Rezepte (2026-09-24).** Übersicht, Import, Bilder, Skalierung,
History und Konflikt verwenden R14/R15/R17/R22/R34 sowie M44/M51/M57/M59.
Pro Zustand bleibt eine sichtbare Primäraktion; ohne Schreibaktion wird die
vorhandene Suche bzw. Rücknavigation hervorgehoben. Bestätigte Importstapel
betonen die Übernahme, übernommene Stapel die Rückkehr zur Rezeptliste.
Verwerfen liegt unter «Weitere Aktionen», gefolgt von einer nativen
Bestätigungsstufe mit Folgetext und `btn-danger`; der Submit-Vertrag bleibt gleich.
Such-/Dateiformat-/Mengenhilfe nutzt `hint()` mit Tastatur- und No-JS-Zugang.
Sicherheits-, Übernahme-, Konflikt- und aufgelöste Referenztexte bleiben inline.
Tabellen verwenden eine Struktur mit `admin-table--stack`, `scope="col"`
und `data-label`; unter 768 px werden Zeilen gestapelt. Statusbadges verwenden
`admin-status--*` mit Icon und Text. Import-Optionsgruppen haben 1/2/3 Spalten
unter 768/ab 768/ab 1440 px. Konfliktwerte bleiben vollständig kopierbar und
schreibgeschützt in einem kompakten Grid, längere Werte mehrzeilig.
Native Formulare aktivieren `data-loading`; Namen, Werte, CSRF, CAS, signierte
Kontexte und Rollenbedingungen bleiben unverändert. Nachweise:
`test_recipe_filters_browser.py::test_polish_recipe_pages` (alle sechs Seiten,
360/1440 px, JS/No-JS, Primäraktion, Tabellen, Tastaturhilfe, Eingabewerterhalt),
Rezeptsuche, Import-Browsertests und unveränderliche Revisions-DB-Tests.

#### M03 — Rezeptzutat: nur die benötigten Details öffnen

Dieselbe Liste wie M02; die erste Zutat ist geöffnet. Andere Zutaten bleiben direkt erreichbar.

```text
+----------------------------------------------------------------------------------------------------------+
| ZUTATEN                                                                         [+] Zutat hinzufuegen    |
| Aepfel         [1800] [Gramm v]                         [v] Details schliessen  [...] Aktionen           |
+----------------------------------------------------------------------------------------------------------+
|   Zutat aus Liste       [Aepfel                                                                     v]   |
|   Bezeichnung im Rezept [Aepfel                                                                      ]   |
|   Gruppe                [Optional                         ]                                              |
|   Notiz                 [Optional                                                                  ]     |
|   [>] Quelle und technische Angaben dieser Zutat                                                         |
|   Diese Angaben werden zusammen mit dem Rezept gespeichert.                                              |
+----------------------------------------------------------------------------------------------------------+
| Wasser         [100 ] [Milliliter v]                    [>] Details            [...] Aktionen            |
| Zucker         [60  ] [Gramm v]                         [>] Details            [...] Aktionen            |
| Zimt           [    ] [Auswaehlen v]                    [>] Details            [...] Aktionen            |
+----------------------------------------------------------------------------------------------------------+
| Aenderungen noch nicht gespeichert                               [Abbrechen]  [S] Rezept speichern       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Die beiden Werte „Zutat aus Liste“ und „Bezeichnung im Rezept“ behalten ihre tatsächliche unterschiedliche Bedeutung. Nicht als Entweder-oder behandeln, solange der Bestand beide benötigt. Menge und Einheit werden nicht als zweite gleichnamige Eingaben im Detailbereich dupliziert.

**Interaktion:** Schliessen behält alle Eingaben. Mehrere Details dürfen zum Vergleichen offen bleiben. Eine gefüllte Notiz oder Gruppe wird nach dem Schliessen als kurze Zusatzinformation erkennbar. Neue und fehlerhafte Zeilen öffnen sich passend; keine eigenständige Speicherung durch „Details schliessen“.

#### M04 — Zubereitung: Kurzfassung und gezielte Bearbeitung

Ein Schritt ist geöffnet. Vollständige Anleitung, Zeit und Bildzuordnung bleiben erhalten.

```text
+----------------------------------------------------------------------------------------------------------+
| ZUBEREITUNG                                                                   [+] Schritt hinzufuegen    |
| 1  Aepfel vorbereiten ...                                  [E] Bearbeiten   [...] Aktionen               |
| 2  Fertige Menge messen ...                         [v] Bearbeitung schliessen   [...] Aktionen          |
+----------------------------------------------------------------------------------------------------------+
|   Anleitung                                                                                              |
|   [Fertige Ausbeute in der angegebenen Einheit messen. Vorschlagsmenge vor Kuechenfreigabe pruefen.   ]  |
|   [                                                                                                 ]    |
|   Dauer [    ] Minuten            Bild zum Schritt [Kein Bild ausgewaehlt                          v]    |
|   Bildzuordnung und Dauer sind nur dann Pflicht, wenn der bestehende Vertrag dies verlangt.              |
+----------------------------------------------------------------------------------------------------------+
| Aenderungen noch nicht gespeichert                               [Abbrechen]  [S] Rezept speichern       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Die Kurzfassung unterstützt Orientierung; die komplette Anleitung bleibt im Editor sichtbar und vergrösserbar. Keine Zeichen abschneiden und als vollständige Anweisung ausgeben. Eine fehlende Dauer bedeutet nicht automatisch null Minuten.

**Speichern:** Die Zeile ist Teil desselben Rezeptformulars. Keine zweite unabhängige Schritt-Speicherung einführen. Eine Bildreferenz bleibt auch erhalten, wenn ihre Detailsteuerung geschlossen oder ein Bildname derzeit nicht auflösbar ist.

#### M05 — Zeilenaktionen: kompakt, beschriftet und kontextbezogen

Geöffnetes Aktionsmenü einer Zutat. Nur im Bestand vorhandene Operationen anbieten.

```text
+----------------------------------------------------------------------------------------------------------+
| Wasser             [100] [Milliliter v]                  [>] Details    [...] Aktionen                   |
|                                                                          +--------------------------+    |
|                                                                          | [+] Davor einfuegen      |    |
|                                                                          | [^] Nach oben            |    |
|                                                                          | [v] Nach unten           |    |
|                                                                          | [X] Aus Rezept entfernen |    |
|                                                                          +--------------------------+    |
| Aktionen betreffen diese Rezeptzeile, nicht die Zutat im zentralen Katalog.                              |
| Reihenfolge und Eingaben bleiben beim bestehenden Formularweg erhalten.                                  |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Kurze sichtbare Wörter; zugängliche Namen bei Bedarf um den Kontext ergänzen, beispielsweise „Wasser nach oben verschieben“. Pfeile passen zur vertikalen Reihenfolge. Am Anfang/Ende unmögliche Bewegungen korrekt deaktivieren oder weglassen. Keine erfundene Funktion „danach einfügen“, wenn der bestehende Weg sie nicht unterstützt.

**Vertrag:** Die zuvor untersuchten Rezeptaktionen verwendeten eigene Submit-/`formaction`-Wege. Aktuellen Stand prüfen und vorhandene `formnovalidate`-Semantik für Strukturaktionen erhalten. Nicht durch neue pauschale Validierungsumgehungen oder eine zweite clientseitige Sortierlogik ersetzen. Nach der Aktion zum betroffenen Objekt zurückkehren.

#### M06 — Rezepteditor auf dem Smartphone

Schmaler Viewport: Name, Menge, Einheit und beschriftete Aktionen bleiben nutzbar. Keine verkleinerte Desktoptabelle.

```text
+------------------------------------------+
| [Menue]             [<] Rezeptliste      |
| Apfelmus bearbeiten                      |
| [!] KI-Entwurf, noch ungeprueft.         |
| [Rezept] [Zutaten] [Zubereitung]         |
+------------------------------------------+
| ZUTATEN (4)                              |
| Aepfel                                   |
| Menge           Einheit                  |
| [1800        ]  [Gramm       v]          |
| [>] Details     [...] Aktionen           |
+------------------------------------------+
| Wasser                                   |
| Menge           Einheit                  |
| [100         ]  [Milliliter  v]          |
| [>] Details     [...] Aktionen           |
+------------------------------------------+
| Zucker                                   |
| Menge           Einheit                  |
| [60          ]  [Gramm       v]          |
| [>] Details     [...] Aktionen           |
+------------------------------------------+
| Weitere Zutaten folgen im Fluss.         |
| [+] Zutat hinzufuegen                    |
+------------------------------------------+
| Aenderungen nicht gespeichert            |
| [S] Rezept speichern                     |
| [Abbrechen]                              |
+------------------------------------------+
```

**Pflicht:** Umordnen statt schrumpfen. Keine horizontal scrollende Gesamtdokumentseite. Abschnittslinks dürfen umbrechen; keine abgeschnittene Tabreihe. Menge und Einheit bleiben sichtbar zugeordnet, auch ohne Tabellenkopf.

**Mobile Leiste:** Bei eingeblendeter Tastatur oder geringer Höhe darf die Speicherleiste in den Dokumentfluss wechseln. Sie verdeckt weder Felder noch Fehler oder Fokus. Die Skizze verspricht nicht, vier Zutaten samt kompletter Rezeptbasis auf 390 × 844 gleichzeitig zu zeigen.

#### M07 — Menüübersicht: Text und Handlung vor Bildern

Geplante Menüeinträge aus verschiedenen Wochen; kein neu erfundener Rezeptkatalog.

```text
+----------------------------------------------------------------------------------------------------------+
| MENUES & BAUSTEINE / Gespeicherte Menues                                                                 |
| [Menues] [Bausteine] [Zutaten] [Rezepte] [Kochbuecher] [Weitere vorhandene Bereiche]                     |
| [Cafeteria] [Patienten]                                                                                  |
| Menue oder Baustein suchen [                                                 ]  [?] Suchen               |
| Ansicht [Liste] [Karten]                                                                                 |
+----------------------------------------------------------------------------------------------------------+
| 11.09.2026 / Mittag / Menue 1                                                                            |
| Gebratenes Zanderfilet  |  Salzkartoffeln, Rahmspinat                    [E] Im Wochenplan oeffnen       |
| Gespeicherter Pruefstand: Geprueft*  |  [!] Allergenangaben nicht erfasst   [>] Hinweise                 |
+----------------------------------------------------------------------------------------------------------+
| 11.09.2026 / Mittag / Vegetarisch                                                                        |
| Falafel-Teller  |  Hummus, Ofengemuese                                 [E] Im Wochenplan oeffnen         |
| Gespeicherter Pruefstand: Geprueft*  |  [!] Allergenangaben nicht erfasst   [>] Hinweise                 |
+----------------------------------------------------------------------------------------------------------+
| * Den belegten Geltungsbereich der bestehenden Pruefung eindeutig beschriften.                           |
| Weitere Treffer folgen kompakt. Seitennavigation nur bei tatsaechlich mehreren Seiten.                   |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Öffnen führt zum tatsächlichen geplanten Eintrag, nicht unbeabsichtigt zu einem globalen Rezept. Sichtbarer Zeitraum, Menüart und relevante Warnung bleiben am Objekt. Lange interne Hinweise sind erreichbar, aber nicht der Hauptinhalt jeder Karte.

**Status:** „Geprüft“ darf nur den verifizierten bestehenden Prüfumfang wiedergeben. Der Stern ist ein Hinweis an den Agenten, keine dauerhaft nötige Fussnotenlösung im Produkt. Bedeutung am Code klären; keine Statusdaten ändern. Vorhandene Bilder nicht löschen, aber aus der Standardübersicht zurücknehmen. KI-Kennzeichnung in bestehenden Bildansichten erhalten.

#### M08 — Bausteinliste mit gezielt erweiterten Filtern

Liste mit wenigen Standardfiltern; zusätzliche Filter sind ausdrücklich geöffnet.

```text
+----------------------------------------------------------------------------------------------------------+
| BAUSTEINE                                                                    [+] Baustein hinzufuegen    |
| Suche [                                                   ]   [?] Suchen                                 |
| Kategorie [Alle v]     Status [Aktiv v]     [v] Weitere Filter                                           |
+----------------------------------------------------------------------------------------------------------+
| Allergen [Milch v]     Praesenz [Enthaelt v]     Herkunft [Alle Laender v]                               |
| [Filter anwenden]     [Filter zuruecksetzen]                                                             |
+----------------------------------------------------------------------------------------------------------+
| Aktive Filter: Aktiv | enthaelt Milch. Zusatzfilter bleiben auch eingeklappt erkennbar.                  |
| Name                 Kategorie       Angaben                         Verwendung          Aktion          |
| Kartoffelstock       Beilage         Enthaelt Milch                  2 Menues             [E] Bearbeiten |
| Weitere passende Treffer folgen; keine erfundene Gesamtzahl.                                             |
+----------------------------------------------------------------------------------------------------------+
| Eingeklappte Zusatzfilter duerfen nicht zu einer unerklaerlichen leeren Liste fuehren.                   |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Suche und höchstens zwei häufige Filter in der Standardansicht. Weitere vorhandene Filter bleiben erreichbar; aktuelle Auswahl und Reset sichtbar. Nutze echte Ländernamen, sofern die bestehende Zuordnung verfügbar ist, nicht ausschliesslich Flaggen oder Codes.

**Funktion:** Bestehende Suchparameter und deren Kombination erhalten. Kein Browserfilter nur über die aktuelle Seite einer serverseitig paginierten Liste. In einer leeren Ergebnismenge unterscheiden, ob Filter, Datenbestand, Rechte oder ein Ladefehler die Ursache sind; siehe M20.

#### M09 — Wochenübersicht: auswählen zuerst, anlegen bei Bedarf

Normalansicht mit geschlossenem Erstellformular. Dieses Muster gilt analog für Listen mit selten genutzter Anlagefunktion.

```text
+----------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Wochenuebersicht                                                 [+] Neue Woche anlegen     |
| Bereich [Cafeteria v]                                                                                    |
+----------------------------------------------------------------------------------------------------------+
| Zeitraum                           Kalenderwoche     Vorhandener Stand          Aktion                   |
| 7.-13. September 2026              KW 37             Veroeffentlicht           [E] Woche oeffnen         |
|                                                                                [...] Aktionen            |
| 31. August-6. September 2026        KW 36             Noch zu pruefen           [E] Woche oeffnen        |
|                                                                                [...] Aktionen            |
+----------------------------------------------------------------------------------------------------------+
| Die Anlage wird erst ueber den Button oben geoeffnet; keine zweite staendige Buttonreihe.                |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Nur einen sichtbaren Einstieg „Neue Woche anlegen“ im Seitenkopf platzieren. Bei Bedarf den bestehenden Formularbereich unterhalb der Werkzeugleiste öffnen: Wochenbeginn, Zusatzname, Hinweis und vorhandene Anlageaktion. Die letzte Zeile der Skizze ist eine Anmerkung, kein zusätzlicher Produkttext. Bei Formularfehlern bleibt der Bereich mit Eingaben offen.

**Semantik:** ISO-Woche und tatsächliche Cafeteria-Ausgabetage unterscheiden. Datumsbereich aus dem geplanten Zeitraum; Freititel ist keine verlässliche Datumsquelle. Kopieraktionen erklären Quelle, Ziel und tatsächliche Überschreibwirkung anhand des Bestands. Keine Zusicherungen erfinden.

#### M10 — Cafeteriaplan: Arbeitsraster statt Verwaltungsblöcke

Breiter Desktop mit ausreichender realer Spaltenbreite; fünf Tage und die zwei vorhandenen Menüarten.

```text
+----------------------------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Cafeteria  |  7.-11. September 2026  |  KW 37                                                                 |
| [Cafeteria] [Patienten] [Wochenuebersicht]                                                                                 |
| [<] Vorherige Woche   [Woche auswaehlen]   [>] Naechste Woche                                                              |
| Veroeffentlichungsstand: [vorhandener Stand]    Pruefung: [vorhandener Befund]                                             |
| [O] Vorschau   [...] Weitere Aktionen                        [!] Offene Angaben pruefen                                    |
+----------------------------------------------------------------------------------------------------------------------------+
+------------------------+------------------------+------------------------+------------------------+------------------------+
| Montag 7.9.            | Dienstag 8.9.          | Mittwoch 9.9.          | Donnerstag 10.9.       | Freitag 11.9.          |
+------------------------+------------------------+------------------------+------------------------+------------------------+
| MENUE 1                | MENUE 1                | MENUE 1                | MENUE 1                | MENUE 1                |
| Pouletbrust an         | Hackbraten             | Rindsgeschnetzeltes    | Schweinsragout         | Gebratenes             |
| Kraeutersauce          | an Rosmarinjus         |                        | Tessiner Art           | Zanderfilet            |
| Kartoffelstock         | Kartoffelgratin        | Nudeln                 | Polenta, Bohnen        | Salzkartoffeln         |
| [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   |
| Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  |
| Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     |
| [>] Hinweise           | [>] Hinweise           | [>] Hinweise           | [>] Hinweise           | [>] Hinweise           |
| [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         |
+------------------------+------------------------+------------------------+------------------------+------------------------+
| VEGETARISCH            | VEGETARISCH            | VEGETARISCH            | VEGETARISCH            | VEGETARISCH            |
| Spinat-Ricotta-        | Gemuese-Curry          | Risotto                | Gemuesegratin          | Falafel-Teller         |
| Ravioli                |                        |                        |                        |                        |
| Tomatensauce           | Reis                   | Gemuese                | Salat                  | Hummus, Gemuese        |
| [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   | [!] Allergene fehlen   |
| Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  | Mitarbeitende: CHF 11  |
| Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     | Externe: CHF 16.60     |
| [>] Hinweise           | [>] Hinweise           | [>] Hinweise           | [>] Hinweise           | [>] Hinweise           |
| [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         | [E] Bearbeiten         |
+------------------------+------------------------+------------------------+------------------------+------------------------+
+----------------------------------------------------------------------------------------------------------------------------+
| Alle Preise sind Beispieldaten. Beide Zielgruppen bleiben bei jedem Menue eindeutig zugeordnet.                            |
| [>] Wochenangaben aendern  |  Tages-/Ausgabeangaben am jeweiligen Tag gezielt oeffnen.                                     |
+----------------------------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Gerichte unmittelbar unter der kompakten Wochensteuerung. Konkrete vorhandene Warnungen und beide Cafeteriapreise sichtbar halten. Nur die ausführlichen Zusatzhinweise liegen hinter „Hinweise“. Keine zusätzlichen Menüarten aus früheren Bildern übernehmen.

**Responsive:** Wenn fünf ausreichend lesbare Spalten nicht passen, in chronologische Tagesabschnitte wechseln. Nicht Schrift verkleinern oder vollständige Namen abschneiden. Beide Preise müssen dem richtigen Menü und der richtigen Zielgruppe zugeordnet bleiben; fehlende Werte nicht raten.

#### M11 — Patientenplan: kompakte Tagesgruppen mit Mittag und Abend

Patienten bleiben ein Sieben-Tage-Plan. Darstellung der Mahlzeiten nebeneinander nur bei genügend Platz.

```text
+----------------------------------------------------------------------------------------------------------+
| PATIENTENPLAN / 7.-13. September 2026 / KW 37                                                            |
| [Cafeteria] [Patienten] [Wochenuebersicht]                                                               |
| Veroeffentlicht  |  [!] Allergenangaben fehlen. Gespeicherten Pruefstand separat erklaeren.              |
| [O] Vorschau  [...] Weitere Aktionen                        [!] Offene Angaben pruefen                   |
+----------------------------------------------------------------------------------------------------------+
| MONTAG, 7. SEPTEMBER                                                                                     |
| MITTAG                                              ABEND                                                |
| Geoeffnet | Zeiten nicht erfasst                     Geoeffnet | Zeiten nicht erfasst                    |
| [E] Ausgabeangaben aendern                           [E] Ausgabeangaben aendern                          |
|                                                                                                          |
| Menue 1: Pouletgeschnetzeltes                        Menue 1: Schinken-Kaese-Toast                       |
| Reis, Zucchetti                                     Tomatensalat                                         |
| [!] Allergene nicht erfasst                         [!] Allergene nicht erfasst                          |
| [E] Bearbeiten  [>] Hinweise                         [E] Bearbeiten  [>] Hinweise                        |
|                                                                                                          |
| Vegetarisch: Gemuesegeschnetzeltes                   Vegetarisch: Gemuese-Toast                          |
| Reis, Zucchetti                                     Tomatensalat                                         |
| [!] Allergene nicht erfasst                         [!] Allergene nicht erfasst                          |
| [E] Bearbeiten  [>] Hinweise                         [E] Bearbeiten  [>] Hinweise                        |
+----------------------------------------------------------------------------------------------------------+
| DIENSTAG bis SONNTAG folgen mit demselben Tagesmuster.                                                   |
| Alle 7 Tage x 2 Mahlzeiten x 2 vorhandenen Menuearten bleiben erreichbar. Keine Preise.                  |
| [>] Wochenangaben aendern                                                                                |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Die nächsten Tage folgen tatsächlich als Tagesgruppen; die Zusammenfassungszeile ist nur eine Verkürzung der Zeichnung. Weder Wochenende noch Abendangebot weglassen. Gefüllte Hinweise kurz erkennbar machen. Standardmässig nicht die grossen Zeit-/Betriebsformulare vor jedes Menü stellen.

#### M11b — Gemeinsame Gänge (Suppe, Dessert)

Suppe und Dessert sind eigenständige Planungszuweisungen pro Datum, Profil und Mahlzeit, nicht Beilagen eines Hauptgerichts. In der Wochenansicht steht die gemeinsame Suppe vor den Hauptmenüs, das gemeinsame Dessert danach; einmal je Ausgabe, nicht als zusätzliche grosse Menükarte. Menüabweichungen werden gezielt geöffnet und an der betroffenen Variante bezeichnet. „Noch nicht geplant“ und „nicht angeboten“ bleiben unterscheidbar. Fehlende Allergene werden nie zu einer positiven Aussage umgedeutet; „nicht angeboten“ trägt keine Kennzeichnung. Die globale Infoleiste zählt gemeinsame Gänge einmal, nicht je Menüvariante. Der Küchenkalender zeigt Gänge kompakt unter der Ausgabe, nicht als weitere Hauptgerichte.

**Admin-Woche:** Der Gang-Editor ist standardmässig zugeklappt, Bedienelemente sind mindestens 48 px hoch. Die Tab-Reihenfolge Veröffentlichen → Vorschau → Prüfen bleibt. Menükarten-Bilder behalten ihr Format (die 64–96-px-Regel gilt nur für Gang-Vorschaubilder).

**Signage und öffentliche Seiten:** Signage-Gänge stehen im vorhandenen Kopfband der Mahlzeit (Patienten-Tag `header.meal-label`, Patienten-Woche `.meal-name`, Cafeteria-Tag `.signage-kicker`), nie als zusätzliche Zeile/Karte; Schrift mindestens 18 px bei 1920 px Breite, skalierend. Bei langen Gangtiteln bleiben Allergen-/Label-Symbole immer vollständig sichtbar (`flex-shrink: 0`), der Titel wird sichtbar mit Ellipse gekürzt. Auf Wochenboards tragen Gänge nur Symbole ohne Allergen-Langtext (wie reguläre Optionen dort). Öffentliche Seiten zeigen eine kompakte Gangzeile mit Token-Abständen, Allergen-/Label-Kennzeichnung über dasselbe Makro wie reguläre Optionen; das Höhenbudget der Patientenwoche bleibt gewahrt.

**Status und Wirkung:** Eine Veröffentlichung sagt nichts über fehlende Angaben oder ungespeicherte Änderungen aus. Den vorhandenen Prüfstand separat erklären. „Ausgabeangaben ändern“ öffnet ausschliesslich das bestehende Formular und dessen eigene Speicheraktion. Kein globales „Alles speichern“, wenn es keine gemeinsame Transaktion gibt.

##### Modul Gänge (Suppe/Dessert) im Wochenplan (2026-09-20)

Nicht geplante Gänge erhalten eine kompakte «Suppe planen»-/«Dessert planen»-Aktion; bestehende Gänge eine beschriftete Aktion «Bearbeiten». Ziele sind die vorhandenen Gangfelder im atomaren Ausgabeformular. Statuswerte `unplanned`, `planned`, `not_offered` und `inherit` bleiben unverändert. Die Rezeptauswahl liegt in einem nativen Detailbereich, offen bei vorhandener Auswahl oder Formularfehler. Suche und Abweichungen stehen nachrangig; «Weitere Optionen» öffnet bei Abweichungen oder Fehlern automatisch. Keine Auswahl wird beim Einklappen deaktiviert, zurückgesetzt oder ausgelassen. Ein Formularfuss enthält genau eine Aktion «Speichern».

Die vorhandene globale Gangwarnung bleibt Aufgabe der Wochenplan-Statusbar (WP21): `course_issues.affected_assignments` und `course_issues.missing_allergens`, Ziel `#course-issues`. Kein zweiter Seitenkopf im wiederholten Partial. Rezept-Suchfelder erhalten pro Ausgabe eindeutige IDs. CSP, No-JS-Bedienbarkeit, 48-px-Ziele und alle POST-/CAS-Felder bleiben erhalten. Public-/Signage-Ausgaben bleiben unverändert. Nachweise: `test_course_browser.py`, `test_course_week_html.py`, `test_course_html_captures.py`.

#### M12 — Menüeditor: breite Hauptarbeit, schmalerer Prüfkontext

Volle Seitenbreite mit gemeinsamem Zwei-Spalten-Layout. Auf schmalen Geräten stehen die Bereiche untereinander.

```text
+-------------------------------------------------------------------+   +----------------------------------+
| MENUE BEARBEITEN / Dienstag 8. September                          |   | PRUEFUNG                         |
| Patienten / Mittag / Menue 1                                      |   | Zuletzt gespeicherter Stand      |
+-------------------------------------------------------------------+   +----------------------------------+
| Titel [Hackbraten an Rosmarinjus                               ]  |   | [!] Allergene nicht erfasst      |
| Beschreibung [Optional                                       ]    |   | [!] Herkunft nicht erfasst       |
+-------------------------------------------------------------------+   | Kennzeichnungen: nicht erfasst   |
| BAUSTEINE                           [+] Baustein hinzufuegen      |   |                                  |
| Kartoffelgratin              [E] Aendern  [...] Aktionen          |   | Neue Eingaben zuerst speichern.  |
| Broccoli                    [E] Aendern  [...] Aktionen           |   |                                  |
+-------------------------------------------------------------------+   | [Pruefung oeffnen]               |
| [>] Ausfuehrlicher Pruefhinweis vorhanden                         |   +----------------------------------+
| [E] Allergene bearbeiten   [E] Herkunft bearbeiten                |   | Bestaetigung nur nach dem        |
| Vorhandene Felder unten oder am Zielabschnitt bearbeiten.         |   | vorhandenen Pruefablauf.         |
+-------------------------------------------------------------------+   | Keine neue Freigabelogik.        |
| Nicht gespeichert                  [S] Menue speichern            |   +----------------------------------+
+-------------------------------------------------------------------+
```

**Pflicht:** Hauptformular deutlich breiter als der Prüfkontext; auf Desktop beispielsweise ungefähr zwei Drittel zu einem Drittel, an reale Inhalte angepasst. Keine schmale gesamte Mittelsäule. Prüfzusammenfassung enthält direkte Links zu bestehenden Feldern, soweit möglich, nicht nur passive Meldungen.

**Geltungsbereich:** Diese Skizze zeigt Patienten, deshalb ohne Preisfelder. In der Cafeteria bleiben beide vorhandenen Preisgruppen als kompakte Feldgruppe erhalten. Menübausteine dürfen die bestehende klare Auswahlart Katalog/Freitext erhalten; Rezeptzutaten aus M03 sind fachlich etwas anderes. Eine existierende seitliche Bearbeitung verwendet dasselbe Formularmuster; keine neue Panel-API bauen.

##### Modul Menüs und Menüeditor inkl. Allergene (2026-09-20)

Die Menüliste bleibt die Standardansicht. M22 liefert Suche und Profilwechsel;
M23 wird als semantische Tabelle mit mobiler Zeilendarstellung angewendet.
Je Menü steht genau ein zusammengefasster Prüfstatus mit Text neben «Bearbeiten».
Karten folgen der Höhe ihrer jeweiligen Rasterzeile; mobil erzwingt eine
aufgeklappte Karte keine Leerfläche in den übrigen Karten.
Die Statusbar zeigt Profil und offene Prüfungen ausschliesslich für die geladene
Ergebnisseite; fehlende Gesamt-, Wochen- oder Veröffentlichungsdaten werden nicht
ersetzt. Im Editor stammen Profil und Tag aus dem bestehenden Kontext. Fehlende
gespeicherte Allergenangaben bleiben eine Warnung, nie eine Frei-von-Aussage.

Die bisherige permanente Allergen-Detailspalte ist ersetzt am 2026-09-20 durch
`option_detail_group(allergens, submitted=submitted, errors=errors,
manual=not is_auto['allergen'])` (M21). Auswahl und Präsenz bleiben indexgepaart
im selben Container. In der schmaleren Editorspalte steht die Präsenz unter dem
gewählten Allergen, damit Namen und Werte lesbar bleiben. Herkunft verwendet eine
gemeinsame Kopfzeile und zugänglich beschriftete Wiederholfelder. Reihenfolge der
Arbeitsbereiche: Titel/Beilage, Bausteine, Kennzeichnungen, weitere Angaben.
`disclosure_section` öffnet weitere Angaben bei Inhalt oder Fehler. Verdeckte
CSRF-/Versionsfelder bleiben unmittelbar im Formular; gespeicherter Prüfstand und
Prüfformular bleiben sichtbar und getrennt vom Entwurf. Die bestehende Sticky-Leiste
behält «Menü speichern» als einzige Primäraktion.

Pflichtnachweis: tatsächliche Referenz-POSTs beider Profile mit/ohne JavaScript,
identische Feldwerte und Reihenfolge innerhalb aller Wiederholfelder sowie
unsortiertes An-/Abwählen. No-JS darf beim Austausch ausgewählter Allergene keine
alte Präsenz einer neuen Checkbox zuordnen. Der WP04-Regressionsfall dokumentiert
hier einen offenen Fehler des gemeinsamen Makro-/Parser-Vertrags: gleiche
Listenlängen reichen nicht als Paarungsnachweis. Dieser Fall blockiert die
Integration bis zur separaten Korrektur des gemeinsamen Vertrags. Keine UI-Freigabe
aus erfolgreichen Referenz-POSTs allein ableiten.

**Polish P3:** Die Listenansicht nutzt `admin-table--stack` mit `data-label`;
Prüfstand ist `admin-status--warning`/`--success` inkl. Allergenhinweis. Ansichtshilfe
in `hint()`.

#### M13 — Baustein bearbeiten: eindeutige Allergenfelder

Editormuster für einen zentralen Baustein. Beispielwerte sind Eingaben, keine fachliche Deklaration.

```text
+----------------------------------------------------------------------------------------------------------+
| BAUSTEIN BEARBEITEN / Kartoffelstock                                       [<] Zur Bausteinliste         |
| Wird in 2 Menues verwendet  |  Aktiv                                                                     |
+----------------------------------------------------------------------------------------------------------+
| Name [Kartoffelstock                     ]  Kategorie [Beilage v]  Herkunft [Nicht erfasst v]            |
| Kennzeichnungen: [ ] Vegan   [ ] Vegetarisch   [ ] Glutenfrei   [ ] Laktosefrei                          |
+----------------------------------------------------------------------------------------------------------+
| ALLERGENE                                                                                                |
| [x] Milch                     Praesenz [Enthaelt      v]                                                 |
| [x] Glutenhaltiges Getreide    Praesenz [Kann enthalten v]                                               |
| [ ] Eier                      Nicht ausgewaehlt                                                          |
| [ ] Fisch                     Nicht ausgewaehlt                                                          |
| [>] Weitere Allergene anzeigen                                                                           |
| [!] Nicht ausgewaehlt bedeutet nicht: allergenfrei bestaetigt.                                           |
+----------------------------------------------------------------------------------------------------------+
| [>] Verwendung und Wirkung zentraler Aenderungen                                                         |
| [...] Weitere Aktionen, einschliesslich vorhandener Archivierung                                         |
+----------------------------------------------------------------------------------------------------------+
| Aenderungen noch nicht gespeichert                            [Abbrechen]  [S] Baustein speichern        |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Keine scheinbar aktive „enthält“-Auswahl neben einem nicht gewählten Allergen. Nicht gewählte zusätzliche Allergene bleiben erreichbar; ausgewählte oder fehlerhafte Angaben dürfen nicht verdeckt werden. Kennzeichnungen nicht automatisch aus Namen oder Allergenfeldern ableiten.

**Vertrag:** Vor dem Deaktivieren oder Ausblenden von Controls die POST-Semantik prüfen. Nur eine Darstellung ändern, keine Werte verlieren oder hidden/disabled-Verhalten neu erfinden. Der Verwendungszähler ist nur bei belegten Daten zulässig. Die Wirkung zentraler Änderungen auf bestehende Menüs anhand des Codes erklären; nicht als garantiert unveränderliche Vergangenheit ausgeben.

##### Modul Bausteine (2026-09-20)

M08/M13 folgen dem gemeinsamen Seitenrahmen: «Bausteine» als Titel, Objektname
im Editor als Kontext. `page_header(status_items=...)` zeigt den Bereich aus
`profile`/`family`; im Editor zusätzlich Aktiv-/Archivzustand aus `component.active`,
Gültigkeit aus `component.profile_scope` und Verwendung aus `component.usage_count`.
Verwendung erklärt die Reichweite zentraler Änderungen. Aktiv ist neutral,
archiviert eine textliche Warnung; kein Slot bestätigt eine Allergenprüfung.
Revisionen/IDs bleiben aus der Statusbar. Fehlende Prüf- oder Publikationsdaten
werden nicht erfunden; zusätzliche Quellen benötigen ein separates Backend-WP.

Die Liste hat eine dominante Aktion «Anlegen» im Kopf. Ihr bestehendes Ankerziel
öffnet das native Anlageformular auch ohne JavaScript. Suchen, Formularsubmit und
Zeilenaktionen bleiben neutral; gefüllte oder fehlerhafte Anlagen öffnen sich.
Suche, Kategorie und Status stehen zuerst, Zusatzfilter in nativen Details;
aktive Zusatzfilter bleiben in der Zusammenfassung sichtbar. Zurücksetzen erscheint
nur bei aktiven Filtern. Leere Ergebnisse bieten eine passende direkte Folgeaktion.

Die bisherigen hohen mobilen Karten sind ersetzt am 2026-09-20 durch kompakte,
priorisierte Zeilen mit einer beschrifteten Bearbeiten-Aktion. Kennzeichnungen
zeigen höchstens zwei Labels; weitere bleiben über «+n» vollständig erreichbar.
Allergenauswahl nutzt ab 1024 px drei Spalten, mobil eine. Haken und Rahmen zeigen
die Auswahl; Präsenz erscheint an der gewählten Option. Fehlende Auswahl bestätigt
keine Allergenfreiheit. Feldnamen `allergen_code` und `allergen_presence__<CODE>`,
Werte, Standardwerte, Reihenfolge und Aktivierung der Controls bleiben unverändert.

Optionale Lebensmittelzuordnung liegt in «Weitere Optionen», bei Inhalt oder Fehler
geöffnet. Archivieren/Reaktivieren samt Folgetext und Bestätigung liegt in «Weitere
Aktionen». CSRF-/CAS-Felder bleiben direkt in ihren Formularen. Der Editor behält
eine erreichbare Speicheraktion; No-JS, Fokus und 48-px-Ziele bleiben verbindlich.
Neue Aktionslabels und Icons verwenden `ui/_semantic.html`; bestehende Fachtexte
bleiben bis zur zentralen Übersetzungsmigration erhalten. Browsernachweise in den
drei Komponenten-Testdateien umfassen 360/768/1024/1440 px, FormData-Parität,
Tastatur, No-JS, Fehlereingaben und Archivierung. Die Route-Matrix aktualisiert WP20.

#### M14 — Drucken und Vorschau: Arbeitsauftrag von Layoutverwaltung trennen

Beispiel mit bewusst unterschiedlichen Zeiträumen für gewählte gespeicherte Woche und veröffentlichten Stand.

```text
+----------------------------------------------------------------------------------------------------------+
| VORSCHAU & BILDSCHIRME / Wochenplan drucken                                                              |
| [Wochenplan drucken] [Bildschirme] [Drucklayouts] [Weitere vorhandene Ausgaben]                          |
+----------------------------------------------------------------------------------------------------------+
| Bereich [Cafeteria v]      Gespeicherte Woche [7.-13. September 2026 / KW 37 v]                          |
| Gewaehlter Stand: gespeicherte Woche 37, nicht automatisch der veroeffentlichte Plan.                    |
| [P] PDF der gewaehlten Woche oeffnen                                                                     |
+----------------------------------------------------------------------------------------------------------+
| [v] Aktuell veroeffentlichten Plan drucken                                                               |
|     Beispiel: anderer Stand, 31. August-6. September 2026 / KW 36.                                       |
|     [P] Veroeffentlichten Plan drucken                                                                   |
+----------------------------------------------------------------------------------------------------------+
| [>] Drucklayout aendern       [>] Fruehere Versionen       [>] Inhalte bearbeiten                        |
| Rezeptdruck bleibt ein eigener bestehender Unterbereich.                                                 |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Die prominenteste Aktion öffnet genau die gewählte gespeicherte Woche. Der veröffentlichte Plan ist eine andere vorhandene Aktion mit eigenem Datenstand; Datum nur nennen, wenn bekannt. Vorhandene Wochenauswahlmechanik weiterverwenden, keinen neuen universellen Pickervertrag erfinden.

**Layoutverwaltung:** Für normales Drucken keine Versionsverwaltung durchlaufen. Entwurf ansehen und aktivieren bleiben getrennt. Keine neue PDF-Engine oder Vorschau-API. Patienten- und Cafeteriaausgaben behalten ihre eigene Preis- und Mahlzeitenlogik.

##### Modul Vorschau & Bildschirme (2026-09-20)

Die Bildschirmverwaltung zeigt kompakte Karten mit genau einer neutralen Direktaktion
«Öffnen». Weitere Ausgabeziele stehen unter «Weitere Aktionen»; eingebettete Vorschauen
sind standardmässig geschlossen und nativ per Tastatur auch ohne JavaScript erreichbar.
Ab 1024 px stehen zwei Karten nebeneinander, mobil eine. Keine Geräteverfügbarkeit aus
vorhandenen Ausgabelinks ableiten.

`page_header(..., status_items=...)` zeigt die vorhandene Web-Wochenvorlage je Bereich
aus `assignments`, beim Zuweisen die aktuelle Vorlage aus `active`. Vorgaben bleiben
neutral; «Aktiv» bezeichnet nur eine gespeicherte Zuordnung. Versionen stehen geschlossen
unter «Details», nicht in der Statusbar. Das Zuweisungsformular nutzt
`disclosure_section` und `form_footer`; Fehler öffnen den Formularbereich. Versteckte
Felder und deren Reihenfolge bleiben direkt im Formular unverändert.

Die eigenständige gespeicherte Wochenvorschau nutzt denselben Seitenkopf und zeigt
gewählte Woche und deren Veröffentlichungsstand. Sie bleibt skriptfrei und trennt
gespeicherte Woche und veröffentlichten Plan. Vorschauinhalt und Signage-Ausgaben
bleiben unverändert. Modulprüfungen erfassen 360/768/1024/1440 px, Karten-/Seitenhöhe,
geschlossene Vorschauen, Feldreihenfolge, No-JS, Tastatur und echten 200-%-Zoom.

##### Modul Vorlagen & Druck (2026-09-20)

Die Übersicht «Vorlagen» folgt M01/M14/M23/M25: Titel entspricht dem bestehenden
Seitentitel der Katalogtests; die Beschreibung nennt Druckvorlagen für gespeicherte
Wochen und Rezeptrevisionen. Genau eine Primäraktion im `main` öffnet das PDF der
gewählten Cafeteria-Woche. Bereichs-PDFs, veröffentlichter Plan und Editorlinks
bleiben sekundär. Die Statusbar nutzt vorhandene Katalogwerte: Woche aus `week`,
aktive Druckvorlage je Bereich aus `catalogs.*.active.name` (`success` nur für den
aktivierten Stand), Rezeptvorlage aus `catalogs.rezepte.active.name`. Anker führen
zur Wochenauswahl bzw. zum Bereichstab. IDs, Revisionsnummern und `row_version`
gehören nicht in die Statusbar.

Die früheren grossen Bereichskarten sind ersetzt am 2026-09-20 durch eine Filterzeile
(Woche), Bereichstabs mit `active` und `aria-current="true"`, eine kompakte
Aktiven-Zeile und nativ geschlossene «Frühere Versionen». Listenzeilen bleiben
`li[data-template-id]` mit Name, einzeiligem Stand, Statusbadge und beschrifteter
Zeilenaktion «Vorlageneditor öffnen». Rezept- und Gerichtvorlagen stehen in zwei
Spalten ab 1024 px. Screen-Vorlagen sind kompakte Zeilen; Zutaten/Rezepte/Kochbücher
liegen unter «Weitere Optionen».

Der Editor trägt denselben Seitentitel. Statusbar: Bereich aus dem Profil, Aktiv/
Nicht aktiv/Archiviert aus `document`/`template.archived` (`success` nur wenn die
angezeigte Revision aktiv ist), Woche aus `week` bzw. Rezepttitel. Speichern ist
die einzige Primäraktion; Aktivieren, Kopieren und Archivieren bleiben nachrangig.
Archivieren behält die native Pflicht-Checkbox ausserhalb des POST-Formulars
(`form="archive-form"`, ohne Feldnamen). Versteckte Felder `_csrf`, `version`,
`revision`, `action` bleiben direkt im Formular. Layoutfelder bleiben vollständig
im DOM und byte-gleich im POST. Modul-CSS: `admin-vorlagen-druck.css`. Nachweis:
`test_print_template_browser.py`, `test_print_template_archive_browser.py`,
`test_print_template_layout_forms.py` (360/768/1024/1440, No-JS, Tastatur).

#### M15 — Einstellungen: kompakte Zusammenfassung, Bearbeitung bei Bedarf

Generisches Muster für vorhandene Einstellungen; keine neuen Einstelloptionen daraus ableiten.

```text
+----------------------------------------------------------------------------------------------------------+
| EINSTELLUNGEN                                                                                            |
| [Bereiche & Zeiten] [Erscheinungsbild] [Datenimport] [Benutzer] [Schnittstellen]                         |
+----------------------------------------------------------------------------------------------------------+
| BEREICHE UND AUSGABEZEITEN                                                                               |
| Cafeteria / Mittag         Vorhandener Zustand und vorhandene Zeiten              [E] Bearbeiten         |
| Patienten / Mittag         Vorhandener Zustand und vorhandene Zeiten              [E] Bearbeiten         |
| Patienten / Abend          Vorhandener Zustand und vorhandene Zeiten              [E] Bearbeiten         |
+----------------------------------------------------------------------------------------------------------+
| Patienten / Abend bearbeiten                                       [v] Bearbeitung schliessen            |
| Betrieb [Offen v]     Beginn [--:--]    Ende [--:--]                                                     |
| Hinweis [                                                                                           ]    |
| [!] Leere Zeiten bleiben leere Zeiten; keine erfundenen Standardwerte.                                   |
| [Abbrechen]                                                        [S] Ausgabeangaben speichern          |
+----------------------------------------------------------------------------------------------------------+
| Weitere Einstellungen folgen als kurze Zusammenfassung statt staendig offener Formularwand.              |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Bestehende Einstellbereiche gruppiert zeigen. Ein Zustand kann „Nicht erfasst“ sein; keine scheinbar konfigurierten Werte aus dem Beispiel übernehmen. Gefährliche oder weitreichende Einstellungen mit konkreter Wirkung erklären.

**Speichern:** Pro bestehendem Einstellformular eine passende Speicherhandlung; nicht unabhängige Endpoints in eine neue globale Transaktion zusammenlegen. Ein geöffneter Bereich mit Fehler bleibt offen. Sensible Schnittstellenwerte oder Schlüssel nicht in Zusammenfassungen und Screenshots offenlegen.

##### Modul Einstellungen – Bereiche & Öffnungszeiten (2026-09-20)

Die Übersicht zeigt je Bereich eine kompakte Zeile mit Wochenendbetrieb, aufklappbaren Wochenvorgaben und «Bearbeiten» zum bestehenden Formular. Die gemeinsame Statusbar enthält echte Bereichsnamen, Zeitzone und ausschliesslich tatsächlich fehlende Zeitangaben offener Regeln; deren Anker führt zum betreffenden Wochenformular. Revisionen, IDs und ein erfundener Publikationsstatus gehören nicht hinein.

Genau eine Primäraktion im `main`: «Anlegen» zum nativen Ausnahmeformular, nach Laden einer Ausnahme dessen «Speichern». Andere unabhängige Formulare behalten neutrale Speicheraktionen und ihre eigenen CSRF-/CAS-Felder. Hinweise stehen unter «Weitere Optionen», bei Inhalt oder Fehler offen. Leere, fehlerfreie Zeitfelder geschlossener Regeln werden kontextabhängig ausgeblendet, niemals deaktiviert oder geleert. Mobile Wochenvorgaben sind einspaltige Datensätze; Desktop zeigt gemeinsame Spaltenüberschriften statt wiederholter sichtbarer Labels. Zugängliche Feldlabels, native Bedienung ohne JavaScript, sichtbarer Fokus und 48-px-Ziele bleiben erhalten. Modul-CSS liegt in `admin-settings-bereiche.css`; gemeinsame Palette und Shell bleiben unverändert.

##### Modul Einstellungen – Darstellung (2026-09-20)

Darstellung verwendet M01, M24 und M25: Titel entspricht dem Navigationspunkt,
ein Satz benennt die globale Wirkung. Die Statusbar zeigt den aktiven, aus dem
Store gelesenen Stand oder ausdrücklich eine ungespeicherte Vorschau bzw. einen
Validierungsfehler. Abstände und Menübilder stammen aus `display_values`; bei
Vorschau/Fehler beschreiben sie die eingereichte Auswahl, nicht den gespeicherten
Stand. Unbekannte Optionswerte werden weggelassen. Keine Revision oder erfundene
Speicherzeit, kein Erfolgsstatus ohne bestätigten Schreibvorgang.

Vier bestehende Selects bleiben in derselben Formularreihenfolge, mit denselben
Namen und Werten. Zwei Spalten ab Tablet, eine auf dem Smartphone; keine zusätzliche
Klickstrecke für Änderungen. Genau ein «Speichern» im Formularfuss, daneben die
neutrale «Vorschau». Seltenes Zurücksetzen liegt mit dem bestehenden Folgenhinweis
in nativen «Weitere Optionen»; bei Fehlern geöffnet. Aufklappen speichert nichts.
CSRF bleibt direkt im Formular; dieses Modul hat keine CAS-/Versionsfelder.

Die Beispielvorschau verwendet ein kleines, vollständig sichtbares Bild neben
dem Text auf Desktop und davor auf Mobile. Allergen-/Prüftext bleibt auch bei
ausgeblendeten Bildern sichtbar. Die Modul-CSS-Datei begrenzt nur das Beispielbild
und ordnet dessen Inhalt; globale Dichte-Innenabstände, Tokens und 48-px-Ziele
bleiben bestehen. Fachtexte ohne Registry-Schlüssel bleiben Bestandsbeschriftungen;
Aktionen, Aufklappbeschriftung und neue Statussymbole nutzen die semantischen Makros.
Nachweis: `tests/test_admin_display_browser.py` mit 360/768/1024/1440 px,
Tastatur, No-JS, 200-%-CSS-Zoom, POST-Feldvergleich, Vorschau, Speichern,
Zurücksetzen und Fehlerzustand. AuthZ/CSRF-Regression:
`tests/test_admin_display_settings.py` (unverändert).

##### Modul Einstellungen – Schnittstellen (2026-09-20)

Schnittstellen folgt M01/M15/M23/M25: ein Satz Kontext, genau eine Primäraktion
«Anlegen» im Kopf und Statusbar aus `status.channels`. Je Kanal werden ausschliesslich
`published` und der vorhandene Zeitraum `week_start`/`week_end` gezeigt. Erfolg
bedeutet veröffentlicht, fehlende Veröffentlichung bleibt eine textliche Warnung.
Revisionen, Schema-/API-/FHIR-Versionen und technische Endpunkte stehen gemeinsam
unter «Weitere Optionen»; sie sind keine Statusslots. Ein globaler API-Gesamtzustand
wird nicht erfunden. Die frühere offene Publikationstabelle ist ersetzt am
2026-09-20 durch diese Statusbar und nachrangige technische Angaben.

Schlüssel bleiben kompakte Tabellenzeilen, mobil priorisierte Listen ohne
Horizontal-Scroll. «Details» ist die einzige direkte Zeilenaktion; Metadaten und
Widerruf folgen darin. Widerruf verlangt einen nativen Bestätigungsschritt mit
sichtbarem Text auch ohne JavaScript; die vorhandene JS-Rückfrage bleibt erhalten.
Die Anlageaktion führt direkt zum ersten Feld im nativen Formularbereich,
auch ohne JavaScript. Fehler und eingereichte Auswahl öffnen ihn serverseitig.
Anlage bleibt ein Öffnen und ein Submit; technische Details sind kein Pflichtschritt.

Feldnamen, Reihenfolge, Standardwerte, POST-Ziele und CSRF bleiben unverändert.
Keine CAS-Felder hinzuerfinden. Der Klartextschlüssel und sein Einmalhinweis bleiben
unverändert und werden nie in Screenshots aufgenommen. Neue Aktionslabels und
Symbole nutzen die semantischen Makros, bestehende Fachtexte bleiben erhalten.
Eigene Styles liegen ausschliesslich in `admin-settings-schnittstellen.css`;
ein begrenztes `!important` überschreibt Tablers gleichrangige mobile Zellregel.
Nachweis: `test_admin_api_page.py` mit eigenem Playwright-Start, vier Pflichtbreiten,
48-px-Zielen, Tastaturfokus, nativen POSTs, Formularwertvergleich und No-JS.
Schreibgeschützte Policy-Browsertests mit alten Struktur-/Aktionsnamen benötigen
Anpassung durch ihren Besitzer; ihre fachlichen Assertions bleiben Pflicht.

#### M16 — Erscheinungsbild: gespeicherten Entwurf eindeutig kennzeichnen

Einstellungen links, dazugehörige Vorschau rechts. Keine nur behauptete Live-Aktualisierung.

```text
+-------------------------------------------------------------------+   +----------------------------------+
| ERSCHEINUNGSBILD / Entwurf bearbeiten                             |   | VORSCHAU                         |
+-------------------------------------------------------------------+   | Gespeicherter Entwurf            |
| Name [Suedhang Standard - Entwurf                              ]  |   +----------------------------------+
| Logo [Vorhandenes Logo v]      [Datei auswaehlen]                 |   | Original-Logo                    |
| Primaerfarbe [Farbwert]       Hintergrund [Farbwert]              |   | Menue mit realistischem Namen    |
| Schrift [Vorhandene Auswahl v]                                    |   | Vorhandene Beispielinhalte       |
+-------------------------------------------------------------------+   |                                  |
| [S] Entwurf speichern und Vorschau anzeigen                       |   | Noch nicht aktiviert.            |
|                                                                   |   | [Entwurf aktivieren]             |
| [>] Fruehere Versionen                                            |   | Nur vorhandene Aktivierung.      |
| [>] Technische Farbwerte und weitere Angaben                      |   +----------------------------------+
+-------------------------------------------------------------------+
```

**Pflicht:** „Vorschau“ benennt den tatsächlich dargestellten Stand. Ein sichtbarer Hinweis bei ungespeicherten Änderungen erklärt, dass die gespeicherte Vorschau diese noch nicht enthält. Die aktive Version darf nicht als ungespeicherter Entwurf erscheinen.

**Nicht neu erfinden:** Kein zusätzlicher Designer, Farbservice oder Schriftabruf. Bestehende Upload-, Entwurfs-, Aktivierungs- und Versionsregeln erhalten. Aktives Marken-CSS und Admin-CSS dürfen sich nicht durch ungeprüfte Vererbung gegenseitig verändern.

#### M17 — Datenimport: Aufgabe und Fehler, nicht technische Rohdaten

Strukturmuster für den bestehenden Importablauf. Vorschau und Import nur in der tatsächlich vorhandenen Reihenfolge.

```text
+----------------------------------------------------------------------------------------------------------+
| EINSTELLUNGEN / Daten importieren                                                                        |
| Bereich [Vorhandene Bereichsauswahl v]      Datei [Datei auswaehlen]  beispiel.csv                       |
| [O] Datei pruefen / vorhandene Vorschau oeffnen                                                          |
+----------------------------------------------------------------------------------------------------------+
| PRUEFERGEBNIS DER AUSGEWAEHLTEN DATEI                                                                    |
| [!] Zeile 4: Eine vorhandene Pflichtangabe fehlt.                                                        |
| [>] Betroffene Zeile und konkrete Korrektur anzeigen                                                     |
| Weitere echte Befunde kompakt als Liste; keine erfundene Fortschrittsanzeige.                            |
+----------------------------------------------------------------------------------------------------------+
| [>] Dateiformat und Erklaerungen                                                                         |
| [>] Technische Details                                                                                   |
| Importaktion nur entsprechend den bestehenden Serverregeln anbieten.                                     |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Genau eine klare Dateiauswahl und eindeutiger Bezug zwischen Ergebnis und geprüfter Datei. Keine alten Prüfungsergebnisse nach Dateiaustausch als aktuell darstellen. Bestehende Importhindernisse verständlich erklären.

**Schutz:** Keine neue automatische Importfunktion, kein Wegklicken fachlicher Fehler und kein neuer Fortschrittsdienst. Rohdaten, Tokens oder interne Fehlerdetails nicht in normale Meldungen kopieren. Produktionsimporte sind keine zulässigen UI-Tests.

##### Modul Einstellungen – Daten importieren (2026-09-20)

Datenimport folgt M01/M17/M25. Seitentitel `Daten importieren` (Navigationspunkt), ein Satz Kontext, Statusbar aus vorhandenen Prüfergebnissen. Leer: `Prüfung` = `Offen` mit Ziel `#csv-upload`. Nach Vorschau: Bereich aus `result.profile` als Cafeteria/Patientenplan, Woche aus `result.week_start` (`KW n · ab TT.MM.JJJJ`), Prüfung `Bereit` (success) oder `Fehlerhaft` (danger, Ziel `#file-error`), `Zeilen` aus `result.rows`, `Warnungen` nur bei `result.warnings` (Ziel `#csv-warnings`). Keine Importrevision, keine internen Profilcodes (`staff_guest`/`patient`) als sichtbarer Text.

Genau eine `.btn-primary` im `main`: «Vorschau prüfen» ohne gültiges Ergebnis, «Geprüfte Datei importieren» danach im Seitenkopf über `form="csv-import"`. Eine zweite Datei prüfen bleibt sekundär. Dateiformat und Spaltenköpfe stehen in `disclosure_section` «Weitere Optionen», offen bei Inhalt oder Fehler. Die Bereichswahl im M17-ASCII ist Komposition; das Profil kommt aus der CSV, kein neues Auswahlfeld. Rezeptimport bleibt unter Rezepte. Feldnamen `_csrf`, `file`, `import_token` und POST-Ziele `/import-preview` sowie `/import` bleiben byte-gleich. Modul-CSS nur in `admin-settings-import.css`. Nachweis: `tests/test_admin_csv_preview_ui.py` (eigener Playwright-Start, 360/768/1024/1440, No-JS, Tastatur, Statusbar, Überlauf), `tests/test_admin_csv_import.py`, `tests/test_csv_validation_followup.py`.

#### M18 — Benutzer und ähnliche Verwaltungslisten

Kompakte Verwaltung mit klarer Objektaktion; ausschliesslich vorhandene und erlaubte Daten zeigen.

```text
+----------------------------------------------------------------------------------------------------------+
| EINSTELLUNGEN / Benutzer und Zugriff                                        [+] Benutzer anlegen         |
| Suche [                                                        ]  [?] Suchen                             |
| Weitere vorhandene Filter bei Bedarf. Keine Anzeige vertraulicher Zugangsdaten.                          |
+----------------------------------------------------------------------------------------------------------+
| Name                    Konto                   Status             Aktion                                |
| Kueche Beispiel         kueche.beispiel          Aktiv              [E] Benutzer oeffnen                 |
| Testkonto               test.beispiel           Deaktiviert        [E] Benutzer oeffnen                  |
+----------------------------------------------------------------------------------------------------------+
| Auf der Detailseite: Rollen, Status und berechtigte Aktionen zusammenhaengend anzeigen.                  |
| Passwort- und Rechteaktionen nicht als namenlose Icons in jede Tabellenzeile quetschen.                  |
| Leere Liste: kurzer Hinweis und nur erlaubte Anlageaktion. Keine leere Grosskarte.                       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Dieselben Listen- und Filtermuster wie in anderen Modulen. Zugriffsstatus nicht allein durch Farbe; Aktionen dem konkreten Konto zuordnen. Rollenabhängige Sichtbarkeit ist nur Darstellung, kein Ersatz für serverseitige Autorisierung.

**Kritische Vorgänge:** Passwort, Deaktivierung und Rechteänderung behalten ihre vorhandenen separaten Schutz- und Bestätigungswege. Keine neue Rollenlogik, keine Teständerungen an echten Konten. Tabellenzeilen dürfen bei langen Namen wachsen.

#### M19 — Fehler in einem zuvor geschlossenen Detailbereich

Beispiel eines tatsächlichen Validierungsfehlers, nicht eine neue fachliche Mengenregel.

```text
+----------------------------------------------------------------------------------------------------------+
| REZEPT BEARBEITEN / Apfelmus                                                                             |
| [!] Speichern nicht erfolgreich. Bitte korrigiere den markierten Eintrag.                                |
| [Zum Fehler: Zutatenbezeichnung bei Zeile 2]                                                             |
+----------------------------------------------------------------------------------------------------------+
| Aepfel       [1800] [Gramm v]                                      [>] Details  [...] Aktionen           |
| ZEILE 2      [100 ] [Milliliter v]                    [!] Fehler    [v] Details schliessen               |
+----------------------------------------------------------------------------------------------------------+
|   Bezeichnung im Rezept [                                                                         ]      |
|   [!] Bitte die Bezeichnung ergaenzen. Diese Meldung stammt aus der bestehenden Validierung.             |
|   Zutat aus Liste [Wasser                                                                         v]     |
|   Andere Eingaben bleiben erhalten.                                                                      |
+----------------------------------------------------------------------------------------------------------+
| Zucker       [60  ] [Gramm v]                                      [>] Details  [...] Aktionen           |
+----------------------------------------------------------------------------------------------------------+
| Nicht gespeichert                                                [Abbrechen]  [S] Rezept speichern       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Fehlerzusammenfassung und lokaler Fehler führen zum sichtbaren Feld. Der zuständige Abschnitt öffnet sich automatisch; sein Fehler bleibt auch beim erneuten Schliessen erkennbar. Keine verlorenen Mengen, Reihenfolgen oder Referenzen.

**Native Validierung:** Auch ein erforderliches Feld in geschlossenen Details muss erreichbar werden. Nicht `required` entfernen, pauschal `novalidate` setzen oder Validierung aufblähen. Vorhandene Sonderbehandlung von Strukturaktionen bleibt davon getrennt.

**Unklare Netzwerkantwort:** Diese ist ein anderer Zustand als eine bestätigte Validierungsablehnung. Dann „Abschluss konnte nicht bestätigt werden“ anzeigen; weder behaupten, nichts sei gespeichert worden, noch die Schreibaktion blind wiederholen.

#### M20 — Leere Daten, keine Treffer und Ladefehler unterscheiden

Drei alternative Zustände desselben Listenmusters; nicht gleichzeitig auf der Seite darstellen.

```text
+----------------------------------------------------------------------------------------------------------+
| A / NOCH KEINE DATEN                                                                                     |
| Noch keine Bausteine angelegt.                                  [+] Baustein hinzufuegen                 |
| Keine Pagination. Kurzer Leerzustand statt einer bildschirmhohen Karte.                                  |
+----------------------------------------------------------------------------------------------------------+
| B / FILTER OHNE TREFFER                                                                                  |
| Keine Bausteine passen zu diesen Filtern.                       [Filter zuruecksetzen]                   |
| Aktiv: Kategorie Gemuese | enthaelt Milch. Auswahl bleibt sichtbar.                                      |
+----------------------------------------------------------------------------------------------------------+
| C / LADEN FEHLGESCHLAGEN                                                                                 |
| [!] Bausteine konnten nicht geladen werden.                    [Erneut laden]                            |
| Nicht als leere Datenbank oder null Treffer ausgeben.                                                    |
+----------------------------------------------------------------------------------------------------------+
| Fehlende Berechtigung ist ein weiterer eigener Zustand, kein leerer Bestand.                             |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Jeweils nur passende, tatsächlich vorhandene und berechtigte Folgeaktionen. Fehler dürfen nicht nach wenigen Sekunden verschwinden. Keine erfundene Nullzählung, wenn die Abfrage fehlgeschlagen ist.

**Übertragung:** Dieses Muster gilt für Menüs, Rezepte, Kochbücher, Vorlagen, Medien und Benutzerlisten genauso. Die fachliche Benennung und erlaubte Anlagehandlung anpassen; keine Funktionsattrappen hinzufügen.

#### M21 — Auswahl mit Detail nach Auswahl

Generisches Muster für wiederholte Optionen mit optionalem Detail; Beispiel Allergene. Desktop mit 2–4 Spalten, mobil eine Spalte.

```text
+----------------------------------------------------------------------------------------------------------+
| ALLERGENE                                                                                                |
| Eingabe: ( ) Manuell  ( ) Automatisch                                                                    |
+----------------------------------------------------------------------------------------------------------+
| [v] Gluten          [ ] Krebstiere        [v] Eier            [ ] Fisch                                  |
| [ ] Erdnuesse       [v] Milch             [ ] Schalenfruechte  [ ] Sellerie                              |
| [ ] Senf            [ ] Sesam             [ ] Sulfite          [ ] Lupinen                                |
| [ ] Soja            [ ] Weichtiere                                                                       |
| 3 von 14 ausgewaehlt                                                                                     |
+----------------------------------------------------------------------------------------------------------+
| Details (optional)  [v]  Nur fuer ausgewaehlte Allergene                                                 |
|   Gluten    Praesenz [Enthaelt      v]                                                                   |
|   Eier      Praesenz [Enthaelt      v]                                                                   |
|   Milch     Praesenz [Enthaelt      v]                                                                   |
| [!] Nicht ausgewaehlt bedeutet nicht: allergenfrei bestaetigt.                                           |
+----------------------------------------------------------------------------------------------------------+
|                                                      [Abbrechen]  [S] Speichern                          |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Auswahl als echte Formularelemente (Checkbox, Select o.ä.) mit Icon und Text. Ausgewählt = Rahmen + Haken + Text, nie nur Farbe. Detailfeld erscheint nur für ausgewählte Optionen; Zähler «n ausgewählt». Ohne JavaScript dürfen Detailfelder sichtbar bleiben; Bedienung muss möglich sein. Keine lange zweispaltige Wiederholungsliste mit dauerhaft sichtbarem Detail je Zeile.

**Sicherheitsregel:** Feldnamen, gesendete Werte, Standardwerte und Prüfstatus bleiben unverändert; «nicht ausgewählt» oder «ungeprüft» wird nie als «allergenfrei» gespeichert oder dargestellt; eine Sammelaktion wie «alle als nicht enthalten setzen» nur, wenn der Wert im Datenmodell heute existiert, und sie verändert den Prüfstatus nicht.

**Responsive:** 2–4 Spalten ab Tablet/Desktop; eine Spalte auf schmalen Displays. Chips umbrechen statt horizontal scrollen.

**Technischer Vertrag (2026-09-20, ersetzt am 2026-09-21 durch den schlüsselbasierten Präsenzvertrag):** `option_detail_group` behält Optionen, Layout, Checkboxen `allergen_code`, Werte `contains|may_contain` und den Hinweis «Nicht ausgewählt bedeutet nicht: allergenfrei bestätigt.». Im Standardmodus trägt jedes Select den Namen `allergen_presence__<CODE>`. Auswahl und Präsenz werden ausschliesslich über den Code zugeordnet, unabhängig von DOM- oder POST-Reihenfolge. Selects bleiben bei Abwahl aktiviert; JavaScript blendet Details nur aus und aktualisiert Zähler. Ohne JavaScript sind alle Details sichtbar und bedienbar. Im automatischen Modus sind Checkbox und Select deaktiviert; der Parser lehnt trotzdem gesendete Allergenfelder ab. Nicht gewählte Präsenzwerte werden ignoriert. Gewählte Codes benötigen einen gültigen Präsenzwert; doppelte Codes sowie gemischtes Alt-/Neuformat werden abgelehnt. Ausschliesslich alte `allergen_presence`-Wiederholfelder bleiben übergangsweise indexgepaart lesbar. Re-Render erhält Werte je Code und verknüpft `field-error`, `is-invalid`, `aria-invalid` und `aria-describedby` mit dem betroffenen Select. Der Grundlagenmodus `field_prefix='allergen_'` mit `absent|contains|may_contain` bleibt unverändert. Gespeicherte Daten, Prüfstatus und Veröffentlichungsprüfung ändern sich nicht.

#### M22 — Eine Filterzeile

Gemeinsame Filterleiste für alle Listenmodule; dieselbe Reihenfolge überall.

```text
+----------------------------------------------------------------------------------------------------------+
| MENUES                                                                               [+] Menue anlegen     |
+----------------------------------------------------------------------------------------------------------+
| Suche [                                    ]  Kategorie [Alle v]  Status [Alle v]  [Weitere Filter v]  |
|                                                                                    [Filter zuruecksetzen] |
+----------------------------------------------------------------------------------------------------------+
| 8 von 8 Menues                                                                                           |
| Name / Unterzeile              Kategorie    Status        Kennzeichnungen              Aktion            |
| Apfelmus / Mittag 12.09.       Dessert      Aktiv         [GF] [V]                     [E] Bearbeiten   |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Suche zuerst. Höchstens 2–3 häufige Filter sichtbar; weitere unter «Weitere Filter». «Filter zurücksetzen» nur bei aktivem Filter. Gleiche Reihenfolge in Menüs, Bausteinen, Zutaten, Rezepten und allen übrigen Modulen.

**Responsive:** Filterzeile umbrechen; Suche bleibt erkennbar an erster Position. Keine zweite parallele Filterleiste.

**Technischer Vertrag (2026-09-20):** `filter_bar(action, search_name='q', search_value='', filters=none, more_filters=none, active=false, reset_url=none, id='filters')` rendert `form.admin-filter-bar[method=get][role=search][data-dirty-tracking=off]`. Das beschriftete Suchfeld steht zuerst; `filters` und `more_filters` sind in Jinja erfasste Markup-Slots mit unveränderten Parameternamen. Aufrufer übergeben höchstens drei häufige Filter in `.admin-filter-slots`; zusätzliche stehen in `details.admin-filter-more` mit Summary «Weitere Filter». Der Reset-Link erscheint nur bei `active` und übergebener URL. Native GET-Übermittlung und Details funktionieren ohne JS; keine neuen JS-Hooks. Nachweis: `test_admin_shared_patterns_browser.py` prüft GET-Parameter, bedingten Reset, Semantik, Fokus, 48-px-Ziele und Reflow bei 360/768/1024/1440 px.

#### M23 — Eine Zeile pro Datensatz

Kompakte Listenzeile mit klarer Hierarchie und einer sichtbaren Zeilenaktion.

```text
+----------------------------------------------------------------------------------------------------------+
| Kartoffelstock / Beilage, in 2 Menues verwendet    [Aktiv]  [GF] [V] [+2]           [E] Bearbeiten [...] |
| Apfelmus / Mittag 12.09., Cafeteria                [Entwurf] [GF] [V]               [E] Bearbeiten [...] |
+----------------------------------------------------------------------------------------------------------+
| [...] Weitere Aktionen  ->  Duplizieren (nur wenn vorhanden) | Archivieren | ...                       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Name plus einzeilige Unterzeile. Status als Badge. Kennzeichnungs-Icons mit Text oder `aria-label`. Genau eine sichtbare Zeilenaktion («Bearbeiten» oder «Ansehen») plus beschriftetes «Weitere Aktionen»-Menü für seltene Aktionen. Überlauf bei Kennzeichnungen als «+n», nicht als Badge-Wolke.

**Responsive:** Zeile darf bei Bedarf wachsen; Aktionen bleiben erreichbar. Keine drei gleichwertigen Icon-Buttons ohne Beschriftung.

**Technischer Vertrag (2026-09-20):** `list_row(name, subtitle, state, action, markings=none, overflow=0, more_actions=none)` rendert `.admin-list-row` mit `.admin-list-name`, einzeiliger `.admin-list-subtitle` (vollständiger Text im DOM und `title`), bestehendem `status_badge(state)` und `.admin-list-markings`. Der Aufrufer begrenzt den Kennzeichnungs-Slot; `overflow` ergänzt ein beschriftetes «+n». `action` verwendet das bestehende `actions`-Mapping (Link oder Button samt Formularattributen); genau diese Aktion steht offen in `.admin-list-actions`. Ein übergebener `more_actions`-Slot erscheint in `details.admin-compact-actions` mit «Weitere Aktionen». Keine neuen `data-`-Hooks, native Links/Buttons/Details bleiben ohne JS bedienbar. Nachweis: `test_admin_shared_patterns_browser.py` für eine sichtbare Aktion, Status, Überlauf, Tastatur, 48-px-Ziele und vier Breiten.

##### Modul Bestellung (2026-09-20)

Die Bestellübersicht folgt M01/M20/M23/M25: Seitentitel `Bestellung` (Navigationspunkt), ein Satz Kontext ohne Sendauftrag, genau eine Primäraktion «Anlegen» im Seitenkopf. Statusbar aus vorhandenen Listenwerten `baskets`, `suppliers` und `articles` (Zähler, `0` ist ein Wert, `warning` wenn leer). Körbe sind der primäre Arbeitsbereich mit kompakter Zeile und «Öffnen»; Lieferanten und Artikel stehen nachrangig. Dauerhaft offene Anlageformulare sind native `details` «Anlegen», geöffnet nur wenn der jeweilige Bestand fehlt. Empty States nennen den nächsten Schritt. Kein Slot «gesendet», keine `row_version` in der Statusbar.

Das Korbdetail nutzt dieselbe Statusbar mit übersetztem Statusbadge, Lieferantennamen und Zeilenzahl. Die vorhandenen Schema-Zustände werden in Übersicht und Korb gleich abgebildet: `draft` → Entwurf/neutral, `abandoned` → Verworfen/neutral, `send_pending` → Versand ausstehend/Warnung, `sent` → Gesendet/erfolgreich, `send_unknown` → Versandstatus unklar/Warnung. Ein Exportzustand existiert nicht; CSV verändert keinen Zustand. Die übrigen gemeinsamen Statusstile erhalten keine erfundenen Fachzustände. «Speichern» ist die einzige Primäraktion; CSV ist «Herunterladen». Nettobedarf (Zutat-UUID/`food_public_id`, Rohmenge) und CSV-Vorschau liegen unter «Weitere Optionen» bzw. «Vorschau». Tabellenzeilen werden unter 768 px als Liste gestapelt (`table-mobile-lg` plus Modul-CSS). `_csrf`, `row_version` und die Wiederholfelder `article_public_id`/`quantity`/`raw_quantity` bleiben im Speicherformular.

Nachbesserung 2026-09-23: «Anlegen» öffnet per GET-Parameter `open=korb|lieferant|artikel` unmittelbar das passende native Details-Formular, auch bei vorhandenen Körben; Anker und bedingtes `autofocus` führen zum ersten Feld. POST-Ziele, Werte und Defaults bleiben unverändert. Empty States, neue Statusbar-Texte und Statuslabels verwenden die Registry und DE/EN-Projektschlüssel `ui.order_*`; die 184 Seeds bleiben erhalten. Nachweis: `test_order_admin.py` für 360/390/768/1024/1440 px mit und ohne JS, alle Korbzeilen bei 1440 px ≤ 96 px, zentrale Ziele ≥ 48 × 48 px, echten Anlage-/Speicher-POST ohne JS, Mehrpositions-Roundtrip mit unterschiedlichen Rohmengen und DE/EN-Statusdarstellung. `test_ui_semantics.py` prüft Registry und Startvalidierung. Screenshot- und Messbelege liegen beim Testlauf; kein Produktionsnachweis.

**Polish P3 (Korb):** Zeilentabelle `admin-table--stack`; CSV-Hinweis in `hint()`.
«Kein Journal / kein Sendauftrag» bleibt im Aufklappbereich. Speicherformular
opt-in `data-loading`.

#### M24 — Formularfuss

Einheitliche Aktionsleiste am Ende jedes Formulars und Editors.

```text
+----------------------------------------------------------------------------------------------------------+
| ... Formularinhalt ...                                                                                   |
+----------------------------------------------------------------------------------------------------------+
| [Loeschen]                                              [Abbrechen]  [S] Speichern                       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Links destruktive oder seltene Aktion (nur wo vorhanden: Archivieren, Löschen). Rechts «Abbrechen» und genau eine Primäraktion «Speichern». Bei langen Editoren kompakte Sticky-Leiste gemäss R08; sie verdeckt weder Feld noch Fehler noch Fokus.

**Responsive:** Sticky-Leiste darf bei mobiler Tastatur in den Dokumentfluss wechseln. Primäraktion bleibt beschriftet.

**Technischer Vertrag (2026-09-20):** `form_footer(primary, cancel_url, rare=none, sticky=false, form_id=none)` rendert `.admin-form-footer`, links den optionalen Jinja-Slot `.admin-form-rare`, rechts `.admin-form-main` mit «Abbrechen» vor genau einer über `actions(primary=...)` gerenderten Speicheraktion. `primary` übernimmt dessen vorhandenen Mapping-Vertrag einschliesslich `name`, `value`, `formaction` und weiterer Formularattribute; Slots dürfen keine zusätzliche Primäraktion enthalten. `sticky` setzt `data-sticky`, optional `data-sticky-form`. Der vorhandene Viewport-Guard setzt `data-sticky-ready`/`.is-static`; erst nach Initialisierung und ab 700 px Höhe wird der Fuss sticky. Kleine Visual Viewports, mobile Tastatur, überhohe Leisten sowie fokussierte Eingabefelder oder Fehler im Formular lassen ihn im Dokumentfluss. Ohne JS bleibt er statisch. Nachweis: `test_admin_shared_patterns_browser.py` prüft genau eine `.btn-primary`, Submit, Fokus und geringe Höhe mit/ohne JS; bestehende Komponenten-Gates sichern `actions` ab.

#### M25 — Weitere Optionen

Seltene oder technische Angaben in nativem `<details>`; Kurztext zeigt vorhandenen Inhalt.

```text
+----------------------------------------------------------------------------------------------------------+
| Name [Kartoffelstock                     ]  Kategorie [Beilage v]                                        |
| [>] Weitere Optionen  —  Quelle erfasst, 1 technische Angabe                                           |
+----------------------------------------------------------------------------------------------------------+
| [v] Weitere Optionen  —  Quelle erfasst, 1 technische Angabe                                           |
|   Quelle [Manuell v]                                                                                     |
|   Interne Notiz [Optional                                                                        ]       |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Natives `<details>`/`<summary>` verwenden. Öffnet sich automatisch bei Fehler oder gefülltem Inhalt (siehe R06). Kurztext im Summary zeigt, dass Inhalte vorhanden sind. Auf-/Zuklappen speichert und verwirft nichts.

**Responsive:** Summary bleibt vollständig lesbar; Inhalt folgt dem gemeinsamen Formular-Grid.

**Technischer Vertrag (2026-09-20):** `{% call disclosure_section(title='Weitere Optionen', id=none, open=false, has_content=false, has_error=false) %}…{% endcall %}` rendert `details.admin-compact-details.admin-disclosure` und `.admin-compact-detail-body`. `open`, `has_content` oder `has_error` öffnen serverseitig; `has_content` ergänzt «enthält Angaben» im Summary. Keine neuen `data-`-Attribute oder JavaScript-Abhängigkeit; native Tastaturbedienung erhält Formularwerte. Nachweis: `test_admin_shared_patterns_browser.py` für explizites Öffnen, Fehler/Inhalt, leeren geschlossenen Zustand, Fokus und responsive Zielgrössen mit und ohne JS.

##### Modul Kochbücher (2026-09-20)

Die Kochbuchliste verwendet M22/M23: eine Filterzeile (Suche, Archiv), kompakte
Vollbreitenzeilen statt eines Kartenrasters, genau eine Primäraktion «Anlegen»
im Seitenkopf und einen Empty State mit derselben Anlagehandlung. Die frühere
dauerhaft sichtbare Anlage unter der Liste (`details#cookbook-create`) ist
ersetzt am 2026-09-20 durch diese Primäraktion plus fokussierten Editor.

Die Statusbar zeigt auf der Liste den Filterzustand (`include_archived` bzw.
aktive Suche) und im Editor Objektstatus (`book.active`) sowie die Anzahl
zugeordneter Rezepte (`book.recipe_public_ids`). `row_version`, IDs und
Publikationswerte sind keine Statusslots; `row_version` bleibt verstecktes
CAS-Feld im Formular. Archivieren liegt im Formularfuss bzw. im Bestätigungsdialog;
Speichern der Zuordnung bleibt sekundär. CSRF, CAS und gesendete Feldnamen bleiben
unverändert. Nachweis: `test_ui_korrektur_cookbooks_browser.py`,
`test_cookbook_routes.py`.

##### Modul Gerichtvorlagen (2026-09-20)

Das Modul Gerichtvorlagen nutzt M22 (Filterzeile), M23 (Zeilenvertrag) und M24 (Formularfuss) anstelle eigener Custom-Controls. Die Haupttabelle trennt Rezept, Status und Planung auf dem Desktop, wird auf schmalen Viewports aber zu einer kompakten Zeile je Vorlage verdichtet. Der Anlage- und Editorbereich folgt dem gemeinsamen Formular-Grid, mit exakt einer Primäraktion im Formularfuss. Statuswerte (Aktiv, Bereich, Rezeptbindung) sind in die zentrale Statusbar verlegt, die Planungsziel-Vorschau verbleibt fokussiert im Einplanen-Kontext. Dauerhaft geöffnete Anlage- oder Suchformulare am Listenende sind durch die Primäraktion im Seitenkopf abgelöst.

Nachbesserung 2026-09-23: H1 und Dokumenttitel bleiben auf Liste, Anlage, Editor und Einplanen «Gerichtvorlagen»; die konkrete Aufgabe steht in der Beschreibung. Liste und Leerzustand besitzen nur die Kopfaktion «Vorlage anlegen», Editoren nur «Speichern» als Primäraktion. Die Rezeptsuche bleibt im Anlageformular (`recipe_search`, nativer Such-Submit mit Werterhalt). Der Archivfilter nutzt einen Jinja-Block und den nativen «Filtern»-Submit ohne Change-Autosubmit. Mobile und Desktop-Planungsaktionen heissen gleich «Als Menü einplanen». Die Zusammenfassung `#planning-summary` bleibt sichtbar und wird ohne JavaScript über «Ziel aktualisieren» erneuert. Textlinks erhalten dieselben 48-px-Bedienziele wie die gemeinsamen Controls; Rezept-Metadaten stehen kompakt zusammen.

Messnachweis: `test_dish_template_browser.py::test_rework_layout_measurements` prüft 360/390/1440 px, genau eine Primäraktion, sämtliche sichtbaren Aktionsziele mindestens 48 × 48 px, Desktop-Zeilen maximal 96 px, Überlauf und echte Statuswerte für aktive/archivierte Vorlagen mit/ohne Rezeptbindung. Bestehende Tests für Konflikte, Rezeptsuche mit Werterhalt, Leserechte, 320-px-Reflow und echten 200-%-Browserzoom bleiben erhalten. Vorher-/Nachherwerte und Gate-Ergebnis stehen im WP09-Nachbesserungsreport.

##### Modul Einkaufslisten (2026-09-20)

**Seitenrahmen:** Liste und Detail tragen den Seitentitel «Einkaufslisten», entsprechend dem Navigationspunkt. Im Detail stehen Listenname, Woche und vorhandener Berechnungsstand in der Kontextzeile; «Drucken» bleibt sekundär. Höchstens eine `.btn-primary` im `main`: auf der Liste «Anlegen» als direkter Fokuslink zum sichtbaren Titelfeld (`draft.write`), im Detail «Neu berechnen», sobald berechtigte Nutzer Bausteine wählen können. Ohne Schreibrecht oder im historischen Stand wird keine Primäraktion erzwungen. Zeilenaktionen bleiben neutral, ausgenommen «Löschen»: Gefahrenstil, räumlicher Abstand und ein gemeinsamer Folgetext über `aria-describedby`. Aktive Archivfilter tragen `active` und `aria-current="true"`.

**Statusbar aus vorhandenen Template-Werten:** Liste: `Positionen` aus Summe `item.open_count` / `item.checked_count` (warning bei offenen, success nur wenn abgehakte existieren und keine offenen); optional `Archiviert` aus gezählten `item.archived_at`, nur wenn `include_archived`. Detail: `Woche` aus `week_labels[detail.menu_week_public_id]` (warning ohne Woche); `Liste` Aktiv/Archiviert aus `detail.archived_at`; `Berechnung` aus `selected.computed_at` bzw. «Noch nicht berechnet», Detailtext die Bedarfspolitik; `Positionen` aus Zeilen-`checked_status` plus `detail.manual_items`; `Unvollständig` nur bei `selected.incomplete_lines`. Kein `row_version`, keine interne ID, kein Bestellstatus (keine Quelle).

**Liste:** Eine Filterzeile «Aktive» / «Archivierte einschliessen» (`archived=1`). Kompakte `list_row` mit Unterzeile Woche · Berechnung · offen/abgehakt, Statusbadge, Zeilenaktion «Öffnen», Drucken und Archivieren unter «Weitere Aktionen». Anlageformular dauerhaft offen: Kopf- und Empty-State-Aktion fokussieren direkt das Titelfeld, auch ohne JavaScript. Kein zusätzlicher Öffnungsschritt. Notiz und Woche bleiben in `disclosure_section` «Weitere Optionen». Feldnamen `_csrf`, `title`, `note`, `menu_week_public_id` unverändert.

**Detail:** Meta-Karten entfallen. Berechnungsstand als GET-Filter `revision` plus «Öffnen». Notiz in «Weitere Optionen». Neu berechnen kompakt, Bausteine ab 1024 px zweispaltig, ab 1440 px dreispaltig; POST `_csrf`, `row_version`, `menu_week_public_id`, `component_ids`, `policy` unverändert. Ergebnis- und manuelle Zeilen kompakt; Abhaken/Wieder öffnen ohne Primärfarbe. «Geändert, erneut offen» und «nicht aktuell» als Warning-/Neutral-Badge mit Text. Manuelle Neuanlage heisst «Anlegen»; der leere Positionsbereich verlinkt direkt zum ersten Feld. Manuelle POST-Felder `item_text`, `quantity`, `unit_code`, `expected_row_version`, `action` und IDs `new-item-*` / `item-*-{id}` unverändert. Moduleigene Styles nur in `admin-einkaufslisten.css`.

**Nachweis:** `tests/test_shopping_list_browser.py` nutzt die vorhandene Session-Fixture `browser` ohne eigenen Playwright-Thread. 360/768/1024/1440, No-JS, direkte Anlageaktionen samt Fokus, zugänglicher Submit-Name, Tastatur, Statusbar, zustandsabhängige Primäraktion und kein Dokument-Overflow. Bei 1440 px Listenzeilen ≤72 px sowie Ergebnis- und manuelle Zeilen mit langen Inhalten ≤96 px; mobile Höhen werden separat gemessen. Fachliche Verträge in `tests/test_shopping_list_routes.py`, `tests/test_shopping_list_db.py`, `tests/test_shopping_list_pdf_http.py`.

**Polish P3:** Ergebnis- und manuelle Tabellen nutzen `admin-table--stack` mit `data-label`; die frühere `d-none d-md-*`-Doppelung entfällt. Zeilenstatus ist `admin-status--*`. Hilfetext zur Bedarfspolitik und zum Berechnungsstand liegt in `hint()`; der Lösch-Folgetext bleibt inline. POST-Formulare opt-in `data-loading`.

##### Modul Lager (2026-09-20)

Die Lagerseite folgt M01/M23/M25: Titel «Lager», ein Satz Kontext, Statusbar
über `page_header(..., status_items=lager_status)`, kompakte Zuordnungstabelle
und Buchungsformulare erst nach «Öffnen» einer Zeile. Die frühere Satzzeile zum
Saldo und die drei gleichgewichtigen Buchungskarten sind ersetzt am 2026-09-20
durch Statusbar plus eine Primärhandlung «Speichern» (Zugang/Abgang);
Umbuchung und Zählung stehen in `disclosure_section` «Weitere Optionen».

Statusslots aus vorhandenem Template-Kontext: gewählte Zutat
(`selected.food_name`), Lagerort (`selected.storage_name`), Bestand
(`balance_label` bzw. «Kein Bestand erfasst» aus `captured`) und bei Bedarf
die Anzahl offener Zuordnungen (`slots` ohne `captured`). Letzte bestätigte
Zählung, IDs und `row_version` werden nicht angezeigt; es gibt keine Quelle
für eine Zählung im Route-Kontext. `success` bleibt ungenutzt, solange kein
bestätigter Zielzustand geliefert wird. «Kein Bestand erfasst» ist der
sichtbare Zustand, nie ein stilles 0.

Genau eine `.btn-primary` im jeweiligen Kontext: Empty State verweist auf
Zutaten (`admin.master_data_list`); nach Auswahl ist «Speichern» die
Buchung. Zeilenaktion «Öffnen» ist neutral, die aktive Zeile trägt `active`
und `aria-current="true"`. Mobil werden Tabellenzeilen zur Liste. Formulare
nutzen 3 Spalten ab 1024 px. Feldnamen, POST-Ziele, CSRF-Felder und
Standardwerte bleiben byte-gleich. Eigene Styles nur in `admin-lager.css`.
Nachweis: `test_inventory_ui.py` (eigener Playwright-Start, 360/768/1024/1440,
No-JS, Tastatur, Formularfeldvergleich).

**Polish P3:** Zuordnungstabelle `admin-table--stack` mit `data-label`;
Bestand ohne Erfassung als `admin-status--warning`. Zuordnungshinweis in
`hint()`, der Saldo-0-Hinweis bleibt sichtbar. Buchungsformulare nutzen
`admin-option-grid` und `data-loading`.

##### Modul Kalkulation (2026-09-20)

Kalkulation nutzt M01/M23/M25: Seitenkopf mit genau einer Primäraktion
«Vorschau» ohne Ergebnis, danach «Bestätigen» für den unveränderlichen Beleg.
Die Eingaben Art → Rezeptrevision → Stichtag stehen auf Desktop in drei Spalten,
mobil untereinander. Die zusätzliche Menürevision liegt in «Weitere Optionen»;
bei Menüauswahl wird der Bereich angeboten, bei vorhandener Zusatzangabe geöffnet.
Feldnamen, Werte und native POST-Formulare bleiben unverändert, auch ohne JavaScript.

Die Statusbar verwendet nur den tatsächlichen Vorschauzustand, den berechneten
Stichtag, unvollständige Positionen und bei vollständiger Berechnung die Summe.
Fehlende Preise oder Umrechnungen bleiben ausdrücklich unvollständig, niemals null
CHF. Ergebniszeilen sind mobil Listen; technische Zutaten-IDs stehen nachrangig
in «Weitere Optionen». Da der vorhandene Kontext keine Namen oder Objektauswahl
liefert, bleibt die erforderliche Revisions-ID eine Eingabe. Ein benannter
Objektwähler benötigt ein eigenes Backend-Paket. Nachweise:
`tests/test_admin_cost_routes.py` (360/768/1024/1440, No-JS, Tastatur, POST-Felder),
`tests/test_shopping_cost.py`, `tests/test_recipe_cost_db.py`, `tests/test_cost_calc.py`.

**Polish P3:** Ergebniszeilen `admin-table--stack` mit `data-label` und
`admin-status--*` für vollständig/unvollständig. «Vorschau schreibt nichts»
liegt in `hint()`; der Preis-unvollständig-Hinweis und der Bestätigungsfolgetext
bleiben sichtbar. Vorschau- und Belegformulare opt-in `data-loading`.

##### Modul Einstellungen – Erscheinungsbild (2026-09-20)

Erscheinungsbild nutzt M01/M24/M25: Seitenkopf «Erscheinungsbild» mit einem Satz
Kontext und genau einer Primäraktion «Speichern». Der frühere Veröffentlichungsblock
im Inhalt ist am 2026-09-20 durch `page_header(..., status_items=...)` ersetzt.
Zulässige Slots aus vorhandenem Template-Kontext: öffentliche Marke
(`active_revision.name`, Variante success, Ziel `?revision=` der aktiven Version),
ausgewählter Stand nur wenn er von der öffentlichen Version abweicht, Stand
Aktiv / Früher aktiv / Entwurf, Aktivierungs- oder Erstellzeit wenn geliefert.
Technische Versionsnummern, IDs und ungespeicherte Farbwerte sind keine Statusslots.

Entwurf und gespeicherte Vorschau stehen ab 1024 px in zwei Spalten, mobil
untereinander. Die Vorschau bleibt ein iframe der bestehenden Preview-Route, in
kompakter Höhe. Aktivieren bleibt sekundär mit Bestätigungstext. Wiederherstellen,
Versionsliste und Südhang-Standard liegen in nativem «Weitere Optionen».
Formularfeldnamen, POST-Ziel, CSRF, CAS-`version`, `revision`, Logo-Upload und
No-JS-Submit bleiben byte-gleich; die Speichern-Schaltfläche liegt im Kopf und
gehört über das native `form`-Attribut zum selben Formular. Nachweise:
`tests/test_ui_korrektur_branding_browser.py` (eigener Playwright-Start, 360/768/1024/1440,
No-JS, Tastatur, Statusbar, Überlauf), `tests/test_branding_browser.py`.

##### Modul Einstellungen – Benutzer & Zugriff (2026-09-20)

Benutzer & Zugriff nutzt M01/M22/M23/M25. Die Anlage unter der Kontenliste ist
ersetzt am 2026-09-20 durch eine Primäraktion «Anlegen» zur vorhandenen Anlageansicht;
leere Listen bieten dieselbe Aktion neutral an. Rollen, Passwort und Kontostatus
bleiben getrennte native Formulare mit unveränderter Bestätigung, CSRF und CAS.
«Bearbeiten» öffnet die Rollen als einzige Primäraktion im Detail; bei einem
Rollenfehler wird «Speichern» hervorgehoben. Passwortentzug und Deaktivierung
bleiben klar destruktiv. Anmeldedaten und Auditlinks liegen unter
«Weitere Optionen», Fehler öffnen weiterhin die betroffene Aktionsgruppe.

Die Detail-Statusbar zeigt ausschliesslich `account.disabled_at`, die Rollen aus
`account.roles`/`role_labels` und die zeitlich geprüfte Sperre aus `locked_until`
und `now`. Liste und Anlage zeigen nur bei fehlender Schreibverfügbarkeit den
Warnstatus «Nur lesen» aus `can_mutate`. Ereignislisten behaupten keinen Sitzungs- oder Abmeldestatus und
erhalten keine dekorativen Zähler. Die Filter verwenden die gemeinsame
`admin-filter-bar` ohne Suchfeld: Die bestehenden Routen erlauben keine Suche.
Kontenzeilen nutzen ab 1024 px drei Spalten, Ereignistabellen mobil beschriftete
Listen. Modul-CSS: `admin-settings-benutzer.css`; zentrale Tokens bleiben erhalten.

Nachweise: `tests/test_ui_korrektur_users_browser.py` mit eigenem Playwright-Start,
360/768/1024/1440 px, No-JS, Tastatur/Fokus, Statusbar, Dichtemessungen und nativen
POST-Verträgen; unveränderte DB-/AuthZ-/CAS-Gates für Konten und Zugriffsereignisse.

#### M26 — Wochenplan Cafeteria — kompakte Wochenplanung

Kompakte Wochenplanung statt riesiger Einzelkarten; Zielmodell SDD v2 §5.1.

```text
+----------------------------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Cafeteria                                                                                                     |
| [<] Vorherige KW   [7.–11. September 2026 / KW 37]   [>] Naechste KW   [Heute]   [Filter]   [Suche........]  [+] Menue   |
| [Pruefung offen]  [3 ohne Allergenangaben]  [Veroeffentlicht]                                                              |
+----------------------------------------------------------------------------------------------------------------------------+
| MONTAG 7.9. — Geoeffnet                                                                                                    |
| +------------------+  +------------------+  +------------------+  +------------------+                                       |
| | Suppe            |  | Menue 1          |  | Vegetarisch      |  | Dessert          |                                       |
| | [img] Tomatensuppe|  | [img] Pouletbrust|  | [img] Risotto    |  | [img] Apfelmus   |                                       |
| | Kartoffel, Brot  |  | Kartoffelstock   |  | Gemuese          |  |                  |                                       |
| | [Entwurf] [!] Allergene fehlen | [Entwurf] [!] Allergene fehlen | [+] Dessert planen |                                       |
| | [E] Bearbeiten   |  | [E] Bearbeiten   |  | [E] Bearbeiten   |  |                  |                                       |
| +------------------+  +------------------+  +------------------+  +------------------+                                       |
| DIENSTAG bis FREITAG folgen mit demselben Tagesmuster.                                                                     |
+----------------------------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Toolbar mit Zeitraum/KW, Vor/Zurück, Heute, Filter, Suche und genau einer Primäraktion. Je Tag eine kompakte Gruppe mit den konfigurierten Slots (Suppe, Menü 1, Vegetarisch, Dessert …): Gerichtname, wichtigste Komponenten, Status-Badge, Allergenwarnung mit Text, kleines Thumbnail, «Bearbeiten». Nicht geplante Slots als kompakte Add-Aktion («+ Suppe planen»). Keine bildschirmfüllenden Food-Fotos. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Bei unzureichender Spaltenbreite in chronologische Tagesabschnitte wechseln (siehe M10). Thumbnails und Badges bleiben lesbar; keine Schriftverkleinerung.

#### M27 — Wochenplan Patienten — Raster

Klare Rasterstruktur statt verstreuter Karten; Zielmodell SDD v2 §5.2.

```text
+----------------------------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Patienten                                                                                                     |
| [<] Vorherige KW   [7.–13. September 2026 / KW 37]   [>] Naechste KW   [Heute]   [Filter]   [Suche........]              |
| [Pruefung offen]  [5 ohne Allergenangaben]                                                                                 |
+----------------------------------------------------------------------------------------------------------------------------+
| Tag          | MITTAG                                              | ABEND                                                |
|--------------+-----------------------------------------------------+------------------------------------------------------|
| Montag 7.9.  | Menue 1: Pouletgeschnetzeltes, Reis                 | Menue 1: Schinken-Kaese-Toast                        |
|              | [!] Allergene fehlen  [E] Bearbeiten                | [!] Allergene fehlen  [E] Bearbeiten                 |
|              | Vegetarisch: Gemuesegeschnetzeltes                  | [+] Dessert planen                                   |
|              | [E] Bearbeiten                                      |                                                      |
| Dienstag …   | (gleiches Raster)                                   |                                                      |
| … Sonntag    | Alle 7 Tage x Mittag/Abend x vorhandene Menuearten  |                                                      |
+----------------------------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Zeile = Tag; Spaltengruppe = Mittag/Abend; darin kompakte Slots mit Gerichtname, Komponenten, Status-Badge, Allergenwarnung mit Text und «Bearbeiten». Nicht geplante Positionen als Add-Aktion («+ Suppe planen», «+ Dessert planen»), nicht als wiederholter Fliesstext. Tagesdetail bei Bedarf öffnen. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Sieben Tage und beide Mahlzeiten bleiben erreichbar; bei schmalem Viewport Tagesgruppen untereinander statt unleserlichem Raster. Keine Preise.

#### M28 — Wochenübersicht — Tabelle

Kompakte Verwaltungsliste; Zielmodell SDD v2 §5.3.

```text
+----------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Wochenuebersicht                                                 [+] Neue Woche anlegen     |
+----------------------------------------------------------------------------------------------------------+
| KW/Zeitraum              | Titel              | Bereich    | Status        | Offene Punkte | Aktionen   |
| 7.–13. September / KW 37| Herbstwoche        | Cafeteria  | Veroeffentlicht| 2            | [O] Oeffnen [...] |
| 31. Aug.–6. Sep. / KW 36| —                  | Patienten  | Zu pruefen    | 5            | [O] Oeffnen [...] |
+----------------------------------------------------------------------------------------------------------+
| [...] Weitere Aktionen  ->  Kopieren | Vorschau | Archivieren (nur wenn vorhanden)                        |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Spalten KW/Zeitraum · Titel · Bereich · Status · offene Punkte · Aktionen. «Öffnen» ist die primäre Zeilenaktion; Kopieren, Vorschau und Archivieren im beschrifteten Overflow. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Tabelle darf in priorisierte Listen wechseln; «Öffnen» bleibt sichtbar beschriftet.

##### Modul Wochenübersicht (Tabelle der gespeicherten Wochen) (2026-09-20)

M28 konkretisiert: KW/Zeitraum, Titel, Status und Aktionen. Die Seite zeigt genau
einen Bereich; daher keine redundante Bereichsspalte. Offene Punkte pro Woche
fehlen im vorhandenen Kontext und werden nicht erfunden. Cafeteria/Patienten sind
native Bereichsfilter mit `active` und `aria-current="true"`, ohne Primärfarbe.
`page_header(status_items=...)` zeigt den Bereich aus `area_names[profile]`;
Gespeicherte Wochen (`rows|length`) und Noch zu prüfen (`row.status == 'review_open'`)
nur bei vollständig geladenem Bestand (`page == 1 and not has_next`). Gesamtzahlen
über mehrere Seiten benötigen eine separate Backend-Erweiterung.

Eine neutrale Aktion «Öffnen» je Zeile; Vorschau und «Kopieren vorbereiten» samt
Quell-/Zielhinweis in nativem «Weitere Aktionen». Normale geschlossene Zeilen bei
1440 px höchstens 64 px; lange Inhalte, Zoom und offene Details dürfen wachsen.
Bei höchstens 1000 px Inhaltsbreite priorisierte Liste ohne horizontales Scrollen,
auch bei Zoom. Genau eine
`.btn-primary`: «Neue Woche anlegen» im Kopf als native Disclosure. Wochenhinweis
unter «Weitere Optionen», bei Inhalt/Fehler offen. Alle Formularfelder und Ziele,
CSRF, CAS und Capability-Bedingungen bleiben erhalten. Eigene Styles ausschliesslich
in `admin-wochenuebersicht.css`; gemeinsame Tokens und semantische Aktionsmakros.
Nachweise: `test_week_management.py`, `test_week_management_browser.py` (eigener
Playwright-Start, 360/768/1024/1440 px, Tastatur und No-JS), management-Fälle in
`test_ui_weeks_browser.py`; keine Abschwächung der Review-/Zoom-Prüfungen.

**Polish P3:** Wochentabelle `admin-table--stack`; Status als `admin-status--*`
mit Icon und Text, lange Beschreibung im `title`. Kopierfolge bleibt im
Aufklappbereich. Anlageformular opt-in `data-loading`; Listenhinweis in `hint()`.

#### M29 — Küchenkalender — Monat

Monatskalender zur Orientierung; Zielmodell SDD v2 §5.4.

```text
+----------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Kuechenkalender                                                                             |
| [<] Vorheriger Monat   September 2026   [>] Naechster Monat   [Heute]   Filter: [Beide|Cafeteria|Patienten] |
+----------------------------------------------------------------------------------------------------------+
| Mo    Di    Mi    Do    Fr    Sa    So                                                                   |
|  7     8     9    10    11    12    13                                                                 |
| Poulet Hack- Rind- Schwei- Zander  —     —                                                             |
| [C]   [C]   [C]   [C]   [C]                                                                              |
| Suppe Suppe Suppe Suppe Suppe                                                                            |
| +2    +1                                                                                                 |
| 14    15    ...                                                                                          |
| (Heute: 9.9. dezent markiert, nicht dominant)                                                            |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Kurze Gerichtnamen, Bereichs-/Mahlzeit-Label, Filter «Beide | Cafeteria | Patienten». Bei Überfüllung «+ n weitere». Heute klar markieren, aber nicht dominant. Klick öffnet Tagesdetail. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Kalenderzellen dürfen umbrechen; Filter und «Heute» bleiben erreichbar.

##### Modul Küchenkalender (Monat) (2026-09-20)

**Seitenrahmen:** `page_header('Küchenkalender', description='Monatsübersicht …', status_items=[…])` mit höchstens einer Primäraktion «Anlass anlegen» rechts (`draft.write`). Statusbar aus vorhandenen Template-Werten: `month_label`, `profiles` (Beide/Cafeteria/Patienten), gezählte geplante Tage im Monat, optional `Anlässe` aus `cell.events`, optional `Heute` wenn `year/month == today`. Keine erfundenen Workflow- oder Prüfstatus-Slots.

**Steuerung:** Monatsnavigation (Vor/Zurück, `type=month`-Sprung mit `<noscript>`-Submit, Heute) und Bereichsfilter als kompakte Button-Gruppe mit `profiles`-Query-Parameter in einer `kitchen-cal-toolbar`. Filter bleiben native Links/GET ohne JavaScript.

**Raster:** Desktop `kitchen-cal-grid` mit verdichteten Zellen, Mahlzeit-Labels, `+ n weitere` in `details`, Anlass-Links und leerem Zustand mit direkter «Planen»-Aktion. Mobil `kitchen-cal-list` (eine Spalte, kein Dokument-Overflow bei 360 px).

**Anlass-Formular (`kuechenkalender_anlass.html`):** Titel «Anlass anlegen»/«Anlass bearbeiten»; Statusbar aus `values.event_date`, `scope_labels[profile_scope]`, `guest_count`, optional `row_version`. Pflichtfelder Datum, Bereich, Titel, Gästezahl sichtbar; Beginn, Ende, Notiz und `row_version` in `disclosure_section` «Weitere Optionen» (öffnet bei Inhalt/Fehler). `form_footer` mit «Abbrechen» zum Kalender und einer «Speichern»-Primäraktion. Alle Feldnamen und POST-Ziele unverändert.

**Nachweis:** `tests/test_calendar_event_routes.py`, `tests/test_calendar_nav.py`.

**Polish P3:** Das Monatsraster bleibt ein Kalender; unter 1024 px gilt weiterhin
die vorhandene `kitchen-cal-list` statt `admin-table--stack`. «Heute» nutzt
`admin-status--info`. Sprungformular opt-in `data-loading`; Raster-/Listenumschaltung
in `hint()`.

#### M30 — Tagesansicht

Operativer Arbeitsplatz für einen einzelnen Tag; Zielmodell SDD v2 §6.

```text
+----------------------------------------------------------------------------------------------------------+
| WOCHENPLAN / Tagesansicht                                                                                |
| [<] Vorheriger Tag   Dienstag, 8. September 2026   [>] Naechster Tag   [Heute]   [...] Tag kopieren     |
+----------------------------------------------------------------------------------------------------------+
| MITTAG                                                                                                   |
| +---------------------------+  +---------------------------+  +---------------------------+              |
| | [img] Menue 1             |  | [img] Vegetarisch         |  | [+] Suppe planen          |              |
| | Pouletbrust an Kraeutersauce| | Gemuese-Curry, Reis       |  |                           |              |
| | Kartoffelstock            |  | [Entwurf] [!] Allergene   |  |                           |              |
| | [Entwurf] [!] Allergene   |  | [E] Bearbeiten  [...]     |  |                           |              |
| | [E] Bearbeiten  [...]     |  |                           |  |                           |              |
| +---------------------------+  +---------------------------+  +---------------------------+              |
| ABEND                                                                                                    |
| (gleiches Kartenmuster)                                                                                  |
+----------------------------------------------------------------------------------------------------------+
```

**Pflicht:** Datum mit Vor/Zurück und Heute; Gruppen Mittag/Abend. Karten mit kleinem Bild, Gerichtname, Typ, Komponenten, Allergene, Status, «Bearbeiten» und Overflow. Nicht geplante Slots als kompakte Add-Karten. Versteckte Versions-/Konfliktfelder, CSRF, Prüf- und Veröffentlichungsstatus der Allergendeklaration, Rollenbedingungen und bestehende Formularziele bleiben unverändert; fehlende oder ungeprüfte Allergenangaben erscheinen nie als allergenfrei.

**Responsive:** Meal-Gruppen untereinander; Add-Karten und Primäraktionen bleiben tastaturbedienbar.

##### Modul Wochenplan-Kern: Cafeteria-Woche, Patienten-Raster, gemeinsame Wochen-Partials (2026-09-20)

M10/M11 und die frühere Bildgrössenregel in M11b sind für die operative Wochenansicht
ersetzt am 2026-09-20 durch M26/M27: kompakte Tagesgruppen, Menü-Thumbnails mit maximal
96 px Kantenlänge, festem Seitenverhältnis und Lazy Loading. Mittag und Abend stehen
auf breiten Arbeitsflächen nebeneinander; Gang-Editoren gehören zur jeweiligen Mahlzeit.
Lange Inhalte dürfen wachsen, Warntexte und beide Cafeteriapreise bleiben lesbar.

Die gemeinsame Wochensteuerung verwendet `page_header(..., status_items=...)`:
KW/Zeitraum, tatsächlicher Wochenstatus, Kartenprüfungen, fehlende/offene
Allergenangaben und vorhandene Gangprobleme. Keine technischen Revisionen oder IDs.
Gangprobleme behalten das Ziel `#course-issues`; das derzeitige gemeinsame Makro
unterstützt keine Linkwerte, daher steht die native Warnaktion in der Werkzeugleiste.
Die wichtigste Wochenaktion steht im Kopf; Vorschau und Wochenprüfung bleiben
sekundär, seltene Aktionen im nativen «Weitere Aktionen»-Bereich.

Alle Formularnamen, Werte, CSRF-/CAS-Felder und Gang-Partials bleiben unverändert.
Die gesperrten Gang-Partials liefern eigene Primärbuttons innerhalb eingeklappter
Formulare; deren Umstellung auf neutrale Buttons benötigt den Integrationsowner.
Keine Suche, Filter, Tageskopie oder Schnellerfassung aus dem Mockup hinzuerfinden.

Die Cafeteria ordnet gemeinsame Gänge neben den beiden Menüoptionen an; im
Patientenraster stehen die Gänge unter der jeweiligen Mahlzeit. Alle Allergen-
und Prüfhinweise bleiben als Text sichtbar. Gangprobleme lassen sich am nativen
Ziel `#course-issues` aufklappen. Ohne JavaScript erlaubt eine native Bestätigung
die Veröffentlichung über dasselbe Formular mit unveränderten CSRF-/CAS-Feldern.
Kopieren zeigt Quelle und Ziel einmal in der Statusbar. Browser-Messungen prüfen
360/768/1024/1440 px, Thumbnailgrösse, Tageshöhe, Mahlzeitenausrichtung und Tastatur.

## 9. Wiederverwendung statt Seitensonderlösungen

Nutze vorhandene Strukturen. Fehlen gemeinsame Bausteine, lege sie in der passenden bestehenden Projektstruktur an. Geeignete Verträge sind:

| Baustein | Gemeinsame Verantwortung |
|---|---|
| Seitenrahmen / Basis-Template | Assets, Sidebar, Topbar, Hauptbereich, globale Meldungen |
| Seitenkopf | Titel, optionale Beschreibung, Breadcrumbs und Aktionen |
| Formular-Macros | Label, Feld, Hilfetext, Pflichtstatus und Fehlerzuordnung |
| Status-Macro | Feste Zuordnung echter Statuswerte zu Text und Farbvariante |
| Empty State | Titel, hilfreiche Erklärung, optionale erlaubte Aktion |
| Pagination | Wahrer Datenumfang, Seitenlinks, deaktivierte Zustände |
| Aktionsleiste | Eine Speicherhandlung je vorhandenem Formular; Status und Reichweite eindeutig, ohne verdeckte Felder oder Fokus |
| Arbeitszeile und Detailbereich | Eine Darstellung derselben Formularfelder; Kurztext, offene Fehler, Fokus und erhaltene Werte |
| Zeilenaktionsmenü | Beschriftete seltene vorhandene Aktionen; ursprüngliche Struktur-/Submit-Semantik und Rückkehr zum Objekt |
| Icon-Macro | Vorhandene Sprite-IDs, konsistente sichtbare Texte und zugängliche Namen; fehlende Icons erkennbar prüfen |

Jinja ist Teil der bestehenden Flask-Template-Struktur; verwende die vorhandene Vererbung und Escape-Regeln. Kein pauschales `safe`, um Darstellungsprobleme zu umgehen. [S8]

Keine parallelen Varianten wie `modern-card`, `better-table` oder `new-form-v2`. Keine universelle Mega-Komponente mit Dutzenden fachlichen Schaltern. Fachseiten dürfen unterschiedliche Inhalte haben; dieselbe Komponente darf nicht pro Seite anders aussehen.

## 10. Responsive Verhalten und Barrierefreiheit

Verwende die installierten Bootstrap-/Tabler-Breakpoints. Dieser Standard setzt die unveränderte Standardaufteilung voraus: ab 992px Desktop-Sidebar, 768–991px Tablet, darunter Smartphone. Bei nachgewiesen angepassten Projekt-Breakpoints zuerst eine zentrale Zuordnung festlegen und dokumentieren, keine zweiten konkurrierenden Breakpoints einführen.

Unterhalb des Desktop-Breakpoints: Sidebar über die vorhandene Collapse-/Offcanvas-Lösung öffnen; „Menü“, Fokus und Schliessen bleiben erreichbar. Sie darf Formulare nicht auf eine schmale Restfläche drücken. Feldgruppen auf kleinen Geräten sinnvoll umordnen: kurze Mengen-/Einheitenfelder dürfen bei ausreichendem Platz nebeneinander bleiben, umfangreiche Bereiche stehen untereinander. Abschnittslinks und Aktionsgruppen umbrechen lassen; Hauptaktionen bleiben sichtbar beschriftet.

Keine horizontale Gesamtdokument-Scrollleiste bei 390px oder im Reflow bei 320 CSS-Pixeln. Zutatenzeilen mobil umordnen statt eine Desktoptabelle zu schrumpfen. Cafeteriaraster bei unzureichender realer Spaltenbreite in chronologische Tagesabschnitte überführen; Patienten behalten sieben Tage, Mittag/Abend und vorhandene Menüarten. Andere fachlich notwendige breite Tabellen dürfen lokal, erkennbar und tastaturbedienbar scrollen; Ausnahmen begründen, wichtige Inhalte nicht abschneiden. Sticky-Speicherleisten verdecken weder Feld noch Fehler oder Fokus und dürfen bei mobiler Tastatur oder geringer Höhe in den Dokumentfluss wechseln.

Ziel ist WCAG 2.2 AA für betroffene Oberflächen: normaler Text mindestens 4,5:1, grosser Text mindestens 3:1; zur Erkennung notwendige nicht-textliche UI-Informationen grundsätzlich mindestens 3:1 zu benachbarten Farben. Prüfe Ausnahmen und Zustände sachgerecht, nicht nur ausgewählte Standardfarben. [S3, S7]

Als zusätzlicher **Projektstandard** gelten mindestens 44px für wesentliche Bedienelemente. Das ist bewusst grosszügiger als das 24px-Mindestmass des WCAG-2.2-AA-Kriteriums 2.5.8, das eigene Ausnahmen kennt. Behaupte nicht, WCAG AA verlange pauschal 44px. [S9]

Sichtbarer Fokus: auf hellen Flächen mindestens 2px Burgunder-Outline mit Abstand, in der Sidebar eine ausreichend kontrastierende helle Variante. Fokus nicht entfernen. Reihenfolge, Labels, Tastaturbedienung, 200%-Zoom und reduzierte Bewegung prüfen. Automatisierte axe-Prüfungen decken nicht alle Barrierefreiheitsanforderungen ab. [S5]

## 11. Migrationsablauf mit überprüfbaren Ergebnissen

### Phase A – Bestand und Befunde

Lies Repository-Anweisungen, relevante SDDs und bestehende Designentscheidungen. Prüfe den Git-Zustand und die tatsächlichen Versionen. Ermittle alle UI-Routen, Templates und Komponenten sowie Start- und Testbefehle.

Erweitere das vorhandene UI-Inventar mit echtem Modul, Route und sinnvollem Parameterbeispiel, Rolle/Zustand, Template, Kernaufgabe, M01–M20-/R01–R10-Zuordnung, vorhandenen Tests und tatsächlichem Nachweisstatus. Routen, Navigation, Template-/Komponentenverwendungen und Browserprüfungen abgleichen; nicht nur Indexseiten. Repräsentative Datenklassen sowie getrennte Rechte-/Fehlerzustände festlegen. Vor Änderungen Screenshots mit synthetischen Daten erfassen; produktive Personen-, Patienten- und Zugangsdaten gehören nicht in Testartefakte. Alte Audits und historische Commits bleiben historische Belege.

Formuliere Befunde konkret nach diesem Muster:

> **Problem → Beleg → Auswirkung → konkrete Korrektur → betroffene Komponenten/Seiten.**

Keine pauschalen Urteile wie „alles veraltet“ und keine unbewiesenen Aussagen über CSS oder Funktionsfehler.

**Historische Einstiegspunkte im aktuellen Stand verifizieren:**

| Einstieg | Zweck der Prüfung |
|---|---|
| `reference_scaffold/cafeteria/templates/admin/base_tabler.html` | Gemeinsamer Seitenrahmen, Navigation, Breite, Vererbung |
| `reference_scaffold/cafeteria/templates/admin/_macros.html` | Bestehende Icons und gemeinsame UI-Bausteine |
| `reference_scaffold/cafeteria/templates/admin/rezepte_editor.html` | Zutaten-, Schritt-, Quellen- und Speicheranordnung |
| `reference_scaffold/cafeteria/templates/admin/_rezepte_fields.html` | Felder und Zeilenaktionen; Verträge nicht versehentlich verändern |
| `reference_scaffold/cafeteria/admin/recipe_routes.py` | Tatsächliche Daten- und Formularsemantik verstehen |
| `docs/design/2026-09-12-fullwidth-audit.md` | Historische Breitenbefunde, kein Nachweis aktueller vertikaler Effizienz |

#### Konkrete Prüfung von Platz und Aufgabenaufwand

| Prüffrage | Erwartete Untersuchung |
|---|---|
| Ist nur der äussere Rahmen breit? | Gesamte Containerhierarchie und echte Kerninhalte messen. |
| Wie weit liegt das erste fachliche Objekt unter dem Seitenbeginn? | Davorstehende Verwaltung, Duplikate und dekorative Karten identifizieren. |
| Wie viele Alltagsangaben sind ohne Zusatzklick bearbeitbar? | Menge/Einheit und typische Felder praktisch bedienen. |
| Wird pro Datensatz ein fast bildschirmhoher Block wiederholt? | Gemeinsames Zeilen-/Detailmuster anwenden; keine Einzelseiten-Ausnahme. |
| Sind leere optionale Felder oder technische IDs ständig offen? | Sinnvoll zusammenfassen und gezielt öffnen; Warnungen erhalten. |
| Sind Tabs, Meldungen, Kopfzeilen oder Aktionen doppelt? | Einen eindeutigen Platz und tatsächlichen Geltungsbereich festlegen. |
| Erzeugen kompakte Menüs mehr Arbeit? | Klickzahl und Scrollweg derselben Aufgabe vorher/nachher vergleichen. |
| Ist Bedienung ohne Vorkenntnis möglich? | Sichtbare Wörter, Kontext und ungefährliche Rückwege prüfen. |
| Gibt es fremde Seiteneffekte? | Gemeinsame CSS-/Macro-Verwendung sowie öffentliche Ausgabe regressionsprüfen. |

#### Messbare Dichteziele

Vergleiche identische Daten, Browserbedingungen und Viewports. Erfasse äussere/innere Breite, Gesamtseitenhöhe im normalen Ausgangszustand, Position des ersten Kerninhalts, direkt nutzbare Zeilen, Klicks/Scrollweg für eine Hauptaufgabe und verbleibende Fehler.

Für normale Listen und Editoren ist erster Kerninhalt innerhalb von ungefähr 280 CSS-Pixeln ab Viewportoberkante ein Prüf-Richtwert. Notwendige Warnungen oder mehrzeilige Titel dürfen ihn überschreiten; begründe dies, statt Pflichtinformationen zu verstecken.

Beim einfachen Rezept mit vier Zutaten und zwei Schritten sollen bei 1440 × 900 in der Standardansicht alle vier kompakten Zutatenzeilen und der Beginn der Zubereitung ohne Verwaltungs-Scrollreise sichtbar sein. Prüfe zusätzlich mindestens ein längeres Rezept mit 20 Zutaten und 10 Schritten. Es darf scrollen; eine offene Grosscard pro Eintrag bleibt unzulässig.

Für nachweislich überlange Wiederholungsformulare kann eine ungefähr halbierte Ausgangsseitenhöhe als Vergleichsziel dienen, nicht als allgemeine Schrumpfpflicht. Bereits kompakte Seiten nicht künstlich verändern. Keine verkleinerte Schrift, versteckte Zutatenliste, neuen Pflichtklicks oder abgeschnittenen Texte als Erfolg zählen.

### Phase B – Gemeinsame Grundlage

Implementiere Tokens, Tabler-Anbindung, Typografie, Seitenrahmen, Navigation und zentrale Komponenten. Prüfe deren Auswirkungen über die inventarisierten Layoutvarianten. Führe kein pauschales globales CSS ein, das Spezialansichten beschädigt.

Lege eine tatsächliche Komponentenübersicht im Entwicklungs-/Testkontext an, sofern noch keine existiert: Buttons und Zustände, Formfelder, Tabs, Cards, Badges, Alerts, Tabelle und Dialog. Verwende echte Komponenten, nicht separat nachgebaute Demo-HTML. Keine ungeschützte Produktions-Demoroute.

### Phase C – Referenz pro Seitentyp

Der Rezepteditor ist die erste Referenz: M02–M06 und M19 inklusive Inline-Mengen, Strukturaktionen, Detail-, Mobil- und Fehlerzuständen. Danach je eine vorhandene repräsentative Listen-, Formular-, Detail- und Einstellungsseite sowie besondere Facharbeitsflächen anhand M01–M20 migrieren. Fehlende Seitentypen oder Fachfunktionen nicht aus Skizzen neu erfinden.

Prüfe die Referenzen im Browser, korrigiere die gemeinsamen Komponenten und halte das resultierende Design fest. Ein generiertes Bild ist stilistische Orientierung, keine pixelgenaue Browser-Baseline und kein funktionaler Vertrag.

### Phase D – Alle Tools und Routen migrieren

Arbeite die vollständige Bestandsaufnahme ab. Übertrage die geprüften Bausteine auf jedes vorhandene Tool, einschliesslich Unterseiten, Modals, Rollenvarianten, Leer- und Fehlerzuständen.

Der Abschluss einer Referenzseite ist nicht der Abschluss der Migration. Bei globaler CSS-Wirkung jede betroffene Route mindestens überprüfen, statt aus einer einzigen schönen Seite auf den Rest zu schliessen.

### Phase E – Regression und Absicherung

Prüfe bestehende Kernabläufe mit realistischen Testdaten: Anzeigen, Anlegen, Bearbeiten, erlaubte Folgeaktionen, Validierung, Redirects, Tabs und Rollen. Besonders Feldnamen, Form-Methoden, Action-URLs, IDs, JS-Hooks, CSRF und das unterschiedliche Submit-Verhalten von `disabled`/`readonly` erhalten.

Nutze die vorhandenen Flask-Tests für serverseitiges Verhalten und Browser-Tests für echte Interaktion. Ein erfolgreicher Template-Render ersetzt keinen Browser-Test. Unverändertes Backend nicht pauschal behaupten, sondern den Diff prüfen.

### Kleine Pakete und laufende Integration

Arbeit in das vorhandene Backlog übernehmen; bestehende Pakete zuordnen und korrekte erledigte Arbeit erhalten. Gemeinsame Templates, Makros, Iconmapping und Styles haben einen Integrationsowner. Die folgende Aufgabenfolge wird vorhandenen MP-/WP-IDs zugeordnet; sie erzeugt keine zweite Paket- oder Leaseverwaltung.

| Paket | Inhalt | Pflichtnachweis |
|---|---|---|
| UI-00 | Aktuellen Stand, Regeln, vorhandene Tests, Inventar und konkrete Befunde erfassen | Tatsächliche Dateien, Rollen, Formularverträge und Baseline |
| UI-01 | Manifest konsolidieren, M01–M20 passend integrieren, Agentenverweise aktualisieren | Eine gültige Quelle ohne konkurrierende Breiten- und Formularkonzepte |
| UI-02 | Gemeinsame kompakte Arbeitszeile, Detailbereich, Aktionsmenü und Symbolverwendung | Tastatur, native/serverseitige Fehler, unveränderter Formularweg |
| UI-03 | Rezepteditor inklusive Mobil-, Detail- und Fehlerzuständen umsetzen | M02–M06 und M19 mit tatsächlichem Speichern und Strukturaktionen |
| UI-04 | Übrige Editoren, Bausteine, Stammdaten und Formulare nachziehen | Vollständige Zuordnung nach Inventar, nicht nur bekannte Screenshots |
| UI-05 | Listen, Wochenübersicht und Planungsflächen verdichten | M07–M12, vollständige Patienten-/Cafeteriasemantik |
| UI-06 | Ausgabehubs, Einstellungen, Design, Import und Benutzer prüfen/umbauen | M14–M18/M20 ohne Ausgabe-, Import- oder Rechteänderungen |
| UI-07 | Gesamtregression und Vergleichsbelege | Jede tatsächliche Seite mit Status, Vorher/Nachher und Tests |
| UI-08 | Zukunftsregeln in vorhandene Inventar-, Browser- und Reviewprüfungen integrieren | Neue UI-Routen können nicht still am Inventar vorbeigehen |
| UI-09 | Nutzertest und verbleibende Abnahme dokumentieren | Ergebnisse oder ausdrücklicher Status „noch ausstehend“ |

Jedes Paket nennt Ziel, R-/M-/A-IDs, tatsächliche Dateien und Besitzer, Abhängigkeiten, konkrete Tests und Risiken. Grosse Seitenpakete weiter aufteilen; nach stabiler gemeinsamer Basis nur unabhängige und dateidisjunkte Seiten parallel bearbeiten. Keine gestarteten Worker ohne tatsächlichen Ausführungsbeleg behaupten. Kleine Änderungen fortlaufend integrieren und prüfen; gemeinsame Ursachen zentral korrigieren und alle betroffenen Verwendungstypen regressionsprüfen. Manifeständerung oder Rezepteditor allein schliessen die Migration nicht ab.

## 12. Reproduzierbarkeit, Abnahmetests und visuelle Regression

Prüfe mindestens diese Viewports:

| Viewport | Zweck |
|---|---|
| 1440 × 900 | Regulärer Desktop |
| 1024 × 768 | Kleiner Desktop / Grenzfall mit Sidebar |
| 768 × 1024 | Tablet mit eingeklappter Navigation |
| 390 × 844 | Smartphone |
| 1920 × 1080 | Breitenprüfung der gemeinsamen Layoutvarianten |
| 2560 × 1440 | Grosse Arbeitsfläche: innere Breite und Dichte prüfen |

Jede interne UI-Seite mindestens bei 1440 × 900 und 390 × 844 öffnen, visuell prüfen und eine passende Kernaufgabe ausführen. Repräsentative Seitentypen und gemeinsame Komponenten zusätzlich in allen sechs Viewports prüfen. Dazu echter **200-%-Browserzoom**, **Reflow bei 320 CSS-Pixeln**, Tastatur und reduzierte Bewegung. Falls echte Zoomsteuerung fehlt, einen ersatzweisen Reflowtest ausdrücklich als solchen führen, niemals als ausgeführten Zoomtest. Fehlende Rollen, Fixtures oder Browserwerkzeuge ergeben „blockiert“ oder „nicht ausgeführt“. Signage behält zusätzlich seine fachlichen 1920 × 1080-/3840 × 2160-Ausgabeprüfungen; Admin-Vollbreite gilt nicht innerhalb eines A4-Druckbogens. Alle tatsächlich geprüften Kombinationen im Inventar festhalten.

Stabile Referenzbedingungen festlegen: Browser und Version, Betriebssystem beziehungsweise Container, tatsächlich geladene Fonts, Viewport, Gerätepixelfaktor, Sprache, Zeitzone, Benutzerrolle, Testdaten und eingefrorene relevante Uhrzeit. Animationen für visuelle Tests kontrollieren, nicht wahllos im Produkt entfernen. Auf Font- und Inhaltsbereitschaft warten, nicht allein mit festen Sleep-Zeiten arbeiten.

Playwright Test kann Screenshots erzeugen und gegen Referenzen vergleichen. Rendering kann sich zwischen Umgebungen unterscheiden; Referenzen und Vergleichsläufe müssen deshalb in kontrollierten vergleichbaren Umgebungen entstehen. [S4]

Freigegebene Baselines versionieren. Der Agent darf vorgeschlagene erste Referenzen erstellen, aber sie nicht selbst als vom Auftraggeber freigegeben ausgeben. Fehlschlagende Screenshots nie blind aktualisieren, um eine Prüfung grün zu machen. Dynamische Daten nur begründet maskieren; keine eigentlichen Layoutfehler wegmaskieren.

**Ein Prompt allein ist keine Garantie für identische Oberflächen. Verbindlich wird der Standard durch gemeinsame implementierte Komponenten, zentrale Tokens und geprüfte visuelle Referenzen.**

### 12.1 Abnahmekriterien A01–A24

Nutze die vorhandenen Testmittel. Neue reine Entwicklungsabhängigkeiten nur im Rahmen der Projektregeln; keine zusätzliche Produktionsbibliothek für diese UI-Aufgabe. Tests dürfen echte Layoutprobleme nicht durch blind aktualisierte Screenshots als neue Baseline akzeptieren.

| ID | Test | Bestehen bedeutet |
|---|---|---|
| A01 | Vollständiges UI-Inventar | Alle tatsächlich vorhandenen internen Seiten, Unteransichten und relevanten Rollen-/Zustandsklassen sind nachvollziehbar erfasst. |
| A02 | Volle Breite | Äussere und innere Gesamtcontainer nutzen den Arbeitsbereich ohne künstliche Mittelsäule und ohne Dokumentüberlauf. |
| A03 | Aufgabenbeginn | Kernarbeit steht vor optionaler Verwaltung; doppelte Bereichsauswahl und gleichlautende Prüfaktionen sind beseitigt. |
| A04 | Rezeptbasis 4/2 | Kurze Basisfelder, vier direkt bedienbare Zutaten und Beginn der Zubereitung erfüllen das beschriebene Desktopziel. |
| A05 | Langes Rezept 20/10 | Liste bleibt kompakt; notwendiges Scrollen statt riesiger Vollformulare; Angaben vollständig zugänglich. |
| A06 | Inline-Mengenänderung | Genau ein massgebliches Feld je Wert; ohne Detaildialog ändern und korrekt speichern. |
| A07 | Detailzustand | Öffnen, Schliessen und lokale Navigation verlieren oder speichern keine Eingaben. |
| A08 | Strukturaktion | Hinzufügen, Verschieben und Entfernen erhalten Reihenfolge, Zuordnungen, signierte Kontexte und bestehende Speichersemantik. |
| A09 | Fehler in geschlossenen Bereichen | Native und serverseitige Fehler öffnen bzw. erschliessen den richtigen Bereich, setzen sinnvollen Fokus und erhalten Werte. |
| A10 | Unverändertes Speichern | Daten, Referenzen, readonly/disabled-Bedeutungen und nicht auflösbare bestehende Zuordnungen überstehen den Roundtrip. |
| A11 | Gespeichert versus geprüft | Keine Bestätigung neuer ungespeicherter Werte durch alten Prüfstand; fehlende Allergene nicht als allergenfrei darstellen. |
| A12 | Unklare Schreibantwort | Kein falscher Erfolg und keine blinde Wiederholung; vorhandenen aktuellen Stand nachvollziehbar prüfen. |
| A13 | Patientenumfang | Alle sieben Tage, Mittag/Abend und bestehenden Menüarten erreichbar; keine Preise. |
| A14 | Cafeteriaumfang | Fünf reguläre Tage, vorhandene Menüarten und beide Preisgruppen korrekt; Ausnahmen aus bestehender Konfiguration erhalten. |
| A15 | Druckdatenstand | Absichtlich unterschiedliche gewählte/veröffentlichte Wochen ergeben korrekt beschriftete und tatsächlich passende Ausgaben. |
| A16 | Symbole und Texte | Vorhandene Icons geladen; gleiche Handlung gleich; Hauptaktionen auf Desktop und Mobil sichtbar beschriftet. |
| A17 | Bedienbarkeit | Maus, Tastatur, Touch, Trefferflächen, Fokus, Smartphone und echte Zoom-/Reflowprüfungen korrekt. *(Ersetzt am 2026-09-20 durch: Pflichtbreiten 360, 768, 1024, 1440 px in der Testmatrix. Sidebar darf mobil zu Drawer werden.)* |
| A18 | Sticky-Leisten | Kein Feld, Fehler oder Fokus verdeckt; eingeblendete mobile Tastatur und geringe Höhe berücksichtigt. |
| A19 | Suche und Leerzustände | Gesamte bestehende Suchsemantik erhalten; Datenleerstand, Filtertrefferlosigkeit, Fehler und Rechte unterscheiden. |
| A20 | Bestehende Sicherheitsgrenzen | CSRF, Formularkontext, Rollen, Versionierung, Session- und Serverprüfungen unverändert wirksam. |
| A21 | Technischer Diff | Keine ungefragten Framework-, Datenmodell-, Vertrags-, Fachlogik- oder Betriebsänderungen. |
| A22 | Öffentliche Nebenwirkungen | Website, Login, Druck/PDF und Signage nicht durch Admin-Styles beschädigt oder mit Admininhalten vermischt. |
| A23 | Vergleichbare Belege | Gleiche Daten/Viewports, echte Screenshots und nachvollziehbare Aufgabenmessung; Baselines nicht blind ersetzt. |
| A24 | Zukunftsgate | Neue/geänderte UI-Routen und gemeinsame Komponenten sind mit passenden Inventar-, Funktions- und Browserprüfungen verbunden. |
| A25 | Auswahl mit Detail nach Auswahl | Kein dauerhaft sichtbares Detailfeld bei nicht ausgewählter Option; Feldnamen, Werte, Standardwerte und Prüfstatus unverändert; «nicht ausgewählt» nie als «allergenfrei» (M21). |
| A26 | Eine Primäraktion je Kontext | Pro Formular genau eine hervorgehobene Speicherhandlung; destruktive Aktionen links, seltene im «Weitere Aktionen»-Menü (M24, R08). Verschärft durch Polish-Lauf: R14, R15. |
| A27 | Einheitliche Listenstruktur | Dieselbe Filterzeile und Zeilenaufbau in allen Modulen; Suche zuerst, «Filter zurücksetzen» nur bei Aktivität (M22, M23). Verschärft durch Polish-Lauf: R30, M33. |
| A28 | Wochenplan Desktop-Dichte | Wochenplan-Ansichten bei 1440 px ohne grosse Leerflächen und ohne bildschirmfüllende Food-Fotos (M26–M30, SDD v2 §5). |
| A29 | Nicht geplante Slots | Leere Planungspositionen als kompakte Add-Aktion («+ Suppe planen»), nicht als Fliesstext oder grosse Leerkarten. |
| A30 | Statuschips mit Handlung | Statuschips mit sichtbarem Text; optional als Link zum Filtern oder Navigieren, nicht nur als Farbindikator. |
| A31 | Review-Checkliste v2 | `docs/design/design-system-v2-2026-09-20/06_QA/UI_REVIEW_CHECKLIST_V2.md` je UI-Paket vollständig abgehakt. |

### 12.2 Nutzertest mit mindestens drei tatsächlichen Personen

Mindestens drei technisch unerfahrene Personen testen repräsentative Kernaufgaben ohne navigierende Hilfestellung: Menge ändern, Zutat hinzufügen und verschieben, Schritt bearbeiten, fehlende Angaben finden und bewusst speichern. Dazu je eine Aufgabe aus Planung, Verwaltung und Ausgabe.

Dokumentiere Suchwege, Fehlklicks, Rückfragen und kritische Missverständnisse. Als Projektziel sollen mindestens zwei von drei Personen jede Kernaufgabe ohne Wegbeschreibung abschliessen. Verwechslungen wie globales Löschen statt lokalem Entfernen, Prüfen statt Speichern oder falscher Druckzeitraum verhindern die Nutzerabnahme unabhängig von einer guten Durchschnittsquote.

Fehlen Testpersonen, bleibt dieser Nachweis offen. Ein Agententest oder automatisierter Kontrastcheck ersetzt weder reale Benutzer noch eine vollständige Zugänglichkeitsprüfung.

## 13. Dauerhafte Regeln für alle Coding-Tools

Dieses Manifest bleibt unter `docs/design/2026-09-09-unified-ui-design-system.md` die einzige ausführliche Quelle. AGENTS.md und CLAUDE.md enthalten denselben kurzen Leseauftrag; bestehende und bereichsspezifische Regeln bleiben erhalten. [S10, S11]

> Vor jeder Frontend-Änderung das zentrale UI-Manifest vollständig lesen und passende R-/M-/A-Regeln verwenden. Volle interne Arbeitsbreite, kompakte Wiederholungszeilen, direkt bedienbare häufige Felder und beschriftete Icons gelten für jede neue und geänderte Seite. Details, Fehler, Formulardaten und Speicherzustände sicher behandeln. Route, Rolle/Zustand, Muster und tatsächliche Tests im vorhandenen UI-Inventar nachführen. Keine Fertigmeldung ohne Funktions- und Sichtnachweise; fehlende Prüfungen nennen.

Ein Dateiname allein belegt nicht, dass der Inhalt gelesen wurde. Startdateien kurz halten und die ausführliche Spezifikation an diesem einzigen Ort pflegen.

Keine parallele Prüfarchitektur: bestehende Routeninventar-, Formular- und Browserprüfungen um vertikale Effizienz, Detail-/Fehlerverhalten, Beschriftungen und Vertragsroundtrips erweitern. Statische Suche ersetzt keine Bedienprüfung. Neue Routen brauchen eine bewusste Inventarzuordnung; jede globale Komponentenänderung löst Regression ihrer betroffenen Verwendungstypen aus.

Frühere Freigaben bei konkreten Änderungen revalidieren, nicht pauschal entwerten oder als aktuelle eigene Tests ausgeben. Bestandsabweichungen bleiben offen, bis sie behoben oder ausdrücklich fachlich begründet sind. Gestaltungsausnahmen nennen Ursache, Umfang und Entscheidung; „war vorher auch so“ genügt nicht. Baselines nicht ungeprüft ersetzen.

## 14. Sicherheits- und Änderungsgrenzen

Keine Änderungen an Authentifizierung, Autorisierung, Session-Handling, Secrets, CSRF oder Datenverträgen als Abkürzung für UI-Arbeit. Keine zusätzlichen öffentlichen Schnittstellen und keine unkontrollierten externen Fonts, CDNs oder Telemetrie integrieren.

Flask, Jinja, Tabler, Iconeinbindung, Datenhaltung und Fachlogik bleiben bestehen. Keine neue Produktionsabhängigkeit, Datenmigration, Speicher-/Vorschau-API, Freigabe- oder Allergenlogik und kein ungefragter Build-/Deploymentumbau. Standardbereich sind bestehende Templates/Partials, projektbezogene Styles, kleine Interaktionen im vorhandenen Assetweg, Tests und Dokumentation. Unvermeidbare darstellungsbezogene Python-Änderungen nach bestehenden Regeln separat begründen. Keine Rezept-, Klinik- oder Formulardaten ungefragt in Local Storage, neue Offline-Speicher oder externe Telemetrie schreiben.

Vor jedem Formular den bestehenden Vertrag sichern: URL, HTTP-Methode, Feldnamen, Indizes, IDs, CSRF, signierter Kontext, Versions-/Konfliktprüfung, `readonly`/`disabled`, `formaction`, `formnovalidate`, Fehlerantwort, Redirect und tatsächlicher Speicherzeitpunkt. Eine optisch lokale Aktion darf nicht unbemerkt eine persistente globale Änderung werden. Strukturaktionen behalten ihre gesonderte Semantik; kein pauschales `novalidate` und keine zweite clientseitige Sortierlogik.

Keine produktiven Lösch-, Import-, Benachrichtigungs- oder Versandaktionen durch Tests auslösen. Vorhandene autorisierte Entwicklungs-/Testumgebung und synthetische Daten verwenden. Sicherheitslücken oder notwendige fachliche Erweiterungen getrennt benennen; Sicherheitsprüfungen nicht verstecken oder stillschweigend aus dem Scope entfernen.

Keine fremden Änderungen überschreiben, keine grossflächigen Rewrites und keine unautorisierten Pushes oder Deployments. In kleinen logisch prüfbaren Änderungen arbeiten. Ohne funktionsfähige Browser-Testumgebung darf Code vorbereitet werden, aber die visuelle Abnahme bleibt offen.

## 15. Lieferumfang und Definition of Done

Liefere die tatsächlichen Implementierungsänderungen, ein konsolidiertes Designsystem, konkrete Befunde, das vollständige UI-Inventar, Testbelege und Vorher-/Nachher-Screenshots. Nutze die vorhandene Dokumentations- und Teststruktur; neue Parallelordner sind kein Qualitätsmerkmal.

Die Abdeckungstabelle enthält mindestens:

| Tool / Modul | Seite / Route / Rolle / Zustand | R-/M-/A-Muster | Befund und Ursache | Geänderte Dateien | Vorher/Nachher | Test / Viewport | Status / Restpunkt |
|---|---|---|---|---|---|---|---|

Teststatus eindeutig verwenden: **bestanden**, **fehlgeschlagen**, **nicht ausgeführt**, **blockiert** oder **nicht anwendbar mit Begründung**. Zusätzlich **implementiert**, **technisch geprüft**, **visuell geprüft** und **durch Benutzer abgenommen** unterscheiden. Ein geerbtes Basis-Template, HTTP 200, Build, Screenshot oder Breitenwert beweist weder vollständige Interaktion noch das Gesamtaudit.

Vorher-/Nachher-Belege unter denselben Bedingungen speichern. Zu HTML-Prototypen die tatsächlichen HTML-/CSS-/JS-Quellen ablegen; Prototypen und generierte Bilder sind kein Implementierungsnachweis. Anwendungsscreenshots eindeutig kennzeichnen. Bereinigte HTML-Belege enthalten keine Zugangsdaten, Sessionwerte, CSRF-Tokens oder personenbezogenen Patientendaten. Die Übergabe nennt pro Paket Anforderungen, tatsächliche Dateien, erhaltene Formularverträge, ausgeführte Tests, Screenshotbelege und Restentscheidungen.

Eine reine Manifestkonsolidierung erfüllt nur den Dokumentteil UI-01. Produktimplementierung, Inventar, Browser-/Formularprüfungen und der reale Drei-Personen-Nutzertest brauchen jeweils eigene Belege; dieses Dokument behauptet keinen bestandenen Produkttest.

Die Gesamtmigration ist erst abgeschlossen, wenn alle vorhandenen betroffenen Tools und Routen inventarisiert, migriert und entsprechend der Testmatrix geprüft sind; das Design zentral umgesetzt ist; wesentliche Abläufe weiterhin funktionieren; keine unerklärten alten Admin-Stile verbleiben; keine Attrappen oder erfundenen Daten hinzugekommen sind; und verbleibende Einschränkungen nicht verschwiegen werden.

Verwende für den Abschlussbericht:

```text
## Konkrete Ausgangsprobleme
Befund, Beleg und Auswirkung.

## Umgesetzte gemeinsame Änderungen
Tokens, Tabler-Anbindung, Layout und Komponenten.

## Abdeckung aller Tools und Seiten
Tatsächliche Namen/Routen mit Status und Restpunkten.

## Tests und Screenshots
Werkzeug, Befehl bzw. Testname, Umgebung, Ergebnis und Belegpfad.

## Änderungen ausserhalb des Frontends
Nur tatsächlich erfolgte Änderungen; sonst nach Diff-Prüfung „keine“.

## Offene Punkte / Blocker
Auswirkung und fehlende Voraussetzung. Nicht ausgeführte Prüfungen nennen.
```

## 16. Ausführungsauftrag

Beginne jetzt mit Repository- und UI-Inventar, konkreten Befunden und dem Start der vorhandenen Testumgebung. Implementiere danach die gemeinsamen Grundlagen, prüfe Referenzen pro Seitentyp und migriere sämtliche vorhandenen Tools und UI-Routen.

**Nicht nur eine Seite modernisieren. Nicht nur Farben austauschen. Nicht nur eine Liste von Empfehlungen liefern. Einen gemeinsamen, getesteten Designstandard im bestehenden Flask-/Tabler-Projekt umsetzen und die vollständige Abdeckung nachweisen.**

---

## Technische Quellen

Die Quellen erläutern Werkzeuge und technische Prüfanforderungen. Die konkrete Palette, Typografie und Layoutmasse oben sind eigenständige Projektentscheidungen. Für die Implementierung die tatsächlich installierten Versionen berücksichtigen.

- **[S1] Tabler: Customize Tabler.** Theme-Anpassung und Primärfarbe. `https://docs.tabler.io/ui/getting-started/customize`
- **[S2] Bootstrap: CSS variables / Buttons.** Globale und komponentenbezogene Variablen. `https://getbootstrap.com/docs/5.3/customize/css-variables/` und `https://getbootstrap.com/docs/5.3/components/buttons/`
- **[S3] W3C: Understanding SC 1.4.3, Contrast (Minimum).** Kontrastberechnung und Schwellenwerte. `https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html`
- **[S4] Playwright: Visual comparisons.** Screenshot-Vergleiche und Umgebungsabhängigkeit. `https://playwright.dev/docs/test-snapshots`
- **[S5] Playwright: Accessibility testing.** axe-Integration und Grenzen automatisierter Prüfungen. `https://playwright.dev/docs/accessibility-testing`
- **[S6] Flask: Testing Flask Applications.** Testclient und Testaufbau. `https://flask.palletsprojects.com/en/stable/testing/`
- **[S7] W3C: Understanding SC 1.4.11, Non-text Contrast.** Kontrast notwendiger UI-Informationen. `https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html`
- **[S8] Flask: Templates.** Jinja-Einbindung und Escaping. `https://flask.palletsprojects.com/en/stable/templating/`
- **[S9] W3C: Understanding SC 2.5.8, Target Size (Minimum).** Mindestzielgrössen und Ausnahmen. `https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html`
- **[S10] OpenAI: Custom instructions with AGENTS.md.** Projektanweisungen für Codex. `https://developers.openai.com/codex/guides/agents-md/`
- **[S11] Anthropic: How Claude remembers your project.** Projektanweisungen über CLAUDE.md. `https://code.claude.com/docs/en/memory`
