"""Check attributed inputs and include their notices in the website distribution.

The component inventory is LICENSES/manifest.json. Evidence-source metadata stays
in curated/sources/, and imported backend records keep their original notices.
This checks coverage and bytes, not legal permission or scholarly priority.
"""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import shutil

ROOT = Path(__file__).resolve().parent.parent
NOTICE_FILES = ('LICENSE', 'NOTICE', 'CITATION.cff')


def inventory(root: Path = ROOT) -> dict:
    return json.loads((root / 'LICENSES/manifest.json').read_text(encoding='utf-8'))


def check(root: Path = ROOT, built: Path | None = None) -> list[str]:
    errors = []
    doc = inventory(root)
    if doc.get('schema') != 'atlas-attribution/1':
        errors.append('unknown attribution inventory schema')
    owned = set()
    for component in doc['components']:
        for field in ('id', 'name', 'credit', 'source', 'url', 'licence', 'licence_file', 'changes', 'use'):
            if not component.get(field):
                errors.append(f"{component.get('id')}: missing {field}")
        for path, expected in component['files'].items():
            if path in owned:
                errors.append(f'{path}: credited more than once')
            owned.add(path)
            file = root / path
            if not file.is_file():
                errors.append(f'{path}: missing distributed component')
            elif hashlib.sha256(file.read_bytes()).hexdigest() != expected:
                errors.append(f'{path}: bytes changed; review source and update attribution')
            if built is not None:
                distributed = built / Path(path).relative_to('site')
                if not distributed.is_file() or hashlib.sha256(distributed.read_bytes()).hexdigest() != expected:
                    errors.append(f'{path}: built component missing or differs from attribution inventory')
        if not (root / component['licence_file']).is_file():
            errors.append(f"{component['id']}: licence copy missing")
    actual = {str(p.relative_to(root)) for folder in ('site/assets/fonts', 'site/assets/vendor')
              for p in (root / folder).rglob('*') if p.is_file()}
    for path in sorted(actual - owned):
        errors.append(f'{path}: distributed asset has no attribution record')
    for path in sorted(owned - actual):
        errors.append(f'{path}: attribution entry is outside the distributed asset folders')
    configured = json.loads((root / 'site/config.json').read_text())['katex_version']
    katex = next((c for c in doc['components'] if c['id'] == 'katex'), {})
    if configured != katex.get('version'):
        errors.append('configured KaTeX version differs from attribution inventory')
    sources = {}
    for path in (root / 'curated/sources').glob('*.json'):
        source = json.loads(path.read_text())['source']
        sources[source['id']] = source
        for field in ('name', 'url', 'authors', 'licence', 'reuse', 'snapshot'):
            if not source.get(field):
                errors.append(f'{path.name}: missing source {field}')
        copies = doc['source_licences'].get(source['id'])
        if copies is None:
            errors.append(f'{path.name}: source terms have not been inventoried')
        elif source.get('reuse') == 'import' and not copies:
            errors.append(f'{path.name}: imported material has no licence copy')
        for copy in copies or []:
            if not (root / copy).is_file():
                errors.append(f'{path.name}: missing {copy}')
    for sid in doc['source_licences'].keys() - sources.keys():
        errors.append(f'{sid}: licence inventory has no source record')
    for name in NOTICE_FILES:
        if not (root / name).is_file():
            errors.append(f'{name}: missing repository notice')
    if built is not None:
        pairs = [(name, name) for name in NOTICE_FILES]
        pairs += [('backend/NOTICE.md', 'backend-NOTICE.md')]
        pairs += [(str(p.relative_to(root)), str(p.relative_to(root)))
                  for p in (root / 'LICENSES').rglob('*') if p.is_file()]
        for source, dest in pairs:
            target = built / dest
            if not target.is_file() or target.read_bytes() != (root / source).read_bytes():
                errors.append(f'{dest}: built notice missing or differs from repository')
    return errors


def write_notices(out: Path, root: Path = ROOT) -> None:
    errors = check(root)
    if errors:
        raise ValueError('\n'.join(errors))
    for name in NOTICE_FILES:
        shutil.copy2(root / name, out / name)
    shutil.copy2(root / 'backend/NOTICE.md', out / 'backend-NOTICE.md')
    shutil.copytree(root / 'LICENSES', out / 'LICENSES', dirs_exist_ok=True)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--built', type=Path, help='also verify notices in this site build')
    args = parser.parse_args()
    errors = check(built=args.built)
    if errors:
        print('\n'.join(errors))
        return 1
    doc = inventory()
    print(f"Attribution inventory: {len(doc['components'])} components, "
          f"{sum(len(c['files']) for c in doc['components'])} asset files, "
          f"{len(doc['source_licences'])} evidence sources; notices present.")
    return 0


if __name__ == '__main__':
    raise SystemExit(main())
