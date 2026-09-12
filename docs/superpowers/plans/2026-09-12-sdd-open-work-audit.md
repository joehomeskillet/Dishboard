# SDD-Abgleich und offene Arbeit — 12. September 2026

Arbeitsstand für die nächste Sprintplanung; ergänzt am 13. September 2026 um die
UI-Aufträge für Gerichtvorlagen, Rezeptverknüpfung, Tagesplanung und Rezeptdruck.
Dieser Abgleich startet keine Produktimplementierung und erklärt keine fachliche Abnahme.

## Quellen und Baseline

- Prüfstand: `2fa44dea36675692bfb8ad4b681dca73dba06737`, `github/main`, Schema 30.
- Letzter belegter Deploy: 12. September, 23:15:29 CEST; healthy und öffentliche HTTP-Proben grün.
- Führende Vertragsquellen: `docs/superpowers/backlog-0909/README.md`, die drei
  `*-sdd.md` und `*-wps.json`, `execution-contract.md`, `docs/BACKLOG.md`.
- Ursprüngliche Produktregeln: `docs/SDD_Klinik_Suedhang_Cafeteria_v3.0.md`.
  Historische Schema-, Liefer- und UI-Statusangaben darin sind kein aktueller Iststand.
- Aktuelle UI-Regeln: `docs/design/2026-09-09-unified-ui-design-system.md` und
  `docs/design/2026-09-12-patientenplan-menueditor-korrektur.md`.
- Lieferbelege: `docs/design/2026-09-12-correction-wave-delivery.md` und externe
  Berichte `wp-release-schema29-0912.md`, `wp-release-schema30-0912.md`,
  `wp-release-wave-final-0912.md` unter `/nvmetank1/projects/rag-stack/.claude/reports/`.

## Manifestzählung der Ausgangsbasis, keine Abschlussquote

| Bereich | WPs | READY | PLANNED | IN_PROGRESS | REVIEWED_LOCAL | DEPLOYED | AWAITING_EXTERNAL |
|---|---:|---:|---:|---:|---:|---:|---:|
| Operations | 37 | 3 | 30 | 0 | 0 | 0 | 4 |
| Rezepte | 43 | 4 | 28 | 4 | 3 | 0 | 4 |
| Surfaces | 65 | 8 | 28 | 0 | 0 | 24 | 5 |
| Gesamt | 145 | 15 | 86 | 4 | 3 | 24 | 13 |

Alle 35 Backlog-IDs sind im bestehenden Graphen zugeordnet; keine fehlende
Abhängigkeits-ID. Diese strukturelle Deckung beweist weder vollständige Umsetzung
noch vollständige fachliche Abnahme. Insbesondere sind die vier `IN_PROGRESS`
keine belegten aktuell laufenden Worker; die vorige Welle ist beendet.
Neue Pakete aus dem UI-Auftrag werden als Ergänzung zu dieser historischen
145-Paket-Zählung ausgewiesen, nicht rückwirkend in den Ausgangsstand eingerechnet.
Das [vollständige Einzelregister](2026-09-13-sdd-work-package-register.md) bewahrt
alle 145 IDs mit Originalstatus, auditierter Einordnung, nächstem Schritt und Quelle.

Nachtrag 13. September: sieben neue UI-/Rezeptpakete ergeben **152 Pakete**
(37 Operations, 48 Rezepte, 67 Surfaces), weiterhin 35/35 Anforderungen.
`MP-REC-DISH-TEMPLATE-WRITER` wurde mit Lieferbeleg von `PLANNED` auf `DEPLOYED`
korrigiert. Die neuen sieben Pakete bleiben `PLANNED`; Umsetzung, aktive Leases
und Produktabnahme werden damit nicht behauptet.

## Erledigte Arbeit nicht neu bauen

- Schema 27/29/30, Grundlagen-Verknüpfung und priorisierter Import sind geliefert.
  SQL nach finalem Deploy: 61 Rezepte, 32 Gerichtvorlagen, 100 Zutaten, 3 Lagerorte.
  Darin 32 Gerichte plus 29 Vorbereitungsrezepte; Importwiederholung und echte isolierte
  Restoreproben sind belegt. `MP-REC-DATA-IMPORT` ist keine noch offene Importfreigabe.
- Alle P1/P2 der letzten Korrekturwelle sind ausgeliefert. Daraus folgt kein
  pauschales `ACCEPTED` für den vollständigen ursprünglichen UI-Auftrag.
- Bestehende reine Kosten-, Importadapter- und Einkaufsaggregat-Kerne werden vor
  Folgearbeiten übernommen; fehlende Produktanschlüsse erhalten ihren bestehenden WP.
- Das UI-Inventar existiert. Veraltete Revision/Schema/Routenangaben aktualisieren,
  statt ein zweites Inventar aufzubauen.

## Getrennte Restarbeitsarten

1. **Statuskorrektur:** Ausgelieferte Commits und vorhandene Belege den ursprünglichen
   MP-IDs zuordnen. Historische Fehlversuche erhalten; keine rückwirkenden PASS-Erfindungen.
2. **Technische Restfunktion:** Fehlender Produktpfad mit vollständigem Vertrag,
   Verbraucheranschlüssen, Dateibesitz und kurzem Gate.
3. **Technischer Nachweis:** Vorhandene Funktion, deren geforderter aktueller
   Integrations-/Browser-/Releasebeleg fehlt. Keine automatische Neuimplementierung.
4. **Externe Abnahme:** Konkrete Küche, berechtigte Quelldatei, Tenant, Consumer,
   Druckgerät oder Player fehlt. Nur davon abhängige Pakete warten.

## Zusätzlich entdeckte Traceability-Lücken

| Bedarf | Quelle | Einordnung |
|---|---|---|
| Backupkopie ausserhalb des Dockerhosts | Master-SDD:291; `docs/DOCKER_COMPOSE_RUNBOOK.md`:69 | Kein explizites WP gefunden. Lokale Restoreproben ersetzen keinen Offhost-Beleg. Neuer Abnahmeauftrag mit benanntem Ziel, berechtigtem Operator, Hash und Restoreprobe erforderlich; kein Transfer auf geratenes Ziel. |
| Weitere Rezeptmanager-/Sammlungsformate | `docs/BACKLOG.md`:186; `docs/design/2026-09-05-screens-vorlagen-verwaltung.md`:159 | Format-/Fixtureentscheidung vor Adapter-WP ergänzen; vorhandene CSV/JSON/XLSX-Pakete decken nicht automatisch alle Fremdformate. Pauli bleibt in MP-PKS, mit REC-004-Querverweis. |
| Richtext-Implementierung nach Entscheidung | `docs/design/2026-09-06-bas-rec-data-contract.md`:930; `MP-REC-RICHTEXT-DECISION` | Entscheidung ist ein eigener Auftrag; eine nachfolgende Implementierung nur mit konkretem freigegebenem Umfang, CSP und Tabler-Vertrag planen. |
| Bestand auf der Zutatenkarte | `operations-sdd.md`:202; Operations-Audit `wp-4a3597a72ed7` | Foundations-Route/Template fehlen im bisherigen Inventur-Schreibbesitz. Nach BALANCE-READ unbekannt, bestätigte Null und positiven Saldo über den bestehenden Food-Consumer zeigen. |
| Beobachtete Bedienaufgabe | Korrekturdokument:238,378; Surfaces-Audit `wp-855e496d2bb5` | Menü finden → nur Beilage ändern → speichern → Prüfstand erklären. Eigenes Usability-WP nötig; DATA-KITCHEN prüft Daten, nicht diese Bedienaufgabe. |

## Bestätigte technische Restketten

| Bereich | Weiterhin fehlender Umfang | Bestehende Pakete und Reihenfolge |
|---|---|---|
| Rezeptnutzung | Zielportionen, gespeicherte Einkaufslisten und deren PDF | PLAN-PORTIONS → SHOPPING-PERSIST → SHOPPING-PDF; vorhandenen SHOPPING-AGGREGATE-Kern übernehmen |
| Suche | FTS, TRGM, gespeicherte Filter und Stapel-Tags | SEARCH-FTS zuerst; TRGM nur nach Betriebsentscheid; Saved Search/Batch Tags als eigene Folgepakete |
| Quellen/Nährwerte | URL-Produktpfad, XLSX, Provideranschluss, Nährwerte, OFF-Vorschlagskette | Vorhandene reine Schema.org-/KI-Adapter nicht neu bauen; persistente Anschlüsse und externe Eingaben getrennt |
| Kosten/Lager/Bestellung | Preisledger, historische Kalkulationen, Bestandsjournal, Inventur, Korb/Export | Zwei Kostenkerne bereits integriert; Lagerorte sind kein Bestand. Versand erst mit realem Anschlussvertrag |
| Fachwissen | PKS-Adapter und Glossar/Übernahme | Rechteartefakte wiederbeschaffen, autorisierte Fixture; keine erfundenen Fremddaten |
| Screens/Vorlagen | Web-Tag, TV-Varianten, Geräte/Playlists, freier Screeneditor, freie PDF-Geometrie, vollständiger Hub | Vorhandene Registry/Editoren sind nur Teilumfang; Entscheidungen und Consumerketten nach UI-Prompt konkretisieren |
| Entra | Revisionierter Connection-Lifecycle | Secretresolverentscheidung → Draft → Test → Aktivierung; echter Tenant separat |
| Abnahme | Aktuelle UI-Matrix, vollständige Regressionen, Küche/Druck/Client/Player | Gelieferte Funktionen mit Originalkriterien abgleichen; keine erneute Implementierung allein aus altem PLANNED |

## UI-Auftrag vom 13. September und nachrangige Altlasten

Erster UI-Sprint: Gerichtvorlagen und Rezepte gegenseitig auffindbar verknüpfen;
aus einer Vorlage ein Menü bewusst einem konkreten Plan und Tag zuordnen;
pro Rezept getrennte Aktionen Ansehen und Drucken sowie den Bezug zur Druckvorlage
anbieten. Fable 5.1 plant diese Ergänzung; getrennte GPT-Quellcodeaudits sind
`wp-recipe-links-discovery-0913.md` und `wp-recipe-view-print-discovery-0913.md`.
Vorhandene Datenbeziehungen, unveränderliche Rezeptansicht und PDF-Erzeugung werden
wiederverwendet. Fehlende Rückverweise, Listenaktionen und Planübergabe sind
Produktanschlüsse; bestehende Funktionen werden nicht als fehlender Neubau geführt.

Die folgenden Altlasten bleiben nachrangig und werden nicht in den neuen
Funktionsauftrag hineingezogen:

| Befund | Priorität | Nachgewiesener Rest / Besitz |
|---|---|---|
| DEBT-01 | P3 | Unerreichbare Legacy-Admin-Blöcke in `static/app.css`; Auth-Ladekette beachten |
| DEBT-02 | P3 | Doppelter Kartenraster-Kern in `recipe-admin.css`/`cookbook-admin.css`, Rezept-/Kochbuchtemplates; Equal-Height und Spalten erhalten |
| DEBT-03 | P3 | Doppelte Fokusregeln in `admin-preview.css`/`admin-screens.css`; berechnete Gleichheit und sichtbaren Tastaturfokus zuerst belegen |
| DEBT-04 | P4 | Unbenutzte Selektoralternativen in `admin-tabler.css`; aktive Alternativen/Vendor-CSS erhalten |
| BUG-03 | P4-Kandidat | Unerreichbarer Dropdown-Escape-Zweig in `admin.js`; Details-/Tooltip-Escape erhalten; erst nach Editor-Freeze prüfen |

Pfade in dieser Tabelle liegen unter `reference_scaffold/cafeteria/`.
Originalbelege: `wp-an-tests-0912.md`:87–125 und `wp-an-frontend-0912.md` im
externen Reportverzeichnis. A04 und der Editor-Eingabeart-Fix `81aba15` sind erledigt
und gehören nicht in diesen Restbestand.

## Bereits feststehende Planungsgrenzen

- Eigener Worktree pro Writer unter `.claude/worktrees/`, Remote `github`.
- Drei native parallele Workerplätze in dieser Sitzung; zusätzlich sind Claude,
  Cursor, AGY und Grok per Nutzeranweisung für eigenständige WPs freigegeben.
  Maximal fünf schwere Hostjobs insgesamt, `rtk pgrep -fc pytest` unter 12;
  Speicherregel und tatsächliche Prozesslast vor Ausführung erneut prüfen.
- Root darf neben Orchestrierung auch abgegrenzte WPs im eigenen Worktree bearbeiten.
  Seine Änderungen brauchen ebenso einen unabhängigen Reviewer.
- SQL-Schema, Migrationsnummern und gemeinsame Registrierungen jeweils ein Besitzer;
  neue Migration erst nach Vorgänger-Freeze nummerieren, niemals alte Schema27-Pläne blind replayen.
- Autor und Reviewer getrennt; bestätigte Review-Fixes an anderen Autor.
- Gezielte Sprint-Gates pro Änderung, unabhängiges Root-Gate und eigener
  Releasebeleg je Integration. Keine unveränderten Gesamtsuiten für kleine Textkorrekturen.
- Patientenkanal strukturell ohne Preise; unveränderliche Historie, Originalactor,
  Standort, CAS, CSRF und Audit erhalten. Keine Abhängigkeiten installieren.
- Keine Secrets lesen, keine fremden Baselines übernehmen, keine produktiven
  Daten als Testfixture. Temporär gestoppte Container bleiben gestoppt.
- OCR-Ausfall, fehlender GitNexus-Index und fehlender authentifizierter Live-Browserbeleg
  sind offene Nachweise; weder automatische Dauerfreistellung noch neue Feature-WPs.

## Auditbesitz

| WP | Unabhängiger Codex-Audit | Bereich |
|---|---|---|
| `wp-4a3597a72ed7` | `sprint_ops_audit` | Operations-SDD und 37 WPs |
| `wp-20bbdcac693e` | `sprint_recipes_audit` | Recipes-SDD und 43 WPs |
| `wp-855e496d2bb5` | `sprint_ui_audit` | Surfaces-SDD und 65 WPs, DEBT01–04 |

Alle drei Audits abgeschlossen; vollständige Tabellen und exakte Quellen stehen
unter ihren WP-IDs im externen Reportverzeichnis. Root führt Ergebnisse und neuen
UI-Prompt in [einen einzigen Sprint- und Besitzplan](2026-09-12-next-sprints.md) zusammen.
