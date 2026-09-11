"""Authoring helper: creates review data only; no runtime importer or database access."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
CAPTURE = ROOT.parent / 'sdd-bindings-root-0908/.claude/live-dish-source-0908.json'
EXAMPLES = ROOT / 'demo/recipe_examples.json'
live = json.loads(CAPTURE.read_text())
examples = json.loads(EXAMPLES.read_text())
foods: dict[str, dict[str, Any]] = {}
recipes: dict[str, dict[str, Any]] = {}


def source(legacy: str | None = None) -> dict[str, Any]:
    value: dict[str, Any] = {'kind': 'ai_assisted', 'note': 'Ungeprüfter Küchenvorschlag; keine tatsächliche Küchenrezeptur oder Allergenfreigabe.'}
    if legacy:
        value['legacy_example'] = {'file': 'demo/recipe_examples.json', 'key': legacy, 'declared_kind': 'manual', 'status': 'example_only_not_kitchen_verified'}
    return value


def food(key: str, name: str, unit: str = 'G', storage: str = 'kuehlraum', groups: str = '', legacy: str | None = None) -> None:
    foods[key] = {'key': 'draft.food.' + key, 'name': name, 'base_unit_code': unit,
                  'storage_keys': ['proposed.storage.' + storage], 'storage_status': 'proposed_editable',
                  'culinary_groups': groups.split(), 'source': source(legacy), 'review_status': 'unreviewed', 'allergen_review_status': 'not_checked'}


DRY = {'kartoffeln', 'zwiebel', 'knoblauch', 'salz', 'pfeffer', 'currypulver', 'paprikapulver', 'basmatireis', 'reis', 'polenta', 'weizengriess', 'lasagneplatten', 'passata', 'olivenoel', 'rapsoel', 'kokosmilch', 'weisswein', 'zucker', 'zimt', 'hausbrot', 'muskat', 'wasser'}
for old in examples['foods']:
    key = old['key'].removeprefix('example.food.')
    groups = ' '.join(t.rsplit('.', 1)[-1] for t in old['tag_keys'] if t.rsplit('.', 1)[-1] in {'MEAT', 'FISH', 'DAIRY', 'EGG'})
    food(key, old['name'], old['base_unit_code'], 'trockenlager' if key in DRY else 'kuehlraum', groups, old['key'])
foods['kichererbsen']['name'] = 'Kichererbsen, gekocht und abgetropft'
foods['kichererbsen']['source']['note'] += ' Zustand aus den bisherigen Zutatenzeilen präzisiert; keine Trocken-/Kochgewichts-Gleichsetzung.'
foods['hartkaese']['source']['note'] += ' Für vegetarische Gerichte Produkt mit vegetarischem Lab auswählen und prüfen.'
for row in [
    ('tomaten', 'Tomaten', 'G', 'kuehlraum', ''), ('essig', 'Apfelessig', 'ML', 'trockenlager', ''),
    ('schinken', 'Kochschinken', 'G', 'kuehlraum', 'MEAT'), ('speck', 'Speckwürfel', 'G', 'kuehlraum', 'MEAT'),
    ('hackfleisch', 'Rindshackfleisch', 'G', 'kuehlraum', 'MEAT'), ('linsen', 'Braune Linsen, trocken', 'G', 'trockenlager', ''),
    ('haferflocken', 'Haferflocken', 'G', 'trockenlager', ''), ('senf', 'Senf', 'G', 'kuehlraum', ''),
    ('mehl', 'Weizenmehl', 'G', 'trockenlager', ''), ('magronen', 'Magronen, trocken', 'G', 'trockenlager', ''),
    ('aepfel', 'Äpfel', 'G', 'kuehlraum', ''), ('pouletschenkel', 'Pouletschenkel', 'STK', 'kuehlraum', 'MEAT'),
    ('rollgerste', 'Rollgerste', 'G', 'trockenlager', ''), ('lauch', 'Lauch', 'G', 'kuehlraum', ''),
    ('sellerie', 'Knollensellerie', 'G', 'kuehlraum', ''), ('rindbraten', 'Rindsschmorbraten, roh', 'G', 'kuehlraum', 'MEAT'),
    ('nuesse', 'Baumnüsse, geschält', 'G', 'trockenlager', ''), ('braetkuegeli', 'Brätkügeli', 'G', 'kuehlraum', 'MEAT'),
    ('pastetli', 'Blätterteigpastetli', 'STK', 'trockenlager', 'DAIRY'), ('tahini', 'Tahini', 'G', 'trockenlager', ''),
    ('zitronensaft', 'Zitronensaft', 'ML', 'kuehlraum', ''), ('hefe', 'Trockenhefe', 'G', 'trockenlager', ''),
    ('kichererbsen-trocken', 'Kichererbsen, trocken', 'G', 'trockenlager', ''), ('erbsen-tk', 'Erbsen, tiefgekühlt', 'G', 'tiefkuehler', ''),
]:
    food(*row)


def ingredients(spec: str) -> list[dict[str, Any]]:
    return [{'food_key': 'draft.food.' + k, 'quantity': q, 'unit_code': u} for k, q, u in (line.split(':') for line in spec.split(';'))]


def recipe(key: str, title: str, quantity: str, unit: str, spec: str, steps: list[str], role: str = 'preparation', legacy: str | None = None) -> dict[str, Any]:
    row = {'key': 'draft.recipe.' + key, 'title': title, 'role': role, 'yield_quantity': quantity, 'yield_unit_code': unit,
           'yield_status': 'proposed_not_measured', 'ingredients': ingredients(spec), 'steps': steps,
           'source': source(legacy), 'review_status': 'unreviewed', 'allergen_review_status': 'not_checked', 'proposed_dietary_labels': []}
    recipes[key] = row
    return row


def prep(key: str, title: str, quantity: str, unit: str, spec: str, method: str, food_key: str | None = None) -> None:
    fk = food_key or key
    recipe(key, title, quantity, unit, spec, [method, 'Fertige Ausbeute in der angegebenen Einheit messen; Vorschlagsmenge vor Küchenfreigabe berichtigen.'])
    if fk not in foods:
        food(fk, title + ', zubereitet', unit)
    foods[fk]['preparation_recipe_key'] = 'draft.recipe.' + key


prep('kichererbsen-gekocht', 'Kichererbsen gekocht', '1800', 'G', 'kichererbsen-trocken:750:G;wasser:2500:ML', 'Kichererbsen einweichen, Einweichwasser abgiessen und in frischem angegebenem Wasser vollständig weich kochen; abtropfen lassen.', 'kichererbsen')
prep('gemuesebruehe', 'Gemüsebouillon', '3000', 'ML', 'rueebli:300:G;lauch:250:G;sellerie:200:G;zwiebel:150:G;wasser:3500:ML;salz:12:G', 'Gemüse schneiden, mit Wasser und Salz auskochen; durch ein Sieb abgiessen. Die Menge bezeichnet fertige, gesiebte Bouillon.')
prep('hummus', 'Hummus', '800', 'G', 'kichererbsen:600:G;tahini:80:G;zitronensaft:40:ML;olivenoel:30:ML;wasser:50:ML;knoblauch:5:G;salz:5:G', 'Gekochte Kichererbsen mit Tahini, Zitronensaft, Öl, Wasser, Knoblauch und Salz fein pürieren.')
prep('falafel', 'Falafel', '1600', 'G', 'kichererbsen:1300:G;zwiebel:150:G;knoblauch:15:G;kraeuter:40:G;mehl:100:G;rapsoel:80:ML;salz:10:G', 'Gekochte, gut abgetropfte Kichererbsen mit Zwiebel, Knoblauch und Kräutern zerkleinern; mit Mehl und Salz binden, formen und in Öl braten. Vorgeschlagene Variante mit gekochten Kichererbsen; Bindung praktisch prüfen.')
prep('roesti', 'Rösti', '2000', 'G', 'kartoffeln:2100:G;rapsoel:60:ML;salz:10:G', 'Kartoffeln vorgaren, schälen und raffeln; mit Salz und Öl portionsweise zu Rösti braten.')
prep('ofengemuese', 'Ofengemüse', '2000', 'G', 'zucchetti:900:G;rueebli:800:G;paprika:600:G;olivenoel:60:ML;salz:10:G', 'Gemüse schneiden, mit Öl und Salz mischen und im Ofen rösten.')
prep('hausbrot', 'Hausbrot', '1000', 'G', 'mehl:650:G;wasser:420:ML;hefe:7:G;salz:10:G', 'Mehl, Wasser, Hefe und Salz zu Teig kneten; gehen lassen, formen und backen. Scheiben nach Gewicht entnehmen.')
prep('kartoffelstock', 'Kartoffelstock', '3200', 'G', 'kartoffeln:3000:G;milch:400:ML;butter:80:G;salz:12:G;muskat:1:PRISE', 'Kartoffeln schälen, weich kochen, abgiessen und mit erwärmter Milch und Butter stampfen; würzen.')
prep('zucchetti-gegart', 'Zucchetti', '1500', 'G', 'zucchetti:1600:G;rapsoel:30:ML;salz:6:G', 'Zucchetti schneiden und in Öl garen, salzen.')
prep('broccoli-gegart', 'Broccoli', '1500', 'G', 'broccoli:1600:G;salz:6:G', 'Broccoli in Röschen teilen, dämpfen und salzen.')
prep('rueebli-gegart', 'Rüebli', '1500', 'G', 'rueebli:1600:G;rapsoel:20:ML;salz:6:G', 'Rüebli schälen und schneiden, dämpfen und mit Öl und Salz abschmecken.')
prep('bohnen-gegart', 'Bohnen', '1500', 'G', 'bohnen:1600:G;rapsoel:20:ML;salz:6:G', 'Bohnen rüsten, vollständig garen und mit Öl und Salz abschmecken.')
prep('blattsalat-angerichtet', 'Blattsalat', '900', 'G', 'blattsalat:800:G;olivenoel:50:ML;essig:30:ML;wasser:30:ML;salz:4:G', 'Salat waschen und abtropfen; aus Öl, Essig, Wasser und Salz Dressing rühren und erst zum Anrichten zugeben.')
prep('basmatireis-gekocht', 'Basmatireis', '2800', 'G', 'basmatireis:1000:G;wasser:2000:ML;salz:8:G', 'Reis waschen und mit angegebenem Wasser und Salz quellen lassen; fertiges Gewicht kontrollieren.')
prep('reis-gekocht', 'Reis', '2800', 'G', 'reis:1000:G;wasser:2000:ML;salz:8:G', 'Reis waschen und mit angegebenem Wasser und Salz quellen lassen; fertiges Gewicht kontrollieren.')
prep('polenta-gekocht', 'Polenta', '3000', 'G', 'polenta:800:G;wasser:2500:ML;salz:10:G;olivenoel:30:ML', 'Polentamais unter Rühren in gesalzenes Wasser einrieseln lassen und ausquellen; Öl einrühren.')
prep('salzkartoffeln', 'Salzkartoffeln', '2400', 'G', 'kartoffeln:2400:G;salz:10:G', 'Kartoffeln schälen, schneiden, in Salzwasser garen und abgiessen.')
prep('rahmspinat', 'Rahmspinat', '1700', 'G', 'blattspinat:1600:G;vollrahm:250:ML;butter:40:G;salz:8:G;muskat:1:PRISE', 'Spinat in Butter garen, Rahm einrühren und mit Salz und Muskat würzen.')
prep('spinat-gegart', 'Spinat', '1400', 'G', 'blattspinat:1600:G;rapsoel:30:ML;salz:6:G', 'Spinat waschen, in Öl garen und salzen; ohne Milchprodukte für beide zugeordneten Gerichte.')
prep('zwetschgenkompott', 'Zwetschgenkompott', '1600', 'G', 'zwetschgen:1600:G;zucker:80:G', 'Zwetschgen entsteinen und mit Zucker weich dünsten; Früchte und Saft gemeinsam verwenden.')
prep('tomatensauce', 'Tomatensauce', '1300', 'G', 'passata:1200:G;zwiebel:150:G;knoblauch:20:G;olivenoel:40:ML;salz:8:G', 'Zwiebel und Knoblauch in Öl anschwitzen, Passata und Salz zugeben und köcheln lassen.')
prep('kraeutersauce', 'Kräutersauce', '650', 'ML', 'vollrahm:400:ML;kraeuter:40:G;weisswein:100:ML;zwiebel:200:G;butter:20:G;salz:5:G', 'Zwiebel in Butter anschwitzen, mit Wein ablöschen, Rahm und Kräuter zufügen und einkochen; fertiges Volumen messen.')
prep('zwiebelsauce', 'Zwiebelsauce', '1000', 'G', 'zwiebel:800:G;gemuesebruehe:400:ML;butter:60:G;salz:5:G', 'Zwiebeln in Butter bräunen, mit vorbereiteter Gemüsebouillon ablöschen und weich schmoren.')
prep('kartoffelgratin', 'Kartoffelgratin', '3400', 'G', 'kartoffeln:2600:G;milch:600:ML;vollrahm:300:ML;hartkaese:150:G;knoblauch:10:G;salz:12:G;muskat:1:PRISE', 'Kartoffeln dünn schneiden, mit Milch, Rahm, Knoblauch und Gewürzen in eine Form schichten; mit Käse überbacken.')
prep('tomatensalat', 'Tomatensalat', '1700', 'G', 'tomaten:1600:G;zwiebel:100:G;olivenoel:40:ML;essig:30:ML;salz:6:G', 'Tomaten und Zwiebel schneiden, mit Öl, Essig und Salz mischen.')
prep('apfelmus', 'Apfelmus', '1600', 'G', 'aepfel:1800:G;wasser:100:ML;zucker:60:G;zimt:2:G', 'Äpfel entkernen und schneiden, mit Wasser weich dünsten; mit Zucker und Zimt pürieren.')
prep('kartoffelwedges', 'Kartoffelwedges', '2400', 'G', 'kartoffeln:2600:G;rapsoel:60:ML;paprikapulver:8:G;salz:10:G', 'Kartoffeln in Spalten schneiden, mit Öl, Paprika und Salz mischen und im Ofen rösten.')
prep('marktgemuese', 'Marktgemüse', '1800', 'G', 'broccoli:700:G;rueebli:700:G;zucchetti:600:G;rapsoel:30:ML;salz:8:G', 'Gemüse passend schneiden, getrennt bissfest garen und mit Öl und Salz mischen. Mischung ist ein bearbeitbarer Vorschlag.')
prep('erbsen-rueebli', 'Erbsen und Rüebli', '1800', 'G', 'erbsen-tk:1000:G;rueebli:900:G;rapsoel:30:ML;salz:8:G', 'Rüebli schneiden und garen; Erbsen zugeben und fertig garen, mit Öl und Salz abschmecken.')

SIDES = {'Kartoffelstock': 'kartoffelstock', 'Zucchetti': 'zucchetti-gegart', 'Broccoli': 'broccoli-gegart', 'Rüebli': 'rueebli-gegart', 'Karotten': 'rueebli-gegart', 'Bohnen': 'bohnen-gegart', 'Blattsalat': 'blattsalat-angerichtet', 'Basmatireis': 'basmatireis-gekocht', 'Reis': 'reis-gekocht', 'Polenta': 'polenta-gekocht', 'Salzkartoffeln': 'salzkartoffeln', 'Rahmspinat': 'rahmspinat', 'Spinat': 'spinat-gegart', 'Zwetschgenkompott': 'zwetschgenkompott', 'Tomatensauce': 'tomatensauce', 'Hummus': 'hummus', 'Rösti': 'roesti', 'Ofengemüse': 'ofengemuese', 'Hausbrot': 'hausbrot', 'Kartoffelgratin': 'kartoffelgratin', 'Tomatensalat': 'tomatensalat', 'Apfelmus': 'apfelmus', 'Kartoffelwedges': 'kartoffelwedges', 'Marktgemüse': 'marktgemuese', 'Erbsen und Rüebli': 'erbsen-rueebli'}
# Explicit 1-based old ingredient lines replaced by prepared components. Never infer via title.
REMOVED = {'pouletbrust-kraeuter': [2, 3, 4, 5, 6, 7], 'spinat-ricotta-ravioli': [2, 3, 4, 5, 6], 'rindsgeschnetzeltes-stroganoff': [6, 7], 'kichererbsen-curry': [7, 8], 'kalbsbratwurst-zwiebelsauce': [2, 3, 4, 5, 6], 'gemuese-lasagne': [8], 'schweinsragout-tessin': [6, 7], 'polenta-pilzragout': [1, 6], 'zanderfilet': [2, 3, 4, 8], 'falafel-teller': [2, 3, 4], 'pouletgeschnetzeltes-paprika': [6, 7], 'gemuesegeschnetzeltes': [4, 7], 'kartoffelsuppe-wienerli': [6], 'kartoffelsuppe-kraeuter': [6], 'ruehrei-kraeuter': [4, 5], 'tofu-ruehrei': [3, 4], 'griessbrei-zwetschgen': [5, 6], 'kokos-griessbrei': [5, 6]}
METHODS = {
    'pouletbrust-kraeuter': 'Poulet salzen und pfeffern, in Butter braten; vorbereitete Kräutersauce zugeben und fertig garen.',
    'spinat-ricotta-ravioli': 'Ravioli in Salzwasser garen, abgiessen und mit vorbereiteter Tomatensauce, Hartkäse und Pfeffer anrichten.',
    'rindsgeschnetzeltes-stroganoff': 'Rind in Öl portionsweise anbraten; Zwiebel und Pilze anschwitzen, mit Wein ablöschen, Rahm zufügen und mit dem Fleisch fertig garen. Salzen und pfeffern.',
    'kichererbsen-curry': 'Zwiebel und Knoblauch in Öl anschwitzen, Curry, Passata und Kokosmilch zugeben; vorbereitete gekochte Kichererbsen darin erhitzen und salzen.',
    'kalbsbratwurst-zwiebelsauce': 'Bratwürste braten und mit vorbereiteter Zwiebelsauce, Salz und Pfeffer abschmecken.',
    'gemuese-lasagne': 'Zwiebel in Öl anschwitzen, Passata zugeben; Zucchetti und Spinat garen, mit Ricotta mischen. Mit Lasagneplatten und Sauce schichten, mit Käse überbacken; Salz und Muskat verwenden.',
    'schweinsragout-tessin': 'Fleisch in Öl anbraten, Zwiebel zugeben, mit Wein ablöschen und mit Passata und Rosmarin weich schmoren. Salzen und pfeffern.',
    'polenta-pilzragout': 'Pilze und Zwiebel in Butter braten, Rahm und Kräuter zufügen; mit Salz und Pfeffer abschmecken. Auf vorbereiteter Polenta anrichten.',
    'zanderfilet': 'Fisch trocken tupfen, salzen und pfeffern, in Butter braten.',
    'falafel-teller': 'Vorbereitete Falafel mit Öl erhitzen, mit Salz und Paprika abschmecken. Hummus genau einmal als fertige Beilage verwenden; keine zusätzlichen Kichererbsen einrechnen.',
    'pouletgeschnetzeltes-paprika': 'Poulet in Öl anbraten, Paprika und Zwiebel zufügen; Paprikapulver und vorbereitete Gemüsebouillon zugeben, fertig garen und salzen.',
    'gemuesegeschnetzeltes': 'Paprika, Pilze und Zwiebel in Öl braten; mit vorbereiteter Gemüsebouillon und Passata garen, salzen und mit Paprikapulver abschmecken. Zucchetti werden ausschliesslich als zugeordnete Beilage gerechnet.',
    'kartoffelsuppe-wienerli': 'Zwiebel in Butter anschwitzen, Kartoffeln und Rüebli zugeben, mit vorbereiteter Gemüsebouillon weich kochen und pürieren. Wienerli darin erhitzen; mit Salz, Muskat und Kräutern abschmecken.',
    'kartoffelsuppe-kraeuter': 'Zwiebel in Öl anschwitzen, Kartoffeln und Rüebli zugeben, mit vorbereiteter Gemüsebouillon weich kochen und pürieren; Kräuter, Salz und Muskat zugeben.',
    'ruehrei-kraeuter': 'Eier mit Milch, Salz und Pfeffer verquirlen, in Butter zu Rührei stocken lassen und Kräuter unterheben.',
    'tofu-ruehrei': 'Tofu zerbröseln, in Öl braten und mit Paprika, Salz, Pfeffer und Kräutern abschmecken.',
    'griessbrei-zwetschgen': 'Milch und Butter erhitzen, Griess einrieseln lassen und unter Rühren quellen; mit Zucker und Zimt abschmecken. Vorbereitetes Kompott einmal zugeben.',
    'kokos-griessbrei': 'Kokosmilch und Wasser erhitzen, Griess einrieseln lassen und unter Rühren quellen; mit Zucker abschmecken. Vorbereitetes Kompott einmal zugeben.',
}
for old in examples['recipes']:
    k = old['key'].removeprefix('example.recipe.')
    p = old['payload']
    kept = [dict(food_key=i['food_key'].replace('example.', 'draft.', 1), quantity=i['quantity'], unit_code=i['unit_code'], legacy_line=n) for n, i in enumerate(p['ingredients'], 1) if n not in REMOVED[k]]
    r = recipe(k, p['title'], p['servings'], p['servings_unit_code'], 'salz:1:G', [METHODS[k]], 'dish', old['key'])
    r['ingredients'] = kept
    r['source']['replaced_legacy_lines'] = REMOVED[k]
    r['source']['adaptation'] = 'Beilagen/Saucen in vorbereitete Foods ausgelagert; deren Ausbeute und zusätzliche Zubereitungszutaten sind neue ungeprüfte Vorschläge. Verbleibende Mengen exakt aus den Beispielzeilen.'
    if k in {'pouletbrust-kraeuter', 'kalbsbratwurst-zwiebelsauce', 'polenta-pilzragout'}:
        pk = {'pouletbrust-kraeuter': 'kraeutersauce', 'kalbsbratwurst-zwiebelsauce': 'zwiebelsauce', 'polenta-pilzragout': 'polenta-gekocht'}[k]
        r['ingredients'] += ingredients(f'{pk}:{recipes[pk]["yield_quantity"]}:{recipes[pk]["yield_unit_code"]}')

NEW = [
    ('schinken-kaese-toast', 'Schinken-Käse-Toast', 'hausbrot:1200:G;schinken:800:G;hartkaese:500:G;butter:60:G', 'Brot mit Butter bestreichen, mit Schinken und Käse belegen und überbacken.'),
    ('gemuese-toast', 'Gemüse-Toast', 'hausbrot:1200:G;zucchetti:600:G;paprika:500:G;champignon:400:G;hartkaese:400:G;olivenoel:40:ML;salz:8:G', 'Gemüse schneiden und in Öl garen, salzen; auf Brot verteilen und mit Käse überbacken.'),
    ('hackbraten-rosmarinjus', 'Hackbraten an Rosmarinjus', 'hackfleisch:2.4:KG;zwiebel:250:G;ei:4:STK;haferflocken:200:G;senf:40:G;salz:16:G;pfeffer:2:PRISE;gemuesebruehe:600:ML;rosmarin:10:G;rapsoel:40:ML;mehl:30:G', 'Zwiebel fein schneiden, mit Hackfleisch, Eiern, Haferflocken, Senf, Salz und Pfeffer mischen; formen und im Ofen garen. Bratensatz mit Öl und Mehl binden, mit vorbereiteter Bouillon ablöschen und Rosmarin darin ziehen lassen.'),
    ('linsenbraten', 'Linsenbraten', 'linsen:900:G;wasser:2200:ML;zwiebel:250:G;rueebli:400:G;haferflocken:250:G;ei:4:STK;senf:30:G;rapsoel:40:ML;salz:14:G;pfeffer:2:PRISE', 'Linsen in Wasser weich kochen und abtropfen; Zwiebel und Rüebli in Öl garen. Mit Linsen, Haferflocken, Eiern, Senf und Gewürzen mischen, in einer Form backen.'),
    ('aelplermagronen-speck', 'Älplermagronen mit Speck', 'magronen:1200:G;kartoffeln:1000:G;vollrahm:500:ML;milch:600:ML;hartkaese:500:G;zwiebel:400:G;speck:500:G;salz:12:G;pfeffer:2:PRISE', 'Kartoffeln würfeln und mit Magronen garen. Speck mit Zwiebeln anbraten; Rahm, Milch und Käse mit Kartoffeln und Teigwaren mischen, würzen und mit Speckzwiebeln anrichten.'),
    ('aelplermagronen-vegetarisch', 'Älplermagronen vegetarisch', 'magronen:1200:G;kartoffeln:1000:G;vollrahm:500:ML;milch:600:ML;hartkaese:500:G;zwiebel:400:G;rapsoel:40:ML;salz:12:G;pfeffer:2:PRISE', 'Kartoffeln würfeln und mit Magronen garen. Zwiebeln in Öl bräunen; Rahm, Milch und Käse mit Kartoffeln und Teigwaren mischen, würzen und Zwiebeln darübergeben.'),
    ('pouletschenkel-ofen', 'Ofen-Pouletschenkel', 'pouletschenkel:20:STK;rapsoel:80:ML;paprikapulver:20:G;rosmarin:10:G;salz:18:G;pfeffer:2:PRISE', 'Schenkel mit Öl, Paprika, Rosmarin, Salz und Pfeffer einreiben und im Ofen vollständig garen; Gargrad nach Küchenstandard kontrollieren.'),
    ('kichererbsen-eintopf', 'Kichererbsen-Eintopf', 'kichererbsen:2200:G;passata:1000:G;zwiebel:300:G;paprika:600:G;gemuesebruehe:600:ML;knoblauch:20:G;olivenoel:50:ML;paprikapulver:12:G;salz:14:G', 'Zwiebel, Knoblauch und Paprika in Öl anschwitzen; Passata, vorbereitete Bouillon und gekochte Kichererbsen zugeben und schmoren. Mit Salz und Paprikapulver abschmecken.'),
    ('buendner-gerstensuppe', 'Bündner Gerstensuppe', 'rollgerste:500:G;lauch:500:G;rueebli:500:G;sellerie:300:G;kartoffeln:700:G;speck:400:G;gemuesebruehe:4000:ML;vollrahm:300:ML;salz:12:G;pfeffer:2:PRISE', 'Speck auslassen, geschnittenes Gemüse darin anschwitzen; Gerste, Kartoffeln und vorbereitete Bouillon zugeben, weich kochen und mit Rahm, Salz und Pfeffer abschmecken.'),
    ('gemuese-gerstensuppe', 'Gemüse-Gerstensuppe', 'rollgerste:500:G;lauch:500:G;rueebli:500:G;sellerie:300:G;kartoffeln:700:G;gemuesebruehe:4000:ML;rapsoel:40:ML;kraeuter:30:G;salz:12:G;pfeffer:2:PRISE', 'Geschnittenes Gemüse in Öl anschwitzen; Gerste, Kartoffeln und vorbereitete Bouillon zugeben, weich kochen und mit Kräutern, Salz und Pfeffer abschmecken.'),
    ('rindsschmorbraten', 'Rindsschmorbraten', 'rindbraten:3000:G;zwiebel:400:G;rueebli:400:G;sellerie:250:G;passata:300:G;gemuesebruehe:1200:ML;rosmarin:10:G;rapsoel:50:ML;salz:18:G;pfeffer:2:PRISE', 'Braten würzen und in Öl anbraten, Gemüse mitrösten; Passata, Rosmarin und vorbereitete Bouillon zugeben und zugedeckt weich schmoren. Sauce pürieren und zum geschnittenen Braten reichen.'),
    ('nussbraten-kraeuter', 'Nussbraten mit Kräutersauce', 'nuesse:800:G;linsen:400:G;wasser:1000:ML;zwiebel:250:G;rueebli:400:G;haferflocken:250:G;ei:4:STK;rapsoel:40:ML;salz:12:G;pfeffer:2:PRISE;kraeutersauce:650:ML', 'Linsen in Wasser weich kochen und abtropfen; Zwiebel und Rüebli in Öl garen. Mit gehackten Nüssen, Haferflocken, Eiern und Gewürzen mischen und in einer Form backen; vorbereitete Kräutersauce dazu reichen.'),
    ('pastetli-braetkuegeli', 'Pastetli mit Brätkügeli', 'pastetli:20:STK;braetkuegeli:1800:G;champignon:800:G;zwiebel:200:G;butter:80:G;mehl:80:G;gemuesebruehe:800:ML;vollrahm:400:ML;salz:10:G;pfeffer:2:PRISE', 'Zwiebel und Pilze in Butter anschwitzen, Mehl einrühren und mit vorbereiteter Bouillon ablöschen; Rahm und Brätkügeli zugeben und vollständig garen. Würzen und in erwärmte Pastetli füllen.'),
    ('gemuese-pastetli', 'Gemüse-Pastetli', 'pastetli:20:STK;champignon:1000:G;zucchetti:700:G;zwiebel:200:G;butter:80:G;mehl:80:G;gemuesebruehe:800:ML;vollrahm:400:ML;salz:10:G;pfeffer:2:PRISE', 'Zwiebel, Pilze und Zucchetti in Butter garen, Mehl einrühren und mit vorbereiteter Bouillon ablöschen; Rahm zufügen und würzen. In erwärmte Pastetli füllen; Erbsen und Rüebli bleiben separate Beilage.'),
]
for key, title, spec, method in NEW:
    recipe(key, title, '20', 'PORTION', spec, [method], 'dish')

labels: dict[str, set[str]] = {}
snapshot_pins = []
for path in sorted((ROOT / 'demo/snapshots').glob('*_kw36.json')):
    snapshot_pins.append({'file': str(path.relative_to(ROOT)), 'sha256': hashlib.sha256(path.read_bytes()).hexdigest()})
    for day in json.loads(path.read_text())['days']:
        for service in day['services']:
            for option in service['options']:
                labels.setdefault(option['title'], set()).update(label['code'] for label in option['labels'])
title_recipes = {r['title']: r for r in recipes.values() if r['role'] == 'dish'}
mappings = []
for title in sorted({m['title'] for m in live['menus']}):
    r = title_recipes[title]
    menus = [m for m in live['menus'] if m['title'] == title]
    sides = [c['text'] for c in menus[0]['components']]
    r['proposed_dietary_labels'] = sorted(labels.get(title, set()) & {'VEGETARIAN', 'VEGAN'})
    for side in sides:
        pk = SIDES[side]
        r['ingredients'].append({'food_key': 'draft.food.' + pk, 'quantity': recipes[pk]['yield_quantity'], 'unit_code': recipes[pk]['yield_unit_code'], 'menu_side_text': side})
    r['steps'].append('Die zugeordneten vorbereiteten Beilagen einmal entnehmen und anrichten: ' + ', '.join(sides) + '. Mengenansatz für 20 Portionen vor Freigabe praktisch prüfen.')
    mappings.append({'title': title, 'recipe_key': r['key'], 'snapshot_labels_observed_not_approved': sorted(labels.get(title, set())),
                     'source_occurrences': [{'menu_public_id': m['public_id'], 'profile': m['profile'], 'location_public_id': m['location_public_id'], 'components': [{'text': c['text'], 'component_id': c['component_id'], 'food_key': 'draft.food.' + SIDES[c['text']]} for c in m['components']]} for m in menus]})

data = {'meta': {'kind': 'dishboard_symbolic_linked_recipe_drafts', 'format_version': 1, 'runtime_import_format': False, 'status': 'unreviewed_preparation_only',
    'created_for_wp': 'wp-39685654718a', 'source_commit': live['production_commit'], 'source_schema_version': live['schema_version'], 'captured_at_utc': live['captured_at_utc'],
    'capture_sha256': hashlib.sha256(CAPTURE.read_bytes()).hexdigest(), 'examples_sha256': hashlib.sha256(EXAMPLES.read_bytes()).hexdigest(), 'snapshot_sources': snapshot_pins,
    'unit_policy': 'Reference existing active foundation codes only; no unit creation or contextual conversion.', 'preparation_policy': 'Symbolic selected recipe key only; future immutable revision resolution and Schema A contract required before import.',
    'quantity_policy': 'Positive decimal strings. Yields are unmeasured kitchen proposals, not density, piece-weight or PORTION-to-mass conversions.',
    'storage_policy': 'Three proposed editable locations; user preference unanswered. No inventory, shelf life, production date or storage safety guarantee.',
    'allergen_policy': 'All unreviewed; source snapshot labels and checked flags are not recipe approval. No LACTOSE_FREE/GLUTEN_FREE approval inferred.',
    'mapping_policy': 'Only original menu occurrences; exact titles/profiles/side text preserved. No replacement weeks, menu mutations or publication.'},
    'existing_unit_codes': [u['code'] for u in live['units']],
    'storage_proposals': [{'key': 'proposed.storage.' + k, 'name': n, 'status': 'proposed', 'editable': True} for k, n in [('trockenlager', 'Trockenlager'), ('kuehlraum', 'Kühlraum'), ('tiefkuehler', 'Tiefkühler')]],
    'foods': list(foods.values()), 'recipes': list(recipes.values()), 'dish_mappings': mappings,
    'source_components': live['components'], 'audit_notes': [
        'Falafel-Teller: alte zusätzliche 200 G Kichererbsen zum bereits vorhandenen Hummus entfernt; Hummus genau einmal als 800 G vorbereitete Zutat.',
        'Gemüsegeschnetzeltes: alte 1600 G Zucchetti aus der Hauptkomponente in die tatsächlich ausgeschriebene Beilage verlagert.',
        'Griessbreie: Zwetschgen und Kompottzucker ausschliesslich im gemeinsamen Kompott; Hauptgericht enthält nur eine Kompottzeile.',
        'Rüebli und Karotten sind ausdrücklich derselbe vorgeschlagene zubereitete Foodkey; Originalbezeichnungen bleiben je Menü unverändert.',
        'Für neue Gerichte werden keine Speck-/Ei-/Milchzutaten in VEGAN-Vorschlägen verwendet; Zutatenprüfung umfasst alle Subrezepte.',
        'Alte 54 Food-Identitäten und 18 Rezeptansätze nachvollziehbar verwendet; deren manual-Quellenangabe ist Beispielprovenienz, keine verifizierte Küchenquelle.',
        'Kochwasser zum Abgiessen, Waschen und Dämpfen ist Prozesswasser, kein erfundener Lagerbestand. Für absorbiertes Wasser oder Bouillon sind Mengen explizit enthalten.',
    ]}
(ROOT / 'demo/linked_recipe_drafts.json').write_text(json.dumps(data, ensure_ascii=False, indent=2) + '\n')
print(f'DRAFT WRITTEN: {len(title_recipes)} dishes, {len(recipes)} total recipes, {len(foods)} foods, {len(mappings)} title mappings; no runtime operations.')
