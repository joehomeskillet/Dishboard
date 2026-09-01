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
