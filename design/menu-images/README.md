# Einheitliche Menübilder – AGY-Serie vom 05.09.2026

Diese Serie enthält zwölf tatsächlich mit AGYs nativem `generate_image` erzeugte Menübilder und den gemeinsamen leeren Referenzteller. Neun Motive sind visuell freigegeben; drei benötigen eine Korrektur. Zwanzig weitere Motive fehlen wegen eines beobachteten Bilddienst-Limits. Keine vollständige Lieferung behaupten.

## Dateien und Zuordnung

- `reference/canonical-reference.jpg`: verbindliche Bildreferenz für jede weitere Generierung.
- `generated/menu-*.jpg`: unveränderte native JPEG-Ausgaben, jeweils 1200 × 896 Pixel.
- `manifest.json`: alle 32 eindeutigen Kombinationen aus Menütitel und geordneter Komponentenliste, zugeordnet zu den 38 dokumentierten Vorkommen.
- `provenance.json`: tatsächlich verwendete AGY-Aufrufe, Sitzungs-IDs, Referenzparameter und beobachteter Fehler.

`ready` bedeutet visuell geprüftes Bild vorhanden. `needs_revision` bedeutet Bild vorhanden, aber vor Einbindung korrigieren. `pending` hat ausdrücklich keinen Dateipfad. Nur `ready` darf automatisch für die Einbindung angeboten werden.

Die Menü-IDs 77–114 belegen den Datenstand der Woche 31.08.–06.09.2026; sie sind keine langfristigen Rezeptschlüssel. Bei späterer Einbindung immer den exakten Menütitel **und** die vollständige geordnete Komponentenliste vergleichen. Geänderte Menüs dürfen kein unpassendes Bild erben. Identische Kombinationen in beiden Profilen teilen ein Motiv: 81/95, 82/96, 83/99, 84/100, 85/103, 86/104.

## Festgehaltene Bildsprache

Fotorealistischer Serviervorschlag einer normalen Schweizer Kantinenportion. Blick exakt von oben, warmer gebrochen weisser matter Hintergrund, derselbe schlichte weisse runde tiefe Teller, mittig positioniert. Diffuses Licht oben links, weicher Schatten unten rechts. Keine zusätzlichen Gefässe, Bestecke, Hände, Schrift, Logos oder Tischdekoration. Der tiefe Teller soll auch Suppen aufnehmen; benanntes Brot liegt dann auf dem Tellerrand.

Die reale Referenz bestimmt Geometrie und Farbe. Ihr Teller misst ungefähr 57 % der Bildbreite. Der ursprüngliche Prompt verlangte 70–72 %, das Modell erzeugte eine kleinere Darstellung. Die Serie übernimmt bewusst die vorhandene Referenz statt abweichender Neugenerierungen. Angefordert wurde `AspectRatio: 4:3`; tatsächlich geliefert wurden 1200 × 896 Pixel, nicht 1200 × 900. Kein Strecken, Zuschneiden oder Skalieren wurde vorgenommen.

Für **jedes** Menü wurde derselbe Originalpfad über den nativen Parameter `ImagePaths` übergeben. Das wurde anhand der eigenen AGY-Transkripte geprüft. Eine bloss textliche Beschreibung des Tellers ersetzt dieses Referenzbild nicht.

## Sichtprüfung und offene Korrekturen

Alle 13 Dateien wurden einzeln geöffnet und betrachtet. Teller, Platzierung, Kamerawinkel, Hintergrund und Beleuchtung sind über die Serie konsistent; die jeweils benannten Hauptspeisen und Beilagen sind erkennbar. Das ist eine Sichtprüfung, kein Nachweis pixelidentischer Hintergründe.

- Menü 89, Schinken-Käse-Toast: zusätzliche sichtbare Kräuter auf dem Tomatensalat.
- Menü 90, Gemüse-Toast: zusätzliche ganze Kräuterblätter auf dem Tomatensalat.
- Menü 102, Tofu-Rührei: zusätzliche Kräutergarnitur auf Rührei und Kartoffeln.

Diese drei Bilder verletzen die Vorgabe, keine unbenannte Garnitur hinzuzufügen. Sie bleiben `needs_revision`. Neun fertige Motive decken zehn Vorkommen ab; die zwölf vorhandenen Motive insgesamt decken dreizehn Vorkommen ab. Die Bildkorrektur muss ebenfalls über AGY und dieselbe Referenz erfolgen.

## Tatsächlich beobachteter Abbruch

AGY wurde direkt mit `gemini-3.6-flash-high` gestartet, ohne Quoten-Vorabprüfung. Das native Bildwerkzeug nennt im Fehler das Modell `gemini-3.1-flash-image`. Nach dreizehn erfolgreichen Bildern einschliesslich Referenz antwortete es am 05.09.2026 gegen 16:15 UTC mit HTTP 429, `RESOURCE_EXHAUSTED`, `QUOTA_EXHAUSTED`. Gemeldeter Reset: `2026-09-05T21:11:34Z`, entsprechend 23:11:34 Uhr in Zürich. Das ist eine damalige Providerangabe und keine Garantie für spätere Verfügbarkeit.

Die drei parallelen Batches stoppten an den IDs 82, 91 und 108. Batch 91 hatte einen identischen zweiten nativen Versuch, ebenfalls mit 429. Kein anderer Bildanbieter wurde verwendet. Alle vier AGY-CLI-Aufrufe endeten mit Exitcode 0, obwohl die drei Batches unvollständig sind; deshalb gelten ausschliesslich die nachgewiesenen Dateien und Manifestzustände.

## Nutzung

Die Bilder sind **KI-generierte Serviervorschläge**, keine Fotos der tatsächlichen Ausgabe und keine Grundlage für Rezeptur, Zutaten, Allergene, Herkunft oder Ernährungslabels. Diese Unterscheidung muss bei späterer Anzeige erhalten bleiben. Dieses Arbeitspaket ändert weder Menüinhalte noch Veröffentlichung oder Admin-Oberfläche.

Die technische Prüfung umfasst JSON, Zuordnung aller 38 Vorkommen, vorhandene Dateien, JPEG-Dekodierung, Pixelmasse und SHA-256. Anwendungstests, PostgreSQL-Gates, Browserprüfung und Deployment sind für diese reinen Bildartefakte nicht ausgeführt.
