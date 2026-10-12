#!/usr/bin/env python3
"""Build an HTML reading view for every current manuscript in the atlas.

For each current manuscript in data/manuscripts.json, this expands the paper's main
TeX file at the pinned upstream commit, converts it to an HTML page that keeps its
mathematics as TeX for KaTeX, and checks every formula with a local KaTeX through
scripts/check_paper_math.mjs. It writes

    site/_build/papers/<slug>.html   one reading page for each accepted or partial paper
    data/paper_acceptance.json       one row per current manuscript: its status and counts

Statuses, computed from the source and never loosened:

    accepted     every formula was checked and typeset; every cross-reference and
                 citation resolved; every environment and command was understood;
                 every extracted statement has its anchor. Figures may be placeholders.
    partial      the page is written with a banner that lists what failed and links the PDF.
    unavailable  no page; the PDF is the only route.

Usage:

    KATEX_JS=/path/to/node_modules/katex python3 scripts/build_papers.py
    python3 scripts/build_papers.py --only SLUG [SLUG ...]
    python3 scripts/build_papers.py --limit 20 --no-math-check

Without node or KATEX_JS every formula is recorded as unchecked, and an unchecked
paper is never accepted. scripts/build_site.py clears site/_build, so run this
script after it. Standard library only.
"""
from __future__ import annotations

import argparse
import html
import importlib
import json
import os
import re
import shutil
import signal
import subprocess
import sys
import time
import unicodedata
from collections import Counter, defaultdict
from concurrent.futures import ProcessPoolExecutor, as_completed
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
SCRIPTS = ROOT / "scripts"
if str(SCRIPTS) not in sys.path:
    sys.path.insert(0, str(SCRIPTS))

import build_data as bd  # noqa: E402  read-only helpers: expand_tex, TexDoc, find_main_tex, parse_bib

DATA = ROOT / "data"
SITE = ROOT / "site"
OUT = SITE / "_build"
ASSETS = SITE / "assets"
ACCEPTANCE = DATA / "paper_acceptance.json"
NUMBERS = DATA / "statement_numbers.json"
LABELS = DATA / "paper_labels.json"
CHECKER = SCRIPTS / "check_paper_math.mjs"
CFG = json.loads((SITE / "config.json").read_text(encoding="utf-8"))
UPSTREAM_PIN = json.loads((ROOT / "upstream.json").read_text(encoding="utf-8"))
COMMIT = UPSTREAM_PIN["commit"]
BLOB = f"https://github.com/openai/math/blob/{COMMIT}/"
TREE = f"https://github.com/openai/math/tree/{COMMIT}/"
PAGE_MARK = '<meta name="atlas-page" content="paper-reader">'
OWN_ASSETS = ("paper.css", "paper.js")
KATEX_OPTIONS = {"throwOnError": True, "strict": "ignore", "trust": False, "maxExpand": 2000}

sys.setrecursionlimit(20000)

# Every human-facing sentence this script writes. British spelling, no em dashes.
TXT = {
    "kicker": "Reading view",
    "numbering": "Numbering computed from the TeX source; the PDF is the reference.",
    "converted": "This page is converted from the paper’s TeX source at commit {commit}.",
    "figures_one": "One figure is shown as a placeholder; see the PDF for it.",
    "figures_many": "{n} figures are shown as placeholders; see the PDF for them.",
    "partial_h": "This reading view is incomplete",
    "partial_p": "Parts of the TeX source did not convert, so this page is not a faithful copy of the paper. The PDF is the reference for everything listed here.",
    "pdf_link": "Read the PDF",
    "f_unchecked": "The formulas on this page have not been checked.",
    "f_formulas": ("1 formula could not be typeset; its TeX source is shown instead.",
                   "{n} formulas could not be typeset; their TeX source is shown instead."),
    "f_refs": ("1 cross-reference points to a label the source does not define.",
               "{n} cross-references point to labels the source does not define."),
    "f_cites": ("1 citation names a key missing from the bibliography.",
                "{n} citations name keys missing from the bibliography."),
    "f_envs": ("1 environment is not supported: {names}.", "{n} environments are not supported: {names}."),
    "f_cmds": ("1 command was not translated: {names}.", "{n} commands were not translated: {names}."),
    "f_anchors": ("1 extracted statement has no anchor on this page.",
                  "{n} extracted statements have no anchor on this page."),
    "tex_source": "TeX source",
    "contents": "Contents",
    "abstract": "Abstract",
    "references": "References",
    "notes": "Notes",
    "proof": "Proof",
    "fig_tikz": "Figure drawn in TikZ; see the PDF",
    "fig_image": "Figure image; see the PDF",
    "fig_other": "Figure not reproduced here; see the PDF",
    "fig_pdf": "Pages included from {file}, which this view cannot show; see the PDF",
    "f_pdf": ("1 PDF file is set into the paper as whole pages, which this view cannot show: {names}.",
              "{n} PDF files are set into the paper as whole pages, which this view cannot show: {names}."),
    "atlas_note": "Atlas note, not part of the paper",
    "lean_k": "Lean.",
    "lean_how": {
        "candidate-pairing": "{lean} is paired with this theorem as a candidate, found by the words the two share; nobody has reviewed the pairing.",
        "producer-cited-association": "The source of {lean} cites this theorem by its label; nobody has reviewed whether the two state the same thing.",
        "producer-declared-binding": "The release binds {lean} to this theorem; nobody has reviewed whether the two state the same thing.",
    },
    "family_n": "family {n}",
    "headline_note": "Of the papers’ main statements, this one shares the most words with OpenAI’s description of {families}, so the atlas shows it as the candidate for the theorem that description names. Nobody has reviewed the choice.",
    "lean_proof": "Its Lean proof, checked against the Lean statement only:",
    "lean_runs_n": "re-run and accepted by {n} groups outside OpenAI",
    "lean_runs_1": "re-run and accepted by one group outside OpenAI",
    "lean_runs_0": "not yet re-run outside OpenAI",
    "lean_holes_1": "one definition Comparator compares by name and type only",
    "lean_holes_n": "{n} definitions Comparator compares by name and type only",
    "listing_link": "Code listing {file}: open it in the release",
    "listing_pdf": "Code listing {file}; see the PDF",
    "math_failed": "This formula could not be typeset; its TeX source is shown.",
    "back": "Back to the text",
    "permalink": "Link to this passage",
    "fn_label": "Note {n}",
    "description": "Reading view of {title}, converted from its TeX source.",
}


def plural(key: str, n: int, **kw) -> str:
    one, many = TXT[key]
    return (one if n == 1 else many).format(n=n, **kw)


# ------------------------------------------------------------ site helpers

S = None  # scripts/build_site.py, imported for its layout helpers


def import_site(retries: int = 8, wait: float = 5.0):
    """Import build_site for page(), trail() and the copy. Another desk may be
    editing it, so a failed import is retried before giving up."""
    global S
    if S is not None:
        return S
    last = None
    for _ in range(retries):
        try:
            S = importlib.import_module("build_site")
            return S
        except Exception as e:  # noqa: BLE001  (a half-written file can raise anything)
            last = e
            sys.modules.pop("build_site", None)
            time.sleep(wait)
    raise SystemExit(f"cannot import scripts/build_site.py: {last}")


def site_copy(path: str, default: str, **kw) -> str:
    try:
        return S.C(path, **kw)
    except Exception:  # noqa: BLE001  (a key may be renamed by the other desk)
        return default.format(**kw) if kw else default


# ------------------------------------------------------------ text helpers

PARA, BO, BC = "\x03", "\x01", "\x02"      # paragraph break; block element start and end
PH_O, PH_C = "\x10", "\x11"                # reference or citation, resolved after the pass
ID_O, ID_C = "\x12", "\x13"                # element id, resolved from its labels
XA_O, XA_C = "\x14", "\x15"                # extra anchors of an element
BIB_MARK = "\x16"                          # where the bibliography goes
CTRL_RE = re.compile(r"[\x00-\x08\x0b\x0c\x0e-\x1f]")
BLOCK_SPLIT = re.compile("(\x01[^\x01\x02]*\x02|\x03)")


def esc_t(s: str) -> str:
    return s.replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;")


def esc_a(s) -> str:
    return html.escape("" if s is None else str(s), quote=True)


def block(h: str) -> str:
    return BO + h + BC


def assemble(frags, first_inline: str = "") -> str:
    """Join converter output into block HTML: inline runs become paragraphs."""
    out, buf = [], [first_inline] if first_inline else []

    def flush():
        t = "".join(buf).strip(" \t\n")
        buf.clear()
        if t:
            out.append(f"<p>{t}</p>")

    for piece in BLOCK_SPLIT.split("".join(frags)):
        if not piece:
            continue
        if piece == PARA:
            flush()
        elif piece[0] == BO:
            flush()
            out.append(piece[1:-1])
        else:
            buf.append(piece)
    flush()
    return "".join(out)


def inline(frags) -> str:
    s = "".join(frags).replace(PARA, " ")
    s = re.sub("\x01([^\x01\x02]*)\x02", r"\1", s)
    return re.sub(r"\s+", " ", s).strip()


def wrap_inline(frags, open_tag: str, close_tag: str) -> str:
    """Wrap each inline run of frags in a tag, leaving block elements outside it."""
    out = []
    for piece in BLOCK_SPLIT.split("".join(frags)):
        if not piece:
            continue
        if piece == PARA or piece[0] == BO or not piece.strip():
            out.append(piece)
        else:
            out.append(open_tag + piece + close_tag)
    return "".join(out)


def strip_tags(h: str) -> str:
    return html.unescape(re.sub(r"<[^>]+>", "", h))


def roman(n: int) -> str:
    if n <= 0:
        return str(n)
    vals = [(1000, "m"), (900, "cm"), (500, "d"), (400, "cd"), (100, "c"), (90, "xc"), (50, "l"), (40, "xl"),
            (10, "x"), (9, "ix"), (5, "v"), (4, "iv"), (1, "i")]
    out = ""
    for v, r in vals:
        while n >= v:
            out += r
            n -= v
    return out


def alph(n: int) -> str:
    if n <= 0:
        return str(n)
    s = ""
    while n > 0:
        n, r = divmod(n - 1, 26)
        s = chr(97 + r) + s
    return s


FNSYMBOLS = ["*", "†", "‡", "§", "¶", "‖", "**", "††", "‡‡"]


def numfmt(style: str, n: int) -> str:
    if style == "arabic":
        return str(n)
    if style == "roman":
        return roman(n)
    if style == "Roman":
        return roman(n).upper()
    if style == "alph":
        return alph(n)
    if style == "Alph":
        return alph(n).upper()
    if style == "fnsymbol":
        return FNSYMBOLS[n - 1] if 0 < n <= len(FNSYMBOLS) else str(n)
    return str(n)


SAFE_SCHEMES = ("http://", "https://", "mailto:", "ftp://")


def clean_url(u: str) -> str:
    u = re.sub(r"\\([#%_&~$])", r"\1", u.strip())
    u = re.sub(r"\s+", "", u)
    return u


# Hosts that serve the same address over https: a bibliography's http:// link to one of
# them is followed as https (the printed text stays as the paper prints it).
HTTPS_HOSTS = {
    "hdl.handle.net", "doi.org", "dx.doi.org", "arxiv.org", "www.arxiv.org", "export.arxiv.org", "www.ams.org",
    "ams.org", "mathscinet.ams.org", "zbmath.org", "www.zbmath.org", "eudml.org", "www.numdam.org", "numdam.org",
    "projecteuclid.org", "www.jstor.org", "jstor.org", "link.springer.com", "onlinelibrary.wiley.com",
    "www.sciencedirect.com", "oeis.org", "www.oeis.org", "en.wikipedia.org", "github.com", "mathoverflow.net",
    "math.stackexchange.com", "msp.org", "www.cambridge.org", "academic.oup.com", "epubs.siam.org", "dl.acm.org",
    "ieeexplore.ieee.org", "www.worldscientific.com", "citeseerx.ist.psu.edu", "www.emis.de", "emis.de",
    "annals.math.princeton.edu", "www.ems-ph.org", "ems.press", "www.semanticscholar.org", "inspirehep.net",
    "repository.kulib.kyoto-u.ac.jp", "www.kurims.kyoto-u.ac.jp", "www.mathnet.ru", "mathnet.ru", "www.lmfdb.org",
    "lmfdb.org", "www.math.ias.edu", "www.ihes.fr", "www.numdam.org",
}


def safe_href(u: str) -> str | None:
    u = clean_url(u)
    m = re.match(r"(?i)^http://([^/:?#]+)", u)
    if m and m.group(1).lower() in HTTPS_HOSTS:
        u = "https://" + u[len("http://"):]
    if u.lower().startswith(SAFE_SCHEMES):
        return u
    if re.match(r"^(www\.)", u):
        return "https://" + u
    return None


def frag_href(label: str) -> str:
    return "#" + quote(label, safe=":/@!$&'()*+,;=-._~[]")


# ------------------------------------------------------------ TeX scanning

CS_RE = re.compile(r"\\(@(?![A-Za-z])|[A-Za-z@]+|.)", re.S)
PLAIN_RE = re.compile(r"[^\\${}~\n\-`'%&#^_\x00-\x1f]+")
BRACE_RE = re.compile(r"[\\{}]")
WORD_CS = re.compile(r"[A-Za-z@]")


def match_brace(s: str, i: int, end: int) -> int:
    """s[i] == '{'. Return the index just after its matching '}' (or end)."""
    depth = 0
    k = i
    while True:
        m = BRACE_RE.search(s, k, end)
        if not m:
            return end
        k = m.start()
        c = s[k]
        if c == "\\":
            k += 2
            continue
        if c == "{":
            depth += 1
        else:
            depth -= 1
            if depth == 0:
                return k + 1
        k += 1


def skip_ws(s: str, i: int, end: int) -> int:
    while i < end and s[i] in " \t\n":
        i += 1
    return i


def skip_space_after_word(s: str, i: int, end: int) -> int:
    """TeX ignores spaces (and one newline) after a control word."""
    k = i
    while k < end and s[k] in " \t":
        k += 1
    if k < end and s[k] == "\n":
        k2 = k + 1
        while k2 < end and s[k2] in " \t":
            k2 += 1
        if k2 < end and s[k2] == "\n":
            return k  # a paragraph break stays
        k = k2
    return k


def read_arg(s: str, i: int, end: int):
    """One TeX argument: a braced group's content, a control sequence or a character."""
    k = skip_ws(s, i, end)
    if k >= end:
        return "", k
    c = s[k]
    if c == "{":
        j = match_brace(s, k, end)
        return s[k + 1:j - 1], j
    if c == "\\":
        m = CS_RE.match(s, k)
        if m:
            return m.group(0), m.end()
    if c in "}":
        return "", k
    return c, k + 1


def read_opt(s: str, i: int, end: int):
    """An optional [argument]: the text up to the first ']' outside braces."""
    k = skip_ws(s, i, end)
    if k < end and s[k] == "[":
        depth = 0
        j = k + 1
        while j < end:
            c = s[j]
            if c == "\\":
                j += 2
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            elif c == "]" and depth == 0:
                return s[k + 1:j], j + 1
            j += 1
        return s[k + 1:end], end
    return None, i


def read_star(s: str, i: int, end: int):
    if i < end and s[i] == "*":
        return True, i + 1
    return False, i


def read_paren(s: str, i: int, end: int):
    k = skip_ws(s, i, end)
    if k < end and s[k] == "(":
        j = s.find(")", k, end)
        if j > 0:
            return s[k + 1:j], j + 1
    return None, i


ENV_TAG = re.compile(r"\\(begin|end)\s*\{([^{}]+)\}")


def find_env_end(s: str, i: int, name: str, end: int):
    """i is just after \\begin{name}. Return (body_end, after_end)."""
    pat = re.compile(r"\\(begin|end)\s*\{" + re.escape(name) + r"\}")
    depth = 1
    for m in pat.finditer(s, i, end):
        depth += 1 if m.group(1) == "begin" else -1
        if depth == 0:
            return m.start(), m.end()
    return end, end


def top_level(s: str, i: int, end: int, pattern: re.Pattern):
    """Positions where pattern matches outside braces and nested environments."""
    hits = []
    k = i
    while k < end:
        c = s[k]
        if c == "{":
            k = match_brace(s, k, end)
            continue
        if c == "\\":
            if s.startswith("\\begin", k):
                m = ENV_TAG.match(s, k)
                if m and m.group(1) == "begin":
                    _, after = find_env_end(s, m.end(), m.group(2), end)
                    k = after
                    continue
            m = pattern.match(s, k)
            if m:
                hits.append((k, m.end()))
                k = max(m.end(), k + 1)
                continue
            m = CS_RE.match(s, k)
            k = m.end() if m else k + 1
            continue
        m = pattern.match(s, k)
        if m:
            hits.append((k, m.end()))
            k = max(m.end(), k + 1)
            continue
        k += 1
    return hits


def split_top(s: str, i: int, end: int, pattern: re.Pattern):
    """Split s[i:end] at top-level matches of pattern: list of (start, end, separator)."""
    parts = []
    pos = i
    for a, b in top_level(s, i, end, pattern):
        parts.append((pos, a, s[a:b]))
        pos = b
    parts.append((pos, end, ""))
    return parts


def find_math_end(s: str, i: int, end: int, closer: str) -> int:
    """Index of the closing delimiter for math starting at i (just after the opener)."""
    k = i
    depth = 0
    while k < end:
        c = s[k]
        if c == "\\":
            if closer in ("\\)", "\\]") and s.startswith(closer, k) and depth <= 0:
                return k
            k += 2
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        elif c == "$" and closer.startswith("$") and depth <= 0:
            if closer == "$$":
                if s.startswith("$$", k):
                    return k
            else:
                return k
        k += 1
    return end


# ------------------------------------------------------------ definitions

class Macro:
    __slots__ = ("name", "nargs", "default", "body", "params", "kind", "extra")

    def __init__(self, name, nargs=0, default=None, body="", params=None, kind="cmd", extra=None):
        self.name = name
        self.nargs = nargs
        self.default = default
        self.body = body
        self.params = params
        self.kind = kind
        self.extra = extra


DEF_RE = re.compile(
    r"\\(newcommand|renewcommand|providecommand|DeclareRobustCommand|DeclareMathOperator|"
    r"DeclarePairedDelimiterXPP|DeclarePairedDelimiterX|DeclarePairedDelimiter|newenvironment|renewenvironment|"
    r"newtheorem|theoremstyle|numberwithin|counterwithin|counterwithout|newcounter|crefname|Crefname|crefalias|"
    r"NewCommandCopy|RenewCommandCopy|DeclareCommandCopy|LetLtxMacro|"
    r"def|gdef|edef|xdef|let|expandafter|newtheoremstyle|setcounter|bibliographystyle|appendix|@namedef|"
    r"begin\s*\{document\})(?![A-Za-z@])")
COPY_CMDS = {"NewCommandCopy", "RenewCommandCopy", "DeclareCommandCopy", "LetLtxMacro"}
DEF_CMDS = {"newcommand", "renewcommand", "providecommand", "DeclareRobustCommand", "DeclareMathOperator",
            "DeclarePairedDelimiter", "DeclarePairedDelimiterX", "DeclarePairedDelimiterXPP", "newenvironment",
            "renewenvironment", "newtheorem", "theoremstyle", "numberwithin", "counterwithin", "counterwithout",
            "newcounter", "crefname", "Crefname", "crefalias", "def", "gdef", "edef", "xdef", "let", "newtheoremstyle",
            "@namedef",
            *COPY_CMDS}


def read_cs_name(s: str, i: int, end: int):
    """Read a macro name given as \\name, {\\name} or {name}: return (name, j)."""
    k = skip_ws(s, i, end)
    if k < end and s[k] == "{":
        j = match_brace(s, k, end)
        inner = s[k + 1:j - 1].strip()
        if inner.startswith("\\"):
            inner = inner[1:]
        return inner, j
    if k < end and s[k] == "\\":
        m = CS_RE.match(s, k)
        if m:
            if m.group(1) == "csname":  # \csname name\endcsname spells the name out
                e = s.find("\\endcsname", m.end(), end)
                if e >= 0:
                    return s[m.end():e].strip(), e + len("\\endcsname")
            return m.group(1), m.end()
    return None, k


def skip_expandafter(s: str, k: int, end: int) -> int:
    """Skip spaces and \\expandafter tokens (\\expandafter\\let\\expandafter\\x\\csname ...)."""
    k = skip_ws(s, k, end)
    while s.startswith("\\expandafter", k, end):
        k = skip_ws(s, k + len("\\expandafter"), end)
    return k


# Assignments that only matter to TeX: a \let (also spelled with \expandafter and \csname) and
# pdfTeX's \pdfliteral. Left in a macro body bound for KaTeX, their names would be expanded as
# formulas; a body that re-lets the macros that call it then grows without end.
LET_STMT_RE = re.compile(
    r"(?:\\expandafter\s*)?\\(?:global\s*\\)?let(?![A-Za-z@])\s*(?:\\expandafter\s*)?"
    r"(?:\\csname\s*[^\\]*?\\endcsname|\\[A-Za-z@]+|\\.)\s*=?\s*"
    r"(?:\\csname\s*[^\\]*?\\endcsname|\\[A-Za-z@]+|\\.|[^\\\s])")
PDFLITERAL_RE = re.compile(r"\\pdfliteral(?![A-Za-z@])\s*(?:direct|page)?\s*\{[^{}]*\}")


def strip_assignments(tex: str) -> str:
    return PDFLITERAL_RE.sub("", LET_STMT_RE.sub("", tex))


def parse_def_params(params: str):
    """\\def parameter text: (nargs, delimited token list or None)."""
    p = params.strip()
    if not p:
        return 0, None
    if re.fullmatch(r"(?:#[1-9])+", p):
        return len(re.findall(r"#[1-9]", p)), None
    toks = []
    k = 0
    while k < len(p):
        if p[k] == "#" and k + 1 < len(p) and p[k + 1].isdigit():
            toks.append(int(p[k + 1]))
            k += 2
        elif p[k] == "\\":
            m = CS_RE.match(p, k)
            toks.append(m.group(0))
            k = m.end()
        elif p[k] in " \t\n":
            k += 1
        else:
            toks.append(p[k])
            k += 1
    return len([t for t in toks if isinstance(t, int)]), toks


# ------------------------------------------------------------ text-mode tables

TEXT_SYMBOLS = {
    "tablename": "Table", "figurename": "Figure",
    "S": "§", "P": "¶", "dag": "†", "ddag": "‡", "copyright": "©", "textcopyright": "©", "textregistered": "®",
    "texttrademark": "™", "pounds": "£", "textsterling": "£", "euro": "€", "texteuro": "€", "textdollar": "$",
    "textbackslash": "\\", "textasciitilde": "~", "textasciicircum": "^", "textbar": "|", "textless": "&lt;",
    "textgreater": "&gt;", "textbullet": "•", "textperiodcentered": "·", "textquotedblleft": "“",
    "textquotedblright": "”", "textquoteleft": "‘", "textquoteright": "’", "textquotedbl": '"',
    "textquotesingle": "'", "textendash": "–", "textemdash": "—", "textellipsis": "…", "ldots": "…", "dots": "…",
    "cdots": "⋯", "textdegree": "°", "textmu": "µ", "texttimes": "×", "textpm": "±", "checkmark": "✓",
    "textexclamdown": "¡", "textquestiondown": "¿", "guillemotleft": "«", "guillemotright": "»",
    "textsection": "§", "textparagraph": "¶", "textdagger": "†", "textdaggerdbl": "‡", "LaTeX": "LaTeX",
    "TeX": "TeX", "LaTeXe": "LaTeX2ε", "BibTeX": "BibTeX", "AmS": "AMS", "ss": "ß", "SS": "SS", "ae": "æ",
    "AE": "Æ", "oe": "œ", "OE": "Œ", "aa": "å", "AA": "Å", "o": "ø", "O": "Ø", "l": "ł", "L": "Ł", "i": "ı",
    "j": "ȷ", "dh": "ð", "DH": "Ð", "th": "þ", "TH": "Þ", "ng": "ŋ", "NG": "Ŋ", "dj": "đ", "DJ": "Đ",
    "quad": "\u2003", "qquad": "\u2003\u2003", "enspace": "\u2002", "thinspace": "\u2009", "negthinspace": "",
    "enskip": "\u2002", "space": " ", "nobreakspace": "\u00a0", "textvisiblespace": "␣", "textunderscore": "_",
    "slash": "/", "textslash": "/", "textbraceleft": "{", "textbraceright": "}", "textasteriskcentered": "∗",
    "textonehalf": "½", "textdiv": "÷", "textlnot": "¬", "textminus": "−", "textlangle": "⟨", "textrangle": "⟩",
    "textleftarrow": "←", "textrightarrow": "→", "textcent": "¢", "textyen": "¥", "textnumero": "№",
    "textordfeminine": "ª", "textordmasculine": "º", "qedsymbol": "□", "qed": "", "textasciiacute": "´",
    "textasciidieresis": "¨", "textasciimacron": "¯", "textthreequarters": "¾", "textonequarter": "¼",
    "textrightarrow": "→", "textsuperscriptone": "¹", "textcopyleft": "🄯", "dotsc": "…", "dotsb": "⋯",
    "hellip": "…", "textcompwordmark": "", "nobreakdash": "", "ignorespacesafterend": "",
}
CONTROL_SYMBOLS = {
    "&": "&amp;", "%": "%", "$": "$", "#": "#", "_": "_", "{": "{", "}": "}", ",": "\u2009", " ": " ",
    "\n": " ", "\t": " ", ";": "\u2005", ":": "\u2005", "!": "", "@": "", "/": "", "-": "", ">": "\u2003",
    "<": "", "|": "‖", "'": None, "`": None,
}
ACCENTS = {"'": "\u0301", "`": "\u0300", "^": "\u0302", '"': "\u0308", "~": "\u0303", "=": "\u0304",
           ".": "\u0307", "u": "\u0306", "v": "\u030c", "H": "\u030b", "c": "\u0327", "k": "\u0328",
           "r": "\u030a", "d": "\u0323", "b": "\u0331", "t": "\u0361", "textcommabelow": "\u0326"}
SPACING_ACCENT = {"'": "´", "`": "`", "^": "^", '"': "¨", "~": "~", "=": "¯", ".": "˙"}
FONT_ARG = {"emph": ("<em>", "</em>"), "textit": ("<i>", "</i>"), "textsl": ("<i>", "</i>"),
            "textbf": ("<b>", "</b>"), "textsc": ('<span class="pr-sc">', "</span>"),
            "texttt": ("<code>", "</code>"), "textsf": ('<span class="pr-sf">', "</span>"),
            "underline": ("<u>", "</u>"), "uline": ("<u>", "</u>"), "sout": ("<s>", "</s>"),
            "textsuperscript": ("<sup>", "</sup>"), "textsubscript": ("<sub>", "</sub>"),
            "fbox": ('<span class="pr-fbox">', "</span>"), "framebox": ('<span class="pr-fbox">', "</span>"),
            "boxed": ('<span class="pr-fbox">', "</span>"), "textmd": ("", ""), "textrm": ("", ""),
            "textup": ("", ""), "textnormal": ("", ""), "text": ("", ""), "mbox": ("", ""), "hbox": ("", ""),
            "nolinkurl": ("<code>", "</code>"), "textls": ("", ""), "foreignlanguage": None,
            "textssc": ('<span class="pr-sc">', "</span>"), "textsw": ("", ""), "textulc": ("", ""),
            "cjk": ("", ""), "mathrm": ("", ""), "textcolor": None, "colorbox": None, "emphasis": ("<em>", "</em>"),
            "makebox": ("", ""), "shortstack": ('<span class="pr-stack">', "</span>"), "NoCaseChange": ("", "")}
FONT_SWITCH = {"bf": ("<b>", "</b>"), "bfseries": ("<b>", "</b>"), "it": ("<i>", "</i>"),
               "itshape": ("<i>", "</i>"), "em": ("<em>", "</em>"), "sl": ("<i>", "</i>"),
               "slshape": ("<i>", "</i>"), "sc": ('<span class="pr-sc">', "</span>"),
               "scshape": ('<span class="pr-sc">', "</span>"), "tt": ("<code>", "</code>"),
               "ttfamily": ("<code>", "</code>"), "sffamily": ('<span class="pr-sf">', "</span>"),
               "sf": ('<span class="pr-sf">', "</span>")}
# Commands that produce nothing on a web page, with the number of braced arguments
# (and optional arguments) they consume.
IGNORE = {
    # no arguments
    **{k: 0 for k in (
        "noindent indent par_ignored smallskip medskip bigskip centering raggedright raggedleft RaggedRight "
        "flushbottom raggedbottom normalfont upshape rmfamily mdseries normalsize small footnotesize scriptsize "
        "tiny large Large LARGE huge Huge selectfont nobreak allowbreak break relax protect hfill hfil hss vfill "
        "vfil null leavevmode unskip ignorespaces newpage clearpage cleardoublepage pagebreak nopagebreak "
        "linebreak nolinebreak samepage sloppy fussy FloatBarrier balance phantomsection maketitle tableofcontents "
        "listoffigures listoftables displaystyle textstyle scriptstyle strut mathstrut begingroup endgroup "
        "bgroup egroup makeatletter makeatother appendixpage frenchspacing nonfrenchspacing onecolumn twocolumn "
        "qedhere nopagebreak allowdisplaybreaks displaybreak boldmath unboldmath normalcolor printindex "
        "thispagestyle_ignored hline toprule midrule bottomrule endhead endfirsthead endfoot endlastfoot "
        "noalign_ignored tabularnewline_ignored newblock blankline vss expandafter noexpand protected long "
        "global outer FloatBarrier suppressfloats clearpage onehalfspacing doublespacing singlespacing "
        "justifying unhbox nointerlineskip offinterlineskip abovedisplayskip_ignored ignorespacesafterend "
        "IfFileExists_ignored pdfbookmark_ignored endinput hypersetup_ignored stepcounter_ignored "
        "printbibliography_ignored nocite_ignored mainmatter frontmatter backmatter rm").split()},
    # one braced argument
    **{k: 1 for k in (
        "label_ignored vspace hspace_ignored index glossary pagestyle thispagestyle pagenumbering enlargethispage "
        "hypersetup setlist captionsetup tikzset usetikzlibrary pgfplotsset bibliographystyle color "
        "markright addvspace input_ignored include includeonly theoremstyle usepackage RequirePackage "
        "hyphenation looseness_ignored pdfstringdefDisableCommands crefformat_ignored urlstyle "
        "selectlanguage newlength newsavebox nocite_ignored DeclareGraphicsExtensions graphicspath "
        "setcounter_ignored keywords_ignored linespread pdfbookmark_ignored thanks_ignored newif "
        "AtBeginDocument AtEndDocument tcbset lstset sisetup FloatBlock subjclass_ignored Needspace needspace "
        "fontencoding bookmark title author date").split()},
    # two braced arguments
    **{k: 2 for k in (
        "setlength addtolength settowidth settoheight settodepth markboth addtocontents numberwithin "
        "counterwithin counterwithout crefalias fontsize newcounter_ignored definecolor_ignored "
        "crefformat Crefformat creflabelformat crefrangeformat Crefrangeformat crefmultiformat "
        "Crefmultiformat crefrangelabelformat crefdefaultlabelformat colorlet setcounter_ignored "
        "pgfmathsetmacro pgfmathtruncatemacro savebox sbox pdfbookmark AddToHook").split()},
    # three braced arguments
    **{k: 3 for k in ("addcontentsline definecolor crefname Crefname newtheorem_ignored DeclareFontShape_ignored").split()},
}
for _k in [k for k in IGNORE if k.endswith("_ignored")]:
    del IGNORE[_k]
DIMEN_PRIMITIVES = {
    "looseness", "parindent", "parskip", "emergencystretch", "tolerance", "pretolerance", "hfuzz", "vfuzz",
    "hbadness", "vbadness", "interlinepenalty", "clubpenalty", "widowpenalty", "displaywidowpenalty",
    "predisplaypenalty", "postdisplaypenalty", "abovedisplayskip", "belowdisplayskip", "abovedisplayshortskip",
    "belowdisplayshortskip", "arraycolsep", "tabcolsep", "baselineskip", "lineskip", "lineskiplimit", "jot",
    "mathsurround", "leftskip", "rightskip", "parfillskip", "vskip", "hskip", "kern", "penalty", "mskip",
    "mkern", "hyphenpenalty", "exhyphenpenalty", "binoppenalty", "relpenalty", "linepenalty", "doublehyphendemerits",
    "finalhyphendemerits", "adjdemerits", "brokenpenalty", "floatsep", "textfloatsep", "intextsep",
    "itemsep", "topsep", "partopsep", "labelsep", "leftmargin", "rightmargin", "listparindent", "itemindent",
    "labelwidth", "fboxsep", "fboxrule", "arrayrulewidth", "doublerulesep", "extrarowheight", "footnotesep",
    "medmuskip", "thinmuskip", "thickmuskip", "lineskiplimits", "delimitershortfall", "nulldelimiterspace",
    "scriptspace", "hangindent", "hangafter", "spaceskip", "xspaceskip", "baselinestretch", "vbadness",
    # hyphenation and page-builder parameters (\lefthyphenmin=2): nothing on a web page
    "lefthyphenmin", "righthyphenmin", "uchyph", "defaulthyphenchar", "pagegoal", "pagetotal", "pagedepth",
    "pagestretch", "pageshrink", "maxdepth", "topskip", "splittopskip", "vsize", "hsize", "textheight",
}
# \dimen0=\pagegoal, \count255=3: a register assignment, which prints nothing.
REGISTER_PRIMITIVES = {"dimen", "count", "skip", "muskip", "toks"}
# \advance\dimen0 by -\pagetotal: register arithmetic, which prints nothing.
ARITH_PRIMITIVES = {"advance", "multiply", "divide"}
DIMEN_RE = re.compile(
    r"\s*=?\s*(?:[-+]?\s*(?:\d+(?:\.\d*)?|\.\d+)?\s*(?:\\[A-Za-z@]+|(?:pt|em|ex|cm|mm|in|bp|pc|dd|cc|sp|mu|fil+|true\s*pt)?))"
    r"(?:\s*(?:plus|minus)\s*[-+]?\s*(?:\d+(?:\.\d*)?|\.\d+)?\s*(?:pt|em|ex|cm|mm|in|bp|pc|dd|cc|sp|mu|fil+|\\[A-Za-z@]+)?)*")

REGISTER_RE = re.compile(r"\s*(?:\d+|@+[A-Za-z]*)?" + DIMEN_RE.pattern)
ARITH_RE = re.compile(r"\s*\\(?:(?:dimen|count|skip|muskip)\s*(?:\d+|@+[A-Za-z]*)?|[A-Za-z@]+)\s*(?:by(?![A-Za-z]))?"
                      + DIMEN_RE.pattern)
LEVELS = {"part": 0, "chapter": 0, "section": 1, "subsection": 2, "subsubsection": 3, "paragraph": 4,
          "subparagraph": 5}
REF_CMDS = {"ref", "eqref", "cref", "Cref", "autoref", "Autoref", "labelcref", "crefrange", "Crefrange",
            "cpageref", "Cpageref", "pageref", "nameref", "Nameref", "vref", "Vref", "subref", "namecref",
            "nameCref", "lcnamecref", "thmref", "eqrefs", "cpagerefrange"}
CITE_CMDS = {"cite", "citep", "citet", "citealp", "citealt", "citeauthor", "citeyear", "citeyearpar",
             "Citep", "Citet", "Citealp", "Citealt", "Citeauthor", "parencite", "textcite", "autocite",
             "Parencite", "Textcite", "Autocite", "footcite", "cites", "citenum", "citetext", "supercite",
             "nocite"}
THEOREM_PLACEHOLDER_ENVS = {"tikzpicture", "tikzcd", "picture", "pgfpicture", "forest", "circuitikz", "axis",
                            "xy", "tikzpicture*", "dot2tex", "asy", "pspicture", "overpic", "sagesilent",
                            "chemfig", "dynkinDiagram"}
MATH_ENVS = {"equation", "equation*", "align", "align*", "gather", "gather*", "multline", "multline*",
             "flalign", "flalign*", "alignat", "alignat*", "eqnarray", "eqnarray*", "displaymath", "math",
             "dmath", "dmath*", "dgroup", "dgroup*"}
MATH_ONLY_ENVS = {"aligned", "gathered", "split", "cases", "dcases", "rcases", "array", "matrix", "pmatrix",
                  "bmatrix", "Bmatrix", "vmatrix", "Vmatrix", "smallmatrix", "psmallmatrix", "bsmallmatrix",
                  "alignedat", "CD", "subarray", "multlined", "darray"}
CONTAINER_ENVS = {"center", "flushleft", "flushright", "quote", "quotation", "verse", "minipage", "samepage",
                  "small", "footnotesize", "scriptsize", "normalsize", "large", "Large", "tiny", "multicols",
                  "multicols*", "adjustwidth", "spacing", "singlespace", "onehalfspace", "doublespace",
                  "sloppypar", "landscape", "framed", "mdframed", "tcolorbox", "boxedminipage", "titlepage",
                  "linenomath", "fleqn", "raggedright", "RaggedRight", "Center", "FlushLeft", "FlushRight",
                  "itshape", "bfseries", "upshape", "list", "trivlist", "otherlanguage", "otherlanguage*",
                  "english", "addmargin", "leftbar", "shaded", "snugshade", "description*", "NoHyper",
                  "fullwidth", "widepage", "abstract*", "frame", "block", "tabbing_ignored", "noindent",
                  "comment_ignored", "centering", "figure_body", "landscape*", "absolutelynopagebreak",
                  "minipage*", "nolinenumbers", "parbox", "lrbox_ignored", "subappendices", "keepcolumns"}
VERBATIM_ENVS = {"verbatim", "verbatim*", "Verbatim", "lstlisting", "minted", "alltt", "BVerbatim",
                 "LVerbatim", "Verbatim*", "code", "spverbatim", "lstlisting*"}
TABLE_ENVS = {"tabular", "tabular*", "tabularx", "longtable", "longtable*", "tabulary", "tabu", "supertabular",
              "xtabular", "NiceTabular", "tblr", "longtblr", "array_text"}
FLOAT_ENVS = {"figure", "figure*", "table", "table*", "wrapfigure", "wraptable", "SCfigure", "sidewaysfigure",
              "sidewaystable", "subfigure", "subtable", "algorithm", "algorithm*", "listing", "floatrow"}
LIST_ENVS = {"enumerate", "itemize", "description", "compactenum", "compactitem", "compactdesc", "inparaenum",
             "asparaenum", "enumerate*", "itemize*", "inparaitem", "steps", "conditions"}
DEFAULT_THM_ENVS_UNDECLARED = {}

CREF_DEFAULT = {
    # type: (singular, plural, abbreviated singular, abbreviated plural)
    "equation": ("equation", "equations", "eq.", "eqs."),
    "figure": ("figure", "figures", "fig.", "figs."),
    "table": ("table", "tables", "table", "tables"),
    "page": ("page", "pages", "page", "pages"),
    "part": ("part", "parts", "part", "parts"),
    "chapter": ("chapter", "chapters", "chapter", "chapters"),
    "section": ("section", "sections", "section", "sections"),
    "subsection": ("section", "sections", "section", "sections"),
    "subsubsection": ("section", "sections", "section", "sections"),
    "paragraph": ("paragraph", "paragraphs", "paragraph", "paragraphs"),
    "appendix": ("appendix", "appendices", "appendix", "appendices"),
    "subappendix": ("appendix", "appendices", "appendix", "appendices"),
    "subsubappendix": ("appendix", "appendices", "appendix", "appendices"),
    "enumi": ("item", "items", "item", "items"),
    "enumii": ("item", "items", "item", "items"),
    "enumiii": ("item", "items", "item", "items"),
    "enumiv": ("item", "items", "item", "items"),
    "footnote": ("footnote", "footnotes", "footnote", "footnotes"),
    "theorem": ("theorem", "theorems", "thm.", "thms."),
    "lemma": ("lemma", "lemmas", "lem.", "lems."),
    "corollary": ("corollary", "corollaries", "cor.", "cors."),
    "proposition": ("proposition", "propositions", "prop.", "props."),
    "definition": ("definition", "definitions", "defn.", "defns."),
    "result": ("result", "results", "result", "results"),
    "example": ("example", "examples", "ex.", "exs."),
    "remark": ("remark", "remarks", "rem.", "rems."),
    "note": ("note", "notes", "note", "notes"),
    "algorithm": ("algorithm", "algorithms", "alg.", "algs."),
    "listing": ("listing", "listings", "listing", "listings"),
    "line": ("line", "lines", "line", "lines"),
}

# Commands from LaTeX packages that KaTeX lacks, given their standard meanings. The
# paper's own definitions always win over these.
SUPPORT_MACROS = {
    "\\bm": "\\boldsymbol{#1}",
    "\\mathbbm": "\\mathbb{#1}",
    "\\mathds": "\\mathbb{#1}",
    "\\ensuremath": "#1",
    "\\xspace": "",
    "\\mbox": "\\text{#1}",
    "\\textsc": "\\textrm{#1}",
    "\\textsl": "\\textit{#1}",
    "\\hdots": "\\ldots",
    "\\nicefrac": "{}^{#1}\\!/\\!{}_{#2}",
    "\\sfrac": "{}^{#1}\\!/\\!{}_{#2}",
    "\\textsuperscript": "^{\\text{#1}}",
    "\\textsubscript": "_{\\text{#1}}",
    "\\widebar": "\\overline{#1}",
    "\\lefteqn": "\\rlap{$#1$}",
    "\\protect": "",
    "\\nobreakdash": "",
    "\\textmd": "\\textrm{#1}",
    # No \fbox here: KaTeX has its own \fbox and defines \boxed through it, so a \fbox
    # macro written with \boxed loops on every boxed formula.
    # accsupp and pdfTeX commands that only mark up the PDF: their arguments are dropped.
    "\\BeginAccSupp": "\\@secondoftwo{#1}{}",
    "\\EndAccSupp": "\\@secondoftwo{#1}{}",
    "\\pdfliteral": "\\@secondoftwo{#1}{}",
    "\\setlength": "\\@secondoftwo{#1#2}{}",
    "\\smallskip": "", "\\medskip": "", "\\bigskip": "",
    "\\dasharrow": "\\dashrightarrow",
    "\\toprule": "\\hline", "\\midrule": "\\hline", "\\bottomrule": "\\hline",
    # the average integral: an integral sign with a bar through it
    "\\fint": "\\mathop{\\rlap{\\hspace{0.18em}\\raisebox{0.05em}{$-$}}\\int}\\nolimits",
    "\\upalpha": "\\alpha", "\\upbeta": "\\beta", "\\upgamma": "\\gamma", "\\updelta": "\\delta",
    "\\upepsilon": "\\epsilon", "\\upmu": "\\mu", "\\uppi": "\\pi", "\\upsigma": "\\sigma", "\\uptau": "\\tau",
    "\\upphi": "\\phi", "\\upomega": "\\omega", "\\uplambda": "\\lambda", "\\uprho": "\\rho", "\\upeta": "\\eta",
    "\\upxi": "\\xi", "\\upzeta": "\\zeta", "\\uptheta": "\\theta", "\\upkappa": "\\kappa", "\\upnu": "\\nu",
    "\\upchi": "\\chi", "\\uppsi": "\\psi", "\\upiota": "\\iota",
}
# Constructs in a macro body that only the Python expander can carry.
PY_ONLY_BODY = re.compile(
    r"\\(?:ref|eqref|cref|Cref|autoref|Autoref|labelcref|pageref|cpageref|nameref|hyperref|label|cite[a-zA-Z]*|"
    r"Cite[a-zA-Z]*|nocite|footnote|csname|ifcsname|expandafter|ifx|ifdefined|ifmmode|ifnum|ifdim|ifthenelse|"
    r"@ifnextchar|@ifstar|@ifundefined|ifblank|IfBooleanTF|IfValueTF|NewDocumentCommand|newcommand|renewcommand|"
    r"def|gdef|edef|xdef|let|refstepcounter|stepcounter|setcounter|addtocounter|the[a-z]+|arabic|roman|alph|Alph|"
    r"Roman|value|begin|end|item|section|subsection|par|vspace|bigskip|medskip|smallskip|noindent|newline|"
    r"hyperlink|hypertarget|url|href|includegraphics|tikz|input|caption)(?![A-Za-z@])")
MATH_REF_RE = re.compile(
    r"\\(eqref|ref|cref|Cref|autoref|Autoref|labelcref|pageref|cpageref|nameref|namecref|nameCref|crefrange|"
    r"Crefrange|vref|subref)(\*?)(?![A-Za-z@])\s*(?:\[[^\]]*\]\s*)?\{([^{}]*)\}(?:\s*\{([^{}]*)\})?")
MATH_CITE_RE = re.compile(
    r"\\(cite[a-zA-Z]*|Cite[a-zA-Z]*|parencite|textcite)(\*?)(?![A-Za-z@])\s*((?:\[[^\]]*\]\s*){0,2})\{([^{}]*)\}")
LABEL_RE = re.compile(r"\\label\s*\{([^{}]*)\}")
NONUM_RE = re.compile(r"\\(?:nonumber|notag)(?![A-Za-z@])")
TAG_RE = re.compile(r"\\tag(\*?)\s*\{")
QEDHERE_RE = re.compile(r"\\qedhere(?![A-Za-z@])")
ROW_SEP = re.compile(r"\\\\\*?(?:\s*\[[^\]]*\])?|\\cr(?![A-Za-z@])|\\tabularnewline(?![A-Za-z@])")
INTERTEXT_RE = re.compile(r"\\(?:intertext|shortintertext)(?![A-Za-z@])")


# ------------------------------------------------------------ the converter

class Paper:
    """One manuscript: its expanded TeX, its definitions, and the converted page."""

    def __init__(self, m: dict, upstream: Path):
        self.m = m
        self.slug = m["id"]
        self.mdir = upstream / "preprints" / self.slug
        rel = (m.get("tex") or {}).get("main")
        self.main = (self.mdir / rel) if rel else bd.find_main_tex(self.mdir)
        if not self.main or not self.main.is_file():
            raise FileNotFoundError("no main TeX file")
        # LaTeX resolves \input against the directory it runs in, the main file's
        # directory, so expand from there and report paths relative to the manuscript.
        base = self.main.parent
        lines = bd.expand_tex(self.main, base)
        prefix = base.relative_to(self.mdir).as_posix() if base != self.mdir else ""
        lines = [(CTRL_RE.sub(" ", t), (f"{prefix}/{f}" if prefix else f), n) for t, f, n in lines]
        self.doc = bd.TexDoc(lines)
        self.text = self.doc.text
        self.raw_lines = {}
        # definitions
        self.macros: dict[str, Macro] = {}
        self.envdefs: dict[str, tuple] = {}
        self.thm: dict[str, dict] = {}
        self.thm_style = "plain"
        self.counters: Counter = Counter()
        self.fmt: dict[str, str] = {}
        self.reset: dict[str, list] = defaultdict(list)
        self.crefnames: dict[str, tuple] = {}
        self.Crefnames: dict[str, tuple] = {}
        self.crefalias: dict[str, str] = {}
        self.cref_opts: set = set()
        self.natbib_opts: set = set()
        self.bibstyle = None
        self.docclass = "article"
        self.class_opts: set = set()
        self.secnumdepth = 3
        self.untranslated: dict[str, str] = {}
        self.included_pdfs: list[str] = []
        # conversion state
        self.ctxs: list[dict] = []
        self.cur = None
        self.labels: dict[str, dict] = {}
        self.dup_labels: list = []
        self.placeholders: list[tuple] = []
        self.formulas: list[dict] = []
        self.footnotes: list[dict] = []
        self.toc: list[tuple] = []
        self.unknown_cmds: Counter = Counter()
        self.unknown_envs: Counter = Counter()
        self.unknown_examples: dict[str, str] = {}
        self.figures: Counter = Counter()
        self.cite_order: list[str] = []
        self.cite_seen: set = set()
        self.cite_total = 0
        self.ref_total = 0
        self.nocite_all = False
        self.thebib = None
        self.bibfiles: list[str] = []
        self.bib_html = ""
        self.in_appendix = False
        self.depth = 0
        self.subeq = None
        self.list_depth = 0
        self.enum_depth = 0
        self.enum_last: dict[int, int] = {}
        self.title_tex = None
        self.author_tex = None
        self.date_tex = None
        self.abstract_tex = None
        self.abstract_off = None
        self.thm_lines: dict[str, str] = {}
        self.printed: dict[tuple, tuple] = {}   # (file, line) -> (kind as printed, number or None)
        self.float_kind = None
        self.float_ctx = None
        self.float_captions = 0
        self.python_macros: set = set()
        self.katex: dict[str, str] = {}
        self.leqno = False
        self.fleqn = False
        self.errors: list[str] = []
        self.init_counters()

    # ------------------------------------------------------------ locations

    def loc(self, off: int):
        return self.doc.loc(max(0, min(off, len(self.text) - 1)))

    def where(self, off) -> str:
        if off is None:
            return ""
        f, n = self.loc(off)
        return f"{f}:{n}"

    def raw_file_lines(self, rel: str):
        if rel not in self.raw_lines:
            try:
                self.raw_lines[rel] = (self.mdir / rel).read_text(encoding="utf-8", errors="replace").split("\n")
            except OSError:
                self.raw_lines[rel] = None
        return self.raw_lines[rel]

    # ------------------------------------------------------------ counters

    def init_counters(self):
        for c, parent in (("subsection", "section"), ("subsubsection", "subsection"),
                          ("paragraph", "subsubsection"), ("subparagraph", "paragraph"),
                          ("enumii", "enumi"), ("enumiii", "enumii"), ("enumiv", "enumiii")):
            self.reset[parent].append(c)
        self.fmt.update({
            "part": r"\Roman{part}", "section": r"\arabic{section}",
            "subsection": r"\thesection.\arabic{subsection}",
            "subsubsection": r"\thesubsection.\arabic{subsubsection}",
            "paragraph": r"\thesubsubsection.\arabic{paragraph}",
            "subparagraph": r"\theparagraph.\arabic{subparagraph}",
            "equation": r"\arabic{equation}", "figure": r"\arabic{figure}", "table": r"\arabic{table}",
            "footnote": r"\arabic{footnote}", "enumi": r"\arabic{enumi}", "enumii": r"\alph{enumii}",
            "enumiii": r"\roman{enumiii}", "enumiv": r"\Alph{enumiv}",
        })

    def step(self, c: str):
        self.counters[c] += 1
        for ch in self.reset.get(c, ()):
            self.zero(ch)

    def zero(self, c: str, depth: int = 0):
        self.counters[c] = 0
        if depth < 12:
            for ch in self.reset.get(c, ()):
                self.zero(ch, depth + 1)

    def the(self, c: str, depth: int = 0) -> str:
        f = self.fmt.get(c)
        if f is None:
            mac = self.macros.get("the" + c)
            f = mac.body if mac else r"\arabic{" + c + "}"
        return self.eval_fmt(f, depth)

    def eval_fmt(self, f: str, depth: int = 0) -> str:
        if depth > 10:
            return ""
        out = []
        i = 0
        n = len(f)
        while i < n:
            mm = re.match(r"\\(arabic|roman|Roman|alph|Alph|fnsymbol)\s*\{\s*([^{}\s]*)\s*\}", f[i:])
            if mm:
                out.append(numfmt(mm.group(1), self.counters.get(mm.group(2), 0)))
                i += mm.end()
                continue
            mm = re.match(r"\\@(arabic|roman|Roman|alph|Alph)\s*\\c@([A-Za-z]+)", f[i:])
            if mm:
                out.append(numfmt(mm.group(1), self.counters.get(mm.group(2), 0)))
                i += mm.end()
                continue
            mm = re.match(r"\\the([A-Za-z]+)", f[i:])
            if mm:
                out.append(self.the(mm.group(1), depth + 1))
                i += mm.end()
                continue
            mm = re.match(r"\\(?:number|the)\s*\\value\s*\{([^{}]*)\}", f[i:])
            if mm:
                out.append(str(self.counters.get(mm.group(1), 0)))
                i += mm.end()
                continue
            mm = re.match(r"\\([A-Za-z@]+|.)", f[i:])
            if mm:
                name = mm.group(1)
                if name in TEXT_SYMBOLS:
                    out.append(TEXT_SYMBOLS[name])
                elif name in CONTROL_SYMBOLS and CONTROL_SYMBOLS[name]:
                    out.append(CONTROL_SYMBOLS[name])
                elif name in self.macros and self.macros[name].nargs == 0 and depth < 8:
                    out.append(self.eval_fmt(self.macros[name].body, depth + 1))
                i += mm.end()
                continue
            if f[i] in "{}":
                i += 1
                continue
            if f[i] == "~":
                out.append("\u00a0")
                i += 1
                continue
            out.append(f[i])
            i += 1
        return "".join(out).strip()

    def refstep(self, c: str) -> str:
        self.step(c)
        return self.the(c)

    def numberwithin(self, c: str, parent: str, keep_format: bool = False):
        for lst in self.reset.values():
            if c in lst:
                lst.remove(c)
        self.reset[parent].append(c)
        if not keep_format:
            self.fmt[c] = "\\the" + parent + r".\arabic{" + c + "}"

    # ------------------------------------------------------------ contexts and labels

    def new_ctx(self, kind: str, num, auto: str, keep_auto: bool = False, name=None, title=None) -> dict:
        ctx = {"i": len(self.ctxs), "kind": kind, "num": num, "auto": auto, "labels": [],
               "keep_auto": keep_auto, "name": name, "title": title}
        self.ctxs.append(ctx)
        return ctx

    @staticmethod
    def id_ph(ctx) -> str:
        return f"{ID_O}{ctx['i']}{ID_C}"

    @staticmethod
    def xa_ph(ctx) -> str:
        return f"{XA_O}{ctx['i']}{XA_C}"

    def set_label(self, key: str, ctx=None, num=None, kind=None, out=None):
        key = key.strip()
        if not key:
            return
        ctx = ctx if ctx is not None else self.cur
        if key in self.labels:
            self.dup_labels.append(key)
            return
        if ctx is None:
            # no counter has been stepped: LaTeX gives an empty label; anchor it here
            ctx = self.new_ctx("none", "", auto="")
            if out is not None:
                out.append(f'<span class="pr-lbl" id="{self.id_ph(ctx)}"></span>')
        rec = {"num": ctx["num"] if num is None else num, "kind": kind or ctx["kind"], "ctx": ctx["i"],
               "name": ctx.get("name"), "title": ctx.get("title")}
        if ctx.get("inline_anchor") and out is not None:
            sub = self.new_ctx(ctx["kind"], rec["num"], auto="")
            sub["labels"].append(key)
            rec["ctx"] = sub["i"]
            out.append(f'<span class="pr-lbl" id="{self.id_ph(sub)}"></span>')
        else:
            ctx["labels"].append(key)
        self.labels[key] = rec

    # ------------------------------------------------------------ definitions pass

    def read_definitions(self):
        t = self.text
        mm = re.search(r"\\documentclass\s*(?:\[([^\]]*)\])?\s*\{([^}]+)\}", t)
        if mm:
            self.docclass = mm.group(2).strip()
            self.class_opts = {o.strip() for o in (mm.group(1) or "").split(",")}
            self.leqno = "leqno" in self.class_opts
            self.fleqn = "fleqn" in self.class_opts
        for pm in re.finditer(r"\\usepackage\s*(?:\[([^\]]*)\])?\s*\{([^}]*)\}", t):
            opts = {o.strip() for o in (pm.group(1) or "").split(",") if o.strip()}
            for name in pm.group(2).split(","):
                name = name.strip()
                if name == "cleveref":
                    self.cref_opts |= opts
                elif name == "natbib":
                    self.natbib_opts |= opts
                    self.natbib = True
                elif name == "amsmath":
                    if "leqno" in opts:
                        self.leqno = True
                    if "fleqn" in opts:
                        self.fleqn = True
        self.has_natbib = bool(re.search(r"\\usepackage\s*(?:\[[^\]]*\])?\s*\{[^}]*\bnatbib\b", t))
        begin_doc = t.find("\\begin{document}")
        self.begin_doc = begin_doc if begin_doc >= 0 else 0
        end_doc = t.find("\\end{document}", self.begin_doc)
        self.end_doc = end_doc if end_doc >= 0 else len(t)
        pos = 0
        n = len(t)
        while True:
            mm = DEF_RE.search(t, pos)
            if not mm:
                break
            name = mm.group(1)
            in_pre = mm.start() < self.begin_doc
            if name.startswith("begin"):
                pos = mm.end()
                continue
            if name in ("setcounter", "appendix", "bibliographystyle"):
                if name == "setcounter" and in_pre:
                    c, j = read_arg(t, mm.end(), n)
                    v, j = read_arg(t, j, n)
                    self.apply_setcounter(c.strip(), v.strip())
                    pos = j
                    continue
                if name == "bibliographystyle":
                    v, j = read_arg(t, mm.end(), n)
                    self.bibstyle = v.strip()
                    pos = j
                    continue
                pos = mm.end()
                continue
            try:
                j = self.parse_definition(t, mm.start(), n, apply=True)
            except Exception as e:  # noqa: BLE001  (a malformed definition must not stop the page)
                self.untranslated[f"line {self.where(mm.start())}"] = f"definition not parsed: {e}"
                j = mm.end()
            pos = max(j, mm.end())
        mt = re.search(r"\\title\s*(?:\[[^\]]*\])?\s*\{", t)
        if mt:
            j = match_brace(t, mt.end() - 1, n)
            self.title_tex = t[mt.end():j - 1]
        ma = re.search(r"\\author\s*(?:\[[^\]]*\])?\s*\{", t)
        if ma:
            j = match_brace(t, ma.end() - 1, n)
            self.author_tex = t[ma.end():j - 1]
        md = re.search(r"\\date\s*\{", t)
        if md:
            j = match_brace(t, md.end() - 1, n)
            self.date_tex = t[md.end():j - 1]
        ab = re.search(r"\\begin\s*\{abstract\}", t)
        if ab:
            b_end, _ = find_env_end(t, ab.end(), "abstract", n)
            self.abstract_tex = (ab.end(), b_end)
        self.translate_macros()

    def apply_setcounter(self, c: str, v: str):
        try:
            val = int(v)
        except ValueError:
            mm = re.match(r"\\value\s*\{([^}]*)\}", v)
            val = self.counters.get(mm.group(1), 0) if mm else None
        if val is None:
            return
        if c == "secnumdepth":
            self.secnumdepth = val
        elif c == "tocdepth":
            pass
        else:
            self.counters[c] = val

    def parse_definition(self, s: str, i: int, end: int, apply: bool) -> int:
        """Parse one definition command starting at s[i] == '\\'. Return the index
        after it. With apply, record the definition."""
        mm = CS_RE.match(s, i)
        cmd = mm.group(1)
        j = mm.end()
        prefix_skip = re.compile(r"\s*\\(?:long|global|protected|outer)(?![A-Za-z@])")
        if cmd in ("newcommand", "renewcommand", "providecommand", "DeclareRobustCommand"):
            _, j = read_star(s, j, end)
            name, j = read_cs_name(s, j, end)
            nargs_s, j = read_opt(s, j, end)
            default, j = read_opt(s, j, end)
            body, j = read_arg(s, j, end)
            if name and apply:
                try:
                    nargs = int((nargs_s or "0").strip() or 0)
                except ValueError:
                    nargs = 0
                if name.startswith("the") and name[3:] and cmd == "renewcommand":
                    self.fmt[name[3:]] = body
                if cmd == "providecommand" and name in self.macros:
                    return j
                self.macros[name] = Macro(name, nargs, default, body, None, "cmd")
            return j
        if cmd in ("def", "gdef", "edef", "xdef"):
            name, k = read_cs_name(s, j, end)
            if name is None:
                return j
            b = s.find("{", k, end)
            if b < 0:
                return k
            params = s[k:b]
            if "\n\n" in params or len(params) > 80:
                return k
            body_end = match_brace(s, b, end)
            body = s[b + 1:body_end - 1]
            if apply:
                nargs, toks = parse_def_params(params)
                if name.startswith("the") and toks is None and nargs == 0:
                    self.fmt[name[3:]] = body
                self.macros[name] = Macro(name, nargs, None, body, toks, "def")
            return body_end
        if cmd == "let":
            name, k = read_cs_name(s, skip_expandafter(s, j, end), end)
            k = skip_ws(s, k, end)
            if k < end and s[k] == "=":
                k = skip_ws(s, k + 1, end)
            k = skip_expandafter(s, k, end)
            if k < end and s.startswith("\\csname", k, end):
                target, k = read_cs_name(s, k, end)
                target = target or ""
            elif k < end and s[k] == "\\":
                m2 = CS_RE.match(s, k)
                target = m2.group(1)
                k = m2.end()
            else:
                target = s[k:k + 1]
                k += 1
            if name and apply and name != target:
                self.let_macro(name, target)
            return k
        if cmd in COPY_CMDS:
            # \NewCommandCopy{\new}{\old} and letltxmacro's \LetLtxMacro: a \let for robust commands
            name, k = read_cs_name(s, j, end)
            target, k = read_cs_name(s, k, end)
            if name and target and apply and name != target:
                self.let_macro(name, target)
            return k
        if cmd == "@namedef":
            name, k = read_arg(s, j, end)
            body, k = read_arg(s, k, end)
            if apply and name and "#" not in name:
                self.macros[name.strip()] = Macro(name.strip(), 0, None, body, None, "csname")
            return k
        if cmd == "expandafter":
            m2 = re.compile(r"\s*\\(?:global\s*\\)?(def|gdef|edef|xdef|newcommand|renewcommand)\s*"
                            r"\\csname\s*(.*?)\\endcsname", re.S).match(s, j)
            if not m2:
                return j
            name = m2.group(2).strip()
            k = m2.end()
            if m2.group(1).endswith("command"):
                nargs_s, k = read_opt(s, k, end)
                body, k = read_arg(s, k, end)
                nargs = int(nargs_s or 0) if (nargs_s or "0").strip().isdigit() else 0
                if apply and "#" not in name:
                    self.macros[name] = Macro(name, nargs, None, body, None, "csname")
                return k
            b = s.find("{", k, end)
            if b < 0:
                return k
            params = s[k:b]
            body_end = match_brace(s, b, end)
            if apply and "#" not in name:
                nargs, toks = parse_def_params(params)
                self.macros[name] = Macro(name, nargs, None, s[b + 1:body_end - 1], toks, "csname")
            return body_end
        if cmd == "DeclareMathOperator":
            star, j = read_star(s, j, end)
            name, j = read_cs_name(s, j, end)
            body, j = read_arg(s, j, end)
            if name and apply:
                op = "\\operatorname*" if star else "\\operatorname"
                self.macros[name] = Macro(name, 0, None, op + "{" + body + "}", None, "op")
            return j
        if cmd.startswith("DeclarePairedDelimiter"):
            name, j = read_cs_name(s, j, end)
            nargs_s, j = read_opt(s, j, end)
            left, j = read_arg(s, j, end)
            right, j = read_arg(s, j, end)
            body = None
            if cmd != "DeclarePairedDelimiter":
                if cmd == "DeclarePairedDelimiterXPP":
                    pre, j = read_arg(s, j, end)
                    _, j = read_arg(s, j, end)
                    _, j = read_arg(s, j, end)
                    post, j = read_arg(s, j, end)
                    body, j = read_arg(s, j, end)
                else:
                    body, j = read_arg(s, j, end)
            if name and apply:
                n_args = int(nargs_s) if nargs_s and nargs_s.strip().isdigit() else 1
                self.macros[name] = Macro(name, n_args, None, body or "#1", None, "paired",
                                          extra=(left.strip(), right.strip()))
            return j
        if cmd in ("newenvironment", "renewenvironment"):
            _, j = read_star(s, j, end)
            name, j = read_arg(s, j, end)
            nargs_s, j = read_opt(s, j, end)
            default, j = read_opt(s, j, end)
            begin, j = read_arg(s, j, end)
            endc, j = read_arg(s, j, end)
            if apply:
                nargs = int(nargs_s) if nargs_s and nargs_s.strip().isdigit() else 0
                self.envdefs[name.strip()] = (nargs, default, begin, endc)
            return j
        if cmd == "newtheorem":
            star, j = read_star(s, j, end)
            env, j = read_arg(s, j, end)
            shared, j = read_opt(s, j, end)
            display, j = read_arg(s, j, end)
            within, j = read_opt(s, j, end)
            if apply:
                self.declare_theorem(env.strip(), display.strip(), shared, within, star)
            return j
        if cmd == "theoremstyle":
            style, j = read_arg(s, j, end)
            if apply:
                self.thm_style = style.strip()
            return j
        if cmd == "newtheoremstyle":
            args = []
            for _ in range(9):
                a, j = read_arg(s, j, end)
                args.append(a)
            if apply:
                body_font = args[3]
                head_font = args[5]
                self.custom_styles = getattr(self, "custom_styles", {})
                self.custom_styles[args[0].strip()] = (
                    "plain" if re.search(r"\\(?:itshape|slshape|it|sl)\b", body_font) else
                    ("remark" if re.search(r"\\(?:itshape|it)\b", head_font) else "definition"))
            return j
        if cmd in ("numberwithin", "counterwithin", "counterwithout"):
            star, j = read_star(s, j, end)
            c, j = read_arg(s, j, end)
            p, j = read_arg(s, j, end)
            if apply:
                c, p = c.strip(), p.strip()
                if cmd == "counterwithout":
                    for lst in self.reset.values():
                        if c in lst:
                            lst.remove(c)
                    if not star:
                        self.fmt[c] = r"\arabic{" + c + "}"
                else:
                    self.numberwithin(c, p, keep_format=star)
            return j
        if cmd == "newcounter":
            c, j = read_arg(s, j, end)
            p, j = read_opt(s, j, end)
            if apply:
                c = c.strip()
                self.counters.setdefault(c, 0)
                self.fmt.setdefault(c, r"\arabic{" + c + "}")
                if p:
                    self.reset[p.strip()].append(c)
            return j
        if cmd in ("crefname", "Crefname"):
            t_, j = read_arg(s, j, end)
            sing, j = read_arg(s, j, end)
            plur, j = read_arg(s, j, end)
            if apply:
                (self.crefnames if cmd == "crefname" else self.Crefnames)[t_.strip()] = (sing, plur)
            return j
        if cmd == "crefalias":
            c, j = read_arg(s, j, end)
            t_, j = read_arg(s, j, end)
            if apply:
                self.crefalias[c.strip()] = t_.strip()
            return j
        return j

    def declare_theorem(self, env, display, shared, within, star):
        style = self.thm_style
        style = getattr(self, "custom_styles", {}).get(style, style)
        if style not in ("plain", "definition", "remark"):
            style = "plain"
        spec = {"display": display, "style": style, "numbered": not star, "counter": None}
        if not star:
            if shared:
                spec["counter"] = shared.strip()
            else:
                spec["counter"] = env
                self.counters.setdefault(env, 0)
                if within:
                    self.numberwithin(env, within.strip())
                else:
                    self.fmt[env] = r"\arabic{" + env + "}"
        self.thm[env] = spec

    # ------------------------------------------------------------ macros for KaTeX

    def let_macro(self, name: str, target: str):
        """\\let\\name\\target copies the target's meaning at this point: a definition of
        this paper is copied; anything else (a built-in) is recorded as an alias of it."""
        src = self.macros.get(target)
        if src is not None and src.kind != "let":
            self.macros[name] = Macro(name, src.nargs, src.default, src.body, src.params, src.kind, src.extra)
        elif src is not None:
            self.macros[name] = Macro(name, 0, None, src.body, None, "let", extra=src.extra)
        else:
            self.macros[name] = Macro(name, 0, None, "\\" + target if target else "", None, "let", extra=target)

    def drop_self_wrappers(self):
        """A paper that saves a built-in (\\let\\Orig\\mapsto) and then redefines the built-in
        through the saved name only wraps it, typically in text for PDF readers. Rendering the
        built-in is what that wrapper shows, so the redefinition is dropped. Without this the
        redefinition calls itself through the alias, in KaTeX as in this script."""
        self.dropped_wrappers = []
        for alias, mac in list(self.macros.items()):
            tgt = mac.extra if mac.kind == "let" else None
            red = self.macros.get(tgt) if tgt else None
            if red is None or red.kind == "let":
                continue
            ref = re.compile(r"\\" + re.escape(alias) + r"(?![A-Za-z@])|\\csname\s*" + re.escape(alias) + r"\s*\\endcsname")
            if ref.search(red.body or ""):
                del self.macros[tgt]
                self.dropped_wrappers.append(tgt)

    def translate_macros(self):
        """Turn the paper's definitions into KaTeX macros. A definition KaTeX cannot
        carry (optional arguments, delimited parameters, references inside) is
        expanded by this script before the formula reaches KaTeX instead."""
        self.drop_self_wrappers()
        # The page header shows the title, authors and date, so \maketitle shows nothing,
        # even where a paper redefines it (four papers print \@title in their own block).
        self.macros.pop("maketitle", None)
        py = set()
        out = {}
        for name, mac in self.macros.items():
            if not re.fullmatch(r"[A-Za-z@]+|[^A-Za-z@\s]", name):
                py.add(name)
                continue
            key = "\\" + name
            if mac.kind == "let":
                tgt = mac.extra or ""
                if tgt == name:
                    continue
                out[key] = mac.body
                continue
            if mac.kind == "op":
                out[key] = mac.body
                continue
            if mac.kind == "paired":
                left, right = mac.extra
                body = mac.body
                n = max(1, mac.nargs)
                star = body.replace("\\delimsize", "\\middle")
                plain = body.replace("\\delimsize", "")
                sized = body.replace("\\delimsize", "#2")
                shift = {str(k): str(k + 3) for k in range(1, 10)}
                sized_args = re.sub(r"#([1-9])", lambda m_: "#" + shift[m_.group(1)], sized) if n else sized
                sized_args = sized_args.replace("#2", "#2")  # size token stays #2
                if body == "#1" and n == 1:
                    out[key] = f"\\@ifstar{{{key}@s}}{{\\@ifnextchar[{{{key}@o}}{{{key}@n}}}}"
                    out[key + "@s"] = f"\\left{left} #1\\right{right}"
                    out[key + "@n"] = f"\\mathopen{{{left}}}#1\\mathclose{{{right}}}"
                    out[key + "@o"] = f"\\mathopen{{#2{left}}}#4\\mathclose{{#2{right}}}\\@firstoftwo{{}}{{#1#3}}"
                else:
                    py.add(name)
                continue
            if mac.default is not None or mac.params is not None:
                py.add(name)
                continue
            if PY_ONLY_BODY.search(mac.body) or "\\@" in mac.body.replace("\\@firstoftwo", ""):
                py.add(name)
                continue
            body = mac.body.replace("\\xspace", "")
            used = {int(d) for d in re.findall(r"(?<!#)#([1-9])", body)}
            for k in range(1, mac.nargs + 1):
                if k not in used:
                    body += "\\@firstoftwo{}{#" + str(k) + "}"
            if used and max(used) > mac.nargs:
                self.untranslated[name] = "uses more parameters than it declares"
                continue
            out[key] = body
        # A KaTeX macro that calls a Python-only macro must be expanded here as well.
        changed = True
        while changed:
            changed = False
            if not py:
                break
            pat = re.compile(r"\\(" + "|".join(re.escape(p) for p in sorted(py, key=len, reverse=True)) + r")(?![A-Za-z@])")
            for key in list(out):
                if key[1:] in self.macros and pat.search(out[key]):
                    py.add(key[1:])
                    del out[key]
                    changed = True
        out = {k: katex_compat(v) for k, v in out.items()}
        for k, v in SUPPORT_MACROS.items():
            if k[1:] not in self.macros:
                out.setdefault(k, v)
        self.python_macros = py
        self.katex = out
        self.py_pat = (re.compile(r"\\(" + "|".join(re.escape(p) for p in sorted(py, key=len, reverse=True))
                                  + r")(?![A-Za-z@])") if py else None)

    # ------------------------------------------------------------ macro expansion

    def read_macro_args(self, mac: Macro, s: str, i: int, end: int):
        args = []
        if mac.params is not None:
            toks = mac.params
            k = i
            for idx, tok in enumerate(toks):
                if isinstance(tok, int):
                    nxt = toks[idx + 1] if idx + 1 < len(toks) else None
                    if nxt is None or isinstance(nxt, int):
                        a, k = read_arg(s, k, end)
                        args.append(a)
                    else:
                        depth = 0
                        start = k
                        while k < end:
                            c = s[k]
                            if c == "\\" and not s.startswith(nxt, k):
                                k += 2
                                continue
                            if c == "{":
                                depth += 1
                            elif c == "}":
                                depth -= 1
                            elif depth == 0 and s.startswith(nxt, k):
                                break
                            k += 1
                        a = s[start:k]
                        if a.startswith("{") and a.endswith("}") and match_brace(a, 0, len(a)) == len(a):
                            a = a[1:-1]
                        args.append(a)
                else:
                    k2 = skip_ws(s, k, end) if tok not in (" ",) else k
                    if s.startswith(tok, k2):
                        k = k2 + len(tok)
                    else:
                        return None, i
            return args, k
        n = mac.nargs
        k = i
        if mac.default is not None:
            opt, k = read_opt(s, k, end)
            args.append(mac.default if opt is None else opt)
            n -= 1
        for _ in range(max(0, n)):
            a, k = read_arg(s, k, end)
            args.append(a)
        return args, k

    @staticmethod
    def substitute(body: str, args) -> str:
        def rep(mm):
            g = mm.group(1)
            if g == "#":
                return "#"
            idx = int(g) - 1
            return args[idx] if idx < len(args) else ""
        return re.sub(r"#(#|[1-9])", rep, body)

    def expand_in_math(self, tex: str) -> str:
        """Expand the Python-only macros inside a formula. A \\let alias that a macro reaches
        from its own body means the built-in it was saved from (TeX copies a meaning at \\let),
        so it is held as \\@atlasbuiltin{name} during expansion and written back at the end."""
        res = self._expand_in_math(tex, 0, max(100_000, 40 * len(tex)))
        return re.sub(r"\\@atlasbuiltin\{([A-Za-z@]+)\}", r"\\\1", res)

    def _expand_in_math(self, tex: str, depth: int, limit: int) -> str:
        if not self.py_pat or depth > 30:
            return tex
        out = []
        pos = 0
        n = len(tex)
        changed = False
        for mm in self.py_pat.finditer(tex):
            if mm.start() < pos:
                continue
            name = mm.group(1)
            mac = self.macros.get(name)
            if mac is None:
                continue
            out.append(tex[pos:mm.start()])
            if mac.kind == "paired":
                star, k = read_star(tex, mm.end(), n)
                size, k = read_opt(tex, k, n)
                args = []
                for _ in range(max(1, mac.nargs)):
                    a, k = read_arg(tex, k, n)
                    args.append(a)
                left, right = mac.extra
                body = self.substitute(mac.body, args)
                if star:
                    rep = f"\\left{left} {body.replace(chr(92) + 'delimsize', chr(92) + 'middle')}\\right{right}"
                elif size:
                    rep = f"\\mathopen{{{size}{left}}}{body.replace(chr(92) + 'delimsize', size)}\\mathclose{{{size}{right}}}"
                else:
                    rep = f"\\mathopen{{{left}}}{body.replace(chr(92) + 'delimsize', '')}\\mathclose{{{right}}}"
                out.append("{" + rep + "}")
                pos = k
                changed = True
                continue
            args, k = self.read_macro_args(mac, tex, mm.end(), n)
            if args is None:
                out.append(tex[mm.start():mm.end()])
                pos = mm.end()
                continue
            body = strip_assignments(self.substitute(mac.body, args))
            body = self.math_conditionals(body, expanding=name)
            out.append(body)
            pos = k
            changed = True
        out.append(tex[pos:])
        res = "".join(out)
        if len(res) > limit:
            # A definition that grows without end: stop here, so the formula fails visibly
            # (the page becomes partial) instead of exhausting memory.
            for mm in self.py_pat.finditer(tex):
                self.untranslated[mm.group(1)] = "expands without end"
            return tex
        if changed:
            return self._expand_in_math(res, depth + 1, limit)
        return res

    def math_conditionals(self, body: str, expanding: str | None = None) -> str:
        """Resolve \\ifcsname, \\csname and \\ifmmode in a macro body bound for KaTeX.
        `expanding` names the macro whose body this is: a \\let alias of that same macro
        stands for the built-in it saved (see expand_in_math)."""
        for _ in range(20):
            mm = re.search(r"\\ifcsname\s*(.*?)\\endcsname", body, re.S)
            if mm:
                then, els, after = self.split_conditional(body, mm.end())
                body = body[:mm.start()] + (then if self.cs_defined(mm.group(1).strip()) else els) + body[after:]
                continue
            mm = re.search(r"\\ifmmode(?![A-Za-z@])", body)
            if mm:
                then, els, after = self.split_conditional(body, mm.end())
                body = body[:mm.start()] + then + body[after:]
                continue
            mm = re.search(r"\\csname\s*(.*?)\\endcsname", body, re.S)
            if mm:
                name = mm.group(1).strip()
                mac = self.macros.get(name)
                if mac is not None and mac.kind == "let" and expanding and mac.extra == expanding:
                    rep = "\\@atlasbuiltin{" + expanding + "}"
                else:
                    rep = mac.body if mac and mac.nargs == 0 else ""
                body = body[:mm.start()] + rep + body[mm.end():]
                continue
            break
        return body

    def cs_defined(self, name: str) -> bool:
        return name in self.macros or name in HANDLER_NAMES

    @staticmethod
    def split_conditional(s: str, i: int):
        """From just after an \\if... test, return (then, else, index after \\fi)."""
        depth = 0
        k = i
        else_at = None
        n = len(s)
        while k < n:
            mm = re.compile(r"\\(if[A-Za-z@]*|else|fi)(?![A-Za-z@])").search(s, k)
            if not mm:
                break
            word = mm.group(1)
            if word.startswith("if") and word not in ("ifnextchar",):
                depth += 1
            elif word == "else" and depth == 0 and else_at is None:
                else_at = (mm.start(), mm.end())
            elif word == "fi":
                if depth == 0:
                    if else_at:
                        return s[i:else_at[0]], s[else_at[1]:mm.start()], mm.end()
                    return s[i:mm.start()], "", mm.end()
                depth -= 1
            k = mm.end()
        return s[i:], "", n

    # ------------------------------------------------------------ the walker

    def walk(self, s: str, i: int, end: int, origin=None) -> list:
        out = []
        while i < end:
            mm = PLAIN_RE.match(s, i, end)
            if mm:
                out.append(esc_t(mm.group()))
                i = mm.end()
                continue
            c = s[i]
            if c == "\\":
                i = self.command(s, i, end, out, origin)
            elif c == "$":
                i = self.dollar(s, i, end, out, origin)
            elif c == "{":
                j = match_brace(s, i, end)
                out.extend(self.walk(s, i + 1, max(i + 1, j - 1), origin))
                i = j
            elif c == "}":
                i += 1
            elif c == "~":
                out.append("\u00a0")
                i += 1
            elif c == "\n":
                k = i + 1
                while k < end and s[k] in " \t":
                    k += 1
                if k < end and s[k] == "\n":
                    while k < end and s[k] in " \t\n":
                        k += 1
                    out.append(PARA)
                    i = k
                else:
                    out.append(" ")
                    i += 1
            elif c == "-":
                if s.startswith("---", i):
                    out.append("—")
                    i += 3
                elif s.startswith("--", i):
                    out.append("–")
                    i += 2
                else:
                    out.append("-")
                    i += 1
            elif c == "`":
                if s.startswith("``", i):
                    out.append("“")
                    i += 2
                else:
                    out.append("‘")
                    i += 1
            elif c == "'":
                if s.startswith("''", i):
                    out.append("”")
                    i += 2
                else:
                    out.append("’")
                    i += 1
            elif c == "%":
                j = s.find("\n", i, end)
                i = end if j < 0 else j + 1
            elif c == "&":
                out.append("&amp;")
                i += 1
            else:
                out.append(esc_t(c))
                i += 1
        return out

    def abs_off(self, origin, i):
        return i if origin is None else origin

    def command(self, s: str, i: int, end: int, out: list, origin) -> int:
        mm = CS_RE.match(s, i)
        if not mm or mm.end() > end:
            out.append("\\")
            return i + 1
        return self.dispatch(mm.group(1), s, i, mm.end(), end, out, origin)

    def dispatch(self, name: str, s: str, start: int, j: int, end: int, out: list, origin, alias_depth=0) -> int:
        mac = self.macros.get(name)
        if mac is not None and alias_depth < 8:
            target = None
            if mac.kind == "let":
                target = mac.extra
            elif mac.nargs == 0 and mac.default is None and mac.params is None:
                bm = re.fullmatch(r"\s*\\([A-Za-z@]+)\s*", mac.body)
                if bm:
                    target = bm.group(1)
            if target and target != name and (target in HANDLERS or target in self.macros
                                              or target in TEXT_SYMBOLS):
                return self.dispatch(target, s, start, j, end, out, origin, alias_depth + 1)
            if name not in HANDLERS:
                return self.expand_user(mac, s, start, j, end, out, origin)
        h = HANDLERS.get(name)
        if h is not None:
            return h(self, name, s, start, j, end, out, origin)
        if name in TEXT_SYMBOLS:
            out.append(TEXT_SYMBOLS[name])
            return skip_space_after_word(s, j, end) if WORD_CS.match(name) else j
        if name in CONTROL_SYMBOLS and CONTROL_SYMBOLS[name] is not None:
            out.append(CONTROL_SYMBOLS[name])
            return j
        if name in ACCENTS:
            return self.h_accent(name, s, start, j, end, out, origin)
        if name in IGNORE:
            k = j
            star, k = read_star(s, k, end)
            for _ in range(IGNORE[name]):
                o, k = read_opt(s, k, end)
                _, k = read_arg(s, k, end)
            if IGNORE[name] == 0:
                o, k2 = read_opt(s, k, end) if name in ("linebreak", "nolinebreak", "pagebreak", "nopagebreak",
                                                        "allowdisplaybreaks", "displaybreak") else (None, k)
                k = k2
                return skip_space_after_word(s, k, end) if WORD_CS.match(name) else k
            return k
        if name in DIMEN_PRIMITIVES:
            m2 = DIMEN_RE.match(s, j, end)
            return m2.end() if m2 else j
        if name in REGISTER_PRIMITIVES:
            m2 = REGISTER_RE.match(s, j, end)
            return m2.end() if m2 else j
        if name in ARITH_PRIMITIVES:
            m2 = ARITH_RE.match(s, j, end)
            return m2.end() if m2 else j
        if name.startswith("the") and (name[3:] in self.counters or name[3:] in self.fmt):
            out.append(esc_t(self.the(name[3:])))
            return skip_space_after_word(s, j, end)
        if name in self.envdefs or name in self.thm:
            # \foo ... \endfoo, the plain-TeX form of an environment: rare, keep the text
            return j
        self.unknown_cmds[name] += 1
        self.unknown_examples.setdefault("\\" + name, self.where(self.abs_off(origin, start)))
        out.append(f'<span class="pr-raw">{esc_t(chr(92) + name)}</span>')
        return j

    def expand_user(self, mac: Macro, s: str, start: int, j: int, end: int, out: list, origin) -> int:
        if self.depth > 60:
            self.untranslated.setdefault(mac.name, "expansion too deep")
            return j
        if mac.kind == "paired" or mac.kind == "op":
            # A maths-only macro used in text: typeset it as a formula.
            k = j
            if mac.kind == "paired":
                star, k = read_star(s, k, end)
                size, k = read_opt(s, k, end)
                args = []
                for _ in range(max(1, mac.nargs)):
                    a, k = read_arg(s, k, end)
                    args.append(a)
                tex = "\\" + mac.name + ("*" if star else "") + (f"[{size}]" if size else "") + "".join(
                    "{" + a + "}" for a in args)
            else:
                tex = "\\" + mac.name
            out.append(self.inline_math(tex, self.abs_off(origin, start)))
            return k
        args, k = self.read_macro_args(mac, s, j, end)
        if args is None:
            self.untranslated.setdefault(mac.name, "arguments do not match its parameter text")
            return j
        body = self.substitute(mac.body, args)
        self.depth += 1
        try:
            out.extend(self.walk(body, 0, len(body), origin=self.abs_off(origin, start)))
        finally:
            self.depth -= 1
        if mac.nargs == 0 and mac.default is None and mac.params is None:
            return skip_space_after_word(s, k, end)
        return k

    # ------------------------------------------------------------ handlers: text

    def h_accent(self, name, s, start, j, end, out, origin):
        k = j
        if name.isalpha():
            k = skip_ws(s, k, end)
        if k < end and s[k] == "{":
            e = match_brace(s, k, end)
            arg = s[k + 1:e - 1]
            k = e
        elif k < end and s[k] == "\\":
            m2 = CS_RE.match(s, k)
            arg = m2.group(0)
            k = m2.end()
        elif k < end:
            arg = s[k]
            k += 1
        else:
            arg = ""
        base = arg.strip()
        base = {"\\i": "i", "\\j": "j", "\\i{}": "i", "\\j{}": "j"}.get(base, base)
        if base.startswith("\\"):
            bn = base[1:].rstrip("{} ")
            base = TEXT_SYMBOLS.get(bn, bn)
        base = base.replace("{", "").replace("}", "")
        if not base:
            out.append(SPACING_ACCENT.get(name, ""))
            return k
        if name == "t" and len(base) >= 2:
            res = base[0] + ACCENTS[name] + base[1:]
        else:
            res = base[0] + ACCENTS[name] + base[1:]
        out.append(esc_t(unicodedata.normalize("NFC", res)))
        return k

    def h_symbol_bs(self, name, s, start, j, end, out, origin):
        # \\ in text: a line break, with an optional star and [space]
        star, k = read_star(s, j, end)
        o, k2 = read_opt(s, k, end)
        out.append("<br>")
        return k2

    def h_newline(self, name, s, start, j, end, out, origin):
        out.append("<br>")
        return skip_space_after_word(s, j, end)

    def h_par(self, name, s, start, j, end, out, origin):
        out.append(PARA)
        return skip_space_after_word(s, j, end)

    def h_font_arg(self, name, s, start, j, end, out, origin):
        star, k = read_star(s, j, end)
        if name in ("makebox", "framebox", "shortstack"):
            _, k = read_opt(s, k, end)
            _, k = read_opt(s, k, end)
        if name == "foreignlanguage":
            _, k = read_opt(s, k, end)
            _, k = read_arg(s, k, end)
            open_, close_ = "", ""
        elif name in ("textcolor", "colorbox"):
            _, k = read_opt(s, k, end)
            _, k = read_arg(s, k, end)
            open_, close_ = "", ""
        else:
            open_, close_ = FONT_ARG[name]
        k2 = skip_ws(s, k, end)
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            inner = self.walk(s, k2 + 1, e - 1, origin)
            k = e
        else:
            arg, k = read_arg(s, k, end)
            inner = self.walk(arg, 0, len(arg), origin=self.abs_off(origin, start))
        if open_:
            out.append(wrap_inline(inner, open_, close_))
        else:
            out.extend(inner)
        return k

    def h_font_switch(self, name, s, start, j, end, out, origin):
        open_, close_ = FONT_SWITCH[name]
        rest = self.walk(s, skip_space_after_word(s, j, end), end, origin)
        out.append(wrap_inline(rest, open_, close_))
        return end

    def h_box(self, name, s, start, j, end, out, origin):
        k = j
        if name == "parbox":
            _, k = read_opt(s, k, end)
            _, k = read_opt(s, k, end)
            _, k = read_opt(s, k, end)
            _, k = read_arg(s, k, end)
        elif name == "raisebox":
            _, k = read_arg(s, k, end)
            _, k = read_opt(s, k, end)
            _, k = read_opt(s, k, end)
        elif name in ("resizebox", "resizebox*"):
            _, k = read_arg(s, k, end)
            _, k = read_arg(s, k, end)
        elif name in ("scalebox",):
            _, k = read_arg(s, k, end)
            _, k = read_opt(s, k, end)
        elif name in ("rotatebox",):
            _, k = read_opt(s, k, end)
            _, k = read_arg(s, k, end)
        elif name in ("adjustbox",):
            _, k = read_arg(s, k, end)
        k2 = skip_ws(s, k, end)
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            out.extend(self.walk(s, k2 + 1, e - 1, origin))
            return e
        return k

    def h_url(self, name, s, start, j, end, out, origin):
        k = skip_ws(s, j, end)
        if k < end and s[k] == "{":
            e = match_brace(s, k, end)
            u = s[k + 1:e - 1]
        else:
            u, e = read_arg(s, k, end)
        if name == "path":
            # url's \path: a file or folder name, which in the release names the paper's own files
            raw = clean_url(u)
            link = self.repo_link(raw, self.mdir) or self.repo_link(raw, self.tex_dir())
            out.append(f'<a href="{esc_a(link)}" rel="noopener"><code>{esc_t(raw)}</code></a>' if link
                       else f"<code>{esc_t(raw)}</code>")
            return e
        href = safe_href(u)
        shown = esc_t(clean_url(u))
        if name == "doi":
            href = "https://doi.org/" + clean_url(u)
            shown = esc_t("doi:" + clean_url(u))
        elif name in ("arxiv", "arXiv", "eprint"):
            href = "https://arxiv.org/abs/" + clean_url(u)
            shown = esc_t("arXiv:" + clean_url(u))
        if href:
            out.append(f'<a href="{esc_a(href)}" rel="noopener">{shown}</a>')
        else:
            out.append(f"<code>{shown}</code>")
        return e

    def h_href(self, name, s, start, j, end, out, origin):
        k = skip_ws(s, j, end)
        if k < end and s[k] == "{":
            e = match_brace(s, k, end)
            u = s[k + 1:e - 1]
        else:
            u, e = read_arg(s, k, end)
        k = skip_ws(s, e, end)
        if k < end and s[k] == "{":
            e2 = match_brace(s, k, end)
            inner = inline(self.walk(s, k + 1, e2 - 1, origin))
        else:
            a, e2 = read_arg(s, k, end)
            inner = esc_t(a)
        href = safe_href(u)
        if href:
            out.append(f'<a href="{esc_a(href)}" rel="noopener">{inner}</a>')
        else:
            out.append(inner)
        return e2

    def h_verb(self, name, s, start, j, end, out, origin):
        k = j
        if name == "lstinline":
            _, k = read_opt(s, k, end)
        star, k = read_star(s, k, end)
        if k >= end:
            return k
        delim = s[k]
        if delim == "{":
            e = match_brace(s, k, end)
            out.append(f"<code>{esc_t(s[k + 1:e - 1])}</code>")
            return e
        e = s.find(delim, k + 1, end)
        e = end if e < 0 else e
        out.append(f"<code>{esc_t(s[k + 1:e])}</code>")
        return min(end, e + 1)

    def h_ensuremath(self, name, s, start, j, end, out, origin):
        arg, k = read_arg(s, j, end)
        out.append(self.inline_math(arg, self.abs_off(origin, start)))
        return k

    def h_texorpdf(self, name, s, start, j, end, out, origin):
        k = skip_ws(s, j, end)
        if k < end and s[k] == "{":
            e = match_brace(s, k, end)
            out.extend(self.walk(s, k + 1, e - 1, origin))
        else:
            _, e = read_arg(s, k, end)
        _, e = read_arg(s, e, end)
        return e

    def h_gobble_first(self, name, s, start, j, end, out, origin):
        # \foo{x}{text}: drop x, keep text
        _, k = read_opt(s, j, end)
        _, k = read_arg(s, k, end)
        k2 = skip_ws(s, k, end)
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            out.extend(self.walk(s, k2 + 1, e - 1, origin))
            return e
        return k

    def h_skip_def(self, name, s, start, j, end, out, origin):
        try:
            k = self.parse_definition(s, start, end, apply=False)
        except Exception:  # noqa: BLE001
            k = j
        return skip_space_after_word(s, max(k, j), end)

    def h_counter(self, name, s, start, j, end, out, origin):
        c, k = read_arg(s, j, end)
        c = c.strip()
        if name in ("setcounter", "addtocounter"):
            v, k = read_arg(s, k, end)
            if name == "setcounter":
                self.apply_setcounter(c, v.strip())
            else:
                try:
                    self.counters[c] += int(v.strip())
                except ValueError:
                    pass
        elif name == "stepcounter":
            self.step(c)
        elif name == "refstepcounter":
            num = self.refstep(c)
            kind = self.crefalias.get(c, c)
            ctx = self.new_ctx(kind, num, auto="")
            ctx["inline_anchor"] = True
            self.cur = ctx
        return skip_space_after_word(s, k, end)

    def h_numfmt(self, name, s, start, j, end, out, origin):
        c, k = read_arg(s, j, end)
        if name == "value":
            out.append(str(self.counters.get(c.strip(), 0)))
        else:
            out.append(esc_t(numfmt(name, self.counters.get(c.strip(), 0))))
        return k

    def h_today(self, name, s, start, j, end, out, origin):
        out.append(esc_t(self.m.get("date") or ""))
        return skip_space_after_word(s, j, end)

    def h_csname(self, name, s, start, j, end, out, origin):
        e = s.find("\\endcsname", j, end)
        if e < 0:
            return j
        cs = s[j:e].strip()
        k = e + len("\\endcsname")
        mac = self.macros.get(cs)
        if mac is None:
            if cs in HANDLERS or cs in TEXT_SYMBOLS:
                return self.dispatch(cs, s, start, k, end, out, origin)
            return k
        return self.expand_user(mac, s, start, k, end, out, origin)

    def h_if(self, name, s, start, j, end, out, origin):
        if name == "ifcsname":
            e = s.find("\\endcsname", j, end)
            if e < 0:
                return j
            cond = self.cs_defined(s[j:e].strip())
            k = e + len("\\endcsname")
        elif name == "ifdefined":
            m2 = CS_RE.match(s, skip_ws(s, j, end))
            cond = bool(m2) and (m2.group(1) in self.macros or m2.group(1) in HANDLERS)
            k = m2.end() if m2 else j
        elif name == "ifmmode":
            cond = False
            k = j
        elif name in ("iftrue",):
            cond = True
            k = j
        elif name in ("iffalse",):
            cond = False
            k = j
        elif name == "ifdim" and re.match(r"\s*(?:\\dimexpr\s*)?\\(?:page(?:goal|total)(?![A-Za-z@])|dimen\s*(?:\d+|@))",
                                          s[j:min(end, j + 80)]):
            # \ifdim\dimexpr\pagegoal-\pagetotal...\newpage\fi tests the position on the printed
            # page; on a web page there is none, and the whole conditional shows nothing.
            _, _, after = self.split_conditional(s[:end], j)
            return after
        else:
            self.unknown_cmds[name] += 1
            self.unknown_examples.setdefault("\\" + name, self.where(self.abs_off(origin, start)))
            cond = True
            k = j
        sub = s[:end]
        then, els, after = self.split_conditional(sub, k)
        branch = then if cond else els
        out.extend(self.walk(branch, 0, len(branch), origin=self.abs_off(origin, start)))
        return after

    def h_ignore_fi(self, name, s, start, j, end, out, origin):
        return j

    def h_space_cmd(self, name, s, start, j, end, out, origin):
        star, k = read_star(s, j, end)
        arg, k = read_arg(s, k, end)
        if name == "hspace" and "fill" not in arg:
            out.append(" ")
        return k

    def h_and(self, name, s, start, j, end, out, origin):
        out.append(", ")
        return skip_space_after_word(s, j, end)

    def h_thanks(self, name, s, start, j, end, out, origin):
        _, k = read_arg(s, j, end)
        return k

    def h_item_stray(self, name, s, start, j, end, out, origin):
        lab, k = read_opt(s, j, end)
        out.append(inline(self.walk(lab, 0, len(lab), self.abs_off(origin, start))) + " " if lab is not None else "• ")
        return k

    def h_qed(self, name, s, start, j, end, out, origin):
        out.append('<span class="pr-qed" aria-hidden="true">□</span>')
        return skip_space_after_word(s, j, end)

    def h_tikz_inline(self, name, s, start, j, end, out, origin):
        # \tikz[options]{...} or \tikz ... ;
        k = j
        _, k = read_opt(s, k, end)
        k = skip_ws(s, k, end)
        if k < end and s[k] == "{":
            k = match_brace(s, k, end)
        else:
            depth = 0
            while k < end:
                c = s[k]
                if c == "{":
                    depth += 1
                elif c == "}":
                    depth -= 1
                elif c == ";" and depth <= 0:
                    k += 1
                    break
                k += 1
        out.append(self.placeholder("tikz", inline_=True))
        return k

    def h_xspace(self, name, s, start, j, end, out, origin):
        """xspace: a space unless punctuation follows (TeX already dropped the space after the macro)."""
        k = j
        while k < end and s[k] in " \t":
            k += 1
        if k < end and s[k] not in ".,;:!?)]}'\"-/\n~":
            out.append(" ")
        return k

    def tex_dir(self) -> Path:
        return self.main.parent if getattr(self, "main", None) else self.mdir

    def repo_link(self, rel: str, base: Path) -> str | None:
        """The file or folder `rel`, relative to `base`, on GitHub at the pinned commit, when it lies
        inside openai/math and is present in the checkout."""
        rel = (rel or "").strip()
        if not rel or "://" in rel:
            return None
        try:
            root = self.mdir.parent.parent.resolve()
            target = (base / rel).resolve()
            relpath = target.relative_to(root).as_posix()
        except (ValueError, OSError):
            return None
        if not relpath or relpath == "." or not target.exists():
            return None
        return f"https://github.com/openai/math/{'tree' if target.is_dir() else 'blob'}/{COMMIT}/{relpath}"

    def h_lstinputlisting(self, name, s, start, j, end, out, origin):
        """A code listing read from a file: linked to that file in the release, never inlined."""
        _, k = read_opt(s, j, end)
        f, k = read_arg(s, k, end)
        f = (f or "").strip()
        link = self.repo_link(f, self.tex_dir()) or self.repo_link(f, self.mdir)
        name_ = f.rsplit("/", 1)[-1] or f
        if link:
            h = (f'<div class="pr-ph pr-ph--listing"><a href="{esc_a(link)}" rel="noopener">'
                 f'{esc_t(TXT["listing_link"].format(file=name_))}</a></div>')
        else:
            h = f'<div class="pr-ph pr-ph--listing" role="note">{esc_t(TXT["listing_pdf"].format(file=name_))}</div>'
        if self.float_kind is None:
            self.figures["listing"] += 1
        out.append(block(h))
        return k

    def h_includepdf(self, name, s, start, j, end, out, origin):
        """\\includepdf[...]{file.pdf} sets whole pages of a PDF into the paper. They are its
        content, so the page names the file and stays incomplete rather than reading as a
        faithful copy."""
        _, k = read_opt(s, j, end)
        arg, k = read_arg(s, k, end)
        f = (arg or "").strip()
        self.included_pdfs.append(f)
        text = TXT["fig_pdf"].format(file=f)
        out.append(block(f'<div class="pr-ph pr-ph--pdf" role="img" aria-label="{esc_a(text)}">{esc_t(text)}</div>'))
        return k

    def h_nameuse(self, name, s, start, j, end, out, origin):
        """\\@nameuse{name}: the macro \\name, defined by \\@namedef."""
        arg, k = read_arg(s, j, end)
        cs = (arg or "").strip()
        mac = self.macros.get(cs)
        if mac is None:
            if cs in HANDLERS or cs in TEXT_SYMBOLS:
                return self.dispatch(cs, s, start, k, end, out, origin)
            return k
        return self.expand_user(mac, s, start, k, end, out, origin)

    def h_includegraphics(self, name, s, start, j, end, out, origin):
        star, k = read_star(s, j, end)
        _, k = read_opt(s, k, end)
        _, k = read_opt(s, k, end)
        _, k = read_arg(s, k, end)
        out.append(self.placeholder("image", inline_=self.float_kind is None))
        return k

    def h_input_left(self, name, s, start, j, end, out, origin):
        _, k = read_arg(s, j, end)
        return k

    def h_appendix(self, name, s, start, j, end, out, origin):
        self.start_appendix()
        return skip_space_after_word(s, j, end)

    def start_appendix(self):
        if self.in_appendix:
            return
        self.in_appendix = True
        self.zero("section")
        self.fmt["section"] = r"\Alph{section}"

    def h_bibliography(self, name, s, start, j, end, out, origin):
        arg, k = read_arg(s, j, end)
        if name == "bibliography":
            self.bibfiles.extend(x.strip() for x in arg.split(",") if x.strip())
        out.append(block(BIB_MARK))
        return k

    def h_printbib(self, name, s, start, j, end, out, origin):
        _, k = read_opt(s, j, end)
        out.append(block(BIB_MARK))
        return k

    def h_footnote(self, name, s, start, j, end, out, origin):
        if name == "footnotemark":
            o, k = read_opt(s, j, end)
            self.step("footnote")
            num = o.strip() if o else self.the("footnote")
            self.pending_fnmark = num
            out.append(f'<sup class="pr-fnref">{esc_t(num)}</sup>')
            return k
        o, k = read_opt(s, j, end)
        k2 = skip_ws(s, k, end)
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            b0, b1 = k2 + 1, e - 1
        else:
            arg, e = read_arg(s, k2, end)
            b0 = b1 = None
        if name == "footnotetext":
            num = o.strip() if o else getattr(self, "pending_fnmark", self.the("footnote"))
            make_ref = False
        else:
            if o:
                num = o.strip()
            else:
                self.step("footnote")
                num = self.the("footnote")
            make_ref = True
        idx = len(self.footnotes) + 1
        ctx = self.new_ctx("footnote", num, auto=f"pr-fn-{idx}")
        saved = self.cur
        self.cur = ctx
        if b0 is not None:
            frags = self.walk(s, b0, b1, origin)
        else:
            frags = self.walk(arg, 0, len(arg), self.abs_off(origin, start))
        self.cur = saved
        self.footnotes.append({"num": num, "ctx": ctx, "html": assemble(frags), "idx": idx})
        if make_ref:
            out.append(f'<sup class="pr-fnref"><a href="#{self.id_ph(ctx)}" id="pr-fnref-{idx}" '
                       f'aria-label="{esc_a(TXT["fn_label"].format(n=num))}">{esc_t(num)}</a></sup>')
        return e

    def h_label(self, name, s, start, j, end, out, origin):
        arg, k = read_arg(s, j, end)
        self.set_label(arg, out=out)
        return skip_space_after_word(s, k, end)

    def h_hypertarget(self, name, s, start, j, end, out, origin):
        tgt, k = read_arg(s, j, end)
        k2 = skip_ws(s, k, end)
        out.append(f'<span class="pr-lbl" id="{esc_a(tgt.strip())}"></span>')
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            out.extend(self.walk(s, k2 + 1, e - 1, origin))
            return e
        return k

    def h_hyperlink(self, name, s, start, j, end, out, origin):
        tgt, k = read_arg(s, j, end)
        k2 = skip_ws(s, k, end)
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            inner = inline(self.walk(s, k2 + 1, e - 1, origin))
        else:
            a, e = read_arg(s, k2, end)
            inner = esc_t(a)
        out.append(f'<a href="{esc_a(frag_href(tgt.strip()))}">{inner}</a>')
        return e

    def h_hyperref(self, name, s, start, j, end, out, origin):
        tgt, k = read_opt(s, j, end)
        k2 = skip_ws(s, k, end)
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            inner = inline(self.walk(s, k2 + 1, e - 1, origin))
        else:
            a, e = read_arg(s, k2, end)
            inner = esc_t(a)
        if tgt is None:
            # \hyperref{url}{category}{name}{text}
            _, e = read_arg(s, e, end)
            _, e = read_arg(s, e, end)
            a, e = read_arg(s, e, end)
            out.append(inline(self.walk(a, 0, len(a), self.abs_off(origin, start))))
            return e
        idx = self.add_placeholder(("hyperref", tgt.strip(), inner), self.abs_off(origin, start))
        out.append(f"{PH_O}{idx}{PH_C}")
        return e

    def h_ref(self, name, s, start, j, end, out, origin):
        star, k = read_star(s, j, end)
        _, k = read_opt(s, k, end)
        arg, k = read_arg(s, k, end)
        extra = None
        if name in ("crefrange", "Crefrange", "cpagerefrange"):
            extra, k = read_arg(s, k, end)
        labels = [x.strip() for x in arg.split(",") if x.strip()]
        idx = self.add_placeholder(("ref", name, labels, extra), self.abs_off(origin, start))
        out.append(f"{PH_O}{idx}{PH_C}")
        return k

    def h_cite(self, name, s, start, j, end, out, origin):
        star, k = read_star(s, j, end)
        opts = []
        for _ in range(2):
            o, k2 = read_opt(s, k, end)
            if o is None:
                break
            opts.append(o)
            k = k2
        keys_s, k = read_arg(s, k, end)
        keys = [x.strip() for x in keys_s.split(",") if x.strip()]
        if name == "nocite":
            for key in keys:
                if key == "*":
                    self.nocite_all = True
                else:
                    self.note_cite(key)
            return k
        for key in keys:
            self.note_cite(key)
        pre = post = None
        if len(opts) == 1:
            post = opts[0]
        elif len(opts) == 2:
            pre, post = opts
        pre_h = inline(self.walk(pre, 0, len(pre), self.abs_off(origin, start))) if pre else ""
        post_h = inline(self.walk(post, 0, len(post), self.abs_off(origin, start))) if post else ""
        idx = self.add_placeholder(("cite", name, keys, pre_h, post_h, star), self.abs_off(origin, start))
        out.append(f"{PH_O}{idx}{PH_C}")
        return k

    def note_cite(self, key):
        if key not in self.cite_seen:
            self.cite_seen.add(key)
            self.cite_order.append(key)

    def add_placeholder(self, item, off) -> int:
        self.placeholders.append((item, off, "text"))
        if item[0] == "ref":
            self.ref_total += 1
        elif item[0] == "cite":
            self.cite_total += 1
        return len(self.placeholders) - 1

    def h_caption(self, name, s, start, j, end, out, origin):
        kind = self.float_kind or "figure"
        k = j
        if name == "captionof":
            star, k = read_star(s, k, end)
            kind_arg, k = read_arg(s, k, end)
            kind = kind_arg.strip() or "figure"
        star, k = read_star(s, k, end)
        _, k = read_opt(s, k, end)
        k2 = skip_ws(s, k, end)
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            b0, b1 = k2 + 1, e - 1
        else:
            arg, e = read_arg(s, k2, end)
            b0 = None
        counter = "table" if kind.startswith("table") else "figure"
        if star:
            num = None
        else:
            num = self.refstep(counter)
        word = "Table" if counter == "table" else "Figure"
        if self.float_ctx is not None and self.float_captions == 0:
            ctx = self.float_ctx
            ctx["num"] = num
            ctx["kind"] = counter
            id_attr = ""
        else:
            ctx = self.new_ctx(counter, num, auto=f"pr-{counter}-{num}")
            id_attr = f' id="{self.id_ph(ctx)}"'
        self.float_captions += 1
        self.cur = ctx
        if b0 is not None:
            body = inline(self.walk(s, b0, b1, origin))
        else:
            body = inline(self.walk(arg, 0, len(arg), self.abs_off(origin, start)))
        sep = ". " if self.docclass.startswith("ams") else ": "
        lead = f'<span class="pr-cap-n">{word} {esc_t(num)}{sep.strip()}</span> ' if num else ""
        out.append(block(f'<p class="pr-cap"{id_attr}>{"" if id_attr == "" else self.xa_ph(ctx)}{lead}{body}</p>'))
        return e

    def h_section(self, name, s, start, j, end, out, origin):
        star, k = read_star(s, j, end)
        short, k = read_opt(s, k, end)
        k2 = skip_ws(s, k, end)
        if k2 < end and s[k2] == "{":
            e = match_brace(s, k2, end)
            title_html = inline(self.walk(s, k2 + 1, e - 1, origin))
        else:
            arg, e = read_arg(s, k2, end)
            title_html = inline(self.walk(arg, 0, len(arg), self.abs_off(origin, start)))
        level = LEVELS[name]
        numbered = not star and level <= self.secnumdepth
        num = None
        kind = name
        if self.in_appendix and name in ("section", "subsection", "subsubsection"):
            kind = {"section": "appendix", "subsection": "subappendix", "subsubsection": "subsubappendix"}[name]
        if numbered:
            num = self.refstep(name)
        sec_i = len(self.toc) + 1
        ctx = self.new_ctx(kind, num or "", auto=f"pr-s{sec_i}", title=title_html)
        if numbered:
            self.cur = ctx
        prefix = ""
        if num:
            if name == "part":
                prefix = f"Part {num}"
            elif name == "section" and self.in_appendix and self.docclass.startswith("ams"):
                prefix = f"Appendix {num}."
            elif self.docclass.startswith("ams") and level <= 3:
                prefix = num + "."
            else:
                prefix = num
        if level >= 4:
            lead = f'<span class="pr-runin" id="{self.id_ph(ctx)}">{self.xa_ph(ctx)}'
            if prefix:
                lead += f'<span class="pr-secnum">{esc_t(prefix)}</span> '
            lead += f"{title_html}{'.' if self.docclass.startswith('ams') else ''}</span> "
            out.append(PARA)
            out.append(lead)
            return skip_space_after_word(s, e, end)
        tag = {0: "h2", 1: "h2", 2: "h3", 3: "h4"}[level]
        cls = "pr-part" if level == 0 else f"pr-sec pr-sec--{level}"
        num_html = f'<span class="pr-secnum">{esc_t(prefix)}</span> ' if prefix else ""
        out.append(block(f'<{tag} class="{cls}" id="{self.id_ph(ctx)}">{self.xa_ph(ctx)}{num_html}'
                         f'<span class="pr-sectitle">{title_html}</span></{tag}>'))
        if level <= 2:
            self.toc.append((level, prefix, title_html, ctx))
        return skip_space_after_word(s, e, end)

    # ------------------------------------------------------------ handlers: environments

    def h_begin(self, name, s, start, j, end, out, origin):
        k = skip_ws(s, j, end)
        if k >= end or s[k] != "{":
            return j
        e = match_brace(s, k, end)
        env = s[k + 1:e - 1].strip()
        b_end, after = find_env_end(s, e, env, end)
        off = self.abs_off(origin, start)
        self.env(env, s, e, b_end, end, out, origin, off)
        return after

    def h_end(self, name, s, start, j, end, out, origin):
        # an \end without its \begin (the begin may sit inside a macro): drop it
        _, k = read_arg(s, j, end)
        return k

    def env(self, env: str, s: str, b0: int, b1: int, end: int, out: list, origin, off):
        if env in MATH_ENVS:
            out.extend(self.math_env(env, s[b0:b1], "", off))
            return
        if env.rstrip("*") == "alignat" or env in ("alignat", "alignat*"):
            out.extend(self.math_env(env, s[b0:b1], "", off))
            return
        if env in self.thm:
            self.env_theorem(env, s, b0, b1, out, origin, off)
            return
        if env in ("proof", "proof*", "pf", "Proof"):
            self.env_proof(s, b0, b1, out, origin, off)
            return
        if env in LIST_ENVS:
            self.env_list(env, s, b0, b1, out, origin, off)
            return
        if env in FLOAT_ENVS:
            self.env_float(env, s, b0, b1, out, origin, off)
            return
        if env in TABLE_ENVS:
            out.append(block(self.env_table(env, s, b0, b1, origin, off)))
            return
        if env in THEOREM_PLACEHOLDER_ENVS:
            out.append(self.placeholder("tikz", inline_=False))
            return
        if env in VERBATIM_ENVS:
            out.append(block(self.env_verbatim(env, s, b0, b1, origin, off)))
            return
        if env in MATH_ONLY_ENVS:
            out.extend(self.display_math(f"\\begin{{{env}}}{s[b0:b1]}\\end{{{env}}}", off))
            return
        if env == "subequations":
            self.step("equation")
            parent = self.the("equation")
            saved_sub = self.subeq
            self.subeq = {"parent": parent, "n": 0}
            saved = self.cur
            ctx = self.new_ctx("equation", parent, auto="")
            ctx["inline_anchor"] = True
            self.cur = ctx
            out.extend(self.walk(s, b0, b1, origin))
            self.cur = saved
            self.subeq = saved_sub
            return
        if env == "abstract":
            return
        if env == "document":
            out.extend(self.walk(s, b0, b1, origin))
            return
        if env == "thebibliography":
            self.env_thebibliography(s, b0, b1, origin, off)
            out.append(block(BIB_MARK))
            return
        if env in ("comment", "IEEEkeywords_hidden"):
            return
        if env in ("appendices", "appendix"):
            self.start_appendix()
            out.extend(self.walk(s, b0, b1, origin))
            return
        if env == "tabbing":
            out.append(block(self.env_tabbing(s, b0, b1, origin)))
            return
        if env in self.envdefs:
            self.env_user(env, s, b0, b1, out, origin, off)
            return
        if env in CONTAINER_ENVS:
            k = b0
            if env in ("minipage", "minipage*", "multicols", "multicols*", "adjustwidth", "spacing",
                       "otherlanguage", "otherlanguage*", "addmargin", "parbox", "tcolorbox", "mdframed"):
                _, k = read_opt(s, k, b1)
                _, k = read_opt(s, k, b1)
                if env in ("minipage", "minipage*", "multicols", "multicols*", "spacing", "otherlanguage",
                           "otherlanguage*", "parbox"):
                    _, k = read_arg(s, k, b1)
                if env == "adjustwidth":
                    _, k = read_arg(s, k, b1)
                    _, k = read_arg(s, k, b1)
            cls = {"center": "pr-center", "Center": "pr-center", "quote": "pr-quote", "quotation": "pr-quote",
                   "verse": "pr-quote", "flushright": "pr-right", "FlushRight": "pr-right", "framed": "pr-framed",
                   "mdframed": "pr-framed", "tcolorbox": "pr-framed"}.get(env, "pr-box")
            inner = self.walk(s, k, b1, origin)
            if env in ("itshape",):
                out.append(wrap_inline(inner, "<i>", "</i>"))
                return
            if env in ("bfseries",):
                out.append(wrap_inline(inner, "<b>", "</b>"))
                return
            out.append(block(f'<div class="{cls}">{assemble(inner)}</div>'))
            return
        self.unknown_envs[env] += 1
        self.unknown_examples.setdefault("env:" + env, self.where(off))
        inner = self.walk(s, b0, b1, origin)
        out.append(block(f'<div class="pr-box pr-unknown" data-env="{esc_a(env)}">{assemble(inner)}</div>'))

    def env_user(self, env, s, b0, b1, out, origin, off):
        nargs, default, begin, endc = self.envdefs[env]
        args = []
        k = b0
        n = nargs
        if default is not None:
            o, k = read_opt(s, k, b1)
            args.append(default if o is None else o)
            n -= 1
        for _ in range(max(0, n)):
            a, k = read_arg(s, k, b1)
            args.append(a)
        text = self.substitute(begin, args) + s[k:b1] + self.substitute(endc, [])
        self.depth += 1
        try:
            out.extend(self.walk(text, 0, len(text), origin=off))
        finally:
            self.depth -= 1

    def env_theorem(self, env, s, b0, b1, out, origin, off):
        spec = self.thm[env]
        k = b0
        note, k2 = read_opt(s, k, b1)
        if note is not None:
            k = k2
        num = None
        if spec["numbered"] and spec["counter"]:
            num = self.refstep(spec["counter"])
        f, line = self.loc(off)
        lid = f"L-{f}-{line}"
        kind = env
        cref_kind = self.crefalias.get(spec["counter"] or env, env) if spec["counter"] and spec["counter"] != env and spec["counter"] in self.crefalias else env
        ctx = self.new_ctx(cref_kind, num or "", auto=lid, keep_auto=True,
                           name=self.walk_inline(spec["display"], off))
        saved = self.cur
        self.cur = ctx
        note_html = self.walk_inline(note, off) if note else ""
        frags = self.walk(s, k, b1, origin)
        self.cur = saved
        head_name = ctx["name"] + (f" {esc_t(num)}" if num else "")
        head = (f'<span class="pr-thm-h"><span class="pr-thm-n">{head_name}</span>'
                + (f'<span class="pr-thm-note"> ({note_html})</span>' if note_html else "")
                + '<span class="pr-thm-p">.</span></span> ')
        body = assemble(frags, first_inline=head)
        style = spec["style"]
        self.thm_lines[lid] = env
        self.printed[(f, line)] = (strip_tags(ctx["name"]).strip(), num or None)
        out.append(block(f'<div class="pr-thm pr-thm--{style}" id="{self.id_ph(ctx)}" data-env="{esc_a(env)}" '
                         f'data-src="{esc_a(f)}:{line}">{self.xa_ph(ctx)}{body}</div>'))
        # What the atlas records at this theorem follows it in a box of its own, named as
        # the atlas's: the paper's statement ends where its author ended it, and the
        # highlight on a linked theorem covers only the author's text.
        mark = lean_pairs().get((self.slug, f, line))
        if mark and (mark["lean"] or mark["headline"]):
            notes = "".join(lean_evidence_html(x) for x in mark["lean"])
            if mark["headline"]:
                notes += headline_note_html(mark["headline"])
            out.append(block(f'<aside class="pr-atlas" aria-label="{esc_a(TXT["atlas_note"])}">'
                             f'<p class="pr-atlas__k">{esc_t(TXT["atlas_note"])}</p>{notes}</aside>'))

    def walk_inline(self, tex: str, off) -> str:
        if not tex:
            return ""
        return inline(self.walk(tex, 0, len(tex), origin=off))

    def env_proof(self, s, b0, b1, out, origin, off):
        note, k = read_opt(s, b0, b1)
        if note is not None:
            head_txt = self.walk_inline(note, off)
            if not re.search(r"[.:!?]\s*(?:</[a-z]+>\s*)*$", strip_tags(head_txt)):
                head_txt += "."
        else:
            pn = self.macros.get("proofname")
            head_txt = (self.walk_inline(pn.body, off) if pn else TXT["proof"]) + "."
            k = b0
        frags = self.walk(s, k, b1, origin)
        body = assemble(frags, first_inline=f'<span class="pr-proof-h">{head_txt}</span> ')
        qed = '<span class="pr-qed" aria-hidden="true">□</span>'
        if body.endswith("</p>"):
            body = body[:-4] + qed + "</p>"
        else:
            body += f'<p class="pr-qed-line">{qed}</p>'
        out.append(block(f'<div class="pr-proof">{body}</div>'))

    # lists ------------------------------------------------------------------

    def list_options(self, opt: str | None):
        """enumitem key=value options or an enumerate-package label template."""
        res = {"label": None, "ref": None, "start": None, "resume": False}
        if not opt:
            return res
        o = opt.strip()
        if re.search(r"(?<![A-Za-z@\\])(label|ref|start|resume|series|leftmargin|itemsep|nosep|noitemsep|wide|"
                     r"align|labelindent|labelsep|topsep|parsep|partopsep|before|after|font|widest|"
                     r"itemindent|listparindent|labelwidth|rightmargin|beginpenalty|style|format|"
                     r"mode|shortlabels|first|last)\b", o) or "=" in o:
            for key, val in self.keyvals(o):
                if key in ("label", "label*"):
                    res["label"] = val
                elif key == "ref":
                    res["ref"] = val
                elif key == "start":
                    try:
                        res["start"] = int(val)
                    except ValueError:
                        pass
                elif key in ("resume", "resume*"):
                    res["resume"] = True
            return res
        # enumerate-package template: the first of 1 a A i I outside commands/braces is the counter
        out = []
        k = 0
        found = False
        depth = 0
        while k < len(o):
            c = o[k]
            if c == "\\":
                mm = CS_RE.match(o, k)
                out.append(mm.group(0))
                k = mm.end()
                continue
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            if not found and depth == 0 and c in "1aAiI":
                out.append({"1": r"\arabic*", "a": r"\alph*", "A": r"\Alph*", "i": r"\roman*", "I": r"\Roman*"}[c])
                found = True
            else:
                out.append(c)
            k += 1
        if found:
            res["label"] = "".join(out)
        return res

    @staticmethod
    def keyvals(o: str):
        items = []
        depth = 0
        cur = []
        for c in o:
            if c == "{":
                depth += 1
            elif c == "}":
                depth -= 1
            if c == "," and depth == 0:
                items.append("".join(cur))
                cur = []
            else:
                cur.append(c)
        items.append("".join(cur))
        res = []
        for it in items:
            if "=" in it:
                key, val = it.split("=", 1)
                val = val.strip()
                if val.startswith("{") and val.endswith("}") and match_brace(val, 0, len(val)) == len(val):
                    val = val[1:-1]
                res.append((key.strip(), val))
            elif it.strip():
                res.append((it.strip(), ""))
        return res

    def env_list(self, env, s, b0, b1, out, origin, off):
        kind = {"compactenum": "enumerate", "inparaenum": "enumerate", "asparaenum": "enumerate",
                "enumerate*": "enumerate", "steps": "enumerate", "conditions": "enumerate",
                "compactitem": "itemize", "itemize*": "itemize", "inparaitem": "itemize",
                "compactdesc": "description"}.get(env, env)
        opt, k = read_opt(s, b0, b1)
        if opt is None:
            k = b0
        opts = self.list_options(opt) if kind != "description" else {"label": None, "ref": None, "start": None,
                                                                      "resume": False}
        self.list_depth += 1
        level = 0
        counter = None
        if kind == "enumerate":
            self.enum_depth += 1
            level = min(self.enum_depth, 4)
            counter = "enum" + ["i", "ii", "iii", "iv"][level - 1]
            if opts["resume"] and level in self.enum_last:
                self.counters[counter] = self.enum_last[level]
            else:
                self.counters[counter] = (opts["start"] - 1) if opts["start"] is not None else 0
            for ch in self.reset.get(counter, ()):
                self.zero(ch)
        label_tpl = opts["label"]
        if kind == "enumerate" and label_tpl is None:
            lm = self.macros.get("labelenum" + ["i", "ii", "iii", "iv"][level - 1])
            if lm:
                label_tpl = lm.body
        ref_tpl = opts["ref"] or label_tpl
        items = top_level(s, k, b1, re.compile(r"\\item(?![A-Za-z@])"))
        pre = s[k:items[0][0]] if items else s[k:b1]
        lis = []
        saved = self.cur
        for idx, (a, b) in enumerate(items):
            seg_end = items[idx + 1][0] if idx + 1 < len(items) else b1
            lab_opt, k2 = read_opt(s, b, seg_end)
            body_start = k2 if lab_opt is not None else b
            item_ctx = None
            if kind == "enumerate":
                if lab_opt is None:
                    self.step(counter)
                    value = self.counters[counter]
                    label_html, ref_txt = self.enum_label(level, value, label_tpl, ref_tpl, off)
                    item_ctx = self.new_ctx(counter, ref_txt, auto=f"pr-item-{len(self.ctxs)}")
                    self.cur = item_ctx
                else:
                    label_html = self.walk_inline(lab_opt, off)
                    item_ctx = self.new_ctx(counter, strip_tags(label_html), auto=f"pr-item-{len(self.ctxs)}")
            elif kind == "itemize":
                if lab_opt is not None:
                    label_html = self.walk_inline(lab_opt, off)
                else:
                    label_html = ["•", "–", "∗", "·"][min(self.list_depth, 4) - 1] if label_tpl is None else \
                        self.walk_inline(label_tpl, off)
            else:
                label_html = self.walk_inline(lab_opt, off) if lab_opt is not None else ""
            frags = self.walk(s, body_start, seg_end, origin)
            body = assemble(frags)
            if kind == "description":
                lis.append(f'<dt>{label_html}</dt><dd>{body}</dd>')
            else:
                id_attr = f' id="{self.id_ph(item_ctx)}"' if item_ctx else ""
                xa = self.xa_ph(item_ctx) if item_ctx else ""
                lis.append(f'<li{id_attr}>{xa}<span class="pr-li-lab">{label_html}</span>'
                           f'<div class="pr-li-body">{body}</div></li>')
        self.cur = saved
        if pre.strip():
            pre_frags = self.walk(s, k, items[0][0] if items else b1, origin)
            if inline(pre_frags):
                out.extend(pre_frags)
        if kind == "enumerate":
            self.enum_last[level] = self.counters[counter]
            self.enum_depth -= 1
        self.list_depth -= 1
        if kind == "description":
            out.append(block(f'<dl class="pr-desc">{"".join(lis)}</dl>'))
        else:
            tag = "ol" if kind == "enumerate" else "ul"
            out.append(block(f'<{tag} class="pr-list">{"".join(lis)}</{tag}>'))

    def enum_label(self, level: int, value: int, label_tpl, ref_tpl, off):
        styles = {1: "arabic", 2: "alph", 3: "roman", 4: "Alph"}
        if label_tpl is None:
            core = numfmt(styles[level], value)
            label = {1: f"{core}.", 2: f"({core})", 3: f"{core}.", 4: f"{core}."}[level]
            # LaTeX prefixes a nested item's reference with its parents' (\p@enumii).
            if level == 1:
                ref = core
            else:
                parents = [self.counters["enum" + ["i", "ii", "iii"][lv - 1]] for lv in range(1, level)]
                pref = numfmt("arabic", parents[0])
                if level >= 3:
                    pref += f"({numfmt('alph', parents[1])})"
                if level >= 4:
                    pref += numfmt("roman", parents[2])
                ref = pref + core
            return esc_t(label), ref

        def fill(tpl):
            t = re.sub(r"\\(arabic|alph|Alph|roman|Roman)\*", lambda m_: numfmt(m_.group(1), value), tpl)
            t = re.sub(r"\\the(enumi{1,3}v?|enumiv)", lambda m_: self.the(m_.group(1)), t)
            t = re.sub(r"\\(arabic|alph|Alph|roman|Roman)\s*\{(enumi{1,3}v?|enumiv)\}",
                       lambda m_: numfmt(m_.group(1), self.counters.get(m_.group(2), 0)), t)
            return t
        label_html = self.walk_inline(fill(label_tpl), off)
        ref_txt = strip_tags(self.walk_inline(fill(ref_tpl or label_tpl), off)).strip()
        if ref_tpl is label_tpl and ref_txt.endswith(".") and not ref_txt.endswith(".."):
            ref_txt = ref_txt[:-1]
        return label_html, ref_txt

    # floats -----------------------------------------------------------------

    def env_float(self, env, s, b0, b1, out, origin, off):
        _, k = read_opt(s, b0, b1)
        if env in ("wrapfigure", "wraptable"):
            _, k = read_opt(s, k, b1)
            _, k = read_arg(s, k, b1)
            _, k = read_arg(s, k, b1)
        kind = "table" if "table" in env else "figure"
        saved = (self.float_kind, self.float_ctx, self.float_captions, self.cur)
        self.float_kind = kind
        self.float_ctx = self.new_ctx(kind, "", auto=f"pr-float-{len(self.ctxs)}")
        self.float_captions = 0
        frags = self.walk(s, k, b1, origin)
        ctx = self.float_ctx
        self.float_kind, self.float_ctx, self.float_captions, self.cur = saved
        # LaTeX keeps the float's \label on its caption: restore the outer label target
        body = assemble(frags)
        body = re.sub(r'(<div class="pr-ph pr-ph--(\w+)"[^>]*>.*?</div>)(\s*\1)+', r"\1", body)
        self.figures_from_html(body)
        out.append(block(f'<div class="pr-float pr-float--{kind}" id="{self.id_ph(ctx)}">{self.xa_ph(ctx)}{body}</div>'))

    def placeholder(self, kind: str, inline_: bool) -> str:
        text = {"tikz": TXT["fig_tikz"], "image": TXT["fig_image"]}.get(kind, TXT["fig_other"])
        h = f'<div class="pr-ph pr-ph--{kind}" role="img" aria-label="{esc_a(text)}">{esc_t(text)}</div>'
        if self.float_kind is None:
            self.figures[kind] += 1
        return block(h)

    def figures_from_html(self, body: str):
        n = 0
        for mm in re.finditer(r'<div class="pr-ph pr-ph--(\w+)"', body):
            self.figures[mm.group(1)] += 1
            n += 1
        if n == 0 and self.float_kind is None and "pr-cap" in body and "<table" not in body:
            pass

    # tables -----------------------------------------------------------------

    def parse_colspec(self, spec: str):
        cols = []
        k = 0
        n = len(spec)
        while k < n:
            c = spec[k]
            if c in "lcrLCRXJ":
                cols.append({"l": "left", "c": "center", "r": "right", "L": "left", "C": "center", "R": "right",
                             "X": "left", "J": "left"}[c])
                k += 1
            elif c in "pmbw":
                k += 1
                if c == "w":
                    _, k = read_arg(spec, k, n)
                    cols.append("left")
                    _, k = read_arg(spec, k, n)
                    continue
                _, k = read_arg(spec, k, n)
                cols.append("left")
            elif c in "@!><":
                k += 1
                _, k = read_arg(spec, k, n)
            elif c == "*":
                k += 1
                cnt, k = read_arg(spec, k, n)
                sub, k = read_arg(spec, k, n)
                try:
                    cols.extend(self.parse_colspec(sub) * int(cnt.strip()))
                except ValueError:
                    pass
            elif c == "S":
                k += 1
                if k < n and spec[k] == "[":
                    _, k = read_opt(spec, k, n)
                cols.append("center")
            else:
                k += 1
        return cols

    def env_table(self, env, s, b0, b1, origin, off) -> str:
        k = b0
        if env in ("tabular*", "tabularx", "tabulary", "xtabular"):
            _, k = read_arg(s, k, b1)
        _, k = read_opt(s, k, b1)
        if env in ("tblr", "longtblr"):
            spec, k = read_arg(s, k, b1)
            cols = []
        else:
            spec, k = read_arg(s, k, b1)
            cols = self.parse_colspec(spec)
        body_rows = split_top(s, k, b1, ROW_SEP)
        rows_html = []
        caption_html = ""
        border_next = False
        skip_mode = None
        rows = []
        # longtable: keep the first head, the body and the last foot
        segments = []
        for (r0, r1, sep) in body_rows:
            segments.append((r0, r1))
        for (r0, r1) in segments:
            text = s[r0:r1]
            if not text.strip():
                continue
            # leading rules and longtable markers
            rule = False
            pos = r0
            while True:
                pos = skip_ws(s, pos, r1)
                mm = re.compile(r"\\(hline|toprule|midrule|bottomrule|cmidrule|cline|addlinespace|specialrule|"
                                r"hhline|endhead|endfirsthead|endfoot|endlastfoot|morecmidrules|noalign|"
                                r"rowcolor|cdashline|hdashline|Xhline|svhline|centering|label|caption|"
                                r"footnotesize|small|tabularnewline)(?![A-Za-z@])").match(s, pos, r1)
                if not mm:
                    break
                word = mm.group(1)
                pos = mm.end()
                if word in ("hline", "toprule", "midrule", "bottomrule", "Xhline", "specialrule", "hhline"):
                    rule = True
                if word in ("cmidrule", "cline", "specialrule", "Xhline", "hhline", "noalign", "rowcolor",
                            "cdashline", "addlinespace"):
                    _, pos = read_paren(s, pos, r1)
                    _, pos = read_opt(s, pos, r1)
                    if word not in ("addlinespace",):
                        _, pos = read_arg(s, pos, r1)
                    if word == "specialrule":
                        _, pos = read_arg(s, pos, r1)
                        _, pos = read_arg(s, pos, r1)
                if word in ("endhead", "endfoot", "endlastfoot"):
                    skip_mode = word
                if word == "endfirsthead":
                    skip_mode = "firsthead"
                if word == "label":
                    lab, pos = read_arg(s, pos, r1)
                    self.set_label(lab)
                if word == "caption":
                    cap_frags = []
                    self.float_kind = self.float_kind or "table"
                    pos = self.h_caption("caption", s, mm.start(), mm.end(), r1, cap_frags, origin)
                    caption_html += "".join(cap_frags).replace(BO, "").replace(BC, "")
            if rule:
                border_next = True
            if pos >= r1 or not s[pos:r1].strip():
                continue
            cells = split_top(s, pos, r1, re.compile(r"&"))
            row = []
            for (c0, c1, _) in cells:
                ctext = s[c0:c1]
                span = 1
                align = None
                mcm = re.match(r"\s*\\multicolumn\s*\{\s*(\d+)\s*\}", ctext)
                frag_start, frag_end = c0, c1
                if mcm:
                    span = int(mcm.group(1))
                    kk = c0 + mcm.end()
                    cs, kk = read_arg(s, kk, c1)
                    al = self.parse_colspec(cs)
                    align = al[0] if al else None
                    kk2 = skip_ws(s, kk, c1)
                    if kk2 < c1 and s[kk2] == "{":
                        e = match_brace(s, kk2, c1)
                        frag_start, frag_end = kk2 + 1, e - 1
                mr = re.match(r"\s*\\multirow\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}\s*(?:\[[^\]]*\])?\s*\{[^{}]*\}\s*"
                              r"(?:\[[^\]]*\])?\s*\{", s[frag_start:frag_end])
                if mr:
                    b = frag_start + mr.end() - 1
                    e = match_brace(s, b, frag_end)
                    frag_start, frag_end = b + 1, e - 1
                cell_html = inline(self.walk(s, frag_start, frag_end, origin))
                row.append((cell_html, span, align))
            if skip_mode in ("endhead_done",):
                continue
            rows.append((row, border_next))
            border_next = False
        for row, border in rows:
            tds = []
            col = 0
            for cell_html, span, align in row:
                al = align or (cols[col] if col < len(cols) else "left")
                attrs = f' colspan="{span}"' if span > 1 else ""
                if al and al != "left":
                    attrs += f' class="pr-{al}"'
                tds.append(f"<td{attrs}>{cell_html}</td>")
                col += span
            cls = ' class="pr-rule"' if border else ""
            rows_html.append(f"<tr{cls}>{''.join(tds)}</tr>")
        cap = f'<div class="pr-tcap">{caption_html}</div>' if caption_html else ""
        return f'{cap}<div class="pr-tbl"><table>{"".join(rows_html)}</table></div>'

    def env_tabbing(self, s, b0, b1, origin) -> str:
        rows = split_top(s, b0, b1, ROW_SEP)
        lines = []
        for r0, r1, _ in rows:
            t = s[r0:r1]
            t = re.sub(r"\\[=>+\-<]", "\u2003", t).replace("\\kill", "")
            lines.append(inline(self.walk(t, 0, len(t), origin=self.abs_off(origin, r0))))
        return f'<p class="pr-tabbing">{"<br>".join(x for x in lines if x)}</p>'

    def env_verbatim(self, env, s, b0, b1, origin, off) -> str:
        body = s[b0:b1]
        if env in ("lstlisting", "Verbatim", "minted", "BVerbatim", "LVerbatim", "Verbatim*", "lstlisting*"):
            o, k = read_opt(body, 0, len(body))
            if env == "minted":
                _, k = read_arg(body, k, len(body))
            if o is not None or env == "minted":
                body = body[k:]
        # expand_tex dropped comments: reread the lines from the file when we can
        if origin is None:
            f0, l0 = self.loc(b0)
            f1, l1 = self.loc(b1)
            lines = self.raw_file_lines(f0) if f0 == f1 else None
            if lines and 0 < l0 <= l1 <= len(lines):
                raw = "\n".join(lines[l0 - 1:l1])
                a = raw.find("\\begin{" + env + "}")
                z = raw.rfind("\\end{" + env + "}")
                if a >= 0 and z > a:
                    raw = raw[a + len("\\begin{" + env + "}"):z]
                    if env in ("lstlisting", "Verbatim", "minted", "BVerbatim", "LVerbatim", "Verbatim*"):
                        o, k = read_opt(raw, 0, len(raw))
                        if env == "minted":
                            _, k = read_arg(raw, k, len(raw))
                        if o is not None or env == "minted":
                            raw = raw[k:]
                    body = raw
        body = body.strip("\n")
        return f'<pre class="pr-verb"><code>{esc_t(body)}</code></pre>'

    # bibliography -----------------------------------------------------------

    def env_thebibliography(self, s, b0, b1, origin, off):
        _, k = read_arg(s, b0, b1)
        items = top_level(s, k, b1, re.compile(r"\\bibitem(?![A-Za-z@])"))
        entries = []
        n = 0
        for idx, (a, b) in enumerate(items):
            seg_end = items[idx + 1][0] if idx + 1 < len(items) else b1
            lab, k2 = read_opt(s, b, seg_end)
            key, k3 = read_arg(s, k2, seg_end)
            n += 1
            saved = self.cur
            frags = self.walk(s, k3, seg_end, origin)
            self.cur = saved
            text = inline(frags)
            label = self.walk_inline(lab, off) if lab is not None else str(n)
            entries.append({"key": key.strip(), "label": label, "html": text})
        self.thebib = entries

    def load_bib_entries(self):
        entries = {}
        for name in self.bibfiles:
            cands = []
            for base in (self.main.parent, self.mdir, self.mdir / "build"):
                p = base / name
                cands += [p, p.with_name(p.name + ".bib")]
            for c in cands:
                if c.is_file():
                    try:
                        parsed = bd.parse_bib(c.read_text(encoding="utf-8", errors="replace"))
                    except Exception:  # noqa: BLE001
                        parsed = {}
                    for key, e in parsed.items():
                        entries.setdefault(key, e)
                    break
        return entries

    def build_bibliography(self):
        """Labels and HTML for the bibliography; returns {key: label}."""
        if self.thebib is not None:
            labels = {}
            items = []
            for e in self.thebib:
                labels.setdefault(e["key"], e["label"])
                items.append((e["key"], e["label"], e["html"]))
            self.bib_items = items
            return labels
        if not self.bibfiles:
            self.bib_items = []
            return {}
        db = self.load_bib_entries()
        keys = list(db) if self.nocite_all else []
        for key in self.cite_order:
            if key not in keys:
                keys.append(key)
        present = [k for k in keys if k in db]
        style = (self.bibstyle or "plain").split("/")[-1]
        family = "alpha" if "alpha" in style else ("unsrt" if style.startswith(("unsrt", "ieeetr")) else "sorted")
        recs = {k: self.bib_record(k, db[k]) for k in present}
        if family == "unsrt":
            order = present
        else:
            order = sorted(present, key=lambda k_: recs[k_]["sort"])
        labels = {}
        if family == "alpha":
            base = {k: recs[k]["alpha"] for k in order}
            counts = Counter(base.values())
            seen = Counter()
            order = sorted(present, key=lambda k_: (purify(base[k_]), recs[k_]["sort"]))
            for k in order:
                lab = base[k]
                if counts[lab] > 1:
                    lab = lab + "abcdefghijklmnopqrstuvwxyz"[seen[base[k]] % 26]
                    seen[base[k]] += 1
                labels[k] = lab
        else:
            for n, k in enumerate(order, 1):
                labels[k] = str(n)
        self.bib_items = [(k, labels[k], recs[k]["html"]) for k in order]
        return labels

    def bib_field(self, e, name):
        v = e["fields"].get(name)
        if not v:
            return ""
        return self.walk_inline(v, None)

    def bib_record(self, key, e):
        f = e["fields"]
        typ = e["type"]
        names = parse_names(f.get("author") or f.get("editor") or "")
        authors_html = self.format_names(names)
        title = self.bib_field(e, "title")
        year = re.sub(r"[{}]", "", f.get("year", "") or "")
        parts = []
        if authors_html:
            parts.append(authors_html + ("" if f.get("author") else (", editors" if len(names) > 1 else ", editor")))
        if typ in ("book", "phdthesis", "mastersthesis", "proceedings", "manual"):
            if title:
                parts.append(f"<i>{title}</i>")
        elif title:
            parts.append(title)
        where = []
        if typ == "article":
            j = self.bib_field(e, "journal")
            if j:
                where.append(f"<i>{j}</i>")
            vol = self.bib_field(e, "volume")
            num = self.bib_field(e, "number")
            pages = self.bib_field(e, "pages")
            vn = vol + (f"({num})" if num else "")
            if vn:
                where.append(vn + (f":{pages}" if pages else ""))
            elif pages:
                where.append(f"pages {pages}")
        elif typ in ("inproceedings", "incollection", "inbook", "conference"):
            bt = self.bib_field(e, "booktitle")
            eds = parse_names(f.get("editor") or "") if f.get("author") else []
            lead = "In "
            if eds:
                lead += self.format_names(eds) + (", editors, " if len(eds) > 1 else ", editor, ")
            if bt:
                where.append(lead + f"<i>{bt}</i>")
            pages = self.bib_field(e, "pages")
            if pages:
                where.append(f"pages {pages}")
            pub = self.bib_field(e, "publisher")
            if pub:
                where.append(pub)
        elif typ in ("book", "proceedings"):
            series = self.bib_field(e, "series")
            vol = self.bib_field(e, "volume")
            if series:
                where.append(series + (f" {vol}" if vol else ""))
            pub = self.bib_field(e, "publisher")
            if pub:
                where.append(pub)
            ed = self.bib_field(e, "edition")
            if ed:
                where.append(f"{ed} edition")
        elif typ in ("phdthesis", "mastersthesis"):
            where.append("PhD thesis" if typ == "phdthesis" else "Master's thesis")
            sch = self.bib_field(e, "school")
            if sch:
                where.append(sch)
        elif typ == "techreport":
            inst = self.bib_field(e, "institution")
            num = self.bib_field(e, "number")
            where.append("Technical Report" + (f" {num}" if num else ""))
            if inst:
                where.append(inst)
        else:
            hp = self.bib_field(e, "howpublished")
            if hp:
                where.append(hp)
            pub = self.bib_field(e, "publisher") or self.bib_field(e, "organization") or self.bib_field(e, "institution")
            if pub:
                where.append(pub)
        if year:
            where.append(esc_t(year))
        if where:
            parts.append(", ".join(where))
        note = self.bib_field(e, "note")
        if note:
            parts.append(note)
        links = []
        doi = (f.get("doi") or "").strip()
        if doi:
            d = clean_url(re.sub(r"^https?://(dx\.)?doi\.org/", "", doi))
            links.append(f'<a href="https://doi.org/{esc_a(d)}" rel="noopener">doi:{esc_t(d)}</a>')
        eprint = (f.get("eprint") or "").strip()
        arch = (f.get("archiveprefix") or f.get("eprinttype") or "").lower()
        if eprint and (arch in ("arxiv", "") and re.match(r"^\d{4}\.\d{4,5}(v\d+)?$|^[a-z\-]+(\.[A-Z]{2})?/\d{7}", eprint)):
            links.append(f'<a href="https://arxiv.org/abs/{esc_a(eprint)}" rel="noopener">arXiv:{esc_t(eprint)}</a>')
        url = (f.get("url") or "").strip()
        if url and not doi:
            href = safe_href(url)
            if href:
                links.append(f'<a href="{esc_a(href)}" rel="noopener">{esc_t(clean_url(url))}</a>')
        text = ". ".join(p.rstrip(". ") for p in parts if p)
        if text:
            text += "."
        if links:
            text += " " + ", ".join(links) + "."
        sort_names = "   ".join(purify(f"{n['von']} {n['last']}  {n['first']}  {n['jr']}") for n in names) or purify(key)
        title_sort = purify(re.sub(r"^(A|An|The)\s+", "", strip_tags(title)))
        rec = {"html": text, "sort": f"{sort_names}    {purify(year)}    {title_sort}",
               "alpha": alpha_label(names, year, key)}
        return rec

    @staticmethod
    def format_names(names) -> str:
        shown = []
        for n in names:
            if n.get("others"):
                shown.append("others")
                continue
            parts = [n["first"], n["von"], n["last"]]
            nm = " ".join(p for p in parts if p)
            if n["jr"]:
                nm += ", " + n["jr"]
            shown.append(nm)
        shown = [detex_name(x) for x in shown]
        if not shown:
            return ""
        if shown[-1] == "others":
            return esc_t(", ".join(shown[:-1])) + " et al."
        if len(shown) == 1:
            return esc_t(shown[0])
        if len(shown) == 2:
            return esc_t(f"{shown[0]} and {shown[1]}")
        return esc_t(", ".join(shown[:-1]) + ", and " + shown[-1])

    # ------------------------------------------------------------ maths

    def dollar(self, s, i, end, out, origin):
        off = self.abs_off(origin, i)
        if s.startswith("$$", i):
            k = find_math_end(s, i + 2, end, "$$")
            out.extend(self.display_math(s[i + 2:k], off))
            return min(end, k + 2)
        k = find_math_end(s, i + 1, end, "$")
        out.append(self.inline_math(s[i + 1:k], off))
        return min(end, k + 1)

    def h_math_paren(self, name, s, start, j, end, out, origin):
        off = self.abs_off(origin, start)
        if name == "(":
            k = find_math_end(s, j, end, "\\)")
            out.append(self.inline_math(s[j:k], off))
            return min(end, k + 2)
        if name == "[":
            k = find_math_end(s, j, end, "\\]")
            out.extend(self.display_math(s[j:k], off))
            return min(end, k + 2)
        return j

    def prep_math(self, tex: str, off) -> str:
        """Prepare a formula for KaTeX: expand what only this script can expand,
        resolve references and citations, and drop labels (recorded by the caller)."""
        tex = katex_compat(self.expand_in_math(tex))
        tex = QEDHERE_RE.sub("", tex)
        tex = re.sub(r"\\(?:allowdisplaybreaks|displaybreak)(?![A-Za-z@])(?:\s*\[\d\])?", "", tex)
        tex = re.sub(r"\\(?:hypertarget)\s*\{[^{}]*\}", "", tex)
        tex = re.sub(r"\\(?:index|nocite)\s*\{[^{}]*\}", "", tex)
        tex = re.sub(r"\\(?:protect|phantomsection)(?![A-Za-z@])", "", tex)
        tex = re.sub(r"\\begin\{(array|subarray|tabular)\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}",
                     lambda m_: "\\begin{" + ("array" if m_.group(1) == "tabular" else m_.group(1)) + "}{"
                     + self.katex_colspec(m_.group(2)) + "}", tex)
        tex = tex.replace("\\begin{tabular}", "\\begin{array}").replace("\\end{tabular}", "\\end{array}")
        tex = tex.replace(r"\begin{psmallmatrix}", r"\left(\begin{smallmatrix}").replace(
            r"\end{psmallmatrix}", r"\end{smallmatrix}\right)")
        tex = tex.replace(r"\begin{bsmallmatrix}", r"\left[\begin{smallmatrix}").replace(
            r"\end{bsmallmatrix}", r"\end{smallmatrix}\right]")
        tex = tex.replace(r"\begin{multlined}", r"\begin{gathered}").replace(r"\end{multlined}", r"\end{gathered}")
        tex = MATH_REF_RE.sub(lambda m_: self.math_ref(m_, off), tex)
        tex = MATH_CITE_RE.sub(lambda m_: self.math_cite(m_, off), tex)
        tex = re.sub(r"\\texorpdfstring\s*\{((?:[^{}]|\{[^{}]*\})*)\}\s*\{(?:[^{}]|\{[^{}]*\})*\}", r"\1", tex)
        tex = re.sub(r"\\(?:footnote|thanks)\s*\{(?:[^{}]|\{[^{}]*\})*\}", "", tex)
        tex = re.sub(r"\\(?:hyperlink)\s*\{[^{}]*\}\s*\{((?:[^{}]|\{[^{}]*\})*)\}", r"\1", tex)
        tex = re.sub(r"\\url\s*\{([^{}]*)\}", lambda m_: "\\texttt{" + m_.group(1).replace("_", "\\_").replace("#", "\\#") + "}", tex)
        tex = re.sub(r"(?<!\\)%.*", "", tex)
        return tex.strip()

    @staticmethod
    def katex_colspec(spec: str) -> str:
        out = []
        k = 0
        n = len(spec)
        while k < n:
            c = spec[k]
            if c in "lcr|:":
                out.append(c)
                k += 1
            elif c in "pmbw":
                k += 1
                _, k = read_arg(spec, k, n)
                if c == "w":
                    _, k = read_arg(spec, k, n)
                out.append("l")
            elif c in "@!><":
                k += 1
                _, k = read_arg(spec, k, n)
            elif c == "*":
                k += 1
                cnt, k = read_arg(spec, k, n)
                sub, k = read_arg(spec, k, n)
                try:
                    out.append(Paper.katex_colspec(sub) * int(cnt.strip()))
                except ValueError:
                    pass
            elif c in "LCRX":
                out.append(c.lower() if c != "X" else "l")
                k += 1
            else:
                k += 1
        return "".join(out) or "c"

    def math_ref(self, mm, off) -> str:
        name = mm.group(1)
        labels = [x.strip() for x in mm.group(3).split(",") if x.strip()]
        extra = mm.group(4) if name in ("crefrange", "Crefrange") else None
        self.placeholders.append((("ref", name, labels, extra), off, "math"))
        self.ref_total += 1
        tail = ("{" + mm.group(4) + "}") if (mm.group(4) is not None and extra is None) else ""
        return f"\\text{{{PH_O}{len(self.placeholders) - 1}{PH_C}}}{tail}"

    def math_cite(self, mm, off) -> str:
        name = mm.group(1)
        keys = [x.strip() for x in mm.group(4).split(",") if x.strip()]
        opts = re.findall(r"\[([^\]]*)\]", mm.group(3) or "")
        pre = post = ""
        if len(opts) == 1:
            post = opts[0]
        elif len(opts) == 2:
            pre, post = opts
        for key in keys:
            self.note_cite(key)
        self.placeholders.append((("cite", name, keys, esc_t(pre), esc_t(post), bool(mm.group(2))), off, "math"))
        self.cite_total += 1
        return f"\\text{{{PH_O}{len(self.placeholders) - 1}{PH_C}}}"

    def take_labels(self, tex: str):
        labels = [x.strip() for x in LABEL_RE.findall(tex)]
        return LABEL_RE.sub("", tex), labels

    def register(self, tex: str, display: bool, off) -> int:
        self.formulas.append({"tex": tex, "display": display, "off": off})
        return len(self.formulas) - 1

    def inline_math(self, tex: str, off) -> str:
        tex, labels = self.take_labels(tex)
        for lab in labels:
            self.set_label(lab)
        if self.has_figure_tex(tex):
            return self.placeholder("tikz", inline_=True)
        tex = self.prep_math(tex, off)
        if not tex:
            return ""
        idx = self.register(tex, False, off)
        return f'<span class="pr-m" data-f="{idx}">{esc_t(tex)}</span>'

    @staticmethod
    def has_figure_tex(tex: str) -> bool:
        return bool(re.search(r"\\begin\{(?:tikzcd|tikzpicture|xy|pspicture)\}|\\xymatrix|\\tikz(?![A-Za-z@])", tex))

    def diagram_display(self, body: str, base: str, star: bool, off) -> str:
        """A displayed diagram KaTeX cannot draw: a placeholder that keeps the display's
        equation number and labels, so references to the diagram still resolve."""
        tex, labels = self.take_labels(body)
        num = None
        tag = self.extract_tag(tex)
        if tag:
            num = self.tag_text(tag[2], off)
        elif base in ("equation", "dmath") and not star and not NONUM_RE.search(tex):
            num = self.next_equation_number()
        ctx = self.new_ctx("equation", "", auto=f"pr-eq-{len(self.formulas)}-{len(self.labels)}-d")
        if num is not None:
            ctx["num"] = num
        for lab in labels:
            self.set_label(lab, ctx=ctx, num=num, kind="equation" if num is not None else None)
        if self.float_kind is None:
            self.figures["tikz"] += 1
        text = TXT["fig_tikz"]
        no = f'<span class="pr-eqno">({esc_t(num)})</span>' if num is not None else ""
        return block(f'<div class="pr-eq pr-eq--diagram" id="{self.id_ph(ctx)}">{self.xa_ph(ctx)}'
                     f'<div class="pr-ph pr-ph--tikz" role="img" aria-label="{esc_a(text)}">{esc_t(text)}</div>{no}</div>')

    def display_math(self, tex: str, off, eq_ctx=None) -> list:
        """An unnumbered display (\\[...\\], $$...$$), unless it carries \\tag or \\label."""
        if self.has_figure_tex(tex):
            return [self.diagram_display(tex, "displaymath", True, off)]
        tex, labels = self.take_labels(tex)
        tag = self.extract_tag(tex)
        ctx = self.new_ctx("equation", "", auto=f"pr-eq-{len(self.formulas)}")
        if tag:
            tex, star, tag_tex = tag
            tag_txt = self.tag_text(tag_tex, off)
            for lab in labels:
                self.set_label(lab, ctx=ctx, num=tag_txt, kind="equation")
            tex = tex + ("\\tag*{" if star else "\\tag{") + tag_tex + "}"
        else:
            for lab in labels:
                self.set_label(lab, ctx=ctx)
        return self.intertext_split(tex, ctx, off)

    def extract_tag(self, tex: str):
        mm = TAG_RE.search(tex)
        if not mm:
            return None
        e = match_brace(tex, mm.end() - 1, len(tex))
        tag_tex = tex[mm.end():e - 1]
        return tex[:mm.start()] + tex[e:], bool(mm.group(1)), tag_tex

    def tag_text(self, tag_tex: str, off) -> str:
        return strip_tags(self.walk_inline(tag_tex, off)) if "$" in tag_tex or "\\" in tag_tex else tag_tex.strip()

    def eq_html(self, tex: str, ctx, off, idx_attr=True) -> str:
        tex = self.prep_math(tex, off)
        idx = self.register(tex, True, off)
        return (f'<div class="pr-eq" id="{self.id_ph(ctx)}">{self.xa_ph(ctx)}'
                f'<span class="pr-m" data-d="1" data-f="{idx}">{esc_t(tex)}</span></div>')

    def intertext_split(self, tex: str, ctx, off) -> list:
        return [block(self.eq_html(tex, ctx, off))]

    def next_equation_number(self) -> str:
        if self.subeq is not None:
            self.subeq["n"] += 1
            return self.subeq["parent"] + alph(self.subeq["n"])
        return self.refstep("equation")

    def math_env(self, env: str, body: str, opt: str, off) -> list:
        base = env.rstrip("*")
        star = env.endswith("*")
        if base == "math":
            return [self.inline_math(body, off)]
        if self.has_figure_tex(body):
            return [self.diagram_display(body, base, star, off)]
        if base == "alignat":
            k = skip_ws(body, 0, len(body))
            ncols = "1"
            if k < len(body) and body[k] == "{":
                e = match_brace(body, k, len(body))
                ncols = body[k + 1:e - 1].strip()
                body = body[e:]
        ctx = self.new_ctx("equation", "", auto=f"pr-eq-{len(self.formulas)}")
        if base in ("equation", "displaymath", "dmath"):
            tex, labels = self.take_labels(body)
            nonum = bool(NONUM_RE.search(tex))
            tex = NONUM_RE.sub("", tex)
            tag = self.extract_tag(tex)
            num = None
            if tag:
                tex, tstar, tag_tex = tag
                num = self.tag_text(tag_tex, off)
                tex += ("\\tag*{" if tstar else "\\tag{") + tag_tex + "}"
            elif base != "displaymath" and not star and not nonum:
                num = self.next_equation_number()
                tex += "\\tag{" + num + "}"
            if re.search(r"(?<!\\)\\\\", self.top_level_text(tex)):
                tex = "\\begin{gathered}" + tex + "\\end{gathered}" if "\\tag" not in tex else tex
            saved = self.cur
            if num is not None:
                ctx["num"] = num
                self.cur = ctx
            for lab in labels:
                self.set_label(lab, ctx=ctx, num=num if num is not None else None,
                               kind="equation" if num is not None else None)
            self.cur = saved
            return [block(self.eq_html(tex, ctx, off))]
        # multi-row environments
        kat_env = {"align": "align*", "flalign": "align*", "eqnarray": "align*", "gather": "gather*",
                   "multline": "gather*", "alignat": "alignat*", "dgroup": "gather*"}.get(base, "align*")
        rows = split_top(body, 0, len(body), ROW_SEP)
        # drop a trailing empty row (a final \\ before \end)
        while len(rows) > 1 and not rows[-1][0] < rows[-1][1] or (len(rows) > 1 and not body[rows[-1][0]:rows[-1][1]].strip()):
            last = rows.pop()
            prev = rows[-1]
            rows[-1] = (prev[0], prev[1], "")
            if not rows:
                break
        pieces = []          # list of ("rows", [row tex]) or ("text", tex)
        cur_rows = []
        nrows = len(rows)
        multline_labels = []
        saved = self.cur
        for ri, (r0, r1, sep) in enumerate(rows):
            row = body[r0:r1]
            # \intertext splits the display
            it = INTERTEXT_RE.search(row)
            if it:
                arg, e = read_arg(row, it.end(), len(row))
                before = row[:it.start()]
                if before.strip():
                    cur_rows.append(before + "\\\\")
                if cur_rows:
                    pieces.append(("rows", cur_rows))
                    cur_rows = []
                pieces.append(("text", arg))
                row = row[e:]
            row, labels = self.take_labels(row)
            nonum = bool(NONUM_RE.search(row))
            row = NONUM_RE.sub("", row)
            tag = self.extract_tag(row)
            num = None
            if base == "multline":
                multline_labels += labels
                labels = []
                if ri == nrows - 1:
                    if tag:
                        row, tstar, tag_tex = tag
                        num = self.tag_text(tag_tex, off)
                        row += ("\\tag*{" if tstar else "\\tag{") + tag_tex + "}"
                    elif not star and not nonum:
                        num = self.next_equation_number()
                        row += "\\tag{" + num + "}"
                    for lab in multline_labels:
                        self.set_label(lab, ctx=ctx, num=num, kind="equation" if num else None)
            else:
                if tag:
                    row, tstar, tag_tex = tag
                    num = self.tag_text(tag_tex, off)
                    row += ("\\tag*{" if tstar else "\\tag{") + tag_tex + "}"
                elif not star and not nonum and row.strip():
                    num = self.next_equation_number()
                    row += "\\tag{" + num + "}"
                for lab in labels:
                    self.set_label(lab, ctx=ctx, num=num, kind="equation" if num else None)
            cur_rows.append(row + (sep if sep else ""))
        self.cur = saved
        if cur_rows:
            pieces.append(("rows", cur_rows))
        res = []
        first = True
        for kind, val in pieces:
            if kind == "text":
                res.append(PARA)
                res.extend(self.walk(val, 0, len(val), origin=off))
                res.append(PARA)
                continue
            rows_tex = "".join(val).rstrip()
            rows_tex = re.sub(r"(\\\\\*?(\s*\[[^\]]*\])?\s*)+$", "", rows_tex)
            if kat_env == "alignat*":
                tex = f"\\begin{{alignat*}}{{{ncols}}}{rows_tex}\\end{{alignat*}}"
            else:
                tex = f"\\begin{{{kat_env}}}{rows_tex}\\end{{{kat_env}}}"
            use_ctx = ctx if first else self.new_ctx("equation", "", auto=f"pr-eq-{len(self.formulas)}")
            first = False
            res.append(block(self.eq_html(tex, use_ctx, off)))
        return res

    @staticmethod
    def top_level_text(t: str) -> str:
        out = []
        depth = 0
        for tok in re.split(r"(\\begin\{[^}]*\}|\\end\{[^}]*\}|\{|\})", t):
            if tok.startswith("\\begin{") or tok == "{":
                depth += 1
            elif tok.startswith("\\end{") or tok == "}":
                depth -= 1
            elif depth == 0:
                out.append(tok)
        return "".join(out)

    # ------------------------------------------------------------ the whole document

    def convert(self):
        self.read_definitions()
        t = self.text
        b0 = self.begin_doc + len("\\begin{document}") if self.begin_doc else 0
        self.body_frags = self.walk(t, b0, self.end_doc, None)
        self.abstract_html = ""
        if self.abstract_tex:
            a0, a1 = self.abstract_tex
            saved = self.cur
            self.abstract_html = assemble(self.walk(t, a0, a1, None))
            self.cur = saved
        self.author_html = self.walk_inline(self.author_tex, None) if self.author_tex else ""
        self.date_html = self.walk_inline(self.date_tex, None) if self.date_tex else ""
        self.resolve()

    def resolve(self):
        bib_labels = self.build_bibliography()
        self.bib_labels = bib_labels
        # element ids from labels
        used = set()
        for key in self.labels:
            used.add(key)
        self.ids = {}
        self.extra = {}
        for ctx in self.ctxs:
            labs = ctx["labels"]
            auto = ctx["auto"] or f"pr-x{ctx['i']}"
            if auto in used and not labs:
                auto = f"{auto}-{ctx['i']}"
            if labs:
                eid = labs[0]
                extra = labs[1:] + ([ctx["auto"]] if ctx.get("keep_auto") and ctx["auto"] else [])
            else:
                eid = auto
                extra = []
            used.add(eid)
            self.ids[ctx["i"]] = eid
            self.extra[ctx["i"]] = "".join(f'<span class="pr-lbl" id="{esc_a(x)}"></span>' for x in extra)
        self.unresolved_refs = []
        self.unresolved_cites = []
        self.resolved_cache = {}
        body = assemble(self.body_frags)
        body = body.replace(BIB_MARK, self.bibliography_html(), 1).replace(BIB_MARK, "")
        self.body_html = self.fill(body)
        self.abstract_html = self.fill(self.abstract_html)
        for fn in self.footnotes:
            fn["html"] = self.fill(fn["html"])
        self.toc_html = self.fill(self.render_toc())
        self.author_html = self.fill(self.author_html)
        for f in self.formulas:
            f["tex"] = self.fill_tex(f["tex"])
        # the TeX inside each formula span must match the checked formula exactly
        def span_tex(mm):
            idx = int(mm.group(2))
            return mm.group(1) + esc_t(self.formulas[idx]["tex"]) + "</span>"
        self.body_html = re.sub(r'(<span class="pr-m"(?: data-d="1")? data-f="(\d+)">)[^<]*</span>', span_tex,
                                self.body_html)
        self.abstract_html = re.sub(r'(<span class="pr-m"(?: data-d="1")? data-f="(\d+)">)[^<]*</span>', span_tex,
                                    self.abstract_html)
        for fn in self.footnotes:
            fn["html"] = re.sub(r'(<span class="pr-m"(?: data-d="1")? data-f="(\d+)">)[^<]*</span>', span_tex,
                                fn["html"])
        self.author_html = re.sub(r'(<span class="pr-m"(?: data-d="1")? data-f="(\d+)">)[^<]*</span>', span_tex,
                                  self.author_html)
        self.toc_html = re.sub(r'(<span class="pr-m"(?: data-d="1")? data-f="(\d+)">)[^<]*</span>', span_tex,
                               self.toc_html)

    def fill(self, h: str) -> str:
        h = re.sub(f"{ID_O}(\\d+){ID_C}", lambda mm: esc_a(self.ids.get(int(mm.group(1)), "")), h)
        h = re.sub(f"{XA_O}(\\d+){XA_C}", lambda mm: self.extra.get(int(mm.group(1)), ""), h)
        h = re.sub(f"{PH_O}(\\d+){PH_C}", lambda mm: self.render_placeholder(int(mm.group(1)), html_mode=True), h)
        return h

    def fill_tex(self, t: str) -> str:
        return re.sub(f"{PH_O}(\\d+){PH_C}", lambda mm: self.render_placeholder(int(mm.group(1)), html_mode=False), t)

    # references -------------------------------------------------------------

    def cref_name(self, kind: str, plural_: bool, capital: bool) -> str:
        kind = self.crefalias.get(kind, kind)
        table = self.Crefnames if capital and kind in self.Crefnames else self.crefnames
        if kind in table:
            sing, plur = table[kind]
            name = strip_tags(self.walk_inline(plur if plural_ else sing, None))
            if capital and table is self.crefnames:
                name = name[:1].upper() + name[1:]
            return name
        if kind in self.thm:
            disp = strip_tags(self.walk_inline(self.thm[kind]["display"], None))
            low = disp if (self.cref_capitalise() or capital) else disp[:1].lower() + disp[1:]
            if plural_:
                low = pluralise(low)
            return low[:1].upper() + low[1:] if capital else low
        d = CREF_DEFAULT.get(kind)
        if d is None:
            base = kind
            name = pluralise(base) if plural_ else base
        else:
            abbrev = "noabbrev" not in self.cref_opts and not capital
            if capital and "noabbrev" not in self.cref_opts and kind in ("equation", "figure"):
                abbrev = True
            name = (d[3] if plural_ else d[2]) if abbrev else (d[1] if plural_ else d[0])
        if capital or self.cref_capitalise():
            name = name[:1].upper() + name[1:]
        return name

    def cref_capitalise(self) -> bool:
        return bool({"capitalise", "capitalize"} & self.cref_opts)

    def ref_link(self, label: str, text_html: str) -> str:
        return f'<a class="pr-ref" href="{esc_a(frag_href(self.anchor_of(label)))}">{text_html}</a>'

    def anchor_of(self, label: str) -> str:
        rec = self.labels.get(label)
        if rec is None:
            return label
        return label

    def render_placeholder(self, idx: int, html_mode: bool) -> str:
        item, off, mode = self.placeholders[idx]
        key = (idx, html_mode)
        if key in self.resolved_cache:
            return self.resolved_cache[key]
        if item[0] == "ref":
            res = self.render_ref(item, off, html_mode and mode == "text")
        elif item[0] == "cite":
            res = self.render_cite(item, off, html_mode and mode == "text")
        elif item[0] == "hyperref":
            _, label, inner = item
            if label in self.labels:
                res = self.ref_link(label, inner)
            else:
                self.unresolved_refs.append((label, self.where(off)))
                res = inner
        else:
            res = ""
        if mode == "math":
            res = tex_text_escape(res) if not html_mode else esc_t(tex_text_escape(res))
        self.resolved_cache[key] = res
        return res

    def render_ref(self, item, off, as_html: bool) -> str:
        _, cmd, labels, extra = item
        recs = []
        for lab in labels:
            rec = self.labels.get(lab)
            if rec is None:
                if (lab, self.where(off)) not in self.unresolved_refs:
                    self.unresolved_refs.append((lab, self.where(off)))
            recs.append((lab, rec))

        def num_of(lab, rec, paren=False):
            if rec is None:
                txt = "??"
                return f'<span class="pr-unres" title="{esc_a(lab)}">??</span>' if as_html else txt
            n = rec["num"] or ""
            if paren:
                n = f"({n})"
            return self.ref_link(lab, esc_t(n)) if as_html else n

        if cmd in ("ref", "subref", "labelcref"):
            return ", ".join(num_of(l_, r_) for l_, r_ in recs)
        if cmd in ("eqref", "eqrefs"):
            return ", ".join(num_of(l_, r_, paren=True) for l_, r_ in recs)
        if cmd in ("pageref", "cpageref", "Cpageref", "cpagerefrange"):
            # pages do not exist here: link to the passage instead
            return ", ".join((self.ref_link(l_, "↗") if as_html else "") if r_ else num_of(l_, r_)
                             for l_, r_ in recs)
        if cmd in ("nameref", "Nameref"):
            outs = []
            for l_, r_ in recs:
                if r_ is None:
                    outs.append(num_of(l_, r_))
                    continue
                t = r_.get("title") or r_.get("name") or esc_t(r_["num"] or "")
                outs.append(self.ref_link(l_, t) if as_html else strip_tags(t))
            return ", ".join(outs)
        if cmd in ("namecref", "nameCref", "lcnamecref"):
            l_, r_ = recs[0] if recs else ("", None)
            if r_ is None:
                return num_of(l_, r_)
            nm = self.cref_name(r_["kind"], False, cmd == "nameCref")
            return esc_t(nm.lower() if cmd == "lcnamecref" else nm) if as_html else nm
        capital = cmd in ("Cref", "Crefrange", "Autoref", "Vref") or (
            cmd in ("cref", "crefrange", "vref") and self.cref_capitalise())
        if cmd in ("autoref", "Autoref"):
            capital = True
        if cmd in ("crefrange", "Crefrange"):
            r2 = self.labels.get(extra.strip()) if extra else None
            if r2 is None and extra:
                self.unresolved_refs.append((extra.strip(), self.where(off)))
            l_, r_ = recs[0] if recs else ("", None)
            if r_ is None:
                return num_of(l_, r_)
            nm = self.cref_name(r_["kind"], True, capital)
            paren = r_["kind"] == "equation"
            second = num_of(extra.strip(), r2, paren) if extra else ""
            txt = f"{esc_t(nm) if as_html else nm} {num_of(l_, r_, paren)} to {second}"
            return txt
        # \cref, \Cref, \autoref: group by type in order of appearance
        groups = []
        index = {}
        for l_, r_ in recs:
            kind = self.crefalias.get(r_["kind"], r_["kind"]) if r_ else "??"
            if kind not in index:
                index[kind] = len(groups)
                groups.append((kind, []))
            groups[index[kind]][1].append((l_, r_))
        parts = []
        for gi, (kind, members) in enumerate(groups):
            if kind == "??":
                parts.append(", ".join(num_of(l_, r_) for l_, r_ in members))
                continue
            paren = kind == "equation"
            cap = capital if gi == 0 else (capital and cmd not in ("cref",))
            name = self.cref_name(kind, len(members) > 1, cap)
            nums = [num_of(l_, r_, paren) for l_, r_ in members]
            if len(nums) == 1:
                if as_html:
                    lab0, rec0 = members[0]
                    n0 = rec0["num"] or ""
                    shown = f"({n0})" if paren else n0
                    parts.append(self.ref_link(lab0, esc_t(f"{name} {shown}".strip())))
                else:
                    parts.append(f"{name} {nums[0]}".strip())
            else:
                joined = ", ".join(nums[:-1]) + " and " + nums[-1]
                parts.append(f"{esc_t(name) if as_html else name} {joined}")
        if len(parts) <= 1:
            return "".join(parts)
        return ", ".join(parts[:-1]) + " and " + parts[-1]

    def render_cite(self, item, off, as_html: bool) -> str:
        _, cmd, keys, pre, post, star = item
        labels = self.bib_labels
        missing = [k for k in keys if k not in labels]
        for k in missing:
            self.unresolved_cites.append((k, self.where(off)))
        numeric = all(re.fullmatch(r"\d+", labels.get(k, "0")) for k in keys)
        sortcomp = {"sort&compress", "sort", "compress"} & self.natbib_opts
        items = [(k, labels.get(k)) for k in keys]
        if numeric and "sort&compress" in self.natbib_opts or (numeric and "sort" in self.natbib_opts):
            items.sort(key=lambda kv: int(kv[1]) if kv[1] else 10 ** 9)

        def one(k, lab):
            if lab is None:
                return f'<span class="pr-unres" title="{esc_a(k)}">?</span>' if as_html else "?"
            return (f'<a class="pr-cite" href="#bib-{esc_a(quote(k, safe=""))}">{lab}</a>' if as_html else
                    strip_tags(lab))

        def compress(seq):
            # natbib's compress: runs of three or more consecutive numbers become a range
            if not ({"sort&compress", "compress"} & self.natbib_opts) or not numeric:
                return [one(k, lab) for k, lab in seq]
            out, run = [], []

            def flush():
                if len(run) >= 3:
                    out.append(one(*run[0]) + "–" + one(*run[-1]))
                else:
                    out.extend(one(*x) for x in run)
                run.clear()
            for k, lab in seq:
                if lab is not None and run and run[-1][1] is not None and int(lab) == int(run[-1][1]) + 1:
                    run.append((k, lab))
                else:
                    flush()
                    run.append((k, lab))
            flush()
            return out

        if cmd in ("citeauthor", "Citeauthor"):
            names = [self.bib_author_short(k) for k in keys]
            return ", ".join(esc_t(n) if as_html else n for n in names)
        if cmd in ("citeyear", "citeyearpar"):
            return ", ".join(self.bib_year(k) for k in keys)
        inner = ", ".join(compress(items))
        if pre:
            inner = f"{pre} {inner}"
        if post:
            inner = f"{inner}, {post}"
        if cmd in ("citet", "Citet", "textcite", "Textcite"):
            names = []
            for k, lab in items:
                nm = self.bib_author_short(k)
                names.append(f"{esc_t(nm) if as_html else nm} [{one(k, lab)}]")
            res = ", ".join(names)
            if post:
                res = res[:-1] + f", {post}]" if res.endswith("]") else res
            return res
        if cmd in ("citealp", "citealt", "Citealp", "Citealt", "citenum"):
            return inner
        return f"[{inner}]"

    def bib_author_short(self, key: str) -> str:
        e = getattr(self, "_bibdb", None)
        if e is None:
            self._bibdb = self.load_bib_entries() if self.bibfiles else {}
            e = self._bibdb
        rec = e.get(key)
        if not rec:
            return key
        names = parse_names(rec["fields"].get("author") or rec["fields"].get("editor") or "")
        lasts = [detex_name(n["von"] + " " + n["last"]).strip() for n in names if not n.get("others")]
        if not lasts:
            return key
        if len(lasts) == 1:
            return lasts[0]
        if len(lasts) == 2 and not names[-1].get("others"):
            return f"{lasts[0]} and {lasts[1]}"
        return f"{lasts[0]} et al."

    def bib_year(self, key: str) -> str:
        e = getattr(self, "_bibdb", None)
        if e is None:
            self._bibdb = self.load_bib_entries() if self.bibfiles else {}
            e = self._bibdb
        rec = e.get(key)
        return re.sub(r"[{}]", "", rec["fields"].get("year", "")) if rec else "?"

    def bibliography_html(self) -> str:
        items = getattr(self, "bib_items", [])
        if not items:
            return ""
        rn = self.macros.get("refname") or self.macros.get("bibname")
        heading = strip_tags(self.walk_inline(rn.body, None)) if rn else TXT["references"]
        lis = []
        for key, label, text in items:
            lis.append(f'<li class="pr-bib-item" id="bib-{esc_a(quote(key, safe=""))}">'
                       f'<span class="pr-bib-lab">[{label}]</span><span class="pr-bib-text">{text}</span></li>')
        self.toc_bib = heading
        return (f'<section class="pr-bib" aria-labelledby="pr-references"><h2 class="pr-sec pr-sec--1" '
                f'id="pr-references">{esc_t(heading)}</h2><ol class="pr-bib-list">{"".join(lis)}</ol></section>')

    def render_toc(self) -> str:
        if not self.toc:
            return ""
        out = ['<ol class="pr-toc-list">']
        open_sub = False
        for level, prefix, title_html, ctx in self.toc:
            href = f"#{ID_O}{ctx['i']}{ID_C}"
            num = f'<span class="pr-toc-n">{esc_t(prefix)}</span> ' if prefix else ""
            item = f'<a href="{href}">{num}{title_html}</a>'
            if level == 2:
                if not open_sub:
                    out.append('<ol class="pr-toc-sub">')
                    open_sub = True
                out.append(f"<li>{item}</li>")
            else:
                if open_sub:
                    out.append("</ol>")
                    open_sub = False
                if len(out) > 1:
                    out.append("</li>")
                out.append(f'<li class="pr-toc-{"part" if level == 0 else "sec"}">{item}')
        if open_sub:
            out.append("</ol>")
        if len(out) > 1:
            out.append("</li>")
        if getattr(self, "toc_bib", None):
            out.append(f'<li class="pr-toc-sec"><a href="#pr-references">{esc_t(self.toc_bib)}</a></li>')
        out.append("</ol>")
        h = "".join(out)
        # links in the contents must not carry anchors of their own
        h = re.sub(f"{XA_O}\\d+{XA_C}", "", h)
        h = re.sub(r'<span class="pr-lbl" id="[^"]*"></span>', "", h)
        h = re.sub(r'<a class="pr-(?:ref|cite)" href="[^"]*">(.*?)</a>', r"\1", h)
        return h

    # ------------------------------------------------------------ checks

    def printed_numbers(self) -> list[dict]:
        """What each extracted statement prints on its reading page ("Theorem" and
        "1.1"), bound to the statement as data/manuscripts.json records it. A
        statement the page does not render as a theorem-like block has no row."""
        rows = []
        for st in self.m.get("statements") or []:
            got = self.printed.get((st.get("file"), st.get("line")))
            if got is None:
                continue
            rows.append({"manuscript": self.slug, "file": st["file"], "line": st["line"], "label": st.get("label"),
                         "statement_sha256": st.get("sha256"), "kind": got[0], "number": got[1]})
        return rows

    def printed_labels(self) -> dict:
        """Every \\label of the paper with what a reference to it prints on the reading page:
        [kind, name, number], where name is the theorem-like heading ("Theorem") or null.
        The anchor on the reading page is the label itself (papers/<slug>.html#<label>)."""
        out = {}
        for key in sorted(self.labels):
            rec = self.labels[key]
            num = rec.get("num")
            out[key] = [rec.get("kind") or "", rec.get("name"), "" if num is None else str(num)]
        return out

    def statement_anchors(self):
        """Every extracted statement must have an anchor on the page."""
        missing = []
        ids = set(self.ids.values())
        for st in self.m.get("statements") or []:
            lab = st.get("label")
            lid = f"L-{st.get('file')}-{st.get('line')}"
            if lab:
                if lab not in self.labels:
                    missing.append(lab)
                continue
            if lid not in ids and lid not in self.thm_lines:
                missing.append(lid)
        return missing


# ------------------------------------------------------------ BibTeX helpers

def tex_text_escape(t: str) -> str:
    """Make plain text safe inside \\text{} for KaTeX."""
    t = strip_tags(t) if "<" in t else t
    rep = {"\\": "\\textbackslash{}", "{": "\\{", "}": "\\}", "#": "\\#", "$": "\\$", "%": "\\%", "&": "\\&",
           "_": "\\_", "^": "\\textasciicircum{}", "~": "\\textasciitilde{}"}
    return "".join(rep.get(c, c) for c in t)


def pluralise(w: str) -> str:
    if not w:
        return w
    if w.endswith("y") and not w.endswith(("ay", "ey", "oy", "uy")):
        return w[:-1] + "ies"
    if w.endswith(("s", "x", "ch", "sh")):
        return w + "es"
    if w.endswith("."):
        return w
    return w + "s"


ACCENT_STRIP = re.compile(r"\\[`'^\"~=.uvHtcdbkr](?![A-Za-z])\s*\{?\\?([A-Za-z])\}?|\\[`'^\"~=.]\s*\{?\\?([A-Za-z])\}?")


def detex_name(s: str) -> str:
    """BibTeX name text to plain Unicode."""
    def acc(mm):
        cmd = mm.group(0)[1]
        letter = mm.group(1) or mm.group(2)
        mark = ACCENTS.get(cmd)
        return unicodedata.normalize("NFC", letter + mark) if mark else letter
    s = re.sub(r"\{\\(ss|ae|AE|oe|OE|o|O|l|L|aa|AA|i|j)\}", lambda m_: TEXT_SYMBOLS.get(m_.group(1), m_.group(1)), s)
    s = re.sub(r"\\([`'^\"~=.uvHtcdbkr])\s*\{\s*\\?([A-Za-z])\s*\}",
               lambda m_: unicodedata.normalize("NFC", m_.group(2) + ACCENTS[m_.group(1)]), s)
    s = re.sub(r"\\([`'^\"~=.])\s*\\?([A-Za-z])", lambda m_: unicodedata.normalize("NFC", m_.group(2) + ACCENTS[m_.group(1)]), s)
    s = re.sub(r"\\([uvHtcdbkr])\s+([A-Za-z])", lambda m_: unicodedata.normalize("NFC", m_.group(2) + ACCENTS[m_.group(1)]), s)
    s = re.sub(r"\\(ss|ae|AE|oe|OE|o|O|l|L|aa|AA|i|j)(?![A-Za-z])", lambda m_: TEXT_SYMBOLS.get(m_.group(1), m_.group(1)), s)
    s = re.sub(r"\\[A-Za-z]+\s*", "", s)
    s = s.replace("{", "").replace("}", "").replace("~", " ")
    return re.sub(r"\s+", " ", s).strip()


def purify(s: str) -> str:
    s = detex_name(s)
    s = unicodedata.normalize("NFKD", s)
    s = "".join(c for c in s if not unicodedata.combining(c))
    s = re.sub(r"[-~]", " ", s)
    s = re.sub(r"[^A-Za-z0-9\s]", "", s)
    return s.lower()


def split_and(s: str):
    parts = []
    depth = 0
    cur = []
    i = 0
    n = len(s)
    while i < n:
        c = s[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if depth == 0 and re.match(r"\s+and\s+", s[i:], re.I) and (i == 0 or s[i] in " \t\n"):
            mm = re.match(r"\s+and\s+", s[i:], re.I)
            parts.append("".join(cur))
            cur = []
            i += mm.end()
            continue
        cur.append(c)
        i += 1
    parts.append("".join(cur))
    return [p.strip() for p in parts if p.strip()]


def split_words(s: str):
    words = []
    depth = 0
    cur = []
    for c in s:
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if c in " \t\n~" and depth == 0:
            if cur:
                words.append("".join(cur))
                cur = []
        else:
            cur.append(c)
    if cur:
        words.append("".join(cur))
    return words


def split_commas(s: str):
    parts = []
    depth = 0
    cur = []
    for c in s:
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
        if c == "," and depth == 0:
            parts.append("".join(cur).strip())
            cur = []
        else:
            cur.append(c)
    parts.append("".join(cur).strip())
    return parts


def is_von(word: str) -> bool:
    w = word.lstrip("{\\")
    w = re.sub(r"^[A-Za-z]+\s*", "", w) if word.startswith("{\\") else w
    for c in word:
        if c.isalpha():
            return c.islower()
    return False


def parse_names(field: str):
    names = []
    for raw in split_and(field):
        if raw.lower() == "others":
            names.append({"first": "", "von": "", "last": "", "jr": "", "others": True})
            continue
        parts = split_commas(raw)
        first = von = last = jr = ""
        if len(parts) >= 3:
            vl = split_words(parts[0])
            jr = parts[1]
            first = parts[2]
        elif len(parts) == 2:
            vl = split_words(parts[0])
            first = parts[1]
        else:
            words = split_words(raw)
            if len(words) == 1:
                last = words[0]
                names.append({"first": "", "von": "", "last": last, "jr": "", "others": False})
                continue
            k = 0
            while k < len(words) - 1 and not is_von(words[k]):
                k += 1
            first = " ".join(words[:k])
            rest = words[k:]
            vl = rest
        # split von/last in vl
        k = 0
        while k < len(vl) - 1 and is_von(vl[k]):
            k += 1
        von = " ".join(vl[:k])
        last = " ".join(vl[k:])
        names.append({"first": first.strip(), "von": von.strip(), "last": last.strip(), "jr": jr.strip(),
                      "others": False})
    return names


def alpha_label(names, year: str, key: str) -> str:
    real = [n for n in names if not n.get("others")]
    if not real:
        lab = purify(key)[:3].capitalize() or "Anon"
    elif len(names) == 1:
        n = real[0]
        initials = "".join(w[0] for w in split_words(detex_name(n["von"])) if w) + \
            "".join(w[0] for w in re.split(r"[\s\-]+", detex_name(n["last"])) if w)
        lab = initials if len(initials) >= 2 else detex_name(n["last"])[:3]
    else:
        take = names[:3] if len(names) > 4 else names
        lab = ""
        for n in take:
            if n.get("others"):
                lab += "+"
                continue
            lab += "".join(w[0] for w in split_words(detex_name(n["von"])) if w) + (detex_name(n["last"])[:1])
        if len(names) > 4:
            lab += "+"
    yr = re.sub(r"\D", "", year)[-2:]
    return lab + yr


# ------------------------------------------------------------ handler table

HANDLERS = {}


def _h(names, method):
    for n in names.split():
        HANDLERS[n] = method


_h("\\", Paper.h_symbol_bs)
_h("newline", Paper.h_newline)
_h("par", Paper.h_par)
for _n in FONT_ARG:
    HANDLERS[_n] = Paper.h_font_arg
_h("makebox", Paper.h_font_arg)
for _n in FONT_SWITCH:
    HANDLERS[_n] = Paper.h_font_switch
_h("parbox raisebox resizebox scalebox rotatebox adjustbox reflectbox", Paper.h_box)
_h("url doi arxiv arXiv eprint path", Paper.h_url)
_h("lstinputlisting", Paper.h_lstinputlisting)
_h("xspace", Paper.h_xspace)
_h("href", Paper.h_href)
_h("verb lstinline", Paper.h_verb)
_h("ensuremath", Paper.h_ensuremath)
_h("texorpdfstring", Paper.h_texorpdf)
_h("newcommand renewcommand providecommand DeclareRobustCommand DeclareMathOperator DeclarePairedDelimiter "
   "DeclarePairedDelimiterX DeclarePairedDelimiterXPP newenvironment renewenvironment newtheorem newtheoremstyle "
   "def gdef edef xdef let newcounter crefname Crefname crefalias numberwithin counterwithin counterwithout "
   "theoremstyle", Paper.h_skip_def)
_h("setcounter addtocounter stepcounter refstepcounter", Paper.h_counter)
_h("arabic roman Roman alph Alph fnsymbol value", Paper.h_numfmt)
_h("today", Paper.h_today)
_h("csname", Paper.h_csname)
_h("ifcsname ifdefined ifmmode iftrue iffalse ifx ifnum ifdim ifthenelse_ignored", Paper.h_if)
_h("fi else", Paper.h_ignore_fi)
_h("hspace", Paper.h_space_cmd)
_h("and", Paper.h_and)
_h("thanks", Paper.h_thanks)
_h("item", Paper.h_item_stray)
_h("qed", Paper.h_qed)
_h("tikz", Paper.h_tikz_inline)
_h("includegraphics", Paper.h_includegraphics)
_h("includepdf", Paper.h_includepdf)
_h("@nameuse", Paper.h_nameuse)
_h("input include subfile", Paper.h_input_left)
_h("appendix", Paper.h_appendix)
_h("bibliography", Paper.h_bibliography)
_h("printbibliography", Paper.h_printbib)
_h("footnote footnotemark footnotetext", Paper.h_footnote)
_h("label", Paper.h_label)
_h("hypertarget", Paper.h_hypertarget)
_h("hyperlink", Paper.h_hyperlink)
_h("hyperref", Paper.h_hyperref)
for _n in REF_CMDS:
    HANDLERS[_n] = Paper.h_ref
for _n in CITE_CMDS:
    HANDLERS[_n] = Paper.h_cite
_h("caption captionof", Paper.h_caption)
_h("part chapter section subsection subsubsection paragraph subparagraph", Paper.h_section)
_h("begin", Paper.h_begin)
_h("end", Paper.h_end)
_h("( [", Paper.h_math_paren)
del HANDLERS["thanks"]
HANDLERS["thanks"] = Paper.h_thanks
HANDLER_NAMES = set(HANDLERS)


# ------------------------------------------------------------ formula checking

def katex_js() -> str | None:
    """The KaTeX build that checks formulas: KATEX_JS if set, otherwise the copy the site
    itself serves (site/assets/vendor/katex-<version>), so the check and the page agree."""
    p = os.environ.get("KATEX_JS")
    if not p:
        own = SITE / "assets" / "vendor" / f"katex-{CFG.get('katex_version')}" / "katex.min.js"
        return str(own) if own.exists() else None
    return p if Path(p).exists() else None


def node_bin() -> str | None:
    return shutil.which("node")


def checker_version() -> str | None:
    kj, nb = katex_js(), node_bin()
    if not kj or not nb:
        return None
    try:
        r = subprocess.run([nb, str(CHECKER), "--version"], capture_output=True, text=True, timeout=60,
                           env={**os.environ, "KATEX_JS": kj})
        return json.loads(r.stdout).get("katex")
    except Exception:  # noqa: BLE001
        return None


def check_formulas(slug: str, formulas, macros, leqno=False, fleqn=False):
    """Return (checked, failures) where failures maps a distinct formula to its error."""
    kj, nb = katex_js(), node_bin()
    distinct = []
    seen = {}
    for f in formulas:
        key = (f["tex"], f["display"])
        if key not in seen:
            seen[key] = len(distinct)
            distinct.append(key)
    items = []
    for n, (tex, disp) in enumerate(distinct):
        it = {"paper": slug, "tex": tex, "display": disp}
        if n == 0:
            it["macros"] = macros
            it["leqno"] = leqno
            it["fleqn"] = fleqn
        elif leqno or fleqn:
            it["leqno"] = leqno
            it["fleqn"] = fleqn
        items.append(it)
    if not items:
        return True, {}, 0
    r = subprocess.run([nb, str(CHECKER)], input=json.dumps(items, ensure_ascii=False), capture_output=True,
                       text=True, timeout=900, env={**os.environ, "KATEX_JS": kj})
    if r.returncode != 0:
        raise RuntimeError(f"checker failed: {r.stderr.strip()[:300]}")
    res = json.loads(r.stdout)
    fails = {distinct[x["index"]]: x["error"] for x in res.get("failures", [])}
    return True, fails, len(distinct)


# ------------------------------------------------------------ one paper

def lean_pairs() -> dict:
    """(manuscript id, file, line) -> the backend's record at that statement: the Lean
    statements paired with it, with the pairing state, and the families whose catalogue
    claim names it as the candidate (build_site.paper_marks, from Statement Map's
    reader packets; nothing is scored here)."""
    import_site()
    return S.paper_marks()


def lean_evidence_html(mark: dict) -> str:
    """A margin note in words: which Lean statement is paired with this theorem, by what
    evidence, and who outside OpenAI reports re-running it. No symbol needs a key."""
    import_site()
    lid = mark["id"][2:]
    bits = [TXT["lean_runs_n"].format(n=S.say(mark["accepted"])) if mark["accepted"] > 1 else
            TXT["lean_runs_1"] if mark["accepted"] == 1 else TXT["lean_runs_0"]]
    if mark.get("holes"):
        bits.append(TXT["lean_holes_1"] if mark["holes"] == 1 else TXT["lean_holes_n"].format(n=mark["holes"]))
    link = f'<a href="../statements/{quote(lid)}.html"><code>{esc_t(lid)}</code></a>'
    how = TXT["lean_how"][mark["state"]].replace("{lean}", "\x00")
    return (f'<p class="pr-lean pr-lean--{"candidate" if mark["state"] == "candidate-pairing" else "cited"}">'
            f'<span class="pr-lean__k">{esc_t(TXT["lean_k"])}</span> '
            f'{esc_t(how).replace(chr(0), link)}<span class="pr-lean__ev">{esc_t(TXT["lean_proof"])} {esc_t("; ".join(bits))}.</span></p>')


def headline_note_html(fids: list) -> str:
    import_site()
    links = ", ".join(f'<a href="../families/{quote(f[2:])}.html">{esc_t(TXT["family_n"].format(n=f[2:]))}</a>' for f in fids)
    return (f'<p class="pr-head-note">{esc_t(TXT["headline_note"]).replace("{families}", links)}</p>')


PAPER_SECONDS = int(os.environ.get("ATLAS_PAPER_SECONDS", "1800"))

# KaTeX has neither \lhook nor \joinrel. The release builds hooked arrows only as
# \lhook\joinrel\longrightarrow and \lhook\joinrel\rightarrow, so those become KaTeX's own
# forms; never \hookrightarrow, which a paper may redefine through \lhook.
KATEX_REWRITES = [
    (re.compile(r"\\lhook\s*\\joinrel\s*\\longrightarrow(?![A-Za-z@])"), "\\xhookrightarrow{\\quad}"),
    (re.compile(r"\\lhook\s*\\joinrel\s*\\rightarrow(?![A-Za-z@])"), '\\mathrel{\\char"21AA}'),
]


def katex_compat(tex: str) -> str:
    tex = strip_assignments(tex)
    for pat, rep in KATEX_REWRITES:
        tex = pat.sub(lambda _m, r=rep: r, tex)
    return tex


class PaperTimeout(Exception):
    pass


def _paper_timeout(signum, frame):
    raise PaperTimeout(f"the conversion took longer than {PAPER_SECONDS} seconds")


def build_one(m: dict, upstream: str, check: bool, out_dir: str) -> dict:
    """build_one_paper under a time limit (ATLAS_PAPER_SECONDS, default 1800; 0 for none),
    so one paper can never stall the build: a paper over the limit is recorded as
    unavailable and keeps its PDF as the route."""
    if PAPER_SECONDS <= 0 or not hasattr(signal, "SIGALRM"):
        return build_one_paper(m, upstream, check, out_dir)
    prev = signal.signal(signal.SIGALRM, _paper_timeout)
    signal.alarm(PAPER_SECONDS)
    try:
        return build_one_paper(m, upstream, check, out_dir)
    except PaperTimeout as e:
        remove_stale(Path(out_dir), m["id"])
        return {"id": m["id"], "status": "unavailable", "page": None, "pdf_url": m.get("pdf_url"),
                "main_tex": (m.get("tex") or {}).get("main"), "reasons": [str(e)]}
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, prev)


def build_one_paper(m: dict, upstream: str, check: bool, out_dir: str) -> dict:
    """Convert, check and write one paper. Returns its acceptance row."""
    import_site()
    upstream = Path(upstream)
    out_dir = Path(out_dir)
    slug = m["id"]
    row = {"id": slug, "status": "unavailable", "page": None, "pdf_url": m.get("pdf_url"),
           "main_tex": (m.get("tex") or {}).get("main"), "reasons": []}
    try:
        p = Paper(m, upstream)
        p.convert()
    except FileNotFoundError as e:
        row["reasons"] = [f"no TeX source: {e}"]
        remove_stale(out_dir, slug)
        return row
    except Exception as e:  # noqa: BLE001  (record and move on; the PDF stays the route)
        import traceback
        row["reasons"] = [f"conversion failed: {type(e).__name__}: {e}"]
        row["trace"] = traceback.format_exc()[-1500:]
        remove_stale(out_dir, slug)
        return row
    if not p.body_html.strip():
        row["reasons"] = ["the converted body is empty"]
        remove_stale(out_dir, slug)
        return row
    total = len(p.formulas)
    fails = {}
    checked = False
    distinct = 0
    check_error = None
    if check and katex_js() and node_bin():
        try:
            checked, fails, distinct = check_formulas(slug, p.formulas, p.katex, p.leqno, p.fleqn)
        except Exception as e:  # noqa: BLE001
            checked = False
            check_error = str(e)[:300]
    failed_occ = [f for f in p.formulas if (f["tex"], f["display"]) in fails]
    examples = []
    seen_ex = set()
    for f in failed_occ:
        key = (f["tex"], f["display"])
        if key in seen_ex:
            continue
        seen_ex.add(key)
        if len(examples) < 5:
            examples.append({"tex": f["tex"][:240], "display": f["display"], "error": fails[key][:240],
                             "where": p.where(f["off"])})
    unresolved_refs = sorted(set(x[0] for x in p.unresolved_refs))
    unresolved_cites = sorted(set(x[0] for x in p.unresolved_cites))
    missing_anchors = p.statement_anchors()
    unknown_cmds = dict(p.unknown_cmds.most_common())
    unknown_envs = dict(p.unknown_envs.most_common())
    row.update({
        "formulas": {"total": total, "distinct": distinct if checked else len({(f["tex"], f["display"]) for f in p.formulas}),
                     "checked": total if checked else 0, "failed": len(failed_occ),
                     "failed_distinct": len(fails), "unchecked": 0 if checked else total, "examples": examples},
        "refs": {"total": p.ref_total, "unresolved": len(p.unresolved_refs), "labels": unresolved_refs[:10],
                 "examples": [{"label": a, "where": b} for a, b in p.unresolved_refs[:5]]},
        "cites": {"total": p.cite_total, "unresolved": len(p.unresolved_cites), "keys": unresolved_cites[:10],
                  "examples": [{"key": a, "where": b} for a, b in p.unresolved_cites[:5]]},
        "environments": {"unknown": sum(unknown_envs.values()), "names": unknown_envs,
                         "examples": {k[4:]: v for k, v in p.unknown_examples.items() if k.startswith("env:")}},
        "commands": {"unknown": sum(unknown_cmds.values()), "names": dict(list(unknown_cmds.items())[:12]),
                     "examples": {k: v for k, v in list(p.unknown_examples.items()) if not k.startswith("env:")}},
        "macros": {"defined": len(p.macros), "to_katex": len([k for k in p.katex if k[1:] in p.macros]),
                   "expanded_by_script": len(p.python_macros), "untranslated": len(p.untranslated),
                   "untranslated_examples": dict(list(p.untranslated.items())[:8]),
                   "built_ins_kept": sorted(getattr(p, "dropped_wrappers", []))},
        "figures": {"placeholders": sum(p.figures.values()), **{k: v for k, v in sorted(p.figures.items())}},
        **({"pdf_pages": {"files": list(p.included_pdfs)}} if p.included_pdfs else {}),
        "statements": {"total": len(p.m.get("statements") or []), "missing_anchor": missing_anchors[:20],
                       "missing": len(missing_anchors)},
        "labels": {"defined": len(p.labels), "duplicates": sorted(set(p.dup_labels))[:10]},
        "bibliography": {"source": "thebibliography" if p.thebib is not None else ("bibtex" if p.bibfiles else "none"),
                         "style": p.bibstyle, "entries": len(getattr(p, "bib_items", []))},
    })
    if check_error:
        row["formulas"]["check_error"] = check_error
    reasons = []
    if not checked:
        reasons.append("formulas unchecked")
    if failed_occ:
        reasons.append("formula failures")
    if p.unresolved_refs:
        reasons.append("unresolved references")
    if p.unresolved_cites:
        reasons.append("unresolved citations")
    if unknown_envs:
        reasons.append("unknown environments")
    if unknown_cmds:
        reasons.append("untranslated commands")
    if p.included_pdfs:
        reasons.append("pages included from PDF")
    if missing_anchors:
        reasons.append("statement anchors missing")
    row["reasons"] = reasons
    row["status"] = "accepted" if not reasons else "partial"
    rel = f"papers/{slug}.html"
    html_text = render_page(p, row, fails, rel)
    path = out_dir / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html_text, encoding="utf-8")
    row["page"] = rel
    row["_printed"] = p.printed_numbers()   # main() moves these to data/statement_numbers.json
    row["_labels"] = p.printed_labels()     # and these to data/paper_labels.json
    return row


def old_numbers() -> dict:
    """data/statement_numbers.json's rows by manuscript, kept for papers a partial run skips."""
    out: dict = {}
    try:
        for r in json.loads(NUMBERS.read_text(encoding="utf-8")).get("rows", []):
            out.setdefault(r["manuscript"], []).append(r)
    except (OSError, ValueError, KeyError):
        return {}
    return out


def old_labels() -> dict:
    """data/paper_labels.json's label maps by manuscript, kept for papers a partial run skips."""
    try:
        return {r["manuscript"]: r["labels"] for r in json.loads(LABELS.read_text(encoding="utf-8")).get("rows", [])}
    except (OSError, ValueError, KeyError):
        return {}


def write_labels(by_manuscript: dict):
    """data/paper_labels.json: for each paper with a reading page, what every \\label prints
    when the paper refers to it (an equation's (1.1), a theorem's 3.2), so other pages can
    resolve \\ref, \\eqref and \\cref in extracted statements to the printed number and
    link the reading page's anchor, rather than show the raw label."""
    rows = [{"manuscript": k, "labels": by_manuscript[k]} for k in sorted(by_manuscript) if by_manuscript[k]]
    head = json.dumps({
        "_note": ("Generated by scripts/build_papers.py. For each paper the atlas reads, every label with what a "
                  "reference to it prints, computed from the paper's own TeX counters by the atlas's TeX reader: "
                  "[kind, heading name or null, printed number]. The reading page's anchor for a label is the label "
                  "itself. The PDF is authoritative. Do not edit by hand."),
        "schema": "atlas-paper-labels/1",
        "upstream_commit": COMMIT,
        "anchor": "papers/<manuscript>.html#<label>",
        "rows_count": len(rows),
    }, ensure_ascii=False, indent=1)
    body = ",\n".join("  " + json.dumps(r, ensure_ascii=False, sort_keys=True) for r in rows)
    LABELS.write_text(head[:-1].rstrip() + ',\n "rows": [\n' + body + "\n ]\n}\n", encoding="utf-8")


def write_numbers(by_manuscript: dict):
    """data/statement_numbers.json: the number each statement prints on its reading
    page, one row per line, so that another tool can import it pinned and bound to
    the statement's source rather than read it from the HTML."""
    rows = sorted((r for rs in by_manuscript.values() for r in rs),
                  key=lambda r: (r["manuscript"], r["file"], r["line"]))
    head = json.dumps({
        "_note": ("Generated by scripts/build_papers.py. The number each extracted statement prints on its "
                  "reading page, computed from the paper's own TeX counters by the atlas's TeX reader. A statement "
                  "the reader did not render as a theorem-like block has no row; number is null for an unnumbered "
                  "one. The PDF is authoritative. Do not edit by hand."),
        "schema": "atlas-statement-numbers/1",
        "upstream_commit": COMMIT,
        "binding": ("manuscript, file, line and statement_sha256 identify the statement as data/manuscripts.json "
                    "records it at the same upstream commit"),
        "rows_count": len(rows),
    }, ensure_ascii=False, indent=1)
    body = ",\n".join("  " + json.dumps(r, ensure_ascii=False) for r in rows)
    NUMBERS.write_text(head[:-1].rstrip() + ',\n "rows": [\n' + body + "\n ]\n}\n", encoding="utf-8")


def remove_stale(out_dir: Path, slug: str):
    """Delete an earlier reading page for a paper that no longer has one; never a
    page this script did not write."""
    path = out_dir / "papers" / f"{slug}.html"
    try:
        if path.is_file() and PAGE_MARK in path.read_text(encoding="utf-8", errors="replace")[:4000]:
            path.unlink()
    except OSError:
        pass


# ------------------------------------------------------------ the page

def banner_items(row) -> list[str]:
    out = []
    f = row["formulas"]
    if f["unchecked"]:
        out.append(TXT["f_unchecked"])
    if f["failed"]:
        out.append(plural("f_formulas", f["failed"]))
    if row["refs"]["unresolved"]:
        out.append(plural("f_refs", row["refs"]["unresolved"]))
    if row["cites"]["unresolved"]:
        out.append(plural("f_cites", row["cites"]["unresolved"]))
    if row["environments"]["unknown"]:
        names = ", ".join(sorted(row["environments"]["names"]))
        out.append(plural("f_envs", row["environments"]["unknown"], names=names))
    if row["commands"]["unknown"]:
        names = ", ".join("\\" + k for k in list(row["commands"]["names"])[:6])
        out.append(plural("f_cmds", row["commands"]["unknown"], names=names))
    pdfs = (row.get("pdf_pages") or {}).get("files") or []
    if pdfs:
        out.append(plural("f_pdf", len(pdfs), names=", ".join(pdfs)))
    if row["statements"]["missing"]:
        out.append(plural("f_anchors", row["statements"]["missing"]))
    return out


def render_page(p: Paper, row: dict, fails: dict, rel: str) -> str:
    m = p.m
    root = "../"
    esc = S.esc
    fam = S.FAM.get(m.get("family") or "")
    if fam:
        di = S.DISC_OF.get(fam["id"])
        crumbs = []
        if di is not None:
            crumbs.append((esc(S.DISCIPLINES[di]["name"]), f"{root}index.html#o=d:{S.DISC_SLUG[di]}"))
        crumbs.append((S.fam_title_html(fam), f"{root}families/{fam['id']}.html"))
        crumbs.append((S.ms_title_html(m), None))
        trail = S.trail(root, crumbs)
    else:
        trail = S.trail(root, [(S.ms_title_html(m), None)])
    title_plain = S.tex_plain(m["title"])
    facts = []
    if p.author_html:
        facts.append(f'<span class="pr-authors">{p.author_html}</span>')
    if m.get("date"):
        facts.append(f'<span>{esc(S.date_words(m["date"]))}</span>')
    actions = [S.pdf_button(m, "btn btn--primary"),
               f'<a class="btn btn--ghost ext" href="{esc(TREE + "preprints/" + m["id"] + "/" + str(Path(row["main_tex"] or "build/main.tex").parent))}" rel="noopener">{esc(TXT["tex_source"])}</a>']
    lede = ""
    if fam:
        lede = (f'<p class="lede">{esc(site_copy("paper.in_result", "Part of result {id}: {title}.", id=fam["id"], title=S.tex_plain(fam["title"])))} '
                f'<a href="{root}families/{fam["id"]}.html#{esc(m["id"])}">{esc(site_copy("paper.read_in_result", "Read it with its result"))}</a></p>')
    notes = ""
    if m.get("version_note"):
        notes += (f'<div class="note"><p class="note__h">{esc(site_copy("family.version_note", "Version note"))}</p>'
                  f'<div class="md-math">{S.md_paragraphs(m["version_note"])}</div></div>')
    figs = row["figures"]["placeholders"]
    if row["status"] == "accepted":
        lines = [TXT["converted"].format(commit=COMMIT[:7]), TXT["numbering"]]
        if figs:
            lines.append(TXT["figures_one"] if figs == 1 else TXT["figures_many"].format(n=figs))
        status = f'<div class="pr-status" role="note"><p>{" ".join(esc(x) for x in lines)}</p></div>'
    else:
        items = banner_items(row)
        if figs:
            items.append(TXT["figures_one"] if figs == 1 else TXT["figures_many"].format(n=figs))
        lis = "".join(f"<li>{esc(x)}</li>" for x in items)
        status = (f'<div class="pr-banner" role="note" aria-labelledby="pr-banner-h">'
                  f'<p class="pr-banner__h" id="pr-banner-h">{esc(TXT["partial_h"])}</p>'
                  f'<p>{esc(TXT["partial_p"])} <a class="ext" href="{esc(m["pdf_url"])}" rel="noopener">{esc(TXT["pdf_link"])}</a></p>'
                  f'<ul>{lis}</ul><p>{esc(TXT["numbering"])}</p></div>')
    abstract = ""
    if p.abstract_html:
        abstract = (f'<section class="pr-abstract" aria-labelledby="pr-abstract-h"><h2 class="pr-sec pr-sec--1" '
                    f'id="pr-abstract-h">{esc(site_copy("paper.abstract", TXT["abstract"]))}</h2>{p.abstract_html}</section>')
    toc = ""
    if p.toc_html:
        toc = (f'<nav class="pr-toc" aria-label="{esc(TXT["contents"])}"><details><summary>{esc(TXT["contents"])}</summary>'
               f'{p.toc_html}</details></nav>')
    notes_html = ""
    if p.footnotes:
        lis = "".join(f'<li id="{esc(p.ids.get(fn["ctx"]["i"], ""))}" class="pr-fn"><span class="pr-fn-n">{esc(fn["num"])}</span>'
                      f'<div class="pr-fn-body">{fn["html"]}</div><a class="pr-fn-back" href="#pr-fnref-{fn["idx"]}" '
                      f'aria-label="{esc(TXT["back"])}">↑</a></li>' for fn in p.footnotes)
        notes_html = (f'<section class="pr-notes" aria-labelledby="pr-notes-h"><h2 class="pr-sec pr-sec--1" id="pr-notes-h">'
                      f'{esc(TXT["notes"])}</h2><ol class="pr-fn-list">{lis}</ol></section>')
    body_html = p.body_html
    if fails:
        failed_idx = {i for i, f in enumerate(p.formulas) if (f["tex"], f["display"]) in fails}

        def mark(mm):
            if int(mm.group(2)) in failed_idx:
                return mm.group(1).replace('class="pr-m"', 'class="pr-m pr-m--fail"')
            return mm.group(1)
        body_html = re.sub(r'(<span class="pr-m"(?: data-d="1")? data-f="(\d+)">)', mark, body_html)
    macros_json = json.dumps(p.katex, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    attrs = ' data-leqno="1"' if p.leqno else ""
    attrs += ' data-fleqn="1"' if p.fleqn else ""
    body = f"""<div class="frame page pr-page">
{trail}
<header class="phead pr-head">
 <p class="phead__kicker">{esc(TXT['kicker'])}</p>
 <h1 class="phead__title">{S.ms_title_html(m)}</h1>
 <p class="phead__facts pr-facts">{', '.join(facts)}</p>
 <p class="actions">{''.join(actions)}</p>
</header>
{lede}
{notes}
{status}
{abstract}
{toc}
<article class="paper" id="pr-paper" lang="en" data-paper="{esc(m['id'])}" data-math-failed="{esc(TXT['math_failed'])}"{attrs}>
{body_html}
</article>
{notes_html}
</div>
<script type="application/json" id="pr-macros">{macros_json}</script>"""
    desc = S.tex_plain(m.get("abstract") or "") or TXT["description"].format(title=title_plain)
    extra = (f'{PAGE_MARK}\n<link rel="stylesheet" href="{root}assets/paper.css">\n'
             f'<script defer src="{root}assets/paper.js"></script>')
    return S.page(rel, title_plain, desc, body, extra_head=extra, page_type="article", main_class="pr-main")


# ------------------------------------------------------------ main

def load_manuscripts():
    ms = json.loads((DATA / "manuscripts.json").read_text(encoding="utf-8"))
    return sorted([m for m in ms if m.get("status") == "current"], key=lambda m: m["id"])


def worker_init():
    import_site()


def summarise(rows) -> dict:
    c = Counter(r["status"] for r in rows)
    reasons = Counter()
    for r in rows:
        for x in r.get("reasons") or []:
            key = x.split(":")[0] if r["status"] == "unavailable" else x
            reasons[key] += 1
    f_total = sum((r.get("formulas") or {}).get("total", 0) for r in rows)
    f_checked = sum((r.get("formulas") or {}).get("checked", 0) for r in rows)
    f_failed = sum((r.get("formulas") or {}).get("failed", 0) for r in rows)
    f_distinct = sum((r.get("formulas") or {}).get("distinct", 0) for r in rows)
    f_failed_distinct = sum((r.get("formulas") or {}).get("failed_distinct", 0) for r in rows)
    figs = sum((r.get("figures") or {}).get("placeholders", 0) for r in rows)
    return {
        "papers": len(rows), "accepted": c.get("accepted", 0), "partial": c.get("partial", 0),
        "unavailable": c.get("unavailable", 0),
        "formulas": {"total": f_total, "checked": f_checked, "failed": f_failed, "distinct": f_distinct,
                     "failed_distinct": f_failed_distinct},
        "figure_placeholders": figs,
        "reasons": dict(reasons.most_common()),
    }


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--only", nargs="+", metavar="SLUG", help="build these manuscripts only")
    ap.add_argument("--limit", type=int, help="build the first N current manuscripts only")
    ap.add_argument("--no-math-check", action="store_true", help="skip the KaTeX check (every page stays partial)")
    ap.add_argument("--jobs", type=int, default=max(1, (os.cpu_count() or 2) - 2), help="parallel workers")
    ap.add_argument("--upstream", default=str((ROOT / CFG.get("upstream_checkout", "../openai-math-upstream")).resolve()),
                    help="the pinned openai/math checkout")
    ap.add_argument("--out", default=str(OUT), help="site build directory (default site/_build)")
    args = ap.parse_args()
    t0 = time.time()
    import_site()
    ms = load_manuscripts()
    if args.only:
        want = set(args.only)
        unknown = want - {m["id"] for m in ms}
        if unknown:
            raise SystemExit(f"not current manuscripts: {sorted(unknown)}")
        ms = [m for m in ms if m["id"] in want]
    if args.limit:
        ms = ms[:args.limit]
    check = not args.no_math_check
    version = checker_version() if check else None
    if check and not version:
        why = "node is not installed" if not node_bin() else "KATEX_JS is not set or does not exist"
        print(f"formula check unavailable ({why}); every formula is recorded as unchecked", file=sys.stderr)
    out_dir = Path(args.out)
    (out_dir / "papers").mkdir(parents=True, exist_ok=True)
    (out_dir / "assets").mkdir(parents=True, exist_ok=True)
    for name in OWN_ASSETS:
        if (ASSETS / name).exists():
            shutil.copy(ASSETS / name, out_dir / "assets" / name)
    rows = []
    do_check = check and bool(version)
    if args.jobs <= 1 or len(ms) <= 1:
        for m in ms:
            rows.append(build_one(m, args.upstream, do_check, str(out_dir)))
            print(f"{rows[-1]['status']:12} {m['id']}", file=sys.stderr)
    else:
        with ProcessPoolExecutor(max_workers=args.jobs, initializer=worker_init) as ex:
            futs = {ex.submit(build_one, m, args.upstream, do_check, str(out_dir)): m for m in ms}
            done = 0
            for fut in as_completed(futs):
                m = futs[fut]
                try:
                    r = fut.result()
                except Exception as e:  # noqa: BLE001
                    r = {"id": m["id"], "status": "unavailable", "page": None, "pdf_url": m.get("pdf_url"),
                         "reasons": [f"build failed: {type(e).__name__}: {e}"]}
                rows.append(r)
                done += 1
                if done % 50 == 0 or done == len(ms):
                    print(f"{done}/{len(ms)} papers", file=sys.stderr)
    # merge into the acceptance file, keeping rows for papers not rebuilt this run
    old = {}
    if ACCEPTANCE.exists() and (args.only or args.limit):
        try:
            old = {r["id"]: r for r in json.loads(ACCEPTANCE.read_text(encoding="utf-8")).get("papers", [])}
        except (ValueError, KeyError):
            old = {}
    current_ids = {m["id"] for m in load_manuscripts()}
    merged = {k: v for k, v in old.items() if k in current_ids}
    numbers = {k: v for k, v in (old_numbers() if (args.only or args.limit) else {}).items() if k in current_ids}
    labels = {k: v for k, v in (old_labels() if (args.only or args.limit) else {}).items() if k in current_ids}
    for r in rows:
        numbers.pop(r["id"], None)
        labels.pop(r["id"], None)
        printed = r.pop("_printed", None)
        if printed:
            numbers[r["id"]] = printed
        lab = r.pop("_labels", None)
        if lab and r.get("status") in ("accepted", "partial"):
            labels[r["id"]] = lab
        r.pop("trace", None) if r.get("status") != "unavailable" else None
        r["checker"] = version if do_check else None
        merged[r["id"]] = r
    all_rows = [merged[k] for k in sorted(merged)]
    doc = {
        "_note": ("Generated by scripts/build_papers.py. One row per current manuscript: whether the atlas shows "
                  "an HTML reading view of it, and the counts behind that status. Do not edit by hand."),
        "upstream_commit": COMMIT,
        "checker": ({"name": "KaTeX", "version": version, "site_version": CFG.get("katex_version"),
                     "options": KATEX_OPTIONS, "script": "scripts/check_paper_math.mjs",
                     "note": ("The check runs the KaTeX version the site loads."
                              if version == CFG.get("katex_version") else
                              "The check runs a local KaTeX whose version differs from the one the site loads.")}
                    if do_check else {"name": None, "status": "unchecked",
                                      "reason": "run without --no-math-check, with node and KATEX_JS available"}),
        "gate": {
            "accepted": ("every formula checked and typeset; every cross-reference and citation resolved; every "
                         "environment and command understood; every extracted statement anchored. Figures may be "
                         "placeholders."),
            "partial": "a page is written with a banner listing what failed and linking the PDF",
            "unavailable": "no page; the PDF is the only route",
            "statement_anchor": ("papers/<slug>.html#<label> for a labelled statement; every theorem-like block also "
                                 "carries the id L-<file>-<line>, the location of its \\begin in data/manuscripts.json"),
        },
        "summary": summarise(all_rows),
        "papers": all_rows,
    }
    ACCEPTANCE.write_text(json.dumps(doc, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")
    write_numbers(numbers)
    write_labels(labels)
    s = summarise(rows)
    print(json.dumps({"built": len(rows), "accepted": s["accepted"], "partial": s["partial"],
                      "unavailable": s["unavailable"], "formulas": s["formulas"],
                      "figure_placeholders": s["figure_placeholders"],
                      "top_reasons": list(s["reasons"].items())[:8],
                      "checker": version if do_check else "unchecked",
                      "seconds": round(time.time() - t0, 1)}, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
