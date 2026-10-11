## What this pull request adds

<!-- One useful contribution and its supporting evidence per pull request. Keep the line that applies and delete the others. -->

- Statement check: `contributions/checks/<statement>/<handle>.md`
- Explanation, new or revised: `contributions/explanations/<family>/<handle>/explanation.md`
- Credit: `contributions/credits/<family>/<handle>-<slug>.md`
- Replay receipt: `contributions/replays/<statement>/<handle>-<YYYYMMDD>.json`
- A change to the atlas itself (scripts, skills, documentation, site)

<!-- If this closes a claim or a problem report, write "Closes #<number>". -->

## Checklist

- [ ] `python3 scripts/check_contributions.py` reports no errors.
- [ ] The recorded upstream_commit is the version I actually read.
- [ ] My name and GitHub handle are in the file, and I stand behind every sentence in it.
- [ ] `ai_assistance` says plainly which tools I used and for what, or says none.
- [ ] Anything I quote from OpenAI's release is short, exact and located.
- [ ] Statement checks: I read the whole challenge file and the paper statement myself.
- [ ] Explanations: I went through the self-check at the end of `STYLE.md`.
- [ ] Credits: I opened and read the earlier work myself.
- [ ] Changes to the atlas: `python3 scripts/check_contributions.py --self-test`, `python3 scripts/sync_skills.py --check` and `python3 scripts/build_site.py` succeed.

## Review evidence, when requesting reviewed status

<!-- Link the independent reviewer's own approval and the content commit they read. Do not add a person to reviewers on their behalf. A substantive edit needs renewed approval. -->

## Anything a reviewer should know

<!-- Open questions, steps you could not verify, or what you would like a second opinion on. -->
