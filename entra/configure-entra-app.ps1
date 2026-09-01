#requires -Version 7.2
<#
.SYNOPSIS
    Erstellt oder aktualisiert die Single-Tenant-App-Registrierung für Südhang Cafeteria.
.DESCRIPTION
    Verwendet Microsoft Graph PowerShell. App-Rollen werden aus app-roles-manifest.json
    übernommen. Bestehende App-Rollen dieser Registrierung werden durch das Manifest ersetzt.
    Die Web-App verwendet den OIDC Authorization Code Flow; implizite ID- und Access-Tokens sind deaktiviert.
    Gruppenzuweisungen sind optional und werden über eine JSON-Datei mit Rollenwert -> Gruppen-ID gesetzt.
.EXAMPLE
    ./configure-entra-app.ps1 -TenantId '<TENANT-ID>' -BaseUrl 'https://cafeteria.suedhang.ch' -WhatIf
#>
[CmdletBinding(SupportsShouldProcess = $true, ConfirmImpact = 'High')]
param(
    [Parameter(Mandatory)] [ValidatePattern('^[0-9a-fA-F-]{36}$')] [string] $TenantId,
    [Parameter()] [string] $DisplayName = 'Klinik Südhang Cafeteria',
    [Parameter(Mandatory)] [ValidatePattern('^https?://')] [string] $BaseUrl,
    [Parameter()] [string] $RoleManifestPath = (Join-Path $PSScriptRoot 'app-roles-manifest.json'),
    [Parameter()] [string] $GroupAssignmentsPath,
    [Parameter()] [switch] $AllowLocalhostRedirect
)

Set-StrictMode -Version Latest
$ErrorActionPreference = 'Stop'

if (-not (Get-Module -ListAvailable -Name Microsoft.Graph.Authentication)) {
    throw 'Microsoft Graph PowerShell fehlt. Install-Module Microsoft.Graph -Scope CurrentUser'
}

Import-Module Microsoft.Graph.Authentication
Connect-MgGraph -TenantId $TenantId -Scopes @(
    'Application.ReadWrite.All',
    'AppRoleAssignment.ReadWrite.All',
    'Group.Read.All'
) -NoWelcome

$manifest = Get-Content -LiteralPath $RoleManifestPath -Raw -Encoding UTF8 | ConvertFrom-Json -Depth 20
if (-not $manifest.appRoles -or $manifest.appRoles.Count -lt 1) {
    throw 'Das Rollenmanifest enthält keine appRoles.'
}

$base = $BaseUrl.TrimEnd('/')
$redirectUris = @("$base/auth/callback")
if ($AllowLocalhostRedirect) { $redirectUris += 'http://localhost:8080/auth/callback' }

$filterName = $DisplayName.Replace("'", "''")
$appResult = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/applications?`$filter=displayName eq '$filterName'&`$select=id,appId,displayName,appRoles"
if ($appResult.value.Count -gt 1) { throw "Mehrere App-Registrierungen mit dem Namen '$DisplayName' gefunden." }

$applicationBody = @{
    displayName = $DisplayName
    signInAudience = 'AzureADMyOrg'
    web = @{
        redirectUris = $redirectUris
        homePageUrl = $base
        logoutUrl = "$base/auth/frontchannel-logout"
        implicitGrantSettings = @{ enableIdTokenIssuance = $false; enableAccessTokenIssuance = $false }
    }
    appRoles = @($manifest.appRoles)
}

if ($appResult.value.Count -eq 0) {
    if ($PSCmdlet.ShouldProcess($DisplayName, 'Entra-App-Registrierung erstellen')) {
        $app = Invoke-MgGraphRequest -Method POST -Uri 'https://graph.microsoft.com/v1.0/applications' -Body ($applicationBody | ConvertTo-Json -Depth 20)
    } else { return }
} else {
    $app = $appResult.value[0]
    if ($PSCmdlet.ShouldProcess($DisplayName, 'Redirects und App-Rollen aktualisieren')) {
        Invoke-MgGraphRequest -Method PATCH -Uri "https://graph.microsoft.com/v1.0/applications/$($app.id)" -Body ($applicationBody | ConvertTo-Json -Depth 20)
        $app = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/applications/$($app.id)?`$select=id,appId,displayName,appRoles"
    }
}

$spResult = Invoke-MgGraphRequest -Method GET -Uri "https://graph.microsoft.com/v1.0/servicePrincipals?`$filter=appId eq '$($app.appId)'&`$select=id,appId,displayName,appRoleAssignmentRequired"
if ($spResult.value.Count -eq 0) {
    if ($PSCmdlet.ShouldProcess($DisplayName, 'Service Principal erstellen')) {
        $sp = Invoke-MgGraphRequest -Method POST -Uri 'https://graph.microsoft.com/v1.0/servicePrincipals' -Body (@{ appId = $app.appId } | ConvertTo-Json)
    }
} else { $sp = $spResult.value[0] }

if ($PSCmdlet.ShouldProcess($DisplayName, 'Benutzerzuweisung erforderlich aktivieren')) {
    Invoke-MgGraphRequest -Method PATCH -Uri "https://graph.microsoft.com/v1.0/servicePrincipals/$($sp.id)" -Body (@{ appRoleAssignmentRequired = $true } | ConvertTo-Json)
}

if ($GroupAssignmentsPath) {
    $assignments = Get-Content -LiteralPath $GroupAssignmentsPath -Raw -Encoding UTF8 | ConvertFrom-Json -AsHashtable
    $rolesByValue = @{}
    foreach ($role in $app.appRoles) { $rolesByValue[$role.value] = $role }
    foreach ($entry in $assignments.GetEnumerator()) {
        $roleValue = [string] $entry.Key
        $groupId = [string] $entry.Value
        if (-not $rolesByValue.ContainsKey($roleValue)) { throw "Unbekannte Rolle in Gruppenzuweisung: $roleValue" }
        $body = @{ principalId = $groupId; resourceId = $sp.id; appRoleId = $rolesByValue[$roleValue].id }
        if ($PSCmdlet.ShouldProcess("Gruppe $groupId", "Rolle $roleValue zuweisen")) {
            try {
                Invoke-MgGraphRequest -Method POST -Uri "https://graph.microsoft.com/v1.0/groups/$groupId/appRoleAssignments" -Body ($body | ConvertTo-Json)
            } catch {
                if ($_.Exception.Message -notmatch 'Permission being assigned already exists') { throw }
            }
        }
    }
}

[pscustomobject]@{
    TenantId = $TenantId
    ApplicationObjectId = $app.id
    ClientId = $app.appId
    ServicePrincipalObjectId = $sp.id
    RedirectUris = $redirectUris -join ', '
    AppRoles = ($app.appRoles.value | Sort-Object) -join ', '
} | Format-List
