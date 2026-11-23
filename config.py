import os

import llm  # noqa: F401  (loads .env so the MM_* settings below are visible)

DB = os.environ.get("MM_DB", "memory.db")
# DeepInfra only. Model ids change over time: check DeepInfra's model list and override via
# MM_MODEL_AGENT / MM_MODEL_EXTRACT / MM_MODEL_FALLBACK in .env.
MODEL_AGENT = os.environ.get("MM_MODEL_AGENT") or llm.default_model("agent")           # reasoning + answers
MODEL_EXTRACT = os.environ.get("MM_MODEL_EXTRACT") or llm.default_model("extract")     # cheap per-meeting extraction
MODEL_FALLBACK = os.environ.get("MM_MODEL_FALLBACK") or llm.default_model("fallback")  # if the primary fails
MAX_STEPS = 14