# PostgreSQL-Datenmodell

Schema-Version 7 modelliert zwei getrennte Angebotsprofile:

| Profil | Zeitraum | Mahlzeiten | Kosteninformationen |
|---|---|---|---|
| `patient` | Montag bis Sonntag | `LUNCH`, `DINNER` | technisch verboten |
| `staff_guest` | Montag bis Freitag | nur `LUNCH` | in `menu_item_prices` verpflichtend |

## Harte Regeln

Die Trigger `validate_menu_week`, `validate_menu_service`, `validate_menu_item`, `validate_menu_item_price` und `validate_publication_revision` lehnen fachlich unzulässige Kombinationen ab. `menu_weeks.profile_id`, `menu_services.menu_week_id` und `menu_items.service_id` sind nach dem Insert unveränderlich; ein Reparenting kann Profil-, Tages- oder Preisregeln nicht umgehen. Ein Patienten-Snapshot mit rekursiven Kosten-Schlüsseln (einschliesslich `UNITPrice`/`PRICEValue` und ungesehener Varianten) oder Kostenwerten wird nicht publiziert. Schlüssel werden kompakt alphanumerisch normalisiert (ohne Case-Grenzen, Trennzeichen und Unicode-Cf) und gegen ein geschlossenes Schema plus verbotene Token geprüft; harmlose Uhrzeiten wie `11.30` bleiben zulässig. Snapshot-Datum, Wochentag, Mahlzeiten, `service_state`, Menüarten und Cafeteria-Kostenstruktur werden exakt geprüft: offen genau zwei Gerichte, geschlossen keine. Cafeteria-Rappenbeträge müssen JSON-Ganzzahlen sein. Cafeteria-Abendessen und Cafeteria-Services am Wochenende werden abgewiesen.

Schliessungen liegen auf `menu_services`, also auf Datum × Profil × Mahlzeit. Cafeteria-Wochenenden werden nicht als Essen erfasst; die Player-Fläche leitet daraus den geschlossenen Zustand ab.

Publikationsrevisionen dürfen nur für eine bereits auf `published` gesetzte Woche eingefügt werden. Insert und `workflow_state`-Demotion sperren dieselbe `menu_weeks`-Zeile `FOR UPDATE` in stabiler Reihenfolge; eine versteckte oder ohne neues Ereignis wieder sichtbare Revision darf dabei nicht entstehen. Snapshotbytes, Revisionscode und die eingefrorene Publikationsidentität (`profile_id`, `location_id`, `week_start`) sind unveränderlich. Ein Rückzug braucht eine kurze replay-sichere Server-Capability (pgcrypto-HMAC über `actor_id`, `revision_id`, `authz_version`, Ablauf und Nonce), nutzt Datenbankzeit und den aus der Capability gebundenen Akteur und schreibt ein unveränderliches `publication_lifecycle_events`-Ereignis; direkte Mutation der Rückzugsfelder bleibt verboten. `cafeteria_app` darf Capabilities nicht ausstellen und Secrets nicht lesen; Task 5 stellt die Capability nach Local-/Entra-Auth über `issue_publication_capability` als Owner/Issuer aus. Bootstrap legt ein zufälliges 32-Byte-Secret an, Rotation ersetzt das aktive Secret und akzeptiert das vorige fünf Minuten lang. `active_publications` zeigt nur nicht zurückgezogene Revisionen mit `workflow_state='published'` und liest Profil und Woche aus der eingefrorenen Revisionsidentität. Eine aus v4 migrierte Draft-Revision wird beim Upgrade zurückgezogen und bleibt unsichtbar. Das Anwendungs-Konto hat für `publication_revisions` `SELECT`, `INSERT` und `EXECUTE` auf `withdraw_publication_revision(revision, capability, reason)`; eine aktive Revision des anderen Profils bleibt ein eigener Datensatz.

## Lokale Anmeldung

`users.auth_provider='local'` koexistiert mit Entra, System und Demo. `local_credentials` speichert einen normalisierten Benutzernamen, ausschließlich Werkzeug-kompatible `scrypt`-/`pbkdf2:sha256`-Hashes, Fehlversuchszähler und Sperrzeit. Rollenänderungen erhöhen `users.authz_version`; sicherheitsrelevante Aktionen werden als unveränderliche `audit_events` durch die Anwendung geschrieben. Es gibt weder Self-Signup noch ein Default-Passwort.

## Migration

`cafeteria.db.run_migrations` führt ausschließlich die feste Reihenfolge `0001_initial_postgresql.sql` (Schema-Version 4), `0002_profile_publication_and_local_auth.sql` (5), `0003_patient_key_and_withdrawal_contracts.sql` (6) und `0004_patient_key_lock_and_capability_contracts.sql` (7) aus. Vor jedem Skip wird der aufgezeichnete SHA-256-Wert gegen die unveränderte Datei geprüft; Drift oder Versionslücken brechen ab. `0001` bis `0003` bleiben byteidentisch. `schema.sql` beschreibt den aktuellen v7-Leerstand, wird vom Runner aber nicht als wiederholbare Migration missbraucht. Das Paket behauptet kein Alembic-Setup.

`cafeteria_app` bleibt für Draft-Tabellen schreibberechtigt und benötigt für Rollenwechsel sowie Passwortrotation `UPDATE` auf `user_role_cache`, `users` und `local_credentials`. Provider, lokale Credentials und Rollensource müssen zusammenpassen; eine Rollenverschiebung erhöht `authz_version` von altem und neuem Benutzer. Es besitzt keine Schreibrechte auf `schema_migrations`, keine Löschrechte auf Benutzer, keine Löschrechte auf Publikationsrevisionen und keine Rechte an Capability-Secrets. Task 5 muss Capabilities nach Local-/Entra-Auth als Owner/Issuer ausstellen.
