#!/usr/bin/env python3
"""Check that statement pages and the papers' reading pages link each other, both ways.

    python3 scripts/check_paper_links.py [site/_build]

Run after scripts/build_site.py and scripts/build_papers.py. A statement page links
down to each paper statement it is paired with that has a reading page
(papers/<slug>.html#<anchor>; a Lean statement can be linked to several); each of those
theorems on its reading page links back up to the statement page. This fails when a
link goes one way only, lands on another paper or theorem, or names an anchor the
reading page does not have. Standard library only.
"""
from __future__ import annotations

import html
import re
import sys
from html.parser import HTMLParser
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent


class PaperAnchors(HTMLParser):
    """Resolve explicit label aliases to their enclosing theorem.

    Atlas notes follow the theorem, outside its div. Remember the last theorem
    closed as well as opened so a nested theorem cannot steal its parent's note.
    """

    def __init__(self):
        super().__init__()
        self.ids = set()
        self.aliases = {}
        self.links = {}
        self.divs = []
        self.last_theorem = None
        self.in_note = False

    def handle_starttag(self, tag, attrs):
        attrs = dict(attrs)
        classes = attrs.get("class", "").split()
        anchor = attrs.get("id")
        if anchor:
            self.ids.add(anchor)
        if tag == "div":
            theorem = anchor if "pr-thm" in classes else None
            self.divs.append(theorem)
            if theorem:
                self.last_theorem = theorem
                self.aliases[theorem] = theorem
        if anchor and "pr-lbl" in classes:
            owner = next((item for item in reversed(self.divs) if item), None)
            if owner:
                self.aliases[anchor] = owner
        if tag == "p":
            self.in_note = "pr-lean" in classes
        if tag == "a" and self.in_note:
            match = re.fullmatch(r"\.\./statements/([^/]+)\.html", attrs.get("href", ""))
            if match:
                self.links.setdefault(unquote(match[1]), set()).add(self.last_theorem)

    def handle_endtag(self, tag):
        if tag == "p":
            self.in_note = False
        if tag == "div" and self.divs:
            theorem = self.divs.pop()
            if theorem:
                self.last_theorem = theorem


def main() -> int:
    build = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site" / "_build"
    down = {}  # statement id -> {(paper slug, anchor)}
    for p in sorted((build / "statements").glob("*.html")):
        found = re.findall(r'class="claim__src"><a href="\.\./papers/([^"#]+)\.html#([^"]+)"', p.read_text(encoding="utf-8"))
        if found:
            down[p.stem] = {(unquote(a), html.unescape(unquote(b))) for a, b in found}
    up = {}  # statement id -> set of (paper slug, theorem id)
    pages = {}
    for p in sorted((build / "papers").glob("*.html")):
        page = pages[p.stem] = PaperAnchors()
        page.feed(p.read_text(encoding="utf-8"))
        for sid, owners in page.links.items():
            up.setdefault(sid, set()).update((p.stem, owner) for owner in owners)
    problems = []
    if not down:
        problems.append("no statement-to-paper links found; build the site before checking")
    problems += [f"{s}: links down to its paper statement, which does not link back" for s in sorted(set(down) - set(up))]
    problems += [f"{s}: linked up from a theorem, but its statement page does not link down" for s in sorted(set(up) - set(down))]
    for s in sorted(set(down) & set(up)):
        targets = {(slug, pages[slug].aliases.get(anchor, anchor) if slug in pages else anchor) for slug, anchor in down[s]}
        if up[s] != targets:
            problems.append(f"{s}: links down to {sorted(down[s])} but is linked up from {sorted(up[s], key=str)}")
    for s, links in sorted(down.items()):
        for slug, anchor in sorted(links):
            page = pages.get(slug)
            if page is None or anchor not in page.ids:
                problems.append(f"{s}: anchor #{anchor} is missing from papers/{slug}.html")
    for line in problems[:40]:
        print(line)
    print(f"paper links: {len(down)} statements link down, {len(up)} are linked up; "
          f"{'OK' if not problems else str(len(problems)) + ' problems'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
