# Umsetzung der Grok-Kritik

**Stand:** 2. September 2026  
**Status:** technisch überarbeitet, nicht fachlich abgenommen

## Kernaussage

Die Kritik wurde nicht als reine Dokumentergänzung behandelt. Das Paket trennt jetzt Patienten und Cafeteria in Datenmodell, CSV, Demo-Daten, Flask-Routen, API, Signage, Website, Backend-Prototypen und Tests.

## Direkt umgesetzt

| Kritikpunkt | Neue Artefakte |
|---|---|
| Patienten Mo–So, Mittag und Abend | `offer_profiles`, `menu_services`, Patienten-Snapshot, Patienten-CSV, Web-/Mobile-/Signage-Ansichten |
| Zwei Menüarten auf allen Screens | `MENU_1` und `VEGGIE` als feste Menüarten; alle Tages-, Wochen-, Mobile- und Player-Prototypen zeigen beide |
| Kein Kostenmodell bei Patienten | separate `menu_item_prices`; DB-Trigger; Patienten-Snapshot/CSV/Templates ohne Kostenfelder |
| Mitarbeitende und Externe mit Kosten | Cafeteria-Snapshot und -CSV mit `internal_rappen`/`external_rappen`; Screens mit beiden CHF-Ansätzen |
| Vier Player statt einer Fläche | vier feste Flask-Routen und vier getrennte Templates; zusätzliche Geschlossenfläche |
| Wochenplayer | Cafeteria 5 × 2 auf 1080p; Patienten 7 × 2 Mahlzeitenblöcke auf 4K |
| Wochenende und Schliessungen | `service_state` je Profil, Datum und Mahlzeit; Cafeteria-Sonntag zeigt geschlossen |
| Getrennte Publikation | je Profil eigene Woche und aktive Revision; Tag/Woche desselben Profils lesen denselben Snapshot |
| Küchenfreundliche CSV | getrennte Patienten- und Cafeteria-Vorlagen statt Einheitsdatei |
| Rollenüberbau | drei Rollen; Publisher darf auch korrigieren |
| Freie Playerparameter | Signage und veröffentlichte API lehnen Query-Parameter ab |
| Alembic-Fiktion | aus Requirements und SDD entfernt; SQL-Datei klar als Baseline bezeichnet |
| Demo-Risiko | Produktion startet nicht mit Demo-Flags; Demo besitzt keine Adminrolle |
| Redis-Passwort im Healthcheck | dediziertes Healthcheck-Skript ohne Passwort im Kommando |
| Lokale Admin-Bootstrap | `python manage.py bootstrap-local-admin --username X --display-name Y` auf der Owner-Verbindung |
| Küchen-Workflows | CSV-Import mit Preview, Publikation und Rückzug pro Profil mit Capabilities |
| App-Role Grants | cafeteria_app erhält EXECUTE auf Validator-Funktionen für sichere Publikation |

## Noch nicht als erledigt behauptet

| Thema | Nachweis-Status |
|---|---|
| Menü-Import-UI | Prototypen vorhanden; CRUD-/Publish-UI teilweise umgesetzt, Kitchen-Workflows referenziert |
| PostgreSQL-Ausführung | Schema und Trigger live getestet; Validator bestätigt (2199 passed, 14 skipped) |
| Compose-Betrieb | auf Zielhost (dishboard.joelduss.xyz) gestartet; Healthchecks bestätigt |
| Backup/Restore | Drill-Tests vorhanden (RUN_LIVE_RESTORE_DRILL=1); realer Produktions-Restore offen |
| Entra | Login und Rollensync optional und offen; Entra-Tenant noch nicht konfiguriert |
| 4K-Lesbarkeit | Screenshot vorhanden (3840 × 2160); Sichtprüfung auf realem Player offen |
| Fachabnahme | Küche/Hotellerie/Pflege/ICT/Datenschutz müssen Checkliste unterzeichnen |

## Screenshotumfang

Das Paket enthält 14 primäre Referenzscreenshots in `design/screenshots/` (plus drei Kompatibilitätskopien) und 18 Live-Screenshots in `design/screenshots/live/` mit INDEX.json. 

Primäre Referenzscreenshots: vier fachliche Player-Ansichten (Cafeteria Tag/Woche/geschlossen + Patienten Tag), eine 4K-Patienten-Woche, vier Mobile-Ansichten (Cafeteria und Patienten, heute/Woche), zwei Website-Wochenansichten (Cafeteria und Patienten) und zwei Backend-Raster (Cafeteria und Patienten).

Live-Screenshots: Anmeldung, lokale Auth, beide Profile website/mobile/signage (heute und Woche), beide Admin-Raster, vier Player-Varianten, Geschlossenfläche, 4K-Wochenplayer.
