# Contributions

Everything people add to the atlas lives in this folder, one file per contribution. The site reads these files and credits each one by name on the pages it touches. `python3 scripts/check_contributions.py` checks file structure and available source identifiers. People check mathematical content and authenticate reviews.

The [website and map are agent-navigable](https://wcook04.github.io/plectis-atlas/agents.md). The guide explains how to find the relevant family, paper or Lean statement through ordinary links and the map's existing JSON.

Start from a template in `_templates/`. How to do each kind of work is in `CONTRIBUTING.md` and the skills in `skills/`.

```text
contributions/
  explanations/<family>/<github-handle>/explanation.md     an explanation, with figures beside it
  checks/<statement-id>/<github-handle>.md                 a statement check
  credits/<family>/<github-handle>-<short-slug>.md         a credit
  replays/<statement-id>/<github-handle>-<YYYYMMDD>.json   a replay receipt
  replays/<statement-id>/<github-handle>-<YYYYMMDD>.log    its log (or .log.gz; see below)
  _templates/                                              one template per kind
```

Problem reports and claims of an explanation are GitHub issues, made with the issue forms.

## Identifiers

- **Family id**: three digits, from `"001"` to `"377"` (045, 061, 070, 123 and 163 are unused), always written in double quotes in frontmatter (`family: "159"`). Without quotes, YAML reads it as a number and drops leading zeros.
- **Statement id**: the name of a Comparator challenge file upstream, `lean/ComparatorChallenges/<id>.lean`, such as `ErdosReciprocal`. Case matters.
- **Manuscript id**: the folder name under `preprints/` upstream, such as `Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026`.
- **GitHub handle**: your GitHub user name, without `@`.
- **Dates**: `YYYY-MM-DD`.

`data/families.json`, `data/statements.json` and `data/manuscripts.json` list current ids. For the current source version, the checker rejects an id that is not in them, a statement checked against the wrong family, and a manuscript from another family. Historical contributions produce a source-version warning and need checking against that version's sources.

## Frontmatter

Markdown contributions start with YAML frontmatter between two lines of `---`. Use the simple forms the templates use: `field: value`, indented groups of fields, and lists with one item per line starting with `- `. Put a value in double quotes when it contains `: ` or starts with a symbol. Put comments on their own lines.

`upstream_commit` is required in every contribution: the full 40-character lowercase commit of the sources read. Older source versions remain historical and must not be promoted for the current version without renewed review.

`ai_assistance` is required in every contribution, including replay receipts. Write `none`, or one plain sentence saying which tool did what, for example `"Claude drafted the Differences section; I checked every line against the Lean file."`

## Explanation

`contributions/explanations/<family>/<github-handle>/explanation.md`, where `<github-handle>` belongs to one of the authors. Figures and the scripts that draw them go in the same folder.

| Field | Required | Value |
|---|---|---|
| `kind` | yes | `explanation` |
| `family` | yes | family id, in double quotes; must match the folder |
| `title` | yes | text |
| `authors` | yes | a list; each item has `name` and `github`, and optionally `orcid` and `url` |
| `status` | yes | `draft`, `ready-for-review` or `reviewed` |
| `ai_assistance` | yes | `none`, or a plain disclosure |
| `reviewers` | no | a list; each item has `name` and `github` |
| `statements` | no | a list of statement ids |
| `manuscripts` | no | a list of manuscript ids |
| `date` | yes | `YYYY-MM-DD` |

`status: reviewed` needs at least one reviewer, and no reviewer may also be an author. The body is free Markdown; name its reader and exact scope, which may be one definition, example or lemma. `STYLE.md` describes the reading test. A reviewed status also requires an authenticated approval of the current content, linked in the `## Review record` body section and the pull request and checked by a maintainer. Template text left in a draft body is a warning. An empty scaffold is not an accepted explanation, and an announcement of work reserves no family. Template text in the frontmatter, or in the body at any other status, is an error.

## Statement check

`contributions/checks/<statement-id>/<github-handle>.md`, where `<github-handle>` is the reviewer's.

| Field | Required | Value |
|---|---|---|
| `kind` | yes | `statement-check` |
| `statement` | yes | statement id; must match the folder |
| `family` | yes | family id, in double quotes; the family the statement belongs to |
| `manuscript` | yes | manuscript id, from the same family |
| `paper_statement` | yes | where the paper states the result, such as `"Theorem 1.2, label thm:erdos"` |
| `verdict` | yes | `matches`, `stronger-than-paper`, `weaker-than-paper`, `different` or `cannot-tell` |
| `reviewer` | yes | `name`, `github` and `background` (one line) |
| `ai_assistance` | yes | `none`, or a plain disclosure |
| `date` | yes | `YYYY-MM-DD` |

This is a full comparison of the configured theorem names. A smaller observation belongs in a source-linked issue note. The verdict concerns statement correspondence and does not imply a successful replay.

The body has these four headings, in this order, each followed by text: `## What the paper says`, `## What the Lean statement says`, `## Differences`, `## Why this verdict`.

## Credit

`contributions/credits/<family>/<github-handle>-<short-slug>.md`, where `<github-handle>` is the contributor's and `<short-slug>` is a few lowercase words joined by hyphens, such as `erdos-turan-1936`.

| Field | Required | Value |
|---|---|---|
| `kind` | yes | `credit` |
| `family` | yes | family id, in double quotes; must match the folder |
| `manuscript` | yes | manuscript id, from the same family |
| `where` | yes | the place in the manuscript, such as `"proof of Lemma 4.2"` |
| `source` | yes | `authors` (text, or a list of names), `title`, `year`, and optionally `doi` (bare, starting `10.`), `arxiv` (bare id, in double quotes) and `url` |
| `relation` | yes | `first-appeared-in`, `uses`, `special-case-of`, `same-argument-as` or `generalises` |
| `contributor` | yes | `name` and `github` |
| `ai_assistance` | yes | `none`, or a plain disclosure |
| `date` | yes | `YYYY-MM-DD` |

The body, three to six sentences, says how the two relate, with locators on both sides, and how you checked.

## Replay receipt

`contributions/replays/<statement-id>/<github-handle>-<YYYYMMDD>.json`, a single JSON object. The date in the file name is the receipt's `date`.

| Key | Required | Value |
|---|---|---|
| `kind` | yes | `"replay"` |
| `statement` | yes | statement id; must match the folder |
| `upstream_commit` | yes | the full 40-character openai/math commit you ran |
| `lean_toolchain` | yes | the contents of `lean/lean-toolchain`, such as `"leanprover/lean4:v4.34.1"` |
| `comparator_commit` | yes | the Comparator commit you built |
| `lean4export_commit` | no | the lean4export commit you built |
| `landrun_commit` | no | the landrun commit you built |
| `result` | yes | `"accepted"`, `"rejected"` or `"error"` |
| `axioms` | yes | a list of axiom names: the `permitted_axioms` Comparator enforced |
| `wall_time_seconds` | yes | a number |
| `machine` | yes | `{"os": ..., "cpu": ..., "ram_gb": <number>}` |
| `contributor` | yes | `{"name": ..., "github": ...}` |
| `log_sha256` | yes | the SHA-256 of the full Comparator log, 64 lowercase hexadecimal characters |
| `ai_assistance` | yes | `none`, or a plain sentence saying which tools did what |
| `notes` | no | text |
| `date` | yes | `"YYYY-MM-DD"` |

Retain the full log. A checksum without a retrievable log does not support a public claim of an accepted or rejected replay. A log under 2 MB may sit beside the receipt as `<github-handle>-<YYYYMMDD>.log` or `.log.gz`; the checker then confirms that `log_sha256` matches it.

## Checking

```sh
python3 scripts/check_contributions.py                 # every contribution
python3 scripts/check_contributions.py <file> ...      # only these files
python3 scripts/check_contributions.py --self-test     # the templates and the checker itself
```

Errors must be fixed before a pull request is merged. Warnings point at things worth a second look, such as a style slip in an explanation, a manuscript withdrawn upstream, an older source pin, or a missing replay log. Use `--strict` for fresh submissions when all required datasets are present. The checker does not fetch external logs; a maintainer must inspect an externally retained log before accepting its evidence. Review historical or editorial warnings explicitly; do not rewrite a source pin to suppress one.

## Licences

Explanations are published under the Creative Commons Attribution 4.0 International licence. Everything else in this folder is published under the repository's licence. `NOTICE` at the repository root has the details.
