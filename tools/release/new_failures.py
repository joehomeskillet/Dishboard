#!/usr/bin/env python3
"""Neue Fehler = Fehler aus JUnit-Dateien minus tools/release/known_red.txt.

Usage: new_failures.py <junit.xml> [<junit.xml> ...]
Exit 0 ohne neue Fehler, 1 mit neuen Fehlern, 2 bei fehlender oder defekter JUnit-Datei.
Test-IDs wie pytest sie nennt, relativ zu reference_scaffold: tests/test_x.py[::Klasse]::test_name[param].
"""
from __future__ import annotations

import sys
import xml.etree.ElementTree as ET
from pathlib import Path

KNOWN_RED = Path(__file__).with_name('known_red.txt')
INFRA_MARKERS = ('Connection refused', 'Sync API inside the asyncio loop', 'ImportError')


def test_id(case: ET.Element) -> str:
    classname = case.get('classname', '')
    name = case.get('name', '')
    if not classname:  # Sammelfehler: name ist der Modulpfad
        return name
    parts = classname.split('.')
    # tests.test_x[.Klasse] -> tests/test_x.py[::Klasse]
    idx = next((i for i, part in enumerate(parts) if part.startswith('test_')), len(parts) - 1)
    return '::'.join(['/'.join(parts[: idx + 1]) + '.py', *parts[idx + 1:], name])


def load_known() -> set[str]:
    lines = KNOWN_RED.read_text(encoding='utf-8').splitlines()
    return {line.strip() for line in lines if line.strip() and not line.lstrip().startswith('#')}


def main(paths: list[str]) -> int:
    if not paths:
        print(__doc__)
        return 2
    ran: set[str] = set()
    failed: dict[str, str] = {}
    for path in paths:
        try:
            root = ET.parse(path).getroot()
        except (OSError, ET.ParseError) as exc:
            print(f'JUnit fehlt oder ist defekt: {path}: {exc}')
            return 2
        for case in root.iter('testcase'):
            case_id = test_id(case)
            ran.add(case_id)
            problem = case.find('failure')
            if problem is None:
                problem = case.find('error')
            if problem is not None:
                failed[case_id] = ' '.join((problem.get('message') or problem.text or '').split())[:160]

    known = load_known()
    new = sorted(set(failed) - known)
    now_green = sorted((known & ran) - set(failed))
    print(f'tests={len(ran)} failed={len(failed)} known_red={len(known)} '
          f'davon_rot_in_diesem_lauf={len(set(failed) & known)}')
    for case_id in new:
        infra = any(marker in failed[case_id] for marker in INFRA_MARKERS)
        print(f'NEU{" [INFRA: neu starten, nicht im Produkt reparieren]" if infra else ""}: {case_id}  {failed[case_id]}')
    for case_id in now_green:
        print(f'BEKANNT ROT, JETZT GRÜN (aus known_red.txt streichen): {case_id}')
    print(f'NEW_FAILURES={len(new)}')
    return 1 if new else 0


if __name__ == '__main__':
    raise SystemExit(main(sys.argv[1:]))
