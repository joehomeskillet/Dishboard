# PostgreSQL-Datenmodell

Die SQL-Baseline modelliert zwei getrennte Angebotsprofile:

| Profil | Zeitraum | Mahlzeiten | Kosteninformationen |
|---|---|---|---|
| `patient` | Montag bis Sonntag | `LUNCH`, `DINNER` | technisch verboten |
| `staff_guest` | Montag bis Freitag | nur `LUNCH` | in `menu_item_prices` verpflichtend |

## Harte Regeln

Die Trigger `validate_menu_service`, `validate_menu_item_price` und `validate_publication_revision` lehnen fachlich unzulässige Kombinationen ab. Ein Patienten-Snapshot mit Kosten-Schlüsseln, `CHF` oder `0.00` wird nicht publiziert. Cafeteria-Abendessen und Cafeteria-Services am Wochenende werden abgewiesen.

Schliessungen liegen auf `menu_services`, also auf Woche × Profil × Datum × Mahlzeit. Cafeteria-Wochenenden werden nicht als Essen erfasst; die Player-Fläche leitet daraus den geschlossenen Zustand ab.

## Migration

`migrations/0001_initial_postgresql.sql` ist bewusst eine SQL-Baseline für eine leere PostgreSQL-Datenbank. Das Paket behauptet kein Alembic-Setup. Änderungen an einer bereits betriebenen Datenbank benötigen vor dem Einsatz eine echte Folgemigration.
