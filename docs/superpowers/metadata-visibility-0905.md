# Gespeicherte Menüangaben sichtbar machen

## Problem und Umfang

Die Admin-Wochenübersicht verwirft Metadaten im Render-Adapter; die gespeicherte
Vorschau zeigt sie bisher nicht. Der Prüfblock des Editors verliert die
Allergen-Präsenz. Öffentliche Tages- und Wochenansichten zeigen bei leeren
Allergenlisten keinen Datenstatus und teilweise keine Beschreibung oder Hinweise.

## Verhalten

- Beide Profile zeigen gespeicherte Beschreibung, Hinweis, Herkunft, Labels und
  Allergene bei der jeweiligen Menükarte. Virtuelle Admin-Slots bleiben leer.
- Die gespeicherte Vorschau zeigt nur betitelte Menükarten. Damit lösen virtuelle
  Slots einer unvollständigen Cafeteria-Woche keinen Fehler bei der Formatierung
  leerer Beträge mehr aus; sie bekommen auch keine scheinbare Allergendeklaration.
- Eine gemeinsame Template-Teilansicht erhält die vorhandenen Label-Utilities;
  jede Angabe erscheint genau einmal. Kein CSS, Generator oder neues Paket nötig.
- `contains` erscheint als „Enthält“, `may_contain` als „Kann enthalten“.
- Leere Allergenlisten bedeuten „Allergenangaben nicht erfasst“, auch bei gesetztem
  Prüfstatus. Daraus folgt keine Aussage zur Allergenfreiheit.
- Bei vorhandenen, ungeprüften Angaben erscheint „Allergenprüfung offen“.
- Der Editor kennzeichnet seinen Prüfblock als zuletzt gespeicherten Stand.
- Komponenten bleiben Komponenten; Titel werden nicht als Zutatenquelle verwendet.
  Es gibt weder geschätzte Ergänzungen noch einen Import von Demoangaben.

## Grenzen und Prüfung

Keine Änderung an Speicherung, Schema, Publikations-/Snapshot-Vertrag oder
öffentlichen APIs. Die öffentliche Darstellung bleibt an veröffentlichte Daten
gebunden; Admin-Vorschau bleibt LAST-SAVED ohne Publikations-Fallback.
Print und Signage behalten ihre bisherigen Templates.

Gezielte Tests prüfen beide Profile mit gespeicherten und fehlenden Metadaten,
beide Allergen-Präsenzen, Editor-Fehleransichten, öffentliche Tages-/Wochenansichten,
Escaping und mobile/Desktop-Darstellung. Bestehende Rendering- und Snapshot-Gates
sichern Mengen, Profiltrennung und unveränderte Projektion ab.

GitNexus: `_cells` HIGH (ein direkter Aufrufer, drei Abläufe), `_display_effects`
HIGH (ein direkter Aufrufer, vier Editor-/Fehlerabläufe). Änderungen bleiben auf
Darstellung beschränkt und werden vor Integration unabhängig geprüft.
