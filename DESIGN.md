# How the Plectis Atlas looks and reads

The design contract for the site. Read it before changing a page; record here
what a page teaches, so the next pass starts from it.

## The read

A public reading room for OpenAI's mathematics release, for mathematicians
first and AI researchers second. It is set in a publication register and kept
as quiet as a good journal. It takes one risk: the front door is the whole
release, drawn as one map that opens into every family, with a list beside it
that reads the map in words. Everything else stays
calm so that the map, and the mathematics, are what a visitor remembers.

The release arrives as 719 papers, 416 Lean files and a catalogue. A
mathematician wants something smaller and sharper: what exactly is claimed,
whether the Lean says the same thing, and who has checked what. The site exists
to answer those questions for any result in under a minute, and to make the
size of the release feel like something a person can walk through.

## What a reader can do for any result

Every family page answers these, in this order. The home page promises them.

1. **The claim.** Read the main theorem exactly as printed, with its number, its hypotheses and its place in the paper.
2. **The formal statement.** See the Lean statement beside it, and whether outside readers judge that it states all of the theorem, part of it or less.
3. **The checks.** See who has re-run what, with what result, and what is left for a reader to check by hand.
4. **The reading.** Open the paper as a page, at the passage.
5. **The connections.** Follow what it cites inside the release, and what cites it.
6. **The problems.** See findings, corrections, disagreements and withdrawn papers.
7. **The next step.** Explain it, check it or correct it, credited by name, with or without an AI account.

This list is grounded in mathematicians' own writing about AI-generated
mathematics. The About page paraphrases those essays and links them.

## No symbol codes

Every drawn thing is one concrete object (a family, a paper, a theorem, a Lean
statement), labelled in words on the drawing. Colour means one thing in a
drawing, said in one line. A state is a sentence beside the object it
qualifies. Never a composite mark that packs several facts into one symbol, never
a key the reader must learn before the page makes sense, never treemap or
stock-market tile grids. (12 October 2026: a "family mark" with papers, a
reader-split diamond, tones and rings was rejected as a code to crack, and the
old tile map as just as bad. The Plectis maths site is the model: a problem is
introduced in words with its mathematics typeset, its status is a sentence, and
its map labels every problem with plain counts.)

## The front door: the map and the list

The release on one screen as our map, with a readable list beside it, the way
a good maps app pairs a map with its results. 700-plus results need both: the
map for where things are, the list for reading them.

- **The map is an illustrated chart, never a to-scale one.** Every object a
  reader can act on is big enough to read and carries its name; the space is
  used; geometry is kept only where it means something. (Will rejected the
  earlier wheel, 12 October 2026: tiny dots on rings, an empty centre and a key
  needed to decode them read as "an arbitrary orbiting thing".)
- **The release:** the seventeen disciplines as labelled regions packed to fill
  the stage, each with its name and counts (families, how many with Lean) and
  its families as discs coloured by one meaning (what the outside readers find
  the release's Lean states), each colour named in one line. The region is what
  a reader chooses.
- **A discipline:** its families as large discs filling the stage, each with
  its title written inside and tinted by its evidence colour. Pointing at one
  draws its citations to its neighbours (brick out, grey in) and steps the rest
  back; a click opens the family's page. Every level fits its stage, so the map
  has no zoom or pan.
- **The list** (the left panel): what the site is for in one sentence, then
  search with one line saying what it finds, then the worked example (π), the
  release in four figures each saying what it counts (linked once, to how they
  are counted), more places to start (and the families the groups disagree
  on), the subjects with a thin bar of their
  colours, the full colour key with counts, and what changed since the release.
  Choosing a subject zooms the map to it and lists its families as plain
  entries: title and one short line, and on pointing the claim's first sentence with its mathematics typeset
  (credited to OpenAI's catalogue), and one sentence saying what the Lean
  states and who checked it. Pointing at an entry lights its node; clicking
  opens the family's page.
- **One place to read a family: its page** (19 October 2026). Clicking a dot
  used to replace the map with a board of cards while the list showed a second
  summary and a third "Open the family page" route; Will could not tell how the
  three related. A family, paper, theorem or Lean statement chosen anywhere on
  the map now opens its own page, and an older `#o=f:…`, `#o=p:…`, `#o=r:…` or
  `#o=l:…` address is replaced by that page. The map holds only the release and
  its subjects.
- **Hover never covers the drawing** (19 October 2026). A floating card beside
  a hovered subject sat on the very dots the reader was reaching for. What the
  pointer names is written on its own line under the drawing, so the
  instruction above never disappears and the bar never changes height.
- **The colour key stands on the map** (UX pass, 19 October 2026). A "Map key"
  button that opened a panel had no visible effect at desktop width, and the
  sidebar key fell below the fold at 1440x900. The bar over the drawing now
  holds the instruction and a row of colour chips (short name, count at this
  level, the full sentence as its title) at the release and in a subject. The
  layout packs below that bar and above the hover line, subject circles start
  at the top of the stage and rows spread down it, and the explorer stands in
  the site frame so the sidebar starts on the header's left edge.
- **The front door's example is the evidence in miniature** (24 October 2026,
  Klara Kaleb's feedback). The four question-and-answer paragraphs became four
  labelled rows: the paper's inequality and corollary as stated, the Lean
  statement's name, each group's own label with the omission both name, and the
  Comparator reports; the action reads "See the evidence side by side". The
  build checks below still stop it if family 017 stops fitting the rows.
- **The front door teaches by one worked example** (round 2, 19 October 2026).
  Under the search, π's family (017) is taken through the whole route in four
  short sentences: what OpenAI's catalogue says the paper proves; the one Lean
  statement chosen for checking (PiExponent); each group's own label (MathVet
  "full", cert-machine "NARROWER — DECLARED") and the omission both name, which
  is why its dot has the "groups disagree" colour; and that both report
  Comparator accepted the proof of that statement, which is not the paper's
  whole claim. Then one filled action opens the family. `example_html` takes
  the names, labels and Lean name from Statement Map and stops the build if the
  family no longer fits the sentences. The π dot wears a quiet ring on the map
  at the release and in its subject, and the idle hover line names it. The four
  figures say what each counts (Lean is defined in the row where it first
  appears). The key on the map asks the colour's one question ("do MathVet and
  cert-machine say the family's Lean states the whole result? It does not say
  whether a proof is right") and each chip answers it ("yes, both groups",
  "they disagree, as for π", "no Lean released", so a white dot never reads as
  a failure). The sidebar's full key now stands above the subjects, and two
  small buttons under the purpose line open the guide and the π family.
  At a subject the citation inks are named in the sentence that says how to
  make arrows appear, never as a legend for arrows not yet drawn.
- **A subject's trail is the site's breadcrumb**: `Map / Number theory`, built
  with atlas.css's `.trail` look, every crumb a link except the subject (plain,
  `aria-current="page"`). Each family row's second line is a sentence, never a
  code: "Family 017: 1 paper, 1 Lean statement. MathVet and cert-machine
  disagree about what its Lean states." The subject's lede says what each row
  shows.
- **Formerly, a family board of cards** in the Zenith Code Map Focus grammar:
  its papers as columns of results, each statement typeset, the Lean statements
  paired with them joined beneath, "Cited by" families on the left and "Cites"
  on the right, with a hover card beside whatever the pointer named. Both were
  retired on 19 October 2026 and their code removed the same day; a family is
  read on its own page, and a click still always leads to mathematics, never to
  a status page.
- Previous and next under the breadcrumbs move between siblings at the current
  level; arrow keys do the same and keep a visible keyboard focus target.
- Hover explains in the caption, click opens, Escape steps back. Selection
  lives in the URL (`#o=d%3Anumber-theory`); Back and Forward restore it;
  older `#d=...&f=...` links still land. Keyboard: Tab, arrows, Enter, Escape.

## What each view shows first

From the outside review of the first rebuild screenshots (12 October 2026):
give space and emphasis to what the current task needs, at each depth.

| View | First read | Second read | Third read |
|---|---|---|---|
| Release | Disciplines and the size of the corpus | Families and what their Lean states | A route into a chosen object |
| Discipline | Readable family titles | Where they sit and how they connect | The selected family's claim |
| Family or theorem | The selected statement, typeset | Its paper and its Lean counterpart | The mathematical neighbourhood |
| Families list | Comparable rows | How their evidence differs | Filters that refine the question |
| Lean statement | The formal statement and its hypotheses | The paper passage and the pairing's state | Sources, runs, further inspection |

- Labels are horizontal and collision-managed, never rotated. The selection
  always keeps its full label.
- Level of detail follows scale: a family is a plain disc until it is large
  enough for its inner map to be read.
- At theorem focus the reading pane widens (about 40 to 45 per cent of the
  workspace) and the map refits. The mathematics never shrinks to fit.
- A list beside the map is an index: a title and one status line per row, and
  the active row expanded.
- Escape and empty map space return through the same browser entry as Back
  when that entry is the previous selection. Breadcrumbs can skip levels;
  their map ancestors remain separate visits. A direct link stays within the
  map when stepping up. A click during a pending return is retained.
- An arrow overlay follows its content box, so moving to a narrower panel or
  shorter paper page removes obsolete scrolling space.
- While a detail packet loads, the sidebar retains one completion subscriber
  per discipline. Only its latest visit refreshes when it arrives; revisiting a
  node cannot queue repeated typesetting or layout work.

## The thread

The line from a paper's theorem to the Lean statement paired with it. Wherever
two statements sit side by side, the qualification sits at the join, because
adjacency itself makes a claim.

| Recorded pairing | Line | Words at the join |
|---|---|---|
| Candidate pairing (shared words) | dashed steel | Found by the words the two share; nobody has reviewed whether they state the same thing. |
| Cited in the Lean source | solid steel | The Lean source cites this theorem by its label; nobody has reviewed the match. |
| Declared by the release's manifest | solid steel | The release binds them; nobody has reviewed the match. |
| Unresolved, or several targets | none | No theorem is paired; the alternatives are listed with their reasons. |
| Reviewed by a named person | solid, heavier | Their recorded relation, their name, the version they reviewed. |

A heading that pairs two statements carries the pairing's state where the
pairing is asserted ("Possible Lean match: suggested from shared wording;
correspondence not reviewed"). A reported re-run is evidence about the Lean
statement it ran, never about the paper theorem beside it, and never upgrades
an unreviewed pairing. Outside readings concern the family's headline as a
whole and sit under a heading that says so.

## Reading a family

The family page is the beginning of mathematical work, not of an audit.

**The first tab is the evidence itself** (24 October 2026, after Klara Kaleb's
feedback: the site "feels quite text-heavy, with some explanations repeated";
she wanted "the paper's claim, the formal statement, and what each assessment
says, with the detailed explanations available when needed"). The tab is called
**Evidence** and opens on one sheet: on the left the paper's statement exactly
as printed (the theorem the selected Lean statement is paired with, else the
backend's candidate, else OpenAI's description in its place); on the right the
selected Lean statement's own text. The divider between them is the thread
(dashed for a candidate found from shared wording, solid where the Lean source
cites the theorem or OpenAI declares the link), and the pairing's qualification
runs along the sheet's foot. Other statements matching OpenAI's description that
no Lean statement is paired with sit under the paper's theorem with OpenAI's own
sentence on what its Lean leaves out, so an omission such as π's Flint–Hills
corollary is visible beside the Lean rather than described. Under the sheet,
one card per outside group, side by side: its label in plain words, its own term,
its reason quoted, its Comparator run. OpenAI's description and the papers close
the tab. Definitions of Lean, Comparator and the groups are glossary links on
the words, not paragraphs; the qualification that no review is recorded is said
once, at the join. A family with no Lean puts its papers in the sheet's right
half under one sentence saying so. `board_pair` and `groups_board` in
`scripts/family_page.py` own this; `scripts/tests/test_family_page.py` pins the
board and the Lean text beside the paper. Paragraphs below describe earlier
passes; where they disagree about the first tab, this one stands.

A fresh-eyes critique the same day refined it. The sheet's foot says once how
the two statements came to stand together ("Atlas put these side by side
because they share wording; nobody has reviewed whether they say the same
thing") and then, on the first screen, what each group finds, each name linking
to its card. The groups compared the Lean with OpenAI's description, so the
description is quoted at the head of their section, introduced as what they
compared; it is never implied that they reviewed the pairing. The board never
repeats the no-review sentence or Comparator's limit; the card says whose proof
of what was run. A group's note is quoted whole, its own term is a small tag
beside its finding, and with several Lean statements each run label stands
beside the statements it was given for. With no Lean the paper takes the whole
sheet. On a phone the Lean follows its own theorem and the tab bar fades at its
edge. Declined: having Atlas explain a group's label in its own words (MathVet's
"full" concerns the headline), since Atlas does not characterise anyone's work.

**The first screen answers the page's question** (19 October 2026). The page
was 8,800px tall at 1440×900, and the comparison of what each group said
started on its fourth screen. Now, under the title, the catalogue's claim sits
beside **What each group found**: one row per outside group with its own word
for how much of the advertised result the Lean states, the gap it names, its
own word for whether OpenAI's proof passed Comparator, and a link to its
record, with one line saying a passing run does not show the statement matches
the paper. The rest is **one tab per reading question**: what the paper
claims; OpenAI's Lean; the groups' reasons; read more; what others wrote; how
to help. The tab bar stays in view; a link into a hidden panel opens it;
without scripts every panel shows in turn. This is the Atlas film's route
(find a result, see its claims, compare the groups' labels and reasons, see
which proof was checked) laid out so it needs no scrolling.

**Every tab uses the screen** (19 October 2026, second pass). Will: "just so
disorganised"; every panel sat in an 830px column beside a 280px column reserved
for a Details pane that was usually closed, so 55 to 80% of a wide screen was
empty. Now the panels take the frame's whole width and Details opens over the
right of the page. One card (surface, one rule, medium radius, one padding), one
heading scale and three spacing steps (section, block, tight) serve every tab.
Information is grouped by what the reader compares: **What the groups found** is
one card per group, side by side and of equal height, holding its scope term,
gap, definition, method, links and its Comparator run of every Lean statement
(or "No run reported"), then OpenAI's note and the AI drafts as two cards, then
other reports and calculations as one grid. **Lean statements** shows every
statement as one wide row (paper theorem beside Lean, the groups' runs as chips
in its head) under a grid of small summary cards; Comparator is one line and a
glossary link. Discussion, connections and contribute are card grids; a few
cards stand in one equal row, many flow in balanced columns, and kinds with
nothing to show are said together in one line. Each section leads with its
answer in one sentence and one quiet line on how to read it. The glance links
each group's term to its definition and its run word to its card, and ends with
what is left to check, quoting OpenAI's own sentence on what its Lean leaves out
(017: the Flint–Hills consequence). A family with no Lean gets a quiet Lean tab
of one line.

**The overview is the first tab; evidence is one row per group** (19 October
2026, third pass). The overview sat above the tabs, so every tab opened under a
screenful the reader had already read. Now the trail, title and tab bar come
first, **Overview** is the default tab and every other tab opens straight into
its task; old addresses into removed sections (`#left`, `#explain`, `#h-left`,
`#h-explain`, `#h-contrib`, `#h-standing`) land on the overview or the theorem.
The overview's table gives each group one row across both questions (does the
Lean state the whole claim; did OpenAI's proof of the named statement pass
Comparator), so a reader never carries a group's name across the page. Each
cell reads in three steps: the plain outcome (from the record's state:
`reported-accepted` "Acceptance reported", `reported-undecided` "Run ended
without a verdict", `reported-built` "Built and checked; Comparator not run"),
then the group's own label and reason, then the date and its account.
cert-machine's "REFUSED" on 005 is a run that ended, not a proof found invalid,
and the outcome word says so before the label. A group with only a run gets "No
coverage assessment recorded", never a failure word. The note on what is
unreviewed is titled by its scope ("Paper–Lean match: no review recorded").

**Atlas asks readers for nothing** (Will, 19 October 2026: "this is all noise
... we're just collecting from online"). The family page has no contribution
tab, no "open questions you can help with" button and no "Open the form" links;
the header nav has no Contribute item (the page stays, linked from the footer);
the map has no How to help band; Lean pages state what is unreviewed as fact
("No comparison of this Lean statement with Theorem 1.1 is recorded") rather
than as a task, and show contributed records only when some exist. Saying that
no review is recorded is evidence and stays; inviting the reader to do the
review is not.

**Set reading modules on the page, not in boxes.** Only mathematics (theorem
and Lean excerpts) and the evidence table sit on a raised surface; group
reports, routes and commentary are columns under a hairline, with group columns
under a 2px ink rule and sharing row tracks (subgrid) so each group's
assessment and runs start on one line. Explanatory text on family pages is
14 to 16px (`--fs-small` and `--fs-body` raised inside `.fx`), never the site's
13px label step. A short theorem stands beside its papers on a wide screen;
follow-up research is the main column of Related reading with references
beside it, so no card stretches round a narrow strip of text. Commentary lists
credited, dated items newest first and an item with no named author last.

**The first screen teaches, one question at a time** (19 October 2026, round 2).
Will: "god-level good clear communication for any audience". Worked on family
017 (π) and checked on 003, 005, 006 and 159. The headings alone now carry the
argument, each answered in its first sentence: *What is claimed?* (the catalogue,
quoted); *Which Lean statement was selected?* (PiExponent, with Lean defined in
half a sentence); *Does the Lean state the whole claim?* (each outside group's
own label as a boxed quotation, the label in plain words, and, quoted, what the
group says is missing, side by side, so the reader sees MathVet's "full" and
cert-machine's "NARROWER — DECLARED" name the same Flint–Hills omission without
Atlas saying so); *Did OpenAI's proof pass Comparator, the checking program?* (a
plain "Yes, accepted" or "No acceptance reported" per group from the backend's
accepted statements, then the group's word, date and own account, and every Lean
statement it did not run); *Not yet checked by anyone* (the unreviewed pairing,
OpenAI's own sentence on what its Lean leaves out, and two buttons that say where
they go). On a wide screen these read left to right in three columns. Rules
learnt: a reader's note can carry its reason after a semicolon, so never cut a
group's note at its first clause (the cut hid MathVet's Flint–Hills sentence);
quoted verdict words are tags, glossary terms keep the dotted underline; group
names, Mathlib, nanoda and "headline" link their glossary entry at first use.
Tabs and section headings are the reader's next questions (What does the paper
claim? What did OpenAI write in Lean? Why do the groups differ, and which proof
was checked? Where can I read more? What have other people written? How can I
help?); none repeats a heading of the first screen, and a tab with nothing in
the release says "(none in the release)". The trail is the site's own
`build_site.trail`: Map / subject / Family N: short title.

- **Head**: the trail; the family's name; OpenAI's catalogue description as a
  credited quotation, with its mathematics typeset.
- **The theorem**: the page's centrepiece, set large as printed (number, paper,
  date), with "Read it in the paper" and "Compare with Lean". "Show on the map"
  opens the family's subject on the map.
- **Two lines kept apart**: the formal status (what the Lean states, who re-ran
  it) and the readable argument (the paper at the passage, any explanation).
  Neither stands in for the other.
- **The claim**: when the backend names a candidate theorem for the headline,
  it is shown exactly as printed, with its number and paper, and the candidate
  state in words. When the headline is unresolved, the catalogue's claim leads
  and the candidates follow with their reasons; no convenient theorem fills the
  gap.
- **The comparison**: the paper theorem and the Lean statement side by side on
  wide screens, stacked on narrow ones, joined by the thread and its words.
  Either can be expanded without resetting the other. No scroll syncing.
- **Then**: what the outside readers found (each in their own term, notes
  beside verdicts, disagreement first), who re-ran the Lean, what is left to
  check, the papers (current, previous editions, withdrawn), connections, and
  how to explain, check or correct it.

## Inspection

One pattern for every supporting record: an outside reading, a re-run, a
candidate theorem, a number, a Lean name, a citation.

- Pointing or focusing shows a light preview that can itself be pointed at and
  dismissed with Escape. Hover is never the only way in.
- Selecting text in a preview preserves the selection being read. A drag,
  cancelled gesture or modified click does not activate the preview.
- Selecting pins the record in the inspection rail beside the reading column
  (a sheet from the bottom on phones). Focus moves to it; closing returns focus
  and the reading position.
- The rail shows the record's source, credit, date, version and a real link to
  the source. Long commands and full inventories live here, not in the reading
  column.
- A qualification that changes the meaning of a claim stays beside the claim,
  never only in the rail.

## Identity and links

Every object keeps one identity across the map, the lists, the family page,
the paper and the Lean page: the backend's ids, never rebuilt from TeX.

- Pages have stable addresses: `families/003.html`, `papers/<slug>.html#<anchor>`,
  `statements/<id>.html`. The map's selection is `index.html#o=<id>`.
- A copied link opens the same object, with JavaScript off too, and the page
  says which release pin it shows.
- A shared family page carries its own title, description and preview, so the
  link stands alone.

## Inks, type and ground

**Ground and inks.**
- One flat ground: cream in the light scheme, violet-black in the dark, with no gradients, glow or texture.
- Steel is for Lean and formal checks: Comparator re-runs and Lean statements.
- Brick is for every other machine check (HOL Light, exact computation) and for outward citations.
- Structure stays in low-chroma greys.
- Colour always comes with a word or a shape, never alone.

**Type.**
- Plectis Serif (STIX Two Text) for reading and theorem text.
- KaTeX for formulas.
- Plectis Sans (Source Sans 3) for the interface.
- Lean in the `--lean-mono` stack.
- Sentence case throughout.
- No tracked capitals, and no monospace outside code.

**Measure.**
- 60 to 72 characters for reading text.
- Wide formulas scroll inside their own box, never the page.
- Reading containers are capped in `ch`. KaTeX's hidden text inflates the audit's character counts, so judge formula-heavy lines by eye.

## The scale, made human

**Numbers.**
- A number is a sentence a person could say aloud, with what it counts.
- It links to the rows behind it.
- No big-number heroes.

**Entering the release.**
- Start from one thing a person can hold: one family, one theorem, one Lean statement.
- The map shows the whole release. A preview speaks for what is under the pointer, and the panel for what is selected; rewriting the panel on every hover made it flicker.
- The one-line colour key sits on the map's first screen.

**Disclosure.**
- Release, then discipline, then family, then result.
- At most four primary actions at any decision point; an expert's contents can show more.
- Lists filter and never dump.

**Teaching by example.** The front page shows the release map and its key.
Opening a family leads to its papers, statements and attributed checks. The
README links a concrete family before offering its full source comparison.

## The repository front page

The README is the first page many readers see. Keep one short introduction,
the website action and a clickable screenshot before the detailed material.
Use real captures of the intended website revision in light and dark schemes;
the screenshot links to the same website as the primary action. A public URL
can lag the working release. Confirm the intended revision before refreshing
images, and record their source and capture state in `docs/ARCHITECTURE.md`.

Follow the preview with routes into the map, a family, Lean statements and
attributed findings. The compact overview and the full count inventory both
come from `scripts/sync_readme.py` through Statement Map's checked reader.
Keep the exact worked comparison and detailed credit available in expandable
sections. Evidence limits remain visible outside those sections.

Build commands and the dataset reference live in `docs/ARCHITECTURE.md`.
Preserve the README's existing section anchors when shortening it. Check the
rendered Markdown in light and dark schemes at laptop and phone widths, and
check that the preview is a working link, not just an image.

Keep the introduction literal: say what the website shows and what a reader
can do there. Use a named example rather than another general description.
Review repetition and vague language across paragraphs, while preserving
attribution and the limits of each check. The directory guides in `docs/`,
`site/` and `scripts/` should help someone browsing GitHub find the relevant
file without repeating the architecture guide.

Repository references for this arrangement:

- [Observable Plot](https://github.com/observablehq/plot) gives its documentation,
  examples and contribution instructions short, direct routes from the README.
- [Datasette](https://github.com/simonw/datasette) names its readers and links a
  live example before the installation details.
- [Lean Blueprint](https://github.com/PatrickMassot/leanblueprint) introduces its
  purpose through real projects before explaining setup.

For Atlas, these support a website action and concrete family example first,
with contributor and developer instructions linked nearby. Folder boundaries
follow the files' responsibilities; a different project's package structure
does not by itself justify moving working paths here.

## Words

- Plain and exact. A statement "states" a theorem, a check "checked" a run, a paper "cites" another.
  - "Certified" appears only as a named source's own verdict, attributed to it.
  - A pairing found automatically is a "candidate", and says so.
- No em dashes. No "not X, Y" framing. No taglines. No middle-dot strings of facts; write a sentence.
- People whose pronouns no source states are "they".
- Ways into the release are chosen by how widely the problem is known, never by anything that implies a ranking of the results, and each says in one line why to read it.
- The atlas shows and does not argue.
  - It never implies that OpenAI or any credited group endorses it.
  - It never characterises anyone's work.
  - What the release lacks is never said. It is simply there on the page, done well.

## Evidence states stay distinct

Each of these states has its own wording. Unknown is neither red nor green.

| Recorded state | What the reader sees |
|---|---|
| Candidate pairing | A proposed correspondence, its method, and that nobody has reviewed it |
| Source reading | Who read the two sources (named, and said to be an AI agent when it is one), each link as Lean declaration, paper statement and relation, the reader's own limits quoted, the explanation on request, and that no person has reviewed it |
| Reported re-run | A named outside group reports this result; the atlas did not re-run it |
| Name linked from the source text | A link found by reading the Lean source, with no claim that Lean elaborated it |
| Paper rendered in full | The reading page passed its rendering checks; this says nothing about the mathematics |
| Unnumbered, or number unavailable | Two different states; neither is replaced by a section number |
| No card, or zero cards | Missing coverage differs from an observed empty set |
| An AI agent's draft classification | A quiet line after the outside readings, never styled as a verdict |
| The two outside readers disagree | One sentence naming both readings leads the section |
| An exact check that was not decided | Says nothing against the result; drawn in neutral grey |
| Headline unresolved | The catalogue's claim leads; candidate theorems follow with their reasons |
| Cited in the Lean source, or declared by the release | A source link between the two, not a review of their match |
| A number whose inputs are incomplete | Its known part and what is missing; never a zero |

## Motion and hover

Pointing previews; selecting commits. Motion answers an action and says one of
three things: what you are pointing at, where what you chose went, or what
changed. Nothing moves on its own, nothing replays on a visit, and no reading
text fades or slides in as it is scrolled to.

| Moment | What answers | Time |
|---|---|---|
| Pointing at a link, button, row or card | Colour, border or background; a card's border darkens | `--t-hover`, 120 ms |
| Pointing at a discipline or family on the map | The caption above the drawing names it in words (title, family, discipline, counts, the evidence line), covering nothing on the drawing; the rest of the map steps back and its row in the list lights | the caption swaps at once; map alphas ease over about 150 ms |
| Moving between levels on the map | Each disc moves from where it was to where it goes; a chosen discipline gets one ring once; the panel's new content rises 6 px into place | discs 640 ms, slow in and out; panel `--t-state` |
| Opening the Details rail or a preview | The rail slides 8 px in from its side (a sheet rises on a phone); a preview fades in | `--t-open`, 240 ms; preview `--t-hover` |
| Choosing a comparison tab | The tab's mark moves; the panels swap without a jump | `--t-state` |
| Arriving at a paper theorem | Its highlight fades out once | 2.4 s, once |
| Pressing a button | It sinks slightly (scale 0.97) | 120 ms |
| Switching theme | No colour transition runs (`.no-transitions` for two frames) | none |

Easing: arrivals use `--ease-out`; anything that travels uses `--ease-move`.
Under reduced motion every transition is instant, discs jump and the ring is
not drawn. On a touch screen, tapping selects.

What motion must never do: make a candidate look settled, move text a reader
is reading, delay the mathematics, or run in a loop.

## The pages and their one job

| Page | Its job |
|---|---|
| `index.html`, the map and the list | See the whole release and find a way in |
| `families/<id>.html` | What is claimed, what states it formally, what has been checked |
| `papers/<slug>.html` | Read the paper, with evidence at each theorem |
| `statements/<id>.html` | Read the Lean statement whole, and what you must check |
| `explain.html` | Every family as a list, with who has explained it |
| `sources.html`, `glossary.html`, `numbers.html`, `contribute.html` (footer only), `about.html` | Credit, terms, counts with receipts, how to contribute, why it is built this way |
| `help.html`, and the `?` guide in every header | How to use the Atlas: four steps to read any result, a link to try them on π, and five words |

## What the October rebuild taught

- **Say what was checked, by whom, in their words.** A re-run sentence names
  the operation and its object ("Comparator accepts OpenAI's proof of this Lean
  statement, as three outside groups report"). Each group then gets its own
  line in its own term. Credited names contain commas, so groups are separated
  by semicolons.
- **Bring the cited passage to the theorem.** A number a theorem cites, such
  as (1.5), opens the actual passage from that paper's reading page under the
  theorem, labelled with the paper and its date. If it cannot be found, the
  link goes to the passage instead of a guess.
- **Retrieval stays behind the mathematics.** How a passage was found (the
  shared words, the method) sits behind "Why this passage is shown". The
  passage's state, unreviewed and found by wording, stays visible.
- **No folds.** Content is shown, or opened in the rail on request.
- **A paper's word macros are words.** `\newcommand{\KN}{Kerr--Newman}` is
  typeset as text, never sent to the formula renderer.
- **One owner for each decision.** The pairing heuristics, headline choice,
  re-run tallies and reader grades that the frontend used to compute have been
  deleted. The backend decides them; the pages say what it decided.
- **A gloss is true of every term mapped to it.** MathVet's "full" means the
  Lean implies the headline; cert-machine's "MATCHES" means it states it. The
  shared state `all` reads "states or implies all of the headline".
- **An AI draft's class names a paper's theorem, never "the headline".** On a
  family whose catalogue claim is unresolved, no page calls any theorem the
  headline.
- **"Compare with Lean" sits only where a pairing exists**, and opens that
  pairing (`#lean-<name>`).
- **A record's own limit sits on its card, quoted** ("not the theorem"), and a
  scope is never cut at a colon.
- **The author's text ends where the author ended it.** What the atlas records
  at a paper's theorem follows it in a box headed "Atlas note, not part of the
  paper"; the highlight on a linked theorem covers only the author's words.
- **A short formula is one unit.** A formula of 32 TeX characters or fewer is
  braced, so "Re s > 11/12" never ends a line on its relation; longer ones keep
  their breaks.
- **On a phone, the list starts with something to open.** The disciplines come
  straight after the release's two sentences; the colour key is a link away.
- **Draw the illustrated chart, never the to-scale one.** A view that needs a
  key to decode its marks has failed. Show each object's name and a concise line
  of its content (a theorem's opening, a Lean statement's label) on the drawing
  itself, and let cards in columns with exact connectors replace rings and
  orbits.
- **Test URL logic on a case-sensitive server.** GitHub Pages is
  case-sensitive and macOS is not; a lower-cased Lean name worked locally and
  404ed on Pages for 220 of 416 statements. `flows_probe.py --serve` serves the
  build as Pages does.
- **Check clipped text as well as page overflow on phones.** A table cell can
  retain a desktop minimum width while its wrapper hides the overflow. Compare
  long titles with their row's bounds at 390px and 320px; reset width constraints
  with selectors at least as specific as the desktop rules.
- **A search the reader has acted on steps back.** Opening a match folds the
  matches behind one button, and the map stops dimming what the search did not
  match, so the opened paper's own results read at full strength.

## Lean statement and paper reading pages (UX pass, 19 October 2026)

**The evidence leads on the Lean statement page too** (24 October 2026, after Klara
Kaleb's feedback). The page opened on a paragraph repeated on all 416 pages, then a
"What is known so far" table of paragraph answers, and only then the Lean and the
paper. Now, under a one-sentence header (what Lean is, a glossary link), the page
opens on the family board's sheet: the paired paper theorem exactly as printed on
the left (several when the Lean's parts match several; with nothing paired, the
backend's reason and the closest statements by name), the Lean text on the right
with one line on `sorry` (or, for a definition-only file, what Comparator compares
instead), and the pairing's qualification once along the sheet's foot, with a link
to how it was chosen. Then one card per outside group, side by side: its assessment
of the family's Lean in plain words with the map's dot, its own term, its reason
quoted, and its Comparator run of this statement; the lead says once that the
assessment is of the family's Lean and the run of this statement, and the foot says
once what a Comparator pass does not show. The detail follows in its own sections:
reading the Lean (OpenAI's note, the AI draft, the symbol key, definitions, axioms),
how the paper theorem was chosen (shared words, other candidates, the method), the
full run reports, what is unchecked, where to read more, the file and the card. The
header's action buttons and the glance table went; every anchor other pages link to
stays (`h-glance` is the sheet, `h-claim` and `h-lean-read` its two halves,
`h-readings` an alias on the groups), and the contents rail follows the new order.
`lean_group_cards` and the sheet in `build_statement` (`scripts/build_site.py`) own
this, with the `.lxb*` rules in `site/assets/lean.css`. Bullets below describe the
earlier passes; where they disagree about the opening, this paragraph stands.

- **The answer comes first.** A Lean statement page opens with "At a glance": its
  family, the paper statement and the match's state ("possible match, not
  reviewed"), then one row per group with both answers in the group's own term:
  does the family's Lean state the advertised result, and did OpenAI's proof pass
  Comparator for this statement. The full reports follow, linked from the table.
- **Compare side by side.** The Lean statement and its paper statement are two
  columns from 1100px; run reports and assessments are equal cards in a grid; the
  share card sits beside the recorded comparisons.
- **Margins carry navigation, never emptiness.** From 1280px a Lean page keeps a
  contents rail and the file's facts in a sticky side column. A paper keeps its
  40em reading measure; the contents stay open on the left from 1280px and the
  family panel (its Lean statements, their possible matches and each group's
  reports) stays on the right from 1000px. Below that, one column: the contents a
  disclosure above the text, the panel after it.
- **A wide display scrolls in its own box**, never past the reading column.

Round 2 (teaching order, 19 October 2026): Will asked for pages that teach any
reader, not emptier ones.

- **Headings are the reader's questions, in order.** A Lean page reads: what is
  known so far; what does the Lean statement say; which paper theorem might it
  state; what do the groups conclude, and why; which proof did Comparator accept,
  and what does that show; what is still unchecked, and how can you help; where to
  read more. Skimming the headings gives the argument. Each section's first
  sentence is its answer. "At a glance" became "What is known so far": four
  questions answered in a sentence each.
- **The groups' reasons sit beside their labels.** The comparison table carries
  each group's rule text and note in its own words, next to its Comparator run, so
  "full" against "NARROWER — DECLARED" can be read with the shared Flint–Hills
  omission that explains it. The separate assessments section went; its anchor
  `h-readings` survives on the table.
- **Notation is explained where it is read.** OpenAI's own note sits above the
  code as its plain reading, the `sorry` note before it, and a key lists only the
  symbols the shown lines use (copy_lean.json `symbols`, matched by pattern).
- **A paper says where it fits before its text.** "Before you read" answers which
  family, which of its theorems have a Lean statement (and which main statements
  have none, such as 017's Flint–Hills corollary), what the groups report in their
  linked terms, and where to go next.
- **One trail**: Map / Subject / Family N: short title / Lean statement Name, or
  the paper's short title ("The paper" when it repeats the family's title).

## Width follows the kind of evidence (20 October 2026)

A visual review of family 003 and the Number theory map found the pages noisy because
every kind of content took the same width. The rules that came out of it:

- **Prose keeps a reading measure; comparisons take the width.** Paper abstracts and
  follow-up summaries stop near 72 characters; with several statements in "What the paper
  claims", each paper is one row, its title, date and actions beside its abstract. The
  theorem and its possible Lean match stay side by side, and their two captions share one
  band so both cards start on the same line.
- **Coverage and proof runs are two comparisons.** The groups tab sets the coverage
  assessments side by side, names a group that made none in one sentence (never an empty
  card), then gives every reported Comparator run in one table of Lean statements by
  groups, with "No run recorded." in each empty cell. A narrow screen stacks each row,
  labelled by group.
- **A record's credit is its link.** Commentary, explanations and follow-ups put the
  author and title as the one link to the source, the date under it and the summary as the
  body; no detached "Source" link. Lists of records run row-wise, at most three across.
- **Labels claim no more than the record.** A credited report is "Other report", not
  "Another Comparator run": some are calculations or say Comparator was not run.
- **A tab opens at its heading.** Choosing a tab while the bar is stuck at the top scrolls
  the new panel to start just under the bar (`family.js`, `toTabs`).
- **Selection on the map keeps the field readable.** Unrelated discs drop to about a third,
  their names to about half, so the next family can be read while the selected family's
  citations lead.

## Papers: fit, credit and the PDF (20 October 2026, second pass)

- **No sideways scrolling for an ordinary formula.** A display wider than its column is
  set smaller until it fits, down to 70% (`atlas.js`, `fitMath`), measured in one batch
  so a long paper costs one layout. Only a formula wider than that keeps its own scroll.
  Raw TeX never flashes while KaTeX loads; it appears after 6 seconds only if
  typesetting never comes.
- **The PDF is a way of reading, offered first.** "Read the PDF" is the first action in a
  paper's header and stays pinned above the contents beside the text.
- **OpenAI's work is credited as OpenAI's.** Every paper page says the paper is OpenAI's,
  from its release under the Apache License 2.0, that Atlas converted the TeX (the
  change notice the licence asks for), that the PDF is the version to cite, and that
  Atlas is not affiliated with OpenAI. "Copy OpenAI's citation" copies the BibTeX OpenAI
  publishes in the manuscript's directory, unchanged. Family pages say "Read OpenAI's
  papers".
- **Every family disc on the map says how many papers it holds,** with its Lean count
  when it has one, in the same place under the title. The title is fitted with that
  line reserved, so a long title never pushes the count out.
- **An absent record is not a refusal.** A group with no recorded coverage assessment is
  described as "Atlas has no record of … assessing", never "did not assess".

**The paper and its evidence at once** (24 October 2026, after Klara Kaleb's feedback that
the site repeats its explanations and is slow to reach the concrete example). Above the
paper's first words there is now only the title, authors and date, the three reading
actions and one quiet line of credit and caution (OpenAI's paper, the licence, that Atlas
converted the TeX and is not affiliated, that the text and numbers can differ from the PDF,
the version to cite); the separate numbering note joined that line. "Before you read" went:
its four answers repeated the panel beside the text and the note at each theorem. The panel
is now the one summary, in the family board's grammar: each Lean statement as a small pair,
the paper's theorem on the left (linked in place, or to the other paper that holds it), the
Lean statement on the right, the divider dashed for a candidate and solid for a cited or
declared link, the pairing's state at the join and each group's Comparator run under it;
then the paper's main statements no Lean statement is paired with ("No Lean statement for
Corollary 1.2"); then one row per group with its own term and the plain gloss. It sits
beside the text from 1000px and before the text on a narrower screen, so a phone meets the
evidence before the abstract. The note after a paired theorem is two lines in a box marked
"Atlas": the Lean statement's name linked with the pairing's state in a few words (the full
sentence is its title), then each group's term and its Comparator run. The heading no longer
repeats the Lean link the note gives just below it. Lean and Comparator are glossary links
on the words. Where this disagrees with "A paper says where it fits before its text" above,
this stands.

## The map sidebar at each selection level

**The family entry is the evidence in miniature** (24 October 2026, after Klara
Kaleb's "text-heavy, with some explanations repeated"). Pointing at a family's
circle, or focusing its row, opens its entry in the subject's list as four
labelled rows like the front page's example: OpenAI's catalogue (the first
sentence, typeset), OpenAI's Lean (the statement the family page shows first,
from the backend's selection, and how many more), each group's own label in its
own words (MathVet "full", cert-machine "NARROWER — DECLARED"), and who reports
Comparator accepted OpenAI's proof of that statement; its last line, "See the
evidence side by side", names what the row's link opens, the family page's
Evidence tab. `build_universe.family_board` writes those fields into each
family's detail record. The family view the map API can still select leads
with the same rows in a card. Repeated sentences were cut at each level: the
subject's lede is its counts (the map bar already says what a circle is and how
to open it); the release key asks its one question once, with MathVet,
cert-machine and Lean as glossary links, and drops the citation sentence the
subject's map bar carries; the search hint that repeated the placeholder is
kept only for screen readers; the "Try an example" button that pointed at the
example directly below it is gone; the family view drops the full catalogue
quote, the assessment-scope sentence, the headline-selection note and the
citation caveat, all of which the family page holds. One quiet line under "How
to use the Atlas" offers the videos (Will, 24 October 2026): "New here? Watch
the Atlas walkthrough", then, smaller and fainter, "or the Maths Map video",
both plain off-site links that hide with the rest of the head's ground text.

On desktop, the colour key stands on the map at the release and in a subject;
the sidebar starts with the release's figures and where to start, then the
subjects. Each family in a subject's list is one title and one short line:
its number, its size and the colour's short name. A
discipline lists families with their paper counts and the readers' assessment. A family is an index of its papers and Lean statements,
with the catalogue claim, attributed readings and citations retained. Choose
a paper to read its abstract and statement previews, then a result to read the
whole statement and its recorded Lean links. A Lean selection shows its human
label, challenge snippet, paper preview and attributed re-runs.

Use the source abstract and each paper's own macros. Sidebar previews keep
whole paragraphs, displayed formulae and lists in source order. Cut only
between blocks, mark any continuation and keep the full statement one click
away; never omit an equation then retain its qualifier. A preview is labelled
and is not a new summary or a verdict. Reader sections appear only when reader
records exist; otherwise use an evidence heading. Put the family scope before
attributed assessments, including when they appear under one selected result.
Keep paper titles and Lean identifiers in the selection heading once. Family result counts mean results drawn on this map.
Section buttons move within the sidebar without changing the selected object,
map position or URL. The sidebar has one vertical scrollbar, including long
Lean snippets; source code may still scroll horizontally.

On desktop, pointing at a family in a discipline brings its expanded sidebar
entry to the top of the reading area immediately. Keyboard focus uses the same
alignment. Keep the catalogue order and allow enough scroll range for the last
entry. Pointer browsing within the sidebar keeps rows compact and must not
reposition them. Moving between a row's title, status and description must not
clear its map highlight or trigger another redraw. Keyboard arrival updates
the expanded entry before aligning it, and internal focus transitions keep it
steady. Leaving the map must not reset the reader's place. A preview does not select an
object, change the address or move keyboard focus.

Family labels wrap at existing compound separators and fit every line inside
the disc. Try alternative line breaks before truncating; a long second word
must not leave a title as “The…” or “A…”. Counts use spare room after the name.
A visible family remains clickable during a map transition. An interrupted
details request can be retried, and a later selection supersedes a pending one.
Pressing a moving circle reserves that circle until release; motion must not
turn the same click into a miss, another family, or Back. Drags and cancelled
gestures must not reuse a reserved selection. Painted discs share the same
visibility threshold with hit testing.
Returning from a family reveals the finished map immediately, with stable
circle positions. Discipline transitions stay brief. Fit labels at the destination
radius once and scale them during motion, rather than wrapping every animation
frame. Retain only the current fit per family and discard old viewport caches.
A failed or stale detail packet stops loading and reports the failure. Redrawing
must never restart a rejected request; another selection can retry with fresh
bytes. Regression checks cover both network failure and a stale generation.
Draw the map when its baseline data is ready; font downloads must not hold up
navigation. Refresh text measurements when fonts arrive. When a chosen family
needs both the parts index and its discipline details, request them together.
Keep shared requests and cached details; do not preload every discipline.
The sidebar preserves focus on its navigation rows as details arrive.
Excerpt fitting is cached for unchanged width, budget and font metrics, including
when the fitting limit was reached. Fresh desktop selections bring the map's
heading and breadcrumbs back into view; scrolling a sidebar must not leave the
next selection cropped above the screen.
Map statements use the paper reader's printed reference numbers and anchors.
Packet URLs change with the rendered packet bytes, even at the same backend
generation, so a corrected preview is not hidden by an old cached response.
Discipline citation arrows carry a visible direction key. Arrowheads point to
the cited family; the line does not assert a proof
dependency. Fade unrelated circles and their labels enough to keep citations
readable, while keeping those circles clickable.

## The shell and the general pages

- **One container.** Header, page head, sections and footer share the frame
  (`--frame`, left edge at `--gutter`). No general page centres a narrow column:
  About, Contribute, Glossary and the 404 page start at the same left edge as the
  lists, so the title never jumps between pages.
- **Use the width with grids, keep the measure in cards.** Lists of things are
  `auto-fit` card grids (sources, numbers, cited works, ways to contribute); the
  Glossary and About read in newspaper columns; an explanation sits beside its
  record. Text keeps a readable line because it lives in a card or a column, not
  because the rest of the screen is empty.
- **One card, one scale.** A card is surface, a 1px `--rule`, `--r-md`, padding
  `--sp-4`. Gaps come from `--sp-1` to `--sp-7` (4, 8, 12, 16, 24, 40, 56 px): 1-3
  inside a component, 4-5 between blocks, 6-7 between sections. Page title, section
  `.h2`, card `.h3`; nothing else sets a heading size.
- **The list pages keep their controls in view.** The filter bar sticks to the top
  as one grid row, and the table head sticks inside its own scroll box. A choice is
  offered once: disagreement is the colour filter's "The groups disagree" (an old
  `?c=disagree` link selects it). Both lists filter by Comparator runs.
- **One breadcrumb.** `build_site.trail` writes every trail below the map: a
  `nav` landmark holding an `ol`, every crumb a link except the page itself
  (`aria-current="page"`), slashes hidden from screen readers and glued to the
  crumb after them. Inside a family: `family_trail(f, root[, here])` gives
  Map / Subject / Family N: title [/ this page]. A list or general page:
  `section_trail(root, key[, page])` gives Map / Section [/ page], and the
  header marks that section; pages inside a family mark Map
  (`aria-current="true"`). The previous/next row sits directly under the trail,
  between two hairlines, on every family, Lean statement and paper page.
- **Every general page opens with its purpose.** The lede says what the page is
  for and who it helps, then what to do next. List column heads and filters
  carry `data-tip` (`tip_attr`): atlas.js shows the plain explanation in the
  glossary popover on hover and focus.
- **The `?` guide teaches through one example.** Beside Search in every header;
  the `?` key, `?help=1` and any `data-help="<step>"` element open it (at that
  step). Family 017 comes first as six numbered steps in a tinted card, the same
  route for any result beside it, then the words in the order a reader meets
  them. The same blocks fill `help.html`. No card floats over the map: the
  map's own panel offers the guide and the example.
- **The glossary has two orders.** `glossary.json` `learning_order` lists the
  core terms; the page shows them first as numbered cards in columns, then
  every term A to Z. A term's `example` follows its definition there and in
  the hover popover.
- **The footer** is the name, independence and licence, then three short labelled
  lists (the Atlas, lists and credits, source). It sits directly after the page's
  last section, with no stacked margins above it.

## Space

**Use the width; never leave a dead gap** (24 October 2026). Will, on a family page
whose theorem sat in a narrow column beside an empty half: "I hate it when we don't
use up the space ... It needs to be better. Just visually, aesthetically, creatively,
artistically." A pass at 1440, 1280, 1920 and a 390 phone, in both schemes, applied
these rules; later passes keep them.

- **Compose, never pad.** Dead space is a column ending far short of its neighbour, a
  wide band holding one short line, a grid row with a lonely item, or a page that is a
  narrow strip down the left. It is fixed by re-placing content the page already has,
  never by filler, padding or invented content.
- **Reading text keeps its measure** (about 60 to 75 characters); the freed width takes
  a second column of real content: a section's answer beside its how-to-read line
  (`.fx-shead`, `.fx-grphead`), a general page's purpose beside its longer account
  (`.phead--split` on Numbers, Sources, About and the two citation lists), an Atlas source
  note beside its source links, OpenAI's note on a Lean statement beside the symbol key,
  the shared words beside the other candidate theorems, the unchecked list beside its
  questions.
- **The shorter column travels.** Where two columns stand side by side and one is more
  than 120px shorter, `family.js` marks the shorter `.fx-travel` (sticky under the tab bar)
  only when it fits the window, so a theorem taller than the window always scrolls to be
  read. It is measured again when a column changes size. This replaced the unconditional
  sticky paper theorem on the Lean tab, which could be taller than a laptop window. A
  paper side holding only OpenAI's description takes the sheet's height and travels, with
  the papers under it.
- **Close a tab on one row.** The evidence tab ends with the papers on the left and the
  note and route to the groups' reasons on the right, under one hairline, not a band of
  space and a second rule.
- **Unequal records.** Three records where one is much longer: the long one on the left,
  the two short ones stacked beside it. Five to twelve source cards of unequal length flow
  in balanced columns; longer lists keep rows. Ranked works run one per row across the
  frame with their citing papers in as many columns as fit, so the ranking reads straight
  down. The careful-reading list runs row-wise across the frame.
- **One Lean statement's name and runs stand beside the Lean tab's answer**; with several,
  each comparison's head sets the name left and the runs right.

Deliberately left: the Lean half of the evidence sheet under a long theorem (it already
travels), the group cards' equal heights (their runs share one line), the glossary's
first list (thirteen indivisible cards balance as well as columns allow), the Numbers
grid's odd last card, and the front page.

## Source readings link declaration to statement (26 October 2026)

Reader v9 gives each Lean statement one pairing decision, and 140 of them are
attributed source readings: a named reader, so far always an AI agent, read the
Lean source and the paper and recorded which configured declaration states which
paper statement, how the two relate (the same claim; the paper statement is one
part of the Lean; the Lean is one part of the paper statement; the Lean is a
consequence of it) and what the link leaves out. The site renders them as such.

- **A reading is a small table read across**: Lean declaration, paper statement
  with its title, relation in words. Above it, one line names the reader, says it is
  an AI agent when it is, and says no person has reviewed the links and no proof was
  checked. That line is the only disclaimer: a recorded limit that only repeats it
  is not quoted again, and every other clause the reader wrote is quoted as written
  under its row. Since reader v10 the backend flags such notes (`general_disclaimer`),
  and the site follows the flag rather than matching words; where every link names
  one bundled declaration, the first column shows the part of it each link concerns
  (`component`, e.g. `StrongTail.DensityAt`).
- **The explanation opens in the inspection rail** ("Why they were linked", beside the
  relation), with the reader, the declarations in full, the relation, the limits and
  the ways to the paper passage and the Lean page, so the rows stay one line each; a
  bundle of nine links fits in about ten lines. The family page keeps its rule of no
  folds.
- **The Lean declaration is in the Lean's ink and the paper statement in the
  paper's**, joined by the dashed rule the sheet already uses for an unreviewed link.
  A screen reader hears the row as a sentence ("main and Theorem 10.1: the paper
  statement is one part of the Lean").
- **The evidence sheet shows at most three links** and sends the rest to the Lean
  tab; the Lean statement's page lists every link in full, with each explanation and
  limit set out.
- **A reading that links nothing says who read the sources and quotes their reason**
  instead of listing the nearest statements by shared words.
- **Never call a reading a word match, a review or a check.** The word-match
  wording ("matched by the words of the Lean statement") belongs only to the
  backend's source-text candidates, and Atlas is not named as the one who chose.
- **A paper column holding several linked statements is one stack**, so the
  caption row still lines the first card up with the Lean card (nine cards once
  overlapped in the subgrid's two rows).

## The guide is four steps (26 October 2026)

Will asked for the `?` guide to be simplified drastically, so that it explains how to
use the site at the most basic level. The guide had a six-step worked example, a six-step general
route and ten definitions, about three screens. It is now one screen: a sentence on what
a page shows, four numbered steps (find a result; read the first screen, paper on the
left and Lean on the right; see what the outside groups found, keeping "does the Lean
say what the paper says" apart from "did the proof pass Comparator"; use the tabs for
more), one button to try them on family 017, and five words beside the steps. Each step
says what is on the screen and what to do with it; Lean and Comparator are defined in
the step that first needs them. The steps keep the ids `lean`, `questions` and `tabs`
that pages use to open the guide at a step.

## Quality floor

Judge every page at four sizes, in both schemes:
- laptop, 1440×790;
- small laptop, 1280×690;
- monitor, 1920×953;
- phone, 390×664.

Every page must also:
- have a skip link first, visible focus and full keyboard use;
- reflow at 320px;
- make no requests to other hosts;
- show no layout shift;
- keep a working route when JavaScript is off.

Read the screenshots in order before calling anything done, and have fresh eyes
read them too.
