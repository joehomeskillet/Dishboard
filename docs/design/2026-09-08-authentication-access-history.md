# IAM-001: authentication access history

Root architecture decision, 8 September 2026. Implements the remaining access-history
contract from `docs/BACKLOG.md` and screens/templates design section8. Existing account
administration and local-account audit remain separate. No session inventory or expiry
scheduler is introduced. This document is preparation, not implementation acceptance.

## Event meaning and privacy

Record completed application authentication decisions and observed explicit logout
requests. A successful login decision is not a guarantee that a browser accepted a cookie
or that Redis persisted a session after the response. Never infer a logout time from
browser closure, idle expiry or absent data. The UI explains that history starts with
this feature; historical `last_login_at` values are not backfilled as events.

Fixed providers: local and entra. Fixed event families: accepted login, rejected login,
unavailable login, explicit logout, frontchannel local-session clear. Rejection reasons
are a bounded internal enum (credentials, role, flow, throttled, unavailable). Public
authentication responses remain generic. GET login and rejected CSRF do not create
authentication outcomes. A repeated logout with no current identity creates no new row.

Store server timestamp, event UUID, fixed action/provider/reason and nullable verified
identity. Omit submitted usernames, IP addresses, user agents, provider errors, claims,
passwords, tokens, session IDs, cookies and authorization headers. Unknown or unverified
identities have no actor. Names displayed by current identity joins are not historical
name snapshots. Existing append-only retention remains; no invented purge period.

## Write and failure boundary

Reuse `audit_events` through one narrowly typed SECURITY DEFINER function in the
existing auth-issuer boundary. Never grant application INSERT on audit tables and never
accept caller-supplied arbitrary action or JSON details. Validate provider/outcome/reason
combinations and verified identity/authz versions. UUID enables idempotent retries of the
same server-owned event; it does not come from a public form. Safe search_path, ownership,
EXECUTE grants and denial of ordinary application calls are part of the function contract.

Reuse audit_events.public_id for the server event UUID. Generate it once outside any
internal retry loop. Identical UUID plus identical normalized provider/action/reason/
actor/version tuple returns the existing unchanged row; a different tuple with the same
UUID raises a controlled validation error. ON CONFLICT DO NOTHING alone is insufficient.
The writer owns one fixed entity_type (`authentication`) and these actions only:
`auth.login.accepted`, `auth.login.rejected`, `auth.login.unavailable`,
`auth.logout.requested`, `auth.frontchannel.requested`. Its details object contains only
provider, reason and nullable authz_version. No extra table or free-form audit API.

Local and Entra login success require all existing credential/claim/role/rate-counter
checks, then durable authentication-decision recording before granting the session.
Mandatory success audit failure fails closed. Record failed accepted attempts where the
issuer is available; an audit outage yields a fixed safe diagnostic, not invented durability.
Preserve user-before-credentials lock order and rate limiting. Session establishment errors
must not be presented as proof of a usable session; keep safe operational diagnostics.

Existing credential counters and last_login_at describe credential verification, which
already precedes Redis/session success. Preserve their lock semantics. A currently locked
account cannot reach the success reset even with a correct password. New audit outage
after an unlocked valid password must return503 and grant no new session. Account-mutation
atomicity refers to existing administrative create/role/password/disable transactions;
their mandatory audits stay atomic. Do not widen app-role EXECUTE privileges to combine
credential counters with the separate issuer transaction. Never backfill last_login_at.

Logout snapshots only current verified server identity and retains the existing CSRF gate.
Session clearing/revocation must proceed independently of audit failure. Verify old-cookie
replay against real Redis. Frontchannel records only the local session being cleared and
makes no claim of verified provider origin or tenant-wide termination. A Redis revocation
failure must never be reported as confirmed revocation. No change weakens account-mutation
audit atomicity or role invalidation.

Flask-Session deletes the stored Redis session during response saving, after session.clear().
Therefore logout events describe observed requests, not completed deletion. Always reach
the existing safe response even if the audit writer fails. If a previously authenticated
logout identity is now inactive or its version is stale, clear it regardless; record a
NULL actor or the fixed unavailable-audit path without assigning an unverified identity.
No-session repeated requests create no new event.

## Read/UI boundary

Separate `Zugriffsverlauf` from existing `Kontoereignisse`. Both route and read function
require `users.manage`; Publisher `audit.read` remains insufficient. Use a fixed action
allowlist, LEFT JOIN identities, no raw JSON projection, stable timestamp/UUID ordering,
50 rows/page, bounded validated filters and no-store on success/error responses. Existing
Tabler table, links, pagination and safe outage patterns supply desktop/mobile/no-JS UI.
Empty history is explicit. Local, Entra and unknown failures must all remain visible.

## Ownership and dependency order

1. IAM-A owns SQL writer, canonical schema/new migration, permissions, version pins and
   every authentication consumer, plus fixed Python writer boundary and outcome tests.
   It starts after PG18 correction0021/v24 freezes; reserve0022/v25 for IAM-A only then.
2. IAM-B owns separate read projection, route/template/registration and user-page links,
   consuming frozen IAM-A event contract without editing the writer module.
3. Independent security/browser reviewer owns acceptance and different-author fixes.

Required proof: fresh and upgraded SQL grants, malformed enum/actor/version rejection,
local and Entra outcomes, exact-once retries, no unverified actor, all role/CSRF/rate/outage
paths, logout despite audit outage and real old-cookie rejection, absence of secret
sentinels from rows/UI/diagnostics, pagination/unknown identities/no-store and actual
desktop/mobile screenshots. Root reruns combined gates. External tenant behavior remains
a separate live acceptance; mocked claims are not a tenant proof.

## Independent design review resolution

WP wp-0d9b941ae3a9 preserved the original AGY HIGH claim and tool failures. Its claimed
lockout bypass is disproved by auth/service.py189–216 before reset222–230; Root and an
independent collector read those lines. No issuer-boundary weakening accepted. The concrete
logout-response, stale-actor and UUID replay contracts above incorporate the valid review
clarifications. Required tests include audit outage after valid credentials, locked account
with valid password, conflicting UUID tuple and old-cookie replay after logout audit outage.
