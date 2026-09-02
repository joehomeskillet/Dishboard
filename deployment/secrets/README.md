# Docker-Secrets

`bootstrap.sh` erzeugt folgende lokale Dateien mit Berechtigung `0600`:

| Datei | Zweck |
|---|---|
| `postgres_owner_password.txt` | PostgreSQL-Eigentümer, Migration und Restore |
| `postgres_app_password.txt` | Nicht privilegiertes Flask-Laufzeitkonto |
| `postgres_backup_password.txt` | Lesendes Backupkonto |
| `postgres_auth_issuer_password.txt` | Ausschliesslich Aufrufe der fünf Auth-Issuer-Funktionen |
| `flask_secret_key.txt` | Signierung der Session-ID |
| `redis_password.txt` | Redis-Authentisierung |
| `entra_client_secret.txt` | Platzhalter; für Produktion ersetzen |

Dateien `*.txt` dürfen nicht in Git oder ein Image gelangen. Das Issuer-Secret
wird einmal zufällig erzeugt und nur an Migration und App gemountet. Es muss von
Owner-, App- und Backup-Secret verschieden sein; eine vollständige
`AUTH_ISSUER_DATABASE_URL` ist verboten und wird nicht persistiert. Der
App-Service erhält App-, Auth-Issuer-, Flask-, Entra- und Redis-Secret;
Eigentümer- und Backupsecret werden ihm nicht gemountet.

Eine nachträgliche Änderung einer PostgreSQL-Secret-Datei ändert das bereits in PostgreSQL gesetzte Rollenpasswort nicht automatisch. Die Rotation muss kontrolliert über den Migrationsdienst erfolgen. Für Entra ist langfristig ein Zertifikat oder zentraler Secret Store einem dauerhaft gespeicherten Client Secret vorzuziehen.
