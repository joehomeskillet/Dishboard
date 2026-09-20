"""Semantic presentation contracts, independent of business state."""
from __future__ import annotations

import os

from flask import Flask, current_app

from .i18n import Translator, load_locales, translate
from .semantics import Semantic, SemanticError, load_registry, validate_locales


def sem(key: str) -> Semantic:
    try:
        return current_app.extensions['ui_semantics'][key]
    except (KeyError, TypeError) as exc:
        raise SemanticError(f'{key}: unknown semantic key') from exc


def require_icon_only(key: str, icon_only: bool = False) -> str:
    item = sem(key)
    if icon_only and (not item.icon_only_allowed or item.role == 'danger'):
        raise SemanticError(f'{key}: icon-only presentation is forbidden')
    return ''


def require_consequence(key: str, consequence_key: str | None) -> str:
    if sem(key).role == 'danger' and not consequence_key:
        raise SemanticError(f'{key}: destructive control requires consequence_key')
    if consequence_key:
        sem(consequence_key)
    return ''


def register_ui(app: Flask) -> None:
    registry = load_registry()
    locales = load_locales(testing=bool(app.config.get('TESTING')))
    validate_locales(registry, locales)
    app.config.setdefault('UI_LOCALE', os.environ.get('UI_LOCALE', 'de'))
    if app.config['UI_LOCALE'] not in locales:
        raise SemanticError(f"{app.config['UI_LOCALE']}: unsupported UI_LOCALE")
    app.extensions['ui_semantics'] = registry
    app.extensions['ui_translator'] = Translator(
        locales, production=app.config.get('APP_ENV') == 'production' and not app.testing,
    )
    app.jinja_env.globals.update(t=translate, sem=sem, require_icon_only=require_icon_only,
                                require_consequence=require_consequence)

    @app.context_processor
    def ui_locale_context():
        return {'ui_locale': app.config['UI_LOCALE']}
