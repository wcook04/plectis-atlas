#!/usr/bin/env python3
"""Exercise reciprocal reading links, including the renderer's location aliases."""
import contextlib
import io
import tempfile
import unittest
from pathlib import Path
from unittest.mock import patch

import sys
sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import check_paper_links


def theorem(anchor="thm:main", alias="L-main.tex-1"):
    return (f'<div class="pr-thm pr-thm--plain" id="{anchor}">'
            f'<span class="pr-lbl" id="{alias}"></span>Theorem</div>')


NOTE = '<aside><p class="pr-lean pr-lean--candidate"><a href="../statements/Demo.html">Demo</a></p></aside>'


class PaperLinkTests(unittest.TestCase):
    def check(self, down="L-main.tex-1", paper=None, slug="paper", other=None):
        with tempfile.TemporaryDirectory() as tmp:
            root = Path(tmp)
            (root / "statements").mkdir()
            (root / "papers").mkdir()
            if down is not None:
                downs = [down] if isinstance(down, str) else down
                (root / "statements/Demo.html").write_text("".join(
                    f'<p class="claim__src"><a href="../papers/{slug}.html#{d}">Theorem</a></p>' for d in downs))
            if paper is not None:
                (root / "papers/paper.html").write_text(paper)
            if other is not None:
                (root / "papers/other.html").write_text(other)
            with patch("sys.argv", ["check_paper_links", str(root)]), contextlib.redirect_stdout(io.StringIO()):
                return check_paper_links.main()

    def test_canonical_and_location_alias_point_to_the_same_theorem(self):
        for anchor in ["thm:main", "thm%3Amain", "L-main.tex-1"]:
            with self.subTest(anchor=anchor):
                self.assertEqual(self.check(anchor, theorem() + NOTE), 0)

    def test_escaped_alias_and_attribute_order(self):
        paper = "<div id='thm:main' class='pr-thm'><span id='L-a&amp;b.tex-1' class='pr-lbl'></span></div>" + NOTE
        self.assertEqual(self.check("L-a%26b.tex-1", paper), 0)

    def test_nested_theorem_does_not_steal_outer_note(self):
        paper = '<div class="pr-thm" id="thm:main"><span class="pr-lbl" id="L-main.tex-1"></span>'
        paper += theorem("lemma:inner", "L-main.tex-2") + "</div>" + NOTE
        self.assertEqual(self.check(paper=paper), 0)

    def test_alias_of_a_different_theorem_fails(self):
        paper = theorem() + theorem("thm:other", "L-main.tex-2") + NOTE
        self.assertEqual(self.check(paper=paper), 1)

    def test_missing_anchor_fails(self):
        self.assertEqual(self.check("missing", theorem() + NOTE), 1)

    def test_different_paper_fails(self):
        self.assertEqual(self.check(paper=theorem(), other=theorem() + NOTE), 1)

    def test_both_one_way_links_fail(self):
        self.assertEqual(self.check(paper=theorem()), 1)
        self.assertEqual(self.check(None, theorem() + NOTE), 1)

    def test_duplicate_reciprocal_link_to_another_theorem_fails(self):
        paper = theorem() + NOTE + theorem("thm:other", "L-main.tex-2") + NOTE
        self.assertEqual(self.check(paper=paper), 1)

    def test_several_linked_theorems_each_link_back(self):
        paper = theorem() + NOTE + theorem("thm:other", "L-main.tex-2") + NOTE
        self.assertEqual(self.check(["thm:main", "thm:other"], paper), 0)

    def test_several_links_down_with_one_missing_back_fails(self):
        paper = theorem() + NOTE + theorem("thm:other", "L-main.tex-2")
        self.assertEqual(self.check(["thm:main", "thm:other"], paper), 1)

    def test_empty_build_fails(self):
        self.assertEqual(self.check(None), 1)


if __name__ == "__main__":
    unittest.main()
