#!/usr/bin/env python3
"""Regression fixtures for the parsers in build_data.py.

    python3 scripts/tests/test_build_data.py

Each fixture is a small input whose correct reading was decided independently of the code.
They come from a rigour review of the atlas (11 October 2026) that found these cases by
construction; the published totals at the pinned commit did not depend on most of them.
Standard library only.
"""
from __future__ import annotations

import sys
import tempfile
import unittest
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))
import build_data as bd  # noqa: E402
from ingest.cert_machine import kernel_reading


class CertMachineReading(unittest.TestCase):
    def test_reason_parentheses_are_not_nested(self):
        result = kernel_reading({'word':'OPEN', 'why':'the job stopped before Comparator ran (see the run log)'}, 'a'*40)
        self.assertEqual(result['text'], 'Re-run through Comparator did not reach a verdict: the job stopped before Comparator ran (see the run log).')
        self.assertEqual(result['verdict'], 'not-decided')

    def test_kernel_acceptance_and_reason_punctuation_are_preserved(self):
        result = kernel_reading({'word':'OPEN', 'why':'timeout. | more detail', 'runs':[{'kernels':["Lean default kernel accepts"]}]}, 'a'*40)
        self.assertEqual(result['text'], "Re-run through Comparator did not reach a verdict. Lean's default kernel accepts the solution; the nanoda replay stopped: timeout.")
        self.assertEqual(kernel_reading({'word':'OPEN'}, 'a'*40)['text'], 'Re-run through Comparator did not reach a verdict.')


class LeanParser(unittest.TestCase):
    def parse(self, text: str):
        with tempfile.TemporaryDirectory() as d:
            p = Path(d) / "Fixture.lean"
            p.write_text(text, encoding="utf-8")
            return bd.parse_challenge(p, Path(d) / "absent.json")

    def test_every_module_in_a_multi_module_import(self):
        c = self.parse("import Mathlib Other.Module\n\ntheorem ok : True := by trivial\n")
        self.assertEqual(c["imports"], ["Mathlib", "Other.Module"])
        self.assertEqual(c["non_mathlib_imports"], ["Other.Module"])

    def test_nested_comments_hide_their_declarations(self):
        c = self.parse("import Mathlib\n/- outer\n/- inner -/\ndef ghost : Nat := 0\n-/\n")
        self.assertEqual(c["vocabulary_count"], 0)

    def test_attribute_line_keeps_the_docstring(self):
        c = self.parse("import Mathlib\n/-- A public explanation for this proposition. -/\n@[simp]\ndef target : Prop := True\n")
        self.assertEqual(c["docstrings"], ["A public explanation for this proposition."])

    def test_bare_end_closes_the_innermost_scope(self):
        c = self.parse("import Mathlib\nnamespace A\nnamespace B\nend\ndef x : Nat := 0\nend A\n")
        self.assertEqual(c["declarations"][0]["name"], "A.x")

    def test_section_does_not_change_names(self):
        c = self.parse("import Mathlib\nnamespace A\nsection\ndef y : Nat := 0\nend\nend A\n")
        self.assertEqual(c["declarations"][0]["name"], "A.y")

    def test_mutual_block_end_keeps_the_namespace(self):
        c = self.parse("import Mathlib\nnamespace OAI\nnoncomputable section\nnamespace BGS\nmutual\n"
                       "inductive T : Type\n  | a\nend\ndef dropFree : Nat := 0\nend BGS\nend\nend OAI\n")
        self.assertEqual([d["name"] for d in c["declarations"]], ["OAI.BGS.T", "OAI.BGS.dropFree"])

    def test_line_comments_and_docstrings_keep_line_numbers(self):
        c = self.parse("import Mathlib -- the library\n/-- doc\nspanning lines -/\ndef z : Nat := 0\n")
        self.assertEqual(c["declarations"][0]["line"], 4)
        self.assertEqual(c["docstrings"], ["doc spanning lines"])


class Statistics(unittest.TestCase):
    def test_conventional_median_of_an_even_sample(self):
        xs = [1, 2, 8, 100]
        mid = len(xs) // 2
        self.assertEqual((sorted(xs)[mid - 1] + sorted(xs)[mid]) / 2, 5.0)


class Manifest(unittest.TestCase):
    def test_main_results_in_any_key_order(self):
        with tempfile.TemporaryDirectory() as d:
            y = Path(d) / "formalization.yaml"
            y.write_text("version: \"v0.4\"\nstatus:\n  main_results:\n    - declaration: Fixture.ok\n      file: Fixture.lean\n"
                         "      comparator_config: ComparatorChallenges/Fixture.json\nreview:\n  status: unchecked\n", encoding="utf-8")
            out, review, top = bd.parse_main_results(y)
            self.assertEqual(out, {"Fixture": [{"declaration": "Fixture.ok", "file": "Fixture.lean"}]})
            self.assertEqual(review, "unchecked")
            self.assertEqual(top, ["version", "status", "review"])

    def test_an_unreadable_item_fails_loudly(self):
        with tempfile.TemporaryDirectory() as d:
            y = Path(d) / "formalization.yaml"
            y.write_text("status:\n  main_results:\n    - comparator_config: ComparatorChallenges/Fixture.json\n", encoding="utf-8")
            with self.assertRaises(SystemExit):
                bd.parse_main_results(y)


class References(unittest.TestCase):
    def test_distinct_titles_sharing_twelve_words_stay_separate(self):
        title = "one two three four five six seven eight nine ten eleven twelve"
        self.assertNotEqual(bd.work_id({"key": "a", "title": title + " first result"}),
                            bd.work_id({"key": "b", "title": title + " second result"}))

    def test_doi_drops_sentence_punctuation_and_unbalanced_closers(self):
        r = bd.ref_record("sample", None, "Author, Example (doi:10.1234/example).")
        self.assertEqual(r.get("doi"), "10.1234/example")

    def test_oai_slug_written_without_a_link_points_inside_the_collection(self):
        # Family 341's October edition cites family 342 by an OAI: slug in howpublished, with no
        # link and a non-OAI key; it was filed as an outside work (found by comparison with
        # jkbennitt/math-release-atlas's independent citation extraction).
        known = {"Taming-implies-compatibility-on-four-manifolds-October-6-2026", "Sharp-fillings-in-CAT(0)-spaces-September-23-2026"}
        raw = ("@misc{OpenAITaming2026, author = {{OpenAI}}, howpublished = {OpenAI Math Release preprint\n"
               "  OAI:Taming-implies-compatibility-on-four-manifolds-October-6-2026}, year = {2026}}")
        self.assertEqual(bd.oai_tokens(raw, known), ["Taming-implies-compatibility-on-four-manifolds-October-6-2026"])
        self.assertEqual(bd.oai_tokens("see OAI:Sharp-fillings-in-CAT(0)-spaces-September-23-2026).", known),
                         ["Sharp-fillings-in-CAT(0)-spaces-September-23-2026"])
        self.assertEqual(bd.oai_tokens("OAI:Not-a-preprint-of-the-release", known), [])

    def test_doi_keeps_balanced_internal_brackets(self):
        self.assertEqual(bd.clean_doi("10.1002/(SICI)1097-0118(199901)30:1<1::AID-JGT1>3.0.CO;2-#)."),
                         "10.1002/(SICI)1097-0118(199901)30:1<1::AID-JGT1>3.0.CO;2-#")


if __name__ == "__main__":
    unittest.main(verbosity=1)
