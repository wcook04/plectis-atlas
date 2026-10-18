# Scope coverage of the Lean statements

`scope_coverage.json` records, for each of the 416 Comparator statements in openai/math at the commit pinned in `../upstream.json`, a draft reading of how much of the headline result of its accompanying paper or papers the statement asserts. An AI agent made it from OpenAI's scope notes, and no person has reviewed it.

One family shows why this needs recording. In family 159 the paper's headline theorem is a quasipolynomial bound for subsets of {1, …, N} with no k-term arithmetic progression. The Lean statement `ErdosReciprocal` states a corollary of that theorem, Erdős's reciprocal-sum conjecture, and OpenAI's scope note `lean/docs/159.md` says so: "The selected theorem is the reciprocal-sum consequence." Its row has class `consequence`.

## The classes

| Class | The Lean statement states |
|---|---|
| `headline` | a headline theorem of an accompanying paper, as stated, allowing harmless formalisation choices |
| `headline-part` | one part or case of a multi-part headline theorem; the other parts are outside this statement |
| `consequence` | a corollary or application of the headline theorem rather than the theorem itself |
| `weaker` | a weaker form of the headline: fewer cases, worse constants, extra hypotheses, or an eventual or qualitative version of a quantitative claim |
| `supporting` | an auxiliary or supporting result outside the headline results, including the five supporting comparisons named in `lean/ComparatorChallenges/README.md` upstream |
| `unclear` | something the materials do not settle; the explanation says what would |

A paper's headline theorem is its main result as the paper states it. A statement the paper derives as a corollary counts as a consequence, even when it appears in the introduction. A few rows carry a second class in `secondary_class` when one statement genuinely does two things, for example supporting estimates bundled with one case of the main theorem.

## The fields of a row

| Field | Content |
|---|---|
| `statement` | the Comparator challenge name, as in `lean/ComparatorChallenges/<statement>.lean` upstream |
| `family` | the family id, as in `data/families.json` |
| `class` | one of the six classes above; `secondary_class` is optional |
| `scope_quote` | one or more consecutive sentences copied from OpenAI's scope note `lean/docs/<family>.md`, an exact substring of the note |
| `paper_headline` | the manuscript statement the class is judged against, as `manuscript`, `label`, `file` and `line`; for `headline` and `headline-part` rows it is the paper statement the challenge states, for `consequence` and `weaker` rows the headline theorem the challenge's statement follows from or weakens, and for `supporting` rows the headline result supported |
| `explanation` | one or two plain sentences saying what the statement asserts and what lies outside it |
| `confidence` | `high`, `medium` or `low` |
| `needs_specialist` | `true` when the class depends on mathematics the reading could not settle |

`label` is `null` where the manuscript's TeX gives the statement no label the dataset could read; `file` and `line` still locate it. When one challenge file states the headline theorems of several accompanying papers, `paper_headline` names one of them and the explanation names the others.

## How it was made

The file is an AI-assisted reading of OpenAI's own material. An AI agent (Claude Code) read, for every statement, OpenAI's scope note for the family, the challenge file with its `.json` configuration, and the theorem-like statements in the introduction of each accompanying manuscript (`data/manuscripts.json`, statements with `headline` true), and consulted a manuscript's TeX source where these were not enough. Every row quotes the scope note, and the checker below confirms each quotation against the note at the pinned commit.

Where a scope note and a challenge file differ, the class follows the challenge file and the explanation says so. Where a challenge file has Comparator definition holes (definitions whose bodies Comparator takes from OpenAI's library) or states its claim through a placeholder axiom, the explanation mentions it.

No named person has yet reviewed the rows. Read `confidence` and `needs_specialist` before relying on a row.

## What it is not

This is a draft coverage classification. It says which paper result each Lean statement is aimed at and how much of that result the statement asserts. Whether the Lean statement means what the paper's sentence means is a separate question, which no row answers. When Comparator accepts a proof under a challenge's configuration, the proof establishes that challenge statement using only the allowed axioms, with any configured definition holes filled from OpenAI's library. Neither Comparator nor this file checks the formal statement against the paper. That comparison is a statement check (`../skills/check-a-statement/SKILL.md`). A row with class `headline` is a claim about coverage; it records no check of the statement.

`data/statements.json` also carries `main_result`, copied from OpenAI's `lean/formalization.yaml`. That list and this classification answer different questions, and they are not expected to agree row by row.

## Confirming or correcting a row

Reviewers confirm or correct rows through the atlas's check-a-statement contributions. Write a statement check for the statement, following `../skills/check-a-statement/SKILL.md`; if you find that the statement covers more or less of the paper than its row says, say so in the check's Differences section. A maintainer then updates the row, keeps its `scope_quote` an exact quotation of the note, and runs the checker. A mismatch can also be reported with the "Suggest a change or ask a precise question" issue form.

## Checking the file

```sh
python3 curated/check_scope_coverage.py --upstream ../openai-math-upstream
```

Without `--upstream` the checker uses `$OPENAI_MATH_UPSTREAM`, then `../openai-math-upstream` beside the atlas, as `scripts/build_data.py` does. It reads the scope notes at the pinned commit with `git show`, so the checkout may be at any later commit. It checks the schema, one row for every statement id in `data/statements.json`, the class names, every quotation against its note, and every `paper_headline` file, line and label against the manuscript sources, then prints the number of rows in each class. It exits with status 1 on any failure and 2 when the upstream checkout cannot be found. It uses only the Python standard library.

## Quotations and licence

The quotations in `scope_quote` and the statement labels are copied from openai/math, which is copyright OpenAI and published under the Apache License 2.0; see `../NOTICE`. The atlas is independent of OpenAI and not affiliated with it.

## Atlas source notes on outside reports

An outside check card may retain a historical coverage description that needs
qualification against the Atlas source pin. Keep the original report's words
and version intact. An optional `atlas_source_note` within that card records
Atlas's separate `text`, `inspected` date, exact `source_pin` and labelled source
`links`. It must disclose AI assistance when applicable and must not imply a
new proof replay or human mathematical review. Family pages show this note
separately from the attributed report, including in its inspection record.

Change the curated input, regenerate the baseline data, capture the committed
Atlas revision in Statement Map, build and validate its reader export, then
re-vendor that export. A frontend-only change to an imported packet would break
its provenance and hashes.
