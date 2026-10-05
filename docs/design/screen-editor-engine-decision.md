# Screen-Editor-Engine — begründete Technologieentscheidung

Stand: 9. September 2026. Paket `MP-SCR-EDITOR-DECISION`. **Keine Produktdependency, keine Editorfreigabe, kein produktiver Canvas.**

Übernahme am 5. Oktober 2026: Der Technologievergleich bleibt datiert. Das aktuelle
Produkt verwendet die feste `REGISTRY` in `cafeteria/screen_templates.py` und
direkte Symbolaktionen. Die damaligen Prototypen und ein neuer Blockparser werden
nicht übernommen. Aktuelle UI-DELTA- und Direktaktionsverträge haben Vorrang.

## Entscheidung

**Native Lösung: vorhandenes `@tabler/core` 1.5.0 plus Tabler Icons 3.46.0** (MIT, lokal gepinnt in `reference_scaffold/cafeteria/static/vendor/tabler.lock.json`). Bedienung ist ein Flask/Jinja-Formular mit Allowlist-Blöcken und Reihenfolge (nach oben/unten), nicht ein freier Zeichen-Canvas.

| Alternative | Version/Lizenz laut Entwurf 5. September 2026 | Warum nicht |
|---|---|---|
| GrapesJS Core | 0.23.6, BSD-3-Clause | Speichert HTML/CSS; Bindungsvertrag verbietet HTML/JS/CSS/URLs/Ausdrücke. Admin-CSP ist `script-src 'self'; style-src 'self'` ohne `unsafe-eval`/`unsafe-inline` für Scripts. Tabler-Gate (alle Werkzeugleisten als Tabler) nicht nachgewiesen. Zweite Adminoberfläche. |
| Puck | 0.23.0, MIT | React-Renderer; kein React im Produkt. Jinja-Kompatibilität entsteht nicht. Tabler-Gate und Samsung-Touch nicht nachgewiesen. |
| pdfme / ReportBro | Screen-fremd bzw. AGPL | Gehören zum Druckslice, nicht zu SCR-003. |

Vorhandene Bibliotheken zuerst. Kostenpflichtige Studio-SDK und zweite Adminoberfläche bleiben ausgeschlossen.

## Keyboard / Touch / Undo / NoJS

Am Pflichtumfang Titel, Logo, Menüblock:

| Aktion | Native Umsetzung |
|---|---|
| Tastatur | Sichtbare Labels, `select`/`button`, Tab-Reihenfolge, Enter sendet das Formular |
| Touch | Gemeinsame Tabler-Komponenten; Symbolaktionen 36 px bei feinem, mindestens 44 px bei grobem Zeiger |
| Undo | Formular «Rückgängig» lädt die letzte unveränderte Revision; kein Editor-Stack in JS |
| NoJS | GET/POST-Formulare; `noscript`-Hinweis; Anordnen über Submit `move` |

Der damalige isolierte Prototyp bleibt auf Quellcommit
`7b5ce49741574c7ba2ed22e393e325b670700a4d`; er ist kein Produktnachweis.

## Damaliger Parservorschlag (nicht implementierter Produktvertrag)

Normalisiertes JSON, höchstens **64 Blöcke**, **256 KiB**, **Tiefe 8**. Zulässige Typen: Logo, Titel, Datum/Uhr, Servicezeit/Hinweis, Menügruppe, Menüfoto, Komponenten, Herkunft, Allergene/Labels, Legende. Bindungen sind **feste IDs** aus der Allowlist, keine Ausdrücke.

Pflichtblöcke Logo, Titel, Menügruppe sind nicht löschbar. Patient verweigert Preisbindungen im Parser. Public-Vorschau enthält keine Admin-/Actor-/CSRF-Felder; sie liest nur veröffentlichte Snapshotfelder.

Diese Grenzen dokumentieren den damaligen Vorschlag. Für aktuelle Vorlagen gelten
die bestehenden Validatoren und die feste Registry; dieses Dokument gibt weder
einen neuen JSON-Vertrag noch ein Folgepaket zur Implementierung frei.

## Grenze

Dieser Freeze installiert nichts, ändert kein CSP und gibt keinen produktiven Editor frei. Ein nicht funktionsfähiger Canvas bleibt unzulässig.
