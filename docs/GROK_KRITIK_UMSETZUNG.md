# Umsetzung der Grok-Kritik

**Stand:** 1. September 2026  
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

## Noch nicht als erledigt behauptet

| Thema | Offener Nachweis |
|---|---|
| Vollständiger Wocheneditor | Prototyp vorhanden, CRUD-/Publish-UI noch umzusetzen |
| PostgreSQL-Ausführung | Schema in realem PostgreSQL-Container starten und DB-Vertragstests ausführen |
| Compose-Betrieb | Image-Build, Service-Start und Dauerlauf auf Zielhost |
| Entra | Login, Rollen, Entzug und Logout im Südhang-Tenant |
| Backup/Restore | realen Dump erzeugen und in separates Testsystem zurückspielen |
| 4K-Lesbarkeit | Sichtprüfung auf dem realen Patientenplayer aus typischer Distanz |
| Fachabnahme | Küche/Hotellerie und ICT müssen die Checkliste unterzeichnen |

## Screenshotumfang

Das Paket enthält 14 primäre Referenzscreenshots und drei Kompatibilitätskopien. Dazu gehören vier fachliche Player-Ansichten, eine Cafeteria-Geschlossenfläche, vier Mobile-Ansichten, zwei Website-Wochenansichten und zwei Backend-Raster. Die Patienten-Woche liegt zusätzlich als 1080p-Vorschau und als 4K-Produktionsentwurf vor.
