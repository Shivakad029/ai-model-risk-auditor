# Running AI Model Risk Auditor in Microsoft Visual Studio

This is a **Python** project (FastAPI + a small CLI). These steps are for
**Visual Studio 2022** on Windows — not VS Code. All steps work offline in mock
mode; no Azure account is needed.

---

## 1. One-time: install the Python workload

1. Open **Visual Studio Installer** → **Modify** on your VS 2022.
2. Under **Workloads**, check **Python development**.
3. Click **Modify** to install. This gives you the Python project system, the
   environments window, and pytest integration in Test Explorer.

If you don't have a Python interpreter yet, the Python workload can install one,
or install **Python 3.11 / 3.12** from python.org and VS will detect it.

---

## 2. Open the solution

1. Unzip `ai-model-risk-auditor.zip`.
2. In Visual Studio: **File → Open → Project/Solution**.
3. Select **`AIModelRiskAuditor.sln`** in the unzipped folder.

The Solution Explorer will show the project with `run_server.py` as the startup
file (shown in **bold**).

> Alternative, no solution file: **File → Open → Folder** and pick the unzipped
> folder. You get full editing and the terminal, but the green Run button and
> Test Explorer are wired up by the `.sln`, so prefer step 2.

---

## 3. Create the virtual environment & install packages

1. In **Solution Explorer**, expand the project and right-click
   **Python Environments → Add Environment…**
2. Choose **Virtual environment**, base it on your Python 3.11/3.12, name it
   `.venv`, and **check "Install packages from requirements.txt"**. Click
   **Create**.

That installs FastAPI, Uvicorn, Pydantic, PyYAML, httpx and pytest.

If you skipped the checkbox, open **View → Terminal** (or the Developer
PowerShell) in the project folder and run:

```powershell
py -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

Make sure the new `.venv` is the **active environment** (bold) in the Python
Environments window.

---

## 4. Run the dashboard

- Press **F5** (Debug) or **Ctrl+F5** (Run without debugging).
- `run_server.py` starts Uvicorn on **http://localhost:8000**.
- Open that URL in a browser. Click **Audit v1** to watch the risk meter climb to
  **Critical**, **Audit v2** to see it drop to **Low**, and **Auto-remediate** to
  watch each module go red → green.

To stop, press the red **Stop** button or close the console window.

---

## 5. Run the command line (optional, no server)

Open the terminal in the project folder (with `.venv` active) and run any of:

```powershell
python -m app.cli suite                 # show the test-suite summary
python -m app.cli audit --version v1    # 🔴 Critical
python -m app.cli audit --version v2    # 🟢 Low
python -m app.cli remediate             # fix each module, show before/after
python -m app.cli gate   --version v1   # release gate — exits 1 (fail)
python -m app.cli gate   --version v2   # release gate — exits 0 (pass)
python -m app.cli audit  --version v1 --report report.html --with-remediation
```

---

## 6. Run the tests

**Option A — Test Explorer (GUI):**
1. **Test → Test Explorer**.
2. VS discovers the 14 pytest tests under `tests/` (the project sets the test
   framework to Pytest). If none appear, confirm `.venv` is the active
   environment and that `pytest` is installed, then click the refresh icon.
3. Click **Run All**. All 14 should pass.

**Option B — terminal:**
```powershell
python -m pytest tests/ -q
```

Expected:
```
..............                                                           [100%]
14 passed
```

These tests prove the core behavior: v1 is **Critical**, v2 is **Low**, the gate
blocks v1 and passes v2, every failing module is remediated, and the
deterministic judges catch the planted canary leak, the unauthorized transfer,
and the zip-code bias.

---

## 7. (Optional) Switch to real Azure

Copy `.env.example` to `.env` in the project root and fill in your values:

| Variable | Effect |
| --- | --- |
| `AZURE_OPENAI_*` + `AUDITOR_USE_LLM_TARGET=true` | attack a real Azure OpenAI deployment instead of the mock bot |
| `AZURE_CONTENT_SAFETY_*` | the `prompt_shield` guardrail uses real Prompt Shields |
| `AUDITOR_USE_LLM_JUDGE=true` | the LLM judge runs against your model |

Nothing else changes — the same attacks, judging and gate run against the live
model, with a deterministic fallback if a call is filtered or the endpoint is slow.

---

## Troubleshooting

| Symptom | Fix |
| --- | --- |
| Tests don't appear in Test Explorer | Set the active env to `.venv`; ensure `pytest` is installed; Test → "Configure Run Settings" not needed — pytest is set in the `.pyproj`. |
| `ModuleNotFoundError: fastapi` | The `.venv` isn't active or packages didn't install — redo step 3. |
| Run button does nothing | Confirm `run_server.py` is the startup file (bold in Solution Explorer); right-click it → **Set as Startup File**. |
| Port 8000 in use | Edit `run_server.py` and change `port=8000` to another port. |
| "Python not found" | Install Python 3.11/3.12 and re-open; add it under Python Environments. |
