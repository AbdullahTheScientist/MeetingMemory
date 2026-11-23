"""Ingest: pure code, no LLM. Parse transcripts -> turns -> SQLite (FTS5).

Importing this module must have no side effects; call main(data_dir) or run it as a script.
"""
import re, sqlite3, sys, glob, os

HDR = re.compile(r"^(\d\d:\d\d:\d\d) (Speaker [A-D])\s*$")


def main(data="../data"):
    db = sqlite3.connect("memory.db")
    db.executescript("""
    DROP TABLE IF EXISTS turns; DROP TABLE IF EXISTS fts;
    CREATE TABLE turns(id INTEGER PRIMARY KEY, meeting TEXT, team TEXT, seq TEXT, turn_no INT,
      t TEXT, speaker TEXT, text TEXT);
    CREATE VIRTUAL TABLE fts USING fts5(text, content='turns', content_rowid='id', tokenize='porter unicode61');
    """)
    n = 0
    for f in sorted(glob.glob(f"{data}/transcripts/*.txt")):
        mid = os.path.basename(f)[:-4]
        team, seq = mid[:-1], mid[-1]
        cur = None
        no = 0
        rows = []
        for line in open(f, encoding="utf-8"):
            line = line.rstrip("\n")
            m = HDR.match(line)
            if m:
                if cur:
                    rows.append(cur)
                no += 1
                cur = [mid, team, seq, no, m.group(1), m.group(2), ""]
            elif cur and line.strip():
                cur[6] += (" " if cur[6] else "") + line.strip()
        if cur:
            rows.append(cur)
        for r in rows:
            db.execute("INSERT INTO turns(meeting,team,seq,turn_no,t,speaker,text) VALUES(?,?,?,?,?,?,?)", r)
            n += 1
    db.execute("INSERT INTO fts(rowid,text) SELECT id,text FROM turns")
    db.commit()
    print("turns:", n)
    return n


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../data")
