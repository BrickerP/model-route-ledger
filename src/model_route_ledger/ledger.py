"""Replay an agent trace twice (baseline vs routed) and build a cost ledger."""
import json
from .pricing import cost, DEFAULT_HAIKU_TOKEN_INFLATION, HAIKU_CLIFF
from .router import route, RANK


def load_trace(path: str) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _tokens(step, model, infl):
    m = infl if model.startswith("haiku") else 1.0
    return (int(step["input_tokens"] * m), int(step.get("cached_tokens", 0) * m), int(step["output_tokens"] * m))


def build(trace: dict, policy, baseline: str = "sonnet-5.5", haiku_inflation: float = DEFAULT_HAIKU_TOKEN_INFLATION,
          min_savings: float = 0.5) -> dict:
    rows = []
    base_total = routed_total = 0.0
    cliff_hits = 0
    downgraded_protected = 0
    for i, s in enumerate(trace["steps"], 1):
        bi, bc, bo = _tokens(s, baseline, haiku_inflation)
        b_usd, _ = cost(baseline, bi, bc, bo)
        model, reason = route(policy, s, haiku_inflation)
        ri, rc, ro = _tokens(s, model, haiku_inflation)
        r_usd, key = cost(model, ri, rc, ro)
        if key.endswith(">100k"):
            cliff_hits += 1
        if s.get("kind") in policy.never_downgrade and RANK[model] < RANK[policy.default]:
            downgraded_protected += 1
        base_total += b_usd
        routed_total += r_usd
        rows.append({"i": i, "routine": s.get("routine", ""), "kind": s.get("kind", ""), "label": s.get("label", ""),
                     "input": s["input_tokens"], "cached": s.get("cached_tokens", 0), "output": s["output_tokens"],
                     "model": model, "price_key": key, "reason": reason,
                     "baseline_usd": b_usd, "routed_usd": r_usd})
    # headroom: biggest Haiku prompt vs the cliff, and how fast re-read logs grow
    haiku_prompts = [(r["input"] + r["cached"]) * haiku_inflation for r in rows if r["model"].startswith("haiku")]
    max_haiku_prompt = int(max(haiku_prompts)) if haiku_prompts else 0
    growth = _log_growth(trace["steps"], haiku_inflation)
    days_to_cliff = None
    if growth and growth > 0:
        days_to_cliff = max(0.0, (HAIKU_CLIFF - max_haiku_prompt) / growth)
    savings = 1 - routed_total / base_total if base_total else 0.0
    by_model = {}
    for r in rows:
        agg = by_model.setdefault(r["model"], {"steps": 0, "usd": 0.0})
        agg["steps"] += 1
        agg["usd"] += r["routed_usd"]
    gates = [
        {"name": f"savings >= {min_savings:.0%}", "ok": savings >= min_savings, "value": f"{savings:.1%}"},
        {"name": "protected steps never downgraded", "ok": downgraded_protected == 0, "value": str(downgraded_protected)},
        {"name": f"no Haiku request over {HAIKU_CLIFF:,}-token price cliff", "ok": cliff_hits == 0, "value": str(cliff_hits)},
    ]
    return {"trace": trace.get("name", "trace"), "source": trace.get("source", ""), "baseline": baseline,
            "haiku_inflation": haiku_inflation, "steps": len(rows), "rows": rows,
            "baseline_usd": base_total, "routed_usd": routed_total, "savings": savings,
            "by_model": by_model, "gates": gates, "max_haiku_prompt": max_haiku_prompt,
            "log_growth_per_day": growth, "days_to_cliff": days_to_cliff, "pass": all(g["ok"] for g in gates)}


def _log_growth(steps, infl):
    """Haiku-token growth per day of steps that re-read a growing log (kind=log_check)."""
    from datetime import datetime
    pts = []
    for s in steps:
        if s.get("kind") != "log_check" or not s.get("ts"):
            continue
        ts = s["ts"]
        if len(ts) >= 5 and (ts[-5] in "+-") and ts[-3] != ":":
            ts = ts[:-2] + ":" + ts[-2:]
        try:
            pts.append((datetime.fromisoformat(ts).timestamp(), s["input_tokens"] * infl))
        except ValueError:
            continue
    if len(pts) < 2:
        return None
    pts.sort()
    dt = (pts[-1][0] - pts[0][0]) / 86400
    return (pts[-1][1] - pts[0][1]) / dt if dt > 0 else None


def summary_text(led: dict) -> str:
    lines = [f"RESULT: {'PASS' if led['pass'] else 'FAIL'}",
             f"  trace={led['trace']}  steps={led['steps']}  baseline=all-{led['baseline']}",
             f"  baseline=${led['baseline_usd']:.4f}  routed=${led['routed_usd']:.4f}  savings={led['savings']:.1%}"]
    mix = "  ".join(f"{m}:{v['steps']}" for m, v in sorted(led["by_model"].items()))
    lines.append(f"  route mix  {mix}")
    if led.get("max_haiku_prompt"):
        lines.append(f"  biggest Haiku prompt {led['max_haiku_prompt']:,} tok / cliff 100,000")
    if led.get("days_to_cliff") is not None:
        lines.append(f"  re-read log grows ~{led['log_growth_per_day']:,.0f} tok/day -> crosses cliff in ~{led['days_to_cliff']:.1f} days")
    for g in led["gates"]:
        lines.append(f"  [{'ok' if g['ok'] else 'XX'}] {g['name']} ({g['value']})")
    return "\n".join(lines)
