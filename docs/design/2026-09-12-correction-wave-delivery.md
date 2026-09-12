# Dishboard-Korrekturwelle: Lieferstand

Stand: belegter Live-Release `6af59e77f250712b962079cbbf5ca576dfc8bad9`, Schema 30.
Diese Notiz ergänzt die ursprüngliche Übergabe; sie erklärt die sieben
`MP-UI-KORREKTUR-*`-Statuswerte in `surfaces-wps.json`. `DEPLOYED` belegt die
Auslieferung. Eine vollständige fachliche Abnahme (`ACCEPTED`) wird nicht behauptet.

## Belegte Auslieferungen

| Release | Revision | Ergebnis und unabhängige Gates |
|---|---|---|
| Stufe 9 | `7fbbfbc2a7950e8c9648edbe53c8143828785c30` | Wochenplan, Rezeptseiten und bisherige UI-Korrekturen ausgeliefert; Gate9-Rücklink korrigiert, Root 19 Tests grün. |
| Stufe 10 | `301aea6af0526393ba80c9fc2f8bc3217f8e98ad` | Sichtbarer Veröffentlichungsstatus und A04: Wochen-/Ausgabefehler erhalten Eingaben; Root 6 + 36 Tests grün. |
| Schema 29 und Beispielimport | `057d44d5081a3cf167a19598d57680590bd8f0ca` | Schema 25 → 29; 100 Zutaten, 61 Rezepte (29 Zubereitungen + 32 Gerichte), 32 Gerichtvorlagen, 3 Lagerorte. Root-Abschlussgate 10 Tests, Menübindung/Mobil 14 Tests grün. |
| Folgekorrekturen | `bb987b24f6ae1819c5b8db95cf1ff4f809076ec7` | SEC003 mit aktions-/bereichsgebundenem CSRF (Root 23 Tests) und Editor-Fokus nach gewählter Eingabeart (Root 2 Tests) ausgeliefert. |
| Schema 30 und API-Rechte | `35da76c3e66f4b246e38d68d2ef9748bdce4d62a` | SEC002/005, UX03/04 und TEST01 (`3175e79` plus API-Merge-Fix): Root 11 Sicherheits-/Vertragstests und 4 UI-Fälle grün. UX06/13 (`e87d985`) ebenfalls ausgeliefert. |

Zu jeder Revision sind Deployment und gesundes Image belegt; `/health/ready`,
`/cafeteria/heute/` und `/patienten/heute/` antworteten mit HTTP 200.
Stufen 9/10 liefen auf Schema 25; die ältere Übergabeangabe Schema 27 war falsch.
Belegtes Image des Schema30-Releases `35da76c`:
`sha256:b3fb2ee3a5faa79ce356639f19ca2cca30fc51d50139c2f7c3b0bb0ca35bc733`.

Schema29-Backup: `cafeteria-20260912T202421Z.HglIma.dump`, SHA-256-Seitendatei
geprüft. Echte isolierte PostgreSQL-18.6-Wiederherstellung erfolgreich, nachdem
`pgcrypto` für die Probe installiert war. Erster Probeversuch ohne diese
Voraussetzung scheiterte; keine Produktionsauswirkung. Rücknahme verlangt
passendes vorheriges Image und Datenbankwiederherstellung zusammen.

Vor Schema 30 wurde `cafeteria-20260912T204232Z.eFboEI.dump` mit SHA-Nachweis
gesichert. Isolierte Wiederherstellung bestätigte Schema 29, 61 Rezepte,
32 Vorlagen, 100 Zutaten und 3 Lagerorte. Schema30-Image ist gesund, Ready meldet
Schema 30, beide Tagespläne HTTP 200, Publikationen weiterhin 4. Deploytimer ist
wieder aktiv. Vor der Migration waren keine Produktions-API-Schlüssel vorhanden.

Importe liefen über vorhandene native Dienste mit bestehendem Admin-Akteur.
Wiederholung übersprang beide Rezeptbatches; Vorlagenwiederholung erzeugte nichts
und übersprang 32 Vorlagen. 29 vorbereitete Rezeptverknüpfungen sind erhalten.
Aktive Lagerorte: Trockenlager, Kühlraum, Tiefkühler. Vier bestehende aktive
Publikationen blieben erhalten. Rezepte bleiben ungeprüfte Entwürfe; keine neuen
Allergendeklarationen oder Testpublikationen wurden erzeugt.

## Ausgelieferte Folgepakete und funktionaler Abschluss

Root hat den funktionalen Abschluss der Korrekturwelle mit Live-Release
`6af59e77f250712b962079cbbf5ca576dfc8bad9` bestätigt: seit 2026-09-12 23:05 CEST
gesund (`healthy`), einschließlich aller vier zuletzt gemergten Folgepakete.
Die unten aufgeführten offenen Nachweise bleiben davon unberührt.

| Paket | Belegter Lieferstand |
|---|---|
| TEST03/04/08 | DEPLOYED `6af59e7`: Native Benutzer-/CSV- und UI-Vertragstests (`d6fcd65`), Root 8 Tests grün. |
| BUG02 | DEPLOYED `6af59e7`: Semantische Recovery-Sections (`1c7deb7`), Root 19 Tests grün. Originalfelder einschließlich Duplikaten, CSRF/CAS und Rezeptpins erhalten. |
| UX12 | DEPLOYED `6af59e7`: Konto-Begriffe (`b3cbc42`), Root 3 Tests grün. |
| TEST05 | DEPLOYED `6af59e7`: Branding-NoJS-Fehlerfall (`9517648`), Root 1 Test grün. |

Delegierte API-Entscheidung: Bestehende Schlüssel behalten bisherige Kanalrechte
und Ablaufdaten. Neue Schlüssel wählen Cafeteria, Patienten oder beide ausdrücklich;
Ablaufdatum ist Pflicht, Vorschlag 30 Tage, Höchstdauer 90 Tage. Unbefristete alte
Schlüssel werden sichtbar gekennzeichnet. Umsetzung ist mit Schema 30 ausgeliefert;
Verhalten bestehender Schlüssel ist durch Tests belegt, nicht durch vorhandene
Produktionsschlüssel.

## Offene Nachweise und Betriebsregeln

- OCR-Provider wiederholt HTTP 429; kein abgeschlossenes OCR-Ergebnis und kein
  behauptetes CLEAN. Unabhängige Root-Diffprüfung und gezielte Sprint-Gates sind belegt.
- GitNexus-Worktree-Indizes fehlen teilweise; betroffene automatische Checks sind
  nicht bestanden, sondern nicht verfügbar.
- Authentifizierter Live-Browsernachweis fehlt: Chromium-MCP scheiterte zweimal an
  der Root-Sandbox. Lokale Browser-/Auth-Gates und Produktions-HTTP/SQL sind eigene,
  belegte Nachweise. Anonyme Admin-Zugriffe lieferten erwartete HTTP 401.
- Vollständige fachliche/UI-Matrix, tatsächlicher Yodeck-Player und Küchendruck
  werden aus diesen Sprint-/HTTP-Nachweisen nicht als abgenommen abgeleitet.
- Keine fremden Screenshot-Baselines übernommen. Nur saubere, nachweislich gemergte
  und nicht mehr benutzte Wellen-Worktrees dürfen separat bereinigt werden.
- Nutzerentscheidung: Temporär gestoppte Container bleiben vorerst gestoppt.
  Keine Wiederstarts ohne neue Freigabe.

Belegquellen auf dem Host: `/nvmetank1/projects/rag-stack/.claude/reports/wp-release-schema29-0912.md`
und `/nvmetank1/projects/menuplan/.claude/worktrees/ui-integration-0911/.claude/state/orchestrator-0912.md`.
Schema30-Live-Beleg zusätzlich durch aktuelle Root-Meldung mit voller Revision,
Image-ID, Backup-/Restore-Nachweis und HTTP-/Schema-Ergebnissen bestätigt.
Nachfolgende Releases benötigen jeweils neuen Live-Beleg, bevor diese Notiz
fortgeschrieben wird.
