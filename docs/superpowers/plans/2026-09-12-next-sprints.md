# Dishboard — nächste Sprints nach der Korrekturwelle

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Alle tatsächlich offenen ursprünglichen und neuen SDD-WPs umsetzen. Der vollständige Dichteauftrag vom 13. September gilt für sämtliche UI-Seiten; der Rezepteditor ist erste Referenz. Gerichtvorlagen und Rezepte werden in beide Richtungen verbunden, Vorlagen einer konkreten Tagesplanung zugeordnet und Rezeptansicht, Druck sowie Druckvorlagenwahl ergänzt. Regelmässige geprüfte Deploys; Tests am Sprintende, danach gezielte Korrektur.

**Architecture:** Die 145 ursprünglichen MP-Verträge und sieben geprüften Feature-WPs bleiben erhalten. 24 Dichtepakete ergänzen UI-00 bis UI-09 des neuen Auftrags im bestehenden surfaces-wps.json: insgesamt 176 WPs. Dieser Plan ergänzt Lieferstand, Anschlüsse und Reihenfolge; vorhandene korrekte Implementierungen werden geprüft und konsumiert. Gemeinsame SQL- und UI-Verträge haben jeweils genau einen Besitzer.

**Tech Stack:** Bestehendes Flask/Jinja/Tabler, PostgreSQL 18.6, Redis, Docker Compose und vorhandene Python-/Playwright-Testumgebung. Keine neue Dependency durch diesen Plan.

**Spec:** `docs/superpowers/backlog-0909/{recipes,operations,surfaces}-sdd.md`, zugehörige `*-wps.json`, `execution-contract.md`, `docs/BACKLOG.md`, `docs/design/2026-09-09-unified-ui-design-system.md`, `docs/design/2026-09-12-patientenplan-menueditor-korrektur.md`, [Feature-SDD Gerichtvorlagen, Rezepte und Tagesplanung](../../design/2026-09-13-gerichtvorlagen-rezepte-planung-sdd.md).

**Baseline (fest am 13. September, 05:05 CEST):** Live und Integrationsbasis sind 0202fd518565fd7068ba8430b2d50641abec2cf8 (Report12774; Schema30, gesund, OCI-Revision und Appcheckout stimmen). Enthalten sind COMPONENTS e5abc1f plus anderer Autor3ee95ab, Architektur-/Tokenversionsklarstellung97ed530 und aktueller Inventaranschlussd13f7fe. Vorherige Releases b62e5db (04:28) und f32fc70 (03:59) behalten ihre eigenen Belege. Historische erste Workerbasis a420992 und alte Capture-/Quellstände bleiben unverändert. Aktive Worker behalten ihre genau zugewiesenen Basen; dieser Docs-WP rebasiert niemanden.

Der integrierte Planfix `wp-8bdb4f7321bd` basiert auf `2a9aed10b394e4d76bb58bd5e384a81fff84af0a` und korrigiert die beiden Befunde aus Review `wp-e7b99a14a8a0`. Der zusätzlich von Root freigegebene Graphabgleich ergänzt für PLAN-PORTIONS die bereits dokumentierten Vorgänger SHARED (`admin.js`) und MENU-PROPOSAL (`menu_editor.html`); die Featureabfolge bleibt dieselbe. Die damaligen Produktworker behielten ihre ausdrücklich zugewiesene Basis `a420992ae91fd801d0ec43d41038f57bbdd3b261`; der Dokumentstand war kein Auftrag zum Rebase und kein Produkt-/Abnahmebeleg.

**Planungsstatus:** 176 WPs und 35 Anforderungen bleiben erhalten. VIEW-PRINT/History, SHARED, WEEKS, Inventar, SHELL, MENUEDITOR und COMPONENTS sind mit den unten genannten Grenzen deployed; OPS-/OFF-Dokumente sind integriert und Bestandteil belegter Releases. Binding- und Foundations-Reviewfix, Cookbooks und Lists arbeiten in vier getrennten Grants. Reale Nutzerabnahme, vollständige Dichte-/Viewportabdeckung und finale Menüvorlagenzuordnung bleiben offen. Aktuelle Grants und Rootreservierungen stehen im Sitzungsabschnitt von file-leases.json; historische Vorschläge erteilen kein Schreibrecht.

## Dichteauftrag 13. September

Normative Regeln, alle zwanzig Mockups und A01-A24 stehen ausschliesslich im bestehenden [zentralen UI-Manifest](../../design/2026-09-09-unified-ui-design-system.md). Quelle ist der vollständige Nutzeranhang `pasted-text-1.txt` vom 13. September. Dieser Abschnitt plant die Ausführung und begründet keine zweite Stilwelt.

| Paket | Ergebnis | Muster | Vorgänger / Besitzübergabe |
|---|---|---|---|
| `MP-UI-DENSITY-INVENTORY` | Aktuelles vollständiges UI-Inventar und Dichtebefunde | M01, M20 | Feste Basis, kein fachlicher Vorgänger |
| `MP-UI-DENSITY-MANIFEST` | Ein zentrales Dichtemanifest und verbindliche Agentenregeln | M01-M20 | Feste Basis, kein fachlicher Vorgänger |
| `MP-UI-DENSITY-RECIPE` | Kompakter Rezepteditor als erste gemeinsame Referenz | M02, M03, M04, M05, M06, M19 | Feste Basis, kein fachlicher Vorgänger |
| `MP-UI-DENSITY-SHARED` | Gemeinsame Zeilen, Details und Aktionsmuster über Verwendungstypen absichern | M01, M03, M05, M19 | MANIFEST, RECIPE |
| `MP-UI-DENSITY-SHELL` | Aufgabenrahmen, dezente Navigation und echte Arbeitsbreite | M01 | SHARED |
| `MP-UI-DENSITY-COMPONENTS` | Bausteinliste, Filter und Allergeneditor verdichten | M08, M13, M19, M20 | SHARED |
| `MP-UI-DENSITY-FOUNDATIONS` | Zutaten, Einheiten, Lagerorte und Vokabular kompakt bearbeiten | M08, M13, M15, M19, M20 | SHARED |
| `MP-UI-DENSITY-MENUEDITOR` | Menüeditor und gespeicherten Prüfkontext verdichten | M12, M19 | SHARED |
| `MP-UI-DENSITY-LISTS` | Menüsammlung und Wochenwahl stellen Auswahl vor Verwaltung | M07, M09, M20 | SHARED |
| `MP-UI-DENSITY-WEEKS` | Cafeteria- und Patientenraster ohne Verwaltungswand | M10, M11, M19 | SHARED |
| `MP-UI-DENSITY-COOKBOOKS` | Kochbücher und Zuordnungen kompakt und eindeutig | M03, M05, M18, M19, M20 | SHARED |
| `MP-UI-DENSITY-RECIPEPAGES` | Rezeptliste, Revisionen, Skalierung, Bilder und Vorlagen im Gesamtinventar | M07, M14, M18, M19, M20 | SHARED, MP-REC-RECIPE-VIEW-PRINT, MP-REC-MENU-PROPOSAL |
| `MP-UI-DENSITY-PREVIEW` | Gewählte Woche und veröffentlichte Ausgabe getrennt drucken | M14 | SHARED |
| `MP-UI-DENSITY-HUBS` | Ausgabehubs und Vorlageinstiege kompakt anschliessen | M14, M20 | SHARED, MP-TPL-RECIPE-DISH-ENTRY |
| `MP-UI-DENSITY-PRINT` | Bestehende Drucklayouteditoren auf verständliche Arbeit ausrichten | M14, M15, M19 | SHARED, MP-REC-PRINT-TEMPLATE-ENTRY, MP-REC-RECIPE-VIEW-PRINT |
| `MP-UI-DENSITY-SCREENS` | Bildschirm- und Darstellungsverwaltung kompakt halten | M14, M15, M20 | SHARED |
| `MP-UI-DENSITY-SETTINGS` | Bereiche und Zeiten mit lokaler gezielter Bearbeitung | M15, M19 | SHARED |
| `MP-UI-DENSITY-BRANDING` | Gespeicherten Markenentwurf und Vorschau klar darstellen | M16, M19 | SHARED |
| `MP-UI-DENSITY-IMPORTS` | Import, Vorschau, Kopieren und Wochenprüfung auf Aufgabe ausrichten | M17, M19, M20 | SHARED |
| `MP-UI-DENSITY-USERS` | Benutzer-, Rechte- und Ereignisverwaltung vereinfachen | M18, M19, M20 | SHARED |
| `MP-UI-DENSITY-API` | Schnittstellenverwaltung ohne technische Informationswand | M15, M18, M19, M20 | IMPORTS |
| `MP-UI-DENSITY-REGRESSION` | Alle inventarisierten UI-Seiten tatsächlich bedienen und vergleichen | M01-M20 | INVENTORY, SHELL, COMPONENTS, FOUNDATIONS, MENUEDITOR, LISTS, WEEKS, COOKBOOKS, RECIPEPAGES, PREVIEW, HUBS, PRINT, SCREENS, SETTINGS, BRANDING, IMPORTS, USERS, API |
| `MP-UI-DENSITY-FUTURE` | Vorhandenes Inventar- und Browsergate gegen neue UI-Lücken ergänzen | M01-M20 | REGRESSION |
| `MP-UI-DENSITY-USABILITY` | Drei technisch unerfahrene Personen beobachten und Abnahme dokumentieren | M01-M20 | REGRESSION |

Die vollständigen Dateien, Kriterien, Testbefehle, Risiken und externen Eingaben stehen in `surfaces-wps.json`. Regel-/Muster-/Abnahme-IDs beziehen sich auf den neuen Dichteauftrag, nicht auf gleichnamige historische P01/A01-Korrekturen. Geplante Familien werden nach dem echten Inventarabgleich weiter geteilt, falls ein einzelner prüfbarer Diff zu gross wird. Direktseiten, Dialoge, Rollen, Leerzustände und Fehler bleiben Bestandteil ihres Besitzers.

Ausführungsfolge:

1. Manifest und Rezeptreferenz parallel auf a420992; Druckvorlagen-Einstieg in eigener Codex-CLI-Lane. Rezeptmenge/Einheit und native Strukturaktionen zuerst sichtbar liefern. Root pflegt Inventar-/Besitzplan. Kein Warten auf sämtliche späteren Fachketten.
2. Sprintgate der betroffenen Abläufe und gemeinsame Layouttypen; unabhängiger Review, Fix durch anderen Autor. Manifeste aus sauberem Export, Fast-forward-fähige Integration mit zwischenzeitlichem github/main, Push und Deploy mit Apprevision/Image/Schema/HTTP-Beleg.
3. Gemeinsame Rezeptmuster einfrieren, zentrale Details/Zeilen weiterverwenden. Danach Shell/Cafeteria/Patienten und unabhängige Baustein-/Stammdaten-/Kochbuchseiten parallel, maximal fünf schwere Jobs.
4. MENUEDITOR und WEEKS zunächst auf der gemeinsamen Dichtebasis einfrieren; MENU-TEMPLATE-BINDING wartet auf beide Freezes und liefert danach den Vertrag für PROPOSAL. LINK-READS und PRINT-TEMPLATE-ENTRY gehen VIEW-PRINT voraus; DENSITY-PRINT folgt VIEW-PRINT. RECIPEPAGES wartet auf VIEW-PRINT und PROPOSAL. Jede gemeinsame Datei wird in dieser Richtung übergeben; unabhängige Einstellungen, Ausgabe, Benutzer und Import laufen weiter.
5. Gesamte Route-/Rolle-/Zustandsmatrix über `tests/test_ui_route_inventory.py` tatsächlich bedienen und mit `create_app()` abgleichen; `test_capture_before_screenshots_and_manifest` erzeugt die App-Captures, `tests/test_ui_inventory_capture.py` bleibt zusätzlich als Recorder-Selbsttest im Gate. Alle Seiten 1440×900 und 390×844; gemeinsame Typen zusätzlich 1024×768, 768×1024, 1920×1080, 2560×1440, echter 200%-Zoom und 320-CSS-Pixel-Reflow. Gleiche synthetische Vorher/Nachher-Daten und aktuelle Capture-Artefakte verwenden. Root weist Wrapper, exklusiven Pool und separates Capture-Ziel vor Ausführung zu; Testzahlen/Skipgründe, tatsächliche Rollen/Zustände/Viewports und fehlende Belege offen ausweisen. Kein Gesamt-PASS bei übersprungenen DB-/Browserprüfungen oder allein durch Recorder-Selbsttests. Physische Nutzer-/Papier-/Playerabnahmen bleiben getrennt.
6. Ursprüngliche Fachketten dieses Plans weiter umsetzen: Mengen/Einkauf, Kosten/Lager/Bestellung, URL-/Nährwert-/OFF-/Quellenarbeit sowie Screens/IAM. Reale externe Voraussetzungen blockieren ausschliesslich ihre abhängigen WPs. Kein Abschluss nach Manifest oder Rezepteditor allein.

Erste Bestandsabweichung: auf a420992 existieren 82 HTML-Templates, die Matrix enthält nur76 und nennt in Metadaten75. Mindestens fünf Gerichtvorlagen- und fünf Rezeptimport-Batch-Routen fehlen; Schema25/5f5-Angaben sind historisch. Der bestehende `test_ui_route_inventory.py`-Abgleich mit `create_app()` wird erweitert, kein zweites Inventarwerkzeug eingeführt. Ein statischer Fund ist kein Browser-PASS.

Besitzserialisierung: `admin-tabler.css` RECIPE → SHARED → SHELL; `admin.js` RECIPE → SHARED → PLAN-PORTIONS; `_macros.html` ausschliesslich SHARED, bevor nachfolgende Seiten die gemeinsame Basis übernehmen. `menu_editor.html` MENUEDITOR → MENU-TEMPLATE-BINDING → PROPOSAL → PLAN-PORTIONS; `_week_menu_card.html` WEEKS → MENU-TEMPLATE-BINDING. Rezept-/Druckvorlagenlinks PRINT-TEMPLATE-ENTRY → VIEW-PRINT → PRINT/RECIPEPAGES. Tool-Browsertest IMPORTS → API. Routenmatrix und beide vorhandenen Tests `test_ui_route_inventory.py`/`test_ui_inventory_capture.py` INVENTORY → REGRESSION → FUTURE; `ui-before-manifest.json` INVENTORY → REGRESSION. Release-Manifeste gehören ausschliesslich Root; fremde site/*-Arbeit wird erhalten und separat auf Aufnahme geprüft.

Der integrierte RECIPE-Vertrag enthält `reference_scaffold/tests/test_recipe_density_browser.py` für Dichte-Fixtures und Interaktionen. `test_recipe_browser.py` und `test_ui_korrektur_recipes_browser.py` bleiben im Vertrag und Testplan. Die vorhandene Vendor-Sprite-Datei und ihr Lock kamen für den unabhängig geprüften Iconfix hinzu; der bestehende datengetriebene Generator blieb unverändert. Der abgeschlossene Grant dokumentiert diesen Besitz, reserviert ihn aber nicht weiter.

Stand 13. September, 02:02 CEST: Druckvorlagen-Einstieg `5c9fa4a`, Inventar
`d983860`, Manifest `39625cc` und separat geprüfter Planfix `7ba8f70` sind in
Release `3ee090d6cb5cc4b6f7863b1a8746fb53d77cfa6e` integriert und live. Der
integrierte Sprintgate bestand mit 100 Tests; vollständige Screenshot-Neuerfassung
blieb ausdrücklich ausgenommen. Image-Revision, Health und Schema 30 sind belegt.

Aktuelle Anschlussentscheidungen: RECIPE übernimmt vor SHARED den bestehenden
Viewport-/Fokushandler in `admin.js` auch für seine mobile Speicherleiste samt
`test_ui_menu_editor_browser.py`. LINK-READS erhält ungespeicherte Formularwerte
bei Suche/Blättern über ein CSRF-geschütztes POST-Intent zur reinen Neuanzeige;
GET bleibt für frische Einstiege. Der SDD-Abschnitt 4.1 und der WP-Vertrag sind
entsprechend präzisiert. Der getrennt autorierte Patientenpreis-/Grid-Testfix
`41b2b6ed76943159f968262a14079f021c8f8244` ist in `dcfc027253a84abd4ecbe8ea7267bfe3d1b4de0d`
integriert; Root prüfte unabhängig CLEAN und 21 Tests in 1,09 Sekunden. Sein
Dateibesitz ist freigegeben.

Lieferstand des festen 05:05-Snapshots (wp-936d57b0846f):

| Lieferung | Unabhängiger Beleg | Status und Grenze |
|---|---|---|
| History/VIEW-PRINT311, SHARED338, WEEKS5358 und Inventar68a89 | Release f32fc70, 03:59 CEST, Report12749; bestehende Root166/49/45 sowie Inventar9 PASS und ein Capture-Deselected bleiben dokumentiert | DEPLOYED; kein vollständiger UI-Capture-Sweep oder Abschluss aller Dichtekriterien |
| OPS5e / OFFfe407 | In f32fc70 enthaltene unabhängig geprüfte Test-/Dokumentlieferungen | INTEGRATED und ausgeliefert; ursprüngliche Fehlversuche und fehlende externe Abnahmen bleiben getrennt |
| SHELLf0a93ac | In b62e5db, 04:28 CEST; Review12755 CLEAN, Root16 PASS221,45s | DEPLOYED; ersetzt die vorher nur teilweise Testalignment-Lieferung8c666; physische/Novizenabnahme offen |
| MENUEDITORf86191f + AGY5d18690 | In b62e5db; ursprünglicher P2-Stickybefund erst durch anderen Autor geschlossen, Review12756 CLEAN; Root65 PASS12 intentionale Skips179,81s plus Fix4 PASS2 intentionale Skips14,95s | DEPLOYED; ursprünglicher Page-Scale-Probe ist kein Beleg für echten Browser200%-Zoom |
| COMPONENTSe5abc1f + 3ee95ab | In0202fd5, 05:05 CEST, Report12774; Review12766 CLEAN, Root57 PASS135,94s und12 Makroprüfungen0,94s; integriert27 PASS1 Capture-Deselected52,40s | DEPLOYED; Länderklartext und konsistente Allergenanzeige, bestehende NoJS-Schreibgrenze bleibt ausdrücklich erhalten |
| Architektur-/Tokenvertrag97ed530 und Inventard13f7fe | In0202fd5, Reviews12768/12771; bisherige historische Capturebelege erhalten | Dokument-/Quellenanschluss; kein zusätzlicher visueller oder fachlicher Abnahmebeleg |

Aktuelle Writer am selben Stichtag:

| WP / tatsächlicher Executor | Exklusiver Besitz | Basis / Worktree / Pool |
|---|---|---|
| MENU-TEMPLATE-BINDING wp-a127e7b49932, native components_reviewfix | Original13 inklusive menu_template_binding.py; bisherige sieben Reparaturpfade sind darin enthalten, kein zusätzlicher Owner. Originalautor gestoppt | 4c0a76b; menu-binding-reviewfix-0913, fix/menu-binding-reviewfix-0913; test-api3 PG32788/Redis32789 |
| FOUNDATIONS wp-c51fd9379326, AGY | Original8 plus test_master_data_browser.py, test_master_data_routes.py, test_master_data_prepared_browser.py | 0c40299; foundations-reviewfix-agy-0913, fix/foundations-reviewfix-agy-0913; test_ui_other PG32853/Redis32854 |
| COOKBOOKS wp-f3edc88fef0f, Claude Code via CSD | kochbuecher.html, kochbuch_editor.html, test_ui_korrektur_cookbooks_browser.py | b62e5db; density-cookbooks-claude-0913, feat/density-cookbooks-claude-0913; test-recipe-print-0908 PG32865/Redis32866 |
| LISTS wp-30852ec2ac03, native density_components | Original5 plus genehmigter test_menu_collection_browser.py für Standardliste/Kartenumschaltung | d340b79; density-lists-0913, feat/density-lists-0913; test-recipe-template-editor-0908 PG32823/Redis32867 |

Binding4c0a76b ist trotz62 Autorprüfungen nicht integriert: Review12770 bestätigt P1 zu veralteten Berechtigungen bei409 und P2 zur standortübergreifend neu gebundenen signierten Quelle. Foundations0c40299 ist nach drei Befunden12764 und zweimal Root8 PASS1 FAIL ebenfalls offen. Cookbooks/Lists erhalten am Stichtag keine Freeze-/Review-/Deploybehauptung.

Alle vier Grants sind dateidisjunkt und reservieren unterschiedliche bereits zugewiesene Pools. Zusammen mit genau einem Root-Gate oder Deploy gelten höchstens fünf schwere Jobs. Kein Neustart gestoppter Container. Root behält Release-Manifeste und beide aktuellen Inventar-JSONs. Der frühere SHELL-/MENUEDITOR-/Inventarbesitz ist abgeschlossen und freigegeben; untere historische Lease-Quellen, elf ältere Completed-Objekte und Capturebelege werden nicht neu geschrieben.

Die aktuelle Quellenbesitzliste im aktiven Leaseabschnitt ergänzt den historischen Snapshot für alle aktiven Pfade, einschliesslich des bereits genehmigten Binding-Helfers. Zukünftige weitere WP-Ansprüche sind sichtbar, gewähren aber keine gleichzeitigen Schreibrechte. Die Recipe→VIEW-PRINT-Übergabe des zwanzigsten History-Testconsumers sowie bestehende Editor-/Vendorhunks bleiben unverändert.

Ausführung erfolgt nach der tatsächlichen Root-Zuweisung, unabhängig von Routerempfehlungen. Dieser leichte Dokumentations-WP führt nur Validator, JSON-/Checksum-/Dateibesitz-/Serialprüfung aus. Fullsuite, echte Anfänger, physische Geräte, vollständige Dichteabnahme und finale Menüvorschlagszuordnung sind damit nicht abgenommen. Spätere Workerereignisse bleiben im operativen Root-Ledger; dieser Snapshot wird nicht fortlaufend nachgezogen.

## Global Constraints

- Aktuelle Nutzeranweisungen vor historischen Dokumentständen; „SDD“ bezeichnet die vorhandenen Software-Design-Verträge.
- Patientenkanal strukturell ohne Kostenfelder oder Kostenwerte; getrennte Profile und unveränderliche Publikationsrevisionen erhalten.
- Originalactor, Berechtigungsversion, Standort, CAS, CSRF, Audit und historische Mengen-/Preis-/Rezeptbelege bleiben verbindlich.
- Nur Worktrees unter `.claude/worktrees/`; Shell ausschließlich `rtk`, ein Befehl pro Aufruf, keine Verkettungen, Pipes oder `rtk proxy`.
- Keine Secrets lesen, keine Dependencies installieren, keine fremden Screenshots als Baseline übernehmen.
- Pro Writer ein Worktree und vollständiger Vertrag samt erforderlichen Verbrauchern. Autor und Reviewer getrennt; bestätigte Fixes an anderen Autor.
- Native Sitzung: drei parallele Workerplätze. Claude, Cursor, AGY und Grok sind zusätzlich für eigenständige WPs freigegeben; Root darf ebenfalls abgegrenzte WPs mit unabhängigem Reviewer bearbeiten. Host: höchstens fünf schwere Jobs insgesamt und `rtk pgrep -fc pytest` unter 12; vor Dispatch Speicher und tatsächliche Testlast prüfen.
- Keine gleichzeitigen SQL-Writer. Migrationsnummer erst nach Freeze des Vorgängers reservieren; bestehende Migrationen niemals neu nummerieren oder neu abspielen.
- Temporär gestoppte Container bleiben gestoppt. Keine fremden Testpools oder Produktionsdaten als Fixtures.
- Grün geprüfte Integrationen regelmäßig über `github/main` ausliefern; Schemaänderungen brauchen manuellen Backup-/Restore-/Kompatibilitätsablauf. Der reguläre Deployservice verweigert Migrationsdiffs.
- Planung ist keine pauschale Produktabnahme. `DEPLOYED` und `ACCEPTED` bleiben getrennt.

## Prüfstand und führende Audits

[SDD-Abgleich](2026-09-12-sdd-open-work-audit.md) enthält Zählung und Statusregeln.
Das [versionierte Einzelregister](2026-09-13-sdd-work-package-register.md) enthält
alle 145 ursprünglichen IDs mit Manifeststatus, auditierter Ist-Einordnung,
nächster Aktion und konkreter Quellreportzeile. Die drei Audits decken zusammen ab:

| Bereich | WPs | Vollständiger Auditbericht |
|---|---:|---|
| Operations | 37 | `/nvmetank1/projects/rag-stack/.claude/reports/wp-4a3597a72ed7.md` |
| Rezepte | 43 | `/nvmetank1/projects/rag-stack/.claude/reports/wp-20bbdcac693e.md` |
| Surfaces | 65 | `/nvmetank1/projects/rag-stack/.claude/reports/wp-855e496d2bb5.md` |

Nicht erneut bauen: importierte Beispielgerichte/Lagerorte, Schema27–30, vorhandene Rezeptbindungen, Stapelimport, reine Schema.org-/KI-/Einkaufsadapter, Kostenkern/Patient-Guard und ausgelieferte UI-Korrekturen. Fehlende unabhängige Einzelbelege werden zugeordnet oder gezielt ergänzt.

Begrenzter Statusabgleich vom 13. September: Die drei Originalaudits decken
37 + 43 + 65 = **145 ursprüngliche WPs** ab. Bereits 24 Surface-Pakete stehen auf
DEPLOYED; bei elf weiteren UI-Familien belegt der Audit Teilumsetzungen, keine
vollständige Abnahme. Operations nennt zwei integrierte CALC-Kerne mit noch offenen
unabhängigen Gesamtbelegen. Diese werden nicht allein aus Quelltext-Existenz
hochgestuft. Der Import ist eindeutig produktiv belegt und wird als zusätzliche
Faktenkorrektur von AWAITING_EXTERNAL auf DEPLOYED gesetzt: 61 Rezepte, 100 Zutaten,
29 Prepared-Pins, 32 Gerichtvorlagen und drei reale Lagerorte; Schema29- und
Finalreleasebericht belegen Wiederholung, Restore und unveränderte vier Publikationen.
DATA-KITCHEN bleibt offen. Zusammen mit dem bereits korrigierten Vorlagenwriter
sind damit **26 der ursprünglichen 145 WPs als DEPLOYED eingeordnet**, ohne Aussage
über eine Abschlussquote. Die 31 Ergänzungen (sieben Feature- und 24 Dichte-WPs)
bleiben separat erkennbar; dieser Abgleich ist kein neuer Audit aller 176 Codepfade.

## Sprintfolge und Lieferpunkte

Sprints sind hier abgeschlossene Funktionsabschnitte, keine erfundenen Kalenderzusagen.
Die Reihenfolge nach Sprint 1 ist der begründete Vorschlag. Die eingegangenen
UI-Aufträge sind in Sprint 1 eingeordnet; erledigte Arbeit wird nicht neu gestartet.

| Sprint | Nutzbarer Ausgang | Umfang | Voraussetzung / Lieferpunkt |
|---|---|---|---|
| 0 — belastbarer Start | Aktueller Status, vollständiger Besitzplan und aufbereiteter UI-Auftrag | Aufgaben 1–3 unten; vorhandene Belege wiederverwenden, externe Eingaben isolieren | Kein Produktrelease nötig; Planvalidator und unabhängiger Planreview |
| 1 — Rezepte, Gerichtvorlagen und Planung | Rezept ansehen/drucken; passende Vorlagen und Rezepte gegenseitig finden; aus Vorlage ein Menü für konkreten Plan und Tag übernehmen | Fable-SDD mit getrennten WPs für Verknüpfung, Leseansicht, Druckvorlagenanschluss und Planübergabe; vorhandene Relations-/PDF-Verträge verwenden | Unabhängig geprüfte Verträge, aktuelle Routenmatrix, konfliktfreie Writer; kurze sichtbare Teilreleases, danach gemeinsamer Ablaufcheck |
| 2 — Portionen und Einkauf | Zielmengen im Plan; gespeicherte Einkaufsliste aus Plan oder Rezeptauswahl; druckbare Liste | `MP-REC-PLAN-PORTIONS` → `MP-REC-SHOPPING-PERSIST` → `MP-REC-SHOPPING-PDF`; vorhandenen Aggregator verwenden | UI-Editor-Freeze, Binding-/Freeze-/PDF-Belege; je grüner vertikaler Lieferung eigener Release |
| 3 — Rezepte finden und wiederverwenden | Suche über Titel und Zutaten; danach gespeicherte Suchen und bestätigte Stapel-Tags | `MP-REC-SEARCH-FTS` → `MP-REC-SAVED-SEARCH`, `MP-REC-BATCH-TAGS`; TRGM nur nach eigenem Betriebsentscheid | Gemeinsame SQL-Dateien nach Sprint 2 frei; FTS benötigt keine TRGM-Freigabe |
| 4 — nachvollziehbare Kosten | Datierte Preise, historische Rezept-/Menükalkulation und bewusste Preisvorschläge | PRICE-LEDGER → RECIPE-PROJECTION → PREPARED-GRAPH → MENU-PROJECTION → RULES-SUGGEST → CALCULATION-RECEIPTS → CALC-ADMIN-UI | Vorhandener Patient-Guard nachgewiesen; PLAN-PORTIONS und Freeze-Verträge; Küchenabnahme separat |
| 5 — echter Lagerbestand | Journal, unbekannt/Null korrekt, Transfer/Inventur und Bestand auf Zutatenkarte | INV-MOVEMENT-CORE → BALANCE-READ → TRANSFER → COUNT-CORRECTION → ADMIN-UI; NO-PLAN-DEBIT, DEMAND-COUPLING und Food-Karten-Anschluss | Keine Gleichsetzung der bereits importierten Lagerorte mit Bestand; Journal-Writer serialisieren |
| 6 — Bestellvorbereitung | Manueller Korb, sichere Vorschau/CSV und Bedarfsübernahme | ORD-SUPPLIER-ARTICLE → BASKET-DRAFT → EXPORT-PREVIEW → ADMIN-PREVIEW; danach DEMAND-LINK | Ohne Lieferantenanschluss lieferbar; verbindlicher Versand bleibt eigenes Paket nach ORD-SEND-RIGHTS |

Präfixe in den letzten drei Zeilen sind `MP-CALC-`, `MP-INV-` bzw. `MP-ORD-`.
Vorbereitete Chargenproduktion folgt der Inventurabnahme; keine verdeckte Warenbuchung beim Planen.

## Sprint 1: Kleine sichtbare Lieferungen

Der vollständige Vertrag steht im Feature-SDD und den jeweiligen MP-Einträgen.
Diese Reihenfolge ersetzt nicht den Dateibesitz oder die Readiness-Prüfung:

| WP | Ergebnis für die Küche | Abhängigkeit und Lieferpunkt |
|---|---|---|
| `MP-REC-LINK-READS` | Verknüpftes Rezept und zugehörige Gerichtvorlagen sehen; Rezeptauswahl auch ausserhalb der ersten 200 Einträge | Bestehenden Vorlagenwriter-Freeze belegen; parallel zum Druckvorlagen-Einstieg möglich |
| `MP-REC-PRINT-TEMPLATE-ENTRY` | Aktive Rezeptdruckvorlage mit korrekter Revision öffnen; zum Rezept zurückkehren | Vorhandene Druckvorlagenverträge; eigener kleiner Release möglich |
| `MP-REC-RECIPE-VIEW-PRINT` | Pro Rezept Ansehen, Bearbeiten und Drucken; Entwurf und gedruckten gespeicherten Stand klar unterscheiden | Nach LINK-READS und PRINT-TEMPLATE-ENTRY; sichtbarer Listen-/Ansichtsrelease |
| `MP-TPL-RECIPE-DISH-ENTRY` | Im Vorlagen-Hub aktive Rezeptdruckvorlage, Rezeptdruck-Einstieg und Gerichtvorlagen finden | Kleiner eigener Anschluss; wartet nicht auf Einkaufs-PDF oder spätere Screeneditoren |
| `MP-REC-MENU-TEMPLATE-BINDING` | Menü behält seine Gerichtvorlage als Herkunft; spätere Vorlagenänderungen verändern gespeicherte Menüs nicht | Bestehenden Binding-Freeze sowie DENSITY-MENUEDITOR und DENSITY-WEEKS belegen; Workflow-Dateien exklusiv, vor PROPOSAL/PLAN-PORTIONS |
| `MP-REC-MENU-PROPOSAL` | «Als Menü einplanen» → konkreter Bereich/Tag/Mahlzeit/Menüart → bewusst speichern | Nach LINK-READS und MENU-TEMPLATE-BINDING; belegte Slots und veraltete Formulare sicher behandeln |
| `MP-UI-TEMPLATE-FLOW-ACCEPT` | Gesamten Weg mit realem Browser unabhängig abnehmen | Nach integrierten Ansichts-/Druck-/Planungsanschlüssen; technische Abnahme getrennt von Papierdruck und Küchenfreigabe |

Root kann den Binding-Writer zusätzlich parallel zu noch offenen LINK-READS-/
PRINT-TEMPLATE-ENTRY-Arbeiten starten, sobald dessen bestehender Freeze und beide
Dichtefreezes MENUEDITOR/WEEKS belegt sind und sämtliche Dateileases konfliktfrei
sind. Autor und Reviewer bleiben getrennt; maximal fünf schwere
Hostjobs einschliesslich Browsergates. Die Druckvorlagen-Hubverknüpfung gehört
zum geforderten Sprintumfang und muss vor dessen Gesamtabnahme erreichbar sein.
Frühe Pakete verwenden bestehende Rezeptziele. Erst RECIPE-VIEW-PRINT schaltet
alle betroffenen Links gemeinsam mit der neuen Ansichtsroute um; kein Teilrelease
enthält Links auf eine noch fehlende Route.

## Task 1: Lieferstatus und Abnahmebelege abgleichen

**Files:** `docs/superpowers/backlog-0909/{recipes,operations,surfaces}-wps.json`,
`README.md`, `EXECUTION-READY.md`, `docs/BACKLOG.md`; Statusänderungen nur mit belegtem MP-Bezug.

**Interfaces:** Konsumiert unveränderte Commit-/Release-/Auditbelege. Produziert pro MP
einen begründeten aktuellen Status und getrennte noch offene Kriterien; keine neuen Produkt-DTOs.

- [x] Vollständige 145-Paket-Tabelle aus den drei Audits mit den ursprünglichen MP-Verträgen abgleichen und versionieren.
- [x] Erledigten Rezeptimport den Schema29-/Finalreleasebelegen zuordnen und seinen Status korrigieren; fachliche Küchenprüfung getrennt offen halten.
- [ ] Verbleibende vorhandene Kern-/UI-Pakete kriterienscharf zuordnen. Für
  `MP-BAS-V27-RELEASE-ACCEPTANCE`, `MP-REC-BINDINGS-ACCEPT`, PDF und UI-Matrix fehlende
  Einzelkriterien separat führen; keinen allgemeinen Autorbericht zu `ACCEPTED` hochstufen.
- [ ] Alte OPS-Belegcommits `4027d1b` und `9a9fc81` lesen und auf heutige Anwendbarkeit
  prüfen; fehlende Capture-Prüfung offen halten. PKS-/TRN-Rechteartefakte erst wiederbeschaffen.
- [ ] „Null Foods“ und alte Schemastände als historischen Stand kennzeichnen. Neue
  Migrationsfixtures enthalten nichtleere Lebensmittel-/Rezeptdaten und unveränderliche Altbytes.
- [ ] Planvalidator ausführen:

```bash
rtk python3 docs/superpowers/backlog-0909/validate-plan.py docs/superpowers/backlog-0909/operations-wps.json docs/superpowers/backlog-0909/recipes-wps.json docs/superpowers/backlog-0909/surfaces-wps.json --source-commit e813806b51fb5efaef5d5755c292f8027ce1b2eb --quiet
```

Der ursprüngliche `source_commit` benennt die historische Planquelle; den aktuellen
Ausführungs-/Reviewcommit getrennt ergänzen. Keine künstliche Änderung dieses Werts,
um alte Belege wie neue erscheinen zu lassen. Ausgangswert: 145 Pakete, 35/35 Anforderungen,
0 Fehler, 62 Hinweise. Hinweise prüfen und erhalten, keine vermeintliche warnungsfreie Freigabe.

## Task 2: Eingegangene UI-Aufträge in vorhandene Verträge einordnen

**Files:** Feature-SDD unter `docs/design/`, `docs/BACKLOG.md`, die beiden
`docs/superpowers/backlog-0909/{recipes,surfaces}-sdd.md`/`*-wps.json` und dieser
Sprintplan. Inventar-Folgeauftrag: bestehende `ui-route-matrix.json` und
`ui-before-manifest.json`. Produktdateien erst nach der Zuordnung reservieren.

**Interfaces:** Konsumiert den unveränderten Nutzerprompt und die aktuelle Routenmatrix.
Produziert je Anforderung: konkrete Route/Zustand, erwartetes Verhalten, existierende
MP-ID oder begründete Ergänzung, Dateibesitz, Abhängigkeit und gezieltes Gate.

- [x] Beide Originalprompts in Feature-SDD §1 und Backlog-Nachtrag bewahren; keine zusätzlichen Layoutwünsche erfinden.
- [x] Vorhandene Verknüpfungs-, Planungs-, Ansichts- und Druckwege durch zwei unabhängige GPT-Quellcodeaudits ermitteln: `wp-recipe-links-discovery-0913.md` und `wp-recipe-view-print-discovery-0913.md` im Reportverzeichnis.
- [x] Jede Anforderung als bereits geliefert, Regression, echter neuer Umfang oder
  präzisierter bestehender Auftrag einordnen. Teilweise vorhandene Lösung ausdrücklich kennzeichnen.
- [x] Inventar-Metadaten und Registrierungskontrakt mit `d983860` integriert; aktuelle Liste/Formularzustände zugeordnet. Die vollständige Screenshot-Neuerfassung bleibt ein eigener offener Gateumfang.
- [x] DEBT01–04 und die neue Zutatenkarten-Bestandsanzeige gegen den Prompt abgleichen.
  Mehrere Anforderungen an dieselbe Datei in einem vollständigen Writervertrag bündeln.
- [x] Für gemeinsam betroffene Dateien eine Konflikttabelle und Merge-Reihenfolge festhalten.
- [x] Erste UI-Dispatches mit geprüftem SDD, genauer Basis, Writer, unabhängigem Reviewer und exklusiven Testpools durchführen; tatsächliche Teilintegrationen und Live-Release oben getrennt belegen.

## Task 3: Fehlende Vertragszuordnungen ergänzen

**Files:** Zugehörige `*-sdd.md`/`*-wps.json`, dieser Plan und begründete Entscheidungs-/Abnahmeberichte.

- [ ] `MP-INV-FOOD-CARD-BALANCE` ergänzen oder den vollständigen bestehenden INV-ADMIN-UI-
  Vertrag erweitern. Voraussetzungen: `MP-INV-BALANCE-READ`, `MP-BAS-FOUNDATIONS` und
  abgeschlossene Grundlagen-UI-Korrektur. Schreibbesitz enthält mindestens
  `admin/master_data_routes.py`, `templates/admin/grundlagen_food.html` und gezielte
  Read-/Browsertests. Gate: unbekannt, ausdrücklich gezählte Null und positiver Saldo.
- [ ] `MP-OPS-BACKUP-OFFHOST-ACCEPT` als QA-001-Nachweis ergänzen: benanntes autorisiertes
  Ziel/Operator, Quelle/Zieldatei samt SHA256/Manifest und isolierter Restore von der
  Offhostkopie. Zunächst nur Evidenzauftrag; keinen Transfer auf unbekanntes Ziel starten.
- [ ] Begrenzten Fremdmanager-Format-/Fixtureentscheid zu REC-004 ergänzen; vorhandene
  PKS-Kette zusätzlich nachvollziehbar zu REC-004 zuordnen. Keine erfundenen Pauli-Daten.
- [ ] `MP-REC-SHOPPING-PERSIST` präzisieren: echter Einstieg aus Wochenplan **und**
  Rezeptauswahl, RR-Lesen exakter Revisionen, DTO-Anbindung zum vorhandenen Aggregator.
- [ ] Guard-Freeze von `MP-CALC-PATIENT-GUARD` vor jedem persistierenden CALC-WP als
  ausdrückliche Readiness-Bedingung ergänzen.
- [ ] `MP-UI-USABILITY-OBSERVATION` ergänzen: benannte repräsentative Küchenperson
  findet ein Menü, ändert nur die Beilage, speichert und erklärt danach Prüfstand
  sowie fehlende Allergenprüfung. Beobachtung und Bedienprobleme getrennt von
  fachlicher DATA-KITCHEN-Freigabe festhalten; keine Produktionsänderung als Testfixture.
- [ ] Richtext-Folge-WP erst bei entsprechendem konkretem Funktionsentscheid ergänzen.
  Vorhandene Klartextempfehlung und CSP-Befund bleiben sichtbar; keine ungefragte Editorinstallation.

## Ausführungsverträge für den ersten fachlichen Folgesprint

Die vollständigen `owned_files`, `contract_files`, `wiring_files`, Kriterien und
Verbote stehen unter der jeweils genannten ID in `recipes-wps.json`. Die folgende
Tabelle hebt die kollidierenden Anschlüsse und minimalen Regressionen hervor; sie
verkleinert diesen Dateibesitz nicht.

| Reihenfolge | WP / Vertrag | Kritische Anschlüsse | Nachzuweisender kurzer Ablauf |
|---|---|---|---|
| 2.1 | MP-REC-PLAN-PORTIONS | `component_assignment_contract.py`, Assignment-/Workflow-Stores, Copy/Review, `workflow_routes.py`, `admin/rendering.py`, `menu_editor.html`, `admin.js`, SQL-Vertrag | Exakte Zielmenge 2.500000 erhalten; 0/negativ/fehlende Einheit abweisen; Save/Load/Copy/Review plus native Add/Remove/Reorder; alte Publikationshashes gleich |
| 2.2 | MP-REC-SHOPPING-PERSIST | `shopping_list_store.py`, `admin/shopping_list_routes.py`, `admin/__init__.py`, `einkaufslisten.html`, SQL-Vertrag | Wochenplan/Rezeptauswahl → Liste; manuelle Zeilen/Abhaken; bewusste Neuberechnung; Original-CAS409 ohne Verlust; historische Inputs reproduzierbar |
| 2.3 | MP-REC-SHOPPING-PDF | `admin/shopping_pdf.py`, Listenroute/-template, `print_template_config.py`, `print_templates.py` | Authentifizierter Download genauer Listenrevision; PDF öffnen; 200 Positionen mit lesbarem Umbruch; Mengen/Einheiten korrekt, Wochen-PDF unverändert |

Gezielte Tests für 2.1: `test_recipe_plan_portions_db.py`,
`test_rec_plan_portions_migration_db.py`; für 2.2: `test_shopping_list_db.py`,
`test_shopping_list_browser.py`, `test_rec_shopping_persist_migration_db.py`;
für 2.3: `test_shopping_list_pdf.py` plus betroffene bestehende Wochen-PDF-Verträge.
Neue Tests entstehen gemeinsam mit ihrer Funktion, keine wertlosen Doppeltests des Implementierungscodes.

Alle genannten Python-/Templatepfade liegen unter `reference_scaffold/cafeteria/`,
Tests unter `reference_scaffold/tests/`. Jede schemaändernde Aufgabe besitzt zusätzlich
`database/schema.sql`, `database/permissions.sql`, `database/validate_schema.py`,
`cafeteria/db.py`, `tools/validate_package.py`, ihre echte neue Migration und eng begrenzte
Versions-/Ledgerfixtures. Die vorhandenen `<ROOT_RESERVED_…>`-Einträge sind **keine**
fertigen Pfade: vor `READY` durch reale Reservierung auf dem dann gefrorenen Schema ersetzen.

## Parallelität und Konfliktplan

| Gemeinsame Fläche | Betroffene Aufgaben | Regel |
|---|---|---|
| SQL/Migrationsledger | Portionen, Einkauf, FTS, Preise, Inventur, Nährwerte, Bestellungen, Glossar | Ein Writer; Consumerphase parallel nur nach veröffentlichtem Freeze |
| Menüeditor/`admin.js`/Rendering | Neuer UI-Prompt, DEBT-Bereinigung, Portionen, spätere Glossarübernahme | UI-Korrektur vor Funktionsanschluss; keine konkurrierenden Edits |
| Grundlagen/Food-Formular | Neuer UI-Prompt, Bestandsanzeige, Nährwerte, OFF-Review | Einen vollständigen Vertrag pro kollidierendem Abschnitt vergeben |
| Rezeptliste/-reader/-route | Neuer UI-Prompt, FTS, Saved Search, Batch Tags | UI-Freeze, dann Suche; Folgefunktionen auf derselben integrierten Basis |
| Einkaufsliste/-route | Persistenz, PDF | Erst Persistenz; PDF danach |
| PDF-Konfiguration/-store | Einkaufs-PDF, Rezeptgeometrie, freie Druckgeometrie | Nicht parallel schreiben; exakte aktive Revision und Legacy-Verträge erhalten |
| `admin/__init__.py`/Sidebar | Neue fachliche Oberflächen | Ein Registrierungsbesitzer bzw. serialisierte vollständige Integrationen |

Praktische Belegung: Writer A bearbeitet den aktuellen vertikalen Funktionsvertrag;
Writer B übernimmt einen dateiunabhängigen Anschluss; Worker C prüft unabhängig
den vorherigen Freeze. Zusätzliche CLI-Lanes bearbeiten unabhängige Quellen-/Fixture-/
Abnahmeaufgaben bis zum Hostlimit. Root integriert, kann einen eigenen abgegrenzten
Vertrag übernehmen und liefert grüne Abschnitte aus. SQL-Writer bleiben serialisiert.

## Weitere eingeplante Ketten und externe Eingaben

| Kette | Nächster eigener Schritt | Wartet nur auf |
|---|---|---|
| URL-Rezeptimport | MP-REC-URL-FETCH nutzt vorhandenen Schema.org-Adapter und Stapelweg | Bestehender Import-Freeze, Ausgangsschutz und eigener UI-Besitz |
| XLSX/Fremdmanager | Tatsächliche berechtigte Beispieldatei/Formatentscheidung | Genau diesen Quelldatensatz und Leseweg; CSV/JSON bleiben nutzbar |
| KI-Import | Vorhandene reine Extraktion übernehmen, danach MP-REC-AI-PROVIDER | Freigegebenen konkreten Provider; keine automatische Allergenfreigabe |
| Nährwerte/OFF | NUT-SCHEMA → SERVICE → RECIPE-PROJECTION; OFF-FIELDMAP parallel als Quellenarbeit, dann Adapter/Fetch/Proposal/UI | Serialisierten Schema-/Food-Vertrag; Schweizer Coverage zusätzlich reale berechtigte Stichprobe |
| Screens/freie Druckgeometrie | Bestehende Decision-WPs und vollständige Anschlussketten nach UI-Prompt auswählen | Konkreten Layoutbedarf; kein Frameworkwechsel aus dem Audit |
| Entra | Resolver-/Connection-Verträge technisch parallel vorplanen | Resolverentscheid: berechtigter Operator bestätigt konkreten Resolver-/Handlebereitstellungsweg; echte Tenantabnahme benötigt zusätzlich genehmigten Testtenant, Redirectregistrierung und berechtigte Testidentitäten |
| PKS/Glossar | Fehlende Rechteartefakte wiederbeschaffen; danach vorhandene Adapter-/Glossar-WPs | Autorisierte PKS-Datei und tatsächlich belegte Datenrechte |
| Küche/Druck/API/Player | Bestehende Abnahme-WPs mit Gerät/Person/Client und gefrorener Revision terminieren | Jeweiligen externen Teilnehmer; kein globaler Entwicklungsstopp |

## Gates und Übergabe je Sprint

- [ ] Vor Start tatsächliche Basis, vollständige Dateileases, freien Testpool und
  Originalanforderung festhalten; GitNexus-Impact vor Symboländerung.
- [ ] Autor prüft kleinsten vollständigen Verhaltensumfang; keine stummen Skips oder
  Herkunftsumdeutung alter Tests. Lint/Typprüfung nur passend zur Änderung.
- [ ] Unabhängiger Reviewer prüft Spezifikation und Qualität. Root führt passende
  Gates unabhängig aus; bestätigte Fixes gehen an anderen Autor.
- [ ] UI: betroffene Route auf Desktop und Mobil; zusätzliche Viewports/Zustände für
  gemeinsame Komponenten nach bestehendem Vertrag. Fokus, NoJS, Zoom und Fehlerrückgabe prüfen.
- [ ] Bei Migrationen echter Upgrade/Restore/ACL-Beleg mit nichtleerem Bestand;
  Rollback braucht kompatibles Image und passende Datenwiederherstellung.
- [ ] Vor Release Manifeste aus sauberem Export erzeugen, Paketprüfung, Push nach
  `github/main`, autorisierten Deploy ausführen, Revision/Image/Schema und HTTP live prüfen.
- [ ] Status erst mit jeweiligem Beleg fortschreiben. Physischer Player, Küchendruck,
  fachliche Mengen/Allergene und Tenantabnahme bleiben eigene Aussagen.

Die konkreten Sprint-1-IDs und geplanten Dateiansprüche stehen im Feature-SDD und
den beiden Manifestnachträgen. Aktive Dateileases, geprüfte Vorgänger-Freezes und
exklusive Testpools vergibt Root erst beim Ausführungsstart. Die Folgeketten oben
bleiben nachvollziehbar erhalten.
