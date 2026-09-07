"""Python and PostgreSQL accept the same finite decimal domains."""
from decimal import Decimal

import pytest
from sqlalchemy import text
from sqlalchemy.exc import DBAPIError

from cafeteria.quantities import parse_factor, parse_quantity
from cafeteria.master_data_proposals import plain
from cafeteria.master_data_types import MasterDataValidationError
from test_master_data_db import (  # noqa: F401
    master, seeded_pg16, installed_pg16, pg16, app_engine,
)


@pytest.mark.parametrize('value', ['1', '0.000001', '999999999999.999999', '1000000000000',
    '0.0000001', '0', '-1', 'NaN', 'Infinity', '-Infinity', '1.0000000', '99999999999.999999999'])
@pytest.mark.parametrize('kind', ['quantity', 'factor'])
def test_numeric_domain_matches_python_without_rounding(master, kind, value):  # noqa: F811
    owner, _, _ = master
    parser = parse_factor if kind == 'factor' else parse_quantity
    try:
        parser(value)
        expected = True
    except ValueError:
        expected = False
    sql = {'factor': 'SELECT cafeteria.master_factor(CAST(:value AS numeric))',
           'quantity': 'SELECT cafeteria.master_quantity(CAST(:value AS numeric))'}[kind]
    with owner.connect() as c:
        assert c.execute(text(sql), {'value': value}).scalar_one() is expected


@pytest.mark.parametrize('value', [' Name  mit  Raum ', 'Cafe\u0301', '\u00a0Name\u00a0',
    'Name\nZeile', 'X\u200dY', 'X\u202eY', 'X\ue000Y', 'X\U000f0000Y', '<Name>', 'x'*121])
def test_text_normalization_matches_database(master, value):  # noqa: F811
    owner, _, _ = master
    try:
        expected = plain(value)
    except MasterDataValidationError:
        with pytest.raises(DBAPIError):
            with owner.begin() as c:
                c.execute(text('SELECT cafeteria.master_text(:value,120)'), {'value': value})
    else:
        with owner.connect() as c:
            assert c.execute(text('SELECT cafeteria.master_text(:value,120)'), {'value': value}).scalar_one() == expected


def test_canonical_units_and_contextual_units_have_exact_seed_values(master):  # noqa: F811
    owner, _, _ = master
    with owner.connect() as c:
        rows = c.execute(text('SELECT code,dimension,base_factor,active FROM cafeteria.measurement_units ORDER BY code')).all()
    assert rows == [('EL','volume',Decimal(15),True),('G','mass',Decimal(1),True),
        ('KG','mass',Decimal(1000),True),('L','volume',Decimal(1000),True),('ML','volume',Decimal(1),True),
        ('PORTION','contextual',None,True),('PRISE','contextual',None,True),('STK','count',Decimal(1),True),
        ('TL','volume',Decimal(5),True)]
