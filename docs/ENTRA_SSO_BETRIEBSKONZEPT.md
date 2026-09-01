# Microsoft-Entra-SSO-Betriebskonzept

## Geltungsbereich

Entra schützt nur das Küchen- und Administrationsbackend. Website, Druck, Signage und veröffentlichte Snapshot-API bleiben anonym erreichbar, geben aber ausschliesslich publizierte Daten aus.

## Rollen

| Rolle | Gruppe, Beispiel | Rechte |
|---|---|---|
| `Cafeteria.Editor` | `SG-Menuplan-Editor` | Patienten- und Cafeteriaraster bearbeiten, CSV prüfen/importieren |
| `Cafeteria.Publisher` | `SG-Menuplan-Publisher` | Editor-Rechte plus profilbezogen publizieren/zurückziehen |
| `Cafeteria.Admin` | `SG-Menuplan-Admin` | Vollzugriff und Audit/Diagnose |

`Assignment required` wird auf der Enterprise Application aktiviert. Verschachtelte Gruppen werden nicht als Voraussetzung eingeplant.

## Anmeldung

- Single-Tenant OIDC Authorization Code Flow.
- Identität über `tid` + `oid`; E-Mail ist kein Primärschlüssel.
- Rollen aus dem `roles`-Claim.
- Serverseitige Redis-Session mit sicherem Cookie.
- Lokaler Logout löscht die Anwendungssitzung; Entra-End-Session wird aufgerufen.
- Kein lokales Passwort und keine Self-Service-Registrierung.

## Demo und Produktion

Der Demo-Login weist nur Editor und Publisher zu. Bei `APP_ENV=production` verweigert die Anwendung den Start, sobald `DEMO_MODE`, `SEED_DEMO` oder `DEMO_TODAY` aktiv beziehungsweise gesetzt sind. Produktiv müssen reale Tenant-, Client- und Credentialwerte vorhanden sein.

## Bereitstellung

```powershell
./entra/configure-entra-app.ps1 `
  -TenantId '<TENANT-ID>' `
  -BaseUrl 'https://cafeteria.suedhang.ch' `
  -WhatIf
```

Nach Prüfung wird `-WhatIf` entfernt. Das Skript liest `app-roles-manifest.json` und kann Gruppenzuweisungen aus einer angepassten Kopie von `group-assignments.example.json` setzen.

## Abnahmetests

1. Zugewiesener Editor kann beide Entwürfe bearbeiten, aber nicht publizieren.
2. Publisher kann korrigieren und getrennt nach Profil publizieren.
3. Admin besitzt Vollzugriff.
4. Nicht zugewiesener Benutzer wird abgewiesen.
5. Rollenentzug beendet den Zugriff spätestens nach Sitzungsablauf; administrativer Sitzungswiderruf wird geprüft.
6. Logout entfernt die lokale Session.
7. Keine Entra- oder Sessiondaten erscheinen in öffentlichen Snapshots oder Logs.
