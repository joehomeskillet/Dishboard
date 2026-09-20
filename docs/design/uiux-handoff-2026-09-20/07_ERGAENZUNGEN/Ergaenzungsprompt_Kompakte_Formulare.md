# Ergänzungsprompt – Kompakte, einfache Formulare

Überarbeite UI-Bereiche, die durch wiederholte Felder, lange Listen oder unnötige Abstände zu viel Platz benötigen.

## Ziel
Bedienung auf einen Blick verständlich, kompakt und fehlertolerant. Funktionalität und Datenmodell bleiben erhalten. Keine neuen Frameworks.

## Regeln
- Wiederholte Optionen nicht als lange zweispaltige Formularlisten darstellen.
- Details nur anzeigen, wenn sie für die aktuelle Auswahl relevant sind (Progressive Disclosure).
- Nicht ausgewählte Optionen erhalten keine dauerhaft sichtbaren Detailfelder.
- Zusammengehörige Auswahl + Status kompakt inline darstellen.
- Häufige Standardfälle mit möglichst wenigen Klicks lösen.
- Desktop-Breite sinnvoll mit 2–3 Spalten nutzen; Mobile auf eine Spalte reduzieren.
- Lange Formulare in kompakte, klar benannte Abschnitte gliedern.
- Bestehende Südhang-/Dishboard-Designsprache beibehalten.

## Beispiel Allergene
Statt Checkbox links + dauerhaft sichtbarem Präsenz-Dropdown rechts:

    Allergene                     Eingabe: ● Manuell  ○ Automatisch

    [✓] Gluten  [enthält ▾]       [ ] Krebstiere
    [✓] Eier    [enthält ▾]       [ ] Fisch
    [ ] Erdnüsse                   [✓] Milch [enthält ▾]
    [ ] Soja                       [ ] Schalenfrüchte
    [ ] Sellerie                   [ ] Senf
    [ ] Sesam                      [ ] Sulfite
    [ ] Lupinen                    [ ] Weichtiere

    3 Allergene ausgewählt

Das Statusfeld erscheint erst nach Auswahl des Allergens. Eine sinnvolle Standardoption darf den Normalfall ohne weiteren Klick abdecken.

## Global anwenden
Suche im gesamten Admin-Frontend zusätzlich nach demselben Anti-Pattern: Option + permanentes Detailfeld, lange Checkbox-/Radio-Listen, wiederholte Labels, grosse Leerflächen und Informationen/Aktionen, die zu früh angezeigt werden.

Nicht nur die Allergenseite korrigieren. Vor Umsetzung kurz betroffene Templates und geplante Vereinfachung dokumentieren; danach implementieren, ohne bestehende Funktionen oder Validierungen zu entfernen.
