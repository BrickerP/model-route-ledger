"""Turn an agent actions_log.jsonl into a token trace.

The log records WHAT each routine step did (type, text, URLs) but not token
usage, so tokens are ESTIMATED from real payload sizes:
  * CJK characters count ~1 token each, other text ~4 chars per token;
  * every step re-sends a cached system/routine context (``context_tokens``);
  * per-type fixed reads model what the step had to look at (a thread, a
    notifications page); ``log_check`` steps re-read the whole log so far.
If your runtime records real usage, write the trace JSON directly instead.
"""
import json
import re

CJK = re.compile(r"[\u3000-\u9fff\uff00-\uffef]")

KIND = {
    "like": "ui_action", "follow": "ui_action", "repost": "ui_action", "rate_limit": "ui_action",
    "post_skip": "ui_action", "engagement_deferred": "ui_action", "reply_deleted": "ui_action",
    "reply": "draft_public_reply", "quote": "draft_public_reply", "post": "draft_public_post",
    "lead_scan": "scan_classify", "engagement_round": "summarize_log", "catchup_check": "log_check",
    "morning_brief": "research_brief",
}

# extra tokens the step reads besides its own payload, and fixed output overhead (tool calls / reasoning)
READ = {"ui_action": 300, "draft_public_reply": 3000, "draft_public_post": 6000, "scan_classify": 6000,
        "summarize_log": 2000, "log_check": 0, "research_brief": 25000}
OUT = {"ui_action": 120, "draft_public_reply": 400, "draft_public_post": 800, "scan_classify": 250,
       "summarize_log": 200, "log_check": 200, "research_brief": 3000}


def est_tokens(text: str) -> int:
    cjk = len(CJK.findall(text))
    return cjk + max(0, len(text) - cjk) // 4


def from_actions_log(path: str, day: str, context_tokens: int = 12000, name: str | None = None,
                     log_window: int | None = None) -> dict:
    """log_window: if set, log_check steps re-read only the last N tokens (tail) instead of the whole log."""
    steps = []
    log_tokens = 0
    with open(path, encoding="utf-8") as f:
        for raw in f:
            line = raw.strip()
            if not line:
                continue
            log_tokens += est_tokens(line)
            try:
                d = json.loads(line)
            except json.JSONDecodeError:
                continue
            if not str(d.get("ts", "")).startswith(day):
                continue
            t = d.get("type", "")
            kind = KIND.get(t, "ui_action")
            text = str(d.get("text", "") or d.get("note", ""))
            payload = est_tokens(text)
            if kind == "log_check":
                inp = min(log_tokens, log_window) if log_window else log_tokens  # re-reads the log so far
            else:
                inp = READ[kind] + payload
            out = OUT[kind] + (payload if kind in ("draft_public_reply", "draft_public_post", "summarize_log", "research_brief") else 0)
            steps.append({"ts": d.get("ts"), "routine": d.get("routine", ""), "kind": kind, "label": t,
                          "input_tokens": inp, "cached_tokens": context_tokens, "output_tokens": out})
    return {"name": name or f"actions_log {day}", "source": f"{path} (tokens estimated from payload sizes)",
            "steps": steps}
