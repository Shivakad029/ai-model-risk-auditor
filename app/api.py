"""FastAPI backend + live dashboard.

Endpoints
  GET  /                      the dashboard (static HTML page)
  GET  /api/health           status + which attack source / engine is active
  GET  /api/suite            the test-suite summary (counts, PyRIT source)
  GET  /api/inventory        the AI model inventory ("Model Inventory")
  GET  /api/runs             recent audit runs
  GET  /api/report/{run}     the HTML validation report for a stored run
  GET  /api/audit/stream     Server-Sent Events: run an audit and stream each case
  POST /api/audit            run an audit synchronously, return the full result
  POST /api/remediate        run auto-remediation against a fresh v1 baseline
"""

from __future__ import annotations

import json
from pathlib import Path

from fastapi import FastAPI, Query
from fastapi.responses import HTMLResponse, JSONResponse, StreamingResponse

from . import storage
from .auditor import attack_source as src
from .auditor.remediation import remediate
from .auditor.runner import run_audit
from .config import ROOT, get_settings
from .gate import evaluate
from .report import render_html
from .target_bot.bot import Guardrails

app = FastAPI(title="AI Model Risk Auditor", version="1.0.0")
DASHBOARD = ROOT / "app" / "static" / "dashboard.html"


@app.on_event("startup")
def _startup() -> None:
    storage.init_db()


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return DASHBOARD.read_text(encoding="utf-8")


@app.get("/api/health")
def health() -> dict:
    s = get_settings()
    return {"status": "ok", "pyrit_source": src.pyrit_source(),
            "engine": "llm" if (s.use_llm_target and s.llm_available) else "mock",
            "llm_judge": s.use_llm_judge and s.llm_available,
            "content_safety": s.content_safety_available, "gate_max_risk": s.gate_max_risk}


@app.get("/api/suite")
def suite() -> dict:
    return src.suite_summary(src.build_suite())


@app.get("/api/inventory")
def inventory() -> list[dict]:
    return storage.list_inventory()


@app.get("/api/runs")
def runs(limit: int = 50) -> list[dict]:
    return storage.list_runs(limit)


@app.get("/api/report/{run_id}", response_class=HTMLResponse)
def report(run_id: int) -> str:
    data = storage.get_run(run_id)
    if not data:
        return "<h1>Run not found</h1>"
    return _render_from_dict(data)


def _inventory_id(bot_version: str) -> str:
    return f"abc-bank-assistant-{bot_version}" if bot_version in ("v1", "v2") else ""


@app.post("/api/audit")
def audit(bot_version: str = Query("v1")) -> JSONResponse:
    result = run_audit(bot_version=bot_version)
    run_id = storage.record_run(result, _inventory_id(bot_version) or None)
    gate = evaluate(result)
    payload = result.to_dict()
    payload["run_id"] = run_id
    payload["gate"] = gate.to_dict()
    return JSONResponse(payload)


@app.post("/api/remediate")
def remediate_endpoint() -> JSONResponse:
    baseline = run_audit(bot_version="v1")
    rems = remediate(baseline)
    return JSONResponse({"baseline": baseline.scorecard.to_dict(),
                         "remediations": [r.to_dict() for r in rems]})


@app.get("/api/audit/stream")
def audit_stream(bot_version: str = Query("v1")) -> StreamingResponse:
    """Run an audit and stream Server-Sent Events as each case is judged."""
    def gen():
        events: list[dict] = []

        def cb(ev: dict) -> None:
            events.append(ev)

        # run_audit calls cb synchronously; we drain after, but to stream live we
        # interleave by running the generator form.
        from .auditor.runner import _run_case, _module_titles
        from .auditor.scoring import score
        guard = Guardrails.all() if bot_version == "v2" else Guardrails.none()
        cases = src.build_suite()
        titles = _module_titles()
        from .target_bot.bot import ABCBankBot
        bot = ABCBankBot(guardrails=guard)
        yield _sse({"event": "start", "bot_version": bot_version, "total": len(cases),
                    "guardrails": guard.enabled(), "engine": bot.engine, "pyrit_source": src.pyrit_source()})
        findings = []
        for i, case in enumerate(cases, 1):
            f = _run_case(bot, case)
            findings.append(f)
            yield _sse({"event": "case", "i": i, "total": len(cases), "module": case.module,
                        "case_id": case.id, "passed": f.passed, "control": f.control,
                        "method": f.method, "severity": case.severity, "technique": case.technique})
        sc = score(findings, titles)
        from .auditor.runner import AuditResult
        result = AuditResult(bot_version=bot_version, guardrails=guard.enabled(), engine=bot.engine,
                             pyrit_source=src.pyrit_source(), duration_s=0.0, scorecard=sc, findings=findings)
        run_id = storage.record_run(result, _inventory_id(bot_version) or None)
        gate = evaluate(result)
        yield _sse({"event": "done", "run_id": run_id, "scorecard": sc.to_dict(), "gate": gate.to_dict()})

    return StreamingResponse(gen(), media_type="text/event-stream",
                             headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"})


def _sse(obj: dict) -> str:
    return f"data: {json.dumps(obj)}\n\n"


def _render_from_dict(data: dict) -> str:
    """Reconstruct lightweight objects from stored JSON so report.render_html works."""
    from types import SimpleNamespace

    def ns(d):
        return SimpleNamespace(**d)

    sc = data["scorecard"]
    scorecard = SimpleNamespace(**{k: v for k, v in sc.items() if k != "modules"},
                                modules=[ns(m) for m in sc["modules"]])
    findings = [ns(f) for f in data["findings"]]
    result = SimpleNamespace(bot_version=data["bot_version"], guardrails=data["guardrails"],
                             engine=data["engine"], pyrit_source=data["pyrit_source"],
                             duration_s=data["duration_s"], scorecard=scorecard, findings=findings)
    return render_html(result)
