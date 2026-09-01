# Änderungsprotokoll

## Rework vom 1. September 2026

### Fachmodell

- Zwei getrennte Profile eingeführt: `patient` und `staff_guest`.
- Patientenplan auf Montag bis Sonntag, Mittag und Abend erweitert.
- Zwei feste Menüarten für jeden offenen Service: Menü 1 und Vegetarisch.
- Cafeteria auf Montag bis Freitag und Mittag begrenzt.
- Kosten in eigene Tabelle verschoben; Patientenpreise werden durch Datenbankregeln verhindert.
- Schliessungen auf Profil × Datum × Mahlzeit verfeinert.
- Publikationsrevisionen und letzte gültige Playerkopien profilbezogen getrennt.

### Oberflächen und Signage

- Vier feste Player-Routen und getrennte Templates ergänzt.
- Cafeteria-Wochenplayer mit 5 × 2 Menükarten erstellt.
- Patienten-Tagesplayer mit Mittag und Abend erstellt.
- Patienten-Wochenplayer als 4K-Layout erstellt; 1080p nur Vorschau.
- Cafeteria-Geschlossenfläche für Wochenende/Feiertage ergänzt.
- Mobile Tages- und Wochenansichten für beide Profile ergänzt.
- Zwei getrennte Backend-Raster als Prototypen ergänzt.
- Insgesamt 14 primäre Referenzscreenshots erzeugt.

### Daten, CSV und Tests

- Zwei Demo-Snapshots derselben Kalenderwoche erzeugt.
- Getrennte Patienten- und Cafeteria-CSV-Vorlagen samt Beispielen erstellt.
- Vertragsprüfungen für Profilisolation, Kostenverbot, vier Routen und Template-Syntax ergänzt.
- Paketvalidator auf die neue Struktur umgestellt.

### Sicherheit und Betrieb

- Öffentliche Datums- und Profilparameter entfernt beziehungsweise abgewiesen.
- Demo-Konfiguration in Produktion technisch blockiert.
- Demo-Benutzer auf Editor/Publisher begrenzt.
- Rollenmodell von fünf auf drei verständliche Rollen reduziert.
- Alembic-Behauptung entfernt; SQL-Baseline klar benannt.
- Redis-Healthcheck liest das Secret ohne Passwort im Healthcheck-Kommando.

### Dokumentation

- SDD vollständig auf zwei Publikationskanäle umgebaut.
- Umsetzung der Grok-Kritik und offene Live-Nachweise separat dokumentiert.
- Abnahmecheckliste, CSV-, Entra-, Design- und Betriebsdokumentation aktualisiert.
