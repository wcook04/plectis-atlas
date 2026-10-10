#!/usr/bin/env python3
"""Copy the agent skills in skills/ to the mirrors that agents read.

Usage:
    python3 scripts/sync_skills.py           make .claude/skills/ and .agents/skills/ exact copies of skills/
    python3 scripts/sync_skills.py --check   report differences and exit 1 if a mirror is out of date

skills/ is the only place to edit a skill. Claude Code reads .claude/skills/;
Codex and other agents read .agents/skills/. Both mirrors are generated: this
script overwrites changed files and removes files that no longer exist in
skills/. Before copying, it checks that every skill folder has a SKILL.md whose
frontmatter has a `name` equal to the folder name and a `description`.

Standard library only; Python 3.10 or newer.
"""
from __future__ import annotations

import argparse
import re
import shutil
import stat
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
SOURCE = ROOT / "skills"
MIRRORS = (ROOT / ".claude" / "skills", ROOT / ".agents" / "skills")
IGNORED_NAMES = {".DS_Store", "__pycache__"}
IGNORED_SUFFIXES = (".pyc", ".pyo")
NAME_RE = re.compile(r"^[a-z0-9]+(?:-[a-z0-9]+)*$")


def wanted(path: Path) -> bool:
    return not any(part in IGNORED_NAMES for part in path.parts) and not path.name.endswith(IGNORED_SUFFIXES)


def files_under(base: Path) -> dict[Path, Path]:
    """Relative path -> absolute path for every file under base."""
    if not base.is_dir():
        return {}
    return {p.relative_to(base): p for p in sorted(base.rglob("*")) if p.is_file() and wanted(p.relative_to(base))}


def read_frontmatter(text: str) -> dict:
    """Parse the frontmatter with the same small YAML parser the contribution
    checker uses, so a value that real YAML parsers reject is caught here."""
    sys.path.insert(0, str(ROOT / "scripts"))
    sys.dont_write_bytecode = True
    try:
        from check_contributions import YamlError, parse_yaml, split_frontmatter
    finally:
        sys.path.pop(0)
    try:
        yaml_text, first_line, _, _ = split_frontmatter(text.replace("\r\n", "\n"))
        value, _, _ = parse_yaml(yaml_text, first_line)
    except YamlError as exc:
        raise ValueError(f"line {exc.line}: {exc.message}") from None
    return value if isinstance(value, dict) else {}


def validate(source: Path) -> list[str]:
    problems = []
    if not source.is_dir():
        return [f"{source.relative_to(ROOT)}/ does not exist"]
    for folder in sorted(p for p in source.iterdir() if p.is_dir() and wanted(Path(p.name))):
        skill = folder / "SKILL.md"
        where = f"skills/{folder.name}"
        if not skill.is_file():
            problems.append(f"{where}: missing SKILL.md")
            continue
        try:
            fields = read_frontmatter(skill.read_text(encoding="utf-8"))
        except ValueError as exc:
            problems.append(f"{where}/SKILL.md: frontmatter {exc}")
            continue
        name = fields.get("name")
        description = fields.get("description")
        if name != folder.name:
            problems.append(f"{where}/SKILL.md: name must be '{folder.name}' (found {name!r})")
        if not NAME_RE.match(folder.name) or len(folder.name) > 64:
            problems.append(f"{where}: folder name must be lowercase letters, digits and single hyphens, "
                            "at most 64 characters")
        if not isinstance(description, str) or not description.strip():
            problems.append(f"{where}/SKILL.md: needs a description saying when to use the skill")
        elif len(description.strip()) > 1024:
            problems.append(f"{where}/SKILL.md: description is {len(description.strip())} characters; "
                            "the limit is 1024")
        extra = sorted(set(fields) - {"name", "description", "license", "compatibility", "metadata",
                                      "allowed-tools"})
        if extra:
            problems.append(f"{where}/SKILL.md: unexpected frontmatter field(s) {', '.join(extra)}")
    return problems


def plan(source: Path, mirror: Path):
    """Return (to_copy, to_delete) as lists of relative paths."""
    src, dst = files_under(source), files_under(mirror)
    to_copy = [rel for rel, path in src.items()
               if rel not in dst or dst[rel].read_bytes() != path.read_bytes()
               or (path.stat().st_mode & 0o111) != (dst[rel].stat().st_mode & 0o111)]
    to_delete = [rel for rel in dst if rel not in src]
    return to_copy, to_delete


def apply(source: Path, mirror: Path, to_copy, to_delete) -> None:
    for rel in to_copy:
        target = mirror / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(source / rel, target)
        mode = (source / rel).stat().st_mode
        target.chmod(stat.S_IMODE(mode))
    for rel in to_delete:
        (mirror / rel).unlink()
    if mirror.is_dir():
        for folder in sorted((p for p in mirror.rglob("*") if p.is_dir()), key=lambda p: len(p.parts), reverse=True):
            if not any(folder.iterdir()):
                folder.rmdir()


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Copy skills/ to .claude/skills/ and .agents/skills/.")
    parser.add_argument("--check", action="store_true", help="report differences without writing; exit 1 if any")
    args = parser.parse_args(argv)

    problems = validate(SOURCE)
    for problem in problems:
        print(f"error: {problem}")
    if problems:
        print("Fix the skills above before syncing.")
        return 1

    out_of_date = False
    for mirror in MIRRORS:
        to_copy, to_delete = plan(SOURCE, mirror)
        label = mirror.relative_to(ROOT)
        if not to_copy and not to_delete:
            print(f"{label}/ is in sync with skills/")
            continue
        out_of_date = True
        if args.check:
            for rel in to_copy:
                print(f"{label}/{rel}: {'differs from' if (mirror / rel).exists() else 'missing from the mirror of'} "
                      f"skills/{rel}")
            for rel in to_delete:
                print(f"{label}/{rel}: not in skills/")
        else:
            apply(SOURCE, mirror, to_copy, to_delete)
            print(f"{label}/: copied {len(to_copy)} file{'s' if len(to_copy) != 1 else ''}, "
                  f"removed {len(to_delete)}")
    if args.check and out_of_date:
        print("The skill mirrors are out of date: run python3 scripts/sync_skills.py and commit the result.")
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
