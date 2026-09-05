# Dishboard: Ausführung des gesamten Backlogs

Stand: 6. September 2026. Aktives Nutzerziel: **«arbeite alles ab an was du jetzt dran bist und das backlog»**. Der Umfang umfasst sämtliche offenen Einträge in [BACKLOG.md](../BACKLOG.md), nicht nur die erste Welle. Kleine Lieferungen sind Zwischenstände, keine Erfüllung des Gesamtziels.

## Ausgangspunkt und neue Entscheidungen

- Autoritativ geprüft: `main`/Produktion `b644dac`, Schema 16, gesundes Image `sha256:b27ef0b959f8d6b1c8d0bf43429aff481171cb2cdce100a07975153a2c213e41`. UI-001/UI-002 sind bereits geliefert.
- Voriger Zielturn: **Fortschritt** durch Produktivdeploy, unabhängige Live-Gates und versionierten vollständigen Backlog.
- Gesamtes Admin bleibt Tabler, einschliesslich neuer Editor-Bedienelemente. Bestehende Bibliotheken verwenden; keine Übernahme eines fremden Admins.
- Nutzerkorrektur: **generisch responsiv**, keine Bindung an ein bestimmtes Samsung-Modell. Signage nutzt **Yodeck auf Raspberry Pi 4B**. Browserbreiten und tatsächliche Player-Anforderungen bestimmen die Abnahme.
- API-001 entwickelt Claude auf ausdrücklichen Nutzerentscheid parallel. Codex bearbeitet die übrigen Backlog-Pakete und übernimmt nach Claudes Lieferung die unabhängigen Gates, Integration und sämtliche Deployments einschliesslich API. Keine parallele API-Implementierung durch Codex; Recovery-Commits und offene Gates werden an Claude übergeben.
- Nur Orchestrator integriert, pusht und deployt. Fremde dirty Worktrees bleiben erhalten. Testdatenbanken exklusiv zuordnen; keine Secrets lesen oder protokollieren.

## Erste Ausführungswelle

| Paket | Verantwortung / Vertragsdateien | Unabhängiger Nachweis |
|---|---|---|
| CAT-001 / wp-40505b9bf3d7 | Eigener WT `component-filters-0906`: Katalog-Store, Komponentenroute, Rendering, Komponenten- und Ländermakro, zugehörige Tests. Keine Sidebar/Base/Settings. | Kombinierte Filter, validierte Querywerte, archivierte/inaktive Daten, kompatible Editor-Auswahl; 390/820/1440 px, GET/Reset/Trefferzahl und bestehendes CRUD. |
| DSP-001 / wp-1183b3cef096 | Eigener WT `global-admin-density-0906`: validierter globaler Settingswert, Route/Registrierung, Tabler-Seite, Sidebar/Base, Dichte-JS/CSS und Tests. Keine Komponenten-/API-/Schemaänderung. | Standard kompakt ohne JS, zwei Browser gleicher globaler Zustand, Rollen/CSRF/ungültige Werte, alte LocalStorage-Werte ignoriert, CSV `data-state` und Pflicht-Hilfen erhalten. |
| API-Inventur / wp-fb3b2cfecee4 | Bestehende A1/B/D/C/A2/F-Lanes nur lesen und übernehmen, wenn Commit und Gates geprüft sind. | Terminalbelege plus aktuelle Prozess-/Worktree-Prüfung; kein Neustart anhand alter Logs oder Quotenmarker. |
| API-Recovery | Fertige Korrekturen A1 `5a5f98b` auf `1631264`, D `6bc1cc7` auf `661eb19`; Übergabe an Claude. | D: `153 passed in 80.18s (0:01:20)`, `GATE_EXIT=0`. A1-Datenbankgate und unabhängige Integration bleiben bei Claude offen. |

Testpaar-Zuordnung: CAT nutzte `test_sdd`, DSP `ui_other`; beide sind nach Abschluss frei. Codex reserviert `test_root` für das kombinierte UI-Gate. API-D-Recovery ist beendet; `api-d` steht Claude wieder zur Verfügung. Claude besitzt die API-Implementierung samt Migration 0014/v17; Codex besitzt unabhängige Integration und alle Release-Umschaltungen.

GitNexus meldet hohe Auswirkungen bei gemeinsamem Komponenten-Store/Rendering: bestehende Signaturen und Auswahlpfade kompatibel halten und mitprüfen. A1 enthält im übernommenen Quellstand einen unbedingten TRUNCATE auf Menüwochen/Publikationen; dieser gehört nicht zur API-Funktion und darf nicht nach main gelangen. Produktivstand enthält diese Änderung nicht.

## Gesamter Ausführungspfad

| Stufe | Backlog-IDs / Ergebnis | Abhängigkeit |
|---|---|---|
| 1 | CAT-001, DSP-001: Komponentenfilter und globale Darstellung liefern. | Bestehende v16-Settings, keine Migration nötig. |
| 2 | API-001 Welle 1: Schema/Keys, REST, FHIR, MCP, Swagger; kombinierte Gates und Sicherheitsreview. | Recovery und Übergabe §4; Migration 0014 reserviert. |
| 3 | API-001 Welle 2: Tabler-Verwaltung/Schlüssel-Endpunkte; abschliessende Integration und Deploy v17. | Welle 1 bestanden, `brief-e.md`/`brief-g.md`, unabhängiges Review/Backup. |
| 4 | SCR-001, TPL-001: Screens- und Vorlagen-Einstieg mit bestehenden Zielen/Fachkatalogen; aktive Vorlagenzuordnung später vollständig anbinden. | Navigation aus Stufe 1; noch keine fertigen Editoren behaupten. |
| 5 | ICO-001/002: lokale Allergen-/Flaggenassets, einheitliche Zuordnung, automatische Legenden in allen Ausgaben. | Fachcodes und PDF-/Public-Verträge erhalten. |
| 6 | SCR-002/003, TPL-002/003, REC-007: bestehende Screen-/Druckeditoren erproben und in Tabler einbinden; revisionierte Vorlagen, echte Vorschau, Aktivierung/Rückweg. | Gemeinsame Assets; Schemafolge nach API; Wochen-PDFs jeweils eine Seite, Rezepte/Einkauf lesbar mehrseitig. |
| 7 | BRD-001, OPS-001: Logo/Farben/Schriften, Anzeigenamen, Öffnungs-/Essenszeiten mit Ausnahmen. | Validierte Settings/Assetpfade und datierte veröffentlichte Services. |
| 8 | IAM-001/002: Benutzerverwaltung, letzter lokaler Admin geschützt; Entra-Entwurf/Test/Aktivierung. | Bestehende Auth-Issuer-Grenze, koordinierte Migrationen, Auth-/Konfigurationswechseltests. |
| 9 | REC-001, BAS-001, REC-006: Rezept-/Zutatenmodell, Kochbücher, Grundlagen/Lager, Suche und Batch-Tags. | Vorhandene Menüs/Komponenten integrieren, keine doppelten Fachbestände. |
| 10 | REC-004/005, PKS-001: CSV/XLSX/JSON, Rezeptmanager, Schema.org-Webimport, Pauli-Adapter. | Tatsächliche Formate/Beispieldaten, Importvorschau, Fehler-/Dublettenbehandlung und berechtigter Datenzugang. |
| 11 | NUT-001, OFF-001, REC-002: Produkt-/Lieferantendaten, Barcodevorschläge, KI-Erkennung/Strukturierung. | Quellen-/Prüfstatus, manuelle Übernahme; bestätigte Werte nicht automatisch überschreiben. |
| 12 | CALC-001, REC-003, INV-001, ORD-001: Portions-/Warenkosten, Planung/Einkauf, Inventur und Bestellvorbereitung. | Mengen-/Einheiten-/Bestandsvertrag, Lieferantenadapter und ausdrückliche Bestellbestätigung. |
| 13 | TRN-001: Fachglossar/Übersetzungseditor in fünf Sprachen. | Berechtigte Begriffsquellen und Fachprüfung, keine ungeprüfte Zusage fremder Wörterbuchbestände. |
| Begleitend | QA-001, DATA-001: responsive/Player-/Druckabnahme und fachliche Bestätigung unbekannter Daten. | Passende Funktion muss tatsächlich nutzbar sein; fehlende fachliche Daten bleiben offen. |
| Nach laufenden Lieferungen | UI-003: Corral-Referenz für Labels, Typografie, Abstände und visuelle Hierarchie auf Tabler adaptieren. | Nutzer hat ausdrücklich Backlog gewünscht; zuerst Referenzvergleich, dann bestehende Tabler-Komponenten und zentrale Tokens anpassen. |

Dateiunabhängige Unterpakete aus verschiedenen Stufen dürfen parallel laufen. Die Entwicklung der API-Stufen 2 und 3 liegt bei Claude, unabhängige Gates und Deployment bei Codex. Gemeinsame Sidebar, Registrierungen, Settings- und Publikationsverträge gehören pro Welle genau einer Lane. Die Tabelle ordnet Abhängigkeiten; sie ist kein Auftrag, alle Arbeit strikt seriell abzuarbeiten.

## Yodeck-Vertrag

Die vier vorhandenen öffentlichen HTTPS-Signage-URLs können als Yodeck-Medium **Web Page** eingebunden werden. Öffentliches HTTP 200 wurde geprüft, nicht die Bedienung eines fremden Yodeck-Kontos. Chromium, Zoom/Auto-adjust und Fallbackbild nach [Yodeck-Webseiten-Dokumentation](https://www.yodeck.com/docs/user-manual/web-pages-introduction/) berücksichtigen.

Gemeinsames Ziel ist 1920×1080; Hochformat zusätzlich prüfen. 4K ist eine separate Ausgabeoption: [Yodeck-Kompatibilität](https://www.yodeck.com/docs/user-manual/raspberry-pi-compatibility/) unterscheidet Pi-4B-RAMvarianten. Patientenwochen müssen auch im FHD-Konzept gut lesbar sein; bei notwendiger Aufteilung bleibt der gesamte Wocheninhalt über nachvollziehbare Seiten/Rotation erreichbar. Kein blosser Zoom eines übergrossen Rasters als Lesbarkeitsnachweis.

Die bestehenden HTML-Seiten besitzen bereits Meta-Refresh 300 Sekunden. Zusätzlich [Player-Refresh](https://www.yodeck.com/docs/user-manual/how-to-set-a-web-page-to-refresh/) bei Einzel-Webseiten prüfen. [Offline-Verhalten](https://www.yodeck.com/docs/user-manual/does-yodeck-work-offline/): serverseitiger Last-Good-Cache ersetzt keine Offline-Datei auf dem Pi; ein freigegebenes Fallbackbild ist separat bereitzustellen/zuordnen. Kein Playerkonto oder externer Bildschirm wird ohne passenden Zugriff als konfiguriert behauptet.

## Fertigstellung und fortlaufende Nachweise

Jedes Paket braucht Quellcommit, unabhängige passende Gates, Manifest/Build und bei UI-Änderungen echten Browser-/Live-Nachweis. Erst danach Status im Backlog aktualisieren. Regelmässig kleine geprüfte Releases ausliefern. Bereits vorhandene Gesamttests nicht pauschal als Nachweis neuer Funktionen verwenden.

Gesamtziel bleibt aktiv, bis sämtliche geforderten Funktionen und ihre Abnahmen nachgewiesen sind. Externe Produkt-/Glossardaten, konkrete Pauli-Exportformate und fachliche Freigaben getrennt von implementierter Import-/Prüffunktion ausweisen; fehlende Daten nicht erfinden. Ein einzelner offener Anschluss hält andere unabhängige Pakete nicht an.
