"""Central configuration. Everything works offline (mock mode) when no Azure settings are present."""

from __future__ import annotations

import os
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA_DIR = ROOT / "data"
CONFIG_DIR = ROOT / "config"
ATTACKS_DIR = ROOT / "attacks"


def _load_dotenv() -> None:
    """Minimal .env loader so the project has no extra dependency for it."""
    env_file = ROOT / ".env"
    if not env_file.exists():
        return
    for line in env_file.read_text(encoding="utf-8").splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        value = value.strip()
        # Strip an inline comment (" # ...") on unquoted values, so a line like
        #   AUDITOR_USE_LLM_TARGET=true   # attack a real deployment
        # is read as "true", not "true   # attack...".
        if value[:1] not in ("'", '"') and " #" in value:
            value = value.split(" #", 1)[0].rstrip()
        os.environ.setdefault(key.strip(), value.strip('"').strip("'"))


_load_dotenv()


@dataclass(frozen=True)
class Settings:
    azure_openai_endpoint: str
    azure_openai_key: str
    azure_openai_deployment: str
    azure_openai_api_version: str
    azure_auth_mode: str          # "key" (default) or "entra" (Microsoft Entra ID token)
    content_safety_endpoint: str
    content_safety_key: str
    use_llm_judge: bool
    use_llm_target: bool
    debug_llm: bool
    llm_log_file: str
    output_dir: Path
    db_path: Path
    gate_max_risk: float

    @property
    def is_foundry_v1(self) -> bool:
        """A Microsoft Foundry / AI Services 'v1' OpenAI-compatible endpoint, which is
        called with the plain OpenAI client (base_url) rather than the classic
        AzureOpenAI client."""
        ep = self.azure_openai_endpoint.rstrip("/").lower()
        return "services.ai.azure.com" in ep or ep.endswith("/openai/v1") or self.azure_auth_mode == "entra"

    @property
    def llm_available(self) -> bool:
        has_creds = bool(self.azure_openai_key) or self.azure_auth_mode == "entra"
        return bool(self.azure_openai_endpoint and self.azure_openai_deployment and has_creds)

    @property
    def content_safety_available(self) -> bool:
        return bool(self.content_safety_endpoint and self.content_safety_key)


def _flag(name: str, default: bool = False) -> bool:
    # Tolerate a stray inline comment or trailing text: judge the first token only.
    raw = os.getenv(name, str(default)).strip().split()
    return bool(raw) and raw[0].strip('"').strip("'").lower() in {"1", "true", "yes", "on"}


@lru_cache(maxsize=1)
def get_settings() -> Settings:
    output_dir = Path(os.getenv("AUDITOR_OUTPUT_DIR", str(ROOT / "output")))
    output_dir.mkdir(parents=True, exist_ok=True)
    return Settings(
        azure_openai_endpoint=os.getenv("AZURE_OPENAI_ENDPOINT", ""),
        azure_openai_key=os.getenv("AZURE_OPENAI_API_KEY", ""),
        azure_openai_deployment=os.getenv("AZURE_OPENAI_DEPLOYMENT", ""),
        azure_openai_api_version=os.getenv("AZURE_OPENAI_API_VERSION", "2024-10-21"),
        azure_auth_mode=os.getenv("AZURE_AUTH_MODE", "key").strip().lower(),
        content_safety_endpoint=os.getenv("AZURE_CONTENT_SAFETY_ENDPOINT", ""),
        content_safety_key=os.getenv("AZURE_CONTENT_SAFETY_KEY", ""),
        use_llm_judge=_flag("AUDITOR_USE_LLM_JUDGE"),
        use_llm_target=_flag("AUDITOR_USE_LLM_TARGET"),
        debug_llm=_flag("AUDITOR_DEBUG_LLM"),
        llm_log_file=os.getenv("AUDITOR_LLM_LOG", ""),
        output_dir=output_dir,
        db_path=Path(os.getenv("AUDITOR_DB_PATH", str(output_dir / "auditor.db"))),
        gate_max_risk=float(os.getenv("AUDITOR_GATE_MAX_RISK", "10")),
    )
