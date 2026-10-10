# Contributing to the OpenAI Math Atlas

The atlas sets every Lean statement in OpenAI's mathematics release beside the paper theorems it formalises, and computes what a machine can: how much vocabulary of its own each Lean statement introduces, what each manuscript cites inside the collection, and which earlier works it builds on. The rest needs people. Readers want motivated explanations, credit where ideas first appeared, and a check, statement by statement, that each Lean statement says what the paper says. That is the work this guide describes.

You need no knowledge of any other project, and no Lean experience for most tasks. Every contribution is credited by name on the atlas.

## Five ways to help

| Contribution | What you produce | Time | Where it goes |
|---|---|---|---|
| Check a statement | A signed verdict on whether one Lean statement says what the paper's theorem says | 15 minutes to an evening | `contributions/checks/<statement>/<you>.md` |
| Explain a result | A motivated, first-principles explanation of one result family | Several evenings | `contributions/explanations/<family>/<you>/explanation.md` |
| Trace a credit | One link from a step in a manuscript to the earlier work it builds on | 30 minutes or more | `contributions/credits/<family>/<you>-<slug>.md` |
| Replay a proof | A receipt from running Comparator on one statement on your own Linux machine | Hours of machine time | `contributions/replays/<statement>/<you>-<date>.json` |
| Report a problem | An issue that pins down a mismatch, an error or a broken link | 10 minutes | an issue made with the "Report a problem" form |

Each kind has a guide in `skills/`, written for people and for AI agents alike:

- `skills/start-here/SKILL.md` helps you choose;
- `skills/check-a-statement/SKILL.md`, `skills/explain-a-result/SKILL.md`, `skills/trace-a-credit/SKILL.md`, `skills/replay-a-proof/SKILL.md` and `skills/report-a-problem/SKILL.md` cover the five kinds;
- `skills/improve-the-atlas/SKILL.md` covers changes to the atlas's own scripts and pages.

## Your first contribution, in about fifteen minutes

A statement check is the quickest way in.

1. **Pick a statement in a field you know.** Browse the atlas, or run this in a clone of the repository:

   ```sh
   python3 skills/start-here/find_work.py --kind check --discipline "number theory"
   ```

   It lists statements nobody has checked yet, with the fewest custom definitions first, and links the Lean file, the scope note and the paper.

2. **Fork the repository on GitHub, clone your fork, and copy the template:**

   ```sh
   mkdir -p contributions/checks/<StatementId>
   cp contributions/_templates/statement-check.md contributions/checks/<StatementId>/<your-github-handle>.md
   ```

3. **Read the paper's statement and the whole Lean file**, following the procedure and checklist in `skills/check-a-statement/SKILL.md`. Its worked example, `ErdosReciprocal`, shows a complete check.

4. **Fill in the file**: the frontmatter, then the four sections "What the paper says", "What the Lean statement says", "Differences" and "Why this verdict".

5. **Check the file:**

   ```sh
   python3 scripts/check_contributions.py contributions/checks/<StatementId>/<your-github-handle>.md
   ```

   Fix anything it reports. It needs only Python 3.10 or newer.

6. **Commit, push to your fork, and open a pull request** with this one file.

## With an AI agent

Open the repository in Claude Code, Codex, Cursor or another coding agent and ask it to begin with the `start-here` skill. The agent reads `AGENTS.md` and the skills (mirrored for Claude Code in `.claude/skills/` and for other agents in `.agents/skills/`). It asks about your background and time, finds a task, drafts with you and runs the checks.

You stay responsible for what you submit. Read every line the agent drafts, check every reference it suggests by opening it, and sign only what you understand.

## Credit and AI assistance

- **Every contribution is credited by name** on the atlas pages it touches: explanations under their authors' names, checks under the reviewer's name, credits and replays under the contributor's name.
- **A named person takes responsibility for every contribution.** Each file names that person with their GitHub handle. Agents may draft, check arithmetic, search and run tools; they never sign.
- **AI assistance is disclosed.** Every Markdown contribution has an `ai_assistance` field holding `none` or a plain sentence saying which tool did what, and it is published with the contribution. Explanations are written in the contributor's own words; any passage a tool drafted is marked.
- **Agents check and explain; they do not hunt for open problems.** The skills in this repository read, compare, trace and replay. Do not point them at unsolved problems in the release or elsewhere.
- **Your contribution stays here unless you say otherwise.** The atlas never sends a contribution to OpenAI or to any other lab. If a way to offer checked rows back to a release is added later, it will be opt-in for each contribution.
- **Declining is respected.** Some mathematicians have chosen not to work on AI-generated releases. Nobody is asked to review anything uninvited, and the atlas keeps no list of people to approach.
- **Verdicts on the atlas come only from named people.** A statement check is the signed judgement of its reviewer. Several people can check the same statement; the atlas shows each verdict with its author. Maintainers do not change your verdict; if they disagree, they say so in the pull request.
- **Credit for ideas requires a source.** A credit file names a citable earlier work, and the claim that an idea first appeared somewhere is made only with a source to back it.
- **Every honest outcome is credited.** A `cannot-tell` check, a replay that ended in `error`, and a credit that settles on `uses` after a long search all record real work and are credited in the same way.
- **Corrections keep the history.** To correct or disagree with someone else's contribution, add your own file (a check with a different verdict, a further credit) or propose a change in a pull request the original authors can see. Earlier contributions stay in the repository's history under their authors' names.

## How review works

- **Statement checks** are merged when they follow the format, engage with the actual files, and give legible reasons. A maintainer may ask questions; the verdict stays yours.
- **Explanations** move from `draft` to `ready-for-review` to `reviewed`. A draft may be merged early, which marks the family as claimed on the atlas. `reviewed` means that a named reviewer, who is not an author, has read the whole explanation and checked its mathematics; the reviewer adds themselves under `reviewers` in a pull request.
- **Credits** are merged when a maintainer can open the source and see what the credit describes.
- **Replay receipts** are checked by `scripts/check_contributions.py`, including the log's SHA-256 when the log is in the repository.

## Claiming an explanation

Claim a family with the "Claim an explanation" issue form before you start, so that two people do not write the same explanation for the same reader. Then open a draft pull request with your `explanation.md` at `status: draft`. Someone writing for a different reader can still claim a family that is already claimed; say so in a comment on the existing claim. A claim with no linked pull request after 30 days may be marked stale, and a comment renews it. `STYLE.md` says what a good explanation contains.

## Without git

Every kind of contribution except an explanation has an issue form: open the Issues tab, choose New issue, and pick "Check a statement", "Suggest a credit", "Share a replay" or "Report a problem". A maintainer turns the form into a file credited to you. An explanation is a long document and needs a pull request, which GitHub's web editor can make without installing anything: on your fork, choose Add file, then Create new file.

## Ground rules

- **One contribution per pull request**, so that each can be reviewed and credited on its own.
- **Quote briefly and exactly, and say where from.** Material from openai/math is copyright OpenAI and published under the Apache License 2.0; the atlas quotes it with attribution and links to its source at the pinned commit.
- **The atlas is independent.** It is not affiliated with or endorsed by OpenAI, and it cannot change OpenAI's files. Report problems in them to the atlas, where the report stays on public record.
- **Licences.** Explanations are published under the Creative Commons Attribution 4.0 International licence. Everything else you contribute is published under the repository's licence, the Apache License 2.0. `NOTICE` has the details. By opening a pull request or submitting an issue form, you agree to publication on these terms.
- **Conduct.** Criticise mathematics and files freely and precisely; treat people with respect. `CODE_OF_CONDUCT.md` applies everywhere in the project.

## Files and formats

The exact format of every contribution, field by field, is in `contributions/README.md`. Templates are in `contributions/_templates/`. The checker reports any file that breaks a rule:

```sh
python3 scripts/check_contributions.py
```

## Questions

Open an issue (a blank one is fine) or comment on the pull request you are working on.
