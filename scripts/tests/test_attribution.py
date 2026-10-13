"""Regressions for uncredited additions and missing distribution notices."""
from pathlib import Path
import hashlib
import json
import shutil
import tempfile
import unittest

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import attribution


class AttributionTests(unittest.TestCase):
    def setUp(self):
        self.tmp = tempfile.TemporaryDirectory()
        self.addCleanup(self.tmp.cleanup)
        self.root = Path(self.tmp.name)
        for folder in ('LICENSES', 'site/assets/vendor', 'site/assets/fonts', 'curated/sources', 'backend'):
            (self.root / folder).mkdir(parents=True)
        for name in (*attribution.NOTICE_FILES, 'backend/NOTICE.md', 'LICENSES/MIT.txt'):
            (self.root / name).write_text('test notice\n')
        self.asset = 'site/assets/vendor/example.js'
        (self.root / self.asset).write_text('test asset\n')
        (self.root / 'site/config.json').write_text('{"katex_version":"test"}')
        self.doc = {'schema':'atlas-attribution/1', 'components':[{
            'id':'katex','name':'Fixture','credit':'Fixture author','url':'https://example.org',
            'source':'https://example.org/source','licence':'MIT','licence_file':'LICENSES/MIT.txt',
            'changes':'Test fixture','use':'Fixture','version':'test',
            'files':{self.asset:hashlib.sha256((self.root / self.asset).read_bytes()).hexdigest()}}],
            'source_licences':{}}
        self.save()

    def save(self):
        (self.root / 'LICENSES/manifest.json').write_text(json.dumps(self.doc))

    def test_notices_travel_with_build_and_missing_copy_fails(self):
        out = self.root / 'out'; out.mkdir()
        shutil.copytree(self.root / 'site/assets', out / 'assets')
        attribution.write_notices(out, self.root)
        self.assertEqual(attribution.check(self.root, out), [])
        (out / 'LICENSES/MIT.txt').unlink()
        self.assertIn('LICENSES/MIT.txt: built notice missing or differs from repository', attribution.check(self.root, out))

    def test_built_asset_must_match_its_recorded_source(self):
        out = self.root / 'out'; out.mkdir()
        attribution.write_notices(out, self.root)
        self.assertTrue(any('built component missing' in x for x in attribution.check(self.root, out)))

    def test_uncredited_asset_fails(self):
        (self.root / 'site/assets/fonts/new.woff2').write_bytes(b'new')
        self.assertTrue(any('no attribution record' in x for x in attribution.check(self.root)))

    def test_replaced_asset_requires_review(self):
        (self.root / self.asset).write_text('changed')
        self.assertTrue(any('bytes changed' in x for x in attribution.check(self.root)))

    def test_new_import_needs_licence_inventory_and_copy(self):
        source = {'id':'external','name':'External','url':'https://example.org',
                  'authors':[{'name':'Fixture author'}],'licence':'MIT','reuse':'import','snapshot':'2026-10-12'}
        (self.root / 'curated/sources/external.json').write_text(json.dumps({'source':source}))
        self.assertTrue(any('not been inventoried' in x for x in attribution.check(self.root)))
        self.doc['source_licences']['external']=[]; self.save()
        self.assertTrue(any('no licence copy' in x for x in attribution.check(self.root)))
        self.doc['source_licences']['external']=['LICENSES/MIT.txt']; self.save()
        self.assertEqual(attribution.check(self.root), [])

    def test_repository_inventory(self):
        self.assertEqual(attribution.check(), [])


if __name__ == '__main__':
    unittest.main()
