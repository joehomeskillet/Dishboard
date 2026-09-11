# Prüfung des erweiterten Referenzpakets

## Umfang

Geprüft wurden die **isolierten Referenzdateien dieses Pakets**, nicht die Flask-/Tabler-Anwendung. Es wurden keine produktiven Seiten aufgerufen, keine Serververträge getestet und keine Änderungen gespeichert oder veröffentlicht.

| Prüfung | Ergebnis / Grenze |
|---|---|
| Sechs Desktop-Referenzseiten gerendert | Chromium; 1600 × 1100 CSS-Pixel, Pixelfaktor 1,5, vollständige Seite. |
| Zwei mobile Referenzseiten gerendert | Menüübersicht und Wochenplan; 390 × 844 CSS-Pixel, Pixelfaktor 2, vollständige Langaufnahme. |
| Desktop-Sichtprüfung | Sechs Bilder angesehen: Ausrichtung, sichtbare Inhalte, Zustände und Hauptaktionen geprüft. Kein Nachweis über die echte Anwendung. |
| Mobile Sichtprüfung | Obere Ansichten von R1-M und E1-M angesehen; Hauptaktionen des ersten Eintrags sind im ersten 844-Pixel-Fenster sichtbar. |
| Statische Breitenprüfung | Sechs HTML-Referenzen bei 1366 × 768, 768 × 1024, 390 × 844 und 320 × 844 untersucht: kein horizontales Dokument-Overflow, Bilder geladen, je eine Hauptüberschrift. |
| Frühere Referenzen | Neun Ist-Bilder bleiben byteidentisch zur ursprünglichen ZIP-Datei; X1 ebenfalls erhalten. |
| Bildstatus | Acht neue Sollbilder sind ENTWURF. Keine Benutzerfreigabe oder Implementierung behauptet. |
| Nicht enthaltene Sollbilder | E3, E4 und E5 bleiben FEHLT. Mobile Ist-Aufnahmen fehlen. |
| Produkt-/Funktionstests | **Nicht durchgeführt.** Statische Buttons sind kein Nachweis für Speichern, Prüfen, Drucken, Kopieren oder Navigation. |
| Nutzer-/Zugänglichkeitsabnahme | **Ausstehend.** Keine vollständige Tastatur-, Touch-, Kontrast- oder WCAG-Prüfung und kein Test mit unerfahrenen Personen. |
| Seitlicher Menüeditor | Nicht in den neuen Referenzen dargestellt; technisch bedingtes Konzeptziel separat prüfen. |

Die erste 320-Pixel-Prüfung fand ein horizontales Überlaufen der illustrativen Druckvorschau. Die Referenz-CSS wurde korrigiert und alle 24 Grössen-/Seitenkombinationen erneut geprüft. Die abschliessenden Werte stehen in [STATISCHE_LAYOUTPRUEFUNG.json](STATISCHE_LAYOUTPRUEFUNG.json).

Exakte Bildschirm- und Bildgrössen: [RENDER_METADATEN.json](RENDER_METADATEN.json). Paketstruktur-/Link-/Originalprüfung: [PAKETPRUEFUNG.json](PAKETPRUEFUNG.json).

Der Badge „Designentwurf · Beispieldaten“ und die Hinweise auf statische Referenzen kennzeichnen die Lieferartefakte. Sie sind keine zusätzliche Anforderung an die produktive Küchenoberfläche.
