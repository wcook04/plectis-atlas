#!/usr/bin/env python3
"""Build the OpenAI Math Atlas static site.

Reads data/*.json (produced by scripts/build_data.py), site/copy.json (every
human-facing sentence) and site/config.json (URLs), and writes static HTML,
per-page data and assets to site/_build/. Standard library only.

    python3 scripts/build_site.py            # build
    python3 scripts/build_site.py --og       # also render social card PNGs (needs Playwright)
    python3 scripts/build_site.py --og-cards # also render one PNG per Lean statement

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
CLAIMS_BY_FAMILY: dict = {}
for _c in _CLAIMS:
    for _f in _c.get("families") or []:
        CLAIMS_BY_FAMILY.setdefault(_f, []).append(_c)
UP = SUMMARY["upstream"]
COMMIT = UP["commit"]
COMMIT_SHORT = COMMIT[:7]
BASE_BLOB = f"https://github.com/openai/math/blob/{COMMIT}/"
BASE_URL = CFG["base_url"].rstrip("/") + "/"
REPO = CFG["repo"].rstrip("/")
KATEX = CFG["katex_version"]
KATEX_CDN = f"https://cdnjs.cloudflare.com/ajax/libs/KaTeX/{KATEX}"
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
    """Escape copy text and set `backticked` words as code."""
    return re.sub(r"`([^`]+)`", r"<code>\1</code>", esc(s))


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

LEAN_KW = ("theorem lemma def abbrev structure class inductive instance axiom opaque example notation infix infixl "
           "infixr prefix postfix macro syntax macro_rules where extends namespace section end open scoped variable "
           "universe noncomputable private protected import in fun let have show from by if then else match with do "
           "deriving mutual set_option attribute local export calc at Type Sort Prop forall exists").split()
LEAN_DECL = "theorem lemma def abbrev structure class inductive instance axiom opaque".split()
LEAN_TOKEN = re.compile(
    r"(?P<doc>/--.*?-/)|(?P<bc>/-.*?-/)|(?P<lc>--[^\n]*)|(?P<str>\"(?:\\.|[^\"\\\n])*\")|(?P<attr>@\[[^\]\n]*\])"
    r"|(?P<decl>\b(?:" + "|".join(LEAN_DECL) + r")\b)(?P<sp>[ \t]+)(?P<name>[^\s:({\[]+)?"
    r"|(?P<sorry>\b(?:sorry|admit)\b)"
    r"|(?P<kw>\b(?:" + "|".join(k for k in LEAN_KW if k not in LEAN_DECL) + r")\b)"
    r"|(?P<num>\b\d+(?:\.\d+)?\b)",
    re.S,
)


def lean_lines(text: str) -> list[str]:
    toks = []
    pos = 0
    for m in LEAN_TOKEN.finditer(text):
        if m.start() > pos:
            toks.append((None, text[pos:m.start()]))
        g = m.lastgroup
        if m.group("decl"):
            toks.append(("k", m.group("decl")))
            toks.append((None, m.group("sp")))
            if m.group("name"):
                toks.append(("d", m.group("name")))
        elif g == "doc":
            toks.append(("c d", m.group(0)))
        elif g in ("bc", "lc"):
            toks.append(("c", m.group(0)))
        elif g == "str":
            toks.append(("s", m.group(0)))
        elif g == "attr":
            toks.append(("a", m.group(0)))
        elif g == "sorry":
            toks.append(("x", m.group(0)))
        elif g == "kw":
            toks.append(("k", m.group(0)))
        elif g == "num":
            toks.append(("n", m.group(0)))
        pos = m.end()
    if pos < len(text):
        toks.append((None, text[pos:]))
    lines = [[]]
    for cls, t in toks:
        parts = t.split("\n")
        for k, p in enumerate(parts):
            if k:
                lines.append([])
            if p:
                lines[-1].append(f'<span class="{cls}">{esc(p)}</span>' if cls else esc(p))
    if text.endswith("\n") and lines and not lines[-1]:
        lines.pop()
    return ["".join(x) for x in lines]


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


def load_contributions(base: Path | None = None):
    c = {"explanations": defaultdict(list), "checks": defaultdict(list), "credits": defaultdict(list), "replays": defaultdict(list)}
    base = base or (ROOT / "contributions")
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
        try:
            text = p.read_text(encoding="utf-8").lstrip("\ufeff").replace("\r\n", "\n")
            if p.suffix == ".json":
                meta = json.loads(text)
            elif p.suffix in (".md", ".markdown"):
                y, first, _body, _ = split_frontmatter(text)
                parsed = parse_yaml(y, first)
                meta = parsed[0] if isinstance(parsed, tuple) else (parsed or {})
            else:
                continue
        except Exception as exc:
            warn(f"contribution {p.relative_to(ROOT)} could not be read ({exc})")
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
        c[kind][target].append({
            "names": names or [handle], "name": ", ".join(names or [handle]), "reviewers": reviewers,
            "status": str(meta.get("status") or "").lower(), "title": meta.get("title"),
            "verdict": (lambda v: None if (v is None or str(v).startswith("[replace")) else str(v).replace("-", " "))(meta.get("verdict") or meta.get("result") or meta.get("relation")),
            "path": "/".join(("contributions",) + rel), "date": str(meta.get("date") or ""),
        })
    return c


CONTRIB = load_contributions()

def load_coverage():
    p = ROOT / "curated" / "scope_coverage.json"
    if not p.exists():
        return {}
    try:
        raw = json.loads(p.read_text(encoding="utf-8"))
    except Exception as exc:
        warn(f"curated/scope_coverage.json could not be read ({exc})")
        return {}
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
    return out


COVERAGE = load_coverage()


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


def family_facets_html(f, root):
    parts = []
    ty, tier = sourced(f, "type"), sourced(f, "tier")
    if ty:
        also = sourced(f, "also")
        label = C("sources.type_words").get(ty["value"], ty["value"]).capitalize()
        if also:
            label += C("sources.also_word", what=C("sources.type_words").get(also["value"], also["value"]))
        parts.append(f'<span>{esc(label)} <span class="muted small">({source_link(ty["source"], root)})</span></span>')
    if tier is not None and tier.get("value") is not None:
        names = (SOURCES.get(tier["source"]) or {}).get("tier_names") or {}
        parts.append(f'<span>{esc(C("sources.tier_label", name=names.get(str(tier["value"]), str(tier["value"]))))} <span class="muted small">({source_link(tier["source"], root)})</span></span>')
    return ('<p class="phead__facets">' + ' <span class="sep" aria-hidden="true">·</span> '.join(parts) + "</p>") if parts else ""


def coverage_html(sid):
    row = COVERAGE.get(sid)
    if not row:
        return ""
    cls = str(row.get("class") or "")
    label = COPY["statement"].get("coverage_classes", {}).get(cls, cls.replace("-", " "))
    quote = row.get("scope_quote") or row.get("quote") or ""
    fam = row.get("family")
    note_url = f"{BASE_BLOB}lean/docs/{fam}.md" if fam else None
    expl = row.get("explanation") or ""
    check = issue_url("check", C("statement.coverage_check_title", id=sid), statement=sid)
    parts = [f'<p class="coverage"><span class="pill pill--support">{esc(label)}</span></p>']
    if quote:
        foot = f'<footer><a class="ext" href="{esc(note_url)}" rel="noopener">{esc(C("statement.coverage_source"))}</a></footer>' if note_url else ""
        parts.append(f'<blockquote class="quote md-math"><p>\u201c{esc(quote)}\u201d</p>{foot}</blockquote>')
    if expl:
        parts.append(f'<p class="md-math">{esc(expl)}</p>')
    parts.append(f'<p class="muted small">{esc(C("statement.coverage_provenance"))} <a class="ext" href="{esc(check)}" rel="noopener">{esc(C("statement.coverage_check"))}</a></p>')
    return "".join(parts)


COVER_RANK = {"headline": 4, "headline-part": 3, "consequence": 2, "weaker": 2, "unclear": 1, "supporting": 1}
COVER_GRADE = {4: "full", 3: "part", 2: "less", 1: "support"}


def fam_cover_grade(f):
    """Strongest coverage among a family's statements: full, part, less, support, or none (no Lean)."""
    ranks = [COVER_RANK.get(str(COVERAGE.get(s, {}).get("class")), 0) for s in f["statements"]]
    if not f["statements"]:
        return "none"
    best = max(ranks) if ranks else 0
    return COVER_GRADE.get(best, "unknown")



def family_exposition_status(fid):
    ex = CONTRIB["explanations"].get(fid, [])
    if any(e["status"] == "reviewed" for e in ex):
        return "explained", ex
    if ex:
        return "claimed", ex
    return "open", []


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


def issue_url(template_key: str, title: str, **fields) -> str:
    name = CFG["issue_templates"][template_key]
    params = {"template": f"{name}.yml", "title": title}
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


def head(rel: str, title: str, description: str, *, og_image: str | None = None, noindex=False,
         extra_head: str = "", page_type="website") -> str:
    depth = rel.count("/")
    root = "../" * depth
    canonical = BASE_URL + ("" if rel == "index.html" else rel)
    full_title = title if title == C("site.name") else f"{title} | {C('site.name')}"
    og = og_image or (BASE_URL + "assets/social-card.png")
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
<meta property="og:image" content="{esc(og)}">
<meta property="og:image:width" content="1200">
<meta property="og:image:height" content="675">
<meta name="twitter:card" content="summary_large_image">
<meta name="twitter:title" content="{esc(title)}">
<meta name="twitter:description" content="{desc}">
<meta name="twitter:image" content="{esc(og)}">
<link rel="icon" href="{root}assets/favicon.svg" type="image/svg+xml">
<link rel="preconnect" href="https://fonts.googleapis.com">
<link rel="preconnect" href="https://fonts.gstatic.com" crossorigin>
<link rel="stylesheet" href="{esc(CFG['fonts_css'])}">
<link rel="stylesheet" href="{KATEX_CDN}/katex.min.css" crossorigin="anonymous">
<link rel="stylesheet" href="{root}assets/atlas.css">
<script>(function(){{try{{var t=localStorage.getItem('atlas-theme');if(t==='dark'||t==='light')document.documentElement.setAttribute('data-theme',t);}}catch(e){{}}}})();</script>
<script defer src="{KATEX_CDN}/katex.min.js" crossorigin="anonymous"></script>
<script defer src="{KATEX_CDN}/contrib/auto-render.min.js" crossorigin="anonymous"></script>
<script defer src="{root}assets/atlas.js"></script>
{extra_head}
</head>"""


NAV = [("index.html", "atlas"), ("explain.html", "explain"), ("statements.html", "statements"),
       ("sources.html", "sources"), ("numbers.html", "numbers"), ("contribute.html", "contribute"),
       ("about.html", "about")]


def header(rel: str, current: str | None) -> str:
    root = "../" * rel.count("/")
    links = []
    for href, key in NAV:
        cur = ' aria-current="page"' if key == current else ""
        links.append(f'<a href="{root}{href}"{cur}>{esc(C("nav." + key))}</a>')
    return f"""<body data-root="{root}" data-copied="{esc(C('words.copied'))}" data-tex-failed="{esc(C('words.tex_failed'))}">
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
  <input class="search__input" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(C('nav.search_placeholder'))}" aria-label="{esc(C('nav.search_placeholder'))}">
 </form>
 <ul class="search__results" role="listbox" aria-label="{esc(C('nav.search'))}"></ul>
 <p class="search__empty" hidden>{esc(C('nav.search_empty'))}</p>
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
   <li><a href="{root}builds-on.html">{esc(C('builds_on.title'))}</a></li>
   <li><a href="{root}rests-on.html">{esc(C('rests_on.title'))}</a></li>
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
    path.write_text(html_text, encoding="utf-8")
    if index:
        PAGES.append(rel)
    STATS["pages"] += 1


def page(rel, title, description, body, *, current=None, og_image=None, noindex=False, extra_head="",
         page_type="website", main_class=""):
    h = head(rel, title, description, og_image=og_image, noindex=noindex, extra_head=extra_head, page_type=page_type)
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
    return f"""<figure class="stmt" id="{aid}" data-macros="{esc(m['id'])}">
 <figcaption class="stmt__head"><span class="stmt__kind">{esc(st['display'])}</span>{title}</figcaption>
 <div class="stmt__body">{body}</div>
 <div class="stmt__foot">
  <span class="stmt__loc">{esc(loc_sec)}{sec_title}</span>
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


def pair_statement(stmt):
    """Choose the paper headline statement whose words overlap most with the Lean notes."""
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    lean_words = words_of(" ".join(stmt.get("labels") or []) + " " + " ".join(stmt.get("docstrings") or []) + " " + stmt["id"]
                          + " " + " ".join(n.split(".")[-1] for n in stmt["comparator"]["theorem_names"]))
    scope_words = words_of((fam or {}).get("lean_doc", {}).get("scope", "") if fam and fam.get("lean_doc") else "")
    best = None
    for slug in stmt.get("papers") or []:
        m = MS.get(slug)
        if not m:
            continue
        for st in headline_statements(m):
            w = words_of((st.get("title") or "") + " " + st["text"])
            score = 3 * len(w & lean_words) + len(w & scope_words) + (1 if st["kind"] == "theorem" else 0)
            if best is None or score > best[0]:
                best = (score, m, st)
    return (best[1], best[2]) if best else (None, None)


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


def lean_card_small(sid, root):
    s = ST[sid]
    label = (s.get("labels") or [sid])[0]
    main = C("words.main_result") if s["main_result"] else C("words.supporting_result")
    vocab = s["vocabulary_count"]
    vtext = C("statement.card_vocab_zero") if vocab == 0 else (C("statement.card_vocab_one") if vocab == 1 else C("statement.card_vocab", count=vocab))
    snippet = lean_snippet_html(s, max_lines=12)
    return f"""<article class="leanc">
 <h3 class="leanc__title"><a href="{root}statements/{esc(sid)}.html"><span class="md-math">{esc(label)}</span></a></h3>
 <p class="leanc__meta"><span class="pill {'pill--main' if s['main_result'] else 'pill--support'}">{esc(main)}</span> <span>{esc(vtext)}</span> <code class="leanc__file">{esc(sid)}.lean</code></p>
 <pre class="lean lean--snippet"><code>{snippet}</code></pre>
 {coverage_html(sid)}
 <p class="leanc__note">{ctext(C('statement.sorry_note_axiom') if s['declares_axiom'] else C('statement.sorry_note'))}</p>{('<p class="leanc__note">' + ctext(C('statement.card_holes_one', name=s['comparator']['definition_names'][0].split('.')[-1]) if len(s['comparator']['definition_names']) == 1 else C('statement.card_holes_many', n=len(s['comparator']['definition_names']), name=s['comparator']['definition_names'][0].split('.')[-1])) + '</p>') if s['comparator'].get('definition_names') else ''}
 <p class="leanc__go"><a href="{root}statements/{esc(sid)}.html">{esc(C('words.open_statement'))}</a></p>
</article>"""


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


def manuscript_block(m, root, conv, lean_ids):
    status = m["status"]
    notes = ""
    if m.get("version_note"):
        notes += f'<div class="note"><p class="note__h">{esc(C("family.version_note"))}</p><div class="md-math">{md_paragraphs(m["version_note"], "preprints/" + m["id"] + "/")}</div></div>'
    prev = ""
    if m.get("previous_versions"):
        lst = ", ".join(f'<a href="{root}papers/{esc(p)}.html">{esc(MS[p]["date"] or p) if p in MS else esc(p)}</a>' for p in m["previous_versions"])
        prev = f'<p class="ms__prev">{esc(C("family.previous_editions"))}: {lst}</p>'
    heads = headline_statements(m)
    if heads:
        stm = "".join(render_paper_statement(m, st, root, conv) for st in heads)
    else:
        stm = f'<p class="muted">{esc(C("family.no_headline"))}</p>'
    counts = m.get("counts") or {}
    return f"""<article class="ms" id="{esc(m['id'])}">
 <h3 class="ms__title"><a href="{root}papers/{esc(m['id'])}.html">{ms_title_html(m)}</a></h3>
 <p class="ms__meta"><span>{esc(m.get('date') or '')}</span><span class="ms__status">{esc(status_label(status))}</span>{pdf_button(m, 'pdflink ext')}</p>
 {notes}
 <div class="ms__abstract tex-auto">{rich(m.get('abstract') or '')}</div>
 {prev}
 <h4 class="ms__sub">{esc(C('family.headline_heading'))}</h4>
 <div class="stmts">{stm}</div>
</article>"""


def build_family(f):
    fid = f["id"]
    rel = f"families/{fid}.html"
    root = "../"
    di = DISC_OF[fid]
    disc = DISCIPLINES[di]["name"]
    title_plain = tex_plain(f["title"])
    mss = [MS[s] for s in f["manuscripts"] if s in MS]
    status, ex = family_exposition_status(fid)
    blocks = []
    convs = {}
    for m in mss:
        conv = TexConv(m, root)
        convs[m["id"]] = conv
        blocks.append(manuscript_block(m, root, conv, f["statements"]))
    # Lean column
    if f["statements"]:
        lean_html = "".join(lean_card_small(s, root) for s in f["statements"] if s in ST)
    else:
        lean_html = f'<p class="muted">{esc(C("family.no_lean"))}</p>'
    scope = ""
    if f.get("lean_doc") and f["lean_doc"].get("scope"):
        scope = f"""<blockquote class="quote md-math">{md_paragraphs(f['lean_doc']['scope'])}<footer><a class="ext" href="{esc(f['lean_doc']['url'])}" rel="noopener">{esc(C('family.lean_scope_source'))}</a></footer></blockquote>"""
    # rests on / cited by
    rests_items, seen = [], set()
    for m in mss:
        for r in m.get("rests_on") or []:
            if r["manuscript"] not in seen:
                seen.add(r["manuscript"])
                rests_items.append((r["manuscript"], r["status"], r["has_lean"]))
    cited_items, seen = [], set()
    for m in mss:
        for c in m.get("cited_by_in_collection") or []:
            if c not in seen and c not in f["manuscripts"]:
                seen.add(c)
                cm = MS.get(c, {})
                cited_items.append((c, cm.get("status", "current"), cm.get("has_lean", False)))
    rests = related_list(rests_items, root, fid) if rests_items else f'<p class="muted">{esc(C("family.rests_none"))}</p>'
    cited = related_list(cited_items, root, fid) if cited_items else f'<p class="muted">{esc(C("family.cited_none"))}</p>'
    # builds on
    builds = []
    for m in mss:
        refs = m.get("references") or []
        if refs:
            items = "".join(ref_entry(r) for r in refs)
            builds.append(f'<details class="builds"><summary>{esc(C("family.builds_summary", count=len(refs), title=tex_plain(m["title"])))}</summary><ol class="refs">{items}</ol></details>')
        else:
            builds.append(f'<p class="muted">{esc(C("family.builds_none"))} ({esc(tex_plain(m["title"]))})</p>')
    # explain box
    if status == "explained":
        ex_line = C("family.explain_done", names=", ".join(n_ for e in ex if e["status"] == "reviewed" for n_ in e["names"]))
    elif status == "claimed":
        ex_line = C("family.explain_claimed", names=", ".join(n_ for e in ex for n_ in e["names"]))
    else:
        ex_line = C("family.explain_open")
    page_url = BASE_URL + rel
    claim = issue_url("claim", C("issues.claim", id=fid, title=title_plain), family=fid)
    problem = issue_url("problem", C("issues.problem_family", id=fid, title=title_plain), page=page_url, family=fid)
    credit = issue_url("credit", C("issues.credit", id=fid, title=title_plain), family=fid)
    check_btn = ""
    if f["statements"]:
        check_btn = f'<a class="btn btn--ghost ext" href="{esc(issue_url("check", C("issues.check", statement=f["statements"][0]), statement=f["statements"][0]))}" rel="noopener">{esc(C("family.check_button"))}</a>'
    credits = CONTRIB["credits"].get(fid, [])
    contributors = ""
    names = [n_ for e in ex for n_ in e["names"]] + [n_ for c_ in credits for n_ in c_["names"]]
    if names:
        contributors = f'<h3 class="h3">{esc(C("family.contributors_heading"))}</h3><p>{esc(", ".join(dict.fromkeys(names)))}</p>'
    facts = C("family.facts", manuscripts=n_ms(len(mss)), discipline=disc, lean=(n_lean(len(f["statements"])) if f["statements"] else C("words.no_lean").capitalize()))
    rs = f.get("reasoning_summary")
    reasoning_html = (f'<p class="muted small">{esc(C("family.reasoning_summary"))} <a class="ext" href="{esc(rs["url"])}" rel="noopener">{esc(rs["title"])}</a></p>') if rs else ""
    fam_claims = CLAIMS_BY_FAMILY.get(fid, [])
    formulations_html = ""
    stmts_c = [c for c in fam_claims if c["kind"] == "statement"]
    thms_c = [c for c in fam_claims if c["kind"] in ("theorem", "lemma")]
    if stmts_c:
        items = []
        for c in stmts_c[:12]:
            head_lines = lean_lines("\n".join((c.get("text") or c["head"]).split("\n")[:14]))
            cmp_note = f' <span class="pill pill--support">{esc(C("family.formulation_checked", id=c["comparator_statement"]))}</span>' if c.get("comparator_statement") else ""
            items.append(f'<li><p><code>{esc(c["name"].split(".")[-1])}</code>{cmp_note} <a class="ext small" href="{esc(BASE_BLOB + c["file"] + "#L" + str(c["line"]))}" rel="noopener">{esc(c["file"].split("/")[-1])}:{c["line"]}</a></p><pre class="lean lean--snippet"><code>{"".join(chr(10) + l for l in head_lines).lstrip(chr(10))}</code></pre></li>')
        more = f'<p class="muted small">{esc(C("family.formulations_more", n=len(stmts_c) - 12))}</p>' if len(stmts_c) > 12 else ""
        thm_line = f'<p class="muted small">{esc(C("family.formulations_theorems", n=len(thms_c)))}</p>' if thms_c else ""
        formulations_html = f'<section class="band" aria-labelledby="h-form"><h2 class="h2" id="h-form">{esc(C("family.formulations_heading"))}</h2><p class="intro">{esc(C("family.formulations_intro"))}</p><ol class="formulations">{"".join(items)}</ol>{more}{thm_line}</section>'

    body = f"""<div class="frame page">
{trail(root, [(esc(disc), f'{root}index.html#d={DISC_SLUG[di]}'), (fam_title_html(f), None)])}
<header class="phead">
 <p class="phead__kicker">{esc(C('family.trail_label', id=fid))}</p>
 <h1 class="phead__title">{fam_title_html(f)}</h1>
 <p class="phead__facts">{esc(facts)}</p>
 {family_facets_html(f, root)}
 <p class="actions"><a class="btn btn--primary" href="#h-explain">{esc(C('family.explain_jump'))}</a><a class="btn btn--ghost" href="{root}index.html#f={fid}">{esc(C('words.show_on_map'))}</a></p>
</header>
{('<section class="band band--tight"><div class="note note--warn"><p class="note__h">' + esc(C('sources.problems_heading')) + '</p>' + findings_list(findings_for(fid, kinds={'error-reported', 'correction', 'replay-fail'}), root) + '</div></section>') if findings_for(fid, kinds={'error-reported', 'correction', 'replay-fail'}) else ''}
<section class="band band--tight" aria-labelledby="h-desc">
 <h2 class="h2" id="h-desc">{esc(C('family.description_heading'))}</h2>
 <blockquote class="quote quote--lead"><div class="tex-auto">{rich(f['description'], '', root, link_results=True)}</div><footer><a class="ext" href="{BASE_BLOB}CONTENTS.md" rel="noopener">{esc(C('family.description_source'))}</a></footer></blockquote>
 {('<h3 class="h3">' + esc(C('sources.said_heading')) + '</h3>' + findings_list(findings_for(fid, kinds={'commentary'}), root)) if findings_for(fid, kinds={'commentary'}) else ''}
</section>
<div class="split">
 <section class="split__main" aria-labelledby="h-ms">
  <h2 class="h2" id="h-ms">{esc(C('family.manuscripts_heading'))}</h2>
  <p class="intro">{esc(C('family.headline_note'))}</p>
  {''.join(blocks)}
 </section>
 <aside class="split__side" aria-labelledby="h-lean">
  <div>
   <h2 class="h2" id="h-lean">{esc(C('family.lean_heading'))}</h2>
   {lean_html}
   {('<h3 class="h3">' + esc(C('family.lean_scope_heading')) + '</h3>' + scope) if scope else ''}
   {reasoning_html}
  </div>
 </aside>
</div>
{formulations_html}
<section class="band" aria-labelledby="h-rests">
 <div class="cols2">
  <div><h2 class="h2" id="h-rests">{esc(C('family.rests_heading'))}</h2><p class="intro">{esc(C('family.rests_intro'))}</p>{rests}</div>
  <div><h2 class="h2">{esc(C('family.cited_heading'))}</h2><p class="intro">{esc(C('family.cited_intro'))}</p>{cited}{('<h3 class="h3">' + esc(C('sources.followups_heading')) + '</h3>' + findings_list(findings_for(fid, kinds={'follow-up-result'}), root)) if findings_for(fid, kinds={'follow-up-result'}) else ''}</div>
 </div>
</section>
<section class="band" aria-labelledby="h-builds">
 <h2 class="h2" id="h-builds">{esc(C('family.builds_heading'))}</h2>
 <p class="intro">{esc(C('family.builds_intro'))}</p>
 {''.join(builds)}
</section>
<section class="band explain-box" aria-labelledby="h-explain">
 <h2 class="h2" id="h-explain">{esc(C('family.explain_heading'))}</h2>
 <p class="explain-box__text">{esc(ex_line)}</p>
 {('<h3 class="h3">' + esc(C('sources.explanations_heading')) + '</h3>' + findings_list(findings_for(fid, kinds={'explanation'}), root)) if findings_for(fid, kinds={'explanation'}) else ''}
 <p class="actions"><a class="btn btn--primary ext" href="{esc(claim)}" rel="noopener">{esc(C('family.claim_button'))}</a>{check_btn}<a class="btn btn--ghost ext" href="{esc(credit)}" rel="noopener">{esc(C('family.credit_button'))}</a><a class="btn btn--quiet ext" href="{esc(problem)}" rel="noopener">{esc(C('family.problem_button'))}</a></p>
 {contributors}
</section>
</div>
{macros_script([m['id'] for m in mss])}"""
    desc = tex_plain(f["description"])
    write_page(rel, page(rel, title_plain, desc, body, page_type="article"))


def build_paper(m):
    slug = m["id"]
    rel = f"papers/{slug}.html"
    root = "../"
    fam = FAM.get(m.get("family") or "")
    title_plain = tex_plain(m["title"])
    items = []
    if fam:
        di = DISC_OF[fam["id"]]
        tr = trail(root, [(esc(DISCIPLINES[di]["name"]), f'{root}index.html#d={DISC_SLUG[di]}'),
                          (fam_title_html(fam), f'{root}families/{fam["id"]}.html'), (ms_title_html(m), None)])
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


def receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html, *, standalone=False):
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    label = (stmt.get("labels") or [stmt["id"]])[0]
    vocab = stmt["vocabulary_count"]
    vtext = C("statement.card_vocab_zero") if vocab == 0 else (C("statement.card_vocab_one") if vocab == 1 else C("statement.card_vocab", count=vocab))
    if paper_st:
        kind = esc(paper_st["display"]) + (f' <span class="rc__sttitle">({conv.text(paper_st["title"], inline=True)})</span>' if paper_st.get("title") else "")
        paper_body = conv.blocks(paper_st["text"])
        paper_src = f'<p class="rc__src"><span class="tex-auto">{rich(paper_ms["title"])}</span></p>'
    else:
        kind = ""
        paper_body = f'<p>{esc(C("family.no_headline"))}</p>'
        paper_src = ""
    snippet = lean_snippet_html(stmt, lines_html, max_lines=18)
    axioms = ", ".join(stmt["comparator"]["permitted_axioms"]) or "none"
    note = C("statement.sorry_note_axiom") if stmt["declares_axiom"] else C("statement.sorry_note")
    hl = stmt["comparator"].get("definition_names") or []
    hole_note = ""
    if hl:
        hole_note = C("statement.card_holes_one", name=hl[0].split(".")[-1]) if len(hl) == 1 else C("statement.card_holes_many", n=len(hl), name=hl[0].split(".")[-1])
        hole_note = f'<p class="rc__note rc__note--hole">{ctext(hole_note)}</p>'
    shown_url = page_url.replace("https://", "")
    return f"""<div class="rc-wrap{' rc-wrap--solo' if standalone else ''}"><article class="rc" data-macros="{esc(paper_ms['id']) if paper_ms else ''}" aria-label="{esc(C('statement.card_heading'))}">
 <header class="rc__head">
  <p class="rc__brand">{MARK_SVG}<span translate="no">{esc(C('site.name'))}</span></p>
  <h2 class="rc__title md-math">{esc(label)}</h2>
  <p class="rc__fam">{esc(C('words.result').capitalize())} {esc(fam['id'] if fam else '')}: <span class="tex-auto">{rich(fam['title']) if fam else ''}</span></p>
 </header>
 <div class="rc__cols">
  <section class="rc__paper"><p class="rc__label">{esc(C('statement.card_paper'))}</p><p class="rc__kind">{kind}</p><div class="rc__fit"><div class="rc__body">{paper_body}</div></div>{paper_src}</section>
  <section class="rc__lean"><p class="rc__label">{esc(C('statement.card_lean'))}</p><div class="rc__fit"><pre class="lean lean--card"><code>{snippet}</code></pre></div><p class="rc__note">{ctext(note)}</p>{hole_note}</section>
 </div>
 <footer class="rc__foot">
  <span class="rc__fact"><strong>{esc(vtext)}</strong></span>
  <span class="rc__fact">{esc(C('statement.card_axioms', axioms=axioms))}</span>
  <span class="rc__fact">{esc(C('statement.card_commit', commit_short=COMMIT_SHORT))}</span>
  <span class="rc__url">{esc(shown_url)}</span>
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


def build_statement(stmt, og_available: set):
    sid = stmt["id"]
    rel = f"statements/{sid}.html"
    root = "../"
    page_url = BASE_URL + rel
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    label = (stmt.get("labels") or [sid])[0]
    lines_html = lean_lines(stmt["lean"])
    paper_ms, paper_st = pair_statement(stmt)
    conv = TexConv(paper_ms, root) if paper_ms else None
    card = receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html)
    # full card page for screenshots
    card_rel = f"cards/{sid}.html"
    card_body = receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html, standalone=True)
    write_page(card_rel, head(card_rel, label, label, noindex=True) + f'\n<body class="card-only" data-root="{root}">\n{card_body}\n{macros_script([paper_ms["id"]] if paper_ms else [])}\n</body></html>\n', index=False)
    # facts
    sol = stmt.get("solution") or []
    sol_html = ", ".join(f'<a class="ext" href="{esc(x["url"])}" rel="noopener"><code>{esc(x["file"])}</code></a>' for x in sol) or f'<code>{esc(stmt["comparator"].get("solution_module") or "")}</code>'
    nm = stmt["non_mathlib_imports"]
    facts = [
        (C("statement.file_label"), f'<a class="ext" href="{esc(stmt["url"])}" rel="noopener"><code>{esc(stmt["file"])}</code></a>'),
        (C("statement.main_key"), esc(C("statement.main_yes") if stmt["main_result"] else C("statement.main_no", id=(stmt.get("families") or [""])[0]))),
        (C("statement.solution"), sol_html),
        (C("statement.permitted_axioms"), ", ".join(f"<code>{esc(a)}</code>" for a in stmt["comparator"]["permitted_axioms"]) + f'<span class="dl__note">{esc(C("statement.permitted_axioms_note"))}</span>'),
        (C("statement.imports"), ", ".join(f"<code>{esc(a)}</code>" for a in stmt["imports"])),
        (C("statement.non_mathlib"), ", ".join(f"<code>{esc(a)}</code>" for a in nm) if nm else esc(C("statements.none"))),
        (C("statement.lines"), num(stmt["statement_lines"])),
        (C("statement.replay_key"), (esc(C("statement.replay_none")) if not (CONTRIB["replays"].get(sid) or findings_for(sid=sid, kinds={"replay-pass", "replay-fail"})) else (esc(C("statement.replay_some", n=len(CONTRIB["replays"].get(sid, [])))) if CONTRIB["replays"].get(sid) else "") + findings_list(findings_for(sid=sid, kinds={"replay-pass", "replay-fail"}), root))),
        (C("statement.nanoda_key"), esc(C("statement.nanoda_yes") if stmt["comparator"].get("enable_nanoda") else C("statement.nanoda_no"))),
    ]
    dl = "".join(f"<div><dt>{esc(k)}</dt><dd>{v}</dd></div>" for k, v in facts)
    # axiom note
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
        axiom = f'<section class="band band--tight"><div class="note"><p class="note__h">{esc(C("statement.axiom_heading"))}</p><p>{note}</p></div></section>'
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
        holes_html = f'<section class="band band--tight" aria-labelledby="h-holes"><h2 class="h2" id="h-holes">{esc(C("statement.holes_heading"))} <span class="count">{len(holes)}</span></h2><p class="intro">{ctext(C("statement.holes_intro"))}</p><ul class="holes">{"".join(items)}</ul></section>'
    # vocabulary
    decl_doc = {d["name"]: d.get("doc") for d in stmt["declarations"]}
    if stmt["vocabulary"]:
        rows = []
        for v in stmt["vocabulary"]:
            nm_full = v["name"] or ""
            parts = nm_full.rsplit(".", 1)
            ns_ = f'<span class="vocab__ns">{esc(parts[0])}.</span>' if len(parts) == 2 else ""
            doc = decl_doc.get(nm_full)
            rows.append(f'<li><a href="#L{v["line"]}"><span class="vocab__kind">{esc(kind_word(v["kind"]))}</span> <code>{ns_}{esc(parts[-1])}</code> <span class="vocab__line">{esc(C("statement.line", line=v["line"]))}</span></a>{f"<span class=\"vocab__doc\">{esc(doc)}</span>" if doc else ""}</li>')
        vocab = f'<p class="intro">{esc(C("statement.vocab_intro"))}</p><ol class="vocab">{"".join(rows)}</ol>'
    else:
        vocab = f'<p class="intro">{esc(C("statement.vocab_none"))}</p>'
    # scope
    scope = ""
    if fam and fam.get("lean_doc") and fam["lean_doc"].get("scope"):
        scope = f'<section class="band band--tight"><h2 class="h2">{esc(C("statement.scope_heading"))}</h2>{coverage_html(sid)}<blockquote class="quote md-math">{md_paragraphs(fam["lean_doc"]["scope"])}<footer><a class="ext" href="{esc(fam["lean_doc"]["url"])}" rel="noopener">{esc(C("statement.scope_source", id=fam["id"]))}</a></footer></blockquote></section>'
    # side by side
    paper_cols = []
    for slug in stmt.get("papers") or []:
        m = MS.get(slug)
        if not m:
            continue
        cv = TexConv(m, root)
        heads = headline_statements(m)
        inner = "".join(render_paper_statement(m, st, root, cv, "pst") for st in heads) or f'<p class="muted">{esc(C("family.no_headline"))}</p>'
        paper_cols.append(f'<div class="sbs__paper"><h3 class="h3"><a href="{root}papers/{esc(slug)}.html">{ms_title_html(m)}</a></h3>{inner}</div>')
    snippet_full = lean_snippet_html(stmt, lines_html)
    # file
    code_lines = "".join(f'<span class="ln" id="L{i}" data-n="{i}">{l}</span>' for i, l in enumerate(lines_html, 1))
    checks = CONTRIB["checks"].get(sid, [])
    replays = CONTRIB["replays"].get(sid, [])
    checks_html = "".join(f'<li><strong>{esc(c["name"])}</strong>{(": " + esc(c["verdict"])) if c.get("verdict") else ""}</li>' for c in checks)
    replays_html = "".join(f'<li><strong>{esc(c["name"])}</strong>{(": " + esc(c["verdict"])) if c.get("verdict") else ""}</li>' for c in replays)
    check_url = issue_url("check", C("issues.check", statement=sid), statement=sid)
    replay_url = issue_url("replay", C("issues.replay", statement=sid), statement=sid)
    problem_url = issue_url("problem", C("issues.problem_statement", statement=sid), page=page_url, statement=sid)
    trail_items = []
    if fam:
        di = DISC_OF[fam["id"]]
        trail_items = [(esc(DISCIPLINES[di]["name"]), f'{root}index.html#d={DISC_SLUG[di]}'), (fam_title_html(fam), f'{root}families/{fam["id"]}.html')]
    trail_items.append((f'<span class="md-math">{esc(label)}</span>', None))
    body = f"""<div class="frame page">
{trail(root, trail_items)}
<header class="phead">
 <p class="phead__kicker">{esc(C('statement.trail_label'))} <code>{esc(sid)}</code></p>
 <h1 class="phead__title md-math">{esc(label)}</h1>
 <p class="phead__facts">{esc(C('statement.main_yes') if stmt['main_result'] else C('statement.main_no', id=(stmt.get('families') or [''])[0]))}</p>
 <p class="actions"><a class="btn btn--primary ext" href="{esc(check_url)}" rel="noopener">{esc(C('statement.check_button'))}</a><a class="btn btn--ghost" href="#h-file">{esc(C('statement.file_heading'))}</a></p>
</header>
<section class="band band--card" aria-labelledby="h-card">
 <h2 class="vh" id="h-card">{esc(C('statement.card_heading'))}</h2>
 {card}
 <p class="card-tools"><button class="btn btn--ghost copy" type="button" data-copy-text="{esc(page_url)}">{esc(C('statement.copy_link'))}</button><span class="muted small">{esc(C('statement.card_intro'))} {esc(C('statement.card_pairing'))}</span></p>
</section>
{axiom}
{holes_html}
{('<section class="band band--tight"><div class="note note--warn"><p class="note__h">' + esc(C('sources.problems_heading')) + '</p>' + findings_list(findings_for(sid=sid, kinds={'error-reported', 'correction', 'replay-fail'}), root) + '</div></section>') if findings_for(sid=sid, kinds={'error-reported', 'correction', 'replay-fail'}) else ''}
<section class="band band--tight"><div class="note"><p class="note__h">{esc(C("statement.comparator_box_heading"))}</p><p>{ctext(C("statement.comparator_box_does"))}</p><p>{ctext(C("statement.comparator_box_not"))}</p></div></section>
<section class="band band--tight"><dl class="dl">{dl}</dl></section>
{scope}
<section class="band" aria-labelledby="h-sbs">
 <h2 class="h2" id="h-sbs">{esc(C('statement.paper_heading'))}</h2>
 <p class="intro">{esc(C('statement.paper_intro'))}</p>
 <div class="sbs"><div class="sbs__left">{''.join(paper_cols)}</div><div class="sbs__right"><div class="{'sticky' if snippet_full.count('class="ln"') <= 26 else ''}"><pre class="lean lean--snippet"><code>{snippet_full}</code></pre><p class="leanc__note">{ctext(C('statement.sorry_note_axiom') if stmt['declares_axiom'] else C('statement.sorry_note'))}</p></div></div></div>
</section>
<section class="band" aria-labelledby="h-vocab">
 <h2 class="h2" id="h-vocab">{esc(C('statement.vocab_heading'))} <span class="count">{num(stmt['vocabulary_count'])}</span></h2>
 {vocab}
</section>
<section class="band" aria-labelledby="h-file">
 <h2 class="h2" id="h-file">{esc(C('statement.file_heading'))}</h2>
 <p class="intro">{esc(C('statement.file_intro', lines=len(lines_html)))} <span class="muted">{ctext(C('statement.sorry_note_axiom') if stmt['declares_axiom'] else C('statement.sorry_note'))}</span></p>
 <pre class="lean lean--file"><code>{code_lines}</code></pre>
</section>
<section class="band explain-box" aria-labelledby="h-checks">
 <h2 class="h2" id="h-checks">{esc(C('statement.checks_heading'))}</h2>
 {f'<ul>{checks_html}</ul>' if checks else f'<p>{esc(C("statement.checks_none"))}</p>'}
 <h3 class="h3">{esc(C('statement.replays_heading'))}</h3>
 {f'<ul>{replays_html}</ul>' if replays else f'<p>{esc(C("statement.replays_none"))}</p>'}
 {('<h3 class="h3">' + esc(C('sources.statement_more')) + '</h3>' + findings_list(findings_for(sid=sid, kinds={'explanation', 'commentary', 'follow-up-result'}), root)) if findings_for(sid=sid, kinds={'explanation', 'commentary', 'follow-up-result'}) else ''}
 <p class="actions"><a class="btn btn--ghost ext" href="{esc(check_url)}" rel="noopener">{esc(C('statement.check_button'))}</a><a class="btn btn--ghost ext" href="{esc(replay_url)}" rel="noopener">{esc(C('statement.replay_button'))}</a><a class="btn btn--quiet ext" href="{esc(problem_url)}" rel="noopener">{esc(C('statement.problem_button'))}</a></p>
</section>
</div>
{macros_script(list(dict.fromkeys(([paper_ms['id']] if paper_ms else []) + list(stmt.get('papers') or []))))}"""
    og = BASE_URL + f"og/{sid}.png" if sid in og_available else None
    desc = f"{label}. " + (C("statement.main_yes") if stmt["main_result"] else C("statement.main_no", id=(stmt.get("families") or [""])[0])) + " " + (C("statement.card_vocab", count=stmt["vocabulary_count"]) + ".")
    write_page(rel, page(rel, f"{label} (Lean)", desc, body, og_image=og, page_type="article"))


# ------------------------------------------------------------------- home


def map_data():
    fams = []
    for f in FAMILIES:
        status, _ = family_exposition_status(f["id"])
        mss = [MS[s] for s in f["manuscripts"] if s in MS]
        fams.append({
            "id": f["id"],
            "t": f["title"],
            "p": tex_plain(f["title"]),
            "d": DISC_OF[f["id"]],
            "m": [[m["title"], m.get("date") or "", m["pdf_url"].replace(BASE_BLOB, ""), m["id"]] for m in mss],
            "s": [[(ST[s].get("labels") or [s])[0], 1 if ST[s]["main_result"] else 0, ST[s]["vocabulary_count"], s] for s in f["statements"] if s in ST],
            "v": fam_max_vocab(f),
            "c": FAM_CITES[f["id"]],
            "b": FAM_CITED_BY[f["id"]],
            "k": fam_cited_by_ms(f),
            "x": {"open": 0, "claimed": 1, "explained": 2}[status],
            "w": len(COMMUNITY["by_family"].get(f["id"], [])) + len(COMMUNITY["efforts_by_family"].get(f["id"], [])),
            "ty": (sourced(f, "type") or {}).get("value"),
            "ti": (sourced(f, "tier") or {}).get("value"),
            "g": fam_cover_grade(f),
        })
    vocab = sorted(v for v in (x["v"] for x in fams) if v is not None)
    return {
        "blob": BASE_BLOB,
        "disciplines": [{"name": d["name"], "slug": DISC_SLUG[i], "families": d["families"]} for i, d in enumerate(DISCIPLINES)],
        "families": fams,
        "sizeBins": size_bins(vocab),
    }


def size_bins(vals):
    """Four bins for families with Lean: Mathlib-only (0) and three quantile bins above it."""
    pos = [v for v in vals if v > 0]
    if not pos:
        return []
    q = lambda p: pos[min(len(pos) - 1, int(p * len(pos)))]
    a, b = q(1 / 3), q(2 / 3)
    return [[0, 0], [1, a], [a + 1, b], [b + 1, None]]


NUMBER_KEYS = [
    ("families", "results", "numbered results in the release's contents list"),
    ("disciplines", "disciplines", ""),
    ("manuscripts_current", "current manuscripts", ""),
    ("statements_lean", "Lean statements", ""),
    ("statements_lean_main_results", "Lean statements of main results", ""),
    ("families_with_lean", "results with a Lean statement", ""),
    ("manuscripts_with_lean", "manuscripts with an accompanying Lean statement", ""),
    ("internal_citation_edges", "citations between manuscripts in the collection", ""),
    ("external_works_cited", "outside works cited", ""),
]

# Labels and computation notes for every summary number. Prose lives in copy.json
# under numbers.items; this list only fixes the order.
NUMBER_ORDER = ["families", "disciplines", "manuscripts_current", "manuscripts_withdrawn", "manuscripts_previous_editions",
                "statements_lean", "statements_lean_main_results", "main_result_declarations", "families_with_lean",
                "manuscripts_with_lean", "lean_statements_pure_mathlib", "lean_statements_with_custom_vocabulary",
                "lean_statements_importing_non_mathlib", "lean_statements_declaring_axioms", "lean_vocabulary_total",
                "lean_vocabulary_median", "lean_vocabulary_max", "internal_citation_edges", "manuscripts_citing_collection",
                "manuscripts_citing_unformalised_collection_results", "external_works_cited", "external_citations"]
HOME_NUMBERS = ["families", "manuscripts_current", "statements_lean", "statements_lean_main_results",
                "families_with_lean", "manuscripts_with_lean", "internal_citation_edges", "external_works_cited"]


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
    rel = "index.html"
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
    ov = [("lean", "home.overlay_lean"), ("covers", "home.overlay_covers"), ("type", "home.overlay_type"), ("tier", "home.overlay_tier"), ("community", "home.overlay_community"), ("size", "home.overlay_size"), ("rests", "home.overlay_rests"), ("explained", "home.overlay_explained")]
    ov_btns = "".join(f'<button type="button" class="seg__b" data-overlay="{k}" aria-pressed="{"true" if k == "lean" else "false"}">{esc(C(lab))}</button>' for k, lab in ov)
    strings = {k: v for k, v in COPY["home"].items()}
    strings.update({"manuscript": C("words.manuscript"), "manuscripts": C("words.manuscripts"),
                    "lean_statement": C("words.lean_statement"), "lean_statements": C("words.lean_statements"),
                    "no_lean": C("words.no_lean"), "main_result": C("words.main_result"),
                    "supporting_result": C("words.supporting_result"), "result": C("words.result"), "results": C("words.results")})
    n_open = sum(1 for f in FAMILIES if family_exposition_status(f["id"])[0] == "open")
    body = f"""<section class="atlas" aria-labelledby="h-atlas">
 <div class="atlas__panel">
  <div class="atlas__intro">
   <h1 class="atlas__title" id="h-atlas">{esc(C('home.title'))}</h1>
   <p class="atlas__lede">{esc(lede)}</p>
   <p class="actions"><a class="btn btn--primary" href="explain.html">{esc(C('home.cta_explain'))}</a><a class="btn btn--ghost" href="statements.html">{esc(C('home.cta_check'))}</a></p>
  </div>
  <div class="atlas__controls">
   <div class="msearch">
    <label class="vh" for="map-search">{esc(C('home.search_label'))}</label>
    <input id="map-search" class="msearch__input" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(C('home.search_placeholder'))}" role="combobox" aria-expanded="false" aria-controls="map-search-list" aria-autocomplete="list">
    <ul class="msearch__list" id="map-search-list" role="listbox" hidden></ul>
   </div>
   <div class="seg" role="group" aria-label="{esc(C('home.overlay_label'))}"><span class="seg__label">{esc(C('home.overlay_label'))}</span><div class="seg__row">{ov_btns}</div></div>
   <div class="legend" aria-live="polite"></div>
  </div>
  <nav class="where" aria-label="{esc(C('home.where_label'))}"></nav>
  <div class="card" hidden></div>
 </div>
 <div class="atlas__stage">
  <div class="field" role="application" aria-label="{esc(C('home.map_heading'))}" aria-describedby="map-help"><noscript><p class="field__noscript">{esc(C('home.no_js'))}</p></noscript></div>
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
  <div><h3 class="h3"><a href="builds-on.html">{esc(C('home.credit_builds'))}</a></h3><p>{esc(C('home.credit_builds_text', works=s['external_works_cited'], top1=work_name(0), top2=work_name(1)))}</p></div>
  <div><h3 class="h3"><a href="rests-on.html">{esc(C('home.credit_rests'))}</a></h3><p>{esc(C('home.credit_rests_text'))}</p></div>
  {('<div><h3 class="h3"><a href="sources.html">' + esc(C('home.credit_community')) + '</a></h3><p>' + esc(C('home.credit_community_text', efforts=len(COMMUNITY['list']), people=len({(a.get('name') or a.get('handle')) for e in COMMUNITY['list'] for a in (e.get('authors') or [])}), findings=len(COMMUNITY['findings']))) + '</p></div>') if COMMUNITY['list'] else ''}
 </div>
</section>
<section class="frame band idx" aria-labelledby="h-index">
 <h2 class="h2" id="h-index">{esc(C('home.index_heading'))}</h2>
 <p class="intro">{esc(C('home.index_intro', families=s['families']))}</p>
 <div class="idx__grid">{''.join(idx)}</div>
</section>
{json_script('map-strings', strings)}"""
    extra = '<link rel="preload" href="data/atlas-map.json" as="fetch" crossorigin>\n<script defer src="assets/map.js"></script>'
    write_page(rel, page(rel, C("site.name"), C("site.description", release_date=CFG["release_date"]), body, current="atlas", extra_head=extra, main_class="main--home"))


def build_explain():
    rel = "explain.html"
    root = ""
    rows = []
    counts = Counter()
    for f in FAMILIES:
        st, ex = family_exposition_status(f["id"])
        counts[st] += 1
        di = DISC_OF[f["id"]]
        claim = issue_url("claim", C("issues.claim", id=f["id"], title=tex_plain(f["title"])), family=f["id"])
        lean = "✓" if f["statements"] else ""
        claim_label = esc(C("explain.claim"))
        claim_html = "" if st == "explained" else f'<a class="btn btn--small ext" href="{esc(claim)}" rel="noopener">{claim_label}</a>'
        who = f'<span class="muted small"> {esc(", ".join(e["name"] for e in ex))}</span>' if ex else ""
        rows.append(f'<tr data-d="{DISC_SLUG[di]}" data-s="{st}"><td class="t-title"><a href="families/{f["id"]}.html">{fam_title_html(f)}</a></td>'
                    f'<td>{esc(DISCIPLINES[di]["name"])}</td><td class="t-num">{len(f["manuscripts"])}</td>'
                    f'<td class="t-c">{"<span class=\"pill pill--main\" title=\"" + esc(n_lean(len(f["statements"]))) + "\">" + num(len(f["statements"])) + "</span>" if lean else ""}</td>'
                    f'<td><span class="st st--{st}">{esc(C("explain.status_" + st))}</span>{who}</td>'
                    f'<td>{claim_html}</td></tr>')
    dbtns = [f'<button type="button" class="chip" data-filter-d="" aria-pressed="true">{esc(C("explain.all"))}</button>']
    for i, d in enumerate(DISCIPLINES):
        dbtns.append(f'<button type="button" class="chip" data-filter-d="{DISC_SLUG[i]}" aria-pressed="false">{esc(d["name"])} <span class="count">{len(d["families"])}</span></button>')
    sbtns = [f'<button type="button" class="chip" data-filter-s="" aria-pressed="true">{esc(C("explain.all"))}</button>']
    for k in ("open", "claimed", "explained"):
        sbtns.append(f'<button type="button" class="chip" data-filter-s="{k}" aria-pressed="false">{esc(C("explain.status_" + k))} <span class="count">{counts[k]}</span></button>')
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('explain.title'))}</h1>
 <p class="lede">{esc(C('explain.lede', open=counts['open'], families=len(FAMILIES)))}</p>
 <p>{esc(C('explain.how'))} <a class="ext" href="{esc(REPO + '/' + CFG['contributing_path'])}" rel="noopener">{esc(C('contribute.guide_link'))}</a></p>
</header>
<div class="filters" data-filter-table="explain-table">
 <div class="filters__g"><p class="filters__h">{esc(C('explain.filter_discipline'))}</p><div class="chips">{''.join(dbtns)}</div></div>
 <div class="filters__g"><p class="filters__h">{esc(C('explain.filter_status'))}</p><div class="chips">{''.join(sbtns)}</div></div>
 <p class="filters__n muted" aria-live="polite" data-shown-template="{esc(C('explain.shown', n='{n}'))}">{esc(C('explain.shown', n=len(FAMILIES)))}</p>
</div>
<div class="table-wrap"><table class="tbl" id="explain-table">
 <thead><tr><th scope="col">{esc(C('explain.col_result'))}</th><th scope="col">{esc(C('explain.col_discipline'))}</th><th scope="col" class="t-num">{esc(C('explain.col_papers'))}</th><th scope="col" class="t-c">{esc(C('explain.col_lean'))}</th><th scope="col">{esc(C('explain.col_status'))}</th><th scope="col"><span class="vh">{esc(C('explain.claim'))}</span></th></tr></thead>
 <tbody>{''.join(rows)}</tbody>
</table></div>
</div>"""
    write_page(rel, page(rel, C("explain.title"), C("explain.lede", open=counts["open"], families=len(FAMILIES)), body, current="explain"))


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
    items = []
    for k in NUMBER_ORDER:
        if k not in s:
            continue
        it = number_item(k)
        d = defs.get(k) or defs.get(it.get("definition_key", "")) or it.get("definition", "")
        extra = ""
        if k == "lean_vocabulary_max" and s.get("lean_vocabulary_max_statement") in ST:
            sid = s["lean_vocabulary_max_statement"]
            extra = f' <a href="statements/{esc(sid)}.html"><code>{esc(sid)}</code></a>'
        if k == "lean_statements_declaring_axioms" and s.get("lean_statements_declaring_axioms_ids"):
            extra = " " + ", ".join(f'<a href="statements/{esc(x)}.html"><code>{esc(x)}</code></a>' for x in s["lean_statements_declaring_axioms_ids"])
        if k == "lean_statements_pure_mathlib" and s.get("lean_statements_pure_mathlib_ids"):
            extra = " " + ", ".join(f'<a href="statements/{esc(x)}.html"><code>{esc(x)}</code></a>' for x in s["lean_statements_pure_mathlib_ids"])
        items.append(f"""<article class="numrow" id="{k}">
 <p class="numrow__v">{num(s[k])}</p>
 <div class="numrow__t">
  <h2 class="h3">{esc(it.get('label', k))}</h2>
  <p><span class="numrow__k">{esc(C('numbers.definition'))}.</span> {esc(d)}{extra}</p>
  <p><span class="numrow__k">{esc(C('numbers.how'))}.</span> {esc(it.get('how', ''))}</p>
 </div>
</article>""")
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
    for key in ("families_with_lean_in_scope_notes", "families_with_a_paper_in_formalization_yaml_sources", "papers_in_formalization_yaml_sources", "tier_list_families_with_lean", "tier_list_lean_formalisations_total"):
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
<section class="band" aria-labelledby="h-envs"><h2 class="h2" id="h-envs">{esc(C('numbers.envs_heading'))}</h2><p class="intro">{esc(C('numbers.envs_intro', manuscripts=s['manuscripts_current']))}</p><table class="tbl tbl--narrow"><tbody>{env_rows}</tbody></table></section>
<section class="band" aria-labelledby="h-wd"><h2 class="h2" id="h-wd">{esc(C('numbers.withdrawn_heading'))}</h2><p class="intro">{esc(C('numbers.withdrawn_intro', n=len(wd)))}</p>{wd_html}</section>
<section class="band" aria-labelledby="h-hist"><h2 class="h2" id="h-hist">{esc(C('numbers.changelog_heading'))}</h2>{hist}</section>
</div>"""
    write_page(rel, page(rel, C("numbers.title"), C("numbers.lede", commit_short=COMMIT_SHORT), body, current="numbers"))


def build_builds_on():
    rel = "builds-on.html"
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
  <p class="work__n">{esc(C('builds_on.cited_by', n=w['citing_manuscripts']))} {' '.join(links)}</p>
  <ul class="work__list">{cites}</ul>
 </div>
</article>""")
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('builds_on.title'))}</h1>
 <p class="lede">{esc(C('builds_on.lede', works=SUMMARY['external_works_cited'], citations=SUMMARY['external_citations'], n=len(hl)))}</p>
 <p>{esc(C('builds_on.credit'))}</p>
 <p class="muted small">{esc(C('builds_on.how'))}</p>
</header>
<section class="band band--tight">{''.join(rows)}</section>
</div>"""
    write_page(rel, page(rel, C("builds_on.title"), C("builds_on.lede", works=SUMMARY["external_works_cited"], citations=SUMMARY["external_citations"], n=len(hl)), body))


def build_sources():
    rel = "sources.html"
    rows = []
    s = SUMMARY
    up = f"""<article class="ceff" id="src-openai-math">
 <h3 class="h3"><a class="ext" href="{esc(CFG['upstream_repo'])}/tree/{COMMIT}" rel="noopener">openai/math</a></h3>
 <p class="muted small">OpenAI · {esc(C('sources.pinned', commit=COMMIT_SHORT))} · Apache-2.0</p>
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
 <p class="muted small">{esc(authors)} · {esc(C('sources.snapshot', date=src.get('snapshot') or ''))} · {esc(C('sources.licence', licence=src.get('licence') or 'n/a'))}</p>
 <p>{esc(src.get('method') or '')}</p>
 <ul class="small">{flist}</ul>
</article>""")
    efforts = []
    for e in sorted(COMMUNITY["list"], key=lambda x: (x.get("kind") or "", x.get("date") or "", x["name"])):
        nf = sum(1 for f in COMMUNITY["findings"] if f.get("effort") == e["id"])
        fams = sorted({f["family"] for f in COMMUNITY["findings"] if f.get("effort") == e["id"] and f.get("family") in FAM} | {x for x in (e.get("families") or []) if x in FAM})
        fam_links = ", ".join(f'<a href="families/{esc(x)}.html">{esc(x)}</a>' for x in fams[:10]) + (" …" if len(fams) > 10 else "")
        efforts.append(f"""<article class="ceff" id="src-{esc(e['id'])}">
 <h3 class="h3"><a class="ext" href="{esc(e['url'])}" rel="noopener">{esc(e['name'])}</a></h3>
 <p class="muted small">{esc(credit_names(e))}{' · ' if credit_names(e) else ''}{esc(e.get('date') or '')} · {esc(C('community.reuse_' + e.get('reuse', 'link')))} {esc(C('community.licence', licence=e.get('licence') or 'n/a'))}</p>
 <p>{esc(e['summary'])}</p>
 {('<p class="small">' + esc(C('sources.used_on', n=nf)) + ' ' + fam_links + '</p>') if fams else ''}
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


def build_rests_on():
    rel = "rests-on.html"
    hl = SUMMARY.get("highlights", {}).get("most_cited_inside_collection", [])
    rows = []
    for k, e in enumerate(hl, 1):
        m = MS.get(e["manuscript"])
        if not m:
            continue
        f = FAM.get(e.get("family") or "")
        citing = "".join(f'<li><a href="papers/{esc(c)}.html">{ms_title_html(MS[c])}</a></li>' for c in m.get("cited_by_in_collection") or [] if c in MS)
        lean = C("rests_on.lean_yes") if e.get("has_lean") else C("rests_on.lean_no")
        rows.append(f"""<article class="work" id="rests-{k}">
 <p class="work__rank">{k}</p>
 <div class="work__t">
  <h2 class="work__h"><a href="papers/{esc(m['id'])}.html">{ms_title_html(m)}</a></h2>
  <p class="work__n">{esc(C('rests_on.cited_by', n=e['cited_by']))}. {esc(lean)}.{(' ' + C('words.result').capitalize() + ' <a href="families/' + f['id'] + '.html">' + fam_title_html(f) + '</a>') if f else ''}</p>
  <ul class="work__list">{citing}</ul>
 </div>
</article>""")
    body = f"""<div class="frame page">
<header class="phead">
 <h1 class="phead__title">{esc(C('rests_on.title'))}</h1>
 <p class="lede">{esc(C('rests_on.lede', edges=SUMMARY['internal_citation_edges'], n=len(hl)))}</p>
 <p class="muted small">{esc(C('rests_on.how'))}</p>
</header>
<section class="band band--tight">{''.join(rows)}</section>
</div>"""
    write_page(rel, page(rel, C("rests_on.title"), C("rests_on.lede", edges=SUMMARY["internal_citation_edges"], n=len(hl)), body))


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
    body = f"""<div class="frame page page--narrow prose-page">
<header class="phead"><h1 class="phead__title">{esc(C('about.title'))}</h1></header>
<section class="band band--tight"><h2 class="h2">{esc(C('about.what_heading'))}</h2><p>{esc(C('about.what', **fill))}</p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.how_heading'))}</h2><p>{esc(C('about.how', **fill))}</p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.independence_heading'))}</h2><p>{esc(C('about.independence'))}</p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.made_heading'))}</h2><p>{esc(C('about.made'))}</p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.not_heading'))}</h2><p>{esc(C('about.not'))}</p></section>
{('<section class="band band--tight"><h2 class="h2">' + esc(C('about.interests_heading')) + '</h2><p>' + esc(C('about.interests')) + '</p></section>') if C('about.interests') else ''}
<section class="band band--tight"><h2 class="h2">{esc(C('about.disclosed_heading'))}</h2><p>{esc(C('about.disclosed_intro'))}</p><ul>{disclosed_items}</ul><p class="muted small">{esc(C('about.disclosed_not'))}</p></section>
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
    return f"""<!doctype html><html lang="en-GB" data-theme="dark"><head><meta charset="utf-8"><link rel="stylesheet" href="{esc(CFG['fonts_css'])}"><link rel="stylesheet" href="../assets/atlas.css"></head>
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


def render_png(pages: list[tuple[Path, Path]], workers: int = 4):
    """Screenshot card pages to PNG with a headless browser, a few at a time."""
    try:
        from playwright.sync_api import sync_playwright  # noqa: optional
    except Exception:
        warn("Playwright is not importable; social card PNGs were not rendered.")
        return 0
    from concurrent.futures import ThreadPoolExecutor

    def run(chunk):
        done = 0
        with sync_playwright() as p:
            try:
                b = p.chromium.launch(channel="chrome")
            except Exception:
                b = p.chromium.launch()
            pg = b.new_page(viewport={"width": 1200, "height": 675}, device_scale_factor=1, color_scheme="light")
            for src, dst in chunk:
                pg.goto(src.as_uri(), wait_until="load")
                try:
                    pg.wait_for_function("document.documentElement.dataset.math || document.body.classList.contains('social')", timeout=15000)
                except Exception:
                    warn(f"card {src.name}: mathematics did not finish before capture")
                pg.evaluate("document.fonts.ready.then(() => true)")
                pg.wait_for_timeout(250)
                dst.parent.mkdir(parents=True, exist_ok=True)
                pg.screenshot(path=str(dst), clip={"x": 0, "y": 0, "width": 1200, "height": 675})
                done += 1
            b.close()
        return done

    workers = max(1, min(workers, len(pages)))
    chunks = [pages[i::workers] for i in range(workers)]
    with ThreadPoolExecutor(max_workers=workers) as ex:
        return sum(ex.map(run, chunks))


# --------------------------------------------------------------------- main


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--og", action="store_true", help="render the site-wide social card PNG")
    ap.add_argument("--og-cards", action="store_true", help="render one PNG per Lean statement")
    args = ap.parse_args()
    t0 = time.time()
    og_dir_keep = OUT / "og"
    keep = None
    if og_dir_keep.exists() and not args.og_cards:
        keep = Path(str(OUT) + "-og-keep")
        if keep.exists():
            shutil.rmtree(keep)
        shutil.move(str(og_dir_keep), str(keep))
    if OUT.exists():
        shutil.rmtree(OUT)
    OUT.mkdir(parents=True)
    if keep:
        shutil.move(str(keep), str(OUT / "og"))
    shutil.copytree(ASSETS, OUT / "assets")
    (OUT / ".nojekyll").write_text("")
    (OUT / "cards").mkdir(exist_ok=True)
    recompute_checks()
    og_available = {p.stem for p in (OUT / "og").glob("*.png")} if (OUT / "og").exists() else set()
    if args.og_cards:
        og_available = {s["id"] for s in STATEMENTS}

    md = map_data()
    (OUT / "data").mkdir(parents=True, exist_ok=True)
    (OUT / "data" / "atlas-map.json").write_text(json.dumps(md, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")
    build_home(md)
    for f in FAMILIES:
        build_family(f)
    for m in MANUSCRIPTS:
        build_paper(m)
    for s in STATEMENTS:
        build_statement(s, og_available)
    build_explain()
    build_statements_table()
    build_numbers()
    build_builds_on()
    build_rests_on()
    build_sources()
    build_contribute()
    build_about()
    build_404()
    build_search_index()
    (OUT / "cards" / "site.html").write_text(social_card_html(), encoding="utf-8")
    build_sitemap()

    if args.og or args.og_cards:
        jobs = [(OUT / "cards" / "site.html", ASSETS / "social-card.png")]
        if args.og_cards:
            jobs += [(OUT / "cards" / f"{s['id']}.html", OUT / "og" / f"{s['id']}.png") for s in STATEMENTS]
        n = render_png(jobs)
        if (ASSETS / "social-card.png").exists():
            shutil.copy(ASSETS / "social-card.png", OUT / "assets" / "social-card.png")
        print(f"rendered {n} PNG cards", file=sys.stderr)
        missing = [s_["id"] for s_ in STATEMENTS if args.og_cards and not (OUT / "og" / f"{s_['id']}.png").exists()]
        if missing:
            warn(f"{len(missing)} statement cards were not rendered: {missing[:5]}")

    size = sum(p.stat().st_size for p in OUT.rglob("*") if p.is_file())
    print(json.dumps({
        "pages": STATS["pages"], "indexed": len(PAGES), "seconds": round(time.time() - t0, 1),
        "bytes": size, "math_inline": STATS["math_inline"], "math_display": STATS["math_display"],
        "unknown_text_commands": STATS["tex_unknown_text_command"], "unrenderable_envs": STATS["tex_unrenderable_env"],
        "top_unknown": [(k, v) for k, v in STATS.most_common() if k.startswith(("unknown:", "env:"))][:25],
        "warnings": WARN,
    }, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
