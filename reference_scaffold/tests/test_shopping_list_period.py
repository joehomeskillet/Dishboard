"""R5 freeze: candidate_components takes date_from and date_to as keyword-only."""
from __future__ import annotations

import inspect

from cafeteria.shopping_list_reads import candidate_components


def test_candidate_components_period_api_is_frozen() -> None:
    params = inspect.signature(candidate_components).parameters
    assert tuple(params)[:2] == ('engine', 'scope')
    assert params['date_from'].kind is inspect.Parameter.KEYWORD_ONLY
    assert params['date_to'].kind is inspect.Parameter.KEYWORD_ONLY
    assert params['date_from'].default is inspect.Parameter.empty
    assert params['date_to'].default is inspect.Parameter.empty
