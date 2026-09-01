# Küchen-CSV: zwei Profile, zwei Formate

| Datei | Zweck | Umfang |
|---|---|---|
| `menu_cafeteria_template.csv` | leere Vorlage Cafeteria | Montag–Freitag, nur Mittag, zwei Menüarten, zwei Kostenfelder |
| `menu_cafeteria_example.csv` | vollständiges Beispiel KW 36 | 10 Menüzeilen |
| `menu_patient_template.csv` | leere Vorlage Patientenplan | Montag–Sonntag, Mittag und Abend, zwei Menüarten |
| `menu_patient_example.csv` | vollständiges Beispiel KW 36 | 28 Menüzeilen |

Die Patienten-Dateien enthalten keine Kostenspalten. Eine Datei darf nur ein Profil und eine ISO-Kalenderwoche enthalten. Das technische Mehrdateien-Bundle ist nicht mehr der primäre Küchenweg und wurde aus dem MVP entfernt.

Validierung:

```bash
python csv/validate_menu_csv.py csv/menu_cafeteria_example.csv
python csv/validate_menu_csv.py csv/menu_patient_example.csv
```
