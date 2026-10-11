# Linking printed claims to Lean: a convention for formalization.yaml

This page is for anyone who releases formal mathematics: a lab, a Lean project or a single author. It proposes one small, optional convention for the `alignment` block of a [`formalization.yaml`](https://github.com/mathlib-initiative/formalization.yaml) manifest, so that a reader can go from a printed theorem to the exact Lean declaration that states it, and back.

The v0.4 template already allows this. Its `alignment` block is free-form, its table is a suggested shape, and readers must tolerate extra keys. The convention below adds four keys to that table and fixes their meanings. A manifest that uses it stays a valid v0.4 manifest.

## The rows

Each row of `alignment.statements` links one printed assertion to at most one Lean declaration.

| Key | Meaning |
|---|---|
| `source` | The `id` of an entry in the manifest's `sources` list. The paper must be listed there. |
| `location` | Where the assertion is printed. A unique TeX label is enough (`{label: "ap:reciprocal"}`); add `file` when a label repeats. For a PDF without source, give the page and a short exact phrase. |
| `lean` | The Lean declaration, by full name, or `null` when the row records a printed claim with no formal statement. |
| `module` | A Lean module that exposes `lean`. |
| `comparator_config` | When the declaration has a Comparator challenge, its configuration file. |
| `status` | The template's own field, unchanged: the producer's account of proof progress (`proved`, `in-progress`, `not-formalized` and so on). |
| `relation` | How the Lean statement relates to the printed one: `exact`, `stronger`, `partial` or `unassessed`. Leave it out and it reads as `unassessed`. |
| `note` | Required for `partial`: which part, case or consequence the Lean states, and what it leaves out. |

`relation` is kept apart from `status` because they answer different questions. A declaration can be fully proved and still state only a corollary of the printed headline. `stronger` means the Lean statement implies the printed one under the stated reading of its definitions; a stronger conclusion under stronger hypotheses is `partial`. Several rows can support one printed assertion; list them all, and claim that together they cover it only with a note that says why. Partial rows never add up to `exact` on their own.

## An example: family 159

OpenAI's manifest does not yet list the paper for family 159, so the example adds it. This fragment is illustrative. Its relations are `unassessed` because no person has compared the statements yet.

```yaml
sources:
  - title: Quasipolynomial Bounds for Arithmetic Progressions
    authors: [OpenAI]
    id: ../preprints/Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026/paper.pdf
    type: article

alignment:
  atlas_profile: "0.1"
  inventory: partial
  statements:
    - source: ../preprints/Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026/paper.pdf
      location: {label: "ap:reciprocal", file: build/sections/00-introduction.tex}
      lean: OAI.Erdos3.manuscriptReciprocalProgressionTheorem
      module: OAI.Combinatorics.Progressions.Main
      comparator_config: ComparatorChallenges/ErdosReciprocal.json
      status: proved
      relation: unassessed
      note: The selected theorem is the reciprocal-sum corollary.
    - source: ../preprints/Quasipolynomial-Bounds-for-Arithmetic-Progressions-September-23-2026/paper.pdf
      location: {label: "ap:main", file: build/sections/00-introduction.tex}
      lean: null
      relation: unassessed
      note: The quantitative bound is outside ErdosReciprocal, as the scope note lean/docs/159.md says.
```

`atlas_profile` marks a block that follows this page. `inventory: partial` says the rows do not list every claim in the listed papers; it says nothing about the claims left out. `status: proved` repeats the producer's own report, which an independent replay may later confirm.

## What the atlas does with it

The atlas reads the manifest at an exact commit and shows each row on the page of its printed statement. Without these rows it falls back to OpenAI's scope notes and to automatic pairing, which it labels as a candidate.

Three kinds of evidence stay separate on every page: the producer's own report, a named person's comparison of the statements, and an independent Comparator replay. A comparison or replay belongs to the commit it examined. When the release moves, the earlier result stays visible as work on that commit until someone checks the new one. Nothing the atlas records changes the manifest's own `review.status`.

## Handing work back

Contributors to the atlas choose, one contribution at a time, whether a producer may receive it. A contribution that opts in can be handed back as an ordinary file: the base commit, the exact target, the proposed manifest rows or source correction, the evidence, who did the work and how AI was used, its licence and how far it has been reviewed. A maintainer can apply it directly. Where a repository accepts pull requests, the same change can arrive as one.

The same route carries citation corrections and explanations, with their authors credited in their own roles.

## Other manifests

Projects that already describe their alignment another way can keep their format. The atlas plans small readers for Axiom's v0.3 manifests (kept as v0.3), for blueprint links such as Math Inc's, and for statement collections such as Formal Conjectures, where a statement may have no proof in the repository.

The convention on this page is a proposal from the atlas. The formalization.yaml template belongs to its own project, under the Apache License 2.0.
