#!/usr/bin/env python3
"""Say whether openai/math changed anything the atlas reads between two commits.

The weekly upstream job asks this before it moves the pin. A new upstream commit
that touches only files the atlas never reads (a GitHub workflow, a repository
setting) changes nothing on the site, so the pin stays and the job ends cleanly.
When a file the atlas reads has changed, following it needs Statement Map's export
at the new commit first (scripts/vendor_backend.py), because scripts/reader.py
refuses a backend pinned elsewhere; the job then says so, with the changed paths.

    python3 scripts/upstream_changes.py --upstream ../openai-math-upstream --from <old> [--to <new>]
        [--github-output "$GITHUB_OUTPUT"]

Prints the changed paths the atlas reads, one per line, then a one-line verdict.
Exits 0 either way; --github-output receives relevant=true|false and count=<n>.
Standard library only.
"""
from __future__ import annotations

import argparse
import subprocess
import sys

# What the atlas reads from openai/math: the paths scripts/fetch_upstream.sh checks out
# (with --lean-library), plus the PDFs it leaves out only for size, since the site links
# each paper's PDF at the pinned commit.
READ_FILES = {"LICENSE", "lean/formalization.yaml", "lean/README.md", "lean/lean-toolchain",
              "lean/lakefile.lean", "lean/lake-manifest.json"}
READ_DIRS = ("lean/docs/", "lean/ComparatorChallenges/", "lean/OAI/", "preprints/")
READ_ROOT_SUFFIXES = (".md", ".tex")


def read_by_atlas(path: str) -> bool:
    if path in READ_FILES or path.startswith(READ_DIRS):
        return True
    return "/" not in path and path.endswith(READ_ROOT_SUFFIXES)


def git(upstream: str, *args: str) -> str:
    return subprocess.run(["git", "-C", upstream, *args], check=True, capture_output=True, text=True).stdout


def changed_paths(upstream: str, old: str, new: str) -> list[str]:
    # The job's checkout is a partial clone at the new commit: fetch the old one too.
    try:
        git(upstream, "cat-file", "-e", old + "^{commit}")
    except subprocess.CalledProcessError:
        git(upstream, "fetch", "--quiet", "origin", old)
    out = git(upstream, "diff", "--no-renames", "--name-only", old, new)
    return [p for p in out.splitlines() if p]


def main(argv: list[str] | None = None) -> int:
    ap = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    ap.add_argument("--upstream", required=True, help="an openai/math checkout holding both commits (or able to fetch them)")
    ap.add_argument("--from", dest="old", required=True, help="the commit the atlas is pinned at")
    ap.add_argument("--to", dest="new", default="HEAD", help="the commit to compare with (default: the checkout's HEAD)")
    ap.add_argument("--github-output", help="append relevant=… and count=… to this file")
    args = ap.parse_args(argv)
    if not args.old.strip():
        ap.error("--from is empty: pass the commit upstream.json records")
    new = git(args.upstream, "rev-parse", args.new).strip()
    paths = [p for p in changed_paths(args.upstream, args.old, new) if read_by_atlas(p)]
    for p in paths:
        print(p)
    if paths:
        print(f"{len(paths)} file(s) the atlas reads changed between {args.old[:12]} and {new[:12]}.")
    else:
        print(f"Nothing the atlas reads changed between {args.old[:12]} and {new[:12]}.")
    if args.github_output:
        with open(args.github_output, "a", encoding="utf-8") as fh:
            fh.write(f"relevant={'true' if paths else 'false'}\ncount={len(paths)}\nnew={new}\n")
    return 0


if __name__ == "__main__":
    sys.exit(main())
