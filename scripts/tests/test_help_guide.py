"""Checks for the shared header's "?" guide (build_site.help_dialog) and the footer: every
page's header carries the button beside Search, labelled for screen readers; the guide is
server-rendered in the page, with the route's steps and the words a visitor meets, each
word linked to a glossary entry that exists; the map alone carries the first-visit hint;
the footer links Numbers and the agents' guide; atlas.js opens the guide from the button,
the ? key, ?help=1 and data-help. Standard library only:
python3 scripts/tests/test_help_guide.py
"""
from __future__ import annotations

import re
import sys
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_site as S  # noqa: E402

JS = (Path(__file__).resolve().parents[2] / "site" / "assets" / "atlas.js").read_text(encoding="utf-8")


class HelpGuide(unittest.TestCase):
    def test_button_sits_between_search_and_theme_on_every_depth(self):
        for rel in ("index.html", "families/017.html", "explanations/017/x/index.html"):
            h = S.header(rel, None)
            i_search, i_help, i_theme = h.index('class="search-open"'), h.index('class="help-open"'), h.index('class="theme-toggle"')
            self.assertLess(i_search, i_help)
            self.assertLess(i_help, i_theme)
            btn = re.search(r'<button class="help-open"[^>]*>', h).group(0)
            self.assertIn(f'aria-label="{S.C("nav.help")}"', btn)
            self.assertIn('aria-controls="help-dialog"', btn)
            self.assertIn('<dialog class="dlg help" id="help-dialog" aria-labelledby="help-title">', h)

    def test_guide_holds_the_route_and_the_words(self):
        d = S.help_dialog("../")
        steps = S.COPY["help"]["steps"]
        self.assertTrue(4 <= len(steps) <= 6)
        for sid, _ in steps:
            self.assertIn(f'id="help-{sid}"', d)
        for tid, label, text in S.COPY["help"]["terms"]:
            self.assertIn(tid, S.GLOSSARY, f"help term {label!r} links a glossary entry that does not exist")
            self.assertIn(f'href="../glossary.html#{tid}"', d)
            self.assertNotIn("—", text.replace("NARROWER — DECLARED", ""), "no em dash in Atlas's own words")
        self.assertIn(S.esc(S.C("help.limit")), d)
        self.assertIn('href="../help.html"', d)

    def test_hint_only_on_the_map(self):
        self.assertIn('id="first-hint"', S.header("index.html", "map"))
        self.assertNotIn('id="first-hint"', S.header("explain.html", "explain"))

    def test_footer_links(self):
        f = S.footer("families/017.html")
        for href in ("../numbers.html", "../about.html", "../glossary.html", "../agents.md", "../sources.html#software"):
            self.assertIn(f'href="{href}"', f)

    def test_script_opens_the_guide_every_way(self):
        block = JS[JS.index("How to use the Atlas (the header's ? guide)"):]
        for needle in ("'.help-open'", "ev.key !== '?'", "q.get('help') === '1'", "[data-help]", "showModal", "'Escape'",
                       "ev.target === dlg", "returnTo.focus", "localStorage"):
            self.assertIn(needle, block)


if __name__ == "__main__":
    unittest.main()
