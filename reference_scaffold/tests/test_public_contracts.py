from __future__ import annotations

import re
import sys
import unicodedata
from copy import deepcopy
from importlib import import_module, util
from pathlib import Path
from typing import Any

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

from cafeteria.admin import routes as admin_routes  # noqa: E402
from cafeteria.api import routes as api_routes  # noqa: E402
from cafeteria.auth.service import AuthorizationState  # noqa: E402
from cafeteria.db import validate_snapshot_payload  # noqa: E402
from cafeteria.public import routes as public_routes  # noqa: E402
from cafeteria import roles as role_module  # noqa: E402
from cafeteria.signage import routes as signage_routes  # noqa: E402
from demo_snapshots import cafeteria_snapshot, patient_snapshot  # noqa: E402


def test_db_reexports_payload_validator_from_isolated_module() -> None:
    spec = util.find_spec('cafeteria.patient_payload')
    assert spec is not None
    module = import_module('cafeteria.patient_payload')
    assert validate_snapshot_payload is module.validate_snapshot_payload


PUBLIC_QUERY_PATHS = (
    '/',
    '/cafeteria/heute/',
    '/cafeteria/wochenangebot/',
    '/patienten/heute/',
    '/patienten/wochenplan/',
    '/druck/cafeteria/woche',
    '/druck/patienten/woche',
    '/cafeteria/legende/',
    '/api/v1/published/cafeteria',
    '/api/v1/published/patienten',
    '/signage/cafeteria/tag',
    '/signage/cafeteria/woche',
    '/signage/patienten/tag',
    '/signage/patienten/woche',
)

PATIENT_OUTPUT_PATHS = (
    '/patienten/heute/',
    '/patienten/wochenplan/',
    '/druck/patienten/woche',
    '/api/v1/published/patienten',
    '/signage/patienten/tag',
    '/signage/patienten/woche',
    '/admin/export/patienten.csv',
)

PATIENT_RESERVED_KEY_PROBES = (
    pytest.param('Gesamtbetrag', 1250, id='gesamtbetrag'),
    pytest.param('Endbetrag', 1250, id='endbetrag'),
    pytest.param('Währungscode', 'CHF', id='waehrungscode-umlaut'),
    pytest.param('Waehrungscode', 'CHF', id='waehrungscode-ascii'),
    pytest.param('Zahlungsbetrag', 1250, id='zahlungsbetrag'),
    pytest.param('Zahlungspflichtig', True, id='zahlungspflichtig'),
    pytest.param('Rechnungsbetrag', 1250, id='rechnungsbetrag'),
    pytest.param('Eurobetrag', 1250, id='eurobetrag'),
    pytest.param('PRlCE', 1250, id='ascii-l-price'),
    pytest.param('CHlF', '12.50', id='ascii-l-chf'),
    pytest.param('PRI\u2066CE', 1250, id='bidi-isolate-price'),
)

PATIENT_UNSAFE_FORMAT_CHARACTERS = tuple(
    chr(codepoint)
    for codepoint in range(sys.maxunicode + 1)
    if (
        unicodedata.category(chr(codepoint)) == 'Cf'
        or unicodedata.bidirectional(chr(codepoint))
        in {'LRE', 'RLE', 'LRO', 'RLO', 'PDF', 'LRI', 'RLI', 'FSI', 'PDI'}
    )
)

PATIENT_FREE_TEXT_BYPASSES = (
    pytest.param('title', 'kostenpflichtig 12.50', id='kostenpflichtig'),
    pytest.param('title', 'Gebühren 12.50', id='gebuehren-plural'),
    pytest.param('title', 'Tarife 12.50', id='tarife-plural'),
    pytest.param('title', 'Aufpreise 12.50', id='aufpreise-plural'),
    pytest.param('title', 'Pricing 12.50', id='pricing'),
    pytest.param('title', 'Chargeable 12.50', id='chargeable'),
    pytest.param('title', 'P r e i s: 12.50', id='spaced-preis'),
    pytest.param('title', 'P\u00a0r\u00a0e\u00a0i\u00a0s: 12.50', id='nbsp-preis'),
    pytest.param('title', 'P\u2028r\u2028e\u2028i\u2028s: 12.50', id='line-separator-preis'),
    pytest.param('title', 'P.r.e.i.s: 12.50', id='punctuated-preis'),
    pytest.param('title', 'P/R/I/C/E 12.50', id='punctuated-price'),
    pytest.param('title', 'P\u0332r\u0332e\u0332i\u0332s: 12.50', id='combining-preis'),
    pytest.param('title', 'Pr\u0435is: 12.50', id='homoglyph-preis'),
    pytest.param('title', 'Fr.: 12.50', id='fr-colon'),
    pytest.param('title', 'Fr. 12', id='fr-whole-amount'),
    pytest.param('title', 'CHF12.50', id='compact-chf-prefix'),
    pytest.param('title', '12.50CHF', id='compact-chf-suffix'),
    pytest.param('title', '12.50 pro Menü', id='amount-with-context'),
    pytest.param('title', '12.50*', id='amount-with-footnote'),
    pytest.param('title', '12.50 (inkl.)', id='swiss-included'),
    pytest.param('title', '12 . 50 pro Menü', id='spaced-decimal'),
    pytest.param('title', '12·50 pro Menü', id='middle-dot-decimal'),
    pytest.param('title', "Fr. 12'50", id='apostrophe-decimal'),
    pytest.param('title', '50 Rp.', id='rappen-abbreviation'),
    pytest.param('title', 'Prix 12.50', id='french-price'),
    pytest.param('title', 'Prezzo 12.50', id='italian-price'),
    pytest.param('labels', [{'code': 'P R I C E', 'name': 'Spezial'}], id='spaced-price-label'),
    pytest.param('labels', [{'code': 'unitPrice', 'name': 'Spezial'}], id='camel-price-label'),
    pytest.param(
        'origins',
        [{'country_code': 'CH', 'ingredient': 'Rind', 'text': 'Prix 12.50'}],
        id='nested-french-price',
    ),
)

PATIENT_SEMANTIC_OBFUSCATIONS = (
    pytest.param('title', 'P r e i s', id='spaced-preis-without-number'),
    pytest.param('title', 'P\u00a0r\u00a0e\u00a0i\u00a0s', id='nbsp-preis-without-number'),
    pytest.param('title', 'P\u2028r\u2028e\u2028i\u2028s', id='line-separator-preis-without-number'),
    pytest.param('title', 'P.r.e.i.s', id='punctuated-preis-without-number'),
    pytest.param('title', 'P/R/I/C/E', id='punctuated-price-without-number'),
    pytest.param('title', 'P\u0332r\u0332e\u0332i\u0332s', id='combining-preis-without-number'),
    pytest.param('title', 'Pr\u0435is', id='homoglyph-preis-without-number'),
    pytest.param('title', 'C H F', id='spaced-chf'),
    pytest.param('title', 'F r', id='spaced-fr'),
    pytest.param('title', 'R p', id='spaced-rp'),
    pytest.param('title', 'unitPrice', id='camel-price-value'),
)

PATIENT_REVIEWER_PROBES = (
    pytest.param('title', 'Preis: 12.50', id='preis-colon'),
    pytest.param('title', 'Kosten 12.50', id='kosten'),
    pytest.param('title', 'internal', id='internal'),
    pytest.param('title', 'external', id='external'),
    pytest.param('title', 'currency', id='currency'),
    pytest.param('title', 'EUR 12.50', id='eur'),
    pytest.param('title', '0,00', id='zero-comma'),
    pytest.param('title', '50 Rappen', id='rappen'),
    pytest.param('title', 'inkludiert', id='inkludiert'),
    pytest.param('labels', [{'code': 'PRICE', 'name': '12.50'}], id='price-label'),
    pytest.param('title', 'Gebühr 12.50', id='gebuehr'),
    pytest.param('title', 'Fee', id='fee'),
    pytest.param('title', 'Charge', id='charge'),
    pytest.param('title', 'Tarif 12,50', id='tarif'),
    pytest.param('title', 'Aufpreis', id='aufpreis'),
    pytest.param('title', 'Frs. 12.50', id='frs'),
    pytest.param('title', '12.–', id='swiss-dash'),
    pytest.param('title', 'inklusive', id='inklusive'),
    pytest.param('title', 'included', id='included'),
    pytest.param('title', 'Pre\u200bis', id='zero-width-preis'),
    pytest.param('title', 'ＰＲＩＣＥ', id='nfkc-price'),
    pytest.param('labels', [{'code': 'RATE', 'name': 'Spezial'}], id='rate-label'),
    pytest.param('labels', [{'code': 'TARIF', 'name': 'Spezial'}], id='tarif-label'),
    pytest.param('labels', [{'code': 'PRI\u200bCE', 'name': 'Spezial'}], id='split-price-label'),
    pytest.param('origins', [{'country_code': 'CH', 'ingredient': 'Rind', 'text': 'Charge 12.50'}], id='nested-charge'),
    pytest.param('title', 12.5, id='numeric-title'),
    pytest.param('title', 'Menüpreis', id='menu-price-compound'),
    pytest.param('title', 'Preisangabe', id='price-declaration-compound'),
    pytest.param('title', 'Preisliste', id='price-list-compound'),
    pytest.param('title', 'Kostenbeitrag', id='cost-contribution-compound'),
    pytest.param('title', 'Kostenanteil', id='cost-share-compound'),
    pytest.param('title', 'Gebührenpflichtig', id='fee-bearing-stem'),
    pytest.param('title', 'Zuschlag', id='surcharge-alias'),
    pytest.param('title', 'Pauschale', id='flat-rate-alias'),
    pytest.param('title', 'Entgelt', id='payment-alias'),
    pytest.param('title', 'Selbstzahler', id='self-payer-alias'),
    pytest.param('title', 'kostete', id='cost-inflection'),
    pytest.param('title', 'Tarifierung', id='tariff-inflection'),
    pytest.param('title', 'Stutz', id='swiss-currency-slang'),
    pytest.param('title', 'Räppli', id='swiss-rappen-slang'),
    pytest.param('title', 'Fränkli', id='swiss-franc-slang'),
    pytest.param('title', 'Prıce', id='dotless-i-price'),
    pytest.param('title', 'Preıs', id='dotless-i-preis'),
    pytest.param('title', 'CΗF', id='greek-eta-chf'),
    pytest.param('title', 'СНF', id='cyrillic-chf'),
    pytest.param('title', 'Fг.', id='cyrillic-fr'),
    pytest.param('title', 'ΡRΙCΕ', id='greek-price-skeleton'),
    pytest.param('title', 'ᴘʀɪᴄᴇ', id='latin-small-cap-price'),
    pytest.param('title', 'unitprice', id='lowercase-price-compound'),
    pytest.param('title', 'Menücost', id='multilingual-cost-compound'),
    pytest.param('title', 'Gebuehrenpflichtig', id='ascii-fee-bearing-stem'),
    pytest.param('title', 'Raeppli', id='ascii-swiss-rappen-slang'),
    pytest.param('title', 'Fraenkli', id='ascii-swiss-franc-slang'),
    pytest.param('title', 'Rappenbetrag', id='swiss-currency-compound'),
    pytest.param('title', '12.50 Uhr pro Menü', id='clock-shaped-price'),
    pytest.param('title', 'Menüpreis 12.50 Uhr', id='compound-clock-price'),
    pytest.param('title', '１２:５０ Uhr pro Menü', id='fullwidth-clock-shaped-price'),
    pytest.param('title', '1٢:5٠ Uhr pro Menü', id='mixed-decimal-clock-shaped-price'),
    pytest.param('description', 'Ausgabe bis 12.50 Uhr', id='clock-outside-note'),
    pytest.param('note', 'Heute Ausgabe bis 12.50 Uhr', id='operational-time-prefix'),
    pytest.param('note', 'Ausgabe bis 12.50 Uhr pro Menü', id='operational-time-suffix'),
    pytest.param('note', 'Ausgabe bis 12.50\u200b Uhr', id='operational-time-format-control'),
    pytest.param('labels', [{'code': 'VEGAN', 'name': '12.50 Uhr pro Menü'}], id='clock-in-label'),
    pytest.param('title', 'Schonkost mit Menüpreis', id='food-term-with-price-semantics'),
    pytest.param('title', 'Gesamtbetrag', id='gesamtbetrag-compound'),
    pytest.param('title', 'Endbetrag', id='endbetrag-compound'),
    pytest.param('title', 'Währungscode', id='waehrungscode-compound'),
    pytest.param('title', 'Waehrungscode', id='waehrungscode-ascii-compound'),
    pytest.param('title', 'Zahlungsbetrag', id='zahlungsbetrag-compound'),
    pytest.param('title', 'Zahlungspflichtig', id='zahlungspflichtig-compound'),
    pytest.param('title', 'Rechnungsbetrag', id='rechnungsbetrag-compound'),
    pytest.param('title', 'Eurobetrag', id='eurobetrag-compound'),
    pytest.param('title', 'PRlCE', id='ascii-l-price-value'),
    pytest.param('title', 'PRLCE', id='ascii-uppercase-l-price-value'),
    pytest.param('title', 'PRIlCE', id='ascii-il-run-price-value'),
    pytest.param('title', 'PRlClNG', id='ascii-l-pricing-value'),
    pytest.param('title', 'unitPRlCE', id='ascii-l-price-compound-value'),
    pytest.param('title', 'CHlF', id='ascii-l-chf-value'),
    pytest.param('title', 'CHIF', id='ascii-i-chf-value'),
    pytest.param('title', 'C H l F', id='spaced-ascii-l-chf-value'),
    pytest.param('description', 'Gemüse\u2066pfanne', id='bidi-isolate-in-text'),
    *PATIENT_FREE_TEXT_BYPASSES,
    *PATIENT_SEMANTIC_OBFUSCATIONS,
)

PATIENT_FREE_TEXT_PATHS = (
    pytest.param(('title',), id='snapshot-title'),
    pytest.param(('shared_note',), id='shared-note'),
    pytest.param(('location', 'name'), id='location-name'),
    pytest.param(('days', 0, 'notice'), id='day-notice'),
    pytest.param(('days', 0, 'services', 0, 'options', 0, 'title'), id='option-title'),
    pytest.param(('days', 0, 'services', 0, 'options', 0, 'description'), id='option-description'),
    pytest.param(('days', 0, 'services', 0, 'options', 0, 'components', 0), id='component'),
    pytest.param(('days', 0, 'services', 0, 'options', 1, 'labels', 0, 'name'), id='label-name'),
    pytest.param(
        ('days', 0, 'services', 1, 'options', 0, 'allergens', 0, 'name'),
        id='allergen-name',
    ),
    pytest.param(('days', 0, 'services', 0, 'options', 0, 'origins', 0, 'ingredient'), id='origin-ingredient'),
    pytest.param(('days', 0, 'services', 0, 'options', 0, 'origins', 0, 'text'), id='origin-text'),
    pytest.param(('days', 0, 'services', 0, 'options', 0, 'note'), id='option-note'),
)


def patient_snapshot_with_probe(field: str, value: object) -> dict:
    snapshot = deepcopy(patient_snapshot())
    option = snapshot['days'][0]['services'][0]['options'][0]
    option[field] = deepcopy(value)
    return snapshot


def patient_snapshot_with_path(path: tuple[str | int, ...], value: object) -> dict:
    snapshot = deepcopy(patient_snapshot())
    target: Any = snapshot
    for part in path[:-1]:
        target = target[part]
    target[path[-1]] = deepcopy(value)
    return snapshot


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    application = Flask(
        'public-contracts',
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
    )
    application.config.update(
        TESTING=True,
        SECRET_KEY='public-contract-tests',
        DEMO_MODE=True,
        DEMO_TODAY='2026-09-01',
        LAST_GOOD_DIR=str(ROOT / '.test-last-good'),
    )
    application.extensions['cafeteria_db'] = object()
    application.add_template_filter(lambda value: value, 'date_long')
    application.add_template_filter(lambda value: value, 'date_short')
    application.add_template_filter(lambda value: int(value) / 100, 'chf')
    application.add_template_filter(lambda value: 36, 'iso_week')
    application.register_blueprint(public_routes.bp)
    application.register_blueprint(api_routes.bp)
    application.register_blueprint(signage_routes.bp)
    application.register_blueprint(admin_routes.bp)
    monkeypatch.setattr(
        role_module,
        'load_user_authorization',
        lambda _engine, user_id: AuthorizationState(
            user_id, 'Test', 'local', 1, ('Cafeteria.Editor',)
        ),
    )

    snapshots = {
        'staff_guest': cafeteria_snapshot(),
        'patient': patient_snapshot(),
    }

    def fake_active_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict:
        return deepcopy(snapshots[profile_code])

    monkeypatch.setattr(public_routes, 'active_snapshot', fake_active_snapshot)
    return application


@pytest.mark.parametrize('path', PUBLIC_QUERY_PATHS)
def test_public_endpoints_reject_every_query_parameter(app: Flask, path: str) -> None:
    response = app.test_client().get(f'{path}?preview=1')

    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize('path', PUBLIC_QUERY_PATHS)
@pytest.mark.parametrize('query_string', ('&&', '&', '=', '&&preview', 'date=2026-09-04'))
def test_public_endpoints_reject_raw_query_string_sequences(
    app: Flask,
    path: str,
    query_string: str,
) -> None:
    response = app.test_client().get(path, query_string=query_string)

    assert response.status_code == 400
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize(
    'path',
    (
        '/cafeteria/heute/',
        '/cafeteria/wochenangebot/',
        '/patienten/heute/',
        '/patienten/wochenplan/',
        '/druck/cafeteria/woche',
        '/druck/patienten/woche',
        '/api/v1/published/cafeteria',
        '/api/v1/published/patienten',
        '/signage/cafeteria/tag',
        '/signage/cafeteria/woche',
        '/signage/patienten/tag',
        '/signage/patienten/woche',
    ),
)
def test_no_snapshot_returns_explicit_non_cacheable_failure(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    def no_snapshot(
        _engine: object,
        _profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> None:
        return None

    monkeypatch.setattr(public_routes, 'active_snapshot', no_snapshot)

    response = app.test_client().get(path)

    assert response.status_code == 404
    assert response.headers['Cache-Control'] == 'no-store'


@pytest.mark.parametrize(
    'path',
    (
        '/patienten/heute/',
        '/patienten/wochenplan/',
        '/druck/patienten/woche',
        '/api/v1/published/patienten',
        '/signage/patienten/tag',
        '/signage/patienten/woche',
    ),
)
def test_patient_http_outputs_hide_internal_validation_categories(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    def invalid_snapshot(*_args: object, **_kwargs: object) -> None:
        raise ValueError('Patienten-Snapshot enthält unzulässige Kostenschlüssel.')

    monkeypatch.setattr(public_routes, 'active_snapshot', invalid_snapshot)
    response = app.test_client().get(path)
    body = response.get_data(as_text=True)

    assert response.status_code == 404
    assert response.headers['Cache-Control'] == 'no-store'
    assert re.search(r'CHF|Intern|Extern|0\.00|Preis|price|rappen|kosten|cost', body, re.I) is None


@pytest.mark.parametrize('demo_today', ('2026-09-05', '2026-09-06'))
@pytest.mark.parametrize('path', ('/cafeteria/heute/', '/signage/cafeteria/tag'))
def test_cafeteria_weekend_is_closed_without_patient_or_friday_fallback(
    app: Flask,
    demo_today: str,
    path: str,
) -> None:
    app.config['DEMO_TODAY'] = demo_today
    response = app.test_client().get(path)
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Cafeteria geschlossen' in body
    assert 'Gebratenes Zanderfilet' not in body
    assert 'Falafel-Teller' not in body
    assert 'Griessbrei mit Zwetschgenkompott' not in body
    assert 'Pastetli mit Brätkügeli' not in body


@pytest.mark.parametrize(
    'path',
    (
        '/cafeteria/heute/',
        '/cafeteria/wochenangebot/',
        '/druck/cafeteria/woche',
        '/signage/cafeteria/tag',
        '/signage/cafeteria/woche',
    ),
)
def test_closed_cafeteria_weekday_renders_service_notice_without_patient_fallback(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    closed = deepcopy(cafeteria_snapshot())
    closed['days'][0]['services'][0] = {
        'meal_code': 'LUNCH',
        'meal_name': 'Mittag',
        'service_state': 'closed',
        'notice': 'Cafeteria wegen Wartung geschlossen',
        'options': [],
    }
    validate_snapshot_payload('staff_guest', closed)
    app.config['DEMO_TODAY'] = closed['days'][0]['date']

    def active_closed_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict:
        assert profile_code == 'staff_guest'
        return deepcopy(closed)

    monkeypatch.setattr(public_routes, 'active_snapshot', active_closed_snapshot)
    response = app.test_client().get(path)
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Cafeteria wegen Wartung geschlossen' in body
    assert 'Griessbrei mit Zwetschgenkompott' not in body
    assert 'Pastetli mit Brätkügeli' not in body


@pytest.mark.parametrize(
    ('path', 'revision'),
    (
        ('/cafeteria/heute/', 'CAF-2026-KW36-R1'),
        ('/cafeteria/wochenangebot/', 'CAF-2026-KW36-R1'),
        ('/patienten/heute/', 'PAT-2026-KW36-R1'),
        ('/patienten/wochenplan/', 'PAT-2026-KW36-R1'),
        ('/signage/cafeteria/tag', 'CAF-2026-KW36-R1'),
        ('/signage/cafeteria/woche', 'CAF-2026-KW36-R1'),
        ('/signage/patienten/tag', 'PAT-2026-KW36-R1'),
        ('/signage/patienten/woche', 'PAT-2026-KW36-R1'),
    ),
)
def test_day_and_week_responses_expose_their_profile_revision(
    app: Flask,
    path: str,
    revision: str,
) -> None:
    response = app.test_client().get(path)

    assert response.status_code == 200
    assert response.headers['X-Snapshot-Revision'] == revision


def test_demo_snapshots_pass_payload_validation() -> None:
    validate_snapshot_payload('patient', patient_snapshot())
    validate_snapshot_payload('staff_guest', cafeteria_snapshot())


@pytest.mark.parametrize(
    ('key', 'value'),
    (
        ('price', 1250),
        ('cost', 1250),
        ('amount', 1250),
        ('currency', 'CHF'),
        ('unitPrice', 1250),
        ('meal_cost', 1250),
        ('total-amount', 1250),
        ('currencyCode', 'CHF'),
        ('preis_betrag', 1250),
        ('waehrung', 'CHF'),
        ('billing_label', 'Intern'),
    ),
)
def test_patient_snapshot_rejects_price_keys(key: str, value: object) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][key] = value

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(
    'title',
    (
        'Intern Preis 12.50',
        'Extern',
        'CHF',
        '0.00',
        'Preis: 12.50',
        'Kosten 12.50',
        'Betrag: 12,50',
        'price = 12.50',
        'cost 12,50',
        'amount 12.50',
        'internal',
        'external',
        'currency',
        'EUR 12.50',
        'Fr. 12.50',
        '12,50 CHF',
        '€ 12,50',
        '0,00',
        '0.–',
        '0.-',
        '50 Rappen',
        'inkludiert',
        'inbegriffen',
        'gratis',
        'kostenlos',
        'Interne',
        'Externen',
    ),
)
def test_patient_snapshot_rejects_price_values(title: str) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0]['title'] = title

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


def test_patient_snapshot_rejects_intern_label() -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0]['labels'] = [
        {'code': 'BILLING', 'name': 'Intern'},
    ]

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


def test_patient_snapshot_rejects_price_code_with_decimal_name() -> None:
    snapshot = patient_snapshot_with_probe('labels', [{'code': 'PRICE', 'name': '12.50'}])

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(('field', 'value'), PATIENT_REVIEWER_PROBES)
def test_patient_snapshot_rejects_reviewer_bypasses(field: str, value: object) -> None:
    snapshot = patient_snapshot_with_probe(field, value)

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(
    ('container', 'key', 'value'),
    (
        ('option', 'weekday', 'Montag'),
        ('option', 'pri\u200bce', '12.50'),
        ('option', 'unitPrice', '12.50'),
        ('option', 'unit_price', '12.50'),
        ('option', 'unit-price', '12.50'),
        ('label', 'title', 'Vegan'),
        ('label', 'rate', '12.50'),
    ),
)
def test_patient_snapshot_rejects_keys_outside_exact_nested_schema(
    container: str,
    key: str,
    value: object,
) -> None:
    snapshot = deepcopy(patient_snapshot())
    option = snapshot['days'][0]['services'][0]['options'][0]
    if container == 'label':
        option['labels'] = [{'code': 'VEGAN', 'name': 'Vegan'}]
    target = option if container == 'option' else option['labels'][0]
    target[key] = value

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(('key', 'value'), PATIENT_RESERVED_KEY_PROBES)
@pytest.mark.parametrize('path', PATIENT_OUTPUT_PATHS)
def test_reserved_patient_key_is_rejected_before_every_output_channel(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    key: str,
    value: object,
) -> None:
    tainted_snapshot = deepcopy(patient_snapshot())
    tainted_snapshot['days'][0]['services'][0]['options'][0][key] = value

    def active_tainted_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict:
        validate_snapshot_payload(profile_code, tainted_snapshot)
        return deepcopy(tainted_snapshot)

    monkeypatch.setattr(public_routes, 'active_snapshot', active_tainted_snapshot)
    monkeypatch.setattr(admin_routes, 'active_snapshot', active_tainted_snapshot)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session['user'] = {'id': 1, 'name': 'Test'}
        flask_session['authz_version'] = 1

    response = client.get(path)
    body = response.get_data(as_text=True)

    assert response.status_code == 404
    assert re.search(
        r'CHF|Intern|Extern|0\.00|Preis|price|rappen|kosten|cost',
        body,
        re.I,
    ) is None


@pytest.mark.parametrize(
    'character',
    PATIENT_UNSAFE_FORMAT_CHARACTERS,
    ids=lambda character: f'U+{ord(character):04X}',
)
def test_patient_snapshot_rejects_every_unicode_format_or_bidi_character(
    character: str,
) -> None:
    snapshot = patient_snapshot_with_probe('description', f'Gemüse{character}pfanne')

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(
    'character',
    PATIENT_UNSAFE_FORMAT_CHARACTERS,
    ids=lambda character: f'U+{ord(character):04X}',
)
def test_patient_snapshot_rejects_every_unicode_format_or_bidi_character_in_key(
    character: str,
) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][f'PRI{character}CE'] = 1250

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize('path', PATIENT_FREE_TEXT_PATHS)
def test_patient_snapshot_rejects_numeric_tokens_in_every_free_text_field(
    path: tuple[str | int, ...],
) -> None:
    value = '12.50 pro Menü' if path[-1] == 'note' else 'Ausgabe bis 12.50 Uhr'
    snapshot = patient_snapshot_with_path(path, value)

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(
    ('code', 'name'),
    (
        ('VEGETARIAN', 'Vegetarisch'),
        ('VEGAN', 'Vegan'),
        ('LACTOSE_FREE', 'Laktosefrei'),
        ('GLUTEN_FREE', 'Glutenfrei'),
    ),
)
def test_patient_snapshot_allows_fixed_label_codes(code: str, name: str) -> None:
    snapshot = patient_snapshot_with_probe('labels', [{'code': code, 'name': name}])

    validate_snapshot_payload('patient', snapshot)


def test_patient_snapshot_rejects_unknown_label_code() -> None:
    snapshot = patient_snapshot_with_probe('labels', [{'code': 'CHEF_SPECIAL', 'name': 'Spezial'}])

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


def test_patient_validation_error_never_reflects_injected_key_or_value() -> None:
    """Returning key paths in validation errors creates a cross-channel reflection sink."""
    injected_key = 'PRI\u2066CE'
    injected_value = 'CHF Intern Extern 0.00 Rappen'
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][injected_key] = injected_value

    with pytest.raises(ValueError) as captured:
        validate_snapshot_payload('patient', snapshot)

    message = str(captured.value)
    assert injected_key not in message
    assert injected_value not in message
    assert re.search(r'CHF|Intern|Extern|0\.00|Preis|price|rappen', message, re.I) is None


@pytest.mark.parametrize(
    'path',
    (
        '/patienten/heute/',
        '/patienten/wochenplan/',
        '/druck/patienten/woche',
        '/signage/patienten/tag',
        '/signage/patienten/woche',
    ),
)
def test_each_closed_patient_meal_renders_its_own_notice(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
) -> None:
    """Using day.notice hides one of two independently closed services."""
    closed = deepcopy(patient_snapshot())
    closed['days'][0]['services'][0] = {
        'meal_code': 'LUNCH',
        'meal_name': 'Mittag',
        'service_state': 'closed',
        'notice': 'Mittagsservice geschlossen',
        'options': [],
    }
    closed['days'][0]['services'][1] = {
        'meal_code': 'DINNER',
        'meal_name': 'Abend',
        'service_state': 'holiday',
        'notice': 'Abendservice entfällt',
        'options': [],
    }
    validate_snapshot_payload('patient', closed)
    app.config['DEMO_TODAY'] = closed['days'][0]['date']

    def active_closed_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict:
        assert profile_code == 'patient'
        return deepcopy(closed)

    monkeypatch.setattr(public_routes, 'active_snapshot', active_closed_snapshot)
    response = app.test_client().get(path)
    body = response.get_data(as_text=True)

    assert response.status_code == 200
    assert 'Mittagsservice geschlossen' in body
    assert 'Abendservice entfällt' in body


@pytest.mark.parametrize(
    ('field', 'value'),
    (
        ('title', 'Internationale Gemüsepfanne'),
        ('title', 'Preiselbeerkompott'),
        ('title', 'Costine di maiale'),
        ('title', 'Schonkost'),
        ('title', 'Vollkost'),
        ('title', 'Kaffeecreme'),
        ('title', 'Eiskaffee'),
        ('title', 'Gebratenes Gemüse'),
        ('title', 'Marinierte Costine di maiale'),
        ('title', 'Kompott aus Preiselbeeren'),
        ('title', 'Aprikosenpraline'),
        ('title', 'Chili sin Carne'),
        ('description', 'International gewürzt'),
        ('description', 'Externalitäten der Landwirtschaft'),
        ('note', 'Ausgabe bis 11.30 Uhr'),
        ('note', 'Ausgabe bis 11.00 Uhr'),
        ('note', 'Ausgabe ab 11:30 Uhr'),
        ('note', 'Ausgabe ab 00.00 Uhr'),
        ('note', 'Ausgabe ab 23:59 Uhr'),
        ('note', 'Serviert um 12:34 Uhr'),
        ('note', 'Therapie um 08.05 Uhr'),
        ('note', 'Ausgabe bis １２:５０ Uhr'),
        ('note', 'Therapie um ١٢:٥٠ Uhr'),
        ('note', 'Serviert um 00:00 Uhr'),
        ('note', 'Therapie um 23:59 Uhr'),
    ),
)
def test_patient_snapshot_allows_menu_text_and_opening_time(field: str, value: str) -> None:
    snapshot = patient_snapshot_with_probe(field, value)

    validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(
    'value',
    (
        'Ausgabe ab 24.00 Uhr',
        'Ausgabe ab 11.60 Uhr',
        'Ausgabe ab 7.30 Uhr',
        'Ausgabe ab 11.30',
        'Therapie um ٢٤:٠٠ Uhr',
        'Menü 12',
        'Menü Ⅻ',
        'Menü 十二',
    ),
)
def test_patient_snapshot_rejects_invalid_or_non_clock_numeric_text(value: str) -> None:
    snapshot = patient_snapshot_with_probe('note', value)

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(('field', 'value'), PATIENT_REVIEWER_PROBES)
@pytest.mark.parametrize('path', PATIENT_OUTPUT_PATHS)
def test_patient_price_probe_is_rejected_before_every_output_channel(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    field: str,
    value: object,
) -> None:
    tainted_snapshot = patient_snapshot_with_probe(field, value)

    def active_tainted_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict:
        validate_snapshot_payload(profile_code, tainted_snapshot)
        return deepcopy(tainted_snapshot)

    monkeypatch.setattr(public_routes, 'active_snapshot', active_tainted_snapshot)
    monkeypatch.setattr(admin_routes, 'active_snapshot', active_tainted_snapshot)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session['user'] = {'id': 1, 'name': 'Test'}
        flask_session['authz_version'] = 1

    response = client.get(path)
    body = response.get_data(as_text=True)

    assert response.status_code == 404
    assert re.search(
        r'CHF|Intern|Extern|0\.00|Preis|price|rappen|kosten|cost',
        body,
        re.I,
    ) is None


def test_patient_api_and_signage_never_use_cafeteria_payload(app: Flask) -> None:
    client = app.test_client()
    api_response = client.get('/api/v1/published/patienten')
    signage = client.get('/signage/patienten/woche').get_data(as_text=True)

    assert api_response.json['profile_code'] == 'patient'
    assert 'prices' not in api_response.get_data(as_text=True)
    assert 'CHF' not in signage
    assert 'Kichererbsen-Curry' not in signage
    assert 'Pastetli mit Brätkügeli' in signage
