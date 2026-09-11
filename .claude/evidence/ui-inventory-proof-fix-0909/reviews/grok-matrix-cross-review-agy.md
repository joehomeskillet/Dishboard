# Cross-Vendor-Review von wp-d7589450daee-grok-matrix

- Reviewer: antigravity-agy, Modell `gemini-3.8-flash-high`, read-only in `claude-sandbox` (Repository schreibgeschützt)
- Geprüft: `5f9b946` (`build_matrix.py`, Autor grok-build/grok-4.6) gegen Basis `50124c2`
- Ergebnis des Reviewers: `WAVE-REVIEW: FINDINGS (5)`

| # | Stelle (Stand 5f9b946) | Schwere (Reviewer) | Befund | Einordnung Orchestrator |
|---|---|---|---|---|
| 1 | `build_matrix.py:138` | HOCH | Regex `(\w+)\(family\) if family else (\w+)\(\)` passt nur auf `operations_routes.py:256`; Umformatierung fällt still auf `capability=None` zurück | Bestätigt als Grenze. Rückfall führt zu den alten Rollen und wird vom Laufzeittest `test_matrix_roles_match_server_side_authorization` erkannt. Kein Umbau im Inventar-WP. |
| 2 | `build_matrix.py:136` | MITTEL | Decorator-Regex `^@(\w+)` ignoriert Einrückung und Dotted Names | Bestätigt als Grenze, gleiche Absicherung wie 1. |
| 3 | `build_matrix.py:100` | HOCH | 15 visuelle Admin-Routen mit `capability=None`, weil `protected`-Wrapper die Capability methodenabhängig wählen (`recipe_errors.py:67-68`, `master_data_routes.py:27-28`); Rollen stimmen | Bestätigt. Korrektur an anderen Autor (agy-matrix-fix): `common.capability_semantics` erklärt `null` und verweist auf den Laufzeittest. |
| 4 | `build_matrix.py:374` | MITTEL | `admin.screen_template_assignment`: POST verlangt `settings.write` (`screen_template_routes.py:96-97`), Matrix führt Editor/Publisher | Bestätigt. Korrektur an anderen Autor: explizite `METHOD_RESTRICTIONS` mit Beleg und Zeilenfeld `method_roles`. |
| 5 | `build_matrix.py:122` | NIEDRIG | Closure-Walk hängt am Variablennamen `capability` | Bestätigt als Grenze, gleiche Absicherung wie 1. |

Zusätzlich vom Orchestrator gefunden und in `91f1fca` korrigiert: `SHARED_STATES` verwies auf die
nicht registrierten Namen `auth.error` (Template) und `admin.components_list` (registriert ist
`admin.components_get`).
