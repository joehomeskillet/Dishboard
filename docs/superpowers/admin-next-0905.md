# Admin: Menüs, Wochen und Ausdruck

## Entscheidung vom 5. September 2026

Der Nutzer delegiert Konzeptauswahl und Umsetzung und verlangt regelmässige
Deployments. Drei unabhängige Konzepte wurden eingeholt: AGY über
`gemini-3.6-flash-high`, Astra über `gpt-6-astra`, Fable über
`claude-fable-5-1`. Dies ist eine Zusammenfassung, kein Rohtranskript.

Alle drei schlagen eine klar gegliederte Navigation, kompakte Wochenzeilen,
eine Menüsammlung und sichtbare Metadaten vor. Astra wird gewählt: Sein Konzept
passt am besten zum vorhandenen Datenmodell und trennt gespeicherte Menüs,
Prüfung und Veröffentlichung klar. AGYs Vorschlag einer Allergen-Schnittmenge
wird ausdrücklich verworfen: Er könnte deklarierte Allergene verlieren.
Fables Vorschläge zu Formularhierarchie und mobilen Tagesansichten ergänzen
die Umsetzung, soweit sie dieselben bestehenden Abläufe nutzen.

## Lieferfolge und Zuständigkeiten

1. Metadaten sichtbar machen: Release `d20b821`, bereits produktiv. Gespeicherte
   Beschreibungen, Hinweise, Allergene, Labels und Herkunft erscheinen in den
   passenden Ansichten. Fehlende Daten sind als fehlend erkennbar.
2. Menüs: Durchsuchbare, paginierte Sammlung vorhandener Menüvorkommen, mit
   Komponenten, Metadaten und direktem Bearbeitungslink. Keine erfundene
   Rezept-Entität und keine Zusammenfassung allein nach gleichem Titel.
   Owner: `admin-menus-0905`, einschliesslich Navigation und App-Registrierung.
3. Ausdruck: Gespeicherte, ausgewählte Woche über geschützte Admin-Route
   drucken. Cafeteria orientiert sich am bereitgestellten Südhang-PDF:
   A4-Hochformat, Bildkopf, Wochentabelle, Fussbereich. Neue Menüdaten und
   Labels ersetzen Referenzinhalte. Patienten bleiben ohne Preisangaben.
   Owner: `admin-print-0905`, einschliesslich Route und Vorschau-Drucklink.
4. Wochenverwaltung: Wochenliste mit Status, neue leere Woche, bestehende
   Vorwochen-Kopie und Links zu Bearbeiten, Vorschau und Druck. Keine neue
   Archivierungs- oder Löschfunktion. Folgewelle nach Integration der Navigation.
5. Allergen-Vorschläge: Alle 38 bestehenden Menüs bekommen nach Prüfung der
   konkreten Vorschläge ungeprüfte Rezepturhinweise im Entwurf. Vermutungen
   werden nicht als bestätigte Allergene gespeichert oder veröffentlicht.

## Abnahme

## Verbindliche Ergänzungen des Nutzers

- Admin nutzt das bestehende Framework **Tabler** und **Tabler Icons**. Kein
  selbst erfundenes CSS-Framework. Gemeinsame Layouts und Formularbausteine,
  lokal eingebundene, versionierte Assets und Südhang-Thementokens. Die vom
  Nutzer verlinkten Tabler-Skills sind für ihre Komponenten-/Layoutregeln zu
  berücksichtigen; Flask/Jinja bleibt das Anwendungsframework.
- PDF entsteht direkt mit **fpdf2** im Python-Backend. **Beide Profile passen
  jeweils auf eine Seite**: Cafeteria A4 hoch nach Referenz, Patienten eigene
  kompakte A4-Querformatvorlage mit allen sieben Tagen und beiden Mahlzeiten.
  Kein Abschneiden, keine still ausgelassenen Angaben; physisch überlange
  Inhalte führen zu einer verständlichen Fehlermeldung statt einer zweiten Seite.
- Menüs erhalten von **AGY** generierte Serviervorschläge. Gemeinsames Referenzbild
  fixiert Teller, Hintergrund, Kamera, Position und Licht. Ein Projekt-Skill
  dokumentiert diesen Bildstil. Fotos belegen keine Zutaten oder Allergene.
- Claude Code übernimmt Tabler, Fach-Lanes PDF und Datenabläufe; einfache
  Dokumentations-/Asset-Aufgaben gehen an OpenCode mit OpenRouter **Free**.
  Cursor kann abgegrenzte Fixes übernehmen. Keine kostenpflichtigen Fallbacks
  für Free-Aufgaben und keine gleichzeitigen Besitzer derselben Dateien.

## Abnahme der aktuellen Umsetzung

Mobile Admin-Ansichten werden primär für 8–10-Zoll-Tablets optimiert
(Nutzerpräzisierung vom 5. September): 768×1024 und 800×1280 sowie beide
Querformate. Bedienelemente mindestens 44 px, lesbare Inhalte, kein horizontaler
Überlauf. Smartphone-Ansichten bleiben ein zusätzlicher Fallback.

Profil- und Standortgrenzen, Berechtigungen und CSRF bleiben erhalten.
GET-Aufrufe verändern keine Daten. Speichern respektiert bestehende Versionen.
Tests laufen gegen isoliertes PostgreSQL, jeweils eine schwere Test-/Browser-
Ausführung gleichzeitig. Vor Integration folgen unabhängige Diff-Prüfung und
erneute Gates. Druck wird zusätzlich als echtes Browser-PDF geprüft: Format,
Seitenzahl, Lesbarkeit und kein abgeschnittener Inhalt. Produktive Anmeldung
wird mit unverändertem bestehenden Passwort geprüft; keine Passwortrotation.

## Bereits bestätigter Deploy

Release `d20b821892ca665655e56491018f2531029d40bd`, Image
`sha256:17b40008b11db84458738834f7dcd82be0e81eb394d59576f4eae4cb0d6512cc`.
Container läuft und ist healthy. Frischer Live-Nachweis: 282/282 Prüfungen,
30 Seiten, keine Fehler oder nicht verfügbaren Seiten. Beleg liegt unter
`.claude/state/handover-2026-09-05/proof/metadata-d20b821/proof.json` im Haupt-Checkout.
OCR war wegen tatsächlich beobachtetem Provider-HTTP-429 nicht verfügbar;
unabhängige Agent-Prüfung des Metadaten-Diffs war CLEAN, 118 Tests bestanden.
