# Fachsymbole: lokale Assetbasis

Stand 07.09.2026. Lokale Symbole für die gemeinsamen Menümetadaten, Legenden und Wochen-PDFs. Die SVGs sind unveränderte Quelldateien; keine Frei-von-Varianten und keine Tabler-Schraubenmutter als Lebensmittelsymbol.

| Quelle | Pin | Lizenz |
|---|---|---|
| [Erudus/erudus-icons](https://github.com/Erudus/erudus-icons/tree/7e25e14a09b1aa0af4f85dc69ebfb03ff99480b7/src/svg) | Commit `7e25e14a09b1aa0af4f85dc69ebfb03ff99480b7` | MIT, [vollständiger Text](licenses/erudus-LICENSE) |
| [lipis/flag-icons](https://github.com/lipis/flag-icons/tree/7aa5b2bdddd570ece62c812c0cb588ccdc099e2e/flags/4x3) | Version 7.5.0, Commit `7aa5b2bdddd570ece62c812c0cb588ccdc099e2e` | MIT, [vollständiger Text](licenses/flag-icons-LICENSE) |
| [Tabler Icons](https://github.com/tabler/tabler-icons/tree/v3.46.0/icons/outline) | `@tabler/icons` 3.46.0, identisches Archiv wie `../tabler.lock.json` | MIT, [vollständiger Text](licenses/tabler-icons-LICENSE) |

[manifest.json](manifest.json) enthält alle 14 bestehenden Allergen-Codes mit den deutschen Seed-Namen und EU-Nummern sowie exakt die 249 Länder der vorhandenen deutschen Auswahl. Länder-Codes und -Namen bleiben unverändert. Jede Zuordnung referenziert eine lokale Datei; `files` bindet SHA-256 und exaktes Archivmitglied, `sources` die Commit-URL, Version, Archiv-Prüfsumme und Lizenz. Deutsche Ländernamen stammen unverändert aus der bereits dokumentierten iso-codes-Auswahl, siehe `docs/design/country-select-source.md` im Projekt.

Textfallback: bei Allergenen der vorhandene deutsche Name, bei Ländern das bestehende ISO-Kürzel zusätzlich zum Ländernamen. Fehlende Zuordnungen oder nicht erfasste Herkunft bleiben ohne erfundene Grafik. Ein Icon trifft keine Aussage darüber, ob ein Menü ein Allergen enthält; enthalten, mögliche Spuren und nicht erfasst bleiben Fachzustände der späteren Verbraucher. Keine Frei-von-Aussage aus fehlenden Daten.

## Reproduzieren und prüfen

Die getrennte Gruppe `labels` enthält ausschliesslich `VEGETARIAN` → `labels/leaf.svg` (Vegetarisch) und `VEGAN` → `labels/plant.svg` (Vegan). Sie stammen aus `package/icons/outline/` des gepinnten offiziellen npm-Archivs. Die vollständigen Namen bleiben sichtbar. Weder Menüslot `VEGGIE`, Gerichtstext, Zutaten noch ein anderes Label erzeugen eine Deklaration. Unbekannte Labels, `LACTOSE_FREE` und `GLUTEN_FREE` bleiben Text; die bestehenden Allergen-/Presence-/Prüfstatus-Verträge bleiben erhalten. Der Admin-Sprite wird für diese eigenständigen SVG-Bilder nicht benötigt und bleibt unverändert.

Vom Repositoryroot, ohne Paketinstallation:

```bash
rtk python3 tools/vendor_food_symbols.py --verify
rtk python3 tools/vendor_food_symbols.py --build
```

`--verify` prüft offline Hashes, SVG-Struktur, Vollständigkeit, tatsächliche Fach-/Ländercodes und den PDF-Prüfbericht. `--build` lädt die beiden HTTPS-Archive von GitHub und das bereits gepinnte offizielle Tabler-npm-Archiv, prüft sie vor dem Kopieren und übernimmt ausschliesslich festgelegte normale Dateien. Die vorhandenen sicheren Datei-/Hash-/Quellhelfer aus `vendor_tabler.py` werden wiederverwendet; bestehende Tabler-Assets bleiben unverändert. Mit `--cache-dir <dir>` werden vorhandene Archive (`erudus.tar.gz`, `flags.tar.gz`, `tabler-icons.tgz`) nach Hashprüfung genutzt; mit `--output-dir <dir>` lässt sich eine getrennte Reproduktion vergleichen. Das Manifest wird nicht automatisch neu vertraut oder überschrieben.

## Tatsächliche SVG-/PDF-Grenze

Der Volltest mit **fpdf2 2.8.8** hat alle 265 SVGs ausgeführt. **14 Allergensymbole, 228 Flaggen und beide Kostformsymbole** lassen sich ohne Rendererwarnung erzeugen. **21 Flaggen benötigen vor einer PDF-Einbindung Konvertierung oder den Länder-Textfallback:** AI, AR, BZ, BI, KY, FK, GD, GT, HT, KG, HR, MX, NI, RS, GS, LK, TW, TN, TC, UM, US. Davon verursachen 13 einen Fehler; acht weitere melden nicht unterstützte oder übersprungene SVG-Teile. Die Dateien bleiben vollständig erhalten. [pdf-compatibility.json](pdf-compatibility.json) dokumentiert jeden Code mit konkretem Fehler-/Warntext und wird über das Manifest gehasht. Die bisherigen Befunde bleiben als ursprünglicher Beleg erhalten; die zwei neuen Labelbefunde wurden nach echtem SVG-Rendern ergänzt.

Warnungsfreies Rendern ist keine endgültige visuelle Freigabe. Insbesondere kleine Flaggen mit Wappen, Symbole in Schwarzweiss sowie Gerätelesbarkeit und endgültige Druckgrösse müssen beim Verbraucher geprüft werden. Die Anforderungen gelten auch bei einer späteren fpdf2-Aktualisierung; Warnungen dürfen nicht ignoriert werden. Keine Rasterizer-Dependency wurde eingeführt.

```bash
rtk python3 tools/vendor_food_symbols.py --pdf-check --artifact-dir .claude/artifacts/food-symbols
```

Dieser zusätzliche Prüfmodus benötigt das bereits im Projekt vorhandene fpdf2 2.8.8 und den lokalen Carlito-Font. Er erzeugt einen vollständigen JSON-Bericht und einen fünfseitigen Kontaktbogen einschliesslich Kostformlabels. Problematische Flaggen werden dort ausdrücklich mit Konvertierungshinweis und Code dargestellt. Der Kontaktbogen ist ein technisches Prüfarbeitsblatt, keine öffentliche Vorlage. Kontaktbogen, PNGs und Quelldownloads liegen im privaten Artefaktverzeichnis des jeweiligen Worktrees; der vollständige maschinenlesbare PDF-Befund ist zusätzlich hier versioniert.
