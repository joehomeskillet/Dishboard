# Vollständige SDD- und WP-Planung

Stand: 9. September 2026, Europe/Zurich. Dieser Plan führt alle 35 IDs aus
[BACKLOG.md](../../BACKLOG.md) zusammen. Er ergänzt deren Sollumfang und ersetzt
ältere Aussagen über Ausführungsreihenfolge, ausschliessliche Agentenzuständigkeit
und damaligen Lieferstatus. Historische Belege bleiben historische Belege.

Nutzerauftrag: vollständigen Backlog vorplanen, anschliessend durch Codex,
Grok-Build, Claude Code und weitere geeignete verfügbare Lanes abarbeiten lassen.
Alle erhalten denselben Arbeitsvertrag. Die gewünschte Nutzung verfügbarer
Kontingente ist kein Auftrag, bezahlte Ersatzanbieter zuzuschalten oder unnötige
Arbeit zu erzeugen. Eine erschöpfte Lane hält unabhängige Pakete nicht an.

## Einstieg

Für jede Frontend-Änderung zuerst das vollständige
[konsolidierte Designsystem](../../design/2026-09-09-unified-ui-design-system.md) lesen.
Es konkretisiert UI-003 für alle vorhandenen Routen und Zustände; die ältere
seitenbezogene Gestaltung ist keine Grenze der Migration.

1. [START.md](START.md): gemeinsamer Startauftrag und konkrete CLI-Einstiege.
2. [Ausführungsvertrag](execution-contract.md): Eigentum, Status, Gates, Übergabe.
3. [Rezepte und Grundlagen](recipes-sdd.md), [zugehörige WPs](recipes-wps.json).
4. [Warenfluss und Fachwissen](operations-sdd.md), [zugehörige WPs](operations-wps.json).
5. [Oberfläche, Zugriff und Abnahme](surfaces-sdd.md), [zugehörige WPs](surfaces-wps.json).
6. [Routingbelege und Dateibesitz](EXECUTION-READY.md): vollständiger Zuordnungs-
   und Leaseindex mit geschützten laufenden Aufgaben und möglichen Startkandidaten.

Die drei JSON-Dateien bilden gemeinsam den Abhängigkeitsgraphen. `MP-*` bezeichnet
eine stabile fachliche Paket-ID; `wp-*` bezeichnet den separat erzeugten
Routingauftrag. Ein neues CLI oder Modell erzeugt keine neue Fachanforderung.

## Gemeinsames SDD

### Ein Datenbestand

Menüs, Rezeptrevisionen, Lebensmittel, Einheiten und Lagerorte werden durch
echte standortgebundene Identitäten verknüpft. Zutaten sind Lebensmittel; ein
vorbereitetes Lebensmittel kann eine konkrete unveränderliche Rezeptrevision
referenzieren. Diese Verbindung erhält die damals gültige Ausbeute und Einheiten.
Alle Mengen verwenden dieselben Stammdaten aus `/admin/grundlagen` und dieselbe
Decimal-Umrechnung. Keine zweite Einheitenliste, keine versteckte Portion-zu-Gramm-
Annahme und keine Verknüpfung allein über ähnlich geschriebene Namen.

Jedes Lebensmittel erhält mindestens einen Lagerort. Eine Lagerzuordnung bedeutet
keinen erfassten Bestand. Erst das separate Inventurjournal liefert Bestände,
Chargen und Bewegungen. Planänderungen buchen keine Ware ab. Vorbereitete Rezepte
dürfen später als chargierte Lebensmittel verwendet werden; Haltbarkeitsdaten
werden nicht aus Rezeptnamen geraten.

Entwürfe dürfen unvollständig bleiben. Neue eingefrorene Rezepte benötigen
Lebensmittel, positive Mengen und gültige Einheiten in jeder Zutatenzeile.
Historische Revisionen und publizierte Menüs bleiben unverändert. Quellen,
Importentscheidungen, Mengenannahmen und fachlicher Prüfstatus bleiben sichtbar.

### Ein Schreibvertrag

Jeder Schreibpfad prüft ursprünglichen Akteur, Berechtigungsversion, Standort und
Objektversion. Ein zusammengehöriger Vorgang schreibt atomar; echte Änderung
bedeutet höchstens den fachlich festgelegten Versionsschritt und einen abgeleiteten
Auditvorgang. Stammdaten bewahren ihren ausdrücklich definierten No-op-Vertrag.
Bestehende Menü-Speicher- und Prüfaktionen behalten die vertraglich erforderliche
Versionsfortschreibung zur Entwertung alter Freigaben; die UI-Migration ändert
diese Semantik nicht. Vorschau und Bestätigung beziehen sich auf denselben serverseitig
signierten Ausgangszustand. Ein Konflikt erneuert diese Signatur nicht heimlich.

SQL-Verträge, Schema-Versionen, gemeinsame Registrierungen und verbundene DTOs
haben pro Ausführungswelle einen Besitzer. Eine Migration wird erst nach
Vorgänger-Freeze nummeriert. Rückfall bedeutet nachgewiesene Kompatibilität zum
geschriebenen Datenstand; ein altes Image allein ist kein Rückfallplan.

### Eine Oberfläche

Admin bleibt Tabler mit vorhandenen Komponenten, Symbolen und Tokens. Neue
Bibliotheken sind gesonderte Entscheidungen nach nachgewiesener Eignung. Public
und Signage verwenden die gewünschte minimalistische weisse Gestaltung.
Patientenausgaben bleiben ohne Preise. Produktansichten zeigen keine technischen
Arbeitsdetails. Tastatur, Fehlerfokus, mobile Breite und verständliche Konflikte
gehören zur Abnahme jedes betroffenen Formulars.

### Ein Liefernachweis

Geplant, implementiert, unabhängig geprüft, integriert, ausgeliefert und fachlich
abgenommen sind verschiedene Aussagen. Jeder Status braucht seinen eigenen
Beleg. Testanzahl und Screenshots allein beweisen weder vollständige SDD-Erfüllung
noch Küchen-, Lizenz-, Entra- oder physische Yodeck-Abnahme.

## Verifizierter Ausgangspunkt

Planungsquellstand: `e813806b51fb5efaef5d5755c292f8027ce1b2eb`, lokal integriert,
Schema 26. Letzter belegter Produktivstand: `5f5f6cb535922db8453c68d871279d6b2e203391`,
Schema 25. Rezepteditor und weisse Public Screens sind seit 8. September,
21:46 Uhr Schweiz live; Zugriffsverlauf seit 22:34 Uhr. Bei jedem Start den
aktuellen Releasebeleg prüfen, diese Momentaufnahme nicht als Dauerzustand nutzen.

Der Rezept-PDF-Editor ist seit 9. September, 01:25 Uhr Schweiz ausgeliefert.
Vollständiges Paketgate: 5810 bestanden, 18 übersprungen; frische Backups und
Live-Readiness geprüft. Root hat den authentifizierten Vorlagen-Reader zusätzlich
am 9. September um etwa02:23 Uhr Schweiz mit einer Anmeldung geprüft:106 Checks,
vier Seitenzustände und acht maskierte Screenshots, keine fachliche Schreibaktion.
Ohne gespeicherte Produktionsrezepte ist ein tatsächlicher Rezept-PDF-Download
dort weiterhin nicht belegt; synthetische PDF-Gates bleiben separat.
Der Workflow-Consumer ab6cd9f ist mit215 Root-Tests und unabhängigem Grok-Review
geprüft. Schema27 hat58 Root-PG16-Tests bestanden. Grundlagen4d5074e besteht
114 Root-DB-/HTTP- und35 Root-Browserprüfungen sowie unabhängigen Review12446.
Gemeinsame Integration, v2-Reader/Freeze und Schema27-Release bleiben offen.

Erfasster Datenentwurf: 32 echte Gerichtstitel mit allen 76 Quellvorkommen,
37 Menükomponenten, 29 Vorbereitungsrezepte und 100 Lebensmittel; zusammen
61 Rezepte. Vorhandene neun Einheiten werden wiederverwendet. Mengen und drei
Lagerorte sind bearbeitbare Vorschläge, alle Rezepte fachlich ungeprüft.
Der Entwurf ist noch nicht importiert. Die vier Quellwochen sind bereits
publiziert und werden beim Import nicht rückwirkend umgeschrieben.

## Ausführung in Wellen

- Laufende Pakete bis zum Freeze fertigstellen; keine konkurrierende Neuerstellung.
- Danach verknüpfte Grundlagen, unveränderliche Rezeptauflösung und Importvertrag
  gemeinsam integrieren. Parallel unabhängige Recherche, Vorschauparser, Glossar-
  und UI-Abnahmeaufgaben ausführen, wenn ihre konkreten Dateien frei sind.
- Rezeptplanung und Einkaufsbedarf bauen auf geprüften Rezepten und Mengen auf.
  Kosten und Lagerjournal folgen den gemeinsamen Lebensmittel-/Einheitenverträgen.
- Bestellvorschläge verbinden Bedarf, Bestand und Lieferanten. Verbindliches
  Absenden bleibt eine ausdrückliche Benutzeraktion.
- Freie Editoren und externe Adapter erhalten eigene Eignungs-/Formatpakete.
  Fehlende lizenzierte Daten oder Playerzugriff blockieren nur abhängige Pakete.
- Nach jeder grünen Integrationswelle einen überprüften Release liefern und
  tatsächlichen Live-Stand aktualisieren. Fachliche Restabnahmen bleiben sichtbar.

Die konkrete Freigabe ergibt sich aus dem Graphen und aktuellem Dateibesitz,
nicht allein aus dieser Reihenfolge. Zwei nominell unabhängige WPs mit derselben
Vertrags- oder Registrierungsdatei werden serialisiert.

Der kombinierte Strukturcheck umfasst136 Pakete und alle35 Anforderungen;
43 Rezepte/Grundlagen,37 Warenfluss/Fachwissen und56 Oberfläche/Abnahme,
darin31 UI-Migrationspakete. Null Fehler. Die53 Hinweise zu leeren
`contract_files` betreffen Pakete ohne ausgewiesenen eigenen gemeinsamen
Vertragswrite; ihre `owned_files` bleiben für Dateileases vollständig verbindlich.
Struktur-PASS ist keine Produktabnahme. Das Public-Politur-Paket kann auf dem
bestehenden ausgelieferten Vertrag beginnen, ohne auf Schema27 oder zusätzliche
Screenvarianten zu warten.
