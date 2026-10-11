#!/usr/bin/env python3
"""Build the atlas dataset from a pinned checkout of github.com/openai/math.

Usage:
    python3 scripts/build_data.py --upstream ../openai-math-upstream [--out data]

Reads only files in the upstream checkout (overview.tex, CONTENTS.md,
history.md, preprints/*, lean/*) and writes deterministic JSON to data/.
Every number shown on the site is computed here or in build_site.py.
Standard library only.
"""
from __future__ import annotations

import argparse
import bisect
import hashlib
import json
import os
import re
import subprocess
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

# ---------------------------------------------------------------- utilities


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="replace")


def sha256(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def norm_ws(text: str) -> str:
    return re.sub(r"\s+", " ", text).strip()


def brace_group(s: str, i: int, open_ch: str = "{", close_ch: str = "}"):
    """s[i] must be open_ch. Return (content, index after closing char)."""
    if i >= len(s) or s[i] != open_ch:
        return None, i
    depth = 0
    j = i
    while j < len(s):
        c = s[j]
        if c == "\\":
            j += 2
            continue
        if c == open_ch:
            depth += 1
        elif c == close_ch:
            depth -= 1
            if depth == 0:
                return s[i + 1 : j], j + 1
        j += 1
    return s[i + 1 :], len(s)


def skip_ws(s: str, i: int) -> int:
    while i < len(s) and s[i] in " \t\r\n":
        i += 1
    return i


SLUG_RE = re.compile(r"preprints/([^/\s{}\[\]]+?)/")


def slugs_in(text: str) -> list[str]:
    out = []
    for m in SLUG_RE.finditer(text):
        if m.group(1) not in out:
            out.append(m.group(1))
    return out


def git_commit(path: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(path), "rev-parse", "HEAD"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


def git_commit_date(path: Path) -> str:
    try:
        return subprocess.run(
            ["git", "-C", str(path), "log", "-1", "--format=%cI"],
            capture_output=True, text=True, check=True,
        ).stdout.strip()
    except Exception:
        return "unknown"


# ------------------------------------------------------- catalogue sources


def parse_overview(path: Path):
    """overview.tex: \\cataloguesection{Discipline} then \\resultentry{id}{title}{desc}{links}."""
    s = read(path)
    disciplines: list[dict] = []
    families: dict[str, dict] = {}
    token = re.compile(r"\\(cataloguesection|resultentry)\s*\{")
    pos = 0
    current = None
    while True:
        m = token.search(s, pos)
        if not m:
            break
        i = m.end() - 1
        if m.group(1) == "cataloguesection":
            name, pos = brace_group(s, i)
            current = norm_ws(name)
            disciplines.append({"name": current, "families": []})
            continue
        args = []
        j = i
        for _ in range(4):
            j = skip_ws(s, j)
            arg, j = brace_group(s, j)
            args.append(arg or "")
        pos = j
        fid, title, desc, links = args
        fid = fid.strip()
        families[fid] = {
            "id": fid,
            "discipline": current,
            "title_tex": norm_ws(title),
            "description_tex": norm_ws(desc),
            "manuscripts": slugs_in(links),
        }
        if disciplines:
            disciplines[-1]["families"].append(fid)
    return disciplines, families


def md_math_to_tex(md: str) -> str:
    """CONTENTS.md writes inline maths as $`...`$; normalise to \\( ... \\)."""
    md = re.sub(r"\$`(.+?)`\$", lambda m: "\\(" + m.group(1) + "\\)", md)
    return md


def parse_contents(path: Path):
    """CONTENTS.md: family blocks then manuscript blocks with abstracts."""
    s = read(path)
    cells = re.findall(r"<td>\s*(.*?)\s*</td>", s, flags=re.S)
    families: dict[str, dict] = {}
    current = None
    fam_re = re.compile(r"^\*\*(\d{3})\.\s+(.+?)\*\*\s*(.*)$", re.S)
    ms_re = re.compile(r"^&emsp;\[(.+?)\]\((preprints/.+?\.pdf)\)\s*(.*)$", re.S)
    for cell in cells:
        cell = cell.strip()
        m = fam_re.match(cell)
        if m:
            fid = m.group(1)
            title = m.group(2).strip().rstrip(".")
            current = families.setdefault(
                fid,
                {
                    "id": fid,
                    "title": md_math_to_tex(title),
                    "description": md_math_to_tex(norm_ws(m.group(3))),
                    "manuscripts": [],
                },
            )
            continue
        m = ms_re.match(cell)
        if m and current is not None:
            link = m.group(2)
            slug = slugs_in(link + "/")[0] if slugs_in(link + "/") else None
            pdf = link.split("/", 2)[2] if link.count("/") >= 2 else None
            current["manuscripts"].append(
                {
                    "slug": slug,
                    "title": md_math_to_tex(m.group(1).strip()),
                    "pdf": pdf,
                    "abstract": md_math_to_tex(norm_ws(m.group(3))),
                }
            )
    return families


def parse_readme(path: Path):
    s = read(path)
    info = {"withdrawn": False, "previous_versions": [], "version_note": None}
    m = re.search(r"^#\s*\[(.+?)\]\(([^)]+)\)", s, flags=re.M)
    if m:
        title = m.group(1).strip()
        if title.lower().startswith("withdrawal notice:"):
            info["withdrawn"] = True
            title = title.split(":", 1)[1].strip()
        info["title"] = title
        info["pdf"] = m.group(2).strip()
    m = re.search(r"\*\*Date:\*\*\s*(.+)", s)
    if m:
        info["date"] = m.group(1).strip()
    m = re.search(r"\*\*Withdrawn on (.+?)\.?\*\*", s)
    if m:
        info["withdrawn"] = True
        info["withdrawn_on"] = m.group(1).strip()
        body = s[m.end():]
        cut = body.find("## Archived manuscript")
        info["withdrawal_note"] = md_math_to_tex(body[:cut].strip() if cut >= 0 else body.strip())
    m = re.search(r"\[Pre-withdrawal PDF\]\(([^)]+)\)", s)
    if m:
        info["archived_pdf"] = m.group(1)
    m = re.search(r"## Version note\s*(.+?)(?:\n## |\Z)", s, flags=re.S)
    if m:
        note = m.group(1).strip()
        info["version_note"] = md_math_to_tex(note)
        info["previous_versions"] = [
            x for x in re.findall(r"\]\(\.\./([^/]+?)/", note)
        ]
    return info


def parse_history(path: Path):
    s = read(path)
    sections = []
    for m in re.finditer(r"^## (.+?)\n(.*?)(?=^## |\Z)", s, flags=re.M | re.S):
        sections.append({"date": m.group(1).strip(), "markdown": m.group(2).strip()})
    return sections


# ------------------------------------------------------------------- TeX

INPUT_RE = re.compile(
    r"\\(?:input|include|subfile|subfileinclude)\s*\{([^}]+)\}|\\input\s+([^\s{}\\]+)|\\(?:sub)?import\s*\{([^}]*)\}\s*\{([^}]+)\}"
)


def strip_comment(line: str) -> str:
    i = 0
    while True:
        j = line.find("%", i)
        if j < 0:
            return line
        k = j - 1
        bs = 0
        while k >= 0 and line[k] == "\\":
            bs += 1
            k -= 1
        if bs % 2 == 0:
            return line[:j]
        i = j + 1


def resolve_tex(name: str, base: Path, root: Path) -> Path | None:
    name = name.strip()
    cands = []
    for b in (base, root):
        p = (b / name)
        cands += [p, p.with_name(p.name + ".tex")]
    for c in cands:
        try:
            if c.is_file():
                return c
        except OSError:
            continue
    return None


def expand_tex(path: Path, root: Path, seen=None, depth=0):
    """Return list of (text, file_rel, lineno) with \\input expanded and comments stripped."""
    seen = seen or set()
    out = []
    if depth > 12 or path in seen:
        return out
    seen = seen | {path}
    try:
        lines = read(path).split("\n")
    except OSError:
        return out
    rel = str(path.relative_to(root)) if str(path).startswith(str(root)) else path.name
    for n, raw in enumerate(lines, 1):
        line = strip_comment(raw)
        if "\\" in line and ("input" in line or "include" in line or "import" in line or "subfile" in line):
            pos = 0
            for m in INPUT_RE.finditer(line):
                pre = line[pos:m.start()]
                if pre.strip():
                    out.append((pre, rel, n))
                if m.group(3) is not None:
                    target = resolve_tex(m.group(4), path.parent / m.group(3), root)
                else:
                    target = resolve_tex(m.group(1) or m.group(2), path.parent, root)
                if target is not None:
                    out.extend(expand_tex(target, root, seen, depth + 1))
                pos = m.end()
            rest = line[pos:]
            if rest.strip() or pos == 0:
                out.append((rest, rel, n))
            continue
        out.append((line, rel, n))
    return out


def find_main_tex(mdir: Path) -> Path | None:
    cands = []
    for p in mdir.rglob("*.tex"):
        try:
            t = read(p)
        except OSError:
            continue
        if "\\begin{document}" in t:
            score = 0
            if p.name in ("main.tex", "paper.tex"):
                score += 4
            if "build" in p.parts:
                score += 2
            if "supplement" in p.name.lower() or "appendix" in p.name.lower():
                score -= 3
            score -= len(p.relative_to(mdir).parts) * 0.1
            cands.append((score, len(t), p))
    if not cands:
        return None
    cands.sort(key=lambda x: (x[0], x[1]), reverse=True)
    return cands[0][2]


DEFAULT_ENVS = {
    "theorem": "Theorem", "thm": "Theorem", "maintheorem": "Main Theorem", "mainthm": "Main Theorem",
    "lemma": "Lemma", "lem": "Lemma", "proposition": "Proposition", "prop": "Proposition",
    "corollary": "Corollary", "cor": "Corollary", "conjecture": "Conjecture", "conj": "Conjecture",
    "definition": "Definition", "defn": "Definition", "claim": "Claim", "remark": "Remark",
    "question": "Question", "problem": "Problem", "hypothesis": "Hypothesis", "assumption": "Assumption",
}


def classify(display: str) -> str:
    d = display.lower()
    for key, kind in (
        ("lemma", "lemma"), ("corollar", "corollary"), ("proposition", "proposition"),
        ("conjecture", "conjecture"), ("theorem", "theorem"), ("claim", "claim"),
        ("definition", "definition"), ("question", "question"), ("problem", "question"),
        ("hypothes", "hypothesis"), ("assumption", "hypothesis"), ("fact", "fact"),
        ("remark", "remark"), ("example", "remark"), ("note", "remark"),
    ):
        if key in d:
            return kind
    return "other"


def theorem_envs(text: str) -> dict[str, str]:
    envs = dict(DEFAULT_ENVS)
    for m in re.finditer(r"\\(?:sp)?newtheorem\*?\s*\{([^}]+)\}\s*(?:\[[^\]]*\])?\s*\{([^}]*)\}", text):
        envs[m.group(1).strip()] = m.group(2).strip() or m.group(1)
    for m in re.finditer(r"\\declaretheorem\s*(\[[^\]]*\])?\s*\{([^}]+)\}\s*(\[[^\]]*\])?", text):
        opts = (m.group(1) or "") + (m.group(3) or "")
        nm = re.search(r"name\s*=\s*\{?([^,}\]]+)", opts)
        env = m.group(2).strip()
        envs[env] = nm.group(1).strip() if nm else env.capitalize()
    return envs


def tex_macros(text: str) -> dict[str, str]:
    macros: dict[str, str] = {}
    for m in re.finditer(r"\\(?:re|provide)?newcommand\*?\s*\{?\\([A-Za-z]+)\}?\s*(\[\d\])?\s*(\[[^\]]*\])?\s*\{", text):
        if m.group(3):
            continue  # optional-argument macros are not portable to KaTeX
        body, _ = brace_group(text, m.end() - 1)
        if body is None or len(body) > 400:
            continue
        macros["\\" + m.group(1)] = body.replace("\\ensuremath", "").replace("\\xspace", "")
    for m in re.finditer(r"\\DeclareMathOperator(\*?)\s*\{?\\([A-Za-z]+)\}?\s*\{", text):
        body, _ = brace_group(text, m.end() - 1)
        if body is None:
            continue
        op = "\\operatorname*" if m.group(1) else "\\operatorname"
        macros["\\" + m.group(2)] = op + "{" + body + "}"
    for m in re.finditer(r"\\DeclarePairedDelimiter(?:X|XPP)?\s*\{?\\([A-Za-z]+)\}?\s*(?:\[\d\])?\s*\{([^{}]*)\}\s*\{([^{}]*)\}", text):
        macros.setdefault("\\" + m.group(1), "\\left" + m.group(2).strip() + " #1 \\right" + m.group(3).strip())
    for m in re.finditer(r"\\def\s*\\([A-Za-z]+)\s*\{", text):
        body, _ = brace_group(text, m.end() - 1)
        if body is None or len(body) > 400 or "#" in body:
            continue
        macros.setdefault("\\" + m.group(1), body)
    return macros


CITE_RE = re.compile(r"\\[A-Za-z]*cite[A-Za-z]*\*?\s*(?:\[[^\]]*\]\s*){0,2}\{([^}]*)\}")


class TexDoc:
    def __init__(self, lines):
        self.lines = lines
        self.text = "\n".join(t for t, _, _ in lines)
        self.starts = []
        pos = 0
        for t, _, _ in lines:
            self.starts.append(pos)
            pos += len(t) + 1

    def loc(self, offset: int):
        k = bisect.bisect_right(self.starts, offset) - 1
        k = max(0, min(k, len(self.lines) - 1))
        _, f, n = self.lines[k]
        return f, n


def env_blocks(text: str, names: list[str]):
    """Yield (env, start, body_start, body_end, end) for \\begin{env}...\\end{env}, nesting-aware."""
    if not names:
        return
    alt = "|".join(re.escape(n) for n in sorted(names, key=len, reverse=True))
    begin_re = re.compile(r"\\begin\{(" + alt + r")\}")
    for m in begin_re.finditer(text):
        env = m.group(1)
        b = re.escape("\\begin{" + env + "}")
        e = re.escape("\\end{" + env + "}")
        tok = re.compile(b + "|" + e)
        depth = 1
        for t in tok.finditer(text, m.end()):
            depth += 1 if t.group(0).startswith("\\begin") else -1
            if depth == 0:
                yield env, m.start(), m.end(), t.start(), t.end()
                break


def parse_tex_manuscript(mdir: Path):
    main = find_main_tex(mdir)
    if main is None:
        return None
    doc = TexDoc(expand_tex(main, mdir))
    text = doc.text
    envs = theorem_envs(text)
    begin_doc = text.find("\\begin{document}")
    body_from = begin_doc if begin_doc >= 0 else 0

    sections = []
    for m in re.finditer(r"\\section\*?\s*(\[[^\]]*\])?\s*\{", text):
        if m.start() < body_from:
            continue
        title, _ = brace_group(text, m.end() - 1)
        sections.append((m.start(), norm_ws(title or "")))
    appendix_at = text.find("\\appendix", body_from)
    sec_starts = [p for p, _ in sections]

    def section_of(off: int):
        k = bisect.bisect_right(sec_starts, off) - 1
        return k  # -1 means before the first section

    abstract = None
    m = re.search(r"\\begin\{abstract\}(.*?)\\end\{abstract\}", text, flags=re.S)
    if m:
        abstract = m.group(1).strip()

    statements = []
    proof_ranges = []
    names = [n for n in envs if classify(envs[n]) not in ("other",)]
    for env, s0, b0, b1, e1 in env_blocks(text, names + ["proof"]):
        if s0 < body_from:
            continue
        if env == "proof":
            proof_ranges.append((s0, e1))
            continue
        display = envs.get(env, env)
        kind = classify(display)
        body = text[b0:b1]
        title = None
        j = skip_ws(body, 0)
        if j < len(body) and body[j] == "[":
            title, k = brace_group(body, j, "[", "]")
            body = body[k:]
        label = None
        lm = re.search(r"\\label\{([^}]+)\}", body)
        if lm:
            label = lm.group(1).strip()
        body_clean = re.sub(r"\\label\{[^}]*\}", "", body).strip()
        f, n = doc.loc(s0)
        sec = section_of(s0)
        statements.append(
            {
                "kind": kind,
                "env": env,
                "display": display,
                "title": norm_ws(title) if title else None,
                "label": label,
                "text": body_clean,
                "sha256": sha256(norm_ws(body_clean)),
                "file": f,
                "line": n,
                "section": sec + 1,
                "section_title": sections[sec][1] if sec >= 0 else None,
                "appendix": appendix_at >= 0 and s0 > appendix_at,
                "_offset": s0,
                "_end": e1,
            }
        )
    statements.sort(key=lambda x: x["_offset"])
    # Headline candidates: theorem-like statements before the second section,
    # or explicitly named main results; fall back to the first three theorems.
    headline_kinds = {"theorem", "corollary", "conjecture", "proposition"}
    second = sec_starts[1] if len(sec_starts) > 1 else None
    for st in statements:
        early = second is None or st["_offset"] < second
        named_main = "main" in (st["display"] or "").lower()
        st["headline"] = st["kind"] in headline_kinds and not st["appendix"] and (early or named_main)
    if not any(st["headline"] for st in statements):
        for st in [x for x in statements if x["kind"] == "theorem" and not x["appendix"]][:3]:
            st["headline"] = True

    # Citations and their point of use.
    bib_start = text.find("\\begin{thebibliography}")
    cites = []
    for m in CITE_RE.finditer(text):
        if m.start() < body_from or (bib_start >= 0 and m.start() > bib_start):
            continue
        keys = [k.strip() for k in m.group(1).split(",") if k.strip()]
        ctx = None
        for st in statements:
            if st["_offset"] <= m.start() < st["_end"]:
                ctx = {"kind": st["kind"], "display": st["display"], "label": st["label"], "title": st["title"]}
        if ctx is None:
            for p0, p1 in proof_ranges:
                if p0 <= m.start() < p1:
                    prev = [st for st in statements if st["_end"] <= p0]
                    ctx = {"kind": "proof", "of": prev[-1]["label"] if prev else None}
                    break
        sec = section_of(m.start())
        f, n = doc.loc(m.start())
        for k in keys:
            cites.append({"key": k, "file": f, "line": n, "context": ctx,
                          "section": sections[sec][1] if sec >= 0 else None})

    thebib = []
    if bib_start >= 0:
        end = text.find("\\end{thebibliography}", bib_start)
        block = text[bib_start: end if end > 0 else len(text)]
        for m in re.finditer(r"\\bibitem\s*(?:\[[^\]]*\])?\s*\{([^}]+)\}(.*?)(?=\\bibitem|\Z)", block, flags=re.S):
            thebib.append({"key": m.group(1).strip(), "raw": norm_ws(m.group(2))})

    for st in statements:
        st.pop("_offset", None)
        st.pop("_end", None)
    return {
        "main_tex": str(main.relative_to(mdir)),
        "abstract_tex": abstract,
        "sections": [t for _, t in sections],
        "statements": statements,
        "cites": cites,
        "thebibliography": thebib,
        "macros": tex_macros(text[:body_from] if body_from else text),
        "counts": Counter(st["kind"] for st in statements),
    }


# ------------------------------------------------------------- BibTeX


def parse_bib(text: str):
    entries = {}
    i = 0
    while True:
        at = text.find("@", i)
        if at < 0:
            break
        m = re.match(r"@([A-Za-z]+)\s*([{(])", text[at:])
        if not m:
            i = at + 1
            continue
        etype = m.group(1).lower()
        open_ch = m.group(2)
        close_ch = "}" if open_ch == "{" else ")"
        body, j = brace_group(text, at + m.end() - 1, open_ch, close_ch)
        i = j
        if body is None or etype in ("comment", "string", "preamble"):
            continue
        comma = body.find(",")
        if comma < 0:
            continue
        key = body[:comma].strip()
        fields = {}
        rest = body[comma + 1:]
        k = 0
        while k < len(rest):
            fm = re.match(r"\s*([A-Za-z_\-]+)\s*=\s*", rest[k:])
            if not fm:
                break
            name = fm.group(1).lower()
            k += fm.end()
            parts = []
            while k < len(rest):
                k = skip_ws(rest, k)
                if k >= len(rest):
                    break
                if rest[k] == "{":
                    val, k = brace_group(rest, k)
                    parts.append(val or "")
                elif rest[k] == '"':
                    e = k + 1
                    depth = 0
                    while e < len(rest):
                        if rest[e] == "{":
                            depth += 1
                        elif rest[e] == "}":
                            depth -= 1
                        elif rest[e] == '"' and depth == 0:
                            break
                        e += 1
                    parts.append(rest[k + 1:e])
                    k = e + 1
                else:
                    vm = re.match(r"[^,#\s}]+", rest[k:])
                    if vm:
                        parts.append(vm.group(0))
                        k += vm.end()
                k = skip_ws(rest, k)
                if k < len(rest) and rest[k] == "#":
                    k += 1
                    continue
                break
            fields[name] = norm_ws("".join(parts))
            k = skip_ws(rest, k)
            if k < len(rest) and rest[k] == ",":
                k += 1
        entries[key] = {"type": etype, "fields": fields, "raw": body}
    return entries


def detex(s: str) -> str:
    # Symbol accents (\'e, \"o, \^o ...) may touch their letter; letter accents (\u, \v, \H, \t, \c, \d, \b, \k)
    # count only when not followed by more letters, so \textbf, \url and \doi survive to the rules below.
    s = re.sub(r"\\[`'^\"~=.]\s*\{?([A-Za-z])\}?", r"\1", s)
    s = re.sub(r"\\[uvHtcdbk](?![A-Za-z])\s*\{?([A-Za-z])\}?", r"\1", s)
    s = re.sub(r"\\href\s*\{[^{}]*\}\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\(?:emph|textit|textbf|textsc|textrm|textsf|texttt|mathrm|mathbf|mathit|text|url|nolinkurl|doi|path)\s*\{([^{}]*)\}", r"\1", s)
    s = re.sub(r"\\[A-Za-z]+\*?", " ", s)
    s = s.replace("{", "").replace("}", "").replace("~", " ").replace("--", "-")
    return norm_ws(s)


ARXIV_RE = re.compile(r"(?:arXiv[:\s]*|arxiv\.org/abs/)(\d{4}\.\d{4,5})", re.I)
DOI_RE = re.compile(r"(10\.\d{4,9}/[^\s,}{\"]+)")
YEAR_RE = re.compile(r"\b(1[6-9]\d\d|20[0-3]\d)\b")


def free_text_year(raw: str):
    """Pick a publication year from a free-text reference, ignoring page ranges."""
    par = re.findall(r"\((1[6-9]\d\d|20[0-3]\d)[a-z]?\)", raw)
    if par:
        return par[-1]
    cands = []
    for m in YEAR_RE.finditer(raw):
        before = raw[max(0, m.start() - 1):m.start()]
        after = raw[m.end():m.end() + 2]
        if before in ("-", "\u2013") or re.match(r"\s*[-\u2013]+\s*\d", after) or re.match(r"[-\u2013]", after):
            continue
        cands.append(m.group(1))
    return cands[-1] if cands else None


def ref_record(key: str, fields: dict | None, raw: str):
    rec = {"key": key}
    if fields:
        rec["authors"] = detex(fields.get("author", "")) or None
        rec["title"] = detex(fields.get("title", "")) or None
        rec["year"] = (YEAR_RE.search(fields.get("year", "") or fields.get("date", "")) or [None, None])[1] if (fields.get("year") or fields.get("date")) else None
        venue = fields.get("journal") or fields.get("booktitle") or fields.get("publisher") or fields.get("howpublished") or ""
        rec["venue"] = detex(venue) or None
    else:
        rec["text"] = detex(raw)[:400]
        rec["year"] = free_text_year(raw)
    blob = raw if raw else ""
    am = ARXIV_RE.search(blob) or (ARXIV_RE.search(fields.get("eprint", "")) if fields else None)
    if fields and not am and re.fullmatch(r"\d{4}\.\d{4,5}(v\d+)?", fields.get("eprint", "") or ""):
        rec["arxiv"] = fields["eprint"].split("v")[0]
    elif am:
        rec["arxiv"] = am.group(1)
    dm = DOI_RE.search((fields or {}).get("doi", "") or blob)
    if dm:
        rec["doi"] = clean_doi(dm.group(1))
    return rec


def clean_doi(d: str) -> str:
    """Drop sentence punctuation and unbalanced closing brackets from the end of a DOI.
    Balanced brackets inside a DOI are legal and kept."""
    while d:
        if d[-1] in ".,;:":
            d = d[:-1]
        elif d[-1] == ")" and d.count(")") > d.count("("):
            d = d[:-1]
        elif d[-1] == "]" and d.count("]") > d.count("["):
            d = d[:-1]
        else:
            break
    return d


def work_id(rec: dict) -> str:
    if rec.get("doi"):
        return "doi:" + rec["doi"].lower()
    if rec.get("arxiv"):
        return "arxiv:" + rec["arxiv"]
    return "title:" + norm_title(rec.get("title") or rec.get("text") or rec["key"])


def norm_title(t: str) -> str:
    return " ".join(re.sub(r"[^a-z0-9]+", " ", (t or "").lower()).split())


# ------------------------------------------------------------------- Lean

DECL_RE = re.compile(
    r"^(?:@\[[^\]]*\]\s*)*(?:(?:noncomputable|private|protected|partial|unsafe|scoped|local)\s+)*"
    r"(theorem|lemma|def|abbrev|structure|class|inductive|instance|axiom|opaque|example|notation|infix|infixl|infixr|prefix|postfix|macro|syntax|macro_rules)\b\s*([^\s:({\[]*)",
)
VOCAB_KINDS = {"def", "abbrev", "structure", "class", "inductive", "instance", "axiom", "opaque",
               "notation", "infix", "infixl", "infixr", "prefix", "postfix", "macro", "syntax", "macro_rules"}


def lean_mask_comments(text: str):
    """Blank out Lean comments, keeping every line break so line numbers survive. Block comments
    nest; a line comment runs to the end of its line. Docstrings (/-- ... -/) are returned as
    {end_line: text} so the declaration that follows can claim them."""
    out, docs = [], {}
    i, n, depth, line = 0, len(text), 0, 1
    doc_chars = None
    while i < n:
        if depth == 0 and text.startswith("--", i):
            j = text.find("\n", i)
            j = n if j < 0 else j
            out.append(" " * (j - i))
            i = j
            continue
        if text.startswith("/-", i):
            if depth == 0:
                doc_chars = [] if text.startswith("/--", i) and not text.startswith("/--/", i) else None
                step = 3 if doc_chars is not None else 2
            else:
                step = 2
            depth += 1
            out.append(" " * step)
            i += step
            continue
        if depth > 0 and text.startswith("-/", i):
            depth -= 1
            out.append("  ")
            i += 2
            if depth == 0 and doc_chars is not None:
                docs[line] = norm_ws("".join(doc_chars))
                doc_chars = None
            continue
        c = text[i]
        if depth > 0:
            if doc_chars is not None:
                doc_chars.append(c)
            out.append("\n" if c == "\n" else " ")
        else:
            out.append(c)
        if c == "\n":
            line += 1
        i += 1
    return "".join(out), docs


ATTR_ONLY_RE = re.compile(r"^(?:@\[[^\]]*\]\s*)+$")


def parse_challenge(lean_path: Path, json_path: Path):
    text = read(lean_path)
    cfg = json.loads(read(json_path)) if json_path.exists() else {}
    masked, docs = lean_mask_comments(text)
    imports = [mod for line in re.findall(r"^import\s+(.+)$", masked, flags=re.M) for mod in line.split()]
    scopes: list[tuple[str, str | None]] = []  # ("namespace", name) or ("section", name or None)
    decls = []
    doc_buf = None
    content_lines = 0
    lines = masked.split("\n")
    for i, line in enumerate(lines):
        st = line.strip()
        if (i + 1) in docs:
            doc_buf = docs[i + 1]
        if not st:
            continue
        m = re.match(r"^namespace\s+(\S+)", st)
        if m:
            scopes.append(("namespace", m.group(1)))
            continue
        m = re.match(r"^(?:@\[[^\]]*\]\s*)*(?:(?:public|private|noncomputable)\s+)*section(?:\s+(\S+))?\s*$", st)
        if m:
            scopes.append(("section", m.group(1)))
            continue
        if st == "mutual":
            scopes.append(("mutual", None))
            continue
        m = re.match(r"^end(?:\s+(\S+))?\s*$", st)
        if m:
            if scopes and (m.group(1) is None or scopes[-1][1] == m.group(1)):
                scopes.pop()
            continue
        if not (st.startswith("import ") or st.startswith("open ") or st.startswith("set_option") or st.startswith("universe") or st.startswith("variable")):
            content_lines += 1
        if ATTR_ONLY_RE.match(st):
            continue  # an attribute line between a docstring and its declaration keeps the docstring
        m = DECL_RE.match(st)
        if m:
            kind, name = m.group(1), m.group(2)
            ns = [nm for k, nm in scopes if k == "namespace" and nm]
            full = ".".join(ns + [name]) if name and kind not in ("notation", "infix", "infixl", "infixr", "prefix", "postfix", "macro", "syntax", "macro_rules") else name
            decls.append({"kind": kind, "name": full, "line": i + 1, "doc": doc_buf})
        doc_buf = None
    vocab = [d for d in decls if d["kind"] in VOCAB_KINDS]
    non_mathlib = [x for x in imports if not (x == "Mathlib" or x.startswith("Mathlib."))]
    theorems = [d for d in decls if d["kind"] in ("theorem", "lemma")]
    return {
        "id": lean_path.stem,
        "file": "lean/ComparatorChallenges/" + lean_path.name,
        "lean": text,
        "sha256": sha256(text),
        "imports": imports,
        "non_mathlib_imports": non_mathlib,
        "declarations": decls,
        "theorems": [d["name"] for d in theorems],
        "docstrings": [d["doc"] for d in decls if d["doc"]],
        "vocabulary": [{"kind": d["kind"], "name": d["name"], "line": d["line"]} for d in vocab],
        "vocabulary_count": len(vocab),
        "declares_axiom": any(d["kind"] == "axiom" for d in decls),
        "statement_lines": content_lines,
        "comparator": {
            "theorem_names": cfg.get("theorem_names", []),
            "definition_names": cfg.get("definition_names", []),
            "permitted_axioms": cfg.get("permitted_axioms", []),
            "solution_module": cfg.get("solution_module"),
            "enable_nanoda": cfg.get("enable_nanoda"),
        },
    }


def parse_lean_doc(path: Path):
    s = read(path)
    title = None
    m = re.search(r"^#\s+(.+)$", s, flags=re.M)
    if m:
        title = m.group(1).strip()
    scope = None
    m = re.search(r"## Scope\s*(.+?)(?:\n## |\Z)", s, flags=re.S)
    if m:
        scope = md_math_to_tex(m.group(1).strip())
    head = s.split("## Scope")[0]
    papers = slugs_in(head)
    rows = []
    m = re.search(r"## Comparator links\s*(.+?)(?:\n## |\Z)", s, flags=re.S)
    if m:
        for line in m.group(1).split("\n"):
            if not line.startswith("|") or "---" in line:
                continue
            cells = [c.strip() for c in line.strip().strip("|").split("|")]
            ids = re.findall(r"ComparatorChallenges/([A-Za-z0-9_]+)\.lean", line)
            if ids:
                rows.append({"label": md_math_to_tex(cells[0]), "statements": ids})
    return {"title": title, "scope": scope, "papers": papers, "rows": rows}


def yaml_block(text: str, key: str) -> tuple[int, list[str]]:
    """Indent and body lines of the first `key:` block (a line holding only that key)."""
    lines = text.splitlines()
    for i, ln in enumerate(lines):
        m = re.match(rf"^(\s*){re.escape(key)}:\s*(#.*)?$", ln)
        if not m:
            continue
        base, body = len(m.group(1)), []
        for ln2 in lines[i + 1:]:
            if ln2.strip() and not ln2.lstrip().startswith("#") and len(ln2) - len(ln2.lstrip()) <= base:
                break
            body.append(ln2)
        return base, body
    return -1, []


def yaml_flat_items(body: list[str]) -> list[dict]:
    """Items of a block sequence of flat `key: scalar` mappings, in any key order. This is the
    only shape formalization.yaml uses for status.main_results; the caller checks the count."""
    items, cur = [], None
    for ln in body:
        s = ln.strip()
        if not s or s.startswith("#"):
            continue
        if s.startswith("- "):
            cur = {}
            items.append(cur)
            s = s[2:].strip()
        m = re.match(r"([A-Za-z_][\w-]*):\s*(.*)$", s)
        if cur is None or not m:
            continue
        k, v = m.group(1), m.group(2).strip()
        if len(v) >= 2 and v[0] in "\"'" and v[-1] == v[0]:
            v = v[1:-1]
        if k in cur:
            raise ValueError(f"formalization.yaml: duplicate key {k!r} in one main_results item")
        cur[k] = v
    return items


def parse_main_results(path: Path):
    s = read(path)
    out = {}
    items = yaml_flat_items(yaml_block(s, "main_results")[1])
    for it in items:
        m = re.match(r"ComparatorChallenges/([A-Za-z0-9_]+)\.json$", it.get("comparator_config", ""))
        if not (m and it.get("declaration") and it.get("file")):
            raise SystemExit(f"formalization.yaml: a main_results item lacks comparator_config, declaration or file: {it}")
        out.setdefault(m.group(1), []).append({"declaration": it["declaration"], "file": it["file"]})
    named = len(re.findall(r"^\s*(?:-\s*)?comparator_config:", s, flags=re.M))
    if named != len(items):
        raise SystemExit(f"formalization.yaml: read {len(items)} main_results items but the file names {named} comparator configs")
    review = None
    for ln in yaml_block(s, "review")[1]:
        m = re.match(r"^\s+status:\s*(\S+)", ln)
        if m:
            review = m.group(1)
            break
    top = re.findall(r"^([a-z_]+):", s, flags=re.M)
    return out, review, top


# ------------------------------------------------------------------ build


def build(upstream: Path, out: Path, quiet: bool = False):
    log = (lambda *a: None) if quiet else (lambda *a: print(*a, file=sys.stderr))
    commit = git_commit(upstream)
    commit_date = git_commit_date(upstream)
    base_blob = f"https://github.com/openai/math/blob/{commit}/"

    disciplines, ov = parse_overview(upstream / "overview.tex")
    ct = parse_contents(upstream / "CONTENTS.md")
    history = parse_history(upstream / "history.md")
    log(f"overview families={len(ov)} disciplines={len(disciplines)} contents families={len(ct)}")

    # ---- manuscripts
    pre = upstream / "preprints"
    all_slugs = sorted(p.name for p in pre.iterdir() if p.is_dir())
    readmes = {s: parse_readme(pre / s / "README.md") for s in all_slugs if (pre / s / "README.md").exists()}
    current = set()
    fam_of = {}
    for fid, f in ov.items():
        for s in f["manuscripts"]:
            current.add(s)
            fam_of.setdefault(s, fid)
    for fid, f in ct.items():
        for m in f["manuscripts"]:
            if m["slug"]:
                current.add(m["slug"])
                fam_of.setdefault(m["slug"], fid)
    previous_of = {}
    for s, r in readmes.items():
        for pv in r.get("previous_versions", []):
            previous_of[pv] = s
    def latest(slug):
        seen = set()
        while slug in previous_of and slug not in seen:
            seen.add(slug)
            slug = previous_of[slug]
        return slug
    contents_ms = {m["slug"]: m for f in ct.values() for m in f["manuscripts"] if m["slug"]}

    manuscripts = {}
    oai_edges = []
    works: dict[str, dict] = {}
    tex_failures = []
    for n_done, slug in enumerate(all_slugs, 1):
        r = readmes.get(slug, {})
        if r.get("withdrawn"):
            status = "withdrawn"
        elif slug in current:
            status = "current"
        elif slug in previous_of:
            status = "previous-edition"
        else:
            status = "other"
        fam = fam_of.get(slug) or fam_of.get(latest(slug))
        cm = contents_ms.get(slug, {})
        rec = {
            "id": slug,
            "family": fam,
            "status": status,
            "title": cm.get("title") or r.get("title") or slug,
            "date": r.get("date"),
            "abstract": cm.get("abstract"),
            "pdf_url": base_blob + "preprints/" + slug + "/" + (cm.get("pdf") or r.get("pdf") or "paper.pdf").split("/")[-1],
            "readme_url": base_blob + "preprints/" + slug + "/README.md",
            "version_note": r.get("version_note"),
            "previous_versions": r.get("previous_versions", []),
            "superseded_by": previous_of.get(slug),
            "withdrawn_on": r.get("withdrawn_on"),
            "withdrawal_note": r.get("withdrawal_note"),
            "archived_pdf": r.get("archived_pdf"),
        }
        tex = None
        if status in ("current", "withdrawn"):
            try:
                tex = parse_tex_manuscript(pre / slug)
            except RecursionError:
                tex = None
            if tex is None:
                tex_failures.append(slug)
        bib_entries = {}
        for b in sorted((pre / slug).rglob("*.bib")):
            bib_entries.update(parse_bib(read(b)))
        if tex:
            cited_keys = []
            for c in tex["cites"]:
                if c["key"] not in cited_keys:
                    cited_keys.append(c["key"])
            bibitems = {b["key"]: b for b in tex["thebibliography"]}
            refs = []
            internal = []
            uses_by_key = defaultdict(list)
            for c in tex["cites"]:
                if len(uses_by_key[c["key"]]) < 12:
                    uses_by_key[c["key"]].append({k: c[k] for k in ("file", "line", "context", "section")})
            for key in cited_keys:
                if key in bib_entries:
                    e = bib_entries[key]
                    raw = e["raw"]
                    ref = ref_record(key, e["fields"], raw)
                elif key in bibitems:
                    raw = bibitems[key]["raw"]
                    ref = ref_record(key, None, raw)
                else:
                    continue
                ref["uses"] = uses_by_key.get(key, [])
                targets = slugs_in(raw) if ("openai/math" in raw or key.startswith("OAI:")) else []
                if key.startswith("OAI:") and not targets:
                    targets = [key[4:]]
                if targets:
                    for t in targets:
                        t_latest = latest(t)
                        internal.append({"key": key, "target": t, "target_latest": t_latest, "uses": ref["uses"]})
                        oai_edges.append((slug, t, t_latest))
                    continue
                ref["work"] = work_id(ref)
                refs.append(ref)
                w = works.setdefault(ref["work"], {"id": ref["work"], "record": {k: ref.get(k) for k in ("authors", "title", "year", "venue", "doi", "arxiv", "text")}, "cited_by": []})
                if slug not in w["cited_by"]:
                    w["cited_by"].append(slug)
            rec.update(
                {
                    "tex": {
                        "main": tex["main_tex"],
                        "abstract": tex["abstract_tex"],
                        "sections": tex["sections"],
                        "macros": tex["macros"],
                    },
                    "statements": [st for st in tex["statements"] if st["kind"] in ("theorem", "proposition", "corollary", "conjecture", "question", "hypothesis")],
                    "lemma_count": tex["counts"].get("lemma", 0),
                    "counts": dict(tex["counts"]),
                    "references": refs,
                    "internal_references": internal,
                    "citations_total": len(tex["cites"]),
                }
            )
        manuscripts[slug] = rec
        if not quiet and n_done % 100 == 0:
            log(f"  manuscripts parsed: {n_done}/{len(all_slugs)}")

    # ---- Lean
    lean = upstream / "lean"
    main_results, review_status, fy_top = parse_main_results(lean / "formalization.yaml")
    challenges = {}
    for p in sorted((lean / "ComparatorChallenges").glob("*.lean")):
        c = parse_challenge(p, p.with_suffix(".json"))
        c["url"] = base_blob + c["file"]
        c["main_result"] = c["id"] in main_results
        if c["main_result"]:
            c["solution"] = [dict(r, url=base_blob + "lean/" + r["file"]) for r in main_results[c["id"]]]
        challenges[c["id"]] = c
    docs = {}
    for p in sorted((lean / "docs").glob("*.md")):
        d = parse_lean_doc(p)
        d["id"] = p.stem
        d["url"] = base_blob + "lean/docs/" + p.name
        docs[p.stem] = d
    for fid, d in docs.items():
        for row in d["rows"]:
            for sid in row["statements"]:
                if sid in challenges:
                    c = challenges[sid]
                    c.setdefault("families", [])
                    if fid not in c["families"]:
                        c["families"].append(fid)
                    c.setdefault("labels", [])
                    if row["label"] not in c["labels"]:
                        c["labels"].append(row["label"])
                    c.setdefault("papers", [])
                    for s in d["papers"]:
                        if s not in c["papers"]:
                            c["papers"].append(s)
    formal_manuscripts = {s for d in docs.values() if d["rows"] for s in d["papers"]}

    # ---- families
    families = []
    for disc in disciplines:
        for fid in disc["families"]:
            f = ov[fid]
            c = ct.get(fid, {})
            d = docs.get(fid)
            ms = [s for s in (f["manuscripts"] or [m["slug"] for m in c.get("manuscripts", [])]) if s]
            stmts = []
            if d:
                for row in d["rows"]:
                    for sid in row["statements"]:
                        if sid not in stmts:
                            stmts.append(sid)
            families.append(
                {
                    "id": fid,
                    "discipline": disc["name"],
                    "title": c.get("title") or f["title_tex"],
                    "description": c.get("description") or f["description_tex"],
                    "manuscripts": ms,
                    "statements": stmts,
                    "lean_doc": {"title": d["title"], "scope": d["scope"], "rows": d["rows"], "url": d["url"]} if d else None,
                }
            )
    fam_by_id = {f["id"]: f for f in families}

    # ---- internal citation graph and dependency status
    edges = []
    seen_e = set()
    for src, tgt, tgt_latest in oai_edges:
        tgt_m = manuscripts.get(tgt)
        tgt_l = manuscripts.get(tgt_latest)
        key = (src, tgt)
        if key in seen_e:
            continue
        seen_e.add(key)
        edges.append(
            {
                "source": src,
                "target": tgt,
                "target_latest": tgt_latest,
                "source_family": manuscripts.get(src, {}).get("family"),
                "target_family": (tgt_l or tgt_m or {}).get("family"),
                "target_status": (tgt_m or {}).get("status", "unresolved"),
                "target_latest_status": (tgt_l or {}).get("status", "unresolved"),
                "target_has_lean": tgt_latest in formal_manuscripts or tgt in formal_manuscripts,
            }
        )
    rests_on = defaultdict(list)
    for e in edges:
        rests_on[e["source"]].append(e)
    for slug, m in manuscripts.items():
        es = rests_on.get(slug, [])
        m["rests_on"] = [
            {"manuscript": e["target_latest"], "cited_as": e["target"], "status": e["target_latest_status"],
             "cited_edition_status": e["target_status"], "has_lean": e["target_has_lean"], "family": e["target_family"]}
            for e in es
        ]
        m["has_lean"] = slug in formal_manuscripts
    cited_by = defaultdict(list)
    for e in edges:
        if e["source"] in manuscripts and manuscripts[e["source"]]["status"] == "current":
            cited_by[e["target_latest"]].append(e["source"])
    for slug, m in manuscripts.items():
        m["cited_by_in_collection"] = sorted(set(cited_by.get(slug, [])))

    # ---- OpenAI's own reported figures, parsed from its files (quoted, never retyped)
    upstream_reported = {}
    hist_text = read(upstream / "history.md")
    m = re.search(r"top-line results formalized to (\d+)\s*/\s*(\d+)\s*=\s*~?(\d+)%", hist_text)
    if m:
        upstream_reported["top_line_results_formalized"] = {
            "formalized": int(m.group(1)), "of": int(m.group(2)), "percent": int(m.group(3)),
            "source": base_blob + "history.md", "quote": m.group(0)}
    readme_text = read(upstream / "README.md")
    m = re.search(r"(\d+) manuscripts organized into (\d+) families", readme_text)
    if m:
        upstream_reported["catalogue"] = {"manuscripts": int(m.group(1)), "families": int(m.group(2)),
                                          "source": base_blob + "README.md", "quote": m.group(0)}
    m = re.search(r"an? (unreleased internal OpenAI model)", readme_text)
    if m:
        upstream_reported["model"] = {"quote": m.group(1), "source": base_blob + "README.md"}
    m = re.search(r"((?:On average, )?each result used [^.]*?compute[^.]*?)\.", readme_text)
    if m:
        upstream_reported["compute"] = {"quote": m.group(1), "source": base_blob + "README.md"}
    m = re.search(r"(the writeup for [^.]*?human edited for readability)", readme_text, flags=re.I)
    if m:
        upstream_reported["human_edited"] = {"quote": m.group(1), "source": base_blob + "README.md"}
    traces = re.findall(r"^\|\s*(\d{3})\s*\|\s*\[(.+?)\]\((reasoning_traces/[^)]+)\)\s*\|", readme_text, flags=re.M)
    upstream_reported["reasoning_summaries"] = {"count": len(traces), "families": [t[0] for t in traces],
                                                "source": base_blob + "README.md"}
    m = re.search(r"posed approximately ([\d,]+) problems", readme_text)
    if m:
        upstream_reported["problems_posed"] = {"approximately": int(m.group(1).replace(",", "")),
                                               "source": base_blob + "README.md", "quote": m.group(0)}

    for fid, title, path in traces:
        if fid in fam_by_id:
            fam_by_id[fid]["reasoning_summary"] = {"title": title, "url": base_blob + path}

    # Reconcile automatic reference identities: a title-only record whose full normalised title equals
    # the title of exactly one DOI or arXiv record (with the same year when both give one) joins that
    # record. Merged keys stay listed as aliases, so each merge can be audited.
    by_title = defaultdict(list)
    for wid, w in works.items():
        if not wid.startswith("title:") and w["record"].get("title"):
            by_title[norm_title(w["record"]["title"])].append(wid)
    remap = {}
    for wid, w in list(works.items()):
        cands = by_title.get(wid[len("title:"):], []) if wid.startswith("title:") else []
        if len(cands) != 1:
            continue
        target = works[cands[0]]
        y1, y2 = w["record"].get("year"), target["record"].get("year")
        if y1 and y2 and y1 != y2:
            continue
        for c in w["cited_by"]:
            if c not in target["cited_by"]:
                target["cited_by"].append(c)
        target.setdefault("aliases", []).append(wid)
        remap[wid] = cands[0]
        del works[wid]
    for m in manuscripts.values():
        for ref in m.get("references") or []:
            if ref.get("work") in remap:
                ref["work"] = remap[ref["work"]]
    log(f"reference identities reconciled by exact title: {len(remap)}")

    # ---- summary
    cur = [m for m in manuscripts.values() if m["status"] == "current"]
    stmt_counts = Counter()
    for m in cur:
        for k, v in m.get("counts", {}).items():
            stmt_counts[k] += v
    pure = [c for c in challenges.values() if not c["non_mathlib_imports"] and c["vocabulary_count"] == 0]
    no_local = [c for c in challenges.values() if c["vocabulary_count"] == 0]
    vocab = [c for c in challenges.values() if c["vocabulary_count"] > 0]

    def median(xs):
        xs = sorted(xs)
        if not xs:
            return 0
        mid = len(xs) // 2
        v = xs[mid] if len(xs) % 2 else (xs[mid - 1] + xs[mid]) / 2
        return int(v) if float(v).is_integer() else v
    cur_with_internal = [m for m in cur if m["rests_on"]]
    cur_on_withdrawn = [m for m in cur if any(r["status"] == "withdrawn" for r in m["rests_on"])]
    cur_on_unformal = [m for m in cur if any(not r["has_lean"] for r in m["rests_on"])]
    current_ids = {m["id"] for m in cur}
    distinct_works = {wid for wid, w in works.items() if any(c in current_ids for c in w["cited_by"])}
    summary = {
        "upstream": {"repository": "https://github.com/openai/math", "commit": commit, "commit_date": commit_date,
                      "formalization_yaml_review_status": review_status, "formalization_yaml_sections": fy_top},
        "upstream_reported": upstream_reported,
        "families": len(families),
        "disciplines": len(disciplines),
        "manuscripts_current": len(cur),
        "manuscripts_withdrawn": sum(1 for m in manuscripts.values() if m["status"] == "withdrawn"),
        "manuscripts_previous_editions": sum(1 for m in manuscripts.values() if m["status"] == "previous-edition"),
        "manuscripts_other": sorted(s for s, m in manuscripts.items() if m["status"] == "other"),
        "manuscripts_tex_unparsed": tex_failures,
        "statements_lean": len(challenges),
        "statements_lean_main_results": sum(1 for c in challenges.values() if c["main_result"]),
        "main_result_declarations": sum(len(v) for v in main_results.values()),
        "families_with_lean": sum(1 for f in families if f["statements"]),
        "manuscripts_with_lean": sum(1 for m in cur if m["has_lean"]),
        "lean_statements_pure_mathlib": len(pure),
        "lean_statements_no_local_vocabulary": len(no_local),
        "lean_statements_with_custom_vocabulary": len(vocab),
        "lean_statements_importing_non_mathlib": sum(1 for c in challenges.values() if c["non_mathlib_imports"]),
        "lean_statements_declaring_axioms": sum(1 for c in challenges.values() if c["declares_axiom"]),
        "lean_statements_with_definition_holes": sorted(c["id"] for c in challenges.values() if c["comparator"].get("definition_names")),
        "lean_definition_holes": sum(len(c["comparator"].get("definition_names") or []) for c in challenges.values()),
        "lean_vocabulary_max": max((c["vocabulary_count"] for c in challenges.values()), default=0),
        "lean_vocabulary_max_statement": max(challenges.values(), key=lambda c: c["vocabulary_count"])["id"] if challenges else None,
        "lean_vocabulary_median": median(c["vocabulary_count"] for c in challenges.values()),
        "lean_statements_declaring_axioms_ids": sorted(c["id"] for c in challenges.values() if c["declares_axiom"]),
        "lean_statements_pure_mathlib_ids": sorted(c["id"] for c in pure),
        "lean_vocabulary_total": sum(c["vocabulary_count"] for c in challenges.values()),
        "paper_statement_environments": dict(sorted(stmt_counts.items())),
        "internal_citation_edges": len(edges),
        "manuscripts_citing_collection": len(cur_with_internal),
        "manuscripts_citing_withdrawn": sorted(m["id"] for m in cur_on_withdrawn),
        "manuscripts_citing_superseded_editions": sorted(m["id"] for m in cur if any(r["cited_edition_status"] == "previous-edition" for r in m["rests_on"])),
        "manuscripts_citing_unformalised_collection_results": len(cur_on_unformal),
        "external_works_cited": len(distinct_works),
        "external_citations": sum(len(m.get("references", [])) for m in cur),
        "definitions": {
            "lean_statements_pure_mathlib": "Comparator challenge files that import only Mathlib and in which a textual scan detects no local vocabulary declarations: a reader checks the theorem statement against Mathlib vocabulary alone. Files with no local vocabulary that import OpenAI's own modules are excluded.",
            "lean_vocabulary": "Local vocabulary declarations detected by a textual scan of a Comparator challenge file: definitions, abbreviations, structures, classes, inductive types, instances, notation, macros and axioms. Theorem and lemma declarations, including the target theorem, are excluded. A proof that Comparator accepts proves the statement as phrased in this vocabulary, so each item is something a reader checks means what the paper means.",
            "manuscripts_with_lean": "Current manuscripts listed as accompanying papers in a family's Lean scope note (lean/docs/NNN.md) that links at least one Comparator statement.",
            "internal_citation_edges": "Bibliography entries in a manuscript's TeX sources that point to another manuscript in the collection (an openai/math preprint link or an OAI: key), counted once per citing and cited manuscript.",
            "external_works_cited": "References outside the collection grouped automatically by DOI, then arXiv id, then full normalised title; a title-only reference joins the one DOI or arXiv record with the same full title (and year, when both give one), keeping the merged keys as aliases in works.json. No person has audited the grouping, so a work can still be split or merged by mistake.",
            "external_citations": "Resolved bibliography keys in current manuscripts' TeX sources that point outside the collection, each manuscript and key counted once.",
        },
    }

    def work_label(w):
        r = w["record"]
        if r.get("title"):
            return {"authors": r.get("authors"), "title": r["title"], "year": r.get("year")}
        return {"text": (r.get("text") or "")[:200], "year": r.get("year")}
    def current_citers(w):
        return [c for c in w["cited_by"] if c in current_ids]
    ranked_works = sorted((w for w in works.values() if current_citers(w)), key=lambda w: (-len(current_citers(w)), w["id"]))
    summary["highlights"] = {
        "most_cited_outside_works": [
            dict(work_label(w), id=w["id"], citing_manuscripts=len(current_citers(w))) for w in ranked_works[:25]
        ],
        "most_cited_inside_collection": [
            {"manuscript": m["id"], "title": m["title"], "family": m["family"],
             "cited_by": len(m["cited_by_in_collection"]), "has_lean": m["has_lean"]}
            for m in sorted(cur, key=lambda m: (-len(m["cited_by_in_collection"]), m["id"]))[:25]
        ],
    }
    summary["definitions"]["most_cited_outside_works"] = "Outside works ranked by how many current manuscripts cite them (each manuscript counted once)."
    summary["definitions"]["most_cited_inside_collection"] = "Current manuscripts ranked by how many other current manuscripts in the collection cite them, with whether each has an accompanying Lean statement."

    out.mkdir(parents=True, exist_ok=True)

    def dump(name, obj):
        (out / name).write_text(json.dumps(obj, ensure_ascii=False, indent=1, sort_keys=False) + "\n", encoding="utf-8")

    # Release-wide coverage classification (curated/scope_coverage.json), when present.
    cov_path = ROOT / "curated" / "scope_coverage.json"
    if cov_path.exists():
        cov = json.loads(cov_path.read_text(encoding="utf-8"))
        by_stmt = {r["statement"]: r for r in cov.get("rows", [])}
        # The classification belongs to one pin and one exact set of challenge files; mixing it with
        # another release would attach old readings to new files, so a mismatch withholds it entirely.
        stale = []
        if cov.get("upstream_commit") != commit:
            stale.append(f"classified at {str(cov.get('upstream_commit'))[:12]}, data built from {commit[:12]}")
        if set(by_stmt) != set(challenges):
            stale.append(f"{len(set(challenges) - set(by_stmt))} challenge files unclassified, "
                         f"{len(set(by_stmt) - set(challenges))} classified files absent")
        if stale:
            log("scope_coverage withheld: " + "; ".join(stale))
            summary["scope_coverage"] = {"stale": True, "stale_reasons": stale, "reviewed_by_people": False,
                                         "upstream_commit": cov.get("upstream_commit")}
        else:
            class_counts = Counter(r["class"] for r in cov.get("rows", []))
            neither, partial_only, no_full, mixed = [], [], [], []
            for f in families:
                if not f["statements"]:
                    continue
                cls = {by_stmt[sid]["class"] for sid in f["statements"] if sid in by_stmt}
                if "headline" not in cls:
                    no_full.append(f["id"])
                    (partial_only if "headline-part" in cls else neither).append(f["id"])
                if len(cls) > 1:
                    mixed.append(f["id"])
            summary["scope_coverage"] = {
                "stale": False,
                "status": "draft",
                "classes": dict(sorted(class_counts.items())),
                "statements_classified": len(by_stmt),
                "families_with_lean_but_no_headline_coverage": sorted(neither),
                "families_partial_headline_only": sorted(partial_only),
                "families_no_full_headline": sorted(no_full),
                "families_mixed_classes": sorted(mixed),
                "reviewed_by_people": False,
                "upstream_commit": cov.get("upstream_commit"),
            }
        summary["definitions"]["scope_coverage"] = (
            "A draft classification of how each Comparator challenge file relates to its paper's headline result: it states "
            "the headline theorem, part of it, a consequence, a weaker form or a supporting result, or the note leaves it unclear. "
            "An AI agent made it from OpenAI's scope note for the family (lean/docs/<family>.md), quoting the note on every row "
            "(curated/scope_coverage.json). No person has reviewed it.")
    # Fold other people's work into the rows, crediting the source on every value (curated/sources/*.json).
    sources = []
    for sp in sorted((ROOT / "curated" / "sources").glob("*.json")):
        src = json.loads(sp.read_text(encoding="utf-8"))
        meta = src.get("source", {})
        sid_ = meta.get("id") or sp.stem
        sources.append({k: meta.get(k) for k in ("id", "name", "url", "authors", "kind", "licence", "reuse", "snapshot", "method", "fields", "tier_names", "adopted")})
        for fid, vals in (src.get("families") or {}).items():
            if fid not in fam_by_id:
                continue
            sourced = fam_by_id[fid].setdefault("sourced", {})
            for field, value in vals.items():
                if value is None:
                    continue
                sourced.setdefault(field, []).append({"value": value, "source": sid_})
    summary["sources"] = sources
    tl = next((x for x in sources if x["id"] == "tier-list"), None)
    yaml_src_slugs = set(re.findall(r"preprints/([^/\s]+)/", read(upstream / "lean" / "formalization.yaml").split("related_formalizations:")[0]))
    recon = {
        "families_with_lean_in_scope_notes": sum(1 for f in families if f["statements"]),
        "families_with_a_paper_in_formalization_yaml_sources": len({m["family"] for sl, m in manuscripts.items() if sl in yaml_src_slugs and m.get("family")}),
        "papers_in_formalization_yaml_sources": len(yaml_src_slugs),
        "openai_reported_top_line_formalized": (upstream_reported.get("top_line_results_formalized") or {}).get("quote"),
    }
    if tl:
        tlf = [f.get("sourced", {}).get("lean_formalisations", [{}])[0].get("value") for f in families]
        recon["tier_list_families_with_lean"] = sum(1 for v in tlf if v)
        recon["tier_list_lean_formalisations_total"] = sum(v for v in tlf if v)
    summary["lean_count_reconciliation"] = recon
    summary["definitions"]["lean_count_reconciliation"] = (
        "Published counts of how much of the release has Lean, side by side: families whose Lean notes link a Comparator "
        "statement; families and papers in the sources list of OpenAI's lean/formalization.yaml; OpenAI's own reported "
        "share; and counts from other public sources. Each measures a different thing.")

    # Review queue: where a careful human reading of a challenge file is most useful, ordered by a
    # stated rule over public facts. It allocates attention; it says nothing about correctness.
    rows_by_stmt = {}
    if cov_path.exists() and not (summary.get("scope_coverage") or {}).get("stale"):
        rows_by_stmt = {r["statement"]: r for r in json.loads(cov_path.read_text(encoding="utf-8")).get("rows", [])}
    no_full = set((summary.get("scope_coverage") or {}).get("families_no_full_headline") or [])
    targets = defaultdict(set)
    for c in challenges.values():
        for t in c["comparator"].get("theorem_names") or []:
            targets[(c["comparator"].get("solution_module"), t)].add(c["id"])
    queue = []
    for c in challenges.values():
        cfg, row, reasons = c["comparator"], rows_by_stmt.get(c["id"]), []
        holes = cfg.get("definition_names") or []
        if not cfg.get("theorem_names"):
            reasons.append((100, "definition-only", "The configuration names no theorem: it checks a definition whose type carries the claim, so read that definition's type and body."))
        if holes:
            reasons.append((90 + len(holes), "definition-holes", f"{len(holes)} definition hole{'s' if len(holes) != 1 else ''}: Comparator compares {'these' if len(holes) != 1 else 'it'} by name and type only, so a reader checks what each solution body means."))
        if row and row["class"] == "unclear":
            reasons.append((85, "unclear-scope", "The draft scope reading could not tell from OpenAI's note how much of the paper's headline result this file states."))
        if row and row.get("needs_specialist"):
            reasons.append((80, "needs-specialist", "The draft scope reading depends on mathematics a specialist should settle."))
        twins = sorted({x for t in cfg.get("theorem_names") or [] for x in targets[(cfg.get("solution_module"), t)]} - {c["id"]})
        if twins:
            reasons.append((70, "shared-target", f"Checks the same target theorem as {', '.join(twins)}; compare the two files before counting them as separate results."))
        if c["declares_axiom"]:
            reasons.append((60, "axiom", "States its claim through an axiom in the challenge file; check what the configuration compares."))
        if c["vocabulary_count"] == 0 and c["non_mathlib_imports"]:
            reasons.append((50, "imported-vocabulary", "Adds no local vocabulary but imports OpenAI modules, so its meaning lives in those imported definitions."))
        if c["vocabulary_count"] >= 100:
            reasons.append((20 + min(c["vocabulary_count"], 2000) // 100, "large", f"{c['vocabulary_count']:,} local vocabulary declarations to read."))
        if row and row["class"] != "headline" and any(f in no_full for f in c["families"]):
            reasons.append((5, "family-without-full-headline", "No Lean statement in its family states the paper's full headline theorem."))
        queue.append({"statement": c["id"], "families": c["families"], "priority": sum(p for p, _, _ in reasons),
                      "reasons": [{"kind": k, "text": t} for _, k, t in sorted(reasons, key=lambda r: -r[0])]})
    queue.sort(key=lambda r: (-r["priority"], r["statement"]))
    for i, r in enumerate(queue, 1):
        r["order"] = i
    summary["review_queue"] = {
        "flagged": sum(1 for r in queue if r["reasons"]),
        "first": [r["statement"] for r in queue[:25]],
        "rule": ("Points per reason, highest first: a configuration with no theorem target 100; definition holes 90 plus one per hole; "
                 "unclear draft scope 85; a draft scope reading needing a specialist 80; a target theorem shared with another file 70; "
                 "an axiom in the challenge 60; no local vocabulary but OpenAI imports 50; 100 or more local declarations 20 plus one per hundred "
                 "(capped); a family with no full-headline statement 5. Ties go alphabetically. The order allocates reading; it is no verdict."),
    }
    summary["lean_distinct_target_theorems"] = len(targets)

    # One receipt per headline number: its unit, the universe it counts over and the rule, so no
    # figure on the site or in the README stands without a definition (scripts/build_data.py).
    pin = f"openai/math at {commit[:12]}"
    sc = summary.get("scope_coverage") or {}

    def receipt(key, value, unit, universe, rule):
        return {"key": key, "value": value, "unit": unit, "universe": universe, "rule": rule, "source": "scripts/build_data.py"}
    summary["metric_receipts"] = [
        receipt("families", summary["families"], "result families", f"{pin}, overview.tex and CONTENTS.md",
                "Each family id in the catalogue. Ids run 001 to 377; five are unused."),
        receipt("manuscripts_current", summary["manuscripts_current"], "manuscripts", f"{pin}, preprints/",
                "Manuscript folders listed under a family in overview.tex or CONTENTS.md and not marked withdrawn in their README."),
        receipt("statements_lean", summary["statements_lean"], "Comparator challenge files", f"{pin}, lean/ComparatorChallenges/",
                "Each <Id>.lean with its <Id>.json configuration. One file can hold several target theorems."),
        receipt("statements_lean_main_results", summary["statements_lean_main_results"], "challenge files", f"{pin}, lean/formalization.yaml",
                "Challenge files named by at least one status.main_results item."),
        receipt("main_result_declarations", summary["main_result_declarations"], "declaration records", f"{pin}, lean/formalization.yaml",
                "Items under status.main_results, each naming a configuration, a declaration and a file."),
        receipt("families_with_lean", summary["families_with_lean"], "result families", f"{pin}, lean/docs/NNN.md",
                "Families whose Lean scope note links at least one Comparator challenge file."),
        receipt("manuscripts_with_lean", summary["manuscripts_with_lean"], "manuscripts", f"{pin}, lean/docs/NNN.md headers",
                "Current manuscripts named as accompanying papers in a scope note that links a challenge file. This is an association by the note; it does not say which of a paper's claims the Lean states."),
        receipt("lean_statements_pure_mathlib", summary["lean_statements_pure_mathlib"], "challenge files", f"{pin}, lean/ComparatorChallenges/",
                "Files that import only Mathlib and in which a textual scan detects no local vocabulary declarations."),
        receipt("lean_statements_no_local_vocabulary", summary["lean_statements_no_local_vocabulary"], "challenge files", f"{pin}, lean/ComparatorChallenges/",
                "Files in which a textual scan detects no local vocabulary declarations, whatever they import."),
        receipt("lean_vocabulary_median", summary["lean_vocabulary_median"], "local vocabulary declarations per file", f"{pin}, all challenge files",
                "Conventional median of the detected local vocabulary declarations (definitions, structures, instances, notation, axioms and similar; theorems and lemmas excluded)."),
        receipt("lean_distinct_target_theorems", summary["lean_distinct_target_theorems"], "distinct target theorems", f"{pin}, lean/ComparatorChallenges/*.json",
                "Distinct pairs of solution module and theorem name across all configurations' theorem_names. Two files can check the same theorem."),
        receipt("lean_definition_holes", summary["lean_definition_holes"], "definition holes", f"{pin}, lean/ComparatorChallenges/*.json",
                f"Names in a configuration's definition_names, across {len(summary['lean_statements_with_definition_holes'])} configurations. "
                "Comparator compares these definitions by name and type only; their bodies come from OpenAI's solution, so a reader checks what each body means."),
        receipt("paper_statement_environments", sum(summary["paper_statement_environments"].values()), "theorem-like environments", f"{pin}, current manuscripts' TeX",
                "Theorem, lemma, proposition, corollary and similar environments extracted from the TeX, repeated statements included."),
        receipt("internal_citation_edges", summary["internal_citation_edges"], "citing and cited manuscript pairs", f"{pin}, current manuscripts' bibliographies",
                "Bibliography entries pointing to another manuscript in the collection. A citation records a reference; it does not establish that a proof uses the cited result."),
        receipt("external_citations", summary["external_citations"], "resolved external reference keys", f"{pin}, current manuscripts' bibliographies",
                "Bibliography keys resolved to a reference outside the collection, each manuscript and key counted once."),
        receipt("external_works_cited", summary["external_works_cited"], "automatically grouped references", f"{pin}, current manuscripts' bibliographies",
                "References grouped by DOI, then arXiv id, then full title, with exact-title matches joined to their DOI or arXiv record and kept as aliases. Unaudited."),
    ]
    if sc and not sc.get("stale"):
        summary["metric_receipts"].append(receipt(
            "scope_coverage", sc["statements_classified"], "challenge files classified", f"{pin}, curated/scope_coverage.json",
            "Draft classification by an AI agent from OpenAI's scope notes, unreviewed: "
            + ", ".join(f"{k} {v}" for k, v in sc["classes"].items()) + "."))
    prior = out / "summary.json"
    if prior.exists():
        # The Lean claim-layer block comes from scripts/build_lean_claims.py; keep it across rebuilds.
        try:
            kept = json.loads(prior.read_text(encoding="utf-8")).get("lean_claim_layer")
        except json.JSONDecodeError:
            kept = None
        if kept and kept.get("upstream_commit") == commit:
            summary["lean_claim_layer"] = kept
        elif kept:
            print("note: dropping lean_claim_layer built from another upstream commit; rerun scripts/build_lean_claims.py",
                  file=sys.stderr)
    dump("summary.json", summary)
    dump("disciplines.json", [{"name": d["name"], "families": d["families"]} for d in disciplines])
    dump("families.json", families)
    dump("manuscripts.json", [manuscripts[s] for s in all_slugs])
    dump("statements.json", [challenges[k] for k in sorted(challenges)])
    dump("review_queue.json", queue)
    dump("graph.json", edges)
    dump("works.json", sorted(works.values(), key=lambda w: (-len(w["cited_by"]), w["id"])))
    dump("history.json", history)
    log(json.dumps({k: v for k, v in summary.items() if k not in ("definitions",)}, ensure_ascii=False, indent=1)[:4000])
    return summary


def main():
    ap = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    ap.add_argument("--upstream", default=os.environ.get("OPENAI_MATH_UPSTREAM", str(ROOT.parent / "openai-math-upstream")))
    ap.add_argument("--out", default=str(ROOT / "data"))
    ap.add_argument("--quiet", action="store_true")
    a = ap.parse_args()
    up = Path(a.upstream).expanduser().resolve()
    if not (up / "overview.tex").exists():
        sys.exit(f"upstream checkout not found at {up}; run scripts/fetch_upstream.sh first")
    pin = json.loads((ROOT / "upstream.json").read_text())["commit"]
    got = git_commit(up)
    if got != pin:
        print(f"warning: upstream is at {got}, upstream.json pins {pin}", file=sys.stderr)
    build(up, Path(a.out), a.quiet)


if __name__ == "__main__":
    main()
