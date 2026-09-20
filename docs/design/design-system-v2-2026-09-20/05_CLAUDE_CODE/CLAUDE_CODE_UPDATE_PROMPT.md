# Claude Code – Auftrag zur UI/UX-Migration

Lies zuerst `02_SDD/DISHBOARD_UI_UX_SDD_V2.md` und `03_DESIGN_MANIFEST/DESIGN_MANIFEST_V2.md`. Danach prüfe sämtliche Referenzen unter `04_REFERENCES/`.

Arbeite nicht screenshotweise. Führe zuerst einen vollständigen UI-Audit des Repositories durch. Erstelle eine Matrix aller Routes/Templates/Partials und ordne sie gemeinsamen UI-Patterns zu. Identifiziere zentrale Komponenten, bevor du Einzelseiten änderst.

Priorität: 1) gemeinsame Shell und kontextuelle linke Navigation, 2) Statusbar/Toolbar/Filter/Actions, 3) Wochenplan vollständig, 4) Menüeditor inkl. Allergene, 5) Menüs & Bausteine vollständig, 6) Einstellungen ohne Verschlechterung, 7) Responsive/A11y/Regression.

Keine Fachfunktion entfernen. Kein neues Framework. Flask + Tabler bleiben. Bestehende Backend-Verträge möglichst unangetastet lassen. Wiederverwendbare Komponenten statt Template-Copy/Paste.

Vor jedem Work Package: betroffene Dateien, geplante Änderungen, Risiken und Tests nennen. Danach implementieren, Tests ausführen und Vorher/Nachher-Screenshots erzeugen. Bei unklarer Fachlogik nicht raten: bestehende Route/Tests/Modelle untersuchen.
