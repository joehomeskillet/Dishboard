# Cross-Vendor-Review: Admin-Shell-/Navigations-Spezifikation

Prüfobjekt: `docs/design/2026-09-11-admin-shell-navigation-spec.md`  
Worktree: `/nvmetank1/projects/menuplan/.claude/worktrees/ui-shell-spec-agy-0911`  
Commit: `953fd28be43c258507e90f1b369373a13d346c5b`  
Reviewer: grok-4.6 (read-only). Keine Repo-Edits.

Massstab: Master `docs/design/2026-09-09-unified-ui-design-system.md` §§3, 5.2, 7, 8, 10, 12; SDD `surfaces-sdd.md` §§4–5; `surfaces-wps.json`; `ui-route-matrix.json`; Icon-Manifest 07.09.; `design-reference-0911.md`; heutige Templates.

Kontrast (WCAG 2.2, relative luminance, Python):  
`#C7D8D9/#173C3F` 8.12:1 · `#9AB7BA/#173C3F` 5.62:1 · `#FFFFFF/#31585B` 7.84:1 · `#F3A6C0/#31585B` **4.12:1** · `#FFFFFF/#173C3F` 11.97:1.

Sprite/Lock (`tabler.lock.json` icons[] und `tabler-icons.svg` `id="tabler-*"`): vorhandene Nav-Icons da; vorgeschlagene 11 IDs alle **MISSING**.  
`container-xl` in `static/vendor/tabler/tabler.min.css`: 1140 px ab 1200 px, 1320 px ab 1400 px. Nicht 1200 px. `admin-tabler.css` setzt kein `max-width: 1200px` auf `.container-xl`.  
Visuelle `admin_tabler`-Routen in der Matrix: **41**, alle in §8.2 zugeordnet.

---

## Befunde

docs/design/2026-09-11-admin-shell-navigation-spec.md:282 HOCH H1-Schrift wird fest auf `Georgia, "Times New Roman", serif` gesetzt; Konflikt K1 (Fira vs Arial/Georgia) ist in MP-UI-BRAND-DECISION offen (`ui-route-matrix.json` `common.fonts.conflict`, `design-reference-0911.md` Zeile 32). Korrektur: Schrift als «gemäss MP-UI-BRAND-DECISION» referenzieren, Familie nicht in der Shell-Spec festlegen.

docs/design/2026-09-11-admin-shell-navigation-spec.md:126 HOCH §3.1/§3.2 versprechen Icons «aus dem vorhandenen Vorrat», schlagen aber `calendar-stats`, `puzzle`, `book-2`, `books`, `database`, `device-desktop`, `template`, `api`, `users`, `palette`, `clock-cog` vor. Keine dieser IDs steht in `static/vendor/tabler.lock.json` `icons[]` (Zeilen 53–81) noch als `id="tabler-…"` im Sprite. Icon-Manifest 07.09. §4: fehlende Symbole sind Assetarbeit, kein Aufruf erfundener Sprite-IDs; Master §4.1: bestehende Sprite-Einbindung, keine neue Bibliothek. Korrektur: heutige Sprite-Namen behalten oder neue IDs nur als Option «nach Vendoraufnahme» kennzeichnen.

docs/design/2026-09-11-admin-shell-navigation-spec.md:24 HOCH §1.1 und §10.1 nennen `MP-UI-PUBLIC-VIEWS` und `MP-UI-SIGNAGE`; beide IDs fehlen in `surfaces-wps.json`. Korrektur: Public/Signage → `MP-UI-SPECIAL-OUTPUTS` plus Runtime `MP-QA-PUBLIC-RUNTIME`; Admin-Screens/Vorlagen bleiben `MP-UI-OUTPUT-HUBS`; Weiss-Politur `MP-UI-PUBLIC-WHITE-POLISH`.

docs/design/2026-09-11-admin-shell-navigation-spec.md:23 HOCH §1.1 verbietet Hexwerte («nur Tokennamen»), §5.4 listet trotzdem `#C7D8D9`, `#173C3F`, `#9AB7BA`, `#FFFFFF`, `#31585B`, `#F3A6C0`. Auftrag ROOT-START: nur Tokennamen. Korrektur: Paare als `--app-sidebar-text` auf `--app-sidebar` usw. benennen; Messung an MP-UI-TOKENS verweisen.

docs/design/2026-09-11-admin-shell-navigation-spec.md:244 HOCH §5.4 Nr. 4 behauptet `--app-sidebar-indicator` auf `--app-sidebar-active` «~6.1:1». WCAG-Rechnung `#F3A6C0` auf `#31585B` ergibt **4.12:1**. Schwelle SC 1.4.11 (≥ 3:1) bleibt erfüllt, die Zahl ist falsch. Weitere Abweichungen: Weiss/Active 7.84 nicht ~7.2; Fokus 11.97 nicht ~12.8; Text 8.12 nicht ~8.3; Label 5.62 nicht ~5.4. Korrektur: gemessene Verhältnisse oder «von TOKENS zu messen» ohne erfundene Zahlen.

docs/design/2026-09-11-admin-shell-navigation-spec.md:274 HOCH §6.2 setzt `overflow-x: hidden` auf Body/Shell. Master §10 und SDD §5 verlangen ein Layout ohne horizontalen Dokumentüberlauf, lokale Tabellenscrollregionen erlaubt; Verstecken kaschiert Layoutfehler. Korrektur: Overflow durch `min-width: 0` am Hauptbereich und lokale Scrollregionen lösen, nicht am Viewport abschneiden.

docs/design/2026-09-11-admin-shell-navigation-spec.md:136 HOCH «API & Schnittstellen» wird auf Admin (`users.manage` / `*`) beschränkt. Matrix `admin.api_overview` Capability ist `api.keys.manage` (`ui-route-matrix.json` Zeile 279), Rollen nur `Cafeteria.Admin`. Sidebar zeigt den Eintrag heute ohne Guard (`_workflow_sidebar.html` Zeile 71) und `common.navigation.always_visible_admin` enthält «API & Schnittstellen». Korrektur: Capability `api.keys.manage`; Sichtbarkeit wie heute (always-visible im Nav, 403 serverseitig) oder Abweichung ausdrücklich als Entscheidungsoption, nicht als Bestand.

docs/design/2026-09-11-admin-shell-navigation-spec.md:101 MITTEL §2.5 behauptet `.container-xl` = «1200 px in Standard-Bootstrap». Installiertes Tabler 1.5.0: `max-width: 1140px` ab 1200 px Viewport, `max-width: 1320px` ab 1400 px (`tabler.min.css`). `admin-tabler.css` setzt nur `max-width: none` bei `data-content-width="full"`. Korrektur: 1140/1320 dokumentieren, nicht 1200.

docs/design/2026-09-11-admin-shell-navigation-spec.md:332 MITTEL Primärbutton «Veröffentlichen». Heute `cafeteria.html:59` und `patienten.html:57`: «Publizieren»; Modal «Woche publizieren». `design-reference-0911.md:34` führt Publizieren vs Veröffentlichen als offenen Konflikt. Korrektur: «Publizieren» behalten oder Umbenennung in §9.1 als Option, nicht stillschweigend.

docs/design/2026-09-11-admin-shell-navigation-spec.md:300 MITTEL Referenz-H1 weichen von den Templates ab und sind nicht als Optionen markiert: «Menüsammlung Cafeteria/Patienten» statt `page_header('Menüs')` (`menu_collection.html:7`); «Neue Komponente anlegen» — es gibt keine Create-Seite, nur Inline «Neue Komponente» in `components.html:26`; «Darstellungseinstellungen» statt `page_header('Design & Marke')` (`display_settings.html:5`); «Cafeteria-Wochenplan bearbeiten» statt «Cafeteria-Plan bearbeiten» (`cafeteria.html:23`); «Patienten-Wochenplan bearbeiten» statt «Patientenplan bearbeiten» (`patienten.html:21`). Korrektur: wörtliche heutige H1, Umbenennung nur in §9.

docs/design/2026-09-11-admin-shell-navigation-spec.md:327 MITTEL Wochenkopf erfindet `week_start`/`week_end` (in `cafeteria.html` nicht vorhanden) und zieht «Vorschau» plus Publish in den Seitenkopf. Heute im Header nur «Wochenangaben prüfen» (`cafeteria.html:27`); Publish/Vorschau/«Vorwoche kopieren» liegen in `.admin-actions` (`cafeteria.html:58–61`). «Vorwoche kopieren» fehlt in §7.2. Korrektur: Aktionen am heutigen Ort belassen oder Umzug als Option; Beschreibung aus `iso_week`, `area_names`, `cells|length` ableiten.

docs/design/2026-09-11-admin-shell-navigation-spec.md:322 MITTEL Breadcrumb `System` > `Design & Marke` für Darstellung: «System» ist nur Nav-Gruppe, kein registrierter Endpunkt. Master §7: kein erfundener Breadcrumb-Zielpfad. Korrektur: Breadcrumb nur mit echtem Elternpfad (`/admin/design/marke`) oder weglassen.

docs/design/2026-09-11-admin-shell-navigation-spec.md:313 MITTEL Revisionsbeschreibung «vom {{ revision.created_at.strftime('%d.%m.%Y') }}» steht so nicht im Template; dort `revision.created_at.isoformat()` (`rezepte_revision.html:12`). `yield=calculated.target` existiert (`rezepte_revision.html:10`) und ist nicht erfunden. Korrektur: Datumsformat aus dem Template bzw. bestehender Anzeige, kein neues strftime.

docs/design/2026-09-11-admin-shell-navigation-spec.md:193 MITTEL Nav-Mindesthöhe 44 px. Heute `.nav-link` `min-height: 48px` (`admin-tabler.css:36`); Icon-Manifest §5 und §8: 48 px Projektstandard; SDD §5: bestehende grössere Ziele nicht künstlich verkleinern. Master erlaubt ≥ 44 px, senkt aber nicht. Korrektur: 48 px als Untergrenze der bestehenden Shell beibehalten; 44 px nur als Master-Minimum nennen.

docs/design/2026-09-11-admin-shell-navigation-spec.md:232 MITTEL Disabled-Nav (`opacity: 0.5`, `aria-disabled`) existiert in der heutigen Sidebar nicht; unberechtigte Einträge werden weggelassen. Korrektur: Disabled-Zustand streichen oder als Nicht-Ziel markieren.

docs/design/2026-09-11-admin-shell-navigation-spec.md:457 MITTEL §10.2 gibt `admin-tabler.css` an MP-UI-SHELL. Dieselbe Datei ist `owned_files` von MP-UI-TOKENS (`surfaces-wps.json:209`). Sequenz TOKENS→SHELL ist genannt, die Schnittmenge (welche CSS-Regeln SHELL nach Freeze noch anfassen darf) fehlt. Korrektur: SHELL auf Nav/Breakpoint/Layout-Selektoren begrenzen; Token-/Farbregeln bei TOKENS lassen.

docs/design/2026-09-11-admin-shell-navigation-spec.md:168 NIEDRIG `user_initials` ist kein heutiges Templatefeld; Ist-Stand `user_name[:2]|upper` (`_workflow_sidebar.html:55`). Korrektur: bestehende Ableitung verwenden.

docs/design/2026-09-11-admin-shell-navigation-spec.md:150 NIEDRIG Footer-Trennlinie `1px solid var(--app-border)` (helles `#E5E7EB`) auf Petrol-Sidebar. Alternative `--app-sidebar-hover` ist genannt, die Erstwahl ist falsch. Korrektur: nur Sidebar-Tokens.

docs/design/2026-09-11-admin-shell-navigation-spec.md:261 NIEDRIG Mobiles Offcanvas: Fokus auf erstes Element, Escape, Rückkehr spezifiziert; Fokusfalle fehlt. Ist-Befund §2.4 hatte Trap-Focus als Lücke, Zielvertrag schliesst sie nicht. Korrektur: Fokus innerhalb des offenen Menüs halten, bis es schliesst.

---

## Was hält

- Alle 14 heutigen Nav-Einträge plus Abmelden sind vorhanden, Endpunkte registriert, keine erfundenen Menüpunkte. Gruppen folgen dem Auftrag (Arbeitsbereich / Rezepte / Ausgabe / Daten & Schnittstellen / System). Umbenennungen in §9.1 sind als Optionen markiert.
- Master-Masse 248 / ≥44 / 20 / 12 / 8 px, Gruppentitel 12 px/600/Kapitälchen, `--app-sidebar-indicator`, `aria-current="page"`, Breakpoint 992 als Annahme, keine leere Topbar, keine globale Suche/Kennzahlen.
- Layoutvarianten: genau 41 visuelle `admin_tabler`-Routen, 1:1 zur Matrix; Zuordnungen plausibel (Wochen `full`, Listen 1440, Formulare 960). `print_template_editor` ist `layout_variant: print` und zu Recht nicht in der 41.
- Skip-Link existiert bereits (`base_tabler.html:20`) und steht im Prüfplan. Keine Nur-Hover-Bedienung.
- Anschluss MP-UI-SHELL: `base_tabler.html`, `_workflow_sidebar.html`, `admin-tabler.css` sind die owned_files; Makros/Tokens/Formulare sind abgegrenzt.
- Icon-Doppelbelegungen §2.3: 6 Paare, 12 von 14, gegen `_workflow_sidebar.html` 63–106 korrekt.
- `yield=calculated.target` ist Templatebestand, kein erfundenes Query.

---

## Verdachtspunkte a–i

a) bestätigt — §7.1:282 setzt Georgia fest; K1 bleibt bei MP-UI-BRAND-DECISION (`ui-route-matrix.json` `common.fonts.conflict`, `design-reference-0911.md:32`).

b) bestätigt — alle 11 vorgeschlagenen IDs fehlen in Sprite und `tabler.lock.json` `icons[]`; nur die heutigen Namen (`calendar-week`, `calendar-cog`, `tools-kitchen-2`, `components`, `copy`, `file-import`, `eye`, `info-circle`, `logout`) sind vorhanden. Master §4.1 / Manifest §4 verletzt.

c) bestätigt — `MP-UI-PUBLIC-VIEWS` und `MP-UI-SIGNAGE` existieren nicht in `surfaces-wps.json`. Echte IDs: `MP-UI-SPECIAL-OUTPUTS`, `MP-UI-OUTPUT-HUBS`, `MP-QA-PUBLIC-RUNTIME` (und `MP-UI-PUBLIC-WHITE-POLISH` für die Weiss-Politur).

d) bestätigt — `#F3A6C0/#31585B` = 4.12:1, nicht ~6.1:1. Auftrag verlangte Tokennamen; §5.4 liefert Hex. Übrige Paare grob in der Grössenordnung, Zahlen ungenau.

e) bestätigt — `overflow-x: hidden` auf Body/Shell (§6.2:274) kaschiert Überlauf. Master §10 / SDD §5: Layout ohne Dokument-Overflow, lokale Tabellenscrollregion erlaubt.

f) bestätigt — Matrix `admin.api_overview.capability` = `api.keys.manage`, nicht `users.manage`. Sidebar/always_visible zeigt den Eintrag heute allen Admin-Rollen.

g) bestätigt — kein 1200-px-`container-xl`. Tabler: 1140 px (≥1200 Viewport), 1320 px (≥1400). Spec-Zahl falsch.

h) bestätigt — stillschweigende Umbenennung «Publizieren» → «Veröffentlichen» (`cafeteria.html:59`, `patienten.html:57`; Konflikt in `design-reference-0911.md:34`).

i) bestätigt — 12 von 14 Doppelbelegungen stimmen gegen `_workflow_sidebar.html` 63–106: `calendar-cog`×2, `tools-kitchen-2`×2, `components`×2, `copy`×2, `eye`×2, `info-circle`×2; eigenständig `calendar-week`, `file-import`.

WAVE-REVIEW: FINDINGS (19)
