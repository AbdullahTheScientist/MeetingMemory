"""CODE ONLY. Search, read, and citation tools. No LLM here."""
import sqlite3, re, sys
from config import DB
db = sqlite3.connect(DB); db.row_factory = sqlite3.Row

def norm(s): return re.sub(r"\s+", " ", s.lower()).strip()

def search(team, query, k=8, meeting=None, upto=None):
    """BM25 over turns, locked to one team. upto='c' hides meetings after c (used for the brief)."""
    query = query if isinstance(query, str) else str(query)
    q = " OR ".join(w for w in re.findall(r"[A-Za-z0-9']+", query) if len(w) > 1)
    if not q: return []
    sql = "SELECT t.meeting,t.turn_no,t.speaker,t.text FROM fts JOIN turns t ON t.id=fts.rowid WHERE fts MATCH ? AND t.team=?"
    args = [q, team]
    if meeting: sql += " AND t.meeting=?"; args.append(meeting)
    if upto: sql += " AND t.seq<=?"; args.append(upto)
    sql += " ORDER BY bm25(fts) LIMIT ?"; args.append(k)
    rows = db.execute(sql, args).fetchall()
    return sorted(rows, key=lambda r: (r["meeting"], r["turn_no"]))   # meeting order decided by CODE

def meetings(team):
    return [r["meeting"] for r in db.execute(
        "SELECT DISTINCT meeting FROM turns WHERE team=? ORDER BY meeting", (team,))]


def window(meeting, turn, before=2, after=4):
    turn = int(turn)                                   # models sometimes send turn numbers as strings
    return db.execute("SELECT meeting,turn_no,speaker,text FROM turns WHERE meeting=? AND turn_no BETWEEN ? AND ? ORDER BY turn_no",
                      (meeting, turn - before, turn + after)).fetchall()

def turn_text(meeting, turn):
    r = db.execute("SELECT text FROM turns WHERE meeting=? AND turn_no=?", (meeting, int(turn))).fetchone()
    return r["text"] if r else None

def verify(meeting, quote):
    """Grader rule: >=6 words, literal substring (case/space-insensitive) inside ONE turn."""
    if not isinstance(quote, str) or len(quote.split()) < 6: return False
    n = norm(quote)
    return any(n in norm(r["text"]) for r in db.execute("SELECT text FROM turns WHERE meeting=?", (meeting,)))

def best_span(meeting, turn, hint=""):
    """The LLM names a TURN (and optionally hint words). CODE copies the exact words: picks the sentence
    with most overlap with the hint, pads with neighbours until >=6 words. Returns None if impossible."""
    hint = hint if isinstance(hint, str) else ""
    text = turn_text(meeting, turn)
    if not text: return None
    sents = [s.strip() for s in re.split(r"(?<=[.?!])\s+", text) if s.strip()]
    if not sents: return None
    h = set(re.findall(r"[a-z0-9']+", hint.lower()))
    i = max(range(len(sents)), key=lambda j: len(h & set(re.findall(r"[a-z0-9']+", sents[j].lower()))) if h else -j)
    lo = hi = i
    span = sents[i]
    while len(span.split()) < 6 and (lo > 0 or hi < len(sents) - 1):
        if hi < len(sents) - 1: hi += 1
        elif lo > 0: lo -= 1
        span = " ".join(sents[lo:hi + 1])
    words = span.split()
    if len(words) > 40: span = " ".join(words[:40])        # keep quotes short; still a literal prefix
    return span if verify(meeting, span) else None

def fmt(rows, maxc=600):
    return "\n".join(f"[{r['meeting']}#{r['turn_no']} {r['speaker']}] {r['text'][:maxc]}" for r in rows) or "(no results)"

if __name__ == "__main__":     # manual use: python mem.py s TEAM "query"   |   python mem.py w MEETING TURN
    if sys.argv[1] == "s": print(fmt(search(sys.argv[2], sys.argv[3])))
    if sys.argv[1] == "w": print(fmt(window(sys.argv[2], int(sys.argv[3]))))
