# Fable Cross-Vendor-Review: WP-O Schema v16 Prüfbelege (2026-09-05)

Ziel: Worktree `review-context-audit-0905`, Basis `abee1b0`, Commit `1db4275`
(«feat(workflow): bind explicit reviews to immutable revision receipts», 28 Dateien); Befunde gegen
den Dateistand dieses Commits verifiziert. Statisches Read-only-Review; keine DB, kein Browser, keine Probes.
Vertrauensmodell: `cafeteria_app` ist die vertrauenswürdige Anwendung, kein kompromittierter Client.

## Verdict

**Ein Blocker (H1), sonst freigabefähig.** Kernlogik (Item-Beleg an `row_version` + Komponenten-Token,
Wochenkontext-Beleg an Titel/Hinweis/`header_revision`/Service-Versionen, Publish prüft beide,
unveränderliche `audit_events`, Migration ohne fabrizierte Belege, alte Publikation bleibt) ist
korrekt und getestet. H1 betrifft nur die Auslieferung des neuen Bildschirms.

## Findings

| Nr | Schwere | Ort | Auslöser | Minimale Korrektur |
|---|---|---|---|---|
| H1 | HOCH | `templates/admin/week_review.html:1` `{% extends "admin/base_tabler.html" %}` | Datei existiert in diesem Worktree nicht (`ls templates/admin/`: kein `base_tabler.html`, kein `_macros.html`). Realer GET `/admin/<family>/wochen/pruefung?week=…` → `TemplateNotFound` → 500. Route-Tests verdecken das: Fixture patcht `render_template` (`test_week_review_routes.py:60-64`), Render-Test stubbt die Basis per `DictLoader` (`:118-121`). Nach Migration ist Publish ohne diesen Bildschirm dauerhaft blockiert («Wochenkopf und Servicehinweise müssen erneut geprüft werden»). | Bis zur UI-Tranche `{% extends "base.html" %}` mit `body_class admin-body`, `admin-shell` + `{% include 'admin/_workflow_sidebar.html' %}` wie `week_management.html` in `abee1b0`; Block `main_attributes` entfernen. Zusätzlich ein Test mit echtem `FileSystemLoader` ohne DictLoader-Stub, der `admin/week_review.html` rendert. |
| M1 | MITTEL | `templates/admin/cafeteria.html`, `patienten.html`, `rendering.py` | Kein Link zur neuen Wochenprüfung (`grep pruefung` nur in `week_review.html` selbst). Status `review_open` bei offenem Wochenkontext ist für Anwender nicht auflösbar. | In der Wochenleiste einen Link `url_for('admin.week_review_get', family=family, week=week)` neben «Vorschau» ergänzen; Text «Wochenkopf prüfen». |
| M2 | MITTEL | `workflow_review.py:164-180` `_review_open_connection`, `workflow_routes.py:411-431` | Pro Menükarte ein zusätzlicher `audit_events`-Lookup plus Token-Neuberechnung; Index `ix_workflow_review_receipts` deckt `(entity_public_id, action, id DESC)`, die Abfrage filtert aber zusätzlich `details->>'reviewed_item_row_version'`, Join über `menu_items.public_id`. 10 Karten × 2 Profile pro Overview sind tragbar; kein Blocker. | Kein Handlungsbedarf jetzt; bei Bedarf `reviewed_item_row_version` als Index-Spalte ergänzen. |
| L1 | NIEDRIG | `record_menu_review` (0013:106-115) | Prüft `reviewed_token` nur syntaktisch; der semantische Wert stammt aus Python (`workflow_review.py:359`). Innerhalb des App-Vertrauensmodells akzeptabel, da `_review_open_connection` beim Publish denselben Python-Token neu berechnet und vergleicht. | Dokumentieren in `database/README.md`, dass der Token-Inhalt anwendungsseitig gebunden ist. |
| L2 | NIEDRIG | `week_review.html:47` | `occurred_at` wird als rohes `timestamptz`-repr gerendert. | `|date_long`-ähnlichen Filter oder `strftime` in der Route. |
| L3 | NIEDRIG | `0013_v15_to_v16.sql:186-192` | `bump_week_header_revision()` wird von `cafeteria_app` entzogen; Trigger feuern in PostgreSQL ohne EXECUTE-Prüfung zur Laufzeit, Header-Save unter App-Rolle funktioniert (Konzept wie bestehende `set_updated_at`). Hinweis nur, damit niemand «reparierend» ein GRANT ergänzt. | Keine. |

## Geprüfte Zusicherungen (mit Evidenz)

- **Beleg an gespeicherte Item-Revision:** `record_menu_review` verlangt `row_version = source+1`,
  `allergen_review_status='checked'`, keine Komponenten-Drift (0013:106-115); `_review_open_connection`
  akzeptiert nur einen Beleg mit `reviewed_item_row_version = i.row_version` und gleichem Token.
  Unscoped Payload (`workflow_review.py:202`) nutzt dieselben fünf Spalten wie der scoped Pfad; Token-Parität gegeben.
- **Wochenkontext unabhängig geprüft, auch komplett geschlossen:** `workflow_week_context` enthält
  Titel, Wochenhinweis, `header_revision`, alle Services mit `row_version`, Status und Hinweis;
  `derive_admin_status` liefert bei vorhandenen Services ohne Items nicht mehr `empty` (`workflow.py:472-475`);
  `test_fully_closed_week_requires_context_review_and_retains_old_publication`.
- **Revert erzwingt neue Prüfung:** Trigger erhöht `header_revision` bei jeder Textänderung; Rückkehr
  zum alten Text ändert den Kontext erneut (`test_header_and_service_edits_including_revert_reject_stale_context`).
- **Fremder Menüedit entwertet nichts:** Kontext enthält keine Item-Daten und keine Wochen-`row_version`
  (`test_independent_item_and_context_receipts_do_not_invalidate_other_menus`).
- **Publish-Reihenfolge und Sperren:** `publish_draft_scoped` sperrt aktiven Standort → Woche
  (`lock_week=True`) → Services `FOR UPDATE` (`_lock_publish_review_state`, `workflow.py:366-380`),
  prüft danach Item- und Kontext-Belege (`:539-542`). Review-Pfad sperrt in derselben Reihenfolge
  (`workflow_review_context.py:79-86`); Header-Save sperrt nur die Woche (`workflow_partial_store.py:222`).
  Kein Zyklus; `test_week_review_and_header_save_hold_real_week_lock_in_both_orders`.
- **Unveränderliche Belege:** `trg_audit_no_update` (schema.sql:2121-2123), `occurred_at` per
  `clock_timestamp()`, `actor_user_id` FK auf `users`; `cafeteria_app` hat nur SELECT auf `audit_events`
  (permissions.sql:70-73), Einträge nur via SECURITY-DEFINER-Funktionen.
- **Least privilege:** Alle fünf Funktionen `REVOKE ... FROM PUBLIC, cafeteria_app, cafeteria_backup,
  cafeteria_auth_issuer`; EXECUTE nur für drei an `cafeteria_app`; `require_workflow_review_actor`
  nicht direkt aufrufbar; `search_path` fixiert. `permissions.sql:141-145` spiegelt die Grants.
- **Keine neuen Rollen:** Rollenprüfung in `require_workflow_review_actor` nutzt bestehende
  `Cafeteria.Editor|Publisher|Admin` aus `application_roles` (schema.sql:47-51) und `user_role_cache`,
  das für Entra (`sync_entra_user`, :1171) und lokale Nutzer (`provision_local_user`, :1293) gefüllt wird.
  Deckt sich mit `draft.write` in `roles.py:10-17`. Deaktivierte Nutzer werden abgewiesen.
- **Migration v15→v16:** nur `ADD COLUMN IF NOT EXISTS header_revision DEFAULT 1`, Funktionen, Trigger,
  zwei Indizes; keine Datenmutation, keine Belege (`test_v15_upgrade_preserves_checked_work_and_publication_without_fabricating_receipts`
  prüft Items, Wochen ohne `header_revision`, Revisionen, `active_publications` byteidentisch und
  `count(workflow.%)=0`). Checksum in `validate_schema.py` stimmt mit `sha256sum` der Datei überein.
- **Alte Publikation bleibt:** Publish-Pfad unverändert bis auf zwei zusätzliche Vorbedingungen;
  `withdraw_replaced_publication` erst nach erfolgreichem Snapshot-Build.
- **Routen:** GET `draft.read`, POST `draft.write`; scoped CSRF-Zweck `week-review`; `_exact` auf
  `{_csrf, week, context_version}`; Query-Parameter bei POST abgelehnt; `Cache-Control: no-store`;
  Token-Format vor DB-Zugriff geprüft (`test_malformed_review_token_is_rejected_before_database_access`).
- **Öffentlich/Entwurf:** Public-Routen unverändert (`published_snapshot` only); Admin-Vorschau zeigt
  weiter den letzten gespeicherten Stand; keine neue Sichtbarkeit von Entwürfen.
- **Replay:** `uq_workflow_review_submission` auf `(action, entity_public_id, submitted_token)` plus
  Python-Vorprüfung «bereits geprüft».

## Coverage-Grenzen (nicht geprüft, kein Befund)

- Kein Test rendert `week_review.html` mit dem echten Template-Loader (siehe H1).
- Kein Test für Service-Save gleichzeitig mit Wochenprüfung (nur Header-Save in beiden Reihenfolgen);
  Sperrreihenfolge ist aus dem Code konsistent.
- `require_workflow_review_actor` sperrt `users`/`user_role_cache` `FOR SHARE` nach Wochen-/Service-Sperren;
  gegen `sync_entra_user` (Issuer-Rolle, sperrt Nutzerzeilen) ist kein Deadlock-Test vorhanden.
- Kein Live-Test der Deploy-Sequenz «alte App stoppen → Migration → v16 starten»; README beschreibt sie korrekt,
  v15-Binary ist nach Migration kein sicherer Rollback (Belege würden ignoriert).
- Keine Prüfung der Signage-/PDF-Pfade; sie lesen weiterhin nur `active_publications`.

## Nachtrag Integration (read-only geprüft an `fc30d79`, `94a3abe`)

H1 und M1 waren Abhängigkeitsbefunde des isolierten Backend-Branchs, keine Fehler in `1db4275` selbst.
In der Root-Integration sind beide statisch aufgelöst:

- **H1 aufgelöst:** `fc30d79` liefert `templates/admin/base_tabler.html` (33 Zeilen) mit genau den
  Blöcken, die `week_review.html` nutzt (`title`, `main_attributes`, `page_header`, `content`) sowie
  `page_styles`/`page_scripts`; Assets `tokens.css`, `vendor/tabler/tabler.min.css`, `admin-tabler.css`,
  `menu-images.css`, `vendor/tabler/tabler.min.js`, `admin.js` existieren an `94a3abe` (`git ls-tree`).
  `_macros.html` enthält `icon`, `field`, `profile_tabs`, `flash_region` (`:3`, `:7`, `:45`, `:55`).
  `week_review.html` und `week_review_routes.py` sind zwischen `1db4275` und `94a3abe` diffgleich;
  `profile` wird von der Route an die Basis (`data-profile`) übergeben. Keine Legacy-Umstellung nötig.
- **M1 aufgelöst:** `94a3abe` migriert `cafeteria.html` und `patienten.html` auf `base_tabler.html` und
  verlinkt im Seitenkopf `/admin/<family>/wochen/pruefung?week=<week>` («Wochenangaben prüfen»);
  `test_week_review_link_points_to_saved_week` (`test_admin_week_tabler_browser.py:92-98`) prüft den Link.

**Explizit noch offen (Browser-Evidenz):** Kein Test in `94a3abe` rendert `week_review.html` mit echtem
Flask-Loader und echter DB oder führt eine reale Wochenprüfung durch den Browser aus; die Route-Tests
stubben weiterhin `render_template` bzw. die Basis. Die angekündigte native QA (12 Fälle, 360/768/1024/1280,
beide Familien, echte Prüfung) schliesst diese Lücke erst, wenn ihr Lauf mit Ausgabe vorliegt. Bis dahin
gilt H1 als statisch aufgelöst, nicht als dynamisch nachgewiesen. Root-DB-Gate 34 PASS deckt Backend, nicht
das Rendering.

## Empfehlung an Root

Statisch freigabefähig auf Integrationsstand `94a3abe`. Migration im kontrollierten Fenster erst nach
vorliegender Browser-Evidenz für die Wochenprüfung (echter Loader, echte DB, beide Familien, mindestens
360 und 1280).
