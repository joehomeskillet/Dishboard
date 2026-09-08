# CSV-Import und -Export

## Zwei getrennte Formate

| Datei | Profil | Vollständige Woche | Besonderheit |
|---|---|---:|---|
| `csv/menu_patient_template.csv` | `patient` | 28 Zeilen | Mo–So × Mittag/Abend × zwei Menüarten; keine Kostenspalten |
| `csv/menu_cafeteria_template.csv` | `staff_guest` | 10 Zeilen | Mo–Fr × Mittag × zwei Menüarten; zwei Kostenspalten |

Beispieldateien mit Daten derselben Kalenderwoche liegen als `menu_patient_example.csv` und `menu_cafeteria_example.csv` bei.

## Gemeinsame Spalten

`schema_version;profil;datum;wochentag;mahlzeit;menueart;external_id;titel;beschreibung;beilagen;labels;allergene_enthaelt;allergene_spuren;herkunft;hinweis;zustand;zustand_text`

Die Cafeteria ergänzt:

`preis_mitarbeitende_chf;preis_externe_chf`

## Regeln

- Trennzeichen: Semikolon; UTF-8 mit optionalem BOM.
- Eine Datei enthält genau ein Profil und genau eine Kalenderwoche.
- `menueart`: `MENU_1` oder `VEGGIE`.
- `mahlzeit`: Patienten `LUNCH` oder `DINNER`; Cafeteria ausschliesslich `LUNCH`.
- Mehrfachwerte werden mit `|` getrennt.
- Herkunft: `Zutat=CH|Zutat=DE`.
- Kosten: Dezimalwert mit zwei Stellen, beispielsweise `11.00`; nur im Cafeteriaformat.
- Geschlossene Services benötigen `zustand` und einen verständlichen `zustand_text`.
- Leere Allergenspalten bedeuten „nicht deklariert“, nicht automatisch „allergenfrei“.
- Der Export neutralisiert Zellen, die mit `=`, `+`, `-` oder `@` beginnen, gegen Tabellenkalkulationsformeln.

## Validierung

```bash
python csv/validate_menu_csv.py csv/menu_patient_example.csv --json
python csv/validate_menu_csv.py csv/menu_cafeteria_example.csv --json
```

Abgewiesen werden insbesondere:

- gemischte Profile,
- Patientenformat mit Kostenfeldern,
- Cafeteria-Abendessen,
- Cafeteria-Samstag oder -Sonntag,
- fehlende Menüart,
- doppelte Kombination aus Datum, Mahlzeit und Menüart,
- ungültige Kostenformate,
- leere `external_id` oder Titel.

Der vollständige Import in den Editor muss zuerst eine Vorschau mit Zeile, Spalte und Fehlertext zeigen. Ohne fehlerfreie Vorschau wird kein Datensatz übernommen.

## Rezeptvorschau: Dishboard CSV/JSON Version 1

Dieses eigene Rezeptformat ist vom Menüwochenformat oben getrennt. Der reine Pythonparser
`cafeteria.recipe_import.parse_recipe_import(data, filename=..., content_type=..., fetched_at=...)`
prüft Bytes und liefert eine unveränderliche Vorschau. Er lädt keine Datei oder URL, legt
keinen Datenbankstapel an und übernimmt oder veröffentlicht nichts. Eine Uploadoberfläche,
persistente Importstapel und deren bestätigte Übernahme sind noch nicht enthalten. XLSX,
Schema.org, Tandoor-Exporte und Pauli-Dateien sind keine zugesagten v1-Eingabeformate.

### Grenzen und CSV-Spalten

- Höchstens 5 MiB (5 × 1024 × 1024 Bytes), mindestens ein und höchstens 2000 Rezepte.
  Ein CSV-Record beziehungsweise JSON-Arrayelement zählt als Rezeptzeile; physische
  Zeilenumbrüche innerhalb eines Felds zählen nicht als weitere Rezepte. Fehlerhafte Records
  zählen mit. Es gibt weder stilles Abschneiden noch Erfolg für eine gültige Teilmenge.
- Inhaltstyp exakt `text/csv` oder `application/json`. Der spätere Uploadadapter muss einen
  vorhandenen MIME-Parser verwenden und dessen reinen Inhaltstyp übergeben. Dateiendungen
  ersetzen diese Prüfung nicht.
- UTF-8 ohne NUL; ein führendes BOM ist nur bei CSV erlaubt. CSV verwendet Semikolon und
  normale Anführungszeichen/verdoppelte innere Anführungszeichen. Keine Makros oder Bilder.
- Jedes dekodierte CSV-Feld darf höchstens **120 × 1024 UTF-8-Bytes** enthalten. Umlaute zählen
  mit ihrer tatsächlichen Bytezahl. Das globale Python-CSV-Feldlimit wird nicht verändert;
  ein extern kleiner eingestelltes Limit führt zu einem kontrollierten Dateifehler ohne
  Teilimport. Für größere einzelne Rezeptfelder steht JSON innerhalb der 5-MiB-Grenze bereit.
- Dateiname: 1–200 Zeichen, kein Pfad, Slash, Backslash, Steuerzeichen, `.` oder `..`.
  Die Abrufzeit kommt als zeitzonenbewusster Zeitpunkt vom Aufrufer.

CSV hat genau diese Spalten in dieser Reihenfolge, mit `1` in jeder `schema_version`-Zelle:

```text
schema_version;title;description;servings;servings_unit_code;prep_minutes;cook_minutes;source_url;source_note;ingredients;steps
```

Ein Record enthält ein vollständiges Rezept. `ingredients` und `steps` sind JSON-Arrays in
den entsprechend CSV-quotierten Zellen. Leere Arrayzellen sind ungültig; ausdrücklich `[]`
ist erlaubt. Optionale Kopftexte und Minuten werden bei leerer CSV-Zelle `null`.
Zusätzliche, doppelte, fehlende oder vertauschte Kopfspalten werden abgewiesen.

### JSON und fachliche Felder

JSON hat genau den folgenden Envelope; `schema_version` ist die Ganzzahl `1`, kein Boolean.
Alle gezeigten Felder sind obligatorisch, optionale Werte werden ausdrücklich `null` gesetzt.
Dasselbe Rezeptobjekt entspricht einem CSV-Record ohne dessen `schema_version`-Spalte.

```json
{
  "schema_version": 1,
  "recipes": [{
    "title": "Kartoffelsuppe",
    "description": null,
    "servings": "4",
    "servings_unit_code": "PORTION",
    "prep_minutes": 10,
    "cook_minutes": 20,
    "source_url": null,
    "source_note": "Eigene Aufzeichnung",
    "ingredients": [{
      "group_label": null,
      "ingredient_text": "Kartoffeln",
      "quantity": "0.750000",
      "unit_code": "KG",
      "note": null
    }],
    "steps": [{"instruction": "Kartoffeln garen.", "duration_minutes": 20}]
  }]
}
```

Mengen sind positive endliche **Dezimalstrings**, niemals JSON-Zahlen/Float. Es gelten die
vorhandenen Mengenregeln: höchstens 12 Vorkomma- und 6 relevante Nachkommastellen, ohne
Rundung oder Kürzung. Nicht relevante Endnullen dürfen normalisiert werden. Menge und
Einheit sind gemeinsam gesetzt oder gemeinsam `null`; die Rezeptausbeute ist erforderlich.
Einheitencodes werden syntaktisch geprüft, ihre Existenz und Verwendbarkeit erst später.

Titel: 120 Zeichen; Beschreibung: 2000; Zutatenbezeichnung/Notiz: 500; Zutatengruppe: 120;
Schritttext: 8000. Zutaten und Schritte haben jeweils höchstens 64 Einträge und behalten ihre
Reihenfolge. Texte folgen der bestehenden NFC-/Whitespace-/Klartextvalidierung. Minuten
sind Ganzzahlen zwischen 0 und 10080 oder `null`. Die optionale HTTP(S)-Quellenadresse ist
auf 2048 Zeichen begrenzt und wird nie abgerufen. Die Quellennotiz darf höchstens 400 Zeichen
enthalten; der Rest des bestehenden 500-Zeichen-Quellenfelds bleibt für den Dateihash frei.

Doppelte JSON-Schlüssel, unbekannte Felder, NaN/Infinity und mehr als zwölf Strukturebenen
werden abgewiesen. Food-, Tag-, Rezept- und Zeilen-UUIDs, Zielversionen, Bilder, Allergene,
Nährwerte und Freigaben gehören nicht in diese v1-Datei. Ihre Anwesenheit führt zu Fehlern;
sie werden nicht still ignoriert oder als bestätigte Fachangabe übernommen.

### Vorschau, Herkunft und spätere Übernahme

Die Vorschau bewahrt Dateiname, SHA-256 der **Originalbytes**, Abrufzeit und 1-basierte
Rezeptzeilennummer. CSV nennt zusätzlich die physische Anfangszeile des Records einschließlich
Kopfzeile; JSON verwendet die Arrayposition. Fehler nennen Zeile, Feldpfad (beispielsweise
`ingredients[0].quantity`), Fehlercode und verständlichen Text ohne rohe Eingabewerte.
Höchstens 16 Feldfehler plus ein Hinweis auf weitere Fehler werden je Zeile ausgegeben.
Eine fehlerhafte Zeile hat keinen Teilpayload; andere Zeilen bleiben zur Korrektur sichtbar.
Dateistruktur-/Größenfehler geben keine teilweise gültige Zeilenmenge frei.

Gültige Preview-Payloads nutzen den vorhandenen Rezeptvertrag: `source.kind='file_import'`,
Referenz `sha256:<Dateihash>:row:<Zeilennummer>`, Originalquellenadresse, Dateihash plus optionale
Notiz und Abrufzeit. Jede Zutatenzeile trägt dieselbe Importherkunft. Die verschachtelten
Werte sind unveränderlich; Bilder/Tags sind leer, Food-/Zeilen-IDs und Schrittbildhashes `null`.
Diese SHA-Referenz ist **nur eine Vorschauherkunft**. Vor einer echten Übernahme muss der
spätere R6-Writer gemäß Datenvertrag die persistente Stapel-UUID plus Zeilennummer einsetzen
und Dateibeleg, ursprüngliche Zielversionen und Standort sichern.

Gleiche normalisierte, ohne Groß-/Kleinschreibung verglichene Titel bilden sichtbare
Dubletten-Gruppen mit allen Zeilennummern, auch bei sonst fehlerhaften Zeilen. Keine Zeile
wird zusammengeführt, verworfen oder automatisch einem bestehenden Rezept zugeordnet.
Bestandsdubletten können ohne Datenbank nicht erkannt werden.

`is_valid` bezeichnet ausschließlich die vollständige Parse-/Fachvalidität der Vorschau.
Jeder Datei-/Zeilenfehler setzt sie auf `false`. Sie ist **keine Commit-Bereitschaft**:
Auch bei `true` muss der spätere Writer Dublettenentscheidungen, Einheiten/Ziele, Standort,
`recipe.import`, ursprüngliche Actor-/Stapel-/Zielversionen, atomare Übernahme und Audit
prüfen. Ein Import darf weder Menüs veröffentlichen noch Allergene automatisch bestätigen.
Späterer CSV-Export muss weiterhin Tabellenkalkulationsformeln neutralisieren; der Parser
selbst führt Feldinhalte niemals aus.
