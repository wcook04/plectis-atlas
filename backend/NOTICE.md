# Sources, credit and licence boundaries

Source material keeps its original authorship and licence. The new implementation
has no public release licence selected yet; this file does not relicense imported
work. Do not infer endorsement by an upstream author or institution.

| Material used | Source and credit | Terms |
| --- | --- | --- |
| Manuscripts, challenge statements, configurations, producer metadata | [OpenAI mathematics collection](https://github.com/openai/math) and its contributors | Apache-2.0; original bytes and source headers retained in snapshots. |
| Corpus catalogue, statement extraction, reading-page numbering, candidate pairings, collected outside records | Will Cook's local OpenAI Math Atlas; immutable producer pin, source file hashes and provenance in `inputs/openai-atlas.json.gz` | Apache-2.0. Adapted into this repository's source adapter; normalization, audit and contribution layers are additions. |
| Source-aware navigation matcher | Will Cook's [Plectis Atlas, `scripts/build_site.py`](https://github.com/wcook04/plectis-atlas/blob/f047bac96ee80ebef0b4f5a403831b84de6e32c1/scripts/build_site.py) | Apache-2.0. Adapted in `web_pairing.py` with audited identities, deterministic traversal, conservative ambiguity and source-over-title ranking. |
| Eight-problem paper–Lean coverage and source records | [Plectis Erdős](https://github.com/wcook04/plectis-erdos), Will Cook and contributors | Apache-2.0; original recorded verdicts preserved. |
| Navier–Stokes and Euler source metadata | [OpenAI NavierStokesAndEuler](https://github.com/openai/NavierStokesAndEuler) | [Pinned Apache-2.0 licence](https://github.com/openai/NavierStokesAndEuler/blob/f9e8bc5b38b6e212696e8a30e3e91517af887bbd/LICENSE). |
| Fermat source metadata and selected source bytes | [Anthropic Fermat's Last Theorem](https://github.com/anthropics/fermats-last-theorem), with original contributors and upstream notices | [Pinned Apache-2.0 licence](https://github.com/anthropics/fermats-last-theorem/blob/6e837e75355538c7f80bab5b956861e86c4eacc2/LICENSE). |
| Scope readings and Comparator reports | [MathVet](https://github.com/mathvet/mathvet), its maintainers | Apache-2.0. Imported through the attributed atlas source record. |
| Scope readings, replay reports, finite-check records | Carlos Toledo's [cert-machine](https://github.com/carlostoledo1891/cert-machine) | MIT. Finite refusal/undecided records remain distinct from refutations. |
| Comparator performance and replay reports | Neal McBurnett's [openai-math-lean-tooling](https://github.com/nealmcb/openai-math-lean-tooling) | MIT. Pending records remain pending at the captured source pin. |
| HOL Light cards and explanatory excerpts | Ben Knill's [openai-math-hol-cards](https://github.com/BenKnill/openai-math-hol-cards) | MIT code; [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/) explanatory prose. Selected records normalized by the atlas and this adapter; original credit retained. |
| Erdős problem links | Thomas Bloom, [erdosproblems.com](https://www.erdosproblems.com/forum/thread/blog:10) | Linked and credited. No general reuse licence inferred. |
| Tier classifications | [OpenAI Math Tier List](https://claude.ai/artifact/JSqNXXfsvRntB6cqoEENaN), author not stated | Source link and attribution retained; no general prose reuse licence inferred. |

Copies of available upstream licences are in `inputs/licenses/`. The Apache-2.0
copy there also accompanies the Apache-licensed source snapshots. Source-specific
pins, methods, URLs, reuse descriptions and credits travel inside the atlas
snapshot's `curated/sources/*.json` records and the emitted ledger. Each blob
snapshot preserves its original text, including copyright headers.

The compact snapshots are transformed containers of source bytes and metadata;
we have changed their packaging, not the authorship of the underlying work.
Agent-authored scope drafts and heuristic pairings keep their unreviewed status.
The comparison with other tools is in [docs/COMPARISON.md](docs/COMPARISON.md).

The exposition guidance adapts Plectis's public mathematical writing skill,
short-paper contract and synthesis guide. Their exact source pins and the
scope of this adaptation are recorded in [docs/EXPOSITION.md](docs/EXPOSITION.md).

The repository-local authoring resources also include:

| Material | Source and credit | Terms and changes |
| --- | --- | --- |
| README authoring skill and reference | [Pieter Kuppens, skills](https://github.com/pkuppens/skills/tree/0f3f1614f21fa3dadb6067eab5dd67a70a1872a6/skills/readme-authoring) | MIT. Original bytes and licence retained; local skill adapted to a static backend and its reader/contributor routes. |
| Documentation-writing skill | [GitHub, Awesome Copilot](https://github.com/github/awesome-copilot/tree/82701c24b99488536ca399ff4789a458b7a05db7/skills/documentation-writer) | MIT. Original bytes and licence retained; local skill uses task context and permits source verification without an additional outline-approval step. |
| Compact mathematical-writing guide | [Will Cook, Writing a Good Mathematical Paper](https://github.com/wcook04/plectis-erdos/blob/0a66e10d35dba45ca1efcdab1d10d2f6011cc595/paper/exposition/writing-a-good-mathematical-paper.tex) | CC BY 4.0. Source and licence retained; shortened and applied to papers, two-page guides and diagrams without repository-specific tooling. |

[skills/sources.json](skills/sources.json) records exact pins, copied paths,
hashes and adapted files. These licences cover their identified imported and
adapted material; they do not select a licence for the backend implementation.

Explanations submitted through the contribution template propose CC BY 4.0.
Contributors should check the licence before sharing. Referencing a source is
not a licence grant over that source, and contribution files do not replace its
copyright or attribution notices.
