# Listenfamilie — Vergleich der administrativen Listen

Gemessen 2026-09-28T00:38:16+00:00 gegen `docs/design/2026-09-26-icon-first-simplification-spec.md` (§3.2 Aktionsbudget, §4 gemeinsames Listenmuster, §5 Symbolbuttons; Abnahme UI-02, UI-03, UI-04, UI-05, UI-24).
Fett markiert ist jeder Wert, der von der häufigsten Ausprägung dieser Messgrösse abweicht.
Typografie wird nur zwischen vorhandenen Textrollen verglichen; fehlende Kopfzeilen zählen nicht als Abweichung. Kopf-Hintergrund, Kopf-Höhe und Linkstatus bleiben Messwerte, gehören aber nicht zur Schrift-Signatur. Abweichende Linkfarben zählen weiterhin.
Geschlossene Überlaufmenüs und Bestätigungsdialoge (§5.4) sind nicht geöffnet und zählen nicht als sichtbarer Text.

Seiten: 41. Listenblöcke bei 1440×900: 82.

## Zusammenfassung

- Seiten mit Buttontext in Zeile oder Kopf: keine
- Seiten mit Karte je Zeile: keine
- Seiten mit mehr als zwei Zeilenaktionen: keine
- Seiten mit abweichender Kopf-, Haupt- oder Sekundärtypografie: keine

## Sichtprüfung und verbleibende Arbeit (2026-09-28, MP-LIST-AUDIT-0928)

**Evidenzgrenze:** Produktcode `0b6c40f07ba38e95e91b36c602db2e19e68d35b7`
(Release 18), isolierte PostgreSQL-/Redis-Fixtures `worker-test-api3`, Rolle
`Cafeteria.Admin`. Das sind keine Produktionsaufnahmen. 41 Seiten wurden bei
1440×900 und 390×844 geladen und fotografiert. Der Desktop-Kontaktbogen wurde
vollständig gesichtet; auffällige Ansichten zusätzlich in Einzelbildern, mobil
Wochenplan Patienten, Vorlagen, Bereiche/Zeiten, Rezepte, Küchenkalender,
Kochbuch, Kalkulation und Bildschirme. Nicht alle 82 Aufnahmen wurden einzeln
in voller Auflösung beurteilt. Die unten genannten Befunde sind keine
appweite WP6-Abnahme.

Lokale Aufnahmen bleiben unter `/var/tmp/list-audit-0928-evidence/`
(Kontaktbogen `contact-sheet.png`, Einzeldateien `<slug>-<breite>x<höhe>.png`).
Messmatrix: `/var/tmp/list-audit-0928-report-final/test_list_family_across_admin_0/list-family-measurements.json`.
JUnit: `/var/tmp/list-audit-0928-report-final.xml`. Diese synthetischen
Aufnahmen wurden nicht als neue Screenshot-Baselines eingecheckt.

| Ansicht / Evidenz-Slug | Sichtbarer Befund | Nächstes begrenztes Paket |
|---|---|---|
| API-Schlüssel / `api-schluessel` | „Widerrufen“ und „Mehr“ stehen weiterhin ausserhalb eines Bestätigungsdialogs als Buttontext; leerer Überlauf in beiden Breiten. | Bereits paralleles API-Paket; danach auf integrierter Revision erneut messen. |
| Rezepte / `rezepte` | „Weitere Filter“ mit Suchsymbol und separater Filterknopf ergeben zwei Einstiege. Statuskarte „Filtern / Aktiv“ wiederholt den Normalzustand. Desktop-Zeile beginnt erst etwa bei y=286; mobil bei y=510. | Einen Filtereinstieg herstellen, Statuskarte entfernen; vorhandene Filter/Formularverträge erhalten. |
| Wochenplan Patienten / `wochenplan-patienten` | Kopf bündelt „28 Menüs: Allergenangaben nicht erfasst“ und „14 Mahlzeiten: Zeiten nicht eingetragen“. Trotzdem grosse gelbe Allergenwarnung je Menü und Zeitwarnung je Mahlzeit. „Offen“ wiederholt sich. Desktop nur zwei volle Tagesblöcke, mobil erster Tag ab etwa y=449. | Gemeinsame Warnungen wirksam bündeln und Tagesanatomie verdichten; unbekannt bleibt unbekannt, individuelle Probleme erreichbar halten. |
| Menüs Patienten / `menues-patienten` | Kopf zählt 24 offene Prüfungen und 24 fehlende Allergenangaben; jede sichtbare Zeile wiederholt dieselbe gelbe Allergenwarnung. Acht zweizeilige Datensätze passen bereits auf Desktop. | Wiederholungen reduzieren, korrekte Zählung und Datensatzbezug erhalten. |
| Vorlagen / `vorlagen` | Vier Kopfkarten; „Standard Aktiv“ dreimal. Weiter unten derselbe aktive Standard erneut als Badge, Standardname und Versionsangabe wiederholt. Erklärung zu öffentlichen Druckansichten doppelt. Mobile erste Bildschirmhöhe enthält nur Kopfkarten, Datum und Tabs. | Kopf auf Wochenkontext plus relevante Abweichung begrenzen; Standarddaten und Erklärungen deduplizieren. Der Audit-Hook öffnet hier bewusst Vorlagenkataloge und beide Profilpanels. |
| Bereiche & Zeiten / `bereiche-zeiten` | Vier Kopfkarten, davon zwei Zeitwarnungen; dieselben Warnungen nochmals in Bereichszeilen. Grosse Bearbeitungsüberschriften in einzelnen Einstellungscontainern. Erste Tabellenzeile etwa y=314 Desktop, y=635 mobil. | Bereich/Zeitzone kompakt darstellen; gruppierte Warnung mit 5/14 fehlenden Zeiten erhalten; Einstellungen ruhiger gliedern. |
| Kochbuch / `kochbuch` | „Status Aktiv“ als eigene Kopfkarte und nochmals Aktiv-Badge im Formular; daneben „0 Rezepte“ als grosse gelbe Karte. Rezeptzuordnung erst etwa y=449 Desktop / y=652 mobil. | Redundanten Normalstatus entfernen; leere Zuordnung fachlich korrekt, kompakter anzeigen. |
| Bildschirme / `bildschirme` | Zwei Kopfkarten wiederholen die Standard-Vorlage; „Vorgabe“ erscheint nochmals in den jeweiligen Listenzeilen. | Normalstatus an einer Stelle zeigen, Liste in den Vordergrund stellen. |
| Kalkulation / `kalkulation` | Im gemessenen Ergebniszustand keine redundante Kopf-Statuskarte mehr. Unvollständigkeit wird oberhalb der Tabelle erklärt und an der betroffenen Zutat markiert. Erste Ergebniszeile etwa y=405 Desktop / y=720 mobil; Formular nimmt viel Platz ein. | Dichte separat prüfen. Erklärung „fehlender Preis oder fehlende Umrechnung, nicht als 0“ nicht als redundanten Normalstatus entfernen. |
| Küchenkalender / `kuechenkalender` | September zeigt „+3 weitere“ bzw. „+1 weitere“; exakte versteckte Anzahl und Expansion wurden hier nicht geprüft. Hervorhebung von „Heute“ ist Zustandsmarkierung. Mobil lange Inhaltsblöcke pro Tag. | Eigenes Zähl-/Aufklapp-Gate mit mehreren Mahlzeiten, Gerichten und Anlässen; aktuelle Tagesmarkierung erhalten. |

### Messkorrekturen und Grenzen

- 22 vorhandene Tabellenköpfe besitzen dieselbe Schrift (12px, Gewicht 500,
  uppercase, `rgb(89, 98, 115)`), Hintergrund und Höhe (33px). 60 Blöcke haben
  keine Kopfzeile. Fehlende Rollen sind keine Typografieabweichung; Geometrie
  bleibt in der Matrix sichtbar. Unterschiedliche Kopfgeometrie ist durch
  einen synthetischen Regressionstest ausdrücklich getrennt von Schrift geprüft.
- Link-/Nicht-Link-Status bei identischer Schriftfarbe ist keine abweichende
  Typografie. Tatsächlich andere Grösse, Gewicht oder Farbe, einschliesslich
  anderer Linkfarbe, werden weiterhin erkannt; Regressionstest belegt alle drei
  Textrollen. 18 alte Abweichungscodes fallen damit weg, sechs bekannte Codes
  für Rezepte/API bleiben. Kein neuer Code wurde akzeptiert.
- `.print-screen-row` wird nun mitgemessen (82 statt 81 Desktop-Blöcke).
  Bei Konto-/Ausgabe-Wrappern wird die innere `.admin-list-row` für Linien und
  Schatten betrachtet. Ein `border-bottom: 0` beweist allein keinen fehlenden
  Trenner: letzte/einzige Zeile, Rahmen und andere Kanten separat prüfen.
  Sechs gemessene Blöcke haben aktuell 0px unten: zwei Bestellübersichten und
  vier Vorlagenblöcke. Das parallele Listenhüllen-Paket hat die zwei Bestell-
  Übersichten als fehlerhafte `:last-child`-Anwendung bestätigt; drei einzelne
  Druckvorlagen brauchen keinen Zwischenraum-Trenner, dem Bildschirmvorlagen-
  Block fehlt die gemeinsame Listenanatomie. Dessen Produktkorrekturen sind
  nicht Bestandteil dieser Messbasis. Ein vom CSS gemeldeter `box-shadow`
  kann vollständig transparent sein; „vorhanden“ in der Rohmatrix beweist
  keinen sichtbaren Kartenschatten. Die farbige Heute-Markierung im Kalender
  ist eine davon getrennte Zustandsmarkierung.
- Berichtsmodus prüft bestehende Baseline **vor** dem Schreiben. Neue Seiten
  oder Abweichungen bleiben rot; Berichtserstellung kann die Ratsche nicht mehr
  durch Überschreiben der Baseline umgehen.
- Nur die ersten drei sichtbaren Zeilen je erkanntem Block liefern Aktions-
  Stichproben. Schrift wird an der ersten erkannten Rolle gemessen. Fehlende
  Rollen, unbekannte Listenstrukturen, darunterliegende Datensätze und anfangs
  geschlossene Zustände sind dadurch nicht vollständig abgesichert. „Keine
  Abweichung“ bedeutet keinen vollständigen Nachweis der Gestaltung.

### Noch fehlende WP6-Evidenz

Rollen ausser `Cafeteria.Admin`; gesperrte, deaktivierte, Fehler-, Lade- und
Speicherzustände; vollständige Tastaturwege und Fokus-Rückgabe; Tooltip per
Fokus und Escape; Touch mit `pointer: coarse` und 44px-Zielen; 200% Zoom;
1024px und 768px; geprüfte Überläufe und Bestätigungsdialoge; exakte Kalender-
Zähler; echte Form-/Freigabeverträge nach jeder Produktkorrektur. Für Listen-
Dichte braucht es ausreichend gefüllte Fixtures (mindestens acht zweizeilige
Datensätze), gemessene erste Datenposition und sichtbare Datensatzanzahl.
Mobile Typografie, Kartenanatomie und Seitenscrollen werden in diesem Test
noch nicht gleich streng wie Desktop verglichen. Visuelle Aufnahme allein
belegt diese Interaktionen und Zustände nicht. Nach Integration anderer Pakete
ist ein erneuter Scan erforderlich; dieser Bericht beschreibt deren frühere
Produktbasis.

### Nachmessung nativer Menüeinträge (2026-09-28, MP-LIST-NATIVE-ENTRY-0928)

Die vollständige Nachmessung auf Produktbasis `c8c2e3c11149b41523a50a34dcba64cdc60230a6`
umfasst erneut 41 Seiten, 82 Desktop-Listenblöcke und beide Viewports. Ein
verschachteltes natives `summary` zählt jetzt als erreichbarer Überlaufeintrag;
äusserer Auslöser, leere Menüs sowie `hidden`- und `inert`-Einträge sind durch
eine Regression getrennt abgesichert. Die frühere Leer-Meldung der API-Details
war ein Messfehler. API-Schlüssel zeigt in beiden Breiten jetzt 0 leere
Überläufe und keine sichtbaren Texte an Kopf-/Zeilenaktionen. Damit entfallen
die vier alten API-Codes; neue Abweichungscodes wurden keine zugelassen.

Die handgeschriebenen Sichtbefunde oben wurden beim Regenerieren vollständig
erhalten (vor dieser Ergänzung 7856 Zeichen unverändert). Ihre historische
Produktbasis und Evidenzgrenzen bleiben gültig. Die API-Aufnahmen bei 1440×900
und 390×844 wurden erneut gesichtet; die übrigen Aufnahmen dieses Laufs liefern
keine neue vollständige Sichtabnahme. Messmatrix:
`/var/tmp/list-native-entry-0928-full/test_list_family_across_admin_0/list-family-measurements.json`.
Aufnahmen: `/var/tmp/list-native-entry-0928-evidence/`. Neue Screenshots wurden
als lokale Evidenz gesichert; die eingecheckten Screenshot-Baselines bleiben
unverändert.

## Messwerte

| Seite | Viewport | Messgrösse | Wert |
|---|---|---|---|
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Filtereinstiege | 0 |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Doppelte Aufklappmarker | 0 |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Leere Info-Symbole | 0 |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Zeile | **Höhe 69px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Status | **admin-label.admin-status--info.badge** |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-eye, tabler-dots; Treffer 36×36, 36×36** |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-eye, tabler-dots; Treffer 36×36, 36×36** |
| Wochenübersicht Cafeteria · Gespeicherte Wochen | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Filtereinstiege | 0 |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Doppelte Aufklappmarker | 0 |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Leere Info-Symbole | 0 |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Zeile | **Höhe 69px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Status | **admin-label.admin-status--info.badge** |
| Wochenübersicht Patienten · Gespeicherte Wochen | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-eye, tabler-dots; Treffer 36×36, 36×36** |
| Wochenübersicht Patienten · Gespeicherte Wochen | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-eye, tabler-dots; Treffer 36×36, 36×36** |
| Wochenübersicht Patienten · Gespeicherte Wochen | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Wochenplan Cafeteria · div | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-send; Treffer 48×48; gefüllte Primärflächen 1** |
| Wochenplan Cafeteria · div | 1440×900 | Filtereinstiege | 0 |
| Wochenplan Cafeteria · div | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Wochenplan Cafeteria · div | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Wochenplan Cafeteria · div | 1440×900 | Doppelte Aufklappmarker | 0 |
| Wochenplan Cafeteria · div | 1440×900 | Leere Info-Symbole | 0 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-send; Treffer 48×48; gefüllte Primärflächen 1** |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Cafeteria · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Cafeteria · div | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenplan Cafeteria · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Cafeteria · div | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Wochenplan Cafeteria · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Cafeteria · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-send; Treffer 48×48; gefüllte Primärflächen 1** |
| Wochenplan Patienten · div | 1440×900 | Filtereinstiege | 0 |
| Wochenplan Patienten · div | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Wochenplan Patienten · div | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Wochenplan Patienten · div | 1440×900 | Doppelte Aufklappmarker | 0 |
| Wochenplan Patienten · div | 1440×900 | Leere Info-Symbole | 0 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-send; Treffer 48×48; gefüllte Primärflächen 1** |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenplan Patienten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenplan Patienten · div | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Wochenplan Patienten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Wochenplan Patienten · div | 1440×900 | Status | keine |
| Wochenplan Patienten · div | 1440×900 | Zeilenaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenplan Patienten · div | 390×844 | Zeilenaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 48×48 |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Filtereinstiege | 0 |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Doppelte Aufklappmarker | 0 |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Leere Info-Symbole | 0 |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Zeile | **Höhe 48px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Sekundärtext | keine |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Status | keine |
| Wochenprüfung Cafeteria · Ausgabeangaben | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Wochenprüfung Cafeteria · Ausgabeangaben | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Wochenprüfung Cafeteria · Ausgabeangaben | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Filtereinstiege | 0 |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Doppelte Aufklappmarker | 0 |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Leere Info-Symbole | 0 |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Listencontainer | div · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Kopfzeile | keine Kopfzeile |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Zeile | **Höhe 48px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Sekundärtext | keine |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Status | keine |
| Wochenprüfung Patienten · Ausgabeangaben | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Wochenprüfung Patienten · Ausgabeangaben | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Wochenprüfung Patienten · Ausgabeangaben | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-calendar-week; Treffer 36×36; gefüllte Primärflächen 1** |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Filtereinstiege | 0 |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Doppelte Aufklappmarker | 0 |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Leere Info-Symbole | 0 |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Zeile | **Höhe 66px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Status | **admin-label.admin-status--warning.badge** |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Zeilenaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 36×36** |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 390×844 | Zeilenaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 36×36** |
| Menüs Cafeteria · Gespeicherte Menüs der aktuellen Suche | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-calendar-week; Treffer 36×36; gefüllte Primärflächen 1** |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-calendar-week; Treffer 36×36; gefüllte Primärflächen 1** |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Filtereinstiege | 0 |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Doppelte Aufklappmarker | 0 |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Leere Info-Symbole | 0 |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Zeile | **Höhe 66px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Status | **admin-label.admin-status--warning.badge** |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 1440×900 | Zeilenaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 36×36** |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 390×844 | Zeilenaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 36×36** |
| Menüs Patienten · Gespeicherte Menüs der aktuellen Suche | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-calendar-week; Treffer 36×36; gefüllte Primärflächen 1** |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Filtereinstiege | **1** |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Doppelte Aufklappmarker | 0 |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Leere Info-Symbole | 0 |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Zeile | **Höhe 64px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Status | **admin-label.admin-status--category.badge** |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Bausteine Cafeteria · Bausteine der aktuellen Suche | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Filtereinstiege | **1** |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Doppelte Aufklappmarker | 0 |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Leere Info-Symbole | 0 |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Zeile | **Höhe 64px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Status | **admin-label.admin-status--category.badge** |
| Bausteine Patienten · Bausteine der aktuellen Suche | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Bausteine Patienten · Bausteine der aktuellen Suche | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Bausteine Patienten · Bausteine der aktuellen Suche | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Kopfaktionen | **4 sichtbar, 0 mit Text (—); Icons tabler: tabler-chevron-left, tabler-chevron-right, tabler-calendar-event, tabler-plus; Treffer 36×36, 36×36, 36×36, 36×36; gefüllte Primärflächen 1** |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Filtereinstiege | 0 |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Doppelte Aufklappmarker | 0 |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Leere Info-Symbole | 0 |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Listencontainer | **table · Rahmen 0px none rgb(229, 231, 235) · Radius 0px · Schatten none** |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Zeile | **Höhe 219px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten vorhanden · Karte nein** |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Status | keine |
| Küchenkalender · Monatsraster Küchenkalender | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Küchenkalender · Kalendertage | 390×844 | Kopfaktionen schmal | **4 sichtbar, 0 mit Text (—); Icons tabler: tabler-chevron-left, tabler-chevron-right, tabler-calendar-event, tabler-plus; Treffer 36×36, 36×36, 36×36, 36×36; gefüllte Primärflächen 1** |
| Zutaten · div | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Zutaten · div | 1440×900 | Filtereinstiege | **1** |
| Zutaten · div | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Zutaten · div | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Zutaten · div | 1440×900 | Doppelte Aufklappmarker | 0 |
| Zutaten · div | 1440×900 | Leere Info-Symbole | 0 |
| Zutaten · div | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Zutaten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Zutaten · div | 1440×900 | Zeile | **Höhe 64px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Zutaten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Zutaten · div | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / Link rgb(89, 98, 115) |
| Zutaten · div | 1440×900 | Status | keine |
| Zutaten · div | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Zutaten · div | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Zutaten · div | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Einheiten · div | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Einheiten · div | 1440×900 | Filtereinstiege | **1** |
| Einheiten · div | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Einheiten · div | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Einheiten · div | 1440×900 | Doppelte Aufklappmarker | 0 |
| Einheiten · div | 1440×900 | Leere Info-Symbole | 0 |
| Einheiten · div | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Einheiten · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Einheiten · div | 1440×900 | Zeile | **Höhe 53px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Einheiten · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Einheiten · div | 1440×900 | Sekundärtext | keine |
| Einheiten · div | 1440×900 | Status | keine |
| Einheiten · div | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Einheiten · div | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Einheiten · div | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Kategorien · keine Datenliste | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Kategorien · keine Datenliste | 1440×900 | Filtereinstiege | **1** |
| Kategorien · keine Datenliste | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Kategorien · keine Datenliste | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Kategorien · keine Datenliste | 1440×900 | Doppelte Aufklappmarker | 0 |
| Kategorien · keine Datenliste | 1440×900 | Leere Info-Symbole | 0 |
| Kategorien · keine Datenliste | 1440×900 | Listencontainer | **keine Liste** |
| Kategorien · keine Datenliste | 1440×900 | Kopfzeile | keine Kopfzeile |
| Kategorien · keine Datenliste | 1440×900 | Zeile | **keine Datenzeile** |
| Kategorien · keine Datenliste | 1440×900 | Haupttext | keine |
| Kategorien · keine Datenliste | 1440×900 | Sekundärtext | keine |
| Kategorien · keine Datenliste | 1440×900 | Status | keine |
| Kategorien · keine Datenliste | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kategorien · keine Datenliste | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kategorien · keine Datenliste | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Kennzeichnungen · div | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Kennzeichnungen · div | 1440×900 | Filtereinstiege | **1** |
| Kennzeichnungen · div | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Kennzeichnungen · div | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Kennzeichnungen · div | 1440×900 | Doppelte Aufklappmarker | 0 |
| Kennzeichnungen · div | 1440×900 | Leere Info-Symbole | 0 |
| Kennzeichnungen · div | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Kennzeichnungen · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Kennzeichnungen · div | 1440×900 | Zeile | **Höhe 53px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Kennzeichnungen · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Kennzeichnungen · div | 1440×900 | Sekundärtext | keine |
| Kennzeichnungen · div | 1440×900 | Status | keine |
| Kennzeichnungen · div | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Kennzeichnungen · div | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Kennzeichnungen · div | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Lagerorte · div | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Lagerorte · div | 1440×900 | Filtereinstiege | **1** |
| Lagerorte · div | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Lagerorte · div | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Lagerorte · div | 1440×900 | Doppelte Aufklappmarker | 0 |
| Lagerorte · div | 1440×900 | Leere Info-Symbole | 0 |
| Lagerorte · div | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Lagerorte · div | 1440×900 | Kopfzeile | keine Kopfzeile |
| Lagerorte · div | 1440×900 | Zeile | **Höhe 53px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Lagerorte · div | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Lagerorte · div | 1440×900 | Sekundärtext | keine |
| Lagerorte · div | 1440×900 | Status | keine |
| Lagerorte · div | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Lagerorte · div | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Lagerorte · div | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Rezepte · Rezepte | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Rezepte · Rezepte | 1440×900 | Filtereinstiege | **2** |
| Rezepte · Rezepte | 1440×900 | Filtereinstiege mit sichtbarem Text | **1** |
| Rezepte · Rezepte | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Rezepte · Rezepte | 1440×900 | Doppelte Aufklappmarker | 0 |
| Rezepte · Rezepte | 1440×900 | Leere Info-Symbole | 0 |
| Rezepte · Rezepte | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Rezepte · Rezepte | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Rezepte · Rezepte | 1440×900 | Zeile | **Höhe 53px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Rezepte · Rezepte | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Rezepte · Rezepte | 1440×900 | Sekundärtext | keine |
| Rezepte · Rezepte | 1440×900 | Status | keine |
| Rezepte · Rezepte | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Rezepte · Rezepte | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Rezepte · Rezepte | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Gerichtvorlagen · table | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Gerichtvorlagen · table | 1440×900 | Filtereinstiege | **1** |
| Gerichtvorlagen · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Gerichtvorlagen · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Gerichtvorlagen · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Gerichtvorlagen · table | 1440×900 | Leere Info-Symbole | 0 |
| Gerichtvorlagen · table | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Gerichtvorlagen · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Gerichtvorlagen · table | 1440×900 | Zeile | **Höhe 53px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Gerichtvorlagen · table | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Gerichtvorlagen · table | 1440×900 | Sekundärtext | keine |
| Gerichtvorlagen · table | 1440×900 | Status | keine |
| Gerichtvorlagen · table | 1440×900 | Zeilenaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right; Treffer 36×36** |
| Gerichtvorlagen · table | 390×844 | Zeilenaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right; Treffer 36×36** |
| Gerichtvorlagen · table | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Lager · Zuordnungen | 1440×900 | Kopfaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Lager · Zuordnungen | 1440×900 | Filtereinstiege | 0 |
| Lager · Zuordnungen | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Lager · Zuordnungen | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Lager · Zuordnungen | 1440×900 | Doppelte Aufklappmarker | 0 |
| Lager · Zuordnungen | 1440×900 | Leere Info-Symbole | 0 |
| Lager · Zuordnungen | 1440×900 | Listencontainer | **table · Rahmen 0px none rgb(229, 231, 235) · Radius 0px · Schatten none** |
| Lager · Zuordnungen | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Lager · Zuordnungen | 1440×900 | Zeile | **Höhe 53px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Lager · Zuordnungen | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Lager · Zuordnungen | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Lager · Zuordnungen | 1440×900 | Status | keine |
| Lager · Zuordnungen | 1440×900 | Zeilenaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right; Treffer 36×36** |
| Lager · Zuordnungen | 390×844 | Zeilenaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right; Treffer 36×36** |
| Lager · Zuordnungen | 390×844 | Kopfaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Kochbücher · Kochbücher | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Kochbücher · Kochbücher | 1440×900 | Filtereinstiege | **1** |
| Kochbücher · Kochbücher | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Kochbücher · Kochbücher | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Kochbücher · Kochbücher | 1440×900 | Doppelte Aufklappmarker | 0 |
| Kochbücher · Kochbücher | 1440×900 | Leere Info-Symbole | 0 |
| Kochbücher · Kochbücher | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Kochbücher · Kochbücher | 1440×900 | Kopfzeile | keine Kopfzeile |
| Kochbücher · Kochbücher | 1440×900 | Zeile | **Höhe 64px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Kochbücher · Kochbücher | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Kochbücher · Kochbücher | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Kochbücher · Kochbücher | 1440×900 | Status | keine |
| Kochbücher · Kochbücher | 1440×900 | Zeilenaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 36×36** |
| Kochbücher · Kochbücher | 390×844 | Zeilenaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 36×36** |
| Kochbücher · Kochbücher | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Einkaufslisten · form | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Einkaufslisten · form | 1440×900 | Filtereinstiege | 0 |
| Einkaufslisten · form | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Einkaufslisten · form | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Einkaufslisten · form | 1440×900 | Doppelte Aufklappmarker | 0 |
| Einkaufslisten · form | 1440×900 | Leere Info-Symbole | 0 |
| Einkaufslisten · form | 1440×900 | Listencontainer | **form · Rahmen 0px none rgb(31, 41, 55) · Radius 0px · Schatten none** |
| Einkaufslisten · form | 1440×900 | Kopfzeile | keine Kopfzeile |
| Einkaufslisten · form | 1440×900 | Zeile | **Höhe 64px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Einkaufslisten · form | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Einkaufslisten · form | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Einkaufslisten · form | 1440×900 | Status | keine |
| Einkaufslisten · form | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right, tabler-dots; Treffer 36×36, 36×36** |
| Einkaufslisten · form | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right, tabler-dots; Treffer 36×36, 36×36** |
| Einkaufslisten · form | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Bestellungen · Warenkorb | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Bestellungen · Warenkorb | 1440×900 | Filtereinstiege | 0 |
| Bestellungen · Warenkorb | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Bestellungen · Warenkorb | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Bestellungen · Warenkorb | 1440×900 | Doppelte Aufklappmarker | 0 |
| Bestellungen · Warenkorb | 1440×900 | Leere Info-Symbole | 0 |
| Bestellungen · Warenkorb | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Bestellungen · Warenkorb | 1440×900 | Kopfzeile | keine Kopfzeile |
| Bestellungen · Warenkorb | 1440×900 | Zeile | **Höhe 52px · Trenner 0px none rgb(89, 98, 115) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Bestellungen · Warenkorb | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Bestellungen · Warenkorb | 1440×900 | Sekundärtext | keine |
| Bestellungen · Warenkorb | 1440×900 | Status | **admin-label.admin-status--neutral.badge.ui-sem-label** |
| Bestellungen · Warenkorb | 1440×900 | Zeilenaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right; Treffer 36×36** |
| Bestellungen · Warenkorb | 390×844 | Zeilenaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right; Treffer 36×36** |
| Bestellungen · Warenkorb | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Bestellungen · Lieferant | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Bestellungen · Lieferant | 1440×900 | Kopfzeile | keine Kopfzeile |
| Bestellungen · Lieferant | 1440×900 | Zeile | **Höhe 64px · Trenner 0px none rgb(89, 98, 115) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Bestellungen · Lieferant | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Bestellungen · Lieferant | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Bestellungen · Lieferant | 1440×900 | Status | **admin-label.admin-status--active.badge.ui-sem-label** |
| Bestellungen · Lieferant | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bestellungen · Lieferant | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kalkulation · table | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-check; Treffer 36×36; gefüllte Primärflächen 1** |
| Kalkulation · table | 1440×900 | Filtereinstiege | 0 |
| Kalkulation · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Kalkulation · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Kalkulation · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Kalkulation · table | 1440×900 | Leere Info-Symbole | 0 |
| Kalkulation · table | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Kalkulation · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Kalkulation · table | 1440×900 | Zeile | **Höhe 49px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Kalkulation · table | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Kalkulation · table | 1440×900 | Sekundärtext | keine |
| Kalkulation · table | 1440×900 | Status | **admin-label.admin-status--warning.badge** |
| Kalkulation · table | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kalkulation · table | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kalkulation · table | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-check; Treffer 36×36; gefüllte Primärflächen 1** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-printer; Treffer 36×36; gefüllte Primärflächen 1** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Filtereinstiege | 0 |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Doppelte Aufklappmarker | 0 |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Leere Info-Symbole | 0 |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Listencontainer | **details · Rahmen 0px none rgb(31, 41, 55) · Radius 12px · Schatten none** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Kopfzeile | keine Kopfzeile |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Zeile | **Höhe 76px · Trenner 0px none rgb(89, 98, 115) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Status | **admin-label.admin-status--active.badge.ui-sem-label** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-printer; Treffer 36×36; gefüllte Primärflächen 1** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Listencontainer | **details · Rahmen 0px none rgb(31, 41, 55) · Radius 12px · Schatten none** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Kopfzeile | keine Kopfzeile |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Zeile | **Höhe 76px · Trenner 0px none rgb(89, 98, 115) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Status | **admin-label.admin-status--active.badge.ui-sem-label** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Druckvorlagen und Vorlagenkatalog · Verfügbare Vorlagen | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit, tabler-dots; Treffer 36×36, 36×36** |
| Druckvorlagen und Vorlagenkatalog · ul | 1440×900 | Listencontainer | **ul · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Druckvorlagen und Vorlagenkatalog · ul | 1440×900 | Kopfzeile | keine Kopfzeile |
| Druckvorlagen und Vorlagenkatalog · ul | 1440×900 | Zeile | **Höhe 76px · Trenner 0px none rgb(89, 98, 115) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Druckvorlagen und Vorlagenkatalog · ul | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Druckvorlagen und Vorlagenkatalog · ul | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Druckvorlagen und Vorlagenkatalog · ul | 1440×900 | Status | **admin-label.admin-status--active.badge.ui-sem-label** |
| Druckvorlagen und Vorlagenkatalog · ul | 1440×900 | Zeilenaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 36×36** |
| Druckvorlagen und Vorlagenkatalog · ul | 390×844 | Zeilenaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-edit; Treffer 36×36** |
| Druckvorlagen und Vorlagenkatalog · Screen-Vorlagen | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Druckvorlagen und Vorlagenkatalog · Screen-Vorlagen | 1440×900 | Kopfzeile | keine Kopfzeile |
| Druckvorlagen und Vorlagenkatalog · Screen-Vorlagen | 1440×900 | Zeile | **Höhe 53px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Druckvorlagen und Vorlagenkatalog · Screen-Vorlagen | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Druckvorlagen und Vorlagenkatalog · Screen-Vorlagen | 1440×900 | Sekundärtext | keine |
| Druckvorlagen und Vorlagenkatalog · Screen-Vorlagen | 1440×900 | Status | **admin-label.admin-status--active.badge.ui-sem-label** |
| Druckvorlagen und Vorlagenkatalog · Screen-Vorlagen | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-eye, tabler-dots; Treffer 36×36, 36×36** |
| Druckvorlagen und Vorlagenkatalog · Screen-Vorlagen | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-eye, tabler-dots; Treffer 36×36, 36×36** |
| Bildschirme · table | 1440×900 | Kopfaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Bildschirme · table | 1440×900 | Filtereinstiege | 0 |
| Bildschirme · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Bildschirme · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Bildschirme · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Bildschirme · table | 1440×900 | Leere Info-Symbole | 0 |
| Bildschirme · table | 1440×900 | Listencontainer | **table · Rahmen 0px none rgb(229, 231, 235) · Radius 0px · Schatten none** |
| Bildschirme · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Bildschirme · table | 1440×900 | Zeile | **Höhe 117px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Bildschirme · table | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Bildschirme · table | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Bildschirme · table | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| Bildschirme · table | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right, tabler-dots; Treffer 36×36, 36×36** |
| Bildschirme · table | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right, tabler-dots; Treffer 36×36, 36×36** |
| Bildschirme · table | 390×844 | Kopfaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Kopfaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Filtereinstiege | 0 |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Doppelte Aufklappmarker | 0 |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Leere Info-Symbole | 0 |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Listencontainer | **keine Liste** |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Kopfzeile | keine Kopfzeile |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Zeile | **keine Datenzeile** |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Haupttext | keine |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Sekundärtext | keine |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Status | keine |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bildschirmvorlagen Cafeteria · keine Datenliste | 390×844 | Kopfaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Kopfaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Filtereinstiege | 0 |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Doppelte Aufklappmarker | 0 |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Leere Info-Symbole | 0 |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Listencontainer | **keine Liste** |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Kopfzeile | keine Kopfzeile |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Zeile | **keine Datenzeile** |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Haupttext | keine |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Sekundärtext | keine |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Status | keine |
| Bildschirmvorlagen Patienten · keine Datenliste | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bildschirmvorlagen Patienten · keine Datenliste | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bildschirmvorlagen Patienten · keine Datenliste | 390×844 | Kopfaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Benutzer · Lokale Konten | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Benutzer · Lokale Konten | 1440×900 | Filtereinstiege | **1** |
| Benutzer · Lokale Konten | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Benutzer · Lokale Konten | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Benutzer · Lokale Konten | 1440×900 | Doppelte Aufklappmarker | 0 |
| Benutzer · Lokale Konten | 1440×900 | Leere Info-Symbole | 0 |
| Benutzer · Lokale Konten | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Benutzer · Lokale Konten | 1440×900 | Kopfzeile | keine Kopfzeile |
| Benutzer · Lokale Konten | 1440×900 | Zeile | **Höhe 64px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Benutzer · Lokale Konten | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Benutzer · Lokale Konten | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Benutzer · Lokale Konten | 1440×900 | Status | **admin-label.admin-status--active.badge** |
| Benutzer · Lokale Konten | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Benutzer · Lokale Konten | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Benutzer · Lokale Konten | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Kontoereignisse · Kontoereignisse | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 1** |
| Kontoereignisse · Kontoereignisse | 1440×900 | Filtereinstiege | 0 |
| Kontoereignisse · Kontoereignisse | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Kontoereignisse · Kontoereignisse | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Kontoereignisse · Kontoereignisse | 1440×900 | Doppelte Aufklappmarker | 0 |
| Kontoereignisse · Kontoereignisse | 1440×900 | Leere Info-Symbole | 0 |
| Kontoereignisse · Kontoereignisse | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Kontoereignisse · Kontoereignisse | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Kontoereignisse · Kontoereignisse | 1440×900 | Zeile | **Höhe 48px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Kontoereignisse · Kontoereignisse | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Kontoereignisse · Kontoereignisse | 1440×900 | Sekundärtext | keine |
| Kontoereignisse · Kontoereignisse | 1440×900 | Status | keine |
| Kontoereignisse · Kontoereignisse | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kontoereignisse · Kontoereignisse | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kontoereignisse · Kontoereignisse | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 1** |
| API-Schlüssel · table | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| API-Schlüssel · table | 1440×900 | Filtereinstiege | 0 |
| API-Schlüssel · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| API-Schlüssel · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| API-Schlüssel · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| API-Schlüssel · table | 1440×900 | Leere Info-Symbole | 0 |
| API-Schlüssel · table | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| API-Schlüssel · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| API-Schlüssel · table | 1440×900 | Zeile | **Höhe 64px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| API-Schlüssel · table | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| API-Schlüssel · table | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| API-Schlüssel · table | 1440×900 | Status | **admin-label.admin-status--neutral.badge** |
| API-Schlüssel · table | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-trash, tabler-dots; Treffer 36×36, 36×36** |
| API-Schlüssel · table | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-trash, tabler-dots; Treffer 36×36, 36×36** |
| API-Schlüssel · table | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Filtereinstiege | **1** |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Doppelte Aufklappmarker | 0 |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Leere Info-Symbole | 0 |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Listencontainer | **keine Liste** |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Kopfzeile | keine Kopfzeile |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Zeile | **keine Datenzeile** |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Haupttext | keine |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Sekundärtext | keine |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Status | keine |
| Zugriffsverlauf · keine Datenliste | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Zugriffsverlauf · keine Datenliste | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Zugriffsverlauf · keine Datenliste | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Rezeptimporte · table | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Rezeptimporte · table | 1440×900 | Filtereinstiege | 0 |
| Rezeptimporte · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Rezeptimporte · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Rezeptimporte · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Rezeptimporte · table | 1440×900 | Leere Info-Symbole | 0 |
| Rezeptimporte · table | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Rezeptimporte · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Rezeptimporte · table | 1440×900 | Zeile | **Höhe 49px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Rezeptimporte · table | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Rezeptimporte · table | 1440×900 | Sekundärtext | keine |
| Rezeptimporte · table | 1440×900 | Status | **admin-label.admin-status--info.badge** |
| Rezeptimporte · table | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Rezeptimporte · table | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Rezeptimporte · table | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Datenimport · keine Datenliste | 1440×900 | Kopfaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Datenimport · keine Datenliste | 1440×900 | Filtereinstiege | 0 |
| Datenimport · keine Datenliste | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Datenimport · keine Datenliste | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Datenimport · keine Datenliste | 1440×900 | Doppelte Aufklappmarker | 0 |
| Datenimport · keine Datenliste | 1440×900 | Leere Info-Symbole | 0 |
| Datenimport · keine Datenliste | 1440×900 | Listencontainer | **keine Liste** |
| Datenimport · keine Datenliste | 1440×900 | Kopfzeile | keine Kopfzeile |
| Datenimport · keine Datenliste | 1440×900 | Zeile | **keine Datenzeile** |
| Datenimport · keine Datenliste | 1440×900 | Haupttext | keine |
| Datenimport · keine Datenliste | 1440×900 | Sekundärtext | keine |
| Datenimport · keine Datenliste | 1440×900 | Status | keine |
| Datenimport · keine Datenliste | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Datenimport · keine Datenliste | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Datenimport · keine Datenliste | 390×844 | Kopfaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Kopfaktionen | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Filtereinstiege | 0 |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Doppelte Aufklappmarker | 0 |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Leere Info-Symbole | 0 |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Zeile | **Höhe 65px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Sekundärtext | keine |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Status | **admin-label.admin-status--warning.badge** |
| Bereiche und Zeiten · Einstellungen | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bereiche und Zeiten · Einstellungen | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bereiche und Zeiten · Einstellungen | 390×844 | Kopfaktionen schmal | 1 sichtbar, 0 mit Text (—); Icons tabler: tabler-plus; Treffer 36×36; gefüllte Primärflächen 1 |
| Rezeptverlauf · table | 1440×900 | Kopfaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right, tabler-versions; Treffer 36×36, 36×36; gefüllte Primärflächen 1** |
| Rezeptverlauf · table | 1440×900 | Filtereinstiege | 0 |
| Rezeptverlauf · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Rezeptverlauf · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Rezeptverlauf · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Rezeptverlauf · table | 1440×900 | Leere Info-Symbole | 0 |
| Rezeptverlauf · table | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Rezeptverlauf · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Rezeptverlauf · table | 1440×900 | Zeile | **Höhe 57px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Rezeptverlauf · table | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Rezeptverlauf · table | 1440×900 | Sekundärtext | 13px / 400 / rgb(89, 98, 115) / kein Link |
| Rezeptverlauf · table | 1440×900 | Status | keine |
| Rezeptverlauf · table | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Rezeptverlauf · table | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Rezeptverlauf · table | 390×844 | Kopfaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right, tabler-versions; Treffer 36×36, 36×36; gefüllte Primärflächen 1** |
| Rezeptverlauf · table | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Rezeptverlauf · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Rezeptverlauf · table | 1440×900 | Zeile | Höhe 105px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein |
| Rezeptverlauf · table | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / kein Link |
| Rezeptverlauf · table | 1440×900 | Sekundärtext | keine |
| Rezeptverlauf · table | 1440×900 | Status | keine |
| Rezeptverlauf · table | 1440×900 | Zeilenaktionen | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right, tabler-dots; Treffer 36×36, 36×36** |
| Rezeptverlauf · table | 390×844 | Zeilenaktionen schmal | **2 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right, tabler-dots; Treffer 36×36, 36×36** |
| Rezeptskalierung · table | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right; Treffer 36×36; gefüllte Primärflächen 0** |
| Rezeptskalierung · table | 1440×900 | Filtereinstiege | 0 |
| Rezeptskalierung · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Rezeptskalierung · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Rezeptskalierung · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Rezeptskalierung · table | 1440×900 | Leere Info-Symbole | 0 |
| Rezeptskalierung · table | 1440×900 | Listencontainer | **section · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Rezeptskalierung · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Rezeptskalierung · table | 1440×900 | Zeile | **Höhe 48px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Rezeptskalierung · table | 1440×900 | Haupttext | keine |
| Rezeptskalierung · table | 1440×900 | Sekundärtext | keine |
| Rezeptskalierung · table | 1440×900 | Status | keine |
| Rezeptskalierung · table | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Rezeptskalierung · table | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Rezeptskalierung · table | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-right; Treffer 36×36; gefüllte Primärflächen 0** |
| Rezeptbilder · keine Datenliste | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Rezeptbilder · keine Datenliste | 1440×900 | Filtereinstiege | 0 |
| Rezeptbilder · keine Datenliste | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Rezeptbilder · keine Datenliste | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Rezeptbilder · keine Datenliste | 1440×900 | Doppelte Aufklappmarker | 0 |
| Rezeptbilder · keine Datenliste | 1440×900 | Leere Info-Symbole | 0 |
| Rezeptbilder · keine Datenliste | 1440×900 | Listencontainer | **keine Liste** |
| Rezeptbilder · keine Datenliste | 1440×900 | Kopfzeile | keine Kopfzeile |
| Rezeptbilder · keine Datenliste | 1440×900 | Zeile | **keine Datenzeile** |
| Rezeptbilder · keine Datenliste | 1440×900 | Haupttext | keine |
| Rezeptbilder · keine Datenliste | 1440×900 | Sekundärtext | keine |
| Rezeptbilder · keine Datenliste | 1440×900 | Status | keine |
| Rezeptbilder · keine Datenliste | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Rezeptbilder · keine Datenliste | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Rezeptbilder · keine Datenliste | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Kochbuch · table | 1440×900 | Kopfaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Kochbuch · table | 1440×900 | Filtereinstiege | 0 |
| Kochbuch · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Kochbuch · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Kochbuch · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Kochbuch · table | 1440×900 | Leere Info-Symbole | 0 |
| Kochbuch · table | 1440×900 | Listencontainer | **table · Rahmen 0px none rgb(229, 231, 235) · Radius 0px · Schatten none** |
| Kochbuch · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Kochbuch · table | 1440×900 | Zeile | **Höhe 65px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Kochbuch · table | 1440×900 | Haupttext | keine |
| Kochbuch · table | 1440×900 | Sekundärtext | keine |
| Kochbuch · table | 1440×900 | Status | keine |
| Kochbuch · table | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kochbuch · table | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Kochbuch · table | 390×844 | Kopfaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —; gefüllte Primärflächen 0** |
| Einkaufsliste · keine Datenliste | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-printer; Treffer 36×36; gefüllte Primärflächen 0** |
| Einkaufsliste · keine Datenliste | 1440×900 | Filtereinstiege | 0 |
| Einkaufsliste · keine Datenliste | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Einkaufsliste · keine Datenliste | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Einkaufsliste · keine Datenliste | 1440×900 | Doppelte Aufklappmarker | 0 |
| Einkaufsliste · keine Datenliste | 1440×900 | Leere Info-Symbole | 0 |
| Einkaufsliste · keine Datenliste | 1440×900 | Listencontainer | **keine Liste** |
| Einkaufsliste · keine Datenliste | 1440×900 | Kopfzeile | keine Kopfzeile |
| Einkaufsliste · keine Datenliste | 1440×900 | Zeile | **keine Datenzeile** |
| Einkaufsliste · keine Datenliste | 1440×900 | Haupttext | keine |
| Einkaufsliste · keine Datenliste | 1440×900 | Sekundärtext | keine |
| Einkaufsliste · keine Datenliste | 1440×900 | Status | keine |
| Einkaufsliste · keine Datenliste | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Einkaufsliste · keine Datenliste | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Einkaufsliste · keine Datenliste | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-printer; Treffer 36×36; gefüllte Primärflächen 0** |
| Bestellkorb · table | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-download; Treffer 36×36; gefüllte Primärflächen 0** |
| Bestellkorb · table | 1440×900 | Filtereinstiege | 0 |
| Bestellkorb · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Bestellkorb · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Bestellkorb · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Bestellkorb · table | 1440×900 | Leere Info-Symbole | 0 |
| Bestellkorb · table | 1440×900 | Listencontainer | **table · Rahmen 0px none rgb(229, 231, 235) · Radius 0px · Schatten none** |
| Bestellkorb · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Bestellkorb · table | 1440×900 | Zeile | **Höhe 65px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Bestellkorb · table | 1440×900 | Haupttext | keine |
| Bestellkorb · table | 1440×900 | Sekundärtext | keine |
| Bestellkorb · table | 1440×900 | Status | keine |
| Bestellkorb · table | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bestellkorb · table | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Bestellkorb · table | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-download; Treffer 36×36; gefüllte Primärflächen 0** |
| Importstapel · table | 1440×900 | Kopfaktionen | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Importstapel · table | 1440×900 | Filtereinstiege | 0 |
| Importstapel · table | 1440×900 | Filtereinstiege mit sichtbarem Text | 0 |
| Importstapel · table | 1440×900 | Überlaufmenü ohne Einträge | 0 |
| Importstapel · table | 1440×900 | Doppelte Aufklappmarker | 0 |
| Importstapel · table | 1440×900 | Leere Info-Symbole | 0 |
| Importstapel · table | 1440×900 | Listencontainer | **div · Rahmen 1px solid rgb(229, 231, 235) · Radius 8px · Schatten none** |
| Importstapel · table | 1440×900 | Kopfzeile | 12px / 500 / uppercase / rgb(89, 98, 115) / Grund rgb(250, 249, 247) / Höhe 33px |
| Importstapel · table | 1440×900 | Zeile | **Höhe 49px · Trenner 1px solid rgb(229, 231, 235) · Grund rgba(0, 0, 0, 0) · Radius 0px · Schatten none · Karte nein** |
| Importstapel · table | 1440×900 | Haupttext | 14px / 600 / rgb(31, 41, 55) / Link rgb(31, 41, 55) |
| Importstapel · table | 1440×900 | Sekundärtext | keine |
| Importstapel · table | 1440×900 | Status | **admin-label.admin-status--info.badge** |
| Importstapel · table | 1440×900 | Zeilenaktionen | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Importstapel · table | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Importstapel · table | 390×844 | Kopfaktionen schmal | **1 sichtbar, 0 mit Text (—); Icons tabler: tabler-arrow-left; Treffer 36×36; gefüllte Primärflächen 0** |
| Küchenkalender · Kalendertage | 390×844 | Zeilenaktionen schmal | **0 sichtbar, 0 mit Text (—); Icons keins: keins; Treffer —** |
| Küchenkalender · Kalendertage | 390×844 | Kopfaktionen schmal | **4 sichtbar, 0 mit Text (—); Icons tabler: tabler-chevron-left, tabler-chevron-right, tabler-calendar-event, tabler-plus; Treffer 36×36, 36×36, 36×36, 36×36; gefüllte Primärflächen 1** |
