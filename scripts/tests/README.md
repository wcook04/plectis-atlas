# Regression suites

Run suites directly from the repository root, for example:

```sh
python3 scripts/tests/test_reader.py
python3 scripts/tests/test_search.py
node scripts/tests/test_universe_labels.js
```

Some suites use a main function rather than unittest discovery. Run the commands
in [the CI workflow](../../.github/workflows/check.yml) for full coverage;
[test_family_page.py](test_family_page.py) additionally checks family rendering.
Tests import their owners from `scripts/`; shared production modules stay there.
Placement rules and Git index behaviour are tested by
[test_repository_structure.py](test_repository_structure.py).

The optional browser regression for deferred family feedback holds and fails the
parts request, then retries it in phone List and Map views and on desktop:

```sh
python3 scripts/tests/test_universe_status.py --shots /tmp/atlas-status-shots
```

Build `site/_build/` first with `scripts/build_site.py` and
`scripts/build_universe.py`. This check requires Playwright and a local Chrome
or Playwright Chromium installation.
