"""Role placement, index changes and ignored output must agree in local and CI checks."""
from pathlib import Path
import subprocess
import sys
import tempfile
import unittest

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import check_repository_structure as structure


class StructureTests(unittest.TestCase):
    def test_role_boundaries(self):
        accepted = structure.REQUIRED | structure.ROOT_FILES | {
            'scripts/build_data.py', 'scripts/ingest/mathvet.py',
            'scripts/tests/test_example.js', 'docs/images/family-dark.png',
            'docs/README.md', 'backend/manifest.json', 'data/statements.json'}
        self.assertEqual(structure.check(accepted), [])
        for path in ('scripts/test_leak.py', 'test_root.py', 'docs/test_tool.js',
                     'docs/map.png', 'docs/helper.py', 'scratch.md', 'site/_build/index.html'):
            with self.subTest(path=path):
                self.assertTrue(any(e.startswith(path + ':') for e in structure.check(accepted | {path})))
        self.assertTrue(structure.check(accepted - {'scripts/reader.py'}))

    def test_git_candidates(self):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            def git(*args):
                return subprocess.check_output(['git', *args], cwd=root, stderr=subprocess.DEVNULL)
            git('init', '-q')
            (root / '.gitignore').write_text('site/_build/\nignored/\n')
            (root / 'scripts').mkdir()
            old = root / 'scripts/test_old.py'
            old.write_text('')
            git('add', '.')
            git('-c', 'user.name=Structure Tests', '-c', 'user.email=tests@example.invalid', 'commit', '-qm', 'fixture')
            git('rm', 'scripts/test_old.py')
            (root / 'scripts/tests').mkdir(parents=True)
            (root / 'scripts/tests/test_new.py').write_text('')
            git('add', 'scripts/tests/test_new.py')
            (root / 'scripts/test_untracked.py').write_text('')
            (root / 'site/_build').mkdir(parents=True)
            (root / 'site/_build/test_ignored.py').write_text('')
            paths = structure.candidates(root)
            self.assertNotIn('scripts/test_old.py', paths)
            self.assertIn('scripts/tests/test_new.py', paths)
            self.assertIn('scripts/test_untracked.py', paths)
            self.assertNotIn('site/_build/test_ignored.py', paths)
            git('add', '-f', 'site/_build/test_ignored.py')
            paths = structure.candidates(root)
            self.assertTrue(any(e.startswith('site/_build/') for e in structure.check(paths)))


if __name__ == '__main__':
    unittest.main()
