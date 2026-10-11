---
name: explain-a-result
description: Write or review a bounded explanation of a definition, example, lemma, proof step or full argument, for a named reader. Preserve source versions, mathematical scope and point-of-use credit. A person understands and signs the public work.
---

# Explain a result

An explanation should help a particular reader understand a particular piece of mathematics. It may cover one example or lemma. Use the existing family folder and give the piece a precise title. A family can contain several explanations, including alternatives for the same reader.

## Decide the scope

1. Name the reader and the background you expect.
2. Name the exact result, definition or step you will explain. State which surrounding claims you will use as inputs.
3. Open that passage, its definitions, and the relevant earlier sources at the recorded versions. For any claim about formal support, open the challenge, configuration and scope note too.
4. Write the reason or mechanism you think will help the reader. If you cannot justify a step, narrow the scope or submit a precise question.
5. Inspect the destination first. If this family already has a file under this handle, extend or revise its appropriate section; do not overwrite it. Separate bounded explanations can use separate titled sections in that file. Otherwise copy `contributions/_templates/explanation.md` to `contributions/explanations/<family>/<handle>/explanation.md`. Record the pin from `upstream.json`. An issue announcing work is optional and reserves nothing.

## Write

Open with the question the piece answers and the exact claim under discussion. State hypotheses and any conventions that affect meaning. For a long argument, give its plan before the details. Give a concrete example or diagram when it explains the mechanism. Brief routine steps can remain brief for the named reader.

Explain why the important step works and why it is needed. Credit a theorem or idea where you use it. Distinguish the manuscript's claim, the content you have checked, and any imported result you are taking as an input. A checked Lean statement and an accepted replay have separate evidence.

End with the exact reach of this explanation and any unresolved dependency. Include an open question only when it is relevant and supported. Do not invent an original problem, a failed approach, a numerical illustration or a stronger conjecture to fill a heading. Section titles and length follow the mathematics; `STYLE.md` supplies the reading test.

## Working with an agent

An agent may help read, search, draft privately and test examples. Human-authored prose with visibly marked, disclosed tool-drafted passages is permitted. Each author must understand the content and be able to answer questions about their contribution without an AI composing the answer.

Open every suggested source before citing it. Mark missing support visibly with `**Not checked:**` and a concrete description. An HTML comment is not a reader-facing warning. Keep a draft private if no person can confirm it; never invent their identity. Only the authors request review and only an independent reviewer supplies their approval.

## Review

Check whether the explanation helps its named reader follow its stated scope, preserves every relevant hypothesis, justifies the difficult step, gives accurate examples and citations, and accurately describes formal support. A routine source check needs one capable independent reviewer. Prominent full-result claims and disputed content need an additional independent review before a reviewed summary is promoted.

Use `draft`, `ready-for-review` and `reviewed`. Record an authenticated review link and the reviewed content version in the pull request and the explanation's `## Review record` section. A substantive revision needs renewed review. Do not infer a completed review from a name in YAML.

Run `python3 scripts/check_contributions.py <file>`. Resolve errors. Consider style warnings in context; passing a linter cannot establish that a reader understands the argument. Ask a target reader to explain the key step or identify where they got lost. One such observation is useful evidence; it is not a general effectiveness study.
