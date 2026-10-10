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
        f"- **{n(s['statements_lean'])} Lean statements** set up as Comparator challenges, {n(s['statements_lean_main_results'])} of them in OpenAI's list of main results. "
        f"{n(s['manuscripts_with_lean'])} manuscripts are accompanying papers of a family with at least one Lean statement.",
        f"- **{n(s['lean_statements_pure_mathlib'])} Lean statements** are written in Mathlib's vocabulary alone. The median statement file introduces "
        f"{s['lean_vocabulary_median']} definitions of its own, and the largest ({s['lean_vocabulary_max_statement']}) introduces {n(s['lean_vocabulary_max'])}. "
        f"Comparator certifies a proof against exactly this file, so each definition is something a reader checks.",
        f"- **{n(s['manuscripts_citing_collection'])} manuscripts** cite other manuscripts in the collection ({n(s['internal_citation_edges'])} citation links). "
        f"{n(s['manuscripts_citing_unformalised_collection_results'])} of them cite at least one manuscript with no accompanying Lean statement.",
        f"- **{n(s['external_citations'])} citations** of earlier work outside the collection, to {n(s['external_works_cited'])} distinct works "
        f"(matched by DOI, then arXiv identifier, then title).",
        f"- The TeX sources of the current manuscripts contain {n(env.get('theorem', 0))} theorems, {n(env.get('proposition', 0))} propositions, "
        f"{n(env.get('corollary', 0))} corollaries and {n(env.get('lemma', 0))} lemmas.",
    ]
    sc = s.get("scope_coverage")
    if sc:
        k = sc["classes"]
        rows.append(
            f"- **What the Lean certifies.** Of {n(sc['statements_classified'])} Lean statements, {n(k.get('headline', 0))} certify a paper's headline theorem as stated, "
            f"{n(k.get('headline-part', 0))} part of one, {n(k.get('consequence', 0))} a consequence, {n(k.get('weaker', 0))} a weaker form and {n(k.get('supporting', 0))} a supporting result. "
            f"In {n(len(sc['families_with_lean_but_no_headline_coverage']))} families with Lean statements, none certifies the headline result. "
            "Classified by an AI agent from OpenAI's own Lean notes, quoting each note (`curated/scope_coverage.json`); no person has reviewed it yet."
        )
    rows += [
        "",
        f"Counted from [openai/math at `{s['upstream']['commit'][:12]}`](https://github.com/openai/math/tree/{s['upstream']['commit']}) by "
        "`scripts/build_data.py`. Exact definitions are in `data/summary.json`.",
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
        f"({stmt['vocabulary_count']} definitions of its own; permitted axioms {', '.join('`'+a+'`' for a in stmt['comparator']['permitted_axioms'])}):",
        "",
        "```lean",
        lean_core(stmt["lean"]),
        "```",
        "",
        f"A Comparator challenge file leaves the proof as `sorry` by design. OpenAI's proof lives in the solution module `{stmt['comparator']['solution_module']}`, "
        "and Comparator accepts it only if it proves exactly the statement above using the permitted axioms.",
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
