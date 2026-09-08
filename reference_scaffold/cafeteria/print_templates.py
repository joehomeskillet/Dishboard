"""Revisioned print drafts; archive writes use v2, explicit layout writes use v3.

After a v2 write, rollback requires a reader/writer retaining all archive guards;
old strict v1 applications cannot read these documents. Layouts require a v3
reader. Historical revision configs stay unchanged; never downgrade the JSON.
"""
from __future__ import annotations

import copy
import json
import re
from collections.abc import Mapping
from datetime import date, datetime, timezone
from typing import Any
from uuid import uuid4

from sqlalchemy import Connection, Engine, text
from sqlalchemy.exc import DBAPIError

from .print_template_config import (
    PROFILES, PrintTemplateConfig, PrintTemplateValidationError, default_config, plain_text, validate_config,
)

MAX_TEMPLATES = 10
MAX_REVISIONS = 50
SETTING_PREFIX = 'print_templates.v1.'
IDENTIFIER = re.compile(r'(?:standard|[0-9a-f]{32})')


class PrintTemplateConflictError(ValueError):
    """Another administrator has changed this profile's templates."""


class PrintTemplateStateError(ValueError):
    """Stored data is invalid; refuse to overwrite it or print different defaults."""


def default_document() -> dict[str, Any]:
    return {
        'schema_version': 2, 'version': 0, 'active_template': 'standard', 'active_revision': 1,
        'templates': [{'id': 'standard', 'archived': False, 'current_revision': 1, 'revisions': [{
            'id': 1, 'name': 'Standard', 'config': default_config(),
            'created_at': None, 'created_by': None, 'restored_from': None,
        }]}],
    }


def template_revision(document: dict[str, Any], template_id: str, revision_id: int | None = None) -> dict[str, Any]:
    template = next((item for item in document['templates'] if item['id'] == template_id), None)
    if template is None:
        raise LookupError('Vorlage nicht gefunden.')
    revision_id = template['current_revision'] if revision_id is None else revision_id
    revision = next((item for item in template['revisions'] if item['id'] == revision_id), None)
    if revision is None:
        raise LookupError('Vorlagenrevision nicht gefunden.')
    return revision


def _integer(value: Any, minimum: int, maximum: int) -> bool:
    return type(value) is int and minimum <= value <= maximum


def _require(condition: object) -> None:
    if not condition:
        raise ValueError('Ungültige Vorlagenstruktur.')


def _validate_document(value: Any, profile: str) -> dict[str, Any]:
    try:
        _require(isinstance(value, dict) and set(value) == set(default_document()))
        _require(type(value['schema_version']) is int and value['schema_version'] in {1, 2, 3})
        schema_version = value['schema_version']
        _require(_integer(value['version'], 0, 2**63 - 2))
        templates = value['templates']
        _require(isinstance(templates, list) and 1 <= len(templates) <= MAX_TEMPLATES)
        ids: set[str] = set()
        for template in templates:
            keys = {'id', 'current_revision', 'revisions'}
            if schema_version >= 2:
                keys.add('archived')
            _require(isinstance(template, dict) and set(template) == keys)
            if schema_version >= 2:
                _require(type(template['archived']) is bool)
            _require(isinstance(template['id'], str) and IDENTIFIER.fullmatch(template['id']))
            _require(template['id'] not in ids)
            ids.add(template['id'])
            revisions = template['revisions']
            _require(isinstance(revisions, list) and 1 <= len(revisions) <= MAX_REVISIONS)
            _require(_integer(template['current_revision'], 1, len(revisions)))
            _require(template['current_revision'] == len(revisions))
            for number, revision in enumerate(revisions, 1):
                _require(isinstance(revision, dict) and set(revision) == {
                    'id', 'name', 'config', 'created_at', 'created_by', 'restored_from',
                })
                _require(type(revision['id']) is int and revision['id'] == number)
                _require(plain_text(revision['name'], 'name', 60, required=True) == revision['name'])
                _require(validate_config(revision['config'], profile) == revision['config'])
                _require(schema_version == 3 or 'layout' not in revision['config'])
                _require(revision['created_by'] is None or _integer(revision['created_by'], 1, 2**63 - 1))
                stamp = revision['created_at']
                _require(stamp is None or (isinstance(stamp, str) and len(stamp) <= 40 and datetime.fromisoformat(stamp).tzinfo))
                source = revision['restored_from']
                _require(source is None or _integer(source, 1, number - 1))
        _require(isinstance(value['active_template'], str) and value['active_template'] in ids)
        _require(_integer(value['active_revision'], 1, MAX_REVISIONS))
        template_revision(value, value['active_template'], value['active_revision'])
        _require(not next(item for item in templates if item['id'] == value['active_template']).get('archived', False))
    except (KeyError, TypeError, ValueError, LookupError) as error:
        raise PrintTemplateStateError('Gespeicherte Druckvorlagen sind ungültig. Bitte Administration verständigen.') from error
    document = copy.deepcopy(value)
    # Normalize legacy reads in memory only. The successful CAS writer upgrades atomically.
    document['schema_version'] = max(2, schema_version)
    for template in document['templates']:
        template.setdefault('archived', False)
    return document


def read_templates(connection: Connection, profile: str) -> dict[str, Any]:
    if profile not in PROFILES:
        raise PrintTemplateValidationError('Unbekanntes Druckprofil.')
    row = connection.execute(text('''
        SELECT setting_value FROM cafeteria.settings
        WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=:key
    '''), {'key': SETTING_PREFIX + profile}).one_or_none()
    return default_document() if row is None else _validate_document(row.setting_value, profile)


def active_template(connection: Connection, profile: str) -> tuple[PrintTemplateConfig, str]:
    document = read_templates(connection, profile)
    template_id, revision_id = document['active_template'], document['active_revision']
    return template_revision(document, template_id, revision_id)['config'], f'{template_id}:{revision_id}'


def _authorize(connection: Connection, actor_id: int, authz_version: int) -> None:
    if not _integer(actor_id, 1, 2**63 - 1) or not _integer(authz_version, 1, 2**63 - 1):
        raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
    # Existing settings guard locks IAM roles before the original actor. Runtime
    # has EXECUTE permission, deliberately no direct UPDATE privilege on roles.
    try:
        connection.execute(text('SELECT cafeteria.lock_operations_actor(:actor, :version)'),
                           {'actor': actor_id, 'version': authz_version})
    except DBAPIError as error:
        if getattr(error.orig, 'sqlstate', None) == '42501':
            raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.') from error
        raise


def _append_revision(template: dict[str, Any], revision: dict[str, Any], actor_id: int) -> None:
    if len(template['revisions']) >= MAX_REVISIONS:
        raise PrintTemplateValidationError('50 Revisionen erreicht. Bitte eine neue Vorlagenkopie erstellen.')
    revision.update(
        id=len(template['revisions']) + 1, created_by=actor_id,
        created_at=datetime.now(timezone.utc).isoformat(),
    )
    template['revisions'].append(revision)
    template['current_revision'] = revision['id']


def change_template(
    engine: Engine, profile: str, actor_id: int, authz_version: int, expected_version: int,
    template_id: str, action: str, *, revision_id: int | None = None,
    name: str | None = None, config: Mapping[str, object] | None = None, week: date | None = None,
) -> tuple[dict[str, Any], str]:
    """Save/copy/restore drafts or activate one checked revision, under one row lock."""
    if profile not in PROFILES or action not in {'save', 'copy', 'restore', 'activate', 'archive', 'reactivate'}:
        raise PrintTemplateValidationError('Vorlagenaktion ist ungültig.')
    if not _integer(expected_version, 0, 2**63 - 2):
        raise PrintTemplateValidationError('Versionsnummer ist ungültig.')
    if revision_id is not None and not _integer(revision_id, 1, MAX_REVISIONS):
        raise PrintTemplateValidationError('Revisionsnummer ist ungültig.')
    if action in {'save', 'copy'}:
        name = plain_text(name, 'name', 60, required=True)
    if action == 'save':
        config = validate_config(config, profile)
    with engine.begin() as connection:
        _authorize(connection, actor_id, authz_version)
        # NULLS NOT DISTINCT uniqueness makes the first concurrent save safe too.
        connection.execute(text('''
            INSERT INTO cafeteria.settings(setting_key, setting_value, updated_by)
            VALUES (:key, CAST(:document AS jsonb), :actor)
            ON CONFLICT (location_id, profile_id, setting_key) DO NOTHING
        '''), {'key': SETTING_PREFIX + profile, 'document': json.dumps(default_document()), 'actor': actor_id})
        value = connection.execute(text('''
            SELECT setting_value FROM cafeteria.settings
            WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=:key FOR UPDATE
        '''), {'key': SETTING_PREFIX + profile}).scalar_one()
        document = _validate_document(value, profile)
        if document['version'] != expected_version:
            raise PrintTemplateConflictError('Vorlagen wurden zwischenzeitlich geändert. Bitte neu laden; Ihre Eingaben wurden nicht gespeichert.')
        if document['version'] == 2**63 - 2:
            raise PrintTemplateConflictError('Versionsgrenze erreicht. Bitte Administration verständigen.')
        source = copy.deepcopy(template_revision(document, template_id, revision_id))
        template = next(item for item in document['templates'] if item['id'] == template_id)
        if template['archived'] and action in {'save', 'restore', 'activate'}:
            raise PrintTemplateConflictError('Archivierte Vorlage zuerst reaktivieren.')
        if action == 'archive':
            if template['archived']:
                raise PrintTemplateConflictError('Vorlage ist bereits archiviert.')
            if document['active_template'] == template_id:
                raise PrintTemplateConflictError('Aktive Vorlage kann nicht archiviert werden. Zuerst eine andere Vorlage aktivieren.')
            template['archived'] = True
        elif action == 'reactivate':
            if not template['archived']:
                raise PrintTemplateConflictError('Vorlage ist bereits verfügbar.')
            template['archived'] = False
        elif action == 'activate':
            _validate_week(connection, profile, week, source['config'])
            document.update(active_template=template_id, active_revision=source['id'])
        elif action == 'copy':
            if len(document['templates']) >= MAX_TEMPLATES:
                raise PrintTemplateValidationError('Höchstens zehn Vorlagen je Bereich sind möglich.')
            template_id = uuid4().hex
            template = {'id': template_id, 'archived': False, 'current_revision': 0, 'revisions': []}
            source.update(name=name, restored_from=None)
            _append_revision(template, source, actor_id)
            document['templates'].append(template)
        else:
            source.update(restored_from=source['id'] if action == 'restore' else None)
            if action == 'save':
                source.update(name=name, config=config)
            _append_revision(template, source, actor_id)
        document['version'] += 1
        if action == 'save' and config is not None and 'layout' in config:
            document['schema_version'] = 3
        connection.execute(text('''
            UPDATE cafeteria.settings SET setting_value=CAST(:document AS jsonb),
                updated_by=:actor, updated_at=clock_timestamp()
            WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=:key
        '''), {'key': SETTING_PREFIX + profile, 'document': json.dumps(document), 'actor': actor_id})
    return document, template_id


def _validate_week(connection: Connection, profile: str, week: date | None, config: Mapping[str, object]) -> None:
    from .admin.week_pdf import render_week_pdf
    from .print_branding import load_pdf_branding
    from .workflow_store import load_draft_connection

    if type(week) is not date or week.isoweekday() != 1:
        raise PrintTemplateValidationError('Bitte eine gespeicherte Woche ab Montag auswählen.', 'week')
    # Reuse the scoped week lock used by all menu writes.
    draft = load_draft_connection(connection, profile, week, lock_week=True)
    render_week_pdf(draft, profile, week, config, branding=load_pdf_branding(connection, profile, config))
