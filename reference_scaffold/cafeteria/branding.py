"""Atomic branding drafts and activation, isolated from publication/template state."""
from __future__ import annotations

import copy
import json
from datetime import datetime, timezone
from typing import Any

from sqlalchemy import Connection, Engine, text

from .branding_assets import LogoAsset, load_logo, store_logo
from .branding_config import (
    BrandConfig, BrandRevision, BrandingValidationError, default_config, validate_config, validate_name,
)

SETTING_KEY = 'branding.v1'
MAX_REVISIONS = 500


class BrandingConflictError(ValueError):
    """A concurrent administrator has changed branding."""


class BrandingStateError(ValueError):
    """Refuse to overwrite invalid persisted branding."""


def default_document() -> dict[str, Any]:
    return {'schema_version': 1, 'version': 0, 'active_revision': 1, 'revisions': [{
        'id': 1, 'name': 'Südhang Standard', 'config': default_config(),
        'created_at': None, 'created_by': None, 'restored_from': None,
        'activated_at': None, 'activated_by': None, 'published': True,
    }]}


def _integer(value: Any, minimum: int, maximum: int = 2**63 - 2) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _require(condition: object) -> None:
    if not condition:
        raise ValueError('Ungültige Markenstruktur.')


def _validate_document(value: Any) -> dict[str, Any]:
    try:
        _require(isinstance(value, dict) and set(value) == set(default_document()))
        _require(type(value['schema_version']) is int and value['schema_version'] == 1)
        _require(_integer(value['version'], 0))
        revisions = value['revisions']
        _require(isinstance(revisions, list) and 1 <= len(revisions) <= MAX_REVISIONS)
        for number, revision in enumerate(revisions, 1):
            _require(isinstance(revision, dict) and set(revision) == set(default_document()['revisions'][0]))
            _require(type(revision['id']) is int and revision['id'] == number)
            _require(validate_name(revision['name']) == revision['name'])
            _require(validate_config(revision['config']) == revision['config'])
            _require(type(revision['published']) is bool)
            for field in ('created_by', 'activated_by'):
                _require(revision[field] is None or _integer(revision[field], 1))
            for field in ('created_at', 'activated_at'):
                stamp = revision[field]
                _require(stamp is None or (isinstance(stamp, str) and len(stamp) <= 40 and datetime.fromisoformat(stamp).tzinfo))
            source = revision['restored_from']
            _require(source is None or _integer(source, 1, number - 1))
            if number == 1:
                _require(revision == default_document()['revisions'][0])
            else:
                _require(revision['created_at'] is not None and revision['created_by'] is not None)
                _require(revision['published'] == (revision['activated_at'] is not None))
                _require(revision['published'] == (revision['activated_by'] is not None))
        _require(_integer(value['active_revision'], 1, len(revisions)))
        _require(revisions[value['active_revision'] - 1]['published'])
    except (KeyError, TypeError, ValueError, IndexError) as error:
        raise BrandingStateError('Gespeicherte Markeneinstellungen sind ungültig. Bitte Administration verständigen.') from error
    return copy.deepcopy(value)


def read_branding(connection: Connection) -> dict[str, Any]:
    row = connection.execute(text('''
        SELECT setting_value FROM cafeteria.settings
        WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=:key
    '''), {'key': SETTING_KEY}).one_or_none()
    return default_document() if row is None else _validate_document(row.setting_value)


def branding_revision(document: dict[str, Any], revision_id: int) -> BrandRevision:
    if not _integer(revision_id, 1, len(document['revisions'])):
        raise LookupError('Markenrevision nicht gefunden.')
    revision = document['revisions'][revision_id - 1]
    return BrandRevision(revision['id'], revision['name'], copy.deepcopy(revision['config']))


def active_branding(connection: Connection) -> BrandRevision:
    document = read_branding(connection)
    return branding_revision(document, document['active_revision'])


def public_revision(document: dict[str, Any], revision_id: int) -> BrandRevision:
    revision = branding_revision(document, revision_id)
    if not document['revisions'][revision_id - 1]['published']:
        raise LookupError('Markenrevision ist nicht veröffentlicht.')
    return revision


def authorize_branding(connection: Connection, actor_id: int, authz_version: int) -> None:
    if not _integer(actor_id, 1) or not _integer(authz_version, 1):
        raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
    user = connection.execute(text('''
        SELECT id FROM cafeteria.users WHERE id=:actor AND authz_version=:version
        AND disabled_at IS NULL FOR SHARE
    '''), {'actor': actor_id, 'version': authz_version}).scalar_one_or_none()
    admin = connection.execute(text('''
        SELECT 1 FROM cafeteria.user_role_cache r JOIN cafeteria.application_roles a
        ON a.role_code=r.role_code AND a.active WHERE r.user_id=:actor AND r.role_code='Cafeteria.Admin'
    '''), {'actor': actor_id}).scalar_one_or_none()
    if user is None or admin is None:
        raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')


def change_branding(
    engine: Engine, actor_id: int, authz_version: int, expected_version: int, action: str, *,
    name: str | None = None, config: BrandConfig | None = None,
    revision_id: int | None = None, logo: LogoAsset | None = None,
) -> dict[str, Any]:
    if action not in {'save', 'activate', 'restore', 'reset'} or not _integer(expected_version, 0):
        raise BrandingValidationError('Markenaktion oder Versionsnummer ist ungültig.')
    if action in {'activate', 'restore'} and not _integer(revision_id, 1, MAX_REVISIONS):
        raise BrandingValidationError('Bitte eine vorhandene Revision auswählen.')
    if logo is not None and action != 'save':
        raise BrandingValidationError('Ein Logo kann nur mit einem Entwurf gespeichert werden.')
    if action == 'save':
        name = validate_name(name)
        config = validate_config(config)
        if logo is not None and config['logo_sha256'] != logo.sha256:
            raise BrandingValidationError('Logo und Entwurf stimmen nicht überein.')
    with engine.begin() as connection:
        authorize_branding(connection, actor_id, authz_version)
        connection.execute(text('''
            INSERT INTO cafeteria.settings(setting_key, setting_value, updated_by)
            VALUES (:key, CAST(:document AS jsonb), :actor)
            ON CONFLICT (location_id, profile_id, setting_key) DO NOTHING
        '''), {'key': SETTING_KEY, 'document': json.dumps(default_document()), 'actor': actor_id})
        value = connection.execute(text('''
            SELECT setting_value FROM cafeteria.settings
            WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=:key FOR UPDATE
        '''), {'key': SETTING_KEY}).scalar_one()
        document = _validate_document(value)
        if document['version'] != expected_version:
            raise BrandingConflictError('Die Marke wurde zwischenzeitlich geändert. Bitte neu laden; Ihre Eingaben wurden nicht gespeichert.')
        stamp = datetime.now(timezone.utc).isoformat()
        if action == 'activate':
            selected = branding_revision(document, revision_id)  # type: ignore[arg-type]
            if selected.config['logo_sha256']:
                load_logo(connection, selected.config['logo_sha256'])
            stored = document['revisions'][selected.id - 1]
            if not stored['published']:
                stored.update(published=True, activated_at=stamp, activated_by=actor_id)
            document['active_revision'] = selected.id
        else:
            if len(document['revisions']) >= MAX_REVISIONS:
                raise BrandingValidationError('500 Markenrevisionen erreicht. Bestehende Revisionen können weiterhin aktiviert werden.')
            if action == 'restore':
                selected = branding_revision(document, revision_id)  # type: ignore[arg-type]
                name, config = selected.name, selected.config
            elif action == 'reset':
                name, config = 'Südhang Standard', default_config()
            assert config is not None
            if logo is not None:
                store_logo(connection, logo, actor_id)
            if config['logo_sha256']:
                load_logo(connection, config['logo_sha256'])
            document['revisions'].append({
                'id': len(document['revisions']) + 1, 'name': name, 'config': config,
                'created_at': stamp, 'created_by': actor_id,
                'restored_from': revision_id if action == 'restore' else None,
                'published': False, 'activated_at': None, 'activated_by': None,
            })
        document['version'] += 1
        connection.execute(text('''
            UPDATE cafeteria.settings SET setting_value=CAST(:document AS jsonb),
                updated_by=:actor, updated_at=clock_timestamp()
            WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=:key
        '''), {'key': SETTING_KEY, 'document': json.dumps(document), 'actor': actor_id})
    return document
