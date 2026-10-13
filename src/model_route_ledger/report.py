"""Self-contained HTML cost-ledger report (no JS, no network)."""
import html

COLORS = {"haiku-5.5": "#2f9e44", "sonnet-5.5": "#1c7ed6", "opus-5.5": "#862e9c"}


def _bar(label, usd, maxv, color, w=560):
    bw = max(2, int(w * usd / maxv)) if maxv else 2
    return (f'<div class="bar"><span class="bl">{html.escape(label)}</span>'
            f'<span class="bv" style="width:{bw}px;background:{color}"></span>'
            f'<span class="bn">${usd:.4f}</span></div>')


def render(led: dict) -> str:
    ok = led["pass"]
    maxv = max(led["baseline_usd"], led["routed_usd"])
    rows = "".join(
        f'<tr><td>{r["i"]}</td><td>{html.escape(r["routine"])}</td><td>{html.escape(r["label"])}</td>'
        f'<td>{html.escape(r["kind"])}</td><td class="n">{r["input"] + r["cached"]:,}</td><td class="n">{r["output"]:,}</td>'
        f'<td><b style="color:{COLORS.get(r["model"], "#333")}">{r["model"]}</b>'
        f'{" ⚠ cliff" if r["price_key"].endswith(">100k") else ""}</td>'
        f'<td class="n">${r["baseline_usd"]:.4f}</td><td class="n">${r["routed_usd"]:.4f}</td></tr>'
        for r in led["rows"])
    gates = "".join(f'<li class="{"ok" if g["ok"] else "bad"}">{"✔" if g["ok"] else "✘"} {html.escape(g["name"])} '
                    f'<b>{html.escape(g["value"])}</b></li>' for g in led["gates"])
    mix = "".join(_bar(f'{m} · {v["steps"]} steps', v["usd"], maxv, COLORS.get(m, "#555"))
                  for m, v in sorted(led["by_model"].items()))
    head = ""
    if led.get("days_to_cliff") is not None:
        head = (f'<p class="warn">Biggest Haiku prompt: <b>{led["max_haiku_prompt"]:,}</b> / 100,000 tokens. '
                f'The re-read log grows ~{led["log_growth_per_day"]:,.0f} tokens/day, so it crosses Haiku 5.5\'s price cliff '
                f'(5× per token) in about <b>{led["days_to_cliff"]:.1f} days</b> unless you tail it.</p>')
    elif led.get("max_haiku_prompt"):
        head = f'<p class="warn">Biggest Haiku prompt: <b>{led["max_haiku_prompt"]:,}</b> / 100,000 tokens.</p>'
    return f"""<!doctype html><html><head><meta charset="utf-8"><title>model-route-ledger · {html.escape(led['trace'])}</title>
<style>
body{{font:15px/1.45 -apple-system,Segoe UI,Helvetica,Arial,sans-serif;margin:0;background:#f6f5f1;color:#1d1d1f}}
.wrap{{max-width:980px;margin:0 auto;padding:28px 32px}}
h1{{font-size:22px;margin:0 0 4px}} .sub{{color:#666;margin:0 0 18px;font-size:13px}}
.cards{{display:flex;gap:14px;margin:0 0 18px}} .card{{flex:1;background:#fff;border-radius:12px;padding:14px 16px;box-shadow:0 1px 2px #0001}}
.card .k{{font-size:12px;color:#777;text-transform:uppercase;letter-spacing:.04em}} .card .v{{font-size:30px;font-weight:700}}
.pass{{color:#2f9e44}} .fail{{color:#e03131}}
.bar{{display:flex;align-items:center;gap:10px;margin:6px 0}} .bl{{width:210px;font-size:13px}} .bv{{height:18px;border-radius:4px;display:inline-block}} .bn{{font-variant-numeric:tabular-nums;font-size:13px}}
ul.g{{list-style:none;padding:0;margin:8px 0 14px}} ul.g li{{margin:4px 0}} li.ok{{color:#2b8a3e}} li.bad{{color:#c92a2a}}
.warn{{background:#fff4e6;border-left:4px solid #f08c00;padding:8px 12px;border-radius:6px;font-size:14px}}
table{{border-collapse:collapse;width:100%;font-size:12px;background:#fff}} td,th{{padding:4px 6px;border-bottom:1px solid #eee;text-align:left}} td.n{{text-align:right;font-variant-numeric:tabular-nums}}
.foot{{color:#888;font-size:12px;margin-top:14px}}
</style></head><body><div class="wrap">
<h1>model-route-ledger · {html.escape(led['trace'])}</h1>
<p class="sub">{html.escape(led['source'])} · baseline: every step on {led['baseline']} · Haiku token inflation ×{led['haiku_inflation']:.2f} · Claude 5.5 list prices</p>
<div class="cards">
<div class="card"><div class="k">Result</div><div class="v {'pass' if ok else 'fail'}">{'PASS' if ok else 'FAIL'}</div></div>
<div class="card"><div class="k">All-{led['baseline']}</div><div class="v">${led['baseline_usd']:.3f}</div></div>
<div class="card"><div class="k">Routed</div><div class="v">${led['routed_usd']:.3f}</div></div>
<div class="card"><div class="k">Savings</div><div class="v pass">{led['savings']:.0%}</div></div>
</div>
{_bar('baseline · all ' + led['baseline'], led['baseline_usd'], maxv, '#adb5bd')}
{mix}
<ul class="g">{gates}</ul>
{head}
<h3>Per-step ledger ({led['steps']} steps)</h3>
<table><tr><th>#</th><th>routine</th><th>step</th><th>kind</th><th>prompt tok</th><th>out tok</th><th>routed to</th><th>baseline</th><th>routed</th></tr>{rows}</table>
<p class="foot">Built with model-route-ledger by Yupeng Lu · AI agent &amp; backend engineer · https://brickerp.github.io/hire/</p>
</div></body></html>"""
