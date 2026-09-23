# Import-Notizen «Global UI Polish Run» (Auftraggeber, 2026-09-23)

Quelle: Prompt des Auftraggebers vom 2026-09-23 (Text in `00_PROMPT_Global_UI_Polish_Run.md`, unverändert
übernommen; ein führendes Sonderzeichen vor dem Titel entfernt). Keine Bilder, keine Mockups.

## Einordnung

- Ergänzt die laufende UI/UX-Welle (Handoff 2026-09-20, Ergänzungsprompts «Kompakte Formulare» und
  «Globale UI-Vereinfachung», Design System v2, Semantic UI Language Pack). Widerspricht diesen nicht;
  bei Überschneidung gelten die konkreteren Vorgaben (v2 Anti-Patterns §14, DoD §15, kanonische Verben,
  48-px-Bedienziele, Seitentitel = Navigationspunkt, genau eine Primäraktion).
- Neu gegenüber v2: verbindliches **kleines Designsystem** über alle Bausteine (§2), sechs
  **Statusstile** (§7: neutral, aktiv, erfolgreich, Warnung, Fehler, Information), vier **Aktionsstufen**
  (§4: primär, sekundär, tertiär, destruktiv), **Textreduktion** (§5), **Interaktionszustände** (§12),
  eine **Abschlussprüfung je Ansicht** (§17).
- Ausführung als Phasen (Orchestrator): P0 Import + Regelabbildung in der Designquelle · P1 App-weites Audit
  (nur lesen) · P2 Designsystem-Konsolidierung (Tokens, Buttons, Status, Formfelder, Tabellen, Cards,
  Dialoge, Leer-/Lade-/Fehlerzustände in den gemeinsamen Dateien) · P3 Anwendung je Modul (laufende und
  bereits gelieferte Pakete) · P4 Abschlussprüfung mit Vorher/Nachher-Belegen.
- Technikvorgabe §14 deckt sich mit dem Projektvertrag: kein Framework-Wechsel, keine Migration, keine
  fachlichen Änderungen, keine DB-Migration.

## Massgebliche Ableitung

Die Regeln werden in `docs/design/2026-09-09-unified-ui-design-system.md` im Abschnitt
«Auftraggeber-Polish-Lauf (2026-09-23)» als R-/M-/A-Regeln geführt; dieser Ordner ist die Quelle, die
Designquelle die verbindliche Ableitung.
