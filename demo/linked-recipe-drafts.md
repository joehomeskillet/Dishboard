# Verknüpfte Rezeptentwürfe für die vorhandenen Gerichte

`linked_recipe_drafts.json` bereitet **alle 32 vorhandenen Gerichtstitel** vor:
18 überarbeitete Beispielansätze und 14 ergänzte Vorschläge. Dazu kommen
29 Zubereitungsrezepte und insgesamt 100 Foods. Die 76 aufgezeichneten
Menüvorkommen und 37 Komponenten bleiben mit exakten Titeln, Profilen und
Beilagentexten nachvollziehbar zugeordnet.

**Das ist ein symbolischer, ungeprüfter Datensatz zur fachlichen Durchsicht,
kein ausführbares Importformat.** Es wurden keine Rezepte, Lagerorte, Menüs,
Wochen, Publikationen oder Bestände in eine Datenbank geschrieben. Der spätere
Writer und der Vertrag für vorbereitete Zutaten sind getrennte Arbeiten.

## Herkunft und Prüfstatus

Die Titel, Profile und Beilagen stammen aus dem schreibgeschützten Capture
vom 8. September 2026, 21:51:49 UTC, auf Produktstand
`693eb74f1a54bd97616dbfc8e0f90bdc1197f508`, Schema 25. Der Capture enthielt
keine Foods, Rezepte oder Lagerorte. Seine Hashreferenz steht in `meta`.

Alle 54 Food-Identitäten und 18 Rezeptansätze aus `demo/recipe_examples.json`
werden mit ihren ursprünglichen Beispielschlüsseln referenziert. Die alte
Datei bleibt unverändert. Ihre Herkunft `manual` bezeichnet erfasste
**Beispieldaten**, keine nachgewiesene Küchenrezeptur. Die neuen und angepassten
Entwürfe sind deshalb `ai_assisted`, `unreviewed` und bei Allergenen
`not_checked`. Originale Zutatenzeilen sind je altem Rezept entweder mit
unveränderter Menge/Einheit erhalten oder ausdrücklich als ersetzt aufgelistet.

Die vorhandenen Snapshot-Kennzeichnungen werden als beobachtete Quelle
festgehalten. Nur vegetarische/vegane Rezepturabsichten werden übernommen und
über sämtliche Subrezepte auf bekannte tierische Zutaten geprüft. Das ist keine
Allergenfreigabe, Produktzertifizierung oder Prüfung von Kreuzkontamination.
`LACTOSE_FREE`, leere Allergenlisten und alte `checked`-Flags werden nicht als
Rezeptfreigabe übernommen. Für vegetarische Käsegerichte bleibt die Auswahl
eines geeigneten Produkts mit vegetarischem Lab ausdrücklich zu prüfen.

## Verknüpfungen und Mengen

- `foods[].key` und `recipes[].key` sind symbolische `draft.*`-Schlüssel.
  Es werden keine neuen Datenbank-UUIDs erfunden. UUIDs in
  `dish_mappings[].source_occurrences` und `source_components` sind unveränderte
  Herkunftsreferenzen vorhandener Datensätze, keine Importanweisungen.
- Ein vorbereitetes Food nennt `preparation_recipe_key`. Beispielsweise
  verwendet Hummus das Rezept für gekochte Kichererbsen; der Falafel-Teller
  verwendet Hummus, Falafel und Ofengemüse als vorbereitete Zutaten.
- Jedes Hauptgericht ergibt vorgeschlagene **20 PORTION**. Vorbereitete
  Rezepte erklären ihre eigene Ausbeute in G oder ML. Beispiel: 800 G Hummus
  werden durch eine Rezeptur mit einer vorgeschlagenen Ausbeute von 800 G
  abgebildet. 400 G davon entsprächen innerhalb dieser Rezeptur dem Faktor 0,5.
- Alle Mengen sind positive Dezimalstrings. Die neun Einheiten sind lediglich
  Referenzen auf vorhandene Grundlagen: G, KG, ML, L, TL, EL, STK, PORTION, PRISE.
  Es gibt keine Annahme über Dichte, Stückgewicht oder PORTION→KG. Die
  vorgeschlagenen gekochten Ausbeuten sind keine gemessenen Umrechnungsfaktoren.
  Bei der Küchenprüfung müssen fertiges Gewicht/Volumen und Portionierung
  gemessen und bei Bedarf korrigiert werden.
- Die reale Beilage steht pro Gericht genau einmal als markierte Zutatenzeile.
  Ihre Rohzutaten liegen im zugehörigen Zubereitungsrezept. Salz, Fett oder
  Zwiebeln können sachlich sowohl im Hauptgericht als auch in einer separaten
  Sauce vorkommen; die neue Zubereitung ist eine ausdrücklich ungeprüfte
  Anpassung, keine Behauptung unveränderter Gesamtnährwerte oder Gesamtmengen.
- Kochwasser zum Abgiessen, Waschen und Dämpfen ist Prozesswasser. Mengen für
  absorbiertes Wasser oder Bouillon sind explizit aufgeführt. Daraus entstehen
  keine Bestände oder Lagerbewegungen.

Ein späterer Import muss symbolische Referenzen erst nach fachlicher Freigabe
auf echte, am selben Standort gültige Foods und ausgewählte unveränderliche
Rezeptrevisionen auflösen. Die vorhandenen Snapshotbytes dürfen dabei nicht
nachträglich verändert werden. Dieser Datensatz setzt keinen neuen
Schema-/Snapshotvertrag eigenständig fest.

## Lagerorte als bearbeitbarer Vorschlag

Jedes Food besitzt mindestens einen vorgeschlagenen Lagerort. **Trockenlager,
Kühlraum und Tiefkühler sind noch nicht vom Nutzer bestätigte Vorschläge**;
`status=proposed`, `editable=true` und `storage_status=proposed_editable` machen
das ausdrücklich sichtbar. Der Standortbetrieb und konkrete Produktzustand
können andere Zuordnungen benötigen. Die Zuordnung ist keine Lagerungs- oder
Haltbarkeitsfreigabe. Es werden keine Mengenbestände, Chargen, Herstellungsdaten,
Haltbarkeiten, Temperaturvorgaben oder Verfalldaten erfunden.

## Bewusste Korrekturen der Beispiele

- Falafel-Teller: Die zusätzlichen 200 G Kichererbsen neben schon vorhandenen
  800 G Hummus entfallen. Hummus wird einmal über sein Zubereitungsrezept gezählt.
- Gemüsegeschnetzeltes: Die bisher im Hauptteil geführten 1600 G Zucchetti
  werden der tatsächlich ausgeschriebenen separaten Beilage zugeordnet.
- Beide Griessbreie: Zwetschgen und Kompottzucker liegen ausschliesslich im
  gemeinsamen Kompottrezept; das Hauptgericht enthält eine Kompottzeile.
- Rüebli und Karotten verweisen bewusst auf denselben vorgeschlagenen
  zubereiteten Foodkey. Ihre tatsächlichen Menübezeichnungen bleiben erhalten.
- Kichererbsen sind als gekocht und abgetropft präzisiert. Die neue trockene
  Zutat ist getrennt; die Kochrezeptur erklärt eine ungeprüfte vorgeschlagene
  Ausbeute und verlangt deren Messung als künftigen Prüfschritt.

## Offline-Prüfung

Der eigene private Validator `.claude/validate_linked_drafts.py` prüft
Quellhashes, vollständige Titel-/Vorkommens-/Komponentenzuordnung, bestehende
Einheiten, Dezimalgrenzen mit `cafeteria.quantities`, Lagerreferenzen,
kompatible Ausbeuten, Zutatenreferenzen, direkte/indirekte Zyklen, einmalige
Beilagen, erhaltene Beispielmengen und verschachtelte Ernährungsabsichten.
`.claude/test_linked_drafts.py` prüft auch gezielt beschädigte Daten.
Beide arbeiten ausschliesslich mit Dateien; sie sind kein Produktimporter.

## Vollständige Gerichtsliste

| Gericht | Tatsächliche Profile | Tatsächliche Beilagen | Rezeptkey |
| --- | --- | --- | --- |
| Bündner Gerstensuppe | patient | Hausbrot | draft.recipe.buendner-gerstensuppe |
| Falafel-Teller | patient, staff_guest | Hummus, Ofengemüse | draft.recipe.falafel-teller |
| Gebratenes Zanderfilet | patient, staff_guest | Salzkartoffeln, Rahmspinat | draft.recipe.zanderfilet |
| Gemüse-Gerstensuppe | patient | Hausbrot | draft.recipe.gemuese-gerstensuppe |
| Gemüse-Lasagne | patient, staff_guest | Blattsalat | draft.recipe.gemuese-lasagne |
| Gemüse-Pastetli | patient | Erbsen und Rüebli, Blattsalat | draft.recipe.gemuese-pastetli |
| Gemüse-Toast | patient | Tomatensalat | draft.recipe.gemuese-toast |
| Gemüsegeschnetzeltes | patient | Reis, Zucchetti | draft.recipe.gemuesegeschnetzeltes |
| Griessbrei mit Zwetschgenkompott | patient | Zwetschgenkompott | draft.recipe.griessbrei-zwetschgen |
| Hackbraten an Rosmarinjus | patient | Kartoffelgratin, Broccoli | draft.recipe.hackbraten-rosmarinjus |
| Kalbsbratwurst mit Zwiebelsauce | patient, staff_guest | Rösti, Rüebli | draft.recipe.kalbsbratwurst-zwiebelsauce |
| Kartoffelsuppe mit Kräutern | patient | Hausbrot | draft.recipe.kartoffelsuppe-kraeuter |
| Kartoffelsuppe mit Wienerli | patient | Hausbrot | draft.recipe.kartoffelsuppe-wienerli |
| Kichererbsen-Curry | staff_guest | Basmatireis, Broccoli | draft.recipe.kichererbsen-curry |
| Kichererbsen-Eintopf | patient | Kartoffelwedges, Marktgemüse | draft.recipe.kichererbsen-eintopf |
| Kokos-Griessbrei | patient | Zwetschgenkompott | draft.recipe.kokos-griessbrei |
| Linsenbraten | patient | Kartoffelgratin, Broccoli | draft.recipe.linsenbraten |
| Nussbraten mit Kräutersauce | patient | Kartoffelstock, Karotten | draft.recipe.nussbraten-kraeuter |
| Ofen-Pouletschenkel | patient | Kartoffelwedges, Marktgemüse | draft.recipe.pouletschenkel-ofen |
| Pastetli mit Brätkügeli | patient | Erbsen und Rüebli, Blattsalat | draft.recipe.pastetli-braetkuegeli |
| Polenta mit Pilzragout | patient, staff_guest | Bohnen | draft.recipe.polenta-pilzragout |
| Pouletbrust an Kräutersauce | staff_guest | Kartoffelstock, Zucchetti | draft.recipe.pouletbrust-kraeuter |
| Pouletgeschnetzeltes Paprika | patient | Reis, Zucchetti | draft.recipe.pouletgeschnetzeltes-paprika |
| Rindsgeschnetzeltes Stroganoff | staff_guest | Basmatireis, Broccoli | draft.recipe.rindsgeschnetzeltes-stroganoff |
| Rindsschmorbraten | patient | Kartoffelstock, Karotten | draft.recipe.rindsschmorbraten |
| Rührei mit Kräutern | patient | Salzkartoffeln, Spinat | draft.recipe.ruehrei-kraeuter |
| Schinken-Käse-Toast | patient | Tomatensalat | draft.recipe.schinken-kaese-toast |
| Schweinsragout Tessiner Art | patient, staff_guest | Polenta, Bohnen | draft.recipe.schweinsragout-tessin |
| Spinat-Ricotta-Ravioli | staff_guest | Tomatensauce, Blattsalat | draft.recipe.spinat-ricotta-ravioli |
| Tofu-Rührei | patient | Salzkartoffeln, Spinat | draft.recipe.tofu-ruehrei |
| Älplermagronen mit Speck | patient | Apfelmus | draft.recipe.aelplermagronen-speck |
| Älplermagronen vegetarisch | patient | Apfelmus | draft.recipe.aelplermagronen-vegetarisch |
