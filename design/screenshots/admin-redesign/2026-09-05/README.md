# Admin-Redesign: Vorher-/Nachher-Belege vom 5. September 2026

Die Aufnahmen dokumentieren den ausgelieferten Admin-Workflow für Cafeteria und Patienten. Produktions-Menüs wurden für die Aufnahmen nicht verändert.

| Verzeichnis | Herkunft und Stand | Inhalt |
| --- | --- | --- |
| `before/` | Authentifizierte Produktion auf `082b815ff3cb928b26724bddc9d22648675338a2`, vor Phase-2-Polish | 24 Bilder und `proof.json`: beide Profile, Übersicht, Menüeditor, Vorschau, Katalog, Komponentendetail und Kopieren |
| `after/` | Authentifizierte Produktion auf `3d5fd951cb11dc5f5c0fe01133a1ef4452184540`; geprüfter Quellstand `d81010dc46f526331806d62e7c23a0cd23f21824` | 30 Bilder und `proof.json`: gleiche Seiten plus leerer CSV-Import und beide CSV-Vorschauen |
| `csv-local/` | Isolierte lokale Fixtures der CSV-UI-Welle, deren Umsetzung als `3e7edf4` geliefert wurde | 16 explizit mit `before-`/`after-` benannte Bilder: leer, ungültig und beide Profilvorschauen |

Viewports: 390×844 und 1440×1100. Die Admin-Aufnahmen sind vollständige Seiten; ihre tatsächliche PNG-Höhe kann deshalb über der Viewporthöhe liegen. Die Dateinamen nennen den Viewport. Die separaten 18 Paketbilder unter `../../live/` haben dagegen exakt die im dortigen `INDEX.json` angegebenen Pixelmaße und decken zusätzlich Login, öffentliche Seiten sowie Signage ab.

`proof.json` enthält Zeitstempel, Seitenstatus, Bildprüfsummen und die Ergebnisse der tatsächlich ausgeführten Checks. Vorher: 216 Checks. Nachher: 282 Checks, keine Fehler, keine fehlende Abdeckung und keine von null abweichende Seitendiagnose. Die Größenprüfung im Helper ist eine Diagnose; die unabhängige Quellen-/Bildprüfung und die Browser-Vertragstests ergänzen sie.

Der vollständige Integrationstest auf `d81010d` ergab `2599 passed, 15 skipped, 22 warnings in 382.79s`; Prozessende und `GATE_EXIT` waren 0. Die 15 Skips betreffen ausdrücklich aktivierbare Restore-/Compose-Proben. Die bereits geprüfte Schema-Migration wurde in dieser UI-Welle nicht geändert.

Unabhängiger lokaler Review: ursprünglicher Brand-Überlauf nach `79a15db` geschlossen; keine offenen Befunde im geprüften Umfang. OCR/Nebius sowie externe Gemini-/Claude-Designpasses waren providerbedingt nicht verfügbar und werden nicht als bestanden ausgewiesen. Der Stock-Designvalidator enthält Scandi-spezifische Vorgaben; die visuelle Abnahme wurde anhand des Dishboard-Vertrags durchgeführt.

Es sind keine Passwörter, Session-Cookies, Browser-Traces oder ausgefüllten Loginformulare abgelegt. CSV-Nachher-Belege verwenden echte Preview-Uploads; der Produktionsimport wurde nicht ausgeführt.
