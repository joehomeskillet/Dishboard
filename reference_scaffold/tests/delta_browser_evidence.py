"""Capture the requested viewport without resetting Chromium's pointer emulation."""
from __future__ import annotations

import json


def capture_delta(page, path, touch, *, masks=()):
    """Keep viewport and touch media stable, retaining Playwright's secret masks."""
    # Detaching a CDP session clears touch emulation. Keep one session per page;
    # the owning browser context closes it, including after assertion failures.
    session = getattr(page, '_delta_capture_session', None)
    if session is None:
        session = page.context.new_cdp_session(page)
        page._delta_capture_session = session
    measure = """() => ({coarse: matchMedia('(pointer: coarse)').matches,
        minimum: getComputedStyle(document.body).getPropertyValue('--app-control-min-height'),
        viewport: {width: innerWidth, height: innerHeight},
        controls: [...document.querySelectorAll('main .ui-sem-control')].map(el => ({
            semantic: el.dataset.semantic, height: el.getBoundingClientRect().height
        }))})"""
    session.send('Emulation.setTouchEmulationEnabled', {'enabled': touch})
    page.evaluate('document.fonts.ready')
    # Allow the initial compositor paint even when page JavaScript is disabled.
    page.wait_for_timeout(50)
    before = page.evaluate(measure)
    assert before['coarse'] == touch, before
    # Chromium's captureBeyondViewport resets touch media on this host.
    # Capture exactly the assigned viewport; native tests cover below-fold fields.
    page.screenshot(path=str(path), full_page=False, mask=list(masks))
    after = page.evaluate(measure)
    path.with_suffix('.json').write_text(json.dumps({'before': before, 'after': after}, indent=2),
                                        encoding='utf-8')
    assert after == before, (before, after)
