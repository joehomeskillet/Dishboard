# REC R2: ausführbarer UI-Implementierungsplan

Stand 07.09.2026; WP wp-60901a3ab439. Geprüfte Schnittstellenbasis:
`c4c8e354427c9f9235fa817c3c3ca751569d115f`. Dies ist ein Plan, keine UI-Abnahme.
Root integriert vor Umsetzung die separat bearbeiteten R1-Korrekturen zur
Schrittbild-Herkunft und zum Audit von Kopf, Schritten und Kochbuchreihenfolge.
Der Start-Commit jedes Pakets muss diese Korrekturen nachweislich enthalten.

## 1. Bindende Grundlage und Umfang

- [BAS/REC-Datenvertrag](2026-09-06-bas-rec-data-contract.md), besonders §3, §5, §7/8 und M-B.
- [Arbeitspakete R1–R4](../superpowers/bas-rec-work-packages-0906.md): dieser Plan umfasst den Rezept-Admin einschließlich der R3-/R4-Verbraucher; keine erneute M-B-Migration.
- [R1-Addendum](2026-09-07-rec-r1-contract-addendum.md): exakte Payloads, DTOs, Fehler und unveränderliche Quellen.
- [Tabler-Vertrag](admin-tabler-contract.md) und [Symbolmanifest](2026-09-07-admin-tabler-icon-manifest.md).
- Tatsächliche Imports: `cafeteria.recipe_store`, `recipe_types`, `master_data_store`, `master_data_types`, `quantities`; keine Route greift direkt auf SQL oder interne Dispatcher zu.

Ergebnis: Rezepte finden, vollständig bearbeiten, Bilder und Quellen sehen, Revisionen
festschreiben/ansehen/skaliert lesen, Kochbücher pflegen, archivieren und reaktivieren.
Kein Richtext, URL-Abruf, Importanbieter, Menübinding, Einkauf, Kalkulation oder neuer PDF-Editor.
Gestaltung: ruhige bestehende Dishboard-Arbeitsfläche; pro Formular eine Hauptaktion,
sichtbar getrennte Zustände „Entwurf“, „Revision“ und „nur berechnet“; kein neues Designsystem.

## 2. HTTP-Vertrag

Alle Pfade unter `/admin`; UUID-Parameter heißen `recipe_id`, `revision_id`, `cookbook_id`.
GETs sind mutationsfrei, auch leere Listen, Skalierung und Bestätigungsseiten. POST-Erfolg
führt über 303 auf einen festen `url_for`-GET; keine freien Rücksprung-URLs.

| Methoden/Pfad | Endpoint unter `admin.*` | Dienst/Verhalten |
|---|---|---|
| GET `/rezepte` | `recipes_list` | `list_recipes`; `q`, `archived=0|1`, `page>=1`; 50 Treffer, nächste Seite ohne erfundene Gesamtzahl |
| GET/POST `/rezepte/neu` | `recipe_new` | leeres Formular / `create_recipe` |
| GET/POST `/rezepte/<recipe_id>` | `recipe_edit` | `get_recipe` / vollständiges `update_recipe` |
| POST `/rezepte/formular` | `recipe_form_rows` | ausschließlich Formularzeilen hinzufügen/entfernen/verschieben, keine Persistenz |
| GET/POST `/rezepte/<recipe_id>/status` | `recipe_status` | konkrete Bestätigung / `set_recipe_active(active=...)` |
| GET `/rezepte/<recipe_id>/revisionen` | `recipe_revisions` | neue gebundene Revisionsliste aus Paket A0 |
| POST `/rezepte/<recipe_id>/revisionen` | `recipe_freeze` | `freeze_revision`, 303 auf exakt zurückgegebene Revisions-UUID |
| GET `/rezepte/<recipe_id>/revisionen/<revision_id>` | `recipe_revision` | `get_revision`, Rezeptzugehörigkeit zwingend prüfen; optional `yield` als reine Vorschau |
| GET `/rezepte/<recipe_id>/skalierung` | `recipe_scale` | gespeicherter Entwurf + `yield`; keine Speicherung |
| GET/POST `/rezepte/<recipe_id>/bilder` | `recipe_images` | gespeicherte Bildverwaltung / `add_recipe_image`, multipart |
| GET `/rezepte/<recipe_id>/bilder/<sha256>` | `recipe_asset` | `get_recipe_asset`, echte Bytes/MIME; nur Rezept oder erhaltene Revision berechtigt |
| GET `/kochbuecher` | `cookbooks_list` | `list_cookbooks`, `archived`, `page`; keine nur auf erster Seite wirkende Scheinsuche |
| GET/POST `/kochbuecher/neu` | `cookbook_new` | `create_cookbook` |
| GET/POST `/kochbuecher/<cookbook_id>` | `cookbook_edit` | `get_cookbook` / `update_cookbook` für Name/Beschreibung |
| POST `/kochbuecher/<cookbook_id>/rezepte` | `cookbook_recipes` | vollständige geordnete UUID-Liste an `replace_cookbook_recipes` |
| GET/POST `/kochbuecher/<cookbook_id>/status` | `cookbook_status` | Bestätigung / `set_cookbook_active` |

Archivierte Rezepte/Kochbücher bleiben lesbar; nur Reaktivieren ist als Write verfügbar.
Bestehende archivierte Zutaten-/Tag-/Rezeptreferenzen sichtbar erhalten, neue nicht anbieten;
der Dienst prüft die tatsächliche Zulässigkeit erneut. Keine lokale Archivregel ersetzt SQL.

## 3. Formulare, Autorisierung und Fehler

Gemeinsamer R2-Formhelper signiert `_form_context` mit bestehendem Anwendungsschlüssel und
eigenem Zweck/Salt: Aktion, Ziel-UUID oder Neuanlage, ursprüngliche `row_version`,
Actor-ID und `authz_version`, serverseitig geladene `expected_location_id`.
CSRF bleibt der vorhandene separate CSRF-Vertrag. Kontext ist kein Berechtigungsersatz.
Vor jedem POST: Sitzung/CSRF, Signatur/Format/Zweck/Ziel prüfen; anschließend ursprüngliche
`ActorExpectation` und `ObjectExpectation` an den Dienst geben. Neuanlage ohne Objektversion.
Keine neue Actor-, Standort- oder CAS-Erwartung durch erneutes Laden im POST erzeugen.
Lesen verlangt `draft.read`, Schreiben `recipe.write`; Rollenänderung/Passwortreset bleibt
unter dem vorhandenen R1/IAM-Lockvertrag wirksam. Keine neue Rolle oder Capability.

Rezeptformular liefert alle im Addendum benannten Aggregatefelder, optionale Werte explizit
None und leere Listen explizit leer. Native Felder: Kopfname wie API; Quelle `source.<field>`;
Zeilen `ingredients.<index>.<field>`, `steps.<index>.<field>`, `images.<index>.<field>`;
Tags wiederholt `tag_public_ids`. Indizes zusammenhängend, Grenzen 64, unbekannte Felder und
doppelte skalare Schlüssel ablehnen. Kein JSON-Textarea als Ersatz für Zutateneditor.
Stabile `line_public_id` bleibt beim Verschieben erhalten; nur neue Zeilen senden leeren
Wert, übersetzt zu None. Entfernen ist explizit; niemals UUID durch Arrayindex ersetzen.
Ursprungsfelder sind sichtbar und unveränderlich; Originalwerte vollständig übertragen,
Dienst prüft sie. Manuelle Neuanlage erfindet weder Importbeleg noch Allergenbestätigung.
Auswahllisten nutzen paginierte B2-Dienste, erhalten gewählte Referenzen auch außerhalb der
aktuellen Ergebnisse; keine still auf 200 Datensätze beschränkte „vollständige“ Auswahl.

`recipe_form_rows` nimmt dieselben Werte plus `row_action`, `row_index`, `row_kind` an;
validiert begrenzte Struktur und signierten Ursprung, erhält unvollständige Feldwerte,
rendert ohne DB-Mutation und ohne neue Signatur. JS darf diese Operation lokal ergänzen.
Bekannte Anzeigetexte der Auswahl werden im ursprünglichen signierten Kontext mitgeführt;
beim Standortkonflikt keine Referenzen des neuen Standorts nachladen.
Kochbuchzuordnung verwendet wiederholte `recipe_public_ids` in sichtbarer Reihenfolge;
numerische Positionsfelder bieten ohne JS eine eindeutige Umsortierung, Duplikate ablehnen.
Kopf und Zuordnungen sind getrennte, klar beschriftete Formulare mit eigenen Originalkontexten.

400: Feldfehler, unveränderte Originaleingaben, `aria-invalid`/`aria-describedby`, Fokus auf
ersten Fehler; führende Zeilenumbrüche und Mehrfachauswahlen im HTML-Roundtrip erhalten.
401: fehlende/stale Sitzung; 403: fehlende Fähigkeit; 404: unbekannt/fremdes Ziel.
409: sichtbarer Konflikt, alle Texte/Auswahlen/Referenzen beschriftet kopierbar, Originalkontext
behalten, kein automatisches Neusenden. „Aktuellen Stand laden“ ist bewusster GET; bei
Standortwechsel sicherer Listenlink statt Zugriff auf fremdes Objekt oder neue Signatur.
503/no-store: äußere Fehlergrenze umfasst Auth, Standort, Kontext und Reader; statische
Tabler-Fehlerantwort ohne erneute DB-abhängige Kontextanreicherung, keine SQL-Details.
Auch B2-Auswahlfehler vollständig nach deren Fehlervertrag behandeln; kein pauschales 400.

## 4. Bilder, Revisionen und Rechnen

Bild-Upload ist eine eigene gespeicherte Arbeitsfläche: erst Entwurf explizit speichern,
dann navigieren; ungespeicherte Änderungen sichtbar warnen. Kein Upload im Hintergrund,
der dem noch offenen Editor heimlich einen neuen CAS-Wert unterschiebt.
Uploadfelder `file`, `caption`, `source_url`, `source_license`, `fetched_at`, CSRF und
Originalkontext; Größen-/MIME-/Magic-Bytes-Vertrag bleibt R1. Metadaten niemals abrufen.
Bildreihenfolge, Beschriftung und Schrittbildbindung laufen über den vollständigen Editor;
ein entferntes Hauptbild darf den erhaltenen Schritt-/Revisionsursprung nicht verlieren.

Revision zeigt UUID, Nummer, Hash, Datum, Herkunft und unveränderten Snapshot. Keine
Live-Foodnamen/Faktoren in historische Berechnung mischen. Gleiches Freeze ergibt 409.
Skalierung zeigt „Ausbeute/Menge“, ursprüngliche Menge/Einheit und positive Zielmenge;
`parse_quantity` und `scale_servings(quantity, source_servings, target_servings)` verwenden,
keine Floats. Einheit bleibt gleich, keine kg-zu-Portion- oder freie Umrechnung.
Mengenlose Zutaten bleiben mengenlos; ursprüngliche Werte zusätzlich sichtbar. Skalieren
ändert weder Entwurf noch Revision/Audit. Einheiten/Faktoren alter Revision aus Snapshot.

## 5. Disjunkte Pakete und vollständiges Wiring

Pfade in dieser Tabelle relativ zu `reference_scaffold/`; jedes Paket eigener Autor/WT.
Neue Pythonmodule unter 400 Zeilen. Gemeinsame Dateien nur nach expliziter Übergabe.

| Paket | Exklusives Eigentum | Abhängigkeit/Ergebnis |
|---|---|---|
| A0 Revisionsreader | `cafeteria/recipe_store.py`, `recipe_reads.py`, `recipe_types.py`; `tests/test_recipe_revision_list_db.py`; R1-Addendum | Root-WP wp-d8105af574dc: `list_revisions(engine, recipe_public_id, *, limit=50, offset=0) -> tuple[RecipeRevisionSummaryDTO,...]`; frozen Summary ohne Snapshot: public_id/recipe_public_id/revision_number/content_hash_sha256/created_at/created_by; draft.read, READ ONLY/REPEATABLE READ, aktiver Standort, archivierter Parent erlaubt, fehlender/fremder Parent 404, leere Liste (), Nummer DESC/public_id, vorhandenes Paging; keine DDL |
| A1 Formularvertrag | `cafeteria/admin/recipe_forms.py`, `recipe_form_rows.py`, `recipe_errors.py`; `cafeteria/templates/admin/rezepte_conflict.html`; `tests/test_recipe_forms.py`, `test_recipe_form_context_db.py` | Nach R1-Fixes; vollständiger signierter Kontext/Parser/Fehler, read-only Zeilenaktionen; Schnittstellen vor A2–A4 einfrieren |
| A2 Liste/Editor | `cafeteria/admin/recipe_routes.py`; `cafeteria/templates/admin/rezepte.html`, `rezepte_editor.html`, `_rezepte_fields.html`; `tests/test_recipe_routes.py`, `test_recipe_browser.py` | Nach A1; Liste, Suche, vollständiger Editor, Tags/Quelle/Archiv, Row-Actions importieren; kein Shared-JS-Edit |
| A3 Revision/Bilder | `cafeteria/admin/recipe_revision_routes.py`, `recipe_image_routes.py`, `recipe_scaling.py`; `cafeteria/templates/admin/rezepte_revisionen.html`, `rezepte_revision.html`, `rezepte_images.html`, `rezepte_scale.html`; `tests/test_recipe_revision_routes.py`, `test_recipe_images_browser.py`, `test_recipe_scaling.py` | Nach A0/A1; parallel A2, Editor-Bildfeld gehört A2; R3 vollständig konsumiert |
| A4 Kochbücher | `cafeteria/admin/cookbook_routes.py`, `cookbook_forms.py`; `cafeteria/templates/admin/kochbuecher.html`, `kochbuch_editor.html`; `tests/test_cookbook_routes.py`, `test_cookbooks_browser.py` | Nach A1; parallel A2/A3; vorhandene R1-Kochbuchdienste, kein zweiter Store/DML |
| A5 Integration | `cafeteria/admin/__init__.py`, `cafeteria/templates/admin/_workflow_sidebar.html`; `tests/test_admin_blueprint_bootstrap.py`, `test_recipe_navigation_browser.py` | Ein eigener Wiring-Owner nach A2–A4; alle Module registrieren, Rezept/Kochbuch-Einstieg capabilitygerecht, aktive Navigation; gemeinsame Templates nicht nachträglich unowned ändern |

Kein neues CSS/JS vorausgesetzt: native nummerierte Zeilenaktionen sind vollständig nutzbar.
Falls progressive Verbesserung später nötig: eigenes gesondert zugewiesenes Paket, niemals
unbemerkt `admin.js`, Basislayout oder Sprite mitändern. Root besitzt Manifest/Release-Wiring.

## 6. Tabler und messbare Abnahme

Lokale Tabler-Cards, Fieldsets, `.form-control`, `.form-select`, `.form-check`, Alerts,
Badges und native Buttons verwenden. [Offizielle Formelemente](https://docs.tabler.io/ui/forms/elements)
und [Tooltips](https://docs.tabler.io/ui/components/tooltip) am 07.09.2026 konsultiert;
lokale Version/CSP bleibt maßgeblich. Keine neue Dependency/CDN/Inlinefreigabe.
Symbole nur aus vorhandenem Sprite; Speichern/Archivieren/Reaktivieren beschriftet.
Hover und Fokus erklären harmlose Symbolaktionen; native „Symbole“-Legende auch ohne JS.

Jedes Paket: echte Route→Dienst→PG-Readback, gültige vollständige Payloads, CSRF und
400/401/403/404/409/503 einschließlich Auth-/Kontextausfall; keine lediglich gemockte Abnahme.
A1/A2: zwei offene Tabs, Original-CAS, Rollenentzug/Reset, Standortwechsel ohne fremde Reads,
Zeilen neu/einfügen/reordnen/entfernen, Quellenerhalt, fremde UUIDs, maximale Texte/64 Zeilen.
A3: reale Uploads, beschädigt/zu groß/falsches MIME, fremder Hash, erhaltene Revisionsbytes,
Schrittbild nach Entfernen aus Hauptliste, Hash nach Entwurfsänderung unverändert;
Skalierungs-Grenzen/fehlende Mengen/gleiche Einheit und unveränderte DB-Snapshots.
A4: echte Zuordnungsreihenfolge, veralteter Kochbuch-CAS, archivierte Referenzen, genau ein
Audit pro Änderung; no-op und wiederholte Statusaktion nach R1-Vertrag.
A5: Chromium mit JS an/aus bei 390/820/1440, Tastatur, Escape/Abbruch ohne POST, sichtbarer
Fehlerfokus, kopierbare 409-Werte, gleiche Karten ≤1px Differenz, kein Seitenoverflow,
48px-Ziele/8px-Abstand/16px-Felder, CSP/Assets und alle Sidebar-/Revisions-/Bildlinks.
Ruff und normale Mypy mit exakter Baseline; vorhandene `test_quantities.py`, R1-DB-/Race-/
Revisions-/Capabilitytests sowie Tabler-/Blueprinttests auf integriertem Kandidaten ausführen.
Root weist exklusive DB-Pools zu und prüft den gesamten eingefrorenen Kandidaten unabhängig.
Screenshots ergänzen Interaktions-/DB-Belege; manuelle Screenreader-Abnahme gesondert nennen.
Erster startfertiger WP: A0 auf c4c8e354 parallel zu den R1-Fixes; vor A1 gemeinsamen geprüften Stand integrieren, danach disjunkte A2–A4.
R2 gilt erst nach A5 und vollständigen Gates als geliefert; REC-001 umfasst weitere Pakete.
