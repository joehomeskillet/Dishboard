"""Small, app-scoped message resolver; parameters are always treated as text."""
from __future__ import annotations

import logging
import math
from collections.abc import Mapping
from pathlib import Path
from string import Formatter

from flask import current_app
from markupsafe import Markup, escape

from .semantics import SemanticError, read_json

TRANSLATIONS = Path(__file__).resolve().parents[1] / 'translations'
FORMATTER = Formatter()
LOGGER = logging.getLogger(__name__)


def message_fields(key: str, message: str) -> set[str]:
    names = set()
    try:
        for _, name, spec, conversion in FORMATTER.parse(message):
            if name is not None:
                if not name.isidentifier() or spec or conversion:
                    raise SemanticError(f'{key}: only named plain placeholders are allowed')
                names.add(name)
    except ValueError as exc:
        raise SemanticError(f'{key}: invalid message placeholders') from exc
    return names


def pseudo(message: str) -> str:
    """Lengthen literal segments, preserving named fields and escaped braces."""
    parts = []
    table = str.maketrans('aeiouAEIOU', 'äëïöüÄËÏÖÜ')
    for literal, name, _, _ in FORMATTER.parse(message):
        parts.append(literal.translate(table).replace('{', '{{').replace('}', '}}'))
        if name is not None:
            parts.append('{' + name + '}')
    padding = max(0, math.ceil(len(message) * 0.4) - 8)
    return '[!! ' + ''.join(parts) + ' ~' * math.ceil(padding / 2) + ' !!]'


def load_locales(*, testing: bool = False) -> dict[str, dict[str, str]]:
    locales = {path.stem: read_json(path) for path in sorted(TRANSLATIONS.glob('*.json'))}
    if 'de' not in locales:
        raise SemanticError('de: required primary locale missing')
    for locale, messages in locales.items():
        if not isinstance(messages, dict):
            raise SemanticError(f'{locale}: expected a message mapping')
        for key, message in messages.items():
            if not isinstance(message, str) or not message.strip():
                raise SemanticError(f'{key}: empty translation in {locale}')
            names = message_fields(key, message)
            if key in locales['de'] and names != message_fields(key, locales['de'][key]):
                raise SemanticError(f'{key}: placeholder mismatch in {locale}')
    if testing:
        locales['xx'] = {key: pseudo(value) for key, value in locales['de'].items()}
    return locales


class Translator:
    def __init__(self, locales: Mapping[str, Mapping[str, str]], *, production: bool = False):
        self.locales = locales
        self.production = production
        self.warned: set[str] = set()

    def translate(self, key: str, locale: str, **params: object) -> Markup:
        if locale not in self.locales:
            raise SemanticError(f'{locale}: unsupported UI_LOCALE')
        message = self.locales[locale].get(key)
        if message is None:
            if not self.production or key not in self.warned:
                LOGGER.warning('Missing UI translation %s in %s', key, locale)
                self.warned.add(key)
            message = self.locales['de'].get(key) if self.production else None
        if message is None:
            return escape(f'⟦{key}⟧')
        names = message_fields(key, message)
        missing = names - params.keys()
        if missing:
            if not self.production:
                raise SemanticError(f'{key}: missing parameters {sorted(missing)}')
            # A template bug must not take a kitchen page down: keep the visible
            # placeholder, log it, and let tests (which raise above) catch the cause.
            LOGGER.error('Missing UI translation parameters %s for %s', sorted(missing), key)
        # Escape the entire result, including str(Markup) parameters. No HTML or
        # __html__ protocol supplied by a caller becomes trusted markup here.
        values = {name: str(params[name]) if name in params else '{' + name + '}' for name in names}
        return escape(message.format_map(values))


def translate(key: str, locale: str | None = None, **params: object) -> Markup:
    translator = current_app.extensions['ui_translator']
    return translator.translate(key, locale or current_app.config['UI_LOCALE'], **params)
