> Paketkopie des bestehenden Nachbesserungsauftrags. Nur lokale Bildpfade wurden angepasst. Ergänzende Bildzuordnung, Freigaben und neue Referenzpaare: [UI_REFERENZEN.md](UI_REFERENZEN.md).

# Dishboard: verbindlicher Kritik- und Nachbesserungsauftrag

## Auftrag an den Coding-Agenten

Die bisherige UI-Überarbeitung ist für die hier gezeigten Ansichten noch nicht abnahmefähig. Teile der Farbwelt, Überschriften und aktiven Zustände wurden angepasst. Die grundlegende Vereinfachung des Arbeitsablaufs ist dagegen nicht konsequent umgesetzt. Grosse Bilder, zusätzliche Karten und neue Rahmen ersetzen diese Arbeit nicht.

**Überarbeite die vorhandene Anwendung, statt ein weiteres unverbindliches Konzept zu liefern.** Benutzer sind Küchenmitarbeitende mit sehr geringer technischer Erfahrung. Sie müssen Aufgaben durch verständliche Beschriftungen und sichtbare Aktionen erledigen können. Die Oberfläche soll zugleich ruhig, hochwertig und zusammengehörig aussehen.

**Flask, Tabler und der technische Unterbau bleiben unverändert.** Dieser Auftrag ergänzt das bestehende UI/UX-Konzept; er ersetzt weder dessen Schutzregeln noch bestehende Projektanweisungen.

---

## 1. Pflichtlektüre, Prüfgrundlage und Grenzen

Lies die bestehende `AGENTS.md` sowie `docs/UI_UX_KONZEPT.md` vollständig. Falls das Konzept noch nicht im Repository liegt, verwende die mitgelieferte Kopie unter `grundlagen/UI_UX_KONZEPT.md`. `grundlagen/AGENTS_UI_UX_REFERENZ.md` ist eine Referenz, kein Auftrag, die Projektdatei zu überschreiben.

Prüfe diese vier neuen Ist-Screenshots:

| Referenz | Datei | Sichtbarer Bereich |
|---|---|---|
| R1 | `ist/R1-menues.png` | Gespeicherte Menüs aus mehreren Wochen, Bildkarten, Prüfhinweise. |
| R2 | `ist/R2-wochenverwaltung.png` | Neue Woche anlegen und gespeicherte Wochen. |
| R3 | `ist/R3-baustein-bearbeiten.png` | Basmatireis bearbeiten, Kennzeichnungen und Allergenfelder. |
| R4 | `ist/R4-druckvorlagen.png` | Ausgabe-/Druckvorlagen, PDF-Aktionen und Versionsangaben. |

**Beweisgrenze:** Die Screenshots belegen sichtbare Gestaltung und Beschriftung. Sie beweisen weder Formularverhalten noch Datenmodell, Berechtigungen, JavaScript, mobile Darstellung oder serverseitige Prüfungen. Trenne im Review:

- **Sichtbar nicht erfüllt:** Ein Widerspruch zum Konzept ist auf einer gezeigten Seite erkennbar.
- **Teilweise erfüllt:** Einzelne Aspekte sind sichtbar verbessert, andere fehlen.
- **Nicht beurteilbar:** Die relevante Ansicht oder Interaktion ist nicht gezeigt. Im laufenden Projekt prüfen, nicht als fehlend behaupten.

Insbesondere sind der eigentliche Wochenplan, dessen Raster, der Menüeditor, ein seitliches Bearbeitungsfenster und die Smartphoneansicht in R1–R4 nicht zu sehen. R2 ist die Wochenverwaltung, nicht der Wochenplan. R3 ist ein zentraler Bausteineditor, nicht der Menüeditor. Verwechsle diese Seiten nicht.

### Rangfolge bei widersprüchlichen Referenzen

Ausdrückliche Projekt-/Sicherheitsregeln und technische Schutzgrenzen haben Vorrang. Danach gelten das verbindliche Textkonzept und dieser konkretisierende Nachbesserungsauftrag. Das früher generierte Mockup dient nur als grobe Stilreferenz.

**Das Mockup war nicht in allen Details konsistent mit dem Konzept:** Es zeigte unter anderem zusätzliche Menüarten, viele Navigationseinträge, dominante Essensbilder und eine nicht zur dargestellten Menge passende Statuszählung. Diese Abweichungen sind keine freigegebenen Anforderungen. Keine zusätzlichen Menüarten, erfundenen Kennzahlen, dekorativen Sprüche oder neuen Funktionen daraus übernehmen.

### Unveränderlicher technischer Rahmen

Erlaubt sind bestehende Jinja-Templates und Partials, projektbezogenes CSS, kleine UI-Ergänzungen im bestehenden JavaScript-Assetweg, Tests und Dokumentation. Verwende die tatsächlich installierten Tabler-Komponenten.

Nicht erlaubt sind neue Frameworks oder Laufzeitabhängigkeiten, Paketupgrades als Voraussetzung, Datenbankmigrationen, neue Datenfelder/Statuswerte, neue API-/Schreibrouten, geänderte Formularverträge, neue Prüf-/Publikationslogik, Änderungen an Authentifizierung/Berechtigungen oder ein Deploymentumbau. Python-View-Anpassungen benötigen die gesonderte Freigabe aus dem Konzept. Keine produktiven Testveröffentlichungen.

Vorhandene Formulare müssen mit denselben URLs, Methoden, Feldnamen, Enumwerten, CSRF-Regeln und fachlichen Wirkungen funktionieren. Ein schönerer Feldname im UI berechtigt nicht zur Änderung eines `name`-Attributs. Fehlende Fähigkeiten werden dokumentiert, nicht als Attrappe dargestellt.

---

## 2. Konkreter Befund: Was noch nicht umgesetzt ist

| ID | Priorität | Sichtbarer Befund | Bezug zum Konzept |
|---|---|---|---|
| N01 | P0 | Die Sidebar zeigt weiterhin 14 weitgehend gleichrangige Fach-/Verwaltungseinstiege. Wochenpläne und Wochenverwaltung sind getrennt; technische Einstellungen stehen neben der täglichen Arbeit. | NAV-01, NAV-02, UX-04 |
| N02 | P0 | In R1 steht ein grünes „Geprüft“ gleichzeitig über „Ungeprüfter Rezepturhinweis“ und „Allergenangaben nicht erfasst“. Die Bedeutung der Prüfung ist für Benutzer widersprüchlich. Ob die Ursache Daten, Freitext oder Fachlogik ist, ist ungeklärt. | SAFE-01–03, STATE-01–03 |
| N03 | P1 | Zwischen Navigation und Inhalt bleibt eine breite Leerzone. Listen, Formulare und Ausgabeseiten wirken wie Inseln innerhalb derselben begrenzten Mittelsäule. | VIS-03, VIS-04 |
| N04 | P1 | R1 priorisiert grosse Bilder und lange Hinweise. Im sichtbaren Ausschnitt dominieren drei hohe Karten; die Bearbeitungsaktionen werden an den unteren Bildrand gedrängt. | UX-01–04, LIST-01, WEEK-05 als gemeinsames Kartenprinzip |
| N05 | P1 | R2 zeigt zuerst ein grosses dauerhaft offenes Erstellformular, erst danach die bereits vorhandenen Wochen. Seltene Einrichtung verdrängt die häufige Auswahl/Bearbeitung. | UX-04, NAV-01, WEEK-02 |
| N06 | P1 | In R3 stehen neben nicht angekreuzten Allergenen bereits Auswahlfelder mit „enthält“. Zwei Bedienelemente vermitteln einen unklaren Zustand; die lange Liste dominiert das Formular. | UX-02, SAFE-01, A11Y-04 |
| N07 | P1 | R4 vermischt Woche auswählen, PDF öffnen, veröffentlichten Plan drucken, Drucklayout bearbeiten, Versionsprüfung und Inhaltsverwaltung. Der passende nächste Schritt ist nicht eindeutig. | UX-01, UX-03–06, OUT-02 |
| N08 | P1 | „Revision“, „Publizierten Plan“, „Komponenten“, „Grundlagen“ und „Screens“ sind weiterhin prominent. R1 enthält eine isolierte Zeile „Symbole“, deren Nutzen im Screenshot nicht erkennbar ist. | UX-06, NAV-01, LIST-01 |
| N09 | Prüfen | Texte und einige Controls wirken weiterhin klein. Exakte CSS-Grössen, Zoom und Klickflächen lassen sich aus den Bildern nicht verlässlich bestimmen. | VIS-02/03, A11Y-01–06 |

P0 bedeutet: zuerst bearbeiten und vor Abnahme klären. Es ist keine Erlaubnis, dafür den technischen Rahmen zu überschreiten.

---

## 3. Verbindliche Nachbesserungen

### A. Gemeinsamen Seitenrahmen und Navigation tatsächlich vereinfachen

**Nicht vier Überschriften über dieselben 14 dauerhaft sichtbaren Links setzen.** Die Hauptebene erhält höchstens vier fachliche Einstiege. Unterseiten erscheinen im passenden Arbeitsbereich, nicht weiterhin als gleichrangige Hauptnavigation.

| Haupteinstieg | Hierhin gehören die bestehenden Funktionen |
|---|---|
| **Wochenplan** | Plan bearbeiten, Woche auswählen, Wochenübersicht, vorhandene Woche-anlegen-/Kopieraktionen. |
| **Menüs & Bausteine** | Geplante Menüs, Bausteine, Zutaten sowie die inzwischen sichtbaren Rezepte und Kochbücher. Fachliche Unterschiede erhalten. |
| **Vorschau & Bildschirme** | Bestehende Vorschauen, Bildschirme, Wochenplan drucken, Drucklayouts und Rezeptdruck. |
| **Einstellungen** | Bereiche/Öffnungszeiten, Erscheinungsbild, Datenimport, Schnittstellen, Benutzer/Zugriff und seltene technische Stammdaten. |

Konto und Abmelden bleiben unten getrennt. Sichtbarkeit folgt den bestehenden Rechten. Auch für Administratoren wird die Navigation geordnet; der Adminstatus ist kein Grund für 14 gleichrangige Einstiege.

Erstelle eine vollständige Alt-neu-Zuordnung aller Links. Bestehende URLs und direkte Aufrufe bleiben gültig. Keine Funktion durch Aufräumen entfernen. Zusätzliche Unterseiten dürfen nicht zu neuen versteckten Navigationsebenen ausarten.

Richte den Inhalt im verfügbaren Bereich **rechts neben** der Sidebar aus. Verwende den gemeinsamen Seitenrahmen statt individueller Zentrierungs-Tricks pro Seite. Desktop-Seitenabstände liegen grundsätzlich bei 24–32 CSS-Pixeln. Listen nutzen die verfügbare Breite bis etwa 1440 Pixel; normale Formularinhalte bleiben etwa 760–960 Pixel breit und erhalten nur bei ausreichend Platz einen seitlichen Kontextbereich. Nicht alle Eingabefelder blind auf Bildschirmbreite ziehen.

**Abnahme:** Die vier gezeigten Seiten haben dieselbe Inhaltskante, Kopfstruktur und Navigationslogik. Ein Benutzer findet eine vorhandene Woche, einen Baustein und die Druckausgabe, ohne die internen Verwaltungsbegriffe kennen zu müssen.

### B. Prüfstatus verständlich und wahrheitsgetreu darstellen

Untersuche im Bestand, was das grüne „Geprüft“ in R1 tatsächlich bestätigt. Ermittle getrennt die Herkunft des Prüfkennzeichens, der Allergenangaben und des unbestätigten Rezepturhinweises. Der Freitext könnte veraltet sein; das ist zu prüfen, nicht vorauszusetzen.

Ein einzelnes unqualifiziertes grünes Gesamtbadge darf fehlende Angaben nicht überdecken. Zeige den vorhandenen Prüfstand mit seinem belegten Geltungsbereich und fehlende Deklarationsangaben unmittelbar daneben. Beispielhafte Struktur, **nur nach bestätigter Datenzuordnung**:

> Status des gespeicherten Menüs: Geprüft  
> Allergenangaben: Nicht erfasst  
> Interner Prüfhinweis vorhanden · Hinweise anzeigen

Die konkreten Wörter müssen den tatsächlichen Bestand erklären. Keine neue Bedeutung wie „Rezept geprüft“ erfinden, wenn die Prüfung etwas anderes betrifft. Warnhinweise bleiben in der Übersicht erkennbar; lange Erläuterungen können in die Detailansicht.

Keine automatische Ableitung aus Titel, Bild oder Rezepturhinweis. Keine Bestätigung leerer Allergenlisten. Keine stille Änderung gespeicherter Prüfstände. Keine neue Freigabesperre nur im Browser. Erkennt die Bestandsprüfung einen fachlichen Widerspruch, dokumentiere ihn separat und eskaliere die notwendige Entscheidung. Unabhängige Layoutarbeiten können weiterlaufen.

**Abnahme:** Bei der Kombination „Geprüft + fehlende Allergene + ungeprüfter Hinweis“ erkennt der Benutzer sofort, welche Angabe vorhanden und welche noch nicht erfasst ist. Der tatsächliche gespeicherte Status wird weder verfälscht noch als umfassendere Zusicherung dargestellt.

### C. Die Menüliste zur nutzbaren Übersicht machen

R1 beschreibt gespeicherte **geplante Menüeinträge aus verschiedenen Wochen**, keinen automatisch wiederverwendbaren Rezeptkatalog. Erhalte diese Bedeutung. Erzeuge aus dieser Liste weder neue Rezepte noch eine neue „Zur Woche hinzufügen“-Funktion.

Baue die Standardansicht textorientiert und kompakt auf. Die vorhandene Listenansicht kann Standard werden, sofern Karten weiterhin sinnvoll erreichbar bleiben. Suche, Bereichswechsel und Ansichtsauswahl bilden eine zusammenhängende Werkzeugleiste statt mehrerer voneinander isolierter Flächen.

| Reihenfolge pro Eintrag | Darstellung |
|---|---|
| Orientierung | Lesbares Datum, Mahlzeit und Menüart. |
| Inhalt | Vollständiger Menüname und kurze Zusammenfassung der Bausteine. |
| Datenlage | Verständlicher Prüfstand; fehlende wichtige Angaben direkt sichtbar. |
| Hauptaktion | **„Im Wochenplan öffnen“**, wenn dies der tatsächliche bestehende Link tut. |
| Details | **„Hinweise anzeigen“** für lange interne Prüfnotizen; keine versteckte Pflichtinformation. |

Die Kernaktion steht unmittelbar am relevanten Inhalt. Nicht nur einen Stift zeigen und nicht voraussetzen, dass Benutzer auf ein Foto klicken. Namen dürfen umbrechen. Keine feste Mindesthöhe, die bei kurzen Inhalten grosse leere Karten erzeugt; ebenso keine feste Maximalhöhe, die Warnungen oder Aktionen abschneidet.

**Bilder:** Im verbindlichen Konzept sind generierte Essensbilder kein zulässiges neues Gestaltungselement. Das spätere Mockup widersprach dem an dieser Stelle. Keine weitere Bildgenerierung oder neue Bildfunktion einbauen. Bereits gespeicherte Bilder nicht löschen. Sie dürfen die Standardübersicht nicht dominieren; vorhandene Bildansichten bleiben nachgeordnet erreichbar und behalten den sichtbaren Hinweis „KI-generierter Serviervorschlag“. Ein Foto ist weder Deklaration noch Nachweis des tatsächlichen Gerichts.

Prüfe die isolierte Zeile „Symbole“. Ist sie eine notwendige Legende, benenne sie konkret, beispielsweise „Kennzeichnungen erklären“, und ordne sie bei den betroffenen Informationen ein. Ist sie ein leeres oder defektes Darstellungselement, behebe es. Nicht ungeprüft entfernen.

**Abnahme:** Ohne Öffnen jeder Karte erkennt man, welches Menü zu welchem Tag gehört, welche Angaben fehlen und wie man genau diesen Eintrag öffnet. Fotos und Langtexte stehen nicht vor der eigentlichen Aufgabe.

### D. Wochenübersicht: bestehende Woche zuerst, neue Woche bei Bedarf

Ordne die vorhandene Wochenverwaltung unter „Wochenplan → Wochenübersicht“ ein. Stelle gespeicherte Wochen und den eindeutigen Weg „Woche öffnen“ in den Vordergrund.

„Neue Woche anlegen“ öffnet das bereits vorhandene Formular bei Bedarf. Keine automatische Erstellung beim Seitenaufruf und kein neuer Backendablauf. Bei serverseitigen Formularfehlern bleibt der Erstellbereich offen, die Eingaben bleiben sichtbar und der Fehler ist zugeordnet.

Zeige pro Woche zunächst den verständlichen Datumsbereich, dann die Kalenderwoche und den vorhandenen Status. „Live“ wird nur dann „Veröffentlicht“, wenn das dessen tatsächliche Bedeutung ist. Eine ISO-Kalenderwoche kann Montag–Sonntag umfassen, während die Cafeteria nur Montag–Freitag bedient: nicht pauschal gespeicherte Wochen auf fünf Tage umschreiben.

„Woche öffnen“ ist die klare Zeilenaktion. Vorschau und vorhandene Kopierfunktionen sind nachgeordnet, beschriftet erreichbar. Beim Kopieren müssen Quelle, Ziel und tatsächliche Wirkung deutlich sein; keine unbelegte Zusicherung zum Überschreiben oder Übernehmen von Prüfständen.

Pagination nur zeigen, wenn es tatsächlich weitere Seiten gibt. R2 zeigt „Seite 1“; ob weitere Seiten vorhanden sind, muss der Agent prüfen.

**Abnahme:** Beim Öffnen der Seite kann man zuerst eine vorhandene Woche wählen. Das Erstellformular nimmt den Arbeitsplatz nur während der Erstellung ein. Bestehende Erstell- und Kopierverträge bleiben identisch.

### E. Bausteineditor: die Allergenbedienung entwirren

R3 bearbeitet einen zentralen Baustein. Zeige im Kopf „Baustein bearbeiten · Basmatireis“. Erläutere den Begriff bei Bedarf einmal kurz: „Zum Beispiel eine Beilage, Sauce oder ein Gemüse.“

Ordne die vorhandenen Felder in klar benannte Abschnitte: Name/Kategorie, Herkunft/Kennzeichnungen, Allergene. Der Kontextbereich enthält Verwendung und Status. Archivieren ist eine nachgeordnete, getrennte Aktion; „Baustein speichern“ ist die primäre Formularaktion.

Die Allergenliste darf nicht gleichzeitig „nicht ausgewählt“ und scheinbar „enthält“ vermitteln. Verwende eine konsistente Zeile je Allergen. Eine zugehörige Auswahl „enthält / kann enthalten“ ist nur als aktiv erkennbar, wenn das betreffende Allergen tatsächlich ausgewählt ist. Bereits gespeicherte Angaben und Fehlermeldungen müssen sofort sichtbar bleiben. Alle weiteren Allergene bleiben per beschrifteter, tastaturbedienbarer Aktion erreichbar.

**Achtung Formularvertrag:** Ausblenden ist nicht dasselbe wie `disabled`. Deaktivierte Controls können aus der Formularübertragung verschwinden. Prüfe vor jeder Änderung, welche Feldkombinationen der Server heute erwartet. Weder Werte verlieren noch versteckte alte Werte unbeabsichtigt speichern. Kein neues Feldformat und keine neue Zustandslogik einführen.

Zeige die bestehende Bedeutung klar: **„Nicht ausgewählt bedeutet nicht: allergenfrei bestätigt.“** Biete „nicht enthalten“ oder eine vollständige Freigabe nur an, wenn der Bestand diese Zustände wirklich unterstützt. Kennzeichnungen wie vegan oder glutenfrei bleiben vorhandene eigenständige Daten, keine Ableitung aus dem Namen.

Erkläre den Geltungsbereich zentraler Änderungen anhand des Codes. „Wird in 4 Gerichten verwendet“ belegt allein nicht, ob eine Änderung bereits geplante oder veröffentlichte Menüs verändert. Keine falsche Zusicherung zur Unveränderlichkeit alter Pläne.

**Abnahme:** Keine scheinbar aktive „enthält“-Angabe neben einer inaktiven Auswahl; bestehende Daten überstehen Öffnen und unverändertes Speichern. Ausgewählte Allergene, Validierungsfehler und Bedienaktionen sind mit Tastatur und Touch erreichbar.

### F. Druckausgabe und Drucklayout sauber trennen

R4 zeigt **Druck-/Ausgabevorlagen**, keine Menüvorlagen zum Befüllen einer Woche. Diese Unterscheidung ist verbindlich.

Die Standardaufgabe lautet: **Bereich wählen → Woche wählen → passende PDF-/Druckausgabe öffnen.** Zeige dafür den tatsächlich gewählten Bereich und Zeitraum. Die primäre Aktion benennt das Ziel, beispielsweise „PDF der gewählten Woche öffnen“.

Trenne insbesondere:

| Aufgabe | Verständliche Oberfläche |
|---|---|
| Gewählte gespeicherte Woche ansehen/drucken | „PDF der gewählten Woche öffnen“, mit tatsächlich ausgewähltem Zeitraum. |
| Aktuell veröffentlichten Plan drucken | „Veröffentlichten Plan drucken“, mit eigenem Datenstand. Nicht behaupten, dass dies die ausgewählte Woche ist. |
| Gestaltung der Ausgabe bearbeiten | Nachgeordneter Bereich „Drucklayout ändern“. |
| Entwurf prüfen oder aktivieren | Gespeicherten Entwurf, aktive Version und tatsächliche Vorschau klar unterscheiden. Bestehende Aktivierungsaktion erhalten. |
| Ältere Versionen ansehen | „Frühere Versionen“, nicht wiederholt „Revision 1“ auf der Hauptarbeitsfläche. |
| Rezeptausgabe | Eigener klarer Unterbereich „Rezepte drucken“ bzw. „Rezept-Drucklayout“, entsprechend der vorhandenen Funktion. |

Die beiden Zielgruppen nicht als zwei umfangreiche, ständig parallele Verwaltungsformulare darstellen. Verwende eine klare Bereichsauswahl oder einen vergleichbar eindeutigen, vorhandenen Navigationsweg. Patienten- und Cafeteriaausgabe bleiben fachlich getrennt; Patienten erhalten keine Preise.

Verweise zu Wochen, Menüs und Bausteinen stehen bei Bedarf gesammelt unter „Inhalte bearbeiten“. Sie konkurrieren nicht als gleichrangige Buttonreihe mit der Druckaufgabe. Für die Vorschau einer festgeschriebenen Rezeptversion bleibt deren tatsächliche Auswahl erhalten; nur die technischen Begriffe werden verständlicher.

Keine neue PDF-Engine, kein neuer Vorschau-Endpunkt, keine Veränderung der veröffentlichten Ausgabestände. Unterschiedliche vorhandene Aktionen nicht unter einem irreführenden gemeinsamen Button zusammenlegen.

**Abnahme:** Ein unerfahrener Benutzer kann erklären, ob er die ausgewählte gespeicherte Woche, den veröffentlichten Plan oder einen Layoutentwurf öffnet. Für normales Drucken muss er keine Versionsverwaltung verstehen.

---

## 4. Gestaltung: verbindliche Präzisierung

Verwende die bestehenden Tokens aus dem Konzept. Kein neues Farbsystem pro Seite, keine neue Schrift und keine weitere UI-Bibliothek.

| Element | Zielvorgabe |
|---|---|
| Grundschrift | 16 CSS-Pixel als Ausgangswert, skalierbar. |
| Labels, Hilfetexte und Status | In der Regel 14–16 CSS-Pixel; nicht zugunsten der Informationsdichte verkleinern. |
| Kernaktionen und Eingaben | Mindestens 44 CSS-Pixel Höhe; auf Touch vorzugsweise 48. |
| Seitentitel | 28–32 CSS-Pixel, sinnvoll kleiner auf schmalen Geräten. |
| Oberflächen | Warmer heller Hintergrund `#F5F4F1`, weisse Arbeitsflächen, Petrol-Navigation `#19383B`. |
| Primäraktion | Südhang-Akzent `#8C1C4B`; eine hervorgehobene Hauptaktion je aktivem Arbeitskontext. |
| Abstände | Gemeinsame Serie 4/8/12/16/24/32/48; klare Ausrichtung statt willkürlicher Leerflächen. |
| Karten | Nur für echte eigenständige Objekte; dezente Begrenzung, kein zusätzlicher Rahmen um jede Überschrift oder Werkzeugleiste. |
| Status | Klartext plus passender Zustand; nicht allein Farbe und nicht pauschal Grün. |

Prüfe tatsächliche CSS-Werte und Viewports bei 100 % Browserzoom. Ein verkleinerter Screenshot ist kein Grössennachweis. Halte alle Kontrast-, Tastatur-, Fokus-, Reflow- und Fehleranforderungen des bestehenden Konzepts ein. Bei 200 % Zoom und auf Smartphone müssen die Inhalte umgeordnet werden, statt zu schrumpfen.

Schweizer Schreibweise; konsistent „Veröffentlichen“, „Bausteine“, „Bildschirme“ und „Version“. Buttontexte benennen Handlungen und bei Verwechslungsgefahr deren Ziel. Keine dekorativen Werbesprüche, keine Emojis als Ersatz für konsistente vorhandene Icons und keine ausschliesslich per Hover sichtbaren Kernaktionen.

---

## 5. Arbeitsreihenfolge und Umfang

| Paket | Ergebnis |
|---|---|
| **K00 · Bestand und Nachweis** | Bestehende Regeln lesen; tatsächliche Dateien, Formularverträge und Statusbedeutungen ermitteln. Matrix: erfüllt / teilweise / offen / blockiert, mit Begründung. Nicht gezeigte Funktionen separat untersuchen. |
| **K01 · Gemeinsame Basis** | Vier Haupteinstiege, vollständige Linkzuordnung, Seitenrahmen, Typografie, Aktionen und responsive Breiten. |
| **K02 · Status und Menüliste** | N02 aufklären; wahrheitsgetreue Statusdarstellung, kompakte Übersicht und eindeutige Öffnungsaktion. |
| **K03 · Wochenübersicht** | Wochen auswählen vor Erstellformular; vorhandene Erstell-, Fehler- und Kopierabläufe erhalten. |
| **K04 · Bausteinformular** | Allergenbedienung, Abschnitte, Änderungsgeltungsbereich und Speicher-/Archivierungsaktionen. |
| **K05 · Druck und Vorschau** | Nutzungsaufgabe von Layoutverwaltung trennen; Datenstände deutlich machen. |
| **K06 · Abnahme** | Echte Browserprüfung, bestehende Regressionstests, Vertragsvergleich, Screenshots und dokumentierte offene Punkte. |

Gemeinsame Layout-/Styledateien haben eine koordinierte Verantwortung. Seitenpakete können danach unabhängig bearbeitet werden. Keine parallelen widersprüchlichen globalen CSS-Korrekturen. Keine Nebenfeatures wie Einkaufsplanung, Nährwertberechnung, neue Bildgenerierung oder ein weiteres Dashboard.

Ein nachgewiesener Backendkonflikt blockiert den betroffenen Teil, nicht sämtliche unabhängigen Darstellungsverbesserungen. Erfinde keine technische Blockade, bevor du den Bestand untersucht hast.

---

## 6. Abnahmetests für diese Korrekturrunde

Ergänze die passenden Tests T01–T34 aus dem Konzept um folgende konkrete Nachweise. Nutze vorhandene Testmittel und isolierte Testdaten. Ein nicht ausgeführter Test gilt nicht als bestanden.

| Test | Bestanden, wenn … |
|---|---|
| K-T01 · Navigation | Maximal vier fachliche Haupteinstiege erscheinen und sämtliche bisherigen Funktionen, einschliesslich Rezepte/Kochbücher, mit unveränderten Rechten erreichbar bleiben. |
| K-T02 · Konsistenter Arbeitsplatz | Alle vier Seiten denselben Seitenrahmen verwenden; Listen nutzen Platz sinnvoll, Formulare bleiben lesbar. Keine starren grossen Offsets neben der Sidebar. |
| K-T03 · Menüstatus | „Geprüft + Allergene nicht erfasst + ungeprüfter Hinweis“ verständlich getrennt erscheint. Keine erfundene Bestätigung, Datenkorrektur oder neue Publikationsregel. |
| K-T04 · Menüliste | Bei langen Namen, langen Prüfnotizen und fehlendem Bild Datum, Menüname, Datenlage und beschriftete Öffnungsaktion verständlich bleiben. Suche und beide bestehenden Ansichten funktionieren. |
| K-T05 · Geplanten Eintrag öffnen | Der Link das richtige Menü im richtigen Wochenkontext öffnet und nicht unbemerkt einen zentralen Rezept-/Katalogeintrag bearbeitet. |
| K-T06 · Neue Woche | Erstellung bewusst geöffnet wird; bei Validierungsfehlern Formular, Eingaben und Meldungen sichtbar bleiben. Kein zweiter Schreibweg und keine doppelte Erstellung durch UI-Mehrfachauslösung. |
| K-T07 · Kopieren | Tatsächliche Quelle, Zielwoche und Wirkung klar sind; bestehende Rechte und Serverregeln unverändert wirken. |
| K-T08 · Allergen-Roundtrip | Leere, ausgewählte und „kann enthalten“-Angaben beim Öffnen und unveränderten Speichern erhalten bleiben. Kein unbeabsichtigter Wertverlust durch ausgeblendete/deaktivierte Controls. |
| K-T09 · Allergenänderung | Auswahl, Abwahl und bestehende Zustandsänderung denselben fachlichen Effekt wie zuvor haben. Keine doppeldeutige aktive „enthält“-Darstellung bei inaktiver Auswahl. |
| K-T10 · Druckdatenstand | Gewählte Woche und veröffentlichter Plan mit absichtlich unterschiedlichen Zeiträumen getestet werden; Beschriftung und tatsächlicher PDF-Inhalt jeweils zusammenpassen. |
| K-T11 · Layoutversion | Entwurf prüfen, aktive Version verwenden und gegebenenfalls aktivieren getrennte, wahrheitsgetreu beschriftete bestehende Aktionen bleiben. |
| K-T12 · Responsive/Zoom | Geänderte Seiten bei 1920×1080, 1366×768, 768×1024, 390×844, 320 CSS-Pixel Breite sowie 200 % Zoom bedienbar bleiben. Kein horizontales Seitenscrollen im Kernablauf. |
| K-T13 · Eingabe und Rechte | Tastatur, sichtbarer Fokus, Fehlerfälle, fehlende Rechte und Schutz ungespeicherter Änderungen tatsächlich getestet sind. Die normalen Formularseiten bleiben nutzbar. |
| K-T14 · Technischer Diff | Keine neuen Abhängigkeiten, Migrationen, Verträge, fachlichen Regeln, Berechtigungsänderungen oder unbeabsichtigten Auswirkungen auf öffentliche Ausgaben enthalten sind. |
| K-T15 · Nicht gezeigte Ziele | Wochenraster, Menüeditor/Panel, Patientenumfang und Mobilansicht im Projekt separat geprüft und ehrlich als erfüllt, offen oder begründet blockiert erfasst sind. |

### Sicht- und Nutzernachweise

Erstelle echte Vorher-/Nachher-Screenshots der vier geänderten Seiten im Browser. Dokumentiere Viewport, Zoom und gezeigten Datenzustand. Ergänze den kritischen Statusfall, ein Bausteinformular mit und ohne Allergenangaben, einen Formularfehler und den Druckfall mit abweichendem veröffentlichtem Zeitraum. Keine generierten Mockups als Umsetzungsnachweis.

Der Nutzertest mit mindestens drei technisch unerfahrenen Personen aus dem Konzept bleibt erforderlich. Ergänzende Aufgaben: „Öffne eine vorhandene Woche“, „Zeige, welche Angaben bei diesem geprüften Menü noch fehlen“, „Bearbeite einen Baustein“ und „Drucke eine bestimmte gespeicherte Woche, nicht den veröffentlichten Plan“. Ein Agent ersetzt diese Personen nicht. Solange der Test aussteht, bleibt die Nutzerabnahme offen.

### Abschlussbericht

Liefere eine Tabelle mit **Befund-ID → Änderung → echte Dateipfade → Test/Nachweis → Status**. Danach nenne erhaltene Formularverträge sowie offene oder blockierte Punkte und deren konkrete Ursache. Verweise auf tatsächliche Screenshots und Testergebnisse.

**Keine Fertigmeldung bei blosser Farb-/Foto-/Card-Kosmetik. Keine Fertigmeldung, wenn die 14-Punkte-Navigation unverändert bleibt, der Prüfstatus weiterhin missverständlich ist oder der technische Unterbau still umgebaut wurde.**

Beginne mit K00. Implementiere anschliessend die nicht blockierten Korrekturen in dieser Reihenfolge. Liefere nicht nur eine weitere Liste von Verbesserungsideen.
