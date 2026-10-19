"""Checks for scripts/upstream_changes.py: an upstream commit touching only files the atlas
never reads is not a change; one touching a scope note, a paper or a challenge is.
Standard library and git only: python3 scripts/tests/test_upstream_changes.py
"""
from __future__ import annotations

import subprocess
import sys
import tempfile
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

import upstream_changes as U  # noqa: E402


def commit(repo: Path, files: dict, message: str) -> str:
    for rel, text in files.items():
        p = repo / rel
        p.parent.mkdir(parents=True, exist_ok=True)
        p.write_text(text, encoding="utf-8")
    subprocess.run(["git", "-C", str(repo), "add", "-A"], check=True)
    subprocess.run(["git", "-C", str(repo), "-c", "user.name=t", "-c", "user.email=t@t", "commit", "-qm", message], check=True)
    return subprocess.run(["git", "-C", str(repo), "rev-parse", "HEAD"], check=True, capture_output=True, text=True).stdout.strip()


def main() -> int:
    fails = []
    for path, want in [(".github/workflows/lock-prs.yml", False), ("lean/docs/017.md", True), ("preprints/x/main.tex", True),
                       ("preprints/x/paper.pdf", True), ("CONTENTS.md", True), ("lean/OAI/A.lean", True),
                       ("lean/lakefile.lean", True), ("docs/site/index.md", False), ("scripts/tool.py", False)]:
        if U.read_by_atlas(path) is not want:
            fails.append(f"read_by_atlas({path!r}) should be {want}")
    with tempfile.TemporaryDirectory() as d:
        repo = Path(d)
        subprocess.run(["git", "init", "-q", str(repo)], check=True)
        a = commit(repo, {"lean/docs/017.md": "scope", "README.md": "release"}, "base")
        b = commit(repo, {".github/workflows/lock-prs.yml": "on: pull_request"}, "workflow only")
        c = commit(repo, {"lean/docs/017.md": "scope, revised"}, "scope note")
        out = Path(d) / "gh_out"
        U.main(["--upstream", str(repo), "--from", a, "--to", b, "--github-output", str(out)])
        if "relevant=false" not in out.read_text():
            fails.append("a workflow-only commit counted as a change")
        out.unlink()
        U.main(["--upstream", str(repo), "--from", a, "--to", c, "--github-output", str(out)])
        text = out.read_text()
        if "relevant=true" not in text or "count=1" not in text:
            fails.append(f"a scope-note change was not counted: {text!r}")
    for f in fails:
        print("FAIL", f)
    print(f"upstream changes: {len(fails)} failures")
    return 1 if fails else 0


if __name__ == "__main__":
    sys.exit(main())
