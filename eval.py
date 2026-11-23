"""CODE: score the agent on YOUR OWN questions. my_questions.json = [{"question_id","team","question","must_contain":["kinetic","battery"]}]
Answers you verified by reading the transcripts -> put the key facts in must_contain. Reports correctness + citation validity + time.
Set MM_EVAL_LIMIT=3 to score only the first few (useful on a tight free-tier quota). Output is unbuffered.
"""
import json, os, time
import agent, mem


def main():
    qs = json.load(open("my_questions.json"))
    limit = int(os.environ.get("MM_EVAL_LIMIT", "0"))
    if limit:
        qs = qs[:limit]
    ok = valid = total_c = 0
    t0 = time.time()
    for q in qs:
        t = time.time()
        try:
            a = agent.answer_question(q)
            err = ""
        except Exception as e:
            a = {"answer": "", "citations": []}
            err = f"ERROR {e}"
        hit = bool(a["answer"]) and all(k.lower() in a["answer"].lower() for k in q["must_contain"])
        v = sum(1 for c in a["citations"] if mem.verify(c["meeting_id"], c["quote"]))
        ok += hit
        valid += v
        total_c += len(a["citations"])
        print(q["question_id"], "CORRECT" if hit else "WRONG", f"cites {v}/{len(a['citations'])}",
              f"{time.time()-t:.1f}s", err, "|", a["answer"][:100], flush=True)
    print(f"correct {ok}/{len(qs)}; valid citations {valid}/{total_c}; "
          f"seconds/question {(time.time()-t0)/max(1,len(qs)):.1f}", flush=True)


if __name__ == "__main__":
    main()
