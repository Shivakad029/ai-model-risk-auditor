"""Startup entry point for Visual Studio's green Run button.

Launches the dashboard + API on http://localhost:8000.
Equivalent to: uvicorn app.api:app --reload
"""
import uvicorn

if __name__ == "__main__":
    uvicorn.run("app.api:app", host="127.0.0.1", port=8000, reload=True)
