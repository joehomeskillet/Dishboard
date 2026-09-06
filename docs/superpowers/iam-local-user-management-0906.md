# IAM-001 — lokale Benutzerverwaltung: SDD und Umsetzungspakete

> **Für ausführende Agents:** Paketweise mit `superpowers:executing-plans` umsetzen; der Orchestrator vergibt disjunkte Worktrees und integriert nach unabhängigem Review. Dieses Dokument autorisiert keine Implementierung oder Produktionsaktion.

**Ziel:** Lokale Konten auflisten, anlegen, Rollen und Passwort ändern, deaktivieren und reaktivieren; den letzten lokalen Admin erhalten und jede erfolgreiche Änderung samt Sessionwiderruf atomar protokollieren.

**Architektur:** Die normale App liest begrenzte Kontoansichten. Nur der getrennte Auth-Issuer führt typisierte, versionsgebundene SQL-Mutationen aus. Web und CLI verwenden denselben DB-Schutz; die Oberfläche folgt erst nach dessen Prüfung.

**Technik:** Bestehende Flask-/Jinja-/Tabler-, SQLAlchemy-, PostgreSQL- und Werkzeug-Bausteine. Keine neue Dependency, kein neuer Identity-Provider, kein Sessionstore.

**Stand:** 06.09.2026, Basis `cc6c8ce`, WP `wp-f643527727bb`. Ausschliesslich Entwurf; keine IAM-Tests, Datenbankverbindung oder Produktionsprüfung ausgeführt. Schema **19 ist ein reservierter Vorschlag**; in diesem Paket entsteht keine Migration/SQL-Datei.

**Grundlagen:** [IAM-001 im Backlog](../BACKLOG.md), [Benutzer und Zugriff, Abschnitt 8](../design/2026-09-05-screens-vorlagen-verwaltung.md), Read-only-Bericht `/nvmetank1/projects/rag-stack/.claude/reports/wp-10b114fef120.md`. Historische Deployaussagen dieser Quellen sind kein aktueller Betriebsnachweis.

## 1. Umfang und verbindliche Grenzen

- Bestehende Rollen bleiben `Cafeteria.Editor`, `Cafeteria.Publisher`, `Cafeteria.Admin`. Alle Kontoseiten und ihr Protokoll verlangen `users.manage`, das ausschliesslich Admins besitzen. `audit.read` reicht nicht: Publisher besitzen diese Fähigkeit bereits.
- Verwaltet werden nur `auth_provider='local'` und Rollenquelle `local`. Entra-, Demo- und Systemkonten sind keine Mutationsziele. Ein aktuell berechtigter Entra-Admin darf lokale Konten verwalten; E-Mail-Identitäten werden niemals zusammengeführt.
- IAM-002, Secrets, Entra-Konfiguration, Provideraktivierung, Kontolöschung und frei definierbare Rollen sind ausgeschlossen. Anzeigename und Benutzername sind nach dem Anlegen nur lesbar; damit braucht diese Welle keine zusätzliche Profil-Editierversion.
- Alle GETs bleiben lesend. Bestehende Passwörter bleiben erhalten, solange nicht ausdrücklich die Passwortaktion bestätigt wird. Keine E-Mail-/Token-Resetstrecke und kein impliziter Passwortwechsel bei Rollen oder Status.
- Passwortregeln aus `auth/issuer.py::validate_local_password` bleiben verbindlich: 14–1024 Zeichen sowie bestehende Klassen-/Schwäche-/Benutzernamenprüfung. Passwörter und Hashes erscheinen nie in URL, Formularwiederanzeige, Flash, Audit, Logs oder Reports.
- Normale App und Auth-Issuer erhalten keine zusätzlichen direkten Identity-Schreibrechte; der Issuer weiterhin keine Tabellen-/Sequenzrechte. Fehlender Issuer sperrt Mutationen mit 503, ohne Fallback auf App-/Owner-Verbindung.

## 2. Bestandsvertrag und notwendige Änderungen

Pythonpfade mit `cafeteria/` sowie `manage.py` liegen unter `reference_scaffold/`. Die kürzeren Pythonangaben `auth/`, `admin/` und `roles.py` beziehen sich auf `reference_scaffold/cafeteria/`; Templateangaben auf `reference_scaffold/cafeteria/templates/`.

| Bestehender Ort | Beleg und Umsetzungskonsequenz |
|---|---|
| `database/schema.sql:20–81` | `users.public_id`, `authz_version`, `disabled_at`; `user_role_cache`; `local_credentials`. `updated_at` ändert sich auch bei Login und ist kein Bearbeitungstoken. |
| `database/schema.sql::resolve_auth_actor` | Bisher Namensauflösung auf genau einen aktiven Admin, ohne erwartete Version oder Actor-Zeilenlock. Nur CLI-Vorabkontext darf Namen verwenden; Web bindet an die aktuelle Session-ID. |
| `database/schema.sql::{provision_local_user,set_local_password,disable_local_user}` | Audit und Mutation bereits gemeinsam, aber noch kein globaler Last-admin-Guard oder Actor-/Target-Versionsvertrag. Bestehende unversionierte Zugänge dürfen keine Umgehung bleiben. |
| `database/schema.sql::{validate_user_auth_provider,bump_user_authz_version}` | Status-/Rollenänderungen erhöhen bereits die Version; Passwortwechsel explizit. Mehrere Rollenänderungen dürfen mehrere Inkremente bewirken. Vertrag ist strikt grösser, nicht genau `+1`. |
| `auth/service.py::authenticate_local_user` | Heute `FOR UPDATE OF c,u`. Vor neuen Mehrkonto-Mutationen in zwei explizite Schritte umstellen: Benutzer, dann Credentials; unter den Locks erneut Passwort/Status prüfen. |
| `database/schema.sql::sync_entra_user` | Upsert sperrt Benutzer vor Rollenänderungen. Diese Reihenfolge erhalten: Sie serialisiert den Entzug einer Entra-Actorrolle gegen die neue Actor-Prüfung. Keine Entra-Konfiguration ändern. |
| `roles.py::require_capability`, `auth/routes.py::_establish_session` | Session enthält Benutzer-ID und AuthZ-Version; jeder geschützte Request lädt aktuelle DB-Autorisierung. Versionsabweichung leert die Session. |
| `auth/issuer.py`, `manage.py` | Drei reguläre CLI-Mutatoren öffnen eigene Issuer-Transaktionen. Sie werden auf denselben neuen Vertrag verdrahtet; keine CLI-Subprozesse aus HTTP. |
| `database/permissions.sql`, `cafeteria/db.py` | Derzeit exakt fünf erlaubte Issuer-Funktionen. Migration, Grants, erwartete Signaturen und Readinesszählung müssen zusammen wechseln. |
| `database/schema.sql::bootstrap_first_local_admin` | Owner-exklusiver Erststart, gemeinsamer vorhandener Advisory-Key `2903847293::bigint`; bereits irgendein aktiver Admin, auch Entra, verhindert Bootstrap. Kein allgemeiner Recovery-Endpunkt. |

GitNexus-Abfrage und Context für `authenticate_local_user`/`disable_local_user` bestätigen die Caller `auth/routes.py::local_login` bzw. `manage.py::main`. Der Graph ersetzt keine SQL-Lockanalyse. In dieser SDD werden keine bestehenden Symbole geändert; die Implementierung muss vor jedem Symboledit Impact erneut auswerten.

## 3. Entscheidung: Was der Adminschutz garantiert

Ein **dauerhaft nutzbarer lokaler Admin** ist ein lokaler, nicht administrativ deaktivierter Benutzer mit vorhandenen gültigen Credentials und aktiver `Cafeteria.Admin`-Rolle aus Quelle `local`. Temporäre Login-Sperren entfernen ihn nicht aus dieser dauerhaften Menge.

Jede Aktion, die ein solches Konto deaktiviert oder ihm die Adminrolle entzieht, muss nach ihrer simulierten Wirkung mindestens einen anderen dauerhaft nutzbaren lokalen Admin übriglassen. Zusätzlich muss mindestens einer der verbleibenden Admins bei der gesperrten DB-Prüfung `locked_until IS NULL OR locked_until <= clock_timestamp()` erfüllen. Ein Entra-Admin ersetzt diesen lokalen Rückweg nicht.

Die temporäre Zusatzprüfung verhindert, dass eine bewusste Kontoaktion nur gerade gesperrte lokale Admins übriglässt. Sie schaltet den Schutz gegen Login-Fehlversuche nicht ab: Ein Konto kann nach dem Commit später temporär gesperrt werden. Die Existenz eines Hashes beweist weder Kenntnis des Passworts noch einen erreichbaren/configurierten Login-Provider. Diese ehrlichen Grenzen erscheinen im Betriebsnachweis; IAM-002 muss Provideränderungen gesondert absichern.

Eigene Rollen-/Statusänderung ist erlaubt, wenn diese Bedingungen erfüllt sind. Erfolgreiche Selbständerung leert nach dem Commit die aktuelle Session und führt zur Anmeldung. Passwortreset des einzigen Admins bleibt mit expliziter Passwortbestätigung erlaubt, da ein gültiges neues Passwort gesetzt wird. Reset eines deaktivierten Kontos reaktiviert es nicht; Reaktivierung setzt weder Passwort noch temporäre Sperre zurück.

## 4. Atomare Konkurrenz- und Sperrentscheidung

Alle fünf lokalen Mutatoren und der bestehende Bootstrap verwenden denselben transaktionsgebundenen Advisory-Lock `2903847293::bigint`. Es ist der vorhandene Bootstrap-Key, kein zweiter unabhängiger Lock. Nur die wenigen administrativen Kontoaktionen werden global serialisiert; normale Logins benötigen diesen Lock nicht.

Jeder Mutator erzwingt `READ COMMITTED` und lehnt andere Isolationsebenen kontrolliert ab. Grund: Nach dem Warten auf den globalen Lock muss die nächste Abfrage den zuletzt bestätigten Adminbestand sehen; ein alter Repeatable-read-Snapshot würde die Mengenprüfung entwerten. Der Issuer öffnet dafür genau eine Transaktion; keine Unterfunktion committed selbst.

Die vollständige Reihenfolge lautet:

1. Form-/CLI-Input prüfen. Beim Reset den tatsächlichen lokalen Zielbenutzernamen über den engen Issuer-Kontext aus §5 per UUID lesen und dessen Actor-/Zielversion gegen die ursprünglichen Erwartungen prüfen. Danach `validate_local_password(password, tatsächlicher_username)` aufrufen und das bestätigte Passwort **vor** Beginn der DB-Sperren mit der vorhandenen Werkzeug-Funktion hashen. Create validiert den geprüften neuen Namen. Keine Benutzerinteraktion unter DB-Lock; die lesende Kontextabfrage ersetzt keine finale Prüfung.
2. Issuer-Transaktion starten, Isolation prüfen, globalen Advisory-Lock erwerben. Endliche lokale Wartezeit setzen (`lock_timeout=5s`, `statement_timeout=15s`); keine automatische Wiederholung einer Mutation nach Timeout oder unklarer Commitantwort.
3. Aktive Rollendefinitionen in stabiler `role_code`-Reihenfolge `FOR SHARE` sperren. IDs von Actor, Ziel und allen dauerhaft nutzbaren lokalen Admin-Kandidaten bestimmen; Menge deduplizieren.
4. Alle betroffenen `users`-Zeilen mit explizitem `ORDER BY id FOR UPDATE` sperren; anschliessend ihre vorhandenen `local_credentials` mit `ORDER BY user_id FOR UPDATE`. Actor gleich Target wird genau einmal gesperrt. Konto/Provider nach Locks erneut prüfen.
5. Actor muss nicht deaktiviert sein, eine aktive Adminrolle besitzen und exakt `expected_actor_authz_version` haben. Danach Ziel-UUID, lokaler Provider und exakt `expected_target_authz_version` prüfen. Rolle und Zielzustand stammen aus der Datenbank, niemals aus Formularrollen.
6. Rollen-/Statuswirkung berechnen und §3 prüfen. Erst dann genau die angeforderte Änderung ausführen, `last_seen_roles` bei Rollenänderung konsistent halten, vorhandene Versionstrigger erhalten und Passwortversion explizit erhöhen.
7. Unveränderliches Ereignis mit Actor, Ziel, altem/neuem Zustand und endgültiger Zielversion schreiben. Mutation, Version und Audit committen gemeinsam; jeder Fehler rollt alles zurück. Erst nach bestätigtem Commit Erfolg melden.

Login muss Benutzer vor Credentials sperren und darf nach einem Credential-Lock keinen früheren Benutzerlock nachfordern. Entra-Sync bleibt Benutzer vor Rollen; die Rollen-Trigger erhöhen die bereits gesperrte Benutzerzeile. Die normale App darf Loginmetadaten ändern, jedoch keine Adminmitgliedschaft oder Rollendefinition. Datenbank-Owner-Eingriffe sind privilegierte Wartung ausserhalb dieser Web-/CLI-Garantie; keine Behauptung eines Schutzes gegen deaktivierte Trigger/Superuser.

Zwei parallele Entziehungen können daher nicht beide dieselbe alte Zweiermenge zählen: Der zweite Mutator wartet und liest danach den bestätigten Bestand; er verliert je nach Actor-/Zielzustand mit 401/403 oder 409. Parallele Entra-Actor-Revokation wird am Benutzerlock geordnet. Loginstatus wird vor dem Last-admin-Entscheid unter Credential-Locks stabilisiert. Die Integration prüft diese Ordnungen mit echten konkurrierenden Verbindungen, nicht mit Sleeps als Synchronisationsbeweis.

## 5. Kleiner gemeinsamer API-/DTO-Vertrag

Neue Datei `cafeteria/auth/local_users.py` besitzt typisierte DTOs, sichere Leseprojektionen und die fünf Python-Einstiege. Bestehende Policy-/Hashvalidierung bleibt in `auth/issuer.py`; keine zweite Passwortpolicy.

```text
ActorExpectation(user_id: int, authz_version: int)
TargetExpectation(public_id: UUID, authz_version: int)
LocalUserContext(actor: ActorExpectation, target: TargetExpectation | None,
                 target_username: str | None)
LocalUser(public_id: UUID, username: str, display_name: str,
          roles: tuple[str, ...], disabled_at: datetime | None,
          locked_until: datetime | None, last_login_at: datetime | None,
          password_changed_at: datetime, authz_version: int)
MutationResult(public_id: UUID, authz_version: int, changed: bool)
AuditEntry(public_id: UUID, occurred_at: datetime, action: str,
           actor_display_name: str | None, target_public_id: UUID | None,
           target_display_name: str, summary: str)

list_local_users(app_engine, *, page: int, status: str) -> tuple[LocalUser, ...]
get_local_user(app_engine, *, public_id: UUID) -> LocalUser | None
list_local_user_events(app_engine, *, page: int,
                       target_public_id: UUID | None) -> tuple[AuditEntry, ...]
load_local_command_context(issuer_engine, *, actor_identifier: str,
                           target_username: str | None = None) -> LocalUserContext
load_local_target_context(issuer_engine, *, actor: ActorExpectation,
                          target: TargetExpectation) -> LocalUserContext
create_local_user(issuer_engine, *, actor: ActorExpectation, username: str,
                  display_name: str, password: str, roles: tuple[str, ...]) -> MutationResult
replace_local_roles(issuer_engine, *, actor: ActorExpectation,
                    target: TargetExpectation, roles: tuple[str, ...]) -> MutationResult
reset_local_password(issuer_engine, *, actor: ActorExpectation,
                     target: TargetExpectation, password: str) -> MutationResult
deactivate_local_user(issuer_engine, *, actor: ActorExpectation,
                      target: TargetExpectation) -> MutationResult
reactivate_local_user(issuer_engine, *, actor: ActorExpectation,
                      target: TargetExpectation) -> MutationResult
```

`page` beginnt bei 1, feste Seitengrösse 50; Status ist genau `all|active|disabled`. Listen sortieren stabil nach Benutzername/Public-ID, Audit nach Zeitpunkt/Public-ID absteigend. Eingaben sind begrenzt; keine frei übergebenen SQL-Sortierausdrücke. Leseprojektionen enthalten niemals `password_hash`. Neue Einträge sind vollständig, Detail-404 verrät keinen fremden Provider. Der Anzeigename wird beim Anlegen getrimmt und auf 1–120 Zeichen begrenzt; Username behält die vorhandene 3–64-Zeichen-Regel.

Die neuen SQL-Einstiege sind `create_local_user_v19`, `replace_local_roles_v19`, `reset_local_password_v19`, `deactivate_local_user_v19`, `reactivate_local_user_v19`. Jeder nimmt Actor-ID und erwartete Actor-Version; alle ausser Create zusätzlich Ziel-UUID und erwartete Zielversion. Create nimmt Benutzername, Anzeigename, Hash und Rollenarray; Roles ein Rollenarray, Password einen Hash. Alle geben nur UUID, endgültige Version und `changed` zurück. SQL prüft Pflichtfelder, Typ-/Wertebereiche und Hashformat zusätzlich zur Pythonpolicy; kein generisches JSON-Mutationsgateway.

Gleiche Rollenliste bzw. bereits gewünschter Status ist bei passenden Versionen ein No-op ohne Versionssprung/Auditduplikat. Eine veraltete Version bleibt auch dann ein Konflikt. Doppelte Create-Namen führen kontrolliert zu 409. Passwortreset ist immer eine explizite Änderung. Fehlercodes werden anhand fester SQLSTATE-/Constraint-Identifikatoren zu `InvalidInput`, `ActorDenied`, `StaleActor`, `UnknownTarget`, `StaleTarget`, `LastLocalAdmin`, `DuplicateUsername` oder `IssuerUnavailable` abgebildet; keine DB-Fehlermeldung ungefiltert rendern.

### Enger Identitätskontext für CLI und UUID-Passwortreset

Genau eine neue lesende SQL-Funktion bedient beide eng getrennten Auflösungen:

```text
local_user_command_context_v19(
  actor_id bigint DEFAULT NULL, actor_identifier text DEFAULT NULL,
  target_public_id uuid DEFAULT NULL, target_username text DEFAULT NULL
) RETURNS TABLE(actor_user_id bigint, actor_authz_version bigint,
                resolved_target_public_id uuid, target_authz_version bigint,
                resolved_target_username text)
```

Die SQL-Typen der Versionsfelder entsprechen `users.authz_version` (`bigint`); Eingabe- und Rückgabespalten haben unterschiedliche Namen.

Namensmodus: `actor_identifier` ist gesetzt, `actor_id` und `target_public_id` sind NULL; `target_username` ist entweder ein gültiger lokaler Username oder für Create NULL. ID-/UUID-Modus: `actor_id` und `target_public_id` sind gesetzt, beide Namensparameter sind NULL. Gemischte, mehrdeutige, leere oder sonst unvollständige Selektoren ergeben `InvalidInput`, keine automatische Fallbackauflösung. Der Actor muss aktuell eindeutig, aktiv und administrativ berechtigt sein; dies wird vor Ausgabe einer Zielidentität geprüft. Das Ziel muss lokal sein, darf für Status-/Resetaktionen aber deaktiviert sein. Unbekannte/nichtlokale Ziele ergeben `UnknownTarget`; kein fremder Provider wird offengelegt. Ohne Ziel im Create-Kontext sind alle drei Zielfelder NULL, sonst alle gesetzt. Username stammt exakt aus `local_credentials.username` des per `users.public_id` gebundenen Kontos, niemals aus der Formularanzeige oder bloss aus dem Namensparameter.

Die Funktion verwendet den bestehenden begrenzten SECURITY-DEFINER-/festen-Suchpfad-Vertrag, bleibt nur für den Issuer ausführbar und enthält ausschliesslich explizite Leseprojektionen. Keine Tabellenrechte, Hashes, Passwörter, Loginmetadatenänderung oder Auditwrites; keine administrativen Advisory-/Zeilenlocks während Kontextlesen oder Passwortbestätigung. Sie liefert den unveränderlichen `LocalUserContext` über beide Python-Wrapper. Nur `load_local_command_context` darf einmalig Erwartungen für einen neuen CLI-Auftrag binden. `load_local_target_context` verwendet ausschliesslich die übergebenen Actor-ID/Ziel-UUID, vergleicht die gelesenen Versionen mit den übergebenen Erwartungen und meldet bei Abweichung `StaleActor`/`StaleTarget`; es ersetzt niemals deren Werte.

`reset_local_password` ruft diesen UUID-Wrapper vor Policy und Hash selbst auf, für Web und CLI identisch. Es verwendet den echten Zielusername für die bestehende `validate_local_password` und übergibt anschliessend **die ursprünglich erhaltenen** Actor-/Target-Erwartungen an `reset_local_password_v19`. Zwischenzeitliche Änderungen nach der Kontextabfrage werden daher unter den finalen SQL-Locks erneut abgewiesen. Username ist in dieser Welle unveränderlich; eine spätere Username-Editierfunktion müsste zusätzlich diesen Identitätsvertrag versionsgebunden erweitern. Kein Username-Formfeld als Policyquelle und keine duplizierte Passwortpolicy.

### CLI ohne alten Umgehungspfad

Bestehende Befehlsnamen und interaktive Passwortbestätigung bleiben. Hinzu kommen `set-local-roles` und `reactivate-local-user`. `load_local_command_context` nutzt ausschliesslich den Namensmodus; der gemeinsame Reset nutzt anschliessend ausschliesslich ID-/UUID-Modus.

Die CLI liest diesen Kontext vor der Bestätigung, zeigt Ziel, Aktion und Rollen/Status ohne Geheimnisse, bestätigt, und reicht genau diese Versionen an denselben Mutator weiter. Ändert sich etwas dazwischen, bricht sie ab; kein stilles erneutes Lesen und Überschreiben. `--actor` bleibt eine vom privilegierten Operator gewählte, DB-geprüfte Auditzuordnung, keine behauptete HTTP-Authentifizierung. Web entnimmt Actor-ID und erwartete Version ausschliesslich `g.auth_user` nach dem Capability-Decorator, nie einem Formfeld.

Die drei alten unversionierten SQL-Signaturen verlieren `EXECUTE` für den Issuer und bleiben fail-closed; alle regulären CLI-Wrapper werden in derselben Releaseeinheit umgestellt. Kein Legacy-Wrapper darf sich erwartete Versionen erst im Schreibaufruf selbst beschaffen. Die konkrete neue Issuer-Allowlist umfasst **acht** Einträge: zwei unveränderte Entra-/Publicationfunktionen, fünf v19-Mutatoren und exakt `local_user_command_context_v19(bigint,text,uuid,text)`. Keine zusätzliche Zweiparameter-Überladung für den früheren Entwurf; Grants, Schema-/Readiness-Signaturen und Zählung prüfen denselben Vierparametervertrag. Interne Lock-/Audithelfer und Bootstrap bleiben ausgeschlossen.

## 6. Audit und Sessionwiderruf

`audit_events` wird weiterverwendet. Normale Rollen erhalten weder UPDATE/DELETE/TRUNCATE noch direktes INSERT; zusätzlich verweigern DB-Trigger UPDATE, DELETE und TRUNCATE auf dieser Tabelle. Nur begrenzte Definer-Funktionen/Trigger fügen Ereignisse hinzu. Das ist Append-only gegenüber Anwendungsrollen, keine kryptografische Unveränderlichkeit gegenüber dem DB-Owner.

Bestehende Ereigniscodes für Create, Rollenzuteilung, Password und Disable bleiben lesbar. Neu sind `auth.local_roles_changed` und `auth.local_user_reactivated`. Neue Kontomutationen setzen `entity_type='user'`, `entity_public_id` auf das Ziel und einen festen Detailsvertrag: interne Ziel-ID, vor/nach-Rollen oder Status soweit betroffen, vorherige/endgültige Zielversion. Keine Passwörter, Hashes, Sessionwerte, Request-Bodies oder frei eingesandten Audittexte. Namen werden für die Ansicht über bestehende Benutzer aufgelöst; Nutzer werden in IAM-001 nicht gelöscht.

Der Leser berücksichtigt ältere `details.target_user_id` und `auth.local_login_locked.details.user_id`, erlaubt nur bekannte Konto-/Sperrereignisse und rendert feste Zusammenfassungen statt Roh-JSON. Kontoliste zeigt `last_login_at` als letzten bekannten Loginzeitpunkt. Abgewiesene oder zurückgerollte Aktionen erzeugen keine fälschlich erfolgreichen DB-Ereignisse; bestehende sichere Fehlerlogs bleiben getrennt.

Sessionwiderruf besteht aus der in derselben Transaktion erhöhten `authz_version`. Bereits ausgestellte Cookies können nicht gelöscht werden, werden aber beim nächsten geschützten Request abgewiesen. Ein bereits laufender anderer Schreibrequest benötigt weiterhin seinen eigenen atomaren Actor-Vertrag; IAM-001 behauptet keinen rückwirkenden Abbruch bereits bestätigter anderer Geschäftsvorgänge. Rollen-/Passwort-/Statusaktion an sich selbst leert nach Commit zusätzlich den aktuellen Cookiezustand; Selbständerung bekommt keine Ausnahme vom Versionscheck.

**Einzige offene Produktentscheidung:** Bedeutet Backlog-«Zugriffsprotokoll» die vorhandenen Konto-/Sperrereignisse oder zusätzlich jeden erfolgreichen/fehlgeschlagenen Login und Logout? Für diese SDD heisst die Seite präzise **«Kontoereignisse»**. Eine vollständige Zugriffshistorie benötigt eine eigene Entscheidung zu Ereignisumfang und Aufbewahrungsfrist; weder Vollständigkeit noch frei erfundene Löschfristen werden zugesagt. Das blockiert die sechs lokalen Verwaltungsfunktionen nicht, bleibt aber eine ausdrücklich offene Backlog-Abnahmegrenze.

## 7. Web-Wiring und Rückweg im Produkt

| Route | Verhalten |
|---|---|
| `GET /admin/benutzer` | Lokale Kontoliste, Statusfilter, Seitennavigation, «Benutzer anlegen», «Kontoereignisse». Fehlender Issuer lässt die Liste lesbar und erklärt gesperrte Schreibaktionen. |
| `GET /admin/benutzer/neu`, `POST /admin/benutzer` | Username, Anzeigename, bestätigtes neues Passwort und bestehende Rollen; eigene Create-Aktion. |
| `GET /admin/benutzer/<uuid>` | Identität/Status und drei getrennte Formulare für Rollen, Passwort und Status. Zurück zur gefilterten Kontoliste über serverseitig validierte lokale Parameter. |
| `POST /admin/benutzer/<uuid>/rollen` | Exakte Rollenmenge, Zielversion, explizit beschriftete Bestätigung. Keine implizite Passwortänderung. |
| `POST /admin/benutzer/<uuid>/passwort` | Zwei neue Passwortfelder; gespeicherte Werte bleiben bei allen Antworten leer. |
| `POST /admin/benutzer/<uuid>/deaktivieren`, `/aktivieren` | Explizite Ziel-/Wirkungsbestätigung, Versionscheck; Status wird serverseitig abgeleitet. |
| `GET /admin/benutzer/protokoll` | Begrenzte Kontoereignisse, optional Ziel-UUID; nie als vollständige Anmeldehistorie bezeichnen. |

Alle Routen verlangen `users.manage`; alle POSTs bestehenden CSRF-Schutz und strikte Formularfeld-/Mehrfachwertprüfung. Nur die Rollenliste darf wiederholte Werte enthalten. Actorfelder aus Requests werden verworfen/abgewiesen. Formulare tragen die beim GET gelesene Zielversion. Header: `Cache-Control: no-store`, bestehende CSP und Referrer-Regeln erhalten; kein Drittanbieter-JavaScript.

Erfolg nutzt PRG 303; Selbständerung führt zur Anmeldung. 400: fehlerhafte Form/Passwortbestätigung; 404: unbekanntes/nichtlokales Ziel; 409: Zielversion, Benutzername oder letzter Admin; 401/403: veralteter/unberechtigter Actor mit bestehender Sessionbereinigung; 503: fehlender Issuer, Sperrtimeout oder DB-Ausfall. Bei 409 bleibt der neue DB-Zustand massgeblich; eine lesende Neuanzeige erklärt den Konflikt und fordert eine neue ausdrückliche Entscheidung. Kein automatisches erneutes POST.

Neue Templates `admin/users.html`, `admin/user_editor.html`, `admin/user_events.html` verwenden `base_tabler.html` und vorhandene Formularmakros. Alle Felder haben sichtbare Labels, Fehlerzuordnung und 48px-Bedienziele; keine Farbcodes als einzige Statusanzeige. Sidebar-Eintrag «Benutzer & Zugriff» in `admin/_workflow_sidebar.html` ist capability-gebunden. Branding, Screens, Vorlagen, Fachmetadaten und bestehende Publikationspfade bleiben fremde Ownership.

## 8. Migration, Rückweg und Freigabereihenfolge

Vorgeschlagen ist **`database/migrations/0016_v18_to_v19.sql`**, derzeit nur reservierter Name. Vor Implementierung muss der Orchestrator den dann aktuellen Schema-HEAD prüfen; kein zweiter Writer darf 19 parallel belegen. Es sind keine neuen Kontotabellen oder Secrets nötig. Migration aktualisiert Funktionen, Auditguards, Grants und Schemavertrag; Schema-Neuaufbau und Upgrade müssen dieselbe Funktions-/Berechtigungsmenge ergeben. Backup nimmt bestehende Konten, Credentials und Audit unverändert mit.

Die Releaseeinheit umfasst ebenso `tools/validate_package.py`: dessen explizite Schema-18-Prüfung, Pflichtdateien, Migrationsliste und Checksumvertrag müssen zusammen auf den bestätigten Schema-19-Stand wechseln. Sämtliche betroffenen Schema-/Migrations-/Paketfixtures müssen die vollständige Versionsfolge bis einschliesslich 19 prüfen, nicht nur das letzte Element. Historische Fixtures behalten ihren historischen Ausgangszustand, führen vor aktuellen `permissions.sql`-/Readiness-Prüfungen aber die komplette Migration bis 19 aus. Alte Migrationen und ihre Prüfsummen bleiben unverändert. Negative Pakettests müssen veralteten Schemastand, fehlende/manipulierte neue Migration und falsche Signaturen/Grants weiter ablehnen. Weder Assertions streichen noch auf Teilmengen reduzieren oder Fehler als Skip/OK umdeuten.

Vor Release wird rein lesend geprüft, ob mindestens ein dauerhaft nutzbarer lokaler Admin und ein tatsächlicher lokaler Anmeldeweg vorhanden sind. Ein bestehender Mangel wird gemeldet und nicht durch Migration automatisch mit Defaultkonto/Passwort repariert. Ein noch berechtigter Admin kann den regulären neuen CLI-Vertrag nutzen, um ein lokales Admin-Konto anzulegen. Bei keinem aktiven Admin gilt ausschliesslich der bestehende Owner-Bootstrap unter kontrollierter Betriebsanweisung; existiert noch ein aktiver Entra-Admin, verweigert dieser Bootstrap wie bisher. Verlust aller tatsächlichen Zugänge benötigt einen gesondert autorisierten Owner-Recovery-Eingriff, keinen versteckten Web-Ausweg.

Migration, neue Readiness-Allowlist und versionierte CLI gehören in dieselbe geprüfte Deploymenteinheit, danach wird das Web-Wiring freigegeben. Alte App/CLI auf Schema19 ist wegen der exakten alten Fünfer-Allowlist und entzogener Altaufrufe kein kompatibler Rückweg. Bei einem UI-Fehler wird auf einen geprüften **Schema19-kompatiblen Stand ohne den neuen Sidebar-/Routenentry** zurückgeschaltet; DB-Guards, Audit und gültige CLI bleiben erhalten. Nach produktiven Kontomutationen kein Restore eines alten Backups als gewöhnlicher Rollback: Es würde Sessionversionen, Passwörter und Audit zurücksetzen. Bevorzugt vorwärts korrigieren; Disaster-Recovery bleibt gesonderter Betriebsprozess mit Zugriffssperre und erneuter Sessioninvalidierung.

## 9. Kleine Umsetzungspakete mit eindeutigem Ownership

Die folgenden Bezeichnungen sind Planpakete, noch keine generierten/vergebenen WPs. Jeder Writer: fetch-first eigener Worktree, fremde Änderungen erhalten, vor Symboledits GitNexus Impact, vor Commit Detect, passende Gates und wörtlicher Report. Der Orchestrator vergibt Pools ausdrücklich; kein geteiltes Fullgate neben anderen Workern.

### IAM-A — DB-Vertrag, gemeinsame Sperren und CLI-Anschluss

**Ein Owner**, weil SQL, Grants, CLI und Paket-/Fixturevertrag nicht getrennt freigegeben werden dürfen. Besitzt `database/schema.sql`, `database/permissions.sql`, die nach Reservierungsbestätigung neue Migration, `database/validate_schema.py`, `tools/validate_package.py`, `cafeteria/db.py`, `cafeteria/auth/{issuer,service,local_users}.py`, `manage.py` und sämtliche betroffenen Schema-/Migrations-/Readiness-/Paket-/Auth-Tests und Fixtures. Dazu gehören insbesondere `test_tabler_package_verification.py`, `test_auth_database.py`, `test_workflow_review_migration_db.py`, `test_component_catalog_migration_db.py` und `test_branding_migration_db.py` unter `reference_scaffold/tests`; weitere tatsächlich betroffene Verträge gehören ebenfalls in diese Releaseeinheit. Der neue `local_users.py`-Teil enthält zunächst DTOs, die beiden Issuer-Kontextwrapper und Mutatoren; die drei App-Leseprojektionen folgen in IAM-B nach diesem Commit. Datei unter etwa 400 Zeilen halten, bei Bedarf bestehende modulare Auth-Konventionen nutzen; keine neue abstrakte Frameworkschicht.

- [ ] Vertragstests für Actor-/Target-Version, letzten Admin und alte unerlaubte SQL-Signaturen erstellen; erwartetes Versagen dokumentieren.
- [ ] Globale Sperre und Benutzer-vor-Credentials-Reihenfolge einschliesslich Login/Bootstrap herstellen; fünf typisierte SQL-Aktionen, den Vierparameter-Kontext samt beiden Wrappern, Auditguards und Least-Privilege-Readiness zusammen verdrahten. Resetpolicy mit realem Zielusername und unveränderten ursprünglichen Erwartungen für CLI/Web prüfen.
- [ ] Bestehende drei CLI-Befehle auf erwartete Versionen umstellen; Rollen/Reaktivierung ergänzen; interaktive Bestätigung vor Transaktionsbeginn, kein Passwort-CLI-Argument.
- [ ] In isoliertem PostgreSQL-Pool die konkrete Matrix unten sowie `test_auth_database.py`, `test_auth_live_hardening.py`, `test_auth_routes.py`, `test_database_role_readiness.py` und neue `test_local_user_management_db.py` ausführen. Separater Upgrade-/Neuanlagevertrag in `test_local_user_management_migration_db.py`.
- [ ] Alle betroffenen historischen Migrationsfixtures bis 19 vor aktuellen Permissions upgraden; vollständige Versionslisten, alte/neue Prüfsummen, Grants und Acht-Funktionen-Readiness prüfen. Vollständige betroffene Module einschliesslich Paketvalidator-Regressionsmodul ausführen; echtes Paketgate mit isolierter DB, keine bloss statische Ersetzung der Versionszahl.
- [ ] Nach Ruff, Mypy, Schema-/Permissionprüfung und unabhängigem Sicherheitsreview einen in sich zusammenhängenden Contract+CLI-Commit liefern. Kein Webentry, solange dieser Vertrag nicht angenommen ist.

### IAM-B — lesende Ansichten und begrenztes Kontoereignisprotokoll

Nach IAM-A, **anderer Owner möglich**. Besitzt Leseprojektionen in `cafeteria/auth/local_users.py` und neue `tests/test_local_user_management_reads.py`; keine Issuer-/SQLänderung. Liefert exakt `LocalUser`/`AuditEntry` und die drei GET-Servicefunktionen aus §5.

- [ ] Tests für Pagination, lokale Providergrenze, alte/neue Auditzielformate und vollständige Abwesenheit von Hash-/Sessionfeldern schreiben.
- [ ] Explizite SELECT-Projektionen und erlaubte Ereigniszusammenfassungen implementieren; ungültige Filter/Werte begrenzen.
- [ ] Neue Lesetests sowie bestehende AuthZ-Tests ausführen; Root prüft, dass keine Identitätsdaten über Publisher-`audit.read` freigegeben werden. Gate/Commit liefern.

### IAM-C — vollständige Tabler-Oberfläche und Routen

Nach IAM-A und IAM-B, **ein UI-Owner**. Besitzt neue `cafeteria/admin/user_routes.py`, drei Templates aus §7, `admin/__init__.py` für Registrierung, `admin/_workflow_sidebar.html`, neue `tests/test_admin_users_routes.py` und `tests/test_admin_users_browser.py`. Bestehende `roles.py` nur für die ausdrückliche `users.manage`-Dokumentation/Tests, falls die vorhandene Admin-Wildcard allein genügt, keine Produktänderung daran.

- [ ] HTTP-Tests für alle sechs Funktionen, Capability/CSRF/Mehrfachfelder, stale Actor/Target, fehlenden Issuer und fehlende fremde Providerziele erstellen.
- [ ] Routen direkt mit §5-Service verdrahten, Actor aus `g.auth_user`, erwartete Zielversion aus strikt geparstem Formular, getrennte Aktionen und PRG/Rückwege herstellen.
- [ ] Vorhandene Tabler-Rahmen/Formularmakros verwenden; Passwörter bei Fehlern leer lassen, Kontoereignisse exakt benennen.
- [ ] Echte HTTP-/CSP-Browserbilder bei 390/820/1440 und beiden Dichten erstellen: volle Liste, leerer Zustand, langes Fehlerbeispiel, Rollen-/Statusbestätigung, Konflikt, Tastaturfokus und 48px-Ziele. Browser schliesst Create → Rollen → Reset → Disable → Reactivate → Login/Sessionwiderruf auf isolierten Testdaten ab.
- [ ] Route-/Browsertests plus `test_admin_form_contracts.py`, `test_admin_blueprint_bootstrap.py`, Ruff/Mypy und Scope-Diff liefern; keine neue Dependency oder unverlangte Darstellungseinstellung.

### IAM-D — unabhängige Integration und Abnahme

**Root/Reviewer**, kein vierter gleichzeitig schreibender Owner. Wiederholt DB-/CLI-/HTTP-Konkurrenzmatrix und überprüft den vollständigen Diff anderer Autoren. Läuft erst nach A–C; Verantwortung für Gesamtgate, Migration/Backup/Readiness, Paket und spätere Betriebsabnahme. Keine UI-only-Teilfertigmeldung für IAM-001.

- [ ] Echte Konkurrenztests mit getrennten Verbindungen und Barrieres prüfen; die gesperrten Transaktionen enden ohne Deadlock und genau der erlaubten Zustandsfolge.
- [ ] Produktentscheidung zum erweiterten Zugriffsprotokoll gesondert ausweisen; keine erfundene Login-/Logout-Vollständigkeit im Releasebericht.
- [ ] Vollständiges Repositorygate auf dem integrierten Commit, sauberes Paket-/Schema-/Restoregate und unveränderte Public-/Signage-/PDF-Pfade prüfen.
- [ ] Produktion zunächst nur lesend abnehmen; produktive Kontomutationen/Passwörter benötigen einen ausdrücklich vereinbarten Testaccount und deren gesonderte Autorisierung. Keine Bestandskonten für automatisierte Smokes verändern.

## 10. Konkrete Abnahmematrix

| Fall auf isolierter DB | Erwartetes Ergebnis |
|---|---|
| Zwei aktive lokale Admins deaktivieren/demotieren gleichzeitig einander, Web↔Web und Web↔CLI | Höchstens eine entziehende Änderung; mindestens ein dauerhaft nutzbarer lokaler Admin, zweiter Actor-/Bestandskonflikt ohne Audit-Erfolg. |
| Ein Admin, zweiter nur Entra oder temporär gesperrt | Deaktivierung/Adminentzug abgewiesen; Passwordreset des lokalen Admins ausdrücklich möglich. |
| Create eines zweiten lokalen Admins parallel zur Entziehung des ersten | Global geordneter Bestand; Entziehung gelingt nur nach bestätigtem Create mit ungesperrtem verbleibendem Admin. |
| Entra-Actorrolle wird zwischen Formular-GET und SQL-Mutation entzogen | Aktuelle Rolle/Version verhindert Mutation; bei bereits gehaltenem Actor-Lock erfolgt die Entziehung erst nach dem zuvor autorisierten Commit. |
| Ziel geändert nach GET oder CLI-Kontext, inklusive gleicher gewünschter Rollen | 409/CLI-Konflikt, kein stilles Refresh/Write; kein doppeltes Audit. |
| Webreset per UUID / CLI-Reset per Name, Kandidat enthält tatsächlichen Zielusername | Gemeinsame bestehende Passwortpolicy verweigert vor Hash/Mutation; kein Passwort/Hash in Kontext, Antwort, Audit oder Log. Gültiger Kandidat funktioniert über denselben Service. |
| Kontext: gemischte/fehlende Selektoren, nichtlokales Ziel, unberechtigter Actor | Strikte Modusprüfung; keine Zielidentität an unberechtigte Actor, kein Lookup-Fallback, kein direktes Issuer-SELECT. Create-Kontext allein darf ohne Ziel sein. |
| Actor/Ziel ändern nach ursprünglichem GET/CLI-Auftrag, vor Kontext bzw. zwischen Kontext und Mutation | Vorabvergleich bzw. finaler SQL-Lockcheck verweigert; ursprüngliche Erwartungen werden nie durch gelesene aktuelle Versionen ersetzt. CLI-Bestätigung bleibt vor Hash/Mutation. |
| Actor=Target; Rollen/Reset/Disable; weitere Admins vorhanden | Ein Lock je Konto, erwartete Wirkung; alte Sessions abgewiesen und eigene Websession geleert. |
| Login parallel zu Reset/Disable und einem Mehrkonto-Mutator | Benutzer-vor-Credentials überall; kein Deadlock, kein Login mit altem Hash nach dessen geordnetem Resetcommit. |
| Nur anderer lokaler Admin wird gerade temporär gesperrt | Last-admin-Entscheid benutzt unter Locks aktuellen Sperrzustand; beide möglichen seriellen Reihenfolgen bleiben nachvollziehbar. |
| Audit-INSERT schlägt nach Kontoänderung fehl | Konto, Hash/Rollen/Status und Version vollständig zurückgerollt; keine Erfolgsmeldung. |
| App-/Issuerrolle versucht direkte Identity-/Auditwrites oder alten SQL-Mutator | Berechtigung verweigert; nur exakt acht erlaubte Issuer-Funktionen; Bootstrap/Helper gesperrt. |
| Providerfremdes Ziel, beliebige Actorfelder, CSRF-Fehler, doppelte skalare Felder | Abgewiesen ohne Zieländerung/Secrets in Antwort; Rollenlisten allein dürfen mehrfach vorkommen. |
| Fehlender Issuer, Timeout, Wiederholung nach unklarer Antwort | Leseseiten weiter möglich; Mutation meldet kontrollierten Fehler, kein Backendfallback und kein automatisches zweites Write. |
| Migration von18/Neuaufbau19/historische Fixtures bis19/Backup-Restore | Vollständige Versionsfolgen und gleiche Signaturen/Grants/Guards; aktuelle Permissions erst nach Upgrade; Konto-UUIDs/Hashes/Versionen/Audit erhalten, keine automatischen Defaultkonten. |
| Paketvalidator mit Schema18, fehlender/manipulierter Migration19 oder falscher Allowlist | Harte Ablehnung; korrektes Schema19-Paket besteht echtes DB-Paketgate. Alte Migrationsprüfsummen und vollständige neue Pflichtdatei-/Signaturprüfung bleiben erhalten. |

## 11. Status dieses Dokumentationspakets

Es wurde nur diese neue Markdown-Datei geschrieben. Codepfade und Bericht wurden lesend ausgewertet; GitNexus Query/Context und vor dem Commit Detect dienen der Scopeprüfung. DB-, Browser-, Securityscanner-, Paket-, OCR- und Produktionsgates sind für dieses Dokumentationspaket **nicht ausgeführt**; erwartete Ergebnisse in §10 sind Testanforderungen, keine bestandenen Tests. Der gesonderte WP-Report enthält tatsächliche Dokumentationschecks und Commit-ID.
