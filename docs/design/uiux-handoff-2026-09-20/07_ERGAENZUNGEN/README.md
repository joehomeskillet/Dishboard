# Ergänzungen des Auftraggebers vom 2026-09-20

Zusätzlich zum Handoff (Ordner `01`–`06`) hat der Auftraggeber am selben Tag zwei Ergänzungsprompts und drei
Beispielbilder geliefert. Die Prompts liegen unverändert in diesem Ordner:

- `Ergaenzungsprompt_Kompakte_Formulare.md` — Option + Detail erst nach Auswahl, 2–3 Spalten, keine langen
  zweispaltigen Wiederholungslisten; Beispiel Allergene; global nach demselben Anti-Pattern suchen.
- `Ergaenzungsprompt_Globale_UI_Vereinfachung.md` — das ganze Admin-Frontend Seite für Seite und Zustand für Zustand
  vereinfachen; Phasen Audit → gemeinsame Komponenten → Module → Detailseiten/Sonderzustände → Regression;
  Entscheidungsregel und Informationshierarchie.

Die drei Beispielbilder lagen nur im Auftragsgespräch vor, nicht als Datei. Damit jede ausführende Stelle dieselbe
Grundlage hat, sind sie unten beschrieben. Sie sind ausdrücklich als **Beispiel** betitelt: Sie zeigen Denkweise und
Komposition, keine Datenquelle und keinen Funktionsumfang.

## Bild 1 — «Vereinfachtes, einheitliches Interface (List + Edit)»

Liste «Menüs» links, kompakte Detailansicht rechts daneben.

- Liste: eine Filterzeile (Suche, Kategorie, Status, «Filter zurücksetzen», Umschalter Liste/Raster); je Datensatz
  **eine** Zeile mit Bild, Name + einzeiliger Unterzeile, Kategorie-Badge, Tag/Datum, Status-Badge
  (Aktiv/Inaktiv/Entwurf), Allergen-Icons und drei gleichartigen Zeilenaktionen (Bearbeiten, Duplizieren, Mehr).
  Fusszeile «8 von 8 Menüs» und Seitenwahl.
- Detail: Titel + Status-Badge, lokale Abschnitte (Allgemein, Zutaten, Zubereitung, Kennzeichnungen, Lager,
  Kalkulation), nur die wichtigsten Felder sichtbar, «Weitere Optionen» eingeklappt, unten einheitlich
  «Löschen» links, «Abbrechen» und «Speichern» rechts.
- Beschriftete Aussagen im Bild: einheitliche Suche & Filter in allen Modulen; kompakte Detailansicht für alle Module
  gleich; klare Listenstruktur; einheitliche Statusbadges; nur die wichtigsten Felder sichtbar; einheitliche
  Aktionsbuttons.

## Bild 2 — «Allergene bei einem Menü – vorher und nachher»

- Vorher (heutiger Zustand, als «unübersichtlich» markiert): 14 Zeilen, je Auswahlfeld + Allergenname + wiederholtes
  Label «Präsenz für …» + dauerhaft sichtbares Auswahlfeld «enthält»; darunter drei gleichgewichtige Schaltflächen.
- Nachher: 14 kompakte Auswahl-Chips mit Icon und Text in vier Spalten, ausgewählte deutlich hervorgehoben
  (Rahmen + Haken, nicht nur Farbe); «Details (optional)» eingeklappt — dort nur für **ausgewählte** Allergene eine
  abweichende Angabe; Standard «enthält»; unten «Abbrechen» und eine Primäraktion «Speichern».

## Bild 3 — «Einheitliches, vereinfachtes Design – Beispiele für alle Menüs»

Neun Miniaturen (Menüs-Liste, Menü bearbeiten, Allergene, Zutaten, Zubereitung, Kochbücher, Einkaufsliste,
Bestellungen, Lager) mit demselben Aufbau: Titel, eine Primäraktion rechts oben, eine Filterzeile, kompakte
Tabellenzeilen mit Status-Badge und «…»-Zeilenmenü.

## Einordnung durch die Umsetzung (verbindlich für diese Welle)

Übernommen werden die **Muster**: eine Filterzeile, eine Zeile pro Datensatz, einheitliche Status-Badges,
einheitliche Zeilenaktionen, Auswahl-Chips mit Detail erst nach Auswahl, «Weitere Optionen» eingeklappt, ein
einheitlicher Formularfuss, 2–3 Spalten auf grossen und eine Spalte auf kleinen Bildschirmen.

Nicht übernommen wird, was den ausdrücklichen Regeln des Handoffs widerspricht oder neue Fachfunktion wäre:

| Im Beispielbild | Entscheidung | Grund |
|---|---|---|
| Horizontale Modul-Tabs über der Liste und alle Module flach in der Sidebar (Bild 1) | nicht übernehmen | SDD «nicht verhandelbar»: keine horizontale Modul-Untermenüleiste; Unterpunkte nur eingerückt in der Sidebar bei aktivem Oberpunkt |
| Globale Suche mit Tastenkürzel, Benachrichtigungsglocke, Hilfe, Datumsnavigation in einer Kopfleiste | nicht Teil der Welle | neue Fachfunktionen; Handoff verlangt «keine neue Businesslogik» |
| «Löschen» im Formularfuss | nur wo die Funktion heute existiert (sonst Archivieren/Reaktivieren) | keine neue Fachfunktion |
| Schritt-Assistent «1. Basisdaten … 6. Vorschau», Timer/Bild je Zubereitungsschritt, Raster-Ansicht, Duplizieren | nur wo heute vorhanden | keine neue Fachfunktion |
| «Alle als ‹nicht enthalten› setzen» und stiller Standardwert (Bild 2) | nur mit unveränderter Speichersemantik | Eine nicht ausgewählte oder ungeprüfte Angabe darf nie als «allergenfrei» gespeichert oder angezeigt werden; Prüfstatus der Allergendeklaration wird durch die Oberfläche nicht verändert |
| Beispielwerte (Gerichte, Daten, Lieferanten, Bestände) | keine Datenquelle | Mockup-Inhalte |
