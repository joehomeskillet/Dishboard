# Dishboard: Ausführung des gesamten Backlogs

## Aktueller Deploy-Nachtrag — Snapshot vom 7. September 2026 nach 11:14:03 CEST

**Produktiv ist `783fab33520e15c956df431f62ad75c9940e2285`, Schema 21**, seit `2026-09-07T09:14:03.117859908Z` (11:14:03 CEST); Image `sha256:2ddb31a28e7297b258daf440170554dd8139f6dafd4cab485dda7484b6955a8b`. Root bestätigt `healthy` und null Neustarts. Vollständige Paketprüfung: **4837 bestanden, 15 explizite Opt-in-Skips, null Failures/Errors**. [Aktueller Deploybeleg](/nvmetank1/projects/menuplan/.claude/state/ops-root-evidence-0907/release-783fab3-deploy.md), wird um die frischen Live-Nachweise ergänzt. Historisch: `2cfc43f` seit 08:33:23 CEST, Image `sha256:3c5167b2615e4144c4353afebc08275b5c9441130a4c48a691e8f949568b4412`, **4716 bestanden/15 Opt-in-Skips/null Fehler** (14 Restore-Drills und eine Compose-Probe deaktiviert): [voriger Deploybeleg](/nvmetank1/projects/menuplan/.claude/state/ops-root-evidence-0907/release-2cfc43f-deploy.md).

**Aktuelle Live-Reader:** B3/V2 meldet **801 Checks, alle true, 34 Screenshots**, Status `incomplete`: Zutaten-/Kategorien-/Tags-Detaildaten, archivierte Einheit sowie inaktive und archivierte Vorlagen fehlen im aktuellen Datenbestand. Der erste Standard-Admin-Lauf meldet **695 Checks, alle true, 34 Screenshots**, ebenfalls `incomplete`: `cafeteria.copy` liefert für die bestehende Woche 2026-08-31 bei beiden Breiten 409. Root prüft die Screenshots; keine Produktivfixtures oder Publikationen für die Abnahme. Vor-/Nachbackup sind per SHA256 und TOC mit 41 Tabellen geprüft; beide Health-Endpunkte liefern 200. Diese lesenden Nachweise sind keine vollständige UI-/Fach-/Playerabnahme.

Historisch zu `2cfc43f` prüfte Root live **738 Admin-Checks/36 Screenshots**, **56 OPS-Checks/2 Screenshots** und **193 ergänzende Checks/10 Screenshots** für Vorlagenkatalog, Screens und Darstellung, jeweils ohne fehlgeschlagene Checks. Datierte PDFs für 2026-08-31 enthalten 10/28 Menüs und Fotos auf je einer A4-Seite; Karten-/Überlaufgeometrie ist geprüft. Die damaligen Screen-Frames zeigten mangels Wochenpublikation korrekt HTML-404 mit `no-store`: keine behauptete gefüllte Vorschau oder vollständige UI-/Fach-/Playerabnahme.

**B2/V1 und jetzt B3/V2 sind produktiv:** Stammdaten-Admin und Vorlagenarchivierung/-reaktivierung ergänzen die bisherigen Kerne; BAS-/TPL-Gesamtaufträge bleiben offen. Menü-Iconaktionen und deklarierte VEG/VGN bleiben produktiv. Die Vorab-Gates `24726` (**306 Tests in 510.48s, null Skips**) und `75283` (**132 Tests in 212.08s, null Skips**) sind durch das vollständige Paketgate ergänzt. Die echte unveränderliche **Kandidat → Fallback → Kandidat-Runde bestand**, mit 36 Screenshots, unveränderter Datenidentität/Sentinels und historischen PDF-Bytes. Begrenzter Fallback: `16b2e72`, Image `sha256:f9669285acce8628c0adf765f294e8b34d589174a22de9391ded9caa5ace81c7`; das alte V1-Image `2cfc43f` ist nach V2-Schreibvorgängen kein Rollback.

**R1 bleibt ohne Gesamtfreigabe und Deploy:** Auf den reinen R1-A-Wertekern (Root: 152 Tests, Ruff PASS) folgen R1-B/Migration `0019_v21_to_v22.sql` und reserviertes Schema 22. Root bestätigte inzwischen 590 Tests und Ruff PASS; normales Mypy bleibt mit 58 bestehenden, baseline-identischen Diagnosen ausdrücklich nicht grün. Ein bestätigter P2-Befund zu gleichem Bildhash bei abweichender Lizenz wird separat korrigiert. R2-UI ist weiterhin geplant, kein Rezepteditor ist fertig. [Folge-Release-Checkpoint](/nvmetank1/projects/menuplan/.claude/state/ops-root-evidence-0907/next-release-r1-checkpoint.md). Der Admin bleibt **Tabler**, nicht Tablet-first. Historische Nachweise unten bleiben erhalten.

## Historischer Root-Checkpoint — 7. September 2026, 06:25 Uhr Schweiz

Die Uhrzeit bezeichnet den belegten Root-Nachtrag um 06:25 CEST (Root-Uhr: 04:25:04 UTC). Der datierte Admin-Live-Beleg unten stammt weiterhin von 05:16 Uhr; daraus wird keine neue Live-Abnahme abgeleitet.

**Produktiv bleibt `3d35cbb` seit 07.09.2026, 04:18:43 CEST, Schema 20.** Das vollständige unabhängige Paketgate bestand mit **4472 Tests und 15 ausdrücklich aktivierbaren Opt-in-Skips**. OPS-001 ist ausgeliefert; B1 gehört ebenfalls zu diesem Release.

Frischer OPS-Beleg `ops-live-branding-3d35cbb-root-0907/proof.json`: **56 Checks bestanden, beide Viewports**. Datierter Admin-Beleg `admin-live-week-3d35cbb-root-0907/proof.json`, erfasst `2026-09-07T03:16:09.722335+00:00`: **738 Checks bestanden, 36 Screenshots, keine Fehler oder nicht verfügbaren Prüfungen**. Beide Familien und Viewports verwenden die gespeicherte Woche **2026-08-31**. Operatorquelle `450894babda514e63602b2e40c8ae123263c38cc` bestand unabhängig 167 Tests nach getrennten Läufen mit 149 und 78 bestandenen Tests. Die datierte Druckprüfung beider Familien bestand mit 10/28 Fotos, jeweils einer PDF-Seite und gleichen Karten; TPL-003 behält die fachliche Druckabnahme.

**Noch nicht deployed:** Symbolkandidat `5b746b35d261ed8b552724b3b273e71fd393973c` enthält Menü-Iconaktionen und deklarierte VEG/VGN für UI-003/ICO-001/002. Kombinierte 121 Tests und unabhängige Imageprüfung (677 gleiche Dateien ohne Extras, 247 AST-Prüfungen, Label/Benutzer/pip/Schema-20-Hashes; Build-WP `wp-1b31436a1455`) bestanden. Vollständige Releasegate-Versuche 6043 und 89103 endeten beide mit Exit 143 ohne JUnit oder Abschlussausgabe; Ursache unbelegt. Root bewahrte beide Evidenzstände, bestätigte jeweils das Ende der Exportprozesse und eskalierte die Abbrüche. Kein dritter unveränderter Lauf und kein vollständiges PASS.

Public-404/`no_published_menu` bleibt bei fehlender aktueller Publikation korrekt. Der Tabler-Fix der bisherigen Public-Leerseite `de80b7e` bestand Rootgate 64757 mit **1959 passed in 65.04s**, Ruff und unverändertem Mypy-Basisvergleich. Mit Operator- und Dokumentationsänderungen ist er in `37ddf54` integriert, nicht deployed; Root bestätigte kombiniert **2126 Tests in 132.06s**. Manifest und vollständige Releaseabnahme stehen aus.

**B2 und V1 unabhängig geprüft, noch nicht ausgeliefert:** B2-Fix `7ca528695e8c1b123d524f6ac6325ef122e8b764` bestand Root G1 mit **218 Tests in 99.57s** und G2 mit **2172 Tests in 273.97s**, jeweils ohne Skips. V1 `8346dbc1d3d3babacfd2020050c5f81b905c1985` bestand **95 Tests in 97.03s**, ohne Skips; dies ist nur der revisionierte PDF-Katalog-Slice für TPL-001. Normale B2-/V1-Mypy-Prüfungen behalten die jeweils 58 Fehler in 12 Basisdateien, ohne neue Diagnosen; kein Gesamt-Mypy-PASS. Das kombinierte 22-Modul-Gate 63474 bestand mit **632 Tests in 357.85s**, ohne Fehler oder Skips. B2 und V1 sind in Root-Commit `17b7e84812b06d5d258220cde804e90bf7be9872` integriert. Manifest, vollständiges Releasegate und Deploy stehen weiterhin aus. Produktion bleibt Schema 20. B3 ist nach Plan und Review (Registrierungen 12161/12164) im eigenen Worktree `bas-b3-ui-astra-0907` auf `17b7e84` beauftragt; keine Implementierung ist fertig. Historische IAM-, Branding- und Playerbelege ersetzen weder neue technische noch offene fachliche und physische Abnahmen.

## Historischer Deploy-Nachtrag — 6. September 2026, 20:38:51 Uhr Schweiz

Die folgenden Nachweise betreffen den damaligen Schema-19-Release. Seine Sicherungen und sein UI-Fallback sind keine aktuelle Schema-20-Rückfallfreigabe; Root führt den geprüften Betriebscheckpoint separat. Historische Smokes ersetzen keine aktuelle Gesamtabnahme.

**Release `3690e04585af6b5c16917872cf6e4b50601b22c9` ist produktiv**, Image `sha256:6fca168acd508b2a66b58399f2beb1f87c979252f20aa55dc7897d1ba79bc828`, Start `2026-09-06T18:38:51.931697209Z` (20:38:51 CEST), `healthy`, öffentlicher HTTP-Status 200. Schema **19**, Migration/Runtime/Auth-Issuer jeweils `ready=true`, Registry-Prüfsumme `e195aac3c6b53fb08f733723cd8ef12e6e40fb7abdc5fe58bf1f88585015c6c1` bestätigt. Vollständiges Paket: **4001 Tests bestanden, 15 Opt-in-Skips**, 4016 insgesamt in 1603.990 Sekunden, `PACKAGE_GATE_EXIT=0`. Die 14 Restore-Opt-ins bestanden separat in 122.97 Sekunden. Die korrigierte Compose-Probe und vier Fehler-/Cleanup-Fälle bestanden gemeinsam mit dem Branding-Operator **67 unabhängige Tests in 21.87 Sekunden**; dies belegt Containererzeugung und Image-/Cleanup-Verträge, keine Dienst- oder Netzkonnektivität. [Aktueller Root-Beleg](/nvmetank1/projects/rag-stack/.claude/reports/wp-ee18982cddf0.md).

Neu live sind die lokale Benutzerverwaltung und gleich grosse Menükarten in beiden HTML-Wochen-Druckprofilen, auch mobil. Frische Nachweise: [IAM](/tmp/dishboard-iam-readonly-live-after-deploy-0906/proof.json) **208 Checks/12 PNG**, [Screens](/tmp/dishboard-screen-variants-live-iam-0906/proof.json) **386 Checks/20 PNG**, [API/Admin/PDF](/tmp/dishboard-iam-api-admin-live-0906/proof.json) **194 Checks/18 PNG**. Alle **788 Checks bestanden**, 50 Screenshots; der Screens-Beleg enthält separat acht abgebrochene Bildabrufe. IAM-Abnahme ausschliesslich lesend, kein produktiver IAM-Schreibtest. Vollständiger Login-/Logout-Zugriffsverlauf bleibt offen.

Die beiden Produktionssicherungen vor/nach Schema 19 sind von Root mit Hash und TOC geprüft. Ein Schema-19-kompatibler UI-off-Fallback `ff4fbc9` ist vorbereitet, unabhängig mit 177 Tests sowie Datei-/AST-/pip-Prüfungen bestätigt und nicht aktiv. Exakte Images und Backup-Hashes stehen im [aktuellen Backlog](../BACKLOG.md). Nach MIME-/Geometrie-Korrektur des Operators hat Root dessen 87 Tests, Ruff/Mypy und zweimal den vollständigen Live-Lauf geprüft: jeweils 798 Checks/40 PNG, null Fehler. Der rohe Status bleibt `incomplete`, weil individuelle öffentliche/Vorschau-Logos aktuell nicht verwendet werden und Zustandsabdeckung vom Live-Inhalt abhängt. Diese Branding-Varianten, physisches Yodeck, fachliche Küchen-/Druckbestätigung und externer Design-Validator bleiben offen.

## Aktive Ausführung — 7. September 2026

**35 IDs, keine Abschlussquote:** 17 IDs haben produktive Teilumfänge, einschliesslich OPS-001 und BAS-001 mit B1/B2; das sind keine 17 vollständigen Abschlüsse. 16 weitere grössere Umsetzungen bleiben offen, QA-001/DATA-001 begleiten als zwei fortlaufende Abnahmen. Freie Vorlagengestaltung, vollständige Screen-Zuordnungen und sämtliche Rezept-/Stammdaten-/Warenwirtschaftspakete behalten ihren Restumfang. Die ältere Lieferfolge unten ordnet Abhängigkeiten; ihr damaliger Status ist historisch. Aktuelle Einzelstände und vollständige ID-Zuordnung stehen in [BACKLOG.md](../BACKLOG.md).

Die früher unterbrochene OPS-Welle ist geprüft und produktiv. Ihre technischen Live-Nachweise
stehen oben; fachliche Bestätigung und physische Playerabnahme werden dadurch nicht ersetzt.

Operativ offene Live-Datenfälle für B3/V2 abnehmen; diese Teilumfänge sind mit `783fab3` ebenso wie Public-/Operator-Folgearbeiten, Symbole, B2 und V1
produktiv. R1-B/Schema 22 benötigt nach dem Lizenzbefund-Fix die unabhängige Gesamtfreigabe; R2-UI bleibt geplant. Die historischen Symbol-Fullgate-Abbrüche erhalten kein nachträgliches PASS. Danach offene Screens-/Vorlagen-/Branding-Funktionen,
Grundlagen/Rezeptverwaltung, Suche/Importe/Produktdaten, Rezeptplanung/Einkauf/
Druck/KI, Kalkulation/Lager/Bestellungen und weitere Anbindungen. Die vollständigen Phasen
und alle 35 IDs bleiben erhalten; Abnahmen begleiten jede Lieferung.

**Geprüfter Teilstand im aktuellen Code:** B1 `e0fb93e` (ursprünglich `c7873fa`, reine Mengen-/Einheitenfunktionen) ist nach
vollständigem Root-Diffreview und unabhängig **101 passed in 1.26s**, Ruff PASS und Mypy PASS
für zwei Dateien integriert ([JUnit](/tmp/dishboard-root-quantities-b1-0906.xml)).
B1 ist mit `3d35cbb` produktiv. B2 ist nach erfüllter OPS-Schema-20-Voraussetzung mit Fix
`7ca5286` unabhängig geprüft und mit `2cfc43f`/Schema 21 produktiv. B3 ist seit `783fab3` ebenfalls produktiv. [BAS/REC-Pakete](bas-rec-work-packages-0906.md)
und [Datenvertrag](../design/2026-09-06-bas-rec-data-contract.md) erhalten sämtliche Restaufträge.

**HugeRTE-Eignungsprobe:** 1.0.13 ist lokal browsergeprüft; Text, Fett, Listen und Silver-Linkdialog
funktionieren unter strikter CSP, dennoch bleibt eine Style-CSP-Verletzung. Silver ist kein
vollständiges Tabler-UI. [Prüfbericht mit Primärquellen](/nvmetank1/projects/rag-stack/.claude/reports/wp-28dc5618ccd1.md)
und [Browserbeleg](/tmp/dishboard-hugerte-wp-28dc5618ccd1/proof.json). Keine Technologiefreigabe;
vollständige CSP-/Tabler-Integration und Produktabnahme bleiben offen, BAS/REC sind nicht fertig.

## Historischer Deploy-Nachtrag — 6. September 2026, 04:55:35 Uhr Schweiz

Dieser Abschnitt dokumentiert den damaligen Schema-17-Stand. Seine offenen Marken-, Symbol- und Legendenumfänge wurden teilweise später geliefert; massgeblich ist der aktuelle Stand oben.

**Release `118a644` ist produktiv**, Image `sha256:afe5305a73128fb92cbbf3f325ea441aacc8b9a6acc38d28487c301eb9779c41`, Container `healthy`, Schema 17. Migration: 32 Tabellen, `ready=true`; Runtime: 30 sichtbare Tabellen, `ready=true`. API, alle vier öffentlichen Tabler-Seiten, vier globale Darstellungsoptionen und der erste Wochen-PDF-Eigenschaftseditor sind jetzt live. **3695 Tests bestanden, 15 Opt-in-Skips**, vollständige Paketprüfung `PACKAGE_GATE_EXIT=0`, **272 Live-Checks bestanden**, 44 Screenshots plus vier Rotationsscreenshots in FHD/4K mit allen 28 Patientenmenüs. [Vollständiger Root-Beleg](/nvmetank1/projects/rag-stack/.claude/reports/wp-bd5539046da6.md).

Die folgenden Vor-Deploy-Angaben zu `1bff82e` und «noch nicht deployed» sind für diesen Lieferumfang historisch. Live-Restbefunde: Favicon HTTP 404, physische Yodeck-Abnahme und externer Design-Validator. Wegen des Favicon bleibt der rohe Rotations-Gesamtstatus `passed:false`; Rotation und Layout bestanden. **Alle 35 Backlog-IDs und der vollständige Restumfang bleiben unverändert**, insbesondere freie Vorlagengestaltung, Markenpflege/Uploads, Screen-Zuordnungen und vollständige PDF-Symbole/Legenden.

Stand: 6. September 2026. Aktives Nutzerziel: **«arbeite alles ab an was du jetzt dran bist und das backlog»**. Der Umfang umfasst sämtliche offenen Einträge in [BACKLOG.md](../BACKLOG.md), nicht nur die erste Welle. Kleine Lieferungen sind Zwischenstände, keine Erfüllung des Gesamtziels.

## Historischer Vor-Deploy-Liefer- und Prüfstand — durch Nachtrag oben abgelöst

**Produktion vor dem neuen Deploy:** `1bff82e`, Image-Präfix `aeab807`, seit 06.09., 03:09:55 Uhr Schweiz, damals Schema 16. CSP-Korrektur um 03:16:31 Uhr; 78 Live-Checks und zwölf Screenshots belegen Screens-Vorschauen, entfernte Signage-Navigationslinks und die Admin-Kartengrössenprüfung. Beleg: `/tmp/dishboard-live-hubs-cards-proof-0906/proof.json`.

**Damals geprüft vorbereitet, noch nicht deployed:** `69ef540` integriert API/Schema 17, PS1–PS5, gemeinsame öffentliche Karten, Ausfallpuffer bis fünf Minuten/Mitternacht, vier globale Darstellungsoptionen und den ersten revisionierten Wochen-PDF-Eigenschaftseditor. BRD-001, TPL-002, SCR-001 und ICO-001/002 bleiben in ihrem vollständigen Umfang offen: freie Gestaltung, Uploads, umfassende Zuordnungen, Legenden und PDF-Symbole sind damit nicht geliefert.

Root hat alle 3710 gesammelten Tests aus 116 Modulen disjunkt auf vier isolierten Pools geprüft:

| Shard | Ergebnis | Laufzeit |
|---|---|---|
| 0 | 2390 bestanden, 1 Opt-in-Skip | 340.04 s |
| 1 | 492 bestanden | 377.44 s |
| 2 | 381 bestanden, 9 Opt-in-Skips | 278.72 s |
| 3 | 432 bestanden, 5 Opt-in-Skips | 389.02 s |

Gesamt: **3695 bestanden, 15 Opt-in-Skips, 22 Warnungen; alle vier `GATE_EXIT=0`**. Die Skips betreffen 14 Restore-Drills und einen Compose-Test. Verteilung: `/tmp/dishboard-release-shards-0906.json`; Logs: `/tmp/dishboard-release-shard-{0,1,2,3}-0906.log`. Frühere Läufe sind beendet: Blueprint-Gate 5 auf `d70460c` mit 3417 bestanden/15 Skips in 945.28 s; Root-Gate 6 auf `8316790` mit 3592 bestanden/1 Fail/31 Setup-Fehlern/15 Skips in 1153.23 s. Dessen Testverträge wurden mit `d8fd9d3` korrigiert und als `69ef540` integriert.

Weitere unabhängige Root-Gates: Mypy für 20 Quellen, Ruff für Quellen/Tests und Node-Syntaxprüfung bestanden; 265 Food- und drei Swagger-Artefakte verifiziert; Gitleaks über 32 Commits ohne Treffer. Bandit unter Python 3.13: 2130 Zeilen, keine Fehler oder Befunde; der Python-3.14-Scanner war wegen `ast.Str` unbrauchbar. Native Browser- und echte PDF-Belege liegen vor. Externe OCR ist nach 429/Timeout beziehungsweise null Modell-Tokens nicht verfügbar, kein CLEAN; Gemini-Design-Validator und physisches Yodeck sind nicht nachgewiesen.

Vor dem neuen Deploy: Backup `022019Z.lHhLPP.dump`, SHA-256 `c98ad3ff34224c477efefccdefa8f1344382e4bdf27ec34a70881a57273b65d7`, mit PostgreSQL 18.6 und 274 TOC-Einträgen geprüft. Beide bestehenden Wochen-PDFs für 2026-08-31 lieferten vor dem Deploy HTTP 200. Paketprüfung, Build, Migration 16→17 und neue Live-Abnahme bleiben bei Root; erst dessen Deploy-Beleg ändert den Produktivstatus.

## Historischer Ausgangspunkt und weiterhin gültige Entscheidungen

- Historischer Ausgangspunkt war `b644dac`, Schema 16. Den aktuellen Produktiv- und Prüfstand beschreibt der Abschnitt oben; UI-001/UI-002 sind bereits geliefert.
- Voriger Zielturn: **Fortschritt** durch Produktivdeploy, unabhängige Live-Gates und versionierten vollständigen Backlog.
- Gesamtes Admin bleibt Tabler, einschliesslich neuer Editor-Bedienelemente. Bestehende Bibliotheken verwenden; keine Übernahme eines fremden Admins.
- Nutzerkorrektur: **generisch responsiv**, keine Bindung an ein bestimmtes Samsung-Modell. Signage nutzt **Yodeck auf Raspberry Pi 4B**. Browserbreiten und tatsächliche Player-Anforderungen bestimmen die Abnahme.
- Seit Nutzerentscheid vom 06.09., 01:55 Uhr übernimmt Codex API-001 und sämtliche Public-Screens-Pakete allein, einschliesslich unabhängiger Gates, Integration und Deployments. Die frühere Claude/Codex-Aufteilung ist aufgehoben.
- Nur Orchestrator integriert, pusht und deployt. Fremde dirty Worktrees bleiben erhalten. Testdatenbanken exklusiv zuordnen; keine Secrets lesen oder protokollieren.

## Historische erste Ausführungswelle

### Übernahme und nächste Lieferung am 6. September

Die vorige Codex-Session wurde kontrolliert beendet und ihre Writer-Sperre freigegeben.
Die Weiterarbeit erfolgt in `integrate/backlog-takeover-0906`, Worktree
`.claude/worktrees/backlog-takeover-0906`. Basis ist der frisch abgeglichene
`github/main`-Commit `0ebea64`; fremde Worktrees bleiben erhalten.

- CAT-001 und DSP-001 befinden sich auf `main` und im laufenden Produktionsrelease
  `0ebea64`. Der gespeicherte Live-Receipt bleibt `incomplete`: keine Fehler,
  aber sechs nicht verfügbare positive Label-Prüfungen mangels gepflegter Daten.
- Das vorbereitete Symbolpaket `63fe3fb` + `7458cb1` wurde in den eigenen
  Integrationsbranch übernommen. Unabhängig bestanden: 1774 fokussierte Tests,
  Offline-Assetprüfung, Ruff und Mypy für die geänderten Module. Externe OCR blieb
  nicht verfügbar; spätere Release-/Live-Belege stehen oben. Legenden-Verbraucher und PDF-Einbindung
  sind weiterhin offen; ICO-001/ICO-002 sind insgesamt nicht abgeschlossen.
- Der neuere Nutzerauftrag und die Übergabe vom 06.09.2026, 01:55 ersetzen die
  Aufteilung von 01:40: Codex übernimmt API und alle Public-Screens-Pakete WP1–5
  vollständig. Der Nachtrag 02:00 meldet API-Gate 4 auf `37d00b7` bereits detached
  auf Pool `test-api-int2`; dieser Lauf ist inzwischen beendet.
  PS1 und die unterbrochene PS5-Lane werden in ihren bestehenden Worktrees
  überprüft und fertiggestellt. PS2–PS4 folgen auf dem geprüften PS1-Commit.

| Paket | Eigentum und Ergebnis | Abnahme / Abhängigkeit |
|---|---|---|
| Symbol-Release | Root integriert die vorbereiteten Assets und gemeinsamen Metadaten-Makros. | Unabhängige Gates, OCR, Manifest, Paketprüfung, Build und Live-Beweis; keine erfundene PDF-/Legenden-Fertigmeldung. |
| SCR-001 / TPL-001 Einstieg | Eine Lane besitzt neue Admin-Übersichten für vorhandene Screen- und Vorlagenziele samt Routenregistrierung, Sidebar und Tests. | Bestehende Rollen-/CSRF-Verträge, echte funktionierende Links, Tabler, 390/820/1440 px; vorhandenen API-Sidebar-Eintrag bei Integration erhalten. Keine neue Migration und keine Platzhalter-Editoren. |
| Backlog-Abgleich | Eine Docs-Lane besitzt ausschließlich `docs/BACKLOG.md`. | Aktueller Status, AGY-Referenz, HugeRTE als Rezepteditor-Prüfkandidat, aktuelle Claude/Codex-Grenzen. |
| Ruff-Bestandsfehler | Eine Lane besitzt ausschließlich `workflow_partial_store.py` und die beiden Komponenten-Katalogtests mit bestehenden Ruff-Befunden. | Verhaltensgleiche Korrekturen, Fixture-Registrierung erhalten, Ruff und passende vorhandene Tests. |

AGYs Analyse wird als Integrations-Abnahmekatalog verwendet: flackerfreier
GET ohne Queryparameter, Datumswechsel auch bei gleicher Wochenrevision,
serverseitiges Datum/Europe-Zurich, erreichbare 404/410 entfernen alte Inhalte,
Wiederanlauf auch nach initialer 404, keine endlose Gültigkeitszusage bei
Offline-Anzeige. Eine Renderprüfung per `set_content` ersetzt keinen echten
Browsernachweis für Skript, CSP und Polling. Generisches FHD/Yodeck bleibt
gemeinsames Ziel; Patientenwoche muss dabei vollständig und lesbar bleiben.

Die vollständige Funktionsliste und nachfolgende Lieferfolge bleiben bestehen.
Die ursprüngliche Claude/Codex-Aufteilung ist historisch;
massgeblich ist die vollständige Übernahme von 01:55. PS5 ist lokal integriert;
der neue Tabler-Stand der vier Public-URLs ist noch nicht produktiv:
`/cafeteria/heute/`, `/cafeteria/wochenangebot/`, `/patienten/heute/` und
`/patienten/wochenplan/`.

| Paket | Verantwortung / Vertragsdateien | Unabhängiger Nachweis |
|---|---|---|
| CAT-001 / wp-40505b9bf3d7 | Eigener WT `component-filters-0906`: Katalog-Store, Komponentenroute, Rendering, Komponenten- und Ländermakro, zugehörige Tests. Keine Sidebar/Base/Settings. | Kombinierte Filter, validierte Querywerte, archivierte/inaktive Daten, kompatible Editor-Auswahl; 390/820/1440 px, GET/Reset/Trefferzahl und bestehendes CRUD. |
| DSP-001 / wp-1183b3cef096 | Eigener WT `global-admin-density-0906`: validierter globaler Settingswert, Route/Registrierung, Tabler-Seite, Sidebar/Base, Dichte-JS/CSS und Tests. Keine Komponenten-/API-/Schemaänderung. | Standard kompakt ohne JS, zwei Browser gleicher globaler Zustand, Rollen/CSRF/ungültige Werte, alte LocalStorage-Werte ignoriert, CSV `data-state` und Pflicht-Hilfen erhalten. |
| API-Inventur / wp-fb3b2cfecee4 | Bestehende A1/B/D/C/A2/F-Lanes nur lesen und übernehmen, wenn Commit und Gates geprüft sind. | Terminalbelege plus aktuelle Prozess-/Worktree-Prüfung; kein Neustart anhand alter Logs oder Quotenmarker. |
| API-Recovery | Fertige Korrekturen A1 `5a5f98b` auf `1631264`, D `6bc1cc7` auf `661eb19`; Übergabe an Claude. | D: `153 passed in 80.18s (0:01:20)`, `GATE_EXIT=0`. A1-Datenbankgate und unabhängige Integration bleiben bei Claude offen. |

Historische Testpaar-Zuordnung: CAT nutzte `test_sdd`, DSP `ui_other`, das kombinierte UI-Gate `test_root`. Daraus folgt keine aktuelle Poolreservierung. API-D-Recovery ist beendet; Codex besitzt seit 01:55 die API-Integration samt Migration 0014/v17 und alle Release-Umschaltungen.

GitNexus meldet hohe Auswirkungen bei gemeinsamem Komponenten-Store/Rendering: bestehende Signaturen und Auswahlpfade kompatibel halten und mitprüfen. Der sachfremde TRUNCATE des ursprünglichen A1-Stands wurde durch Recovery `5a5f98b` entfernt; er ist kein offener Bestandteil des aktuellen Kandidaten.

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

Dateiunabhängige Unterpakete aus verschiedenen Stufen dürfen parallel laufen. Codex verantwortet auch die API-Stufen 2 und 3 samt unabhängigen Gates und Deployment. Gemeinsame Sidebar, Registrierungen, Settings- und Publikationsverträge gehören pro Welle genau einer Lane. Die Tabelle ordnet Abhängigkeiten; sie ist kein Auftrag, alle Arbeit strikt seriell abzuarbeiten.

## Yodeck-Vertrag

Die vier vorhandenen öffentlichen HTTPS-Signage-URLs können als Yodeck-Medium **Web Page** eingebunden werden. Öffentliches HTTP 200 wurde geprüft, nicht die Bedienung eines fremden Yodeck-Kontos. Chromium, Zoom/Auto-adjust und Fallbackbild nach [Yodeck-Webseiten-Dokumentation](https://www.yodeck.com/docs/user-manual/web-pages-introduction/) berücksichtigen.

Gemeinsames Ziel ist 1920×1080; Hochformat zusätzlich prüfen. 4K ist eine separate Ausgabeoption: [Yodeck-Kompatibilität](https://www.yodeck.com/docs/user-manual/raspberry-pi-compatibility/) unterscheidet Pi-4B-RAMvarianten. Patientenwochen müssen auch im FHD-Konzept gut lesbar sein; bei notwendiger Aufteilung bleibt der gesamte Wocheninhalt über nachvollziehbare Seiten/Rotation erreichbar. Kein blosser Zoom eines übergrossen Rasters als Lesbarkeitsnachweis.

Die bestehenden HTML-Seiten besitzen bereits Meta-Refresh 300 Sekunden. Zusätzlich [Player-Refresh](https://www.yodeck.com/docs/user-manual/how-to-set-a-web-page-to-refresh/) bei Einzel-Webseiten prüfen. [Offline-Verhalten](https://www.yodeck.com/docs/user-manual/does-yodeck-work-offline/): serverseitiger Last-Good-Cache ersetzt keine Offline-Datei auf dem Pi; ein freigegebenes Fallbackbild ist separat bereitzustellen/zuordnen. Kein Playerkonto oder externer Bildschirm wird ohne passenden Zugriff als konfiguriert behauptet.

## Fertigstellung und fortlaufende Nachweise

Jedes Paket braucht Quellcommit, unabhängige passende Gates, Manifest/Build und bei UI-Änderungen echten Browser-/Live-Nachweis. Erst danach Status im Backlog aktualisieren. Regelmässig kleine geprüfte Releases ausliefern. Bereits vorhandene Gesamttests nicht pauschal als Nachweis neuer Funktionen verwenden.

Gesamtziel bleibt aktiv, bis sämtliche geforderten Funktionen und ihre Abnahmen nachgewiesen sind. Externe Produkt-/Glossardaten, konkrete Pauli-Exportformate und fachliche Freigaben getrennt von implementierter Import-/Prüffunktion ausweisen; fehlende Daten nicht erfinden. Ein einzelner offener Anschluss hält andere unabhängige Pakete nicht an.
