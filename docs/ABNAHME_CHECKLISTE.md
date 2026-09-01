# Abnahme-Checkliste

**Statuswerte:** ☐ offen · ◐ technisch geprüft · ☑ fachlich abgenommen

## Fachmodell und Inhalte

| Prüfung | Erwartung | Status |
|---|---|:---:|
| Patientenwoche | Montag bis Sonntag vorhanden | ☐ |
| Patientenmahlzeiten | Jeder offene Tag enthält Mittag und Abend | ☐ |
| Zwei Menüarten | Jeder offene Service enthält Menü 1 und Vegetarisch | ☐ |
| Patientenkanal | Keine Kosteninformation in Formular, HTML, JSON, CSV, Druck oder Snapshot | ☐ |
| Cafeteriawoche | Nur Montag bis Freitag | ☐ |
| Cafeteriamahlzeit | Nur Mittag | ☐ |
| Cafeteriakosten | Mitarbeitende und Externe je Menükarte sichtbar | ☐ |
| Schliessungen | Zustand wird je Profil, Datum und Mahlzeit erfasst | ☐ |

## Website, Mobile und Druck

| Prüfung | Erwartung | Status |
|---|---|:---:|
| Patienten Mobile heute | Mittag und Abend; je zwei Menüarten; keine Kosteninformation | ◐ |
| Patienten Mobile Woche | Mo–So vertikal lesbar; keine Überlagerung | ◐ |
| Cafeteria Mobile heute | Zwei Menüarten und beide Kostenansätze | ◐ |
| Cafeteria Mobile Woche | Mo–Fr, keine Abend-/Wochenendzeilen | ◐ |
| Patienten Druck | Mo–So, Mittag/Abend, zwei Menüarten | ☐ |
| Cafeteria Druck | Mo–Fr, Mittag, Kostenansätze | ☐ |

## Digital Signage

| Prüfung | Erwartung | Status |
|---|---|:---:|
| Cafeteria Tag | 1920 × 1080, zwei Karten, Kosten, kein Scrollen | ◐ |
| Cafeteria Sonntag | Vollfläche geschlossen; kein Freitag- oder Patienten-Fallback | ☐ |
| Cafeteria Woche | 5 × 2 Karten, Mo–Fr, Preise, 1920 × 1080 | ◐ |
| Patienten Tag | Mittag und Abend, je zwei Optionen, 1920 × 1080 | ◐ |
| Patienten Woche | 7 × 2 Mahlzeitenblöcke, je zwei Optionen, 3840 × 2160 | ◐ |
| Profilisolation | Kein Player enthält Daten des anderen Profils | ☐ |
| Revisionsgleichheit | Tag/Woche je Profil melden dieselbe Revision | ☐ |
| Fehlerbetrieb | Letzte gültige Revision desselben Profils wird angezeigt | ☐ |
| Aktualisierung | Standard 300 Sekunden | ☐ |

## Datenbank und Import

| Prüfung | Erwartung | Status |
|---|---|:---:|
| Cafeteria + Abend | Speicherung wird abgelehnt | ☐ |
| Cafeteria + Wochenende | Speicherung wird abgelehnt | ☐ |
| Patient + Kosten | Speicherung/Import/Publikation wird abgelehnt | ☐ |
| Unvollständige Menüarten | Publikation wird abgelehnt | ☐ |
| Patienten-CSV | 28 Zeilen; keine Kostenspalten | ◐ |
| Cafeteria-CSV | 10 Zeilen; zwei Kostenspalten | ◐ |
| Publikationsisolation | Cafeteriapublikation ändert Patientenrevision nicht | ☐ |

## Sicherheit und Betrieb

| Prüfung | Erwartung | Status |
|---|---|:---:|
| Entra Login | Nur zugewiesene Personen/Gruppen | ☐ |
| Rollen | Editor, Publisher mit Editierrecht, Admin | ◐ |
| Demo in Produktion | Anwendung verweigert den Start | ◐ |
| CSRF | Jeder implementierte Schreibpfad geschützt | ☐ |
| Query-Parameter | Signage/API lehnen Parameter ab | ◐ |
| Secrets | Keine Secrets in Git, `.env`, Kommandos oder Logs | ☐ |
| Compose | Build und alle Healthchecks auf Zielhost erfolgreich | ☐ |
| Backup | Dump, Hash, externe Kopie | ☐ |
| Restore | Wiederherstellung in separates Testsystem | ☐ |
| 4K-Sichttest | Patienten-Woche aus realer Distanz lesbar | ☐ |
| Küche | Mindestens zwei reale Wochen erfasst und freigegeben | ☐ |

Eine fachliche Freigabe ist erst zulässig, wenn alle MUSS-Prüfungen mit Testnachweis dokumentiert und von Küche sowie ICT unterzeichnet sind.
