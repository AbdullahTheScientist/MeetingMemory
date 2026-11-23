"""LLM STAGE 1 (offline, once per meeting, Gemini Flash): turn messy speech into structured memory + track what is current.
Code: chunking, hashing/caching, storage, ordering.  LLM (cheap model): extraction + supersession judgement."""
import json, re, sys, hashlib, sqlite3, os
import llm
from config import DB, MODEL_EXTRACT
import mem
db = mem.db
db.executescript("""
CREATE TABLE IF NOT EXISTS memory_items(id INTEGER PRIMARY KEY, meeting TEXT, team TEXT, seq TEXT, turn INT,
  type TEXT, topic TEXT, summary TEXT, speaker TEXT, status TEXT DEFAULT 'current', superseded_by INT);
CREATE TABLE IF NOT EXISTS processed(meeting TEXT PRIMARY KEY, hash TEXT);
""")

CHUNK_TOKENS = int(os.environ.get("MM_EXTRACT_TOKENS", "3000"))

def ask(prompt):
    return llm.ask_json(MODEL_EXTRACT, prompt)

def as_list(res):
    """Models sometimes wrap the list in an object ({"items":[...]}) or return junk; always give back a list of dicts."""
    if isinstance(res, dict):
        res = next((v for v in res.values() if isinstance(v, list)), [])
    return [x for x in res if isinstance(x, dict)] if isinstance(res, list) else []

def ask_lines(lines):
    """Ask on one transcript chunk; halve it if the provider says the request is too large."""
    try:
        return as_list(ask(EXTRACT + "\n".join(lines)))
    except llm.RequestTooLarge:
        if len(lines) <= 1:
            raise
        mid = len(lines) // 2
        return ask_lines(lines[:mid]) + ask_lines(lines[mid:])

def chunk_lines(lines, budget=CHUNK_TOKENS):
    """Group turns so each prompt stays under the per-request token budget."""
    chunks, cur, size = [], [], 0
    for line in lines:
        t = llm.estimate_tokens(line)
        if cur and size + t > budget:
            chunks.append(cur); cur, size = [], 0
        cur.append(line); size += t
    if cur:
        chunks.append(cur)
    return chunks

EXTRACT = """You read part of a meeting transcript (team designing a TV remote). Extract items worth remembering:
decisions, proposals, objections, action items (who promised to do what), and numbers (costs/prices).
Return ONLY a JSON list: [{"type":"decision|proposal|objection|action|number","topic":"2-3 word topic","summary":"one line","speaker":"Speaker X","turn":<turn number>}]
Use the turn numbers shown. Do not invent anything.

TRANSCRIPT:
"""

SUPERSEDE = """Earlier remembered decisions for this team (id: meeting | topic | summary):
{old}

New decisions from meeting {meeting}:
{new}

For each NEW item, list ids of EARLIER items it replaces or reverses (same subject, e.g. a feature dropped or a material changed).
Return ONLY JSON: [{{"new_id":<id>,"replaces":[<old ids>]}}]. Use [] if nothing is replaced."""

SKIPPED_BATCHES = []

def supersede(meeting, team, seq):
    """LLM judges which earlier decisions a meeting's decisions replace. Small batches + capped history keep the
    prompt and the reply short (long replies were the cause of empty/truncated JSON). A failed batch is skipped, not fatal."""
    new = db.execute("SELECT id,topic,summary FROM memory_items WHERE meeting=? AND type IN('decision','proposal')", (meeting,)).fetchall()
    old = db.execute("SELECT id,meeting,topic,summary FROM memory_items WHERE team=? AND seq<? AND type IN('decision','proposal') AND status='current' ORDER BY seq,turn", (team, seq)).fetchall()
    old = old[-80:]
    old_ids = {o["id"] for o in old}
    if not new or not old: return
    old_txt = "\n".join(f"{o['id']}: {o['meeting']} | {o['topic']} | {o['summary']}" for o in old)
    for i in range(0, len(new), 10):
        batch = new[i:i + 10]
        new_txt = "\n".join(f"{n['id']}: {n['topic']} | {n['summary']}" for n in batch)
        try:
            res = as_list(ask(SUPERSEDE.format(old=old_txt, new=new_txt, meeting=meeting)))
        except llm.QuotaExhausted:
            raise
        except Exception as e:
            print(f"   supersession batch skipped ({meeting}): {str(e)[:90]}")
            SKIPPED_BATCHES.append((meeting, i)); continue
        for r in res:
            reps = r.get("replaces", [])
            for oid in (reps if isinstance(reps, list) else []):
                if isinstance(oid, int) and oid in old_ids and isinstance(r.get("new_id"), int):
                    db.execute("UPDATE memory_items SET status='superseded', superseded_by=? WHERE id=?", (r["new_id"], oid))

def process(meeting):
    rows = db.execute("SELECT turn_no,speaker,text FROM turns WHERE meeting=? ORDER BY turn_no", (meeting,)).fetchall()
    h = hashlib.sha256("".join(r["text"] for r in rows).encode()).hexdigest()
    if db.execute("SELECT 1 FROM processed WHERE meeting=? AND hash=?", (meeting, h)).fetchone(): return  # cache
    team, seq = meeting[:-1], meeting[-1]
    db.execute("DELETE FROM memory_items WHERE meeting=?", (meeting,))
    for chunk in chunk_lines([f"#{r['turn_no']} {r['speaker']}: {r['text']}" for r in rows]):
        for it in ask_lines(chunk):
            db.execute("INSERT INTO memory_items(meeting,team,seq,turn,type,topic,summary,speaker) VALUES(?,?,?,?,?,?,?,?)",
                       (meeting, team, seq, it.get("turn"), it.get("type"), it.get("topic"), it.get("summary"), it.get("speaker")))
    db.commit()                                   # keep the extraction even if supersession has trouble
    supersede(meeting, team, seq)
    db.execute("INSERT OR REPLACE INTO processed VALUES(?,?)", (meeting, h)); db.commit()

if __name__ == "__main__":
    meetings = sys.argv[1:] or [r[0] for r in db.execute("SELECT DISTINCT meeting FROM turns ORDER BY meeting")]  # a<b<c<d order matters
    failed = []
    for m in meetings:
        print("extract", m, flush=True)
        try:
            process(m)
            n = db.execute("SELECT COUNT(*) FROM memory_items WHERE meeting=?", (m,)).fetchone()[0]
            sup = db.execute("SELECT COUNT(*) FROM memory_items WHERE status='superseded' AND superseded_by IN (SELECT id FROM memory_items WHERE meeting=?)", (m,)).fetchone()[0]
            print(f"   ok {m}: {n} items saved, {sup} earlier decisions marked superseded by it", flush=True)
        except llm.QuotaExhausted as e:
            db.rollback(); print(f"\nSTOPPED at {m}: {e}"); break
        except Exception as e:
            db.rollback(); failed.append(m); print(f"   SKIPPED {m}: {str(e)[:120]}")
    print(f"done. meetings failed: {failed or 'none'}; supersession batches skipped: {len(SKIPPED_BATCHES)}")
    if failed or SKIPPED_BATCHES: print("Re-run `python extract.py` to retry failed meetings (finished ones are cached).")