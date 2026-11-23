# MeetingMemory — one-page write-up

## Architecture

```
data/transcripts/*.txt
   |  ingest.py (pure code)
   v
SQLite: turns(meeting, team, seq, turn_no, speaker, text) + FTS5 index
   |                                   ^
   |  extract.py (cheap LLM, offline)  |  agent.py (LLM plans, code executes)
   v                                   |
memory_items(decision/action/..., status=current|superseded)
                                       |
                          answers.json / TS3012 brief
```

`ingest.py` parses the AMI turn headers, stores one row per turn and builds a BM25 FTS5
index. `mem.py` is the only retrieval layer: it locks every query to one team, returns
turns in meeting order, reads windows around a turn, copies exact spans, and verifies
quotes. `extract.py` runs once per meeting (hash-cached): a cheap model pulls decisions,
actions, objections and numbers into `memory_items`; a second call decides which earlier
items a new meeting replaces, and **code** writes the `superseded` status. `agent.py` is
the online loop: the model chooses searches/windows/memory lookups, then submits *turn ids
+ hints*; code resolves those to verbatim quotes, re-checks them, and asks the model to
retry if verification fails.

## The model-vs-code line (and why)

**Never the model:** parsing, tokenising, indexing, team isolation, meeting ordering,
chunking, caching, storage, supersession state changes, quote copying, literal quote
verification, final JSON assembly. These are deterministic, auditable, free, and a model
can only make them slower and less reliable.

**The model:** query planning, relevance judgement (“does this passage answer the
question?”), which turn to cite, and the supersession judgement (“does this new decision
replace that old one?”). These need language understanding over messy speech.

The important constraint: **the model never writes a citation.** It names a turn and a
short hint; code copies a contiguous span from that turn and rejects anything under six
words or not found verbatim. That is why the shipped `answers.json` has 58/58 verified
quotes and zero invented text.

## Memory over time

Meetings sort `a < b < c < d`. A “what changed” question searches later meetings and
reports first and final state. `memory` exposes current vs superseded items, so an answer
can say “first X, later Y” rather than averaging the two. Supersession is stored as data,
not recomputed per question, which is what keeps it cheap at scale. The TS3012 brief is
built with `upto='c'` so meeting d cannot leak into it; `mem.search` hides later meetings
at the SQL level, not in the prompt.

## Models, APIs, and where they broke

Stdlib-only direct REST to an OpenAI-compatible `/chat/completions` endpoint
(`llm.py`) — no SDK dependency to fight. The shipped `.env` targets **DeepInfra**:
`DeepSeek-V3.2` for the agent loop, `DeepSeek-V4-Flash` for extraction, `Nemotron-3-Super`
as fallback. Code defaults are `openai/gpt-oss-120b` / `openai/gpt-oss-20b`.

The recorded eval ran earlier on the **Gemini free tier**, which is where things broke:
`gemini-2.5-pro` had a daily quota of **0**; `gemini-2.5-flash`/`-lite` hit 20/day;
`gemini-3.5-flash` was slow and intermittently 503. Fixes that carried over: multi-key
round-robin with per-key cooldowns, a fallback model, request-too-large detection ->
chunk halving in `extract.py`, empty/`finish_reason=length` retry with a larger output
budget, robust coercion of model-shaped tool args, a forced-submit step near the cap, and
per-question saves so a quota stop cannot discard completed answers.

## Proof (and honest failures)

Shipped `answers.json` (agent output): **22/25 answered with 58 verified citations,
0 invalid quotes**; Q16, Q21 and Q25 returned “Could not find verifiable evidence”. The
TS3012 brief (meetings a-c) carries 20 verified inline citations across decided / changed /
actions / open disagreements. `answers_curated.json` is a hand-curated reference with
**25/25 answers and 61 verified citations**; it is not agent output.

Own 10-question eval (`my_questions.json`, `eval.log`): **4/10 correct, 12/12 citations
valid on the questions that answered, ~22 s/question**. M05 was answered but semantically
wrong. M06-M10 never got to reason: the free-tier key returned HTTP 429, so five of the ten
were quota failures, not retrieval failures.

Three questions the agent got wrong, and why:

1. **Q16 (TS3010, navigation control).** Correct answer: the project manager favoured a
   joystick, the final costed design replaced it with push-buttons, and the special colour
   was given up to reach 12.50 Euro. The agent returned no verifiable evidence. Its query
   drift stayed on “joystick / navigation” and never included “push-buttons” or “special
   colour”, so it never retrieved the final turn, then submitted empty rather than
   broadening once more.
2. **Q21 (IS1007, component prices).** Correct answer: Speaker C said they would check
   prices, reported about fifteen (the speaker said “dollars”) for the fully featured
   version, and the team then decided two versions (with and without the LCD) because the
   LCD was too expensive. This is a three-hop question across meetings c and d (action ->
   figure -> LCD decision); the agent failed to chain the hops and returned no evidence.
3. **Q25 (ES2011, fruit/vegetable shapes).** Correct answer: they decided **not** to use
   fruit/vegetable shapes, keeping only fruit colours/patterns on the rubber, because a
   shape conflicts with holding the remote comfortably. Retrieval surfaced the fun
   shape/play-dough asides and the agent could not isolate the final “colour, not shape”
   decision, so it returned nothing. Verbatim citations would not have saved this: a real
   quote does not prove a claim, so the fix is a claim-to-quote entailment check, not just
   a substring check.

## Cost and time at 1,000 / 10,000 meetings

Ingest is pure code: this machine does 138 meetings in **3.5 s** (~25 s per 1,000,
~4 min per 10,000). Extraction is the only ingest LLM cost: ~1-2 calls per meeting,
~6-7k input tokens each, so 1,000 meetings is roughly 13M input tokens — a few dollars at
cheap-model rates — and about an hour sequentially, minutes if parallelised. Answering is
bounded by retrieved context (~2-5k tokens/question), not corpus size.

## What production needs

Incremental ingest and a queue for extraction; shard/partition the index by team; hybrid
BM25 + embeddings for paraphrase; versioned decision objects with evidence; an entailment
check between answer and quote; per-team access control; observability of
retrieval -> citation -> answer; and a regression set of hand-checked questions run on every
model or prompt change.
