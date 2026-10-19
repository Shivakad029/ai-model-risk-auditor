# 🛡️ AI Model Risk Auditor

**An agentic AI red-team and model risk auditor for banking AI.**
An internal AI model-risk tool authored by Shiva.

It attacks an AI assistant across six risk types, judges each
response with evidence, scores the overall risk, proposes and *proves* a fix for
each failing area, maps every finding to the controls bank validators already
use (SR 11-7, NIST AI RMF, OWASP LLM Top 10, ECOA/Reg B), and enforces a
pass/fail **release gate** in CI.

> **Attack source:** adversarial prompt phrasings come from **Microsoft PyRIT**
> (MIT-licensed). This project adds the banking test *objectives*, the judging,
> scoring, remediation, reporting, release gate and dashboard. **All data is
> synthetic — never point this at a production system.**

Everything runs **offline in deterministic mock mode** with no Azure account and
no network. Add Azure credentials to attack a real Azure OpenAI deployment and
use Prompt Shields + an LLM judge.

---

## The six risk types

| Module | Risk | Deterministic proof of a failure |
|---|---|---|
| **Prompt Injection** | Prompt injection / jailbreaks (LLM01) | planted canary / system prompt appears in reply |
| **Document Injection** | Indirect injection via documents | instruction hidden in an uploaded doc is obeyed |
| **Data Leakage** | Data leakage (LLM02) | a planted canary account or another customer's data leaks |
| **Hallucination** | Hallucination (LLM09) | invents a policy that exists in no document |
| **Fair Lending** | Bias / fair lending (ECOA) | two prompts differing only by zip/name/age get different loan amounts |
| **Excessive Agency** | Excessive agency (LLM06) | a money-moving tool executes without verification |

Serious verdicts are **deterministic** (canary strings, tool execution,
paired-prompt comparison). Only the "did it invent a policy?" check uses an LLM
judge, and only when Azure is configured; otherwise it falls back to a grounding
check. The method is recorded on every finding.

---

## Open in Visual Studio

Open `AIModelRiskAuditor.sln` in Visual Studio 2022 (Python workload). Full
step-by-step setup, run and test instructions are in
[`docs/VISUAL_STUDIO.md`](docs/VISUAL_STUDIO.md). AI usage & governance:
[`docs/AI_USAGE.md`](docs/AI_USAGE.md). Azure setup (mock → real):
[`docs/AZURE_SETUP.md`](docs/AZURE_SETUP.md). Code walkthrough (every file in `app/`):
[`docs/CODE_WALKTHROUGH.md`](docs/CODE_WALKTHROUGH.md). Add new guardrails (how it breaks, how to extend):
[`docs/ADDING_GUARDRAILS.md`](docs/ADDING_GUARDRAILS.md). Architecture diagram:
[`docs/architecture.html`](docs/architecture.html) / [`docs/architecture.md`](docs/architecture.md).

## Quick start

```bash
pip install -r requirements.txt

# Run the before/after audits from the command line
python -m app.cli audit --version v1      # 🔴 Critical
python -m app.cli audit --version v2      # 🟢 Low

# Auto-remediate: fix each failing module one control at a time, prove it worked
python -m app.cli remediate

# The release gate (exits non-zero when it fails — this is what CI runs)
python -m app.cli gate --version v1       # FAIL
python -m app.cli gate --version v2       # PASS

# Write an HTML validation report
python -m app.cli audit --version v1 --report report.html --with-remediation
```

### Live dashboard

```bash
./run.sh            # or: uvicorn app.api:app --reload
# open http://localhost:8000
```

Click **Audit v1** to watch the risk meter climb to *Critical* in real time,
**Audit v2** to watch it drop to *Low*, and **Auto-remediate** to see each
control take its module from red to green. Every run links to its validation
report and shows the release-gate decision.

---

## The demo flow (for the pitch)

1. **Audit v1** — dashboard fills with red, rating hits **Critical**, the release
   gate shows **FAIL** with specific reasons.
2. Open one **Data Leakage** finding — the planted canary is right there in the reply.
3. **Fair Lending** panel — two identical loan questions, different zip codes, different
   pre-qualified amounts.
4. **Auto-remediate** — each module goes red → green as its control is applied
   and re-tested.
5. **Audit v2** — rating **Low**, gate **PASS**, and the GitLab pipeline blocks
   any build that regresses.

---

## Switching to real Azure (optional)

```bash
cp .env.example .env     # then fill in your values
# AZURE_OPENAI_* ............ attack a real deployment / use the LLM judge
# AZURE_CONTENT_SAFETY_* .... use Prompt Shields for the prompt_shield guardrail
# AUDITOR_USE_LLM_TARGET=true
# AUDITOR_USE_LLM_JUDGE=true
```

Nothing else changes — the same attacks, judging and gate run against the live
model. If the content filter blocks an attack prompt or the endpoint is slow, the
affected call falls back to deterministic logic so a demo never stalls.

---

## Architecture

```
PyRIT templates ─┐
                 ├─ attack_source → test suite → runner → target bot (v1/v2, guardrails)
objectives.yaml ─┘                                   │
                                                     ▼
                                     judge (canary / tool / pair / LLM)
                                                     │
                            ┌────────────────────────┼───────────────────────┐
                            ▼                         ▼                        ▼
                        scoring (risk,           remediation             regmap (SR 11-7,
                        rating)                  (prove each fix)        NIST, OWASP, ECOA)
                            │                         │                        │
                            └──────────── report (HTML) · gate (CI) · storage (inventory + runs)
                                                     │
                                          api (FastAPI + SSE) → dashboard
```

| Path | What it is |
|---|---|
| `app/target_bot/` | the ABC Bank Assistant (v1 ungoverned / v2 governed) and its guardrails |
| `app/auditor/attack_source.py` | loads PyRIT phrasings (installed pkg → vendored), builds the suite |
| `app/auditor/judge.py` | deterministic + LLM judging with evidence |
| `app/auditor/scoring.py` | weighted risk score and the rating |
| `app/auditor/remediation.py` | one-control-per-module fix-and-retest |
| `app/auditor/regmap.py` | finding → regulatory-control mapping |
| `app/report.py` | self-contained HTML validation report |
| `app/gate.py` / `app/cli.py` | the release gate and CLI |
| `app/api.py` + `app/static/dashboard.html` | API, SSE streaming, live dashboard |
| `app/storage.py` | SQLite AI inventory ("Model Inventory") + run history |
| `attacks/objectives.yaml` | the banking test objectives (this project's) |
| `attacks/pyrit_vendored/` | MIT-licensed PyRIT templates + attribution |
| `tests/` | 14 offline end-to-end tests |
| `.gitlab-ci.yml` | unit tests + the AI release gate |

---

## Tests & CI

```bash
python -m pytest tests/ -q      # 14 tests, fully offline
```

`.gitlab-ci.yml` runs the tests, writes the validation report as a pipeline
artifact, and runs the release gate — point `TARGET_VERSION` at the model under
review.

---

## Scope & safety

This is a hackathon prototype on **synthetic data**. The bot, customers and
policies are invented. It demonstrates the method; a production deployment would
run against non-production models only, behind access controls and logging, with
the scorecard thresholds owned by model risk. Mapping findings to frameworks is
**not** a compliance attestation.

Attack content: Microsoft PyRIT, MIT License — see `attacks/pyrit_vendored/`.
