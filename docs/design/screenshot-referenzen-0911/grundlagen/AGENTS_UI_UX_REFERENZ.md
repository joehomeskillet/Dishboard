> Historische Agentenregeln als Referenz; nicht ungeprüft über eine Projekt-AGENTS.md kopieren. Das lokale Konzept liegt in [UI_UX_KONZEPT.md](UI_UX_KONZEPT.md), die neue Bildzuordnung in [UI_REFERENZEN.md](../UI_REFERENZEN.md).

# AGENTS.md — verbindliche UI/UX-Regeln für Dishboard

## 1. Auftrag und Pflichtlektüre

Du arbeitest an der UI/UX-Überarbeitung der Menüplanung der Klinik Südhang. Die Benutzer haben sehr geringe technische Erfahrung. Das Ergebnis muss verständlich, fehlertolerant und hochwertig gestaltet sein.

**Lies vor jeder Änderung vollständig `docs/UI_UX_KONZEPT.md`.** Das Dokument enthält Zielbild, Schutzgrenzen, Anforderungen mit IDs, Arbeitspakete und Abnahmetests. Diese Datei regelt deine Arbeitsweise; das Konzept ist die detaillierte Referenz.

Bestehende Projekt-, Sicherheits- und Agentenregeln bleiben erhalten. Eine vorhandene `AGENTS.md` darf nicht ungeprüft durch diese Datei ersetzt werden. Bei Integration werden die Regeln zusammengeführt. Widersprüche werden vor dem betroffenen Eingriff offengelegt, nicht stillschweigend zu deinen Gunsten aufgelöst.

## 2. Unverhandelbare Grenzen

| Regel | Verpflichtung |
|---|---|
| **A-01 · Unterbau erhalten** | Flask, Tabler, Datenbank, Datenmodelle, Routenverträge, Authentifizierung, Berechtigungen, Prüf-/Publikationslogik und Betriebsarchitektur bleiben unverändert. |
| **A-02 · Keine neuen Abhängigkeiten** | Kein Frameworkwechsel, keine SPA, kein zusätzliches Bootstrap, kein neues UI-/Drag-/Icon-/Schriftpaket, kein neuer Dienst und kein erzwungenes Versionsupgrade. |
| **A-03 · Begrenzter Änderungsbereich** | Standardmässig nur Templates, bestehende Styles/Assets, kleine UI-Skripte, Tests und Dokumentation. Python-View-Anpassungen nur mit der im Konzept beschriebenen separaten Genehmigung. |
| **A-04 · Verträge bewahren** | Vorhandene URLs, HTTP-Methoden, Formularnamen, IDs, Enumwerte, CSRF-Verfahren, Validierung und fachliche Wirkungen nicht verändern. Sichtbare Umbenennung ist keine Vertragsänderung. |
| **A-05 · Keine erfundenen Funktionen** | Kein Autosave, Live-Preview, Undo, Prüfergebnis, Versionsstand oder Publikationserfolg ohne tatsächlich bestätigte Grundlage. |
| **A-06 · Sicherheit nicht nur anzeigen** | Serverprüfungen bleiben wirksam. Keine Freigabe nur im Browser, keine Rechteprüfung nur durch ausgeblendete Buttons, kein ungeprüftes HTML-Rendering. |
| **A-07 · Daten nicht umdeuten** | Leere Allergene sind nicht allergenfrei. Titel und KI-Vermutungen werden nicht zu Deklarationen. Zutaten und Bausteine nicht im Datenmodell zusammenlegen. |
| **A-08 · Angebote trennen** | Patienten: Montag–Sonntag, Mittag und Abend, keine Preise. Cafeteria: vorhandene Menüarten, Servicekonfiguration und beide Preisgruppen erhalten. |
| **A-09 · Keine Funktion versteckt entfernen** | Alle bisherigen Einstiege bleiben sinnvoll erreichbar. Filter, Historien und seltene Funktionen dürfen reduziert sichtbar, aber nicht still gelöscht werden. |
| **A-10 · Keine ungefragten Produktivaktionen** | Keine produktiven Menüveröffentlichungen, Datenmigrationen, destruktiven Datenänderungen oder ungefragten Deployments für UI-Tests. |

Kann eine UX-Anforderung nur durch Verletzung dieser Grenzen erfüllt werden, stoppe den betroffenen Teil. Dokumentiere Anforderungs-ID, nachgewiesene technische Ursache und kleinste mögliche Alternative. Arbeite nur an unabhängigen, nicht blockierten Teilen weiter. Ein nicht umsetzbarer Komfortteil wird nicht durch eine Attrappe ersetzt.

## 3. Verbindliches Bedien- und Gestaltungsziel

Die Anwendung ist ein **Wochenplaner für die Küche**, kein allgemeines Datenbank-Adminfrontend.

| Bereich | Muss-Ziel |
|---|---|
| Navigation | Höchstens vier fachliche Einstiege: Wochenplan; Menüs & Bausteine; Vorschau & Bildschirme; Einstellungen. Vorhandene Rechte respektieren. |
| Wochenplan | Menüs stehen im Vordergrund. Breite auf grossen Screens nutzen; auf kleinen Screens in lesbare Tagesabschnitte wechseln. |
| Orientierung | Bereich, Datum, Mahlzeit und Menüart klar anzeigen. Datumsbereich nicht aus einem möglicherweise falschen Freititel ableiten. |
| Aktionen | Eine hervorgehobene Hauptaktion je aktivem Kontext; keine mehrfach verstreuten Prüfbuttons. |
| Bearbeitung | Seitliches Bearbeitungsfenster als Ziel, vollständige Editorseite als erhaltener Weg. Keine neue Speicher-API dafür bauen. |
| Formulare | Sichtbare Labels, klare Reihenfolge, ein eindeutiger Speicherbutton, Eingaben bei Fehlern erhalten. |
| Speichern/Prüfen/Veröffentlichen | Unterschied und tatsächlich betroffenen Datenstand verständlich machen; keine neue Transaktions-/Statuslogik. |
| Bausteine | Kompakte Zeilen; eindeutige Auswahl zwischen Katalog und vorhandenem Freitextweg. Sortieren ohne Ziehen möglich. |
| Suche | Suche und wenige Hauptfilter; weitere Filter gezielt öffnen, aktive Filter sichtbar halten. |
| Erscheinungsbild | Gemeinsame Tokens aus dem Konzept, bestehende Marke, lesbare Typografie, klare Flächen, konsistente Abstände. |
| Bedienbarkeit | Kerncontrols mindestens 44 Pixel hoch, auf Touch vorzugsweise 48; Tastatur, Zoom und Smartphone berücksichtigen. |
| Ausgaben | Keine Adminnavigation oder neuen internen Prüfhinweise auf öffentlichen Seiten/Bildschirmen. Admin-CSS begrenzen. |

Keine reinen Symbol-Kernaktionen, keine Hover-Pflicht, kein Drag-and-Drop-Zwang, keine verschachtelten Modaldialoge, keine abgeschnittenen Pflichtinformationen. „Schick“ bedeutet hier konsistent und lesbar, nicht mehr Animation, mehr Karten oder kleinere Schrift.

## 4. Arbeitsbeginn: Bestandsaufnahme statt Vermutungen

**WP-00 ist verpflichtend.** Erfasse vor der Implementierung die tatsächlichen Templates, Komponenten, installierten Assets, Formularverträge und vorhandenen Prüf-/Publikationsregeln. Prüfe, ob vorgeschlagene Komfortfunktionen wirklich vorhanden sind oder mit bestehenden Verträgen funktionieren.

Die Screenshots im Paket sind ein visueller Ist-Nachweis. Sie belegen keine Backendsemantik. Behaupte nicht, eine Route, ein Statusfeld oder ein Test existiere, bevor du dies im Projekt geprüft hast.

Dokumentiere mindestens:

| Gegenstand | Erforderlicher Nachweis |
|---|---|
| UI-Dateien | Tatsächliche Pfade und gemeinsamer Seitenrahmen. |
| Assets | Vorhandene Tabler-/Bootstrap-/Schrift-/Iconeinbindung; keine Doppelbeladung. |
| Angefasste Formulare | Route, Methode, Feldnamen, CSRF, Rollen, Fehler-/Erfolgsantwort und Wirkung. |
| Zustände | Was „gespeichert“, „geprüft“, „veröffentlicht“ und „Entwurf“ im Bestand tatsächlich bedeutet. |
| Ausgabegrenzen | Welche Templates/Styles Admin, öffentliche Ansichten und Signage verwenden. |
| Baseline | Vorhandene Testergebnisse und dokumentierte bereits bestehende Fehler. |

## 5. Umsetzung in kleinen Arbeitspaketen

Arbeite in der Reihenfolge und mit den Abhängigkeiten aus Kapitel 12 des Konzepts. Benenne vor jedem Paket Ziel, Anforderungs-IDs, betroffene Dateien und Prüfungen. Keine grossflächigen Nebenrefactorings.

Gemeinsame Tokens, Seitenrahmen und Formularpartiale haben eine koordinierte Verantwortung. Parallel arbeitende Agenten dürfen nicht unabhängig konkurrierende globale Styles oder Formulare erzeugen. Bei einer Teamaufteilung koordiniert ein Integrationsverantwortlicher diese gemeinsamen Dateien; ein Reviewer prüft technische Grenzen und Regressionen.

Verwende bestehende Tabler-Muster und Jinja-Wiederverwendung. Keine zweite unabhängige Menüformularimplementierung für das Panel. Keine „vorübergehende“ neue Abhängigkeit, die nachher im Projekt bleibt.

## 6. Pflichtprüfung vor Übergabe

Führe die für dein Paket einschlägigen Tests T01–T34 aus dem Konzept aus. Prüfe zusätzlich die bestehenden Regressionstests. Verwende vorhandene Werkzeuge; installiere nicht ungefragt eine neue Testinfrastruktur.

Für geänderte Schreibabläufe sind erfolgreiche Eingabe, Validierungsfehler, fehlende Rechte, ungespeicherter Abbruch und eine unklare/fehlgeschlagene Antwort zu prüfen. Für neue Layouts sind mindestens Desktop, kleiner Laptop, Tablet und Smartphone relevant; Grössen stehen im Konzept.

Sichtprüfung bedeutet echte gerenderte Seiten ansehen: normale Daten, lange Texte, leerer Zustand, Fehlerzustand und offene Prüfung. Code lesen oder einen CSS-Build erfolgreich ausführen ersetzt das nicht. Fehlende Browser-/Screenshotwerkzeuge werden als Grenze gemeldet; keine erfundenen Bilder oder angeblichen Tests.

Der Test mit mindestens drei technisch unerfahrenen Personen kann nicht durch dich als Agent ersetzt werden. Solange er fehlt, bleibt die Nutzerabnahme ausstehend.

## 7. Abschlussbericht — Pflichtformat

| Feld | Inhalt |
|---|---|
| Arbeitspaket | WP-ID und tatsächlich umgesetzter Umfang. |
| Anforderungen | Erfüllte IDs; nicht erfüllte oder blockierte IDs ausdrücklich getrennt. |
| Dateien | Tatsächlich geänderte Pfade. |
| Vertragscheck | Welche bestehenden Formulare/Schreibwege unverändert erhalten wurden. |
| Tests | Wirklich ausgeführte Befehle oder manuelle Schritte und ihre Ergebnisse. |
| Sichtnachweise | Tatsächliche Screenshots mit Viewport und Zustand oder ehrliche Angabe, dass sie fehlen. |
| Technischer Schutz | Bestätigung anhand des Diffs, dass kein ungefragter Unterbauwechsel enthalten ist. |
| Offen/Blockiert | Konkreter Grund und benötigte Entscheidung; kein pauschales „alles fertig“. |

**Ein nicht ausgeführter Test gilt nicht als bestanden. Ein schöner Screenshot beweist keinen funktionierenden Ablauf. Eine funktionierende Demo mit falscher Fachlogik ist nicht abnahmefähig.**

## 8. Review-Ausschlusskriterien

Ein Review lehnt insbesondere ab: reine kosmetische Überarbeitung ohne vereinfachten Ablauf; neue Frameworks/Verträge; verschwundene Bestandsfunktionen; falsches Autosave; vorgetäuschte Vorschautreue; automatisch bestätigte Allergene; Preise im Patientenplan; Tastatur-/Touch-unbedienbare Kernfunktionen; verdeckte Fehler; ungeprüfte öffentliche CSS-Nebenwirkungen; erfundene Testergebnisse.

Die Entscheidung bei Konflikten lautet: **korrekte Daten und Sicherheit → unveränderter Unterbau → verständliche Bedienung → konsistente Gestaltung → zusätzliche Komforteffekte.**
