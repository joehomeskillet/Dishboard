"""DB-free tests for the UI/UX wave capture helper functions."""
from __future__ import annotations

import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / 'tools'))

from capture_uiux_wave import (  # noqa: E402
    exit_code_from_rows,
    filename_for,
    manifest_row,
    slugify,
    wave_pages,
)


def test_wave_pages_inventory_is_complete() -> None:
    pages = wave_pages()
    assert len(pages) == 17
    slugs = {page.slug for page in pages}
    assert slugs == {
        'wochenplan-cafeteria',
        'menues',
        'bausteine',
        'zutaten-grundlagen',
        'rezepte',
        'kochbuecher',
        'gerichtvorlagen',
        'einkaufslisten',
        'bestellung',
        'lager',
        'kalkulation',
        'bereiche-oeffnungszeiten',
        'erscheinungsbild',
        'darstellung',
        'daten-importieren',
        'schnittstellen',
        'benutzer-zugriff',
    }


def test_filename_slug_uses_module_and_width_only() -> None:
    assert filename_for('menues', 360) == 'menues-360.png'
    assert filename_for('bereiche-oeffnungszeiten', 1440) == 'bereiche-oeffnungszeiten-1440.png'
    assert slugify('Bereiche & Öffnungszeiten') == 'bereiche-oeffnungszeiten'


def test_manifest_row_shape() -> None:
    row = manifest_row(
        path='/tmp/before/menues-360.png',
        route='/admin/cafeteria/menues',
        viewport={'width': 360, 'height': 800},
        http_status=200,
        sha256='abc',
        horizontal_overflow=False,
        console_errors=['late console failure'],
    )
    assert row == {
        'path': '/tmp/before/menues-360.png',
        'route': '/admin/cafeteria/menues',
        'viewport': {'width': 360, 'height': 800},
        'http_status': 200,
        'sha256': 'abc',
        'horizontal_overflow': False,
        'console_errors': ['late console failure'],
    }


def test_exit_code_is_one_when_any_row_has_error() -> None:
    ok = manifest_row(
        path='/tmp/before/menues-360.png',
        route='/admin/cafeteria/menues',
        viewport={'width': 360, 'height': 800},
        http_status=200,
        sha256='abc',
        horizontal_overflow=False,
        console_errors=[],
    )
    failed = manifest_row(
        path='/tmp/before/menues-768.png',
        route='/admin/cafeteria/menues',
        viewport={'width': 768, 'height': 1024},
        http_status=None,
        sha256=None,
        horizontal_overflow=None,
        console_errors=[],
        error='RuntimeError: HTTP 500',
    )
    assert exit_code_from_rows([ok]) == 0
    assert exit_code_from_rows([ok, failed]) == 1
    assert exit_code_from_rows([
        manifest_row(
            path='/tmp/before/menues-360.png',
            route='/admin/cafeteria/menues',
            viewport={'width': 360, 'height': 800},
            http_status=404,
            sha256=None,
            horizontal_overflow=None,
            console_errors=[],
        ),
    ]) == 1
