# Wochenverwaltung

Gespeicherte Wochen beider Profile erhalten eine eigene Navigation und eine nach Datum absteigend sortierte Übersicht mit zwölf Wochen pro Seite. Auch leere Wochen erscheinen. Der Status verwendet die bestehende fachliche Ableitung; Archivierung bleibt ein separater Hinweis.

Eine beschriftete Erfassungsmaske legt ausschliesslich neue Wochen an. Montag, Titel und Hinweis verwenden den bestehenden Parser und Store. Erwartete Version ist immer null; vorhandene Wochen werden mit HTTP 409 geschützt. Standort, Benutzer, Profil und Formularzweck binden den CSRF-Token. Speichern führt mit HTTP 303 zum Wocheneditor. Vorschau und Kopieren verwenden bestehende Routen; Kopieren öffnet die Bestätigung für die Folgewoche. Keine Migration, Löschung oder automatische Veröffentlichung.

Gestaltung: ruhige Südhang-Oberfläche mit vorhandenen Token-Klassen; klare Hauptaktion „Woche anlegen“, lesbare Wochenkarten und native Links. Tablet 768×1024, 800×1280, 1024×768 und 1280×800 sowie Telefon bleiben ohne horizontalen Inhaltsüberlauf nutzbar. Bedienflächen mindestens 44 Pixel. Fehler erhalten Eingaben.

Prüfung: echte PostgreSQL-Tests für leere Anlage, Version eins, Konfliktschutz, Profil-/Standortgrenzen, CSRF, Berechtigungen, Status und Pagination; Browser prüft Navigation, Anlage und Tabletgeometrie. Bestehende Authentifizierung und Passwörter bleiben unverändert.
