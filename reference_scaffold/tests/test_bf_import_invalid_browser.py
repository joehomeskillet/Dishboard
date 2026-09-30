"""BF-E3 T32: an invalid week CSV is previewed per row and never adopted."""
from __future__ import annotations

import csv
import io
from pathlib import Path

import pytest
from sqlalchemy import text

from test_admin_workflow_routes import DATABASE_URL, _login, database_engine  # noqa: F401
from test_rendered_ui import browser  # noqa: F401
from test_ui_master_shell_browser import _goto, _page, site  # noqa: F401

pytestmark = pytest.mark.skipif(not DATABASE_URL, reason='TEST_DATABASE_URL fehlt.')

EVIDENCE = Path(
    '/nvmetank1/projects/menuplan/.claude/worktrees/icon-first-r18'
    '/.claude/state/claude-session-2026-09-29/audit/BF/E3'
)
SENTINEL = 'BF-E3-SENTINEL-NICHT-UEBERNEHMEN'
FINGERPRINT = text(
    """
    SELECT
      (SELECT count(*) FROM cafeteria.menu_weeks),
      (SELECT coalesce(sum(row_version), 0) FROM cafeteria.menu_weeks),
      (SELECT count(*) FROM cafeteria.menu_services),
      (SELECT coalesce(sum(row_version), 0) FROM cafeteria.menu_services),
      (SELECT count(*) FROM cafeteria.menu_items),
      (SELECT coalesce(sum(row_version), 0) FROM cafeteria.menu_items),
      (SELECT count(*) FROM cafeteria.recipes),
      (SELECT count(*) FROM cafeteria.menu_items WHERE title = 'BF-E3-SENTINEL-NICHT-UEBERNEHMEN')
    """
)


def _shot(page, name: str) -> None:
    EVIDENCE.mkdir(parents=True, exist_ok=True)
    page.screenshot(path=str(EVIDENCE / f'{name}.png'))


def _invalid_csv() -> bytes:
    source = Path(__file__).resolve().parents[2] / 'csv' / 'menu_cafeteria_example.csv'
    reader = csv.DictReader(io.StringIO(source.read_text(encoding='utf-8-sig')), delimiter=';')
    rows = list(reader)
    rows[0]['preis_mitarbeitende_chf'] = 'kein-preis'
    rows[1]['preis_externe_chf'] = 'auch-kein-preis'
    rows[2]['titel'] = SENTINEL
    buffer = io.StringIO(newline='')
    writer = csv.DictWriter(buffer, fieldnames=list(reader.fieldnames or []), delimiter=';', lineterminator='\n')
    writer.writeheader()
    writer.writerows(rows)
    return buffer.getvalue().encode()


def _fingerprint(engine) -> tuple[int, ...]:
    with engine.connect() as connection:
        row = connection.execute(FINGERPRINT).one()
    return tuple(int(value) for value in row)


def test_t32_invalid_import_previews_without_writing(site) -> None:  # noqa: F811
    """Invalid rows stay in the preview, one error each, and the draft is unchanged."""
    app, _, engine, _ = site
    client, _ = _login(app, engine, ['Cafeteria.Admin'])
    payload = _invalid_csv()
    before = _fingerprint(engine)
    assert before[-1] == 0
    for javascript in (True, False):
        page = _page(site, client, viewport={'width': 1280, 'height': 900}, java_script_enabled=javascript)
        try:
            _goto(page, '/admin/import-preview')
            page.locator('#file').set_input_files({
                'name': 'bf-e3-invalid.csv', 'mimeType': 'text/csv', 'buffer': payload,
            })
            page.get_by_role('button', name='Vorschau prüfen', exact=True).click()
            page.wait_for_load_state('networkidle')
            issues = page.locator('.csv-issue-row').all_inner_texts()
            ready = page.get_by_role('heading', name='Bereit zum Import').count()
            adopted = page.locator('#csv-import').count() + page.locator('input[name="import_token"]').count()
            heading = page.get_by_role('heading', name='Datei korrigieren').count()
            state = page.locator('main[data-state="error"]').count()
            after = _fingerprint(engine)
            ok = (
                any('Zeile 2,' in issue for issue in issues)
                and any('Zeile 3,' in issue for issue in issues)
                and ready == 0 and adopted == 0 and heading == 1 and state == 1
                and after == before
            )
            if not ok:
                _shot(page, f't32-js{int(javascript)}')
            assert ok, {
                'javascript': javascript, 'issues': issues, 'ready': ready, 'adopted': adopted,
                'heading': heading, 'state': state, 'before': before, 'after': after,
            }
        finally:
            page.context.close()
