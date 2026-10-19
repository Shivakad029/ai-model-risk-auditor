# Architecture — AI Model Risk Auditor

An agentic AI model-risk auditor. Attack phrasings from **PyRIT** drive banking
red-team objectives through a target assistant; each answer is judged with
evidence, scored, remediated, mapped to controls, and gated in CI.

A styled, interactive version of this diagram is in **`docs/architecture.html`**
(open it in any browser). The Mermaid source below renders on GitLab/GitHub and
in Visual Studio's Markdown preview.

```mermaid
flowchart TD
    subgraph S1["01 · Attack sources"]
        PYRIT["PyRIT<br/><small>jailbreak phrasings · MIT</small>"]
        OBJ["objectives.yaml<br/><small>6 banking modules</small>"]
    end
    subgraph S2["02 · Audit engine"]
        ATK["attack_source<br/><small>build test suite</small>"]
        RUN["runner<br/><small>drive each case</small>"]
        BOT["ABC Bank Assistant<br/><small>v1 Critical / v2 Governed · 6 guardrails</small>"]
    end
    subgraph S3["03 · Judging"]
        DET["Deterministic judge<br/><small>canary · tool · pair-diff</small>"]
        LLM["LLM judge<br/><small>hallucination · grounding fallback</small>"]
    end
    subgraph S4["04 · Analysis"]
        SCORE["scoring<br/><small>risk score + rating</small>"]
        REM["remediation<br/><small>prove each fix</small>"]
        REG["regmap<br/><small>SR 11-7 · NIST · OWASP · ECOA</small>"]
    end
    subgraph S5["05 · Surfaces & outputs"]
        REP["Validation report<br/><small>HTML</small>"]
        GATE["Release gate<br/><small>GitLab CI</small>"]
        DB["Storage<br/><small>SQLite inventory + runs</small>"]
        API["API + Dashboard<br/><small>FastAPI + SSE</small>"]
    end
    subgraph S6["Platform & runtime · cross-cutting"]
        AZ["Azure OpenAI · Content Safety (Prompt Shields) · AI Foundry · GitLab CI/CD<br/><small>Mock mode runs fully offline — Azure optional</small>"]
    end

    PYRIT --> ATK
    OBJ --> ATK
    ATK --> RUN --> BOT --> DET
    BOT --> LLM
    DET --> SCORE
    LLM --> SCORE
    SCORE --> REM --> REG
    REG --> REP
    REG --> GATE
    REG --> DB
    REG --> API
    S2 -.runs on.- S6
    S3 -.runs on.- S6
```

## Flow in words

1. **Attack sources** — PyRIT supplies the adversarial phrasings; `objectives.yaml`
   supplies the benign banking goals across six modules (Prompt Injection, Document Injection,
   Data Leakage, Hallucination, Fair Lending, Excessive Agency).
2. **Audit engine** — `attack_source` expands objectives × phrasings into the
   suite; `runner` drives each case against the target bot (v1 ungoverned / v2
   governed, six toggleable guardrails).
3. **Judging** — deterministic for the serious verdicts (canary leaks, tool
   execution, fair-lending pair comparison); an LLM judge only for hallucination,
   with a grounding fallback.
4. **Analysis** — weighted risk score and rating; one-control-per-module
   remediation that re-tests to prove the fix; regulatory mapping.
5. **Surfaces** — HTML validation report, GitLab CI release gate, SQLite
   inventory + run history, and a FastAPI dashboard with a live SSE risk meter.

The platform layer is cross-cutting: with no credentials the whole system runs
offline in deterministic **mock mode**; add Azure env vars to attack a real
Azure OpenAI deployment and use Prompt Shields.
