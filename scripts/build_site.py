#!/usr/bin/env python3
"""Build the Plectis Atlas static site.

Reads data/*.json (produced by scripts/build_data.py), site/copy.json (every
human-facing sentence) and site/config.json (URLs), and writes static HTML,
per-page data and assets to site/_build/. Standard library only.

    python3 scripts/build_site.py            # build
    python3 scripts/build_site.py --og       # also render social card PNGs (needs Playwright)
    python3 scripts/build_site.py --og-cards # also render one PNG per Lean statement
    python3 scripts/build_site.py --contributions DIR --out DIR   # build against a fixture

Every number on the site is read from data/summary.json or computed here.
"""
from __future__ import annotations

import argparse
import hashlib
import html
import json
import re
import shutil
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from pathlib import Path
from urllib.parse import quote, urlencode

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data"
SITE = ROOT / "site"
OUT = SITE / "_build"
ASSETS = SITE / "assets"

# --------------------------------------------------------------------- load


def load(name):
    return json.loads((DATA / name).read_text(encoding="utf-8"))


CFG = json.loads((SITE / "config.json").read_text(encoding="utf-8"))
COPY = json.loads((SITE / "copy.json").read_text(encoding="utf-8"))
SUMMARY = load("summary.json")
DISCIPLINES = load("disciplines.json")
FAMILIES = load("families.json")
MANUSCRIPTS = load("manuscripts.json")
STATEMENTS = load("statements.json")
GRAPH = load("graph.json")
HISTORY = load("history.json")

FAM = {f["id"]: f for f in FAMILIES}
MS = {m["id"]: m for m in MANUSCRIPTS}
ST = {s["id"]: s for s in STATEMENTS}
try:
    _CLAIMS = load("lean_claims.json")
except FileNotFoundError:
    _CLAIMS = []
# Papers with a full reading page (scripts/build_papers.py writes it over papers/<slug>.html).
try:
    PAPER_READING = {r["id"]: r["status"] for r in load("paper_acceptance.json").get("papers", [])
                     if r.get("status") in ("accepted", "partial")}
except (FileNotFoundError, ValueError):
    PAPER_READING = {}


def paper_statement_href(ms_id, st, root):
    """The statement's place in the paper's reading page, or None when the paper has none:
    its label, else L-<file>-<line> (the anchors scripts/build_papers.py writes)."""
    if ms_id not in PAPER_READING or not st:
        return None
    anchor = st.get("label") or f'L-{st.get("file")}-{st.get("line")}'
    return f"{root}papers/{quote(ms_id)}.html#{quote(anchor, safe=':-_./')}"
CLAIMS_BY_FAMILY: dict = {}
for _c in _CLAIMS:
    for _f in _c.get("families") or []:
        CLAIMS_BY_FAMILY.setdefault(_f, []).append(_c)
try:
    _RQ = load("review_queue.json")
except FileNotFoundError:
    _RQ = []
REVIEW_REASONS = {r["statement"]: [x.get("text") for x in (r.get("reasons") or []) if x.get("text")] for r in _RQ if isinstance(r, dict) and r.get("statement")}
UP = SUMMARY["upstream"]
COMMIT = UP["commit"]
COMMIT_SHORT = COMMIT[:7]
BASE_BLOB = f"https://github.com/openai/math/blob/{COMMIT}/"
BASE_URL = CFG["base_url"].rstrip("/") + "/"
REPO = CFG["repo"].rstrip("/")
KATEX = CFG["katex_version"]
# KaTeX is served from the site itself (site/assets/vendor/katex-<version>, MIT), the
# same build the paper checker runs, so pages make no third-party requests.
KATEX_DIR = f"assets/vendor/katex-{KATEX}"
DISC_OF = {fid: i for i, d in enumerate(DISCIPLINES) for fid in d["families"]}
WARN: list[str] = []
STATS = Counter()


def warn(msg):
    WARN.append(msg)


# ------------------------------------------------------------------ helpers


def esc(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def num(n) -> str:
    return f"{n:,}" if isinstance(n, int) else str(n)


def C(path: str, **kw) -> str:
    node = COPY
    for part in path.split("."):
        node = node[part]
    if kw:
        node = node.format(**{k: (num(v) if isinstance(v, int) else v) for k, v in kw.items()})
    return node


def ctext(s: str) -> str:
    """Escape copy text, set `backticked` words as code, and turn [[id|text]] into a
    glossary term (its href is completed with the page's root by write_page)."""
    out = re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(s))
    return TERM_RE.sub(lambda m: term_link(m.group(1), m.group(2)), out)


GLOSSARY = {t_["id"]: t_ for t_ in json.loads((ASSETS / "glossary.json").read_text(encoding="utf-8"))["terms"]}
TERM_RE = re.compile(r"\[\[([a-z0-9-]+)\|([^\]]+)\]\]")


def term_link(tid: str, text_html: str) -> str:
    if tid not in GLOSSARY:
        WARN.append(f"unknown glossary term {tid!r}")
        return text_html
    return f'<a class="term" href="__ROOT__glossary.html#{tid}" data-term="{tid}">{text_html}</a>'


def nword(n: int, sing: str, plur: str) -> str:
    return f"{num(n)} {sing if n == 1 else plur}"


def n_ms(n):
    return nword(n, C("words.manuscript"), C("words.manuscripts"))


def n_lean(n):
    return nword(n, C("words.lean_statement"), C("words.lean_statements"))


def slugify(s: str) -> str:
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", s.lower()).strip("-")


DISC_SLUG = [slugify(d["name"]) for d in DISCIPLINES]

GREEK = {k: v for k, v in zip(
    "alpha beta gamma delta epsilon varepsilon zeta eta theta vartheta iota kappa lambda mu nu xi pi rho sigma tau upsilon phi varphi chi psi omega Gamma Delta Theta Lambda Xi Pi Sigma Phi Psi Omega".split(),
    "α β γ δ ε ε ζ η θ ϑ ι κ λ μ ν ξ π ρ σ τ υ ϕ φ χ ψ ω Γ Δ Θ Λ Ξ Π Σ Φ Ψ Ω".split())}
PLAIN_SYM = {"le": "≤", "leq": "≤", "ge": "≥", "geq": "≥", "lt": "<", "gt": ">", "ne": "≠", "neq": "≠", "cdot": "·",
             "times": "×", "infty": "∞", "to": "→", "in": "∈", "pm": "±", "ldots": "…", "cdots": "⋯", "dots": "…",
             "log": "log", "exp": "exp", "Re": "Re", "sim": "∼", "approx": "≈", "subset": "⊂", "subseteq": "⊆",
             "ell": "ℓ", "partial": "∂", "sqrt": "√", "mid": "|", "colon": ":", "otimes": "⊗", "oplus": "⊕"}
SUPS = str.maketrans("0123456789+-=()niak", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵃᵏ")
SUBS = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")


def tex_plain(s: str) -> str:
    """Plain-text rendering of a title or description for <title>, meta tags and search."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = html.unescape(s)

    def math(m):
        t = m.group(1)
        t = re.sub(r"\\(?:mathsf|mathcal|mathbb|mathrm|mathbf|operatorname|text|mathit|mathfrak|mathscr)\s*\{([^{}]*)\}", r"\1", t)
        t = re.sub(r"\\(?:mathsf|mathcal|mathbb|mathrm|mathbf)\s+(\w)", r"\1", t)
        t = re.sub(r"\\([A-Za-z]+)", lambda mm: GREEK.get(mm.group(1), PLAIN_SYM.get(mm.group(1), "")), t)
        t = re.sub(r"\^\{([^{}]*)\}", lambda mm: mm.group(1).translate(SUPS) if re.fullmatch(r"[0-9+\-=()niak]+", mm.group(1)) else "^" + mm.group(1), t)
        t = re.sub(r"\^(\w)", lambda mm: mm.group(1).translate(SUPS), t)
        t = re.sub(r"_\{([^{}]*)\}", lambda mm: mm.group(1).translate(SUBS) if re.fullmatch(r"[0-9+\-=()]+", mm.group(1)) else "_" + mm.group(1), t)
        t = re.sub(r"_(\d)", lambda mm: mm.group(1).translate(SUBS), t)
        t = t.replace("{", "").replace("}", "").replace("\\", "")
        return re.sub(r"\s+", " ", t).strip()

    s = re.sub(r"\\\((.*?)\\\)", math, s, flags=re.S)
    s = re.sub(r"\\\[(.*?)\\\]", math, s, flags=re.S)
    s = re.sub(r"\$([^$]+)\$", math, s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def short(s: str, n: int) -> str:
    s = s.strip()
    if len(s) <= n:
        return s
    cut = s[: n - 1].rsplit(" ", 1)[0]
    return cut.rstrip(",;:.") + "…"


ALLOWED_TAGS = re.compile(r"</?(?:i|b|em|strong|sub|sup)>")


def resolve_link(url: str, base_dir: str = "") -> str:
    if re.match(r"^[a-z]+://", url):
        return url
    if url.startswith("../"):
        # Relative to preprints/<slug>/README.md
        return BASE_BLOB + "preprints/" + url[3:]
    return BASE_BLOB + base_dir + url


def rich(s: str, base_dir: str = "", root: str = "", link_results: bool = False) -> str:
    """Sanitise release HTML (allowing <i>, <sub>, <sup>), turn markdown links into
    links at the pinned commit, keep TeX delimiters for the client renderer."""
    if not s:
        return ""
    out = []
    pos = 0
    for m in re.finditer(r"\[([^\]]+)\]\(([^)\s]+)\)|" + ALLOWED_TAGS.pattern, s):
        out.append(_esc_keep_entities(s[pos:m.start()]))
        if m.group(1):
            href = resolve_link(m.group(2), base_dir)
            out.append(f'<a href="{esc(href)}" rel="noopener">{_esc_keep_entities(m.group(1))}</a>')
        else:
            out.append(m.group(0))
        pos = m.end()
    out.append(_esc_keep_entities(s[pos:]))
    res = "".join(out)
    if link_results:
        res = re.sub(r"\b(results?) (\d{3})\b", lambda m: (f'{m.group(1)} <a href="{root}families/{m.group(2)}.html">{m.group(2)}</a>' if m.group(2) in FAM else m.group(0)), res)
    return res


def _esc_keep_entities(t: str) -> str:
    t = re.sub(r"&(?!(?:[a-zA-Z]+|#\d+|#x[0-9a-fA-F]+);)", "&amp;", t)
    return t.replace("<", "&lt;").replace(">", "&gt;")


def md_paragraphs(s: str, base_dir: str = "") -> str:
    paras = [p.strip() for p in re.split(r"\n\s*\n", s or "") if p.strip()]
    out = []
    for p in paras:
        if all(line.strip().startswith(("- ", "* ")) for line in p.splitlines()):
            items = "".join(f"<li>{md_inline(line.strip()[2:], base_dir)}</li>" for line in p.splitlines())
            out.append(f"<ul>{items}</ul>")
        else:
            out.append(f"<p>{md_inline(p, base_dir)}</p>")
    return "".join(out)


def md_inline(s: str, base_dir: str = "") -> str:
    r = rich(s, base_dir)
    r = re.sub(r"\*\*([^*]+)\*\*", r"<strong>\1</strong>", r)
    r = re.sub(r"`([^`]+)`", r"<code>\1</code>", r)
    return r


def clean_ref_text(s):
    """Undo two artefacts of the data extractor's detex step: '\\t' of \\textbf read as
    an accent ('extbf'), and '\\u' of \\url likewise ('rl'), '\\d' of \\doi ('oi')."""
    if not s:
        return s
    s = re.sub(r"\bext(?:bf|it|tt|sc|rm|up|sf|normal|sl)(?=[\w(\[])", "", s)
    s = re.sub(r"\bext(?:bf|it|tt|sc|rm|up|sf|normal|sl)\b\s*", "", s)
    s = re.sub(r"\bextquotedblleft", "“", s)
    s = re.sub(r"\bextquotedblright", "”", s)
    s = re.sub(r"\brl(?=https?://)", "", s)
    s = re.sub(r"\boi(?=10\.\d{4})", "doi:", s)
    return re.sub(r"\s+", " ", s).strip()


# ------------------------------------------------------- TeX statement converter

MATH_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*",
             "eqnarray", "eqnarray*", "displaymath", "math", "flalign", "flalign*", "alignat", "alignat*",
             "dmath", "dmath*"}
LIST_ENVS = {"enumerate", "itemize", "description"}
FORMAT = {"emph": "em", "textit": "em", "textsl": "em", "textbf": "strong", "texttt": "code", "underline": "u"}
PLAIN_CMD = {"textup", "textnormal", "textrm", "text", "mbox", "hbox", "textmd", "textsf", "fbox", "makebox", "textsc"}
SKIP_ARG = {"label", "index", "vspace", "hspace", "phantom", "nocite", "addcontentsline", "hypertarget", "enlargethispage"}
SKIP_NOARG = {"noindent", "medskip", "smallskip", "bigskip", "centering", "normalfont", "nobreak", "allowbreak", "relax",
              "protect", "hfill", "null", "linebreak", "newpage", "clearpage", "leavevmode", "unskip", "ignorespaces",
              "break", "upshape", "itshape", "rmfamily", "mdseries", "displaystyle", "small", "footnotesize", "normalsize",
              "nolinebreak", "pagebreak", "nopagebreak", "hfil", "vfill", "qedhere", "smallbreak", "medbreak", "bigbreak", "indent", "sloppy"}
SYMBOL = {"S": "§", "ldots": "…", "dots": "…", "textellipsis": "…", "&": "&amp;", "%": "%", "_": "_", "#": "#",
          "$": "$", "{": "{", "}": "}", "textendash": "–", "textemdash": "—", "textquoteright": "’",
          "textquoteleft": "‘", "i": "ı", "ss": "ß", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł", "ae": "æ", "AE": "Æ",
          "oe": "œ", "aa": "å", "quad": "\u2003", "qquad": "\u2003\u2003", ",": "\u2009", " ": " ", "@": "", "/": "",
          "-": "", "textbackslash": "\\", "P": "¶", "dag": "†", "copyright": "©", "checkmark": "✓",
          "textdegree": "°", "enspace": "\u2002", "thinspace": "\u2009", ";": " ", "!": "", "textasciitilde": "~"}
ACCENTS = {'"': "\u0308", "'": "\u0301", "`": "\u0300", "^": "\u0302", "~": "\u0303", "=": "\u0304", ".": "\u0307",
           "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "k": "\u0328", "r": "\u030a"}
REF_CMDS = {"ref", "eqref", "Cref", "cref", "autoref", "Autoref", "pageref", "nameref", "cpageref", "Cpageref", "labelcref", "subref"}
CITE_CMDS = {"cite", "citep", "citet", "cites", "citealp", "parencite", "textcite", "Cite", "citealt", "citeauthor"}
BLOCK_OPEN, BLOCK_CLOSE, PARA = "\x01", "\x02", "\x03"


def roman(n: int) -> str:
    vals = [(10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, r in vals:
        while n >= v:
            out += r
            n -= v
    return out


def brace_group(s: str, i: int, o="{", c="}"):
    """s[i] == o; return (content, index after the closing bracket)."""
    depth = 0
    j = i
    while j < len(s):
        ch = s[j]
        if ch == "\\":
            j += 2
            continue
        if ch == o:
            depth += 1
        elif ch == c:
            depth -= 1
            if depth == 0:
                return s[i + 1:j], j + 1
        j += 1
    return s[i + 1:], len(s)


def skip_ws(s, i):
    while i < len(s) and s[i] in " \t\n":
        i += 1
    return i


def find_env_end(s: str, i: int, name: str):
    """i is just after \\begin{name}; return (body_end, after_end)."""
    depth = 1
    pat = re.compile(r"\\(begin|end)\{" + re.escape(name) + r"\}")
    for m in pat.finditer(s, i):
        depth += 1 if m.group(1) == "begin" else -1
        if depth == 0:
            return m.start(), m.end()
    return len(s), len(s)


def strip_math(t: str) -> str:
    t = re.sub(r"\\label\s*\{[^{}]*\}", "", t)
    t = re.sub(r"\\(?:nonumber|notag)\b", "", t)
    t = re.sub(r"\\eqref\s*\{([^{}]*)\}", lambda m: r"\text{(" + m.group(1).replace("_", r"\_") + ")}", t)
    t = re.sub(r"\\(?:ref|Cref|cref)\s*\{([^{}]*)\}", lambda m: r"\text{" + m.group(1).replace("_", r"\_") + "}", t)
    t = re.sub(r"\\cite\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}", "", t)
    t = re.sub(r"\\intertext\s*\{([^{}]*)\}", r"\\text{\1}\\\\", t)
    t = re.sub(r"(?<!\\)%[^\n]*", "", t)
    t = t.replace(r"\begin{split}", r"\begin{aligned}").replace(r"\end{split}", r"\end{aligned}")
    t = t.replace(r"\begin{psmallmatrix}", r"\left(\begin{smallmatrix}").replace(r"\end{psmallmatrix}", r"\end{smallmatrix}\right)")
    return t.strip()


class TexConv:
    def __init__(self, ms: dict, root: str):
        self.ms = ms
        self.root = root
        self.labels = {st["label"]: st for st in (ms.get("statements") or []) if st.get("label")}
        self.refs = {r["key"]: r for r in (ms.get("references") or [])}
        self.internal = {r["key"]: r for r in (ms.get("internal_references") or [])}
        self.macros = (ms.get("tex") or {}).get("macros") or {}
        self.fail = 0

    # math -----------------------------------------------------------
    def m_inline(self, t: str) -> str:
        STATS["math_inline"] += 1
        return f'<span class="m">{esc(strip_math(t))}</span>'

    def m_display(self, t: str, env: str = "", opt: str = "") -> str:
        STATS["math_display"] += 1
        t = strip_math(t)
        base = env.rstrip("*")
        if base in ("align", "flalign", "eqnarray"):
            t = re.sub(r"\\tag\*?\s*\{[^{}]*\}", "", t)
            t = r"\begin{aligned}" + t + r"\end{aligned}"
        elif base in ("gather", "multline"):
            t = re.sub(r"\\tag\*?\s*\{[^{}]*\}", "", t)
            t = r"\begin{gathered}" + t + r"\end{gathered}"
        elif base == "alignat":
            t = re.sub(r"\\tag\*?\s*\{[^{}]*\}", "", t)
            t = r"\begin{alignedat}{" + (opt or "1") + "}" + t + r"\end{alignedat}"
        elif re.search(r"(?<!\\)\\\\", _top_level(t)):
            t = r"\begin{gathered}" + t + r"\end{gathered}"
        return f'{BLOCK_OPEN}<div class="m-d"><span class="m" data-d="1">{esc(t)}</span></div>{BLOCK_CLOSE}'

    # text -----------------------------------------------------------
    def cite(self, keys: str, opt: str | None) -> str:
        parts = []
        for k in [k.strip() for k in keys.split(",") if k.strip()]:
            if k in self.internal:
                tgt = self.internal[k].get("target_latest") or self.internal[k].get("target")
                if tgt in MS:
                    parts.append(f'<a href="{self.root}papers/{esc(tgt)}.html">{esc(short(tex_plain(MS[tgt]["title"]), 48))}</a>')
                    continue
            r = self.refs.get(k)
            parts.append(esc(cite_label(r, k)))
        inner = "; ".join(parts)
        if opt:
            inner += ", " + self.text(opt, inline=True)
        return f'<span class="cite">[{inner}]</span>'

    def xref(self, cmd: str, label: str) -> str:
        st = self.labels.get(label)
        title = C("family.xref_title", label=label)
        if st:
            where = (st.get("section_title") or "")
            title = f'{st["display"]}{(" (" + st["title"] + ")") if st.get("title") else ""}, {C("words.section", n=st["section"])}{(": " + where) if where else ""}'
        text = f"({label})" if cmd == "eqref" else label
        return f'<span class="xref" title="{esc(title)}">{esc(text)}</span>'

    def text(self, s: str, inline: bool = False) -> str:
        out = self._conv(s)
        if inline:
            return out.replace(PARA, " ").replace(BLOCK_OPEN, "").replace(BLOCK_CLOSE, "")
        return out

    def blocks(self, s: str) -> str:
        """Convert a statement body to block HTML (paragraphs, lists, display maths)."""
        raw = self._conv(s)
        html_parts = []
        buf = []

        def flush():
            t = "".join(buf).strip()
            if t:
                html_parts.append(f"<p>{t}</p>")
            buf.clear()

        i = 0
        for piece in re.split(f"({BLOCK_OPEN}.*?{BLOCK_CLOSE}|{PARA})", raw, flags=re.S):
            if not piece:
                continue
            if piece == PARA:
                flush()
            elif piece.startswith(BLOCK_OPEN):
                flush()
                html_parts.append(piece[1:-1])
            else:
                buf.append(piece)
            i += 1
        flush()
        return "".join(html_parts)

    def _conv(self, s: str) -> str:
        out = []
        i = 0
        n = len(s)
        while i < n:
            c = s[i]
            if s.startswith("$$", i):
                j = s.find("$$", i + 2)
                j = n if j < 0 else j
                out.append(self.m_display(s[i + 2:j]))
                i = j + 2
            elif c == "$":
                j = i + 1
                while j < n and not (s[j] == "$" and s[j - 1] != "\\"):
                    j += 1
                out.append(self.m_inline(s[i + 1:j]))
                i = j + 1
            elif s.startswith("\\(", i):
                j = s.find("\\)", i + 2)
                j = n if j < 0 else j
                out.append(self.m_inline(s[i + 2:j]))
                i = j + 2
            elif s.startswith("\\[", i):
                j = s.find("\\]", i + 2)
                j = n if j < 0 else j
                out.append(self.m_display(s[i + 2:j]))
                i = j + 2
            elif s.startswith("\\begin{", i):
                name, k = brace_group(s, i + 6)
                opt = ""
                k2 = skip_ws(s, k)
                if k2 < n and s[k2] == "[" and name not in MATH_ENVS:
                    opt, k = brace_group(s, k2, "[", "]")
                elif name.rstrip("*") == "alignat" and k2 < n and s[k2] == "{":
                    opt, k = brace_group(s, k2)
                b_end, after = find_env_end(s, k, name)
                body = s[k:b_end]
                out.append(self.env(name, body, opt))
                i = after
            elif c == "\\":
                i = self.command(s, i, out)
            elif c == "{":
                body, j = brace_group(s, i)
                m = re.match(r"\s*\\(em|it|bf|sl|sc|itshape|bfseries)\b\s*", body)
                if m:
                    tag = "strong" if m.group(1) in ("bf", "bfseries") else ("span class=\"sc\"" if m.group(1) == "sc" else "em")
                    close = tag.split()[0]
                    out.append(f"<{tag}>{self.text(body[m.end():], inline=True)}</{close}>")
                else:
                    out.append(self._conv(body))
                i = j
            elif c == "}":
                i += 1
            elif c == "~":
                out.append("&nbsp;")
                i += 1
            elif c == "%":
                j = s.find("\n", i)
                i = n if j < 0 else j + 1
            elif s.startswith("``", i):
                out.append("“")
                i += 2
            elif s.startswith("''", i):
                out.append("”")
                i += 2
            elif c == "`":
                out.append("‘")
                i += 1
            elif c == "'":
                out.append("’")
                i += 1
            elif s.startswith("---", i):
                out.append("—")
                i += 3
            elif s.startswith("--", i):
                out.append("–")
                i += 2
            elif c == "\n":
                m = re.match(r"\n[ \t]*\n\s*", s[i:])
                if m:
                    out.append(PARA)
                    i += m.end()
                else:
                    out.append(" ")
                    i += 1
            elif c == "&":
                out.append("&amp;")
                i += 1
            elif c == "<":
                out.append("&lt;")
                i += 1
            elif c == ">":
                out.append("&gt;")
                i += 1
            elif c == '"':
                out.append("&quot;")
                i += 1
            else:
                out.append(c)
                i += 1
        return "".join(out)

    def read_args(self, s, i, count=1, optional=True):
        opt = None
        j = skip_ws(s, i)
        if optional and j < len(s) and s[j] == "[":
            opt, i = brace_group(s, j, "[", "]")
        args = []
        for _ in range(count):
            j = skip_ws(s, i)
            if j < len(s) and s[j] == "{":
                a, i = brace_group(s, j)
                args.append(a)
            elif j < len(s) and s[j] != "\\":
                args.append(s[j])
                i = j + 1
            else:
                args.append("")
        return opt, args, i

    def command(self, s: str, i: int, out: list) -> int:
        n = len(s)
        m = re.match(r"\\([A-Za-z]+\*?|.)", s[i:])
        if not m:
            out.append("\\")
            return i + 1
        name = m.group(1)
        j = i + m.end()
        bare = name.rstrip("*")
        if name == "\\":
            out.append("<br>")
            j2 = skip_ws(s, j)
            if j2 < n and s[j2] == "[":
                _, j = brace_group(s, j2, "[", "]")
            return j
        if name in ACCENTS and (name not in "uvHckr" or (j < n and (s[j] == "{" or s[j] == " "))):
            j = skip_ws(s, j) if name in "uvHckr" else j
            if j < n and s[j] == "{":
                arg, j = brace_group(s, j)
            else:
                arg, j = (s[j] if j < n else ""), j + 1
            arg = arg.replace("\\i", "i").replace("\\j", "j").strip()
            if arg:
                out.append(esc(unicodedata.normalize("NFC", arg[0] + ACCENTS[name] + arg[1:])))
            return j
        if bare in FORMAT:
            _, args, j = self.read_args(s, j, 1, optional=False)
            tag = FORMAT[bare]
            out.append(f"<{tag}>{self.text(args[0], inline=True)}</{tag}>")
            return j
        if bare in PLAIN_CMD:
            _, args, j = self.read_args(s, j, 1, optional=False)
            inner = self.text(args[0], inline=True)
            out.append(f'<span class="sc">{inner}</span>' if bare == "textsc" else inner)
            return j
        if bare in SKIP_ARG:
            _, _, j = self.read_args(s, j, 1)
            return j
        if bare in SKIP_NOARG:
            return j
        if bare == "par":
            out.append(PARA)
            return j
        if bare in ("newline", "linebreak"):
            out.append("<br>")
            return j
        if bare in REF_CMDS:
            _, args, j = self.read_args(s, j, 1)
            labels = [x.strip() for x in args[0].split(",") if x.strip()]
            out.append(", ".join(self.xref(bare, lab) for lab in labels))
            return j
        if bare == "hyperref":
            _, args, j = self.read_args(s, j, 1)
            out.append(self.text(args[0], inline=True))
            return j
        if bare in CITE_CMDS:
            opt, args, j = self.read_args(s, j, 1)
            j2 = skip_ws(s, j)
            if j2 < n and s[j2] == "{" and opt is not None:
                # \cite[pre][post]{key}
                pass
            out.append(self.cite(args[0], opt))
            return j
        if bare == "footnote":
            _, args, j = self.read_args(s, j, 1)
            out.append(f'<span class="fn">({self.text(args[0], inline=True)})</span>')
            return j
        if bare == "url":
            _, args, j = self.read_args(s, j, 1, optional=False)
            out.append(f'<a href="{esc(args[0])}" rel="noopener">{esc(args[0])}</a>')
            return j
        if bare == "href":
            _, args, j = self.read_args(s, j, 2, optional=False)
            out.append(f'<a href="{esc(args[0])}" rel="noopener">{self.text(args[1], inline=True)}</a>')
            return j
        if bare == "ensuremath":
            _, args, j = self.read_args(s, j, 1, optional=False)
            out.append(self.m_inline(args[0]))
            return j
        if bare == "item":
            # stray \item outside a list
            out.append("• ")
            return j
        if bare in SYMBOL:
            out.append(SYMBOL[bare])
            return j
        key = "\\" + bare
        if key in self.macros or bare in GREEK or bare in PLAIN_SYM:
            arity = 0
            if key in self.macros:
                found = re.findall(r"#(\d)", self.macros[key])
                arity = max(map(int, found)) if found else 0
            _, args, j2 = self.read_args(s, j, arity, optional=False) if arity else (None, [], j)
            out.append(self.m_inline(key + "".join("{" + a + "}" for a in args)))
            return j2
        STATS["tex_unknown_text_command"] += 1
        STATS["unknown:" + bare] += 1
        out.append(f'<span class="tex-raw">\\{esc(name)}</span>')
        return j

    def env(self, name: str, body: str, opt: str) -> str:
        base = name.rstrip("*")
        if name in MATH_ENVS:
            return self.m_display(body, name, opt)
        if base in ("aligned", "gathered", "cases", "array", "pmatrix", "bmatrix", "matrix", "CD", "split"):
            return self.m_display(f"\\begin{{{name}}}{body}\\end{{{name}}}")
        if base in LIST_ENVS:
            return self.list_env(base, body, opt)
        if base in ("quote", "quotation", "center", "flushleft", "itshape", "minipage", "proof", "remark", "small"):
            return f'{BLOCK_OPEN}<div class="tex-env">{self.blocks(body)}</div>{BLOCK_CLOSE}'
        STATS["tex_unrenderable_env"] += 1
        STATS["env:" + name] += 1
        return f'{BLOCK_OPEN}<pre class="tex-fallback">{esc(chr(92) + "begin{" + name + "}" + body + chr(92) + "end{" + name + "}")}</pre>{BLOCK_CLOSE}'

    def list_env(self, kind: str, body: str, opt: str) -> str:
        items = []
        depth = 0
        k = 0
        starts = []
        while k < len(body):
            if body.startswith("\\begin{", k):
                depth += 1
                k += 7
                continue
            if body.startswith("\\end{", k):
                depth -= 1
                k += 5
                continue
            if body[k] == "{":
                _, k = brace_group(body, k)
                continue
            if depth == 0 and re.match(r"\\item\b", body[k:]):
                starts.append(k)
                k += 5
                continue
            k += 1
        for a, b in zip(starts, starts[1:] + [len(body)]):
            seg = body[a + 5:b]
            lab = None
            j = skip_ws(seg, 0)
            if j < len(seg) and seg[j] == "[":
                lab, j2 = brace_group(seg, j, "[", "]")
                seg = seg[j2:]
            items.append((lab, seg))
        style = "decimal"
        o = opt or ""
        if "roman" in o or re.search(r"\(?i\)", o):
            style = "roman"
        elif "Alph" in o or re.search(r"\(?A\)", o):
            style = "Alpha"
        elif "alph" in o or re.search(r"\(?a\)", o):
            style = "alpha"
        paren = "(" in o
        lis = []
        for idx, (lab, seg) in enumerate(items, 1):
            if lab is not None:
                label = self.text(lab, inline=True)
            elif kind == "itemize":
                label = "•"
            else:
                core = {"roman": roman(idx), "alpha": chr(96 + idx), "Alpha": chr(64 + idx)}.get(style, str(idx))
                label = f"({core})" if paren or style != "decimal" else f"{core}."
            lis.append(f'<li><span class="li-lab">{label}</span><div class="li-body">{self.blocks(seg)}</div></li>')
        tag = "ul" if kind == "itemize" else "ol"
        return f'{BLOCK_OPEN}<{tag} class="tex-list">{"".join(lis)}</{tag}>{BLOCK_CLOSE}'


def _top_level(t: str) -> str:
    """Text of t outside any \\begin...\\end environment."""
    out = []
    depth = 0
    for tok in re.split(r"(\\begin\{[^}]*\}|\\end\{[^}]*\})", t):
        if tok.startswith("\\begin{"):
            depth += 1
        elif tok.startswith("\\end{"):
            depth -= 1
        elif depth == 0:
            out.append(tok)
    return "".join(out)


def cite_label(r, key):
    if not r:
        return key
    authors = clean_ref_text(r.get("authors") or "")
    year = r.get("year") or ""
    if authors:
        names = [a.strip() for a in re.split(r"\s+and\s+", authors) if a.strip()]
        surn = []
        for a in names:
            if "," in a:
                surn.append(a.split(",")[0].strip())
            else:
                surn.append(a.split()[-1] if a.split() else a)
        if len(surn) > 2:
            lab = surn[0] + " et al."
        else:
            lab = " and ".join(surn)
        return f"{lab}, {year}".strip(", ")
    return key


# ------------------------------------------------------------- Lean highlight

def lean_lines(text: str) -> list[str]:
    """Highlighted lines without links, for snippets and cards: Lean's own
    tokenizer in scripts/lean_render.py (nested comments, Lean's identifier
    characters), each line hanging from its own indentation when it wraps."""
    import lean_render
    return lean_render.lines_html(text)


def lean_key_ranges(text: str, theorem_names: list[str]):
    """Line ranges (0-based, inclusive) that state the checked theorem, plus the
    definition its type names when that type is a single defined word."""
    lines = text.split("\n")
    ranges = []
    for full in theorem_names:
        sh = full.split(".")[-1]
        pat = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable)\s+)*(?:theorem|lemma)\s+" + re.escape(sh) + r"(?=[\s:({\[]|$)")
        idx = next((k for k, l in enumerate(lines) if pat.match(l)), None)
        if idx is None:
            continue
        end = idx
        while end < len(lines) - 1 and ":=" not in lines[end] and end - idx < 40:
            end += 1
        nxt = end + 1
        while nxt < len(lines) and not lines[nxt].strip():
            nxt += 1
        if nxt < len(lines) and lines[nxt].strip() in ("sorry", "by sorry", "exact sorry"):
            end = nxt
        sig = " ".join(lines[idx:end + 1])
        sig = sig.split(":=")[0]
        depth = 0
        colon = None
        for k, ch in enumerate(sig):
            if ch in "([{⦃":
                depth += 1
            elif ch in ")]}⦄":
                depth -= 1
            elif ch == ":" and depth == 0 and k > 0:
                colon = k
                break
        typ = sig[colon + 1:].strip() if colon else ""
        if re.fullmatch(r"[\w.'’]+", typ):
            dname = typ.split(".")[-1]
            dpat = re.compile(r"^\s*(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable)\s+)*(?:def|abbrev)\s+" + re.escape(dname) + r"(?=[\s:({\[]|$)")
            didx = next((k for k, l in enumerate(lines) if dpat.match(l)), None)
            if didx is not None:
                dend = didx
                while dend + 1 < len(lines) and lines[dend + 1].strip() and not re.match(r"^(?:theorem|lemma|def|abbrev|structure|end|namespace|/-|--|axiom|noncomputable|instance)\b", lines[dend + 1].strip()) and dend - didx < 30:
                    dend += 1
                ranges.append((didx, dend))
        ranges.append((idx, end))
    for k, l in enumerate(lines):
        if re.match(r"^\s*axiom\s", l):
            ranges.append((k, k))
    ranges = sorted(set(ranges))
    merged = []
    for a, b in ranges:
        if merged and a <= merged[-1][1] + 1:
            merged[-1] = (merged[-1][0], max(b, merged[-1][1]))
        else:
            merged.append((a, b))
    return merged


# ----------------------------------------------------------- contributions


def _contrib_parsers():
    """The contributor kit's own stdlib YAML reader (scripts/check_contributions.py)."""
    try:
        sys.path.insert(0, str(ROOT / "scripts"))
        import check_contributions as cc  # noqa: E402
        return cc.parse_yaml, cc.split_frontmatter
    except Exception as exc:  # pragma: no cover
        warn(f"could not import scripts/check_contributions.py ({exc}); contributions were not read")
        return None, None
    finally:
        if sys.path and sys.path[0] == str(ROOT / "scripts"):
            sys.path.pop(0)


def _names(v):
    """Names from a person record or a list of them, falling back to the GitHub handle."""
    out = []
    for p in (v if isinstance(v, list) else [v]):
        if isinstance(p, dict):
            name = p.get("name") or p.get("github")
            if name and not str(name).startswith("[replace"):
                out.append(str(name))
        elif isinstance(p, str) and p and not p.startswith("[replace"):
            out.append(p)
    return out


def _str_list(v):
    if isinstance(v, list):
        return [str(x) for x in v if x is not None and not str(x).startswith("[replace")]
    return [str(v)] if v and not str(v).startswith("[replace") else []


def _clean(v):
    """A frontmatter value as text, or None while it is still template text."""
    if v is None:
        return None
    s = str(v).strip()
    return None if (not s or s.startswith("[replace")) else s


def _reader_scope_line(body: str):
    """The '**Reader and scope:** ...' line the explanation template asks for."""
    m = re.search(r"^\*\*Reader and scope:?\*\*:?\s*(.+)$", body or "", re.M)
    return _clean(m.group(1)) if m else None


def load_contributions(base: Path | None = None):
    c = {"explanations": defaultdict(list), "checks": defaultdict(list), "credits": defaultdict(list), "replays": defaultdict(list)}
    base = base or CONTRIB_BASE
    if not base.exists():
        return c
    parse_yaml, split_frontmatter = _contrib_parsers()
    if not parse_yaml:
        return c
    for p in sorted(base.rglob("*")):
        if not p.is_file() or p.name.startswith(".") or "_templates" in p.parts:
            continue
        rel = p.relative_to(base).parts
        if len(rel) < 2 or rel[0] not in c:
            continue
        kind, target = rel[0], rel[1]
        body = ""
        try:
            text = p.read_text(encoding="utf-8").lstrip("\ufeff").replace("\r\n", "\n")
            if p.suffix == ".json":
                meta = json.loads(text)
            elif p.suffix in (".md", ".markdown"):
                y, first, body, _ = split_frontmatter(text)
                parsed = parse_yaml(y, first)
                meta = parsed[0] if isinstance(parsed, tuple) else (parsed or {})
            else:
                continue
        except Exception as exc:
            warn(f"contribution {p} could not be read ({exc})")
            continue
        if not isinstance(meta, dict):
            continue
        if kind == "explanations":
            names = _names(meta.get("authors"))
            reviewers = _names(meta.get("reviewers"))
        elif kind == "checks":
            names = _names(meta.get("reviewer"))
            reviewers = []
        else:
            names = _names(meta.get("contributor"))
            reviewers = []
        handle = rel[2] if kind == "explanations" and len(rel) > 3 else p.stem
        rec = {
            "names": names or [handle], "name": ", ".join(names or [handle]), "reviewers": reviewers,
            "status": str(meta.get("status") or "").lower(), "title": _clean(meta.get("title")),
            "verdict": (lambda v: None if (v is None or str(v).startswith("[replace")) else str(v).replace("-", " "))(meta.get("verdict") or meta.get("result") or meta.get("relation")),
            "path": "/".join(("contributions",) + rel), "date": str(meta.get("date") or ""),
            "handle": handle, "upstream_commit": _clean(meta.get("upstream_commit")),
            "statements": _str_list(meta.get("statements") or meta.get("statement")),
            "manuscripts": _str_list(meta.get("manuscripts") or meta.get("manuscript")),
            "paper_statement": _clean(meta.get("paper_statement")),
        }
        if kind == "explanations":
            # Keep the explanation itself, so a reader can reach it: the Markdown body,
            # the folder its figures sit in, and the stated reader and scope.
            rec["body"] = body
            rec["folder"] = p.parent
            rec["reader"] = _clean(meta.get("reader") or meta.get("audience"))
            rec["scope"] = _clean(meta.get("scope"))
            rec["reader_scope"] = _reader_scope_line(body)
        c[kind][target].append(rec)
    return c


CONTRIB_BASE = ROOT / "contributions"
CONTRIB = load_contributions()

def load_coverage():
    """The draft scope reading (curated/scope_coverage.json) and the commit it was made at."""
    p = ROOT / "curated" / "scope_coverage.json"
    if not p.exists():
        return {}, None
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        warn(f"curated/scope_coverage.json could not be read ({exc})")
        return {}, None
    rows = raw.get("statements", raw.get("rows", raw)) if isinstance(raw, dict) else raw
    out = {}
    if isinstance(rows, dict):
        for k, v in rows.items():
            if isinstance(v, dict):
                out[k] = v
    elif isinstance(rows, list):
        for v in rows:
            if isinstance(v, dict) and (v.get("statement") or v.get("id")):
                out[v.get("statement") or v.get("id")] = v
    return out, (raw.get("upstream_commit") if isinstance(raw, dict) else None)


COVERAGE, _COVERAGE_COMMIT = load_coverage()
SCOPE_SUMMARY = SUMMARY.get("scope_coverage") or {}
# The draft scope reading is shown only when it was made at the pinned commit. When
# summary.json marks it stale, or its own pin differs, the site shows no scope colours
# and says why, instead of colouring the map from a reading of other files.
COVER_STALE = bool(SCOPE_SUMMARY.get("stale")) or bool(_COVERAGE_COMMIT and _COVERAGE_COMMIT != COMMIT) \
    or bool(SCOPE_SUMMARY.get("upstream_commit") and SCOPE_SUMMARY.get("upstream_commit") != COMMIT)
if COVER_STALE:
    warn("the draft scope reading does not match the pinned commit; scope colours and labels are withheld")


def load_community():
    p = ROOT / "curated" / "community.json"
    empty = {"efforts": {}, "by_family": {}, "by_statement": {}, "efforts_by_family": {}, "list": [], "findings": []}
    if not p.exists():
        return empty
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        warn(f"curated/community.json could not be read ({exc})")
        return empty
    eff = {e["id"]: e for e in raw.get("efforts", [])}
    by_family, by_statement, efforts_by_family = {}, {}, {}
    for f in raw.get("findings", []):
        if f.get("effort") not in eff:
            continue
        by_family.setdefault(f.get("family"), []).append(f)
        if f.get("statement"):
            by_statement.setdefault(f["statement"], []).append(f)
    for e in eff.values():
        for fam in e.get("families") or []:
            efforts_by_family.setdefault(fam, []).append(e)
    return {"efforts": eff, "by_family": by_family, "by_statement": by_statement,
            "efforts_by_family": efforts_by_family, "list": list(eff.values()), "findings": raw.get("findings", [])}


COMMUNITY = load_community()


def credit_names(e):
    return ", ".join((a.get("name") or a.get("handle") or "") for a in (e.get("authors") or []) if (a.get("name") or a.get("handle")))


def finding_item(f, root):
    e = COMMUNITY["efforts"].get(f["effort"], {})
    kind = C("community.finding_kinds").get(f["kind"], f["kind"]) if isinstance(C("community.finding_kinds"), dict) else f["kind"]
    who = credit_names(e)
    return (f'<li class="cfind"><span class="pill pill--support">{esc(kind)}</span> {esc(f["summary"])} '
            f'<span class="muted small">{esc(who)}{", " if who else ""}{esc(e.get("name", ""))}, {esc(f["date"])}</span> '
            f'<a class="ext small" href="{esc(f["url"])}" rel="noopener">{esc(C("community.source"))}</a></li>')


SOURCES = {x["id"]: x for x in SUMMARY.get("sources", []) if x.get("id")}


def sourced(f, field):
    vals = (f.get("sourced") or {}).get(field) or []
    return vals[0] if vals else None


def sourced_all(obj, field):
    """Every source's value for a field, in source order, as [{value, source}]."""
    return (obj.get("sourced") or {}).get(field) or []


def source_credit(source_id):
    src = SOURCES.get(source_id) or {}
    return src.get("credit") or src.get("name") or source_id


def independent_reruns_html(stmt, root):
    """Other people's re-runs of this challenge, each in its own words, credited, dated and linked."""
    items = []
    for v in sourced_all(stmt, "replay"):
        rv = v["value"]
        holes = (rv.get("holes") or {}).get("text")
        when = f', {esc(date_words(rv["date"]))}' if rv.get("date") else ""
        items.append(f'<li><p>{ctext(rv["text"])}{(" " + ctext(holes)) if holes else ""}</p>'
                     f'<p class="small muted">{source_link(v["source"], root)}{when}. '
                     f'<a class="ext" href="{esc(rv["url"])}" rel="noopener">{esc(C("sources.record_link"))}</a></p></li>')
    if not items:
        return ""
    return (f'<div class="reruns"><h3 class="h3">{esc(C("statement.reruns_heading"))}</h3>'
            f'<p class="intro small">{ctext(C("statement.reruns_intro"))}</p><ul class="cfinds">{"".join(items)}</ul></div>')


def build_glossary():
    """The glossary page: every term pages link with [[id|text]], grouped by first letter."""
    rel = "glossary.html"
    terms = sorted(GLOSSARY.values(), key=lambda t_: t_["term"].lower())
    groups = {}
    for t_ in terms:
        groups.setdefault(t_["term"][0].upper(), []).append(t_)
    blocks = "".join(
        f'<section class="gloss__group" aria-labelledby="g-{L}"><h2 class="h3" id="g-{L}">{L}</h2><dl class="gloss">'
        + "".join(f'<div class="gloss__row" id="{esc(t_["id"])}"><dt>{esc(t_["term"])}</dt><dd>{esc(t_["short"])}</dd></div>' for t_ in group)
        + "</dl></section>" for L, group in groups.items())
    body = f"""<div class="frame page page--narrow">
<header class="phead">
 <h1 class="phead__title">{esc(C('glossary.title'))}</h1>
 <p class="lede">{esc(C('glossary.lede'))}</p>
</header>
{blocks}
</div>"""
    write_page(rel, page(rel, C("glossary.title"), C("glossary.lede"), body, current="glossary"))


def source_link(source_id, root):
    src = SOURCES.get(source_id) or COMMUNITY["efforts"].get(source_id) or {}
    name = src.get("name") or source_id
    return f'<a href="{root}sources.html#src-{esc(source_id)}">{esc(name)}</a>'


def findings_for(fid=None, sid=None, kinds=None):
    pool = COMMUNITY["by_statement"].get(sid, []) if sid else COMMUNITY["by_family"].get(fid, [])
    return [f for f in pool if (kinds is None or f["kind"] in kinds)]


def findings_list(finds, root):
    if not finds:
        return ""
    return '<ul class="cfinds">' + "".join(finding_item(f, root) for f in sorted(finds, key=lambda x: x["date"])) + "</ul>"


def adopted_list_html(adopted):
    """What the atlas took from a source: ideas re-implemented, or code and data reused under licence."""
    if not adopted:
        return ""
    items = "".join(f'<li>{esc(C("sources.adopted_kind_" + a["kind"]))}: {esc(a["what"])} <span class="muted">({esc(a["where"])})</span></li>' for a in adopted)
    return f'<p class="small"><strong>{esc(C("sources.adopted_heading"))}</strong></p><ul class="small">{items}</ul>'


def cover_class(sid):
    """The draft scope class of one statement, or None when no classification is recorded."""
    if COVER_STALE:
        return None
    row = COVERAGE.get(sid)
    cls = str((row or {}).get("class") or "")
    if cls == "weaker-form":
        cls = "weaker"
    return cls or None


def cover_label(cls):
    return COPY["statement"]["coverage_classes"].get(cls, cls.replace("-", " ")) if cls else C("statement.coverage_unclassified")


def coverage_html(sid, compact=False):
    """OpenAI's own note on what this statement covers, quoted, then the atlas's AI draft
    reading of that note as one quiet line. A draft is never styled as a verdict."""
    if COVER_STALE:
        return f'<div class="scope"><p class="scope__src">{esc(C("statement.coverage_stale"))}</p></div>'
    row = COVERAGE.get(sid)
    if not row:
        return ""
    cls = cover_class(sid)
    quote = row.get("scope_quote") or row.get("quote") or ""
    fam = row.get("family")
    note_url = f"{BASE_BLOB}lean/docs/{fam}.md" if fam else None
    check = issue_url("check", C("statement.coverage_check_title", id=sid), statement=sid, upstream_commit=COMMIT)
    parts = []
    if quote:
        foot = f'<footer>{esc(C("statement.coverage_quote_by"))} <a class="ext" href="{esc(note_url)}" rel="noopener">{esc(C("statement.coverage_source"))}</a></footer>' if note_url else ""
        parts.append(f'<p class="scope__src">{esc(C("statement.note_heading"))}</p>'
                     f'<blockquote class="quote md-math"><p>\u201c{esc(quote)}\u201d</p>{foot}</blockquote>')
    if cls:
        parts.append(f'<p class="scope__draft">{esc(C("statement.draft_line", cls=cover_label(cls)[0].lower() + cover_label(cls)[1:]))} '
                     f'<a class="ext" href="{esc(check)}" rel="noopener">{esc(C("statement.coverage_check"))}</a></p>')
    return ('<div class="scope">' + "".join(parts) + "</div>") if parts else ""


COVER_RANK = {"headline": 4, "headline-part": 3, "consequence": 2, "weaker": 2, "supporting": 1}
COVER_GRADE = {4: "full", 3: "part", 2: "less", 1: "support"}


def fam_cover_grade(f):
    """(grade, flag) for a family's map colour. The grade is the strongest classified
    statement: full, part, less or support; 'unclear' when the only classified
    statements are unclear; 'unclassified' when none is classified; 'none' with no
    Lean statement; 'stale' when the reading does not match the pinned commit. The
    flag is set when the family's statements differ in class or are not all classified,
    so one colour never stands for every statement silently."""
    if not f["statements"]:
        return "none", False
    if COVER_STALE:
        return "stale", False
    classes = [cover_class(s) for s in f["statements"]]
    known = [COVER_RANK[c] for c in classes if c in COVER_RANK]
    if known:
        grade = COVER_GRADE[max(known)]
    elif "unclear" in classes:
        grade = "unclear"
    else:
        grade = "unclassified"
    return grade, len(set(classes)) > 1


def family_exposition_status(fid):
    """'reviewed' when a reviewed explanation is recorded (of whatever scope it states),
    'progress' when only drafts are recorded, 'none' otherwise."""
    ex = CONTRIB["explanations"].get(fid, [])
    if any(e["status"] == "reviewed" for e in ex):
        return "reviewed", ex
    if ex:
        return "progress", ex
    return "none", []


def explanation_rel(e, fid):
    return f"explanations/{fid}/{slugify(e['handle']) or 'explanation'}.html"


def reviewed_explanations(fid):
    return [e for e in CONTRIB["explanations"].get(fid, []) if e["status"] == "reviewed"]


# ---------------------------------------------------------------- relations

FAM_CITES = defaultdict(list)       # fid -> ordered unique family ids it cites
FAM_CITED_BY = defaultdict(list)
for f in FAMILIES:
    for slug in f["manuscripts"]:
        m = MS.get(slug)
        if not m:
            continue
        for r in m.get("rests_on") or []:
            tf = r.get("family")
            if tf and tf != f["id"] and tf not in FAM_CITES[f["id"]]:
                FAM_CITES[f["id"]].append(tf)
        for c in m.get("cited_by_in_collection") or []:
            cf = MS.get(c, {}).get("family")
            if cf and cf != f["id"] and cf not in FAM_CITED_BY[f["id"]]:
                FAM_CITED_BY[f["id"]].append(cf)


def fam_cited_by_ms(f):
    """Distinct current manuscripts outside the result that cite one of its manuscripts."""
    out = set()
    for slug in f["manuscripts"]:
        for c in (MS.get(slug) or {}).get("cited_by_in_collection") or []:
            if c not in f["manuscripts"] and MS.get(c, {}).get("status") == "current":
                out.add(c)
    return len(out)


def fam_max_vocab(f):
    v = [ST[s]["vocabulary_count"] for s in f["statements"] if s in ST]
    return max(v) if v else None


def fam_has_main(f):
    return any(ST[s]["main_result"] for s in f["statements"] if s in ST)


def backend_target(alias: str) -> dict | None:
    """Statement Map's contribution target for a reader id ("f:159", "l:ErdosReciprocal"):
    the exact content a contribution concerns, with a fingerprint of its text."""
    import backend
    b = backend.load()
    return b.target(alias) if b else None


def issue_url(template_key: str, title: str, **fields) -> str:
    name = CFG["issue_templates"][template_key]
    params = {"template": f"{name}.yml", "title": title}
    if "target" not in fields:
        # The form records the exact version of what the reader saw, so a review stays
        # tied to that text if the release changes it.
        alias = ("f:" + fields["family"]) if fields.get("family") else (("l:" + fields["statement"]) if fields.get("statement") else None)
        t = backend_target(alias) if alias else None
        if t:
            fields = {**fields, "target": f'{t["id"]} {t["fingerprint"]}'}
    for k, v in CFG.get("issue_prefill", {}).get(name, {}).items():
        try:
            val = v.format(**fields)
        except KeyError:
            continue
        if val:
            params[k] = val
    return f"{REPO}/issues/new?{urlencode(params, quote_via=quote)}"


# -------------------------------------------------------------- page shell

PAGES: list[tuple[str, str]] = []   # (rel path, lastmod) for the sitemap

MARK_SVG = (
    '<svg class="mark" viewBox="0 0 24 24" aria-hidden="true" focusable="false">'
    '<rect x="2" y="2" width="11" height="12" class="mk-a"/><rect x="14" y="2" width="8" height="7" class="mk-b"/>'
    '<rect x="14" y="10" width="8" height="12" class="mk-c"/><rect x="2" y="15" width="5" height="7" class="mk-c"/>'
    '<rect x="8" y="15" width="5" height="7" class="mk-d"/></svg>'
)


GENERIC_OG = "assets/social-card.png"


def og_meta(og_url: str, alt: str) -> str:
    return (f'<meta property="og:image" content="{esc(og_url)}">\n'
            '<meta property="og:image:width" content="1200">\n'
            '<meta property="og:image:height" content="675">\n'
            f'<meta property="og:image:alt" content="{esc(alt)}">\n'
            '<meta name="twitter:card" content="summary_large_image">\n'
            f'<meta name="twitter:image" content="{esc(og_url)}">\n'
            f'<meta name="twitter:image:alt" content="{esc(alt)}">')


def generic_og_meta() -> str:
    return og_meta(BASE_URL + GENERIC_OG, C("social.card_alt"))


def head(rel: str, title: str, description: str, *, og_block: str | None = None, noindex=False,
         extra_head: str = "", page_type="website") -> str:
    depth = rel.count("/")
    root = "../" * depth
    canonical = BASE_URL + ("" if rel == "index.html" else rel)
    full_title = title if title == C("site.name") else f"{title} | {C('site.name')}"
    og = og_block or generic_og_meta()
    desc = esc(short(description, 300))
    robots = '<meta name="robots" content="noindex">' if noindex else ""
    return f"""<!doctype html>
<html lang="en-GB">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{esc(full_title)}</title>
<meta name="description" content="{desc}">
<link rel="canonical" href="{esc(canonical)}">
{robots}
<meta name="color-scheme" content="light dark">
<meta name="theme-color" content="#f8f0e2" media="(prefers-color-scheme: light)">
<meta name="theme-color" content="#1c1526" media="(prefers-color-scheme: dark)">
<meta property="og:type" content="{page_type}">
<meta property="og:site_name" content="{esc(C('site.name'))}">
<meta property="og:title" content="{esc(title)}">
<meta property="og:description" content="{desc}">
<meta property="og:url" content="{esc(canonical)}">
{og}
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{desc}">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="preload" href="{root}assets/fonts/plectis-serif.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{root}assets/fonts/plectis-sans.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{root}{KATEX_DIR}/katex.min.css">
<link rel="stylesheet" href="{root}assets/atlas.css">
<script>(function(){{try{{var t=localStorage.getItem('atlas-theme');if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();</script>
<script defer src="{root}{KATEX_DIR}/katex.min.js"></script>
<script defer src="{root}{KATEX_DIR}/contrib/auto-render.min.js"></script>
<script defer src="{root}assets/atlas.js"></script>
{extra_head}
</head>"""


# The front door is the release universe (scripts/build_universe.py writes index.html).
# Numbers lives in the footer and in the home page's bands.
NAV = [("index.html", "map"), ("explain.html", "explain"), ("statements.html", "statements"),
       ("sources.html", "sources"), ("glossary.html", "glossary"),
       ("contribute.html", "contribute"), ("about.html", "about")]


def header(rel: str, current: str | None) -> str:
    root = "../" * rel.count("/")
    links = []
    for href, key in NAV:
        cur = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{root}{href}"{cur}>{esc(C("nav." + key))}</a>')
    return f"""<body data-root="{root}" data-copied="{esc(C('words.copied'))}" data-copy-failed="{esc(C('words.copy_failed'))}" data-tex-failed="{esc(C('words.tex_failed'))}">
<a class="skip" href="#main">{esc(C('site.skip'))}</a>
<header class="top">
 <div class="frame top__in">
  <a class="brand" href="{root}index.html" aria-label="{esc(C('nav.brand_label'))}">{MARK_SVG}<span class="brand__name" translate="no">{esc(C('site.name'))}</span></a>
  <nav class="nav" aria-label="{esc(C('nav.site_nav'))}">{''.join(links)}</nav>
  <div class="top__tools">
   <button class="search-open" type="button" aria-haspopup="dialog" aria-controls="search-dialog"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M12.6 12.6 17 17"/></svg><span class="search-open__label">{esc(C('nav.search'))}</span><kbd>/</kbd></button>
   <button class="theme-toggle" type="button" data-label-dark="{esc(C('nav.theme_dark'))}" data-label-light="{esc(C('nav.theme_light'))}" aria-label="{esc(C('nav.theme_dark'))}"><span class="theme-toggle__thumb" aria-hidden="true"></span></button>
  </div>
 </div>
</header>
<dialog class="search" id="search-dialog" aria-label="{esc(C('nav.search'))}">
 <form method="dialog" class="search__form" role="search">
  <input class="search__input" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(C('nav.search_placeholder'))}" aria-label="{esc(C('nav.search_placeholder'))}" role="combobox" aria-expanded="true" aria-controls="search-results" aria-autocomplete="list">
 </form>
 <ul class="search__results" id="search-results" role="listbox" aria-label="{esc(C('nav.search'))}"></ul>
 <p class="search__empty" hidden>{esc(C('nav.search_empty'))}</p>
 <p class="search__failed" hidden>{esc(C('nav.search_failed'))} <a href="{root}index.html#catalogue">{esc(C('nav.search_failed_link'))}</a></p>
</dialog>"""


def footer(rel: str) -> str:
    root = "../" * rel.count("/")
    up = CFG["upstream_repo"]
    return f"""<footer class="foot">
 <div class="frame foot__in">
  <div class="foot__lead">
   <p class="foot__name">{MARK_SVG}<span translate="no">{esc(C('site.name'))}</span></p>
   <p>{esc(C('site.independence', author=CFG['author']))}</p>
   <p>{esc(C('site.licence', upstream='openai/math', commit_short=COMMIT_SHORT))}</p>
  </div>
  <ul class="foot__links">
   <li><a href="{root}about.html">{esc(C('nav.about'))}</a></li>
   <li><a href="{root}numbers.html">{esc(C('nav.numbers'))}</a></li>
   <li><a href="{root}citations-within.html">{esc(C('citations_within.title'))}</a></li>
   <li><a href="{root}references-outside.html">{esc(C('references_outside.title'))}</a></li>
   <li><a href="{root}contribute.html">{esc(C('nav.contribute'))}</a></li>
   <li><a class="ext" href="{esc(REPO)}" rel="noopener">{esc(C('site.repo_link'))}</a></li>
   <li><a class="ext" href="{esc(up)}/tree/{COMMIT}" rel="noopener">{esc(C('site.upstream_link'))}</a></li>
  </ul>
 </div>
</footer>
</body>
</html>
"""


def write_page(rel: str, html_text: str, index=True):
    path = OUT / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    # glossary links made by ctext() learn the page's depth here
    html_text = html_text.replace("__ROOT__", "../" * rel.count("/"))
    path.write_text(html_text, encoding="utf-8")
    if index:
        PAGES.append(rel)
    STATS["pages"] += 1


def page(rel, title, description, body, *, current=None, og_block=None, noindex=False, extra_head="",
         page_type="website", main_class=""):
    h = head(rel, title, description, og_block=og_block, noindex=noindex, extra_head=extra_head, page_type=page_type)
    return f'{h}\n{header(rel, current)}\n<main id="main" class="{main_class}" tabindex="-1">\n{body}\n</main>\n{footer(rel)}'


def trail(root, items):
    parts = [f'<a href="{root}index.html">{esc(C("nav.trail_home"))}</a>']
    for label, href in items:
        if href:
            parts.append(f'<a href="{href}">{label}</a>')
        else:
            parts.append(f'<span aria-current="page">{label}</span>')
    return '<nav class="trail" aria-label="' + esc(C("nav.breadcrumb")) + '">' + '<span class="trail__sep" aria-hidden="true">/</span>'.join(parts) + "</nav>"


def json_script(id_, obj):
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" id="{id_}">{s}</script>'


def status_label(status):
    return {"current": C("words.status_current"), "withdrawn": C("words.status_withdrawn"),
            "previous-edition": C("words.status_previous")}.get(status, status)


def fam_title_html(f):
    return f'<span class="tex-auto">{rich(f["title"])}</span>'


def ms_title_html(m):
    return f'<span class="tex-auto">{rich(m["title"])}</span>'


def pdf_button(m, cls="btn btn--ghost"):
    return (f'<a class="{cls} ext" href="{esc(m["pdf_url"])}" rel="noopener" '
            f'aria-label="{esc(C("words.pdf_label", title=tex_plain(m["title"])))}">{esc(C("words.pdf"))}</a>')


# --------------------------------------------------------- statements in TeX


def render_paper_statement(m, st, root, conv: TexConv, anchor_prefix="st"):
    body = conv.blocks(st["text"])
    title = f' <span class="stmt__title">({conv.text(st["title"], inline=True)})</span>' if st.get("title") else ""
    src_url = f'{BASE_BLOB}preprints/{m["id"]}/{st["file"]}#L{st["line"]}'
    loc_sec = C("words.appendix") if st.get("appendix") else C("words.section", n=st["section"])
    sec_title = f', {esc(st["section_title"])}' if st.get("section_title") else ""
    aid = f'{anchor_prefix}-{slugify(m["id"])[:40]}-{slugify(st.get("label") or str(st["line"]))}'
    raw = st["text"]
    in_paper = paper_statement_href(m["id"], st, root)
    in_paper_html = f'<a href="{esc(in_paper)}">{esc(C("words.read_in_paper"))}</a>' if in_paper else ""
    return f"""<figure class="stmt" id="{aid}" data-macros="{esc(m['id'])}">
 <figcaption class="stmt__head"><span class="stmt__kind">{esc(st['display'])}</span>{title}</figcaption>
 <div class="stmt__body">{body}</div>
 <div class="stmt__foot">
  <span class="stmt__loc">{esc(loc_sec)}{sec_title}</span>
  {in_paper_html}
  <a class="ext" href="{esc(src_url)}" rel="noopener">{esc(C('words.source_line', line=st['line']))}</a>
  <details class="texsrc"><summary>{esc(C('words.tex_source'))}</summary><div class="texsrc__box"><button class="copy" type="button" data-copy-next>{esc(C('words.copy'))}</button><pre><code>{esc(raw)}</code></pre></div></details>
 </div>
</figure>"""


def macros_script(ids):
    obj = {}
    for i in ids:
        m = MS.get(i)
        if m and m.get("tex"):
            obj[i] = (m["tex"].get("macros") or {})
    return json_script("tex-macros", obj)


def headline_statements(m):
    return [s for s in (m.get("statements") or []) if s.get("headline")]


STOP = set("the and for that with this every each from which have there their then than into such are its has where when also being over under only some all any can not one two three both these those whose this into onto them they our we us is be by of to in on as at an a or if it".split())


def words_of(s: str) -> set:
    s = re.sub(r"\\[A-Za-z]+", " ", s or "")
    s = re.sub(r"([a-z])([A-Z])", r"\1 \2", s)
    return {w for w in re.findall(r"[a-zA-Zőöüéè]{4,}", s.lower()) if w not in STOP}


# A candidate must share at least this many distinct content words (four letters or
# more, stop words removed) with the Lean labels, names, docstrings and scope note.
# At one or two shared words the overlap is the field's common vocabulary ('graph',
# 'prime', 'bound'), which every headline statement of the same paper also carries, so
# it cannot single one out; a probe over the 416 challenge files at the pinned commit
# found 23 pairings at that level. Three is the smallest count at which the chosen
# statement shares something more specific than the subject. The pairing also abstains
# when two candidates tie for the best score, since overlap then does not decide.
PAIR_MIN_SHARED = 3


def pair_statement(stmt):
    """A candidate paper statement for a Lean challenge, chosen by word overlap with
    the Lean notes, or (None, None, reason) when the overlap is too weak to choose.
    This is a heuristic for finding the passage to read; it is never a review."""
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    lean_words = words_of(" ".join(stmt.get("labels") or []) + " " + " ".join(stmt.get("docstrings") or []) + " " + stmt["id"]
                          + " " + " ".join(n.split(".")[-1] for n in stmt["comparator"]["theorem_names"]))
    scope_words = words_of((fam or {}).get("lean_doc", {}).get("scope", "") if fam and fam.get("lean_doc") else "")
    scored = []
    for slug in stmt.get("papers") or []:
        m = MS.get(slug)
        if not m:
            continue
        for st in headline_statements(m):
            w = words_of((st.get("title") or "") + " " + st["text"])
            shared = (w & lean_words) | (w & scope_words)
            score = 3 * len(w & lean_words) + len(w & scope_words) + (1 if st["kind"] == "theorem" else 0)
            scored.append((score, len(shared), m, st))
    if not scored:
        return None, None, "none"
    scored.sort(key=lambda x: -x[0])
    best = scored[0]
    if best[1] < PAIR_MIN_SHARED:
        STATS["pairing_abstained_weak"] += 1
        return None, None, "weak"
    if len(scored) > 1 and scored[1][0] == best[0]:
        STATS["pairing_abstained_tie"] += 1
        return None, None, "tie"
    STATS["pairing_candidate"] += 1
    return best[2], best[3], "candidate"


_HOLE_CACHE = {}


def def_holes(stmt):
    """Definitions Comparator compares by name and type only (definition_names), with
    where OpenAI's library defines each, found in the solution module's folder of the
    pinned checkout when that checkout is present."""
    names = stmt["comparator"].get("definition_names") or []
    if not names:
        return []
    up = (ROOT / CFG["upstream_checkout"]).resolve() if CFG.get("upstream_checkout") else None
    module = stmt["comparator"].get("solution_module") or ""
    folder = "lean/" + "/".join(module.split(".")[:-1]) if module else ""
    found = {}
    if up and folder and (up / folder).is_dir():
        if folder not in _HOLE_CACHE:
            index = {}
            for f in sorted((up / folder).rglob("*.lean")):
                ns = []
                for k, line in enumerate(f.read_text(encoding="utf-8", errors="replace").split("\n"), 1):
                    st = line.strip()
                    m = re.match(r"^namespace\s+(\S+)", st)
                    if m:
                        ns.append(m.group(1))
                        continue
                    m = re.match(r"^end\s+(\S+)", st)
                    if m and ns and ns[-1] == m.group(1):
                        ns.pop()
                        continue
                    m = re.match(r"^(?:@\[[^\]]*\]\s*)*(?:(?:noncomputable|private|protected|partial)\s+)*(?:def|abbrev|structure|class|inductive|opaque)\s+([^\s:({\[]+)", st)
                    if m:
                        full = ".".join(ns + [m.group(1)])
                        index.setdefault(full, (str(f.relative_to(up)), k))
            _HOLE_CACHE[folder] = index
        found = _HOLE_CACHE[folder]
    out = []
    for n_ in names:
        hit = found.get(n_)
        out.append({"name": n_, "short": n_.split(".")[-1],
                    "file": hit[0] if hit else None,
                    "url": (BASE_BLOB + hit[0] + f"#L{hit[1]}") if hit else None})
    return out


# ------------------------------------------------------------------- pages


def lean_snippet_html(stmt, lines_html=None, max_lines=None):
    text = stmt["lean"]
    lines_html = lines_html or lean_lines(text)
    ranges = lean_key_ranges(text, stmt["comparator"]["theorem_names"] or stmt["theorems"][:1])
    out = []
    total = 0
    for k, (a, b) in enumerate(ranges):
        if k:
            out.append('<span class="ln ln--gap" aria-hidden="true">⋮</span>')
        for i in range(a, b + 1):
            if max_lines and total >= max_lines:
                out.append('<span class="ln ln--gap" aria-hidden="true">⋮</span>')
                return "".join(out)
            out.append(f'<span class="ln" data-n="{i + 1}">{lines_html[i] if i < len(lines_html) else ""}</span>')
            total += 1
    return "".join(out)


def kind_word(kind):
    key = "statement.kind_" + kind
    try:
        return C(key)
    except KeyError:
        return C("statement.kind_other")


PURE_MATHLIB = set(SUMMARY.get("lean_statements_pure_mathlib_ids") or [])


def vocab_text(s) -> str:
    """Words for a file's local vocabulary count. 'Imports only Mathlib' is said only
    of the files summary.json lists as importing Mathlib alone with no local vocabulary."""
    v = s["vocabulary_count"]
    if s["id"] in PURE_MATHLIB:
        return C("statement.card_vocab_pure")
    if v == 0:
        return C("statement.card_vocab_zero")
    return C("statement.card_vocab_one") if v == 1 else C("statement.card_vocab", count=v)


def related_list(items, root, fam_self=None):
    """items: list of (slug) manuscripts with statuses."""
    out = []
    for slug, status, has_lean in items:
        m = MS.get(slug)
        if not m:
            continue
        fam = FAM.get(m.get("family") or "")
        fam_link = f' <span class="rel__fam">{esc(C("words.result").capitalize())} <a href="{root}families/{fam["id"]}.html">{fam_title_html(fam)}</a></span>' if fam and fam["id"] != fam_self else ""
        lean = C("words.has_lean") if has_lean else C("words.no_lean")
        out.append(f'<li><a class="rel__title" href="{root}papers/{esc(slug)}.html">{ms_title_html(m)}</a>'
                   f'<span class="rel__meta">{esc(C("family.cites_status", status=status_label(status), lean=lean))}</span>{fam_link}</li>')
    return '<ul class="rel">' + "".join(out) + "</ul>"


def describe_use(u):
    ctx = u.get("context")
    parts = []
    if ctx and ctx.get("kind") == "proof" and ctx.get("of"):
        parts.append(C("family.use_proof", label=ctx["of"]))
    elif ctx and ctx.get("kind") and ctx.get("label"):
        parts.append(C("family.use_statement", kind=ctx.get("display") or ctx["kind"], label=ctx["label"]))
    if u.get("section"):
        parts.append(C("family.use_section", section=tex_plain(u["section"])))
    return ", ".join(parts)


def ref_entry(r):
    authors = clean_ref_text(r.get("authors"))
    title = clean_ref_text(r.get("title"))
    venue = clean_ref_text(r.get("venue"))
    if title or authors:
        main = ""
        if authors:
            main += f'<span class="ref__au">{esc(authors)}</span>'
        if title:
            main += f' <span class="ref__ti">{esc(title)}</span>'
        tail = ", ".join(x for x in [venue, r.get("year")] if x)
        if tail:
            main += f' <span class="ref__ve">{esc(tail)}</span>'
    else:
        main = f'<span class="ref__tx">{esc(clean_ref_text(r.get("text") or r["key"]))}</span>'
    links = []
    if r.get("doi"):
        links.append(f'<a class="ext" href="https://doi.org/{esc(r["doi"])}" rel="noopener">DOI</a>')
    if r.get("arxiv"):
        links.append(f'<a class="ext" href="https://arxiv.org/abs/{esc(r["arxiv"])}" rel="noopener">arXiv</a>')
    uses = []
    seen = set()
    for u in r.get("uses") or []:
        d = describe_use(u)
        if d and d not in seen:
            seen.add(d)
            uses.append(d)
    use_html = f'<span class="ref__use">{esc(C("family.used_in", where="; ".join(uses[:4])))}</span>' if uses else ""
    return f'<li class="ref">{main} {" ".join(links)}{use_html}</li>'


# ------------------------------------------------- contributed Markdown, safely

IMG_EXT = {".png", ".jpg", ".jpeg", ".gif", ".webp", ".svg"}
# Maths is kept as escaped TeX for the client renderer: $$...$$, \[...\], \(...\), $...$.
_MD_MATH = re.compile(r"\$\$.+?\$\$|\\\[.+?\\\]|\\\(.+?\\\)|(?<![\\$])\$(?=\S)[^$\n]*?[^\s\\]\$|(?<![\\$])\$[^\s$\\]\$", re.S)


def safe_href(url: str, base: str):
    """An href for a contributed link, or None. Only http(s), mailto, in-page anchors
    and plain relative paths (resolved against base) survive; javascript:, data: and
    every other scheme are dropped."""
    u = (url or "").strip()
    if re.match(r"^(?:https?:|mailto:)", u, re.I):
        return u
    if u.startswith("#"):
        return u
    if re.match(r"^[a-z][a-z0-9+.\-]*:", u, re.I) or u.startswith("//") or ".." in u.split("/"):
        return None
    return base + re.sub(r"^\./", "", u)


def md_inline_safe(text: str, link) -> str:
    """Inline Markdown with every raw HTML character escaped. Code spans and maths are
    set aside first so emphasis markers inside them are left alone."""
    keep: list[str] = []

    def stash(h):
        keep.append(h)
        return f"\x00{len(keep) - 1}\x00"

    text = re.sub(r"`([^`\n]+)`", lambda m: stash(f"<code>{esc(m.group(1))}</code>"), text)
    text = _MD_MATH.sub(lambda m: stash(esc(m.group(0))), text)
    text = re.sub(r"!\[([^\]]*)\]\(([^)\s]+)\)", lambda m: stash(link(m.group(2), esc(m.group(1)), True)), text)
    text = re.sub(r"\[([^\]]+)\]\(([^)\s]+)\)", lambda m: stash(link(m.group(2), md_inline_safe(m.group(1), link), False)), text)
    text = esc(text)
    text = re.sub(r"\*\*(?=\S)(.+?)(?<=\S)\*\*", r"<strong>\1</strong>", text, flags=re.S)
    text = re.sub(r"(?<![\w])__(?=\S)(.+?)(?<=\S)__(?![\w])", r"<strong>\1</strong>", text, flags=re.S)
    text = re.sub(r"(?<![*\w])\*(?=\S)(.+?)(?<=\S)\*(?![*\w])", r"<em>\1</em>", text, flags=re.S)
    text = re.sub(r"(?<![\w])_(?=\S)(.+?)(?<=\S)_(?![\w])", r"<em>\1</em>", text, flags=re.S)
    while "\x00" in text:
        new = re.sub(r"\x00(\d+)\x00", lambda m: keep[int(m.group(1))], text)
        if new == text:
            break
        text = new
    return text


def md_render(src: str, link) -> str:
    """A small, safe Markdown renderer for contributed explanations: headings,
    paragraphs, lists, block quotes, rules, fenced code and display maths. Raw HTML is
    shown as text, never interpreted, so a contribution can carry no script."""
    lines = (src or "").replace("\r\n", "\n").split("\n")
    out: list[str] = []
    para: list[str] = []

    def flush():
        if para:
            out.append("<p>" + md_inline_safe("\n".join(para), link) + "</p>")
            para.clear()

    i = 0
    while i < len(lines):
        ln = lines[i]
        s = ln.strip()
        if s.startswith("```") or s.startswith("~~~"):
            flush()
            fence, j, buf = s[:3], i + 1, []
            while j < len(lines) and not lines[j].strip().startswith(fence):
                buf.append(lines[j])
                j += 1
            out.append(f'<pre class="md-code"><code>{esc(chr(10).join(buf))}</code></pre>')
            i = j + 1
            continue
        if s.startswith("$$") and s.count("$$") % 2 == 1:
            flush()
            buf, j = [ln], i + 1
            while j < len(lines) and "$$" not in lines[j]:
                buf.append(lines[j])
                j += 1
            if j < len(lines):
                buf.append(lines[j])
            out.append(f'<div class="m-d">{esc(chr(10).join(buf))}</div>')
            i = j + 1
            continue
        m = re.match(r"^(#{1,6})\s+(.*?)\s*#*$", s)
        if m:
            flush()
            n = {1: 2, 2: 2, 3: 3}.get(len(m.group(1)), 4)
            out.append(f'<h{n} class="md-h">{md_inline_safe(m.group(2), link)}</h{n}>')
            i += 1
            continue
        if re.fullmatch(r"(?:-\s*){3,}|(?:\*\s*){3,}|(?:_\s*){3,}", s):
            flush()
            out.append("<hr>")
            i += 1
            continue
        if s.startswith(">"):
            flush()
            buf = []
            while i < len(lines) and lines[i].strip().startswith(">"):
                buf.append(re.sub(r"^\s*>\s?", "", lines[i]))
                i += 1
            out.append(f'<blockquote class="quote">{md_render(chr(10).join(buf), link)}</blockquote>')
            continue
        lm = re.match(r"^\s*([-*+]|\d+[.)])\s+(.*)$", ln)
        if lm:
            flush()
            ordered = lm.group(1)[0].isdigit()
            items: list[list[str]] = []
            while i < len(lines):
                cur = lines[i]
                im = re.match(r"^\s*([-*+]|\d+[.)])\s+(.*)$", cur)
                if im and (im.group(1)[0].isdigit()) == ordered:
                    items.append([im.group(2)])
                elif cur.strip() and cur[:1] in (" ", "\t") and items:
                    items[-1].append(cur.strip())
                else:
                    break
                i += 1
            tag = "ol" if ordered else "ul"
            out.append(f"<{tag}>" + "".join(f"<li>{md_inline_safe(chr(10).join(it), link)}</li>" for it in items) + f"</{tag}>")
            continue
        if not s:
            flush()
            i += 1
            continue
        para.append(ln)
        i += 1
    flush()
    return "".join(out)


def strip_leading_h1(body: str) -> str:
    """Drop the Markdown title line: the page shows the title as its own heading."""
    return re.sub(r"\A\s*#\s+[^\n]*\n", "", body or "", count=1)


def people(names):
    return ", ".join(names) if names else ""


def statement_links(ids, root):
    out = []
    for sid in ids:
        s = ST.get(sid)
        if s:
            out.append(f'<a href="{root}statements/{esc(sid)}.html"><span class="md-math">{esc((s.get("labels") or [sid])[0])}</span></a>')
    return ", ".join(out)


def explanation_meta_html(e, fid, root, link_title=True):
    """Author, reviewer, date, scope, reader and source version, beside the text."""
    rows = []
    rows.append((C("explanation.authors"), esc(people(e["names"]))))
    rows.append((C("explanation.reviewers"), esc(people(e["reviewers"])) if e["reviewers"] else esc(C("explanation.reviewers_none"))))
    if e.get("date"):
        rows.append((C("explanation.date"), esc(e["date"])))
    if e.get("scope"):
        rows.append((C("explanation.scope"), f'<span class="md-math">{esc(e["scope"])}</span>'))
    if e.get("reader"):
        rows.append((C("explanation.reader"), f'<span class="md-math">{esc(e["reader"])}</span>'))
    if e.get("reader_scope") and not (e.get("scope") and e.get("reader")):
        rows.append((C("explanation.reader_scope"), f'<span class="md-math">{esc(e["reader_scope"])}</span>'))
    if e.get("statements"):
        rows.append((C("explanation.statements"), statement_links(e["statements"], root)))
    if e.get("upstream_commit"):
        uc = e["upstream_commit"]
        extra = "" if uc == COMMIT else f' <span class="dl__note">{esc(C("explanation.older_version"))}</span>'
        rows.append((C("explanation.version"), f'<code>{esc(uc[:7])}</code>{extra}'))
    rows.append((C("explanation.source_file"), f'<a class="ext" href="{esc(REPO + "/blob/main/" + e["path"])}" rel="noopener"><code>{esc(e["path"])}</code></a>'))
    return '<dl class="dl dl--meta">' + "".join(f"<div><dt>{esc(k)}</dt><dd>{v}</dd></div>" for k, v in rows) + "</dl>"


def build_explanation(f, e):
    """A stable reading page for one reviewed explanation."""
    fid = f["id"]
    rel = explanation_rel(e, fid)
    root = "../../"
    hslug = slugify(e["handle"]) or "explanation"
    folder: Path = e["folder"]
    copied = set()
    if folder.is_dir():
        for p in sorted(folder.iterdir()):
            if p.is_file() and p.suffix.lower() in IMG_EXT:
                dst = OUT / "explanations" / fid / hslug / p.name
                dst.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy(p, dst)
                copied.add(p.name)
    repo_base = REPO + "/blob/main/" + "/".join(e["path"].split("/")[:-1]) + "/"

    def link(url, text_html, image):
        if image:
            u = (url or "").strip()
            if re.match(r"^https?:", u, re.I):
                return f'<a class="ext" href="{esc(u)}" rel="noopener">{text_html or esc(u)}</a>'
            name = re.sub(r"^\./", "", u)
            if name in copied:
                return f'<img class="md-img" src="{esc(hslug + "/" + name)}" alt="{text_html}" loading="lazy">'
            return text_html
        href = safe_href(url, repo_base)
        return f'<a href="{esc(href)}" rel="noopener">{text_html}</a>' if href else text_html

    body_html = md_render(strip_leading_h1(e["body"]), link)
    di = DISC_OF[fid]
    title = e.get("title") or C("explanation.untitled")
    page_url = BASE_URL + rel
    suggest = suggest_url(page_url, title)
    body = f"""<div class="frame page page--narrow">
{trail(root, [(esc(DISCIPLINES[di]["name"]), f'{root}index.html#o=d:{DISC_SLUG[di]}'), (fam_title_html(f), f'{root}families/{fid}.html'), (f'<span class="md-math">{esc(title)}</span>', None)])}
<header class="phead">
 <p class="phead__kicker">{esc(C('explanation.kicker', id=fid))}</p>
 <h1 class="phead__title md-math">{esc(title)}</h1>
 <p class="phead__facts">{esc(C('explanation.reviewed_note'))}</p>
</header>
<section class="band band--tight">{explanation_meta_html(e, fid, root)}</section>
<article class="band explain-body prose md-math" data-macros="">{body_html}</article>
<section class="band band--tight"><p class="actions"><a class="btn btn--ghost" href="{root}families/{fid}.html">{esc(C('explanation.back', id=fid))}</a><a class="btn btn--quiet ext" href="{esc(suggest)}" rel="noopener">{esc(C('words.suggest_change'))}</a></p></section>
</div>"""
    write_page(rel, page(rel, title, C("explanation.description", title=title, id=fid), body, page_type="article"))


# ------------------------------------------------------- contribution actions


def suggest_url(page_url: str, name: str, statement_label: str | None = None) -> str:
    """The 'Suggest a change' issue form, prefilled with where the reader was: the page,
    the statement label when there is one, and the pinned upstream commit."""
    if statement_label:
        where = C("issues.note_where_statement", url=page_url, label=statement_label, commit=COMMIT)
    else:
        where = C("issues.note_where", url=page_url, commit=COMMIT)
    return issue_url("problem", C("issues.note", name=short(tex_plain(name), 90)), page=where)


def check_url(sid: str) -> str:
    return issue_url("check", C("issues.check", statement=sid), statement=sid, upstream_commit=COMMIT)


def check_choice_html(sids, root):
    """One check link per statement. A family with several statements offers an explicit
    choice, so a check is never silently filed against the first one."""
    sids = [s for s in sids if s in ST]
    if not sids:
        return ""
    if len(sids) == 1:
        return f'<a class="btn btn--ghost ext" href="{esc(check_url(sids[0]))}" rel="noopener">{esc(C("family.check_button"))}</a>'
    items = "".join(f'<li><a class="ext" href="{esc(check_url(s))}" rel="noopener"><span class="md-math">{esc((ST[s].get("labels") or [s])[0])}</span></a> <span class="muted small">{esc(C("family.check_file", file=s + ".lean"))}</span></li>' for s in sids)
    return f'<details class="choose"><summary class="btn btn--ghost">{esc(C("family.check_choose", n=len(sids)))}</summary><div class="choose__box"><p class="small muted">{esc(C("family.check_choose_intro"))}</p><ul class="choose__list">{items}</ul></div></details>'


# ------------------------------------------------------------ the family page
# DESIGN.md, "What a reader can do for any result": a family page answers, in this
# order, what is claimed, what states it formally, what has been checked, where to
# read it, what it connects to, and what a reader can do next. The bench carries the
# first two: the paper's theorem and the Lean statement, joined by the thread.

try:
    _SN = load("statement_numbers.json")
    # A row binds a printed number to the exact statement text at the pinned commit.
    STATEMENT_NUMBERS = ({(r["manuscript"], r["file"], r["line"]): r for r in _SN.get("rows", [])}
                         if _SN.get("upstream_commit") == COMMIT else {})
except (FileNotFoundError, ValueError):
    STATEMENT_NUMBERS = {}

try:
    _PL = load("paper_labels.json")
    # label -> [kind, heading name or None, printed number], per manuscript, pinned to the commit.
    PAPER_LABELS = ({r["manuscript"]: r["labels"] for r in _PL.get("rows", [])}
                    if _PL.get("upstream_commit") == COMMIT else {})
except (FileNotFoundError, ValueError):
    PAPER_LABELS = {}

KIND_WORD = {"section": "Section", "subsection": "Section", "subsubsection": "Section", "appendix": "Appendix",
             "figure": "Figure", "table": "Table", "item": "item", "footnote": "footnote"}
REF_IN_MATH = re.compile(r"\\(eqref|ref|cref|Cref|autoref|Autoref)\s*\{([^{}]*)\}")


class LabelTexConv(TexConv):
    """TexConv that prints a cross-reference as the paper prints it: \\eqref as (1.1),
    \\ref as 1.1, \\cref as Theorem 1.1, through data/paper_labels.json (written by
    scripts/build_papers.py), linked to the label's anchor on the reading page. A label the
    map does not hold prints ??, as LaTeX does; the raw label never reaches the page."""

    def __init__(self, ms: dict, root: str):
        super().__init__(ms, root)
        self.printed_labels = PAPER_LABELS.get(ms["id"], {})

    def ref_text(self, cmd: str, label: str) -> str:
        rec = self.printed_labels.get(label)
        if not rec or not rec[2]:
            STATS["family_refs_unresolved"] += 1
            return "(??)" if cmd == "eqref" else "??"
        kind, name, num = rec
        if cmd == "eqref" or (kind == "equation" and cmd in ("cref", "Cref", "autoref", "Autoref")):
            return f"({num})"
        if cmd in ("cref", "Cref", "autoref", "Autoref"):
            word = name or KIND_WORD.get(kind) or ""
            return f"{word} {num}".strip()
        return num

    def xref(self, cmd: str, label: str) -> str:
        text = self.ref_text(cmd, label)
        if "??" not in text and self.ms["id"] in PAPER_READING:
            href = f'{self.root}papers/{quote(self.ms["id"])}.html#{quote(label, safe=":-_./")}'
            return f'<a class="xref" href="{esc(href)}">{esc(text)}</a>'
        return f'<span class="xref">{esc(text)}</span>'

    def _refs_in_math(self, t: str) -> str:
        return REF_IN_MATH.sub(lambda mm: r"\text{" + self.ref_text(mm.group(1), mm.group(2).split(",")[0].strip()) + "}", t)

    def m_inline(self, t: str) -> str:
        return super().m_inline(self._refs_in_math(t))

    def m_display(self, t: str, env: str = "", opt: str = "") -> str:
        return super().m_display(self._refs_in_math(t), env, opt)


def printed_label(mid: str, label: str, kind_word: str = "") -> str:
    """What a reference to label prints in manuscript mid ("Corollary 3.2", "(1.1)"), or ""
    when the label map does not hold it."""
    rec = PAPER_LABELS.get(mid, {}).get(label)
    if not rec or not rec[2]:
        return ""
    kind, name, num = rec
    if kind == "equation":
        return f"({num})"
    word = kind_word or name or KIND_WORD.get(kind) or ""
    return f"{word} {num}".strip()


def resolved_refs(mid: str, refs: list) -> list:
    """The paper's outside references with each place of citation named as the paper prints
    it ("the proof of Corollary 3.2", "Theorem 1.1"). A label the map does not hold is
    dropped, leaving the section, so a raw TeX label never reaches the page."""
    out = []
    for r in refs:
        uses = []
        for u in r.get("uses") or []:
            ctx = dict(u.get("context") or {})
            if ctx.get("kind") == "proof" and ctx.get("of"):
                words = printed_label(mid, ctx["of"])
                ctx = dict(ctx, of=words) if words else {}
            elif ctx.get("label"):
                words = printed_label(mid, ctx["label"], ctx.get("display") or "")
                ctx = dict(ctx, label=words.split(" ", 1)[1] if " " in words else words) if words else {}
            uses.append(dict(u, context=ctx))
        out.append(dict(r, uses=uses))
    return out


GLUE = re.compile(r'(<span class="m">[^<]*</span>)([.,;:!?)\]]+)')
# One formula only: the span runs from a \( to the first \) after it.
GLUE_AUTO = re.compile(r'(\\\((?:(?!\\\))[^<])*\\\))([.,;:!?)]+)')


def glue(h: str) -> str:
    """Keep a formula and the punctuation that follows it on one line."""
    return GLUE_AUTO.sub(r'<span class="m-glue">\1\2</span>', GLUE.sub(r'<span class="m-glue">\1\2</span>', h))


RAW_LABEL = re.compile(r"\((?:eq|thm|lem|lemma|prop|cor|def|defn|sec|rem|conj|fig|tab|app|claim|ex|hyp|cond|step|part)[:.][^)\s]*\)"
                       r"|\b(?:eq|thm|lem|prop|cor|def|sec|rem|conj|fig|tab):[A-Za-z0-9]", re.I)


def guard_labels(where: str, h: str) -> str:
    """Stop the build when a raw TeX label survives in rendered statement text (the Show
    the TeX box, which quotes the source, is exempt)."""
    t = re.sub(r'<details class="texsrc">.*?</details>', " ", h, flags=re.S)
    t = re.sub(r"<[^>]+>", " ", t)
    hits = RAW_LABEL.findall(html.unescape(t))
    if hits:
        raise SystemExit(f"build_family: raw TeX label in statement text on {where}: {hits[:3]}")
    return h


def lean_breaks(h: str) -> str:
    """Let a long Lean name break only after an underscore or a dot."""
    return re.sub(r">([^<]+)", lambda mm: ">" + re.sub(r"([_.])(?=\w)", r"\1<wbr>", mm.group(1)), h)


MONTHS = ["January", "February", "March", "April", "May", "June", "July", "August", "September",
          "October", "November", "December"]


def date_words(s) -> str:
    """'2026-10-10' or 'October 10, 2026' as '10 October 2026'; anything else unchanged."""
    s = (s or "").strip()
    m = re.match(r"^(\d{4})-(\d{2})-(\d{2})", s)
    if m:
        return f"{int(m.group(3))} {MONTHS[int(m.group(2)) - 1]} {m.group(1)}"
    m = re.match(r"^([A-Z][a-z]+) (\d{1,2}), (\d{4})$", s)
    if m and m.group(1) in MONTHS:
        return f"{int(m.group(2))} {m.group(1)} {m.group(3)}"
    return s


def curly(s) -> str:
    """Typographic apostrophes in recorded prose (a word's ' becomes ’); code spans keep theirs."""
    parts = re.split(r"(`[^`]*`)", s or "")
    return "".join(p if p.startswith("`") else re.sub(r"(?<=[A-Za-z0-9])'(?=[A-Za-z])", "\u2019", p) for p in parts)


def say(n: int) -> str:
    """A small count as a word a person would say aloud; larger counts as figures."""
    words = C("family.numbers")
    return words[n] if 0 <= n < len(words) else num(n)


def count_words(n: int, key: str) -> str:
    """'one paper', 'three papers': family.count.<key> holds the singular and plural."""
    sing, plur = C("family.count")[key]
    return f"{say(n)} {sing if n == 1 else plur}"


def printed_name(m, st):
    """(kind, number, state) for a statement as its reading page prints it. The state is
    'numbered'; 'unnumbered' when the paper prints no number; or 'unavailable' when no
    row is bound to this exact statement text. Neither of the last two borrows a
    section number."""
    r = STATEMENT_NUMBERS.get((m["id"], st.get("file"), st.get("line")))
    if not r or (st.get("sha256") and r.get("statement_sha256") != st["sha256"]):
        return st["display"], None, "unavailable"
    kind = r.get("kind") or st["display"]
    if r.get("number") in (None, ""):
        return kind, None, "unnumbered"
    return kind, str(r["number"]), "numbered"


def printed_html(m, st) -> str:
    kind, number, state = printed_name(m, st)
    if number:
        return f"{esc(kind)}&nbsp;{esc(number)}"
    return f'{esc(kind)} <span class="fam-numstate">({esc(C("family.num_" + state))})</span>'


def printed_plain(m, st) -> str:
    kind, number, _ = printed_name(m, st)
    return f"{kind} {number}" if number else kind


def credit_link(source_id, root) -> str:
    """A credited source by the name of the people behind it, linked to its row on the sources page."""
    return f'<a href="{root}sources.html#src-{esc(source_id)}">{esc(source_credit(source_id))}</a>'


_PAIRS: dict = {}


def family_pair(sid):
    """pair_statement for one Lean statement, computed once. The build's pairing counts
    stay those of the statement pages, which make the same choice."""
    if sid not in _PAIRS:
        keys = ("pairing_candidate", "pairing_abstained_weak", "pairing_abstained_tie")
        before = {k: STATS[k] for k in keys}
        _PAIRS[sid] = pair_statement(ST[sid])
        for k in keys:
            STATS[k] = before[k]
    return _PAIRS[sid]


def pair_words(stmt, st, limit=4):
    """(words shared with the Lean statement's title, file and theorem names, words shared
    only with OpenAI's Lean note): the two sets pair_statement scores, longest first since
    they are the most specific."""
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    lean_words = words_of(" ".join(stmt.get("labels") or []) + " " + " ".join(stmt.get("docstrings") or []) + " " + stmt["id"]
                          + " " + " ".join(n.split(".")[-1] for n in stmt["comparator"]["theorem_names"]))
    scope_words = words_of(((fam or {}).get("lean_doc") or {}).get("scope", ""))
    w = words_of((st.get("title") or "") + " " + st["text"])
    lean = sorted(w & lean_words, key=lambda x: (-len(x), x))[:limit]
    note = sorted((w & scope_words) - lean_words, key=lambda x: (-len(x), x))[:max(0, limit - len(lean))]
    return lean, note


def first_headline(f):
    """(manuscript, statement) the page shows when no Lean statement chose one: the first
    headline theorem of the first current paper, else its first headline statement."""
    heads = [(MS[s], st) for s in f["manuscripts"] if s in MS and MS[s]["status"] == "current" for st in headline_statements(MS[s])]
    if not heads:
        heads = [(MS[s], st) for s in f["manuscripts"] if s in MS for st in headline_statements(MS[s])]
    return next(((m, st) for m, st in heads if st["kind"] == "theorem"), heads[0] if heads else (None, None))


def bench_choice(f):
    """(main, (manuscript, statement), pairs). pairs lists (sid, manuscript, statement, why)
    for every Lean statement; main is the one drawn large: a main result with a candidate
    pairing, else any candidate, else the first statement."""
    pairs = [(sid, *family_pair(sid)) for sid in f["statements"] if sid in ST]
    cands = [p for p in pairs if p[3] == "candidate"]
    main = next((p for p in cands if ST[p[0]]["main_result"]), None) or (cands[0] if cands else None) or (pairs[0] if pairs else None)
    if main and main[3] == "candidate":
        return main, (main[1], main[2]), pairs
    return main, first_headline(f), pairs


def same_statement(a, b) -> bool:
    return bool(a and b) and a[0]["id"] == b[0]["id"] and a[1].get("file") == b[1].get("file") and a[1].get("line") == b[1].get("line")


def runs_of(sid):
    return sourced_all(ST[sid], "replay")


def run_groups(sid) -> int:
    return len({v["source"] for v in runs_of(sid) if (v.get("value") or {}).get("verdict") == "accepted"})


GLYPH_RUN = {"ok": '<svg class="glyph glyph--ok" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.2 6.4 4.9 9 9.8 3.2"/></svg>',
             "open": '<svg class="glyph glyph--open" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="3.6"/></svg>'}


def thread_svg(vertical=False) -> str:
    """The thread: a dot at the paper's theorem, a diamond at the Lean statement, a dashed
    steel line between (dashed while the pairing is a candidate). Each end's centre sits
    on a card's border (family.css places it), so the line never crosses a word.
    Decorative: the caption beside it says the same in words."""
    if vertical:
        return ('<svg class="thread thread--v" viewBox="0 0 14 44" width="14" height="44" aria-hidden="true" focusable="false">'
                '<circle class="thread__dot" cx="7" cy="4" r="3.5"/><path class="thread__line" d="M7 9V34.5"/>'
                '<path class="thread__end" d="M7 35.5l4.5 4.5-4.5 4.5-4.5-4.5z"/></svg>')
    return ('<svg class="thread thread--h" viewBox="0 0 76 12" width="76" height="12" aria-hidden="true" focusable="false">'
            '<circle class="thread__dot" cx="5.5" cy="6" r="4"/><path class="thread__line" d="M11 6H65"/>'
            '<path class="thread__end" d="M66 6l4.5-4.5L75 6l-4.5 4.5z"/></svg>')


def mini_thread(paired: bool) -> str:
    if paired:
        return ('<svg class="mthread" viewBox="0 0 34 10" width="34" height="10" aria-hidden="true">'
                '<circle cx="4" cy="5" r="3"/><path d="M8.5 5H25"/><path class="mthread__end" d="M26 5l3.5-3.5L33 5l-3.5 3.5z"/></svg>')
    return ('<svg class="mthread mthread--none" viewBox="0 0 34 10" width="34" height="10" aria-hidden="true">'
            '<path class="mthread__end" d="M26 5l3.5-3.5L33 5l-3.5 3.5z"/></svg>')


def bench_paper_card(m, st, root, conv, aid="bench-theorem") -> str:
    """The paper's theorem as printed, source first: the paper and its place, then the
    number, the exact TeX, and the passage on the reading page."""
    title = f' <span class="bp__title">({conv.text(st["title"], inline=True)})</span>' if st.get("title") else ""
    where = C("family.where_appendix") if st.get("appendix") else (
        C("family.where_section_titled", n=st["section"], title=tex_plain(st["section_title"])) if st.get("section_title")
        else C("family.where_section", n=st["section"]))
    passage = paper_statement_href(m["id"], st, root)
    src_url = f'{BASE_BLOB}preprints/{m["id"]}/{st["file"]}#L{st["line"]}'
    if passage:
        go = f'<a class="bp__go" href="{esc(passage)}">{esc(C("family.read_passage"))}</a>'
    else:
        go = f'<a class="bp__go ext" href="{esc(m["pdf_url"])}" rel="noopener">{esc(C("family.read_pdf"))}</a>'
    body = guard_labels(f"{m['id']} line {st['line']}", glue(conv.blocks(st["text"])))
    return f"""<article class="bp" id="{aid}" data-macros="{esc(m['id'])}" aria-labelledby="{aid}-h">
 <p class="bp__src">{C("family.paper_in", paper=f'<a href="{root}papers/{esc(m["id"])}.html">{ms_title_html(m)}</a>', where=esc(where))}</p>
 <h3 class="bp__head" id="{aid}-h"><span class="bp__kind">{printed_html(m, st)}.</span>{title}</h3>
 <div class="bp__body">{body}</div>
 <footer class="bp__foot">
  <p class="bp__acts">{go}<a class="ext" href="{esc(src_url)}" rel="noopener">{esc(C('words.source_line', line=st['line']))}</a></p>
  <details class="texsrc"><summary>{esc(C('words.tex_source'))}</summary><div class="texsrc__box"><button class="copy" type="button" data-copy-next>{esc(C('words.copy'))}</button><pre><code>{esc(st["text"])}</code></pre></div></details>
 </footer>
</article>"""


def runs_html(sid, root) -> str:
    """Outside re-runs through Comparator, one line per group; each group's own account folded."""
    items, hows = [], []
    for v in runs_of(sid):
        rv = v.get("value") or {}
        verdict = rv.get("verdict") or ""
        word = C("family.run_verdict").get(verdict, verdict)
        state = "ok" if verdict == "accepted" else "open"
        when = f' <span class="runs__when">{esc(date_words(rv.get("date")))}</span>' if rv.get("date") else ""
        items.append(f'<li class="runs__i runs__i--{state}">{GLYPH_RUN[state]}<p class="runs__line"><span class="runs__who">{credit_link(v["source"], root)}</span> '
                     f'<span class="runs__v">{esc(word)}</span>{when} <a class="ext runs__rec" href="{esc(rv.get("url") or "")}" rel="noopener" '
                     f'aria-label="{esc(C("family.run_record_label", who=source_credit(v["source"])))}">{esc(C("family.run_record"))}</a></p></li>')
        how = curly(rv.get("text"))
        if verdict == "accepted":
            how = re.sub(r"\bpassed\b", "accepted", how)
        hows.append(f'<li><span class="runs__who2">{esc(source_credit(v["source"]))}:</span> {ctext(how)}</li>')
    if not items:
        return f'<div class="runs"><p class="runs__h">{ctext(C("family.runs_heading"))}</p><p class="runs__none">{esc(C("family.runs_none"))}</p></div>'
    return (f'<div class="runs"><p class="runs__h">{ctext(C("family.runs_heading"))}</p><ul class="runs__list">{"".join(items)}</ul>'
            f'<details class="fam-fold runs__fold"><summary>{esc(C("family.runs_how"))}</summary><ul class="runs__hows">{"".join(hows)}</ul>'
            f'<p class="runs__note">{esc(C("family.runs_note"))}</p></details></div>')


def bench_lean_card(sid, root) -> str:
    """The Lean statement paired with the theorem, in Lean's own text: the first theorem
    Comparator checks in the file in full, then the others by name, so the card never
    shows less than the file states without saying so; then who has re-run it."""
    s = ST[sid]
    label = (s.get("labels") or [sid])[0]
    where = C("family.lean_main") if s["main_result"] else C("family.lean_support")
    holes = s["comparator"].get("definition_names") or []
    holes_html = ""
    if holes:
        holes_html = '<p class="bl__note">' + ctext(C("statement.card_holes_one", name=holes[0].split(".")[-1]) if len(holes) == 1
                                                     else C("statement.card_holes_many", n=len(holes), name=holes[0].split(".")[-1])) + "</p>"
    note = C("family.lean_note_axiom") if s["declares_axiom"] else C("family.lean_note")
    names = s["comparator"]["theorem_names"] or s["theorems"][:1]
    first = dict(s, comparator=dict(s["comparator"], theorem_names=names[:1]))
    more = ""
    if len(names) > 1:
        lines = {d["name"]: d["line"] for d in s.get("declarations") or []}
        items = ", ".join(f'<a href="{root}statements/{esc(sid)}.html' + (f'#L{lines[n_]}' if n_ in lines else "")
                          + f'"><code translate="no">{lean_breaks(">" + esc(n_.split(".")[-1]))[1:]}</code></a>' for n_ in names[1:])
        more = (f'<p class="bl__more">' + esc(C("family.lean_more_1") if len(names) == 2 else C("family.lean_more_n", n=say(len(names) - 1)))
                + f" {items}.</p>")
    return f"""<article class="bl" id="bench-lean" aria-labelledby="bench-lean-h">
 <h3 class="bl__title" id="bench-lean-h"><a href="{root}statements/{esc(sid)}.html"><span class="md-math">{esc(label)}</span></a></h3>
 <p class="bl__file"><code class="bl__fname" translate="no">{esc(sid)}.lean</code>, {esc(where)}</p>
 <pre class="lean lean--snippet bl__code"><code>{lean_breaks(lean_snippet_html(first, max_lines=16))}</code></pre>
 {more}
 <p class="bl__note">{ctext(note)}</p>{holes_html}
 {runs_html(sid, root)}
 <p class="bl__go"><a href="{root}statements/{esc(sid)}.html">{esc(C('words.open_statement'))}</a></p>
</article>"""


READING_GRADE = {"matches": "all", "full": "all", "partial": "part", "narrower-declared": "less",
                 "narrower-undeclared": "less", "narrower-unlinked": "less", "weaker-statement": "less",
                 "different": "other", "supporting-only": "other"}
READERS = ["mathvet", "cert-machine"]
GLYPH_READING = {
    "all": '<circle cx="7" cy="7" r="5.5"/><circle class="fill" cx="7" cy="7" r="5.5"/>',
    "part": '<circle cx="7" cy="7" r="5.5"/><path class="fill" d="M7 1.5a5.5 5.5 0 0 1 0 11z"/>',
    "less": '<circle cx="7" cy="7" r="5.5"/><path class="fill" d="M7 1.5a5.5 5.5 0 0 1 5.5 5.5H7z"/>',
    "other": '<circle cx="7" cy="7" r="5.5"/>',
}


def reader_method(src, root, record_url="") -> str:
    """One line under a reader's name: their method in the words the atlas records from
    their published rules (curated/sources/<id>.json), shortened and attributed, linked."""
    s_ = (SOURCES.get(src) or {})
    method = s_.get("method") or ""
    first = re.split(r"(?<=[.;])\s", method, maxsplit=1)[0].rstrip(";.") + "." if method else ""
    # Their published rules: MathVet's rubric at the commit the atlas read; cert-machine's report.
    url = ""
    if src == "mathvet" and re.search(r"/blob/[0-9a-f]{40}/", record_url or ""):
        url = re.sub(r"/blob/([0-9a-f]{40})/.*", r"/blob/\1/PROTOCOL.md", record_url)
    elif src == "cert-machine":
        url = s_.get("url") or ""
    label = C("family.reader_rules").get(src)
    link = f' <a class="ext" href="{esc(url)}" rel="noopener">{esc(label)}</a>' if url and label else ""
    return f'<p class="rd__method">{esc(C("family.reader_method", method=curly(first)))}{link}</p>' if first else ""


def readings_html(f, root, draft="") -> str:
    """The outside readers' verdicts on whether the family's Lean statements state its
    headline: each in their own term beside a plain gloss, with their note directly under
    it at the same weight, then OpenAI's own note. The page adds no summary of its own."""
    vals = {v["source"]: v["value"] for v in sourced_all(f, "scope_reading")}
    if not vals and not f["statements"]:
        return ""
    cols = []
    for src in READERS + [s_ for s_ in vals if s_ not in READERS]:
        rv = vals.get(src)
        who = f'<p class="rd__who">{credit_link(src, root)}</p>{reader_method(src, root, (rv or {}).get("url"))}'
        if not rv:
            cols.append(f'<div class="rd rd--none">{who}<p class="rd__v">{esc(C("family.reading_none"))}</p></div>')
            continue
        grade = READING_GRADE.get(rv.get("verdict"), "other")
        gloss = C("family.reading_v").get(rv.get("verdict")) or ""
        term = rv.get("code") or rv.get("verdict") or ""
        notes = ""
        if rv.get("gap"):
            notes += f'<p class="rd__note"><span class="rd__k">{esc(C("family.reading_gap"))}</span> <span class="md-math">{ctext(curly(rv["gap"]))}</span></p>'
        if rv.get("note"):
            notes += f'<p class="rd__note md-math">{ctext(curly(rv["note"]))}</p>'
        cols.append(f'<div class="rd rd--{grade}">{who}'
                    f'<p class="rd__v"><svg class="rd__g" viewBox="0 0 14 14" aria-hidden="true">{GLYPH_READING[grade]}</svg>'
                    f'<span><span class="rd__gloss">{esc(gloss)}</span> <span class="rd__termw">{esc(C("family.reading_term"))} <code class="rd__term">{esc(term)}</code></span></span></p>'
                    f'{notes}<p class="rd__def">{esc(C("family.reading_def"))} {ctext(curly(rv.get("text")))}</p>'
                    f'<p class="rd__src"><a class="ext" href="{esc(rv.get("url") or "")}" rel="noopener">{esc(C("sources.record_link"))}</a></p></div>')
    note = ""
    doc = f.get("lean_doc") or {}
    if doc.get("scope"):
        paras = [curly(p) for p in re.split(r"\n\s*\n", doc["scope"].strip()) if p.strip()]
        first = md_paragraphs(paras[0])
        rest = ""
        if len(paras) > 1:
            rest = f'<details class="fam-fold"><summary>{esc(C("family.note_rest"))}</summary>{md_paragraphs(chr(10) + chr(10).join(paras[1:]))}</details>'
        note = (f'<div class="rd-note"><p class="rd-note__h"><a class="ext" href="{esc(doc.get("url") or "")}" rel="noopener">{esc(C("family.note_heading"))}</a></p>'
                f'<blockquote class="rd-note__q md-math">{first}{rest}</blockquote></div>')
    return (f'<section class="rds" aria-labelledby="h-readings"><h3 class="rds__h" id="h-readings">{esc(C("family.readings_heading"))}</h3>'
            f'<p class="rds__intro">{ctext(C("family.readings_intro"))}</p>'
            f'<div class="rds__pair">{"".join(cols)}</div>{note}{draft}</section>')


def draft_scope_line(sid, root) -> str:
    """The AI agent's draft classification of one statement, as a draft, with its check link."""
    if COVER_STALE:
        return f'<p class="bench__draft">{esc(C("statement.coverage_stale"))}</p>'
    cls = cover_class(sid)
    label = cover_label(cls)
    label = label[:1].lower() + label[1:]
    key = "family.draft_scope" if cls and label.startswith("states") else ("family.draft_scope_unclear" if cls == "unclear" else "family.draft_scope_none")
    check = issue_url("check", C("statement.coverage_check_title", id=sid), statement=sid, upstream_commit=COMMIT)
    return (f'<p class="bench__draft">{esc(C(key, label=label) if key == "family.draft_scope" else C(key))} '
            f'<a class="ext" href="{esc(check)}" rel="noopener">{esc(C("statement.coverage_check"))}</a></p>')


def support_mode(f):
    """(headline manuscript, headline statement) when the release's Lean is paired with a
    theorem other than the family's headline and every outside reader finds that the Lean
    states only a supporting or a different result; None otherwise. The page then shows the
    headline as the claim and the paired theorem as what the Lean states."""
    main, (m, st), pairs = bench_choice(f)
    if not main or main[3] != "candidate":
        return None
    grades = [READING_GRADE.get((v.get("value") or {}).get("verdict"), "other") for v in sourced_all(f, "scope_reading")]
    hm, hs = first_headline(f)
    if not grades or any(g != "other" for g in grades) or not hs or same_statement((m, st), (hm, hs)):
        return None
    if any(p[3] == "candidate" and same_statement((p[1], p[2]), (hm, hs)) for p in pairs):
        return None
    return hm, hs


def thread_caption(fid, f, main, m, st, pairs, root) -> str:
    """The thread in words: what is paired, how the atlas found it, that nobody has reviewed
    it, and every other Lean statement paired with the same theorem, reachable here."""
    sid = main[0]
    label = (ST[sid].get("labels") or [sid])[0]
    theorem = printed_plain(m, st)
    others = [p for p in pairs if p is not main and p[3] == "candidate" and same_statement((p[1], p[2]), (m, st))]
    lean_w, note_w = pair_words(ST[sid], st)
    if others:
        links = "; ".join(f'<a href="{root}statements/{esc(p[0])}.html"><span class="md-math">{esc((ST[p[0]].get("labels") or [p[0]])[0])}</span></a>' for p in others)
        first = C("family.thread_many", theorem=esc(theorem), n=say(len(others) + 1), shown=f'<span class="md-math">{esc(label)}</span>', others=links)
    else:
        first = ctext(C("family.thread_one", theorem=theorem))
    if lean_w and note_w:
        how = C("family.thread_words_both", lean=", ".join(lean_w), note=", ".join(note_w))
    elif lean_w:
        how = C("family.thread_words_lean", lean=", ".join(lean_w))
    else:
        how = C("family.thread_words_note", note=", ".join(note_w))
    end = C("family.thread_unreviewed_n") if others else C("family.thread_unreviewed_1")
    return (f'{first} {esc(how)} {esc(end)} '
            f'<a class="ext" href="{esc(check_url(sid))}" rel="noopener">{esc(C("family.thread_check"))}</a>')


def family_claim_card(fid, root) -> str:
    """The bench for one family: the paper's theorem in a paper card, the Lean statement
    paired with it in a Lean card, the thread between them, and the outside readers'
    verdicts. Where the Lean states only a supporting step, the headline theorem comes
    first as the claim. Self-contained for embedding: the page needs family_head(root) and
    the KaTeX macros of family_claim_macro_ids(fid)."""
    f = FAM[fid]
    main, (m, st), pairs = bench_choice(f)
    claim = ""
    sup = support_mode(f)
    if sup:
        hm, hs = sup
        claim = (f'<div class="bench-claim">{bench_paper_card(hm, hs, root, LabelTexConv(hm, root), aid="bench-claim")}'
                 f'<p class="bench-claim__note">{esc(C("family.support_claim_note"))}</p></div>'
                 f'<h3 class="bench__sub" id="h-lean-states">{esc(C("family.support_heading"))}</h3>'
                 f'<p class="bench__subnote">{esc(C("family.support_subnote"))}</p>')
    if m and st:
        paper = bench_paper_card(m, st, root, LabelTexConv(m, root))
    else:
        paper = f'<article class="bp bp--none" id="bench-theorem"><p>{esc(C("family.no_headline_any"))}</p></article>'
    cap_side = cap_stack = ""
    if main:
        sid, _, _, why = main
        lean = bench_lean_card(sid, root)
        label = (ST[sid].get("labels") or [sid])[0]
        if why == "candidate":
            cap = thread_caption(fid, f, main, m, st, pairs, root)
            # The caption sits under the paper card beside the Lean card when they stand side
            # by side, and after both when they stack; one copy shows at a time.
            cap_side = f'<p class="bench__cap bench__cap--side" id="thread-{esc(fid)}">{cap}</p>'
            cap_stack = f'<p class="bench__cap bench__cap--stack">{cap}</p>'
            joint = (f'<div class="bench__thread" role="img" aria-label="{esc(C("family.thread_label", theorem=printed_plain(m, st), label=tex_plain(label)))}" '
                     f'aria-describedby="thread-{esc(fid)}">{thread_svg()}{thread_svg(vertical=True)}</div>')
            kind = "paired"
        else:
            cap_stack = f'<p class="bench__cap bench__cap--none">{ctext(C("family.nothread_" + why))}</p>'
            joint = ""
            kind = "unpaired"
        draft = draft_scope_line(sid, root)
    else:
        lean = (f'<div class="bl bl--none"><p class="bl__title">{esc(C("family.nolean_h"))}</p>'
                f'<p class="bl__none">{esc(C("family.nolean_text"))}</p>'
                f'<p class="bl__none">{esc(C("family.nolean_invite"))} '
                f'<a class="ext" href="{esc(suggest_url(BASE_URL + "families/" + fid + ".html", C("issues.family_name", id=fid, title=tex_plain(f["title"]))))}" rel="noopener">{esc(C("words.suggest_change"))}</a>.</p></div>')
        joint = ""
        kind = "nolean"
        draft = ""
    # Each card sits in a side column; the shorter one may travel (stick) beside the
    # longer as the reader scrolls (family.js decides), carrying the thread with it.
    gap = "bench__gap" + ("" if kind == "paired" else " bench__gap--none")
    readings = readings_html(f, root, draft) if (f["statements"] or sourced_all(f, "scope_reading")) else draft
    # Self-contained: the glossary links ctext() leaves for write_page are resolved here,
    # since a page that embeds the bench may write its file another way.
    return (f'<div class="bench-host">{claim}<div class="bench bench--{kind}" data-bench>'
            f'<div class="bench__side bench__side--paper"><div class="bench__travel"><div class="bench__paper">{paper}{joint}</div>{cap_side}</div></div>'
            f'<div class="{gap}" aria-hidden="true"></div>'
            f'<div class="bench__side bench__side--lean"><div class="bench__travel">{lean}</div></div>'
            f'<div class="bench__notes">{cap_stack}{readings}</div></div></div>').replace("__ROOT__", root)


def family_claim_macro_ids(fid) -> list:
    """Manuscript ids whose KaTeX macros the bench needs (for macros_script)."""
    f = FAM[fid]
    _, (m, _), _ = bench_choice(f)
    sup = support_mode(f)
    return list(dict.fromkeys(([sup[0]["id"]] if sup else []) + ([m["id"]] if m else [])))


def family_head(root) -> str:
    """The sheets and scripts a family page needs (scripts/family_page.py)."""
    import family_page
    return family_page.head_assets(sys.modules[__name__], root)


def bench_index_html(f, root) -> str:
    """Every other theorem and Lean statement, compact: which theorem each Lean statement
    is paired with, and which theorems have none. The bench above is the large case."""
    main, theorem, pairs = bench_choice(f)
    if not pairs and not theorem[0]:
        return ""
    rows = []
    # Lean statements paired with the bench theorem itself are named at the thread.
    # Other theorems: those a Lean statement pairs with first, then the rest.
    paired_to = {}
    for p in pairs:
        if p[3] == "candidate" and not same_statement((p[1], p[2]), theorem):
            paired_to.setdefault((p[1]["id"], p[2]["file"], p[2]["line"]), []).append(p)
    heads = [(MS[s], st) for s in f["manuscripts"] if s in MS for st in headline_statements(MS[s])]
    sup = support_mode(f)
    if sup:
        heads = [h for h in heads if not same_statement(h, sup)]
    for key, ps in paired_to.items():
        if not any((m["id"], st["file"], st["line"]) == key for m, st in heads):
            heads.append((ps[0][1], ps[0][2]))
    others = [(m, st) for m, st in heads if not same_statement((m, st), theorem)]
    others.sort(key=lambda x: 0 if (x[0]["id"], x[1]["file"], x[1]["line"]) in paired_to else 1)
    shown = 0
    rest = 0
    for m, st in others:
        ps = paired_to.get((m["id"], st["file"], st["line"]), [])
        if not ps and shown >= 4:
            rest += 1
            continue
        href = paper_statement_href(m["id"], st, root) or f"{root}papers/{esc(m['id'])}.html"
        thm = f'<span class="bx__thm"><a href="{esc(href)}">{printed_html(m, st)}</a> <span class="bx__in">{C("family.index_in", paper=ms_title_html(m))}</span></span>'
        if ps:
            lean = ", ".join(f'<a href="{root}statements/{esc(p[0])}.html"><span class="md-math">{esc((ST[p[0]].get("labels") or [p[0]])[0])}</span></a> <span class="bx__runs">{esc(runs_phrase(p[0]))}</span>' for p in ps)
            rows.append(f'<li class="bx__i">{mini_thread(True)}<p>{thm}<span class="bx__to">{lean}</span></p></li>')
        elif pairs:
            rows.append(f'<li class="bx__i bx__i--bare"><span class="bx__pad" aria-hidden="true"></span><p>{thm}<span class="bx__to bx__to--none">{esc(C("family.index_no_lean"))}</span></p></li>')
        else:
            rows.append(f'<li class="bx__i bx__i--bare bx__i--plain"><span class="bx__pad" aria-hidden="true"></span><p>{thm}</p></li>')
        shown += 1
    for p in pairs:
        if p is not main and p[3] != "candidate":
            lean = f'<a href="{root}statements/{esc(p[0])}.html"><span class="md-math">{esc((ST[p[0]].get("labels") or [p[0]])[0])}</span></a>'
            rows.append(f'<li class="bx__i bx__i--loose">{mini_thread(False)}<p>{C("family.index_unpaired", lean=lean, why=esc(C("family.index_why_" + p[3])))} <span class="bx__runs">{esc(runs_phrase(p[0]))}</span></p></li>')
    if rest:
        rest_key = "family.index_rest" if pairs else "family.index_rest_nolean"
        rows.append(f'<li class="bx__i bx__i--rest"><span class="bx__pad" aria-hidden="true"></span><p>{C(rest_key, n=say(rest))[:1].upper() + C(rest_key, n=say(rest))[1:]} <a href="#h-ms">{esc(C("family.index_rest_link"))}</a>.</p></li>')
    if not rows:
        return ""
    return (f'<div class="bx"><h3 class="bx__h" id="h-index">{esc(C("family.index_heading" if pairs else "family.index_heading_nolean"))}</h3>'
            f'<ul class="bx__list{"" if pairs else " bx__list--plain"}">{"".join(rows)}</ul></div>')


def runs_phrase(sid) -> str:
    n = run_groups(sid)
    if n == 0:
        return C("family.runs_phrase_none")
    return C("family.runs_phrase_1") if n == 1 else C("family.runs_phrase_n", n=say(n))


def fam_finds(finds, root, cls="ff") -> str:
    """Outside findings, each credited where it sits: what they found, who, where, when."""
    out = []
    for f_ in finds:
        e = COMMUNITY["efforts"].get(f_.get("effort") or "", {})
        who = credit_names(e)
        credit = f_.get("_credit") or ", ".join(x for x in [who, e.get("name", "")] if x)
        what = f_["_html"] if f_.get("_html") else esc(curly(f_["summary"]))
        out.append(f'<li class="{cls}__i"><p class="{cls}__what">{what}</p>'
                   f'<p class="{cls}__who">{esc(curly(credit))}{(", " + esc(date_words(f_["date"]))) if f_.get("date") else ""}. '
                   f'<a class="ext" href="{esc(f_["url"])}" rel="noopener">{esc(C("community.source"))}</a></p></li>')
    return f'<ul class="{cls}">' + "".join(out) + "</ul>"


def finds_block(finds, root, heading, hid, keep=3) -> str:
    """A credited list that shows its first few and folds the rest, so it filters rather than dumps."""
    if not finds:
        return ""
    finds = sorted(finds, key=lambda x: x["date"], reverse=True)
    head = f'<h3 class="h3" id="{hid}">{esc(heading)}</h3>'
    if len(finds) <= keep + 1:
        return head + fam_finds(finds, root)
    return (head + fam_finds(finds[:keep], root)
            + f'<details class="fam-fold"><summary>{esc(C("family.show_all", n=len(finds)))}</summary>{fam_finds(finds[keep:], root)}</details>')


def head_lede(desc: str):
    """(first sentence, rest) of OpenAI's catalogue description: the first full stop
    outside mathematics after the sentence has begun."""
    depth = 0
    i = 0
    while i < len(desc) - 1:
        two = desc[i:i + 2]
        if two in ("\\(", "\\["):
            depth += 1
            i += 2
            continue
        if two in ("\\)", "\\]"):
            depth = max(0, depth - 1)
            i += 2
            continue
        if desc[i] == "." and desc[i + 1] == " " and depth == 0 and i > 40:
            return desc[:i + 1], desc[i + 2:]
        i += 1
    return desc, ""


def head_facts_html(f, root, mss, problems) -> str:
    """The family's facts as sentences a person could say aloud, each linked to the rows behind it."""
    fid = f["id"]
    n = len(mss)
    reading = sum(1 for m in mss if m["id"] in PAPER_READING)
    papers = count_words(n, "paper")
    if reading and reading == n:
        papers += ", " + (C("family.facts_read_all") if n > 1 else C("family.facts_read_one"))
    elif reading:
        papers += ", " + C("family.facts_read_some", k=say(reading))
    stmts = [s for s in f["statements"] if s in ST]
    if stmts:
        runs = sum(1 for s in stmts if run_groups(s))
        lean = f'<a href="#h-bench">{esc(count_words(len(stmts), "lean"))}</a>'
        if runs == len(stmts):
            lean += ", " + esc(C("family.facts_run_all") if len(stmts) > 1 else C("family.facts_run_one"))
        elif runs:
            lean += ", " + esc(C("family.facts_run_some", k=say(runs)))
        else:
            lean += ", " + esc(C("family.facts_run_none") if len(stmts) > 1 else C("family.facts_run_none_one"))
    else:
        lean = esc(C("family.facts_lean_none"))
    sents = [C("family.facts", id=esc(fid), papers=f'<a href="#h-ms">{esc(papers)}</a>', lean=lean)]
    wd = [m for m in MANUSCRIPTS if m["status"] == "withdrawn" and m.get("family") == fid]
    if wd:
        sents.append(f'<a href="#h-withdrawn">{esc(C("family.facts_withdrawn_1") if len(wd) == 1 else C("family.facts_withdrawn_n", n=say(len(wd)).capitalize()))}</a>')
    if problems:
        sents.append(f'<a href="#h-problems">{esc(C("family.facts_problems_1") if len(problems) == 1 else C("family.facts_problems_n", n=say(len(problems)).capitalize()))}</a>')
    erd = sourced(f, "erdos_problems")
    if erd and erd.get("value"):
        probs = [f'<a class="ext" href="{esc(p["url"])}" rel="noopener">{esc(C("sources.erdos_number", n=p["number"]))}</a>' for p in erd["value"]]
        joined = probs[0] if len(probs) == 1 else ", ".join(probs[:-1]) + " " + C("family.and") + " " + probs[-1]
        sents.append(C("family.facts_erdos", problems=joined, source=credit_link(erd["source"], root)))
    return '<p class="fhead__facts" id="h-standing">' + " ".join(sents) + "</p>"


def checks_html(f, root, problems) -> str:
    """What has been checked, by whom, and what is left for a reader to check."""
    fid = f["id"]
    stmts = [s for s in f["statements"] if s in ST]
    parts = []
    # Re-runs, statement by statement, when there is more than the bench's one statement.
    if len(stmts) > 1:
        groups = []
        for s in stmts:
            for v in runs_of(s):
                if v["source"] not in groups:
                    groups.append(v["source"])
        if groups:
            head = "".join(f'<th scope="col">{credit_link(g, root)}</th>' for g in groups)
            body = []
            for s in stmts:
                by = {v["source"]: v["value"] for v in runs_of(s)}
                cells = []
                for g in groups:
                    rv = by.get(g)
                    if not rv:
                        cells.append(f'<td class="rt__c rt__c--none">{esc(C("family.rt_none"))}</td>')
                        continue
                    state = "ok" if rv.get("verdict") == "accepted" else "open"
                    cells.append(f'<td class="rt__c rt__c--{state}"><a href="{esc(rv.get("url") or "")}" rel="noopener" class="rt__a">{GLYPH_RUN[state]}{esc(C("family.run_verdict").get(rv.get("verdict"), rv.get("verdict") or ""))}</a>'
                                 f'<span class="rt__d">{esc(date_words(rv.get("date")))}</span></td>')
                label = (ST[s].get("labels") or [s])[0]
                body.append(f'<tr><th scope="row"><a href="{root}statements/{esc(s)}.html"><span class="md-math">{esc(label)}</span></a></th>{"".join(cells)}</tr>')
            parts.append(f'<h3 class="h3" id="h-reruns">{esc(C("family.rt_heading"))}</h3><p class="intro">{ctext(C("family.rt_intro"))}</p>'
                         f'<div class="rt-wrap" tabindex="0" role="region" aria-labelledby="h-reruns"><table class="rt"><thead><tr><th scope="col">{esc(C("family.rt_lean"))}</th>{head}</tr></thead><tbody>{"".join(body)}</tbody></table></div>')
    parts.append(other_assistant_html(f, root))
    parts.append(finite_checks_html(f, root))
    elsewhere = findings_for(fid, kinds={"replay-pass"})
    parts.append(finds_block(elsewhere, root, C("family.reported_heading"), "h-reported"))
    if problems:
        parts.append(f'<div class="fam-problems"><h3 class="h3" id="h-problems">{esc(C("sources.problems_heading"))}</h3>{fam_finds(sorted(problems, key=lambda x: x["date"]), root)}</div>')
    parts.append(left_to_check_html(f, root))
    return "".join(p for p in parts if p)


def left_to_check_html(f, root) -> str:
    """What nobody has yet checked, each item with the place to check it."""
    stmts = [s for s in f["statements"] if s in ST]
    items = []
    if not stmts:
        items.append(esc(C("family.left_nolean")))
    else:
        cands = [s for s in stmts if family_pair(s)[2] == "candidate"]
        if cands:
            items.append(ctext(C("family.left_pairing_1") if len(cands) == 1 else C("family.left_pairing_n", n=say(len(cands))))
                         + f' <a href="#h-contrib">{esc(C("family.left_pairing_link"))}</a>')
        for s in stmts:
            holes = ST[s]["comparator"].get("definition_names") or []
            label = (ST[s].get("labels") or [s])[0]
            if holes:
                items.append(f'<a href="{root}statements/{esc(s)}.html#h-holes"><span class="md-math">{esc(label)}</span></a>: ' + ctext(C("family.left_holes_1") if len(holes) == 1 else C("family.left_holes_n", n=say(len(holes)))))
        unrun = [s for s in stmts if not run_groups(s)]
        for s in unrun:
            label = (ST[s].get("labels") or [s])[0]
            items.append(f'<a href="{root}statements/{esc(s)}.html"><span class="md-math">{esc(label)}</span></a>: ' + esc(C("family.left_unrun")))
        if not COVER_STALE and any(COVERAGE.get(s) for s in stmts):
            items.append(esc(C("family.left_scope")))
        for v in sourced_all(f, "scope_reading"):
            d = (v.get("value") or {}).get("definitions_to_check")
            if d:
                items.append(C("family.left_defs", source=credit_link(v["source"], root)) + f' <span class="md-math">{ctext(d)}</span>')
    fin = Counter(c["verdict"] for v in sourced_all(f, "finite_checks") for c in v["value"])
    if fin.get("refused"):
        items.append(esc(C("family.left_finite_1") if fin["refused"] == 1 else C("family.left_finite_n", n=say(fin["refused"]))))
    if fin.get("needs-data"):
        items.append(esc(C("family.left_data_1") if fin["needs-data"] == 1 else C("family.left_data_n", n=say(fin["needs-data"]))))
    if not items:
        return ""
    return (f'<div class="left"><h3 class="h3" id="h-left">{esc(C("family.left_heading"))}</h3>'
            f'<ul class="left__list">{"".join("<li>" + i + "</li>" for i in items)}</ul></div>')


def paper_row(m, root, conv, seen) -> str:
    """One paper: where to read it, its edition, and (folded) its abstract and the statements it opens with."""
    heads = headline_statements(m)
    reading = m["id"] in PAPER_READING
    notes = ""
    if m.get("version_note"):
        notes += (f'<details class="fam-fold"><summary>{esc(C("family.version_note"))}</summary>'
                  f'<div class="md-math">{md_paragraphs(m["version_note"], "preprints/" + m["id"] + "/")}</div></details>')
    prev = ""
    if m.get("previous_versions"):
        lst = ", ".join(f'<a href="{root}papers/{esc(p)}.html">{esc(date_words(MS[p]["date"]) or p) if p in MS else esc(p)}</a>' for p in m["previous_versions"])
        prev = f'<p class="pp__prev">{esc(C("family.previous_editions"))}: {lst}</p>'
    figs = []
    for st in heads:
        fig = guard_labels(f"{m['id']} line {st['line']}", glue(render_paper_statement(m, st, root, conv)))
        aid = re.search(r'id="([^"]+)"', fig).group(1)
        if aid in seen:  # two editions whose slugs share their first 40 characters
            k = 2
            while f"{aid}-{k}" in seen:
                k += 1
            fig = fig.replace(f'id="{aid}"', f'id="{aid}-{k}"', 1)
            aid = f"{aid}-{k}"
        seen.add(aid)
        figs.append(fig)
    stm = "".join(figs) if heads else f'<p class="muted">{esc(C("family.no_headline"))}</p>'
    abstract = f'<div class="pp__abstract tex-auto">{rich(m.get("abstract") or "")}</div>' if m.get("abstract") else ""
    fold = (C("family.paper_fold_1") if len(heads) == 1 else C("family.paper_fold", n=say(len(heads)))) if heads else C("family.paper_fold_none")
    meta = C("family.paper_meta", date=date_words(m.get("date")) or C("family.undated"), status=status_label(m["status"]).lower())
    read = (f'<a class="btn btn--ghost" href="{root}papers/{esc(m["id"])}.html">{esc(C("family.read_here"))}</a>' if reading
            else f'<a class="btn btn--ghost" href="{root}papers/{esc(m["id"])}.html">{esc(C("family.open_page"))}</a>')
    # Earlier editions link to their result at their own slug: keep that anchor here.
    aliases = ""
    for p in m.get("previous_versions") or []:
        if p not in seen and p not in FAM.get(m.get("family") or "", {}).get("manuscripts", []):
            seen.add(p)
            aliases += f'<span class="fam-alias" id="{esc(p)}"></span>'
    return f"""<article class="pp" id="{esc(m['id'])}">{aliases}
 <h3 class="pp__title"><a href="{root}papers/{esc(m['id'])}.html">{ms_title_html(m)}</a></h3>
 <p class="pp__meta">{esc(meta)}</p>
 <p class="pp__acts">{read}{pdf_button(m, 'btn btn--quiet')}</p>
 {notes}{prev}
 <details class="fam-fold pp__more"><summary>{esc(fold)}</summary>{abstract}<div class="stmts">{stm}</div></details>
</article>"""


def explanation_section_html(f, root):
    fid = f["id"]
    ex = CONTRIB["explanations"].get(fid, [])
    parts = []
    rev = [e for e in ex if e["status"] == "reviewed"]
    for e in rev:
        href = f'{root}{explanation_rel(e, fid)}'
        parts.append(f"""<article class="exrec">
 <p class="exrec__status"><span class="pill pill--explained">{esc(C('family.explain_reviewed_pill'))}</span></p>
 <h3 class="h3 md-math"><a href="{href}">{esc(e.get('title') or C('explanation.untitled'))}</a></h3>
 {explanation_meta_html(e, fid, root)}
 <p class="actions"><a class="btn btn--primary" href="{href}">{esc(C('family.read_explanation'))}</a></p>
</article>""")
    drafts = [e for e in ex if e["status"] != "reviewed"]
    if drafts:
        items = "".join(f'<li><span class="md-math">{esc(e.get("title") or C("explanation.untitled"))}</span>, {esc(people(e["names"]))} <span class="muted small">({esc(C("family.explain_status_" + ("ready" if e["status"] == "ready-for-review" else "draft")))})</span> <a class="ext small" href="{esc(REPO + "/blob/main/" + e["path"])}" rel="noopener">{esc(C("family.explain_draft_source"))}</a></li>' for e in drafts)
        parts.append(f'<h3 class="h3">{esc(C("family.explain_progress_heading"))}</h3><p class="intro">{esc(C("family.explain_progress_intro"))}</p><ul class="exdrafts">{items}</ul>')
    if not rev:
        parts.insert(0, f'<p class="fam-invite">{esc(C("family.explain_none"))}</p>')
    parts.append(finds_block(findings_for(fid, kinds={"explanation"}), root, C("sources.explanations_heading"), "h-elsewhere"))
    return "".join(parts)


def build_family(f):
    """families/<id>.html, built from the family's reader packet by scripts/family_page.py."""
    import family_page
    family_page.build(sys.modules[__name__], f)


GLYPH_MACHINE = {"ok": '<svg class="glyph glyph--brick" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.2 6.4 4.9 9 9.8 3.2"/></svg>',
                 "open": '<svg class="glyph glyph--open" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="3.6"/></svg>'}


def withdrawn_from_family_html(fid, root):
    """Manuscripts listed under this family when the release was published and withdrawn since."""
    wd = [m for m in MANUSCRIPTS if m["status"] == "withdrawn" and m.get("family") == fid]
    if not wd:
        return ""
    arts = "".join(
        f'<article class="wd" id="{esc(m["id"])}"><h4 class="wd__title"><a href="{root}papers/{esc(m["id"])}.html">{ms_title_html(m)}</a></h4>'
        f'<div class="wd__note md-math">{md_paragraphs(m.get("withdrawal_note") or "")}</div>'
        f'<p class="wd__when">{esc(C("paper.withdrawn_on", date=date_words(m.get("withdrawn_on")) or ""))}</p></article>' for m in wd)
    then = tex_plain(wd[0].get("family_title_on_release_day") or FAM[fid]["title"])
    return (f'<div class="wds"><h3 class="h3" id="h-withdrawn">{esc(C("family.withdrawn_heading"))}</h3>'
            f'<p class="intro small">{esc(C("family.withdrawn_intro", title=then))}</p>{arts}</div>')


def finite_checks_html(f, root):
    """Finite parts of this family's papers decided by exact code, each in the checker's own
    terms. A check that does not decide says nothing against the result."""
    words = C("family.finite_words")
    items = []
    for v in sourced_all(f, "finite_checks"):
        for c in v["value"]:
            m = MS.get(c.get("manuscript") or "")
            paper = f' <a href="{root}papers/{esc(m["id"])}.html">{ms_title_html(m)}</a>' if m else ""
            scope = f', {esc(c["scope"])}' if c.get("scope") else ""
            state = "ok" if c["verdict"] == "certified" else "open"
            detail = (f'<details class="fam-fold"><summary>{esc(C("family.finite_detail"))}</summary>'
                      f'<p class="small">{esc(c["detail"])}</p></details>') if c.get("detail") else ""
            undecided = f' <span class="fc__plain">{esc(C("family.finite_undecided_note"))}</span>' if c["verdict"] == "refused" else ""
            items.append(f'<li class="fc fc--{state}">{GLYPH_MACHINE[state]}<div><p class="fc__v"><strong>{esc(words.get(c["verdict"], c["code"]))}</strong>{scope}.{paper}</p>'
                         f'<p class="fc__text">{esc(c.get("text") or "")}{undecided}</p>{detail}'
                         f'<p class="fc__src">{esc(C("family.finite_their_word", code=c["code"]))} {credit_link(v["source"], root)}, {esc(c["id"])}. '
                         f'<a class="ext" href="{esc(c["url"])}" rel="noopener">{esc(C("sources.record_link"))}</a></p></div></li>')
    if not items:
        return ""
    return (f'<h3 class="h3" id="h-finite">{esc(C("family.finite_heading"))}</h3><p class="intro small">{ctext(C("family.finite_intro"))}</p>'
            f'<ul class="fcs">{"".join(items)}</ul>')


def other_assistant_html(f, root):
    """Checks of this family's steps in another proof assistant, quoted with attribution."""
    items = []
    for v in sourced_all(f, "hol_checks"):
        for c in v["value"]:
            items.append(
                f'<li class="fc fc--ok">{GLYPH_MACHINE["ok"]}<div><p class="fc__v"><strong>{esc(C("family.hol_card", card=c["card"]))}</strong> {esc(c["certifies"])}</p>'
                f'<p class="fc__text">{esc(C("family.hol_relation"))} {esc(c["relation"])}</p>'
                f'<p class="fc__src">{esc(C("family.hol_runs", warm=c["warm"], cold=c["cold"]))} '
                f'{credit_link(v["source"], root)}. <a class="ext" href="{esc(c["url"])}" rel="noopener">{esc(C("family.hol_card_link"))}</a></p></div></li>')
    if not items:
        return ""
    return (f'<h3 class="h3" id="h-hol">{esc(C("family.hol_heading"))}</h3><p class="intro small">{ctext(C("family.hol_intro"))}</p>'
            f'<ul class="fcs">{"".join(items)}</ul>')


def build_paper(m):
    slug = m["id"]
    rel = f"papers/{slug}.html"
    root = "../"
    fam = FAM.get(m.get("family") or "")
    title_plain = tex_plain(m["title"])
    items = []
    if fam:
        di = DISC_OF[fam["id"]]
        tr = trail(root, [(esc(DISCIPLINES[di]["name"]), f'{root}index.html#o=d:{DISC_SLUG[di]}'),
                          (fam_title_html(fam), f'{root}families/{fam["id"]}.html'), (ms_title_html(m), None)])
        if m.get("family_on_release_day"):
            then = tex_plain(m.get("family_title_on_release_day") or fam["title"])
            items.append(f'<p class="lede">{esc(C("paper.in_result_withdrawn", id=fam["id"], title=then))} <a href="{root}families/{fam["id"]}.html#{esc(slug)}">{esc(C("paper.see_result_now"))}</a></p>')
        else:
            items.append(f'<p class="lede">{esc(C("paper.in_result", id=fam["id"], title=tex_plain(fam["title"])))} <a href="{root}families/{fam["id"]}.html#{esc(slug)}">{esc(C("paper.read_in_result"))}</a></p>')
    else:
        tr = trail(root, [(ms_title_html(m), None)])
    notes = ""
    if m["status"] == "withdrawn":
        notes += f'<div class="note note--warn"><p class="note__h">{esc(C("family.withdrawal_note"))}</p><div class="md-math">{md_paragraphs(m.get("withdrawal_note") or "")}</div><p>{esc(C("paper.withdrawn_on", date=m.get("withdrawn_on") or ""))}</p></div>'
    if m["status"] == "previous-edition" and m.get("superseded_by") in MS:
        cur = MS[m["superseded_by"]]
        notes += f'<div class="note"><p>{C("family.superseded", link=f"<a href=\"{root}papers/{esc(cur["id"])}.html\">{ms_title_html(cur)}</a>")}</p></div>'
    if m.get("version_note"):
        notes += f'<div class="note"><p class="note__h">{esc(C("family.version_note"))}</p><div class="md-math">{md_paragraphs(m["version_note"])}</div></div>'
    links = [pdf_button(m, "btn btn--primary")]
    if m.get("archived_pdf"):
        links.append(f'<a class="btn btn--ghost ext" href="{esc(m["archived_pdf"])}" rel="noopener">{esc(C("paper.archived"))}</a>')
    stm = ""
    if m.get("statements"):
        conv = TexConv(m, root)
        heads = headline_statements(m)
        if heads:
            stm = f'<section class="band band--tight"><h2 class="h2">{esc(C("family.headline_heading"))}</h2>{"".join(render_paper_statement(m, st, root, conv) for st in heads)}</section>'
    date = esc(C("paper.dated", date=m["date"])) if m.get("date") else ""
    body = f"""<div class="frame page page--narrow">
{tr}
<header class="phead">
 <p class="phead__kicker">{esc(status_label(m['status']))}</p>
 <h1 class="phead__title">{ms_title_html(m)}</h1>
 <p class="phead__facts">{date}</p>
 <p class="actions">{''.join(links)}</p>
</header>
{''.join(items)}
{notes}
<section class="band band--tight"><h2 class="h2">{esc(C('paper.abstract'))}</h2><div class="prose tex-auto">{rich(m.get('abstract') or '')}</div></section>
{stm}
</div>
{macros_script([slug])}"""
    desc = tex_plain(m.get("abstract") or m["title"])
    write_page(rel, page(rel, title_plain, desc, body, page_type="article"), index=(m["status"] == "current"))


def record_items(items):
    return "; ".join(C("statement.record_item", verdict=v, name=n_, date=d) if d else C("statement.record_item_nodate", verdict=v, name=n_) for v, n_, d in items)


def review_records(sid):
    """(statement review, independent replay) as short sentences for the card and the
    reading section: the recorded values from contributions and community findings, or
    'none recorded' when there are none."""
    checks = [(c["verdict"] or C("statement.record_no_verdict"), c["name"], c["date"]) for c in CONTRIB["checks"].get(sid, [])]
    review = C("statement.review_recorded", items=record_items(checks)) if checks else C("statement.review_none")
    reps = [(r["verdict"] or C("statement.record_no_verdict"), r["name"], r["date"]) for r in CONTRIB["replays"].get(sid, [])]
    for f_ in findings_for(sid=sid, kinds={"replay-pass", "replay-fail"}):
        e = COMMUNITY["efforts"].get(f_["effort"], {})
        kinds = C("community.finding_kinds")
        reps.append((kinds.get(f_["kind"], f_["kind"]) if isinstance(kinds, dict) else f_["kind"], credit_names(e) or e.get("name", ""), f_.get("date") or ""))
    rerun_kinds = C("statement.rerun_kinds")
    for v in sourced_all(ST.get(sid) or {}, "replay"):
        rv = v["value"]
        reps.append((rerun_kinds.get(rv["verdict"], rv["verdict"]) if isinstance(rerun_kinds, dict) else rv["verdict"], source_credit(v["source"]), rv.get("date") or ""))
    replay = C("statement.replay_recorded", items=record_items(reps)) if reps else C("statement.replay_none_short")
    return review, replay


def receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html, pairing, *, standalone=False):
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    label = (stmt.get("labels") or [stmt["id"]])[0]
    vtext = vocab_text(stmt)
    if paper_st:
        kind = esc(paper_st["display"]) + (f' <span class="rc__sttitle">({conv.text(paper_st["title"], inline=True)})</span>' if paper_st.get("title") else "")
        paper_body = conv.blocks(paper_st["text"])
        loc = C("statement.card_locator", label=paper_st["label"], file=paper_st["file"], line=paper_st["line"]) if paper_st.get("label") else C("statement.card_locator_nolabel", file=paper_st["file"], line=paper_st["line"])
        paper_src = f'<p class="rc__src"><span class="tex-auto">{rich(paper_ms["title"])}</span></p><p class="rc__loc">{esc(loc)}</p>'
        paper_label = C("statement.card_paper_candidate")
    else:
        kind = ""
        paper_body = f'<p class="rc__none">{esc(C("statement.card_paper_abstain_" + pairing))}</p>'
        paper_src = ""
        paper_label = C("statement.card_paper_none")
    snippet = lean_snippet_html(stmt, lines_html, max_lines=18)
    axioms = ", ".join(stmt["comparator"]["permitted_axioms"]) or C("statements.none")
    note = C("statement.sorry_note_axiom") if stmt["declares_axiom"] else C("statement.sorry_note")
    hl = stmt["comparator"].get("definition_names") or []
    hole_note = ""
    if hl:
        hole_note = C("statement.card_holes_one", name=hl[0].split(".")[-1]) if len(hl) == 1 else C("statement.card_holes_many", n=len(hl), name=hl[0].split(".")[-1])
        hole_note = f'<p class="rc__note rc__note--hole">{ctext(hole_note)}</p>'
    review, replay = review_records(stmt["id"])
    cls = cover_class(stmt["id"])
    scope_line = C("statement.card_scope_stale") if COVER_STALE else C("statement.card_scope", label=cover_label(cls))
    shown_url = page_url.replace("https://", "")
    return f"""<div class="rc-wrap{' rc-wrap--solo' if standalone else ''}"><article class="rc" data-macros="{esc(paper_ms['id']) if paper_ms else ''}" aria-label="{esc(C('statement.card_heading'))}">
 <header class="rc__head">
  <p class="rc__brand">{MARK_SVG}<span translate="no">{esc(C('site.name'))}</span></p>
  <h2 class="rc__title md-math">{esc(label)}</h2>
  <p class="rc__fam">{esc(C('words.result').capitalize())} {esc(fam['id'] if fam else '')}: <span class="tex-auto">{rich(fam['title']) if fam else ''}</span></p>
 </header>
 <div class="rc__cols">
  <section class="rc__paper"><p class="rc__label">{esc(paper_label)}</p><p class="rc__kind">{kind}</p><div class="rc__fit"><div class="rc__body">{paper_body}</div></div>{paper_src}</section>
  <section class="rc__lean"><p class="rc__label">{esc(C('statement.card_lean'))}</p><div class="rc__fit"><pre class="lean lean--card"><code>{snippet}</code></pre></div><p class="rc__note">{ctext(note)}</p>{hole_note}</section>
 </div>
 <footer class="rc__foot">
  <p class="rc__status"><span class="rc__fact">{esc(scope_line)}</span><span class="rc__fact"><strong>{esc(review)}</strong></span><span class="rc__fact"><strong>{esc(replay)}</strong></span></p>
  <p class="rc__facts"><span class="rc__fact">{esc(vtext)}</span><span class="rc__fact">{esc(C('statement.card_axioms', axioms=axioms))}</span><span class="rc__fact">{esc(C('statement.card_commit', commit_short=COMMIT_SHORT))}</span><span class="rc__url">{esc(shown_url)}</span></p>
 </footer>
</article></div>"""


def upstream_line(path_rel: str, pattern: str):
    up = (ROOT / CFG.get("upstream_checkout", "")).resolve() if CFG.get("upstream_checkout") else None
    if not up or not (up / path_rel).exists():
        return None
    for k, line in enumerate((up / path_rel).read_text(encoding="utf-8").split("\n"), 1):
        if re.match(pattern, line):
            return k
    return None


_DECL_START = re.compile(r"^(?:@\[[^\]]*\]\s*)*(?:(?:private|protected|noncomputable|partial|scoped|local|unsafe)\s+)*"
                         r"(?:def|abbrev|structure|class|inductive|instance|axiom|opaque|theorem|lemma|notation|infixl?|infixr|prefix|postfix|macro|macro_rules|syntax|example)\b")


def decl_spans(stmt):
    """0-based inclusive line spans of each declaration in a challenge file, ending
    before the next top-level declaration, comment or namespace command."""
    lines = stmt["lean"].split("\n")
    starts = {d["line"] - 1 for d in stmt["declarations"]}
    spans = {}
    for d in stmt["declarations"]:
        a = d["line"] - 1
        b = a
        k = a + 1
        while k < len(lines):
            t = lines[k]
            top = not t.startswith((" ", "\t"))
            if k in starts:
                break
            if top and t.strip() and (_DECL_START.match(t) or re.match(r"^(?:end|namespace|section|open|variable|universe|set_option|attribute|#|/-|--)", t)):
                break
            b = k
            k += 1
        while b > a and not lines[b].strip():
            b -= 1
        spans[d["name"]] = (a, b)
    return spans, lines


def needed_definitions(stmt, cap=24):
    """Local vocabulary the checked statement mentions, followed through the bodies of
    what it mentions. Matching is by name in the source text, so a name reached only
    through notation or an open namespace can be missed; the full file stays below."""
    spans, lines = decl_spans(stmt)
    vocab = {v["name"]: v for v in stmt["vocabulary"] if v.get("name")}
    shorts = {}
    for full in vocab:
        shorts.setdefault(full.split(".")[-1], full)
    seeds = []
    for t in (stmt["comparator"]["theorem_names"] or stmt["theorems"][:1]):
        sp = spans.get(t)
        if sp:
            seeds.append("\n".join(lines[sp[0]:sp[1] + 1]).split(":=")[0])
    seeds.append(" ".join(n_.split(".")[-1] for n_ in stmt["comparator"].get("definition_names") or []))
    found, queue = [], list(seeds)
    while queue and len(found) < cap * 4:
        txt = queue.pop(0)
        for sn, full in shorts.items():
            if full in found:
                continue
            if re.search(r"(?<![\w'])" + re.escape(sn) + r"(?![\w'])", txt):
                found.append(full)
                sp = spans.get(full)
                if sp:
                    queue.append("\n".join(lines[sp[0]:sp[1] + 1]))
    found = [n_ for n_ in found if n_ in spans]
    found.sort(key=lambda n_: spans[n_][0])
    return found, spans, lines, vocab


def definitions_html(stmt, lines_html, cap=24):
    names, spans, lines, vocab = needed_definitions(stmt, cap)
    if not names:
        return ""
    items = []
    for full in names[:cap]:
        a, b = spans[full]
        h = a
        while h < b and ":=" not in lines[h] and not lines[h].rstrip().endswith(" where") and h - a < 3:
            h += 1
        head = "".join(f'<span class="ln" data-n="{i + 1}">{lines_html[i]}</span>' for i in range(a, h + 1))
        more = ""
        if b > h:
            bodyl = "".join(f'<span class="ln" data-n="{i + 1}">{lines_html[i]}</span>' for i in range(a, b + 1))
            more = f'<details class="decl__more"><summary>{esc(C("statement.def_show", n=b - a + 1))}</summary><pre class="lean lean--snippet"><code>{bodyl}</code></pre></details>'
        sn = full.rsplit(".", 1)
        ns_ = f'<span class="vocab__ns">{esc(sn[0])}.</span>' if len(sn) == 2 else ""
        items.append(f'<li class="decl"><p class="decl__name"><span class="vocab__kind">{esc(kind_word(vocab[full]["kind"]))}</span> <code>{ns_}{esc(sn[-1])}</code> <a class="vocab__line" href="#L{a + 1}">{esc(C("statement.line", line=a + 1))}</a></p><pre class="lean lean--snippet"><code>{head}</code></pre>{more}</li>')
    extra = f'<p class="muted small">{esc(C("statement.defs_more", n=len(names) - cap))}</p>' if len(names) > cap else ""
    return f'<h3 class="h3">{esc(C("statement.defs_heading"))}</h3><p class="intro">{esc(C("statement.defs_intro"))}</p><ul class="decls">{"".join(items)}</ul>{extra}'


def comparator_box_html(stmt):
    """What an accepted Comparator run under this configuration would establish, with
    the configuration's definition holes listed by name."""
    holes = stmt["comparator"].get("definition_names") or []
    if holes:
        hl = ", ".join(f"`{h.split('.')[-1]}`" for h in holes[:12]) + (C("statement.holes_more", n=len(holes) - 12) if len(holes) > 12 else "")
        holes_p = ctext(C("statement.comparator_box_holes", n=len(holes), names=hl))
    else:
        holes_p = esc(C("statement.comparator_box_noholes"))
    axioms = ", ".join(f"<code>{esc(a)}</code>" for a in stmt["comparator"]["permitted_axioms"]) or esc(C("statements.none"))
    return (f'<div class="note"><p class="note__h">{esc(C("statement.comparator_box_heading"))}</p>'
            f'<p>{ctext(C("statement.comparator_box_does"))}</p><p>{holes_p}</p>'
            f'<p>{esc(C("statement.comparator_box_axioms"))} {axioms}</p>'
            f'<p>{ctext(C("statement.comparator_box_not"))}</p></div>')


OG_DONE: dict = {}   # statement id -> (generic og block, per-statement og block)


def build_statement(stmt):
    sid = stmt["id"]
    rel = f"statements/{sid}.html"
    root = "../"
    page_url = BASE_URL + rel
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    label = (stmt.get("labels") or [sid])[0]
    lines_html = lean_lines(stmt["lean"])
    paper_ms, paper_st, pairing = pair_statement(stmt)
    conv = TexConv(paper_ms, root) if paper_ms else None
    card = receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html, pairing)
    # full card page for screenshots
    card_rel = f"cards/{sid}.html"
    card_body = receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html, pairing, standalone=True)
    write_page(card_rel, head(card_rel, label, label, noindex=True) + f'\n<body class="card-only" data-root="{root}">\n{card_body}\n{macros_script([paper_ms["id"]] if paper_ms else [])}\n</body></html>\n', index=False)
    # the selected claim: the paper's statement (a labelled candidate) ...
    if paper_st:
        loc = C("statement.card_locator", label=paper_st["label"], file=paper_st["file"], line=paper_st["line"]) if paper_st.get("label") else C("statement.card_locator_nolabel", file=paper_st["file"], line=paper_st["line"])
        paper_read = (f'<p class="claim__label">{esc(C("statement.card_paper_candidate"))}</p>'
                      f'<p class="claim__src"><a href="{esc(paper_statement_href(paper_ms["id"], paper_st, root) or (root + "papers/" + paper_ms["id"] + ".html"))}">{ms_title_html(paper_ms)}</a>. {esc(loc)}</p>'
                      + render_paper_statement(paper_ms, paper_st, root, conv, "claim"))
    else:
        paper_read = f'<p class="claim__label">{esc(C("statement.card_paper_none"))}</p><p class="muted">{esc(C("statement.card_paper_abstain_" + pairing))} <a href="#h-sbs">{esc(C("statement.all_statements_link"))}</a></p>'
    # ... the Lean statement with the definitions needed to read it ...
    snippet_full = lean_snippet_html(stmt, lines_html)
    defs = definitions_html(stmt, lines_html)
    holes = def_holes(stmt)
    holes_html = ""
    if holes:
        items = []
        for h_ in holes:
            if h_["url"]:
                link = f'<a class="ext" href="{esc(h_["url"])}" rel="noopener"><code>{esc(h_["file"])}</code></a>'
                items.append("<li>" + ctext(C("statement.hole_item", name=h_["short"], link="\x00")).replace("\x00", link) + "</li>")
            else:
                items.append("<li>" + ctext(C("statement.hole_item_nolink", name=h_["short"], module=stmt["comparator"].get("solution_module") or "")) + "</li>")
        holes_html = f'<h3 class="h3" id="h-holes">{esc(C("statement.holes_heading"))} <span class="count">{len(holes)}</span></h3><p class="intro">{ctext(C("statement.holes_intro"))}</p><ul class="holes">{"".join(items)}</ul>'
    # axiom note
    sol = stmt.get("solution") or []
    axiom = ""
    if stmt["declares_axiom"]:
        ax_line = next((d["line"] for d in stmt["declarations"] if d["kind"] == "axiom"), None)
        link = ""
        if sol:
            sline = upstream_line("lean/" + sol[0]["file"], r"^\s*theorem\s+" + re.escape(sol[0]["declaration"].split(".")[-1]) + r"\b")
            href = sol[0]["url"] + (f"#L{sline}" if sline else "")
            link = f'<a class="ext" href="{esc(href)}" rel="noopener">{esc(C("statement.axiom_solution_link"))}</a>'
        note = ctext(C("statement.axiom_note", line=ax_line, axioms=", ".join(stmt["comparator"]["permitted_axioms"]), solution_link="\x00"))
        note = note.replace("\x00", link)
        axiom = f'<div class="note"><p class="note__h">{esc(C("statement.axiom_heading"))}</p><p>{note}</p></div>'
    # ... and the scope record with the review and replay states.
    review, replay = review_records(sid)
    # The two outside readers judge a family's Lean statements together, so their verdicts
    # and notes live on the family page; this page points there rather than restating them.
    readers_link = ""
    if fam and fam.get("readers_agreement") and fam["readers_agreement"] != "none":
        readers_link = (f'<p class="readers-link">{esc(C("statement.readers_intro"))} '
                        f'<a href="{root}families/{esc(fam["id"])}.html#h-readings">{esc(C("statement.readers_link"))}</a></p>')
    family_note = ""
    if fam and fam.get("lean_doc") and fam["lean_doc"].get("scope"):
        family_note = f'<details class="more"><summary>{esc(C("statement.scope_full", id=fam["id"]))}</summary><blockquote class="quote md-math">{md_paragraphs(fam["lean_doc"]["scope"])}<footer><a class="ext" href="{esc(fam["lean_doc"]["url"])}" rel="noopener">{esc(C("statement.scope_source", id=fam["id"]))}</a></footer></blockquote></details>'
    # supporting material
    sol_html = ", ".join(f'<a class="ext" href="{esc(x["url"])}" rel="noopener"><code>{esc(x["file"])}</code></a>' for x in sol) or f'<code>{esc(stmt["comparator"].get("solution_module") or "")}</code>'
    nm = stmt["non_mathlib_imports"]
    facts = [
        (C("statement.file_label"), f'<a class="ext" href="{esc(stmt["url"])}" rel="noopener"><code>{esc(stmt["file"])}</code></a>'),
        (C("statement.main_key"), esc(C("statement.main_yes") if stmt["main_result"] else C("statement.main_no", id=(stmt.get("families") or [""])[0]))),
        (C("statement.solution"), sol_html),
        (C("statement.permitted_axioms"), ", ".join(f"<code>{esc(a)}</code>" for a in stmt["comparator"]["permitted_axioms"]) + f'<span class="dl__note">{esc(C("statement.permitted_axioms_note"))}</span>'),
        (C("statement.imports"), ", ".join(f"<code>{esc(a)}</code>" for a in stmt["imports"])),
        (C("statement.non_mathlib"), ", ".join(f"<code>{esc(a)}</code>" for a in nm) if nm else esc(C("statements.none"))),
        (C("statement.vocab_key"), esc(vocab_text(stmt))),
        (C("statement.lines"), num(stmt["statement_lines"])),
        (C("statement.nanoda_key"), esc(C("statement.nanoda_yes") if stmt["comparator"].get("enable_nanoda") else C("statement.nanoda_no"))),
    ]
    dl = "".join(f"<div><dt>{esc(k)}</dt><dd>{v}</dd></div>" for k, v in facts)
    # The file view's "What you must check" panel lists every local declaration, in the order
    # the theorem reaches them, so the page no longer repeats them in a separate fold.
    paper_cols = []
    for slug in stmt.get("papers") or []:
        m = MS.get(slug)
        if not m:
            continue
        cv = TexConv(m, root)
        heads = headline_statements(m)
        inner = "".join(render_paper_statement(m, st, root, cv, "pst") for st in heads) or f'<p class="muted">{esc(C("family.no_headline"))}</p>'
        paper_cols.append(f'<div class="sbs__paper"><h3 class="h3"><a href="{root}papers/{esc(slug)}.html">{ms_title_html(m)}</a></h3>{inner}</div>')
    import lean_render  # the whole file, every resolved name linked, beside "What you must check"
    file_section = lean_render.file_section(stmt, commit=COMMIT, root=root)
    checks = CONTRIB["checks"].get(sid, [])
    replays = CONTRIB["replays"].get(sid, [])
    checks_html = "".join(f'<li><strong>{esc(c["name"])}</strong>{(": " + esc(c["verdict"])) if c.get("verdict") else ""}{(", " + esc(c["date"])) if c.get("date") else ""} <a class="ext small" href="{esc(REPO + "/blob/main/" + c["path"])}" rel="noopener">{esc(C("statement.record_link"))}</a></li>' for c in checks)
    replays_html = "".join(f'<li><strong>{esc(c["name"])}</strong>{(": " + esc(c["verdict"])) if c.get("verdict") else ""}{(", " + esc(c["date"])) if c.get("date") else ""} <a class="ext small" href="{esc(REPO + "/blob/main/" + c["path"])}" rel="noopener">{esc(C("statement.record_link"))}</a></li>' for c in replays)
    replay_url = issue_url("replay", C("issues.replay", statement=sid), statement=sid)
    suggest = suggest_url(page_url, label, statement_label=label)
    trail_items = []
    if fam:
        di = DISC_OF[fam["id"]]
        trail_items = [(esc(DISCIPLINES[di]["name"]), f'{root}index.html#o=d:{DISC_SLUG[di]}'), (fam_title_html(fam), f'{root}families/{fam["id"]}.html')]
    trail_items.append((f'<span class="md-math">{esc(label)}</span>', None))
    where = ""
    if fam:
        where = f'{esc(C("statement.in_result"))} <a href="{root}families/{fam["id"]}.html">{esc(C("words.result").capitalize())} {esc(fam["id"])}: {fam_title_html(fam)}</a>. '
    where += f'{esc(C("statement.file_label"))} <a class="ext" href="{esc(stmt["url"])}" rel="noopener"><code>{esc(stmt["file"])}</code></a>.'
    where += f' <a href="{root}index.html#o=l:{quote(sid)}">{esc(C("words.show_on_map"))}</a>'
    reasons = REVIEW_REASONS.get(sid) or []
    reasons_html = (f'<div class="note"><p class="note__h">{esc(C("statement.reasons_heading"))}</p><ul class="rq__why">' + "".join(f'<li class="md-math">{ctext(t)}</li>' for t in reasons) + '</ul></div>') if reasons else ""
    problems = findings_for(sid=sid, kinds={'error-reported', 'correction', 'replay-fail'})
    more_finds = findings_for(sid=sid, kinds={'explanation', 'commentary', 'follow-up-result'})
    body = f"""<div class="frame page">
{trail(root, trail_items)}
<header class="phead">
 <p class="phead__kicker">{esc(C('statement.trail_label'))}</p>
 <h1 class="phead__title md-math">{esc(label)}</h1>
 <p class="phead__facts">{where}</p>
 <p class="phead__facts">{esc(C('statement.main_yes') if stmt['main_result'] else C('statement.main_no', id=(stmt.get('families') or [''])[0]))}</p>
 <p class="actions"><a class="btn btn--primary ext" href="{esc(check_url(sid))}" rel="noopener">{esc(C('statement.check_button'))}</a><a class="btn btn--ghost" href="#h-share">{esc(C('statement.share_jump'))}</a><a class="btn btn--quiet ext" href="{esc(suggest)}" rel="noopener">{esc(C('words.suggest_change'))}</a></p>
</header>
{('<section class="band band--tight"><div class="note note--warn"><p class="note__h">' + esc(C('sources.problems_heading')) + '</p>' + findings_list(problems, root) + '</div></section>') if problems else ''}
<section class="band band--tight claim" aria-labelledby="h-claim">
 <h2 class="h2" id="h-claim">{esc(C('statement.claim_paper_heading'))}</h2>
 {paper_read}
</section>
<section class="band band--tight claim" aria-labelledby="h-lean-read">
 <h2 class="h2" id="h-lean-read">{esc(C('statement.claim_lean_heading'))}</h2>
 <p class="intro">{esc(C('statement.claim_lean_intro'))}</p>
 <pre class="lean lean--snippet lean--read"><code>{snippet_full}</code></pre>
 <p class="leanc__note">{ctext(C('statement.sorry_note_axiom') if stmt['declares_axiom'] else C('statement.sorry_note'))}</p>
 {defs}
 {holes_html}
 {axiom}
 {comparator_box_html(stmt)}
</section>
<section class="band band--tight claim" aria-labelledby="h-scope">
 <h2 class="h2" id="h-scope">{esc(C('statement.claim_scope_heading'))}</h2>
 {independent_reruns_html(stmt, root)}
 {readers_link}
 {coverage_html(sid)}
 {family_note}
 <p class="review-status">{esc(review)}</p>
 <p class="review-status">{esc(replay)}</p>
</section>
<section class="band band--card" aria-labelledby="h-share">
 <h2 class="h2" id="h-share">{esc(C('statement.card_heading'))}</h2>
 <p class="intro">{esc(C('statement.card_intro'))}</p>
 {card}
 <p class="card-tools"><button class="btn btn--ghost copy" type="button" data-copy-text="{esc(page_url)}">{esc(C('statement.copy_link'))}</button><span class="muted small">{esc(C('statement.card_pairing'))}</span></p>
</section>
<section class="band supporting" aria-labelledby="h-support">
 <h2 class="h2" id="h-support">{esc(C('statement.support_heading'))}</h2>
 <details class="more" id="sbs"><summary><span class="h3" id="h-sbs">{esc(C('statement.paper_heading'))}</span></summary><p class="intro">{esc(C('statement.paper_intro'))}</p><div class="sbs__all">{''.join(paper_cols)}</div></details>
 <details class="more"><summary><span class="h3">{esc(C('statement.facts_heading'))}</span></summary><dl class="dl">{dl}</dl></details>
 {file_section}
</section>
<section class="band explain-box" aria-labelledby="h-checks">
 <h2 class="h2" id="h-checks">{esc(C('statement.checks_heading'))}</h2>
 {f'<ul>{checks_html}</ul>' if checks else f'<p>{esc(C("statement.checks_none"))}</p>'}
 <h3 class="h3">{esc(C('statement.replays_heading'))}</h3>
 {f'<ul>{replays_html}</ul>' if replays else f'<p>{esc(C("statement.replays_none"))}</p>'}
 {('<h3 class="h3">' + esc(C('sources.statement_more')) + '</h3>' + findings_list(more_finds, root)) if more_finds else ''}
 {reasons_html}
 <p class="actions"><a class="btn btn--ghost ext" href="{esc(check_url(sid))}" rel="noopener">{esc(C('statement.check_button'))}</a><a class="btn btn--ghost ext" href="{esc(replay_url)}" rel="noopener">{esc(C('statement.replay_button'))}</a><a class="btn btn--quiet ext" href="{esc(suggest)}" rel="noopener">{esc(C('words.suggest_change'))}</a></p>
</section>
</div>
{macros_script(list(dict.fromkeys(([paper_ms['id']] if paper_ms else []) + list(stmt.get('papers') or []))))}"""
    desc = f"{label}. " + (C("statement.main_yes") if stmt["main_result"] else C("statement.main_no", id=(stmt.get("families") or [""])[0])) + " " + vocab_text(stmt) + "."
    # Social image: the generic card unless this build renders the statement's own card
    # successfully; main() swaps the block in only after checking the file it produced.
    generic = generic_og_meta()
    own = og_meta(BASE_URL + f"og/{sid}.png", C("statement.og_alt", label=label))
    OG_DONE[sid] = (generic, own)
    lean_head = f'<link rel="stylesheet" href="{root}assets/lean.css">\n<script defer src="{root}assets/lean.js"></script>'
    write_page(rel, page(rel, f"{label} (Lean)", desc, body, og_block=generic, page_type="article", extra_head=lean_head))


# ------------------------------------------------------------------- home


def map_data():
    fams = []
    for f in FAMILIES:
        status, _ = family_exposition_status(f["id"])
        mss = [MS[s] for s in f["manuscripts"] if s in MS]
        grade, mixed = fam_cover_grade(f)
        rev = reviewed_explanations(f["id"])
        fams.append({
            "id": f["id"],
            "t": f["title"],
            "p": tex_plain(f["title"]),
            "d": DISC_OF[f["id"]],
            "m": [[m["title"], m.get("date") or "", m["pdf_url"].replace(BASE_BLOB, ""), m["id"]] for m in mss],
            # label, main result, local vocabulary count, id, draft scope class (or null)
            "s": [[(ST[s].get("labels") or [s])[0], 1 if ST[s]["main_result"] else 0, ST[s]["vocabulary_count"], s, cover_class(s)] for s in f["statements"] if s in ST],
            "v": fam_max_vocab(f),
            "c": FAM_CITES[f["id"]],
            "b": FAM_CITED_BY[f["id"]],
            "k": fam_cited_by_ms(f),
            "x": {"none": 0, "progress": 1, "reviewed": 2}[status],
            "e": explanation_rel(rev[0], f["id"]) if rev else None,
            "w": len(COMMUNITY["by_family"].get(f["id"], [])) + len(COMMUNITY["efforts_by_family"].get(f["id"], [])),
            "ty": (sourced(f, "type") or {}).get("value"),
            "ti": (sourced(f, "tier") or {}).get("value"),
            "g": grade,
            "gm": 1 if mixed else 0,
            "rd": f.get("readers_agreement") or "none",
        })
    vocab = sorted(v for v in (x["v"] for x in fams) if v is not None)
    return {
        "blob": BASE_BLOB,
        "disciplines": [{"name": d["name"], "slug": DISC_SLUG[i], "families": d["families"]} for i, d in enumerate(DISCIPLINES)],
        "families": fams,
        "sizeBins": size_bins(vocab),
        "coverStale": COVER_STALE,
        "coverClasses": COPY["statement"]["coverage_classes"],
    }


def size_bins(vals):
    """Four bins for families with Lean: no local vocabulary (0) and three quantile bins above it."""
    pos = [v for v in vals if v > 0]
    if not pos:
        return []
    q = lambda p: pos[min(len(pos) - 1, int(p * len(pos)))]
    a, b = q(1 / 3), q(2 / 3)
    return [[0, 0], [1, a], [a + 1, b], [b + 1, None]]


# Labels and computation notes for every summary number. Prose lives in copy.json
# under numbers.items; this list only fixes the order.
NUMBER_ORDER = ["families", "disciplines", "manuscripts_current", "manuscripts_withdrawn", "manuscripts_previous_editions",
                "statements_lean", "statements_lean_main_results", "main_result_declarations", "families_with_lean",
                "manuscripts_with_lean", "lean_statements_pure_mathlib", "lean_statements_no_local_vocabulary", "lean_statements_with_custom_vocabulary",
                "lean_statements_importing_non_mathlib", "lean_statements_declaring_axioms", "lean_definition_holes", "lean_vocabulary_total",
                "lean_vocabulary_median", "lean_vocabulary_max", "internal_citation_edges", "manuscripts_citing_collection",
                "manuscripts_citing_unformalised_collection_results", "external_works_cited", "external_citations"]
HOME_NUMBERS = ["families", "manuscripts_current", "statements_lean", "statements_lean_main_results",
                "families_with_lean", "manuscripts_with_lean", "internal_citation_edges", "external_works_cited"]


def num_words(n):
    words = "zero one two three four five six seven eight nine ten".split()
    return words[n] if isinstance(n, int) and 0 <= n < len(words) else num(n)


def number_item(key):
    items = COPY["numbers"]["items"]
    it = items.get(key, {})
    return it


def work_name(i):
    hl = SUMMARY.get("highlights", {}).get("most_cited_outside_works", [])
    if i >= len(hl):
        return ""
    w = hl[i]
    title = clean_ref_text(w.get("title") or w.get("text") or "")
    au = clean_ref_text(w.get("authors") or "")
    if au and "authors" not in au.lower():
        sur = au.split(",")[0].split(" and ")[0].strip()
        return f"{sur}’s {title}"
    return title if title.lower().startswith("the ") else title


def build_home(md):
    """The treemap with its colour-by lenses, at tiles.html ("Every family as a tile").
    index.html is the release universe, written by scripts/build_universe.py; it is
    registered here because the sitemap is written before that script runs."""
    rel = "tiles.html"
    PAGES.append("index.html")
    root = ""
    s = SUMMARY
    lede = C("home.lede", families=s["families"], disciplines=s["disciplines"], manuscripts=s["manuscripts_current"],
             lean=s["statements_lean"], families_with_lean=s["families_with_lean"])
    nums = []
    for k in HOME_NUMBERS:
        it = number_item(k)
        nums.append(f'<li><a href="numbers.html#{k}"><span class="num__v">{num(s[k])}</span><span class="num__l">{esc(it.get("label", k))}</span></a></li>')
    # index of every result
    idx = []
    for i, d in enumerate(DISCIPLINES):
        lis = "".join(f'<li><a href="families/{fid}.html">{fam_title_html(FAM[fid])}</a></li>' for fid in d["families"] if fid in FAM)
        idx.append(f'<section class="idx__d" id="idx-{DISC_SLUG[i]}"><h3 class="h3">{esc(d["name"])} <span class="count">{len(d["families"])}</span></h3><ul>{lis}</ul></section>')
    ov = [("lean", "home.overlay_lean"), ("readers", "home.overlay_readers"), ("covers", "home.overlay_covers"), ("type", "home.overlay_type"), ("tier", "home.overlay_tier"), ("community", "home.overlay_community"), ("size", "home.overlay_size"), ("citations", "home.overlay_citations"), ("explained", "home.overlay_explained")]
    ov_btns = "".join(f'<button type="button" class="seg__b" data-overlay="{k}" aria-pressed="{"true" if k == "lean" else "false"}">{esc(C(lab))}</button>' for k, lab in ov)
    strings = {k: v for k, v in COPY["home"].items()}
    strings.update({"manuscript": C("words.manuscript"), "manuscripts": C("words.manuscripts"),
                    "lean_statement": C("words.lean_statement"), "lean_statements": C("words.lean_statements"),
                    "no_lean": C("words.no_lean"), "main_result": C("words.main_result"),
                    "supporting_result": C("words.supporting_result"), "result": C("words.result"), "results": C("words.results"),
                    "pure_ids": sorted(PURE_MATHLIB)})
    body = f"""<section class="atlas" aria-labelledby="h-atlas">
 <div class="atlas__panel">
  <div class="atlas__intro">
   <h1 class="atlas__title" id="h-atlas">{esc(C('home.title'))}</h1>
   <p class="atlas__lede">{esc(lede)}</p>
   <p class="actions"><a class="btn btn--primary" href="index.html">{esc(C('home.cta_map'))}</a><a class="btn btn--ghost" href="#catalogue">{esc(C('home.cta_browse'))}</a></p>
  </div>
  <div class="atlas__controls">
   <div class="msearch">
    <label class="vh" for="map-search">{esc(C('home.search_label'))}</label>
    <input id="map-search" class="msearch__input" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(C('home.search_placeholder'))}" role="combobox" aria-expanded="false" aria-controls="map-search-list" aria-autocomplete="list">
    <ul class="msearch__list" id="map-search-list" role="listbox" aria-label="{esc(C('home.search_label'))}" hidden></ul>
   </div>
   <div class="seg" role="group" aria-label="{esc(C('home.overlay_label'))}"><span class="seg__label">{esc(C('home.overlay_label'))}</span><div class="seg__row">{ov_btns}</div></div>
   <div class="legend" aria-live="polite"></div>
  </div>
  <nav class="where" aria-label="{esc(C('home.where_label'))}"></nav>
  <div class="card" hidden tabindex="-1"></div>
  <section class="mlist" aria-labelledby="mlist-h"><h2 class="mlist__h" id="mlist-h" tabindex="-1"></h2><ul class="mlist__ul"></ul></section>
 </div>
 <div class="atlas__stage">
  <div class="field" role="group" aria-label="{esc(C('home.map_heading'))}" aria-describedby="map-help map-area"><noscript><p class="field__noscript">{esc(C('home.no_js'))} <a href="#catalogue">{esc(C('home.cta_browse'))}</a></p></noscript></div>
  <p class="caption__area" id="map-area">{esc(C('home.area_note'))}</p>
  <p class="caption" id="map-help" aria-live="polite">{esc(C('home.map_help'))}</p>
 </div>
</section>
<section class="frame band" aria-labelledby="h-numbers">
 <h2 class="h2" id="h-numbers">{esc(C('home.numbers_heading'))}</h2>
 <p class="intro">{esc(C('home.numbers_intro'))}</p>
 <ul class="nums">{''.join(nums)}</ul>
 <p><a href="numbers.html">{esc(C('home.numbers_more'))}</a></p>
</section>
<section class="frame band" aria-labelledby="h-credit">
 <h2 class="h2" id="h-credit">{esc(C('home.credit_heading'))}</h2>
 <div class="cols2">
  <div><h3 class="h3"><a href="citations-within.html">{esc(C('home.credit_within'))}</a></h3><p>{esc(C('home.credit_within_text'))}</p></div>
  <div><h3 class="h3"><a href="references-outside.html">{esc(C('home.credit_outside'))}</a></h3><p>{esc(C('home.credit_outside_text', works=s['external_works_cited'], top1=work_name(0), top2=work_name(1)))}</p></div>
  {('<div><h3 class="h3"><a href="sources.html">' + esc(C('home.credit_community')) + '</a></h3><p>' + esc(C('home.credit_community_text', efforts=len(COMMUNITY['list']), people=len({(a.get('name') or a.get('handle')) for e in COMMUNITY['list'] for a in (e.get('authors') or [])}), findings=len(COMMUNITY['findings']))) + '</p></div>') if COMMUNITY['list'] else ''}
 </div>
</section>
<section class="frame band idx" id="catalogue" aria-labelledby="h-index" tabindex="-1">
 <h2 class="h2" id="h-index">{esc(C('home.index_heading'))}</h2>
 <p class="intro">{esc(C('home.index_intro', families=s['families']))}</p>
 <div class="idx__grid">{''.join(idx)}</div>
</section>
{json_script('map-strings', strings)}"""
    extra = '<link rel="preload" href="data/atlas-map.json" as="fetch" crossorigin>\n<script defer src="assets/map.js"></script>'
    write_page(rel, page(rel, C("home.title"), C("home.description"), body, current=None, extra_head=extra, main_class="main--home"))


def review_queue_html(root):
    """Where a careful reading is most useful: the first files of the review order,
    each with its reasons in words. The order allocates reading time only."""
    rq = SUMMARY.get("review_queue") or {}
    first = [x for x in (rq.get("first") or []) if x in ST]
    if not first:
        return ""
    items = []
    for sid in first:
        st = ST[sid]
        fid = (st.get("families") or [None])[0]
        f = FAM.get(fid)
        fam_html = f' <span class="muted small">{esc(C("words.result").capitalize())} {esc(fid)}: <a href="{root}families/{esc(fid)}.html">{fam_title_html(f)}</a></span>' if f else ""
        why = "".join(f'<li class="md-math">{ctext(t)}</li>' for t in REVIEW_REASONS.get(sid) or [])
        items.append(f'<li><a href="{root}statements/{esc(sid)}.html"><span class="md-math">{esc((st.get("labels") or [sid])[0])}</span></a>{fam_html}{("<ul class=" + chr(34) + "rq__why" + chr(34) + ">" + why + "</ul>") if why else ""}</li>')
    rule = f'<p class="muted small">{esc(rq["rule"])}</p>' if rq.get("rule") else ""
    return (f'<section class="band band--tight" id="careful-reading" aria-labelledby="h-rq"><h2 class="h2" id="h-rq">{esc(C("explain.queue_heading"))}</h2>'
            f'<p class="intro">{esc(C("explain.queue_intro", n=len(first), flagged=rq.get("flagged", len(first))))}</p><ol class="rq">{"".join(items)}</ol>{rule}'
            f'<p class="muted small">{esc(C("explain.queue_not_verdict"))}</p></section>')


def build_explain():
    """The Families page: every family as a list first, with its Lean statements, the
    re-runs outside groups report accepting, the outside readers' agreement, withdrawn
    papers and explanation status; the filters above it; the careful-reading queue after."""
    rel = "explain.html"
    root = ""
    rows = []
    counts = Counter()
    for f in FAMILIES:
        st, ex = family_exposition_status(f["id"])
        counts[st] += 1
        di = DISC_OF[f["id"]]
        claim = issue_url("claim", C("issues.claim", id=f["id"], title=tex_plain(f["title"])), family=f["id"])
        rev = reviewed_explanations(f["id"])
        if rev:
            action = f'<a class="btn btn--small" href="{explanation_rel(rev[0], f["id"])}">{esc(C("explain.read"))}</a>'
        else:
            action = f'<a class="btn btn--small ext" href="{esc(claim)}" rel="noopener">{esc(C("explain.claim"))}</a>'
        who = f'<span class="muted small"> {esc(", ".join(e["name"] for e in ex))}</span>' if ex else ""
        lean = [ST[x] for x in f["statements"] if x in ST]
        accepted = sum(1 for x in lean if any(v["value"].get("verdict") == "accepted" for v in sourced_all(x, "replay")))
        runs = C("explain.runs_of", k=accepted, n=len(lean)) if lean else ""
        readers = f.get("readers_agreement") or "none"
        readers_html = f'<span class="rd-{esc(readers)}">{esc(C("explain.readers_" + readers))}</span>' if lean else ""
        withdrawn = sum(1 for m in MANUSCRIPTS if m["status"] == "withdrawn" and m.get("family") == f["id"])
        rows.append(f'<tr data-d="{DISC_SLUG[di]}" data-s="{st}"><td class="t-title"><a href="families/{f["id"]}.html">{fam_title_html(f)}</a></td>'
                    f'<td>{esc(DISCIPLINES[di]["name"])}</td>'
                    f'<td class="t-num">{num(len(lean)) if lean else ""}</td>'
                    f'<td class="t-num">{esc(runs)}</td>'
                    f'<td>{readers_html}</td>'
                    f'<td class="t-num">{num(withdrawn) if withdrawn else ""}</td>'
                    f'<td><span class="st st--{st}">{esc(C("explain.status_" + st))}</span>{who}</td>'
                    f'<td>{action}</td></tr>')
    dbtns = [f'<button type="button" class="chip" data-filter-d="" aria-pressed="true">{esc(C("explain.all"))}</button>']
    for i, d in enumerate(DISCIPLINES):
        dbtns.append(f'<button type="button" class="chip" data-filter-d="{DISC_SLUG[i]}" aria-pressed="false">{esc(d["name"])} <span class="count">{len(d["families"])}</span></button>')
    sbtns = [f'<button type="button" class="chip" data-filter-s="" aria-pressed="true">{esc(C("explain.all"))}</button>']
    for k in ("none", "progress", "reviewed"):
        sbtns.append(f'<button type="button" class="chip" data-filter-s="{k}" aria-pressed="false">{esc(C("explain.status_" + k))} <span class="count">{counts[k]}</span></button>')
    # The invitation is said once, after the list, and quietly.
    invite_key = "explain.invite_all" if counts["none"] == len(FAMILIES) else "explain.invite"
    invite = (f'<p class="muted">{esc(C(invite_key, open=counts["none"], families=len(FAMILIES)))} {esc(C("explain.how"))} '
              f'<a class="ext" href="{esc(REPO + "/" + CFG["contributing_path"])}" rel="noopener">{esc(C("contribute.guide_link"))}</a></p>')
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('explain.title'))}</h1>
 <p class="lede">{esc(C('explain.lede', families=len(FAMILIES)))}</p>
</header>
<section class="band band--tight" aria-labelledby="h-list">
<h2 class="h2" id="h-list">{esc(C('explain.list_heading'))}</h2>
<div class="filters" data-filter-table="explain-table">
 <div class="filters__g"><p class="filters__h">{esc(C('explain.filter_discipline'))}</p><div class="chips">{''.join(dbtns)}</div></div>
 <div class="filters__g"><p class="filters__h">{esc(C('explain.filter_status'))}</p><div class="chips">{''.join(sbtns)}</div></div>
 <p class="filters__n muted" aria-live="polite" data-shown-template="{esc(C('explain.shown', n='{n}'))}">{esc(C('explain.shown', n=len(FAMILIES)))}</p>
</div>
<div class="table-wrap"><table class="tbl" id="explain-table">
 <thead><tr><th scope="col">{esc(C('explain.col_result'))}</th><th scope="col">{esc(C('explain.col_discipline'))}</th><th scope="col" class="t-num">{esc(C('explain.col_lean'))}</th><th scope="col" class="t-num">{esc(C('explain.col_runs'))}</th><th scope="col">{esc(C('explain.col_readers'))}</th><th scope="col" class="t-num">{esc(C('explain.col_withdrawn'))}</th><th scope="col">{esc(C('explain.col_status'))}</th><th scope="col"><span class="vh">{esc(C('explain.col_action'))}</span></th></tr></thead>
 <tbody>{''.join(rows)}</tbody>
</table></div>
{invite}
</section>
{review_queue_html(root)}
</div>"""
    write_page(rel, page(rel, C("explain.title"), C("explain.lede", families=len(FAMILIES)), body, current="explain"))


def build_statements_table():
    rel = "statements.html"
    rows = []
    for s in STATEMENTS:
        fid = s["families"][0] if s.get("families") else None
        f = FAM.get(fid)
        di = DISC_OF.get(fid)
        label = (s.get("labels") or [s["id"]])[0]
        nm = len(s["non_mathlib_imports"])
        nh = len(s["comparator"].get("definition_names") or [])
        rows.append(f'<tr data-q="{esc((label + " " + s["id"] + " " + (tex_plain(f["title"]) if f else "") + " " + (DISCIPLINES[di]["name"] if di is not None else "")).lower())}">'
                    f'<td class="t-title" data-v="{esc(label.lower())}"><a href="statements/{esc(s["id"])}.html"><span class="md-math">{esc(label)}</span></a><code class="t-id">{esc(s["id"])}</code></td>'
                    f'<td data-v="{esc(fid or "")}">{f"<a href=\"families/{fid}.html\">{fam_title_html(f)}</a>" if f else ""}</td>'
                    f'<td data-v="{esc(DISCIPLINES[di]["name"] if di is not None else "")}">{esc(DISCIPLINES[di]["name"] if di is not None else "")}</td>'
                    f'<td class="t-c" data-v="{1 if s["main_result"] else 0}">{esc(C("statements.yes") if s["main_result"] else C("statements.no"))}</td>'
                    f'<td class="t-num" data-v="{s["vocabulary_count"]}">{num(s["vocabulary_count"])}</td>'
                    f'<td class="t-num" data-v="{s["statement_lines"]}">{num(s["statement_lines"])}</td>'
                    f'<td class="t-num" data-v="{nm}">{num(nm) if nm else ""}</td>'
                    f'<td class="t-num" data-v="{nh}">{num(nh) if nh else ""}</td></tr>')
    cols = [("statement", "t"), ("result", "t"), ("discipline", "t"), ("main", "n"), ("vocab", "n"), ("lines", "n"), ("imports", "n"), ("holes", "n")]
    ths = "".join(f'<th scope="col" class="{"t-num" if t == "n" and k != "main" else ("t-c" if k == "main" else "")}" aria-sort="none"><button type="button" class="sort" data-sort="{i}" data-type="{t}">{esc(C("statements.col_" + k))}</button></th>' for i, (k, t) in enumerate(cols))
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('statements.title'))}</h1>
 <p class="lede">{esc(C('statements.lede', lean=SUMMARY['statements_lean'], main=SUMMARY['statements_lean_main_results']))}</p>
</header>
<div class="filters"><label class="vh" for="tbl-filter">{esc(C('statements.filter'))}</label><input id="tbl-filter" class="filter-input" type="search" placeholder="{esc(C('statements.filter'))}" data-filter-rows="stmt-table"><p class="filters__n muted" aria-live="polite" data-shown-template="{esc(C('statements.shown', n='{n}'))}">{esc(C('statements.shown', n=len(STATEMENTS)))}</p></div>
<div class="table-wrap"><table class="tbl tbl--sortable" id="stmt-table">
 <thead><tr>{ths}</tr></thead>
 <tbody>{''.join(rows)}</tbody>
</table></div>
</div>"""
    write_page(rel, page(rel, C("statements.title"), C("statements.lede", lean=SUMMARY["statements_lean"], main=SUMMARY["statements_lean_main_results"]), body, current="statements"))


def recompute_checks():
    """Recount headline numbers from the data files and compare with summary.json."""
    cur = [m for m in MANUSCRIPTS if m["status"] == "current"]
    checks = {
        "families": len(FAMILIES),
        "disciplines": len(DISCIPLINES),
        "manuscripts_current": len(cur),
        "manuscripts_withdrawn": sum(1 for m in MANUSCRIPTS if m["status"] == "withdrawn"),
        "manuscripts_previous_editions": sum(1 for m in MANUSCRIPTS if m["status"] == "previous-edition"),
        "statements_lean": len(STATEMENTS),
        "statements_lean_main_results": sum(1 for s in STATEMENTS if s["main_result"]),
        "families_with_lean": sum(1 for f in FAMILIES if f["statements"]),
        "manuscripts_with_lean": sum(1 for m in cur if m["has_lean"]),
        "lean_statements_declaring_axioms": sum(1 for s in STATEMENTS if s["declares_axiom"]),
        "lean_vocabulary_total": sum(s["vocabulary_count"] for s in STATEMENTS),
        "lean_vocabulary_max": max(s["vocabulary_count"] for s in STATEMENTS),
        "internal_citation_edges": len(GRAPH),
        "external_citations": sum(len(m.get("references") or []) for m in cur),
    }
    out = {}
    for k, v in checks.items():
        out[k] = v
        if SUMMARY.get(k) != v:
            warn(f"summary.json {k}={SUMMARY.get(k)} but the data files give {v}")
    return out


def build_numbers():
    rel = "numbers.html"
    s = SUMMARY
    defs = s.get("definitions", {})
    receipts = {r.get("key"): r for r in (s.get("metric_receipts") or []) if isinstance(r, dict) and r.get("key")}
    used_receipts = set()

    def receipt_html(key):
        r = receipts.get(key)
        if not r:
            return ""
        used_receipts.add(key)
        rows = []
        for field in ("unit", "universe", "rule", "source"):
            if r.get(field):
                val = f'<code>{esc(r[field])}</code>' if field == "source" else esc(r[field])
                rows.append(f'<div><dt>{esc(C("numbers.receipt_" + field))}</dt><dd>{val}</dd></div>')
        return f'<details class="receipt"><summary>{esc(C("numbers.receipt_heading"))}</summary><dl class="dl dl--receipt">{"".join(rows)}</dl></details>'

    items = []
    for k in NUMBER_ORDER:
        if k not in s or not isinstance(s[k], int):
            continue
        it = number_item(k)
        # Wording comes from copy.json, which owns every sentence on the site; the
        # data file's definition is the fallback for a number copy.json does not describe.
        d = it.get("definition") or defs.get(k) or defs.get(it.get("definition_key", "")) or ""
        extra = ""
        if k == "lean_vocabulary_max" and s.get("lean_vocabulary_max_statement") in ST:
            sid = s["lean_vocabulary_max_statement"]
            extra = f' <a href="statements/{esc(sid)}.html"><code>{esc(sid)}</code></a>'
        if k == "lean_statements_declaring_axioms" and s.get("lean_statements_declaring_axioms_ids"):
            extra = " " + ", ".join(f'<a href="statements/{esc(x)}.html"><code>{esc(x)}</code></a>' for x in s["lean_statements_declaring_axioms_ids"])
        if k == "lean_statements_pure_mathlib" and s.get("lean_statements_pure_mathlib_ids"):
            extra = " " + ", ".join(f'<a href="statements/{esc(x)}.html"><code>{esc(x)}</code></a>' for x in s["lean_statements_pure_mathlib_ids"])
        if k == "lean_definition_holes" and s.get("lean_statements_with_definition_holes"):
            extra = " " + ", ".join(f'<a href="statements/{esc(x)}.html"><code>{esc(x)}</code></a>' for x in s["lean_statements_with_definition_holes"])
        items.append(f"""<article class="numrow" id="{k}">
 <p class="numrow__v">{num(s[k])}</p>
 <div class="numrow__t">
  <h2 class="h3">{esc(it.get('label', k))}</h2>
  <p><span class="numrow__k">{esc(C('numbers.definition'))}.</span> {esc(d)}{extra}</p>
  <p><span class="numrow__k">{esc(C('numbers.how'))}.</span> {esc(it.get('how', ''))}</p>
  {receipt_html(k)}
 </div>
</article>""")
    # The draft scope reading, with its unclear class kept apart.
    sc = s.get("scope_coverage") or {}
    scope_html = ""
    if sc.get("classes"):
        if COVER_STALE:
            scope_body = f'<p>{esc(C("numbers.scope_stale"))}</p>'
        else:
            order = ["headline", "headline-part", "consequence", "weaker", "supporting", "unclear"]
            keys = order + [k for k in sc["classes"] if k not in order]
            rows_ = "".join(f'<tr><td>{esc(cover_label(k))}</td><td class="t-num">{num(sc["classes"][k])}</td></tr>' for k in keys if k in sc["classes"])
            total = sum(v for v in sc["classes"].values() if isinstance(v, int))
            rows_ += f'<tr><td><strong>{esc(C("numbers.scope_total"))}</strong></td><td class="t-num"><strong>{num(total)}</strong></td></tr>'
            fam_rows = []
            for key in ("families_no_full_headline", "families_partial_headline_only", "families_with_lean_but_no_headline_coverage", "families_mixed_classes"):
                v = sc.get(key)
                if isinstance(v, list):
                    links = ", ".join(f'<a href="families/{esc(x)}.html">{esc(x)}</a>' for x in v if x in FAM)
                    fam_rows.append(f'<details class="receipt"><summary>{esc(C("numbers.scope_" + key, n=len(v)))}</summary><p class="small">{links}</p></details>')
            scope_body = f'<table class="tbl tbl--narrow"><tbody>{rows_}</tbody></table>{"".join(fam_rows)}'
        scope_html = f'<section class="band" aria-labelledby="h-scope-n" id="scope"><h2 class="h2" id="h-scope-n">{esc(C("numbers.scope_heading"))}</h2><p class="intro">{esc(C("numbers.scope_intro"))}</p>{scope_body}{receipt_html("scope_coverage")}</section>'
    # The Lean library scan: a source index, never a check.
    lc = s.get("lean_claim_layer") or {}
    claim_html = ""
    if lc:
        crow = []
        for key in ("lean_projects", "lean_files", "projects_with_model_file", "model_files", "model_statement_definitions", "model_statement_projects_linked_to_a_family", "manuscript_theorems", "projects_with_manuscript_theorems"):
            if isinstance(lc.get(key), int):
                crow.append(f'<tr><td>{esc(C("numbers.claims." + key))}</td><td class="t-num">{num(lc[key])}</td></tr>')
        direct = lc.get("manuscript_theorems_checked_by_comparator")
        direct_p = f'<p>{esc(C("numbers.claims.direct", n=num_words(direct), total=lc.get("manuscript_theorems", 0)))}</p>' if isinstance(direct, int) else ""
        claim_html = f'<section class="band" aria-labelledby="h-claims" id="lean-library"><h2 class="h2" id="h-claims">{esc(C("numbers.claims.heading"))}</h2><p class="intro">{esc(C("numbers.claims.intro"))}</p><table class="tbl tbl--narrow"><tbody>{"".join(crow)}</tbody></table>{direct_p}</section>'
    def other_receipts():
        rest = [k for k in receipts if k not in used_receipts]
        if not rest:
            return ""
        out = []
        for k in rest:
            r = receipts[k]
            label = number_item(k).get("label") or r.get("unit") or ""
            val = num(r["value"]) if isinstance(r.get("value"), int) else ""
            out.append(f'<article class="numrow" id="receipt-{esc(k)}"><p class="numrow__v">{val}</p><div class="numrow__t"><h3 class="h3">{esc(label)}</h3>{receipt_html(k)}</div></article>')
        return f'<section class="band" aria-labelledby="h-receipts"><h2 class="h2" id="h-receipts">{esc(C("numbers.receipts_heading"))}</h2>{"".join(out)}</section>'

    # upstream figures
    upr = s.get("upstream_reported", {})
    up_html = []
    if upr:
        tf = upr.get("top_line_results_formalized")
        if tf:
            up_html.append(f"""<article class="pair" id="openai-formalised">
 <div class="pair__a"><p class="pair__k">{esc(C('numbers.col_openai'))}</p><p class="pair__v">{esc(C('numbers.formalised_value', a=tf['formalized'], b=tf['of']))}</p><blockquote class="quote"><p>“{esc(tf['quote'])}”</p><footer>{esc(C('numbers.quoted_from'))} <a class="ext" href="{esc(tf['source'])}" rel="noopener">history.md</a></footer></blockquote></div>
 <div class="pair__b"><p class="pair__k">{esc(C('numbers.col_atlas'))}</p><p class="pair__v">{esc(C('numbers.atlas_formalised_value', n=s['manuscripts_with_lean']))}</p><p>{esc(C('numbers.upstream_formalised_atlas', n=s['manuscripts_with_lean']))}</p><p class="muted small">{esc(defs.get('manuscripts_with_lean', ''))}</p></div>
</article>""")
        cat = upr.get("catalogue")
        if cat:
            up_html.append(f"""<article class="pair">
 <div class="pair__a"><p class="pair__k">{esc(C('numbers.col_openai'))}</p><p class="pair__v">{esc(C('numbers.catalogue_value', manuscripts=cat['manuscripts'], families=cat['families']))}</p><blockquote class="quote"><p>“{esc(cat['quote'])}”</p><footer>{esc(C('numbers.quoted_from'))} <a class="ext" href="{esc(cat['source'])}" rel="noopener">README.md</a></footer></blockquote></div>
 <div class="pair__b"><p class="pair__k">{esc(C('numbers.col_atlas'))}</p><p class="pair__v">{esc(C('numbers.catalogue_atlas_value', manuscripts=s['manuscripts_current'], families=s['families']))}</p><p>{esc(C('numbers.upstream_catalogue_atlas', manuscripts=s['manuscripts_current'], families=s['families']))}</p></div>
</article>""")
        pp = upr.get("problems_posed")
        if pp:
            up_html.append(f"""<article class="pair">
 <div class="pair__a"><p class="pair__k">{esc(C('numbers.col_openai'))}</p><p class="pair__v">{esc(C('numbers.problems_value', n=pp['approximately']))}</p><blockquote class="quote"><p>“{esc(pp['quote'])}”</p><footer>{esc(C('numbers.quoted_from'))} <a class="ext" href="{esc(pp['source'])}" rel="noopener">README.md</a></footer></blockquote></div>
 <div class="pair__b"><p class="pair__k">{esc(C('numbers.col_atlas'))}</p><p>{esc(C('numbers.upstream_problems_atlas'))}</p></div>
</article>""")
    rc = s.get("lean_count_reconciliation") or {}
    recon_rows = []
    for key in ("families_with_lean_in_scope_notes", "families_with_a_paper_in_formalization_yaml_sources", "papers_in_formalization_yaml_sources", "tier_list_families_with_lean", "tier_list_lean_formalisations_total",
                "mathvet_families_full", "mathvet_families_partial", "mathvet_families_weaker_or_supporting",
                "cert_machine_families_matching", "cert_machine_families_narrower_declared", "cert_machine_families_narrower_undeclared_or_unlinked", "cert_machine_families_different_or_supporting",
                "mathvet_challenges_accepted", "cert_machine_challenges_accepted"):
        if rc.get(key) is not None:
            recon_rows.append(f'<tr><td>{esc(C("numbers.recon." + key))}</td><td class="t-num">{num(rc[key])}</td></tr>')
    if rc.get("openai_reported_top_line_formalized"):
        recon_rows.append(f'<tr><td>{esc(C("numbers.recon.openai_reported"))}</td><td class="t-num">\u201c{esc(rc["openai_reported_top_line_formalized"])}\u201d</td></tr>')
    recon_html = (f'<section class="band" aria-labelledby="h-recon"><h2 class="h2" id="h-recon">{esc(C("numbers.recon.heading"))}</h2><p class="intro">{esc(C("numbers.recon.intro"))}</p><table class="tbl"><tbody>{"".join(recon_rows)}</tbody></table><p class="muted small">{esc(C("numbers.recon.note"))}</p></section>') if recon_rows else ""
    envs = s.get("paper_statement_environments", {})
    env_rows = "".join(f'<tr><td>{esc(k)}</td><td class="t-num">{num(v)}</td></tr>' for k, v in sorted(envs.items(), key=lambda kv: -kv[1]))
    wd = [m for m in MANUSCRIPTS if m["status"] == "withdrawn"]
    wd_html = "".join(f'<article class="note note--warn"><h3 class="h3"><a href="papers/{esc(m["id"])}.html">{ms_title_html(m)}</a></h3><div class="md-math">{md_paragraphs(m.get("withdrawal_note") or "")}</div><p class="muted small">{esc(C("paper.withdrawn_on", date=m.get("withdrawn_on") or ""))}</p></article>' for m in wd)
    hist = "".join(f'<article class="changelog"><h3 class="h3">{esc(h["date"])}</h3><blockquote class="quote md-math">{md_paragraphs(h["markdown"])}<footer><a class="ext" href="{BASE_BLOB}history.md" rel="noopener">{esc(C("numbers.changelog_source"))}</a></footer></blockquote></article>' for h in HISTORY)
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('numbers.title'))}</h1>
 <p class="lede">{esc(C('numbers.lede', commit_short=COMMIT_SHORT))}</p>
</header>
<section class="band" aria-labelledby="h-up"><h2 class="h2" id="h-up">{esc(C('numbers.upstream_heading'))}</h2><p class="intro">{esc(C('numbers.upstream_intro'))}</p>{''.join(up_html)}</section>
{recon_html}
<section class="band" aria-labelledby="h-atlas-n"><h2 class="h2" id="h-atlas-n">{esc(C('numbers.atlas_heading'))}</h2>{''.join(items)}</section>
{scope_html}
{claim_html}
<section class="band" aria-labelledby="h-envs"><h2 class="h2" id="h-envs">{esc(C('numbers.envs_heading'))}</h2><p class="intro">{esc(C('numbers.envs_intro', manuscripts=s['manuscripts_current'], unparsed=len(s.get('manuscripts_tex_unparsed') or [])))}</p><table class="tbl tbl--narrow"><tbody>{env_rows}</tbody></table>{receipt_html('paper_statement_environments')}</section>
{other_receipts()}
<section class="band" aria-labelledby="h-wd"><h2 class="h2" id="h-wd">{esc(C('numbers.withdrawn_heading'))}</h2><p class="intro">{esc(C('numbers.withdrawn_intro', n=len(wd)))}</p>{wd_html}</section>
<section class="band" aria-labelledby="h-hist"><h2 class="h2" id="h-hist">{esc(C('numbers.changelog_heading'))}</h2>{hist}</section>
</div>"""
    write_page(rel, page(rel, C("numbers.title"), C("numbers.lede", commit_short=COMMIT_SHORT), body, current="numbers"))


def build_references_outside():
    rel = "references-outside.html"
    hl = SUMMARY.get("highlights", {}).get("most_cited_outside_works", [])
    works = {w["id"]: w for w in load("works.json")}
    rows = []
    for k, w in enumerate(hl, 1):
        rec = works.get(w["id"], {})
        cited_by = rec.get("cited_by", [])
        authors = clean_ref_text(w.get("authors"))
        title = clean_ref_text(w.get("title"))
        if title:
            head_ = f'<span class="work__ti">{esc(title)}</span>' + (f' <span class="work__au">{esc(authors)}</span>' if authors else "")
        else:
            head_ = f'<span class="work__tx">{esc(clean_ref_text(w.get("text") or w["id"]))}</span>'
        rr = rec.get("record", {})
        links = []
        if rr.get("doi"):
            links.append(f'<a class="ext" href="https://doi.org/{esc(rr["doi"])}" rel="noopener">DOI</a>')
        if rr.get("arxiv"):
            links.append(f'<a class="ext" href="https://arxiv.org/abs/{esc(rr["arxiv"])}" rel="noopener">arXiv</a>')
        cites = "".join(f'<li><a href="papers/{esc(c)}.html">{ms_title_html(MS[c])}</a></li>' for c in cited_by if c in MS and MS[c]["status"] == "current")
        rows.append(f"""<article class="work" id="work-{k}">
 <p class="work__rank">{k}</p>
 <div class="work__t">
  <h2 class="work__h">{head_} {('<span class="work__yr">' + esc(w.get('year')) + '</span>') if w.get('year') and title else ''}</h2>
  <p class="work__n">{esc(C('references_outside.cited_by', n=w['citing_manuscripts']))} {' '.join(links)}</p>
  <ul class="work__list">{cites}</ul>
 </div>
</article>""")
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('references_outside.title'))}</h1>
 <p class="lede">{esc(C('references_outside.lede', works=SUMMARY['external_works_cited'], citations=SUMMARY['external_citations'], n=len(hl)))}</p>
 <p>{esc(C('references_outside.credit'))}</p>
 <p class="muted small">{esc(C('references_outside.how'))}</p>
</header>
<section class="band band--tight">{''.join(rows)}</section>
</div>"""
    write_page(rel, page(rel, C("references_outside.title"), C("references_outside.lede", works=SUMMARY["external_works_cited"], citations=SUMMARY["external_citations"], n=len(hl)), body))


def build_sources():
    rel = "sources.html"
    rows = []
    s = SUMMARY
    up = f"""<article class="ceff" id="src-openai-math">
 <h3 class="h3"><a class="ext" href="{esc(CFG['upstream_repo'])}/tree/{COMMIT}" rel="noopener">openai/math</a></h3>
 <p class="muted small">OpenAI, {esc(C('sources.pinned', commit=COMMIT_SHORT))}, Apache-2.0</p>
 <p>{esc(C('sources.openai_uses', families=s['families'], manuscripts=s['manuscripts_current'], lean=s['statements_lean']))}</p>
</article>"""
    own = f"""<article class="ceff" id="src-atlas">
 <h3 class="h3"><a class="ext" href="{esc(REPO)}" rel="noopener">{esc(C('site.name'))}</a></h3>
 <p class="muted small">{esc(CFG['author'])}</p>
 <p>{esc(C('sources.atlas_uses'))}</p>
</article>"""
    ingested = []
    for src in s.get("sources", []):
        fields = src.get("fields") or {}
        flist = "".join(f"<li><strong>{esc(k)}</strong>: {esc(v)}</li>" for k, v in fields.items())
        authors = ", ".join(a.get("name") or a.get("handle") or "" for a in (src.get("authors") or []))
        ingested.append(f"""<article class="ceff" id="src-{esc(src['id'])}">
 <h3 class="h3"><a class="ext" href="{esc(src.get('url') or '')}" rel="noopener">{esc(src.get('name') or src['id'])}</a></h3>
 <p class="muted small">{esc(authors)}, {esc(C('sources.snapshot', date=src.get('snapshot') or ''))}, {esc(C('sources.licence', licence=src.get('licence') or 'n/a'))}</p>
 <p>{esc(src.get('method') or '')}</p>
 <ul class="small">{flist}</ul>
 {adopted_list_html(src.get('adopted'))}
</article>""")
    efforts = []
    for e in sorted(COMMUNITY["list"], key=lambda x: (x.get("kind") or "", x.get("date") or "", x["name"])):
        nf = sum(1 for f in COMMUNITY["findings"] if f.get("effort") == e["id"])
        fams = sorted({f["family"] for f in COMMUNITY["findings"] if f.get("effort") == e["id"] and f.get("family") in FAM} | {x for x in (e.get("families") or []) if x in FAM})
        fam_links = ", ".join(f'<a href="families/{esc(x)}.html">{esc(x)}</a>' for x in fams[:10]) + (" …" if len(fams) > 10 else "")
        efforts.append(f"""<article class="ceff" id="src-{esc(e['id'])}">
 <h3 class="h3"><a class="ext" href="{esc(e['url'])}" rel="noopener">{esc(e['name'])}</a></h3>
 <p class="muted small">{esc(credit_names(e))}{', ' if credit_names(e) else ''}{esc(e.get('date') or '')}, {esc(C('community.reuse_' + e.get('reuse', 'link')))} {esc(C('community.licence', licence=e.get('licence') or 'n/a'))}</p>
 <p>{esc(e['summary'])}</p>
 {('<p class="small">' + esc(C('sources.used_on', n=nf)) + ' ' + fam_links + '</p>') if fams else ''}
 {adopted_list_html(e.get('adopted'))}
</article>""")
    people = {(a.get("name") or a.get("handle")) for e in COMMUNITY["list"] for a in (e.get("authors") or [])}
    lede = C("sources.lede", sources=2 + len(s.get("sources", [])) + len(COMMUNITY["list"]), people=len(people), findings=len(COMMUNITY["findings"]))
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('sources.title'))}</h1>
 <p class="lede">{esc(lede)}</p>
 <p>{esc(C('sources.credit'))}</p>
 <p class="muted small">{esc(C('community.how'))} <a class="ext" href="{esc(issue_url('problem', C('community.add_title'), page=BASE_URL + rel))}" rel="noopener">{esc(C('community.add'))}</a></p>
</header>
<section class="band band--tight"><h2 class="h2">{esc(C('sources.base_heading'))}</h2><div class="ceffs">{up}{own}</div></section>
{('<section class="band band--tight"><h2 class="h2">' + esc(C('sources.ingested_heading')) + '</h2><p class="intro">' + esc(C('sources.ingested_intro')) + '</p><div class="ceffs">' + ''.join(ingested) + '</div></section>') if ingested else ''}
{('<section class="band band--tight"><h2 class="h2">' + esc(C('sources.efforts_heading')) + '</h2><p class="intro">' + esc(C('sources.efforts_intro')) + '</p><div class="ceffs">' + ''.join(efforts) + '</div></section>') if efforts else ''}
</div>"""
    write_page(rel, page(rel, C("sources.title"), lede, body, current="sources"))


def build_citations_within():
    rel = "citations-within.html"
    hl = SUMMARY.get("highlights", {}).get("most_cited_inside_collection", [])
    rows = []
    for k, e in enumerate(hl, 1):
        m = MS.get(e["manuscript"])
        if not m:
            continue
        f = FAM.get(e.get("family") or "")
        citing = "".join(f'<li><a href="papers/{esc(c)}.html">{ms_title_html(MS[c])}</a></li>' for c in m.get("cited_by_in_collection") or [] if c in MS)
        lean = C("citations_within.lean_yes") if e.get("has_lean") else C("citations_within.lean_no")
        rows.append(f"""<article class="work" id="cited-{k}">
 <p class="work__rank">{k}</p>
 <div class="work__t">
  <h2 class="work__h"><a href="papers/{esc(m['id'])}.html">{ms_title_html(m)}</a></h2>
  <p class="work__n">{esc(C('citations_within.cited_by', n=e['cited_by']))}. {esc(lean)}.{(' ' + C('words.result').capitalize() + ' <a href="families/' + f['id'] + '.html">' + fam_title_html(f) + '</a>') if f else ''}</p>
  <ul class="work__list">{citing}</ul>
 </div>
</article>""")
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('citations_within.title'))}</h1>
 <p class="lede">{esc(C('citations_within.lede', edges=SUMMARY['internal_citation_edges'], n=len(hl)))}</p>
 <p class="muted small">{esc(C('citations_within.how'))}</p>
</header>
<section class="band band--tight">{''.join(rows)}</section>
</div>"""
    write_page(rel, page(rel, C("citations_within.title"), C("citations_within.lede", edges=SUMMARY["internal_citation_edges"], n=len(hl)), body))


def contributor_names():
    names = []
    for kind in CONTRIB.values():
        for lst in kind.values():
            for e in lst:
                names.extend(e["names"])
    return list(dict.fromkeys(names))


def build_contribute():
    rel = "contribute.html"
    guide = REPO + "/" + CFG["contributing_path"]
    ways = []
    for key in ("claim", "check", "problem", "credit", "replay"):
        name = CFG["issue_templates"][key]
        ways.append(f'<li><a class="ext" href="{esc(REPO)}/issues/new?template={esc(name)}.yml" rel="noopener">{esc(C("contribute." + key))}</a></li>')
    names = contributor_names()
    contrib = f'<p>{esc(", ".join(names))}</p>' if names else f'<p class="muted">{esc(C("contribute.contributors_none"))}</p>'
    body = f"""<div class="frame page page--narrow">
<header class="phead"><h1 class="phead__title">{esc(C('contribute.title'))}</h1><p class="lede">{esc(C('contribute.lede'))}</p></header>
<section class="band band--tight"><h2 class="h2">{esc(C('contribute.ways_heading'))}</h2><ul class="ways">{''.join(ways)}</ul>
<p>{esc(C('contribute.guide'))} <a class="ext" href="{esc(guide)}" rel="noopener">{esc(C('contribute.guide_link'))}</a></p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('explain.queue_heading'))}</h2><p>{esc(C('contribute.queue'))} <a href="explain.html#careful-reading">{esc(C('contribute.queue_link'))}</a></p></section>
<section class="band" id="contributors"><h2 class="h2">{esc(C('contribute.contributors_heading'))}</h2>{contrib}</section>
</div>"""
    write_page(rel, page(rel, C("contribute.title"), C("contribute.lede"), body, current="contribute"))


def build_about():
    rel = "about.html"
    s = SUMMARY
    fill = dict(release_date=CFG["release_date"], families=s["families"], families_with_lean=s["families_with_lean"],
                commit_short=COMMIT_SHORT, author=CFG["author"])
    cite = C("about.cite_format", author=CFG["author"], name=C("site.name"), url=BASE_URL, commit=COMMIT)
    ur = SUMMARY.get("upstream_reported", {})
    disclosed = []
    for key in ("catalogue", "model", "compute", "problems_posed", "top_line_results_formalized", "human_edited"):
        if ur.get(key, {}).get("quote"):
            disclosed.append(f'<li>\u201c{esc(ur[key]["quote"])}\u201d <a class="ext small" href="{esc(ur[key]["source"])}" rel="noopener">{esc(ur[key]["source"].rsplit("/", 1)[-1])}</a></li>')
    if ur.get("reasoning_summaries", {}).get("count"):
        disclosed.append(f'<li>{esc(C("about.disclosed_traces", n=ur["reasoning_summaries"]["count"]))}</li>')
    disclosed_items = "".join(disclosed)
    related_items = "".join(f'<li><a class="ext" href="{esc(u)}" rel="noopener">{esc(t)}</a>: {esc(d)}</li>' for t, u, d in CFG.get("related_efforts", []))
    # The essays behind the design, each paraphrased and linked, then what the atlas does, in
    # its own voice: no author is enlisted, and the page says they are not involved.
    approach = "".join(
        f'<li class="approach__item"><p><span class="approach__who">{esc(a["who"])}</span>, in '
        f'<a class="ext" href="{esc(a["url"])}" rel="noopener">{esc(a["title"])}</a>, {esc(a["argues"])}</p></li>'
        for a in COPY["about"]["approach_items"])
    approach += "</ul>" + f'<p class="approach__then">{esc(C("about.approach_response_intro"))}</p><ul class="adds">' + "".join(
        f"<li>{esc(t)}</li>" for t in COPY["about"]["approach_responses"])
    reading = list(PAPER_READING.values())
    groups = len({v["source"] for s_ in STATEMENTS for v in sourced_all(s_, "replay")})
    adds_fill = dict(manuscripts=num(s["manuscripts_current"]), lean=num(s["statements_lean"]), families=num(s["families"]),
                     accepted=num(reading.count("accepted")), partial=num(reading.count("partial")), groups=num(groups))
    adds = "".join(f"<li>{esc(t.format(**adds_fill))}</li>" for t in COPY["about"]["adds_items"])
    import backend
    b = backend.load()
    backend_p = f'<p>{esc(C("about.backend", generation=b.generation.split(":")[-1][:12]))}</p>' if b else ""
    body = f"""<div class="frame page page--narrow prose-page">
<header class="phead"><h1 class="phead__title">{esc(C('about.title'))}</h1></header>
<section class="band band--tight"><h2 class="h2">{esc(C('about.what_heading'))}</h2><p>{esc(C('about.what', **fill))}</p></section>
<section class="band band--tight" id="approach" aria-labelledby="h-approach"><h2 class="h2" id="h-approach">{esc(C('about.approach_heading'))}</h2><p>{esc(C('about.approach_intro'))}</p><ul class="approach">{approach}</ul></section>
<section class="band band--tight" id="adds" aria-labelledby="h-adds"><h2 class="h2" id="h-adds">{esc(C('about.adds_heading'))}</h2><p>{esc(C('about.adds_intro', **adds_fill))}</p><ul class="adds">{adds}</ul></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.how_heading'))}</h2><p>{esc(C('about.how', **fill))}</p>{backend_p}</section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.independence_heading'))}</h2><p>{esc(C('about.independence'))}</p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.made_heading'))}</h2><p>{esc(C('about.made'))}</p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.not_heading'))}</h2><p>{esc(C('about.not'))}</p></section>
{('<section class="band band--tight"><h2 class="h2">' + esc(C('about.interests_heading')) + '</h2><p>' + esc(C('about.interests')) + '</p></section>') if C('about.interests') else ''}
<section class="band band--tight"><h2 class="h2">{esc(C('about.disclosed_heading'))}</h2><p>{esc(C('about.disclosed_intro'))}</p><ul>{disclosed_items}</ul></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.related_heading'))}</h2><p>{esc(C('about.related_intro'))}</p><ul>{related_items}</ul></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.licence_heading'))}</h2><p>{esc(C('about.licence'))} <a class="ext" href="{CFG['upstream_repo']}/blob/{COMMIT}/LICENSE" rel="noopener">LICENSE</a></p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.cite_heading'))}</h2><p>{esc(C('about.cite'))}</p><div class="texsrc__box texsrc__box--open"><button class="copy" type="button" data-copy-next>{esc(C('words.copy'))}</button><pre><code>{esc(cite)}</code></pre></div></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.author_heading'))}</h2><p>{esc(C('about.author', **fill))} <a class="ext" href="{esc(CFG['author_url'])}" rel="noopener">{esc(C('about.author_link'))}</a></p></section>
</div>"""
    write_page(rel, page(rel, C("about.title"), C("about.what", **fill), body, current="about"))


def build_404():
    rel = "404.html"
    base = CFG["base_url"].rstrip("/")
    body = f'<div class="frame page page--narrow"><header class="phead"><h1 class="phead__title">{esc(C("notfound.title"))}</h1><p class="lede">{esc(C("notfound.text"))}</p><p class="actions"><a class="btn btn--primary" href="{esc(base)}/">{esc(C("nav.atlas"))}</a></p></header></div>'
    h = page(rel, C("notfound.title"), C("notfound.text"), body, noindex=True)
    # Absolute asset paths: the host serves this page at any depth.
    path = re.sub(r"https?://[^/]+", "", base)
    h = h.replace('href="assets/', f'href="{path}/assets/').replace('src="assets/', f'src="{path}/assets/').replace('data-root=""', f'data-root="{path}/"')
    for href, key in NAV:
        h = h.replace(f'href="{href}"', f'href="{path}/{href}"')
    write_page(rel, h, index=False)


def build_search_index():
    idx = []
    for f in FAMILIES:
        idx.append({"t": tex_plain(f["title"]), "k": C("words.result").capitalize() + " " + f["id"], "u": f"families/{f['id']}.html", "s": DISCIPLINES[DISC_OF[f["id"]]]["name"]})
    for m in MANUSCRIPTS:
        if m["status"] not in ("current", "withdrawn"):
            continue
        idx.append({"t": tex_plain(m["title"]), "k": C("words.manuscript").capitalize() + (", " + C("words.status_withdrawn").lower() if m["status"] == "withdrawn" else ""), "u": f"papers/{m['id']}.html", "s": m.get("date") or ""})
    for s in STATEMENTS:
        idx.append({"t": (s.get("labels") or [s["id"]])[0], "k": C("words.lean_statement"), "u": f"statements/{s['id']}.html", "s": s["id"]})
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "data" / "search.json").write_text(json.dumps(idx, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


def build_sitemap():
    lines = ['<?xml version="1.0" encoding="UTF-8"?>', '<urlset xmlns="http://www.sitemaps.org/schemas/sitemap/0.9">']
    for rel in PAGES:
        url = BASE_URL + ("" if rel == "index.html" else rel)
        lines.append(f"<url><loc>{esc(url)}</loc></url>")
    lines.append("</urlset>")
    (OUT / "sitemap.xml").write_text("\n".join(lines) + "\n", encoding="utf-8")
    (OUT / "robots.txt").write_text(f"User-agent: *\nAllow: /\nDisallow: /cards/\nSitemap: {BASE_URL}sitemap.xml\n", encoding="utf-8")


def social_card_html():
    """Site-wide social card: a static treemap of the release drawn from the data."""
    s = SUMMARY
    W, H = 1200, 675
    fx, fy, fw, fh = 560, 48, 600, 579
    regions = []
    for i, d in enumerate(DISCIPLINES):
        val = sum(len(FAM[f]["manuscripts"]) for f in d["families"] if f in FAM)
        regions.append((val, i))
    rects = squarify([v for v, _ in sorted(regions, reverse=True)], fx, fy, fw, fh)
    svg = []
    for (val, i), (x, y, w, h) in zip(sorted(regions, reverse=True), rects):
        fams = sorted(DISCIPLINES[i]["families"], key=lambda f: -len(FAM[f]["manuscripts"]))
        inner = squarify([len(FAM[f]["manuscripts"]) for f in fams], x + 3, y + 3, w - 6, h - 6)
        svg.append(f'<rect x="{x:.1f}" y="{y:.1f}" width="{w:.1f}" height="{h:.1f}" class="sc-reg"/>')
        for f, (a, b, c, e) in zip(fams, inner):
            cls = "sc-main" if fam_has_main(FAM[f]) else ("sc-sup" if FAM[f]["statements"] else "sc-none")
            svg.append(f'<rect x="{a + 1:.1f}" y="{b + 1:.1f}" width="{max(c - 2, 0):.1f}" height="{max(e - 2, 0):.1f}" class="{cls}"/>')
    line = C("social.card_line", families=s["families"], manuscripts=s["manuscripts_current"], lean=s["statements_lean"], commit_short=COMMIT_SHORT)
    return f"""<!doctype html><html lang="en-GB" data-theme="dark"><head><meta charset="utf-8"><link rel="stylesheet" href="../assets/atlas.css"></head>
<body class="social"><div class="social__card"><div class="social__text"><p class="social__brand">{MARK_SVG}</p><h1>{esc(C('social.card_title'))}</h1><p>{esc(line)}</p><p class="social__key"><span class="k"><span class="sw sw--main"></span><span>{esc(C('home.legend_lean_main'))}</span></span><span class="k"><span class="sw sw--sup"></span><span>{esc(C('home.legend_lean_support'))}</span></span><span class="k"><span class="sw sw--none"></span><span>{esc(C('home.legend_lean_none'))}</span></span></p></div>
<svg class="social__map" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{''.join(svg)}</svg></div></body></html>"""


def squarify(values, x, y, w, h):
    """Squarified treemap (Bruls, Huizing, van Wijk). values sorted descending."""
    total = sum(values)
    if total <= 0:
        return [(x, y, 0, 0) for _ in values]
    scale = w * h / total
    areas = [v * scale for v in values]
    rects = []
    i = 0
    while i < len(areas):
        short_side = min(w, h)
        row = [areas[i]]
        j = i + 1

        def worst(r):
            s_ = sum(r)
            return max(max(r) * short_side ** 2 / s_ ** 2, s_ ** 2 / (short_side ** 2 * min(r)))

        while j < len(areas) and worst(row + [areas[j]]) <= worst(row):
            row.append(areas[j])
            j += 1
        s_ = sum(row)
        if w >= h:
            cw = s_ / h
            cy = y
            for a in row:
                ch = a / cw
                rects.append((x, cy, cw, ch))
                cy += ch
            x += cw
            w -= cw
        else:
            ch = s_ / w
            cx = x
            for a in row:
                cw = a / ch
                rects.append((cx, y, cw, ch))
                cx += cw
            y += ch
            h -= ch
        i = j
    return rects


def render_png(pages: list[tuple[Path, Path]], workers: int = 4) -> list[Path]:
    """Screenshot card pages to PNG with a headless browser, a few at a time. Returns
    the images that were produced and passed the gate: mathematics typeset with no
    failures, no clipped column, and a file on disk. A rejected card produces nothing."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: optional
    except Exception:
        warn("Playwright is not importable; social card PNGs were not rendered.")
        return []
    from concurrent.futures import ThreadPoolExecutor

    def run(chunk):
        done = []
        with sync_playwright() as p:
            try:
                b = p.chromium.launch(channel="chrome")
            except Exception:
                b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1200, "height": 675}, device_scale_factor=1, color_scheme="light")
            for src, dst in chunk:
                pg.goto(src.as_uri(), wait_until="load")
                social = False
                try:
                    pg.wait_for_function("document.documentElement.dataset.math || document.body.classList.contains('social')", timeout=15000)
                except Exception:
                    warn(f"card {src.name}: mathematics did not finish; no image produced")
                    continue
                pg.evaluate("document.fonts.ready.then(() => true)")
                pg.wait_for_timeout(250)
                state = pg.evaluate("""() => ({social: document.body.classList.contains('social'),
                    math: document.documentElement.dataset.math || '',
                    failed: (window.__atlasMath || {}).failed || 0,
                    clipped: document.querySelectorAll('.is-clipped').length})""")
                social = state["social"]
                if not social and (state["math"] != "ready" or state["failed"] or state["clipped"]):
                    warn(f"card {src.name}: rejected (maths {state['math'] or 'missing'}, {state['failed']} formula failures, {state['clipped']} clipped columns)")
                    continue
                dst.parent.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(dst), clip={"x": 0, "y": 0, "width": 1200, "height": 675})
                if dst.exists() and dst.stat().st_size > 0:
                    done.append(dst)
            b.close()
        return done

    workers = max(1, min(workers, len(pages)))
    chunks = [pages[i::workers] for i in range(workers)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return [d for part in ex.map(run, chunks) for d in part]


# --------------------------------------------------------------------- main


def main():
    global CONTRIB, OUT
    ap = argparse.ArgumentParser()
    ap.add_argument("--og", action="store_true", help="render the site-wide social card PNG")
    ap.add_argument("--og-cards", action="store_true", help="render one PNG per Lean statement")
    ap.add_argument("--contributions", help="read contributions from this folder instead of contributions/ (for testing a fixture)")
    ap.add_argument("--out", help="write the site here instead of site/_build")
    args = ap.parse_args()
    t0 = time.time()
    if args.contributions:
        CONTRIB = load_contributions(Path(args.contributions).resolve())
    if args.out:
        OUT = Path(args.out).resolve()
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    shutil.copytree(ASSETS, OUT / "assets")
    (OUT / ".nojekyll").write_text("")
    (OUT / "cards").mkdir(exist_ok=True)
    recompute_checks()

    md = map_data()
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "data" / "atlas-map.json").write_text(json.dumps(md, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    build_home(md)
    for f in FAMILIES:
        build_family(f)
    for m in MANUSCRIPTS:
        build_paper(m)
    for s in STATEMENTS:
        build_statement(s)
    build_explain()
    build_statements_table()
    build_numbers()
    build_citations_within()
    build_references_outside()
    build_sources()
    build_glossary()
    build_contribute()
    build_about()
    build_404()
    build_search_index()
    (OUT / "cards" / "site.html").write_text(social_card_html(), encoding="utf-8")
    build_sitemap()

    produced = 0
    if args.og or args.og_cards:
        jobs = [(OUT / "cards" / "site.html", ASSETS / "social-card.png")]
        if args.og_cards:
            jobs += [(OUT / "cards" / f"{s['id']}.html", OUT / "og" / f"{s['id']}.png") for s in STATEMENTS]
        done = render_png(jobs)
        produced = len([d for d in done if d.parent == OUT / "og"])
        if (ASSETS / "social-card.png").exists():
            shutil.copy(ASSETS / "social-card.png", OUT / "assets" / "social-card.png")
        print(f"rendered {produced} PNG cards", file=sys.stderr)
        # A statement page names its own image only when this build produced it;
        # every other statement page keeps the generic card.
        for dst in done:
            sid = dst.stem
            if dst.parent == OUT / "og" and sid in OG_DONE:
                pth = OUT / "statements" / f"{sid}.html"
                generic, own = OG_DONE[sid]
                pth.write_text(pth.read_text(encoding="utf-8").replace(generic, own, 1), encoding="utf-8")
        if args.og_cards:
            missing = [s_["id"] for s_ in STATEMENTS if (OUT / "og" / f"{s_['id']}.png") not in set(done)]
            if missing:
                warn(f"{len(missing)} statement cards were not produced and use the generic image: {missing[:5]}")

    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(json.dumps({
        "pages": STATS["pages"], "indexed": len(PAGES), "seconds": round(time.time() - t0, 1),
        "bytes": size, "math_inline": STATS["math_inline"], "math_display": STATS["math_display"],
        "unknown_text_commands": STATS["tex_unknown_text_command"], "unrenderable_envs": STATS["tex_unrenderable_env"],
        "pairing": {"candidate": STATS["pairing_candidate"], "abstained_weak": STATS["pairing_abstained_weak"], "abstained_tie": STATS["pairing_abstained_tie"]},
        "og_statement_images": produced,
        "top_unknown": [(k, v) for k, v in STATS.most_common() if k.startswith(("unknown:", "env:"))][:25],
        "warnings": WARN,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
