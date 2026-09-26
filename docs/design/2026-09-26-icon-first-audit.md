# Icon-first UI-Audit (WP1a)

Dieses Dokument fasst das Ansichteninventar gemäss Spezifikation §12.1 zusammen.

## 1. Abdeckungstabelle aller administrativen Ansichten

| Ansicht | Template(s) | Listentyp | Sichtbare Aktionsvarianten je Zeile | Kopfaktionen (Anzahl, Primär) | Badge-/Statusvarianten | Filtermuster | Infokarten/Wiederholungen | Status |
|---|---|---|---|---|---|---|---|---|
| **Patienten-Wochenplan** | `patienten.html`, `_week_controls.html`, `_week_service.html`, `_course_line.html` | Kalender/Raster (`patient-admin-table`) | 1 (`actions.add` / `actions.edit` als `icon_button` oder `<a class="btn">`) | 4 (u.a. Prüfen, CSV, Übernehmen); Primär: `actions.confirm` | `label('Allergenangaben fehlen')`, `label('Nicht gespeichert')` | Wochen-Navigation (Datumssprung) | Warnungen wiederholen sich je Mahlzeit/Zeile | offen |
| **Wochenübersicht (cafeteria)** | `cafeteria.html`, `_week_controls.html`, `_week_menu_card.html`, `_service_courses.html` | Kartenraster | 1 (`actions.edit`/`actions.add` als `<a class="btn ui-sem-control">`) | wie Patienten-Wochenplan | `status_badge_sem('review.pending')`, div. `ui_label` | Profil-Abhängigkeit, Wochen-Nav | Fehlende Allergene wiederholen sich je Karte | offen |
| **Küchenkalender** | `kuechenkalender.html`, `kuechenkalender_anlass.html` | Kalender | 1 (`actions.add` "Planen" als `icon_button`) | 3 (Anlass anlegen, Heute, Vor/Zurück); Primär: `actions.add` | `label('Heute', 'info')` | Profil-Chips (`<a class="btn">`) | keine auffälligen | offen |
| **Menüs** | `menu_collection.html`, `menu_editor.html` | Liste / Editor-Formular | Editor: bis zu 4 (`actions.edit`, Move, Delete via rohen `<button>`) | (Editor) 3 (Speichern, Zurück, Öffnen); Primär: `actions.save` | `label(mode_text)`, `allergen-mode-badge` | Text-Filter (Rezeptsuche im Formular) | Warntext "Allergenangaben nicht erfasst" | offen |
| **Bausteine** (Pilot) | `components.html`, `component_editor.html` | Tabelle (`admin-table`) | 1 (`actions.edit` über `row_actions`) | Filterleiste + `actions.add`; Primär: `actions.add` | `ui_label('Aktiv'/'archiviert')`, Kategorie-Labels | 5 Selects (Kategorie, Label, Allergen, Land) | Leere Zustände (`empty_state`) | offen |
| **Zutaten** | `grundlagen_food.html` | Detail-Formular in Sektionen | keine | 2 je Sektion (Save/Undo); Primär: `actions.save` | `section_summary` mit Icon (`clipboard-check`) | Input-Suche mit Submit-Button | Erklärtexte je Abschnitt ("Gespeicherte Allergenangaben...") | offen |
| **Rezepte** (Pilot) | `rezepte.html`, `rezepte_editor.html`, `rezepte_ansicht.html` | Tabelle / Editor-Formular | 2 (`actions.open` + `actions.more` Dropdown-Summary) | 1 (Liste `actions.add`), >3 (Editor `actions.save` etc.) | "Entwurf" / "Archiviert" als Plaintext | Filterbar (Query/Tags) | Details-Akkordeons für Zutaten/Schritte | offen |
| **Gerichtvorlagen** | `gerichtvorlagen.html`, `gerichtvorlage_einplanen.html` | Tabelle (`admin-table`) | 1 (`actions.open` "Einplanen" über `row_actions`) | 2 (`actions.add`, `actions.back`); Primär: `actions.add` | `label('Aktiv'/'Archiviert')` | `filter_bar_sem` mit Archiv, Rezeptsuche | Paginierung (Vorige/Weitere) | offen |
| **Lager** | `lager.html` | Tabelle (`lager-table`) | 1 (`actions.open` via `icon_button`) | diverse Speichern/Buchen-Aktionen | `label('Kein Bestand erfasst', 'warning')` | keine | "Kein Bestand erfasst" wiederholt je Zeile | offen |


## 2. Pflichtreferenzen (§2) und Zeilenfunde

Die für WP1 relevanten Kern-Ansichten und konkrete Code-Befunde (mit Zeilen):

- **Patienten-Wochenplan**:
  - `admin/_course_line.html:22`: `icon_button('actions.add', ... emphasis='secondary')` (Text: `<kind> planen`)
  - `admin/_course_line.html:26`: rohes `<a class="btn ui-sem-control ui-sem-control--icon-only">` für Edit-Aktion.
- **Wochenübersicht (cafeteria)**:
  - `admin/_week_menu_card.html:15`: breiter Button mit Text für Vorlage (`<a class="btn text-wrap text-start">`).
  - `admin/_week_menu_card.html:77`: Bearbeiten/Hinzufügen-Aktion als `<a class="btn ui-sem-control">`.
  - `admin/_week_controls.html:65`: `icon_button('actions.confirm', type='button', text=publish_label)`
- **Küchenkalender**:
  - `admin/kuechenkalender.html:49`: `icon_button('actions.add', ... class='kitchen-cal-plan')`
  - `admin/kuechenkalender.html:114-116`: Profil-Filter hardcodiert als `<a class="btn">` anstatt als Icon-Filter-Komponente.
- **Menüs**:
  - `admin/menu_editor.html:178-180`: Rohe `<button type="button" class="btn">` für "Nach oben", "Nach unten" und "Löschen".
- **Bausteine**:
  - `admin/components.html:140`: Standard-Aktion über das Makro `row_actions(...)`.
  - `admin/component_editor.html:33-34`: Abbrechen/Speichern Buttons am Seitenkopf.
- **Zutaten**:
  - `admin/grundlagen_food.html:147`: Prüf-Aktion (Confirm/Undo) als `icon_button` neben verstecktem Input.
- **Rezepte**:
  - `admin/rezepte.html:34`: Kompakte Aktionen im `<details class="admin-compact-actions">`-Menü.
- **Gerichtvorlagen**:
  - `admin/gerichtvorlagen.html:43`: Einplanen als `icon_button('actions.open', text='Einplanen')`.
  - `admin/gerichtvorlagen.html:89`: Einplanen im Makro `row_actions`.
- **Lager**:
  - `admin/lager.html:43`: Aktion über `icon_button('actions.open')`.


## 3. Zählung pro Ansicht (Abgleich mit Zielen §3.1, §3.2)

- **Zeilenaktionen (Ziel: max. Hauptaktion + Überlauf)**: In den meisten Tabellen (`components`, `gerichtvorlagen`) wird dies bereits über `row_actions` (1 Aktion) oder `<details>`-Überlauf (`rezepte`) eingehalten. Editor-Listen (wie `menu_editor`) haben aktuell zu viele direkt sichtbare Aktionen je Zeile (Edit, Up, Down, Delete = 4 Aktionen). Kalender haben konsequent 1 Aktion (Slot).
- **Kopfaktionen (Ziel: Primäraktion hervorheben)**: Im `_week_controls.html` gibt es viele verschiedene Aktionen (Prüfen, Publizieren, CSV, Vorwoche kopieren). Sie sind in Dropdowns teils verpackt, aber die visuelle Hierarchie kann optimiert werden. In Editoren sind Abbrechen/Speichern meist gepaart (`rezepte_editor`, `component_editor`).
- **Wiederholungstexte**: Stark vertreten sind `Allergenangaben nicht erfasst` (Menükarte), `Allergenangaben fehlen` (Patientenplan) und `Kein Bestand erfasst` (Lager). Dies führt zu optischer Unruhe in den Übersichten, was gemäss §8.2 zu bündeln oder kompakter zu gestalten ist.


## 4. Fachliche Schutzstellen (§8.4)

Diese Texte und Prüfmechanismen **müssen** erhalten bleiben:

- **Nicht erfasst**:
  - `admin/_week_menu_card.html:37` (`<p>Allergenangaben nicht erfasst</p>`)
  - `admin/menu_editor.html:389` (`Allergenangaben nicht erfasst`)
- **Allergenprüfung offen**:
  - `admin/_week_menu_card.html:39` (`<p>Allergenprüfung offen</p>`)
  - `admin/_week_controls.html:51` (`allergen_stats.review_open ~ ' Allergenprüfungen offen'`)
- **Lagerbestand fehlt**:
  - `admin/lager.html:41` (`label('Kein Bestand erfasst', 'warning', icon='alert-triangle')`)
- **Entwurf angezeigt / Nicht gespeichert**:
  - `admin/rezepte_editor.html:28` (`Entwurf · Änderungen werden erst mit Speichern übernommen.`)
  - `admin/_week_service.html:38` (`label('Nicht gespeichert', 'neutral', detail='Vorgabe, noch nicht gespeichert')`)


## 5. Reihenfolgevorschlag (Mikropakete WP3–WP5)

Um eine kollisionsfreie und schrittweise Umsetzung zu gewährleisten:

1. **WP3 (Pilot)**: `admin/components.html`, `admin/component_editor.html`, `admin/rezepte.html`
   - Grundbausteine konsolidieren, Listenanatomie in einfachen Tabellen etablieren.
2. **WP4**: `admin/menu_collection.html`, `admin/menu_editor.html`, `admin/gerichtvorlagen.html`
   - Editor-Zeilenaktionen vereinfachen, Suchfilter konsolidieren.
3. **WP5**: `admin/patienten.html`, `admin/cafeteria.html`, `admin/_week_controls.html`
   - Komplexe Raster- und Kalenderansichten, Reduktion der Kopfaktionen und Warnwiederholungen.
