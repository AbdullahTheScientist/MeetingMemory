"""CODE: runs the 25 questions + the brief and writes answers.json. Quotes are re-verified before saving.

Resilient by design: one bad model call must not throw away 20 good answers. Each answer is
appended and the file is rewritten after every question, so a quota stop leaves usable output.
"""
import json, sys, time
import agent, mem


def main(path="../data/questions.json"):
    data = json.load(open(path))
    answers = []

    def save(brief=""):
        clean = []
        for a in answers:
            a["citations"] = [c for c in a.get("citations", []) if mem.verify(c["meeting_id"], c["quote"])]
            clean.append(a)
        json.dump({"answers": clean, "brief": brief}, open("answers.json", "w", encoding="utf-8"), indent=2)

    for q in data["questions"]:
        print(q["question_id"], q["question"][:70], flush=True)
        t0 = time.time()
        try:
            a = agent.answer_question(q)
        except Exception as e:
            a = {"question_id": q["question_id"], "answer": f"Agent error: {e}", "citations": []}
        a["citations"] = [c for c in a.get("citations", []) if mem.verify(c["meeting_id"], c["quote"])]
        answers.append(a)
        print(f"  -> {len(a['citations'])} cites, {time.time()-t0:.1f}s", flush=True)
        save()

    try:
        brief = agent.write_brief(data["brief_task"]["team"])
    except Exception as e:
        brief = f"(brief failed: {e})"

    save(brief)
    print("wrote answers.json; citations:", sum(len(a["citations"]) for a in answers))


if __name__ == "__main__":
    main(sys.argv[1] if len(sys.argv) > 1 else "../data/questions.json")
