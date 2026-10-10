#!/usr/bin/env python3
"""Check the contribution files under contributions/.

Usage:
    python3 scripts/check_contributions.py                 check every contribution
    python3 scripts/check_contributions.py FILE [FILE ...]  check only these files
    python3 scripts/check_contributions.py --self-test     check the templates and the checker itself

Options:
    --no-data   skip the cross-checks against data/*.json
    --strict    count warnings as errors
    --json      print the findings as JSON

The four file formats (explanation, statement check, credit, replay receipt) are
described in contributions/README.md. The checker reads the frontmatter of each
Markdown file with a small built-in parser for the simple YAML used there, checks
kinds, required fields, allowed values, dates and identifiers, checks that each
file sits at the path its frontmatter implies, and, when data/*.json exist, checks
that every family, statement and manuscript it names exists.

Standard library only; Python 3.10 or newer.
Exit status: 0 when there are no errors, 1 when there are errors, 2 for a usage error.
"""
from __future__ import annotations

import argparse
import datetime as _dt
import gzip
import hashlib
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
CONTRIB = ROOT / "contributions"
TEMPLATES = CONTRIB / "_templates"
DATA = ROOT / "data"

PLACEHOLDER = "[replace:"
HANDLE_PLACEHOLDER = "your-github-handle"

STATUSES = ("draft", "ready-for-review", "reviewed")
VERDICTS = ("matches", "stronger-than-paper", "weaker-than-paper", "different", "cannot-tell")
RELATIONS = ("first-appeared-in", "uses", "special-case-of", "same-argument-as", "generalises")
RESULTS = ("accepted", "rejected", "error")
CHECK_HEADINGS = ("What the paper says", "What the Lean statement says", "Differences", "Why this verdict")

MAX_LOG_BYTES = 2_000_000
MAX_ASSET_BYTES = 5_000_000

HANDLE_RE = re.compile(r"^[A-Za-z0-9](?:[A-Za-z0-9]|-(?=[A-Za-z0-9])){0,38}$")
FAMILY_RE = re.compile(r"^\d{3}$")
STATEMENT_RE = re.compile(r"^[A-Za-z][A-Za-z0-9_]*$")
MANUSCRIPT_RE = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._()\-]*$")
SLUG_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")
DATE_RE = re.compile(r"^\d{4}-\d{2}-\d{2}$")
ORCID_RE = re.compile(r"^\d{4}-\d{4}-\d{4}-\d{3}[\dX]$")
URL_RE = re.compile(r"^https?://\S+$")
DOI_RE = re.compile(r"^10\.\d{4,9}/\S+$")
ARXIV_RE = re.compile(r"^(?:\d{4}\.\d{4,5}|[a-z\-]+(?:\.[A-Z]{2})?/\d{7})(?:v\d+)?$")
HEX40_RE = re.compile(r"^[0-9a-f]{40}$")
COMMIT_RE = re.compile(r"^[0-9a-f]{7,40}$")
SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
REPLAY_STEM_RE = re.compile(r"^(?P<handle>.+)-(?P<date>\d{8})$")


# --------------------------------------------------------------------------
# A small parser for the simple YAML used in frontmatter.
#
# Supported: "key: value" lines, nested mappings, block lists ("- item"),
# lists of mappings, flow lists [a, b] and flow mappings {a: b}, single- and
# double-quoted strings, block scalars (| and >), and comments. Plain values
# are typed the way common YAML parsers type them (numbers, true/false/yes/no,
# null), so the checker sees what other tools will see.
# --------------------------------------------------------------------------


class YamlError(Exception):
    def __init__(self, message: str, line: int):
        super().__init__(message)
        self.message = message
        self.line = line


_KEY_RE = re.compile(r"^([A-Za-z_][A-Za-z0-9_\-]*)\s*:(?:[ \t]+(.*))?$")
_BLOCK_INDICATORS = ("|", "|-", "|+", ">", ">-", ">+")
_TRUE = {"true", "yes", "on"}
_FALSE = {"false", "no", "off"}
_INT_RE = re.compile(r"^[-+]?\d+$")
_FLOAT_RE = re.compile(r"^[-+]?(?:\d+\.\d*|\.\d+)(?:[eE][-+]?\d+)?$")


def _plain_value(s: str):
    low = s.lower()
    if s == "~" or low == "null":
        return None
    if low in _TRUE:
        return True
    if low in _FALSE:
        return False
    if _INT_RE.match(s):
        return int(s)
    if _FLOAT_RE.match(s):
        return float(s)
    return s


def _parse_double_quoted(s: str, line: int):
    """s starts with a double quote. Return (value, index after the closing quote)."""
    out = []
    i = 1
    escapes = {'"': '"', "\\": "\\", "/": "/", "n": "\n", "t": "\t", "r": "\r", "0": "\0", " ": " "}
    while i < len(s):
        ch = s[i]
        if ch == '"':
            return "".join(out), i + 1
        if ch == "\\":
            if i + 1 >= len(s):
                break
            nxt = s[i + 1]
            if nxt in escapes:
                out.append(escapes[nxt])
                i += 2
                continue
            if nxt == "u" and re.match(r"^[0-9a-fA-F]{4}$", s[i + 2:i + 6]):
                out.append(chr(int(s[i + 2:i + 6], 16)))
                i += 6
                continue
            raise YamlError(f"unknown escape '\\{nxt}' inside double quotes; write \\\\ for a backslash", line)
        out.append(ch)
        i += 1
    raise YamlError("a double-quoted value has no closing quote on this line", line)


def _parse_single_quoted(s: str, line: int):
    out = []
    i = 1
    while i < len(s):
        ch = s[i]
        if ch == "'":
            if i + 1 < len(s) and s[i + 1] == "'":
                out.append("'")
                i += 2
                continue
            return "".join(out), i + 1
        out.append(ch)
        i += 1
    raise YamlError("a single-quoted value has no closing quote on this line", line)


def _expect_comment_only(rest: str, line: int) -> None:
    rest = rest.strip()
    if rest and not rest.startswith("#"):
        raise YamlError(f"unexpected text after the value: {rest!r}", line)


def _split_flow(inner: str, line: int) -> list[str]:
    """Split the inside of [ ] or { } on commas that are outside quotes."""
    parts, buf, quote = [], [], None
    i = 0
    while i < len(inner):
        ch = inner[i]
        if quote:
            buf.append(ch)
            if ch == quote:
                if quote == "'" and i + 1 < len(inner) and inner[i + 1] == "'":
                    buf.append("'")
                    i += 2
                    continue
                quote = None
            elif ch == "\\" and quote == '"' and i + 1 < len(inner):
                buf.append(inner[i + 1])
                i += 2
                continue
        elif ch in "\"'":
            quote = ch
            buf.append(ch)
        elif ch in "[]{}":
            raise YamlError("lists inside lists are not supported here; write one item per line instead", line)
        elif ch == ",":
            parts.append("".join(buf))
            buf = []
        else:
            buf.append(ch)
        i += 1
    if quote:
        raise YamlError("a quoted value inside brackets has no closing quote", line)
    parts.append("".join(buf))
    if len(parts) == 1 and not parts[0].strip():
        return []
    return parts


def _find_flow_end(s: str, close: str, line: int) -> int:
    quote = None
    i = 1
    while i < len(s):
        ch = s[i]
        if quote:
            if ch == quote:
                if quote == "'" and i + 1 < len(s) and s[i + 1] == "'":
                    i += 2
                    continue
                quote = None
            elif ch == "\\" and quote == '"':
                i += 2
                continue
        elif ch in "\"'":
            quote = ch
        elif ch == close:
            return i
        i += 1
    raise YamlError(f"no closing '{close}' on this line", line)


class _Parser:
    def __init__(self, text: str, first_line: int = 1):
        self.lines = text.split("\n")
        self.first = first_line
        self.i = 0
        self.line_of: dict[str, int] = {}
        self.warnings: list[tuple[int, str]] = []

    # -- helpers --------------------------------------------------------
    def lineno(self, idx: int | None = None) -> int:
        return self.first + (self.i if idx is None else idx)

    def _blank(self, idx: int) -> bool:
        s = self.lines[idx].strip()
        return s == "" or s.startswith("#")

    def _skip_blank(self) -> None:
        while self.i < len(self.lines) and self._blank(self.i):
            self.i += 1

    def _indent(self, idx: int) -> int:
        line = self.lines[idx]
        stripped = line.lstrip(" ")
        if stripped.startswith("\t"):
            raise YamlError("indent with spaces; a tab at the start of a line is not allowed", self.lineno(idx))
        return len(line) - len(stripped)

    @staticmethod
    def _is_item(content: str) -> bool:
        return content == "-" or content.startswith("- ")

    # -- values on one line ---------------------------------------------
    def _inline(self, text: str, line: int):
        s = text.strip()
        if s == "" or s.startswith("#"):
            return None
        if s[0] == '"':
            value, end = _parse_double_quoted(s, line)
            _expect_comment_only(s[end:], line)
            return value
        if s[0] == "'":
            value, end = _parse_single_quoted(s, line)
            _expect_comment_only(s[end:], line)
            return value
        if s[0] == "[":
            end = _find_flow_end(s, "]", line)
            parts = _split_flow(s[1:end], line)
            _expect_comment_only(s[end + 1:], line)
            return [self._flow_scalar(part, line) for part in parts]
        if s[0] == "{":
            end = _find_flow_end(s, "}", line)
            parts = _split_flow(s[1:end], line)
            _expect_comment_only(s[end + 1:], line)
            result = {}
            for part in parts:
                m = re.match(r"^\s*([A-Za-z_][A-Za-z0-9_\-]*)\s*:\s*(.*)$", part)
                if not m:
                    raise YamlError(f"expected 'field: value' inside braces, found {part.strip()!r}", line)
                if m.group(1) in result:
                    raise YamlError(f"field '{m.group(1)}' appears twice", line)
                result[m.group(1)] = self._flow_scalar(m.group(2), line)
            return result
        return self._plain(s, line)

    def _flow_scalar(self, part: str, line: int):
        p = part.strip()
        if p == "":
            raise YamlError("empty item between commas", line)
        if p[0] == '"':
            value, end = _parse_double_quoted(p, line)
            _expect_comment_only(p[end:], line)
            return value
        if p[0] == "'":
            value, end = _parse_single_quoted(p, line)
            _expect_comment_only(p[end:], line)
            return value
        return self._plain(p, line, in_flow=True)

    def _plain(self, s: str, line: int, in_flow: bool = False):
        cut = s.find(" #")
        if cut != -1:
            comment = s[cut + 2:]
            if comment[:1].isalnum():
                self.warnings.append((line, "everything after ' #' is read as a comment; if it belongs to "
                                            "the value, put the whole value in double quotes"))
            s = s[:cut].rstrip()
        if s[:1] in ("&", "*", "!", "%", "@", "`", "|", ">"):
            raise YamlError(f"a value cannot start with {s[0]!r}; put the whole value in double quotes", line)
        if s.startswith("- ") or s == "-":
            raise YamlError("a list item must start on its own line, below the field name", line)
        if ": " in s or s.endswith(":"):
            raise YamlError("this value contains ': '; put the whole value in double quotes", line)
        return _plain_value(s)

    # -- blocks ------------------------------------------------------------
    def parse(self):
        self._skip_blank()
        if self.i >= len(self.lines):
            return {}
        if self._indent(self.i) != 0:
            raise YamlError("the first field must start at the beginning of the line", self.lineno())
        if self._is_item(self.lines[self.i]):
            raise YamlError("the frontmatter must be a set of 'field: value' lines", self.lineno())
        value = self._mapping(0, "")
        self._skip_blank()
        if self.i < len(self.lines):
            raise YamlError("unexpected text; check the indentation of this line", self.lineno())
        return value

    def _block(self, indent: int, path: str):
        content = self.lines[self.i][indent:]
        if self._is_item(content):
            return self._list(indent, path)
        return self._mapping(indent, path)

    def _mapping(self, indent: int, path: str) -> dict:
        result: dict = {}
        while True:
            self._skip_blank()
            if self.i >= len(self.lines):
                break
            ind = self._indent(self.i)
            if ind < indent:
                break
            if ind > indent:
                raise YamlError("unexpected indentation; line it up with the field above", self.lineno())
            raw = self.lines[self.i][ind:]
            if self._is_item(raw):
                raise YamlError("a list item needs a field name on the line above it", self.lineno())
            m = _KEY_RE.match(raw)
            if not m:
                raise YamlError(f"expected 'field: value', found {raw.strip()!r}", self.lineno())
            key, rest = m.group(1), m.group(2) or ""
            keypath = f"{path}.{key}" if path else key
            line = self.lineno()
            if key in result:
                raise YamlError(f"field '{key}' appears twice", line)
            self.line_of[keypath] = line
            self.i += 1
            stripped = rest.strip()
            if stripped == "" or stripped.startswith("#"):
                self._skip_blank()
                if self.i < len(self.lines):
                    nind = self._indent(self.i)
                    ncontent = self.lines[self.i][nind:]
                    if nind > ind:
                        result[key] = self._block(nind, keypath)
                        continue
                    if nind == ind and self._is_item(ncontent):
                        result[key] = self._list(ind, keypath)
                        continue
                result[key] = None
                continue
            indicator = stripped.split(" #")[0].strip() if stripped[0] not in "\"'" else ""
            if indicator in _BLOCK_INDICATORS:
                result[key] = self._block_scalar(ind, indicator)
                continue
            result[key] = self._inline(rest, line)
        return result

    def _list(self, indent: int, path: str) -> list:
        items: list = []
        while True:
            self._skip_blank()
            if self.i >= len(self.lines):
                break
            ind = self._indent(self.i)
            if ind < indent:
                break
            if ind > indent:
                raise YamlError("unexpected indentation inside a list", self.lineno())
            raw = self.lines[self.i][ind:]
            if not self._is_item(raw):
                break
            itempath = f"{path}[{len(items)}]"
            line = self.lineno()
            self.line_of[itempath] = line
            after = raw[1:]
            stripped = after.lstrip(" ")
            if stripped == "" or stripped.startswith("#"):
                self.i += 1
                self._skip_blank()
                if self.i >= len(self.lines) or self._indent(self.i) <= ind:
                    items.append(None)
                    continue
                items.append(self._block(self._indent(self.i), itempath))
                continue
            col = ind + 1 + (len(after) - len(stripped))
            if stripped[0] not in "\"'[{" and _KEY_RE.match(stripped):
                self.lines[self.i] = " " * col + stripped
                items.append(self._mapping(col, itempath))
                continue
            if stripped.split(" #")[0].strip() in _BLOCK_INDICATORS:
                raise YamlError("a block of text cannot be a list item here; use a quoted value", line)
            items.append(self._inline(stripped, line))
            self.i += 1
        return items

    def _block_scalar(self, parent_indent: int, indicator: str) -> str:
        style, chomp = indicator[0], indicator[1:]
        collected: list[str] = []
        content_indent = None
        while self.i < len(self.lines):
            line = self.lines[self.i]
            if line.strip() == "":
                collected.append("")
                self.i += 1
                continue
            ind = len(line) - len(line.lstrip(" "))
            if content_indent is None:
                if ind <= parent_indent:
                    break
                content_indent = ind
            if ind < content_indent:
                break
            collected.append(line[content_indent:])
            self.i += 1
        trailing = 0
        while collected and collected[-1] == "":
            collected.pop()
            trailing += 1
        if style == "|":
            text = "\n".join(collected)
        else:
            paragraphs, current = [], []
            for item in collected:
                if item == "":
                    paragraphs.append(" ".join(current))
                    current = []
                else:
                    current.append(item.strip())
            paragraphs.append(" ".join(current))
            text = "\n".join(paragraphs)
        if not collected:
            return ""
        if chomp == "-":
            return text
        if chomp == "+":
            return text + "\n" * (1 + trailing)
        return text + "\n"


def parse_yaml(text: str, first_line: int = 1):
    """Parse simple YAML. Returns (value, line_of, warnings). Raises YamlError."""
    parser = _Parser(text.replace("\r\n", "\n"), first_line)
    value = parser.parse()
    return value, parser.line_of, parser.warnings


# --------------------------------------------------------------------------
# Findings
# --------------------------------------------------------------------------


class Finding:
    __slots__ = ("level", "path", "line", "message")

    def __init__(self, level: str, path: str, line: int | None, message: str):
        self.level, self.path, self.line, self.message = level, path, line, message

    def text(self) -> str:
        where = self.path + (f":{self.line}" if self.line else "")
        return f"{where}: {self.level}: {self.message}"

    def as_dict(self) -> dict:
        return {"level": self.level, "file": self.path, "line": self.line, "message": self.message}


class Report:
    def __init__(self, path: str):
        self.path = path
        self.findings: list[Finding] = []

    def error(self, message: str, line: int | None = None) -> None:
        self.findings.append(Finding("error", self.path, line, message))

    def warn(self, message: str, line: int | None = None) -> None:
        self.findings.append(Finding("warning", self.path, line, message))

    @property
    def errors(self) -> list[Finding]:
        return [f for f in self.findings if f.level == "error"]


# --------------------------------------------------------------------------
# Data from data/*.json (optional)
# --------------------------------------------------------------------------


def _load_index(path: Path, key: str):
    """Return ({id: record}, note). Accepts a list of records with "id", a dict
    keyed by id, or a dict holding such a list under `key`."""
    rel = path.relative_to(ROOT) if path.is_relative_to(ROOT) else path
    if not path.is_file():
        return None, f"{rel} not found, so ids from it are not checked (run scripts/build_data.py)"
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError) as exc:
        return None, f"could not read {rel} ({exc}), so ids from it are not checked"
    items = raw
    if isinstance(raw, dict):
        if isinstance(raw.get(key), list):
            items = raw[key]
        elif raw and all(isinstance(v, dict) for v in raw.values()):
            return {str(k): v for k, v in raw.items()}, None
    if isinstance(items, list):
        index = {}
        for item in items:
            if isinstance(item, dict) and item.get("id") is not None:
                index[str(item["id"])] = item
        return index, None
    return None, f"{rel} has an unexpected shape, so ids from it are not checked"


class Data:
    def __init__(self, root: Path = ROOT, enabled: bool = True):
        self.notes: list[str] = []
        self.families = self.manuscripts = self.statements = None
        self.pinned_commit = None
        if not enabled:
            return
        for attr, name in (("families", "families"), ("manuscripts", "manuscripts"), ("statements", "statements")):
            index, note = _load_index(root / "data" / f"{name}.json", name)
            setattr(self, attr, index)
            if note:
                self.notes.append(note)
        upstream = root / "upstream.json"
        if upstream.is_file():
            try:
                commit = json.loads(upstream.read_text(encoding="utf-8")).get("commit")
                if isinstance(commit, str) and HEX40_RE.match(commit):
                    self.pinned_commit = commit
            except (OSError, ValueError):
                pass

    @staticmethod
    def _ids(record: dict | None, key: str) -> list[str]:
        if not isinstance(record, dict):
            return []
        value = record.get(key)
        if isinstance(value, list):
            return [str(v) for v in value]
        if isinstance(value, str):
            return [value]
        return []


# --------------------------------------------------------------------------
# Field checks
# --------------------------------------------------------------------------


class Ctx:
    def __init__(self, report: Report, line_of: dict[str, int], data: Data, template: bool):
        self.r = report
        self.line_of = line_of
        self.data = data
        self.template = template

    def line(self, path: str) -> int | None:
        while path:
            if path in self.line_of:
                return self.line_of[path]
            if "[" in path and path.endswith("]"):
                path = path[: path.rfind("[")]
            elif "." in path:
                path = path[: path.rfind(".")]
            else:
                break
        return self.line_of.get(path)


def _is_placeholder(value) -> bool:
    return isinstance(value, str) and (PLACEHOLDER in value or value.strip() == HANDLE_PLACEHOLDER)


def _describe(value) -> str:
    if value is None:
        return "nothing"
    if isinstance(value, bool):
        return f"the yes/no value {str(value).lower()}"
    if isinstance(value, (int, float)):
        return f"the number {value}"
    if isinstance(value, list):
        return "a list"
    if isinstance(value, dict):
        return "a group of fields"
    return repr(value)


def text_field(max_len: int | None = None):
    def check(value, ctx: Ctx, label: str, path: str) -> None:
        if not isinstance(value, str) or not value.strip():
            ctx.r.error(f"{label} must be text (found {_describe(value)})", ctx.line(path))
            return
        if max_len and len(value.strip()) > max_len:
            ctx.r.error(f"{label} is longer than {max_len} characters", ctx.line(path))
    return check


def enum_field(values: tuple[str, ...]):
    def check(value, ctx: Ctx, label: str, path: str) -> None:
        if not isinstance(value, str) or value.strip() not in values:
            ctx.r.error(f"{label} must be one of: {', '.join(values)} (found {_describe(value)})", ctx.line(path))
    return check


def kind_field(expected: str):
    def check(value, ctx: Ctx, label: str, path: str) -> None:
        if value != expected:
            ctx.r.error(f"kind must be '{expected}' for a file in this folder (found {_describe(value)})",
                        ctx.line(path))
    return check


def handle_field(value, ctx: Ctx, label: str, path: str) -> None:
    if not isinstance(value, str):
        ctx.r.error(f"{label} must be a GitHub handle (found {_describe(value)})", ctx.line(path))
        return
    if value.startswith("@"):
        ctx.r.error(f"{label}: write the GitHub handle without the @", ctx.line(path))
        return
    if not HANDLE_RE.match(value):
        ctx.r.error(f"{label} is not a valid GitHub handle: {value!r}", ctx.line(path))


def family_field(value, ctx: Ctx, label: str, path: str) -> None:
    if isinstance(value, int) and not isinstance(value, bool):
        ctx.r.error(f'{label} must be three digits in double quotes, for example family: "{value:03d}" '
                    "(without quotes, YAML reads it as a number and can drop leading zeros)", ctx.line(path))
        return
    if not isinstance(value, str) or not FAMILY_RE.match(value):
        ctx.r.error(f'{label} must be a three-digit family id in double quotes, such as "159" '
                    f"(found {_describe(value)})", ctx.line(path))
        return
    families = ctx.data.families
    if families is not None and value not in families:
        ctx.r.error(f"{label}: there is no family {value} in data/families.json", ctx.line(path))


def statement_field(value, ctx: Ctx, label: str, path: str) -> None:
    if not isinstance(value, str) or not STATEMENT_RE.match(value):
        ctx.r.error(f"{label} must be a statement id such as ErdosReciprocal (found {_describe(value)})",
                    ctx.line(path))
        return
    statements = ctx.data.statements
    if statements is not None and value not in statements:
        ctx.r.error(f"{label}: there is no statement {value} in data/statements.json (ids are case-sensitive)",
                    ctx.line(path))


def manuscript_field(value, ctx: Ctx, label: str, path: str) -> None:
    if not isinstance(value, str) or not MANUSCRIPT_RE.match(value):
        ctx.r.error(f"{label} must be a manuscript id, the folder name under preprints/ upstream "
                    f"(found {_describe(value)})", ctx.line(path))
        return
    manuscripts = ctx.data.manuscripts
    if manuscripts is not None and value not in manuscripts:
        ctx.r.error(f"{label}: there is no manuscript {value} in data/manuscripts.json", ctx.line(path))


def date_field(value, ctx: Ctx, label: str, path: str) -> None:
    if isinstance(value, _dt.date):
        value = value.isoformat()
    if not isinstance(value, str) or not DATE_RE.match(value):
        ctx.r.error(f"{label} must be a date written YYYY-MM-DD (found {_describe(value)})", ctx.line(path))
        return
    try:
        day = _dt.date.fromisoformat(value)
    except ValueError:
        ctx.r.error(f"{label} is not a real calendar date: {value}", ctx.line(path))
        return
    if day > _dt.date.today() + _dt.timedelta(days=2):
        ctx.r.warn(f"{label} {value} is in the future", ctx.line(path))


def orcid_field(value, ctx: Ctx, label: str, path: str) -> None:
    if not isinstance(value, str):
        ctx.r.error(f"{label} must be an ORCID iD such as 0000-0002-1825-0097", ctx.line(path))
        return
    bare = value.strip()
    for prefix in ("https://orcid.org/", "http://orcid.org/"):
        if bare.startswith(prefix):
            bare = bare[len(prefix):]
    if not ORCID_RE.match(bare):
        ctx.r.error(f"{label} must be an ORCID iD such as 0000-0002-1825-0097 (found {value!r})", ctx.line(path))
        return
    digits = bare.replace("-", "")
    total = 0
    for ch in digits[:-1]:
        total = (total + int(ch)) * 2
    check = (12 - total % 11) % 11
    if digits[-1] != ("X" if check == 10 else str(check)):
        ctx.r.error(f"{label} {value} fails the ORCID checksum; check for a typing error", ctx.line(path))


def url_field(value, ctx: Ctx, label: str, path: str) -> None:
    if not isinstance(value, str) or not URL_RE.match(value.strip()):
        ctx.r.error(f"{label} must be a web address starting with https:// (found {_describe(value)})",
                    ctx.line(path))


def doi_field(value, ctx: Ctx, label: str, path: str) -> None:
    if not isinstance(value, str):
        ctx.r.error(f"{label} must be a DOI such as 10.4007/annals.2008.167.481", ctx.line(path))
        return
    v = value.strip()
    if v.lower().startswith(("https://doi.org/", "http://doi.org/", "doi:", "https://dx.doi.org/")):
        ctx.r.error(f"{label}: write the bare DOI, starting with 10., without a prefix (found {value!r})",
                    ctx.line(path))
    elif not DOI_RE.match(v):
        ctx.r.error(f"{label} must be a DOI such as 10.4007/annals.2008.167.481 (found {value!r})", ctx.line(path))


def arxiv_field(value, ctx: Ctx, label: str, path: str) -> None:
    if isinstance(value, float):
        ctx.r.error(f'{label}: put the arXiv id in double quotes, for example arxiv: "2301.01234", '
                    "so it is not read as a number", ctx.line(path))
        return
    if not isinstance(value, str):
        ctx.r.error(f"{label} must be an arXiv id such as 2301.01234 (found {_describe(value)})", ctx.line(path))
        return
    v = value.strip()
    if v.lower().startswith(("arxiv:", "https://arxiv.org/")):
        ctx.r.error(f"{label}: write the bare arXiv id, such as 2301.01234, without a prefix", ctx.line(path))
    elif not ARXIV_RE.match(v):
        ctx.r.error(f"{label} must be an arXiv id such as 2301.01234 or math/0501001 (found {value!r})",
                    ctx.line(path))


def year_field(value, ctx: Ctx, label: str, path: str) -> None:
    year = None
    if isinstance(value, int) and not isinstance(value, bool):
        year = value
    elif isinstance(value, str) and re.match(r"^\d{4}$", value.strip()):
        year = int(value)
    if year is None or not 1500 <= year <= _dt.date.today().year + 1:
        ctx.r.error(f"{label} must be a four-digit year (found {_describe(value)})", ctx.line(path))


def number_field(minimum: float, strictly: bool = False):
    def check(value, ctx: Ctx, label: str, path: str) -> None:
        if isinstance(value, bool) or not isinstance(value, (int, float)):
            ctx.r.error(f"{label} must be a number written without quotes (found {_describe(value)})",
                        ctx.line(path))
            return
        if value < minimum or (strictly and value == minimum):
            word = "greater than" if strictly else "at least"
            ctx.r.error(f"{label} must be {word} {minimum:g}", ctx.line(path))
    return check


def hex_field(regex: re.Pattern, what: str, example: str):
    def check(value, ctx: Ctx, label: str, path: str) -> None:
        if not isinstance(value, str) or not regex.match(value.strip()):
            ctx.r.error(f"{label} must be {what}, for example {example} (found {_describe(value)})", ctx.line(path))
    return check


def ai_field(value, ctx: Ctx, label: str, path: str) -> None:
    if value is False:
        ctx.r.error(f'{label}: write ai_assistance: none (YAML reads a bare "no" as false)', ctx.line(path))
        return
    if not isinstance(value, str) or not value.strip():
        ctx.r.error(f'{label} must be "none" or a plain sentence saying which tool did what '
                    f"(found {_describe(value)})", ctx.line(path))
        return
    v = " ".join(value.split())
    if v.lower().rstrip(".") == "none":
        return
    if v.lower().rstrip(".") in {"yes", "some", "ai", "llm", "n/a", "na", "true", "used", "chatgpt", "claude"} \
            or len(v) < 15:
        ctx.r.error(f'{label} must be "none" or a sentence such as "Claude drafted the Differences section; '
                    'I checked every line against the Lean file." (found ' + repr(value) + ")", ctx.line(path))


def list_field(item_check, min_items: int = 0, what: str = "item"):
    def check(value, ctx: Ctx, label: str, path: str) -> None:
        if not isinstance(value, list):
            ctx.r.error(f"{label} must be a list, with each {what} on its own line starting with '- ' "
                        f"(found {_describe(value)})", ctx.line(path))
            return
        if len(value) < min_items:
            ctx.r.error(f"{label} needs at least {min_items} {what}{'s' if min_items != 1 else ''}", ctx.line(path))
        for n, item in enumerate(value):
            _check_value(item, item_check, ctx, f"{label}[{n + 1}]", f"{path}[{n}]")
    return check


def object_field(spec: dict):
    def check(value, ctx: Ctx, label: str, path: str) -> None:
        if not isinstance(value, dict):
            ctx.r.error(f"{label} must be a group of indented fields (found {_describe(value)})", ctx.line(path))
            return
        check_object(value, spec, ctx, path, label)
    return check


def authors_text_field(value, ctx: Ctx, label: str, path: str) -> None:
    if isinstance(value, list):
        if not value:
            ctx.r.error(f"{label} must name at least one author", ctx.line(path))
        for n, item in enumerate(value):
            _check_value(item, text_field(300), ctx, f"{label}[{n + 1}]", f"{path}[{n}]")
        return
    text_field(500)(value, ctx, label, path)


def _check_value(value, checker, ctx: Ctx, label: str, path: str) -> None:
    if _is_placeholder(value):
        if not ctx.template:
            ctx.r.error(f"{label} still holds template text; replace it with your own", ctx.line(path))
        return
    checker(value, ctx, label, path)


def check_object(obj: dict, spec: dict, ctx: Ctx, prefix: str = "", label_prefix: str = "") -> None:
    for key in obj:
        if key not in spec:
            known = ", ".join(spec)
            where = f"{label_prefix}." if label_prefix else ""
            ctx.r.error(f"unknown field '{where}{key}'; the fields allowed here are: {known}",
                        ctx.line(f"{prefix}.{key}" if prefix else key))
    for key, (required, checker) in spec.items():
        path = f"{prefix}.{key}" if prefix else key
        label = f"{label_prefix}.{key}" if label_prefix else key
        if key not in obj or obj[key] is None or (isinstance(obj[key], str) and not obj[key].strip()):
            if required:
                ctx.r.error(f"missing required field '{label}'", ctx.line(prefix) if prefix else None)
            continue
        _check_value(obj[key], checker, ctx, label, path)


# --------------------------------------------------------------------------
# Schemas
# --------------------------------------------------------------------------

PERSON = {"name": (True, text_field(200)), "github": (True, handle_field)}
AUTHOR = {"name": (True, text_field(200)), "github": (True, handle_field),
          "orcid": (False, orcid_field), "url": (False, url_field)}
REVIEWER = {"name": (True, text_field(200)), "github": (True, handle_field), "background": (True, text_field(500))}
SOURCE = {"authors": (True, authors_text_field), "title": (True, text_field(500)), "year": (True, year_field),
          "doi": (False, doi_field), "url": (False, url_field), "arxiv": (False, arxiv_field)}
MACHINE = {"os": (True, text_field(200)), "cpu": (True, text_field(200)),
           "ram_gb": (True, number_field(0, strictly=True))}

SCHEMAS = {
    "explanation": {
        "kind": (True, kind_field("explanation")),
        "family": (True, family_field),
        "title": (True, text_field(200)),
        "authors": (True, list_field(object_field(AUTHOR), 1, "author")),
        "status": (True, enum_field(STATUSES)),
        "ai_assistance": (True, ai_field),
        "reviewers": (False, list_field(object_field(PERSON), 0, "reviewer")),
        "statements": (False, list_field(statement_field, 0, "statement id")),
        "manuscripts": (False, list_field(manuscript_field, 0, "manuscript id")),
        "date": (True, date_field),
    },
    "statement-check": {
        "kind": (True, kind_field("statement-check")),
        "statement": (True, statement_field),
        "family": (True, family_field),
        "manuscript": (True, manuscript_field),
        "paper_statement": (True, text_field(300)),
        "verdict": (True, enum_field(VERDICTS)),
        "reviewer": (True, object_field(REVIEWER)),
        "ai_assistance": (True, ai_field),
        "date": (True, date_field),
    },
    "credit": {
        "kind": (True, kind_field("credit")),
        "family": (True, family_field),
        "manuscript": (True, manuscript_field),
        "where": (True, text_field(300)),
        "source": (True, object_field(SOURCE)),
        "relation": (True, enum_field(RELATIONS)),
        "contributor": (True, object_field(PERSON)),
        "ai_assistance": (True, ai_field),
        "date": (True, date_field),
    },
    "replay": {
        "kind": (True, kind_field("replay")),
        "statement": (True, statement_field),
        "upstream_commit": (True, hex_field(HEX40_RE, "a full 40-character commit id",
                                            "fd4aeeb2ee4fc729c18d98444fed42fd0529eeeb")),
        "lean_toolchain": (True, text_field(100)),
        "comparator_commit": (True, hex_field(COMMIT_RE, "a commit id in lowercase hexadecimal",
                                              "the output of git rev-parse HEAD")),
        "lean4export_commit": (False, hex_field(COMMIT_RE, "a commit id in lowercase hexadecimal",
                                                "the output of git rev-parse HEAD")),
        "landrun_commit": (False, hex_field(COMMIT_RE, "a commit id in lowercase hexadecimal",
                                            "the output of git rev-parse HEAD")),
        "result": (True, enum_field(RESULTS)),
        "axioms": (True, list_field(text_field(200), 0, "axiom name")),
        "wall_time_seconds": (True, number_field(0)),
        "machine": (True, object_field(MACHINE)),
        "contributor": (True, object_field(PERSON)),
        "log_sha256": (True, hex_field(SHA256_RE, "64 lowercase hexadecimal characters",
                                       "the first field printed by sha256sum comparator.log")),
        "notes": (False, text_field(4000)),
        "date": (True, date_field),
    },
}

TEMPLATE_FILES = {
    "explanation": "explanation.md",
    "statement-check": "statement-check.md",
    "credit": "credit.md",
    "replay": "replay.json",
}


# --------------------------------------------------------------------------
# Paths
# --------------------------------------------------------------------------


def classify(rel: Path):
    """Return (kind, parts) for a path relative to contributions/, or (None, reason)."""
    parts = rel.parts
    if not parts:
        return None, "not a file"
    top = parts[0]
    if top == "explanations":
        if len(parts) == 4 and parts[3] == "explanation.md":
            return "explanation", parts
        if len(parts) >= 4 and parts[-1].endswith(".md"):
            return None, ("only explanation.md is read in an explanation folder; "
                          "rename this file or merge it into explanation.md")
        if len(parts) >= 4:
            return "asset", parts
        return None, "explanations go in contributions/explanations/<family>/<github-handle>/explanation.md"
    if top == "checks":
        if len(parts) == 3 and parts[2].endswith(".md"):
            return "statement-check", parts
        return None, "statement checks go in contributions/checks/<statement-id>/<github-handle>.md"
    if top == "credits":
        if len(parts) == 3 and parts[2].endswith(".md"):
            return "credit", parts
        return None, "credits go in contributions/credits/<family>/<github-handle>-<short-slug>.md"
    if top == "replays":
        if len(parts) == 3 and parts[2].endswith(".json"):
            return "replay", parts
        if len(parts) == 3 and (parts[2].endswith(".log") or parts[2].endswith(".log.gz")):
            return "replay-log", parts
        return None, "replay receipts go in contributions/replays/<statement-id>/<github-handle>-<YYYYMMDD>.json"
    return None, ("unexpected file; contributions live in explanations/, checks/, credits/ or replays/ "
                  "(see contributions/README.md)")


def _same_handle(a, b) -> bool:
    return isinstance(a, str) and isinstance(b, str) and a.lower() == b.lower()


def check_path(kind: str, parts: tuple, meta: dict, ctx: Ctx) -> None:
    r = ctx.r
    if kind == "explanation":
        family, handle = parts[1], parts[2]
        if isinstance(meta.get("family"), str) and meta["family"] != family:
            r.error(f"this file is in the folder for family {family} but says family: \"{meta['family']}\"",
                    ctx.line("family"))
        authors = meta.get("authors") if isinstance(meta.get("authors"), list) else []
        handles = [a.get("github") for a in authors if isinstance(a, dict)]
        if handles and not any(_same_handle(handle, h) for h in handles):
            r.error(f"the folder name '{handle}' must be the GitHub handle of one of the authors "
                    f"({', '.join(str(h) for h in handles)})", ctx.line("authors"))
    elif kind == "statement-check":
        statement, handle = parts[1], parts[2][: -len(".md")]
        if isinstance(meta.get("statement"), str) and meta["statement"] != statement:
            r.error(f"this file is in the folder for statement {statement} but says statement: "
                    f"{meta['statement']}", ctx.line("statement"))
        reviewer = meta.get("reviewer") if isinstance(meta.get("reviewer"), dict) else {}
        github = reviewer.get("github")
        if isinstance(github, str) and not _is_placeholder(github) and not _same_handle(github, handle):
            r.error(f"the file name must be the reviewer's GitHub handle: rename it to {github}.md",
                    ctx.line("reviewer.github"))
    elif kind == "credit":
        family, stem = parts[1], parts[2][: -len(".md")]
        if isinstance(meta.get("family"), str) and meta["family"] != family:
            r.error(f"this file is in the folder for family {family} but says family: \"{meta['family']}\"",
                    ctx.line("family"))
        contributor = meta.get("contributor") if isinstance(meta.get("contributor"), dict) else {}
        github = contributor.get("github")
        if isinstance(github, str) and HANDLE_RE.match(github):
            if not stem.lower().startswith(github.lower() + "-"):
                r.error(f"the file name must start with the contributor's GitHub handle and a hyphen, "
                        f"for example {github}-erdos-1974.md", ctx.line("contributor.github"))
            else:
                slug = stem[len(github) + 1:]
                if not SLUG_RE.match(slug) or len(slug) > 60:
                    r.error(f"the part of the file name after '{github}-' must be a short slug of lowercase "
                            f"letters, digits and hyphens (found '{slug}')", None)
    elif kind == "replay":
        statement, stem = parts[1], parts[2][: -len(".json")]
        if isinstance(meta.get("statement"), str) and meta["statement"] != statement:
            r.error(f"this file is in the folder for statement {statement} but says statement: "
                    f"{meta['statement']}", ctx.line("statement"))
        m = REPLAY_STEM_RE.match(stem)
        if not m:
            r.error("the file name must be <github-handle>-<YYYYMMDD>.json", None)
            return
        contributor = meta.get("contributor") if isinstance(meta.get("contributor"), dict) else {}
        github = contributor.get("github")
        if isinstance(github, str) and not _is_placeholder(github) and not _same_handle(github, m.group("handle")):
            r.error(f"the file name must start with the contributor's GitHub handle ({github})",
                    ctx.line("contributor.github"))
        date = meta.get("date")
        if isinstance(date, str) and DATE_RE.match(date) and date.replace("-", "") != m.group("date"):
            r.error(f"the date in the file name ({m.group('date')}) must match date: {date}", ctx.line("date"))


# --------------------------------------------------------------------------
# Bodies
# --------------------------------------------------------------------------

HEADING_RE = re.compile(r"^ {0,3}(#{1,6})[ \t]+(.*?)[ \t]*#*[ \t]*$")
FENCE_RE = re.compile(r"^ {0,3}(`{3,}|~{3,})")
COMMENT_RE = re.compile(r"<!--.*?-->", re.S)


def body_lines(body: str) -> list[tuple[int, str, bool]]:
    """(index, line, inside_code_fence) for each body line."""
    out, fence = [], None
    for n, line in enumerate(body.split("\n")):
        m = FENCE_RE.match(line)
        if m:
            marker = m.group(1)[0]
            if fence is None:
                fence = marker
                out.append((n, line, True))
                continue
            if marker == fence:
                fence = None
                out.append((n, line, True))
                continue
        out.append((n, line, fence is not None))
    return out


def meaningful(text: str) -> bool:
    return bool(COMMENT_RE.sub("", text).strip())


def check_body(kind: str, meta: dict, body: str, body_line: int, ctx: Ctx) -> None:
    r = ctx.r
    if not meaningful(body):
        r.error("the text below the frontmatter is empty", body_line)
        return
    lines = body_lines(body)
    placeholder_lines = [body_line + n for n, line, _ in lines if PLACEHOLDER in line]
    if placeholder_lines and not ctx.template:
        message = (f"template text ('{PLACEHOLDER} ...') is still present on line"
                   f"{'s' if len(placeholder_lines) > 1 else ''} "
                   f"{', '.join(str(n) for n in placeholder_lines[:8])}; replace it with your own text")
        if kind == "explanation" and meta.get("status") == "draft":
            r.warn(message + " before asking for review", placeholder_lines[0])
        else:
            r.error(message, placeholder_lines[0])
    if kind == "statement-check":
        found = []
        for n, line, in_code in lines:
            if in_code:
                continue
            m = HEADING_RE.match(line)
            if m:
                found.append((n, m.group(2).strip().rstrip(":").strip()))
        positions = []
        start = 0
        for wanted in CHECK_HEADINGS:
            hit = next((i for i in range(start, len(found)) if found[i][1].lower() == wanted.lower()), None)
            if hit is None:
                r.error(f"missing the heading '## {wanted}' (the four headings must appear in this order: "
                        f"{'; '.join(CHECK_HEADINGS)})", body_line)
                return
            positions.append(found[hit][0])
            start = hit + 1
        all_lines = body.split("\n")
        for idx, wanted in enumerate(CHECK_HEADINGS):
            end = positions[idx + 1] if idx + 1 < len(positions) else len(all_lines)
            section = "\n".join(all_lines[positions[idx] + 1:end])
            if not meaningful(section):
                r.error(f"the section '{wanted}' is empty", body_line + positions[idx])
    if kind == "explanation":
        for n, line, in_code in lines:
            if in_code:
                continue
            plain = re.sub(r"`[^`]*`", "", line)
            if "\u2014" in plain:
                r.warn("style: replace the em dash with a comma, colon or full stop (see STYLE.md)", body_line + n)
            if re.search(r"\b(becomes?|turns? into)\b", plain, re.I):
                r.warn("style: for a value, say 'is' or 'equals'; 'becomes' and 'turns into' describe processes "
                       "(see STYLE.md)", body_line + n)


# --------------------------------------------------------------------------
# Cross-checks against data/*.json
# --------------------------------------------------------------------------


def check_links(kind: str, meta: dict, ctx: Ctx) -> None:
    data, r = ctx.data, ctx.r
    family = meta.get("family") if isinstance(meta.get("family"), str) else None
    manuscript = meta.get("manuscript") if isinstance(meta.get("manuscript"), str) else None
    statement = meta.get("statement") if isinstance(meta.get("statement"), str) else None

    def manuscript_family_check(slug: str, path: str, strict: bool) -> None:
        if data.manuscripts is None or slug not in data.manuscripts or family is None:
            return
        record = data.manuscripts[slug]
        owner = record.get("family") if isinstance(record, dict) else None
        if owner and owner != family:
            message = f"manuscript {slug} belongs to family {owner}, and this file names family {family}"
            (r.error if strict else r.warn)(message, ctx.line(path))
        status = record.get("status") if isinstance(record, dict) else None
        if status in ("withdrawn", "previous-edition"):
            r.warn(f"manuscript {slug} is marked {status} upstream; check whether a current edition "
                   "should be named instead", ctx.line(path))

    if kind in ("statement-check", "credit") and manuscript and not _is_placeholder(manuscript):
        manuscript_family_check(manuscript, "manuscript", strict=True)

    if kind == "statement-check" and statement and data.statements and statement in data.statements:
        record = data.statements[statement]
        families = Data._ids(record, "families")
        if family and families and family not in families:
            r.error(f"statement {statement} belongs to family {', '.join(families)}, and this file names family {family}",
                    ctx.line("family"))
        papers = Data._ids(record, "papers")
        if manuscript and papers and manuscript not in papers:
            r.warn(f"manuscript {manuscript} is not one of the papers the upstream scope note links to "
                   f"{statement}; check that this is the paper you meant", ctx.line("manuscript"))

    if kind == "explanation":
        statements = meta.get("statements") if isinstance(meta.get("statements"), list) else []
        manuscripts = meta.get("manuscripts") if isinstance(meta.get("manuscripts"), list) else []
        for n, sid in enumerate(statements):
            if isinstance(sid, str) and data.statements and sid in data.statements and family:
                families = Data._ids(data.statements[sid], "families")
                if families and family not in families:
                    r.warn(f"statement {sid} belongs to family {', '.join(families)}, and this file names family {family}",
                           ctx.line(f"statements[{n}]"))
        for n, slug in enumerate(manuscripts):
            if isinstance(slug, str) and not _is_placeholder(slug):
                manuscript_family_check(slug, f"manuscripts[{n}]", strict=False)

    if kind == "replay" and statement:
        commit = meta.get("upstream_commit")
        if data.pinned_commit and isinstance(commit, str) and HEX40_RE.match(commit) \
                and commit != data.pinned_commit:
            r.warn(f"upstream_commit differs from the commit the atlas reads ({data.pinned_commit}); "
                   "say why in notes", ctx.line("upstream_commit"))
        if data.statements and statement in data.statements and commit == data.pinned_commit:
            comparator = data.statements[statement].get("comparator") or {}
            permitted = comparator.get("permitted_axioms") if isinstance(comparator, dict) else None
            axioms = meta.get("axioms")
            if isinstance(permitted, list) and isinstance(axioms, list) and meta.get("result") == "accepted":
                extra = [a for a in axioms if isinstance(a, str) and a not in permitted]
                if extra:
                    r.error(f"axioms lists {', '.join(extra)}, which the challenge's permitted_axioms do not "
                            f"allow ({', '.join(permitted)}); Comparator would not accept that", ctx.line("axioms"))
        sha = meta.get("comparator_commit")
        if isinstance(sha, str) and COMMIT_RE.match(sha) and len(sha) < 40:
            r.warn("record the full 40-character Comparator commit", ctx.line("comparator_commit"))


def check_rules(kind: str, meta: dict, ctx: Ctx) -> None:
    r = ctx.r
    if kind == "explanation":
        authors_raw = meta.get("authors") if isinstance(meta.get("authors"), list) else []
        reviewers_raw = meta.get("reviewers") if isinstance(meta.get("reviewers"), list) else []
        authors = [a for a in authors_raw if isinstance(a, dict)]
        reviewers = [p for p in reviewers_raw if isinstance(p, dict)]
        author_handles = [str(a.get("github", "")).lower() for a in authors]
        if len(set(author_handles)) < len(author_handles):
            r.error("the same GitHub handle appears twice in authors", ctx.line("authors"))
        overlap = [p.get("github") for p in reviewers if str(p.get("github", "")).lower() in author_handles]
        if overlap:
            r.error(f"a reviewer must be someone other than the authors (found {', '.join(map(str, overlap))})",
                    ctx.line("reviewers"))
        if meta.get("status") == "reviewed" and not reviewers:
            r.error("status: reviewed needs at least one named reviewer under reviewers", ctx.line("status"))


# --------------------------------------------------------------------------
# One file
# --------------------------------------------------------------------------


def split_frontmatter(text: str):
    """Return (yaml_text, yaml_first_line, body, body_first_line)."""
    lines = text.split("\n")
    if not lines or lines[0].strip() != "---":
        raise YamlError("the file must start with a line containing only ---, then the fields, then another --- line", 1)
    for idx in range(1, len(lines)):
        if lines[idx].strip() == "---":
            return "\n".join(lines[1:idx]), 2, "\n".join(lines[idx + 1:]), idx + 2
    raise YamlError("the frontmatter has no closing --- line", 1)


def read_text(path: Path, report: Report) -> str | None:
    try:
        text = path.read_bytes().decode("utf-8")
    except UnicodeDecodeError:
        report.error("the file is not valid UTF-8 text")
        return None
    except OSError as exc:
        report.error(f"could not read the file ({exc})")
        return None
    if text.startswith("\ufeff"):
        text = text[1:]
    return text.replace("\r\n", "\n")


def check_document(kind: str, parts: tuple, text: str, report: Report, data: Data,
                   template: bool = False, folder: Path | None = None) -> dict | None:
    """Check one contribution given its kind, its path parts and its text."""
    if kind == "replay":
        try:
            meta = json.loads(text)
        except ValueError as exc:
            line = getattr(exc, "lineno", None)
            report.error(f"not valid JSON: {getattr(exc, 'msg', exc)}", line)
            return None
        if not isinstance(meta, dict):
            report.error("a replay receipt must be one JSON object { ... }")
            return None
        line_of = _json_key_lines(text)
        ctx = Ctx(report, line_of, data, template)
        check_object(meta, SCHEMAS[kind], ctx)
        check_path(kind, parts, meta, ctx)
        check_links(kind, meta, ctx)
        if folder is not None:
            check_replay_log(parts, meta, folder, ctx)
        return meta
    try:
        yaml_text, yaml_line, body, body_line = split_frontmatter(text)
        meta, line_of, warnings = parse_yaml(yaml_text, yaml_line)
    except YamlError as exc:
        report.error(f"frontmatter: {exc.message}", exc.line)
        return None
    for line, message in warnings:
        report.warn(f"frontmatter: {message}", line)
    ctx = Ctx(report, line_of, data, template)
    if "kind" not in meta:
        report.error(f"missing required field 'kind'; add the line: kind: {kind}", yaml_line)
    check_object(meta, SCHEMAS[kind], ctx)
    check_path(kind, parts, meta, ctx)
    check_rules(kind, meta, ctx)
    check_links(kind, meta, ctx)
    check_body(kind, meta, body, body_line, ctx)
    return meta


def _json_key_lines(text: str) -> dict[str, int]:
    """Line numbers of keys in a JSON object, as dotted paths (best effort)."""
    out: dict[str, int] = {}
    stack: list[str] = []
    depth_keys: list[str | None] = []
    for n, line in enumerate(text.split("\n"), start=1):
        for m in re.finditer(r'"([A-Za-z0-9_]+)"\s*:|[{}]', line):
            token = m.group(0)
            if token == "{":
                stack.append(depth_keys[-1] if depth_keys else "")
                depth_keys.append(None)
            elif token == "}":
                if stack:
                    stack.pop()
                if depth_keys:
                    depth_keys.pop()
            else:
                key = m.group(1)
                prefix = ".".join(p for p in stack[1:] if p)
                out[f"{prefix}.{key}" if prefix else key] = n
                if depth_keys:
                    depth_keys[-1] = key
    return out


def check_replay_log(parts: tuple, meta: dict, folder: Path, ctx: Ctx) -> None:
    stem = parts[2][: -len(".json")]
    for suffix in (".log", ".log.gz"):
        log = folder / (stem + suffix)
        if not log.is_file():
            continue
        size = log.stat().st_size
        if size > MAX_LOG_BYTES:
            ctx.r.error(f"{log.name} is {size // 1000} kB; logs over {MAX_LOG_BYTES // 1_000_000} MB belong in "
                        "the pull request as an attachment")
            continue
        data = log.read_bytes()
        if suffix == ".log.gz":
            try:
                data = gzip.decompress(data)
            except (OSError, EOFError) as exc:
                ctx.r.error(f"{log.name} is not a readable gzip file ({exc})")
                continue
        digest = hashlib.sha256(data).hexdigest()
        expected = meta.get("log_sha256")
        if isinstance(expected, str) and expected != digest:
            ctx.r.error(f"log_sha256 does not match {log.name} (the file's SHA-256 is {digest})",
                        ctx.line("log_sha256"))


def check_file(path: Path, data: Data) -> list[Finding]:
    try:
        rel_root = path.resolve().relative_to(ROOT)
    except ValueError:
        rel_root = path
    report = Report(str(rel_root))
    try:
        rel = path.resolve().relative_to(CONTRIB)
    except ValueError:
        report.error("not inside contributions/")
        return report.findings
    if rel.parts and rel.parts[0] == "_templates":
        return report.findings
    if rel.name.startswith(".") or rel == Path("README.md"):
        return report.findings
    kind, parts = classify(rel)
    if kind is None:
        report.error(parts)
        return report.findings
    if kind == "asset":
        size = path.stat().st_size
        if size > MAX_ASSET_BYTES:
            report.warn(f"this file is {size // 1_000_000} MB; please keep figures under "
                        f"{MAX_ASSET_BYTES // 1_000_000} MB")
        return report.findings
    if kind == "replay-log":
        stem = rel.name[: -len(".log.gz")] if rel.name.endswith(".log.gz") else rel.name[: -len(".log")]
        if not (path.parent / (stem + ".json")).is_file():
            report.error(f"this log has no receipt beside it ({stem}.json)")
        return report.findings
    text = read_text(path, report)
    if text is None:
        return report.findings
    check_document(kind, parts, text, report, data, folder=path.parent)
    return report.findings


def iter_contributions(root: Path):
    if not root.is_dir():
        return
    for path in sorted(root.rglob("*")):
        if not path.is_file():
            continue
        rel = path.relative_to(root)
        if any(part.startswith(".") for part in rel.parts) or "__pycache__" in rel.parts:
            continue
        if rel.parts[0] == "_templates" or rel == Path("README.md"):
            continue
        yield path


# --------------------------------------------------------------------------
# Self-test
# --------------------------------------------------------------------------

PARSER_CASES = [
    ('a: 1\nb: text here\nc: "quoted: yes"\n', {"a": 1, "b": "text here", "c": "quoted: yes"}),
    ("l:\n  - x\n  - y\n", {"l": ["x", "y"]}),
    ("l:\n- x\n- y\nm: z\n", {"l": ["x", "y"], "m": "z"}),
    ("l: [a, \"b, c\", 'd']\n", {"l": ["a", "b, c", "d"]}),
    ("p:\n  name: Ada Lovelace\n  github: ada\n", {"p": {"name": "Ada Lovelace", "github": "ada"}}),
    ("ps:\n  - name: Ada\n    github: ada\n  - name: Bo\n    github: bo\n",
     {"ps": [{"name": "Ada", "github": "ada"}, {"name": "Bo", "github": "bo"}]}),
    ("f: {name: Ada, github: ada}\n", {"f": {"name": "Ada", "github": "ada"}}),
    ("t: >\n  one\n  two\n\n  three\nu: v\n", {"t": "one two\nthree\n", "u": "v"}),
    ("t: |-\n  one\n  two\n", {"t": "one\ntwo"}),
    ("a: x # comment\n# a full-line comment\nb: 'it''s'\n", {"a": "x", "b": "it's"}),
    ("u: https://example.org/a#b\n", {"u": "https://example.org/a#b"}),
    ("e: []\nn:\n", {"e": [], "n": None}),
    ('d: 2026-10-10\nq: "159"\nb: no\nw: Theorem 1.2, label thm:erdos\n',
     {"d": "2026-10-10", "q": "159", "b": False, "w": "Theorem 1.2, label thm:erdos"}),
    ('s: "caf\\u00e9 \\"x\\""\n', {"s": 'café "x"'}),
]

PARSER_ERRORS = [
    "a: b: c\n",
    "a:\n\t- x\n",
    'a: "unclosed\n',
    "a: 1\na: 2\n",
    "  a: 1\n",
    "a: [x, [y]]\n",
    "- x\n",
    "a: 1\n  b: 2\n",
    "a: *ref\n",
    "a:b\n",
]


def _template_cases(texts: dict[str, str]):
    """Mutations of the templates, each of which must be rejected. Yields
    (description, kind, parts, text, template_mode)."""
    e, c, k, rp = texts["explanation"], texts["statement-check"], texts["credit"], texts["replay"]
    ep = ("explanations", "159", "your-github-handle", "explanation.md")
    cp = ("checks", "ErdosReciprocal", "your-github-handle.md")
    kp = ("credits", "159", "your-github-handle-erdos-1974.md")
    rpp = ("replays", "ErdosReciprocal", "your-github-handle-20261010.json")

    def sub(text, old, new, count=1):
        if old not in text:
            raise AssertionError(f"self-test mutation target not found in template: {old!r}")
        return text.replace(old, new, count)

    def drop_line(text, prefix):
        lines = text.split("\n")
        kept = [line for line in lines if not line.startswith(prefix)]
        if len(kept) == len(lines):
            raise AssertionError(f"self-test: no line starting with {prefix!r}")
        return "\n".join(kept)

    yield "explanation without ai_assistance", "explanation", ep, drop_line(e, "ai_assistance:"), True
    yield "explanation with an unknown status", "explanation", ep, sub(e, "status: draft", "status: done"), True
    yield "explanation with a two-digit family", "explanation", ep, sub(e, 'family: "159"', 'family: "15"'), True
    yield "explanation with an unquoted family", "explanation", ep, sub(e, 'family: "159"', "family: 159"), True
    yield "explanation in the wrong family folder", "explanation", \
        ("explanations", "158", "your-github-handle", "explanation.md"), e, True
    yield "explanation reviewed without reviewers", "explanation", ep, sub(e, "status: draft", "status: reviewed"), True
    yield "explanation with an unknown field", "explanation", ep, sub(e, "status: draft", "status: draft\nstauts: x"), True
    yield "explanation with a bad date", "explanation", ep, re.sub(r"(?m)^date: .*$", "date: 2026-02-30", e), True
    yield "explanation with a tab", "explanation", ep, sub(e, "  - name:", "\t- name:"), True
    yield "explanation with template text outside template mode", "explanation", ep, \
        sub(e, "status: draft", "status: ready-for-review"), False
    yield "statement check without the Differences heading", "statement-check", cp, \
        sub(c, "## Differences", "## Notes"), True
    yield "statement check with headings out of order", "statement-check", cp, \
        sub(sub(c, "## What the paper says", "## TMP"), "## What the Lean statement says",
            "## What the paper says").replace("## TMP", "## What the Lean statement says"), True
    yield "statement check with an unknown verdict", "statement-check", cp, re.sub(
        r"(?m)^verdict: .*$", "verdict: match", c), True
    yield "statement check with a misspelt field", "statement-check", cp, sub(c, "verdict:", "verdcit:"), True
    yield "statement check without a reviewer background", "statement-check", cp, \
        drop_line(c, "  background:"), True
    yield "statement check in the wrong statement folder", "statement-check", \
        ("checks", "Catalan", "your-github-handle.md"), c, True
    yield "statement check with an unknown statement", "statement-check", \
        ("checks", "NoSuchStatementAnywhere", "your-github-handle.md"), \
        sub(c, "statement: ErdosReciprocal", "statement: NoSuchStatementAnywhere"), True
    yield 'statement check with ai_assistance: "yes"', "statement-check", cp, re.sub(
        r"(?m)^ai_assistance: .*$", "ai_assistance: yes", c), True
    yield "statement check with a value containing ': '", "statement-check", cp, re.sub(
        r"(?m)^paper_statement: .*$", "paper_statement: Corollary 1.2: divergent sums", c), True
    yield "credit with an unknown relation", "credit", kp, re.sub(r"(?m)^relation: .*$", "relation: inspired-by", k), True
    yield "credit whose file name does not start with the handle", "credit", \
        ("credits", "159", "someone-else-erdos-1974.md"), k, True
    yield "credit with a DOI url", "credit", kp, sub(k, "source:\n", "source:\n  doi: https://doi.org/10.1000/x\n"), True
    yield "credit with an empty body", "credit", kp, k.split("\n---\n", 1)[0] + "\n---\n", True
    yield "credit naming a manuscript from another family", "credit", kp, re.sub(
        r"(?m)^manuscript: .*$",
        "manuscript: A-counterexample-to-Hadwigers-conjecture-September-23-2026", k), True
    replay = json.loads(rp)
    for description, change in (
        ("replay with an unknown result", {"result": "ok"}),
        ("replay with a short upstream commit", {"upstream_commit": "fd4aeeb"}),
        ("replay with a malformed log hash", {"log_sha256": "abc"}),
        ("replay with wall time in quotes", {"wall_time_seconds": "120"}),
        ("replay without machine memory", {"machine": {"os": "Linux", "cpu": "x86"}}),
        ("replay with an extra key", {"wall_time": 5}),
        ("replay with a date that differs from the file name", {"date": "2026-10-11"}),
    ):
        mutated = dict(replay)
        mutated.update(change)
        yield description, "replay", rpp, json.dumps(mutated, indent=2, ensure_ascii=False), True
    yield "replay that is not JSON", "replay", rpp, rp.replace("{", "", 1), True


def _fill(text: str) -> str:
    """Replace template text the way a contributor would."""
    text = re.sub(r'(?m)^(\s*year: ).*$', r"\g<1>1974", text)
    text = re.sub(r'"\[replace:[^"\]]*\]"', '"Sample text written for the self-test"', text)
    text = re.sub(r"\[replace:[^\]]*\]", "Sample text written for the self-test.", text)
    return text.replace("your-github-handle", "octocat")


def _filled_cases(texts: dict[str, str]):
    """The templates filled in the way a contributor would. Each must pass
    outside template mode. Yields (description, kind, parts, text)."""

    e = _fill(texts["explanation"]).replace(
        "status: draft", "status: reviewed\nreviewers:\n  - name: Sample Reviewer\n    github: monalisa")
    yield "a filled-in, reviewed explanation", "explanation", \
        ("explanations", "159", "octocat", "explanation.md"), e
    c = re.sub(r"(?m)^verdict: .*$", "verdict: matches", _fill(texts["statement-check"]))
    yield "a filled-in statement check", "statement-check", ("checks", "ErdosReciprocal", "octocat.md"), c
    k = _fill(texts["credit"])
    yield "a filled-in credit", "credit", ("credits", "159", "octocat-erdos-1974.md"), k
    meta = json.loads(texts["replay"])
    meta.update({
        "comparator_commit": "1234567890abcdef1234567890abcdef12345678",
        "lean4export_commit": "abcdef1234567890abcdef1234567890abcdef12",
        "landrun_commit": "0123456789abcdef0123456789abcdef01234567",
        "result": "accepted",
        "wall_time_seconds": 1834.5,
        "machine": {"os": "Ubuntu 24.04, Linux 6.8", "cpu": "32-core x86-64", "ram_gb": 128},
        "contributor": {"name": "Sample Person", "github": "octocat"},
        "log_sha256": "a" * 64,
        "notes": "Written for the self-test.",
    })
    yield "a filled-in replay receipt", "replay", ("replays", "ErdosReciprocal", "octocat-20261010.json"), \
        json.dumps(meta, indent=2)


CLASSIFY_CASES = [
    ("explanations/159/octocat/explanation.md", "explanation"),
    ("explanations/159/octocat/figure-1.svg", "asset"),
    ("explanations/159/octocat/notes.md", None),
    ("explanations/159/explanation.md", None),
    ("checks/ErdosReciprocal/octocat.md", "statement-check"),
    ("checks/ErdosReciprocal/octocat.txt", None),
    ("credits/159/octocat-erdos-1974.md", "credit"),
    ("replays/ErdosReciprocal/octocat-20261010.json", "replay"),
    ("replays/ErdosReciprocal/octocat-20261010.log.gz", "replay-log"),
    ("misc/notes.md", None),
]


def _log_hash_test() -> list[str]:
    """The log next to a receipt must match log_sha256; check both outcomes."""
    import tempfile
    failures = []
    with tempfile.TemporaryDirectory() as tmp:
        folder = Path(tmp)
        log = b"Building ComparatorChallenges.ErdosReciprocal\nYour solution is okay!\n"
        (folder / "octocat-20261010.log").write_bytes(log)
        parts = ("replays", "ErdosReciprocal", "octocat-20261010.json")
        for digest, should_fail in ((hashlib.sha256(log).hexdigest(), False), ("b" * 64, True)):
            report = Report("self-test")
            check_replay_log(parts, {"log_sha256": digest}, folder, Ctx(report, {}, Data(enabled=False), False))
            if bool(report.errors) != should_fail:
                failures.append(f"log hash check {'accepted a wrong' if should_fail else 'rejected a correct'} hash")
        (folder / "octocat-20261010.log").unlink()
        (folder / "octocat-20261010.log.gz").write_bytes(gzip.compress(log))
        report = Report("self-test")
        check_replay_log(parts, {"log_sha256": hashlib.sha256(log).hexdigest()}, folder,
                         Ctx(report, {}, Data(enabled=False), False))
        if report.errors:
            failures.append("log hash check rejected a correct hash for a .log.gz file")
    return failures


def self_test() -> int:
    failures: list[str] = []
    passed = 0

    for rel, expected in CLASSIFY_CASES:
        kind, _ = classify(Path(rel))
        if kind != expected:
            failures.append(f"path {rel} was classified as {kind}, expected {expected}")
        else:
            passed += 1
    log_failures = _log_hash_test()
    failures.extend(log_failures)
    passed += 3 - len(log_failures)

    for text, expected in PARSER_CASES:
        try:
            value, _, _ = parse_yaml(text)
        except YamlError as exc:
            failures.append(f"parser rejected {text!r}: {exc.message}")
            continue
        if value != expected:
            failures.append(f"parser read {text!r} as {value!r}, expected {expected!r}")
        else:
            passed += 1
    for text in PARSER_ERRORS:
        try:
            parse_yaml(text)
        except YamlError:
            passed += 1
        else:
            failures.append(f"parser accepted invalid text {text!r}")

    data = Data()
    for note in data.notes:
        print(f"note: {note}")
    texts: dict[str, str] = {}
    canonical = {
        "explanation": lambda m: ("explanations", m.get("family", "000"),
                                  (m.get("authors") or [{}])[0].get("github", "x"), "explanation.md"),
        "statement-check": lambda m: ("checks", m.get("statement", "X"),
                                      (m.get("reviewer") or {}).get("github", "x") + ".md"),
        "credit": lambda m: ("credits", m.get("family", "000"),
                             (m.get("contributor") or {}).get("github", "x") + "-erdos-1974.md"),
        "replay": lambda m: ("replays", m.get("statement", "X"),
                             f"{(m.get('contributor') or {}).get('github', 'x')}-"
                             f"{str(m.get('date', '')).replace('-', '')}.json"),
    }
    for kind, name in TEMPLATE_FILES.items():
        path = TEMPLATES / name
        if not path.is_file():
            failures.append(f"missing template contributions/_templates/{name}")
            continue
        report = Report(f"contributions/_templates/{name}")
        text = read_text(path, report)
        if text is None:
            failures.extend(f.text() for f in report.findings)
            continue
        texts[kind] = text
        if kind == "replay":
            try:
                meta = json.loads(text)
            except ValueError as exc:
                failures.append(f"{name} is not valid JSON: {exc}")
                continue
        else:
            try:
                meta = parse_yaml(split_frontmatter(text)[0])[0]
            except YamlError as exc:
                failures.append(f"{name}:{exc.line}: {exc.message}")
                continue
        parts = canonical[kind](meta)
        check_document(kind, parts, text, report, data, template=True)
        problems = [f for f in report.findings if f.level == "error"]
        if problems:
            failures.extend(f"template {f.text()}" for f in problems)
        else:
            passed += 1
            print(f"ok: template {name} is valid (as {'/'.join(parts)})")

    skill_examples = sorted((ROOT / "skills").glob("*/examples/*.md")) if (ROOT / "skills").is_dir() else []
    for path in skill_examples:
        report = Report(str(path.relative_to(ROOT)))
        text = read_text(path, report)
        if text is None:
            failures.extend(f.text() for f in report.findings)
            continue
        try:
            meta = parse_yaml(split_frontmatter(text)[0])[0]
        except YamlError as exc:
            failures.append(f"{path.relative_to(ROOT)}:{exc.line}: {exc.message}")
            continue
        kind = meta.get("kind")
        if kind not in canonical or kind == "replay":
            failures.append(f"{path.relative_to(ROOT)}: kind must be explanation, statement-check or credit")
            continue
        check_document(kind, canonical[kind](meta), text, report, data, template=True)
        problems = [f for f in report.findings if f.level == "error"]
        if problems:
            failures.extend(f"example {f.text()}" for f in problems)
        else:
            passed += 1
            print(f"ok: worked example {path.relative_to(ROOT)} is valid")

    if len(texts) == len(TEMPLATE_FILES):
        for description, kind, parts, text in _filled_cases(texts):
            report = Report("self-test")
            check_document(kind, parts, text, report, data, template=False)
            if report.findings:
                failures.extend(f"{description} was not accepted cleanly: {f.text()}" for f in report.findings)
            else:
                passed += 1
        print("ok: filled-in copies of the four templates pass outside template mode")
        head, body = texts["explanation"].split("\n---\n", 1)
        report = Report("self-test")
        check_document("explanation", ("explanations", "159", "octocat", "explanation.md"),
                       _fill(head) + "\n---\n" + body, report, data, template=False)
        if report.errors or not report.findings:
            failures.append("a draft explanation with template text left in its body should give warnings "
                            "and no errors; got " + "; ".join(f.text() for f in report.findings))
        else:
            passed += 1
            print("ok: template text left in the body of a draft is a warning")
        rejected = 0
        for description, kind, parts, text, template_mode in _template_cases(texts):
            report = Report("self-test")
            check_document(kind, parts, text, report, data, template=template_mode)
            needs_data = "unknown statement" in description or "another family" in description \
                or "wrong statement folder" in description
            if needs_data and (data.statements is None or data.manuscripts is None):
                continue
            if report.errors:
                rejected += 1
            else:
                failures.append(f"the checker accepted a broken file: {description}")
        passed += rejected
        print(f"ok: {rejected} deliberately broken files were rejected")

    for failure in failures:
        print(f"FAIL: {failure}")
    print(f"self-test: {passed} checks passed, {len(failures)} failed")
    return 1 if failures else 0


# --------------------------------------------------------------------------
# Main
# --------------------------------------------------------------------------


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(
        description="Check the contribution files under contributions/ (see contributions/README.md).")
    parser.add_argument("files", nargs="*", type=Path, help="files to check (default: every contribution)")
    parser.add_argument("--self-test", action="store_true", help="check the templates and the checker itself")
    parser.add_argument("--no-data", action="store_true", help="skip the cross-checks against data/*.json")
    parser.add_argument("--strict", action="store_true", help="count warnings as errors")
    parser.add_argument("--json", action="store_true", help="print findings as JSON")
    args = parser.parse_args(argv)

    if args.self_test:
        return self_test()

    data = Data(enabled=not args.no_data)
    paths = [p if p.is_absolute() else Path.cwd() / p for p in args.files] if args.files \
        else list(iter_contributions(CONTRIB))
    findings: list[Finding] = []
    checked = 0
    for path in paths:
        if not path.is_file():
            findings.append(Finding("error", str(path), None, "no such file"))
            continue
        checked += 1
        findings.extend(check_file(path, data))

    errors = sum(1 for f in findings if f.level == "error")
    warnings = sum(1 for f in findings if f.level == "warning")
    failed = errors > 0 or (args.strict and warnings > 0)
    if args.json:
        print(json.dumps({"ok": not failed, "files_checked": checked, "errors": errors, "warnings": warnings,
                          "notes": data.notes, "findings": [f.as_dict() for f in findings]},
                         indent=2, ensure_ascii=False))
    else:
        for note in data.notes:
            print(f"note: {note}")
        for finding in findings:
            print(finding.text())
        print(f"Checked {checked} file{'s' if checked != 1 else ''}: "
              f"{errors} error{'s' if errors != 1 else ''}, {warnings} warning{'s' if warnings != 1 else ''}.")
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
