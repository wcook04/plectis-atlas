"""Checks for the family page (scripts/family_page.py) on the specimen families.

Builds the pages into a temporary directory and checks what DESIGN.md and the brief
pin: the anchors other pages link to, the theorem shown only when the backend names a
candidate, every state in words (no symbol mark), every inspection trigger with its
record, no repeated ids, and every "what is left to check" link carrying its target's
exact fingerprint. Standard library only: python3 scripts/tests/test_family_page.py
"""
from __future__ import annotations

import re
import sys
import tempfile
from collections import Counter
from html import unescape
from pathlib import Path
from urllib.parse import unquote

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import build_site as S  # noqa: E402
import family_page  # noqa: E402

SPECIMENS = ["001", "003", "017", "032", "159", "260", "099", "312", "238", "090", "081", "102"]
ANCHORS = ["h-desc", "h-lean", "h-ms", "h-explain", "h-checks", "compare", "claim", "h-bench", "h-cites", "h-readings"]


def main() -> int:
    tmp = Path(tempfile.mkdtemp(prefix="atlas-family-"))
    S.OUT = tmp
    fails = []
    for fid in SPECIMENS:
        family_page.build(S, S.FAM[fid])
        html = (tmp / "families" / f"{fid}.html").read_text(encoding="utf-8")
        doc = family_page._reader().family(fid)

        def check(ok, what):
            if not ok:
                fails.append(f"{fid}: {what}")
        ids = re.findall(r' id="([^"]+)"', html)
        for a in ANCHORS:
            check(a in ids, f"anchor #{a} missing")
        dup = [k for k, v in Counter(ids).items() if v > 1]
        check(not dup, f"repeated ids {dup[:4]}")
        for h in set(re.findall(r'href="#([^"]+)"', html)):
            check(h in ids, f"in-page link #{h} has no target")
        for t in set(re.findall(r'data-inspect="([^"]+)"', html)):
            check(f'<template id="{t}">' in html, f"inspection record {t} missing")
        check("<details" not in html, "a fold on the page")
        check('class="sp ' not in html and "sp-half" not in html, "a symbol mark is drawn")
        check("assets/evidence.css" not in html and "assets/figure.css" not in html, "a retired sheet is linked")
        claim = doc["claim"]
        if claim["state"] == "candidate" and claim.get("primary_candidate"):
            check('id="claim-theorem"' in html, "the candidate theorem is not the centrepiece")
        else:
            check('id="claim-theorem"' not in html, "an unresolved headline shows a single theorem")
            notes = [family_page.W(k) for k in ("claim.unresolved", "claim.unresolved_one", "claim.unresolved_none")]
            page_text = unquote(html)
            said = next((n for n in notes if n in page_text), None)
            check(said is not None, "the unresolved sentence is missing")
            # The page leads with what the papers state; how those statements were chosen follows them.
            if said and 'id="claim-alt-1"' in html:
                check(page_text.index('id="claim-alt-1"') < page_text.index(said), "the unresolved note comes before the statements")
        for rc in doc.get("remaining_checks") or []:
            fp = (rc.get("contribution_target") or {}).get("fingerprint")
            if fp:
                check(fp in unquote(html), f"no contribution link carries {fp[:19]}")
        if doc.get("lean"):
            for l in doc["lean"]:
                check(f'id="lean-{l["id"][2:]}"' in html, f"no comparison for {l['id']}")
        check(" — " not in re.sub(r"“[^”]*”|<code.*?</code>|<pre.*?</pre>|<template.*?</template>", "", html, flags=re.S)
              .split("<main", 1)[-1].split("Their method", 1)[0], "an em dash in the page's own words")
        for what in compare_buttons(fid, html):
            check(False, what)
    fails += status_group_counts()
    fails += tied_order()
    fails += definition_only_statement(tmp)
    fails += complete_theorem_snippets(tmp)
    for f in fails:
        print("FAIL", f)
    print(f"family page: {len(SPECIMENS)} specimens, {len(fails)} failures")
    return 1 if fails else 0


def definition_only_statement(tmp: Path) -> list:
    """The definition-only challenge must not open blank in any reading view."""
    stmt = S.ST["ElementaryPositivity"]
    S.build_statement(stmt)
    family_page.build(S, S.FAM["169"])
    fails = []
    views = [
        ("statements/ElementaryPositivity.html", "lean--read"),
        ("cards/ElementaryPositivity.html", "lean--card"),
        ("families/169.html", "fx-lean__code"),
    ]
    for rel, css in views:
        html = (tmp / rel).read_text(encoding="utf-8")
        blocks = re.findall(r'<pre class="[^"]*' + css + r'[^"]*"><code>(.*?)</code></pre>', html, re.S)
        plain = unescape(re.sub(r"<[^>]*>", "", "".join(blocks)))
        if "def elementaryPositivityWitness" not in plain or "G.PermutationWitness" not in plain:
            fails.append(f"{rel}: configured definition is missing from the Lean snippet")
    page = (tmp / views[0][0]).read_text(encoding="utf-8")
    opening = page.split('id="h-lean-read"', 1)[1].split('<h3', 1)[0]
    if "verification settings name no theorem" not in opening or "name and type only" not in opening:
        fails.append("ElementaryPositivity: definition-only qualification missing beside the snippet")
    if "Definition selected for comparison:" not in page or "Theorem selected for verification:" in page:
        fails.append("ElementaryPositivity: definition-only target labelled as a theorem")
    report_heading = re.search(r'<h2[^>]*id="h-runs"[^>]*>(.*?)</h2>', page, re.S)
    if not report_heading or "proof" in report_heading[1].lower():
        fails.append("ElementaryPositivity: run report heading implies a theorem proof was verified")
    family = (tmp / "families/169.html").read_text(encoding="utf-8")
    if family_page.W("compare.sorry") in family or "by its name and type only" not in family:
        fails.append("Family 169: definition-only snippet is described as a theorem")
    card = (tmp / "cards/ElementaryPositivity.html").read_text(encoding="utf-8")
    if "states the theorem" in card or "checks only the name and type" not in card:
        fails.append("ElementaryPositivity card: definition-only qualification missing")
    return fails


def complete_theorem_snippets(tmp: Path) -> list:
    """Named arguments and qualified names must not truncate or hide a theorem."""
    fails = []
    specimens = {
        "CartierChartCompactnessSupport": "normalizedWeights a) := by",
        "CoveringDensity": "theorem CoveringOrder.optimal_order : CoveringOrder.OptimalOrder := by",
        "MatroidProphet": "theorem one_sample.{u} : OneSampleChallenge.{u} := by",
        "SiegelZeros": "theorem WeightedTorusJets.dirichletRealZeroBound_proof :",
        "CKSBondiPenrose": "(1-ε R) * OAI.CKSSourceExterior.cutArea g D ≤ OAI.CKSSourceExterior.cutArea gR D := by",
    }
    for sid, ending in specimens.items():
        plain = unescape(re.sub(r"<[^>]*>", "", S.lean_snippet_html(S.ST[sid])))
        if ending not in plain:
            fails.append(f"{sid}: configured theorem excerpt is incomplete")
    stmt = S.ST["CartierChartCompactnessSupport"]
    S.build_statement(stmt)
    family_page.build(S, S.FAM["066"])
    for rel, css in [
        ("statements/CartierChartCompactnessSupport.html", "lean--read"),
        ("cards/CartierChartCompactnessSupport.html", "lean--card"),
        ("families/066.html", "fx-lean__code"),
    ]:
        html = (tmp / rel).read_text(encoding="utf-8")
        blocks = re.findall(r'<pre class="[^"]*' + css + r'[^"]*"><code>(.*?)</code></pre>', html, re.S)
        plain = unescape(re.sub(r"<[^>]*>", "", "".join(blocks)))
        if "normalizedWeights a) := by" not in plain or "sorry" not in plain:
            fails.append(f"{rel}: compactness statement or proof placeholder is truncated")
    return fails


def compare_buttons(fid: str, html: str) -> list:
    """"Compare with Lean" sits only on a theorem card whose statement a Lean statement is
    paired with, and opens that pairing; a card no Lean is paired with says so instead."""
    c = family_page.Ctx(S, S.FAM[fid])
    claim = c.doc.get("claim") or {}
    if claim.get("state") == "candidate" and claim.get("primary_candidate") in c.stmts:
        shown = family_page.opening_statements(c)[0]
    else:
        alts = [a for a in claim.get("alternatives") or [] if a.get("statement_id") in c.stmts]
        shown = [a["statement_id"] for a in family_page.tie_order(c, alts)][:3]
    section = html.split('id="claim"', 1)[-1].split("</section>", 1)[0]
    cards = re.findall(r'<article class="fx-st[^"]*" id="claim-[^"]+"(.*?)</article>', section, flags=re.S)
    out = []
    for sid, body in zip(shown, cards):
        lean = family_page.paired_lean(c, sid)
        hrefs = re.findall(r'href="#([^"]+)"[^>]*>' + re.escape(family_page.W("actions.compare")) + "<", body)
        if lean and hrefs != [f"lean-{lean}"]:
            out.append(f"{sid}: paired with {lean}, but its compare links are {hrefs}")
        if not lean and hrefs:
            out.append(f"{sid}: no Lean statement is paired with it, yet it offers {hrefs}")
        if not lean and c.leans and family_page.W("claim.no_lean_paired") not in body:
            out.append(f"{sid}: no Lean statement is paired with it, and the card does not say so")
    return out


def tied_order() -> list:
    """Among candidates the backend ties, the page opens on one a Lean statement is paired
    with whenever there is one, then on the lead paper's; the set of tied candidates is
    the backend's, unchanged."""
    fails = []
    for fid in S.FAM:
        c = family_page.Ctx(S, S.FAM[fid])
        claim = c.doc.get("claim") or {}
        if claim.get("state") == "candidate" and claim.get("primary_candidate") in c.stmts:
            continue
        alts = [a for a in claim.get("alternatives") or [] if a.get("statement_id") in c.stmts]
        if not alts:
            continue
        top = max(a.get("score") or 0 for a in alts)
        tied = [a["statement_id"] for a in alts if (a.get("score") or 0) == top]
        order = [a["statement_id"] for a in family_page.tie_order(c, alts)]
        if sorted(order) != sorted(tied):
            fails.append(f"{fid}: the tie shown is not the backend's tie")
        if any(family_page.paired_lean(c, s) for s in tied) and not family_page.paired_lean(c, order[0]):
            fails.append(f"{fid}: opens on {order[0]}, which no Lean statement is paired with, before a paired candidate")
    return fails


NUMBER_WORDS = {1: "one", 2: "two", 3: "three", 4: "four", 5: "five"}


def status_group_counts() -> list:
    """Every family's status line counts the outside groups in accepted_current_sources:
    one group is never "groups", and on a single Lean statement the number is exact."""
    fails = []
    for fid in S.FAM:
        c = family_page.Ctx(S, S.FAM[fid])
        if not c.leans:
            continue
        line = family_page.status_runs(c)
        groups = {s for l in c.leans for s in l.get("accepted_current_sources") or []}
        if not groups:
            ok = line.startswith("no independent acceptance report")
        elif len(groups) == 1:
            ok = line.startswith("one independent group ") and "groups" not in line
        else:
            ok = "independent groups" in line and not line.startswith("one independent group")
            if len(c.leans) == 1 or sum(1 for l in c.leans if l.get("accepted_current_sources")) == 1:
                ok = ok and line.startswith(f"{NUMBER_WORDS.get(len(groups), len(groups))} independent groups ")
        if not ok:
            fails.append(f"{fid}: status line {line!r} for {len(groups)} accepting groups")
    return fails


if __name__ == "__main__":
    sys.exit(main())
