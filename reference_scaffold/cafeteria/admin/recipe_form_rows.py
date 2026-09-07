"""Native row operations; validate original context, never persist or resign."""
from werkzeug.datastructures import MultiDict

from .recipe_forms import FormError, ROWS, parse_recipe_form, read_context


def apply_row_action(form: MultiDict[str, str], *, action: str,
                     target_public_id: str | None) -> MultiDict[str, str]:
    if action not in ('recipe.create', 'recipe.update'):
        raise FormError('Zeilenaktion benötigt ein Rezeptformular.')
    read_context(action=action, target_public_id=target_public_id, form=form)
    data = parse_recipe_form(form, structural_only=True)
    if any(len(form.getlist(key)) != 1 for key in ('row_action', 'row_index', 'row_kind')):
        raise FormError('Zeilenaktion ist unvollständig.')
    kind, operation, raw_index = form['row_kind'], form['row_action'], form['row_index']
    if kind not in ROWS or operation not in ('add', 'remove', 'up', 'down'):
        raise FormError('Ungültige Zeilenaktion.')
    if not raw_index.isascii() or not raw_index.isdecimal() or len(raw_index) > 2:
        raise FormError('Ungültige Zeilenposition.')
    index = int(raw_index)
    rows = data[kind]
    if operation == 'add':
        if len(rows) == 64 or not 0 <= index <= len(rows):
            raise FormError('Höchstens 64 Zeilen; gültige Einfügeposition erforderlich.', kind)
        row = {field: '' for field in ROWS[kind]}
        if kind == 'ingredients':
            row['source_kind'] = 'manual'
        rows.insert(index, row)
    else:
        if not 0 <= index < len(rows):
            raise FormError('Diese Zeile existiert nicht.', kind)
        if operation == 'remove':
            rows.pop(index)
        else:
            destination = index + (-1 if operation == 'up' else 1)
            if not 0 <= destination < len(rows):
                raise FormError('Zeile kann nicht weiter verschoben werden.', kind)
            rows[index], rows[destination] = rows[destination], rows[index]
    result = MultiDict((key, value) for key, value in form.items(multi=True)
                       if not key.startswith(kind + '.') and key not in ('row_kind', 'row_action', 'row_index'))
    for index, row in enumerate(rows):
        for field, value in row.items():
            result.add(f'{kind}.{index}.{field}', value)
    return result
