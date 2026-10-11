#!/usr/bin/env python3
"""Check that statement pages and the papers' reading pages link each other, both ways.

    python3 scripts/check_paper_links.py [site/_build]

Run after scripts/build_site.py and scripts/build_papers.py. A statement page whose
paired paper statement has a reading page links down to it (papers/<slug>.html#<anchor>);
that theorem on the reading page links back up to the statement page. This fails when
a link goes one way only, lands on another paper or theorem, or names an anchor the
reading page does not have. Standard library only.
"""
from __future__ import annotations

import html
import re
import sys
from pathlib import Path
from urllib.parse import unquote

ROOT = Path(__file__).resolve().parent.parent


def main() -> int:
    build = Path(sys.argv[1]) if len(sys.argv) > 1 else ROOT / "site" / "_build"
    down = {}  # statement id -> (paper slug, anchor)
    for p in sorted((build / "statements").glob("*.html")):
        m = re.search(r'class="claim__src"><a href="\.\./papers/([^"#]+)\.html#([^"]+)"', p.read_text(encoding="utf-8"))
        if m:
            down[p.stem] = (unquote(m.group(1)), html.unescape(unquote(m.group(2))))
    up = {}  # statement id -> (paper slug, id of the theorem block holding the note)
    pages = {}
    for p in sorted((build / "papers").glob("*.html")):
        t = pages[p.stem] = p.read_text(encoding="utf-8")
        starts = [(m.start(), m.group(1)) for m in re.finditer(r'<div class="pr-thm[^"]*" id="([^"]+)"', t)]
        for note in re.finditer(r'<p class="pr-lean">(.*?)</p>', t, re.S):
            owner = [bid for pos, bid in starts if pos < note.start()]
            for sid in re.findall(r'href="\.\./statements/([^"]+)\.html"', note.group(1)):
                up[unquote(sid)] = (p.stem, html.unescape(owner[-1]) if owner else None)
    problems = []
    problems += [f"{s}: links down to its paper statement, which does not link back" for s in sorted(set(down) - set(up))]
    problems += [f"{s}: linked up from a theorem, but its statement page does not link down" for s in sorted(set(up) - set(down))]
    for s in sorted(set(down) & set(up)):
        if down[s] != up[s]:
            problems.append(f"{s}: links down to {down[s]} but is linked up from {up[s]}")
    for s, (slug, anchor) in sorted(down.items()):
        t = pages.get(slug)
        if t is None or f'id="{html.escape(anchor, quote=True)}"' not in t:
            problems.append(f"{s}: anchor #{anchor} is missing from papers/{slug}.html")
    for line in problems[:40]:
        print(line)
    print(f"paper links: {len(down)} statements link down, {len(up)} are linked up; "
          f"{'OK' if not problems else str(len(problems)) + ' problems'}")
    return 1 if problems else 0


if __name__ == "__main__":
    sys.exit(main())
