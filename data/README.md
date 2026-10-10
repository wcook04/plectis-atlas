# The atlas dataset

Plain JSON, rebuilt from the openai/math commit in `../upstream.json` by `python3 scripts/build_data.py`. Nothing here is edited by hand. Quoted text (titles, abstracts, theorem statements, Lean files, scope notes) is copyright OpenAI under the Apache License 2.0; see `../NOTICE`.

## Files

| File | One record per | Key fields |
|---|---|---|
| `summary.json` | the release | every headline number, each with a definition under `definitions`; OpenAI's own reported figures under `upstream_reported`, quoted with their source |
| `disciplines.json` | discipline (17) | `name`, `families` in OpenAI's catalogue order |
| `families.json` | result family (372) | `id` ("001" to "372"), `discipline`, `title`, `description` (OpenAI's text, inline maths as `\( \)`), `manuscripts`, `statements`, `lean_doc` (OpenAI's per-family Lean scope note) |
| `manuscripts.json` | manuscript folder (749: 719 current, 3 withdrawn, 27 earlier editions) | `id` (the upstream folder name), `family`, `status`, `title`, `date`, `abstract`, `pdf_url`, `statements`, `references`, `rests_on`, `cited_by_in_collection`, `has_lean` |
| `statements.json` | Comparator statement file (416) | `id` (challenge name), `lean` (full file), `sha256`, `imports`, `vocabulary`, `vocabulary_count`, `comparator`, `main_result`, `solution`, `families`, `labels`, `papers` |
| `graph.json` | citation between two manuscripts in the collection (578) | `source`, `target`, `target_latest`, families and statuses |
| `works.json` | outside work cited (about 11,000) | `id` (DOI, arXiv identifier or normalised title), `record`, `cited_by` |
| `history.json` | dated section of OpenAI's `history.md` | `date`, `markdown` |

## How the fields are made

- **Paper statements** (`manuscripts[].statements`) are the theorem-like environments in each manuscript's TeX sources after `\input` files are expanded: theorems, propositions, corollaries, conjectures, questions and hypotheses. Each carries its source `file` and `line`, its `label`, the TeX `text`, and a `sha256` of the whitespace-normalised text. `headline` marks the theorem-like statements before the second section (or named as main results). Lemmas are counted in `lemma_count`.
- **References** are the bibliography entries a manuscript actually cites, from its `.bib` files or `thebibliography`. `uses` lists where each is cited: the file, line, section and, when the citation sits inside a statement or a proof, which one.
- **Rests on** (`rests_on`) lists the manuscripts in the collection that a manuscript cites, followed through any later editions, with each one's status and whether it is an accompanying paper of a family with a Lean statement (`has_lean`).
- **Statement vocabulary** (`statements[].vocabulary`) lists the definitions, abbreviations, structures, classes, inductive types, instances, notation, macros and axioms that a Comparator challenge file introduces. Comparator certifies a solution against exactly this file, so each item is something a reader checks.
- **Lean coverage** of a manuscript (`has_lean`) means OpenAI's Lean scope note for its family (`lean/docs/NNN.md`) lists it as an accompanying paper and links at least one Comparator statement. It is a different measure from OpenAI's reported share of formalised top-line results, which `summary.json` quotes separately.

## Known limits

- Theorem numbers such as "Theorem 1.2" are not computed; statements are identified by label, file and line, and link to the PDF.
- Distinct outside works are matched by DOI, then arXiv identifier, then normalised title, so a few works cited in different forms may count twice.
- The pairing of a Lean statement with the exact paper theorem it formalises is left to reviewers (see `../CONTRIBUTING.md`); the site shows the paper's headline statements beside the family's Lean statements.
