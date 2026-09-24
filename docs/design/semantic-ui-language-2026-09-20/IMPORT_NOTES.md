# Importhinweise zum Paket «Semantic UI Language» (2026-09-20)

Die zwölf Dateien dieses Ordners stammen aus dem gelieferten Paket `dishboard_icon_pack`.
P2c ergänzt am 2026-09-24 die drei Aktionen Aktivieren, Übernehmen und Verlauf
in JSON/CSV und DE-/EN-Texten. Alle verwenden vorhandene Sprite-Icons; keine
Vendor-/Fallback-Änderung. Runtime-Registry: 205→208; Designquelle: 184→187.
Laut
`00_START_HERE.md` bleiben das bestehende Designmanifest und die SDDs die übergeordnete Spezifikation; dieses Paket
ist ein Delta für **Icons, Beschriftungen, Status-Vokabular und Mehrsprachigkeit** und hat bei widersprüchlichen
Icon-/Label-Regeln Vorrang.

## Was das Paket verlangt (Kurzfassung)

- Ein Modell: `semantic_key → Icon → Label-Key → Tooltip-Key → Aria-Key → erlaubte Darstellung → Rolle`.
  187 Bedeutungen in 15 Kategorien (`05_SEMANTIC_REGISTRY.csv`/`.json`), je drei Texte in `locale_de.json` und
  `locale_en.json` (561 Schlüssel; vor P2c 552).
- Keine festen UI-Texte in Templates ausser Dateninhalten; stabile Schlüssel; keine aus Fragmenten gebauten Sätze;
  Labels dürfen ~40 % wachsen; fehlende Übersetzungen müssen in der Entwicklung sichtbar sein.
- Kanonische Verben: Anlegen, Hinzufügen, Bearbeiten, Öffnen, Speichern, Bestätigen, Löschen, Archivieren, Kopieren,
  Vorschau, Aktivieren, Übernehmen, Verlauf — keine Synonyme je Modul.
- Darstellungsstufen: Icon-only nur für wiederholte, risikoarme, allgemein verständliche Aktionen (immer Tooltip +
  `aria-label`); Icon + Kurzlabel als Standard; Icon + Label + Hilfetext für destruktive, seltene,
  sicherheitsrelevante Aktionen.
- Feste Symbolreihenfolge auf Menü-/Mahlzeitkarten: `[Kostform] [Allergene] [Eigenschaften] [Prüf-/Status]`.
- Zentrale Bausteine: Icon, IconButton, IconLabel, StatusBadge, SymbolRow, DietIcon, AllergenIcon, ActionMenu,
  StatusBar, FilterBar, EmptyState, ConfirmDialog.

## Abgleich mit dem Projekt (vom Import geprüft)

| Thema | Befund | Folge |
|---|---|---|
| Icon-Verfügbarkeit | Das lokal ausgelieferte Tabler-Sprite (`static/vendor/tabler-icons/tabler-icons.svg`) enthält 35 Icons; von 143 in der Registry genannten fehlen **118**. | Wie in `07_REGISTRY_GUIDE.md` vorgesehen: zentrales Mapping auf das nächstpassende vorhandene Icon — nie lokal im Template. Das Erweitern des Sprites ist ein eigener, kontrollierter Schritt (Herkunft/Lizenz in `SOURCES.md`, Icon-Manifest `docs/design/2026-09-07-admin-tabler-icon-manifest.md`). |
| Allergen-Icons | Projekt besitzt eigene geprüfte Allergen-SVGs (`static/vendor/food-symbols/`). | Bleiben massgeblich; Registry-Kategorie `allergen` verweist darauf statt auf Tabler-Icons. |
| Verb «Öffnen» | Bisherige Wellen-Regel nutzte «Ansehen» für reines Lesen. | Das Paket hat Vorrang: «Öffnen» = ansehen ohne Bearbeiten; «Bearbeiten» = ändern. |
| Bedienziele | Paket nennt ~44×44 px. | Im Projekt bleibt der strengere, getestete Wert von 48 px. |
| Allergen-Editor | Wireframe zeigt die Detailauswahl als eigene Liste unter den Chips. | Umsetzung bleibt das Muster M21 der Designquelle (Detail direkt an der gewählten Option): Allergen und Präsenz werden als indexgepaarte Felder gesendet; das Detailfeld wird deaktiviert statt versteckt und steht im selben Container. Die Regel «keine deaktivierten Detailfelder ZEIGEN» ist erfüllt, weil nicht gewählte Optionen kein sichtbares Detailfeld haben. |
| Mehrsprachigkeit | Im Projekt existiert bisher keine Übersetzungsschicht; Deutsch ist fest in Templates. | Einführung als eigene Architektur-Arbeit (Registry + Übersetzungs-Resolver + Makros), danach Migration zuerst der gemeinsamen Komponenten, dann modulweise. Keine neue Abhängigkeit. |
| Doppelte deutsche Labels | Sieben Labels kommen in der Registry mehrfach vor (z. B. «Fisch» als Kostform/Allergen, «Bestellung», «Einstellungen»). | Zulässig, weil die Bedeutungen verschieden sind; die Validierung prüft Schlüssel-Eindeutigkeit, nicht Label-Eindeutigkeit. |
