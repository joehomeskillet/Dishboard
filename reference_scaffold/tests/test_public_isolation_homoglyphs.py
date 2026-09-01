from __future__ import annotations

import sys
from copy import deepcopy
from pathlib import Path

import pytest
from flask import Flask

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'reference_scaffold'))
sys.path.insert(0, str(ROOT / 'tools'))

from cafeteria.admin import routes as admin_routes  # noqa: E402
from cafeteria.api import routes as api_routes  # noqa: E402
from cafeteria.db import validate_snapshot_payload  # noqa: E402
from cafeteria.public import routes as public_routes  # noqa: E402
from cafeteria.signage import routes as signage_routes  # noqa: E402
from demo_snapshots import cafeteria_snapshot, patient_snapshot  # noqa: E402

PATIENT_OUTPUT_PATHS = (
    '/patienten/heute/',
    '/patienten/wochenplan/',
    '/druck/patienten/woche',
    '/api/v1/published/patienten',
    '/signage/patienten/tag',
    '/signage/patienten/woche',
    '/admin/export/patienten.csv',
)

HOMOGLYPH_VALUE_PROBES = (
    pytest.param('title', 'C\ua730H zwölf fünfzig', id='ipa-smallcap-f-chf-amount'),
    pytest.param('title', 'zwölf Fr\u0251nken', id='ipa-alpha-franken'),
    pytest.param('title', 'Gesamtbetr\u0251g', id='ipa-alpha-gesamtbetrag'),
    pytest.param('description', 'C\ua730H zwölf fünfzig', id='ipa-chf-in-description'),
    pytest.param('note', 'zwölf Fr\u0251nken', id='ipa-franken-in-note'),
    pytest.param('title', 'C\ua730H', id='ipa-smallcap-f-chf-alone'),
    pytest.param('title', 'Fr\u0251nken', id='ipa-alpha-franken-alone'),
    pytest.param('title', 'betr\u0251g', id='ipa-alpha-betrag-alone'),
)

HOMOGLYPH_KEY_PROBES = (
    pytest.param('C\ua730H', '12.50', id='ipa-smallcap-f-chf-key'),
    pytest.param('Gesamtbetr\u0251g', 1250, id='ipa-alpha-gesamtbetrag-key'),
    pytest.param('Fr\u0251nken', 1250, id='ipa-alpha-franken-key'),
)

SAFE_MENU_PROBES = (
    pytest.param('title', 'Aufbewahrung im Kühlschrank', id='storage-note'),
    pytest.param('description', 'Aufbewahrung im Kühlschrank', id='storage-description'),
    pytest.param('note', 'Aufbewahrung im Kühlschrank', id='storage-option-note'),
    pytest.param('title', 'Schonkost', id='schonkost'),
    pytest.param('title', 'Vollkost', id='vollkost'),
    pytest.param('title', 'Aprikosenpraline', id='aprikosenpraline'),
    pytest.param('title', 'Chili sin Carne', id='chili'),
    pytest.param('title', 'Crème brûlée', id='accent-creme'),
    pytest.param('title', 'Rösti mit Gemüse', id='accent-roesti'),
    pytest.param('title', 'Poulet à la crème', id='accent-poulet'),
    pytest.param('title', 'Piña colada Dessert', id='accent-pina'),
    pytest.param('title', 'Mantı mit Joghurt', id='turkish-manti'),
    pytest.param('description', 'Mantı mit Joghurt', id='turkish-manti-description'),
    pytest.param('note', 'Mantı mit Joghurt', id='turkish-manti-note'),
    pytest.param('title', 'Œufs', id='ligature-oeufs'),
    pytest.param('title', 'Œufs brouillés', id='ligature-oeufs-dish'),
    pytest.param('title', 'Zwölf-Gewürze-Suppe', id='number-spice-soup'),
    pytest.param('title', 'Zwölf Kräuter Risotto', id='number-herb-risotto'),
    pytest.param('note', 'Ausgabe bis 11.30 Uhr', id='clock-note'),
    pytest.param('note', 'Serviert um 12:34 Uhr', id='clock-colon-note'),
)

CURRENCY_SYMBOL_VALUE_PROBES = (
    pytest.param('title', '€', id='euro-sign'),
    pytest.param('title', '£', id='pound-sign'),
    pytest.param('title', '¥', id='yen-sign'),
    pytest.param('title', '₣', id='franc-sign'),
    pytest.param('title', '₹', id='rupee-sign'),
    pytest.param('title', '₽', id='ruble-sign'),
    pytest.param('title', '₿', id='bitcoin-sign'),
    pytest.param('title', 'Menü €', id='menu-euro'),
    pytest.param('description', 'Menü €', id='menu-euro-description'),
    pytest.param('note', '£', id='pound-in-note'),
)

CURRENCY_SYMBOL_KEY_PROBES = (
    pytest.param('€', 1250, id='euro-key'),
    pytest.param('£', '12.50', id='pound-key'),
    pytest.param('Menü €', 1250, id='menu-euro-key'),
)

CURRENCY_COMPOUND_PROBES = (
    pytest.param('title', 'Währung', id='waehrung-umlaut'),
    pytest.param('title', 'Waehrung', id='waehrung-ascii'),
    pytest.param('title', 'Fremdwährung', id='fremdwaehrung'),
    pytest.param('title', 'Gesamtbetrag', id='gesamtbetrag-ascii'),
    pytest.param('title', 'zwölf Franken', id='spelled-franken-ascii'),
)

ASCII_IL_AND_FORMAT_VALUES = (
    pytest.param('title', 'PRlCE', id='ascii-l-price'),
    pytest.param('title', 'CHlF', id='ascii-l-chf'),
    pytest.param('title', 'Pre\u200bis', id='cf-zwsp-preis'),
    pytest.param('description', 'Gemüse\u2066pfanne', id='bidi-isolate'),
)

ASCII_IL_AND_FORMAT_KEYS = (
    pytest.param('PRlCE', 1250, id='ascii-l-price-key'),
    pytest.param('CHlF', '12.50', id='ascii-l-chf-key'),
    pytest.param('PRI\u200bCE', 1250, id='cf-zwsp-price-key'),
    pytest.param('PRI\u2066CE', 1250, id='bidi-isolate-price-key'),
)


def patient_snapshot_with_probe(field: str, value: object) -> dict:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][field] = deepcopy(value)
    return snapshot


@pytest.fixture
def app(monkeypatch: pytest.MonkeyPatch) -> Flask:
    application = Flask(
        'public-isolation-homoglyphs',
        template_folder=str(ROOT / 'reference_scaffold' / 'cafeteria' / 'templates'),
    )
    application.config.update(
        TESTING=True,
        SECRET_KEY='public-isolation-homoglyph-tests',
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

    def fake_active_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict:
        return deepcopy({'staff_guest': cafeteria_snapshot(), 'patient': patient_snapshot()}[profile_code])

    monkeypatch.setattr(public_routes, 'active_snapshot', fake_active_snapshot)
    return application


def assert_channel_rejects(app: Flask, monkeypatch: pytest.MonkeyPatch, path: str, snapshot: dict) -> None:
    def active_tainted_snapshot(
        _engine: object,
        profile_code: str,
        _requested_date: str,
        *,
        last_good_dir: str,
    ) -> dict:
        validate_snapshot_payload(profile_code, snapshot)
        return deepcopy(snapshot)

    monkeypatch.setattr(public_routes, 'active_snapshot', active_tainted_snapshot)
    monkeypatch.setattr(admin_routes, 'active_snapshot', active_tainted_snapshot)
    client = app.test_client()
    with client.session_transaction() as flask_session:
        flask_session['user'] = {'id': 1, 'name': 'Test'}
        flask_session['roles'] = ['Cafeteria.Editor']

    with pytest.raises(ValueError, match='unzulässig'):
        client.get(path)


@pytest.mark.parametrize(('field', 'value'), HOMOGLYPH_VALUE_PROBES)
def test_patient_snapshot_rejects_latin_ipa_price_homoglyphs(field: str, value: object) -> None:
    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', patient_snapshot_with_probe(field, value))


@pytest.mark.parametrize(('key', 'value'), HOMOGLYPH_KEY_PROBES)
def test_patient_snapshot_rejects_latin_ipa_price_homoglyph_keys(key: str, value: object) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][key] = value

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(('field', 'value'), HOMOGLYPH_VALUE_PROBES)
@pytest.mark.parametrize('path', PATIENT_OUTPUT_PATHS)
def test_homoglyph_value_is_rejected_before_every_output_channel(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    field: str,
    value: object,
) -> None:
    assert_channel_rejects(app, monkeypatch, path, patient_snapshot_with_probe(field, value))


@pytest.mark.parametrize(('key', 'value'), HOMOGLYPH_KEY_PROBES)
@pytest.mark.parametrize('path', PATIENT_OUTPUT_PATHS)
def test_homoglyph_key_is_rejected_before_every_output_channel(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    key: str,
    value: object,
) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][key] = value
    assert_channel_rejects(app, monkeypatch, path, snapshot)


@pytest.mark.parametrize(('field', 'value'), SAFE_MENU_PROBES)
def test_patient_snapshot_allows_storage_food_and_accented_menu_text(field: str, value: str) -> None:
    validate_snapshot_payload('patient', patient_snapshot_with_probe(field, value))


@pytest.mark.parametrize(('field', 'value'), CURRENCY_COMPOUND_PROBES)
def test_patient_snapshot_still_rejects_currency_and_amount_compounds(field: str, value: str) -> None:
    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', patient_snapshot_with_probe(field, value))


@pytest.mark.parametrize(('field', 'value'), ASCII_IL_AND_FORMAT_VALUES)
def test_patient_snapshot_still_rejects_ascii_il_cf_and_bidi_values(field: str, value: object) -> None:
    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', patient_snapshot_with_probe(field, value))


@pytest.mark.parametrize(('key', 'value'), ASCII_IL_AND_FORMAT_KEYS)
def test_patient_snapshot_still_rejects_ascii_il_cf_and_bidi_keys(key: str, value: object) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][key] = value

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(('field', 'value'), CURRENCY_SYMBOL_VALUE_PROBES)
def test_patient_snapshot_rejects_currency_symbols_in_values(field: str, value: object) -> None:
    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', patient_snapshot_with_probe(field, value))


@pytest.mark.parametrize(('key', 'value'), CURRENCY_SYMBOL_KEY_PROBES)
def test_patient_snapshot_rejects_currency_symbols_in_keys(key: str, value: object) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][key] = value

    with pytest.raises(ValueError, match='unzulässig'):
        validate_snapshot_payload('patient', snapshot)


@pytest.mark.parametrize(('field', 'value'), CURRENCY_SYMBOL_VALUE_PROBES)
@pytest.mark.parametrize('path', PATIENT_OUTPUT_PATHS)
def test_currency_symbol_value_is_rejected_before_every_output_channel(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    field: str,
    value: object,
) -> None:
    assert_channel_rejects(app, monkeypatch, path, patient_snapshot_with_probe(field, value))


@pytest.mark.parametrize(('key', 'value'), CURRENCY_SYMBOL_KEY_PROBES)
@pytest.mark.parametrize('path', PATIENT_OUTPUT_PATHS)
def test_currency_symbol_key_is_rejected_before_every_output_channel(
    app: Flask,
    monkeypatch: pytest.MonkeyPatch,
    path: str,
    key: str,
    value: object,
) -> None:
    snapshot = deepcopy(patient_snapshot())
    snapshot['days'][0]['services'][0]['options'][0][key] = value
    assert_channel_rejects(app, monkeypatch, path, snapshot)
