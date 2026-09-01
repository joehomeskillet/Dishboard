# Flask-Referenzgerüst

Das Gerüst zeigt die geforderte Kanaltrennung, ist aber noch kein fertiger Wocheneditor.

## Öffentliche Webansichten

- `/cafeteria/heute/`
- `/cafeteria/wochenangebot/`
- `/patienten/heute/`
- `/patienten/wochenplan/`
- `/druck/cafeteria/woche`
- `/druck/patienten/woche`

## Feste Player-Flächen

- `/signage/cafeteria/tag`
- `/signage/cafeteria/woche`
- `/signage/patienten/tag`
- `/signage/patienten/woche`

Player-URLs akzeptieren keine Query-Parameter. Tag und Woche eines Profils lesen denselben publizierten Snapshot. Ein letzter gültiger Snapshot wird bei erfolgreichem Lesen atomar im konfigurierten `LAST_GOOD_DIR` abgelegt und bei Datenbankfehlern verwendet.

## Rollen

Das MVP verwendet drei Entra-App-Rollen: Redaktion, Redaktion plus Publikation und Administration. Die Publikationsrolle darf auch erfassen; eine isolierte Publisher-Rolle ohne Bearbeitungsrecht wurde entfernt.

## Grenzen

Der Code enthält Routing, Snapshot-Lesen, getrennte CSV-Ausgabe, Authentifizierung, CSRF-Prüfung des Upload-POST und statische Zieltemplates. Ein vollständiger Editor, Publikationsdialog und Live-PostgreSQL-E2E bleiben als Umsetzungsarbeit offen.
