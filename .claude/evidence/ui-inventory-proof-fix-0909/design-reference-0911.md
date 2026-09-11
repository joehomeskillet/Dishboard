# Zielbild-Referenz vom 11. September 2026 — Einordnung für MP-UI-BRAND-DECISION

Der Auftraggeber hat am 11.09.2026 im Chat ein Mockup der Cafeteria-Wochenplanung
(KW 37, 7.–11. September 2026) als «Beispiel für ein gutes Design anhand des Beschriebs» und
ausdrücklich als Referenz geliefert. Das Bild liegt nur im Chatverlauf vor, nicht als Datei im
Repository; es ist deshalb hier beschrieben, nicht versioniert.

**Status:** stilistische Orientierung. Nach Master §11 Phase C ist ein generiertes Bild
«stilistische Orientierung, keine pixelgenaue Browser-Baseline und kein funktionaler Vertrag».
Nach Master §2.2 und §8 werden nur tatsächlich vorhandene Funktionen und Daten dargestellt.
Dieses Inventar-WP ändert keine Oberfläche; Umsetzung und Konfliktentscheid gehören zu
MP-UI-BRAND-DECISION und den nachfolgenden UI-Paketen.

## Übereinstimmung mit dem Master (übernehmbar)

| Element im Mockup | Master-Bezug |
|---|---|
| Dunkle Petrol-Sidebar mit Logo oben, Abmelden unten | §5.1 `--app-sidebar`, §7 Logout erreichbar |
| Navigation nach Aufgaben gruppiert (ohne Titel, «Stammdaten», «Ausgabe», «Administration») | §7 Gruppierung nach Aufgaben, leere Gruppen weglassen |
| Aktiver Eintrag mit Fläche, Icon und Zweizeiler (Titel plus Kurzbeschreibung) | §7 aktiver Eintrag, verständliche Benennung |
| Warmer heller Hintergrund, weisse Karten mit dezentem Rand | §5.1 `--app-bg`, §8 Cards |
| Burgunder für die wichtigste Handlung und Auswahl (Publizieren, ausgewählte Karte, Speichern) | §5.1 Burgunder = wichtigste Handlung |
| Status-Pills mit Icon und Text («Bereit», «Prüfung offen», «Noch offen») | §8 Status-Badges, Farbe nie einzige Information |
| Wochenraster Tage × Menüarten, Datum unter jedem Tag | UX-Konzept WEEK-03 |
| Seitliches Bearbeitungsfenster, Woche bleibt sichtbar | UX-Konzept EDIT-01 (Offcanvas, vorab zu prüfen) |
| Wochenhinweis unten mit Erklärung, wo er erscheint | UX-Konzept WEEK-07 |

## Konflikte, die vor einer Umsetzung zu entscheiden sind

| Element im Mockup | Konflikt | Beleg |
|---|---|---|
| Überschriften serifenlos | Master §5.2 verlangt Georgia für H1/Card-Titel; Produkt liefert Fira Sans (`common.fonts.conflict` der Matrix) | Master §5.2, `ui-route-matrix.json` |
| «KW 37 · 7.–11. September 2026» (KW zuerst) | UX-Konzept WEEK-02: Datum vor Kalenderwoche | UX-Konzept §5.1 |
| «Publizieren» | UX-Wörterbuch: «Veröffentlichen» | UX-Konzept §3.3 |
| «Publizieren» primär, obwohl 2 Prüfungen offen | Bei offenen Prüfungen ist «Offene Angaben prüfen» die Hauptaktion; eine Hauptaktion je Kontext | UX-Konzept UX-03, WEEK-06 |
| Kebab-Menü «⋮» auf jeder Karte | Häufige Aktionen beschriftet sichtbar, kein leeres Dreipunktmenü; Karte braucht sichtbares «Bearbeiten» | Master §8, UX-Konzept WEEK-05 |
| Status als frei wählbares Feld im Editor | Prüfstatus ist Ergebnis der bestehenden Prüfung, keine neue Sperr- oder Statuslogik im Browser | UX-Konzept STATE-01/03 |
| Rollenname «Cafeteria.Admin» sichtbar | Technische Begriffe im Küchenablauf vermeiden | UX-Konzept UX-06 |
| Food-Fotos auf jeder Karte | Vorhandene optionale Menübilder ja; generierte Essensbilder sind ausgeschlossen | UX-Konzept VIS-01 |

## Im Mockup, im Produkt nicht vorhanden — nicht erfinden

Geprüft gegen alle 116 Routen und 75 Templates des Inventars (Quelle `5f5f6cb`, Schema 25):

| Element im Mockup | Befund |
|---|---|
| Globale Suche «Gericht, Zutat oder Vorlage suchen … Ctrl+K» | Keine globale Suchroute; nur Listenfilter. Tastenkürzel ist nie Voraussetzung (UX-02). |
| Menüpunkt «Menüarchiv – Frühere Wochen» | Keine Archivroute; nächstliegend `admin.week_management` («Wochenverwaltung»). Nur Umbenennung prüfen, keine neue Funktion. |
| Menüpunkt «Vorlagen – Schnell starten» | `admin.vorlagen` sind Druck- und Screen-Ausgabevorlagen, keine Menüvorlagen; Bedeutung nicht vertauschen (UX-Konzept §3.2). |
| Menüpunkt «Allergene & Labels» | Keine eigene Route; ob das Grundlagen-Vokabular Allergene oder Labels führt, klärt MP-UI-FOUNDATIONS. |
| Menüpunkt «Preise – Verkaufspreise» | Keine eigene Preisseite; Preise sind Felder im Menü-Editor. |
| Zeilen «Vegan» und «Dessert» mit eigenen Preisen | Cafeteria hat die bestehenden zwei Menüarten (UX-Konzept FACH-01). |
| Kennzahl-Pills «8/10 Gerichte vollständig», «2 Prüfungen offen» | Nur mit vollständig vorhandener echter Zahl (TECH-03, WEEK-06). |
| Handschrift-Slogan «Gutes Essen macht den Tag besser ♡» | Kein Claim ergänzen (Master §7); dekorativ. |
| Editor-Tabs Details/Komponenten/Allergene/Preise, Feld «Kategorie» | Nur vorhandene Felder und Formulare (FACH-03, IMPL-03). |

## Im Produkt vorhanden, im Mockup nicht sichtbar — muss erreichbar bleiben

NAV-02 «kein Funktionsverlust durch Aufräumen»: Kochbücher (`admin.cookbooks_list`), API &
Schnittstellen (`admin.api_*`), Wochenverwaltung und Wochenprüfung (`admin.week_management`,
`admin.week_review_get`), Grundlagen-Detailarten, Benutzer-Protokoll und Zugriffsverlauf,
Patientenplan (`admin.patienten`). Die bedingte Sichtbarkeit (Rezepte/Kochbücher ab Editor,
Benutzer sowie Design & Marke nur Admin) bleibt serverseitig bestimmt.

## Zuordnung der Mockup-Navigation zu echten Endpunkten

| Mockup | Endpunkt(e) im Inventar | Heutige Beschriftung |
|---|---|---|
| Wochenplan | `admin.cafeteria`, `admin.patienten` | Wochenpläne |
| Menüarchiv | (keiner; nächstliegend `admin.week_management`) | Wochenverwaltung |
| Vorlagen | `admin.vorlagen` (Ausgabevorlagen) | Vorlagen |
| Gerichte | `admin.recipes_list` | Rezepte (bedingt) |
| Zutaten & Komponenten | `admin.components_list`, `admin.master_data_list` | Komponenten, Grundlagen |
| Allergene & Labels | (keiner) | — |
| Preise | (keiner) | — |
| Screens | `admin.screens` | Screens |
| Website | `admin.preview` | Menüs/Vorschau je Bereich |
| Bereiche & Zeiten | `admin.operations_settings` | Bereiche & Zeiten (Admin) |
| Design & Marke | `admin.branding_editor`, `admin.display_settings` | Design & Marke (Admin) |
| Import | `admin.import_preview`, `admin.import_csv` | CSV Import |
| Benutzer | `admin.local_users_list` | Benutzer & Zugriff (Admin) |
| Abmelden | `auth.logout` | Abmelden |

Nächster Schritt nach dem Inventar-Freeze: MP-UI-BRAND-DECISION entscheidet die Konflikte oben
(insbesondere Typografie, KW/Datum, Primäraktion) und legt fest, welche übernehmbaren Elemente
als gemeinsame Komponenten umgesetzt werden.
