"""Checks for the one breadcrumb grammar (build_site.trail) and the general pages' teaching
openings: the trail is a labelled nav landmark holding an ordered list; every crumb links
except the current page, which carries aria-current="page"; the slashes are hidden from
screen readers; every list and general page opens with the trail, then its title, then one
sentence on what the page is for, and marks its section in the header; family, Lean
statement, paper and explanation pages use Map / Subject / Family N: title; the list
pages' column heads and filters explain themselves; the glossary's learning order names
real terms; and the guide puts its worked example before the general route.
Standard library only:
python3 scripts/tests/test_breadcrumbs.py
"""
from __future__ import annotations

import json
import re
import sys
import tempfile
import unittest
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_site as S  # noqa: E402

ROOT = Path(__file__).resolve().parents[2]


def the_trail(html: str) -> str:
    m = re.search(r'<nav class="trail"[^>]*>.*?</nav>', html, re.S)
    assert m, "no breadcrumb"
    return m.group(0)


def crumbs(html: str) -> list[tuple[str, str | None]]:
    """(text, href) per crumb; href None for the current page."""
    out = []
    for li in re.findall(r'<li class="trail__i">(.*?)</li>', the_trail(html), re.S):
        a = re.search(r'<a href="([^"]+)">(.*?)</a>', li, re.S)
        if a:
            out.append((unescape(re.sub(r"<[^>]+>", "", a.group(2))), a.group(1)))
        else:
            cur = re.search(r'<span class="trail__cur" aria-current="page">(.*?)</span>$', li, re.S)
            assert cur, li
            out.append((unescape(re.sub(r"<[^>]+>", "", cur.group(1))), None))
    return out


class Grammar(unittest.TestCase):
    def test_markup_is_a_landmark_with_an_ordered_list(self):
        h = S.trail("../", [("Number theory", "../index.html#o=d:number-theory"), ("Here", None)])
        self.assertTrue(h.startswith(f'<nav class="trail" aria-label="{S.C("nav.breadcrumb")}"><ol class="trail__list">'))
        self.assertEqual(h.count("<li"), 3)
        self.assertEqual(h.count('aria-current="page"'), 1)
        # one hidden slash before every crumb after the first, none before Map
        self.assertEqual(h.count('<span class="trail__sep" aria-hidden="true">/</span>'), 2)
        self.assertNotIn("trail__sep", h.split("</li>")[0])
        self.assertEqual(crumbs(h)[0], ("Map", "../index.html"))
        self.assertEqual(crumbs(h)[-1], ("Here", None))

    def test_family_crumbs_name_the_number_and_title(self):
        f = S.FAM["017"]
        here = S.family_trail(f, "../")
        self.assertEqual([c[1] for c in crumbs(here)], ["../index.html", "../index.html#o=d%3Anumber-theory", None])
        self.assertTrue(crumbs(here)[-1][0].startswith("Family 017: The irrationality exponent of"))
        below = S.family_trail(f, "../", "PiExponent")
        self.assertEqual(crumbs(below)[2][1], "../families/017.html")
        self.assertEqual(crumbs(below)[3], ("PiExponent", None))


class GeneralPages(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        S.OUT = Path(tempfile.mkdtemp(prefix="atlas-trail-"))
        S.PAGES.clear()
        for build in (S.build_explain, S.build_statements_table, S.build_numbers, S.build_sources,
                      S.build_citations_within, S.build_references_outside, S.build_glossary, S.build_about,
                      S.build_contribute, S.build_help):
            build()

    def page(self, rel):
        return (S.OUT / rel).read_text(encoding="utf-8")

    def test_each_page_opens_with_its_trail_title_and_purpose(self):
        cases = {  # page: (crumbs after Map, current nav section or None)
            "explain.html": (["Families"], "explain"),
            "statements.html": (["Lean statements"], "statements"),
            "sources.html": (["Sources"], "sources"),
            "glossary.html": (["Glossary"], "glossary"),
            "about.html": (["About"], "about"),
            "contribute.html": (["Contribute"], "contribute"),
            "numbers.html": (["About", "Numbers"], "about"),
            "citations-within.html": (["Families", S.C("citations_within.title")], "explain"),
            "references-outside.html": (["Families", S.C("references_outside.title")], "explain"),
            "help.html": ([S.C("help.title")], None),
        }
        for rel, (want, section) in cases.items():
            h = self.page(rel)
            got = crumbs(h)
            self.assertEqual([c[0] for c in got[1:]], want, rel)
            self.assertTrue(all(c[1] for c in got[:-1]) and got[-1][1] is None, rel)
            main = h[h.index('<main id="main"'):]
            self.assertLess(main.index('<nav class="trail"'), main.index("<h1"), rel)
            # the opening under the title (its first two paragraphs) says who the page is for
            opening = " ".join(re.findall(r"<p[^>]*>(.*?)</p>", main[main.index("</h1>"):], re.S)[:2])
            self.assertRegex(unescape(opening), r"(?i)\bfor (anyone|mathematicians)|first list", rel)
            cur = re.findall(r'<a href="[^"]*" aria-current="page">', h[:h.index("</header>")])
            # A section the header nav carries marks itself there; one the footer carries
            # (Contribute) has nothing to mark in the header.
            if section and section in dict((k, v) for v, k in S.NAV):
                href = dict((k, v) for v, k in S.NAV)[section]
                self.assertEqual(cur, [f'<a href="{href}" aria-current="page">'], rel)
            else:
                self.assertEqual(cur, [], rel)

    def test_list_heads_and_filters_explain_themselves(self):
        for rel, table in (("explain.html", "families-table"), ("statements.html", "stmt-table")):
            h = self.page(rel)
            thead = re.search(rf'id="{table}".*?<thead>(.*?)</thead>', h, re.S).group(1)
            ths = re.findall(r"<th[^>]*>", thead)
            self.assertTrue(ths)
            for th in ths:
                self.assertRegex(th, r'data-tip="[^"]{12,}"', rel)
            groups = re.findall(r'<div class="filters__g"([^>]*)><label', h)
            self.assertTrue(groups)
            self.assertTrue(all("data-tip=" in g for g in groups if 'filters__g--' not in g), rel)
        js = (ROOT / "site/assets/atlas.js").read_text(encoding="utf-8")
        self.assertIn("closest('[data-tip]')", js)


class Teaching(unittest.TestCase):
    def test_glossary_learning_order_and_examples(self):
        g = json.loads((ROOT / "site/assets/glossary.json").read_text(encoding="utf-8"))
        ids = {t["id"] for t in g["terms"]}
        self.assertTrue(set(g["learning_order"]) <= ids)
        self.assertEqual(g["learning_order"][:4], ["family", "headline", "lean", "challenge"])
        for t in g["terms"]:
            if t["id"] in g["learning_order"]:
                self.assertTrue(t.get("example"), f"core term {t['id']} has no example")
            self.assertNotIn("—", (t["short"] + t.get("example", "")).replace("NARROWER — DECLARED", ""))

    def test_guide_teaches_the_example_first(self):
        d = S.help_dialog("../")
        self.assertLess(d.index('class="help__example"'), d.index('class="help__route"'))
        self.assertLess(d.index('class="help__route"'), d.index('class="help__words"'))

if __name__ == "__main__":
    unittest.main()
