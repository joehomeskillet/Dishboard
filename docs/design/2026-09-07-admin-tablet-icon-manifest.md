# Dishboard Admin: Tablet- und Symbolmanifest

Stand: 7. September 2026. Designautor: **GPT-6 Astra**. WP `wp-e6846db6f07d`.
Verbindlicher Sollvertrag für spätere UI-Arbeit; **keine Produktimplementierung oder Freigabe**.
Geprüfte Dokumentbasis: `e9d9f5a9e5c5df395f0475cbc6a9be6adf6ba7cb`, Branch
`docs/admin-tablet-manifest-astra-0907`. Produktstatus ist aus diesem Dokument nicht abzuleiten.

## 1. Auftrag und Rangfolge

«überal symbole verwenden wo es geht, auch für vega usw. ich möchte mehr symbole statt text.
beim drüberfahren soll es aber ersichtlich sein.» Dazu gilt: **«KARTEN IMMER GLEICH GROSS»**.

Dishboard soll sich wie ein ruhiges Küchenarbeitsbrett bedienen: Woche erkennen, Gericht
finden, bearbeiten, prüfen und gezielt veröffentlichen. Wiederholte Bedienwörter weichen
einer konsistenten Symbolsprache. Gericht, Datum, Bereich und fachliche Wahrheit bleiben lesbar.
Das Besondere ist das geordnete Kartenraster mit einer wiederkehrenden, kleinen Aktionszone.
Keine dekorativen Diagramme, wechselnden Iconstile oder zusätzlichen Dashboard-Kennzahlen.

Rangfolge: Fach-/Sicherheitsverträge → vorhandener Tabler-Vertrag → dieses Manifest.
Dieses Manifest präzisiert icon-only für wiederholte **Aktionen**; es hebt die Textpflicht
für Status, Navigation und Formulare nicht auf. Fachliche Änderungen benötigen einen eigenen WP.

- [Tabler-Vertrag](admin-tabler-contract.md): Shell, Makros, lokale Assets, 48-px-Ziele.
- [DOM-/Formularvertrag](admin-redesign-ui.md): Feldnamen, Versionen, Profile und Arbeitsstände.
- [Screens und Vorlagen](2026-09-05-screens-vorlagen-verwaltung.md): Vorschauen, Legenden und Ausgaben.
- [BAS/REC-Vertrag](2026-09-06-bas-rec-data-contract.md) und [Backlog](../BACKLOG.md):
  Rezepte/Stammdaten sind nicht vollständig implementiert; der vorhandene Mengenkern beweist keine Rezeptoberfläche.
- OPS-Zusatz: SDD `docs/design/2026-09-06-ops-bereiche-zeiten-sdd.md`, **nur im noch
  unveröffentlichten Kandidaten** `/nvmetank1/projects/menuplan/.claude/worktrees/ops-root-review-0906`
  (von Root referenzierter HEAD `acb018d`). Vor OPS-Umsetzung dortigen Integrationsstand prüfen;
  die SDD fehlt auf der Basis dieses Dokuments. Keine alte OPS-Fassung als Freigabe verwenden.

## 2. Eine visuelle Sprache

Alle Adminflächen einschliesslich Menü-, Komponenten-, Druckvorlagen- und zukünftiger
Rezepteditoren bleiben Tabler. Vorhandene `admin/base_tabler.html`, `_macros.html`,
`_workflow_sidebar.html` und `static/admin-tabler.css` sind die gemeinsame Oberfläche.
Dateinamen ohne Präfix beziehen sich hier auf `reference_scaffold/cafeteria/`.
Kein neues Framework, keine Dependency und keine fremde Editor-Skin als Paralleloberfläche.

| Entscheidung | Verbindliche Anwendung |
|---|---|
| Marke | Bordeaux für die Hauptaktion (`--sh-primary`), dunkles Petrol für Navigation (`--sh-teal-950`), warme ruhige Fläche (`--sh-canvas-strong`), helle Karten (`--sh-panel`). Vorhandene Tabler-Zuordnung nutzen. |
| Text/Fokus | `--sh-ink`, `--sh-ink-muted`, vorhandene Fokusringe; Kontrast am tatsächlichen Paar prüfen, ein Tokenname ist kein Kontrastnachweis. |
| Schrift | Lokal gehostete Fira Sans über `--sh-font`/`--sh-font-display`; 16 px Grund-/Eingabetext. Vorhandene Einstellung gross bleibt wirksam. Keine zusätzliche Schrift. |
| Hierarchie | Ein `h1` über `page_header`, `h2.card-title` für Abschnitte, `h3` für Gerichte. Gewicht 600 für Titel, 400 für Inhalte; kein dauerndes Versal-UI. Datum, Uhrzeit und Zahlen sauber ausrichten. |
| Rundung | Bestehendes Mapping `--sh-radius-sm`/`--sh-radius-md`; kein neuer Radius pro Route. |
| Abstand | Bestehende Tabler-Grid-/Abstandsutilities: `.row.g-3`, `.btn-list`, `.row-cards`; 8 px zwischen Aktionen, 16 px Standardinnenabstand, vorhandene 24 px auf breiten Flächen bzw. 12 px im Kompaktmodus. Keine erfundenen Spacing-Tokens. |
| Dichte | Vorhandene serverseitige `data-density`, `data-font-size`, `data-content-width` beachten. Kompakt reduziert Zwischenraum, niemals 48-px-Ziele oder Lesbarkeit. Kein zweiter lokaler Dichtespeicher. |
| Bewegung | Nur kurze funktionsbezogene Übergänge. `prefers-reduced-motion` ohne dekorative Bewegung; Statuswechsel auch ohne Animation erkennbar. |

## 3. Tablet zuerst und gleiche Karten

| CSS-Breite | Navigation / Arbeitsfläche | Karten und Editor |
|---|---|---|
| 390 px | Sichtbarer Menüknopf, Tabler-Collapse; Bereich und KW bleiben im Kopf. Aktionen umbrechen. | Eine Karte pro Reihe; Formular, dann Vorschau. Keine horizontale Dokumentbewegung. |
| 820 px, Hochformat | Collapse wie auf dem Smartphone, vollständig beschriftete Navigation im geöffneten Menü. | Zwei gleich breite Karten, sofern volle Inhalte/48-px-Aktionen passen; Editor grundsätzlich einspaltig. |
| 1024 px, Querformat | Weiterhin Collapse gemäss bestehender 1200-px-Schwelle. Kontext über dem Inhalt. | Zwei Karten; Hauptformular und optionale seitliche Vorschau nur bei ausreichend breiten Feldern, sonst darunter. Keine verkleinerte Desktop-Wochenmatrix. |
| 1440 px | Feste Sidebar, beschriftete Links; bestehende `container-xl`-/Breiteneinstellung. | Drei Karten in Sammlungen, zwei in Vergleichs-/Screensgruppen; Editor mit Eigenschaften und Vorschau nebeneinander. |

Zusätzlich die bestehenden Grenzfälle 1199/1200 px und Reflow bei 320 CSS-px prüfen.
Rotation verliert weder Formularinhalt noch Auswahl, Fokus oder Scrollposition unnötig.
Eine geöffnete Bildschirmtastatur darf Feld, Fehler und nächste Aktion nicht verdecken.
Sticky-Aktionen nur bei ausreichender Höhe; kein überdeckender zweiter Aktionsstreifen.

**Gleichheit bedeutet gleiche Breite und Höhe innerhalb derselben wiederholten Kartengruppe
bei gleichem Viewport**, auch über mehrere Rasterreihen. Verschiedene Semantikgruppen
(z. B. Eigenschaftenformular und PDF-Vorschau) müssen nicht dieselbe Höhe erhalten.
Eine Gruppe hat gemeinsame Kopf-, Medien-, Inhalts- und Fusszonen. Fussaktionen stehen
immer unten an derselben Position. `h-100` allein gleicht lediglich eine Bootstrap-Reihe
an und reicht für diese gruppenweite Forderung nicht aus. Zuerst CSS-Grid mit einheitlicher,
intrinsisch am längsten Inhalt bemessener Zeilenhöhe prüfen; kein JS-Höhenmesssystem als Default.

Alle Gerichtstitel, Komponenten, Hinweise und Deklarationen bleiben vollständig sichtbar:
kein `line-clamp`, Ellipsis, feste maximale Texthöhe oder innerer Kartenscroll zum Erzwingen
der Gleichheit. Lange Inhalte vergrössern die ganze Vergleichsgruppe. Leere Menüslots
behalten dieselbe Geometrie mit «Noch kein Gericht» und erreichbarer Anlegeaktion.

Medien verwenden gleiche reservierte Vorschaufläche pro Gruppe. Fehlendes Bild in einer
Bildgruppe erhält einen neutralen Platzhalter; ausdrücklich gewählte **Ohne-Bilder-Ansicht**
entfernt die Medienzone gruppenweit. Kein ungefragtes Ersatzbild und keine verbleibende
leere Fotofläche in der bildlosen Variante. Screens zeigen Web-/TV-Vorschau in ihrem richtigen
Seitenverhältnis innerhalb derselben Medienbox; Hochformat nicht beschneiden, sondern einpassen.
Vorschau ist keine komplette begehbare Website im kleinen iframe; voller Zugriff erfolgt
über beschrifteten Link. Vorhandenes `inert`/Fokusverhalten der Screens erhalten.

## 4. Symbolsprache und zulässige Verkürzung

Das Aktionsmakro `icon(name, class='', label=None)` nutzt den lokalen Tabler-Sprite.
Die folgenden Namen sind auf der Basis wirklich vorhanden, ohne Präfix `tabler-` aufgeführt.
Bei Icon+Text ist das SVG dekorativ. Bei icon-only bekommt **das interaktive Element** einen
eindeutigen Namen, z. B. «Randenrisotto bearbeiten, Montag Mittag»; nicht nur das Kind-SVG.

| Bedeutung | Vorhandenes Symbol | Sichtbare Darstellung |
|---|---|---|
| Wochenpläne / Verwaltung / neue Woche | `calendar-week` / `calendar-cog` / `calendar-plus` | Navigation und neue Woche: Icon+Kurztext. |
| Menüs / Komponenten / CSV | `tools-kitchen-2` / `components` / `file-import` | Navigation: Icon+Text; Bereich nicht nur aus Symbol ableiten. |
| Screens / Vorlagen | `eye` / `copy` | Bestehende Zuordnung zunächst behalten; Text unterscheidet sie von Aktionen. |
| API, Benutzer / Design | `info-circle` / `eye` | Bestehende Sidebar verwendet diese mehrfach; daher hier keine reine Symbolnavigation. |
| Anlegen / Bearbeiten / Speichern | `plus` / `pencil` / `device-floppy` | Wiederholtes Hinzufügen/Bearbeiten icon-only; Hauptaktion «Anlegen»/«Speichern» mit Text. |
| Kopieren / Archiv / Reaktivieren | `copy` / `archive` / `archive-off` | Kopieren in Karten icon-only, wenn Ziel klar; Archivieren/Reaktivieren mit Kurztext im Aktionsmenü. |
| Löschen / Zeile entfernen | `trash` | Persistentes Löschen mit Text und Bestätigung. Ungespeicherte optionale Zeile: icon-only mit kontextuellem Namen, ohne globale Löschsemantik. |
| Suchen / Zurücksetzen | `search` / `x` | Suchfeld sichtbar beschriftet; Suchbutton und lokales Zurücksetzen icon-only. Reset darf keinen gespeicherten Inhalt löschen. |
| Vorschau / Prüfen / Publizieren | `eye` / `clipboard-check` / `upload` | Vorschau in Karten icon-only; «Prüfen» und «Publizieren» mit Text. `upload` allein wäre mehrdeutig. |
| Zurück / Seite vorher, nachher | `arrow-left` / `chevron-left`, `chevron-right` | Pfeile icon-only bei beschrifteter Pagination; Kontextwechsel «Zurück zur Woche» mit Text. |
| Geprüft / Warnung / Hilfe | `circle-check` / `alert-triangle` / `info-circle` | Status mit Kurztext; Hilfe sichtbar als «Symbole». |
| Neu laden | `refresh` | Icon-only ausser bei Konflikten: dort «Aktuellen Stand laden». |

**Fehlende Symbole sind geplante Assetarbeit**, keine verfügbaren IDs: Filter (Trichter),
Drucken (Drucker), Uhrzeit (Uhr), Mittag/Abend (Sonne/Mond), eigene Screen-/Benutzer-/Design-
Piktogramme. Vor Umsetzung passende offizielle Tabler-Assets im gepinnten Bestand verifizieren,
lokal über den vorhandenen Vendorprozess aufnehmen und Paketprüfung aktualisieren.
Bis dahin «Filter», «Drucken» und Zeiten als Kurztext anzeigen; kein Aufruf erfundener Sprite-IDs.
OPS darf ein inzwischen integriertes `clock` verwenden, wenn dieser Zielstand es nachweist.

### Ernährung, Allergene und Herkunft sind Daten, keine Dekoration

`food_symbol` unterstützt auf dieser Basis nur exakte bekannte Codes in `allergens` und
`countries`; `labels` werden von `food_legend` textuell erhalten, haben aber **noch kein SVG**.
`_food_symbols.html` ist der bestehende gemeinsame Renderer. Keine Pfade aus Formwerten bauen.

| Fachbedeutung | Vertrag für die Darstellung |
|---|---|
| `VEGETARIAN` | Bestätigtes Kostformlabel «Vegetarisch». Vorschlag für neues lokales Symbol: Blatt mit sichtbarem Kürzel «VEG». Keine reine Farbdifferenz zum veganen Symbol. |
| `VEGAN` | Eigenständiges bestätigtes Label «Vegan». Vorschlag: Keimling mit sichtbarem Kürzel «VGN». Exakte Zeichenform in Asset-WP festlegen; bis dahin ausgeschriebene Namen. |
| Menüoption `VEGGIE` | Auswahl-/Slotbezeichnung «Vegetarisch», keine automatische `VEGAN`-Deklaration und kein Prüfbeleg. Ein Sloticon ist räumlich von den bestätigten Kostformlabels zu trennen. |
| Fleisch / Fisch als Gerichtstyp | Nur bei expliziter kanonischer Zuordnung; Titel, Foto, fehlendes Veggie-Label und Herkunftszeile sind kein Typnachweis. Noch kein bestätigter Fleisch-Labelcode/Sprite vorhanden. Vorgeschlagene Tier-/Fischpiktogramme erst nach Datenvertrag. |
| Allergen `FISH` | Vorhandenes lokales Allergensymbol bezeichnet die Fischdeklaration, nicht pauschal «Fischmenü». `may_contain` darf keine Gerichtskategorie erzeugen. |
| Deklarierte Allergene | Vorhandene Symbole der 14 Gruppen plus dauerhaft lesbares «Enthält: …» bzw. «Kann enthalten: …». Symbol/Code niemals als alleinige Sicherheitsinformation. |
| Geprüft | `circle-check` + «Geprüft» nur aus vorhandenem Prüfstatus/Beleg. Menüprüfung und Allergenprüfung nicht miteinander gleichsetzen. |
| Ungeprüft / Vorschlag | `clipboard-check` + «Prüfung offen» bzw. «Vorschlag – ungeprüft». BAS/REC-Importhinweise bleiben im Vorschlagsbereich; keine Übernahme in bestätigte Deklarationen ohne menschlichen Freigabeschritt. |
| Unbekannt / nicht erfasst | `info-circle` + «Nicht erfasst»; unbekannte Presence mit «Allergenangabe ungeklärt». Fehlende Allergene bedeuten niemals allergenfrei. Fehlende Labels bedeuten weder vegan noch Fleisch. |
| Herkunft | Lokale Flagge aus exaktem Ländercode plus Zutatenbezug und Ländername, z. B. «Rindfleisch · Schweiz». Keine Flagge als Herkunft des ganzen Menüs ausgeben. Unbekannter Code bleibt Text. |

Bestätigte Kostformbadges dürfen in dichten Übersichtskarten nach Einführung der unterschiedlichen
Symbole als Piktogramm+VEG/VGN erscheinen; voller Name bleibt über Fokus/Hover und Legende
verfügbar. Editor, Prüfung und bestätigte Deklarationsdetails zeigen den ausgeschriebenen Namen.
Keine automatische Labelvererbung aus Rezeptzutaten: BAS/REC-Freigabe- und Revisionsvertrag gilt.
Die Legende erklärt nur im aktuellen Abschnitt sichtbare Daten, erhält Presence-Unterschiede
und die Hinweise auf offene/fehlende Prüfung. Vollständige Menüausgaben und ihre eigene
Public-/Signage-/PDF-Legendenpolitik bleiben erhalten.

### Service und Zeit

Offen/Geschlossen mit eindeutigem Symbol **und** Kurztext; geschlossen immer mit gespeichertem
Hinweis. Keine rote/grüne Punktanzeige allein. Mittag und Abend bleiben benannt; Uhrzeit als
Ziffern, nicht als Uhrgrafik. Fehlende Zeiten erzeugen keine Standardzeit im Admin.
OPS: «Vorgabe, noch nicht gespeichert» bei synthetischen Services von gespeicherten Zeiten
unterscheiden; Zeiten in Europe/Zurich, bestehende Servicezeile vor Vorgabe, bewusste Übernahme
als eigene beschriftete Aktion. Wochenendbetrieb nicht durch ein Kalendericon implizit aktivieren.

## 5. Hover, Fokus und Touch: ein eindeutiger Vertrag

1. Icon-only-Aktion ist ein natives `button` oder `a`, mindestens **48×48 CSS-px**,
   mindestens 8 px Abstand zur nächsten Aktion. Keine anklickbaren `div`-Karten mit
   verschachtelten Buttons. Fokus ist sichtbar; Linknavigation bleibt echte Linknavigation.
2. Tooltip erscheint auf Maus-Hover **und Tastaturfokus**, beschreibt Aktion/Objekt und
   bleibt beim Überfahren der Tooltipfläche offen. Escape schliesst ohne Fokusverschiebung.
   Keine Links/Formulare im Tooltip; kein reines `title` als einzige Implementierung.
   Tabler-Initialisierung einmalig im lokalen vorhandenen JS; keine neue Frameworkinitialisierung.
3. Jede Aktionsgruppe hat Zugang zum sichtbaren **«Symbole»**-Hilfeknopf im Seitenkontext.
   Robuste Basis: natives `details`/`summary`, als Tabler-Fläche gestaltet, mit Symbol,
   ausgeschriebenem Namen und Bedeutung. Erster Tap öffnet ausschliesslich diese Legende;
   zweiter Tap auf denselben Schalter schliesst sie. Kein Long-Press-Zwang, kein Hilfemodus.
4. Erster Tap auf eine normale Vorschau-/Bearbeitenaktion führt sie regulär aus.
   Die Anwendung fängt den Tap nicht zum Tooltipzeigen ab. Wer Erklärung braucht, nutzt
   vorher «Symbole». Tastaturbedienung bleibt Enter/Space gemäss nativem Control.
5. Erster Tap auf eine gefährliche Aktion öffnet nur die vorhandene Bestätigung mit
   konkretem Objekt und Folge. Erst der separat beschriftete Bestätigungsbutton führt
   das POST aus. Abbrechen/Escape erhält Daten und gibt Fokus zurück. Publizieren und
   Aktivieren bleiben ausdrücklich benannt, mit unveränderten Versions-/Prüfbedingungen.
6. Nicht ausführbare Aktionen erhalten einen dauerhaft sichtbaren Grund und nächsten Schritt;
   Erklärung nicht ausschliesslich an einen deaktivierten, unfokussierbaren Button hängen.
   Ohne JS bleiben native Formulare/Links und die Symbollegende verwendbar.

Tooltips ergänzen Erklärungen; Gerichtsnamen, Labels von Eingabefeldern, Fehler,
Konflikte und sicherheitsrelevante Deklarationen dürfen nie ausschliesslich dort stehen.
Neue Tooltip-/Popovertechnik muss mit strikter CSP funktionieren. Kein `unsafe-inline`,
CDN, fremdes SVG oder HTML aus Nutzereingaben im Tooltip. Falls der lokale Tabler-Tooltip
CSP/Interaktion nicht erfüllt, gilt der beschriftete Fallback bis zur geprüften Anpassung.

## 6. Muster für Arbeitsflächen und Zustände

Formulare gruppieren Felder fachlich in Tabler-Cards/Fieldsets: Gericht, Komponenten,
Deklarationen, Herkunft. Sichtbare Labels bleiben, optionale Hinweise stehen einmal je
Gruppe. Wiederholte Zeilen benötigen eindeutige IDs; Checkbox-/Radiozeile ist vollständig
tappbar. Native Auswahl-, Datums-/Zeit- und Textfelder behalten Formnamen, CSRF, Versionen
und Servervalidierung. Ein Speichernpfad pro Formular, eine hervorgehobene Hauptaktion
pro Arbeitskontext; mehrere unabhängige Serviceformulare behalten ihre expliziten Submits.

Tabellen für echten Zahlen-/Zeilenvergleich; Kopfzellen und Beschriftung erhalten.
Unter 992 px bestehendes `table-mobile-lg` mit `data-label` oder gleichwertige semantische
Liste nutzen. Keine CSS-Umordnung gegen die Lesereihenfolge. Filter in einer gemeinsamen
Zeile, bei Platzmangel untereinander; aktive Filterwerte und Trefferzahl bleiben sichtbar.
Keine zweite versteckte Suche hinter einem unerklärten Trichtersymbol.

Editoren: Eigenschaften sind Tabler-Controls, Vorschau zeigt klar ihren Stand.
Bestehender Druckeditor behält Revision, Prüfen/Aktivieren, Wiederherstellen und PDF-Link.
Ein freier Canvas-/Blockeditor und Rezept-Richtext sind Backlog; dieses Manifest gibt
weder pdfme noch HugeRTE als neue Produktdependency frei. Ein bestehendes textarea bleibt
vollwertiger Fallback. Drag-and-drop benötigt erreichbare «Nach oben/unten»-Alternativen.

| Zustand | Sichtbare Reaktion und Fortsetzung |
|---|---|
| Laden/Speichern | Layoutstabile Ladeanzeige mit Aktionsname, `aria-busy`; Doppelsubmit verhindern, Eingaben erhalten, Fehler macht Aktion wieder möglich. |
| Leer | Konkreter Satz: «Noch keine Komponenten»; eine passende Anlegeaktion. Leere Suche getrennt: Filter ändern/zurücksetzen. |
| Fehler | Tabler-Alert und Fehler am Feld über `aria-describedby`/`aria-invalid`; Fokus zur Fehlerregion/erstem Fehler. Keine reine Toastfehlermeldung. |
| Konflikt 409 | «Zwischenzeitlich geändert» plus konkreter Kontext; Eingabe nicht verwerfen und nicht still überschreiben. Aktuellen Stand explizit laden; erneutes Senden nur nach Versionsabgleich. |
| Ungespeichert | Sichtbarer Hinweis «Ungespeicherte Änderungen» nach tatsächlicher Änderung; Navigation mit bestehenden Guard/Fallback absichern, kein erfundenes Autosave. |
| Gespeichert / publiziert | Rückmeldung unterscheidet Speichern von Publizieren. Vorschau LAST-SAVED, Screens publiziert, aktive Druckrevision jeweils sichtbar. |
| Unvollständig / Prüfung offen | Gelieferter Wochenstatus, offene Prüfungen und konkrete blockierende Schritte; kein clientseitig erfundener Status. |

### Konkrete Vorher/Nachher-Beispiele

- Menükarte: statt jeder wiederholten Schaltfläche «Bearbeiten» und «Vorschau» zwei
  feste Symbolziele `pencil`/`eye`. Gerichtstitel und «Prüfung offen» bleiben Text;
  zugänglicher Name enthält Tag, Mahlzeit und Gericht. Vorschau nur, wo bereits ein Ziel existiert.
- Deklaration: statt wiederholtem «Vegetarisch» in jeder dichten Karte künftig Blatt+VEG;
  Keimling+VGN ist erkennbar verschieden. «Enthält: Milch» bleibt ausgeschrieben, auch auf 390 px.
- Screens: Bereich/Kanal als Überschrift, Tabs «Tag», «Woche», «Ohne Bilder» mit Symbol;
  in der aktiven Ansicht eine klare Öffnenaktion. Bestehende unterschiedlichen Ziele behalten,
  Auswahlzustand und jeweils vollständigen Linknamen sichern; nicht alle als identisches Auge.
- Menüeditor: Plus am Ende der Komponentenliste statt wiederholtem «Komponente hinzufügen»;
  Name «Komponente hinzufügen», Gruppenüberschrift sichtbar. Speichern bleibt «Speichern».
- Vorlagen: Symbol für PDF-Öffnen, aber «Revision 4 prüfen und aktivieren» ausgeschrieben.
  Ein Auge darf keinen Wechsel der aktiven Druckvorlage auslösen.

## 7. Anwendung auf die vorhandenen Routenfamilien

`{family}` bezeichnet ausschliesslich `cafeteria` oder `patienten`; bestehende URL-Erzeugung
und Rechteprüfung erhalten. Die Pfade sind keine Einladung, neue Handler zu erstellen.

| Familie / belegter Einstieg | Anwendung / besondere Grenze |
|---|---|
| `/admin/{family}`, Wochenverwaltung über `admin.week_management` | Woche/Bereich oben, gleiche Menüslots, Serviceformulare, kompakte wiederholte Aktionen. Patienten bleiben vollständig preisfrei, auch Attribute. OPS kann 5-/7-Tage-Raster ändern; Slotzahl nicht neu hardcoden. |
| `/admin/{family}/menu`, `…/komponenten`, `…/menues` | Tabler-Editor/Katalog/Sammlung, gemeinsame Actionposition, deklarierte Daten vollständig. Archiv und Verwendung sichtbar. |
| `admin.import_preview`, `/admin/{family}/copy`, Wochenprüfung | Quelle/Ziel, Korrektur und Freigabe lesbar; Importvorschau nicht als gespeicherten Inhalt darstellen. Copy-Formvertrag erhalten. |
| `/admin/{family}/preview` | LAST-SAVED und Woche sichtbar; keine Publikationsfallbacks. Vollständige gleich grosse Karten und passende Legende. |
| `admin.screens` / `admin.vorlagen` | Bestehende Web-/Signage-, Tages-/Wochen- und Ohne-Bilder-Varianten; gleiche Gruppengeometrie, echter Vollansichtslink. |
| `/admin/vorlagen/{family}` | Eigenschaften/gespeicherte PDF-Vorschau, Revision, Aktivieren und Verlauf mit Tabler. Kein Ersatz des Datenmodells durch einen Fremdeditor. |
| `/admin/design/darstellung`, `admin.branding_editor` | Bestehende Dichte, Textgrösse, Inhaltsbreite und Markenoptionen; Vorschau als ungespeichert kenntlich, Speichern explizit. |
| `admin.local_users_list`, `admin.api_overview` | Rechte/Benutzerstatus und sensible Aktionen benannt; keine Geheimnisse in Tooltips oder Vorschaukarten. Sichtbarkeit folgt bestehenden Fähigkeiten. |
| OPS `/admin/bereiche-zeiten` | Noch nicht auf Dokumentbasis integriert. Nach Freeze: Anzeigenamen, Wochenvorgaben, datierte Ausnahmen, sichtbare Zeitzone und gespeicherter/vorgegebener Stand. |
| BAS/REC, Einkauf, Kalkulation | Zukunft laut Backlog, keine erfundenen URLs. Dieselben Muster erst auf freigegebenen Daten-/Rechteverträgen anwenden; bestätigte Daten und Vorschläge getrennt. |

## 8. Messbare Abnahme für die spätere Umsetzung

Alle folgenden Produktprüfungen sind **geplant, in diesem Dokument-WP nicht ausgeführt**.
Bestehende Tests sind Anknüpfungspunkte, keine Behauptung, dass sie bereits jeden neuen Fall testen.
Testpfade relativ zu `reference_scaffold/tests/`; Tools liegen im Repository unter `tools/`.

| Gate | Messkriterium | Vorhandener Ansatz / erforderliche Ergänzung |
|---|---|---|
| Responsive | 390/820/1024/1440 und 1199/1200 px, beide Orientierungen; Dokumentbreite ≤ Viewport; 320-px-Reflow und 200% Textvergrösserung. | `test_admin_tabler_browser.py`, `test_admin_week_tabler_browser.py`; neue Viewports ergänzen. |
| Geometrie/Inhalt | Jede Karte derselben Gruppe: Breite/Höhe höchstens 1 CSS-px Differenz, auch unterschiedliche Rasterreihen. Keine abgeschnittenen Titel/Komponenten/Deklarationen. | `test_admin_week_equal_cards_browser.py`, `test_preview_equal_cards_browser.py`; mehrreihige Extremdaten ergänzen. |
| Extremdaten | Längster erlaubter Titel, viele Komponenten, alle Allergene mit beiden Presence-Werten, lange Länder-/Bereichsnamen, leere Slots, gemischte Bilder und bewusst bildlos. | `test_food_legends_admin.py`, `test_menu_metadata_visibility.py`, `test_public_week_no_images.py`; Kombinationen ergänzen. |
| Touch | Alle Aktionsrechtecke ≥48×48 px, Abstand ≥8 px; Legende mit erstem Tap offen, normale Aktion mit erstem Tap wirksam, gefährlicher Tap ohne sofortige Mutation. | `test_admin_ux_browser.py`; neue Touchfälle plus echtes Tablet mit Modell/OS/Browser protokollieren. |
| Tastatur/Screenreader | Jede Aktion benannt; sichtbarer Fokus; Tooltip auf Fokus/Hover, Escape, Überfahren; Legende per Tastatur, Fokus nach Bestätigung zurück. Keine Tooltipfallen. | `test_week_form_focus_browser.py`, `test_admin_menu_editor_browser.py`; neue Tooltip-/Namensprüfungen und manuelle Screenreaderprüfung. |
| Fachwahrheit | Vegan ≠ vegetarisch ≠ `VEGGIE`-Slot; unbekannt ≠ frei; Vorschlag ≠ deklariert; Presence und Herkunft erhalten. | `test_food_symbols.py`, `test_food_legends_admin.py`, `test_menu_metadata_visibility.py`; Label-/Vorschlagsfälle ergänzen. |
| Zustände | Fehler, 409, ungespeichert, Laden, leere Suche, geschlossener Service ohne Datenverlust/Überdeckung. | `test_admin_form_contracts.py`, `test_admin_menu_save_back_browser.py`, `test_week_review_browser.py`. |
| Screens/Editor | Jede Tabvariante und bildlose Ausgabe erreichbar; richtige Vorschauquelle, aktive Revision, vollständiger PDF-Inhalt. | `test_admin_screens_preview_browser.py`, `test_print_template_browser.py`, `test_admin_display_options_browser.py`, `test_week_pdf.py`. |
| Assets/CSP | Keine externen Requests/Inlinefreigaben/CSP-Verletzungen; jedes referenzierte Spriteziel vorhanden; 0 unbekannte Label-Assets. | `test_food_symbol_assets.py`, `test_tabler_package_verification.py`, Browserkonsole/Netzwerk prüfen; `tools/validate_package.py`. |
| Auslieferungsnachweis | Frischer Commit-/URL-/Viewportbeleg, Browserinteraktion plus Screenshot, keine Übernahme alter PASS-Zahlen. | `tools/admin_tabler_proof.py`, `tools/capture_admin_live_proof.py`; Root führt freigegebene Zielumgebung. |

WCAG-Ziel: AA-Kontrast (normaler Text 4,5:1, grosser Text 3:1, notwendige UI-Grafik 3:1),
keine Farbalone-Zustände, sichtbarer unverdeckter Fokus. **48 px ist der Projektstandard**,
nicht die Behauptung, WCAG fordere genau 48 px. Ein Screenshot beweist weder Touch noch Fokus.

## 9. Priorisierte, dateigetreue Umsetzungswellen

Diese WPs werden hier nur vorbereitet. Root weist vor Dispatch isolierte Worktrees und genaue
Testdateien zu. Gemeinsame Dateien haben immer genau einen Eigentümer. Keine Arbeit am aktiven
OPS-Kandidaten, bevor Root dessen Freeze/Integration bestätigt hat.

| Welle | Eigentum und Ergebnis | Abhängigkeit |
|---|---|---|
| P0 – Vertrags-/Assetowner | `tools/vendor_tabler.py`, lokaler Tabler-Sprite und zugehörige Vendorbelege; bestätigte neue Icon-IDs und VEG/VGN-Zuordnung festlegen. Bei Labelhelper-Änderung auch alleiniger Besitz `food_symbols.py`, `_food_symbols.html` samt Symboltests. Keine Dateninferenz. | Root bestätigt Target-HEAD und Code-Impact; Vendor/Paketmanifest-Wiring ausschliesslich Root. |
| P1 – Shell-/Interaktionsowner | `templates/admin/_macros.html`, `base_tabler.html`, `_workflow_sidebar.html`, `static/admin.js`, `static/admin-tabler.css`; Namen/Tooltip/Legende, 48-px-Geometrie, Fallback und Fokus zentral. | Nach P0; OPS-Sidebaränderungen zuerst integrieren. Diese Dateien danach für Folgelanes gesperrt. |
| P2a – Wochen-/Menüowner | `cafeteria.html`, `patienten.html`, `menu_editor.html`, `week_review.html` und genau deren Styles/Tests nach Zuweisung. Gleiche Karten, unveränderte Formverträge. | P1, OPS-Freeze. Kein `admin/rendering.py` ohne separaten Vertragsowner. |
| P2b – Katalogowner | `components.html`, `component_editor.html`, `menu_collection.html`, zugehörige exklusive Styles/Tests. | Parallel P2a, nur gefrorene Makros konsumieren. |
| P2c – Ausgabe-/Einstellungsowner | `screens.html`, `vorlagen.html`, `print_template_editor.html`, `display_settings.html`, `branding_editor.html`, zugehörige exklusive Styles/Tests. Vorschauen und bildloser Modus. | Parallel P2a/b; keine Public-/Signage-/PDF-Datenänderungen. |
| P3 – Rest-/Zukunftsowner | Copy/Import, Benutzer/API, dann OPS-Restpolitur und später BAS/REC jeweils als eigene kleine file-disjoint WPs. | Daten-/Rechteverträge zuerst; keine vorgetäuschten Zukunftsrouten. |
| R – Root Integration | Renderer-Kontext, Routenregistrierung, Paketmanifest und gemeinsame Testfixtures; Diffs/GitNexus, echte Browser-/Touch-/Fachgates, anschliessend freigegebene Auslieferung. | Nach jeder kleinen abgeschlossenen Welle; kein paralleles Schreiben derselben Vertragsdatei. |

Bei neuen Symbolen/GitNexus-Symboländerungen muss jede Write-Lane den Impact vor dem Edit
prüfen; Shared-Helper sind kein stiller Nebenedit. Nicht bestandene Gates bleiben offen.

## 10. Primärquellen und tatsächliche Dokumentprüfung

Am 7. September 2026 gelesen; externe Empfehlungen ersetzen weder lokale Versionsprüfung
noch Browserabnahme:

- [Tabler Tooltips](https://docs.tabler.io/ui/components/tooltips): vorhandenes Komponentenmodell
  und Datenattribute als Ausgangspunkt; Fokus-/Touch-/CSP-Vertrag oben zusätzlich prüfen.
- [Tabler Cards](https://docs.tabler.io/ui/components/card): bestehende Kopf-/Inhalts-/Fussstruktur;
  gruppenweit gleiche Höhen sind die ergänzende Dishboard-Anforderung.
- [WAI Tooltip Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/tooltip/): Fokus bleibt auf
  Auslöser, Escape, `aria-describedby`; die APG kennzeichnet dieses Muster ausdrücklich als
  noch nicht konsentierten Entwurf, nicht als normative WCAG-Pflicht.
- [WCAG 1.4.13](https://www.w3.org/WAI/WCAG22/Understanding/content-on-hover-or-focus.html):
  Zusatzinhalt schliessbar, überfahrbar und beständig halten.
- [WCAG 2.5.5](https://www.w3.org/WAI/WCAG22/Understanding/target-size-enhanced.html):
  44×44 CSS-px für das erweiterte AAA-Ziel mit Ausnahmen; Dishboard setzt einheitlich 48×48.
- [WCAG Reflow](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html):
  Umbruch statt horizontalem Seitenscroll bei schmalem Darstellungsbereich.

Tatsächlich ausgeführt: lokaler Worktree-/HEAD-/Quellenabgleich, GitNexus Query/Context,
Indexierung des eigenen Alias. Abschlussbeleg mit `git diff --check`, Scopeprüfung,
`gitnexus_detect_changes` und Commit steht im WP-Report. Keine App-/Browser-/Touchtests
für diesen reinen Dokument-WP. OCR nicht verfügbar: Root meldete bereits zwei 429-Versuche;
kein erneuter Lauf, kein behauptetes PASS. Dieses Manifest ist damit reviewbar, aber kein
OCR-geprüfter oder visuell abgenommener Produktstand.
