"""Checks for the previous and next row under a breadcrumb (build_site.sibling_nav):
families step through their field, Lean statements through their family, papers through
their family, in the parent page's order; the ends show only the direction that exists;
the links carry rel=prev and rel=next. Standard library only:
python3 scripts/tests/test_sibling_nav.py
"""
from __future__ import annotations

import re
import sys
import tempfile
import unittest
from html import unescape
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_site as S  # noqa: E402
import family_page  # noqa: E402


def links(html: str) -> dict:
    nav = re.search(r'<nav class="sib".*?</nav>', html, re.S)
    if not nav:
        return {}
    return {rel: href for rel, href in re.findall(r'rel="(prev|next)" href="([^"]+)"', nav.group(0))}


class FamilySiblings(unittest.TestCase):
    def test_every_family_steps_through_its_field_in_order(self):
        for d in S.DISCIPLINES:
            ids = d["families"]
            for i, fid in enumerate(ids):
                html = S.sibling_nav("family", S.family_siblings(fid, "../"), discipline=d["name"])
                got = links(html)
                if len(ids) < 2:
                    self.assertEqual(html, "")
                    continue
                self.assertEqual(got.get("prev"), f"../families/{ids[i - 1]}.html" if i > 0 else None, fid)
                self.assertEqual(got.get("next"), f"../families/{ids[i + 1]}.html" if i + 1 < len(ids) else None, fid)
                self.assertIn(unescape(S.C("siblings.family_position", n=i + 1, total=len(ids), discipline=d["name"])),
                              unescape(html))

    def test_family_page_shows_the_row_under_its_breadcrumb(self):
        S.OUT = Path(tempfile.mkdtemp(prefix="atlas-sib-"))
        d = next(d for d in S.DISCIPLINES if len(d["families"]) > 2)
        fid = d["families"][1]
        family_page.build(S, S.FAM[fid])
        html = (S.OUT / "families" / f"{fid}.html").read_text(encoding="utf-8")
        self.assertLess(html.index('class="trail'), html.index('<nav class="sib"'))
        self.assertLess(html.index('<nav class="sib"'), html.index('class="fx-title'))
        self.assertEqual(links(html), {"prev": f"../families/{d['families'][0]}.html",
                                       "next": f"../families/{d['families'][2]}.html"})


class LeanSiblings(unittest.TestCase):
    def test_lean_statements_follow_the_family_page_order(self):
        sid = next(s["id"] for s in S.STATEMENTS if s.get("families") and len(S.FAM[s["families"][0]]["statements"]) > 2)
        items, i = S.lean_siblings(sid, "../")
        _fid, doc, _ = S.lean_family_doc(sid)
        sel = ((doc.get("selection") or {}).get("lean") or "")[2:]
        order = sorted([l["id"][2:] for l in doc["lean"]], key=lambda x: x != sel)
        order = [x for x in order if x in S.ST]
        self.assertEqual([h for h, _, _ in items], [f"../statements/{x}.html" for x in order])
        self.assertEqual(order[i], sid)
        first = S.sibling_nav("lean", (items, 0))
        last = S.sibling_nav("lean", (items, len(items) - 1))
        self.assertEqual(set(links(first)), {"next"})
        self.assertEqual(set(links(last)), {"prev"})

    def test_a_lone_statement_has_no_row(self):
        for s in S.STATEMENTS:
            found = S.lean_siblings(s["id"], "../")
            if found and len(found[0]) == 1:
                self.assertEqual(S.sibling_nav("lean", found), "")
                return


class PaperSiblings(unittest.TestCase):
    def test_papers_follow_the_family_page_order_and_name_earlier_editions(self):
        fid = next(f["id"] for f in S.FAMILIES
                   if any(h.get("status") == "previous-edition" for h in S.RD().family(f["id"]).get("paper_history") or []))
        hist = S.RD().family(fid)["paper_history"]
        cur = [h["id"][2:] for h in hist if h["status"] == "current"]
        prev = [h["id"][2:] for h in hist if h["status"] == "previous-edition"]
        items, i = S.paper_siblings(cur[0], "../")
        self.assertEqual(i, 0)
        self.assertEqual([h for h, _, _ in items][:len(cur) + len(prev)],
                         [f"../papers/{x}.html" for x in cur + prev])
        earlier = S.C("words.status_previous").lower()
        self.assertIn(earlier, items[len(cur)][2])
        self.assertNotIn(earlier, items[0][2])

    def test_rows_use_copy_and_show_no_ids(self):
        m = next(m for m in S.MANUSCRIPTS if m.get("family") and len(S.FAM[m["family"]]["manuscripts"]) > 2)
        html = S.sibling_nav("paper", S.paper_siblings(m["id"], "../"))
        self.assertIn(f'aria-label="{S.esc(S.C("siblings.paper_label"))}"', html)
        visible = re.sub(r"<[^>]+>", " ", re.sub(r'\s(aria-label|href|title)="[^"]*"', "", html))
        self.assertNotIn(m["id"], visible)
        self.assertNotIn("—", unescape(html))


if __name__ == "__main__":
    unittest.main()
