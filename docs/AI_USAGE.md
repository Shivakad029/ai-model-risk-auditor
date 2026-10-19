# AI usage in AI Model Risk Auditor

This document accounts for exactly where AI (LLMs and AI classifiers) is used in
the solution, where it is deliberately **not** used, and how that is governed.
It is written for a model-risk / audit reader.

> **Bottom line:** AI is used in up to four places, all optional. Every serious
> pass/fail verdict — data leaks, unauthorized actions, bias — is **deterministic
> and model-free**, so findings are reproducible and auditable. With no Azure
> credentials, the tool runs fully offline with **zero AI calls** and still
> produces the complete Critical → Low result.

---

## Two different "AIs" — keep them separate

| | What it is | Role |
|---|---|---|
| **AI under test** | the target bank assistant | the thing the auditor attacks |
| **AI used by the auditor** | a small, optional amount | only the fuzzy judgments |

The auditor's credibility depends on the second being minimal and the serious
verdicts not depending on it.

---

## Every place AI is used

| # | Where | Which AI | On by default | Input → Output | Fallback when off / fails |
|---|---|---|---|---|---|
| 1 | **Target bot** (under test) | Azure OpenAI (e.g. GPT-4o) | No (mock) | attack prompt → bot reply | rule-based mock bot |
| 2 | **`prompt_shield` guardrail** | Azure AI Content Safety – Prompt Shields (classifier) | No | user prompt → attack? yes/no | deterministic regex detector |
| 3 | **LLM judge** (hallucination check only) | Azure OpenAI | No | bot reply → invented a policy? yes/no | deterministic grounding check (`[Source:]`) |
| 4 | **Attack phrasings** | PyRIT templates | n/a | objective → disguised prompt | static text substitution (no model) |

Precise notes:

- **#4 is not an LLM at runtime.** PyRIT *can* use a model to mutate attacks, but
  this build uses its **static, vendored jailbreak templates** — string
  substitution, fully deterministic and offline. Attack generation makes no AI
  call here.
- **#1, #2, #3 are each optional**, toggled by `AUDITOR_USE_LLM_TARGET`, the
  `prompt_shield` guardrail flag, and `AUDITOR_USE_LLM_JUDGE`. With no Azure
  keys, all three fall back and the system runs with zero AI calls.
- The only place the auditor's **own** reasoning uses a model is **#3, one
  check** (did the bot invent a policy?), because "is this made up?" is genuinely
  fuzzy. Everything else is rules.

### Where each lives in the code

| Component | File |
|---|---|
| Azure OpenAI + Prompt Shields wrappers | `app/llm.py` |
| Target bot (mock + `llm` engine) | `app/target_bot/bot.py` |
| `prompt_shield` guardrail (regex + Prompt Shields) | `app/target_bot/guards.py` |
| LLM judge + deterministic fallback | `app/auditor/judge.py` (`_judge_hallucination`) |
| PyRIT template loading / substitution | `app/auditor/attack_source.py` |
| Feature flags | `app/config.py` / `.env` |

---

## Where AI is deliberately NOT used

Every serious verdict is deterministic — no model involved, even when Azure is
connected:

- **Data leak** → literal canary-string match (`"CANARY-ABC-7F3A" in reply`)
- **Unauthorized action** → did the `transfer_funds` tool execute? (set membership)
- **Fair-lending bias** → compare two loan amounts as numbers
- **Risk score, rating, remediation, release gate, regulatory mapping** → pure
  arithmetic and rules

So a leak is **proven**, not **assessed by an AI**. That is what makes a finding
reproducible and re-runnable by a validator.

---

## Model-risk implications

- **Bounded model reliance.** The single model-graded check (hallucination) has a
  deterministic fallback, and the judging **method is recorded on every finding**
  (`canary`, `tool-check`, `pair-diff`, `grounding`, `llm-judge`), so a validator
  can see precisely which verdicts were AI-graded.
- **An LLM judge is never the sole proof.** Leaks and unauthorized actions are
  confirmed by canaries and tool checks; the LLM judge's agreement rate against
  human labels is reported (see the deck's Q&A appendix), not assumed.
- **Safe degradation.** If a model is slow, content-filtered, or offline, the
  affected call falls back to deterministic logic rather than failing — important
  for both demos and production.
- **Azure-native and governable.** #1 and #3 are Azure OpenAI; #2 is Azure AI
  Content Safety — all inside the bank's tenant, governable through Azure AI
  Foundry, with every prompt, reply, and score logged for the audit trail.

---

## One-line summary

AI is used in up to four optional places — the target model under test, one AI
guardrail (Prompt Shields), one AI judge (hallucination only), and PyRIT's
(static) attack templates. Every serious verdict is deterministic and model-free,
so findings are reproducible and auditable; with no keys, the tool runs fully
offline with zero AI calls.
