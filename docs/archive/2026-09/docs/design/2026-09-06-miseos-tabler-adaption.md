# UI-003: MiseOS-Referenz in Dishboard übertragen

Status: visuell geprüft und für die nächste UI-Welle vorbereitet; noch keine Umsetzung oder Abnahme. Die laufende Branding-/Legendenlieferung hat Vorrang. Das Gesamtziel und die übrigen Backlog-IDs bleiben offen.

## Geprüfte Referenz

Am 06.09.2026 wurden der [Corral-Abschlussbericht](https://corral.dk/posts/final-thoughts/) sowie die Originalbilder für [Vorschlagsliste](https://corral.dk/img/blog/dish-suggestions.png), [Detailansicht](https://corral.dk/img/blog/dish-suggestions-detail.png), [Menüauswahl](https://corral.dk/img/blog/dish-select.png) und [Mitarbeitendenansicht](https://corral.dk/img/blog/chef-suggestion.png) tatsächlich geöffnet und visuell geprüft.

Beobachtet: ruhige helle Flächen, dünne Trennlinien, klar gegliederte Navigation, Status-Pills, kurze Metadatenlabels über Werten sowie getrennte Haupt- und Nebenaktionen. Listen bündeln Statusfilter und Suche; Auswahlkarten verbinden Titel, Beschreibung, letzte Verwendung und eine direkte Aktion. Die gezeigten Bilder sind Desktopansichten; sie belegen keine mobile Bedienbarkeit oder Barrierefreiheit.

Die folgenden Entscheidungen sind eine Übertragung auf Dishboard. Fremde Logos, Texte, Stylesheets oder Komponenten werden nicht kopiert. Der lokale Abruf über `rag-web scrape` endete zweimal mit Exit 4 ohne Ausgabe; die Referenz wurde anschliessend direkt über HTTPS geprüft.

## Konkrete Übertragung

| Bereich | Änderung mit vorhandenen Tabler-Mitteln | Prüfkriterium |
|---|---|---|
| Formular | Sichtbares `form-label` unmittelbar vor dem zugehörigen Feld; Hilfe und Fehler über `aria-describedby`. Fachgruppen mit kurzen Überschriften und konsistenten Abständen. | Label-Fokus funktioniert; Pflichtfeld, Fehler und gespeicherter Zustand auch ohne Farbe verständlich. |
| Liste | Gemeinsame Werkzeugleiste für vorhandene Suche/Filter; klarer Titel mit nachgeordneten Metadaten, ruhige Zeilentrennung und benannte Status-Badges. | Keine neuen Filter ohne Datenvertrag; vorhandene URL-Filter, leere Ergebnisse und Zurücksetzen funktionieren. |
| Menükarten | Titel, Bestandteile, Deklarationen und Aktionen in wiederkehrender Reihenfolge; Nebeninformationen optisch nachordnen. | Alle gleichartigen Karten pro Ansicht gleich gross; vollständige Pflichtangaben bleiben lesbar. |
| Aktionen | Eine erkennbare Hauptaktion; Nebenaktionen als bestehende Tabler-Varianten. Kritische Aktionen räumlich klar zugeordnet. | Tastaturfokus sichtbar, Aktionsnamen eindeutig, bestehende 48-px-Touchziele eingehalten. |
| Farben und Schrift | Ausschliesslich bestehende Tabler-Utilities und zentrale Dishboard-/Branding-Tokens verwenden. | Statusfarben behalten Bedeutung; keine harten Seitenfarben und keine neue Schrift-Dependency. |

Kompakte Dichte bleibt Standard. Die grosszügigen Desktopabstände und kleinen blassen Referenzlabels werden nicht ungeprüft übernommen. Platzhalter ersetzen keine Feldlabels. Allergen-, Herkunfts- und Prüfhinweise werden weder gekürzt noch in unzugängliche Hover-Inhalte verschoben.

## Kleine Ausführungsfolge

1. Nach Integration der Markenbasis drei repräsentative bestehende Seiten auswählen: Menüformular, Menüsammlung/Liste und Admin-Wochenkarten. Vorherbilder mit unveränderten Testdaten aufnehmen.
2. Je ein kleiner Commit für Formularhierarchie, Listenwerkzeugleiste und Kartenhierarchie. Vor Dispatch genaue Dateieigentümer festlegen; gemeinsame Tokens höchstens eine Lane pro Welle. Keine neue Rendering-Schicht oder Abhängigkeit.
3. Nachherbilder bei 390, 820 und 1440 px mit identischen Daten vergleichen; kompakte und komfortable Dichte, lange Inhalte, Fehlerzustand sowie leere Liste prüfen. Bestehende Suche, Speichern, Tastaturbedienung, 48-px-Ziele, Kontrast und gleiche Kartengrössen nachweisen.
4. Root liest Diffs und wiederholt passende Browser-/Regressionsgates. UI-003 bleibt bis zum tatsächlich geprüften Deploy offen.

Deterministisch erzeugtes Vergleichspaket: `wp-70b31a459235`. Der Router ordnete es `browser` / `playwright-chromium-headless` zu; dies ist eine Prüffähigkeit, kein Code-Writer. Die späteren drei Write-Pakete benötigen eigene Dateiverträge und isolierte Worktrees. Aktuell wurde keine zusätzliche Ausführungslane gestartet.
