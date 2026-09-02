# Microsoft Entra ID / Single Sign-on

## Zielkonfiguration

| Eigenschaft | Festlegung |
|---|---|
| Kontotyp | Nur Konten im Südhang-Tenant (`AzureADMyOrg`) |
| Protokoll | OpenID Connect, Authorization Code Flow |
| Backend-Zugriff | Nur explizit zugewiesene Benutzer oder Sicherheitsgruppen |
| Autorisierung | App-Rollen im Claim `roles` |
| Benutzerkorrelation | `tid` + `oid`, nicht die E-Mail-Adresse |
| Graph-Berechtigungen der Web-App | Für das MVP keine |

## Rollenmodell des MVP

| Rolle | Rechte |
|---|---|
| `Cafeteria.Editor` | Beide Profile erfassen, profilbezogene CSV-Dateien prüfen/importieren, Vorschau und Export |
| `Cafeteria.Publisher` | Enthält die Editor-Rechte und darf eine Revision profilbezogen publizieren oder zurückziehen |
| `Cafeteria.Admin` | Vollzugriff, Audit und Diagnose |

Die Publikationsrolle enthält bewusst Erfassungsrechte. Eine Person, die fachlich freigibt, darf notwendige Korrekturen vor der Freigabe durchführen; das frühere Modell „publizieren, aber nicht bearbeiten“ entfällt.

## Bereitstellung

```powershell
Install-Module Microsoft.Graph -Scope CurrentUser
./configure-entra-app.ps1 `
  -TenantId '<TENANT-ID>' `
  -BaseUrl 'https://dishboard.joelduss.xyz' `
  -AllowLocalhostRedirect `
  -WhatIf
```

Nach der Kontrolle `-WhatIf` entfernen. Für optionale Gruppenzuweisungen `group-assignments.example.json` kopieren, reale Gruppen-Objekt-IDs eintragen und die Kopie über `-GroupAssignmentsPath` angeben.

## Client-Credential

Das Compose-Beispiel liest das Client Secret aus einem Docker Secret. Es gehört nicht in Git, `.env`, Prozessargumente oder Logs. Ein Zertifikat kann später als betriebliche Härtung ergänzt werden, ist aber kein eigener Anwendungsstack.

## Redirect und Logout

Die erlaubten URLs stehen in `redirect-uris.txt`: `https://dishboard.joelduss.xyz/auth/callback` und `https://dishboard.joelduss.xyz/auth/frontchannel-logout`. Änderungen am Hostnamen oder Reverse-Proxy-Pfad müssen gleichzeitig in Entra und `APP_PUBLIC_BASE_URL` nachgeführt werden. Beim Produktionsstart mit `ENTRA_ENABLED=true` lehnt der Entrypoint Platzhalter-IDs sowie das Bootstrap-Platzhaltersecret ab.
