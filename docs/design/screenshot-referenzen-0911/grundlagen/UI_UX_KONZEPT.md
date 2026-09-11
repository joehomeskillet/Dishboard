> Paketkopie: Inhaltliche Anforderungen unverändert; lokale Bildverweise an dieses ZIP angepasst. Einstieg und aktuelle Bildzuordnung: [UI_REFERENZEN.md](../UI_REFERENZEN.md). Die Screenshotfreigaben in der zentralen Referenztabelle sind massgeblich.

# Dishboard — verbindliches UI/UX-Konzept

**Projekt:** Klinik Südhang · Menüplanung  
**Stand:** 7. September 2026  
**Dokumentstatus:** Zielvorgabe für die nächste UI-Iteration; keine Behauptung über bereits umgesetzte Funktionen  
**Zielgruppe:** Küchenmitarbeitende mit sehr geringer technischer Erfahrung  
**Technischer Rahmen:** Bestehendes Flask, bestehendes Tabler und bestehender technischer Unterbau bleiben erhalten.  
**Geltung:** Für alle Agenten und Personen, die diese UI-Iteration planen, implementieren, prüfen oder zusammenführen.

> **Leitentscheidung:** Die Anwendung wird ein verständlicher Wochenplaner für die Küche, nicht ein schöner gefärbtes Datenbankformular. Die vorhandene Fachlogik wird verständlich dargestellt, nicht ersetzt.

## 0. Verbindlichkeit, Quellen und Grenzen

### 0.1 Bedeutung der Anforderungen

| Kennzeichnung | Verbindlichkeit |
|---|---|
| **MUSS** | Voraussetzung für die Abnahme. Eine nicht erfüllte Anforderung bleibt offen oder blockiert. |
| **DARF NICHT** | Ausschlusskriterium. Eine solche Umsetzung darf nicht als fertig freigegeben werden. |
| **SOLL** | Vorgesehene Umsetzung. Eine Abweichung braucht eine dokumentierte Begründung und explizite Freigabe. |
| **OPTIONAL** | Nur nach den Pflichtanforderungen und ohne zusätzliche technische Infrastruktur. |

Explizite Projektvorgaben, Sicherheit und der Schutz des bestehenden Unterbaus haben Vorrang vor einer Komfortfunktion. Agenten dürfen einen Konflikt nicht durch eine eigenmächtige Änderung am Backend auflösen. Sie dokumentieren die betroffene Anforderung, den nachgewiesenen Grund und die kleinste mögliche Alternative. Nicht betroffene Arbeitspakete können weiterlaufen.

Die Datei `AGENTS.md` im Paket regelt die Arbeitsweise. Dieses Konzept ist die fachliche und gestalterische Referenz. Regeln dürfen nicht stillschweigend abgeschwächt werden, um einen Test oder einen Abschlussbericht grün zu bekommen.

### 0.2 Was bekannt ist — und was nicht

Die Ist-Bewertung basiert auf den fünf bereitgestellten Screenshots: Wochenplan, Menüeditor, Komponenten, Grundlagen sowie Design & Marke. Die aktuelle Codebasis, installierte Paketversionen und tatsächlichen Request-/Response-Verträge wurden für dieses Dokument nicht untersucht. Deshalb benennt dieses Dokument keine angeblich vorhandenen neuen Routen, Datenfelder oder Funktionen.

| Grundlage | Verwendung |
|---|---|
| Aktueller Auftrag | Technisch sehr unerfahrene Benutzer, hochwertige Gestaltung, Flask/Tabler und Unterbau unverändert. |
| Screenshots E1–E5 | Nachweis für sichtbare Probleme und vorhandene Oberflächen. Kein Nachweis für Backendverhalten. |
| Bestehender Projektkontext | Cafeteria und Patientenangebot getrennt; Patienten Montag–Sonntag, Mittag und Abend, ohne Preise; Cafeteria mit Preisen für Mitarbeitende und Externe. |
| Offizielle Dokumentation S1–S10 | Referenz für die Nutzung vorhandener UI-Komponenten und ausgewählte Anforderungen an Zugänglichkeit. Kein Auftrag für ein Versionsupgrade. |

**IST-01 — Bestandsaufnahme ist Pflicht.** Vor der Umsetzung sind vorhandene Templates, Formulare, Routen, Rollenprüfungen und Prüf-/Publikationsregeln zu lesen. Unbekanntes bleibt als unbekannt gekennzeichnet. Neue Produktfunktionen werden nicht aus einer Designskizze abgeleitet.

### 0.3 Sichtbare Probleme, die diese Iteration lösen soll

| Referenz | Beobachtung | Verbindliche Konsequenz |
|---|---|---|
| E1 · Wochenplan | Mehrfach platzierte Prüfaktionen; Tagesangaben und Hinweise verdrängen die Planung. | Eine klare Wochensteuerung; Menüs vor Verwaltungsdetails. |
| E1 · Wochenplan | Wenig nutzbare Arbeitsfläche; ein einzelner Tag benötigt viel Höhe. | Breiter Wochenarbeitsplatz auf grossen Bildschirmen, lesbare Tagesansicht auf kleinen. |
| E1 · Wochenplan | Wochenüberschrift/KW, Montag 7. September und Freititel „31. August bis 6. September“ passen sichtbar nicht zusammen. | Datumsidentität aus dem tatsächlich geplanten Zeitraum anzeigen; widersprüchliche Zusatztexte nicht als Zeitraum verwenden. Ursache separat prüfen. |
| E2 · Menüeditor | Mehrere Speicher-/Prüfaktionen; langer formularorientierter Aufbau. | Ein klarer Bearbeitungskontext mit verständlichem nächsten Schritt. |
| E2 · Menüeditor | Katalogauswahl und Freitext stehen gleichzeitig nebeneinander. | Eingabeart eindeutig wählen; nie unklar lassen, welcher Wert gespeichert wird. |
| E3 · Komponenten | Acht sichtbare Filter vor einer kleinen Trefferliste. | Suche und wenige Hauptfilter; weitere Filter gezielt öffnen. |
| E4 · Grundlagen | Unverständlicher Bereichsname; leere Liste mit unnötiger Seitennavigation. | Küchennahe Begriffe und handlungsorientierte Leerzustände. |
| E5 · Design | Technische Versionsbegriffe und gespeicherte Vorschau dominieren. | „Aktuelles Design“, „Entwurf“ und klar benannte Vorschau; Versionierung bleibt im Hintergrund erhalten. |

Referenzbilder sind im Paket unter `../ist/frueher/` abgelegt. Sie zeigen den Ausgangszustand, nicht die gewünschte Gestaltung.

---

## 1. Produktprinzipien für technisch unerfahrene Benutzer

**UX-01 — Die Oberfläche beantwortet jederzeit drei Fragen:** „Wo bin ich?“, „Was ist noch offen?“ und „Was mache ich als Nächstes?“ Bereich, Zeitraum und Bearbeitungskontext sind sichtbar; die nächste sinnvolle Handlung ist beschriftet.

**UX-02 — Sichtbare Schaltflächen statt versteckter Bedienkonzepte.** Die Kernaufgaben funktionieren durch Lesen und Klicken bzw. Tippen. Doppelklick, Rechtsklick, Hover, Tastenkürzel oder Ziehen dürfen nie Voraussetzung sein. Symbole ergänzen verständliche Wörter, ersetzen sie aber bei Kernaktionen nicht.

**UX-03 — Eine hervorgehobene Hauptaktion je aktivem Arbeitskontext.** Auf der Wochenübersicht beispielsweise „Offene Angaben prüfen“, im Editor „Menü speichern“. Ein offener modaler Editor bildet einen eigenen Kontext; die Aktionen der Hintergrundseite sind dann nicht bedienbar.

**UX-04 — Seltenes erst bei Bedarf anzeigen.** Öffnungszeiten, technische Details, umfangreiche Filter und Versionsverläufe werden gezielt geöffnet. Pflichtfelder, Fehler, wesentliche Prüfhinweise und Publikationshindernisse dürfen dabei nicht verschwinden.

**UX-05 — Verlässlichkeit vor vermeintlicher Einfachheit.** Speichern, Prüfen und Veröffentlichen sind unterschiedliche Handlungen. Die Oberfläche darf sie weder sprachlich vermischen noch technisch zusammenlegen, wenn das bestehende System sie getrennt verarbeitet.

**UX-06 — Klartext auf Deutsch, Schweizer Schreibweise.** Kurze vollständige Sätze, „ss“ statt „ß“, „Mitarbeitende“, „Externe“, „Veröffentlichen“, „Bausteine“. Keine Begriffe wie CRUD, Payload, Drawer, Revision oder Workflow im normalen Küchenablauf.

### 1.1 Wichtigste Benutzeraufgaben

| Aufgabe | Erwartetes Erlebnis |
|---|---|
| Ein Menü für Dienstag ändern | Woche sehen, Menü öffnen, ändern, speichern, wieder am gleichen Ort sein. |
| Eine neue Woche vorbereiten | Gewünschte Woche wählen, vorhandene Kopier-/Vorlagenfunktion erkennen, Wirkung verstehen. |
| Eine fehlende Angabe ergänzen | Hinweis lesen, direkt zum betroffenen Feld gelangen, Angabe speichern. |
| Einen fertigen Plan veröffentlichen | Offene Punkte nachvollziehen, Vorschau ansehen, bewusst veröffentlichen. |
| Einen Baustein finden | Begriff eingeben; passende Treffer sehen; keine Filterkenntnisse brauchen. |
| Den Patientenplan ansehen | Sofort erkennen: sieben Tage, Mittag und Abend, keine Preise. |

Die Arbeitsfläche startet nach dem vorhandenen Login möglichst direkt beim Wochenplan, soweit der bestehende Navigationsablauf das ohne Änderung am Authentifizierungsunterbau erlaubt. Ein zusätzliches Dashboard mit Kennzahlen, Diagrammen oder Begrüssungskarten ist nicht Teil dieses Auftrags.

---

## 2. Unveränderlicher technischer und fachlicher Rahmen

### 2.1 Technische Schutzgrenzen

**TECH-01 — Kein Stackwechsel und kein versteckter Umbau.**

| Bereich | Erlaubt | Nicht erlaubt |
|---|---|---|
| Flask/Jinja | Vorhandene Templates umstrukturieren, Partials und Makros für Darstellung wiederverwenden. | Flask ersetzen, SPA einführen, Rendering-Architektur austauschen. |
| Tabler | Installierte Komponenten und vorhandene Assets verwenden; gezielte Design-Tokens/Overrides ergänzen. | Tabler ersetzen, zweite Bootstrap-Kopie laden, Upgrade als Voraussetzung einführen. |
| Gestaltung | HTML-Struktur, CSS, responsive Layouts, lesbare Beschriftungen, vorhandene Icons. | Zweites Designsystem, neue Iconbibliothek, neue externe Schrift-/Assetdienste. |
| JavaScript | Kleine lokale Verbesserungen im bestehenden Assetweg, etwa Panelsteuerung oder Formularwarnungen. | React, Vue, Svelte, Alpine, HTMX oder andere bislang nicht vorhandene Laufzeitabhängigkeiten ergänzen. |
| Datenhaltung | Bestehende Daten unverändert lesen und über vorhandene Formulare bearbeiten. | Migrationen, neue Tabellen, Spalten, Modelle, Statuswerte, Storage- oder Cachekonzepte. |
| Verträge | Vorhandene URLs, Methoden, Formularnamen, IDs und Antwortsemantik verwenden. | Neue API-/Schreibrouten, geänderte Payloads, andere Kopier- oder Speichersemantik. |
| Fachlogik | Vorhandene Ergebnisse verständlich anzeigen. | Neue Allergenberechnung, Prüfregeln, Freigabeketten oder Preislogik. |
| Sicherheit | Bestehende Rollen-, CSRF-, Session- und serverseitige Validierungsprüfungen vollständig erhalten. | Sicherheitsprüfungen durch ausgeblendete Buttons oder JavaScript ersetzen. |
| Betrieb | Bestehende Tests ergänzen, bestehende Build-/Startwege verwenden. | Docker-/Deployment-Umbau, neue Dienste, neue Buildpipeline, ungefragte Veröffentlichung. |

**TECH-02 — Standardänderungsbereich:** Templates, projektbezogene Styles, vorhandener JavaScript-Assetbereich, Tests und Dokumentation. Änderungen an Python-Views sind nicht pauschal freigegeben. Eine allenfalls nötige, ausschliesslich darstellungsbezogene Weitergabe bereits vorhandener Daten muss vorab separat begründet und genehmigt werden; Verträge und Fachlogik bleiben auch dabei unverändert.

**TECH-03 — Keine vorgetäuschten Funktionen.** Kein „automatisch gespeichert“, wenn kein bestehender bestätigter Speichervorgang stattgefunden hat. Keine grüne Prüfung aus einem lokalen Formularzustand. Keine funktionierenden Demo-Buttons ohne echte Anbindung. Kein „Rückgängig“, wenn das System die vorherige Änderung nicht wirklich rückgängig machen kann.

**TECH-04 — Vorhandene Formularwege bleiben nutzbar.** Zusätzliche Panelbedienung darf ein funktionierendes Formular nicht durch eine nur teilweise funktionierende JavaScript-Lösung ersetzen. Die normale Editorseite bleibt eine nutzbare Alternative. Fehler, Berechtigungen und Speichern müssen in beiden Darstellungen gleich wirken.

Flask integriert Jinja und aktiviert bei üblichen HTML-Templates standardmässig Autoescaping. Diese Schutzwirkung bleibt erhalten; ungeprüfte Menü-/Hinweistexte dürfen nicht über `safe`-Ausnahmen eingebracht werden. [S2]

### 2.2 Fachliche Grenzen

**FACH-01 — Angebotsbereiche bleiben getrennt.**

| Merkmal | Cafeteria | Patienten |
|---|---|---|
| Zielgruppe | Mitarbeitende und externe Gäste | Patientinnen und Patienten |
| Reguläre Planung | Montag–Freitag, Mittag; bestehende Bereichs-/Servicekonfiguration ist massgeblich. | Montag–Sonntag, Mittag und Abend. |
| Menüarten | Bestehende zwei Menüarten; Benennungen aus dem Bestand. | Vorhandene Menüarten; keine neue Anzahl erfinden. |
| Preise | Mitarbeitende und Externe getrennt. | Keine Preisfelder oder Preisangaben im Patientenablauf und in der Patientenausgabe. |
| Ausnahmen | Bestehende Schliessungen und Sonderzeiten berücksichtigen. | Vorhandene Tages-/Serviceausnahmen erhalten. |

**FACH-02 — Oberfläche ist kein Datenmodell.** „Komponenten“ dürfen in der Bedienung „Bausteine“ heissen. Zutaten und Komponenten werden deshalb weder in der Datenbank zusammengelegt noch bei Auswahl oder Speicherung verwechselt. Eine fachliche Datenebene darf nicht allein für ein einfacheres Menü abgeschafft werden.

**FACH-03 — Keine neuen Fähigkeiten aus Wunschbildern ableiten.** Vorlagen, Duplizieren, Vorschauen, Varianten oder Prüfzahlen erscheinen nur mit tatsächlicher Unterstützung im Bestand. Fehlt eine vorausgesetzte Fähigkeit, wird eine Lücke gemeldet; der UI-Auftrag ist kein Auftrag zum Neubau dieser Fähigkeit.

---

## 3. Navigation und Begriffe

### 3.1 Vier verständliche Hauptbereiche

**NAV-01 — Die linke Hauptnavigation enthält höchstens vier fachliche Einstiege.** Konto/Abmelden ist ein separater unterer Bereich. Vorhandene Berechtigungen bestimmen die Sichtbarkeit; es werden keine neuen Rollen eingeführt.

| Hauptbereich | Inhalt | Zweck |
|---|---|---|
| **Wochenplan** | Woche auswählen, Cafeteria/Patienten, vorhandene Wochenübersicht und Vorlagenaktionen. | Die tägliche Planungsarbeit. |
| **Menüs & Bausteine** | Bestehende Menüs, Bausteine, Zutaten; bei Bedarf zugehörige Stammdaten. | Wiederverwendbare Inhalte finden und pflegen. |
| **Vorschau & Bildschirme** | Bestehende Website-/Mobilvorschau, Bildschirme und Ausgabevorlagen. | Prüfen, was die jeweilige Zielgruppe tatsächlich sieht. |
| **Einstellungen** | Bereiche/Zeiten, Design, Import, Schnittstellen, Benutzer und technische Stammdaten. | Seltene Verwaltungsaufgaben. |

Die Hauptnavigation ist flach. Unterbereiche werden innerhalb der jeweiligen Seite als beschriftete Tabs oder einfache Unterseiten angeboten. Mehr als zwei Navigationsebenen sind nicht vorgesehen. Ein unerfahrener Benutzer muss weder „Grundlagen“ noch „Wochenverwaltung“ verstehen, um einen Plan zu bearbeiten.

### 3.2 Zuordnung bestehender Einstiege

| Bisheriger Eintrag | Neuer sichtbarer Ort | Schutzregel |
|---|---|---|
| Wochenpläne | Wochenplan | Bestehende URLs bleiben erhalten. |
| Wochenverwaltung | Wochenplan → Woche auswählen / Wochenübersicht | Bestehende Verwaltungsfunktionen bleiben erreichbar. |
| Menüs | Menüs & Bausteine → Menüs | Erst prüfen, ob es ein Katalog oder eine Liste geplanter Menüeinträge ist; nichts umdeuten. |
| Komponenten | Menüs & Bausteine → Bausteine | Datenmodell bleibt unverändert. |
| Grundlagen → Zutaten | Menüs & Bausteine → Zutaten | Zutaten nicht mit fertigen Beilagen/Rezeptbausteinen gleichsetzen. |
| Grundlagen → Einheiten/Kategorien/Tags | Passende Unterseiten in Menüs & Bausteine oder Einstellungen | Begriffe vereinheitlichen, Datensätze nicht verschmelzen. |
| CSV Import | Einstellungen → Daten importieren | Format, Validierung und vorhandener Importablauf bleiben gleich. |
| Screens | Vorschau & Bildschirme → Bildschirme | Bestehende Player-/Ausgabeadressen unverändert. |
| Vorlagen | Menüvorlagen bei Menüs & Bausteine; Ausgabevorlagen bei Vorschau & Bildschirme | Tatsächlichen Vorlagentyp im Bestand ermitteln, nicht raten. |
| API & Schnittstellen | Einstellungen → Schnittstellen | Berechtigungen unverändert. |
| Benutzer & Zugriff | Einstellungen → Benutzer & Zugriff | Keine clientseitige Ersatzberechtigung. |
| Design & Marke | Einstellungen → Erscheinungsbild | Bestehende Aktivierung und Versionshistorie erhalten. |
| Bereiche & Zeiten | Einstellungen → Bereiche & Öffnungszeiten | Semantik bestehender Services erhalten. |

**NAV-02 — Kein Funktionsverlust durch Aufräumen.** Vorher/nachher ist eine vollständige Zuordnung aller bisherigen Einstiege zu erstellen. Weniger Navigation bedeutet nicht weniger erreichbare Funktionen.

### 3.3 Wörterbuch für die Oberfläche

| Vermeiden | Verwenden |
|---|---|
| Publizieren | Veröffentlichen |
| Komponente | Baustein; einmal erklären: „Zum Beispiel eine Beilage, Sauce oder ein Gemüse.“ |
| Service | Ausgabe / Öffnungszeit, abhängig von der tatsächlichen Bedeutung |
| Revision | Version, nur im optionalen Verlauf |
| Grundlagen | Zutaten, Einheiten oder Kategorien konkret benennen |
| Prüfung offen | Noch zu prüfen; daneben den konkreten Grund anzeigen |
| Wochenvorgaben übernehmen | Standardzeiten ergänzen — nur wenn dies die tatsächliche Wirkung trifft |
| Freitext-Komponente | Eigener Baustein als Text |
| Externe CHF | Preis für externe Gäste · CHF |

Fachlich unterschiedliche Begriffe werden nicht aus Bequemlichkeit vereinheitlicht: „Menü“ ist der geplante Eintrag, „Baustein“ ein Bestandteil und „Zutat“ ein Rohstoff, soweit der Bestand diese Unterscheidung tatsächlich verwendet.

---

## 4. Verbindliche Gestaltungsrichtung

### 4.1 Zielbild

**VIS-01 — Ruhige, hochwertige Arbeitsoberfläche.** Heller neutraler Arbeitsbereich, weisse Inhaltsflächen, dunkle petrolfarbene Navigation und gezielte Südhang-Akzente. Qualität entsteht durch Ausrichtung, Typografie, klare Zustände und genügend Platz, nicht durch zusätzliche Dekoration.

Das bestehende Südhang-Logo bleibt erhalten und wird nicht verzerrt. Die bestehende Schrift bleibt; sofern Fira Sans tatsächlich eingebunden ist, wird sie weiterverwendet. Keine neue Schriftbibliothek und keine neuen externen Fontabrufe.

**DARF NICHT:** Glassmorphism, dekorative Verläufe, riesige Begrüssungsflächen, erfundene Kennzahlen, generierte Essensbilder, animierte Hintergründe, wahllose Farben pro Menü, mehrfache Schatten auf verschachtelten Karten oder ein ungefragter Dark-Mode-Umbau.

### 4.2 Gemeinsame Design-Tokens

Die folgenden Werte sind die Ausgangsvorgabe für die UI-Iteration, keine Behauptung über bestehende CSS-Werte. Sie werden zentral auf die vorhandenen Tabler-Variablen bzw. den bestehenden projektbezogenen Override-Bereich abgebildet. Kein separater Farben-/Abstands-Satz pro Seite.

| Zweck | Zielwert | Regel |
|---|---|---|
| Seitenhintergrund | `#F5F4F1` | Ruhiger, leicht warmer Hintergrund. |
| Inhaltsfläche | `#FFFFFF` | Formulare, Tabellen und Menüobjekte. |
| Haupttext | `#242B32` | Gute Lesbarkeit, nicht hellgrau. |
| Sekundärtext | `#59636E` | Hinweise bleiben gut lesbar. |
| Primärfarbe | `#8C1C4B` | Südhang-Akzent, primäre Aktion. |
| Primärfarbe Hover | `#74133D` | Dunkler, ohne Grössensprung. |
| Navigation | `#19383B` | Dunkles Petrol. |
| Navigationstext | `#E2ECEC` | Heller, kontrastreicher Text. |
| Aktiver Navigationseintrag | `#294C50` | Fläche plus Schriftgewicht/Markierung, nicht nur Farbe. |
| Dekorative Trennlinie | `#D4D9DE` | Nicht automatisch als ausreichender Eingaberand betrachten. |
| Erkennbarer Eingaberand | `#7B8791` | Eingabefelder müssen gegen ihre Umgebung erkennbar bleiben. |
| Fokus | `#1E65B8` | Deutlich sichtbare, kontrastgeprüfte Kontur mit Abstand. |
| Entwurf | Text `#4F5D6B`, Fläche `#EDF0F3` | Immer mit ausgeschriebenem Status. |
| Zu prüfen | Text `#805600`, Fläche `#FFF3CD` | Kein blosses Warnsymbol. |
| Fehler | Text `#A12727`, Fläche `#FDECEC` | Fehlerursache und Handlung ergänzen. |
| Erfolgreich / geprüft | Text `#21633E`, Fläche `#E8F4ED` | Nur bei tatsächlichem passenden Zustand. |

**VIS-02 — Alle tatsächlich verwendeten Farbkombinationen werden geprüft.** Auch Hover, Fokus, deaktivierte Zustände und aktiver Tab sind zu berücksichtigen. Eine Tokenliste allein ist kein Nachweis. Das Markendesign für öffentliche Ausgaben und das Admin-UI dürfen durch CSS-Vererbung nicht versehentlich gekoppelt werden.

### 4.3 Typografie, Abstände und Grössen

| Element | Vorgabe |
|---|---|
| Grundschrift | 16 CSS-Pixel als Ausgangswert; relativ skalierbar, keine erzwungene Verkleinerung des Root-Fonts. |
| Hinweise, Labels, Status | In der Regel 14–16 CSS-Pixel; keine 10-/11-Pixel-Bedienhinweise. |
| Seitentitel | 28–32 CSS-Pixel, auf kleinen Screens 24–28. |
| Abschnittstitel | 18–20 CSS-Pixel. |
| Menüname | 16–18 CSS-Pixel, deutliches Schriftgewicht. |
| Zeilenhöhe | Fliesstext etwa 1,45–1,6. |
| Kernbuttons/Eingaben | Mindestens 44 CSS-Pixel hoch; auf Touchgeräten vorzugsweise 48. |
| Kompakte Symbolschaltfläche | Mindestens 44 × 44 CSS-Pixel Klickfläche; zugänglicher Name. |
| Abstandsserie | 4, 8, 12, 16, 24, 32, 48 CSS-Pixel; keine willkürlichen Einzelabstände. |
| Karten | Meist 16–20 Pixel Innenabstand, 10–12 Pixel Radius, dezente Linie statt dominanter Schatten. |
| Tabellenzeilen | Mindestens etwa 56 Pixel, bei mehrzeiligem Inhalt automatisch höher. |

Die 44-Pixel-Vorgabe ist bewusst ein Projektziel für diese Zielgruppe. WCAG 2.2 AA nennt für Zeigerziele grundsätzlich 24 × 24 CSS-Pixel mit Ausnahmen; dieses Dokument setzt grössere Bedienelemente an. [S3]

### 4.4 Platznutzung

**VIS-03 — Breite richtet sich nach der Aufgabe.** Der Wochenplan nutzt die verfügbare Breite. Ein einzelnes Formular wird dagegen nicht über 1600 Pixel auseinandergezogen.

| Oberfläche | Layoutvorgabe |
|---|---|
| Navigation auf grossen Displays | Etwa 224 Pixel breit; sichtbare Wörter, keine reine Iconleiste. |
| Wochenplan | Fluid, bis etwa 1680 Pixel Arbeitsbreite innerhalb des Bereichs rechts der Navigation. |
| Listen/Verwaltung | Fluid, bis etwa 1440 Pixel. |
| Normale Editorseite | Formularinhalt etwa 760–960 Pixel; Prüfbereich daneben, wenn genügend Platz. |
| Seitliches Bearbeitungsfenster | Etwa 560–640 Pixel breit, auf kleinen Displays vollflächig. |
| Seitenabstand | Desktop 24–32 Pixel, Tablet 20–24, Smartphone 16. |

Die Arbeitsfläche wird innerhalb des Bereichs neben der Navigation positioniert, nicht durch einen starren Offset in der gesamten Browserbreite zentriert. Auf kleineren Geräten wird die Navigation über einen sichtbar beschrifteten „Menü“-Button geöffnet; sie darf nicht den Plan auf eine unbrauchbare Restbreite drücken.

**VIS-04 — Weniger Container, klare Ebenen.** Eine Seitenüberschrift benötigt keine eigene Karte. Innerhalb eines Formulars werden Abschnitte mit Überschrift und Abstand getrennt. Eine Menükarte ist ein eigenständiges Objekt; eine Karte um jede einzelne Formulareigenschaft ist unnötig.

---

## 5. Wochenplan als zentrale Arbeitsfläche

### 5.1 Aufbau von oben nach unten

**WEEK-01 — Feste Reihenfolge:** Bereich und Zeitraum → Wochenaktionen/Status → Planungsfläche → optionale Wochenangaben. Vor der ersten Menüreihe dürfen keine langen Hilfetexte, Standardzeitenformulare oder mehrfachen Statuskarten stehen.

Beispiel für die Anordnung, nicht für neue Backendzustände:

```text
Menüplanung

[Cafeteria]  [Patienten]

7.–11. September 2026                                  Kalenderwoche 37
[Vorherige Woche]  [Woche auswählen]  [Nächste Woche]

Noch nicht veröffentlicht · 2 Angaben sind noch zu prüfen
[Vorschau]  [Weitere Aktionen]                    [Offene Angaben prüfen]

             Montag      Dienstag    Mittwoch    Donnerstag    Freitag
             7.9.        8.9.        9.9.        10.9.          11.9.
Menü 1       Menükarte   Menükarte   Menükarte   Menükarte      Menükarte
Vegetarisch  Menükarte   Menükarte   Menükarte   Menükarte      Menükarte

[Wochenangaben ändern]
```

**WEEK-02 — Datum vor Kalenderwoche.** Ein verständlicher Datumsbereich ist die Hauptorientierung. Die KW ist Zusatzinformation. Ein frei eingegebener Wochentitel darf das tatsächliche Plandatum nicht ersetzen. Bei vorhandenen widersprüchlichen Titeln wird die Inkonsistenz sichtbar gemacht, nicht stillschweigend in der Datenbank korrigiert.

### 5.2 Raster und responsive Darstellung

**WEEK-03 — Cafeteria:** Bei ausreichender realer Arbeitsbreite, Richtwert etwa 1160 Pixel, fünf Tagesspalten und zwei Menüzeilen. Tagesspalten bleiben ungefähr 200 Pixel oder breiter. Wird es enger, wechselt die Darstellung zu chronologischen Tagesabschnitten mit zwei Menükarten nebeneinander; auf schmalen Smartphones stehen diese untereinander.

Die Mindestbreite wird mit realen Menünamen geprüft. Weder Schriftverkleinerung noch abgeschnittene Namen noch horizontales Scrollen der ganzen Seite dürfen einen ungeeigneten Rastermodus retten. Auf Desktop und Mobil bleibt die logische Lesereihenfolge nachvollziehbar; Tag und Menüart sind für Tastatur-/Screenreaderbedienung pro Eintrag bestimmbar.

**WEEK-04 — Patienten:** Alle sieben Tage bleiben erreichbar. Mittag und Abend sind eindeutig getrennt. Standard ist eine lesbare chronologische Tagesdarstellung; sieben schmale Spalten sind kein Pflichtlayout. Eine vorhandene oder rein darstellungsseitig mögliche Mahlzeitenfilterung kann „Alle Mahlzeiten“, „Mittag“ und „Abend“ anbieten. Die Voreinstellung darf den Abendplan nicht unbemerkt verschwinden lassen.

Cafeteria und Patienten verwenden gemeinsame Gestaltungsmuster, aber nicht zwangsweise dasselbe Raster. Unterschiedliche Tages-/Mahlzeitenumfänge werden nicht zugunsten einer hübschen Fünf-Tage-Demo beschnitten.

### 5.3 Inhalt einer Menükarte

| Reihenfolge | Inhalt |
|---|---|
| 1 | Menüart, beispielsweise „Menü 1“ oder vorhandene vegetarische Kategorie. |
| 2 | Gut lesbarer, vollständiger Menüname. |
| 3 | Beilagen/Bausteine in kurzer, lesbarer Zusammenfassung. |
| 4 | Ein konkreter Prüfstatus, etwa „Allergene noch prüfen“, soweit der Bestand diese Ursache liefert. |
| 5 | Cafeteriapreise mit eindeutigen Zielgruppen, sofern im Plan sinnvoll darstellbar. |
| 6 | Sichtbare Aktion „Bearbeiten“; eine grössere klickbare Fläche darf ergänzen. |

**WEEK-05 — Kein Informationsverlust für optische Gleichheit.** Karten dürfen wachsen. Wesentliche Namen, Datumsangaben, Preise und Warnungen werden nicht mit einer festen Höhe abgeschnitten. Lange interne Details gehören in den Editor; notwendige Hinweise bleiben zugänglich. Verschachtelte klickbare Elemente sind zu vermeiden; ein klarer Link/Button ist die robuste Basis.

Ein leerer Slot zeigt „Noch kein Menü“ und „Menü hinzufügen“, sofern die bestehende Erstellung für diesen Slot zulässig ist. Ein geschlossener Tag zeigt „Geschlossen“ statt leerer roter Fehlerkarten. Ein technischer Ladefehler sieht nicht wie eine leere Woche aus.

### 5.4 Wochenaktionen

**WEEK-06 — Eine gemeinsame Wochensteuerung statt verteilter Duplikate.** „Wochenangaben prüfen“ steht nicht gleichzeitig im Header und nochmals darunter. „Vorwoche kopieren“, Vorlagen und seltene Aktionen liegen unter dem beschrifteten „Weitere Aktionen“.

| Tatsächliche Situation | Darstellung | Nächster Schritt |
|---|---|---|
| Noch offene Pflicht-/Prüfangaben | „2 Angaben sind noch zu prüfen“, sofern die Zahl vollständig vorliegt. | „Offene Angaben prüfen“. |
| Bestehende Publikationsprüfung erlaubt Veröffentlichung | „Bereit zur Veröffentlichung“. | „Veröffentlichen“. |
| Plan bereits veröffentlicht | „Veröffentlicht“; Zeitpunkt nur bei vorhandenen Daten. | Vorschau bzw. vorhandene weitere Bearbeitung. |
| Keine Berechtigung zum Veröffentlichen | Sachlicher Hinweis, keine ausführbare Publikationsaktion. | Nur vorhandene erlaubte Funktionen. |
| Prüfung/Status konnte nicht geladen werden | „Status konnte nicht geladen werden“. | Erneut laden; nicht grün oder „0 offen“. |

„Bereit zur Veröffentlichung“ ist eine Darstellung vorhandener Prüfergebnisse, kein neuer gespeicherter Status. Ist der Bestand dafür nicht aussagekräftig genug, bleibt die vorhandene Statusbezeichnung mit besserer Erklärung bestehen.

Eine fixierte Aktionsleiste ist zulässig, darf aber keine Felder oder den Tastaturfokus verdecken. Auf kleinen oder niedrigen Viewports kann sie in den normalen Dokumentfluss wechseln. [S5]

### 5.5 Tages- und Wochenangaben

**WEEK-07 — Standardwerte zuerst lesen, Abweichungen gezielt bearbeiten.** Pro Tag werden vorhandene Öffnungszeiten und ein möglicher Hinweis kurz angezeigt. „Tagesangaben ändern“ öffnet die bestehenden Felder für Betrieb/Öffnungszeit/Hinweis. Kein Benutzer muss für jeden normal geöffneten Tag dieselben Felder erneut durcharbeiten.

„Standardzeiten ergänzen“ ist eine ausdrückliche Aktion und verwendet ausschliesslich die vorhandene Funktion. Vor dem Ausführen muss ihre tatsächliche Wirkung verständlich sein. Keine automatische Änderung beim Öffnen der Woche und kein Versprechen „Vorhandene Werte bleiben erhalten“, bevor dies am Code geprüft wurde.

Wochenhinweis und Zusatztitel werden unter „Wochenangaben ändern“ bearbeitet. Speichert dieses Formular unabhängig vom Menüeditor, bleibt es unabhängig. Ein neuer globaler „Alles speichern“-Button ist ohne entsprechende bestehende Transaktion verboten.

**WEEK-08 — Kopieren ist nie blind.** Vor einer vorhandenen Kopieraktion sind Quellwoche, Zielwoche und bekannte Auswirkungen sichtbar. Überschreiben, Ergänzen oder Mitkopieren von Preisen/Prüfständen darf nicht erfunden werden. Ein Bestätigungsdialog benennt die tatsächliche Wirkung; er bietet nur vom Backend unterstützte Optionen.

---

## 6. Menü bearbeiten, ohne die Orientierung zu verlieren

### 6.1 Seitliches Bearbeitungsfenster und vollständige Editorseite

**EDIT-01 — Zielinteraktion:** Auf grossen Bildschirmen öffnet „Bearbeiten“ ein seitliches Bearbeitungsfenster. Die Woche bleibt sichtbar, ist während modaler Bearbeitung aber nicht bedienbar. Auf Smartphone wird derselbe Bearbeitungskontext vollflächig angezeigt. Die normale Editor-URL bleibt verwendbar.

Tabler dokumentiert dafür eine Offcanvas-Komponente. Ob die installierte Version und der bestehende Formularkontext diese Erweiterung ohne Vertragsänderung erlauben, wird in der Bestandsaufnahme geprüft. Die Dokumentation ist kein Nachweis für eine bereits eingebaute Projektfunktion. [S1]

Kann eine saubere Panelintegration nur durch neue Backendverträge erreicht werden, bleibt die neu gestaltete vollständige Editorseite der vorläufige Standard. Der Panelteil wird ausdrücklich als blockiert gemeldet, nicht durch eine zweite ungeprüfte Speicherlogik nachgebaut.

### 6.2 Festes Bearbeitungsmuster

```text
Montag, 7. September · Mittag · Menü 1
Menü bearbeiten                         [Zurück zum Wochenplan]

Menüname
[Pouletbrust an Kräutersauce                                  ]

Bausteine
Kartoffelstock                    [Nach oben] [Nach unten] [Entfernen]
Zucchetti                         [Nach oben] [Nach unten] [Entfernen]
[Baustein hinzufügen]

Beschreibung / Hinweis
Nur die im Bestand vorhandenen Felder mit erklärtem Anzeigezweck.

Allergene, Herkunft und Kennzeichnungen
Noch zu prüfen: Allergene wurden noch nicht erfasst.
[Angaben bearbeiten]

Preise — nur Cafeteria
Mitarbeitende [11.00] CHF          Externe [16.60] CHF

Änderungen noch nicht gespeichert
[Abbrechen]                                      [Menü speichern]
```

**EDIT-02 — Kontext bleibt sichtbar.** Datum, Mahlzeit und Menüart stehen im Titel oder direkt darunter. Der Benutzer muss nicht aus dem Menütext erraten, welchen Tag er gerade verändert.

**EDIT-03 — Ein primärer Speicherbutton.** „Menü speichern“ ist eindeutig. Die bisherige Konkurrenz aus „Speichern“, „Speichern und zurück“, „Abbrechen“ und „Prüfung öffnen“ wird auf klare Aktionen reduziert. Die genaue Rückkehr nach dem Speichern verwendet das bestehende Verhalten bzw. erhält den Kontext darstellungsseitig, ohne neue Redirect-Verträge einzuführen.

Bei Erfolg wird der betroffene Eintrag aktualisiert bzw. nach dem bestehenden Redirect wieder angezeigt. Woche, Bereich und nach Möglichkeit Scroll-/Fokusposition bleiben erhalten. Ein Fehler schliesst den Editor nicht und verwirft die Eingaben nicht.

### 6.3 Schutz vor verlorenen Eingaben

**EDIT-04 — Ungespeicherte Änderungen sind sichtbar.** Nach einer Eingabe steht „Änderungen noch nicht gespeichert“. „Gespeichert“ erscheint erst nach einer bestätigten erfolgreichen Antwort. Ein globaler Speicherzustand darf nicht aus einem einzelnen erfolgreich gespeicherten Formular abgeleitet werden.

Bei Schliessen, Bereichswechsel oder interner Navigation mit Änderungen erfolgt eine verständliche Rückfrage: „Du hast Änderungen noch nicht gespeichert.“ Aktionen: „Weiter bearbeiten“ und „Änderungen verwerfen“. Die sichere Standardaktion ist „Weiter bearbeiten“. Eine Browserwarnung beim Verlassen kann ergänzen, ist aber keine garantierte Absicherung gegen Absturz oder Tab-Schliessen.

Keine Menüinhalte oder klinikbezogenen Formulardaten werden für diese Iteration ungefragt in Local Storage, Drittanbieter-Tracking oder neue Offline-Speicher geschrieben.

### 6.4 Komponenten/Bausteine

**EDIT-05 — Eine Zeile pro Baustein statt eines Formularblocks pro Baustein.** Die Reihenfolge ist sichtbar. Hinzufügen, Entfernen und Umsortieren funktionieren ohne Ziehen.

| Situation | Verhalten |
|---|---|
| Baustein aus vorhandenem Katalog | Auswahl über vorhandene Suche/Auswahlkomponente; nur vorhandene Datensätze anbieten. |
| Eigener Text | Deutlich gewählte Eingabeart „Eigener Text“, sofern der Bestand das unterstützt. |
| Beide Eingabearten vorhanden | Eindeutige Auswahl der Eingabeart; keine zwei scheinbar gleichzeitigen Quellen. Bestehende Formularsemantik beibehalten. |
| Sortieren | Beschriftete Aktionen „Nach oben“ / „Nach unten“; an den Grenzen sinnvoll deaktiviert. |
| Entfernen aus einem noch ungespeicherten Menü | Zeile entfernen; persistiert erst durch die tatsächliche vorhandene Speicheraktion. |
| Zentralen Baustein löschen/archivieren | Getrennte Handlung mit tatsächlichem Geltungsbereich; nicht mit „aus diesem Menü entfernen“ verwechseln. |

**EDIT-06 — Ziehen ist höchstens eine Ergänzung.** Kein neues Drag-and-Drop-Paket. Eine alternative Bedienung ohne Ziehbewegung bleibt vorhanden; W3C beschreibt dies ausdrücklich als Anforderung für entsprechende Zeigerinteraktionen. [S4]

Ein neuer zentraler Baustein wird nur über eine bereits vorhandene, berechtigte Erstellung angelegt. Kein zweites Modal über dem Editor. Fehlt eine einfache Inline-Erstellung, bleibt der vorhandene Weg mit Schutz ungespeicherter Änderungen erhalten.

### 6.5 Geltungsbereich jeder Änderung

**EDIT-07 — Der Benutzer erkennt, was er verändert.** Bei einem geplanten Menü darf nicht unbemerkt ein globaler Katalogeintrag geändert werden. Umgekehrt darf eine zentrale Änderung nicht als Änderung nur dieses Menüs beschriftet sein.

Ein Hinweis wie „Wird in 4 Menüs verwendet“ erscheint nur mit einer verlässlichen vorhandenen Zahl. Ob eine Bausteinänderung bestehende Pläne beeinflusst oder nur künftige Auswahlen, wird anhand des Bestands beschrieben. Keine unbelegte Zusicherung „Vergangene Pläne bleiben unverändert“.

---

## 7. Allergene, Herkunft, Prüfung und Veröffentlichung

### 7.1 Unbedingte Schutzregeln

**SAFE-01 — Fehlende Daten sind keine bestätigte Freiheit von Allergenen.** „Nicht erfasst“, „enthält“, „kann enthalten“ und eine ausdrücklich bestätigte Abwesenheit bleiben fachlich unterscheidbar. Eine leere Allergenliste darf weder einen grünen Haken noch „Allergenfrei“ erzeugen.

**SAFE-02 — Keine automatische Wahrheit aus Menünamen.** Titel, Freitexte oder vermutete Rezepturen sind keine neue Allergen-/Herkunftsquelle. Die UI führt keine KI-Erkennung, neue Ableitung oder neue Aggregationslogik ein. Bereits vorhandene geprüfte Daten dürfen angezeigt werden; Quellen nur, wenn das System sie tatsächlich kennt.

**SAFE-03 — Hinweise sind nicht Bestätigungen.** Ein Text wie „Bei Kräutersauce Milch prüfen“ bleibt ein Prüfhinweis. Er wird nicht in eine bestätigte Deklaration umgewandelt. Hinweise dürfen verständlicher gegliedert, aber nicht fachlich umgedeutet werden.

Die genaue lebensmittelrechtliche oder medizinische Bewertung ist nicht Gegenstand dieses UI-Konzepts. Vorhandene fachliche Prüf- und Publikationsregeln bleiben massgeblich; ein im Bestand erkannter fachlicher Fehler wird separat gemeldet und nicht verdeckt.

### 7.2 Verständliche Prüfung

**STATE-01 — Zwei Dinge getrennt darstellen:** den Veröffentlichungsstand und den Stand der fachlichen Prüfung. „Veröffentlicht“ bedeutet nicht automatisch „alle neuen Änderungen geprüft“. „Geprüft“ bedeutet nicht automatisch „öffentlich sichtbar“.

Die erklärende Orientierung „1. Planen → 2. Prüfen → 3. Veröffentlichen“ ist zulässig. Sie ist kein Auftrag für einen neuen serverseitigen Zustandsautomaten oder eine neue Freigaberolle.

| Datenlage | Verständlicher Text | Aktion |
|---|---|---|
| Allergene nicht erfasst | „Die Allergene sind noch nicht erfasst.“ | „Allergene bearbeiten“. |
| Vorhandene Prüfung noch offen | „Diese Angaben müssen noch geprüft werden.“ | Bestehende Prüfung öffnen. |
| Ungespeicherte Änderungen | „Speichere zuerst deine Änderungen. Danach kannst du die gespeicherten Angaben prüfen.“ | „Menü speichern“. |
| Tatsächlich bestätigte Prüfung | „Angaben geprüft“. Name/Zeit nur, falls verfügbar. | Bestehende Detailansicht. |
| Bestehende Validierung meldet einen Fehler | Konkreter Feldname und verständliche Korrekturanweisung. | Direkt zum betreffenden Feld. |

**STATE-02 — Prüfung bezieht sich auf den richtigen Datenstand.** Eine vorhandene Prüfung des zuletzt gespeicherten Menüs darf nicht so wirken, als bestätige sie ungespeicherte Eingaben. Speichern und Prüfen bleiben getrennte vorhandene Operationen; kein neues kombiniertes „Speichern und bestätigen“ ohne ausdrückliche bestehende Unterstützung.

**STATE-03 — Keine neue Sperrlogik im Browser erfinden.** Bestehende serverseitige Publikationshindernisse werden klar erklärt und bleiben wirksam. Fehlende oder unklare Validierung im Backend ist ein Befund, keine Einladung zu einer nur optischen Frontendsperre. Ein nicht erfüllbarer sicherer Prüfablauf wird als blockiert eskaliert.

### 7.3 Veröffentlichung

**STATE-04 — Veröffentlichen bleibt bewusst.** Vor dem bestehenden schreibenden Vorgang werden Bereich, Zeitraum und tatsächliche Wirkung benannt. Beispiel: „Cafeteriaplan für 7.–11. September veröffentlichen?“ Der Text nennt nur Ausgabeziele, die der Bestand tatsächlich bedient.

Erfolgsrückmeldung erst nach Bestätigung: „Der Cafeteriaplan wurde veröffentlicht.“ Ein fehlgeschlagener oder unklar beantworteter Request darf keinen Erfolgszustand auslösen. Bei Netzwerkabbruch während einer Schreiboperation lautet die Meldung sinngemäss „Der Abschluss konnte nicht bestätigt werden. Lade den aktuellen Stand, bevor du die Aktion erneut ausführst.“ Kein blindes automatisches Wiederholen potenziell nicht idempotenter Aktionen.

Ein bereits veröffentlichter Plan mit Änderungen wird ausschliesslich nach den bestehenden Versionierungs-/Publikationsregeln dargestellt. Das UI darf keine neue Entwurfsebene erfinden oder behaupten, eine öffentliche Ausgabe sei noch unverändert, wenn dies nicht nachgewiesen ist.

---

## 8. Menüs, Bausteine und Zutaten verwalten

### 8.1 Standardansicht

**LIST-01 — Suche zuerst.** Seitenkopf mit Titel und einer Hauptaktion, darunter Suchfeld und höchstens zwei Standardfilter. Weitere Filter liegen hinter „Weitere Filter“, mit Anzahl aktiver zusätzlicher Filter.

```text
Bausteine                                          [Baustein hinzufügen]

[Bausteine suchen …                     ] [Suchen]
[Kategorie] [Status] [Weitere Filter · 2 aktiv]
Aktiv: Kategorie Gemüse · Enthält Milch             [Filter zurücksetzen]

Name              Kategorie     Angaben                Verwendung     Status
Broccoli          Gemüse        bestehende Angaben     4 Menüs        Aktiv
Kartoffelstock    Beilage        bestehende Angaben     2 Menüs        Aktiv
```

„Enthält Milch“ im Beispiel bezeichnet einen gesetzten Filter, keine Aussage über eine beliebige Zutat. Produktdaten und Treffer werden ausschliesslich aus dem Bestand angezeigt.

**LIST-02 — Bestehende Suchsemantik bleibt erhalten.** Kein neuer Suchdienst, keine neue clientseitige Vollsuche über unvollständig geladene Daten. Suche per Enter und sichtbarem Button verwenden die vorhandenen Parameter. Filter kombinieren sich wie bisher; aktive Filter bleiben erkennbar. Versteckte aktive Filter dürfen keine unerklärlich leere Liste erzeugen.

### 8.2 Tabellen und Detailbearbeitung

Der Name ist ein eindeutig fokussierbarer Link. Eine klickbare Zeile darf ergänzen, darf aber nicht die einzige Bedienmöglichkeit sein. Ein winziger Bleistift allein ist unzureichend. Auf Smartphone werden nur weniger wichtige Spalten in eine zugängliche Detaildarstellung verschoben; relevante Angaben werden nicht gelöscht.

Bei Herkunft sollen verständliche Ländernamen statt alleiniger Flaggen oder Ländercodes stehen, soweit eine vorhandene Zuordnung verfügbar ist. Kennzeichnungen wie „Vegan“, „Glutenfrei“ oder „Laktosefrei“ erscheinen nur nach bestehender Datenlage, nicht als aus dem Namen abgeleitete Dekoration.

### 8.3 Leer-, Fehler- und Ladezustände

**LIST-03 — Jede Situation bekommt einen passenden Text.**

| Zustand | Text | Handlung |
|---|---|---|
| Noch keine Datensätze | „Es sind noch keine Bausteine angelegt.“ | „Baustein hinzufügen“, sofern erlaubt. |
| Filter ohne Treffer | „Keine Bausteine passen zu deiner Suche.“ | „Filter zurücksetzen“. |
| Kein Zugriff | „Du hast für diesen Bereich keine Berechtigung.“ | Vorhandene erlaubte Navigation. |
| Laden fehlgeschlagen | „Die Bausteine konnten nicht geladen werden.“ | „Erneut laden“. |
| Archivierter Eintrag | „Archiviert“ mit Erklärung der vorhandenen Nutzbarkeit. | Nur bestehende erlaubte Aktionen. |

Keine Pagination bei einer tatsächlich leeren Liste oder nur einer Seite, sofern dadurch keine vorhandene Funktion verloren geht. Ladeplatzhalter dürfen nur bei echtem asynchronem Laden erscheinen, nicht als künstliche Animation vor einer bereits gerenderten Tabelle.

---

## 9. Erscheinungsbild, Vorschau und Ausgaben

### 9.1 Erscheinungsbild bearbeiten

**BRAND-01 — Bestehende Designversionierung bleibt erhalten, aber wird verständlich präsentiert.**

| Bisher sichtbarer Schwerpunkt | Ziel |
|---|---|
| Revision 1 / Revision aktivieren | Aktuelles Design / Entwurf / Entwurf aktivieren. |
| Technischer Verlauf sofort sichtbar | „Frühere Versionen“ als nachgeordneter Bereich. |
| Hexwerte ohne visuelle Orientierung | Farbfeld plus weiterhin erreichbarer exakter Wert; bestehende Validierung. |
| Unklare gespeicherte Vorschau | Deutliche Beschriftung des tatsächlich gezeigten Standes. |

Auf grossen Screens stehen Einstellungen und Vorschau nebeneinander, auf kleinen untereinander. Logo, Farben und Schrift sind klar gegliedert. Die Vorschau verwendet typische, realistisch lange Menütexte und berücksichtigt Cafeteria/Patienten, soweit die vorhandene Vorschaufunktion diese Kontexte bereits unterstützt.

**BRAND-02 — „Live-Vorschau“ nur bei wirklicher Live-Aktualisierung.** Zeigt der Bestand erst den gespeicherten Entwurf, heisst die Aktion „Entwurf speichern und Vorschau anzeigen“. Eine reine Browservorschau muss als ungespeichert erkennbar bleiben. Aktivierung ist ein eigener bestehender Vorgang mit klarer Wirkung; Speicher- und Aktivierungslogik werden nicht umgebaut.

### 9.2 Admin, öffentliche Website und Bildschirme trennen

**OUT-01 — Gemeinsame Marke, unterschiedliche Bedienflächen.** Admin-Navigation, Prüfnotizen, Bearbeiten-Buttons und interne Kontoinformationen gehören nicht in öffentliche oder Signage-Ausgaben. Admin-Styles werden so begrenzt, dass bestehende Ausgaben nicht unabsichtlich verändert werden.

| Ausgabe | Erhaltungs-/Gestaltungsregel |
|---|---|
| Admin/Küche | Tabler, klare Bedienaktionen, Prüfstatus und vorhandene Verwaltungsfunktionen. |
| Website/Smartphone | Lesbare Menüs für die jeweilige Zielgruppe, keine Adminnavigation. |
| Patientenansicht | Sieben Tage, Mittag/Abend, keine Preise. |
| Cafeteriaansicht | Vorhandene beiden Preisgruppen und Menüarten korrekt zugeordnet. |
| Signage Tag | Vorhandene eigenständige Anzeige, keine interaktive Adminoberfläche. |
| Signage Woche | Falls vorhanden: vollständiger vorgesehener Wocheninhalt im bestehenden Ausgabemodus. Fehlt dieser Modus, Lücke dokumentieren statt neue Infrastruktur entwickeln. |

**OUT-02 — Keine vorgetäuschte Vorschautreue.** Vorschau benennt Zielgruppe, Zeitraum, Ausgabemodus und Entwurf/veröffentlichten Stand, soweit verfügbar. Eine generische Beispielkarte ist keine nachgewiesene Vorschau des tatsächlichen Bildschirms.

**OUT-03 — Bestehende Ausgabeverträge bleiben stabil.** Player-URLs, API-Verträge, Cache-/Aktivierungsregeln und publizierte Datenstände werden nicht für diese UI-Iteration geändert. Eine UI-Änderung darf keine technischen Agenten- oder Prüfhinweise neu öffentlich machen. Ist die heutige Sichtbarkeit eines Hinweisfelds unklar, wird sie vor einer Umbenennung ermittelt.

Bei vorhandenen 16:9-Ausgaben erfolgt ein eigener Sichttest mit 1920 × 1080 und 1280 × 720. Keine abgeschnittenen Pflichtinformationen, keine scrollende Adminseite als Bildschirmansicht. Falls das vorhandene Layout den Inhalt nicht darstellen kann, bleibt dieser Abnahmepunkt offen; die Schrift wird nicht beliebig verkleinert.

---

## 10. Zugänglichkeit und Fehlertoleranz

**A11Y-01 — Kernabläufe funktionieren mit Tastatur, Maus und Touch.** Fokus ist deutlich sichtbar; alle sichtbaren Aktionen sind erreichbar und verständlich benannt. Browserzoom wird nicht deaktiviert. Hover ist nie der einzige Weg zu einer Information.

**A11Y-02 — Kontrast.** Normale Texte erreichen mindestens 4,5:1. Für grosse Texte und notwendige nichttextliche UI-Kennzeichnungen werden die jeweils anwendbaren Anforderungen geprüft; erforderliche Komponenten-/Zustandskontraste liegen grundsätzlich bei 3:1 gegen angrenzende Farben. Farbe allein übermittelt nie Status oder Fehler. [S6, S8]

**A11Y-03 — Responsives Umfliessen.** Bei 320 CSS-Pixel Breite bleibt der normale Bedienablauf ohne horizontales Seitenscrollen nutzbar. Bei 200 % Zoom bleiben Beschriftungen und Aktionen vollständig erreichbar; zusätzlich Reflow entsprechend 320 CSS-Pixel prüfen. Ein Wochenraster darf dafür in Tagesabschnitte wechseln. [S7]

**A11Y-04 — Beschriftete Felder und verständliche Fehler.** Jedes Feld hat eine sichtbare zugeordnete Beschriftung; ein Platzhalter ersetzt kein Label. Fehler erscheinen am betroffenen Feld und bei mehreren Fehlern zusätzlich in einer fokussierbaren Zusammenfassung. Sie beschreiben, was zu korrigieren ist. Eingaben bleiben erhalten. [S9]

**A11Y-05 — Modales Bearbeitungsfenster.** Beim Öffnen wird der Fokus sinnvoll gesetzt und bleibt im offenen Dialog. Der Hintergrund ist nicht bedienbar. Beim Schliessen kehrt der Fokus zum auslösenden Eintrag zurück. Der Dialog hat einen zugänglichen Titel, eine sichtbare Schliessen-/Zurück-Aktion und eine Escape-Behandlung, die den Schutz ungespeicherter Änderungen respektiert. Keine verschachtelten Modaldialoge. [S10]

**A11Y-06 — Sticky-Leisten verdecken nichts.** Das aktive Feld und der sichtbare Fokus bleiben erreichbar. Tastatureinblendung auf Smartphone, geringe Fensterhöhe und Zoom sind ausdrücklich zu testen. [S5]

Erfolgsmeldungen werden zusätzlich zum optischen Status für assistive Technologien geeignet angekündigt. Fehler und Hinweise verschwinden nicht nach zwei Sekunden. Animationen sind kurz, sachlich und bei reduzierter Bewegung abschaltbar. Keine Animation darf das Erfassen oder Prüfen verzögern.

**Wichtig:** Die genannten Kriterien sind eine verbindliche Prüfauswahl für dieses Projekt. Ihre Umsetzung allein ist keine vollständige WCAG-Konformitätsprüfung oder Zertifizierung.

### 10.1 Weitere Fehlerfälle

| Fall | Vorgabe |
|---|---|
| Doppelklick auf Speichern | Unbeabsichtigte Mehrfachauslösung im laufenden UI-Vorgang verhindern; bestehende Serverregeln bleiben erforderlich. |
| Servervalidierung schlägt fehl | Werte erhalten, konkrete Meldungen, Editor bleibt im Bearbeitungskontext. |
| Session abgelaufen | Kein falscher Erfolg. Vorhandenen Anmeldeweg verwenden und Datenverlustgrenze klar benennen. |
| Netzwerkantwort nach Speichern fehlt | Abschluss als unklar melden; nicht automatisch erneut schreiben. |
| Zwei Personen bearbeiten gleichzeitig | Vorhandene Konflikterkennung erhalten. Fehlt sie, als bestehendes Risiko dokumentieren; keine neue Sperrinfrastruktur erfinden. |
| Sehr langer Menüname | Umbruch und dynamische Höhe; kein Überdecken von Status/Buttons. |
| Leere Herkunft/Allergene | „Nicht erfasst“ statt leerer grüner Kennzeichnung. |
| Wechsel Cafeteria → Patienten | Titel, Inhalt und Preisfelder wechseln konsistent; kein Restzustand aus dem anderen Bereich. |

---

## 11. Umsetzung mit dem bestehenden Unterbau

### 11.1 Vorgehen

**IMPL-01 — Bestand vor Neuerfindung.** Wiederverwendbare Darstellungsbausteine werden innerhalb der existierenden Struktur gebildet. Die folgenden Namen beschreiben Verantwortlichkeiten, keine verbindlich behaupteten Dateipfade:

| Baustein | Verantwortung |
|---|---|
| Admin-Seitenrahmen | Navigation, Seitenabstände, Titelbereich, responsive Navigation. |
| Wochensteuerung | Zeitraum, Bereich, bestehende Statusdaten, Wochenaktionen. |
| Menükarte | Gleiche Reihenfolge von Name, Bausteinen, Preisen und Status. |
| Menüformular | Dieselben Felder/Verträge auf Editorseite und gegebenenfalls im Panel. |
| Prüfzusammenfassung | Bestehende Prüfbefunde verständlich und einheitlich anzeigen. |
| Such-/Filterleiste | Suche, Hauptfilter, erweiterte Filter und aktive Filter. |
| Leer-/Fehlerzustand | Einheitliche Texte und tatsächlich passende Aktionen. |
| Design-Tokens | Gemeinsame Typografie, Abstände, Farben und interaktive Zustände. |

Tabler stellt entsprechende Layout-, Formular- und UI-Komponenten bereit. Es werden die im Projekt installierten Möglichkeiten genutzt; Beispiele aus neuerer Dokumentation rechtfertigen kein zusätzliches Paket oder Versionsupgrade. [S1]

### 11.2 Verträge explizit sichern

**IMPL-02 — Für jeden angefassten Schreibablauf vorab dokumentieren:** vorhandene Route, HTTP-Methode, Feldnamen, CSRF-Verfahren, Rollenprüfung, Validierungsantwort, Erfolgsantwort/Redirect sowie tatsächlicher fachlicher Effekt. Testfälle verwenden diese bestehenden Verträge.

Neue zusätzliche Anzeige-IDs, Klassen oder zugängliche Beschriftungen sind erlaubt. Eine Umbenennung sichtbarer Wörter ist keine Erlaubnis, `name`-Attribute, serverseitige Enumwerte oder Formulardaten zu verändern.

**IMPL-03 — Ein Formular, keine konkurrierenden Implementierungen.** Vollständige Editorseite und Panel verwenden dieselben wiederverwendeten Felddefinitionen/Partials und den gleichen vorhandenen Schreibweg. Kein eigenständiger clientseitiger Allergen-, Preis- oder Freigabealgorithmus.

### 11.3 Änderungsgrösse und Zusammenarbeit

**IMPL-04 — Kleine, prüfbare Arbeitspakete.** Ein Paket hat klar benannte Dateien, Anforderungen und Tests. Die Basisgestaltung wird zuerst stabilisiert. Mehrere Agenten dürfen keine widersprüchlichen globalen Styles oder denselben Seitenrahmen gleichzeitig umbauen.

Die Integration prüft insbesondere globale CSS-Auswirkungen, doppelte IDs, mehrfach geladene Assets, veränderte Feldnamen und verlorene bestehende Funktionen. Ein bestandener Einzeltest des Editors reicht nicht für die Freigabe der gesamten Anwendung.

---

## 12. Arbeitspakete und Freigabepunkte

| Paket | Inhalt | Voraussetzungen | Konkretes Ergebnis |
|---|---|---|---|
| **WP-00 Bestand & Baseline** | Templates, Abhängigkeiten, Routen/Formulare, Rollen, Zustände, Ausgabegrenzen erfassen; vorhandene Tests ausführen. | Keine. | Tatsächliche Dateiliste, Vertragsmatrix, Baseline-Ergebnisse, offene Fragen. Noch kein Redesign. |
| **WP-01 Gemeinsame Gestaltung** | Tokens, Typografie, Buttons, Felder, Hinweise, Seitenbreiten und responsive Navigation. | WP-00. | Gemeinsame Basis ohne Framework-/Assetwechsel; Vergleichsscreenshots. |
| **WP-02 Navigation** | Vier Einstiege, konsistente Begriffe, vollständige Zuordnung aller bisherigen Funktionen. | WP-01. | Erreichbarkeit und Berechtigungen unverändert; keine verlorenen Einstiege. |
| **WP-03 Wochenplan** | Cafeteriaraster, responsive Tagesdarstellung, Patientenstruktur, Wochensteuerung, optionale Tagesangaben. | WP-01/02. | End-to-End lesbare Planung mit echten Daten; korrekte Bereiche/Zeiträume. |
| **WP-04 Menüeditor** | Formular vereinfachen, Bausteinzeilen, Speicherschutz, gleiche Editorseite/Panel-Felder. | WP-03 und bestätigte Formularverträge. | Bearbeiten/Speichern/Fehler/Rückkehr vollständig; Panelteil bei technischer Grenze ausdrücklich blockiert. |
| **WP-05 Prüfung & Veröffentlichung** | Klartext, direkte Fehlerwege, getrennter Prüf-/Publikationsstand, bestätigte Erfolgsanzeigen. | WP-04 und belegte Backendregeln. | Kein Umgehen oder Neuerfinden von Fachlogik; richtige gespeicherte Version. |
| **WP-06 Menüs & Stammdaten** | Such-/Filterleiste, Tabellen, Leerzustände, verständlicher Änderungsgeltungsbereich. | WP-01/02. | Weniger sichtbare Komplexität bei gleichen Such-/Schreibverträgen. |
| **WP-07 Design & Ausgabeprüfung** | Erscheinungsbild vereinfachen; Vorschaukennzeichnung; bestehende öffentliche/Signage-Ausgaben regressionsprüfen. | WP-01 und bekannte Ausgabegrenzen. | Keine Admin-CSS-Nebenwirkungen; Preis-/Zielgruppentrennung korrekt. |
| **WP-08 Gesamtprüfung** | Zugänglichkeit, Geräte, Fehlerfälle, vollständige Regression und Test mit unerfahrenen Personen. | Alle nicht blockierten Pakete. | Abnahmebericht mit Nachweisen; offene Pflichtpunkte klar benannt. |

**GATE-01:** Ohne WP-00 kein Eingriff in Formulare, Zustände oder öffentliche Ausgabe.  
**GATE-02:** Ohne bestätigte Designbasis kein seitenweise unterschiedliches Styling.  
**GATE-03:** Ohne Vertrags-/Regressionstest kein Merge eines Schreibablaufs.  
**GATE-04:** Ohne ehrlichen Abschlussbericht keine Fertigmeldung.

Unabhängige Seitenpakete dürfen nach Freigabe der gemeinsamen Basis parallel bearbeitet werden, sofern ihre Dateiverantwortung klar getrennt ist. Der Integrationsverantwortliche koordiniert Änderungen an gemeinsamen Partials und Styles.

---

## 13. Verbindliche Abnahmetests

Die Tests sind mit vorhandenen Testmitteln und einer isolierten Testumgebung durchzuführen. Keine Testveröffentlichung produktiver Klinikpläne. Testdaten enthalten keine personenbezogenen Patientendaten.

### 13.1 Funktion und Verständlichkeit

| ID | Test | Bestanden, wenn … |
|---|---|---|
| T01 | Hauptnavigation vergleichen | Alle bisherigen Funktionen einem neuen Einstieg zugeordnet und mit unveränderten Rechten erreichbar sind. |
| T02 | Woche wechseln | Datum, KW, Tage und Inhalte zusammenpassen; kein alter Freititel als falscher Zeitraum erscheint. |
| T03 | Cafeteria-Woche am grossen Bildschirm | Fünf Tage und zwei Menüarten lesbar, korrekt zugeordnet und ohne riesige Verwaltungsblöcke erscheinen. |
| T04 | Patientenplan | Montag bis Sonntag sowie Mittag und Abend vollständig erreichbar sind; keine Preise erscheinen. |
| T05 | Menü öffnen und zurückkehren | Datum/Mahlzeit/Menüart eindeutig sind und derselbe Wochenkontext erhalten bleibt. |
| T06 | Menü erfolgreich speichern | Tatsächlicher vorhandener Schreibweg genutzt und Erfolg erst nach bestätigter Antwort angezeigt wird. |
| T07 | Ungespeichert schliessen | Interne Navigation nicht still verwirft; „Weiter bearbeiten“ die Eingaben erhält. |
| T08 | Validierungsfehler | Werte erhalten bleiben, der Fehler zum Feld führt und keine falsche Erfolgsmeldung erscheint. |
| T09 | Baustein aus Liste / eigener Text | Genau die gewählte bestehende Eingabeart gespeichert wird; keine unbemerkte andere Quelle greift. |
| T10 | Bausteine sortieren | Reihenfolge ohne Drag-and-Drop geändert und nach Speichern korrekt wiedergegeben wird. |
| T11 | Allergenangaben fehlen | „Nicht erfasst“ sichtbar ist; kein „Allergenfrei“ oder grüner Prüfstatus entsteht. |
| T12 | Prüfen vor Speichern | Eine Prüfung des alten Standes nicht als Bestätigung neuer ungespeicherter Werte dargestellt wird. |
| T13 | Veröffentlichung gesperrt | Bestehender Serverblock weiter wirkt und sein Grund verständlich sichtbar ist. |
| T14 | Veröffentlichen erfolgreich | Richtiger Bereich/Zeitraum betroffen ist und bestehende Ausgabe unverändert korrekt funktioniert. |
| T15 | Kopieraktion | Quell-/Zielwoche und tatsächliche Wirkung stimmen; nichts Unbelegtes über Überschreiben behauptet wird. |
| T16 | Suche und Zusatzfilter | Bestehende Suchsemantik gilt, aktive Filter sichtbar bleiben und Zurücksetzen funktioniert. |
| T17 | Leere Liste / kein Treffer / Ladefehler | Drei unterscheidbare Zustände mit passenden Aktionen angezeigt werden. |
| T18 | Design speichern/aktivieren | Entwurf, angezeigte Vorschau und aktives Design entsprechend der bestehenden Logik unterschieden werden. |
| T19 | Rollenprüfung | Nicht erlaubte Vorgänge weiterhin serverseitig abgelehnt werden; Navigation keine Berechtigung ersetzt. |
| T20 | JavaScript deaktiviert oder Panel fehlt | Vorhandene vollständige Editor-/Formularwege weiterhin korrekt nutzbar sind. |

### 13.2 Gestaltung, Geräte und Fehlerfälle

| ID | Test | Bestanden, wenn … |
|---|---|---|
| T21 | 1920 × 1080 | Wochenplan nutzt den Arbeitsplatz sinnvoll; keine schmale Insel in grosser Leerfläche. |
| T22 | 1366 × 768 | Navigation/Planmodus passen sich an; Texte und Hauptaktionen bleiben lesbar. |
| T23 | 1024 × 768 und 768 × 1024 | Tagesdarstellung und Touchbedienung funktionieren; keine unbedienbar schmale Restfläche. |
| T24 | 390 × 844 und 320 CSS-Pixel Breite | Kein horizontales Seitenscrollen im Kernablauf; Editor/Buttons bleiben vollständig nutzbar. |
| T25 | 200 % Zoom / Reflow | Texte und Aktionen nicht verdeckt werden; bei schmalem Layout sinnvolle Umordnung statt Schrumpfen. |
| T26 | Tastatur komplett | Woche, Editor, Bausteine, Prüfung und Navigation ohne Maus bedienbar sind; Fokus sichtbar bleibt. |
| T27 | Modaler Editor | Fokusführung, Hintergrundsperre, Rückkehr und Schliessen mit Eingabeschutz funktionieren. |
| T28 | Kontrast und Status | Tatsächliche Farbkombinationen gemessen sind; kein Status nur durch Farbe vermittelt wird. |
| T29 | Lange Texte / fehlende Werte | Keine wesentlichen Informationen abgeschnitten, überlagert oder falsch als vollständig dargestellt werden. |
| T30 | Fehlende/unklare Speicherantwort | Keine automatische Wiederholung unsicherer Schreibaktionen und kein falscher Erfolg auftreten. |
| T31 | Öffentliche Ausgaben | Keine Admincontrols/Prüfnotizen neu sichtbar werden; korrekte Zielgruppen und Preise erhalten bleiben. |
| T32 | Vorhandenes Signage in 1080p/720p | Vorgesehene Inhalte im bestehenden Ausgabemodus vollständig ohne Adminnavigation dargestellt werden. |
| T33 | Konsistenz über fünf Ausgangsseiten | Gleiche Abstände, Schriftgrössen, Buttons, Fehler-/Leerzustände und Seitenrahmen verwendet werden. |
| T34 | Technischer Diff | Keine ungefragten Abhängigkeiten, Migrationen, geänderten Verträge oder Sicherheitsabschwächungen enthalten sind. |

Ein Test erhält genau einen Status: **bestanden**, **fehlgeschlagen**, **blockiert** oder **nicht anwendbar mit Begründung**. „Nicht getestet“ ist kein Erfolg. Nicht verfügbare Browser-/Testwerkzeuge werden ausdrücklich angegeben; Agenten erfinden weder Testergebnisse noch Screenshots.

### 13.3 Nutzertest ohne Schulungsvortrag

**QA-01 — Mindestens drei Personen mit geringer technischer Erfahrung testen die Kernaufgaben.** Wenn diese Personen noch nicht verfügbar sind, bleibt die Nutzerabnahme offen; ein Agent darf diesen Test nicht selbst ersetzen.

Nach einer kurzen Kontextangabe erhalten die Testpersonen nacheinander diese Aufgaben:

| Aufgabe | Beobachtetes Erfolgskriterium |
|---|---|
| „Ändere beim Menü vom Dienstag die Beilage und speichere.“ | Richtiger Tag und Eintrag, tatsächliches Speichern, keine Hilfe zur Navigation. |
| „Finde heraus, warum diese Woche noch nicht veröffentlicht werden kann.“ | Konkretes Hindernis wird gefunden und in eigenen Worten erklärt. |
| „Zeige den Patientenplan für Sonntagabend.“ | Kein falscher Bereich, keine Verwechslung mit Cafeteria oder Mittag. |
| „Suche einen Baustein und entferne danach alle Filter.“ | Suche und Zurücksetzen werden selbstständig gefunden. |
| „Bereite diesen fertigen Testplan zur Veröffentlichung vor.“ | Unterschied zwischen Speichern, Prüfen, Vorschau und Veröffentlichen verstanden. |

Projektziel: Jede Kernaufgabe wird von mindestens zwei der drei Personen ohne navigierende Hilfestellung abgeschlossen. Kritische Fehlhandlungen wie falscher Zielbereich, irrtümliches Veröffentlichen oder das Verstehen fehlender Allergene als bestätigte Allergenfreiheit verhindern die Abnahme auch bei ansonsten guter Quote. Suchzeiten, Fehlklicks und Rückfragen werden protokolliert; Optimierungen erfolgen anhand dieser Beobachtungen, nicht anhand behaupteter Zufriedenheit.

---

## 14. Definition of Done und Übergabe

**DONE-01 — Fertig bedeutet mehr als „sieht moderner aus“.** Ein Paket ist erst abnahmefähig, wenn seine zugeordneten Muss-Anforderungen erfüllt, bestehende Funktionen erhalten und Tests nachvollziehbar dokumentiert sind.

| Pflichtnachweis | Inhalt |
|---|---|
| Änderungsübersicht | Tatsächlich geänderte Dateien und umgesetzte Anforderungs-IDs. |
| Bestands-/Vertragsnachweis | Erhaltene URLs, Formulardaten und Schreib-/Prüfsemantik für angefasste Abläufe. |
| Testprotokoll | Ausgeführte Befehle bzw. manuelle Schritte und echte Ergebnisse. |
| Sichtprüfung | Vorher/nachher bei relevanten Grössen; zusätzlich leer, Fehler, lange Inhalte und offene Prüfung. |
| Technischer Diff-Check | Keine Stack-, Datenmodell-, API-, Berechtigungs- oder Deploymentänderung. |
| Offene Punkte | Blockierte Anforderungen mit konkretem Grund, ohne beschönigende Fertigmeldung. |
| Nutzerabnahme | Ergebnisse von QA-01 oder ausdrücklicher Status „noch ausstehend“. |

**Automatische Ablehnung im Review:** reine Farb-/Card-Kosmetik bei unverändert überladenem Ablauf; neuer Frameworkunterbau; versteckte entfernte Funktionen; falsches Autosave; vorgetäuschte Live-Vorschau; automatisch bestätigte Allergene; Drag-and-Drop als einzige Bedienung; unlesbar zusammengedrückter Patientenplan; neue Preisangaben in Patientenausgaben; erfolglose Tests als bestanden gemeldet.

### 14.1 Abschlussformat für Agenten

Jeder Abschluss nennt: Arbeitspaket, erfüllte Anforderungen, geänderte Dateien, erhaltene Verträge, tatsächlich ausgeführte Prüfungen, Screenshotnachweise und offene/blockierte Punkte. Eine pauschale Aussage „alles funktioniert“ ersetzt keinen dieser Nachweise.

### 14.2 Entscheidungsregel bei Zielkonflikten

Die Reihenfolge lautet: **korrekte Daten und Sicherheit → unveränderter technischer Unterbau → verständliche Bedienung → konsistente Gestaltung → zusätzliche Komforteffekte.**

Eine technische Grenze rechtfertigt eine dokumentierte reduzierte Komfortfunktion, aber keine erfundene Funktion. Eine schöne Oberfläche rechtfertigt weder fehlende Menüs noch versteckte Pflichtangaben. Ein bestehender Unterbau rechtfertigt umgekehrt nicht, verständliche Beschriftungen, lesbare Schrift oder klare Navigation aufzuschieben.

---

## 15. Referenzen

### 15.1 Bereitgestellte Ausgangsscreenshots

| Referenz | Datei | Inhalt |
|---|---|---|
| E1 | [01-wochenplan.png](../ist/frueher/E1-wochenplan.png) | Cafeteria-Wochenplan mit Tagesangaben und Menükarten. |
| E2 | [02-menueeditor.png](../ist/frueher/E2-menueeditor.png) | Menüeditor mit Preisen, Komponenten und Prüfung. |
| E3 | [03-komponenten.png](../ist/frueher/E3-komponentenliste.png) | Umfangreiche Filter und Komponentenliste. |
| E4 | [04-grundlagen.png](../ist/frueher/E4-grundlagen.png) | Zutaten-/Grundlagenbereich mit leerem Zustand. |
| E5 | [05-erscheinungsbild.png](../ist/frueher/E5-erscheinungsbild.png) | Designentwurf, Vorschau und Revisionsverlauf. |

### 15.2 Technische und Zugänglichkeitsreferenzen

Offizielle Quellen, am 7. September 2026 abgerufen. Die konkreten Layoutmasse, Farben, Navigation und Arbeitsabläufe in diesem Konzept sind projektspezifische Festlegungen; sie werden nicht als Vorgaben der Hersteller ausgegeben.

| ID | Quelle | Wofür sie herangezogen wird |
|---|---|---|
| S1 | [Tabler: UI-Komponenten](https://docs.tabler.io/ui/components/) und [Offcanvas](https://docs.tabler.io/ui/components/offcanvas/) | Bestehende Komponenten statt neuem UI-Framework. |
| S2 | [Flask: Templates](https://flask.palletsprojects.com/en/stable/templating/) | Jinja-Integration und Autoescaping erhalten. |
| S3 | [W3C: Target Size (Minimum), 2.5.8](https://www.w3.org/WAI/WCAG22/Understanding/target-size-minimum.html) | Unterscheidung Normminimum und grösserer Projekt-Klickflächen. |
| S4 | [W3C: Dragging Movements, 2.5.7](https://www.w3.org/WAI/WCAG22/Understanding/dragging-movements.html) | Alternative ohne Ziehbewegung. |
| S5 | [W3C: Focus Not Obscured, 2.4.11](https://www.w3.org/WAI/WCAG22/Understanding/focus-not-obscured-minimum.html) | Fokus nicht durch fixierte Bereiche verdecken. |
| S6 | [W3C: Contrast (Minimum), 1.4.3](https://www.w3.org/WAI/WCAG22/Understanding/contrast-minimum.html) | Textkontrast. |
| S7 | [W3C: Reflow, 1.4.10](https://www.w3.org/WAI/WCAG22/Understanding/reflow.html) | Nutzung bei schmalen Viewports und Zoom. |
| S8 | [W3C: Non-text Contrast, 1.4.11](https://www.w3.org/WAI/WCAG22/Understanding/non-text-contrast.html) | Erkennbare Bedienelemente und Zustände. |
| S9 | [W3C: Error Identification, 3.3.1](https://www.w3.org/WAI/WCAG22/Understanding/error-identification.html) | Fehler am Feld und verständliche Korrekturmöglichkeiten. |
| S10 | [W3C ARIA APG: Modal Dialog Pattern](https://www.w3.org/WAI/ARIA/apg/patterns/dialog-modal/) | Fokusführung und Verhalten des modalen Bearbeitungsfensters. |

**Ende der verbindlichen Zielvorgabe.**
