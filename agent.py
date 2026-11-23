"""LLM STAGE 2 LLM decides what to search/read and drafts the answer;
CODE executes the tools, enforces meeting order, copies quotes, and verifies them."""
import json
import llm
from config import MODEL_AGENT, MAX_STEPS
import mem

CITE = {"type": "array", "items": {"type": "object", "properties": {
    "meeting": {"type": "string"}, "turn": {"type": "integer"},
    "hint": {"type": "string", "description": "a few words from the turn that support the claim"}},
    "required": ["meeting", "turn"]}}
TOOLS = [
 {"name": "search", "description": "Keyword search inside ONE team's transcripts. Returns turns as [meeting#turn speaker] text.",
  "parameters": {"type": "object", "properties": {"query": {"type": "string"}, "meeting": {"type": "string", "description": "optional, e.g. TS3007d"}}, "required": ["query"]}},
 {"name": "window", "description": "Read turns around a turn number in a meeting.",
  "parameters": {"type": "object", "properties": {"meeting": {"type": "string"}, "turn": {"type": "integer"}}, "required": ["meeting", "turn"]}},
 {"name": "memory", "description": "List extracted decisions/actions for the team with status current/superseded (may be empty if extract.py was not run).",
  "parameters": {"type": "object", "properties": {"topic": {"type": "string"}}}},
]
SUBMIT_ANSWER = {"name": "submit_answer", "description": "Final answer, 1-3 sentences, with 1-3 citations given as meeting + turn number (NOT quotes).",
  "parameters": {"type": "object", "properties": {"answer": {"type": "string"}, "citations": CITE}, "required": ["answer", "citations"]}}
SUBMIT_BRIEF = {"name": "submit_brief", "description": "Final brief. Every point needs 1-3 citations (meeting + turn).",
  "parameters": {"type": "object", "properties": {"sections": {"type": "array", "items": {"type": "object", "properties": {
      "heading": {"type": "string"}, "points": {"type": "array", "items": {"type": "object", "properties": {
          "text": {"type": "string"}, "citations": CITE}, "required": ["text", "citations"]}}}, "required": ["heading", "points"]}}},
      "required": ["sections"]}}

RULES = """Meetings of a team happen in order a < b < c < d. A LATER meeting can replace an earlier decision (often when costs
were checked against the 12.50 Euro budget), so for 'what changed' questions search the later meetings too and report first AND final state.
Speakers are letters (Speaker A..D); give the letter, and the role only if the transcripts make it clear.
Search a few times with different words (the speech is messy: 'um', fillers, STT errors, 'L_C_D_' for LCD). Use window to read context.
Never write quotes yourself: submit meeting + turn number (and a short hint) and code copies the exact words.
Work in a tight loop: after at most 6-8 tool calls you MUST call the submit tool with your best answer and 1-3 turns.
Do not keep searching for perfect evidence. If the evidence is genuinely missing, submit the best-supported partial answer."""

def _s(v):
    """Tool args come from a model: coerce scalars/containers instead of crashing the loop."""
    if v is None: return ""
    if isinstance(v, (dict, list)): return json.dumps(v)
    return str(v)

def _i(v, default=0):
    try: return int(v)
    except Exception: return default

def run_tool(name, a, team, upto):
    a = {k: v for k, v in (a or {}).items()}
    if name == "search": return mem.fmt(mem.search(team, _s(a.get("query")), 10, _s(a.get("meeting")) or None, upto))
    if name == "window": return mem.fmt(mem.window(_s(a.get("meeting")), _i(a.get("turn"))), 900)
    if name == "memory":
        q = "SELECT meeting,turn,type,topic,summary,speaker,status FROM memory_items WHERE team=?" + (" AND seq<=?" if upto else "") + " ORDER BY seq,turn"
        rows = mem.db.execute(q, [team] + ([upto] if upto else [])).fetchall()
        t = _s(a.get("topic")).lower()
        rows = [r for r in rows if not t or t in (r["topic"] or "").lower() or t in (r["summary"] or "").lower()]
        return "\n".join(f"{r['meeting']}#{r['turn']} {r['type']} [{r['status']}] {r['topic']}: {r['summary']} ({r['speaker']})" for r in rows[:60]) or "(memory empty)"

def resolve(cites, team, upto):
    """CODE: turn the model's (meeting, turn, hint) into verified exact quotes. Returns (good, problems)."""
    good, bad = [], []
    for c in (cites or []):
        if not isinstance(c, dict): bad.append(f"{c!r} not a citation object"); continue
        m, t = _s(c.get("meeting")), _i(c.get("turn"))
        if not m.startswith(team) or (upto and m[-1] > upto): bad.append(f"{m}#{t} not allowed"); continue
        q = mem.best_span(m, t, _s(c.get("hint")))
        (good if q else bad).append({"meeting_id": m, "quote": q} if q else f"{m}#{c['turn']} could not give a >=6-word quote")
    return good, bad

def loop(prompt, submit_tool, team, upto=None):
    contents = [llm.user_text(prompt)]
    tools = TOOLS + [submit_tool]
    for step in range(MAX_STEPS):
        if step == MAX_STEPS - 2:
            contents.append(llm.user_text("You have one step left. You MUST call the submit tool now."))
        content, calls = llm.tool_step(MODEL_AGENT, RULES, tools, contents)
        contents.append(content)
        if not calls:
            contents.append(llm.user_text("Use the tools, then call the submit tool.")); continue
        for name, args, _cid in calls:
            if name == submit_tool["name"]:
                return args                                   # LLM finished; CODE now resolves + verifies the citations
        contents.append(llm.tool_results([(cid, n, run_tool(n, args, team, upto)) for n, args, cid in calls]))
    return None

def answer_question(q):
    team = q["team"]
    prompt = f"Team {team}. Meetings: {', '.join(mem.meetings(team))}. Question: {q['question']}"
    for _ in range(3):                                    # retry if citations fail code verification
        out = loop(prompt, SUBMIT_ANSWER, team)
        if not out: break
        good, bad = resolve(out["citations"], team, None)
        if good: return {"question_id": q["question_id"], "answer": out["answer"], "citations": good}
        prompt += f"\nYour last citations failed verification: {bad}. Search again and cite different turns."
    return {"question_id": q["question_id"], "answer": "Could not find verifiable evidence.", "citations": []}

def write_brief(team, upto="c"):
    prompt = (f"Write the brief team {team} should read before their final meeting. Use ONLY meetings up to '{upto}' "
              f"({', '.join(m for m in mem.meetings(team) if m[-1] <= upto)}). "
              "Sections: 1 Decided, 2 What changed (show before->after), 3 Open actions and owners, 4 Disagreements still open. "
              "Search broadly per section (decision, agreed, I will, next meeting, budget, cost, disagree, but). Every point needs citations.")
    out = loop(prompt, SUBMIT_BRIEF, team, upto)
    lines = []
    for s in (out or {}).get("sections", []):
        lines.append("\n" + s["heading"].upper())
        for p in s["points"]:
            good, _ = resolve(p["citations"], team, upto)
            if good: lines.append("- " + p["text"] + " " + " ".join(f'[{c["meeting_id"]}: "{c["quote"]}"]' for c in good))
    return "\n".join(lines)
