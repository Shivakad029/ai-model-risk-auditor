"""Command-line interface.

  python -m app.cli audit --version v1          run an audit, print the scorecard
  python -m app.cli audit --version v2 --report report.html
  python -m app.cli remediate                   fix each failing module, show before/after
  python -m app.cli gate --version v1 --max-risk 10   release gate (exit 1 if it fails)
  python -m app.cli inventory                   list the AI model inventory
  python -m app.cli suite                       show the test-suite summary
  python -m app.cli ping                        check whether the live LLM is reachable
"""

from __future__ import annotations

import argparse
import sys

from . import storage
from .auditor import attack_source as src
from .auditor.remediation import remediate
from .auditor.runner import run_audit
from .gate import evaluate
from .report import write_report

RATING_ICON = {"Low": "🟢", "Guarded": "🟡", "Elevated": "🟠", "Critical": "🔴"}


def _print_scorecard(result) -> None:
    sc = result.scorecard
    icon = RATING_ICON.get(sc.rating, "•")
    print(f"\n{icon} {sc.rating.upper()}   risk score {sc.risk_score}   "
          f"{sc.passed}/{sc.total} passed   {sc.control_failures} control failures")
    print(f"   attack source: {result.pyrit_source}   engine: {result.engine}\n")
    print(f"   {'module':18}{'pass':>7}  {'fail':>5}  {'ctrl':>5}  severity")
    print("   " + "-" * 46)
    for m in sc.modules:
        print(f"   {m.module:18}{m.pass_rate:6}%  {m.failed - m.control_failed:5}  "
              f"{m.control_failed:5}  {m.severity}")


def cmd_audit(a) -> int:
    result = run_audit(bot_version=a.version)
    inv = f"abc-bank-assistant-{a.version}" if a.version in ("v1", "v2") else None
    storage.init_db()
    run_id = storage.record_run(result, inv)
    _print_scorecard(result)
    print(f"\n   stored as run #{run_id}")
    if a.report:
        rems = remediate(run_audit(bot_version="v1")) if a.with_remediation else None
        path = write_report(result, rems, a.report)
        print(f"   report written to {path}")
    return 0


def cmd_remediate(a) -> int:
    baseline = run_audit(bot_version="v1")
    print("Baseline:")
    _print_scorecard(baseline)
    print("\nRemediation (one control per module):\n")
    print(f"   {'module':18}{'control':16}{'before':>8} {'after':>8}  result")
    print("   " + "-" * 56)
    for r in remediate(baseline):
        res = "✅ resolved" if r.resolved else "◑ partial"
        print(f"   {r.module:18}{r.guardrail:16}{r.before_pass_rate:7}% {r.after_pass_rate:7}%  {res}")
    return 0


def cmd_gate(a) -> int:
    result = run_audit(bot_version=a.version)
    gate = evaluate(result, max_risk=a.max_risk)
    status = "PASS ✅" if gate.passed else "FAIL ❌"
    print(f"\nRelease gate: {status}   (risk {gate.risk_score} / threshold {gate.threshold}, rating {gate.rating})")
    for r in gate.reasons:
        print(f"   - {r}")
    return 0 if gate.passed else 1


def cmd_inventory(a) -> int:
    storage.init_db()
    print(f"{'id':32}{'owner':16}{'tier':8}{'status':10}{'rating':10}risk")
    print("-" * 86)
    for row in storage.list_inventory():
        print(f"{row['id']:32}{row['owner'] or '-':16}{row['risk_tier'] or '-':8}"
              f"{row['status']:10}{str(row['last_rating'] or '-'):10}{row['last_risk_score'] if row['last_risk_score'] is not None else '-'}")
    return 0


def cmd_ping(a) -> int:
    """Prove whether the real LLM is reachable, or whether the app is on the deterministic fallback."""
    from . import llm
    from .config import get_settings

    s = get_settings()
    print("\nConfiguration")
    print("   " + "-" * 50)
    print(f"   endpoint        : {s.azure_openai_endpoint or '(not set)'}")
    print(f"   deployment      : {s.azure_openai_deployment or '(not set)'}")
    print(f"   auth mode       : {s.azure_auth_mode}")
    print(f"   api key set     : {'yes' if s.azure_openai_key else 'no'}")
    print(f"   endpoint style  : {'Foundry v1 (OpenAI client)' if s.is_foundry_v1 else 'classic AzureOpenAI'}")
    print(f"   USE_LLM_TARGET  : {s.use_llm_target}")
    print(f"   USE_LLM_JUDGE   : {s.use_llm_judge}")
    print(f"   llm_available   : {s.llm_available}")

    if not s.llm_available:
        print("\n🔸 LLM NOT configured — the app is running in deterministic mock mode.")
        print("   Fill in AZURE_OPENAI_* in .env and restart to use the live model.\n")
        return 1

    print(f"\n   calling {s.azure_openai_deployment} ...")
    reply = llm.chat([{"role": "user", "content": "Reply with exactly: PONG"}], max_tokens=256)
    if reply is None:
        print("\n❌ LLM call FAILED — the app would fall back to deterministic logic.")
        print("   Check the warning logged above (bad key, wrong endpoint, model name, quota).\n")
        return 1
    if not reply.strip():
        print("\n⚠️  CONNECTED, but the model returned an EMPTY reply.")
        print("   Auth/endpoint are correct (no error), but the token budget was likely")
        print("   consumed by reasoning. This build raises the budget and sets minimal")
        print("   reasoning for gpt-5 models — if you still see this, increase max_tokens.\n")
        return 1

    print(f"\n✅ LLM IS LIVE. Model replied: {reply.strip()!r}")
    if s.use_llm_target or s.use_llm_judge:
        which = []
        if s.use_llm_target:
            which.append("target bot")
        if s.use_llm_judge:
            which.append("hallucination judge")
        print(f"   Audits WILL use the live model for: {', '.join(which)}.\n")
    else:
        print("   NOTE: the connection works, but AUDITOR_USE_LLM_TARGET and")
        print("   AUDITOR_USE_LLM_JUDGE are both false, so audits still run in MOCK mode.")
        print("   Set them true in .env and restart to attack the live model.\n")
    return 0


def cmd_suite(a) -> int:
    s = src.suite_summary(src.build_suite())
    print(f"Attack source: {s['pyrit_source']}")
    print(f"Total test cases: {s['total']}")
    for mod, n in s["by_module"].items():
        print(f"   {mod:18}{n}")
    return 0


def main(argv=None) -> int:
    p = argparse.ArgumentParser(prog="auditor", description="AI Model Risk Auditor — AI model risk auditor")
    sub = p.add_subparsers(dest="cmd", required=True)

    a = sub.add_parser("audit", help="run an audit")
    a.add_argument("--version", default="v1", help="v1 (ungoverned), v2 (governed), or a label")
    a.add_argument("--report", help="write an HTML validation report to this path")
    a.add_argument("--with-remediation", action="store_true", help="include remediation in the report")
    a.set_defaults(func=cmd_audit)

    r = sub.add_parser("remediate", help="auto-remediate each failing module")
    r.set_defaults(func=cmd_remediate)

    g = sub.add_parser("gate", help="release gate (exit 1 on fail)")
    g.add_argument("--version", default="v1")
    g.add_argument("--max-risk", type=float, default=None)
    g.set_defaults(func=cmd_gate)

    sub.add_parser("inventory", help="list the AI model inventory").set_defaults(func=cmd_inventory)
    sub.add_parser("suite", help="show the test-suite summary").set_defaults(func=cmd_suite)
    sub.add_parser("ping", help="check whether the live LLM is reachable (one real call)").set_defaults(func=cmd_ping)

    args = p.parse_args(argv)
    return args.func(args)


if __name__ == "__main__":
    sys.exit(main())
