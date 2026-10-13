import argparse
import json
import os
import sys

from .ingest import from_actions_log
from .ledger import build, load_trace, summary_text
from .pricing import DEFAULT_HAIKU_TOKEN_INFLATION
from .report import render
from .router import Policy

HERE = os.path.dirname(os.path.abspath(__file__))
ROOT = os.path.abspath(os.path.join(HERE, "..", ".."))


def _emit(led, report, as_json):
    if report:
        os.makedirs(os.path.dirname(os.path.abspath(report)), exist_ok=True)
        with open(report, "w", encoding="utf-8") as f:
            f.write(render(led))
    if as_json:
        print(json.dumps({k: v for k, v in led.items() if k != "rows"}, indent=2))
    else:
        print(summary_text(led))
        if report:
            print(f"  report -> {report}")
    return 0 if led["pass"] else 1


def main(argv=None):
    ap = argparse.ArgumentParser(prog="model-route-ledger",
                                 description="Replay an agent trace: all-Sonnet vs routed (Haiku/Sonnet/Opus) cost ledger + PASS/FAIL gates.")
    sub = ap.add_subparsers(dest="cmd", required=True)

    def common(p):
        p.add_argument("--policy", default=os.path.join(ROOT, "fixtures", "policy.json"))
        p.add_argument("--baseline", default="sonnet-5.5", choices=["haiku-5.5", "sonnet-5.5", "opus-5.5"])
        p.add_argument("--haiku-inflation", type=float, default=DEFAULT_HAIKU_TOKEN_INFLATION)
        p.add_argument("--min-savings", type=float, default=0.5)
        p.add_argument("--report", default=None)
        p.add_argument("--json", action="store_true")

    d = sub.add_parser("demo", help="replay our own agent's day (bundled fixture)")
    common(d)
    r = sub.add_parser("run", help="replay a trace JSON")
    r.add_argument("trace")
    common(r)
    i = sub.add_parser("from-log", help="build a trace from an agent actions_log.jsonl, then replay it")
    i.add_argument("log")
    i.add_argument("--day", required=True, help="YYYY-MM-DD prefix of ts to include")
    i.add_argument("--context-tokens", type=int, default=12000)
    i.add_argument("--log-window", type=int, default=None, help="tail: re-read at most N log tokens per check")
    i.add_argument("--save-trace", default=None)
    common(i)

    a = ap.parse_args(argv)
    policy = Policy.load(a.policy)
    if a.cmd == "demo":
        trace = load_trace(os.path.join(ROOT, "fixtures", "our_agent_day_2026-10-13.json"))
        a.report = a.report or os.path.join(ROOT, "docs", "demo-report.html")
    elif a.cmd == "run":
        trace = load_trace(a.trace)
    else:
        trace = from_actions_log(a.log, a.day, a.context_tokens, log_window=a.log_window)
        if a.save_trace:
            with open(a.save_trace, "w", encoding="utf-8") as f:
                json.dump(trace, f, ensure_ascii=False, indent=1)
    led = build(trace, policy, a.baseline, a.haiku_inflation, a.min_savings)
    return _emit(led, a.report, a.json)


if __name__ == "__main__":
    sys.exit(main())
