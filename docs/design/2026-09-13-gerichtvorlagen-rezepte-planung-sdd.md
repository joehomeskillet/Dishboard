# Gerichtvorlagen, Rezepte und Tagesplanung — Feature-SDD

Stand: 13. September 2026. Planungs-WP `wp-61d537d988a2`, Planer Fable 5.1
(`claude-fable-5-1`). Basis `c0839fbc803e0574582627f06692b29040bb3e53`;
Produktbaseline darin `2fa44dea36675692bfb8ad4b681dca73dba06737`, Schema 30,
live seit 12. September 2026, 23:15 CEST. Dieses Dokument ist Spezifikation und
WP-Zuordnung, keine Implementierung, keine Browserprüfung und keine Abnahme.

Verbindliche Vorgaben bleiben: [Ausführungsvertrag](../superpowers/backlog-0909/execution-contract.md),
[UI-Masterprompt](2026-09-09-unified-ui-design-system.md),
[Korrekturvertrag Patientenplan/Menüeditor vom 12.09.](2026-09-12-patientenplan-menueditor-korrektur.md),
[Rezept-SDD](../superpowers/backlog-0909/recipes-sdd.md) und
[Surface-SDD](../superpowers/backlog-0909/surfaces-sdd.md). Die Arbeitspakete stehen
in `recipes-wps.json` und `surfaces-wps.json` (Nachtrag 13.09.).

## 1. Originalaufträge, unverändert

> https://dishboard.joelduss.xyz/admin/gerichtvorlagen/bcbef3cf-3529-4165-ac43-1f543572c1ff gerichtsvorlagen sollten auf https://dishboard.joelduss.xyz/admin/rezepte rezepte matchen und umgekehrt. aus den gerichtsvorlagen sollen menüvorschläge erstellt werden können und direkt einem tag und planung zugeordnet. idiotensicheres ui nach neuem ui manifest. (ins backlog in wp-s zerlegt, das kann fable 5.1 planen)

> https://dishboard.joelduss.xyz/admin/rezepte button pro rezept für die direkt ansicht und eines für drucken fehlt, muss in vorlagen als druckvorlage verknüpft sein.

Die URLs sind Kontext für den Quellabgleich. Ein externer Webabruf fand nicht statt;
alle Aussagen unten stammen aus dem Quellstand `c0839fb` und den drei Audits
(`wp-20bbdcac693e`, `wp-855e496d2bb5`, `wp-4a3597a72ed7`) sowie den beiden
Codex-Discovery-Berichten `wp-recipe-links-discovery-0913` und
`wp-recipe-view-print-discovery-0913` im Host-Berichtsspeicher.

## 2. Ist-Stand mit Quellenankern

Alle Produktpfade liegen unter `reference_scaffold/cafeteria/`, Tests unter
`reference_scaffold/tests/`, SQL unter `database/`.

| Bereich | Belegter Ist-Stand | Anker |
|---|---|---|
| Gerichtvorlage | Tabelle `dish_templates`: `public_id`, `menu_type_id` (MENU_1/VEGGIE/leer), `profile_scope` (common/patient/staff_guest), `title`, `description`, `active`, `updated_at` als CAS; seit v26 `recipe_id` → **Rezeptkopf** (`recipes.id`, `ON DELETE RESTRICT`), mehrere Vorlagen dürfen dasselbe Rezept binden. | `database/schema.sql:161`, `:4921`; `migrations/0023_v25_to_v26.sql` |
| Vorlagenpflege | `/admin/gerichtvorlagen` (Liste, `?archived=1`), `/neu`, `/<uuid>` mit Anlegen/Ändern/Archivieren/Reaktivieren über `create/update/set_dish_template_active_v26`; `draft.read`/`draft.write`; Rezeptauswahl als natives Select über `list_recipes(include_archived=True)` mit Standardlimit **200**, ohne Suche, Seiten oder Retained-Lookup des gebundenen Rezepts. | `admin/dish_template_routes.py:62`, `:80–160`; `dish_template_store.py:24–46`; `templates/admin/gerichtvorlagen.html` |
| Lieferstand Vorlagen | Store, Routen, Template, Tests und Sidebar-/Tab-Eintrag sind in `c0839fb` enthalten; 32 Vorlagen wurden am 12.09. über den nativen Writer importiert (Schema-29-Release). Das Manifest führte `MP-REC-DISH-TEMPLATE-WRITER` noch als `PLANNED`; der Nachtrag korrigiert das mit Beleg. | `tests/test_dish_template_routes.py`, `tests/test_dish_template_browser.py`; Audit `wp-20bbdcac693e`; `wp-release-schema29-0912.md` |
| Menüposition ↔ Vorlage | `menu_items.dish_template_id` (nullable, `ON DELETE SET NULL`, Index, Trigger `menu_items_dish_recipe_scope` mit `FOR SHARE` auf der Vorlage) existiert. **Kein Python-Writer setzt die Spalte**: `write_draft_item` INSERT/UPDATE lässt sie aus; nur die Vorwochenkopie kopiert sie mit. Kein Reader zeigt sie an. | `database/schema.sql:195`, `:4926`, `:4960–4975`; `workflow_item_write.py:27–72`; `workflow_copy_store.py:173`, `:276` |
| Menüposition ↔ Rezept | Je Bausteinzeile `menu_item_components.recipe_revision_id` → **unveränderlicher gespeicherter Stand**; Auswahl im Menüeditor als gebundene Seite (50) aus Snapshot-Metadaten mit Retained-Selection, archivierte/unlesbare Stände bleiben gebunden sichtbar; keine Suche über den Gesamtbestand («noch nicht angeschlossen»). | `menu_recipe_choices.py`; `templates/admin/menu_editor.html:142–159`; `workflow_partial_form.py:31–38`, `:406` |
| Menüeditor/Tagesplan | `/admin/<cafeteria|patienten>/menu?week&day&meal&option` lädt oder erzeugt den Slot (`row_version` 0 = neu), `menu_post` schreibt über `persist_menu_item` mit Slot-CAS; Raster: Patienten LUNCH/DINNER, Cafeteria LUNCH, Menüarten MENU_1/VEGGIE, Cafeteria-Wochenende nur mit OPS-Freigabe; Rückkehr `?return_to=week` mit Flash. Unbekannte Formularfelder werden abgewiesen. | `admin/workflow_routes.py:124`, `:496–553`; `workflow.py:48–50`; `workflow_partial_store.py:411` |
| Menüsammlung | `/admin/<family>/menues` listet gespeicherte Vorkommen (Titel/Bausteintext), ohne Vorlagenbezug. | `admin/menu_collection_store.py:17` |
| Rezeptliste | `/admin/rezepte`: Karten mit «Bearbeiten» (Schreibrecht + aktiv, sonst dasselbe Ziel als «Ansehen») und «Gespeicherte Stände». Keine Nur-Lese-Ansicht des Entwurfs, keine Druckaktion, kein Vorlagenbezug; Kartendaten kennen keinen neuesten Stand. | `admin/recipe_routes.py:143`; `templates/admin/rezepte.html` |
| Rezeptansicht | Vollständige unveränderliche Darstellung nur je gespeichertem Stand `/rezepte/<uuid>/revisionen/<uuid>` mit «PDF öffnen»; `/rezepte/<uuid>/skalierung` zeigt nur Zutaten/Mengen des Entwurfs. Der Editor-GET ist die einzige Entwurfs-Gesamtdarstellung und für Leser nur deaktiviert. | `admin/recipe_revision_routes.py:83`, `:129`; `templates/admin/rezepte_revision.html`, `rezepte_scale.html` |
| Rezeptdruck | `GET /rezepte/<uuid>/revisionen/<uuid>/druck.pdf` (`draft.read`, nur `yield`): REPEATABLE READ READ ONLY, `recipe_print_input`, **aktive globale Rezeptdruckvorlage** `active_template(conn,'recipe')`, Branding, `render_recipe_pdf`; 422 bei Renderfehler; Header `X-Print-Template-Revision`, `X-Recipe-Revision`, `X-Recipe-Content-SHA256`. Kein Entwurfs-PDF, kein Festschreiben per GET. | `admin/recipe_revision_routes.py:96–126`; `print_templates.py:129`; `admin/recipe_pdf.py` |
| Druckvorlagen | Hub `/admin/vorlagen` (`draft.read`) mit Karte «Rezeptvorlagen» (alle Vorlagen, neueste/aktive Revision, Admin-Links in den Editor). Editor `/admin/vorlagen/rezepte` (`settings.write`, faktisch Admin) mit Parametern `template`, `revision`, `recipe`, `recipe_revision`, `yield`; ohne `template` öffnet **`standard`**, nicht die aktive Vorlage; ohne `revision` die neueste, nicht die aktive Revision. Rezeptseiten verweisen nirgends auf die Vorlage. | `admin/output_routes.py:34`; `templates/admin/vorlagen.html:118–140`; `admin/recipe_print_template_routes.py:58–88`, `:168`; `_recipe_template_selection.html` |
| Öffentliche Projektion | Publikationssnapshot und Hash enthalten weder `dish_template_id` noch Revisionsreferenz; nur der interne Review kennt Revision/Hash. | `workflow_snapshot.py` (keine Fundstelle); Rezept-SDD §6.3 |
| Inventar/Matrix | `ui-route-matrix.json` (116 Routen, Basis Schema 25) enthält keine Gerichtvorlagen-Route. | `docs/superpowers/backlog-0909/ui-route-matrix.json`; Audit `wp-855e496d2bb5` |
| Importstand | 32 Gerichtvorlagen, 32 Gerichte, 29 Vorbereitungsrezepte, 100 Lebensmittel, 3 Lagerorte importiert; Mengen/Allergene fachlich ungeprüft (DATA-001). Kein neuer Import in diesem Plan. | `wp-release-schema29-0912.md:44–50` |

## 3. Begriffe und kanonischer Datenvertrag

| Begriff (UI) | Datensatz | Identität | Veränderlich |
|---|---|---|---|
| Gerichtvorlage | `dish_templates` | `public_id` | ja, CAS `updated_at` |
| Rezept | `recipes` (Kopf) | `public_id`, `row_version` | ja |
| Gespeicherter Stand | `recipe_revisions` | `public_id`, `revision_number`, Hash | nein |
| Menü (Slot) | `menu_items` je `(service, menu_type)` | Woche · Tag · Mahlzeit · Menüart; `row_version` | ja |
| Baustein | `menu_item_components` | Position | ja |

Es gibt genau **vier Kanten**, alle vorhanden, keine wird verdoppelt:

1. Vorlage → Rezeptkopf: `dish_templates.recipe_id`. Kanonische Schreibstelle bleibt
   der Vorlagen-Writer (v26-Verben, `draft.write`, `updated_at`-CAS). Ein Rezept kann
   in null, einer oder mehreren Vorlagen stehen.
2. Rezeptkopf → Vorlagen: **abgeleitete Leserichtung** derselben Kante. Keine Spalte
   im Rezept-Payload, kein zweiter Datenbestand.
3. Menü → Vorlage: `menu_items.dish_template_id`. Wird beim Speichern aus einem
   Vorschlag gesetzt, bleibt beim späteren Bearbeiten erhalten, wird nur ausdrücklich
   gelöst. Herkunftsangabe, keine Live-Kopplung: spätere Änderungen an der Vorlage
   verändern kein gespeichertes Menü.
4. Baustein → gespeicherter Stand: `menu_item_components.recipe_revision_id`. Wird
   nur durch ausdrückliche Auswahl im Editor gesetzt; nie aus dem Rezeptkopf abgeleitet.

**Kopf gegen Stand.** Die Vorlage bindet den Kopf, weil sie ein Vorrat für künftige
Planungen ist. Das Menü bindet den Stand, weil ein geplantes Menü unveränderlich
belegbar sein muss. Beim Vorschlag wird der neueste gespeicherte Stand des Kopfes
**sichtbar vorgeschlagen** und im Formular als Auswahl gezeigt; gespeichert wird nur,
was im Formular steht. Alte Menüs, Vorlagen und PDFs werden nie nachträglich auf
einen neueren Stand umgeschrieben.

Nur Stände eines **aktiven** Rezepts dürfen neu gebunden werden. Bei archiviertem
Vorlagenrezept bleibt dessen Altzuordnung an der Vorlage lesbar, der neue
Menüvorschlag enthält aber keine Rezeptbindung. Ein schon gebundener archivierter
Stand bleibt bei unveränderter Altbindung erhalten; Entfernen und späteres
Wiederbinden zählt als Neubindung und wird abgewiesen.

### 3.1 «Matching» ist explizite Zuordnung, nicht Namensgleichheit

- Zuordnung erfolgt ausschliesslich über die vorhandenen UUIDs (Rezept, Stand,
  Vorlage). Keine automatische Gleichsetzung ähnlicher Titel, kein Fuzzy-Matching,
  kein Hintergrundjob. Die Titelsuche ist nur eine Hilfe zum Finden.
- Der Importadapter `tools/import_dish_templates.py` löst Identität deterministisch
  (exakte UUID oder casefold-Titel mit Konfliktabweisung); er ist Importwerkzeug und
  bleibt ausserhalb der Bedienoberfläche.

Sichtbare Zustände, jeweils mit Klartext und ohne technische IDs als Hauptinformation:

| Sicht | Zustand | Anzeige |
|---|---|---|
| Vorlage | eindeutig | «Rezept: Rösti» mit Link zur Rezeptansicht |
| Vorlage | kein Rezept | «Kein Rezept verknüpft» + Auswahl im Formular |
| Vorlage | Rezept archiviert | «Rezept archiviert» – bleibt gebunden lesbar; Neubindung eines archivierten Rezepts wird serverseitig abgewiesen (55000 → 409) |
| Vorlage | Rezept ohne Stand | «Noch kein gespeicherter Stand» + Link «Stand festhalten» |
| Vorlage | Verwendung | «In 3 Menüs verwendet» (Zählung über `dish_template_id`) |
| Rezept | keine Vorlage | «Keine Gerichtvorlage» + «Vorlage anlegen» (`/gerichtvorlagen/neu?recipe=<uuid>`, nur Vorbefüllung) |
| Rezept | eine Vorlage | «Gerichtvorlage: Rösti (Menü 1, Gemeinsam)» |
| Rezept | mehrere Vorlagen | alle Namen, je Link |
| Rezept | Vorlage archiviert | Name mit Zusatz «archiviert» |
| Menü | aus Vorlage | «Aus Vorlage «Rösti»» auf Karte und im Editor; archivierte Vorlage mit Zusatz |
| Menü | Vorlagenrezept inzwischen anders | Der Bezug bleibt Herkunft; keine Warnung, keine Umschreibung. Der gebundene Stand des Bausteins ist massgeblich. |

## 4. Benutzerabläufe (Soll)

### 4.1 Vorlage → Rezept prüfen und ändern (vorhanden, ergänzt)

Vorlagenliste zeigt pro Zeile Titel, Menüart, Geltungsbereich, Rezeptzustand (§3.1),
Verwendung und Aktivstatus. Das Formular behält das native Rezept-Select, erhält aber
eine gebundene Auswahl: Titelfilter ohne JavaScript, Seite von 50, das aktuell
gebundene Rezept bleibt ausserhalb der Seite als «Aktuelle Auswahl» erhalten. Das
200-Limit entfällt.

Für frische Einstiege bleibt ein GET-Titelfilter möglich. Während der Bearbeitung
laufen Suche und Blättern über ein CSRF-geschütztes POST-Intent mit
`formnovalidate`, das sämtliche ungespeicherten Formularwerte erhält und nur neu
anzeigt. Es schreibt weder Fachdaten noch Audit und legt keinen neuen
Formularzustand in Session oder Store an. CSRF-Token gelangen nie in die URL.
Diese Root-Präzisierung vom 13. September verhindert Datenverlust durch Navigation
aus einem bereits bearbeiteten Formular.

### 4.2 Rezept → Vorlagen sehen und anlegen

Rezeptkarte und Rezeptansicht nennen die verknüpften Vorlagen (§3.1). «Vorlage
anlegen» öffnet das bestehende Vorlagenformular mit vorbelegtem Rezept; nichts wird
durch das Öffnen gespeichert. Ändern einer Vorlage bleibt Sache des Vorlagenformulars
(`draft.write`); `recipe.write` allein erlaubt keine Vorlagenänderung.

### 4.3 Vorlage → Menüvorschlag → Tag und Plan

1. Auf der aktiven Vorlage (Schreibrecht) Aktion **«Als Menü einplanen»**.
2. Seite «Einplanen» mit nativen Feldern: Bereich (aus `profile_scope`: `common` →
   Cafeteria oder Patienten wählbar, sonst fest), Woche (Montag, Standard: aktuelle
   Woche), Tag (die sieben Tage der gewählten Woche; Cafeteria Sa/So nur, wenn die
   Bereichszeiten Wochenenden erlauben oder der Service existiert), Mahlzeit (Cafeteria
   Mittag; Patienten Mittag/Abend), Menüart (aus Vorlage vorbelegt, änderbar).
   Zusammenfassung in Worten: «Rösti → Dienstag, 16. September · Mittag · Menü 1».
3. Das Einplanenformular hält beim ersten Laden den ursprünglichen Actor samt
   Authz-Version, Standort sowie Vorlagen-UUID und `updated_at` im bestehenden
   signierten Formkontextverfahren (`admin/workflow_scope.py`) fest. Absenden
   (CSRF, `draft.write`) prüft diesen Originalkontext, das Raster wie `menu_get`
   und den Slot; keine Erwartung wird aus aktuellem Zustand ersetzt.
   - **leer** → 303 auf den Menüeditor mit `template=<uuid>` und signiertem
     Übergabekontext, der zusätzlich das geprüfte Ziel (Profil/Woche/Tag/Mahlzeit/
     Menüart) und ursprüngliches Create-CAS `row_version=0` bindet; noch nichts
     gespeichert. Kein roher CSRF-Token in URL oder Logs.
   - **belegt** → 409-Seite «Dieser Platz ist bereits belegt mit «Kartoffelstock»» mit
     «Bestehendes Menü öffnen» und «Anderes Ziel wählen». Kein Überschreiben.
   - Vorlage archiviert, Standort gewechselt → 409 mit erhaltenem Formular; ungültiges
     Raster/Bereich → 400 mit erhaltenen Werten.
4. Der Menü-GET validiert den mitgegebenen signierten Originalkontext und übernimmt
   ihn unverändert bis zum Save-POST. Ein nacktes `template=<uuid>` ist kein gültiger
   Vorschlagskontext. Actor/Authz/Standort, Vorlagenversion oder Ziel inzwischen
   geändert oder Slot inzwischen belegt → 409 mit ursprünglichen Eingaben und
   Erwartungen; keine neue `_scope()`-Erwartung, kein neues Create-/Update-CAS und
   kein stiller Wechsel in den normalen Bearbeitungsmodus. «Bestehendes Menü öffnen»
   ist ausschliesslich eine ausdrückliche neue Navigation des Benutzers.
   Bei unverändertem Kontext: Menüeditor, vorbefüllt und deutlich betitelt
   «Neues Menü aus Vorlage «Rösti»»:
   Menüname und Beschreibung aus der Vorlage; Baustein 1 als Text «Rösti» mit
   Rezeptstand-Auswahl auf dem neuesten gespeicherten Stand («Stand 3 vom 10.09.») mit
   Hinweis «Vorgeschlagen. Anderen Stand wählen oder ohne Rezeptbindung speichern.»;
   ohne Stand: «Das Rezept «Rösti» hat noch keinen gespeicherten Stand. Menü kann ohne
   Rezeptbindung gespeichert werden.» + Link «Stand festhalten». Bei archiviertem
   Rezept: «Rezept archiviert; für eine neue Bindung bewusst reaktivieren oder ein
   aktives Rezept wählen»; keine archivierte Revision vorschlagen oder neu auswählbar
   machen. Ohne solche Entscheidung bleibt der Vorschlag ohne Rezeptbindung.
   Cafeteria-Preise
   bleiben leer und Pflicht. Kennzeichnungen im Standardmodus. Verstecktes Feld
   `dish_template_public_id`.
5. **«Menü speichern»** (einziger Speicherweg, bestehender `menu_post`, Slot-CAS 0):
   Der Writer prüft in derselben Schreibtransaktion vor Mutation die ursprüngliche
   Actor/Authz-/Standorterwartung, Vorlagen-UUID/`updated_at`/Aktivstatus/Profil und
   den ursprünglichen Zielslot/CAS unter den vorhandenen Sperren erneut. Änderungen
   seit Einplanen → 409 mit Originalwerten, keine neue Erwartung und kein Teilwrite.
   Live-Auth 401/403 und ungültige Signatur/CSRF werden weiterhin abgewiesen.
   Erfolg → Wochenplan mit Flash «Menü «Rösti» aus Vorlage «Rösti» für Dienstag,
   16. September, Mittag, Menü 1 gespeichert.» Die Karte zeigt «Aus Vorlage «Rösti»».
   Doppeltes Absenden → zweiter Schreibvorgang trifft `row_version` 1 ≠ 0 → 409
   «Dieses Menü wurde inzwischen gespeichert» mit Link zum Menü; kein Duplikat
   (`UNIQUE (service_id, menu_type_id)`).
6. Späteres Bearbeiten behält den Bezug, auch nach Archivierung der Vorlage:
   unverändert mitgesendete ursprüngliche UUID ist eine erhaltene Altbindung und
   bei Änderung anderer Menüfelder zulässig. Neubindung/Wiederbindung einer
   archivierten Vorlage bleibt verboten. Lösen nur über Kontrollkästchen
   «Vorlagenbezug lösen» mit Bestätigung im Formular; ein altes Formular ohne das Feld
   löst nichts.

Der Vorschlag ist absichtlich **transient**: kein `menu_proposal`-Datensatz, keine
Freigabe-Warteschlange. Ein gespeichertes Menü ist das Ergebnis; alles davor ist ein
vorbefülltes Formular.

### 4.4 Rezept ansehen

Neue Route `GET /admin/rezepte/<uuid>/ansicht` (`draft.read`, nur `yield`): vollständige
Nur-Lese-Darstellung des aktuellen Entwurfs (Titel, Beschreibung, Ausbeute, Zutaten
mit Mengenberechnung, Zubereitung, Bilder/Herkunft, Kennzeichnungen, Vorlagenbezug),
Kopfhinweis «Entwurf · nicht festgeschrieben» und Verweis auf den neuesten
gespeicherten Stand. Wiederverwendet `render_scaled` und die Makros aus
`rezepte_scale.html`. GET schreibt nie, erzeugt keinen Formkontext.

Rezeptkarte: **«Ansehen»** (Ansicht), **«Bearbeiten»** (nur Schreibrecht und aktiv),
**«Drucken»**. Kein Ziel doppelt.

### 4.5 Rezept drucken

«Drucken» führt bei vorhandenem gespeichertem Stand direkt zum vorhandenen PDF des
**neuesten** Stands; das Label nennt ihn («Drucken · Stand 3»). Ohne Stand führt die
Aktion zu «Gespeicherte Stände» mit dem Text «Zum Drucken zuerst einen Stand
festhalten» – der bestehende Freeze-Ablauf bleibt der einzige Schreibweg, nie ein GET.
Die Ständeliste erhält je Zeile «PDF öffnen». Ein Entwurfs-PDF wird nicht eingeführt
(Entscheidung D6).

### 4.6 Druckvorlage verknüpft sichtbar

Ansicht, Stand-Ansicht und Ständeliste zeigen «Druckvorlage: Rezept A4 · Revision 2
(aktiv)». Admin (`settings.write`) erhält den Link in den Editor mit **explizit
aufgelösten** IDs `template=<aktiv>&revision=<aktiv>&recipe=<uuid>[&recipe_revision=…]`;
andere Rollen sehen nur den Text. Der Editor ohne Parameter öffnet künftig die aktive
Vorlage und Revision (virtueller Default, initialisiert nichts) und zeigt bei
Rezeptkontext «Zurück zum Rezept «Rösti»». Im Hub erhält die Rezeptvorlagen-Karte
«Aktive Vorlage öffnen» mit expliziten IDs und einen Einstieg «Rezept drucken» zur
Rezeptliste; eine Karte «Gerichtvorlagen» (TPL-001 «Menüvorlagen») verlinkt die Liste
mit Zählung aktiv/archiviert.

## 5. Fehler-, Leer- und Konfliktzustände

| Fall | Verhalten |
|---|---|
| Vorlagenliste leer | Empty State «Noch keine Gerichtvorlagen» + «Vorlage anlegen» (nur Schreibrecht) |
| Rezeptsuche ohne Treffer im Vorlagenformular | «Keine passenden Rezepte»; aktuelle Auswahl bleibt |
| `?recipe=` unbekannt/standortfremd | 404 auf der Seite, Formular ohne Vorbelegung |
| Vorlage archiviert beim Einplanen | 409 «Diese Vorlage ist archiviert. Reaktivieren oder andere Vorlage wählen.» |
| Bereich passt nicht zum Geltungsbereich | 400 am Feld «Bereich», Werte erhalten |
| Slot belegt | Konfliktseite mit beiden Wegen, kein Schreiben |
| Slot inzwischen belegt (Race zwischen Einplanen und Speichern) | 409 aus Slot-CAS, Eingaben erhalten, Link zum Menü |
| Rezept der Vorlage archiviert | Neuer Vorschlag ohne Rezeptbindung und mit Hinweis; keine archivierte Revision neu wählbar. Bewusste Reaktivierung oder Wahl eines aktiven Rezepts nötig. Unveränderte bestehende Altbindungen bleiben erhalten. |
| Vorlage eines bestehenden Menüs später archiviert | Andere Menüfelder dürfen mit unverändertem ursprünglichem Vorlagenbezug gespeichert werden; explizites Lösen erlaubt, Neubindung/Wiederbindung abgewiesen. |
| Rezept ohne Stand | Hinweis, Menü ohne Bindung speicherbar |
| Actor/Authz/Standort/Vorlagenversion oder Ziel während Ablauf gewechselt | 409 mit Originalkontext; neuer Ablauf nur bewusst vom Einplanenformular starten, nie im Menü-GET auffrischen; Live-Auth 401/403 bleibt vorgelagert. |
| Fehlende Berechtigung | Aktionen unsichtbar; POST 403; GET-Seiten für Leser sichtbar ohne Schreibaktionen |
| Drucken ohne Stand | Weiterleitung zu Ständen mit Erklärung |
| PDF-Renderer lehnt ab | bestehendes 422 mit Klartext; keine Umschreibung |
| Druckvorlagenstore defekt | bestehende 503-Hülle, no-store |
| Vorlagen-Editor ohne Parameter | aktive Vorlage/Revision; explizite Parameter wie bisher |

## 6. UI-Vertrag nach Masterprompt

- Gemeinsamer Seitenrahmen, `page_header`, bestehende Makros (`field`, `select`,
  `status_badge`, `empty_state`, `pagination`), Tabler-Komponenten, Tokens; keine neue
  Palette, kein Framework, keine neue Dependency.
- Klare Labels in Küchensprache: «Ansehen», «Bearbeiten», «Drucken», «Als Menü
  einplanen», «Gespeicherter Stand», «Vorlagenbezug lösen». Technische IDs, Hashes und
  Versionen nur in «Technische Details».
- Genau eine dominante Aktion je Aufgabe: Einplanen-Seite «Weiter zum Menü», Editor
  «Menü speichern». Keine kombinierte Speichern-und-Prüfen-Transaktion.
- Native Formulare, NoJS-Grundfunktion, Tastatur/Fokus/Escape, 44-px-Ziele,
  keine horizontale Seitenscrollbar bei 390 px, 200 %-Zoom.
- Viewports: jede geänderte Route 1440×900 und 390×844; Gerichtvorlagenliste,
  Formular und Einplanen-Seite als Listen-/Formulartyp zusätzlich 1024×768, 768×1024,
  1920×1080. Screenshots sind vorgeschlagene Referenzen, keine freigegebenen Baselines.
- Zustandsdarstellung: Aussage vor Farbe; «Aus Vorlage», «archiviert», «kein Stand»
  als Text mit Badge, nie nur farbig.

## 7. Sicherheit und Invarianten

- Original-Actor/Authz (`ActorExpectation`), aktiver Standort, CSRF (scoped für
  Menüformulare), CAS (`updated_at` Vorlage, `row_version` Menü/Rezept) bleiben
  vom Einplanenformular über POST → 303 → Menü-GET → Save unverändert gebunden
  (§4.3). Übergabekontext nutzt die bestehende Signatur-/Formkontextinfrastruktur,
  keine neue Bibliothek; Weitergabe und Prüfung sind Teil desselben WP-Vertrags.
  Ursprüngliche Erwartungen werden beim finalen Schreiben transaktional erneut
  geprüft. GET schreibt keine Fachdaten und frischt keine bestehende Erwartung auf.
- Idempotenz: Einplanen-POST schreibt nichts (nur Prüfung und Redirect); Speichern ist
  durch Slot-CAS und `UNIQUE (service_id, menu_type_id)` doppelklicksicher.
- Patientenkanal bleibt strukturell preisfrei; der Vorschlag erfindet keine Preise,
  Kennzeichnungen, Allergene oder Prüfstände. Cafeteria-Preise bleiben Pflichtfelder.
- Publikationssnapshot, Hash und öffentliche Renderer bleiben bytegleich; kein
  Vorlagen- oder Revisionsfeld gelangt in die öffentliche Projektion.
- Keine SQL-Änderung, keine Migration: alle Spalten, Trigger und Verben existieren.
  Trigger `menu_items_dish_recipe_scope` (23514) wird als 409 mit Klartext abgebildet.
- Berechtigungen bleiben: Vorlagen `draft.read/draft.write`, Menü `draft.read/draft.write`,
  Rezept `draft.read/recipe.write`, Druckvorlageneditor `settings.write`. Keine
  Ausweitung von `settings.write` für Druck.
- CSV-Vollersatz einer Woche ersetzt Inhalt einschliesslich Vorlagenbezug (bestehendes
  `DELETE FROM menu_items`), Vorwochenkopie kopiert den Bezug weiter. Beides wird
  getestet und dokumentiert, nichts geschieht still.

## 8. Entscheidungen mit Begründung

| Nr. | Entscheidung | Begründung |
|---|---|---|
| D1 | Vorlage bindet Rezeptkopf, Menü bindet Stand | Vorhandenes Schema; Vorrat gegen Beleg (§3) |
| D2 | Kein Auto-Matching, nur explizite UUID-Zuordnung | Brief-Vorgabe; mehrere Vorlagen je Rezept sind legitim |
| D3 | Vorschlag transient, Ergebnis ist das gespeicherte Menü | Keine zweite Datenhaltung; vorhandener Writer, CAS und Review bleiben einzige Wahrheit |
| D4 | Neuester Stand wird sichtbar vorgeschlagen, nie still gesetzt | Brief-Vorgabe «keine automatische Gleichsetzung»; Formularinhalt entscheidet |
| D5 | Bezug Menü→Vorlage über bestehendes `dish_template_id`, Lösen nur explizit | Spalte, Trigger und Kopie existieren; Herkunft bleibt nachvollziehbar |
| D6 | Kein Entwurfs-PDF; Drucken = neuester Stand oder erklärter Weg zum Festhalten | PDF-Vertrag ist unveränderlich; Festschreiben per GET verboten |
| D7 | Direktansicht als kleine neue Nur-Lese-Route statt Editor-GET | Editor-GET signiert Formkontext und ist für Leser nur deaktiviert; Discovery-Befund |
| D8 | Druckvorlagen-Verknüpfung als Anzeige + explizit aufgelöste Editor-IDs | «Ohne `template` = standard» wäre ein falscher «aktiv»-Link; keine persistente Rezept-Vorlagen-Zuordnung, weil das PDF global die aktive Vorlage nutzt |
| D9 | Vorlagen-Rezeptauswahl gebunden mit Retained-Selection statt 200er-Limit | Discovery-Befund; gleiches Muster wie Menüeditor |
| D10 | Keine Migration, kein READY vor Root-Lease | Alle Verträge vorhanden; gemeinsame Workflow-Dateien sind mit `MP-REC-PLAN-PORTIONS` serialisiert |

## 9. Abnahmefälle

| ID | Fall | WP |
|---|---|---|
| A1 | Vorlagenliste zeigt Rezeptzustand, Verwendung und funktionierenden Link je Zeile; zunächst bestehender Editor, Umstellung auf neue Ansicht mit VIEW-PRINT; Leser ohne Schreibaktionen | LINK-READS, VIEW-PRINT |
| A2 | Rezept ausserhalb der ersten 200 ist im Vorlagenformular findbar; gebundenes Rezept bleibt ausserhalb der Seite sichtbar | LINK-READS |
| A3 | `/gerichtvorlagen/neu?recipe=` befüllt vor, schreibt nichts, 404 bei fremder UUID | LINK-READS |
| A4 | Rezeptkarte: Ansehen/Bearbeiten/Drucken getrennt; Leserolle ohne Bearbeiten; keine doppelten Ziele | VIEW-PRINT |
| A5 | Ansicht zeigt Entwurf vollständig, Hinweis «nicht festgeschrieben», Vorlagenbezug, Druckvorlage | VIEW-PRINT |
| A6 | Drucken mit Stand öffnet PDF (Bytes + nativer Paint getrennt geprüft); ohne Stand Erklärung, kein Freeze | VIEW-PRINT |
| A7 | Admin-Link in den Editor trägt aktive `template`/`revision`; andere Rollen nur Text | VIEW-PRINT, PRINT-TEMPLATE-ENTRY |
| A8 | Editor ohne Parameter öffnet aktive Vorlage/Revision; nichts initialisiert; Rückweg zunächst bestehender Editor, Umstellung auf neue Ansicht gemeinsam mit deren Route | PRINT-TEMPLATE-ENTRY, VIEW-PRINT |
| A9 | Menüformular mit `dish_template_public_id` speichert Bezug; Rücklesen zeigt «Aus Vorlage»; UPDATE ohne Feld erhält; Lösen nur explizit | MENU-TEMPLATE-BINDING |
| A10 | Neue profil-/standortfremde oder archivierte Vorlagenbindung → 400/409; ursprüngliche unveränderte Altbindung nach Archivierung bei anderer Menüänderung bleibt; Lösen erlaubt; Trigger 23514 → 409 | MENU-TEMPLATE-BINDING |
| A11 | Publikationshash und öffentliche Projektion unverändert; Kopie behält Bezug; CSV-Ersatz dokumentiert | MENU-TEMPLATE-BINDING |
| A12 | Einplanen: Bereich/Woche/Tag/Mahlzeit/Menüart nativ, NoJS; leerer Slot → vorbefüllter Editor; belegter Slot → Konfliktseite ohne Schreiben | MENU-PROPOSAL |
| A13 | Vorbefüllung: Titel, Beschreibung, aktiver Rezeptstand sichtbar vorgeschlagen; kein Stand/Rezept/archiviertes Rezept mit Hinweis ohne neue archivierte Bindung; Patienten ohne Preise | MENU-PROPOSAL |
| A14 | Speichern → Wochenplan-Flash mit Vorlage, Tag, Mahlzeit, Menüart; Karte «Aus Vorlage» | MENU-PROPOSAL |
| A15 | Originalkontext durch alle Übergänge: Actor/Authz-/Standort-/Vorlagenversion-/Zielwechsel sowie belegter Slot nach 303 oder vor Save → 409 ohne Neusignierung/Moduswechsel/Teilwrite; doppelte Abgabe erzeugt kein Duplikat | MENU-TEMPLATE-BINDING, MENU-PROPOSAL |
| A16 | Separat lieferbarer Hub: Gerichtvorlagen-Karte, «Aktive Vorlage öffnen» mit IDs, «Rezept drucken»; keine Abhängigkeit von Einkaufsdruck/Screen-Editor | TPL-RECIPE-DISH-ENTRY |
| A17 | Inventar enthält Gerichtvorlagen-Familie und Rezeptansicht | UI-INVENTORY |
| A18 | Gesamtfluss in fünf Viewports, JS/NoJS, Tastatur, Zoom, Kontrast, Rollen, Zustände; Evidenzdatei | UI-TEMPLATE-FLOW-ACCEPT |

## 10. Arbeitspakete, Reihenfolge und Konflikte

Neue Pakete (alle `PLANNED`, Root vergibt Leases und setzt `READY`):

| Reihenfolge | WP | Slice | Kern | Anschlüsse |
|---|---|---|---|---|
| 1 | `MP-REC-LINK-READS` | recipes | `recipe_link_reads.py`, Vorlagenliste/-formular | `dish_template_routes.py`, `gerichtvorlagen.html` |
| 2 | `MP-REC-PRINT-TEMPLATE-ENTRY` | recipes | aktive Vorlage als Default, Rückweg | `recipe_print_template_routes.py`, `_recipe_template_selection.html` |
| 3 | `MP-REC-RECIPE-VIEW-PRINT` | recipes | Ansicht, Drucken, Vorlagenbezug, Druckvorlagenanzeige samt Umschaltung der bisherigen Rezeptlinks | `recipe_routes.py`, `recipe_revision_routes.py`, `rezepte*.html`, `gerichtvorlagen.html`, `_recipe_template_selection.html` und deren Routen-/Browsertests |
| 4 | `MP-REC-MENU-TEMPLATE-BINDING` | recipes | Vorlagenbezug im Menüwriter/-reader | Workflow-Vertragscluster (seriell mit PLAN-PORTIONS) |
| 5 | `MP-REC-MENU-PROPOSAL` | recipes | Einplanen-Seite, Editor-Vorbefüllung, Ergebnis | `dish_template_routes.py`, `workflow_routes.py`, `rendering.py`, `menu_editor.html` |
| 6 | `MP-TPL-RECIPE-DISH-ENTRY` | surfaces | kleiner Rezeptdruck-/Gerichtvorlagen-Hubanschluss | `output_routes.py`, `vorlagen.html`, vorhandene Hub-/Katalog-/Browsertests |
| 7 | `MP-UI-TEMPLATE-FLOW-ACCEPT` | surfaces | unabhängige Browserabnahme | eigener Test + Evidenz |

Erweiterte Pakete: `MP-REC-DISH-TEMPLATE-WRITER` (Status/Beleg), `MP-REC-BINDINGS-ACCEPT`
(vierte Kante), `MP-UI-INVENTORY`, `MP-UI-MATRIX`, `MP-UI-RECIPE-LISTS`,
`MP-UI-PRINT-EDITOR`, `MP-TPL-HUB-COMPLETE`. 1 kann parallel zu 2; 3 nach 1 und 2;
4 nach Freeze von `MP-REC-BINDINGS` und nicht gleichzeitig mit `MP-REC-PLAN-PORTIONS`;
5 nach 1 und 4; 6 nach 3 und geliefertem OUTPUT-HUBS/Vorlagen-Writer;
7 nach 3, 5 und 6. Der spätere `MP-TPL-HUB-COMPLETE` konsumiert 6 und behält seine
eigenen weiteren Featureabhängigkeiten. Kein SQL-Writer in dieser Welle.

**Lieferbare Zwischenstände:** LINK-READS und PRINT-TEMPLATE-ENTRY verlinken zuerst
den vorhandenen `admin.recipe_edit`; kein `url_for` auf noch unregistrierte Ansicht.
VIEW-PRINT übernimmt `gerichtvorlagen.html` und `_recipe_template_selection.html`
samt vorhandenen Route-/Browsertests als Schreibanschlüsse und schaltet beide Links
zusammen mit Registrierung und Tests der neuen Ansicht um. Jede Teilrelease hat
funktionierende GET-Ziele; BuildError-/404-Freiheit wird vor und nach Umstellung
mit Admin/Leser und JS/NoJS geprüft. Keine neue Abhängigkeit rückwärts auf VIEW-PRINT.

| Gemeinsame Datei | Writer | Regel |
|---|---|---|
| `gerichtvorlagen.html`, `tests/test_dish_template_*.py` | LINK-READS → VIEW-PRINT → MENU-PROPOSAL | sequenzielle Dateileases, keine fachliche Zusatzabhängigkeit |
| `admin/dish_template_routes.py` | LINK-READS → MENU-PROPOSAL | seriell |
| `admin/workflow_routes.py`, `admin/rendering.py`, `menu_editor.html` | BINDING-UI (geliefert) · PLAN-PORTIONS · MENU-TEMPLATE-BINDING → MENU-PROPOSAL | ein aktiver Writer; PLAN-PORTIONS und BINDING nicht parallel |
| `workflow_partial_form.py`, `workflow_item_write.py`, `workflow_partial_store.py`, `workflow_store.py` | BINDINGS (Anker) · PLAN-PORTIONS · MENU-TEMPLATE-BINDING | seriell nach Root-Lease |
| `admin/workflow_scope.py` | MENU-TEMPLATE-BINDING | signierter Übergabevertrag; MENU-PROPOSAL konsumiert denselben geprüften Kontext |
| `rezepte.html`, `rezepte_revisionen.html` | VIEW-PRINT → UI-RECIPE-LISTS → SEARCH-FTS/SAVED-SEARCH/BATCH-TAGS | seriell |
| `rezepte_revision.html` | UI-REF-DETAIL (geliefert) → VIEW-PRINT | Lease |
| `recipe_print_template_routes.py` | PRINT-TEMPLATE-ENTRY → PDF-GEOMETRY | seriell |
| `_recipe_template_selection.html`, `tests/test_recipe_template_editor_*.py` | PRINT-TEMPLATE-ENTRY → VIEW-PRINT → UI-PRINT-EDITOR | seriell |
| `vorlagen.html`, `output_routes.py`, Hub-/Katalogtests | TPL-RECIPE-DISH-ENTRY → TPL-HUB-COMPLETE | jeweils ein Hub-Owner, kleiner Anschluss zuerst |
| `_week_menu_card.html` | UI-KORREKTUR-WEEK (geliefert) → MENU-TEMPLATE-BINDING | Lease |

Gates je WP stehen im Manifest (gezielte pytest-Listen mit realem Wrapper, Browser
390/1440 und Matrix für Seitentypen). Release: reguläre Anwendungsreleases ohne
Migration; Rollback = vorheriges kompatibles Image, keine Daten betroffen, ausser dem
Menüwriter-Bezug, dessen Spalte nullable ist und von alten Readern ignoriert wird.

## 11. Nicht-Ziele

- Kein persistenter Vorschlagsdatensatz, keine Freigabe-/Ranking-Logik.
- Kein Entwurfs-PDF, kein automatischer Druck, keine Rezept-spezifische Druckvorlagenzuordnung.
- Keine automatische Namensgleichsetzung, kein neuer Import, kein Freeze/Review/Publish.
- Keine Änderung an Zielportionen (`MP-REC-PLAN-PORTIONS`), Einkaufslisten oder Kalkulation.
- Keine neue Menüart, kein neuer Bereich, keine Änderung der Bereichszeiten.
- Keine Migration, keine neue Dependency, kein Framework.

## 12. Offene Punkte für Root

- Statusabgleich des Manifests gemäss Sprintplan Task 1 (u. a. `MP-REC-BINDINGS`,
  `MP-REC-BINDING-UI` geliefert, aber nicht als solche geführt); dieser Nachtrag
  korrigiert mit Beleg nur `MP-REC-DISH-TEMPLATE-WRITER`.
- Leases für die Konflikttabelle in §10 und Testpools je Writer.
- `README.md`/`EXECUTION-READY.md` im Backlog-Ordner nennen alte Paketzahlen; sie sind
  nicht Teil des Schreibbesitzes dieses WPs.
- Fachliche Küchenabnahme (DATA-001) und Papierdruck (`MP-TPL-PAPER`) bleiben getrennt.
