"""DeepInfra-only LLM client (stdlib only, OpenAI-compatible /chat/completions).

The rest of the project needs four things from this file: user_text, tool_step, tool_results, ask_json
(plus RequestTooLarge, QuotaExhausted and estimate_tokens for extract.py). Keeping it small keeps the
retrieval/citation code independent of the vendor.

.env (same folder as this file):
    DEEPINFRA_API_KEY=...            # or DEEPINFRA_API_KEY1, DEEPINFRA_API_KEY2, ... to rotate keys
    MM_MODEL_AGENT=openai/gpt-oss-120b      # optional overrides: MM_MODEL_EXTRACT, MM_MODEL_FALLBACK
    MM_MAX_TOKENS=4096                      # optional; MM_REASONING_EFFORT=low|medium|high (only sent if set)
Requests are round-robined across the keys; a key that returns 429 is parked for a cooldown so the others keep working.
"""
import json
import os
import re
import socket
import threading
import time
import urllib.error
import urllib.request


def _load_env():
    here = os.path.dirname(os.path.abspath(__file__))
    path = os.path.join(here, ".env")
    if not os.path.exists(path):
        return
    with open(path, encoding="utf-8") as fh:
        for line in fh:
            m = re.match(r"\s*([A-Za-z0-9_]+)\s*=\s*(.*?)\s*$", line)
            if not m:
                continue
            k, v = m.group(1), m.group(2).strip()
            if v[:1] in ("'", '"'):
                end = v.find(v[0], 1)
                v = v[1:end] if end != -1 else v.strip(v[0])
            else:
                v = v.split("#", 1)[0].strip()          # drop trailing `# comment`
            low = k.lower()
            if re.fullmatch(r"deepinfra_?api_?keys?\d*", low):
                os.environ.setdefault(re.sub(r"[^A-Za-z0-9]", "", low).upper().replace("DEEPINFRAAPIKEY", "DEEPINFRA_API_KEY"), v)
            elif k.upper().startswith("MM_"):
                os.environ.setdefault(k.upper(), v)


_load_env()

BASE_URL = (os.environ.get("MM_BASE_URL") or "https://api.deepinfra.com/v1/openai").rstrip("/")
DEFAULT_MODELS = {"agent": "openai/gpt-oss-120b", "extract": "openai/gpt-oss-20b", "fallback": "openai/gpt-oss-20b"}
RETRIES = int(os.environ.get("MM_RETRIES", "5"))
TIMEOUT = float(os.environ.get("MM_TIMEOUT", "120"))             # seconds per HTTP request; a timeout rotates keys
KEY_COOLDOWN = float(os.environ.get("MM_KEY_COOLDOWN", "60"))    # seconds to park a key after HTTP 429 (if no retry-after)
KEY_MAX_WAIT = float(os.environ.get("MM_KEY_MAX_WAIT", "65"))    # longest we sleep waiting for a parked key
MIN_INTERVAL = float(os.environ.get("MM_MIN_INTERVAL", "0"))     # optional pause between calls
USER_AGENT = os.environ.get("MM_USER_AGENT", "MeetingMemory/1.0")
TOKEN_SAFETY = float(os.environ.get("MM_TOKEN_SAFETY", "1.25"))  # chars/4 is optimistic; pad the estimate
MAX_TOKENS = int(os.environ.get("MM_MAX_TOKENS", "4096"))        # gpt-oss spends part of this on hidden reasoning
TEMP = float(os.environ.get("MM_TEMP", "0.2"))
OVERLOAD_TRIES = int(os.environ.get("MM_OVERLOAD_TRIES", "3"))      # "model busy" answers tolerated before using the fallback model
OVERLOAD_BACKOFF = float(os.environ.get("MM_OVERLOAD_BACKOFF", "3"))  # seconds; doubles each time
_last_call = [0.0]


def default_model(role):
    return DEFAULT_MODELS[role]


class RequestTooLarge(RuntimeError):
    """The request is bigger than the model accepts; the caller must split the input (extract.py halves its chunk)."""

    def __init__(self, tokens=0, limit=None):
        self.tokens = tokens
        self.limit = limit
        super().__init__(f"Request (~{tokens} tokens) is too large for the model; split the input into smaller chunks")


class QuotaExhausted(RuntimeError):
    """Every key is parked for a long time (rate/quota). Waiting in-process is pointless: stop and re-run later."""


def estimate_tokens(text):
    if not text:
        return 0
    return max(1, int(len(text) / 4.0 * TOKEN_SAFETY) + 8)


class _KeyPool:
    """Round-robin keys with per-key cooldowns."""

    def __init__(self, keys):
        self.keys = list(dict.fromkeys(k for k in keys if k))
        self._i = 0
        self._cool = {}
        self._lock = threading.Lock()

    def __len__(self):
        return len(self.keys)

    def acquire(self):
        """Return (key, seconds_to_wait) for the key that is available soonest."""
        with self._lock:
            if not self.keys:
                raise RuntimeError("No API key: add DEEPINFRA_API_KEY (or DEEPINFRA_API_KEY1..N) to .env next to llm.py")
            now = time.time()
            n = len(self.keys)
            best = None
            for _ in range(n):
                k = self.keys[self._i % n]
                self._i += 1
                wait = max(0.0, self._cool.get(k, 0.0) - now)
                if wait <= 0:
                    return k, 0.0
                if best is None or wait < best[1]:
                    best = (k, wait)
            return best

    def penalize(self, key, seconds):
        if key:
            with self._lock:
                self._cool[key] = max(self._cool.get(key, 0.0), time.time() + max(1.0, seconds))


def _collect_keys():
    keys = []

    def add(value):
        for part in re.split(r"[,;\s]+", value or ""):
            if part.strip() and part.strip() not in keys:
                keys.append(part.strip())

    add(os.environ.get("MM_API_KEYS"))
    add(os.environ.get("DEEPINFRA_API_KEYS"))
    add(os.environ.get("DEEPINFRA_API_KEY"))
    for name in sorted(os.environ):
        if re.fullmatch(r"DEEPINFRA_API_KEY\d+", name.upper()):
            add(os.environ[name])
    return keys


_KEYS = _KeyPool(_collect_keys())


def _parse_duration(value):
    if not value:
        return 0.0
    total = 0.0
    for num, unit in re.findall(r"([\d.]+)\s*(ms|s|m|h|d)", str(value).strip()):
        total += float(num) * {"ms": 0.001, "s": 1.0, "m": 60.0, "h": 3600.0, "d": 86400.0}[unit]
    return total


def _retry_after(err):
    try:
        h = {str(k).lower(): v for k, v in err.headers.items()}
    except Exception:
        return KEY_COOLDOWN
    try:
        return max(1.0, float(h.get("retry-after")))
    except (TypeError, ValueError):
        pass
    waits = [_parse_duration(h.get(n)) for n in ("x-ratelimit-reset-tokens", "x-ratelimit-reset-requests", "x-ratelimit-reset")]
    waits = [w for w in waits if w > 0]
    return max(waits) if waits else KEY_COOLDOWN


def _is_timeout(err):
    if isinstance(err, (TimeoutError, socket.timeout)):
        return True
    return isinstance(getattr(err, "reason", None), (TimeoutError, socket.timeout))


def _call(model, send, tokens=0):
    """Retry transient errors / rotate keys, then try MM_MODEL_FALLBACK. `send(model, key)` does one request."""
    last = None
    models = [model]
    fb = os.environ.get("MM_MODEL_FALLBACK") or DEFAULT_MODELS["fallback"]
    if fb != model:
        models.append(fb)
    attempts = max(RETRIES, len(_KEYS), 1)
    for m in models:
        overloaded = 0
        for attempt in range(attempts):
            key, wait = _KEYS.acquire()
            if wait > 2 * KEY_MAX_WAIT:
                raise QuotaExhausted(f"All API keys are rate-limited for about {int(wait)}s more. "
                                     f"Stop and re-run later; finished work is cached.")
            if wait > 0:
                print(f"   [llm] waiting {wait:.0f}s for rate limit to clear...", flush=True)
                time.sleep(min(wait, KEY_MAX_WAIT))
            if MIN_INTERVAL:
                gap = MIN_INTERVAL - (time.time() - _last_call[0])
                if gap > 0:
                    time.sleep(gap)
            _last_call[0] = time.time()
            try:
                return send(m, key)
            except (RequestTooLarge, QuotaExhausted):
                raise
            except urllib.error.HTTPError as e:
                detail = e.read().decode("utf-8", "replace")
                last = f"{m}: HTTP {e.code}: {detail[:600]}"
                if e.code == 413 or (e.code == 400 and re.search(r"context|too (long|large)|maximum.*tokens", detail, re.I)):
                    raise RequestTooLarge(tokens)
                if e.code == 429 and re.search(r"engine_overloaded|model busy|overloaded", detail, re.I):
                    # The MODEL is at capacity: every key gets the same answer, so do not park the key.
                    overloaded += 1
                    print(f"   [llm] {m} is overloaded ({overloaded}/{OVERLOAD_TRIES}); not a key limit", flush=True)
                    if overloaded >= OVERLOAD_TRIES:
                        break                          # give up on this model, try the fallback model
                    time.sleep(min(30, OVERLOAD_BACKOFF * 2 ** (overloaded - 1)))
                    continue
                if e.code == 429:
                    secs = _retry_after(e)
                    print(f"   [llm] HTTP 429, key parked for {secs:.0f}s: {detail[:140]}", flush=True)
                    _KEYS.penalize(key, secs)
                    if attempt < attempts - 1:
                        continue                      # rotate to another key immediately
                    break                             # every key limited: try the fallback model
                if e.code in (500, 502, 503, 504) and attempt < attempts - 1:
                    time.sleep(min(15, 2 ** attempt) + attempt)
                    continue
                break                                 # other errors (401, 404 model not found...): try the fallback model
            except Exception as e:                    # network reset, timeout, ...
                last = f"{m}: {type(e).__name__}: {e}"
                if attempt < attempts - 1:
                    if not _is_timeout(e):
                        time.sleep(min(15, 2 ** attempt))
                    continue
    raise RuntimeError(f"LLM call failed ({last})")


def _post(model, body):
    tokens = estimate_tokens(json.dumps(body))

    def send(m, key):
        b = dict(body)
        b["model"] = m
        effort = os.environ.get("MM_REASONING_EFFORT")
        if effort and "gpt-oss" in m.lower() and "reasoning_effort" not in b:
            b["reasoning_effort"] = effort
        req = urllib.request.Request(
            f"{BASE_URL}/chat/completions",
            data=json.dumps(b).encode("utf-8"),
            headers={"Content-Type": "application/json", "Authorization": f"Bearer {key}", "User-Agent": USER_AGENT},
            method="POST",
        )
        with urllib.request.urlopen(req, timeout=TIMEOUT) as resp:
            return json.loads(resp.read().decode("utf-8"))

    return _call(model, send, tokens)


# ---- conversation helpers. The project keeps messages in a small neutral format ({"role","parts"}); it is
# ---- converted to OpenAI chat messages only here, so agent.py never needs to know the wire format.
def user_text(prompt):
    return {"role": "user", "parts": [{"text": prompt}]}


def tool_results(results):
    """results: [(call_id, name, output)]"""
    parts = []
    for cid, name, out in results:
        parts.append({"functionResponse": {"name": name, "id": cid, "response": {"result": str(out)}}})
    return {"role": "user", "parts": parts}


def _calls(content):
    calls = []
    for part in (content or {}).get("parts", []):
        fc = part.get("functionCall")
        if fc:
            calls.append((fc.get("name"), fc.get("args") or {}, fc.get("id")))
    return calls


def _messages(system, contents):
    msgs = [{"role": "system", "content": system}]
    for c in contents:
        parts = c.get("parts", [])
        texts = [p["text"] for p in parts if "text" in p]
        if c.get("role") == "user":
            if texts:
                msgs.append({"role": "user", "content": "\n".join(texts)})
            for p in parts:
                fr = p.get("functionResponse")
                if fr:
                    msgs.append({"role": "tool", "tool_call_id": fr.get("id") or fr.get("name"),
                                 "content": str((fr.get("response") or {}).get("result", ""))})
        else:
            msg = {"role": "assistant"}
            if texts:
                msg["content"] = "\n".join(texts)
            tcs = [{"id": p["functionCall"].get("id") or f"call_{i}", "type": "function",
                    "function": {"name": p["functionCall"].get("name"),
                                 "arguments": json.dumps(p["functionCall"].get("args") or {})}}
                   for i, p in enumerate(x for x in parts if "functionCall" in x)]
            if tcs:
                msg["tool_calls"] = tcs
            msgs.append(msg)
    return msgs


def tool_step(model, system, tools, contents):
    """One agent turn -> (model_content, [(name, args, call_id), ...])."""
    data = _post(model, {
        "messages": _messages(system, contents),
        "tools": [{"type": "function", "function": t} for t in tools],
        "tool_choice": "auto",
        "temperature": TEMP,
        "max_tokens": MAX_TOKENS,
    })
    choices = data.get("choices") or []
    if not choices:
        raise RuntimeError(f"No choices returned ({str(data)[:300]})")
    msg = choices[0].get("message") or {}
    parts = []
    if msg.get("content"):
        parts.append({"text": msg["content"]})
    for tc in msg.get("tool_calls") or []:
        fn = tc.get("function") or {}
        args = fn.get("arguments")
        if isinstance(args, str):
            try:
                args = json.loads(args)
            except Exception:
                args = {"_raw": args}
        parts.append({"functionCall": {"name": fn.get("name"), "args": args or {}, "id": tc.get("id")}})
    content = {"role": "model", "parts": parts}
    return content, _calls(content)


def _first_json(text, finish_reason=None):
    text = (text or "").strip()
    if not text:
        raise ValueError(f"Model returned an empty reply (finish_reason={finish_reason})")
    text = re.sub(r"^```(?:json)?\s*", "", text)
    text = re.sub(r"\s*```$", "", text)
    try:
        return json.loads(text)
    except Exception:
        pass
    for opener, closer in (("[", "]"), ("{", "}")):
        i, j = text.find(opener), text.rfind(closer)
        if i != -1 and j > i:
            try:
                return json.loads(text[i:j + 1])
            except Exception:
                continue
    raise ValueError(f"Model did not return JSON (finish_reason={finish_reason}): {text[:300]}")


def ask_json(model, prompt, tries=3):
    """Prompt -> parsed JSON. An empty/truncated reply (finish_reason=length) retries with a doubled output budget."""
    max_tokens = MAX_TOKENS
    err = None
    for attempt in range(tries):
        try:
            data = _post(model, {"messages": [{"role": "user", "content": prompt}], "temperature": 0, "max_tokens": max_tokens})
            ch = (data.get("choices") or [{}])[0]
            text = (ch.get("message") or {}).get("content") or ""
            fr = ch.get("finish_reason")
            try:
                return _first_json(text, fr)
            except ValueError:
                if fr == "length":
                    max_tokens = min(max_tokens * 2, 16000)
                raise
        except (RequestTooLarge, QuotaExhausted):
            raise
        except Exception as e:
            err = e
            time.sleep(1 + attempt)
    raise RuntimeError(f"ask_json failed after {tries} tries: {err}")