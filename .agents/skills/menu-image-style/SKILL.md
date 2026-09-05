---
name: menu-image-style
description: Einheitliche Menübilder für Dishboard erzeugen oder erneuern; verbindliche Referenz, Kompositionsprüfung und Herkunftsnachweis.
---

# Einheitliche Menübilder

Diesen Skill vor jeder Menübild-Generierung oder Bildänderung lesen.
Ziel: dieselbe Fotoserie, bei der ausschliesslich das Essen wechselt.

## Verbindliche Referenz

- Datei: `design/menu-images/reference/canonical-reference.jpg`.
- SHA-256: `9bee05b69c5f85a70c82940ec7d1a69f17a53d7e062713483e3472ca8f8b714a`.
- Vor jedem Auftrag Datei und Hash prüfen; keine neue leere Szene erfinden.
- Referenz bei **jedem** Bild als echtes Bildeingabe-Argument übergeben.
- AGY: natives `generate_image`, Parameter `ImagePaths`.
- OpenRouter Image API: `input_references`, Bild als Data-URL.
- Eine Beschreibung des Tellers allein ersetzt die Bildeingabe nicht.

## Fester Stil

- Fotorealistische normale Schweizer Kantinenportion.
- Bildformat 1200 × 896 Pixel, native 1K-Ausgabe mit angefordertem Verhältnis 4:3.
- Keine Streckung oder nachträgliche Änderung der Tellergeometrie.
- Exakt senkrechte Kamera: 90 Grad von oben.
- Derselbe schlichte weisse runde tiefe Keramikteller, mittig bei 50 %/50 %.
- Tellerdurchmesser ungefähr 57 % der Bildbreite, vollständig sichtbar.
- Derselbe warme gebrochen weisse matte Hintergrund.
- Diffuses Tageslicht oben links, weicher dezenter Schatten unten rechts.
- Keine Bestecke, Hände, Servietten, Logos, Schrift oder weitere Gefässe.
- Keine unbenannte Kräutergarnitur oder dekorative Zusatzspeise.
- Suppe kommt in denselben tiefen Teller; **nur benanntes** Brot auf den Rand.
- **Nur benanntes** Apfelmus oder Kompott neben die Hauptspeise auf denselben Teller.
- Keine allgemeinen Brot-/Kompott-Anweisungen für Menüs ohne solche Komponenten.
- Hinweise zu Serviervorschlag oder Allergenen gehören in die Oberfläche, nie ins Bild.

## Komposition und Zuordnung

1. Exakten aktuellen Menütitel und vollständige **geordnete** Komponentenliste laden.
2. Die benannte Hauptspeise und alle Komponenten sichtbar darstellen.
3. Keine fehlenden Rezepturinformationen, Herkunft oder Diätlabels erfinden.
4. Identische Titel **und** Komponenten dürfen ein Bild teilen, auch profilübergreifend.
5. Titel- oder Komponentenänderung macht die bisherige Zuordnung ungültig:
   neu generieren und prüfen; nicht bloss nach Titel oder historischer Menü-ID zuordnen.
6. `design/menu-images/manifest.json` enthält Zuordnung, Status, Abmessungen und Hashes.

## Anbieter und Ausführung

AGY zuerst direkt starten; keine Quoten-Vorabprüfung und keine Sperre aus alten Markierungen.
Nur eine echte Bilddatei beweist erfolgreiche Generierung; Textantworten reichen nicht.
Aktuelle AGY-Anleitung vor Aufruf prüfen; Modell explizit setzen.

Bei tatsächlich gescheitertem AGY-Aufruf ist für dieses Projekt auch **Google über
OpenRouter** vom Nutzer autorisiert. Festes Modell: `google/gemini-3.1-flash-image`.
`provider.only=["google-ai-studio"]`, `allow_fallbacks=false`; kein stiller Anbieterwechsel.
Client: `tools/google_menu_images.py --menu-id <ID>`, Shell immer mit `rtk`.
Er nutzt den bestehenden geschützten Runtime-Zugang; Schlüssel nie ausgeben oder committen.
Preis vor einem neuen Batch aktuell prüfen. Der Batch vom 05.09.2026 ist auf maximal
24 Aufrufe und 3 US-Dollar begrenzt; Belege und Limits nicht löschen, um weiterzulaufen.
Ein neues Batch braucht einen ausdrücklich festgelegten Umfang und Kostenrahmen.

## Prüfung vor Freigabe

- Tatsächliche Datei öffnen und jedes Motiv visuell prüfen.
- Teller, Position, Kamera, Hintergrund und Licht mit der Referenz vergleichen.
- Hauptspeise und jede Komponente prüfen; keine zusätzliche Schrift oder Garnitur.
- Dateiformat anhand echter Bytes prüfen; JPEG nicht als PNG benennen.
- Pixelmasse, SHA-256, Anbieter, Modell, Referenzhash und Kostenbeleg festhalten.
- Fehlerhafte Varianten separat erhalten und als verworfen dokumentieren.
- Erst nach bestandener Sicht- und Dateiprüfung Status `ready` setzen.
- Ohne fertiges Bild keinen erfundenen Dateipfad oder fremden Ersatz zuordnen.

Alle Bilder sind **KI-generierte Serviervorschläge**. Sie beweisen weder tatsächliche
Ausgabe noch Rezeptur, Zutaten, Allergene, Herkunft oder Ernährungslabels.
Diese Kennzeichnung bei der späteren Anzeige beibehalten.
