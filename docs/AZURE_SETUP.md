# Azure setup — switch from mock mode to real models

By default the project runs **fully offline in mock mode** (no keys, no network).
Follow these steps to point it at your real Azure OpenAI deployment and, if you
want, Azure AI Content Safety (Prompt Shields).

You need up to six values: four for Azure OpenAI, two for Content Safety (only if
you want the real Prompt Shields guardrail). All of them go into one `.env` file.

---

## Part A — Get the Azure OpenAI details (4 values)

You need an Azure OpenAI resource with a model deployed (e.g. GPT-4o).

1. **Endpoint + key** — Azure Portal → your **Azure OpenAI** resource → left menu
   **Keys and Endpoint**.
   - Copy **Endpoint** → `AZURE_OPENAI_ENDPOINT`
     (looks like `https://your-resource.openai.azure.com/`)
   - Copy **KEY 1** → `AZURE_OPENAI_API_KEY`
2. **Deployment name** — **Azure AI Foundry** (or Azure OpenAI Studio) →
   **Deployments**. This is the **name you gave the deployment**, not the model
   name (e.g. you deployed `gpt-4o` under the name `gpt-4o-prod` → use
   `gpt-4o-prod`).
   - → `AZURE_OPENAI_DEPLOYMENT`
3. **API version** — leave the default `2024-10-21` (a stable GA version). Change
   it only if your tenant requires a specific one.
   - → `AZURE_OPENAI_API_VERSION`

> No deployment yet? AI Foundry → **Deployments → + Deploy model** → pick
> `gpt-4o` → give it a name → that name is your deployment value.

---

## Part B — Get the Content Safety details (2 values, optional)

Only needed if you want the `prompt_shield` guardrail to use **real** Azure
Prompt Shields instead of the built-in regex fallback.

1. Azure Portal → your **Content Safety** (Azure AI Services) resource →
   **Keys and Endpoint**.
   - Endpoint → `AZURE_CONTENT_SAFETY_ENDPOINT`
   - KEY 1 → `AZURE_CONTENT_SAFETY_KEY`

Skip this if you have no Content Safety resource — the guardrail still works via
the deterministic detector.

---

## Part C — Create and fill the `.env` file

In the project root (same folder as `requirements.txt`):

1. Copy the template. In PowerShell:
   ```powershell
   Copy-Item .env.example .env
   ```
2. Open `.env` and fill in your values:
   ```ini
   AZURE_OPENAI_ENDPOINT=https://your-resource.openai.azure.com/
   AZURE_OPENAI_API_KEY=<your key 1>
   AZURE_OPENAI_DEPLOYMENT=gpt-4o-prod
   AZURE_OPENAI_API_VERSION=2024-10-21

   AZURE_CONTENT_SAFETY_ENDPOINT=https://your-cs-resource.cognitiveservices.azure.com/
   AZURE_CONTENT_SAFETY_KEY=<your cs key>

   AUDITOR_USE_LLM_TARGET=false
   AUDITOR_USE_LLM_JUDGE=false
   AUDITOR_GATE_MAX_RISK=10
   ```

---

## Part D — Turn on the AI you want

The flags decide what actually uses the model (all default to `false` = mock):

| Flag | Set to `true` to… |
|---|---|
| `AUDITOR_USE_LLM_TARGET` | attack your **real** Azure OpenAI deployment instead of the mock bot |
| `AUDITOR_USE_LLM_JUDGE` | use the model for the **hallucination** judge (grounding fallback otherwise) |

The `prompt_shield` guardrail uses real Prompt Shields automatically once the two
`AZURE_CONTENT_SAFETY_*` values are filled in — no separate flag.

Set the one(s) you want to `true` and save.

---

## Part E — Verify it picked them up

1. Install the Azure SDK (only needed in LLM mode):
   ```powershell
   .\.venv\Scripts\python.exe -m pip install openai
   ```
2. Start the server (`run.bat`) and open **http://localhost:8000/api/health**.
   You'll see:
   ```json
   {"engine":"llm","llm_judge":true,"content_safety":true, "...": "..."}
   ```
   - `engine: "llm"` → the target bot is hitting Azure OpenAI
   - `llm_judge: true` → the LLM judge is on
   - `content_safety: true` → Prompt Shields is wired up

   If any shows `mock` / `false`, that key or flag isn't set — recheck `.env`.
3. Run an audit (`audit.bat v1`). It now runs against the live model, with
   automatic fallback to the deterministic logic if a call is content-filtered or
   times out.

---

## How it works under the hood

On startup `app/config.py` reads `.env`, and `app/llm.py` only calls Azure when
`llm_available` is true (all three Azure OpenAI values present) **and** the
matching flag is set — otherwise it returns `None` and the caller uses the
deterministic path. So a missing key or a filtered response never crashes a run;
it falls back.

| Setting | Read in | Used by |
|---|---|---|
| `AZURE_OPENAI_*` | `config.py` → `Settings.llm_available` | `llm.chat()` — target bot & LLM judge |
| `AZURE_CONTENT_SAFETY_*` | `config.py` → `content_safety_available` | `llm.prompt_shield()` — `prompt_shield` guardrail |
| `AUDITOR_USE_LLM_TARGET` | `config.py` | `target_bot/bot.py` engine selection |
| `AUDITOR_USE_LLM_JUDGE` | `config.py` | `auditor/judge.py` hallucination check |

---

## Security notes (for a bank setup)

- `.env` is already in `.gitignore` — **never commit it**.
- For a real deployment, pull these values from **Key Vault / Managed Identity**
  rather than a file. The `.env` is for local and demo use only.
- If your Azure OpenAI sits behind **Private Link** or pins a specific API
  version, a call may fail — the health page still loads and the system falls
  back, so check the server console for the exact Azure error.

See also: `docs/AI_USAGE.md` (what each AI component does) and
`.env.example` (the template).
