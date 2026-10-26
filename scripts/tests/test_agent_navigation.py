"""Check the public agent route against the map it documents. Standard library only.

python3 scripts/tests/test_agent_navigation.py [--built site/_build]
"""
from __future__ import annotations

import argparse
import contextlib
import io
import json
import re
import sys
import unittest
from html.parser import HTMLParser
from pathlib import Path
from unittest.mock import patch
from urllib.parse import unquote, urljoin, urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_universe as U

BUILT = None


class Tags(HTMLParser):
    def __init__(self, text):
        super().__init__()
        self.tags = []
        self.feed(text)

    def handle_starttag(self, tag, attrs):
        self.tags.append((tag, dict(attrs)))


class AgentNavigation(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        U.import_site()
        cls.model = U.Model(U.R.load())
        cls.data = cls.model.data
        cls.guides = U.build_agent_navigation(cls.data, cls.model.gen, "test-version")

    def test_existing_graph_has_unique_ids_and_complete_bidirectional_membership(self):
        d = self.data
        ids = [row['id'] for kind in ('disciplines', 'families', 'papers', 'results', 'lean')
               for row in d[kind]]
        self.assertEqual(len(ids), len(set(ids)))
        for di, discipline in enumerate(d['disciplines']):
            for fi in discipline['families']:
                self.assertEqual(d['families'][fi]['d'], di)
        for fi, family in enumerate(d['families']):
            self.assertIn(fi, d['disciplines'][family['d']]['families'])
            for kind in ('papers', 'lean'):
                for index in family[kind]:
                    self.assertEqual(d[kind][index]['f'], fi)
        for pi, paper in enumerate(d['papers']):
            self.assertIn(pi, d['families'][paper['f']]['papers'])
            for ri in paper['results']:
                self.assertEqual(d['results'][ri]['p'], pi)
        for ri, result in enumerate(d['results']):
            paper = d['papers'][result['p']]
            self.assertIn(ri, paper['results'])
            self.assertEqual(result['f'], paper['f'])
            for li in result['lean']:
                self.assertIn(ri, d['lean'][li]['results'])
        for li, lean in enumerate(d['lean']):
            self.assertIn(li, d['families'][lean['f']]['lean'])
            self.assertTrue(lean['pairing'])
            for ri in lean['results']:
                self.assertIn(li, d['results'][ri]['lean'])
                self.assertEqual(lean['f'], d['results'][ri]['f'])
        citations = set()
        for a, b, forward, reverse in d['links']:
            for source, target, count in ((a, b, forward), (b, a, reverse)):
                self.assertGreaterEqual(count, 0)
                if count:
                    self.assertIn([target, count], d['families'][source]['cites'])
                    self.assertIn([source, count], d['families'][target]['citedBy'])
                    citations.add((source, target, count))
        self.assertEqual(citations, {(i, j, n) for i, f in enumerate(d['families'])
                                     for j, n in f['cites']})
        self.assertEqual(citations, {(j, i, n) for i, f in enumerate(d['families'])
                                     for j, n in f['citedBy']})

    def test_guide_keeps_source_identity_and_complete_project_path(self):
        guide = self.guides['agents.md']
        self.assertIn(self.model.gen, guide)
        self.assertIn(U.S.COMMIT, guide)
        self.assertIn('candidate-pairing', guide)
        self.assertIn('citation is not a proof dependency', guide)
        self.assertIn('zero-based array indices', guide)
        for content in self.guides.values():
            urls = re.findall(r'\]\((https?://[^)]+)\)', content)
            self.assertTrue(urls)
            for url in urls:
                if urlsplit(url).netloc == urlsplit(U.S.BASE_URL).netloc:
                    self.assertTrue(url.startswith(U.S.BASE_URL), url)

    def test_example_fetches_current_packets_and_rejects_mixed_generations(self):
        guide = self.guides['agents.md']
        code = re.search(r'```python\n(.*?)\n```', guide, re.S)[1]
        overview = {'generation_id': self.model.gen,
                    **{k: self.data[k] for k in ('disciplines', 'families', 'links')}}
        parts = {'generation_id': self.model.gen,
                 **{k: self.data[k] for k in ('papers', 'results', 'lean')}}
        requested = []

        def fetch(url, timeout):
            self.assertEqual(timeout, 30)
            self.assertTrue(url.startswith(U.S.BASE_URL + 'data/universe-'), url)
            requested.append(url)
            packet = parts if 'universe-parts.json' in url else overview
            return io.StringIO(json.dumps(packet))

        with patch('urllib.request.urlopen', fetch), contextlib.redirect_stdout(io.StringIO()) as output:
            exec(code, {})
        self.assertEqual(len(requested), 2)
        self.assertIn('f:159', output.getvalue())
        self.assertIn('l:ErdosReciprocal', output.getvalue())
        parts['generation_id'] = 'different-deployment'
        with patch('urllib.request.urlopen', fetch), self.assertRaisesRegex(RuntimeError, 'Deployment changed'):
            exec(code, {})

    def test_discovery_is_a_link_without_a_browser_download(self):
        for rel in ('index.html', 'families/159.html', 'nested/path/page.html'):
            head = U.S.head(rel, 'Title', 'Description')
            links = [attrs for tag, attrs in Tags(head).tags if tag == 'link']
            agent = [a for a in links if a.get('href', '').endswith('agents.md')]
            self.assertEqual(len(agent), 1)
            self.assertEqual(agent[0]['rel'], 'help')
            self.assertEqual(urljoin(U.S.BASE_URL + rel, agent[0]['href']), U.S.BASE_URL + 'agents.md')
            self.assertIn('agents.md', U.S.footer(rel))
            for attrs in links:
                if attrs.get('rel') in ('preload', 'prefetch', 'modulepreload'):
                    self.assertNotIn('agents.md', attrs['href'])
                    self.assertNotIn('llms.txt', attrs['href'])
        for asset in (U.ASSETS / 'atlas.js', U.ASSETS / 'universe.js'):
            self.assertNotRegex(asset.read_text(), r'agents\.md|llms\.txt')

    def test_built_packets_and_page_destinations(self):
        if BUILT is None:
            self.skipTest('pass --built after the complete build for route integration')
        overview = json.loads((BUILT / 'data/universe-data.json').read_text())
        parts = json.loads((BUILT / 'data/universe-parts.json').read_text())
        self.assertEqual(overview['generation_id'], parts['generation_id'])
        self.assertEqual(overview['generation_id'], self.model.gen)
        self.assertEqual(overview['contract'][0]['upstream_commit'], U.S.COMMIT)
        for kind in ('disciplines', 'families', 'links'):
            self.assertEqual(overview[kind], self.data[kind])
        for kind in ('papers', 'results', 'lean'):
            self.assertEqual(parts[kind], self.data[kind])
        expected = U.build_agent_navigation(self.data, self.model.gen, U.packet_version(BUILT / 'data'))
        for name, content in expected.items():
            self.assertEqual((BUILT / name).read_text(), content)
            for url in re.findall(r'\]\((https?://[^)]+)\)', content):
                if url.startswith(U.S.BASE_URL):
                    path = unquote(urlsplit(url[len(U.S.BASE_URL):]).path) or 'index.html'
                    self.assertTrue((BUILT / path).is_file(), path)
        for kind in ('families', 'papers', 'results', 'lean'):
            for node in self.data[kind]:
                if node.get('href'):
                    path = unquote(urlsplit(node['href']).path)
                    self.assertFalse(path.startswith('/'), node['id'])
                    self.assertTrue((BUILT / path).is_file(), (node['id'], path))
        for path in ('index.html', 'families/159.html', 'statements/ErdosReciprocal.html'):
            self.assertIn('agents.md', (BUILT / path).read_text())

    def test_no_page_keeps_the_root_placeholder(self):
        """Shared HTML marks the site root as __ROOT__ until a page is written; a page
        written outside build_site.write_page (the map's index.html once) kept it, so its
        guide linked to .../__ROOT__families/017.html."""
        if BUILT is None:
            self.skipTest('pass --built after the complete build')
        kept = [str(p.relative_to(BUILT)) for p in BUILT.rglob('*.html') if '__ROOT__' in p.read_text(encoding='utf-8')]
        self.assertEqual(kept, [], f'{len(kept)} built pages keep __ROOT__')


if __name__ == '__main__':
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--built', type=Path)
    args, remaining = parser.parse_known_args()
    BUILT = args.built
    unittest.main(argv=[sys.argv[0], *remaining])
