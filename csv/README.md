# Küchen-CSV: zwei Profile, zwei Formate

| Datei | Zweck | Umfang |
|---|---|---|
| `menu_cafeteria_template.csv` | leere Vorlage Cafeteria | Montag–Freitag, nur Mittag, zwei Menüarten, zwei Kostenfelder |
| `menu_cafeteria_example.csv` | vollständiges Beispiel KW 36 | 10 Menüzeilen |
| `menu_patient_template.csv` | leere Vorlage Patientenplan | Montag–Sonntag, Mittag und Abend, zwei Menüarten |
| `menu_patient_example.csv` | vollständiges Beispiel KW 36 | 28 Menüzeilen |

Die Patienten-Dateien enthalten keine Kostenspalten. Eine Datei darf nur ein Profil und eine ISO-Kalenderwoche enthalten. Das technische Mehrdateien-Bundle ist nicht mehr der primäre Küchenweg und wurde aus dem MVP entfernt.

Vorlagen, Beispiele und Exporte verwenden Schema 3. Die gemeinsame Spalte `beilage_dazu` steht direkt nach `beilagen` und enthält leer, `suppe` oder `salat`; leer bedeutet «Keine». Schema-2-Dateien ohne diese Spalte bleiben importierbar. Da der Import die Woche vollständig ersetzt, setzt ein Schema-2-Import bestehende Beilagen auf «Keine» und zeigt diesen Hinweis vor der Übernahme. Exporte schreiben immer Schema 3.

Validierung:

```bash
python csv/validate_menu_csv.py csv/menu_cafeteria_example.csv
python csv/validate_menu_csv.py csv/menu_patient_example.csv
```
