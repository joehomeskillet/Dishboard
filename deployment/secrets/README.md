# Docker-Secrets

`bootstrap.sh` erzeugt folgende lokale Dateien mit Berechtigung `0600`:

| Datei | Zweck |
|---|---|
| `postgres_owner_password.txt` | PostgreSQL-Eigentümer, Migration und Restore |
| `postgres_app_password.txt` | Nicht privilegiertes Flask-Laufzeitkonto |
| `postgres_backup_password.txt` | Lesendes Backupkonto |
| `flask_secret_key.txt` | Signierung der Session-ID |
| `redis_password.txt` | Redis-Authentisierung |
| `entra_client_secret.txt` | Platzhalter; für Produktion ersetzen |

Dateien `*.txt` dürfen nicht in Git oder ein Image gelangen. Der App-Service erhält nur App-, Flask-, Entra- und Redis-Secret; Eigentümer- und Backupsecret werden ihm nicht gemountet.

Eine nachträgliche Änderung einer PostgreSQL-Secret-Datei ändert das bereits in PostgreSQL gesetzte Rollenpasswort nicht automatisch. Die Rotation muss kontrolliert über den Migrationsdienst erfolgen. Für Entra ist langfristig ein Zertifikat oder zentraler Secret Store einem dauerhaft gespeicherten Client Secret vorzuziehen.
