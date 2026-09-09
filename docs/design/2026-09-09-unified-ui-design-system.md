<!-- Verbindlicher Nutzerauftrag vom 9. September 2026. Konsolidiert ältere UI-Entwürfe; fachliche, Sicherheits- und Architekturverträge bleiben erhalten. -->

# Masterprompt: Bestehende Flask-/Tabler-Anwendungen auf ein einheitliches Design migrieren

**Einsatz:** Arbeitsauftrag für Codex oder Claude Code im bestehenden Repository.

**Geltungsbereich:** Die gesamte Anwendung, alle vorhandenen Tools, Module, Verwaltungsseiten und gemeinsam verwendeten UI-Komponenten. Keine Bindung an eine bestimmte Fachdomäne, Beispielseite oder Route.

**Technische Basis:** Flask, Jinja2, Tabler, das zur installierten Tabler-Version gehörende Bootstrap und Tabler Icons.

**Ziel:** Ein gemeinsames, wiederverwendbares und überprüfbares Design statt einzelner verschönerter Seiten.

Dieses Dokument ist eigenständig verwendbar. Die beiden älteren Entwürfe zum UI-Design und zur seitenbezogenen Migration werden für diese UI-Aufgabe durch diesen konsolidierten Standard ersetzt. Bestehende Sicherheits-, Architektur- und Repository-Vorgaben bleiben gültig. Bei einem Konflikt mit einem freigegebenen Corporate Design oder Projektvertrag: Konflikt benennen, nicht stillschweigend überschreiben.

---

## 1. Dein Auftrag

Migriere das bestehende Frontend auf das hier festgelegte Designsystem. Setze die Änderungen im Repository um; liefere nicht lediglich Vorschläge oder ein weiteres Konzept.

Arbeite von gemeinsamen Grundlagen zu den einzelnen Seitentypen: Design-Tokens, Tabler-Anbindung, Layout, Navigation, Komponenten und danach sämtliche betroffenen Tools und Routen. Eine Referenzseite dient der Entwicklung und Prüfung des Standards, nicht als Begrenzung des Auftrags.

**Gleiche Gestaltung bedeutet gemeinsame Komponenten und Regeln. Es bedeutet nicht, jede Seite in dasselbe Formular-plus-Tabelle-Layout zu zwingen.**

Erhalte Geschäftslogik, Daten, Berechtigungen und bestehende Bedienabläufe. Erfinde keine Funktionen, Datenspalten, Pflichtfelder, Zeichenlimits, Menüpunkte oder Statuswerte. Verändere keine API-Verträge und führe keine Datenbankmigration als Nebenprodukt der Gestaltung durch.

Die Farben in diesem Dokument sind die vorgeschlagene gemeinsame Anwendungspalette. Sie sind kein Nachweis einer offiziell freigegebenen Corporate-Design-Farbdefinition.

## 2. Konkrete Stellungnahme zum bisherigen Stand

### 2.1 Am gezeigten Ist-Interface erkennbar

Diese Befunde stammen aus der gezeigten Oberfläche. Ob dieselben Probleme auf weiteren Seiten bestehen, musst du im Repository und Browser prüfen.

| Befund | Was daran nicht stimmt | Verbindliche Korrektur |
|---|---|---|
| Grosse freie Randflächen bei gleichzeitig kleinen Texten und Bedienelementen | Der verfügbare Platz hilft der Lesbarkeit nicht. Innen ist die Oberfläche dicht, aussen bleibt viel Fläche leer. | Inhaltsbreite innerhalb des Hauptbereichs berechnen; Schrift, Feldhöhe und Abstände gemeinsam anheben. Nicht einfach alle Cards bildschirmbreit ziehen. |
| Seitenüberschrift kaum dominanter als ein Card-Titel | Seite, Bereich und einzelne Aufgabe haben zu wenig unterschiedliche Gewichtung. | Eindeutige H1, kurze hilfreiche Beschreibung und einheitlicher Seitenkopf. |
| Lange, praktisch ungegliederte Sidebar | Alltagsaufgaben, Stammdaten und Systemeinstellungen erscheinen nahezu gleichrangig. | Vorhandene Einträge nach tatsächlichen Aufgaben gruppieren, aktive Position eindeutig zeigen und Berechtigungen erhalten. |
| Ähnlich klingende Navigationsbegriffe ohne Erklärung | Der Unterschied zwischen benachbarten Funktionen ist für neue Benutzer nicht sofort klar. | Aufgaben und Zielseiten prüfen; verständliche Benennung oder kurze Erklärung verwenden. Nicht blind Funktionen zusammenlegen. |
| Formularfelder nutzen nur einen Teil der grossen Card | Kartenbreite und innere Feldaufteilung wirken nicht aufeinander abgestimmt. | Inhalt sinnvoll an ein gemeinsames Grid binden. Kurze Felder nicht endlos dehnen, längere Felder erhalten den nötigen Raum. |
| Feldhinweis „optional“ weit entfernt vom Label | Information und zugehöriges Feld sind visuell voneinander getrennt. | „Optional“ beim Label oder im direkt zugeordneten Hilfetext anzeigen. |
| Kleine Tabellenüberschriften und unauffällige Statusanzeigen | Die Lesbarkeit der eigentlichen Daten erhält zu wenig Gewicht. | Gut lesbare Tabellenbeschriftungen, klarer Abstand und ausreichend kontrastierende Status-Badges. |
| Mehrere ähnlich gewichtete Zeilenaktionen | Wichtigkeit und Nutzungshäufigkeit werden nicht unterschieden. | Häufige Aktionen beschriftet sichtbar lassen; seltene Aktionen nur bei Bedarf in ein funktionierendes Menü verschieben. |
| Pagination mit Vor-/Zurück-Steuerung bei nur einer Seite | Sichtbare Bedienung erzeugt keine zusätzliche Funktion. | Bei einer Seite nur die Anzahl anzeigen; Seitensteuerung erst bei mehreren Seiten. |

**Nicht als Fehler behaupten:** Eine fehlende Suche bei zwei Datensätzen ist kein grundsätzliches UX-Problem. Ein Screenshot belegt weder defekte Funktionen noch fehlende Barrierefreiheitstests oder eine bestimmte CSS-Ursache. Behaupte solche Dinge erst nach Prüfung.

### 2.2 Fehler und Lücken in den bisherigen Prompt-Entwürfen

| Bisherige Vorgabe | Warum sie nicht genügt | Neue Entscheidung |
|---|---|---|
| Eine konkrete Fachseite bestimmt die gesamte Migration. | Andere Tools und Seitentypen können unbearbeitet bleiben. | Vollständiges UI-Inventar und Nachweis pro vorhandener Route. |
| „Modern“, „ruhig“, „hochwertig“ ohne prüfbare Umsetzung. | Der Agent muss wichtige Entscheidungen jedes Mal neu interpretieren. | Feste Tokens, Komponentenverträge, Layoutvarianten und visuelle Referenzen. |
| Wertebereiche wie 240–260 px oder 32–36 px. | Mehrere unterschiedliche Ergebnisse erfüllen denselben Prompt. | Eindeutige Standardwerte und fest definierte responsive Abweichungen. |
| „Tabler-Standardschrift“, obwohl das Mockup Serifentitel zeigt. | Textvorgabe und visuelles Ziel widersprechen sich. | Feste Schriftfamilien für Bedientext und Überschriften; siehe Typografie. |
| Nur eigene CSS-Variablen definieren. | Das beweist nicht, dass Tabler-Komponenten diese tatsächlich verwenden. | Tokens an die installierte Tabler-Version anbinden und berechnete Browser-Styles prüfen. [S1, S2] |
| Helle Status- und Hilfstextfarben. | Einige konkret vorgeschlagene Kombinationen sind für kleine Schrift zu kontrastarm. | Dunklere Textfarben, getrennte Status-Texttokens und Kontrastprüfung. [S3] |
| Suche, Benachrichtigungen und Änderungsmetadaten als feste Mockup-Elemente. | Aus einer Illustration wird sonst unbeabsichtigt eine neue Funktionsanforderung. | Nur tatsächlich vorhandene Funktionen und Daten darstellen. |
| „Responsive prüfen“, aber ohne benannte Werkzeuge oder Belege. | Es bleibt unklar, ob wirklich im Browser geprüft wurde. | Playwright beziehungsweise vorhandene Browser-Werkzeuge, dokumentierte Viewports, Screenshots und Teststatus. [S4] |
| „Alles gleich“ ohne Abgrenzung der Ansichten. | Login, Formulare, Kalender und Digital Signage könnten unpassend gleichgeschaltet werden. | Gemeinsame Designsprache, aber passende Layoutvarianten. |

Konkrete Nachrechnung der alten Farbwerte, jeweils als voll deckender Text auf dem genannten Hintergrund: `#238636` auf `#EAF8ED` ergibt rund **4,22:1**, `#B26A00` auf `#FFF4D6` rund **3,87:1**, `#9CA3AF` auf Weiss rund **2,54:1**. Für normalen Text ist nach WCAG 2.2 AA grundsätzlich mindestens **4,5:1** erforderlich. Die neuen Tokens korrigieren diese Kombinationen. Das ist eine Bewertung der früher vorgeschlagenen Werte, keine Kontrastmessung der laufenden Anwendung. [S3]

## 3. Geltungsbereich: Alle vorhandenen Tools und Seitentypen

Erstelle eine vollständige Bestandsaufnahme aus Routen, Blueprints, Templates, Navigation, Dialogen und erreichbaren UI-Zuständen. Beschränke dich nicht auf Links in der Sidebar: Auch Bearbeitungsseiten, Unterseiten und rollenabhängige Ansichten zählen.

| Vorhandener Seitentyp / Tool | Designauftrag |
|---|---|
| Dashboard und Übersichtsseiten | Verständliche Hierarchie, echte Kennzahlen und konsistente Karten. Keine zusätzlichen Statistik-Kacheln als Dekoration. |
| Listen, Suche und Stammdatenverwaltung | Einheitlicher Seitenkopf, Tabellen, Filter, Aktionen, Status, leere Zustände und Pagination. |
| Anlegen, Bearbeiten und Detailansichten | Einheitliche Labels, Feldgruppen, Validierung, Aktionsleiste und Darstellung von Metadaten. |
| Einstellungen und Konfiguration | Thematische Gruppen, verständliche Erklärungen, konsistente Speichern-/Abbrechen-Logik. |
| Benutzer, Rollen und Zugriffe | Dasselbe Design; Rollenmodell und serverseitige Autorisierung unverändert. |
| Import, Export und Schnittstellenverwaltung | Einheitliche Dateiauswahl, Resultate und Fehlermeldungen; Fortschritt nur bei vorhandener technischer Grundlage. |
| Kalender, Planung, Kanban und ähnliche Fachwerkzeuge | Gemeinsame Farben, Schrift, Navigation und Bedienelemente; das fachlich notwendige Arbeitslayout erhalten. |
| Medien, Vorlagen und Inhaltsverwaltung | Gemeinsame Karten, Vorschauen, Auswahlzustände und Aktionen. |
| Modals, Dropdowns, Tabs und Bestätigungen | Auch diese Oberflächen migrieren, nicht nur vollständige HTML-Seiten. |
| Login, Zugriff verweigert und Fehlerseiten | Gemeinsame Marken- und Formgestaltung; kein erzwungener Admin-Seitenrahmen vor der Anmeldung. |
| Öffentliche Ansichten, Druck, Kiosk und Digital Signage | Gemeinsame Tokens nur dort übernehmen, wo passend. Keine Sidebar, keine Admin-Aktionen, keine pauschale Desktop-Schriftgrösse übertragen. Als eigene Layoutvarianten erfassen und gegen unbeabsichtigte Änderungen prüfen. |

Diese Tabelle ist eine Prüfliste, kein Auftrag, fehlende Module neu zu entwickeln. Verwende die echten Modulnamen und Routen des jeweiligen Projekts.

## 4. Technologien und Werkzeuge: explizit und mit klaren Grenzen

### 4.1 Laufzeit und Implementierung

| Technologie | Vorgabe |
|---|---|
| Flask | Bestehende Anwendung, Blueprints, Endpoints, Request-Verarbeitung und Sessions weiterverwenden. |
| Jinja2 | Vorhandene Template-Vererbung, Partials und Macros nutzen; wiederkehrende UI nicht kopieren. |
| Tabler / `@tabler/core` | Verbindliche Komponentenbasis. Installierte Version aus Projekt und Assets ermitteln, nicht automatisch aktualisieren. |
| Bootstrap | Nur die vorhandene, zur Tabler-Integration passende Basis nutzen. Kein zweites Bootstrap-CSS oder zweiter JS-Bundle. |
| Tabler Icons | Ein einziges konsistentes Icon-System. Bestehende SVG-/Sprite-Einbindung weiterverwenden. Keine Emojis als UI-Icons. |
| CSS / vorhandenes Sass | Zentrale Tokens und Komponenten-Styles. Vorhandenen Build verwenden, keinen neuen Build nur für die Neugestaltung einführen. |
| JavaScript | Vorhandene Skripte und Bootstrap-/Tabler-Interaktionen wiederverwenden. Neue kleine Interaktionen ohne neue Laufzeitbibliothek. |
| Vorhandene Bibliotheken | Zum Beispiel HTMX oder Alpine nur weiterverwenden, wenn schon Teil der Anwendung. Nicht neu einführen. |
| Nicht zulässig | React, Vue, Svelte, Tailwind, neue UI-Kits, Frameworkwechsel oder eine neue SPA als Nebenprodukt. |

### 4.2 Arbeits- und Prüfwerkzeuge des Coding Agents

| Werkzeug | Konkreter Einsatz | Grenze / Fallback |
|---|---|---|
| Codex oder Claude Code | Repository lesen, begrenzte Änderungen implementieren, Tests ausführen und Befunde dokumentieren. | Nur tatsächlich verfügbare Werkzeuge verwenden. |
| Git | Arbeitszustand vorab prüfen, Diffs lesen, fremde Änderungen erhalten, eigene Änderungen nachvollziehbar halten. | Kein `reset --hard`, kein automatischer Push, kein Deployment ohne Auftrag. |
| Shell / Terminal | Bestehende Start-, Build- und Testbefehle ausführen; Versionen und Assets ermitteln. | Bestehende Projektumgebung verwenden. Keine produktiven Daten verändern. |
| ripgrep (`rg`) | Templates, Inline-Styles, Farbwerte, Klassen, Duplikate und JS-Selektoren suchen. | Falls nicht vorhanden: `git grep`, vorhandene Dateisuche oder PowerShell `Select-String`. |
| Playwright | Echte Seiten öffnen, Navigation und Formulare bedienen, Viewports prüfen und Screenshots erstellen. | Vorhandene Integration nutzen. Fehlende Browser-/Testumgebung ausdrücklich als Blocker melden. |
| Playwright Test | Wenn im Projekt vorhanden: Screenshot-Vergleiche mit freigegebenen Referenzen, zum Beispiel `toHaveScreenshot()`. [S4] | Diese Assertion gehört zum Playwright-Test-Runner; nicht eine identische Python-API erfinden. |
| Browser-DevTools / vorhandenes Chrome-DevTools-MCP | Berechnete CSS-Werte, Box-Modell, Netzwerk, Konsole, Fokus und überlaufende Elemente untersuchen. | Kein MCP als vorhanden voraussetzen. Vorhandene gleichwertige Browser-Werkzeuge sind ausreichend. |
| axe-core / `@axe-core/playwright` | Automatisierte Accessibility-Prüfung, wenn verfügbar. [S5] | Nur Prüfwerkzeug, keine neue Produktionsabhängigkeit. Ersetzt keine manuelle Tastaturprüfung. |
| Flask-Testclient und bestehendes pytest/unittest | GET-/POST-Verhalten, Weiterleitungen, Berechtigungen und Regressionen prüfen. [S6] | Vorhandenes Testframework behalten. Kein Wechsel allein wegen dieses Prompts. |
| Vorhandene Linter und Formatter | Bestehende Qualitätsprüfungen für Python, Templates, CSS und JavaScript ausführen. | Nicht das ganze Repository unnötig neu formatieren. |

Nicht verfügbare Werkzeuge zuerst durch vorhandene gleichwertige Mittel ersetzen. Neue reine Entwicklungsabhängigkeiten nur nach den Repository-Regeln beziehungsweise mit nötiger Freigabe installieren. Fehlende Tests nicht als bestanden deklarieren und Sicherheitsmechanismen nicht deaktivieren, um Tests zu erleichtern.

## 5. Feste visuelle Basis

Die Stilrichtung bleibt: dunkle Petrol-Sidebar, warmer heller Hintergrund, weisse Inhaltsflächen, Burgunder als Handlungsakzent und zurückhaltende Trennlinien.

### 5.1 Zentrale Farb-Tokens

Definiere diese Werte einmal in einer gemeinsamen Token-Datei oder der entsprechenden vorhandenen zentralen Struktur. Die Namen sind der gemeinsame Vertrag; keine zweite parallele Palette anlegen.

```css
:root {
  --app-bg: #F6F4F1;
  --app-surface: #FFFFFF;
  --app-surface-soft: #FAF9F7;

  --app-sidebar: #173C3F;
  --app-sidebar-hover: #214A4D;
  --app-sidebar-active: #31585B;
  --app-sidebar-text: #C7D8D9;
  --app-sidebar-label: #9AB7BA;
  --app-sidebar-indicator: #F3A6C0;

  --app-primary: #A3164D;
  --app-primary-rgb: 163, 22, 77;
  --app-primary-hover: #8E123F;
  --app-primary-active: #7C1037;
  --app-primary-soft: #F7E8EE;
  --app-on-primary: #FFFFFF;

  --app-text: #1F2937;
  --app-text-muted: #596273;
  --app-border: #E5E7EB;
  --app-border-soft: #EFECE8;
  --app-control-border: #808B99;
  --app-focus: #A3164D;

  --app-success: #2FB344;
  --app-success-text: #166534;
  --app-success-soft: #EAF8ED;
  --app-warning: #F59F00;
  --app-warning-text: #854D0E;
  --app-warning-soft: #FFF4D6;
  --app-danger: #D63939;
  --app-danger-text: #B42318;
  --app-danger-soft: #FCEAEA;
  --app-info: #4299E1;
  --app-info-text: #175CD3;
  --app-info-soft: #EAF4FC;
  --app-neutral-text: #475467;
  --app-neutral-soft: #EEF0F2;
}
```

Burgunder bezeichnet die wichtigste Handlung, Auswahl oder einen Link, nicht eine beliebige grosse Hintergrundfläche. Für kleine Statustexte immer `*-text` auf `*-soft` verwenden, nicht die hellere Akzentfarbe. Destruktive Buttons verwenden einen geprüften dunklen Rotton, beispielsweise `--app-danger-text` mit Weiss.

Die helle Sidebar-Akzentlinie ist absichtlich nicht dunkelburgunder: Dunkles Burgunder hebt sich gegen Petrol schlecht ab. Aktive Navigation zusätzlich durch Hintergrund, Schriftgewicht und `aria-current` kennzeichnen.

Helle Card-Rahmen sind dekorative Trennlinien. Wo eine Umrandung nötig ist, um ein Eingabefeld oder Bedienelement zu erkennen, `--app-control-border` und die tatsächliche Hintergrundfarbe auf ausreichenden Kontrast prüfen. [S7]

### 5.2 Typografie, Masse und Abstände

| Element | Fester Standard |
|---|---|
| Schrift für Fliesstext, Navigation, Tabellen, Formulare und Buttons | `Arial, Helvetica, sans-serif` |
| Schrift für H1 und Card-Überschriften | `Georgia, "Times New Roman", serif` |
| Fliesstext / Eingabefelder | `1rem`, Zeilenhöhe `1.5` |
| H1 ab Desktop-Breakpoint | `2.125rem`, Gewicht `700`, Zeilenhöhe `1.2` |
| H1 unter Desktop-Breakpoint | `1.75rem`, Gewicht `700`, Zeilenhöhe `1.2` |
| Card-Überschrift | `1.25rem`, Gewicht `700`, Zeilenhöhe `1.3` |
| Navigation / Tabellen / Labels | `0.875rem`; Labels Gewicht `600` |
| Hilfetext / sekundäre Metadaten | `0.8125rem`; wichtige Handlungsinformationen nicht kleiner setzen |
| Sidebar | `248px` breit auf Desktop |
| Topbar | `64px` Mindesthöhe, darf bei Zoom/Inhalten wachsen |
| Standard-Container | `1440px` maximale äussere Breite einschliesslich Innenabstand, innerhalb des Hauptbereichs |
| Reine schmale Formular-/Leseseite | `960px` maximale äussere Breite als zentrale Layoutvariante |
| Arbeitsfläche für bestehende Kalender/Kanban | Verfügbare Breite als eigene zentrale Variante; keine willkürliche Seiten-CSS-Lösung |
| Inhaltspadding | Desktop `32px`, Tablet `24px`, Smartphone `16px` |
| Card-Radius | `12px` |
| Button-/Feld-/Nav-Radius | `8px` |
| Status-Badge-Radius | `999px` |
| Standard-Interaktionshöhe | mindestens `44px`; mehrzeilige Labels dürfen wachsen |
| Tabellenzeile | durch Padding und Controls mindestens ungefähr `64px`, keine feste abschneidende Höhe |
| Card-Innenabstand | `24px`, auf Smartphone `16px` |
| Abstand zwischen Hauptblöcken | `24px` |
| Formular-Grid-Abstand | `24px` |
| Erlaubte allgemeine Abstandsskala | `4 / 8 / 12 / 16 / 24 / 32 / 40 / 48px` |
| Schatten | `0 1px 2px rgba(0, 0, 0, 0.025)` |

Die Serifentitel greifen die visuelle Richtung des Mockups ausdrücklich auf. Die Schriftwahl bleibt nicht mehr der jeweiligen Tabler-Standardkonfiguration überlassen. Keine pro Seite abweichende Schrift, keine nachträglich eingeführte Condensed-Schrift und kein unkontrollierter externer Font-Aufruf.

Die `rem`-Werte gehen vom unveränderten Browser-Standard aus. Keine erzwungene 16px-Root-Grösse, keine Zoom-Sperre und keine Schriftverkleinerung, um Probleme zu kaschieren. Fontstacks garantieren ohne identische installierte Fonts keine pixelgleichen Ergebnisse über Betriebssysteme hinweg; dokumentiere deshalb den tatsächlich verwendeten Font der Referenzumgebung. Eine spätere freigegebene selbst gehostete Markenschrift wird zentral und mit neuen geprüften Referenzen eingeführt.

Lege wiederkehrende Masswerte ebenfalls zentral als Tokens an. Keine leicht unterschiedlichen Radien oder Paddings über einzelne Templates verteilen.

## 6. Tabler tatsächlich anbinden, nicht nur umfärben

Untersuche zuerst die installierte Tabler-/Bootstrap-Version und die ausgelieferten CSS-Dateien. Dokumentation neuerer Versionen ist keine Aufforderung zum Upgrade.

Eigene `--app-*`-Variablen müssen an die tatsächlich verwendeten Theme- und Komponentenvariablen angeschlossen werden. Tabler dokumentiert beispielsweise `--tblr-primary`; Bootstrap-Komponenten können eigene lokale Variablen besitzen. Deshalb ist ein Eintrag in `:root` allein kein Nachweis, dass Buttons, Checkboxen, Tabs und Pagination richtig aussehen. [S1, S2]

Prüfe insbesondere Primärfarbe und RGB-Varianten, Body-Hintergrund, Schriftfamilien, Linkfarben sowie Normal-, Hover-, Active-, Focus-, Disabled- und Invalid-Zustände. `--app-primary-rgb` steht hier für RGB-Kanäle und wird nicht aus einem Hex-String zusammengesetzt.

Nutze den bestehenden Sass-Build, falls dieser bereits die Theme-Erstellung übernimmt. Sonst verwende schlanke, korrekt nach den Herstellerstyles geladene zentrale Overrides. Bearbeite keine minifizierten Vendor-Dateien und löse Konflikte nicht durch eine wachsende Sammlung von `!important`.

Prüfe berechnete Styles im Browser. Verhindere unbeabsichtigte Auswirkungen auf Druck, öffentliche Seiten, Signage und eingebundene Drittkomponenten durch passende Layout-/Bereichsselektoren. Entferne alte Überschreibungen erst nach Prüfung ihrer bisherigen Nutzung.

## 7. Gemeinsamer Seitenrahmen und Navigation

Alle regulären internen Tools verwenden denselben Seitenrahmen: Sidebar, bei benötigten Funktionen Topbar, Seitenkopf und Hauptinhalt. Topbar-Inhalte nicht erfinden; ohne zusätzliche Funktion keine leere Zierleiste erzeugen. Die gewählte Anwendungslösung wird zentral umgesetzt, nicht pro Tool neu entschieden.

Der Hauptbereich braucht `min-width: 0`. Seine Breite wird aus dem verfügbaren Bereich neben der Sidebar berechnet. Containerbreite nicht zusätzlich vom gesamten Viewport zentrieren. Schmale Formulare dürfen schmal bleiben; Tabellen und Facharbeitsflächen erhalten die definierte passende Variante.

Die Sidebar erhält das vorhandene Original-Logo und den Produktnamen. Kein Logo nachzeichnen, keinen Claim ergänzen. Navigation nach Aufgaben gruppieren, beispielsweise „Arbeitsbereich“, „Verwaltung“, „Daten & Schnittstellen“ und „System“. Diese Gruppen nur verwenden, wenn entsprechende Einträge existieren. Leere Gruppen weglassen.

Navigationseinträge: mindestens 44px hoch, Icon 20px, Abstand zwischen Icon und Text 12px, Radius 8px. Gruppentitel: 12px, Gewicht 600, dezente Grossschreibung. Aktiver Eintrag: definierter Hintergrund, weisse Schrift, Gewicht 700, 3px helle Akzentlinie ohne Layoutsprung.

Der Navigationsbereich scrollt bei Platzmangel, der Logout bleibt erreichbar. Profilfunktionen an einem klaren Ort bündeln, nicht mehrfach dieselbe Benutzerinformation in Sidebar und Topbar wiederholen. Rollenabhängige Sichtbarkeit erhalten; sie ersetzt keine serverseitige Autorisierung.

Seitenkopf: logisch korrekter Breadcrumb, genau eine H1, gegebenenfalls ein kurzer wirklich hilfreicher Satz und die wichtigsten Seitenaktionen. Kein erfundener Breadcrumb-Zielpfad, kein dekorativer Eyebrow auf jeder Seite und kein Fülltext wie „Hier können Sie die Verwaltung verwalten“.

## 8. Komponentenregeln für alle Tools

| Komponente | Verbindliche Regel |
|---|---|
| Cards | Weisse Fläche, 12px Radius, dezenter Rand und minimaler Schatten. Header/Body/Footer nur soweit inhaltlich nötig. Keine Card in Card ohne fachlichen Grund. |
| Tabs | Aktiver Tab mit Burgundertext, hellem Akzenthintergrund und 2px Unterlinie. Echte Seitenwechsel als Links; dynamische Tabs nur mit passender Tastatur- und ARIA-Implementierung. |
| Buttons | Eine dominante Aktion je aktueller Aufgabe. Nebenaktionen weiss/neutral. Mindestens 44px Bedienhöhe; Text erklärt die Aktion. Keine universelle Primäraktion auf reinen Leseseiten erzwingen. |
| Formularfelder | Sichtbares Label, tatsächlicher Pflichtstatus, sinnvoller Datentyp, 44px Mindesthöhe, passende Breite und verständlicher Hilfetext. Placeholder ersetzt kein Label. |
| Validierung | Bestehende Regeln und serverseitige Prüfung erhalten. Fehlermeldung am Feld zuordnen, `aria-invalid`/`aria-describedby` passend setzen, Werte nach Fehler erhalten. |
| Textareas | Sinnvolle Mindesthöhe und vertikale Vergrösserung erlauben. Zeichenlimit und Zähler nur aus echten bestehenden Vorgaben ableiten. |
| Tabellen | Semantische Tabelle, Header in normaler Schreibweise, ausreichend Padding, dezente Zeilentrennung. Daten und Aktionen nicht abschneiden oder unter 14px verkleinern. |
| Status-Badges | 13px Text, 4px/10px Padding, Pill-Form, dunkle Status-Textfarbe auf heller Statusfläche. Farbe nie als einzige Information. Reale Backend-Statuswerte über eine gemeinsame Zuordnung darstellen. |
| Zeilenaktionen | Häufige Aktionen beschriftet sichtbar; seltene in ein echtes Dropdown. Keine versteckten Nur-Hover-Aktionen. Kein leeres Dreipunktmenü. |
| Suche und Filter | Nur vorhandene oder ausdrücklich beauftragte Funktionalität. Bei serverseitiger Pagination niemals nur die sichtbare Seite filtern und es als Suche im Gesamtbestand ausgeben. |
| Pagination | In den Listenabschluss integrieren. Gesamtzahl und Seitengrösse aus echten Daten. Keine Seitennavigation bei nur einer Seite. |
| Leere Zustände | Zwischen „noch keine Daten“, „kein Suchtreffer“ und „keine Berechtigung“ unterscheiden. Nur erlaubte und sinnvolle Folgeaktionen anbieten. |
| Erfolg und Fehler | Gemeinsame Flash-/Alert-Komponente, verständliche Texte, Feldfehler zusätzlich lokal. Wichtige Informationen nicht nach kurzer Zeit automatisch entfernen. |
| Modals | Nur für passende kurze Aufgaben. Aussagekräftiger Titel, korrekter Fokus, Tastaturbedienung, Rückkehr zum Auslöser. Lange Formulare nicht in kleine Modals pressen. |
| Destruktive Aktionen | Bestehende Bestätigungen und Schutzmassnahmen erhalten. Objekt und Konsequenz benennen. Keine zusätzlichen riskanten Aktionen erfinden. |
| Ladezustände | Nur dort anzeigen, wo tatsächlich geladen wird. Keine künstlichen Wartezeiten oder erfundenen Fortschrittsprozente. |

Ein statisches Anlegeformular braucht nicht automatisch einen „Abbrechen“-Button. Ein Dashboard braucht nicht automatisch eine Suche. Eine Datentabelle braucht nicht automatisch eine Spalte „Letzte Änderung“. Das Mockup ist keine Datenquelle.

Sprache: Bestehende Anrede und Anwendungssprache konsistent halten. Für deutschsprachige Schweizer Anwendungen Schweizer Rechtschreibung verwenden. Sichtbare Datumsformate können lokalisiert werden; maschinelle Feldwerte und erwartete Backend-Formate unverändert lassen. Keine technischen Interna oder vertraulichen Informationen in Endbenutzer-Fehlermeldungen.

## 9. Wiederverwendung statt Seitensonderlösungen

Nutze vorhandene Strukturen. Fehlen gemeinsame Bausteine, lege sie in der passenden bestehenden Projektstruktur an. Geeignete Verträge sind:

| Baustein | Gemeinsame Verantwortung |
|---|---|
| Seitenrahmen / Basis-Template | Assets, Sidebar, Topbar, Hauptbereich, globale Meldungen |
| Seitenkopf | Titel, optionale Beschreibung, Breadcrumbs und Aktionen |
| Formular-Macros | Label, Feld, Hilfetext, Pflichtstatus und Fehlerzuordnung |
| Status-Macro | Feste Zuordnung echter Statuswerte zu Text und Farbvariante |
| Empty State | Titel, hilfreiche Erklärung, optionale erlaubte Aktion |
| Pagination | Wahrer Datenumfang, Seitenlinks, deaktivierte Zustände |
| Aktionsleiste | Einheitliche Anordnung ohne fachliche Logik im CSS |

Jinja ist Teil der bestehenden Flask-Template-Struktur; verwende die vorhandene Vererbung und Escape-Regeln. Kein pauschales `safe`, um Darstellungsprobleme zu umgehen. [S8]

Keine parallelen Varianten wie `modern-card`, `better-table` oder `new-form-v2`. Keine universelle Mega-Komponente mit Dutzenden fachlichen Schaltern. Fachseiten dürfen unterschiedliche Inhalte haben; dieselbe Komponente darf nicht pro Seite anders aussehen.

## 10. Responsive Verhalten und Barrierefreiheit

Verwende die installierten Bootstrap-/Tabler-Breakpoints. Dieser Standard setzt die unveränderte Standardaufteilung voraus: ab 992px Desktop-Sidebar, 768–991px Tablet, darunter Smartphone. Bei nachgewiesen angepassten Projekt-Breakpoints zuerst eine zentrale Zuordnung festlegen und dokumentieren, keine zweiten konkurrierenden Breakpoints einführen.

Unterhalb des Desktop-Breakpoints: Sidebar über die vorhandene passende Collapse-/Offcanvas-Lösung öffnen, Menübutton erreichbar halten, Fokus und Schliessen prüfen. Formulare auf kleinen Geräten einspaltig. Aktionsgruppen dürfen umbrechen, kritische Aktionen bleiben verständlich beschriftet.

Keine horizontale Seitenscrollbar bei 390px. Breite Tabellen dürfen in einem lokal beschränkten, erkennbaren und tastaturbedienbaren Bereich horizontal scrollen. Das ist keine Erlaubnis, wichtige Inhalte unsichtbar zu verstecken. Kalender und vergleichbare Arbeitsflächen erhalten dokumentierte fachliche Ausnahmen.

Ziel ist WCAG 2.2 AA für betroffene Oberflächen: normaler Text mindestens 4,5:1, grosser Text mindestens 3:1; zur Erkennung notwendige nicht-textliche UI-Informationen grundsätzlich mindestens 3:1 zu benachbarten Farben. Prüfe Ausnahmen und Zustände sachgerecht, nicht nur ausgewählte Standardfarben. [S3, S7]

Als zusätzlicher **Projektstandard** gelten mindestens 44px für wesentliche Bedienelemente. Das ist bewusst grosszügiger als das 24px-Mindestmass des WCAG-2.2-AA-Kriteriums 2.5.8, das eigene Ausnahmen kennt. Behaupte nicht, WCAG AA verlange pauschal 44px. [S9]

Sichtbarer Fokus: auf hellen Flächen mindestens 2px Burgunder-Outline mit Abstand, in der Sidebar eine ausreichend kontrastierende helle Variante. Fokus nicht entfernen. Reihenfolge, Labels, Tastaturbedienung, 200%-Zoom und reduzierte Bewegung prüfen. Automatisierte axe-Prüfungen decken nicht alle Barrierefreiheitsanforderungen ab. [S5]

## 11. Migrationsablauf mit überprüfbaren Ergebnissen

### Phase A – Bestand und Befunde

Lies Repository-Anweisungen, relevante SDDs und bestehende Designentscheidungen. Prüfe den Git-Zustand und die tatsächlichen Versionen. Ermittle alle UI-Routen, Templates und Komponenten sowie Start- und Testbefehle.

Erstelle ein Inventar mit echtem Tool-/Modulnamen, Route oder Zustand, Template, Rolle, Layoutvariante und Migrationsstatus. Erfasse vor Änderungen Screenshots mit datenschutzgerechten Testdaten. Produktive Personen-, Patienten- und Zugangsdaten gehören nicht in Testartefakte.

Formuliere Befunde konkret nach diesem Muster:

> **Problem → Beleg → Auswirkung → konkrete Korrektur → betroffene Komponenten/Seiten.**

Keine pauschalen Urteile wie „alles veraltet“ und keine unbewiesenen Aussagen über CSS oder Funktionsfehler.

### Phase B – Gemeinsame Grundlage

Implementiere Tokens, Tabler-Anbindung, Typografie, Seitenrahmen, Navigation und zentrale Komponenten. Prüfe deren Auswirkungen über die inventarisierten Layoutvarianten. Führe kein pauschales globales CSS ein, das Spezialansichten beschädigt.

Lege eine tatsächliche Komponentenübersicht im Entwicklungs-/Testkontext an, sofern noch keine existiert: Buttons und Zustände, Formfelder, Tabs, Cards, Badges, Alerts, Tabelle und Dialog. Verwende echte Komponenten, nicht separat nachgebaute Demo-HTML. Keine ungeschützte Produktions-Demoroute.

### Phase C – Referenz pro Seitentyp

Migriere je eine vorhandene repräsentative Listen-, Formular-, Detail- und Einstellungsseite; dazu vorhandene besondere Facharbeitsflächen. Fehlende Seitentypen nicht neu erfinden.

Prüfe die Referenzen im Browser, korrigiere die gemeinsamen Komponenten und halte das resultierende Design fest. Ein generiertes Bild ist stilistische Orientierung, keine pixelgenaue Browser-Baseline und kein funktionaler Vertrag.

### Phase D – Alle Tools und Routen migrieren

Arbeite die vollständige Bestandsaufnahme ab. Übertrage die geprüften Bausteine auf jedes vorhandene Tool, einschliesslich Unterseiten, Modals, Rollenvarianten, Leer- und Fehlerzuständen.

Der Abschluss einer Referenzseite ist nicht der Abschluss der Migration. Bei globaler CSS-Wirkung jede betroffene Route mindestens überprüfen, statt aus einer einzigen schönen Seite auf den Rest zu schliessen.

### Phase E – Regression und Absicherung

Prüfe bestehende Kernabläufe mit realistischen Testdaten: Anzeigen, Anlegen, Bearbeiten, erlaubte Folgeaktionen, Validierung, Redirects, Tabs und Rollen. Besonders Feldnamen, Form-Methoden, Action-URLs, IDs, JS-Hooks, CSRF und das unterschiedliche Submit-Verhalten von `disabled`/`readonly` erhalten.

Nutze die vorhandenen Flask-Tests für serverseitiges Verhalten und Browser-Tests für echte Interaktion. Ein erfolgreicher Template-Render ersetzt keinen Browser-Test. Unverändertes Backend nicht pauschal behaupten, sondern den Diff prüfen.

## 12. Reproduzierbarkeit: Screenshots und visuelle Regression

Prüfe mindestens diese Viewports:

| Viewport | Zweck |
|---|---|
| 1440 × 900 | Regulärer Desktop |
| 1024 × 768 | Kleiner Desktop / Grenzfall mit Sidebar |
| 768 × 1024 | Tablet mit eingeklappter Navigation |
| 390 × 844 | Smartphone |
| 1920 × 1080 | Zusätzliche Breitenprüfung der gemeinsamen Layoutvarianten |

Alle migrierten Routen mindestens am Desktop und Smartphone prüfen. Die repräsentativen Seitentypen und gemeinsamen Komponenten zusätzlich in allen genannten Viewports prüfen. In der Abdeckungstabelle genau festhalten, welche Kombinationen tatsächlich ausgeführt wurden.

Stabile Referenzbedingungen festlegen: Browser und Version, Betriebssystem beziehungsweise Container, tatsächlich geladene Fonts, Viewport, Gerätepixelfaktor, Sprache, Zeitzone, Benutzerrolle, Testdaten und eingefrorene relevante Uhrzeit. Animationen für visuelle Tests kontrollieren, nicht wahllos im Produkt entfernen. Auf Font- und Inhaltsbereitschaft warten, nicht allein mit festen Sleep-Zeiten arbeiten.

Playwright Test kann Screenshots erzeugen und gegen Referenzen vergleichen. Rendering kann sich zwischen Umgebungen unterscheiden; Referenzen und Vergleichsläufe müssen deshalb in kontrollierten vergleichbaren Umgebungen entstehen. [S4]

Freigegebene Baselines versionieren. Der Agent darf vorgeschlagene erste Referenzen erstellen, aber sie nicht selbst als vom Auftraggeber freigegeben ausgeben. Fehlschlagende Screenshots nie blind aktualisieren, um eine Prüfung grün zu machen. Dynamische Daten nur begründet maskieren; keine eigentlichen Layoutfehler wegmaskieren.

**Ein Prompt allein ist keine Garantie für identische Oberflächen. Verbindlich wird der Standard durch gemeinsame implementierte Komponenten, zentrale Tokens und geprüfte visuelle Referenzen.**

## 13. Dauerhafte Regeln für Codex und Claude Code

Lege das konsolidierte Designsystem im Repository beispielsweise unter `docs/ui/design-system.md` ab; nutze einen vorhandenen gleichwertigen Pfad statt doppelter Dokumentation.

Ergänze die vorhandene `AGENTS.md` für Codex und die vorhandene `CLAUDE.md` für Claude Code mit einem kurzen, eindeutigen Leseauftrag. Beide Werkzeuge besitzen dokumentierte Projektanweisungsmechanismen. Bestehende Anweisungen nicht überschreiben; bereichsspezifische Regeln ebenfalls berücksichtigen. [S10, S11]

Geeigneter einzufügender Text, an den tatsächlichen Pfad angepasst:

> Vor jeder Frontend-Änderung `docs/ui/design-system.md` vollständig lesen. Die dort definierten Tokens, Komponenten, Layoutvarianten und Qualitätsprüfungen sind für alle Tools und Seiten verbindlich. Vorhandene UI-Bausteine wiederverwenden. Neue Designvarianten nur mit begründeter zentraler Entscheidung. Keine Frameworkwechsel und keine fachlichen Änderungen als Nebenprodukt. Relevante Funktionstests und visuelle Prüfungen ausführen; nicht ausgeführte Prüfungen ausdrücklich kennzeichnen. Freigegebene Screenshot-Baselines nicht ungeprüft ersetzen.

Ein Dateiname allein stellt nicht sicher, dass der gesamte Inhalt tatsächlich geladen wurde. Der Agent muss das referenzierte Designsystem lesen; halte die Startdateien kurz und die ausführliche Spezifikation an einem einzigen Ort.

## 14. Sicherheits- und Änderungsgrenzen

Keine Änderungen an Authentifizierung, Autorisierung, Session-Handling, Secrets, CSRF oder Datenverträgen als Abkürzung für UI-Arbeit. Keine zusätzlichen öffentlichen Schnittstellen und keine unkontrollierten externen Fonts, CDNs oder Telemetrie integrieren.

Keine produktiven Lösch-, Import-, Benachrichtigungs- oder Versandaktionen durch Tests auslösen. Vorhandene autorisierte Entwicklungs-/Testumgebung und synthetische Daten verwenden. Sicherheitslücken oder notwendige fachliche Erweiterungen getrennt benennen; Sicherheitsprüfungen nicht verstecken oder stillschweigend aus dem Scope entfernen.

Keine fremden Änderungen überschreiben, keine grossflächigen Rewrites und keine unautorisierten Pushes oder Deployments. In kleinen logisch prüfbaren Änderungen arbeiten. Ohne funktionsfähige Browser-Testumgebung darf Code vorbereitet werden, aber die visuelle Abnahme bleibt offen.

## 15. Lieferumfang und Definition of Done

Liefere die tatsächlichen Implementierungsänderungen, ein konsolidiertes Designsystem, konkrete Befunde, das vollständige UI-Inventar, Testbelege und Vorher-/Nachher-Screenshots. Nutze die vorhandene Dokumentations- und Teststruktur; neue Parallelordner sind kein Qualitätsmerkmal.

Die Abdeckungstabelle enthält mindestens:

| Tool / Modul | Route / Zustand | Layout | Design migriert | Funktion | Desktop | Mobile | Accessibility | Beleg / Restpunkt |
|---|---|---|---|---|---|---|---|---|

Statuswerte eindeutig verwenden: **bestanden**, **fehlgeschlagen**, **nicht ausgeführt**, **blockiert** oder begründet **nicht anwendbar**. Ein geerbtes Basis-Template beweist noch nicht, dass eine Seite vollständig geprüft ist.

Die Gesamtmigration ist erst abgeschlossen, wenn alle vorhandenen betroffenen Tools und Routen inventarisiert, migriert und entsprechend der Testmatrix geprüft sind; das Design zentral umgesetzt ist; wesentliche Abläufe weiterhin funktionieren; keine unerklärten alten Admin-Stile verbleiben; keine Attrappen oder erfundenen Daten hinzugekommen sind; und verbleibende Einschränkungen nicht verschwiegen werden.

Verwende für den Abschlussbericht:

```text
## Konkrete Ausgangsprobleme
Befund, Beleg und Auswirkung.

## Umgesetzte gemeinsame Änderungen
Tokens, Tabler-Anbindung, Layout und Komponenten.

## Abdeckung aller Tools und Seiten
Tatsächliche Namen/Routen mit Status und Restpunkten.

## Tests und Screenshots
Werkzeug, Befehl bzw. Testname, Umgebung, Ergebnis und Belegpfad.

## Änderungen ausserhalb des Frontends
Nur tatsächlich erfolgte Änderungen; sonst nach Diff-Prüfung „keine“.

## Offene Punkte / Blocker
Auswirkung und fehlende Voraussetzung. Nicht ausgeführte Prüfungen nennen.
```

## 16. Ausführungsauftrag

Beginne jetzt mit Repository- und UI-Inventar, konkreten Befunden und dem Start der vorhandenen Testumgebung. Implementiere danach die gemeinsamen Grundlagen, prüfe Referenzen pro Seitentyp und migriere sämtliche vorhandenen Tools und UI-Routen.

**Nicht nur eine Seite modernisieren. Nicht nur Farben austauschen. Nicht nur eine Liste von Empfehlungen liefern. Einen gemeinsamen, getesteten Designstandard im bestehenden Flask-/Tabler-Projekt umsetzen und die vollständige Abdeckung nachweisen.**

---

## Technische Quellen

Die Quellen erläutern Werkzeuge und technische Prüfanforderungen. Die konkrete Palette, Typografie und Layoutmasse oben sind eigenständige Projektentscheidungen. Für die Implementierung die tatsächlich installierten Versionen berücksichtigen.

- **[S1] Tabler: Customize Tabler.** Theme-Anpassung und Primärfarbe. `https://docs.tabler.io/ui/getting-started/customize`
- **[S2] Bootstrap: CSS variables / Buttons.** Globale und komponentenbezogene Variablen. `https://getbootstrap.com/docs/5.3/customize/css-variables/` und `https://getbootstrap.com/docs/5.3/components/buttons/`
- **[S3] W3C: Understanding SC 1.4.3, Contrast (Minimum).** Kontrastberechnung und Schwellenwerte. `https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html`
- **[S4] Playwright: Visual comparisons.** Screenshot-Vergleiche und Umgebungsabhängigkeit. `https://playwright.dev/docs/test-snapshots`
- **[S5] Playwright: Accessibility testing.** axe-Integration und Grenzen automatisierter Prüfungen. `https://playwright.dev/docs/accessibility-testing`
- **[S6] Flask: Testing Flask Applications.** Testclient und Testaufbau. `https://flask.palletsprojects.com/en/stable/testing/`
- **[S7] W3C: Understanding SC 1.4.11, Non-text Contrast.** Kontrast notwendiger UI-Informationen. `https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html`
- **[S8] Flask: Templates.** Jinja-Einbindung und Escaping. `https://flask.palletsprojects.com/en/stable/templating/`
- **[S9] W3C: Understanding SC 2.5.8, Target Size (Minimum).** Mindestzielgrössen und Ausnahmen. `https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html`
- **[S10] OpenAI: Custom instructions with AGENTS.md.** Projektanweisungen für Codex. `https://developers.openai.com/codex/guides/agents-md/`
- **[S11] Anthropic: How Claude remembers your project.** Projektanweisungen über CLAUDE.md. `https://code.claude.com/docs/en/memory`
 prompt für UI polish bzw. UI überarbeitung. auch ins backlog, kleine wps erzeugen.
