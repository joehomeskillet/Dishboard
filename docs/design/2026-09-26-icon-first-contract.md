# Icon-first: Komponentenvertrag, Icon-Semantik und Testauswirkung

Stand: 26. September 2026. WP1b, Analyse; Grundlage für WP2, keine Produktmigration.
Basis: `42c85fef319c00262abbbfbcd2c4e029d01c9faa`.
Worktree: `/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-contract-0926`;
Branch: `docs/icon-first-contract-0926`.

## 1. Geltung, Belege und Messmethode

Vorrang hat `docs/design/2026-09-26-icon-first-simplification-spec.md` (S):
Standardaktionen icon-only (S:156), Namen/Tooltip (S:181–190), Textausnahmen (S:191–200),
Zustände (S:202–210), Semantik (S:212–246), Tokens (S:250–270), Status (S:280–313),
Toolbar/Details (S:319–347), Erhalt der Ausführung (S:541–559), Abnahme (S:583–620).
Das ältere Manifest wird durch diese Präzisierung in den unten aufgeführten Punkten
ersetzt. Dieses Dokument beschreibt deren konkrete Integration, kein zweites Designsystem.

Die bereitgestellte Spezifikation war bei Arbeitsbeginn untracked. Sie wird nicht
mitcommittet. Einziger neuer Repo-Inhalt dieses WP ist dieses Dokument. Keine
Änderung von Templates, CSS, Python/JS, Tests, Baselines, AGENTS.md oder CLAUDE.md.
Keine Datenänderung, keine Veröffentlichung, kein Browser-/Live-Nachweis.

Belegkürzel, jeweils mit repositoryrelativem Vollpfad:

| Kürzel | Datei |
|---|---|
| M | `docs/design/2026-09-09-unified-ui-design-system.md` |
| A | `reference_scaffold/cafeteria/templates/admin/_macros.html` |
| U | `reference_scaffold/cafeteria/templates/ui/_semantic.html` |
| R | `reference_scaffold/cafeteria/ui/semantic_registry.json` |
| F | `reference_scaffold/cafeteria/ui/icon_fallbacks.json` |
| I | `reference_scaffold/cafeteria/static/vendor/tabler-icons/tabler-icons.svg` |
| T | `reference_scaffold/cafeteria/static/tokens.css` |
| C | `reference_scaffold/cafeteria/static/admin-tabler.css` |
| SC | `reference_scaffold/cafeteria/static/ui-semantic.css` |
| JS | `reference_scaffold/cafeteria/static/admin.js` |
| V | `reference_scaffold/cafeteria/ui/semantics.py` |
| UI | `reference_scaffold/cafeteria/ui/__init__.py` |
| L | `reference_scaffold/cafeteria/ui/i18n.py` |
| DE / EN | `reference_scaffold/cafeteria/translations/de.json` / `en.json` |
| Tests | `reference_scaffold/tests/` |

Makrozahlen sind **statische Trefferzeilen**, keine gerenderten Instanzen: rekursives
`rtk grep -rnE '\bNAME\(' reference_scaffold/cafeteria/templates`, danach
Definitionszeilen mit `macro NAME(` herausnehmen. Interne Aufrufe zählen mit,
Imports ohne Aufruf nicht. Mehrere Aufrufe auf einer Zeile zählen einmal.
Aliase wie `render_label` sind nicht heimlich dem Original zugerechnet.
CSS-Zahlen sind `rtk grep -rnF MUSTER reference_scaffold/cafeteria/templates`;
Definition/Verwendung der Klasse im gemeinsamen Template zählt mit. Teilstring
`admin-table` schliesst `admin-table--stack` ein. Treffer mit Exit 1 sind null.
Zählungen wurden gegen direkt gelesene Quellen geprüft; keine Laufzeit-Hochrechnung.

Testauswirkung wurde über Quellensuche und Python-AST ermittelt, nicht durch
Ausführung: Textselektoren/-asserts, HTML-Stringprüfungen, anschließend Klassifikation
der tatsächlichen Kontrollziele. Abschnitt 5 benennt Zähleinheit und Grenzen.

## 2. Gemeinsamer Bestand

### 2.1 Makros und Helper

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Die folgenden Menü-/Erstes-Item-/Zwei-Aktionen-Befunde bleiben historische Bestandsaufnahme. Als Standard sind sie abgelöst; alle verfügbaren Befehle werden direkt gerendert.

Signaturen hier sind IST, einschließlich Defaults; Änderungen folgen in Abschnitt 4.

| Datei:Zeile | Signatur | Trefferzeilen | Varianten / Befund |
|---|---|---:|---|
| A:3 | `icon(name, class='', label=none)` | 212 | Lokales Sprite; ohne Label dekorativ, `focusable=false`. Kein zweiter SVG-Renderer nötig. |
| A:7 | `icon_link(href, label)` | 0 | Bereits icon-only, fest auf `actions.edit`, volle Breite, Tabler-Tooltip; durch Tests weiterhin abgedeckt. |
| U:5 | `sem_icon(key)` | 27 | Registry-Auflösung; Food-Symbole bleiben eigener fachlicher Zweig. |
| U:13 | `icon_label(key)` | 136 | Icon + sichtbarer Text; für Navigation, Status und Menüeinträge weiter nötig. Nicht global verstecken. |
| U:19 | `action_contract_error(message)` | 11 | Fehler via `sem`, kein stiller Fallback. |
| U:21 | `action_attrs(attrs)` | 1 | Allowlist, Escaping, Boolean-Attribute, `noopener`; nicht durch freie HTML-Attribute ersetzen. |
| U:48 | `icon_button(key, href=none, name=none, value=none, icon_only=false, type='submit', id=none, form=none, consequence_key=none, size='default', text=none, aria_label=none, title=none, class='', emphasis=none, attrs=none)` | 128 | Default Text; Primär-icon-only verboten U:55; Tooltip nur `title` U:64. |
| U:99 | `action_menu(items)` | 1 | Ein Aufruf in `row_actions`; rendert auch leer. `details/summary`, sichtbares „Mehr“, kein eigener lokalisierter Objektname. |
| U:110 | `row_actions(items)` | 3 | Erstes Item direkt, Rest im Menü; Zwei-Aktionen-Budget vorhanden. Drei weitere gleichnamige Treffer gehören zum Rezeptadapter unten. |
| A:346 | `actions(primary=none, secondary=none, class='')` | 2 | Legacy-HTML-/Mapping-Renderer plus Alias `render_actions`; freie Icon-/Labelwahl, eigene Link/Button-Ausgabe. |
| A:475 | `form_footer(primary, cancel_url, rare=none, sticky=false, form_id=none, secondary=none, danger=none)` | 3 | Separates Mehr-Menü und festes „Abbrechen“; unterstützt native Formzuordnung. |
| U:124 | `confirm_dialog(key, consequence_key, confirm_key, id='semantic-confirm', open=false, name=none, value=none, form=none)` | 0 | Wiederholte Default-ID möglich; expliziter Bestätigungstext muss erhalten bleiben. |
| A:79 | `hint(text, id, mode='tooltip')` | 38 | `inline`, `tooltip`/native Details, `dialog`; nicht gleichbedeutend mit dem Button-Tooltip. Sicherheitsangaben bleiben inline. |
| A:487 | `disclosure_section(title=none, id=none, open=false, has_content=false, has_error=false)` | 33 | Öffnet bei Inhalt/Fehler; generisches Chevron derzeit ohne zustandsabhängige Auswahl. |
| A:460 | `list_row(name=none, subtitle=none, state=none, action=none, markings=none, overflow=0, more_actions=none, primary=none, secondary=none, meta=none, status=none, actions=none)` | 9 | Alte/neue Slotnamen; eigener Mehr-Renderer; Status und Aktionshülle auch ohne Inhalt. |
| A:454 | `empty_value()` | 9 | „—“; nicht für unbekannte Bestände missbrauchen. Null bleibt echter Wert. |
| A:456 | `sort_header(label, key, current, direction, url)` | 0 | Tabelle, `scope=col`, `aria-sort`, sichtbarer fachlicher Spaltentitel. |
| A:218 | `label(text, variant='neutral', icon=none, detail=none, semantic_key=none, status=none, class='')` | 34 | Kanonischer Badge; Detail zusätzlich visuell verborgen. Alias `render_label`. |
| A:224 | `status_badge(value, mapping=none, label=none, detail=none)` | 4 | Legacy-State-/Farbmapping delegiert an `render_label`; feste deutsche State-Namen. |
| A:270 | `status(value, label=none, mapping=none)` | 2 | Kompatibilitätsadapter zu `status_badge`. |
| U:68 | `status_badge_sem(key, detail=none)` | 9 | Registry + Übersetzung + `label`; bereits gemeinsame Darstellung. |
| A:11 | `page_header(title, description=none, breadcrumbs=none, actions=none, pretitle=none, status_items=[])` | 53 | Caller oder actions; bis fünf nichtleere Statuswerte, kein Budget für hineingereichtes Aktions-HTML. |
| U:136 | `status_bar(title_key, items=[], description_key=none, actions=none)` | 0 | Übersetzungsadapter auf `page_header`, keine neue Status-Komponente nötig. |
| A:443 | `filter_bar(action, search_name='q', search_value='', filters=none, more_filters=none, active=false, reset_url=none, id='filters', maxlength=none, describedby=none, loading=none, open=false)` | 1 | GET; „Weitere Filter“ mit Suchicon plus separater Filter-Submit; Reset nur bei aktivem Filter. |
| U:146 | `filter_bar_sem(action, search_name='q', search_value='', filters=none, more_filters=none, active=false, reset_url=none, id='filters', maxlength=none, describedby=none, loading=none, open=false)` | 3 | Delegiert komplett an A:443; Suchlabel noch deutsch. |
| A:382 | `profile_tabs(links, current)` | 0 | Cafeteria/Patienten als Text; harte Labels. Nicht zu Icons umwandeln. |
| A:296 | `pagination(page, has_next=none, prev_url=none, next_url=none, label='Pagination', has_prev=none, total_pages=none, total_items=none)` | 12 | Page-Objekt oder skalare Parameter; Navigation mit Zurück/Weiter, deaktiviert als span. |
| A:278 | `empty_state(kind, title, text, action=none, semantic_key=none, icon_name=none)` | 22 | Caller-/Aktionsslot; keine erfundene Aktion bei fehlenden Rechten. |
| U:120 | `empty_state_sem(key, description_key=none, action_key=none, href=none)` | 3 | Delegiert an empty_state und icon_button. |

Formlabels bleiben Text: `field(...)` A:98 und gleichnamiger Rezeptadapter haben
zusammen 44 Treffer, `select(...)` A:110 und Rezeptadapter zusammen 13;
`option_detail_group(...)` A:398 hat 2. Diese sind fachliche Controls,
keine Kandidaten für pauschales Icon-only. `diet_icon`, `allergen_icon`,
`symbol_row` U:74/76/85 bleiben lesbare Fachkennzeichnung.

Python-Vertrag: `sem(key: str)` UI:12, `require_icon_only(key: str,
icon_only: bool=False)` UI:19 und `require_consequence(key: str,
consequence_key: str|None)` UI:26 sind registrierte Jinja-Globals (UI:45).
`load_registry(path=ROOT/'semantic_registry.json')` V:67 prüft Sprite und Fallback;
`validate_locales(registry, locales)` V:112 verbietet derzeit jede zusätzliche
Locale-Nachricht ausser den drei Registry-Suffixen. `translate(key, locale=None,
**params)` L:94 nutzt `Translator.translate` L:69, maskiert das gesamte Ergebnis
einschliesslich Markup-Parametern (L:88–91). Placeholder-Symmetrie existiert schon
(L:20–29,45–59). Kein neues Übersetzungssystem erforderlich.
Grep-Aufrufzeilen in cafeteria (Definitionen ausgeschlossen): sem 47,
require_icon_only 2, require_consequence 3, load_registry 1, sprite_icons 1,
validate_locales 1. Der Jinja-Alias t und gleichnamige fremde translate-Methoden
sind keine direkte Python-Callerzählung für L:94.

Zusätzliche fachliche Adapter/Varianten; Pfade hier relativ zu
`reference_scaffold/cafeteria/templates/admin/`, Zählung wie oben:

| Datei:Zeile | Signatur | Trefferzeilen | Abgrenzung |
|---|---|---:|---|
| `_rezepte_fields.html:14` | `row_button(kind, operation, index, label, symbol, focus=false, aria_label=none)` | 6 | Eigener Submitrenderer mit formaction/formnovalidate, freiem Icon und Text. |
| `_rezepte_fields.html:17` | `row_actions(kind, index, count, label)` | 3 | Namenskollision mit U:110, andere Signatur. Aufrufe rezepte_editor.html:56,78,99; eigener Überlauf-/Reihenfolgenvertrag. |
| `_week_controls.html:42` | `overview_header(heading, description)` | 2 | Kopf, Status, Wochenaktionen und Veröffentlichung. |
| `_area_tabs.html:112` | `render_tabs()` | 0 | Vorhandener Navigationsadapter; Text bleibt. |
| `kuechenkalender.html:47` | `day_plan_btn(cell)` | 2 | Lokaler Kalenderzugang. |
| `kuechenkalender.html:52` | `day_body(cell)` | 2 | Kalenderzelleninhalt, keine Standardzeile erzwingen. |
| `einkaufsliste.html:47` | `line_status(line)` | 1 | Fachlicher Statusadapter. |
| `menu_collection.html:20` | `review_status(row)` | 2 | Geprüft/offen, keine Publikationsaktion. |
| `menu_editor.html:36` | `mode_summary(key, title, badge_id)` | 3 | Detail-/Formabschnitt mit Zustand. |
| `gerichtvorlagen.html:8` | `accompaniment_state(item, icon_visible=true)` | 1 | Beilagenzustand, Text erhalten. |
| `gerichtvorlagen.html:13` | `recipe_state(item)` | 2 | Rezeptbindung. |
| `rezepte_ansicht.html:1` | `template_links(links, recipe_id, can_create)` | 2 | Navigations-/Erstellaktionen mit eigenen Rechten. |
| `rezepte_ansicht.html:7` | `print_reference(template)` | 2 | Vorlagen-/Drucknavigation. |
| `grundlagen.html:26` | `status_summary()` | 3 | Versions-/Statuskontext. |
| `grundlagen.html:31` | `status_actions()` | 3 | Archivieren/Reaktivieren mit eigenem Formular/Folgetext. |
| `grundlagen.html:40` | `section_summary(title, symbol='chevron-right')` | 9 | Lokaler Detailtrigger mit zusätzlichem Chevron. |

Aliase `render_actions` A:453, `render_label` A:222 und `render_icon` A:217
haben jeweils eine weitere Aufrufzeile. Gleichnamige `field`/`select` in
`_rezepte_fields.html:2,8` sind andere Signaturen, kein Beweis für Nutzung des
zentralen Formularmakros. Fachliche Partial-Adapter sind Migrationsverbraucher;
WP2 erzeugt dafür keine Kopien. Bei Delegation zwischen U und A lokale
Makro-Imports verwenden, keinen zyklischen Top-Level-Import hinzufügen.


### 2.2 CSS, Tooltip, Zustände und Duplikate

| Muster / Quelle | Template-Trefferzeilen | IST und Auswirkung |
|---|---:|---|
| `ui-sem-control`, SC:17–44 | 21 | Größe über `--app-button-size`; quadratisch nur icon-only. Fokus vorhanden. |
| `admin-row-actions`, SC:38 | Makro U:110 | Flex, rechtsbündig; CSS und Makro gemeinsam weiterverwenden. |
| `admin-list-row`, C:503 | 1 | Zentral A:463. Aufrufe via list_row oben gezählt; keine Behauptung „nur eine Liste“. |
| `admin-table--stack`, C:532,585 | 24 | Tabelle bleibt Tabelle; schmal CSS-Grid/Block, `data-label`; Semantik und a11y im Browser prüfen. |
| `admin-table`, C:532–544 | 46 | Enthält Stack-Treffer; nicht zu 24 addieren. |
| `admin-compact-actions`, C:435–442 | 9 | Zweite Überlauf-Familie: A:470/478, lokale Editor-Templates. |
| `admin-compact-details`, C:433–439 | 30 | Detail-/Filterfamilie; 48-px-Minimum auch für summary. |
| `admin-filter-bar`, C:489–502 | 9 | Acht weitere Treffer neben zentraler Form A:444; lokale Renderer nicht per CSS allein vereinheitlichen. |
| `admin-compact-toolbar`, C:443 | 4 | Separate Toolbar; kein zweiter Such-Stack nötig. |
| `profile-tabs`, A:383 | 2 | Makro und lokales Muster; fachliche Textnavigation erhalten. |
| `admin-label`, A:220; C:665ff | 1 | Zentraler Renderer; semantische/Legacy-Adapter oben. |
| `admin-statusbar`, A:24–29,68; C:632 | 6 | Zählt Quellzeilen, nicht Anzahl Statuschips. |
| `recipe-list-row` / `recipe-card`, C:550 | 1 / 2 | Legacy-Listen-/Kartenklassen; Typografieadapter bereits vorhanden, Container noch nicht dadurch konsolidiert. |
| `data-admin-icon-action`, JS:61 | 8 | Einige manuelle Links + icon_link; icon_button ist noch nicht angeschlossen. |
| `data-bs-toggle="dropdown"` | 0 | Exakter literaler Treffer; dynamische `attrs`-Mappings sind damit nicht ausgeschlossen. |

`base_tabler.html:9–14,37–39` lädt Tokens, Tabler, admin-tabler.css,
ui-semantic.css und Tabler-JS vor admin.js. Bestehende Reihenfolge erhalten.

Tooltip-Ansatz existiert: JS:60–73 hält Tabler-Instanz, erlaubt Pointer-Hover auf
Tooltip; JS:622–633 schliesst mit Escape. Er umfasst nur initial gefundene
`[data-admin-icon-action]`, nicht alle semantischen Controls oder spätere DOM-Knoten.
A:8 setzt zusätzlich `data-bs-toggle=tooltip` und `data-bs-title`; U:64 nur
`title`. Das ist eine Integrationslücke, kein Grund für zweite Tooltip-Bibliothek.

Native Ladeanzeige JS:5–35 berücksichtigt Serialization, setzt disabled/aria-busy
und stellt auf pageshow wieder her; gewählt wird derzeit der erste aktive
`button.btn-primary`, nicht `event.submitter`. Sperre wird verzögert gesetzt.
JS:36–38 verhindert nur Default-Klick auf deaktivierte Links, nicht sämtliche
Button-/Custom-Handler. JS:119/126 überschreibt bei Dirty-State sogar `textContent`
und zerstört Icons. Diese Stellen müssen zum Zustandsvertrag gehören.

Escape/Fokusrückgabe für Dropdowns und Details existiert JS:634–655. Der globale
Fallback schliesst gegebenenfalls alle offenen Details; nicht blind auf editierte
Datensatzdetails ausweiten. Bestehende Werte dürfen dabei nicht verloren gehen.

## 3. Icon-Semantik gegen S §6

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** `actions.more`/dots ist als normaler Aktionszugang abgelöst. Der historische Registry-Befund bleibt erhalten; keine generischen Aktionssammler rendern.

147 Symbole im lokalen Sprite I:3–149. Die folgende Tabelle prüft die tatsächlich
ausgelieferte Datei, nicht eine vermutete externe Tabler-Version. Heute liegen
alle hier vorhandenen Registry-Icons direkt im Sprite. F:2–24 enthält nur
crab/knife/oven/peanut/recipe/shell; kein world-upload-Fallback.

| Registry-Schlüssel / Beleg | Heutiges Icon | Ziel-Tabler-Icon | Lokal / Fallback | Konflikt / Entscheidung |
|---|---|---|---|---|
| actions.add R:3; actions.add_existing R:14 | plus / circle-plus | plus | ja I:113 | Gleiche Hinzufügen-Grundaktion vereinheitlichen; Labels dürfen „Anlegen“/„Hinzufügen“ bleiben. Keine neuen Keys. |
| actions.edit R:58 | edit | pencil | ja I:108 | Bewusste Konsolidierung; edit I:61 existiert ebenfalls. Nur eine kanonische Bearbeiten-Zuordnung. |
| actions.save R:69 | device-floppy | device-floppy | ja I:57 | Bereits korrekt; keine neue Speichern-Semantik. |
| actions.cancel R:91; actions.close R:102 | x | x | ja I:149 | Absichtlich gleiches Icon, verschiedene exakte Namen. |
| actions.open R:179 | chevron-right | arrow-right | ja I:12 | Heute mit Detail-Aufklappen vermischt. Navigation von Disclosure trennen. |
| ui.disclosure.details R:2269; ui.disclosure.more_options R:2280 | chevron-right | chevron-right geschlossen / chevron-down offen | ja I:38/36 | Vorhandene Keys; Zustand zentral auswählen, keine per-Seite Icons. |
| view.expand R:773; view.collapse R:784 | chevron-down / chevron-up | chevron-right / chevron-down | ja I:38/36 | Einheitliche Zustandsanzeige: expand-Trigger geschlossen rechts, collapse-Trigger offen unten. |
| actions.more R:168 | dots | dots | ja I:59 | Vorhanden; Text am geschlossenen Trigger entfällt. |
| view.search R:674 | search | search | ja I:121 | Vorhanden; nicht neue actions.search erfinden. |
| view.filter R:685 | filter | filter | ja I:71 | Filteröffnung statt paralleler „Weitere Filter“-Suche A:447. |
| view.reset R:696 | filter-off | filter-off | ja I:72 | Nur Filter-Reset; kein allgemeiner fachlicher Reset. |
| actions.copy R:146 | copy | copy | ja I:54 | Duplizieren/Kopieren gleicher Vorgang, kontextgenauer Locale-Name. |
| actions.archive R:124 | archive | archive | ja I:6 | Vorhanden; Bestätigung/Rechte bleiben. |
| actions.delete R:113 | trash | trash | ja I:136 | Vorhanden; Danger-/Konsequenzschutz erhalten. |
| actions.preview R:245 | eye | eye | ja I:64 | Nicht als Öffnen-Ersatz für beliebige Detailseiten. |
| **actions.plan (neu)** | Kein Aktionskey; actions.open missbraucht | calendar-plus | ja I:30 | Reale Lücke: templates/admin/gerichtvorlagen.html:43 zeigt „Einplanen“ mit actions.open. |
| **actions.review (neu)** | actions.confirm → check | list-check | ja I:91 | Reale Lücke: templates/admin/_week_controls.html:60,77,80. Status review.* beschreibt Zustand, keine Aktion. |
| **actions.publish (neu)** | actions.confirm → check | world-upload | **nein**; neuer Fallback auf send I:123 | Reale Lücke: templates/admin/_week_controls.html:65,74,118,149. Ein zentraler Eintrag `"world-upload":{"icon":"send","icon_only_allowed":true}`; keine zweite Symbolsammlung. |
| actions.import R:289; actions.upload R:278 | file-import / upload | upload | ja I:138 | Imports mit gleicher Upload-Bedeutung konsolidieren; Import-Ausführung weiterhin eigener Key/Name. |
| actions.export R:300; actions.download R:267 | file-export / download | download | ja I:60 | Gleiche Richtung; Ziel/Formate im Namen erhalten. |
| actions.print R:256 | printer | printer | ja I:114 | Vorhanden. |
| time.previous R:850; time.next R:861 | chevron-left / chevron-right | unverändert | ja I:37/38 | Datumsnavigation existiert. time.next darf icon-only nicht mehr aufgrund primary verbieten. |
| actions.back R:190; actions.next R:201 | arrow-left / arrow-right | unverändert | ja I:11/12 | Workflow-/Rücknavigation nicht mit Zeitnavigation gleichsetzen. |
| actions.confirm R:80; actions.apply R:36 | check / check | check für echte Bestätigung/Übernahme | ja I:34 | Nicht für Prüfen/Veröffentlichen weiterverwenden. Fachliche Unterschiede im lokalisierten Namen. |

Nur drei neue Aktionskeys, ein tatsächlich fehlendes Zielicon mit zentralem
Fallback. Keine neuen Keys für Speichern, Suche, Filter, Reset, Details oder Zeitnavigation.

Status-Kollisionen sind nicht automatisch Fehler: R:333/344/388/586 verwenden
circle-check für OK/Erfolgreich/Aktiv/Geprüft, R:432/630 checks für Erledigt/Bereit;
R:641 world-check bezeichnet **veröffentlichten Zustand**. Die sichtbaren
Statusnamen bleiben gemäß S:280–311. `status.readonly` R:498 und Vorschau teilen
eye, jedoch nicht Rolle. `order.shopping_list` R:1345 und
`navigation.shopping` R:2005 nutzen list-check für dieselbe fachliche Navigation;
actions.review bekommt seinen eigenen Namen und Kontext. Keinen Zustand in eine
Ausführungsaktion umdeuten.

DE/EN:74–76 enthalten bereits Bearbeiten/Edit; DE/EN:89–91 Weiter/Next.
Heute sind Aktionslabel/aria/tooltip überwiegend identisch. Objektbezug ist eine
Locale-Lücke, kein neues Icon. Für Publizieren muss auch „Erneut veröffentlichen“
bzw. „Änderungen veröffentlichen“ erhalten werden (Tests/test_ui_semantics.py:46–52);
kein generisches „Bestätigen“ als Rückschritt.

## 4. Sollvertrag für WP2

### 4.1 Kompatibilität und Signaturen

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Menü-Wrapper, `menu_item` und Menütext begründen keinen generischen Aktionssammler mehr. Altadapter dürfen nur direkte Symbolgruppen ausgeben; Kontext-, Attribut-, Namens-, Zustands- und Formularverträge bleiben erhalten.

Alle bisherigen Positionsparameter bleiben in gleicher Reihenfolge. Neue Parameter
werden angehängt. „Rückwärtskompatibel“ meint Aufrufbarkeit, DOM-Hooks,
Link-/Submit-Vertrag und fachliche Namen; **nicht bytegleiches HTML oder unveränderte
sichtbare Beschriftung**. Gerade diese Darstellung ändert S §5 ausdrücklich.
Kein seitenabhängiger Feature-Schalter.

~~~jinja
icon_button(key, href=none, name=none, value=none, icon_only=true,
            type='submit', id=none, form=none, consequence_key=none,
            size='default', text=none, aria_label=none, title=none,
            class='', emphasis=none, attrs=none,
            object_name=none, text_exception=none,
            disabled=false, disabled_reason_id=none, busy=false)

action_menu(items, id=none, object_name=none)
row_actions(items, id=none, object_name=none)
disclosure_section(title=none, id=none, open=false, has_content=false,
                   has_error=false, object_name=none, inline=false)
list_row(name=none, subtitle=none, state=none, action=none, markings=none,
         overflow=0, more_actions=none, primary=none, secondary=none,
         meta=none, status=none, actions=none,
         details=none, id=none, status_context=none)
filter_bar(action, search_name='q', search_value='', filters=none,
           more_filters=none, active=false, reset_url=none, id='filters',
           maxlength=none, describedby=none, loading=none, open=false,
           profile=none, active_count=0)
filter_bar_sem(action, search_name='q', search_value='', filters=none,
               more_filters=none, active=false, reset_url=none, id='filters',
               maxlength=none, describedby=none, loading=none, open=false,
               profile=none, active_count=0)
~~~

`page_header`, `label`, `status_badge_sem`, `status_badge`, `profile_tabs`,
`form_footer`, `actions` und `confirm_dialog` behalten ihre IST-Signaturen.
Ihre internen Controls delegieren zum gemeinsamen Renderer; keine dritte
Button-Implementierung. Legacy-HTML-Slots bleiben aufrufbar, erhalten aber keinen
automatischen „migriert“-Status. `icon_link(href,label)` bleibt Wrapper für
actions.edit mit dem bestehenden vollständigen Namen.

| Bisheriger Parameter | Weiterleben |
|---|---|
| text= | Bleibt akzeptierter kurzer Legacy-Aktionsname, maskiert. Allein **keine** Textausnahme. Ohne aria_label/object_name dient er auch als alter zugänglicher Name; damit bleiben zielspezifische Namen erhalten. Neue Aufrufer verwenden Registry/Locale statt freie deutsche Texte. |
| icon_only= | Default true. true bedeutet icon-only; altes explizites false allein erteilt keine Ausnahme und wird im Standardkontext auf icon-only normalisiert. Für beschriftete Darstellung ist text_exception nötig. Zulässige Ausnahme bestimmt Darstellung auch in Wrappern; nicht über CSS verbergen. |
| aria_label= | Bestehender vollständiger Name bleibt akzeptiert und exakt erhalten. Kein automatisches deutsches „Label: Name“. Neue Objektaufrufe nutzen object_name und Locale-Platzhalter. Bei Textausnahme muss sichtbares Label im Namen enthalten sein; dafür vollständige Übersetzung liefern. |
| emphasis= | none nutzt Registry; primary/secondary/danger bleiben gültig. Primary bestimmt Gewichtung, nicht Textpflicht. Danger darf nicht neutralisiert werden. |
| attrs= | Mapping-Allowlist U:21–46 bleibt; data-* Hooks, aria-Beziehungen und native Formularattribute unverändert. Kein onclick/style/raw HTML. Zustandsattribute gehören in typed Parameter; widersprüchliche doppelte Werte werden abgewiesen. |
| title= | Bestehender Text wird als gemeinsamer Tooltip-Inhalt übernommen, maskiert; optionales title allein ist kein Nachweis. Tooltip-Initialisierung muss native Doppel-Tooltips vermeiden. |
| size= | default bleibt Standard; large bleibt kompatibler expliziter Sonderfall, kein Standard für Listen. Keine neue Dichteauswahl. |
| class= | Bestehende Selektoren/Hookklassen bleiben. Keine Umgehung von Icon, Größe, Gewichtung oder Textausnahme; dropdown-item erhält Text nur durch Menü-Wrapper. |
| consequence_key= | Bleibt verpflichtend für destruktive Ausführung; verständlicher Folgetext außerhalb des Iconquadrats, in Menü/Bestätigung sichtbar. Kein Tooltip als einzige Warnung. |
| href/type/name/value/form/id | Unverändert durchreichen; href → Link, sonst Button. Default type=submit bleibt wegen alter Formulare erhalten; reine UI-Toggler verwenden ausdrücklich type=button. |

`text_exception` ist feste Enum: `none`, `menu_item`, `confirmation`,
`navigation`, `status_warning`. Kein beliebiger Begründungstext.
`menu_item` setzt nur action_menu, `confirmation` nur bestehender
Bestätigungsdialog; `navigation` nur fachliche Navigation/Profilauswahl, nicht
„Öffnen“ als Zeilenaktion. `status_warning` nur tatsächlich erklärungsbedürftiger
Zustand gemäß S:191–200. Formlabels/Inhalte bleiben außerhalb icon_button.
Wrapper müssen Ausnahmen explizit setzen, nicht aus Klassen oder Bildschirmbreite
erraten. Unbekannte Enumwerte werden abgewiesen.

### 4.2 Lokalisierter Name, Escaping, Tooltip

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** „Weitere Aktionen für {object}“ ist als normaler Aktionszugang abgelöst. Historische Locale-Schlüssel dürfen bestehen; direkt gerenderte Befehle behalten eindeutige lokalisierte Namen und Tooltips.

Priorität des Namens: vorhandenes explizites `aria_label` → übersetztes
Objektmuster bei `object_name` → bestehendes `text` → `t(item.aria_key)`.
Keine Verkettung „Objekt + bearbeiten“, kein HTML im Tooltip. SVG bleibt
`aria-hidden=true, focusable=false` (A:4).

Konkrete Locale-Erweiterung für bekannte Registry-Schlüssel:
optionale, zusammengehörige `.aria_object` und `.tooltip_object`.
Beispiel DE `actions.edit.aria_object = "{object} bearbeiten"`,
EN `"Edit {object}"`; DE `actions.more.aria_object =
"Weitere Aktionen für {object}"`, EN `"More actions for {object}"`.
Aufruf `t(key ~ '.aria_object', object=object_name)` nutzt vorhandenes L:69.
Objektname nur String, kein Markup-Vertrauen, keine |safe-Umgehung.

V:112 muss die erlaubten Suffixe prüfen: nur bekannte Registry-Keys, beide
Objektsuffixe gemeinsam, gleiche Placeholder-Menge `{object}` und vollständige
DE/EN-Abdeckung. Bestehende drei Nachrichten bleiben unverändert gültig;
keine pauschale Abschaltung der orphan-Prüfung. Fehlendes Objektmuster bei
angefordertem object_name ist im Test ein konkreter Vertragsfehler.
Generische Filter-/Suchlabels werden ebenfalls über die bestehende Registry
lokalisiert, nicht in Templates zusammengesetzt.

Ein vorhandener clientseitiger Initializer in JS verbindet alle semantischen
Iconcontrols mit Tabler-Tooltip, auch nach dynamischem Einfügen. Kein neuer
Dependency-/Plugin-Stack. Hover **und** Fokus öffnen; Escape schliesst ohne
Aktionsausführung, solange Fokus/Hover unverändert nicht sofort wieder öffnen;
Zeiger kann auf Tooltip wechseln; Tooltip bleibt bis Verlassen beider Flächen,
Fokuswechsel oder explizitem Schliessen. Keine feste kurze Ablaufzeit.
`aria-describedby` vorhandener Hilfen bleibt neben Tooltip-ID erhalten.
Textinhalt escaped, kein html=true mit Datensatzwerten.

Ohne JS bleiben native Links, Formulare und Details bedienbar, mit Namen und
sichtbaren Sperrgründen. Native title kann Fallback sein, zählt aber nicht als
Erfüllung des gemeinsamen Tooltip-Gates S UI-08. Touch braucht für seltene
Fachaktionen sichtbaren Menütext, keinen Langdruck.

### 4.3 Deaktiviert, laufend, Fokus und Ausführung

- `disabled=true` auf Button: echtes disabled. Link: aria-disabled, kein
  ausführbares Navigationsziel im deaktivierten Renderzustand, dafür explizit
  role=link und Tastaturfokus erhalten; ursprüngliches
  Ziel nur intern für gezieltes Reaktivieren erhalten. Eine alleinige
  aria-disabled-Annotation reicht nicht.
- Legacy `attrs.disabled` bleibt Boolean; für Links nach gleicher Sperrregel
  normalisieren. JS sperrt disabled/busy vor direkten und delegierten Handlern
  für Pointer/Klick, Enter/Space, Formular-Submit und native Navigation.
  Native Links behalten außerhalb Sperre Enter-Verhalten; keine künstliche
  Space-Aktivierung für Links.
- `disabled_reason_id` verweist auf sichtbare, vorhandene kontextuelle Erklärung;
  mit aria-describedby verbinden. Native disabled muss nicht fokussierbar
  gemacht werden, damit der Grund erreichbar ist. Keine zusätzliche Hover-Hürde.
- `busy=true`: gleicher Name, gleiche Abmessungen, aria-busy=true,
  SVG/ruhiger Fortschritt in reserviertem 20-px-Platz. Keine neue Textlänge und
  kein zusätzlicher Spinner außerhalb des Quadrats.
- Den tatsächlichen `event.submitter` merken. Reentrancy-Sperre synchron setzen,
  erfolgreiche Controls inklusive name/value/formaction erst serialisieren,
  native Deaktivierung danach; ungültige/abgebrochene Vorgänge entsperren.
  pageshow stellt ursprüngliche Zustände wieder her. Kein pauschales erstes
  btn-primary wählen. JS:5–35 ist Ausgangspunkt, noch kein erfüllter Vertrag.
- Dirty-State JS:119/126 darf weder SVG noch zugänglichen Aktionsnamen ersetzen.
  „Zuerst speichern“ gehört in sichtbare verknüpfte Erklärung; Icon/Name bleiben.
- Bestehende CSRF-/CAS-Felder, name/value-Reihenfolge, form-Zuordnung, HTTP-Methode,
  formaction, formnovalidate, URLs, data-* Events und Rechte unverändert.
  Speichern/Löschen/Publizieren werden nicht zu GET. Serverprüfung bleibt maßgeblich.

### 4.4 Überlauf, Zeilen und Details

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Erstes-Item-plus-dots, Menü-Kurztext, Menü-Öffnen/Schliessen und Überlauf-Adapter für `more_actions`/`form_footer.rare` sind abgelöst. Alle verfügbaren Items erscheinen direkt, schmal mit sichtbarem Umbruch. Leere Gruppen entfallen; Fachdetails, Status, native Semantik, Fokus und Schutzschritte bleiben erhalten.

`action_menu([])` rendert **nichts**; `row_actions([])` ebenfalls keine leere
Aktionshülle. Nach erlaubnisgefilterter Eingabe zeigt row_actions höchstens das
erste Item direkt, bei weiteren Items genau einen dots-Auslöser.
Items behalten alle bisherigen Felder und reichen neue typed Zustands-/Kontextfelder
an icon_button durch. Menüitems setzen text_exception=menu_item und zeigen immer
Icon + kurzen lokalisierten Aktionsnamen, unabhängig von altem item.icon_only.

Native `details/summary` bleibt No-JS-Grundlage; keine ARIA-menu-Rolle ohne
vollständige Menü-Tastaturimplementierung. Tab erreicht Einträge; Enter/Space
bedienen summary. Escape schliesst das aktive Menü und gibt Fokus an **seinen**
Auslöser zurück; kein Submit beim Öffnen. Dialogrückkehr ebenfalls zum Auslöser,
auch nach Abbruch. Outside-click schliesst nur Menü, keine bearbeiteten Details.

IDs: explizite id gewinnt; fehlt sie, erzeugt ein kleiner requestgebundener
Zähler in bestehendem UI-Modul kollisionsfreie DOM-IDs, nicht Objektname/Slug.
Wrapper leiten von derselben Basis Trigger-/Panel-/Tooltip-IDs ab.
aria-controls verweist auf vorhandenes Panel, aria-expanded folgt offen/geschlossen.
Keine Default-ID „semantic-confirm“ mehrfach auf derselben Seite.

`list_row` erhält gemeinsame optionale Details. `inline=true` bei
disclosure_section bedeutet Detailzugang am **lesbaren Datensatznamen** mit Chevron;
kein dritter isolierter Button rechts. Namenslink oder Detailtrigger, nicht
beides verschachteln. Freie Metadaten erscheinen höchstens in einer zweiten
Zeile, lange essenzielle Namen dürfen wachsen. Keine klickbare Gesamtzeile.
`more_actions`/form_footer.rare bleiben Legacy-Slots, werden in denselben
Überlauf-Adapter integriert; niemals zusätzlich zu row_actions noch ein
zweites Mehr-Menü erzeugen. Bereits gerendertes HTML nicht heuristisch parsen:
Aufrufer migratorisch auf strukturierte Items umstellen.

Status nur aus vorhandenem Zustand. `status_context` darf ausschließlich einen
vom Aufrufer tatsächlich gesetzten homogenen Filter beschreiben; nur dann
redundantes „Aktiv“ weglassen. In gemischter Liste bleibt Status sichtbar.
Kein Statusplatzhalter, wenn überhaupt kein Status sinnvoll ist. „Nicht erfasst“
bleibt Text und wird nicht „0“/„—“. `label` bleibt Darstellungskern.

Tabelle bleibt table, einfache Liste bekommt geeignete Listenhülle und Zeilenadapter;
list_row-div niemals als direktes tbody-Kind. Tokens/Typografie/Trenner teilen,
keinen Universalrenderer mit ungültigem HTML erzwingen.

### 4.5 Tokens, Kopf und Toolbar

| Token / Ziel | Bestand und konkrete Änderung |
|---|---|
| `--app-button-size` = 36px | Heute 48 via --app-space-12, T:183/219. Nur standardisierte Aktionscontrols umstellen, nicht sämtliche Formfelder. |
| `--app-button-size-touch` = 44px (neu) | Gemeinsamer Wert für `@media (pointer: coarse)`; zusätzlich `(any-pointer: coarse)` berücksichtigen, damit Hybridgeräte mit grobem Zweitzeiger nicht durchfallen. |
| `--app-action-icon-size` = 20px (neu) | Eigener Aktionstoken; `--app-label-icon-size` T:207 bleibt Statusicon-Metrik. |
| Zeilen | --app-list-row-min-height 48px, zusätzlicher zweizeiliger Richtwert 64px; min-height statt fester Höhe. T:186–199/C:535 dürfen Wachstum nicht abschneiden. |
| Radius/Abstand | --app-radius-control 8px T:180 nutzen; Containerziel 8px gegen bisherige --app-radius-card 12px T:179 konsolidieren. Vorhandene Leiter T:212–219 verwenden. |
| Typografie | T:191–198 bereits 14px Haupt-/Metarollen und 13px sekundär über vorhandene Variablen. Keine Root-Verkleinerung/zoom. |
| Legacy-Overrides | C:123,139,435–436 erzwingen teils 48px: gezielt standardisierte Aktionscontrols priorisieren; Fokus-/Formfeldgrößen erhalten. |
| Status | Bestehende --app-label-* T:200–208 und C:665ff gemeinsam; sichtbarer Text, keine Warnbadge-Wand als Standard. |

Normaler Kopf: Titel, nötiger Kontext, maximal eine gefüllte fachliche Primäraktion
und zwei weitere direkte fachliche Aktionen; Rest in Überlauf (S:81–100).
Datum/Profil bleibt gemeinsame Kontextgruppe, keine extra Profilkarte.
`page_header` darf leere Beschreibung/status_items bereits heute weglassen (A:12–18).

Toolbar: Suche, optional einmal profile, ein Filtereinstieg. Bestehendes GET-Formular,
Feldnamen, Werte, Hidden-Filter/Paging und Submit-Verhalten erhalten.
Enter im Suchfeld sucht; bei sichtbarem Suchbutton view.search im selben Suchblock.
view.filter öffnet direkt benachbarte Zusatzfilter, kein zweiter gleichwertiger
Filterbutton. Anwenden/Zurücksetzen im geöffneten Bereich, Reset view.reset.
`active_count=0` reserviert keine Zeile; bei >0 lokalisierter Zähler am Einstieg.
filters/more_filters bleiben akzeptierte Slots, bilden gemeinsam diesen Bereich;
profile ist eigene verständliche Textauswahl, kein Icon und keine doppelte Auswahl.
Kein neues Autosubmit-System neben JS:668–672.

## 5. Testauswirkung

### 5.1 Zählweise und Ergebnis

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Die historischen Menüeintrags- und Textausnahme-Erwartungen aus §5.1–5.4 begründen kein Aktionsmenü mehr. Zahlen und damalige Testbefunde bleiben unverändert; Direktdarstellung braucht neue Nachweise unter Erhalt aller Sicherheits-, Rollen- und Funktionsassertionen.

**73 Testfunktionen mit textabhängigen Kontrollprüfungen, 215 weitere
Testfunktionen mit Button-/Link-Namensselektoren; 2 davon in gesperrter Datei.
0 gesperrte Testfunktionen mit festgeschriebenem sichtbarem Buttontext gefunden.**

113 konkrete Text-Prüfstellen sind in der Tabelle referenziert. Zähleinheit:
ein statisch definiertes `test_*`, keine pytest-Parameterinstanz, kein Lauf und
keine behauptete Zahl fehlschlagender Tests. Lokale Helper einschließlich
als Callback übergebener Helper wurden auf Testaufrufer zurückgeführt;
verschiedene verschachtelte `verify`-Funktionen nicht zusammengeworfen.
V und N sind pro Test disjunkt: ein Test mit beiden Mustern zählt als V.
N erfasst explizites `get_by_role('button'|'link', name=...)` einschließlich
Navigation; „nur Name“ bezieht sich auf diese Kontrollprüfung, nicht auf andere
Inhalts-, Größen-, title- oder DOM-Prüfungen desselben Tests.

V umfasst normale Aktionen, Überlauf-/Details-Auslöser und zulässige Textausnahmen.
Daher bedeutet V **prüfen und zielgerichtet migrieren**, nicht 73 Änderungen:
Menüeinträge, Sicherheitsbestätigungen, Formular-/Abschnittsbezeichnungen und
Navigation dürfen weiterhin Text tragen. Nicht als Aktionskonflikt zählen
Statusinhalt, Gerichtname, Tabellenüberschrift, Tooltip-Inhalt oder ein
`inner_text()` nur als Fehlerdiagnose.

Methoden: `get_by_text`, `has_text`, `:has-text`, `inner_text`,
`text_content`, `to_have_text`, `to_contain_text`, BeautifulSoup
`get_text`/`.span.text`, HTML-Literale. `text_content` kann versteckten Text
mitzählen: niemals als alleinigen Sichtnachweis behandeln.

Alle Dateinamen in der Tabelle liegen unter **Tests**. V-Zeilen sind einzelne
Prüfstellen (teils in Helpern); N-Zeile ist erster Button-/Link-Namensselektor
der Datei als Einstieg, nicht zwingend Teil eines N-only-Tests.

| Datei | V: Testfunktionen | N: nur Name | V-Zeilen / Art gemäß 5.2 | N-Einstiegszeile |
|---|---:|---:|---|---:|
| `test_admin_access_history_browser.py` | 0 | 1 | — | 50 |
| `test_admin_api_key_policy.py` | 1 | 0 | 123 | 117 |
| `test_admin_api_page.py` | 1 | 0 | 307 | — |
| `test_admin_copy_ui.py` | 0 | 1 | — | 88 |
| `test_admin_cost_routes.py` | 1 | 0 | 121, 123 | — |
| `test_admin_csv_preview_ui.py` | 3 | 2 | 207, 233, 270, 429, 464 | 190 |
| `test_admin_display_browser.py` | 3 | 2 | 77, 242, 326 | 92 |
| `test_admin_display_options_browser.py` | 0 | 1 | — | 48 |
| `test_admin_local_users_browser.py` | 0 | 1 | — | 133 |
| `test_admin_menu_editor_browser.py` | 1 | 4 | 419 | 82 |
| `test_admin_menu_save_back_browser.py` | 0 | 2 | — | 23 |
| `test_admin_nav_browser.py` | 0 | 3 | — | 79 |
| `test_admin_operations_browser.py` | 0 | 1 | — | 36 |
| `test_admin_output_hubs.py` | 1 | 1 | 124 | 309 |
| `test_admin_overview_forms.py` | 0 | 3 | — | 32 |
| `test_admin_screens_preview_browser.py` | 0 | 2 | — | 96 |
| `test_admin_shared_patterns_browser.py` | 1 | 10 | 192 | 163 |
| `test_admin_shell_ui.py` | 0 | 1 | — | 77 |
| `test_admin_tabler_browser.py` | 0 | 1 | — | 71 |
| `test_admin_template_catalog_browser.py` | 2 | 0 | 98, 106, 214, 269, 274, 288 | 228 |
| `test_admin_ux_browser.py` | 1 | 4 | 159 | 135 |
| `test_admin_week_equal_cards_browser.py` | 1 | 1 | 90 | 59 |
| `test_admin_week_tabler_browser.py` | 0 | 4 | — | 181 |
| `test_admin_week_ui.py` | 1 | 1 | 151, 152, 155, 225 | 192 |
| `test_branding_browser.py` | 0 | 1 | — | 74 |
| `test_branding_header_browser.py` | 0 | 1 | — | 103 |
| `test_branding_logo_browser.py` | 0 | 1 | — | 119 |
| `test_calendar_event_routes.py` | 1 | 0 | 87 | 90 |
| `test_component_catalog_browser.py` | 1 | 2 | 229 | 46 |
| `test_component_filters_browser.py` | 0 | 1 | — | 38 |
| `test_component_food_selection_browser.py` | 0 | 2 | — | 292 |
| `test_cookbooks_browser.py` | 0 | 2 | — | 90 |
| `test_course_browser.py` | 1 | 1 | 58 | 160 |
| `test_dish_template_browser.py` | 4 | 3 | 59, 202, 434, 470 | 48 |
| `test_inventory_ui.py` | 0 | 1 | — | 186 |
| `test_master_data_browser.py` | 0 | 4 | — | 91 |
| `test_master_data_prepared_browser.py` | 0 | 2 | — | 36 |
| `test_menu_accompaniment_flow_accept.py` | 0 | 2 | — | 151 |
| `test_menu_collection_browser.py` | 2 | 2 | 51, 218 | 93 |
| `test_menu_proposal_browser.py` | 0 | 5 | — | 63 |
| `test_menu_recipe_selection_browser.py` | 0 | 2 | — | 323 |
| `test_menu_template_binding_browser.py` | 0 | 2 | — | 105 |
| `test_print_branding_browser.py` | 0 | 1 | — | 30 |
| `test_print_template_archive_browser.py` | 0 | 4 | — | 41 |
| `test_print_template_browser.py` | 1 | 2 | 220 | 190 |
| `test_print_template_layout_forms.py` | 1 | 0 | 269 | 261 |
| `test_recipe_browser.py` | 1 | 0 | 71, 80 | 37 |
| `test_recipe_density_browser.py` | 1 | 3 | 103 | 105 |
| `test_recipe_filters_browser.py` | 0 | 2 | — | 51 |
| `test_recipe_freeze_v2_browser.py` | 1 | 2 | 127 | 122 |
| `test_recipe_images_browser.py` | 1 | 1 | 108 | 76 |
| `test_recipe_import_browser.py` | 2 | 3 | 147, 359 | 57 |
| `test_recipe_navigation_browser.py` | 1 | 0 | 157, 172, 206, 216, 221 | 59 |
| `test_recipe_pdf_http.py` | 0 | 1 | — | 196 |
| `test_recipe_plan_portions_browser.py` | 0 | 2 | — | 243 |
| `test_recipe_revision_routes.py` | 1 | 0 | 290 | — |
| `test_recipe_search_browser.py` | 0 | 3 | — | 48 |
| `test_recipe_template_editor_browser.py` | 0 | 3 | — | 56 |
| `test_recipe_view_print_browser.py` | 0 | 4 | — | 60 |
| `test_rendered_ui.py` | 0 | 1 | — | 1046 |
| `test_screen_template_browser.py` | 1 | 2 | 292 | 125 |
| `test_screen_template_navigation.py` | 0 | 1 | — | 78 |
| `test_shopping_list_browser.py` | 0 | 4 | — | 84 |
| `test_ui_brand_ops_browser.py` | 0 | 2 | — | 166 |
| `test_ui_fullwidth_pages_b_browser.py` | 0 | 1 | — | 185 |
| `test_ui_fullwidth_shell_browser.py` | 3 | 1 | 122 | 176 |
| `test_ui_korrektur_branding_browser.py` | 3 | 2 | 148, 208, 220, 450 | 126 |
| `test_ui_korrektur_components_browser.py` | 2 | 5 | 167, 190 | 141 |
| `test_ui_korrektur_cookbooks_browser.py` | 4 | 3 | 184, 211, 212, 235, 571, 579 | 180 |
| `test_ui_korrektur_editor_browser.py` | 0 | 9 | — | 50 |
| `test_ui_korrektur_grundlagen_browser.py` | 3 | 3 | 195, 205, 224, 260, 266, 282, 305 | 108 |
| `test_ui_korrektur_menus_browser.py` | 2 | 0 | 178, 191, 272 | 291 |
| `test_ui_korrektur_ops_browser.py` | 0 | 3 | — | 71 |
| `test_ui_korrektur_recipes_browser.py` | 1 | 0 | 89, 103, 104, 107, 110, 155 | 117 |
| `test_ui_korrektur_screens_browser.py` | 0 | 4 | — | 179 |
| `test_ui_korrektur_tools_browser.py` | 0 | 5 | — | 125 |
| `test_ui_korrektur_users_browser.py` | 2 | 4 | 226, 363, 369, 376 | 229 |
| `test_ui_korrektur_vorlagen_browser.py` | 1 | 6 | 237, 240, 243 | 150 |
| `test_ui_korrektur_week_browser.py` | 1 | 5 | 300 | 129 |
| `test_ui_master_components_browser.py` | 1 | 0 | 452 | — |
| `test_ui_master_shell_browser.py` | 0 | 6 | — | 186 |
| `test_ui_master_tokens_browser.py` | 0 | 1 | — | 599 |
| `test_ui_menu_editor_browser.py` | 1 | 1 | 359, 363, 367, 381 | 271 |
| `test_ui_output_hubs_browser.py` | 0 | 1 | — | 427 |
| `test_ui_preview_browser.py` | 0 | 3 | — | 196 |
| `test_ui_reference_detail_browser.py` | 1 | 4 | 219, 243 | 208 |
| `test_ui_reference_form_browser.py` | 1 | 2 | 144 | 229 |
| `test_ui_reference_list_browser.py` | 1 | 0 | 81, 114, 162 | 150 |
| `test_ui_reference_settings_browser.py` | 0 | 5 | — | 106 |
| `test_ui_reference_workspace_browser.py` | 1 | 2 | 145 | 85 |
| `test_ui_route_inventory.py` | 0 | 4 | — | 257 |
| `test_ui_semantic_macros_browser.py` | 0 | 3 | — | 109 |
| `test_ui_semantics.py` | 8 | 0 | 76, 84, 273, 303, 307, 372, 374, 378, 481, 536, 621, 653 | — |
| `test_ui_shell_fixes_browser.py` | 0 | 1 | — | 57 |
| `test_ui_weeks_browser.py` | 0 | 3 | — | 187 |
| `test_week_form_focus_browser.py` | 0 | 1 | — | 40 |
| `test_week_form_rerender_browser.py` | 0 | 1 | — | 120 |
| `test_week_management_browser.py` | 0 | 2 | — | 40 |
| `test_week_review_browser.py` | 0 | 3 | — | 97 |

### 5.2 Art der Abhängigkeit und konkrete Migration

| Prüfart | Konkrete Datei:Zeile | Wirkung |
|---|---|---|
| Exakter sichtbarer Aktionstext | test_menu_collection_browser.py:51; test_ui_korrektur_components_browser.py:167; test_component_catalog_browser.py:229 | „Bearbeiten“ im Control-DOM entfällt; Name und vorhandene URL prüfen, Icon-only zusätzlich belegen. |
| inner_text | test_menu_collection_browser.py:218; test_ui_reference_list_browser.py:114; test_ui_fullwidth_shell_browser.py:122; test_ui_master_components_browser.py:452 | Explizite Textpflicht auch ohne konkretes Wort. Shell-/Nav-Ausnahmen von normalen Aktionen trennen. |
| Textselektor/get_by_text | test_recipe_navigation_browser.py:172,206,216,221; test_recipe_browser.py:80; test_recipe_freeze_v2_browser.py:127 | Geschlossener Mehr-/Detailtrigger benötigt Rollen-/Namensselektor statt sichtbarem Text. |
| has_text / :has-text | test_ui_reference_form_browser.py:142–145; test_admin_menu_editor_browser.py:419; test_admin_ux_browser.py:159; test_course_browser.py:58 | Aktionsziel explizit über Rolle/Name oder stabilen Hook; kein Text-Suchersatz durch unsichere DOM-Position. |
| Gerendertes HTML / BeautifulSoup | test_ui_semantics.py:76,84,303,378,481,536,621,653 | Registry-Name und aria-label getrennt von bewusstem Menü-/Dialogtext testen. |
| HTML-String-Assert mit Ankertext | test_recipe_revision_routes.py:290; test_admin_output_hubs.py:124; test_admin_template_catalog_browser.py:98,106 | Nicht bloß String entfernen; URL/Anzahl/Rechte behalten, sichtbare Navigation ggf. zulässige Ausnahme. |
| Negative HTML-String-Checks | test_recipe_revision_routes.py:303; test_dish_template_routes.py:359; test_recipe_navigation_browser.py:255 | Ohne Text können sie fälschlich grün werden. Verbotene Zielroute/Formaktion/Control prüfen; AuthZ-Absicht erhalten. Nicht in V-Positivzahl enthalten. |
| Unscharfer Response-Text | test_cookbook_routes.py:231 | „Anlegen“ irgendwo in response.text beweist kein sichtbares Label; aria-label würde denselben String liefern. Nicht als sichtbaren Buttontest zählen. |
| Namen unabhängig vom DOM-Text | test_ui_semantic_macros_browser.py:109,137,160,172; test_menu_accompaniment_flow_accept.py:151,187,327,374 | get_by_role bleibt gültig, wenn aria-label denselben Namen trägt; explizite Objektzuordnung darf dabei nicht unkontrolliert alte Namen ändern. |
| Beabsichtigte Textausnahme | test_ui_semantics.py:273,307; test_ui_korrektur_branding_browser.py:208,220; test_ui_korrektur_users_browser.py:363–376 | Text in geöffnetem Menü/Sicherheitsaktion nur nach Kontext klassifizieren; kein globales Löschen dieser Assertions. |
| Bereits icon-only | test_ui_korrektur_cookbooks_browser.py:161–168,259,598; test_ui_korrektur_screens_browser.py:125 | _icon_control liefert Name/title, verlangt gerade **leeren** inner_text. Nicht irrtümlich als Textpflicht zählen. |

### 5.3 Gesperrte *_accept.py

Repositoryweite Dateisuche findet genau
`reference_scaffold/tests/test_menu_accompaniment_flow_accept.py`.
**Konfliktliste für sichtbaren Buttontext: leer. Datei bleibt gesperrt.**

`_post_button` :149–151 nutzt get_by_role/name; Aufrufe :160/174/178/205/316.
Weitere Namen :187 „Menü speichern“, :327 „Veröffentlichen“, :374
„Speichern“ (Abwesenheit für Leser). Zwei Testfunktionen nutzen diese Wege.
Die Textprüfungen :180,208–210,231–233,299–301 betreffen Herkunfts-/Beilageninhalt,
:322 den Sperrgrund als Diagnose, keine festgeschriebene Buttonbeschriftung.
Diese Fachtexte bleiben erhalten. Keine Änderung oder Umgehung des Accept-Gates.
Falls ein späterer Pilot unter erhaltenen Namen dennoch kollidiert: konkreter
Konflikt an Orchestrator, niemals Accept-Datei anpassen.

### 5.4 Zusätzliche Vertragsgates, nicht in V/N aufsummieren

- Tests/test_ui_semantics.py:212–225 verbietet icon-only bei save/delete;
  :506–520 erwartet Fehler bei primary+icon_only; :644–654 verlangt weiterhin
  Text für activate/apply. Das widerspricht dem neuen Default.
- Tests/test_ui_semantics.py:438–464: **ein Test mit sechs Byte-Hash-Fällen**.
  icon_button, action_menu, row_actions, beide filter_bar-Adapter ändern bewusst
  HTML; field gehört nicht zur Icon-first-Änderung. Hashes nicht blind erneuern:
  native Form-/Rechte-/Escaping-Invarianten separat erhalten und neuen DOM-Vertrag
  ausdrücklich abnehmen.
- Tests/test_ui_semantics.py:532–560 erzwingt „sichtbares Label: aria_label“ und
  exaktes Markup; :584 vollständige Attributmenge ohne standardmäßiges aria-label.
  Neue Tooltip-/Nameattribute verursachen gewollte Änderungen.
- Tests/test_ui_semantic_macros_browser.py:110,143,162,180 prüft title und
  48-px-Ziele; Tests/test_ui_fullwidth_shell_browser.py:124 sowie
  Tests/test_ui_master_components_browser.py:449 verlangen ebenfalls 48px.
  Zielgrößen nach Eingabemodus prüfen, Navigation/Formfelder nicht schrumpfen.
- Tests/test_ui_semantics.py:416–422 begrenzt kurze Aktionslabels auf 2 Wörter/
  18 Zeichen. Als Menü-Kurzlabel-Regel brauchbar; **nicht** auf Objektname,
  Tooltip, zugänglichen Namen oder notwendige Bestätigung übertragen.
- Tests/test_order_admin.py:379–400 prüft Statuslabel-Spans. Kein Konflikt:
  Status behält verständlichen Text gemäß S §8.

## 6. Regelkonflikte und Ersatzformulierungen

> **ABGELÖST (2026-09-29; [SDD Direkte Symbolaktionen](2026-09-29-direct-symbol-actions-sdd.md)):** Die folgenden historischen Ersatzformulierungen mit Ein-Direktaktions-Budget, dots, Menü-Kurztext oder „kein dritter Button“ begründen keinen Aktionsüberlauf und kein Zahlenlimit mehr. Es gilt direkte Sichtbarkeit aller verfügbaren Aktionen; übrige Icon-first- und Schutzregeln bleiben gültig.

Dieses WP dokumentiert Konflikte; es ändert weder Governance noch Tests.
Alle M-Zeilen sind Fundstellen im bestehenden Manifest, inklusive wiederholter
historischer Vertragsabschnitte. Nur Aktionen betreffende Teile ersetzen;
Navigation, Formlabels und Status nicht pauschal enttexten.

| Beleg | Konflikt | Ersatz gemäß S |
|---|---|---|
| AGENTS.md:50; CLAUDE.md:50 | „konsistente Icons mit sichtbarem Text“ ohne Rollentrennung | „Standardaktionen als konsistente Iconbuttons mit lokalisiertem zugänglichem Namen und gemeinsamem Tooltip; sichtbarer Text für Fachinhalt, Navigation/Profilauswahl, Menüeinträge, Sicherheitsbestätigungen und notwendige Zustände.“ |
| M:170 | Icons ohne Text generell als Fehler bei unklarer Bedeutung | „Seltene/ungewohnte Aktionen im geöffneten Menü mit Kurztext; keine Hover-/Langdruckpflicht.“ |
| M:213 (R14),215 (R16),297 | Tertiary und häufige Aktionen Icon+Text / Kurztext | „Gewichtung unabhängig von Beschriftung; normale Kopf-/Zeilenaktionen icon-only; eine Direktaktion plus belegter Überlauf.“ |
| M:214 (R15),298,547–548 | Destruktiv immer sichtbares Buttonlabel | „Gefährliche Bedeutung, expliziter zugänglicher Name und Konsequenz bleiben; sichtbares Label im Menü und Bestätigungsdialog, kein globales Danger-icon-only-Verbot.“ |
| M:252–253 (R28/29),710–713,773 | Alte icon_only_allowed-Politik / wichtige Aktionen nur Text | „Registry bildet Semantik ab; normale Aktionen einschließlich primary icon-only. Fachkennzeichnungen, Navigation und Textausnahmen bewahren ihre Regeln.“ |
| M:351 (M45),518–523 (R44),561–563 (R47) | 48px Button / 56px Zeile und title-only | „36px fein, mindestens 44px grob, 20px Aktionsicon; Zeile Richtwert 48/64px mit Wachstum; Tooltip Hover+Fokus+Escape+Pointer.“ |
| M:525–534 | Freier text und automatische deutsche Namenskomposition | „Locale-Placeholder für Objektname; alte Aufrufparameter bleiben Übergangsadapter. Sichtbare Textausnahme nur explizite Enum.“ |
| M:538–539 (R45),594–596 | Sichtbares „⋯ Mehr“ | „Geschlossener dots-Trigger mit lokalisiertem Namen; geöffnet Icon+Kurztext; ohne Einträge kein Menü.“ |
| M:589;748 (M64/Signatur) | Bytegleichheit / icon_only=false | „Aufruf-/Ausführungskompatibilität erhalten; absichtlich geändertes DOM mit icon_only=true und expliziten Textausnahmen.“ |
| M:818 (R05),1027,1029,1031 | Hauptaktionen auch mobil zwingend Text | „Auf Desktop/Mobil gleiches Icon-only; keine wechselnde Beschriftung nach Breite. Navigation und Fachtexte bleiben lesbar.“ |
| M:1065 (Buttons),1116 | Hauptaktionen beschriftet / Skizzenlabels als verbindliche UI-Texte | „Aktionen in Skizzen stehen für Registry-Icons, nicht permanente Buttontexte; Inhalte/Formlabels bleiben verbindlich.“ |
| M:1391 | Zeilenaktionen mit kurzen sichtbaren Wörtern | „Reihenfolgeaktionen mit semantischem Icon und lokalisiertem Objektbezug; im Menü Kurztext, Zielgrößen und native Formdaten erhalten.“ |
| M:2189 | Sichtbare Zeilenaktion plus beschriftetes Weitere-Aktionen-Menü | „Rechts Haupt-Iconaktion plus dots, Menütext erst geöffnet; Detailzugang am Namen, kein dritter Button.“ |
| M:2317;2387;2507;2540 | text=-Kurzlabels, Speichern/Öffnen sichtbar; lange Erklärung im title | „Zielspezifische Namen erhalten, normale Aktionsfläche icon-only, gemeinsamer Tooltip statt title allein.“ |
| M:2617;2627–2630 | Wochenaktionen behalten sichtbare Texte/Registry-Ersatzverben | „Eigene actions.review/actions.publish/actions.plan; konkreter fachlicher Name in Locale, sichtbare Bestätigungslabels bleiben.“ |
| M:2683;2693;2839 (A16) | Icon-Makro + Hauptaktionen sichtbar beschriftet | „DOM-Namen und Sprite prüfen; Standardaktion ohne sichtbaren Begleittext, definierte Textausnahmen getrennt abnehmen.“ |
| U:49–56; UI:19–22; R:3,69,80,113,861 | Aktuelle Guards verhindern neuen Standard | „Textpflicht nach Kontext, nicht pauschal nach primary/danger; Konsequenz-/Rechteschutz bleibt.“ |
| Tests aus §5.2 / §5.4 | Sichtbarer Text, alte Verbote, Bytes und Geometrie fixiert | „Name/Rolle, Aktionssemantik, Ausführung, Icon-only und Textausnahmen separat prüfen; funktionale Assertions nicht entfernen.“ |

**Keine Regelkonflikte:** M:152/236/238/307/352/368/610/721/1182/1312/1833
(Status mit Text), M:1053 (Navigation), M:1066 (Feldlabels), M:2145
(Formauswahl), M:2853 (Statuschips) bleiben mit S §5.4/§8 vereinbar.
M:1964 betrifft eine Sicherheitsbestätigung; sichtbarer Text bleibt.
M:1236 Wiederherstellung/Prüfbestätigung verlangt weiter eindeutige Bedeutung,
nicht pauschal alte sichtbare Toolbartexte. M:2739 verlangt Verständlichkeit;
das wird über Name, Tooltip, Menü und sichere Rückwege konkretisiert.

Ratchet präzise: `tools/ui_consistency_inventory.py:20,91–132` zählt
literal_buttons/long_labels/wrong_icons etc.; es verlangt **keinen**
nichtleeren sichtbaren Buttontext. Tests/test_ui_consistency_ratchet.py:28–35
akzeptiert bereits sem_icon plus visually-hidden. :19–25,47–56 fixieren
alte Detektorbeispiele, nicht allgemeine Textpflicht. Daher kein erfundener
Blocker „Ratchet verbietet Icon-only“. Echte Lücke: falsche Icons werden anhand
sichtbarer Verben erkannt (:130–132); nach Textentfernung braucht die bestehende
Ratsche semantische Keys/Renderer als Evidenz. Lange Namen nicht als lange
sichtbare Labels zählen. Baseline nur nach nachgewiesener Migration senken,
nicht zum Verdecken neuer Ausnahmen erhöhen (M:568–578).

## 7. WP2: drei Pakete mit disjunktem Dateibesitz

Kein separater Writer für icon_button und action_menu: beide liegen in U, ihre
Legacy-Adapter in A. Ein Eigentümer pro Datei, keine konkurrierenden Teilbesitzer.
Alle folgenden Tests sind Gate-Vorschläge, hier nicht ausgeführt.
Orchestrator erzeugt ausführbare WPs und isolierte Writer-Worktrees; dieser
Analyse-Worker startet keine Unteragenten.

| Paket | Exklusiver Dateibesitz | Lieferumfang / Anschluss | Gate-Testdateien |
|---|---|---|---|
| **2a Registry, Namen, Policies** | `cafeteria/ui/semantic_registry.json`, `icon_fallbacks.json`, `semantics.py`, `__init__.py`, `i18n.py`, `translations/de.json`, `en.json` unter reference_scaffold | Drei reale Aktionskeys, kanonische Icons, world-upload→send-Fallback; Placeholder-Erweiterung mit strikter Validierung; primary darf icon-only, Folgenprüfung bleibt; requestgebundene ID-Hilfe für 2b. Kein Sprite-Update nötig. | Tests/test_ui_semantics.py (read-only bis 2b angepasste Tests liefert); vorhandene Registry-/Locale-/Escaping-Tests. |
| **2b Renderer, Verhalten, Adapter** | `cafeteria/templates/ui/_semantic.html`, `templates/admin/_macros.html`, `static/admin.js`, `static/ui-semantic.css`; Tests/`test_ui_semantics.py`, `test_ui_semantic_macros_browser.py`, `test_admin_shared_patterns_browser.py`, `test_ui_master_components_browser.py` | Gesamter Button-/Tooltip-/Zustandsvertrag; action_menu/row_actions, Legacy-Wrapper, Details-ID/Fokus, status/list/filter/header-Adapter. Besitzt auch Registry- und Renderer-Testanschlüsse in gemeinsamer Testdatei; 2a liefert dafür Fälle, schreibt diese Datei nicht. | Eigene vier Testdateien; unveränderte Tests/test_menu_accompaniment_flow_accept.py; test_menu_collection_browser.py Tooltip/CSP; native Form-/Dirty-State-Gates. |
| **2c Tokens, Konsistenz und Governance** | `cafeteria/static/tokens.css`, `static/admin-tabler.css`; `tools/ui_consistency_inventory.py`; Tests/`test_ui_consistency_ratchet.py`, `test_ui_master_tokens_browser.py`; `docs/design/2026-09-09-unified-ui-design-system.md`, `AGENTS.md`, `CLAUDE.md` | Gemeinsame 36/44/20-Geometrie, Zeilen-/Status-/Toolbar-Tokens, alte Größen-Overrides gezielt konsolidieren, Ratchet erkennt Icon-Semantik ohne sichtbare Verben; §6 in vorhandenen Governance-Orten einarbeiten. | Eigene Ratchet-/Token-Tests; read-only Tests/test_ui_fullwidth_shell_browser.py, test_ui_master_components_browser.py, test_ui_semantic_macros_browser.py. |

Alle Produkt-/Testpfade in Paketspalte ohne Prefix sind relativ zu
`reference_scaffold/`, tools/docs/AGENTS/CLAUDE relativ zum Repository.
Kein Paket besitzt Accept-Dateien. Bestehende Baseline und UI-Inventar erhalten
erst nach passenden Pilotnachweisen einen gesondert zugewiesenen Eigentümer.

Reihenfolge: 2a stabilisiert Registry-/Locale-/Helpervertrag; 2b integriert
Renderer **und alle Aufrufer innerhalb seiner gemeinsamen Dateien**;
2c kann Tokenkonstanten gegen diesen Vertrag vorbereiten, Integration/Gates
erst nach 2b. Shared-Teständerungen von 2b gehören zur Abnahme von 2a:
vorher nicht „grün“ behaupten. Bei Bedarf Arbeit innerhalb eines Pakets sequenziell
in kleine Commits teilen, Besitz bleibt eindeutig. Modul-Templates und ihre
spezifischen Tests aus §5 werden ab WP3/Pilot bzw. WP4/WP5 migriert, nicht von
mehreren WP2-Writern nebenbei.

Abnahmematrix WP2: DE/EN/Pseudo; Objektname mit Anführungszeichen, <>& und langen
Namen; Fine/Coarse/Hybrid-Pointer; Viewports 1440×900, 1024×768, 768×1024, 390×844;
200%-Zoom/Reflow; Tab/Enter/Space/Escape; Hover über Tooltip; leeres/volles Menü;
gesperrt/laufend/Fehler/No-JS; Submitter mit externem form/name/value/formaction;
Rückkehr und erhaltene Eingaben. Zustände und Messungen im echten Browser, keine
Screenshot- oder count-only-Abnahme. Pilot Bausteine und Rezepte nach S:539.

## 8. Nachweisstatus dieses Analyse-WP

Quellen-/Sprite-/Locale-/Teststellen und grep-Zählungen wurden statisch geprüft.
GitNexus-Query zur semantischen UI lieferte keine passenden Prozesse, nur
Dateiverweise; daher sind die Live-Dateien dieses Worktrees Grundlage. Kein
Produkt-Symbol wird geändert, deshalb kein symbolbezogener Edit/Impact-Lauf.
Staged Diff/Scope und Whitespace-Prüfung wurden ausgeführt. Genau eine Datei,
keine Produkt-/Teständerung; Tabellensummen unabhängig aus dem Dokument geprüft:
99 Testdateien, V=73, N=215, 113 referenzierte Textprüfstellen.

Gate-Ausgaben vor Commit:

~~~text
rtk git diff --cached --check
exit_code=0; stdout leer

gitnexus_detect_changes(repo=<dieser Worktree>, scope=staged)
Erstaufruf: Error: Repository "/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-contract-0926" not found.
Identischer Retry: Error: Repository "/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-contract-0926" not found.

rtk ocr review --repo <dieser Worktree> --staged --format json --audience agent --background <WP1b-Kontext>
Erstaufruf: Error: unknown flag: --staged
exit_code=1
Identischer Retry: Error: unknown flag: --staged
exit_code=1
~~~

GitNexus listet andere menuplan-Worktrees, aber nicht diesen. Kein fremder
Index wird als Prüfung dieses staged Diffs ausgegeben. Vollständige Toolantworten
liegen im Sitzungsprotokoll; oben ist der Fehlerkern ohne lange Repositoryliste.
Der vorgeschriebene OCR-Branchvergleich gegen den Basiscommit folgt nach Commit;
sein Ergebnis gehört in den Abschlussbericht. Bisher kein CLEAN-Review behauptet.

Nicht ausgeführt: pytest, Browser-/Screenshotmatrix, DB-/AuthZ-/Formularläufe,
Lint/Typecheck des Produkts, Deploy oder Liveprüfung. Für einen reinen
Vertrags-Diff wäre deren Ergebnis kein Nachweis der noch ausstehenden WP2-Umsetzung.
Die 73/215 sind Analysezahlen, keine bestandenen Tests.

Offene Umsetzungskonflikte: alte Default-/Danger-/Primary-Textpolitik,
bytegenaue Legacy-Gates, 48px-Gates, noch nicht appweite Tooltip-/Sperranbindung,
drei fehlende Aktionssemantiken sowie Migration textabhängiger Modulprüfungen.
Gesperrte Accept-Tests haben keinen nachgewiesenen Buttontext-Konflikt.
