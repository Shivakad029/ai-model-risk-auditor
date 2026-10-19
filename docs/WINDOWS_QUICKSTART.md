# Windows quick start

The project is plain Python and runs natively on Windows — no separate Windows
build. These `.bat` files (in the project root) wrap the setup/run/test steps so
you don't have to activate the virtual environment or fight PowerShell's
execution policy. They call the venv's Python directly.

**Double-click, or run from a terminal, in this order:**

| File | What it does |
| --- | --- |
| `setup.bat` | One-time. Creates `.venv` and installs all dependencies. |
| `test.bat`  | Runs the 14 tests (expect `14 passed`). |
| `run.bat`   | Starts the dashboard at http://localhost:8000 (Ctrl+C to stop). |
| `audit.bat` | Runs an audit in the console. `audit.bat v1` or `audit.bat v2`. |

That's it. If `setup.bat` says Python isn't found, install Python 3.11 or 3.12
from python.org (check **"Add python.exe to PATH"** during install), then run
`setup.bat` again.

Prefer the manual commands instead? See `docs/VISUAL_STUDIO.md`.
