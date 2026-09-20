# Importhinweise zum Design System v2 (2026-09-20)

Die sechs Dateien dieses Ordners (`README.md`, `02_SDD/`, `03_DESIGN_MANIFEST/`, `04_REFERENCES/README.md`,
`05_CLAUDE_CODE/`, `06_QA/`) sind unverändert aus dem gelieferten Paket `Dishboard_Design_System_v2` übernommen.
Laut Paket-README haben sie bei Widersprüchen Vorrang vor dem früheren Handoff.

## Was nicht in diesem Ordner liegt — und warum

- **`base_handoff/`** des Pakets ist inhaltsgleich mit dem bereits eingecheckten ersten Handoff unter
  [`../uiux-handoff-2026-09-20/`](../uiux-handoff-2026-09-20/) und wird nicht doppelt abgelegt. Dort fehlt weiterhin
  bewusst ein Referenzbild (Seite «Benutzer & Zugriff» mit den Anmeldenamen der produktiven Konten), weil dieses
  Repository öffentlich ist; siehe dessen `03_REFERENCES/README.md`.
- **Referenzbilder v2:** `04_REFERENCES/README.md` nennt die Ordner `accepted-settings/`, `current-modules/`,
  `current-weekplan/` und `generated-mockups/`. Im gelieferten Paket lag unter `04_REFERENCES/` nur dieses README;
  die Bildordner fehlten. Vorhanden sind: die akzeptierten Einstellungs-Referenzen und Ist-Bilder der Module im
  ersten Handoff sowie die Beschreibung der drei im Auftragsgespräch gezeigten Beispielbilder unter
  [`../uiux-handoff-2026-09-20/07_ERGAENZUNGEN/README.md`](../uiux-handoff-2026-09-20/07_ERGAENZUNGEN/README.md).
  Für den Wochenplan (Cafeteria, Patienten, Wochenübersicht, Küchenkalender, Tagesansicht) gilt bis zur Nachlieferung
  der Bilder der Text des SDD v2 §5–§6 als Zielmodell; der Ist-Zustand wird aus eigenen Aufnahmen belegt.

## Einordnung gegenüber bestehenden Projektregeln

- Touch-Ziele: SDD v2 §13 nennt «ca. 44 px». Im Projekt gilt und bleibt der strengere, durch Tests abgesicherte
  Wert von **48 px** für zentrale Bedienelemente; er erfüllt die v2-Vorgabe.
- Navigation: v2 §3 bestätigt die bereits umgesetzte Regel (Unterpunkte nur links beim aktiven Hauptpunkt, keine
  horizontale Doppel-Navigation) und ergänzt den Hauptpunkt **Wochenplan** mit den Unterpunkten Cafeteria,
  Patienten, Wochenübersicht, Küchenkalender.
- Allergene: v2 §8 («abweichende Präsenzangabe erst nach Auswahl/in Details») wird als Inline-Detail direkt an der
  gewählten Option umgesetzt (Muster M21 der Designquelle). Grund: Die Formulare senden Allergen und Präsenz als
  indexgepaarte Wiederholfelder; das Detailfeld wird deaktiviert statt versteckt und bleibt im selben Container.
- Normative Übernahme: Die Regeln von SDD v2 und Manifest v2 werden in die lebende Designquelle
  [`../2026-09-09-unified-ui-design-system.md`](../2026-09-09-unified-ui-design-system.md) eingearbeitet; diese bleibt
  die Pflichtlektüre laut `AGENTS.md`.
