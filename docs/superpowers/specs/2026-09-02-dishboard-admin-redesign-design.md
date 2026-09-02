# Software Design Document (SDD): Dishboard Admin Redesign

## 1. Scope, Non-Goals und Constraints
**Scope:** Vollständiges Redesign des Dishboard-Admin-Bereichs zur stark vereinfachten, fehlertoleranten Menü-Erfassung (Novice-Friendly).
**Non-Goals:** Keine neuen Frameworks, keine Änderung der Patienten-App.
**Constraints:**
- Stack: Flask, Jinja, PostgreSQL, Vanilla JS.
- Keine neuen Abhängigkeiten (zero new dependencies).
- Design-System: Wiederverwendung der Therapieplan-Design-Tokens.
- Strikte Mandanten-Isolation: Patient vs. Personal/Gäste (Cafeteria).
- Immutable Snapshots: Bereits publizierte Versionen bleiben unveränderlich.

## 2. Datenmodell (Additiv)
**Neue Komponententabellen:**
- `menu_components`: `location_id`, `public_id` (UUID), `profile_scope` (common/patient/staff_guest), `category` (meat/side/vegetable/sauce/dessert/other), `name`, `origin_country_code`, `active` (boolean, Archivierungsflag), `row_version`, Timestamps. Constraints: Case-insensitive Unique Constraint für den Namen.
- Child-Tabellen für Labels/Allergene: Eine Zuweisung pro Allergen (Präsenz).

**Erweiterungen bestehender Tabellen:**
- `menu_item_components`: Erweiterung um nullable `component_id` und `component_row_version`. Der bestehende `component_text` bleibt zur Abwärtskompatibilität und für manuelle Überschreibungen erhalten.
- `menu_items`: Neues Metadaten-Feld `mode` (`automatic` / `manual`).

## 3. Deterministische Vererbung (Inheritance)
- **Auflösung:** Server-seitige Auflösung der UUIDs und Scopes. Union-Menge der Labels aller zugeordneten Komponenten. "Contains" (Enthält) überschreibt "may_contain" (Kann Spuren enthalten).
- **Herkunft:** Die Herkunft (origin) der Komponente wird transparent weitergegeben.
- **Modi:**
  - `automatic`: Materialisiert die berechneten Werte in die bestehenden Metadaten-Tabellen (effective metadata).
  - `manual`: Expliziter Whole-Menu Override (Überschreiben des gesamten Menüs, keine Vererbung).
- **Invalidierung:** Jede Änderung an Komponenten, Metadaten oder Zuweisungen setzt den Allergen-Review-Status zurück.
- **Publish-Blocker:** Eine veraltete Master-Version (`stale master`) blockiert das Publizieren (Publish), bis diese Version explizit akzeptiert/reviewt wurde. Die JSON-Repräsentation zum Zeitpunkt der Publikation wird eingefroren (frozen).

## 4. Migration (v12 -> v13 via Skript 0010)
- **Backfill:** Jede Legacy-Komponente wird pro Location/Profile als `menu_components` angelegt (Category: `other`). Der Text bleibt exakt erhalten.
- **Metadata Preservation:** Der Modus `manual` stellt sicher, dass bestehende Legacy-Menü-Metadaten vollständig erhalten bleiben.
- **Cleanup:** Bei Duplikaten gewinnt "contains". Unaufgelöste Legacy-Zeilen bleiben als "gültig" markiert (unresolved rows valid).
- **Updates:** Anpassung von DB-Grants, Validator-Skripten, `db.py` und Schema.
- **Sicherheit:** Migration muss voll reversibel sein (Safety/Backup-Garantie).

## 5. Routen und Data Flow
- **Routen-Architektur:**
  - Bestehende Profile-GETs erwarten einen validierten `week`-Query-Parameter.
  - Fokussierte Menu-GET/POST-Requests funktionieren als Partial-Service.
  - Week Header und Service-Status werden ebenfalls als Partial-Ops abgewickelt.
- **Kopierfunktion:** Same-Profile Copy ist nur in leere Zielwochen zulässig.
- **Komponentenverwaltung:** Endpoints für List, Create, Edit, Archive und Search.
- **Preview:** Gespeicherte Entwürfe (Drafts) werden als Vorschau mit Auth-Check gerendert (Header: no-store, Banner: Preview, Öffnung in neuem Tab).
- **Publish Workflow:** Publish erfordert ein Review und sendet einen POST auf den *bereits zuvor gespeicherten* Draft. Umsetzung via PRG-Pattern (Post/Redirect/Get) und Flash-Messages für Revisionen.
- **Sicherheit & Optimistic Locking:** Profile werden serverseitig abgeleitet. Einsatz von CSRF-Tokens, Capabilities-Checks, exact Keys und Optimistic Locking für `week` und `component` Versions.

## 6. User Experience (UX)
- **Week Overview:** 10 (Patient) bzw. 28 (Staff) Cards. Eindeutige Status-Anzeigen: empty, incomplete, review open, ready, live, changed. Navigation: previous, today, next. Ansichten: empty, loading, error, dense.
- **Component UX:** Search, Category-Filter, Checklisten-Auswahl, große Labels, eine vererbte Zusammenfassung (inherited summary) sowie ein Advanced Override.
- **Sprache & Formatierung:** Komplett deutsche, für Laien verständliche Texte. Währungsdarstellung für CHF mit Komma/Punkt-Dezimalstellen (Decimal -> Rappen).
- **Fehlerhandling:** Präzise Fehlermeldungen auf Tages-, Mahlzeit- und Menüebene.
- **Interaktionen:** Dirty-Guard bei ungespeicherten Änderungen, natives Bestätigungsfenster beim Publizieren, klare Loading-Texte, Sticky Actions auf mobilen Geräten. Auto-Fokus auf den ersten Fehler.
- **Responsiveness & A11y:** Vollständig tastaturbedienbar. Unterstützte Viewports: 390px, 1440px, 2560px sowie bei 50% Zoom. Status-Indikatoren dürfen sich nicht ausschließlich auf Farbe verlassen (a11y).

## 7. Acceptance Matrix
1. **Goal Requirements:** Alle funktionalen Ziele der vereinfachten Eingabe erfüllt.
2. **Security:** Isolation der Daten, CSRF, Parameter-Tampering verhindert.
3. **Tests/Gates:** Alle Unit-, Integration- und E2E-Tests passieren erfolgreich. Linting und Typisierung ohne Fehler.
4. **Reviews:** Abnahme durch AGY und Grok (Consensus-Review) erfolgreich abgeschlossen.
5. **Deployment:** Reibungsloser Deploy, erfolgreicher Rollback-Test und Live-Proof erbracht.

## 8. Phasen und Subprojekte (Ownership Boundaries)
- **Phase 1 (Schema & DB):** Schema-Updates und Migration (0010), `db.py`, Grants, Validator.
- **Phase 2 (Store & Models):** Datenmodell-Objekte, Vererbungslogik, Optimistic Locking.
- **Phase 3 (Workflow & Routes):** Partial-Services, Controller-Logik, Publish-Workflow.
- **Phase 4 (Templates, JS, CSS):** Vanilla JS, Jinja-Templates, Therapieplan-Tokens-Integration.
*Regel:* Keine parallelen Writer auf geteilten Contracts (z.B. Schema), strikte serielle Bearbeitung an den Schnittstellen.

## 9. Self-Review, Contradictions, Ambiguity
- **Keine Widersprüche identifiziert:** Die Trennung von `automatic` und `manual` löst potenzielle Konflikte bei Metadaten sauber auf.
- **Eindeutigkeit:** Die Definition des Publish-Blockers durch einen "stale master" ist eindeutig festgelegt.
- **Vollständigkeit:** Alle vom Benutzer vorgegebenen Constraints sind dokumentiert und adressiert.
