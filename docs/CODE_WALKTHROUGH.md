# Code walkthrough — the `app/` package

This is a detailed, file-by-file explanation of the `app/` package, which is the
engine of the auditor. The two sibling folders `attacks/` and `data/` are inputs
(the tests and the fake bank); `app/` is the code that runs the tests against the
bank and turns the results into a scorecard, a report, and a CI gate.

## Package layout

```
app/
  __init__.py            package marker + version
  config.py              settings & .env loading (mock vs Azure)
  llm.py                 Azure OpenAI + Content Safety wrappers (optional)
  target_bot/
    __init__.py
    bot.py               the ABC Bank Assistant (the thing under test)
    guards.py            guardrail building blocks (canaries, detectors, filters)
  auditor/
    __init__.py
    attack_source.py     PyRIT phrasings + objectives -> the test suite
    judge.py             PASS/FAIL per case, with evidence
    scoring.py           risk score + rating
    remediation.py       one-control-per-module fix-and-retest
    regmap.py            findings -> SR 11-7 / NIST / OWASP / ECOA
    runner.py            drive the suite, collect findings, score the run
  report.py              self-contained HTML validation report
  gate.py                the CI release gate (pass/fail)
  storage.py             SQLite inventory + run history
  cli.py                 command-line interface
  api.py                 FastAPI app + SSE streaming
  static/
    dashboard.html       the live dashboard (single page)
```

Dependency direction: `config` and `llm` are the base; `target_bot` and
`auditor` build on them; `report`, `gate`, `storage` consume audit results;
`cli` and `api` are the two entry points that tie it all together.

---

## Cross-cutting

### `config.py` — one place for all settings
- Loads `.env` with a tiny built-in parser (`_load_dotenv`), so there's no extra
  dependency. Reads it as UTF-8.
- Exposes a frozen `Settings` dataclass via `get_settings()` (cached), with the
  Azure OpenAI and Content Safety values, the feature flags
  (`use_llm_target`, `use_llm_judge`), the output dir, the DB path, and the gate
  threshold.
- Two computed properties decide behavior everywhere else:
  - `llm_available` — true only if all three Azure OpenAI values are present.
  - `content_safety_available` — true only if both Content Safety values are set.
- Defines the project paths (`ROOT`, `DATA_DIR`, `CONFIG_DIR`, `ATTACKS_DIR`).

### `llm.py` — the only place that calls Azure
- `chat(messages, ...)` and `chat_json(...)` call Azure OpenAI. If
  `llm_available` is false, or any error occurs (content filter, network, quota),
  they return `None`. Callers treat `None` as "use the deterministic path."
- `prompt_shield(user_prompt, documents)` calls Azure AI Content Safety's
  Prompt Shields endpoint; returns `{"user_attack": bool, "document_attack":
  bool}` or `None` when not configured.
- The OpenAI SDK is imported lazily inside `chat`, so mock mode needs no SDK
  installed. This isolation is why the whole system runs offline: nothing else
  touches the network.

---

## `target_bot/` — the AI being audited

### `bot.py` — the ABC Bank Assistant
The deliberately weak chatbot the auditor attacks. Key pieces:

- **`SYSTEM_PROMPT`** — the bot's instructions, containing the planted
  system-prompt canary ("staff escalation code is `CANARY-ABC-7F3A`").
- **`PLANTED_BIASED_ZIPS`** — the deliberate fair-lending flaw: v1 credit logic
  treats these fictional zips as "high risk" (a redlining proxy).
- **`Guardrails`** — a dataclass of six booleans (`prompt_shield`,
  `document_scan`, `output_filter`, `grounded_only`, `strip_protected`,
  `tool_authz`). Helpers: `none()` (=v1), `all()` (=v2), `from_value()` (parse a
  list/dict/str), `enabled()` (list the on ones). This is what makes one code
  base behave as v1 or v2 or any single-guardrail variant.
- **`ToolCall`** / **`BotResponse`** — the structured return: the reply text, any
  tool calls (`executed` / `blocked`), and which guardrails fired. The judge
  reads these fields.
- **Knowledge loading** — on import, `POLICIES` and `CUSTOMERS` are read from
  `data/` once; `retrieve_policy()` is a tiny keyword retriever used to answer
  (and to decide when the bot is inventing a policy).
- **`ABCBankBot`** — the bot itself:
  - `__init__` picks the engine: `mock` (default) or `llm` (if
    `use_llm_target` and `llm_available`).
  - `chat(message, history, document, session)` is the entry point. Order:
    1. pre-check guardrails (`prompt_shield` on the turns, `document_scan` on an
       uploaded doc);
    2. produce a reply via `_mock_chat` (regex intent routing) or `_llm_chat`
       (Azure, with a fallback to mock);
    3. post-check (`output_filter` redacts canaries / other customers' accounts).
  - `_mock_chat` routes by intent with regex: reveal-system-prompt, money
    transfer, customer lookup, loan decision, policy question. Each branch
    contains the planted flaw the matching module tests for.
  - `_loan_decision` is where `strip_protected` and the zip bias interact.
  - `_llm_chat` builds a system prompt with the policies + visible customers,
    calls `llm.chat`, and parses a `TOOL transfer_funds ...` line into a
    `ToolCall`; if the model is unavailable it falls back to `_mock_chat`.

### `guards.py` — guardrail building blocks
- **Canary constants** — `PROMPT_CANARY` (`CANARY-ABC-7F3A`) and
  `CUSTOMER_CANARY` (`CANARY-ACCT-1313`), and `CANARIES = [...]`.
- **`detect_injection(text, is_document)`** — the jailbreak detector: regex
  patterns for "ignore previous instructions", "admin mode", "reveal the system
  prompt", base64-decoded payloads, etc., backed by Prompt Shields when
  available. Used by the `prompt_shield` and `document_scan` guardrails.
- **`decode_base64_chunks`** — pulls hidden text out of base64 (a common
  jailbreak trick) so both the detector and the naive mock bot "see" it.
- **`filter_output(reply, allowed_accounts)`** — redacts canaries, the internal
  prompt, and any account that isn't the verified holder's. The `output_filter`
  guardrail.
- **`strip_protected_attributes(text)`** — removes names and zip codes before a
  credit decision. The `strip_protected` guardrail (the fair-lending fix).

---

## `auditor/` — the engine that runs the audit

### `attack_source.py` — build the test suite
- Resolves the PyRIT attack phrasings: prefers the installed `pyrit` package;
  falls back to the vendored MIT templates in `attacks/pyrit_vendored/`.
  `pyrit_source()` reports which is in use (shown on the report for provenance).
- `wrap_jailbreak(template, objective)` inserts an objective into a jailbreak
  template's `{{ prompt }}` slot.
- **`TestCase`** — one concrete test: id, module, objective id, technique,
  severity, OWASP tag, the `turns`, an optional `document`/`session`, the
  `expect` criteria, `control` flag, and (for fair lending) `pair`/`attribute`.
- **`build_suite(modules, include_controls, max_jailbreaks)`** — reads
  `attacks/objectives.yaml` and expands each objective across the PyRIT phrasings
  into the full ordered list of `TestCase`s (~53). This is the one place the
  "what" (objectives) and the "how" (phrasings) are combined.
- `suite_summary()` — counts by module + the PyRIT source, for the dashboard/CLI.

### `judge.py` — decide PASS / FAIL with evidence
- **`Finding`** — the verdict for one case: passed/failed, the `method` used
  (`canary`, `tool-check`, `pair-diff`, `grounding`, `llm-judge`), a rationale,
  and the attack + response transcript for the evidence pack.
- `judge_single(case, resp)` applies the case's `expect` block deterministically:
  - `no_leak` → `_leaked()` scans for canaries / unauthorized accounts (method
    `canary`);
  - `no_tool` / `must_execute` → check which tools executed (method `tool-check`);
  - `must_contain`, `must_cite` → content / grounding checks;
  - `must_decline_unknown` → `_judge_hallucination()`, the one fuzzy check: LLM
    judge when configured, deterministic grounding fallback otherwise.
- `judge_pair(case, resp_a, resp_b)` — fair lending: extracts the loan amount
  from each paired reply and fails if they differ (method `pair-diff`).

### `scoring.py` — risk score and rating
- `SEVERITY_WEIGHT` (critical=10 … low=1) and the rating thresholds
  (`Low` → `Guarded` → `Elevated` → `Critical`).
- **`ModuleScore`** / **`Scorecard`** dataclasses, with `pass_rate` computed over
  the real (non-control) cases.
- `score(findings, module_titles)` — groups findings by module, weights the real
  failures by severity into a single `risk_score`, derives the `rating`, and
  counts `control_failures` (over-blocking). Modules are sorted most-severe
  first.

### `remediation.py` — prove each fix
- `MODULE_FIX` maps each module to the one guardrail that remediates it and a
  human-readable description.
- `remediate(baseline)` — for each failing module, re-runs just that module with
  that single guardrail on, and returns a `Remediation` (before/after pass rate,
  resolved?, any control regressions). This is what turns "we recommend a
  control" into "we proved the control works."

### `regmap.py` — map to the frameworks
- `MODULE_FRAMEWORKS` ties each module to specific controls in OWASP LLM Top 10,
  NIST AI RMF, SR 11-7, and (for Fair Lending) ECOA/Reg B.
- `mapping_rows()` flattens it for the report's regulatory-mapping table. This is
  a mapping to controls, not a compliance attestation.

### `runner.py` — orchestrate a run
- **`AuditResult`** — the full output of a run: bot version, guardrails, engine,
  PyRIT source, duration, the `Scorecard`, and all `Finding`s.
- `_run_case(bot, case)` — sends a case to the bot (paired, multi-turn, or
  single) and calls the right judge.
- `run_audit(bot_version, guardrails, modules, engine, max_jailbreaks, progress)`
  — builds the suite, creates the bot with the right guardrails (v1=none,
  v2=all, or a custom set for remediation), runs every case, scores the run, and
  optionally emits `progress` events (used by the dashboard's live stream).

---

## Consuming the results

### `report.py` — the HTML validation report
- `render_html(result, remediations)` builds a self-contained, themeable HTML
  report (no external assets): the rating card, per-module scorecard, failing
  findings with attack/response evidence, the remediation table, and the
  regulatory mapping. `write_report()` saves it to the output dir.

### `gate.py` — the CI release gate
- `evaluate(result, max_risk)` returns a `GateResult` (passed + reasons). It
  fails when the risk score exceeds the threshold, any critical module has a real
  failure, or a control test regressed. The CLI's `gate` command maps this to the
  process exit code (0 pass / 1 fail) that a pipeline keys off.

### `storage.py` — inventory + history (SQLite)
- Schema: an `inventory` table (the AI model inventory — "Model Inventory": owner, risk
  tier, data classification, last tested, last rating) and a `runs` table (every
  audit's score, counts, and full JSON).
- `init_db(seed=True)` seeds the two demo bots; `record_run()` stores a run and
  updates the inventory; `list_inventory()`, `list_runs()`, `get_run()` read
  them back. The DB lives under `output/` and is regenerated.

---

## The two entry points

### `cli.py` — command line
Subcommands, each mapping to the engine above:
- `audit --version v1|v2 [--report path] [--with-remediation]` — run + print the
  scorecard, store it, optionally write the report.
- `remediate` — baseline then fix each module, print before/after.
- `gate --version v1|v2 [--max-risk N]` — run the gate, **exit 1 on fail** (this
  is what CI calls).
- `inventory`, `suite` — list the inventory / show the suite summary.

### `api.py` — FastAPI app + dashboard
- `GET /` serves `static/dashboard.html`.
- `GET /api/health` — status + which attack source / engine / judge are active.
- `GET /api/suite`, `GET /api/inventory`, `GET /api/runs`,
  `GET /api/report/{run}` — read endpoints.
- `POST /api/audit`, `POST /api/remediate` — run synchronously, return JSON.
- `GET /api/audit/stream` — **Server-Sent Events**: runs an audit and streams one
  event per case so the dashboard's risk meter fills live, then a `done` event
  with the scorecard and gate result.

### `static/dashboard.html`
A single self-contained page: the risk meter, per-module bars, a live log, and
the gate banner. It opens an `EventSource` on `/api/audit/stream`, updates the UI
as each `case` event arrives, and links to the stored report on `done`.

---

## End-to-end trace of one audit

1. `cli audit --version v1` (or the dashboard's **Audit v1**) calls
   `run_audit("v1")`.
2. `run_audit` → `attack_source.build_suite()` combines `objectives.yaml` with
   the PyRIT phrasings into ~53 `TestCase`s, and creates a `ABCBankBot` with
   `Guardrails.none()`.
3. For each case, `_run_case` sends the prompt(s) to `bot.chat()` and passes the
   `BotResponse` to `judge_single` / `judge_pair`, producing a `Finding` (with a
   deterministic `method` where possible).
4. `scoring.score()` turns the findings into a `Scorecard` (risk 39.3, rating
   **Critical**).
5. `storage.record_run()` saves it; `gate.evaluate()` returns **fail** (exit 1).
6. `report.render_html()` can write the evidence report; `remediation.remediate()`
   can re-run each module with one guardrail to prove the fix.
7. Running the same with `"v2"` (`Guardrails.all()`) yields rating **Low**, gate
   **pass** — the before/after story.

---

## Why it's structured this way (design intent)

- **Determinism first.** The serious verdicts (`canary`, `tool-check`,
  `pair-diff`) never call a model, so findings are reproducible and auditable.
- **One bot, many configs.** `Guardrails` lets v1, v2, and each single-guardrail
  remediation reuse the same code — the only honest way to show before/after.
- **Optional AI, isolated.** Only `llm.py` touches Azure; everything degrades to
  deterministic logic, so the whole system runs offline.
- **Inputs vs engine.** `attacks/` and `data/` are editable inputs; `app/` is the
  engine. You tune tests without touching code.

See also: `docs/architecture.md` (the diagram), `docs/AI_USAGE.md` (where AI is
used), and `docs/AZURE_SETUP.md` (switching to real models).
