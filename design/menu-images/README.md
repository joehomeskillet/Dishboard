# Einheitliche Menübilder – AGY-Serie vom 05.09.2026

Alle 38 dokumentierten Menüvorkommen sind mit 32 visuell geprüften Motiven abgedeckt: neun aus AGYs nativem `generate_image`, 23 nach ausdrücklich erlaubtem Wechsel zu Google über OpenRouter. Der gemeinsame leere Referenzteller bleibt unverändert. Vier verworfene Varianten sind separat im Manifest dokumentiert und dürfen nicht angezeigt werden.

## Dateien und Zuordnung

- `reference/canonical-reference.jpg`: verbindliche Bildreferenz für jede weitere Generierung.
- `generated/menu-*.jpg`: ursprüngliche native AGY-JPEGs, jeweils 1200 × 896 Pixel; drei verworfene Varianten bleiben als Nachweis erhalten.
- `openrouter/`: native Google-JPEGs und Kosten-/Promptbelege; eine verworfene Variante trägt `-rejected` im Namen.
- `manifest.json`: alle 32 eindeutigen Kombinationen aus Menütitel und geordneter Komponentenliste, zugeordnet zu den 38 dokumentierten Vorkommen.
- `provenance.json`: tatsächlich verwendete AGY-Aufrufe, Sitzungs-IDs, Referenzparameter und beobachteter Fehler.

`ready` bedeutet visuell geprüftes Bild vorhanden. Alle 32 aktiven Zuordnungen sind jetzt `ready`. Bei späteren Ergänzungen bedeutet `needs_revision`: vor Einbindung korrigieren; `pending` hat keinen Dateipfad. Nur `ready` darf automatisch für die Einbindung angeboten werden. `retired_assets` enthält ausschliesslich verworfene frühere Varianten.

Die Menü-IDs 77–114 belegen den Datenstand der Woche 31.08.–06.09.2026; sie sind keine langfristigen Rezeptschlüssel. Bei späterer Einbindung immer den exakten Menütitel **und** die vollständige geordnete Komponentenliste vergleichen. Geänderte Menüs dürfen kein unpassendes Bild erben. Identische Kombinationen in beiden Profilen teilen ein Motiv: 81/95, 82/96, 83/99, 84/100, 85/103, 86/104.

## Festgehaltene Bildsprache

Fotorealistischer Serviervorschlag einer normalen Schweizer Kantinenportion. Blick exakt von oben, warmer gebrochen weisser matter Hintergrund, derselbe schlichte weisse runde tiefe Teller, mittig positioniert. Diffuses Licht oben links, weicher Schatten unten rechts. Keine zusätzlichen Gefässe, Bestecke, Hände, Schrift, Logos oder Tischdekoration. Der tiefe Teller soll auch Suppen aufnehmen; benanntes Brot liegt dann auf dem Tellerrand.

Die reale Referenz bestimmt Geometrie und Farbe. Ihr Teller misst ungefähr 57 % der Bildbreite. Der ursprüngliche Prompt verlangte 70–72 %, das Modell erzeugte eine kleinere Darstellung. Die Serie übernimmt bewusst die vorhandene Referenz statt abweichender Neugenerierungen. Angefordert wurde `AspectRatio: 4:3`; tatsächlich geliefert wurden 1200 × 896 Pixel, nicht 1200 × 900. Kein Strecken, Zuschneiden oder Skalieren wurde vorgenommen.

Für **jedes** Menü wurde dasselbe Originalbild als echte Bildeingabe übergeben: AGY verwendet `ImagePaths`, OpenRouter `input_references` mit den Base64-kodierten Referenzbytes. Die eigenen AGY-Transkripte, Clientprüfung und OpenRouter-Belege dokumentieren dies. Eine bloss textliche Beschreibung des Tellers ersetzt dieses Referenzbild nicht.

## Sichtprüfung und verworfene Varianten

Alle 37 Bilddateien einschliesslich Referenz und verworfener Varianten wurden einzeln geöffnet und betrachtet. Teller, Platzierung, Kamerawinkel, Hintergrund und Beleuchtung sind über die freigegebene Serie konsistent; die jeweils benannten Hauptspeisen und Beilagen sind erkennbar. Das ist eine Sichtprüfung, kein Nachweis pixelidentischer Hintergründe.

- Menü 89, Schinken-Käse-Toast: zusätzliche sichtbare Kräuter auf dem Tomatensalat.
- Menü 90, Gemüse-Toast: zusätzliche ganze Kräuterblätter auf dem Tomatensalat.
- Menü 102, Tofu-Rührei: zusätzliche Kräutergarnitur auf Rührei und Kartoffeln.

Diese drei AGY-Varianten wurden durch geprüfte Google/OpenRouter-Bilder ersetzt. Zusätzlich wurde der erste OpenRouter-Versuch für Menü 108 verworfen: Er enthielt Text auf dem Teller sowie unbenanntes Brot und Fruchtpüree. Eine ausdrücklich erlaubte gezielte Neugenerierung zeigt nur Kichererbsen-Eintopf, Kartoffelwedges und Marktgemüse, ohne Schrift. Alle vier verworfenen Dateien bleiben aus den aktiven Zuordnungen ausgeschlossen.

## Tatsächlich beobachteter Abbruch

AGY wurde direkt mit `gemini-3.6-flash-high` gestartet, ohne Quoten-Vorabprüfung. Das native Bildwerkzeug nennt im Fehler das Modell `gemini-3.1-flash-image`. Nach dreizehn erfolgreichen Bildern einschliesslich Referenz antwortete es am 05.09.2026 gegen 16:15 UTC mit HTTP 429, `RESOURCE_EXHAUSTED`, `QUOTA_EXHAUSTED`. Gemeldeter Reset: `2026-09-05T21:11:34Z`, entsprechend 23:11:34 Uhr in Zürich. Das ist eine damalige Providerangabe und keine Garantie für spätere Verfügbarkeit.

Die drei parallelen AGY-Batches stoppten an den IDs 82, 91 und 108. Batch 91 hatte einen identischen zweiten nativen Versuch, ebenfalls mit 429. Alle vier AGY-CLI-Aufrufe endeten mit Exitcode 0, obwohl die drei Batches unvollständig waren; deshalb gelten ausschliesslich nachgewiesene Dateien und Manifestzustände. Danach erlaubte der Nutzer ausdrücklich Google über OpenRouter, womit die Serie vervollständigt wurde.

## Google über OpenRouter und Kosten

`tools/google_menu_images.py` verwendet ausschliesslich die Python-Standardbibliothek, das Modell `google/gemini-3.1-flash-image` und den festgelegten Anbieter `google-ai-studio`; automatische Fallbacks sind deaktiviert. Der bestehende geschützte Runtime-Zugang wird intern wie beim installierten `or-chat` geladen. Schlüsselwerte werden weder ausgegeben noch in Artefakten gespeichert.

Die [OpenRouter Image API](https://openrouter.ai/docs/guides/overview/multimodal/image-generation) liefert Bildbytes und Nutzungsgebühren. Aktueller [Modelltarif](https://openrouter.ai/google/gemini-3.1-flash-image): 60 US-Dollar je Million Bildtokens; Google nennt [1120 Tokens für ein 1K-Bild](https://ai.google.dev/gemini-api/docs/pricing#gemini-3.1-flash-image), entsprechend 0,0672 US-Dollar Bildoutput plus Eingabe/Text. Die tatsächlichen 24 Aufrufe dieser Serie kosteten zusammen **1,643154 US-Dollar**, einschliesslich der verworfenen und korrigierten Variante 108. Alle Einzelbelege liegen unter `openrouter/`.

Der Client sperrt gleichzeitige Aufrufe, schützt bereits fertige Motive, verhindert unbeabsichtigte Doppelaufrufe und stoppt bei ungeklärten Ergebnissen. Vor jedem Request wird der bisherige Betrag plus 0,30 US-Dollar Reserve gegen die Grenze von 3 US-Dollar geprüft. Das freigegebene Limit beträgt 24 Aufrufe, davon einer für die Korrektur von Menü 108. Es ist vollständig genutzt; für weitere Batches Limits und Belege nicht löschen oder still zurücksetzen.

## Nutzung

Die Bilder sind **KI-generierte Serviervorschläge**, keine Fotos der tatsächlichen Ausgabe und keine Grundlage für Rezeptur, Zutaten, Allergene, Herkunft oder Ernährungslabels. Diese Unterscheidung muss bei späterer Anzeige erhalten bleiben. Dieses Arbeitspaket ändert weder Menüinhalte noch Veröffentlichung oder Admin-Oberfläche.

Der dauerhafte Stil-Skill liegt unter `.agents/skills/menu-image-style/SKILL.md`. Die technische Prüfung umfasst JSON, Zuordnung aller 38 Vorkommen, JPEG-Dekodierung, Pixelmasse, SHA-256, Kostenaddition und den Ausschluss verworfener Varianten. Für den Client wurden Ruff, Mypy, Bandit und Offlineprüfungen der Provider-/Referenzbindung, Budget- und Duplikatsperren sowie redaktierter Fehler durchgeführt. Der zusätzliche Ruff-Sicherheitslauf meldet S310 für `urllib.request.Request`; der URL ist festes HTTPS und Weiterleitungen sind blockiert. Anwendungstests, PostgreSQL-Gates, Browserprüfung und Deployment liegen ausserhalb dieses Bildarbeitspakets.
