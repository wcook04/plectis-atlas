#!/usr/bin/env python3
"""Check role placement from Git's index and nonignored working candidates."""
from pathlib import Path, PurePosixPath
import subprocess

ROOT = Path(__file__).resolve().parents[1]
ROOT_FILES = {
    '.gitattributes', '.gitignore', 'AGENTS.md', 'ALIGNMENT.md', 'CITATION.cff',
    'CLAUDE.md', 'CODE_OF_CONDUCT.md', 'CONTRIBUTING.md', 'DESIGN.md', 'LICENSE',
    'NOTICE', 'README.md', 'SECURITY.md', 'STYLE.md', 'upstream.json',
}
REQUIRED = {'scripts/reader.py', 'scripts/build_site.py', 'docs/ARCHITECTURE.md',
            'scripts/tests/test_reader.py', 'scripts/check_community.py',
            'scripts/check_scope_coverage.py', 'docs/images/map-light.png'}
# Published commands retained as launchers, not homes for new validator code.
CURATED_LAUNCHERS = {'curated/check_community.py', 'curated/check_scope_coverage.py'}


def candidates(root: Path) -> set[str]:
    """Include staged additions, exclude staged deletions and ignored output."""
    raw = subprocess.check_output(
        ['git', 'ls-files', '-z', '--cached', '--others', '--exclude-standard'], cwd=root)
    return set(raw.decode().split('\0')) - {''}


def check(paths: set[str]) -> list[str]:
    errors = [f'{p}: required source is missing' for p in sorted(REQUIRED - paths)]
    for name in sorted(paths):
        p = PurePosixPath(name)
        if len(p.parts) == 1 and name not in ROOT_FILES:
            errors.append(f'{name}: root is for public entry files and repository configuration')
        if p.name.startswith('test_') and p.suffix in {'.py', '.js', '.mjs'} and p.parts[:2] != ('scripts', 'tests'):
            errors.append(f'{name}: regression suites belong in scripts/tests/')
        if p.parts[0] == 'docs' and p.suffix in {'.png', '.jpg', '.jpeg', '.webp', '.svg'} and p.parts[:2] != ('docs', 'images'):
            errors.append(f'{name}: documentation images belong in docs/images/')
        if p.parts[0] == 'docs' and p.suffix in {'.py', '.js', '.mjs', '.sh'}:
            errors.append(f'{name}: executable tooling belongs in scripts/')
        if p.parts[0] == 'curated' and p.suffix in {'.py', '.js', '.mjs', '.sh'} and name not in CURATED_LAUNCHERS:
            errors.append(f'{name}: curated records are data; executable tooling belongs in scripts/')
        if p.parts[:2] == ('site', '_build'):
            errors.append(f'{name}: generated website output must not be tracked')
    return errors


def main() -> int:
    errors = check(candidates(ROOT))
    print('\n'.join(errors) if errors else 'Repository structure: OK')
    return bool(errors)


if __name__ == '__main__':
    raise SystemExit(main())
