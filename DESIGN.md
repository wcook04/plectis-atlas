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
  back; a click opens the family board. Every level fits its stage, so the map
  has no zoom or pan.
- **The list** (the left panel): the release in sentences, search, then the
  disciplines. Choosing one zooms the map to it and lists its families as plain
  entries: title, the claim's first sentence with its mathematics typeset
  (credited to OpenAI's catalogue), and one sentence saying what the Lean
  states and who checked it. Pointing at an entry lights its node; clicking
  opens the family.
- **A family: a board of cards** in the Zenith Code Map Focus grammar. Its
  papers are columns in date order (short title, date, "Read the paper");
  under each, a card per result with its printed number and the opening of the
  statement typeset with the paper's macros; under a result, the Lean statement
  paired with it (label, identifier, the pairing in words, the re-run
  sentence), joined by a connector, dashed for a candidate. "Cited by" families
  on the left, "Cites" on the right. One line at the foot says what a dashed
  line means; there is no key. On a phone the board is one column of the same
  cards. A click always leads to mathematics, never to a status page.
- Hover explains, click selects, double-click or Enter opens, Escape steps
  back. Selection lives in the URL (`#o=f%3A003`,
  `#o=d%3Anumber-theory`, `#o=r:...`, `#o=l:...`); Back and Forward restore it;
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
- While a detail packet loads, the board and sidebar each retain one completion
  subscriber per discipline. Only the current board and latest sidebar visit
  refresh when it arrives; revisiting a node cannot queue repeated typesetting
  or layout work.
- A pointer double-click retains the first card through reading-panel reflow.
  Its second click opens that card even if the sidebar has moved beneath it;
  dragging, cancelled gestures and modified clicks do not open it.

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

- **Head**: the trail; the family's name; OpenAI's catalogue description as a
  credited quotation, with its mathematics typeset.
- **The theorem**: the page's centrepiece, set large as printed (number, paper,
  date), with "Read it in the paper" and "Compare with Lean". Its place in the
  family is one click away on the map ("Show on the map").
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
| Pointing at a discipline, family or board card on the map | A card beside it names it in words (title, family, discipline, counts, the evidence line, a statement's opening); it is placed where it covers the fewest other names and never the pointed object; the rest of the map steps back and its row in the list lights | fades in `--t-hover` after a 70 ms pause; map alphas ease over about 150 ms |
| Moving between levels on the map | Each disc moves from where it was to where it goes; a family's disc grows to fill the stage and its board fades in 8 px; the chosen card gets one ring once; the panel's new content rises 6 px into place | discs 640 ms, slow in and out; board `--t-open`; panel `--t-state` |
| Opening the Details rail or a preview | The rail slides 8 px in from its side (a sheet rises on a phone); a preview fades in | `--t-open`, 240 ms; preview `--t-hover` |
| Choosing a comparison tab | The tab's mark moves; the panels swap without a jump | `--t-state` |
| Arriving at a paper theorem | Its highlight fades out once | 2.4 s, once |
| Pressing a button | It sinks slightly (scale 0.97) | 120 ms |
| Switching theme | No colour transition runs (`.no-transitions` for two frames) | none |

Easing: arrivals use `--ease-out`; anything that travels uses `--ease-move`.
Under reduced motion every transition is instant, discs jump and the ring is
not drawn. Touch screens get no hover card; tapping
selects.

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
| `sources.html`, `glossary.html`, `numbers.html`, `contribute.html`, `about.html` | Credit, terms, counts with receipts, how to help, why it is built this way |

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

## The map sidebar at each selection level

On desktop, the release starts with the colour key, visible without scrolling;
the disciplines follow it. The map key remains available at every depth. A
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
Lean snippets; source code may still scroll horizontally. Compact map cards
stop before an omitted formula instead of carrying on after it; a numbered
list marker alone is not a sentence or a useful preview.

On desktop, pointing at a family in a discipline brings its expanded sidebar
entry to the top of the reading area immediately. Keyboard focus uses the same
alignment. Keep the catalogue order and allow enough scroll range for the last
entry. Pointer movement within the sidebar must not reposition its rows, and
leaving the map must not reset the reader's place. A preview does not select an
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
An outgoing board loses mouse and keyboard interaction immediately.
Returning from a family reveals the finished map immediately, with stable
circle positions and no outgoing board covering it.
Family boards open as soon as their data is available; they do not wait for a
decorative zoom. Discipline transitions stay brief. Fit labels at the destination
radius once and scale them during motion, rather than wrapping every animation
frame. Retain only the current fit per family and discard old viewport caches.
A failed or stale detail packet stops loading and reports the failure. Redrawing
must never restart a rejected request; another selection can retry with fresh
bytes. Regression checks cover both network failure and a stale generation.
Draw the map when its baseline data is ready; font downloads must not hold up
navigation. Refresh text measurements when fonts arrive. When a chosen family
needs both the parts index and its discipline details, request them together.
Keep shared requests and cached details; do not preload every discipline.
Board layout must not recursively rebuild its own content. Reserve scrollbar
space so overflow does not alternate the column count. Resize and pagination
refresh only the visible excerpts, with bounded fitting work. Verify boards
near a column breakpoint, including the 14-paper log-abundance family.
Detail arriving for a neighbouring family updates that family's title in place.
It must not rebuild the paper board, move its page, or discard keyboard focus.
An own-detail refresh preserves the board's page, scroll and focused control.
The sidebar likewise preserves focus on its navigation rows as details arrive.
Excerpt fitting is cached for unchanged width, budget and font metrics, including
when the fitting limit was reached. Fresh desktop selections bring the map's
heading and breadcrumbs back into view; scrolling a sidebar must not leave the
next selection cropped above the screen.
Dragging across board text selects text without selecting a record or stepping
back. Board pointer clicks use the same movement tolerance as map circles.
Map statements use the paper reader's printed reference numbers and anchors.
Packet URLs change with the rendered packet bytes, even at the same backend
generation, so a corrected preview is not hidden by an old cached response.
Discipline citation arrows carry a visible direction key. Arrowheads point to
the cited family, including on the board; the line does not assert a proof
dependency. Fade unrelated circles and their labels enough to keep citations
readable, while keeping those circles clickable.

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
