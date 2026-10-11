# Instructions for AI agents

This file is for AI coding agents (Claude Code, Codex, Cursor and others) working in this repository. People should start with `CONTRIBUTING.md`.

## What this repository is

The Plectis Atlas is an independent reader's atlas to OpenAI's mathematics release, the repository openai/math, read at the commit pinned in `upstream.json`. Scripts compute the machine-derived layer into `data/*.json` and a static site. People add the human layer as files in `contributions/`: explanations of result families, statement checks comparing a Lean statement with its paper theorem, credits to earlier work, and replay receipts from re-running Comparator.

## Start

If the person has not chosen a task, follow `skills/start-here/SKILL.md`. Otherwise open the skill for the task:

| Task | Skill |
|---|---|
| Choose something to do | `skills/start-here/SKILL.md` |
| Compare a Lean statement with the paper's theorem | `skills/check-a-statement/SKILL.md` |
| Write or review an explanation of a family | `skills/explain-a-result/SKILL.md`, with `STYLE.md` |
| Record where an idea first appeared | `skills/trace-a-credit/SKILL.md` |
| Re-run Comparator and record a receipt | `skills/replay-a-proof/SKILL.md` |
| Report a mismatch, an error or a broken link | `skills/report-a-problem/SKILL.md` |
| Change the scripts, data, site or skills | `skills/improve-the-atlas/SKILL.md` |

`skills/` holds the canonical skills. `.claude/skills/` and `.agents/skills/` are generated copies; edit `skills/` and run `python3 scripts/sync_skills.py`.

## Rules

1. **A named person is responsible for every contribution.** Never invent or guess a person's name, GitHub handle, ORCID, background, reviewer or verdict. Ask, and use exactly what they tell you.
2. **You draft; the person signs.** You may draft any section of a check, an explanation or a credit. The person chooses the verdict, and only the person sets `status: ready-for-review`. Only a named reviewer who is not an author supplies a review; promotion to `status: reviewed` needs their authenticated approval of this content version, checked by a maintainer.
3. **Disclose your part.** Write `ai_assistance` truthfully and specifically: which tool, which sections, what the person checked. Never write `none` for work you helped with, including a replay receipt. Do not compose public discussion or review replies on the person's behalf; use final text they provide.
4. **Invent nothing.** Every citation, DOI, arXiv id, theorem number, page, quotation and line number comes from a source you opened in this session. If you cannot open a source, say so and leave the field out.
5. **Quote exactly.** Copy quoted text from the source file at the pinned commit; never retype or paraphrase inside quotation marks. Keep quotations from OpenAI's release short and located. It is published under the Apache License 2.0, and the atlas is independent of OpenAI and not affiliated with it.
6. **Keep the mathematics honest.** Keep what is proved, computed, heuristic and open visibly separate. No sentence is stronger or weaker than its source. Mark every step you could not verify, and list those steps when you hand the draft over.
7. **Leave generated files to their generators.** Never edit `data/`, `site/_build/`, the computed blocks of `README.md`, `.claude/skills/` or `.agents/skills/` by hand. Change the generator and regenerate.
8. **Keep the formats.** Paths and field names in `contributions/README.md` are fixed; the site and the checker depend on them.
9. **Check before you hand over.** Run `python3 scripts/check_contributions.py <file>` on every contribution you create or edit, and fix errors that can be resolved from the evidence. If identity, a source or a human judgement is missing, keep an unsigned draft private and list the missing evidence. Never invent fields to satisfy the checker.
10. **Ask before acting outside the repository.** Pushing, opening a pull request, opening an issue and posting a comment all act under the person's name. Do them only with the person's explicit go-ahead.

## Scope and versions

Begin with a bounded note when the person has fifteen minutes. A short Lean file is not evidence that the mathematics is easy. Record `upstream_commit` on every contribution, and leave earlier contributions attached to the version they actually read. Keep unchecked steps visible in text. Do not use the atlas to generate solutions to open problems, send private contributor material to outside AI services without their agreement, or solicit reviews in other communities.

## Where things are

| Path | What it holds |
|---|---|
| `upstream.json` | The pinned openai/math commit |
| `data/statements.json` | Every Comparator challenge: its Lean text (`lean`), configuration (`comparator`), family (`families`) and linked papers (`papers`) |
| `data/families.json` | Every family: discipline, title, description, `manuscripts`, `statements`, and the Lean scope note (`lean_doc`) |
| `data/manuscripts.json` | Every manuscript: title, abstract, headline statements with source file and line (`statements`), bibliography (`references`) |
| `data/summary.json` | Every count on the site, with its definition |
| `contributions/` | Contributions; formats in `contributions/README.md`, templates in `contributions/_templates/` |
| `STYLE.md` | How to write an explanation |
| `CONTRIBUTING.md` | The guide for people, including the credit and AI policy |
| `scripts/check_contributions.py` | The contribution checker |
| `scripts/sync_skills.py` | Regenerates the skill mirrors |
| `scripts/build_data.py`, `scripts/build_site.py` | The data and site builders |
| `scripts/build_papers.py`, `data/paper_acceptance.json` | Each paper's full reading page, and whether it was accepted (every formula, reference and statement anchor checked) |
| `data/statement_numbers.json` | What each extracted statement prints on its reading page ("Theorem", "1.1"), bound to its file, line and sha256; written by `scripts/build_papers.py` |
| `scripts/lean_render.py`, `scripts/build_lean_xref.py`, `data/lean_xref.json` | The Lean file view: Lean's tokens, name resolution, and each declaration's counterpart in OpenAI's library and Mathlib at the pinned commits |

Links in the data point at github.com/openai/math at the pinned commit. To print one statement's Lean text and configuration:

```sh
python3 -c "import json; s = {x['id']: x for x in json.load(open('data/statements.json'))}['ErdosReciprocal']; print(s['lean']); print(s['comparator'])"
```

## Commands

```sh
python3 skills/start-here/find_work.py --kind check --discipline "<field>"   # candidates ordered by vocabulary count
python3 scripts/check_contributions.py [<file> ...]                           # check contributions
python3 scripts/check_contributions.py --self-test                            # check the templates and the checker
python3 scripts/sync_skills.py [--check]                                      # regenerate or check the skill mirrors
```

All scripts use only the Python standard library and need Python 3.10 or newer.

## Writing

Explanations follow `STYLE.md`. When you draft prose for a person, keep their own sentences where they wrote them, and write plainly: short declarative sentences, every term defined at first use, no slogans. The atlas's own documentation uses British spelling and avoids em dashes.
