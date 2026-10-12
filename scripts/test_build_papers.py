#!/usr/bin/env python3
"""Regression fixtures for the paper reader in build_papers.py.

    python3 scripts/test_build_papers.py
    KATEX_JS=path/to/node_modules/katex python3 scripts/test_build_papers.py   # also renders with KaTeX

Each fixture comes from a failure found by building every paper of the release.
Standard library only.
"""
from __future__ import annotations

import json
import re
import signal
import subprocess
import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
import build_papers as bp  # noqa: E402


class LayoutCommands(unittest.TestCase):
    def test_needspace_produces_nothing(self):
        # \Needspace{<length>} (needspace package) only asks LaTeX for room on the page.
        for name in ("Needspace", "needspace"):
            self.assertEqual(bp.IGNORE.get(name), 1, name)


SAVED_ARROWS = r"""\documentclass{article}
\expandafter\let\csname PaperOriginalhookrightarrow\endcsname\hookrightarrow
\expandafter\let\csname PaperOriginalmapsto\endcsname\mapsto
\newcommand{\PaperArrowText}[2]{\mathrel{\begingroup
  \expandafter\let\expandafter\hookrightarrow\csname PaperOriginalhookrightarrow\endcsname
  \expandafter\let\expandafter\mapsto\csname PaperOriginalmapsto\endcsname
  \pdfliteral direct{/Span << /ActualText <FEFF#1> >> BDC}%
  #2\pdfliteral direct{EMC}\endgroup}}
\renewcommand{\hookrightarrow}{\PaperArrowText{21AA}{\csname PaperOriginalhookrightarrow\endcsname}}
\renewcommand{\mapsto}{\PaperArrowText{21A6}{\csname PaperOriginalmapsto\endcsname}}
\begin{document}
We have $A\hookrightarrow B$ and $x\mapsto y$, and $C\lhook\joinrel\longrightarrow D$.
\end{document}
"""


class MacroExpansion(unittest.TestCase):
    def convert(self, tex: str, statements=None):
        bp.import_site()
        with tempfile.TemporaryDirectory() as d:
            folder = Path(d) / "preprints" / "fixture"
            folder.mkdir(parents=True)
            (folder / "paper.tex").write_text(tex, encoding="utf-8")
            m = {"id": "fixture", "title": "Fixture", "tex": {"main": "paper.tex"}}
            if statements is not None:
                m["statements"] = statements
            p = bp.Paper(m, Path(d))
            signal.signal(signal.SIGALRM, lambda *_: (_ for _ in ()).throw(TimeoutError("conversion runs away")))
            signal.alarm(30)
            try:
                p.convert()
            finally:
                signal.alarm(0)
        return p

    def test_a_copied_built_in_wrapped_for_pdf_readers_stays_the_built_in(self):
        # 3 papers: \NewCommandCopy{\OriginalMapsto}{\mapsto} then \renewcommand{\mapsto}{... \OriginalMapsto ...}
        p = self.convert("\\documentclass{article}\n\\NewCommandCopy{\\OriginalMapsto}{\\mapsto}\n"
                         "\\renewcommand{\\mapsto}{\\BeginAccSupp{method=hex,unicode,ActualText=21A6}\\OriginalMapsto\\EndAccSupp{}}\n"
                         "\\begin{document}\nSo $x\\mapsto y$.\n\\end{document}\n")
        self.assertEqual(p.dropped_wrappers, ["mapsto"])
        self.assertNotIn("\\mapsto", p.katex)
        self.assertEqual(p.katex.get("\\OriginalMapsto"), "\\mapsto")

    def test_let_copies_a_definition_of_the_paper(self):
        p = self.convert("\\documentclass{article}\n\\newcommand{\\foo}{a}\n\\let\\oldfoo\\foo\n"
                         "\\renewcommand{\\foo}{\\oldfoo b}\n\\begin{document}\n$\\foo$\n\\end{document}\n")
        self.assertEqual(p.katex.get("\\oldfoo"), "a")
        self.assertEqual(p.katex.get("\\foo"), "\\oldfoo b")

    def test_a_labelled_diagram_keeps_its_number_and_reference(self):
        p = self.convert("\\documentclass{article}\n\\begin{document}\n\\begin{equation}\\label{eq:square}"
                         "\\begin{tikzcd} A \\arrow[r] & B \\end{tikzcd}\\end{equation}\nBy \\eqref{eq:square}.\n"
                         "\\end{document}\n")
        self.assertIn("eq:square", p.labels)
        self.assertEqual(p.unresolved_refs, [] if isinstance(p.unresolved_refs, list) else type(p.unresolved_refs)())
        self.assertIn('class="pr-eqno">(1)<', p.body_html)

    def test_a_page_position_test_shows_nothing(self):
        p = self.convert("\\documentclass{article}\n\\begin{document}\nBefore.\n"
                         "\\par\\ifdim\\dimexpr\\pagegoal-\\pagetotal\\relax<6\\baselineskip\\newpage\\fi\nAfter.\n"
                         "\\end{document}\n")
        self.assertNotIn("<6", p.body_html)
        self.assertNotIn("pagegoal", "".join(p.unknown_cmds))
        self.assertIn("After.", p.body_html)

    def test_printed_numbers_follow_the_papers_counters(self):
        # data/statement_numbers.json: the head each statement prints, bound to its source line
        tex = ("\\documentclass{article}\n\\newtheorem{theorem}{Theorem}[section]\n\\newtheorem{lemma}[theorem]{Lemma}\n"
               "\\newtheorem*{claim}{Claim}\n\\begin{document}\n\\section{One}\n"
               "\\begin{theorem}\\label{t:a}\nA.\n\\end{theorem}\n\\begin{lemma}\nB.\n\\end{lemma}\n"
               "\\begin{claim}\nC.\n\\end{claim}\n\\end{document}\n")
        sts = [{"file": "paper.tex", "line": 7, "label": "t:a", "sha256": "sha256:a"},
               {"file": "paper.tex", "line": 10, "label": None, "sha256": "sha256:b"},
               {"file": "paper.tex", "line": 13, "label": None, "sha256": "sha256:c"},
               {"file": "paper.tex", "line": 99, "label": None, "sha256": "sha256:absent"}]
        p = self.convert(tex, statements=sts)
        got = [(r["line"], r["kind"], r["number"], r["statement_sha256"]) for r in p.printed_numbers()]
        self.assertEqual(got, [(7, "Theorem", "1.1", "sha256:a"), (10, "Lemma", "1.2", "sha256:b"),
                               (13, "Claim", None, "sha256:c")])

    def test_csname_spells_a_let_name(self):
        s = r"\csname PaperOriginalmapsto\endcsname\mapsto"
        name, k = bp.read_cs_name(s, 0, len(s))
        self.assertEqual((name, s[k:]), ("PaperOriginalmapsto", r"\mapsto"))

    def test_assignments_leave_nothing_for_katex(self):
        body = (r"\begingroup\expandafter\let\expandafter\mapsto\csname PaperOriginalmapsto\endcsname"
                r"\pdfliteral direct{EMC}#2\let\x=\y\endgroup")
        self.assertEqual(bp.strip_assignments(body), r"\begingroup#2\endgroup")

    def test_hooked_arrows_use_katex_forms(self):
        self.assertEqual(bp.katex_compat(r"A\lhook\joinrel\longrightarrow B"), r"A\xhookrightarrow{\quad} B")
        self.assertEqual(bp.katex_compat(r"A\lhook\joinrel\rightarrow B"), r'A\mathrel{\char"21AA} B')

    def test_saved_arrows_expand_once(self):
        # Two papers of the release save the built-in arrows with \let, then redefine them
        # through the saved names inside a macro that re-lets every arrow. Expanding the
        # re-let names as formulas grew each formula sixfold per level, to 21 GB.
        p = self.convert(SAVED_ARROWS)
        texts = [f["tex"] for f in p.formulas]
        self.assertEqual(len(texts), 3, texts)
        self.assertLess(max(len(t) for t in texts), 200, texts)
        self.assertEqual(sum(t.count("\\hookrightarrow") for t in texts), 1, texts)
        self.assertEqual(sum(t.count("\\mapsto") for t in texts), 1, texts)
        self.assertIn("\\xhookrightarrow", texts[2])
        for t in texts:
            for gone in ("\\let", "\\pdfliteral", "\\csname", "PaperArrowText", "atlasbuiltin"):
                self.assertNotIn(gone, t)


class MapStatementReferences(unittest.TestCase):
    def test_packet_urls_change_when_rendering_changes_at_the_same_pin(self):
        import build_universe as universe
        with tempfile.TemporaryDirectory() as temporary:
            directory = Path(temporary)
            packet = directory / "universe-detail-0.json"
            packet.write_text('{"generation_id":"same-pin","html":"(eq:label)"}')
            before = universe.packet_version(directory)
            self.assertEqual(before, universe.packet_version(directory))
            packet.write_text('{"generation_id":"same-pin","html":"(2.1)"}')
            self.assertNotEqual(before, universe.packet_version(directory))

    def test_map_excerpts_use_the_papers_printed_equation_numbers(self):
        import build_universe as universe
        universe.import_site()
        cases = [
            ("A-local-Penrose-inequality-for-conformal-perturbations-of-Schwarzschild-anti-de-Sitter-data-October-5-2026",
             "thm:main", ("2.1", "2.6"), ("eq:background", "eq:branch")),
            ("Asymptotic-midpoint-uniform-convexity-and-unbounded-diamond-distortion-in-a-reflexive-tree-space-September-27-2026",
             "thm:main", ("1.4",), ("eq:segment-norm",)),
        ]
        for manuscript, label, numbers, raw_labels in cases:
            with self.subTest(manuscript=manuscript):
                result = universe.statement_html(manuscript, {"name": label}, "fixture")
                self.assertIsNotNone(result)
                for number in numbers:
                    self.assertIn(f">({number})</a>", result["html"])
                for raw in raw_labels:
                    self.assertNotIn(f">({raw})</span>", result["html"])
                    self.assertIn(f".html#{raw}", result["html"])


class SupportMacros(unittest.TestCase):
    def test_no_fbox_macro(self):
        # KaTeX defines \boxed through \fbox, so a \fbox macro written with \boxed loops.
        self.assertNotIn("\\fbox", bp.SUPPORT_MACROS)

    @unittest.skipUnless(bp.katex_js() and bp.node_bin(), "needs node and KATEX_JS")
    def test_every_support_macro_expands_without_a_loop(self):
        items = []
        for name, body in bp.SUPPORT_MACROS.items():
            n = max((int(k) for k in re.findall(r"#(\d)", body)), default=0)
            items.append({"paper": "fixture", "tex": name + "{a}" * n, "display": False})
        items.append({"paper": "fixture", "tex": "\\boxed{x+y}", "display": True})
        items[0]["macros"] = bp.SUPPORT_MACROS
        r = subprocess.run([bp.node_bin(), str(bp.CHECKER)], input=json.dumps(items), capture_output=True,
                           text=True, timeout=120, env={**__import__("os").environ, "KATEX_JS": bp.katex_js()})
        self.assertEqual(r.returncode, 0, r.stderr)
        loops = [items[f["index"]]["tex"] for f in json.loads(r.stdout)["failures"]
                 if "Too many expansions" in f.get("error", "")]
        self.assertEqual(loops, [])


if __name__ == "__main__":
    unittest.main(verbosity=1)
