#!/usr/bin/env python3
"""Build data/lean_xref.json: where the names in the 416 challenge files are declared.

scripts/lean_render.py links every identifier of a challenge file it can resolve.
Resolution needs to know which candidate names exist, and that knowledge comes
from here, computed once from pinned sources and committed, so the site build
needs no library checkout:

* OpenAI's library (lean/OAI in the openai/math checkout at the pinned commit).
  Only the names the challenge files use are looked up: each local declaration's
  counterpart in the import closure of its file's solution module (the copy a
  Comparator run compares against), and the names a challenge file takes from
  the OpenAI modules it imports itself. Each is recorded with its file and line.
* Mathlib, Batteries and Lean's core library, for the names that are neither
  local nor OpenAI's. Mathlib and Batteries are read at the commits that
  lean/lake-manifest.json pins, with `git archive` from a local Lake packages
  directory (nothing is checked out or changed); Lean's core is read from a
  local toolchain's sources. Only candidate names that occur in the challenge
  files are kept, with two flags: constructor and protected.

    python3 scripts/build_lean_xref.py --packages DIR [--lean-src DIR]
    python3 scripts/build_lean_xref.py --check      # verify every OpenAI location

--packages names a Lake packages directory (for example <project>/.lake/packages)
whose mathlib and batteries git repositories contain the pinned commits. Without
it the external names already in data/lean_xref.json are kept. Standard library
only, plus the git binary.
"""
from __future__ import annotations

import argparse
import io
import json
import re
import subprocess
import sys
import tarfile
import time
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import lean_render as lr  # noqa: E402

DATA = ROOT / "data"
OUT = DATA / "lean_xref.json"

# ------------------------------------------------------------ library scanner

_MASK = re.compile(r"--[^\n]*|/-|\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\\n])'")
_NONNL = re.compile(r"[^\n]")


def mask(text: str) -> str:
    """The text with comments, strings and character literals blanked, keeping
    every line break so line numbers survive."""
    out = []
    pos = 0
    while True:
        m = _MASK.search(text, pos)
        if not m:
            out.append(text[pos:])
            break
        out.append(text[pos:m.start()])
        end = lr._block_end(text, m.start()) if m.group() == "/-" else m.end()
        out.append(_NONNL.sub(" ", text[m.start():end]))
        pos = end
    return "".join(out)


_ID = lr.IDENT_RE.pattern
_MODS = r"(?:(?:private|protected|noncomputable|partial|unsafe|nonrec|public|meta|scoped|local)\s+)*"
_DECL = re.compile(
    r"^(?P<ind>[ \t]*)(?P<attrs>(?:@\[.*?\]\s*)*)(?P<mods>" + _MODS + r")"
    r"(?P<kw>def|theorem|lemma|abbrev|instance|structure|class\s+inductive|class|inductive|coinductive|axiom|opaque|irreducible_def|alias)\b(?P<rest>.*)$")
_NS = re.compile(r"^\s*namespace\s+(" + _ID + r")")
_SEC = re.compile(r"^\s*(?:@\[.*?\]\s*)*(?:(?:noncomputable|public|private|meta)\s+)*section\b")
_MUTUAL = re.compile(r"^\s*mutual\b")
_END = re.compile(r"^\s*end\b(?:\s+(" + _ID + r"))?")
_EXPORT = re.compile(r"^\s*export\s+(" + _ID + r")\s*\(([^)]*)\)")
_SIMPROC = re.compile(r"^\s*(?:@\[.*?\]\s*)*(?:(?:private|protected|public|meta)\s+)*"
                      r"(?:builtin_)?d?simproc(?:_decl)?\s+(?:↓\s*)?(?:\[[^\]]*\]\s*)?(" + _ID + r")")
_ATTR_CMD = re.compile(r"^\s*attribute\s*\[([^\]]*)\]\s*(.*)$")
_ATTR_ONLY = re.compile(r"^\s*@\[")
_PRIORITY = re.compile(r"^\s*\((?:priority|name)\s*:=[^)]*\)")
_NAME = re.compile(r"\s*(" + _ID + r")")
_FIELD = re.compile(r"^(?P<ind>[ \t]+)(?P<names>" + _ID + r"(?:[ \t]+" + _ID + r")*)[ \t]*(?P<next>::|:(?!=)|\(|\{|\[|⦃)")
_FIELD_GROUP = re.compile(r"^(?P<ind>[ \t]+)[(\[{⦃](?P<names>" + _ID + r"(?:[ \t]+" + _ID + r")*)[ \t]*:")
_CTOR = re.compile(r"(?:^|\s)\|\s*(" + _ID + r")")
_WHERE = re.compile(r"\bwhere\b")
_EXTENDS = re.compile(r"\bextends\b(.*?)(?:\bwhere\b|:=|$)")


def _split_words(s: str):
    return re.findall(r"[A-Z]+(?![a-z])|[A-Z]?[a-z]+|[0-9]+|[^A-Za-z0-9]+", s)


def additive_names(full: str, name_dict: dict, abbrevs: dict):
    """Mathlib's guess of a translated name (Mathlib/Tactic/Translate/GuessName.lean)
    for to_additive and to_dual, approximated: each word is looked up in the
    dictionary, keeping the case of its first letter. Extra guesses are harmless:
    a name is only ever kept when a challenge file uses it."""
    out = []
    parts = full.split(".")
    new = []
    for p in parts:
        words = _split_words(p)
        res = []
        for w in words:
            rep = name_dict.get(w.lower())
            if rep and w.isalpha():
                joined = "".join(rep)
                if w[0].islower():
                    joined = joined.lower() if len(rep) == 1 and w.islower() else joined[0].lower() + joined[1:]
                res.append(joined)
            else:
                res.append(w)
        s = "".join(res)
        for k, v in abbrevs.items():
            if k in s:
                # at the start of a lower-case name a leading acronym is lowered whole: TSupport -> tsupport
                s = s.replace(k, re.sub(r"^[A-Z]+", lambda m: m.group().lower(), v)
                              if s.startswith(k) else v[0].lower() + v[1:])
            s = s.replace(k[0].upper() + k[1:], v)
        new.append(s)
    cand = ".".join(new)
    if cand != full:
        out.append(cand)
    return out


TO_ADDITIVE_DICT = {
    "one": ["Zero"], "mul": ["Add"], "smul": ["VAdd"], "inv": ["Neg"], "div": ["Sub"], "sdiv": ["VSub"],
    "prod": ["Sum"], "hmul": ["HAdd"], "hsmul": ["HVAdd"], "hdiv": ["HSub"], "hpow": ["HSMul"],
    "finprod": ["Finsum"], "tprod": ["TSum"], "pow": ["NSMul"], "npow": ["NSMul"], "zpow": ["ZSMul"],
    "mabs": ["Abs"], "monoid": ["Add", "Monoid"], "submonoid": ["Add", "Submonoid"], "group": ["Add", "Group"],
    "subgroup": ["Add", "Subgroup"], "semigroup": ["Add", "Semigroup"], "torsor": ["Add", "Torsor"],
    "magma": ["Add", "Magma"], "haar": ["Add", "Haar"], "prehaar": ["Add", "Prehaar"], "unit": ["Add", "Unit"],
    "units": ["Add", "Units"], "cyclic": ["Add", "Cyclic"], "commute": ["Add", "Commute"],
    "semiconj": ["Add", "Semiconj"], "conj": ["Add", "Conj"], "commutator": ["Add", "Commutator"],
    "rootable": ["Divisible"], "zpowers": ["ZMultiples"], "powers": ["Multiples"],
    "multipliable": ["Summable"], "square": ["Even"], "conjugates": ["Add", "Conjugates"],
}
TO_DUAL_DICT = {
    "top": ["Bot"], "bot": ["Top"], "inf": ["Sup"], "sup": ["Inf"], "min": ["Max"], "max": ["Min"],
    "lower": ["Upper"], "upper": ["Lower"], "least": ["Greatest"], "greatest": ["Least"], "succ": ["Pred"],
    "pred": ["Succ"], "ioi": ["Iio"], "iio": ["Ioi"], "ici": ["Iic"], "iic": ["Ici"], "ioc": ["Ico"],
    "ico": ["Ioc"], "liminf": ["Limsup"], "limsup": ["Liminf"],
}
TO_DUAL_ABBREV = {}
TRANSLATE = {"to_additive": (TO_ADDITIVE_DICT, None), "to_dual": (TO_DUAL_DICT, None)}


def load_translations(packages: Path, commit: str):
    """The to_additive and to_dual dictionaries exactly as the pinned Mathlib
    defines them (Mathlib/Tactic/Translate/ToAdditive.lean and ToDual.lean)."""
    global TO_ADDITIVE_DICT, TO_ADDITIVE_ABBREV, TO_DUAL_DICT, TO_DUAL_ABBREV
    out = {}
    for attr, path in (("to_additive", "Mathlib/Tactic/Translate/ToAdditive.lean"),
                       ("to_dual", "Mathlib/Tactic/Translate/ToDual.lean")):
        r = subprocess.run(["git", "-C", str(packages / "mathlib"), "show", f"{commit}:{path}"],
                           capture_output=True, text=True)
        if r.returncode:
            continue
        src = r.stdout
        a = src.find("def nameDict")
        b = src.find("def abbreviationDict")
        names = {m.group(1): re.findall(r'"([^"]+)"', m.group(2))
                 for m in re.finditer(r'\(\s*"([^"]+)"\s*,\s*\[([^\]]*)\]\s*\)', src[a:b if b > a else None])}
        abbr = {m.group(1): m.group(2) for m in re.finditer(r'\(\s*"([^"]+)"\s*,\s*"([^"]+)"\s*\)', src[b:]
                                                            if b >= 0 else "")}
        if names:
            out[attr] = (names, abbr)
    if "to_additive" in out:
        TO_ADDITIVE_DICT, TO_ADDITIVE_ABBREV = out["to_additive"]
    if "to_dual" in out:
        TO_DUAL_DICT, TO_DUAL_ABBREV = out["to_dual"]
    return {k: len(v[0]) for k, v in out.items()}


TO_ADDITIVE_ABBREV = {
    "addSupport": "Support", "addTSupport": "TSupport", "addIndicator": "Indicator", "zeroLePart": "PosPart",
    "leZeroPart": "NegPart", "orderOf": "AddOrderOf", "addSingle": "Single", "addAntidiagonal": "Antidiagonal",
    "isEven": "Even", "commAdd": "AddComm", "cancelAdd": "AddCancel",
}


def translated(full: str, attrs: str, attr: str, base):
    """Names a to_additive or to_dual attribute gives the declaration `full`: its
    explicit name when the attribute names one, else the dictionary's guess."""
    out = []
    # every use of the attribute, skipping relatives such as to_additive_ignore_args
    for occ in re.finditer(r"\b" + attr + r"\b(?![_])\??", attrs):
        ta = attrs[occ.end():]
        while True:
            mm = re.match(r"\s*\((?:attr|reorder|relevant_arg|dont_translate)\s*:=", ta)
            if not mm:
                break
            depth = 0
            for q, ch in enumerate(ta):
                if ch == "(":
                    depth += 1
                elif ch == ")":
                    depth -= 1
                    if depth == 0:
                        ta = ta[q + 1:]
                        break
            else:
                break
        ta = ta.strip()
        if ta.startswith("existing") or ta.startswith("self"):
            continue
        mm = re.match(_ID, ta)
        if mm:
            # an explicit name is relative to the declaration's namespace, unless it says _root_
            explicit = mm.group()
            if explicit.startswith("_root_."):
                out.append(explicit[len("_root_."):])
            else:
                out.append(".".join(list(base) + [explicit]) if base else explicit)
            continue
        d, ab = (TO_ADDITIVE_DICT, TO_ADDITIVE_ABBREV) if attr == "to_additive" else (TO_DUAL_DICT, TO_DUAL_ABBREV)
        out += additive_names(full, d, ab)
    return out


def scan_decls(text: str, *, keep_private=False):
    """Declarations of one Lean source file: (full name, line, flags), and the
    aliases its `export` lines create. Flags: 1 constructor, 2 protected."""
    return scan_masked(mask(text), keep_private=keep_private)


def scan_masked(m_text: str, *, keep_private=False):
    lines = m_text.split("\n")
    struct_line = (0,)
    out = []
    aliases = []
    stack = []            # list of (kind, [parts])
    pend_attrs = ""
    attr_open = 0
    struct = None         # (full, decl_indent, where_seen, field_indent, has_ctor)
    induct = None         # (full, decl_indent)

    def ns():
        return [p for _, ps in stack for p in ps]

    def full_of(name, base):
        if name.startswith("_root_."):
            return name[len("_root_."):]
        return ".".join(base + [name]) if base else name

    for i, line in enumerate(lines, 1):
        st = line.strip()
        if not st:
            continue
        ind = len(line) - len(line.lstrip())
        # a multi-line attribute list
        if attr_open:
            pend_attrs += " " + st
            attr_open += st.count("[") - st.count("]")
            if attr_open > 0:
                continue
            attr_open = 0
            tail = pend_attrs[pend_attrs.rfind("]") + 1:].strip() if "]" in pend_attrs else ""
            if not tail:
                continue
            line = " " * ind + tail
            st = tail
        if struct is not None:
            full, dind, seen, find, has_ctor = struct
            if ind <= dind:
                if not has_ctor:
                    out.append((full + ".mk", struct_line[0], 1))
                struct = None
            else:
                if not seen:
                    if _WHERE.search(st):
                        struct = (full, dind, True, find, has_ctor)
                    continue
                if find is None:
                    find = ind
                    struct = (full, dind, True, find, has_ctor)
                if ind == find:
                    m = _FIELD.match(line)
                    if m:
                        names = m.group("names").split()
                        if m.group("next") == "::":
                            out.append((full + "." + names[0], i, 1))
                            struct = (full, dind, True, find, True)
                        elif not st.startswith("deriving"):
                            for nm in (names if m.group("next").startswith(":") else names[:1]):
                                out.append((full + "." + nm, i, 0))
                    else:
                        m = _FIELD_GROUP.match(line)
                        if m:
                            for nm in m.group("names").split():
                                out.append((full + "." + nm, i, 0))
                continue
        if induct is not None:
            full, dind = induct
            if ind <= dind and not st.startswith("|"):
                induct = None
            else:
                for m in _CTOR.finditer(line):
                    out.append((full + "." + m.group(1), i, 1))
                continue
        m = _NS.match(line)
        if m:
            stack.append(("ns", m.group(1).split(".")))
            continue
        if _SEC.match(line) and not _DECL.match(line):
            stack.append(("sec", []))
            continue
        if _MUTUAL.match(line):
            stack.append(("mutual", []))
            continue
        m = _END.match(line)
        if m and (len(st) == 3 or st[3] in " \t"):
            k = len(m.group(1).split(".")) if m.group(1) else 1
            for _ in range(k):
                if stack:
                    stack.pop()
            continue
        m = _SIMPROC.match(line)
        if m:
            out.append((full_of(m.group(1), ns()), i, 0))
            continue
        m = _ATTR_CMD.match(line)
        if m and ("to_additive" in m.group(1) or "to_dual" in m.group(1)):
            base = ns()
            targets = [x for x in m.group(2).split() if lr.IDENT_RE.fullmatch(x)]
            for tname in targets:
                for full_t in (full_of(tname, base), tname):
                    for attr in ("to_additive", "to_dual"):
                        if attr in m.group(1):
                            out.extend((x, i, 0) for x in translated(full_t, m.group(1), attr, base))
            continue
        m = _EXPORT.match(line)
        if m:
            base = ns()
            target = m.group(1)
            for nm in m.group(2).split():
                for k in range(len(base), -1, -1):
                    aliases.append((full_of(nm, base), ".".join(base[:k] + [target, nm]) if not target.startswith("_root_.") else target[7:] + "." + nm))
            continue
        if _ATTR_ONLY.match(line) and not _DECL.match(line):
            depth = st.count("[") - st.count("]")
            pend_attrs = (pend_attrs + " " + st) if pend_attrs else st
            if depth > 0:
                attr_open = depth
            continue
        m = _DECL.match(line)
        if not m:
            pend_attrs = ""
            continue
        attrs = (pend_attrs + " " + m.group("attrs")).strip()
        pend_attrs = ""
        mods = m.group("mods").split()
        kw = m.group("kw").split()[0] if not m.group("kw").startswith("class") else m.group("kw")
        rest = m.group("rest")
        base = ns()
        names = []
        if kw == "alias":
            r = rest.strip()
            if r.startswith("⟨"):
                names = [x.strip() for x in r[1:r.find("⟩")].split(",")
                         if x.strip() != "_" and lr.IDENT_RE.fullmatch(x.strip())]
            else:
                mm = _NAME.match(rest)
                if mm:
                    names = [mm.group(1)]
        else:
            r = rest
            if kw == "instance":
                while True:
                    mm = _PRIORITY.match(r)
                    if not mm:
                        break
                    r = r[mm.end():]
            mm = _NAME.match(r)
            if mm and kw != "example":
                nm = mm.group(1)
                after = r[mm.end():mm.end() + 1]
                if not (kw == "instance" and nm in ("where",)) and nm not in lr.KEYWORDS:
                    names = [nm]
                    if kw == "instance" and after and after not in " \t:({[⦃.":
                        names = []
        if "private" in mods and not keep_private:
            names = []
        prot = 2 if "protected" in mods else 0
        names = [nm for nm in names if nm != "_"]
        for nm in names:
            full = full_of(nm, base)
            out.append((full, i, prot))
            for attr in ("to_additive", "to_dual"):
                if attr in attrs:
                    out.extend((x, i, prot) for x in translated(full, attrs, attr, full.split(".")[:-1]))
            if "to_additive" in attrs and "to_dual" in attrs:
                for add in additive_names(full, TO_ADDITIVE_DICT, TO_ADDITIVE_ABBREV):
                    out.extend((x, i, prot) for x in additive_names(add, TO_DUAL_DICT, TO_DUAL_ABBREV))
            if "@[ext" in attrs or re.search(r"[\[,]\s*ext\b", attrs):
                out.append((full + ".ext", i, 0))
                out.append((full + ".ext_iff", i, 0))
        if names and kw.startswith("class") and "inductive" not in kw or kw == "structure":
            if names:
                full = full_of(names[0], base)
                struct_line = (i,)
                struct = (full, len(line) - len(line.lstrip()), bool(_WHERE.search(rest)), None, False)
                me = _EXTENDS.search(rest)
                if me:
                    depth = 0
                    cur = ""
                    for ch in me.group(1) + ",":
                        if ch in "([{⟨":
                            depth += 1
                        elif ch in ")]}⟩":
                            depth -= 1
                        if ch == "," and depth == 0:
                            mm = re.match(r"\s*(" + _ID + ")", cur)
                            if mm:
                                out.append((full + ".to" + mm.group(1).split(".")[-1], i, 0))
                            cur = ""
                        else:
                            cur += ch
        elif names and ("inductive" in kw or kw == "coinductive"):
            full = full_of(names[0], base)
            induct = (full, len(line) - len(line.lstrip()))
            for mm in _CTOR.finditer(rest):
                out.append((full + "." + mm.group(1), i, 1))
            out.append((full + ".rec", i, 0))
            out.append((full + ".casesOn", i, 0))
        if names and kw == "irreducible_def":
            out.append((full_of(names[0], base) + "_def", i, 0))
    if struct is not None and not struct[4]:
        out.append((struct[0] + ".mk", struct_line[0], 1))
    return out, aliases


# ------------------------------------------------------------ sources

def git_tree(repo: Path, commit: str, prefixes):
    """(path, text) of every .lean file under the prefixes at the commit, read with
    git archive (the working tree is never touched)."""
    cmd = ["git", "-C", str(repo), "archive", "--format=tar", commit, *prefixes]
    proc = subprocess.Popen(cmd, stdout=subprocess.PIPE, stderr=subprocess.PIPE)
    with tarfile.open(fileobj=proc.stdout, mode="r|") as tar:
        for member in tar:
            if member.isfile() and member.name.endswith(".lean"):
                f = tar.extractfile(member)
                yield member.name, f.read().decode("utf-8", errors="replace")
    proc.wait()
    if proc.returncode:
        raise SystemExit(f"git archive failed in {repo}: {proc.stderr.read().decode()[:300]}")


def dir_tree(base: Path, prefixes):
    for p in prefixes:
        root = base / p
        files = [root] if root.is_file() else sorted(root.rglob("*.lean"))
        for f in files:
            yield str(f.relative_to(base)), f.read_text(encoding="utf-8", errors="replace")


def scan_external(packages: Path | None, lean_src: Path | None, manifest: dict, needed: set):
    """Flags of the needed names that Mathlib, Batteries and Lean's core declare,
    and the needed aliases their export lines create, with their targets."""
    flags_all = {}
    alias_all = {}
    sources = {}
    pins = {p["name"]: p["rev"] for p in manifest.get("packages", [])}

    def take(path_texts):
        nfiles = 0
        for _, text in path_texts:
            nfiles += 1
            decls, als = scan_decls(text)
            for full, _line, flags in decls:
                flags_all[full] = flags_all.get(full, 0) | flags
            for a, t in als:
                alias_all.setdefault(a, []).append(t)
        return nfiles

    if lean_src is not None:
        sources["lean"] = {"files": take(dir_tree(lean_src, ["Init", "Init.lean", "Std", "Std.lean",
                                                             "Lean/Meta/Tactic/Simp/BuiltinSimprocs"]))}
    if packages is not None:
        for name, prefixes in (("batteries", ["Batteries", "Batteries.lean"]), ("mathlib", ["Mathlib", "Mathlib.lean"])):
            rev = pins.get(name)
            sources[name] = {"commit": rev, "files": take(git_tree(packages / name, rev, prefixes))}
    found = {n: flags_all[n] for n in needed if n in flags_all}
    aliases = {}
    for a in needed:
        for t in alias_all.get(a, []):
            if t in flags_all:
                aliases[a] = t
                found.setdefault(t, flags_all[t])
                break
    sources["declared_names"] = len(flags_all)
    return found, aliases, sources


# ------------------------------------------------------------ OpenAI library

_IMPORT = re.compile(r"^\s*(?:public\s+|private\s+|meta\s+)*import\s+(?:all\s+)?([\w.«»']+)", re.M)
_HEADER_END = re.compile(r"^(?:namespace|section|open|noncomputable|universe|variable|set_option|def|theorem|lemma|"
                         r"abbrev|structure|class|inductive|instance|@\[|/--)", re.M)


class Library:
    """lean/OAI at the pinned commit: imports and declarations per module, memoised."""

    def __init__(self, lean_root: Path):
        self.root = lean_root
        self._imports = {}
        self._decls = {}
        self._closure = {}

    def path(self, module: str):
        return self.root / (module.replace(".", "/") + ".lean")

    def _text(self, module):
        p = self.path(module)
        return p.read_text(encoding="utf-8", errors="replace") if p.exists() else None

    def _load(self, module, text=None):
        text = self._text(module) if text is None else text
        if text is None:
            self._decls[module] = {}
            return
        ds, _ = scan_decls(text)
        rel = str(self.path(module).relative_to(self.root))
        table = {}
        for full, line, flags in ds:
            table.setdefault(full, (rel, line, flags))
        self._decls[module] = table

    def imports(self, module):
        """The OpenAI modules a module imports, read from its header (imports come
        before any other command in a Lean file)."""
        if module not in self._imports:
            text = self._text(module)
            head = ""
            if text is not None:
                cut = _HEADER_END.search(text)
                head = mask(text[:cut.start()] if cut else text)
            self._imports[module] = [m for m in _IMPORT.findall(head) if m.startswith("OAI")]
        return self._imports[module]

    def closure(self, module):
        if module in self._closure:
            return self._closure[module]
        seen = set()
        todo = [module]
        while todo:
            m = todo.pop()
            if m in seen:
                continue
            seen.add(m)
            todo.extend(self.imports(m))
        self._closure[module] = seen
        return seen

    def decls(self, module):
        if module not in self._decls:
            self._load(module)
        return self._decls[module]

    def find(self, names, modules):
        """Where each name is declared among the modules. A module whose text never
        mentions a wanted name's last component is not scanned."""
        out = {}
        if not names:
            return out
        shorts = sorted({n.rsplit(".", 1)[-1] for n in names}, key=len, reverse=True)
        probe = re.compile("|".join(re.escape(x) for x in shorts))
        for m in sorted(modules):
            if m not in self._decls:
                text = self._text(m)
                if text is None or not probe.search(text):
                    continue
                self._load(m, text)
            table = self._decls[m]
            for n in names:
                if n not in out and n in table:
                    out[n] = table[n]
        return out


# ------------------------------------------------------------ main

def build(args):
    t0 = time.time()
    statements = json.loads((DATA / "statements.json").read_text(encoding="utf-8"))
    summary = json.loads((DATA / "summary.json").read_text(encoding="utf-8"))
    commit = summary["upstream"]["commit"]
    cfg = json.loads((ROOT / "site" / "config.json").read_text(encoding="utf-8"))
    upstream = Path(args.upstream or (ROOT / cfg.get("upstream_checkout", "../openai-math-upstream"))).resolve()
    lean_root = upstream / "lean"
    head = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    if head != commit:
        raise SystemExit(f"{upstream} is at {head or 'no commit'}, not the pinned {commit}")
    manifest = json.loads((lean_root / "lake-manifest.json").read_text(encoding="utf-8"))
    toolchain = (lean_root / "lean-toolchain").read_text(encoding="utf-8").strip()

    dicts = load_translations(Path(args.packages).expanduser(), {p["name"]: p["rev"] for p in manifest["packages"]}["mathlib"]) \
        if args.packages else {}
    if dicts:
        print(f"translation dictionaries from the pinned Mathlib: {dicts}", file=sys.stderr)
    lib = Library(lean_root)
    needed = set()
    per = {}
    for s in statements:
        lf = lr.LeanFile(s["lean"])
        cands = lr.reference_candidates(lf)
        needed |= cands
        per[s["id"]] = (lf, cands)
    print(f"read {len(statements)} challenge files: {len(needed):,} candidate names ({time.time() - t0:.0f}s)", file=sys.stderr)

    files: list[str] = []
    file_ix: dict[str, int] = {}

    def fid(path):
        if path not in file_ix:
            file_ix[path] = len(files)
            files.append(path)
        return file_ix[path]

    st_out = {}
    n_lib = n_scope = 0
    for s in statements:
        sid = s["id"]
        lf, cands = per[sid]
        entry = {}
        # names the file takes from the OpenAI modules it imports
        own = [m for m in s.get("non_mathlib_imports") or [] if m.startswith("OAI")]
        if own:
            mods = set()
            for m in own:
                mods |= lib.closure(m)
            hits = lib.find({c for c in cands if c.startswith("OAI.")}, mods)
            if hits:
                entry["scope"] = {k: [fid(v[0]), v[1], v[2]] for k, v in sorted(hits.items())}
                n_scope += len(hits)
        # each local declaration's counterpart in the solution module's import closure
        sol = s["comparator"].get("solution_module")
        if sol:
            local = {full for full, (_di, _line, kind, _p) in lf.local_names.items() if kind == "decl"}
            local |= set(s["comparator"].get("definition_names") or [])
            hits = lib.find(local, lib.closure(sol))
            if hits:
                entry["library"] = {k: [fid(v[0]), v[1]] for k, v in sorted(hits.items())}
                n_lib += len(hits)
        if entry:
            st_out[sid] = entry
    print(f"OpenAI library: {n_lib:,} counterparts, {n_scope:,} imported names ({time.time() - t0:.0f}s)", file=sys.stderr)

    old = {}
    if OUT.exists():
        try:
            old = json.loads(OUT.read_text(encoding="utf-8"))
        except ValueError:
            old = {}
    if args.packages:
        lean_src = Path(args.lean_src).expanduser() if args.lean_src else pick_lean_src(toolchain)
        ext_needed = {n for n in needed if not n.startswith("OAI.")}
        external, aliases, sources = scan_external(Path(args.packages).expanduser(), lean_src, manifest, ext_needed)
        sources["lean"] = dict(sources.get("lean") or {}, pinned=toolchain.split(":")[-1],
                               read=lean_src.parent.parent.name.split("---")[-1] if lean_src else None)
        print(f"external: {len(external):,} names, {len(aliases):,} aliases ({time.time() - t0:.0f}s)", file=sys.stderr)
    else:
        external, aliases, sources = old.get("external", {}), old.get("aliases", {}), old.get("sources", {})
        print("no --packages: keeping the external names already recorded", file=sys.stderr)

    out = {
        "_note": "Generated by scripts/build_lean_xref.py; do not edit by hand.",
        "upstream_commit": commit,
        "sources": sources,
        "counts": {"statements": len(statements), "library_counterparts": n_lib, "imported_names": n_scope,
                   "external_names": len(external), "aliases": len(aliases)},
        "files": files,
        "statements": st_out,
        "external": dict(sorted(external.items())),
        "aliases": dict(sorted(aliases.items())),
    }
    tmp = OUT.with_suffix(".json.tmp")
    tmp.write_text(json.dumps(out, ensure_ascii=False, indent=1) + "\n", encoding="utf-8")   # as data/*.json
    tmp.replace(OUT)          # a reader never sees a half-written file
    print(f"wrote {OUT.relative_to(ROOT)} ({OUT.stat().st_size / 1e6:.2f} MB) in {time.time() - t0:.0f}s", file=sys.stderr)
    return 0


def pick_lean_src(toolchain: str):
    """The toolchain's own sources when installed, else the nearest installed version."""
    base = Path.home() / ".elan" / "toolchains"
    want = toolchain.split(":")[-1]
    exact = base / ("leanprover--lean4---" + want) / "src" / "lean"
    if exact.is_dir():
        return exact

    def ver(s):
        m = re.match(r"v?(\d+)\.(\d+)\.(\d+)", s)
        return tuple(int(x) for x in m.groups()) if m else (0, 0, 0)
    have = [p for p in base.glob("leanprover--lean4---v*") if (p / "src" / "lean" / "Init").is_dir()]
    if not have:
        return None
    w = ver(want)
    have.sort(key=lambda p: (abs((ver(p.name.split("---")[-1])[0] - w[0]) * 1000 + ver(p.name.split("---")[-1])[1] - w[1]), p.name))
    return have[0] / "src" / "lean"


_CHECK_FIELD = re.compile(r"^\s+(?:" + _ID + r"\s+)*" + _ID + r"\s*(?::|::|\(|\{|\[)")   # a structure field or constructor


def check(args):
    """Every OpenAI location names a file that exists in the pinned checkout and a
    line that declares that name."""
    x = json.loads(OUT.read_text(encoding="utf-8"))
    cfg = json.loads((ROOT / "site" / "config.json").read_text(encoding="utf-8"))
    upstream = Path(args.upstream or (ROOT / cfg.get("upstream_checkout", "../openai-math-upstream"))).resolve()
    head = subprocess.run(["git", "-C", str(upstream), "rev-parse", "HEAD"], capture_output=True, text=True).stdout.strip()
    problems = []
    if head != x["upstream_commit"]:
        problems.append(f"checkout at {head}, xref at {x['upstream_commit']}")
    cache = {}
    n = 0
    for sid, entry in x["statements"].items():
        for section in ("library", "scope"):
            for name, loc in (entry.get(section) or {}).items():
                n += 1
                path = x["files"][loc[0]]
                line = loc[1]
                if path not in cache:
                    p = upstream / "lean" / path
                    cache[path] = p.read_text(encoding="utf-8", errors="replace").split("\n") if p.exists() else None
                lines = cache[path]
                short = name.split(".")[-1]
                if lines is None:
                    problems.append(f"{sid}: {name}: {path} does not exist")
                elif not (1 <= line <= len(lines)):
                    problems.append(f"{sid}: {name}: {path} has no line {line}")
                elif not re.search(r"(?<![\w'])" + re.escape(short) + r"(?![\w'])", lines[line - 1]):
                    problems.append(f"{sid}: {name}: line {line} of {path} does not name {short}")
                elif not (_DECL.match(lines[line - 1]) or _CHECK_FIELD.match(lines[line - 1])
                          or re.match(r"^\s*\|\s*" + re.escape(short) + r"\b", lines[line - 1])):
                    problems.append(f"{sid}: {name}: line {line} of {path} names {short} without declaring it")
    for p in problems[:30]:
        print(p)
    print(f"lean_xref: {n:,} OpenAI locations checked against {upstream} at {head[:12]}; "
          f"{'OK' if not problems else str(len(problems)) + ' problems'}")
    return 1 if problems else 0


def main():
    ap = argparse.ArgumentParser(description=__doc__.split("\n\n")[0])
    ap.add_argument("--upstream", help="the openai/math checkout at the pinned commit (default: site/config.json)")
    ap.add_argument("--packages", help="a Lake packages directory holding the pinned mathlib and batteries commits")
    ap.add_argument("--lean-src", help="Lean core sources (the src/lean directory of a toolchain)")
    ap.add_argument("--check", action="store_true", help="verify every OpenAI location and exit")
    args = ap.parse_args()
    return check(args) if args.check else build(args)


if __name__ == "__main__":
    sys.exit(main())
