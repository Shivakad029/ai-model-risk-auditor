"""Validation report generator: a self-contained HTML model-validation report in the
shape a bank validator expects (scope, tests run, findings with evidence, remediation,
regulatory mapping). Renders with no external assets so it can be saved or printed.
"""

from __future__ import annotations

import html
from datetime import datetime, timezone
from pathlib import Path

from .auditor.regmap import mapping_rows
from .config import get_settings

RATING_COLOR = {"Low": "#1a7f52", "Guarded": "#b07b00", "Elevated": "#c1521f", "Critical": "#b3261e"}


def _esc(x) -> str:
    return html.escape(str(x))


def _bar(pct: float) -> str:
    color = "#1a7f52" if pct >= 90 else "#b07b00" if pct >= 60 else "#b3261e"
    return (f'<div class="bar"><div class="fill" style="width:{pct}%;background:{color}"></div>'
            f'<span>{pct}%</span></div>')


def render_html(result, remediations=None) -> str:
    sc = result.scorecard
    rc = RATING_COLOR.get(sc.rating, "#555")
    now = datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")
    remediations = remediations or []

    mod_rows = "\n".join(
        f"<tr><td><b>{_esc(m.title)}</b><br><span class=sev>{_esc(m.severity)}</span></td>"
        f"<td>{_bar(m.pass_rate)}</td><td>{m.passed}/{m.total}</td>"
        f"<td>{m.failed - m.control_failed}</td>"
        f"<td>{'⚠ '+str(m.control_failed) if m.control_failed else '0'}</td></tr>"
        for m in sc.modules)

    fails = [f for f in result.findings if not f.passed and not f.control]
    fails.sort(key=lambda f: {"critical": 0, "high": 1, "medium": 2, "low": 3}.get(f.severity, 9))
    finding_rows = "\n".join(
        f"<details class=finding><summary><span class='pill {f.severity}'>{_esc(f.severity)}</span> "
        f"<b>{_esc(f.case_id)}</b> — {_esc(f.module)} <span class=method>{_esc(f.method)}</span></summary>"
        f"<p class=rat>{_esc(f.rationale)}</p>"
        f"<div class=evid><div><h5>Attack ({_esc(f.technique)})</h5><pre>{_esc(f.attack[:1500])}</pre></div>"
        f"<div><h5>Bot response</h5><pre>{_esc(f.response[:1500])}</pre></div></div></details>"
        for f in fails) or "<p class=none>No failing findings. ✅</p>"

    rem_rows = "\n".join(
        f"<tr><td>{_esc(r.module)}</td><td><code>{_esc(r.guardrail)}</code><br>{_esc(r.fix)}</td>"
        f"<td>{r.before_pass_rate}% → <b>{r.after_pass_rate}%</b></td>"
        f"<td>{'✅ resolved' if r.resolved else '◑ partial'}</td></tr>"
        for r in remediations) or "<tr><td colspan=4 class=none>Remediation not run.</td></tr>"

    reg_by_mod: dict[str, list[dict]] = {}
    for row in mapping_rows():
        reg_by_mod.setdefault(row["module"], []).append(row)
    reg_rows = "\n".join(
        f"<tr><td>{_esc(mod)}</td><td>{'<br>'.join(_esc(r['framework']) + ': ' + _esc(r['control']) for r in rows)}</td></tr>"
        for mod, rows in reg_by_mod.items())

    return f"""<!doctype html><html lang=en><head><meta charset=utf-8>
<meta name=viewport content="width=device-width,initial-scale=1">
<title>AI Model Validation Report — {_esc(result.bot_version)}</title>
<style>
:root{{--ink:#1a1a1a;--muted:#666;--line:#e3e3dd;--bg:#faf9f6}}
*{{box-sizing:border-box}}
body{{font:15px/1.55 -apple-system,Segoe UI,Roboto,Helvetica,Arial,sans-serif;color:var(--ink);
background:var(--bg);margin:0;padding:32px;max-width:960px;margin:auto}}
h1{{font-size:24px;margin:0 0 4px}}h2{{font-size:18px;margin:32px 0 10px;border-bottom:2px solid var(--line);padding-bottom:4px}}
.sub{{color:var(--muted);margin:0 0 20px}}
.ratecard{{display:flex;gap:16px;align-items:center;padding:18px 22px;border-radius:12px;
background:#fff;border:1px solid var(--line);margin:18px 0}}
.rating{{font-size:30px;font-weight:700;color:{rc}}}
.score{{font-size:30px;font-weight:700}}
.kpis{{display:flex;gap:28px;margin-left:auto;text-align:center}}
.kpis div span{{display:block;font-size:22px;font-weight:700}}
.kpis div small{{color:var(--muted)}}
table{{width:100%;border-collapse:collapse;background:#fff;border:1px solid var(--line);border-radius:8px;overflow:hidden}}
th,td{{text-align:left;padding:9px 12px;border-bottom:1px solid var(--line);vertical-align:top}}
th{{background:#f1f0ea;font-size:13px}}
.sev{{font-size:12px;color:var(--muted);text-transform:uppercase}}
.bar{{position:relative;background:#eee;border-radius:5px;height:18px;width:160px}}
.bar .fill{{height:100%;border-radius:5px}}
.bar span{{position:absolute;right:6px;top:0;font-size:12px;line-height:18px}}
.pill{{font-size:11px;padding:2px 7px;border-radius:10px;color:#fff;text-transform:uppercase}}
.pill.critical,.pill.high{{background:#b3261e}}.pill.medium{{background:#b07b00}}.pill.low{{background:#777}}
.method{{font-size:11px;color:var(--muted);border:1px solid var(--line);padding:1px 6px;border-radius:8px;margin-left:6px}}
details.finding{{background:#fff;border:1px solid var(--line);border-radius:8px;margin:7px 0;padding:8px 12px}}
summary{{cursor:pointer}}.rat{{color:#b3261e;margin:8px 0}}
.evid{{display:grid;grid-template-columns:1fr 1fr;gap:12px}}
.evid h5{{margin:4px 0;color:var(--muted);font-size:12px}}
pre{{background:#f6f5ef;padding:8px;border-radius:6px;white-space:pre-wrap;word-break:break-word;font-size:12px;max-height:260px;overflow:auto}}
code{{background:#f1f0ea;padding:1px 5px;border-radius:4px;font-size:13px}}
.none{{color:var(--muted)}}.prov{{font-size:12px;color:var(--muted);margin-top:40px;border-top:1px solid var(--line);padding-top:10px}}
@media(max-width:640px){{.evid{{grid-template-columns:1fr}}.kpis{{flex-wrap:wrap;gap:14px}}}}
</style></head><body>
<h1>AI Model Validation Report</h1>
<p class=sub>AI Model Risk Auditor · target <b>{_esc(result.bot_version)}</b> · guardrails: {_esc(', '.join(result.guardrails) or 'none')} · {now}</p>

<div class=ratecard>
  <div><div class=rating>{_esc(sc.rating)}</div><small>overall rating</small></div>
  <div><div class=score>{sc.risk_score}</div><small>weighted risk score</small></div>
  <div class=kpis>
    <div><span>{sc.total}</span><small>tests</small></div>
    <div><span style=color:#1a7f52>{sc.passed}</span><small>passed</small></div>
    <div><span style=color:#b3261e>{sc.failed}</span><small>failed</small></div>
    <div><span>{sc.control_failures}</span><small>control fails</small></div>
  </div>
</div>

<h2>1. Scope &amp; method</h2>
<p>Automated red-team of the target assistant across six risk modules. Attack phrasings sourced from
<b>{_esc(result.pyrit_source)}</b>; banking objectives and judging added by this tool. All data is synthetic.
Judging is deterministic for leaks (planted canaries), unauthorized actions (tool execution) and fair lending
(paired-prompt comparison); hallucination uses an LLM judge when configured, else a grounding check. Engine:
<code>{_esc(result.engine)}</code>. Duration: {result.duration_s}s.</p>

<h2>2. Scorecard by module</h2>
<table><tr><th>Module</th><th>Pass rate</th><th>Passed</th><th>Real failures</th><th>Control fails</th></tr>
{mod_rows}</table>

<h2>3. Findings (failures, most severe first)</h2>
{finding_rows}

<h2>4. Remediation</h2>
<table><tr><th>Module</th><th>Recommended control</th><th>Pass rate</th><th>Result</th></tr>
{rem_rows}</table>

<h2>5. Regulatory mapping</h2>
<p class=sub>Maps evidence to the controls validators and auditors use. This is not a compliance attestation.</p>
<table><tr><th>Module</th><th>Framework control</th></tr>
{reg_rows}</table>

<p class=prov>Generated by AI Model Risk Auditor. Attack source: {_esc(result.pyrit_source)} (Microsoft PyRIT, MIT).
Synthetic data only — not for use against production systems.</p>
</body></html>"""


def write_report(result, remediations=None, path: str | Path | None = None) -> Path:
    out = Path(path) if path else get_settings().output_dir / f"report_{result.bot_version}.html"
    out.write_text(render_html(result, remediations), encoding="utf-8")
    return out
