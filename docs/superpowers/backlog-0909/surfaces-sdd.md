# Oberflächen, Zugriff und Abnahme — vollständiger Surface-SDD

Stand: 9. September 2026. Planungsquelle e813806b51fb5efaef5d5755c292f8027ce1b2eb
(Schema 26, lokal integriert). Dieser SDD und [surfaces-wps.json](surfaces-wps.json)
planen exakt 19 Backlog-IDs. Sie sind keine Implementierung, Browserprüfung oder Gesamtfreigabe.
[Gemeinsamer Ausführungsvertrag](execution-contract.md) gilt identisch für Codex, Grok-Build
und Claude Code. Frühere exklusive Codex-Zuweisungen für API/Screens sind ersetzt.

<a id="rangfolge"></a>
## 1. Rangfolge, Quelle und heutiger Stand

Verbindliche einzige Designquelle ist der
[UI-Masterprompt vom 9. September](../../design/2026-09-09-unified-ui-design-system.md).
Er ersetzt ältere visuelle Vorgaben, nicht Fachlichkeit, Sicherheit oder Architektur.
Seine Palette wird hier nicht kopiert. Sie ist Nutzerentscheidung, kein bestätigtes Corporate
Design. Der vorliegende SDD konkretisiert Dateibesitz und fachliche Restgrenzen.
Weitere Grundlagen: [Haupt-SDD](../../SDD_Klinik_Suedhang_Cafeteria_v3.0.md),
[Backlog](../../BACKLOG.md), [bisherige Ausführung](../backlog-execution-0906.md),
[Screen-/Vorlagenvertrag](../../design/2026-09-05-screens-vorlagen-verwaltung.md),
[natives PDF](../../design/2026-09-08-native-pdf-layout-contract.md),
[Zugriffshistorie](../../design/2026-09-08-authentication-access-history.md).
Historische Statusabsätze und damalige Migrationsnummern sind keine neue Reservierung.

Die vom Orchestrator belegte Produktion ist 693eb74f1a54bd97616dbfc8e0f90bdc1197f508,
Schema 25. Rezepteditor/weisse Public Screens sind seit 8. September 21:46 Uhr Schweiz,
Zugriffshistorie seit 22:34 Uhr live. Dies ist übernommener datierter Releasebeleg,
kein neuer Live-Aufruf dieses Dokument-WPs. Rezept-PDF/Core/Editor im Kandidaten
5f5f6cb535922db8453c68d871279d6b2e203391 sind implementiert; korrigiertes Vollgate/Release
bleiben beim MP-REC-PDF-RELEASE. Nicht neu bauen und nicht als ausgeliefert bezeichnen.

R5b wurde während dieser Planung als ab6cd9f9a7fccd793f882667dbaf21ffb7307327 eingefroren;
unabhängige Prüfung/Integration bleibt beim Rezeptanker MP-REC-BINDINGS.
Schema27 und Grundlagen-Consumer bleiben MP-BAS-SCHEMA27 und MP-BAS-FOUNDATIONS.
Keine ihrer Dateien parallel verändern. Weitere Migrationen erhalten erst nach deren
Freeze eine vom Orchestrator vergebene Nummer. Kein zweiter 26→27-Writer.

| ID | Bestehend und Sourceanker | Vollständig verbleibende Grenze |
|---|---|---|
| UI-001 | admin/menu_collection_routes.py:menu_collection, menu_collection_store.py:find_menus; produktive Liste/Karten | Beide Ansichten und Rollen im vollständigen UI-Nachweis, keine neue Sammlung |
| UI-002 | public/routes.py:published_response, signage/routes.py:signage_response | Keine sichtbaren technischen Interna, auch leere/Fehlerflächen und neue Varianten |
| UI-003 | templates/admin/base_tabler.html, _macros.html, static/admin-tabler.css | Gesamter neue Masterprompt: alle Routen, Unterseiten, Modals, Rollen, Zustände und Login |
| CAT-001 | component_catalog_filters.py:ComponentFilters, component_catalog_store.py:find_components | Positive kombinierte Datenfälle fachlich/live bestätigen; UI-Polish erhält Filtersemantik |
| DSP-001 | display_settings.py:get_admin_display/set_admin_display | Globale Werte in allen Adminseiten und zweiter Sitzung; keine Wirkung auf Spezialausgaben |
| BRD-001 | branding.py:change_branding, branding_tokens.py:branding_css, branding_assets.py:normalize_logo | Aktive individuelle Marke im neuen UI und tatsächlich auf Papier/Player prüfen |
| API-001 | api/v1_routes.py:weeks, api/openapi.py:build_openapi, fhir/routes.py:metadata, dishboard_mcp/server.py:build_server | Bestehende Verträge erhalten, konkrete externe Clientanbindung separat abnehmen |
| ICO-001 | food_symbols.py:food_symbol, admin/week_pdf_symbols.py | Gepinnte 14 Gruppen/Flaggen, Textfallback in neuen Verbrauchern und Papier/Player |
| ICO-002 | food_symbols.py:food_legend, templates/_food_symbols.html | Nur sichtbare Codes, Presence/unbekannt getrennt, je Rotations-/Druckseite |
| SCR-001 | screen_templates.py:REGISTRY/read_assignment/activate; aktuell vier web.week-Einträge | Weitere Tag/TV-Ziele, revisionierter Katalog, Orientierung/Zielgruppen, Geräte und begrenzte Playlists |
| SCR-002 | public/routes.py, signage/routes.py, static/signage.js | Bestehende weisse Tag/Woche-/Rotationsausgaben regressions- und physisch abnehmen |
| SCR-003 | screen_templates.py:ScreenTemplate, admin/screen_template_routes.py | Freie erlaubte Blockgestaltung nach Eignungsentscheidung, vollständiges Tabler-UI und sichere Publikationsbindung |
| TPL-001 | print_templates.py:read_templates/change_template, admin/output_routes.py:vorlagen | Alle echten Kataloge verknüpfen; Menüvorlagen und Einkaufsdruck durch Rezeptowner liefern lassen |
| TPL-002 | print_template_config.py:validate_layout, admin/week_pdf_layout.py | Bestehende native Raster nicht neu bauen; verbleibende freie Geometrie erst konkret entscheiden und sicher ergänzen |
| TPL-003 | admin/week_pdf.py:render_week_pdf, admin/print_routes.py | Tatsächliche einseitige Wochen-PDFs und fachlicher Papiernachweis |
| IAM-001 | auth/access_events.py:record_access_event, auth/access_history_reads.py:list_access_history | Gelieferte Konto-/Zugriffsfunktion erhalten, technische Rollen-/Redis- und echte Fachabnahme |
| IAM-002 | auth/routes.py:_client/login/callback, config.py:Config | Revisionierte Verbindungsentwürfe, geschützte Referenzen, gebundener Test, Aktivierung und Rückweg |
| QA-001 | tests/test_rendered_ui.py, test_signage_engine.py, tools/capture_public_white_proof.py | Vollständige Laufzeitmatrix, unabhängige Liveprüfung und physischer Yodeck-Nachweis |
| DATA-001 | master_data_store.py:set_food_allergen_review/accept_proposal, workflow_review.py | Menschliche Küche bestätigt konkrete Datenstände; Vorschlag ist nie Freigabe |

Alle Produktanker ohne Präfix liegen unter reference_scaffold/cafeteria/.
Die drei Rezept-/Grundlagenanker werden nur konsumiert; dieses Slice definiert sie nicht.

<a id="gemeinsamer-vertrag"></a>
## 2. Gemeinsamer unveränderlicher Fach- und Schreibvertrag

Patienten bleiben strukturell preisfrei: Formular, Attribute, DTO, JSON, CSV, HTML und PDF;
keine nur versteckten Preise. Beide Cafeteriapreise bleiben lesbar. Technisches Profil ist
keine frei editierbare Bezeichnung. OPS-Ausnahmen/Wochenenden und gespeicherte Bereichsnamen
kommen aus den bestehenden Services/Snapshots. Keine neuen Menüdaten aus Designfeldern.
Publizierte Snapshots und historische Rezeptrevisionen werden nie überschrieben.

Neue Fachmutationen benutzen ursprünglichen Actor/Authz/Scope/CAS, bestehenden Rollenlock
und einen festen eng berechtigten Writer. Genau eine reale Änderung, Version und abgeleitetes
Audit atomar; unverändertes Speichern ohne Änderung. Bestehende Same-state-Aktionen, die
vertraglich 409 liefern, bleiben 409. Kein neues universelles Audit-JSON und kein App-INSERT
auf audit_events. UI-Polish verändert diese Verträge überhaupt nicht.

Formkontext wird serverseitig signiert, bindet ursprüngliche Identität/Berechtigung,
Objekt/Ziel/Version und CSRF. Fehler bewahren Eingaben und Originalkontext; frischer Stand
nur durch bewussten GET. Fehlende oder mehrfache Felder/Booleans als Version, ungültige UUIDs,
zu tiefe/zu grosse JSON-Dokumente werden vor Traversierung abgewiesen. 400 für ungültige
Eingabe, 401/403 für Identität/Recht, 404 für scoped fehlendes Ziel, 409 für Konflikt,
503 für beschädigte/unverfügbare Persistenz; keine rohen DB/Providertexte. Bestehende
profilspezifische Statusverträge haben Vorrang. Admin auch bei 503 no-store, keine DB-Rekursion
in Fehlerseiten. GET initialisiert oder repariert keinen Datensatz.

Öffentliche Renderer verwenden nur veröffentlichte Daten desselben Profils. Neue Design-
und Assignmentrevision sind eigene Metadaten; keine Menürevision vortäuschen. Uhr/Datum
Europe/Zurich, Rücknahme 404/410 entfernt alten Inhalt sofort, DB-Ausfall höchstens vorhandene
fünf Minuten und nie über Mitternacht. Kein Profil-/Tagesfallback, kein unbegrenzter Cache.

<a id="ui-inventar"></a>
## 3. UI-003: vollständiges Inventar und nachweisbare Reihenfolge

Statische Prüfung dieser Basis fand 110 Routendeklarationen in 111 Pythonmodulen und
75 HTML-Templates. Darin sind auch API, Redirects und reine POSTs; das ist keine Zahl
visuell abgenommener Seiten. MP-UI-INVENTORY löst tatsächliche Flask-Registrierung,
Template/Partial, Berechtigung und Zustand auf. Kein Produktstart/DB-Zugriff in diesem SDD-WP.

Inventarspalten: Modul, Endpoint/Methoden/URL, Template/Partials, Rolle, Layoutvariante,
notwendige Beispieldaten, Dialog-/Tab-/Leer-/Fehler-/Konfliktzustände, ursprüngliche Form-
und JS-Hooks, aktueller Screenshot, verantwortliches MP, Migration/Tests/Restpunkt.
Jede HTML-Route und jeder relevante Unterzustand bekommt eine Zeile. Redirect/Dateidownload/
JSON wird ausdrücklich als nichtvisuell klassifiziert und funktional gegatet, nicht verloren.
Dynamische Rollen werden anonym/Editor/Publisher/Admin getrennt geprüft, ohne Geheimnisse.

| Familie | Bestehende Routenmodule | Vollständige Templategruppe / Anschluss |
|---|---|---|
| Planung/Menüs | workflow_routes, week_management_routes, week_review_routes, menu_collection_routes | cafeteria, patienten, week_management, week_review, menu_editor, menu_collection, preview, copy |
| Komponenten | workflow_routes | components, component_editor, _country_select |
| Import | admin/routes | import_preview; bestehende CSV data-state erhalten |
| Grundlagen | master_data_routes | grundlagen, grundlagen_food, grundlagen_unit, grundlagen_vocabulary, location_conflict/unavailable; nach MP-BAS-FOUNDATIONS |
| Rezepte | recipe_routes, recipe_revision_routes, recipe_image_routes | rezepte, editor/_fields, revisionen/revision, scale, images, conflict; nach zuständigem Rezeptfreeze |
| Kochbücher | cookbook_routes | kochbuecher, kochbuch_editor |
| Ausgaben | output_routes, screen_template_routes, print_template_routes, recipe_print_template_routes, print_routes | screens, vorlagen, Zuordnung, print_template_editor/selection und sämtliche Fehlerhüllen |
| Einstellungen | display_routes, branding_routes, operations_routes | display_settings, branding_editor/preview, operations |
| Identität | local_user_routes, access_history_routes, auth/routes | local_users/create/editor/events/forms/unavailable, access_history, auth/local_login/error |
| API-UI | admin/api_routes, api/docs_routes | admin/api, api/docs; Daten-API/FHIR/MCP funktional erhalten |
| Spezialausgaben | public/routes, signage/routes | Alle public/signage-Templates einschliesslich Druck, Legende, geschlossen/unverfügbar |

Dateien mit gleicher Verantwortung werden serialisiert: gemeinsame Tokens → Shell → Makros;
danach fünf Referenzen, danach die übrigen vorhandenen Familien. Gemeinsame Dateien werden
in Folgepaketen nur konsumiert, nicht nebenbei erneut bearbeitet. Ein nachgewiesener Makro-
Fehler geht als kleiner Folgefix zurück an den zentralen Owner. Aktive Grundlagen- und
Rezeptdateien erst nach deren Freeze integrieren. Zukünftige neue Fachseiten übernehmen
dieselben Regeln in ihrem Feature-WP; diese UI-Aufgabe entwickelt keine fehlende Fachfunktion.

<a id="ui-grundlagen"></a>
## 4. Tokens, Marke, Shell und gemeinsame Komponenten

Masterprompt §§5–10 ist die einzige Wertetabelle. Vor Umsetzung aktuelle Tabler-Assets und
berechnete Styles prüfen. Konkrete Quellkonflikte: base_tabler lädt Branding zuletzt;
branding_tokens.branding_css setzt eigene Heading-Fonts und Flächen, auch mit !important-
Einzelregeln. Vorhandene Admin-Sidebar verwendet angepasste 1200-px-Grenze; der neue Standard
nennt 992 bei unveränderter Herstelleraufteilung. Tatsächlich aktive Markenwerte sind hier
nicht aus Produktion gelesen. MP-UI-BRAND-DECISION dokumentiert die Zuordnung und fordert
eine konkrete Konfliktentscheidung vor Überschreiben. Historische Brandingrevisionen/Logos
werden nicht angepasst. Keine erfundene Corporate-Freigabe und keine neue Brand-Datenmigration.

Unangepasste Adminstandards folgen dem Masterprompt; aktive abweichende Marken werden
als konkrete Kompatibilitätsfälle geprüft und nicht still übergangen. Schriftmischung,
CSS-Ladereihenfolge, Primary/RGB, Hover/Active/Focus/Disabled/Invalid müssen tatsächlich
wirken. Spezialisierte Public-/Print-/TV-Schriftgrössen und weisse Flächen bleiben geschützt.
Tokens zentral ergänzen/mappen, keine zweite Seitentokenpalette, keine Vendoränderung und
kein neues Sass-/SPA-System. System-Fontfallbacks im Referenzbrowser protokollieren.

Shell: min-width:0 im Hauptbereich, Standard/schmal/Arbeitsfläche als echte zentrale
Varianten, vorhandene Navigation aufgabenbezogen und rollenabhängig gruppieren. Aktive
Position, erreichbarer Logout, Escape/Fokus im mobilen Menü. Keine leere Topbar oder
Dashboardzahlen erfinden. Login bekommt passende Authvariante ohne Adminsidebar.

Makros konsumieren echte bestehende Daten: page_header, Felder/Hilfe/Fehler, Status, Empty
State, Pagination und Aktionen. Kein pauschales safe, kein Mega-Makro. Feldnamen, IDs,
Action/Methoden, CSRF, versionierte Formtokens und disabled/readonly-Semantik bleiben gleich.
Einseitige Pagination nur bei echtem has_next/has_prev, keine erfundene Gesamtzahl.
Touch/Fokus/Hover erklären vorhandene Symbole; häufige Aktionen sichtbar beschriftet gemäss
neuem Masterprompt. Keine neue Aktion oder Bestätigung, die Fachabläufe ändert.

<a id="ui-matrix"></a>
## 5. Referenzen, Vollmigration und Gestaltungsabnahme

Je eine tatsächlich vorhandene Referenz: Menüsammlung/Liste, Komponentenformular,
Rezeptrevisionsdetail, Darstellungseinstellung und Wochenarbeitsfläche. Nach reproduzierbarer
Prüfung konsumieren alle übrigen Familien die gefrorenen Komponenten. Referenzen sind
vorgeschlagen und werden unabhängig gesichtet. Eine Sichtung durch einen Agenten
ist keine Freigabe durch den Auftraggeber; diesen Status nur mit dessen tatsächlichem
Freigabebeleg vergeben. Vorgeschlagene Referenzen bleiben entsprechend gekennzeichnet.

Alle migrierten Routen mindestens 1440×900 und 390×844. Alle fünf Referenztypen und gemeinsame
Komponenten zusätzlich 1024×768, 768×1024 und 1920×1080. JS an/aus, Tastatur/Escape/Fokusrückkehr,
200%-Zoom, reduced-motion, leere/sparse/dichte/langtextige Inhalte und Fehler/409. Tatsächlich
installierte Browser-/Fontversion, Locale, Zeitzone, Uhrzeit, DPR und Fixturehash protokollieren.
Native Python-Playwright verwenden; toHaveScreenshot ist keine erfundene Python-Assertion.
axe nur wenn vorhanden, sonst fehlend dokumentieren und manuelle Checks trotzdem ausführen.

Computed Styles prüfen AA-Kontraste in allen Zuständen; aktuelle Mindestaktionen nach
Masterprompt, bestehende grössere Ziele nicht künstlich verkleinern. Keine 44-px-WCAG-Behauptung.
Keine horizontale Dokumentbewegung; lokale Tabellenscrollregion nur gekennzeichnet und
tastaturbedienbar. Vergleichbare Menükarten behalten gleiche Geometrie ohne Pflichttext-Clamp.
Facharbeitsflächen dürfen sinnvoll andere Layouts haben.

MP-UI-MATRIX schliesst jede Inventarzeile mit bestanden/fehlgeschlagen/nicht ausgeführt/
blockiert/begründet nicht anwendbar. Keine automatische Baselineerneuerung. Produktivdaten
nicht als Schreibfixture; Release und GET-Liveprüfung durch Root. Neue native PDF-Paintbilder
und PDF-Dateigeometrie sind getrennte Belege, keine schwarzen Browserframes als PASS.

<a id="screen-zuordnung"></a>
## 6. SCR-001: Ziele, Katalog und sichere aktive Zuordnung

Bestehender S1 bleibt lesbar: vier feste ScreenTemplate-Einträge, zwei globale
screen_assignment.v1.{profile}.web.week-Keys, activate_screen_assignment_v23.
Explizite Ohne-Bilder-URLs bleiben dauerhaft bildlos; kanonische Wochenstandards bleiben
kompatibel. Fehlende Zeile virtueller Default, beschädigte Zeile 503 statt Ersatz.
Keine Änderung registrierter Migration0020 oder v1-Dokumente beim GET.

Erweiterung schrittweise:
1. Tages-Webziel mit zwei tatsächlich verschiedenen, weissen kompatiblen Layouts; Titel,
   Menüs, Zeiten und Pflichtmetadaten vollständig. Kein Ein-Option-Speicherknopf.
2. Je TV-Ziel zwei gemessene Varianten: Tag mit gleichwertigen Kartenrastern, Woche mit
   Raster oder seitenweiser Rotation. Kein Webraster lediglich verkleinert im TV.
3. Neuer begrenzter Zuordnungsvertrag für profile × channel(web/signage) × period(day/week)
   × orientation(landscape/portrait). Zielmerkmale sind feste serverseitige Allowlist, keine
   beliebigen Settingskeys, URLs oder Jinja-Pfade. Die globale alte v1-Wochenzuordnung bleibt
   eigene unveränderte Kompatibilitätsquelle. Neue Targets verwenden eigenes v2-Schema.
4. Geräte/Gruppen referenzieren genau einen Standort und ein Profil, geprüfte Zielmerkmale
   sowie konkrete Template-/Rendererrevision. Opaque UUID ist ein veröffentlichter
   Darstellungsbezug, kein Loginsecret. Keine persönlichen Daten, Fernsteuerung oder Cookies.
   Neuer öffentlicher Gerätepfad darf nur aus der gespeicherten Zuordnung auflösen; bestehende
   vier kanonische Signage-URLs ändern weder Semantik noch akzeptieren sie Profilparameter.
5. Zeitplan/Playlist enthält höchstens 20 Einträge derselben Profil-/Zielkompatibilität,
   exakte Revisionen, Reihenfolge und 30–300 Sekunden Standzeit. Europe/Zurich-Fenster
   serverseitig auswerten, Überschneidungen ablehnen, DST/Mitternacht testen. Kein fremder
   URL-Player oder automatischer Fallbackring. Ausserhalb gültiger Belegung neutrale Fläche.

Neue SQL-Funktionen eng SECURITY DEFINER, fester search_path/revoke PUBLIC; bestehende
settings.write-Rollen und Originalauthz. App erhält nur die erforderlichen EXECUTEs,
keine Audittabellen-Schreibrechte. Actor/Location vor Zielobjekt, ursprüngliche Assignment-
CAS, genau ein fixes Audit. Archivierbare verwendete Revisionen bleiben lesbar, aktive
Zuordnung kann nicht ersatzlos verschwinden. Wiederherstellung erzeugt neuen Entwurf,
keine Änderung vergangener Revision. Unterschied zwischen Design- und Datenaktivierung
sichtbar. Schema-Reservierungsgruppe SURF-SCREEN, nach Schema27-Freeze, kein Nummernraten.

TV-Polling vergleicht neue Assignment-/Layoutrevision zusätzlich zu Menü/Branding/Datum.
Bestehende 60-s-Polls, 15-s-Timeout, keine Überlappung, 30-s-Rotation, maximal fünf Minuten
und Mitternachtsablauf bleiben. Ein Designwechsel bei gleichem Datenhash muss erscheinen.
Regressionsgate umfasst OPS, Legenden, Gleichheit und Rücknahme. Adminpreview verwendet
echte veröffentlichte Kontextdaten, fehlend 404/no-store; Entwurfsdesign ist nur autorisiert
sichtbar und erzeugt keine Veröffentlichung.

<a id="screen-editor"></a>
## 7. SCR-003: freie Gestaltung mit erlaubten Datenblöcken

GrapesJS/Puck/pdfme sind historische Kandidaten, keine Dependencyfreigabe. MP-SCR-EDITOR-DECISION
liefert einen begrenzten tatsächlichen Tabler-/CSP-/Keyboard-/Touch-Prototyp mit Quellen-
/Lizenz-/Versionsbeleg und dokumentierter Wahl. Vorhandene Bibliotheken zuerst; keine
kostenpflichtige Studio-SDK- oder zweite Adminoberfläche. Nicht funktionsfähiger Prototyp
schaltet keinen produktiven Editor frei. Entscheidung spezifiziert genau unterstützte
Engine und Version, bevor abhängige Implementierung startet.

Portabler Fachvertrag unabhängig von Engine: Dokument versioniert, höchstens 64 Blöcke,
256 KiB normalisierte JSON, Tiefe8, max20 Vorlagen und50 Revisionen pro Ziel. Zulässige
Blöcke: Logo, Bereich/Titel, Datum/Uhr, Servicezeit/Hinweis, Menügruppe, Menüfoto,
Komponenten, Herkunft, deklarierte Allergene/Labels und automatische Legende.
Bindungen sind feste IDs, keine Ausdrücke/HTML/JS/CSS/URLs/Templatepfade. Pflichtblöcke
dürfen weder entfernt noch ausserhalb des sichtbaren Bereichs verborgen werden.
Patientenziel verweigert Preisbindung bereits im Parser und im Renderer.

Entwurf, neue Revision, Duplikat, Vorschau, Aktivierung, Restore als neuer Entwurf,
Archiv/Reaktivierung bilden einen vollständigen Lifecycle mit Zielkompatibilität/CAS.
Erste nutzbare Slice liefert Titel/Logo plus gebundene Menügruppe. Diese Gruppe verwendet
bereits den vollständigen vorhandenen Renderer samt Pflichtmetadaten und Legende; sie
darf keine fachlichen Angaben bis zu einem Folgepaket weglassen. Weitere Slice macht
Metadaten/Foto/Legende separat gestaltbar und ergänzt native Geometriebedienung. Kein frei erfundener Menütexteditor
im Design: Link zum kanonischen Fachformular.
Uploads nur bestehend geprüfte lokale Assets samt Hash/Lizenz; externe Referenzen/SVG-
Skripte ablehnen. Crop/Fit darf Pflichtinformationen nicht abschneiden.
Neue Revision aktivieren nur bei tatsächlichem Renderfit; Layout im Runtimeprozess
identisch zu Preview interpretieren. API-Browsereditorpersistenz bleibt admin/settings.write.

<a id="druck"></a>
## 8. TPL-001/002/003: vollständiger Hub, native Gestaltung und Papier

Bestehend: PrintTemplateConfig acht Eigenschaften, optional layout.version1, Store-
Dokumentversionen1/2/3 mit zehn Vorlagen und50 Revisionen. Aktuelle Raster days_rows und
days_columns, Bilder/grössen, Feldreihenfolge, Legende/Kopf/Fuss sind geliefert.
Patientenlayout beginnt days_columns; Text mindestens8.5pt und Text-/Bildabstand mindestens2pt.
Keine erneute Umsetzung dieser Controls und kein behaupteter freier Canvas.

MP-TPL-FREE-DECISION vergleicht §5 Screen-/Vorlagen-Soll mit genau diesen Fähigkeiten:
verbleibende freie Anordnung, Spalten-/Zeilenmasse und Blockgeometrie an realen Wochen
demonstrieren. Natives fpdf2 bleibt Ausgangspunkt; der aktuelle Vertrag verbietet beliebige
Koordinaten. Eine Erweiterung benötigt zuerst ausdrücklich akzeptierten neuen, begrenzten
Layoutvertrag. Keine versteckte universelle JSON→PDF-Übersetzung und keine Bibliotheksfreigabe
durch dieses Planungsdokument. Freie Geometrie wird danach als neue optionale Layoutversion
implementiert, niemals in alte Revisionen injiziert.

Konkrete Mindestgrenze des Folgeformats: nur feste Fachbindungen, endliche begrenzte
Punktwerte innerhalb des A4-Inhaltsbereichs, max64 Blöcke, kein HTML/CSS/JS/Remoteasset.
Alle Pflichtfelder genau einmal, beide Cafeteriapreise und keine Patientenpreise;
Komponenten/Erklärungen dürfen wachsen oder Fit verweigern. Spalten/Zeilen bilden weiterhin
sämtliche tatsächlichen Services inkl OPS. Wochen-PDF: Cafeteria A4 hoch, Patienten A4 quer,
genau eine Seite. Überlauf nennt den betroffenen deutschen Block/Feldnamen, keine
Verkleinerung/Clipping. Reiche Kombinationen dürfen nachvollziehbar abgelehnt werden.

Preview/Download/Aktivierung rendern dieselbe gespeicherte Woche mit denselben lokalen
Assets, Template-/Brandingrevisionen. PDF-Paint, extrahierte Text-/Bildboxen, alle10/28
Menüs beziehungsweise tatsächlich erlaubte OPS-Slots und Preise/Legenden prüfen.
Unsupported neue Revision verweigert Aktivierung atomar; kein Legacyfallback.
Alte PDF-Bytes/Revisionconfigs und archive/restore/read-Verträge bleiben gleich;
neuer JSON-Writer erst mit kompatiblem Rückfallreader.

Hub zeigt echte Wochen-, Rezept-, Screen-, Menüvorlagen- und Grundlagen-Einstiege.
Rezept-PDF-Release gehört MP-REC-PDF-RELEASE; Einkaufslisten-PDF und Portionsmodell gehören
Rezeptslice (MP-REC-SHOPPING-PDF). Menüvorlagen-CRUD (MP-REC-DISH-TEMPLATE-WRITER)
benutzt vorhandene dish_templates/v26-Funktionen unter
Rezeptownership; Surface-Hub verlinkt erst registrierte reale Endpunkte und korrekte
Archiv-/Verwendungssicht, keine Attrappen. Katalog/Screen-Pflege teilen output_routes und
vorlagen.html: explizite serielle Integration, keine zwei konkurrierenden Hubowner.

Papierabnahme getrennt: berechtigte Küche prüft Lesbarkeit, kleine Symbole in Farbe/
Schwarzweiss und fachlich vollständige echte Woche. Browserzoom ist kein Drucknachweis.

<a id="iam"></a>
## 9. IAM: gelieferter Verlauf und neue Entra-Verbindungen

IAM-001 ist bereits ausgeliefert. users.manage in Reader UND Route schützt Konto-/Zugriffs-
historie; audit.read eines Publishers genügt nicht. 50er stabile Pagination, feste Provider/
Actionfilter, LEFT JOIN nur aktueller Name als Beschriftung, keine Rohdetails.
auth.login.accepted ist bestätigte Anmeldeentscheidung, kein Beweis erfolgreicher Redis-
Antwort; logout/frontchannel sind Anfragen, keine behauptete externe vollständige Abmeldung.
Auditfehler vor neuer Session führt503, Logout erreicht Response-Save/Redisdelete trotz
Auditfehler; fehlender/ungültiger Callbackflow meldet Fehler ohne bestehende Session zu löschen.
ServereventUUID identisch bei zulässigem Retry, identisches Tuple dedupliziert, abweichendes
Tuple verweigert. Keine historischen last_login_at-Backfills oder ungeprüften Actors.

IAM-002 erweitert den statischen _client/config-Pfad, ohne aktuelle lokale/Entra-Anmeldung
während Entwurfserstellung umzuschalten. Neuer Metadatenstore: connection_uuid, name,
revision, tenant_uuid, client_uuid, feste Callbackroute, opaque secret_ref+secret_version,
created_by/at, archived; separate aktive Verbindung+Revision mit Original-CAS.
Mehrere Entwürfe, genau eine aktive Revision. Limits20 Verbindungen/50 Revisionen.
Keine Secretwerte in allgemeinen Settings, Datenbankaudit, HTML, URL oder Fehlermeldung.

MP-IAM-SECRET-DECISION legt vorhandenen genehmigten Resolver fest: nur opaque Handles,
keine frei wählbaren Pfade/Envnamen; Ausgabe ausschliesslich kurzfristig im Serverprozess.
Fehlende Referenz bleibt unavailable, keine Konfigurationsdatei aus Webrequests schreiben.
Persistenz/ACL ist neuer serialisierter SURF-IAM-ENTRA-Migrationsslot nach Schema27.
Nur getrennte Issuerfunktionen schreiben, feste users.manage-Prüfung mit originalem Actor/
Authz, role/actor vor globalem Aktivslot und Zielrevision; App nur bounded Readprojektion.

Teststart bindet exakte Draftrevision, Tenant/Client/Secretversion und Callback in der
serverseitigen auth_flow. Testmodus authentifiziert den Verbindungsnachweis, gewährt aber
keine zusätzliche Anwendungssession/-Rolle. Testresultat ist zeitbegrenzt15min, signiert,
an Originalactor/Authz und unveränderte Draftrevision gebunden, nie wiederverwendbar nach
Änderung. Tenant/Object-ID bleibt Identität; keine E-Mail-Kontenzusammenführung.
Claims nur nach MSAL-Validierung; erlaubte Rollennamen, aud/tid/oid und Duplikate prüfen.
Anonymen Callback nicht als verifizierten Administrationsactor auditieren.

Aktivierung benötigt diesen erfolgreichen Test sowie Original-Draft-/Aktivslot-CAS und
nachweislich verbleibenden aktiven lokalen Admin. Fehler bewahrt bisherige Aktivierung.
Bereits gestartete normale Loginflows behalten ihre gepinnte alte Revision während eines
Wechsels, maximal die bereits genehmigte Flowlebensdauer. Secretversion bis Ende solcher
Flows/zulässiger Rückkehr behalten; keine automatische Garbage-Collection aktiver Historie.
Rollback ist explizite Reaktivierung einer weiterhin testbar gültigen Revision, keine
DB-/Env-Restauration. Neu scheiternder Provider lässt lokale Anmeldung erreichbar.
Paralleltests für letzten lokalen Admin, Actorrevocation, zwei Aktivierer und A→B-Wechsel
mit noch laufendem A-Callback sind Pflicht. Keine produktiven Tenanttests ohne zugewiesenen
Testtenant und ausdrücklich berechtigte Identitäten.

<a id="abnahme"></a>
## 10. Abnahme von Marke, Symbolen, API, Daten und Player

BRD/DSP: echtes Standard-/Custombrand mit Logo und absichtlich logoNone; Cachealtantworten,
Kontrast, Fonts, zwei Sitzungen und alle Settingszustände. Ein fehlender eigener Logo-Datensatz
ist nicht anwendbar oder blockiert, kein erfundenes PASS. Public bleibt weiss, Adminwerte
ändern weder Signage-Minimalschrift noch PDF-Seitengrösse.

ICO: gemeinsame gepinnte14 Allergengruppen, bekannte Länder und tatsächlich deklarierte
VEG/VGN; Slot VEGETARISCH ist kein automatisches Veganlabel. Legende nur sichtbare Daten,
dedupliziert stabil, contains/may_contain/unknown getrennt. Keine freien Länderflaggenpfade
oder Emojiabhängigkeit. Unbekannt ergibt Textfallback, nicht allergenfrei.

API: vorhandene REST-v1/OpenAPI/Swagger, FHIR-R5-Leser und MCP nicht neu implementieren.
Readerauth, profilsicheres Snapshot, Schlüsselrechte/Revocation/Cache/No-store und exakte
Schnittstellen-Smokes bei Änderungen behalten. Externe Clientabnahme bekommt konkreten
erlaubten Client, Schlüssel durch vorhandene Verwaltung und berechtigten Operator;
keine neuen API-Schemas oder Keys allein für UI-Polish. Kein API-Key in Screenshots/Reports.

DATA: 32 reale Gerichte/76 Vorkommen/61 Rezepte/100 Foods sind eingefrorener ungeprüfter
Datenentwurf unter MP-REC-DATA-DRAFTS, kein Import/Bestandsnachweis. MP-REC-IMPORT-BATCH
persistiert Provenienz; Surface-Datenabnahme liest konkrete importierte Revisionen und
dokumentiert Kitchen-Entscheid mit Quelle und unverändertem Original-CAS. Neue Mengen/
Allergenangaben bleiben Vorschläge bis bewusster fachlicher Übernahme. Keine veröffentlichte
Quellwoche umschreiben. Fehlende bestätigte Positivlabels halten nur CAT/DATA-Abnahme offen,
nicht unabhängige Editoren oder Bestandscode. Bestehende Human-Reviewpfade wiederverwenden.

QA: vier Web- und vier Signage-Routen, zusätzlich explizit bildlose Wochen und HTML-Druck.
Desktop/Mobile sowie1920×1080/3840×2160, relevante Hochformate, Zoom, Rücknahme, Datumswechsel,
Ausfall und Wiederanlauf. Native DOM-Geometrie muss semantische äussere Karten messen:
cafe-week-day rund/clipped, innere cafe-week-slot darf flach sein. Kein blanket radius>0
als visueller Fehlernachweis. Oberer Farbrand/Foto überdeckt keine Kartenrundung.
Synthetische HTTP-Fixture und tatsächliche Livepublikation klar getrennt labeln.
Patienten-FHD mit vollständiger nachvollziehbarer Rotation ist neu akzeptierter Ansatz;
ein heruntergezoomtes28-Slot-4K-Raster ist kein FHD-PASS.

Physisches Yodeck/Raspberry Pi4B separat: tatsächliche Hardware/RAM/OS/Chromium, Auflösung,
Zoom/Refresh, Betrachtungsabstand, Rotation, Offline/Netztrennung und Mitternacht dokumentieren.
Nur autorisierter Testplayer, keine Änderung eines fremden Kontos. Papier- und Kitchen-
Abnahmen brauchen benannte Person/Datum/Version und offene Befunde. Fehlende externe Eingabe
blockiert nur das jeweilige external_acceptance-Paket.

<a id="pakete"></a>
## 11. Startfähige WPs, Prüfumgebung und Rückweg

[surfaces-wps.json](surfaces-wps.json) ist der ausführbare DAG dieses Slices.
Jedes MP nennt zulässige Dateien, konkrete Anschlussstellen, Voraussetzungen, Kriterien
und Gatefamilie. proposed:-Pfade sind ausdrücklich neu anzulegende Dateien, keine bereits
vorhandenen Tests. geteilte Registrierungen/SQL/Hubdateien nur seriell.
READY bedeutet fachliche Voraussetzungen vorhanden; Orchestrator weist vor Ausführung
aktuellen Worktree/Pool/Wrapper zu. Kein alter Port aus einem Bericht ist eine Reservierung.

Gemeinsame Dateien erhalten eine ausdrückliche exklusive Owner-Sperre vor jedem Schreib-WP:
SCHEMA-WRITER-LEASE umfasst schema/permissions/validate_schema/db/validate_package und
alle Versions-/Inventarverträge; REGISTRY-WRITER-LEASE umfasst gemeinsame Blueprint-
Registrierung und von mehreren Features berührte Hubs. Root vergibt diese Sperren nach
aktuellem Freeze und prüft den vollständigen Pfadvertrag. Zwei fachlich unabhängige DAG-
Knoten dürfen solche Dateien trotzdem niemals parallel ändern. RESERVED_*.sql sind
ausdrücklich Platzhalter für die spätere serielle Reservierung, keine ausführbaren oder
bereits registrierten Migrationsdateien. UI-Polish reserviert überhaupt keine Migration.

Bestätigte native Testschnittstelle ist Python -B -m pytest, installiert pytest9.0.2.
Der generische Hostname python ist in dieser Umgebung nicht vorhanden. Deshalb nennt JSON
TESTGATE/ BROWSERGATE mit exakter relativer Testliste als bewusst noch zuzuweisenden Harness,
statt einen nicht vorhandenen universellen Befehl zu behaupten. Der Orchestrator bindet
den realen Python-/Browserpfad nach execution-contract.md; keine Installation.
Dieses Dokument-WP führt ausschliesslich Struktur/Quellen/Graph/Secret/Diffprüfungen aus.

Für jede neue Persistenz gilt: Vorwärtsmigration registrieren, Freshschema identisch,
App-/IssuerACL und historische Migrationbytes testen. Rückfallimage muss neue gespeicherte
Revisionen lesen und dieselbe Zielsemantik bewahren; andernfalls Forward-Fix.
Kein JSON-Downgrade, kein Snapshotrewrite und kein Dump-Restore als gewöhnlicher UI-Rückweg.
Reine UI-Änderungen können durch vorherige kompatible Templates/Assets zurückgenommen werden,
ohne Daten/Scopes/Reviewzustand anzufassen. Root integriert regelmässig geprüfte kleine Wellen;
physische/externe Freigaben bleiben als eigene offene Nachweise sichtbar.

<a id="public-white-polish"></a>
## 12. Öffentliche Weiss-Politur und obere Kartenkante

Dieser Abschnitt trägt genau ein kleines Paket, `MP-UI-PUBLIC-WHITE-POLISH`. Er
beschreibt keine Admin-Migration und löst keine Kaskade über die Verwaltung aus.

### 12.1 Belegter Ausgangsbefund

Grundlage sind die vorhandenen Live-Aufnahmen vom 8. September 2026, 23:33 UTC,
unter `.claude/state/ops-root-evidence-0908/recipe-pdf-public-live-2333/`. Alle
zwölf Aufnahmen sind mit HTTP 200, ohne Konsolenfehler und ohne fehlgeschlagene
Requests erfasst; `INDEX.json` führt je Aufnahme URL, Viewport und SHA-256.

| Aufnahme | Befund |
|---|---|
| `mobile-cafeteria-woche-390x844.png` | Das erste Gerichtselement beginnt erst bei rund `y = 613`. Davor liegen Kopfleiste, Bereichszeile, grosse Datumsüberschrift, erklärender Fliesstext, der Knopf «Tagesansicht», das Kalenderwochen-Badge und eine zweizeilig umbrechende Tagesleiste. |
| `signage-cafeteria-tag-1920x1080.png` | Zwischen der Komponentenzeile und dem Fussbereich jeder Menükarte steht ein grosser leerer Streifen. Das Bild selbst ist zusätzlich seitlich weiss ausgelegt. |
| `website-cafeteria-woche-1440x1100.png` | Root sieht abgerundete Karten und abgeschnittene Farbstreifen. Die frühere Beanstandung bleibt ein genauer Browser-Prüfpunkt; diese Aufnahme allein beweist keinen fortbestehenden Rundungsfehler. |

Relevante Quellstellen dieses Prüfstands; ihre Wirkung ist im Browser zu messen:

- `reference_scaffold/cafeteria/static/public.css:.public-page .week-nav .nav-link`
  setzt `flex: 1 1 6rem`. Fünf Tageseinträge mit Abständen überschreiten damit auf
  390 Pixeln die verfügbare Breite und brechen in eine zweite Zeile um.
- `reference_scaffold/cafeteria/static/public.css:.public-page .page-header`
  ergänzt `margin-top: 2rem` zusätzlich zum Vorspann aus
  `templates/public/cafeteria_week.html`.
- `reference_scaffold/cafeteria/static/signage.css:.hero-food-media` deckelt das
  Bild bei `max-height: 34vh`, während `.hero-food .content` und `.hero-food>footer`
  auf `flex: 0 0 auto` stehen. Der Rest der Kartenhöhe bleibt deshalb als Leerraum
  zwischen Inhalt und Fuss stehen.
- Die Rundungsabsicht existiert bereits: `public.css` klammert mit
  `.public-page .card { overflow: hidden }` und `signage.css` mit
  `.signage-shell .card { overflow: hidden }` sowie
  `.signage-shell .card-status-top { inset-inline: 0; top: 0 }`. Die Clip-Geometrie
  ist im Browser zu prüfen. Nur eine nachgewiesene Abweichung wird korrigiert.
  Gleiche berechnete Radien von Elternkarte und dünnem Farbstreifen sind dafür
  kein geeigneter Test; korrektes Clipping der gerenderten Kante ist entscheidend.

### 12.2 Sollverhalten

Die öffentliche Fläche bleibt weiss und minimalistisch. Der Vorspann führt auf
kleinen Breiten kompakter zum Inhalt, die Tagesleiste bleibt einzeilig oder wird
zu einem erkennbaren, tastaturbedienbaren horizontal scrollbaren Bereich. Der
freie Restplatz der TV-Tageskarte geht an die vorhandenen Inhaltsblöcke statt als
Leerstreifen stehen zu bleiben. Die obere farbige Kartenkante folgt in Web und
Signage exakt der Kartenrundung.

### 12.3 Ausdrückliche Nicht-Ziele

Logos, Menüinhalte, Preise, Allergen- und Herkunftsangaben, Schriftgrössen und
Lesbarkeit bleiben unverändert. Tages-, Wochen- und TV-Semantik sowie die
Erreichbarkeit aller Inhalte bleiben erhalten. Nur die ausdrücklich beschriebene
Navigation darf einen lokal begrenzten Scrollbereich bekommen. Es entsteht **keine** Variante mit
farbigem Hintergrund und keine zweite Kartenkomponente. Die Bildanpassung
`object-fit: contain` in `signage.css` bleibt unangetastet: ein Wechsel auf
`cover` würde Speisefotos beschneiden und ist hier ausdrücklich nicht Teil des
Auftrags. Admin, Tokensdatei, öffentliche und Signage-Routen sowie Datenbank
bleiben unberührt.

### 12.4 Besitz und Reihenfolge

Dieses Paket kann auf dem ausgelieferten Public-Vertrag5f5 beginnen. Es benötigt
weder Schema27 noch künftige neue Screenvarianten oder Admin-Tokens. Root reserviert
alle besessenen Dateien exklusiv; `MP-SCR-TV-VARIANTS` und spätere Tokenarbeit
dürfen dieselben Dateien erst nach Rückgabe dieses Besitzes bearbeiten und müssen
die Politur erhalten. Gemeinsame Pfade sind Dateileases, keine künstliche
Funktionsabhängigkeit. `tokens.css` bleibt lesend; die vorhandenen Tokens werden
verwendet. `cafeteria_today.html` und `patient_today.html` bleiben ebenfalls lesend.
`MP-UI-MATRIX` und `MP-UI-RELEASE`
hängen an diesem Knoten, damit die Politur in der Abdeckungsmatrix und im Release
tatsächlich erscheint.

### 12.5 Abnahme

Geprüft wird in allen fünf Master-Viewports aus dem kanonischen Designstandard:
1440 × 900, 1024 × 768, 768 × 1024, 390 × 844 und 1920 × 1080. Die tatsächlich
ausgeführten Kombinationen gehören in die Abdeckungstabelle.

Messbare Kriterien bei den dokumentierten stabilen Referenzdaten und 100% Zoom:
erstes Gerichtselement bei 390 × 844 oberhalb von `y = 520`;
Tagesleiste einzeilig oder ausgewiesen scrollbar; Leerstreifen der TV-Tageskarte
höchstens 24 Pixel; kein sichtbarer Farbstreifen ausserhalb der gerundeten
Kartenkontur, belegt durch Browsergeometrie und vergrösserte Eckaufnahmen;
keine horizontale Seitenscrollbar bei 390 Pixeln. Jeder Wert wird als gemessene
Zahl belegt, nicht als Behauptung. Lange Inhalte und 200% Zoom bleiben vollständig
erreichbar; die Positionsziele dürfen nicht durch kleinere Schrift oder abgeschnittene
Inhalte erzwungen werden.

Neue Screenshots sind **vorgeschlagene** Referenzen. Sie dürfen nicht als vom
Auftraggeber freigegebene Baseline ausgegeben werden, und fehlschlagende
Vergleiche werden nicht blind aktualisiert.
