#!/usr/bin/env python3
"""Lean challenge files as evidence pages.

Everything that turns a Comparator challenge file into HTML lives here:

* a Lean 4 tokenizer (nested comments, Lean's identifier characters, dotted names);
* a reading of the file's commands: namespaces, sections, `open` and `variable`
  lines, declarations, structure fields, constructors and local notation;
* name resolution that follows Lean's own order (the current namespace and its
  parents first, then the root, open namespaces and exports), checked against
  data/lean_xref.json, which scripts/build_lean_xref.py writes from the pinned
  sources. A name with no candidate in that file, or with more than one, stays
  plain: nothing is linked to a guess;
* the "What you must check" panel: the declarations the checked theorem rests on,
  in dependency order, from a textual reference graph;
* the whole file, highlighted, with every resolved identifier linked.

build_site.py calls `lines_html` (highlighted lines without links, for snippets
and cards) and `file_section` (the file and the panel on statements/<id>.html).
Every visible string comes from site/copy_lean.json. Standard library only.

Ported from Will Cook's Plectis site (ai_workflow at commit 4b1ebab611):
* tools/meta/dissemination/maths_site_assets/maths.js, "Problem-local import map":
  the list is the object (a filterable list with a shown count, an empty state
  with a button that clears the filter, and relations that expand under the
  selected row), and controls that stay hidden until the script runs;
* tools/meta/dissemination/build_plectis_maths_site.py, `source_map_html`: the
  same list's markup, where every row keeps a working link without scripts;
* tools/meta/dissemination/maths_site_assets/maths.js, deep links that open the
  folded section holding their target.
"""
from __future__ import annotations

import bisect
import json
import re
from pathlib import Path
from urllib.parse import quote

ROOT = Path(__file__).resolve().parent.parent
COPY_PATH = ROOT / "site" / "copy_lean.json"
XREF_PATH = ROOT / "data" / "lean_xref.json"
MATHLIB_FIND = "https://leanprover-community.github.io/mathlib4_docs/find/?pattern={name}#doc"
GITHUB_BLOB = "https://github.com/openai/math/blob/{commit}/lean/{path}#L{line}"

# ------------------------------------------------------------------ tokenizer

# Lean 4's identifier characters (Lean.isLetterLike, isSubScriptAlnum, isIdFirst
# and isIdRest in Lean's Init/Meta.lean): ASCII letters and underscore, Greek
# except lambda, Pi and Sigma, Coptic, polytonic Greek, the letterlike block and
# the mathematical alphanumerics; later characters add digits, ', ! and ?, and
# subscript digits and letters.
_IDF = ("A-Za-z_α-κμ-ωΑ-ΟΡ΢Τ-Ω"
        "ϊ-ϻἀ-῾℀-⅏\U0001d49c-\U0001d59f")
_IDR = _IDF + "0-9'!?₀-₉ₐ-ₜᵢ-ᵪⱼ"
_COMP = f"(?:[{_IDF}][{_IDR}]*|«[^»\\n]*»)"
IDENT_RE = re.compile(f"{_COMP}(?:\\.{_COMP})*")
_COMP_RE = re.compile(_COMP)

_TOKEN = re.compile(
    r"(?P<ws>[ \t\r\n]+)"
    r"|(?P<lc>--[^\n]*)"
    r"|(?P<bc>/-)"
    r'|(?P<str>"(?:\\.|[^"\\])*")'
    r"|(?P<chr>'(?:\\(?:x[0-9a-fA-F]{2}|u\{[0-9a-fA-F]+\}|[^\n])|[^'\\\n])')"
    r"|(?P<num>0[xX][0-9a-fA-F_]+|0[bB][01_]+|0[oO][0-7_]+|[0-9][0-9_]*(?:\.[0-9]+)?(?:[eE][+-]?[0-9]+)?)"
    f"|(?P<id>{_COMP}(?:\\.{_COMP})*)"
    r"|(?P<attr>@\[)"
    r"|(?P<op>:=|=>|<;>|\.\.\.?|::|<\||\|>\.?|\|\||&&|->|<-|//)"
    r"|(?P<sym>.)",
    re.S,
)
_BC = re.compile(r"/-|-/")
_STR = re.compile(r'"(?:\\.|[^"\\])*"', re.S)
_INT = re.compile(r"[0-9][0-9_]*")

COMMENT = frozenset(("lc", "bc", "doc", "mdoc"))
SKIP = frozenset(("ws", "lc", "bc", "doc", "mdoc"))


def _block_end(text: str, pos: int) -> int:
    """End of the (nested) block comment that opens at pos."""
    depth = 0
    i = pos
    while True:
        m = _BC.search(text, i)
        if not m:
            return len(text)
        depth += 1 if m.group() == "/-" else -1
        i = m.end()
        if depth == 0:
            return i


def _attr_end(text: str, pos: int) -> int:
    """End of the attribute list `@[ ... ]` that opens at pos (brackets nest)."""
    depth = 0
    i = pos + 1
    n = len(text)
    while i < n:
        c = text[i]
        if c == "[":
            depth += 1
        elif c == "]":
            depth -= 1
            if depth == 0:
                return i + 1
        elif c == '"':
            m = _STR.match(text, i)
            if m:
                i = m.end()
                continue
        elif c == "/" and text.startswith("/-", i):
            i = _block_end(text, i)
            continue
        i += 1
    return n


def lex(text: str):
    """Tokens as (kind, start, end), covering the text exactly. Kinds: ws, lc, bc,
    doc (/-- -/), mdoc (/-! -/), str, chr, num, id, kw, attr, op, sym."""
    toks = []
    append = toks.append
    pos, n = 0, len(text)
    match = _TOKEN.match
    while pos < n:
        m = match(text, pos)
        k = m.lastgroup
        if k == "bc":
            end = _block_end(text, pos)
            kind = "doc" if text.startswith("/--", pos) and not text.startswith("/--/", pos) else (
                "mdoc" if text.startswith("/-!", pos) else "bc")
            append((kind, pos, end))
            pos = end
            continue
        if k == "attr":
            end = _attr_end(text, pos)
            append(("attr", pos, end))
            pos = end
            continue
        end = m.end()
        if k == "num" and pos and text[pos - 1] == "." and "." in text[pos:end]:
            end = _INT.match(text, pos).end()     # h.1.2 is two field indices, not 1.2
        elif k == "id":
            w = text[pos:end]
            if w in KEYWORDS and not (pos and text[pos - 1] == "."):
                k = "kw"
            elif w in ("_", "__"):
                k = "sym"                          # a hole, not a name
            elif len(w) == 2 and (w[0] in NOTATION_IDS and w[1] == "_" or w[0] == "_" and w[1] in NOTATION_IDS):
                k = "notn"
            elif w in NOTATION_IDS:
                k = "notn"                         # ℕ ℤ ℚ ℝ ℂ: notation for Nat, Int, Rat, Real, Complex
        append((k, pos, end))
        pos = end
    return toks


# ------------------------------------------------------------------ vocabulary

DECL_KW = frozenset("def theorem lemma abbrev instance structure class inductive axiom opaque example "
                    "irreducible_def coinductive".split())
MODIFIERS = frozenset("private protected noncomputable partial unsafe nonrec public meta scoped local".split())
NOTATION_KW = frozenset("notation infix infixl infixr prefix postfix".split())
MACRO_KW = frozenset("macro macro_rules syntax elab elab_rules declare_syntax_cat run_cmd".split())
KEYWORDS = DECL_KW | MODIFIERS | NOTATION_KW | MACRO_KW | frozenset(
    "where extends namespace section end open export variable universe mutual deriving set_option attribute "
    "import alias termination_by decreasing_by fun let have show from by if then else match with do "
    "return for in at calc suffices obtain Type Sort Prop this haveI letI hiding renaming using only "
    "generalizing unless mut try catch finally nat_lit omit include".split())
NOTATION_IDS = frozenset("ℕ ℤ ℚ ℝ ℂ".split())
# A letter written straight after one of these is part of a notation such as
# →L[ℂ] (continuous linear maps), ≃o or ℕ∞ω, never a name of its own.
NOTATION_LEAD = frozenset("→≃↪↠⟶∞⇑⥤⋙∘#")
BINDER_SYMS = frozenset("∀ ∃ Π Σ ∑ ∏ ⋃ ⋂ ⨆ ⨅ ∫ ∮ ⨁ ⨂ ∐ ⨍ ∯ λ".split())
BINDER_DECOR = frozenset("! ' ᶠ ᵐ ⁻ ᵖ ˢ".split())
OPEN_BR = {"(": ")", "[": "]", "{": "}", "⦃": "⦄", "⟨": "⟩", "⟦": "⟧", "⁅": "⁆"}
CLOSE_BR = frozenset(OPEN_BR.values())
# Tactics, recognised only where a tactic can start: after `by`, `;`, `<;>` or
# `·`, or first on a line once a `by` block has begun. Elsewhere the same words
# (rfl, trivial, id) are ordinary terms and are resolved like any other name.
TACTICS = frozenset("""
exact exacts apply refine refine' intro intros rintro rintros obtain rcases cases cases' induction induction'
constructor use exists existsi left right rfl trivial assumption contradiction exfalso decide native_decide
simp simp_all simpa simp_rw dsimp simp? norm_num norm_num1 ring ring_nf ring1 field_simp linarith nlinarith
positivity polyrith linear_combination omega aesop tauto gcongr bound fun_prop measurability continuity
infer_instance exact_mod_cast push_cast norm_cast assumption_mod_cast unfold delta change congr congr! ext
funext split split_ifs by_cases by_contra by_contra! push_neg specialize subst classical rw rwa erw rw?
nth_rewrite nth_rw conv convert apply_fun first repeat repeat' all_goals any_goals try iterate on_goal swap
rotate_left rotate_right pick_goal case case' next nofun nomatch done skip stop clear rename_i revert
generalize set lift choose peel filter_upwards interval_cases fin_cases mono apply_rules solve_by_elim abel
group noncomm_ring zify qify rify grind exact? apply? decreasing_tactic decreasing_trivial simp_wf
with_reducible constructorm casesm tfae_have tfae_finish wlog symm trans calc show refine_lift sorry admit
haveI letI exact_fun_prop module aesop_cat simp_intro subst_vars injection injections push conv_lhs conv_rhs
enter arg lhs rhs norm_num! simp_arith omega_nat
""".split())
TACTIC_BINDERS = frozenset("""
intro intros rintro rintros obtain rcases cases' induction' ext funext by_contra by_contra! by_cases choose
lift set generalize peel filter_upwards rename_i next case case' with
""".split())


# ------------------------------------------------------------------ analysis

class Decl:
    """One command of the file that declares something: a definition, theorem,
    structure, inductive type, instance, axiom, notation or macro."""
    __slots__ = ("idx", "cmd", "kind", "name", "full", "line", "kw_tok", "name_tok", "first", "last",
                 "body", "ns", "mods", "is_local_notation", "atoms", "atom_ids", "fields", "ctors",
                 "binders", "end_line", "doc", "mutual")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


class Command:
    __slots__ = ("idx", "kind", "first", "last", "line", "end_line", "head", "ns", "opens", "vars",
                 "notations", "decl", "binders", "mutual", "term_opens")

    def __init__(self, **kw):
        for k in self.__slots__:
            setattr(self, k, kw.get(k))


class OpenDecl:
    """An `open` line: every namespace candidate it names, with its explicit,
    hidden or renamed names."""
    __slots__ = ("spaces", "only", "hiding", "renames")

    def __init__(self, spaces, only=None, hiding=None, renames=None):
        self.spaces = spaces          # candidate full namespaces, innermost first
        self.only = only              # explicit names, or None for all
        self.hiding = hiding or set()
        self.renames = renames or {}  # new short name -> original short name

    def candidates(self, parts):
        """Full names this open makes `parts` refer to."""
        head, rest = parts[0], parts[1:]
        out = []
        if self.renames:
            if len(parts) == 1 and head in self.renames:
                out += [s + "." + self.renames[head] for s in self.spaces]
            return out
        if self.only is not None:
            if head in self.only:
                out += [s + "." + ".".join(parts) for s in self.spaces]
            return out
        if head in self.hiding and len(parts) == 1:
            return out
        return [s + "." + ".".join(parts) for s in self.spaces]


def split_name(name: str):
    """Components of a dotted name, keeping «guillemet» parts whole."""
    if "«" not in name:
        return name.split(".") if name else []
    parts = []
    pos = 0
    while pos < len(name):
        m = _COMP_RE.match(name, pos)
        if not m:
            break
        parts.append(m.group())
        pos = m.end() + 1
    return parts


class LeanFile:
    """A challenge file read into commands, declarations, scopes and token roles."""

    def __init__(self, text: str):
        self.text = text
        toks = lex(text)
        self.kind = [t[0] for t in toks]
        self.start = [t[1] for t in toks]
        self.end = [t[2] for t in toks]
        self.nl = [m.start() for m in re.finditer("\n", text)]
        self.line = [bisect.bisect_right(self.nl, s) + 1 for s in self.start]
        self.sig = [i for i, k in enumerate(self.kind) if k not in SKIP]
        self.sig_pos = {j: p for p, j in enumerate(self.sig)}
        self.n_lines = len(self.nl) + (0 if text.endswith("\n") else 1)
        self.role = {}          # token index -> role letter (see _roles)
        self.decls: list[Decl] = []
        self.commands: list[Command] = []
        self.local_names = {}   # full name -> (decl idx, line, kind, protected)
        self.aliases = {}       # alias full name -> list of target candidates
        self._commands()
        self._scopes()
        for c in self.commands:
            self._roles(c)

    # -- small helpers
    def tx(self, i):
        return self.text[self.start[i]:self.end[i]]

    def col(self, i):
        s = self.start[i]
        p = bisect.bisect_left(self.nl, s)
        return s - (self.nl[p - 1] + 1 if p else 0)

    def line_text(self, ln):
        a = self.nl[ln - 2] + 1 if ln > 1 else 0
        b = self.nl[ln - 1] if ln - 1 < len(self.nl) else len(self.text)
        return self.text[a:b]

    # -- commands
    def _commands(self):
        """Split the file into commands. A line starts a command when its first
        token (after attributes and modifiers) is a command keyword. `open` and
        `set_option` also exist inside terms and proofs, so they start a command
        only at or left of the indentation of the declaration they follow."""
        kind, sig, line = self.kind, self.sig, self.line
        firsts = []
        seen = set()
        for j in sig:
            ln = line[j]
            if ln not in seen:
                seen.add(ln)
                firsts.append(j)
        cmd_starts = []      # (first token, head token, command kind)
        decl_indent = None
        pending = None       # first token of attribute/modifier-only lines above
        for j in firsts:
            ln = line[j]
            p = self.sig_pos[j]
            k = p
            while k < len(sig) and line[sig[k]] == ln and (kind[sig[k]] == "attr" or (kind[sig[k]] == "kw" and self.tx(sig[k]) in MODIFIERS)):
                k += 1
            if k >= len(sig) or line[sig[k]] != ln:
                if pending is None:
                    pending = j          # attributes or modifiers alone on a line
                continue
            h = sig[k]
            word = self.tx(h) if kind[h] in ("kw", "id") else ""
            col = self.col(j)
            ck = None
            if kind[h] == "kw":
                if word in DECL_KW:
                    ck = "decl"
                elif word in NOTATION_KW:
                    ck = "notation"
                elif word in MACRO_KW:
                    ck = "macro"
                elif word in ("namespace", "section", "end", "mutual", "variable", "universe", "export",
                              "attribute", "alias", "import", "omit", "include"):
                    ck = word
                elif word == "deriving" and k + 1 < len(sig) and self.tx(sig[k + 1]) == "instance":
                    ck = "deriving"
                elif word in ("open", "set_option"):
                    if decl_indent is None or col <= decl_indent:
                        ck = word
            elif kind[h] == "sym" and self.tx(h) == "#" and k + 1 < len(sig) and line[sig[k + 1]] == ln:
                if decl_indent is None or col <= decl_indent:
                    ck = "hash"
            if ck is None:
                pending = None
                continue
            start = pending if pending is not None else j
            pending = None
            cmd_starts.append((start, h, ck))
            decl_indent = col if ck in ("decl", "notation", "macro", "alias") else None
        for n_, (start, h, ck) in enumerate(cmd_starts):
            nxt = cmd_starts[n_ + 1][0] if n_ + 1 < len(cmd_starts) else len(self.kind)
            # last significant token before the next command
            p = bisect.bisect_left(sig, nxt) - 1
            last = sig[p] if p >= 0 else start
            if last < start:
                last = start
            self.commands.append(Command(idx=n_, kind=ck, first=start, last=last, head=h,
                                         line=line[h], end_line=line[last]))

    def _cmd_sig(self, c):
        a = bisect.bisect_left(self.sig, c.first)
        b = bisect.bisect_right(self.sig, c.last)
        return self.sig[a:b]

    # -- scopes: namespaces, sections, opens, variables, notation
    def _scopes(self):
        stack = [{"kind": "file", "ns": [], "opens": [], "vars": set(), "notations": [], "mutual": None}]
        pending_in = None     # (opens, vars) from `open ... in` / `variable ... in`
        for c in self.commands:
            toks = self._cmd_sig(c)
            words = [self.tx(t) for t in toks]
            hk = toks.index(c.head) if c.head in toks else 0
            ns = [p for s in stack for p in s["ns"]]
            opens = [o for s in stack for o in s["opens"]]
            vars_ = set().union(*(s["vars"] for s in stack))
            notes = [nt for s in stack for nt in s["notations"]]
            mutual = next((s["mutual"] for s in reversed(stack) if s["mutual"] is not None), None)
            ends_in = bool(words) and words[-1] == "in" and self.kind[toks[-1]] == "kw"
            if pending_in is not None:
                opens = opens + pending_in[0]
                vars_ = vars_ | pending_in[1]
            c.ns, c.opens, c.vars, c.notations, c.mutual = tuple(ns), opens, vars_, notes, mutual
            if not ends_in:
                pending_in = None
            if c.kind == "namespace":
                name = words[hk + 1] if hk + 1 < len(words) else ""
                for part in split_name(name):
                    stack.append({"kind": "ns", "ns": [part], "opens": [], "vars": set(), "notations": [], "mutual": None})
            elif c.kind == "section":
                stack.append({"kind": "sec", "ns": [], "opens": [], "vars": set(), "notations": [], "mutual": None})
            elif c.kind == "mutual":
                stack.append({"kind": "mutual", "ns": [], "opens": [], "vars": set(), "notations": [], "mutual": c.idx})
            elif c.kind == "end":
                name = words[hk + 1] if hk + 1 < len(words) and self.line[toks[hk + 1]] == c.line and self.kind[toks[hk + 1]] == "id" else ""
                k = max(1, len(split_name(name))) if name else 1
                for _ in range(k):
                    if len(stack) > 1:
                        stack.pop()
            elif c.kind == "open":
                od = self._parse_open(toks, hk, ns)
                if ends_in:
                    pending_in = ((pending_in[0] if pending_in else []) + od, pending_in[1] if pending_in else set())
                else:
                    stack[-1]["opens"].extend(od)
            elif c.kind == "variable":
                names = self._binder_groups(toks[hk + 1:], mark=True)
                if ends_in:
                    pending_in = (pending_in[0] if pending_in else [], (pending_in[1] if pending_in else set()) | names)
                else:
                    stack[-1]["vars"] |= names
            elif c.kind in ("set_option", "omit", "include") and ends_in:
                pending_in = pending_in or ([], set())
            elif c.kind == "export":
                self._parse_export(toks, hk, ns)
            elif c.kind == "notation":
                self._declare(c, toks, hk, ns, stack)
            elif c.kind in ("decl", "macro", "alias", "deriving"):
                self._declare(c, toks, hk, ns, stack)
            if c.kind in ("open", "set_option", "variable") and ends_in:
                continue

    def _parse_open(self, toks, hk, ns):
        """OpenDecls of one `open` command (none for `open scoped`)."""
        out = []
        i = hk + 1
        words = [self.tx(t) for t in toks]
        if i < len(toks) and words[i] in ("scoped", "private"):
            for t, w in zip(toks[i:], words[i:]):
                if w == "in" and self.kind[t] == "kw":
                    break
                self.role[t] = "n"
            return out
        cur = None
        while i < len(toks):
            t = toks[i]
            w = words[i]
            if self.kind[t] == "kw" and w == "in":
                break
            if self.kind[t] == "id":
                self.role[t] = "n"
                rel = w[len("_root_."):] if w.startswith("_root_.") else w
                spaces = [rel] if w.startswith("_root_.") else [".".join(ns[:k] + [rel]) for k in range(len(ns), -1, -1)]
                cur = OpenDecl(spaces)
                out.append(cur)
                i += 1
                continue
            if w == "(" and cur is not None:
                names = set()
                i += 1
                while i < len(toks) and words[i] != ")":
                    if self.kind[toks[i]] == "id":
                        names.add(words[i])
                        self.role[toks[i]] = "e"       # explicit name: resolved under the namespace
                    i += 1
                cur.only = names
                i += 1
                continue
            if w == "hiding" and cur is not None:
                i += 1
                while i < len(toks) and self.kind[toks[i]] == "id":
                    cur.hiding.add(words[i])
                    self.role[toks[i]] = "n"
                    i += 1
                continue
            if w == "renaming" and cur is not None:
                i += 1
                while i + 2 < len(toks) and self.kind[toks[i]] == "id" and words[i + 1] in ("→", "->"):
                    cur.renames[words[i + 2]] = words[i]
                    self.role[toks[i]] = "n"
                    self.role[toks[i + 2]] = "n"
                    i += 3
                    if i < len(toks) and words[i] == ",":
                        i += 1
                continue
            i += 1
        return out

    def _parse_export(self, toks, hk, ns):
        words = [self.tx(t) for t in toks]
        i = hk + 1
        if i >= len(toks) or self.kind[toks[i]] != "id":
            return
        target = words[i]
        self.role[toks[i]] = "n"
        rel = target[len("_root_."):] if target.startswith("_root_.") else target
        spaces = [rel] if target.startswith("_root_.") else [".".join(ns[:k] + [rel]) for k in range(len(ns), -1, -1)]
        i += 1
        if i < len(toks) and words[i] == "(":
            i += 1
            while i < len(toks) and words[i] != ")":
                if self.kind[toks[i]] == "id":
                    alias = ".".join(ns + [words[i]])
                    self.aliases.setdefault(alias, []).extend(s + "." + words[i] for s in spaces)
                    self.role[toks[i]] = "e"
                i += 1

    def _group_end(self, toks, i):
        """Index in toks of the bracket that closes toks[i]."""
        depth = 0
        for k in range(i, len(toks)):
            w = self.tx(toks[k])
            if w in OPEN_BR and self.kind[toks[k]] == "sym":
                depth += 1
            elif w in CLOSE_BR and self.kind[toks[k]] == "sym":
                depth -= 1
                if depth == 0:
                    return k
        return len(toks) - 1

    def _binder_groups(self, toks, mark=True, stop=None):
        """Names bound by bracketed binder groups at the head of toks, e.g.
        `(x y : T) {z} [inst : C]`. Stops at the first token outside a group."""
        names = set()
        i = 0
        while i < len(toks):
            t = toks[i]
            w = self.tx(t)
            if stop and w in stop:
                break
            if self.kind[t] == "sym" and w in ("(", "{", "[", "⦃", "⟨"):
                e = self._group_end(toks, i)
                inner = toks[i + 1:e]
                names |= self._group_names(inner, w, mark)
                i = e + 1
                continue
            break
        return names

    def _group_names(self, inner, opener, mark=True):
        """Binder names inside one bracket group: the identifiers before its first
        top-level colon; a group without a colon binds its names when it is a
        ( ), { }, ⦃ ⦄ or ⟨ ⟩ group, and none when it is an instance [ ] group."""
        names = set()
        depth = 0
        colon = None
        for k, t in enumerate(inner):
            w = self.tx(t)
            if self.kind[t] in ("sym", "op"):
                if w in OPEN_BR:
                    depth += 1
                elif w in CLOSE_BR:
                    depth -= 1
                elif depth == 0 and w == ":=":
                    return names          # (priority := 100), (x := v): not binders
                elif depth == 0 and w == ":":
                    colon = k
                    break
        head = inner[:colon] if colon is not None else (inner if opener in ("(", "{", "⦃", "⟨") else [])
        for t in head:
            if self.kind[t] == "id" and "." not in self.tx(t):
                names.add(self.tx(t))
                if mark:
                    self.role[t] = "b"
            elif self.kind[t] == "sym" and self.tx(t) in ("⟨", "("):
                pass
        return names

    # -- declarations
    def _declare(self, c, toks, hk, ns, stack):
        words = [self.tx(t) for t in toks]
        mods = {w for t, w in zip(toks[:hk], words[:hk]) if self.kind[t] == "kw" and w in MODIFIERS}
        d = Decl(idx=len(self.decls), cmd=c.idx, kind=words[hk], kw_tok=c.head, first=c.first, last=c.last,
                 line=c.line, end_line=c.end_line, mods=mods, fields=[], ctors=[], atoms=[], atom_ids=set(),
                 binders=set(), mutual=c.mutual)
        c.decl = d.idx
        self.decls.append(d)
        if c.kind == "notation":
            self._notation(d, c, toks, hk, stack)
            return
        if c.kind in ("macro", "deriving"):
            d.kind = words[hk] if c.kind == "macro" else "deriving"
            for t in toks:
                if self.kind[t] == "id" and c.kind == "macro":
                    self.role[t] = "N"
            d.body = None
            return
        if c.kind == "alias":
            d.kind = "alias"
            i = hk + 1
            if i < len(toks) and self.kind[toks[i]] == "id":
                d.name_tok = toks[i]
                d.name = words[i]
                d.full = self._full(ns, d.name)
                self.role[toks[i]] = "D"
                self._add_name(d.full, d, d.line, "decl")
            return
        kw = words[hk]
        i = hk + 1
        if kw == "class" and i < len(toks) and words[i] == "inductive":
            kw = "inductive"
            d.kind = "class"
            i += 1
        if kw == "instance":
            while i < len(toks) and words[i] == "(" and i + 1 < len(toks) and words[i + 1] == "priority":
                e = self._group_end(toks, i)
                for t in toks[i:e + 1]:
                    self.role[t] = "n"
                i = e + 1
        if kw != "example" and i < len(toks) and self.kind[toks[i]] == "id":
            d.name_tok = toks[i]
            d.name = words[i]
            d.full = self._full(ns, d.name)
            self.role[toks[i]] = "D"
            i += 1
        d.ns = tuple(split_name(d.full)[:-1]) if d.full else tuple(ns)
        if d.full:
            self._add_name(d.full, d, d.line, "decl", "protected" in mods)
        if i + 1 < len(toks) and words[i] == "." and words[i + 1] == "{":
            e = self._group_end(toks, i + 1)
            for t in toks[i + 2:e]:
                if self.kind[t] == "id":
                    self.role[t] = "u"
            i = e + 1
        # signature: binder groups, then the type up to := / where / |
        sig_toks = toks[i:]
        body = None
        depth = 0
        for k, t in enumerate(sig_toks):
            w = self.tx(t)
            if self.kind[t] in ("sym", "op"):
                if w in OPEN_BR:
                    depth += 1
                elif w in CLOSE_BR:
                    depth -= 1
                elif depth == 0 and (w == ":=" or (w == "|" and self._line_first(t))):
                    body = k
                    break
            elif self.kind[t] == "kw" and depth == 0 and w in ("where", "deriving"):
                body = k
                break
        d.body = sig_toks[body] if body is not None else None
        head = sig_toks[:body] if body is not None else sig_toks
        d.binders |= self._binder_groups(head, mark=True, stop={":"})
        if kw in ("structure", "class") and body is not None:
            self._structure(d, sig_toks[body:], c)
        elif kw == "inductive":
            self._inductive(d, sig_toks[body:] if body is not None else [], c)

    def _line_first(self, t):
        p = self.sig_pos[t]
        return p == 0 or self.line[self.sig[p - 1]] != self.line[t]

    def _full(self, ns, name):
        if name.startswith("_root_."):
            return name[len("_root_."):]
        return ".".join(list(ns) + [name])

    def _add_name(self, full, d, line, kind, protected=False):
        if full and full not in self.local_names:
            self.local_names[full] = (d.idx, line, kind, protected)

    def _structure(self, d, toks, c):
        """Fields of a structure or class: the names before the colon (or binder) on
        each line at the body's indentation; `name ::` names the constructor."""
        if not toks or self.tx(toks[0]) != "where":
            if toks and self.tx(toks[0]) == ":=":
                pass
            else:
                self._add_name(d.full + ".mk", d, d.line, "ctor")
                return
        rest = toks[1:]
        field_col = None
        ctor = None
        lines_seen = set()
        for k, t in enumerate(rest):
            ln = self.line[t]
            if ln in lines_seen or not self._line_first(t):
                continue
            lines_seen.add(ln)
            colx = self.col(t)
            if self.kind[t] == "kw" and self.tx(t) == "deriving":
                break
            if field_col is None:
                field_col = colx
            if colx != field_col:
                continue
            # this line starts a field (or the constructor)
            j = k
            names = []
            while j < len(rest) and self.line[rest[j]] == ln and self.kind[rest[j]] == "id":
                names.append(rest[j])
                j += 1
            nxt = self.tx(rest[j]) if j < len(rest) and self.line[rest[j]] == ln else ""
            if names and nxt == "::":
                ctor = self.tx(names[0])
                self.role[names[0]] = "C"
                self._add_name(d.full + "." + ctor, d, ln, "ctor")
                d.ctors.append((ctor, ln))
                continue
            if names and nxt in (":", "(", "{", "[", "⦃"):
                for nt in names[:1] if nxt != ":" else names:
                    fn = self.tx(nt)
                    self.role[nt] = "F"
                    self._add_name(d.full + "." + fn, d, ln, "field")
                    d.fields.append((fn, ln))
                    d.binders.add(fn)
                if nxt != ":":
                    # binders of a field with parameters: name (x : T) : U
                    d.binders |= self._binder_groups(rest[j:], mark=True, stop={":"})
                continue
            if self.tx(t) in ("(", "{", "[", "⦃"):
                e = self._group_end(rest, k)
                inner = rest[k + 1:e]
                cpos = next((q for q, x in enumerate(inner) if self.tx(x) == ":"), None)
                for nt in (inner[:cpos] if cpos is not None else []):
                    if self.kind[nt] == "id":
                        fn = self.tx(nt)
                        self.role[nt] = "F"
                        self._add_name(d.full + "." + fn, d, ln, "field")
                        d.fields.append((fn, ln))
                        d.binders.add(fn)
        if ctor is None:
            self._add_name(d.full + ".mk", d, d.line, "ctor")
        # `extends A, B` gives the parent projections toA and toB
        hk = self._cmd_sig(self.commands[c.idx])
        words = [self.tx(t) for t in hk]
        if "extends" in words:
            i = words.index("extends") + 1
            depth = 0
            expect = True
            while i < len(words) and words[i] not in ("where", ":=") :
                w = words[i]
                if w in OPEN_BR:
                    depth += 1
                elif w in CLOSE_BR:
                    depth -= 1
                elif depth == 0 and w == ",":
                    expect = True
                elif depth == 0 and expect and self.kind[hk[i]] == "id":
                    short = split_name(w)[-1]
                    self._add_name(d.full + ".to" + short, d, d.line, "field")
                    d.binders.add("to" + short)
                    # a parent declared earlier in this file lends its fields to this body
                    parent = next((x for x in reversed(self.decls[:d.idx]) if x.full and x.kind in ("structure", "class")
                                   and split_name(x.full)[-1] == short), None)
                    if parent is not None:
                        d.binders |= {f for f, _ in parent.fields}
                    expect = False
                i += 1

    def _inductive(self, d, toks, c):
        for k, t in enumerate(toks):
            if self.tx(t) == "|" and k + 1 < len(toks) and self.kind[toks[k + 1]] == "id":
                nt = toks[k + 1]
                cn = self.tx(nt)
                self.role[nt] = "C"
                self._add_name(d.full + "." + cn, d, self.line[nt], "ctor")
                d.ctors.append((cn, self.line[nt]))
                # binders of the constructor
                j = k + 2
                d.binders |= self._binder_groups(toks[j:], mark=True, stop={":", "|"})
            elif self.kind[t] == "kw" and self.tx(t) == "deriving":
                break

    def _notation(self, d, c, toks, hk, stack):
        words = [self.tx(t) for t in toks]
        d.kind = words[hk]
        d.is_local_notation = bool({"local", "scoped"} & {w for t, w in zip(toks[:hk], words[:hk])})
        i = hk + 1
        arrow = next((k for k in range(i, len(toks)) if words[k] == "=>"), len(toks))
        atoms = []
        k = i
        while k < arrow:
            t = toks[k]
            w = words[k]
            if w == "(" and k + 1 < arrow and words[k + 1] in ("name", "priority"):
                e = self._group_end(toks, k)
                for x in toks[k:e + 1]:
                    self.role[x] = "n"
                k = e + 1
                continue
            if self.kind[t] == "str":
                atoms.append(json.loads(w) if w.startswith('"') else w)
            elif self.kind[t] == "id":
                self.role[t] = "N"
                d.binders.add(w)
            k += 1
        d.atoms = [a.strip() for a in atoms if a.strip()]
        d.atom_ids = {a for a in d.atoms if IDENT_RE.fullmatch(a)}
        if d.atoms:
            d.name = " ".join(d.atoms)
        d.body = toks[arrow] if arrow < len(toks) else None
        d.ns = tuple(c.ns)
        target = stack[-1] if d.is_local_notation else stack[0]
        target["notations"].append(d.idx)

    # -- token roles inside one command
    def _roles(self, c):
        """Mark binders, patterns, fields, tactics, universes and notation parts in
        one command; whatever stays unmarked is a reference to resolve."""
        toks = self._cmd_sig(c)
        c.term_opens = []
        d = self.decls[c.decl] if c.decl is not None else None
        binders = d.binders if d is not None else set()
        c.binders = binders
        if not toks:
            return
        kind, role = self.kind, self.role
        words = [self.tx(t) for t in toks]
        if c.kind in ("namespace", "section", "end", "universe", "import"):
            for t in toks:
                if kind[t] == "id":
                    role[t] = "u" if c.kind == "universe" else "n"
            return
        if c.kind == "set_option":
            for k, t in enumerate(toks):
                if words[k] == "in":
                    break
                if kind[t] == "id":
                    role[t] = "o"
            return
        if c.kind == "variable":
            binders |= {self.tx(t) for t in toks if role.get(t) == "b"}
        if c.kind == "macro":
            return
        ns = list(d.ns) if d is not None and d.ns is not None else list(c.ns)
        n = len(toks)
        in_by = False
        for k in range(n):
            t = toks[k]
            w = words[k]
            kd = kind[t]
            prev = words[k - 1] if k else ""
            if kd == "id" and t not in role:
                s0, e0 = self.start[t], self.end[t]
                if s0 and self.text[s0 - 1] in NOTATION_LEAD:
                    role[t] = "N"          # part of a notation such as →L[ℂ], ∘L or #v[...]
                    continue
                if e0 - s0 <= 2 and self.text[e0:e0 + 1] in ("(", "["):
                    role[t] = "N"          # a notation head written against its bracket: C(X, Y), s(x, y), 𝓝[s]
                    continue
                if prev in ("Type", "Sort") and kind[toks[k - 1]] == "kw":
                    role[t] = "u"
                    continue
            if kd == "kw" and w in ("by", "decreasing_by"):
                in_by = True
            elif kd == "id" and w == "structural" and prev == "termination_by":
                role[t] = "t"
            elif kd == "kw" and w == "open" and c.kind != "open":
                # `open X in` inside a term opens X for what follows it
                c.term_opens.append((t, self._parse_open(toks, k, ns)))
                continue
            elif kd == "kw" and w == "set_option" and c.kind != "set_option":
                j = k + 1
                while j < n and words[j] != "in":
                    if kind[toks[j]] == "id":
                        role[toks[j]] = "o"
                    j += 1
                continue
            elif kd == "kw" and w in ("Type", "Sort") and k + 1 < n and words[k + 1] == "(":
                e = self._group_end(toks, k + 1)
                for x in toks[k + 2:e]:
                    if kind[x] == "id":
                        role[x] = "u"
                continue
            elif kd == "sym" and w == "{" and prev == "." and self.start[t] == self.end[toks[k - 1]]:
                e = self._group_end(toks, k)
                for x in toks[k + 1:e]:
                    if kind[x] == "id":
                        role[x] = "u"          # universe arguments: Foo.{u, v}
                continue
            # tactic names where a tactic can start
            if kd == "id" and t not in role and w in TACTICS:
                if (prev in ("by", "decreasing_by", ";", "<;>", "·", ".") or (k and role.get(toks[k - 1]) == "t")
                        or (in_by and (self._line_first(t) or prev in ("=>", "|", "(")))):
                    role[t] = "t"
                    if k + 2 < n and kind[toks[k + 1]] == "id" and words[k + 2] == ":" and "." not in words[k + 1]:
                        role[toks[k + 1]] = "b"      # a named hypothesis: cases h : e, by_cases h : p
                        binders.add(words[k + 1])
            # binder notations: ∀ x y, ∃ x ∈ s, ∑ i ∈ range n, fun x => ...
            if (kd == "sym" and w in BINDER_SYMS) or (kd == "kw" and w == "fun"):
                j = k + 1
                while j < n and kind[toks[j]] == "sym" and words[j] in BINDER_DECOR:
                    j += 1
                if kd == "kw" and j < n and words[j] == "|":
                    continue        # fun | pat => ..., read as match arms
                binders |= self._binder_list(toks, j)
            elif kd == "kw" and w in ("let", "have", "haveI", "letI", "obtain", "suffices"):
                binders |= self._let_binders(toks, k + 1)
            elif kd == "kw" and w == "if" and k + 2 < n and kind[toks[k + 1]] == "id" and words[k + 2] == ":":
                role[toks[k + 1]] = "b"
                binders.add(words[k + 1])
            elif kd == "kw" and w == "match":
                j = k + 1
                while j < n and words[j] != "with":
                    if kind[toks[j]] == "id" and j + 1 < n and words[j + 1] == ":" and "." not in words[j]:
                        role[toks[j]] = "b"
                        binders.add(words[j])
                    j += 1
            elif kd == "sym" and w in ("(", "{", "⦃", "[") and t not in role:
                e = self._group_end(toks, k)
                if e + 1 < n and words[e + 1] in ("→", "->", "×", "×'") and k + 1 < e and self._has_colon(toks[k + 1:e]):
                    binders |= self._group_names(toks[k + 1:e], w, True)     # (x : A) → B x, (j : ℕ) × D j
                elif w == "{" and k + 1 < n and (kind[toks[k + 1]] == "id" or words[k + 1] in ("(", "⟨")):
                    binders |= self._set_builder(toks, k)
            elif kd in ("kw", "id") and w in TACTIC_BINDERS and (role.get(t) == "t" or (w == "with" and in_by)):
                binders |= self._tactic_binders(toks, k)
            elif kd == "sym" and w == "|" and self._arm_start(toks, k):
                self._arm(toks, k)
            elif kd == "op" and w == ":=" and k and not (d is not None and t == d.body):
                # (the declaration's own := ends its statement: what precedes it is the type)
                pt = toks[k - 1]
                before = words[k - 2] if k >= 2 else ""
                # Inside a term, `name args := value` at the start of a line can only define a
                # field (of a `where` block, at any depth, or of a structure instance).
                if kind[pt] == "id" and pt not in role and (before in ("(", "{", ",", "with") or self._line_first(pt)):
                    role[pt] = "f"           # field of a structure instance, or a named argument
                elif (kind[pt] == "id" and pt not in role) or words[k - 1] == "_" or words[k - 1] in CLOSE_BR:
                    # a where-block field with parameters: toFun x y := ..., right_inv _ := ..., comp_id {X Y} f := ...
                    j = k - 1
                    ln = self.line[t]
                    while j >= 0 and self.line[toks[j]] == ln:
                        x = toks[j]
                        wx = words[j]
                        if (kind[x] == "id" and x not in role) or (kind[x] == "sym" and wx == "_"):
                            j -= 1
                        elif kind[x] == "sym" and wx in CLOSE_BR:
                            depth = 0
                            while j >= 0:
                                if words[j] in CLOSE_BR:
                                    depth += 1
                                elif words[j] in OPEN_BR:
                                    depth -= 1
                                    if depth == 0:
                                        break
                                j -= 1
                            j -= 1
                        else:
                            break
                    first = toks[j + 1] if j + 1 < k else None
                    if (first is not None and first != pt and kind[first] == "id" and first not in role
                            and self._line_first(first) and "." not in self.tx(first)):
                        role[first] = "f"
                        for x in toks[j + 2:k]:
                            if kind[x] == "id" and "." not in self.tx(x) and x not in role:
                                role[x] = "b"
                                binders.add(self.tx(x))

    def _has_colon(self, inner):
        """Whether a bracket group's contents have a top-level type colon, as a
        binder group (x : A) has and a parenthesised term (f x) has not."""
        depth = 0
        for t in inner:
            w = self.tx(t)
            if w in OPEN_BR:
                depth += 1
            elif w in CLOSE_BR:
                depth -= 1
            elif depth == 0 and w == ":":
                return True
        return False

    def _binder_list(self, toks, j):
        """Binders right after a binder symbol: identifiers and bracket groups up to
        the first other token (a colon, a binder predicate, a comma, `in`, ∂)."""
        names = set()
        n = len(toks)
        while j < n:
            t = toks[j]
            w = self.tx(t)
            if self.kind[t] == "id" and "." not in w:
                self.role[t] = "b"
                names.add(w)
                j += 1
                continue
            if self.kind[t] == "sym" and w in ("(", "{", "[", "⦃", "⟨"):
                e = self._group_end(toks, j)
                names |= self._group_names(toks[j + 1:e], w, True)
                # patterns such as ⟨a, b⟩ bind every identifier inside
                if w == "⟨":
                    for x in toks[j + 1:e]:
                        if self.kind[x] == "id" and "." not in self.tx(x):
                            self.role[x] = "b"
                            names.add(self.tx(x))
                j = e + 1
                continue
            if self.kind[t] == "sym" and w == "_":
                j += 1
                continue
            break
        return names

    def _let_binders(self, toks, j):
        """Names bound by let, have, obtain and suffices: a name with its parameter
        groups (have h (x : X) : P x := ...), or a destructuring pattern
        (obtain ⟨a, ha⟩ | h := e), up to the := or the type colon."""
        names = set()
        n = len(toks)
        if j < n and self.kind[toks[j]] == "id":
            self.role[toks[j]] = "b"
            names.add(self.tx(toks[j]))
            names |= self._binder_groups(toks[j + 1:], mark=True, stop={":", ":="})
            return names
        depth = 0
        while j < n:
            t = toks[j]
            w = self.tx(t)
            if w in OPEN_BR:
                depth += 1
            elif w in CLOSE_BR:
                depth -= 1
                if depth < 0:
                    break
            elif depth == 0 and w in (":=", ":", "←", "<-", "from"):
                break
            elif self.kind[t] == "id" and "." not in w and t not in self.role and (depth > 0 or self.tx(toks[j - 1]) == "|"):
                self.role[t] = "b"
                names.add(w)
            j += 1
        return names

    def _set_builder(self, toks, k):
        """{x | p x}, {x : T | p x}, {x ∈ s | p x}: binders before the bar."""
        e = self._group_end(toks, k)
        inner = toks[k + 1:e]
        depth = 0
        bar = None
        for q, t in enumerate(inner):
            w = self.tx(t)
            if w in OPEN_BR:
                depth += 1
            elif w in CLOSE_BR:
                depth -= 1
            elif depth == 0 and w == ":=":
                return set()
            elif depth == 0 and w in ("|", "//"):
                bar = q
                break
        if bar is None:
            return set()
        names = set()
        depth = 0
        for t in inner[:bar]:
            w = self.tx(t)
            if w in OPEN_BR:
                depth += 1
            elif w in CLOSE_BR:
                depth -= 1
            elif self.kind[t] == "id" and "." not in w:
                self.role[t] = "b"
                names.add(w)
            elif depth == 0 and w in (":", "∈", "∉", "⊆", "<", ">", "≤", "≥"):
                break
        return names

    def _tactic_binders(self, toks, k):
        names = set()
        n = len(toks)
        ln = self.line[toks[k]]
        j = k + 1
        depth = 0
        bars = self.tx(toks[k]) in ("rcases", "obtain", "rintro", "rintros", "with")
        last = self.tx(toks[k])
        while j < n:
            t = toks[j]
            w = self.tx(t)
            if self.line[t] != ln:
                # a pattern may continue on the next line after `with`, a bar, a comma or an open bracket
                if depth > 0 or last in ("with", "|", ","):
                    ln = self.line[t]
                else:
                    break
            if w in (":=", ":", "using", "at", "from", ";", "<;>", "=>") or (w == "|" and not bars):
                if depth == 0:
                    break
            if w in OPEN_BR:
                depth += 1
            elif w in CLOSE_BR:
                depth -= 1
            elif self.kind[t] == "id" and "." not in w and t not in self.role:
                self.role[t] = "b"
                names.add(w)
            last = w
            j += 1
        return names

    def _arm_start(self, toks, k):
        """A bar that begins a match arm: first on its line, after `with`, `fun` or
        `:=`, or followed by `=>` on the same line before any other bar."""
        t = toks[k]
        if self._line_first(t):
            return True
        prev = self.tx(toks[k - 1]) if k else ""
        if prev in ("with", "fun", "λ", ":="):
            return True
        ln = self.line[t]
        depth = 0
        for j in range(k + 1, len(toks)):
            x = toks[j]
            if self.line[x] != ln:
                return False
            w = self.tx(x)
            if w in OPEN_BR:
                depth += 1
            elif w in CLOSE_BR:
                depth -= 1
                if depth < 0:
                    return False
            elif depth == 0 and w == "|":
                return False
            elif depth == 0 and w == "=>":
                return True
        return False

    def _arm(self, toks, k):
        """Identifiers of a match pattern, up to `=>`. Each is a pattern variable
        unless it resolves to a constructor (decided at resolution)."""
        names = set()
        n = len(toks)
        j = k + 1
        if j < n and self.kind[toks[j]] == "id" and self.role.get(toks[j]) == "C":
            return names                 # an inductive constructor line
        depth = 0
        end = None
        while j < n:
            w = self.tx(toks[j])
            if w in OPEN_BR:
                depth += 1
            elif w in CLOSE_BR:
                depth -= 1
                if depth < 0:
                    return names
            elif depth == 0 and w == "=>":
                end = j
                break
            elif depth == 0 and w in (":=", "where"):
                return names
            j += 1
        if end is None:
            return names
        for t in toks[k + 1:end]:
            if self.kind[t] == "id" and t not in self.role and "." not in self.tx(t) and not self._after_dot(t):
                self.role[t] = "p"
        return names

    def _after_dot(self, t):
        s = self.start[t]
        return s > 0 and self.text[s - 1] == "."


# ------------------------------------------------------------------ resolution

class Target:
    __slots__ = ("kind", "name", "line", "path", "ctor", "protected", "decl")

    def __init__(self, kind, name, line=None, path=None, ctor=False, protected=False, decl=None):
        self.kind, self.name, self.line, self.path = kind, name, line, path
        self.ctor, self.protected, self.decl = ctor, protected, decl


AMBIGUOUS = Target("ambiguous", "")
_XREF = None


def xref():
    """data/lean_xref.json. Without it nothing outside the file can be linked, so its
    absence is reported; a damaged file stops the build."""
    global _XREF
    if _XREF is None:
        try:
            _XREF = json.loads(XREF_PATH.read_text(encoding="utf-8"))
        except FileNotFoundError:
            import sys
            print(f"lean_render: {XREF_PATH} is missing; run scripts/build_lean_xref.py. "
                  "Only names declared in each file are linked.", file=sys.stderr)
            _XREF = {"external": {}, "aliases": {}, "statements": {}, "files": [], "upstream_commit": ""}
    return _XREF


# Bits of an external name's flag in data/lean_xref.json.
EXT_CTOR, EXT_PROTECTED = 1, 2


class Resolver:
    """Lean's name resolution over this file's declarations, the OpenAI modules it
    imports, and the external names the pinned sources declare."""

    def __init__(self, lf: LeanFile, sid: str | None = None):
        self.lf = lf
        x = xref()
        self.ext = x.get("external", {})
        self.ext_alias = x.get("aliases", {})
        st = x.get("statements", {}).get(sid or "", {})
        files = x.get("files", [])
        self.scope = {k: (files[v[0]], v[1], v[2] if len(v) > 2 else 0) for k, v in st.get("scope", {}).items()}
        self.library = {k: (files[v[0]], v[1]) for k, v in st.get("library", {}).items()}
        self.commit = x.get("upstream_commit", "")

    def _lookup(self, cand, atomic, cmd_idx):
        lf = self.lf
        hit = lf.local_names.get(cand)
        if hit is not None:
            di, line, kind, prot = hit
            d = lf.decls[di]
            visible = d.cmd <= cmd_idx or (d.mutual is not None and d.mutual == lf.commands[cmd_idx].mutual)
            if visible and not (atomic and prot):
                return Target("local", cand, line=line, ctor=(kind == "ctor"), protected=prot, decl=di)
        al = lf.aliases.get(cand)
        if al:
            for tgt in al:
                h = self._lookup(tgt, False, cmd_idx)
                if h is not None:
                    return h
        s = self.scope.get(cand)
        if s is not None:
            if not (atomic and s[2] & EXT_PROTECTED):
                return Target("oai", cand, line=s[1], path=s[0], ctor=bool(s[2] & EXT_CTOR))
        f = self.ext.get(cand)
        if f is not None:
            if not (atomic and f & EXT_PROTECTED):
                return Target("ext", cand, ctor=bool(f & EXT_CTOR), protected=bool(f & EXT_PROTECTED))
        a = self.ext_alias.get(cand)
        if a is not None:
            f = self.ext.get(a)
            if f is not None:
                return Target("ext", a, ctor=bool(f & EXT_CTOR))
        return None

    def resolve(self, name, ns, opens, cmd_idx):
        """(Target, number of name components it covers), AMBIGUOUS, or (None, 0).
        Components after the covered ones are field projections."""
        parts = split_name(name)
        if not parts:
            return None, 0
        root_only = parts[0] == "_root_"
        if root_only:
            parts = parts[1:]
            if not parts:
                return None, 0
        for k in range(len(parts), 0, -1):
            prefix = parts[:k]
            atomic = k == 1
            joined = ".".join(prefix)
            hits = []
            if not root_only:
                for i in range(len(ns), 0, -1):
                    h = self._lookup(".".join(list(ns[:i]) + prefix), atomic, cmd_idx)
                    if h is not None:
                        hits.append(h)
                        break
            if not hits:
                h = self._lookup(joined, False, cmd_idx)
                if h is not None:
                    hits.append(h)
                if not root_only:
                    for o in opens:
                        for cand in o.candidates(prefix):
                            h = self._lookup(cand, atomic, cmd_idx)
                            if h is not None and all(h.name != x.name for x in hits):
                                hits.append(h)
            if hits:
                uniq = {h.name: h for h in hits}
                if len(uniq) == 1:
                    return next(iter(uniq.values())), k + (1 if root_only else 0)
                return AMBIGUOUS, k + (1 if root_only else 0)
        return None, 0


def reference_candidates(lf: LeanFile):
    """Every full name the resolver could look up for this file's identifiers, for
    scripts/build_lean_xref.py: the names it must find in the pinned sources."""
    out = set()
    cmds = lf.commands
    for ci, c in enumerate(cmds):
        toks = lf._cmd_sig(c)
        for t in toks:
            if lf.kind[t] != "id":
                continue
            parts = split_name(lf.tx(t))
            if not parts:
                continue
            if parts[0] == "_root_":
                parts = parts[1:]
                for k in range(len(parts), 0, -1):
                    out.add(".".join(parts[:k]))
                continue
            ns = list(c.ns)
            d = lf.decls[c.decl] if c.decl is not None else None
            if d is not None and d.ns is not None:
                ns = list(d.ns)
            opens = list(c.opens) + [od for ft, ods in (c.term_opens or []) if ft < t for od in ods]
            for k in range(len(parts), 0, -1):
                prefix = parts[:k]
                for i in range(len(ns), -1, -1):
                    out.add(".".join(ns[:i] + prefix))
                for o in opens:
                    out.update(o.candidates(prefix))
    for tgts in lf.aliases.values():
        out.update(tgts)
    return out


# ------------------------------------------------------------------ copy

_COPY = None


def copy():
    global _COPY
    if _COPY is None:
        _COPY = json.loads(COPY_PATH.read_text(encoding="utf-8"))
    return _COPY


def T(path: str, **kw) -> str:
    node = copy()
    for part in path.split("."):
        node = node[part]
    if kw:
        node = node.format(**{k: (f"{v:,}" if isinstance(v, int) else v) for k, v in kw.items()})
    return node


def Tn(path: str, n: int, **kw) -> str:
    """The `one` or `many` form of a counted string."""
    return T(path + (".one" if n == 1 else ".many"), n=n, **kw)


_ESC = str.maketrans({"&": "&amp;", "<": "&lt;", ">": "&gt;", '"': "&quot;", "'": "&#x27;"})


def esc(s) -> str:
    """html.escape(s, quote=True), as one C-level translate."""
    return ("" if s is None else str(s)).translate(_ESC)


def wbr(name: str) -> str:
    """A name escaped, with break opportunities after `_`, `.` and `/`, so a long
    Lean name wraps at its seams in a narrow column, never mid-word."""
    return re.sub(r"([_./])", r"\1<wbr>", esc(name))


# ------------------------------------------------------------------ reading

SNIPPET_CLASS = {"lc": "c", "bc": "c", "doc": "c d", "mdoc": "c d", "str": "s", "chr": "s", "num": "n",
                 "attr": "a", "kw": "k"}
FILE_CLASS = {"lc": "c", "bc": "c", "doc": "cd", "mdoc": "cd", "str": "s", "chr": "s", "num": "n",
              "attr": "a", "kw": "k", "notn": "nt"}


class Reading:
    """A challenge file read for its page: what every identifier refers to, and
    which declarations each declaration uses."""

    def __init__(self, text: str, sid: str | None = None, holes=()):
        self.lf = lf = LeanFile(text)
        self.res = Resolver(lf, sid)
        self.holes = set(holes or ())
        self.links = {}          # token -> (Target, components covered)
        self.notation_use = {}   # token -> notation decl index
        self.library_site = {}   # declaration-name token -> (path, line)
        self.stats = {"local": 0, "oai": 0, "ext": 0, "notation": 0, "library": 0, "ambiguous": 0,
                      "unknown": 0, "variable": 0, "projection": 0, "pattern": 0}
        self.unknown = {}
        self.unknown_toks = []
        self.proj = {}           # token -> components written after a variable or term (x.foo)
        self._resolve_all()
        self.edges = self._graph()

    def _active_atoms(self, c):
        atoms = {}
        for di in c.notations or ():
            for a in self.lf.decls[di].atom_ids:
                atoms[a] = di
        return atoms

    def _resolve_all(self):
        lf, res, st = self.lf, self.res, self.stats
        for c in lf.commands:
            toks = lf._cmd_sig(c)
            if not toks:
                continue
            d = lf.decls[c.decl] if c.decl is not None else None
            ns = d.ns if d is not None and d.ns is not None else c.ns
            binders = set(c.binders or ()) | set(c.vars or ())
            dotted = any("." in b for b in binders)
            term_opens = getattr(c, "term_opens", None) or []
            atoms = self._active_atoms(c) if c.notations else {}

            def opens_at(t):
                if not term_opens:
                    return c.opens
                extra = [od for ft, ods in term_opens if ft < t for od in ods]
                return c.opens + extra if extra else c.opens

            for t in toks:
                if lf.kind[t] == "id" and lf.role.get(t) == "p":
                    w = lf.tx(t)
                    if w in atoms:
                        self.notation_use[t] = atoms[w]
                        st["notation"] += 1
                        continue
                    tg, k = res.resolve(w, ns, opens_at(t), c.idx)
                    if tg is not None and tg is not AMBIGUOUS and tg.ctor:
                        self.links[t] = (tg, k)
                        st[tg.kind] += 1
                    else:
                        binders.add(w)
                        st["pattern"] += 1
            last_ns_tok = None
            for t in toks:
                if lf.kind[t] != "id":
                    continue
                r = lf.role.get(t)
                w = lf.tx(t)
                if r == "n":
                    last_ns_tok = t
                    continue
                if r == "D" and d is not None and d.full and d.full in res.library:
                    self.library_site[t] = res.library[d.full]
                    st["library"] += 1
                    continue
                if r not in (None, "e") or w in ("sorry", "admit"):
                    continue
                if r is None and w in atoms:
                    self.notation_use[t] = atoms[w]
                    st["notation"] += 1
                    continue
                if lf._after_dot(t):
                    st["projection"] += 1
                    self.proj[t] = split_name(w)              # (e).foo: foo is a field or a dot call
                    continue
                parts = split_name(w)
                if r == "e":
                    if last_ns_tok is None:
                        continue
                    w = lf.tx(last_ns_tok) + "." + w
                elif parts and (parts[0] in binders or (dotted and any(".".join(parts[:q]) in binders for q in range(2, len(parts) + 1)))):
                    st["variable"] += 1
                    if len(parts) > 1:
                        self.proj[t] = parts[1:]              # x.foo.bar on a variable x
                    continue
                tg, k = res.resolve(w, ns, opens_at(t), c.idx)
                if tg is not None and tg is not AMBIGUOUS and 0 < k < len(parts):
                    self.proj[t] = parts[k:]                  # Global.x.foo: the part after the name
                if tg is None:
                    st["unknown"] += 1
                    self.unknown[w] = self.unknown.get(w, 0) + 1
                    self.unknown_toks.append(t)
                elif tg is AMBIGUOUS:
                    st["ambiguous"] += 1
                else:
                    if r == "e":
                        k = len(split_name(lf.tx(t)))
                        self.links[t] = (tg, -k)        # the whole written name
                    else:
                        self.links[t] = (tg, k)
                    st[tg.kind] += 1

    def _graph(self):
        """Edges between declarations: d uses e when a name in d's text resolves to
        e (its fields and constructors count as e), or when d uses e's notation.
        A theorem contributes only its statement, before `:=`.

        Dot notation on a variable (x.foo, (f a).foo) calls T.foo for x's type T,
        which a textual scan cannot know. Such a `foo` adds an edge to every local
        declaration named foo in the namespace of a type this file declares: the
        list may then hold a declaration the statement does not need, never omit
        one it does. These edges are never shown as links in the code."""
        lf = self.lf
        edges = [set() for _ in lf.decls]
        self.imported = [dict() for _ in lf.decls]     # decl -> {OpenAI name it uses: (path, line)}
        types = {d.full for d in lf.decls if d.full and d.kind in ("structure", "class", "inductive", "def", "abbrev", "opaque")}
        by_field = {}
        for full, (di, _line, _kind, _p) in lf.local_names.items():
            parent, _, last = full.rpartition(".")
            if parent in types:
                by_field.setdefault(last, set()).add(di)
        for c in lf.commands:
            if c.decl is None:
                continue
            d = lf.decls[c.decl]
            # a theorem contributes its statement; a definition hole is followed whole, since
            # its body here is the copy a reader compares with the one in OpenAI's library
            limit = d.body if d.kind in ("theorem", "lemma") else None
            sym_atoms = []
            for di in c.notations or ():
                nd = lf.decls[di]
                sym_atoms += [(a, di) for a in nd.atoms if a not in nd.atom_ids]
            chunks = []
            for i in range(c.first, (limit if limit is not None else c.last + 1)):
                if i in self.links:
                    tg = self.links[i][0]
                    if tg.kind == "local" and tg.decl is not None and tg.decl != d.idx:
                        edges[d.idx].add(tg.decl)
                    elif tg.kind == "oai":
                        self.imported[d.idx][tg.name] = (tg.path, tg.line)
                elif i in self.notation_use:
                    edges[d.idx].add(self.notation_use[i])
                if i in self.proj and by_field:
                    for comp in self.proj[i]:
                        for di in by_field.get(comp, ()):
                            if di != d.idx and lf.decls[di].cmd <= c.idx:
                                edges[d.idx].add(di)
                if sym_atoms and lf.kind[i] not in COMMENT and lf.kind[i] not in ("str", "chr"):
                    chunks.append(lf.text[lf.start[i]:lf.end[i]])
            if sym_atoms:
                body = "".join(chunks)
                for a, di in sym_atoms:
                    if a in body:
                        edges[d.idx].add(di)
        return edges

    # -- what the checked theorem rests on
    def must_check(self, theorem_names, extra=()):
        """The declarations the checked theorems reach, with the configuration's other
        checked names (its definition holes) as further starting points. Returns the
        starting points, the reached declarations in dependency order, and those the
        theorems name directly."""
        lf = self.lf
        seeds = []
        for full in theorem_names:
            hit = lf.local_names.get(full)
            if hit is not None and hit[0] not in seeds:
                seeds.append(hit[0])
        if not seeds:
            seeds = [d.idx for d in lf.decls if d.kind in ("theorem", "lemma", "axiom")][:1]
        heads = list(seeds)
        for full in extra:
            hit = lf.local_names.get(full)
            if hit is not None and hit[0] not in seeds:
                seeds.append(hit[0])
        reach = set(seeds)
        todo = list(seeds)
        direct = set()
        for s_ in heads:
            direct |= self.edges[s_]
        while todo:
            x = todo.pop()
            for y in self.edges[x]:
                if y not in reach:
                    reach.add(y)
                    todo.append(y)
        return heads, self._topo(reach), direct - set(heads)

    def _topo(self, nodes):
        """Dependency order: each declaration after everything it uses, file order
        breaking ties (and the rare cycle of a mutual block)."""
        import heapq
        indeg = {x: 0 for x in nodes}
        users = {x: [] for x in nodes}
        for x in nodes:
            for y in self.edges[x]:
                if y in nodes and y != x:
                    indeg[x] += 1
                    users[y].append(x)
        heap = [x for x in nodes if indeg[x] == 0]
        heapq.heapify(heap)
        out, done = [], set()
        while len(out) < len(nodes):
            if not heap:
                rest = min(x for x in nodes if x not in done)
                indeg[rest] = 0
                heap = [rest]
            x = heapq.heappop(heap)
            if x in done:
                continue
            done.add(x)
            out.append(x)
            for u in users[x]:
                indeg[u] -= 1
                if indeg[u] == 0:
                    heapq.heappush(heap, u)
        return out


# ------------------------------------------------------------------ HTML

def _wrap(cls, href, inner):
    if href:
        return f'<a class="{cls}" href="{esc(href)}">{inner}</a>' if cls else f'<a href="{esc(href)}">{inner}</a>'
    if cls:
        return f'<span class="{cls}">{inner}</span>'
    return inner


def _emit(lines_out, cur, text, cls=None, href=None):
    """Append text to the current line, splitting at line breaks; each piece keeps
    its class (and link) so no element spans two lines."""
    if "\n" not in text:
        if text:
            cur.append(_wrap(cls, href, text.translate(_ESC)))
        return
    for j, part in enumerate(text.split("\n")):
        if j:
            lines_out.append("".join(cur))
            cur.clear()
        if part:
            cur.append(_wrap(cls, href, part.translate(_ESC)))


def lines_html(text: str) -> list[str]:
    """Highlighted lines without links, for snippets and cards (atlas.css classes),
    each wrapped so that a wrapped line hangs from its own indentation."""
    toks = lex(text)
    out, cur = [], []
    after_decl = False
    for k, s, e in toks:
        w = text[s:e]
        cls = SNIPPET_CLASS.get(k)
        if k == "kw" and w in DECL_KW:
            after_decl = True
        elif k == "id":
            if w in ("sorry", "admit"):
                cls = "x"
            elif after_decl:
                cls = "d"
            after_decl = False
        elif k not in ("ws", "attr") and not (k == "kw" and w in MODIFIERS):
            after_decl = False if k != "kw" else after_decl
        _emit(out, cur, w, cls)
    out.append("".join(cur))
    if text.endswith("\n") and out and not out[-1]:
        out.pop()
    raw = text.split("\n")
    res = []
    for i, h in enumerate(out):
        src = raw[i] if i < len(raw) else ""
        ind = len(src) - len(src.lstrip(" "))
        res.append(hang(h, ind))
    return res


def hang(inner: str, indent: int) -> str:
    """One snippet line as an inline block that wraps with a hanging indent: the
    continuation of a long line starts four columns right of the line's own
    indentation, never at column 0. Inline styles, so it works on every page."""
    if not inner:
        return inner
    h = indent + 4
    return (f'<span style="display:inline-block;vertical-align:top;max-width:100%;'
            f'padding-left:{h}ch;text-indent:-{h}ch">{inner}</span>')


def _decl_label(lf: LeanFile, d: Decl) -> tuple[str, str]:
    """(namespace, short name) shown for a declaration; an anonymous instance shows
    its class, a notation its symbols."""
    if d.full:
        parts = split_name(d.full)
        return ".".join(parts[:-1]), parts[-1]
    if d.kind in NOTATION_KW and d.atoms:
        return "", " ".join(d.atoms)
    toks = lf._cmd_sig(lf.commands[d.cmd])
    try:
        p = toks.index(d.kw_tok)
    except ValueError:
        p = 0
    stop = d.body if d.body is not None else toks[-1] + 1
    seg = [lf.tx(t) for t in toks[p + 1:] if t < stop]
    if seg and seg[0] == ":":
        seg = seg[1:]
    label = " ".join(seg)
    label = re.sub(r"\s+([,)\]}])", r"\1", re.sub(r"([(\[{])\s+", r"\1", label))
    if len(label) > 64:
        label = label[:61].rstrip() + "…"
    return "", label


def _head_lines(lf: LeanFile, d: Decl) -> int:
    """Lines the hover card shows: a declaration of six lines or fewer whole, else
    its head, up to the line where its body starts (at most eight lines)."""
    whole = d.end_line - d.line + 1
    if whole <= 6:
        return max(1, whole)
    end = lf.line[d.body] if d.body is not None else d.end_line
    return max(1, min(end - d.line + 1, 8))


def file_section(stmt: dict, *, commit: str, root: str = "../") -> str:
    """The whole challenge file with every resolved identifier linked, beside the
    "What you must check" panel. Replaces the old "Read the whole file" fold."""
    text = stmt["lean"]
    sid = stmt["id"]
    holes = stmt["comparator"].get("definition_names") or []
    configured = stmt["comparator"].get("theorem_names") or []
    # what Comparator checks: the configured theorems, or, when a configuration names
    # none, the definitions it checks by name and type
    theorems = configured or (holes if holes else stmt.get("theorems", [])[:1])
    rd = Reading(text, sid, holes)
    lf = rd.lf
    commit_short = commit[:7]
    blob = GITHUB_BLOB

    # -- the file, line by line
    out, cur = [], []
    decl_at_tok = {d.kw_tok: d for d in lf.decls}
    for i, k in enumerate(lf.kind):
        s, e = lf.start[i], lf.end[i]
        w = lf.text[s:e]
        cls = FILE_CLASS.get(k)
        href = None
        if k == "id":
            r = lf.role.get(i)
            if w in ("sorry", "admit"):
                cls = "x"
            elif i in rd.links:
                tg, kk = rd.links[i]
                if tg.kind == "local":
                    cls, href = "r", f"#L{tg.line}"
                elif tg.kind == "oai":
                    cls, href = "o", blob.format(commit=commit, path=tg.path, line=tg.line)
                else:
                    cls, href = "m", MATHLIB_FIND.format(name=quote(tg.name, safe=".'_"))
                parts = split_name(w)
                if kk > 0 and kk < len(parts):
                    head = ".".join(parts[:kk])
                    _emit(out, cur, head, cls, href)
                    _emit(out, cur, w[len(head):])
                    continue
            elif i in rd.notation_use:
                nd = lf.decls[rd.notation_use[i]]
                cls, href = "r", f"#L{nd.line}"
            elif i in rd.library_site:
                path, line = rd.library_site[i]
                cls, href = "d lib", blob.format(commit=commit, path=path, line=line)
            elif r in ("D", "F", "C"):
                cls = "d"
            elif r == "t":
                cls = "k"
            else:
                cls = None
        elif k == "kw" and w in ("sorry", "admit"):
            cls = "x"
        _emit(out, cur, w, cls, href)
    out.append("".join(cur))
    if text.endswith("\n") and out and not out[-1]:
        out.pop()
    raw = text.split("\n")
    head_of = {d.line: _head_lines(lf, d) for d in lf.decls}
    big = len(out) > 400
    rows = []
    for n_, h in enumerate(out, 1):
        src = raw[n_ - 1] if n_ - 1 < len(raw) else ""
        ind = len(src) - len(src.lstrip(" "))
        attrs = f' style="--i:{ind}"' if ind else ""
        if n_ in head_of:
            attrs += f' data-h="{head_of[n_]}"'
        if big and (n_ - 1) % 100 == 0:
            if n_ > 1:
                rows.append("</span>")
            rows.append(f'<span class="lx-k" style="--n:{min(100, len(out) - n_ + 1)}">')
        rows.append(f'<span class="ln" id="L{n_}" data-n="{n_}"{attrs}>{h}</span>')
    if big:
        rows.append("</span>")
    code = "".join(rows)

    # -- the panel
    seeds, order, direct = rd.must_check(theorems, extra=holes)
    inset = set(order)
    used_imported = {}         # declarations of the imported OpenAI modules the closure names
    for x in order:
        used_imported.update(rd.imported[x])
    used_by = {x: [] for x in inset}
    for x in inset:
        for y in rd.edges[x]:
            if y in inset and y != x:
                used_by[y].append(x)
    named = [d for d in lf.decls if d.kind not in ("deriving",)]
    total = len([d for d in named if d.idx not in seeds])
    need = [x for x in order if x not in seeds]
    lines_to_read = sum(lf.decls[x].end_line - lf.decls[x].line + 1 for x in order)
    ix = {x: q for q, x in enumerate(order)}
    # the namespace most listed declarations share is said once, above the list
    from collections import Counter
    spaces = Counter(".".join(split_name(lf.decls[x].full)[:-1]) for x in order if lf.decls[x].full)
    common, common_n = spaces.most_common(1)[0] if spaces else ("", 0)
    if not common or common_n * 2 < len(order):
        common = ""
    rows_p = []
    theorem_label = None
    for x in order:
        d = lf.decls[x]
        nsp, short = _decl_label(lf, d)
        if nsp and common and (nsp == common or nsp.startswith(common + ".")):
            nsp = nsp[len(common) + 1:]
        if x in seeds and theorem_label is None:
            theorem_label = short
        flags = []
        if x in seeds and d.kind in ("theorem", "lemma", "axiom"):
            flags.append(f'<span class="lxp-flag lxp-flag--thm">{esc(T("panel.flag_theorem"))}</span>')
        elif x in direct:
            flags.append(f'<span class="lxp-flag">{esc(T("panel.flag_direct"))}</span>')
        if d.full and d.full in holes:
            flags.append(f'<span class="lxp-flag lxp-flag--hole">{esc(T("panel.flag_hole"))}</span>')
        lib = rd.res.library.get(d.full or "")
        lib_html = ""
        if lib:
            lib_html = (f'<a class="lxp-lib" href="{esc(blob.format(commit=commit, path=lib[0], line=lib[1]))}" '
                        f'rel="noopener" aria-label="{esc(T("panel.library_aria", name=d.full))}">{esc(T("panel.library"))}</a>')
        uses = len([y for y in rd.edges[x] if y in inset and y != x])
        users = len(used_by[x])
        rel = (f'<button type="button" class="lxp-rel" data-rel="{ix[x]}" aria-expanded="false" hidden '
               f'aria-label="{esc(T("panel.rel_aria", name=short))}">{esc(T("panel.rel_counts", uses=uses, users=users))}</button>')
        ns_html = f'<span class="lxp-ns">{wbr(nsp)}.<wbr></span>' if nsp else ""
        data_q = esc((d.full or short).lower())
        rows_p.append(
            f'<li class="lxp-row{" is-direct" if x in direct or x in seeds else ""}{" is-thm" if x in seeds else ""}" '
            f'data-q="{data_q}" data-i="{ix[x]}">'
            f'<a class="lxp-go" href="#L{d.line}"><span class="lxp-kind">{esc(d.kind)}</span> '
            f'<code class="lxp-name">{ns_html}{wbr(short)}</code></a>'
            f'<span class="lxp-meta"><span class="lxp-line">{esc(T("panel.line", line=d.line))}</span>{"".join(flags)}{lib_html}{rel}</span></li>')
    data = {
        "n": [[lf.decls[x].line, _decl_label(lf, lf.decls[x])[1]] for x in order],
        "u": [[ix[y] for y in sorted(rd.edges[x]) if y in inset and y != x] for x in order],
    }
    # implicit: instances, notation and attributes the graph cannot follow
    implicit = []
    for d in lf.decls:
        if d.idx in inset:
            continue
        if d.kind in ("instance", "deriving") or d.kind in NOTATION_KW or d.kind in MACRO_KW or d.kind == "axiom":
            implicit.append(d)
    attr_cmds = [c for c in lf.commands if c.kind in ("attribute",)]
    not_needed = [d for d in lf.decls if d.idx not in inset and d not in implicit]

    def mini(d):
        nsp, short = _decl_label(lf, d)
        return (f'<li><a href="#L{d.line}"><span class="lxp-kind">{esc(d.kind)}</span> <code>{wbr(short)}</code></a>'
                f' <span class="lxp-line">{esc(T("panel.line", line=d.line))}</span></li>')

    imported_html = ""
    if used_imported:
        items = []
        for name, (path, line) in sorted(used_imported.items()):
            href = blob.format(commit=commit, path=path, line=line)
            items.append(f'<li><a class="lxp-lib" href="{esc(href)}" rel="noopener" '
                         f'aria-label="{esc(T("panel.library_aria", name=name))}"><code>{wbr(name)}</code></a>'
                         f' <span class="lxp-line">{wbr(path)}:{line}</span></li>')
        imported_html = (f'<div class="lxp-more"><h5 class="lxp-h">{esc(T("panel.imported_heading"))} '
                         f'<span class="count">{len(items):,}</span></h5><p class="lxp-note">{esc(T("panel.imported_intro"))}</p>'
                         f'<ul class="lxp-mini">{"".join(items)}</ul></div>')
    imp_html = ""
    if implicit or attr_cmds:
        items = [mini(d) for d in implicit]
        for c in attr_cmds:
            src = lf.line_text(c.line).strip()
            items.append(f'<li><a href="#L{c.line}"><code>{esc(src[:70] + ("…" if len(src) > 70 else ""))}</code></a>'
                         f' <span class="lxp-line">{esc(T("panel.line", line=c.line))}</span></li>')
        imp_html = (f'<div class="lxp-more"><h5 class="lxp-h">{esc(T("panel.implicit_heading"))} '
                    f'<span class="count">{len(items):,}</span></h5><p class="lxp-note">{esc(T("panel.implicit_intro"))}</p>'
                    f'<ul class="lxp-mini">{"".join(items)}</ul></div>')
    nn_html = ""
    if not_needed:
        nn_html = (f'<details class="lxp-more lxp-nn"><summary>{esc(Tn("panel.not_needed", len(not_needed)))}</summary>'
                   f'<p class="lxp-note">{esc(T("panel.not_needed_intro"))}</p>'
                   f'<ul class="lxp-mini">{"".join(mini(d) for d in not_needed)}</ul></details>')
    n_need = len(need)
    if not n_need:
        summary = T("panel.summary_none")
    elif n_need == total:
        summary = Tn("panel.summary_all", n_need, lines=lines_to_read)
    else:
        summary = Tn("panel.summary", n_need, total=total, lines=lines_to_read)
    if direct - set(seeds) and n_need:
        summary += " " + Tn("panel.summary_direct", len(direct - set(seeds)))
    if used_imported:
        summary += " " + Tn("panel.summary_imported", len(used_imported))
    ns_note = (f'<p class="lxp-note">{esc(T("file.namespace_note", ns=common))}</p>'
               if common and len(order) > 1 else "")
    long_list = len(order) > 12
    controls = ""
    if long_list:
        controls = (f'<div class="lxp-controls" data-lx-controls hidden>'
                    f'<label class="lxp-search"><span class="vh">{esc(T("panel.search_label"))}</span>'
                    f'<input type="search" data-lx-search placeholder="{esc(T("panel.search_placeholder"))}" autocomplete="off" spellcheck="false"></label>'
                    f'<label class="lxp-direct"><input type="checkbox" data-lx-direct> {esc(T("panel.direct_only"))}</label>'
                    f'<span class="lxp-count" data-lx-count role="status"></span></div>')
    if configured or not holes:
        intro = T("panel.intro", theorem=theorem_label or "")
    else:
        intro = T("panel.intro_holes", names=", ".join(split_name(h)[-1] for h in holes))
    if holes:
        intro += " " + T("panel.holes_note")
    panel = (f'<aside class="lxp" aria-labelledby="h-check">'
             f'<h4 class="lxp-title" id="h-check">{esc(T("panel.heading"))}</h4>'
             f'<p class="lxp-intro">{esc(intro)}</p><p class="lxp-sum">{esc(summary)}</p>{ns_note}'
             f'{controls}<ol class="lxp-list" data-lx-list>{"".join(rows_p)}</ol>'
             f'<p class="lxp-empty" data-lx-empty hidden>{esc(T("panel.empty"))} '
             f'<button type="button" data-lx-clear>{esc(T("panel.clear"))}</button></p>'
             f'{imported_html}{imp_html}{nn_html}</aside>')

    # -- legend and counts
    st = rd.stats
    mathlib = xref().get("sources", {}).get("mathlib", {}).get("commit", "")
    legend = (f'<p class="lx-legend"><span class="lx-key lx-key--r">{esc(T("file.legend_local"))}</span>'
              + (f'<span class="lx-key lx-key--o">{esc(T("file.legend_oai", commit=commit_short))}</span>' if st["oai"] or st["library"] else "")
              + f'<span class="lx-key--m">{esc(T("file.legend_mathlib"))}</span></p>')
    counts = T("file.counts", local=st["local"] + st["notation"], ext=st["ext"])
    if st["oai"]:
        counts += " " + Tn("file.counts_imported", st["oai"])
    if st["library"]:
        counts += " " + Tn("file.counts_library", st["library"])
    plain = st["unknown"] + st["ambiguous"]
    if plain:
        counts += " " + Tn("file.counts_plain", plain)
        if st["ambiguous"]:
            counts += " " + Tn("file.counts_ambiguous", st["ambiguous"])
    note_m = T("file.mathlib_note", mathlib=mathlib[:7]) if mathlib else ""
    js_data = json_script({"strings": copy()["script"], "commit": commit_short, "data": data})
    rd.stats["lines"] = len(out)
    rd.stats["must_check"] = n_need
    LAST_STATS[sid] = dict(rd.stats, unknown_names=sorted(rd.unknown.items(), key=lambda kv: -kv[1])[:20])
    return (f'<section class="lx" id="file" aria-labelledby="h-file" data-lx>'
            f'<h3 class="h3" id="h-file">{esc(T("file.heading"))}</h3>'
            f'<p class="intro">{esc(T("file.intro", lines=len(out), commit=commit_short))}</p>'
            f'{legend}<p class="lx-counts">{esc(counts)} {esc(note_m)}</p>'
            f'<div class="lx-bench">{panel}'
            f'<div class="lx-codewrap"><pre class="lx-code" tabindex="0" aria-label="{esc(T("file.code_aria", file=stmt["file"]))}"><code>{code}</code></pre></div>'
            f'</div><div class="lx-card" data-lx-card role="tooltip" hidden></div>{js_data}</section>')


LAST_STATS: dict = {}


def json_script(obj) -> str:
    s = json.dumps(obj, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    return f'<script type="application/json" data-lx-json>{s}</script>'


