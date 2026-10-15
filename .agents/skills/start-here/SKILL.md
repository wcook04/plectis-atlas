---
name: start-here
description: Help a person or agent choose one useful source-linked note or a larger task. Agents may report their own unreviewed observations; a person confirms and signs contribution files and mathematical verdicts.
---

# Start here

Start from the page or mathematical question already chosen. If a person brought it, ask only for missing context that changes the task: their relevant background and available time. Ask about Lean or hardware only if they choose statement comparison or replay.

For a first visit or a fifteen-minute budget, suggest one note on a source passage: clarify a definition, identify a missing reason, check an example, locate a cited result, or ask a precise question. A person may use the **Suggest a change or ask a precise question** issue form. An agent reporting its own source, rendering, navigation or reproduction observation may use the [unreviewed agent observation form](https://github.com/wcook04/plectis-atlas/issues/new?template=agent-observation.yml) if its operator and platform permit posting. Follow `skills/report-a-problem/SKILL.md` for either route. The note needs exact public source and page locations, revisions, the observation, checks actually done and uncertainty. A settled mathematical verdict is work for the signed check route.

If no passage is selected, use `python3 skills/start-here/find_work.py --disciplines`, then the relevant `--kind` and `--discipline` query. Treat the output as candidates. Definition counts measure local vocabulary, not mathematical difficulty, review demand or prerequisite knowledge. Inspect the actual sources before suggesting an item. Do not describe the ranking as easiest first.

Offer one item and one alternative with their source links. Prefer a source-accessible task whose output and stopping point fit the person's background. A source note should answer one question; a full check follows `check-a-statement`; an explanation can cover one lemma or example and follows `explain-a-result`; a literature link follows `trace-a-credit`; a replay follows `replay-a-proof`.

Working announcements are optional and nonexclusive. An empty directory, an inconclusive check or someone else's draft is not a reason to prevent useful work. Inspect existing contributions before proposing a duplicate.

Agents keep drafts of signed contributions private until a person supplies their identity and confirms the content. Do not invent a signature or verdict to make validation pass. An agent's own observation remains unreviewed, attributed to its disclosed public account; disclose whether an operator directed or reviewed it without naming them unless authorised. If a source is absent, name it and produce a precise reading note or question. Never copy a teaching example as if a person independently checked it.

For signed repository contribution files, give the path, copy command and validation command. Read `contributions/README.md`; record `upstream_commit` and truthful `ai_assistance`. An unreviewed agent observation is an issue, not a contribution file. End with the particular useful result, the evidence opened, and any question still unresolved. Do not promise acceptance, a fifteen-minute full verdict, or automatic review credit.
