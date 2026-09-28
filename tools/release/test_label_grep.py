"""Conservative release-label discovery without confusing show_text and text."""
from __future__ import annotations

import io
import json
import tempfile
import unittest
from contextlib import redirect_stdout
from pathlib import Path
from unittest.mock import patch

import label_grep


LABELS = {'actions.cancel.label': 'Abbrechen', 'actions.add_recipe.label': 'Rezept'}


class VisibleTextsTests(unittest.TestCase):
    def test_show_text_preserves_registry_label_with_keyword_whitespace(self):
        for argument in ('show_text=true', 'show_text = true', 'show_text\t=\ttrue'):
            with self.subTest(argument=argument):
                self.assertEqual(
                    label_grep.visible_texts("{{ icon_button('actions.cancel', " + argument + ') }}', LABELS),
                    {'Abbrechen'},
                )

    def test_explicit_text_replaces_registry_label_with_keyword_whitespace(self):
        for keyword in ('text=', 'text = ', 'text\t=\t'):
            for prefix in ('', 'show_text=true, '):
                with self.subTest(keyword=keyword, prefix=prefix):
                    self.assertEqual(
                        label_grep.visible_texts(
                            "{{ icon_button('actions.cancel', " + prefix + keyword + "'Zurückgehen') }}", LABELS),
                        {'Zurückgehen'},
                    )

    def test_no_text_and_icon_label_remain_conservative(self):
        for source in (
            "{{ icon_button('actions.cancel') }}",
            "{{ icon_button('actions.cancel', show_text=false) }}",
            "{{ icon_label('actions.cancel') }}",
        ):
            with self.subTest(source=source):
                self.assertEqual(label_grep.visible_texts(source, LABELS), {'Abbrechen'})
        self.assertEqual(label_grep.visible_texts("{{ icon_label('unknown.key') }}", LABELS), set())


class LabelImpactTests(unittest.TestCase):
    def scan(self, changed_lines, sources, *, files_only=False):
        diff = 'diff --git a/' + label_grep.TEMPLATES + '/example.html b/' + label_grep.TEMPLATES
        diff += '/example.html\n' + changed_lines

        def fake_git(_worktree, *args):
            if args == ('merge-base', 'base', 'HEAD'):
                return 'base\n'
            if args in (('show', f'base:{label_grep.DE_LOCALE}'), ('show', f'HEAD:{label_grep.DE_LOCALE}')):
                return json.dumps(LABELS)
            if args == ('diff', '--no-renames', '-U0', 'base..HEAD', '--', label_grep.TEMPLATES, label_grep.DE_LOCALE):
                return diff
            self.fail(f'Unexpected git invocation: {args!r}')

        with tempfile.TemporaryDirectory() as directory:
            tests = Path(directory, 'reference_scaffold', 'tests')
            tests.mkdir(parents=True)
            for name, source in sources.items():
                (tests / name).write_text(source, encoding='utf-8')
            output = io.StringIO()
            argv = [directory, 'base'] + (['--files'] if files_only else [])
            with patch.object(label_grep, 'git', side_effect=fake_git), redirect_stdout(output):
                status = label_grep.main(argv)
        return status, output.getvalue()

    def test_retained_registry_label_does_not_invent_removed_text(self):
        status, output = self.scan(
            "-{{ icon_button('actions.cancel') }}\n"
            "+{{ icon_button('actions.cancel', show_text=true) }}\n",
            {'test_retained_accept.py': "assert label == 'Abbrechen'"},
        )
        self.assertEqual(status, 0)
        self.assertEqual(output, 'entfernte_texte=0 trefferdateien=0 locked=0\n')

    def test_real_registry_and_explicit_text_removals_still_match_tests(self):
        status, output = self.scan(
            "-{{ icon_button('actions.cancel', show_text=true) }}\n"
            "-{{ icon_button('actions.add_recipe', text = 'Rezept erzeugen') }}\n"
            "+{{ icon_button('actions.add_recipe', text = 'Neues Rezept') }}\n",
            {'test_registry.py': "assert label == 'Abbrechen'", 'test_explicit.py': "assert label == 'Rezept erzeugen'"},
        )
        self.assertEqual(status, 0)
        self.assertIn("'Abbrechen': tests/test_registry.py\n", output)
        self.assertIn("'Rezept erzeugen': tests/test_explicit.py\n", output)
        self.assertIn('entfernte_texte=2 trefferdateien=2 locked=0\n', output)
        self.assertNotIn("'Rezept':", output)

    def test_locked_collision_blocks_but_files_mode_keeps_its_contract(self):
        removed = "-{{ icon_button('actions.cancel', show_text=true) }}\n"
        sources = {'test_behavior.py': "assert 'Abbrechen'", 'test_contract_accept.py': "assert 'Abbrechen'"}
        status, output = self.scan(removed, sources)
        self.assertEqual(status, 1)
        self.assertIn('LOCKED tests/test_contract_accept.py', output)
        self.assertIn('entfernte_texte=1 trefferdateien=2 locked=1\n', output)
        status, output = self.scan(removed, sources, files_only=True)
        self.assertEqual(status, 0)
        self.assertEqual(output.splitlines(), ['tests/test_behavior.py', 'tests/test_contract_accept.py'])


if __name__ == '__main__':
    unittest.main()
