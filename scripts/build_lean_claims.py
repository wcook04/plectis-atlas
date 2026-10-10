#!/usr/bin/env python3
"""Index the claim layer inside OpenAI's Lean library.

Many projects in openai/math state their papers' claims as Lean propositions in a
`Model.lean` file (for example `def QuantitativeDensityBound (k : ℕ) : Prop := ...`)
and some name the theorems that prove them `manuscript...`. Comparator checks only
the 416 challenge statements. This script lists the rest of that layer so readers
can see, family by family, which of a paper's formal claims Comparator checks and
which are stated or proved only inside the library.

Usage:
    python3 scripts/build_lean_claims.py --upstream ../openai-math-upstream [--out data]

Needs the upstream checkout's `lean/OAI/` tree (scripts/fetch_upstream.sh --lean-library
fetches it; it is large). Writes data/lean_claims.json and merges a `lean_claim_layer`
block into data/summary.json. Standard library only. The scan reads declarations
textually; it does not build Lean, so "proved in the library" means a theorem with
this name exists in the source, not that it has been checked.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from collections import defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DECL = re.compile(
    r"^(?:@\[[^\]]*\]\s*)*(?:(?:noncomputable|private|protected|partial|unsafe|scoped|local)\s+)*"
    r"(theorem|lemma|def|abbrev)\s+([^\s:({\[]+)")


def read(p: Path) -> str:
    return p.read_text(encoding="utf-8", errors="replace")


def scan_file(path: Path, rel: str, want_props: bool):
    """Yield declarations with full names, kinds, lines, docstrings and a statement head."""
    lines = read(path).split("\n")
    ns: list[str] = []
    out = []
    doc = None
    i = 0
    while i < len(lines):
        st = lines[i].strip()
        if st.startswith("/--"):
            buf = [lines[i]]
            while "-/" not in lines[i] and i + 1 < len(lines):
                i += 1
                buf.append(lines[i])
            text = "\n".join(buf).strip()
            text = re.sub(r"^/--\s*", "", text)
            doc = re.sub(r"\s+", " ", re.sub(r"\s*-/\s*$", "", text)).strip()
            i += 1
            continue
        if st.startswith("/-"):
            while "-/" not in lines[i] and i + 1 < len(lines):
                i += 1
            i += 1
            continue
        m = re.match(r"^namespace\s+(\S+)", st)
        if m:
            ns.extend(m.group(1).split("."))
            i += 1
            continue
        m = re.match(r"^end\s+(\S+)", st)
        if m:
            parts = m.group(1).split(".")
            if ns[-len(parts):] == parts:
                del ns[-len(parts):]
            i += 1
            continue
        m = DECL.match(st)
        if m:
            kind, name = m.group(1), m.group(2)
            full = name if name.startswith("_root_.") else ".".join(ns + [name])
            head_lines = [lines[i].rstrip()]
            j = i + 1
            while j < len(lines) and j < i + 40 and ":=" not in "\n".join(head_lines) and not lines[j].strip().startswith(("theorem ", "lemma ", "def ")):
                head_lines.append(lines[j].rstrip())
                j += 1
            head = "\n".join(head_lines)
            head = head.split(":=")[0].rstrip()
            is_prop = kind in ("def", "abbrev") and re.search(r":\s*Prop\s*$", head.split("\n")[-1] + "") is not None
            if not is_prop and kind in ("def", "abbrev"):
                is_prop = bool(re.search(r"\)\s*:\s*Prop\b|^\s*(?:noncomputable\s+)?(?:def|abbrev)\s+\S+\s*:\s*Prop\b", head, flags=re.M))
            manuscript = "manuscript" in name.lower()
            if (want_props and is_prop) or (manuscript and kind in ("theorem", "lemma")):
                rec = {"name": full, "kind": "statement" if is_prop else kind, "file": rel, "line": i + 1,
                       "doc": doc, "head": head[:1200]}
                if is_prop:
                    # A proposition's body is the claim itself: keep the full definition (indented continuation lines).
                    body = [lines[i].rstrip()]
                    j = i + 1
                    while j < len(lines) and j < i + 60:
                        ln = lines[j]
                        if not ln.strip():
                            nxt = next((x for x in lines[j + 1:j + 4] if x.strip()), "")
                            if nxt.startswith((" ", "\t")):
                                body.append("")
                                j += 1
                                continue
                            break
                        if ln.startswith((" ", "\t")):
                            body.append(ln.rstrip())
                            j += 1
                            continue
                        break
                    rec["text"] = "\n".join(body)[:4000]
                out.append(rec)
        doc = None if st and not st.startswith("--") else doc
        i += 1
    return out


def project_of(rel: str) -> str:
    parts = rel.split("/")
    return "/".join(parts[:3]) if len(parts) >= 4 else "/".join(parts[:-1])


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", default=str(ROOT.parent / "openai-math-upstream"))
    ap.add_argument("--out", default=str(ROOT / "data"))
    a = ap.parse_args()
    up = Path(a.upstream).expanduser().resolve()
    oai = up / "lean" / "OAI"
    if not oai.is_dir():
        sys.exit(f"{oai} not found: fetch the Lean library with scripts/fetch_upstream.sh --lean-library")
    out = Path(a.out)
    statements = json.loads((out / "statements.json").read_text(encoding="utf-8"))

    # Comparator coverage: theorem names each challenge certifies, and its solution module's project.
    certified = {}
    project_families = defaultdict(set)
    for s in statements:
        for t in s["comparator"]["theorem_names"]:
            certified[t] = s["id"]
        mod = s["comparator"].get("solution_module") or ""
        if mod.startswith("OAI."):
            proj = "lean/" + "/".join(mod.split(".")[:3])
            for f in s.get("families", []):
                project_families[proj].add(f)

    claims = []
    model_files = 0
    projects = set()
    for path in sorted(oai.rglob("*.lean")):
        rel = str(path.relative_to(up))
        parts_rel = path.relative_to(up / "lean").parts
        if len(parts_rel) >= 4:  # OAI/<Area>/<Project>/...: a project folder, not a loose file in an area
            projects.add("/".join(parts_rel[:3]))
        is_model = path.name == "Model.lean"
        model_files += is_model
        text_has = is_model or "manuscript" in path.read_bytes().decode("utf-8", "replace")
        if not text_has:
            continue
        for d in scan_file(path, rel, want_props=is_model):
            proj = "lean/" + "/".join(rel.split("/")[1:4])
            d["project"] = proj
            d["families"] = sorted(project_families.get(proj, []))
            d["comparator_statement"] = certified.get(d["name"])
            claims.append(d)

    props = [c for c in claims if c["kind"] == "statement"]
    ms = [c for c in claims if c["kind"] in ("theorem", "lemma")]
    import subprocess
    commit = subprocess.run(["git", "-C", str(up), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    summary_block = {
        "upstream_commit": commit,
        "lean_projects": len(projects),
        "lean_files": sum(1 for _ in oai.rglob("*.lean")),
        "projects_with_model_file": model_files,
        "model_statement_definitions": len(props),
        "manuscript_theorems": len(ms),
        "projects_with_manuscript_theorems": len({c["project"] for c in ms}),
        "manuscript_theorems_checked_by_comparator": sum(1 for c in ms if c["comparator_statement"]),
        "model_statement_projects_linked_to_a_family": len({c["project"] for c in props if c["families"]}),
        "definitions": {
            "model_statement_definitions": "Proposition-valued definitions (def or abbrev ending in `: Prop`) in a project's Model.lean, where projects state their papers' claims as Lean propositions.",
            "manuscript_theorems": "Theorems or lemmas whose name contains 'manuscript', the naming some projects use for proofs of their papers' claims.",
            "manuscript_theorems_checked_by_comparator": "Manuscript theorems whose full name is one of the theorem names in a Comparator challenge configuration.",
            "lean_projects": "Folders OAI/<area>/<project>/ in OpenAI's Lean library that contain Lean files.",
            "scan": "Textual scan of lean/OAI at the pinned commit; nothing is built, so a listed theorem exists in the source but is not thereby checked.",
        },
    }
    (out / "lean_claims.json").write_text(json.dumps(claims, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    sp = out / "summary.json"
    summary = json.loads(sp.read_text(encoding="utf-8"))
    summary["lean_claim_layer"] = summary_block
    sp.write_text(json.dumps(summary, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    print(json.dumps({k: v for k, v in summary_block.items() if k != "definitions"}, indent=1))


if __name__ == "__main__":
    main()
