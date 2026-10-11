---
name: trace-a-credit
description: Use when recording where an idea used in one of the release's manuscripts first appeared, or which earlier human work a step builds on, as a credit file (contributions/credits/<family>/<github-handle>-<short-slug>.md). Covers where to search (the manuscript's own bibliography, zbMATH Open, MathSciNet, arXiv, Google Scholar), how to choose the relation honestly, and the rule that no priority is asserted without a citable source.
---

# Trace a credit

The manuscripts cite earlier work, but a bibliography does not always say which idea came from where, and some steps follow known arguments without naming them. A credit file records one link: this step of this manuscript relates in this way to this earlier work. The atlas shows each credit on the manuscript's page, with the name of the person who traced it.

## What a credit records

- `where`: the exact place in the manuscript, such as "proof of Lemma 4.2" or "equation (2.5) in Section 2".
- `source`: the earlier work, with `authors`, `title` and `year`, and a `doi`, `arxiv` id or stable `url` when one exists.
- `relation`: how the step at `where` relates to the source.

| Relation | Meaning |
|---|---|
| `first-appeared-in` | The source is the earliest appearance found within the search you describe; the atlas does not certify global priority. |
| `uses` | The step at `where` uses a result or method from the source. |
| `special-case-of` | The result at `where` is a special case of a result in the source. |
| `same-argument-as` | The argument at `where` is essentially the argument in the source. |
| `generalises` | The result at `where` generalises a result in the source. |

The body has three to six sentences: the step in the manuscript with its locator, the earlier result with its theorem number and page, how they relate, and how you checked.

Use `uses` for an ordinary verified dependency. Searching for the first appearance is optional and may take substantial specialist work. Read both passages and record the source versions.

## How to search

1. **Pin down the idea.** Write the step at `where` as one precise sentence: a statement with its hypotheses, or a method. Search for that mathematics in the field's standard terms; the manuscript's own wording may be unusual.
2. **Start with the manuscript's own bibliography.** The atlas lists each manuscript's references and where each is used (`data/manuscripts.json`, field `references`); the TeX source upstream is in `preprints/<manuscript>/build/`. Check whether a cited work really contains the step, and find the theorem.
3. **Search the literature.**
   - [zbMATH Open](https://zbmath.org/): free, with reviews and references reaching back to the nineteenth century.
   - [MathSciNet](https://mathscinet.ams.org/): reviews and citations, through a library subscription.
   - [arXiv](https://arxiv.org/): recent preprints.
   - [Google Scholar](https://scholar.google.com/): its "Cited by" link moves forwards in time.
   - [Crossref](https://search.crossref.org/): to find or confirm a DOI.
   - Monographs and surveys in the field, whose historical notes often trace an idea.
   - For problem collections: the [Erdős problems site](https://www.erdosproblems.com/), and the [OEIS](https://oeis.org/) for integer sequences.
4. **Follow the trail both ways.** Move backwards through the references of the earliest source you found, and forwards through works that cite it, until the trail stops.
5. **Read the source itself.** Find the exact theorem, lemma or page. A title, an abstract or a review cannot support a relation on its own.

## Honesty rules

- **No priority without a citable source.** `first-appeared-in` means the earliest appearance you found. Say in the body where you searched and how far back. If you are unsure, use `uses` or `same-argument-as` and say what you could not settle.
- **Exact locators.** Give theorem, page and equation numbers as they appear in the version you read, and name that version (journal or arXiv version) when they differ.
- **Say whether the manuscript already cites the source.** A credit is still useful when it does: it locates the exact result.
- **Credit the mathematics.** Leave out speculation about how a manuscript was produced and about anyone's motives.
- **Invent nothing.** If you cannot find a DOI, leave the field out. Open every reference an AI tool suggests before you use it; such tools produce plausible titles, authors, DOIs and theorem numbers that do not exist.
- **One link per file.** If a step uses three earlier results, write three files.

## Write it up

```sh
mkdir -p contributions/credits/<family>
cp contributions/_templates/credit.md contributions/credits/<family>/<your-github-handle>-<short-slug>.md
```

The slug is a few lowercase words that identify the link, such as `erdos-turan-1936` or `lemma-4-2-weyl`. Fill in the frontmatter and the body, including `upstream_commit` from `upstream.json`, then run:

```sh
python3 scripts/check_contributions.py contributions/credits/<family>/<your-github-handle>-<short-slug>.md
```

Open a pull request with this one file, or use the "Suggest a credit" issue form instead.

The atlas already computes which manuscripts in the collection cite which others. Credit files are for work outside the collection.
