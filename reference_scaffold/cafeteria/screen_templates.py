"""Fixed web-week renderers and bounded, global, audited assignments."""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text
from sqlalchemy.engine import Connection, Engine
from sqlalchemy.exc import DBAPIError


class ScreenValidation(ValueError):
    pass


class ScreenStateError(ValueError):
    pass


class ScreenConflict(ValueError):
    pass


@dataclass(frozen=True)
class ScreenTemplate:
    id: str
    profile: str
    show_menu_images: bool
    renderer_revision: int = 1
    channel: str = 'web'
    period: str = 'week'

    @property
    def name(self) -> str:
        return 'Wochenplan mit Bildern' if self.show_menu_images else 'Wochenplan ohne Bilder'


REGISTRY = tuple(ScreenTemplate(f'{family}-week-{mode}', profile, mode == 'photo')
                 for family, profile in [('cafeteria', 'staff_guest'), ('patient', 'patient')]
                 for mode in ('photo', 'text'))
MAX_VERSION = 2**63 - 2


@dataclass(frozen=True)
class Assignment:
    version: int
    template: ScreenTemplate

    @property
    def revision(self) -> str:
        return f'{self.template.id}:{self.template.renderer_revision}:{self.version}'

    def document(self) -> dict[str, object]:
        return {'schema_version': 1, 'version': self.version, 'template_id': self.template.id,
                'renderer_revision': self.template.renderer_revision}


def choices(profile: str) -> tuple[ScreenTemplate, ...]:
    if profile not in ('staff_guest', 'patient'):
        raise ScreenValidation('Unbekannter Bereich.')
    return tuple(item for item in REGISTRY if item.profile == profile)


def key(profile: str) -> str:
    choices(profile)
    return f'screen_assignment.v1.{profile}.web.week'


def resolve(profile: str, template_id: str, revision: int = 1) -> ScreenTemplate:
    choices(profile)
    selected = next((item for item in REGISTRY if item.id == template_id), None)
    if selected is None:
        raise LookupError('Screen-Vorlage nicht gefunden.')
    if selected.profile != profile or type(revision) is not int or revision != selected.renderer_revision:
        raise ScreenValidation('Die Vorlage passt nicht zum gewählten Ziel.')
    return selected


def parse(value: object, profile: str) -> Assignment:
    try:
        if not isinstance(value, dict) or set(value) != {'schema_version', 'version', 'template_id', 'renderer_revision'}:
            raise ValueError
        if type(value['schema_version']) is not int or value['schema_version'] != 1:
            raise ValueError
        if type(value['version']) is not int or not 0 <= value['version'] <= MAX_VERSION:
            raise ValueError
        if not isinstance(value['template_id'], str):
            raise ValueError
        return Assignment(value['version'], resolve(profile, value['template_id'], value['renderer_revision']))
    except (ValueError, LookupError) as error:
        raise ScreenStateError('Screen-Zuordnung ist nicht verfügbar.') from error


def read_assignment(connection: Connection, profile: str) -> Assignment:
    row = connection.execute(text('''SELECT setting_value FROM cafeteria.settings
        WHERE location_id IS NULL AND profile_id IS NULL AND setting_key=:key'''), {'key': key(profile)}).one_or_none()
    return Assignment(0, choices(profile)[0]) if row is None else parse(row.setting_value, profile)


def activate(engine: Engine, profile: str, actor: int, authz_version: int,
             expected_version: int, template_id: str, revision: int) -> Assignment:
    selected = resolve(profile, template_id, revision)
    if type(expected_version) is not int or not 0 <= expected_version <= MAX_VERSION:
        raise ScreenValidation('Versionsnummer ist ungültig.')
    if any(type(value) is not int or not 1 <= value < 2**63 for value in (actor, authz_version)):
        raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.')
    try:
        with engine.begin() as connection:
            value = connection.execute(text('''SELECT cafeteria.activate_screen_assignment_v23(
                :actor,:authz,:profile,:version,:template,:revision)'''),
                {'actor': actor, 'authz': authz_version, 'profile': profile, 'version': expected_version,
                 'template': selected.id, 'revision': revision}).scalar_one()
            return parse(value, profile)
    except DBAPIError as error:
        code = getattr(error.orig, 'sqlstate', None)
        if code == '42501':
            raise PermissionError('Aktuelle Admin-Berechtigung erforderlich.') from None
        if code == 'P2001':
            raise ScreenValidation('Die Eingaben sind ungültig.') from None
        if code == 'P2004':
            raise ScreenStateError('Screen-Zuordnung ist nicht verfügbar.') from None
        if code == '55000':
            raise ScreenConflict('Die Zuordnung wurde geändert oder die Auswahl ist bereits aktiv. Ihre Auswahl wurde nicht gespeichert. Bitte aktuellen Stand laden.') from None
        raise
