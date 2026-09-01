#!/usr/bin/env python3
"""Deterministische Beispieldaten für dieselbe Kalenderwoche in beiden Profilen."""
from __future__ import annotations

from copy import deepcopy
from typing import Any

WEEK_START = '2026-08-31'
WEEK_END = '2026-09-06'

DAYS = [
    ('2026-08-31', 'Montag'),
    ('2026-09-01', 'Dienstag'),
    ('2026-09-02', 'Mittwoch'),
    ('2026-09-03', 'Donnerstag'),
    ('2026-09-04', 'Freitag'),
    ('2026-09-05', 'Samstag'),
    ('2026-09-06', 'Sonntag'),
]

CAFETERIA = {
    '2026-08-31': (
        ('Pouletbrust an Kräutersauce', 'Kartoffelstock · Zucchetti', ['Kartoffelstock', 'Zucchetti'], [], [('Poulet', 'CH')]),
        ('Spinat-Ricotta-Ravioli', 'Tomatensauce · Blattsalat', ['Tomatensauce', 'Blattsalat'], ['VEGETARIAN'], []),
    ),
    '2026-09-01': (
        ('Rindsgeschnetzeltes Stroganoff', 'Basmatireis · Broccoli', ['Basmatireis', 'Broccoli'], [], [('Rind', 'CH')]),
        ('Kichererbsen-Curry', 'Basmatireis · Broccoli', ['Basmatireis', 'Broccoli'], ['VEGAN', 'LACTOSE_FREE'], []),
    ),
    '2026-09-02': (
        ('Kalbsbratwurst mit Zwiebelsauce', 'Rösti · Rüebli', ['Rösti', 'Rüebli'], [], [('Kalb', 'CH')]),
        ('Gemüse-Lasagne', 'Blattsalat', ['Blattsalat'], ['VEGETARIAN'], []),
    ),
    '2026-09-03': (
        ('Schweinsragout Tessiner Art', 'Polenta · Bohnen', ['Polenta', 'Bohnen'], [], [('Schwein', 'CH')]),
        ('Polenta mit Pilzragout', 'Bohnen', ['Bohnen'], ['VEGETARIAN'], []),
    ),
    '2026-09-04': (
        ('Gebratenes Zanderfilet', 'Salzkartoffeln · Rahmspinat', ['Salzkartoffeln', 'Rahmspinat'], [], [('Zander', 'DE')]),
        ('Falafel-Teller', 'Hummus · Ofengemüse', ['Hummus', 'Ofengemüse'], ['VEGAN', 'LACTOSE_FREE'], []),
    ),
}

PATIENT = {
    '2026-08-31': {
        'LUNCH': (
            ('Pouletgeschnetzeltes Paprika', 'Reis · Zucchetti', ['Reis', 'Zucchetti'], [], [('Poulet', 'CH')]),
            ('Gemüsegeschnetzeltes', 'Reis · Zucchetti', ['Reis', 'Zucchetti'], ['VEGETARIAN'], []),
        ),
        'DINNER': (
            ('Schinken-Käse-Toast', 'Tomatensalat', ['Tomatensalat'], [], [('Schwein', 'CH')]),
            ('Gemüse-Toast', 'Tomatensalat', ['Tomatensalat'], ['VEGETARIAN'], []),
        ),
    },
    '2026-09-01': {
        'LUNCH': (
            ('Hackbraten an Rosmarinjus', 'Kartoffelgratin · Broccoli', ['Kartoffelgratin', 'Broccoli'], [], [('Rind', 'CH')]),
            ('Linsenbraten', 'Kartoffelgratin · Broccoli', ['Kartoffelgratin', 'Broccoli'], ['VEGETARIAN'], []),
        ),
        'DINNER': (
            ('Kartoffelsuppe mit Wienerli', 'Hausbrot', ['Hausbrot'], [], [('Schwein', 'CH')]),
            ('Kartoffelsuppe mit Kräutern', 'Hausbrot', ['Hausbrot'], ['VEGETARIAN'], []),
        ),
    },
    '2026-09-02': {
        'LUNCH': (
            ('Kalbsbratwurst mit Zwiebelsauce', 'Rösti · Rüebli', ['Rösti', 'Rüebli'], [], [('Kalb', 'CH')]),
            ('Gemüse-Lasagne', 'Blattsalat', ['Blattsalat'], ['VEGETARIAN'], []),
        ),
        'DINNER': (
            ('Älplermagronen mit Speck', 'Apfelmus', ['Apfelmus'], [], [('Schwein', 'CH')]),
            ('Älplermagronen vegetarisch', 'Apfelmus', ['Apfelmus'], ['VEGETARIAN'], []),
        ),
    },
    '2026-09-03': {
        'LUNCH': (
            ('Schweinsragout Tessiner Art', 'Polenta · Bohnen', ['Polenta', 'Bohnen'], [], [('Schwein', 'CH')]),
            ('Polenta mit Pilzragout', 'Bohnen', ['Bohnen'], ['VEGETARIAN'], []),
        ),
        'DINNER': (
            ('Rührei mit Kräutern', 'Salzkartoffeln · Spinat', ['Salzkartoffeln', 'Spinat'], ['VEGETARIAN'], []),
            ('Tofu-Rührei', 'Salzkartoffeln · Spinat', ['Salzkartoffeln', 'Spinat'], ['VEGAN'], []),
        ),
    },
    '2026-09-04': {
        'LUNCH': (
            ('Gebratenes Zanderfilet', 'Salzkartoffeln · Rahmspinat', ['Salzkartoffeln', 'Rahmspinat'], [], [('Zander', 'DE')]),
            ('Falafel-Teller', 'Hummus · Ofengemüse', ['Hummus', 'Ofengemüse'], ['VEGAN'], []),
        ),
        'DINNER': (
            ('Griessbrei mit Zwetschgenkompott', 'Zimt und Zucker', ['Zwetschgenkompott'], ['VEGETARIAN'], []),
            ('Kokos-Griessbrei', 'Zwetschgenkompott', ['Zwetschgenkompott'], ['VEGAN'], []),
        ),
    },
    '2026-09-05': {
        'LUNCH': (
            ('Ofen-Pouletschenkel', 'Kartoffelwedges · Marktgemüse', ['Kartoffelwedges', 'Marktgemüse'], [], [('Poulet', 'CH')]),
            ('Kichererbsen-Eintopf', 'Kartoffelwedges · Marktgemüse', ['Kartoffelwedges', 'Marktgemüse'], ['VEGAN'], []),
        ),
        'DINNER': (
            ('Bündner Gerstensuppe', 'Hausbrot', ['Hausbrot'], [], [('Rind', 'CH')]),
            ('Gemüse-Gerstensuppe', 'Hausbrot', ['Hausbrot'], ['VEGETARIAN'], []),
        ),
    },
    '2026-09-06': {
        'LUNCH': (
            ('Rindsschmorbraten', 'Kartoffelstock · Karotten', ['Kartoffelstock', 'Karotten'], [], [('Rind', 'CH')]),
            ('Nussbraten mit Kräutersauce', 'Kartoffelstock · Karotten', ['Kartoffelstock', 'Karotten'], ['VEGETARIAN'], []),
        ),
        'DINNER': (
            ('Pastetli mit Brätkügeli', 'Erbsen und Rüebli · Blattsalat', ['Erbsen und Rüebli', 'Blattsalat'], [], [('Kalb', 'CH')]),
            ('Gemüse-Pastetli', 'Erbsen und Rüebli · Blattsalat', ['Erbsen und Rüebli', 'Blattsalat'], ['VEGETARIAN'], []),
        ),
    },
}

LABEL_NAMES = {
    'VEGETARIAN': 'Vegetarisch',
    'VEGAN': 'Vegan',
    'LACTOSE_FREE': 'Laktosefrei',
    'GLUTEN_FREE': 'Glutenfrei',
}


def _allergens(title: str) -> list[dict[str, str]]:
    values: list[tuple[str, str, str]] = []
    lower = title.lower()
    if any(word in lower for word in ('käse', 'ricotta', 'rahm', 'griess', 'gratin')):
        values.append(('MILK', 'Milch', 'contains'))
    if any(word in lower for word in ('toast', 'ravioli', 'lasagne', 'pastetli', 'brot', 'magronen', 'gerste', 'griess')):
        values.append(('GLUTEN', 'Glutenhaltiges Getreide', 'contains'))
    if any(word in lower for word in ('nuss', 'curry')):
        values.append(('NUTS', 'Schalenfrüchte', 'may_contain'))
    return [{'code': c, 'name': n, 'presence': p} for c, n, p in values]


def _option(
    *,
    profile: str,
    date_value: str,
    meal: str,
    index: int,
    data: tuple[str, str, list[str], list[str], list[tuple[str, str]]],
) -> dict[str, Any]:
    title, description, components, labels, origins = data
    result: dict[str, Any] = {
        'external_id': f'{profile.upper()}-{date_value}-{meal}-{index}',
        'type_code': 'MENU_1' if index == 1 else 'VEGGIE',
        'type_name': 'Menü 1' if index == 1 else 'Vegetarisch',
        'title': title,
        'description': description,
        'components': components,
        'labels': [{'code': code, 'name': LABEL_NAMES[code]} for code in labels],
        'allergens': _allergens(title),
        'origins': [
            {'ingredient': ingredient, 'country_code': country, 'text': f'{ingredient}: Schweiz' if country == 'CH' else f'{ingredient}: Deutschland'}
            for ingredient, country in origins
        ],
        'note': '',
        'allergen_review_status': 'checked',
    }
    if profile == 'staff_guest':
        result['prices'] = {'internal_rappen': 1100, 'external_rappen': 1660, 'currency': 'CHF'}
    return result


def cafeteria_snapshot() -> dict[str, Any]:
    days: list[dict[str, Any]] = []
    for date_value, weekday in DAYS:
        if date_value in CAFETERIA:
            options = [
                _option(profile='staff_guest', date_value=date_value, meal='LUNCH', index=index, data=data)
                for index, data in enumerate(CAFETERIA[date_value], start=1)
            ]
            days.append({
                'date': date_value,
                'weekday': weekday,
                'state': 'open',
                'notice': '',
                'services': [{'meal_code': 'LUNCH', 'meal_name': 'Mittag', 'options': options}],
            })
        else:
            days.append({
                'date': date_value,
                'weekday': weekday,
                'state': 'closed',
                'notice': 'Cafeteria geschlossen',
                'services': [],
            })
    return {
        'schema_version': 2,
        'profile_code': 'staff_guest',
        'channel': 'cafeteria',
        'revision_id': 'CAF-2026-KW36-R1',
        'location': {'code': 'KIRCHLINDACH', 'name': 'Klinik Südhang Kirchlindach'},
        'week_start': WEEK_START,
        'week_end': WEEK_END,
        'title': '31. August bis 4. September',
        'shared_note': 'Cafeteria-Mittag für Mitarbeitende und externe Gäste.',
        'days': days,
    }


def patient_snapshot() -> dict[str, Any]:
    days: list[dict[str, Any]] = []
    for date_value, weekday in DAYS:
        services = []
        for meal_code, meal_name in (('LUNCH', 'Mittag'), ('DINNER', 'Abend')):
            options = [
                _option(profile='patient', date_value=date_value, meal=meal_code, index=index, data=data)
                for index, data in enumerate(PATIENT[date_value][meal_code], start=1)
            ]
            services.append({'meal_code': meal_code, 'meal_name': meal_name, 'options': options})
        days.append({
            'date': date_value,
            'weekday': weekday,
            'state': 'open',
            'notice': '',
            'services': services,
        })
    return {
        'schema_version': 2,
        'profile_code': 'patient',
        'channel': 'patienten',
        'revision_id': 'PAT-2026-KW36-R1',
        'location': {'code': 'KIRCHLINDACH', 'name': 'Klinik Südhang Kirchlindach'},
        'week_start': WEEK_START,
        'week_end': WEEK_END,
        'title': '31. August bis 6. September',
        'shared_note': 'Allgemeiner Speiseplan für Patientinnen und Patienten.',
        'days': days,
    }


def snapshots() -> tuple[dict[str, Any], dict[str, Any]]:
    return deepcopy(cafeteria_snapshot()), deepcopy(patient_snapshot())
