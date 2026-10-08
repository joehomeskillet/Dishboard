#!/usr/bin/env python3
"""Parse every admin template without DB access; this is not a rendering proof."""
from pathlib import Path

from jinja2 import Environment, FileSystemLoader


def main() -> int:
    root = Path(__file__).resolve().parents[1] / 'reference_scaffold/cafeteria/templates'
    environment = Environment(loader=FileSystemLoader(root))
    templates = sorted((root / 'admin').rglob('*.html'))
    for path in templates:
        environment.parse(path.read_text(), name=path.relative_to(root).as_posix())
    print(f'Parsed {len(templates)} admin templates without DB access; rendering is checked in test tiers.')
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
