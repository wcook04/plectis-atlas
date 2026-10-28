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

import evidence
import attribution
import reader
import websites

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
COPY_LEAN = json.loads((SITE / "copy_lean.json").read_text(encoding="utf-8"))
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
    _PAPER_ACCEPTANCE = load("paper_acceptance.json").get("papers", [])
    PAPER_READING = {r["id"]: r["status"] for r in _PAPER_ACCEPTANCE
                     if r.get("status") in ("accepted", "partial")}
    # A partial reading page may have no rendered bibliography.
    PAPER_BIBLIOGRAPHY = {r["id"] for r in _PAPER_ACCEPTANCE if r["id"] in PAPER_READING
                         and (r.get("bibliography") or {}).get("entries", 0) > 0}
except (FileNotFoundError, ValueError):
    PAPER_READING = {}
    PAPER_BIBLIOGRAPHY = set()


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


_GLOSSARY_JSON = json.loads((ASSETS / "glossary.json").read_text(encoding="utf-8"))
GLOSSARY = {t_["id"]: t_ for t_ in _GLOSSARY_JSON["terms"]}
GLOSSARY_ORDER = [t_ for t_ in _GLOSSARY_JSON.get("learning_order") or [] if t_ in GLOSSARY]
TERM_RE = re.compile(r"\[\[([a-z0-9-]+)\|([^\]]+)\]\]")


def term_link(tid: str, text_html: str) -> str:
    if tid not in GLOSSARY:
        WARN.append(f"unknown glossary term {tid!r}")
        return text_html
    return f'<a class="term" href="__ROOT__glossary.html#{tid}" data-term="{tid}">{text_html}</a>'




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
             "ell": "ℓ", "partial": "∂", "sqrt": "√", "mid": "|", "colon": ":", "otimes": "⊗", "oplus": "⊕",
             "exists": "∃", "forall": "∀", "notin": "∉", "supset": "⊃", "supseteq": "⊇", "cap": "∩", "cup": "∪",
             "setminus": "∖", "emptyset": "∅", "varnothing": "∅", "circ": "∘", "ast": "∗", "star": "⋆",
             "wedge": "∧", "vee": "∨", "neg": "¬", "nabla": "∇", "hbar": "ℏ", "aleph": "ℵ", "langle": "⟨",
             "rangle": "⟩", "Vert": "‖", "mapsto": "↦", "rightarrow": "→", "leftarrow": "←", "Rightarrow": "⇒",
             "iff": "⟺", "equiv": "≡", "cong": "≅", "simeq": "≃", "ll": "≪", "gg": "≫", "prec": "≺", "perp": "⊥",
             "sum": "∑", "prod": "∏", "int": "∫", "lvert": "|", "rvert": "|", "vert": "|", "lfloor": "⌊",
             "rfloor": "⌋", "lceil": "⌈", "rceil": "⌉", "dagger": "†", "prime": "′", "quad": " ", "qquad": " "}
# Commands that print nothing in a plain title: sizes, spacing and delimiters' sizing.
PLAIN_DROP = {"left", "right", "big", "Big", "bigg", "Bigg", "bigl", "bigr", "Bigl", "Bigr", "biggl", "biggr",
              "displaystyle", "textstyle", "scriptstyle", "limits", "nolimits", "mathop", "mathord", "mathrel",
              "mathbin", "mathopen", "mathclose", "nonumber", "notag", "label", "boldsymbol", "bm", "middle"}
BLACKBOARD = {"R": "ℝ", "Z": "ℤ", "N": "ℕ", "Q": "ℚ", "C": "ℂ", "P": "ℙ", "H": "ℍ", "F": "𝔽", "E": "𝔼",
              "A": "𝔸", "T": "𝕋", "K": "𝕂", "S": "𝕊"}
SUPS = str.maketrans("0123456789+-=()niak/", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾ⁿⁱᵃᵏ\u2044")
# A longer exponent (2^{0.49n}, C^{1,α}) in modifier letters, when every character has one.
SUP_MORE = {**{chr(c): v for c, v in zip(b"0123456789+-=()/", "⁰¹²³⁴⁵⁶⁷⁸⁹⁺⁻⁼⁽⁾\u2044")},
            **dict(zip("abcdefghijklmnoprstuvwxyz", "ᵃᵇᶜᵈᵉᶠᵍʰⁱʲᵏˡᵐⁿᵒᵖʳˢᵗᵘᵛʷˣʸᶻ")),
            **dict(zip("αβγδεθφχ", "ᵅᵝᵞᵟᵋᶿᵠᵡ")), ".": "·", ",": ",", " ": ""}


def _sup(body: str) -> str:
    if re.fullmatch(r"[0-9+\-=()niak/]+", body):
        return body.translate(SUPS)
    if body and all(ch in SUP_MORE for ch in body):
        return "".join(SUP_MORE[ch] for ch in body)
    return "^(" + body + ")"
SUBS = str.maketrans("0123456789+-=()", "₀₁₂₃₄₅₆₇₈₉₊₋₌₍₎")
SUB_LETTERS = dict(zip("aehijklmnoprstuvx", "ₐₑₕᵢⱼₖₗₘₙₒₚᵣₛₜᵤᵥₓ"))
_RELATION = re.compile(r"\s*([≤≥≠<>∈∉⊂⊆⊃⊇≈∼≡≅≃≪≫→←⇒⟺↦=×⊗⊕])\s*")
_OPERATOR_WORD = re.compile(r"(?<=[\w)\]])(?=\\(?:log|exp|sin|cos|tan|det|dim|ker|max|min|sup|inf|lim|gcd|deg|arg)(?![A-Za-z]))")


def _plain_math(t: str) -> str:
    """One formula as plain Unicode text: CAT(0), L₁, c₀, C¹, ℤ³, P ≠ NP."""
    t = re.sub(r"\\mathbb\s*\{?\s*([A-Z])\s*\}?", lambda mm: BLACKBOARD.get(mm.group(1), mm.group(1)), t)
    t = re.sub(r"\\(?:mathsf|mathcal|mathbb|mathrm|mathbf|operatorname\*?|text|mathit|mathfrak|mathscr|mathtt|"
               r"textsf|textbf|textit|texttt|textrm|textup|textnormal|mbox|hbox|emph|boldsymbol|bm)\s*\{([^{}]*)\}", r"\1", t)
    t = re.sub(r"\\(?:mathsf|mathcal|mathbb|mathrm|mathbf)\s+(\w)", r"\1", t)
    t = re.sub(r"\\[dt]?frac\s*\{([^{}]*)\}\s*\{([^{}]*)\}", r"\1/\2", t)
    t = _OPERATOR_WORD.sub(" ", t)
    t = re.sub(r"\\([A-Za-z]+)", lambda mm: GREEK.get(mm.group(1)) or PLAIN_SYM.get(mm.group(1))
               or ("" if mm.group(1) in PLAIN_DROP else mm.group(1)), t)
    t = re.sub(r"\\[,;:!> ]", " ", t)
    t = re.sub(r"\^\{([^{}]*)\}", lambda mm: _sup(mm.group(1)), t)
    t = re.sub(r"\^(\w)", lambda mm: mm.group(1).translate(SUPS), t)
    t = re.sub(r"_\{([^{}]*)\}", lambda mm: mm.group(1).translate(SUBS) if re.fullmatch(r"[0-9+\-=()]+", mm.group(1)) else "_" + mm.group(1), t)
    t = re.sub(r"_(\d)", lambda mm: mm.group(1).translate(SUBS), t)
    t = re.sub(r"_(?:\{([aehijklmnoprstuvx])\}|([aehijklmnoprstuvx]))", lambda mm: SUB_LETTERS[mm.group(1) or mm.group(2)], t)
    t = re.sub(r"_(?=[∞αβγδεπσωℓ])", "", t)
    t = t.replace("{", "").replace("}", "").replace("\\", "")
    t = _RELATION.sub(r" \1 ", t)
    return re.sub(r"\s+", " ", t).strip()


# An apostrophe inside a word, after any letter (Erdős's, Patterson's), is typographic in
# prose. A prime in TeX, a code span, a tag and an identifier keep their straight quote.
_APOS = re.compile(r"(?<=[^\W_])'(?=[^\W\d_])")
_PROSE_SKIP = re.compile(r"(`[^`]*`|<[^>]+>|\]\([^)\s]*\)|\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|(?<!\\)\$[^$]*(?<!\\)\$)", re.S)


def curly_prose(s) -> str:
    """Typographic apostrophes in a name or title from the release, outside formulas,
    tags and code spans."""
    if not s or "'" not in s:
        return s or ""
    return "".join(p if i % 2 else _APOS.sub("\u2019", p) for i, p in enumerate(_PROSE_SKIP.split(s)))


def tex_plain(s: str) -> str:
    """Plain-text rendering of a title or description for <title>, meta tags and search:
    its formulas in Unicode (CAT(0), L₁, c₀, C¹), no dollar signs or backslashes."""
    if not s:
        return ""
    s = re.sub(r"<[^>]+>", "", s)
    s = curly_prose(html.unescape(s))
    math = lambda m: _plain_math(m.group(1))
    s = re.sub(r"\\\((.*?)\\\)", math, s, flags=re.S)
    s = re.sub(r"\\\[(.*?)\\\]", math, s, flags=re.S)
    s = re.sub(r"\$\$(.+?)\$\$", math, s, flags=re.S)
    s = re.sub(r"(?<!\\)\$([^$]+)\$", math, s)
    # A superscript or subscript the source writes outside $...$ ("A C^1 Counterexample").
    s = re.sub(r"(?<=[A-Za-z)])\^\{?([0-9]+)\}?", lambda mm: mm.group(1).translate(SUPS), s)
    s = re.sub(r"(?<=[A-Za-z])_\{?([0-9]+)\}?(?![\w])", lambda mm: mm.group(1).translate(SUBS), s)
    s = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", s)
    s = re.sub(r"\\([%&#_$])", r"\1", s)
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
    s = curly_prose(s)
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
    res = text_dashes("".join(out))
    if link_results:
        res = re.sub(r"\b(results?) (\d{3})\b", lambda m: (f'{m.group(1)} <a href="{root}families/{m.group(2)}.html">{m.group(2)}</a>' if m.group(2) in FAM else m.group(0)), res)
    return res


_MATH_SPAN = re.compile(r"(<[^>]*>|\\\(.*?\\\)|\\\[.*?\\\]|\$\$.*?\$\$|(?<!\\)\$.*?(?<!\\)\$)", re.S)


def text_dashes(h: str) -> str:
    """TeX's text-mode ligatures outside maths: --- an em dash, -- an en dash, as the
    release's TeX means them (Kerr--Newman is Kerr–Newman). Maths is left for KaTeX,
    where -- is two minus signs."""
    parts = _MATH_SPAN.split(h)
    return "".join(p if i % 2 else p.replace("---", "\u2014").replace("--", "\u2013") for i, p in enumerate(parts))


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
# A macro body made only of words: letters, spaces, hyphens and dashes, apostrophes,
# full stops and commas (Kerr--Newman, i.e., et al.). Such a macro is text.
TEXT_MACRO = re.compile(r"^[A-Za-z][A-Za-z \-'.,’]*$")
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
            if bare.isalpha():
                # TeX ends a control word at the first non-letter and drops the spaces after it:
                # R\o rdam is Rørdam, and \ldots and is "…and".
                while j < n and s[j] in " \t":
                    j += 1
            return j
        key = "\\" + bare
        body = self.macros.get(key)
        if body is not None and TEXT_MACRO.match(body) and not re.search(r"#\d", body) \
                and re.search(r"[\s.\-]|[A-Za-z]{4}", body):
            # A paper's own macro that stands for words (\newcommand{\KN}{Kerr--Newman},
            # \newcommand{\ie}{i.e.}) is text, not mathematics: typeset it as the paper
            # prints it, with TeX's text dashes, and let a following control space stand.
            words = body.replace("---", "\N{EM DASH}").replace("--", "\N{EN DASH}")
            out.append(esc(words))
            return j
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
        # A paper's own item labels (label=(G\arabic*)) print as the paper prints them,
        # (G1), (G2), (G3), which the statement's own references then name.
        tpl = list_label_template(opt) if kind == "enumerate" else None
        if tpl:
            n = 0
            for i, (lab, seg) in enumerate(items):
                if lab is None:
                    n += 1
                    items[i] = (re.sub(r"\\(arabic|alph|Alph|roman|Roman)\*", lambda m: _LIST_COUNTERS[m.group(1)](n), tpl), seg)
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


_LIST_COUNTERS = {"arabic": str, "alph": lambda n: chr(96 + n), "Alph": lambda n: chr(64 + n),
                  "roman": lambda n: roman(n), "Roman": lambda n: roman(n).upper()}


def list_label_template(opt: str) -> str | None:
    """The label= key of an enumerate's options ("label=\\textup{(G\\arabic*)},ref=G\\arabic*"),
    braces and all, or None when the options set no counter label."""
    depth, start, parts = 0, 0, []
    for i, ch in enumerate(opt or ""):
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
        elif ch == "," and depth == 0:
            parts.append(opt[start:i])
            start = i + 1
    parts.append((opt or "")[start:])
    for p in parts:
        k, eq, v = p.partition("=")
        if eq and k.strip() == "label":
            v = v.strip()
            if v.startswith("{") and v.endswith("}"):
                v = v[1:-1]
            return v if re.search(r"\\(?:arabic|alph|Alph|roman|Roman)\*", v) else None
    return None


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
    import lean_render

    lines = text.split("\n")
    # Use the same declaration reader as the full-file view: a named argument
    # such as (R := R) is not the start of a proof, and theorem names may be
    # qualified, universe-polymorphic or repeated in different namespaces.
    source = lean_render.LeanFile(text)
    declarations = {d.full: d for d in source.decls if d.kind in ("theorem", "lemma")}
    ranges = []
    for full in theorem_names:
        decl = declarations.get(full)
        if decl is None:
            continue
        idx = decl.line - 1
        end = source.line[decl.body] - 1 if decl.body is not None else decl.end_line - 1
        nxt = end + 1
        while nxt < len(lines) and not lines[nxt].strip():
            nxt += 1
        if nxt < len(lines) and lines[nxt].strip() in ("sorry", "by sorry", "exact sorry"):
            end = nxt
        sig = text[source.start[decl.kw_tok]:source.start[decl.body]] if decl.body is not None else " ".join(lines[idx:end + 1])
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




def glossary_row(t_, prefix=""):
    """One term: its plain definition, then a concrete example from the release."""
    ex = (f'<p class="gloss__ex"><span class="gloss__exk">{esc(C("glossary.example"))}:</span> {esc(t_["example"])}</p>'
          if t_.get("example") else "")
    return (f'<div class="gloss__row" id="{prefix}{esc(t_["id"])}"><dt>{esc(t_["term"])}</dt>'
            f'<dd><p class="gloss__def">{esc(t_["short"])}</p>{ex}</dd></div>')


def build_glossary():
    """The glossary page: first the core terms in the order a newcomer meets them
    (glossary.json learning_order), each with an example; then every term A to Z, grouped
    by first letter. The A to Z rows keep the term ids pages link to; the learning list
    links down to them."""
    rel = "glossary.html"
    terms = sorted(GLOSSARY.values(), key=lambda t_: t_["term"].lower())
    groups = {}
    for t_ in terms:
        groups.setdefault(t_["term"][0].upper(), []).append(t_)
    blocks = "".join(
        f'<section class="gloss__group" aria-labelledby="g-{L}"><h3 class="h3" id="g-{L}">{L}</h3><dl class="gloss">'
        + "".join(glossary_row(t_) for t_ in group)
        + "</dl></section>" for L, group in groups.items())
    letters = "".join(f'<li><a href="#g-{L}">{L}</a></li>' for L in groups)
    start = "".join(
        f'<li class="gstart__i"><a class="gstart__t" href="#{esc(tid)}">{esc(GLOSSARY[tid]["term"])}</a>'
        f'<p class="gstart__d">{esc(GLOSSARY[tid]["short"])}</p>'
        + (f'<p class="gloss__ex"><span class="gloss__exk">{esc(C("glossary.example"))}:</span> {esc(GLOSSARY[tid]["example"])}</p>' if GLOSSARY[tid].get("example") else "")
        + "</li>" for tid in GLOSSARY_ORDER)
    body = f"""<div class="frame page page--wide">
{section_trail("", "glossary")}
<header class="phead">
 <h1 class="phead__title">{esc(C('glossary.title'))}</h1>
 <p class="lede">{esc(C('glossary.lede'))}</p>
</header>
<section class="band band--tight" aria-labelledby="h-gstart"><h2 class="h2" id="h-gstart">{esc(C('glossary.start_heading'))}</h2>
<ol class="gstart">{start}</ol></section>
<section class="band band--tight" aria-labelledby="h-gall"><h2 class="h2" id="h-gall">{esc(C('glossary.all_heading'))}</h2>
<nav class="jump" aria-label="{esc(C('glossary.letters'))}"><ul>{letters}</ul></nav>
<div class="gloss-cols">{blocks}</div></section>
</div>"""
    write_page(rel, page(rel, C("glossary.title"), C("glossary.lede"), body, current="glossary"))


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




def cover_label(cls):
    """An AI draft's scope class (scope_draft.value.class, as the backend normalises it) in the
    words every page uses for it (site/copy_evidence.json, draft_class). The draft judges a
    statement against a theorem of its paper, which is never named as the headline."""
    return evidence.WORDS["draft_class"].get(cls, cls.replace("_", " ").replace("-", " ")) if cls else C("statement.coverage_unclassified")




COVER_RANK = {"headline": 4, "headline-part": 3, "consequence": 2, "weaker": 2, "supporting": 1}
COVER_GRADE = {4: "full", 3: "part", 2: "less", 1: "support"}




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




def fam_has_main(f):
    return any(ST[s]["main_result"] for s in f["statements"] if s in ST)


def RD():
    """Statement Map's reader packets, checked against the export (scripts/reader.py).
    The backend decides every semantic question; the pages render its decisions."""
    import reader
    return reader.load()


SEARCH_TEXT_KEYS = ("family", "in-paper", "in-family", "discipline-n", "found", "found-one", "missing-one", "missing-many",
                    "apart", "failed", "more", "truncated", "kind-family", "kind-lean", "kind-manuscript",
                    "kind-statement", "kind-discipline", "suggest")


def search_data_attrs() -> str:
    """The search dialog's words, for the script that fills it (site/copy.json "search")."""
    return "".join(f' data-{k}="{esc(C("search.js." + k))}"' for k in SEARCH_TEXT_KEYS)


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


def asset_v(name: str) -> str:
    """A short digest of a site asset, for its ?v= query: a redeploy that changes the file
    changes its address, so a cached page never pairs new HTML with an old script."""
    v = _ASSET_V.get(name)
    if v is None:
        path = ASSETS / name
        v = hashlib.sha256(path.read_bytes()).hexdigest()[:10] if path.exists() else ""
        _ASSET_V[name] = v
    return f"{name}?v={v}" if v else name


_ASSET_V: dict = {}


def head(rel: str, title: str, description: str, *, og_block: str | None = None, noindex=False,
         extra_head: str = "", page_type="website", canonical_rel: str | None = None) -> str:
    depth = rel.count("/")
    root = "../" * depth
    # Titles and descriptions are plain text: a formula in one is written in Unicode
    # (CAT(0), L₁), never as TeX, in the tab, the search result and a pasted link's preview.
    title = tex_plain(title)
    description = tex_plain(description)
    crel = canonical_rel or rel
    canonical = BASE_URL + ("" if crel == "index.html" else crel)
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
<link rel="help" type="text/markdown" href="{root}agents.md" title="{esc(C('site.agents_link'))}">
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
<link rel="apple-touch-icon" href="{root}assets/apple-touch-icon.png">
<link rel="preload" href="{root}assets/fonts/plectis-serif.woff2" as="font" type="font/woff2" crossorigin>
<link rel="preload" href="{root}assets/fonts/plectis-sans.woff2" as="font" type="font/woff2" crossorigin>
<link rel="stylesheet" href="{root}{KATEX_DIR}/katex.min.css">
<link rel="stylesheet" href="{root}assets/{asset_v('atlas.css')}">
<link rel="stylesheet" href="{root}assets/{asset_v('websites/family.css')}">
<script>(function(){{var d=document.documentElement;d.classList.add('js');try{{var t=localStorage.getItem('atlas-theme');if(t==='dark'||t==='light')d.setAttribute('data-theme',t);}}catch(e){{}}}})();</script>
<script defer src="{root}{KATEX_DIR}/katex.min.js"></script>
<script defer src="{root}{KATEX_DIR}/contrib/auto-render.min.js"></script>
<script defer src="{root}assets/{asset_v('atlas.js')}"></script>
{extra_head}
</head>"""


# The front door is the release universe (scripts/build_universe.py writes index.html).
# Numbers lives in the footer and in the home page's bands.
NAV = [("index.html", "map"), ("explain.html", "explain"), ("statements.html", "statements"),
       ("sources.html", "sources"), ("glossary.html", "glossary"),
       ("about.html", "about")]
# Every section page, including those the header nav leaves to the footer (Contribute left the
# header on 19 October 2026: Atlas collects from public sources and asks readers for nothing).
SECTIONS = NAV + [("contribute.html", "contribute")]


def header(rel: str, current: str | None) -> str:
    root = "../" * rel.count("/")
    links = []
    # A page inside a family (family, Lean statement, paper, explanation) sits under the
    # map in the breadcrumb, so the nav marks Map as its section (aria-current="true").
    inside = current is None and rel.split("/")[0] in ("families", "statements", "papers", "explanations")
    for href, key in NAV:
        cur = ' aria-current="page"' if key == current else (' aria-current="true"' if inside and key == "map" else "")
        links.append(f'<a href="{root}{href}"{cur}>{esc(C("nav." + key))}</a>')
    # The wordmark is the ladder's second rung: "Will Cook / Plectis Atlas", the first rung
    # his home page, which lists every one of his websites and films (scripts/websites.py).
    ladder = websites.ladder(f'<a class="brand" href="{root}index.html" aria-label="{esc(C("nav.brand_label"))}">'
                             f'{MARK_SVG}<span class="brand__name" translate="no">{esc(C("site.name"))}</span></a>')
    return f"""<body data-root="{root}" data-generation="{esc(RD().generation)}" data-copied="{esc(C('words.copied'))}" data-copy-failed="{esc(C('words.copy_failed'))}" data-tex-failed="{esc(C('words.tex_failed'))}" data-example-word="{esc(C('glossary.example'))}">
<a class="skip" href="#main">{esc(C('site.skip'))}</a>
<header class="top">
 <div class="frame top__in">
  {ladder}
  <nav class="nav" id="site-nav" aria-label="{esc(C('nav.site_nav'))}">{''.join(links)}</nav>
  <div class="top__tools">
   <button class="nav-toggle" type="button" aria-expanded="false" aria-controls="site-nav"><svg viewBox="0 0 20 20" aria-hidden="true"><path d="M3 6h14M3 10h14M3 14h14"/></svg><span>{esc(C('nav.menu'))}</span></button>
   <a class="search-open" href="{root}explain.html" aria-label="{esc(C('nav.search'))}" aria-haspopup="dialog" aria-controls="search-dialog"><svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M12.6 12.6 17 17"/></svg><span class="search-open__label">{esc(C('nav.search'))}</span><kbd aria-hidden="true">/</kbd></a>
   <button class="help-open" type="button" aria-label="{esc(C('nav.help'))}" title="{esc(C('nav.help'))}" aria-haspopup="dialog" aria-controls="help-dialog"><span aria-hidden="true">?</span></button>
   <button class="theme-toggle" type="button" data-label-dark="{esc(C('nav.theme_dark'))}" data-label-light="{esc(C('nav.theme_light'))}" aria-label="{esc(C('nav.theme_dark'))}"><span class="theme-toggle__thumb" aria-hidden="true"></span></button>
  </div>
 </div>
</header>
<dialog class="search" id="search-dialog" aria-labelledby="search-title"{search_data_attrs()}>
 <form class="search__form" role="search">
  <label class="search__label" id="search-title" for="search-q">{esc(C('search.title'))}</label>
  <div class="search__bar">
   <svg viewBox="0 0 20 20" aria-hidden="true"><circle cx="8.5" cy="8.5" r="5.5"/><path d="M12.6 12.6 17 17"/></svg>
   <input class="search__input" id="search-q" type="search" autocomplete="off" spellcheck="false" placeholder="{esc(C('search.placeholder'))}" role="combobox" aria-expanded="true" aria-controls="search-results" aria-autocomplete="list" aria-describedby="search-help">
   <button class="search__close" type="button">{esc(C('search.close'))}</button>
  </div>
  <p class="search__help" id="search-help">{esc(C('search.help'))}</p>
 </form>
 <p class="search__status" role="status" aria-live="polite"></p>
 <div class="search__results" id="search-results" role="listbox" aria-label="{esc(C('search.results_label'))}"></div>
 <p class="search__keys">{C('search.keys')}</p>
</dialog>
{help_dialog(root)}"""


def help_steps_html(prefix: str = "help-", lead: bool = False) -> str:
    """The guide's numbered steps, shared by the help dialog, help.html and the 404 page;
    lead sets them as the guide's main card. Each step carries an id, so
    data-help="<step>" opens the guide at it."""
    cls = "help__steps help__steps--ex" if lead else "help__steps"
    return f'<ol class="{cls}">' + "".join(
        f'<li id="{prefix}{esc(sid)}"><span class="help__step">{text}</span></li>' for sid, text in COPY["help"]["steps"]) + "</ol>"


def help_terms_html(root: str) -> str:
    return '<dl class="help__terms">' + "".join(
        f'<div class="help__term"><dt><a href="{root}glossary.html#{esc(tid)}">{esc(label)}</a></dt><dd>{esc(text)}</dd></div>'
        for tid, label, text in COPY["help"]["terms"]) + "</dl>"


def help_more_html(root: str, page_link=True) -> str:
    links = [f'<a href="{root}glossary.html">{esc(C("help.glossary_link"))}</a>']
    if page_link:
        links.append(f'<a href="{root}help.html">{esc(C("help.page_link"))}</a>')
    return '<p class="help__more">' + "".join(links) + "</p>"


def help_guide_html(root: str, h: str = "h3", prefix: str = "help-", page_link=True) -> str:
    """The guide: four steps to read any result, a link to try them on family 017, and
    beside them the few words every page uses, each linked to its glossary entry."""
    hc = "help__h" if h == "h3" else "h2"
    return f"""<div class="help__cols">
  <section class="help__example" aria-labelledby="{prefix}steps-h"><{h} class="{hc}" id="{prefix}steps-h">{esc(C('help.steps_heading'))}</{h}>{help_steps_html(prefix, lead=True)}
   <p class="help__more"><a class="btn btn--primary btn--small" href="{root}families/017.html">{esc(C('help.example_open'))}</a></p></section>
  <section class="help__words help__words--side" aria-labelledby="{prefix}terms-h"><{h} class="{hc}" id="{prefix}terms-h">{esc(C('help.terms_heading'))}</{h}>{help_terms_html(root)}
   {help_more_html(root, page_link)}</section>
 </div>"""


def help_dialog(root: str) -> str:
    """The how-to-use guide behind the header's ? button: rendered on every page, so it
    reads without scripts in the page source; atlas.js only opens and closes it (also from
    the ? key, ?help=1 in the address, and any element with data-help)."""
    return f"""<dialog class="dlg help" id="help-dialog" aria-labelledby="help-title">
 <div class="help__head">
  <h2 class="help__title" id="help-title">{esc(C('help.title'))}</h2>
  <button class="search__close help__close" type="button">{esc(C('help.close'))}</button>
 </div>
 <div class="help__body">
  <p class="help__what">{esc(C('help.what'))}</p>
  {help_guide_html(root)}
  <p class="help__limit">{esc(C('help.limit'))}</p>
 </div>
 <p class="search__keys">{C('help.keys')}</p>
</dialog>"""


def build_help():
    """help.html: the same guide as a page, for readers without scripts and for links. The
    Atlas walkthrough film stands beside its opening (scripts/websites.py), its still beside
    its title so the steps and their example stay on the first screen; the dialog behind
    the header's ? keeps to the steps."""
    rel = "help.html"
    film = websites.film_slot(websites.film(), size="inline",
                              sizes="(min-width: 1100px) 16rem, (max-width: 30rem) 7rem, 11rem")
    body = f"""<div class="frame page page--wide page--help">
{trail("", [(esc(C("help.title")), None)])}
<header class="phead phead--film"><h1 class="phead__title">{esc(C('help.title'))}</h1><p class="lede">{esc(C('help.what'))}</p>
<p class="phead__facts">{esc(C('help.page_lede'))}</p>{film}</header>
{help_guide_html("", "h2", "step-", page_link=False)}
<p class="help__limit">{esc(C('help.limit'))}</p>
</div>"""
    write_page(rel, page(rel, C("help.title"), C("help.page_description"), body, current="help"))


def footer(rel: str) -> str:
    root = "../" * rel.count("/")
    up = CFG["upstream_repo"]
    return f"""<footer class="foot">
 <div class="frame foot__in">
  <div class="foot__lead">
   <p class="foot__name">{MARK_SVG}<span translate="no">{esc(C('site.name'))}</span></p>
   <p>{esc(C('site.independence', author=CFG['author']))}</p>
   <p class="foot__family">{esc(C('site.family_lead'))} <a class="ext" href="{esc(CFG['author_url'])}" rel="noopener">{esc(C('site.family_link'))}</a></p>
   <p>{esc(C('site.licence', upstream='openai/math', commit_short=COMMIT_SHORT))}</p>
  </div>
  <nav class="foot__nav" aria-label="{esc(C('site.foot_nav'))}">
   <div class="foot__col"><h2 class="foot__h">{esc(C('site.foot_atlas'))}</h2><ul class="foot__links">
    <li><a href="{root}about.html">{esc(C('nav.about'))}</a></li>
    <li><a href="{root}numbers.html">{esc(C('nav.numbers'))}</a></li>
    <li><a href="{root}contribute.html">{esc(C('nav.contribute'))}</a></li>
    <li><a href="{root}glossary.html">{esc(C('nav.glossary'))}</a></li>
   </ul></div>
   <div class="foot__col"><h2 class="foot__h">{esc(C('site.foot_lists'))}</h2><ul class="foot__links">
    <li><a href="{root}citations-within.html">{esc(C('citations_within.title'))}</a></li>
    <li><a href="{root}references-outside.html">{esc(C('references_outside.title'))}</a></li>
    <li><a href="{root}sources.html#software">{esc(C("site.notices_link"))}</a></li>
   </ul></div>
   <div class="foot__col"><h2 class="foot__h">{esc(C('site.foot_source'))}</h2><ul class="foot__links">
    <li><a class="ext" href="{esc(REPO)}" rel="noopener">{esc(C('site.repo_link'))}</a></li>
    <li><a class="ext" href="{esc(up)}/tree/{COMMIT}" rel="noopener">{esc(C('site.upstream_link'))}</a></li>
    <li><a href="{root}agents.md">{esc(C('site.agents_link'))}</a></li>
   </ul></div>
  </nav>
  {websites.sister_sites()}
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
         page_type="website", main_class="", canonical_rel=None):
    h = head(rel, title, description, og_block=og_block, noindex=noindex, extra_head=extra_head, page_type=page_type,
             canonical_rel=canonical_rel)
    return f'{h}\n{header(rel, current)}\n<main id="main" class="{main_class}" tabindex="-1">\n{body}\n</main>\n{footer(rel)}'


# The one breadcrumb grammar for every page below the front door (DESIGN.md, "The shell
# and the general pages"): Map / <Subject> / Family <N>: <title> / <this page>, and on a
# list or general page Map / <Section> [/ <this page>]. It is an ordered list inside a
# labelled nav landmark; every crumb is a link except the page itself, which carries
# aria-current="page"; the slashes are hidden from screen readers. A separator goes with
# the step after it (a word joiner glues them), so a phone never shows a "/" alone at the
# end of a line. TRAIL_SEP stays for builders that still write their own crumbs.
TRAIL_SEP = ' <span class="trail__sep" aria-hidden="true">/</span>\u2060'


def trail(root, items):
    """items: (label_html, href) pairs after Map; href None marks the current page."""
    crumbs = [(esc(C("nav.trail_home")), f"{root}index.html")] + list(items)
    lis = []
    for i, (label, href) in enumerate(crumbs):
        sep = '<span class="trail__sep" aria-hidden="true">/</span>\u2060' if i else ""
        inner = f'<a href="{href}">{label}</a>' if href else f'<span class="trail__cur" aria-current="page">{label}</span>'
        lis.append(f'<li class="trail__i">{sep}{inner}</li>')
    return ('<nav class="trail" aria-label="' + esc(C("nav.breadcrumb")) + '"><ol class="trail__list">'
            + "".join(lis) + "</ol></nav>")


def family_crumb_html(f) -> str:
    """A family as a crumb: "Family 017: The irrationality exponent of π is 2"."""
    return esc(C("nav.trail_family", num=f["id"])) + ": " + fam_title_html(f)


def family_crumbs(f, root, current=False):
    """The crumbs from the map down to a family: its subject (the map opened on that
    subject), then "Family N: short title", a link unless the family page is the current
    page. A long title is cut at a word with the whole title in its tooltip."""
    di = DISC_OF.get(f["id"])
    items = []
    if di is not None:
        items.append((esc(DISCIPLINES[di]["name"]), f'{root}index.html#o=d%3A{DISC_SLUG[di]}'))
    title = crumb_title(fam_title_html(f), tex_plain(f["title"]))
    items.append((esc(C("nav.trail_family", num=f["id"])) + ": " + title,
                  None if current else f'{root}families/{f["id"]}.html'))
    return items


def family_trail(f, root, here_html=None):
    """The trail of a family page (here_html None) or of a page inside a family (a Lean
    statement, a paper, an explanation), whose own name here_html ends the trail."""
    items = family_crumbs(f, root, current=here_html is None)
    if here_html is not None:
        items.append((here_html, None))
    return trail(root, items)


def section_trail(root, key, *here):
    """The trail of a list or general page: Map / <Section> for the section's own page,
    Map / <Section> / <this page> for a page that belongs to a section (its nav item is
    then the current one). key names a NAV entry; here is this page's own name, plain."""
    href = dict((k, h) for h, k in SECTIONS)[key]
    sec = esc(COPY["nav"]["crumb"].get(key) or C("nav." + key))
    if not here:
        return trail(root, [(sec, None)])
    return trail(root, [(sec, f"{root}{href}")] + [(esc(h), None) for h in here])


# Lateral navigation. The breadcrumb climbs (map, field, family); this row moves sideways
# to the neighbouring family in the same field, the neighbouring Lean statement in the same
# family, or the neighbouring paper in the same family, in the order the parent page lists
# them. Each neighbour is a list of (href, title_html, title_plain).

def family_siblings(fid: str, root: str):
    """The families of fid's field in the field's order, and fid's place among them."""
    di = DISC_OF.get(fid)
    if di is None:
        return None
    ids = [x for x in DISCIPLINES[di]["families"] if x in FAM]
    if fid not in ids:
        return None
    items = [(f"{root}families/{x}.html", fam_title_html(FAM[x]), tex_plain(FAM[x]["title"])) for x in ids]
    return items, ids.index(fid), DISCIPLINES[di]["name"]


def lean_siblings(sid: str, root: str):
    """The Lean statements of sid's family in the family page's order (the selected one
    first, then the backend's order), and sid's place among them."""
    _fid, doc, _rec = lean_family_doc(sid)
    if not doc:
        return None
    leans = [l["id"][2:] for l in doc.get("lean") or []]
    sel = ((doc.get("selection") or {}).get("lean") or "")[2:]
    leans.sort(key=lambda x: x != sel)
    ids = [x for x in leans if x in ST]
    if sid not in ids:
        return None
    items = []
    for x in ids:
        label = curly_prose((ST[x].get("labels") or [x])[0])
        items.append((f"{root}statements/{quote(x)}.html", f'<span class="md-math">{esc(label)}</span>', tex_plain(label)))
    return items, ids.index(sid)


class Siblings(tuple):
    """(items, index), as every sibling finder returns, with the words for this page's
    place when the plain count needs qualifying (papers counted with withdrawn papers
    and earlier editions say so)."""
    position = None


def paper_siblings(slug: str, root: str):
    """The papers of slug's family in the family page's order (current papers, previous
    editions, then papers withdrawn since release day), and slug's place among them."""
    m = MS.get(slug)
    fid = (m or {}).get("family")
    if not fid or fid not in FAM:
        return None
    hist = RD().family(fid).get("paper_history") or []
    ids = [h["id"][2:] for h in hist if h.get("status") == "current"]
    ids += [h["id"][2:] for h in hist if h.get("status") == "previous-edition"]
    ids += [x["id"] for x in MANUSCRIPTS if x["status"] == "withdrawn" and x.get("family") == fid]
    ids = [x for x in dict.fromkeys(ids) if x in MS]
    if slug not in ids:
        return None
    items = []
    for x in ids:
        mx = MS[x]
        # An earlier edition usually shares its title with the current one; say which it is.
        st = "" if mx["status"] == "current" else status_label(mx["status"]).lower()
        items.append((f"{root}papers/{quote(x)}.html",
                      ms_title_html(mx) + (f' <span class="sib__st">({esc(st)})</span>' if st else ""),
                      tex_plain(mx["title"]) + (f" ({st})" if st else "")))
    found = Siblings((items, ids.index(slug)))
    nw = sum(1 for x in ids if MS[x]["status"] == "withdrawn")
    ne = sum(1 for x in ids if MS[x]["status"] not in ("current", "withdrawn"))
    what = ([C("siblings.withdrawn_1") if nw == 1 else C("siblings.withdrawn_n", k=nw)] if nw else []) + \
           ([C("siblings.editions_1") if ne == 1 else C("siblings.editions_n", k=ne)] if ne else [])
    if what:
        found.position = C("siblings.paper_including", n=ids.index(slug) + 1, total=len(ids),
                           what=C("siblings.and_join").join(what))
    return found


def sibling_nav(kind: str, found, **kw) -> str:
    """The previous and next row: the neighbours' names as links (rel=prev, rel=next) and
    this page's place in the list between them. Nothing when the page has no neighbour;
    at either end only the direction that exists."""
    if not found:
        return ""
    items, i = found[0], found[1]
    if len(items) < 2:
        return ""

    def link(j, side):
        href, title_html, title_plain = items[j]
        arrow = "←" if side == "prev" else "→"
        arr = f'<span class="sib__arr" aria-hidden="true">{arrow}</span>'
        t = f'<span class="sib__t">{title_html}</span>'
        return (f'<a class="sib__a sib__a--{side}" rel="{side}" href="{esc(href)}" '
                f'aria-label="{esc(C("siblings." + kind + "_" + side, title=title_plain, **kw))}">'
                + (arr + t if side == "prev" else t + arr) + "</a>")

    prev_ = link(i - 1, "prev") if i > 0 else '<span class="sib__a sib__a--prev" aria-hidden="true"></span>'
    next_ = link(i + 1, "next") if i + 1 < len(items) else '<span class="sib__a sib__a--next" aria-hidden="true"></span>'
    pos_words = getattr(found, "position", None) or C("siblings." + kind + "_position", n=i + 1, total=len(items), **kw)
    pos = f'<p class="sib__pos">{esc(pos_words)}</p>'
    return (f'<nav class="sib" aria-label="{esc(C("siblings." + kind + "_label", **kw))}">'
            f'{pos}{prev_}{next_}</nav>')


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


# A drawing in a statement's TeX (TikZ, xy, picture) is not typeset in the browser; the
# statement says where it is instead. scripts/family_page.py can import these.
DIAGRAM = re.compile(r"\\begin\{(tikzpicture|tikzcd|xy|picture)\}.*?\\end\{\1\}", re.S)
_DIAGRAM_MARK = "ZZATLASDIAGRAMZZ"


def statement_blocks(conv: TexConv, text: str, href: str | None = None) -> str:
    """A statement's TeX as HTML, with each diagram replaced by one line that says the
    diagram is drawn in the paper (linked to the passage when there is a reading page)."""
    body = conv.blocks(DIAGRAM.sub(f" {_DIAGRAM_MARK} ", text or ""))
    if _DIAGRAM_MARK not in body:
        return body
    note = (C("words.diagram_link", href=esc(href)) if href else esc(C("words.diagram")))
    body = re.sub(r'<div class="m-d">\s*<span class="m"[^>]*>\s*' + _DIAGRAM_MARK + r'\s*</span>\s*</div>|<span class="m"[^>]*>\s*'
                  + _DIAGRAM_MARK + r'\s*</span>', _DIAGRAM_MARK, body)
    return re.sub(r"(?:<p>)?\s*" + _DIAGRAM_MARK + r"\s*(?:</p>)?", f'<span class="stmt__diagram">{note}</span>', body)


def render_paper_statement(m, st, root, conv: TexConv, anchor_prefix="st"):
    body = statement_blocks(conv, st["text"], paper_statement_href(m["id"], st, root))
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
    targets = stmt["comparator"]["theorem_names"] or stmt["theorems"][:1]
    if targets:
        ranges = lean_key_ranges(text, targets)
    else:
        # A definition-only configuration still has a statement to read. Use
        # its exact indexed declaration rather than leaving every snippet blank.
        spans, _ = decl_spans(stmt)
        ranges = sorted({spans[name] for name in stmt["comparator"].get("definition_names", []) if name in spans})
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
    body = f"""<div class="frame page page--wide">
{family_trail(f, root, f'<span class="md-math">{esc(title)}</span>')}
<header class="phead">
 <p class="phead__kicker">{esc(C('explanation.kicker', id=fid))}</p>
 <h1 class="phead__title md-math">{esc(title)}</h1>
 <p class="phead__facts">{esc(C('explanation.reviewed_note'))}</p>
</header>
<div class="rd">
<article class="rd__main explain-body prose md-math" data-macros="">{body_html}</article>
<aside class="rd__side"><div class="panel">{explanation_meta_html(e, fid, root)}
<p class="actions"><a class="btn btn--ghost" href="{root}families/{fid}.html">{esc(C('explanation.back', id=fid))}</a><a class="btn btn--quiet ext" href="{esc(suggest)}" rel="noopener">{esc(C('words.suggest_change'))}</a></p></div></aside>
</div>
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


def camel_breaks(name: str) -> str:
    """An escaped identifier or file name that may break on a phone only between its
    capitalised words or before its extension: CharacterVarieties<wbr>AllSeams..."""
    return re.sub(r"(?<=[a-z0-9])(?=[A-Z])|(?=\.lean$)", "<wbr>", esc(name))


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
    return "".join(p if p.startswith("`") else _APOS.sub("\u2019", p) for p in parts)


def say(n: int) -> str:
    """A small count as a word a person would say aloud; larger counts as figures."""
    words = C("family.numbers")
    return words[n] if 0 <= n < len(words) else num(n)






def credit_link(source_id, root) -> str:
    """A credited source by the name of the people behind it, linked to its row on the sources page."""
    return f'<a href="{root}sources.html#src-{esc(source_id)}">{esc(source_credit(source_id))}</a>'








GLYPH_RUN = {"ok": '<svg class="glyph glyph--ok" viewBox="0 0 12 12" aria-hidden="true"><path d="M2.2 6.4 4.9 9 9.8 3.2"/></svg>',
             "open": '<svg class="glyph glyph--open" viewBox="0 0 12 12" aria-hidden="true"><circle cx="6" cy="6" r="3.6"/></svg>'}






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




def build_paper(m):
    slug = m["id"]
    rel = f"papers/{slug}.html"
    root = "../"
    fam = FAM.get(m.get("family") or "")
    title_plain = tex_plain(m["title"])
    items = []
    if fam:
        di = DISC_OF[fam["id"]]
        tr = family_trail(fam, root, ms_title_html(m))
        tr += sibling_nav("paper", paper_siblings(slug, root))
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
    abstract = ""
    if (m.get("abstract") or "").strip():
        abstract = f'<section class="band band--tight"><h2 class="h2">{esc(C("paper.abstract"))}</h2><div class="prose tex-auto">{rich(m["abstract"])}</div></section>'
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
{abstract}
{stm}
</div>
{macros_script([slug])}"""
    desc = tex_plain(m.get("abstract") or m["title"])
    # An earlier edition or a withdrawn paper shares its title with the current edition:
    # its tab names its status and date, and search engines are pointed at the current one.
    page_title, canonical_rel = title_plain, None
    if m["status"] != "current":
        st_word = status_label(m["status"]).lower()
        dated = date_words(m.get("date"))
        page_title = (C("paper.title_status", title=title_plain, status=st_word, date=dated) if dated
                      else C("paper.title_status_undated", title=title_plain, status=st_word))
        cur = MS.get(m.get("superseded_by") or "")
        if m["status"] == "previous-edition" and cur and cur.get("status") == "current":
            canonical_rel = f"papers/{cur['id']}.html"
    write_page(rel, page(rel, page_title, desc, body, page_type="article", canonical_rel=canonical_rel),
               index=(m["status"] == "current"))


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


def receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html, pinfo, lrec, *, standalone=False):
    """The shareable comparison card: the paired paper theorem beside the Lean statement,
    with the pairing state and the re-run record from the backend."""
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    label = (stmt.get("labels") or [stmt["id"]])[0]
    vtext = vocab_text(stmt)
    state = pairing_kind(pinfo)
    # A reading or a word match that links several paper statements names the others too.
    also = ""
    if paper_st and len(pinfo.get("targets") or []) > 1:
        doc_ = lean_family_doc(stmt["id"])[1]
        others = []
        for t in pinfo["targets"][1:] if doc_ else []:
            _m, st_, rec_ = ms_statement(doc_, t)
            others.append(backend_printed(rec_, st_))
        if others:
            also = f'<p class="rc__loc">{esc(LW("card.also_linked", which=", ".join(others)))}</p>'
    if paper_st:
        kind = esc(paper_st["display"]) + (f' <span class="rc__sttitle">({conv.text(paper_st["title"], inline=True)})</span>' if paper_st.get("title") else "")
        paper_body = statement_blocks(conv, paper_st["text"])
        loc = C("statement.card_locator", label=paper_st["label"], file=paper_st["file"], line=paper_st["line"]) if paper_st.get("label") else C("statement.card_locator_nolabel", file=paper_st["file"], line=paper_st["line"])
        paper_src = f'<p class="rc__src"><span class="tex-auto">{rich(paper_ms["title"])}</span></p><p class="rc__loc">{esc(loc)}</p>{also}'
        paper_label = cap(evidence.say("pairing_short." + state))
    else:
        kind = ""
        if pinfo.get("readings"):
            rd = pinfo["readings"][0]
            why_ = reading_limits(pinfo.get("reason") or rd.get("limitations") or "")
            paper_body = (f'<p class="rc__none">{esc(READING_WORDS["unresolved"].format(author=rd.get("author") or READING_WORDS["someone"]))}</p>'
                          + (f'<p class="rc__none">“{esc(curly_prose(why_))}”</p>' if why_ else ""))
        else:
            paper_body = f'<p class="rc__none">{esc(pinfo.get("reason") or evidence.say("pairing.unavailable"))}</p>'
        paper_src = ""
        paper_label = C("statement.card_paper_none")
    snippet = lean_snippet_html(stmt, lines_html, max_lines=18)
    axioms = ", ".join(stmt["comparator"]["permitted_axioms"]) or C("statements.none")
    note = C("statement.sorry_note_axiom") if stmt["declares_axiom"] else C("statement.sorry_note")
    hl = stmt["comparator"].get("definition_names") or []
    hole_note = ""
    if hl:
        if not stmt["comparator"]["theorem_names"]:
            note = ""
        hole_note = C("statement.card_holes_one", name=hl[0].split(".")[-1]) if len(hl) == 1 else C("statement.card_holes_many", n=len(hl), name=hl[0].split(".")[-1])
        hole_note = f'<p class="rc__note rc__note--hole">{ctext(hole_note)}</p>'
    review, _replay = review_records(stmt["id"])
    acc = len((lrec or {}).get("accepted_current_sources") or [])
    reruns = (evidence.say("reruns.none") if not acc else LW("card.reruns_one") if acc == 1 else LW("card.reruns_many", n=say(acc)))
    shown_url = page_url.replace("https://", "")
    return f"""<div class="rc-wrap{' rc-wrap--solo' if standalone else ''}"><article class="rc" data-macros="{esc(paper_ms['id']) if paper_ms else ''}" aria-label="{esc(C('statement.card_heading'))}">
 <header class="rc__head">
  <p class="rc__brand">{MARK_SVG}<span translate="no">{esc(C('site.name'))}</span></p>
  <h2 class="rc__title md-math">{esc(label)}</h2>
  <p class="rc__fam">{esc(LW('card.family', id=fam['id'] if fam else ''))} <span class="tex-auto">{rich(fam['title']) if fam else ''}</span></p>
 </header>
 <div class="rc__cols">
  <section class="rc__paper"><p class="rc__label">{esc(paper_label)}</p><p class="rc__kind">{kind}</p><div class="rc__fit"><div class="rc__body">{paper_body}</div></div>{paper_src}</section>
  <section class="rc__lean"><p class="rc__label">{esc(C('statement.card_lean'))}</p><div class="rc__fit"><pre class="lean lean--card"><code>{snippet}</code></pre></div>{('<p class="rc__note">' + ctext(note) + '</p>') if note else ''}{hole_note}</section>
 </div>
 <footer class="rc__foot">
  <p class="rc__status"><span class="rc__fact">{esc(evidence.say('pairing.' + state))}</span><span class="rc__fact"><strong>{esc(reruns)}</strong></span><span class="rc__fact"><strong>{esc(review)}</strong></span></p>
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


def definitions_html(stmt, lines_html, cap=24, shown=()):
    """The local definitions the checked statement reaches, each with its source lines.
    A definition whose lines the Lean block above already shows (shown: 0-based inclusive
    line ranges, such as the definition a theorem's type names) is not repeated."""
    names, spans, lines, vocab = needed_definitions(stmt, cap)
    names = [n_ for n_ in names if not any(a <= spans[n_][0] and spans[n_][1] <= b for a, b in shown)]
    if not names:
        return ""
    items = []
    for full in names[:cap]:
        a, b = spans[full]
        h = a
        while h < b and ":=" not in lines[h] and not lines[h].rstrip().endswith(" where") and h - a < 3:
            h += 1
        # A declaration of up to ten lines is shown whole; a longer one shows its head
        # and folds the rest, which starts after the head so no line is repeated.
        if b - a + 1 <= 10:
            h = b
        head = "".join(f'<span class="ln" data-n="{i + 1}">{lines_html[i]}</span>' for i in range(a, h + 1))
        more = ""
        if b > h:
            bodyl = "".join(f'<span class="ln" data-n="{i + 1}">{lines_html[i]}</span>' for i in range(h + 1, b + 1))
            rest = b - h
            more = (f'<details class="decl__more"><summary>{esc(LW("defs.show_rest.one") if rest == 1 else LW("defs.show_rest.many", n=rest))}</summary>'
                    f'<pre class="lean lean--snippet lean--cont"><code>{bodyl}</code></pre></details>')
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
    acceptance_key = ("statement.comparator_box_definition_only"
                      if holes and not stmt["comparator"]["theorem_names"]
                      else "statement.comparator_box_does")
    axioms = ", ".join(f"<code>{esc(a)}</code>" for a in stmt["comparator"]["permitted_axioms"]) or esc(C("statements.none"))
    return (f'<div class="note"><p class="note__h">{esc(C("statement.comparator_box_heading"))}</p>'
            f'<p>{ctext(C(acceptance_key))}</p><p>{holes_p}</p>'
            f'<p>{esc(C("statement.comparator_box_axioms"))} {axioms}</p>'
            f'<p>{ctext(C("statement.comparator_box_not"))}</p></div>')


# --------------------------------------------- Lean pages: the backend's decisions
#
# Statement Map (scripts/reader.py) decides which paper theorem a Lean statement is
# paired with, by what evidence, who re-ran it and what each outside reader found.
# These helpers only find that record and say it in words.

PAIRED_STATES = ("candidate-pairing", "producer-cited-association", "producer-declared-binding")


def cap(s: str) -> str:
    """Capitalise the first letter only ("cited in the Lean source")."""
    return s[:1].upper() + s[1:]


def prose_credit(name: str) -> str:
    """A credited name as prose says it: "Carlos Toledo, cert-machine" is
    "Carlos Toledo’s cert-machine"; "MathVet" stays "MathVet"."""
    return "’s ".join(name.split(", ", 1)) if ", " in name else name


def LW(key: str, **kw) -> str:
    """A string from site/copy_lean.json by dotted key (the Lean page's own words)."""
    node = COPY_LEAN
    for part in key.split("."):
        node = node[part]
    return node.format(**kw) if kw else node


def lean_family_doc(lid: str):
    """(family id, family reader packet, the Lean record in it) for a Lean statement,
    from the first family the backend lists it under."""
    r = RD()
    summ = r.lean_summary(lid)
    if not summ or not summ.get("family_ids"):
        return None, None, None
    fid = summ["family_ids"][0]
    doc = r.family(fid)
    rec = next((l for l in doc.get("lean") or [] if l["id"] == ("l:" + lid if not lid.startswith("l:") else lid)), None)
    return fid, doc, rec


def backend_pairing(doc: dict, lid: str) -> dict:
    """The backend's pairing for one Lean statement of a family, as recorded:

    1. the family's selection, when it names this Lean statement;
    2. otherwise a producer-cited or producer-declared correspondence for it, when the
       backend records exactly one target;
    3. otherwise a source association the backend resolved to one local statement
       (WEB.md: a uniquely cited local target takes precedence over a lexical candidate;
       several or unresolved targets abstain);
    4. otherwise the lexical pairing selection, with its abstention reason.

    Returns {state, target, reason, alternatives, method, association, record}. Nothing
    here scores or compares statements; every field is the backend's."""
    lid = lid if lid.startswith("l:") else "l:" + lid
    sel = doc.get("selection") or {}
    ps = next((p for p in doc.get("pairing_selections") or [] if p.get("source") == lid), None)
    alts = list((ps or {}).get("alternatives") or [])
    assoc = [a for a in doc.get("source_associations") or [] if a.get("source_id") == lid]
    out = {"state": "unavailable", "target": None, "reason": None, "alternatives": alts,
           "method": (ps or {}).get("method"), "association": assoc[0] if len(assoc) == 1 else None, "record": ps}
    if sel.get("lean") == lid:
        out.update(state=sel.get("pairing_state") or "unavailable", target=sel.get("paired_statement"))
        if out["state"] == "unavailable":
            out["reason"] = (ps or {}).get("abstention_reason")
        return out
    strong = {(c["state"], c.get("target")) for c in doc.get("correspondences") or []
              if c.get("source") == lid and c.get("state") in ("producer-cited-association", "producer-declared-binding")}
    if len(strong) == 1:
        st, tg = next(iter(strong))
        out.update(state=st, target=tg)
        return out
    if assoc:
        targets = {t for a in assoc for t in (a.get("local_statement_ids") or [])}
        if all(a.get("state") == "unique" for a in assoc) and len(targets) == 1:
            out.update(state="producer-cited-association", target=next(iter(targets)))
        else:
            out["reason"] = LW("pairing.assoc_unresolved")
        return out
    if ps and ps.get("status") == "candidate" and ps.get("target"):
        out.update(state="candidate-pairing", target=ps["target"])
    elif ps:
        out["reason"] = ps.get("abstention_reason")
    return out


_LEAN_PAIRING: dict = {}


def _reading_record(r, cr: dict) -> dict:
    """One attributed source reading, as the decision names it and with the explanation
    from its full contribution (the Lean preview the reading's detail route reaches):
    {author, kind, provenance, review_state, decision, body, limitations, targets:
    [{target, declarations, component, relation, limitations, general_disclaimer, explanation}]}."""
    full = {}
    try:
        full = r.resolve(cr["detail"]) if cr.get("detail") else {}
    except reader.ReaderError:
        full = {}
    nav = (full or {}).get("navigation") or {}
    expl = {}
    for t in nav.get("targets") or []:
        row = (t.get("row_id") or "").replace("#", ":", 1)
        expl[row] = t.get("explanation") or ""
    targets = []
    for t in cr.get("targets") or []:
        tid = t.get("target") or ""
        targets.append({"target": tid, "declarations": list(t.get("declarations") or []), "component": t.get("component") or "",
                        "relation": t.get("relation"), "limitations": t.get("limitations") or "",
                        "general_disclaimer": t.get("general_disclaimer"), "explanation": expl.get(tid[2:], "")})
    return {"author": (cr.get("author") or {}).get("name") or "", "kind": (cr.get("author") or {}).get("kind") or "",
            "provenance": (cr.get("provenance") or {}).get("kind") or "", "review_state": cr.get("review_state") or "unreviewed",
            "decision": cr.get("decision") or "", "body": (full or {}).get("body") or "",
            "limitations": nav.get("limitations") or "", "targets": targets}


def lean_pairing(doc: dict, lid: str) -> dict:
    """One Lean statement's pairing with the family's paper statements: Statement Map's one
    decision for it (reader v9, Reader.pairing_decision), never re-ranked here. A citation
    in the Lean source or a binding in the release's manifest comes first; then an
    attributed source reading, which names each configured declaration, the paper
    statement it is linked to, the relation and the reading's limits; then the backend's
    source-text candidate from the Lean's own words; otherwise nothing is paired and the
    backend's reason is shown. Every pairing is unreviewed unless a review is recorded.

    Returns {state, kind, target, targets, evidence, method, reason, readings, alternatives,
    paper, paper_why, association, record}. state is the backend's; kind is the display
    state, "source-reading" for an attributed reading. evidence is one of declared, cited,
    reading, lean-words, none. targets keeps every linked statement in the backend's order."""
    lid = lid if lid.startswith("l:") else "l:" + lid
    key = (doc.get("id"), lid)
    if key in _LEAN_PAIRING:
        return _LEAN_PAIRING[key]
    r = RD()
    base = backend_pairing(doc, lid)
    try:
        d = r.pairing_decision(doc["id"], lid) or {}
    except reader.ReaderError:
        d = {}
    stc = d.get("source_text_candidate") or {}
    state = d.get("state") or base["state"]
    targets = list(dict.fromkeys(d.get("targets") or ([d["target"]] if d.get("target") else [])))
    if not d:
        targets = [base["target"]] if base.get("target") else []
    if not targets and state in PAIRED_STATES:
        state = "unavailable"
    method = d.get("method") or base.get("method")
    readings = [_reading_record(r, cr) for cr in d.get("contributed_readings") or []]
    reading = method == "contributed-source-reading"
    if state == "producer-declared-binding":
        ev = "declared"
    elif state == "producer-cited-association":
        ev = "cited"
    elif state == "candidate-pairing":
        ev = "reading" if reading else "lean-words"
    else:
        ev = "none"
    out = {"state": state, "kind": "source-reading" if (reading and targets) else state,
           "target": targets[0] if targets else None, "targets": targets, "evidence": ev, "method": method,
           "reason": None if targets else (d.get("reason") or base.get("reason") or LW("pairing.no_confident")),
           "readings": readings, "alternatives": list(stc.get("alternatives") or []),
           "paper": stc.get("paper"), "paper_why": list(stc.get("paper_why") or []),
           "association": base.get("association"), "record": d or base.get("record")}
    _LEAN_PAIRING[key] = out
    return out


def pairing_kind(pinfo: dict) -> str:
    """The display state of a pairing: the backend's state, or "source-reading" when an
    attributed source reading links the statements (it is still an unreviewed candidate)."""
    return pinfo.get("kind") or pinfo.get("state") or "unavailable"


# A reading's own limits often repeat the disclaimer the line naming the reader gives
# ("an agent source reading, not a proof replay"); that clause is not repeated beside
# every link. Every other clause the reader recorded is quoted as written.
_READING_DISCLAIMER = re.compile(
    r"agent[- ](?:source reading|authored)|no human approval|source[- ]level (?:formulation )?comparison only"
    r"|\bnot (?:an? )?(?:independent(?:ly)? (?:verification|review|reviewed|proof)|(?:lean |proof )(?:verification|replay|execution|certification)"
    r"|proof verification|independent verification|mathematical verification)", re.I)


# The words for a source reading are the family page's own (site/copy_family.json), so
# the Lean statement page says the same thing in the same words.
READING_WORDS = json.loads((SITE / "copy_family.json").read_text(encoding="utf-8"))["reading"]


def link_limits(t: dict) -> str:
    """The limits a source reader recorded for one link, as written. Statement Map flags a
    note that is only the general disclaimer (general_disclaimer, reader v10); the line
    naming the reader says that once, so a flagged note is not repeated beside the link.
    Without the flag, the disclaimer clauses are recognised by their words instead."""
    if "general_disclaimer" in t and t["general_disclaimer"] is not None:
        return "" if t["general_disclaimer"] else (t.get("limitations") or "").strip()
    return reading_limits(t.get("limitations"))


def reading_limits(text: str) -> str:
    """What a source reader recorded as a link's limits, clause by clause, without the
    general disclaimer that the line naming the reader already gives."""
    keep = [x for x in re.split(r"(?<=[.;])\s+", (text or "").strip()) if x and not _READING_DISCLAIMER.search(x)]
    out = " ".join(keep).strip()
    out = out[:-1] + "." if out.endswith(";") else out
    return out[:1].upper() + out[1:]


def reading_how_html(doc: dict, pinfo: dict, root: str) -> str:
    """How a source reading links a Lean statement to the paper, in full: who read the
    two sources, then each link (the configured declarations, the paper statement with
    its paper, the relation recorded), the reader's explanation and the limits they
    recorded, quoted as written."""
    F = READING_WORDS
    out = []
    for rd in pinfo.get("readings") or []:
        by = (F["by_agent"] if rd.get("kind") == "agent" else F["by_person"]).format(author=rd.get("author") or F["someone"])
        items = []
        for t in rd["targets"]:
            decls = ", ".join(f'<code translate="no">{esc(d)}</code>' for d in t["declarations"]) or esc(F["the_lean"])
            if t.get("component"):
                decls += " " + esc(F["component_of"]).replace("{component}", f'<code translate="no">{esc(t["component"])}</code>')
            rel = F["relation"].get(t.get("relation") or "", "")
            line = F["link"].format(decls="\x00", label="\x01", relation=esc(rel)).replace("\x00", decls).replace("\x01", statement_ref_html(doc, t["target"], root))
            expl = (f'<p class="rl__expl">{esc(curly_prose(t["explanation"]))}</p>') if t.get("explanation") else ""
            lim = link_limits(t)
            lim_html = f'<p class="rl__lim">{esc(F["limit"])} “{esc(curly_prose(lim))}”</p>' if lim else ""
            items.append(f'<li class="rl__i"><p class="rl__link">{line}</p>{expl}{lim_html}</li>')
        if items:
            out.append(f'<p class="rl__by">{ctext(by)}</p><ol class="rl__l">{"".join(items)}</ol>')
    return f'<div class="rl">{"".join(out)}</div>' if out else ""


def reading_link(pinfo: dict, target: str) -> dict | None:
    """The source reading's record for one linked paper statement: its declarations,
    relation, limitations and explanation, with the reading's author."""
    for rd in pinfo.get("readings") or []:
        for t in rd["targets"]:
            if t["target"] == target:
                return dict(t, author=rd["author"], author_kind=rd["kind"], review_state=rd["review_state"])
    return None


# Every page counts the pairing these pages show (the Families list, the cards, the map).
evidence.PAIRING_READER = lean_pairing


def pairing_terms(pinfo: dict, target: str | None = None) -> dict:
    """{lean, note, catalogue}: the words a candidate pairing was found by, split by where
    they come from."""
    target = target or pinfo.get("target")
    if pinfo.get("evidence") == "catalogue-words" and target == pinfo.get("target"):
        return {"lean": [], "title": [], "note": [], "catalogue": list(pinfo.get("backend_terms") or [])}
    a = next((x for x in pinfo.get("alternatives") or [] if x.get("target") == target), {})
    if not a.get("lean_terms") and not a.get("note_terms") and not a.get("title_terms") and a.get("matched_terms"):
        return {"lean": [], "title": [], "note": [], "catalogue": list(a["matched_terms"])}   # a backend record
    return {"lean": list(a.get("lean_terms") or []), "title": list(a.get("title_terms") or []),
            "note": list(a.get("note_terms") or []), "catalogue": []}


def pair_targets(doc: dict) -> dict:
    """Lean id -> (paper statement ids, pairing state) for every Lean statement of a
    family, from lean_pairing. The ids are every statement the Lean is paired with, the
    clearest first; an empty list is "no confident match". The map board and the family
    page both read this, so they draw the same pairs."""
    out = {}
    for l in doc.get("lean") or []:
        p = lean_pairing(doc, l["id"])
        out[l["id"]] = (list(p.get("targets") or ([p["target"]] if p.get("target") else [])), p["state"])
    return out


def backend_statement(doc: dict, stmt_id: str) -> dict | None:
    return next((s for s in doc.get("statements") or [] if s.get("id") == stmt_id), None)


def ms_statement(doc: dict, stmt_id: str):
    """(manuscript, statement in data/manuscripts.json, backend statement record) for a
    backend statement id, joined by manuscript and label, else file and line; the
    printed TeX lives in the Atlas's own extraction."""
    rec = backend_statement(doc, stmt_id) if doc else None
    if not stmt_id or not stmt_id.startswith("r:"):
        return None, None, rec
    slug, _, anchor = stmt_id[2:].partition(":")
    m = MS.get(slug)
    if not m:
        return None, None, rec
    st = None
    if not anchor.startswith("L-"):
        label = anchor.split("@", 1)[0]
        cands = [s for s in m["statements"] if s.get("label") == label]
        if len(cands) > 1 and rec and rec.get("source"):
            line = rec["source"].get("line")
            cands = [s for s in cands if s.get("line") == line] or cands
        st = cands[0] if cands else None
    if st is None and rec and rec.get("source"):
        f = (rec["source"].get("file") or "").split(f"preprints/{slug}/", 1)[-1]
        st = next((s for s in m["statements"] if s.get("file") == f and s.get("line") == rec["source"].get("line")), None)
    if st is None and rec and rec.get("source"):
        st = backend_only_statement(doc, rec, slug)
    return m, st, rec


_LABEL_LEAD = re.compile(r"^\s*\\label\{[^{}]*\}\s*")


def statement_detail(doc: dict, stmt_id: str) -> dict | None:
    """A paper statement's statement-detail packet, through the family's evidence case
    that names it (the exact TeX, its source file and line, its printed number)."""
    try:
        ev = RD().evidence(doc["id"]) if doc else None
    except reader.ReaderError:
        return None
    for case in (ev or {}).get("cases") or []:
        for ps in case.get("paper_statements") or []:
            if ps.get("id") == stmt_id and ps.get("detail"):
                return RD().resolve(ps["detail"])
    return None


def backend_only_statement(doc: dict, rec: dict, slug: str) -> dict | None:
    """A statement the Atlas's extraction does not hold (a lemma, or a statement the backend
    imported by its exact anchor), in that extraction's shape, from the backend's record
    and its statement-detail packet. The text is the source's own TeX without its label."""
    text = rec.get("text") or ""
    det = None
    if not text.strip():
        det = statement_detail(doc, rec["id"])
        text = (det or {}).get("text") or ""
    if not text.strip():
        return None
    src = rec.get("source") or (det or {}).get("source") or {}
    # The statement's TeX label is its id's anchor (r:<slug>:<label>); a location anchor
    # (L-<file>-<line>) has none. The record's name is a label or the statement's title.
    anchor = (rec.get("id") or "")[2:].partition(":")[2].split("@", 1)[0]
    label = anchor if anchor and not anchor.startswith("L-") else ""
    name = rec.get("name") or ""
    title = "" if (not name or name == label or name == rec.get("display")) else name
    return {"file": (src.get("file") or "").split(f"preprints/{slug}/", 1)[-1], "line": src.get("line"),
            "label": label or None, "title": title or None, "text": _LABEL_LEAD.sub("", text),
            "display": rec.get("display") or "Statement", "kind": rec.get("statement_kind"),
            "env": rec.get("statement_kind"), "section": rec.get("section"), "section_title": rec.get("section_title"),
            "appendix": bool(rec.get("appendix")), "headline": False, "sha256": None, "backend_only": True}


def backend_printed(rec: dict | None, st: dict | None = None) -> str:
    """'Theorem 1.1', or the kind with its numbering state; never a section number."""
    kind = (rec or {}).get("display") or (st or {}).get("display") or LW("statement_kind")
    status = (rec or {}).get("printed_number_status")
    if status == "recorded" and rec.get("printed_number"):
        return f"{kind} {rec['printed_number']}"
    return f"{kind} ({C('family.num_' + ('unnumbered' if status == 'unnumbered' else 'unavailable'))})"


def statement_reading_page(rec: dict | None, st: dict | None, m: dict | None) -> str | None:
    """Where a paper statement is read: the backend's reading_page, else, for a statement
    the backend imported by its exact TeX label (a lemma the Atlas's extraction does not
    hold), that label's anchor on the paper's reading page. check_paper_links.py fails the
    build if such an anchor is missing."""
    if rec and rec.get("reading_page"):
        return rec["reading_page"]
    label = (st or {}).get("label")
    if m and label and (st or {}).get("backend_only") and m["id"] in PAPER_READING:
        return f"papers/{quote(m['id'])}.html#{quote(label, safe=':')}"
    return None


def statement_ref_html(doc, stmt_id, root) -> str:
    """'Theorem 1.1 of <paper title>', linked to its place on the paper's reading page."""
    m, st, rec = ms_statement(doc, stmt_id)
    name = backend_printed(rec, st)
    page = statement_reading_page(rec, st, m)
    href = (root + page) if page else (f"{root}papers/{quote(m['id'])}.html" if m else None)
    title = ms_title_html(m) if m else esc(stmt_id)
    link = f'<a href="{esc(href)}">{esc(name)}</a>' if href else esc(name)
    return LW("pairing.ref", name="\x00", title="\x01").replace("\x00", link).replace("\x01", f'<span class="tex-auto">{title}</span>')


def words_list(terms: list, show: int = 8) -> str:
    """'a, b and c', at most show words, with 'and n more' past that."""
    shown = list(terms[:show])
    if not shown:
        return ""
    if len(terms) > show:
        return ", ".join(shown) + " " + LW("pairing.and_more", n=say(len(terms) - show))
    return ", ".join(shown[:-1]) + (" " + LW("and") + " " if len(shown) > 1 else "") + shown[-1]


def shared_words_sentence(pinfo: dict, target: str | None = None, show: int = 8) -> list:
    """The sentences saying which words a candidate was found by and where each comes
    from: the Lean text, the paper's title (for a main theorem), the release's name and
    note for the Lean, or, for the fallback, the catalogue's wording."""
    t = pairing_terms(pinfo, target)
    out = []
    if t["lean"]:
        out.append(LW("pairing.how_lean", words=words_list(t["lean"], show)))
    if t.get("title"):
        out.append(LW("pairing.how_title", words=words_list(t["title"], show)))
    if t["note"]:
        out.append(LW("pairing.how_note", words=words_list(t["note"], show)))
    if t["catalogue"]:
        out.append(LW("pairing.how_catalogue", words=words_list(t["catalogue"], show)))
    if not out:
        out.append(LW("pairing.how_nothing"))
    return out


def paper_pref_sentence(pinfo: dict) -> str:
    """Why the candidates come from one paper, when the release's names say which."""
    if not pinfo.get("paper") or not pinfo.get("paper_why"):
        return ""
    m = MS.get(pinfo["paper"]) or {}
    title = f'<span class="tex-auto">{ms_title_html(m)}</span>' if m else esc(pinfo["paper"])
    return esc(LW("pairing.paper_why." + pinfo["paper_why"][0], paper="\x00")).replace("\x00", title)


def join_html(doc, pinfo, root) -> str:
    """The words at the join between the paper theorem and the Lean statement: what
    links them, by what evidence, and that nobody has reviewed the match."""
    state = pinfo["state"]
    cls = {"candidate-pairing": "join--candidate", "producer-cited-association": "join--cited",
           "producer-declared-binding": "join--cited"}.get(state, "join--none")
    parts = [] if state in PAIRED_STATES else [f'<p class="join__words">{esc(evidence.say("pairing." + state))}</p>']
    if state == "candidate-pairing":
        ev_key = pinfo.get("evidence", "lean-words") + ("-multi" if len(pinfo.get("targets") or []) > 1 else "")
        parts.append(f'<p class="join__words">{esc(LW("pairing.evidence." + ev_key))}</p>')
        if pinfo.get("evidence") == "reading":
            parts.append(reading_how_html(doc, pinfo, root))
        elif len(pinfo.get("targets") or []) < 2:
            parts.append(f'<p class="join__how">{esc(" ".join(shared_words_sentence(pinfo)))}</p>')
        pref = paper_pref_sentence(pinfo)
        if pref:
            parts.append(f'<p class="join__how">{pref}</p>')
    elif state == "producer-cited-association" and pinfo.get("association"):
        a = pinfo["association"]
        src = a.get("source") or {}
        url = f'https://github.com/openai/math/blob/{src.get("pin") or COMMIT}/{src.get("file")}#L{src.get("start_line")}-L{src.get("end_line")}'
        parts.append(f'<p class="join__how">{esc(LW("pairing.cited_how", declaration=a.get("declaration") or ""))} '
                     f'<a class="ext" href="{esc(url)}" rel="noopener">{esc(LW("pairing.cited_link", line=src.get("start_line")))}</a></p>'
                     f'<pre class="lean lean--quote"><code>{esc(src.get("quote") or "")}</code></pre>')
    if not parts:
        return ""
    return f'<div class="join {cls}" role="note" aria-label="{esc(LW("pairing.join_label"))}">{"".join(parts)}</div>'


def alternatives_html(doc, pinfo, root, limit=4) -> str:
    """The other close statements, as a visible list: each with the Lean words it shares,
    or, when it shares none, the words it shares with the release's name and note."""
    shown = set(pinfo.get("targets") or []) | {pinfo.get("target")}
    rows = [a for a in pinfo["alternatives"] if a.get("target") and a["target"] not in shown and a.get("score", 1) > 0][:limit]
    items = []
    for a in rows:
        why = " ".join(shared_words_sentence(pinfo, a["target"], show=6))
        items.append(f'<li>{statement_ref_html(doc, a["target"], root)}. <span class="muted">{esc(why)}</span></li>')
    return "".join(items)


def run_state_words(run) -> str:
    return LW("runs.state." + run.get("state", "unknown")) if run.get("state") in COPY_LEAN["runs"]["state"] else run.get("state", "")


def lean_runs_html(rec, root) -> str:
    """Re-runs reported by outside groups, grouped by source as the backend groups them,
    each in the group's own term, dated, with its receipt."""
    runs = {x["id"]: x for x in rec.get("runs") or []}
    names = {}
    for x in runs.values():
        names.setdefault(x["source"], prose_credit((x.get("credit") or {}).get("name") or x["source"]))
    acc = [names.get(s, s) for s in rec.get("accepted_current_sources") or []]
    lead = (evidence.say("reruns.none") if not acc else evidence.say("reruns.one", names=acc[0]) if len(acc) == 1
            else cap(evidence.say("reruns.many", n=say(len(acc)), names=evidence.join_names(acc))))
    groups = []
    for g in rec.get("run_groups") or []:
        rows = [runs[i] for i in g.get("run_ids") or [] if i in runs]
        if not rows:
            continue
        credit = rows[0].get("credit") or {}
        who = f'<a class="ext" href="{esc(credit["url"])}" rel="noopener">{esc(names[g["source"]])}</a>' if credit.get("url") else esc(names[g["source"]])
        lis = []
        for x in rows:
            sv = x.get("source_value") or {}
            pin = LW("runs.pin_current") if x.get("pin_state") == "current" else LW("runs.pin_other", pin=str(x.get("pin") or "")[:7])
            when = date_words(x["date"]) if x.get("date") else LW("runs.undated")
            receipt = f' <a class="ext" href="{esc(x["receipt"])}" rel="noopener">{esc(LW("runs.receipt"))}</a>' if x.get("receipt") else ""
            lis.append(f'<li><p><span class="run__state">{esc(cap(run_state_words(x)))}</span> '
                       f'<span class="run__term">{esc(LW("runs.their_term", term=x.get("source_term") or ""))}</span></p>'
                       f'<p>{esc(curly(sv.get("text") or ""))}</p>'
                       f'<p class="small muted">{esc(LW("runs.when", when=when, pin=pin))}{receipt}</p></li>')
        method = (credit.get("method") or "").strip()
        if method and method[-1] not in ".!?)":
            method += "…"   # the source record stops mid-sentence; say so rather than end abruptly
        method_html = (f'<details class="run__method"><summary>{esc(LW("runs.method"))}</summary><p class="small">{esc(curly(method))}</p></details>'
                       if method else "")
        groups.append(f'<div class="run"><h3 class="h3">{who}</h3>{method_html}<ul class="run__list">{"".join(lis)}</ul></div>')
    body = f'<div class="runs">{"".join(groups)}</div>' if groups else f'<p class="muted">{esc(LW("runs.none_recorded"))}</p>'
    return (f'<p class="lead-sentence">{esc(cap(curly(lead)))} {esc(LW("runs.reported"))}</p>{body}')


def scope_draft_html(fid, doc, rec) -> str:
    """OpenAI's own note on what the Lean covers, quoted, then the AI agent's draft
    classification of it as one quiet line, never styled as a verdict."""
    sd = (rec or {}).get("scope_draft") or {}
    val = sd.get("value") or {}
    if not val:
        return ""
    note_url = (((doc.get("producer_scope") or {}).get("value") or {}).get("url"))
    parts = []
    if val.get("quote"):
        foot = (f'<footer>{esc(C("statement.coverage_quote_by"))} <a class="ext" href="{esc(note_url)}" rel="noopener">'
                f'{esc(C("statement.coverage_source"))}</a></footer>') if note_url else ""
        parts.append(f'<p class="scope__src">{esc(C("statement.note_heading"))}</p>'
                     f'<blockquote class="quote md-math"><p>“{esc(val["quote"])}”</p>{foot}</blockquote>')
    cls = val.get("class")
    if cls:
        parts.append(f'<p class="scope__draft">{esc(C("statement.draft_line", cls=cover_label(cls)))}</p>')
    return '<div class="scope">' + "".join(parts) + "</div>"


def crumb_title(title_html: str, plain: str, n: int = 52) -> str:
    """A breadcrumb's short title: the rendered title when it is short, otherwise its
    plain words cut at a word, with the whole title in the tooltip."""
    if len(plain) <= n:
        return title_html
    return f'<span title="{esc(plain)}">{esc(short(plain, n - 4))}</span>'


def lean_symbols_html(code: str, definition_only: bool) -> str:
    """A key to the Lean notation the shown lines actually use, at the point a newcomer
    reads them: each entry's pattern is searched in the code, and only entries found are
    listed (site/copy_lean.json "symbols"). The first entry reads the statement's frame."""
    rows = [LW("symbols.frame_def" if definition_only else "symbols.frame_theorem")]
    for ent in COPY_LEAN["symbols"]["entries"]:
        if re.search(ent["re"], code):
            rows.append(ent["say"])
        if len(rows) >= 11:
            break
    items = "".join(f"<li>{ctext(r_)}</li>" for r_ in rows)
    return (f'<div class="lsym"><p class="lsym__h">{esc(LW("symbols.heading"))}</p>'
            f'<ul class="lsym__list">{items}</ul><p class="lsym__more">{ctext(LW("symbols.more"))}</p></div>')


def lean_groups(doc, rec):
    """Each group with an assessment of the family or a run of this statement, in the
    site's reader order: (source, display name, reading, runs)."""
    import evidence as _ev
    readings = {r_["source"]: r_ for r_ in (doc or {}).get("readings") or []}
    runs = [x for x in (rec or {}).get("runs") or []]
    run_by = defaultdict(list)
    for g in (rec or {}).get("run_groups") or []:
        ids = set(g.get("run_ids") or [])
        run_by[g["source"]].extend(x for x in runs if x["id"] in ids)
    order = _ev.reader_order(set(readings))
    order = [s for s in order if s in readings] + [s for s in run_by if s not in readings]
    out = []
    for src in order:
        rd = readings.get(src)
        rr = run_by.get(src) or []
        credit = (rd or {}).get("credit") or (rr[0].get("credit") if rr else {}) or {}
        out.append((src, prose_credit(credit.get("name") or src), rd, rr))
    return out


def reruns_sentence(rec) -> str:
    """Who reports that Comparator accepted OpenAI's solution for this Lean statement."""
    runs = {x["id"]: x for x in (rec or {}).get("runs") or []}
    names = {}
    for x in runs.values():
        names.setdefault(x["source"], prose_credit((x.get("credit") or {}).get("name") or x["source"]))
    acc = [names.get(s_, s_) for s_ in (rec or {}).get("accepted_current_sources") or []]
    return cap(curly(evidence.say("reruns.none") if not acc else evidence.say("reruns.one", names=acc[0]) if len(acc) == 1
                     else evidence.say("reruns.many", n=say(len(acc)), names=evidence.join_names(acc))))


def lean_left_items(sid, fid, doc, rec, pinfo, paper_ok, definition_only) -> list:
    """What is still unchecked about this Lean statement, in plain sentences, from the
    backend's open items for it and its family and from the contributions on record."""
    items = []
    ref = None
    kinds = {x.get("kind") for x in (doc or {}).get("remaining_checks") or []
             if x.get("target") in ("l:" + sid, fid)}
    if paper_ok and pinfo.get("target") and not CONTRIB["checks"].get(sid):
        refs = []
        for t in pinfo.get("targets") or [pinfo["target"]]:
            _m, _st, _r = ms_statement(doc, t)
            refs.append(backend_printed(_r, _st))
        ref = ", ".join(refs[:-1]) + (" " + C("family.and") + " " if len(refs) > 1 else "") + refs[-1]
        # A source reading recorded a relation; what is unchecked is a person's review of it.
        items.append(LW("left.match_reading" if pairing_kind(pinfo) == "source-reading" else "left.match", ref=ref))
    elif not paper_ok and pinfo.get("readings"):
        items.append(LW("left.no_match_reading"))
    elif not paper_ok:
        items.append(LW("left.no_match"))
    if "replay" in kinds:
        items.append(LW("left.replay"))
    if "definition-review" in kinds or definition_only:
        items.append(LW("left.definitions"))
    if "scope-review" in kinds:
        items.append(LW("left.scope"))
    readings = (doc or {}).get("readings") or []
    if readings:
        import evidence as _ev
        if _ev.family_evidence(RD(), fid).agreement == "disagree":
            items.append(LW("left.disagree"))
    items.append(LW("left.paper"))
    return items


def lean_group_cards(fam, fid, doc, rec, root, definition_only) -> str:
    """What each outside group found, as one card per group side by side (the family
    page's grammar): its assessment of the family's Lean in plain words with a dot in the
    map's ink, its own term, its reason quoted, then its Comparator run of this Lean
    statement. The assessment is of the family's Lean; the run is of this statement; the
    lead says so once. Every value is the backend's; nothing is scored here."""
    import evidence as _ev
    fam_id = fam["id"] if fam else (fid or "f:")[2:]
    comparator = term_link("comparator", "Comparator") if "comparator" in GLOSSARY else "Comparator"
    cards = []
    groups = lean_groups(doc, rec)
    for src, nm, rd, rr in groups:
        who = term_link(src, esc(nm)) if src in GLOSSARY else esc(nm)
        term = ""
        if rd:
            sv = rd.get("source_value") or {}
            tone = _ev.TONE.get(rd.get("state"), "none")
            dot = {"full": "all", "part": "part", "other": "other"}.get(tone, "none")
            defn = curly(sv.get("text") or "")
            t = rd.get("source_term") or ""
            if t:
                term = (f'<p class="lxb-vd__term"><span class="lxb-vt"{f" title={chr(34)}{esc(defn)}{chr(34)}" if defn else ""}>'
                        f'{esc(LW("glance.their_term", term=t))}</span></p>')
            gloss = COPY_LEAN["board"]["state"].get(rd.get("state") or "") or cap(_ev.say("tone." + tone))
            reason = (sv.get("gap") or sv.get("note") or "").strip()
            if reason.rstrip(".").lower() == "none":
                reason = ""
            link = (f' <a class="ext lxb-vd__go" href="{esc(sv["url"])}" rel="noopener">{esc(LW("board.record"))}</a>'
                    if sv.get("url") else "")
            why = (f'<blockquote class="lxb-vd__why md-math"><p>“{ctext(reason)}”{link}</p></blockquote>' if reason
                   else f'<p class="lxb-vd__why lxb-vd__why--none">{esc(LW("board.no_reason"))}{link}</p>')
            defs = sv.get("definitions_to_check")
            if defs:
                why += f'<p class="lxb-vd__defs"><span>{esc(LW("readings.defs"))}</span> {ctext(defs)}</p>'
            body = (f'<p class="lxb-vd__out"><span class="lxb-dot lxb-dot--{dot}" aria-hidden="true"></span>'
                    f'{esc(LW("board.on_family", id=fam_id, what=gloss))}</p>{why}')
        else:
            body = f'<p class="lxb-vd__none">{esc(LW("board.not_read"))}</p>'
        if rr:
            items = []
            for x in rr:
                st_ = x.get("state") or "unknown"
                word = COPY_LEAN["board"]["run"].get(st_) or cap(run_state_words(x))
                when = date_words(x["date"]) if x.get("date") else LW("runs.undated")
                pin = "" if x.get("pin_state") == "current" else " " + LW("glance.pin_other", pin=str(x.get("pin") or "")[:7])
                rep = f' <a class="ext" href="{esc(x["receipt"])}" rel="noopener">{esc(LW("glance.report"))}</a>' if x.get("receipt") else ""
                acct = curly((x.get("source_value") or {}).get("text") or "")
                items.append(f'<li><p class="lxb-run__out lxb-run__out--{esc(st_)}">{esc(word)}</p>'
                             f'<p class="lxb-run__term">{esc(LW("board.their_label"))} <span class="lxb-vt">{esc(LW("glance.their_term", term=x.get("source_term") or ""))}</span>, '
                             f'{esc(when + pin)}{rep}</p>'
                             + (f'<p class="lxb-run__acct">{esc(acct)}</p>' if acct else "") + '</li>')
            run = f'<ul class="lxb-run__list">{"".join(items)}</ul>'
        else:
            run = f'<p class="lxb-run__none">{esc(LW("glance.no_run"))}</p>'
        run_k = esc(LW("board.run_k" + ("_def" if definition_only else ""), comparator="\x00")).replace("\x00", comparator)
        cards.append(f'<article class="lxb-vd"><header class="lxb-vd__hd"><h3 class="lxb-vd__who">{who}</h3>{term}</header>'
                     f'{body}<div class="lxb-vd__run"><p class="lxb-vd__rk">{run_k}</p>{run}</div></article>')
    ev = _ev.family_evidence(RD(), fid) if fid else None
    lead = []
    if any(rd for _s, _n, rd, _r in groups):
        lead.append(esc(LW("board.lead", id=fam_id)))
        if ev and (doc or {}).get("readings"):
            lead.append(esc(ev.agreement_sentence()))
    pass_ = esc(LW("board.pass" + ("_def" if definition_only else ""), comparator="\x00")).replace("\x00", comparator)
    fam_link = (f'<a href="{root}families/{esc(fam_id)}.html#h-readings">{esc(LW("page.readings_link"))}</a>' if fam else "")
    grid = (f'<div class="lxb-vds">{"".join(cards)}</div>' if cards
            else f'<p class="muted">{esc(LW("runs.none_recorded"))}</p>')
    return (f'<section class="band band--tight lxb-groups" aria-labelledby="h-groups"><span id="h-readings" class="anchor-alias"></span>'
            f'<h2 class="lxb-h" id="h-groups">{esc(LW("board.heading"))} <button type="button" class="help-q" data-help="questions" aria-label="{esc(LW("glance.help_label"))}">?</button></h2>'
            + (f'<p class="lxb-lead">{" ".join(lead)}</p>' if lead else "")
            + f'{grid}<div class="lxb-foot"><p>{pass_}</p>{f"<p>{fam_link}</p>" if fam_link else ""}</div></section>')


def lean_next_html(fam, sid, paper_rec, paper_ref, rec, stmt, root) -> str:
    """Where a reader goes from here: the family page, the paper passage, each group's
    original reports, the file on GitHub."""
    items = []
    if fam:
        items.append(f'<li><a href="{root}families/{fam["id"]}.html">{esc(LW("next.family", id=fam["id"]))}</a> '
                     f'<span class="muted">{esc(LW("next.family_what"))}</span></li>')
    if paper_rec and paper_rec.get("reading_page") and paper_ref:
        items.append(f'<li><a href="{esc(root + paper_rec["reading_page"])}">{esc(LW("next.paper", ref=paper_ref))}</a> '
                     f'<span class="muted">{esc(LW("next.paper_what"))}</span></li>')
    seen = set()
    for x in (rec or {}).get("runs") or []:
        if x.get("receipt") and x["receipt"] not in seen:
            seen.add(x["receipt"])
            nm = prose_credit((x.get("credit") or {}).get("name") or x["source"])
            items.append(f'<li><a class="ext" href="{esc(x["receipt"])}" rel="noopener">{esc(LW("next.report", name=nm))}</a></li>')
    items.append(f'<li><a class="ext" href="{esc(stmt["url"])}" rel="noopener">{esc(LW("next.file"))}</a> '
                 f'<span class="muted">{esc(LW("next.file_what"))}</span></li>')
    return (f'<section class="band band--tight lxs-next" aria-labelledby="h-next"><h2 class="h2" id="h-next">{esc(LW("next.heading"))}</h2>'
            f'<ul class="next">{"".join(items)}</ul></section>')


_PAPER_MARKS = None


def paper_marks():
    """(manuscript id, file, line) -> what the backend records at that theorem, for the
    paper reading pages' margin notes: {"lean": [{id, state, accepted, holes}],
    "headline": [family ids whose catalogue claim names it as the candidate]}.
    Every pairing is lean_pairing's reading of the backend's records."""
    global _PAPER_MARKS
    if _PAPER_MARKS is not None:
        return _PAPER_MARKS
    r = RD()
    marks = defaultdict(lambda: {"lean": [], "headline": []})
    for fid in r.family_ids():
        doc = r.family(fid)
        for rec in doc.get("lean") or []:
            pinfo = lean_pairing(doc, rec["id"])
            if pinfo["state"] not in PAIRED_STATES or not pinfo["target"]:
                continue
            # Every statement the Lean is linked to carries the note, not only the first.
            for target in pinfo.get("targets") or [pinfo["target"]]:
                m, st, _ = ms_statement(doc, target)
                if not st:
                    continue
                row = marks[(m["id"], st["file"], st["line"])]
                if any(x["id"] == rec["id"] for x in row["lean"]):
                    continue
                row["lean"].append({"id": rec["id"], "state": pairing_kind(pinfo),
                                        "accepted": len(rec.get("accepted_current_sources") or []),
                                        "holes": len(rec["definition_holes"]) if isinstance(rec.get("definition_holes"), list) else None})
        claim = doc.get("claim") or {}
        if claim.get("state") == "candidate" and claim.get("primary_candidate"):
            m, st, _ = ms_statement(doc, claim["primary_candidate"])
            if st:
                marks[(m["id"], st["file"], st["line"])]["headline"].append(fid)
    _PAPER_MARKS = dict(marks)
    return _PAPER_MARKS


def proof_sources_html(fid, sid) -> str:
    """The solution declarations Comparator checks against this challenge, each linked at
    its own pinned file and line, and the Comparator configuration: the backend's source
    roles (lean-preview packets). The challenge's `sorry` is a placeholder, never the
    submitted proof; this line says where the proof is."""
    pv = RD().lean_preview(fid, sid) if fid else None
    roles = (pv or {}).get("source_roles") or {}
    sols = [x for x in roles.get("solutions") or [] if (x.get("source") or {}).get("url")]
    if not sols:
        return ""
    items = []
    for x in sols:
        src = x["source"]
        where = f'<code>{esc(src["file"].rsplit("/", 1)[-1])}</code>' + (", " + esc(LW("sheet.proof_line", line=src["line"])) if src.get("line") else "")
        items.append(f'<li><a class="ext" href="{esc(src["url"])}" rel="noopener"><code translate="no">{esc(x["name"])}</code></a> ({where})</li>')
    cfg = ((roles.get("configuration") or {}).get("source") or {}).get("url")
    settings = f'<p class="lxb-note"><a class="ext" href="{esc(cfg)}" rel="noopener">{esc(LW("sheet.proof_settings"))}</a></p>' if cfg else ""
    return (f'<p class="lxb-note lxb-proof">{esc(LW("sheet.proof_one" if len(sols) == 1 else "sheet.proof_many"))}</p>'
            f'<ul class="lxb-proofs">{"".join(items)}</ul>{settings}')


OG_DONE: dict = {}   # statement id -> (generic og block, per-statement og block)


def build_statement(stmt):
    sid = stmt["id"]
    rel = f"statements/{sid}.html"
    root = "../"
    page_url = BASE_URL + rel
    fam = FAM.get(stmt["families"][0]) if stmt.get("families") else None
    label = curly_prose((stmt.get("labels") or [sid])[0])
    lines_html = lean_lines(stmt["lean"])
    # The backend's record for this Lean statement: its family packet, its pairing,
    # its re-runs and the draft scope reading.
    fid, doc, lrec = lean_family_doc(sid)
    summ = RD().lean_summary(sid) or {}
    pinfo = lean_pairing(doc, sid) if doc else {"state": "unavailable", "target": None, "reason": LW("pairing.no_record"),
                                                "alternatives": [], "association": None}
    paper_ms, paper_st, paper_rec = ms_statement(doc, pinfo["target"]) if pinfo["target"] else (None, None, None)
    if pinfo["target"] and not paper_st:
        warn(f"{sid}: the backend pairs it with {pinfo['target']}, which data/manuscripts.json does not hold")
    conv = TexConv(paper_ms, root) if paper_ms else None
    card = receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html, pinfo, lrec)
    # full card page for screenshots
    card_rel = f"cards/{sid}.html"
    card_body = receipt_card(stmt, root, page_url, paper_ms, paper_st, conv, lines_html, pinfo, lrec, standalone=True)
    write_page(card_rel, head(card_rel, label, label, noindex=True) + f'\n<body class="card-only" data-root="{root}">\n{card_body}\n{macros_script([paper_ms["id"]] if paper_ms else [])}\n</body></html>\n', index=False)
    # The sheet's left half: the paper theorem the Lean statement is paired with, exactly
    # as printed (several when its parts match several), or, with none paired, why and
    # the closest statements. The words at the join say how the two are linked, once.
    multi = len(pinfo.get("targets") or []) > 1 and bool(paper_st)
    reading = pairing_kind(pinfo) == "source-reading"
    pair_state = ("reading" if reading and paper_st else "multi" if multi
                  else pinfo["state"] if pinfo["state"] in PAIRED_STATES and paper_st else "unavailable")
    alts = alternatives_html(doc, pinfo, root, limit=6 if paper_st else 5) if doc else ""
    if paper_st:
        blocks = []
        for t in (pinfo["targets"] if multi else [pinfo["target"]]):
            tm, tst, _ = ms_statement(doc, t)
            if not tst:
                continue
            blocks.append(f'<div class="pair__target"><p class="claim__src">{statement_ref_html(doc, t, root)}</p>'
                          + render_paper_statement(tm, tst, root, conv if tm is paper_ms else TexConv(tm, root), "claim") + "</div>")
        paper_side = "".join(blocks)
    else:
        # With nothing paired: the backend's reason, then the closest statements by name
        # only; the words each shares wait in "How Atlas looked for a paper theorem".
        reason = pinfo.get("reason")
        if pinfo.get("readings"):
            # A source reading that links nothing: who read the sources and their reason.
            F = READING_WORDS
            rd = pinfo["readings"][0]
            reason = None
            paper_side_lead = (f'<p class="lxb-none">{esc(F["unresolved"].format(author=rd.get("author") or F["someone"]))}</p>'
                               f'<p class="lxb-none rl__lim">“{esc(curly_prose(reading_limits(pinfo.get("reason") or rd.get("limitations") or "")))}”</p>')
        else:
            paper_side_lead = ""
        shown_ = set(pinfo.get("targets") or []) | {pinfo.get("target")}
        near = [a["target"] for a in (pinfo.get("alternatives") or [])
                if a.get("target") and a["target"] not in shown_ and a.get("score", 1) > 0][:5] if doc and not pinfo.get("readings") else []
        paper_side = (paper_side_lead + (f'<p class="lxb-none">{esc(cap(reason))}</p>' if reason else "")
                      + (f'<p class="lxb-xh">{esc(LW("sheet.closest"))}</p><ul class="alts">'
                         + "".join(f"<li>{statement_ref_html(doc, t, root)}</li>" for t in near) + '</ul>' if near else ""))
    join_line = (f'<p class="lxb-join lxb-join--{esc(pair_state)}"><span class="lxb-jh">{esc(LW("sheet.join_head." + pair_state))}.</span> '
                 f'{esc(LW("sheet.join_qual." + pair_state))} <a href="#h-pairing">{esc(LW("sheet.join_how" + ("_reading" if reading else "")))}</a></p>')
    # How the pairing was found, for a reader who asks: the words shared, the cited line,
    # why one paper, the other candidates and the method. None of it repeats the join.
    how = []
    if reading and paper_st:
        how.append(reading_how_html(doc, pinfo, root))
    elif pinfo["state"] == "candidate-pairing" and paper_st:
        for t in (pinfo["targets"] if multi else [pinfo["target"]]):
            lead_ = (statement_ref_html(doc, t, root) + ". ") if multi else ""
            how.append(f'<p class="join__how">{lead_}{esc(" ".join(shared_words_sentence(pinfo, t)))}</p>')
    elif pinfo["state"] == "producer-cited-association" and pinfo.get("association"):
        how.append(join_html(doc, pinfo, root))
    pref = "" if reading else paper_pref_sentence(pinfo)
    if pref:
        how.append(f'<p class="join__how">{pref}</p>')
    if alts and not reading and not pinfo.get("readings"):
        how.append(f'<h3 class="h3">{esc(LW("page.alternatives_heading" if paper_st else "sheet.closest_how"))}</h3><ul class="alts">{alts}</ul>')
    if doc and (reading or pinfo.get("readings")):
        how.append(f'<p class="small muted pair__method">{esc(LW("pairing.method_reading"))}</p>')
    elif doc and pinfo["state"] not in ("producer-cited-association", "producer-declared-binding"):
        how.append(f'<p class="small muted pair__method">{esc(LW("pairing.method"))}</p>')
    # The shared words and the method on the left, the other candidates beside them, so
    # neither column runs half the width with the other half empty (24 October 2026).
    alt_i = next((i for i, x in enumerate(how) if '<ul class="alts">' in x), None)
    if alt_i is not None and len(how) > 1:
        rest = [x for i, x in enumerate(how) if i != alt_i]
        how = [f'<div class="lxb-how__cols"><div class="lxb-how__a">{"".join(rest)}</div><div class="lxb-how__b">{how[alt_i]}</div></div>']
    pairing_section = (f'<section class="band band--tight lxb-how" aria-labelledby="h-pairing">'
                       f'<h2 class="h2" id="h-pairing">{esc(LW("sheet.how_heading" + ("_reading" if reading and paper_st else "" if paper_st else "_none")))}</h2>'
                       + "".join(how) + '</section>')
    # ... the Lean statement with the definitions needed to read it ...
    snippet_full = lean_snippet_html(stmt, lines_html)
    # The same lines as plain text for the Copy button (the rendered lines are spans).
    _src = stmt["lean"].split("\n")
    _tg = stmt["comparator"]["theorem_names"] or stmt["theorems"][:1]
    _ranges = (lean_key_ranges(stmt["lean"], _tg) if _tg else
               sorted({sp for n_, sp in decl_spans(stmt)[0].items() if n_ in (stmt["comparator"].get("definition_names") or [])}))
    lean_copy = "\n\n".join("\n".join(_src[a:b + 1]) for a, b in _ranges)
    defs = definitions_html(stmt, lines_html, shown=_ranges)
    holes = def_holes(stmt)
    definition_only = not stmt["comparator"]["theorem_names"] and bool(holes)
    plain_reading = scope_draft_html(fid, doc, lrec) if doc else ""
    symbols = lean_symbols_html(lean_copy, definition_only)
    left_items = lean_left_items(sid, fid, doc, lrec, pinfo, bool(paper_st), definition_only)
    # One line under the Lean text: what stands in for the proof, or, for a file that
    # configures definitions, what Comparator compares instead. The rest waits below.
    lean_note = (LW("sheet.def_note", names=", ".join(h["short"] for h in holes)) if definition_only else
                 C("statement.sorry_note_axiom") if stmt["declares_axiom"] else LW("sheet.sorry"))
    holes_html = ""
    if holes:
        items = []
        for h_ in holes:
            if h_["url"]:
                link = f'<a class="ext" href="{esc(h_["url"])}" rel="noopener"><code>{esc(h_["file"])}</code></a>'
                items.append("<li>" + ctext(C("statement.hole_item", name=h_["short"], link="\x00")).replace("\x00", link) + "</li>")
            else:
                items.append("<li>" + ctext(C("statement.hole_item_nolink", name=h_["short"], module=stmt["comparator"].get("solution_module") or "")) + "</li>")
        holes_html = f'<h3 class="h3" id="h-holes">{esc(C("statement.holes_heading"))} <span class="count">{len(holes)}</span></h3><p class="intro">{ctext(C("statement.holes_intro"))}</p><ul class="holes">{"".join(items)}</ul><p class="leanc__note">{ctext(LW("panel.holes_note"))}</p>'
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
    main = (lrec or summ).get("main_result")
    main_line = C("statement.main_yes") if main else C("statement.main_no", id=(fid or "f:")[2:])
    # supporting material
    sol_html = ", ".join(f'<a class="ext" href="{esc(x["url"])}" rel="noopener"><code>{esc(x["file"])}</code></a>' for x in sol) or f'<code>{esc(stmt["comparator"].get("solution_module") or "")}</code>'
    nm = stmt["non_mathlib_imports"]
    facts = [
        (C("statement.file_label"), f'<a class="ext" href="{esc(stmt["url"])}" rel="noopener"><code>{esc(stmt["file"])}</code></a>'),
        (C("statement.main_key"), esc(main_line)),
        (C("statement.solution"), sol_html),
        (C("statement.permitted_axioms"), ", ".join(f"<code>{esc(a)}</code>" for a in stmt["comparator"]["permitted_axioms"]) + f'<span class="dl__note">{esc(C("statement.permitted_axioms_note"))}</span>'),
        (C("statement.imports"), ", ".join(f"<code>{esc(a)}</code>" for a in stmt["imports"])),
        (C("statement.non_mathlib"), ", ".join(f"<code>{esc(a)}</code>" for a in nm) if nm else esc(C("statements.none"))),
        (C("statement.vocab_key"), esc(vocab_text(stmt))),
        (C("statement.lines"), num(stmt["statement_lines"])),
        (C("statement.nanoda_key"), esc(C("statement.nanoda_yes") if (lrec or summ).get("nanoda_enabled") else C("statement.nanoda_no"))),
    ]
    # Terms a newcomer meets here for the first time carry their glossary definition.
    _terms = {C("statement.permitted_axioms"): ("axioms", C("statement.permitted_axioms")),
              C("statement.non_mathlib"): ("mathlib", C("statement.non_mathlib")),
              C("statement.nanoda_key"): ("nanoda", C("statement.nanoda_key"))}
    def _dt(k):
        tid, text = _terms.get(k, (None, k))
        return term_link(tid, esc(text)) if tid in GLOSSARY else esc(k)
    facts = [(k, v + (f'<span class="dl__note">{esc(LW("facts.solution_note"))}</span>' if k == C("statement.solution") else ""))
             for k, v in facts]
    dl = "".join(f"<div><dt>{_dt(k)}</dt><dd>{v}</dd></div>" for k, v in facts)
    paper_cols = []
    for slug in stmt.get("papers") or []:
        m = MS.get(slug)
        if not m:
            continue
        cv = TexConv(m, root)
        heads = headline_statements(m)
        inner = "".join(render_paper_statement(m, st, root, cv, "pst") for st in heads) or f'<p class="muted">{esc(C("family.no_headline"))}</p>'
        paper_cols.append(f'<div class="sbs__paper"><h3 class="h3"><a href="{root}papers/{esc(slug)}.html">{ms_title_html(m)}</a></h3>{inner}</div>')
    import lean_render  # the whole file, every name the source text resolves linked, beside "What you must check"
    file_section = lean_render.file_section(stmt, commit=COMMIT, root=root)
    checks = CONTRIB["checks"].get(sid, [])
    replays = CONTRIB["replays"].get(sid, [])
    checks_html = "".join(f'<li><strong>{esc(c["name"])}</strong>{(": " + esc(c["verdict"])) if c.get("verdict") else ""}{(", " + esc(c["date"])) if c.get("date") else ""} <a class="ext small" href="{esc(REPO + "/blob/main/" + c["path"])}" rel="noopener">{esc(C("statement.record_link"))}</a></li>' for c in checks)
    replays_html = "".join(f'<li><strong>{esc(c["name"])}</strong>{(": " + esc(c["verdict"])) if c.get("verdict") else ""}{(", " + esc(c["date"])) if c.get("date") else ""} <a class="ext small" href="{esc(REPO + "/blob/main/" + c["path"])}" rel="noopener">{esc(C("statement.record_link"))}</a></li>' for c in replays)
    replay_url = issue_url("replay", C("issues.replay", statement=sid), statement=sid)
    suggest = suggest_url(page_url, label, statement_label=label)
    # The breadcrumb is the page's ancestry and ends at the family, its parent; the
    # heading below names the page itself. Without a family it keeps the page's name.
    # Map / Subject / Family N: short title / Lean statement Name (the breadcrumb grammar).
    trail_items = family_crumbs(fam, root) if fam else []
    trail_items.append((esc(LW("trail.lean")) + f' <span translate="no">{camel_breaks(sid)}</span>', None))
    # Under the heading: the source file as one typed link (its role, then its name; the
    # full path in its title and in the facts list below) and the map as another, each a
    # whole unit when the line wraps; then the family number and the catalogue's word,
    # which the breadcrumb's family name does not repeat.
    role = "challenge" if stmt["file"].startswith("lean/ComparatorChallenges/") else "other"
    src_link = (f'<a class="ext phead__src" href="{esc(stmt["url"])}" rel="noopener" title="{esc(stmt["file"])}">'
                f'{esc(LW("page.source_role." + role))} <code>{camel_breaks(stmt["file"].rsplit("/", 1)[-1])}</code></a>')
    map_link = f'<a class="phead__map" href="{root}index.html#o=l:{quote(sid)}">{esc(C("words.show_on_map"))}</a>'
    meta = []
    if fam and main:  # the catalogue's sentence for a supporting statement names the family itself
        meta.append(LW("page.family_number", id=fam["id"]))
    others = [f for f in (summ.get("family_ids") or [])[1:]]
    if others:
        meta.append(LW("page.also_in", families=", ".join(o[2:] for o in others)))
    reasons = REVIEW_REASONS.get(sid) or []
    reasons_html = (f'<div class="note"><p class="note__h">{esc(C("statement.reasons_heading"))}</p><ul class="rq__why">' + "".join(f'<li class="md-math">{ctext(t)}</li>' for t in reasons) + '</ul></div>') if reasons else ""
    problems = findings_for(sid=sid, kinds={'error-reported', 'correction', 'replay-fail'})
    more_finds = findings_for(sid=sid, kinds={'explanation', 'commentary', 'follow-up-result'})
    human_name = summ.get("name")
    # Under the heading: the release's own name for it (when it differs) and the fully
    # qualified name of each checked theorem, each with a Copy button.
    thm_names = stmt["comparator"]["theorem_names"] or stmt["comparator"].get("definition_names") or stmt["theorems"][:1]
    name_items = "".join(f'<span class="phead__thm"><code translate="no">{camel_breaks(n_)}</code> '
                         f'<button class="btn btn--quiet copy" type="button" data-copy-text="{esc(n_)}" aria-label="{esc(LW("page.copy_name") + " " + n_)}">{esc(LW("page.copy_name"))}</button></span>'
                         for n_ in thm_names)
    target_kind = "definition" if definition_only else "theorem"
    target_label = LW(f"page.{target_kind}_name" + ("s" if len(thm_names) != 1 else ""))
    subtitle = ((f'<p class="phead__sub"><span class="md-math">{esc(human_name)}</span></p>' if human_name and human_name != label else "")
                + (f'<p class="phead__sub phead__thms"><span class="phead__thmk">{esc(target_label)}</span> {name_items}</p>' if thm_names
                   else f'<p class="phead__sub"><code>{camel_breaks(sid)}</code></p>'))
    runs_section = lean_runs_html(lrec, root) if lrec else f'<p class="muted">{esc(LW("runs.none_recorded"))}</p>'
    groups_section = lean_group_cards(fam, fid, doc, lrec, root, definition_only)
    next_section = lean_next_html(fam, sid, paper_rec, backend_printed(paper_rec, paper_st) if paper_st else None, lrec, stmt, root)
    left_html = "".join(f"<li>{esc(t)}</li>" for t in left_items)
    # Contributed comparisons and runs are shown when Atlas holds some; their absence is
    # not announced (Atlas collects from public sources and asks readers for nothing).
    records_html = ""
    if checks or replays:
        records_html = ('<div class="left-records">'
                        + (f'<div><h3 class="h3">{esc(C("statement.checks_heading"))}</h3><ul>{checks_html}</ul></div>' if checks else "")
                        + (f'<div><h3 class="h3">{esc(C("statement.replays_heading"))}</h3><ul>{replays_html}</ul></div>' if replays else "")
                        + '</div>')
    # The contents rail beside the page on a wide screen: each section in reading order,
    # each a question the section answers.
    # The contents rail beside the page on a wide screen, in the page's order: the Lean
    # beside the paper, what the groups found, then the detail a reader may ask for.
    toc_items = [("h-glance", LW("toc.glance")), ("h-groups", LW("toc.groups")), ("h-lean-notes", LW("toc.lean")),
                 ("h-pairing", LW("toc.claim")), ("h-runs", LW("toc.runs")), ("h-checks", LW("toc.checks")),
                 ("h-next", LW("toc.next")), ("h-file", LW("toc.file")), ("h-share", LW("toc.share"))]
    toc = (f'<nav class="lxs-toc" aria-labelledby="lxs-toc-h"><p class="lxs-side__h" id="lxs-toc-h">{esc(LW("toc.heading"))}</p><ol>'
           + "".join(f'<li><a href="#{i}">{esc(t)}</a></li>' for i, t in toc_items) + '</ol></nav>')
    runs_heading = LW("page.formal_heading" + ("_def" if definition_only else ""))
    sheet_state = {"producer-cited-association": "cited", "producer-declared-binding": "cited"}.get(pinfo["state"], "candidate") if paper_st else "none"
    lean_side = LW("sheet.lean_h" + ("_def" if definition_only else ""))
    # OpenAI's note and the symbol key beside it; the definitions, holes and axioms follow.
    reading_pair = (f'<div class="lxb-notes__cols"><div class="lxb-notes__a">{plain_reading}</div><div class="lxb-notes__b">{symbols}</div></div>'
                    if plain_reading.strip() and symbols.strip() else plain_reading + symbols)
    notes_body = reading_pair + defs + holes_html + axiom
    body = f"""<div class="frame page page--lean">
{trail(root, trail_items)}
{sibling_nav("lean", lean_siblings(sid, root))}
<div class="lxs">
<header class="phead lxs-head">
 <p class="phead__kicker">{esc(LW('page.kicker'))}</p>
 <h1 class="phead__title md-math" aria-label="{esc(tex_plain(label))}">{esc(label)}</h1>
 {subtitle}
 <p class="phead__where">{src_link}{map_link}<span class="phead__meta">{esc(" ".join(meta))}</span></p>
 <p class="phead__what">{ctext(LW('page.what' + ('_def' if definition_only else '')))}</p>
</header>
<div class="lxs-main">
<section class="band band--tight lxb" aria-labelledby="h-glance">
 <h2 class="vh" id="h-glance">{esc(LW('sheet.heading'))}</h2>
 <div class="lxb-pair lxb-pair--{sheet_state}">
  <div class="lxb-paper">
   <h2 class="lxb-side lxb-side--paper" id="h-claim">{esc(LW('sheet.paper_h' if paper_st else 'sheet.paper_h_none'))}</h2>
   {paper_side}
  </div>
  <div class="lxb-lean">
   <h2 class="lxb-side lxb-side--lean" id="h-lean-read">{ctext(lean_side)} <button type="button" class="help-q" data-help="lean" aria-label="{esc(LW('page.lean_help_label'))}">?</button></h2>
   <div class="lean__tools"><button class="btn btn--quiet copy" type="button" data-copy-text="{esc(lean_copy)}">{esc(LW('page.copy_lean'))}</button><pre class="lean lean--snippet lean--read lxb-code"><code>{snippet_full}</code></pre></div>
   <p class="lxb-note">{ctext(lean_note)}</p>{proof_sources_html(fid, sid) if not definition_only and not stmt["declares_axiom"] else ""}
  </div>
  {join_line}
 </div>
</section>
{('<section class="band band--tight"><div class="note note--warn"><p class="note__h">' + esc(C('sources.problems_heading')) + '</p>' + findings_list(problems, root) + '</div></section>') if problems else ''}
{groups_section}
{('<section class="band band--tight lxb-notes" aria-labelledby="h-lean-notes"><h2 class="h2" id="h-lean-notes">' + esc(LW('sheet.notes_heading' + ('_def' if definition_only else ''))) + '</h2>' + notes_body + '</section>') if notes_body.strip() else '<span id="h-lean-notes" class="anchor-alias"></span>'}
{pairing_section}
<section class="band band--tight" aria-labelledby="h-runs">
 <h2 class="h2" id="h-runs">{esc(runs_heading)}</h2>
 {runs_section}
 <div class="runs-notes">{comparator_box_html(stmt)}</div>
</section>
<section class="band band--tight explain-box" aria-labelledby="h-checks">
 <h2 class="h2" id="h-checks">{esc(LW('left.heading'))}</h2>
 <p class="intro">{esc(LW('left.intro'))}</p>
 <ul class="left">{left_html}</ul>
 {records_html}
 {('<h3 class="h3">' + esc(C('sources.statement_more')) + '</h3>' + findings_list(more_finds, root)) if more_finds else ''}
 {reasons_html}
</section>
{next_section}
<section class="band supporting" aria-labelledby="h-support">
 <h2 class="h2" id="h-support">{esc(C('statement.support_heading'))}</h2>
 {file_section}
 <details class="more" id="sbs"><summary><span class="h3" id="h-sbs">{esc(C('statement.paper_heading'))}</span></summary><p class="intro">{esc(C('statement.paper_intro'))}</p><div class="sbs__all">{''.join(paper_cols)}</div></details>
</section>
<section class="band band--card" aria-labelledby="h-share">
 <h2 class="h2" id="h-share">{esc(C('statement.card_heading'))}</h2>
 <p class="intro">{esc(C('statement.card_intro'))}</p>
 {card}
 <p class="card-tools"><button class="btn btn--ghost copy" type="button" data-copy-text="{esc(page_url)}">{esc(C('statement.copy_link'))}</button></p>
</section>
</div>
<aside class="lxs-side" aria-label="{esc(LW('toc.side_label'))}">
{toc}
<section class="lxs-facts" aria-labelledby="h-facts"><h2 class="lxs-side__h" id="h-facts">{esc(C('statement.facts_heading'))}</h2><dl class="dl">{dl}</dl></section>
</aside>
</div>
</div>
{macros_script(list(dict.fromkeys(([paper_ms['id']] if paper_ms else []) + list(stmt.get('papers') or []))))}"""
    desc = f"{tex_plain(label)}. " + (f"{human_name}. " if human_name and human_name != label else "") + main_line + " " + cap(evidence.say("pairing_short." + pinfo["state"])) + "."
    # Social image: the generic card unless this build renders the statement's own card
    # successfully; main() swaps the block in only after checking the file it produced.
    generic = generic_og_meta()
    own = og_meta(BASE_URL + f"og/{sid}.png", C("statement.og_alt", label=label))
    OG_DONE[sid] = (generic, own)
    lean_head = f'<link rel="stylesheet" href="{root}assets/{asset_v("lean.css")}">\n<script defer src="{root}assets/{asset_v("lean.js")}"></script>'
    write_page(rel, page(rel, f"{tex_plain(label)} (Lean)", desc, body, og_block=generic, page_type="article", extra_head=lean_head))


# ------------------------------------------------------------------- home


def build_home():
    """index.html is the release's front door, written by scripts/build_universe.py; it is
    registered here because the sitemap is written before that script runs. The tile
    map that stood at tiles.html is retired: the address now sends a reader to the
    front door, with a link for browsers that ignore the refresh."""
    PAGES.append("index.html")
    (OUT / "tiles.html").write_text(
        '<!doctype html>\n<html lang="en-GB"><head><meta charset="utf-8">'
        '<meta http-equiv="refresh" content="0; url=index.html"><link rel="canonical" href="' + esc(BASE_URL) + '">'
        f'<meta name="robots" content="noindex"><title>{esc(C("site.name"))}</title></head>'
        f'<body><p><a href="index.html">{esc(C("home.tiles_moved"))}</a></p></body></html>\n', encoding="utf-8")


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


def quiet_none(label: str) -> str:
    """An empty table cell: a dash to the eye and its meaning to a screen reader, so a long
    list does not repeat the same sentence on every row."""
    return f'<span class="cell__none cell__dash"><span aria-hidden="true">\u2013</span><span class="vh">{esc(label)}</span></span>'


def head_term(tid, label_html: str) -> str:
    """A column head or filter label that is also its glossary term, when the glossary
    has one (the same link and hover as [[id|text]] in copy)."""
    return term_link(tid, label_html) if tid and tid in GLOSSARY else label_html


def sort_head(i: int, typ: str, label: str, tid=None) -> str:
    """A sortable column head. With a glossary term, the words link the term and the
    arrow beside them sorts; otherwise the whole head is the sort button."""
    if tid and tid in GLOSSARY:
        return (f'{term_link(tid, esc(label))}<button type="button" class="sort sort--arrow" data-sort="{i}" data-type="{typ}" '
                f'aria-label="{esc(C("explain.sort_by", col=label))}"></button>')
    return f'<button type="button" class="sort" data-sort="{i}" data-type="{typ}">{esc(label)}</button>'


def tip_attr(text: str | None, above=False) -> str:
    """A column head's or filter's plain explanation, shown by atlas.js beside it on hover
    and on focus (the same popover as a glossary word), and read as its description."""
    if not text:
        return ""
    return f' data-tip="{esc(text)}"' + (' data-tip-place="above"' if above else "")


def reader_term(source: str):
    """The glossary term for an outside reader ("mathvet", "cert-machine"), if there is one."""
    return source if source in GLOSSARY else None


def build_explain():
    """The Families list: all of the release's families as rows, each state said in words
    from the backend's records (scripts/evidence.py): papers, Lean statements, each
    outside reader's own term with a plain gloss, accepted re-runs, checks by another
    method, problems reported and explanations. Complete and readable without
    JavaScript; with it, filters by discipline and evidence and sortable columns make
    the list a tool."""
    rel = "explain.html"
    r = RD()
    evs = evidence.all_families(r)
    counts = dict(evidence.legend_counts(evs))
    say_e = evidence.say
    # The map's colour for each family, by the map's own rule, so that every count in
    # the map's colour key is reproduced here by one filter (build_universe.KEY_FILTERS).
    import build_universe as BU
    colour_words = json.loads((SITE / "copy_universe.json").read_text(encoding="utf-8"))["key"]
    # The two readers' names, in the order the evidence vocabulary sets.
    reader_names = {}
    for ev in evs:
        for rd in ev.readers:
            if rd.tone != "none" and rd.name and rd.name != rd.source:
                reader_names.setdefault(rd.source, rd.name)
    order = evidence.reader_order(set(reader_names))[:2]
    # "Carlos Toledo, cert-machine" is "Carlos Toledo’s cert-machine" in prose and
    # "cert-machine" in a column head; "MathVet" is "MathVet" in both.
    short_name = {s_: reader_names.get(s_, s_).split(", ")[-1] for s_ in order}
    prose_name = {s_: ("’s ".join(reader_names[s_].split(", ", 1)) if ", " in reader_names.get(s_, "") else reader_names.get(s_, s_)) for s_ in order}
    disc = {d["id"]: (slugify(d["name"]), d["name"]) for d in r.universe.get("disciplines") or []}
    status_counts = Counter()
    rows = []
    for ev in evs:
        fid = ev.num
        f = FAM.get(fid)
        st, ex = family_exposition_status(fid)
        status_counts[st] += 1
        dslug, dname = disc.get(ev.discipline, ("", ""))
        classes = []
        if ev.has_lean:
            classes.append("lean")
            if ev.agreement == "disagree":
                classes.append("disagree")
            # how its Lean statements are paired, one class per kind present (scripts/evidence.py)
            classes += list(ev.pairing_classes)
        else:
            classes.append("nolean")
        if ev.checks:
            classes.append("ring")
        others = ev.community_count("explanation")
        problems = ev.community_count("error-reported") + ev.community_count("correction")
        if others:
            classes.append("explained_by_others")
        if problems:
            classes.append("problems_reported")
        # the same records that write the row's edition note
        if ev.withdrawn:
            classes.append("has_withdrawn")
        if ev.editions:
            classes.append("has_edition")
        for key in ("has_withdrawn", "has_edition"):
            if key in classes:
                counts[key] = counts.get(key, 0) + 1
        tone = BU.tone_class(ev)
        counts["t_" + tone] = counts.get("t_" + tone, 0) + 1
        # papers elsewhere in the release that cite one of the family's papers, by the
        # rule the family page's "Cited by" list uses
        own = set(f["manuscripts"]) if f else set()
        citing = {c for slug in own for c in (MS.get(slug, {}).get("cited_by_in_collection") or []) if c not in own}
        cited_n = len(citing)
        title = fam_title_html(f) if f else esc(ev.name)
        name_plain = tex_plain(f["title"]) if f else ev.name
        # papers
        extra = []
        if ev.editions:
            extra.append(C("explain.editions_1") if ev.editions == 1 else C("explain.editions_n", n=say(ev.editions)))
        if ev.withdrawn:
            extra.append(C("explain.withdrawn_1") if ev.withdrawn == 1 else C("explain.withdrawn_n", n=say(ev.withdrawn)))
        papers = num(ev.papers)
        editions = f'<span class="cell__sub">{esc(cap(", ".join(extra)))}</span>' if extra else ""
        # Lean statements and re-runs
        k = len(ev.lean)
        if k:
            lean_cell = num(k)
            rerun = sum(1 for l in ev.lean if l.accepted)
            proof = "all" if rerun == k else "some" if rerun else "none"
            counts["p_" + proof] = counts.get("p_" + proof, 0) + 1
            runs_cell = f'{esc(C("explain.runs_of", k=num(rerun), n=num(k)))}'
        else:
            lean_cell = quiet_none(C("explain.no_lean_label"))
            runs_cell = quiet_none(C("explain.no_lean_label"))
            rerun = -1
            proof = "nolean"
        # each reader's own term, with a plain gloss under it
        rcells = []
        tones = {}
        for side, src in enumerate(order):
            rd = next((x for x in ev.readers if x.source == src), None)
            tones[side] = rd.tone if rd else "none"
            if not k:
                rcells.append(f'<td class="t-reader" data-v="">{quiet_none(C("explain.no_lean_label"))}</td>')
            elif rd is None or rd.tone == "none" or not rd.term:
                rcells.append(f'<td class="t-reader" data-v="~"><span class="cell__none">{esc(C("explain.not_read"))}</span></td>')
            else:
                rcells.append(f'<td class="t-reader" data-v="{esc(rd.tone)}"><span class="cell__plain">{esc(cap(say_e("tone_short." + rd.tone)))}</span>'
                              f'<span class="cell__sub">{esc(C("explain.their_term", term=rd.term))}</span></td>')
        agree = ""
        if k and ev.agreement == "disagree":
            agree = f'<span class="cell__flag">{esc(C("explain.disagree_flag"))}</span>'
        checks = ", ".join(say_e("check_kind." + c) for c in ev.checks if c in evidence.WORDS["check_kind"])
        checks = cap(checks) if checks else ""
        checks_cell = esc(checks) if checks else quiet_none(C("explain.checks_none"))
        # explanations: what there is to read first (a reviewed explanation for the atlas,
        # explanations by others, reported problems), then the state of the atlas's own
        # explanation, qualified, then the offer to write one
        rev = reviewed_explanations(fid)
        # A family with no explanation yet says so quietly; the page invites explanations once.
        status = [quiet_none(C("explain.status_none"))] if st == "none" else [f'<span class="st st--{st}">{esc(C("explain.status_" + st))}</span>']
        if ex:
            status.append(f'<span class="cell__sub">{esc(", ".join(e["name"] for e in ex))}</span>')
        reading = []
        if others:
            reading.append(f'<a class="cell__sub" href="families/{fid}.html#h-explain">'
                           f'{esc(cap(C("explain.others_1") if others == 1 else C("explain.others_n", n=say(others))))}</a>')
        if problems:
            reading.append(f'<a class="cell__sub cell__warn" href="families/{fid}.html#h-problems">'
                           f'{esc(cap(C("explain.problems_1") if problems == 1 else C("explain.problems_n", n=say(problems))))}</a>')
        if rev:
            expl = status + reading + [f'<a class="cell__sub" href="{explanation_rel(rev[0], fid)}">{esc(C("explain.read"))}</a>']
        elif st == "none":
            expl = reading or status
        else:
            expl = reading + status
        rows.append(
            f'<tr id="f-{fid}" data-q="{esc((fid + " " + name_plain + " " + dname).lower())}" data-d="{dslug}" data-c="{" ".join(classes)}" data-l="{tones.get(0, "none") if k else "nolean"}" '
            f'data-r="{tones.get(1, "none") if k else "nolean"}" data-s="{st}" data-t="{tone}" data-p="{proof}">'
            f'<td class="t-num t-id" data-v="{fid}">{fid}</td>'
            f'<td class="t-title" data-v="{esc(name_plain.lower())}"><a href="families/{fid}.html">{title}</a>'
            f'<span class="cell__sub t-disc-inline">{esc(dname)}</span>{editions}{agree}</td>'
            f'<td class="t-disc" data-v="{esc(dname)}">{esc(dname)}</td>'
            f'<td class="t-num" data-v="{ev.papers}" data-label="{esc(C("explain.col_papers"))}">{papers}</td>'
            f'<td class="t-num t-lean" data-v="{k}" data-label="{esc(C("explain.col_lean"))}">{lean_cell}</td>'
            f'<td class="t-num t-cited" data-v="{cited_n}" data-label="{esc(C("explain.col_cited"))}">'
            f'{num(cited_n) if cited_n else quiet_none(C("explain.cited_none"))}</td>'
            + "".join(c.replace('<td class="t-reader"', f'<td class="t-reader" data-label="{esc(C("explain.col_reader", name=short_name[order[i]]))}"', 1)
                      for i, c in enumerate(rcells)) +
            f'<td class="t-num" data-v="{rerun}" data-label="{esc(C("explain.col_runs"))}">{runs_cell}</td>'
            f'<td data-v="{esc(checks)}" data-label="{esc(C("explain.col_checks"))}">{checks_cell}</td>'
            f'<td data-v="{st}" data-label="{esc(C("explain.col_status"))}">{"".join(expl)}</td></tr>')
    # Filters, in one row: discipline, evidence, each reader's finding, and words.
    def select(fid_, label, key, opts, term=None, tip=None):
        return (f'<div class="filters__g"{tip_attr(tip, above=True)}><label class="filters__h" for="{fid_}">{head_term(term, esc(label))}</label>'
                f'<select class="select" id="{fid_}" data-filter="{key}">{"".join(opts)}</select></div>')
    dopts = [f'<option value="">{esc(C("explain.all_disciplines"))}</option>']
    for d in r.universe.get("disciplines") or []:
        dopts.append(f'<option value="{slugify(d["name"])}">{esc(d["name"])} ({num(len(d.get("family_ids") or []))})</option>')
    eopts = [f'<option value="">{esc(C("explain.all_evidence"))}</option>']
    # Disagreement is offered once, as the colour filter's "The groups disagree" (t=split
    # selects exactly the rows classed disagree); an old ?c=disagree link maps to it in atlas.js.
    for group, keys in (("lean", ("lean", "nolean")), ("pairing", evidence.PAIRING_CLASSES),
                        ("checks", ("ring",)), ("explanations", ("explained_by_others",)), ("problems", ("problems_reported",)),
                        ("papers", ("has_withdrawn", "has_edition"))):
        # An option that would lead to an empty list is not offered.
        def ev_label(key):
            return say_e("pairing_class." + key) if group == "pairing" else C("explain.ev_" + key)
        shown_opts = "".join(f'<option value="{key}">{esc(ev_label(key))} ({num(counts.get(key, 0))})</option>'
                             for key in keys if counts.get(key, 0))
        if shown_opts:
            eopts.append(f'<optgroup label="{esc(C("explain.evgroup_" + group))}">{shown_opts}</optgroup>')
    topts = [f'<option value="">{esc(C("explain.colour_any"))}</option>'] + [
        f'<option value="{t_}">{esc(C("explain.colour_split") if t_ == "split" else colour_words[t_])} ({num(counts["t_" + t_])})</option>'
        for t_ in BU.TONE_ORDER if counts.get("t_" + t_)]
    popts = [f'<option value="">{esc(C("explain.proof_any"))}</option>'] + [
        f'<option value="{p_}">{esc(C("explain.proof_" + p_))} ({num(counts["p_" + p_])})</option>'
        for p_ in ("all", "some", "none") if counts.get("p_" + p_)]
    selects = [select("ff-d", C("explain.filter_discipline"), "d", dopts, tip=C("explain.tips.f_discipline")),
               select("ff-c", C("explain.filter_evidence"), "c", eopts, tip=C("explain.tips.f_evidence")),
               select("ff-t", C("explain.filter_colour"), "t", topts, term="map-colours", tip=C("explain.tips.f_colour")),
               select("ff-p", C("explain.filter_proof"), "p", popts, term="rerun", tip=C("explain.tips.f_proof"))]
    for side, src in enumerate(order):
        opts = [f'<option value="">{esc(C("explain.reader_any"))}</option>']
        for tone in evidence.TONES:
            n = counts.get(("left_" if side == 0 else "right_") + tone, 0)
            if not n:
                continue   # an option that leads to an empty list is not offered
            opts.append(f'<option value="{tone}">{esc(cap(say_e("tone_short." + tone)))} ({num(n)})</option>')
        selects.append(select(f"ff-{side}", C("explain.filter_reader", name=short_name[src]), "l" if side == 0 else "r", opts,
                              term=reader_term(src), tip=C("explain.tips.f_reader", name=short_name[src])))
    selects.append(f'<div class="filters__g filters__g--q"><label class="filters__h" for="ff-q">{esc(C("explain.filter_words"))}</label>'
                   f'<input class="filter-input" id="ff-q" type="search" data-filter="q" autocomplete="off" spellcheck="false" placeholder="{esc(C("explain.filter_words_ph"))}">'
                   f'<a class="filters__all" href="index.html" data-search-all="index.html">{esc(C("explain.search_all"))}</a></div>')
    sort_cols = [("id", "n"), ("result", "s"), ("discipline", "s"), ("papers", "n"), ("lean", "n"), ("cited", "n")]
    col_terms = {"result": "family", "lean": "challenge"}
    heads = []
    for i, (key, typ) in enumerate(sort_cols):
        cls = ' class="t-num"' if typ == "n" else (' class="t-disc"' if key == "discipline" else "")
        heads.append(f'<th scope="col"{cls} aria-sort="{"ascending" if key == "id" else "none"}"{tip_attr(C("explain.tips." + key))}>'
                     f'{sort_head(i, typ, C("explain.col_" + key), col_terms.get(key))}</th>')
    for src in order:
        heads.append(f'<th scope="col" class="t-reader"{tip_attr(C("explain.tips.reader", name=short_name[src]))}>{head_term(reader_term(src), esc(C("explain.col_reader", name=short_name[src])))}</th>')
    runs_i = len(sort_cols) + len(order)
    heads.append(f'<th scope="col" class="t-num" aria-sort="none"{tip_attr(C("explain.tips.runs"))}>{sort_head(runs_i, "n", C("explain.col_runs"), "rerun")}</th>')
    heads.append(f'<th scope="col"{tip_attr(C("explain.tips.checks"))}><span class="th-tip" tabindex="0">{esc(C("explain.col_checks"))}</span></th>')
    heads.append(f'<th scope="col"{tip_attr(C("explain.tips.status"))}><span class="th-tip" tabindex="0">{esc(C("explain.col_status"))}</span></th>')
    # On a phone the column heads are hidden; this menu sorts the list instead.
    sort_menu = [("0:n:ascending", "sort_id"), ("1:s:ascending", "sort_name"), ("2:s:ascending", "sort_discipline"),
                 ("3:n:descending", "sort_papers"), ("4:n:descending", "sort_lean"), ("5:n:descending", "sort_cited"),
                 (f"{runs_i}:n:descending", "sort_runs")]
    sort_select = (f'<div class="filters__g filters__g--sort"><label class="filters__h" for="ff-sort">{esc(C("explain.sort_label"))}</label>'
                   f'<select class="select" id="ff-sort" data-sort-table="families-table">'
                   + "".join(f'<option value="{v}">{esc(C("explain." + k))}</option>' for v, k in sort_menu) + "</select></div>")
    readers_note = C("explain.readers_note", left=prose_name[order[0]], right=prose_name[order[1]] if len(order) > 1 else "")
    body = f"""<div class="frame page page--families">
{section_trail("", "explain")}
<header class="phead phead--compact">
 <h1 class="phead__title">{esc(C('explain.title'))}</h1>
 <p class="phead__lede">{esc(C('explain.lede', families=NUM('families')))}</p>
 <p class="phead__invite">{C('explain.more_lists', cited='<a href="citations-within.html">' + esc(C('explain.cited_short')) + '</a>', outside='<a href="references-outside.html">' + esc(C('explain.outside_short')) + '</a>')}</p>
 </header>
<section class="band band--table" aria-labelledby="h-list">
<h2 class="h2 vh" id="h-list">{esc(C('explain.list_heading'))}</h2>
<div class="filters filters--families" data-filter-families="families-table">
 <button type="button" class="btn btn--ghost filters__toggle" aria-expanded="false" aria-controls="families-filters">{esc(C('explain.filter_toggle'))}</button>
 {sort_select}
 <div class="filters__panel" id="families-filters">{''.join(selects)}</div>
 <div class="filters__status">
  <p class="filters__n" aria-live="polite" data-shown-template="{esc(C('explain.shown', n='{n}', total=NUM('families')))}" data-criteria-lead="{esc(C('explain.criteria_lead'))}">{esc(C('explain.shown', n=NUM('families'), total=NUM('families')))}</p>
  <button type="button" class="btn btn--quiet filters__reset" hidden>{esc(C('explain.reset'))}</button>
 </div>
 <p class="filters__note">{esc(readers_note)} {esc(C('explain.counts_note'))}</p>
</div>
<p class="filters__empty" hidden>{esc(C('explain.none_match'))}</p>
<div class="table-wrap"><table class="tbl tbl--sortable tbl--families" id="families-table">
 <caption class="vh">{esc(C('explain.caption'))}</caption>
 <thead><tr>{''.join(heads)}</tr></thead>
 <tbody>{''.join(rows)}</tbody>
</table></div>
</section>
{review_queue_html("")}
</div>"""
    write_page(rel, page(rel, C("explain.title"), C("explain.lede", families=NUM("families")), body, current="explain"))


def build_statements_table():
    """statements.html: every Lean statement with what a reviewer needs beside it: the
    paper statement it is paired with (and how), what the outside readers found about
    its family, and how many groups report re-running it; filters by discipline, pairing
    and each reader's finding; on a phone, one card per statement with a sort menu."""
    rel = "statements.html"
    r = RD()
    T = lambda k, **kw: LW("table." + k, **kw)
    reader_names = {}
    evs = {}
    for s in STATEMENTS:
        for fid_ in s.get("families") or []:
            if fid_ not in evs:
                evs[fid_] = evidence.family_evidence(r, "f:" + fid_)
                for rd in evs[fid_].readers:
                    if rd.tone != "none" and rd.name and rd.name != rd.source:
                        reader_names.setdefault(rd.source, rd.name)
    order = evidence.reader_order(set(reader_names))[:2]
    short_name = {s_: reader_names.get(s_, s_).split(", ")[-1] for s_ in order}
    disc_slug = {}
    counts = Counter()
    rows = []
    for s in STATEMENTS:
        fid = s["families"][0] if s.get("families") else None
        f = FAM.get(fid)
        di = DISC_OF.get(fid)
        dname = DISCIPLINES[di]["name"] if di is not None else ""
        dslug = slugify(dname) if dname else ""
        disc_slug[dslug] = dname
        label = curly_prose((s.get("labels") or [s["id"]])[0])
        # the pairing, as lean_pairing reads it
        bfid, doc, lrec = lean_family_doc(s["id"])
        pinfo = lean_pairing(doc, s["id"]) if doc else {"state": "unavailable", "targets": [], "evidence": "none"}
        ev_kind = pinfo.get("evidence", "none")
        if pinfo["state"] == "producer-declared-binding":
            ev_kind = "declared"
        elif pinfo["state"] == "producer-cited-association":
            ev_kind = "cited"
        refs, sort_v = [], ""
        for t in pinfo.get("targets") or []:
            m, st, rec = ms_statement(doc, t)
            if not st:
                continue
            name = backend_printed(rec, st)
            href = (rec or {}).get("reading_page") or (f"papers/{quote(m['id'])}.html" if m else "")
            refs.append(f'<a href="{esc(href)}">{esc(name)}</a><span class="cell__sub tex-auto">{ms_title_html(m)}</span>')
            sort_v = sort_v or (tex_plain(m["title"]) + " " + name).lower()
        how = T("pair." + ev_kind)
        pair_cell = ("".join(refs) + f'<span class="cell__sub">{esc(how)}</span>') if refs else f'<span class="cell__none">{esc(how)}</span>'
        classes = [ev_kind]
        if len(refs) > 1:
            classes.append("several")
        if s["main_result"]:
            classes.append("main")
        # what the outside readers found about the family, in words
        ev = evs.get(fid)
        tones, rcells = {}, []
        for side, src in enumerate(order):
            rd = next((x for x in (ev.readers if ev else []) if x.source == src), None)
            tone = rd.tone if rd and rd.term else "none"
            tones[side] = tone
            counts[(side, tone)] += 1
            cell = (f'<span class="cell__plain">{esc(cap(evidence.say("tone_short." + tone)))}</span>'
                    f'<span class="cell__sub">{esc(T("their_term", term=rd.term))}</span>') if tone != "none" else f'<span class="cell__none">{esc(T("not_read"))}</span>'
            rcells.append(f'<td class="t-reader" data-v="{esc(tone if tone != "none" else "~")}" data-label="{esc(T("col_reader", name=short_name[src]))}">{cell}</td>')
        acc = len((lrec or {}).get("accepted_current_sources") or [])
        counts[ev_kind] += 1
        # notes: definition holes, imports outside Mathlib, a declared axiom
        nh = len(s["comparator"].get("definition_names") or [])
        nm = s["non_mathlib_imports"]
        notes = []
        if nh:
            notes.append(T("note_holes_one") if nh == 1 else T("note_holes_many", n=num(nh)))
        if nm:
            notes.append(T("note_imports", names=", ".join(nm[:3]) + ("…" if len(nm) > 3 else "")))
        if s.get("declares_axiom"):
            notes.append(T("note_axiom"))
        notes_html = "".join(f'<span class="cell__sub">{esc(n_)}</span>' for n_ in notes)
        q = " ".join([label, s["id"], tex_plain(f["title"]) if f else "", dname, how]).lower()
        # the two groups on this statement's family, and the Comparator runs reported for it
        fev = evs.get(fid)
        groups = "disagree" if fev and fev.agreement == "disagree" else ("agree" if fev and fev.agreement == "agree" else "")
        if groups:
            counts["g_" + groups] += 1
        proof = "accepted" if acc else ("other" if (lrec or {}).get("runs") else "none")
        counts["p_" + proof] += 1
        rows.append(
            f'<tr data-q="{esc(q)}" data-d="{dslug}" data-c="{" ".join(classes)}" data-l="{tones.get(0, "none")}" data-r="{tones.get(1, "none")}" data-g="{groups}" data-p="{proof}">'
            f'<td class="t-title" data-v="{esc(label.lower())}"><a href="statements/{esc(s["id"])}.html"><span class="md-math">{esc(label)}</span></a>'
            f'<code class="t-lid">{esc(s["id"])}</code><span class="cell__sub t-disc-inline">{esc(dname)}</span></td>'
            f'<td data-v="{esc(fid or "")}" data-label="{esc(T("col_result"))}">{f"<a href=\"families/{fid}.html\">{fam_title_html(f)}</a>" if f else ""}</td>'
            f'<td class="t-disc" data-v="{esc(dname)}">{esc(dname)}</td>'
            f'<td class="t-pair" data-v="{esc(sort_v or "~")}" data-label="{esc(T("col_pair"))}">{pair_cell}</td>'
            + "".join(rcells) +
            f'<td class="t-num" data-v="{acc}" data-label="{esc(T("col_runs"))}">{num(acc)}</td>'
            f'<td class="t-c" data-v="{1 if s["main_result"] else 0}" data-label="{esc(T("col_main"))}">{esc(C("statements.yes") if s["main_result"] else C("statements.no"))}</td>'
            f'<td class="t-num" data-v="{s["vocabulary_count"]}" data-label="{esc(T("col_vocab"))}">{num(s["vocabulary_count"])}</td>'
            f'<td class="t-num" data-v="{s["statement_lines"]}" data-label="{esc(T("col_lines"))}">{num(s["statement_lines"])}</td>'
            f'<td class="t-notes" data-v="{len(notes)}" data-label="{esc(T("col_notes"))}">{notes_html}</td></tr>')
    cols = [("statement", "s", ""), ("result", "s", ""), ("discipline", "s", "t-disc"), ("pair", "s", "t-pair")]
    # column heads link their glossary term where the glossary has one
    head_terms = {"statement": "challenge", "result": "family", "pair": "pairing", "runs": "rerun", "vocab": "local-vocabulary"}
    heads = [f'<th scope="col"{(" class=" + chr(34) + c + chr(34)) if c else ""} aria-sort="none"{tip_attr(C("statements.tips." + k))}>{sort_head(i, t, T("col_" + k), head_terms.get(k))}</th>'
             for i, (k, t, c) in enumerate(cols)]
    for side, src in enumerate(order):
        heads.append(f'<th scope="col" class="t-reader" aria-sort="none"{tip_attr(C("statements.tips.reader", name=short_name[src]))}>{sort_head(4 + side, "s", T("col_reader", name=short_name[src]), reader_term(src))}</th>')
    base = 4 + len(order)
    for j, (k, c) in enumerate((("runs", "t-num"), ("main", "t-c"), ("vocab", "t-num"), ("lines", "t-num"), ("notes", ""))):
        label = C("statements.col_runs") if k == "runs" else T("col_" + k)
        heads.append(f'<th scope="col"{(" class=" + chr(34) + c + chr(34)) if c else ""} aria-sort="none"{tip_attr(C("statements.tips." + k))}>{sort_head(base + j, "n", label, head_terms.get(k))}</th>')

    def select(id_, label, key, opts, term=None, tip=None):
        return (f'<div class="filters__g"{tip_attr(tip, above=True)}><label class="filters__h" for="{id_}">{head_term(term, esc(label))}</label>'
                f'<select class="select" id="{id_}" data-filter="{key}">{"".join(opts)}</select></div>')
    dcount = Counter(slugify(DISCIPLINES[DISC_OF[s["families"][0]]]["name"]) for s in STATEMENTS if s.get("families") and DISC_OF.get(s["families"][0]) is not None)
    dopts = [f'<option value="">{esc(T("all_disciplines"))}</option>'] + [
        f'<option value="{k}">{esc(v)} ({num(dcount[k])})</option>' for k, v in sorted(disc_slug.items(), key=lambda x: x[1]) if k]
    popts = [f'<option value="">{esc(T("all_pairings"))}</option>'] + [
        f'<option value="{k}">{esc(cap(T("pair." + k)))} ({num(counts[k])})</option>' for k in ("declared", "cited", "lean-words", "catalogue-words", "none") if counts[k]]
    gopts = [f'<option value="">{esc(C("statements.groups_any"))}</option>'] + [
        f'<option value="{k}">{esc(C("statements.groups_" + k))} ({num(counts["g_" + k])})</option>' for k in ("disagree", "agree") if counts["g_" + k]]
    ropts = [f'<option value="">{esc(C("statements.proof_any"))}</option>'] + [
        f'<option value="{k}">{esc(C("statements.proof_" + k))} ({num(counts["p_" + k])})</option>' for k in ("accepted", "other", "none") if counts["p_" + k]]
    selects = [select("sf-d", T("filter_discipline"), "d", dopts, tip=C("statements.tips.f_discipline")),
               select("sf-c", T("filter_pairing"), "c", popts, term="pairing", tip=C("statements.tips.f_pairing")),
               select("sf-g", C("statements.filter_groups"), "g", gopts, term="readers", tip=C("statements.tips.f_groups")),
               select("sf-p", C("statements.filter_proof"), "p", ropts, term="rerun", tip=C("statements.tips.f_proof"))]
    for side, src in enumerate(order):
        opts = [f'<option value="">{esc(T("reader_any"))}</option>'] + [
            f'<option value="{tone}">{esc(cap(evidence.say("tone_short." + tone)))} ({num(counts[(side, tone)])})</option>'
            for tone in evidence.TONES if counts[(side, tone)]]
        selects.append(select(f"sf-{side}", T("filter_reader", name=short_name[src]), "l" if side == 0 else "r", opts, term=reader_term(src),
                              tip=C("statements.tips.f_reader", name=short_name[src])))
    selects.append(f'<div class="filters__g filters__g--q"><label class="filters__h" for="sf-q">{esc(T("filter_words"))}</label>'
                   f'<input class="filter-input" id="sf-q" type="search" data-filter="q" autocomplete="off" spellcheck="false" placeholder="{esc(T("filter_words_ph"))}"></div>')
    sort_menu = [("0:s:ascending", "sort_name"), ("2:s:ascending", "sort_discipline"), ("3:s:ascending", "sort_pair"),
                 (f"{base}:n:descending", "sort_runs"), (f"{base + 2}:n:descending", "sort_vocab"), (f"{base + 3}:n:descending", "sort_lines")]
    sort_select = (f'<div class="filters__g filters__g--sort"><label class="filters__h" for="sf-sort">{esc(T("sort_label"))}</label>'
                   f'<select class="select" id="sf-sort" data-sort-table="stmt-table">'
                   + "".join(f'<option value="{v}">{esc(T(k))}</option>' for v, k in sort_menu) + "</select></div>")
    total = len(STATEMENTS)
    lede = C("statements.lede", lean=NUM("statements_lean"), main=NUM("statements_lean_main_results"))
    readers_note = T("readers_note", names=evidence.join_names([prose_credit(reader_names.get(s_, s_)) for s_ in order]))
    body = f"""<div class="frame page page--families page--stmts">
{section_trail("", "statements")}
<header class="phead phead--compact">
 <h1 class="phead__title">{esc(C('statements.title'))}</h1>
 <p class="phead__lede">{esc(lede)}</p>
</header>
<section class="band band--table" aria-labelledby="h-stmt-list">
<h2 class="h2 vh" id="h-stmt-list">{esc(T('list_heading'))}</h2>
<div class="filters filters--families" data-filter-families="stmt-table">
 <button type="button" class="btn btn--ghost filters__toggle" aria-expanded="false" aria-controls="stmt-filters">{esc(T('filter_toggle'))}</button>
 {sort_select}
 <div class="filters__panel" id="stmt-filters">{''.join(selects)}</div>
 <div class="filters__status">
  <p class="filters__n" aria-live="polite" data-shown-template="{esc(T('shown', n='{n}', total=num(total)))}" data-criteria-lead="{esc(T('criteria_lead'))}">{esc(T('shown', n=num(total), total=num(total)))}</p>
  <button type="button" class="btn btn--quiet filters__reset" hidden>{esc(T('reset'))}</button>
 </div>
 <p class="filters__note">{esc(readers_note)} {esc(T('pair_note'))}</p>
</div>
<p class="filters__empty" hidden>{esc(T('none_match'))}</p>
<div class="table-wrap"><table class="tbl tbl--sortable tbl--families tbl--stmts" id="stmt-table">
 <caption class="vh">{esc(T('caption'))}</caption>
 <thead><tr>{''.join(heads)}</tr></thead>
 <tbody>{''.join(rows)}</tbody>
</table></div>
</section>
</div>"""
    write_page(rel, page(rel, C("statements.title"), lede, body, current="statements"))


NUMBER_PACKETS = ("number-receipt", "number-members")

# The numbers page's groups, in reading order. Which group a number sits in is
# presentation; every value, unit, rule, state and credit is the backend's. A sentence
# key the backend adds later lands in the last group, so nothing is dropped.
NUMBER_GROUPS = [
    ("release", ["families", "disciplines", "manuscripts_current", "manuscripts_withdrawn", "manuscripts_previous_editions"]),
    ("lean", ["statements_lean", "statements_lean_main_results", "main_result_declarations", "distinct_target_theorems",
              "families_with_lean", "manuscripts_with_lean", "lean_definition_holes", "lean_statements_pure_mathlib",
              "lean_statements_no_local_vocabulary", "lean_statements_with_custom_vocabulary",
              "lean_statements_importing_non_mathlib", "lean_statements_declaring_axioms", "lean_vocabulary_total",
              "lean_vocabulary_median", "lean_vocabulary_max"]),
    ("citations", ["internal_citation_edges", "atlas_baseline_internal_citation_edges", "manuscripts_citing_collection",
                   "atlas_baseline_manuscripts_citing_collection", "manuscripts_citing_unformalised_collection_results",
                   "atlas_baseline_manuscripts_citing_unformalised_collection_results", "external_citations",
                   "external_works_cited"]),
    ("scope", ["scope_statements_classified", "scope_class_headline", "scope_class_headline-part", "scope_class_consequence",
               "scope_class_weaker", "scope_class_supporting", "scope_class_unclear", "scope_families_no_full_headline",
               "scope_families_partial_headline_only", "scope_families_with_lean_but_no_headline_coverage",
               "scope_families_mixed_classes"]),
    ("library", ["lean_projects", "lean_files", "projects_with_model_file", "model_files", "model_statement_definitions",
                 "model_statement_projects_linked_to_a_family", "manuscript_theorems", "projects_with_manuscript_theorems",
                 "manuscript_theorems_checked_by_comparator"]),
    ("papers", ["paper_environments_theorem", "paper_environments_lemma", "paper_environments_proposition",
                "paper_environments_corollary", "paper_environments_definition", "paper_environments_remark",
                "paper_environments_hypothesis", "paper_environments_claim", "paper_environments_question"]),
    ("community", ["community_efforts", "community_findings", "community_people"]),
    ("other", []),
]


def number_value(summary: dict) -> str:
    """A number's value as the page prints it: never a zero for an unknown."""
    v = summary.get("value")
    if v is None:
        kv = summary.get("known_value")
        return C("numbers.value_known", n=num(kv)) if kv is not None else C("numbers.value_unknown")
    if isinstance(v, float):
        return f"{v:,.1f}".rstrip("0").rstrip(".") if v != int(v) else num(int(v))
    return num(v)


def NUM(key: str) -> str:
    """The value of a number the site states in a sentence, from the backend's numbers
    index (r.number), formatted for a sentence. Unknown values say so in words."""
    return number_value(RD().number(key))


def NUMV(key: str):
    """The raw value (None when unknown), for choosing singular or plural wording."""
    return RD().number(key).get("value")


def number_credit(summary: dict) -> str:
    cr = summary.get("credit") or {}
    names = []
    for i in cr.get("inputs") or []:
        n_ = i.get("credit") or i.get("source")
        if n_ and n_ not in names:
            names.append(n_)
    kind = cr.get("kind") or ""
    # A credit with no named input says how it was made, in words (never the backend's kind id).
    who = "; ".join(names) or COPY["numbers"]["credit_kinds"].get(kind) or ""
    if not names and kind and kind not in COPY["numbers"]["credit_kinds"]:
        warn(f"numbers: no words for credit kind {kind!r} (site/copy.json numbers.credit_kinds)")
    return who


def build_numbers():
    rel = "numbers.html"
    r = RD()
    # The receipts and their member pages, copied at their logical paths for the page's
    # script; the build reconstructs every receipt and checks its digest first.
    dst = OUT / "data"
    for logical, path in r.browser_files(NUMBER_PACKETS):
        r.packet(logical)
        out = dst / logical
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, out)
    keys = r.numbers_index["sentence_keys"]
    grouped = {g: [k for k in ks if k in keys] for g, ks in NUMBER_GROUPS}
    placed = {k for ks in grouped.values() for k in ks}
    grouped["other"] = [k for k in keys if k not in placed]
    labels = COPY["numbers"]["labels"]
    credits = Counter(number_credit(r.number(k)) for k in keys)
    common_credit = credits.most_common(1)[0][0] if credits else ""
    sections = []
    for g, ks in NUMBER_GROUPS:
        ks = grouped[g]
        if not ks:
            continue
        rows = []
        for k in ks:
            s = r.number(k)
            r.number_receipt(k)            # stops the build if the receipt does not reconstruct
            state = s.get("state") or "computed"
            value = number_value(s)
            label = labels.get(k) or k.replace("_", " ")
            # The backend's rule names its fields; the page says it in words, and the raw rule
            # stays in the receipt (data/...). A rule without words is left off the page.
            rule = COPY["numbers"]["rule_words"].get(k, "")
            if not rule:
                warn(f"numbers: no plain rule for {k!r} (site/copy.json numbers.rule_words)")
            unit = COPY["numbers"]["unit_words"].get(s.get("unit") or "", "")
            if s.get("unit") and not unit:
                warn(f"numbers: no words for the unit {s.get('unit')!r} (site/copy.json numbers.unit_words)")
            credit = number_credit(s)
            receipt = s.get("receipt") or {}
            raw = f'data/{receipt.get("path")}' if receipt.get("path") else ""
            state_words = C("numbers.state." + state) if state in COPY["numbers"]["state"] else state
            rows.append(f"""<article class="numrow" id="n-{esc(k)}" data-receipt="{esc(receipt.get('path') or '')}">
 <p class="numrow__v{' numrow__v--unknown' if s.get('value') is None else ''}">{esc(value)}</p>
 <div class="numrow__t">
  <h3 class="h3">{esc(cap(label))}</h3>
  <p class="numrow__unit">{esc(C('numbers.unit', unit=unit)) if unit else ''} <span class="numrow__state numrow__state--{esc(state)}">{esc(state_words)}</span></p>
  {f'<p class="numrow__rule"><span class="numrow__k">{esc(C("numbers.rule"))}</span> {esc(rule)}</p>' if rule else ''}
  {f'<p class="numrow__credit"><span class="numrow__k">{esc(C("numbers.credit"))}</span> {esc(credit)}</p>' if credit != common_credit else ''}
  <details class="receipt" data-key="{esc(k)}"><summary>{esc(C('numbers.records'))}</summary>
   <div class="receipt__body"><p class="small muted">{esc(C('numbers.records_nojs'))} <a href="{esc(raw)}">{esc(C('numbers.records_raw'))}</a></p></div>
  </details>
 </div>
</article>""")
        intro = C("numbers.group_intro." + g) if g in COPY["numbers"]["group_intro"] else ""
        extra = ""
        if g == "citations":
            extra = f'<p class="intro">{esc(C("numbers.two_inventories", current=NUM("internal_citation_edges"), baseline=NUM("atlas_baseline_internal_citation_edges")))}</p>'
        sections.append(f'<section class="band" aria-labelledby="h-n-{g}"><h2 class="h2" id="h-n-{g}">{esc(C("numbers.group." + g))}</h2>'
                        f'{f"<p class=intro>{esc(intro)}</p>" if intro else ""}{extra}<div class="numrows">{"".join(rows)}</div></section>')
    # What OpenAI's release says about itself, quoted, beside the backend's count.
    s_ = SUMMARY
    upr = s_.get("upstream_reported", {})
    up_html = []
    cat = upr.get("catalogue")
    if cat:
        up_html.append(f"""<article class="pair">
 <div class="pair__a"><p class="pair__k">{esc(C('numbers.col_openai'))}</p><blockquote class="quote"><p>“{esc(cat['quote'])}”</p><footer>{esc(C('numbers.quoted_from'))} <a class="ext" href="{esc(cat['source'])}" rel="noopener">README.md</a></footer></blockquote></div>
 <div class="pair__b"><p class="pair__k">{esc(C('numbers.col_atlas'))}</p><p>{esc(C('numbers.catalogue_atlas_value', manuscripts=NUM('manuscripts_current'), families=NUM('families')))} <a href="#n-manuscripts_current">{esc(C('numbers.see_records'))}</a></p></div>
</article>""")
    tf = upr.get("top_line_results_formalized")
    if tf:
        up_html.append(f"""<article class="pair">
 <div class="pair__a"><p class="pair__k">{esc(C('numbers.col_openai'))}</p><blockquote class="quote"><p>“{esc(tf['quote'])}”</p><footer>{esc(C('numbers.quoted_from'))} <a class="ext" href="{esc(tf['source'])}" rel="noopener">history.md</a></footer></blockquote></div>
 <div class="pair__b"><p class="pair__k">{esc(C('numbers.col_atlas'))}</p><p>{esc(C('numbers.upstream_formalised_atlas', n=NUM('manuscripts_with_lean')))} <a href="#n-manuscripts_with_lean">{esc(C('numbers.see_records'))}</a></p></div>
</article>""")
    wd = [m for m in MANUSCRIPTS if m["status"] == "withdrawn"]
    wd_html = "".join(f'<article class="note note--warn"><h3 class="h3"><a href="papers/{esc(m["id"])}.html">{ms_title_html(m)}</a></h3><div class="md-math">{md_paragraphs(m.get("withdrawal_note") or "")}</div><p class="muted small">{esc(C("paper.withdrawn_on", date=m.get("withdrawn_on") or ""))}</p></article>' for m in wd)
    hist = "".join(f'<article class="changelog"><h3 class="h3">{esc(h["date"])}</h3><blockquote class="quote md-math">{md_paragraphs(h["markdown"])}<footer><a class="ext" href="{BASE_BLOB}history.md" rel="noopener">{esc(C("numbers.changelog_source"))}</a></footer></blockquote></article>' for h in HISTORY)
    toc = "".join(f'<li><a href="#h-n-{g}">{esc(C("numbers.group." + g))}</a></li>' for g, _ in NUMBER_GROUPS if grouped[g])
    body = f"""<div class="frame page page--numbers" data-generation="{esc(r.generation)}">
{section_trail("", "about", C("numbers.title"))}
<header class="phead phead--split">
 <h1 class="phead__title">{esc(C('numbers.title'))}</h1>
 <p class="lede">{esc(C('numbers.purpose'))}</p>
 <div class="phead__more">
 <p>{esc(C('numbers.lede'))}</p>
 <p class="phead__facts">{esc(C('numbers.states_note'))}</p>
 <p class="phead__facts">{esc(C('numbers.credit_common', credit=common_credit))}</p>
 </div>
 <nav class="numtoc" aria-label="{esc(C('numbers.toc_label'))}"><ul>{toc}</ul></nav>
</header>
{''.join(sections)}
<section class="band" aria-labelledby="h-up"><h2 class="h2" id="h-up">{esc(C('numbers.upstream_heading'))}</h2><p class="intro">{esc(C('numbers.upstream_intro'))}</p>{''.join(up_html)}</section>
<section class="band" aria-labelledby="h-wd"><h2 class="h2" id="h-wd">{esc(C('numbers.withdrawn_heading'))}</h2><p class="intro">{esc(C('numbers.withdrawn_intro', n=NUM('manuscripts_withdrawn')))}</p>{wd_html}</section>
<section class="band" aria-labelledby="h-hist"><h2 class="h2" id="h-hist">{esc(C('numbers.changelog_heading'))}</h2>{hist}</section>
</div>
{json_script('number-words', COPY['numbers']['js'])}"""
    write_page(rel, page(rel, C("numbers.title"), C("numbers.lede"), body, current="about"))


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
            head_ = f'<span class="work__ti md-math">{esc(curly_prose(title))}</span>' + (f' <span class="work__au">{esc(authors)}</span>' if authors else "")
        else:
            head_ = f'<span class="work__tx md-math">{esc(curly_prose(clean_ref_text(w.get("text") or w["id"])))}</span>'
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
    r = RD()
    copy_citation_packets(r)
    # Three names to try, taken from the most-cited works' recorded authors.
    tries = []
    for w in hl:
        first = (clean_ref_text(w.get("authors")) or "").split(" and ")[0].split(",")[0].strip()
        # A person's surname, not a collective author ("The Stacks Project Authors").
        if first and first not in tries and " " not in first and first[:1].isupper():
            tries.append(first)
        if len(tries) == 3:
            break
    try_html = " ".join(f'<button type="button" class="chip" data-cite-try="{esc(t)}">{esc(t)}</button>' for t in tries)
    find = f"""<section class="band band--tight cite" id="find-citations" aria-labelledby="h-cite">
 <h2 class="h2" id="h-cite">{esc(C('references_outside.find_heading'))}</h2>
 <p class="intro">{esc(C('references_outside.find_intro'))}</p>
 <form class="cite-form" id="cite-form" role="search">
  <label class="cite-form__l" for="cite-q">{esc(C('references_outside.find_label'))}</label>
  <div class="cite-form__row">
   <input class="cite-form__q" id="cite-q" type="search" name="cites" autocomplete="off" spellcheck="false" placeholder="{esc(C('references_outside.find_placeholder'))}">
   <button class="btn btn--primary" type="submit">{esc(C('references_outside.find_button'))}</button>
  </div>
  <fieldset class="cite-form__in"><legend class="vh">{esc(C('references_outside.find_label'))}</legend>
   <label><input type="radio" name="cite-field" value="author" checked> {esc(C('references_outside.find_field_author'))}</label>
   <label><input type="radio" name="cite-field" value="text"> {esc(C('references_outside.find_field_text'))}</label>
  </fieldset>
  {('<p class="cite-form__try">' + esc(C('references_outside.find_try')) + ' ' + try_html + '</p>') if tries else ''}
 </form>
 <p class="cite-status" id="cite-status" role="status" aria-live="polite"></p>
 <div class="cite-out" id="cite-out"></div>
 <p class="muted small">{esc(C('references_outside.find_boundary'))}</p>
</section>"""
    body = f"""<div class="frame page" data-generation="{esc(r.generation)}">
{section_trail("", "explain", C("references_outside.title"))}
<header class="phead phead--split">
 <h1 class="phead__title">{esc(C('references_outside.title'))}</h1>
 <p class="lede">{esc(C('references_outside.purpose'))}</p>
 <div class="phead__more">
 <p>{esc(C('references_outside.lede', works=NUM('external_works_cited'), citations=NUM('external_citations'), n=len(hl)))}</p>
 <p>{esc(C('references_outside.credit'))}</p>
 </div>
 <p class="muted small">{esc(C('references_outside.how'))}</p>
</header>
{find}
<section class="band band--tight"><div class="works">{''.join(rows)}</div></section>
</div>
{json_script('cite-words', COPY['references_outside']['js'])}"""
    extra = f'<script defer src="assets/{asset_v("cite.js")}"></script>'
    write_page(rel, page(rel, C("references_outside.title"), C("references_outside.lede", works=NUM("external_works_cited"), citations=NUM("external_citations"), n=len(hl)), body, current="explain", extra_head=extra))


CITATION_PACKETS = ("citations-index", "citation-entries", "citation-shard")


def copy_citation_packets(r):
    """Copy Statement Map's citation index (data/citations-index.json), entry chunks and
    shards (data/citations/) at their logical paths, each checked first, for the lookup on
    references-outside.html (site/assets/cite.js). A query reads only the index, its
    shards and the chunks it needs."""
    dst = OUT / "data"
    for logical, path in r.browser_files(CITATION_PACKETS):
        r.packet(logical)       # checks bytes, release, pin and generation
        out = dst / logical
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, out)


def used_on(nf: int, nfam: int) -> str:
    """What an outside effort is attached to: its findings and the families they concern,
    or only the families it covers when no finding is recorded."""
    fams = C("sources.on_result" if nfam == 1 else "sources.on_results")
    if not nf:
        return C("sources.covers", families=fams)
    return C("sources.used_on", findings=C("sources.findings_one") if nf == 1 else C("sources.findings_many", n=nf), families=fams)


def build_sources():
    rel = "sources.html"
    rows = []
    s = SUMMARY
    up = f"""<article class="ceff" id="src-openai-math">
 <h3 class="h3"><a class="ext" href="{esc(CFG['upstream_repo'])}/tree/{COMMIT}" rel="noopener">openai/math</a></h3>
 <p class="muted small">OpenAI, {esc(C('sources.pinned', commit=COMMIT_SHORT))}, Apache-2.0</p>
 <p>{esc(C('sources.openai_uses', families=NUM('families'), manuscripts=NUM('manuscripts_current'), lean=NUM('statements_lean')))}</p>
</article>"""
    own = f"""<article class="ceff" id="src-atlas">
 <h3 class="h3"><a class="ext" href="{esc(REPO)}" rel="noopener">{esc(C('site.name'))}</a></h3>
 <p class="muted small">{esc(CFG['author'])}</p>
 <p>{esc(C('sources.atlas_uses'))}</p>
</article>"""
    components = []
    for item in attribution.inventory()["components"]:
        components.append(f"""<article class="ceff" id="component-{esc(item['id'])}">
 <h3 class="h3"><a class="ext" href="{esc(item['url'])}" rel="noopener">{esc(item['name'])}</a> {esc(item['version'])}</h3>
 <p class="muted small">{esc(item['credit'])} · {esc(item['licence'])}</p>
 <p>{esc(item['use'])} {esc(item['changes'])}</p>
 <p class="small"><a href="{esc(item['licence_file'])}">{esc(C('sources.licence_copy'))}</a> · <a class="ext" href="{esc(item['source'])}" rel="noopener">{esc(C('sources.component_source'))}</a></p>
</article>""")
    ingested = []
    for src in s.get("sources", []):
        # The curated source owner retains the import revision; the older summary
        # projection records only the capture date.
        source_meta = json.loads((ROOT / "curated" / "sources" / f"{src['id']}.json").read_text())["source"]
        provenance = []
        if source_meta.get("repository") and source_meta.get("snapshot_commit"):
            pin = source_meta["snapshot_commit"]
            pinned_url = source_meta["repository"].rstrip("/") + "/tree/" + pin
            provenance.append(f'<a class="ext" href="{esc(pinned_url)}" rel="noopener">{esc(C("sources.pin_link"))} {esc(pin[:12])}</a>')
        for licence_file in attribution.inventory()["source_licences"].get(src["id"], []):
            provenance.append(f'<a href="{esc(licence_file)}">{esc(C("sources.licence_copy"))}</a>')
        fields = src.get("fields") or {}
        # each field the source adds, named in words (the field id stays in the data)
        field_words = COPY["sources"]["field_words"]
        for k in fields:
            if k not in field_words:
                warn(f"sources: no words for the field {k!r} of {src['id']} (site/copy.json sources.field_words)")
        flist = "".join(f"<li><strong>{esc(field_words.get(k) or cap(k.replace('_', ' ')))}</strong>: {esc(v)}</li>" for k, v in fields.items())
        authors = ", ".join(a.get("name") or a.get("handle") or "" for a in (src.get("authors") or []))
        ingested.append(f"""<article class="ceff" id="src-{esc(src['id'])}">
 <h3 class="h3"><a class="ext" href="{esc(src.get('url') or '')}" rel="noopener"><span class="md-math">{esc(src.get('name') or src['id'])}</span></a></h3>
 <p class="muted small">{esc(authors)}, {esc(C('sources.snapshot', date=src.get('snapshot') or ''))}, {esc(C('sources.licence', licence=src.get('licence') or 'n/a'))}</p>
 {('<p class="small">' + ' · '.join(provenance) + '</p>') if provenance else ''}
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
 <h3 class="h3"><a class="ext" href="{esc(e['url'])}" rel="noopener"><span class="md-math">{esc(curly_prose(e['name']))}</span></a></h3>
 <p class="muted small">{esc(credit_names(e))}{', ' if credit_names(e) else ''}{esc(e.get('date') or '')}, {esc(C('community.reuse_' + e.get('reuse', 'link')))} {esc(C('community.licence', licence=e.get('licence') or 'n/a'))}</p>
 <p class="md-math">{esc(e['summary'])}</p>
 {('<p class="small">' + esc(used_on(nf, len(fams))) + ' ' + fam_links + '</p>') if fams else ''}
 {adopted_list_html(e.get('adopted'))}
</article>""")
    people = {(a.get("name") or a.get("handle")) for e in COMMUNITY["list"] for a in (e.get("authors") or [])}
    lede = C("sources.lede", sources=num(2 + len(s.get("sources", [])) + (NUMV("community_efforts") or len(COMMUNITY["list"]))), people=NUM("community_people"), findings=NUM("community_findings"))
    body = f"""<div class="frame page">
{section_trail("", "sources")}
<header class="phead phead--split">
 <h1 class="phead__title">{esc(C('sources.title'))}</h1>
 <p class="lede">{esc(C('sources.purpose'))}</p>
 <div class="phead__more"><p class="phead__facts">{esc(lede)} {esc(C('sources.credit'))}</p></div>
 <nav class="jump" aria-label="{esc(C('sources.jump_label'))}"><ul><li><a href="#base">{esc(C('sources.base_heading'))}</a></li>{('<li><a href="#ingested">' + esc(C('sources.ingested_heading')) + '</a></li>') if ingested else ''}{('<li><a href="#efforts">' + esc(C('sources.efforts_heading')) + '</a></li>') if efforts else ''}<li><a href="#software">{esc(C('sources.components_heading'))}</a></li><li><a href="NOTICE">{esc(C('sources.notices_link'))}</a></li><li><a href="CITATION.cff">{esc(C('sources.citation_link'))}</a></li></ul></nav>
 <p class="muted small">{esc(C('community.how'))} <a class="ext" href="{esc(issue_url('problem', C('community.add_title'), page=BASE_URL + rel))}" rel="noopener">{esc(C('community.add'))}</a></p>
</header>
<section class="band band--tight" id="base"><h2 class="h2">{esc(C('sources.base_heading'))}</h2><div class="ceffs">{up}{own}</div></section>
{('<section class="band band--tight" id="ingested"><h2 class="h2">' + esc(C('sources.ingested_heading')) + '</h2><p class="intro">' + esc(C('sources.ingested_intro')) + '</p><div class="ceffs">' + ''.join(ingested) + '</div></section>') if ingested else ''}
{('<section class="band band--tight" id="efforts"><h2 class="h2">' + esc(C('sources.efforts_heading')) + '</h2><p class="intro">' + esc(C('sources.efforts_intro')) + '</p><div class="ceffs">' + ''.join(efforts) + '</div></section>') if efforts else ''}
<section class="band band--tight" id="software"><h2 class="h2">{esc(C("sources.components_heading"))}</h2><p class="intro">{esc(C("sources.components_intro"))}</p><div class="ceffs">{"".join(components)}</div></section>
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
  <p class="work__n">{esc(C('citations_within.cited_by', n=e['cited_by']))}. {esc(lean)}.{(' ' + C('words.result').capitalize() + ' ' + f['id'] + ': <a href="families/' + f['id'] + '.html">' + fam_title_html(f) + '</a>') if f else ''}</p>
  <ul class="work__list">{citing}</ul>
 </div>
</article>""")
    body = f"""<div class="frame page">
{section_trail("", "explain", C("citations_within.title"))}
<header class="phead phead--split">
 <h1 class="phead__title">{esc(C('citations_within.title'))}</h1>
 <p class="lede">{esc(C('citations_within.purpose'))}</p>
 <div class="phead__more">
 <p>{esc(C('citations_within.lede', edges=NUM('internal_citation_edges'), n=len(hl)))}</p>
 </div>
 <p class="muted small">{esc(C('citations_within.how'))}</p>
</header>
<section class="band band--tight"><div class="works">{''.join(rows)}</div></section>
</div>"""
    write_page(rel, page(rel, C("citations_within.title"), C("citations_within.lede", edges=NUM("internal_citation_edges"), n=len(hl)), body, current="explain"))


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
        short, who = COPY["contribute"]["way_names"][key]
        ways.append(f'<li class="way"><a class="way__a ext" href="{esc(REPO)}/issues/new?template={esc(name)}.yml" rel="noopener">'
                    f'<span class="way__n">{esc(short)}</span><span class="way__who">{esc(who)}</span>'
                    f'<span class="way__d">{esc(C("contribute." + key))}</span></a></li>')
    names = contributor_names()
    contrib = f'<p>{esc(", ".join(names))}</p>' if names else f'<p class="muted">{esc(C("contribute.contributors_none"))}</p>'
    body = f"""<div class="frame page page--wide">
{section_trail("", "contribute")}
<header class="phead"><h1 class="phead__title">{esc(C('contribute.title'))}</h1><p class="lede">{esc(C('contribute.purpose'))}</p></header>
<section class="band band--tight"><h2 class="h2">{esc(C('contribute.ways_heading'))}</h2><ul class="ways">{''.join(ways)}</ul>
<p class="intro">{esc(C('contribute.guide'))} <a class="ext" href="{esc(guide)}" rel="noopener">{esc(C('contribute.guide_link'))}</a></p></section>
<div class="cards2">
<section class="panel"><h2 class="h3">{esc(C('explain.queue_heading'))}</h2><p>{esc(C('contribute.queue'))} <a href="explain.html#careful-reading">{esc(C('contribute.queue_link'))}</a></p></section>
<section class="panel" id="contributors"><h2 class="h3">{esc(C('contribute.contributors_heading'))}</h2>{contrib}</section>
</div>
</div>"""
    write_page(rel, page(rel, C("contribute.title"), C("contribute.lede"), body, current="contribute"))


def credited_groups() -> list[str]:
    """Every outside group whose record the backend carries: readings, re-runs and check
    cards, by their credited names, in first-seen order."""
    r = RD()
    names = []
    for fid in r.family_ids():
        d = r.family(fid)
        recs = [x.get("credit") for x in d.get("readings") or []]
        recs += [run.get("credit") for l in d.get("lean") or [] for run in l.get("runs") or []]
        recs += [c.get("credit") for c in d.get("independent_check_cards") or []]
        for cr in recs:
            n_ = (cr or {}).get("name")
            if n_ and n_ not in names:
                names.append(n_)
    return names


def build_about():
    rel = "about.html"
    r = RD()
    fill = dict(release_date=CFG["release_date"], families=NUM("families"), families_with_lean=NUM("families_with_lean"),
                commit_short=COMMIT_SHORT, author=CFG["author"])
    cite = C("about.cite_format", author=CFG["author"], name=C("site.citation_title"), url=BASE_URL, commit=COMMIT)
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
    adds_fill = dict(manuscripts=NUM("manuscripts_current"), lean=NUM("statements_lean"), families=NUM("families"))
    adds = "".join(f"<li>{esc(t.format(**adds_fill))}</li>" for t in COPY["about"]["adds_items"])
    receipt = r.export.get("acceptance_receipt") or {}
    backend_p = (f'<p>{esc(C("about.backend"))}</p>'
                 f'<p>{esc(C("about.backend_pin", generation=r.generation.split(":")[-1][:12], commit=(r.commit or "")[:12], runtime=(r.runtime or "")[:12], exporter=r.exporter or "", receipt=(receipt.get("sha256") or "").split(":")[-1][:12], schema=r.export.get("reader_schema") or ""))} '
                 f'<a href="numbers.html">{esc(C("about.backend_numbers"))}</a></p>')
    groups = [prose_credit(g) for g in credited_groups()]
    group_list = ", ".join(groups[:-1]) + (" " + C("about.and") + " " if len(groups) > 1 else "") + (groups[-1] if groups else "")
    since = "".join(
        f'<li class="approach__item"><p><span class="approach__who">{esc(a["who"])}</span>, in '
        f'<a class="ext" href="{esc(a["url"])}" rel="noopener">{esc(a["title"])}</a>, {esc(a["says"])}</p></li>'
        for a in COPY["about"]["since_items"])
    body = f"""<div class="frame page page--wide prose-page">
{section_trail("", "about")}
<header class="phead phead--split"><h1 class="phead__title">{esc(C('about.title'))}</h1><p class="lede">{esc(C('about.purpose', author=CFG['author']))}</p>
<section class="phead__sec phead__more" aria-labelledby="h-what"><h2 class="vh" id="h-what">{esc(C('about.what_heading'))}</h2><p>{esc(C('about.what', **fill))}</p></section>
<p class="actions"><a class="btn btn--primary" href="families/017.html">{esc(C('about.example_button'))}</a><a class="btn btn--ghost" href="help.html">{esc(C('help.title'))}</a></p></header>
<div class="flow">
<section class="band band--tight" id="approach" aria-labelledby="h-approach"><h2 class="h2" id="h-approach">{esc(C('about.approach_heading'))}</h2><p>{esc(C('about.approach_intro'))}</p><ul class="approach">{approach}</ul></section>
<section class="band band--tight" id="since" aria-labelledby="h-since"><h2 class="h2" id="h-since">{esc(C('about.since_heading'))}</h2><p>{esc(C('about.since_intro'))}</p><ul class="approach">{since}</ul><p>{esc(C('about.since_note'))}</p></section>
<section class="band band--tight" id="adds" aria-labelledby="h-adds"><h2 class="h2" id="h-adds">{esc(C('about.adds_heading'))}</h2><p>{esc(C('about.adds_intro', **adds_fill))}</p><ul class="adds">{adds}</ul></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.how_heading'))}</h2><p>{esc(C('about.how', **fill))}</p>{backend_p}</section>
<section class="band band--tight" id="independence"><h2 class="h2">{esc(C('about.independence_heading'))}</h2><p>{esc(C('about.independence'))}</p><p>{esc(C('about.independence_groups', groups=group_list))}</p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.made_heading'))}</h2><p>{esc(C('about.made'))}</p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.not_heading'))}</h2><p>{esc(C('about.not'))}</p></section>
{('<section class="band band--tight"><h2 class="h2">' + esc(C('about.interests_heading')) + '</h2><p>' + esc(C('about.interests')) + '</p></section>') if C('about.interests') else ''}
<section class="band band--tight"><h2 class="h2">{esc(C('about.disclosed_heading'))}</h2><p>{esc(C('about.disclosed_intro'))}</p><ul>{disclosed_items}</ul></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.related_heading'))}</h2><p>{esc(C('about.related_intro'))}</p><ul>{related_items}</ul></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.licence_heading'))}</h2><p>{esc(C('about.licence'))} <a href="sources.html#software">{esc(C("about.licence_link"))}</a></p></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.cite_heading'))}</h2><p>{esc(C('about.cite'))} <a href="CITATION.cff">CITATION.cff</a></p><div class="texsrc__box texsrc__box--open"><button class="copy" type="button" data-copy-next>{esc(C('words.copy'))}</button><pre><code>{esc(cite)}</code></pre></div></section>
<section class="band band--tight"><h2 class="h2">{esc(C('about.author_heading'))}</h2><p>{esc(C('about.author', **fill))} <a class="ext" href="{esc(CFG['author_url'])}" rel="noopener">{esc(C('about.author_link'))}</a></p></section>
</div>
</div>"""
    write_page(rel, page(rel, C("about.title"), C("about.what", **fill), body, current="about"))


def build_404():
    rel = "404.html"
    base = CFG["base_url"].rstrip("/")
    # Where to go instead: the Families list (every family), the search, and the map.
    families = f'<a href="explain.html">{esc(C("notfound.families_link"))}</a>'
    text = esc(C("notfound.families", link="\x00")).replace("\x00", families)
    body = (f'<div class="frame page page--wide page--404">{trail("", [(esc(C("notfound.title")), None)])}<header class="phead"><h1 class="phead__title">{esc(C("notfound.title"))}</h1>'
            f'<p class="lede">{esc(C("notfound.text"))} {text}</p>'
            f'<p class="actions"><a class="btn btn--primary" href="explain.html">{esc(C("notfound.families_button"))}</a>'
            f'<a class="btn btn--ghost" href="explain.html" data-open-search>{esc(C("notfound.search_button"))}</a>'
            f'<a class="btn btn--quiet" href="{esc(base)}/">{esc(C("notfound.map_button"))}</a></p></header>'
            f'<section class="band band--tight help-route"><h2 class="h2">{esc(C("help.route_alone"))}</h2>{help_steps_html("step-")}</section></div>')
    h = page(rel, C("notfound.title"), C("notfound.text") + " " + C("notfound.families", link=C("notfound.families_link")),
             body, noindex=True)
    # The host serves this page at any depth: local assets and links need the site root.
    path = re.sub(r"https?://[^/]+", "", base)
    h = h.replace('src="assets/', f'src="{path}/assets/').replace('data-root=""', f'data-root="{path}/"')
    h = re.sub(r'href="(?![a-zA-Z][a-zA-Z0-9+.-]*:|/|#)([^"]+)"',
               lambda match: f'href="{path}/{match.group(1)}"', h)
    write_page(rel, h, index=False)


SEARCH_PACKETS = ("search-index", "search-shard", "search-entries")


def search_url(entry_id: str, kind: str) -> str | None:
    """The Atlas page that reads a search entry (mirrors urlFor in site/assets/atlas.js;
    scripts/tests/test_search.py checks both against the backend's own reading_page routes)."""
    head, _, rest = entry_id.partition(":")
    quote_c = lambda v: quote(v, safe="-_.!~*'()")    # encodeURIComponent
    if kind == "family":
        return f"families/{quote_c(rest)}.html"
    if kind == "lean":
        return f"statements/{quote_c(rest)}.html"
    if kind == "manuscript":
        return f"papers/{quote_c(rest)}.html"
    if kind == "discipline":
        return "index.html#o=" + quote_c(entry_id)
    if kind == "statement":
        slug, _, anchor = rest.partition(":")
        return f"papers/{quote_c(slug)}.html#" + quote(anchor, safe=";,/?:@&=+$-_.!~*'()")
    return None


def search_statement_name(entry):
    """Render citation-bearing navigation labels with their paper's bibliography.

    Search packets and the source statement retain the original title. Only the
    displayed label is rendered here, without links nested inside a result link.
    """
    name = entry.get("source_name") or entry.get("name") or ""
    if entry["kind"] != "statement" or not re.search(r"\\(?:" + "|".join(CITE_CMDS) + r")\b", name):
        return None
    slug = entry["id"][2:].partition(":")[0]
    ms = MS.get(slug)
    if not ms:
        return None

    class NameConv(TexConv):
        def cite(self, keys, opt):
            # Some source titles use undefined locator macros. Keep the cited
            # work in the navigation label; the full title remains in the paper.
            if opt and re.search(r"\\[A-Za-z]+", self.text(opt, inline=True)):
                opt = None
            return super().cite(keys, opt)

    rendered = NameConv(ms, "").text(name, inline=True)
    rendered = re.sub(r'<span class="m"[^>]*>(.*?)</span>',
                      lambda m: esc(_plain_math(html.unescape(m.group(1)))), rendered, flags=re.S)
    rendered = tex_plain(rendered)
    # With a printed number the backend names the statement by it; the title follows,
    # as in the paper ("Theorem 1.1 (Finite-level ... decomposition)"), as atlas.js does.
    return f'{entry["name"]} ({rendered})' if entry.get("source_name") else rendered


def build_search_data():
    """Copy Statement Map's compact search into data/search/ at its logical paths, and
    write labels.json beside it: which index range holds which kind of entry, each
    paper's title and each family's name, discipline and holdings in words, so a result list can
    show them without loading the reader packets. Ambiguous and non-current paper results
    also carry their source date and edition status. Lean filenames retain their canonical
    case for exact-name lookup without probing filesystem paths. Every file carries the generation."""
    r = RD()
    dst = OUT / "data" / "search"
    for logical, path in r.browser_files(SEARCH_PACKETS):
        r.packet(logical)       # checks bytes, release, pin and generation
        out = dst / logical
        out.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(path, out)
    idx = r.search_index
    entries = []
    for k, chunk in enumerate(idx["entry_chunks"]):
        doc = r.packet(chunk)
        if doc.get("start") != k * idx["entry_chunk_size"]:
            raise SystemExit(f"{chunk} starts at {doc.get('start')}")
        entries.extend(doc["entries"])
    if len(entries) != idx["entry_count"]:
        raise SystemExit(f"search entries: {len(entries)} read, the index says {idx['entry_count']}")
    runs = []
    for i, e in enumerate(entries):
        if runs and runs[-1][0] == e["kind"] and runs[-1][2] == i - 1:
            runs[-1][2] = i
        else:
            runs.append([e["kind"], i, i])
    import evidence
    disc_name = {}
    for d in r.universe.get("disciplines") or []:
        for fid in d.get("family_ids") or []:
            disc_name[fid] = d["name"]
    say = evidence.say

    def holdings(ev):
        papers = say("sentence.papers_one") if ev.papers == 1 else say("sentence.papers_many", n=ev.papers)
        k = len(ev.lean)
        lean = say("sentence.lean_none") if k == 0 else say("sentence.lean_one") if k == 1 else say("sentence.lean_many", n=k)
        return f"{papers}, {lean}"

    fams = {ev.id: {"n": tex_plain(ev.name), "d": disc_name.get(ev.id, ""), "e": holdings(ev)} for ev in evidence.all_families(r)}
    papers = {e["id"]: tex_plain(e["name"]) for e in entries if e["kind"] == "manuscript"}
    title_counts = Counter(papers.values())
    editions = {}
    for pid, title in papers.items():
        m = MS.get(pid[2:])
        if m and (title_counts[title] > 1 or m.get("status") != "current"):
            editions[pid] = ", ".join(filter(None, (date_words(m.get("date")), status_label(m.get("status")))))
    # Every Lean statement by its exact name, so a name typed in any case finds its
    # statement without asking the host for a page (GitHub Pages matches paths by case).
    lean = {}
    for e in entries:
        if e["kind"] != "lean":
            continue
        name = e["id"][2:]
        if any(k.lower() == name.lower() for k in lean):
            raise SystemExit(f"search labels: two Lean statements differ only in case: {name}")
        lean[name] = [curly_prose(e["name"]), e.get("family_ids") or []]
    statement_names = {e["id"]: name for e in entries if (name := search_statement_name(e))}
    labels = {"schema": "plectis-atlas-search-labels/1", "generation_id": r.generation,
              "source": "search-index.json and its entry chunks; family holdings from the reader packets; edition dates, status and citation labels from the manuscript source index",
              "kinds": runs, "papers": papers, "paper_editions": editions,
              "families": fams, "lean": lean, "statement_names": statement_names}
    (dst / "labels.json").write_text(json.dumps(labels, ensure_ascii=False, separators=(",", ":")), encoding="utf-8")


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
    line = C("social.card_line", families=NUM("families"), manuscripts=NUM("manuscripts_current"), lean=NUM("statements_lean"), commit_short=COMMIT_SHORT)
    return f"""<!doctype html><html lang="en-GB" data-theme="dark"><head><meta charset="utf-8"><link rel="stylesheet" href="../assets/atlas.css"></head>
<body class="social"><div class="social__card"><div class="social__text"><p class="social__brand">{MARK_SVG}</p><h1>{esc(C('social.card_title'))}</h1><p>{esc(line)}</p><p class="social__key"><span class="k"><span class="sw sw--main"></span><span>{esc(C('home.legend_lean_main'))}</span></span><span class="k"><span class="sw sw--sup"></span><span>{esc(C('home.legend_lean_support'))}</span></span><span class="k"><span class="sw sw--none"></span><span>{esc(C('home.legend_lean_none'))}</span></span></p></div>
<svg class="social__map" viewBox="0 0 {W} {H}" width="{W}" height="{H}">{''.join(svg)}</svg></div></body></html>"""


def squarify(values, x, y, w, h):
    """Squarified treemap; values sorted descending.

    Bruls, Huizing and van Wijk (2000), doi:10.1007/978-3-7091-6783-0_4.
    See docs/ATTRIBUTION.md for the method and scope of use.
    """
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
    attribution.write_notices(OUT)
    (OUT / ".nojekyll").write_text("")
    (OUT / "cards").mkdir(exist_ok=True)

    (OUT / "data").mkdir(parents=True, exist_ok=True)
    build_home()
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
    build_help()
    build_search_data()
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
