"""Persisted legacy print revisions and active-only brand resolution with PostgreSQL."""
from __future__ import annotations

import copy

from sqlalchemy import text

from cafeteria.branding import change_branding
from cafeteria.branding_assets import normalize_logo
from cafeteria.branding_config import default_config as brand_defaults
from cafeteria.print_branding import load_pdf_branding
from cafeteria.print_template_config import default_config, validate_config
from cafeteria.print_templates import SETTING_PREFIX, default_document, read_templates
from test_branding_store import _actor, _png, app, database_engine  # noqa: F401


def test_existing_documents_and_explicit_magenta_keep_their_meaning(app, database_engine):  # noqa: F811
    expected = copy.deepcopy(default_document())
    with database_engine.connect() as connection:
        for profile in ('patient', 'staff_guest'):
            assert read_templates(connection, profile) == expected
            assert load_pdf_branding(connection, profile, default_config()) is None
            explicit = {**default_config(), 'palette': 'brand'}
            assert validate_config(explicit, profile) == explicit
            assert load_pdf_branding(connection, profile, explicit) is None
        assert connection.execute(text('SELECT count(*) FROM cafeteria.settings WHERE setting_key LIKE :key'),
                                  {'key': SETTING_PREFIX + '%'}).scalar_one() == 0
        assert connection.execute(text("SELECT count(*) FROM cafeteria.settings WHERE setting_key='branding.v1'")).scalar_one() == 0


def test_only_activated_brand_and_its_immutable_logo_are_resolved(app, database_engine):  # noqa: F811
    actor, authz = _actor(app, database_engine)
    logo = normalize_logo(_png())
    config = {**brand_defaults(), 'font_body': 'carlito', 'font_heading': 'fira', 'logo_sha256': logo.sha256}
    template = {**default_config(), 'font': 'active_brand', 'palette': 'active_brand', 'logo': 'active_brand'}
    before = copy.deepcopy(template)
    change_branding(database_engine, actor, authz, 0, 'save', name='Neue Marke', config=config, logo=logo)
    with database_engine.connect() as connection:
        initial = load_pdf_branding(connection, 'patient', template)
        assert initial is not None and initial.revision_id == 1 and initial.logo_png is None
    change_branding(database_engine, actor, authz, 1, 'activate', revision_id=2)
    with database_engine.connect() as connection:
        active = load_pdf_branding(connection, 'patient', template)
        assert active is not None and active.revision_id == 2
        assert active.logo_png == logo.png
        assert active.font_body == 'carlito' and active.font_heading == 'fira'
        assert active.primary == (140, 28, 75) and active.accent == (53, 102, 111)
        override = load_pdf_branding(connection, 'patient', {**template, 'logo': 'none'})
        assert override is not None and override.logo_png is None
    assert template == before
