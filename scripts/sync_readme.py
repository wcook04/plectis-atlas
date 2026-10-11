#!/usr/bin/env python3
"""Regenerate the computed blocks of README.md from data/*.json.

Blocks live between <!-- numbers:start --> / <!-- numbers:end --> and
<!-- example:start --> / <!-- example:end -->. Run after build_data.py.
`--check` exits 1 if README.md is out of date. Standard library only.
"""
from __future__ import annotations

import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


def n(x: int) -> str:
    return f"{x:,}"


def numbers_block(s: dict) -> str:
    env = s["paper_statement_environments"]
    rows = [
        f"- **{n(s['families'])} result families** in {s['disciplines']} disciplines, from **{n(s['manuscripts_current'])} current manuscripts** "
        f"({s['manuscripts_withdrawn']} more were withdrawn and {s['manuscripts_previous_editions']} earlier editions remain in the collection).",
        f"- **{n(s['statements_lean'])} Comparator challenge files**, {n(s['statements_lean_main_results'])} of them named in OpenAI's list of main results "
        f"({n(s['main_result_declarations'])} declarations). {n(s['families_with_lean'])} families have a Lean scope note linking at least one challenge file, "
        f"and those notes name {n(s['manuscripts_with_lean'])} current manuscripts as accompanying papers.",
        f"- **{n(s['lean_statements_pure_mathlib'])} challenge files** import only Mathlib and add no local vocabulary. The median file adds "
        f"{s['lean_vocabulary_median']} local vocabulary declarations (definitions, structures, instances, notation and similar), and the largest "
        f"({s['lean_vocabulary_max_statement']}) adds {n(s['lean_vocabulary_max'])}. Each one is part of what the statement means, so a reader checks it against the paper.",
        f"- **{n(s['manuscripts_citing_collection'])} manuscripts** cite other manuscripts in the collection ({n(s['internal_citation_edges'])} citation links). "
        f"{n(s['manuscripts_citing_unformalised_collection_results'])} of them cite at least one manuscript with no accompanying Lean statement.",
        f"- **{n(s['external_citations'])} resolved references** to work outside the collection, which group automatically into {n(s['external_works_cited'])} works "
        f"(by DOI, then arXiv identifier, then title; the grouping is unaudited).",
        f"- The TeX sources of the current manuscripts contain {n(env.get('theorem', 0))} theorem, {n(env.get('proposition', 0))} proposition, "
        f"{n(env.get('corollary', 0))} corollary and {n(env.get('lemma', 0))} lemma environments, repeated statements included.",
    ]
    sc = s.get("scope_coverage")
    if sc and sc.get("stale"):
        rows.append("- **Draft scope reading.** Withheld: it was made for a different upstream commit or set of challenge files "
                    f"({'; '.join(sc.get('stale_reasons') or [])}).")
    elif sc:
        k = sc["classes"]
        rows.append(
            f"- **Draft scope reading.** Of {n(sc['statements_classified'])} challenge files, {n(k.get('headline', 0))} state a paper's headline theorem as stated, "
            f"{n(k.get('headline-part', 0))} part of one, {n(k.get('consequence', 0))} a consequence, {n(k.get('weaker', 0))} a weaker form and "
            f"{n(k.get('supporting', 0))} a supporting result; for {n(k.get('unclear', 0))} the note leaves it unclear. "
            f"In {n(len(sc['families_with_lean_but_no_headline_coverage']))} families with Lean statements, no statement covers the headline result or part of it, "
            f"and in {n(len(sc.get('families_partial_headline_only') or []))} more only part of it is covered. "
            "An AI agent classified each file from OpenAI's scope note, quoting the note (`curated/scope_coverage.json`); no person has reviewed it."
        )
    ra = s.get("readers_agreement") or {}
    if ra.get("agree-full") is not None:
        rows.append(
            f"- **Two independent readers.** [MathVet](https://math.vet) and Carlos Toledo's [cert-machine](https://github.com/carlostoledo1891/cert-machine), "
            f"reading each family's Lean against its headline independently of OpenAI and of each other, agree that {n(ra.get('agree-full', 0))} families' "
            f"Lean states the headline and {n(ra.get('agree-less', 0))} states less; they disagree on {n(ra.get('disagree', 0))}. "
            "Their verdicts sit on each family page, credited.")
    try:
        pa = load("paper_acceptance.json")
    except FileNotFoundError:
        pa = None
    if pa and pa.get("upstream_commit") == s["upstream"]["commit"] and pa.get("summary"):
        ps = pa["summary"]
        rest = ps.get("partial", 0)
        rows.append(
            f"- **Every paper in the browser.** {n(ps['accepted'])} of the {n(ps['papers'])} current manuscripts have a full reading page made from "
            f"their TeX, with every formula, cross-reference, citation and theorem anchor checked (figures are shown as placeholders); "
            f"the other {n(rest)} have a reading page with a banner listing what did not convert"
            + (f", and {n(ps['unavailable'])} have none" if ps.get("unavailable") else "")
            + ". Formulas are checked with the KaTeX version the site loads. The PDF stays the reference (`data/paper_acceptance.json`).")
    rows += [
        "",
        f"Counted from [openai/math at `{s['upstream']['commit'][:12]}`](https://github.com/openai/math/tree/{s['upstream']['commit']}) by "
        "`scripts/build_data.py`. The unit, universe and rule behind each number are in `data/summary.json` under `metric_receipts`.",
    ]
    return "\n".join(rows)


def lean_core(text: str) -> str:
    keep = []
    for line in text.split("\n"):
        st = line.strip()
        if not st or st.startswith(("import ", "namespace ", "end", "open ", "section", "noncomputable section")):
            continue
        keep.append(line)
    return "\n".join(keep)


def reported_reruns(sid: str) -> str:
    """Who reports re-running Comparator on this challenge and accepting the proof, from the
    backend export (backend/), credited by the name each source gives."""
    sys.path.insert(0, str(ROOT / "scripts"))
    import backend
    b = backend.load()
    lean = b.lean_statement(sid) if b else None
    names = []
    for s in (lean or {}).get("reported_accepted_replay_sources") or []:
        p = ROOT / "curated" / "sources" / f"{s}.json"
        names.append(json.loads(p.read_text(encoding="utf-8"))["source"]["credit"].split(",")[0] if p.exists() else s)
    if not names:
        return "No outside re-run is recorded yet."
    who = names[0] if len(names) == 1 else ", ".join(names[:-1]) + " and " + names[-1]
    return f"{who} report re-running Comparator on it and accepting the proof."


def example_block(families, manuscripts, statements) -> str:
    fam = next(f for f in families if f["id"] == "159")
    stmt = next(s for s in statements if s["id"] == "ErdosReciprocal")
    ms = next(m for m in manuscripts if m["id"] == fam["manuscripts"][0])
    cor = next(st for st in ms["statements"] if st.get("label") == "ap:reciprocal")
    main = next(st for st in ms["statements"] if st.get("label") == "ap:main")
    paper_text = re.sub(r"\s+", " ", cor["text"]).strip()
    main_text = re.sub(r"\\begin\{equation\}|\\end\{equation\}", "$$", main["text"])
    main_text = re.sub(r"\\bigl|\\bigr", "", main_text)
    main_text = re.sub(r"[ \t]+", " ", main_text).strip()
    return "\n".join([
        f"**Family 159: {fam['title']}.** The paper, [*{ms['title']}*]({ms['pdf_url']}), states:",
        "",
        f"> **Theorem** (label `{main['label']}`). " + main_text.replace("\n", "\n> "),
        ">",
        f"> **Corollary** (label `{cor['label']}`). {paper_text}",
        "",
        f"The Lean statement [`{stmt['id']}`]({stmt['url']}), the fixed statement Comparator checks OpenAI's proof against when it is run "
        f"({stmt['vocabulary_count']} local vocabulary declarations; allowed axioms {', '.join('`'+a+'`' for a in stmt['comparator']['permitted_axioms'])}; {'no definition holes' if not stmt['comparator'].get('definition_names') else str(len(stmt['comparator']['definition_names'])) + ' definition holes'}):",
        "",
        "```lean",
        lean_core(stmt["lean"]),
        "```",
        "",
        f"This challenge file leaves the proof as `sorry` by design. OpenAI's proof lives in the solution module `{stmt['comparator']['solution_module']}`, "
        "and if Comparator accepts a run, the proof establishes exactly the statement above using only the allowed axioms. "
        + reported_reruns(stmt["id"]),
        "",
        "OpenAI's scope note for this family:",
        "",
        "> " + re.sub(r"\s*\n\s*", " ", fam["lean_doc"]["scope"]).strip(),
    ])


def replace_block(text: str, name: str, body: str) -> str:
    pat = re.compile(rf"(<!-- {name}:start -->\n).*?(<!-- {name}:end -->)", re.S)
    if not pat.search(text):
        raise SystemExit(f"README.md has no {name} block")
    return pat.sub(lambda m: m.group(1) + body + "\n" + m.group(2), text)


def main():
    readme = ROOT / "README.md"
    text = readme.read_text(encoding="utf-8")
    s = load("summary.json")
    new = replace_block(text, "numbers", numbers_block(s))
    new = replace_block(new, "example", example_block(load("families.json"), load("manuscripts.json"), load("statements.json")))
    if "--check" in sys.argv:
        if new != text:
            print("README.md is out of date: run python3 scripts/sync_readme.py", file=sys.stderr)
            sys.exit(1)
        return
    readme.write_text(new, encoding="utf-8")


if __name__ == "__main__":
    main()
