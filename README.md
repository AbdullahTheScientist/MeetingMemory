# MeetingMemory

Turn the 138 AMI meeting transcripts (35 teams, ~676k words) into a searchable memory,
answer questions with word-for-word verified citations, and brief a team before its next
meeting. Built as the Catalist Agentic AI intern build test.

The agent retrieves against an index — it never pastes the corpus into a prompt. The same
code is bounded by *retrieved* tokens, not corpus size, so the design does not rely on the
data fitting in one context window.

## Layout

```
MeetingMemory/
  data/transcripts/*.txt   # 138 meetings (a-d per team)
  data/questions.json      # 25 questions + brief_task (team TS3012)
  my_questions.json        # 10 hand-written eval questions with must_contain keys
  .env                     # DEEPINFRA_API_KEY=... and MM_* overrides
  memory.db                # SQLite + FTS5, built by ingest.py
```

Scripts live in this directory and take the data directory as an argument.

## Run

No `pip install` is needed: the LLM client is standard-library only. Run everything from
this directory.

```powershell
python ingest.py data                          # 1. parse data/transcripts -> memory.db (SQLite+FTS5), seconds
python extract.py TS3012a TS3012b TS3012c       # 2. optional: LLM structured memory for the brief's team
python run_all.py data/questions.json           # 3. agent answers 25 questions + brief -> answers.json
python eval.py                                  # 4. score the agent on my_questions.json
```

`build_answers.py` writes a hand-curated answer set with the *same* code-verified citation
rules and no LLM calls:

```powershell
python build_answers.py                         # curated 25/25 set -> answers.json (overwrites the agent file)
```

Because step 4/`build_answers.py` write `answers.json`, copy the agent output first if you
want to keep both. The repository ships:

- **`answers.json`** — the agent's own output (the submission). 25 questions, **22 answered
  with 58 code-verified citations**; Q16, Q21, Q25 returned no verifiable evidence. Brief
  for TS3012 built from meetings a, b, c with 20 verified inline citations.
- **`answers_curated.json`** — a hand-curated reference produced by `build_answers.py`
  (25/25, 61 citations, 33-citation TS3012 brief). Not agent output; use it as a ceiling.

Smoke tests:

```powershell
python mem.py s TS3007 "kinetic"
python -c "import mem; print(mem.db.execute('select count(*) from turns').fetchone()[0])"
```

## Environment

Python 3.11. The only external service is an OpenAI-compatible `/chat/completions` endpoint;
the default is **DeepInfra**.

`llm.py` reads keys from `.env` (same folder): `DEEPINFRA_API_KEY=...`, or
`DEEPINFRA_API_KEY1..N` to rotate. A key that returns 429 is parked for a cooldown and the
others keep working. Model ids are configurable in `.env` / environment:

| var | shipped value | use |
|---|---|---|
| `MM_MODEL_AGENT` | `deepseek-ai/DeepSeek-V3.2` | tool loop + answer drafting |
| `MM_MODEL_EXTRACT` | `deepseek-ai/DeepSeek-V4-Flash-0731` | per-meeting structured extraction |
| `MM_MODEL_FALLBACK` | `nvidia/NVIDIA-Nemotron-3-Super-120B-A12B` | used if the primary fails |
| `MM_BASE_URL` | `https://api.deepinfra.com/v1/openai` | any OpenAI-compatible base URL |

Code defaults (if `.env` is absent) are `openai/gpt-oss-120b` (agent) and `openai/gpt-oss-20b`
(extract/fallback). Other OpenAI-compatible providers work by setting `MM_BASE_URL` and a
matching `DEEPINFRA_API_KEY`/`MM_API_KEYS`.

## Who does what

| File | Role | LLM? |
|---|---|---|
| config.py | model names, step cap | no |
| ingest.py | parse transcripts into turns, SQLite + FTS5 index | no |
| mem.py | search (team-locked, meeting-ordered), window, quote copy (`best_span`), quote check (`verify`) | no |
| extract.py | per meeting: extract decisions/actions/numbers; then judge what replaces earlier decisions; hash-cached | cheap model |
| agent.py | loop: model plans searches/reads/memory lookups; code runs tools, copies + verifies quotes, retries | agent model + code |
| run_all.py | runs all questions + brief, final quote re-check, writes answers.json | no |
| build_answers.py | curated answer set with the same code-verified citation rules | no |
| eval.py | own questions: correctness, citation validity, seconds/question | via agent |

## Where the model/code line is

- **Code (no LLM):** ingestion, tokenisation, BM25 search, team isolation, meeting ordering,
  chunking, caching, storage, supersession *state writes*, quote copying, literal quote
  verification, final answer assembly.
- **LLM:** which queries to run, whether a passage answers the question, which turn to cite
  (a turn id + hint, never a written quote), and the supersession judgement between two
  candidate items.
- The model never writes a citation string. It names a turn; code copies a contiguous span
  from that turn and refuses anything under six words or not found verbatim.

## What actually ran

- `ingest.py data` -> **48,148 turns / 138 meetings / 35 teams**.
- `extract.py TS3012a TS3012b TS3012c` -> 258 memory items, 81 marked superseded.
- `run_all.py data/questions.json` -> the shipped `answers.json`: **22/25 answered, 58
  verified citations, 0 invalid quotes**; Q16, Q21, Q25 answered "Could not find verifiable
  evidence". The TS3012 brief has 20 verified inline citations.
- `build_answers.py` -> `answers_curated.json`: **25/25 answers, 61 verified citations**,
  plus a 33-citation TS3012 brief.
- `eval.py` on `my_questions.json` -> **4/10 correct, 12/12 citations valid on answered
  questions, ~22 s/question** (`eval.log`). M05 was answered but semantically wrong; M06-M10
  were stopped by HTTP 429 free-tier quota, not by retrieval.

## Model notes and where things broke

- No SDK: direct REST from the standard library keeps the retrieval/citation code
  independent of vendor changes.
- The recorded eval ran on the Gemini free tier: `gemini-2.5-pro` had a daily quota of 0,
  `gemini-2.5-flash`/`-lite` hit 20/day, `gemini-3.5-flash` was slow and intermittently 503.
  That is why 5 of 10 eval questions show 429 rather than a reasoning failure. The project
  now targets DeepInfra to avoid that ceiling.
- Robustness added for this: multi-key round-robin with per-key cooldowns, fallback model,
  request-too-large detection -> chunk halving in `extract.py`, empty/`finish_reason=length`
  retry with a larger output budget, and per-question saves so a quota stop cannot discard
  finished answers.

## Scale (why 10,000 meetings is not one prompt)

SQLite + FTS5 here; the same code is bounded by *retrieved* tokens, not corpus size.
Ingestion is O(words) pure code (~25 s per 1,000 meetings on this machine). The only LLM
cost at ingest is one or two cheap extraction calls per meeting (~6-7k input tokens each),
so 1,000 meetings is on the order of a few dollars and about an hour sequentially, minutes
if parallelised. Answering is bounded by ~2-5k retrieved tokens per question.

Production would shard the index by team, add incremental ingest, keep per-meeting
structured memory so questions never scan the whole corpus, add a claim-to-quote entailment
check, and run a regression set on every model/prompt change.

## Submission checklist

| Requirement | Where |
|---|---|
| Ingest transcripts into searchable memory | `ingest.py`, `memory.db` |
| Answer 25 questions with 1-3 verified citations | `answers.json` |
| Brief Team TS3012 (decided / changed / actions / open) before meeting d | `answers.json` `brief` |
| 10 own questions, scored, right and wrong reported | `my_questions.json`, `eval.log` |
| Cost/time at 1,000 meetings | this README + `WRITEUP.md` |
| Three wrong questions explained | `WRITEUP.md` |
| Architecture, model-vs-code line, tools, failures | `WRITEUP.md` |

The live agent run is the evidence that the loop, tools and verification work end to end;
its unanswered questions are documented honestly in `WRITEUP.md` rather than hidden. The
curated set is provided as a reference for a complete, all-citations-valid answer sheet.
