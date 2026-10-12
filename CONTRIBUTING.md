# Contributing to the Plectis Atlas

Help the next reader understand one piece of the mathematics. A useful contribution can be a correction, an example, a precise question, a source for a step, a statement comparison or an explanation. Choose a part you can read and support.

## Start with one note

On the page you are reading, choose **Suggest a change**, or open an issue with the **Suggest a change or ask a precise question** form. Give three things:

1. The page or source passage you mean.
2. One correction, question, example or suggested explanation.
3. What you checked, with the source or calculation that supports it.

Say how you used AI, or write `none`. GitHub supplies your handle; a different public display name is optional. You can do this without installing git, Lean or an AI tool.

For a first visit, give one passage about fifteen minutes. If you cannot settle it, stop at a precise question; that is a useful note too.

A maintainer checks the note and either incorporates it, asks a specific question, or explains why it does not help. An incorporated note links to its source issue and credits its contributor beside the changed explanation or reference. Submission history stays visible.

## Choose a larger task when it fits

| Task | Scope | Guide and destination |
|---|---|---|
| Explain something | One definition, example, lemma, proof step or complete argument, for a named reader | `skills/explain-a-result/SKILL.md`; `contributions/explanations/<family>/<handle>/explanation.md` |
| Check a statement | Compare all theorems listed in one challenge configuration with their precisely located paper statements | `skills/check-a-statement/SKILL.md`; `contributions/checks/<statement>/<handle>.md` |
| Locate an earlier result | Connect one step to a result or method in a source you opened | `skills/trace-a-credit/SKILL.md`; `contributions/credits/<family>/<handle>-<slug>.md` |
| Replay a check | Run the specified Comparator configuration and retain the full log | `skills/replay-a-proof/SKILL.md`; `contributions/replays/<statement>/<handle>-<YYYYMMDD>.json` |

Use the issue forms if you prefer. A maintainer can prepare the repository file and ask you to confirm its contents and credit. For an explanation, GitHub's web editor can create or edit the Markdown file on your fork. An issue announcing work is optional.

For a repository contribution, copy the relevant template, fill it in, then run:

```sh
python3 scripts/check_contributions.py <path-to-your-file>
```

The command checks format and available source identifiers. It cannot establish mathematical correctness, a person's identity, or whether a claimed review happened. Keep unrelated work in separate pull requests; a correction and its supporting evidence belong together.

## Sources and versions

Each incorporated repository contribution records the full `upstream_commit` it used. A page-linked note can arrive first; the maintainer confirms its actual source version before incorporation. Copy it from `upstream.json` after opening that version's sources. Locate the exact paper statement and every relevant definition; a scope note is evidence of the release author's intended coverage. It does not replace reading the paper.

An older contribution remains attached to its recorded version. A new upstream release does not renew its review. Maintainers keep it visible as work on an older version until the relevant sources and review have been compared again. Never replace its pin just to remove a warning.

## Responsibility and AI assistance

Agents can help locate sources, draft private notes, check examples and run tools. Read and understand the content you submit, open the cited sources, and disclose which tools did what in `ai_assistance`. Write public discussion and review replies in your own words. Explain the reasoning for a mathematical judgement yourself.

An agent must leave an unsigned draft private when a person has not confirmed it. It must list missing sources and unchecked steps visibly. It must never invent an author, a reviewer, expertise, a verdict or a successful run. Templates initially say `none`; replace this whenever any AI assistance occurred.

Keep AI drafts private until you can support the proposed contribution. Human-authored prose with visibly marked, disclosed tool-drafted passages is permitted. The author must still understand and answer for that passage. Source-specific uncertainty belongs in the submitted note; it must not be hidden in an HTML comment.

New contributors should keep one substantive item awaiting review at a time. A maintainer can agree to a small batch after seeing a useful example. Corrective reports about an existing contribution can always be raised. Do not submit generated bulk explanations or send agents to other communities to solicit reviews.

## What review means

A statement check records its signer's judgement about correspondence between specified statements. It does not report that a proof was replayed. A replay reports one tool run. An explanation records understanding of its stated scope. These appear separately.

Before promoting a statement comparison or explanation to a reviewed result on the site, obtain an independent review of the relevant content from a person who can assess it. A short description of relevant experience is useful; a degree is not required. For a disputed comparison, a definition hole, or a prominent full-result claim, obtain a second independent review before promotion. A small source correction needs a maintainer who has checked that source.

The reviewer writes from their own account, identifies the content and commit they read, and explains the scope of their review. A name typed into frontmatter is insufficient. Maintainers check that the recorded approval covers the current version and that the reviewer is not an author. A substantive edit needs a fresh approval. Explanations retain the existing `draft`, `ready-for-review` and `reviewed` values; `ready-for-review` is the authors' request for review.

If reasoned reviews disagree, show the disagreement and both reasons. Do not decide it by a vote count. A material, source-specific challenge suspends the affected reviewed summary while it is assessed. Keep unaffected contributions visible. Corrections and withdrawals preserve the earlier version and link the replacement or reason.

## Working on an explanation

Announce work if coordination would help: name the passage, your intended reader and a draft link if you have one. This reserves nothing, including against another explanation for the same reader. After a week without a progress link, the announcement may be marked inactive; returning to it is welcome. An announcement does not count as an explanation.

Credit names the original sources, explanation authors, reviewers and contributors to later improvements separately. Record the date and link of a public exposition. The atlas records this history; it does not award mathematical priority or transfer authorship of an upstream result. A contributor may volunteer to maintain an explanation without accepting an indefinite duty.

## Ground rules

Contributing is voluntary, and declining needs no explanation. The atlas serves its readers independently of OpenAI. It makes no promise of payment or a reply from a lab. It does not send contributions to other organisations on a contributor's behalf; any such action needs that contributor's agreement. Existing public licences still apply to reuse by third parties.

Credit sources at the point of use. Describe `first-appeared-in` as the earliest source your stated search found, and leave priority unsettled unless the evidence supports more. `uses` is sufficient for most useful source links.

Explanations use CC BY 4.0; other contributions use the repository's Apache-2.0 licence. `NOTICE` gives the terms. Keep others' private material private, quote briefly, and respect the rules of communities you visit. `CODE_OF_CONDUCT.md` applies. Formats and templates are in `contributions/README.md`.
