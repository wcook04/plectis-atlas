---
name: start-here
description: Help a person contribute one useful source-linked note, or choose a larger task they can support. Prefer a passage already being read; agents prepare private drafts and the person signs.
---

# Start here

Start from the page or mathematical question the person brought. Ask only for missing context that changes the task: their relevant background and available time. Ask about Lean or hardware only if they choose statement comparison or replay.

For a first visit or a fifteen-minute budget, suggest one note on a source passage: clarify a definition, identify a missing reason, check an example, locate a cited result, or ask a precise question. Use the **Suggest a change or ask a precise question** issue form. The note needs a location, the observation, and what supports it. A settled verdict is optional work for later.

If no passage is selected, use `python3 skills/start-here/find_work.py --disciplines`, then the relevant `--kind` and `--discipline` query. Treat the output as candidates. Definition counts measure local vocabulary, not mathematical difficulty, review demand or prerequisite knowledge. Inspect the actual sources before suggesting an item. Do not describe the ranking as easiest first.

Offer one item and one alternative with their source links. Prefer a source-accessible task whose output and stopping point fit the person's background. A source note should answer one question; a full check follows `check-a-statement`; an explanation can cover one lemma or example and follows `explain-a-result`; a literature link follows `trace-a-credit`; a replay follows `replay-a-proof`.

Working announcements are optional and nonexclusive. An empty directory, an inconclusive check or someone else's draft is not a reason to prevent useful work. Inspect existing contributions before proposing a duplicate.

Agents draft privately until the person supplies their identity and confirms the content. Do not invent a signature or verdict to make validation pass. If a source is absent, name it and produce a precise reading note or question. Never copy a teaching example as if a person independently checked it.

For repository files, give the path, copy command and validation command. Read `contributions/README.md`; record `upstream_commit` and truthful `ai_assistance`. End with the particular useful result, the evidence opened, and any question still unresolved. Do not promise acceptance, a fifteen-minute full verdict, or automatic review credit.
