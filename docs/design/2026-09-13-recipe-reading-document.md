# Gemeinsames Rezeptblatt für Ansicht und PDF

Vertrag vom 13. September 2026; WP `wp-a52430b2b917`, Basis `9aa03c3bff070333258942589a512fc3c8ce5dc2`.
Quelle ist der neue ausdrückliche Nutzerauftrag: dedizierte Rezeptansicht ohne
Formfelder und ein ähnlich aufgebautes, lesbares HTML-/PDF-Rezeptblatt mit Icons.
Er ersetzt die ältere Bindung an bytegleiche **gerenderte v1-PDF-Ausgabe**.
Snapshotbytes, gespeicherte Hashes, Revisionsidentitäten und History bleiben strikt
unveränderlich. Kein neuer Snapshot, keine Migration, kein Speichern durch Lesen.

Das unabhängige Audit `recipe-readable-audit-0913/audit-metrics.json` belegt beim
ausgewählten vorhandenen Stand vier Zutaten, zwei Schritte, zwei PDF-Seiten und
fehlende bekannte Zeiten in der HTML-Ansicht. Ein Legacy-Beispiel hat keine Schritte.
Diese externen Auditdaten sind Referenz, keine neuen Testfixtures oder Baselines.
Der Vertrag ist noch keine HTML-/PDF-Implementierung oder visuelle Abnahme.

## Öffentliche Schnittstelle

```python
from cafeteria.admin.recipe_document import DOCUMENT_VERSION, build_recipe_document

DOCUMENT_VERSION = 'recipe-reading-v1'

def build_recipe_document(
    payload: Mapping[str, Any],
    target: str | None = None,
    *,
    revision: RecipeRevisionDTO | None = None,
) -> dict[str, Any]: ...
```

`payload` ist der bestehende vollständige Rezeptpayload, kein Formular oder
Teilpayload. Mit `revision` muss er genau `revision.snapshot['recipe']` entsprechen,
auch bei v1; ein aktueller Entwurf darf nie als alter gespeicherter Stand erscheinen.
Revisionsmetadaten und vorhandene kanonische Bytes werden geprüft; v2-Kinder werden
durch die bestehende `scaled_recipe`-/`verified_prepared`-Kette gebunden. Die bestehenden
Reader bleiben für Standort, Rechte, RR-Transaktion und Originaldaten zuständig.
Ohne Revision ist die Ausgabe ausdrücklich `draft`; keine Standnummer, UUID oder
Prüfsumme wird erfunden. Den Rezeptkopf-/Archivkontext ergänzt der vorhandene Caller.

Nur `scaled_recipe(payload, target, revision=revision)` rechnet Mengen. Der Helper
konvertiert selbst keine Einheiten und validiert interne Kind-Zielmengen nicht erneut
als sechsstellige Speichereingabe. Vorhandene eingefrorene Faktoren und exakte
Kindrevisionen bestimmen diese Berechnungen; nie aktuelle Foodpins oder „latest“.
Ungültiges Benutzerziel behält den bisherigen `FormError(field='yield')`;
ungültige gespeicherte Daten ergeben `RecipeConfigurationError`.
Keine I/O, DB-Abfrage, Assetauflösung, HTML-Markierung oder Mutation eines Inputs.
Ergebniscontainer sind neue Python-Dicts/-Listen, keine persistente Datenstruktur.

## Exakte Ausgabefelder

Alle nachstehenden Schlüssel sind immer vorhanden. `None` bedeutet nicht erfasst;
null Mengen und null Zeiten werden weder zu null Gramm noch zu null Minuten gemacht.

| Feld | Form und Bedeutung |
|---|---|
| `document_version` | String `recipe-reading-v1`, Version dieses Projektionsvertrags, keine Rezeptrevision. |
| `identity` | Dict `kind` (`draft`/`revision`), `recipe_public_id`, `revision_public_id`, `revision_number`, `content_hash_sha256`, `created_at`. Bei Entwurf sind die letzten fünf Werte `None`; sonst originale Identitäten und ISO-Zeitpunkt. |
| `title`, `description` | Vollständiger Originaltitel und ursprüngliche Beschreibung (`str`/`None`). |
| `yield` | Dict `amount` (führende berechnete Decimal-Zeichenfolge), `unit` (Originalcode), `original_amount` (ursprünglicher Ausbeutewert), `is_scaled` (bool), `measurement_status` (`None`: kein strukturiertes Messurteil im bestehenden Payload). |
| `times` | Dict `prep_minutes`, `cook_minutes`, je ursprünglicher Integer oder `None`; 0 ist bekannt. Keine erfundene Gesamtzeit. |
| `warnings` | Liste von Dicts `code`, `text`. `allergens_unrecorded`: „Allergenangaben sind in diesen Rezeptdaten nicht erfasst.“; zusätzlich `ai_source`: „KI-unterstützte Angaben; vor Verwendung fachlich prüfen.“, wenn eine vorhandene Herkunft KI-unterstützt ist. Keine Freigabe-/Ungeprüft-Behauptung aus blosser Persistenz. |
| `source_notes` | Liste vollständiger nicht-null Herkunftsnotizen aus den deduplizierten Records. Sichtbar vor dem Lesekern; nicht im technischen Detailbereich verstecken. |
| `ingredients` | Geordnete Liste mit `number` (1-basiert), `line_public_id`, `food_public_id`, `group_label`, `text`, `amount`, `unit`, `original_amount`, `note`, `source_id`. Reihenfolge, gleiche Namen und wiederkehrende Gruppen bleiben erhalten; keine Aggregation. |
| `steps` | Geordnete Liste `number` (1-basiert), `instruction`, `duration_minutes`, `image_sha256`. Vollständige Absätze und 0-Minuten-Angaben erhalten. |
| `empty_ingredients`, `empty_steps` | `None` bei vorhandenen Zeilen, sonst „Keine Zutaten gespeichert.“ bzw. „Keine Schritte gespeichert.“. Keine erfundene Anleitung. |
| `images` | Originale Bildmetadaten, je `sha256`, `caption`, `source_url`, `source_license`, `fetched_at`; keine Livebilder, keine erfundenen URLs/Bytedaten. Schrittbildhashes zusätzlich in `steps`. |
| `tag_public_ids` | Kopie der originalen Kennungsfolge. Keine erfundenen Namen, Nährwerte, Bewertungen oder Allergenaussagen. |
| `recipe_source_id` | Integer-ID des Rezept-Herkunftsrecords innerhalb dieses Dokuments. |
| `provenance` | Geordnete Liste `id` (1-basiert), `label`, `source`, `uses`. `source` hat genau `kind`, `reference`, `url`, `note`, `fetched_at`. `uses` enthält `recipe` und/oder `ingredient:N`; nicht durch Titel zuordnen. |
| `prepared` | Flache Liste jeder Verwendung aus `scaled_recipe`, in derselben Reihenfolge: `use_number`, `first_use_number`, `for_ingredient`, `document`. Das Kinddokument hat dieselben Felder einschließlich eigener Identität, Schritte, Bilder, Quellen und berechneter Menge; sein `prepared` ist leer, weil sämtliche Verwendungen bereits flach im Wurzeldokument stehen. |

Ingredient-Herkunft wird aus `source_kind`, `source_reference`, `fetched_at`
gebildet; `url=None` und `note=None`, weil Zutaten keine eigenen Herkunftsfelder
dafür besitzen. `ingredient.note` ist ein Kochhinweis und bleibt ausschließlich
an der Zutat, nicht in `source_notes` oder als Herkunftsnotiz. Rezeptquelle
übernimmt alle fünf vorhandenen Felder. Nur exakt gleiche komplette Records werden
vereinigt. Auch unterschiedliche Zeit-Zeichenfolgen, Notizen oder Nullwerte bleiben
unterschiedlich; keine fuzzy Zusammenfassung. Gleiche Zutatenquelle braucht einen
Herkunftsblock mit allen Zeilenreferenzen, auch bei unterschiedlichen Kochhinweisen.
Vollständige Herkunft kann nach dem Rezept kompakt stehen.

`first_use_number` identifiziert nur die erste Verwendung desselben Paars aus
Kindrevision und Inhaltshash. Keine Verwendung/Menge wird entfernt. Der Helper liefert
auch beim zweiten Gebrauch sämtliche Kind-Schritte und Bildmetadaten. Ein Renderer
darf identische Anleitung/Bilder beim Folgegebrauch durch einen expliziten Verweis
auf den ersten vollständig ausgegebenen Kindblock ersetzen; Menge und Verwendung
bleiben jeweils sichtbar. Abweichende Revision/Hashes werden niemals zusammengelegt.

## Wahrheits- und Lesevertrag

Ein führender Mengenwert je Zutat: `amount` + `unit`. Standardansicht zeigt keine
doppelte Original/Berechnet-Tabelle. Originalausbeute und Originalmengen bleiben in
einem klar bezeichneten Zusatzbereich erreichbar. Eine Ausbeute ohne Messnachweis
heisst „angegebene Ausbeute“, bei Skalierung „berechnete Ausbeute“, niemals „gemessen“.
Vorhandene Notizen zu ungeprüften Daten, KI, nicht geprüften Allergenen oder nicht
gemessener Ausbeute müssen unverändert sichtbar bleiben. Freitext wird nicht in neue
fachliche Statusflags umgedeutet. Warnings und Quellennotizen dürfen nicht zugunsten
einer kürzeren Seite verschwinden oder erst in „Technische Details“ erscheinen.

Ansicht ist Lesen: keine Input-, Select-, Textarea- oder readonly/disabled-Formfelder
im Rezeptblatt. Bearbeiten, Drucken, History und vorhandene Mengenanpassung sind
klar beschriftete getrennte Aktionen; vorhandene Validierungs- und Zielparameter
bleiben erhalten. Entwurf und exakter gespeicherter Stand sind sichtbar verschieden.
HTML-Reader und PDF erhalten dasselbe Dokument und unterscheiden nur Ausgabeform.

## Gemeinsamer Aufbau und Pagination

- Vorhandene Fira-Schriften, Tabler-Bausteine, aktive Marken-/Druckvorlagen und
  gepinnte Icons nutzen. Keine Vendor-/Frameworkänderung. Für Hauptaktionen sichtbare
  Beschriftung; rein dekorative SVGs vor Screenreadern verbergen, Iconaktionen benennen.
- Titel und Revisions-/Entwurfkontext zuerst, dann Beschreibung, bekannte Zeiten,
  Ausbeute und wichtige Warnungen/Notizen. Keine leeren Metadatenkarten.
- Desktop und A4: Zutaten ungefähr ein Drittel, Zubereitung ungefähr zwei Drittel
  der verfügbaren Breite. Mobile und enger Reflow: gleiche natürliche Reihenfolge
  gestapelt. Vollständige Schritttexte und Gruppennamen; keine Ellipsen.
- Rezept-/Schrittbilder bleiben bei ihrem Inhalt mit Herkunft/Lizenz; fehlende
  benötigte Assets kontrolliert melden statt still weglassen. HTML nutzt bestehende
  scoped Assetroute, PDF bereits exakt geladene/verifizierte Assetbytes.
- Kleine Rezepte sollen bei passenden Textlängen auf eine A4-Seite passen; keine
  generelle Einseitenpflicht durch Schrumpfen oder Datenverlust. 11pt Standardtext
  und vorhandene größere Einstellung respektieren. Header/Footer und Vorlagenränder
  bleiben wirksam. Keine unbedingte neue Seite je Herkunft oder Kindverwendung.
- Lange Zutaten, Schritte, Quellen und Unterrezepte fließen vollständig über Seiten.
  Überschrift nicht ohne Folgeinhalt; überhohe Absätze teilen, nie abschneiden oder
  über Footer schreiben. Seitennummern und Fortsetzung sind verständlich.

## Consumer- und Versionsgates

HTML/PDF-Worker ändern getrennte Consumer nach Root-Integration dieses Helpers.
Gemeinsame Tests verwenden synthetische Daten: vollständig 4/2, lang 60/40, fehlende
Legacy-Menge/Schritte, KI-/Quellnotizen, 0/null-Zeiten, Bilder, wiederholte Kindverwendungen
und abweichende Herkunft. PDF prüft vollständigen Text, Seitenkoordinaten, Bildidentität
und lesbare Typografie; HTML prüft echte Inhalte, keine Formularfelder im Lesekern,
JS/NoJS und 1440/390 plus 1024/768/1920/2560/320 sowie nativen 200%-Zoom.
Dieser Contract-WP führt nur pure Unitprüfungen aus.

Die aktuelle PDF-Route ist `200` mit `Cache-Control: no-store`, ohne ETag. Dieser
Vertrag verlangt keinen neuen Cachelayer. Ein alter `If-None-Match` muss weiter
`200`/`no-store` ergeben, nicht still alte Layoutbytes bestätigen. `document_version`
steht Consumer-Golden-/Metadatenprüfungen zur Verfügung. Sollte später bereits
autorisierte Caching-Infrastruktur verwendet werden, müssen Layoutversion und
ausgewählte Rezept-/Template-/Markenidentität Teil dieser Identität sein; das ist
kein Auftrag, sie jetzt einzuführen. Content-Hash bleibt ausschließlich Snapshot-Hash.
